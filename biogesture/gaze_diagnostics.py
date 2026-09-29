"""Read-only numeric calibration diagnostics; no camera, files, network or input.

Reports are useful evidence, not a different acceptance test. Target errors
use the same bounded estimate as validation; raw estimates are separately
labelled so extrapolation is visible. Training error is in-sample and cannot
establish accuracy. Numeric observations are included ONLY when a caller
explicitly requests ``include_samples=True`` for a voluntary local export.
"""

from dataclasses import asdict
import math
from collections.abc import Mapping

import numpy as np

from . import __version__
from .gaze import FEATURE_COUNT, GazeCalibration, GazeObservation


FEATURE_NAMES = (
    "iris_a_x", "iris_a_y", "iris_b_x", "iris_b_y", "nose_yaw_proxy", "nose_pitch_proxy",
    "eye_span_frame_ratio", "roll_radians", "eye_midpoint_x", "eye_midpoint_y",
)
LEGACY_ENGINE_ID = "legacy-ridge-v1"
PRECISION_ENGINE_ID = "precision-openvino-v1"
PRECISION_ENGINE_IDS = frozenset((PRECISION_ENGINE_ID, "precision-openvino-v2"))
PRECISION_OBSERVATION_SCHEMA = "openvino-gaze6-v1"
AUXILIARY_FEATURE_NAMES = (
    "gaze_unit_x", "gaze_unit_y", "gaze_unit_z", "head_yaw_radians", "head_pitch_radians", "head_roll_radians",
)
# Only these non-identifying acquisition/configuration details can be exported.
# Unknown object attributes are never stringified (they can contain file paths).
CONTEXT_KEYS = frozenset((
    "app_version", "camera_width", "camera_height", "capture_fps", "detection_fps", "face_fps",
    "monitor_width", "monitor_height", "monitor_scale", "background", "pointer_mode", "profile",
    "settle_seconds", "collect_seconds", "minimum_samples", "frame_max_age", "sample_gap_limit",
    "phase",
))
CAPTURE_KEYS = frozenset((
    "phase", "index", "target", "accepted", "rejected", "valid_samples", "samples", "duplicates",
    "stale", "invalid", "future", "reasons", "reason_counts", "elapsed_seconds", "useful_seconds",
    "reacquisitions", "discarded", "timeout", "completed", "fresh_samples", "effective_fps",
    "point_index", "outcome", "attempts",
))
TELEMETRY_KEYS = {
    "camera": frozenset(("requested_width", "requested_height", "requested_fps", "requested_detection_fps", "mirror")),
    "monitor": frozenset(("width", "height", "left", "top")),
    # Absolute worker timestamps are intentionally excluded from the export.
    "worker": frozenset(("image_width", "image_height", "inference_ms", "capture_to_result_ms", "face_fps",
                         "valid", "reason", "returned_faces", "eye_width_px", "eye_opening_ratio",
                         "gaze_engine", "neural_ms", "neural_features")),
}


def _safe(value, depth=0):
    """JSON primitives only; never emit NaN, Infinity, arrays, bytes or objects."""
    if depth > 8:
        return None
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {k: _safe(v, depth + 1) for k, v in value.items() if isinstance(k, str)}
    if isinstance(value, (list, tuple)):
        return [_safe(v, depth + 1) for v in value]
    return None


def _target(value):
    return GazeCalibration._target(value)


def _features(observation):
    try:
        values = observation.features
        if (len(values) == FEATURE_COUNT
                and all(not isinstance(v, bool) and math.isfinite(v) for v in values)):
            return tuple(float(v) for v in values)
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _auxiliary_features(observation):
    """The precision schema permits exactly six finite numeric values, never tensors."""
    try:
        values = observation.auxiliary_features
        if (observation.feature_schema == PRECISION_OBSERVATION_SCHEMA
                and isinstance(values, (tuple, list)) and len(values) == len(AUXILIARY_FEATURE_NAMES)
                and all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
                        for v in values)):
            return tuple(float(v) for v in values)
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _pairs(samples):
    """Keep malformed target entries counted as rejected instead of crashing UI."""
    result = []
    for pair in samples:
        try:
            observation, target = pair
        except (TypeError, ValueError):
            result.append((None, None))
            continue
        result.append((observation, _target(target)))
    return result


def diagnostic_prediction(calibration, observation) -> dict:
    """Display-only estimates. This must never be wired to desktop actions."""
    return _safe(calibration.diagnostic_prediction(observation))


def _point_stats(target, observations, calibration):
    estimates = [diagnostic_prediction(calibration, observation) for observation in observations]
    bounded = [item["bounded"] for item in estimates if item["bounded"] is not None]
    raw = [item["raw"] for item in estimates if item["raw"] is not None]
    features = [row for observation in observations if (row := _features(observation)) is not None]
    errors = [math.dist(prediction, target) for prediction in bounded]
    raw_errors = [math.dist(prediction, target) for prediction in raw]
    center = np.mean(bounded, axis=0) if bounded else None
    raw_center = np.mean(raw, axis=0) if raw else None
    # Match the validation report's RMS around median, not around the mean.
    jitter = (float(np.sqrt(np.mean(np.sum((np.asarray(bounded) - np.median(bounded, axis=0)) ** 2, axis=1))))
              if bounded else None)
    return {
        "target": list(target), "n": len(observations), "predicted_n": len(bounded),
        "predicted_mean": center.tolist() if center is not None else None,
        "bias_xy": (center - target).tolist() if center is not None else None,
        "mean_error": float(np.mean(errors)) if errors else None,
        "max_error": max(errors) if errors else None, "jitter": jitter,
        "rejected": len(observations) - len(bounded),
        "raw_predicted_mean": raw_center.tolist() if raw_center is not None else None,
        "raw_mean_error": float(np.mean(raw_errors)) if raw_errors else None,
        "raw_max_error": max(raw_errors) if raw_errors else None,
        "feature_median": np.median(features, axis=0).tolist() if features else None,
        "feature_range": np.ptp(features, axis=0).tolist() if features else None,
    }


def _phase(pairs, calibration):
    grouped = {}
    malformed = 0
    for observation, target in pairs:
        if target is None:
            malformed += 1
            continue
        grouped.setdefault(target, []).append(observation)
    points = [_point_stats(target, observations, calibration) for target, observations in grouped.items()]
    n = sum(point["predicted_n"] for point in points)
    valid_points = [point for point in points if point["predicted_n"]]
    summary = {
        "n": len(pairs), "target_count": len(points), "predicted_n": n,
        "rejected": malformed + sum(point["rejected"] for point in points),
        "mean_error": (sum(point["mean_error"] * point["predicted_n"] for point in valid_points) / n
                       if n else None),
        "max_error": max((point["max_error"] for point in valid_points), default=None),
        "jitter": max((point["jitter"] for point in valid_points), default=None),
        "target_balanced_mean_error": (float(np.mean([point["mean_error"] for point in valid_points]))
                                       if valid_points else None),
        "bias_xy": ([sum(point["bias_xy"][axis] * point["predicted_n"] for point in valid_points) / n
                     for axis in (0, 1)] if n else None),
    }
    return points, summary


def _feature_stats(pairs, reader=_features):
    rows = [features for observation, _ in pairs if (features := reader(observation)) is not None]
    if not rows:
        return None
    matrix = np.asarray(rows)
    return {"n": len(rows), "minimum": matrix.min(axis=0).tolist(), "maximum": matrix.max(axis=0).tolist(),
            "median": np.median(matrix, axis=0).tolist(), "range": np.ptp(matrix, axis=0).tolist()}


def _signal(points, calibration):
    medians = [point["feature_median"] for point in points if point["feature_median"] is not None]
    model = calibration.diagnostic_model()
    if getattr(calibration, "engine_id", LEGACY_ENGINE_ID) == LEGACY_ENGINE_ID:
        model["coefficient_feature_names"] = list(FEATURE_NAMES[:6])
        model["coefficient_units"] = "Normalized screen x/y per one feature unit; not physical eye angles"
    if not medians:
        return {"target_median_range": None, "iris_singular_values": None, "iris_condition_ratio": None,
                "model": model}
    matrix = np.asarray(medians)
    iris = (matrix[:, :2] + matrix[:, 2:4]) * .5
    singular = np.linalg.svd(iris - iris.mean(axis=0), compute_uv=False)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 1e-12 else None
    return {"target_median_range": np.ptp(matrix, axis=0).tolist(),
            "iris_singular_values": singular.tolist(), "iris_condition_ratio": condition, "model": model}


def _context(context):
    if not isinstance(context, Mapping):
        return {}
    result = {k: v for k, v in context.items() if k in CONTEXT_KEYS}
    pointer = context.get("pointer_filter")
    if (isinstance(pointer, Mapping) and pointer.get("id") == "ocular-one-euro-v1"
            and pointer.get("scope") == "output_only"):
        keys = ("min_cutoff", "beta", "derivative_cutoff", "jump_distance", "reset_gap_seconds")
        if all(isinstance(pointer.get(k), (int, float)) and not isinstance(pointer[k], bool)
               and math.isfinite(pointer[k]) and 0 <= pointer[k] <= 100 for k in keys):
            result["pointer_filter"] = {"id": pointer["id"], "scope": pointer["scope"],
                                        **{k: pointer[k] for k in keys}}
    monitor = context.get("monitor")
    if isinstance(monitor, Mapping):
        result["monitor"] = {k: v for k, v in monitor.items() if k in ("width", "height", "left", "top")}
    telemetry = context.get("telemetry")
    if isinstance(telemetry, Mapping):
        result["telemetry"] = {section: {k: v for k, v in values.items() if k in TELEMETRY_KEYS[section]}
                               for section, values in telemetry.items()
                               if section in TELEMETRY_KEYS and isinstance(values, Mapping)}
        worker = result["telemetry"].get("worker", {})
        if "neural_features" in worker:
            neural = worker["neural_features"]
            if not (isinstance(neural, (list, tuple)) and len(neural) == 6
                    and all(not isinstance(value, bool) and isinstance(value, (int, float))
                            and math.isfinite(value) for value in neural)):
                worker.pop("neural_features")
    return result


def _hypotheses(training, validation, limits):
    """Evidence-linked descriptions, intentionally no asserted physical cause."""
    notes = ["Orientativo: estos datos no identifican por sí solos una causa ni prueban reflejos, lentes o iluminación."]
    if not validation["n"]:
        notes.append("Todavía no hay muestras independientes de comprobación.")
        return notes
    if validation["rejected"]:
        notes.append("Hay estimaciones bloqueadas o muestras inválidas; las métricas calculables no incluyen esos rechazos.")
    train_error, val_error, jitter = training["mean_error"], validation["mean_error"], validation["jitter"]
    if val_error is not None and val_error > limits["mean_error"]:
        if jitter is not None and jitter <= limits["mean_error"]:
            notes.append("En estas muestras predomina el desfase de posición sobre la dispersión; no demuestra que movieras mal los ojos.")
        if train_error is not None and train_error <= limits["mean_error"]:
            notes.append("El ajuste reproduce mejor los puntos aprendidos que los nuevos: revisar generalización, señal ocular y cambios entre fases.")
        elif train_error is not None:
            notes.append("También hay error al reproducir los puntos aprendidos: revisar representación ocular, muestras y ajuste antes de atribuirlo al usuario.")
    if jitter is not None and jitter > limits["mean_error"]:
        notes.append("Hay dispersión entre fotogramas del mismo objetivo; comparar estabilidad, tiempos de captura y calidad de señal.")
    notes.append("El error de entrenamiento reutiliza muestras aprendidas y no sustituye la comprobación independiente.")
    return notes


def _export_samples(training, validation, *, precision=False):
    stamped = [o.timestamp for o, _ in training + validation
               if isinstance(o, GazeObservation) and not isinstance(o.timestamp, bool)
               and isinstance(o.timestamp, (int, float)) and math.isfinite(o.timestamp)]
    start = min(stamped, default=0.0)
    result = []
    for phase, pairs in (("training", training), ("validation", validation)):
        for observation, target in pairs:
            if not isinstance(observation, GazeObservation):
                continue
            stamp = observation.timestamp
            relative = (stamp - start if not isinstance(stamp, bool) and isinstance(stamp, (int, float))
                        and math.isfinite(stamp) else None)
            row = {"phase": phase, "target": target, "t_seconds": relative,
                   "features": _features(observation), "valid": observation.valid is True,
                   "reason": observation.reason if isinstance(observation.reason, str) else ""}
            if precision:
                row["auxiliary_features"] = _auxiliary_features(observation)
            result.append(row)
    return result


def build_diagnostic_report(calibration, validation_samples, *, capture_points=(), context=None,
                            include_samples=False) -> dict:
    """Build a detached report without modifying the fitted model or its gate.

    The caller owns saving/export consent. ``context`` is allow-listed config;
    unrecognized keys (including paths, images, names and absolute timestamps)
    are dropped. Reports never persist anything themselves.
    """
    engine_id = getattr(calibration, "engine_id", LEGACY_ENGINE_ID)
    if engine_id != LEGACY_ENGINE_ID and engine_id not in PRECISION_ENGINE_IDS:
        raise ValueError("Motor ocular de diagnóstico no compatible")
    precision = engine_id in PRECISION_ENGINE_IDS
    if precision and getattr(calibration, "observation_schema", None) != PRECISION_OBSERVATION_SCHEMA:
        raise ValueError("Esquema ocular de precisión no compatible")
    training = _pairs(calibration.training_samples)
    validation = _pairs(validation_samples)
    training_points, train_summary = _phase(training, calibration)
    validation_points, val_summary = _phase(validation, calibration)
    train_features, val_features = _feature_stats(training), _feature_stats(validation)
    features = []
    for index, name in enumerate(FEATURE_NAMES):
        row = {"name": name, "index": index}
        for phase, stats in (("training", train_features), ("validation", val_features)):
            row[phase] = ({field: values[index] for field, values in stats.items() if field != "n"}
                          if stats else None)
        row["median_shift"] = (val_features["median"][index] - train_features["median"][index]
                               if train_features and val_features else None)
        features.append(row)
    limits = {"mean_error": calibration.mean_error_limit, "max_error": calibration.max_error_limit}
    result = {
        "schema_version": 2 if precision else 1, "app_version": __version__, "diagnostic_only": True,
        "metric_space": "Euclidean normalized monitor coordinates; not pixels, degrees or accuracy percentage",
        "privacy": "Local numeric diagnostics only; no images, video, identity or absolute timestamps",
        "limits": limits, "fitted": calibration.fitted, "ready": calibration.ready,
        "acceptance_report": asdict(calibration.report),
        "training": training_points, "validation": validation_points,
        "summary": {"training": train_summary, "validation": val_summary},
        "features": features, "posture": features[4:],
        "signal": _signal(training_points, calibration),
        "hypotheses": _hypotheses(train_summary, val_summary, limits),
        "capture_points": [{k: v for k, v in point.items() if k in CAPTURE_KEYS}
                           for point in capture_points if isinstance(point, Mapping)],
        "context": _context(context),
        "samples_included": include_samples is True,
    }
    if precision:
        result["engine_id"] = engine_id
        result["observation_schema"] = PRECISION_OBSERVATION_SCHEMA
        result["auxiliary_features"] = []
        extra_train = _feature_stats(training, _auxiliary_features)
        extra_val = _feature_stats(validation, _auxiliary_features)
        for index, name in enumerate(AUXILIARY_FEATURE_NAMES):
            row = {"name": name, "index": index,
                   "units": "unit_vector_component" if index < 3 else "radians"}
            for phase, stats in (("training", extra_train), ("validation", extra_val)):
                row[phase] = ({field: values[index] for field, values in stats.items() if field != "n"}
                              if stats else None)
            row["median_shift"] = (extra_val["median"][index] - extra_train["median"][index]
                                   if extra_train and extra_val else None)
            result["auxiliary_features"].append(row)
    if include_samples is True:
        result["samples"] = _export_samples(training, validation, precision=precision)
    return _safe(result)
