"""Export/replay diagnoses a session; it is not a live input authorization."""

from copy import deepcopy
import json
from unittest.mock import Mock, patch

import pytest

from biogesture.gaze import VALIDATION_TARGETS
from biogesture.gaze_diagnostics import build_diagnostic_report
from biogesture.gaze_replay import main, replay_diagnostic
from tests.test_gaze import observed, trained


def session_export(*, shifted=False):
    calibration = trained()
    samples = [(observed(t, (target[0] + .12 if shifted else target[0], target[1])), target)
               for t, target in enumerate(VALIDATION_TARGETS, 20)]
    calibration.validate(samples)
    return build_diagnostic_report(calibration, samples, include_samples=True)


@pytest.mark.parametrize("shifted", [True, False])
def test_replay_reproduces_raw_validation_and_never_opens_camera_or_input(shifted):
    exported = session_export(shifted=shifted)
    original = deepcopy(exported)
    with patch("biogesture.face_tracking.FaceTrackingWorker") as detector, patch("socket.socket") as network:
        replayed = replay_diagnostic(exported)
    assert replayed["acceptance_report"] == exported["acceptance_report"]
    assert replayed["ready"] is (not shifted)
    assert replayed["replay"]["desktop_input_enabled"] is False
    assert replayed["samples_included"] is False
    assert exported == original
    detector.assert_not_called()
    network.assert_not_called()


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(schema_version=True),
    lambda p: p.update(schema_version=100),
    lambda p: p.update(samples=[]),
    lambda p: p.update(limits={"mean_error": float("nan")}),
    lambda p: p.update(limits={"max_error": True}),
    lambda p: p["samples"][1].update(t_seconds=p["samples"][0]["t_seconds"]),
    lambda p: p["samples"][0].update(target=[.5, float("inf")]),
    lambda p: p["samples"][0].update(features=[1] * 9),
    lambda p: p["samples"][0].update(features=[True] * 10),
    lambda p: p["samples"][-1].update(phase="training"),
    lambda p: p["samples"][0].update(valid="true"),
    lambda p: p["samples"][0].update(t_seconds=-1),
])
def test_replay_rejects_malformed_or_reordered_measurements(mutation):
    exported = session_export()
    mutation(exported)
    with pytest.raises(ValueError):
        replay_diagnostic(exported)


def test_replay_cli_reads_only_the_selected_file(tmp_path, capsys):
    path = tmp_path / "diagnóstico.json"
    path.write_text(json.dumps(session_export()), encoding="utf-8")
    before = path.read_bytes()
    assert main([str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["replay"]["camera_opened"] is False
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_replay_cli_rejects_broken_json_without_stacktrace(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(path)])
    assert exc.value.code == 2
    assert "No se pudo reproducir" in capsys.readouterr().err


@pytest.mark.parametrize("width,height", [(0, 480), (640, 0), (-640, 480), (True, 480), (640, float("nan"))])
def test_diagnostic_geometry_refuses_invalid_frame_dimensions(width, height):
    from biogesture.face_tracking import eye_geometry_metrics
    from tests.test_gaze import face
    assert eye_geometry_metrics(face(), width, height) == {}


def test_desktop_diagnostics_export_is_explicit_and_does_not_unpause(monkeypatch, tmp_path):
    from biogesture.desktop import DesktopApp
    from tests.test_gaze_desktop import ocular_app
    app, native = ocular_app(ready=False)
    app.pipeline.latest_gaze_diagnostics.return_value = {"face_fps": 24.5}
    factory = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.GazeCalibrationDialog", factory)
    monkeypatch.setattr("biogesture.desktop.data_directory", lambda: tmp_path)
    DesktopApp.open_gaze_calibration(app)
    assert list(tmp_path.iterdir()) == []
    callbacks = factory.call_args.kwargs
    telemetry = callbacks["latest_diagnostics"]()
    assert telemetry["worker"]["face_fps"] == 24.5
    assert telemetry["camera"]["requested_width"] == app.settings.capture_width
    assert telemetry["monitor"]["width"] > 0
    path = callbacks["on_export_diagnostics"](session_export(shifted=True))
    assert path.parent == tmp_path / "diagnostics" / "gaze"
    assert json.loads(path.read_text(encoding="utf-8"))["ready"] is False
    assert app.engine.paused
    assert not app._gaze_session.calibration.ready
    assert not native.mock_calls
