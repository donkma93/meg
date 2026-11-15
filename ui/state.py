# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - ZERO-LAG APPLICATION STATE MANAGER
Quản lý trạng thái ứng dụng đồng bộ, chống nghẽn luồng Tkinter bằng State Diffing & Batched Dispatch.
"""

import time
import threading
from collections import deque
from typing import Dict, Any, List, Optional, Tuple

class AppStateManager:
    """Kho lưu trữ trạng thái trung tâm Reactive & Thread-safe cho toàn bộ Dashboard."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(AppStateManager, cls).__new__(cls)
                    cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.state_lock = threading.Lock()
        
        # 1. Trạng thái 10 Slots Auto Train
        self.slots: Dict[int, Dict[str, Any]] = {}
        self._slot_dirty: Dict[int, bool] = {}
        for i in range(1, 11):
            self.slots[i] = {
                "slot_idx": i,
                "assigned_pid": None,
                "char_name": "---",
                "level": "---",
                "coords": "--,--",
                "server": "---",
                "status": "Chờ kết nối...",
                "is_running": False,
                "map": "---",
                "spot": "(125, 125)",
                "resets": 0,
                "class_code": "",
                "mirror_enabled": True,
                "moss_enabled": True
            }
            self._slot_dirty[i] = True

        # 2. Hàng đợi Log tập trung (Batched Queue)
        self.log_queue: deque = deque(maxlen=500)
        self.new_logs_count: int = 0

        # 3. Trạng thái Sự kiện (Mirror & Moss)
        self.events = {
            "mirror": {
                "countdown_sec": 0,
                "is_gate_open": False,
                "status_text": "Chờ cổng mở...",
                "next_time_str": "--:10",
                "participants": []
            },
            "moss": {
                "countdown_sec": 0,
                "is_open": False,
                "status_text": "Chờ mốc giờ...",
                "next_time_str": "--:15",
                "participants": []
            }
        }
        self.events_dirty = True

        # 4. Trạng thái Toàn cục (Thống kê PIDs, License)
        self.active_pids: List[int] = []
        self.detected_games: Dict[int, str] = {}
        self.license_info: str = "Đang kiểm tra..."
        self.global_dirty = True

    # --------------------------------------------------------------------------
    # QUẢN LÝ DỮ LIỆU TELEMETRY SLOT (STATE DIFFING)
    # --------------------------------------------------------------------------
    def update_slot_telemetry(
        self,
        slot_idx: int,
        char_name: Optional[str] = None,
        level: Optional[str] = None,
        coords: Optional[str] = None,
        server: Optional[str] = None,
        resets: Optional[int] = None,
        class_code: Optional[str] = None,
        status: Optional[str] = None,
        is_running: Optional[bool] = None,
        assigned_pid: Optional[int] = None,
        map: Optional[str] = None
    ):
        """Cập nhật dữ liệu từ nền. Áp dụng State Diffing: Chỉ đánh dấu DIRTY khi có giá trị thay đổi."""
        if slot_idx not in self.slots:
            return

        with self.state_lock:
            s = self.slots[slot_idx]
            changed = False

            if char_name is not None and s["char_name"] != char_name:
                s["char_name"] = char_name
                changed = True
            if level is not None and s["level"] != level:
                s["level"] = level
                changed = True
            if coords is not None and s["coords"] != coords:
                s["coords"] = coords
                changed = True
            if server is not None and s["server"] != server:
                s["server"] = server
                changed = True
            if resets is not None and s["resets"] != resets:
                s["resets"] = resets
                changed = True
            if class_code is not None and s["class_code"] != class_code:
                s["class_code"] = class_code
                changed = True
            if status is not None and s["status"] != status:
                s["status"] = status
                changed = True
            if is_running is not None and s["is_running"] != is_running:
                s["is_running"] = is_running
                changed = True
            if assigned_pid is not None and s["assigned_pid"] != assigned_pid:
                s["assigned_pid"] = assigned_pid
                changed = True
            if map is not None and s.get("map") != map:
                s["map"] = map
                changed = True

            if changed:
                self._slot_dirty[slot_idx] = True

    def get_dirty_slots(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các slot có thay đổi để UI cập nhật In-Place, sau đó xóa cờ dirty."""
        with self.state_lock:
            res = []
            for idx, is_dirty in self._slot_dirty.items():
                if is_dirty:
                    res.append(dict(self.slots[idx]))
                    self._slot_dirty[idx] = False
            return res

    def get_slot(self, slot_idx: int) -> Dict[str, Any]:
        with self.state_lock:
            return dict(self.slots.get(slot_idx, {}))

    # --------------------------------------------------------------------------
    # QUẢN LÝ NHẬT KÝ HỆ THỐNG THEO LÔ (BATCHED LOGS)
    # --------------------------------------------------------------------------
    def append_log(self, text: str, level: str = "INFO", slot: Optional[int] = None):
        """Ghi log vào hàng đợi từ bất kỳ luồng nào (Non-blocking)."""
        now_str = time.strftime("%H:%M:%S")
        with self.state_lock:
            self.log_queue.append((now_str, level.upper(), slot, text))
            self.new_logs_count += 1

    def pop_pending_logs(self) -> List[Tuple[str, str, Optional[int], str]]:
        """Lấy toàn bộ logs mới dồn toa để nạp 1 lần duy nhất vào Text Widget."""
        with self.state_lock:
            if not self.log_queue or self.new_logs_count == 0:
                return []
            # Lấy tất cả logs mới
            count = min(self.new_logs_count, len(self.log_queue))
            logs = list(self.log_queue)[-count:]
            self.new_logs_count = 0
            return logs

    # --------------------------------------------------------------------------
    # QUẢN LÝ TIẾN TRÌNH & SỰ KIỆN
    # --------------------------------------------------------------------------
    def update_detected_games(self, games: Dict[int, str]):
        with self.state_lock:
            if self.detected_games != games:
                self.detected_games = dict(games)
                self.active_pids = list(games.keys())
                self.global_dirty = True

    def update_event_state(self, event_name: str, **kwargs):
        with self.state_lock:
            if event_name in self.events:
                self.events[event_name].update(kwargs)
                self.events_dirty = True
