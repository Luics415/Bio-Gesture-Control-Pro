"""Precision diagnostics remain numeric, reproducible and unable to control the PC."""

import builtins
from copy import deepcopy
from dataclasses import replace
import json
import math
import os
from unittest.mock import Mock

import pytest

from biogesture.coordinates import RectMonitor
from biogesture.gaze import CalibrationReport
from biogesture.gaze_diagnostics import (PRECISION_ENGINE_ID, PRECISION_OBSERVATION_SCHEMA,
                                         build_diagnostic_report)
from biogesture.gaze_precision import PrecisionGazeCalibration
from biogesture.gaze_replay import replay_diagnostic
from biogesture.gaze_ui import CalibrationCollector, GazeCalibrationDialog
from tests.test_gaze import observed
from tests.test_gaze_ui import bare_dialog


def precision_observed(timestamp, target=(.5, .5)):
    x, y = (target[0] - .5) * .5, (target[1] - .5) * .5
    norm = math.sqrt(x * x + y * y + 1)
    return replace(observed(timestamp, target), auxiliary_features=(x / norm, y / norm, -1 / norm, 0., 0., 0.),
                   feature_schema=PRECISION_OBSERVATION_SCHEMA)


def fitted_precision():
    calibration = PrecisionGazeCalibration()
    timestamp = 10.
    for target in calibration.training_targets:
        for _ in range(3):
            assert calibration.add_sample(precision_observed(timestamp, target), target)
            timestamp += .05
    assert calibration.fit(), calibration.report.reason
    return calibration


def precision_validation(calibration, *, shifted=False):
    result = []
    timestamp = 20.
    for target in calibration.validation_targets:
        point = (target[0] + .12, target[1]) if shifted else target
        for _ in range(3):
            result.append((precision_observed(timestamp, point), target))
            timestamp += .05
    return result


def session_export(*, shifted=False):
    calibration = fitted_precision()
    validation = precision_validation(calibration, shifted=shifted)
    calibration.validate(validation)
    return build_diagnostic_report(calibration, validation, include_samples=True)


def finish_precision_point(collector, now, *, shifted=False):
    original = collector.phase, collector.point_index
    for _ in range(100):
        now = round(now + .05, 6)
        target = collector.target
        if shifted:
            target = target[0] + .12, target[1]
        collector.update(precision_observed(now, target), now)
        if (collector.phase, collector.point_index) != original:
            return now
    raise AssertionError("El objetivo de precisión no terminó")


def precision_collector(*, shifted=True):
    collector = CalibrationCollector(PrecisionGazeCalibration)
    collector.start(10)
    now = 10
    for _ in range(13):
        now = finish_precision_point(collector, now)
    assert collector.phase == "validation", collector.message
    for _ in range(9):
        now = finish_precision_point(collector, now, shifted=shifted)
    return collector, now


def test_precision_report_schema_and_six_named_numeric_auxiliary_features_without_samples_by_default():
    calibration = fitted_precision()
    report = build_diagnostic_report(calibration, precision_validation(calibration))
    assert report["schema_version"] == 2
    assert report["engine_id"] == PRECISION_ENGINE_ID
    assert report["observation_schema"] == PRECISION_OBSERVATION_SCHEMA
    assert len(report["features"]) == 10
    assert len(report["auxiliary_features"]) == 6
    assert [row["units"] for row in report["auxiliary_features"]] == ["unit_vector_component"] * 3 + ["radians"] * 3
    assert "samples" not in report and report["samples_included"] is False
    assert "coefficient_feature_names" not in report["signal"]["model"]
    assert report["signal"]["model"]["kind"] == "personalized_kernel_ridge"
    json.dumps(report, allow_nan=False)


def test_precision_worker_telemetry_exports_only_six_numeric_neural_features_and_timing():
    calibration = fitted_precision()
    worker = {"gaze_engine": PRECISION_ENGINE_ID, "neural_ms": 12.3,
              "neural_features": (0., 0., -1., 0., 0., 0.), "frame": b"not an image export"}
    report = build_diagnostic_report(calibration, (), context={"telemetry": {"worker": worker}})
    actual = report["context"]["telemetry"]["worker"]
    assert actual["gaze_engine"] == PRECISION_ENGINE_ID and actual["neural_ms"] == 12.3
    assert actual["neural_features"] == [0., 0., -1., 0., 0., 0.]
    assert "frame" not in actual
    worker["neural_features"] = ["encoded image"] * 6
    report = build_diagnostic_report(calibration, (), context={"telemetry": {"worker": worker}})
    assert "neural_features" not in report["context"]["telemetry"]["worker"]


@pytest.mark.parametrize("shifted", [False, True])
def test_precision_replay_preserves_model_selection_and_heldout_result_without_cnn_or_io(shifted, monkeypatch):
    payload = session_export(shifted=shifted)
    before = deepcopy(payload)
    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        assert name.split(".")[0] not in ("openvino", "mediapipe", "cv2")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "open", Mock(side_effect=AssertionError("No files in numeric replay")))
    result = replay_diagnostic(payload)
    assert result["acceptance_report"] == payload["acceptance_report"]
    assert result["signal"]["model"]["selection"] == payload["signal"]["model"]["selection"]
    assert result["replay"]["desktop_input_enabled"] is False
    assert result["replay"]["camera_opened"] is False
    assert payload == before


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(schema_version=3),
    lambda p: p.update(engine_id="user_module.CustomModel"),
    lambda p: p.update(engine_id="legacy-ridge-v1"),
    lambda p: p.update(observation_schema="future-schema"),
    lambda p: p["samples"][0].pop("auxiliary_features"),
    lambda p: p["samples"][0].update(auxiliary_features=[0.] * 7),
    lambda p: p["samples"][0].update(auxiliary_features=[True] * 6),
    lambda p: p["samples"][0].update(auxiliary_features=[math.inf] * 6),
    lambda p: p["samples"][-1].update(phase="training"),
])
def test_precision_replay_rejects_unknown_versions_schemas_engines_and_malformed_measurements(mutate):
    payload = session_export()
    mutate(payload)
    with pytest.raises(ValueError):
        replay_diagnostic(payload)


def test_legacy_v1_cannot_disguise_precision_data():
    payload = session_export()
    payload["schema_version"] = 1
    with pytest.raises(ValueError, match="esquema 1"):
        replay_diagnostic(payload)
    payload.pop("engine_id")
    payload.pop("observation_schema")
    with pytest.raises(ValueError, match="auxiliares"):
        replay_diagnostic(payload)


def test_precision_export_only_exports_six_valid_auxiliary_numbers_not_opaque_data():
    calibration = fitted_precision()
    validation = precision_validation(calibration)
    bad = replace(validation[0][0], valid=False, auxiliary_features=(b"not-an-image",) * 6)
    report = build_diagnostic_report(calibration, [(bad, validation[0][1])], include_samples=True)
    assert all(len(row["auxiliary_features"]) == 6 for row in report["samples"] if row["phase"] == "training")
    assert report["samples"][-1]["auxiliary_features"] is None
    assert "not-an-image" not in json.dumps(report, allow_nan=False)


def test_report_readonly_keeps_precision_model_readiness_and_training_validation_separate():
    calibration = fitted_precision()
    validation = precision_validation(calibration)
    calibration.validate(validation)
    model = deepcopy(calibration.diagnostic_model())
    before = calibration.report, calibration.ready, calibration.training_samples
    build_diagnostic_report(calibration, validation, include_samples=True)
    assert (calibration.report, calibration.ready, calibration.training_samples) == before
    assert calibration.diagnostic_model() == model


def test_collector_runs_thirteen_training_and_nine_distinct_validation_targets():
    collector, _ = precision_collector(shifted=False)
    assert len(collector.training_targets) == 13 and len(collector.validation_targets) == 9
    assert not set(collector.training_targets) & set(collector.validation_targets)
    assert len(collector.capture_points) == 22
    assert collector.phase == "complete", collector.message
    assert collector.calibration.ready


@pytest.mark.parametrize("changes", [
    {"feature_schema": "iris10-v1"}, {"auxiliary_features": ()},
    {"auxiliary_features": (0, 0, 5, 0, 0, 0)},
    {"auxiliary_features": (0, 0, 1, math.pi, 0, 0)},
])
def test_collector_rejects_wrong_precision_schema_or_vector_before_learning(changes):
    collector = CalibrationCollector(PrecisionGazeCalibration)
    collector.start(10)
    sample = replace(precision_observed(10.8), **changes)
    assert not collector._usable(sample, 10.8)
    collector.update(sample, 10.8)
    assert not collector._samples and not collector.calibration.sample_count
    assert collector.phase == "calibration"


def test_precision_failure_number_uses_engine_validation_count():
    collector = CalibrationCollector(PrecisionGazeCalibration)
    collector.start(10)
    target = collector.validation_targets[-1]
    collector._accuracy_failure(CalibrationReport(mean_error=.1, max_error=.2, worst_target=target))
    assert "punto de comprobación 9 de 9" in collector.message
    assert not collector.can_retry_point and not collector.calibration.ready


def test_precision_dialog_idle_counts_and_live_six_variables():
    dialog = bare_dialog()
    dialog.collector = CalibrationCollector(PrecisionGazeCalibration)
    dialog._paint = GazeCalibrationDialog._paint.__get__(dialog)
    dialog._painted = None
    dialog.canvas, dialog.start_button = Mock(), Mock()
    dialog._paint()
    texts = " ".join(kwargs["text"] for _, kwargs in dialog.canvas.create_text.call_args_list)
    assert "Habrá 13 puntos y luego 9 de comprobación" in texts
    dialog._live_observation = precision_observed(10.1)
    dialog._latest_diagnostics = lambda: {"worker": {"neural_ms": 12.3}}
    dialog.canvas.reset_mock()
    dialog._paint_technical()
    texts = " ".join(kwargs["text"] for _, kwargs in dialog.canvas.create_text.call_args_list)
    assert "Precisión local" in texts and "Mirada unitaria XYZ" in texts and "yaw/pitch/roll" in texts
    assert "ocular 12.3 ms" in texts


def test_precision_failure_keeps_p_d_e_readonly_and_export_explicit():
    dialog = bare_dialog()
    dialog.collector, now = precision_collector()
    dialog._clock.return_value = now + .1
    dialog._latest_observation.return_value = precision_observed(now + .1)
    dialog.canvas = Mock()
    dialog._on_export_diagnostics = Mock(return_value="precision-test.json")
    assert dialog.collector.phase == "error"
    dialog.toggle_details()
    dialog._tick()
    dialog.toggle_probe()
    dialog._tick()
    dialog._on_export_diagnostics.assert_not_called()
    dialog.export_diagnostics()
    payload = dialog._on_export_diagnostics.call_args.args[0]
    assert payload["schema_version"] == 2 and payload["samples_included"] is True
    assert not dialog.collector.calibration.ready
    dialog._on_success.assert_not_called()
    dialog._on_close.assert_not_called()


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Tk precision geometry is opt-in")
@pytest.mark.parametrize("scaling", [1.333, 2.0])
def test_precision_twenty_two_point_ledger_and_result_fit_real_800x600(scaling):
    import tkinter as tk

    from biogesture.windows import enable_dpi_awareness

    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", scaling)
    dialog = None
    try:
        dialog = GazeCalibrationDialog(root, RectMonitor("test", "Test", 0, 0, 800, 600), lambda: None,
                                       Mock(), Mock(), calibration_factory=PrecisionGazeCalibration,
                                       clock=lambda: 100)
        dialog.collector, _ = precision_collector()
        dialog._live_observation = precision_observed(100)
        for detail in (False, True):
            dialog._detail = detail
            dialog._paint()
            root.update_idletasks()
            for item in dialog.canvas.find_all():
                left, top, right, bottom = dialog.canvas.bbox(item)
                assert 0 <= left < right <= 800
                assert 0 <= top < bottom <= 525
            if detail:
                ledger = dialog.canvas.find_withtag("capture_ledger")
                assert len(ledger) == 3
                assert all(dialog.canvas.bbox(item)[3] < 385 for item in ledger)
    finally:
        if dialog is not None:
            dialog.destroy()
        root.destroy()
