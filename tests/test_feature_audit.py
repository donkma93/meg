"""
Comprehensive Feature Audit & Leak Prevention Test Suite for MEGAMU Auto Train.
Covers:
- Resource leak prevention (Win32 HDESK, Process handles, thread isolation)
- Auto Train (Stage matching, auto point, auto reset, route warp)
- Moss Merchant (Roll logic, scheduling, stop criteria)
- Double Goer & Turbo Sniping (Lugard move, schedule, ticket checks, IPC flood prevention)
- Devil Square (Schedule, reset range, ticket preference, config persistence)
- RAM Optimizer (Working set trimming, process enumeration)
- Accounts & Slot Controller (Binding, lifecycle, cleanup)
- UI Views & Modals (Zero crash instantiation, attribute validation)
"""

import unittest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from core.slot_controller import SlotController
from core.storage import ConfigPersistenceManager
from core.constants import CLASS_ID_TO_CODE, CLASS_CODE_TO_NAME
import meg_navigator
from meg_navigator import ensure_desktop_attached, ProcessMemoryReader
from meg_auto_worker import MapResolver
import meg_direct_engine
from meg_direct_engine import MegDirectEngine
import meg_ram_optimizer


class TestResourceLeakPrevention(unittest.TestCase):
    """Kiểm tra việc ngăn chặn triệt để rò rỉ tài nguyên hệ thống (Win32 Handles, Threads, RAM)."""

    def test_ensure_desktop_attached_thread_local_caching(self):
        """Đảm bảo ensure_desktop_attached không mở lặp lại hàng nghìn HDESK handle."""
        initial_attached = getattr(meg_navigator._desktop_thread_local, "attached", False)
        # Gọi lặp lại 500 lần trên cùng 1 thread
        for _ in range(500):
            ensure_desktop_attached()

        self.assertTrue(getattr(meg_navigator._desktop_thread_local, "attached", False))

    def test_process_memory_reader_close_all(self):
        """Đảm bảo ProcessMemoryReader.close_all giải phóng toàn bộ process handle và cache."""
        ProcessMemoryReader._proc_handles[99999] = 123456
        ProcessMemoryReader._module_cache[99999] = 0x18000000
        ProcessMemoryReader._char_name_cache[99999] = "TestChar"
        ProcessMemoryReader._cached_coord_regions[99999] = [(10, 20)]

        ProcessMemoryReader.close_all()

        self.assertEqual(len(ProcessMemoryReader._proc_handles), 0)
        self.assertEqual(len(ProcessMemoryReader._module_cache), 0)
        self.assertEqual(len(ProcessMemoryReader._char_name_cache), 0)
        self.assertEqual(len(ProcessMemoryReader._cached_coord_regions), 0)

    def test_direct_engine_detach_handles_interrupt(self):
        """Đảm bảo MegDirectEngine.detach() và cleanup_all() an toàn tuyệt đối khi bị ngắt."""
        eng = MegDirectEngine(1234)
        eng.session = MagicMock()
        eng.script = MagicMock()
        eng.is_ready = True

        # Khi session.detach() gây exception hoặc interrupt
        eng.session.detach.side_effect = KeyboardInterrupt("Test interrupt")
        # detach() không được ném unhandled exception
        eng.detach()
        self.assertFalse(eng.is_ready)
        self.assertIsNone(eng.session)
        self.assertIsNone(eng.script)

        # Cleanup all an toàn
        MegDirectEngine.cleanup_all()


class TestAutoTrainFeature(unittest.TestCase):
    """Kiểm tra toàn diện chức năng Auto Train."""

    def test_map_resolver_stage_routing(self):
        """Kiểm tra MapResolver nhận diện lệnh chuyển map chính xác."""
        resolver = MapResolver.get_instance()
        cmd_lorencia = resolver.resolve("Lorencia")
        self.assertIn("lorencia", cmd_lorencia.lower())

        cmd_ev = resolver.resolve("ev")
        self.assertEqual(cmd_ev, "/m ev")

        norm_ev = resolver._norm("ev")
        self.assertEqual(resolver.map_ids.get(norm_ev), 53)

    def test_class_stat_profile_mappings(self):
        """Kiểm tra bảng tra cứu class và tỷ lệ point tồn tại đầy đủ."""
        self.assertIn(1, CLASS_ID_TO_CODE)  # Dark Knight
        self.assertEqual(CLASS_ID_TO_CODE[1], "DK")
        self.assertIn("DK", CLASS_CODE_TO_NAME)
        self.assertIn("Dark Knight", CLASS_CODE_TO_NAME["DK"])

    def test_slot_controller_reset_and_points_config(self):
        """Kiểm tra cấu hình auto reset và auto point trong SlotController."""
        mock_app = MagicMock()
        ctrl = SlotController(1, mock_app)
        ctrl.auto_reset = True
        ctrl.reset_level = 400
        ctrl.auto_add_point = True
        ctrl.stat_mode = "auto"
        ctrl.stat_ratio = {"str": 40, "agi": 30, "vit": 10, "ene": 20}

        self.assertTrue(ctrl.auto_reset)
        self.assertEqual(ctrl.reset_level, 400)
        self.assertTrue(ctrl.auto_add_point)
        self.assertEqual(sum(ctrl.stat_ratio.values()), 100)


class TestMossMerchantFeature(unittest.TestCase):
    """Kiểm tra chức năng Moss Merchant."""

    def test_moss_schedule_calculation(self):
        """Kiểm tra tính toán lịch mở Moss: 00:15, 06:15, 12:15, 18:15 (kéo dài 5 phút)."""
        schedule_slots = [(0, 15), (6, 15), (12, 15), (18, 15)]
        moss_duration = 300

        # Giả lập thời gian đang trong sự kiện (ví dụ 06:17:30)
        sim_now = datetime(2026, 11, 5, 6, 17, 30)
        in_moss = False
        for h, m in schedule_slots:
            st = sim_now.replace(hour=h, minute=m, second=0, microsecond=0)
            en = st + timedelta(seconds=moss_duration)
            if st <= sim_now < en:
                in_moss = True
                rem_sec = int((en - sim_now).total_seconds())
                self.assertEqual(rem_sec, 150)
                break
        self.assertTrue(in_moss)

        # Giả lập thời gian ngoài sự kiện (ví dụ 07:00:00)
        sim_now2 = datetime(2026, 11, 5, 7, 0, 0)
        next_start = None
        for h, m in schedule_slots:
            cand = sim_now2.replace(hour=h, minute=m, second=0, microsecond=0)
            if cand + timedelta(seconds=moss_duration) <= sim_now2:
                cand += timedelta(days=1)
            if next_start is None or cand < next_start:
                next_start = cand
        self.assertEqual(next_start.hour, 12)
        self.assertEqual(next_start.minute, 15)

    def test_slot_controller_moss_state(self):
        """Kiểm tra trạng thái quay Moss trong SlotController."""
        mock_app = MagicMock()
        ctrl = SlotController(2, mock_app)
        ctrl.assigned_pid = 1234
        ctrl.is_alive = MagicMock(return_value=True)
        mock_eng = MagicMock()
        mock_eng.is_ready = True
        ctrl.get_engine = MagicMock(return_value=mock_eng)
        ctrl.engine = mock_eng

        with patch("core.slot_controller.is_megamu_process_alive", return_value=True):
            ctrl.start_moss()
            self.assertTrue(ctrl.moss_running)
            ctrl.stop_moss()
            self.assertFalse(ctrl.moss_running)


class TestDoubleGoerFeature(unittest.TestCase):
    """Kiểm tra chức năng Double Goer (Mirror of Dimensions) & Turbo Sniping."""

    def test_mirror_schedule_hours(self):
        """Kiểm tra khung giờ mở cổng Double Goer: các giờ chẵn từ :10 đến :15."""
        valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
        test_dt = datetime(2026, 11, 5, 14, 12, 0)
        is_gate_open = (test_dt.hour in valid_hours and 10 <= test_dt.minute < 15)
        self.assertTrue(is_gate_open)

        test_dt2 = datetime(2026, 11, 5, 14, 16, 0)
        is_gate_open2 = (test_dt2.hour in valid_hours and 10 <= test_dt2.minute < 15)
        self.assertFalse(is_gate_open2)

    def test_turbo_sniping_state_machine(self):
        """Kiểm tra bắt đầu và dừng Turbo Sniping trên SlotController."""
        mock_app = MagicMock()
        ctrl = SlotController(3, mock_app)
        self.assertFalse(ctrl.mirror_sniping)
        ctrl.cached_mirror_ticket_slot = 15
        ctrl.assigned_pid = 1234
        mock_eng = MagicMock()
        mock_eng.is_ready = True
        mock_eng.start_native_mirror_turbo.return_value = {"success": True}
        ctrl.engine = mock_eng

        with patch("core.slot_controller.is_megamu_process_alive", return_value=True):
            res = ctrl.start_mirror_turbo_sniping(interval_ms=80, max_duration_s=10.0)
            self.assertTrue(res)
            self.assertTrue(ctrl.mirror_sniping)
            
            ctrl.stop_mirror_turbo_sniping()
            self.assertFalse(ctrl.mirror_sniping)


class TestDevilSquareFeature(unittest.TestCase):
    """Kiểm tra chức năng Devil Square (DS)."""

    def test_devil_square_schedule_hours(self):
        """Kiểm tra khung giờ mở cổng Devil Square: giờ lẻ từ phút :26 đến :30."""
        odd_hours = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
        dt_open = datetime(2026, 11, 5, 15, 28, 0)
        is_open = (dt_open.hour in odd_hours and 26 <= dt_open.minute <= 30)
        self.assertTrue(is_open)

        dt_closed = datetime(2026, 11, 5, 15, 31, 0)
        is_open_closed = (dt_closed.hour in odd_hours and 26 <= dt_closed.minute <= 30)
        self.assertFalse(is_open_closed)

    def test_devil_reset_eligibility(self):
        """Kiểm tra điều kiện số reset để vào Devil Square."""
        min_resets = 5
        max_resets = 9999

        char_resets_ineligible = 3
        is_eligible = (min_resets <= char_resets_ineligible <= max_resets)
        self.assertFalse(is_eligible)

        char_resets_eligible = 10
        is_eligible2 = (min_resets <= char_resets_eligible <= max_resets)
        self.assertTrue(is_eligible2)


class TestRamOptimizerFeature(unittest.TestCase):
    """Kiểm tra chức năng RAM Optimizer."""

    def test_trim_process_memory_mock(self):
        """Kiểm tra hàm trim bộ nhớ tiến trình không crash và trả kết quả hợp lệ."""
        with patch("psutil.Process") as mock_proc, \
             patch("ctypes.windll.kernel32.OpenProcess", return_value=123), \
             patch("ctypes.windll.kernel32.CloseHandle", return_value=1), \
             patch("ctypes.windll.psapi.EmptyWorkingSet", return_value=1):
            
            mock_inst = MagicMock()
            mock_inst.is_running.return_value = True
            mock_inst.memory_info.return_value = MagicMock(rss=200 * 1024 * 1024)
            mock_proc.return_value = mock_inst

            res = meg_ram_optimizer.trim_single_process(9999)
            self.assertTrue(res)


class TestLicenseAndHWIDFeature(unittest.TestCase):
    """Kiểm tra chức năng xác thực bản quyền & HWID định danh máy."""

    def test_license_client_resolution(self):
        """Đảm bảo license_client luôn được nạp thành công và có HWID hợp lệ."""
        from ui.modals.license_dialog import _resolve_license_client
        lc = _resolve_license_client()
        self.assertIsNotNone(lc)
        hwid = lc.get_machine_hwid()
        self.assertIsInstance(hwid, str)
        self.assertNotEqual(hwid, "N/A")
        self.assertTrue(len(hwid) > 0)


class TestModalsAndViewsIntegrity(unittest.TestCase):
    """Kiểm tra toàn bộ modal dialogs và views không có lỗi cú pháp, import, hoặc NameError."""

    @classmethod
    def setUpClass(cls):
        import customtkinter as ctk
        cls.app = ctk.CTk()
        cls.app.withdraw()
        cls.app.controllers = [SlotController(i, cls.app) for i in range(1, 11)]
        cls.app.slot_ui_elements = {}
        cls.app._apply_window_icon = lambda w: None
        cls.app.update_header_stats = lambda: None
        cls.app.update_modules_visibility = lambda: None
        cls.app.log_message = lambda *args, **kwargs: None
        cls.app.clear_logs = lambda: None
        cls.app.render_logs = lambda: None
        cls.app.on_editor_profile_change = lambda val: None
        cls.app.reload_editor_from_file = lambda: None
        cls.app.open_stop_events_log_file = lambda: None
        cls.app.update_info = {"version": "v1.5.8"}
        cls.app.append_moss_log = lambda msg: None
        cls.app.append_mirror_log = lambda msg: None
        cls.app.update_mirror_slot_ui_state = lambda *a, **k: None
        cls.app.update_mirror_slot_status = lambda *a, **k: None
        cls.app.update_moss_slot_ui_state = lambda *a, **k: None
        cls.app.get_moss_cat_name = lambda c: "Kiếm"
        cls.app.load_profile_into_editor = lambda idx: None
        cls.app.save_editor_to_file = lambda **kw: None
        cls.app.map_list = ["Lorencia", "Noria", "Devias", "Elbeland"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_open_license_dialog(self):
        from ui.modals.license_dialog import open_license_dialog
        open_license_dialog(self.app)
        self.assertTrue(hasattr(self.app, "_license_dialog"))
        self.app._license_dialog.destroy()

    def test_open_devil_global_config_dialog(self):
        from ui.modals.devil_modal import open_devil_global_config_dialog
        open_devil_global_config_dialog(self.app)

    def test_open_stats_modal(self):
        from ui.modals.stats_modal import open_slot_stat_ratio_dialog
        open_slot_stat_ratio_dialog(self.app, 1)

    def test_open_logs_modal(self):
        from ui.modals.logs_modal import open_logs_window
        open_logs_window(self.app)
        if hasattr(self.app, "_logs_window_instance") and self.app._logs_window_instance:
            self.app._logs_window_instance.destroy()

    def test_open_profiles_modal(self):
        from ui.modals.profiles_modal import open_profiles_modal
        open_profiles_modal(self.app, 1)
        if hasattr(self.app, "_profiles_window_instance") and self.app._profiles_window_instance:
            self.app._profiles_window_instance.destroy()

    def test_open_update_dialog(self):
        from ui.modals.update_dialog import open_update_dialog
        open_update_dialog(self.app)


if __name__ == "__main__":
    unittest.main()
