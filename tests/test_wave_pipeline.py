"""Selector -> gestures -> desktop mode, entirely with generated hands and fake UI."""

from dataclasses import replace
import math
from unittest.mock import Mock

import pytest

from biogesture.coordinates import RectMonitor, ScreenMapper
from biogesture.auxiliary import AuxiliaryGestureEngine
from biogesture.desktop import DesktopApp
from biogesture.gestures import GestureEngine
from biogesture.selection import PrincipalHandSelector
from biogesture.settings import Settings
from biogesture.windows import WindowsActions
from tests.test_gestures import hand


class FakeWindow:
    def __init__(self):
        self.borderless = False
        self.values = {"-topmost": False, "-alpha": 1.0}

    def overrideredirect(self, value):
        self.borderless = value

    def attributes(self, name, value):
        self.values[name] = value


def anatomical_hand(label, mirror, now, dx=0, dy=0, pose="palm"):
    original = hand(pose, now, handedness=label, dy=dy)
    reflected = (label == "Left") == mirror
    points = tuple(replace(p, x=(1 - p.x if reflected else p.x) + dx / original.width)
                   for p in original.landmarks)
    return replace(original, landmarks=points)


def desktop(settings):
    app = DesktopApp.__new__(DesktopApp)
    app.settings = settings
    app.engine = GestureEngine(settings)
    app.auxiliary_engine = AuxiliaryGestureEngine(settings)
    native = Mock()
    app.actions = WindowsActions(_native=native)
    app.mapper = ScreenMapper(settings, RectMonitor("main", "Principal", 0, 0, 1920, 1080, True))
    app.root = FakeWindow()
    app.fixed_button = Mock()
    app._operation = False
    app._camera_enabled = True
    app._settings_dialog = app._calibration_dialog = app._tray = None
    app.smoke = True
    app.notify = Mock()
    return app, native


def choose_principal(selector, app, label, mirror):
    for now in (10.0, 10.1, 10.2, 10.4):
        selected = selector.update([anatomical_hand(label, mirror, now)], now)
        output = app.engine.update(selected.sample, now)
        app._apply_output(output, now)
    assert selector.selected


def wave(selector, app, label, mirror, fps, amplitude, *, second=True, start=10.4):
    outputs = []
    for index in range(1, fps + 1):
        now = start + index / fps
        principal = anatomical_hand(label, mirror, now, dx=amplitude * math.sin(2 * math.pi * 2 * index / fps))
        hands = [principal]
        if second:
            # The ignored hand holds a pinch: it must never press the mouse.
            auxiliary = anatomical_hand("Left" if label == "Right" else "Right", mirror, now,
                                        dy=-200, pose="pinch")
            hands = [principal, auxiliary] if index % 2 else [auxiliary, principal]
        selected = selector.update(hands, now)
        assert selected.sample is principal, (index, fps, amplitude, selected.status)
        output = app.engine.update(selected.sample, now)
        app._apply_output(output, now)
        outputs.append(output)
    return outputs


@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("amplitude", [60, 120, 180])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("label", ["Left", "Right"])
def test_paused_wave_of_selected_hand_reaches_fixed_transparent_window_without_os_input(fps, amplitude, mirror, label):
    app, native = desktop(Settings(start_paused=True, mirror=mirror))
    selector = PrincipalHandSelector()
    choose_principal(selector, app, label, mirror)
    outputs = wave(selector, app, label, mirror, fps, amplitude)
    assert sum(event.kind == "toggle_window" for output in outputs for event in output.events) == 1
    assert app.settings.fixed_window
    assert app.root.borderless
    assert app.root.values == {"-topmost": True, "-alpha": app.settings.opacity}
    app.fixed_button.configure.assert_called_with(text="Normal")
    assert app.engine.paused
    assert all(output.pointer is None for output in outputs)
    assert native.mock_calls == []


@pytest.mark.parametrize("fps", [15, 30])
def test_active_wave_switches_back_to_normal_after_clear_release_without_secondary_clicks(fps):
    app, native = desktop(Settings(start_paused=False))
    selector = PrincipalHandSelector()
    choose_principal(selector, app, "Right", True)
    outputs = wave(selector, app, "Right", True, fps, 120)
    assert sum(event.kind == "toggle_window" for output in outputs for event in output.events) == 1
    assert app.settings.fixed_window
    # The hand remains open; waiting out cooldown never requires a closed pose.
    for index in range(1, 10):
        now = 11.4 + index / 30
        principal = anatomical_hand("Right", True, now, pose="palm")
        auxiliary = anatomical_hand("Left", True, now, dy=-200, pose="pinch")
        selected = selector.update([auxiliary, principal], now)
        app._apply_output(app.engine.update(selected.sample, now), now)
    outputs = wave(selector, app, "Right", True, fps, 120, start=11.7)
    assert sum(event.kind == "toggle_window" for output in outputs for event in output.events) == 1
    assert not app.settings.fixed_window
    assert not app.root.borderless
    assert app.root.values == {"-topmost": False, "-alpha": 1.0}
    native.button.assert_not_called()
    native.key.assert_not_called()


def test_secondary_wave_cannot_finish_missing_principal_wave_or_toggle_window():
    app, native = desktop(Settings(start_paused=True))
    selector = PrincipalHandSelector()
    choose_principal(selector, app, "Right", True)
    outputs = []
    for now, dx in ((10.45, 20), (10.5, 60), (10.55, 70)):
        principal = anatomical_hand("Right", True, now, dx=dx)
        auxiliary = anatomical_hand("Left", True, now, dy=-200)
        selected = selector.update([principal, auxiliary], now)
        output = app.engine.update(selected.sample, now)
        app._apply_output(output, now)
        outputs.append(output)
    for index in range(1, 31):
        now = 10.55 + index / 15
        auxiliary = anatomical_hand("Left", True, now, dy=-200,
                                    dx=60 * math.sin(2 * math.pi * 2 * index / 15))
        selected = selector.update([auxiliary], now)
        assert selected.sample is None
        output = app.engine.update(selected.sample, now)
        app._apply_output(output, now)
        outputs.append(output)
    assert not any(event.kind == "toggle_window" for output in outputs for event in output.events)
    assert not app.settings.fixed_window
    assert native.mock_calls == []
