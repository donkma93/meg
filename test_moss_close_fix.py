import unittest
import json
import os
import re

class TestMossCloseFix(unittest.TestCase):
    def test_offsets_json(self):
        """Verify offsets in JSON configuration files."""
        for path in ['megamu_offsets.json', 'config/megamu_offsets.json']:
            self.assertTrue(os.path.exists(path), f"File {path} does not exist")
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(data.get("window_hide"), "0x25986B0")
            self.assertEqual(data.get("window_show"), "0x258FBC0")
            self.assertEqual(data.get("window_set_state"), "0x258A730")
            self.assertEqual(data.get("game_object_set_active"), "0x456F2B0")
            self.assertEqual(data.get("component_get_game_object"), "0x456AE90")
            self.assertEqual(data.get("button_press"), "0x464E520")
            self.assertEqual(data.get("unity_event_invoke"), "0x4588220")
            self.assertEqual(data.get("moss_window_close"), "0x25986B0")

    def test_direct_engine_default_offsets(self):
        """Verify DEFAULT_OFFSETS in meg_direct_engine.py."""
        from meg_direct_engine import DEFAULT_OFFSETS
        self.assertEqual(DEFAULT_OFFSETS.get("window_hide"), "0x25986B0")
        self.assertEqual(DEFAULT_OFFSETS.get("window_show"), "0x258FBC0")
        self.assertEqual(DEFAULT_OFFSETS.get("window_set_state"), "0x258A730")
        self.assertEqual(DEFAULT_OFFSETS.get("game_object_set_active"), "0x456F2B0")
        self.assertEqual(DEFAULT_OFFSETS.get("component_get_game_object"), "0x456AE90")
        self.assertEqual(DEFAULT_OFFSETS.get("button_press"), "0x464E520")
        self.assertEqual(DEFAULT_OFFSETS.get("unity_event_invoke"), "0x4588220")
        self.assertEqual(DEFAULT_OFFSETS.get("moss_window_close"), "0x25986B0")

    def test_frida_script_contents(self):
        """Verify Frida script in meg_direct_engine.py contains proper closing logic."""
        with open('meg_direct_engine.py', 'r', encoding='utf-8') as f:
            code = f.read()

        # Check native function declarations
        self.assertIn("var nativeButtonPress = null;", code)
        self.assertIn("var nativeUnityEventInvoke = null;", code)
        self.assertIn("var nativeWindowToggle = null;", code)

        # Check closeMoss implementation
        self.assertIn("closeMoss: function()", code)
        self.assertIn("nativeButtonPress(closeBtn, ptr(0))", code)
        self.assertIn("nativeUnityEventInvoke(onClick, ptr(0))", code)
        self.assertIn("nativeWindowHide(win, ptr(0))", code)
        self.assertIn("nativeGameObjectSetActive(wGo, 0, ptr(0))", code)
        self.assertIn("nativeGameObjectSetActive(mGo, 0, ptr(0))", code)
        self.assertIn("sendGSPacket([0xC1, 0x04, 0x31, 0x00])", code)

        # Check Python close_moss ESC fallback
        self.assertIn("self.send_background_key(hwnd, 0x1B, 0.05)", code)

    def test_gui_moss_closing_verification(self):
        """Verify meg_gui.py has verification logic on close."""
        with open('meg_gui.py', 'r', encoding='utf-8') as f:
            code = f.read()

        self.assertIn("if hasattr(eng, \"is_moss_open\") and eng.is_moss_open():", code)

if __name__ == '__main__':
    unittest.main()

