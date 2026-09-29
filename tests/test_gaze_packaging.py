"""Ocular distribution contracts, fake inference unless explicitly opted in."""

import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from biogesture import gaze_smoke, startup
from scripts import build_portable as portable
from tests.test_packaging import fake_bundle, gaze_report, put


def test_precision_assets_and_documentation_are_explicit_not_private():
    from biogesture.gaze_neural import MODEL_ASSETS
    assets = portable.required_assets()
    assert "assets/models/OPENVINO-LICENSE.txt" in assets
    assert all("assets/models/gaze-precision/" + a.filename in assets for a in MODEL_ASSETS)
    assert "docs/PRECISION_OCULAR.md" in portable.PUBLIC_FILES
    assert "README-3.0.md" in portable.PUBLIC_FILES
    assert not any("diagnostics/gaze" in name or "private" in name for name in assets)


def test_spec_excludes_and_rejects_converter_and_telemetry_even_inside_python_archive():
    spec = (portable.ROOT / "packaging/BioGestureControlPro.spec").read_text(encoding="utf-8")
    assert '"openvino.tools", "openvino_telemetry"' in spec
    assert 'for module_name, _, _ in a.pure:' in spec
    assert 'module_name.startswith("openvino_telemetry.")' in spec
    assert 'module_name.startswith("openvino.tools.")' in spec


def test_runtime_collection_does_not_import_vendor_converter_and_uses_only_cpu_ir(tmp_path, monkeypatch):
    package = tmp_path / "openvino"
    for name in portable.OPENVINO_DLLS:
        put(package / "libs" / name)
    for name in ("__init__.py", "runtime/__init__.py", "properties/hint/__init__.py", "frontend/frontend.py",
                 "tools/ovc/convert.py", "torch/__init__.py", "frontend/tensorflow/utils.py"):
        put(package / name, b'raise AssertionError("must not execute vendor code")')
    distribution = SimpleNamespace(locate_file=lambda relative: tmp_path / relative)
    monkeypatch.setattr(portable.metadata, "distribution", lambda name: distribution)
    binaries, modules = portable.openvino_runtime_inputs()
    assert {Path(source).name for source, _ in binaries} == set(portable.OPENVINO_DLLS)
    assert all(destination == "openvino/libs" for _, destination in binaries)
    assert modules == ["openvino", "openvino.frontend.frontend", "openvino.properties.hint", "openvino.runtime"]
    assert "openvino_intel_gpu_plugin.dll" not in portable.OPENVINO_DLLS
    assert "openvino_onnx_frontend.dll" not in portable.OPENVINO_DLLS


def test_missing_cpu_plugin_stops_runtime_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(portable.metadata, "distribution", lambda name: SimpleNamespace(locate_file=lambda p: tmp_path / p))
    with pytest.raises(FileNotFoundError, match="biblioteca ocular"):
        portable.openvino_runtime_inputs()


def test_build_environment_does_not_modify_parent_or_use_external_python_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "unrelated-path")
    monkeypatch.setenv("PYTHONHOME", "unrelated-python")
    monkeypatch.delenv("BIOGESTURE_BUILD_RUNTIME_ONLY", raising=False)
    before = dict(os.environ)
    environment = portable.build_environment(tmp_path)
    assert environment["PYTHONPATH"] == str((portable.ROOT / portable.BUILD_SUPPORT).parent)
    assert environment["BIOGESTURE_BUILD_RUNTIME_ONLY"] == "1"
    assert "PYTHONHOME" not in environment
    assert dict(os.environ) == before


def test_build_startup_exclusions_reach_real_pyinstaller_isolated_workers(tmp_path):
    pytest.importorskip("PyInstaller", reason="Optional pinned build tool, not an app dependency")
    program = '''
from scripts.build_portable import verify_build_import_exclusions
verify_build_import_exclusions()
from PyInstaller import isolated
def attempt_imports():
    import importlib
    blocked = []
    for name in ("openvino.tools", "openvino.tools.ovc", "openvino_telemetry"):
        try:
            importlib.import_module(name)
        except ImportError:
            blocked.append(name)
    return blocked
assert len(attempt_imports()) == 3
assert len(isolated.call(attempt_imports)) == 3
'''
    result = subprocess.run([sys.executable, "-c", program], cwd=portable.ROOT,
                            env=portable.build_environment(tmp_path), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_build_startup_file_is_inactive_without_private_flag(tmp_path):
    pytest.importorskip("PyInstaller", reason="Optional pinned build tool, not an app dependency")
    environment = portable.build_environment(tmp_path)
    environment.pop("BIOGESTURE_BUILD_RUNTIME_ONLY")
    program = '''
import sys
assert "openvino.tools" not in sys.modules
assert "openvino_telemetry" not in sys.modules
from scripts.build_portable import verify_build_import_exclusions
try:
    verify_build_import_exclusions()
except RuntimeError:
    pass
else:
    raise AssertionError("unguarded build must fail closed")
'''
    result = subprocess.run([sys.executable, "-c", program], cwd=portable.ROOT,
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_build_startup_file_and_exclusion_check_are_not_distributed():
    spec = (portable.ROOT / "packaging/BioGestureControlPro.spec").read_text(encoding="utf-8")
    assert "verify_build_import_exclusions(ROOT)" in spec
    assert '"sitecustomize"' in spec
    assert portable.BUILD_SUPPORT not in portable.PUBLIC_FILES
    assert portable.BUILD_SUPPORT not in portable.required_assets()


@pytest.mark.parametrize("name", portable.OPENVINO_DLLS)
def test_missing_openvino_dll_rejects_portable(tmp_path, name):
    root, bundle = fake_bundle(tmp_path)
    (bundle / "_internal/openvino/libs" / name).unlink()
    with pytest.raises(ValueError, match="runtime ocular"):
        portable.validate_bundle(bundle, root)


@pytest.mark.parametrize("relative", ["openvino_telemetry", "openvino/tools/ovc"])
def test_converter_or_telemetry_payload_rejects_portable(tmp_path, relative):
    root, bundle = fake_bundle(tmp_path)
    put(bundle / "_internal" / relative / "__init__.py")
    with pytest.raises(ValueError, match="telemetría"):
        portable.validate_bundle(bundle, root)


@pytest.mark.parametrize(("key", "value"), [("version", "wrong"), ("frozen", False), ("frames", 0),
    ("features", 0), ("error", "failure"), ("runtime", "not-OpenVINO"), ("converter_loaded", True),
    ("telemetry_loaded", True), ("network_attempts", 1), ("camera_opened", True), ("system_input", True),
    ("accuracy_validation", "passed"), ("models_sha384", {}), ("face_detector", {}), ("platform", "Linux")])
def test_gaze_report_is_not_accepted_by_ok_flag_alone(key, value):
    report = gaze_report()
    portable.validate_gaze_report(report, portable.application_version())
    report[key] = value
    with pytest.raises(RuntimeError, match="informe ocular"):
        portable.validate_gaze_report(report, portable.application_version())


def test_gaze_smoke_dispatch_precedes_window_mutex_and_actions(monkeypatch):
    probe = Mock(return_value=0)
    popup, instance = Mock(), Mock()
    monkeypatch.setattr(gaze_smoke, "run_gaze_smoke", probe)
    monkeypatch.setattr(startup, "setup_logging", Mock())
    monkeypatch.setattr(startup, "redirect_native_output", Mock())
    monkeypatch.setattr(startup, "configure_smoke_data_directory", Mock())
    monkeypatch.setattr(startup.tk, "Tk", popup)
    monkeypatch.setattr(startup, "SingleInstance", instance)
    assert startup.main(["--gaze-smoke"]) == 0
    probe.assert_called_once_with(startup.resource_path("assets/models"), startup.data_directory() / "gaze-smoke.json", console=False)
    popup.assert_not_called()
    instance.assert_not_called()


@pytest.mark.parametrize("other", ["--smoke", "--detector-smoke"])
def test_gaze_probe_mode_cannot_be_combined_with_other_smokes(other):
    with pytest.raises(SystemExit) as error:
        startup.parse_arguments(["--gaze-smoke", other])
    assert error.value.code == 2


def test_gaze_probe_bootstrap_failure_has_no_popup(monkeypatch):
    popup = Mock()
    monkeypatch.setattr(startup, "main", Mock(side_effect=OSError("controlled failure")))
    monkeypatch.setattr(startup.ctypes.windll.user32, "MessageBoxW", popup)
    assert startup.run(["--gaze-smoke"]) == 1
    popup.assert_not_called()


@pytest.fixture
def fake_inference(monkeypatch):
    extractor = SimpleNamespace(extract=Mock(return_value=(0., 0., -1., 0., 0., 0.)), close=Mock())
    monkeypatch.setattr(gaze_smoke, "probe_face_model", Mock(return_value={"frames": 1, "detected_faces": 0}))
    monkeypatch.setattr(gaze_smoke, "NeuralGazeExtractor", Mock(return_value=extractor))
    monkeypatch.setitem(sys.modules, "openvino.runtime", SimpleNamespace(get_version=lambda: "2024.6.0-synthetic"))
    return extractor


def test_synthetic_geometry_matches_preprocessing_without_real_image():
    from biogesture.gaze_neural import prepare_inputs
    pixels, points = gaze_smoke.synthetic_inputs()
    assert pixels.dtype == np.uint8 and pixels.shape == (480, 640, 3)
    assert len(points) == 478
    assert all(np.isfinite(p).all() for p in prepare_inputs(pixels, points).values())


def test_gaze_report_closes_runtime_without_personal_data(tmp_path, fake_inference):
    report_path = tmp_path / "gaze-smoke.json"
    before = socket.socket.connect
    assert gaze_smoke.run_gaze_smoke(tmp_path, report_path) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] and report["frames"] == 3 and report["features"] == 6
    assert report["accuracy_validation"] == "not_measured"
    assert report["network_attempts"] == 0
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")
    fake_inference.close.assert_called_once()
    assert socket.socket.connect is before


@pytest.mark.parametrize("bad", [(0., 0., 0., 0., 0., 0.), (math.nan, 0., -1., 0., 0., 0.), ()])
def test_invalid_direction_fails_probe_and_still_closes_runtime(tmp_path, fake_inference, bad):
    fake_inference.extract.return_value = bad
    destination = tmp_path / "probe.json"
    assert gaze_smoke.run_gaze_smoke(tmp_path, destination) == 1
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert not report["ok"] and report["error"] == "ValueError"
    fake_inference.close.assert_called_once()


def test_network_attempt_fails_even_if_library_swallows_exception(tmp_path, fake_inference):
    def tries_network(*args):
        try:
            socket.getaddrinfo("should-not-resolve.invalid", 443)
        except RuntimeError:
            pass
        return (0., 0., -1., 0., 0., 0.)
    fake_inference.extract.side_effect = tries_network
    destination = tmp_path / "probe.json"
    assert gaze_smoke.run_gaze_smoke(tmp_path, destination) == 1
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["network_attempts"] == 3 and not report["ok"]


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_OPENVINO") != "1", reason="Explicit native synthetic probe")
def test_fresh_source_probe_loads_face_and_gaze_models_without_camera_or_network(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["BIOGESTURE_DATA_DIR"] = str(tmp_path / "ocular diagnóstico á")
    result = subprocess.run([sys.executable, str(root / "control.py"), "--gaze-smoke"],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((Path(environment["BIOGESTURE_DATA_DIR"]) / "gaze-smoke.json").read_text(encoding="utf-8"))
    assert report["ok"] and not report["frozen"] and report["frames"] == 3
    assert not report["converter_loaded"] and not report["telemetry_loaded"] and report["network_attempts"] == 0
