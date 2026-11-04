"""
Moss Merchant Domain Service for MEGAMU Auto Train Dashboard.
Manages Moss Merchant schedule calculation, NPC interaction,
safe rolling loop, item verification, and trash cleaning.
"""

import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Callable, Tuple


class MossService:
    """Domain service managing the Moss Merchant (The Gambler) automation."""

    MOSS_TIMES = ["00:15", "06:15", "12:15", "18:15"]

    MOSS_CAT_OPTIONS = [
        ("Vũ Khí 1 Tay (1H Weapons)", 0),
        ("Vũ Khí 2 Tay (2H Weapons)", 1),
        ("Gậy Phép (Staves)", 2),
        ("Cung Nỏ (Bows & Crossbows)", 3),
        ("Khiên (Shields)", 4),
        ("Mũ (Helmets)", 5),
        ("Giáp (Armor)", 6),
        ("Quần (Pants)", 7),
        ("Găng (Gloves)", 8),
        ("Giày (Boots)", 9),
        ("Trang Sức (Accessories)", 10),
    ]

    _instance: Optional['MossService'] = None
    _lock = threading.RLock()

    def __init__(self):
        self._running_slots: Dict[int, bool] = {}
        self._worker_threads: Dict[int, threading.Thread] = {}
        self._initial_item_slots: Dict[int, Set[int]] = {}

    @classmethod
    def get_instance(cls) -> 'MossService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_category_name(cls, cat_id: int) -> str:
        for name, cid in cls.MOSS_CAT_OPTIONS:
            if cid == int(cat_id):
                return name
        return f"Category {cat_id}"

    @classmethod
    def get_next_moss_schedule(cls, dt: Optional[datetime] = None) -> Tuple[bool, int, str]:
        """
        Kiểm tra thời gian tới mốc mở Moss tiếp theo (00:15, 06:15, 12:15, 18:15).
        - Trả về: (is_moss_active, minutes_remaining, display_str)
        """
        now = dt or datetime.now()
        cur_min_of_day = now.hour * 60 + now.minute

        # Mốc Moss: 15, 375, 735, 1095
        target_mins = [15, 375, 735, 1095]

        # Kiểm tra nếu đang trong khoảng thời gian diễn ra (15 phút từ lúc mở)
        for t in target_mins:
            if t <= cur_min_of_day < t + 15:
                rem_m = (t + 15) - cur_min_of_day
                return True, rem_m, f"Sự kiện Moss Merchant ĐANG DIỄN RA! Còn ~{rem_m} phút"

        # Tìm mốc tiếp theo
        next_t = None
        for t in target_mins:
            if t > cur_min_of_day:
                next_t = t
                break
        if next_t is None:
            next_t = target_mins[0] + 24 * 60  # 00:15 ngày hôm sau

        diff = next_t - cur_min_of_day
        h = diff // 60
        m = diff % 60
        return False, diff, f"Còn {h}h {m}m đến giờ mở Moss Merchant"

    def is_slot_running(self, slot_idx: int) -> bool:
        with self._lock:
            return bool(self._running_slots.get(slot_idx, False))

    def stop_slot_moss(self, slot_idx: int):
        """Dừng quay Moss của riêng slot_idx."""
        with self._lock:
            self._running_slots[slot_idx] = False

    def stop_all_slots(self):
        """Dừng quay Moss trên toàn bộ các slots."""
        with self._lock:
            for s_idx in list(self._running_slots.keys()):
                self._running_slots[s_idx] = False

