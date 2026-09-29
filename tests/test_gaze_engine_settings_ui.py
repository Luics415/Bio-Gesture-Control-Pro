"""Actual selector/save/reset lifecycle, without camera or desktop input."""

from dataclasses import asdict, replace
import os

import pytest

from biogesture.gaze import GazeSession, GazeState
from biogesture.settings import Settings
from tests.test_desktop import (real_control_settings_app as desktop_settings_fixture,
                               settings_control, settings_notebook, settings_save, settings_tab)
from tests.test_gaze import calibrated
from tests.test_gaze_precision import fitted, validation
from tests.test_gaze_peripheral import fitted_peripheral, peripheral_validation


real_control_settings_app = desktop_settings_fixture


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Selector ocular real optativo de Tk")
@pytest.mark.parametrize("initial_id,selected_label,selected_id", [
    ("precision-openvino-v1", "Anterior · comparación", "legacy-ridge-v1"),
    ("legacy-ridge-v1", "Personal · OpenVINO", "precision-openvino-v1"),
    ("precision-openvino-v1", "Precisión v2 · OpenVINO", "precision-openvino-v2"),
    ("precision-openvino-v2", "Personal · OpenVINO", "precision-openvino-v1"),
])
def test_motor_ocular_selector_persists_choice_and_revokes_old_calibration_without_changing_hands(
        real_control_settings_app, initial_id, selected_label, selected_id):
    app, root, path = real_control_settings_app
    app.settings = replace(app.settings, cursor_mode="eyes", gaze_engine=initial_id)
    app.engine.settings = app.auxiliary_engine.settings = app.settings
    original_values = asdict(app.settings)
    app._reset_gaze_session()
    previous = (fitted_peripheral() if initial_id == "precision-openvino-v2" else
                fitted() if initial_id == "precision-openvino-v1" else calibrated())
    if initial_id == "precision-openvino-v1":
        assert previous.validate(validation()).accepted
    if initial_id == "precision-openvino-v2":
        assert previous.validate(peripheral_validation()).accepted
    assert previous.ready
    app._gaze_session = GazeSession(previous)
    app._gaze_state = GazeState("TRACKING", (.5, .5), True)
    app._gaze_cursor_position = (500, 300)

    app.open_settings()
    root.update()
    dialog = app._settings_dialog
    tab = settings_tab(settings_notebook(dialog), "Control")
    selector = settings_control(tab, "Motor ocular")
    assert selector.winfo_class() == "TCombobox"
    assert str(selector.cget("state")) == "readonly"
    labels = {"precision-openvino-v2": "Precisión v2 · OpenVINO", "precision-openvino-v1": "Personal · OpenVINO",
              "legacy-ridge-v1": "Anterior · comparación"}
    assert tuple(selector.cget("values")) == tuple(labels.values())
    assert selector.get() == labels[initial_id]
    selector.set(selected_label)
    app.smoke = False
    try:
        settings_save(dialog).invoke()
    finally:
        app.smoke = True

    assert app._settings_dialog is None
    saved = Settings.load(path)
    assert saved.gaze_engine == app.settings.gaze_engine == selected_id
    assert {k: v for k, v in asdict(saved).items() if k != "gaze_engine"} == {
        k: v for k, v in original_values.items() if k != "gaze_engine"}
    app._restart_camera.assert_called_once_with(True)
    assert app._gaze_session.calibration is not previous
    assert app._gaze_session.calibration.engine_id == selected_id
    assert not app._gaze_session.calibration.ready
    assert app._gaze_state is None and app._gaze_cursor_position is None
    assert app._gaze_prompt_pending and app.engine.paused
    assert app.pipeline is None and app.actions._native is None

    app.open_settings()
    root.update()
    tab = settings_tab(settings_notebook(app._settings_dialog), "Control")
    assert settings_control(tab, "Motor ocular").get() == selected_label
    assert settings_control(tab, "Mover cursor con").get() == "Ojos (experimental)"
