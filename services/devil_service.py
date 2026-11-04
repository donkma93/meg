"""
Devil Square Domain Service for MEGAMU Auto Train Dashboard.
Encapsulates schedule calculation, reset/ticket eligibility checking,
and entry logic into Devil Square.
"""

from datetime import datetime
from typing import Tuple, Dict, Any, Optional


class DevilService:
    """Domain service managing the Devil Square event lifecycle."""

    @staticmethod
    def is_devil_schedule(dt: Optional[datetime] = None) -> Tuple[bool, int, str]:
        """
        Kiểm tra xem thời điểm hiện tại có đang trong khung giờ mở cổng Devil Square không.
        - Khung giờ mở cổng: :27 đến :30 (3 phút trước giờ chẵn hoặc các mốc 2 tiếng 1 lần).
        - Trả về: (is_open, minutes_to_open, status_description)
        """
        now = dt or datetime.now()
        minute = now.minute
        second = now.second

        # Cổng mở từ phút 27:00 đến 30:00
        if 27 <= minute < 30:
            remaining_sec = (30 * 60) - (minute * 60 + second)
            return True, 0, f"Cổng Devil Square ĐANG MỞ! Còn {remaining_sec}s"

        # Tính thời gian chờ đến mốc :27 tiếp theo
        if minute < 27:
            diff_min = 27 - minute
        else:
            diff_min = (60 - minute) + 27

        return False, diff_min, f"Còn {diff_min} phút đến giờ mở cổng Devil Square"

    @staticmethod
    def check_resets_eligibility(current_resets: int, min_resets: int = 0, max_resets: int = 9999) -> bool:
        """Kiểm tra điều kiện mốc Reset có hợp lệ để đi Devil Square không."""
        c_rs = int(current_resets or 0)
        mn = int(min_resets or 0)
        mx = int(max_resets or 9999)
        if mx <= 0:
            mx = 9999
        return mn <= c_rs <= mx

    @staticmethod
    def check_ticket_eligibility(
        engine,
        ticket_preference: str = "auto"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra số lượng và loại vé Devil Square trong hòm đồ.
        - ticket_preference: 'auto' | 'master' | 'normal'
        - Trả về: (has_valid_ticket, ticket_type_used, ticket_info_dict)
        """
        if not engine:
            return False, "none", {"error": "Engine not available"}

        try:
            if hasattr(engine, "get_devil_ticket_info"):
                info = engine.get_devil_ticket_info() or {}
            else:
                return False, "none", {"error": "Engine missing get_devil_ticket_info"}
        except Exception as e:
            return False, "none", {"error": str(e)}

        has_normal = bool(info.get("hasNormalTicket") and info.get("normalCount", 0) > 0)
        has_master = bool(info.get("hasMasterTicket") and info.get("masterCount", 0) > 0)

        pref = (ticket_preference or "auto").lower()
        if pref == "master":
            if has_master:
                return True, "master", info
            return False, "none", info
        elif pref == "normal":
            if has_normal:
                return True, "normal", info
            return False, "none", info
        else:  # auto preference: ưu tiên master nếu có, fallback normal
            if has_master:
                return True, "master", info
            elif has_normal:
                return True, "normal", info
            return False, "none", info

    @staticmethod
    def enter_devil_square(
        engine,
        ticket_preference: str = "auto"
    ) -> Dict[str, Any]:
        """
        Gửi lệnh tham gia Devil Square qua Direct Engine.
        """
        if not engine:
            return {"success": False, "error": "Engine not ready"}

        try:
            if hasattr(engine, "enter_devil"):
                res = engine.enter_devil(ticket_preference=ticket_preference)
                return res if isinstance(res, dict) else {"success": bool(res)}
            elif hasattr(engine, "enter_devil_square"):
                res = engine.enter_devil_square(ticket_preference=ticket_preference)
                return res if isinstance(res, dict) else {"success": bool(res)}
        except Exception as e:
            return {"success": False, "error": str(e)}

        return {"success": False, "error": "No enter_devil method found on engine"}

    @staticmethod
    def is_in_devil_map(map_id: int) -> bool:
        """Kiểm tra Map ID hiện tại có phải là bản đồ Devil Square không (Map 9 hoặc Map 32)."""
        return int(map_id) in (9, 32)

