"""Two session roles with automatic recovery, not an identity lock.

The user chooses the principal by leaving one hand visible once. Laterality is
only matching evidence for that session, never a hard-coded permission. A lost
frame or crossing cannot latch the application into a manual recovery state.
"""

from dataclasses import dataclass
import math

from .models import HandSample


@dataclass(frozen=True)
class SelectionResult:
    sample: HandSample | None
    status: str
    hand_count: int
    auxiliary: HandSample | None = None


@dataclass(frozen=True)
class _Feature:
    sample: HandSample
    center: tuple[float, float]
    scale: float


@dataclass
class _Track:
    feature: _Feature
    last_seen: float
    velocity: tuple[float, float] = (0.0, 0.0)


class PrincipalHandSelector:
    """Keep both roles across missing frames, reacquiring from each new result."""

    def __init__(self, confidence=0.65):
        self.confidence = confidence
        self.reset()

    def reset(self):
        """An explicit new choice, used at startup or from the user controls."""
        self._tracks = {}
        self._principal_label = ""
        self._last_time = None
        self._principal_missing = False
        self._auxiliary_observed = False

    def suspend(self):
        """Forget motion prediction during camera interruption, not the roles."""
        for track in self._tracks.values():
            track.velocity = (0.0, 0.0)
        self._principal_missing = True

    @property
    def selected(self):
        return 1 in self._tracks

    @staticmethod
    def _feature(sample):
        if (len(sample.landmarks) != 21 or sample.width <= 0 or sample.height <= 0
                or not math.isfinite(sample.confidence) or not math.isfinite(sample.timestamp)
                or not all(math.isfinite(v) for p in sample.landmarks for v in (p.x, p.y, p.z))):
            return None
        aspect = sample.height / sample.width
        points = [(p.x, p.y * aspect) for p in sample.landmarks]
        center = tuple(sum(points[i][axis] for i in (0, 5, 9, 13, 17)) / 5 for axis in (0, 1))
        scale = (math.dist(points[0], points[9]) + math.dist(points[5], points[17])) / 2
        return _Feature(sample, center, scale) if scale >= 0.008 else None

    def _label(self, role):
        if not self._principal_label:
            return ""
        return self._principal_label if role == 1 else ("Left" if self._principal_label == "Right" else "Right")

    def _cost(self, role, feature, now):
        expected = self._label(role)
        observed = feature.sample.handedness
        reliable = observed in ("Left", "Right") and feature.sample.confidence >= self.confidence
        track = self._tracks.get(role)
        if track is None:
            return (0.5 if observed == expected else 9.0) if reliable and expected else 6.0
        dt = max(0.0, now - track.last_seen)
        horizon = min(dt, 0.075) if dt <= 0.2 else 0.0
        prediction = tuple(p + v * horizon for p, v in zip(track.feature.center, track.velocity))
        scale = (track.feature.scale + feature.scale) / 2
        spatial = min(math.dist(prediction, feature.center),
                      math.dist(track.feature.center, feature.center) + scale * 0.2) / scale
        spatial = min(6.0, spatial) * (1.0 if dt <= 0.2 else 0.15)
        mismatch = reliable and expected and observed != expected
        # Reliable session laterality outweighs even a large positional change:
        # a fast crossing must not let the auxiliary steal the principal role.
        # The narrow one-hand label-jitter exception is handled before scoring.
        penalty = 8.0 if mismatch else 0.0
        return spatial + penalty + min(0.5, abs(math.log(feature.scale / track.feature.scale)) * 0.15)

    def _update_track(self, role, feature, now):
        previous = self._tracks.get(role)
        velocity = (0.0, 0.0)
        if previous and 0 < now - previous.last_seen <= 0.2:
            dt = now - previous.last_seen
            velocity = tuple(old * 0.5 + (new - last) / dt * 0.5
                             for old, last, new in zip(previous.velocity, previous.feature.center, feature.center))
        self._tracks[role] = _Track(feature, now, velocity)

    def _continuous_single_principal(self, feature, now):
        track = self._tracks[1]
        scale = (track.feature.scale + feature.scale) / 2
        return (not self._auxiliary_observed and not self._principal_missing
                and 0 < now - track.last_seen < 0.2
                and math.dist(track.feature.center, feature.center) <= scale * 0.4)

    def update(self, samples, now):
        samples = tuple(samples)
        count = len(samples)
        if not math.isfinite(now):
            self.suspend()
            return SelectionResult(None, "SIN DETECCIÓN", count)
        if self._last_time is not None and now <= self._last_time:
            return SelectionResult(None, "ESPERANDO CUADRO", count)
        self._last_time = now
        if self.selected and count > 1:
            self._auxiliary_observed = True
        features = []
        for sample in samples:
            feature = self._feature(sample)
            if (feature and sample.confidence >= self.confidence
                    and 0 <= now - sample.timestamp <= 0.35):
                features.append(feature)
        if not features or count > 2:
            self.suspend()
            return SelectionResult(None, "SIN DETECCIÓN", count)
        if not self.selected:
            # Only initial choice needs one hand. No off-screen timer and no
            # repeated election following a lost detection.
            if count != 1 or len(features) != 1:
                return SelectionResult(None, "DEJA UNA MANO PARA ELEGIR PRINCIPAL", count)
            feature = features[0]
            self._principal_label = feature.sample.handedness if feature.sample.handedness in ("Left", "Right") else ""
            self._update_track(1, feature, now)
            self._principal_missing = False
            return SelectionResult(feature.sample, "PRINCIPAL", count)

        if len(features) == 2:
            # Withhold only the overlapping observation. A clear next frame
            # recovers automatically without requiring any user ceremony.
            if math.dist(features[0].center, features[1].center) < min(f.scale for f in features) * 0.35:
                self._principal_missing = True
                return SelectionResult(None, "RECUPERANDO SEGUIMIENTO", count)
            labels = [feature.sample.handedness for feature in features]
            gap = self._principal_missing or now - self._tracks[1].last_seen > 0.2
            if gap and labels[0] == labels[1] and labels[0] in ("Left", "Right"):
                # Duplicated anatomy after an unseen interval cannot establish
                # both roles. Discard only this result, not the session choice.
                self._principal_missing = True
                return SelectionResult(None, "RECUPERANDO SEGUIMIENTO", count)
            direct = self._cost(1, features[0], now) + self._cost(2, features[1], now)
            reverse = self._cost(1, features[1], now) + self._cost(2, features[0], now)
            assignments = {1: features[0], 2: features[1]} if direct <= reverse else {1: features[1], 2: features[0]}
        else:
            feature = features[0]
            role = (1 if count == 1 and self._continuous_single_principal(feature, now)
                    else min((1, 2), key=lambda role: self._cost(role, feature, now)))
            assignments = {role: feature}
        for role, feature in assignments.items():
            self._update_track(role, feature, now)
        principal = assignments.get(1)
        auxiliary = assignments.get(2)
        if auxiliary is not None:
            self._auxiliary_observed = True
        self._principal_missing = principal is None
        return SelectionResult(principal.sample if principal else None,
                               "DOS MANOS" if principal and auxiliary else "PRINCIPAL" if principal else "AUXILIAR",
                               count, auxiliary.sample if auxiliary else None)
