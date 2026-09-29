"""Dialog-owned Tcl traces must be released on their creating thread."""

from queue import Queue
import os
from unittest.mock import Mock

import pytest

from biogesture.coordinates import RectMonitor
from biogesture.desktop import DesktopApp
from biogesture.gestures import GestureEngine
from biogesture.settings import Settings
from biogesture.windows import WindowsActions


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Ciclo de vida real optativo de Tk")
@pytest.mark.parametrize("close_method", ["button", "destroy"])
def test_settings_removes_its_variable_trace_on_every_close(monkeypatch, tmp_path, close_method):
    import tkinter as tk
    import weakref

    monkeypatch.setenv("BIOGESTURE_DATA_DIR", str(tmp_path))
    factory = Mock(side_effect=AssertionError("No camera in lifetime test"))
    monkeypatch.setattr("biogesture.desktop.TrackingPipeline", factory)
    traces = []
    original = tk.Variable.trace_add

    def traced(variable, mode, callback):
        name = original(variable, mode, callback)
        traces.append((weakref.ref(variable), name))
        return name

    monkeypatch.setattr(tk.Variable, "trace_add", traced)
    root = tk.Tk()
    root.withdraw()
    settings = Settings()
    app = DesktopApp(root, settings, Queue(), GestureEngine(settings), WindowsActions(dry_run=True), None,
                     [RectMonitor("test", "Prueba", 0, 0, 800, 600, True)], smoke=True)
    try:
        app.open_settings()
        root.update_idletasks()
        dialog = app._settings_dialog
        assert traces
        if close_method == "destroy":
            dialog.destroy()
        else:
            buttons = next(w for w in dialog.winfo_children() if w.winfo_class() == "TFrame"
                           and any(c.winfo_class() == "TButton" and c.cget("text") == "Cancelar"
                                   for c in w.winfo_children()))
            next(w for w in buttons.winfo_children()
                 if w.winfo_class() == "TButton" and w.cget("text") == "Cancelar").invoke()
        assert app._settings_dialog is None
        # No gc.collect: removing traces breaks ownership synchronously.
        for reference, command in traces:
            variable = reference()
            assert variable is None or not variable.trace_info()
            assert not root.tk.call("info", "commands", command)
        factory.assert_not_called()
    finally:
        app.request_close()
        app.tick()
