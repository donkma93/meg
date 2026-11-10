import unittest
import json
import os

# Các RVA đã đối chiếu tận dump_current/dump.cs VÀ kiểm chứng trực tiếp trên
# GameAssembly.dll đang cài (byte đầu hàm phải là prologue hợp lệ, không nằm giữa hàm khác).
VERIFIED_MOSS_RVAS = {
    "moss_send_roll": "0x23F8BE0",   # MossMerchantWindow.FOILGIOOHJL(int) - gửi packet quay
    "moss_roll_click": "0x27AA8B0",  # MMossMerchantWindow.OGILEDKJPLF() - OnClick RollButton
    "moss_select_cat": "0x27A8510",  # MMossMerchantWindow.IGGEKEFMNIJ(category)
}

# Các key điều khiển UI (Window.Show/Hide, Button.Press...) hiện vẫn là RVA của build CŨ.
# Chúng CHƯA khớp dump_current/dump.cs nên không được coi là "ground truth" ở đây;
# danh sách này chỉ dùng để phát hiện lệch giữa 3 nguồn cấu hình.
WINDOW_KEYS = [
    "window_hide", "window_show", "window_set_state", "window_toggle",
    "moss_window_close", "button_press", "unity_event_invoke",
    "component_get_game_object", "game_object_set_active",
]


class TestMossCloseFix(unittest.TestCase):
    def test_offsets_json_consistency(self):
        """3 nguồn offset (root JSON, config JSON, DEFAULT_OFFSETS) phải khớp nhau.

        Đây là bài kiểm tra chống phân kỳ cấu hình — trước đây
        `component_get_game_object` tồn tại 2 giá trị khác nhau giữa root và config.
        """
        from meg_direct_engine import DEFAULT_OFFSETS

        with open('megamu_offsets.json', 'r', encoding='utf-8') as f:
            root = json.load(f)
        with open('config/megamu_offsets.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        for key in list(VERIFIED_MOSS_RVAS) + WINDOW_KEYS:
            self.assertIn(key, root, f"root JSON thiếu {key}")
            self.assertIn(key, cfg, f"config JSON thiếu {key}")
            self.assertEqual(
                root[key].lower(), cfg[key].lower(),
                f"Lệch offset '{key}' giữa megamu_offsets.json ({root[key]}) và config/megamu_offsets.json ({cfg[key]})"
            )
            if key in DEFAULT_OFFSETS:
                self.assertEqual(
                    DEFAULT_OFFSETS[key].lower(), cfg[key].lower(),
                    f"Lệch offset '{key}' giữa DEFAULT_OFFSETS và config JSON"
                )

    def test_moss_rvas_match_dump(self):
        """Các RVA lõi của Moss phải đúng như đã đối chiếu với dump.cs của build hiện tại."""
        with open('config/megamu_offsets.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        for key, expected in VERIFIED_MOSS_RVAS.items():
            self.assertEqual(cfg.get(key, "").lower(), expected.lower(),
                             f"{key} không khớp dump.cs: {cfg.get(key)} != {expected}")

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
        self.assertIn("sendGSPacket([0xC1, 0x04, 0x31, 0x00])", code)

        # Pipeline dọn rác v2 phải tồn tại và có xác minh
        self.assertIn("disposeJunkItems: function(", code)
        self.assertIn("function runDropPass(", code)
        self.assertIn("function runSellPass(", code)

        # Check Python close_moss ESC fallback
        self.assertIn("self.send_background_key(hwnd, 0x1B, 0.05)", code)

    def test_gui_moss_closing_verification(self):
        """Verify meg_gui.py has verification logic on close."""
        with open('meg_gui.py', 'r', encoding='utf-8') as f:
            code = f.read()

        self.assertIn("if hasattr(eng, \"is_moss_open\") and eng.is_moss_open():", code)

    def test_gui_uses_auto_disposal(self):
        """Vòng lặp Moss phải dùng chế độ auto (vứt -> bán) thay vì chỉ vứt."""
        with open('meg_gui.py', 'r', encoding='utf-8') as f:
            code = f.read()
        self.assertIn('eng.clean_inventory_junk(\n                                    "auto"', code)
        self.assertIn("_moss_try_sell_fallback", code)
        self.assertIn("_moss_log_disposal_failure", code)


if __name__ == '__main__':
    unittest.main()
