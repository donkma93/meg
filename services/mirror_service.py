"""
Mirror (Double Goer) Domain Service for MEGAMU Auto Train Dashboard.
Encapsulates Double Goer schedule, preparation timing, ticket checking,
turbo sniping coordination, and in-dungeon lifecycle.
"""

from datetime import datetime
from typing import Tuple, Dict, Any, Optional, List


class MirrorService:
    """Domain service managing the Double Goer / Mirror of Dimensions event."""

    # Double Goer opens every 2 hours at :15
    MIRROR_HOURS = list(range(0, 24, 2))
    PREP_MINUTES_BEFORE = 5
    MIRROR_TICKET_ID = 7279  # Mirror of Dimensions

    @classmethod
    def get_schedule_state(cls, dt: Optional[datetime] = None) -> Tuple[str, int, str]:
        """
        Tính toán trạng thái hiện tại của sự kiện Double Goer.
        - Trả về: (state, seconds_to_transition, display_str)
          * 'GATE_OPEN': Đang trong giờ mở cổng (:15 đến :25)
          * 'PREP': Đang trong 5 phút chuẩn bị (:10 đến :15)
          * 'WAITING': Đang chờ tới mốc chuẩn bị tiếp theo
        """
        now = dt or datetime.now()
        h = now.hour
        m = now.minute
        s = now.second

        # Xác định mốc giờ chẵn mở sự kiện (0, 2, 4, ..., 22)
        # Giờ mở cổng: h thuộc MIRROR_HOURS và 15 <= m < 25
        if (h in cls.MIRROR_HOURS) and (15 <= m < 25):
            rem_s = (25 * 60) - (m * 60 + s)
            return "GATE_OPEN", rem_s, f"Cổng Double Goer ĐANG MỞ! Còn {rem_s}s"

        # Giờ chuẩn bị: h thuộc MIRROR_HOURS và 10 <= m < 15
        if (h in cls.MIRROR_HOURS) and (10 <= m < 15):
            rem_s = (15 * 60) - (m * 60 + s)
            return "PREP", rem_s, f"Đang chuẩn bị vào Double Goer (Mở cổng sau {rem_s}s)"

        # Tìm mốc chuẩn bị tiếp theo (:10 của mốc giờ chẵn)
        # Tìm giờ chẵn tiếp theo
        for target_h in cls.MIRROR_HOURS:
            if target_h > h or (target_h == h and m < 10):
                next_prep_sec = (target_h * 3600 + 10 * 60) - (h * 3600 + m * 60 + s)
                rem_m = next_prep_sec // 60
                return "WAITING", next_prep_sec, f"Còn {rem_m} phút đến giờ chuẩn bị Double Goer ({target_h:02d}:10)"

        # Qua 22:15 -> Mốc tiếp theo là 00:10 ngày mai
        next_prep_sec = (24 * 3600 + 10 * 60) - (h * 3600 + m * 60 + s)
        rem_m = next_prep_sec // 60
        return "WAITING", next_prep_sec, f"Còn {rem_m} phút đến giờ chuẩn bị Double Goer (00:10)"

    @classmethod
    def is_in_mirror_dungeon(cls, map_id: int) -> bool:
        """Kiểm tra Map ID hiện tại có thuộc Double Goer Dungeon không (Map 65, 66, 67, 68)."""
        return int(map_id) in (65, 66, 67, 68)

    @classmethod
    def check_mirror_ticket(cls, engine) -> Dict[str, Any]:
        """Kiểm tra xem nhân vật có vé Mirror of Dimensions (item 7279) không."""
        if not engine:
            return {"has_ticket": False, "count": 0, "error": "Engine not ready"}

        try:
            if hasattr(engine, "count_item"):
                count = engine.count_item(cls.MIRROR_TICKET_ID)
                return {"has_ticket": count > 0, "count": int(count)}
            elif hasattr(engine, "find_item_slot"):
                slot = engine.find_item_slot(cls.MIRROR_TICKET_ID)
                return {"has_ticket": slot is not None and slot >= 0, "slot": slot, "count": 1 if slot is not None and slot >= 0 else 0}
        except Exception as e:
            return {"has_ticket": False, "count": 0, "error": str(e)}

        return {"has_ticket": False, "count": 0}

