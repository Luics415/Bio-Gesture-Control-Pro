"""Diagnostics inspect synthetic fits without establishing physical accuracy."""

from dataclasses import FrozenInstanceError, replace
import builtins
import json
import math
import socket

import numpy as np
import pytest

from biogesture.gaze import CALIBRATION_TARGETS, VALIDATION_TARGETS, GazeCalibration, GazeObservation, GazeSession
from biogesture.gaze_diagnostics import build_diagnostic_report, diagnostic_prediction


def observed(timestamp=100.0, target=(.5, .5), *, bias=(0., 0.), y_scale=.25):
    x, y = target
    ix, iy = (x - .5) * .3 + bias[0], (y - .5) * y_scale + bias[1]
    return GazeObservation(timestamp, (ix, iy, ix, iy, 0., .375, .3, 0., .5, .4), True, "")


def fitted(*, count=3, y_scale=.25):
    calibration = GazeCalibration()
    timestamp = 1000.
    for target in CALIBRATION_TARGETS:
        for _ in range(count):
            assert calibration.add_sample(observed(timestamp, target, y_scale=y_scale), target)
            timestamp += .05
    assert calibration.fit()
    return calibration


def validation(*, count=3, bias=(0., 0.), y_scale=.25):
    pairs = []
    timestamp = 1010.
    for target in VALIDATION_TARGETS:
        for _ in range(count):
            pairs.append((observed(timestamp, target, bias=bias, y_scale=y_scale), target))
            timestamp += .05
    return pairs


def test_default_report_omits_replay_samples_and_is_json_safe():
    report = build_diagnostic_report(fitted(), validation())
    encoded = json.dumps(report, allow_nan=False)
    assert json.loads(encoded)["schema_version"] == 1
    assert isinstance(report["schema_version"], int)
    assert report["samples_included"] is False and "samples" not in report
    assert report["diagnostic_only"] is True
    assert len(report["training"]) == 9 and len(report["validation"]) == 4
    assert report["acceptance_report"]["mean_error"] is None


@pytest.mark.parametrize("validated", [False, True])
def test_every_diagnostic_api_preserves_model_report_and_readiness(validated):
    calibration = fitted()
    pairs = validation()
    if validated:
        assert calibration.validate(pairs).accepted
    weights = calibration._weights.copy()
    original_report, ready = calibration.report, calibration.ready
    prediction = calibration.predict(pairs[0][0])
    before = calibration.training_samples
    build_diagnostic_report(calibration, pairs, include_samples=True)
    diagnostic_prediction(calibration, pairs[0][0])
    calibration.diagnostic_model()
    assert calibration.ready is ready and calibration.report is original_report
    assert calibration.predict(pairs[0][0]) == prediction
    np.testing.assert_array_equal(weights, calibration._weights)
    assert calibration.training_samples == before


def test_fitted_but_unvalidated_model_can_be_drawn_but_cannot_control():
    calibration = fitted()
    observation = observed(1100., (.3, .7))
    prediction = diagnostic_prediction(calibration, observation)
    assert prediction["bounded"] == pytest.approx((.3, .7), abs=.003)
    assert "no autoriza" in prediction["reason"]
    assert calibration.predict(observation) is None
    session = GazeSession(calibration)
    assert not session.update(observation, observation.timestamp, victory=True).can_act


def test_raw_prediction_outside_geometry_remains_labelled_blocked():
    calibration = fitted()
    sample = observed()
    sample = replace(sample, features=sample.features[:6] + (.9,) + sample.features[7:])
    result = diagnostic_prediction(calibration, sample)
    assert result["raw"] == pytest.approx((.5, .5), abs=.003)
    assert result["bounded"] is None and "Bloqueado" in result["reason"]
    assert calibration.predict(sample) is None


def test_raw_prediction_outside_screen_is_not_clipped_into_validity():
    calibration = fitted()
    sample = observed(target=(1.12, .5))
    result = diagnostic_prediction(calibration, sample)
    assert result["raw"][0] > 1.04 and result["bounded"] is None
    assert "Bloqueado" in result["reason"]


@pytest.mark.parametrize("sample", [None, GazeObservation(1), observed(math.nan),
                                   replace(observed(), features=(math.nan,) * 10)])
def test_invalid_observation_returns_no_diagnostic_prediction(sample):
    result = diagnostic_prediction(fitted(), sample)
    assert result["raw"] is None and result["bounded"] is None
    json.dumps(result, allow_nan=False)


def test_unfitted_model_and_empty_samples_produce_useful_report():
    calibration = GazeCalibration()
    report = build_diagnostic_report(calibration, ())
    assert report["fitted"] is False
    assert report["summary"]["training"]["mean_error"] is None
    assert report["signal"]["model"]["coefficients"] is None
    assert any("Todavía" in text for text in report["hypotheses"])
    assert diagnostic_prediction(calibration, observed())["raw"] is None
    json.dumps(report, allow_nan=False)


def test_target_metrics_are_calculated_from_same_estimates_as_validation():
    calibration = fitted()
    pairs = validation(bias=(.021, -.010))
    accepted_report = calibration.validate(pairs)
    report = build_diagnostic_report(calibration, pairs)
    summary = report["summary"]["validation"]
    assert summary["mean_error"] == pytest.approx(accepted_report.mean_error)
    assert summary["max_error"] == pytest.approx(accepted_report.max_error)
    assert summary["jitter"] == pytest.approx(accepted_report.jitter_error)
    for point in report["validation"]:
        prediction = diagnostic_prediction(calibration, next(o for o, t in pairs if list(t) == point["target"]))["bounded"]
        assert point["predicted_mean"] == pytest.approx(prediction)
        assert point["bias_xy"] == pytest.approx(np.asarray(prediction) - point["target"])
        assert point["mean_error"] == pytest.approx(math.dist(prediction, point["target"]))
        assert point["n"] == 3 and point["rejected"] == 0


def test_invalid_samples_are_counted_instead_of_disappearing_from_report():
    calibration = fitted()
    pairs = validation()
    pairs.extend(((GazeObservation(1050), (.3, .3)), (None, None), "malformed"))
    report = build_diagnostic_report(calibration, pairs)
    assert report["summary"]["validation"]["n"] == len(pairs)
    assert report["summary"]["validation"]["rejected"] == 3
    assert report["validation"][0]["rejected"] == 1
    assert any("no incluyen esos rechazos" in text for text in report["hypotheses"])


def test_stable_position_bias_is_not_reported_as_proven_user_or_glasses_error():
    report = build_diagnostic_report(fitted(), validation(bias=(.03, .015)))
    assert report["summary"]["validation"]["jitter"] < .001
    assert report["summary"]["validation"]["mean_error"] > .04
    text = " ".join(report["hypotheses"])
    assert "desfase" in text and "no demuestra" in text and "generalización" in text
    assert "no identifican por sí solos" in text


def test_raw_failed_frame_is_counted_even_when_other_frames_are_centered():
    calibration = fitted()
    pairs = validation()
    pairs.append((observed(1050., (1.12, .3)), (.7, .3)))
    assert not calibration.validate(pairs).accepted
    report = build_diagnostic_report(calibration, pairs)
    assert report["summary"]["validation"]["rejected"] == 1
    point = next(p for p in report["validation"] if p["target"] == [.7, .3])
    assert point["raw_max_error"] > .4
    assert report["ready"] is False


def test_feature_medians_ranges_and_posture_do_not_claim_distance_in_meters():
    report = build_diagnostic_report(fitted(), validation(bias=(.01, .005)))
    assert len(report["features"]) == 10 and len(report["posture"]) == 6
    assert report["features"][0]["median_shift"] == pytest.approx(.01)
    assert report["features"][0]["training"]["range"] == pytest.approx(.24)
    assert report["posture"][2]["name"] == "eye_span_frame_ratio"
    assert report["signal"]["iris_condition_ratio"] > 1


def test_low_vertical_signal_shows_high_sensitivity_without_changing_gate():
    calibration = fitted(count=14, y_scale=.014)
    pairs = validation(count=14, bias=(0., .0025), y_scale=.014)
    assert not calibration.validate(pairs).accepted
    report = build_diagnostic_report(calibration, pairs)
    assert report["signal"]["target_median_range"][1] == pytest.approx(.0112)
    coefficients = report["signal"]["model"]["coefficients"]
    vertical_gain = coefficients[1][1] + coefficients[3][1]
    assert vertical_gain > 65
    assert report["summary"]["validation"]["mean_error"] > .15
    assert report["summary"]["validation"]["jitter"] < .001
    assert report["limits"] == {"mean_error": .04, "max_error": .08}


def test_model_coefficients_reproduce_raw_prediction_in_original_units():
    calibration = fitted()
    model = calibration.diagnostic_model()
    observation = observed(1100, (.24, .81))
    raw = np.asarray(observation.features[:6]) @ model["coefficients"] + model["intercept"]
    assert raw == pytest.approx(diagnostic_prediction(calibration, observation)["raw"])
    model["coefficients"][0][0] = 1e100
    assert calibration.diagnostic_model()["coefficients"][0][0] != 1e100


def test_numeric_export_is_explicit_and_all_timestamps_are_relative():
    report = build_diagnostic_report(fitted(), validation(), include_samples=True)
    assert report["samples_included"] is True
    assert len(report["samples"]) == 39
    assert report["samples"][0]["t_seconds"] == 0
    assert all(0 <= sample["t_seconds"] < 20 for sample in report["samples"])
    assert all(len(sample["features"]) == 10 for sample in report["samples"])
    assert {sample["phase"] for sample in report["samples"]} == {"training", "validation"}
    assert '"timestamp"' not in json.dumps(report)


def test_export_can_replay_fit_and_validation_without_images_or_saved_weights():
    calibration = fitted()
    pairs = validation(bias=(.023, .009))
    original = calibration.validate(pairs)
    report = json.loads(json.dumps(build_diagnostic_report(calibration, pairs, include_samples=True), allow_nan=False))
    replay = GazeCalibration(mean_error_limit=report["limits"]["mean_error"],
                             max_error_limit=report["limits"]["max_error"])
    held_out = []
    for item in report["samples"]:
        observation = GazeObservation(item["t_seconds"], tuple(item["features"]), item["valid"], item["reason"])
        if item["phase"] == "training":
            assert replay.add_sample(observation, item["target"])
        else:
            held_out.append((observation, item["target"]))
    assert replay.fit()
    repeated = replay.validate(held_out)
    assert repeated.mean_error == pytest.approx(original.mean_error)
    assert repeated.max_error == pytest.approx(original.max_error)
    assert repeated.accepted == original.accepted


def test_export_context_allowlist_excludes_images_names_paths_and_absolute_time():
    context = {"name": "private-name", "path": "C:/private/path", "background": "dark",
               "monitor": {"width": 1920, "height": 1080, "name": "private-name"},
               "telemetry": {"camera": {"requested_width": 640, "path": "private"},
                             "worker": {"timestamp": 12345., "image_width": 640, "eye_width_px": (20., 21.),
                                        "frame": np.zeros((2, 2, 3)), "inference_ms": math.inf}}}
    captures = [{"phase": "validation", "point_index": 1, "samples": 14, "target": (.3, .3),
                 "outcome": "complete", "attempts": 2, "rejected": {"blink": 2}, "timestamp": 5000., "image": b"image"}]
    report = build_diagnostic_report(fitted(), validation(), context=context, capture_points=captures)
    encoded = json.dumps(report, allow_nan=False)
    assert "private" not in encoded and '"timestamp"' not in encoded
    assert report["context"]["telemetry"]["worker"]["inference_ms"] is None
    assert report["context"]["telemetry"]["worker"]["eye_width_px"] == [20., 21.]
    assert report["capture_points"][0]["attempts"] == 2
    assert report["capture_points"][0]["rejected"] == {"blink": 2}


def test_detached_training_samples_cannot_mutate_internal_features():
    calibration = GazeCalibration()
    sample = observed(1)
    mutable_features = list(sample.features)
    assert calibration.add_sample(replace(sample, features=mutable_features), (.5, .5))
    snapshot = calibration.training_samples
    assert isinstance(snapshot[0][0].features, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot[0][0].valid = False
    mutable_features[0] = .2
    assert snapshot[0][0].features[0] == 0.


def test_reports_never_open_files_or_network_connections(monkeypatch):
    calibration, pairs = fitted(), validation()
    def forbidden(*args, **kwargs):
        raise AssertionError("Diagnostics must not perform I/O")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    report = build_diagnostic_report(calibration, pairs, include_samples=True)
    assert report["samples"]


def test_null_or_unknown_context_objects_are_not_stringified():
    class Private:
        def __str__(self):
            raise AssertionError("Must not stringify unknown context")
    report = build_diagnostic_report(GazeCalibration(), (), context={"camera_width": Private()})
    assert report["context"]["camera_width"] is None
    assert build_diagnostic_report(GazeCalibration(), (), context=Private())["context"] == {}
