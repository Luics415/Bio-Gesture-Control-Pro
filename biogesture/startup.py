"""Lightweight startup: show the approved author splash before loading ML."""

import argparse
import ctypes
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from .paths import resource_path
from .settings import Settings, data_directory

MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
_native_log_path = None


def redirect_native_output(path):
    """Capture Python, native file descriptors and Win32 stdout/stderr.

    Run once, before loading MediaPipe or starting workers. Pythonw may start
    with sys.stdout/sys.stderr=None; control.py supplies valid inherited handles
    when it relaunches that case, keeping C stdio usable from process birth.
    Tests exercise this only in child processes, never in the pytest process.
    """
    global _native_log_path
    if _native_log_path is not None:
        return _native_log_path
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            try:
                stream.flush()
            except (OSError, ValueError):
                pass
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.dup2(descriptor, 1)
        os.dup2(descriptor, 2)
    finally:
        if descriptor not in (1, 2):
            os.close(descriptor)
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
        kernel.SetStdHandle.restype = wintypes.BOOL
        for constant, descriptor in ((-11, 1), (-12, 2)):
            if not kernel.SetStdHandle(wintypes.DWORD(constant).value, msvcrt.get_osfhandle(descriptor)):
                raise ctypes.WinError(ctypes.get_last_error())
    sys.stdout = os.fdopen(os.dup(1), "w", encoding="utf-8", errors="backslashreplace", buffering=1)
    sys.stderr = os.fdopen(os.dup(2), "w", encoding="utf-8", errors="backslashreplace", buffering=1)
    _native_log_path = path
    return path


def setup_logging():
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "biogesture.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
                        handlers=[handler], force=True)


def verify_model():
    path = resource_path("assets/models/hand_landmarker.task")
    if not path.is_file():
        raise FileNotFoundError("Falta el modelo local de seguimiento.")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != MODEL_SHA256:
        raise ValueError("El modelo de seguimiento está incompleto o fue modificado.")
    return path


def startup_ready(packet):
    """A loading status alone does not mean the camera/detector is ready."""
    return packet is not None and (packet.rgb is not None or bool(packet.error))


class SingleInstance:
    """Session-scoped mutex; never terminate another process."""

    def __init__(self):
        self.handle = None
        self.already_running = False
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            self.kernel.CreateMutexW.restype = ctypes.c_void_p
            self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            self.handle = self.kernel.CreateMutexW(None, False, "Local\\Luics415.BioGestureControlPro")
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self.already_running = ctypes.get_last_error() == 183

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class Splash:
    """Approved artwork, resized as a whole; status lives outside the artwork."""

    def __init__(self, root):
        from PIL import Image, ImageTk

        self.window = tk.Toplevel(root, bg="#050e27")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        width, height = 660, 464
        x = (self.window.winfo_screenwidth() - width) // 2
        y = (self.window.winfo_screenheight() - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        with Image.open(resource_path("assets/brand/splash-author.png")) as art:
            self.image = ImageTk.PhotoImage(art.resize((660, 440), Image.Resampling.LANCZOS))
        tk.Label(self.window, image=self.image, bd=0, bg="#050e27").pack()
        self.status = tk.StringVar(value="Cargando configuración…")
        tk.Label(self.window, textvariable=self.status, bg="#050e27", fg="#2ee8ce",
                 font=("Segoe UI", 9)).pack(fill="x")
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.window.destroy()


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description="Bio-Gesture Control Pro")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="Prueba de interfaz sin cámara ni entradas reales")
    mode.add_argument("--detector-smoke", action="store_true", help="Prueba del modelo con una imagen sintética, sin cámara")
    parser.add_argument("--smoke-seconds", type=float, default=3.0)
    parser.add_argument("--console", action="store_true", help="Conservar salida de consola para diagnóstico de desarrollo")
    visuals = parser.add_mutually_exclusive_group()
    visuals.add_argument("--diagnostics", dest="diagnostic_visuals", action="store_true",
                         help="Mostrar el estado de diagnóstico fuera del área de cámara")
    visuals.add_argument("--clean-ui", dest="diagnostic_visuals", action="store_false",
                         help="Ocultar el estado externo; puntos según Ajustes y menú radial conservado")
    parser.set_defaults(diagnostic_visuals=False)
    return parser.parse_args(argv)


def configure_smoke_data_directory():
    """Never write a frozen smoke run into its installed/extracted resources."""
    if not os.environ.get("BIOGESTURE_DATA_DIR"):
        directory = data_directory() / "smoke" if getattr(sys, "frozen", False) else resource_path("output/smoke-data")
        os.environ["BIOGESTURE_DATA_DIR"] = str(directory)
    return data_directory()


def recovery_instructions():
    action = ("Extrae el paquete completo en una carpeta local y vuelve a abrir Bio-Gesture."
              if getattr(sys, "frozen", False)
              else "Ejecuta PREPARAR_DESARROLLO.bat y vuelve a iniciar.")
    return f"{action}\n\nCarpeta de diagnóstico:\n{data_directory()}"


def main(argv=None):
    args = parse_arguments(argv)
    if args.smoke:
        configure_smoke_data_directory()
    setup_logging()
    if not args.console and not args.smoke:
        redirect_native_output(data_directory() / "native.log")
    if args.detector_smoke:
        from .detector_smoke import run_detector_smoke
        return run_detector_smoke(resource_path("assets/models/hand_landmarker.task"), MODEL_SHA256,
                                  data_directory() / "detector-smoke.json", console=args.console)
    logging.info("Inicio de aplicación; prueba sin dispositivos=%s", args.smoke)
    logging.info("Intérprete=%s; entorno=%s; consola de desarrollo=%s", sys.executable, sys.prefix, args.console)
    from .windows import enable_dpi_awareness
    enable_dpi_awareness()
    instance = None if args.smoke else SingleInstance()
    if instance and instance.already_running:
        alert = tk.Tk()
        alert.withdraw()
        messagebox.showinfo("Bio-Gesture Control Pro", "Bio-Gesture ya está abierto. Usa el ancla de la bandeja.", parent=alert)
        alert.destroy()
        instance.close()
        return 0
    root = tk.Tk()
    root.withdraw()
    splash = Splash(root)
    startup_bus, bus = Queue(), Queue()
    holder = {}
    exit_code = [0]

    def initialize():
        try:
            startup_bus.put(("status", "Comprobando modelo y configuración…"))
            path = verify_model()
            settings = Settings.load()
            from .gestures import GestureEngine
            from .tracking import TrackingPipeline
            from .windows import WindowsActions, list_monitors
            startup_bus.put(("ready", (settings, GestureEngine(settings), TrackingPipeline,
                                        WindowsActions, list_monitors(), path)))
        except Exception as exc:
            logging.exception("Fallo de arranque")
            startup_bus.put(("failed", str(exc)))

    def startup_tick():
        try:
            name, value = startup_bus.get_nowait()
        except Empty:
            root.after(20, startup_tick)
            return
        if name == "status":
            splash.status.set(value)
        elif name == "failed":
            exit_code[0] = 1
            splash.close()
            messagebox.showerror("No se pudo iniciar", f"{value}\n\n{recovery_instructions()}", parent=root)
            root.destroy()
            return
        elif name == "ready":
            try:
                from .desktop import DesktopApp
                settings, engine, pipeline_type, actions_type, monitors, model_path = value
                # COM/audio actions are owned by the UI thread, not the ML callback.
                actions = actions_type(dry_run=args.smoke)
                holder["actions"] = actions
                pipeline = None if args.smoke else pipeline_type(settings, model_path,
                    status_callback=lambda text: bus.put(("status", text)))
                holder["pipeline"] = pipeline
                if pipeline:
                    pipeline.start()
                app = DesktopApp(root, settings, bus, engine, actions, pipeline, monitors,
                                 smoke=args.smoke, diagnostic_visuals=args.diagnostic_visuals)
                holder["app"] = app
                began = time.monotonic()

                def finish_startup():
                    if app.closing:
                        splash.close()
                        return
                    packet = pipeline.latest() if pipeline else None
                    if args.smoke or startup_ready(packet) or time.monotonic()-began > 8:
                        splash.close()
                        root.deiconify()
                        if args.smoke:
                            root.after(max(100, int(args.smoke_seconds*1000)), app.request_close)
                    else:
                        splash.status.set(packet.status if packet else "Conectando cámara y preparando detección…")
                        root.after(40, finish_startup)
                finish_startup()
                return
            except Exception as exc:
                logging.exception("Fallo al construir la interfaz")
                startup_bus.put(("failed", str(exc)))
        root.after(20, startup_tick)

    threading.Thread(target=initialize, name="BioGestureStartup", daemon=True).start()
    root.after(10, startup_tick)
    try:
        root.mainloop()
    finally:
        if holder.get("actions"):
            holder["actions"].close()
        app = holder.get("app")
        pipeline = app.pipeline if app else holder.get("pipeline")
        if pipeline:
            pipeline.stop(timeout=2)
        if instance:
            instance.close()
        logging.info("Aplicación cerrada")
    return exit_code[0]


def run(argv=None):
    """Show bootstrap failures even when launched through pythonw without a console."""
    try:
        return main(argv)
    except Exception as exc:
        logging.exception("Fallo antes de completar el arranque")
        if "--detector-smoke" in (sys.argv[1:] if argv is None else argv):
            return 1
        text = (f"No se pudo iniciar Bio-Gesture Control Pro.\n\n{exc}\n\n"
                f"{recovery_instructions()}")
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, text, "Bio-Gesture Control Pro", 0x10)
        else:
            print(text)
        return 1
