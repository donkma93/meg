"""
Unit Test Suite: Production Architecture & Hardening Verification.
Kiểm thử toàn diện Single-Instance Mutex, MemoryService, Modular Views,
và nút Toggle gộp CƯỚP CỔNG/DỪNG.
"""

import unittest
import os
import sys
import customtkinter as ctk

from core.system_mutex import SingleInstanceMutex
from services.memory_service import MemoryService
from ui.views import (
    MossView,
    MirrorView,
    AccountsView,
    ProfilesView,
    LogsView,
)
import meg_gui


class TestProductionArchitecture(unittest.TestCase):
    """Kiểm thử tính đúng đắn và độ tin cậy của các thành phần kiến trúc Production."""

    def test_single_instance_mutex(self):
        """Kiểm tra Win32 Single-Instance Mutex ngăn chặn chạy đè 2 ứng dụng."""
        mutex_name = "Global\\MEGAMU_Test_Unique_Mutex_12345"
        m1 = SingleInstanceMutex(mutex_name)
        ok1 = m1.acquire()
        self.assertTrue(ok1, "Bản Dashboard đầu tiên phải chiếm được Mutex thành công.")
        self.assertFalse(m1.already_running)

        # Bản thứ 2 mở đè lên
        m2 = SingleInstanceMutex(mutex_name)
        ok2 = m2.acquire()
        if sys.platform == "win32":
            self.assertFalse(ok2, "Bản thứ 2 mở đè phải bị từ chối do Mutex đã tồn tại.")
            self.assertTrue(m2.already_running)

        # Giải phóng
        m2.release()
        m1.release()

        # Sau khi giải phóng, bản mới lại có thể chiếm được
        m3 = SingleInstanceMutex(mutex_name)
        ok3 = m3.acquire()
        self.assertTrue(ok3, "Sau khi giải phóng, phiên bản mới phải chiếm được Mutex.")
        m3.release()

    def test_memory_service(self):
        """Kiểm tra MemoryService thu thập thông tin RAM và thu hồi Working Set."""
        info = MemoryService.get_system_memory_info()
        self.assertIn("total_mb", info)
        self.assertIn("available_mb", info)
        self.assertIn("used_mb", info)
        self.assertIn("percent", info)
        self.assertGreater(info["total_mb"], 0)

        # Trim chính tiến trình hiện tại
        res = MemoryService.trim_self()
        if sys.platform == "win32":
            self.assertTrue(res, "Phải trim working set của tiến trình hiện tại thành công.")

        # Trim danh sách tiến trình rỗng
        batch_res = MemoryService.trim_all_game_processes([])
        self.assertEqual(batch_res["trimmed"], 0)
        self.assertEqual(batch_res["failed"], 0)

    def test_modular_views_initialization(self):
        """Kiểm tra khởi dựng ứng dụng và chuyển tab qua các Modular Views."""
        app = meg_gui.DashboardApp()
        app.withdraw()

        # Kiểm tra build_moss_view qua MossView
        self.assertTrue(hasattr(app, "lbl_moss_countdown"))
        self.assertTrue(hasattr(app, "btn_moss_start_all"))
        self.assertTrue(hasattr(app, "btn_moss_stop_all"))

        # Kiểm tra build_mirror_view qua MirrorView
        self.assertTrue(hasattr(app, "btn_mirror_toggle_snipe"))
        self.assertTrue(hasattr(app, "lbl_mirror_countdown"))

        # Kiểm tra gộp 1 nút duy nhất CƯỚP CỔNG / DỪNG
        self.assertEqual(app.btn_mirror_toggle_snipe.cget("text"), "⚡ CƯỚP CỔNG")
        self.assertIn("#7c3aed", app.btn_mirror_toggle_snipe.cget("fg_color").lower())

        # Giả lập khi có slot đang sniping
        app.controllers[0].mirror_sniping = True
        app.update_mirror_snipe_button_state()
        self.assertEqual(app.btn_mirror_toggle_snipe.cget("text"), "⏹ DỪNG CƯỚP")
        self.assertIn("#dc2626", app.btn_mirror_toggle_snipe.cget("fg_color").lower())

        # Giả lập khi dừng
        app.controllers[0].mirror_sniping = False
        app.update_mirror_snipe_button_state()
        self.assertEqual(app.btn_mirror_toggle_snipe.cget("text"), "⚡ CƯỚP CỔNG")

        # Kiểm tra API tương thích ngược của views
        acc_view = AccountsView(app, app.panel_accounts)
        self.assertEqual(acc_view.get_slot_count(), len(app.controllers))

        prof_view = ProfilesView(app)
        self.assertFalse(prof_view.is_open())

        logs_view = LogsView(app)
        self.assertFalse(logs_view.is_open())

        app.on_closing()


if __name__ == "__main__":
    unittest.main()

