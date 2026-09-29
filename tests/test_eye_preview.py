"""Eye-only calibration preparation previews, with generated pixels only.

These checks never access a camera, a photograph, native desktop input, or a
real facial model. They verify geometry, explicit opt-in, and ephemeral data.
"""

from dataclasses import replace
import math
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

from biogesture.face_tracking import EyePreview, FaceTrackingWorker, make_eye_preview
from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline
from tests.test_gaze import face
from tests.test_tracking import FakePipeline


def pixels(width=640, height=480):
    """Synthetic coordinates encoded as colors, not a captured person."""
    y, x = np.indices((height, width))
    return np.stack((x % 256, y % 256, (x + y) % 256), axis=2).astype(np.uint8)


def eye_worker():
    return FaceTrackingWorker(Settings(cursor_mode="eyes", gaze_engine="legacy-ridge-v1"), Path("unused-face.task"))


def run_one(eye, monkeypatch, *, faces=None, during_detection=None, stamp=99.9):
    """Exactly one synchronous fake inference; no camera or native thread."""
    detector = Mock()

    def detect(image, timestamp):
        if during_detection:
            during_detection()
        return SimpleNamespace(face_landmarks=[face()] if faces is None else faces)

    detector.detect_for_video.side_effect = detect
    eye._mp = SimpleNamespace(Image=Mock(return_value="synthetic"),
                              ImageFormat=SimpleNamespace(SRGB="SRGB"))
    eye._make_detector = Mock(return_value=detector)
    eye.offer(pixels(), stamp)
    monkeypatch.setattr(eye._stop, "is_set", Mock(side_effect=[False, False, True]))
    monkeypatch.setattr("biogesture.face_tracking.time.monotonic", lambda: 100.0)
    monkeypatch.setattr("biogesture.face_tracking.eye_focus_ok", lambda *args: True)
    eye._run()
    detector.close.assert_called_once()
    return detector


def test_preview_contains_only_exact_eye_strip_not_the_full_frame():
    rgb = pixels()
    preview = make_eye_preview(rgb, face(), 12.5)
    assert isinstance(preview, EyePreview)
    assert preview.timestamp == 12.5
    assert preview.rgb.shape == (72, 308, 3)
    np.testing.assert_array_equal(preview.rgb, rgb[156:228, 166:474])
    assert len(preview.points) == 10
    # Both iris centers are in the strip, not in full-camera coordinates.
    assert preview.points[4] == pytest.approx(((224 - 166) / 308, .5))
    assert preview.points[9] == pytest.approx(((416 - 166) / 308, .5))
    assert all(0 <= coordinate <= 1 for point in preview.points for coordinate in point)


def test_preview_is_detached_from_source_buffer_and_cannot_reveal_other_regions():
    rgb = pixels()
    preview = make_eye_preview(rgb, face(), 10)
    saved = preview.rgb.copy()
    assert not np.shares_memory(preview.rgb, rgb)
    rgb[:] = 0
    np.testing.assert_array_equal(preview.rgb, saved)


@pytest.mark.parametrize("width,height", [(1280, 960), (1920, 1080)])
def test_large_capture_preview_is_bounded_and_preserves_rgb_and_relative_points(width, height):
    preview = make_eye_preview(pixels(width, height), face(), 10)
    assert preview.rgb.dtype == np.uint8
    assert preview.rgb.shape[1] == 480
    assert preview.rgb.shape[0] < 480
    assert preview.rgb.shape[2] == 3
    assert preview.points[4][0] < preview.points[9][0]
    assert preview.points[4][1] == pytest.approx(.5, abs=.02)
    assert preview.points[9][1] == pytest.approx(.5, abs=.02)
    assert all(0 <= coordinate <= 1 for point in preview.points for coordinate in point)


def test_padding_clips_at_camera_edges_without_wrapping_to_other_side():
    landmarks = tuple(replace(p, x=p.x - .30, y=p.y - .38) for p in face())
    rgb = pixels()
    preview = make_eye_preview(rgb, landmarks, 1)
    assert preview is not None
    np.testing.assert_array_equal(preview.rgb[0, 0], rgb[0, 0])
    assert preview.points[0][0] == pytest.approx(0)
    assert preview.points[1][1] == pytest.approx(0)
    assert all(0 <= coordinate <= 1 for point in preview.points for coordinate in point)


@pytest.mark.parametrize("rgb", [
    None, [], np.zeros((0, 640, 3), dtype=np.uint8),
    np.zeros((480, 0, 3), dtype=np.uint8), np.zeros((640,), dtype=np.uint8),
    np.zeros((480, 640), dtype=np.uint8), np.zeros((480, 640, 1), dtype=np.uint8),
    np.zeros((480, 640, 4), dtype=np.uint8), np.zeros((480, 640, 3, 1), dtype=np.uint8),
    np.zeros((480, 640, 3), dtype=np.float32),
    np.full((480, 640, 3), np.nan, dtype=np.float32),
    np.empty((960, 1280, 3), dtype=object),
])
def test_malformed_or_non_rgb_input_is_rejected_without_exception(rgb):
    assert make_eye_preview(rgb, face(), 1) is None


@pytest.mark.parametrize("stamp", [None, "12", True, math.nan, math.inf, -math.inf])
def test_invalid_capture_timestamp_cannot_produce_preview(stamp):
    assert make_eye_preview(pixels(), face(), stamp) is None


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -0.01, 1.0, 1.01])
@pytest.mark.parametrize("coordinate", ["x", "y"])
def test_bad_or_outside_eye_landmark_is_fail_closed(value, coordinate):
    landmarks = list(face())
    landmarks[468] = replace(landmarks[468], **{coordinate: value})
    assert make_eye_preview(pixels(), landmarks, 1) is None


@pytest.mark.parametrize("landmarks", [None, [], face()[:470], [object()] * 478])
def test_missing_landmarks_cannot_produce_preview(landmarks):
    assert make_eye_preview(pixels(), landmarks, 1) is None


def test_tiny_eye_span_is_not_enlarged_into_a_misleading_preview():
    landmarks = tuple(replace(p, x=.5 + (p.x - .5) * .05) for p in face())
    assert make_eye_preview(pixels(), landmarks, 1) is None


def test_preview_production_does_not_write_images_or_open_network():
    rgb = pixels()
    with (patch("builtins.open") as files, patch.object(Path, "write_bytes") as binary,
          patch.object(Path, "write_text") as text, patch.object(cv2, "imwrite") as image_file,
          patch.object(np, "save") as array_file, patch("socket.create_connection") as network):
        assert make_eye_preview(rgb, face(), 1) is not None
    for operation in (files, binary, text, image_file, array_file, network):
        operation.assert_not_called()


def test_worker_preview_is_disabled_by_default_and_builder_is_not_called(monkeypatch):
    eye = eye_worker()
    assert not eye._preview_enabled
    assert eye.latest_preview() is None
    with patch("biogesture.face_tracking.make_eye_preview") as builder:
        run_one(eye, monkeypatch)
    builder.assert_not_called()
    assert eye.latest().valid
    assert eye.latest_preview() is None


def test_explicit_opt_in_produces_fresh_eye_only_preview(monkeypatch):
    eye = eye_worker()
    eye.set_preview_enabled(True)
    run_one(eye, monkeypatch)
    preview = eye.latest_preview()
    assert isinstance(preview, EyePreview)
    assert preview.timestamp == 99.9 == eye.latest().timestamp
    assert preview.rgb.shape == (72, 308, 3)
    assert eye._pending is None


@pytest.mark.parametrize("faces", [[], [face(), face()]])
def test_missing_or_ambiguous_face_clears_previous_preview(monkeypatch, faces):
    eye = eye_worker()
    eye.set_preview_enabled(True)
    eye._preview = make_eye_preview(pixels(), face(), 99)
    run_one(eye, monkeypatch, faces=faces)
    assert eye.latest_preview() is None
    assert not eye.latest().valid


def test_disabling_preview_releases_pixels_and_increments_its_generation():
    eye = eye_worker()
    eye.set_preview_enabled(True)
    eye._preview = make_eye_preview(pixels(), face(), 99)
    generation = eye._preview_generation
    eye.set_preview_enabled(False)
    assert eye._preview is None
    assert eye.latest_preview() is None
    assert eye._preview_generation > generation


@pytest.mark.parametrize("transition", ["disable", "disable_reenable", "invalidate"])
def test_inflight_preview_cannot_survive_privacy_or_capture_generation_change(monkeypatch, transition):
    eye = eye_worker()
    eye.set_preview_enabled(True)
    eye._preview = make_eye_preview(pixels(), face(), 99)

    def change():
        if transition == "invalidate":
            eye.invalidate()
        else:
            eye.set_preview_enabled(False)
            if transition == "disable_reenable":
                eye.set_preview_enabled(True)

    run_one(eye, monkeypatch, during_detection=change)
    assert eye.latest_preview() is None
    assert eye._preview is None


def test_enabling_mid_inference_does_not_publish_unrequested_old_frame(monkeypatch):
    eye = eye_worker()
    run_one(eye, monkeypatch, during_detection=lambda: eye.set_preview_enabled(True))
    assert eye.latest_preview() is None


def test_camera_invalidation_and_stop_release_preview_and_pending_frame():
    eye = eye_worker()
    eye.set_preview_enabled(True)
    eye._preview = make_eye_preview(pixels(), face(), 99)
    eye.offer(pixels(), 99.9)
    eye.invalidate()
    assert eye.latest_preview() is None
    assert eye._pending is None
    eye._preview = make_eye_preview(pixels(), face(), 100)
    assert eye.stop(timeout=0)
    assert eye.latest_preview() is None
    assert eye._pending is None


def test_fatal_detector_failure_does_not_retain_old_preview():
    eye = eye_worker()
    eye.set_preview_enabled(True)
    eye._preview = make_eye_preview(pixels(), face(), 99)
    eye._make_detector = Mock(side_effect=RuntimeError("synthetic model failure"))
    eye._run()
    assert not eye.latest().valid
    assert eye.latest_preview() is None
    assert eye._preview is None


def test_pipeline_without_facial_worker_does_not_create_one_for_preview():
    pipeline = TrackingPipeline(Settings(), Path("unused-hands.task"))
    pipeline.set_eye_preview_enabled(True)
    assert pipeline._face_worker is None
    assert pipeline.latest_eye_preview() is None


def test_pipeline_only_forwards_explicit_preview_toggle_and_latest_reader():
    pipeline = TrackingPipeline(Settings(cursor_mode="eyes"), Path("unused-hands.task"))
    eye = Mock()
    expected = object()
    eye.latest_preview.return_value = expected
    pipeline._face_worker = eye
    pipeline.set_eye_preview_enabled(True)
    eye.set_preview_enabled.assert_called_once_with(True)
    assert pipeline.latest_eye_preview() is expected
    eye.latest_preview.assert_called_once_with()
    eye.start.assert_not_called()


def test_worker_registration_and_close_cannot_restore_preview_after_disable():
    """A close racing with delayed startup wins, without native model loading."""
    entered, release, closing = Event(), Event(), Event()
    errors = []
    pipeline = FakePipeline()
    pipeline.settings = Settings(cursor_mode="eyes")
    pipeline.set_eye_preview_enabled(True)
    # The fake worker initializes, but no camera loop or inference may start.
    pipeline._stop.set()

    class DelayedPreviewWorker:
        running = False

        def __init__(self):
            self.enabled = False
            self.locked_calls = []

        def set_preview_enabled(self, enabled):
            self.locked_calls.append(pipeline._condition._is_owned())
            if enabled:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("Synthetic startup barrier timed out")
            self.enabled = bool(enabled)

        def start(self):
            pass

        def stop(self, timeout=0):
            return True

    eye = DelayedPreviewWorker()

    def disable():
        closing.set()
        try:
            pipeline.set_eye_preview_enabled(False)
        except Exception as exc:
            errors.append(exc)

    startup = Thread(target=pipeline._run)
    closer = Thread(target=disable)
    with patch("biogesture.face_tracking.FaceTrackingWorker", return_value=eye):
        try:
            startup.start()
            assert entered.wait(1)
            closer.start()
            assert closing.wait(1)
        finally:
            release.set()
            startup.join(2)
            if closer.ident is not None:
                closer.join(2)
    assert not startup.is_alive() and not closer.is_alive()
    assert not errors
    assert eye.locked_calls == [True, True]
    assert pipeline._eye_preview_enabled is False
    assert eye.enabled is False
