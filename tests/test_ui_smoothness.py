import unittest
from unittest.mock import MagicMock
import os
import sys

# Đảm bảo import được các module dự án
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestUiSmoothness(unittest.TestCase):
    """Kiểm thử tối ưu hóa UI: Dirty-Checking, Lazy Rendering và Persistent Stacking."""

    def setUp(self):
        # Tạo mock app nhẹ mà không khởi chạy Tkinter GUI loop
        self.app = MagicMock()
        self.app.running = True
        self.app._is_resizing = False
        self.app._slot_telemetry_cache = {}
        self.app._logs_dirty = False
        self.app.active_tab = "accounts"
        self.app.after = lambda delay, fn: fn()

        # Tạo slot controller giả lập
        ctrl1 = MagicMock()
        ctrl1.slot_idx = 1
        ctrl1.coords = "120, 150"
        ctrl1.char_name = "KANGzz"
        ctrl1.assigned_pid = 1234
        ctrl1.auto_requested = False
        ctrl1.status = "Đang chạy"
        ctrl1.level = "400"
        ctrl1.points = 1000
        ctrl1.current_resets = 50
        ctrl1.profile_index = 1
        ctrl1.class_code = "MG"

        self.app.controllers = [ctrl1]

    def test_telemetry_dirty_checking_eliminates_redraws(self):
        """When identical telemetry is received, widgets must NOT be reconfigured."""
        from meg_gui import DashboardApp

        mock_coords_lbl = MagicMock()
        mock_lvl_lbl = MagicMock()
        mock_pts_lbl = MagicMock()
        mock_proc_var = MagicMock()
        mock_prog_bar = MagicMock()
        mock_exp_lbl = MagicMock()

        self.app.slot_ui_elements = {
            1: {
                "coords_lbl": mock_coords_lbl,
                "lvl_lbl": mock_lvl_lbl,
                "pts_lbl": mock_pts_lbl,
                "proc_var": mock_proc_var,
                "prog_bar": mock_prog_bar,
                "exp_lbl": mock_exp_lbl,
                "profile_var": MagicMock()
            }
        }

        # First call: Cache is empty -> Updates widgets
        DashboardApp.update_slot_ui_telemetry(self.app, 1, "KANGzz", "400", "120, 150", 1000)
        self.assertEqual(mock_coords_lbl.configure.call_count, 1)
        self.assertEqual(mock_lvl_lbl.configure.call_count, 1)

        # Second call with identical data -> Dirty check prevents configure calls
        DashboardApp.update_slot_ui_telemetry(self.app, 1, "KANGzz", "400", "120, 150", 1000)
        # Call count should STILL be 1 (0 redraws!)
        self.assertEqual(mock_coords_lbl.configure.call_count, 1)
        self.assertEqual(mock_lvl_lbl.configure.call_count, 1)

        # Third call with new coordinates -> Only coords widget updates
        DashboardApp.update_slot_ui_telemetry(self.app, 1, "KANGzz", "400", "125, 150", 1000)
        self.assertEqual(mock_coords_lbl.configure.call_count, 2)
        # Level didn't change -> call count remains 1
        self.assertEqual(mock_lvl_lbl.configure.call_count, 1)

    def test_lazy_tab_rendering_skips_hidden_tabs(self):
        """When user is on 'accounts' tab, telemetry must NOT update moss or mirror slots."""
        from meg_gui import DashboardApp

        self.app.active_tab = "accounts"
        self.app.update_moss_slot_telemetry = MagicMock()
        self.app.update_mirror_slot_telemetry = MagicMock()
        self.app.slot_ui_elements = {1: {"active": True}}

        # Simulate telemetry cycle while on accounts tab
        DashboardApp.update_slot_ui_telemetry(self.app, 1, "KANGzz", "400", "120, 150", 1000)

        # Hidden tabs must NOT receive updates
        self.app.update_moss_slot_telemetry.assert_not_called()
        self.app.update_mirror_slot_telemetry.assert_not_called()

        # Switch to 'moss' tab
        self.app.active_tab = "moss"
        DashboardApp.update_slot_ui_telemetry(self.app, 1, "KANGzz", "400", "120, 150", 1000)
        self.assertEqual(self.app.update_moss_slot_telemetry.call_count, 1)
        self.app.update_mirror_slot_telemetry.assert_not_called()

    def test_lazy_log_rendering_when_tab_inactive(self):
        """When on non-logs tab, render_logs must mark _logs_dirty and NOT touch log_textbox."""
        from meg_gui import DashboardApp

        self.app.active_tab = "accounts"
        self.app.log_textbox = MagicMock()

        DashboardApp.render_logs(self.app)

        self.assertTrue(self.app._logs_dirty)
        self.app.log_textbox.configure.assert_not_called()

    def test_master_run_button_dirty_check(self):
        """update_master_run_button must only configure the button on actual state transition."""
        from meg_gui import DashboardApp

        self.app.btn_master_run = MagicMock()
        self.app.controllers[0].worker = None
        self.app.controllers[0].auto_requested = False

        # First call: All stopped -> configures button to "play"
        DashboardApp.update_master_run_button(self.app)
        self.assertEqual(self.app.btn_master_run.configure.call_count, 1)

        # Repeated call with same state -> 0 redundant configure calls
        DashboardApp.update_master_run_button(self.app)
        self.assertEqual(self.app.btn_master_run.configure.call_count, 1)

        # Transition to running: True -> configures button
        self.app.controllers[0].auto_requested = True
        DashboardApp.update_master_run_button(self.app)
        self.assertEqual(self.app.btn_master_run.configure.call_count, 2)

    def test_switch_tab_uses_tkraise_instantaneously(self):
        """switch_tab must use tkraise() without calling place_forget on previous panel, and open modal for profiles/logs."""
        from meg_gui import DashboardApp

        mock_panel_acc = MagicMock()
        mock_panel_moss = MagicMock()
        self.app.panel_accounts = mock_panel_acc
        self.app.panel_moss = mock_panel_moss
        self.app._tab_panels = {"accounts": mock_panel_acc, "moss": mock_panel_moss}
        self.app.active_tab = "accounts"
        self.app._active_panel = mock_panel_acc

        # Switch to moss panel
        DashboardApp.switch_tab(self.app, "moss")

        # Must call tkraise() on moss
        self.assertEqual(mock_panel_moss.tkraise.call_count, 1)
        # Must NEVER call place_forget on previous panel (Zero-relayout)
        self.assertEqual(mock_panel_acc.place_forget.call_count, 0)
        self.assertEqual(self.app.active_tab, "moss")

        # Calling profiles delegates directly to open_profiles_modal
        self.app.open_profiles_modal = MagicMock()
        DashboardApp.switch_tab(self.app, "profiles")
        self.assertEqual(self.app.open_profiles_modal.call_count, 1)

        # Calling logs delegates directly to open_logs_window
        self.app.open_logs_window = MagicMock()
        DashboardApp.switch_tab(self.app, "logs")
        self.assertEqual(self.app.open_logs_window.call_count, 1)


if __name__ == "__main__":
    unittest.main()
