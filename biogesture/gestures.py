"""Deterministic one-hand gesture state machine; never sends desktop input.

All distances use camera pixel aspect and palm scale. Input times are monotonic;
only new, recent samples advance a gesture. Pausing keeps detection available
so the victory gesture can also resume control.
"""

import math
import time
from dataclasses import dataclass

from .models import ActionEvent, EngineOutput, HandSample
from .settings import Settings


MENUS = {
    "PRINCIPAL": ["SISTEMA", "EDICION", "WEB", "MEDIA", "MAYUS", "PESTANYA", "INICIO", "ESC"],
    "SISTEMA": ["CONFIG", "ADMIN", "BLOQUEAR", "BUSCAR", "VOL+", "VOL-", "MUTE", "VOLVER"],
    "EDICION": ["COPIAR", "PEGAR", "DESHACER", "REHACER", "CORTAR", "TODO", "DELETE", "VOLVER"],
    "WEB": ["NUEVA T", "CERRAR T", "RECARGAR", "REGRESAR", "AVANCE", "FAVORITOS", "DESCARGA", "VOLVER"],
    "MEDIA": ["PLAY/PAUSE", "SIGUIENTE", "ATRAS 10s", "ADELAN 10s", "MUTE", "FULLSCREEN", "SUBTITULOS", "VOLVER"],
}


def _distance(a, b) -> float:
    return math.dist(a, b)


def _angle(a, b, c) -> float:
    u = tuple(x - y for x, y in zip(a, b))
    v = tuple(x - y for x, y in zip(c, b))
    denominator = math.sqrt(sum(x * x for x in u) * sum(x * x for x in v))
    if denominator < 1e-8:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v)) / denominator))))


class HandGeometry:
    """Scale/orientation-independent features extracted from 21 landmarks."""

    def __init__(self, sample: HandSample, mirror: bool = True):
        self._palm_sign = (1 if sample.handedness == "Right" else -1) * (1 if mirror else -1)
        self.points = tuple((p.x * sample.width, p.y * sample.height, p.z * sample.width) for p in sample.landmarks)
        p = self.points
        self.scale = (_distance(p[0], p[9]) + _distance(p[5], p[17])) / 2.0
        self.extended = tuple(self._finger(base) for base in (5, 9, 13, 17))
        self.thumb_extended = (
            _angle(p[2], p[3], p[4]) > 145.0
            and _distance(p[4], p[5]) > self.scale * 0.42
            and _distance(p[4], p[0]) > _distance(p[3], p[0]) * 1.04
        )

    def _finger(self, base: int) -> bool:
        p = self.points
        return (
            _angle(p[base], p[base + 1], p[base + 2]) > 150.0
            and _angle(p[base + 1], p[base + 2], p[base + 3]) > 145.0
            and _distance(p[0], p[base + 3]) > _distance(p[0], p[base + 1]) * 1.05
        )

    def distance(self, a: int, b: int) -> float:
        return _distance(self.points[a], self.points[b]) / max(self.scale, 1e-8)

    @property
    def open_for_wave(self) -> bool:
        """An extended hand may have curved fingers and an uncertain thumb.

        This cue belongs only to the temporal window gesture. The precise
        finger features used for clicking and pause are unchanged.
        """
        p = self.points
        relaxed = 0
        for base in (5, 9, 13, 17):
            if (_angle(p[base], p[base + 1], p[base + 2]) > 110.0
                    and _angle(p[base + 1], p[base + 2], p[base + 3]) > 100.0
                    and _distance(p[base], p[base + 3]) > self.scale * 0.55
                    and _distance(p[0], p[base + 3]) > _distance(p[0], p[base]) * 1.15):
                relaxed += 1
        return relaxed >= 3

    @property
    def palm_facing_camera(self) -> bool:
        p = self.points
        u = tuple(a - b for a, b in zip(p[9], p[0]))
        v = tuple(a - b for a, b in zip(p[17], p[5]))
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        norm = math.sqrt(sum(x * x for x in cross))
        # The signed normal distinguishes a palm from its back. Handedness is
        # anatomical; capture has already applied the configured display mirror.
        return norm > 1e-8 and self._palm_sign * cross[2] / norm > 0.55


@dataclass
class _WaveSequence:
    anchor_x: float
    anchor_y: float
    scale: float
    started: float | None = None
    last_turn: float | None = None
    direction: int = 0
    traversals: int = 0


@dataclass(frozen=True)
class _WaveResult:
    open_pose: bool = False
    consumed: bool = False
    toggled: bool = False
    progress: float = 0.0
    state: str = "PUNTERO"


class _WindowWave:
    """Four alternating sweeps, automatically rearmed after a short cooldown."""

    GAP_TOLERANCE = 0.15
    MIN_TURN_INTERVAL = 0.08
    REQUIRED_TRAVERSALS = 4
    COOLDOWN_SECONDS = 0.30

    def __init__(self):
        self.sequence = None
        self.last_open = None
        self.cooldown_until = 0.0

    def cancel(self) -> None:
        self.sequence = None
        self.last_open = None
        # Tracking loss or a UI pause cannot bypass the brief anti-repeat delay.

    def _result(self, open_pose=False) -> _WaveResult:
        count = self.sequence.traversals if self.sequence else 0
        return _WaveResult(open_pose, count >= 2, False, count / self.REQUIRED_TRAVERSALS,
                           f"ONDA {count}/{self.REQUIRED_TRAVERSALS}" if count else "PUNTERO")

    def observe(self, geometry: HandGeometry | None, now: float, settings: Settings,
                *, pinching: bool = False) -> _WaveResult:
        if geometry is None:
            if self.last_open is None or now - self.last_open > self.GAP_TOLERANCE + 1e-6:
                self.sequence = None
            return self._result()

        open_pose = geometry.open_for_wave and not pinching
        if not open_pose:
            if pinching or self.last_open is None or now - self.last_open > self.GAP_TOLERANCE + 1e-6:
                self.sequence = None
            # Pinches keep their working mouse semantics immediately; they are
            # never consumed by an old window-wave candidate or cooldown.
            return _WaveResult() if pinching else self._result()

        if self.last_open is not None and now - self.last_open > self.GAP_TOLERANCE + 1e-6:
            self.sequence = None
        self.last_open = now
        if now < self.cooldown_until:
            # Do not count residual motion toward the next complete sequence.
            # The open hand controls the cursor normally throughout this delay.
            self.sequence = None
            return self._result(True)

        # MCP centroid is less sensitive to individual finger bends than a tip.
        x = sum(geometry.points[i][0] for i in (5, 9, 13, 17)) / 4.0
        y = sum(geometry.points[i][1] for i in (5, 9, 13, 17)) / 4.0
        current = self.sequence
        if (current is None
                or (current.started is not None and now - current.started > settings.wave_window)
                or abs(y - current.anchor_y) > current.scale * 0.9
                or not 0.55 <= geometry.scale / current.scale <= 1.8):
            self.sequence = _WaveSequence(x, y, geometry.scale)
            return self._result(True)

        dx = x - current.anchor_x
        direction = 1 if dx > 0 else -1
        amplitude = max(12.0, settings.wave_amplitude * current.scale)
        if current.started is None and abs(dx) >= max(3.0, amplitude * 0.2):
            current.started = now
        if current.direction and direction == current.direction:
            current.anchor_x = x
        elif abs(dx) >= amplitude:
            if current.last_turn is not None and now - current.last_turn < self.MIN_TURN_INTERVAL:
                # Large, nearly instantaneous alternating landmark jumps are
                # noise, not a deliberate physical waving motion.
                self.sequence = _WaveSequence(x, y, geometry.scale)
                return self._result(True)
            current.last_turn = now
            current.traversals += 1
            current.anchor_x = x
            current.direction = direction
        if current.traversals >= self.REQUIRED_TRAVERSALS:
            self.sequence = None
            self.cooldown_until = now + self.COOLDOWN_SECONDS
            return _WaveResult(True, False, True, 1.0, "VENTANA CAMBIADA")
        return self._result(True)


class GestureEngine:
    MAX_SAMPLE_AGE = 0.35

    def __init__(self, settings: Settings):
        self.settings = settings
        self.paused = settings.start_paused
        self._left_down = False
        self._last_timestamp = None
        self._last_output = EngineOutput()
        self._window_wave = _WindowWave()
        self._clear_gestures()

    def _clear_gestures(self) -> None:
        self._candidate = ""
        self._candidate_since = 0.0
        self._pause_latched = False
        self._right_latched = False
        self._left_rearm_required = False
        self._menu_rearm_required = False
        self._pinch_since = None
        self._volume_y = None
        self._menu_open = False
        self._menu_origin = None
        self._menu_level = "PRINCIPAL"
        self._menu_selected = -1
        self._menu_since = 0.0
        self._menu_wait_neutral = False

    def _release(self) -> list[ActionEvent]:
        events = [ActionEvent("release_left")] if self._left_down else []
        self._left_down = False
        self._pinch_since = None
        return events

    def reset(self, *, preserve_wave: bool = False) -> EngineOutput:
        # A tracking interruption is not proof that a held pose was released.
        # Preserve one-shot latches until a later reliable sample shows release.
        pause_latched, right_latched = self._pause_latched, self._right_latched
        left_blocked = self._left_rearm_required or self._pinch_since is not None
        menu_blocked = self._menu_rearm_required or self._menu_open
        events = self._release()
        self._clear_gestures()
        self._pause_latched, self._right_latched = pause_latched, right_latched
        if not preserve_wave:
            self._window_wave.cancel()
        self._left_rearm_required, self._menu_rearm_required = left_blocked, menu_blocked
        self._last_timestamp = None
        return self._output("PAUSADO" if self.paused else "SIN MANO", events)

    def set_paused(self, paused: bool) -> EngineOutput:
        changed = self.paused != bool(paused)
        self.paused = bool(paused)
        result = self.reset()
        events = list(result.events)
        if changed:
            events.append(ActionEvent("pause_changed", self.paused))
        return self._output("PAUSADO" if self.paused else "LISTO", events)

    def _output(self, state: str, events=(), pointer=None, progress: float = 0.0) -> EngineOutput:
        self._last_output = EngineOutput(
            state=state, events=tuple(events), pointer=pointer,
            progress=max(0.0, min(1.0, progress)), menu_level=self._menu_level,
            menu_selected=self._menu_selected if self._menu_open else -1,
        )
        return self._last_output

    def _hold(self, candidate: str, now: float, duration: float) -> float:
        if self._candidate != candidate:
            self._candidate, self._candidate_since = candidate, now
        return min(1.0, (now - self._candidate_since) / duration)

    def _close_menu(self) -> None:
        self._menu_open = False
        self._menu_origin = None
        self._menu_level = "PRINCIPAL"
        self._menu_selected = -1
        self._menu_wait_neutral = False

    def _valid(self, sample: HandSample, now: float) -> bool:
        return (
            len(sample.landmarks) == 21 and sample.width > 0 and sample.height > 0
            and math.isfinite(sample.confidence) and sample.confidence >= self.settings.tracking_confidence
            and math.isfinite(sample.timestamp) and 0.0 <= now - sample.timestamp <= self.MAX_SAMPLE_AGE
            and all(math.isfinite(v) for p in sample.landmarks for v in (p.x, p.y, p.z))
        )

    def _menu(self, geometry: HandGeometry, now: float, events: list[ActionEvent]) -> EngineOutput:
        progress = self._hold("MENU", now, self.settings.menu_hold)
        if not self._menu_open:
            if progress < 1.0:
                return self._output("PREPARANDO MENU", events, progress=progress)
            self._menu_open = True
            self._menu_origin = geometry.points[4]
        x, y, _ = geometry.points[4]
        ox, oy, _ = self._menu_origin
        dx, dy = (x - ox) / geometry.scale, (y - oy) / geometry.scale
        radius = math.hypot(dx, dy)
        if radius < 0.45:
            self._menu_wait_neutral = False
            self._menu_selected = -1
            return self._output("MENU", events)
        if self._menu_wait_neutral or radius < 0.65:
            self._menu_selected = -1
            return self._output("MENU", events)
        selected = int(((math.degrees(math.atan2(dy, dx)) + 22.5) % 360.0) // 45.0)
        if self._menu_selected != selected:
            self._menu_selected, self._menu_since = selected, now
        progress = (now - self._menu_since) / self.settings.selection_hold
        if progress >= 1.0:
            label = MENUS[self._menu_level][selected]
            if label in MENUS:
                self._menu_level = label
            elif label == "VOLVER":
                self._menu_level = "PRINCIPAL"
            else:
                events.append(ActionEvent("command", label))
            self._menu_wait_neutral = True
            self._menu_selected = -1
            progress = 0.0
        return self._output("MENU", events, progress=progress)

    def update(self, sample: HandSample | None, now: float | None = None) -> EngineOutput:
        now = time.monotonic() if now is None else now
        if not math.isfinite(now):
            return self.reset()
        if sample is None or not self._valid(sample, now):
            self._window_wave.observe(None, now, self.settings)
            return self.reset(preserve_wave=True)
        if self._last_timestamp is not None and sample.timestamp <= self._last_timestamp:
            if sample.timestamp < self._last_timestamp:
                return self.reset()
            # Re-reading a frame must not advance holds or repeat desktop input.
            return self._output(self._last_output.state, progress=self._last_output.progress)
        events = []
        if self._last_timestamp is not None and sample.timestamp - self._last_timestamp > self.MAX_SAMPLE_AGE:
            events.extend(self.reset().events)
        self._last_timestamp = sample.timestamp
        geometry = HandGeometry(sample, mirror=self.settings.mirror)
        if geometry.scale < 5.0:
            self._window_wave.observe(None, now, self.settings)
            return self.reset(preserve_wave=True)
        s = self.settings
        index, middle, ring, little = geometry.extended
        left_distance, right_distance, volume_distance = (geometry.distance(4, i) for i in (8, 12, 16))
        if left_distance >= s.pinch_open:
            self._left_rearm_required = False
            # Mouse semantics are physical: opening releases the held button
            # before the new hand pose can take another gesture's priority.
            if self._pinch_since is not None or self._left_down:
                events.extend(self._release())
        if right_distance >= s.pinch_open:
            self._right_latched = False
        pinching = (min(left_distance, right_distance, volume_distance) < s.pinch_close
                    or self._pinch_since is not None
                    or (self._volume_y is not None and volume_distance < s.pinch_open)
                    or (self._right_latched and right_distance < s.pinch_open))
        wave = self._window_wave.observe(geometry, now, s, pinching=pinching)
        if wave.toggled:
            events.append(ActionEvent("toggle_window"))
        if wave.consumed or wave.open_pose:
            if wave.open_pose:
                # A reliably open hand is a real release of victory, even
                # though window gestures are also recognized while paused.
                self._pause_latched = False
            events.extend(self._release())
            self._candidate = ""
            self._close_menu()
            self._volume_y = None
            if wave.consumed:
                return self._output(wave.state, events, progress=wave.progress)
            if self.paused:
                state = "PAUSADO" if not wave.progress else "PAUSADO · " + wave.state
                return self._output(state, events, progress=wave.progress)
            return self._output(wave.state, events, (sample.landmarks[8].x, sample.landmarks[8].y), wave.progress)
        victory = (index and middle and not ring and not little
                   and geometry.distance(8, 12) > 0.5 and left_distance > 0.5
                   and min(right_distance, volume_distance) >= s.pinch_open)
        if victory:
            events.extend(self._release())
            self._close_menu()
            self._volume_y = None
            progress = self._hold("PAUSA", now, s.pause_hold)
            if progress >= 1.0 and not self._pause_latched:
                self.paused = not self.paused
                self._pause_latched = True
                events.append(ActionEvent("pause_changed", self.paused))
            return self._output("PAUSADO" if self.paused else "GESTO PAUSA", events, progress=progress)
        self._pause_latched = False
        if self.paused:
            self._candidate = ""
            return self._output("PAUSADO", events)

        thumb_only = geometry.thumb_extended and not any(geometry.extended) and min(left_distance, right_distance, volume_distance) > s.pinch_open
        if thumb_only:
            events.extend(self._release())
            self._volume_y = None
            if self._menu_rearm_required:
                return self._output("SOLTAR GESTO", events)
            return self._menu(geometry, now, events)
        self._menu_rearm_required = False
        if self._menu_open or self._candidate == "MENU":
            self._close_menu()
            self._candidate = ""

        # A retained left pinch owns its gesture until the hysteresis opens it.
        distances = {"PINZA": left_distance, "CLIC DERECHO": right_distance, "VOLUMEN": volume_distance}
        if self._pinch_since is not None:
            mode = "PINZA"
        elif self._volume_y is not None and volume_distance < s.pinch_open:
            mode = "VOLUMEN"
        elif self._right_latched and right_distance < s.pinch_open:
            mode = "CLIC DERECHO"
        else:
            nearest = min(distances, key=distances.get)
            mode = nearest if distances[nearest] < s.pinch_close else ""
        if mode != "VOLUMEN":
            self._volume_y = None
        if mode:
            self._candidate = ""
            if mode == "PINZA":
                if self._left_rearm_required:
                    return self._output("SOLTAR GESTO", events)
                if self._pinch_since is None:
                    self._pinch_since = now
                if not self._left_down:
                    self._left_down = True
                    events.append(ActionEvent("press_left"))
                # drag_hold affects only the label; it never delays mouse-down.
                state = "ARRASTRE" if now - self._pinch_since >= s.drag_hold else "PINZA"
                return self._output(state, events, (sample.landmarks[8].x, sample.landmarks[8].y))
            events.extend(self._release())
            if mode == "CLIC DERECHO":
                if not self._right_latched:
                    self._right_latched = True
                    events.append(ActionEvent("click_right"))
            else:
                current_y = geometry.points[16][1]
                if self._volume_y is not None:
                    movement = (self._volume_y - current_y) / geometry.scale
                    if abs(movement) >= 0.025:
                        # Relative movement: a stationary pinched hand never repeats.
                        events.append(ActionEvent("volume_delta", max(-0.25, min(0.25, movement * s.volume_sensitivity))))
                        self._volume_y = current_y
                else:
                    self._volume_y = current_y
            pointer = (sample.landmarks[8].x, sample.landmarks[8].y) if mode == "CLIC DERECHO" else None
            return self._output(mode, events, pointer)

        # Scrolling belongs exclusively to the auxiliary hand's L gesture in
        # 3.0. Former straight/bent two-finger scroll poses are ordinary pointer
        # poses here, so they cannot scroll accidentally or suspend navigation.
        self._candidate = ""
        # The legacy cursor always used landmark 8. Other fingers need not form
        # an index-only pose; only the exclusive modes above suspend navigation.
        return self._output("PUNTERO", events, (sample.landmarks[8].x, sample.landmarks[8].y))
