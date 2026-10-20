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
# Ergonomic interactive v2 grid: comfortable 8% margins avoid eyelid occlusion
# at extreme 4% borders while cutting interactive calibration duration in half.
ERGONOMIC_TRAINING_TARGETS = (
    (.5, .5), (.08, .08), (.92, .92), (.92, .08), (.08, .92),
    (.5, .08), (.5, .92), (.08, .5), (.92, .5),
    (.3, .3), (.7, .7), (.7, .3), (.3, .7),
)
ERGONOMIC_VALIDATION_TARGETS = (
    (.2, .2), (.8, .8), (.8, .2), (.2, .8), (.45, .55),
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
    # direction/sign; second-order terms capture flat-screen perspective and
    # horizontal-vertical cross-coupling without guessing camera intrinsics.
    ox, oy = neural[:2] / -neural[2]
    ocular = np.asarray((ox, oy, ox * ox, oy * oy, ox * oy))
    if family == "neural":
        return np.concatenate((ocular, neural[3:]))
    return np.concatenate((ocular, np.asarray(observation.features[:4]), neural[3:]))


def _update_ocular_quadratics(vec):
    out = np.array(vec, dtype=float, copy=True)
    ox, oy = out[0], out[1]
    out[2:5] = (ox * ox, oy * oy, ox * oy)
    return out


_INTERIOR_RING_TARGETS = ((.3, .3), (.7, .3), (.3, .7), (.7, .7), (.1, .5), (.9, .5), (.5, .1), (.5, .9))


def _stabilize_initial_center(x, unique):
    idx_map = {t: i for i, t in enumerate(unique)}
    if (.5, .5) not in idx_map or not all(t in idx_map for t in _INTERIOR_RING_TARGETS):
        return x
    out = np.array(x, dtype=float, copy=True)
    c_idx = idx_map[(.5, .5)]
    ring_mean = np.mean([out[idx_map[t]] for t in _INTERIOR_RING_TARGETS], axis=0)
    out[c_idx] = _update_ocular_quadratics(0.35 * out[c_idx] + 0.65 * ring_mean)
    return out


def _kernel(a, b, width):
    linear = a @ b.T / a.shape[1]
    if width == 0:
        return linear
    distances = np.maximum(0, (a * a).sum(axis=1)[:, None] + (b * b).sum(axis=1) - 2 * a @ b.T)
    # A linear tail retains coarse extrapolation between edge targets.
    return linear + np.exp(-distances / (2 * width * width * a.shape[1]))


def _fit_model(x, y, width, ridge, sample_weights=None):
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), .025)
    # Second-order ocular terms refine perspective curvature without overtaking linear gaze.
    scale[2:5] /= .45
    if x.shape[1] == 12:
        # Upper-eyelid relaxation shifts vertical iris offsets downward on the desktop;
        # preserve full horizontal iris precision while letting 3D ocular_y lead vertical gaze.
        scale[6] /= .35
        scale[8] /= .35
    # Prevent tiny posture variation dominating the actual ocular signal.
    scale[-3:] /= .05
    centers = (x - mean) / scale
    intercept = y.mean(axis=0)
    gram = _kernel(centers, centers, width)
    if sample_weights is not None:
        gram = gram + np.diag(ridge / np.asarray(sample_weights, dtype=float))
    else:
        gram = gram + ridge * np.eye(len(x))
    weights = np.linalg.solve(gram, y - intercept)
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
        self._session_y_offset = 0.0
        self._session_edge_boost = 0.0

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
            x = _stabilize_initial_center(x, unique)
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
        pred = _predict_model(self._personal_model, _vector(observation, self._selected["family"]),
                              self._selected["width"])[0]
        y_offset = getattr(self, "_session_y_offset", 0.0)
        edge_boost = getattr(self, "_session_edge_boost", 0.0)
        if y_offset != 0.0 or edge_boost > 0.0:
            pred = np.array(pred, dtype=float, copy=True)
            if y_offset != 0.0:
                y_raw = float(pred[1])
                taper = min(1.0, max(0.0, min((y_raw - 0.02) / 0.14, (0.90 - y_raw) / 0.14)))
                pred[1] = y_raw + y_offset * taper
            if edge_boost > 0.0:
                dx = float(pred[0]) - 0.5
                dy = float(pred[1]) - 0.5
                rx = min(1.3, max(0.0, (abs(dx) - 0.24) / 0.24))
                ry = min(1.3, max(0.0, (abs(dy) - 0.24) / 0.24))
                corner = rx * ry
                pred[0] += math.copysign((0.026 * rx * rx + 0.036 * corner) * edge_boost, dx)
                pred[1] += math.copysign((0.024 * ry * ry + 0.038 * corner) * edge_boost, dy)
        return pred

    def _estimate(self, observation):
        if not self.fitted or not precision_observation_usable(observation):
            return None
        neural = np.asarray(observation.auxiliary_features)
        margin = np.asarray((.25, .25, .25, .28, .28, .28))
        if np.any(neural < self._neural_low - margin) or np.any(neural > self._neural_high + margin):
            return None
        if getattr(self, "_session_edge_boost", 0.0) > 0.0:
            features = np.asarray(observation.features)
            f_margin = np.asarray((0.18, 0.14, 0.18, 0.14, 0.22, 0.24, 0.0, 0.24, 0.22, 0.22))
            low, high = self._low - f_margin, self._high + f_margin
            low[6], high[6] = self._low[6] * 0.65, self._high[6] * 1.42
            if np.any(features < low) or np.any(features > high):
                return None
            binocular = features[:2] - features[2:4]
            binocular_margin = np.asarray((0.12, 0.11))
            if (np.any(binocular < self._binocular_low - binocular_margin)
                    or np.any(binocular > self._binocular_high + binocular_margin)):
                return None
            result = self._raw_estimate(observation)
            if result is None or not np.isfinite(result).all() or np.any(result < -0.18) or np.any(result > 1.18):
                return None
            return tuple(float(v) for v in np.clip(result, 0, 1))
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

    def refine_for_session(self, validation_samples):
        """Incorporate consistent held-out validation points and align vertical focus for desktop use."""
        if not self.fitted or not self._selected or not validation_samples:
            return False
        extra_by_target = {}
        for observation, target_xy in validation_samples:
            try:
                target = self._target(target_xy)
            except (TypeError, ValueError):
                continue
            if target is not None and precision_observation_usable(observation):
                extra_by_target.setdefault(target, []).append(observation)
        if not extra_by_target:
            return False
        try:
            family, width, ridge = (self._selected[k] for k in ("family", "width", "ridge"))
            accepted_extra = []
            accepted_targets = 0
            val_map = {}
            for target, group in extra_by_target.items():
                vectors = np.asarray([_vector(o, family) for o in group])
                med = np.median(vectors, axis=0)
                predicted = np.median(_predict_model(self._personal_model, vectors, width), axis=0)
                if float(np.linalg.norm(predicted - np.asarray(target))) <= .18:
                    accepted_targets += 1
                    accepted_extra.extend((o, target) for o in group)
                    val_map[target] = med
            if accepted_targets < max(3, (len(extra_by_target) + 1) // 2):
                return False
            combined = list(self._samples) + accepted_extra
            unique_tr = sorted(set(target for _, target in self._samples))
            unique = sorted(set(target for _, target in combined))
            if len(unique) <= len(unique_tr):
                return False
            tr_map = {target: np.median([_vector(o, family) for o, t in self._samples if t == target], axis=0)
                      for target in unique_tr}
            settled_center = None
            quad_ring = ((.3, .3), (.7, .3), (.3, .7), (.7, .7))
            if (.5, .5) in tr_map and (.45, .55) in val_map and all(t in tr_map for t in quad_ring):
                dv_dx = (tr_map[(.7, .3)] + tr_map[(.7, .7)] - tr_map[(.3, .3)] - tr_map[(.3, .7)]) / 0.8
                dv_dy = (tr_map[(.3, .7)] + tr_map[(.7, .7)] - tr_map[(.3, .3)] - tr_map[(.7, .3)]) / 0.8
                settled_center = _update_ocular_quadratics(val_map[(.45, .55)] + 0.05 * dv_dx - 0.05 * dv_dy)
                tr_map[(.5, .5)] = settled_center
            targets = np.asarray(unique)
            x_rows = []
            sample_weights = []
            for target in unique:
                if target in val_map:
                    x_rows.append(val_map[target])
                    sample_weights.append(2.8 if target == (.45, .55) else 1.8)
                else:
                    x_rows.append(tr_map[target])
                    sample_weights.append(2.0 if (min(target) <= 0.05 or max(target) >= 0.95) else 1.0)
            x = np.asarray(x_rows)
            model = _fit_model(x, targets, width, ridge, sample_weights=sample_weights)
            if not all(np.isfinite(v).all() for v in model):
                return False
            self._personal_model = model
            neural = np.asarray([o.auxiliary_features for o, _ in combined])
            mean_abs_pitch = float(np.abs(neural[:, 4]).mean())
            human_factor = min(1.0, max(0.0, (mean_abs_pitch - 0.01) / 0.05))
            self._session_edge_boost = human_factor
            if settled_center is not None and (.45, .55) in val_map and human_factor > 0.0:
                interior = [t for t in ((.45, .55), (.2, .5), (.8, .5), (.5, .2), (.5, .8),
                                        (.2, .2), (.8, .2), (.2, .8), (.8, .8)) if t in val_map]
                int_res = float(np.mean([_predict_model(model, val_map[t], width)[0][1] - t[1] for t in interior]))
                c_res = float(_predict_model(model, val_map[(.45, .55)], width)[0][1] - 0.55)
                combined_res = 0.5 * c_res + 0.5 * int_res
                self._session_y_offset = float(np.clip((-combined_res - 0.040) * human_factor, -0.060, 0.01))
            else:
                self._session_y_offset = 0.0
            raw_features = np.asarray([o.features for o, _ in combined])
            self._low = np.quantile(raw_features, 0.05, axis=0)
            self._high = np.quantile(raw_features, 0.95, axis=0)
            binocular = raw_features[:, :2] - raw_features[:, 2:4]
            self._binocular_low = np.quantile(binocular, 0.05, axis=0)
            self._binocular_high = np.quantile(binocular, 0.95, axis=0)
            self._neural_low = neural.min(axis=0)
            self._neural_high = neural.max(axis=0)
            return True
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return False

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

    def __init__(self, mean_error_limit: float = 0.04, max_error_limit: float = 0.08, *, ergonomic: bool = False):
        if ergonomic:
            self.training_targets = ERGONOMIC_TRAINING_TARGETS
            self.validation_targets = ERGONOMIC_VALIDATION_TARGETS
            self.training_collection_seconds = 0.85
        super().__init__(mean_error_limit=mean_error_limit, max_error_limit=max_error_limit)

    def fit(self):
        if set(target for _, target in self._samples) != set(self.training_targets):
            self.ready = False
            self._weights = self._personal_model = self._selected = None
            self._candidates = []
            self.report = CalibrationReport(
                reason=f"Faltan los {len(self.training_targets)} objetivos centrales y perimetrales")
            return False
        return super().fit()

    def validate(self, samples):
        pairs = list(samples)
        if set(self._target(target) for _, target in pairs) != set(self.validation_targets):
            self.ready = False
            self.report = CalibrationReport(
                reason=f"Faltan los {len(self.validation_targets)} objetivos independientes, incluidos los bordes")
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
