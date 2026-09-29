"""Ocular-only output stabilization; never used to learn or validate a gaze model.

All filter tuning is in normalized monitor coordinates, so screen size, DPI and
the index's settings do not alter it. No camera, neural runtime or OS input lives
here. The isolated P viewer and desktop use precisely this same filter.
"""

import math

from .coordinates import OneEuroFilter, RectMonitor


class GazePointerFilter:
    """Reduce fixation jitter while following confirmed gaze shifts promptly.

    An abrupt displacement over 16% of the normalized screen diagonal scale
    waits for one further *fresh* sample. An isolated spike is never fed into
    the filter; any continuing shift is accepted on that next frame. Thus this
    guard cannot keep an intended shift pending forever.
    This is smoothing, not a correction to calibration accuracy.
    """

    # A lower base cutoff gives a calmer fixation.  A moderate beta keeps
    # deliberate saccades responsive without reintroducing camera noise.
    # Values are tuned in normalized monitor coordinates and are shared by
    # the desktop cursor and the diagnostic P viewer.
    MIN_CUTOFF = 0.3
    BETA = 5.0
    DERIVATIVE_CUTOFF = 1.0
    RESET_GAP_SECONDS = .25
    JUMP_DISTANCE = .16

    def __init__(self):
        self._x = OneEuroFilter(self.MIN_CUTOFF, self.BETA, self.DERIVATIVE_CUTOFF)
        self._y = OneEuroFilter(self.MIN_CUTOFF, self.BETA, self.DERIVATIVE_CUTOFF)
        self.reset()

    def reset(self):
        self._x.reset()
        self._y.reset()
        self._timestamp = self._accepted = self._value = self._pending_origin = None

    @property
    def timestamp(self):
        """Latest capture processed, never a UI poll time."""
        return self._timestamp

    def filter(self, x, y, timestamp):
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (x, y, timestamp)) or not (0 <= x <= 1 and 0 <= y <= 1)):
            self.reset()
            raise ValueError("El puntero ocular requiere coordenadas normalizadas y tiempo válidos")
        if self._timestamp is not None:
            if timestamp <= self._timestamp:
                return self._value
            if timestamp - self._timestamp > self.RESET_GAP_SECONDS:
                self.reset()
        point = x, y
        self._timestamp = timestamp
        if self._accepted is not None:
            if self._pending_origin is not None:
                self._pending_origin = None
            elif math.dist(point, self._accepted) > self.JUMP_DISTANCE:
                self._pending_origin = self._accepted
                return self._value
        self._accepted = point
        self._value = self._x(x, timestamp), self._y(y, timestamp)
        return self._value

    __call__ = filter


class GazePointerMapper:
    """Stabilized normalized gaze to physical monitor pixels, without input."""

    def __init__(self, monitor: RectMonitor):
        if monitor.width <= 0 or monitor.height <= 0:
            raise ValueError("El monitor debe tener un tamaño positivo")
        self.monitor = monitor
        self.filter = GazePointerFilter()

    def reset(self):
        self.filter.reset()

    def map(self, x, y, timestamp):
        x, y = self.filter(x, y, timestamp)
        monitor = self.monitor
        return (monitor.left + round(x * (monitor.width - 1)),
                monitor.top + round(y * (monitor.height - 1)))
