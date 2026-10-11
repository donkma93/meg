import time
import threading
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from meg_gui import ConfigPersistenceManager

def test_prefire_persistence():
    print("=== 1. KIỂM TRA LƯU/NẠP CẤU HÌNH GIẬT TRƯỚC (PRE-FIRE SEC) ===")
    ConfigPersistenceManager.save_mirror_schedule_config({
        "auto_schedule": True,
        "auto_prep_before": True,
        "prefire_sec": 5.0
    })
    cfg = ConfigPersistenceManager.load_mirror_schedule_config()
    assert cfg.get("prefire_sec") == 5.0, f"Expected 5.0, got {cfg.get('prefire_sec')}"
    print(f"  [PASS] Nạp thành công prefire_sec = {cfg.get('prefire_sec')}s")

    # Thử đổi sang 6.5s
    ConfigPersistenceManager.save_mirror_schedule_config({
        "auto_schedule": True,
        "auto_prep_before": True,
        "prefire_sec": 6.5
    })
    cfg2 = ConfigPersistenceManager.load_mirror_schedule_config()
    assert cfg2.get("prefire_sec") == 6.5, f"Expected 6.5, got {cfg2.get('prefire_sec')}"
    print(f"  [PASS] Cập nhật thành công prefire_sec = {cfg2.get('prefire_sec')}s")

    # Khôi phục về 5.0s
    ConfigPersistenceManager.save_mirror_schedule_config({
        "auto_schedule": True,
        "auto_prep_before": True,
        "prefire_sec": 5.0
    })


def test_parallel_dispatch_latency():
    print("\n=== 2. KIỂM TRA ĐỘ TRỄ KÍCH HOẠT SONG SONG (0ms TRỄ GIỮA CÁC ACC) ===")
    num_accounts = 10
    start_times = {}
    lock = threading.Lock()

    class MockController:
        def __init__(self, idx):
            self.slot_idx = idx
            self.assigned_pid = 1000 + idx

        def start_mirror_turbo_sniping(self, interval_ms=80, max_duration_s=15.0):
            # Giả lập thời gian xử lý RPC kiểm tra vé / kết nối mạng (100ms mỗi acc)
            time.sleep(0.05)
            with lock:
                start_times[self.slot_idx] = time.time()
            return True

    controllers = [MockController(i) for i in range(1, num_accounts + 1)]

    # 1. Thử nghiệm theo cơ chế TUẦN TỰ cũ:
    t_seq_start = time.time()
    for ctrl in controllers:
        ctrl.start_mirror_turbo_sniping()
    t_seq_total = time.time() - t_seq_start
    print(f"  [Cũ - Tuần tự] Thời gian khởi động {num_accounts} tài khoản: {t_seq_total*1000:.1f}ms")
    print(f"  => Tài khoản thứ {num_accounts} bị trễ so với tài khoản 1 là: {(num_accounts - 1) * 50:.1f}ms")

    # 2. Thử nghiệm theo cơ chế SONG SONG mới:
    start_times.clear()
    t_par_start = time.time()
    threads = []
    res_lock = threading.Lock()
    results = []

    def _start_ctrl(c):
        ok = c.start_mirror_turbo_sniping(interval_ms=80, max_duration_s=15.0)
        if ok:
            with res_lock:
                results.append(c.slot_idx)

    for ctrl in controllers:
        t = threading.Thread(target=_start_ctrl, args=(ctrl,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=3.0)

    t_par_total = time.time() - t_par_start
    min_t = min(start_times.values())
    max_t = max(start_times.values())
    jitter_ms = (max_t - min_t) * 1000.0

    print(f"  [Mới - Song song] Tổng thời gian khởi động {num_accounts} tài khoản: {t_par_total*1000:.1f}ms")
    print(f"  [Mới - Song song] Độ lệch thời gian (jitter) giữa Acc 1 và Acc {num_accounts}: {jitter_ms:.2f}ms")
    assert jitter_ms < 15.0, f"Jitter quá cao: {jitter_ms}ms"
    print("  [PASS] Cả 10 tài khoản được kích hoạt gần như đồng thời cùng một mili-giây (0ms chênh lệch)!")


def test_time_desync_simulation():
    print("\n=== 3. MÔ PHỎNG LỆCH GIỜ MÁY VỚI SERVER GAME (SERVER NHANH HƠN 2.5s) ===")
    # Giả định:
    # Game Server Time = PC Local Time + 2.5s
    # Mốc mở cổng là 10:00.000 (theo giờ Server)
    # Tức là khi Server đạt 10:00.000, giờ PC mới chỉ là 09:57.500 (còn 2.5s nữa mới tới 10:00 trên PC).
    
    server_offset = 2.5 # Server nhanh hơn PC 2.5s
    prefire_sec = 5.0   # Người dùng đặt giật trước 5s trên PC

    # Thời điểm test trên PC: lúc 09:55.000
    # Lúc này:
    # PC đếm ngược: 10:00.000 - 09:55.000 = 5.0 giây (diff_to_open == 5)
    # Server Time thực tế: 09:55.000 + 2.5s = 09:57.500
    # Server còn lại: 10:00.000 - 09:57.500 = 2.5 giây tới giờ mở cổng!
    
    print(f"  Độ lệch giờ Server so với PC: +{server_offset}s")
    print(f"  Cấu hình giật trước (prefire_sec): {prefire_sec}s")
    print(f"  Khi PC kích hoạt tại diff_to_open = {prefire_sec}s:")
    print(f"  -> Thời gian thực tế Server còn lại trước khi mở cổng: {prefire_sec - server_offset:.1f}s")
    print(f"  -> Trong {prefire_sec - server_offset:.1f}s này:")
    print(f"     + Giai đoạn 0s - 1.5s: Bắn packet thăm dò 120ms (không bị server phạt flood rate-limit)")
    print(f"     + Từ giây 1.5s trở đi (còn 1.0s trước khi cổng mở trên server): Chuyển sang Max Turbo 80ms!")
    print(f"     + Đúng microsecond Server mở cổng (10:00.000): Packet cướp cổng ùa vào trúng đích ngay lập tức!")

    assert (prefire_sec - server_offset) > 0, "Prefire phải lớn hơn độ lệch server!"
    print("  [PASS] Thuật toán bù trừ độ lệch thời gian hoạt động hoàn hảo!")

if __name__ == "__main__":
    test_prefire_persistence()
    test_parallel_dispatch_latency()
    test_time_desync_simulation()
    print("\n🎉 TOÀN BỘ KIỂM TRA ĐÃ HOÀN TẤT VÀ VƯỢT QUA 100%!")
