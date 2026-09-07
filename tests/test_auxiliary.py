"""Synthetic auxiliary-hand sequences; no camera, hooks or desktop inputs."""

from dataclasses import replace
import math

import pytest

from biogesture.auxiliary import AuxiliaryGestureEngine, DEFAULT_COMMANDS, FINGER_TIPS
from biogesture.gestures import HandGeometry
from biogesture.models import ActionEvent, Landmark
from biogesture.settings import Settings
from tests.test_gestures import hand


def pinch(tip=8, timestamp=10.0, distance=0.05, **kwargs):
    sample = hand("palm", timestamp, **kwargs)
    points = list(sample.landmarks)
    scale = HandGeometry(sample).scale
    points[4] = replace(points[tip], x=points[tip].x - distance * scale / sample.width)
    return replace(sample, landmarks=tuple(points))


def feed(engine, tip=8, *, start=10.0, duration=0.6, step=0.05, **kwargs):
    events = []
    for frame in range(round(duration / step) + 1):
        timestamp = start + frame * step
        events.extend(engine.update(pinch(tip, timestamp), timestamp, **kwargs))
    return events


@pytest.mark.parametrize(("tip", "command"), zip(FINGER_TIPS, DEFAULT_COMMANDS))
def test_each_auxiliary_pinch_fires_only_one_command(tip, command):
    engine = AuxiliaryGestureEngine(Settings())
    events = feed(engine, tip, duration=2)
    assert events == [ActionEvent("command", command)]


def test_short_pinch_does_not_fire_and_opening_cancels_hold():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=0.4)
    assert not engine.update(hand("palm", 10.42), 10.42)
    assert not feed(engine, start=10.45, duration=0.4)
    assert engine.update(pinch(timestamp=10.9), 10.9) == (ActionEvent("command", "COPIAR"),)


def test_command_waits_exactly_for_hold_on_fresh_samples():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=0.4)
    assert not engine.update(pinch(timestamp=10.449), 10.449)
    assert engine.update(pinch(timestamp=10.45), 10.45) == (ActionEvent("command", "COPIAR"),)


def test_hysteresis_keeps_candidate_and_fired_latch_until_open():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=0.3)
    for timestamp in (10.35, 10.4):
        assert not engine.update(pinch(timestamp=timestamp, distance=.30), timestamp)
    assert engine.update(pinch(timestamp=10.45, distance=.30), 10.45)
    assert not engine.update(pinch(timestamp=10.5, distance=.30), 10.5)
    assert not engine.update(pinch(timestamp=10.55, distance=.37), 10.55)
    assert not engine.update(pinch(timestamp=10.6, distance=.30), 10.6)
    assert feed(engine, start=10.65) == [ActionEvent("command", "COPIAR")]


def test_hysteresis_band_alone_does_not_start_a_pinch():
    engine = AuxiliaryGestureEngine(Settings())
    for frame in range(20):
        now = 10 + frame * .1
        assert not engine.update(pinch(timestamp=now, distance=.30), now)


def test_observed_open_rearms_once():
    engine = AuxiliaryGestureEngine(Settings())
    assert feed(engine) == [ActionEvent("command", "COPIAR")]
    assert not engine.update(hand("palm", 10.65), 10.65)
    assert feed(engine, start=10.7) == [ActionEvent("command", "COPIAR")]


def test_switching_finger_starts_a_new_hold():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, 8, duration=.4)
    assert not feed(engine, 20, start=10.45, duration=.4)
    assert engine.update(pinch(20, 10.9), 10.9) == (ActionEvent("command", "REHACER"),)


def test_candidate_owns_hysteresis_even_when_another_finger_is_closer():
    engine = AuxiliaryGestureEngine(Settings())
    assert not engine.update(pinch(timestamp=10), 10)
    for frame in range(1, 10):
        timestamp = 10 + frame * .05
        sample = pinch(timestamp=timestamp, distance=.30)
        points = list(sample.landmarks)
        points[12] = points[4]
        result = engine.update(replace(sample, landmarks=tuple(points)), timestamp)
    assert result == (ActionEvent("command", "COPIAR"),)


def test_missing_hand_cancels_unfinished_hold():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not engine.update(None, 10.45)
    assert not feed(engine, start=10.5, duration=.4)
    assert engine.update(pinch(timestamp=10.95), 10.95)


def test_missing_hand_and_reset_do_not_rearm_a_fired_pinch():
    engine = AuxiliaryGestureEngine(Settings())
    assert feed(engine)
    assert not engine.update(None, 11)
    engine.reset()
    assert not feed(engine, start=11.1, duration=1)
    assert not engine.update(hand("palm", 12.2), 12.2)
    assert feed(engine, start=12.25)


def test_disabled_candidate_requires_a_fresh_hold_after_resume():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not feed(engine, start=10.45, duration=1, enabled=False)
    assert not feed(engine, start=11.5, duration=.4)
    assert engine.update(pinch(timestamp=11.95), 11.95)


def test_disabled_fired_pinch_stays_latched_even_after_unobserved_release():
    engine = AuxiliaryGestureEngine(Settings())
    assert feed(engine)
    assert not engine.update(hand("palm", 10.7), 10.7, enabled=False)
    assert not feed(engine, start=10.75)
    assert not engine.update(hand("palm", 11.4), 11.4)
    assert feed(engine, start=11.45)


def test_repeated_frames_do_not_advance_hold_or_release_latch():
    engine = AuxiliaryGestureEngine(Settings())
    sample = pinch(timestamp=10)
    for timestamp in (10, 10.1, 10.2, 10.3, 10.4, 10.5):
        assert not engine.update(sample, timestamp)
    assert feed(engine, start=10.55)
    old_open = hand("palm", 11.05)
    assert not engine.update(old_open, 11.2)
    assert not feed(engine, start=11.25)


def test_long_gap_between_fresh_samples_restarts_hold():
    engine = AuxiliaryGestureEngine(Settings())
    assert not engine.update(pinch(timestamp=10), 10)
    assert not engine.update(pinch(timestamp=10.5), 10.5)
    assert not feed(engine, start=10.55, duration=.35)
    assert engine.update(pinch(timestamp=10.95), 10.95)


@pytest.mark.parametrize("bad_sample", [
    None,
    replace(pinch(), timestamp=9.5),
    replace(pinch(), timestamp=10.1),
    replace(pinch(), timestamp=math.nan),
    replace(pinch(), confidence=.2),
    replace(pinch(), confidence=math.inf),
    replace(pinch(), confidence=1.2),
    replace(pinch(), width=0),
    replace(pinch(), height=math.inf),
    replace(pinch(), landmarks=()),
    replace(pinch(), landmarks=(Landmark(math.nan, 0),) * 21),
    replace(pinch(), landmarks=(Landmark(0, 0),) * 21),
    replace(pinch(), landmarks=(None,) * 21),
    replace(pinch(), landmarks=(Landmark("bad", 0),) * 21),
    object(),
])
def test_invalid_samples_fail_closed(bad_sample):
    engine = AuxiliaryGestureEngine(Settings())
    assert not engine.update(bad_sample, 10)
    assert not feed(engine, start=10.1, duration=.4)


@pytest.mark.parametrize("now", [math.nan, math.inf, -math.inf, "bad", True])
def test_invalid_clock_cancels_pending_hold(now):
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not engine.update(pinch(timestamp=10.45), now)
    assert not feed(engine, start=10.5, duration=.4)


def test_regressing_clock_or_frame_cancels_hold_without_accepting_replay():
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not engine.update(pinch(timestamp=10.3), 10.3)
    assert not engine.update(pinch(timestamp=10.35), 10.45)
    assert not feed(engine, start=10.5, duration=.4)
    assert engine.update(pinch(timestamp=10.95), 10.95)


def test_map_change_restarts_candidate_but_preserves_fired_latch():
    commands = ("GUARDAR", "BUSCAR", "TERMINAL", "PALETA")
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not feed(engine, start=10.45, duration=.4, commands=commands)
    assert engine.update(pinch(timestamp=10.9), 10.9, commands=commands) == (ActionEvent("command", "GUARDAR"),)
    assert not feed(engine, start=10.95, commands=DEFAULT_COMMANDS)


@pytest.mark.parametrize("commands", [(), ("COPIAR",) * 3, ("COPIAR",) * 5, "ABCD", ("",) * 4,
                                      (None,) * 4, ("  ",) * 4])
def test_invalid_command_map_cancels_candidate(commands):
    engine = AuxiliaryGestureEngine(Settings())
    assert not feed(engine, duration=.4)
    assert not engine.update(pinch(timestamp=10.45), 10.45, commands=commands)
    assert not feed(engine, start=10.5, duration=.4)


@pytest.mark.parametrize("handedness", ["Left", "Right"])
@pytest.mark.parametrize("size", [.55, 1.0, 1.8])
def test_assigned_role_is_not_bound_to_laterality_or_scale(handedness, size):
    engine = AuxiliaryGestureEngine(Settings())
    events = []
    for frame in range(20):
        now = 10 + frame * .05
        events.extend(engine.update(pinch(20, now, size=size, handedness=handedness, rotation=60), now))
    assert events == [ActionEvent("command", "REHACER")]


def test_explicit_clear_starts_new_session_with_fresh_hold():
    engine = AuxiliaryGestureEngine(Settings())
    assert feed(engine)
    engine.clear()
    assert not feed(engine, start=10, duration=.4)
    assert engine.update(pinch(timestamp=10.45), 10.45)
