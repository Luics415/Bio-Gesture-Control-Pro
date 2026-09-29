"""Replay an explicitly exported calibration with no camera, GUI or OS input.

Usage: python -m biogesture.gaze_replay path/to/mirada-test.json [--json]
Only JSON measurements are accepted; no objects, executable code or model
files are loaded from the report. Replays never activate a live gaze session.
"""

import argparse
import json
import math
from pathlib import Path

from .gaze import FEATURE_COUNT, GazeCalibration, GazeObservation
from .gaze_diagnostics import (LEGACY_ENGINE_ID, PRECISION_ENGINE_IDS, PRECISION_OBSERVATION_SCHEMA,
                               build_diagnostic_report)
from .gaze_export import MAX_EXPORT_BYTES


MAX_SAMPLES = 10000


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def replay_diagnostic(payload):
    """Recreate training and held-out evaluation in their original order."""
    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload["schema_version"] not in (1, 2)):
        raise ValueError("Formato de diagnóstico no compatible; se necesita schema_version 1 o 2")
    precision = payload["schema_version"] == 2
    if precision:
        if (payload.get("engine_id") not in PRECISION_ENGINE_IDS
                or payload.get("observation_schema") != PRECISION_OBSERVATION_SCHEMA):
            raise ValueError("Motor o esquema ocular de precisión no compatible")
    elif (payload.get("engine_id", LEGACY_ENGINE_ID) != LEGACY_ENGINE_ID
          or payload.get("observation_schema", "iris10-v1") != "iris10-v1"):
        raise ValueError("El esquema 1 solo admite el motor ocular heredado")
    rows = payload.get("samples")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_SAMPLES:
        raise ValueError("Se necesitan entre 1 y 10000 muestras numéricas exportadas")
    limits = payload.get("limits", {})
    if not isinstance(limits, dict):
        raise ValueError("Límites de calibración inválidos")
    mean_limit, max_limit = limits.get("mean_error", .04), limits.get("max_error", .08)
    if not all(_number(v) for v in (mean_limit, max_limit)):
        raise ValueError("Límites de calibración inválidos")
    if precision:
        # Closed, local registry. Reports cannot name Python modules, files,
        # pickles or executable model objects. No inference model is loaded.
        from .gaze_precision import create_gaze_calibration
        calibration = create_gaze_calibration(payload["engine_id"],
                                              mean_error_limit=mean_limit, max_error_limit=max_limit)
    else:
        calibration = GazeCalibration(mean_error_limit=mean_limit, max_error_limit=max_limit)
    validation = []
    validation_started = False
    previous = -math.inf
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Muestra inválida")
        phase, stamp, features, target = (row.get(k) for k in ("phase", "t_seconds", "features", "target"))
        if (phase not in ("training", "validation") or not _number(stamp) or stamp < 0
                or stamp <= previous or type(row.get("valid")) is not bool):
            raise ValueError("Fase o tiempo de muestra inválidos; no se reordenan capturas")
        previous = stamp
        if (not isinstance(target, list) or len(target) != 2
                or not all(_number(v) and 0 <= v <= 1 for v in target)):
            raise ValueError("Objetivo de muestra inválido")
        if features is None and row["valid"] is False:
            features = []
        elif (not isinstance(features, list) or len(features) != FEATURE_COUNT
              or not all(_number(v) for v in features)):
            raise ValueError("Características de muestra inválidas")
        extra = {}
        if precision:
            auxiliary = row.get("auxiliary_features")
            if auxiliary is None and row["valid"] is False:
                auxiliary = []
            elif (not isinstance(auxiliary, list) or len(auxiliary) != 6
                  or not all(_number(v) for v in auxiliary)):
                raise ValueError("Se necesitan seis características oculares auxiliares finitas")
            extra = {"auxiliary_features": tuple(auxiliary), "feature_schema": PRECISION_OBSERVATION_SCHEMA}
        elif "auxiliary_features" in row and row["auxiliary_features"] not in (None, []):
            raise ValueError("El esquema 1 no admite características oculares auxiliares")
        observation = GazeObservation(float(stamp), tuple(features), row["valid"],
                                      "Muestra inválida exportada" if not row["valid"] else "", **extra)
        if phase == "training":
            if validation_started or not calibration.add_sample(observation, tuple(target)):
                raise ValueError("Entrenamiento inválido o mezclado con comprobación")
        else:
            validation_started = True
            validation.append((observation, tuple(target)))
    if calibration.fit() and validation:
        calibration.validate(validation)
    result = build_diagnostic_report(calibration, validation)
    result["replay"] = {"source_app_version": str(payload.get("app_version", "desconocida"))[:40],
                        "camera_opened": False, "desktop_input_enabled": False}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reanalizar mediciones oculares locales sin cámara ni controlar la PC")
    parser.add_argument("report", type=Path, help="Archivo mirada-*.json exportado desde la calibración")
    parser.add_argument("--json", action="store_true", help="Mostrar el informe numérico completo")
    args = parser.parse_args(argv)
    try:
        with args.report.open("rb") as source:
            content = source.read(MAX_EXPORT_BYTES + 1)
        if len(content) > MAX_EXPORT_BYTES:
            raise ValueError("Archivo demasiado grande")
        result = replay_diagnostic(json.loads(content))
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
        parser.exit(2, f"No se pudo reproducir el diagnóstico: {exc}\n")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    else:
        print("Reproducción local: sin cámara, sin entradas al escritorio y sin activar el control.")
        print(json.dumps(result.get("summary", {}), ensure_ascii=False, allow_nan=False, indent=2))
        for hint in result.get("hypotheses", []):
            print(f"- {hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
