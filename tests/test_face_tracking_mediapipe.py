"""Optional native model verification; generated frames, no camera or OS input."""

import hashlib
import os
from pathlib import Path
import time

import numpy as np
import pytest

from biogesture.face_tracking import FACE_MODEL_SHA256, FaceTrackingWorker
from biogesture.settings import Settings
from tests.test_tracking_mediapipe import SyntheticCapturePipeline


MODEL = Path(__file__).resolve().parents[1] / "assets/models/face_landmarker.task"


def test_bundled_face_model_is_the_reviewed_official_version():
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == FACE_MODEL_SHA256


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_MEDIAPIPE") != "1", reason="Modelo real opt-in, sin webcam")
@pytest.mark.parametrize("engine", ["legacy-ridge-v1", "precision-openvino-v1", "precision-openvino-v2"])
def test_native_face_model_loads_unicode_path_and_rejects_blank_frame(tmp_path, engine):
    if engine != "legacy-ridge-v1" and os.environ.get("BIOGESTURE_TEST_OPENVINO") != "1":
        pytest.skip("OpenVINO nativo opt-in")
    model = tmp_path / "Prueba á 日本語" / "ojos.task"
    model.parent.mkdir()
    model.write_bytes(MODEL.read_bytes())
    if engine != "legacy-ridge-v1":
        from biogesture.gaze_neural import MODEL_ASSETS
        destination = model.parent / "gaze-precision"
        destination.mkdir()
        for asset in MODEL_ASSETS:
            (destination / asset.filename).write_bytes((MODEL.parent / "gaze-precision" / asset.filename).read_bytes())
    worker = FaceTrackingWorker(Settings(cursor_mode="eyes", gaze_engine=engine), model)
    worker.start()
    try:
        deadline = time.monotonic() + 12
        while worker.latest() is None and time.monotonic() < deadline:
            worker.offer(np.zeros((480, 640, 3), dtype=np.uint8), time.monotonic())
            time.sleep(.04)
        observation = worker.latest()
        assert observation is not None
        assert not observation.valid and observation.reason == "Ojos no visibles"
    finally:
        assert worker.stop(timeout=2)
    assert not worker.running and worker.latest() is None


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_MEDIAPIPE") != "1", reason="Dos modelos reales opt-in, sin webcam")
@pytest.mark.parametrize("engine", ["legacy-ridge-v1", "precision-openvino-v1", "precision-openvino-v2"])
def test_real_hands_and_eyes_share_capture_without_blocking_each_other(engine):
    if engine != "legacy-ridge-v1" and os.environ.get("BIOGESTURE_TEST_OPENVINO") != "1":
        pytest.skip("OpenVINO nativo opt-in")
    pipeline = SyntheticCapturePipeline()
    pipeline.settings.cursor_mode = "eyes"
    pipeline.settings.gaze_engine = engine
    pipeline.start()
    try:
        packets = pipeline.await_results(8, timeout=15)
        assert len(packets) >= 8
        assert not any(packet.error for packet in packets)
        deadline = time.monotonic() + 8
        while pipeline.latest_gaze() is None and time.monotonic() < deadline:
            time.sleep(.04)
        assert pipeline.latest_gaze() is not None
        assert pipeline.latest_gaze().reason == "Ojos no visibles"
        pipeline.set_resting(True)
        assert pipeline._face_worker._resting
        pipeline.set_resting(False)
        assert not pipeline._face_worker._resting
    finally:
        assert pipeline.stop(timeout=3)
    assert pipeline.capture_released.is_set() and not pipeline.running
