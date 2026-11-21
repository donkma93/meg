import unittest
from unittest.mock import MagicMock, patch


class TestMultiSlotOver10(unittest.TestCase):
    """Kiểm thử nhận diện, tự mở rộng và đồng bộ telemetry cho > 10 nhân vật (slot 11..15)."""

    def setUp(self):
        from ui.state import AppStateManager
        # Tạo instance sạch cho mỗi test (không phá singleton dùng chung)
        self.state_mgr = object.__new__(AppStateManager)
        self.state_mgr._init_state()

    def test_state_manager_supports_slots_over_10_and_disconnect(self):
        """AppStateManager phải nhận telemetry cho slot 11..15 thay vì âm thầm drop."""
        for idx in range(11, 16):
            self.state_mgr.update_slot_telemetry(
                slot_idx=idx,
                assigned_pid=1000 + idx,
                char_name=f"Hero{idx}",
                level="400",
                coords="125,130",
                server="Sv3",
                map="Lorencia",
                status="Đã kết nối",
                is_running=True,
                class_code="DK",
            )

        self.assertEqual(len(self.state_mgr.slots), 15)
        for idx in range(11, 16):
            slot = self.state_mgr.get_slot(idx)
            self.assertEqual(slot["assigned_pid"], 1000 + idx)
            self.assertEqual(slot["char_name"], f"Hero{idx}")
            self.assertEqual(slot["level"], "400")
            self.assertEqual(slot["server"], "Sv3")
            self.assertEqual(slot["class_code"], "DK")
            self.assertTrue(slot["is_running"])

        dirty = self.state_mgr.get_dirty_slots()
        dirty_ids = {d["slot_idx"] for d in dirty}
        for idx in range(11, 16):
            self.assertIn(idx, dirty_ids)

        # Kiểm tra ngắt kết nối (assigned_pid=None) thực sự xóa PID chứ không bị bỏ qua
        self.state_mgr.update_slot_telemetry(slot_idx=12, assigned_pid=None, char_name="---", status="Game đã đóng")
        slot12 = self.state_mgr.get_slot(12)
        self.assertIsNone(slot12["assigned_pid"])
        self.assertEqual(slot12["char_name"], "---")

        # Xóa slot cuối
        self.state_mgr.remove_slot(15)
        self.assertNotIn(15, self.state_mgr.slots)

    def test_engine_sync_title_parser_and_15_clients(self):
        """build_enhanced_detected_games phải nhận diện đủ tên & server cho 15 cửa sổ MEGAMU."""
        from ui.engine_sync import build_enhanced_detected_games

        raw = {2000 + i: f"CharName{i} (400/10rr) - MEGAMU Sv{(i % 5) + 1}" for i in range(1, 16)}
        enhanced = build_enhanced_detected_games(raw)
        self.assertEqual(len(enhanced), 15)
        for i in range(1, 16):
            pid = 2000 + i
            self.assertIn(f"CharName{i}", enhanced[pid])
            self.assertIn(f"[Sv{(i % 5) + 1}]", enhanced[pid])
            self.assertIn(f"(PID {pid})", enhanced[pid])

    def test_optimized_worker_assign_all_expands_past_10_slots(self):
        """DashboardAppOptimized._worker_assign_all phải tự mở rộng từ 10 lên 15 slots khi có 15 game & License >= 15."""
        from meg_gui_optimized import DashboardAppOptimized

        with patch.object(DashboardAppOptimized, "__init__", lambda self: None):
            app = DashboardAppOptimized()
            app.state_mgr = self.state_mgr
            app.controllers = []
            app.detected_games = {}
            app.log_message = MagicMock()
            app.update_header_stats = MagicMock()
            app.trigger_mirror_ticket_scan = MagicMock()
            app.after = lambda _delay, fn: fn()
            app.train_view = MagicMock()
            app.mirror_view = MagicMock()
            app.moss_view = MagicMock()

            # Tạo 10 slot ban đầu
            def _make_ctrl(idx):
                c = MagicMock()
                c.slot_idx = idx
                c.assigned_pid = None
                c.char_name = "---"
                c.server_name = "---"
                def _attach(pid):
                    c.assigned_pid = pid
                    return True
                c.attach_pid.side_effect = _attach
                return c

            for i in range(1, 11):
                app.controllers.append(_make_ctrl(i))

            def _fake_add_slot(silent=False):
                idx = len(app.controllers) + 1
                c = _make_ctrl(idx)
                app.controllers.append(c)
                app.state_mgr.ensure_slot(idx)
                return c

            app.add_new_slot = MagicMock(side_effect=_fake_add_slot)

            # 15 cửa sổ game đang mở
            raw_games = {3000 + i: f"Acc{i:02d} [Sv3] (PID {3000 + i})" for i in range(1, 16)}

            with patch("meg_gui_optimized.build_enhanced_detected_games", return_value=raw_games), \
                 patch("psutil.pid_exists", return_value=True), \
                 patch("meg_gui_optimized.license_client.load_license_data", return_value={"max_slots": 50}), \
                 patch("meg_gui_optimized.license_client.is_license_valid", return_value=True):
                app._worker_assign_all()

            self.assertEqual(app.add_new_slot.call_count, 5)
            self.assertEqual(len(app.controllers), 15)
            for i in range(1, 16):
                pid = 3000 + i
                self.assertEqual(app.controllers[i - 1].assigned_pid, pid)
                self.assertEqual(app.controllers[i - 1].char_name, f"Acc{i:02d}")
                slot_state = app.state_mgr.get_slot(i)
                self.assertEqual(slot_state["assigned_pid"], pid)
                self.assertEqual(slot_state["char_name"], f"Acc{i:02d}")

    def test_optimized_worker_assign_all_respects_license_limit(self):
        """Khi License chỉ cho 10 slot, không được mở vượt hạn mức License."""
        from meg_gui_optimized import DashboardAppOptimized

        with patch.object(DashboardAppOptimized, "__init__", lambda self: None):
            app = DashboardAppOptimized()
            app.state_mgr = self.state_mgr
            app.controllers = []
            app.log_message = MagicMock()
            app.update_header_stats = MagicMock()
            app.trigger_mirror_ticket_scan = MagicMock()
            app.after = lambda _delay, fn: fn()
            app.train_view = MagicMock()
            app.mirror_view = MagicMock()
            app.moss_view = MagicMock()

            for i in range(1, 11):
                c = MagicMock()
                c.slot_idx = i
                c.assigned_pid = None
                c.char_name = "---"
                c.server_name = "---"
                c.attach_pid.side_effect = lambda pid, ctrl=c: setattr(ctrl, "assigned_pid", pid) or True
                app.controllers.append(c)

            app.add_new_slot = MagicMock()
            raw_games = {4000 + i: f"Acc{i:02d} [Sv3] (PID {4000 + i})" for i in range(1, 13)}

            with patch("meg_gui_optimized.build_enhanced_detected_games", return_value=raw_games), \
                 patch("psutil.pid_exists", return_value=True), \
                 patch("meg_gui_optimized.license_client.load_license_data", return_value={"max_slots": 10}), \
                 patch("meg_gui_optimized.license_client.is_license_valid", return_value=True):
                app._worker_assign_all()

            app.add_new_slot.assert_not_called()
            self.assertEqual(len(app.controllers), 10)
            warn_calls = [args for args, _ in app.log_message.call_args_list if len(args) >= 2 and args[1] == "WARNING"]
            self.assertTrue(any("10 slot" in str(a[0]) for a in warn_calls))


if __name__ == "__main__":
    unittest.main()
