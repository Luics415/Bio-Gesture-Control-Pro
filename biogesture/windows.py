"""Windows input, monitor and audio adapters with explicit resource ownership."""

from collections import deque
import ctypes
from ctypes import wintypes
import logging
import math
import os
from pathlib import Path
import subprocess
import threading

from .models import ActionEvent


VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
      "tab": 0x09, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "grave": 0xC0,
      "caps_lock": 0x14, "delete": 0x2E, "left": 0x25, "right": 0x27,
      "up": 0x26, "down": 0x28, "home": 0x24, "end": 0x23,
      "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
      "media_next": 0xB0, "media_previous": 0xB1, "media_play_pause": 0xB3,
      **{f"f{i}": 0x6F + i for i in range(1, 13)},
      **{c.lower(): ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}}

GLOBAL_SHORTCUTS = {
    "MAYUS": ("caps_lock",), "DELETE": ("delete",), "INICIO": ("win",),
    "ESC": ("escape",), "BUSCAR": ("win", "s"), "PESTANYA": ("alt", "tab"),
    "COPIAR": ("ctrl", "c"), "PEGAR": ("ctrl", "v"), "DESHACER": ("ctrl", "z"),
    "REHACER": ("ctrl", "y"), "CORTAR": ("ctrl", "x"), "TODO": ("ctrl", "a"),
    "NUEVA T": ("ctrl", "t"), "CERRAR T": ("ctrl", "w"), "RECARGAR": ("f5",),
    "REGRESAR": ("alt", "left"), "AVANCE": ("alt", "right"),
    "FAVORITOS": ("ctrl", "d"), "DESCARGA": ("ctrl", "j"),
    "PLAY/PAUSE": ("media_play_pause",), "SIGUIENTE": ("media_next",),
    "ANTERIOR": ("media_previous",), "MUTE": ("volume_mute",),
    "VOL+": ("volume_up",), "VOL-": ("volume_down",),
    "GUARDAR": ("ctrl", "s"), "GUARDAR TODO": ("ctrl", "shift", "s"),
    "SIGUIENTE T": ("ctrl", "tab"), "ANTERIOR T": ("ctrl", "shift", "tab"),
}
PROFILE_SHORTCUTS = {
    "Global": {},
    "Navegador": {"BUSCAR": ("ctrl", "f"), "FULLSCREEN": ("f11",)},
    "VS Code": {"BUSCAR": ("ctrl", "f"), "REEMPLAZAR": ("ctrl", "h"),
                "PALETA": ("ctrl", "shift", "p"), "EJECUTAR": ("f5",),
                "TERMINAL": ("ctrl", "grave"), "FULLSCREEN": ("f11",)},
    # These are the legacy YouTube player shortcuts, opt-in and focus-dependent.
    "Multimedia": {"ATRAS 10s": ("j",), "ADELAN 10s": ("l",),
                   "FULLSCREEN": ("f",), "SUBTITULOS": ("c",)},
}

# Everyday auxiliary editing, independent of the principal hand's profile.
# Applications decide what their current selection and undo history mean.
AUXILIARY_SHORTCUTS = {
    "COPIAR": ("ctrl", "c"), "PEGAR": ("ctrl", "v"),
    "DESHACER": ("ctrl", "z"), "REHACER": ("ctrl", "y"),
}


def enable_dpi_awareness():
    """Call before constructing any Tk window; coordinate values are physical pixels."""
    if os.name != "nt":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        fn = user32.SetProcessDpiAwarenessContext
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = wintypes.BOOL
        if fn(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return True
        if ctypes.get_last_error() == 5:  # Awareness already fixed by manifest/runtime.
            return True
    except AttributeError:
        pass
    try:
        result = ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return result in (0, -2147024891)
    except (AttributeError, OSError):
        return bool(user32.SetProcessDPIAware())


def list_monitors():
    from .coordinates import RectMonitor
    if os.name != "nt":
        return [RectMonitor("primary", "Pantalla de prueba", 0, 0, 1920, 1080, True)]
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                      wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                          callback_type, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    monitors = []

    @callback_type
    def collect(handle, hdc, rect, param):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcMonitor
            monitors.append(RectMonitor(info.szDevice, info.szDevice, r.left, r.top,
                                        r.right - r.left, r.bottom - r.top, bool(info.dwFlags & 1)))
        return True

    if not user32.EnumDisplayMonitors(None, None, collect, 0) or not monitors:
        raise OSError("Windows no pudo enumerar las pantallas")
    return sorted(monitors, key=lambda m: (not m.primary, m.left, m.top))


class _NativeInput:
    """Minimal SendInput binding; no controllers or inputs are created at import."""

    class Mouse(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32),
                    ("mouseData", ctypes.c_uint32), ("dwFlags", ctypes.c_uint32),
                    ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]

    class Keyboard(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_uint16), ("wScan", ctypes.c_uint16),
                    ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32),
                    ("dwExtraInfo", ctypes.c_size_t)]

    def __init__(self):
        if os.name != "nt":
            raise OSError("El control del escritorio requiere Windows")

        class Payload(ctypes.Union):
            _fields_ = [("mi", self.Mouse), ("ki", self.Keyboard)]

        class Input(ctypes.Structure):
            _fields_ = [("type", ctypes.c_uint32), ("payload", Payload)]

        self.Input, self.Payload = Input, Payload
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SendInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(Input), ctypes.c_int]
        self.user32.SendInput.restype = ctypes.c_uint32
        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user32.SetCursorPos.restype = wintypes.BOOL
        self.user32.LockWorkStation.restype = wintypes.BOOL

    def _send(self, event):
        if self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event)) != 1:
            raise OSError("Windows rechazó la entrada (la ventana puede requerir permisos superiores)")

    def move(self, x, y):
        if not self.user32.SetCursorPos(x, y):
            raise ctypes.WinError(ctypes.get_last_error())

    def button(self, button, down):
        flags = {("left", True): 0x0002, ("left", False): 0x0004,
                 ("right", True): 0x0008, ("right", False): 0x0010}
        event = self.Input(0, self.Payload(mi=self.Mouse(0, 0, 0, flags[(button, down)], 0, 0)))
        self._send(event)

    def scroll(self, amount):
        event = self.Input(0, self.Payload(mi=self.Mouse(0, 0, ctypes.c_uint32(amount * 120).value,
                                                       0x0800, 0, 0)))
        self._send(event)

    def key(self, name, down):
        extended = name in ("left", "right", "up", "down", "home", "end", "delete", "win")
        flags = int(extended) | (0 if down else 0x0002)
        self._send(self.Input(1, self.Payload(ki=self.Keyboard(VK[name], 0, flags, 0, 0))))

    def lock(self):
        if not self.user32.LockWorkStation():
            raise ctypes.WinError(ctypes.get_last_error())

    def task_manager(self):
        buffer = ctypes.create_unicode_buffer(32768)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
        kernel32.GetSystemDirectoryW.restype = wintypes.UINT
        size = kernel32.GetSystemDirectoryW(buffer, len(buffer))
        if not size or size >= len(buffer):
            raise OSError("No se encontró la carpeta del sistema")
        subprocess.Popen([str(Path(buffer.value) / "Taskmgr.exe")], shell=False,
                         creationflags=subprocess.CREATE_NO_WINDOW)


class _AudioVolume:
    def __init__(self):
        self._endpoint = None
        self._com = None
        self._thread = None

    def _connect(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        if self._com is None:
            comtypes.CoInitialize()
            self._com, self._thread = comtypes, threading.get_ident()
        elif self._thread != threading.get_ident():
            raise RuntimeError("El audio debe usarse desde el hilo que lo inicializó")
        speakers = AudioUtilities.GetSpeakers()
        endpoint = getattr(speakers, "EndpointVolume", None)
        if endpoint is None:
            interface = speakers.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            endpoint = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        self._endpoint = endpoint

    def adjust(self, delta):
        for attempt in range(2):
            try:
                if self._endpoint is None:
                    self._connect()
                current = self._endpoint.GetMasterVolumeLevelScalar()
                self._endpoint.SetMasterVolumeLevelScalar(max(0.0, min(1.0, current + delta)), None)
                return
            except Exception:
                self._endpoint = None
                if attempt:
                    raise

    def close(self):
        self._endpoint = None
        if self._com is not None:
            if self._thread != threading.get_ident():
                raise RuntimeError("El audio debe cerrarse desde su hilo original")
            self._com.CoUninitialize()
            self._com = None


class WindowsActions:
    def __init__(self, dry_run=False, *, _native=None, _volume=None, shortcuts=None):
        self.dry_run = dry_run
        self._native = _native
        self._volume = _volume
        self.profile = "Global"
        self.last_error = None
        self._held_buttons = set()
        self._held_keys = set()
        self._closed = False
        self.history = deque(maxlen=256)
        self._shortcuts = {name: dict(mapping) for name, mapping in PROFILE_SHORTCUTS.items()}
        if shortcuts:
            for profile, mapping in shortcuts.items():
                if profile not in self._shortcuts or not isinstance(mapping, dict):
                    raise ValueError("Perfil de atajos inválido")
                for command, keys in mapping.items():
                    if (not isinstance(command, str) or not isinstance(keys, (tuple, list))
                            or not 1 <= len(keys) <= 4 or any(k not in VK for k in keys)):
                        raise ValueError("Solo se admiten combinaciones de 1 a 4 teclas conocidas")
                    self._shortcuts[profile][command] = tuple(keys)

    def set_profile(self, profile):
        if profile not in self._shortcuts:
            raise ValueError("Perfil desconocido")
        self.release_all()
        self.profile = profile

    def _input(self):
        if self._native is None:
            self._native = _NativeInput()
        return self._native

    def _button(self, button, down):
        if down:
            self._held_buttons.add(button)
        if not self.dry_run:
            self._input().button(button, down)
        if not down:
            self._held_buttons.discard(button)

    def _chord(self, keys):
        try:
            for key in keys:
                self._held_keys.add(key)
                if not self.dry_run:
                    self._input().key(key, True)
        finally:
            failures = []
            for key in reversed(keys):
                if key in self._held_keys:
                    try:
                        if not self.dry_run:
                            self._input().key(key, False)
                        self._held_keys.discard(key)
                    except Exception as exc:
                        failures.append(exc)
            if failures:
                raise failures[0]

    def move(self, x, y):
        try:
            if self._closed:
                return False
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Coordenadas inválidas")
            if not self.dry_run:
                self._input().move(round(x), round(y))
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logging.error("No se pudo mover el cursor: %s", exc)
            return False

    def handle(self, event: ActionEvent):
        self.last_error = None
        try:
            if self._closed:
                raise RuntimeError("Los controles están cerrados")
            self.history.append(event)
            kind = event.kind
            if kind == "press_left":
                if "left" not in self._held_buttons:
                    self._button("left", True)
            elif kind == "release_left":
                if "left" in self._held_buttons:
                    self._button("left", False)
            elif kind in ("click_left", "click_right"):
                button = "left" if kind == "click_left" else "right"
                try:
                    self._button(button, True)
                finally:
                    self._button(button, False)
            elif kind == "scroll":
                amount = max(-30, min(30, round(float(event.value))))
                if amount and not self.dry_run:
                    self._input().scroll(amount)
            elif kind == "volume_delta":
                delta = float(event.value)
                if not math.isfinite(delta):
                    raise ValueError("Cambio de volumen inválido")
                if not self.dry_run and delta:
                    if self._volume is None:
                        self._volume = _AudioVolume()
                    self._volume.adjust(max(-1.0, min(1.0, delta)))
            elif kind == "command":
                self._command(event.value)
            elif kind == "auxiliary_command":
                keys = AUXILIARY_SHORTCUTS.get(event.value)
                if keys is None:
                    raise ValueError("Comando auxiliar no permitido")
                self._chord(keys)
            elif kind in ("release_all", "pause_changed"):
                return self.release_all()
            else:
                raise ValueError(f"Evento no admitido por Windows: {kind}")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logging.error("Acción %s: %s", event.kind, exc)
            self.release_all()
            return False

    def _command(self, command):
        if command in ("CONFIG", "VOLVER", "SISTEMA", "EDICION", "WEB", "MEDIA"):
            raise ValueError(f"{command} debe ser atendido por la interfaz")
        if command == "ADMIN":
            if not self.dry_run:
                self._input().task_manager()
        elif command == "BLOQUEAR":
            self.release_all()
            if not self.dry_run:
                self._input().lock()
        else:
            keys = self._shortcuts[self.profile].get(command, GLOBAL_SHORTCUTS.get(command))
            if keys is None:
                if command in ("ATRAS 10s", "ADELAN 10s", "SUBTITULOS", "FULLSCREEN"):
                    raise ValueError(f"{command} requiere el perfil Multimedia y un reproductor compatible")
                raise ValueError(f"Comando desconocido: {command}")
            self._chord(keys)

    def release_all(self):
        """Release only inputs issued by this application, including failed key-ups."""
        failures = []
        for button in tuple(self._held_buttons):
            try:
                self._button(button, False)
            except Exception as exc:
                failures.append(exc)
        for key in tuple(self._held_keys):
            try:
                if not self.dry_run:
                    self._input().key(key, False)
                self._held_keys.discard(key)
            except Exception as exc:
                failures.append(exc)
        if failures:
            self.last_error = str(failures[0])
            logging.error("No se pudieron liberar todas las entradas: %s", failures[0])
        return not failures

    def close(self):
        released = self.release_all()
        try:
            if self._volume is not None:
                self._volume.close()
        except Exception as exc:
            self.last_error = str(exc)
            logging.error("No se pudo cerrar el audio: %s", exc)
        self._closed = True
        return released
