import unittest
from unittest.mock import Mock, patch

from biogesture.models import ActionEvent
from biogesture.windows import WindowsActions, _AudioVolume


class WindowsActionTests(unittest.TestCase):
    def test_construction_and_dry_run_never_initialize_native_input(self):
        with patch("biogesture.windows._NativeInput") as native:
            actions = WindowsActions(dry_run=True)
            actions.move(-1920, 10)
            actions.handle(ActionEvent("click_left"))
            actions.handle(ActionEvent("command", "PLAY/PAUSE"))
            actions.handle(ActionEvent("command", "BLOQUEAR"))
            actions.handle(ActionEvent("volume_delta", 0.1))
            actions.close()
            native.assert_not_called()

    def test_drag_press_is_idempotent_and_release_all_only_releases_owned_inputs(self):
        native = Mock()
        actions = WindowsActions(_native=native)
        actions.handle(ActionEvent("press_left"))
        actions.handle(ActionEvent("press_left"))
        actions.release_all()
        actions.release_all()
        self.assertEqual(native.button.call_args_list, [(("left", True),), (("left", False),)])
        native.key.assert_not_called()

    def test_shortcut_failure_releases_modifier_and_key(self):
        native = Mock()

        def key(name, down):
            if name == "c" and down:
                raise OSError("test blocked key")

        native.key.side_effect = key
        actions = WindowsActions(_native=native)
        with self.assertLogs(level="ERROR"):
            self.assertFalse(actions.handle(ActionEvent("command", "COPIAR")))
        self.assertIn((("c", False),), native.key.call_args_list)
        self.assertIn((("ctrl", False),), native.key.call_args_list)
        self.assertFalse(actions._held_keys)
        self.assertIn("test blocked key", actions.last_error)

    def test_failed_mouse_release_is_retained_for_retry(self):
        native = Mock()
        native.button.side_effect = [None, OSError("temporary"), None]
        actions = WindowsActions(_native=native)
        actions.handle(ActionEvent("press_left"))
        with self.assertLogs(level="ERROR"):
            self.assertFalse(actions.release_all())
        self.assertIn("left", actions._held_buttons)
        self.assertTrue(actions.release_all())
        self.assertFalse(actions._held_buttons)

    def test_media_commands_use_global_media_keys(self):
        native = Mock()
        actions = WindowsActions(_native=native)
        for command, key in (("PLAY/PAUSE", "media_play_pause"), ("SIGUIENTE", "media_next"),
                             ("MUTE", "volume_mute"), ("VOL+", "volume_up")):
            native.reset_mock()
            self.assertTrue(actions.handle(ActionEvent("command", command)))
            self.assertEqual(native.key.call_args_list, [((key, True),), ((key, False),)])

    def test_video_letters_only_in_explicit_multimedia_profile(self):
        native = Mock()
        actions = WindowsActions(_native=native)
        with self.assertLogs(level="ERROR"):
            self.assertFalse(actions.handle(ActionEvent("command", "ATRAS 10s")))
        native.key.assert_not_called()
        actions.set_profile("Multimedia")
        self.assertTrue(actions.handle(ActionEvent("command", "ATRAS 10s")))
        native.key.assert_any_call("j", True)

    def test_system_actions_are_explicit_and_separate(self):
        native = Mock()
        actions = WindowsActions(_native=native)
        self.assertTrue(actions.handle(ActionEvent("command", "ADMIN")))
        native.task_manager.assert_called_once()
        native.lock.assert_not_called()
        self.assertTrue(actions.handle(ActionEvent("command", "BLOQUEAR")))
        native.lock.assert_called_once()
        self.assertTrue(actions.handle(ActionEvent("command", "BUSCAR")))
        native.key.assert_any_call("win", True)
        native.key.assert_any_call("s", True)

    def test_profile_shortcuts_are_validated_and_apply(self):
        native = Mock()
        with self.assertRaises(ValueError):
            WindowsActions(shortcuts={"Global": {"COPIAR": ("shell-execute",)}})
        actions = WindowsActions(
            _native=native, shortcuts={"Global": {"COPIAR": ("ctrl", "shift", "c")}})
        self.assertTrue(actions.handle(ActionEvent("command", "COPIAR")))
        native.key.assert_any_call("shift", True)

    def test_screen_coordinates_support_negative_monitors(self):
        native = Mock()
        actions = WindowsActions(_native=native)
        self.assertTrue(actions.move(-1000.5, 125.6))
        native.move.assert_called_once_with(-1000, 126)
        with self.assertLogs(level="ERROR"):
            self.assertFalse(actions.move(float("nan"), 0))

    def test_volume_uses_scalar_delta_and_close_releases_audio(self):
        volume = Mock()
        actions = WindowsActions(_native=Mock(), _volume=volume)
        self.assertTrue(actions.handle(ActionEvent("volume_delta", 0.05)))
        volume.adjust.assert_called_once_with(0.05)
        actions.close()
        volume.close.assert_called_once()
        with self.assertLogs(level="ERROR"):
            self.assertFalse(actions.handle(ActionEvent("click_left")))

    def test_audio_refreshes_endpoint_once_after_device_failure(self):
        audio = _AudioVolume()
        stale, current = Mock(), Mock()
        stale.GetMasterVolumeLevelScalar.side_effect = OSError("device removed")
        current.GetMasterVolumeLevelScalar.return_value = 0.9
        endpoints = iter([stale, current])

        def connect():
            audio._endpoint = next(endpoints)

        audio._connect = Mock(side_effect=connect)
        audio.adjust(0.3)
        self.assertEqual(audio._connect.call_count, 2)
        current.SetMasterVolumeLevelScalar.assert_called_once_with(1.0, None)


if __name__ == "__main__":
    unittest.main()
