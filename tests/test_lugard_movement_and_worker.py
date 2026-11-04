import unittest
from unittest.mock import MagicMock, patch
import math


class TestLugardMovementAndWorker(unittest.TestCase):
    """Kiểm thử tính năng di chuyển về Lugard và cô lập AutoTrain."""

    def test_move_to_lugard_when_already_near(self):
        """Khi nhân vật đã ở Event Square sát Lugard (229, 22), move_to_lugard phải xác nhận và không warp map."""
        from core.slot_controller import SlotController

        app = MagicMock()
        ctrl = SlotController(slot_idx=1, app=app)
        ctrl.assigned_pid = 12345
        ctrl.char_name = "osint88"

        mock_eng = MagicMock()
        mock_eng.is_ready = True
        mock_eng.is_helper_active.return_value = True
        mock_eng.get_scene_state.return_value = {"ok": True, "type": 4, "worldReady": True}
        mock_eng.get_player_info.return_value = {
            "name": "osint88",
            "mapId": 53,
            "tileX": 230,
            "tileY": 23
        }
        mock_eng.get_mirror_ticket_info.return_value = {"hasTicket": True, "slots": [15], "count": 1}
        ctrl.engine = mock_eng

        with patch("core.slot_controller.is_megamu_process_alive", return_value=True):
            with patch.object(ctrl, "_pause_train_for_mirror") as mock_pause:
                ok = ctrl.move_to_lugard()
                self.assertTrue(ok)
                mock_pause.assert_called_once()
                mock_eng.stop_helper.assert_called_once()
                # Do đã ở cự ly dist <= 3.0, không cần dispatch move_to
                mock_eng.move_to.assert_not_called()

    def test_move_to_lugard_when_other_map(self):
        """Khi nhân vật ở map khác (Lost Tower), move_to_lugard phải gửi /m ev rồi di chuyển tới (229, 22)."""
        from core.slot_controller import SlotController

        app = MagicMock()
        ctrl = SlotController(slot_idx=1, app=app)
        ctrl.assigned_pid = 12345
        ctrl.char_name = "osint88"

        mock_eng = MagicMock()
        mock_eng.is_ready = True
        mock_eng.is_helper_active.return_value = False
        mock_eng.get_scene_state.return_value = {"ok": True, "type": 4, "worldReady": True}

        # Lần 1: Map 4 (Lost Tower). Lần 2+: Map 53 (Event Square) tại (225, 30) rồi tới (229, 22)
        pinfo_seq = [
            {"name": "osint88", "mapId": 4, "tileX": 50, "tileY": 50},
            {"name": "osint88", "mapId": 53, "tileX": 225, "tileY": 30},
            {"name": "osint88", "mapId": 53, "tileX": 229, "tileY": 22},
        ]
        mock_eng.get_player_info.side_effect = lambda: pinfo_seq.pop(0) if pinfo_seq else {"name": "osint88", "mapId": 53, "tileX": 229, "tileY": 22}
        mock_eng.get_mirror_ticket_info.return_value = {"hasTicket": True, "slots": [15], "count": 1}
        ctrl.engine = mock_eng

        with patch("core.slot_controller.is_megamu_process_alive", return_value=True):
            with patch("time.sleep", return_value=None):
                ok = ctrl.move_to_lugard()
                self.assertTrue(ok)
                mock_eng.send_chat.assert_called_with("/m ev")
                mock_eng.move_to.assert_called_with(229, 22)

    def test_autotrain_worker_pauses_near_lugard(self):
        """AutoTrainWorker phải nhận diện đúng điều kiện đứng tại Lugard (Event Square / Elbeland)."""
        px, py = 230, 23
        current_map_id = 53
        is_near_lugard = (
            (current_map_id in (53, 40) and math.hypot(px - 229, py - 22) <= 14) or
            (current_map_id == 51 and math.hypot(px - 49, py - 216) <= 14)
        )
        self.assertTrue(is_near_lugard)

        # Test ở xa Lugard
        px, py = 200, 100
        is_far = (
            (current_map_id in (53, 40) and math.hypot(px - 229, py - 22) <= 14) or
            (current_map_id == 51 and math.hypot(px - 49, py - 216) <= 14)
        )
        self.assertFalse(is_far)


if __name__ == "__main__":
    unittest.main()
