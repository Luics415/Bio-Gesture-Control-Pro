"""Exercise desktop stale-frame and shutdown paths without creating Tk or input."""

from collections import deque
import logging
from queue import Queue
from unittest.mock import Mock

from biogesture.desktop import DesktopApp
from biogesture.auxiliary import AuxiliaryGestureEngine
from biogesture.gestures import GestureEngine
from biogesture.models import TrackingPacket
from biogesture.settings import Settings
from biogesture.windows import WindowsActions
from tests.test_gestures import hand


def active_drag_app():
    app = DesktopApp.__new__(DesktopApp)
    app.settings = Settings(start_paused=False)
    app.engine = GestureEngine(app.settings)
    app.auxiliary_engine = AuxiliaryGestureEngine(app.settings)
    native = Mock()
    app.actions = WindowsActions(_native=native)
    for frame in range(16):
        now = 10 + frame / 30
        app.output = app.engine.update(hand("pinch", now), now)
        for event in app.output.events:
            app.actions.handle(event)
    app.root = Mock()
    app.bus = Queue()
    app.mapper = Mock()
    app.pipeline = Mock()
    app.pipeline.latest.return_value = TrackingPacket(42, 10.5, 10.51, sample=hand("pinch", 10.5))
    app._packet = None
    app._sequence = 42
    app._last_capture = app._last_monitors = 10.5
    app._last_resource_check = 0.0
    app._cpu_percent = app._memory_mb = 0.0
    app._process = None
    app._notice_until = 0
    app._samples = deque(maxlen=120)
    app._closing = app._destroyed = app._operation = False
    app._settings_dialog = app._calibration_dialog = None
    app._camera_enabled = app.smoke = True
    app._tray = app._hook = None
    app.status = app.metrics = app.pause_button = Mock()
    app.notify = Mock()
    app._render = Mock()
    return app, native


def test_no_new_frames_watchdog_releases_drag_and_resets_mapper(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    app, native = active_drag_app()
    assert native.button.call_args_list == [(("left", True),)]
    monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: 10.9)
    app.tick()
    app.tick()
    assert native.button.call_args_list == [(("left", True),), (("left", False),)]
    assert not app.actions._held_buttons
    assert app.mapper.reset.called
    assert app.output.pointer is None
    assert not app.engine.paused
    native.move.assert_not_called()
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR], caplog.text


def test_new_packet_with_stale_landmarks_cannot_keep_drag_held(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    app, native = active_drag_app()
    app.pipeline.latest.return_value = TrackingPacket(43, 10.5, 10.51, sample=hand("pinch", 10.5))
    monkeypatch.setattr("biogesture.desktop.time.monotonic", lambda: 10.9)
    app.tick()
    assert native.button.call_args_list == [(("left", True),), (("left", False),)]
    assert not app._samples
    assert app.output.pointer is None
    assert not app.engine.paused
    native.move.assert_not_called()
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR], caplog.text


def test_shutdown_releases_drag_before_waiting_for_pipeline_stop(caplog):
    caplog.set_level(logging.ERROR)
    app, native = active_drag_app()
    app.smoke = False

    def pipeline_stop(timeout):
        assert timeout == 2
        assert not app.actions._held_buttons
        assert app.engine.paused
        return True

    app.pipeline.stop.side_effect = pipeline_stop
    app.request_close()
    assert app.closing
    assert native.button.call_args_list == [(("left", True),), (("left", False),)]
    assert app.bus.get(timeout=2) == ("close_done", True)
    app.pipeline.stop.assert_called_once_with(timeout=2)
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR], caplog.text
