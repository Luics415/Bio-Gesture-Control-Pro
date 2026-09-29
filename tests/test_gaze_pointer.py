"""Ocular stabilization and P comparison without cameras or desktop input."""

from dataclasses import replace
import math
import os
import random
import statistics
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from biogesture.coordinates import RectMonitor, ScreenMapper
from biogesture.desktop import DesktopApp
from biogesture.gaze_pointer import GazePointerFilter, GazePointerMapper
from biogesture.gaze_ui import CalibrationCollector, GazeCalibrationDialog
from biogesture.settings import Settings
from tests.test_gaze_ui import bare_dialog, failed_accuracy_collector, observation


def test_stabilizer_uses_the_reduced_tremor_profile():
    assert GazePointerFilter.MIN_CUTOFF == pytest.approx(.22)
    assert GazePointerFilter.BETA == pytest.approx(4.)


@pytest.mark.parametrize("fps", [15, 24, 30, 60])
def test_fixation_reduces_synthetic_jitter_without_changing_mean(fps):
    rng = random.Random(415)
    raw = [(.5 + rng.gauss(0, .02), .5 + rng.gauss(0, .02)) for _ in range(fps * 20)]
    smoother = GazePointerFilter()
    filtered = [smoother(*point, index / fps) for index, point in enumerate(raw)]
    for axis in (0, 1):
        source = [point[axis] for point in raw[fps:]]
        actual = [point[axis] for point in filtered[fps:]]
        assert statistics.pstdev(actual) < .65 * statistics.pstdev(source)
        assert abs(statistics.mean(actual) - statistics.mean(source)) < .002


@pytest.mark.parametrize("fps", [15, 24, 30, 60])
def test_confirmed_step_reaches_ninety_percent_within_150_ms(fps):
    smoother = GazePointerFilter()
    for frame in range(fps):
        smoother(.2, .2, frame / fps)
    samples = [(index / fps, smoother(.8, .8, 1 + index / fps)) for index in range(fps)]
    assert samples[0][1] == (.2, .2)  # One-frame guard, not an uncontrolled jump.
    time_to_target = next(elapsed for elapsed, point in samples if point[0] >= .74)
    assert time_to_target <= .15
    assert samples[-1][1] == pytest.approx((.8, .8), abs=.005)


def test_one_frame_spike_never_reaches_pointer():
    smoother = GazePointerFilter()
    assert smoother(.5, .5, 1) == (.5, .5)
    assert smoother(.98, .02, 1.04) == (.5, .5)
    assert smoother(.5, .5, 1.08) == (.5, .5)


def test_guard_cannot_wait_more_than_one_fresh_frame_on_continuing_motion():
    smoother = GazePointerFilter()
    smoother(.2, .2, 1)
    assert smoother(.5, .5, 1.04) == (.2, .2)
    result = smoother(.8, .8, 1.08)
    assert result[0] > .7 and result[1] > .7


def test_duplicate_polls_and_out_of_order_frames_do_not_advance_filter():
    smoother = GazePointerFilter()
    smoother(.2, .2, 1)
    first = smoother(.8, .8, 1.04)
    for _ in range(20):
        assert smoother(.8, .8, 1.04) == first
        assert smoother(.6, .6, 1.02) == first
    assert smoother.timestamp == 1.04
    assert smoother(.8, .8, 1.08)[0] > .7


def test_reset_and_capture_gap_drop_old_filter_and_pending_shift():
    smoother = GazePointerFilter()
    smoother(.2, .2, 1)
    smoother(.8, .8, 1.04)
    smoother.reset()
    assert smoother.timestamp is None
    assert smoother(.9, .1, 1.08) == (.9, .1)
    assert smoother(.1, .9, 1.5) == (.1, .9)


@pytest.mark.parametrize("bad", [(math.nan, .5, 1), (.5, math.inf, 1), (.5, .5, math.nan),
                                 (True, .5, 1), (.5, .5, True), (-.1, .5, 1), (1.1, .5, 1)])
def test_invalid_inputs_reset_then_reject(bad):
    smoother = GazePointerFilter()
    smoother(.2, .2, .5)
    with pytest.raises(ValueError):
        smoother(*bad)
    assert smoother.timestamp is None
    assert smoother(.8, .8, 1.1) == (.8, .8)


def test_mapper_matches_normalized_filter_across_monitor_sizes_and_negative_origins():
    monitors = [RectMonitor("small", "Small", -800, -600, 800, 600),
                RectMonitor("large", "Large", 0, 0, 3840, 2160)]
    reference = GazePointerFilter()
    mappers = [GazePointerMapper(monitor) for monitor in monitors]
    for index, point in enumerate([(.5, .5), (.51, .49), (.8, .2), (.8, .2), (.79, .21)]):
        timestamp = index * .04
        normalized = reference(*point, timestamp)
        for mapper in mappers:
            result = mapper.map(*point, timestamp)
            m = mapper.monitor
            assert result == (m.left + round(normalized[0] * (m.width - 1)),
                              m.top + round(normalized[1] * (m.height - 1)))


def test_first_mapping_reaches_actual_edges_not_an_index_active_rectangle():
    monitor = RectMonitor("left", "Left", -1920, -100, 1920, 1080)
    mapper = GazePointerMapper(monitor)
    assert mapper.map(0, 0, 1) == (-1920, -100)
    mapper.reset()
    assert mapper.map(1, 1, 2) == (-1, 979)


def test_desktop_eye_mapper_does_not_inherit_any_index_calibration_or_smoothing():
    monitor = RectMonitor("main", "Main", 0, 0, 1920, 1080)
    standard = Settings(cursor_mode="eyes")
    unusual = replace(standard, min_cutoff=20., filter_beta=.5, invert_x=True, invert_y=True,
                      active_left=.2, active_right=.7, active_top=.1, active_bottom=.8)
    results = []
    for settings in (standard, unusual):
        app = DesktopApp.__new__(DesktopApp)
        app.settings, app.monitors = settings, [monitor]
        app.mapper = ScreenMapper(settings, monitor)
        index_mapper = app.mapper
        app._reset_gaze_session()
        assert app.mapper is index_mapper and app.mapper.settings is settings
        assert isinstance(app._gaze_mapper, GazePointerMapper)
        results.append([app._gaze_mapper.map(*point, i * .04)
                        for i, point in enumerate([(.5, .5), (.52, .48), (.8, .2), (.8, .2)])])
    assert results[0] == results[1]


def test_index_only_session_never_creates_gaze_mapper():
    app = DesktopApp.__new__(DesktopApp)
    app.settings = Settings(cursor_mode="index")
    app._reset_gaze_session()
    assert not hasattr(app, "_gaze_mapper")
    assert app._gaze_session is None


def test_pause_and_resume_reset_ocular_output_without_changing_hand_mapper():
    app = DesktopApp.__new__(DesktopApp)
    app.settings = Settings(cursor_mode="eyes")
    app._gaze_mapper = GazePointerMapper(RectMonitor("m", "M", 0, 0, 1920, 1080))
    app.engine = Mock()
    app.actions = Mock()
    app.auxiliary_engine = Mock()
    app.mapper = Mock()
    app._update_tray_state = Mock()
    for paused in (True, False):
        app._gaze_mapper.map(.5, .5, 1)
        app.pause(paused)
        assert app._gaze_mapper.filter.timestamp is None
    assert app.mapper.reset.call_count == 2  # Original hand reset still runs.


def probe_dialog(monkeypatch):
    dialog = bare_dialog()
    dialog.collector, _ = failed_accuracy_collector()
    dialog.canvas = Mock()
    dialog._probe = True
    dialog._probe_stabilized = True
    predictor = Mock()
    monkeypatch.setattr("biogesture.gaze_ui.diagnostic_prediction", predictor)
    return dialog, predictor


def paint_probe(dialog, predictor, point, stamp):
    dialog._live_observation = observation(stamp)
    dialog._clock.return_value = stamp
    predictor.return_value = {"raw": point, "bounded": point, "reason": ""}
    dialog.canvas.reset_mock()
    dialog._paint_probe_marker()
    args = dialog.canvas.create_line.call_args_list[0].args
    return ((args[0] + 10) / (dialog.monitor.width - 1), args[1] / (dialog.monitor.height - 1))


def test_probe_stabilized_uses_same_filter_as_cursor_and_original_stays_available(monkeypatch):
    dialog, predictor = probe_dialog(monkeypatch)
    reference = GazePointerFilter()
    before = dialog.collector.calibration.report
    for index, point in enumerate([(.5, .5), (.52, .48), (.8, .2), (.8, .2)]):
        timestamp = 100 + index * .04
        result = paint_probe(dialog, predictor, point, timestamp)
        assert result == pytest.approx(reference(*point, timestamp))
    last_stamp = dialog._probe_filter.timestamp
    dialog.toggle_probe_filter()
    assert not dialog._probe_stabilized
    assert dialog._probe_filter.timestamp == last_stamp  # F changes only which is drawn.
    assert paint_probe(dialog, predictor, (.7, .3), 100.16) == pytest.approx((.7, .3))
    dialog._on_success.assert_not_called()
    assert dialog.collector.calibration.report is before and not dialog.collector.calibration.ready


def test_probe_duplicates_do_not_accumulate_smoothing_and_invalid_frame_resets(monkeypatch):
    dialog, predictor = probe_dialog(monkeypatch)
    paint_probe(dialog, predictor, (.5, .5), 100)
    expected = paint_probe(dialog, predictor, (.8, .2), 100.04)
    for _ in range(10):
        assert paint_probe(dialog, predictor, (.8, .2), 100.04) == expected
    assert dialog._probe_filter.timestamp == 100.04
    dialog._live_observation = None
    dialog.canvas.reset_mock()
    dialog._paint_probe_marker()
    dialog.canvas.create_line.assert_not_called()
    assert dialog._probe_filter.timestamp is None
    assert paint_probe(dialog, predictor, (.8, .2), 100.08) == pytest.approx((.8, .2))


def test_probe_filter_toggle_unavailable_during_collection_or_outside_probe():
    dialog = bare_dialog()
    dialog._probe_stabilized = True
    dialog.toggle_probe_filter()
    assert dialog._probe_stabilized
    dialog.collector.start(10)
    dialog._probe = True
    dialog.toggle_probe_filter()
    assert dialog._probe_stabilized


def test_peripheral_training_collects_more_actual_time_but_validation_keeps_raw_duration():
    from biogesture.gaze_precision import PeripheralGazeCalibration
    from tests.test_gaze_precision_diagnostics import precision_observed

    collector = CalibrationCollector(PeripheralGazeCalibration)
    collector.start(10)
    assert collector.required_collection_seconds == 1.2
    for index in range(31):
        stamp = round(10 + index * .05, 6)
        collector.update(precision_observed(stamp, collector.target), stamp)
    assert collector.point_index == 0  # .8 seconds useful is no longer enough.
    for index in range(31, 39):
        stamp = round(10 + index * .05, 6)
        collector.update(precision_observed(stamp, collector.target), stamp)
    assert collector.point_index == 1
    assert collector.capture_points[0]["useful_seconds"] == pytest.approx(1.2)
    collector.phase, collector.point_index = "validation", 0
    assert collector.required_collection_seconds == .8


def test_peripheral_timeout_reports_required_training_duration():
    from biogesture.gaze_precision import PeripheralGazeCalibration

    collector = CalibrationCollector(PeripheralGazeCalibration)
    collector.start(10)
    collector.update(None, 30)
    assert collector.phase == "error"
    assert "1.2 s útiles" in collector.message


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Tk real optativo sin cámara ni entrada")
@pytest.mark.parametrize("size", [(800, 600), (1920, 1080)])
def test_peripheral_targets_do_not_overlap_status_or_controls(size):
    import tkinter as tk

    width, height = size
    root = tk.Tk()
    root.withdraw()
    dialog = GazeCalibrationDialog(root, RectMonitor("test", "Test", 0, 0, width, height),
                                   lambda: None, Mock(), Mock())
    try:
        dialog.collector.start(10)
        # Test every peripheral target independent of the selected engine.
        targets = tuple((x, y) for x in (.04, .5, .96) for y in (.04, .96)) + ((.04, .5), (.96, .5))
        dialog.collector.calibration = SimpleNamespace(training_targets=targets)
        for index, target in enumerate(targets):
            dialog.collector.point_index = index
            dialog._painted = None
            dialog._paint()
            root.update_idletasks()
            assert not dialog._buttons.winfo_ismapped()
            assert not dialog._diagnostic_buttons.winfo_ismapped()
            x, y = target[0] * (width - 1), target[1] * (height - 1)
            for item in dialog.canvas.find_all():
                if dialog.canvas.type(item) != "text":
                    continue
                left, top, right, bottom = dialog.canvas.bbox(item)
                assert right < x - 17 or left > x + 17 or bottom < y - 17 or top > y + 17
        dialog.collector, _ = failed_accuracy_collector()
        dialog._paint()
        dialog.toggle_probe()
        root.update_idletasks()
        assert dialog.filter_button.winfo_ismapped()
        for bar in (dialog._buttons, dialog._diagnostic_buttons):
            assert bar.winfo_x() >= 0
            assert bar.winfo_x() + bar.winfo_width() <= width
        dialog.filter_button.invoke()
        assert not dialog._probe_stabilized
        assert dialog.window.bind("<KeyPress-f>") and dialog.window.bind("<KeyPress-F>")
    finally:
        dialog.destroy()
        root.destroy()
