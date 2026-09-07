"""Interpreter selection and native logs; never starts the camera or controls."""

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

import control


def prepared_project(tmp_path, monkeypatch):
    project = tmp_path / "Project with spaces"
    scripts = project / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    for executable in ("python.exe", "pythonw.exe"):
        (scripts / executable).write_bytes(b"test placeholder; not executable")
    monkeypatch.setattr(control, "PROJECT_ROOT", project)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "global" / "python.exe"))
    monkeypatch.delenv(control.RELAUNCH_GUARD, raising=False)
    return project


def test_global_python_relaunches_absolute_local_pythonw_without_console(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    monkeypatch.setenv("PYTHONPATH", "unrelated-global-packages")
    monkeypatch.setenv("PYTHONHOME", "global-python")
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.relaunch_if_needed([])
    command = popen.call_args.args[0]
    options = popen.call_args.kwargs
    assert command == [str(project / ".venv" / "Scripts" / "pythonw.exe"), str(project / "control.py")]
    assert options["cwd"] == str(project)
    assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert options["env"][control.RELAUNCH_GUARD] == command[0]
    assert options["env"]["PYTHONNOUSERSITE"] == "1"
    assert "PYTHONPATH" not in options["env"]
    assert "PYTHONHOME" not in options["env"]


def test_local_console_python_also_switches_to_pythonw_by_default(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "executable", str(project / ".venv" / "Scripts" / "python.exe"))
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.relaunch_if_needed([])
    assert Path(popen.call_args.args[0][0]).name == "pythonw.exe"


def test_local_pythonw_is_not_relaunched(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    target = project / ".venv" / "Scripts" / "pythonw.exe"
    monkeypatch.setattr(sys, "executable", str(target))
    monkeypatch.setenv(control.RELAUNCH_GUARD, str(target))
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert not control.relaunch_if_needed([])
    popen.assert_not_called()


def test_pythonw_without_standard_streams_is_relaunched_once_with_valid_handles(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    target = project / ".venv" / "Scripts" / "pythonw.exe"
    monkeypatch.setattr(sys, "executable", str(target))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.relaunch_if_needed([])
    assert popen.call_args.kwargs["stdout"] == subprocess.DEVNULL
    assert popen.call_args.kwargs["stderr"] == subprocess.DEVNULL
    monkeypatch.setenv(control.RELAUNCH_GUARD, str(target))
    assert not control.relaunch_if_needed([])
    assert popen.call_count == 1


def test_relaunch_guard_stops_a_broken_interpreter_redirector(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    monkeypatch.setenv(control.RELAUNCH_GUARD, str(project / ".venv" / "Scripts" / "pythonw.exe"))
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    with pytest.raises(RuntimeError, match="entorno local"):
        control.relaunch_if_needed([])
    popen.assert_not_called()


def test_missing_environment_is_an_error_not_a_global_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "PROJECT_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="PREPARAR_DESARROLLO"):
        control.relaunch_if_needed([])


@pytest.mark.parametrize("arguments", [["--smoke"], ["--smoke", "--smoke-seconds", "0.1"],
                                        ["--detector-smoke"], ["--help"], ["-h"]])
def test_smoke_and_help_keep_the_current_process_and_exit_status(tmp_path, monkeypatch, arguments):
    prepared_project(tmp_path, monkeypatch)
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert not control.relaunch_if_needed(arguments)
    popen.assert_not_called()


def test_explicit_developer_console_still_uses_local_dependencies(tmp_path, monkeypatch):
    project = prepared_project(tmp_path, monkeypatch)
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(control.subprocess, "run", run)
    assert control.relaunch_if_needed(["--console"])
    assert run.call_args.args[0] == [str(project / ".venv" / "Scripts" / "python.exe"),
                                    str(project / "control.py"), "--console"]
    assert "creationflags" not in run.call_args.kwargs


def frozen_without_streams(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(Path.cwd() / "build test" / "BioGesture.exe"))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.delenv(control.FROZEN_STDIO_GUARD, raising=False)
    return Path(sys.executable).resolve()


def test_frozen_windowed_relaunches_itself_once_not_python(monkeypatch):
    target = frozen_without_streams(monkeypatch)
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.relaunch_frozen_if_needed(["--clean-ui"]) == 0
    assert popen.call_args.args[0] == [str(target), "--clean-ui"]
    options = popen.call_args.kwargs
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert options["env"][control.FROZEN_STDIO_GUARD] == str(target)
    assert options["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    monkeypatch.setenv(control.FROZEN_STDIO_GUARD, str(target))
    assert control.relaunch_frozen_if_needed(["--clean-ui"]) is None
    assert popen.call_count == 1


@pytest.mark.parametrize("arguments", [["--smoke"], ["--detector-smoke"], ["--console"]])
@pytest.mark.parametrize("status", [0, 1, 7])
def test_frozen_test_mode_waits_and_preserves_failure_status(monkeypatch, arguments, status):
    target = frozen_without_streams(monkeypatch)
    run = Mock(return_value=Mock(returncode=status))
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "run", run)
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.main(arguments) == status
    assert run.call_args.args[0] == [str(target), *arguments]
    assert run.call_args.kwargs["check"] is False
    popen.assert_not_called()


def test_frozen_with_valid_streams_does_not_relaunch(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv(control.FROZEN_STDIO_GUARD, raising=False)
    popen = Mock()
    monkeypatch.setattr(control.subprocess, "Popen", popen)
    assert control.relaunch_frozen_if_needed([]) is None
    popen.assert_not_called()


def test_failed_frozen_detector_relaunch_never_opens_an_error_window(monkeypatch):
    frozen_without_streams(monkeypatch)
    run = Mock(side_effect=OSError("controlled failure"))
    popup = Mock()
    monkeypatch.setattr(control.subprocess, "run", run)
    monkeypatch.setattr(control.ctypes.windll.user32, "MessageBoxW", popup)
    assert control.main(["--detector-smoke"]) == 1
    popup.assert_not_called()


@pytest.mark.skipif(os.name != "nt", reason="Redirección nativa de Windows")
@pytest.mark.parametrize("interpreter_name", ["python.exe", "pythonw.exe"])
def test_native_output_is_logged_without_console_in_isolated_process(tmp_path, interpreter_name):
    interpreter = Path(sys.executable).with_name(interpreter_name)
    destination = tmp_path / "native-unicode-á.log"
    # No app main, ML imports, window, input controller, hooks or webcam.
    probe = r'''
import ctypes, os, sys
from biogesture.startup import redirect_native_output
redirect_native_output(sys.argv[1])
print('PYTHON_STDOUT', flush=True)
print('PYTHON_STDERR', file=sys.stderr, flush=True)
os.write(1, b'FD1_OUTPUT\n')
os.write(2, b'FD2_OUTPUT\n')
crt = ctypes.CDLL('ucrtbase')
crt.__acrt_iob_func.argtypes = [ctypes.c_uint]
crt.__acrt_iob_func.restype = ctypes.c_void_p
crt.fputs.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
crt.fputs.restype = ctypes.c_int
crt.fflush.argtypes = [ctypes.c_void_p]
crt.fflush.restype = ctypes.c_int
crt.fputs(b'C_STDOUT\n', crt.__acrt_iob_func(1))
crt.fputs(b'C_STDERR\n', crt.__acrt_iob_func(2))
crt.fflush(None)
kernel = ctypes.WinDLL('kernel32')
kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
kernel.GetStdHandle.restype = ctypes.c_void_p
kernel.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
written = ctypes.c_uint32()
assert kernel.WriteFile(kernel.GetStdHandle(ctypes.c_uint32(-12).value), b'WIN32_OUTPUT\n', 13, ctypes.byref(written), None)
kernel.GetConsoleWindow.restype = ctypes.c_void_p
assert not kernel.GetConsoleWindow(), 'The child must not own a console'
'''
    result = subprocess.run([str(interpreter), "-c", probe, str(destination)],
                            cwd=Path(control.__file__).resolve().parent, timeout=20,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    assert result.returncode == 0
    content = destination.read_text(encoding="utf-8")
    for expected in ("PYTHON_STDOUT", "PYTHON_STDERR", "FD1_OUTPUT", "FD2_OUTPUT", "C_STDOUT", "C_STDERR", "WIN32_OUTPUT"):
        assert expected in content
