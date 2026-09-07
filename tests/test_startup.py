"""Startup guards, without opening a camera or a desktop window."""

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from biogesture.models import TrackingPacket
from biogesture import startup


def test_status_packet_does_not_dismiss_author_splash():
    assert not startup.startup_ready(None)
    assert not startup.startup_ready(TrackingPacket(0, 1, 1, status="PREPARANDO DETECCIÓN"))
    assert startup.startup_ready(TrackingPacket(1, 1, 1, rgb=object()))
    assert startup.startup_ready(TrackingPacket(2, 1, 1, error="Cámara no disponible"))


def test_model_integrity_is_checked_before_loading(tmp_path, monkeypatch):
    model = tmp_path / "model.task"
    monkeypatch.setattr(startup, "resource_path", lambda path: model)
    with pytest.raises(FileNotFoundError):
        startup.verify_model()
    model.write_bytes(b"controlled test model")
    with pytest.raises(ValueError, match="incompleto"):
        startup.verify_model()
    monkeypatch.setattr(startup, "MODEL_SHA256", hashlib.sha256(model.read_bytes()).hexdigest())
    assert startup.verify_model() == model


def test_pythonw_bootstrap_error_is_visible_and_returns_failure(monkeypatch):
    def broken_main(argv):
        raise OSError("controlled failure")
    notify = Mock()
    monkeypatch.setattr(startup, "main", broken_main)
    monkeypatch.setattr(startup.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(MessageBoxW=notify)))
    assert startup.run([]) == 1
    notify.assert_called_once()
    assert "controlled failure" in notify.call_args.args[1]


@pytest.mark.parametrize("frozen", [False, True])
def test_visual_diagnostics_are_explicit_for_source_and_distribution(monkeypatch, frozen):
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    assert startup.parse_arguments([]).diagnostic_visuals is False
    assert startup.parse_arguments(["--diagnostics"]).diagnostic_visuals is True
    assert startup.parse_arguments(["--clean-ui"]).diagnostic_visuals is False


def test_cli_help_limits_diagnostics_to_status_outside_the_camera(capsys):
    with pytest.raises(SystemExit) as error:
        startup.parse_arguments(["--help"])
    assert error.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "Mostrar el estado de diagnóstico fuera del área de cámara" in help_text
    assert "Ocultar el estado externo; puntos según Ajustes" in help_text
    assert "Mostrar puntos" not in help_text


@pytest.mark.parametrize("arguments", [["--clean-ui", "--diagnostics"], ["--smoke", "--detector-smoke"]])
def test_conflicting_startup_modes_are_rejected(arguments):
    with pytest.raises(SystemExit) as error:
        startup.parse_arguments(arguments)
    assert error.value.code == 2


def test_frozen_smoke_uses_user_data_not_the_bundle(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("BIOGESTURE_DATA_DIR", raising=False)
    base = Path.cwd() / "output" / "user-data"
    monkeypatch.setenv("LOCALAPPDATA", str(base))
    bundle = Mock(side_effect=AssertionError("Bundle resources must stay read-only"))
    monkeypatch.setattr(startup, "resource_path", bundle)
    assert startup.configure_smoke_data_directory() == base / "BioGestureControlPro" / "smoke"
    bundle.assert_not_called()


@pytest.mark.parametrize("frozen", [False, True])
def test_smoke_preserves_an_explicit_isolated_data_directory(monkeypatch, frozen):
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    override = Path.cwd() / "output" / "explicit-smoke-data"
    monkeypatch.setenv("BIOGESTURE_DATA_DIR", str(override))
    assert startup.configure_smoke_data_directory() == override


def test_frozen_recovery_does_not_request_external_python_or_bat(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    text = startup.recovery_instructions()
    assert "Extrae el paquete completo" in text
    assert str(startup.data_directory()) in text
    assert ".bat" not in text and "Python" not in text


def test_detector_smoke_dispatch_has_no_window_mutex_or_actions(monkeypatch):
    from biogesture import detector_smoke

    probe = Mock(return_value=0)
    popup = Mock()
    instance = Mock()
    monkeypatch.setattr(detector_smoke, "run_detector_smoke", probe)
    monkeypatch.setattr(startup, "setup_logging", Mock())
    monkeypatch.setattr(startup, "redirect_native_output", Mock())
    monkeypatch.setattr(startup.tk, "Tk", popup)
    monkeypatch.setattr(startup, "SingleInstance", instance)
    assert startup.main(["--detector-smoke"]) == 0
    probe.assert_called_once_with(startup.resource_path("assets/models/hand_landmarker.task"), startup.MODEL_SHA256,
                                  startup.data_directory() / "detector-smoke.json", console=False)
    popup.assert_not_called()
    instance.assert_not_called()


def test_detector_smoke_bootstrap_failure_returns_code_without_popup(monkeypatch):
    popup = Mock()
    monkeypatch.setattr(startup, "main", Mock(side_effect=OSError("controlled failure")))
    monkeypatch.setattr(startup.ctypes.windll.user32, "MessageBoxW", popup)
    assert startup.run(["--detector-smoke"]) == 1
    popup.assert_not_called()


def fake_detector(monkeypatch):
    context = MagicMock()
    context.__enter__.return_value.detect.return_value = SimpleNamespace(hand_landmarks=[])
    factory = Mock(return_value=context)
    mp = SimpleNamespace(
        Image=Mock(), ImageFormat=SimpleNamespace(SRGB="SRGB"),
        tasks=SimpleNamespace(BaseOptions=Mock(), vision=SimpleNamespace(
            HandLandmarkerOptions=Mock(), RunningMode=SimpleNamespace(IMAGE="IMAGE"),
            HandLandmarker=SimpleNamespace(create_from_options=factory))))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    return mp, context, factory


def test_detector_probe_writes_non_identifying_report_after_inference_and_close(tmp_path, monkeypatch, capsys):
    from biogesture.detector_smoke import run_detector_smoke

    mp, context, factory = fake_detector(monkeypatch)
    model = tmp_path / "test.task"
    model.write_bytes(b"synthetic-model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    destination = tmp_path / "detector-smoke.json"
    assert run_detector_smoke(model, digest, destination) == 0
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["ok"] is True and report["frames"] == 1 and report["detected_hands"] == 0
    assert report["model_sha256"] == digest and report["error"] is None
    assert {"version", "platform", "architecture", "python"} <= report.keys()
    assert str(tmp_path) not in destination.read_text(encoding="utf-8")
    assert mp.Image.call_args.kwargs["data"].shape == (480, 640, 3)
    assert not mp.Image.call_args.kwargs["data"].any()
    mp.tasks.BaseOptions.assert_called_once_with(model_asset_buffer=b"synthetic-model")
    factory.assert_called_once()
    context.__enter__.return_value.detect.assert_called_once()
    context.__exit__.assert_called_once()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("stage", ["inference", "close"])
def test_detector_failure_report_has_no_private_exception_path(tmp_path, monkeypatch, stage):
    from biogesture.detector_smoke import run_detector_smoke

    _, context, _ = fake_detector(monkeypatch)
    error = RuntimeError("private-user-secret in a machine-specific path")
    if stage == "inference":
        context.__enter__.return_value.detect.side_effect = error
    else:
        context.__exit__.side_effect = error
    model = tmp_path / "test.task"
    model.write_bytes(b"synthetic-model")
    destination = tmp_path / "detector-smoke.json"
    assert run_detector_smoke(model, hashlib.sha256(model.read_bytes()).hexdigest(), destination) == 1
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["ok"] is False and report["error"] == "RuntimeError"
    assert "private-user-secret" not in destination.read_text(encoding="utf-8")
    context.__exit__.assert_called_once()


def test_detector_hash_failure_never_initializes_native_model(tmp_path, monkeypatch):
    from biogesture.detector_smoke import run_detector_smoke

    _, _, factory = fake_detector(monkeypatch)
    model = tmp_path / "test.task"
    model.write_bytes(b"unapproved-model")
    destination = tmp_path / "detector-smoke.json"
    assert run_detector_smoke(model, "incorrect-hash", destination) == 1
    factory.assert_not_called()
    assert json.loads(destination.read_text(encoding="utf-8"))["error"] == "ValueError"
