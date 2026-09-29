"""Frozen/source ocular inference probe. Generated pixels only; no input/camera.

This checks distribution mechanics, not physical gaze accuracy. The bounded
caller owns timeout; no calibration is saved or approved by this probe.
"""

from contextlib import ExitStack
import hashlib
import json
import logging
import math
from pathlib import Path
import platform
import socket
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

from . import __version__
from .gaze_neural import FACE_OVAL, MODEL_ASSETS, NeuralGazeExtractor


def synthetic_inputs():
    """Synthetic geometry and colored pixels, never a photo or webcam image."""
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :320, 0] = 255
    frame[:, 320:, 1] = 128
    points = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for j, index in enumerate(FACE_OVAL):
        angle = j * 2 * math.pi / len(FACE_OVAL)
        points[index] = SimpleNamespace(x=.5 + .25 * math.sin(angle), y=.5 - .3 * math.cos(angle))
    for index, x in ((33, .30), (133, .38), (362, .62), (263, .70)):
        points[index] = SimpleNamespace(x=x, y=.4)
    return frame, points


def probe_face_model(model_path):
    from .face_tracking import FACE_MODEL_SHA256
    import mediapipe as mp
    import numpy as np
    model = Path(model_path).read_bytes()
    digest = hashlib.sha256(model).hexdigest()
    if digest != FACE_MODEL_SHA256:
        raise ValueError("El modelo facial no coincide con el aprobado")
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_buffer=model),
        running_mode=mp.tasks.vision.RunningMode.IMAGE, num_faces=1,
        output_face_blendshapes=False, output_facial_transformation_matrixes=False,
    )
    frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((480, 640, 3), dtype=np.uint8))
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        count = len(detector.detect(frame).face_landmarks)
    if count:
        raise ValueError("Detección facial inesperada en el cuadro vacío")
    return {"frames": 1, "detected_faces": count, "model_sha256": digest}


def run_gaze_smoke(model_directory, report_path, *, console=False):
    report = {"version": __version__, "platform": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "frozen": bool(getattr(sys, "frozen", False)),
              "ok": False, "frames": 0, "error": None, "network_attempts": 0,
              "converter_loaded": False, "telemetry_loaded": False, "models_sha384": {},
              "camera_opened": False, "system_input": False, "accuracy_validation": "not_measured"}
    extractor = None

    def deny_network(*args, **kwargs):
        report["network_attempts"] += 1
        raise RuntimeError("La prueba ocular no permite conexiones de red")

    try:
        with ExitStack() as guards:
            for owner, attribute in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                                     (socket.socket, "sendto"), (socket, "getaddrinfo")):
                guards.enter_context(patch.object(owner, attribute, deny_network))
            model_directory = Path(model_directory)
            report["face_detector"] = probe_face_model(model_directory / "face_landmarker.task")
            extractor = NeuralGazeExtractor(model_directory / "gaze-precision")
            from openvino.runtime import get_version
            report["runtime"] = get_version()
            # Constructor has verified all four byte buffers before loading.
            report["models_sha384"] = {asset.filename: asset.sha384 for asset in MODEL_ASSETS}
            frame, points = synthetic_inputs()
            elapsed = []
            for _ in range(3):
                started = time.perf_counter()
                values = extractor.extract(frame, points)
                elapsed.append((time.perf_counter() - started) * 1000)
                if (len(values) != 6 or not all(math.isfinite(v) for v in values)
                        or abs(math.sqrt(sum(v*v for v in values[:3])) - 1) > 1e-5):
                    raise ValueError("El modelo ocular no produjo una dirección finita unitaria")
                report["frames"] += 1
            report["inference_ms"] = elapsed
            report["features"] = len(values)
            report["unit_vector_norm"] = math.sqrt(sum(v*v for v in values[:3]))
            extractor.close()
            extractor = None
            report["converter_loaded"] = any(n == "openvino.tools.ovc" or n.startswith("openvino.tools.ovc.")
                                               for n in tuple(sys.modules))
            report["telemetry_loaded"] = any(n == "openvino_telemetry" or n.startswith("openvino_telemetry.")
                                               for n in tuple(sys.modules))
            if report["network_attempts"] or report["converter_loaded"] or report["telemetry_loaded"]:
                raise RuntimeError("La prueba no confirmó el motor exclusivamente local")
            report["ok"] = True
    except Exception as exc:
        report["error"] = type(exc).__name__
        logging.exception("Falló la prueba sintética ocular")
    finally:
        if extractor is not None:
            extractor.close()
    try:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        logging.exception("No se pudo escribir el informe sintético ocular")
        return 1
    if console and sys.stdout is not None:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1
