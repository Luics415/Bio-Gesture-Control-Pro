"""Explicit ocular calibration, isolated from camera preview and desktop input.

The pure collector requires fresh samples from settled, uninterrupted segments.
The Tk shell never enables control: a successful callback only hands the caller
a calibrated, independently validated mapping. The caller keeps control paused.
"""

import ctypes
from collections import Counter, deque
from ctypes import wintypes
import logging
import math
import os
import time
import tkinter as tk

from .coordinates import RectMonitor
from .gaze import CALIBRATION_TARGETS, FEATURE_COUNT, VALIDATION_TARGETS, GazeCalibration, GazeObservation
from .gaze_diagnostics import (PRECISION_ENGINE_IDS, PRECISION_OBSERVATION_SCHEMA,
                               build_diagnostic_report, diagnostic_prediction)
from .gaze_pointer import GazePointerFilter
from .ui import compact_button


WIZARD_VALIDATION_TARGETS = (*VALIDATION_TARGETS, (0.5, 0.3))
WIZARD_PALETTES = {
    "neutral": {"background": "#aeb5bb", "text": "#17242d", "muted": "#33434e", "accent": "#075663"},
    "dark": {"background": "#242b33", "text": "#edf2f5", "muted": "#b6c2cb", "accent": "#79d8dc"},
}


class CalibrationCollector:
    """Engine-provided training targets, then independent validation targets.

    A blink ends a segment, not the entire point. Fresh samples must settle
    again before collection resumes. Only time between samples in the same
    uninterrupted segment counts; neither blinks nor repeated UI polls add time.
    A bounded point deadline prevents collecting unrelated samples indefinitely.
    """

    SETTLE_SECONDS = 0.7
    RESUME_SETTLE_SECONDS = 0.25
    COLLECT_SECONDS = 0.8
    MIN_SAMPLES = 8
    MIN_SAMPLE_SPAN = 0.6
    MAX_SAMPLE_AGE = 0.25
    POINT_TIMEOUT_SECONDS = 20.0

    def __init__(self, calibration_factory=GazeCalibration):
        self._factory = calibration_factory
        self.calibration = None
        self.phase = "idle"
        self.point_index = 0
        self.message = "Cabeza cómoda y relativamente quieta; mueve solo la mirada al centro del punto."
        self._samples = []
        self._validation_samples = []
        self._point_since = None
        self._last_timestamp = -math.inf
        self._last_now = None
        self._target_since = None
        self._segment_last = None
        self._useful_seconds = 0.0
        self._settle_duration = self.SETTLE_SECONDS
        self._drop_reasons = Counter()
        self._last_drop = None
        self._retry_point = None
        self.capture_points = []
        self._attempts = 1

    @property
    def validation_samples(self):
        return tuple(self._validation_samples)

    @property
    def running(self):
        return self.phase in ("calibration", "validation")

    @property
    def targets(self):
        return self.validation_targets if self.phase == "validation" else self.training_targets

    @property
    def training_targets(self):
        return tuple(getattr(self.calibration or self._factory, "training_targets", CALIBRATION_TARGETS))

    @property
    def validation_targets(self):
        return tuple(getattr(self.calibration or self._factory, "validation_targets", WIZARD_VALIDATION_TARGETS))

    @property
    def required_collection_seconds(self):
        """Only new-engine training may request a longer capture, never filtering."""
        if self.phase != "calibration":
            return self.COLLECT_SECONDS
        return max(self.COLLECT_SECONDS, getattr(self.calibration or self._factory,
                                                "training_collection_seconds", self.COLLECT_SECONDS))

    @property
    def target(self):
        return self.targets[self.point_index] if self.running else None

    def start(self, now):
        if not self._valid_time(now):
            raise ValueError("El reloj de calibración no es válido")
        self.calibration = self._factory()
        self.phase = "calibration"
        self.point_index = 0
        self._validation_samples = []
        self.capture_points = []
        self._samples = []
        self._last_timestamp = -math.inf
        self._last_now = self._point_since = now
        self._begin_point(now)
        self._retry_point = None
        self.message = "Mira el centro del punto."

    def _begin_point(self, now):
        self._samples = []
        self._point_since = self._target_since = now
        self._segment_last = None
        self._useful_seconds = 0.0
        self._settle_duration = self.SETTLE_SECONDS
        self._drop_reasons = Counter()
        self._last_drop = None
        self._attempts = 1

    @property
    def can_retry_point(self):
        return self.phase == "error" and self._retry_point is not None

    def retry_point(self, now):
        """Retry only a timed-out, uncommitted target, never a failed accuracy gate."""
        if not self.can_retry_point or not self._valid_time(now):
            return False
        self.phase, self.point_index = self._retry_point
        prior = next((p for p in self.capture_points
                      if p["phase"] == self.phase and p["point_index"] == self.point_index + 1), None)
        self._retry_point = None
        self._last_now = now
        self._begin_point(now)
        self._attempts = prior["attempts"] + 1 if prior else 1
        self.message = "Mira el centro del mismo punto."
        return True

    @staticmethod
    def _valid_time(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

    def _usable(self, observation, now):
        try:
            base_usable = (
                isinstance(observation, GazeObservation) and observation.valid is True
                and self._valid_time(observation.timestamp)
                and 0 <= now - observation.timestamp <= self.MAX_SAMPLE_AGE
                and len(observation.features) == FEATURE_COUNT
                and all(self._valid_time(v) for v in observation.features)
                and observation.features[6] > 0
            )
            if not base_usable:
                return False
            if getattr(self.calibration, "engine_id", None) in PRECISION_ENGINE_IDS:
                from .gaze_precision import precision_observation_usable
                return precision_observation_usable(observation)
            return True
        except (TypeError, ValueError, AttributeError):
            return False

    def fail(self, reason):
        if self.running and self.point_index < len(self.targets):
            self._record_capture("interrupted")
        if self.phase != "error":
            self._log_diagnostics("error")
        self.phase = "error"
        self.message = str(reason)
        self._samples = []
        self._retry_point = None

    def _record_capture(self, outcome):
        """One summary per target, including retries but never duplicated frames."""
        if not self.running or self.point_index >= len(self.targets):
            return
        key = self.phase, self.point_index + 1
        previous = next((p for p in self.capture_points
                         if (p["phase"], p["point_index"]) == key), None)
        elapsed = max(0.0, (self._last_now or 0) - (self._target_since or 0))
        rejected = dict(self._drop_reasons)
        if previous and self._attempts > previous["attempts"]:
            elapsed += previous["elapsed_seconds"]
            rejected = dict(Counter(previous["rejected"]) + Counter(rejected))
        item = dict(phase=self.phase, point_index=self.point_index + 1,
                    target=list(self.target), samples=len(self._samples),
                    useful_seconds=self._useful_seconds, elapsed_seconds=elapsed,
                    rejected=rejected, outcome=outcome, attempts=self._attempts)
        if previous:
            self.capture_points[self.capture_points.index(previous)] = item
        else:
            self.capture_points.append(item)

    def _log_diagnostics(self, outcome):
        report = getattr(self.calibration, "report", None)
        logging.info(
            "Calibración ocular: resultado=%s fase=%s punto=%s muestras=%s "
            "error_medio=%s error_maximo=%s variacion=%s peor_objetivo=%s objetivos=%s",
            outcome, self.phase, self.point_index + 1,
            getattr(report, "samples", 0), getattr(report, "mean_error", None),
            getattr(report, "max_error", None), getattr(report, "jitter_error", None),
            getattr(report, "worst_target", None), getattr(report, "target_count", 0),
        )

    def _restart_point(self, reason=None, *, discard=False):
        if discard:
            self._samples = []
            self._useful_seconds = 0.0
        self._point_since = None
        self._segment_last = None
        self._settle_duration = self.RESUME_SETTLE_SECONDS
        self.message = (f"{reason}. Vuelve a mirar el mismo punto." if reason
                        else "Esperando ojos visibles. Vuelve a mirar el mismo punto.")

    def interrupt(self, message):
        if self.running:
            self._restart_point(discard=True)
            self.message = str(message)

    def _timeout(self):
        phase, index = self.phase, self.point_index
        required_seconds = self.required_collection_seconds
        label = "Calibración" if phase == "calibration" else "Comprobación"
        reason = self._drop_reasons.most_common(1)
        detail = reason[0][0] if reason else "Llegan pocas muestras nuevas y estables"
        samples, duration = len(self._samples), self._useful_seconds
        self.fail(
            f"{label}: punto {index + 1} de {len(self.targets)} sin completar en "
            f"{self.POINT_TIMEOUT_SECONDS:g} s.\n"
            f"Recogidas {samples} muestras y {duration:.1f} s útiles; necesitamos "
            f"{self.MIN_SAMPLES} muestras y {required_seconds:.1f} s útiles.\n"
            f"Motivo principal: {detail}.\n"
            "Comprueba que ambos ojos sean visibles; reduce reflejos con luz suave o cambia el fondo. "
            "Puedes repetir solo este punto."
        )
        self.capture_points[-1]["outcome"] = "timeout"
        self._retry_point = phase, index

    def _accuracy_failure(self, report):
        details = [str(report.reason)]
        if math.isfinite(report.mean_error) and math.isfinite(report.max_error):
            if "Error medio" not in str(report.reason):
                details.append(f"Error medio: {report.mean_error:.1%}; máximo: {report.max_error:.1%}.")
            details.append("Porcentajes de la distancia en coordenadas normalizadas de pantalla, no de aciertos.")
        worst = getattr(report, "worst_target", None)
        if isinstance(worst, (tuple, list)) and len(worst) == 2:
            try:
                point = self.validation_targets.index(tuple(worst)) + 1
                details.append(f"Mayor desviación en el punto de comprobación {point} de {len(self.validation_targets)}.")
            except ValueError:
                pass
        details.append("Mira el centro de cada objetivo, no los dibujos de los ojos. "
                       "Cabeza cómoda y estable; mueve solo los ojos. "
                       "Si hay reflejos en los lentes, prueba el fondo oscuro o una luz suave frontal.")
        self.fail("\n".join(details))

    def update(self, observation, now):
        if not self.running:
            return
        if not self._valid_time(now) or (self._last_now is not None and now < self._last_now):
            self.fail("El reloj cambió. Reintenta la calibración.")
            return
        self._last_now = now
        if self._target_since is not None and now - self._target_since >= self.POINT_TIMEOUT_SECONDS:
            self._timeout()
            return
        if not self._usable(observation, now):
            # Invalid packets still advance the capture watermark. An older
            # valid packet cannot undo an already observed blink or occlusion.
            stamp = getattr(observation, "timestamp", None)
            if self._valid_time(stamp) and stamp <= now:
                self._last_timestamp = max(self._last_timestamp, stamp)
            reason = getattr(observation, "reason", "")
            reason = reason[:180] if isinstance(reason, str) else ""
            if not reason:
                reason = "Sin una imagen ocular nueva y válida"
            drop = (stamp if self._valid_time(stamp) else None, reason)
            if drop != self._last_drop:
                self._drop_reasons[reason] += 1
                self._last_drop = drop
            if reason.startswith("Ojos no disponibles"):
                self.fail(reason)
            else:
                self._restart_point(reason)
            return
        stamp = observation.timestamp
        if stamp <= self._last_timestamp:
            # A recent duplicate is just a UI poll; a replay is not continuity.
            if stamp < self._last_timestamp:
                self._restart_point()
            return
        if self._last_timestamp > -math.inf and stamp - self._last_timestamp > self.MAX_SAMPLE_AGE:
            self._restart_point()
        self._last_timestamp = stamp
        if self._point_since is None:
            self._point_since = stamp
        if stamp - self._point_since < self._settle_duration - 1e-9:
            self.message = "Mira el centro del punto."
            return
        if self._segment_last is not None:
            self._useful_seconds += stamp - self._segment_last
        self._segment_last = stamp
        self._samples.append(observation)
        self.message = (f"Mira su centro · {len(self._samples)} muestras · "
                        f"{min(self._useful_seconds, self.required_collection_seconds):.1f}/{self.required_collection_seconds:.1f} s útiles")
        if (len(self._samples) < self.MIN_SAMPLES
                or self._useful_seconds < max(self.required_collection_seconds, self.MIN_SAMPLE_SPAN) - 1e-9):
            return

        target = self.target
        try:
            if self.phase == "calibration":
                if not all(self.calibration.add_sample(sample, target) for sample in self._samples):
                    self.fail("No se pudieron aceptar las muestras. Reintenta la calibración.")
                    return
            else:
                self._validation_samples.extend((sample, target) for sample in self._samples)
            self._record_capture("complete")
            self.point_index += 1
            self._begin_point(now)
            self.message = "Mira el centro del nuevo punto."
            if self.point_index < len(self.targets):
                return
            if self.phase == "calibration":
                if not self.calibration.fit():
                    self.fail(self.calibration.report.reason)
                    return
                self.phase = "validation"
                self.point_index = 0
                self.message = f"Ahora comprobaremos la precisión con {len(self.validation_targets)} puntos nuevos."
                return
            report = self.calibration.validate(self._validation_samples)
            if not report.accepted or not self.calibration.ready:
                self._accuracy_failure(report)
                return
            self.phase = "complete"
            self.message = "Calibración validada. El control permanece en pausa."
            self._log_diagnostics("complete")
        except (ValueError, TypeError, ArithmeticError) as exc:
            logging.exception("No se pudo completar la calibración ocular")
            self.fail(f"No se pudo completar la calibración: {exc}")


def position_calibration_window(window, monitor: RectMonitor, *, _user32=None):
    """Use physical monitor coordinates; Tk's negative offsets mean something else.

    A Windows native position failure is fatal to calibration, since collecting
    against a different monitor rectangle would produce an incorrect mapping.
    """
    values = (monitor.left, monitor.top, monitor.width, monitor.height)
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values) or min(monitor.width, monitor.height) <= 0:
        raise ValueError("El monitor debe tener coordenadas enteras y tamaño positivo")
    window.geometry(f"{monitor.width}x{monitor.height}")
    window.update_idletasks()
    if os.name == "nt" or _user32 is not None:
        user32 = _user32 if _user32 is not None else ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        handle = user32.GetAncestor(window.winfo_id(), 2) or window.winfo_id()
        if not user32.SetWindowPos(handle, None, monitor.left, monitor.top, monitor.width, monitor.height, 0x0014):
            raise OSError("No se pudo colocar la calibración en la pantalla elegida")
    elif monitor.left < 0 or monitor.top < 0:
        raise OSError("La calibración en pantallas con origen negativo requiere el adaptador de Windows")
    else:
        window.geometry(f"{monitor.width}x{monitor.height}+{monitor.left}+{monitor.top}")


class GazeCalibrationDialog:
    """Full-monitor, explicit calibration window; Escape always cancels.

    ``latest_observation`` is a nonblocking reader of the most recent camera
    observation. It must not start a camera or perform inference on the Tk
    thread. ``on_success`` never implies permission to resume desktop input.
    """

    POLL_MS = 33
    PREVIEW_MAX_AGE = 0.35

    def __init__(self, parent, monitor, latest_observation, on_success, on_close,
                 *, calibration_factory=GazeCalibration, clock=time.monotonic,
                 latest_preview=None, set_preview_enabled=None,
                 latest_diagnostics=None, on_export_diagnostics=None):
        self.monitor = monitor
        self._latest_observation = latest_observation
        self._on_success, self._on_close = on_success, on_close
        self._clock = clock
        self._latest_preview = latest_preview
        self._set_preview_enabled = set_preview_enabled
        self._latest_diagnostics = latest_diagnostics
        self._on_export_diagnostics = on_export_diagnostics
        self._detail = False
        self._probe = False
        self._probe_stabilized = True
        self._probe_filter = GazePointerFilter()
        self._diagnostic_status = ""
        self._live_observation = None
        self._live_stamps = deque(maxlen=240)
        self._report_cache = None
        self._report_cache_key = None
        self._preview_enabled = False
        self._preview_image = None
        self._preview_stamp = None
        self._palette_name = "neutral"
        self._acquisition_background = "neutral"
        self.collector = CalibrationCollector(calibration_factory)
        self._closed = self._delivered = False
        self._after = None
        self._painted = None
        self.window = tk.Toplevel(parent)
        try:
            self.window.withdraw()
            self.window.title("Calibrar mirada · Bio-Gesture")
            self.window.configure(background=self.palette["background"])
            self.window.resizable(False, False)
            self.window.overrideredirect(True)
            self.window.protocol("WM_DELETE_WINDOW", self.destroy)
            self.window.bind("<Escape>", lambda event: self.escape())
            for key in ("d", "D"):
                self.window.bind(f"<KeyPress-{key}>", lambda event: self.toggle_details())
            for key in ("p", "P"):
                self.window.bind(f"<KeyPress-{key}>", lambda event: self.toggle_probe())
            for key in ("e", "E"):
                self.window.bind(f"<KeyPress-{key}>", lambda event: self.export_diagnostics())
            for key in ("f", "F"):
                self.window.bind(f"<KeyPress-{key}>", lambda event: self.toggle_probe_filter())
            self.window.bind("<Destroy>", self._window_destroyed)
            self.canvas = tk.Canvas(self.window, background=self.palette["background"], highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self._buttons = tk.Frame(self.window, bg=self.palette["background"])
            self._buttons.place(relx=1.0, rely=1.0, x=-14, y=-10, anchor="se")
            self.start_button = compact_button(self._buttons, "Iniciar", self.start, accent=True)
            self.start_button.pack(side="left", padx=7)
            self.background_button = compact_button(self._buttons, "Fondo: gris mate", self.toggle_background)
            self.background_button.pack(side="left", padx=7)
            compact_button(self._buttons, "Cancelar · Esc", self.destroy).pack(side="left", padx=7)
            self._diagnostic_buttons = tk.Frame(self.window, bg=self.palette["background"])
            self._diagnostic_buttons.place(relx=1.0, rely=1.0, x=-14, y=-43, anchor="se")
            self.detail_button = compact_button(self._diagnostic_buttons, "Detalle · D", self.toggle_details)
            self.detail_button.pack(side="left", padx=7)
            self.probe_button = compact_button(self._diagnostic_buttons, "Probar sin controlar PC · P", self.toggle_probe)
            self.probe_button.pack(side="left", padx=7)
            self.filter_button = compact_button(self._diagnostic_buttons, "Estabilizado · F", self.toggle_probe_filter)
            self.export_button = compact_button(self._diagnostic_buttons, "Exportar diagnóstico · E", self.export_diagnostics)
            self.export_button.pack(side="left", padx=7)
            self.window.deiconify()
            position_calibration_window(self.window, monitor)
            self.window.lift()
            self.window.grab_set()
            self.start_button.focus_set()
            self._paint()
            self._after = self.window.after(self.POLL_MS, self._tick)
        except Exception:
            self.destroy()
            raise

    def lift(self):
        if not self._closed:
            self.window.lift()

    def start(self):
        if self._closed or self.collector.running or getattr(self, "_probe", False):
            return
        self._report_cache = self._report_cache_key = None
        self._diagnostic_status = ""
        if not self.collector.retry_point(self._clock()):
            self._acquisition_background = getattr(self, "_palette_name", "neutral")
            self.collector.start(self._clock())
        self._preview_image = self._preview_stamp = None
        self._paint()

    def escape(self):
        if getattr(self, "_probe", False):
            self._probe = False
            self._reset_probe_filter()
            self._painted = None
            self._paint()
        else:
            self.destroy()

    def toggle_details(self):
        if self._closed or getattr(self, "_probe", False):
            return
        self._detail = not getattr(self, "_detail", False)
        self._painted = None
        self._paint()

    def toggle_probe(self):
        if (self._closed or self.collector.running
                or not getattr(self.collector.calibration, "fitted", False)):
            return
        self._probe = not getattr(self, "_probe", False)
        self._reset_probe_filter()
        self._painted = None
        self._preview_image = self._preview_stamp = None
        self._paint()

    def _reset_probe_filter(self):
        if not hasattr(self, "_probe_filter"):
            self._probe_filter = GazePointerFilter()
        self._probe_filter.reset()

    def toggle_probe_filter(self):
        """Change visualization only: never fit, validate, export or move input."""
        if self._closed or not getattr(self, "_probe", False) or self.collector.running:
            return
        self._probe_stabilized = not getattr(self, "_probe_stabilized", True)
        # Both views keep the same fresh-sample filter history for a fair switch.
        self._painted = None
        self._paint()

    def _telemetry(self):
        reader = getattr(self, "_latest_diagnostics", None)
        try:
            result = reader() if reader is not None else {}
            return result if isinstance(result, dict) else {}
        except Exception:
            logging.exception("No se pudo leer el diagnóstico ocular")
            return {}

    def diagnostic_report(self, *, include_samples=False):
        collector = self.collector
        key = (id(collector.calibration), collector.phase, len(collector.validation_samples),
               len(collector.capture_points), collector.message,
               getattr(self, "_acquisition_background", "neutral"))
        if not include_samples and key == getattr(self, "_report_cache_key", None):
            return self._report_cache
        report = build_diagnostic_report(
            collector.calibration, collector.validation_samples,
            capture_points=collector.capture_points,
            context={"monitor": {"width": self.monitor.width, "height": self.monitor.height,
                                 "left": self.monitor.left, "top": self.monitor.top},
                     "background": getattr(self, "_acquisition_background", "neutral"),
                     "phase": collector.phase, "telemetry": self._telemetry(),
                     "pointer_filter": {
                         "id": "ocular-one-euro-v1", "scope": "output_only",
                         "min_cutoff": GazePointerFilter.MIN_CUTOFF,
                         "beta": GazePointerFilter.BETA,
                         "derivative_cutoff": GazePointerFilter.DERIVATIVE_CUTOFF,
                         "reset_gap_seconds": GazePointerFilter.RESET_GAP_SECONDS,
                         "jump_distance": GazePointerFilter.JUMP_DISTANCE,
                     }},
            include_samples=include_samples)
        if not include_samples:
            self._report_cache, self._report_cache_key = report, key
        return report

    def export_diagnostics(self):
        """Only an explicit user action may persist local numeric eye samples."""
        writer = getattr(self, "_on_export_diagnostics", None)
        if self._closed or self.collector.running or writer is None or self.collector.calibration is None:
            return
        try:
            path = writer(self.diagnostic_report(include_samples=True))
            self._diagnostic_status = f"Guardado localmente: {path}. Solo datos numéricos; sin imágenes ni envío."
        except Exception:
            logging.exception("No se pudo exportar el diagnóstico ocular")
            self._diagnostic_status = "No se pudo guardar el informe. Revisa la carpeta de registros."
        self._painted = None
        self._paint()

    def _read_live(self):
        try:
            value = self._latest_observation()
        except Exception:
            logging.exception("No se pudo leer la observación ocular")
            value = None
        self._live_observation = value
        stamp = getattr(value, "timestamp", None)
        if not hasattr(self, "_live_stamps"):
            self._live_stamps = deque(maxlen=240)
        if (self.collector._valid_time(stamp)
                and 0 <= self._clock() - stamp <= self.collector.MAX_SAMPLE_AGE
                and (not self._live_stamps or stamp > self._live_stamps[-1])):
            self._live_stamps.append(stamp)
        return value

    def _live_text(self):
        value = getattr(self, "_live_observation", None)
        now = self._clock()
        stamp = getattr(value, "timestamp", None)
        age = f"{max(0, now - stamp) * 1000:.0f} ms" if self.collector._valid_time(stamp) else "sin muestra"
        stamps = [s for s in getattr(self, "_live_stamps", ()) if 0 <= now - s <= 2]
        fps = ((len(stamps) - 1) / (stamps[-1] - stamps[0])
               if len(stamps) > 1 and now - stamps[-1] <= .5 else 0)
        valid = self.collector._usable(value, now)
        reason = ("válida" if valid else str(getattr(value, "reason", "") or "sin muestra fresca"))
        first = f"Muestra: {age} · Observaciones nuevas: {fps:.1f}/s · {reason[:100]}"
        features = getattr(value, "features", ())
        if (isinstance(features, (tuple, list)) and len(features) == FEATURE_COUNT
                and all(self.collector._valid_time(v) for v in features)):
            return first + (f"\nIris A ({features[0]:+.3f}, {features[1]:+.3f}) · "
                            f"Iris B ({features[2]:+.3f}, {features[3]:+.3f})\n"
                            f"Postura ({features[4]:+.3f}, {features[5]:+.3f}) · "
                            f"Escala {features[6]:.3f} · Giro {features[7]:+.3f}")
        return first

    def _enable_preview(self, enabled):
        callback = getattr(self, "_set_preview_enabled", None)
        if enabled == getattr(self, "_preview_enabled", False):
            return
        self._preview_enabled = enabled
        if callback is not None:
            try:
                callback(enabled)
            except Exception:
                # Optional preview cannot prevent cancel, pause, or shutdown.
                logging.exception("No se pudo cambiar la vista previa ocular")

    @property
    def palette(self):
        return WIZARD_PALETTES[getattr(self, "_palette_name", "neutral")]

    def toggle_background(self):
        """Illumination must not change midway through a calibration mapping."""
        if self._closed or self.collector.running or getattr(self, "_probe", False):
            return
        self._palette_name = "dark" if self._palette_name == "neutral" else "neutral"
        # A point-only retry would mix illumination conditions between targets.
        # Changing the background explicitly requires a fresh calibration.
        self.collector._retry_point = None
        self._painted = None
        self._paint()

    def _tick(self):
        self._after = None
        if self._closed:
            return
        if self.collector.running:
            focused = self.window.focus_displayof()
            if focused is None or focused.winfo_toplevel() is not self.window:
                self.collector.interrupt("Vuelve a esta ventana para continuar con el mismo punto.")
            elif ((self.window.winfo_rootx(), self.window.winfo_rooty(),
                   self.window.winfo_width(), self.window.winfo_height())
                  != (self.monitor.left, self.monitor.top, self.monitor.width, self.monitor.height)):
                self.collector.fail("La pantalla o la ventana cambió. Cierra y vuelve a calibrar.")
            else:
                observation = self._read_live()
                self.collector.update(observation, self._clock())
        elif getattr(self, "_probe", False) or getattr(self, "_detail", False):
            self._read_live()
        self._paint()
        if getattr(self, "_probe", False):
            self._paint_probe_marker()
        elif getattr(self, "_detail", False):
            self._paint_live_details()
        if (not self.collector.running and self.collector.phase != "complete"
                and not self._results_visible() and not getattr(self, "_detail", False)
                and not getattr(self, "_probe", False)):
            self._paint_preview()
        if self.collector.phase == "complete" and not self._delivered:
            self._delivered = True
            try:
                self._on_success(self.collector.calibration)
            finally:
                self.destroy()
            return
        self._after = self.window.after(self.POLL_MS, self._tick)

    def _paint(self):
        collector = self.collector
        detail, probe = getattr(self, "_detail", False), getattr(self, "_probe", False)
        state = (collector.phase, collector.point_index, collector.message,
                 getattr(self, "_palette_name", "neutral"), detail, probe,
                 getattr(self, "_probe_stabilized", True),
                 getattr(self, "_diagnostic_status", ""))
        if state == self._painted:
            return
        self._painted = state
        canvas = self.canvas
        canvas.delete("all")
        self._preview_stamp = None
        palette = self.palette
        self._enable_preview(not collector.running and collector.phase != "complete"
                             and not (detail or probe or self._results_visible()))
        canvas.configure(background=palette["background"])
        self.window.configure(background=palette["background"])
        if hasattr(self, "_buttons"):
            self._buttons.configure(background=palette["background"])
            if collector.running:
                self._buttons.place_forget()
            else:
                self._buttons.place(relx=1.0, rely=1.0, x=-14, y=-10, anchor="se")
        if hasattr(self, "_diagnostic_buttons"):
            self._diagnostic_buttons.configure(background=palette["background"])
            self.detail_button.configure(text="Volver · D" if detail else "Detalle · D",
                                         state="disabled" if probe else "normal")
            self.probe_button.configure(text="Volver al resultado · P" if probe else "Probar sin controlar PC · P",
                                        state="normal" if (not collector.running and
                                                           getattr(collector.calibration, "fitted", False)) else "disabled")
            self.export_button.configure(state="normal" if (not collector.running and collector.calibration is not None
                                                            and self._on_export_diagnostics is not None) else "disabled")
            if hasattr(self, "filter_button"):
                if probe:
                    self.filter_button.configure(text=("Estabilizado · F" if getattr(self, "_probe_stabilized", True)
                                                       else "Original · F"))
                    self.filter_button.pack(side="left", padx=7)
                else:
                    self.filter_button.pack_forget()
            if collector.running:
                self._diagnostic_buttons.place_forget()
            else:
                self._diagnostic_buttons.place(relx=1.0, rely=1.0, x=-14, y=-43, anchor="se")
        width, height = self.monitor.width, self.monitor.height
        self.start_button.configure(state="disabled" if collector.running or probe else "normal",
                                    text=("Iniciar" if collector.phase == "idle" else
                                          "Repetir punto" if collector.can_retry_point else "Reintentar todo"))
        if hasattr(self, "background_button"):
            self.background_button.configure(
                state="disabled" if collector.running or probe else "normal",
                text="Fondo: gris mate" if getattr(self, "_palette_name", "neutral") == "neutral" else "Fondo: oscuro")
        if probe:
            self._paint_probe()
        elif collector.running:
            label = "Calibración" if collector.phase == "calibration" else "Comprobación"
            # Peripheral targets may sit at 5% of the screen. Instructions and
            # controls must not cover them, including on compact monitors.
            # Keep a single status line on the opposite vertical edge.
            status_y = height - 18 if collector.target[1] <= .5 else 18
            canvas.create_text(width / 2, status_y,
                               text=f"⚓  {label} · {collector.point_index + 1} de {len(collector.targets)} · Esc: cancelar",
                               fill=palette["text"], font=("Segoe UI", -13), width=width - 36)
            x, y = collector.target
            x, y = x * (width - 1), y * (height - 1)
            canvas.create_oval(x - 17, y - 17, x + 17, y + 17, outline=palette["accent"], width=2)
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=palette["text"], outline="")
            message_y = height - 43 if collector.target[1] <= .5 else 43
            canvas.create_text(width / 2, message_y, text=collector.message,
                               fill=palette["muted"], font=("Segoe UI", -12), width=width - 36)
            if detail:
                self._paint_live_details()
        elif detail:
            self._paint_technical()
        elif self._results_visible():
            self._paint_results()
        else:
            canvas.create_text(width / 2, 42, text="⚓  Calibrar mirada", fill=palette["accent"],
                               font=("Segoe UI", -26))
            instructions = (
                "1. Siéntate cómodo, con la cámara quieta y tus lentes habituales.\n"
                "2. Mantén la cabeza relativamente estable; no sigas el punto con la cabeza.\n"
                "3. Mueve SOLO LA MIRADA al centro del objetivo y espera a que cambie.\n"
                "4. Parpadea normalmente. No necesitas mostrar ni mover las manos.\n"
                "5. No sigas los dibujos de los ojos: solo sirven para comprobar su visibilidad.\n\n"
                f"Habrá {len(collector.training_targets)} puntos y luego {len(collector.validation_targets)} "
                "de comprobación. El cursor permanecerá en pausa.\n"
                "Usa luz suave frontal. Si el monitor se refleja en tus lentes, prueba Fondo: oscuro."
            )
            text = instructions if collector.phase == "idle" else collector.message
            canvas.create_text(width / 2, 92, text=text,
                               fill=palette["text"], font=("Segoe UI", -14), justify="left", anchor="n",
                               width=max(150, min(1000, width - 70)))
            if getattr(self, "_latest_preview", None) is not None:
                preview_y = self._preview_y()
                canvas.create_text(width / 2, preview_y - 22,
                                   text="Vista ampliada: comprueba ambos ojos y los reflejos. Ampliar no mejora la detección.",
                                   fill=palette["muted"], font=("Segoe UI", -12), width=width - 60)
            if collector.phase == "error":
                canvas.create_text(width / 2, height - 85,
                                   text="La comprobación no habilita el control si la precisión es insuficiente.",
                                   fill=palette["muted"], font=("Segoe UI", -12), width=width - 60)
        if not collector.running:
            status = getattr(self, "_diagnostic_status", "")
            if status:
                canvas.create_text(20, height - 120, text=status, anchor="nw", width=width - 40,
                                   fill=palette["text"], font=("Segoe UI", -12), tags="export_status")

    def _results_visible(self):
        return (self.collector.phase == "error" and bool(self.collector.validation_samples)
                and getattr(self.collector.calibration, "fitted", False))

    def _paint_results(self):
        canvas, palette = self.canvas, self.palette
        width, height = self.monitor.width, self.monitor.height
        report = self.diagnostic_report()
        measured = self.collector.calibration.report
        canvas.create_text(width / 2, 30, text="⚓  Resultado de la comprobación · control bloqueado",
                           fill=palette["accent"], font=("Segoe UI", -20))
        def percent(value):
            return f"{value:.1%}" if self.collector._valid_time(value) else "no disponible"
        rejected = report.get("summary", {}).get("validation", {}).get("rejected", 0)
        limits = report["limits"]
        canvas.create_text(24, 65, text=(f"Error medio {percent(measured.mean_error)} · máximo {percent(measured.max_error)}. "
                                       f"Límites: {percent(limits['mean_error'])} / {percent(limits['max_error'])}. "
                                       f"Muestras sin predicción: {rejected}."),
                           fill=palette["text"], anchor="nw", width=width - 48, font=("Segoe UI", -13))
        reason = str(measured.reason or self.collector.message).replace("\n", " ")
        canvas.create_text(24, 105, text=f"Motivo: {reason[:180]}{'…' if len(reason) > 180 else ''}",
                           fill=palette["muted"], anchor="nw", width=width - 48, font=("Segoe UI", -12))
        canvas.create_text(24, 144, text="○ Objetivo   × Mirada media estimada   — Desviación (distancia normalizada, no aciertos)",
                           fill=palette["muted"], anchor="nw", width=width - 48, font=("Segoe UI", -12))
        map_width = min(width * .55, (height - 355) * width / height)
        map_height = map_width * height / width
        left, top = 28, 174
        canvas.create_rectangle(left, top, left + map_width, top + map_height,
                                outline=palette["muted"], tags="diagnostic_map")
        rows = report.get("validation", [])
        for number, row in enumerate(rows, 1):
            target, predicted = row["target"], row.get("predicted_mean")
            x, y = left + target[0] * map_width, top + target[1] * map_height
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                               outline=palette["accent"], width=2, tags="diagnostic_map")
            canvas.create_text(x, y - 13, text=str(number), fill=palette["text"],
                               font=("Segoe UI", -11), tags="diagnostic_map")
            if predicted is not None:
                px, py = left + predicted[0] * map_width, top + predicted[1] * map_height
                canvas.create_line(x, y, px, py, fill=palette["accent"], tags="diagnostic_map")
                canvas.create_line(px - 5, py - 5, px + 5, py + 5, fill=palette["text"], width=2, tags="diagnostic_map")
                canvas.create_line(px - 5, py + 5, px + 5, py - 5, fill=palette["text"], width=2, tags="diagnostic_map")
        table_left = left + map_width + 30
        lines = ["Punto   Media / Máximo   Muestras"]
        for number, row in enumerate(rows, 1):
            mean, maximum = row.get("mean_error"), row.get("max_error")
            errors = f"{mean:.1%} / {maximum:.1%}" if mean is not None and maximum is not None else "sin predicción"
            lines.append(f"{number}         {errors}         {row['n']}")
        canvas.create_text(table_left, top, text="\n".join(lines), anchor="nw", justify="left",
                           width=max(160, width - table_left - 20), fill=palette["text"], font=("Segoe UI", -12))
        canvas.create_text(24, top + map_height + 20,
                           text=("D: inspeccionar iris, postura y adquisición. P: visualizar el modelo sin controlar la PC.\n"
                                 "E: guardar informe local con datos numéricos de esta prueba, sin fotos ni video.\n"
                                 "Las pruebas sintéticas no demuestran precisión real: este mapa permite investigarla."),
                           anchor="nw", width=width - 48, fill=palette["muted"], font=("Segoe UI", -12))

    def _paint_technical(self):
        canvas, palette = self.canvas, self.palette
        width = self.monitor.width
        precision = getattr(self.collector.calibration or self.collector._factory, "engine_id", None) in PRECISION_ENGINE_IDS
        engine_label = "Precisión local" if precision else "Iris clásico"
        canvas.create_text(24, 24, text=f"⚓  Diagnóstico · {engine_label} · D para volver",
                           fill=palette["accent"], font=("Segoe UI", -21), anchor="nw")
        canvas.create_text(24, 65, text="Sin control de la PC. Los números describen la detección; no certifican que el iris sea correcto.",
                           fill=palette["muted"], font=("Segoe UI", -12), anchor="nw", width=width - 48)
        lines = []
        for point in self.collector.capture_points:
            name = "C" if point["phase"] == "calibration" else "V"
            drops = sum(point["rejected"].values())
            lines.append(f"{name}{point['point_index']}: {point['samples']}m "
                         f"{point['useful_seconds']:.1f}/{point['elapsed_seconds']:.1f}s "
                         f"r{drops} i{point['attempts']}")
        canvas.create_text(24, 222, text="C: calibración · V: validación · m: muestras · segundos útiles/totales · r: rechazos · i: intentos",
                           anchor="nw", width=width - 48, fill=palette["muted"], font=("Segoe UI", -11))
        # The compact ledger remains readable even on a 800 x 600 monitor.
        columns = 3 if len(lines) > 14 else 2
        chunk_size = max(1, math.ceil(len(lines) / columns))
        for column in range(columns):
            entries = lines[column * chunk_size:(column + 1) * chunk_size]
            canvas.create_text(24 + column * width / columns, 243, text="\n".join(entries) or "Sin puntos recogidos todavía.",
                               anchor="nw", width=width / columns - 42, fill=palette["text"],
                               font=("Segoe UI", -11), tags="capture_ledger")
        if self.collector.calibration is not None:
            report = self.diagnostic_report()
            summary = report.get("summary", {})
            def metric(phase, key):
                value = summary.get(phase, {}).get(key)
                return f"{value:.1%}" if self.collector._valid_time(value) else "—"
            canvas.create_text(24, 385,
                               text=(f"Aprendizaje: error {metric('training', 'mean_error')} · "
                                     f"Comprobación: error {metric('validation', 'mean_error')} · "
                                     f"variación {metric('validation', 'jitter')}\n"
                                     "Un error bajo durante aprendizaje no demuestra precisión en puntos nuevos."),
                               anchor="nw", width=width - 48, fill=palette["text"], font=("Segoe UI", -12))
            hypotheses = report.get("hypotheses", [])
            # Core supplies cautious diagnostic hints, never an automatic verdict.
            hints = [str(h.get("message", h)) if isinstance(h, dict) else str(h) for h in hypotheses]
            if hints:
                canvas.create_text(24, 422, text="\n".join(hints[:2]), anchor="nw",
                                   width=width - 48, fill=palette["muted"], font=("Segoe UI", -12))
        self._paint_live_details()

    def _paint_live_details(self):
        self.canvas.delete("live_diagnostics")
        width, height = self.monitor.width, self.monitor.height
        if self.collector.running:
            text = self._live_text().split("\n")[0] + " · D: ocultar detalle"
            diagnostic_y = height - 75 if self.collector.target[1] <= .5 else 65
            self.canvas.create_text(18, diagnostic_y, text=text, fill=self.palette["muted"],
                                    font=("Segoe UI", -11), anchor="nw", width=width - 36, tags="live_diagnostics")
        else:
            self.canvas.create_text(24, 105, text=self._live_text(), fill=self.palette["text"],
                                    font=("Segoe UI", -13), anchor="nw", width=width - 48, tags="live_diagnostics")
            observation = getattr(self, "_live_observation", None)
            extra = getattr(observation, "auxiliary_features", ())
            if (getattr(observation, "feature_schema", None) == PRECISION_OBSERVATION_SCHEMA
                    and isinstance(extra, (tuple, list)) and len(extra) == 6
                    and all(self.collector._valid_time(v) for v in extra)):
                auxiliary = (f"Mirada unitaria XYZ: ({extra[0]:+.3f}, {extra[1]:+.3f}, {extra[2]:+.3f})\n"
                             f"Cabeza yaw/pitch/roll: ({extra[3]:+.3f}, {extra[4]:+.3f}, {extra[5]:+.3f}) rad")
                self.canvas.create_text(24, 155, text=auxiliary, fill=self.palette["text"],
                                        font=("Segoe UI", -12), anchor="nw", width=width - 48, tags="live_diagnostics")
            worker = self._telemetry().get("worker", {})
            if isinstance(worker, dict):
                def number(key, suffix=""):
                    value = worker.get(key)
                    return f"{value:.1f}{suffix}" if self.collector._valid_time(value) else "—"
                def pair(key):
                    values = worker.get(key)
                    if isinstance(values, (list, tuple)) and len(values) == 2:
                        return "/".join(f"{v:.2f}" if self.collector._valid_time(v) else "—" for v in values)
                    return "—"
                text = (f"Detector: {number('face_fps', '/s')} · cálculo {number('inference_ms', ' ms')} · "
                        f"ocular {number('neural_ms', ' ms')} · captura→resultado {number('capture_to_result_ms', ' ms')}\n"
                        f"Ojos: {pair('eye_width_px')} px · apertura/anchura: {pair('eye_opening_ratio')}")
                self.canvas.create_text(24, 188, text=text, fill=self.palette["muted"],
                                        font=("Segoe UI", -12), anchor="nw", width=width - 48, tags="live_diagnostics")

    def _paint_probe(self):
        width, height = self.monitor.width, self.monitor.height
        self.canvas.create_text(width / 2, 28, text="⚓  Prueba aislada · NO controla la PC",
                                fill=self.palette["accent"], font=("Segoe UI", -21))
        mode = "ESTABILIZADO: mismo filtro que el cursor ocular" if getattr(self, "_probe_stabilized", True) else "ORIGINAL: sin suavizado temporal"
        self.canvas.create_text(20, 62, text=f"{mode}. F: alternar. P o Esc: volver. La cruz no mueve el cursor real.",
                                fill=self.palette["text"], font=("Segoe UI", -13), anchor="nw", width=width - 40)
        self.canvas.create_text(20, height - 152, text="Una prueba fallida sigue bloqueada. Este visor no aprueba ni modifica la calibración.",
                                fill=self.palette["muted"], font=("Segoe UI", -12), anchor="nw", width=width - 40)

    def _paint_probe_marker(self):
        self.canvas.delete("probe_marker")
        value = getattr(self, "_live_observation", None)
        width, height = self.monitor.width, self.monitor.height
        prediction = {"raw": None, "bounded": None, "reason": "Sin una muestra fresca y válida"}
        if self.collector._usable(value, self._clock()):
            prediction = diagnostic_prediction(self.collector.calibration, value)
        bounded = prediction.get("bounded")
        if bounded is not None:
            if not hasattr(self, "_probe_filter"):
                self._probe_filter = GazePointerFilter()
            stabilized = self._probe_filter(*bounded, value.timestamp)
            displayed = stabilized if getattr(self, "_probe_stabilized", True) else bounded
            # Same normalized screen coordinates as the real mapping, with no
            # preview-specific transform that could hide a directional error.
            x, y = displayed[0] * (width - 1), displayed[1] * (height - 1)
            self.canvas.create_line(x - 10, y, x + 10, y, fill=self.palette["accent"], width=3, tags="probe_marker")
            self.canvas.create_line(x, y - 10, x, y + 10, fill=self.palette["accent"], width=3, tags="probe_marker")
            raw = prediction["raw"]
            status = f"Estimación sin recorte: ({raw[0]:+.3f}, {raw[1]:+.3f}) · "
            status += "Fuera de pantalla" if any(v < 0 or v > 1 for v in raw) else "Dentro de pantalla"
            status += f" · Estabilizada: ({stabilized[0]:+.3f}, {stabilized[1]:+.3f})"
        else:
            self._reset_probe_filter()
            status = str(prediction.get("reason") or "Sin predicción válida")
            raw = prediction.get("raw")
            if raw is not None:
                status = f"Estimación sin recorte: ({raw[0]:+.3f}, {raw[1]:+.3f}) · {status}"
        self.canvas.create_text(20, 88, text=status, anchor="nw", width=width - 40,
                                fill=self.palette["muted"], font=("Segoe UI", -12), tags="probe_marker")

    def _preview_y(self):
        return min(self.monitor.height - 200, max(325, self.monitor.height * .62))

    def _paint_preview(self):
        """Optional, ephemeral eye-only crop. Never show it beside a target."""
        reader = getattr(self, "_latest_preview", None)
        if (reader is None or self.collector.running or self._results_visible()
                or getattr(self, "_detail", False) or getattr(self, "_probe", False)):
            return
        try:
            preview = reader()
            stamp = getattr(preview, "timestamp", None)
            fresh = (self.collector._valid_time(stamp)
                     and 0 <= self._clock() - stamp <= self.PREVIEW_MAX_AGE)
            if not fresh:
                self.canvas.delete("eye_preview")
                self._preview_image = self._preview_stamp = None
                self.canvas.create_text(self.monitor.width / 2, self._preview_y() + 40,
                                        text="Esperando una imagen nueva de ambos ojos…",
                                        fill=self.palette["muted"], font=("Segoe UI", -13), tags="eye_preview")
                return
            if stamp == self._preview_stamp:
                return
            from PIL import Image, ImageDraw, ImageTk

            frame = Image.fromarray(preview.rgb).convert("RGB")
            if frame.width <= 0 or frame.height <= 0:
                raise ValueError("Recorte ocular vacío")
            factor = min(300 / frame.width, 95 / frame.height)
            size = max(1, round(frame.width * factor)), max(1, round(frame.height * factor))
            frame = frame.resize(size, Image.Resampling.BILINEAR)
            draw = ImageDraw.Draw(frame)
            for point in getattr(preview, "points", ()):
                if len(point) == 2 and all(math.isfinite(value) and 0 <= value <= 1 for value in point):
                    x, y = point[0] * (frame.width - 1), point[1] * (frame.height - 1)
                    draw.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill="#79d8dc")
            self._preview_image = ImageTk.PhotoImage(frame, master=self.window)
            self._preview_stamp = stamp
            self.canvas.delete("eye_preview")
            self.canvas.create_image(self.monitor.width / 2, self._preview_y(), image=self._preview_image,
                                     anchor="n", tags="eye_preview")
        except Exception:
            logging.exception("No se pudo mostrar la vista previa ocular")
            self.canvas.delete("eye_preview")
            self._preview_image = self._preview_stamp = None

    def _window_destroyed(self, event):
        if event.widget is self.window:
            self.destroy()

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        self._enable_preview(False)
        self._preview_image = self._preview_stamp = None
        self._live_observation = None
        self._live_stamps = deque(maxlen=240)
        self._report_cache = self._report_cache_key = None
        try:
            if self._after is not None:
                self.window.after_cancel(self._after)
                self._after = None
            if self.window.winfo_exists():
                if self.window.grab_current() is self.window:
                    self.window.grab_release()
                self.window.destroy()
        except tk.TclError:
            pass
        finally:
            self._on_close()
