"""3.0 controls must not alter an existing 2.7 user's tuned hand settings."""

from dataclasses import asdict
import json

import pytest

from biogesture.settings import Settings
from biogesture.tracking import TrackingPipeline


def test_old_settings_choose_index_without_losing_preferences(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 3, "capture_width": 1280, "capture_height": 720,
                                "active_left": .2, "pinch_close": .22, "show_landmarks": True}), encoding="utf-8")
    settings = Settings.load(path)
    assert (settings.cursor_mode, settings.performance_mode) == ("index", "optimal")
    assert settings.active_left == .2 and settings.pinch_close == .22 and settings.show_landmarks
    assert settings.capture_width == 1280


@pytest.mark.parametrize("mode", ["index", "eyes"])
def test_optimal_keeps_requested_quality_without_adaptive_downgrading(mode):
    settings = Settings(cursor_mode=mode, capture_width=1280, capture_height=720, capture_fps=60, detection_fps=30)
    runtime = settings.runtime_settings()
    assert runtime is not settings
    assert asdict(runtime) == asdict(settings)


def test_legacy_saving_profile_is_forced_to_full_quality(tmp_path):
    settings = Settings(performance_mode="saving", capture_width=1280, capture_height=720,
                        capture_fps=60, detection_fps=30)
    path = tmp_path / "settings.json"
    settings.save(path)
    pipeline = TrackingPipeline(settings, "hand_landmarker.task")
    assert (pipeline.settings.capture_width, pipeline.settings.capture_height) == (1280, 720)
    assert pipeline.settings.capture_fps == 60 and pipeline.settings.detection_fps == 30
    assert pipeline.settings.performance_mode == "optimal"
    assert Settings.load(path).performance_mode == "optimal"
    assert settings.capture_width == 1280 and settings.capture_fps == 60


@pytest.mark.parametrize("values", [
    {"cursor_mode": "unknown"}, {"performance_mode": "auto"},
    {"auxiliary_scroll_dead_zone": .001}, {"auxiliary_scroll_dead_zone": float("nan")},
    {"auxiliary_scroll_sensitivity": -1}, {"cursor_mode": True},
])
def test_invalid_mode_or_scroll_settings_fail_before_save(values):
    with pytest.raises(ValueError):
        Settings(**values).validate()
