"""Minimal radial presentation: eight short labels and one horizontal dwell bar."""

from dataclasses import dataclass
import math

from .gestures import MENUS


WINDOW_WIDTH = 550
WINDOW_HEIGHT = 375
TOOLBAR_HEIGHT = 28
FOOTER_HEIGHT = 12
CAMERA_HEIGHT = WINDOW_HEIGHT - TOOLBAR_HEIGHT - FOOTER_HEIGHT
BACKGROUND = "#11171d"
SURFACE = "#1a232c"
BORDER = "#35424c"
TEXT = "#eef2f5"
MUTED = "#9daab5"
ACCENT = "#79d8dc"

COMMAND_LABELS = {
    "SISTEMA": "Sistema", "EDICION": "Edición", "WEB": "Web", "MEDIA": "Multimedia",
    "MAYUS": "Mayúsculas", "PESTANYA": "Ventanas", "INICIO": "Inicio", "ESC": "Escape",
    "CONFIG": "Ajustes", "ADMIN": "Tareas", "BLOQUEAR": "Bloquear", "BUSCAR": "Buscar",
    "VOL+": "Volumen +", "VOL-": "Volumen −", "MUTE": "Silenciar", "VOLVER": "Volver",
    "COPIAR": "Copiar", "PEGAR": "Pegar", "DESHACER": "Deshacer", "REHACER": "Rehacer",
    "CORTAR": "Cortar", "TODO": "Seleccionar todo", "DELETE": "Eliminar",
    "NUEVA T": "Nueva pestaña", "CERRAR T": "Cerrar pestaña", "RECARGAR": "Recargar",
    "REGRESAR": "Atrás", "AVANCE": "Adelante", "FAVORITOS": "Favoritos", "DESCARGA": "Descargas",
    "PLAY/PAUSE": "Play/pausa", "SIGUIENTE": "Siguiente", "ATRAS 10s": "−10 s",
    "ADELAN 10s": "+10 s", "FULLSCREEN": "Pantalla completa", "SUBTITULOS": "Subtítulos",
}
STATE_LABELS = {
    "PAUSADO": "En pausa", "LISTO": "Listo", "SIN MANO": "Buscando mano", "PUNTERO": "Cursor",
    "PINZA": "Clic / arrastre", "ARRASTRE": "Arrastrando", "CLIC DERECHO": "Clic derecho",
    "VOLUMEN": "Volumen", "SCROLL": "Desplazamiento", "PREPARANDO SCROLL": "Preparando desplazamiento",
    "PREPARANDO MENU": "Preparando menú", "MENU": "Menú de acciones", "GESTO PAUSA": "Cambio de pausa",
    "PALMA / VENTANA": "Gesto de ventana", "SOLTAR GESTO": "Suelta el gesto", "CÁMARA APAGADA": "Cámara apagada",
    "ONDA 1/4": "Ventana · recorrido 1 de 4", "ONDA 2/4": "Ventana · recorrido 2 de 4",
    "ONDA 3/4": "Ventana · recorrido 3 de 4", "VENTANA CAMBIADA": "Ventana cambiada",
}


@dataclass(frozen=True)
class RadialGeometry:
    center_x: float = WINDOW_WIDTH / 2
    center_y: float = CAMERA_HEIGHT / 2 - 1
    inner_radius: float = 63
    outer_radius: float = 141
    label_radius: float = 103

    def point(self, radius, degrees):
        angle = math.radians(degrees)
        return self.center_x + radius * math.cos(angle), self.center_y + radius * math.sin(angle)

    def sector_polygon(self, index):
        """Index zero points right; increasing indices move clockwise, like the engine."""
        if index not in range(8):
            raise ValueError("El menú contiene ocho sectores")
        angles = [index * 45 - 21 + step * 3 for step in range(15)]
        points = [self.point(self.outer_radius, a) for a in angles]
        points.extend(self.point(self.inner_radius, a) for a in reversed(angles))
        return tuple(value for point in points for value in point)

    def label_position(self, index):
        return self.point(self.label_radius, index * 45)

    def ring_bounds(self, extra=0):
        radius = self.outer_radius + extra
        return self.center_x - radius, self.center_y - radius, self.center_x + radius, self.center_y + radius

    def progress_bounds(self):
        return self.center_x - 42, self.center_y - 2, self.center_x + 42, self.center_y + 2


def status_text(state, profile, *, paused=False, fixed=False):
    label = STATE_LABELS.get(state, state.capitalize())
    if paused and state not in ("PAUSADO", "CÁMARA APAGADA"):
        label = "En pausa" if state in ("LISTO", "PUNTERO") else f"En pausa · {label}"
    return f"{label}  ·  {profile}" + ("  ·  Fija" if fixed else "")


def draw_empty_state(canvas, title="", detail=""):
    """Clear the camera area; legacy title/detail arguments never become overlays."""
    canvas.delete("all")


def draw_radial_menu(canvas, output, geometry=None):
    geometry = geometry or RadialGeometry()
    commands = MENUS.get(output.menu_level, MENUS["PRINCIPAL"])
    selected = output.menu_selected if output.menu_selected in range(8) else -1
    canvas.create_oval(*geometry.ring_bounds(5), fill=BACKGROUND, outline="", tags="radial")
    for index, command in enumerate(commands):
        active = index == selected
        canvas.create_text(*geometry.label_position(index), text=COMMAND_LABELS[command], fill=ACCENT if active else TEXT,
                           font=("Segoe UI", -12, "bold" if active else "normal"), justify="center",
                           tags=("radial", "radial-label", f"label-{index}"))
    if selected >= 0:
        left, top, right, bottom = geometry.progress_bounds()
        progress = max(0.0, min(1.0, output.progress)) if math.isfinite(output.progress) else 0.0
        canvas.create_rectangle(left, top, right, bottom, fill=BORDER, outline="",
                                tags=("radial", "radial-progress-track"))
        if progress > 0:
            canvas.create_rectangle(left, top, left + (right - left) * progress, bottom,
                                    fill=ACCENT, outline="", tags=("radial", "radial-progress"))
