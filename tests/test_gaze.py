"""Pure synthetic checks. These do not establish real-world gaze accuracy."""

from dataclasses import replace
import math

import numpy as np
import pytest

from biogesture.gaze import (
    CALIBRATION_TARGETS,
    VALIDATION_TARGETS,
    GazeCalibration,
    GazeObservation,
    GazeSession,
    extract_gaze_observation,
)
from biogesture.models import Landmark


def observed(timestamp=100.0, target=(0.5, 0.5), **changes):
    x, y = target
    iris_x, iris_y = (x - 0.5) * 0.3, (y - 0.5) * 0.25
    observation = GazeObservation(timestamp, (iris_x, iris_y, iris_x, iris_y, 0, .375, .3, 0, .5, .4), True, "")
    return replace(observation, **changes)


def trained():
    calibration = GazeCalibration()
    for timestamp, target in enumerate(CALIBRATION_TARGETS, 1):
        assert calibration.add_sample(observed(timestamp, target), target)
    assert calibration.fit()
    return calibration


def calibrated():
    calibration = trained()
    samples = [(observed(t, target), target) for t, target in enumerate(VALIDATION_TARGETS, 20)]
    assert calibration.validate(samples).accepted
    return calibration


def face(*, iris_x=0.0, iris_y=0.0):
    points = [Landmark(.5, .5) for _ in range(478)]
    for outer, inner, upper, lower, iris, x in (
        (33, 133, 159, 145, 468, .35), (362, 263, 386, 374, 473, .65),
    ):
        for index, xy in (
            (outer, (x - .05, .4)), (inner, (x + .05, .4)),
            (upper, (x, .38)), (lower, (x, .42)), (iris, (x + iris_x, .4 + iris_y)),
        ):
            points[index] = Landmark(*xy)
    points[1] = Landmark(.5, .55)
    return tuple(points)


def test_extracts_iris_geometry_without_claiming_screen_coordinates():
    observation = extract_gaze_observation(face(iris_x=.01, iris_y=.005), 1.0)
    assert observation.valid
    assert len(observation.features) == 10
    assert observation.features[:4] == pytest.approx((.1, .0375, .1, .0375))
    assert observation.features[6] == pytest.approx(.3)


def test_capture_is_already_mirrored_and_extraction_does_not_flip_it_again():
    original = face(iris_x=.012)
    mirrored = tuple(replace(point, x=1 - point.x) for point in original)
    a = extract_gaze_observation(original, 1.0)
    b = extract_gaze_observation(mirrored, 1.0)
    assert a.valid and b.valid
    assert b.features[0] == pytest.approx(-a.features[0])
    assert b.features[2] == pytest.approx(-a.features[2])


@pytest.mark.parametrize("indices", [(159, 145), (386, 374)])
def test_one_blink_is_enough_to_reject_the_observation(indices):
    points = list(face())
    points[indices[1]] = points[indices[0]]
    result = extract_gaze_observation(points, 1.0)
    assert not result.valid
    assert "Parpadeo" in result.reason


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_iris_is_rejected(value):
    points = list(face())
    points[468] = Landmark(value, .4)
    assert not extract_gaze_observation(points, 1.0).valid


def test_tiny_eyes_are_rejected_instead_of_extrapolating_distance():
    points = tuple(Landmark(.5 + (p.x - .5) * .1, .5 + (p.y - .5) * .1) for p in face())
    assert not extract_gaze_observation(points, 1.0).valid


def test_turned_head_and_iris_outside_eye_are_rejected():
    points = list(face())
    points[1] = Landmark(.8, .55)
    assert not extract_gaze_observation(points, 1.0).valid
    assert not extract_gaze_observation(face(iris_x=.08), 1.0).valid


@pytest.mark.parametrize("landmarks,time,width,height", [([], 1., 640, 480), (face(), math.nan, 640, 480),
                                                        (face(), 1., 0, 480), (face(), 1., 640, 0)])
def test_invalid_extraction_input_is_fail_closed(landmarks, time, width, height):
    assert not extract_gaze_observation(landmarks, time, width, height).valid


def test_calibration_cannot_point_until_independent_validation_passes():
    assert GazeCalibration().predict(observed()) is None
    calibration = trained()
    assert calibration.fitted and not calibration.ready
    assert calibration.predict(observed()) is None
    report = calibration.validate([(observed(t, target), target) for t, target in enumerate(VALIDATION_TARGETS, 20)])
    assert report.accepted and report.passed and report.samples == 4
    assert report.max_error < .005
    assert calibration.predict(observed(target=(.25, .75))) == pytest.approx((.25, .75), abs=.003)


def test_mapping_can_learn_mirrored_iris_orientation_without_implicit_screen_flip():
    calibration = GazeCalibration()

    def inverse_observation(timestamp, target):
        return observed(timestamp, (1 - target[0], target[1]))

    for t, target in enumerate(CALIBRATION_TARGETS, 1):
        calibration.add_sample(inverse_observation(t, target), target)
    assert calibration.fit()
    assert calibration.validate([(inverse_observation(t, target), target)
                                 for t, target in enumerate(VALIDATION_TARGETS, 20)]).accepted
    assert calibration.predict(inverse_observation(50, (.2, .8))) == pytest.approx((.2, .8), abs=.003)


def test_repeated_training_timestamps_and_invalid_observations_are_rejected():
    calibration = GazeCalibration()
    assert calibration.add_sample(observed(1), (.5, .5))
    assert not calibration.add_sample(observed(1), (.1, .1))
    assert not calibration.add_sample(observed(0), (.1, .1))
    assert not calibration.add_sample(observed(2, valid=False), (.1, .1))
    assert not calibration.add_sample(observed(3), (math.nan, .1))
    assert calibration.sample_count == 1


@pytest.mark.parametrize("features", [(), (0,) * 10, (math.nan,) * 10, (math.inf,) * 10, (1e308,) * 10])
def test_malformed_features_do_not_train_or_predict(features):
    observation = observed(features=features)
    assert not GazeCalibration().add_sample(observation, (.5, .5))
    assert calibrated().predict(observation) is None


def test_repeated_target_and_degenerate_iris_cannot_fit():
    calibration = GazeCalibration()
    for t in range(20):
        calibration.add_sample(observed(t), (.5, .5))
    assert not calibration.fit()
    calibration.reset()
    for t, target in enumerate(CALIBRATION_TARGETS):
        calibration.add_sample(observed(t), target)
    assert not calibration.fit()
    assert "variación ocular" in calibration.report.reason


def test_one_dimensional_eye_motion_cannot_fit_two_dimensional_pointer():
    calibration = GazeCalibration()
    for t, target in enumerate(CALIBRATION_TARGETS):
        calibration.add_sample(observed(t, (target[0], .5)), target)
    assert not calibration.fit()


def test_validation_cannot_reuse_training_points_or_frames():
    calibration = trained()
    assert not calibration.validate([(observed(t, target), target)
                                     for t, target in enumerate(CALIBRATION_TARGETS, 20)]).accepted
    assert not calibration.validate([(observed(t, target), target)
                                     for t, target in enumerate(VALIDATION_TARGETS, 1)]).accepted


def test_validation_requires_four_distinct_well_spread_targets():
    calibration = trained()
    assert not calibration.validate([(observed(t, (.3, .3)), (.3, .3)) for t in range(20, 30)]).accepted
    narrow = ((.2, .2), (.21, .21), (.22, .22), (.23, .23))
    assert not calibration.validate([(observed(t, target), target) for t, target in enumerate(narrow, 20)]).accepted


def test_validation_rejects_wrong_gaze_and_revokes_previous_readiness():
    calibration = calibrated()
    report = calibration.validate([(observed(t, (.5, .5)), target)
                                   for t, target in enumerate(VALIDATION_TARGETS, 40)])
    assert not report.accepted and report.max_error > .08
    assert not calibration.ready
    assert calibration.predict(observed()) is None


@pytest.mark.parametrize("index,value", [(4, .5), (5, .8), (6, .15), (6, .5), (7, .3), (8, .8), (9, .8)])
def test_outside_calibrated_posture_distance_and_position_do_not_extrapolate(index, value):
    calibration = calibrated()
    features = list(observed().features)
    features[index] = value
    assert calibration.predict(observed(features=tuple(features))) is None


def test_moderate_distance_and_position_variation_remain_inside_experimental_guard():
    calibration = calibrated()
    features = list(observed().features)
    features[6], features[8], features[9] = .27, .54, .43
    assert calibration.predict(observed(features=tuple(features))) == pytest.approx((.5, .5))


def test_opposite_iris_errors_cannot_cancel_into_a_false_central_gaze():
    calibration = calibrated()
    features = list(observed().features)
    features[0], features[2] = .09, -.09
    # Both individual eyes remain within trained coordinate margins, and
    # their mean is the calibrated center, but their disagreement is invalid.
    assert calibration.predict(observed(features=tuple(features))) is None


def test_natural_binocular_offset_is_learned_instead_of_requiring_identical_eyes():
    calibration = GazeCalibration()

    def asymmetric(timestamp, target):
        sample = observed(timestamp, target)
        features = list(sample.features)
        features[0] += .06
        features[2] -= .03
        return replace(sample, features=tuple(features))

    for t, target in enumerate(CALIBRATION_TARGETS, 1):
        calibration.add_sample(asymmetric(t, target), target)
    assert calibration.fit()
    assert calibration.validate([(asymmetric(t, target), target)
                                 for t, target in enumerate(VALIDATION_TARGETS, 20)]).accepted
    assert calibration.predict(asymmetric(100, (.5, .5))) == pytest.approx((.5, .5))


def test_new_training_data_and_reset_invalidate_calibration():
    calibration = calibrated()
    assert calibration.add_sample(observed(100), (.5, .5))
    assert not calibration.ready and not calibration.fitted
    calibration.reset()
    assert calibration.sample_count == 0


def noisy_eye_calibration(seed=21, noise=.003, *, outlier=False):
    """Synthetic eye motion plus small target-correlated nose displacement.

    The nose changes its correlation in holdout, as when a user settles their
    head after following the first targets. This is a numerical regression,
    not a recording or evidence that glasses are supported in practice.
    """
    generator = np.random.default_rng(seed)
    timestamp = 0

    def sample(target, *, training):
        nonlocal timestamp
        timestamp += 1
        x, y = target
        features = np.asarray([(x - .5) * .18, (y - .5) * .12] * 2
                              + [0, .375, .3, 0, .5, .4])
        features[:4] += generator.normal(0, noise, 4)
        features[4:6] += (np.asarray([x - .5, y - .5]) * .05 if training
                          else np.asarray([.015, -.015]))
        features[4:6] += generator.normal(0, .0003, 2)
        return GazeObservation(timestamp, tuple(features), True, "")

    calibration = GazeCalibration()
    for target in CALIBRATION_TARGETS:
        for index in range(17):
            frame = sample(target, training=True)
            if outlier and index == 3:
                features = list(frame.features)
                for axis in range(4):
                    features[axis] += .04
                frame = replace(frame, features=tuple(features))
            assert calibration.add_sample(frame, target)
    assert calibration.fit()
    validation = [(sample(target, training=False), target)
                  for target in VALIDATION_TARGETS for _ in range(17)]
    return calibration, validation


@pytest.mark.parametrize("seed", [1, 7, 21, 42])
@pytest.mark.parametrize("noise", [.0005, .003, .004])
def test_target_correlated_posture_does_not_replace_actual_eye_signal(seed, noise):
    calibration, pairs = noisy_eye_calibration(seed, noise)
    report = calibration.validate(pairs)
    assert report.accepted
    assert report.mean_error <= .04
    assert report.max_error <= .08
    assert report.target_count == 4
    assert report.worst_target in VALIDATION_TARGETS
    assert 0 < report.jitter_error < .04


def test_an_isolated_training_outlier_does_not_bias_the_target_representative():
    calibration, pairs = noisy_eye_calibration(outlier=True)
    assert calibration.validate(pairs).accepted


def test_longer_target_capture_does_not_weaken_fit_regularization():
    baseline = GazeCalibration()
    repeated = GazeCalibration()
    stamp = 0
    for index, target in enumerate(CALIBRATION_TARGETS):
        frame = observed(index + 1, target)
        features = list(frame.features)
        features[4] = (target[0] - .5) * .04
        features[5] += (target[1] - .5) * .04
        frame = replace(frame, features=tuple(features))
        assert baseline.add_sample(frame, target)
        for _ in range(3 + index * 7):
            stamp += 1
            assert repeated.add_sample(replace(frame, timestamp=stamp), target)
    assert baseline.fit() and repeated.fit()
    assert repeated._weights == pytest.approx(baseline._weights)


def test_held_out_target_labels_never_refit_the_learned_mapping():
    calibration, pairs = noisy_eye_calibration()
    before = calibration._weights.copy()
    wrong = [(frame, (1 - target[0], 1 - target[1])) for frame, target in pairs]
    assert not calibration.validate(wrong).accepted
    assert calibration._weights == pytest.approx(before)
    assert calibration.validate(pairs).accepted
    assert calibration._weights == pytest.approx(before)


def test_large_jitter_does_not_pass_merely_because_target_centers_are_correct():
    calibration = trained()
    pairs = []
    stamp = 20
    for target in VALIDATION_TARGETS:
        for offset in (-.1, .1) * 8:
            stamp += 1
            pairs.append((observed(stamp, (target[0] + offset, target[1])), target))
    report = calibration.validate(pairs)
    assert not report.accepted
    assert report.target_mean_error < .005
    assert report.jitter_error > .08
    assert report.max_error > .08
    assert "varió demasiado" in report.reason
    assert "Error medio" in report.reason
    assert "límites" in report.reason
    assert not calibration.ready


def test_one_bad_held_out_frame_is_not_hidden_by_target_aggregation():
    calibration = trained()
    pairs = []
    stamp = 20
    for target in VALIDATION_TARGETS:
        for index in range(17):
            stamp += 1
            actual_target = (target[0] + .12, target[1]) if index == 3 else target
            pairs.append((observed(stamp, actual_target), target))
    report = calibration.validate(pairs)
    assert report.mean_error < .04
    assert report.target_mean_error < .005
    assert report.max_error > .08
    assert not report.accepted


def test_correct_holdout_with_excessive_eye_noise_still_fails_accuracy_gate():
    calibration, pairs = noisy_eye_calibration(noise=.012)
    report = calibration.validate(pairs)
    assert not report.accepted
    assert report.mean_error > .04 or report.max_error > .08
    assert not calibration.ready


def active_session(start=100.0):
    session = GazeSession(calibrated())
    assert not session.update(observed(start), start).can_act
    state = session.update(observed(start + .2), start + .2)
    assert state.can_act
    return session


def test_session_is_calibration_locked_by_default_and_reset_requires_it_again():
    session = GazeSession()
    state = session.update(observed(), 100, victory=True)
    assert state.state == "CALIBRATION" and not state.can_act
    session = active_session()
    session.reset(101)
    assert not session.calibration.ready
    assert not session.update(observed(101), 101, victory=True).can_act


def test_blink_blocks_immediately_but_does_not_erase_calibration():
    session = active_session()
    state = session.update(observed(100.3, valid=False), 100.3)
    assert not state.can_act and state.pointer is None
    assert session.calibration.ready
    assert session.update(observed(100.4), 100.4).state == "RECOVERING"
    assert session.update(observed(100.6), 100.6).can_act


def test_recent_duplicate_holds_pointer_but_cannot_create_recovery_stability():
    session = GazeSession(calibrated())
    first = observed(100)
    assert not session.update(first, 100).can_act
    assert not session.update(first, 100.2).can_act
    assert session.update(observed(100.2), 100.2).can_act
    state = session.update(observed(100.2), 100.3)
    assert state.can_act and state.pointer == pytest.approx((.5, .5))


def test_repeated_frame_becomes_stale_and_does_not_reset_seventy_second_timeout():
    session = active_session()
    cached = observed(100.2)
    assert not session.update(cached, 100.46).can_act
    assert not session.update(cached, 170.19).paused
    assert session.update(cached, 170.21).paused


def test_none_stale_future_and_out_of_order_frames_cannot_move_pointer():
    for bad in (None, observed(99.9), observed(101), observed(100.1)):
        session = active_session()
        state = session.update(bad, 100.3)
        assert not state.can_act and state.pointer is None


def test_invalid_new_frame_prevents_replaying_an_older_valid_frame():
    session = active_session()
    assert not session.update(observed(100.4, valid=False), 100.4).can_act
    # An observation newer than the previous valid one, but older than the
    # blink, must not seed recovery. Neither can relabeling that blink's frame.
    assert not session.update(observed(100.3), 100.41).can_act
    assert not session.update(observed(100.4), 100.42).can_act
    assert not session.update(observed(100.5), 100.5).can_act
    assert session.update(observed(100.7), 100.7).can_act


def test_future_timestamp_does_not_permanently_poison_recovery_watermark():
    session = active_session()
    assert not session.update(observed(1e6), 100.3).can_act
    assert not session.update(observed(100.4), 100.4).can_act
    assert session.update(observed(100.6), 100.6).can_act


def test_rest_latches_before_accepting_new_person_and_does_not_auto_resume():
    session = active_session()
    state = session.update(observed(171), 171)
    assert state.paused and not state.can_act
    assert session.update(observed(171.2), 171.2).paused
    state = session.update(observed(171.4), 171.4, victory=True)
    assert not state.paused and state.can_act


def test_victory_cannot_resume_rest_without_valid_stable_gaze():
    session = active_session()
    assert session.update(None, 171, victory=True).paused
    assert session.update(observed(171.1), 171.1, victory=True).paused
    assert session.update(observed(171.3), 171.3, victory=True).can_act


def test_victory_can_resume_between_fresh_frames_after_stability_was_established():
    session = active_session()
    session.update(observed(171), 171)
    session.update(observed(171.2), 171.2)
    state = session.update(observed(171.2), 171.25, victory=True)
    assert state.can_act and not state.paused


def test_no_frame_since_start_eventually_enters_rest_without_calibrating():
    session = GazeSession()
    assert not session.update(None, 10).paused
    assert session.update(None, 80).paused


def test_losing_calibrated_geometry_blocks_actions_even_if_face_is_detected():
    session = active_session()
    features = list(observed().features)
    features[6] = .1
    assert not session.update(observed(100.3, features=tuple(features)), 100.3).can_act
    assert session.update(observed(171, features=tuple(features)), 171).paused


@pytest.mark.parametrize("now", [math.nan, math.inf, -math.inf, 99.0])
def test_invalid_and_reversing_clock_fail_closed(now):
    session = active_session()
    assert not session.update(observed(), now).can_act


@pytest.mark.parametrize("name", ["loss_timeout", "recovery_seconds", "max_frame_age"])
@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf])
def test_invalid_timing_configuration_is_rejected(name, value):
    with pytest.raises(ValueError):
        GazeSession(**{name: value})
