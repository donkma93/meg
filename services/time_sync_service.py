# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - TIME SYNCHRONIZATION SERVICE
Module đồng bộ thời gian thực chuẩn xác cao (High-Precision Server Time Synchronizer):
- Tự động đo độ lệch đồng hồ giữa PC trạm và Giờ Nguyên Tử Quốc Tế (NTP UTC) qua Cristian's Algorithm.
- Tự động tích hợp GameServer RTT và One-Way Latency từ luồng Probe / Recv Packet.
- Cung cấp thời gian thực Server Time (sai số < 10ms) cho toàn bộ hệ thống Đếm ngược và Bắn tỉa.
"""

import time
import socket
import struct
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List, Callable


NTP_SERVERS = [
    ("time.google.com", 123),
    ("time.cloudflare.com", 123),
    ("time.windows.com", 123),
]


class GameTimeSyncService:
    """Singleton Service quản lý độ lệch thời gian và nhịp mạng Game."""

    _instance: Optional["GameTimeSyncService"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "GameTimeSyncService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._ntp_offset_sec: float = 0.0          # Delta t = T_real - T_pc (dương nếu PC chậm, âm nếu PC nhanh)
        self._ntp_rtt_ms: float = 0.0              # Ping tới máy chủ NTP
        self._last_ntp_sync_ts: float = 0.0        # Thời điểm sync NTP lần cuối (time.time())
        self._game_rtt_ms: float = 280.0           # Ping tới GameServer MEGAMU (mặc định 280ms từ VN sang Brazil)
        self._game_rtt_samples: List[float] = []   # Lịch sử mẫu RTT game gần nhất
        self._sync_status_str: str = "Chưa đồng bộ"
        self._is_syncing: bool = False
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Khởi động sync ban đầu trong thread ngầm
        threading.Thread(target=self.sync_ntp, daemon=True, name="InitialNtpSync").start()

    # --------------------------------------------------------------------------
    # 1. ĐO ĐỘ LỆCH NGUYÊN TỬ (NTP CRISTIAN'S ALGORITHM)
    # --------------------------------------------------------------------------
    def sync_ntp(self, timeout_sec: float = 2.0, force: bool = False) -> bool:
        """Đo độ lệch đồng hồ máy tính so với Atomic Clock qua NTP UDP Port 123."""
        with self._lock:
            if self._is_syncing:
                return False
            self._is_syncing = True

        best_offset = None
        best_rtt = 9999.0
        used_server = ""

        try:
            for host, port in NTP_SERVERS:
                client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client.settimeout(timeout_sec)
                try:
                    # NTP packet v3/v4: 48 bytes, byte đầu = 0x1b (client mode)
                    msg = b'\x1b' + 47 * b'\0'
                    t0 = time.time()
                    client.sendto(msg, (host, port))
                    data, _ = client.recvfrom(1024)
                    t3 = time.time()

                    if len(data) >= 48:
                        # Unpack Transmit Timestamp (offset 40) và Receive Timestamp (offset 32)
                        r_sec, r_frac = struct.unpack('!II', data[32:40])
                        t_sec, t_frac = struct.unpack('!II', data[40:48])

                        # Chuyển đổi NTP epoch (1900-01-01) sang Unix epoch (1970-01-01) = 2208988800s
                        t1 = (r_sec - 2208988800) + (r_frac / 4294967296.0)
                        t2 = (t_sec - 2208988800) + (t_frac / 4294967296.0)

                        # Cristian's Algorithm:
                        # Offset = ((t1 - t0) + (t2 - t3)) / 2
                        # Round Trip Time (RTT) = (t3 - t0) - (t2 - t1)
                        offset = ((t1 - t0) + (t2 - t3)) / 2.0
                        rtt_ms = max(0.0, ((t3 - t0) - (t2 - t1)) * 1000.0)

                        # Chọn server có RTT thấp nhất để giảm thiểu jitter
                        if rtt_ms < best_rtt:
                            best_rtt = rtt_ms
                            best_offset = offset
                            used_server = host
                except Exception:
                    pass
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass
        finally:
            with self._lock:
                self._is_syncing = False

        if best_offset is not None:
            self._ntp_offset_sec = best_offset
            self._ntp_rtt_ms = best_rtt
            self._last_ntp_sync_ts = time.time()
            sign = "+" if self._ntp_offset_sec >= 0 else ""
            self._sync_status_str = f"✓ Đã sync ({used_server}): {sign}{self._ntp_offset_sec*1000.0:.1f}ms (Ping {best_rtt:.0f}ms)"
            self._notify_listeners()
            return True
        else:
            self._sync_status_str = "⚠ Lỗi kết nối NTP"
            self._notify_listeners()
            return False

    # --------------------------------------------------------------------------
    # 2. CẬP NHẬT RTT GAME TỪ PACKET PROBE / RECV
    # --------------------------------------------------------------------------
    def record_game_rtt(self, rtt_ms: float):
        """Nhận chỉ số RTT đo được thực tế từ GameAssembly qua hàm probe hoặc hook."""
        if rtt_ms <= 5 or rtt_ms > 3000:
            return
        self._game_rtt_samples.append(rtt_ms)
        if len(self._game_rtt_samples) > 10:
            self._game_rtt_samples.pop(0)

        # Tính trung bình trượt có trọng số (EWMA)
        avg_rtt = sum(self._game_rtt_samples) / len(self._game_rtt_samples)
        self._game_rtt_ms = round(avg_rtt, 1)

    # --------------------------------------------------------------------------
    # 3. TRUY VẤN THỜI GIAN ĐỒNG BỘ CHUẨN XÁC
    # --------------------------------------------------------------------------
    def get_ntp_offset_sec(self) -> float:
        """Độ lệch NTP so với PC (giây)."""
        return self._ntp_offset_sec

    def get_ntp_offset_ms(self) -> float:
        """Độ lệch NTP so với PC (mili-giây)."""
        return self._ntp_offset_sec * 1000.0

    def get_game_rtt_ms(self) -> float:
        """Độ trễ Round-Trip Time tới GameServer MEGAMU (ms)."""
        return self._game_rtt_ms

    def get_one_way_latency_sec(self) -> float:
        """Thời gian gói tin bay 1 chiều từ Client tới GameServer (giây)."""
        return (self._game_rtt_ms / 2.0) / 1000.0

    def get_server_now(self) -> datetime:
        """Lấy mốc thời gian chuẩn Atomic/Server Time tại thời điểm hiện tại."""
        return datetime.now() + timedelta(seconds=self._ntp_offset_sec)

    def get_server_epoch_ms(self) -> float:
        """Mốc Epoch UTC đã được bù trừ sai số đồng hồ PC."""
        return (time.time() + self._ntp_offset_sec) * 1000.0

    def get_sync_status_text(self) -> str:
        """Chuỗi hiển thị trạng thái đồng bộ ngắn gọn cho giao diện."""
        return self._sync_status_str

    # --------------------------------------------------------------------------
    # 4. TÍNH TOÁN LỊCH TRÌNH VÀ ĐẾM NGƯỢC CHÍNH XÁC CHO MIRROR
    # --------------------------------------------------------------------------
    def get_mirror_event_schedule(self) -> Dict[str, Any]:
        """Tính toán chính xác theo Giờ Server đã đồng bộ:
        - Giờ chẵn :10-:15 (00, 02, 04, ..., 22).
        - Trả về diff_to_open_float, is_gate_open, next_gate_dt, formatted strings.
        """
        srv_now = self.get_server_now()
        valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]

        # Khung mở cổng: từ phút 10 đến trước phút 15 của các giờ chẵn
        is_gate_open = (srv_now.hour in valid_hours and 10 <= srv_now.minute < 15)

        next_gate = None
        for h in valid_hours:
            cand = srv_now.replace(hour=h, minute=10, second=0, microsecond=0)
            if cand > srv_now:
                next_gate = cand
                break

        if next_gate is None:
            tomorrow = srv_now + timedelta(days=1)
            next_gate = tomorrow.replace(hour=0, minute=10, second=0, microsecond=0)

        if is_gate_open:
            end_open = srv_now.replace(minute=15, second=0, microsecond=0)
            rem_sec_float = max(0.0, (end_open - srv_now).total_seconds())
            next_str = f"{srv_now.hour:02d}:10 - {srv_now.hour:02d}:15"
            status = "CỔNG ĐANG MỞ!"
        else:
            rem_sec_float = max(0.0, (next_gate - srv_now).total_seconds())
            next_str = next_gate.strftime("%H:%M")
            rem_sec = int(rem_sec_float)
            status = f"Mở sau: {rem_sec // 3600:02d}:{(rem_sec % 3600) // 60:02d}:{rem_sec % 60:02d}"

        rem_sec = int(rem_sec_float)
        cd_str = f"{rem_sec // 3600:02d}:{(rem_sec % 3600) // 60:02d}:{rem_sec % 60:02d}"

        return {
            "server_now": srv_now,
            "is_gate_open": is_gate_open,
            "diff_to_open_float": rem_sec_float,
            "countdown_sec": rem_sec,
            "countdown_str": cd_str,
            "next_gate_dt": next_gate,
            "next_time_str": next_str,
            "status_text": status,
            "ntp_offset_sec": self._ntp_offset_sec,
            "game_rtt_ms": self._game_rtt_ms,
            "one_way_latency_sec": self.get_one_way_latency_sec(),
        }

    # --------------------------------------------------------------------------
    # 5. LISTENER & AUTO-REFRESH WORKER
    # --------------------------------------------------------------------------
    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        self._listeners.append(callback)

    def _notify_listeners(self):
        data = {
            "offset_sec": self._ntp_offset_sec,
            "offset_ms": self.get_ntp_offset_ms(),
            "rtt_ms": self._ntp_rtt_ms,
            "game_rtt_ms": self._game_rtt_ms,
            "status": self._sync_status_str,
        }
        for cb in self._listeners:
            try:
                cb(data)
            except Exception:
                pass

    def start_background_sync(self, interval_sec: float = 600.0):
        """Bật luồng đồng bộ định kỳ (mặc định 10 phút/lần)."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                # Tự động đồng bộ lại nếu đã quá 10 phút
                if time.time() - self._last_ntp_sync_ts >= interval_sec:
                    self.sync_ntp()
                self._stop_event.wait(60.0)

        self._worker_thread = threading.Thread(target=_loop, daemon=True, name="NtpBackgroundSync")
        self._worker_thread.start()

    def stop_background_sync(self):
        self._stop_event.set()


# Hàm tiện ích truy cập nhanh
def get_time_sync() -> GameTimeSyncService:
    return GameTimeSyncService.get_instance()
