"""New perimeter acquisition is versioned; historic reports are not retuned."""

from dataclasses import asdict, replace
import json
import math
from unittest.mock import Mock

import numpy as np
import pytest

from biogesture.gaze_diagnostics import build_diagnostic_report
from biogesture.gaze_precision import (PERIPHERAL_ENGINE, PeripheralGazeCalibration,
                                       PrecisionGazeCalibration, TRAINING_TARGETS,
                                       create_gaze_calibration)
from biogesture.gaze_replay import replay_diagnostic
from biogesture.settings import Settings
from tests.test_gaze_precision import neural_observed


def fitted_peripheral():
    result = PeripheralGazeCalibration()
    for stamp, target in enumerate(result.training_targets, 1):
        assert result.add_sample(neural_observed(stamp, target), target)
    assert result.fit(), result.report.reason
    return result


def peripheral_validation(*, bad=False):
    return [(neural_observed(stamp, (.5, .5) if bad else target), target)
            for stamp, target in enumerate(PeripheralGazeCalibration.validation_targets, 30)]


def test_new_grid_retains_intermediate_training_and_adds_independent_peripheral_checks():
    training = PeripheralGazeCalibration.training_targets
    validation = PeripheralGazeCalibration.validation_targets
    assert len(set(training)) == 21 and len(set(validation)) == 13
    assert set(TRAINING_TARGETS).issubset(training)
    assert len([t for t in training if min(t) < .05 or max(t) > .95]) == 8
    assert all(math.dist(a, b) >= .04 for a in training for b in validation)
    assert np.ptp(training, axis=0) == pytest.approx([.92, .92])
    assert np.ptp(validation, axis=0) == pytest.approx([.86, .86])


def test_new_engine_does_not_accept_old_or_invented_target_coverage():
    calibration = PeripheralGazeCalibration()
    for stamp, target in enumerate(TRAINING_TARGETS, 1):
        calibration.add_sample(neural_observed(stamp, target), target)
    assert not calibration.fit() and not calibration.ready
    for stamp, target in enumerate(calibration.training_targets, 100):
        calibration.add_sample(neural_observed(stamp, target), target)
    assert calibration.fit()
    # An arbitrary additional target cannot bypass the protocol/bounded solve.
    calibration.add_sample(neural_observed(200), (.51, .51))
    assert not calibration.fit()


def test_perimeter_fit_does_not_enable_control_or_impose_a_screen_gain():
    calibration = fitted_peripheral()
    assert not calibration.ready and calibration.predict(neural_observed(50)) is None
    assert calibration.validate(peripheral_validation()).passed
    for target in ((.04, .04), (.96, .96), (.5, .04), (.5, .96), (.5, .5)):
        assert calibration.predict(neural_observed(100, target)) == pytest.approx(target, abs=.015)


def test_peripheral_validation_is_complete_raw_and_never_changes_the_selected_model():
    calibration = fitted_peripheral()
    before = calibration.diagnostic_model()
    assert not calibration.validate(peripheral_validation()[:-1]).passed
    assert not calibration.validate(peripheral_validation(bad=True)).passed
    assert calibration.diagnostic_model() == before
    assert not calibration.ready and calibration.predict(neural_observed(100)) is None
    assert calibration.mean_error_limit == .04 and calibration.max_error_limit == .08


@pytest.mark.parametrize("bad", [False, True])
def test_peripheral_export_replay_identifies_revision_and_reproduces_gate(bad):
    calibration = fitted_peripheral()
    validation = peripheral_validation(bad=bad)
    calibration.validate(validation)
    payload = build_diagnostic_report(calibration, validation, include_samples=True)
    assert payload["engine_id"] == PERIPHERAL_ENGINE and payload["schema_version"] == 2
    replayed = replay_diagnostic(json.loads(json.dumps(payload, allow_nan=False)))
    assert replayed["acceptance_report"] == payload["acceptance_report"]
    assert replayed["signal"]["model"]["selection"] == payload["signal"]["model"]["selection"]
    assert replayed["replay"]["desktop_input_enabled"] is False


def test_defaults_and_persisted_comparison_choice_preserve_hand_settings(tmp_path):
    assert Settings().gaze_engine == PERIPHERAL_ENGINE
    prior = Settings(gaze_engine="precision-openvino-v1", pinch_close=.27, filter_beta=.042,
                     auxiliary_scroll_sensitivity=1.2)
    path = tmp_path / "settings.json"
    prior.save(path)
    assert asdict(Settings.load(path)) == asdict(prior)
    assert type(create_gaze_calibration("precision-openvino-v1")) is PrecisionGazeCalibration
    assert type(create_gaze_calibration(PERIPHERAL_ENGINE)) is PeripheralGazeCalibration


def test_worker_precise_cost_uses_high_resolution_clock_not_capture_clock(monkeypatch):
    from tests.test_face_tracking import run_one, worker
    from tests.test_gaze import face
    eye = worker()
    eye.settings = replace(eye.settings, gaze_engine=PERIPHERAL_ENGINE)
    neural = Mock()

    def detect():
        monkeypatch.setattr("biogesture.face_tracking.time.perf_counter", lambda: 200.0025)

    def infer(*args):
        monkeypatch.setattr("biogesture.face_tracking.time.perf_counter", lambda: 200.004)
        return (0., 0., -1., 0., 0., 0.)

    neural.extract.side_effect = infer
    eye._make_neural = Mock(return_value=neural)
    run_one(eye, monkeypatch, [face()], timestamp=99.9, during_detection=detect)
    report = eye.latest_diagnostics()
    assert report["neural_ms"] == pytest.approx(1.5)
    assert report["inference_ms"] == pytest.approx(4)
    assert report["capture_to_result_ms"] == pytest.approx(100)
    assert report["gaze_engine"] == PERIPHERAL_ENGINE


def test_pointer_metadata_is_allowlisted_and_never_changes_approval():
    calibration = fitted_peripheral()
    calibration.validate(peripheral_validation())
    before = asdict(calibration.report)
    metadata = {"id": "ocular-one-euro-v1", "scope": "output_only", "min_cutoff": .3,
                "beta": 5., "derivative_cutoff": 1., "jump_distance": .16, "reset_gap_seconds": .25,
                "image": "not allowed", "username": "not allowed"}
    report = build_diagnostic_report(calibration, peripheral_validation(), context={"pointer_filter": metadata})
    assert report["context"]["pointer_filter"] == {k: v for k, v in metadata.items()
                                                  if k not in ("image", "username")}
    assert asdict(calibration.report) == before
    for bad in (True, "encoded image", math.nan, -1):
        metadata["beta"] = bad
        report = build_diagnostic_report(calibration, (), context={"pointer_filter": metadata})
        assert "pointer_filter" not in report["context"]
