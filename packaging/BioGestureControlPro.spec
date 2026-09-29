# Windows x64 onedir/windowed; run through scripts/build-portable.ps1.
import os
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_portable import APP_NAME, application_version, numeric_version, required_assets, openvino_runtime_inputs, verify_build_import_exclusions

STAGE = Path(os.environ["BIOGESTURE_BUILD_STAGE"]).resolve()
if not STAGE.is_relative_to((ROOT / "build").resolve()) or not (STAGE / "licenses").is_dir():
    raise RuntimeError("Usa scripts/build-portable.ps1 para preparar los recursos de empaquetado")
verify_build_import_exclusions(ROOT)

datas = [(str(ROOT / relative), str(Path(relative).parent)) for relative in required_assets()]
datas += collect_data_files("mediapipe", excludes=["**/*_test*", "**/testdata/**", "**/tests/**"])
datas += copy_metadata("mediapipe") + copy_metadata("pystray") + copy_metadata("pynput")
datas += copy_metadata("openvino")
datas += [(str(STAGE / "licenses"), "licenses")]
ocular_binaries, ocular_imports = openvino_runtime_inputs()

version = application_version(ROOT)
version_resource = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numeric_version(version), prodvers=numeric_version(version), mask=0x3f,
                     flags=0x2, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [
        StringStruct("CompanyName", "Luics415"),
        StringStruct("FileDescription", "Bio-Gesture Control Pro"),
        StringStruct("FileVersion", version),
        StringStruct("InternalName", APP_NAME),
        StringStruct("LegalCopyright", "Desarrollado por Luics415"),
        StringStruct("OriginalFilename", APP_NAME + ".exe"),
        StringStruct("ProductName", "Bio-Gesture Control Pro"),
        StringStruct("ProductVersion", version),
    ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)

a = Analysis(
    [str(ROOT / "control.py")], pathex=[str(ROOT)],
    binaries=collect_dynamic_libs("mediapipe") + ocular_binaries, datas=datas,
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32",
                   "mediapipe.python._framework_bindings", "PIL._tkinter_finder", "openvino._pyopenvino"] + ocular_imports,
    hookspath=[], runtime_hooks=[],
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
    excludes=["pytest", "pip", "piptools", "IPython", "notebook", "tensorflow", "torch", "sitecustomize",
              "mediapipe.tasks.python.genai.converter", "openvino.tools", "openvino_telemetry", "openvino.torch", "openvino.preprocess.torchvision",
              "openvino.frontend.tensorflow", "openvino.frontend.tensorflow_lite", "openvino.frontend.pytorch",
              "openvino.frontend.paddle", "openvino.frontend.onnx", "openvino.frontend.jax"],
    noarchive=False,
)
for module_name, _, _ in a.pure:
    if (module_name == "openvino_telemetry" or module_name.startswith("openvino_telemetry.")
            or module_name == "openvino.tools" or module_name.startswith("openvino.tools.")):
        raise RuntimeError("El análisis intentó incluir conversión/telemetría ocular en el ejecutable")
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(ROOT / "assets/brand/app.ico"), version=version_resource,
          uac_admin=False, contents_directory="_internal")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
