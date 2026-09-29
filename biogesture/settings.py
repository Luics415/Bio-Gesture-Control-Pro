"""Validated settings, atomic persistence and application data paths."""

import json
import logging
import math
import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path


def data_directory() -> Path:
    override = os.environ.get("BIOGESTURE_DATA_DIR")
    return Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BioGestureControlPro"


@dataclass
class Settings:
    schema_version: int = 3
    camera_index: int = 0
    capture_width: int = 640
    capture_height: int = 480
    capture_fps: int = 30
    detection_fps: int = 30
    mirror: bool = True
    detection_confidence: float = 0.65
    tracking_confidence: float = 0.65
    pinch_close: float = 0.25
    pinch_open: float = 0.36
    drag_hold: float = 0.35
    pause_hold: float = 2.0
    menu_hold: float = 0.8
    selection_hold: float = 1.0
    scroll_hold: float = 0.7
    scroll_rate: float = 6.0
    wave_amplitude: float = 0.50
    wave_window: float = 2.2
    volume_sensitivity: float = 1.5
    min_cutoff: float = 1.8
    filter_beta: float = 0.03
    active_left: float = 0.12
    active_top: float = 0.12
    active_right: float = 0.88
    active_bottom: float = 0.88
    invert_x: bool = False
    invert_y: bool = False
    monitor_id: str = "primary"
    opacity: float = 0.85
    fixed_window: bool = False
    start_paused: bool = True
    show_landmarks: bool = False
    profile: str = "Global"
    auxiliary_enabled: bool = True
    cursor_mode: str = "index"
    gaze_engine: str = "precision-openvino-v2"
    performance_mode: str = "optimal"
    auxiliary_scroll_dead_zone: float = 0.12
    auxiliary_scroll_sensitivity: float = 1.0

    def runtime_settings(self) -> "Settings":
        """Return the always-full-quality runtime profile.

        ``saving`` remains readable for compatibility with old settings files,
        but is no longer a selectable or effective runtime mode.
        """
        self.validate()
        return replace(self, performance_mode="optimal")

    def validate(self) -> "Settings":
        for f in fields(self):
            default = getattr(Settings(), f.name)
            value = getattr(self, f.name)
            expected = type(default)
            if expected is float:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f"Valor inválido: {f.name}")
            elif type(value) is not expected:
                raise ValueError(f"Tipo inválido: {f.name}")
        bounds = {
            "camera_index": (0, 16), "capture_width": (320, 1920), "capture_height": (240, 1080),
            "capture_fps": (10, 60), "detection_fps": (5, 60),
            "detection_confidence": (0.4, 0.95), "tracking_confidence": (0.4, 0.95),
            "pinch_close": (0.08, 0.5), "pinch_open": (0.12, 0.8), "drag_hold": (0.2, 1.5),
            "pause_hold": (1.0, 4.0), "menu_hold": (0.4, 2.0), "selection_hold": (0.5, 3.0),
            "scroll_hold": (0.3, 2.0), "scroll_rate": (1.0, 20.0), "wave_amplitude": (0.3, 2.0),
            "wave_window": (0.6, 3.0), "volume_sensitivity": (0.3, 4.0),
            "min_cutoff": (0.5, 8.0), "filter_beta": (0.0, 0.2), "opacity": (0.4, 1.0),
            "active_left": (0.0, 0.8), "active_top": (0.0, 0.8),
            "active_right": (0.2, 1.0), "active_bottom": (0.2, 1.0),
            "auxiliary_scroll_dead_zone": (0.03, 0.6), "auxiliary_scroll_sensitivity": (0.2, 3.0),
        }
        for key, (low, high) in bounds.items():
            if not low <= getattr(self, key) <= high:
                raise ValueError(f"{key}: debe estar entre {low} y {high}")
        if self.pinch_open <= self.pinch_close:
            raise ValueError("La apertura de pinza debe superar el cierre")
        if self.active_right - self.active_left < 0.2 or self.active_bottom - self.active_top < 0.2:
            raise ValueError("El área de control debe medir al menos 20% por eje")
        if self.profile not in ("Global", "VS Code", "Navegador", "Multimedia"):
            raise ValueError("Perfil inválido")
        if self.cursor_mode not in ("index", "eyes"):
            raise ValueError("Control de cursor inválido")
        if self.gaze_engine not in ("precision-openvino-v2", "precision-openvino-v1", "legacy-ridge-v1"):
            raise ValueError("Motor ocular inválido")
        if self.performance_mode not in ("optimal", "saving"):
            raise ValueError("Modo de rendimiento inválido")
        if self.schema_version != 3:
            raise ValueError("Formato de configuración no compatible")
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or data_directory() / "settings.json"
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Se esperaba un objeto de configuración")
            # Schema 1 selected Right/Left as a role. Roles now belong to a
            # session track; retain calibration and every unrelated preference.
            if raw.get("schema_version", 1) == 1 and type(raw.get("schema_version", 1)) is int:
                raw = dict(raw)
                raw["schema_version"] = 2
                raw.pop("dominant_hand", None)
            if raw.get("schema_version") == 2 and type(raw.get("schema_version")) is int:
                raw = dict(raw)
                # Upgrade only the original pair of defaults; preserve tuned
                # wave settings and all cursor/click/calibration preferences.
                if raw.get("wave_amplitude", 0.65) == 0.65 and raw.get("wave_window", 1.6) == 1.6:
                    raw["wave_amplitude"], raw["wave_window"] = 0.50, 2.2
                raw["schema_version"] = 3
            # The former saver option is retired. Keep old files loadable but
            # normalize them to the single full-quality runtime profile.
            if raw.get("performance_mode") == "saving":
                raw["performance_mode"] = "optimal"
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in raw.items() if k in known}).validate()
        except (OSError, ValueError, TypeError):
            logging.exception("No se pudo cargar %s; se usan valores predeterminados", path)
            return cls()

    def save(self, path: Path | None = None) -> None:
        self.validate()
        path = path or data_directory() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
