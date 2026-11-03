import unittest
from unittest.mock import MagicMock, patch

class TestAssignAll(unittest.TestCase):
    def test_assign_all_with_flexible_counts(self):
        """Kiểm tra assign_all gán linh hoạt 3, 4, 6, 7, 8... game và tự mở thêm slot."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.slot_ui_elements = {}
            app.detected_games = {}
            app.log_message = MagicMock()
            app.update_header_stats = MagicMock()
            app.refresh_games = MagicMock()
            app.add_new_slot = MagicMock()

            # Giả lập 5 controllers ban đầu
            for i in range(1, 6):
                ctrl = MagicMock()
                ctrl.slot_idx = i
                ctrl.assigned_pid = None
                app.controllers.append(ctrl)

            # Trường hợp 1: Có 3 game mở
            app.detected_games = {101: "MEGAMU (101)", 102: "MEGAMU (102)", 103: "MEGAMU (103)"}
            with patch("psutil.pid_exists", return_value=True), \
                 patch("license_client.load_license_data", return_value={"max_slots": 10}), \
                 patch("license_client.is_license_valid", return_value=True):
                app.assign_all()

            app.controllers[0].attach_pid.assert_called_once_with(101)
            app.controllers[1].attach_pid.assert_called_once_with(102)
            app.controllers[2].attach_pid.assert_called_once_with(103)
            self.assertIsNone(app.controllers[3].attach_pid.call_args)
            print("  -> [PASS] Gán chính xác 3 game vào 3 slot đầu")

    def test_assign_all_auto_expand_slots(self):
        """Kiểm tra khi có 7 game mở mà chỉ có 5 slot thì tự mở thêm 2 slot."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.slot_ui_elements = {}
            app.detected_games = {
                101: "G1", 102: "G2", 103: "G3", 104: "G4",
                105: "G5", 106: "G6", 107: "G7"
            }
            app.log_message = MagicMock()
            app.update_header_stats = MagicMock()
            app.refresh_games = MagicMock()

            # Giả lập 5 controllers ban đầu
            for i in range(1, 6):
                ctrl = MagicMock()
                ctrl.slot_idx = i
                ctrl.assigned_pid = None
                app.controllers.append(ctrl)

            def fake_add_slot():
                idx = len(app.controllers) + 1
                ctrl = MagicMock()
                ctrl.slot_idx = idx
                ctrl.assigned_pid = None
                app.controllers.append(ctrl)

            app.add_new_slot = MagicMock(side_effect=fake_add_slot)

            with patch("psutil.pid_exists", return_value=True), \
                 patch("license_client.load_license_data", return_value={"max_slots": 10}), \
                 patch("license_client.is_license_valid", return_value=True):
                app.assign_all()

            # Kiểm tra đã gọi add_new_slot 2 lần để từ 5 lên 7 slots
            self.assertEqual(app.add_new_slot.call_count, 2)
            self.assertEqual(len(app.controllers), 7)
            for i, pid in enumerate([101, 102, 103, 104, 105, 106, 107]):
                app.controllers[i].attach_pid.assert_called_once_with(pid)
            print("  -> [PASS] Tự động mở rộng từ 5 lên 7 slots và gán đủ 7 game!")

if __name__ == '__main__':
    unittest.main()

