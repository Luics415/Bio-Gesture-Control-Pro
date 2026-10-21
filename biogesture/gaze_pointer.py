"""Ocular-only output stabilization; never used to learn or validate a gaze model.

All filter tuning is in normalized monitor coordinates, so screen size, DPI and
the index's settings do not alter it. No camera, neural runtime or OS input lives
here. The isolated P viewer and desktop use precisely this same filter.
"""

import math

from .coordinates import OneEuroFilter, RectMonitor


def extract_head_pose(observation) -> tuple[float, float] | None:
    """Extract head yaw and pitch (in radians) from an ocular observation.

    Prefers OpenVINO neural 3D head pose angles (radians) when available;
    falls back to MediaPipe geometric nose orientation angles.
    Returns None if observation is missing, non-finite, or invalid.
    """
    if observation is None or not getattr(observation, "valid", False):
        return None
    aux = getattr(observation, "auxiliary_features", ())
    if len(aux) >= 5 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in aux[3:5]):
        return (float(aux[3]), float(aux[4]))
    feat = getattr(observation, "features", ())
    if len(feat) >= 6 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in feat[4:6]):
        return (float(feat[4]) * 0.75, float(feat[5] - 0.25) * 0.75)
    return None


class GazePointerFilter:
    """Reduce fixation jitter while following confirmed gaze shifts promptly.

    An abrupt displacement over 16% of the normalized screen diagonal scale
    waits for one further *fresh* sample. An isolated spike is never fed into
    the filter; any continuing shift is accepted on that next frame. Thus this
    guard cannot keep an intended shift pending forever.
    This is smoothing, not a correction to calibration accuracy.
    """

    # A lower base cutoff gives a calmer fixation. A restrained beta keeps
    # deliberate saccades responsive while suppressing residual eye tremor.
    # Values are tuned in normalized monitor coordinates and are shared by
    # the desktop cursor and the diagnostic P viewer.
    MIN_CUTOFF = 0.22
    BETA = 4.0
    DERIVATIVE_CUTOFF = 1.0
    RESET_GAP_SECONDS = .25
    JUMP_DISTANCE = .16
    # Normalized deadband used only after the temporal filter.  Small residual
    # eye tremor inside this radius is treated as the same fixation, so the
    # desktop pointer does not wander while the user is looking at one place.
    # The release radius gives hysteresis and a soft transition to avoid rapid
    # re-entry or sudden steps at the edge of the deadband.
    FIXATION_RADIUS = .0085
    FIXATION_RELEASE_RADIUS = .0175

    # Hybrid Two-Stage Head/Face Micro-Targeting Vernier
    FACE_DEADZONE = 0.0022
    FACE_GAIN_X = 0.62
    FACE_GAIN_Y = 0.58
    MAX_MICRO_RADIUS = 0.065

    def __init__(self):
        self._x = OneEuroFilter(self.MIN_CUTOFF, self.BETA, self.DERIVATIVE_CUTOFF)
        self._y = OneEuroFilter(self.MIN_CUTOFF, self.BETA, self.DERIVATIVE_CUTOFF)
        self.reset()

    def reset(self):
        self._x.reset()
        self._y.reset()
        self._timestamp = self._accepted = self._value = self._pending_origin = None
        self._fixation = None
        self._fixation_active = False
        self._candidate_fixation = None
        self._face_anchor = None
        self._micro_offset = (0.0, 0.0)
        self._stage = "MACRO"

    @property
    def timestamp(self):
        """Latest capture processed, never a UI poll time."""
        return self._timestamp

    @property
    def stage(self) -> str:
        """Current hybrid control stage: 'MACRO' (gaze navigation) or 'MICRO' (facial vernier)."""
        return self._stage

    @property
    def micro_offset(self) -> tuple[float, float]:
        """Current micro-targeting displacement in normalized screen coordinates."""
        return self._micro_offset

    @property
    def face_anchor(self) -> tuple[float, float] | None:
        """Active facial orientation reference baseline for the current fixation."""
        return self._face_anchor

    def filter(self, x, y, timestamp, observation=None):
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
        fx_in, fy_in = x, y
        if self._fixation_active and self._fixation is not None and math.dist(point, self._fixation) < 0.036:
            fx_in = 0.65 * x + 0.35 * self._fixation[0]
            fy_in = 0.65 * y + 0.35 * self._fixation[1]
        filtered = self._x(fx_in, timestamp), self._y(fy_in, timestamp)
        if self._fixation is None:
            self._fixation = filtered
            self._fixation_active = True
            self._candidate_fixation = None
        elif self._fixation_active:
            # Keep the pointer at the concentration point until the filtered
            # gaze leaves the larger release radius.
            dist = math.dist(filtered, self._fixation)
            if dist < self.FIXATION_RELEASE_RADIUS:
                if dist > 0.0045:
                    fx, fy = self._fixation
                    self._fixation = (fx + 0.08 * (filtered[0] - fx), fy + 0.08 * (filtered[1] - fy))
                filtered = self._fixation
            else:
                self._fixation_active = False
                if dist < 0.045:
                    t = (dist - self.FIXATION_RELEASE_RADIUS) / (0.045 - self.FIXATION_RELEASE_RADIUS)
                    fx, fy = self._fixation
                    filtered = (fx + t * (filtered[0] - fx), fy + t * (filtered[1] - fy))
                self._candidate_fixation = filtered
        else:
            # In deliberate saccade/motion: establish fixation only when motion settles
            if self._candidate_fixation is not None and math.dist(filtered, self._candidate_fixation) <= self.FIXATION_RADIUS:
                self._fixation = filtered
                self._fixation_active = True
            else:
                self._candidate_fixation = filtered

        # Two-stage Gaze + Face micro-targeting fusion
        head_pose = extract_head_pose(observation)
        if head_pose is not None:
            if self._fixation_active:
                self._stage = "MICRO"
                if self._face_anchor is None:
                    self._face_anchor = head_pose
                else:
                    dyaw = head_pose[0] - self._face_anchor[0]
                    dpitch = head_pose[1] - self._face_anchor[1]

                    # Gentle posture creep compensation (half-life ~4s)
                    self._face_anchor = (
                        0.996 * self._face_anchor[0] + 0.004 * head_pose[0],
                        0.996 * self._face_anchor[1] + 0.004 * head_pose[1]
                    )

                    deadzone = self.FACE_DEADZONE
                    def _dz(val):
                        mag = abs(val)
                        if mag <= deadzone:
                            return 0.0
                        return math.copysign(mag - deadzone, val)

                    eff_yaw = _dz(dyaw)
                    eff_pitch = _dz(dpitch)

                    gain_x = self.FACE_GAIN_X * (1.0 + 8.0 * min(0.05, abs(eff_yaw)))
                    gain_y = self.FACE_GAIN_Y * (1.0 + 8.0 * min(0.05, abs(eff_pitch)))

                    ox = eff_yaw * gain_x
                    oy = eff_pitch * gain_y

                    dist_micro = math.hypot(ox, oy)
                    if dist_micro > self.MAX_MICRO_RADIUS:
                        scale = self.MAX_MICRO_RADIUS / dist_micro
                        ox *= scale
                        oy *= scale

                    self._micro_offset = (
                        0.68 * self._micro_offset[0] + 0.32 * ox,
                        0.68 * self._micro_offset[1] + 0.32 * oy
                    )
            else:
                self._stage = "MACRO"
                self._face_anchor = None
                self._micro_offset = (
                    0.50 * self._micro_offset[0],
                    0.50 * self._micro_offset[1]
                )

            combined_x = min(1.0, max(0.0, filtered[0] + self._micro_offset[0]))
            combined_y = min(1.0, max(0.0, filtered[1] + self._micro_offset[1]))
            filtered = (combined_x, combined_y)
        else:
            self._stage = "MACRO"
            self._face_anchor = None
            self._micro_offset = (0.0, 0.0)

        self._value = filtered
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

    @property
    def stage(self) -> str:
        return self.filter.stage

    @property
    def micro_offset(self) -> tuple[float, float]:
        return self.filter.micro_offset

    @property
    def face_anchor(self) -> tuple[float, float] | None:
        return self.filter.face_anchor

    def map(self, x, y, timestamp, observation=None):
        x, y = self.filter(x, y, timestamp, observation=observation)
        monitor = self.monitor
        return (monitor.left + round(x * (monitor.width - 1)),
                monitor.top + round(y * (monitor.height - 1)))
