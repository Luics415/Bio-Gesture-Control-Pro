"""Package boundaries and reproducible inputs; never build or run a real app."""

import json
from pathlib import Path
import shutil
import struct
import subprocess
from unittest.mock import Mock
import zipfile

import pytest

from scripts import build_portable as portable


def put(path, content=b"fixture"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def pe_file(path, subsystem=2):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x80 + 24 + 68, subsystem)
    return put(path, data)


def fake_bundle(tmp_path):
    root, bundle = tmp_path / "source", tmp_path / portable.APP_NAME
    pe_file(bundle / (portable.APP_NAME + ".exe"))
    for relative in portable.required_assets():
        put(root / relative, relative.encode())
        put(bundle / "_internal" / relative, relative.encode())
    for name in portable.PUBLIC_FILES:
        put(root / name, name.encode())
        put(bundle / name, name.encode())
    for source, destination in portable.PUBLIC_ASSET_MAP.items():
        pdf = b"%PDF-1.4\n% Synthetic packaging fixture, never rendered.\n%%EOF\n"
        put(root / source, pdf)
        put(bundle / destination, pdf)
    for relative in ("python312.dll", "_tcl_data/init.tcl", "_tk_data/tk.tcl", "licenses/PYTHON-LICENSE.txt"):
        put(bundle / "_internal" / relative)
    for name in portable.OPENVINO_DLLS:
        put(bundle / "_internal/openvino/libs" / name)
    manifest = {"files": {path.relative_to(bundle).as_posix(): portable.sha256(path)
                          for path in portable.portable_members(bundle)}}
    put(bundle / "BUILD-MANIFEST.json", json.dumps(manifest).encode())
    return root, bundle


@pytest.mark.parametrize(("version", "expected"), [
    ("2.0.0-dev.5", (2, 0, 0, 5)), ("2.0.0.dev5", (2, 0, 0, 5)), ("2.1.3", (2, 1, 3, 0)),
    ("2.7.0", (2, 7, 0, 0)),
])
def test_version_resource_is_derived_from_source(version, expected):
    assert portable.numeric_version(version) == expected


def test_application_version_is_read_without_executing_module(tmp_path):
    put(tmp_path / "biogesture/__init__.py", b'raise RuntimeError("must not execute")\n__version__ = "2.0.0-dev.5"\n')
    assert portable.application_version(tmp_path) == "2.0.0-dev.5"


def test_build_lock_preserves_every_runtime_pin_and_exact_build_tools():
    runtime = portable.pinned_packages(portable.ROOT / "requirements.lock.txt")
    build = portable.pinned_packages(portable.ROOT / "requirements-build.lock.txt")
    assert runtime and all(build.get(name) == version for name, version in runtime.items())
    assert all(build[name] == version for name, version in portable.BUILD_TOOLS.items())
    for entry in (portable.ROOT / "requirements-build.lock.txt").read_text(encoding="utf-8").split("\n\n"):
        if "==" in entry and not entry.lstrip().startswith("#"):
            assert "--hash=sha256:" in entry


def test_spec_is_windowed_onedir_without_admin_or_upx():
    spec = (portable.ROOT / "packaging/BioGestureControlPro.spec").read_text(encoding="utf-8")
    assert "console=False" in spec and "exclude_binaries=True" in spec and "COLLECT(" in spec
    assert "uac_admin=False" in spec and "upx=False" in spec
    assert 'contents_directory="_internal"' in spec
    assert "assets/brand/app.ico" in spec and "collect_data_files(\"mediapipe\"" in spec
    assert "numeric_version(version)" in spec


def test_valid_bundle_has_python_tk_approved_assets_and_public_docs(tmp_path):
    root, bundle = fake_bundle(tmp_path)
    assert portable.validate_bundle(bundle, root)
    assert "README-2.0.md" in portable.PUBLIC_FILES
    assert "README.md" in portable.PUBLIC_FILES
    assert "legacy/v1.20.36/README.md" in portable.PUBLIC_FILES
    assert not any(name.lower().endswith((".bat", ".png")) for name in portable.PUBLIC_FILES)
    assert portable.PUBLIC_ASSET_MAP == {
        "docs/manual/Manual-de-usuario.pdf": "Manual-de-usuario.pdf"}
    assert (bundle / "Manual-de-usuario.pdf").is_file()


@pytest.mark.parametrize("subsystem", [1, 3, 9])
def test_console_or_wrong_subsystem_is_rejected(tmp_path, subsystem):
    root, bundle = fake_bundle(tmp_path)
    pe_file(bundle / (portable.APP_NAME + ".exe"), subsystem)
    with pytest.raises(ValueError, match="sin consola"):
        portable.validate_bundle(bundle, root)


def test_altered_approved_artwork_is_rejected(tmp_path):
    root, bundle = fake_bundle(tmp_path)
    put(bundle / "_internal/assets/brand/splash-author.png", b"changed")
    with pytest.raises(ValueError, match="Recurso modificado"):
        portable.validate_bundle(bundle, root)


@pytest.mark.parametrize("relative", ["python312.dll", "_tcl_data/init.tcl", "_tk_data/tk.tcl",
                                     "licenses/PYTHON-LICENSE.txt"])
def test_missing_runtime_components_are_rejected(tmp_path, relative):
    root, bundle = fake_bundle(tmp_path)
    (bundle / "_internal" / relative).unlink()
    with pytest.raises(ValueError):
        portable.validate_bundle(bundle, root)


@pytest.mark.parametrize("relative", [".venv/secret.txt", "venv/old.txt", "ACTIVAR_CAMARA.bat",
                                     "_internal/output/frame.png", "_internal/settings.json",
                                     "_internal/native.log", "_internal/local-signing/key.pfx",
                                     "docs/captures/private-camera.png", "docs/unapproved.md",
                                     "docs/captures/private/session.png", "_internal/docs/captures/private/hand.png",
                                     "_internal/Docs/Captures/Private/landmarks.json"])
def test_private_and_unapproved_content_is_rejected_not_silently_packaged(tmp_path, relative):
    _, bundle = fake_bundle(tmp_path)
    put(bundle / relative)
    with pytest.raises(ValueError, match="Archivo ajeno"):
        portable.portable_members(bundle)


def test_symbolic_links_are_rejected(tmp_path, monkeypatch):
    _, bundle = fake_bundle(tmp_path)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "python312.dll" or original(self))
    with pytest.raises(ValueError, match="enlaces"):
        portable.portable_members(bundle)


def test_zip_has_stable_metadata_filtered_content_and_sha256(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    first_hash = portable.write_zip(bundle, first)
    second_hash = portable.write_zip(bundle, second)
    assert first_hash == second_hash
    assert first.with_suffix(".zip.sha256").read_text().startswith(first_hash)
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert all(name.startswith(portable.APP_NAME + "/") and "\\" not in name for name in names)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert portable.APP_NAME + "/README-2.0.md" in names
        assert portable.APP_NAME + "/docs/captures/README.md" in names
        assert portable.APP_NAME + "/Manual-de-usuario.pdf" in names
        assert not any("/output/" in name for name in names)
        assert archive.testzip() is None
    assert not first.with_suffix(".zip.partial").exists()


def test_zip_does_not_overwrite_previous_delivery(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    archive = put(tmp_path / "existing.zip", b"user artifact")
    with pytest.raises(FileExistsError):
        portable.write_zip(bundle, archive)
    assert archive.read_bytes() == b"user artifact"


def test_zip_does_not_overwrite_an_existing_hash_sidecar(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    sidecar = put(tmp_path / "existing.zip.sha256", b"previous hash")
    with pytest.raises(FileExistsError):
        portable.write_zip(bundle, tmp_path / "existing.zip")
    assert sidecar.read_bytes() == b"previous hash"
    assert not (tmp_path / "existing.zip").exists()


def test_mismatched_manifest_prevents_zip_creation(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    put(bundle / "README-2.0.md", b"changed after manifest")
    with pytest.raises(ValueError, match="manifest"):
        portable.write_zip(bundle, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()


def test_zip_hash_verification_detects_modified_payload(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    manifest = (bundle / "BUILD-MANIFEST.json").read_bytes()
    put(bundle / "README-2.0.md", b"changed after manifest")
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "x") as archive:
        for member in portable.portable_members(bundle):
            archive.write(member, portable.APP_NAME + "/" + member.relative_to(bundle).as_posix())
    assert (bundle / "BUILD-MANIFEST.json").read_bytes() == manifest
    with pytest.raises(ValueError, match="Hash"):
        portable.verify_zip(path)


@pytest.mark.parametrize("relative", ["../LICENSE", "../../private/LICENSE", "C:/Users/secret/LICENSE",
                                     "/etc/LICENSE", r"\\server\share\LICENSE"])
def test_license_metadata_cannot_escape_staging(tmp_path, relative):
    with pytest.raises(ValueError, match="licencia"):
        portable.license_target(tmp_path, "dependency", relative)


def detector_report():
    return {"ok": True, "version": portable.application_version(), "model_sha256": portable.MODEL_SHA256,
            "frames": 1, "detected_hands": 0, "error": None, "platform": "Windows", "architecture": "AMD64",
            "python": "3.12.10"}


def gaze_report():
    from biogesture.face_tracking import FACE_MODEL_SHA256
    from biogesture.gaze_neural import MODEL_ASSETS
    return {"ok": True, "version": portable.application_version(), "frozen": True, "frames": 3, "features": 6,
            "error": None, "platform": "Windows", "architecture": "AMD64", "python": "3.12.10",
            "runtime": "2024.6.0-native-build", "converter_loaded": False, "telemetry_loaded": False,
            "network_attempts": 0, "camera_opened": False, "system_input": False,
            "accuracy_validation": "not_measured", "models_sha384": {a.filename: a.sha384 for a in MODEL_ASSETS},
            "face_detector": {"frames": 1, "detected_faces": 0, "model_sha256": FACE_MODEL_SHA256}}


def test_synthetic_verification_uses_only_smoke_flags_and_isolated_paths(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    executable = tmp_path / portable.APP_NAME / (portable.APP_NAME + ".exe")

    def probe(command, **kwargs):
        if "--detector-smoke" in command:
            put(stage / "smoke-data/detector-smoke.json", json.dumps(detector_report()).encode())
        if "--gaze-smoke" in command:
            put(stage / "smoke-data/gaze-smoke.json", json.dumps(gaze_report()).encode())
        return 0

    calls = Mock(side_effect=probe)
    monkeypatch.setattr(portable, "run_probe", calls)
    monkeypatch.setenv("BIOGESTURE_FROZEN_STDIO_READY", "must-be-cleared")
    result = portable.run_smoke(executable, stage)
    assert set(result) == {"detector", "gaze", "desktop"}
    assert calls.call_count == 3
    assert calls.call_args_list[0].args[0] == [str(executable), "--detector-smoke"]
    assert calls.call_args_list[1].args[0] == [str(executable), "--gaze-smoke"]
    assert calls.call_args_list[2].args[0] == [str(executable), "--smoke", "--smoke-seconds", ".3"]
    for call in calls.call_args_list:
        assert call.kwargs["cwd"] == stage
        environment = call.kwargs["environment"]
        assert environment["BIOGESTURE_DATA_DIR"] == str(stage / "smoke-data")
        assert ".venv" not in environment["PATH"] and "PYTHONPATH" not in environment
        assert "BIOGESTURE_FROZEN_STDIO_READY" not in environment


def test_missing_detector_report_is_not_treated_as_success(tmp_path, monkeypatch):
    monkeypatch.setattr(portable, "run_probe", Mock(return_value=0))
    with pytest.raises(FileNotFoundError):
        portable.run_smoke(tmp_path / "app.exe", tmp_path)


def test_failed_smoke_does_not_continue_to_another_launch(tmp_path, monkeypatch):
    calls = Mock(return_value=1)
    monkeypatch.setattr(portable, "run_probe", calls)
    with pytest.raises(RuntimeError, match="detector"):
        portable.run_smoke(tmp_path / "app.exe", tmp_path)
    assert calls.call_count == 1


@pytest.mark.parametrize(("key", "value"), [("version", "old"), ("frames", 0), ("detected_hands", 1),
                                            ("model_sha256", "wrong"), ("platform", "Linux"),
                                            ("architecture", "ARM64"), ("python", "3.11.0"), ("error", "failure")])
def test_detector_report_checks_more_than_the_ok_flag(key, value):
    report = detector_report()
    report[key] = value
    with pytest.raises(RuntimeError, match="informe"):
        portable.validate_detector_report(report, portable.application_version())


def test_existing_smoke_data_is_not_reused(tmp_path):
    (tmp_path / "smoke-data").mkdir()
    with pytest.raises(FileExistsError):
        portable.run_smoke(tmp_path / "app.exe", tmp_path)


def test_probe_timeout_terminates_only_its_own_process_tree(tmp_path, monkeypatch):
    import psutil
    process = Mock(pid=34567)
    process.wait.side_effect = [subprocess.TimeoutExpired("own-probe", 60), 1]
    child = Mock()
    inspected = Mock()
    inspected.children.return_value = [child]
    lookup = Mock(return_value=inspected)
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(psutil, "Process", lookup)
    waited = Mock()
    monkeypatch.setattr(psutil, "wait_procs", waited)
    with pytest.raises(subprocess.TimeoutExpired):
        portable.run_probe([str(tmp_path / "app.exe"), "--detector-smoke"], cwd=tmp_path, environment={})
    lookup.assert_called_once_with(34567)
    inspected.children.assert_called_once_with(recursive=True)
    child.kill.assert_called_once()
    process.kill.assert_called_once()
    waited.assert_called_once_with([child], timeout=10)


def test_unicode_portability_runs_relocated_exe_and_isolates_all_probe_data(tmp_path, monkeypatch):
    root, bundle = fake_bundle(tmp_path)
    before = {p.relative_to(bundle).as_posix(): portable.sha256(p) for p in portable.portable_members(bundle)}
    stage = tmp_path / "build-stage"
    calls = []

    def probe(command, *, cwd, environment):
        calls.append(command)
        relocated = stage / "Prueba portable á" / portable.APP_NAME
        assert Path(command[0]) == relocated / (portable.APP_NAME + ".exe")
        assert Path(command[0]).is_file()
        assert cwd == stage / "Prueba portable á"
        assert environment["BIOGESTURE_DATA_DIR"] == str(cwd / "smoke-data")
        if "--detector-smoke" in command:
            put(cwd / "smoke-data/detector-smoke.json", json.dumps(detector_report()).encode())
        if "--gaze-smoke" in command:
            put(cwd / "smoke-data/gaze-smoke.json", json.dumps(gaze_report()).encode())
        return 0

    monkeypatch.setattr(portable, "run_probe", probe)
    result = portable.verify_unicode_portability(bundle, stage, root)
    assert set(result) == {"detector", "gaze", "desktop"}
    assert calls[0][1:] == ["--detector-smoke"]
    assert calls[1][1:] == ["--gaze-smoke"]
    assert calls[2][1:] == ["--smoke", "--smoke-seconds", ".3"]
    after = {p.relative_to(bundle).as_posix(): portable.sha256(p) for p in portable.portable_members(bundle)}
    assert before == after
    assert not (bundle / "smoke-data").exists()


def test_unicode_portability_does_not_reuse_an_old_copy(tmp_path, monkeypatch):
    root, bundle = fake_bundle(tmp_path)
    stage = tmp_path / "build-stage"
    put(stage / "Prueba portable á" / "previous-artifact", b"preserve")
    probe = Mock()
    monkeypatch.setattr(portable, "run_smoke", probe)
    with pytest.raises(FileExistsError):
        portable.verify_unicode_portability(bundle, stage, root)
    probe.assert_not_called()
    assert (stage / "Prueba portable á" / "previous-artifact").read_bytes() == b"preserve"


def test_failed_unicode_probe_prevents_creation_of_delivery_zip(tmp_path, monkeypatch):
    root, compiled_fixture = fake_bundle(tmp_path)
    monkeypatch.setattr(portable, "check_environment", Mock(return_value={}))
    monkeypatch.setattr(portable, "source_snapshot", Mock(return_value={}))
    monkeypatch.setattr(portable, "application_version", Mock(return_value="2.0.0-dev.5"))
    monkeypatch.setattr(portable, "stage_licenses", Mock())

    def compile_fixture(command, **kwargs):
        output = Path(command[command.index("--distpath") + 1]) / portable.APP_NAME
        shutil.copytree(compiled_fixture, output)

    monkeypatch.setattr(subprocess, "run", compile_fixture)
    monkeypatch.setattr(portable, "run_smoke", Mock(return_value={"detector": {"exit_code": 0}}))
    unicode_probe = Mock(side_effect=RuntimeError("controlled Unicode-path failure"))
    monkeypatch.setattr(portable, "verify_unicode_portability", unicode_probe)
    archive = Mock()
    monkeypatch.setattr(portable, "write_zip", archive)
    with pytest.raises(RuntimeError, match="Unicode-path"):
        portable.build(root)
    unicode_probe.assert_called_once()
    archive.assert_not_called()
    assert not list((root / "dist").glob("*.zip"))


def test_manual_copy_is_explicit_and_never_copies_output_or_private_captures(tmp_path):
    root, _ = fake_bundle(tmp_path)
    put(root / "output/pdf/unapproved.pdf", b"private document")
    put(root / "output/pdf/manual-preview.png", b"preview image")
    put(root / "docs/manual/unapproved.pdf", b"unapproved document")
    put(root / "docs/captures/private/hand.png", b"private photograph")
    put(root / "docs/captures/private/landmarks.json", b"private observation")
    destination = tmp_path / "public-copy"
    portable.copy_public_files(destination, root)
    copied = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    assert copied == {*portable.PUBLIC_FILES, "Manual-de-usuario.pdf"}
    source = next(iter(portable.PUBLIC_ASSET_MAP))
    assert (destination / "Manual-de-usuario.pdf").read_bytes() == (root / source).read_bytes()


def test_missing_manual_requires_prior_generation_and_does_not_copy_partial_docs(tmp_path):
    root, _ = fake_bundle(tmp_path)
    (root / next(iter(portable.PUBLIC_ASSET_MAP))).unlink()
    destination = tmp_path / "must-not-copy"
    with pytest.raises(FileNotFoundError, match="genera y revisa"):
        portable.copy_public_files(destination, root)
    assert not destination.exists()


@pytest.mark.skipif(portable.os.name != "nt" or portable.sys.version_info[:2] != (3, 12)
                    or struct.calcsize("P") != 8, reason="Preflight de compilación Windows CPython 3.12 x64")
def test_environment_check_requires_generated_pdf_without_using_local_output(tmp_path, monkeypatch):
    root, _ = fake_bundle(tmp_path)
    (root / next(iter(portable.PUBLIC_ASSET_MAP))).unlink()
    monkeypatch.setattr(portable, "pinned_packages", lambda path: dict(portable.GAZE_RUNTIME)
                        if Path(path).name == "requirements-gaze.lock.txt" else dict(portable.BUILD_TOOLS))
    monkeypatch.setattr(portable.metadata, "version", lambda name: {**portable.BUILD_TOOLS, **portable.GAZE_RUNTIME}[name])
    original_sha256 = portable.sha256
    model = root / "assets/models/hand_landmarker.task"
    monkeypatch.setattr(portable, "sha256", lambda path: portable.MODEL_SHA256 if Path(path) == model
                        else original_sha256(path))
    with pytest.raises(FileNotFoundError, match="Falta el manual PDF"):
        portable.check_environment(root)
    assert not (root / "dist").exists()
    assert not (root / next(iter(portable.PUBLIC_ASSET_MAP))).exists()


@pytest.mark.parametrize("contents", [b"", b"not a PDF", b"%PDF-3.0\n%%EOF\n", b"%PDF-1.4\ntruncated"])
def test_invalid_or_incomplete_manual_is_rejected_before_packaging(tmp_path, contents):
    root, _ = fake_bundle(tmp_path)
    put(root / next(iter(portable.PUBLIC_ASSET_MAP)), contents)
    with pytest.raises(ValueError, match="PDF"):
        portable.generated_public_assets(root)


@pytest.mark.parametrize("link_part", ["manual", "Manual-de-usuario.pdf"])
def test_manual_source_or_parent_cannot_be_a_link(tmp_path, monkeypatch, link_part):
    root, _ = fake_bundle(tmp_path)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == link_part or original(self))
    with pytest.raises(ValueError, match="enlaces"):
        portable.generated_public_assets(root)


def test_manual_bundle_copy_requires_valid_pdf_envelope(tmp_path):
    root, bundle = fake_bundle(tmp_path)
    put(bundle / "Manual-de-usuario.pdf", b"renamed text is not a manual")
    with pytest.raises(ValueError, match="cabecera PDF"):
        portable.validate_bundle(bundle, root)


def test_manual_bundle_copy_must_match_the_source_hash(tmp_path):
    root, bundle = fake_bundle(tmp_path)
    put(bundle / "Manual-de-usuario.pdf", b"%PDF-1.4\nmodified content\n%%EOF\n")
    with pytest.raises(ValueError, match="Manual PDF modificado"):
        portable.validate_bundle(bundle, root)


def test_missing_manual_in_bundle_is_rejected(tmp_path):
    root, bundle = fake_bundle(tmp_path)
    (bundle / "Manual-de-usuario.pdf").unlink()
    with pytest.raises(FileNotFoundError):
        portable.validate_bundle(bundle, root)


def test_manual_change_after_manifest_prevents_zip_creation(tmp_path):
    _, bundle = fake_bundle(tmp_path)
    put(bundle / "Manual-de-usuario.pdf", b"%PDF-1.4\nmodified after manifest\n%%EOF\n")
    with pytest.raises(ValueError, match="manifest"):
        portable.write_zip(bundle, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()


def test_source_snapshot_tracks_manual_and_builder_but_no_private_files(tmp_path):
    root, _ = fake_bundle(tmp_path)
    for relative in ("control.py", "pyproject.toml", "packaging/BioGestureControlPro.spec",
                     "scripts/build_portable.py", "scripts/build-portable.ps1", portable.MANUAL_BUILDER,
                     *portable.MANUAL_DEPENDENCIES, portable.BUILD_SUPPORT, "requirements.lock.txt", "requirements-build.lock.txt", "requirements-gaze.lock.txt",
                     "biogesture/__init__.py"):
        put(root / relative)
    put(root / "docs/captures/private/camera.png", b"private")
    put(root / "output/pdf/unapproved.pdf", b"private")
    source = next(iter(portable.PUBLIC_ASSET_MAP))
    before = portable.source_snapshot(root)
    assert source in before and portable.MANUAL_BUILDER in before
    assert portable.BUILD_SUPPORT in before
    assert portable.MANUAL_DEPENDENCIES == ("scripts/manual_hands.py",)
    assert all(name in before for name in portable.MANUAL_DEPENDENCIES)
    assert before[source] == portable.sha256(root / source)
    assert "docs/captures/private/camera.png" not in before
    assert "output/pdf/unapproved.pdf" not in before
    put(root / source, b"%PDF-1.4\nnew generation\n%%EOF\n")
    after = portable.source_snapshot(root)
    assert {name for name in before if before[name] != after[name]} == {source}
    put(root / portable.MANUAL_BUILDER, b"updated generator")
    newest = portable.source_snapshot(root)
    assert {name for name in after if after[name] != newest[name]} == {portable.MANUAL_BUILDER}
    put(root / "scripts/manual_hands.py", b"updated illustrations")
    illustrated = portable.source_snapshot(root)
    assert {name for name in newest if newest[name] != illustrated[name]} == {"scripts/manual_hands.py"}


def test_manual_generation_does_not_add_reportlab_to_app_dependencies():
    runtime = portable.pinned_packages(portable.ROOT / "requirements.lock.txt")
    assert "reportlab" not in {name.lower() for name in runtime}
    spec = (portable.ROOT / "packaging/BioGestureControlPro.spec").read_text(encoding="utf-8")
    assert portable.MANUAL_BUILDER not in spec
    assert all(name not in spec for name in portable.MANUAL_DEPENDENCIES)
