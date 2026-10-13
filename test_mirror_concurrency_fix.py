import sys
import time
import threading
from typing import Dict, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from meg_auto_worker import AutoTrainWorker

def test_autotrain_event_isolation():
    print("\n=== 1. KIỂM TRA TỰ ĐỘNG CÔ LẬP TRÁNH TRANH CHẤP TRONG AUTOTRAINWORKER ===")
    
    logs = []
    def mock_log(msg, lvl="INFO"):
        logs.append((lvl, msg))

    class MockCore:
        def __init__(self):
            self.map_id = 51 # Elbeland
            self.warp_called = False
            self.helper_started = False
        def get_player_info(self, max_age=0.5):
            return {
                "level": 300,
                "mapId": self.map_id,
                "tileX": 50,
                "tileY": 50,
                "isMoving": False
            }
        def send_chat(self, msg):
            self.warp_called = True
        def start_helper(self, **kwargs):
            self.helper_started = True
            return True
        def stop_helper(self):
            self.helper_started = False
            return True
        def cancel_move(self):
            pass
        def is_helper_active(self, **kwargs):
            return self.helper_started

    core = MockCore()
    stages = [
        {"min_level": 1, "max_level": 400, "map_name": "Tarkan", "map": "Tarkan", "x": 100, "y": 100}
    ]
    worker = AutoTrainWorker(
        pid=1234,
        stages=stages,
        log_callback=mock_log,
        progress_callback=lambda s, p: None,
        config={"poll_interval": 0.05},
        slot_idx=1
    )
    worker.core = core
    worker.map_resolver.resolve_map_id = lambda name: 8 # Tarkan = 8

    # 1. Khởi động worker
    worker.start()
    time.sleep(0.1)
    assert worker.running, "Worker phải đang chạy!"

    # 2. Tạm dừng cho sự kiện Double Goer
    worker.pause_for_event("Sự kiện Double Goer bắt đầu")
    assert worker.is_paused_for_event == True, "Worker phải ở trạng thái is_paused_for_event = True!"
    core.warp_called = False

    # Giả lập nhân vật bị tele về Elbeland (Map 51) trong khi stage yêu cầu Tarkan (Map 8)
    core.map_id = 51
    time.sleep(0.15)
    assert core.warp_called == False, "KHI ĐÃ PAUSE, WORKER TUYỆT ĐỐI KHÔNG ĐƯỢC GỬI LỆNH WARP!"
    print("  [PASS] Khi pause_for_event, AutoTrainWorker không gửi bất kỳ lệnh warp/move nào.")

    # 3. Giả lập nhân vật lọt vào map Double Goer (Map 65)
    core.map_id = 65
    time.sleep(0.15)
    assert core.warp_called == False, "KHI Ở MAP DOUBLE GOER (65), WORKER TUYỆT ĐỐI KHÔNG CAN THIỆP!"
    print("  [PASS] Khi ở map Double Goer (Map 65-68), AutoTrainWorker tự động cô lập an toàn.")

    # 4. Giả lập sự kiện kết thúc hoặc hết 5s không vào được -> Khôi phục worker
    worker.resume_from_event("Hết 5s không vào được - Quay lại bãi train")
    assert worker.is_paused_for_event == False, "Worker phải được bỏ cờ pause!"
    assert worker.current_stage_key is None, "current_stage_key phải được reset để re-route về bãi cắm!"
    print("  [PASS] Khi resume_from_event, AutoTrainWorker tự động reset trạng thái để sẵn sàng đưa nhân vật về bãi train.")

    worker.stop()
    print("  => OK: Kiểm thử cô lập AutoTrainWorker đạt 100% PASS.")

def test_slot_controller_mutex_and_recovery():
    print("\n=== 2. KIỂM TRA MUTEX LOCK VÀ TỰ ĐỘNG KHÔI PHỤC AUTO TRAIN TRONG SLOTCONTROLLER ===")
    from meg_gui import SlotController, DashboardApp

    # Mock App tối giản
    class MockApp:
        def __init__(self):
            self.running = True
            self.logs = []
            self.mirror_ui_elements = {}
        def append_mirror_log(self, msg):
            self.logs.append(msg)
        def update_mirror_slot_ui_state(self, slot_idx, is_running):
            pass
        def update_mirror_slot_status(self, slot_idx, text, text_color=None):
            pass
        def after(self, ms, func):
            # Thực thi ngay lập tức
            try:
                func()
            except Exception:
                pass

    app = MockApp()
    ctrl = SlotController(slot_idx=1, app=app)
    ctrl.assigned_pid = 999999 # Không tồn tại nhưng để test logic

    assert hasattr(ctrl, "_mirror_lock"), "Thiếu _mirror_lock trong SlotController!"
    assert hasattr(ctrl, "resume_auto_train_after_mirror"), "Thiếu resume_auto_train_after_mirror!"

    # Giả lập slot đang bật Auto Train
    ctrl.auto_requested = True
    ctrl._pause_train_for_mirror("Test Pause")
    assert ctrl.resume_auto_train_after_mirror == True, "Phải ghi nhớ cờ resume_auto_train_after_mirror = True!"
    print("  [PASS] _pause_train_for_mirror đã ghi nhận cờ khôi phục Auto Train.")

    resumed_called = [False]
    ctrl.start_auto = lambda: resumed_called.__setitem__(0, True)
    ctrl._resume_train_after_mirror("Test Resume")
    assert ctrl.resume_auto_train_after_mirror == False, "Cờ resume phải được reset!"
    assert resumed_called[0] == True, "start_auto phải được gọi để đưa nhân vật trở lại bãi train!"
    print("  [PASS] _resume_train_after_mirror tự động kích hoạt đưa nhân vật về bãi train thành công.")

    print("  => OK: Mutex và Recovery logic trong SlotController đạt 100% PASS.")

if __name__ == "__main__":
    test_autotrain_event_isolation()
    test_slot_controller_mutex_and_recovery()
    print("\n🎉 TOÀN BỘ KIỂM THỬ TRANH CHẤP & BẤT ĐỒNG BỘ ĐẠT 100% THÀNH CÔNG!")
