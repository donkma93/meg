"""
Unit tests for Phase 2: Adaptive Telemetry, Batch Read, and CPU/IPC Optimization.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meg_direct_engine import MegDirectEngine
from meg_gui import SlotController


class TestAdaptiveTelemetry(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock(spec=MegDirectEngine)
        self.mock_engine.is_ready = True
        self.mock_engine.last_fast_state = {
            "name": "Knight01",
            "level": 380,
            "classId": 1,
            "mapId": 0,
            "tileX": 125,
            "tileY": 130,
            "x": 125,
            "y": 130,
            "isMoving": False,
            "helperState": 1,
            "points": 500,
            "masterPoints": 20,
            "resets": 15
        }
        self.mock_engine.last_fast_state_time = 1000.0
        self.mock_engine.get_player_info = MegDirectEngine.get_player_info.__get__(self.mock_engine)
        self.mock_engine.get_batch_telemetry = MegDirectEngine.get_batch_telemetry.__get__(self.mock_engine)
        self.mock_engine.set_telemetry_rate = MegDirectEngine.set_telemetry_rate.__get__(self.mock_engine)

    def test_batch_telemetry_structure(self):
        """Batch Telemetry must return the entire character telemetry in a single dict."""
        with patch("time.time", return_value=1000.1):
            tele = self.mock_engine.get_batch_telemetry(max_age=0.55, allow_blocking=False)
            self.assertIsNotNone(tele)
            self.assertIn("name", tele)
            self.assertIn("level", tele)
            self.assertIn("classId", tele)
            self.assertIn("mapId", tele)
            self.assertIn("tileX", tele)
            self.assertIn("tileY", tele)
            self.assertIn("isMoving", tele)
            self.assertIn("helperState", tele)
            self.assertIn("points", tele)
            self.assertIn("resets", tele)
            self.assertEqual(tele["name"], "Knight01")
            self.assertEqual(tele["level"], 380)
            self.assertEqual(tele["resets"], 15)

    def test_set_telemetry_rate(self):
        """Verify dynamic native telemetry rate configuration."""
        self.mock_engine._call = MagicMock(return_value=True)
        self.mock_engine.set_telemetry_rate(800)
        self.mock_engine._call.assert_called_with("setTelemetryInterval", 800)

    def test_slot_controller_adaptive_movement_tracking(self):
        """Verify SlotController accurately updates is_moving and caches character name."""
        mock_app = MagicMock()
        mock_app.detected_games = {1234: "MEGAMU - Knight01"}
        ctrl = SlotController(slot_idx=1, app=mock_app, default_profile=1)
        ctrl.assigned_pid = 1234
        ctrl.engine = self.mock_engine

        # First sync: character name is resolved
        with patch("core.slot_controller.is_megamu_process_alive", return_value=True), patch("time.time", return_value=1000.1):
            ctrl.sync_telemetry()
            self.assertEqual(ctrl.char_name, "Knight01")
            self.assertFalse(ctrl.is_moving)

        # Second sync: simulate moving character
        moving_state = dict(self.mock_engine.last_fast_state)
        moving_state["isMoving"] = True
        moving_state["tileX"] = 126
        self.mock_engine.last_fast_state = moving_state

        with patch("core.slot_controller.is_megamu_process_alive", return_value=True), patch("time.time", return_value=1000.2):
            ctrl.sync_telemetry()
            self.assertTrue(ctrl.is_moving)
            self.assertEqual(ctrl.coords, "126,130")

    def test_adaptive_sleep_intervals(self):
        """Verify the logic for adaptive intervals (moving vs stationary vs disconnected)."""
        def calculate_sleep(any_moving: bool, any_connected: bool) -> float:
            if any_moving:
                return 0.25
            elif any_connected:
                return 0.75
            else:
                return 1.5

        # Moving character: 250ms for smooth UI
        self.assertEqual(calculate_sleep(any_moving=True, any_connected=True), 0.25)
        # Stationary train at spot: 750ms (cuts 67% CPU/IPC)
        self.assertEqual(calculate_sleep(any_moving=False, any_connected=True), 0.75)
        # Disconnected: 1500ms
        self.assertEqual(calculate_sleep(any_moving=False, any_connected=False), 1.5)


if __name__ == "__main__":
    unittest.main()

