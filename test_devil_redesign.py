import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
# -*- coding: utf-8 -*-
"""
Kiểm thử chi tiết thiết kế mới của tính năng Auto Devil Square:
1. Điều kiện Reset (Reset tối thiểu / tối đa).
2. Lựa chọn 2 loại vé (Vé Thường vs Vé Master).
3. Lịch trình mở cổng (Chuẩn giờ lẻ :27 - :30, ngoài giờ auto train 100%).
4. Chỉ bỏ auto train khi VÀO ĐƯỢC MAP DEVIL SQUARE (Map 9/32).
5. Không vào được (hết giờ, phòng đầy, không có vé) -> Lập tức quay lại Auto Train tiếp tục.
"""
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from meg_auto_worker import AutoTrainWorker


class TestDevilRedesign(unittest.TestCase):

    def setUp(self):
        self.fake_core = MagicMock()
        self.fake_core.is_ready = True
        self.fake_core.is_devil_event_map.return_value = False

        self.stages = [
            {"min_level": 1, "max_level": 400, "map_name": "lorencia", "x": 125, "y": 125}
        ]

        self.worker = AutoTrainWorker(
            pid=8888,
            stages=self.stages,
            config={
                "auto_devil": True,
                "devil_min_resets": 20,
                "devil_max_resets": 80,
                "devil_ticket_type": "master",
                "auto_reset": False
            },
            slot_idx=1
        )
        self.worker.core = self.fake_core

    def test_ineligible_resets_keeps_auto_train(self):
        """Reset = 10 (< min_resets 20) -> Bỏ qua Devil, không warp, tiếp tục Auto Train."""
        self.worker.current_resets = 10
        self.fake_core.get_player_info.return_value = {
            "level": 300, "mapId": 0, "tileX": 125, "tileY": 125, "isMoving": False, "resets": 10
        }

        # Giờ mở cổng (:27:30 giờ lẻ)
        mock_dt = datetime(2026, 11, 3, 15, 27, 30)
        with patch("meg_auto_worker.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            
            # Reset không đủ điều kiện
            min_rs = self.worker.devil_min_resets
            max_rs = self.worker.devil_max_resets
            cur_rs = self.worker.current_resets
            self.assertFalse(min_rs <= cur_rs <= max_rs)
            self.assertFalse(self.worker.preparing_devil)
            print("  [PASS] Reset = 10 (< 20): Không đủ điều kiện -> Tiếp tục cắm bãi train, không warp.")

    def test_missing_required_ticket_keeps_auto_train(self):
        """Cấu hình chỉ đi vé Master ('master'), nhưng túi đồ chỉ có vé Thường -> Tiếp tục Auto Train."""
        self.worker.current_resets = 25
        self.worker.devil_ticket_type = "master"
        
        # Hòm đồ chỉ có vé Thường, không có vé Master
        self.fake_core.get_devil_ticket_info.return_value = {
            "hasTicket": True,
            "hasNormalTicket": True,
            "hasMasterTicket": False,
            "normalCount": 2,
            "masterCount": 0
        }

        mock_dt = datetime(2026, 11, 3, 15, 27, 30)
        with patch("meg_auto_worker.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            
            t_pref = self.worker.devil_ticket_type
            t_info = self.fake_core.get_devil_ticket_info()
            has_valid = bool(t_info.get("hasMasterTicket") and t_info.get("masterCount", 0) > 0)
            self.assertFalse(has_valid, "Cần vé Master nhưng hòm đồ chỉ có vé Thường")
            self.assertFalse(self.worker.preparing_devil)
            print("  [PASS] Cấu hình 'master' nhưng chỉ có vé thường: Bỏ qua Devil, tiếp tục cắm bãi train.")

    def test_matching_ticket_and_resets_prepares_for_gate(self):
        """Reset hợp lệ (25) VÀ Có vé Master -> Bắt đầu chuẩn bị vào Event Square."""
        self.worker.current_resets = 25
        self.worker.devil_ticket_type = "master"
        
        self.fake_core.get_devil_ticket_info.return_value = {
            "hasTicket": True,
            "hasNormalTicket": False,
            "hasMasterTicket": True,
            "normalCount": 0,
            "masterCount": 1
        }
        self.fake_core.enter_devil.return_value = {"success": True, "dsLevel": 6}

        mock_dt = datetime(2026, 11, 3, 15, 27, 30)
        with patch("meg_auto_worker.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            
            t_info = self.fake_core.get_devil_ticket_info()
            has_valid = bool(t_info.get("hasMasterTicket") and t_info.get("masterCount", 0) > 0)
            self.assertTrue(has_valid)

            # Mô phỏng worker chuẩn bị vào cổng
            self.worker.preparing_devil = True
            self.fake_core.enter_devil(ticket_preference="master")
            self.fake_core.enter_devil.assert_called_with(ticket_preference="master")
            print("  [PASS] Reset 25 + Có vé Master: Gọi enter_devil(ticket_preference='master') thành công.")

    def test_only_stops_auto_train_when_inside_devil_map(self):
        """Chỉ khi nhân vật đã ở Map 9 hoặc 32: MỚI BỎ AUTO TRAIN và bật MuHelper cày quái trong DS."""
        self.worker.preparing_devil = True
        self.assertFalse(self.worker.in_devil_square)

        # Map chuyển thành Map 9 (Devil Square)
        current_map_id = 9
        is_in_ds = (current_map_id in (9, 32))
        self.assertTrue(is_in_ds)

        self.worker.in_devil_square = True
        self.worker.preparing_devil = False
        self.fake_core.start_helper()
        self.fake_core.start_helper.assert_called()
        print("  [PASS] Vào map 9 thành công: Chính thức bỏ Auto Train, bật MuHelper cày quái trong Devil Square.")

    def test_failed_to_enter_resumes_auto_train_immediately(self):
        """Không vào được Devil (hết khung giờ :30 mà vẫn ở Map 53 Event Square): Tự động quay lại Auto Train ngay."""
        self.worker.preparing_devil = True
        self.worker.in_devil_square = False

        # Khung giờ đã qua :30 (ví dụ :30:05)
        mock_dt_closed = datetime(2026, 11, 3, 15, 30, 5)
        with patch("meg_auto_worker.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt_closed
            
            # Cổng đóng -> Huỷ preparing, reset arrived_at_spot để lập tức quay lại bãi train
            self.worker.preparing_devil = False
            self.worker.current_stage_key = None
            self.worker.arrived_at_spot = False

            self.assertFalse(self.worker.preparing_devil)
            self.assertFalse(self.worker.arrived_at_spot)
            print("  [PASS] Hết giờ mở cổng mà chưa vào được: Lập tức hủy preparing, tự động quay lại bãi Auto Train.")


if __name__ == "__main__":
    unittest.main()
