"""Choose the project's interpreter before loading any desktop or ML code."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
RELAUNCH_GUARD = "BIOGESTURE_RELAUNCH_TARGET"
FROZEN_STDIO_GUARD = "BIOGESTURE_FROZEN_STDIO_READY"


def relaunch_frozen_if_needed(argv):
    """Give windowed native libraries valid inherited handles exactly once.

    A packaged executable must relaunch itself, never an external Python. Test
    modes wait and return the child's status; the normal launch hands off.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return None
    target = Path(sys.executable).resolve()
    if os.environ.get(FROZEN_STDIO_GUARD) == str(target):
        return None
    if sys.stdout is not None and sys.stderr is not None:
        return None
    environment = os.environ.copy()
    environment[FROZEN_STDIO_GUARD] = str(target)
    # Public PyInstaller restart option; do not alter its private _PYI_* state.
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    options = dict(cwd=str(target.parent), env=environment, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    command = [str(target), *argv]
    if any(argument in argv for argument in ("--smoke", "--detector-smoke", "--gaze-smoke", "--console")):
        return subprocess.run(command, check=False, **options).returncode
    subprocess.Popen(command, **options)
    return 0


def relaunch_if_needed(argv):
    """Return True after handing a normal launch to the isolated GUI runtime.

    --smoke stays in the caller for test exit codes. --console keeps a developer
    console, but still uses the project's environment when started globally.
    """
    if os.name != "nt" or getattr(sys, "frozen", False) or any(arg in argv for arg in ("--smoke", "--detector-smoke", "--gaze-smoke", "--help", "-h")):
        return False
    console = "--console" in argv
    target = PROJECT_ROOT / ".venv" / "Scripts" / ("python.exe" if console else "pythonw.exe")
    same_interpreter = Path(sys.executable).resolve() == target.resolve()
    handed_off = os.environ.get(RELAUNCH_GUARD) == str(target)
    # A direct WScript/pythonw start can have no C stdio handles. Spawn once with
    # explicit handles so native libraries get valid streams from process birth.
    if same_interpreter and (console or handed_off or (sys.stdout is not None and sys.stderr is not None)):
        return False
    if handed_off:
        raise RuntimeError("El entorno local no pudo iniciarse correctamente. Ejecuta PREPARAR_DESARROLLO.bat.")
    if not target.is_file():
        raise FileNotFoundError("Falta el entorno local de Bio-Gesture. Ejecuta PREPARAR_DESARROLLO.bat antes de iniciar.")
    environment = os.environ.copy()
    environment[RELAUNCH_GUARD] = str(target)
    environment["PYTHONNOUSERSITE"] = "1"
    # These Python-wide overrides can otherwise defeat an explicitly chosen venv.
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    command = [str(target), str(PROJECT_ROOT / "control.py"), *argv]
    if console:
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), env=environment, check=False)
        if result.returncode:
            raise RuntimeError(f"El intérprete local terminó con código {result.returncode}.")
    else:
        subprocess.Popen(command, cwd=str(PROJECT_ROOT), env=environment,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        frozen_result = relaunch_frozen_if_needed(argv)
        if frozen_result is not None:
            return frozen_result
        if relaunch_if_needed(argv):
            return 0
    except (OSError, RuntimeError) as exc:
        if any(flag in argv for flag in ("--detector-smoke", "--gaze-smoke")):
            return 1
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, str(exc), "Bio-Gesture Control Pro", 0x10)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    from biogesture.startup import run
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
