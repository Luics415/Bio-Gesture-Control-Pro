import math
import unittest

from biogesture.coordinates import OneEuroFilter, RectMonitor, ScreenMapper, fit_video
from biogesture.settings import Settings


class CoordinatesTests(unittest.TestCase):
    def test_calibrated_corners_are_exact_and_clamped(self):
        settings = Settings()
        for width, height in ((1366, 768), (1920, 1080), (3840, 2160)):
            mapper = ScreenMapper(settings, RectMonitor("1", "Panel", 0, 0, width, height, True))
            self.assertEqual(mapper.map(settings.active_left, settings.active_top, 1), (0, 0))
            mapper.reset()
            self.assertEqual(mapper.map(settings.active_right, settings.active_bottom, 2), (width - 1, height - 1))
            mapper.reset()
            self.assertEqual(mapper.map(5, -5, 3), (width - 1, 0))

    def test_negative_monitor_origins_and_virtual_desktop(self):
        mapper = ScreenMapper(Settings(), RectMonitor("left", "Left", -2560, -500, 2560, 1440))
        self.assertEqual(mapper.map(.12, .12, 0), (-2560, -500))
        mapper.reset()
        self.assertEqual(mapper.map(.88, .88, 1), (-1, 939))
        mapper = ScreenMapper(Settings(), RectMonitor("all", "All", -2560, -500, 4480, 1580))
        self.assertEqual(mapper.map(.88, .88, 0), (1919, 1079))

    def test_explicit_inversion_does_not_repeat_capture_mirroring(self):
        monitor = RectMonitor("1", "Panel", 0, 0, 1001, 1001)
        a = ScreenMapper(Settings(mirror=True), monitor)
        b = ScreenMapper(Settings(mirror=False), monitor)
        self.assertEqual(a.map(.2, .3, 0), b.map(.2, .3, 0))
        inverted = ScreenMapper(Settings(invert_x=True, invert_y=True), monitor)
        self.assertEqual(inverted.map(.12, .88, 0), (1000, 0))

    def test_filter_initializes_at_hand_and_resets_after_tracking_gap(self):
        smoother = OneEuroFilter()
        self.assertEqual(smoother(1500, 0), 1500)
        self.assertLess(smoother(1700, .03), 1700)
        self.assertEqual(smoother(-500, 1), -500)
        smoother.reset()
        self.assertEqual(smoother(400, 1.1), 400)

    def test_filter_reduces_jitter_and_responds_to_motion(self):
        smoother = OneEuroFilter()
        smoother(500, 0)
        errors = [abs(smoother(500 + 4 * (-1) ** i, i / 30) - 500) for i in range(1, 31)]
        self.assertLess(sum(errors) / len(errors), 2.0)
        previous = smoother(650, 31 / 30)
        self.assertGreater(previous, 610)
        self.assertLess(previous, 650)

    def test_filter_is_time_based_across_frame_rates(self):
        endpoints = []
        for fps in (15, 30, 60):
            smoother = OneEuroFilter()
            points = [smoother(100 + 400 * i / fps, i / fps) for i in range(fps + 1)]
            endpoints.append(points[-1])
        self.assertLess(max(endpoints) - min(endpoints), 5)

    def test_adaptive_filter_has_less_ramp_delay_than_legacy_fixed_blend(self):
        # Both see the identical physical-pixel trajectory. The legacy /5 blend
        # gives a frame-rate-dependent delay, especially at 15 FPS.
        for fps in (15, 30, 60):
            smoother = OneEuroFilter(min_cutoff=1.8, beta=.03)
            legacy = 100.0
            adaptive = smoother(legacy, 0)
            for frame in range(1, fps + 1):
                target = 100 + 400 * frame / fps
                legacy += (target - legacy) / 5
                adaptive = smoother(target, frame / fps)
            self.assertLess(abs(500 - adaptive), abs(500 - legacy) * .4, fps)
            self.assertLess(abs(500 - adaptive), 8, fps)

    def test_screen_mapper_filter_uses_physical_pixel_velocity(self):
        monitor = RectMonitor("1", "Panel", -1920, 0, 1920, 1080)
        settings = Settings()
        mapper = ScreenMapper(settings, monitor)
        expected_x = OneEuroFilter(settings.min_cutoff, settings.filter_beta)
        for frame in range(31):
            timestamp = frame / 30
            camera_x = settings.active_left + .5 * frame / 30
            calibrated = (camera_x - settings.active_left) / (settings.active_right - settings.active_left)
            expected = round(expected_x(monitor.left + calibrated * (monitor.width - 1), timestamp))
            actual, _ = mapper.map(camera_x, .5, timestamp)
            self.assertEqual(actual, expected)

    def test_nonmonotonic_time_does_not_divide_or_jump(self):
        smoother = OneEuroFilter()
        self.assertEqual(smoother(50, 1), 50)
        self.assertEqual(smoother(500, 1), 50)
        self.assertEqual(smoother(500, .5), 50)

    def test_nonfinite_coordinates_are_rejected(self):
        mapper = ScreenMapper(Settings(), RectMonitor("1", "Panel", 0, 0, 1920, 1080))
        for x, y, t in ((math.nan, .5, 1), (.5, math.inf, 1), (.5, .5, math.nan)):
            with self.assertRaises(ValueError):
                mapper.map(x, y, t)

    def test_letterboxing_preserves_aspect_and_bounds(self):
        for source in ((1920, 1080), (640, 480), (480, 640)):
            left, top, width, height = fit_video(*source, 550, 330)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(left + width, 550)
            self.assertLessEqual(top + height, 330)
            self.assertAlmostEqual(width / height, source[0] / source[1], delta=.006)


if __name__ == "__main__":
    unittest.main()
