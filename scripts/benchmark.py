"""Synthetic benchmark. No camera, mouse controller or keyboard controller."""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biogesture import __version__  # noqa: E402
from biogesture.models import HandSample, Landmark  # noqa: E402
from biogesture.settings import Settings  # noqa: E402


def synthetic_sample(index: int) -> HandSample:
    """Representative 2D poses, not a physical detection accuracy dataset."""
    center_x = 0.5 + math.sin(index / 80) * 0.1
    coordinates = [(0.0, 0.22), (-0.05, 0.17), (-0.09, 0.10), (-0.15, 0.06), (-0.19, 0.02)]
    pose = (index // 30) % 3
    for finger, origin_x in enumerate((-0.06, 0.0, 0.06, 0.12)):
        if pose == 0 or finger == 0:
            coordinates.extend([(origin_x, 0.05), (origin_x, -0.02), (origin_x, -0.09), (origin_x, -0.16)])
        else:
            coordinates.extend([(origin_x, 0.05), (origin_x, 0.02), (origin_x, 0.10), (origin_x, 0.15)])
    if pose == 2:
        coordinates[4] = (coordinates[8][0] - 0.005, coordinates[8][1])
    landmarks = tuple(Landmark(center_x + x, 0.45 + y) for x, y in coordinates)
    return HandSample(timestamp=index / 30.0 + 1.0, landmarks=landmarks)


def summarize(durations: list[float]) -> dict:
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]
    return {"iterations": len(durations), "mean_ms": statistics.mean(durations) * 1000,
            "p50_ms": statistics.median(durations) * 1000, "p95_ms": p95 * 1000,
            "max_ms": max(durations) * 1000}


def benchmark_engine(iterations: int) -> dict:
    from biogesture.gestures import GestureEngine

    engine = GestureEngine(Settings(start_paused=False))
    engine.set_paused(False)
    durations = []
    event_count = 0
    states = set()
    for index in range(iterations + 100):
        sample = synthetic_sample(index)
        started = time.perf_counter()
        output = engine.update(sample, sample.timestamp)
        duration = time.perf_counter() - started
        if index >= 100:
            durations.append(duration)
            event_count += len(output.events)
            states.add(output.state)
    return {"kind": "synthetic_gesture_engine", **summarize(durations),
            "generated_events_not_executed": event_count, "observed_states": sorted(states),
            "interpretation": "Tiempo del motor con coordenadas sintéticas; excluye cámara, MediaPipe, interfaz y respuesta real."}


def benchmark_blank_detector(iterations: int) -> dict:
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    model_path = ROOT / "assets" / "models" / "hand_landmarker.task"
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO, num_hands=1,
    )
    durations = []
    frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((480, 640, 3), dtype=np.uint8))
    with vision.HandLandmarker.create_from_options(options) as detector:
        for index in range(iterations + 10):
            started = time.perf_counter()
            detector.detect_for_video(frame, (index + 1) * 34)
            duration = time.perf_counter() - started
            if index >= 10:
                durations.append(duration)
    return {"kind": "blank_frame_detector", **summarize(durations),
            "frame_size": [640, 480], "hands": 0,
            "interpretation": "Inferencia de cuadros negros sin manos; no representa seguimiento real ni latencia completa."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--detector", action="store_true", help="Además, procesa cuadros negros con el modelo local")
    parser.add_argument("--detector-iterations", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1_000_000 or not 1 <= args.detector_iterations <= 1000:
        parser.error("iterations debe estar entre 1 y 1000000; detector-iterations entre 1 y 1000")
    reports = [benchmark_engine(args.iterations)]
    if args.detector:
        reports.append(benchmark_blank_detector(args.detector_iterations))
    print(json.dumps({"version": __version__, "platform": platform.platform(),
                      "python": platform.python_version(), "camera_opened": False, "input_sent": False,
                      "benchmarks": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

