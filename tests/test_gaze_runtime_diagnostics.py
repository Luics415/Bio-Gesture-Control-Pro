"""Local numeric diagnostics; synthetic landmarks and fake detectors only.

These tests never open a camera, move the desktop pointer, or use a real face.
They check observability/privacy contracts, not real-world gaze accuracy.
"""

from dataclasses import replace
import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

from biogesture.face_tracking import eye_geometry_metrics
from biogesture.gaze_export import save_gaze_diagnostic
from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline
from tests.test_face_tracking import run_one, worker
from tests.test_gaze import face


def test_eye_geometry_reports_both_eye_pixel_widths_and_aspect_correct_opening():
    result = eye_geometry_metrics(face(), 640, 480)
    assert result["eye_width_px"] == pytest.approx((64, 64))
    assert result["eye_opening_ratio"] == pytest.approx((.3, .3))
    larger = eye_geometry_metrics(face(), 1280, 960)
    assert larger["eye_width_px"] == pytest.approx((128, 128))
    assert larger["eye_opening_ratio"] == pytest.approx((.3, .3))


def test_geometry_is_invariant_to_eye_corner_order_and_horizontal_mirroring():
    points = tuple(replace(p, x=1 - p.x) for p in face())
    assert eye_geometry_metrics(points, 640, 480) == eye_geometry_metrics(face(), 640, 480)


def test_eye_geometry_uses_perpendicular_opening_in_rotated_pixel_space():
    angle = .23
    points = []
    for p in face():
        x, y = (p.x - .5) * 640, (p.y - .5) * 480
        points.append(replace(p, x=.5 + (x * math.cos(angle) - y * math.sin(angle)) / 640,
                              y=.5 + (x * math.sin(angle) + y * math.cos(angle)) / 480))
    assert eye_geometry_metrics(points, 640, 480) == eye_geometry_metrics(face(), 640, 480)


def test_eye_geometry_exposes_a_closed_eye_without_claiming_it_is_valid_gaze():
    points = list(face())
    points[145] = points[159]
    result = eye_geometry_metrics(points, 640, 480)
    assert result["eye_width_px"] == pytest.approx((64, 64))
    assert result["eye_opening_ratio"] == pytest.approx((0, .3))


@pytest.mark.parametrize("points", [None, [], face()[:385], [object()] * 478])
def test_missing_eye_geometry_is_an_empty_numeric_report(points):
    assert eye_geometry_metrics(points, 640, 480) == {}


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "invalid", None])
def test_nonfinite_or_malformed_geometry_does_not_produce_json_poison(value):
    points = list(face())
    points[33] = replace(points[33], x=value)
    assert eye_geometry_metrics(points, 640, 480) == {}


def test_zero_eye_span_is_not_divided_by_zero():
    points = list(face())
    points[133] = points[33]
    assert eye_geometry_metrics(points, 640, 480) == {}


def test_worker_diagnostics_are_empty_before_inference_and_return_a_copy(monkeypatch):
    eye = worker()
    assert eye.latest_diagnostics() == {}
    run_one(eye, monkeypatch, [face()], timestamp=99.9)
    result = eye.latest_diagnostics()
    assert result["timestamp"] == 99.9
    assert result["valid"] is True and result["reason"] == ""
    assert result["returned_faces"] == 1
    assert result["image_width"] == 640 and result["image_height"] == 480
    assert result["eye_width_px"] == pytest.approx((64, 64))
    result["valid"] = False
    result["image_width"] = -1
    result["eye_width_px"] = (0, 0)
    assert eye.latest_diagnostics()["valid"] is True
    assert eye.latest_diagnostics()["image_width"] == 640
    assert eye.latest_diagnostics()["eye_width_px"] == pytest.approx((64, 64))


def test_capture_latency_includes_waiting_not_only_inference(monkeypatch):
    eye = worker()
    run_one(eye, monkeypatch, [face()], timestamp=99.9)
    result = eye.latest_diagnostics()
    assert result["inference_ms"] == 0
    assert result["capture_to_result_ms"] == pytest.approx(100)
    assert result["face_fps"] == 0  # One completion is not a measured frequency.


def test_face_fps_uses_actual_completions_not_requested_camera_rate(monkeypatch):
    eye = worker()
    eye._completed_times.extend((99.8, 99.9))
    run_one(eye, monkeypatch, [face()])
    assert eye.latest_diagnostics()["face_fps"] == pytest.approx(10)
    assert eye.latest_diagnostics()["face_fps"] != eye.settings.detection_fps


def test_fps_excludes_ancient_completions_after_a_long_gap(monkeypatch):
    eye = worker()
    eye._completed_times.extend((80, 81, 82))
    run_one(eye, monkeypatch, [face()])
    assert eye.latest_diagnostics()["face_fps"] == 0


def test_diagnostic_timing_history_is_bounded():
    eye = worker()
    eye._completed_times.extend(range(1000))
    assert len(eye._completed_times) <= 60


@pytest.mark.parametrize("faces", [[], [face(), face()]])
def test_absent_or_ambiguous_face_replaces_previous_geometry(monkeypatch, faces):
    eye = worker()
    eye._diagnostics = {"eye_width_px": (100, 100), "valid": True}
    run_one(eye, monkeypatch, faces)
    result = eye.latest_diagnostics()
    assert result["valid"] is False
    assert result["returned_faces"] == len(faces)
    assert "eye_width_px" not in result and "eye_opening_ratio" not in result


def test_late_generation_cannot_republish_old_diagnostics(monkeypatch):
    eye = worker()
    eye._diagnostics = {"timestamp": 99, "valid": True}
    eye._completed_times.append(99)
    run_one(eye, monkeypatch, [face()], during_detection=eye.invalidate)
    assert eye.latest_diagnostics() == {}
    assert not eye._completed_times


def test_stop_clears_numeric_diagnostics_and_timing_history():
    eye = worker()
    eye._diagnostics = {"timestamp": 99, "valid": True}
    eye._completed_times.append(99)
    assert eye.stop(timeout=0)
    assert eye.latest_diagnostics() == {}
    assert not eye._completed_times


def test_fatal_model_error_does_not_leave_old_diagnostics():
    eye = worker()
    eye._diagnostics = {"timestamp": 99, "valid": True}
    eye._completed_times.append(99)
    eye._make_detector = Mock(side_effect=RuntimeError("synthetic failure"))
    eye._run()
    assert eye.latest_diagnostics() == {}
    assert not eye._completed_times
    assert "synthetic failure" in eye.latest().reason


def test_pipeline_diagnostic_reader_never_starts_optional_face_processing():
    pipeline = TrackingPipeline(Settings(), Path("unused.task"))
    assert pipeline.latest_gaze_diagnostics() == {}
    assert pipeline._face_worker is None
    expected = {"timestamp": 100, "image_width": 640}
    pipeline._face_worker = Mock()
    pipeline._face_worker.latest_diagnostics.return_value = expected
    assert pipeline.latest_gaze_diagnostics() is expected
    pipeline._face_worker.latest_diagnostics.assert_called_once_with()
    pipeline._face_worker.start.assert_not_called()


def test_export_is_explicit_utf8_json_and_does_not_upload(tmp_path):
    destination = tmp_path / "diagnósticos"
    report = {"accepted": False, "reason": "Precisión insuficiente", "mean": .12,
              "samples": [{"target": [.3, .7], "prediction": [.4, .8]}]}
    assert not destination.exists()
    with patch("socket.create_connection") as network, patch("urllib.request.urlopen") as request:
        path = save_gaze_diagnostic(report, destination)
    assert path.parent == destination and path.name.startswith("mirada-") and path.suffix == ".json"
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert b"Precisi\xc3\xb3n" in path.read_bytes()
    network.assert_not_called()
    request.assert_not_called()


@pytest.mark.parametrize("payload", [None, [], "report", 42, True])
def test_export_requires_an_explicit_report_object_before_creating_files(tmp_path, payload):
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError):
        save_gaze_diagnostic(payload, destination)
    assert not destination.exists()


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_export_rejects_nonfinite_nested_values_before_creating_files(tmp_path, value):
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError):
        save_gaze_diagnostic({"nested": [{"error": value}]}, destination)
    assert not destination.exists()


@pytest.mark.parametrize("value", [object(), np.zeros((2, 2, 3), dtype=np.uint8), b"image-data"])
def test_export_refuses_frame_arrays_and_opaque_objects(tmp_path, value):
    destination = tmp_path / "not-created"
    with pytest.raises(TypeError):
        save_gaze_diagnostic({"unwanted": value}, destination)
    assert not destination.exists()


def test_export_rejects_oversized_payload_before_directory_creation(tmp_path, monkeypatch):
    monkeypatch.setattr("biogesture.gaze_export.MAX_EXPORT_BYTES", 64)
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError, match="tamaño"):
        save_gaze_diagnostic({"detail": "x" * 100}, destination)
    assert not destination.exists()


def test_export_size_limit_counts_encoded_bytes_not_characters(tmp_path, monkeypatch):
    payload = {"detail": "á" * 20}
    monkeypatch.setattr("biogesture.gaze_export.MAX_EXPORT_BYTES", 50)
    assert len(json.dumps(payload, ensure_ascii=False, indent=2)) < 50
    with pytest.raises(ValueError, match="tamaño"):
        save_gaze_diagnostic(payload, tmp_path / "not-created")


def test_successive_exports_preserve_all_previous_attempts(tmp_path):
    first = save_gaze_diagnostic({"attempt": 1}, tmp_path)
    original = first.read_bytes()
    second = save_gaze_diagnostic({"attempt": 2}, tmp_path)
    assert first != second
    assert first.read_bytes() == original
    assert json.loads(second.read_text(encoding="utf-8")) == {"attempt": 2}
    assert set(tmp_path.iterdir()) == {first, second}


def test_even_filename_collision_never_overwrites_an_earlier_report(tmp_path, monkeypatch):
    fake_clock = Mock()
    fake_clock.now.return_value = Mock()
    fake_clock.now.return_value.__format__ = lambda self, spec: "20260908-120000"
    monkeypatch.setattr("biogesture.gaze_export.datetime", fake_clock)
    monkeypatch.setattr("biogesture.gaze_export.uuid4", lambda: SimpleNamespace(hex="0123456789abcdef"))
    first = save_gaze_diagnostic({"attempt": 1}, tmp_path)
    original = first.read_bytes()
    with pytest.raises(FileExistsError):
        save_gaze_diagnostic({"attempt": 2}, tmp_path)
    assert first.read_bytes() == original
    assert list(tmp_path.iterdir()) == [first]
