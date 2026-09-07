"""Window-wave replays with imperfect anatomy, timing and tracking gaps."""

import math
import unittest
from dataclasses import replace

from biogesture.gestures import GestureEngine, HandGeometry
from biogesture.models import Landmark
from biogesture.settings import Settings
from tests.test_gestures import hand


def relaxed_hand(timestamp, dx=0, *, handedness="Right", reflect=False, bent_little=True):
    sample = hand("palm", timestamp, dx=dx, handedness=handedness)
    points = list(sample.landmarks)
    for base in (5, 9, 13, 17):
        mcp = points[base]
        points[base + 1] = Landmark(mcp.x, mcp.y - 35 / sample.height)
        points[base + 2] = Landmark(mcp.x + 18 / sample.width, mcp.y - 57 / sample.height)
        points[base + 3] = Landmark(mcp.x + 30 / sample.width, mcp.y - 70 / sample.height)
    # The thumb is not reliably extended; one other finger may be fully folded.
    points[1:5] = hand("pointer", timestamp, dx=dx).landmarks[1:5]
    if bent_little:
        points[17:] = hand("fist", timestamp, dx=dx).landmarks[17:]
    if reflect:
        points = [replace(p, x=1 - p.x, z=-p.z) for p in points]
    return replace(sample, landmarks=tuple(points))


def wave_x(fraction, amplitude=60):
    if fraction <= 1 / 4:
        return amplitude * fraction * 4
    if fraction <= 2 / 4:
        return amplitude - 2 * amplitude * (fraction - 1 / 4) * 4
    if fraction <= 3 / 4:
        return -amplitude + 2 * amplitude * (fraction - 2 / 4) * 4
    return amplitude - 2 * amplitude * (fraction - 3 / 4) * 4


class WindowWaveTests(unittest.TestCase):
    def setUp(self):
        self.engine = GestureEngine(Settings(start_paused=False))

    @staticmethod
    def events(outputs):
        return [event for output in outputs for event in output.events]

    def replay(self, fps=30, duration=1.2, start=10, factory=relaxed_hand, interruptions=None):
        outputs = []
        frames = round(duration * fps)
        for frame in range(frames + 1):
            timestamp = start + frame / fps
            dx = wave_x(frame / frames)
            sample = factory(timestamp, dx)
            if interruptions:
                sample = interruptions(frame, timestamp, sample)
            outputs.append(self.engine.update(sample, timestamp))
        return outputs

    def test_relaxed_open_hand_does_not_need_perfect_joints_or_thumb(self):
        geometry = HandGeometry(relaxed_hand(10))
        self.assertFalse(any(geometry.extended))
        self.assertFalse(geometry.thumb_extended)
        self.assertTrue(geometry.open_for_wave)

    def test_four_sweeps_work_at_15_and_30_fps_regardless_of_label_or_mirror(self):
        for fps in (15, 30):
            for handedness in ("Right", "Left"):
                for mirror in (True, False):
                    for reflected in (True, False):
                        self.engine = GestureEngine(Settings(start_paused=False, mirror=mirror))
                        def factory(timestamp, dx):
                            return relaxed_hand(timestamp, dx, handedness=handedness, reflect=reflected)
                        outputs = self.replay(fps=fps, factory=factory)
                        self.assertEqual([event.kind for event in self.events(outputs)], ["toggle_window"],
                                         (fps, handedness, mirror, reflected))

    def test_pause_allows_only_window_toggle_without_mouse_or_keyboard(self):
        for fps in (15, 30):
            self.engine = GestureEngine(Settings(start_paused=True))
            outputs = self.replay(fps=fps)
            self.assertEqual([event.kind for event in self.events(outputs)], ["toggle_window"])
            self.assertTrue(all(output.pointer is None for output in outputs))
            self.assertTrue(self.engine.paused)

    def test_progress_shows_first_sweep_reversal_and_completion(self):
        outputs = self.replay()
        self.assertTrue(any(output.progress == 1 / 4 and output.pointer is not None for output in outputs))
        for count in (2, 3):
            self.assertTrue(any(output.progress == count / 4 and output.pointer is None for output in outputs))
        completed = [output for output in outputs if output.state == "VENTANA CAMBIADA"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].progress, 1)
        self.assertIsNotNone(completed[0].pointer)

    def test_short_tracking_or_pose_gaps_preserve_the_sequence(self):
        for fps in (15, 30):
            for missing in (False, True):
                self.engine = GestureEngine(Settings(start_paused=False))
                bad_frames = {9} if fps == 15 else {18, 19, 20}
                def interrupt(frame, timestamp, sample):
                    if frame not in bad_frames:
                        return sample
                    return None if missing else hand("fist", timestamp)
                outputs = self.replay(fps=fps, interruptions=interrupt)
                self.assertEqual([event.kind for event in self.events(outputs)], ["toggle_window"], (fps, missing))

    def test_long_tracking_gap_cannot_connect_two_incomplete_waves(self):
        outputs = []
        for timestamp, dx in ((10, 0), (10.1, 60), (10.2, -60)):
            outputs.append(self.engine.update(relaxed_hand(timestamp, dx), timestamp))
        outputs.append(self.engine.update(None, 10.3))
        outputs.append(self.engine.update(None, 10.4))
        outputs.append(self.engine.update(relaxed_hand(10.5, 60), 10.5))
        self.assertNotIn("toggle_window", [event.kind for event in self.events(outputs)])
        self.assertIsNotNone(outputs[-1].pointer)

    def test_supported_motion_speeds_and_expired_attempt(self):
        for duration in (.65, 1.2, 1.8):
            self.engine = GestureEngine(Settings(start_paused=False))
            outputs = self.replay(duration=duration)
            self.assertEqual([event.kind for event in self.events(outputs)], ["toggle_window"], duration)
        self.engine = GestureEngine(Settings(start_paused=False))
        self.assertFalse(self.events(self.replay(duration=4.2)))

    def test_jitter_and_unrealistically_fast_landmark_jumps_do_not_toggle(self):
        for fast_jumps in (False, True):
            self.engine = GestureEngine(Settings(start_paused=False))
            outputs = []
            for frame in range(61):
                timestamp = 10 + frame / 30
                dx = 60 * (-1) ** frame if fast_jumps else 7 * math.sin(frame * 1.8)
                outputs.append(self.engine.update(relaxed_hand(timestamp, dx), timestamp))
            self.assertNotIn("toggle_window", [event.kind for event in self.events(outputs)])

    def test_pointing_or_pinching_while_waving_cannot_toggle_window(self):
        for pose in ("pointer", "pinch", "right", "volume"):
            self.engine = GestureEngine(Settings(start_paused=False))
            outputs = self.replay(factory=lambda timestamp, dx: hand(pose, timestamp, dx=dx))
            kinds = [event.kind for event in self.events(outputs)]
            self.assertNotIn("toggle_window", kinds, pose)
            if pose == "pinch":
                self.assertEqual(kinds, ["press_left"])
            elif pose == "right":
                self.assertEqual(kinds, ["click_right"])

    def test_a_pinch_immediately_interrupts_an_incomplete_wave(self):
        outputs = []
        for timestamp, dx in ((10, 0), (10.1, 60), (10.2, -60)):
            outputs.append(self.engine.update(relaxed_hand(timestamp, dx), timestamp))
        outputs.append(self.engine.update(hand("pinch", 10.25), 10.25))
        self.assertEqual(outputs[-1].events[0].kind, "press_left")
        self.assertIsNotNone(outputs[-1].pointer)
        outputs.append(self.engine.update(hand("pointer", 10.3), 10.3))
        self.assertEqual(outputs[-1].events[0].kind, "release_left")
        self.assertNotIn("toggle_window", [event.kind for event in self.events(outputs)])

    def test_two_complete_waves_rearm_without_closing_or_removing_the_hand(self):
        for fps in (15, 30):
            for paused in (False, True):
                self.engine = GestureEngine(Settings(start_paused=paused))
                first = self.replay(fps=fps, duration=1.2)
                self.assertEqual([event.kind for event in self.events(first)], ["toggle_window"])
                held = self.engine.update(relaxed_hand(11.25, -60), 11.25)
                self.assertFalse(held.events)
                if not paused:
                    self.assertIsNotNone(held.pointer)
                repeated = self.replay(fps=fps, duration=1.2, start=11.3)
                self.assertEqual([event.kind for event in self.events(repeated)], ["toggle_window"])
                if paused:
                    self.assertTrue(all(output.pointer is None for output in first + [held] + repeated))

    def test_cooldown_motion_does_not_count_toward_the_next_four_sweeps(self):
        for timestamp, dx in ((10, 0), (10.15, 60), (10.3, -60), (10.45, 60), (10.6, -60)):
            output = self.engine.update(relaxed_hand(timestamp, dx), timestamp)
        self.assertEqual([event.kind for event in output.events], ["toggle_window"])
        for timestamp, dx in ((10.67, 60), (10.74, -60), (10.81, 60), (10.88, -60)):
            output = self.engine.update(relaxed_hand(timestamp, dx), timestamp)
            self.assertFalse(output.events)
            self.assertIsNotNone(output.pointer)
            self.assertEqual(output.progress, 0)
        for timestamp, dx in ((10.93, 0), (11.03, 60), (11.13, -60), (11.23, 60)):
            output = self.engine.update(relaxed_hand(timestamp, dx), timestamp)
            self.assertFalse(output.events)
        output = self.engine.update(relaxed_hand(11.33, -60), 11.33)
        self.assertEqual([event.kind for event in output.events], ["toggle_window"])
        self.assertIsNotNone(output.pointer)

    def test_stationary_open_hand_after_toggle_never_repeats_or_freezes_cursor(self):
        first = self.replay()
        self.assertEqual([event.kind for event in self.events(first)], ["toggle_window"])
        for frame in range(1, 121):
            timestamp = 11.2 + frame / 30
            sample = relaxed_hand(timestamp, -60)
            output = self.engine.update(sample, timestamp)
            self.assertFalse(output.events)
            self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y))

    def test_pinches_keep_immediate_mouse_semantics_during_window_cooldown(self):
        self.replay()
        closed = self.engine.update(hand("pinch", 11.23), 11.23)
        opened = self.engine.update(hand("pointer", 11.25), 11.25)
        right = self.engine.update(hand("right", 11.27), 11.27)
        self.assertEqual([event.kind for event in self.events([closed, opened, right])],
                         ["press_left", "release_left", "click_right"])
        self.assertTrue(all(output.pointer is not None for output in (closed, opened, right)))


if __name__ == "__main__":
    unittest.main()
