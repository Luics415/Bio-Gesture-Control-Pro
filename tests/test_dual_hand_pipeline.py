"""Both session roles through gesture engines and fake Windows input."""

from pathlib import Path
from unittest.mock import call

import pytest

from biogesture.models import ActionEvent, EngineOutput
from biogesture.selection import PrincipalHandSelector
from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline, _Frame
from biogesture.windows import AUXILIARY_SHORTCUTS
from tests.test_auxiliary import pinch
from tests.test_gestures import hand
from tests.test_tracking import FakeRGB, result
from tests.test_wave_pipeline import desktop


def frame(app, selector, hands, now):
    selection = selector.update(hands, now)
    app.output = app.engine.update(selection.sample, now)
    app._apply_output(app.output, now)
    app._apply_auxiliary(selection.auxiliary, now)
    return selection


@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("tip,command", [(8, "COPIAR"), (12, "PEGAR"), (16, "DESHACER"), (20, "REHACER")])
def test_both_hands_move_cursor_and_issue_exactly_one_auxiliary_command(label, fps, tip, command):
    app, native = desktop(Settings(start_paused=False))
    selector = PrincipalHandSelector()
    frame(app, selector, [hand("pointer", 10, handedness=label, dx=-100)], 10)
    opposite = "Left" if label == "Right" else "Right"
    for index in range(1, fps + 1):
        now = 10 + index / fps
        principal = hand("pointer", now, handedness=label, dx=-100 + index)
        auxiliary = pinch(tip, now, handedness=opposite, dx=140)
        selected = frame(app, selector, [principal, auxiliary] if index % 2 else [auxiliary, principal], now)
        assert selected.sample is principal
        assert selected.auxiliary is auxiliary
        assert app.output.pointer == (principal.landmarks[8].x, principal.landmarks[8].y)
    assert list(app.actions.history) == [ActionEvent("auxiliary_command", command)]
    keys = AUXILIARY_SHORTCUTS[command]
    assert native.key.call_args_list == [call(key, True) for key in keys] + [call(key, False) for key in reversed(keys)]
    assert native.move.call_count == fps + 1
    native.button.assert_not_called()
    assert not app.actions._held_keys


@pytest.mark.parametrize("blocked", ["paused", "settings", "calibration", "camera", "operation", "disabled",
                                    "PINZA", "ARRASTRE", "CLIC DERECHO", "MENU", "ONDA 2/4", "VOLUMEN", "SCROLL"])
def test_auxiliary_shortcuts_cannot_interrupt_modal_pause_or_exclusive_principal_gestures(blocked):
    app, native = desktop(Settings(start_paused=False))
    app.output = EngineOutput(state="PUNTERO")
    if blocked == "paused":
        app.engine.set_paused(True)
    elif blocked == "settings":
        app._settings_dialog = object()
    elif blocked == "calibration":
        app._calibration_dialog = object()
    elif blocked == "camera":
        app._camera_enabled = False
    elif blocked == "operation":
        app._operation = True
    elif blocked == "disabled":
        app.settings.auxiliary_enabled = False
    else:
        app.output = EngineOutput(state=blocked)
    for index in range(31):
        now = 10 + index / 30
        app._apply_auxiliary(pinch(timestamp=now), now)
    assert native.mock_calls == []


def test_auxiliary_keeps_role_alone_and_missing_primary_recovers_without_retiring_either_hand():
    app, native = desktop(Settings(start_paused=False))
    selector = PrincipalHandSelector()
    frame(app, selector, [hand("pointer", 10, handedness="Right", dx=-100)], 10)
    for index in range(1, 21):
        now = 10 + index / 20
        auxiliary = pinch(12, now, handedness="Left", dx=140)
        selected = frame(app, selector, [auxiliary], now)
        assert selected.sample is None
        assert selected.auxiliary is auxiliary
    assert list(app.actions.history) == [ActionEvent("auxiliary_command", "PEGAR")]
    assert native.move.call_count == 1
    primary = hand("pointer", 11.05, handedness="Right", dx=-160)
    aux = hand("palm", 11.05, handedness="Left", dx=140)
    assert frame(app, selector, [aux, primary], 11.05).sample is primary
    assert native.move.call_count == 2


def test_missing_auxiliary_frames_cancel_pending_hold_without_reselecting_roles():
    app, native = desktop(Settings(start_paused=False))
    selector = PrincipalHandSelector()
    frame(app, selector, [hand("pointer", 10, handedness="Right", dx=-100)], 10)
    for index in range(1, 31):
        now = 10 + index / 30
        main = hand("pointer", now, handedness="Right", dx=-100)
        aux = pinch(timestamp=now, handedness="Left", dx=140)
        frame(app, selector, [main] if index == 8 else [main, aux], now)
        if index <= 21:
            assert not app.actions.history
    assert list(app.actions.history) == [ActionEvent("auxiliary_command", "COPIAR")]


def test_callback_publishes_both_roles_and_explicit_reselection_discards_old_callbacks():
    pipeline = TrackingPipeline(Settings(), Path("unused"))
    def submit(timestamp, detection):
        pipeline._inflight = (round(timestamp * 1000), _Frame(timestamp, FakeRGB(), pipeline._generation), timestamp)
        pipeline._on_result(detection, None, round(timestamp * 1000))
        return pipeline.latest()
    initial = result()
    assert submit(10, initial).sample is not None
    second = result()
    second.hand_landmarks[0] = [replace_point(p, x=p.x + .5) for p in second.hand_landmarks[0]]
    second.handedness[0][0].category_name = "Left"
    initial.hand_landmarks += second.hand_landmarks
    initial.handedness += second.handedness
    packet = submit(10.1, initial)
    assert packet.sample.handedness == "Right"
    assert packet.auxiliary.handedness == "Left"
    pipeline._inflight = (10200, _Frame(10.2, FakeRGB(), pipeline._generation), 10.2)
    pipeline.reset_roles()
    pipeline._on_result(initial, None, 10200)
    assert pipeline.latest() is None
    assert submit(10.3, initial).sample is None  # Both still visible: initial choice only.
    assert submit(10.4, second).sample.handedness == "Left"  # No hold/off-screen timer.


def replace_point(point, **values):
    from types import SimpleNamespace
    return SimpleNamespace(**(vars(point) | values))


def test_invalid_auxiliary_shortcut_cannot_execute_arbitrary_command():
    app, native = desktop(Settings(start_paused=False))
    assert not app.actions.handle(ActionEvent("auxiliary_command", "BLOQUEAR"))
    assert native.mock_calls == []
