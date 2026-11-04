import json
import unittest
from meg_direct_engine import DEFAULT_OFFSETS, MegDirectEngine

class TestDialogSuppression(unittest.TestCase):

    def test_offsets_json_values(self):
        with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
            offsets = json.load(f)

        self.assertEqual(offsets.get("game_object_set_active"), "0x45CCB90")
        self.assertEqual(offsets.get("window_show"), "0x25EFD90")
        self.assertEqual(offsets.get("window_hide"), "0x25F8B80")
        self.assertEqual(offsets.get("window_toggle"), "0x25E9EE0")
        self.assertEqual(offsets.get("button_press"), "0x46ABE00")
        self.assertEqual(offsets.get("unity_event_invoke"), "0x45E5B00")
        self.assertEqual(offsets.get("doublegoer_enter_recv"), "0xF92350")
        self.assertEqual(offsets.get("mhelper_ui_show_alert"), "0x1BF9CC0")

    def test_default_offsets_match(self):
        self.assertEqual(DEFAULT_OFFSETS.get("game_object_set_active"), "0x45CCB90")
        self.assertEqual(DEFAULT_OFFSETS.get("window_show"), "0x25EFD90")
        self.assertEqual(DEFAULT_OFFSETS.get("window_hide"), "0x25F8B80")
        self.assertEqual(DEFAULT_OFFSETS.get("window_toggle"), "0x25E9EE0")
        self.assertEqual(DEFAULT_OFFSETS.get("button_press"), "0x46ABE00")
        self.assertEqual(DEFAULT_OFFSETS.get("unity_event_invoke"), "0x45E5B00")
        self.assertEqual(DEFAULT_OFFSETS.get("doublegoer_enter_recv"), "0xF92350")

    def test_frida_js_no_corruption_and_zero_popup(self):
        engine = MegDirectEngine(pid=99999)
        js = engine._generate_js()

        # Must NOT write NULL to helperUi + 0x78 (which corrupted HelperUI state and prevented manual dismissal)
        self.assertNotIn("helperUi.add(0x78).writePointer(ptr(0));", js)

        # Must have Zero-Popup packet modification
        self.assertIn("pktPtr.add(0x24).writeU8(0)", js)

        # Must have dismissActiveDialog export
        self.assertIn("dismissActiveDialog:", js)
        self.assertIn("setDialogSuppression:", js)

    def test_engine_has_dialog_methods(self):
        engine = MegDirectEngine(pid=99999)
        self.assertTrue(hasattr(engine, "dismiss_active_dialog"))
        self.assertTrue(hasattr(engine, "set_dialog_suppression"))

if __name__ == "__main__":
    unittest.main()
