"""Configuration must never apply invalid or partially written control settings."""

import json

import pytest

from biogesture.settings import Settings, data_directory


def test_new_settings_start_with_landmarks_unchecked():
    assert Settings().show_landmarks is False


@pytest.mark.parametrize("schema", [1, 2, 3])
@pytest.mark.parametrize("enabled", [False, True])
def test_existing_landmark_preference_survives_load_migration_and_save(tmp_path, schema, enabled):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"schema_version": schema, "show_landmarks": enabled,
                                  "profile": "Navegador", "opacity": .65}), encoding="utf-8")
    loaded = Settings.load(target)
    assert loaded.show_landmarks is enabled
    assert loaded.profile == "Navegador" and loaded.opacity == .65
    loaded.save(target)
    assert Settings.load(target).show_landmarks is enabled
    assert json.loads(target.read_text(encoding="utf-8"))["show_landmarks"] is enabled


def test_settings_round_trip_retains_calibration_and_profile(tmp_path):
    target = tmp_path / "nested" / "settings.json"
    configured = Settings(monitor_id="monitor-2", active_left=0.2,
                          active_right=0.7, opacity=0.6, profile="VS Code", invert_y=True)
    configured.save(target)
    assert Settings.load(target) == configured
    assert not target.with_suffix(".tmp").exists()


@pytest.mark.parametrize("content", ["{", "[]", '{"pinch_close": 0.5, "pinch_open": 0.2}',
                                     '{"capture_fps": true}', '{"schema_version": 99}'])
def test_invalid_config_falls_back_to_safe_defaults(tmp_path, content):
    target = tmp_path / "settings.json"
    target.write_text(content, encoding="utf-8")
    assert Settings.load(target) == Settings()
    assert Settings.load(target).start_paused
    assert target.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("values", [
    {"pinch_close": 0.4, "pinch_open": 0.3},
    {"active_left": 0.7, "active_right": 0.75},
    {"active_top": 0.8, "active_bottom": 0.5},
    {"detection_confidence": float("nan")},
    {"filter_beta": float("inf")},
    {"capture_width": True},
    {"start_paused": "false"},
    {"schema_version": 1},
    {"profile": "missing"},
])
def test_invalid_settings_cannot_overwrite_previous_file(tmp_path, values):
    target = tmp_path / "settings.json"
    Settings().save(target)
    original = target.read_bytes()
    with pytest.raises(ValueError):
        Settings(**values).save(target)
    assert target.read_bytes() == original


def test_unknown_fields_preserve_supported_configuration(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"profile": "Navegador", "future_setting": 123}), encoding="utf-8")
    assert Settings.load(target).profile == "Navegador"


def test_data_directory_can_be_isolated_for_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOGESTURE_DATA_DIR", str(tmp_path))
    assert data_directory() == tmp_path
    Settings().save()
    assert (tmp_path / "settings.json").is_file()


@pytest.mark.parametrize("old_hand", ["Left", "Right"])
def test_schema_one_migration_drops_fixed_hand_role_but_preserves_preferences(tmp_path, old_hand):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"schema_version": 1, "dominant_hand": old_hand,
                                  "camera_index": 2, "mirror": False, "profile": "VS Code",
                                  "active_left": 0.2, "opacity": 0.6}), encoding="utf-8")
    migrated = Settings.load(target)
    assert migrated.schema_version == 3
    assert not hasattr(migrated, "dominant_hand")
    assert migrated.camera_index == 2
    assert migrated.profile == "VS Code"
    assert migrated.active_left == 0.2
    assert migrated.opacity == 0.6
    assert not migrated.mirror
    migrated.save(target)
    assert "dominant_hand" not in json.loads(target.read_text(encoding="utf-8"))


@pytest.mark.parametrize("schema", [1, 2])
def test_old_wave_defaults_are_updated_without_touching_working_cursor_settings(tmp_path, schema):
    target = tmp_path / "settings.json"
    raw = {"schema_version": schema, "wave_amplitude": 0.65, "wave_window": 1.6,
           "pinch_close": 0.27, "pinch_open": 0.40, "min_cutoff": 3.0,
           "filter_beta": 0.05, "active_left": 0.20, "start_paused": False}
    target.write_text(json.dumps(raw), encoding="utf-8")
    result = Settings.load(target)
    assert result.schema_version == 3
    assert (result.wave_amplitude, result.wave_window) == (0.50, 2.2)
    for key in ("pinch_close", "pinch_open", "min_cutoff", "filter_beta", "active_left", "start_paused"):
        assert getattr(result, key) == raw[key]
    assert json.loads(target.read_text(encoding="utf-8")) == raw


@pytest.mark.parametrize("amplitude,window", [(0.80, 1.6), (0.65, 2.8), (0.8, 2.8)])
def test_user_tuned_wave_settings_survive_migration(tmp_path, amplitude, window):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"schema_version": 2, "wave_amplitude": amplitude,
                                  "wave_window": window}), encoding="utf-8")
    result = Settings.load(target)
    assert (result.wave_amplitude, result.wave_window) == (amplitude, window)


def test_new_schema_keeps_explicit_original_thresholds_if_requested(tmp_path):
    target = tmp_path / "settings.json"
    settings = Settings(wave_amplitude=0.65, wave_window=1.6)
    settings.save(target)
    assert Settings.load(target) == settings
