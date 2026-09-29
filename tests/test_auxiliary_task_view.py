"""Joined-finger task-view holds use only deterministic samples, no OS input."""

from dataclasses import replace

import pytest

from biogesture.auxiliary import AuxiliaryGestureEngine
from biogesture.gestures import HandGeometry
from biogesture.models import ActionEvent
from biogesture.settings import Settings
from tests.test_auxiliary import feed as pinch_frames, pinch
from tests.test_auxiliary_scroll import l_frames
from tests.test_gestures import hand


def task_frames(engine, *, start=10, duration=1, fps=30, pose="scroll_up", **kwargs):
    events = []
    for frame in range(round(duration * fps) + 1):
        now = start + frame / fps
        events.extend(engine.update(hand(pose, now, **kwargs), now))
    return events


@pytest.mark.parametrize("fps", [5, 10, 15, 30, 60])
def test_joined_fingers_fire_one_task_view_only_after_continuous_hold(fps):
    engine = AuxiliaryGestureEngine(Settings(detection_fps=fps))
    assert not task_frames(engine, duration=.6, fps=fps)
    assert task_frames(engine, start=10.6, duration=3, fps=fps) == [ActionEvent("command", "VISTA_TAREAS")]


@pytest.mark.parametrize("pose", ["victory", "pointer", "palm", "fist", "thumb", "scroll_down", "right"])
def test_unrelated_poses_cannot_open_task_view(pose):
    engine = AuxiliaryGestureEngine(Settings())
    assert all(event.value != "VISTA_TAREAS" for event in task_frames(engine, pose=pose, duration=2))


def test_l_and_all_existing_pinches_keep_their_own_meaning():
    engine = AuxiliaryGestureEngine(Settings())
    assert not l_frames(engine)
    assert all(event.kind == "scroll" for event in l_frames(engine, start=10.65, duration=1, dy=-100))
    for tip, command in zip((8, 12, 16, 20), ("COPIAR", "PEGAR", "DESHACER", "REHACER")):
        engine.clear()
        assert pinch_frames(engine, tip, duration=1) == [ActionEvent("command", command)]


@pytest.mark.parametrize("interruption", ["missing", "disabled", "invalid", "reset", "stale"])
def test_tracking_interruptions_never_rearm_fired_task_view(interruption):
    engine = AuxiliaryGestureEngine(Settings())
    assert task_frames(engine) == [ActionEvent("command", "VISTA_TAREAS")]
    if interruption == "missing":
        assert not engine.update(None, 11.05)
    elif interruption == "disabled":
        assert not engine.update(hand("palm", 11.05), 11.05, enabled=False)
    elif interruption == "invalid":
        assert not engine.update(replace(hand("palm", 11.05), confidence=.1), 11.05)
    elif interruption == "stale":
        assert not engine.update(hand("palm", 10.9), 11.05)
    else:
        engine.reset()
    assert not task_frames(engine, start=11.1, duration=2)
    assert not engine.update(hand("palm", 13.15), 13.15)
    assert task_frames(engine, start=13.2) == [ActionEvent("command", "VISTA_TAREAS")]


@pytest.mark.parametrize("interruption", ["missing", "invalid", "gap", "pose"])
def test_unfinished_task_hold_restarts_after_loss_or_pose_change(interruption):
    engine = AuxiliaryGestureEngine(Settings())
    assert not task_frames(engine, duration=.5)
    restart = 10.6
    if interruption == "missing":
        assert not engine.update(None, 10.55)
    elif interruption == "invalid":
        assert not engine.update(replace(hand("scroll_up", 10.55), confidence=.1), 10.55)
    elif interruption == "pose":
        assert not engine.update(hand("victory", 10.55), 10.55)
    else:
        restart = 10.7
    assert not task_frames(engine, start=restart, duration=.6)
    assert task_frames(engine, start=restart + .65) == [ActionEvent("command", "VISTA_TAREAS")]


def test_small_separation_noise_cannot_repeat_an_already_fired_command():
    engine = AuxiliaryGestureEngine(Settings())
    assert task_frames(engine)
    for frame in range(1, 61):
        now = 11 + frame / 30
        sample = hand("scroll_up", now)
        points = list(sample.landmarks)
        scale = HandGeometry(sample).scale
        separation = .35 if frame % 2 else .2
        points[12] = replace(points[8], x=points[8].x + separation * scale / sample.width)
        assert not engine.update(replace(sample, landmarks=tuple(points)), now)


def test_duplicate_frames_and_regressing_clock_cannot_advance_task_hold():
    engine = AuxiliaryGestureEngine(Settings())
    sample = hand("scroll_up", 10)
    for now in (10, 10.1, 10.2, 10.3):
        assert not engine.update(sample, now)
    assert not engine.update(hand("scroll_up", 10.2), 10.2)
    assert not task_frames(engine, start=10.35, duration=.6)
    assert task_frames(engine, start=11) == [ActionEvent("command", "VISTA_TAREAS")]


@pytest.mark.parametrize("handedness", ["Left", "Right"])
@pytest.mark.parametrize("size", [.6, 1.0, 1.8])
@pytest.mark.parametrize("rotation", [-70, 0, 65])
def test_task_view_is_independent_of_role_laterality_size_and_rotation(handedness, size, rotation):
    engine = AuxiliaryGestureEngine(Settings())
    assert task_frames(engine, handedness=handedness, size=size, rotation=rotation) == [
        ActionEvent("command", "VISTA_TAREAS")]


def test_transition_from_task_view_to_pinch_preserves_pinch_command_and_latch():
    engine = AuxiliaryGestureEngine(Settings())
    assert task_frames(engine)
    assert pinch_frames(engine, 8, start=11.05, duration=1) == [ActionEvent("command", "COPIAR")]
    assert not engine.update(pinch(8, 12.1), 12.1)
    assert task_frames(engine, start=12.15) == [ActionEvent("command", "VISTA_TAREAS")]
