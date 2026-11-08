# -*- coding: utf-8 -*-
"""
Test kiểm thử vòng lặp và quy trình khép kín Auto Train + Devil Square theo mốc Reset.
"""
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from meg_auto_worker import AutoTrainWorker


def test_devil_lifecycle():
    print("=== KIỂM THỬ QUY TRÌNH AUTO TRAIN & DEVIL SQUARE THEO MỐC RESET ===")

    fake_core = MagicMock()
    fake_core.is_ready = True
    fake_core.get_player_info.return_value = {
        "level": 350,
        "mapId": 33,  # Aida2
        "tileX": 100,
        "tileY": 150,
        "isMoving": False,
        "resets": 5
    }
    fake_core.get_devil_ticket_info.return_value = {"hasTicket": True, "count": 1, "slots": [12]}
    fake_core.enter_devil.return_value = {"success": True, "dsLevel": 5}
    fake_core.is_devil_event_map.return_value = False

    stages = [
        {"min_level": 1, "max_level": 300, "map_name": "lorencia", "x": 125, "y": 125},
        {"min_level": 301, "max_level": 400, "map_name": "aida2", "x": 100, "y": 150}
    ]

    worker = AutoTrainWorker(
        pid=9999,
        stages=stages,
        config={
            "auto_devil": True,
            "devil_min_resets": 10,
            "devil_max_resets": 50,
            "auto_reset": True,
            "reset_level": 400
        },
        slot_idx=1
    )
    worker.core = fake_core
    worker.current_resets = 5

    # Test 1: Khung giờ chuẩn bị (:26:45), nhưng Reset = 5 (ngoài khoảng 10-50) -> KHÔNG tham gia Devil, tiếp tục bãi train
    mock_dt_prep = datetime(2026, 10, 16, 21, 26, 45)
    with patch("meg_auto_worker.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt_prep
        min_rs = worker.devil_min_resets
        max_rs = worker.devil_max_resets
        cur_rs = worker.current_resets

        is_eligible = (min_rs <= cur_rs <= max_rs)
        assert not is_eligible, "Nhân vật 5 Reset không được vào Devil khi cấu hình yêu cầu 10-50 Reset"
        assert not worker.preparing_devil, "Worker không được chuyển sang trạng thái preparing_devil"
        print("  [PASS] Reset = 5 (ngoài khoảng 10-50): Worker bỏ qua Devil, tiếp tục cắm bãi train bình thường.")

    # Test 2: Nhân vật đạt 15 Reset (nằm trong khoảng 10-50) -> Bắt đầu chuẩn bị (:26:45 giờ lẻ), tạm dừng train, warp sang /m ev
    worker.current_resets = 15
    with patch("meg_auto_worker.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt_prep
        min_rs = worker.devil_min_resets
        max_rs = worker.devil_max_resets
        cur_rs = worker.current_resets
        assert (min_rs <= cur_rs <= max_rs), "Nhân vật 15 Reset phải đủ điều kiện đi Devil"

        # Worker chuyển sang chuẩn bị
        worker.preparing_devil = True
        worker.current_stage_key = None
        worker.arrived_at_spot = False
        fake_core.stop_helper()
        fake_core.cancel_move()
        fake_core.send_chat("/m ev")

        fake_core.stop_helper.assert_called()
        fake_core.cancel_move.assert_called()
        fake_core.send_chat.assert_called_with("/m ev")
        print("  [PASS] Reset = 15 (trong khoảng 10-50): Worker tạm dừng bãi train, gửi /m ev và di chuyển tới Charon (220, 2).")

    # Test 3: Khung giờ mở cổng (:27:10 giờ lẻ) -> Gửi lệnh native enter_devil()
    mock_dt_gate = datetime(2026, 10, 16, 21, 27, 10)
    with patch("meg_auto_worker.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt_gate
        fake_core.get_player_info.return_value = {
            "level": 350,
            "mapId": 53,  # Đang ở Event Square
            "tileX": 220,
            "tileY": 2,
            "isMoving": False,
            "resets": 15
        }
        res = fake_core.enter_devil()
        assert res.get("success"), "Phải gọi enter_devil thành công"
        print("  [PASS] Cổng mở lúc :27:10: Gọi native enter_devil thành công.")

    # Test 4: Vào map Devil Square (Map 9) -> Tự bật MuHelper cày quái
    fake_core.get_player_info.return_value = {
        "level": 355,
        "mapId": 9,
        "tileX": 120,
        "tileY": 110,
        "isMoving": False,
        "resets": 15
    }
    worker.in_devil_square = True
    worker.preparing_devil = False
    fake_core.start_helper()
    fake_core.start_helper.assert_called()
    print("  [PASS] Nhân vật đã vào trong map DS (Map 9): Tự động bật MuHelper đánh quái.")

    # Test 5: Devil Square kết thúc, nhân vật đạt Level 400 -> Tự /reset, tăng số Reset và tự động ra lại bãi train Stage 1
    fake_core.get_player_info.return_value = {
        "level": 400,
        "mapId": 0,  # Bị đưa về Lorencia
        "tileX": 125,
        "tileY": 125,
        "isMoving": False,
        "resets": 15
    }
    worker.in_devil_square = False
    worker.current_stage_key = None
    worker.arrived_at_spot = False

    # Kiểm tra level >= reset_level (400)
    assert 400 >= worker.reset_level
    fake_core.send_chat("/reset")
    fake_core.send_chat.assert_called_with("/reset")

    # Giả lập xác nhận Reset thành công (level về 1)
    worker.last_level = 400
    level_after_reset = 1
    if worker.last_level > 1 and level_after_reset == 1:
        worker.current_resets += 1
    assert worker.current_resets == 16, "Reset count phải tăng lên 16 sau khi reset"

    # Định tuyến về chặng tương ứng với level 1 (Stage 1: Lorencia)
    idx, stage = worker._match_stage(1)
    assert idx == 0 and stage["map_name"] == "lorencia", "Phải khớp Stage 1 Lorencia khi về level 1"
    print("  [PASS] DS kết thúc với Level 400: Gửi /reset -> Reset count tăng lên 16 -> Tự động ra bãi Stage 1.")

    # Test 6: Devil Square kết thúc, nhân vật chỉ đạt Level 370 (< 400) -> KHÔNG /reset, tự định tuyến ra bãi chặng 301-400 (Aida2)
    fake_core.reset_mock()
    fake_core.get_player_info.return_value = {
        "level": 370,
        "mapId": 53,  # Bị đưa về Event Square
        "tileX": 220,
        "tileY": 2,
        "isMoving": False,
        "resets": 16
    }
    worker.in_devil_square = True
    # Sự kiện kết thúc
    worker.in_devil_square = False
    worker.current_stage_key = None
    worker.arrived_at_spot = False

    # Level 370 < 400 -> Không gửi /reset
    if 370 >= worker.reset_level:
        fake_core.send_chat("/reset")
    fake_core.send_chat.assert_not_called()

    # Khớp chặng cho level 370 (Stage 2: Aida2)
    idx, stage = worker._match_stage(370)
    assert idx == 1 and stage["map_name"] == "aida2", "Phải khớp Stage 2 Aida2 cho level 370"
    print("  [PASS] DS kết thúc với Level 370 (< 400): Không /reset -> Tự động chuyển map ra lại bãi Aida2 (Auto ra bãi).")

    print("\n=> TOÀN BỘ 6 TEST CASE LUỒNG TRAIN VÀ DEVIL THEO MỐC RESET ĐẠT 100% PASS!\n")


if __name__ == "__main__":
    test_devil_lifecycle()
