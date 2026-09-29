"""Ocular desktop safety with synthetic observations and fake native input."""

from collections import deque
from queue import Queue
from unittest.mock import Mock, call

import pytest

from biogesture.coordinates import RectMonitor
from biogesture.desktop import DesktopApp
from biogesture.gaze import GazeObservation, GazeSession, GazeState
from biogesture.models import EngineOutput, TrackingPacket
from biogesture.settings import Settings
from tests.test_gaze import calibrated, observed
from tests.test_gestures import hand
from tests.test_wave_pipeline import desktop


def ocular_app(*, ready=True, **settings):
    app, native = desktop(Settings(cursor_mode="eyes", start_paused=False, **settings))
    app.monitors = [RectMonitor("main", "Principal", 0, 0, 1920, 1080, True)]
    app.pipeline = Mock()
    app.pipeline.latest_gaze.return_value = None
    app.pipeline.latest.return_value = None
    app._reset_gaze_session()
    if ready:
        app._gaze_session = GazeSession(calibrated())
        app._gaze_prompt_pending = False
    app.output = EngineOutput(state="PUNTERO")
    app._closing = app._destroyed = False
    app.bus = Queue()
    app._samples = deque()
    app.root = Mock()
    app.pause_button = Mock()
    app._packet = None
    app._sequence = -1
    app._last_capture = 100
    app._notice_until = float("inf")
    app._diagnostics_visible = False
    app.open_gaze_calibration = Mock()
    return app, native


def gaze(app, now, target=(.5, .5), *, valid=True):
    app.pipeline.latest_gaze.return_value = observed(now, target, valid=valid)
    app._update_gaze(now)
    return app._gaze_state


def stable(app, *, start=100, target=(.5, .5)):
    assert not gaze(app, start, target).can_act
    assert gaze(app, start + .2, target).can_act


def primary(app, pose, now):
    app.output = app.engine.update(hand(pose, now), now)
    app._apply_output(app.output, now)
    return app.output


def test_unvalidated_calibration_blocks_cursor_click_and_auxiliary_actions():
    app, native = ocular_app(ready=False)
    gaze(app, 100)
    gaze(app, 100.2)
    primary(app, "pinch", 100.2)
    app._move_gaze(100.2)
    app._apply_auxiliary(hand("scroll_up", 100.2), 100.2)
    assert not app._gaze_state.can_act
    assert not native.mock_calls
    assert not app.actions._held_buttons


def test_activation_requests_calibration_and_victory_cannot_bypass_it():
    app, native = ocular_app(ready=False)
    app.pause(True)
    app.toggle_pause()
    app.open_gaze_calibration.assert_called_once()
    assert app.engine.paused
    for index in range(70):
        now = 100 + index / 30
        gaze(app, now)
        primary(app, "victory", now)
    assert app.engine.paused
    assert not native.mock_calls


def test_eye_position_uses_full_monitor_not_index_camera_region_or_inversion():
    app, native = ocular_app(active_left=.25, active_right=.75, active_top=.3,
                             active_bottom=.7, invert_x=True, invert_y=True)
    app.mapper = Mock()
    app._gaze_state = GazeState("TRACKING", (.1, .9), True)
    app._gaze_observation = observed(100)
    app._move_gaze(100)
    native.move.assert_called_once_with(round(.1 * 1919), round(.9 * 1079))
    app.mapper.map.assert_not_called()


def test_eye_click_moves_to_gaze_before_pressing_not_to_index_tip():
    app, native = ocular_app()
    stable(app, target=(.3, .7))
    primary(app, "pinch", 100.2)
    assert [c[0] for c in native.mock_calls] == ["move", "button"]
    assert native.button.call_args == call("left", True)
    assert native.move.call_args.args[0] == pytest.approx(.3 * 1919, abs=2)
    assert native.move.call_args.args[1] == pytest.approx(.7 * 1079, abs=2)


@pytest.mark.parametrize("loss", ["blink", "absent", "stale", "out_of_calibration"])
def test_losing_usable_eyes_freezes_pointer_then_releases_drag_at_bounded_timeout(loss):
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    assert app.actions._held_buttons == {"left"}
    native.reset_mock()
    if loss == "blink":
        app.pipeline.latest_gaze.return_value = GazeObservation(100.3, reason="Parpadeo")
    elif loss == "absent":
        app.pipeline.latest_gaze.return_value = None
    elif loss == "stale":
        app.pipeline.latest_gaze.return_value = observed(99.9)
    else:
        sample = observed(100.3)
        app.pipeline.latest_gaze.return_value = observed(100.3, features=sample.features[:6] + (.03,) + sample.features[7:])
    app._update_gaze(100.3)
    assert not app._gaze_state.can_act
    assert app._gaze_session.calibration.ready
    assert app.actions._held_buttons == {"left"}
    primary(app, "pinch", 100.3)
    app._apply_auxiliary(hand("scroll_up", 100.3), 100.3)
    app._move_gaze(100.3)
    assert not native.mock_calls
    app._update_gaze(100.61)
    assert app.actions._held_buttons == {"left"}
    app._update_gaze(100.63)
    assert not app.actions._held_buttons
    assert native.button.call_args_list == [call("left", False)]
    native.reset_mock()
    primary(app, "pinch", 100.64)
    app._apply_auxiliary(hand("scroll_up", 100.64), 100.64)
    app._move_gaze(100.64)
    assert not native.mock_calls


def test_short_blink_and_stability_recovery_preserve_existing_drag_without_repress():
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    native.reset_mock()
    gaze(app, 100.3, valid=False)
    primary(app, "pinch", 100.3)
    assert not gaze(app, 100.4).can_act
    primary(app, "pinch", 100.4)
    assert not gaze(app, 100.5).can_act
    primary(app, "pinch", 100.5)
    assert not native.mock_calls
    assert gaze(app, 100.56).can_act
    primary(app, "pinch", 100.56)
    assert app.actions._held_buttons == {"left"}
    native.button.assert_not_called()
    assert native.move.call_count == 1


def test_opening_pinch_during_blink_releases_immediately_without_waiting_for_eyes():
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    native.reset_mock()
    gaze(app, 100.3, valid=False)
    primary(app, "pointer", 100.31)
    assert not app.actions._held_buttons
    assert native.button.call_args_list == [call("left", False)]
    native.move.assert_not_called()
    primary(app, "pinch", 100.35)
    assert not app.actions._held_buttons
    assert native.button.call_count == 1


def test_prolonged_eye_loss_releases_held_button_only_once():
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    native.reset_mock()
    for now in (100.3, 100.4, 100.5, 100.61, 100.63, 100.7, 100.8, 101):
        gaze(app, now, valid=False)
        primary(app, "pinch", now)
    assert native.button.call_args_list == [call("left", False)]
    assert not app.actions._held_buttons
    native.move.assert_not_called()


def test_blink_grace_never_authorizes_a_new_click_without_preexisting_drag():
    app, native = ocular_app()
    stable(app)
    gaze(app, 100.3, valid=False)
    primary(app, "pinch", 100.31)
    assert not app.actions._held_buttons
    assert not native.mock_calls


def test_failed_pinch_release_during_blink_pauses_like_other_input_failures():
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    gaze(app, 100.3, valid=False)
    native.button.side_effect = [OSError("release failed"), None]
    primary(app, "pointer", 100.31)
    assert app.engine.paused
    assert not app.actions._held_buttons
    app.notify.assert_called()


def test_failed_timeout_release_cannot_resume_eye_moves_with_a_stuck_button():
    app, native = ocular_app()
    stable(app)
    primary(app, "pinch", 100.2)
    gaze(app, 100.3, valid=False)
    native.reset_mock()
    native.button.side_effect = OSError("persistent release failure")
    gaze(app, 100.63, valid=False)
    assert app.engine.paused
    gaze(app, 100.7)
    gaze(app, 100.9)
    app._move_gaze(100.9)
    native.move.assert_not_called()
    app.notify.assert_called()


def test_short_blink_recovers_without_recalibration_or_rest_latch():
    app, native = ocular_app()
    stable(app)
    gaze(app, 100.3, valid=False)
    calibration = app._gaze_session.calibration
    assert not gaze(app, 100.4).can_act
    assert gaze(app, 100.6).can_act
    assert app._gaze_session.calibration is calibration
    assert not app._gaze_state.paused
    app.open_gaze_calibration.assert_not_called()


def test_seventy_second_rest_requires_victory_even_after_stable_eyes_return():
    app, native = ocular_app()
    stable(app)
    app.pipeline.latest_gaze.return_value = None
    app._update_gaze(170.19)
    assert not app.engine.paused
    app._update_gaze(170.21)
    assert app.engine.paused and app._gaze_state.paused
    app.pipeline.set_resting.assert_called_with(True)
    gaze(app, 170.3)
    gaze(app, 170.5)
    assert not app._gaze_state.can_act
    app.toggle_pause()
    assert app.engine.paused
    for index in range(70):
        now = 170.6 + index / 30
        gaze(app, now)
        primary(app, "victory", now)
    assert not app.engine.paused
    assert app._gaze_state.can_act
    app.pipeline.set_resting.assert_called_with(False)
    native.button.assert_not_called()


def test_victory_cannot_unlock_rest_without_valid_eyes():
    app, native = ocular_app()
    stable(app)
    app.pipeline.latest_gaze.return_value = None
    app._update_gaze(171)
    for index in range(70):
        now = 171.1 + index / 30
        app._update_gaze(now)
        primary(app, "victory", now)
    assert app.engine.paused and app._gaze_state.paused
    assert not native.mock_calls


@pytest.mark.parametrize("role", ["sample", "auxiliary"])
def test_hand_return_wakes_inference_but_does_not_unlock_rest(role):
    app, native = ocular_app()
    stable(app)
    app.pipeline.latest_gaze.return_value = None
    app._update_gaze(171)
    assert app.engine.paused
    app.pipeline.set_resting.assert_called_with(True)
    app._packet = TrackingPacket(1, 171.1, 171.1, **{role: hand("pointer", 171.1)})
    app._update_gaze(171.1)
    app.pipeline.set_resting.assert_called_with(False)
    assert app.engine.paused and app._gaze_state.paused
    assert not app._gaze_state.can_act
    app._move_gaze(171.1)
    assert not native.mock_calls


def test_stale_hand_packet_does_not_keep_normal_rate_active_during_rest():
    app, native = ocular_app()
    stable(app)
    app.pipeline.latest_gaze.return_value = None
    app._packet = TrackingPacket(1, 170, 170, sample=hand("pointer", 170))
    app._update_gaze(171)
    assert app.engine.paused
    app.pipeline.set_resting.assert_called_with(True)


def test_tick_updates_eye_cursor_independently_without_any_hand_packet(monkeypatch):
    app, native = ocular_app()
    stable(app)
    for index, now in enumerate((100.25, 100.4, 100.55)):
        app.pipeline.latest_gaze.return_value = observed(now, (.3 + .1 * index, .5))
        monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: now)
        app.tick()
    assert native.move.call_count == 3
    native.button.assert_not_called()
    native.key.assert_not_called()
    assert not app.engine.paused


def test_unchanged_face_packet_cannot_repeat_cursor_moves():
    app, native = ocular_app()
    stable(app)
    app._move_gaze(100.2)
    app._update_gaze(100.21)
    app._move_gaze(100.21)
    assert native.move.call_count == 1


def test_camera_restart_discards_current_observation_and_validated_session():
    app, native = ocular_app()
    stable(app)
    old_session = app._gaze_session
    app._restart_camera()
    assert app.engine.paused
    assert app._gaze_session is not old_session
    assert not app._gaze_session.calibration.ready
    assert app._gaze_state is None and app._gaze_observation is None
    app._move_gaze(100.3)
    native.move.assert_not_called()


def test_index_mode_has_no_eye_session_calls_and_keeps_index_control():
    app, native = ocular_app()
    app.settings.cursor_mode = "index"
    app._reset_gaze_session()
    app._update_gaze(100)
    app._move_gaze(100)
    assert app._gaze_session is None
    app.pipeline.latest_gaze.assert_not_called()
    app.pipeline.set_resting.assert_not_called()
    primary(app, "pinch", 100)
    assert [c[0] for c in native.mock_calls] == ["move", "button"]


@pytest.mark.parametrize("modal", ["_operation", "_settings_dialog", "_calibration_dialog"])
def test_modal_dialogs_cannot_leak_eye_moves_or_clicks(modal):
    app, native = ocular_app()
    stable(app)
    setattr(app, modal, True)
    primary(app, "pinch", 100.2)
    app._move_gaze(100.2)
    assert app.engine.paused
    assert not native.mock_calls


def test_failed_eye_move_blocks_the_click_and_pauses():
    app, native = ocular_app()
    stable(app)
    native.move.side_effect = OSError("controlled failure")
    primary(app, "pinch", 100.2)
    assert app.engine.paused
    native.button.assert_not_called()


def test_initial_eye_observation_prompts_calibration_once_not_at_every_poll(monkeypatch):
    app, native = ocular_app(ready=False)
    for now in (100.1, 100.2, 100.3):
        monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: now)
        app.pipeline.latest_gaze.return_value = observed(now)
        app.tick()
    app.open_gaze_calibration.assert_called_once()
    assert not app._gaze_prompt_pending
    assert not native.mock_calls


@pytest.mark.parametrize("blocker", ["hidden", "_operation", "_settings_dialog", "_calibration_dialog"])
def test_initial_calibration_prompt_waits_for_visible_nonmodal_app(monkeypatch, blocker):
    app, native = ocular_app(ready=False)
    app.pipeline.latest_gaze.return_value = observed(100.1)
    if blocker == "hidden":
        app.root.winfo_viewable.return_value = False
    else:
        setattr(app, blocker, True)
    monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: 100.1)
    app.tick()
    app.open_gaze_calibration.assert_not_called()
    assert app._gaze_prompt_pending
    if blocker == "hidden":
        app.root.winfo_viewable.return_value = True
    else:
        setattr(app, blocker, False)
    app.tick()
    app.open_gaze_calibration.assert_called_once()


def test_dismissing_calibration_does_not_reopen_it_automatically(monkeypatch):
    app, native = ocular_app(ready=False)
    factory = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.GazeCalibrationDialog", factory)
    DesktopApp.open_gaze_calibration(app)
    assert app.engine.paused
    on_close = factory.call_args.args[-1]
    on_close()
    assert app._calibration_dialog is None
    assert not app._gaze_prompt_pending
    app.pipeline.latest_gaze.return_value = observed(100.1)
    monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: 100.1)
    app.tick()
    app.open_gaze_calibration.assert_not_called()
    assert not native.mock_calls


def test_virtual_desktop_cannot_start_single_monitor_gaze_calibration(monkeypatch):
    app, native = ocular_app(monitor_id="virtual")
    factory = Mock()
    message = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.GazeCalibrationDialog", factory)
    monkeypatch.setattr("biogesture.desktop.messagebox.showinfo", message)
    DesktopApp.open_gaze_calibration(app)
    assert app.engine.paused
    factory.assert_not_called()
    message.assert_called_once()
