"""Cross-module regressions: gesture transitions must not multiply OS actions."""

from dataclasses import replace
import unittest
from unittest.mock import Mock

from biogesture.gestures import GestureEngine, HandGeometry
from biogesture.settings import Settings
from biogesture.windows import WindowsActions
from tests.test_gestures import hand


class IntegrationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.engine = GestureEngine(Settings(start_paused=False))
        self.native = Mock()
        self.actions = WindowsActions(_native=self.native)

    def dispatch(self, output):
        for event in output.events:
            if event.kind != "toggle_window":
                self.actions.handle(event)

    def test_short_left_to_right_pinch_releases_left_without_synthetic_click(self):
        self.dispatch(self.engine.update(hand("pinch", 10), 10))
        output = self.engine.update(hand("right", 10.15), 10.15)
        self.dispatch(output)
        self.assertEqual([event.kind for event in output.events], ["release_left", "click_right"])
        self.assertEqual(self.native.button.call_args_list,
                         [(("left", True),), (("left", False),), (("right", True),), (("right", False),)])

    def test_index_pointer_is_available_with_other_fingers_extended_before_wave(self):
        palm = hand("palm", 10)
        points = list(palm.landmarks)
        points[1:5] = hand("pointer", 10).landmarks[1:5]
        transitional = replace(palm, landmarks=tuple(points))
        geometry = HandGeometry(transitional)
        self.assertTrue(all(geometry.extended))
        self.assertFalse(geometry.thumb_extended)
        output = self.engine.update(transitional, 10)
        self.assertEqual(output.pointer, (transitional.landmarks[8].x, transitional.landmarks[8].y))
        self.assertFalse(output.events)

    def test_camera_loss_releases_actual_adapter_drag_once(self):
        for frame in range(17):
            timestamp = 10 + frame / 30
            self.dispatch(self.engine.update(hand("pinch", timestamp), timestamp))
        self.assertEqual(self.native.button.call_args_list, [(("left", True),)])
        self.dispatch(self.engine.update(None, 10.6))
        self.dispatch(self.engine.update(None, 10.7))
        self.assertEqual(self.native.button.call_args_list,
                         [(("left", True),), (("left", False),)])
        self.assertFalse(self.actions._held_buttons)

    def test_thumb_flicker_during_continuous_wave_does_not_toggle_twice(self):
        outputs = []
        for frame, dx in enumerate((0, 60, -5, 60, -5)):
            timestamp = 10 + frame * 0.15
            outputs.append(self.engine.update(hand("palm", timestamp, dx=dx), timestamp))
        palm = hand("palm", 10.7)
        points = list(palm.landmarks)
        points[1:5] = hand("pointer", 10.7).landmarks[1:5]
        outputs.append(self.engine.update(replace(palm, landmarks=tuple(points)), 10.7))
        for frame, dx in enumerate((0, 60, -5, 60, -5)):
            timestamp = 10.8 + frame * 0.15
            outputs.append(self.engine.update(hand("palm", timestamp, dx=dx), timestamp))
        toggles = [event for output in outputs for event in output.events if event.kind == "toggle_window"]
        self.assertEqual(len(toggles), 1)

    def test_right_click_reacquisition_does_not_repeat_native_click(self):
        self.dispatch(self.engine.update(hand("right", 10), 10))
        self.dispatch(self.engine.update(None, 10.1))
        for frame in range(16):
            timestamp = 10.2 + frame / 30
            self.dispatch(self.engine.update(hand("right", timestamp), timestamp))
        self.assertEqual(self.native.button.call_args_list,
                         [(("right", True),), (("right", False),)])


if __name__ == "__main__":
    unittest.main()
