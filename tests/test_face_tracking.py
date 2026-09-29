"""Local facial worker contracts, using fake models/cameras/detectors only."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import numpy as np

from biogesture.face_tracking import FaceTrackingWorker, eye_focus_ok
from biogesture.gaze import GazeObservation
from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline
from tests.test_gaze import face
from tests.test_tracking import FakeRGB, FakePipeline


def worker():
    return FaceTrackingWorker(Settings(cursor_mode="eyes", gaze_engine="legacy-ridge-v1"), Path("local-model.task"))


def fake_mediapipe():
    detector = Mock()
    base_options = Mock()
    options = Mock()
    factory = Mock(return_value=detector)
    mp = SimpleNamespace(tasks=SimpleNamespace(BaseOptions=base_options, vision=SimpleNamespace(
        FaceLandmarkerOptions=options, RunningMode=SimpleNamespace(VIDEO="VIDEO"),
        FaceLandmarker=SimpleNamespace(create_from_options=factory))))
    return mp, detector, base_options, options, factory


def test_detector_uses_verified_local_bytes_and_disables_unused_face_outputs(monkeypatch):
    eye = worker()
    eye.model_path = Mock()
    model = b"local-test-model-not-real"
    eye.model_path.read_bytes.return_value = model
    monkeypatch.setattr("biogesture.face_tracking.FACE_MODEL_SHA256", hashlib.sha256(model).hexdigest())
    mp, detector, base_options, options, factory = fake_mediapipe()
    with patch.dict("sys.modules", {"mediapipe": mp}):
        assert eye._make_detector() is detector
    eye.model_path.read_bytes.assert_called_once()
    base_options.assert_called_once_with(model_asset_buffer=model)
    configuration = options.call_args.kwargs
    assert configuration["num_faces"] == 1
    assert configuration["running_mode"] == "VIDEO"
    assert configuration["output_face_blendshapes"] is False
    assert configuration["output_facial_transformation_matrixes"] is False
    assert configuration["min_face_detection_confidence"] == eye.settings.detection_confidence
    assert configuration["min_tracking_confidence"] == eye.settings.tracking_confidence
    factory.assert_called_once()


@pytest.mark.parametrize("failure", ["modified", "missing"])
def test_invalid_local_model_cannot_instantiate_detector_or_fetch_a_replacement(failure):
    eye = worker()
    eye.model_path = Mock()
    eye.model_path.read_bytes.return_value = b"untrusted-model"
    if failure == "missing":
        eye.model_path.read_bytes.side_effect = FileNotFoundError("missing local model")
    mp, detector, base_options, options, factory = fake_mediapipe()
    with patch.dict("sys.modules", {"mediapipe": mp}), patch("urllib.request.urlopen") as network:
        with pytest.raises((ValueError, FileNotFoundError)):
            eye._make_detector()
        network.assert_not_called()
    factory.assert_not_called()
    base_options.assert_not_called()


def test_worker_has_one_latest_frame_slot_instead_of_a_queue():
    eye = worker()
    frames = [FakeRGB() for _ in range(100)]
    for i, rgb in enumerate(frames):
        eye.offer(rgb, i)
    assert eye._pending == (frames[-1], 99, 0)
    assert eye.latest() is None


def test_invalidation_removes_old_observation_pending_frame_and_changes_generation():
    eye = worker()
    eye._latest = GazeObservation(100)
    eye.offer(FakeRGB(), 100)
    eye.invalidate()
    assert eye.latest() is None
    assert eye._pending is None
    assert eye._generation == 1


def run_one(eye, monkeypatch, faces, *, during_detection=None, timestamp=100):
    """Run exactly one worker iteration synchronously, without native threads."""
    detector = Mock()

    def detect(image, submitted):
        if during_detection:
            during_detection()
        return SimpleNamespace(face_landmarks=faces)

    detector.detect_for_video.side_effect = detect
    eye._mp = SimpleNamespace(Image=Mock(return_value="fake-image"), ImageFormat=SimpleNamespace(SRGB="SRGB"))
    eye._make_detector = Mock(return_value=detector)
    eye.offer(FakeRGB(), timestamp)
    # While condition; guarded publication; next while condition.
    monkeypatch.setattr(eye._stop, "is_set", Mock(side_effect=[False, False, True]))
    monkeypatch.setattr("biogesture.face_tracking.time.monotonic", lambda: 100)
    monkeypatch.setattr("biogesture.face_tracking.time.perf_counter", lambda: 200)
    monkeypatch.setattr("biogesture.face_tracking.eye_focus_ok", lambda rgb, landmarks: True)
    eye._run()
    detector.close.assert_called_once()
    return detector


def test_face_worker_keeps_capture_timestamp_and_iris_features(monkeypatch):
    eye = worker()
    detector = run_one(eye, monkeypatch, [face()], timestamp=99.9)
    result = eye.latest()
    assert result.valid
    assert result.timestamp == 99.9
    assert len(result.features) == 10
    detector.detect_for_video.assert_called_once_with("fake-image", 99900)
    assert eye.inference_ms == 0


@pytest.mark.parametrize("faces", [[], [face(), face()]])
def test_zero_or_multiple_returned_faces_produce_invalid_observation(monkeypatch, faces):
    eye = worker()
    run_one(eye, monkeypatch, faces)
    assert not eye.latest().valid
    assert "visibles" in eye.latest().reason


def test_late_face_result_from_invalidated_camera_generation_is_discarded(monkeypatch):
    eye = worker()
    run_one(eye, monkeypatch, [face()], during_detection=eye.invalidate)
    assert eye.latest() is None


def test_stale_unsent_frame_is_dropped_without_inference(monkeypatch):
    eye = worker()
    detector = Mock()
    eye._make_detector = Mock(return_value=detector)
    eye.offer(FakeRGB(), 99)
    monkeypatch.setattr(eye._stop, "is_set", Mock(side_effect=[False, True]))
    monkeypatch.setattr("biogesture.face_tracking.time.monotonic", lambda: 100)
    eye._run()
    detector.detect_for_video.assert_not_called()
    detector.close.assert_called_once()
    assert eye.latest() is None


def test_initialization_failure_is_observable_without_any_capture_or_input():
    eye = worker()
    eye._make_detector = Mock(side_effect=FileNotFoundError("test missing model"))
    eye._run()
    assert not eye.latest().valid
    assert "test missing model" in eye.latest().reason


def test_stop_clears_face_data_and_refuses_success_while_native_thread_is_alive():
    eye = worker()
    eye._thread = Mock()
    eye._thread.is_alive.return_value = True
    eye._latest = GazeObservation(100)
    eye.offer(FakeRGB(), 100)
    assert not eye.stop(timeout=0)
    assert eye.latest() is None and eye._pending is None
    with pytest.raises(RuntimeError):
        eye.start()


def test_one_camera_frame_is_shared_with_face_worker_without_replacing_hand_slot():
    pipeline = TrackingPipeline(Settings(cursor_mode="eyes"), Path("hands.task"))
    pipeline._face_worker = Mock()
    frame = FakeRGB()
    pipeline._offer_frame(frame, 100)
    assert pipeline._pending.rgb is frame
    pipeline._face_worker.offer.assert_called_once_with(frame, 100)


def test_camera_disconnect_invalidates_facial_result_alongside_hand_result():
    pipeline = TrackingPipeline(Settings(cursor_mode="eyes"), Path("hands.task"))
    pipeline._face_worker = worker()
    pipeline._face_worker._latest = GazeObservation(100)
    pipeline._face_worker.offer(FakeRGB(), 100)
    pipeline._invalidate_camera("test camera removed")
    assert pipeline.latest_gaze() is None
    assert pipeline._face_worker._pending is None
    assert pipeline.latest().sample is None
    assert pipeline.latest().status == "RECONECTANDO CÁMARA"


@pytest.mark.parametrize("performance", ["optimal", "saving"])
def test_index_profiles_never_construct_a_facial_worker(performance):
    pipeline = FakePipeline()
    pipeline.settings = Settings(performance_mode=performance).runtime_settings()
    pipeline._stop.set()
    with patch("biogesture.face_tracking.FaceTrackingWorker") as factory:
        pipeline._run()
    factory.assert_not_called()
    assert pipeline.latest_gaze() is None


def test_eye_pipeline_uses_sibling_local_model_and_stops_worker_on_shutdown():
    pipeline = FakePipeline()
    pipeline.settings = Settings(cursor_mode="eyes")
    pipeline._stop.set()
    with patch("biogesture.face_tracking.FaceTrackingWorker") as factory:
        factory.return_value.running = False
        pipeline._run()
    factory.assert_called_once_with(pipeline.settings, Path("face_landmarker.task"))
    factory.return_value.start.assert_called_once()
    factory.return_value.stop.assert_called_once()


@pytest.mark.parametrize("resting", [True, False])
def test_rest_state_is_forwarded_to_face_processing(resting):
    pipeline = TrackingPipeline(Settings(cursor_mode="eyes"), Path("hands.task"))
    pipeline._face_worker = Mock()
    pipeline.set_resting(resting)
    assert pipeline._resting is resting
    pipeline._face_worker.set_resting.assert_called_once_with(resting)


@pytest.mark.parametrize("value", [0, 127, 255])
def test_uniform_eye_regions_are_not_accepted_as_focused(value):
    assert not eye_focus_ok(np.full((480, 640, 3), value, dtype=np.uint8), face())


def checkerboard():
    pixels = ((np.indices((480, 640)).sum(axis=0) % 2) * 255).astype(np.uint8)
    return np.repeat(pixels[:, :, None], 3, axis=2)


def test_detailed_synthetic_eye_regions_pass_focus_gate():
    assert eye_focus_ok(checkerboard(), face())


def test_blurred_eye_regions_fail_even_with_plausible_landmarks():
    import cv2
    rgb = cv2.GaussianBlur(checkerboard(), (15, 15), 4)
    assert not eye_focus_ok(rgb, face())


def test_only_one_focused_eye_is_insufficient():
    rgb = checkerboard()
    rgb[:, 320:] = 127
    assert not eye_focus_ok(rgb, face())
