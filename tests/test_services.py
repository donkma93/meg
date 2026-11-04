"""
Unit tests for Phase 3 Domain Services:
TrainService, DevilService, MossService, MirrorService.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.devil_service import DevilService
from services.moss_service import MossService
from services.mirror_service import MirrorService
from services.train_service import TrainService


class TestDevilService(unittest.TestCase):
    def test_devil_schedule_gate_open(self):
        """At 15:28:00, Devil Square gate should be OPEN."""
        dt_open = datetime(2026, 11, 4, 15, 28, 0)
        is_open, rem_min, desc = DevilService.is_devil_schedule(dt_open)
        self.assertTrue(is_open)
        self.assertEqual(rem_min, 0)
        self.assertIn("ĐANG MỞ", desc)

    def test_devil_schedule_waiting(self):
        """At 15:10:00, Devil Square gate should be waiting for 17 minutes."""
        dt_wait = datetime(2026, 11, 4, 15, 10, 0)
        is_open, rem_min, desc = DevilService.is_devil_schedule(dt_wait)
        self.assertFalse(is_open)
        self.assertEqual(rem_min, 17)

    def test_resets_eligibility(self):
        """Test reset boundary verification."""
        self.assertTrue(DevilService.check_resets_eligibility(current_resets=25, min_resets=20, max_resets=80))
        self.assertFalse(DevilService.check_resets_eligibility(current_resets=10, min_resets=20, max_resets=80))
        self.assertFalse(DevilService.check_resets_eligibility(current_resets=85, min_resets=20, max_resets=80))
        # Default max_resets=0 should mean unlimited (9999)
        self.assertTrue(DevilService.check_resets_eligibility(current_resets=500, min_resets=10, max_resets=0))

    def test_ticket_eligibility_preference(self):
        """Test ticket requirements for normal vs master tickets."""
        mock_engine = MagicMock()
        mock_engine.get_devil_ticket_info.return_value = {
            "hasTicket": True,
            "hasNormalTicket": True,
            "hasMasterTicket": False,
            "normalCount": 3,
            "masterCount": 0
        }

        # 1. Requiring master ticket when only normal ticket is present -> False
        valid, t_type, _ = DevilService.check_ticket_eligibility(mock_engine, ticket_preference="master")
        self.assertFalse(valid)
        self.assertEqual(t_type, "none")

        # 2. Requiring normal ticket -> True
        valid, t_type, _ = DevilService.check_ticket_eligibility(mock_engine, ticket_preference="normal")
        self.assertTrue(valid)
        self.assertEqual(t_type, "normal")

        # 3. Requiring auto -> falls back to normal
        valid, t_type, _ = DevilService.check_ticket_eligibility(mock_engine, ticket_preference="auto")
        self.assertTrue(valid)
        self.assertEqual(t_type, "normal")

    def test_is_in_devil_map(self):
        self.assertTrue(DevilService.is_in_devil_map(9))
        self.assertTrue(DevilService.is_in_devil_map(32))
        self.assertFalse(DevilService.is_in_devil_map(0))
        self.assertFalse(DevilService.is_in_devil_map(80))


class TestMossService(unittest.TestCase):
    def test_moss_categories(self):
        self.assertEqual(MossService.get_category_name(0), "Vũ Khí 1 Tay (1H Weapons)")
        self.assertEqual(MossService.get_category_name(2), "Gậy Phép (Staves)")
        self.assertEqual(MossService.get_category_name(10), "Trang Sức (Accessories)")

    def test_moss_schedule_active(self):
        """At 06:18:00, Moss event is active (between 06:15 and 06:30)."""
        dt_active = datetime(2026, 11, 4, 6, 18, 0)
        is_active, rem_m, desc = MossService.get_next_moss_schedule(dt_active)
        self.assertTrue(is_active)
        self.assertIn("ĐANG DIỄN RA", desc)

    def test_moss_schedule_waiting(self):
        """At 05:00:00, Moss next schedule is at 06:15 (75 minutes)."""
        dt_wait = datetime(2026, 11, 4, 5, 0, 0)
        is_active, rem_m, desc = MossService.get_next_moss_schedule(dt_wait)
        self.assertFalse(is_active)
        self.assertEqual(rem_m, 75)

    def test_moss_slot_lifecycle(self):
        moss_svc = MossService.get_instance()
        moss_svc._running_slots[1] = True
        self.assertTrue(moss_svc.is_slot_running(1))
        moss_svc.stop_slot_moss(1)
        self.assertFalse(moss_svc.is_slot_running(1))


class TestMirrorService(unittest.TestCase):
    def test_mirror_schedule_states(self):
        # 14:12:00 -> PREP (10 <= m < 15 of even hour 14)
        dt_prep = datetime(2026, 11, 4, 14, 12, 0)
        state, rem_s, desc = MirrorService.get_schedule_state(dt_prep)
        self.assertEqual(state, "PREP")
        self.assertEqual(rem_s, 180)  # 3 minutes left to 14:15

        # 14:18:00 -> GATE_OPEN (15 <= m < 25 of even hour 14)
        dt_open = datetime(2026, 11, 4, 14, 18, 0)
        state, rem_s, desc = MirrorService.get_schedule_state(dt_open)
        self.assertEqual(state, "GATE_OPEN")

        # 14:35:00 -> WAITING (waiting for next even hour 16:10)
        dt_wait = datetime(2026, 11, 4, 14, 35, 0)
        state, rem_s, desc = MirrorService.get_schedule_state(dt_wait)
        self.assertEqual(state, "WAITING")

    def test_is_in_mirror_dungeon(self):
        for m_id in (65, 66, 67, 68):
            self.assertTrue(MirrorService.is_in_mirror_dungeon(m_id))
        self.assertFalse(MirrorService.is_in_mirror_dungeon(0))
        self.assertFalse(MirrorService.is_in_mirror_dungeon(9))

    def test_check_mirror_ticket(self):
        mock_engine = MagicMock()
        mock_engine.count_item.return_value = 2
        res = MirrorService.check_mirror_ticket(mock_engine)
        self.assertTrue(res["has_ticket"])
        self.assertEqual(res["count"], 2)


class TestTrainService(unittest.TestCase):
    def test_train_service_singleton(self):
        svc1 = TrainService.get_instance()
        svc2 = TrainService.get_instance()
        self.assertIs(svc1, svc2)

    @patch("services.train_service.AutoTrainWorker")
    def test_worker_management(self, mock_worker_cls):
        mock_worker = MagicMock()
        mock_worker.running = True
        mock_worker_cls.return_value = mock_worker

        svc = TrainService()
        worker = svc.start_train_worker(
            slot_idx=1,
            pid=1234,
            stages=[{"map_name": "Lorencia", "min_level": 1, "max_level": 400}],
            config={"auto_devil": False}
        )
        self.assertTrue(svc.is_worker_running(1))
        self.assertIs(svc.get_worker(1), worker)

        svc.pause_train_worker(1, reason="Test Pause")
        mock_worker.pause_for_event.assert_called_with(reason="Test Pause")

        svc.resume_train_worker(1, reason="Test Resume")
        mock_worker.resume_from_event.assert_called_with(reason="Test Resume")

        svc.stop_train_worker(1, reason="Test Stop")
        mock_worker.stop.assert_called_with(reason="Test Stop")
        self.assertFalse(svc.is_worker_running(1))


if __name__ == "__main__":
    unittest.main()

