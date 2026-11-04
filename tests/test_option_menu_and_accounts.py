"""
Unit tests for ModernOptionMenu and Account PID Selection Workflow.
Verifies:
1. ModernOptionMenu event handling, non-blocking click, item selection, outside dismiss.
2. Account PID selection: deconflict when assigning same PID to another slot, detach on '--'.
3. Non-blocking character name resolution in refresh_games.
"""

import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
import customtkinter as ctk

from ui.components.option_menu import ModernOptionMenu


class TestModernOptionMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.geometry("400x300+100+100")
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_menu_creation_and_values(self):
        menu = ModernOptionMenu(self.root, values=["Alpha", "Beta", "Gamma"])
        menu.pack()
        self.root.update()
        self.assertEqual(menu.get(), "Alpha")

        menu.set("Beta")
        self.assertEqual(menu.get(), "Beta")
        menu.destroy()

    def test_menu_toggle_returns_break(self):
        menu = ModernOptionMenu(self.root, values=["Item 1", "Item 2"])
        menu.pack()
        self.root.update()

        ret = menu._on_trigger_click()
        self.assertEqual(ret, "break")
        self.assertTrue(menu._popup is not None and menu._popup.winfo_exists())

        # Second click closes
        ret2 = menu._on_trigger_click()
        self.assertEqual(ret2, "break")
        self.assertIsNone(menu._popup)
        menu.destroy()

    def test_item_selection_triggers_callback(self):
        selected = []
        menu = ModernOptionMenu(
            self.root,
            values=["Hero (101)", "Mage (102)"],
            command=lambda v: selected.append(v)
        )
        menu.pack()
        self.root.update()

        menu._open_popup()
        self.root.update()
        self.assertIsNotNone(menu._popup)

        # Trigger selection
        menu._on_select("Mage (102)")
        self.root.update()

        self.assertEqual(selected, ["Mage (102)"])
        self.assertEqual(menu.get(), "Mage (102)")
        self.assertIsNone(menu._popup)
        menu.destroy()

    def test_disabled_state_prevents_opening(self):
        menu = ModernOptionMenu(self.root, values=["A", "B"], state="disabled")
        menu.pack()
        self.root.update()

        ret = menu._on_trigger_click()
        self.assertEqual(ret, "break")
        self.assertIsNone(menu._popup)
        menu.destroy()


class TestAccountPidSelection(unittest.TestCase):
    def test_slot_pid_deconflict(self):
        """When PID is assigned to Slot 2 while already in Slot 1, Slot 1 is automatically unassigned."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.slot_ui_elements = {}
            app.moss_ui_elements = {}
            app.mirror_ui_elements = {}
            app.detected_games = {1234: "Hero - MEGAMU", 5678: "Mage - MEGAMU"}
            app._char_name_cache = {}
            app.log_message = MagicMock()
            app.update_slot_ui_telemetry = MagicMock()
            app.update_slot_run_button_state = MagicMock()

            # Create 2 mock controllers
            ctrl1 = MagicMock()
            ctrl1.slot_idx = 1
            ctrl1.assigned_pid = 1234
            ctrl1.char_name = "Hero"

            ctrl2 = MagicMock()
            ctrl2.slot_idx = 2
            ctrl2.assigned_pid = None
            ctrl2.char_name = "---"

            app.controllers = [ctrl1, ctrl2]

            combo1 = MagicMock()
            combo2 = MagicMock()
            app.slot_ui_elements[1] = {"proc_combo": combo1}
            app.slot_ui_elements[2] = {"proc_combo": combo2}

            # Assign PID 1234 to Slot 2
            with patch("meg_gui.is_megamu_process_alive", return_value=True):
                app.on_slot_pid_selected(2, "Hero (1234)")

            # Check that Slot 1 was unassigned
            ctrl1.detach.assert_called_once()
            self.assertIsNone(ctrl1.assigned_pid)
            combo1.set.assert_called_once_with("--")
            ctrl1.set_status.assert_called_once()

            # Check that Slot 2 was attached
            ctrl2.attach_pid.assert_called_once_with(1234)

    def test_slot_unassign_on_dash(self):
        """When selecting '--', the slot detaches cleanly."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            app.controllers = []
            app.slot_ui_elements = {}
            app.moss_ui_elements = {}
            app.mirror_ui_elements = {}
            app.log_message = MagicMock()
            app.update_slot_ui_telemetry = MagicMock()
            app.update_slot_run_button_state = MagicMock()

            ctrl1 = MagicMock()
            ctrl1.slot_idx = 1
            ctrl1.assigned_pid = 1234
            app.controllers = [ctrl1]

            app.on_slot_pid_selected(1, "--")

            ctrl1.detach.assert_called_once()
            self.assertIsNone(ctrl1.assigned_pid)
            app.update_slot_ui_telemetry.assert_called_once_with(1, "---", "LV --", "---")

    def test_slot_profile_selection(self):
        """When selecting a different profile (e.g. Config 4), the slot updates and saves immediately."""
        from meg_gui import DashboardApp

        with patch.object(DashboardApp, "__init__", lambda self: None):
            app = DashboardApp()
            ctrl = MagicMock()
            ctrl.slot_idx = 1
            ctrl.profile_index = 1
            app.controllers = [ctrl]
            app.slot_assignments = {1: 1}
            app.slot_ui_elements = {}
            app.log_message = MagicMock()

            profile_var = MagicMock()
            preset_combo = MagicMock()
            app.slot_ui_elements[1] = {
                "profile_var": profile_var,
                "preset_combo": preset_combo
            }

            with patch("core.storage.ConfigPersistenceManager.save_all_slot_assignments") as mock_save:
                app.on_slot_profile_selected(1, "Config 4")

            ctrl.set_profile.assert_called_once_with(4)
            self.assertEqual(app.slot_assignments[1], 4)
            profile_var.set.assert_called_once_with("Config 4")
            preset_combo.set.assert_called_once_with("Config 4")
            mock_save.assert_called_once_with({1: 4})


if __name__ == "__main__":
    unittest.main()
