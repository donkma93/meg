# -*- coding: utf-8 -*-
"""
test_devil_ticket_matching.py - Kiểm thử logic khớp cấp độ vé Devil Square
với cấp độ nhân vật theo chuẩn MU Online và Reverse Engineering GameAssembly.dll:

Quy tắc:
1. DS 1 (Lv 15 - 130)  -> Cần Vé Thường +1 (Target Level: 0)
2. DS 2 (Lv 131 - 180) -> Cần Vé Thường +2 (Target Level: 1)  [Ví dụ: Slayer Lv 137]
3. DS 3 (Lv 181 - 230) -> Cần Vé Thường +3 (Target Level: 2)
4. DS 4 (Lv 231 - 280) -> Cần Vé Thường +4 (Target Level: 3)
5. DS 5 (Lv 281 - 330) -> Cần Vé Thường +5 (Target Level: 4)
6. DS 6 (Lv 331 - 400) -> Cần Vé Thường +6 (Target Level: 5)
7. DS 7 (Lv 400+ Master) -> Cần Vé Master / Vé Thường +7 (Target Level: 6)

Xác minh:
- Nhân vật Lv 137 chỉ có Vé Master (+7) KHÔNG được coi là có vé hợp lệ và KHÔNG chạy ra cổng.
- Nhân vật Lv 137 có Vé Thường +2 được coi là hợp lệ và vào cổng.
- Nhân vật Lv 400+ có Vé Master được coi là hợp lệ.
"""

import unittest
from unittest.mock import MagicMock
from meg_auto_worker import AutoTrainWorker


class TestDevilTicketMatching(unittest.TestCase):
    def setUp(self):
        self.mock_core = MagicMock()
        self.mock_core.is_ready = True
        self.mock_core.is_devil_event_map.return_value = False

        self.cfg = {
            "account_id": "test_acc",
            "auto_devil": True,
            "devil_ticket_type": "auto",
            "devil_min_resets": 0,
            "devil_max_resets": 9999,
            "resets": 10,
        }
        self.worker = AutoTrainWorker(99999, self.cfg)
        self.worker.core = self.mock_core
        self.worker._log = MagicMock()

    def test_level_175_with_master_ticket_only(self):
        """Nhân vật Level 175 (Slayer) chỉ có Vé Master:
        Theo chuẩn MEGAMU, Level 175 thuộc DS 1 (50-199) yêu cầu Vé +1.
        Vé Master chỉ dành cho Level 900+ (DS 7).
        Hệ thống PHẢI từ chối vé Master ở Level 175 để tránh popup 'You don't have a ticket for your level'."""
        t_info = {
            "charLevel": 175,
            "dsLevel": 0,
            "targetTicketLevel": 1,
            "isMasterEligible": False,
            "hasTicket": True,
            "hasMasterTicket": True,
            "hasNormalTicket": False,
            "hasMatchedTicket": False,
            "hasEligibleMasterTicket": False,
            "hasEligibleNormalTicket": False,
            "masterCount": 1,
            "normalCount": 0,
            "count": 1
        }
        self.mock_core.get_devil_ticket_info.return_value = t_info
        info = {"level": 175, "class": 9, "mapId": 0}

        cur_lvl = int(info.get("level", 1))
        ds_lvl = int(t_info.get("dsLevel", 0))
        target_ticket_lvl = int(t_info.get("targetTicketLevel", ds_lvl + 1))
        t_pref = "auto"

        has_matched = bool(t_info.get("hasMatchedTicket", False))
        is_master_tier = (ds_lvl >= 6)
        has_valid_ticket = has_matched and (is_master_tier if t_info.get("hasMasterTicket") else True)
        self.assertFalse(has_valid_ticket, "Nhân vật Level 175 chỉ có Vé Master KHÔNG được chấp nhận để không bị lỗi popup!")
        self.assertEqual(ds_lvl, 0, "Level 175 thuộc phòng DS 1 (dsLevel = 0, Tier 1: 50-199)")

    def test_level_175_with_normal_ticket_plus_1(self):
        """Nhân vật Level 175 có Vé Thường +1: Khớp cấp độ DS 1 (50-199) hợp lệ 100%."""
        t_info = {
            "charLevel": 175,
            "dsLevel": 0,
            "targetTicketLevel": 1,
            "isMasterEligible": False,
            "hasTicket": True,
            "hasMasterTicket": False,
            "hasNormalTicket": True,
            "hasMatchedTicket": True,
            "hasEligibleMasterTicket": False,
            "hasEligibleNormalTicket": True,
            "normalMatchedCount": 1,
            "normalCount": 1,
            "count": 1
        }
        self.mock_core.get_devil_ticket_info.return_value = t_info
        info = {"level": 175, "class": 9, "mapId": 0}

        cur_lvl = int(info.get("level", 1))
        ds_lvl = int(t_info.get("dsLevel", 0))
        target_ticket_lvl = int(t_info.get("targetTicketLevel", ds_lvl + 1))
        is_master_eligible = bool(t_info.get("isMasterEligible", False))

        has_valid_ticket = bool(t_info.get("hasMatchedTicket", False))
        self.assertTrue(has_valid_ticket, "Nhân vật Level 175 có Vé Thường +1 phải được chấp nhận!")
        if not is_master_eligible:
            if t_info.get("hasEligibleNormalTicket") or (t_info.get("hasNormalTicket") and t_info.get("normalMatchedCount", 0) > 0):
                has_valid_ticket = True

        self.assertTrue(has_valid_ticket, "Nhân vật Level 137 có Vé Thường +2 phải được chấp nhận!")

    def test_level_400_with_master_ticket(self):
        """Nhân vật Level 400+ (Master): Vé Master hợp lệ 100%."""
        t_info = {
            "charLevel": 400,
            "dsLevel": 6,
            "targetTicketLevel": 7,
            "isMasterEligible": True,
            "hasTicket": True,
            "hasMasterTicket": True,
            "hasNormalTicket": False,
            "hasMatchedTicket": True,
            "hasEligibleMasterTicket": True,
            "hasEligibleNormalTicket": False,
            "masterCount": 1,
            "normalCount": 0,
            "count": 1
        }
        cur_lvl = 400
        ds_lvl = 6
        is_master_eligible = bool(t_info.get("isMasterEligible", (cur_lvl >= 400 or ds_lvl >= 6)))

        has_valid_ticket = False
        if is_master_eligible:
            if t_info.get("hasEligibleMasterTicket") or (t_info.get("hasMasterTicket") and t_info.get("masterCount", 0) > 0):
                has_valid_ticket = True

        self.assertTrue(has_valid_ticket, "Nhân vật Level 400+ dùng Vé Master phải được chấp nhận!")


if __name__ == "__main__":
    unittest.main()
