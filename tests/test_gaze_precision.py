"""Synthetic precision-engine contracts, not evidence of physical accuracy."""

from dataclasses import asdict, replace
import math
from unittest.mock import Mock, patch

import numpy as np
import pytest

from biogesture.gaze import GazeSession
from biogesture.gaze_precision import (
    PRECISION_ENGINE, PRECISION_SCHEMA, TRAINING_TARGETS, VALIDATION_TARGETS,
    PrecisionGazeCalibration, create_gaze_calibration, precision_observation_usable,
)
from biogesture.settings import Settings
from tests.test_gaze import observed


def neural_observed(timestamp, target=(.5, .5), **changes):
    vector = np.asarray((target[0] - .5, target[1] - .5, -1.))
    vector /= np.linalg.norm(vector)
    sample = replace(observed(timestamp, target), feature_schema=PRECISION_SCHEMA,
                     auxiliary_features=tuple(vector) + (0., 0., 0.))
    return replace(sample, **changes)


def fitted():
    calibration = PrecisionGazeCalibration()
    for stamp, target in enumerate(TRAINING_TARGETS, 1):
        assert calibration.add_sample(neural_observed(stamp, target), target)
    assert calibration.fit()
    return calibration


def validation():
    return [(neural_observed(stamp, target), target) for stamp, target in enumerate(VALIDATION_TARGETS, 30)]


def test_defaults_change_only_the_ocular_backend_and_keep_hand_settings():
    settings = Settings()
    assert settings.gaze_engine == "precision-openvino-v2"
    assert settings.cursor_mode == "index"
    assert asdict(settings.runtime_settings()) == asdict(settings)
    legacy = replace(settings, performance_mode="saving").runtime_settings()
    assert legacy.performance_mode == "optimal"
    with pytest.raises(ValueError):
        Settings(gaze_engine="download-and-execute").validate()


def test_factory_has_closed_identifiers_and_does_not_load_any_neural_runtime():
    with patch("builtins.__import__", wraps=__import__) as imports:
        assert create_gaze_calibration(PRECISION_ENGINE).engine_id == PRECISION_ENGINE
        assert create_gaze_calibration("legacy-ridge-v1").engine_id == "legacy-ridge-v1"
    assert not any(call.args[0].startswith(("openvino", "cv2", "mediapipe")) for call in imports.call_args_list)
    with pytest.raises(ValueError):
        create_gaze_calibration("some.module:function")


@pytest.mark.parametrize("changes", [
    {"auxiliary_features": ()}, {"auxiliary_features": (0., 0., -1., 0., 0., math.nan)},
    {"auxiliary_features": (0., 0., 1., 0., 0., 0.)},
    {"auxiliary_features": (0., 0., -1., 2., 0., 0.)},
    {"auxiliary_features": (0., 0., -2., 0., 0., 0.)},
    {"auxiliary_features": (1., 0., 0., 0., 0., 0.)},
    {"auxiliary_features": (0., 0., True, 0., 0., 0.)},
    {"feature_schema": "iris10-v1"}, {"valid": False},
])
def test_invalid_or_mismatched_neural_measurements_never_enter_training(changes):
    sample = neural_observed(1, **changes)
    assert not precision_observation_usable(sample)
    assert not PrecisionGazeCalibration().add_sample(sample, (.5, .5))


def test_thirteen_interleaved_targets_and_nine_new_targets_cover_the_screen():
    assert len(set(TRAINING_TARGETS)) == 13 and len(set(VALIDATION_TARGETS)) == 9
    assert all(math.dist(a, b) >= .04 for a in TRAINING_TARGETS for b in VALIDATION_TARGETS)
    assert abs(np.corrcoef(np.arange(13), np.array(TRAINING_TARGETS)[:, 1])[0, 1]) < .4
    for grid in (TRAINING_TARGETS, VALIDATION_TARGETS):
        assert min(np.ptp(np.array(grid), axis=0)) >= .6


def test_fitting_never_approves_control_and_requires_all_training_targets():
    calibration = PrecisionGazeCalibration()
    for stamp, target in enumerate(TRAINING_TARGETS[:-1], 1):
        calibration.add_sample(neural_observed(stamp, target), target)
    assert not calibration.fit()
    calibration = fitted()
    assert calibration.fitted and not calibration.ready
    sample = neural_observed(30)
    assert calibration.predict(sample) is None
    assert calibration.diagnostic_prediction(sample)["raw"] is not None


def test_independent_validation_can_approve_synthetic_mapping():
    calibration = fitted()
    assert calibration.validate(validation()).passed
    assert calibration.predict(neural_observed(100)) == pytest.approx((.5, .5), abs=.01)


def test_bad_validation_does_not_refit_select_or_enable_and_cannot_reuse_training():
    calibration = fitted()
    before = calibration.diagnostic_model()
    bad = [(neural_observed(stamp, (.5, .5)), target) for stamp, target in enumerate(VALIDATION_TARGETS, 30)]
    assert not calibration.validate(bad).passed
    assert calibration.diagnostic_model() == before
    assert calibration.predict(neural_observed(100)) is None
    assert not calibration.validate(calibration.training_samples).passed


def test_correlated_duplicate_frames_do_not_change_the_fit_or_model_selection():
    first, second = PrecisionGazeCalibration(), PrecisionGazeCalibration()
    stamp = 0
    for target in TRAINING_TARGETS:
        stamp += 1
        first.add_sample(neural_observed(stamp, target), target)
        for i in range(12):
            second.add_sample(neural_observed(stamp + i / 100, target), target)
    assert first.fit() and second.fit()
    a, b = first.diagnostic_model()["selection"], second.diagnostic_model()["selection"]
    assert a["family"] == b["family"]
    for key in ("ridge", "width", "training_cv_error"):
        assert a[key] == pytest.approx(b[key], abs=1e-14)


def test_out_of_posture_bounds_and_legacy_observations_do_not_move_cursor():
    calibration = fitted()
    assert calibration.validate(validation()).passed
    assert calibration.predict(observed(100)) is None
    wrong = neural_observed(100, auxiliary_features=(0., 0., -1., .4, 0., 0.))
    assert calibration.predict(wrong) is None
    session = GazeSession(calibration)
    assert not session.update(wrong, 100).can_act


def test_new_training_and_reset_revoke_readiness_and_drop_models():
    calibration = fitted()
    assert calibration.validate(validation()).passed
    assert calibration.add_sample(neural_observed(100), (.5, .5))
    assert not calibration.fitted and not calibration.ready
    calibration.reset()
    assert not calibration.training_samples and calibration.diagnostic_model()["selection"] is None


def test_face_worker_neural_factory_is_not_used_in_legacy_mode():
    from biogesture.face_tracking import FaceTrackingWorker
    eye = FaceTrackingWorker(Settings(gaze_engine="legacy-ridge-v1"), "assets/models/face_landmarker.task")
    with patch("builtins.__import__", wraps=__import__) as imports:
        assert eye._make_neural() is None
    assert not any("gaze_neural" in call.args[0] for call in imports.call_args_list)


def test_worker_adds_neural_output_without_changing_base_features(monkeypatch):
    from tests.test_face_tracking import run_one, worker
    from tests.test_gaze import face
    eye = worker()
    eye.settings = replace(eye.settings, gaze_engine=PRECISION_ENGINE)
    neural = Mock()
    neural.extract.return_value = (0., 0., -1., 0., 0., 0.)
    eye._make_neural = Mock(return_value=neural)
    run_one(eye, monkeypatch, [face()], timestamp=99.9)
    result = eye.latest()
    assert result.valid and result.feature_schema == PRECISION_SCHEMA
    assert len(result.features) == 10 and result.auxiliary_features == neural.extract.return_value
    assert eye.latest_diagnostics()["gaze_engine"] == PRECISION_ENGINE
    neural.close.assert_called_once_with()
    assert eye._neural is None


@pytest.mark.parametrize("value", [(0., 0., 0., 0., 0., 0.), (math.nan,) * 6])
def test_invalid_cnn_output_is_not_published_as_valid_gaze(monkeypatch, value):
    from tests.test_face_tracking import run_one, worker
    from tests.test_gaze import face
    eye = worker()
    neural = Mock()
    neural.extract.return_value = value
    eye._make_neural = Mock(return_value=neural)
    run_one(eye, monkeypatch, [face()], timestamp=99.9)
    assert not eye.latest().valid
    neural.close.assert_called_once_with()


def test_neural_resources_close_after_inference_failure(monkeypatch):
    from tests.test_face_tracking import run_one, worker
    from tests.test_gaze import face
    eye = worker()
    neural = Mock()
    neural.extract.side_effect = RuntimeError("synthetic inference failure")
    eye._make_neural = Mock(return_value=neural)
    run_one(eye, monkeypatch, [face()], timestamp=99.9)
    assert not eye.latest().valid
    neural.close.assert_called_once_with()
    assert eye._neural is None


def test_small_chair_posture_shift_does_not_drift_calibrated_gaze():
    calibration = PrecisionGazeCalibration()
    for stamp, target in enumerate(TRAINING_TARGETS, 1):
        base = neural_observed(stamp, target)
        # Tiny incidental head angle variation during still-head calibration.
        yaw = (target[0] - .5) * .01
        pitch = (target[1] - .5) * .01
        sample = replace(base, auxiliary_features=base.auxiliary_features[:3] + (yaw, pitch, 0.))
        assert calibration.add_sample(sample, target)
    assert calibration.fit()
    assert calibration.validate(validation()).passed
    shifted = neural_observed(120, (.5, .5))
    shifted = replace(shifted, auxiliary_features=shifted.auxiliary_features[:3] + (.08, -.06, .02))
    predicted = calibration.predict(shifted)
    assert predicted is not None
    assert math.dist(predicted, (.5, .5)) < .015


def test_refine_for_session_incorporates_consistent_validation_points_and_ignores_outliers():
    calibration = fitted()
    valid_pairs = validation()
    assert calibration.validate(valid_pairs).passed
    assert calibration.refine_for_session(valid_pairs)
    assert len(calibration._personal_model[2]) == len(TRAINING_TARGETS) + len(VALIDATION_TARGETS)
    assert calibration.predict(neural_observed(200, (.07, .93))) == pytest.approx((.07, .93), abs=.02)

    calibration2 = fitted()
    corrupted = [(neural_observed(stamp, (.5, .5)), target) for stamp, target in enumerate(VALIDATION_TARGETS, 30)]
    calibration2.unlock()
    assert not calibration2.refine_for_session(corrupted)


def test_initial_center_stare_and_relaxed_desktop_eyelids_stay_centered():
    calibration = PrecisionGazeCalibration(mean_error_limit=0.12, max_error_limit=0.22)
    for stamp, target in enumerate(TRAINING_TARGETS, 1):
        base = neural_observed(stamp, target)
        features = list(base.features)
        aux = list(base.auxiliary_features)
        aux[4] = 0.22  # Natural seated head pitch
        if target == (.5, .5):
            # Initial wide-eyed stare on the very first calibration point
            features[1] -= 0.012
            features[3] -= 0.012
        sample = replace(base, features=tuple(features), auxiliary_features=tuple(aux))
        assert calibration.add_sample(sample, target)
    assert calibration.fit()
    valid_pairs = []
    for stamp, target in enumerate(VALIDATION_TARGETS, 30):
        base = neural_observed(stamp, target)
        aux = list(base.auxiliary_features)
        aux[4] = 0.22
        valid_pairs.append((replace(base, auxiliary_features=tuple(aux)), target))
    assert calibration.validate(valid_pairs).passed
    assert calibration.refine_for_session(valid_pairs)
    assert calibration._session_y_offset < -0.015
    # Simulate relaxed upper eyelids on the live desktop at screen center and corners
    center_obs = neural_observed(150, (.5, .5))
    f_relaxed = list(center_obs.features)
    f_relaxed[1] += 0.010
    f_relaxed[3] += 0.010
    a_relaxed = list(center_obs.auxiliary_features)
    a_relaxed[1] += 0.020 * (-a_relaxed[2])
    norm = float(np.linalg.norm(a_relaxed[:3]))
    a_relaxed[:3] = [v / norm for v in a_relaxed[:3]]
    a_relaxed[4] = 0.22
    relaxed_sample = replace(center_obs, features=tuple(f_relaxed), auxiliary_features=tuple(a_relaxed))
    predicted = calibration.predict(relaxed_sample)
    assert predicted is not None
    assert abs(predicted[0] - .5) < .015
    assert abs(predicted[1] - .5) < .02
    corner_obs = neural_observed(160, (.92, .92))
    a_corner = list(corner_obs.auxiliary_features)
    a_corner[4] = 0.22
    corner_pred = calibration.predict(replace(corner_obs, auxiliary_features=tuple(a_corner)))
    assert corner_pred is not None and corner_pred[0] > .95 and corner_pred[1] > .94


def test_z_distance_and_chair_parallax_compensation_maintain_edge_reach():
    calibration = fitted()
    assert calibration.validate(validation()).passed
    # Simulate leaning back in the chair (interocular scale drops by ~15% and angular excursion compresses)
    CompressedTarget = (.5 + (.8 - .5) * .91, .5 + (.8 - .5) * .91)
    obs = neural_observed(120, CompressedTarget)
    features = list(obs.features)
    features[6] *= 0.86  # 14% smaller interocular span in frame (further from webcam)
    leaned_back = replace(obs, features=tuple(features))
    predicted = calibration.predict(leaned_back)
    assert predicted is not None
    assert math.dist(predicted, (.8, .8)) < 0.015


def test_record_click_feedback_adapts_online_bias_and_posture_baseline():
    calibration = fitted()
    assert calibration.validate(validation()).passed
    obs = neural_observed(130, (.48, .48))
    features = list(obs.features)
    features[6] *= 0.92
    features[9] += 0.02
    sample = replace(obs, features=tuple(features))
    before = calibration.predict(sample)
    for _ in range(5):
        assert calibration.record_click_feedback(sample, (.5, .5))
    after = calibration.predict(sample)
    assert math.dist(after, (.5, .5)) < math.dist(before, (.5, .5))
    # Wild outlier click targets (>12% away from gaze) are rejected
    assert not calibration.record_click_feedback(sample, (.95, .95))



