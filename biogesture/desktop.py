"""Tk desktop shell. Worker and tray callbacks communicate only through a queue."""

from collections import deque
import ctypes
from ctypes import wintypes
from dataclasses import replace
import logging
import math
import os
from queue import Empty
import statistics
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import __version__
from .auxiliary import AuxiliaryGestureEngine
from .coordinates import RectMonitor, ScreenMapper, fit_video
from .models import ActionEvent, EngineOutput
from .paths import resource_path
from .rendering import (ACCENT, BACKGROUND, CAMERA_HEIGHT, FOOTER_HEIGHT, MUTED, TEXT,
                        TOOLBAR_HEIGHT, draw_empty_state, draw_radial_menu,
                        status_text)
from .settings import data_directory
from .tracking import TrackingPipeline
from .ui import MenuAction, compact_button
from .windows import list_monitors


CYAN = ACCENT
GREEN = "#a4d5bd"
CONNECTIONS = ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
               (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
               (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20))


def choose_monitor(monitors, monitor_id):
    """Resolve persisted selection, including the full physical-pixel desktop."""
    if not monitors:
        raise ValueError("No hay pantallas disponibles")
    if monitor_id == "virtual":
        left = min(m.left for m in monitors)
        top = min(m.top for m in monitors)
        right = max(m.left + m.width for m in monitors)
        bottom = max(m.top + m.height for m in monitors)
        return RectMonitor("virtual", "Escritorio completo", left, top, right - left, bottom - top)
    return next((m for m in monitors if m.id == monitor_id),
                next((m for m in monitors if m.primary), monitors[0]))


def calibration_corner(samples, now, since, settings):
    """Median of a short, recent sample window; rejects absent or unstable hands."""
    usable = [s for s in samples if max(since, now - 1.2) <= s.timestamp <= now
              and len(s.landmarks) == 21
              and s.confidence >= settings.tracking_confidence]
    if len(usable) < 4 or usable[-1].timestamp - usable[0].timestamp < 0.6 or now - usable[-1].timestamp > 0.35:
        raise ValueError("Mantén la mano elegida visible y el índice quieto durante un segundo.")
    xs = [s.landmarks[8].x for s in usable]
    ys = [s.landmarks[8].y for s in usable]
    if not all(math.isfinite(v) for v in xs + ys):
        raise ValueError("Las coordenadas recibidas no son válidas.")
    if max(xs) - min(xs) > 0.1 or max(ys) - min(ys) > 0.1:
        raise ValueError("La mano se movió demasiado. Mantén el índice quieto e inténtalo otra vez.")
    return statistics.median(xs), statistics.median(ys)


class DesktopApp:
    def __init__(self, root, settings, bus, engine, actions, pipeline, monitors, *, smoke=False, diagnostic_visuals=False):
        self.root, self.settings, self.bus = root, settings, bus
        self.engine, self.actions, self.pipeline = engine, actions, pipeline
        self.auxiliary_engine = AuxiliaryGestureEngine(settings)
        self.monitors, self.smoke = list(monitors), smoke
        self.diagnostic_visuals = diagnostic_visuals  # External status only; never camera overlays.
        self.mapper = ScreenMapper(settings, choose_monitor(self.monitors, settings.monitor_id))
        self.actions.set_profile(settings.profile)
        self.output = EngineOutput(state="PAUSADO" if engine.paused else "LISTO")
        self._sequence = -1
        self._last_capture = time.monotonic()
        self._last_monitors = time.monotonic()
        self._last_resource_check = 0.0
        self._cpu_percent = self._memory_mb = 0.0
        self._process = None
        try:
            import psutil
            self._process = psutil.Process()
            self._process.cpu_percent()
        except Exception:
            logging.debug("Métricas de recursos no disponibles", exc_info=True)
        self._packet = None
        self._samples = deque(maxlen=120)
        self._photo = self._anchor_photo = None
        self._tray = self._hook = None
        self._tray_ready = False
        self._closing = False
        self._destroyed = False
        self._operation = False
        self._camera_enabled = True
        self._settings_dialog = self._calibration_dialog = None
        self._diagnostics_visible = False
        self._notice, self._notice_until = "", 0.0
        self._after = None
        self._build()
        self._apply_window_mode()
        if not smoke:
            self._start_integrations()
        self._after = self.root.after(16, self.tick)

    @property
    def closing(self):
        return self._closing

    def _build(self):
        root = self.root
        root.title(f"Bio-Gesture Control Pro · Luics415 · {__version__}")
        root.geometry("550x375")
        root.resizable(False, False)
        root.configure(background=BACKGROUND)
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        root.bind("<Control-Alt-F12>", lambda event: self.pause(True))
        toolbar = tk.Frame(root, bg=BACKGROUND, width=550, height=TOOLBAR_HEIGHT)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        self._drag_origin = None

        def begin_drag(event):
            if self.settings.fixed_window:
                self._drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

        def drag(event):
            if self.settings.fixed_window and self._drag_origin:
                x, y, window_x, window_y = self._drag_origin
                self._position_window(window_x + event.x_root - x, window_y + event.y_root - y)

        toolbar.bind("<ButtonPress-1>", begin_drag)
        toolbar.bind("<B1-Motion>", drag)
        toolbar.bind("<ButtonRelease-1>", lambda event: setattr(self, "_drag_origin", None))
        try:
            with Image.open(resource_path("assets/brand/anchor-approved.png")) as original:
                icon = original.convert("RGBA")
                self._anchor_photo = ImageTk.PhotoImage(icon.resize((20, 20), Image.Resampling.LANCZOS), master=root)
            root.iconphoto(True, self._anchor_photo)
            tk.Label(toolbar, image=self._anchor_photo, bg=BACKGROUND, bd=0).pack(side="left", padx=(8, 5))
        except (OSError, tk.TclError):
            logging.exception("No se pudo cargar el icono de ancla")
            tk.Label(toolbar, text="⚓", fg=CYAN, bg=BACKGROUND, font=("Segoe UI", -18)).pack(side="left", padx=5)
        brand = tk.Label(toolbar, text="Bio-Gesture", fg="#ccd6dc", bg=BACKGROUND, font=("Segoe UI", -11), bd=0)
        brand.pack(side="left")
        for widget in (brand,):
            widget.bind("<ButtonPress-1>", begin_drag)
            widget.bind("<B1-Motion>", drag)
            widget.bind("<ButtonRelease-1>", lambda event: setattr(self, "_drag_origin", None))
        self.more_menu = tk.Menu(root, tearoff=False, bg=BACKGROUND, fg=TEXT, activebackground="#28343d",
                                 activeforeground=TEXT, borderwidth=1, font=("Segoe UI", -12),
                                 postcommand=self._update_more_menu)
        self.more_menu.add_command(label="Fijar ventana transparente", command=self.toggle_window)
        self.more_menu.add_command(label="Apagar cámara", command=self.toggle_camera)
        self.more_menu.add_command(label="Ocultar en la bandeja", command=self.hide)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="Salir", command=self.request_close)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="Reelegir mano principal", command=self.reselect_principal)
        self.more_menu.add_command(label="Desactivar mano auxiliar", command=self.toggle_auxiliary)
        self.fixed_button = MenuAction(self.more_menu, 0, {"Normal": "Volver a ventana normal", "Fija": "Fijar ventana transparente"})
        self.camera_button = MenuAction(self.more_menu, 1)
        self.more_button = compact_button(toolbar, "Más  ⋯", self._show_more)
        self.more_button.pack(side="right", padx=(1, 6), pady=2)
        self.settings_button = compact_button(toolbar, "Ajustes", self.open_settings)
        self.settings_button.pack(side="right", padx=1, pady=2)
        self.pause_button = compact_button(toolbar, "Activar" if self.engine.paused else "Pausar", self.toggle_pause, accent=True)
        self.pause_button.pack(side="right", padx=1, pady=2)
        root.bind("<Alt-m>", lambda event: self._show_more())
        self.canvas = tk.Canvas(root, width=550, height=CAMERA_HEIGHT, bg="#080d12", highlightthickness=0)
        self.canvas.pack()
        self._draw_empty_state()
        self.status = tk.StringVar(value="En pausa  ·  Configura y calibra antes de activar")
        self.metrics = tk.StringVar(value="Las mediciones aparecerán cuando la cámara esté disponible.")
        footer = tk.Frame(root, height=FOOTER_HEIGHT, background=BACKGROUND)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        if self.diagnostic_visuals:
            tk.Label(footer, textvariable=self.status, bg=BACKGROUND, fg=MUTED, bd=0,
                     anchor="w", font=("Segoe UI", -9), padx=8).pack(fill="both", expand=True)

    def _draw_empty_state(self):
        draw_empty_state(self.canvas)

    def _update_more_menu(self):
        self.fixed_button.configure(text="Normal" if self.settings.fixed_window else "Fija")
        self.camera_button.configure(text="Apagar cámara" if self._camera_enabled else "Encender cámara")
        self.more_menu.entryconfigure(7, label="Desactivar mano auxiliar" if self.settings.auxiliary_enabled else "Activar mano auxiliar")

    def reselect_principal(self):
        self.pause(True)
        self.auxiliary_engine.clear()
        if self.pipeline:
            self.pipeline.reset_roles()
        self._packet = None
        self._samples.clear()
        self.notify("Deja visible la mano que usarás como principal; después puedes mostrar las dos.")

    def toggle_auxiliary(self):
        self.settings.auxiliary_enabled = not self.settings.auxiliary_enabled
        self.auxiliary_engine.reset()
        self._update_more_menu()
        if not self.smoke:
            try:
                self.settings.save()
            except OSError as exc:
                self.notify(f"No se pudo guardar el ajuste auxiliar: {exc}")

    def _show_more(self):
        self._update_more_menu()
        try:
            self.more_menu.tk_popup(self.more_button.winfo_rootx(), self.more_button.winfo_rooty() + self.more_button.winfo_height())
        finally:
            self.more_menu.grab_release()

    def _start_integrations(self):
        try:
            import pystray

            def enqueue(kind):
                return lambda icon, item: self.bus.put((kind, None))

            menu = pystray.Menu(
                pystray.MenuItem("Mostrar cámara", enqueue("show"), default=True),
                pystray.MenuItem("Pausar control", enqueue("pause")),
                pystray.MenuItem("Ventana normal / fija", enqueue("toggle_window")),
                pystray.MenuItem("Encender / apagar cámara", enqueue("camera_toggle")),
                pystray.MenuItem("Configuración", enqueue("settings")),
                pystray.MenuItem("Salir", enqueue("close")),
            )
            with Image.open(resource_path("assets/brand/anchor-approved.png")) as source:
                tray_image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
            self._tray = pystray.Icon("BioGestureControlPro", tray_image, "Bio-Gesture · Pausado", menu)

            def run_tray():
                try:
                    def ready(icon):
                        icon.visible = True
                        self.bus.put(("tray_ready", None))
                    self._tray.run(setup=ready)
                except Exception as exc:
                    logging.exception("La bandeja no está disponible")
                    self.bus.put(("tray_error", str(exc)))
            threading.Thread(target=run_tray, name="BioGesture-tray", daemon=True).start()
        except Exception as exc:
            logging.exception("No se pudo preparar la bandeja")
            self.notify(f"Bandeja no disponible: {exc}")
        try:
            from pynput.keyboard import GlobalHotKeys
            self._hook = GlobalHotKeys({"<ctrl>+<alt>+<f12>": lambda: self.bus.put(("pause", None))})
            self._hook.start()
        except Exception:
            logging.exception("No se pudo registrar la pausa global")
            self.notify("Usa Pausar o la bandeja; el atajo global no está disponible.")

    def notify(self, message, seconds=6):
        self._notice, self._notice_until = str(message), time.monotonic() + seconds
        self.status.set(str(message))
        logging.info("Estado: %s", message)

    def _dispatch(self, kind, payload=None):
        if kind == "close_done":
            if not payload:
                logging.warning("Cierre: el controlador nativo no respondió dentro del plazo")
            self._destroy()
            return
        if self._closing:
            return
        if kind == "pause":
            self.pause(True)
            self.show()
        elif kind == "show":
            self.show()
        elif kind == "hide":
            self.hide()
        elif kind == "close":
            self.request_close()
        elif kind == "toggle_window":
            self.toggle_window()
        elif kind == "camera_toggle":
            self.toggle_camera()
        elif kind == "settings":
            self.open_settings()
        elif kind == "tray_ready":
            self._tray_ready = True
        elif kind == "tray_error":
            self._tray_ready = False
            self.show()
            self.notify("Bandeja no disponible; la ventana permanecerá accesible.")
        elif kind == "camera_stopped":
            self._operation = False
            stopped, restart = payload
            if not stopped:
                self._camera_enabled = False
                self.notify("La cámara sigue cerrándose. Reintenta desde Más → Encender cámara.", 15)
                return
            self._camera_enabled = False
            if restart:
                self.pipeline = TrackingPipeline(self.settings, resource_path("assets/models/hand_landmarker.task"))
                self._sequence, self._last_capture = -1, time.monotonic()
                self._samples.clear()
                if not self.smoke:
                    self.pipeline.start()
                self._camera_enabled = True
                self.notify("Conectando cámara; el control permanece pausado.")
            else:
                self._draw_empty_state()
                self.notify("Cámara apagada. Enciéndela desde Más.", 15)
        elif kind in ("status", "error"):
            self.notify(payload)

    def tick(self):
        try:
            for _ in range(100):
                try:
                    event = self.bus.get_nowait()
                except Empty:
                    break
                kind, payload = (event, None) if isinstance(event, str) else event
                self._dispatch(kind, payload)
                if self._destroyed:
                    return
            if not self._closing:
                now = time.monotonic()
                packet = self.pipeline.latest() if self.pipeline and self._camera_enabled and not self._operation else None
                if packet is not None and packet.sequence != self._sequence:
                    self._sequence, self._packet = packet.sequence, packet
                    self._last_capture = packet.captured_at
                    if packet.error:
                        self.pause(True)
                        self.notify(packet.error, 15)
                    sample = packet.sample if now - packet.captured_at <= 0.35 else None
                    if sample is not None:
                        self._samples.append(sample)
                    else:
                        self._samples.clear()
                    self.output = self.engine.update(sample, now)
                    self._apply_output(self.output, now)
                    auxiliary = packet.auxiliary if now - packet.captured_at <= 0.35 else None
                    self._apply_auxiliary(auxiliary, now)
                    if packet.rgb is not None and self.root.winfo_viewable():
                        self._render(packet, self.output)
                    elif packet.error:
                        self._draw_empty_state()
                elif now - self._last_capture > 0.35:
                    self.output = self.engine.update(None, now)
                    self._apply_output(self.output, now)
                    self.auxiliary_engine.reset()
                    self.mapper.reset()
                if not self.smoke and now - self._last_monitors >= 3.0:
                    self._last_monitors = now
                    self._refresh_monitors()
                self.pause_button.configure(text="Activar" if self.engine.paused else "Pausar")
                if now >= self._notice_until:
                    state = self.output.state if self._camera_enabled else "CÁMARA APAGADA"
                    if self._camera_enabled and self._packet and self._packet.sample is None:
                        state = self._packet.status
                    self.status.set(status_text(state, self.settings.profile, paused=self.engine.paused,
                                                fixed=self.settings.fixed_window))
                if self._packet and getattr(self, "_diagnostics_visible", False):
                    m = self._packet.metrics
                    age = max(0.0, now - self._packet.captured_at) * 1000
                    if self._process and now - self._last_resource_check >= 1.0:
                        self._last_resource_check = now
                        try:
                            self._cpu_percent = self._process.cpu_percent()
                            self._memory_mb = self._process.memory_info().rss / (1024 * 1024)
                        except Exception:
                            logging.debug("No se pudieron leer recursos", exc_info=True)
                    self.metrics.set(f"Cámara: {m.get('capture_fps', 0):.0f} FPS\nDetección: {m.get('inference_ms', 0):.0f} ms\n"
                                     f"CPU: {self._cpu_percent:.0f}% · Memoria: {self._memory_mb:.0f} MiB\nAntigüedad del cuadro: {age:.0f} ms")
        except tk.TclError:
            if not self._closing:
                logging.exception("Error de interfaz")
                self.engine.set_paused(True)
                self.actions.release_all()
                self.mapper.reset()
        except Exception as exc:
            logging.exception("Error en actualización del escritorio")
            self.pause(True)
            self.notify(f"Control pausado: {exc}")
        if not self._destroyed:
            self._after = self.root.after(16, self.tick)

    def _apply_output(self, output, now):
        if self._operation or self._settings_dialog or self._calibration_dialog:
            if not self.engine.paused:
                self.pause(True)
            self.actions.release_all()
            return
        interrupts = any(event.kind == "pause_changed" or
                         (event.kind == "command" and event.value == "CONFIG") for event in output.events)
        # Mouse input belongs at this frame's index-tip position, not the
        # previous frame. A down/up pair is a normal click; held down is drag.
        if output.pointer is not None and not self.engine.paused and not interrupts:
            if not self.actions.move(*self.mapper.map(*output.pointer, now)):
                self.pause(True)
                self.notify(self.actions.last_error or "No se pudo mover el cursor.")
                return
        for event in output.events:
            if event.kind == "toggle_window":
                self.toggle_window()
            elif event.kind == "pause_changed":
                self.actions.release_all()
                self.mapper.reset()
                self._update_tray_state()
                return
            elif event.kind == "command" and event.value == "CONFIG":
                self.open_settings()
                return
            elif not self.actions.handle(event):
                self.pause(True)
                self.notify(self.actions.last_error or "Windows rechazó la acción.")
                return

    def _apply_auxiliary(self, sample, now):
        enabled = (self.settings.auxiliary_enabled and not self.engine.paused
                   and not self._operation and self._camera_enabled
                   and not self._settings_dialog and not self._calibration_dialog
                   and self.output.state in ("PUNTERO", "SIN MANO", "LISTO")
                   and not self.output.events)
        events = self.auxiliary_engine.update(sample, now, enabled=enabled)
        if not enabled:
            return
        for event in events:
            if event.kind == "command":
                routed = ActionEvent("auxiliary_command", event.value)
            elif event.kind == "scroll":
                routed = event
            else:
                self.pause(True)
                self.notify("Evento auxiliar no permitido; control pausado.")
                return
            if not self.actions.handle(routed):
                self.pause(True)
                self.notify(self.actions.last_error or "Windows rechazó la acción auxiliar.")
                return

    def _render(self, packet, output):
        image = Image.fromarray(packet.rgb)
        left, top, width, height = fit_video(image.width, image.height, 550, CAMERA_HEIGHT)
        self._photo = ImageTk.PhotoImage(image.resize((width, height), Image.Resampling.BILINEAR), master=self.root)
        self.canvas.delete("all")
        self.canvas.create_image(left, top, anchor="nw", image=self._photo)
        for sample, color in ((packet.sample, GREEN), (packet.auxiliary, "#c3a6e3")):
            if not sample or not self.settings.show_landmarks:
                continue
            points = [(left + p.x * width, top + p.y * height) for p in sample.landmarks]
            if len(points) == 21:
                for a, b in CONNECTIONS:
                    self.canvas.create_line(*points[a], *points[b], fill=color, width=2)
                for x, y in points:
                    self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=CYAN, outline="")
        if output.state == "MENU":
            self._draw_menu(output)

    def _draw_menu(self, output):
        draw_radial_menu(self.canvas, output)

    def pause(self, paused=True):
        output = self.engine.set_paused(paused)
        self.output = output
        self.actions.release_all()
        self.auxiliary_engine.reset()
        self.mapper.reset()
        self._update_tray_state()

    def _update_tray_state(self):
        if self._tray:
            try:
                self._tray.title = "Bio-Gesture · Pausado" if self.engine.paused else "Bio-Gesture · Activo"
            except Exception:
                logging.debug("No se pudo actualizar el estado de bandeja", exc_info=True)

    def toggle_pause(self):
        if self.engine.paused and (self._operation or not self._camera_enabled or self._settings_dialog or self._calibration_dialog):
            self.notify("Cierra la configuración y enciende la cámara antes de activar.")
            return
        self.pause(not self.engine.paused)

    def _apply_window_mode(self):
        self.root.overrideredirect(self.settings.fixed_window)
        self.root.attributes("-topmost", self.settings.fixed_window)
        self.root.attributes("-alpha", self.settings.opacity if self.settings.fixed_window else 1.0)
        self.fixed_button.configure(text="Normal" if self.settings.fixed_window else "Fija")

    def _position_window(self, x, y):
        # Negative Tk geometry offsets refer to the far screen edge, while
        # Windows coordinates here are absolute and may name a left monitor.
        if os.name == "nt":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SetWindowPos.restype = wintypes.BOOL
            handle = user32.GetAncestor(self.root.winfo_id(), 2)
            if not user32.SetWindowPos(handle, None, round(x), round(y), 0, 0, 0x0015):
                logging.error("No se pudo mover la ventana: %s", ctypes.get_last_error())
        else:
            self.root.geometry(f"550x375+{max(0, round(x))}+{max(0, round(y))}")

    def toggle_window(self):
        self.settings.fixed_window = not self.settings.fixed_window
        self._apply_window_mode()
        self.notify("Ventana fija transparente" if self.settings.fixed_window else "Ventana normal")
        if not self.smoke:
            try:
                self.settings.save()
            except OSError as exc:
                self.notify(f"No se pudo guardar el modo de ventana: {exc}")

    def hide(self):
        if self.smoke or self._tray_ready:
            self.root.withdraw()
        else:
            self.notify("La bandeja todavía no está disponible; minimiza la ventana para recuperarla.")

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def _refresh_monitors(self):
        try:
            monitors = list_monitors()
            if monitors != self.monitors:
                self.pause(True)
                self.monitors = monitors
                self.mapper = ScreenMapper(self.settings, choose_monitor(monitors, self.settings.monitor_id))
                self.notify("Las pantallas cambiaron. Revisa el monitor y vuelve a activar.", 12)
        except Exception as exc:
            self.pause(True)
            self.notify(f"No se pudieron consultar las pantallas: {exc}")

    def toggle_camera(self):
        if self._operation:
            return
        self._restart_camera(restart=not self._camera_enabled or not self.pipeline or not self.pipeline.running)

    def _restart_camera(self, restart=True):
        self.pause(True)
        self._operation = True
        self.notify("Preparando cámara…")

        def stop_worker():
            try:
                stopped = True if self.smoke or not self.pipeline else self.pipeline.stop(timeout=2)
            except Exception:
                logging.exception("Falló el cierre de la cámara")
                stopped = False
            self.bus.put(("camera_stopped", (stopped, restart)))
        if self.smoke:
            stop_worker()
        else:
            threading.Thread(target=stop_worker, name="BioGesture-restart", daemon=True).start()

    def open_settings(self):
        if self._closing:
            return
        self.pause(True)
        if self._settings_dialog:
            self._settings_dialog.lift()
            return
        self.show()
        dialog = tk.Toplevel(self.root)
        self._settings_dialog = dialog
        dialog.title("Configuración · Bio-Gesture")
        dialog.geometry("530x565")
        dialog.resizable(True, True)
        dialog.minsize(420, 350)
        dialog.transient(self.root)
        body = ttk.Frame(dialog)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        viewport = tk.Canvas(body, highlightthickness=0)
        vertical = ttk.Scrollbar(body, orient="vertical", command=viewport.yview)
        horizontal = ttk.Scrollbar(body, orient="horizontal", command=viewport.xview)
        viewport.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        viewport.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        notebook = ttk.Notebook(viewport)
        notebook_window = viewport.create_window(0, 0, anchor="nw", window=notebook)

        def update_scroll_region(event=None):
            viewport.configure(scrollregion=viewport.bbox("all"))

        def fit_notebook(event):
            viewport.itemconfigure(notebook_window, width=max(notebook.winfo_reqwidth(), event.width),
                                   height=max(notebook.winfo_reqheight(), event.height))
            update_scroll_region()

        notebook.bind("<Configure>", update_scroll_region)
        viewport.bind("<Configure>", fit_notebook)
        variables = {}
        tabs = {}
        for name in ("Cámara", "Precisión", "Escritorio", "Diagnóstico"):
            tabs[name] = ttk.Frame(notebook, padding=12)
            notebook.add(tabs[name], text=name)

        def field(tab_name, label, key, options=None):
            tab = tabs[tab_name]
            row = len(tab.grid_slaves()) // 2
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=5)
            value = getattr(self.settings, key)
            variable = tk.BooleanVar(value=value) if type(value) is bool else tk.StringVar(value=str(value))
            variables[key] = variable
            if type(value) is bool:
                widget = ttk.Checkbutton(tab, variable=variable)
            elif options:
                widget = ttk.Combobox(tab, textvariable=variable, values=options, state="readonly", width=24)
            else:
                widget = ttk.Entry(tab, textvariable=variable, width=27)
            widget.grid(row=row, column=1, sticky="ew", padx=(18, 0), pady=5)
            tab.columnconfigure(1, weight=1)

        for label, key, options in (
            ("Índice de cámara (0–16)", "camera_index", None),
            ("Ancho solicitado", "capture_width", (320, 640, 960, 1280, 1920)),
            ("Alto solicitado", "capture_height", (240, 360, 480, 540, 720, 1080)),
            ("FPS de cámara", "capture_fps", (15, 24, 30, 60)),
            ("FPS de detección", "detection_fps", (5, 10, 15, 24, 30, 60)),
            ("Vista espejo", "mirror", None),
        ):
            field("Cámara", label, key, options)
        ttk.Label(tabs["Cámara"], text="Deja una mano visible para elegir la principal al inicio.\nDespués puedes usar las dos, cada una con sus comandos.\nLa detección se recupera sola, sin retirar las manos.\nMás → Reelegir mano principal permite cambiar los roles.",
                  wraplength=425).grid(row=10, column=0, columnspan=2, sticky="w", pady=14)
        for label, key in (
            ("Cierre de pinza / palma", "pinch_close"), ("Apertura de pinza / palma", "pinch_open"),
            ("Indicador de arrastre (s)", "drag_hold"), ("Suavizado en reposo", "min_cutoff"),
            ("Respuesta al movimiento", "filter_beta"), ("Velocidad de desplazamiento", "scroll_rate"),
            ("Sensibilidad de volumen", "volume_sensitivity"), ("Invertir horizontal", "invert_x"),
            ("Invertir vertical", "invert_y"),
        ):
            field("Precisión", label, key)
        monitor_options = ["primary", "virtual"] + [m.id for m in self.monitors]
        field("Escritorio", "Monitor", "monitor_id", monitor_options)
        field("Escritorio", "Perfil", "profile", ("Global", "VS Code", "Navegador", "Multimedia"))
        field("Escritorio", "Opacidad fija (0.4–1)", "opacity")
        field("Escritorio", "Iniciar pausado", "start_paused")
        field("Escritorio", "Dibujar puntos de mano", "show_landmarks")
        field("Escritorio", "Comandos de mano auxiliar", "auxiliary_enabled")
        ttk.Label(tabs["Escritorio"], text="primary = principal · virtual = todas las pantallas\nLos perfiles actúan sobre la aplicación en primer plano.",
                  wraplength=420).grid(row=7, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(tabs["Escritorio"], text="Calibrar zona de trabajo…", command=self.open_calibration).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(tabs["Diagnóstico"], text=f"Versión {__version__}\nPrincipal + auxiliar · Roles recuperables\n\n"
                  "Auxiliar, pinzas con el pulgar (mantener 0.45 s):\n"
                  "Índice: copiar · Corazón: pegar\nAnular: deshacer · Meñique: rehacer\n"
                  "L (pulgar e índice): mantener 0.45 s; subir/bajar desplaza.\n"
                  "Volver al centro o soltar la L detiene el desplazamiento.\n"
                  "La aplicación activa decide qué puede copiar o deshacer.\n\n"
                  "El modelo funciona localmente. No se guardan fotos ni video.\n\n"
                  "La pausa conserva la detección para reanudar con victoria.\n"
                  "Cámara apaga el dispositivo. Salir cierra la aplicación.\n\n"
                  "Ctrl+Alt+F12: pausar y recuperar la ventana.\n\n"
                  f"Configuración y registros:\n{data_directory()}", wraplength=425, justify="left").pack(anchor="w")
        ttk.Button(tabs["Diagnóstico"], text="Abrir carpeta de diagnóstico", command=self._open_data_directory).pack(anchor="w", pady=15)
        ttk.Label(tabs["Diagnóstico"], textvariable=self.status, justify="left", wraplength=425).pack(anchor="w")
        ttk.Label(tabs["Diagnóstico"], textvariable=self.metrics, justify="left", wraplength=425).pack(anchor="w")

        def diagnostics_visibility(event=None):
            self._diagnostics_visible = notebook.select() == str(tabs["Diagnóstico"])

        notebook.bind("<<NotebookTabChanged>>", diagnostics_visibility)

        def close_dialog():
            self._settings_dialog = None
            self._diagnostics_visible = False
            if self._calibration_dialog:
                calibration = self._calibration_dialog
                self._calibration_dialog = None
                calibration.destroy()
            dialog.destroy()

        def on_destroy(event):
            if event.widget is dialog and self._settings_dialog is dialog:
                self._settings_dialog = None
                self._diagnostics_visible = False
                if self._calibration_dialog:
                    calibration = self._calibration_dialog
                    self._calibration_dialog = None
                    calibration.destroy()

        def save():
            if self._operation:
                messagebox.showinfo("Cámara", "Espera a que termine el cambio de cámara.", parent=dialog)
                return
            try:
                changes = {}
                for key, variable in variables.items():
                    previous = getattr(self.settings, key)
                    changes[key] = type(previous)(variable.get())
                candidate = replace(self.settings, **changes).validate()
                if not self.smoke:
                    candidate.save()
                self.settings = candidate
                self.engine.settings = candidate
                self.auxiliary_engine.settings = candidate
                self.pause(True)
                self.actions.set_profile(candidate.profile)
                self.mapper = ScreenMapper(candidate, choose_monitor(self.monitors, candidate.monitor_id))
                self._apply_window_mode()
                close_dialog()
                self._restart_camera(True)
            except (ValueError, TypeError, OSError, tk.TclError) as exc:
                messagebox.showerror("Revisa la configuración", str(exc), parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Label(buttons, text="El control permanece pausado.").pack(side="left")
        ttk.Button(buttons, text="Guardar", command=save).pack(side="right")
        ttk.Button(buttons, text="Cancelar", command=close_dialog).pack(side="right", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Destroy>", on_destroy)
        dialog.update_idletasks()
        desired_width = max(530, notebook.winfo_reqwidth() + vertical.winfo_reqwidth() + 28,
                            buttons.winfo_reqwidth() + 28)
        desired_height = max(400, notebook.winfo_reqheight() + horizontal.winfo_reqheight()
                             + buttons.winfo_reqheight() + 48)
        dialog.geometry(f"{min(desired_width, max(420, dialog.winfo_screenwidth() - 48))}x"
                        f"{min(desired_height, max(350, dialog.winfo_screenheight() - 90))}")

    def _open_data_directory(self):
        if self.smoke:
            return
        try:
            directory = data_directory()
            directory.mkdir(parents=True, exist_ok=True)
            os.startfile(directory)
        except OSError as exc:
            messagebox.showerror("Diagnóstico", str(exc), parent=self._settings_dialog or self.root)

    def open_calibration(self):
        self.pause(True)
        if self._calibration_dialog:
            self._calibration_dialog.lift()
            return
        dialog = tk.Toplevel(self.root)
        self._calibration_dialog = dialog
        dialog.title("Calibrar zona de trabajo")
        dialog.geometry("480x245")
        dialog.resizable(True, True)
        self._samples.clear()
        state = {"since": time.monotonic(), "first": None}
        instruction = tk.StringVar(value="1. Coloca el índice en el extremo superior izquierdo\n"
                                   "del área que puedes alcanzar cómodamente.\nMantén la posición un segundo y pulsa Capturar.")
        ttk.Label(dialog, textvariable=instruction, justify="center", wraplength=450).pack(padx=15, pady=24)
        ttk.Label(dialog, text="La referencia es la imagen de cámara con tu espejo actual.\n"
                  "Muestra solo la mano que usarás y aplica los cambios de cámara.", justify="center").pack(pady=4)

        def close():
            self._calibration_dialog = None
            dialog.destroy()

        def on_destroy(event):
            if event.widget is dialog and self._calibration_dialog is dialog:
                self._calibration_dialog = None

        def capture():
            try:
                point = calibration_corner(self._samples, time.monotonic(), state["since"], self.settings)
                if state["first"] is None:
                    state["first"] = point
                    state["since"] = time.monotonic()
                    self._samples.clear()
                    instruction.set("2. Coloca el índice en el extremo inferior derecho.\n"
                                    "Mantén la posición un segundo y pulsa Capturar.")
                    return
                x, y = state["first"]
                candidate = replace(self.settings, active_left=x, active_top=y, active_right=point[0], active_bottom=point[1]).validate()
                if not self.smoke:
                    candidate.save()
                self.settings = candidate
                self.engine.settings = candidate
                self.auxiliary_engine.settings = candidate
                self.mapper = ScreenMapper(candidate, choose_monitor(self.monitors, candidate.monitor_id))
                self.notify("Zona calibrada. Cierra Ajustes y pulsa Activar.", 12)
                close()
            except (ValueError, OSError) as exc:
                messagebox.showerror("Calibración", str(exc), parent=dialog)
        buttons = ttk.Frame(dialog)
        buttons.pack(pady=16)
        ttk.Button(buttons, text="Capturar", command=capture).pack(side="left", padx=8)
        ttk.Button(buttons, text="Cancelar", command=close).pack(side="left", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.bind("<Destroy>", on_destroy)
        dialog.update_idletasks()
        dialog.geometry(f"{min(max(480, dialog.winfo_reqwidth()), dialog.winfo_screenwidth() - 48)}x"
                        f"{min(max(245, dialog.winfo_reqheight()), dialog.winfo_screenheight() - 90)}")

    def request_close(self):
        if self._closing:
            return
        self._closing = True
        self.pause(True)
        self.actions.close()
        self.notify("Cerrando cámara…")
        if self._hook:
            try:
                self._hook.stop()
            except Exception:
                logging.exception("No se pudo detener el atajo global; el cierre continuará")

        def stop_worker():
            if self._tray:
                try:
                    self._tray.stop()
                except Exception:
                    logging.exception("Error al cerrar la bandeja")
            try:
                stopped = True if self.smoke or not self.pipeline else self.pipeline.stop(timeout=2)
            except Exception:
                logging.exception("Error al cerrar el seguimiento")
                stopped = False
            self.bus.put(("close_done", stopped))
        if self.smoke:
            stop_worker()
        else:
            threading.Thread(target=stop_worker, name="BioGesture-close", daemon=True).start()

    def _destroy(self):
        self._destroyed = True
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except tk.TclError:
                pass
        self.root.destroy()
