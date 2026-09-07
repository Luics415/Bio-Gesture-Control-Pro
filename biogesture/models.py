"""Dependency-free contracts shared by tracking, gestures and presentation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class HandSample:
    timestamp: float
    landmarks: tuple[Landmark, ...]
    width: int = 640
    height: int = 480
    handedness: str = "Right"
    confidence: float = 1.0


@dataclass(frozen=True)
class ActionEvent:
    kind: str
    value: Any = None


@dataclass(frozen=True)
class EngineOutput:
    state: str = "SIN MANO"
    events: tuple[ActionEvent, ...] = ()
    pointer: tuple[float, float] | None = None
    progress: float = 0.0
    menu_level: str = "PRINCIPAL"
    menu_selected: int = -1


@dataclass(frozen=True)
class TrackingPacket:
    sequence: int
    captured_at: float
    completed_at: float
    rgb: Any = None
    sample: HandSample | None = None
    status: str = "LISTO"
    error: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    auxiliary: HandSample | None = None
