"""Read-only environment checks: never opens a camera or sends input events."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import platform
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_environment() -> dict:
    checks = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    record("Windows x64 / Python 3.12", platform.system() == "Windows"
           and sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8,
           f"{platform.system()} {platform.machine()}, Python {platform.python_version()}")
    record("Entorno .venv", Path(sys.prefix).resolve() == (ROOT / ".venv").resolve(), sys.prefix)

    requirements = ROOT / "requirements.in"
    if not requirements.is_file():
        record("Dependencias directas", False, "Falta requirements.in")
    else:
        for name, expected in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s#]+)", requirements.read_text("utf-8"), re.MULTILINE):
            try:
                installed = importlib.metadata.version(name)
                record(name, installed == expected, f"{installed}; esperado {expected}")
            except importlib.metadata.PackageNotFoundError:
                record(name, False, "No instalado")

    for package in ("opencv-python", "opencv-python-headless", "opencv-contrib-python-headless"):
        try:
            installed = importlib.metadata.version(package)
            record(f"Conflicto {package}", False, f"Instalado {installed}; comparte cv2 con opencv-contrib-python")
        except importlib.metadata.PackageNotFoundError:
            pass

    # Imports only. No Tk root, VideoCapture, MediaPipe task or input controller is created.
    for module in ("_tkinter", "numpy", "cv2", "mediapipe", "PIL", "pynput", "pystray", "psutil", "comtypes", "pycaw"):
        try:
            importlib.import_module(module)
            record(f"Importar {module}", True, "Disponible")
        except Exception as error:
            record(f"Importar {module}", False, f"{type(error).__name__}: {error}")

    model = ROOT / "assets" / "models" / "hand_landmarker.task"
    model_readme = model.with_name("README.md")
    if model.is_file() and model_readme.is_file():
        with model.open("rb") as model_file:
            digest = hashlib.file_digest(model_file, "sha256").hexdigest()
        expected = re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", model_readme.read_text("utf-8").lower())
        record("Modelo local SHA-256", digest in expected, digest)
    else:
        record("Modelo local SHA-256", False, "Falta el modelo o su registro de integridad")

    return {"ok": all(check["ok"] for check in checks), "checks": checks,
            "camera_opened": False, "input_sent": False}


def main() -> int:
    report = check_environment()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
