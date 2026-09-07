"""Desktop coordination tests without Tk windows, cameras or system input."""

from collections import deque
import logging
import os
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from biogesture.coordinates import RectMonitor
from biogesture.desktop import CONNECTIONS, DesktopApp, calibration_corner, choose_monitor
from biogesture.models import ActionEvent, EngineOutput, HandSample, Landmark, TrackingPacket
from biogesture.settings import Settings


def samples(x=0.2, y=0.2, hand="Right"):
    return [HandSample(10 + i * 0.1, (Landmark(x, y),) * 21, handedness=hand) for i in range(11)]


def test_virtual_desktop_preserves_negative_origins_and_gaps():
    monitors = [RectMonitor("left", "Izquierda", -1920, -100, 1920, 1080),
                RectMonitor("main", "Principal", 0, 0, 2560, 1440, True)]
    result = choose_monitor(monitors, "virtual")
    assert (result.left, result.top, result.width, result.height) == (-1920, -100, 4480, 1540)
    assert choose_monitor(monitors, "missing").id == "main"


@pytest.mark.parametrize("hand", ["Right", "Left"])
def test_calibration_uses_the_primary_samples_regardless_of_laterality(hand):
    points = samples(hand=hand)
    assert calibration_corner(points, 11.1, 10, Settings()) == pytest.approx((0.2, 0.2))


@pytest.mark.parametrize("points,now,since", [
    (samples()[:2], 10.2, 10),
    (samples(), 12, 10),
    (samples(), 11.1, 10.9),
    (samples(float("nan")), 11.1, 10),
])
def test_calibration_rejects_insufficient_old_or_invalid_data(points, now, since):
    with pytest.raises(ValueError):
        calibration_corner(points, now, since, Settings())


def test_calibration_rejects_motion_between_corners():
    points = samples()
    points[-1] = HandSample(11, (Landmark(0.8, 0.8),) * 21)
    with pytest.raises(ValueError, match="movió"):
        calibration_corner(points, 11.1, 10, Settings())


@pytest.mark.parametrize("modal", ["_operation", "_settings_dialog", "_calibration_dialog"])
def test_settings_and_calibration_block_even_a_gesture_that_resumes_control(modal):
    app = DesktopApp.__new__(DesktopApp)
    app._operation = app._settings_dialog = app._calibration_dialog = None
    setattr(app, modal, True)
    app.engine = SimpleNamespace(paused=False)
    app.actions = Mock()
    app.pause = Mock()
    app.toggle_window = Mock()
    app._apply_output(EngineOutput(events=(ActionEvent("command", "BLOQUEAR"),), pointer=(0.5, 0.5)), 11)
    app.pause.assert_called_once_with(True)
    app.actions.release_all.assert_called_once()
    app.actions.handle.assert_not_called()
    app.actions.move.assert_not_called()


def test_failed_camera_stop_does_not_start_a_second_pipeline(monkeypatch):
    app = DesktopApp.__new__(DesktopApp)
    app._closing = False
    app._operation = True
    app._camera_enabled = True
    app.notify = Mock()
    app.pipeline = object()
    original = app.pipeline
    factory = Mock()
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", factory)
    app._dispatch("camera_stopped", (False, True))
    assert app.pipeline is original
    assert not app._operation
    assert not app._camera_enabled
    factory.assert_not_called()


def test_hidden_window_requires_ready_tray_for_recovery():
    app = DesktopApp.__new__(DesktopApp)
    app.root = Mock()
    app.notify = Mock()
    app.smoke = app._tray_ready = False
    app.hide()
    app.root.withdraw.assert_not_called()
    app._tray_ready = True
    app.hide()
    app.root.withdraw.assert_called_once()


def test_successful_camera_restart_waits_for_stop_confirmation(monkeypatch):
    app = DesktopApp.__new__(DesktopApp)
    app._closing = False
    app._operation = True
    app._camera_enabled = False
    app.settings = Settings()
    app._samples = deque(samples())
    app.smoke = False
    app.notify = Mock()
    new_pipeline = Mock()
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", Mock(return_value=new_pipeline))
    app._dispatch("camera_stopped", (True, True))
    assert app.pipeline is new_pipeline
    assert app._camera_enabled
    assert not app._operation
    assert not app._samples
    new_pipeline.start.assert_called_once()


def test_smoke_close_never_touches_camera_or_hooks():
    app = DesktopApp.__new__(DesktopApp)
    app._closing = False
    app.pause = app.notify = Mock()
    app.actions = Mock()
    app.smoke = True
    app.pipeline = None
    app._hook = app._tray = None
    app.bus = Queue()
    app.request_close()
    assert app.closing
    app.actions.close.assert_called_once()
    assert app.bus.get_nowait() == ("close_done", True)


def test_failed_global_hook_stop_does_not_abort_or_latch_incomplete_close(caplog):
    app = DesktopApp.__new__(DesktopApp)
    app._closing = False
    app.pause = Mock()
    app.notify = Mock()
    app.actions = Mock()
    app.smoke = True
    app.pipeline = None
    app._tray = None
    app._hook = Mock()
    app._hook.stop.side_effect = RuntimeError("controlled hook failure")
    app.bus = Queue()

    app.request_close()

    assert app.closing
    assert app.bus.get_nowait() == ("close_done", True)
    app.actions.close.assert_called_once()
    assert "el cierre continuará" in caplog.text
    app.request_close()
    app._hook.stop.assert_called_once()


def output_app():
    app = DesktopApp.__new__(DesktopApp)
    app._operation = app._settings_dialog = app._calibration_dialog = None
    app.engine = SimpleNamespace(paused=False)
    app.actions = Mock()
    app.actions.handle.return_value = True
    app.actions.last_error = "Error de prueba"
    app.mapper = Mock()
    app.mapper.map.return_value = (100, 200)
    app.pause = Mock()
    app.notify = Mock()
    app.open_settings = Mock()
    app._update_tray_state = Mock()
    return app


def test_output_stops_on_failed_action_after_positioning_before_later_commands():
    app = output_app()
    app.actions.handle.return_value = False
    first = ActionEvent("click_left")
    app._apply_output(EngineOutput(events=(first, ActionEvent("command", "BLOQUEAR")), pointer=(0.5, 0.5)), 11)
    app.actions.handle.assert_called_once_with(first)
    app.actions.move.assert_called_once_with(100, 200)
    app.pause.assert_called_once_with(True)


@pytest.mark.parametrize("kind", ["press_left", "release_left", "click_right"])
def test_mouse_action_uses_this_frames_index_position(kind):
    app = output_app()
    event = ActionEvent(kind)
    app._apply_output(EngineOutput(events=(event,), pointer=(0.5, 0.5)), 11)
    assert app.actions.method_calls == [call.move(100, 200), call.handle(event)]


def test_failed_cursor_move_never_presses_a_button_at_an_old_position():
    app = output_app()
    app.actions.move.return_value = False
    app._apply_output(EngineOutput(events=(ActionEvent("press_left"),), pointer=(0.5, 0.5)), 11)
    app.actions.handle.assert_not_called()
    app.pause.assert_called_once_with(True)


def test_opening_settings_stops_the_remaining_output_batch():
    app = output_app()
    app._apply_output(EngineOutput(events=(ActionEvent("command", "CONFIG"), ActionEvent("click_left")), pointer=(0.5, 0.5)), 11)
    app.open_settings.assert_called_once()
    app.actions.handle.assert_not_called()
    app.actions.move.assert_not_called()


def test_pause_gesture_updates_tray_and_does_not_continue_old_batch():
    app = output_app()
    app._apply_output(EngineOutput(events=(ActionEvent("pause_changed", True), ActionEvent("click_left")), pointer=(0.5, 0.5)), 11)
    app._update_tray_state.assert_called_once()
    app.actions.release_all.assert_called_once()
    app.actions.handle.assert_not_called()
    app.actions.move.assert_not_called()


@pytest.mark.parametrize("paused", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_auxiliary_toggle_does_not_change_pause_cursor_or_primary_output(paused, enabled):
    from biogesture.auxiliary import AuxiliaryGestureEngine

    app = output_app()
    app.settings = Settings(auxiliary_enabled=enabled)
    app.engine.paused = paused
    app.auxiliary_engine = AuxiliaryGestureEngine(app.settings)
    app.auxiliary_engine._candidate = 8
    app.auxiliary_engine._candidate_since = 10
    app.auxiliary_engine._latched_tip = 12
    app.output = EngineOutput(state="PUNTERO", pointer=(.3, .7))
    previous = app.output
    app.smoke = True
    app._update_more_menu = Mock()

    app.toggle_auxiliary()

    assert app.settings.auxiliary_enabled is not enabled
    assert app.engine.paused is paused
    assert app.output is previous
    assert app.auxiliary_engine._candidate is None
    assert app.auxiliary_engine._latched_tip == 12  # A held pinch must not replay on enable.
    app._update_more_menu.assert_called_once()
    app.pause.assert_not_called()
    assert not app.actions.mock_calls
    assert not app.mapper.mock_calls


@pytest.mark.parametrize("with_pipeline", [False, True])
def test_reselect_only_resets_roles_and_cancels_old_samples_without_camera_start(with_pipeline, monkeypatch):
    from biogesture.auxiliary import AuxiliaryGestureEngine

    app = output_app()
    app.settings = Settings()
    app.auxiliary_engine = AuxiliaryGestureEngine(app.settings)
    app.auxiliary_engine._latched_tip = 8
    app.pipeline = Mock() if with_pipeline else None
    app._packet = object()
    app._samples = deque(samples())
    factory = Mock()
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", factory)

    app.reselect_principal()

    app.pause.assert_called_once_with(True)
    assert app._packet is None and not app._samples
    assert app.auxiliary_engine._latched_tip is None
    factory.assert_not_called()
    if with_pipeline:
        assert app.pipeline.method_calls == [call.reset_roles()]
    app.actions.move.assert_not_called()
    app.actions.handle.assert_not_called()


def auxiliary_app():
    app = output_app()
    app.settings = Settings()
    app._camera_enabled = True
    app.output = EngineOutput(state="PUNTERO", pointer=(.4, .5))
    app.auxiliary_engine = Mock()
    app.auxiliary_engine.update.return_value = ()
    return app


@pytest.mark.parametrize("barrier", ["disabled", "paused", "operation", "camera_off", "settings", "calibration",
                                     "menu", "pinch", "wave", "primary_event"])
def test_auxiliary_is_disabled_during_primary_exclusive_actions_and_modal_states(barrier):
    app = auxiliary_app()
    if barrier == "disabled":
        app.settings.auxiliary_enabled = False
    elif barrier == "paused":
        app.engine.paused = True
    elif barrier == "operation":
        app._operation = True
    elif barrier == "camera_off":
        app._camera_enabled = False
    elif barrier == "settings":
        app._settings_dialog = True
    elif barrier == "calibration":
        app._calibration_dialog = True
    else:
        app.output = EngineOutput(state={"menu": "MENU", "pinch": "PINZA", "wave": "ONDA 1/4",
                                         "primary_event": "PUNTERO"}[barrier],
                                  events=(ActionEvent("click_right"),) if barrier == "primary_event" else ())
    sample = samples()[0]

    app._apply_auxiliary(sample, 10)

    app.auxiliary_engine.update.assert_called_once_with(sample, 10, enabled=False)
    assert not app.actions.mock_calls
    assert not app.mapper.mock_calls


@pytest.mark.parametrize("command", ["COPIAR", "PEGAR", "DESHACER", "REHACER"])
def test_auxiliary_routes_editing_command_without_moving_the_cursor(command):
    app = auxiliary_app()
    sample = samples()[0]
    app.auxiliary_engine.update.return_value = (ActionEvent("command", command),)

    app._apply_auxiliary(sample, 10)

    app.auxiliary_engine.update.assert_called_once_with(sample, 10, enabled=True)
    assert app.actions.method_calls == [call.handle(ActionEvent("auxiliary_command", command))]
    assert not app.mapper.mock_calls
    app.pause.assert_not_called()


def test_failed_auxiliary_command_pauses_and_surfaces_the_error():
    app = auxiliary_app()
    app.auxiliary_engine.update.return_value = (ActionEvent("command", "COPIAR"),)
    app.actions.handle.return_value = False

    app._apply_auxiliary(samples()[0], 10)

    app.pause.assert_called_once_with(True)
    app.notify.assert_called_once_with("Error de prueba")
    app.actions.move.assert_not_called()


@pytest.mark.parametrize("show_landmarks", [False, True])
@pytest.mark.parametrize("diagnostic_visuals", [False, True])
def test_render_draws_both_assigned_hands_and_respects_landmark_setting(show_landmarks, diagnostic_visuals, monkeypatch):
    import numpy as np

    app = output_app()
    app.settings = Settings(show_landmarks=show_landmarks)
    app.diagnostic_visuals = diagnostic_visuals
    app.root = Mock()
    app.canvas = Mock()
    app._draw_menu = Mock()
    image = Mock()
    monkeypatch.setattr("biogesture.desktop.ImageTk.PhotoImage", Mock(return_value=image))
    packet = TrackingPacket(1, 10, 10, rgb=np.zeros((480, 640, 3), dtype=np.uint8),
                            sample=samples(.2, .3)[0], auxiliary=samples(.8, .6, "Left")[0])
    output = EngineOutput(state="PUNTERO")

    app._render(packet, output)

    visible = show_landmarks
    assert app.canvas.create_line.call_count == (2 * len(CONNECTIONS) if visible else 0)
    assert app.canvas.create_oval.call_count == (42 if visible else 0)
    if visible:
        assert len({item.kwargs["fill"] for item in app.canvas.create_line.call_args_list}) == 2
        assert all(0 <= value <= (550 if index % 2 == 0 else 335)
                   for item in app.canvas.create_line.call_args_list for index, value in enumerate(item.args))
    app.canvas.create_text.assert_not_called()
    app.canvas.create_rectangle.assert_not_called()
    app._draw_menu.assert_not_called()
    app.canvas.create_image.assert_called_once()
    assert not app.actions.mock_calls


@pytest.mark.parametrize("diagnostic_visuals", [False, True])
@pytest.mark.parametrize("show_landmarks", [False, True])
@pytest.mark.parametrize("state", [
    "LISTO", "PUNTERO", "SIN MANO", "PAUSADO", "PINZA", "ARRASTRE", "CLIC DERECHO",
    "VOLUMEN", "SCROLL", "PREPARANDO SCROLL", "PREPARANDO MENU", "GESTO PAUSA",
    "PALMA / VENTANA", "SOLTAR GESTO", "ONDA 1/4", "ONDA 2/4", "ONDA 3/4",
    "PAUSADO · ONDA 2/4", "VENTANA CAMBIADA", "MENU",
])
def test_camera_has_no_gesture_text_or_bars_in_any_mode_except_the_radial(
        monkeypatch, state, show_landmarks, diagnostic_visuals):
    import numpy as np

    app = output_app()
    app.settings = Settings(show_landmarks=show_landmarks)
    app.diagnostic_visuals = diagnostic_visuals
    app.engine.paused = state.startswith("PAUSADO")
    app.canvas = Mock()
    app.root = Mock()
    monkeypatch.setattr("biogesture.desktop.ImageTk.PhotoImage", Mock())
    detected = state != "SIN MANO"
    packet = TrackingPacket(1, 10, 10, rgb=np.zeros((480, 640, 3), dtype=np.uint8),
                            sample=samples()[0] if detected else None,
                            auxiliary=samples(.7)[0] if detected else None)
    app._render(packet, EngineOutput(state=state, menu_selected=1, progress=.5))
    app.canvas.delete.assert_called_once_with("all")
    app.canvas.create_image.assert_called_once()
    visible = detected and show_landmarks
    assert app.canvas.create_line.call_count == (2 * len(CONNECTIONS) if visible else 0)
    assert app.canvas.create_text.call_count == (8 if state == "MENU" else 0)
    assert all("radial-label" in item.kwargs["tags"] for item in app.canvas.create_text.call_args_list)
    assert app.canvas.create_oval.call_count == (42 if visible else 0) + (1 if state == "MENU" else 0)
    assert app.canvas.create_rectangle.call_count == (2 if state == "MENU" else 0)
    assert all("radial" in item.kwargs["tags"] for item in app.canvas.create_rectangle.call_args_list)
    assert not app.actions.mock_calls


@pytest.mark.parametrize("diagnostic_visuals", [False, True])
def test_empty_camera_never_displays_instructions_even_with_diagnostics(diagnostic_visuals):
    app = output_app()
    app.canvas = Mock()
    app.diagnostic_visuals = diagnostic_visuals
    app._draw_empty_state()
    assert app.canvas.mock_calls == [call.delete("all")]


@pytest.mark.parametrize("diagnostic_visuals", [False, True])
def test_camera_off_clears_the_canvas_and_keeps_its_notice_external(diagnostic_visuals):
    app = output_app()
    del app.notify  # Exercise the real external-status notification path.
    app.canvas = Mock()
    app.status = Mock()
    app.diagnostic_visuals = diagnostic_visuals
    app._closing = False
    app._operation = app._camera_enabled = True
    app._dispatch("camera_stopped", (True, False))
    assert app.canvas.mock_calls == [call.delete("all")]
    app.status.set.assert_called_once_with("Cámara apagada. Enciéndela desde Más.")
    assert not app._operation and not app._camera_enabled
    assert not app.actions.mock_calls


@pytest.mark.parametrize("diagnostic_visuals", [False, True])
def test_notifications_remain_outside_camera_and_available_to_diagnostics_and_logs(caplog, diagnostic_visuals):
    app = DesktopApp.__new__(DesktopApp)
    app.diagnostic_visuals = diagnostic_visuals
    app.canvas = Mock()
    app.status = Mock()
    with caplog.at_level(logging.INFO):
        app.notify("Problema de cámara de prueba")
    app.status.set.assert_called_once_with("Problema de cámara de prueba")
    assert "Problema de cámara de prueba" in caplog.text
    assert not app.canvas.mock_calls


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Casilla real optativa de Tk, sin dispositivos")
@pytest.mark.parametrize("diagnostic_visuals", [False, True])
def test_landmark_checkbox_applies_persists_and_reopens_independently_of_diagnostics(
        tmp_path, monkeypatch, caplog, diagnostic_visuals):
    import tkinter as tk

    import numpy as np

    from biogesture.gestures import GestureEngine
    from biogesture.windows import WindowsActions

    monkeypatch.setenv("BIOGESTURE_DATA_DIR", str(tmp_path))
    factory = Mock(side_effect=AssertionError("This UI test must not create a camera pipeline"))
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", factory)
    target = tmp_path / "settings.json"
    packet = TrackingPacket(1, 10, 10, rgb=np.zeros((480, 640, 3), dtype=np.uint8),
                            sample=samples(.2, .3)[0], auxiliary=samples(.8, .6, "Left")[0])

    def checkbox(app):
        app.open_settings()
        app.root.update()
        dialog = app._settings_dialog
        notebook = next(widget for child in dialog.winfo_children()
                        for nested in child.winfo_children() for widget in nested.winfo_children()
                        if widget.winfo_class() == "TNotebook")
        notebook.select(2)
        app.root.update()
        tab = app.root.nametowidget(notebook.tabs()[2])
        label = next(widget for widget in tab.winfo_children()
                     if widget.winfo_class() == "TLabel" and widget.cget("text") == "Dibujar puntos de mano")
        return tab.grid_slaves(row=label.grid_info()["row"], column=1)[0]

    # Recreate the shell from disk between enabled/disabled cases; no camera,
    # hook or native input controller is ever started in either shell.
    for enabled in (True, False):
        root = tk.Tk()
        root.withdraw()
        callback_errors = []
        root.report_callback_exception = lambda *error: callback_errors.append(error)
        settings = Settings.load(target)
        before = vars(settings).copy()
        app = DesktopApp(root, settings, Queue(), GestureEngine(settings), WindowsActions(dry_run=True), None,
                         [RectMonitor("main", "Prueba", 0, 0, 1920, 1080, True)], smoke=True,
                         diagnostic_visuals=diagnostic_visuals)
        app._restart_camera = Mock()  # Saving must not open or restart a real device.
        footer = root.winfo_children()[-1]
        try:
            control = checkbox(app)
            assert control.instate(["selected"]) is not enabled
            control.invoke()
            assert control.instate(["selected"]) is enabled
            dialog = app._settings_dialog
            save = next(widget for child in dialog.winfo_children() for widget in child.winfo_children()
                        if widget.winfo_class() == "TButton" and widget.cget("text") == "Guardar")
            # Exercise the real production persistence branch in the isolated
            # tmp_path only; integrations remain absent and restart is mocked.
            app.smoke = False
            try:
                save.invoke()
            finally:
                app.smoke = True
            assert app._settings_dialog is None
            assert app.settings.show_landmarks is enabled
            assert Settings.load(target).show_landmarks is enabled
            assert vars(app.settings) == {**before, "show_landmarks": enabled}
            app._restart_camera.assert_called_once_with(True)
            assert app.diagnostic_visuals is diagnostic_visuals
            assert bool(footer.winfo_children()) is diagnostic_visuals

            app._render(packet, EngineOutput(state="ONDA 2/4", progress=.5))
            kinds = [app.canvas.type(item) for item in app.canvas.find_all()]
            assert kinds.count("line") == (2 * len(CONNECTIONS) if enabled else 0)
            assert kinds.count("oval") == (42 if enabled else 0)
            assert kinds.count("text") == 0
            assert kinds.count("rectangle") == 0
            assert not app.canvas.find_withtag("radial")
            assert checkbox(app).instate(["selected"]) is enabled
            assert not callback_errors
            assert app.actions._native is None and app._hook is None and app._tray is None
            assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
        finally:
            app.request_close()
            app.tick()
    factory.assert_not_called()


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Activar BIOGESTURE_TEST_GUI=1 para geometría real de Tk")
@pytest.mark.parametrize("scaling", [1.333, 1.666, 2.0, 2.666])
@pytest.mark.parametrize("diagnostic_visuals", [None, False, True], ids=["default", "clean", "diagnostics"])
def test_tk_layout_fits_fixed_window_and_dialogs_at_multiple_dpi(scaling, diagnostic_visuals, monkeypatch, caplog):
    import tkinter as tk

    from biogesture.gestures import GestureEngine
    from biogesture.rendering import CAMERA_HEIGHT, TOOLBAR_HEIGHT
    from biogesture.windows import WindowsActions

    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", scaling)
    callback_errors = []
    root.report_callback_exception = lambda *error: callback_errors.append(error)
    factory = Mock()
    factory.return_value.latest.return_value = None
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", factory)
    save_settings = Mock()
    monkeypatch.setattr(Settings, "save", save_settings)
    settings = Settings()
    visuals = {} if diagnostic_visuals is None else {"diagnostic_visuals": diagnostic_visuals}
    app = DesktopApp(root, settings, Queue(), GestureEngine(settings), WindowsActions(dry_run=True), None,
                     [RectMonitor("main", "Prueba", 0, 0, 1920, 1080, True)], smoke=True,
                     **visuals)
    try:
        root.deiconify()
        root.update()
        root.update_idletasks()
        assert (root.winfo_width(), root.winfo_height()) == (550, 375)
        assert (app.canvas.winfo_width(), app.canvas.winfo_height()) == (550, CAMERA_HEIGHT)
        footer = root.winfo_children()[-1]
        assert app.diagnostic_visuals is (diagnostic_visuals is True)
        assert bool(footer.winfo_children()) is (diagnostic_visuals is True)
        assert not app.canvas.find_all()
        for child in root.winfo_children():
            if not child.winfo_manager():
                continue
            assert child.winfo_y() + child.winfo_height() <= 375
            assert child.winfo_x() + child.winfo_width() <= 550
        toolbar = root.winfo_children()[0]
        for button in toolbar.winfo_children():
            assert button.winfo_x() + button.winfo_width() <= 550
            assert button.winfo_y() + button.winfo_height() <= TOOLBAR_HEIGHT
        assert app.more_menu.entrycget(6, "label") == "Reelegir mano principal"
        app.pause(False)
        mapper = app.mapper
        mapper.map(.4, .6, 10)
        mapper_state = (vars(mapper._x).copy(), vars(mapper._y).copy())
        output = app.output
        for enabled in (False, True):
            app.more_menu.invoke(7)
            assert app.settings.auxiliary_enabled is enabled
            assert app.auxiliary_engine.settings is app.settings
            assert not app.engine.paused and app.output is output
            assert (vars(mapper._x), vars(mapper._y)) == mapper_state
            assert app.more_menu.entrycget(7, "label") == (
                "Desactivar mano auxiliar" if enabled else "Activar mano auxiliar")
        app._samples.extend(samples())
        app.auxiliary_engine._latched_tip = 8
        app.more_menu.invoke(6)
        assert app.engine.paused
        assert not app._samples and app._packet is None
        assert app.auxiliary_engine._latched_tip is None
        assert app.pipeline is None
        factory.assert_not_called()
        app.toggle_window()
        root.update()
        assert root.overrideredirect()
        assert root.attributes("-topmost")
        assert root.attributes("-alpha") == pytest.approx(0.85)
        app._position_window(-100, 50)
        root.update()
        assert root.winfo_x() == -100
        app._position_window(40, 40)
        app.toggle_window()
        root.update()
        assert not root.overrideredirect()
        assert not root.attributes("-topmost")
        assert root.attributes("-alpha") == pytest.approx(1.0)
        app.open_settings()
        root.update()
        root.update_idletasks()
        dialog = app._settings_dialog
        assert not app._diagnostics_visible
        notebook = next(widget for child in dialog.winfo_children()
                        for nested in child.winfo_children() for widget in nested.winfo_children()
                        if widget.winfo_class() == "TNotebook")
        notebook.select(3)
        root.update()
        assert app._diagnostics_visible
        diagnostics = root.nametowidget(notebook.tabs()[3])
        assert any(widget.winfo_class() == "TLabel" and str(widget.cget("textvariable")) == str(app.status)
                   for widget in diagnostics.winfo_children())
        diagnostics_text = " ".join(widget.cget("text") for widget in diagnostics.winfo_children()
                                    if widget.winfo_class() == "TLabel")
        assert all(command in diagnostics_text for command in ("copiar", "pegar", "deshacer", "rehacer"))
        assert "0.45 s" in diagnostics_text
        desktop_tab = root.nametowidget(notebook.tabs()[2])
        auxiliary_label = next(widget for widget in desktop_tab.winfo_children()
                               if widget.winfo_class() == "TLabel" and widget.cget("text") == "Comandos de mano auxiliar")
        auxiliary_control = desktop_tab.grid_slaves(row=auxiliary_label.grid_info()["row"], column=1)[0]
        assert auxiliary_control.winfo_class() == "TCheckbutton"
        assert auxiliary_control.instate(["selected"])
        notebook.select(0)
        root.update()
        assert not app._diagnostics_visible
        assert dialog.winfo_width() <= root.winfo_screenwidth()
        assert dialog.winfo_height() <= root.winfo_screenheight() - 50
        for child in dialog.winfo_children():
            assert child.winfo_y() + child.winfo_height() <= dialog.winfo_height()
        app.open_calibration()
        root.update()
        root.update_idletasks()
        calibration = app._calibration_dialog
        assert calibration.winfo_height() <= root.winfo_screenheight() - 50
        dialog.destroy()
        root.update_idletasks()
        assert app._settings_dialog is None
        assert app._calibration_dialog is None
        assert not app._diagnostics_visible
        app.open_settings()
        root.update()
        dialog = app._settings_dialog
        notebook = next(widget for child in dialog.winfo_children()
                        for nested in child.winfo_children() for widget in nested.winfo_children()
                        if widget.winfo_class() == "TNotebook")
        desktop_tab = root.nametowidget(notebook.tabs()[2])
        auxiliary_label = next(widget for widget in desktop_tab.winfo_children()
                               if widget.winfo_class() == "TLabel" and widget.cget("text") == "Comandos de mano auxiliar")
        desktop_tab.grid_slaves(row=auxiliary_label.grid_info()["row"], column=1)[0].invoke()
        save_button = next(widget for child in dialog.winfo_children() for widget in child.winfo_children()
                           if widget.winfo_class() == "TButton" and widget.cget("text") == "Guardar")
        save_button.invoke()
        app.tick()
        assert app._settings_dialog is None
        assert not app.settings.auxiliary_enabled
        assert app.engine.settings is app.settings and app.auxiliary_engine.settings is app.settings
        assert app.engine.paused
        factory.assert_called_once()
        factory.return_value.start.assert_not_called()
        save_settings.assert_not_called()
        assert not callback_errors
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    finally:
        app.request_close()
        app.tick()
