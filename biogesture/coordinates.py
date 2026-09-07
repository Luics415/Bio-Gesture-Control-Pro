"""Screen geometry and time-based smoothing, with no desktop side effects."""

import math
from dataclasses import dataclass

from .settings import Settings


@dataclass(frozen=True)
class RectMonitor:
    id: str
    name: str
    left: int
    top: int
    width: int
    height: int
    primary: bool = False


class OneEuroFilter:
    """Adaptive low-pass filter: stable at rest, faster during deliberate motion."""

    def __init__(self, min_cutoff: float = 1.8, beta: float = 0.03, derivative_cutoff: float = 1.0):
        if min_cutoff <= 0 or beta < 0 or derivative_cutoff <= 0:
            raise ValueError("Los parámetros del filtro deben ser positivos")
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.derivative_cutoff = derivative_cutoff
        self.reset()

    def reset(self) -> None:
        self._time = None
        self._raw = self._value = self._derivative = 0.0

    @staticmethod
    def _alpha(cutoff: float, elapsed: float) -> float:
        return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * cutoff * elapsed))

    def filter(self, value: float, timestamp: float) -> float:
        if not math.isfinite(value) or not math.isfinite(timestamp):
            raise ValueError("Las coordenadas y el tiempo deben ser finitos")
        if self._time is None or timestamp - self._time > 0.35:
            self._time, self._raw, self._value, self._derivative = timestamp, value, value, 0.0
            return value
        if timestamp <= self._time:
            return self._value
        elapsed = timestamp - self._time
        velocity = (value - self._raw) / elapsed
        alpha_d = self._alpha(self.derivative_cutoff, elapsed)
        self._derivative += alpha_d * (velocity - self._derivative)
        alpha = self._alpha(self.min_cutoff + self.beta * abs(self._derivative), elapsed)
        self._value += alpha * (value - self._value)
        self._raw, self._time = value, timestamp
        return self._value

    __call__ = filter


class ScreenMapper:
    """Map a calibrated camera region to one physical-pixel monitor rectangle.

    Camera mirroring is applied once by capture, never repeated here. DPI-aware
    monitor enumeration belongs to the Windows adapter, so negative coordinates
    and monitors above/left of the primary monitor are preserved exactly.
    """

    def __init__(self, settings: Settings, monitor: RectMonitor):
        if monitor.width <= 0 or monitor.height <= 0:
            raise ValueError("El monitor debe tener un tamaño positivo")
        self.settings = settings
        self.monitor = monitor
        self._x = OneEuroFilter(settings.min_cutoff, settings.filter_beta)
        self._y = OneEuroFilter(settings.min_cutoff, settings.filter_beta)

    def reset(self) -> None:
        self._x.reset()
        self._y.reset()

    def map(self, x: float, y: float, timestamp: float) -> tuple[int, int]:
        if not all(math.isfinite(v) for v in (x, y, timestamp)):
            raise ValueError("La posición recibida no es válida")
        s, m = self.settings, self.monitor
        x = min(1.0, max(0.0, (x - s.active_left) / (s.active_right - s.active_left)))
        y = min(1.0, max(0.0, (y - s.active_top) / (s.active_bottom - s.active_top)))
        if s.invert_x:
            x = 1.0 - x
        if s.invert_y:
            y = 1.0 - y
        # Filter in physical pixels: beta then has consistent meaning at any FPS.
        px = self._x(m.left + x * (m.width - 1), timestamp)
        py = self._y(m.top + y * (m.height - 1), timestamp)
        return (
            max(m.left, min(m.left + m.width - 1, round(px))),
            max(m.top, min(m.top + m.height - 1, round(py))),
        )


def fit_video(source_width: int, source_height: int, target_width: int, target_height: int) -> tuple[int, int, int, int]:
    """Return (left, top, width, height) for an undistorted letterboxed preview."""
    if min(source_width, source_height, target_width, target_height) <= 0:
        raise ValueError("Las dimensiones deben ser positivas")
    ratio = min(target_width / source_width, target_height / source_height)
    width = min(target_width, max(1, round(source_width * ratio)))
    height = min(target_height, max(1, round(source_height * ratio)))
    return (target_width - width) // 2, (target_height - height) // 2, width, height
