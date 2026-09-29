"""Personalized mapping of a pretrained binocular CNN's observations.

No camera, neural inference, model downloads or desktop actions live here.
The small kernel model selects its regularization using TRAINING targets only
(leave-one-target-out, not random correlated frames). Held-out validation is
unchanged, and is never used to train, select, repair or smooth predictions.
"""

import math

import numpy as np

from .gaze import CalibrationReport, GazeCalibration, _usable


PRECISION_SCHEMA = "openvino-gaze6-v1"
PRECISION_ENGINE = "precision-openvino-v1"
PERIPHERAL_ENGINE = "precision-openvino-v2"
# Interleaving avoids tying screen Y to steadily increasing acquisition time.
TRAINING_TARGETS = (
    (.5, .5), (.1, .1), (.9, .9), (.9, .1), (.1, .9),
    (.5, .1), (.5, .9), (.1, .5), (.9, .5),
    (.3, .3), (.7, .7), (.7, .3), (.3, .7),
)
VALIDATION_TARGETS = (
    (.2, .2), (.8, .8), (.8, .2), (.2, .8), (.5, .2),
    (.8, .5), (.5, .8), (.2, .5), (.45, .55),
)
# Keep the v1 grid/model replayable. This new revision learns an additional
# perimeter without replacing its intermediate targets or expanding outputs.
PERIPHERAL_TRAINING_TARGETS = (
    (.5, .5), (.04, .04), (.9, .9), (.96, .04), (.1, .9),
    (.5, .96), (.3, .3), (.04, .5), (.7, .7), (.96, .96),
    (.1, .1), (.04, .96), (.9, .1), (.5, .04), (.3, .7),
    (.96, .5), (.7, .3), (.5, .1), (.5, .9), (.1, .5), (.9, .5),
)
PERIPHERAL_VALIDATION_TARGETS = (
    (.2, .2), (.93, .93), (.8, .2), (.07, .93), (.5, .2),
    (.93, .07), (.8, .8), (.07, .07), (.2, .8),
    (.8, .5), (.5, .8), (.2, .5), (.45, .55),
)


def precision_observation_usable(observation):
    if not _usable(observation) or getattr(observation, "feature_schema", None) != PRECISION_SCHEMA:
        return False
    values = getattr(observation, "auxiliary_features", ())
    try:
        return (len(values) == 6
                and all(not isinstance(v, bool) and math.isfinite(v) for v in values)
                and .98 <= math.sqrt(sum(v * v for v in values[:3])) <= 1.02
                # OMZ gazeVectorToGazeAngles maps (0, 0, -1) to frontal
                # (yaw=0, pitch=0). Preserve that actual model convention.
                and values[2] < -.15
                and all(abs(v) < math.pi / 2 for v in values[3:]))
    except (TypeError, ValueError):
        return False


def _vector(observation, family):
    neural = np.asarray(observation.auxiliary_features)
    # Preserve the CNN's vector convention. A personalized screen map learns
    # direction/sign; do not guess camera intrinsics or distance in centimeters.
    ocular = neural[:2] / -neural[2]
    if family == "neural":
        return np.concatenate((ocular, neural[3:]))
    return np.concatenate((ocular, np.asarray(observation.features[:4]), neural[3:]))


def _kernel(a, b, width):
    linear = a @ b.T / a.shape[1]
    if width == 0:
        return linear
    distances = np.maximum(0, (a * a).sum(axis=1)[:, None] + (b * b).sum(axis=1) - 2 * a @ b.T)
    # A linear tail retains coarse extrapolation between edge targets.
    return linear + np.exp(-distances / (2 * width * width * a.shape[1]))


def _fit_model(x, y, width, ridge):
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), .025)
    # Prevent tiny posture variation dominating the actual ocular signal.
    scale[-3:] /= .35
    centers = (x - mean) / scale
    intercept = y.mean(axis=0)
    weights = np.linalg.solve(_kernel(centers, centers, width) + ridge * np.eye(len(x)), y - intercept)
    return mean, scale, centers, weights, intercept


def _predict_model(model, x, width):
    mean, scale, centers, weights, intercept = model
    return _kernel((np.atleast_2d(x) - mean) / scale, centers, width) @ weights + intercept


class PrecisionGazeCalibration(GazeCalibration):
    engine_id = PRECISION_ENGINE
    observation_schema = PRECISION_SCHEMA
    training_targets = TRAINING_TARGETS
    validation_targets = VALIDATION_TARGETS

    def reset(self):
        super().reset()
        self._personal_model = None
        self._candidates = []
        self._selected = None
        self._neural_low = self._neural_high = None

    @property
    def fitted(self):
        return self._weights is not None and self._personal_model is not None

    def add_sample(self, observation, target_xy):
        if not precision_observation_usable(observation):
            return False
        accepted = super().add_sample(observation, target_xy)
        if accepted:
            self._personal_model = None
            self._selected = None
            self._candidates = []
        return accepted

    def fit(self):
        self._personal_model = None
        self._candidates = []
        self._selected = None
        self.ready = False
        unique = sorted(set(target for _, target in self._samples))
        if len(unique) != len(self.training_targets):
            self._weights = None
            self.report = CalibrationReport(reason=f"Faltan {len(self.training_targets)} objetivos de calibración personal")
            return False
        # Establish the same raw iris/pose/scale/binocular bounds as legacy.
        if not super().fit():
            return False
        targets = np.asarray(unique)
        try:
            for family in ("neural", "fusion"):
                groups = [np.asarray([_vector(o, family) for o, t in self._samples if t == target])
                          for target in unique]
                x = np.asarray([np.median(group, axis=0) for group in groups])
                for width in (0.0, .7, 1.5):
                    for ridge in (.01, .1, 1.0):
                        errors = []
                        for i, group in enumerate(groups):
                            keep = np.arange(len(x)) != i
                            model = _fit_model(x[keep], targets[keep], width, ridge)
                            predictions = _predict_model(model, group, width)
                            errors.append(float(np.linalg.norm(predictions - targets[i], axis=1).mean()))
                        self._candidates.append(dict(family=family, width=width, ridge=ridge,
                                                     training_cv_error=float(np.mean(errors))))
            self._selected = min(self._candidates, key=lambda row: row["training_cv_error"]).copy()
            family, width, ridge = (self._selected[k] for k in ("family", "width", "ridge"))
            x = np.asarray([np.median([_vector(o, family) for o, t in self._samples if t == target], axis=0)
                            for target in unique])
            self._personal_model = _fit_model(x, targets, width, ridge)
            neural = np.asarray([o.auxiliary_features for o, _ in self._samples])
            self._neural_low = neural.min(axis=0)
            self._neural_high = neural.max(axis=0)
            if not all(np.isfinite(v).all() for v in self._personal_model):
                raise ValueError("Ajuste personal no finito")
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            self._personal_model = None
            self._weights = None
            self.report = CalibrationReport(reason="No se pudo ajustar el modelo ocular personal")
            return False
        self.report = CalibrationReport(reason=f"Modelo personal ajustado; faltan {len(self.validation_targets)} objetivos nuevos")
        return True

    def _raw_estimate(self, observation):
        if not self.fitted or not precision_observation_usable(observation):
            return None
        return _predict_model(self._personal_model, _vector(observation, self._selected["family"]),
                              self._selected["width"])[0]

    def _estimate(self, observation):
        if not self.fitted or not precision_observation_usable(observation):
            return None
        neural = np.asarray(observation.auxiliary_features)
        margin = np.asarray((.15, .15, .15, .18, .18, .18))
        if np.any(neural < self._neural_low - margin) or np.any(neural > self._neural_high + margin):
            return None
        return super()._estimate(observation)

    def validate(self, samples):
        pairs = list(samples)
        if (len({self._target(t) for _, t in pairs}) < len(self.validation_targets)
                or any(not precision_observation_usable(o) for o, _ in pairs)):
            self.ready = False
            self.report = CalibrationReport(
                reason=f"Se necesitan {len(self.validation_targets)} objetivos nuevos con observaciones del motor ocular")
            return self.report
        return super().validate(pairs)

    def diagnostic_model(self):
        return {
            "engine_id": self.engine_id, "observation_schema": self.observation_schema,
            "kind": "personalized_kernel_ridge", "coefficients": None, "intercept": None,
            "selection": dict(self._selected) if self._selected else None,
            "training_candidates": [dict(row) for row in self._candidates],
            "selection_source": "leave_one_training_target_out; never validation",
            "training_target_count": len(set(t for _, t in self._samples)),
        }


class PeripheralGazeCalibration(PrecisionGazeCalibration):
    """Same tested estimator, new perimeter acquisition and independent gate.

    Do not synthesize edge observations from v1 data: more screen coverage
    requires actual new observations. No attraction, snapping or global gain.
    """

    engine_id = PERIPHERAL_ENGINE
    training_targets = PERIPHERAL_TRAINING_TARGETS
    validation_targets = PERIPHERAL_VALIDATION_TARGETS
    training_collection_seconds = 1.2

    def fit(self):
        if set(target for _, target in self._samples) != set(self.training_targets):
            self.ready = False
            self._weights = self._personal_model = self._selected = None
            self._candidates = []
            self.report = CalibrationReport(reason="Faltan los 21 objetivos centrales y perimetrales")
            return False
        return super().fit()

    def validate(self, samples):
        pairs = list(samples)
        if set(self._target(target) for _, target in pairs) != set(self.validation_targets):
            self.ready = False
            self.report = CalibrationReport(reason="Faltan los 13 objetivos independientes, incluidos los bordes")
            return self.report
        return super().validate(pairs)


def gaze_calibration_type(engine_id):
    if engine_id == "legacy-ridge-v1":
        return GazeCalibration
    if engine_id == PRECISION_ENGINE:
        return PrecisionGazeCalibration
    if engine_id == PERIPHERAL_ENGINE:
        return PeripheralGazeCalibration
    raise ValueError("Motor ocular no compatible")


def create_gaze_calibration(engine_id, **kwargs):
    return gaze_calibration_type(engine_id)(**kwargs)
