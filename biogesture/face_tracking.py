"""Optional local face worker: one latest frame, no camera or desktop ownership.

Face landmarks are observations for a calibrated experimental estimator, never
screen gaze coordinates by themselves. Importing this module loads no model.
"""

from dataclasses import dataclass, replace
from collections import deque
import hashlib
import logging
import math
from pathlib import Path
import threading
import time


FACE_MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


def eye_geometry_metrics(landmarks, width, height):
    """Numeric observation diagnostics, not another detector or a quality score."""
    widths, openings = [], []
    try:
        if (isinstance(width, bool) or isinstance(height, bool)
                or not math.isfinite(width) or not math.isfinite(height) or min(width, height) <= 0):
            return {}
        for a, b, upper, lower in ((33, 133, 159, 145), (362, 263, 386, 374)):
            points = [(float(landmarks[i].x) * width, float(landmarks[i].y) * height)
                      for i in (a, b, upper, lower)]
            if not all(math.isfinite(v) for p in points for v in p):
                return {}
            dx, dy = points[1][0] - points[0][0], points[1][1] - points[0][1]
            span = math.hypot(dx, dy)
            if span <= 0:
                return {}
            opening = abs((points[3][0] - points[2][0]) * -dy
                          + (points[3][1] - points[2][1]) * dx) / (span * span)
            widths.append(round(span, 3))
            openings.append(round(opening, 5))
        return {"eye_width_px": tuple(widths), "eye_opening_ratio": tuple(openings)}
    except (TypeError, ValueError, AttributeError, IndexError, OverflowError):
        return {}


@dataclass(frozen=True)
class EyePreview:
    """Ephemeral eye-only preparation image; never written to a file."""
    rgb: object
    points: tuple[tuple[float, float], ...]
    timestamp: float


def make_eye_preview(rgb, landmarks, timestamp):
    """Small eye strip with both iris centers, for the calibration setup only."""
    try:
        import cv2
        import numpy as np
        if (not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8
                or min(rgb.shape[:2]) <= 0 or isinstance(timestamp, bool)):
            return None
        height, width = rgb.shape[:2]
        indices = (33, 159, 133, 145, 468, 362, 386, 263, 374, 473)
        points = [(float(landmarks[i].x) * width, float(landmarks[i].y) * height) for i in indices]
        if (not math.isfinite(timestamp) or not all(math.isfinite(v) for point in points for v in point)
                or any(not (0 <= x < width and 0 <= y < height) for x, y in points)):
            return None
        xs, ys = zip(*points)
        span = max(xs) - min(xs)
        if not 24 <= span <= width * .85:
            return None
        padding = max(4, span * .10)
        left, right = max(0, int(min(xs) - padding)), min(width, int(max(xs) + padding) + 1)
        top, bottom = max(0, int(min(ys) - padding)), min(height, int(max(ys) + padding) + 1)
        if bottom - top < 6:
            return None
        crop = rgb[top:bottom, left:right].copy()
        normalized = tuple(((x - left) / (right - left), (y - top) / (bottom - top)) for x, y in points)
        if crop.shape[1] > 480:
            crop = cv2.resize(crop, (480, max(1, round(crop.shape[0] * 480 / crop.shape[1]))))
        return EyePreview(crop, normalized, timestamp)
    except (AttributeError, IndexError, ValueError, TypeError, OverflowError, cv2.error):
        return None


def eye_focus_ok(rgb, landmarks, minimum_variance=12.0):
    """Conservative blur gate on eye crops, not a glasses/reflection classifier.

    The initial threshold is experimental and must be measured on real cameras.
    This rejects low-detail crops; plausible landmarks alone cannot do that.
    """
    import cv2
    import math
    height, width = rgb.shape[:2]
    for indices in ((33, 133, 159, 145), (362, 263, 386, 374)):
        coordinates = [(landmarks[i].x * width, landmarks[i].y * height) for i in indices]
        if not all(math.isfinite(v) for point in coordinates for v in point):
            return False
        xs, ys = zip(*coordinates)
        pad = max(2, (max(xs) - min(xs)) * .15)
        left, right = max(0, int(min(xs) - pad)), min(width, int(max(xs) + pad) + 1)
        top, bottom = max(0, int(min(ys) - pad)), min(height, int(max(ys) + pad) + 1)
        if right - left < 12 or bottom - top < 5:
            return False
        gray = cv2.cvtColor(rgb[top:bottom, left:right], cv2.COLOR_RGB2GRAY)
        if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < minimum_variance:
            return False
    return True


class FaceTrackingWorker:
    def __init__(self, settings, model_path: Path):
        self.settings = settings
        self.model_path = Path(model_path)
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread = None
        self._pending = self._latest = None
        self._generation = 0
        self._resting = False
        self._preview_enabled = False
        self._preview_generation = 0
        self._preview = None
        self.inference_ms = 0.0
        self._diagnostics = {}
        self._completed_times = deque(maxlen=60)
        self._neural = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            raise RuntimeError("El seguimiento ocular anterior sigue activo")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="BioGesture-eyes", daemon=True)
        self._thread.start()

    def offer(self, rgb, timestamp):
        with self._condition:
            self._pending = (rgb, timestamp, self._generation)
            self._condition.notify_all()

    def latest(self):
        with self._condition:
            return self._latest

    def latest_diagnostics(self):
        with self._condition:
            return dict(self._diagnostics)

    def set_preview_enabled(self, enabled):
        with self._condition:
            if bool(enabled) != self._preview_enabled:
                self._preview_generation += 1
                self._preview = None
            self._preview_enabled = bool(enabled)

    def latest_preview(self):
        with self._condition:
            return self._preview if self._preview_enabled else None

    def invalidate(self):
        with self._condition:
            self._generation += 1
            self._pending = self._latest = None
            self._preview = None
            self._diagnostics = {}
            self._completed_times.clear()

    def set_resting(self, resting):
        with self._condition:
            self._resting = bool(resting)
            self._condition.notify_all()

    def stop(self, timeout=2.0):
        self._stop.set()
        self.invalidate()
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(max(0.0, timeout))
        return not self.running

    def _make_detector(self):
        import mediapipe as mp
        self._mp = mp
        model = self.model_path.read_bytes()
        if hashlib.sha256(model).hexdigest() != FACE_MODEL_SHA256:
            raise ValueError("El modelo ocular no coincide con la versión verificada")
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=self.settings.detection_confidence,
            min_face_presence_confidence=self.settings.detection_confidence,
            min_tracking_confidence=self.settings.tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        return mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def _make_neural(self):
        if self.settings.gaze_engine not in ("precision-openvino-v1", "precision-openvino-v2"):
            return None
        from .gaze_neural import NeuralGazeExtractor
        return NeuralGazeExtractor(self.model_path.parent / "gaze-precision")

    def _run(self):
        from .gaze import GazeObservation, extract_gaze_observation
        detector = None
        try:
            detector = self._make_detector()
            # No CNN imports/loading on the Tk or hand detection threads.
            self._neural = self._make_neural()
            next_due, last_ms = 0.0, 0
            while not self._stop.is_set():
                with self._condition:
                    now = time.monotonic()
                    if self._pending is None or now < next_due:
                        self._condition.wait(timeout=min(.05, max(.001, next_due - now))
                                             if now < next_due else .05)
                        continue
                    rgb, captured_at, generation = self._pending
                    self._pending = None
                    frequency = min(5, self.settings.detection_fps) if self._resting else self.settings.detection_fps
                    preview_enabled = self._preview_enabled
                    preview_generation = self._preview_generation
                if now - captured_at > .35:
                    continue
                calculation_started = time.perf_counter()
                image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                last_ms = max(last_ms + 1, int(captured_at * 1000))
                result = detector.detect_for_video(image, last_ms)
                height, width = rgb.shape[:2]
                faces = result.face_landmarks
                observation = (extract_gaze_observation(faces[0], captured_at, width, height)
                               if len(faces) == 1 else GazeObservation(captured_at, reason="Ojos no visibles"))
                if observation.valid and not eye_focus_ok(rgb, faces[0]):
                    observation = GazeObservation(captured_at, reason="Ojos desenfocados o sin detalle suficiente")
                neural_ms = 0.0
                if observation.valid and self._neural is not None:
                    neural_started = time.perf_counter()
                    try:
                        values = self._neural.extract(rgb, faces[0])
                        observation = replace(observation, auxiliary_features=tuple(values),
                                              feature_schema="openvino-gaze6-v1")
                        from .gaze_precision import precision_observation_usable
                        if not precision_observation_usable(observation):
                            observation = GazeObservation(captured_at, reason="Dirección ocular no fiable")
                    except (ValueError, ArithmeticError) as exc:
                        observation = GazeObservation(captured_at, reason=f"Recorte ocular no válido: {exc}")
                    neural_ms = (time.perf_counter() - neural_started) * 1000
                preview = (make_eye_preview(rgb, faces[0], captured_at)
                           if preview_enabled and len(faces) == 1 else None)
                geometry = eye_geometry_metrics(faces[0], width, height) if len(faces) == 1 else {}
                completed = time.monotonic()
                with self._condition:
                    if generation == self._generation and not self._stop.is_set():
                        self._latest = observation
                        self.inference_ms = (time.perf_counter() - calculation_started) * 1000
                        self._completed_times.append(completed)
                        recent = [stamp for stamp in self._completed_times if completed - stamp <= 5.0]
                        fps = ((len(recent) - 1) / (recent[-1] - recent[0])
                               if len(recent) > 1 and recent[-1] > recent[0] else 0.0)
                        self._diagnostics = {
                            "timestamp": captured_at, "image_width": width, "image_height": height,
                            "inference_ms": self.inference_ms,
                            "capture_to_result_ms": max(0.0, (completed - captured_at) * 1000),
                            "face_fps": fps, "valid": observation.valid, "reason": observation.reason,
                            "returned_faces": len(faces), **geometry,
                            "gaze_engine": self.settings.gaze_engine, "neural_ms": neural_ms,
                            "neural_features": observation.auxiliary_features,
                        }
                        if self._preview_enabled and preview_generation == self._preview_generation:
                            self._preview = preview
                next_due = now + 1 / frequency
        except Exception as exc:
            logging.exception("Seguimiento ocular no disponible")
            with self._condition:
                self._preview = None
                self._diagnostics = {}
                self._completed_times.clear()
                self._latest = GazeObservation(time.monotonic(), reason=f"Ojos no disponibles: {exc}")
        finally:
            neural, self._neural = self._neural, None
            if neural is not None:
                try:
                    neural.close()
                except Exception:
                    logging.exception("No se pudo cerrar el motor de mirada")
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    logging.exception("No se pudo cerrar el detector ocular")
