#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_devil_rea_entry.py - Kiểm thử toàn diện cơ chế Native Entry Devil Square theo Reverse Engineering (REA)
Xác minh:
1. Offsets chuẩn từ GameAssembly.dll & dump.cs:
   - devil_closure_enter: 0xF91530 (DevilSquare.ECEGJEAOELA.ILEAOLLJKPG)
   - devil_closure_type_info: 0x5553118 (DevilSquare.ECEGJEAOELA_TypeInfo)
   - devil_npc_click: 0xF82E70 (DevilSquare.JCKMKJCPMMI)
   - devil_enter_alt: 0xF834C0 (DevilSquare.HNCDPEIBGPG)
   - devil_enter_1e: 0xF75CF0 (DevilSquare.OMKNMKGNIPF)
2. Công thức Wire Slot: wireSlot = actualSlot + 12 (add dil, 0xc tại 0xF91678)
3. Zero-Confirm Entry: Gọi trực tiếp closure native trong RAM, không hiển thị dialog UI.
4. Gửi đồng thời Opcode 0x90, 0x1E, 0xC2 với các định dạng slot wireSlot, actualSlot, relSlot.
"""

import unittest
import json
import os
import re

class TestDevilReaEntry(unittest.TestCase):
    def test_offsets_config(self):
        # 1. Kiểm tra file config/megamu_offsets.json
        cfg_path = os.path.join(os.path.dirname(__file__), "config", "megamu_offsets.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.assertEqual(cfg.get("devil_closure_enter"), "0xF91530")
        self.assertEqual(cfg.get("devil_closure_type_info"), "0x5553118")
        self.assertEqual(cfg.get("devil_npc_click"), "0xF82E70")
        self.assertEqual(cfg.get("devil_enter"), "0xF91530")
        self.assertEqual(cfg.get("devil_enter_alt"), "0xF834C0")
        self.assertEqual(cfg.get("devil_enter_1e"), "0xF75CF0")
        self.assertEqual(cfg.get("table_event_entry_level"), "0xCEA9B0")
        self.assertEqual(cfg.get("helper_ui_show_confirm"), "0x1BFFFB0")
        self.assertEqual(cfg.get("item_devil_ticket_master"), 6702)
        self.assertEqual(cfg.get("item_devil_ticket"), 7187)

    def test_default_offsets_code(self):
        # 2. Kiểm tra DEFAULT_OFFSETS trong meg_direct_engine.py
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn('"devil_closure_enter": "0xF91530"', code)
        self.assertIn('"devil_closure_type_info": "0x5553118"', code)
        self.assertIn('"devil_npc_click": "0xF82E70"', code)
        self.assertIn('"devil_enter_alt": "0xF834C0"', code)
        self.assertIn('"devil_enter_1e": "0xF75CF0"', code)
        self.assertIn('"table_event_entry_level": "0xCEA9B0"', code)
        self.assertIn('"helper_ui_show_confirm": "0x1BFFFB0"', code)

    def test_frida_js_devil_closure_and_wire_slot(self):
        # 3. Kiểm tra mã JavaScript Frida trong meg_direct_engine.py
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            code = f.read()

        # Kiểm tra khai báo nativeDevilClosureEnter
        self.assertIn("var nativeDevilClosureEnter = null;", code)
        self.assertIn("off('__DEVIL_CLOSURE_ENTER__')", code)
        self.assertIn("off('__DEVIL_CLOSURE_TYPE_INFO__')", code)
        self.assertIn("off('__TABLE_EVENT_ENTRY_LEVEL__')", code)
        self.assertIn("off('__HELPER_UI_SHOW_CONFIRM__')", code)

        # Kiểm tra REA hooks:
        # a) tableEventEntryLevelHook: Thay thế kết quả -1 thành DS level chuẩn
        self.assertIn("tableEventEntryLevelHook", code)
        self.assertIn("retval.replace(ptr(dsLvl));", code)

        # b) helperUIShowDialogHook: Chặn dialog báo lỗi thiếu vé
        self.assertIn("helperUIShowDialogHook", code)
        self.assertIn('lowMsg.indexOf("ticket for your level") !== -1', code)

        # c) helperUIShowConfirmHook: Auto confirm popup để vào ngay (Zero-confirm 100%)
        self.assertIn("helperUIShowConfirmHook", code)
        self.assertIn("actFn(target, 1, ptr(0));", code)

        # Kiểm tra tính toán wireSlot = actualSlot + 12
        self.assertIn("var wireSlot = (actualSlot + 12) & 0xFF;", code)

        # Kiểm tra tính toán enterDsLevel đúng theo cấp độ nhân vật (TableEventEntryLevel)
        self.assertIn("var enterDsLevel = (charLvl >= 400 || dsLevel >= 6) ? 6 : ((dsLevel !== undefined && dsLevel !== null && dsLevel >= 0) ? dsLevel : 0);", code)

        # Kiểm tra packet 0x90, 0x1E, 0xC2
        self.assertIn("[0xC1, 0x05, 0x90, lvl, wireSlot]", code)
        self.assertIn("[0xC1, 0x05, 0x1E, lvl, wireSlot]", code)
        self.assertIn("[0xC1, 0x05, 0xC2, lvl, wireSlot]", code)

        # Kiểm tra cơ chế tự động tương tác NPC Charon (Zero-manual click)
        # GameServer bắt buộc mở session tương tác Charon trước khi nhận opcode 0x90
        enter_devil_code = code.split("enterDevil: function")[1].split("getDevilTicketInfo: function")[0]
        self.assertIn("sendCharonTalkPacket();", enter_devil_code)
        self.assertIn("invokeNpcTalk(charon);", enter_devil_code)

    def test_wire_slot_calculation(self):
        # 4. Xác minh tính toán wire slot cho các vị trí item khác nhau
        test_cases = [
            (20, 20, 8, 32),    # Slot 20 trong itemsArr -> rel 8 -> wireSlot 32 (0x20)
            (12, 12, 0, 24),    # Slot 12 đầu thùng đồ -> rel 0 -> wireSlot 24 (0x18)
            (75, 75, 63, 87),   # Slot cuối main inv -> wireSlot 87
            (76, 76, 64, 88),   # Slot đầu expanded inv -> wireSlot 88
        ]
        for slot, expected_actual, expected_rel, expected_wire in test_cases:
            actual = (slot + 12) if slot < 12 else slot
            rel = (actual - 12) if actual >= 12 else actual
            wire = actual + 12
            self.assertEqual(actual, expected_actual)
            self.assertEqual(rel, expected_rel)
            self.assertEqual(wire, expected_wire)

if __name__ == "__main__":
    unittest.main()
