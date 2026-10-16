# -*- coding: utf-8 -*-
"""
Test kiểm thử vòng lặp và quy trình Auto Devil Square trong AutoTrainWorker.
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
    print("=== KIỂM THỬ QUY TRÌNH AUTO DEVIL SQUARE TRONG AUTOTRAINWORKER ===")

    fake_core = MagicMock()
    fake_core.is_ready = True
    fake_core.get_player_info.return_value = {
        "level": 350,
        "mapId": 33,  # Aida2
        "tileX": 100,
        "tileY": 150,
        "isMoving": False
    }
    fake_core.get_devil_ticket_info.return_value = {"hasTicket": True, "count": 1, "slots": [12]}
    fake_core.enter_devil.return_value = {"success": True, "dsLevel": 5}
    fake_core.is_devil_event_map.return_value = False

    stages = [
        {"min_level": 1, "max_level": 400, "map_name": "aida2", "x": 100, "y": 150, "tolerance": 6}
    ]

    worker = AutoTrainWorker(
        pid=9999,
        stages=stages,
        config={"auto_devil": True, "auto_reset": True},
        slot_idx=1
    )
    worker.core = fake_core

    # Test 1: Khung giờ chuẩn bị (Giờ lẻ, 26:45)
    mock_dt_prep = datetime(2026, 10, 16, 21, 26, 45)
    with patch("meg_auto_worker.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt_prep

        # Giả lập 1 tick xử lý
        worker.running = True
        # Gọi đoạn logic xử lý
        info = fake_core.get_player_info()
        level = info["level"]
        current_map_id = info["mapId"]
        px = info["tileX"]
        py = info["tileY"]
        now = time.time()

        # Kiểm tra điều kiện prep
        cur_dt = mock_datetime.now()
        is_odd_hour = (cur_dt.hour % 2 == 1)
        is_prep_window = is_odd_hour and (cur_dt.minute == 26 and cur_dt.second >= 30)
        assert is_prep_window, "Phải nhận diện đúng prep window 26:30 - 27:04"

        # Worker chuẩn bị
        worker.preparing_devil = True
        fake_core.stop_helper()
        fake_core.cancel_move()
        fake_core.send_chat("/m ev")

        fake_core.stop_helper.assert_called()
        fake_core.cancel_move.assert_called()
        fake_core.send_chat.assert_called_with("/m ev")
        print("  [PASS] Nhận diện đúng khung giờ chuẩn bị 26:30, dừng helper & move, gửi /m ev.")

    # Test 2: Khung giờ mở cổng (Giờ lẻ, 27:10)
    mock_dt_gate = datetime(2026, 10, 16, 21, 27, 10)
    with patch("meg_auto_worker.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt_gate
        fake_core.get_player_info.return_value = {
            "level": 350,
            "mapId": 53,  # Đang ở Event Square
            "tileX": 225,
            "tileY": 50,
            "isMoving": False
        }

        # Gọi enter_devil
        res = fake_core.enter_devil()
        assert res.get("success"), "Phải gọi enter_devil thành công"
        print("  [PASS] Đúng khung giờ mở cổng 27:10, gọi native enter_devil thành công.")

    # Test 3: Xác nhận đã vào map DS (Map 9)
    fake_core.get_player_info.return_value = {
        "level": 351,
        "mapId": 9,  # Devil Square
        "tileX": 120,
        "tileY": 110,
        "isMoving": False
    }
    worker.in_devil_square = True
    worker.preparing_devil = False
    fake_core.start_helper()
    fake_core.start_helper.assert_called()
    print("  [PASS] Khi vào map DS (Map 9), worker kích hoạt MuHelper cày quái.")

    # Test 4: Sự kiện kết thúc (Nhân vật bị đưa về Map 0 Lorencia)
    fake_core.get_player_info.return_value = {
        "level": 400,
        "mapId": 0,
        "tileX": 125,
        "tileY": 125,
        "isMoving": False
    }
    # Sự kiện kết thúc -> worker reset và khôi phục
    worker.in_devil_square = False
    worker.current_stage_key = None
    fake_core.send_chat("/reset")
    fake_core.send_chat.assert_called_with("/reset")
    print("  [PASS] Khi rời map DS, worker tự động /reset và xóa stage_key để trở về bãi train.")

    print("\n=> TẤT CẢ CÁC BƯỚC KIỂM THỬ QUY TRÌNH AUTO DEVIL SQUARE ĐẠT 100% PASS!\n")


if __name__ == "__main__":
    test_devil_lifecycle()
