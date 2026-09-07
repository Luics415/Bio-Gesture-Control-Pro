"""Auxiliary L-scroll sequences use synthetic hands, never camera or OS input."""

from dataclasses import replace
import math

import pytest

from biogesture.auxiliary import AuxiliaryGestureEngine
from biogesture.gestures import GestureEngine, HandGeometry
from biogesture.models import ActionEvent, Landmark
from biogesture.settings import Settings
from tests.test_auxiliary import feed as pinch_frames, pinch
from tests.test_gestures import hand


def l_hand(timestamp=10.0, dy=0.0, handedness="Left", dx=140.0, *, width=640, height=480,
           size=1.0, rotation=0.0, mirror=False, angle=90.0, center_y=0.5):
    """An isolated L, transformable like the primary engine's replay fixture."""
    sample = hand("pointer", timestamp, width=width, height=height, handedness=handedness)
    geometry = HandGeometry(sample)
    ox, oy, _ = geometry.points[0]
    points = [(x - ox, y - oy) for x, y, _ in geometry.points]
    theta = math.radians(angle)
    vx, vy = -55 * math.sin(theta), -55 * math.cos(theta)
    points[1:5] = [(-22, -14), (-45, -45), (-45 + vx / 2, -45 + vy / 2), (-45 + vx, -45 + vy)]
    rotate = math.radians(rotation)
    encoded = []
    for x, y in points:
        x = -x if mirror else x
        tx = (x * math.cos(rotate) - y * math.sin(rotate)) * size + dx
        ty = (x * math.sin(rotate) + y * math.cos(rotate)) * size
        encoded.append(Landmark((ox + tx) / width, (oy + ty) / height))
    offset_y = center_y - sum(encoded[i].y for i in (0, 5, 9, 13, 17)) / 5 + dy / height
    return replace(sample, landmarks=tuple(replace(point, y=point.y + offset_y) for point in encoded))


def l_frames(engine, *, start=10.0, duration=.6, fps=30, enabled=True, **kwargs):
    events = []
    for frame in range(round(duration * fps) + 1):
        timestamp = start + frame / fps
        events.extend(engine.update(l_hand(timestamp, **kwargs), timestamp, enabled=enabled))
    return events


def wheel(events):
    assert all(event.kind == "scroll" and type(event.value) is int and event.value != 0 for event in events)
    return sum(event.value for event in events)


@pytest.mark.parametrize(("center_y", "direction"), [(.2, 1), (.8, -1)])
def test_l_held_above_or_below_center_scrolls_without_first_visiting_center(center_y, direction):
    engine = AuxiliaryGestureEngine(Settings())
    assert not l_frames(engine, duration=.4, center_y=center_y)
    events = l_frames(engine, start=10.4, duration=1.6, center_y=center_y)
    assert events and all(event.value * direction > 0 for event in events)


@pytest.mark.parametrize(("center_y", "direction"), [(0.0, 1), (1.0, -1)])
def test_confirmation_does_not_count_the_preceding_hold_as_scroll_time(center_y, direction):
    engine = AuxiliaryGestureEngine(Settings(scroll_rate=20.0))
    for frame in range(10):
        now = 10 + frame * .05
        assert not engine.update(l_hand(now, center_y=center_y), now)
    assert engine.update(l_hand(10.5, center_y=center_y), 10.5) == (ActionEvent("scroll", direction),)


@pytest.mark.parametrize("center_y", [.45, .475, .5, .525, .55])
def test_stationary_l_in_fixed_neutral_band_never_scrolls(center_y):
    engine = AuxiliaryGestureEngine(Settings())
    assert not l_frames(engine, duration=10, center_y=center_y)


@pytest.mark.parametrize("fps", [5, 10, 15, 30, 60])
@pytest.mark.parametrize("direction", [-1, 1])
def test_deflected_l_scrolls_continuously_with_expected_direction(fps, direction):
    engine = AuxiliaryGestureEngine(Settings(scroll_rate=6.0, detection_fps=fps))
    assert not l_frames(engine, fps=fps)
    events = l_frames(engine, start=10.6, duration=2, fps=fps, center_y=.5 - direction * .5)
    assert events
    assert all(event.value * direction > 0 for event in events)
    assert abs(wheel(events) - direction * 12) <= 1


def test_scroll_amount_is_time_based_at_all_supported_test_rates():
    totals = []
    for fps in (5, 10, 15, 30):
        engine = AuxiliaryGestureEngine(Settings(scroll_rate=9.0, detection_fps=fps))
        l_frames(engine, fps=fps)
        totals.append(wheel(l_frames(engine, start=10.6, duration=3, fps=fps, center_y=.3)))
    assert max(totals) - min(totals) <= 1
    assert all(abs(total - 13.5) <= 1 for total in totals)


def test_speed_is_proportional_and_bounded_by_settings():
    totals = []
    for center_y in (.45, .3, 0, -.5):
        engine = AuxiliaryGestureEngine(Settings(scroll_rate=6.0))
        l_frames(engine)
        totals.append(wheel(l_frames(engine, start=10.6, duration=2, center_y=center_y)))
    assert totals[0] == 0
    assert abs(totals[1] - 6) <= 1
    assert abs(totals[2] - 12) <= 1
    assert totals[3] == totals[2]


def test_dead_zone_noise_and_horizontal_motion_do_not_accumulate_scroll():
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    for frame in range(1, 151):
        now = 10.6 + frame / 30
        sample = l_hand(now, dx=140 + 70 * math.sin(frame), center_y=.5 + .049 * math.sin(frame * 1.1))
        assert not engine.update(sample, now)


def test_returning_to_center_clears_fraction_and_stops_immediately():
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    assert not engine.update(l_hand(10.7, center_y=0), 10.7)
    assert not engine.update(l_hand(10.75), 10.75)
    assert not engine.update(l_hand(10.85, center_y=0), 10.85)
    assert not engine.update(l_hand(10.9), 10.9)
    assert not l_frames(engine, start=10.95, duration=2)


def test_direction_change_does_not_send_an_old_direction_fraction():
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    assert not engine.update(l_hand(10.7, center_y=0), 10.7)
    assert not engine.update(l_hand(10.8, center_y=1), 10.8)
    assert engine.update(l_hand(10.9, center_y=1), 10.9) == (ActionEvent("scroll", -1),)


@pytest.mark.parametrize("interruption", ["missing", "disabled", "reset", "invalid", "release", "gap"])
def test_interruptions_drop_fraction_and_reconfirm_in_place_without_catchup(interruption):
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    assert not engine.update(l_hand(10.7, center_y=0), 10.7)
    if interruption == "missing":
        assert not engine.update(None, 10.75)
    elif interruption == "disabled":
        assert not engine.update(l_hand(10.75, center_y=0), 10.75, enabled=False)
    elif interruption == "reset":
        engine.reset()
    elif interruption == "invalid":
        assert not engine.update(replace(l_hand(10.75), confidence=.1), 10.75)
    elif interruption == "release":
        assert not engine.update(hand("pointer", 10.75), 10.75)
    # The gap case leaves a 0.2 s interval without an explicit missing sample.
    assert not l_frames(engine, start=10.9, duration=.4, center_y=0)
    assert wheel(l_frames(engine, start=11.3, duration=1, center_y=0)) > 0


def test_repeated_and_stale_frames_never_repeat_wheel_events():
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    sample = l_hand(10.7, dy=-90)
    assert not engine.update(sample, 10.7)
    for now in (10.75, 10.8, 10.9, 11.0, 11.1):
        assert not engine.update(sample, now)
    assert not l_frames(engine, start=11.15, duration=.4, center_y=.2)
    assert wheel(l_frames(engine, start=11.55, duration=1, center_y=.2)) > 0


@pytest.mark.parametrize("fps", [5, 10, 15, 30])
def test_adaptive_gap_reset_prevents_catchup_at_low_and_high_detection_rates(fps):
    engine = AuxiliaryGestureEngine(Settings(detection_fps=fps, scroll_rate=20.0))
    assert not l_frames(engine, fps=fps)
    events = l_frames(engine, start=10.6, duration=1, fps=fps, center_y=.1)
    assert events and max(abs(event.value) for event in events) <= math.ceil(20 / fps)
    limit = min(.35, max(.15, 1.5 / fps))
    restart = 11.6 + limit + .01
    assert not l_frames(engine, start=restart, duration=.4, fps=fps, center_y=.1)
    recovered = l_frames(engine, start=restart + .4, duration=1, fps=fps, center_y=.1)
    assert recovered and max(abs(event.value) for event in recovered) <= math.ceil(20 / fps)


@pytest.mark.parametrize("fps", [5, 10, 15, 30])
def test_explicit_missing_frame_always_cancels_even_within_adaptive_gap(fps):
    engine = AuxiliaryGestureEngine(Settings(detection_fps=fps))
    l_frames(engine, fps=fps)
    assert not engine.update(None, 10.61)
    assert not l_frames(engine, start=10.65, duration=.4, fps=fps, center_y=.1)
    assert wheel(l_frames(engine, start=11.05, duration=1, fps=fps, center_y=.1)) > 0


@pytest.mark.parametrize("tip", [8, 12, 16, 20])
def test_pinches_immediately_cancel_scroll_then_issue_only_one_command(tip):
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    assert not engine.update(l_hand(10.7, center_y=0), 10.7)
    events = pinch_frames(engine, tip, start=10.75, duration=1)
    assert len(events) == 1 and events[0].kind == "command"
    assert not l_frames(engine, start=11.8, duration=.4, center_y=0)
    assert wheel(l_frames(engine, start=12.2, duration=1, center_y=0)) > 0


@pytest.mark.parametrize("pose", ["pointer", "thumb", "palm", "fist", "victory", "scroll_up", "scroll_down"])
def test_other_poses_do_not_activate_l_scroll(pose):
    engine = AuxiliaryGestureEngine(Settings())
    for frame in range(45):
        now = 10 + frame / 30
        sample = hand(pose, now, dy=-frame * 3)
        events = engine.update(sample, now)
        assert all(event.kind != "scroll" for event in events)


@pytest.mark.parametrize("angle", [20, 45, 135, 160])
def test_non_l_thumb_angles_do_not_scroll(angle):
    engine = AuxiliaryGestureEngine(Settings())
    assert not l_frames(engine, angle=angle)
    assert not l_frames(engine, start=10.65, duration=1, dy=-90, angle=angle)


@pytest.mark.parametrize("handedness", ["Left", "Right"])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize(("width", "height", "size", "rotation"), [
    (640, 480, .6, 0), (1280, 720, 1.0, 65), (480, 640, 1.8, -90), (1920, 1080, 1.0, 175),
])
def test_l_scroll_is_scale_aspect_orientation_and_label_independent(handedness, mirror, width, height, size, rotation):
    kwargs = dict(handedness=handedness, mirror=mirror, width=width, height=height, size=size, rotation=rotation)
    engine = AuxiliaryGestureEngine(Settings(mirror=mirror))
    assert AuxiliaryGestureEngine._is_l_pose(HandGeometry(l_hand(**kwargs), mirror=mirror))
    assert not l_frames(engine, **kwargs)
    assert wheel(l_frames(engine, start=10.65, duration=1, center_y=.2, **kwargs)) > 0


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("handedness", ["Left", "Right"])
@pytest.mark.parametrize(("width", "height"), [(640, 480), (1280, 720), (480, 640), (1920, 1080)])
@pytest.mark.parametrize(("center_y", "direction"), [(.2, 1), (.8, -1)])
def test_same_normalized_image_position_has_same_rate_without_initial_anchor(
        fps, mirror, handedness, width, height, center_y, direction):
    engine = AuxiliaryGestureEngine(Settings(scroll_rate=6.0, detection_fps=fps, mirror=mirror))
    events = l_frames(engine, duration=2, fps=fps, center_y=center_y, mirror=mirror,
                      handedness=handedness, width=width, height=height)
    # |0.5-y|=.30: speed=6*(.25+.75*(.30-.05)/(.50-.05))=4, active for 1.55 s.
    assert wheel(events) == direction * 6


def test_speed_depends_on_image_position_not_palm_size_or_activation_height():
    totals = []
    for size in (.6, 1, 1.8):
        for initial_y in (.2, .5, .8):
            engine = AuxiliaryGestureEngine(Settings(scroll_rate=6.0))
            l_frames(engine, center_y=initial_y, size=size)
            # Clear any fraction without losing the confirmed L.
            assert not engine.update(l_hand(10.65, size=size, center_y=.5), 10.65)
            totals.append(wheel(l_frames(engine, start=10.7, duration=2, size=size, center_y=.2)))
    assert len(set(totals)) == 1


def test_fixed_neutral_band_stops_even_when_l_was_activated_elsewhere():
    engine = AuxiliaryGestureEngine(Settings())
    assert wheel(l_frames(engine, duration=2, center_y=.2)) > 0
    for index, center_y in enumerate((.45, .5, .55)):
        assert not l_frames(engine, start=12.05 + index * .05, duration=0, center_y=center_y)
    assert not l_frames(engine, start=12.2, duration=2, center_y=.5)


def test_unreliable_scale_jump_requires_reconfirmation_without_a_scroll_burst():
    engine = AuxiliaryGestureEngine(Settings())
    l_frames(engine)
    assert not engine.update(l_hand(10.65, size=2.0, center_y=.1), 10.65)
    assert not l_frames(engine, start=10.7, duration=.4, size=2.0, center_y=.1)
    assert wheel(l_frames(engine, start=11.1, duration=1, size=2.0, center_y=.1)) > 0


def test_auxiliary_l_and_pinch_do_not_change_primary_engine_behavior_or_settings():
    settings = Settings(start_paused=False)
    primary, reference = GestureEngine(settings), GestureEngine(replace(settings))
    auxiliary = AuxiliaryGestureEngine(settings)
    expected_settings = replace(settings)
    for frame in range(90):
        now = 10 + frame / 30
        pose = "pointer" if frame < 20 or frame > 65 else "pinch"
        sample = hand(pose, now, dx=frame)
        aux = l_hand(now, dy=0 if frame < 20 else -90) if frame < 65 else pinch(12, now)
        events = auxiliary.update(aux, now)
        assert all(event.kind in ("command", "scroll") for event in events)
        assert primary.update(sample, now) == reference.update(sample, now)
    assert settings == expected_settings
