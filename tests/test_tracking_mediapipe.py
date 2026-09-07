"""Opt-in real-model test using generated frames, never webcam or desktop input.

Run with BIOGESTURE_TEST_MEDIAPIPE=1 in the prepared development environment.
Blank asymmetric images verify callbacks and preview orientation, not hand accuracy.
"""

from collections import deque
import json
import os
from pathlib import Path
import shutil
import threading
import time
import unittest

import pytest

from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline


class SyntheticCapturePipeline(TrackingPipeline):
    def __init__(self, mirror=True, model_path=None):
        super().__init__(Settings(mirror=mirror, capture_width=320, capture_height=240,
                                  capture_fps=30, detection_fps=30),
                         model_path or Path(__file__).resolve().parents[1] / "assets/models/hand_landmarker.task")
        self.results = deque(maxlen=32)
        self.callback_times = deque(maxlen=32)
        self.capture_released = threading.Event()

    def _capture_loop(self):
        import numpy as np
        rgb = np.zeros((240, 320, 3), dtype=np.uint8)
        rgb[:, :160, 0] = 96
        rgb[:, 160:, 2] = 192
        self.capture_released.clear()
        try:
            while not self._stop.is_set():
                self._offer_frame(rgb.copy(), time.monotonic())
                self._stop.wait(1 / self.settings.capture_fps)
        finally:
            self.capture_released.set()

    def _on_result(self, result, image, timestamp_ms):
        super()._on_result(result, image, timestamp_ms)
        with self._condition:
            packet = self._packet
            if packet is not None and packet.rgb is not None and not self._stop.is_set():
                if not self.results or packet.sequence != self.results[-1].sequence:
                    self.results.append(packet)
                    self.callback_times.append(timestamp_ms)
                    self._condition.notify_all()

    def await_results(self, count, timeout=20):
        with self._condition:
            self._condition.wait_for(
                lambda: len(self.results) >= count or (self._packet is not None and self._packet.error),
                timeout=timeout)
            return list(self.results)


@unittest.skipUnless(os.environ.get("BIOGESTURE_TEST_MEDIAPIPE") == "1", "Integración MediaPipe opt-in")
class RealMediaPipeTests(unittest.TestCase):
    def test_real_live_stream_multiple_callbacks_mirror_and_clean_stop(self):
        for mirror in (True, False):
            with self.subTest(mirror=mirror):
                pipeline = SyntheticCapturePipeline(mirror)
                pipeline.start()
                try:
                    packets = pipeline.await_results(5)
                    self.assertGreaterEqual(len(packets), 5, str(pipeline.latest()))
                    self.assertTrue(all(p.error is None and p.status == "SIN DETECCIÓN" for p in packets))
                    self.assertTrue(all(p.sample is None and p.auxiliary is None for p in packets))
                    self.assertTrue(all(p.rgb.shape == (240, 320, 3) for p in packets))
                    self.assertTrue(all(a.captured_at < b.captured_at for a, b in zip(packets, packets[1:])))
                    self.assertTrue(all(a < b for a, b in zip(pipeline.callback_times, list(pipeline.callback_times)[1:])))
                    self.assertTrue(all(p.completed_at >= p.captured_at for p in packets))
                    first_pixel = tuple(int(c) for c in packets[-1].rgb[0, 0])
                    self.assertEqual(first_pixel, (96, 0, 0) if mirror else (0, 0, 192))
                finally:
                    began = time.monotonic()
                    self.assertTrue(pipeline.stop(timeout=2), "El cierre del modelo real agotó el plazo")
                    self.assertLess(time.monotonic() - began, 2.5)
                self.assertTrue(pipeline.capture_released.is_set())
                self.assertFalse(pipeline.running)
                self.assertIsNone(pipeline.latest().sample)
                self.assertIsNone(pipeline.latest().rgb)
                self.assertEqual(pipeline.latest().status, "DETENIDO")

    def test_real_pipeline_can_restart_only_after_clean_stop(self):
        pipeline = SyntheticCapturePipeline()
        previous_timestamp = 0
        for _ in range(2):
            pipeline.results.clear()
            pipeline.callback_times.clear()
            pipeline.start()
            try:
                packets = pipeline.await_results(3)
                self.assertGreaterEqual(len(packets), 3, str(pipeline.latest()))
                self.assertGreater(pipeline.callback_times[0], previous_timestamp)
                previous_timestamp = pipeline.callback_times[-1]
            finally:
                self.assertTrue(pipeline.stop(timeout=2))
            self.assertFalse(pipeline.running)


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_MEDIAPIPE") != "1", reason="Integración MediaPipe opt-in")
def test_real_image_and_live_stream_load_model_from_unicode_path(tmp_path):
    from biogesture.detector_smoke import run_detector_smoke
    from biogesture.startup import MODEL_SHA256

    source = Path(__file__).resolve().parents[1] / "assets/models/hand_landmarker.task"
    model = tmp_path / "Prueba portable á 日本語" / "modelo ñ.task"
    model.parent.mkdir()
    shutil.copyfile(source, model)
    report_path = model.parent / "detector-smoke.json"
    assert run_detector_smoke(model, MODEL_SHA256, report_path) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True and report["frames"] == 1 and report["detected_hands"] == 0
    assert report["model_sha256"] == MODEL_SHA256
    pipeline = SyntheticCapturePipeline(model_path=model)
    pipeline.start()
    try:
        packets = pipeline.await_results(3)
        assert len(packets) >= 3, str(pipeline.latest())
        assert all(packet.error is None for packet in packets)
        assert all(packet.sample is None and packet.auxiliary is None for packet in packets)
    finally:
        assert pipeline.stop(timeout=2)
    assert pipeline.capture_released.is_set()
    assert not pipeline.running


if __name__ == "__main__":
    unittest.main()
