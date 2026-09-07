"""Packaged inference probe: one synthetic image, no camera, Tk or system input."""

import hashlib
import json
import logging
from pathlib import Path
import platform
import sys

from . import __version__


def run_detector_smoke(model_path: Path, expected_sha256: str, report_path: Path, *, console=False) -> int:
    """Write a small non-identifying report and return 0 only after detector close.

    The invoking build verifier owns the process timeout. Keeping inference in
    this process avoids introducing another thread around native detector calls.
    """
    report = {"version": __version__, "platform": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "model_sha256": None,
              "ok": False, "frames": 0, "detected_hands": None, "error": None}
    try:
        model_buffer = Path(model_path).read_bytes()
        report["model_sha256"] = hashlib.sha256(model_buffer).hexdigest()
        if report["model_sha256"] != expected_sha256:
            raise ValueError("El modelo de seguimiento no coincide con el aprobado")
        import mediapipe as mp
        import numpy as np
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model_buffer),
            running_mode=mp.tasks.vision.RunningMode.IMAGE, num_hands=2,
        )
        frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((480, 640, 3), dtype=np.uint8))
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
            result = detector.detect(frame)
            report["frames"] = 1
            report["detected_hands"] = len(result.hand_landmarks)
        report["ok"] = True
        logging.info("Prueba sintética del detector completada")
    except Exception as exc:
        # Exception messages from native libraries may contain machine/user
        # paths. Keep them in the private log, never in the shareable JSON.
        report["error"] = type(exc).__name__
        logging.exception("Falló la prueba sintética del detector")
    try:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        logging.exception("No se pudo escribir el informe sintético del detector")
        return 1
    if console and sys.stdout is not None:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1
