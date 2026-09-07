"""Auxiliary pinches and L-pose scrolling; descriptive events, no desktop input."""

import math

from .gestures import HandGeometry
from .models import ActionEvent, HandSample
from .settings import Settings


DEFAULT_COMMANDS = ("COPIAR", "PEGAR", "DESHACER", "REHACER")
FINGER_TIPS = (8, 12, 16, 20)


class AuxiliaryGestureEngine:
    """Hold a pinch for one command or an L for image-centered scrolling.

    The caller owns role assignment and must disable this engine whenever the
    auxiliary is not authorized. A sample's handedness is not an authorization.
    Command positions correspond to index, middle, ring and little finger.
    """

    HOLD_SECONDS = 0.45
    MAX_SAMPLE_AGE = 0.35
    MIN_SCROLL_GAP = 0.15
    MAX_SCROLL_GAP = 0.35
    # Normalized camera-image Y: stop within 0.45..0.55, full speed at 0 or 1.
    SCROLL_CENTER_Y = 0.5
    SCROLL_DEAD_ZONE = 0.05
    SCROLL_FULL_SPEED = 0.5
    SCROLL_MIN_SPEED_FRACTION = 0.25
    L_MIN_ANGLE = 55.0
    L_MAX_ANGLE = 125.0

    def __init__(self, settings: Settings):
        self.settings = settings
        self.clear()

    def reset(self) -> None:
        """Cancel a pending hold, retaining the fired latch and replay watermark."""
        self._candidate = None
        self._candidate_since = None
        self._clear_scroll()

    def _clear_scroll(self) -> None:
        self._l_since = None
        self._scroll_scale = None
        self._scroll_timestamp = None
        self._scroll_carry = 0.0
        self._scroll_direction = 0

    def clear(self) -> None:
        """Hard reset for an explicitly new role/session, not tracking loss."""
        self.reset()
        self._latched_tip = None
        self._last_timestamp = None
        self._last_now = None
        self._commands = None

    @staticmethod
    def _finite(value) -> bool:
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    def _valid(self, sample: HandSample, now: float) -> bool:
        try:
            return (
                len(sample.landmarks) == 21
                and self._finite(sample.width) and sample.width > 0
                and self._finite(sample.height) and sample.height > 0
                and self._finite(sample.confidence)
                and self.settings.tracking_confidence <= sample.confidence <= 1.0
                and self._finite(sample.timestamp)
                and 0 <= now - sample.timestamp <= self.MAX_SAMPLE_AGE
                and all(self._finite(v) for p in sample.landmarks for v in (p.x, p.y, p.z))
            )
        except (AttributeError, TypeError, OverflowError):
            return False

    @classmethod
    def _is_l_pose(cls, geometry: HandGeometry) -> bool:
        """Index and thumb at roughly 90 degrees, three other fingers folded.

        This auxiliary-only cue is invariant under mirror, laterality and hand
        rotation; scroll direction remains the vertical axis of the image.
        """
        p = geometry.points
        scale = geometry.scale
        # These tolerances belong only to the auxiliary. A natural L can have
        # a slightly bent index/thumb; primary cursor/pinch features stay intact.
        if (cls._joint_angle(p[5], p[6], p[7]) < 140
                or cls._joint_angle(p[6], p[7], p[8]) < 135
                or math.dist(p[0], p[8]) <= math.dist(p[0], p[6]) * 1.08
                or math.dist(p[5], p[8]) < scale * 0.7
                or cls._joint_angle(p[2], p[3], p[4]) < 135
                or math.dist(p[4], p[5]) < scale * 0.5
                or math.dist(p[0], p[4]) <= math.dist(p[0], p[3]) * 1.02):
            return False
        for base in (9, 13, 17):
            if (math.dist(p[0], p[base + 3]) > math.dist(p[0], p[base + 1]) * 1.10
                    or (cls._joint_angle(p[base], p[base + 1], p[base + 2]) > 160
                        and math.dist(p[base], p[base + 3]) > scale * 0.8)):
                return False
        # Compare the visible L in the image plane. Estimated depth can make
        # the same clear right-angle silhouette look acute in 3D.
        thumb = tuple(b - a for a, b in zip(p[2][:2], p[4][:2]))
        index = tuple(b - a for a, b in zip(p[5][:2], p[8][:2]))
        if min(math.hypot(*thumb), math.hypot(*index)) < scale * 0.3:
            return False
        denominator = math.hypot(*thumb) * math.hypot(*index)
        if not math.isfinite(denominator) or denominator <= 1e-8:
            return False
        cosine = sum(a * b for a, b in zip(thumb, index)) / denominator
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        return cls.L_MIN_ANGLE <= angle <= cls.L_MAX_ANGLE and geometry.distance(4, 8) >= 0.7

    @staticmethod
    def _joint_angle(a, b, c) -> float:
        u, v = tuple(x - y for x, y in zip(a, b)), tuple(x - y for x, y in zip(c, b))
        denominator = math.hypot(*u) * math.hypot(*v)
        if denominator <= 1e-8:
            return 0.0
        cosine = sum(x * y for x, y in zip(u, v)) / denominator
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    def _scroll(self, geometry: HandGeometry, timestamp: float, image_height: float) -> tuple[ActionEvent, ...]:
        if not self._is_l_pose(geometry):
            self._clear_scroll()
            return ()
        frequency = self.settings.detection_fps
        if not self._finite(frequency) or frequency <= 0:
            self._clear_scroll()
            return ()
        gap_limit = min(self.MAX_SCROLL_GAP, max(self.MIN_SCROLL_GAP, 1.5 / frequency))
        if (self._scroll_timestamp is not None
                and timestamp - self._scroll_timestamp > gap_limit + 1e-9):
            # No catch-up after a frame stall; confirm the L again in place.
            self._clear_scroll()
        previous = self._scroll_timestamp
        self._scroll_timestamp = timestamp
        if self._l_since is None:
            self._l_since = timestamp
        if timestamp - self._l_since + 1e-9 < self.HOLD_SECONDS:
            return ()
        if self._scroll_scale is None:
            self._scroll_scale = geometry.scale
        if not 0.55 <= geometry.scale / self._scroll_scale <= 1.8:
            self._clear_scroll()
            return ()
        # The palm's vertical position is measured against the fixed image
        # center, never against where the hand happened to confirm the L.
        center_y = sum(geometry.points[i][1] for i in (0, 5, 9, 13, 17)) / (5 * image_height)
        displacement = self.SCROLL_CENTER_Y - center_y
        magnitude = abs(displacement) - self.SCROLL_DEAD_ZONE
        if magnitude <= 1e-9:
            self._scroll_carry = 0.0
            self._scroll_direction = 0
            return ()
        direction = 1 if displacement > 0 else -1
        if direction != self._scroll_direction:
            self._scroll_carry = 0.0
            self._scroll_direction = direction
        maximum_rate = self.settings.scroll_rate
        if not self._finite(maximum_rate) or maximum_rate <= 0:
            self._clear_scroll()
            return ()
        deflection = min(1.0, magnitude / (self.SCROLL_FULL_SPEED - self.SCROLL_DEAD_ZONE))
        # A confirmed L just outside neutral must not take minutes to produce a
        # wheel step. Neutral still stops immediately and clears the fraction.
        speed = maximum_rate * (self.SCROLL_MIN_SPEED_FRACTION
                                + (1 - self.SCROLL_MIN_SPEED_FRACTION) * deflection)
        # A low-FPS confirmation may arrive after the hold deadline. Integrate
        # only its active part, not the preceding 0.45 seconds of preparation.
        active_since = self._l_since + self.HOLD_SECONDS
        elapsed = timestamp - max(previous if previous is not None else timestamp, active_since)
        self._scroll_carry += direction * speed * elapsed
        # Monotonic decimal timestamps may represent an exact whole step as
        # 3.99999999999998; do not defer that step and bunch it into the next frame.
        steps = math.trunc(self._scroll_carry + direction * 1e-9)
        self._scroll_carry -= steps
        if abs(self._scroll_carry) < 1e-8:
            self._scroll_carry = 0.0
        return (ActionEvent("scroll", steps),) if steps else ()

    def update(self, sample: HandSample | None, now: float, *, enabled: bool = True,
               commands=DEFAULT_COMMANDS) -> tuple[ActionEvent, ...]:
        """Return zero or one command/scroll event from a fresh observation.

        Invalid configuration or samples fail closed. Disabling never clears a
        fired latch; an open pinch must be observed after enabling to rearm it.
        Changing the command map cancels the hold without clearing that latch.
        """
        if not self._finite(now):
            self.reset()
            return ()
        if self._last_now is not None and now < self._last_now:
            self.reset()
            return ()
        self._last_now = now
        if (not isinstance(commands, (tuple, list)) or len(commands) != 4
                or any(not isinstance(command, str) or not command.strip() for command in commands)):
            self.reset()
            return ()
        command_map = tuple(commands)
        if command_map != self._commands:
            self.reset()
            self._commands = command_map
        if sample is None or not self._valid(sample, now):
            self.reset()
            return ()
        timestamp = sample.timestamp
        if self._last_timestamp is not None:
            if timestamp <= self._last_timestamp:
                if timestamp < self._last_timestamp or not enabled:
                    self.reset()
                return ()
            if timestamp - self._last_timestamp > self.MAX_SAMPLE_AGE:
                self.reset()
        self._last_timestamp = timestamp
        if not enabled:
            self.reset()
            return ()
        geometry = HandGeometry(sample, mirror=self.settings.mirror)
        if not math.isfinite(geometry.scale) or geometry.scale < 5:
            self.reset()
            return ()
        distances = {tip: geometry.distance(4, tip) for tip in FINGER_TIPS}
        if any(not math.isfinite(distance) for distance in distances.values()):
            self.reset()
            return ()
        if self._latched_tip is not None:
            if distances[self._latched_tip] < self.settings.pinch_open:
                self._clear_scroll()
                return ()
            self._latched_tip = None
        if self._candidate is not None and distances[self._candidate] >= self.settings.pinch_open:
            self.reset()
        if self._candidate is None:
            tip = min(FINGER_TIPS, key=distances.__getitem__)
            if distances[tip] >= self.settings.pinch_close:
                return self._scroll(geometry, timestamp, sample.height)
            self._clear_scroll()
            self._candidate, self._candidate_since = tip, timestamp
            return ()
        self._clear_scroll()
        if timestamp - self._candidate_since + 1e-9 < self.HOLD_SECONDS:
            return ()
        tip = self._candidate
        self._latched_tip = tip
        self.reset()
        return (ActionEvent("command", command_map[FINGER_TIPS.index(tip)]),)
