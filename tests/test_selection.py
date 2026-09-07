from dataclasses import replace
import math

import pytest

from biogesture.selection import PrincipalHandSelector
from tests.test_gestures import hand


def sample(label, x, timestamp):
    return hand("pointer", timestamp, handedness=label, dx=(x - 0.5) * 640)


def acquire(selector, label="Right", x=0.3, start=10.0):
    output = None
    for delta in (0.0, 0.1, 0.2, 0.35):
        point = sample(label, x, start + delta)
        output = selector.update([point], start + delta)
    return output


@pytest.mark.parametrize("label", ["Left", "Right"])
def test_either_hand_becomes_principal_on_the_first_valid_frame(label):
    selector = PrincipalHandSelector()
    current = sample(label, 0.3, 10)
    output = selector.update([current], 10)
    assert output.sample is current
    assert output.auxiliary is None
    assert output.status == "PRINCIPAL"
    assert selector.selected


@pytest.mark.parametrize("chosen_label", ["Left", "Right"])
def test_two_hands_at_start_need_only_one_single_hand_frame_to_choose(chosen_label):
    selector = PrincipalHandSelector()
    for index in range(20):
        now = 10 + index * 0.1
        hands = [sample("Right", 0.3, now), sample("Left", 0.7, now)]
        output = selector.update(hands if index % 2 else hands[::-1], now)
        assert output.sample is None
        assert "UNA MANO" in output.status
        assert not selector.selected
    chosen = sample(chosen_label, 0.7, 12)
    assert selector.update([chosen], 12).sample is chosen
    assert selector.selected


@pytest.mark.parametrize("label", ["Left", "Right"])
def test_detector_order_changes_do_not_change_principal_or_auxiliary(label):
    selector = PrincipalHandSelector()
    acquire(selector, label)
    other = "Left" if label == "Right" else "Right"
    for index in range(10):
        now = 10.4 + index * 0.05
        principal, secondary = sample(label, 0.3, now), sample(other, 0.7, now)
        hands = [principal, secondary] if index % 2 else [secondary, principal]
        output = selector.update(hands, now)
        assert output.sample is principal
        assert output.auxiliary is secondary
        assert output.hand_count == 2


@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_new_secondary_at_old_position_cannot_steal_a_moving_principal(label, reverse_order):
    selector = PrincipalHandSelector()
    acquire(selector, label, 0.3)
    principal = sample(label, 0.5, 10.4)
    secondary = sample("Left" if label == "Right" else "Right", 0.3, 10.4)
    hands = [principal, secondary]
    output = selector.update(hands[::-1] if reverse_order else hands, 10.4)
    assert output.sample is principal
    assert output.auxiliary is secondary
    assert selector.selected
    principal = sample(label, 0.5, 10.45)
    secondary = sample(secondary.handedness, 0.3, 10.45)
    output = selector.update([secondary, principal], 10.45)
    assert output.sample is principal
    assert output.auxiliary is secondary


@pytest.mark.parametrize("label", ["Left", "Right"])
def test_new_secondary_far_from_continuous_principal_does_not_block_selection(label):
    selector = PrincipalHandSelector()
    acquire(selector, label, 0.3)
    principal = sample(label, 0.31, 10.4)
    secondary = sample("Left" if label == "Right" else "Right", 0.7, 10.4)
    assert selector.update([secondary, principal], 10.4).sample is principal


def test_single_hand_continuous_label_jitter_preserves_free_principal_choice():
    for initial_label in ("Left", "Right"):
        selector = PrincipalHandSelector()
        acquire(selector, initial_label, 0.3)
        other_label = "Left" if initial_label == "Right" else "Right"
        for index, label in enumerate((other_label, initial_label, other_label, initial_label)):
            timestamp = 10.4 + index * 0.05
            principal = sample(label, 0.3 + index * 0.01, timestamp)
            assert selector.update([principal], timestamp).sample is principal


def test_two_new_hands_after_empty_frame_cannot_replace_principal_with_opposite_anatomy():
    selector = PrincipalHandSelector()
    acquire(selector, "Right", 0.3)
    selector.update([], 10.4)
    output = selector.update([sample("Left", 0.3, 10.5), sample("Left", 0.7, 10.5)], 10.5)
    assert output.sample is None
    assert output.auxiliary is None
    assert "RECUPERANDO" in output.status
    principal, auxiliary = sample("Right", 0.7, 10.55), sample("Left", 0.3, 10.55)
    recovered = selector.update([auxiliary, principal], 10.55)
    assert recovered.sample is principal
    assert recovered.auxiliary is auxiliary


def test_two_existing_tracks_after_gap_do_not_accept_one_sided_anatomy_replacement():
    selector = PrincipalHandSelector()
    acquire(selector, "Right", 0.3)
    selector.update([sample("Right", 0.3, 10.4), sample("Left", 0.7, 10.4)], 10.4)
    selector.update([], 10.45)
    output = selector.update([sample("Left", 0.3, 10.5), sample("Left", 0.7, 10.5)], 10.5)
    assert output.sample is None
    assert "RECUPERANDO" in output.status
    principal, auxiliary = sample("Right", 0.7, 10.55), sample("Left", 0.3, 10.55)
    recovered = selector.update([principal, auxiliary], 10.55)
    assert recovered.sample is principal
    assert recovered.auxiliary is auxiliary


def test_remaining_secondary_cannot_take_cursor_even_at_old_principal_position():
    selector = PrincipalHandSelector()
    acquire(selector)
    selector.update([sample("Right", 0.3, 10.4), sample("Left", 0.7, 10.4)], 10.4)
    for index in range(30):
        now = 10.5 + index * 0.1
        x = max(0.3, 0.7 - index * 0.03)
        auxiliary = sample("Left", x, now)
        output = selector.update([auxiliary], now)
        assert output.sample is None
        assert output.auxiliary is auxiliary
        assert selector.selected
        assert output.status == "AUXILIAR"


def test_missing_principal_may_return_while_secondary_remains_far_away():
    selector = PrincipalHandSelector()
    acquire(selector)
    selector.update([sample("Right", 0.3, 10.4), sample("Left", 0.7, 10.4)], 10.4)
    for now in (10.5, 10.6, 10.7):
        assert selector.update([sample("Left", 0.7, now)], now).sample is None
    principal = sample("Right", 0.3, 10.8)
    assert selector.update([sample("Left", 0.7, 10.8), principal], 10.8).sample is principal


def test_overlapping_crossing_recovers_on_the_next_clear_frame_without_a_new_choice():
    selector = PrincipalHandSelector()
    acquire(selector, x=0.4)
    selector.update([sample("Right", 0.4, 10.4), sample("Left", 0.6, 10.4)], 10.4)
    output = selector.update([sample("Left", 0.51, 10.5), sample("Right", 0.49, 10.5)], 10.5)
    assert output.sample is None
    assert output.auxiliary is None
    assert "RECUPERANDO" in output.status
    for index in range(5):
        now = 10.6 + index * 0.1
        principal, auxiliary = sample("Right", 0.7, now), sample("Left", 0.3, now)
        output = selector.update([auxiliary, principal], now)
        assert output.sample is principal
        assert output.auxiliary is auxiliary
    assert selector.selected


@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_fast_opposite_hands_swap_positions_without_swapping_roles(label, reverse_order):
    selector = PrincipalHandSelector()
    other = "Left" if label == "Right" else "Right"
    acquire(selector, label)
    selector.update([sample(label, 0.3, 10.4), sample(other, 0.7, 10.4)], 10.4)
    principal, auxiliary = sample(label, 0.7, 10.5), sample(other, 0.3, 10.5)
    hands = [principal, auxiliary]
    output = selector.update(hands[::-1] if reverse_order else hands, 10.5)
    assert output.sample is principal
    assert output.auxiliary is auxiliary


def test_handedness_label_jitter_does_not_replace_principal():
    selector = PrincipalHandSelector()
    acquire(selector)
    for index, label in enumerate(("Left", "Right", "Right", "Left", "Right")):
        now = 10.4 + index * 0.05
        principal = sample(label, 0.3, now)
        secondary = sample("Left", 0.7, now)
        assert selector.update([secondary, principal], now).sample is principal


def test_brief_empty_frame_does_not_reassign_visible_secondary():
    selector = PrincipalHandSelector()
    acquire(selector)
    selector.update([sample("Right", 0.3, 10.4), sample("Left", 0.7, 10.4)], 10.4)
    selector.update([sample("Left", 0.7, 10.5)], 10.5)
    selector.update([], 10.6)
    assert selector.update([sample("Left", 0.7, 10.7)], 10.7).sample is None


def test_opposite_hand_after_short_occlusion_cannot_replace_principal_at_same_position():
    selector = PrincipalHandSelector()
    acquire(selector, "Right", 0.3)
    assert selector.update([], 10.4).sample is None
    output = selector.update([sample("Left", 0.3, 10.5)], 10.5)
    assert output.sample is None
    assert output.auxiliary.handedness == "Left"
    assert output.status == "AUXILIAR"
    assert selector.selected
    principal = sample("Right", 0.3, 10.55)
    assert selector.update([principal], 10.55).sample is principal


def test_same_hand_may_reappear_after_short_occlusion_without_new_role():
    selector = PrincipalHandSelector()
    acquire(selector, "Left", 0.3)
    selector.update([], 10.4)
    principal = sample("Left", 0.3, 10.5)
    assert selector.update([principal], 10.5).sample is principal


def test_camera_interruption_is_not_evidence_both_hands_left():
    selector = PrincipalHandSelector()
    acquire(selector)
    selector.suspend()
    output = selector.update([sample("Left", 0.3, 10.4)], 10.4)
    assert output.sample is None
    assert output.status == "AUXILIAR"
    principal = sample("Right", 0.3, 10.45)
    assert selector.update([principal], 10.45).sample is principal


def test_long_result_gap_cannot_implicitly_select_a_new_hand():
    selector = PrincipalHandSelector()
    acquire(selector)
    assert selector.update([sample("Left", 0.3, 12)], 12).sample is None
    assert selector.selected


def test_low_confidence_visible_hand_does_not_rearm_as_if_absent():
    selector = PrincipalHandSelector()
    acquire(selector)
    selector.suspend()
    for index in range(20):
        now = 10.4 + index * 0.1
        output = selector.update([replace(sample("Left", 0.3, now), confidence=0.1)], now)
        assert output.sample is None
    assert selector.selected


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("amplitude", [60, 120, 180])
def test_continuous_quick_lateral_waves_preserve_principal_at_different_frame_rates(fps, amplitude):
    selector = PrincipalHandSelector()
    acquire(selector, x=0.5)
    for index in range(1, fps * 2 + 1):
        now = 10.35 + index / fps
        principal = hand("palm", now, dx=amplitude * math.sin(2 * math.pi * 2 * index / fps))
        output = selector.update([principal], now)
        assert output.sample is principal, (fps, amplitude, index, output.status)


def test_large_principal_displacement_does_not_create_a_manual_recovery_lock():
    selector = PrincipalHandSelector()
    acquire(selector, x=0.2)
    principal = sample("Right", 0.85, 10.35 + 1 / 15)
    assert selector.update([principal], 10.35 + 1 / 15).sample is principal
    assert selector.selected


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("amplitude", [120, 180])
@pytest.mark.parametrize("missing", [3, 7])
def test_one_lost_frame_during_lateral_reversal_preserves_consistent_principal(fps, amplitude, missing):
    selector = PrincipalHandSelector()
    acquire(selector, x=0.5)
    for index in range(1, fps + 1):
        now = 10.35 + index / fps
        principal = hand("palm", now, dx=amplitude * math.sin(2 * math.pi * 2 * index / fps))
        output = selector.update([] if index == missing else [principal], now)
        if index == missing:
            assert output.sample is None
        else:
            assert output.sample is principal, (fps, amplitude, missing, index, output.status)


def test_short_gap_returns_auxiliary_separately_and_recovers_a_repositioned_principal():
    selector = PrincipalHandSelector()
    acquire(selector, x=0.5)
    selector.update([], 10.4)
    auxiliary = hand("palm", 10.5, dx=130, handedness="Left")
    output = selector.update([auxiliary], 10.5)
    assert output.sample is None
    assert output.auxiliary is auxiliary
    principal = hand("palm", 10.55, dx=130, dy=-180)
    assert selector.update([principal], 10.55).sample is principal
    assert selector.selected


@pytest.mark.parametrize("label", ["Left", "Right"])
def test_one_initial_frame_is_enough_before_both_roles_return_together(label):
    selector = PrincipalHandSelector()
    principal = sample(label, 0.3, 10)
    assert selector.update([principal], 10).sample is principal
    other = "Left" if label == "Right" else "Right"
    principal, auxiliary = sample(label, 0.3, 10.03), sample(other, 0.7, 10.03)
    output = selector.update([auxiliary, principal], 10.03)
    assert output.sample is principal
    assert output.auxiliary is auxiliary


@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("gap", [.05, .5, 5, 60])
@pytest.mark.parametrize("both_return", [False, True])
def test_missing_frames_of_any_duration_recover_roles_automatically(label, gap, both_return):
    selector = PrincipalHandSelector()
    acquire(selector, label)
    other = "Left" if label == "Right" else "Right"
    selector.update([sample(label, 0.3, 10.4), sample(other, 0.7, 10.4)], 10.4)
    assert selector.update([], 10.45).sample is None
    timestamp = 10.45 + gap
    principal = sample(label, 0.75, timestamp)
    auxiliary = sample(other, 0.25, timestamp)
    output = selector.update([auxiliary, principal] if both_return else [principal], timestamp)
    assert output.sample is principal
    assert output.auxiliary is (auxiliary if both_return else None)
    assert selector.selected


def test_continuous_single_hand_label_jitter_does_not_create_a_virtual_auxiliary():
    selector = PrincipalHandSelector()
    selector.update([sample("Left", 0.3, 10)], 10)
    for frame in range(1, 31):
        timestamp = 10 + frame / 30
        principal = sample("Right" if frame % 2 else "Left", 0.3 + .01 * math.sin(frame), timestamp)
        output = selector.update([principal], timestamp)
        assert output.sample is principal
        assert output.auxiliary is None


def test_label_jitter_exception_cannot_bridge_a_single_empty_frame():
    selector = PrincipalHandSelector()
    selector.update([sample("Right", 0.3, 10)], 10)
    selector.update([], 10.03)
    auxiliary = sample("Left", 0.3, 10.06)
    output = selector.update([auxiliary], 10.06)
    assert output.sample is None
    assert output.auxiliary is auxiliary
    principal = sample("Right", 0.31, 10.09)
    assert selector.update([principal], 10.09).sample is principal


def test_label_jitter_exception_is_disabled_after_auxiliary_was_observed():
    selector = PrincipalHandSelector()
    selector.update([sample("Right", 0.3, 10)], 10)
    selector.update([sample("Right", 0.3, 10.03), sample("Left", 0.7, 10.03)], 10.03)
    principal = sample("Right", 0.3, 10.06)
    assert selector.update([principal], 10.06).sample is principal
    auxiliary = sample("Left", 0.3, 10.09)
    output = selector.update([auxiliary], 10.09)
    assert output.sample is None
    assert output.auxiliary is auxiliary


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("amplitude", [60, 120, 180])
@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("mirror", [False, True])
def test_fast_waves_keep_both_roles_with_either_principal_and_mirror(fps, amplitude, label, mirror):
    selector = PrincipalHandSelector()
    other = "Left" if label == "Right" else "Right"

    def observed(pose, label, now, dx=0, dy=0):
        result = hand(pose, now, handedness=label, dx=dx, dy=dy)
        if mirror:
            result = replace(result, landmarks=tuple(replace(p, x=1 - p.x, z=-p.z) for p in result.landmarks))
        return result

    initial = observed("palm", label, 10)
    assert selector.update([initial], 10).sample is initial
    for frame in range(1, fps * 2 + 1):
        timestamp = 10 + frame / fps
        principal = observed("palm", label, timestamp,
                             dx=amplitude * math.sin(2 * math.pi * 2 * frame / fps))
        auxiliary = observed("pinch", other, timestamp, dy=-200)
        hands = [principal, auxiliary] if frame % 2 else [auxiliary, principal]
        output = selector.update(hands, timestamp)
        assert output.sample is principal
        assert output.auxiliary is auxiliary


@pytest.mark.parametrize("confidence", [.65, .7, .79, .8, 1.0])
def test_auxiliary_alone_never_supplies_pointer_or_clicks_to_the_gesture_engine(confidence):
    from biogesture.gestures import GestureEngine
    from biogesture.settings import Settings

    selector = PrincipalHandSelector()
    engine = GestureEngine(Settings(start_paused=False))
    chosen = selector.update([sample("Right", 0.3, 10)], 10)
    engine.update(chosen.sample, 10)
    selector.update([sample("Right", 0.3, 10.03), sample("Left", 0.7, 10.03)], 10.03)
    for frame in range(1, 91):
        timestamp = 10.03 + frame / 30
        auxiliary = replace(hand("pinch", timestamp, handedness="Left", dx=-128), confidence=confidence)
        selected = selector.update([auxiliary], timestamp)
        assert selected.sample is None
        assert selected.auxiliary is auxiliary
        output = engine.update(selected.sample, timestamp)
        assert output.pointer is None
        assert output.events == ()


def test_explicit_reset_allows_a_new_immediate_choice_but_loss_does_not_reset_roles():
    selector = PrincipalHandSelector()
    selector.update([sample("Left", 0.3, 10)], 10)
    selector.update([], 11)
    assert selector.selected
    selector.reset()
    assert not selector.selected
    principal = sample("Right", 0.7, 12)
    assert selector.update([principal], 12).sample is principal
