"""Calibration collection and dialog lifecycle, without a camera or OS input."""

from dataclasses import replace
import os
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from biogesture.coordinates import RectMonitor
from biogesture.gaze import CALIBRATION_TARGETS, CalibrationReport, GazeObservation
from biogesture.gaze_ui import (CalibrationCollector, GazeCalibrationDialog,
                                WIZARD_VALIDATION_TARGETS, position_calibration_window)


def observation(timestamp, target=(.5, .5)):
    x, y = ((coordinate - .5) * .3 for coordinate in target)
    return GazeObservation(timestamp, (x, y, x, y, 0.0, .375, .30, 0.0, .5, .4), True, "")


def finish_point(collector, now, *, observed_target=None):
    original = collector.phase, collector.point_index
    for _ in range(100):
        now = round(now + .05, 6)
        collector.update(observation(now, observed_target or collector.target), now)
        if (collector.phase, collector.point_index) != original:
            return now
    raise AssertionError("El punto no terminó con observaciones válidas")


def finish_training(collector):
    now = 10
    collector.start(now)
    for _ in range(9):
        now = finish_point(collector, now)
    return now


def test_exactly_nine_training_and_five_independent_validation_points():
    assert len(set(CALIBRATION_TARGETS)) == 9
    assert len(set(WIZARD_VALIDATION_TARGETS)) == 5
    assert not set(CALIBRATION_TARGETS) & set(WIZARD_VALIDATION_TARGETS)
    for coordinates in (CALIBRATION_TARGETS, WIZARD_VALIDATION_TARGETS):
        assert max(x for x, _ in coordinates) - min(x for x, _ in coordinates) >= .3
        assert max(y for _, y in coordinates) - min(y for _, y in coordinates) >= .3


def test_no_collection_before_explicit_start():
    collector = CalibrationCollector()
    collector.update(observation(10), 10)
    assert collector.phase == "idle"
    assert collector.target is None
    assert collector.calibration is None


def test_settling_uses_capture_time_not_poll_time():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(7):
        stamp = 10 + frame * .1
        collector.update(observation(stamp), stamp)
    collector.update(observation(10.699), 10.8)
    assert not collector._samples
    collector.update(observation(10.7), 10.8)
    assert len(collector._samples) == 1


def test_eight_fast_samples_do_not_bypass_collection_duration():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(78):
        now = 10 + frame * .01
        collector.update(observation(now, collector.target), now)
    assert len(collector._samples) >= collector.MIN_SAMPLES
    assert collector.point_index == 0
    assert collector.calibration.sample_count == 0


def test_sparse_frames_do_not_form_a_continuous_capture():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(30):
        now = 10 + frame * .3
        collector.update(observation(now), now)
    assert collector.point_index == 0
    assert not collector._samples


def test_repeated_recent_frames_do_not_count_twice_and_stale_ends_segment():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(8):
        now = 10 + frame * .1
        collector.update(observation(now), now)
    sample = observation(10.7)
    for now in (10.75, 10.8, 10.85, 10.9):
        collector.update(sample, now)
    assert len(collector._samples) == 1
    collector.update(sample, 10.96)
    assert len(collector._samples) == 1
    assert collector._point_since is None
    assert collector._segment_last is None
    assert collector._useful_seconds == 0


@pytest.mark.parametrize("invalid", [
    None, object(), GazeObservation(10.8), observation(10), observation(11),
    replace(observation(10.8), timestamp=float("nan")),
    replace(observation(10.8), timestamp=True),
    replace(observation(10.8), features=(float("nan"),) * 10),
    replace(observation(10.8), features=()),
    replace(observation(10.8), features=observation(10.8).features[:6] + (0.0, 0.0, .5, .4)),
])
def test_invalid_observations_pause_current_segment_without_counting_gaps(invalid):
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(8):
        now = 10 + frame * .1
        collector.update(observation(now), now)
    assert collector._samples
    collector.update(invalid, 10.8)
    assert len(collector._samples) == 1
    assert collector._point_since is None
    assert collector._segment_last is None
    assert collector._useful_seconds == 0
    assert collector.phase == "calibration"
    assert collector.point_index == 0


def test_blink_between_short_good_segments_can_complete_only_the_same_point():
    collector = CalibrationCollector()
    collector.start(10)
    target = collector.target
    for frame in range(12):
        stamp = round(10 + frame * .1, 6)
        collector.update(observation(stamp, target), stamp)
    first_count = len(collector._samples)
    first_duration = collector._useful_seconds
    assert first_duration == pytest.approx(.4)
    invalid = GazeObservation(11.2, reason="Parpadeo")
    for now in (11.2, 11.23, 11.26):
        collector.update(invalid, now)
    assert collector._drop_reasons["Parpadeo"] == 1
    assert len(collector._samples) == first_count
    # The time spent blinking and settling is not counted as usable gaze time.
    for stamp in (11.3, 11.4, 11.5, 11.6):
        collector.update(observation(stamp, target), stamp)
    assert collector._useful_seconds == pytest.approx(first_duration)
    assert collector.point_index == 0
    for stamp in (11.7, 11.8, 11.9, 12.0):
        collector.update(observation(stamp, target), stamp)
    assert collector.point_index == 1
    assert collector.calibration.sample_count >= 8
    assert not collector._samples
    assert collector._useful_seconds == 0
    assert all(sample_target == target for _, sample_target in collector.calibration._samples)


def test_invalid_frames_and_large_gap_never_supply_collection_time():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(12):
        stamp = round(10 + frame * .1, 6)
        collector.update(observation(stamp), stamp)
    duration = collector._useful_seconds
    for stamp in (12, 13, 14):
        collector.update(GazeObservation(stamp, reason="Parpadeo"), stamp)
    for stamp in (14.1, 14.2, 14.3, 14.4):
        collector.update(observation(stamp), stamp)
    assert collector._useful_seconds == pytest.approx(duration)
    assert collector.point_index == 0


def test_point_timeout_reports_stage_target_counts_reason_and_allows_only_point_retry():
    collector = CalibrationCollector()
    collector.start(10)
    now = finish_point(collector, 10)
    count = collector.calibration.sample_count
    collector.update(GazeObservation(now + .1, reason="Parpadeo u ojos ocultos"), now + .1)
    collector.update(None, now + collector.POINT_TIMEOUT_SECONDS)
    assert collector.phase == "error"
    assert "punto 2 de 9" in collector.message
    assert "muestras" in collector.message and "s útiles" in collector.message
    assert "Parpadeo u ojos ocultos" in collector.message
    assert collector.can_retry_point
    assert collector.retry_point(now + 30)
    assert collector.phase == "calibration" and collector.point_index == 1
    assert collector.calibration.sample_count == count
    assert not collector._samples
    assert collector._useful_seconds == 0


def test_focus_loss_discards_current_point_partial_data_without_reusing_off_target_gaze():
    collector = CalibrationCollector()
    collector.start(10)
    for frame in range(12):
        stamp = round(10 + frame * .1, 6)
        collector.update(observation(stamp), stamp)
    assert collector._samples
    collector.interrupt("Vuelve a esta ventana")
    assert not collector._samples
    assert collector._useful_seconds == 0
    assert collector.point_index == 0


def test_accuracy_failure_explains_numeric_errors_without_enabling_point_retry():
    collector = CalibrationCollector()
    collector.start(10)
    report = CalibrationReport(mean_error=.052, max_error=.123, reason="Precisión insuficiente")
    collector._accuracy_failure(report)
    assert collector.phase == "error"
    assert "5.2%" in collector.message and "12.3%" in collector.message
    assert "no de aciertos" in collector.message
    assert "no los dibujos" in collector.message
    assert not collector.can_retry_point
    assert not collector.retry_point(20)
    assert not collector.calibration.ready


def test_terminal_diagnostics_are_logged_once_without_eye_features(caplog):
    collector = CalibrationCollector()
    collector.start(10)
    with caplog.at_level("INFO"):
        collector.fail("Precisión insuficiente")
        collector.fail("Precisión insuficiente")
    entries = [record.message for record in caplog.records if "Calibración ocular:" in record.message]
    assert len(entries) == 1
    assert "error_medio=" in entries[0] and "peor_objetivo=" in entries[0]
    assert "features" not in entries[0] and "rgb" not in entries[0]


def test_blink_preserves_completed_points_and_restarts_current_settle():
    collector = CalibrationCollector()
    collector.start(10)
    now = finish_point(collector, 10)
    assert collector.point_index == 1
    trained_count = collector.calibration.sample_count
    collector.update(None, now + .1)
    assert collector.point_index == 1
    assert collector.calibration.sample_count == trained_count
    collector.update(observation(now + .2, collector.target), now + .2)
    assert collector._point_since == now + .2
    assert not collector._samples


def test_out_of_order_sample_cannot_be_reused_for_a_target():
    collector = CalibrationCollector()
    collector.start(10)
    collector.update(observation(10.1), 10.1)
    collector.update(observation(10.05), 10.2)
    assert collector._point_since is None
    collector.update(observation(10.1), 10.2)
    assert collector._point_since is None


def test_invalid_new_packet_blocks_older_valid_replay_after_blink():
    collector = CalibrationCollector()
    collector.start(10)
    collector.update(observation(10.1), 10.1)
    collector.update(GazeObservation(10.2, reason="Parpadeo"), 10.2)
    collector.update(observation(10.15), 10.22)
    assert collector._point_since is None
    assert not collector._samples
    assert collector._last_timestamp == 10.2


def test_missing_eye_model_shows_explicit_failure_instead_of_waiting_forever():
    collector = CalibrationCollector()
    collector.start(10)
    reason = "Ojos no disponibles: falta el modelo facial; revisa la instalación"
    collector.update(GazeObservation(10.1, reason=reason), 10.1)
    assert collector.phase == "error"
    assert collector.message == reason
    assert not collector.calibration.ready


def test_temporary_occlusion_reason_is_visible_only_in_calibration_dialog_state():
    collector = CalibrationCollector()
    collector.start(10)
    collector.update(GazeObservation(10.1, reason="Parpadeo u ojos ocultos"), 10.1)
    assert collector.phase == "calibration"
    assert "Parpadeo u ojos ocultos" in collector.message
    collector.update(observation(10.1), 10.2)
    assert collector._point_since is None


@pytest.mark.parametrize("now", [float("nan"), float("inf"), True, "11", 9])
def test_bad_or_regressing_clock_cannot_complete_calibration(now):
    collector = CalibrationCollector()
    collector.start(10)
    collector.update(observation(10), now)
    assert collector.phase == "error"
    assert not collector.calibration.ready


def test_training_alone_never_enables_predictions():
    collector = CalibrationCollector()
    now = finish_training(collector)
    assert collector.phase == "validation"
    assert collector.calibration.fitted
    assert not collector.calibration.ready
    assert collector.calibration.predict(observation(now, (.3, .3))) is None


def test_degenerate_eye_motion_fails_before_validation():
    collector = CalibrationCollector()
    collector.start(10)
    now = 10
    for _ in range(9):
        now = finish_point(collector, now, observed_target=(.5, .5))
    assert collector.phase == "error"
    assert "variación" in collector.message
    assert not collector.calibration.ready


def test_bad_held_out_accuracy_does_not_pass():
    collector = CalibrationCollector()
    now = finish_training(collector)
    for _ in range(5):
        x, y = collector.target
        now = finish_point(collector, now, observed_target=(x + .15, y))
    assert collector.phase == "error"
    assert not collector.calibration.ready
    assert "Precisión insuficiente" in collector.message


def test_success_requires_all_five_validation_points_and_unique_times():
    collector = CalibrationCollector()
    now = finish_training(collector)
    for _ in range(4):
        now = finish_point(collector, now)
        assert not collector.calibration.ready
    finish_point(collector, now)
    assert collector.phase == "complete"
    assert collector.calibration.ready
    assert collector.calibration.report.accepted
    stamps = [sample.timestamp for sample, _ in collector._validation_samples]
    assert len(stamps) == len(set(stamps))
    assert collector.calibration.report.samples >= 5 * collector.MIN_SAMPLES
    assert "pausa" in collector.message


def test_retry_discards_old_model_and_both_sample_sets():
    collector = CalibrationCollector()
    finish_training(collector)
    old_calibration = collector.calibration
    collector.start(100)
    assert collector.calibration is not old_calibration
    assert collector.calibration.sample_count == 0
    assert not collector._validation_samples
    assert collector.point_index == 0
    assert collector.phase == "calibration"


def test_negative_monitor_position_uses_absolute_native_coordinates_and_size():
    monitor = RectMonitor("left", "Izquierda", -1920, -100, 1920, 1080)
    window = Mock()
    window.winfo_id.return_value = 42
    native = Mock()
    native.GetAncestor.return_value = 84
    native.SetWindowPos.return_value = True
    position_calibration_window(window, monitor, _user32=native)
    native.SetWindowPos.assert_called_once_with(84, None, -1920, -100, 1920, 1080, 0x0014)
    window.geometry.assert_called_once_with("1920x1080")


def test_failed_native_position_is_not_silently_accepted():
    native = Mock()
    native.SetWindowPos.return_value = False
    with pytest.raises(OSError, match="pantalla elegida"):
        position_calibration_window(Mock(), RectMonitor("m", "Monitor", 0, 0, 1920, 1080), _user32=native)


@pytest.mark.parametrize("monitor", [RectMonitor("m", "M", 0, 0, 0, 1080),
                                     RectMonitor("m", "M", .5, 0, 1920, 1080)])
def test_invalid_monitor_rejected_before_window_is_positioned(monitor):
    window = Mock()
    with pytest.raises(ValueError):
        position_calibration_window(window, monitor)
    window.geometry.assert_not_called()


def bare_dialog():
    dialog = GazeCalibrationDialog.__new__(GazeCalibrationDialog)
    dialog.window = Mock()
    dialog.window.winfo_exists.return_value = True
    dialog.window.grab_current.return_value = dialog.window
    dialog.window.focus_displayof.return_value = dialog.window
    dialog.window.winfo_toplevel.return_value = dialog.window
    dialog.window.winfo_rootx.return_value = 0
    dialog.window.winfo_rooty.return_value = 0
    dialog.window.winfo_width.return_value = 1920
    dialog.window.winfo_height.return_value = 1080
    dialog.window.after.return_value = "next-tick"
    dialog.monitor = RectMonitor("m", "Monitor", 0, 0, 1920, 1080)
    dialog._closed = dialog._delivered = False
    dialog._after = "scheduled-tick"
    dialog._on_close, dialog._on_success = Mock(), Mock()
    dialog._latest_observation = Mock(return_value=observation(10.1))
    dialog._clock = Mock(return_value=10.1)
    dialog._paint = Mock()
    dialog.collector = CalibrationCollector()
    return dialog


def test_cancel_destroys_once_cancels_tick_and_never_reports_success():
    dialog = bare_dialog()
    dialog.destroy()
    dialog.destroy()
    dialog.window.after_cancel.assert_called_once_with("scheduled-tick")
    dialog.window.grab_release.assert_called_once()
    dialog.window.destroy.assert_called_once()
    dialog._on_close.assert_called_once_with()
    dialog._on_success.assert_not_called()
    dialog._tick()
    dialog._latest_observation.assert_not_called()


def test_success_callback_hands_off_only_validated_mapping_and_closes_once():
    dialog = bare_dialog()
    now = finish_training(dialog.collector)
    for _ in range(5):
        now = finish_point(dialog.collector, now)
    dialog._tick()
    dialog._tick()
    dialog._on_success.assert_called_once_with(dialog.collector.calibration)
    dialog._on_close.assert_called_once_with()
    dialog.window.after.assert_not_called()


def test_validation_failure_keeps_dialog_open_for_explicit_retry():
    dialog = bare_dialog()
    dialog.collector.start(10)
    dialog.collector.fail("Precisión insuficiente")
    dialog._tick()
    dialog._on_success.assert_not_called()
    dialog._on_close.assert_not_called()
    dialog.window.after.assert_called_once_with(dialog.POLL_MS, dialog._tick)


def test_inactive_wizard_cannot_collect_eyes_looking_at_another_window():
    dialog = bare_dialog()
    dialog.collector.start(10)
    dialog.window.focus_displayof.return_value = None
    dialog._tick()
    dialog._latest_observation.assert_not_called()
    assert dialog.collector._point_since is None
    assert "Vuelve a esta ventana" in dialog.collector.message


def test_changed_monitor_geometry_stops_collection():
    dialog = bare_dialog()
    dialog.collector.start(10)
    dialog.window.winfo_rootx.return_value = -100
    dialog._tick()
    dialog._latest_observation.assert_not_called()
    assert dialog.collector.phase == "error"


def test_latest_camera_reader_error_cannot_produce_a_success_callback():
    dialog = bare_dialog()
    dialog.collector.start(10)
    dialog._latest_observation.side_effect = RuntimeError("camera unavailable")
    dialog._tick()
    dialog._on_success.assert_not_called()
    assert dialog.collector._point_since is None


def test_constructor_binds_escape_and_creates_separate_window(monkeypatch):
    parent, window, canvas = Mock(), Mock(), Mock()
    window.winfo_exists.return_value = True
    window.grab_current.return_value = window
    window_factory = Mock(return_value=window)
    monkeypatch.setattr("biogesture.gaze_ui.tk.Toplevel", window_factory)
    monkeypatch.setattr("biogesture.gaze_ui.tk.Canvas", Mock(return_value=canvas))
    monkeypatch.setattr("biogesture.gaze_ui.tk.Frame", Mock())
    monkeypatch.setattr("biogesture.gaze_ui.compact_button", Mock())
    position = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.position_calibration_window", position)
    success, close, latest = Mock(), Mock(), Mock()
    monitor = RectMonitor("left", "Izquierda", -1920, 0, 1920, 1080)
    dialog = GazeCalibrationDialog(parent, monitor, latest, success, close)
    window_factory.assert_called_once_with(parent)
    position.assert_called_once_with(window, monitor)
    latest.assert_not_called()
    escape = next(args[1] for args, _ in window.bind.call_args_list if args[0] == "<Escape>")
    escape(SimpleNamespace())
    close.assert_called_once_with()
    success.assert_not_called()
    assert dialog._closed


def test_target_draw_uses_monitor_local_coordinates_with_no_camera_overlay():
    dialog = bare_dialog()
    dialog._paint = GazeCalibrationDialog._paint.__get__(dialog)
    dialog._painted = None
    dialog.canvas = Mock()
    dialog.start_button = Mock()
    dialog.monitor = RectMonitor("left", "Izquierda", -1920, -100, 1920, 1080)
    dialog.collector.start(10)
    dialog._paint()
    x, y = CALIBRATION_TARGETS[0]
    x, y = x * 1919, y * 1079
    assert dialog.canvas.create_oval.call_args_list == [
        call(x - 17, y - 17, x + 17, y + 17, outline="#075663", width=2),
        call(x - 4, y - 4, x + 4, y + 4, fill="#17242d", outline=""),
    ]


def test_background_cannot_change_while_target_is_running_and_invalidates_point_only_retry():
    dialog = bare_dialog()
    dialog._palette_name = "neutral"
    dialog.collector.start(10)
    dialog.toggle_background()
    assert dialog._palette_name == "neutral"
    dialog.collector.update(None, 31)
    assert dialog.collector.can_retry_point
    dialog.toggle_background()
    assert dialog._palette_name == "dark"
    assert not dialog.collector.can_retry_point


def test_instruction_screen_explains_head_eyes_hands_and_lens_reflections():
    dialog = bare_dialog()
    dialog._paint = GazeCalibrationDialog._paint.__get__(dialog)
    dialog._painted = None
    dialog.canvas, dialog.start_button = Mock(), Mock()
    dialog._paint()
    texts = " ".join(kwargs["text"] for _, kwargs in dialog.canvas.create_text.call_args_list)
    for instruction in ("SOLO LA MIRADA", "cabeza relativamente estable", "Parpadea normalmente",
                        "No necesitas", "manos", "No sigas los dibujos", "lentes", "Fondo: oscuro"):
        assert instruction in texts


def test_preview_is_not_polled_during_targets_and_cleared_when_stale():
    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog._latest_preview = Mock(return_value=SimpleNamespace(timestamp=9))
    dialog._preview_image = object()
    dialog.collector.start(10)
    dialog._paint_preview()
    dialog._latest_preview.assert_not_called()
    dialog.collector.fail("Reintentar")
    dialog._paint_preview()
    dialog._latest_preview.assert_called_once_with()
    dialog.canvas.delete.assert_called_with("eye_preview")
    assert dialog._preview_image is None


def test_preview_activation_changes_only_once_per_phase_and_is_disabled_on_close():
    dialog = bare_dialog()
    dialog._set_preview_enabled = Mock()
    dialog._preview_enabled = False
    dialog._enable_preview(True)
    dialog._enable_preview(True)
    dialog._enable_preview(False)
    dialog._enable_preview(True)
    dialog.destroy()
    assert dialog._set_preview_enabled.call_args_list == [call(True), call(False), call(True), call(False)]


def test_failed_preview_callback_does_not_prevent_cleanup_or_retain_eye_photo():
    dialog = bare_dialog()
    dialog._preview_image, dialog._preview_stamp = object(), 10
    dialog._preview_enabled = True
    dialog._set_preview_enabled = Mock(side_effect=RuntimeError("preview unavailable"))
    dialog.destroy()
    dialog.window.destroy.assert_called_once_with()
    dialog._on_close.assert_called_once_with()
    assert dialog._preview_image is None and dialog._preview_stamp is None


def test_eye_only_preview_is_enlarged_with_preserved_aspect_ratio_and_never_saved(monkeypatch):
    import numpy as np
    from PIL import Image, ImageTk

    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog._preview_stamp = None
    dialog._latest_preview = Mock(return_value=SimpleNamespace(
        timestamp=10.1, rgb=np.zeros((30, 100, 3), dtype=np.uint8), points=((.2, .3), (.7, .4))))
    photo = Mock(return_value=object())
    save = Mock()
    monkeypatch.setattr(ImageTk, "PhotoImage", photo)
    monkeypatch.setattr(Image.Image, "save", save)
    dialog._paint_preview()
    frame = photo.call_args.args[0]
    assert frame.size == (300, 90)
    dialog.canvas.create_image.assert_called_once()
    save.assert_not_called()
    dialog._paint_preview()
    assert photo.call_count == 1


def failed_accuracy_collector():
    collector = CalibrationCollector()
    now = finish_training(collector)
    for _ in range(5):
        x, y = collector.target
        now = finish_point(collector, now, observed_target=(x + .15, y))
    assert collector.phase == "error" and collector.calibration.fitted
    return collector, now


def test_capture_ledger_keeps_fourteen_unique_points_and_raw_validation_after_failure():
    collector, _ = failed_accuracy_collector()
    assert len(collector.capture_points) == 14
    assert len({(p["phase"], p["point_index"]) for p in collector.capture_points}) == 14
    assert all(p["outcome"] == "complete" for p in collector.capture_points)
    assert all(p["samples"] >= collector.MIN_SAMPLES for p in collector.capture_points)
    assert all(p["useful_seconds"] >= collector.COLLECT_SECONDS - 1e-9 for p in collector.capture_points)
    assert len(collector.validation_samples) > 5 * collector.MIN_SAMPLES
    collector.start(100)
    assert not collector.capture_points and not collector.validation_samples


def test_capture_ledger_merges_point_retry_and_counts_repeated_rejection_only_once():
    collector = CalibrationCollector()
    collector.start(10)
    bad = GazeObservation(10.1, reason="Parpadeo")
    for now in (10.1, 10.15, 10.2):
        collector.update(bad, now)
    collector.update(None, 30)
    assert collector.capture_points[0]["outcome"] == "timeout"
    assert collector.capture_points[0]["rejected"] == {"Parpadeo": 1}
    assert collector.retry_point(40)
    finish_point(collector, 40)
    assert len(collector.capture_points) == 1
    point = collector.capture_points[0]
    assert point["attempts"] == 2
    assert point["outcome"] == "complete"
    assert point["rejected"] == {"Parpadeo": 1}
    assert point["elapsed_seconds"] >= 21


def test_probe_is_not_available_without_fitted_model_or_during_validation():
    dialog = bare_dialog()
    dialog.toggle_probe()
    assert not getattr(dialog, "_probe", False)
    finish_training(dialog.collector)
    dialog.toggle_probe()
    assert not getattr(dialog, "_probe", False)
    dialog._on_success.assert_not_called()


def test_failed_mapping_probe_only_draws_and_never_completes_or_mutates_calibration():
    dialog = bare_dialog()
    dialog.collector, now = failed_accuracy_collector()
    dialog.canvas = Mock()
    dialog._clock.return_value = now + .1
    dialog._latest_observation.return_value = observation(now + .1, (.3, .3))
    report = dialog.collector.calibration.report
    dialog.toggle_probe()
    assert dialog._probe
    dialog._tick()
    assert dialog.canvas.create_line.call_count == 2
    assert dialog.collector.phase == "error"
    assert dialog.collector.calibration.report is report
    assert not dialog.collector.calibration.ready
    dialog._on_success.assert_not_called()
    dialog._on_close.assert_not_called()
    dialog.escape()
    assert not dialog._probe
    dialog._on_close.assert_not_called()
    dialog.escape()
    dialog._on_close.assert_called_once_with()


@pytest.mark.parametrize("bad", [None, observation(0), GazeObservation(10.1, reason="Parpadeo")])
def test_probe_removes_old_marker_on_missing_blink_or_stale_frame(bad):
    dialog = bare_dialog()
    dialog.collector, _ = failed_accuracy_collector()
    dialog.canvas = Mock()
    dialog._live_observation = bad
    dialog._paint_probe_marker()
    dialog.canvas.delete.assert_called_once_with("probe_marker")
    dialog.canvas.create_line.assert_not_called()
    dialog._on_success.assert_not_called()


def test_probe_draw_uses_full_monitor_normalized_mapping_without_preview_remapping(monkeypatch):
    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog._live_observation = observation(10.1)
    predictor = Mock(return_value={"raw": (.2, .8), "bounded": (.2, .8), "reason": ""})
    monkeypatch.setattr("biogesture.gaze_ui.diagnostic_prediction", predictor)
    dialog._paint_probe_marker()
    x, y = .2 * 1919, .8 * 1079
    assert dialog.canvas.create_line.call_args_list == [
        call(x - 10, y, x + 10, y, fill="#075663", width=3, tags="probe_marker"),
        call(x, y - 10, x, y + 10, fill="#075663", width=3, tags="probe_marker"),
    ]


def test_diagnostics_and_probe_can_never_export_automatically():
    dialog = bare_dialog()
    dialog.collector, now = failed_accuracy_collector()
    dialog._on_export_diagnostics = Mock(return_value="local.json")
    dialog.canvas = Mock()
    dialog._clock.return_value = now + .1
    dialog._latest_observation.return_value = observation(now + .1)
    dialog.toggle_details()
    dialog._tick()
    dialog.toggle_probe()
    dialog._tick()
    dialog._on_export_diagnostics.assert_not_called()
    dialog._on_success.assert_not_called()


def test_explicit_export_includes_samples_and_does_not_approve_failed_mapping():
    dialog = bare_dialog()
    dialog.collector, _ = failed_accuracy_collector()
    dialog._on_export_diagnostics = Mock(return_value="local.json")
    dialog.export_diagnostics()
    exported = dialog._on_export_diagnostics.call_args.args[0]
    assert exported["capture_points"]
    assert any(sample["phase"] == "validation" for sample in exported["samples"])
    assert "sin imágenes ni envío" in dialog._diagnostic_status
    assert not dialog.collector.calibration.ready
    dialog._on_success.assert_not_called()


def test_export_is_blocked_during_collection_and_handles_filesystem_error():
    dialog = bare_dialog()
    dialog._on_export_diagnostics = Mock(side_effect=OSError("not writable"))
    finish_training(dialog.collector)
    dialog.export_diagnostics()
    dialog._on_export_diagnostics.assert_not_called()
    dialog.collector.fail("stop")
    dialog.export_diagnostics()
    assert "No se pudo guardar" in dialog._diagnostic_status
    assert not dialog.collector.calibration.ready


def test_running_detail_shows_no_estimate_map_eye_preview_or_prediction(monkeypatch):
    dialog = bare_dialog()
    dialog._paint = GazeCalibrationDialog._paint.__get__(dialog)
    dialog.canvas, dialog.start_button = Mock(), Mock()
    dialog._painted = None
    dialog._detail = True
    dialog._latest_preview = Mock()
    prediction = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.diagnostic_prediction", prediction)
    dialog.collector.start(10)
    dialog._tick()
    prediction.assert_not_called()
    dialog._latest_preview.assert_not_called()
    dialog.canvas.create_line.assert_not_called()
    assert dialog.canvas.create_oval.call_count == 2


def test_observation_fps_uses_unique_samples_not_ui_poll_frequency_and_expires():
    dialog = bare_dialog()
    for now in (10.1, 10.15, 10.2):
        dialog._clock.return_value = now
        dialog._read_live()
    assert len(dialog._live_stamps) == 1
    dialog._clock.return_value = 10.3
    dialog._latest_observation.return_value = observation(10.3)
    dialog._read_live()
    assert "5.0/s" in dialog._live_text()
    dialog._clock.return_value = 12
    assert "0.0/s" in dialog._live_text()


def test_optional_telemetry_failure_is_nonfatal():
    dialog = bare_dialog()
    dialog._latest_diagnostics = Mock(side_effect=RuntimeError("worker unavailable"))
    assert dialog._telemetry() == {}
    dialog._on_success.assert_not_called()


def test_export_background_is_acquisition_palette_not_post_failure_view_palette():
    dialog = bare_dialog()
    dialog._palette_name = "neutral"
    dialog.start()
    dialog.collector.fail("failure")
    dialog.toggle_background()
    assert dialog._palette_name == "dark"
    assert dialog.diagnostic_report(include_samples=True)["context"]["background"] == "neutral"
    dialog.start()
    assert dialog.diagnostic_report(include_samples=True)["context"]["background"] == "dark"


def test_result_shows_unavailable_errors_reason_rejected_and_actual_limits():
    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog.collector, _ = failed_accuracy_collector()
    dialog.collector.calibration.report = CalibrationReport(reason="Fuera del rango de postura")
    dialog.collector.calibration.mean_error_limit = .032
    dialog.collector.calibration.max_error_limit = .071
    dialog._paint_results()
    texts = " ".join(kwargs["text"] for _, kwargs in dialog.canvas.create_text.call_args_list)
    assert "inf%" not in texts and "nan%" not in texts
    assert "no disponible" in texts and "Fuera del rango de postura" in texts
    assert "Muestras sin predicción" in texts
    assert "3.2% / 7.1%" in texts


def test_probe_reports_raw_rejected_prediction_without_drawing_marker(monkeypatch):
    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog._live_observation = observation(10.1)
    monkeypatch.setattr("biogesture.gaze_ui.diagnostic_prediction", Mock(return_value={
        "raw": (-.4, .6), "bounded": None, "reason": "Fuera del rango"}))
    dialog._paint_probe_marker()
    dialog.canvas.create_line.assert_not_called()
    text = dialog.canvas.create_text.call_args.kwargs["text"]
    assert "-0.400" in text and "Fuera del rango" in text


def test_detail_compares_training_validation_and_jitter_without_approving():
    dialog = bare_dialog()
    dialog.canvas = Mock()
    dialog.collector, _ = failed_accuracy_collector()
    dialog._paint_technical()
    texts = " ".join(kwargs["text"] for _, kwargs in dialog.canvas.create_text.call_args_list)
    assert "Aprendizaje: error" in texts and "Comprobación: error" in texts and "variación" in texts
    assert not dialog.collector.calibration.ready


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Geometría diagnóstica real optativa de Tk")
@pytest.mark.parametrize("scaling", [1.333, 2.0])
@pytest.mark.parametrize("size", [(800, 600), (1920, 1080)])
def test_real_tk_diagnostic_results_details_and_buttons_fit_without_camera(scaling, size):
    import tkinter as tk

    from biogesture.windows import enable_dpi_awareness

    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", scaling)
    width, height = size
    monitor = RectMonitor("test", "Pantalla de prueba", 0, 0, width, height)
    success, close = Mock(), Mock()
    dialog = None
    try:
        dialog = GazeCalibrationDialog(root, monitor, lambda: None, success, close, clock=lambda: 100,
                                       on_export_diagnostics=lambda payload: "local.json")
        dialog.collector, _ = failed_accuracy_collector()
        dialog._paint()
        root.update_idletasks()
        assert dialog.canvas.find_withtag("diagnostic_map")
        for detailed in (False, True):
            dialog._detail = detailed
            dialog._paint()
            root.update_idletasks()
            for item in dialog.canvas.find_all():
                left, top, right, bottom = dialog.canvas.bbox(item)
                assert 0 <= left < right <= width
                assert 0 <= top < bottom <= height - 75
            for bar in (dialog._buttons, dialog._diagnostic_buttons):
                assert bar.winfo_x() >= 0
                assert bar.winfo_x() + bar.winfo_width() <= width
                assert 0 <= bar.winfo_y() < bar.winfo_y() + bar.winfo_height() <= height
        dialog.toggle_probe()
        root.update_idletasks()
        assert dialog._probe
        dialog.escape()
        assert not dialog._probe and not dialog._closed
        success.assert_not_called()
    finally:
        if dialog is not None:
            dialog.destroy()
        root.destroy()


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Geometría ocular real optativa de Tk")
@pytest.mark.parametrize("scaling", [1.333, 2.0])
@pytest.mark.parametrize("size", [(800, 600), (1920, 1080)])
def test_real_tk_calibration_geometry_targets_and_close_without_input(scaling, size):
    import tkinter as tk

    from biogesture.windows import enable_dpi_awareness

    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", scaling)
    errors = []
    root.report_callback_exception = lambda *error: errors.append(error)
    width, height = size
    monitor = RectMonitor("test", "Pantalla de prueba", 0, 0, width, height)
    success, close, latest = Mock(), Mock(), Mock(return_value=None)
    dialog = None
    try:
        dialog = GazeCalibrationDialog(root, monitor, latest, success, close, clock=lambda: 10.0)
        root.update()
        assert (dialog.window.winfo_rootx(), dialog.window.winfo_rooty()) == (0, 0)
        assert (dialog.window.winfo_width(), dialog.window.winfo_height()) == size
        assert (dialog.canvas.winfo_width(), dialog.canvas.winfo_height()) == size
        assert dialog.window.bind("<Escape>")
        for item in dialog.canvas.find_all():
            left, top, right, bottom = dialog.canvas.bbox(item)
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height
        dialog.collector._accuracy_failure(CalibrationReport(
            mean_error=.052, max_error=.123, worst_target=(.7, .3),
            reason=("Precisión insuficiente: la mirada varió demasiado mientras se mostraba un mismo objetivo. "
                    "Error medio 5.2% y máximo 12.3% (límites 4% y 8%). Mantén la cabeza cómoda y relativamente "
                    "estable; mira el centro del punto hasta que cambie. Comprueba que ambos ojos sean visibles.")))
        dialog._latest_preview = lambda: None
        dialog._paint()
        dialog._paint_preview()
        root.update_idletasks()
        text_items = [item for item in dialog.canvas.find_all() if dialog.canvas.type(item) == "text"]
        error_item = next(item for item in text_items
                          if dialog.canvas.itemcget(item, "text").startswith("Precisión insuficiente"))
        assert dialog.canvas.bbox(error_item)[3] < dialog._preview_y() - 30
        for item in dialog.canvas.find_all():
            left, top, right, bottom = dialog.canvas.bbox(item)
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height
        dialog.start()
        for phase, targets in (("calibration", CALIBRATION_TARGETS),
                               ("validation", WIZARD_VALIDATION_TARGETS)):
            dialog.collector.phase = phase
            for index, target in enumerate(targets):
                dialog.collector.point_index = index
                dialog._paint()
                root.update_idletasks()
                ovals = [item for item in dialog.canvas.find_all() if dialog.canvas.type(item) == "oval"]
                assert len(ovals) == 2
                x, y = target[0] * (width - 1), target[1] * (height - 1)
                assert dialog.canvas.coords(ovals[0]) == pytest.approx((x - 17, y - 17, x + 17, y + 17))
                for item in dialog.canvas.find_all():
                    left, top, right, bottom = dialog.canvas.bbox(item)
                    assert 0 <= left < right <= width
                    assert 0 <= top < bottom <= height
        dialog.destroy()
        root.update()
        assert not dialog.window.winfo_exists()
        close.assert_called_once_with()
        success.assert_not_called()
        assert not errors
    finally:
        if dialog is not None:
            dialog.destroy()
        root.destroy()
