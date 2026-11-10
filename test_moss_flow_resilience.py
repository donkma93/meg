# -*- coding: utf-8 -*-
"""
test_moss_flow_resilience.py
Kiểm thử tính kiên cường và thông minh của quy trình Auto Moss:
1. Nhận diện cửa sổ Moss đã mở sẵn (Pre-opened window detection)
2. Tự động di chuyển về Elbeland (22, 225) nếu nhân vật ở xa
3. Kiểm tra Zen chuẩn từ RAM (get_player_zen)
4. Multi-channel Polling verification (Zen, Inventory diff, RewardStorage)
5. Chẩn đoán chính xác giới hạn khối 4x4 (CheckFreeBlock) thay vì đoán mò hết Zen
6. Không cưỡng chế đóng cửa sổ game của người dùng khi gặp lỗi
"""

import unittest
import re
from pathlib import Path

class TestMossFlowResilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gui_path = Path("meg_gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            cls.gui_code = f.read()

        engine_path = Path("meg_direct_engine.py")
        with open(engine_path, "r", encoding="utf-8") as f:
            cls.engine_code = f.read()

    def test_sync_move_method_exists(self):
        """AccountController phải có _sync_move_to_moss_elbeland đồng bộ."""
        self.assertIn("def _sync_move_to_moss_elbeland(self, eng)", self.gui_code)
        self.assertIn('eng.send_chat("/move Elbeland")', self.gui_code)
        self.assertIn("eng.start_auto_move(22, 225", self.gui_code)

    def test_pre_opened_moss_detection_in_open_npc(self):
        """open_moss_npc phải kiểm tra is_moss_open() trước tiên để không gửi talk thừa."""
        self.assertIn("def open_moss_npc(self)", self.gui_code)
        # Kiểm tra đoạn code nhận diện pre-opened
        idx_open = self.gui_code.find("def open_moss_npc(self)")
        sub = self.gui_code[idx_open:idx_open+1200]
        self.assertIn("eng.is_moss_open()", sub)
        self.assertIn("ĐÃ MỞ SẴN", sub.upper() or "ĐÃ MỞ SẴN" in sub)

    def test_pre_opened_moss_detection_in_loop(self):
        """_run_moss_loop phải nhận diện ngay nếu bảng Moss đã mở sẵn."""
        idx_loop = self.gui_code.find("def _run_moss_loop():")
        sub = self.gui_code[idx_loop:idx_loop+1500]
        self.assertIn("eng.is_moss_open()", sub)
        self.assertIn("npc_ready = True", sub)

    def test_zen_verification_before_roll(self):
        """Trước khi bấm quay phải kiểm tra get_player_zen() >= 1_000_000."""
        self.assertIn("zen_before = eng.get_player_zen()", self.gui_code)
        self.assertIn("1_000_000", self.gui_code)
        self.assertIn("Không đủ Zen để quay Moss", self.gui_code)

    def test_multi_channel_polling(self):
        """Phải có vòng lặp Multi-channel polling lắng nghe Zen, Inventory, RewardStorage."""
        self.assertIn("time.time() - poll_start < 1.5", self.gui_code)
        self.assertIn("(zen_before - zen_now) >= 500_000", self.gui_code)
        self.assertIn("get_moss_roll_status", self.gui_code)
        self.assertIn("hasReward", self.gui_code)

    def test_accurate_diagnosis_and_failure_threshold(self):
        """Chẩn đoán chính xác CheckFreeBlock(4,4) và nâng ngưỡng chịu lỗi lên >= 4."""
        self.assertIn("CheckFreeBlock(4,4)", self.gui_code)
        self.assertIn("consecutive_fails >= 4", self.gui_code)

    def test_no_forced_close_on_exit(self):
        """Khi dừng quay hoặc gặp lỗi, không cưỡng chế gọi close_moss làm biến mất cửa sổ."""
        idx_exit = self.gui_code.find("self.moss_running = False")
        # Tìm đoạn cuối của _run_moss_loop
        idx_loop = self.gui_code.find("def _run_moss_loop():")
        idx_worker = self.gui_code.find("self.moss_worker_thread = threading.Thread", idx_loop)
        sub = self.gui_code[idx_loop:idx_worker]
        # Không được có eng.close_moss() ở khối thoát lỗi / kết thúc
        self.assertNotIn("eng.close_moss()", sub)

    def test_engine_has_valid_roll_rva(self):
        """meg_direct_engine.py và offsets.json phải trỏ tới 0x27AA8B0 (OGILEDKJPLF)."""
        self.assertIn('"moss_roll_click": "0x27AA8B0"', self.engine_code)


if __name__ == '__main__':
    unittest.main()
