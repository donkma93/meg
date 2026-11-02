import unittest
from unittest.mock import MagicMock, patch
import os
import sys

class TestTrashInPlace(unittest.TestCase):
    def test_clean_moss_inventory_in_place(self):
        """Kiểm tra clean_moss_inventory ném đồ trực tiếp tại chỗ bằng trash thay vì chạy đi Silvia."""
        from meg_gui import SlotController

        app_mock = MagicMock()
        ctrl = SlotController(1, app_mock, default_profile=1)
        ctrl.assigned_pid = 1234
        ctrl.char_name = "TestChar"
        ctrl.moss_category = 0

        engine_mock = MagicMock()
        engine_mock.is_ready = True
        engine_mock.is_moss_open.return_value = True
        engine_mock.clean_inventory_junk.return_value = {"cleaned": 7, "failed": 0}
        ctrl.engine = engine_mock

        with patch("psutil.pid_exists", return_value=True):
            # Gọi ném đồ tại chỗ (mặc định category=-1 để dọn sạch mọi đồ rác)
            cleaned = ctrl.clean_moss_inventory(method="trash", category=-1, run_in_thread=False)

        # 1. Đảm bảo gọi clean_inventory_junk với method 'trash' và category=-1
        engine_mock.clean_inventory_junk.assert_called_once()
        args, kwargs = engine_mock.clean_inventory_junk.call_args
        self.assertEqual(args[0], "trash")
        self.assertEqual(kwargs.get("category"), -1)
        self.assertEqual(kwargs.get("max_junk_level"), 6)

        # 2. Đảm bảo trả về đúng số lượng đồ đã ném
        self.assertEqual(cleaned, 7)

        # 3. Đảm bảo KHÔNG gọi sell_moss_items_at_merchant
        self.assertFalse(hasattr(ctrl, "_manual_selling") and ctrl._manual_selling)

    def test_clean_all_moss_inventories_type_safety(self):
        """Kiểm tra clean_all_moss_inventories an toàn kiểu dữ liệu và không bị lỗi TypeError."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.append_moss_log = MagicMock()
            app.after = MagicMock(side_effect=lambda ms, fn: fn())

            ctrl1 = MagicMock()
            ctrl1.slot_idx = 1
            ctrl1.assigned_pid = 100
            ctrl1.moss_enabled = True
            ctrl1.clean_moss_inventory.return_value = 3

            ctrl2 = MagicMock()
            ctrl2.slot_idx = 2
            ctrl2.assigned_pid = 200
            ctrl2.moss_enabled = True
            ctrl2.clean_moss_inventory.return_value = None  # Giả sử trả về None vẫn không crash

            app.controllers = [ctrl1, ctrl2]

            with patch("psutil.pid_exists", return_value=True):
                # Chạy clean_all_moss_inventories
                with patch("threading.Thread") as mock_thread:
                    app.clean_all_moss_inventories()
                    worker_target = mock_thread.call_args[1]["target"]
                    worker_target()

            ctrl1.clean_moss_inventory.assert_called_once_with(method="trash", category=-1, run_in_thread=False)
            ctrl2.clean_moss_inventory.assert_called_once_with(method="trash", category=-1, run_in_thread=False)

    def test_sell_all_moss_inventories(self):
        """Kiểm tra chức năng bán tại NPC Silvia vẫn hoạt động độc lập và tách biệt với ném đồ."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.append_moss_log = MagicMock()
            app.after = MagicMock(side_effect=lambda ms, fn: fn())

            ctrl1 = MagicMock()
            ctrl1.slot_idx = 1
            ctrl1.assigned_pid = 100
            ctrl1.moss_enabled = True

            app.controllers = [ctrl1]

            with patch("psutil.pid_exists", return_value=True):
                with patch("threading.Thread") as mock_thread:
                    app.sell_all_moss_inventories()
                    worker_target = mock_thread.call_args[1]["target"]
                    worker_target()

            ctrl1.sell_moss_inventory.assert_called_once()

    def test_code_structure_has_both_trash_and_sell_buttons(self):
        """Kiểm tra mã nguồn có đủ nút ném đồ tại chỗ và bán đồ Silvia cả trên hàng slot lẫn thanh công cụ."""
        with open("meg_gui.py", "r", encoding="utf-8") as f:
            code = f.read()

        # Kiểm tra nút per-slot
        self.assertIn('btn_drop = ctk.CTkButton', code)
        self.assertIn('text="🗑️ Ném"', code)
        self.assertIn('"btn_drop": btn_drop', code)

        # Kiểm tra nút toolbar
        self.assertIn('text="🗑️ Ném Tại Chỗ"', code)
        self.assertIn('text="💰 Bán Silvia"', code)
        self.assertIn('command=self.clean_all_moss_inventories', code)
        self.assertIn('command=self.sell_all_moss_inventories', code)

        # Kiểm tra context menu
        self.assertIn('🗑️ Ném đồ rác tại chỗ (Slot này)', code)
        self.assertIn('💰 Bán đồ rác tại NPC Silvia', code)

    def test_offsets_safe_from_native_crash(self):
        """Kiểm tra inv_trash_item, inv_drop_item, inv_sell_item được đặt 0x0 để vô hiệu hóa gọi native crash."""
        import json
        with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
            cfgs = json.load(f)
        self.assertEqual(cfgs.get("inv_trash_item"), "0x0")
        self.assertEqual(cfgs.get("inv_drop_item"), "0x0")
        self.assertEqual(cfgs.get("inv_sell_item"), "0x0")

    def test_moss_junk_bows_not_blocked_by_divine_filter(self):
        """Kiểm tra REA: Các loại cung nỏ rác thường +0..+6 từ Moss (Celestial, Albatross, Dark Stinger, Viper...)
        KHÔNG bị chặn nhầm bởi isDivineOrDragonItem, trong khi DAA và đồ Exc/Socket/Set vẫn được bảo vệ 100%."""
        import subprocess
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            engine_code = f.read()

        # Trích xuất hàm isDivineOrDragonItem và isItemProtected từ Frida JS
        start_idx = engine_code.find("function isDivineOrDragonItem")
        end_idx = engine_code.find("var nativeGetGameUI = null;")
        self.assertTrue(start_idx > 0 and end_idx > start_idx)
        js_code = engine_code[start_idx:end_idx]

        test_runner = f"""
function getItemName(ptr) {{
    return ptr && ptr.name ? ptr.name : "";
}}
{js_code}

const tests = [
    // 1. Cung nỏ rác từ Moss (+0..+4 không Exc, không Socket, không Set) -> PHẢI LÀ RÁC (protected = false)
    {{ name: "Dark Stinger Bow", sec: 4, type: 24, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 2, expectedProtected: false }},
    {{ name: "Celestial Bow", sec: 4, type: 17, lvl: 2, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 2, expectedProtected: false }},
    {{ name: "Albatross Bow", sec: 4, type: 22, lvl: 4, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: false }},
    {{ name: "Arrow Viper Crossbow", sec: 4, type: 20, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 2, expectedProtected: false }},
    {{ name: "Saint Crossbow", sec: 4, type: 16, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: false }},
    {{ name: "Bone Blade", sec: 0, type: 22, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 0, expectedProtected: false }},
    {{ name: "Daybreak", sec: 0, type: 24, lvl: 3, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 0, expectedProtected: false }},
    {{ name: "Kundun Staff", sec: 5, type: 12, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 3, expectedProtected: false }},

    // Khi dọn dẹp thủ công toàn bộ thùng đồ (mossCat = -1), mọi loại vũ khí rác đều bị dọn
    {{ name: "Dark Stinger Bow (Manual Clean)", sec: 4, type: 24, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: -1, expectedProtected: false }},
    {{ name: "Bone Blade (Manual Clean)", sec: 0, type: 22, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: -1, expectedProtected: false }},

    // 2. Vũ khí Thần / Thiên Sứ / Rồng thật -> BẢO VỆ TUYỆT ĐỐI (protected = true)
    {{ name: "Divine Archangel Bow", sec: 4, type: 18, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: true }},
    {{ name: "Blessed Divine Archangel Bow", sec: 4, type: 26, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: true }},
    {{ name: "Divine Archangel Sword", sec: 0, type: 19, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 0, expectedProtected: true }},
    {{ name: "Dragon Spear", sec: 3, type: 10, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 0, expectedProtected: true }},
    {{ name: "Chaos Dragon Axe", sec: 1, type: 6, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 0, expectedProtected: true }},

    // 3. Đồ thường nhưng có thuộc tính quý (Exc, Socket, Set, >= +7) -> BẢO VỆ TUYỆT ĐỐI (protected = true)
    {{ name: "Dark Stinger Bow Excellent", sec: 4, type: 24, lvl: 0, exc: 1, anc: 0, sock: 0, harm: 0, luck: 1, mossCat: 2, expectedProtected: true }},
    {{ name: "Albatross Bow Socket", sec: 4, type: 22, lvl: 0, exc: 0, anc: 0, sock: 3, harm: 0, luck: 0, mossCat: 2, expectedProtected: true }},
    {{ name: "Celestial Bow Ancient", sec: 4, type: 17, lvl: 0, exc: 0, anc: 5, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: true }},
    {{ name: "Dark Stinger Bow +7", sec: 4, type: 24, lvl: 7, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, mossCat: 2, expectedProtected: true }}
];

for (const t of tests) {{
    const idx = t.sec * 512 + t.type;
    const cat = (t.mossCat !== undefined) ? t.mossCat : 2;
    const isProt = isItemProtected({{ name: t.name }}, idx, t.lvl, t.exc, t.anc, t.sock, t.harm, t.luck, cat, 6);
    if (isProt !== t.expectedProtected) {{
        console.error(`FAILED: ${{t.name}} expected protected=${{t.expectedProtected}} but got ${{isProt}}`);
        process.exit(1);
    }}
}}
console.log("ALL_PASSED");
"""
        proc = subprocess.run(["node", "-e", test_runner], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node test failed: {proc.stderr} {proc.stdout}")
        self.assertIn("ALL_PASSED", proc.stdout)

if __name__ == "__main__":
    unittest.main()
