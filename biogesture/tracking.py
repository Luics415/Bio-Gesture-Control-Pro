"""Bounded, latest-frame camera tracking. Importing this module opens no device."""

from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import time

from .models import HandSample, Landmark, TrackingPacket
from .selection import PrincipalHandSelector
from .settings import Settings


@dataclass(frozen=True)
class _Frame:
    timestamp: float
    rgb: object
    generation: int


class TrackingPipeline:
    """One capture slot, one inference in flight, and one immutable result snapshot.

    Callbacks run on worker threads; consumers must marshal UI work themselves.
    stop() reports False if a native camera/model call does not return in time.
    Such a pipeline cannot be restarted until its workers have actually exited.
    """

    def __init__(self, settings: Settings, model_path: Path, status_callback=None):
        self.settings = settings
        self.model_path = Path(model_path)
        self.status_callback = status_callback
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._worker = None
        self._capture_worker = None
        self._capture = None
        self._packet = None
        self._pending = None
        self._inflight = None
        self._generation = 0
        self._sequence = 0
        self._timestamp_ms = 0
        self._selector = PrincipalHandSelector(settings.tracking_confidence)
        self._metrics = {"capture_fps": 0.0, "inference_ms": 0.0,
                         "dropped_frames": 0.0, "captured_frames": 0.0,
                         "processed_frames": 0.0, "reconnections": 0.0}

    @property
    def running(self):
        return any(t is not None and t.is_alive()
                   for t in (self._worker, self._capture_worker))

    def start(self):
        if self.running:
            raise RuntimeError("El seguimiento anterior todavía está activo")
        self.settings.validate()
        with self._condition:
            self._stop.clear()
            self._pending = self._inflight = None
            self._generation += 1
            self._selector.reset()
        self._worker = threading.Thread(target=self._run, name="BioGesture-tracking", daemon=True)
        self._worker.start()

    def latest(self):
        with self._condition:
            return self._packet

    def reset_roles(self):
        """User-requested new principal; discard callbacks already in flight."""
        with self._condition:
            self._generation += 1
            self._pending = None
            self._selector.reset()
            self._packet = None

    def stop(self, timeout=2):
        self._stop.set()
        with self._condition:
            self._pending = None
            self._generation += 1
            self._condition.notify_all()
        deadline = time.monotonic() + max(0.0, timeout)
        for worker in (self._worker, self._capture_worker):
            if worker and worker is not threading.current_thread():
                worker.join(max(0.0, deadline - time.monotonic()))
        stopped = not self.running
        self._publish_status("DETENIDO" if stopped else "CERRANDO CÁMARA",
                             None if stopped else "El controlador de cámara está tardando en cerrar")
        return stopped

    def _publish_status(self, status, error=None):
        with self._condition:
            self._sequence += 1
            now = time.monotonic()
            self._packet = TrackingPacket(self._sequence, now, now, status=status,
                                          error=error, metrics=dict(self._metrics))
        if self.status_callback:
            try:
                self.status_callback(status)
            except Exception:
                logging.exception("Falló el aviso de estado del seguimiento")

    def _make_detector(self):
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Falta el modelo de manos: {self.model_path.name}")
        import mediapipe as mp
        self._mp = mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            # Python handles Unicode Windows paths; native model path loading
            # may not. Pass the original bytes without changing the asset.
            base_options=mp.tasks.BaseOptions(model_asset_buffer=self.model_path.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
            # Both hands share one inference; the session selector assigns roles.
            num_hands=2,
            min_hand_detection_confidence=self.settings.detection_confidence,
            min_hand_presence_confidence=self.settings.detection_confidence,
            min_tracking_confidence=self.settings.tracking_confidence,
            result_callback=self._on_result,
        )
        return mp.tasks.vision.HandLandmarker.create_from_options(options)

    def _image(self, rgb):
        return self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

    def _run(self):
        detector = None
        try:
            self._publish_status("PREPARANDO DETECCIÓN")
            detector = self._make_detector()
            if self._stop.is_set():
                return
            self._capture_worker = threading.Thread(target=self._capture_loop,
                                                     name="BioGesture-camera", daemon=True)
            self._capture_worker.start()
            next_due = 0.0
            while not self._stop.is_set():
                with self._condition:
                    now = time.monotonic()
                    if self._inflight and now - self._inflight[2] > 5.0:
                        raise TimeoutError("La detección no respondió; reinicia la cámara")
                    if self._pending is None or self._inflight or now < next_due:
                        self._condition.wait(timeout=min(0.05, max(0.001, next_due - now))
                                             if now < next_due else 0.05)
                        continue
                    frame = self._pending
                    self._pending = None
                    self._timestamp_ms = max(self._timestamp_ms + 1, int(frame.timestamp * 1000))
                    timestamp_ms = self._timestamp_ms
                    self._inflight = (timestamp_ms, frame, now)
                detector.detect_async(self._image(frame.rgb), timestamp_ms)
                next_due = now + 1 / self.settings.detection_fps
        except Exception as exc:
            logging.exception("Falló el seguimiento")
            self._publish_status("ERROR DE DETECCIÓN", str(exc))
        finally:
            self._stop.set()
            with self._condition:
                self._pending = None
                self._generation += 1
                self._condition.notify_all()
            if self._capture_worker:
                self._capture_worker.join(timeout=2.0)
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    logging.exception("No se pudo cerrar el detector")
            with self._condition:
                self._inflight = None

    def _offer_frame(self, rgb, timestamp):
        """Replace unsent frames instead of queuing latency behind inference."""
        with self._condition:
            if self._pending is not None:
                self._metrics["dropped_frames"] += 1
            self._metrics["captured_frames"] += 1
            self._pending = _Frame(timestamp, rgb, self._generation)
            self._condition.notify_all()

    def _invalidate_camera(self, error):
        with self._condition:
            self._generation += 1
            self._pending = None
            self._selector.suspend()
            self._metrics["capture_fps"] = 0.0
        self._publish_status("RECONECTANDO CÁMARA", error)

    def _on_result(self, result, output_image, timestamp_ms):
        del output_image
        try:
            with self._condition:
                context = self._inflight
                if context is None or timestamp_ms != context[0]:
                    return
                _, frame, submitted_at = context
                self._inflight = None
                self._condition.notify_all()
                if self._stop.is_set() or frame.generation != self._generation:
                    return
                now = time.monotonic()
                rgb = frame.rgb
                height, width = rgb.shape[:2]
                samples = []
                for index, hand_landmarks in enumerate(result.hand_landmarks):
                    categories = result.handedness[index] if index < len(result.handedness) else []
                    category = categories[0] if categories else None
                    # MediaPipe's selfie convention: inference always receives a
                    # mirrored image. Display/coordinates may then be unmirrored.
                    landmarks = tuple(Landmark(p.x if self.settings.mirror else 1 - p.x,
                                               p.y, p.z) for p in hand_landmarks)
                    samples.append(HandSample(frame.timestamp, landmarks, width, height,
                                              category.category_name if category else "Unknown",
                                              category.score if category else 0.0))
                selection = self._selector.update(samples, frame.timestamp)
                if not self.settings.mirror:
                    rgb = rgb[:, ::-1].copy()
                self._metrics["inference_ms"] = (now - submitted_at) * 1000
                self._metrics["latency_ms"] = (now - frame.timestamp) * 1000
                self._metrics["processed_frames"] += 1
                self._metrics["detected_hands"] = float(selection.hand_count)
                self._metrics["principal_selected"] = float(self._selector.selected)
                self._sequence += 1
                self._packet = TrackingPacket(self._sequence, frame.timestamp, now, rgb, selection.sample,
                                              selection.status, metrics=dict(self._metrics), auxiliary=selection.auxiliary)
        except Exception as exc:
            logging.exception("Falló la lectura de landmarks")
            self._publish_status("ERROR DE DETECCIÓN", str(exc))

    def _open_capture(self, cv2):
        errors = []
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            if self._stop.is_set():
                break
            cap = cv2.VideoCapture(self.settings.camera_index, backend)
            self._capture = cap
            try:
                if not cap.isOpened():
                    raise OSError("La cámara no está disponible o está ocupada")
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.capture_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.capture_height)
                cap.set(cv2.CAP_PROP_FPS, self.settings.capture_fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise OSError("La cámara se abrió pero no entregó imagen")
                height, width = frame.shape[:2]
                with self._condition:
                    self._metrics.update(negotiated_width=float(width), negotiated_height=float(height),
                                         negotiated_fps=float(cap.get(cv2.CAP_PROP_FPS)),
                                         camera_backend=float(backend))
                logging.info("Cámara negociada: %sx%s, %.1f FPS, backend %s", width, height,
                             cap.get(cv2.CAP_PROP_FPS), backend)
                return cap, frame
            except Exception as exc:
                errors.append(str(exc))
                cap.release()
                self._capture = None
        raise OSError("; ".join(errors) or "Cámara detenida")

    def _capture_loop(self):
        cap = None
        try:
            import cv2
            delay = 0.5
            while not self._stop.is_set():
                try:
                    self._publish_status("CONECTANDO CÁMARA")
                    cap, frame = self._open_capture(cv2)
                    delay = 0.5
                    count, interval_start = 0, time.monotonic()
                    while not self._stop.is_set():
                        started = time.monotonic()
                        # Infer at negotiated aspect ratio; never resize to UI dimensions.
                        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                        self._offer_frame(rgb, started)
                        count += 1
                        elapsed = started - interval_start
                        if elapsed >= 1.0:
                            with self._condition:
                                self._metrics["capture_fps"] = count / elapsed
                            count, interval_start = 0, started
                        if self._stop.wait(max(0.0, 1 / self.settings.capture_fps -
                                                (time.monotonic() - started))):
                            break
                        ok, frame = cap.read()
                        if not ok or frame is None:
                            raise OSError("Se perdió la imagen de la cámara")
                except Exception as exc:
                    if not self._stop.is_set():
                        logging.warning("Cámara: %s", exc)
                        self._invalidate_camera(str(exc))
                finally:
                    if cap is not None:
                        cap.release()
                        cap = None
                        self._capture = None
                if not self._stop.is_set():
                    with self._condition:
                        self._metrics["reconnections"] += 1
                    self._stop.wait(delay)
                    delay = min(5.0, delay * 2)
        except Exception as exc:
            logging.exception("No se pudo iniciar la captura")
            self._publish_status("ERROR DE CÁMARA", str(exc))
            self._stop.set()
        finally:
            if cap is not None:
                cap.release()
            self._capture = None
