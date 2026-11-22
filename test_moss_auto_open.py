#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_moss_auto_open.py
Kiểm thử hồi quy cho bản sửa lỗi tự động mở bảng Moss không cần click thủ công NPC:
1. findMossNpc() & _find_moss_npc_rpm() phải lọc chặt ViewportBody + NpcBody, loại trừ tuyệt đối CharacterBody (người chơi),
   đọc Skin (+0x60) & MonsterInfo (+0x138) và ưu tiên điểm số (Skin/Class == 492 > tên 'moss' > NpcBody tại 22,225).
2. interactMossNpc() & openMoss() TUYỆT ĐỐI không được cưỡng chế win+0x48 = 1 cục bộ trước khi Server mở bảng thật.
3. performMossInteractOnMainThread() dọn cửa sổ kẹt trước khi gửi C1:30 và có fallback nativeNpcSendTalk nếu nativeNpcTalk tự hủy âm thầm.
4. pollMossSelectAfterServerOpenOnMainThread() tự động chọn tab Category ngay khi Server mở bảng thật (catCount > 0).
5. meg_gui.py: _ensure_near_moss_npc(), _run_moss_loop(), open_moss_npc(), roll_moss_once() chờ đúng is_moss_ready() từ Server.
6. Cú pháp Python & Frida JS (node --check) và cổng Zero-Offset-On-Disk đều PASS 100%.
"""

import os
import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent


class TestMossAutoOpen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from meg_direct_engine import MegDirectEngine
        cls.engine_src = (BASE_DIR / "meg_direct_engine.py").read_text(encoding="utf-8")
        cls.gui_src = (BASE_DIR / "meg_gui.py").read_text(encoding="utf-8")
        eng = MegDirectEngine(999999)
        cls.js = eng._generate_js()

    def test_01_js_syntax_valid_node(self):
        tmp = BASE_DIR / "scratch" / "_tmp_test_moss_auto_open.js"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(self.js, encoding="utf-8")
        try:
            res = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Lỗi cú pháp JS:\n{res.stderr}")
        finally:
            if tmp.exists():
                tmp.unlink()

    def test_02_find_moss_npc_excludes_players_and_reads_real_skin(self):
        start = self.js.index("function findMossNpc()")
        end = self.js.index("function getNpcManagerPtr()", start)
        fn = self.js[start:end]

        self.assertIn("entryAddr.readS32() < 0", fn, "Phải bỏ qua slot Dictionary bị xóa")
        self.assertIn('vKlassName.indexOf("ViewportBody") === -1', fn, "Phải kiểm tra ViewportBody")
        self.assertIn('bKlassName.indexOf("CharacterBody") !== -1', fn, "Phải loại trừ tuyệt đối người chơi CharacterBody")
        self.assertIn("body.add(0x60).readS32()", fn, "Phải đọc Body.Skin (+0x60) thật của NPC")
        self.assertIn("bSkin === 492", fn, "Phải nhận diện đúng Skin ID 492 của Moss")
        self.assertIn("body.add(0x138).readPointer()", fn, "Phải đọc MonsterInfo (+0x138) làm fallback tên NPC")
        self.assertIn('bKlassName.indexOf("NpcBody") !== -1', fn, "Fallback tọa độ chỉ áp dụng cho NpcBody thật")

    def test_03_python_rpm_scanner_excludes_players_and_reads_skin(self):
        start = self.engine_src.index("def _find_moss_npc_rpm(self)")
        end = self.engine_src.index("def interact_moss_npc(self", start)
        fn = self.engine_src[start:end]

        self.assertIn('"ViewportBody" not in read_klass_name(val)', fn)
        self.assertIn('"CharacterBody" in b_klass', fn)
        self.assertIn("read_i32(body + 0x60)", fn)
        self.assertIn("b_skin == 492", fn)

    def test_04_find_merchant_npc_excludes_players(self):
        start = self.js.index("function findMerchantNpc()")
        end = self.js.index("var guiUpdateOff =", start)
        fn = self.js[start:end]

        self.assertIn("entryAddr.readS32() < 0", fn)
        self.assertIn('indexOf("ViewportBody") === -1', fn)
        self.assertIn('indexOf("CharacterBody") !== -1', fn)

    def test_05_interact_moss_does_not_fake_open_local_window(self):
        start = self.js.index("interactMossNpc: function(categoryId)")
        end = self.js.index("findMerchantNpc: function()", start)
        fn = self.js[start:end]

        self.assertIn("pendingMossOpenCategory = null;", fn, "Không được cưỡng chế pendingMossOpenCategory trước khi Server phản hồi!")
        self.assertIn("pendingMossSelectAfterServerOpen =", fn, "Phải đợi Server mở bảng thật rồi mới chọn Category")
        self.assertIn("pendingMossInteractPtr = npc.ptr;", fn)

        # setupMossWindow và performMossResetNow không được phép cưỡng chế win+0x48 = 1 khi chưa có catCount > 0
        s_start = self.js.index("function setupMossWindow(")
        s_end = self.js.index("function performMossCloseNow()", s_start)
        s_fn = self.js[s_start:s_end]
        self.assertIn("isMossWindowServerReady(mossWin)", s_fn)
        self.assertNotIn("writeU8(1)", s_fn, "setupMossWindow không được tự ghi win+0x48 = 1 khi Server chưa mở!")

    def test_06_invoke_npc_talk_detects_silent_abort_and_clears_blockers(self):
        self.assertIn("function performMossInteractOnMainThread(", self.js)
        self.assertIn("clearBlockingWindowsForNpcTalk(gui)", self.js)
        self.assertIn("invokeNpcTalk(nPtr, true)", self.js)
        self.assertIn("afterTalk = nm.add(0x20).readFloat()", self.js)
        self.assertIn("pollMossSelectAfterServerOpenOnMainThread", self.js)

    def test_07_gui_waits_for_server_ready_and_walks_close(self):
        self.assertIn("def _ensure_near_moss_npc(", self.gui_src)
        self.assertIn("self._ensure_near_moss_npc(eng, npc_info=npc_info, max_dist=3.0)", self.gui_src)
        self.assertIn("opened_by_server = False", self.gui_src)
        self.assertIn("if eng and eng.is_moss_ready():", self.gui_src)

    def test_08_zero_offset_leak_gate(self):
        import build_secure_release
        self.assertTrue(build_secure_release.audit_zero_offset_leaks())


if __name__ == "__main__":
    unittest.main(verbosity=2)
