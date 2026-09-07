"""Auxiliary extension boundaries, using only fake desktop input."""

from unittest.mock import call

import pytest

from biogesture.models import ActionEvent, EngineOutput
from biogesture.selection import PrincipalHandSelector
from biogesture.windows import AUXILIARY_SHORTCUTS, WindowsActions
from tests.test_desktop import auxiliary_app
from tests.test_auxiliary_scroll import l_hand
from tests.test_dual_hand_pipeline import frame
from tests.test_gestures import hand
from tests.test_wave_pipeline import desktop
from biogesture.settings import Settings


@pytest.mark.parametrize("profile", ["Global", "VS Code", "Navegador", "Multimedia"])
def test_new_editing_shortcuts_work_independently_of_the_principal_profile(profile):
    from unittest.mock import Mock
    native = Mock()
    actions = WindowsActions(_native=native)
    actions.set_profile(profile)
    expected = {"COPIAR": ("ctrl", "c"), "PEGAR": ("ctrl", "v"),
                "DESHACER": ("ctrl", "z"), "REHACER": ("ctrl", "y")}
    assert AUXILIARY_SHORTCUTS == expected
    for command, keys in expected.items():
        native.reset_mock()
        assert actions.handle(ActionEvent("auxiliary_command", command))
        assert native.key.call_args_list == [call(key, True) for key in keys] + [call(key, False) for key in reversed(keys)]
        native.move.assert_not_called()
        native.button.assert_not_called()
        assert not actions._held_keys


@pytest.mark.parametrize("amount", [-6, -1, 1, 6])
def test_auxiliary_wheel_is_routed_as_wheel_not_a_command_or_pointer(amount):
    app = auxiliary_app()
    app.auxiliary_engine.update.return_value = (ActionEvent("scroll", amount),)
    app._apply_auxiliary(hand("pointer", 10), 10)
    assert app.actions.method_calls == [call.handle(ActionEvent("scroll", amount))]
    assert not app.mapper.mock_calls
    app.pause.assert_not_called()


@pytest.mark.parametrize("state", ["SCROLL", "PREPARANDO SCROLL", "PINZA", "ARRASTRE", "CLIC DERECHO",
                                    "MENU", "PREPARANDO MENU", "VOLUMEN", "ONDA 1/4", "ONDA 2/4", "ONDA 3/4"])
def test_principal_exclusive_states_block_wheel_even_if_auxiliary_engine_misbehaves(state):
    app = auxiliary_app()
    app.output = EngineOutput(state=state)
    app.auxiliary_engine.update.return_value = (ActionEvent("scroll", 3),)
    app._apply_auxiliary(hand("pointer", 10), 10)
    app.auxiliary_engine.update.assert_called_once_with(hand("pointer", 10), 10, enabled=False)
    assert not app.actions.mock_calls


@pytest.mark.parametrize("event", [ActionEvent("press_left"), ActionEvent("click_right"), ActionEvent("toggle_window"),
                                   ActionEvent("volume_delta", .1), ActionEvent("move", (.9, .9))])
def test_auxiliary_cannot_introduce_main_hand_actions(event):
    app = auxiliary_app()
    app.auxiliary_engine.update.return_value = (event,)
    app._apply_auxiliary(hand("pointer", 10), 10)
    app.actions.handle.assert_not_called()
    app.actions.move.assert_not_called()
    app.pause.assert_called_once_with(True)


def test_wheel_dispatch_failure_stops_batch_and_pauses_without_an_extra_action():
    app = auxiliary_app()
    app.auxiliary_engine.update.return_value = (ActionEvent("scroll", 1), ActionEvent("command", "PEGAR"))
    app.actions.handle.return_value = False
    app._apply_auxiliary(hand("pointer", 10), 10)
    assert app.actions.method_calls == [call.handle(ActionEvent("scroll", 1))]
    app.pause.assert_called_once_with(True)


def test_principal_index_move_precedes_auxiliary_wheel_without_focus_click():
    from unittest.mock import Mock
    app, native = desktop(Settings(start_paused=False))
    app.auxiliary_engine = Mock()
    app.auxiliary_engine.update.return_value = (ActionEvent("scroll", -1),)
    app.output = app.engine.update(hand("pointer", 10), 10)
    app._apply_output(app.output, 10)
    app._apply_auxiliary(hand("pointer", 10), 10)
    assert [item[0] for item in native.mock_calls] == ["move", "scroll"]
    native.button.assert_not_called()
    native.key.assert_not_called()


def test_failed_principal_move_also_blocks_auxiliary_wheel():
    from unittest.mock import Mock
    app, native = desktop(Settings(start_paused=False))
    native.move.side_effect = OSError("test unavailable cursor")
    app.auxiliary_engine = Mock()
    app.auxiliary_engine.update.return_value = (ActionEvent("scroll", 1),)
    app.output = app.engine.update(hand("pointer", 10), 10)
    app._apply_output(app.output, 10)
    app._apply_auxiliary(hand("pointer", 10), 10)
    assert app.engine.paused
    native.scroll.assert_not_called()
    native.button.assert_not_called()


def test_principal_click_drag_and_right_click_trace_is_unchanged_with_missing_auxiliary():
    active, actual_native = desktop(Settings(start_paused=False))
    baseline, baseline_native = desktop(Settings(start_paused=False))
    poses = ["pointer", *(["pinch"] * 16), "pointer", "right", "right", "pointer"]
    for index, pose in enumerate(poses):
        now = 10 + index / 30
        main = hand(pose, now, dx=index)
        for app in (active, baseline):
            app.output = app.engine.update(main, now)
            app._apply_output(app.output, now)
        active._apply_auxiliary(None, now)
        assert active.output == baseline.output
    assert actual_native.mock_calls == baseline_native.mock_calls
    assert actual_native.button.call_args_list == [call("left", True), call("left", False),
                                                   call("right", True), call("right", False)]


@pytest.mark.parametrize("label", ["Left", "Right"])
@pytest.mark.parametrize("fps", [15, 30])
@pytest.mark.parametrize("direction", [-1, 1])
def test_selected_auxiliary_l_scrolls_while_only_principal_moves_cursor(label, fps, direction):
    app, native = desktop(Settings(start_paused=False, detection_fps=fps))
    selector = PrincipalHandSelector()
    frame(app, selector, [hand("pointer", 10, handedness=label, dx=-100)], 10)
    other = "Left" if label == "Right" else "Right"
    wheel_steps = []
    for index in range(1, fps * 2 + 1):
        now = 10 + index / fps
        main = hand("pointer", now, handedness=label, dx=-100 + index * .2)
        secondary = l_hand(now, center_y=.2 if direction > 0 else .8, handedness=other)
        native.reset_mock()
        selected = frame(app, selector, [secondary, main] if index % 2 else [main, secondary], now)
        assert selected.sample is main and selected.auxiliary is secondary
        assert app.output.pointer == (main.landmarks[8].x, main.landmarks[8].y)
        assert [c[0] for c in native.mock_calls] in (["move"], ["move", "scroll"])
        wheel_steps.extend(c.args[0] for c in native.scroll.call_args_list)
    assert wheel_steps and all(step * direction > 0 for step in wheel_steps)
    assert abs(sum(wheel_steps)) <= app.settings.scroll_rate * 2
    assert not app.engine.paused


def test_auxiliary_loss_reconfirms_at_the_same_fixed_image_position_without_interrupting_principal():
    app, native = desktop(Settings(start_paused=False))
    selector = PrincipalHandSelector()
    frame(app, selector, [hand("pointer", 10, dx=-100)], 10)
    for index in range(1, 61):
        now = 10 + index / 30
        frame(app, selector, [hand("pointer", now, dx=-100), l_hand(now, center_y=.1)], now)
    assert native.scroll.call_count > 0
    wheel_before = native.scroll.call_count
    for index in range(1, 31):
        now = 12 + index / 30
        main = hand("pointer", now, dx=-100)
        selected = frame(app, selector, [main] if index == 1 else [main, l_hand(now, center_y=.1)], now)
        assert selected.sample is main
        assert app.output.pointer is not None
        if index <= 14:
            assert native.scroll.call_count == wheel_before  # No inherited time or accumulated wheel fraction.
    assert native.scroll.call_count > wheel_before  # Reconfirmed above center without moving to neutral.
    assert native.move.call_count == 91
    native.button.assert_not_called()


def test_principal_drag_cancels_active_auxiliary_scroll_without_modifying_the_drag():
    active, active_native = desktop(Settings(start_paused=False))
    baseline, baseline_native = desktop(Settings(start_paused=False))
    for index in range(61):
        now = 10 + index / 30
        for app in (active, baseline):
            app.output = app.engine.update(hand("pointer", now), now)
            app._apply_output(app.output, now)
        active._apply_auxiliary(l_hand(now, center_y=.1), now)
    assert active_native.scroll.call_count > 0
    active_native.reset_mock()
    baseline_native.reset_mock()
    for index, pose in enumerate([*(["pinch"] * 18), "pointer", "right", "right", "pointer"]):
        now = 12 + (index + 1) / 30
        for app in (active, baseline):
            app.output = app.engine.update(hand(pose, now, dx=index), now)
            app._apply_output(app.output, now)
        active._apply_auxiliary(l_hand(now, center_y=.1), now)
        assert active.output == baseline.output
    assert active_native.mock_calls == baseline_native.mock_calls
    active_native.scroll.assert_not_called()
