import math
import unittest
from dataclasses import replace

from biogesture.gestures import GestureEngine, HandGeometry, MENUS
from biogesture.models import HandSample, Landmark
from biogesture.settings import Settings


def hand(pose="pointer", timestamp=10.0, *, dx=0.0, dy=0.0, size=1.0, rotation=0.0,
         handedness="Right", width=640, height=480):
    """Planar synthetic joint chains, transformed before normalized encoding."""
    points = [(0.0, 0.0)] * 21
    points[0:5] = [(0, 0), (-20, -10), (-38, -25), (-30, -43), (-20, -35)]
    extended = {5} if pose in ("pointer", "pinch", "volume") else set()
    if pose in ("victory", "right", "scroll_up"):
        extended = {5, 9}
    if pose == "palm":
        extended = {5, 9, 13, 17}
    for base, x, y in ((5, -32, -50), (9, 0, -60), (13, 24, -55), (17, 48, -45)):
        points[base] = (x, y)
        if base in extended:
            points[base + 1:base + 4] = [(x, y - 35), (x, y - 63), (x, y - 88)]
        else:
            points[base + 1:base + 4] = [(x, y - 30), (x + 9, y - 18), (x, y - 7)]
    if pose in ("thumb", "palm"):
        points[1:5] = [(-22, -14), (-50, -34), (-70, -54), (-87, -73)]
    if pose == "victory":
        for base, sign in ((5, -1), (9, 1)):
            for j in (1, 2, 3):
                x, y = points[base + j]
                points[base + j] = (x + sign * 7 * j, y)
    if pose == "scroll_up":
        points[6:9] = [(-20, -90), (-14, -120), (-8, -147)]
        points[10:13] = [(-4, -100), (-7, -125), (-9, -148)]
    if pose == "scroll_down":
        points[6:9] = [(-30, -80), (-20, -55), (-14, -28)]
        points[10:13] = [(0, -90), (-5, -55), (-10, -28)]
        points[4] = (-58, -22)
    if pose in ("pinch", "right", "volume"):
        tip = {"pinch": 8, "right": 12, "volume": 16}[pose]
        x, y = points[tip]
        points[4] = (x + 3, y + 2)
        points[3] = (x - 12, y + 14)
    angle = math.radians(rotation)
    encoded = []
    for x, y in points:
        tx = (x * math.cos(angle) - y * math.sin(angle)) * size + dx
        ty = (x * math.sin(angle) + y * math.cos(angle)) * size + dy
        encoded.append(Landmark((width / 2 + tx) / width, (height * .75 + ty) / height))
    return HandSample(timestamp, tuple(encoded), width, height, handedness)


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(start_paused=False)
        self.engine = GestureEngine(self.settings)

    def feed(self, pose, start=10.0, duration=1.0, fps=30, **kwargs):
        outputs = []
        for frame in range(round(duration * fps) + 1):
            timestamp = start + frame / fps
            outputs.append(self.engine.update(hand(pose, timestamp, **kwargs), timestamp))
        return outputs

    @staticmethod
    def kinds(outputs):
        return [event.kind for output in outputs for event in output.events]

    def test_geometry_is_rotation_scale_and_aspect_independent(self):
        for pose in ("pointer", "thumb", "palm", "victory", "scroll_up", "pinch"):
            reference = HandGeometry(hand(pose))
            for rotation in (-120, -45, 0, 60, 170):
                for size in (.55, 1.0, 1.75):
                    geometry = HandGeometry(hand(pose, rotation=rotation, size=size, width=1280, height=720))
                    self.assertEqual(geometry.extended, reference.extended, (pose, rotation, size))
                    self.assertEqual(geometry.thumb_extended, reference.thumb_extended)
                    self.assertAlmostEqual(geometry.distance(4, 8), reference.distance(4, 8), places=8)

    def test_geometry_survives_three_dimensional_rotation(self):
        for pose in ("pointer", "thumb", "palm", "victory", "pinch"):
            sample = hand(pose)
            original = HandGeometry(sample)
            for tilt_x, tilt_y in ((30, 25), (-30, -25), (0, 180), (80, 0)):
                ax, ay = math.radians(tilt_x), math.radians(tilt_y)
                transformed = []
                origin = original.points[0]
                for point in original.points:
                    x, y, z = (a - b for a, b in zip(point, origin))
                    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
                    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
                    transformed.append(Landmark((x + origin[0]) / sample.width, (y + origin[1]) / sample.height, z / sample.width))
                geometry = HandGeometry(replace(sample, landmarks=tuple(transformed)))
                self.assertEqual(geometry.extended, original.extended, (pose, tilt_x, tilt_y))
                self.assertEqual(geometry.thumb_extended, original.thumb_extended)
                self.assertAlmostEqual(geometry.distance(4, 8), original.distance(4, 8), places=8)

    def test_palm_normal_distinguishes_backside_handedness_and_mirror(self):
        sample = hand("palm")
        reflected = replace(sample, landmarks=tuple(replace(p, x=1 - p.x, z=-p.z) for p in sample.landmarks))
        self.assertTrue(HandGeometry(sample).palm_facing_camera)
        self.assertFalse(HandGeometry(reflected).palm_facing_camera)
        self.assertTrue(HandGeometry(reflected, mirror=False).palm_facing_camera)
        self.assertTrue(HandGeometry(replace(reflected, handedness="Left")).palm_facing_camera)
        self.assertFalse(HandGeometry(replace(sample, handedness="Left")).palm_facing_camera)

    def test_pointer_follows_index_tip_without_a_special_finger_pose(self):
        for pose in ("pointer", "fist", "palm"):
            self.engine.reset()
            sample = hand(pose)
            output = self.engine.update(sample, sample.timestamp)
            self.assertEqual(output.state, "PUNTERO", pose)
            self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y), pose)

    def test_cursor_source_does_not_remove_existing_primary_hand_commands(self):
        # Gaze fusion owns pointer selection. Changing the source must not
        # silently remove right-click, volume, menu or the victory safety cue.
        for pose in ("pinch", "right", "volume", "thumb", "victory"):
            with self.subTest(pose=pose):
                engines = [GestureEngine(Settings(start_paused=False, cursor_mode=mode))
                           for mode in ("index", "eyes")]
                for frame in range(70):
                    now = 10 + frame / 30
                    sample = hand(pose, now, dy=-min(frame, 15))
                    self.assertEqual(engines[0].update(sample, now), engines[1].update(sample, now))

    def test_eye_mode_retains_four_sweep_window_gesture(self):
        self.engine = GestureEngine(Settings(start_paused=False, cursor_mode="eyes"))
        outputs = []
        for step, dx in enumerate((0, 60, -5, 60, -5)):
            now = 10 + step * .15
            outputs.append(self.engine.update(hand("palm", now, dx=dx), now))
        self.assertEqual(self.kinds(outputs), ["toggle_window"])

    def test_other_extended_fingers_do_not_disable_index_tip_navigation(self):
        sample = hand("palm")
        points = list(sample.landmarks)
        points[1:5] = hand("pointer").landmarks[1:5]
        sample = replace(sample, landmarks=tuple(points))
        output = self.engine.update(sample, sample.timestamp)
        self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y))
        self.assertFalse(output.events)

    def test_short_pinch_presses_immediately_and_releases_once_without_extra_click(self):
        outputs = self.feed("pinch", duration=.2)
        self.assertEqual(self.kinds([outputs[0]]), ["press_left"])
        self.assertEqual(self.kinds(outputs), ["press_left"])
        self.assertEqual(outputs[0].state, "PINZA")
        outputs += self.feed("pointer", start=10.23, duration=.2)
        self.assertEqual(self.kinds(outputs), ["press_left", "release_left"])

    def test_short_left_pinch_releases_when_switching_to_competing_gesture(self):
        for pose in ("right", "volume", "scroll_up", "scroll_down", "palm", "victory", "thumb"):
            self.engine = GestureEngine(self.settings)
            self.feed("pinch", duration=.1)
            output = self.feed(pose, start=10.15, duration=0)[0]
            self.assertEqual(output.events[0].kind, "release_left", pose)
            self.assertNotIn("click_left", self.kinds([output]), pose)

    def test_rapid_close_open_cycles_each_make_one_native_button_pair(self):
        outputs = []
        for timestamp, pose in ((10, "pinch"), (10.08, "pointer"), (10.16, "pinch"), (10.24, "pointer")):
            outputs.append(self.engine.update(hand(pose, timestamp), timestamp))
        self.assertEqual(self.kinds(outputs), ["press_left", "release_left", "press_left", "release_left"])

    def test_drag_does_not_wait_for_drag_label_delay(self):
        self.engine = GestureEngine(Settings(start_paused=False, drag_hold=1.5))
        first_sample = hand("pinch", 10)
        first = self.engine.update(first_sample, 10)
        moved_sample = hand("pinch", 10.05, dx=30, dy=20)
        moved = self.engine.update(moved_sample, 10.05)
        self.assertEqual(self.kinds([first]), ["press_left"])
        self.assertFalse(moved.events)
        self.assertNotEqual(first.pointer, moved.pointer)
        self.assertEqual(moved.pointer, (moved_sample.landmarks[8].x, moved_sample.landmarks[8].y))
        self.assertEqual(moved.state, "PINZA")
        released = self.engine.update(hand("pointer", 10.1, dx=30, dy=20), 10.1)
        self.assertEqual(self.kinds([released]), ["release_left"])

    def test_left_pinch_is_not_stolen_by_the_other_four_extended_fingers(self):
        sample = hand("pinch")
        points = list(sample.landmarks)
        points[9:] = hand("palm").landmarks[9:]
        sample = replace(sample, landmarks=tuple(points))
        self.assertTrue(all(HandGeometry(sample).extended))
        output = self.engine.update(sample, sample.timestamp)
        self.assertEqual(self.kinds([output]), ["press_left"])
        self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y))

    def test_right_pinch_is_not_stolen_by_victory_with_a_separated_index(self):
        sample = hand("victory")
        points = list(sample.landmarks)
        points[4] = replace(points[12], x=points[12].x + .005, y=points[12].y + .005)
        sample = replace(sample, landmarks=tuple(points))
        geometry = HandGeometry(sample)
        self.assertTrue(geometry.extended[0] and geometry.extended[1])
        self.assertGreater(geometry.distance(8, 12), .5)
        output = self.engine.update(sample, sample.timestamp)
        self.assertEqual(self.kinds([output]), ["click_right"])
        self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y))

    def test_right_pinch_keeps_cursor_on_index_without_repeated_clicks(self):
        first = self.engine.update(hand("right", 10), 10)
        moved_sample = hand("right", 10.1, dx=40)
        moved = self.engine.update(moved_sample, 10.1)
        self.assertEqual(self.kinds([first]), ["click_right"])
        self.assertFalse(moved.events)
        self.assertNotEqual(first.pointer, moved.pointer)
        self.assertEqual(moved.pointer, (moved_sample.landmarks[8].x, moved_sample.landmarks[8].y))

    def test_drag_releases_without_extra_click(self):
        outputs = self.feed("pinch", duration=.8)
        self.assertEqual(self.kinds(outputs).count("press_left"), 1)
        self.assertEqual(outputs[-1].state, "ARRASTRE")
        outputs += self.feed("pointer", start=10.85, duration=.2)
        self.assertEqual(self.kinds(outputs).count("release_left"), 1)
        self.assertNotIn("click_left", self.kinds(outputs))

    def test_pinching_hysteresis_does_not_flicker(self):
        self.feed("pinch", duration=.5)
        sample = hand("pinch", 10.55)
        points = list(sample.landmarks)
        scale = HandGeometry(sample).scale
        points[4] = replace(points[8], x=points[8].x + scale * .30 / sample.width)
        output = self.engine.update(replace(sample, landmarks=tuple(points)), 10.55)
        self.assertEqual(output.state, "ARRASTRE")
        self.assertNotIn("release_left", self.kinds([output]))

    def test_priority_gestures_cancel_drag_without_click(self):
        for pose in ("thumb", "palm", "victory"):
            self.engine = GestureEngine(self.settings)
            self.feed("pinch", duration=.5)
            output = self.feed(pose, start=10.55, duration=0)[0]
            self.assertIn("release_left", self.kinds([output]), pose)
            self.assertNotIn("click_left", self.kinds([output]), pose)
            if pose != "palm":
                self.assertIsNone(output.pointer)

    def test_loss_pause_low_confidence_and_stale_release_drag(self):
        for reason in ("loss", "pause", "low", "stale", "gap", "reverse"):
            self.engine = GestureEngine(self.settings)
            self.feed("pinch", duration=.5)
            if reason == "pause":
                output = self.engine.set_paused(True)
            elif reason == "loss":
                output = self.engine.update(None, 10.55)
            elif reason == "low":
                output = self.engine.update(replace(hand("pinch", 10.55), confidence=.2), 10.55)
            elif reason == "stale":
                output = self.engine.update(hand("pinch", 10.5), 11.0)
            elif reason == "reverse":
                output = self.engine.update(hand("pinch", 10.4), 10.55)
            else:
                output = self.engine.update(hand("pointer", 11.0), 11.0)
            self.assertIn("release_left", self.kinds([output]), reason)
            self.assertNotIn("click_left", self.kinds([output]), reason)
            self.assertNotIn("release_left", self.kinds([self.engine.reset()]))

    def test_invalid_landmarks_never_send_actions(self):
        sample = hand("pointer")
        for invalid in (replace(sample, landmarks=()), replace(sample, width=0),
                        replace(sample, confidence=float("nan")),
                        replace(sample, landmarks=(Landmark(float("nan"), 0),) + sample.landmarks[1:])):
            output = self.engine.update(invalid, 10)
            self.assertEqual(output.state, "SIN MANO")
            self.assertFalse(output.events)
            self.assertIsNone(output.pointer)

    def test_duplicate_frames_do_not_advance_a_hold(self):
        sample = hand("pinch")
        first = self.engine.update(sample, 10)
        for timestamp in (10.1, 10.2, 10.3):
            duplicate = self.engine.update(sample, timestamp)
            self.assertFalse(duplicate.events)
            self.assertIsNone(duplicate.pointer)
        self.assertEqual(first.state, "PINZA")

    def test_reacquiring_held_pinch_cannot_restart_drag_until_open(self):
        self.feed("pinch", duration=.5)
        self.engine.update(None, 10.55)
        outputs = self.feed("pinch", start=10.6, duration=1.0)
        self.assertNotIn("press_left", self.kinds(outputs))
        self.assertIsNone(outputs[-1].pointer)
        self.feed("pointer", start=11.65, duration=.1)
        outputs = self.feed("pinch", start=11.8, duration=.5)
        self.assertEqual(self.kinds(outputs).count("press_left"), 1)

    def test_tracking_loss_does_not_rearm_right_click_or_pause(self):
        self.feed("right", duration=.5)
        self.engine.update(None, 10.55)
        outputs = self.feed("right", start=10.6, duration=1.0)
        self.assertNotIn("click_right", self.kinds(outputs))
        self.feed("victory", start=11.65, duration=2.2)
        self.assertTrue(self.engine.paused)
        self.engine.update(None, 13.9)
        outputs = self.feed("victory", start=14, duration=2.2)
        self.assertNotIn("pause_changed", self.kinds(outputs))
        self.assertTrue(self.engine.paused)

    def test_right_click_is_once_until_fingers_release(self):
        outputs = self.feed("right", duration=2.0)
        self.assertEqual(self.kinds(outputs).count("click_right"), 1)
        self.feed("pointer", start=12.05, duration=.1)
        outputs = self.feed("right", start=12.2, duration=.5)
        self.assertEqual(self.kinds(outputs).count("click_right"), 1)

    def test_victory_pauses_and_resumes_once_per_pose(self):
        outputs = self.feed("victory", duration=5.0)
        self.assertEqual(self.kinds(outputs).count("pause_changed"), 1)
        self.assertTrue(self.engine.paused)
        self.assertTrue(all(output.pointer is None for output in outputs))
        self.feed("fist", start=15.05, duration=.1)
        outputs = self.feed("victory", start=15.2, duration=3.0)
        self.assertEqual(self.kinds(outputs).count("pause_changed"), 1)
        self.assertFalse(self.engine.paused)

    def test_victory_requires_continuous_hold(self):
        self.feed("victory", duration=1.5)
        self.feed("pointer", start=11.55, duration=.1)
        outputs = self.feed("victory", start=11.7, duration=1.5)
        self.assertNotIn("pause_changed", self.kinds(outputs))
        self.assertFalse(self.engine.paused)

    def test_open_palm_between_victory_holds_rearms_pause(self):
        self.feed("victory", duration=2.2)
        self.assertTrue(self.engine.paused)
        self.feed("palm", start=12.25, duration=.2)
        outputs = self.feed("victory", start=12.5, duration=2.2)
        self.assertEqual(self.kinds(outputs).count("pause_changed"), 1)
        self.assertFalse(self.engine.paused)

    def test_engine_accepts_either_anatomical_hand_as_pipeline_selected_primary(self):
        for handedness in ("Left", "Right"):
            self.engine = GestureEngine(Settings(start_paused=False))
            self.assertIsNotNone(self.feed("pointer", duration=0, handedness=handedness)[0].pointer)
            output = self.feed("pinch", start=10.1, duration=0, handedness=handedness)[0]
            self.assertEqual(self.kinds([output]), ["press_left"])
            self.engine.reset()
            output = self.feed("right", start=10.2, duration=0, handedness=handedness)[0]
            self.assertEqual(self.kinds([output]), ["click_right"])

    def test_palm_wave_requires_four_real_alternating_sweeps(self):
        outputs = []
        for step, dx in enumerate((0, 60, -5, 60, -5)):
            outputs.append(self.engine.update(hand("palm", 10 + step * .15, dx=dx), 10 + step * .15))
        self.assertNotIn("toggle_window", self.kinds(outputs[:4]))
        self.assertEqual(self.kinds(outputs).count("toggle_window"), 1)
        self.assertIsNotNone(outputs[0].pointer)
        self.assertIsNotNone(outputs[1].pointer)
        self.assertTrue(all(output.pointer is None for output in outputs[2:4]))
        self.assertIsNotNone(outputs[4].pointer)
        self.assertEqual(outputs[4].state, "VENTANA CAMBIADA")

    def test_completed_wave_rearms_with_open_hand_and_uncertain_thumb(self):
        outputs = []
        for step, dx in enumerate((0, 60, -5, 60, -5)):
            outputs.append(self.engine.update(hand("palm", 10 + step * .15, dx=dx), 10 + step * .15))
        self.assertEqual(self.kinds(outputs).count("toggle_window"), 1)
        sample = hand("palm", 10.7)
        points = list(sample.landmarks)
        points[1:5] = hand("pointer", 10.7).landmarks[1:5]
        noisy = self.engine.update(replace(sample, landmarks=tuple(points)), 10.7)
        self.assertIsNotNone(noisy.pointer)
        self.assertFalse(noisy.events)
        cooldown = self.engine.update(hand("palm", 10.8, dx=60), 10.8)
        self.assertIsNotNone(cooldown.pointer)
        self.assertFalse(cooldown.events)
        outputs = []
        for step, dx in enumerate((0, 60, -5, 60, -5)):
            timestamp = 10.91 + step * .1
            outputs.append(self.engine.update(hand("palm", timestamp, dx=dx), timestamp))
        self.assertNotIn("toggle_window", self.kinds(outputs[:4]))
        self.assertEqual(self.kinds(outputs), ["toggle_window"])
        self.assertIsNotNone(outputs[-1].pointer)

    def test_wave_takes_cursor_only_after_a_real_lateral_reversal(self):
        initial = self.engine.update(hand("palm", 10), 10)
        small_move = self.engine.update(hand("palm", 10.1, dx=10), 10.1)
        first_sweep = self.engine.update(hand("palm", 10.2, dx=60), 10.2)
        reversed_sweep = self.engine.update(hand("palm", 10.3, dx=-5), 10.3)
        self.assertIsNotNone(initial.pointer)
        self.assertIsNotNone(small_move.pointer)
        self.assertIsNotNone(first_sweep.pointer)
        self.assertIsNone(reversed_sweep.pointer)
        outputs = self.feed("palm", start=10.35, duration=1.5, dx=-5)
        self.assertTrue(all(output.pointer is None for output in outputs))
        expired = self.feed("palm", start=11.9, duration=.7, dx=-5)
        self.assertNotIn("toggle_window", self.kinds(outputs + expired))
        self.assertIsNotNone(expired[-1].pointer)

    def test_large_one_way_palm_movement_never_freezes_cursor_or_toggles(self):
        outputs = []
        for frame, dx in enumerate((0, 60, 120, 180, 240, 300, 360, 420, 480)):
            timestamp = 10 + frame * .15
            sample = hand("palm", timestamp, dx=dx)
            output = self.engine.update(sample, timestamp)
            self.assertEqual(output.pointer, (sample.landmarks[8].x, sample.landmarks[8].y))
            outputs.append(output)
        self.assertNotIn("toggle_window", self.kinds(outputs))

    def test_wave_rejects_one_direction_vertical_drift_and_wrong_pose(self):
        sequences = (("palm", (0, 60, 120, 180, 240), (0,) * 5),
                     ("palm", (0, 60, -5, 60, -5), (0, 60, 120, 180, 240)),
                     ("pointer", (0, 60, -5, 60, -5), (0,) * 5))
        for pose, xs, ys in sequences:
            self.engine.reset()
            outputs = [self.engine.update(hand(pose, 10 + i * .15, dx=x, dy=y), 10 + i * .15)
                       for i, (x, y) in enumerate(zip(xs, ys))]
            self.assertNotIn("toggle_window", self.kinds(outputs))

    def test_slow_wave_outside_time_window_does_not_toggle(self):
        outputs = []
        positions = (0, 60, -5, 60, -5)
        for step, dx in enumerate(positions):
            outputs += self.feed("palm", start=10 + step * 1.3, duration=1.25, dx=dx)
        self.assertNotIn("toggle_window", self.kinds(outputs))

    def test_volume_uses_motion_not_stationary_repeat(self):
        outputs = self.feed("volume", duration=.2)
        self.assertNotIn("volume_delta", self.kinds(outputs))
        outputs = self.feed("volume", start=10.25, duration=.5, dy=-10)
        volume_events = [event.value for output in outputs for event in output.events if event.kind == "volume_delta"]
        self.assertEqual(len(volume_events), 1)
        self.assertGreater(volume_events[0], 0)
        self.assertTrue(all(output.pointer is None for output in outputs))
        outputs = self.feed("volume", start=10.8, duration=.2, dy=0)
        self.assertLess(next(event.value for output in outputs for event in output.events if event.kind == "volume_delta"), 0)

    def test_legacy_scroll_poses_never_scroll_or_consume_pointer(self):
        for pose in ("scroll_up", "scroll_down", "fist"):
            for fps in (15, 30, 60):
                for handedness in ("Left", "Right"):
                    with self.subTest(pose=pose, fps=fps, handedness=handedness):
                        self.engine = GestureEngine(self.settings)
                        outputs = self.feed(pose, duration=2.8, fps=fps, handedness=handedness)
                        self.assertFalse(self.kinds(outputs))
                        self.assertTrue(all(output.state == "PUNTERO" for output in outputs))
                        self.assertTrue(all(output.pointer is not None for output in outputs))

    def test_legacy_scroll_poses_still_release_drag_without_extra_actions(self):
        for pose in ("scroll_up", "scroll_down"):
            with self.subTest(pose=pose):
                self.engine = GestureEngine(self.settings)
                self.feed("pinch", duration=.6)
                outputs = self.feed(pose, start=10.65, duration=2)
                self.assertEqual(self.kinds(outputs), ["release_left"])
                self.assertTrue(all(output.pointer is not None for output in outputs))

    def test_menu_opens_without_pointer_and_right_sector_wraps(self):
        outputs = self.feed("thumb", duration=1.0)
        self.assertEqual(outputs[-1].state, "MENU")
        self.assertTrue(all(output.pointer is None for output in outputs))
        output = self.feed("thumb", start=11.05, duration=0, dx=65, dy=-1)[0]
        self.assertEqual(output.menu_selected, 0)
        output = self.feed("thumb", start=11.1, duration=0, dx=65, dy=1)[0]
        self.assertEqual(output.menu_selected, 0)

    def test_menu_submenu_requires_return_to_center_then_executes_once(self):
        self.feed("thumb", duration=1.0)
        outputs = self.feed("thumb", start=11.05, duration=1.2, dx=65)
        self.assertEqual(outputs[-1].menu_level, "SISTEMA")
        self.assertNotIn("command", self.kinds(outputs))
        outputs = self.feed("thumb", start=12.3, duration=2.0, dx=65)
        self.assertNotIn("command", self.kinds(outputs))
        self.feed("thumb", start=14.35, duration=.1)
        outputs = self.feed("thumb", start=14.5, duration=2.0, dx=65)
        self.assertEqual([event.value for output in outputs for event in output.events if event.kind == "command"], ["CONFIG"])

    def test_menu_neutral_resets_dwell(self):
        self.feed("thumb", duration=1.0)
        self.feed("thumb", start=11.05, duration=.6, dx=-65)
        self.feed("thumb", start=11.7, duration=.1)
        outputs = self.feed("thumb", start=11.85, duration=.6, dx=-65)
        self.assertNotIn("command", self.kinds(outputs))

    def test_exiting_menu_via_palm_clears_previous_submenu(self):
        self.feed("thumb", duration=1.0)
        outputs = self.feed("thumb", start=11.05, duration=1.2, dx=65)
        self.assertEqual(outputs[-1].menu_level, "SISTEMA")
        self.feed("palm", start=12.3, duration=.1)
        outputs = self.feed("thumb", start=12.45, duration=1.0)
        self.assertEqual(outputs[-1].menu_level, "PRINCIPAL")
        self.assertEqual(outputs[-1].menu_selected, -1)
        self.assertNotIn("command", self.kinds(outputs))

    def test_menus_have_exactly_eight_real_labels(self):
        for level, labels in MENUS.items():
            self.assertEqual(len(labels), 8, level)
            self.assertEqual(len(set(labels)), 8, level)
        self.assertEqual(MENUS["SISTEMA"][:4], ["CONFIG", "ADMIN", "BLOQUEAR", "BUSCAR"])


if __name__ == "__main__":
    unittest.main()
