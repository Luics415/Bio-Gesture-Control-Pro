"""Build and verify a portable Windows folder, without deleting existing output.

Pinned inputs improve reproducibility; this does not promise bit-identical PE
files between machines, signing, clean-PC compatibility or physical validation.
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import struct
import subprocess
import sys
import zipfile


APP_NAME = "BioGestureControlPro"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
BUILD_TOOLS = {"pyinstaller": "6.22.2", "pyinstaller-hooks-contrib": "2026.7"}
GAZE_RUNTIME = {"openvino": "2024.6.0", "openvino-telemetry": "2025.2.0"}
OPENVINO_DLLS = ("openvino.dll", "openvino_intel_cpu_plugin.dll", "openvino_ir_frontend.dll",
                "tbb12.dll", "tbbbind_2_5.dll", "tbbmalloc.dll", "tbbmalloc_proxy.dll")
PUBLIC_FILES = ("README.md", "README-2.0.md", "README-3.0.md", "legacy/v1.20.36/README.md", "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md",
                "docs/GESTURES.md", "docs/ARCHITECTURE.md", "docs/PHASES_1_4.md", "docs/DEVELOPMENT.md",
                "docs/DISTRIBUTION.md", "docs/VALIDATION.md", "docs/DELIVERY_DEV7.md", "docs/DELIVERY_DEV8.md", "docs/captures/README.md",
                "docs/PRECISION_OCULAR.md", "docs/DIAGNOSTICO_OCULAR.md", "docs/manual/Guia-3.0.md",
                "docs/ASSETS_RIGHTS.md",
                "docs/legal/README.md", "docs/legal/PRIVACIDAD.md", "docs/legal/TERMINOS.md",
                "docs/legal/COOKIES.md")
PUBLIC_ASSET_MAP = {"docs/manual/Manual-de-usuario.pdf": "Manual-de-usuario.pdf"}
MANUAL_BUILDER = "scripts/create_user_manual.py"
MANUAL_DEPENDENCIES = ("scripts/manual_hands.py",)
BUILD_SUPPORT = "packaging/build_support/sitecustomize.py"
FORBIDDEN_PARTS = {".git", ".venv", "venv", "output", "local-signing", ".env", "__pycache__"}
FORBIDDEN_NAMES = {"settings.json", "native.log", "biogesture.log"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def application_version(root=ROOT):
    tree = ast.parse((root / "biogesture/__init__.py").read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__"
                                                     for t in statement.targets):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str) and re.fullmatch(r"[0-9A-Za-z.+-]+", value):
                return value
    raise ValueError("No se pudo leer una versión válida de la aplicación")


def numeric_version(version):
    release = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    development = re.search(r"dev[.-]?(\d+)", version)
    if release is None:
        raise ValueError("La versión necesita tres componentes numéricos")
    numbers = (*map(int, release.groups()), int(development.group(1)) if development else 0)
    if any(part > 65535 for part in numbers):
        raise ValueError("La versión supera el límite de recursos PE")
    return numbers


def required_assets():
    from biogesture.gaze_neural import MODEL_ASSETS
    return ("assets/models/hand_landmarker.task", "assets/models/face_landmarker.task", "assets/models/README.md", "assets/brand/app.ico",
            "assets/brand/anchor-approved.png", "assets/brand/splash-author.png", "assets/brand/tray.png",
            "assets/brand/README.md", "assets/models/OPENVINO-LICENSE.txt",
            *("assets/models/gaze-precision/" + asset.filename for asset in MODEL_ASSETS))


def openvino_runtime_inputs():
    """Discover only local IR/CPU inference files, without importing OpenVINO.

    Importing the vendor root during build can start its optional converter's
    telemetry. Reading wheel metadata avoids executing it at collection time.
    Conversion frontends and accelerator plugins are not required by our CPU IR.
    """
    distribution = metadata.distribution("openvino")
    package = Path(distribution.locate_file("openvino"))
    binaries = []
    for name in OPENVINO_DLLS:
        source = package / "libs" / name
        if not source.is_file():
            raise FileNotFoundError(f"Falta la biblioteca ocular bloqueada: {name}")
        binaries.append((str(source), "openvino/libs"))
    modules = []
    skip = {"tools", "torch", "torchvision", "cmake", "include", "lib", "libs", "__pycache__"}
    for source in package.rglob("*.py"):
        parts = source.relative_to(package).with_suffix("").parts
        if set(parts) & skip or (parts[0] == "frontend" and len(parts) > 2):
            continue
        module_parts = parts[:-1] if parts[-1] == "__init__" else parts
        modules.append(".".join(("openvino", *module_parts)))
    return binaries, sorted(set(modules))


def build_environment(stage, root=ROOT):
    """Scope startup exclusions to the compiler and its subprocesses only."""
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment["PYTHONPATH"] = str((Path(root) / BUILD_SUPPORT).parent.resolve())
    environment["PYTHONNOUSERSITE"] = "1"
    environment["BIOGESTURE_BUILD_RUNTIME_ONLY"] = "1"
    environment["BIOGESTURE_BUILD_STAGE"] = str(stage)
    environment["PYTHONHASHSEED"] = "0"
    environment["MPLBACKEND"] = "Agg"
    return environment


def verify_build_import_exclusions(root=ROOT):
    """Fail closed if compiler or isolated workers missed our startup guard.

    The documented sitecustomize mechanism runs before vendor discovery. This
    check uses PyInstaller's public isolated API, without modifying its code.
    """
    from PyInstaller import isolated

    def inspect_startup():
        import sys
        module = sys.modules.get("sitecustomize")
        blocked = all(name in sys.modules and sys.modules[name] is None
                      for name in ("openvino.tools", "openvino_telemetry"))
        return getattr(module, "__file__", ""), blocked

    expected = (Path(root) / BUILD_SUPPORT).resolve()
    for filename, blocked in (inspect_startup(), isolated.call(inspect_startup)):
        if not blocked or not filename or Path(filename).resolve() != expected:
            raise RuntimeError("Falta el aislamiento de conversión/telemetría al compilar")


def pinned_packages(path):
    return dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", Path(path).read_text(encoding="utf-8"), re.MULTILINE))


def validate_manual_pdf(path):
    """Check the approved generated PDF envelope, not its visual correctness."""
    path = Path(path)
    with path.open("rb") as stream:
        if re.fullmatch(rb"%PDF-(?:1\.[0-7]|2\.0)", stream.read(8)) is None:
            raise ValueError("El manual no tiene una cabecera PDF válida")
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 1024))
        if not stream.read().rstrip().endswith(b"%%EOF"):
            raise ValueError("El manual PDF está incompleto: falta su marcador final")
    return sha256(path)


def generated_public_assets(root=ROOT):
    """Allow only the single reviewed, versioned PDF, never other documents."""
    root = Path(root).resolve()
    assets = {}
    for relative, destination in PUBLIC_ASSET_MAP.items():
        source = root / relative
        if not source.resolve().is_relative_to(root):
            raise ValueError("El manual PDF queda fuera del proyecto")
        for parent in (source, *source.parents):
            if parent == root:
                break
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ValueError("No se admiten enlaces en la ruta del manual PDF")
        if not source.is_file():
            raise FileNotFoundError(f"Falta el manual PDF; genera y revisa con {MANUAL_BUILDER}, "
                                    f"y conserva la copia aprobada en {relative} antes de compilar")
        validate_manual_pdf(source)
        assets[destination] = source
    return assets


def copy_public_files(bundle, root=ROOT):
    sources = {name: Path(root) / name for name in PUBLIC_FILES}
    sources.update(generated_public_assets(root))
    for destination, source in sources.items():
        target = Path(bundle) / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def source_snapshot(root=ROOT):
    root = Path(root).resolve()
    paths = [root / "control.py", root / "pyproject.toml", root / "packaging/BioGestureControlPro.spec",
             root / "scripts/build_portable.py", root / "scripts/build-portable.ps1",
             root / "requirements.lock.txt", root / "requirements-build.lock.txt",
             root / "requirements-gaze.lock.txt", root / MANUAL_BUILDER, root / BUILD_SUPPORT]
    paths += list((root / "biogesture").glob("*.py"))
    paths += [root / name for name in MANUAL_DEPENDENCIES]
    paths += [root / name for name in (*required_assets(), *PUBLIC_FILES)]
    paths += list(generated_public_assets(root).values())
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(set(paths))}


def check_environment(root=ROOT):
    if os.name != "nt" or sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        raise RuntimeError("El portable se compila con CPython 3.12 x64 en Windows")
    pins = pinned_packages(root / "requirements-build.lock.txt")
    runtime = pinned_packages(root / "requirements.lock.txt")
    if any(pins.get(name) != version for name, version in runtime.items()):
        raise RuntimeError("El bloqueo de build no conserva las versiones de ejecución")
    for name, version in pins.items():
        if metadata.version(name) != version:
            raise RuntimeError(f"Versión distinta de la bloqueada: {name}; ejecuta build-portable.ps1 -InstallBuildTools")
    for name, version in BUILD_TOOLS.items():
        if pins.get(name) != version:
            raise RuntimeError(f"Herramienta sin la versión esperada: {name}")
    gaze_pins = pinned_packages(root / "requirements-gaze.lock.txt")
    if gaze_pins != GAZE_RUNTIME:
        raise RuntimeError("El complemento ocular no coincide con las versiones esperadas")
    for name, version in gaze_pins.items():
        if metadata.version(name) != version:
            raise RuntimeError(f"Falta el complemento ocular bloqueado: {name}; ejecuta build-portable.ps1 -InstallBuildTools")
    pins.update(gaze_pins)
    if sha256(root / "assets/models/hand_landmarker.task") != MODEL_SHA256:
        raise RuntimeError("La integridad del modelo local no coincide")
    # This only discovers Tcl/Tk; it creates no window and touches no camera.
    import tkinter
    if not tkinter.TclVersion or not tkinter.TkVersion:
        raise RuntimeError("El intérprete de compilación necesita Tcl/Tk")
    source_snapshot(root)
    from biogesture.face_tracking import FACE_MODEL_SHA256
    from biogesture.gaze_neural import verified_model_bytes
    if sha256(root / "assets/models/face_landmarker.task") != FACE_MODEL_SHA256:
        raise RuntimeError("La integridad del modelo facial local no coincide")
    verified_model_bytes(root / "assets/models/gaze-precision")
    openvino_runtime_inputs()
    return pins


def stage_licenses(stage, pins):
    destination = stage / "licenses"
    destination.mkdir(parents=True)
    inventory = []
    for name, version in sorted(pins.items()):
        distribution = metadata.distribution(name)
        entry = {"name": name, "version": version, "license": distribution.metadata.get("License-Expression")
                 or distribution.metadata.get("License", ""), "license_files": []}
        for relative in distribution.files or ():
            basename = Path(str(relative)).name.lower()
            if not (basename.startswith(("license", "copying", "notice", "copyright"))
                    or ".dist-info/licenses/" in str(relative).replace("\\", "/").lower()):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            target = license_target(destination, name, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            entry["license_files"].append(target.relative_to(destination).as_posix())
        inventory.append(entry)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Falta la licencia del intérprete Python que se distribuirá")
    shutil.copy2(python_license, destination / "PYTHON-LICENSE.txt")
    (destination / "DEPENDENCIES.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")


def license_target(destination, distribution, relative):
    relative = str(relative).replace("\\", "/")
    pure = PurePosixPath(relative)
    if (pure.is_absolute() or PureWindowsPath(relative).drive or ".." in pure.parts
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", distribution)):
        raise ValueError("Ruta de licencia de dependencia no válida")
    target = Path(destination) / distribution / Path(*pure.parts)
    if not target.resolve().is_relative_to(Path(destination).resolve()):
        raise ValueError("La licencia queda fuera de la carpeta de empaquetado")
    return target


def portable_members(bundle):
    """Strict package boundary: compiled tree and explicit public files only."""
    bundle = Path(bundle).resolve()
    allowed_files = {APP_NAME + ".exe", *PUBLIC_FILES, *PUBLIC_ASSET_MAP.values(), "BUILD-MANIFEST.json"}
    public_parents = {parent.as_posix() for name in PUBLIC_FILES for parent in PurePosixPath(name).parents
                      if parent.as_posix() != "."}
    members = []
    for path in sorted(bundle.rglob("*")):
        relative = path.relative_to(bundle)
        parts = {part.lower() for part in relative.parts}
        if (path.is_symlink() or getattr(path, "is_junction", lambda: False)()
                or not path.resolve().is_relative_to(bundle)):
            raise ValueError(f"No se admiten enlaces en el portable: {relative}")
        approved = (relative.parts[0] == "_internal" or relative.as_posix() in allowed_files
                    or (path.is_dir() and relative.as_posix() in public_parents))
        private_capture = "/docs/captures/private/" in f"/{relative.as_posix().lower()}/"
        if (not approved or parts & FORBIDDEN_PARTS
                or private_capture or path.name.lower() in FORBIDDEN_NAMES
                or path.suffix.lower() in (".log", ".pfx", ".p12", ".key")):
            raise ValueError(f"Archivo ajeno al portable: {relative}")
        if path.is_file():
            members.append(path)
    return members


def pe_subsystem(path):
    """Read PE/COFF subsystem without executing the binary."""
    with Path(path).open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("El ejecutable no tiene cabecera PE")
        stream.seek(0x3c)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("Firma PE inválida")
        stream.seek(offset + 24 + 68)
        return struct.unpack("<H", stream.read(2))[0]


def validate_bundle(bundle, root=ROOT):
    bundle = Path(bundle)
    if pe_subsystem(bundle / (APP_NAME + ".exe")) != 2:
        raise ValueError("El portable debe usar subsistema gráfico de Windows, sin consola")
    internal = bundle / "_internal"
    if not (internal / "python312.dll").is_file():
        raise ValueError("Falta el intérprete Python integrado")
    if not (internal / "_tcl_data/init.tcl").is_file() or not (internal / "_tk_data/tk.tcl").is_file():
        raise ValueError("Faltan los recursos Tcl/Tk")
    for relative in required_assets():
        if sha256(internal / relative) != sha256(root / relative):
            raise ValueError(f"Recurso modificado durante el empaquetado: {relative}")
    for name in PUBLIC_FILES:
        if sha256(bundle / name) != sha256(root / name):
            raise ValueError(f"Aviso/documentación no coincide: {name}")
    for destination, source in generated_public_assets(root).items():
        if validate_manual_pdf(bundle / destination) != sha256(source):
            raise ValueError(f"Manual PDF modificado durante el empaquetado: {destination}")
    if not (internal / "licenses/PYTHON-LICENSE.txt").is_file():
        raise ValueError("Faltan las licencias incluidas")
    for name in OPENVINO_DLLS:
        if not (internal / "openvino/libs" / name).is_file():
            raise ValueError(f"Falta el runtime ocular integrado: {name}")
    if (internal / "openvino_telemetry").exists() or (internal / "openvino/tools/ovc").exists():
        raise ValueError("El portable no debe incluir el conversor ocular ni la telemetría")
    return portable_members(bundle)


def run_probe(command, *, cwd, environment, timeout=60):
    """Timeout cleanup is limited to this explicitly launched probe's PID tree."""
    process = subprocess.Popen(command, cwd=cwd, env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        import psutil
        try:
            descendants = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        for child in reversed(descendants):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        process.kill()
        process.wait(timeout=10)
        psutil.wait_procs(descendants, timeout=10)
        raise


def validate_detector_report(report, expected_version):
    if (report.get("ok") is not True or report.get("model_sha256") != MODEL_SHA256
            or report.get("version") != expected_version or report.get("frames") != 1
            or report.get("detected_hands") != 0 or report.get("error") is not None
            or report.get("platform") != "Windows" or report.get("architecture", "").lower() not in ("amd64", "x86_64")
            or not str(report.get("python", "")).startswith("3.12.")):
        raise RuntimeError("El informe del detector no confirma versión/modelo/plataforma e inferencia esperados")


def validate_gaze_report(report, expected_version):
    from biogesture.face_tracking import FACE_MODEL_SHA256
    from biogesture.gaze_neural import MODEL_ASSETS
    if (report.get("ok") is not True or report.get("version") != expected_version
            or report.get("frozen") is not True or report.get("frames") != 3
            or report.get("features") != 6 or report.get("error") is not None
            or report.get("platform") != "Windows" or report.get("architecture", "").lower() not in ("amd64", "x86_64")
            or not str(report.get("python", "")).startswith("3.12.")
            or not str(report.get("runtime", "")).startswith(GAZE_RUNTIME["openvino"])
            or report.get("converter_loaded") is not False or report.get("telemetry_loaded") is not False
            or report.get("network_attempts") != 0 or report.get("camera_opened") is not False
            or report.get("system_input") is not False or report.get("accuracy_validation") != "not_measured"
            or report.get("models_sha384") != {a.filename: a.sha384 for a in MODEL_ASSETS}
            or report.get("face_detector") != {"frames": 1, "detected_faces": 0, "model_sha256": FACE_MODEL_SHA256}):
        raise RuntimeError("El informe ocular no confirma modelos, runtime local e inferencia congelada esperados")


def run_smoke(executable, stage):
    environment = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "BIOGESTURE_RELAUNCH_TARGET", "BIOGESTURE_FROZEN_STDIO_READY"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    smoke_directory = stage / "smoke-data"
    smoke_directory.mkdir(parents=True, exist_ok=False)
    environment["BIOGESTURE_DATA_DIR"] = str(smoke_directory)
    # Run from outside the project with no Python executable on PATH.
    environment["PATH"] = os.pathsep.join((os.environ.get("SystemRoot", r"C:\Windows"),
                                           str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32")))
    results = {}
    for name, arguments in (("detector", ["--detector-smoke"]),
                            ("gaze", ["--gaze-smoke"]),
                            ("desktop", ["--smoke", "--smoke-seconds", ".3"])):
        return_code = run_probe([str(executable), *arguments], cwd=stage, environment=environment)
        if return_code:
            raise RuntimeError(f"La prueba sintética {name} falló: código {return_code}")
        results[name] = {"exit_code": return_code}
        if name == "detector":
            report = json.loads((smoke_directory / "detector-smoke.json").read_text(encoding="utf-8"))
            validate_detector_report(report, application_version())
            results[name]["report"] = report
        elif name == "gaze":
            report = json.loads((smoke_directory / "gaze-smoke.json").read_text(encoding="utf-8"))
            validate_gaze_report(report, application_version())
            results[name]["report"] = report
    return results


def verify_unicode_portability(bundle, stage, root=ROOT):
    """Run the complete relocated bundle from a path containing spaces and á.

    The original distribution stays untouched. All probe logs live beside the
    copy under this build's staging directory, never in the deliverable.
    """
    portable_members(bundle)
    unicode_stage = Path(stage) / "Prueba portable á"
    unicode_stage.mkdir(parents=True, exist_ok=False)
    relocated = unicode_stage / APP_NAME
    shutil.copytree(bundle, relocated)
    validate_bundle(relocated, root)
    return run_smoke(relocated / (APP_NAME + ".exe"), unicode_stage)


def verify_manifest(bundle):
    expected = json.loads((Path(bundle) / "BUILD-MANIFEST.json").read_text(encoding="utf-8")).get("files")
    actual = {path.relative_to(bundle).as_posix(): sha256(path) for path in portable_members(bundle)
              if path.name != "BUILD-MANIFEST.json"}
    if expected != actual:
        raise ValueError("Los archivos del portable no coinciden con su manifest")


def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        prefix = APP_NAME + "/"
        manifest_name = prefix + "BUILD-MANIFEST.json"
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        expected = manifest.get("files", {})
        expected_members = {prefix + name for name in expected} | {manifest_name}
        names = archive.namelist()
        if len(set(names)) != len(names) or set(names) != expected_members:
            raise ValueError("Los miembros del ZIP no coinciden con su manifest")
        for name, expected_hash in expected.items():
            with archive.open(prefix + name) as stream:
                actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"Hash del ZIP incorrecto: {name}")
        if archive.testzip() is not None:
            raise ValueError("La verificación CRC del ZIP falló")


def write_zip(bundle, destination):
    bundle = Path(bundle)
    destination = Path(destination)
    sidecar = destination.with_suffix(destination.suffix + ".sha256")
    if destination.exists() or sidecar.exists():
        raise FileExistsError("No se sobrescriben entregas anteriores")
    verify_manifest(bundle)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in portable_members(bundle):
            info = zipfile.ZipInfo(f"{APP_NAME}/{path.relative_to(bundle).as_posix()}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with path.open("rb") as source, archive.open(info, "w") as target:
                shutil.copyfileobj(source, target)
    verify_zip(temporary)
    temporary.rename(destination)
    digest = sha256(destination)
    with sidecar.open("x", encoding="ascii") as stream:
        stream.write(f"{digest}  {destination.name}\n")
    return digest


def build(root=ROOT):
    pins = check_environment(root)
    snapshot = source_snapshot(root)
    version = application_version(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stage = root / "build/portable" / run_id
    stage.mkdir(parents=True, exist_ok=False)
    stage_licenses(stage, pins)
    output_name = f"{APP_NAME}-{version}-windows-x64-{run_id}"
    distribution = root / "dist" / output_name
    distribution.mkdir(parents=True, exist_ok=False)
    environment = build_environment(stage, root)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--workpath", str(stage / "pyinstaller"), "--distpath", str(distribution),
                    str(root / "packaging/BioGestureControlPro.spec")], cwd=root, env=environment, check=True)
    bundle = distribution / APP_NAME
    copy_public_files(bundle, root)
    validate_bundle(bundle, root)
    smoke_results = run_smoke(bundle / (APP_NAME + ".exe"), stage)
    smoke_results["unicode_path"] = verify_unicode_portability(bundle, stage, root)
    if source_snapshot(root) != snapshot:
        raise RuntimeError("El código o recursos cambiaron durante la compilación; no se creará el ZIP")
    manifest = {"application": APP_NAME, "version": version, "target": "Windows x64 / CPython 3.12",
                "format": "onedir-windowed", "signed": False, "physical_validation": "pending",
                "clean_pc_validation": "pending", "build_tools": BUILD_TOOLS, "source_sha256": snapshot,
                "synthetic_checks": smoke_results,
                "files": {path.relative_to(bundle).as_posix(): sha256(path) for path in portable_members(bundle)}}
    (bundle / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = root / "dist" / (output_name + ".zip")
    digest = write_zip(bundle, archive)
    print(json.dumps({"bundle": str(bundle), "archive": str(archive), "sha256": digest}, ensure_ascii=False, indent=2))
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compilar y verificar el portable Windows sin publicar ni firmar")
    parser.add_argument("--check", action="store_true", help="Comprobar herramientas y recursos sin compilar")
    args = parser.parse_args(argv)
    if args.check:
        check_environment()
        print("Herramientas y recursos de empaquetado comprobados; no se compiló ni se abrió la cámara.")
    else:
        build()


if __name__ == "__main__":
    main()
