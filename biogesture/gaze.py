"""Experimental, local gaze estimation and fail-closed session contracts.

MediaPipe face/iris landmarks are observations, NOT screen gaze coordinates.
The mapping below must be calibrated for this session and pass independent
validation before it can provide a pointer. It is deliberately bounded rather
than extrapolating through an unobserved posture, a blink, or missing frames.
No camera, biometric identification, desktop input, or persistence lives here.
"""

from dataclasses import dataclass, replace
import math
from typing import Iterable, Sequence

import numpy as np


FEATURE_COUNT = 10
CALIBRATION_TARGETS = tuple((x, y) for y in (0.1, 0.5, 0.9) for x in (0.1, 0.5, 0.9))
VALIDATION_TARGETS = ((0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7))


@dataclass(frozen=True)
class GazeObservation:
    timestamp: float
    features: tuple[float, ...] = ()
    valid: bool = False
    reason: str = "Sin ojos válidos"
    auxiliary_features: tuple[float, ...] = ()
    feature_schema: str = "iris10-v1"


@dataclass(frozen=True)
class CalibrationReport:
    """Accuracy in normalized screen units; no fields are physical angles.

    ``mean_error`` and ``max_error`` include every held-out frame and decide
    acceptance. The per-target center error and RMS jitter are diagnostics
    only; they can never hide a bad raw prediction or enable desktop input.
    """
    accepted: bool = False
    mean_error: float = math.inf
    max_error: float = math.inf
    samples: int = 0
    reason: str = "Calibración pendiente"
    target_count: int = 0
    worst_target: tuple[float, float] | None = None
    jitter_error: float = math.inf
    target_mean_error: float = math.inf

    @property
    def passed(self) -> bool:
        return self.accepted


@dataclass(frozen=True)
class GazeState:
    state: str
    pointer: tuple[float, float] | None = None
    can_act: bool = False
    paused: bool = False
    reason: str = ""


def _usable(observation: GazeObservation) -> bool:
    try:
        return (
            observation.valid is True
            and not isinstance(observation.timestamp, bool)
            and math.isfinite(observation.timestamp)
            and len(observation.features) == FEATURE_COUNT
            and all(not isinstance(v, bool) and math.isfinite(v) for v in observation.features)
            and all(abs(observation.features[i]) <= 0.65 for i in (0, 2))
            and all(abs(observation.features[i]) <= 0.4 for i in (1, 3))
            and abs(observation.features[4]) <= 0.42
            and 0.05 < observation.features[5] < 1.1
            and 0 < observation.features[6] <= 1.5
            and abs(observation.features[7]) <= 0.45
            and all(0 <= observation.features[i] <= 1 for i in (8, 9))
        )
    except (TypeError, ValueError, AttributeError):
        return False


def extract_gaze_observation(
    landmarks: Sequence,
    timestamp: float,
    width: int = 640,
    height: int = 480,
) -> GazeObservation:
    """Extract iris-in-eye geometry from one already-mirrored face mesh.

    Landmarks expose normalized ``x`` and ``y`` attributes. Features are both
    iris offsets (x/y each), nose displacement (a 2-D posture proxy), eye span,
    roll, and the eye midpoint in the image. This is not a 3-D gaze model.
    Pixel aspect ratio is applied before angles and distances are evaluated.
    Camera mirroring must happen once, upstream; it is not repeated here.
    """
    def invalid(reason: str) -> GazeObservation:
        return GazeObservation(timestamp, reason=reason)

    try:
        if not math.isfinite(timestamp) or width <= 0 or height <= 0:
            return invalid("Imagen o tiempo inválidos")
        if len(landmarks) < 478:
            return invalid("Se requieren los puntos faciales y del iris")
        indices = (33, 133, 159, 145, 468, 362, 263, 386, 374, 473, 1)
        points = {
            i: np.asarray((float(landmarks[i].x) * width, float(landmarks[i].y) * height))
            for i in indices
        }
        if not all(np.isfinite(point).all() for point in points.values()):
            return invalid("Puntos oculares no finitos")
        if any(not (0 <= p[0] <= width and 0 <= p[1] <= height) for p in points.values()):
            return invalid("Ojos fuera de la imagen")
        eye_features = []
        centers = []
        for outer, inner, upper, lower, iris in ((33, 133, 159, 145, 468), (362, 263, 386, 374, 473)):
            a, b = points[outer], points[inner]
            if a[0] > b[0]:
                a, b = b, a
            vector = b - a
            span = float(np.linalg.norm(vector))
            if span < 12:
                return invalid("Ojos demasiado pequeños para estimar la mirada")
            horizontal = vector / span
            vertical = np.asarray((-horizontal[1], horizontal[0]))
            opening = abs(float(np.dot(points[lower] - points[upper], vertical))) / span
            if not 0.11 <= opening <= 0.8:
                return invalid("Parpadeo u ojos ocultos")
            center = (a + b) * 0.5
            offset = points[iris] - center
            iris_x = float(np.dot(offset, horizontal)) / span
            iris_y = float(np.dot(offset, vertical)) / span
            if abs(iris_x) > 0.65 or abs(iris_y) > 0.4:
                return invalid("Geometría del iris no fiable")
            eye_features.extend((iris_x, iris_y))
            centers.append(center)
        centers.sort(key=lambda p: p[0])
        eye_vector = centers[1] - centers[0]
        eye_span = float(np.linalg.norm(eye_vector))
        if eye_span < 35:
            return invalid("Rostro demasiado pequeño")
        axis = eye_vector / eye_span
        vertical = np.asarray((-axis[1], axis[0]))
        midpoint = (centers[0] + centers[1]) * 0.5
        nose = points[1] - midpoint
        yaw = float(np.dot(nose, axis)) / eye_span
        pitch = float(np.dot(nose, vertical)) / eye_span
        roll = math.atan2(eye_vector[1], eye_vector[0])
        if abs(yaw) > 0.42 or not 0.05 < pitch < 1.1 or abs(roll) > 0.45:
            return invalid("Cabeza fuera del margen de seguimiento")
        features = tuple(eye_features) + (
            yaw, pitch, eye_span / width, roll, float(midpoint[0] / width), float(midpoint[1] / height)
        )
        return GazeObservation(timestamp, features, True, "")
    except (TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return invalid("Observación ocular inválida")


class GazeCalibration:
    """Bounded ridge mapping with a mandatory, held-out accuracy gate.

    Error is Euclidean distance in normalized monitor coordinates, not pixels
    or physical distance. The default gates are exploratory, not evidence of
    production accuracy. Physical target-selection tests remain mandatory.
    """

    engine_id = "legacy-ridge-v1"
    observation_schema = "iris10-v1"

    def __init__(self, *, mean_error_limit: float = 0.04, max_error_limit: float = 0.08):
        if not all(math.isfinite(v) and 0 < v <= 0.25 for v in (mean_error_limit, max_error_limit)):
            raise ValueError("Los límites de error deben estar entre 0 y 0.25")
        self.mean_error_limit = mean_error_limit
        self.max_error_limit = max_error_limit
        self.reset()

    def reset(self) -> None:
        self._samples: list[tuple[GazeObservation, tuple[float, float]]] = []
        self._weights = self._mean = self._spread = self._low = self._high = None
        self._binocular_low = self._binocular_high = None
        self._last_timestamp = -math.inf
        self.ready = False
        self.report = CalibrationReport()

    @property
    def fitted(self) -> bool:
        return self._weights is not None

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def training_samples(self) -> tuple[tuple[GazeObservation, tuple[float, float]], ...]:
        """Detached, immutable observations for explicit local diagnostics.

        Reading this snapshot never fits, validates, or authorizes a pointer.
        No images or identity data are part of these numeric observations.
        """
        return tuple((replace(o, features=tuple(o.features), auxiliary_features=tuple(o.auxiliary_features)), tuple(target))
                     for o, target in self._samples)

    def diagnostic_prediction(self, observation: GazeObservation) -> dict:
        """Inspect the fitted model without changing readiness or enabling input.

        ``raw`` may be outside the screen or calibrated geometry and is NEVER
        an authorized pointer. ``bounded`` applies exactly the normal estimate
        guards, but still bypasses the readiness gate for display only.
        """
        if not self.fitted:
            return {"raw": None, "bounded": None, "reason": "Modelo todavía no ajustado"}
        if not _usable(observation):
            return {"raw": None, "bounded": None, "reason": "Observación ocular no válida"}
        result = self._raw_estimate(observation)
        if result is None or not np.isfinite(result).all():
            return {"raw": None, "bounded": None, "reason": "Estimación no finita"}
        bounded = self._estimate(observation)
        return {
            "raw": [float(v) for v in result],
            "bounded": list(bounded) if bounded is not None else None,
            "reason": ("Solo diagnóstico; no autoriza control" if bounded is not None
                       else "Bloqueado por el margen calibrado o de pantalla; solo diagnóstico"),
        }

    def diagnostic_model(self) -> dict:
        """Detached numeric coefficients for explaining amplification, not input."""
        if not self.fitted:
            return {"coefficients": None, "intercept": None}
        coefficients = self._weights[:6] / self._spread[:, None]
        intercept = self._weights[6] - self._mean @ coefficients
        return {"coefficients": coefficients.tolist(), "intercept": intercept.tolist()}

    @staticmethod
    def _target(target) -> tuple[float, float] | None:
        try:
            if len(target) == 2 and all(math.isfinite(v) and 0 <= v <= 1 for v in target):
                return float(target[0]), float(target[1])
        except (TypeError, ValueError):
            pass
        return None

    def add_sample(self, observation: GazeObservation, target_xy: tuple[float, float]) -> bool:
        target = self._target(target_xy)
        if not _usable(observation) or target is None or observation.timestamp <= self._last_timestamp:
            return False
        self._samples.append((observation, target))
        self._last_timestamp = observation.timestamp
        # New training data invalidate any previous independent validation.
        self._weights = None
        self.ready = False
        self.report = CalibrationReport()
        return True

    def fit(self) -> bool:
        self.ready = False
        self._weights = None
        self.report = CalibrationReport(reason="Faltan nueve objetivos distintos")
        unique_targets = set(target for _, target in self._samples)
        if len(unique_targets) < 9:
            return False
        # Consecutive camera frames from the same fixation are not independent
        # screen targets. Give each target one robust representative, so a
        # longer capture (or higher FPS) cannot dominate the fit/regularizer.
        # This uses training data only; held-out frames are never refitted.
        grouped = {
            target: np.asarray([observation.features for observation, captured_target in self._samples
                                if captured_target == target])
            for target in sorted(unique_targets)
        }
        features = np.asarray([np.median(rows, axis=0) for rows in grouped.values()])
        targets = np.asarray(list(grouped))
        if np.any(np.ptp(targets, axis=0) < 0.6):
            self.report = CalibrationReport(reason="Los objetivos no cubren la pantalla")
            return False
        iris_mean = (features[:, :2] + features[:, 2:4]) / 2
        singular = np.linalg.svd(iris_mean - iris_mean.mean(axis=0), compute_uv=False)
        if singular[-1] / math.sqrt(len(features)) < 0.004 or singular[0] / singular[-1] > 100:
            self.report = CalibrationReport(reason="No hay variación ocular suficiente en ambos ejes")
            return False
        self._mean = features[:, :6].mean(axis=0)
        self._spread = np.maximum(features[:, :6].std(axis=0), 0.015)
        design = np.column_stack(((features[:, :6] - self._mean) / self._spread, np.ones(len(features))))
        # Nose position may accidentally follow the target sequence while the
        # user calibrates. It must not replace the actual eye signal merely
        # because nose landmarks are less noisy. Shrink these posture proxies
        # more strongly; this is not learned 3-D head-motion compensation.
        penalty = np.diag((0.01, 0.01, 0.01, 0.01, 1.0, 1.0, 0.0))
        try:
            weights = np.linalg.solve(design.T @ design + penalty, design.T @ targets)
        except np.linalg.LinAlgError:
            self.report = CalibrationReport(reason="La calibración no se pudo resolver")
            return False
        if not np.isfinite(weights).all():
            return False
        self._weights = weights
        # Keep the original runtime geometry guards based on the raw training
        # observations. Robust fitting must not silently relax these bounds.
        raw_features = np.asarray([observation.features for observation, _ in self._samples])
        self._low = np.quantile(raw_features, 0.05, axis=0)
        self._high = np.quantile(raw_features, 0.95, axis=0)
        binocular = raw_features[:, :2] - raw_features[:, 2:4]
        self._binocular_low = np.quantile(binocular, 0.05, axis=0)
        self._binocular_high = np.quantile(binocular, 0.95, axis=0)
        self.report = CalibrationReport(reason="Falta validación con objetivos nuevos")
        return True

    def _estimate(self, observation: GazeObservation) -> tuple[float, float] | None:
        if not self.fitted or not _usable(observation):
            return None
        features = np.asarray(observation.features)
        # Iris, 2-D posture, scale, roll and frame position all have finite
        # margins. These conservative bounds are NOT distance compensation.
        margin = np.asarray((0.10, 0.07, 0.10, 0.07, 0.10, 0.12, 0.0, 0.12, 0.09, 0.09))
        low, high = self._low - margin, self._high + margin
        low[6], high[6] = self._low[6] * 0.78, self._high[6] * 1.25
        if np.any(features < low) or np.any(features > high):
            return None
        # Opposite iris errors can cancel in a regression and look like a
        # perfectly central gaze. Reject excessive disagreement relative to
        # this user's training geometry; this is not a vergence model.
        binocular = features[:2] - features[2:4]
        binocular_margin = np.asarray((0.08, 0.07))
        if (np.any(binocular < self._binocular_low - binocular_margin)
                or np.any(binocular > self._binocular_high + binocular_margin)):
            return None
        result = self._raw_estimate(observation)
        if result is None or not np.isfinite(result).all() or np.any(result < -0.04) or np.any(result > 1.04):
            return None
        return tuple(float(v) for v in np.clip(result, 0, 1))

    def _raw_estimate(self, observation):
        row = np.append((np.asarray(observation.features[:6]) - self._mean) / self._spread, 1.0)
        return row @ self._weights

    def validate(
        self, samples: Iterable[tuple[GazeObservation, tuple[float, float]]]
    ) -> CalibrationReport:
        self.ready = False
        pairs = list(samples)
        self.report = CalibrationReport(reason="Faltan cuatro objetivos de validación nuevos")
        if not self.fitted or len(pairs) < 4:
            return self.report
        seen_times = {observation.timestamp for observation, _ in self._samples}
        training_targets = [target for _, target in self._samples]
        validation_targets = set()
        errors = []
        predictions_by_target = {}
        for observation, candidate_target in pairs:
            target = self._target(candidate_target)
            if target is None or not _usable(observation) or observation.timestamp in seen_times:
                self.report = CalibrationReport(reason="Las muestras de validación deben ser independientes")
                return self.report
            if observation.timestamp <= self._last_timestamp:
                self.report = CalibrationReport(reason="La validación debe realizarse después de calibrar")
                return self.report
            seen_times.add(observation.timestamp)
            if any(math.dist(target, trained) < 0.04 for trained in training_targets):
                self.report = CalibrationReport(reason="Usa objetivos diferentes de los de calibración")
                return self.report
            prediction = self._estimate(observation)
            if prediction is None:
                self.report = CalibrationReport(reason="Validación fuera del margen de seguimiento")
                return self.report
            validation_targets.add(target)
            errors.append(math.dist(prediction, target))
            predictions_by_target.setdefault(target, []).append(prediction)
        if len(validation_targets) < 4:
            return self.report
        coordinates = np.asarray(list(validation_targets))
        if np.any(np.ptp(coordinates, axis=0) < 0.3):
            self.report = CalibrationReport(reason="La validación debe cubrir ambos ejes")
            return self.report
        mean_error, max_error = float(np.mean(errors)), max(errors)
        # These target-level metrics explain the failure, but do not relax the
        # accuracy gate: every raw prediction still participates in max_error.
        # A jittery gaze centered on the target must not unlock the cursor.
        centers = {target: np.median(rows, axis=0) for target, rows in predictions_by_target.items()}
        target_errors = {target: math.dist(center, target) for target, center in centers.items()}
        jitter_error = max(
            float(np.sqrt(np.mean(np.sum((np.asarray(rows) - centers[target]) ** 2, axis=1))))
            for target, rows in predictions_by_target.items()
        )
        worst_target = max(
            predictions_by_target,
            key=lambda target: max(math.dist(prediction, target)
                                   for prediction in predictions_by_target[target]),
        )
        self.ready = mean_error <= self.mean_error_limit and max_error <= self.max_error_limit
        if self.ready:
            reason = "Validación aprobada"
        else:
            issue = ("la estimación ocular varió demasiado al mirar los puntos"
                     if jitter_error > self.mean_error_limit
                     else "la posición estimada no coincidió con los puntos")
            reason = (
                f"Precisión insuficiente: {issue}. "
                f"Error medio {mean_error:.1%} y máximo {max_error:.1%} "
                f"(límites {self.mean_error_limit:.1%} y {self.max_error_limit:.1%}). "
                "Mantén la cabeza cómoda y estable, mira el centro de cada punto "
                "y evita reflejos sobre los ojos antes de reintentar."
            )
        self.report = CalibrationReport(
            self.ready, mean_error, max_error, len(errors),
            reason, len(validation_targets), worst_target, jitter_error,
            float(np.mean(list(target_errors.values()))),
        )
        return self.report

    def predict(self, observation: GazeObservation) -> tuple[float, float] | None:
        return self._estimate(observation) if self.ready else None


class GazeSession:
    """Fail-closed frame freshness and 70-second rest latch, without identity.

    ``now`` and capture timestamps use the same monotonic clock. Repeated
    packets never count as fresh sight of the user. Only an explicit victory
    with stable valid gaze can leave rest; raw presence cannot unlock it.
    """

    def __init__(
        self,
        calibration: GazeCalibration | None = None,
        *,
        loss_timeout: float = 70.0,
        recovery_seconds: float = 0.15,
        max_frame_age: float = 0.25,
    ):
        if not all(math.isfinite(v) and v > 0 for v in (loss_timeout, recovery_seconds, max_frame_age)):
            raise ValueError("Los tiempos de seguimiento deben ser finitos y positivos")
        self.calibration = calibration if calibration is not None else GazeCalibration()
        self.loss_timeout = loss_timeout
        self.recovery_seconds = recovery_seconds
        self.max_frame_age = max_frame_age
        self._reset_tracking()

    def _reset_tracking(self) -> None:
        self.paused = False
        self._start = self._last_now = None
        self._last_processed = -math.inf
        self._last_received = -math.inf
        self._last_valid = self._stable_since = None
        self._last_pointer = None

    def reset(self, now: float | None = None) -> None:
        """Start a new session: previous calibration must not silently persist."""
        if now is not None and not math.isfinite(now):
            raise ValueError("El tiempo debe ser finito")
        self.calibration.reset()
        self._reset_tracking()
        self._start = now

    def update(
        self, observation: GazeObservation | None, now: float, *, victory: bool = False
    ) -> GazeState:
        if not math.isfinite(now) or (self._last_now is not None and now < self._last_now):
            self._stable_since = None
            self._last_pointer = None
            return GazeState("LOST", paused=self.paused, reason="Reloj de seguimiento inválido")
        self._last_now = now
        if self._start is None:
            self._start = now
        absence_since = self._last_valid if self._last_valid is not None else self._start
        # Evaluate before accepting a new face, otherwise a bystander arriving
        # after the timeout could prevent the rest latch from ever engaging.
        if now - absence_since >= self.loss_timeout:
            self.paused = True
        received_before = self._last_received
        try:
            stamp = observation.timestamp
            if not isinstance(stamp, bool) and math.isfinite(stamp) and stamp <= now:
                self._last_received = max(self._last_received, stamp)
        except (TypeError, ValueError, AttributeError):
            pass
        fresh = (
            observation is not None
            and _usable(observation)
            and 0 <= now - observation.timestamp <= self.max_frame_age
            and observation.timestamp > received_before
        )
        if not fresh:
            # A recent duplicate may simply be a UI poll between camera
            # frames. Hold the previously authorized position within the age
            # limit, but never count the duplicate as fresh presence/stability.
            recent_duplicate = (
                observation is not None and _usable(observation)
                and observation.timestamp == self._last_processed == self._last_received
                and 0 <= now - observation.timestamp <= self.max_frame_age
            )
            if recent_duplicate:
                stable = (
                    self._stable_since is not None and self._last_valid is not None
                    and self._last_valid - self._stable_since >= self.recovery_seconds
                )
                if self.calibration.ready and self._last_pointer is not None and stable:
                    if self.paused and victory:
                        self.paused = False
                    if not self.paused:
                        return GazeState("TRACKING", self._last_pointer, True)
                if self.paused:
                    return GazeState("REST", paused=True, reason="Pausa: requiere victoria y mirada estable")
                if not self.calibration.ready:
                    return GazeState("CALIBRATION", reason="Calibración ocular obligatoria")
                return GazeState("RECOVERING", reason="Comprobando estabilidad ocular")
            self._stable_since = None
            self._last_pointer = None
            return GazeState(
                "REST" if self.paused else "LOST", paused=self.paused,
                reason="Esperando una observación ocular nueva y válida",
            )
        self._last_processed = observation.timestamp
        if not self.calibration.ready:
            self._stable_since = None
            self._last_pointer = None
            # Valid observations during calibration establish presence only;
            # they can never authorize desktop actions or unlock rest.
            self._last_valid = observation.timestamp
            return GazeState("REST" if self.paused else "CALIBRATION", paused=self.paused,
                             reason="Calibración ocular obligatoria")
        pointer = self.calibration.predict(observation)
        if pointer is None:
            self._stable_since = None
            self._last_pointer = None
            return GazeState("REST" if self.paused else "LOST", paused=self.paused,
                             reason="Mirada fuera del margen calibrado")
        if self._last_valid is None or observation.timestamp - self._last_valid > 0.75:
            self._stable_since = None
        self._last_valid = observation.timestamp
        self._last_pointer = pointer
        if self._stable_since is None:
            self._stable_since = observation.timestamp
        stable = observation.timestamp - self._stable_since >= self.recovery_seconds
        if self.paused:
            if not (victory and stable):
                return GazeState("REST", paused=True, reason="Pausa: requiere victoria y mirada estable")
            self.paused = False
        if not stable:
            return GazeState("RECOVERING", reason="Comprobando estabilidad ocular")
        return GazeState("TRACKING", pointer, True)
