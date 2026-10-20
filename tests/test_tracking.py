from pathlib import Path
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock, patch

from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline, _Frame
from tests.test_gestures import hand


class FakeRGB:
    shape = (480, 640, 3)

    def __init__(self, reversed=False):
        self.reversed = reversed

    def __getitem__(self, key):
        return FakeRGB(not self.reversed)

    def copy(self):
        return self


def result():
    points = hand("pointer").landmarks
    return SimpleNamespace(
        hand_landmarks=[[SimpleNamespace(x=p.x - 0.3, y=p.y - 0.45, z=p.z) for p in points]],
        handedness=[[SimpleNamespace(category_name="Right", score=0.99)]])


class FakeDetector:
    def __init__(self):
        self.closed = False
        self.calls = []
        self.submitted = threading.Event()

    def detect_async(self, image, timestamp):
        self.calls.append(timestamp)
        self.submitted.set()

    def close(self):
        self.closed = True


class FakePipeline(TrackingPipeline):
    def __init__(self):
        super().__init__(Settings(), Path("not-used.task"))
        self.detector = FakeDetector()
        self.capture_released = threading.Event()

    def _make_detector(self):
        return self.detector

    def _image(self, rgb):
        return rgb

    def _capture_loop(self):
        try:
            self._offer_frame(FakeRGB(), time.monotonic())
            self._stop.wait()
        finally:
            self.capture_released.set()


class TrackingTests(unittest.TestCase):
    def test_model_loader_passes_original_bytes_not_a_native_unicode_path(self):
        pipeline = TrackingPipeline(Settings(), Path("Portable á 日本語/modelo ñ.task"))
        pipeline.model_path = Mock()
        pipeline.model_path.is_file.return_value = True
        pipeline.model_path.read_bytes.return_value = b"original-model-bytes"
        detector = Mock()
        base_options = Mock()
        options = Mock()
        factory = Mock(return_value=detector)
        mp = SimpleNamespace(tasks=SimpleNamespace(BaseOptions=base_options, vision=SimpleNamespace(
            HandLandmarkerOptions=options, RunningMode=SimpleNamespace(LIVE_STREAM="LIVE_STREAM"),
            HandLandmarker=SimpleNamespace(create_from_options=factory))))
        with patch.dict("sys.modules", {"mediapipe": mp}):
            self.assertIs(pipeline._make_detector(), detector)
        base_options.assert_called_once_with(model_asset_buffer=b"original-model-bytes")
        pipeline.model_path.read_bytes.assert_called_once()
        self.assertEqual(options.call_args.kwargs["num_hands"], 2)
        self.assertEqual(options.call_args.kwargs["running_mode"], "LIVE_STREAM")

    def test_capture_slot_replaces_unsent_frames(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        for n in range(100):
            pipeline._offer_frame(FakeRGB(), n)
        self.assertEqual(pipeline._pending.timestamp, 99)
        self.assertEqual(pipeline._metrics["dropped_frames"], 99)
        self.assertIsNone(pipeline.latest())

    def test_callback_keeps_capture_timestamp_and_physical_hand(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        now = time.monotonic()
        for index, delta in enumerate((-0.4, -0.3, -0.2, 0)):
            pipeline._inflight = (123 + index, _Frame(now + delta, FakeRGB(), 0), now)
            pipeline._on_result(result(), None, 123 + index)
        packet = pipeline.latest()
        self.assertEqual(packet.sample.timestamp, now)
        self.assertEqual(packet.sample.handedness, "Right")
        self.assertEqual(packet.sample.landmarks[0].x, 0.2)
        self.assertEqual(packet.rgb.shape, (480, 640, 3))
        self.assertIs(packet, pipeline.latest())  # Snapshot, not a destructive queue pop.

    def test_nonmirrored_view_changes_coordinates_but_not_physical_hand(self):
        pipeline = TrackingPipeline(Settings(mirror=False), Path("unused"))
        now = time.monotonic()
        for index, delta in enumerate((-0.4, -0.3, -0.2, 0)):
            pipeline._inflight = (123 + index, _Frame(now + delta, FakeRGB(), 0), now)
            pipeline._on_result(result(), None, 123 + index)
        packet = pipeline.latest()
        self.assertEqual(packet.sample.handedness, "Right")
        self.assertAlmostEqual(packet.sample.landmarks[0].x, 0.8)
        self.assertTrue(packet.rgb.reversed)

    def test_camera_loss_rejects_late_landmarks_and_clears_image(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        now = time.monotonic()
        pipeline._inflight = (123, _Frame(now, FakeRGB(), 0), now)
        pipeline._invalidate_camera("unplugged")
        packet = pipeline.latest()
        pipeline._on_result(result(), None, 123)
        self.assertIs(pipeline.latest(), packet)
        self.assertIsNone(packet.sample)
        self.assertIsNone(packet.rgb)
        self.assertEqual(packet.status, "RECONECTANDO CÁMARA")

    def test_single_inflight_and_normal_cleanup(self):
        pipeline = FakePipeline()
        pipeline.start()
        try:
            self.assertTrue(pipeline.detector.submitted.wait(1))
            for _ in range(100):
                pipeline._offer_frame(FakeRGB(), time.monotonic())
            self.assertEqual(len(pipeline.detector.calls), 1)
            pipeline._on_result(result(), None, pipeline.detector.calls[0])
            self.assertIsNotNone(pipeline.latest().rgb)
            self.assertIsNotNone(pipeline.latest().sample)
            self.assertEqual(pipeline.latest().status, "PRINCIPAL")
        finally:
            self.assertTrue(pipeline.stop())
        self.assertTrue(pipeline.detector.closed)
        self.assertTrue(pipeline.capture_released.is_set())
        self.assertIsNone(pipeline.latest().sample)

    def test_stop_timeout_prevents_restart_until_worker_returns(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        unblock = threading.Event()
        pipeline._worker = threading.Thread(target=unblock.wait)
        pipeline._worker.start()
        try:
            self.assertFalse(pipeline.stop(timeout=0.001))
            with self.assertRaises(RuntimeError):
                pipeline.start()
        finally:
            unblock.set()
            pipeline._worker.join(1)
        self.assertTrue(pipeline.stop())

    def test_missing_model_produces_observable_error_without_opening_camera(self):
        pipeline = TrackingPipeline(Settings(), Path("definitely-missing-model.task"))
        pipeline._capture_loop = Mock()
        with self.assertLogs(level="ERROR"):
            pipeline._run()
        self.assertIn("Falta el modelo", pipeline.latest().error)
        pipeline._capture_loop.assert_not_called()

    def test_backend_fallback_releases_failed_camera_and_records_negotiation(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        failed, good = Mock(), Mock()
        failed.isOpened.return_value = True
        failed.read.return_value = (False, None)
        good.isOpened.return_value = True
        good.read.return_value = (True, FakeRGB())
        good.get.return_value = 25.0
        cv2 = SimpleNamespace(CAP_DSHOW=700, CAP_MSMF=1400, CAP_PROP_FOURCC=6,
                              CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4,
                              CAP_PROP_FPS=5, CAP_PROP_BUFFERSIZE=38,
                              VideoWriter_fourcc=Mock(return_value=1),
                              VideoCapture=Mock(side_effect=[failed, good]))
        cap, frame = pipeline._open_capture(cv2)
        self.assertIs(cap, good)
        failed.release.assert_called_once()
        self.assertEqual(pipeline._metrics["negotiated_fps"], 25.0)
        self.assertEqual(pipeline._metrics["camera_backend"], 1400.0)
        self.assertEqual(pipeline._metrics["negotiated_width"], frame.shape[1])
        cap.release()

    def test_real_capture_loop_releases_camera_after_frame_failure(self):
        pipeline = TrackingPipeline(Settings(), Path("unused"))
        cap = Mock()
        cap.read.return_value = (False, None)
        pipeline._open_capture = Mock(return_value=(cap, FakeRGB()))
        original_invalidate = pipeline._invalidate_camera

        def invalidate(error):
            original_invalidate(error)
            pipeline._stop.set()

        pipeline._invalidate_camera = invalidate
        cv2 = SimpleNamespace(COLOR_BGR2RGB=1, flip=lambda f, axis: f,
                              cvtColor=lambda f, color: f)
        with patch.dict("sys.modules", {"cv2": cv2}), self.assertLogs(level="WARNING"):
            pipeline._capture_loop()
        cap.release.assert_called_once()
        self.assertIsNone(pipeline.latest().sample)
        self.assertIsNone(pipeline._pending)
        self.assertEqual(pipeline.latest().status, "RECONECTANDO CÁMARA")

    def test_inference_failure_closes_detector_and_capture_worker(self):
        pipeline = FakePipeline()
        pipeline.detector.detect_async = Mock(side_effect=RuntimeError("inference failed"))
        with self.assertLogs(level="ERROR"):
            pipeline._run()
        self.assertTrue(pipeline.detector.closed)
        self.assertTrue(pipeline.capture_released.is_set())
        self.assertEqual(pipeline.latest().error, "inference failed")


if __name__ == "__main__":
    unittest.main()
