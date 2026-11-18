# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - PARTY MANAGER SERVICE (MULTI-PT ENHANCED)
Quản lý tự động ghép nhóm (Auto PT) đa nhóm giữa các tài khoản MEGAMU:
- Hỗ trợ nhiều nhóm PT (Multi-PT) độc lập, mỗi nhóm có Chủ PT (Leader) và các Thành viên (Members) riêng.
- Hỗ trợ 2 chế độ:
  1. Tự động chia nhóm (5 acc/nhóm): Slot 1-5 vào PT 1, Slot 6-10 vào PT 2, v.v.
  2. Tùy chỉnh danh sách nhóm thủ công: Tự do chọn Chủ PT và Thành viên cho từng nhóm.
- Quản lý lệnh in-game /re auto [password] và /re off qua Direct Engine / Native Chat.
- Giám sát trạng thái Party từ RAM IL2CPP (InParty, IsLeader, LeaderName, Danh sách thành viên).
- Tự động duy trì và khôi phục Party cho từng nhóm khi nhân vật chết, chuyển map hoặc relogin.
"""

import os
import json
import time
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple, Callable

from meg_direct_engine import MegDirectEngine
from meg_navigator import ProcessMemoryReader

logger = logging.getLogger("PartyManager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTY_CONFIG_PATH = os.path.join(BASE_DIR, "config", "party_config.json")

DEFAULT_PARTY_CONFIG = {
    "enabled": True,
    "mode": "auto_5",           # "auto_5" (tự động 5 acc/PT) hoặc "custom" (tùy chỉnh)
    "leader_slot": 1,           # default fallback
    "party_pass": "1234",       # pass mặc định chung
    "auto_re_pass": True,
    "auto_reconnect": True,
    "sync_interval_sec": 6.0,
    "parties": []               # Danh sách cấu hình các nhóm PT
}


class PartyManager:
    """Singleton Service quản lý Auto Party (hỗ trợ nhiều PT độc lập) cho toàn bộ các Slots."""

    _instance: Optional["PartyManager"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "PartyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.config: Dict[str, Any] = dict(DEFAULT_PARTY_CONFIG)
        self.load_config()

        self._last_tick_time: float = 0.0
        self._is_syncing: bool = False
        self._sync_lock = threading.Lock()

        # Cache danh sách slots đã biết gần nhất
        self._last_known_slots: List[int] = []

        # Cache RAM party info: {slot_idx: {"data": dict, "ts": float}}
        self._slot_party_cache: Dict[int, Dict[str, Any]] = {}

    # --------------------------------------------------------------------------
    # CẤU HÌNH & LƯU TRỮ
    # --------------------------------------------------------------------------
    def load_config(self) -> Dict[str, Any]:
        """Tải cấu hình Party từ file JSON."""
        if os.path.exists(PARTY_CONFIG_PATH):
            try:
                with open(PARTY_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.config.update(data)
            except Exception as e:
                logger.error(f"Lỗi đọc {PARTY_CONFIG_PATH}: {e}")
        else:
            self.save_config()
        return self.config

    def save_config(self) -> bool:
        """Lưu cấu hình Party vào file JSON."""
        try:
            os.makedirs(os.path.dirname(PARTY_CONFIG_PATH), exist_ok=True)
            with open(PARTY_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi lưu {PARTY_CONFIG_PATH}: {e}")
            return False

    def update_config(
        self,
        enabled: Optional[bool] = None,
        mode: Optional[str] = None,
        leader_slot: Optional[int] = None,
        party_pass: Optional[str] = None,
        auto_re_pass: Optional[bool] = None,
        auto_reconnect: Optional[bool] = None,
        sync_interval_sec: Optional[float] = None,
        parties: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Cập nhật các tham số cấu hình Party và ghi đĩa."""
        if enabled is not None:
            self.config["enabled"] = bool(enabled)
        if mode is not None:
            self.config["mode"] = "custom" if str(mode).strip() == "custom" else "auto_5"
        if leader_slot is not None:
            self.config["leader_slot"] = int(leader_slot)
        if party_pass is not None:
            self.config["party_pass"] = str(party_pass).strip()
        if auto_re_pass is not None:
            self.config["auto_re_pass"] = bool(auto_re_pass)
        if auto_reconnect is not None:
            self.config["auto_reconnect"] = bool(auto_reconnect)
        if sync_interval_sec is not None:
            self.config["sync_interval_sec"] = max(2.0, float(sync_interval_sec))
        if parties is not None:
            self.config["parties"] = self._sanitize_parties(parties)

        return self.save_config()

    @property
    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    @property
    def mode(self) -> str:
        return str(self.config.get("mode", "auto_5"))

    @property
    def leader_slot(self) -> int:
        return int(self.config.get("leader_slot", 1))

    @property
    def party_pass(self) -> str:
        return str(self.config.get("party_pass", "1234")).strip()

    @property
    def auto_re_pass(self) -> bool:
        return bool(self.config.get("auto_re_pass", True))

    @property
    def auto_reconnect(self) -> bool:
        return bool(self.config.get("auto_reconnect", True))

    @property
    def sync_interval(self) -> float:
        return float(self.config.get("sync_interval_sec", 6.0))

    # --------------------------------------------------------------------------
    # CHIA NHÓM VÀ QUẢN LÝ NHIỀU PARTY (MULTI-PT)
    # --------------------------------------------------------------------------
    @staticmethod
    def auto_split_parties(
        slots: List[int],
        default_pass: str = "1234",
        max_per_pt: int = 5,
        configured_parties: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tự động phân bổ danh sách slots thành các nhóm PT (tối đa max_per_pt slot / nhóm):
        - Cứ đủ max_per_pt (5) tài khoản là tự động tạo một nhóm PT mới độc lập.
        - Mỗi nhóm PT có Chủ PT (Leader) và các Thành viên (Members) riêng.
        - Nếu có configured_parties (người dùng đã chọn Chủ PT cụ thể cho nhóm), giữ nguyên Chủ PT được chọn.
        """
        cleaned_slots = sorted(list(set(int(s) for s in slots if int(s) > 0)))
        if not cleaned_slots:
            return [{
                "id": 1,
                "name": "PT 1",
                "leader_slot": 1,
                "member_slots": [],
                "party_pass": default_pass
            }]

        cfg_map: Dict[int, Dict[str, Any]] = {}
        if configured_parties:
            for p in configured_parties:
                if isinstance(p, dict) and "id" in p:
                    cfg_map[int(p["id"])] = p

        parties: List[Dict[str, Any]] = []
        party_idx = 1
        for i in range(0, len(cleaned_slots), max_per_pt):
            chunk = cleaned_slots[i:i + max_per_pt]
            
            existing = cfg_map.get(party_idx)
            saved_lead = int(existing.get("leader_slot", 0)) if existing else 0
            saved_pass = str(existing.get("party_pass", default_pass)).strip() if existing else default_pass
            saved_name = str(existing.get("name", f"PT {party_idx}")).strip() if existing else f"PT {party_idx}"

            # Nếu Leader đã cấu hình trước đó nằm trong chunk của nhóm này thì ưu tiên giữ nguyên
            if saved_lead in chunk:
                l_slot = saved_lead
            else:
                l_slot = chunk[0]

            m_slots = [s for s in chunk if s != l_slot]

            parties.append({
                "id": party_idx,
                "name": saved_name or f"PT {party_idx}",
                "leader_slot": l_slot,
                "member_slots": m_slots,
                "party_pass": saved_pass or default_pass
            })
            party_idx += 1
        return parties

    def _sanitize_parties(self, raw_parties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Làm sạch và chuẩn hóa danh sách Party cấu hình."""
        clean: List[Dict[str, Any]] = []
        default_pwd = self.party_pass
        for idx, p in enumerate(raw_parties, 1):
            if not isinstance(p, dict):
                continue
            l_slot = int(p.get("leader_slot", idx))
            raw_members = p.get("member_slots", [])
            if isinstance(raw_members, str):
                # Hỗ trợ chuỗi phân tách dấu phẩy vd "2, 3, 4, 5"
                m_slots = []
                for part in raw_members.replace(";", ",").split(","):
                    part = part.strip()
                    if part.isdigit():
                        m_slots.append(int(part))
            elif isinstance(raw_members, list):
                m_slots = [int(s) for s in raw_members if str(s).isdigit() or isinstance(s, int)]
            else:
                m_slots = []

            # Loại bỏ leader ra khỏi danh sách member và giới hạn tối đa 4 member (1 leader + 4 = 5)
            m_slots = [s for s in m_slots if s != l_slot and s > 0][:4]

            clean.append({
                "id": int(p.get("id", idx)),
                "name": str(p.get("name", f"PT {idx}")).strip() or f"PT {idx}",
                "leader_slot": l_slot,
                "member_slots": m_slots,
                "party_pass": str(p.get("party_pass", default_pwd)).strip() or default_pwd
            })
        return clean

    def get_parties(self, controllers: Optional[list] = None) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các nhóm Party hiện hành:
        - Nếu mode == 'custom' và có cấu hình parties: Trả về danh sách custom đã được chuẩn hóa.
        - Nếu mode == 'auto_5': Tự động chia các slot theo quy tắc 5 acc/nhóm (giữ nguyên Chủ PT đã chỉ định nếu có).
        """
        # Cập nhật cache slot
        if controllers:
            slots = [getattr(c, "slot_idx", 0) for c in controllers if getattr(c, "slot_idx", 0) > 0]
            if slots:
                self._last_known_slots = sorted(list(set(slots)))

        available_slots = self._last_known_slots or list(range(1, 11))
        configured = self._sanitize_parties(self.config.get("parties", [])) if self.config.get("parties") else None

        if self.mode == "custom" and configured:
            return configured

        # Chế độ tự động chia 5 acc/nhóm (tự động phân bổ hoặc giữ nguyên Leader đã cấu hình)
        return self.auto_split_parties(
            available_slots,
            self.party_pass,
            max_per_pt=5,
            configured_parties=configured
        )

    def is_leader(self, slot_idx: int, controllers: Optional[list] = None) -> bool:
        """Kiểm tra slot_idx có phải là Chủ PT (Leader) của bất kỳ nhóm nào không."""
        parties = self.get_parties(controllers)
        for p in parties:
            if int(p.get("leader_slot", 0)) == slot_idx:
                return True
        return False

    def get_slot_party_role(
        self,
        slot_idx: int,
        controllers: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Xác định vai trò và thông tin nhóm của 1 slot_idx.
        Returns: {
            "party_id": int,
            "party_name": str,
            "is_leader": bool,
            "leader_slot": int,
            "role_display": str,   # vd "👑 Chủ PT 1" hoặc "👥 TV PT 1"
            "party_pass": str
        }
        """
        parties = self.get_parties(controllers)
        for p in parties:
            p_id = int(p.get("id", 1))
            p_name = p.get("name", f"PT {p_id}")
            l_slot = int(p.get("leader_slot", 0))
            m_slots = [int(s) for s in p.get("member_slots", [])]

            if slot_idx == l_slot:
                return {
                    "party_id": p_id,
                    "party_name": p_name,
                    "is_leader": True,
                    "leader_slot": l_slot,
                    "role_display": f"👑 Chủ {p_name}",
                    "party_pass": str(p.get("party_pass", self.party_pass))
                }
            elif slot_idx in m_slots:
                return {
                    "party_id": p_id,
                    "party_name": p_name,
                    "is_leader": False,
                    "leader_slot": l_slot,
                    "role_display": f"👥 TV {p_name}",
                    "party_pass": str(p.get("party_pass", self.party_pass))
                }

        return {
            "party_id": 0,
            "party_name": "Chưa gán",
            "is_leader": False,
            "leader_slot": 0,
            "role_display": "⚪ Chưa gán PT",
            "party_pass": self.party_pass
        }

    # --------------------------------------------------------------------------
    # ĐỌC TRẠNG THÁI PARTY TỪ RAM
    # --------------------------------------------------------------------------
    def read_slot_party_info(
        self,
        ctrl,
        max_cache_age: float = 1.5,
        controllers: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Đọc thông tin Party của 1 slot (có cache ngắn hạn tránh đè RAM).
        Returns: {
            "in_party": bool,
            "is_leader": bool,
            "leader_name": str,
            "member_count": int,
            "members": list,
            "role": str,
            "party_name": str,
            "party_id": int,
            "connected": bool
        }
        """
        slot_idx = getattr(ctrl, "slot_idx", 0)
        now = time.time()

        cached = self._slot_party_cache.get(slot_idx)
        if cached and (now - cached.get("ts", 0) < max_cache_age):
            return cached.get("data", {})

        pid = getattr(ctrl, "assigned_pid", None)
        role_info = self.get_slot_party_role(slot_idx, controllers)

        default_data = {
            "in_party": False,
            "is_leader": False,
            "leader_name": "",
            "member_count": 0,
            "members": [],
            "role": "leader" if role_info["is_leader"] else "member",
            "role_display": role_info["role_display"],
            "party_name": role_info["party_name"],
            "party_id": role_info["party_id"],
            "configured_leader": role_info["is_leader"],
            "connected": False
        }

        if not pid:
            self._slot_party_cache[slot_idx] = {"data": default_data, "ts": now}
            return default_data

        party_data = default_data
        try:
            if ProcessMemoryReader:
                info = ProcessMemoryReader.read_party_info(pid)
                if info:
                    party_data = {
                        "in_party": info.get("in_party", False),
                        "is_leader": info.get("is_leader", False),
                        "leader_name": info.get("leader_name", ""),
                        "member_count": info.get("member_count", 0),
                        "members": info.get("members", []),
                        "role": "leader" if role_info["is_leader"] else "member",
                        "role_display": role_info["role_display"],
                        "party_name": role_info["party_name"],
                        "party_id": role_info["party_id"],
                        "configured_leader": role_info["is_leader"],
                        "connected": True
                    }
        except Exception as e:
            logger.debug(f"read_slot_party_info slot {slot_idx} error: {e}")

        self._slot_party_cache[slot_idx] = {"data": party_data, "ts": now}
        return party_data

    # --------------------------------------------------------------------------
    # THỰC THI ĐỒNG BỘ MULTI-PT (FORCE SYNC & AUTO TICK)
    # --------------------------------------------------------------------------
    def force_sync_party_async(
        self,
        controllers: list,
        on_complete: Optional[Callable[[bool, str], None]] = None
    ) -> None:
        """Kích hoạt đồng bộ ghép toàn bộ các nhóm Party trong luồng nền (Zero-Lag UI)."""
        t = threading.Thread(
            target=self._run_force_sync,
            args=(controllers, on_complete),
            name="PartyManager_ForceSync",
            daemon=True
        )
        t.start()

    def _run_force_sync(
        self,
        controllers: list,
        on_complete: Optional[Callable[[bool, str], None]] = None
    ) -> None:
        """Luồng thực thi đồng bộ Multi-PT."""
        with self._sync_lock:
            self._is_syncing = True
            try:
                ok, msg = self._execute_sync(controllers)
            except Exception as e:
                ok, msg = False, f"Lỗi đồng bộ Party: {e}"
            finally:
                self._is_syncing = False

        if on_complete:
            try:
                on_complete(ok, msg)
            except Exception:
                pass

    def _execute_sync(self, controllers: list) -> Tuple[bool, str]:
        """
        Thực hiện đồng bộ Auto Multi-PT chuyên sâu (Direct Engine):
        1. Lấy danh sách các nhóm Party (PT 1, PT 2, ...).
        2. Với mỗi nhóm, xác định Leader Slot và Member Slots của riêng nhóm đó.
        3. Bật /re auto [password] cho Leader và Members của nhóm.
        4. Kiểm tra Map và khoảng cách: Nếu Member khác map, tự /move sang map Leader.
        5. Leader của nhóm gửi packet mời (C1:40) trực tiếp tới các Member trong nhóm.
        6. Giám sát RAM IL2CPP của từng nhóm và trả về báo cáo kết quả chi tiết.
        """
        if not controllers:
            return False, "Không có tài khoản nào trong hệ thống!"

        parties = self.get_parties(controllers)
        if not parties:
            return False, "Không tìm thấy cấu hình nhóm PT nào!"

        ctrl_map: Dict[int, Any] = {getattr(c, "slot_idx", 0): c for c in controllers}

        summary_lines: List[str] = []
        total_parties = len(parties)
        success_parties = 0

        for party in parties:
            p_id = int(party.get("id", 1))
            p_name = party.get("name", f"PT {p_id}")
            leader_slot = int(party.get("leader_slot", 1))
            member_slots = [int(s) for s in party.get("member_slots", []) if int(s) != leader_slot][:4]
            password = str(party.get("party_pass", self.party_pass)).strip() or self.party_pass

            leader_ctrl = ctrl_map.get(leader_slot)
            if not leader_ctrl or not getattr(leader_ctrl, "assigned_pid", None):
                summary_lines.append(f"• {p_name}: Chủ nhóm Slot {leader_slot} chưa mở game hoặc chưa gán PID!")
                continue

            leader_pid = leader_ctrl.assigned_pid
            leader_engine = getattr(leader_ctrl, "engine", None)
            if not leader_engine or not getattr(leader_engine, "is_ready", False):
                leader_engine = MegDirectEngine.get_engine(leader_pid)

            leader_name = (
                getattr(leader_ctrl, "char_name", "")
                or ProcessMemoryReader.read_character_name(leader_pid)
                or f"Slot_{leader_slot}"
            )

            leader_live = ProcessMemoryReader.read_live_state(leader_pid)
            leader_map_id = leader_live[0] if leader_live else None
            leader_map_name = leader_live[1] if leader_live else ""
            leader_x = leader_live[2] if leader_live else 0
            leader_y = leader_live[3] if leader_live else 0

            # 1. Bật /re auto cho Leader nhóm
            if leader_engine and hasattr(leader_engine, "set_party_auto_mode"):
                leader_engine.set_party_auto_mode(password=password, enable=True)
            elif hasattr(leader_ctrl, "send_chat_command"):
                cmd = f"/re auto {password}" if password else "/re auto"
                leader_ctrl.send_chat_command(cmd)

            time.sleep(0.2)

            # 2. Xử lý từng Member của nhóm này
            invited_count = 0
            already_in_count = 0
            failed_members: List[str] = []

            for m_slot in member_slots:
                m_ctrl = ctrl_map.get(m_slot)
                if not m_ctrl or not getattr(m_ctrl, "assigned_pid", None):
                    failed_members.append(f"Slot {m_slot} (chưa vào game)")
                    continue

                m_pid = m_ctrl.assigned_pid
                m_engine = getattr(m_ctrl, "engine", None)
                if not m_engine or not getattr(m_engine, "is_ready", False):
                    m_engine = MegDirectEngine.get_engine(m_pid)

                m_name = (
                    getattr(m_ctrl, "char_name", "")
                    or ProcessMemoryReader.read_character_name(m_pid)
                    or f"Slot_{m_slot}"
                )

                # Bật /re auto cho member
                if m_engine and hasattr(m_engine, "set_party_auto_mode"):
                    m_engine.set_party_auto_mode(password=password, enable=True)
                elif hasattr(m_ctrl, "send_chat_command"):
                    cmd = f"/re auto {password}" if password else "/re auto"
                    m_ctrl.send_chat_command(cmd)

                # Kiểm tra xem member đã ở trong party của Leader này chưa
                m_party = ProcessMemoryReader.read_party_info(m_pid)
                if m_party.get("in_party", False):
                    m_lead = m_party.get("leader_name", "").strip().lower()
                    if not leader_name or m_lead == leader_name.lower():
                        already_in_count += 1
                        continue
                    else:
                        # Member đang ở nhóm khác, rời nhóm cũ
                        if m_engine and hasattr(m_engine, "send_chat"):
                            m_engine.send_chat("/re off")
                            time.sleep(0.4)

                # Kiểm tra vị trí / Map của Member
                m_live = ProcessMemoryReader.read_live_state(m_pid)
                m_map_id = m_live[0] if m_live else None
                m_x = m_live[2] if m_live else 0
                m_y = m_live[3] if m_live else 0

                # Nếu khác map, member tự /move sang map của Leader
                if leader_map_id is not None and m_map_id is not None and leader_map_id != m_map_id:
                    if leader_map_name and m_engine:
                        logger.info(f"[AutoParty {p_name}] Di chuyển member {m_name} sang map {leader_map_name} của Leader {leader_name}...")
                        m_engine.send_chat(f"/move {leader_map_name}")
                        time.sleep(2.0)
                        m_live = ProcessMemoryReader.read_live_state(m_pid)
                        if m_live:
                            m_x, m_y = m_live[2], m_live[3]

                # Nếu cùng map nhưng cách xa > 14 ô, di chuyển lại gần
                if m_live and leader_live:
                    dist = ((m_x - leader_x)**2 + (m_y - leader_y)**2)**0.5
                    if dist > 14 and m_engine:
                        logger.info(f"[AutoParty {p_name}] Member {m_name} cách Leader {dist:.1f} ô, di chuyển lại gần...")
                        m_engine.move_to(leader_x, leader_y)
                        time.sleep(1.2)

                # Leader gửi lời mời Party tới Member
                if leader_engine and hasattr(leader_engine, "invite_party_by_name"):
                    logger.info(f"[AutoParty {p_name}] Leader {leader_name} đang gửi lời mời Party tới {m_name}...")
                    inv_res = leader_engine.invite_party_by_name(m_name)
                    if not inv_res.get("ok") and inv_res.get("error") == "player_not_found_in_viewport":
                        if m_engine:
                            m_engine.move_to(leader_x, leader_y)
                        time.sleep(1.5)
                        inv_res = leader_engine.invite_party_by_name(m_name)

                    if inv_res.get("ok"):
                        invited_count += 1
                    else:
                        failed_members.append(f"{m_name} ({inv_res.get('error', 'unknown')})")
                else:
                    failed_members.append(f"{m_name} (no_invite_func)")

                time.sleep(0.3)

            # Chờ 1.0s và kiểm tra RAM của Leader nhóm này
            time.sleep(1.0)
            leader_party = ProcessMemoryReader.read_party_info(leader_pid)
            m_count = leader_party.get("member_count", 1)
            members_in_pt = [m.get("name") for m in leader_party.get("members", []) if m.get("name")]
            names_str = ", ".join(members_in_pt) if members_in_pt else leader_name
            total_expected = 1 + len(member_slots)

            pt_line = f"• {p_name} [Chủ Slot {leader_slot} ({leader_name})]: {m_count}/{total_expected} TV ({names_str})"
            if failed_members:
                pt_line += f"\n   ↳ Cần kiểm tra: {', '.join(failed_members)}"
            summary_lines.append(pt_line)

            if m_count > 1 or already_in_count > 0 or invited_count > 0 or not member_slots:
                success_parties += 1

        ok = (success_parties > 0)
        status_header = (
            f"✅ Đã thiết lập Multi-PT thành công ({success_parties}/{total_parties} nhóm hoàn tất)!"
            if ok else "⚠️ Chưa thể ghép nhóm hoàn chỉnh!"
        )
        final_msg = f"{status_header}\n" + "\n".join(summary_lines)
        return ok, final_msg

    def disable_all_party_async(
        self,
        controllers: list,
        on_complete: Optional[Callable[[bool, str], None]] = None
    ) -> None:
        """Tắt tính năng Auto Party trên toàn bộ các slots (/re off) trong luồng nền."""
        def _worker():
            count = 0
            for ctrl in controllers:
                pid = getattr(ctrl, "assigned_pid", None)
                if not pid:
                    continue
                engine = getattr(ctrl, "engine", None)
                if engine and hasattr(engine, "set_party_auto_mode"):
                    engine.set_party_auto_mode(enable=False)
                    count += 1
                elif hasattr(ctrl, "send_chat_command"):
                    ctrl.send_chat_command("/re off")
                    count += 1
                elif engine and hasattr(engine, "send_chat"):
                    engine.send_chat("/re off")
                    count += 1
                time.sleep(0.15)

            if on_complete:
                try:
                    on_complete(True, f"Đã tắt chế độ Auto Party (/re off) trên {count} tài khoản.")
                except Exception:
                    pass

        t = threading.Thread(target=_worker, name="PartyManager_DisableAll", daemon=True)
        t.start()

    # --------------------------------------------------------------------------
    # TICK ĐỊNH KỲ TỪ HEARTBEAT (MULTI-PT SELF-HEALING)
    # --------------------------------------------------------------------------
    def tick(self, controllers: list) -> None:
        """
        Được gọi định kỳ từ Dashboard Heartbeat (Zero-lag).
        Tự động kiểm tra trạng thái và khôi phục Party cho từng nhóm độc lập.
        """
        if not self.is_enabled:
            return

        now = time.time()
        if now - self._last_tick_time < self.sync_interval:
            return

        self._last_tick_time = now

        # Kiểm tra nếu đang có tác vụ đồng bộ chạy thì bỏ qua
        if self._is_syncing:
            return

        if not self.auto_reconnect:
            return

        # Chạy kiểm tra và hồi phục trong background thread
        threading.Thread(
            target=self._check_and_heal_party,
            args=(controllers,),
            name="PartyManager_HealParty",
            daemon=True
        ).start()

    def _check_and_heal_party(self, controllers: list) -> None:
        """Kiểm tra và tự động gửi lại lệnh ghép nếu phát hiện thành viên của từng nhóm bị rớt hoặc mất PT."""
        if not controllers:
            return

        parties = self.get_parties(controllers)
        if not parties:
            return

        ctrl_map: Dict[int, Any] = {getattr(c, "slot_idx", 0): c for c in controllers}

        for party in parties:
            p_name = party.get("name", "PT")
            leader_slot = int(party.get("leader_slot", 1))
            member_slots = [int(s) for s in party.get("member_slots", []) if int(s) != leader_slot][:4]
            password = str(party.get("party_pass", self.party_pass)).strip() or self.party_pass

            leader_ctrl = ctrl_map.get(leader_slot)
            if not leader_ctrl or not getattr(leader_ctrl, "assigned_pid", None):
                continue

            leader_pid = leader_ctrl.assigned_pid
            leader_engine = getattr(leader_ctrl, "engine", None)
            if not leader_engine or not getattr(leader_engine, "is_ready", False):
                leader_engine = MegDirectEngine.get_engine(leader_pid)

            leader_party = ProcessMemoryReader.read_party_info(leader_pid)
            leader_member_count = leader_party.get("member_count", 0)

            # Nếu Leader đã đủ số thành viên mong đợi (1 Leader + len(member_slots)), không cần heal nhóm này
            total_expected = 1 + len(member_slots)
            if leader_member_count >= total_expected and total_expected > 1:
                continue

            leader_name = (
                getattr(leader_ctrl, "char_name", "")
                or ProcessMemoryReader.read_character_name(leader_pid)
                or ""
            )

            leader_live = ProcessMemoryReader.read_live_state(leader_pid)
            leader_map_id = leader_live[0] if leader_live else None
            leader_map_name = leader_live[1] if leader_live else ""
            leader_x = leader_live[2] if leader_live else 0
            leader_y = leader_live[3] if leader_live else 0

            # Kiểm tra từng Member của nhóm này
            missing_members = []
            for m_slot in member_slots:
                m_ctrl = ctrl_map.get(m_slot)
                if not m_ctrl or not getattr(m_ctrl, "assigned_pid", None):
                    continue

                m_info = self.read_slot_party_info(m_ctrl, max_cache_age=0.5, controllers=controllers)
                # Nếu thành viên đang kết nối nhưng KHÔNG ở trong party hoặc đang ở party khác
                if not m_info.get("in_party", False):
                    missing_members.append(m_ctrl)
                elif leader_name and m_info.get("leader_name", "").strip().lower() != leader_name.lower():
                    missing_members.append(m_ctrl)

            if missing_members:
                # 1. Đảm bảo Leader vẫn bật /re auto
                if leader_engine and hasattr(leader_engine, "set_party_auto_mode"):
                    leader_engine.set_party_auto_mode(password=password, enable=True)

                # 2. Xử lý và mời các thành viên chưa có party của nhóm này
                for m_ctrl in missing_members:
                    m_pid = getattr(m_ctrl, "assigned_pid", None)
                    if not m_pid:
                        continue

                    m_engine = getattr(m_ctrl, "engine", None)
                    if not m_engine or not getattr(m_engine, "is_ready", False):
                        m_engine = MegDirectEngine.get_engine(m_pid)

                    m_name = (
                        getattr(m_ctrl, "char_name", "")
                        or ProcessMemoryReader.read_character_name(m_pid)
                        or ""
                    )

                    # Bật /re auto cho member
                    if m_engine and hasattr(m_engine, "set_party_auto_mode"):
                        m_engine.set_party_auto_mode(password=password, enable=True)

                    # Kiểm tra map
                    m_live = ProcessMemoryReader.read_live_state(m_pid)
                    m_map_id = m_live[0] if m_live else None
                    if leader_map_id is not None and m_map_id is not None and leader_map_id != m_map_id:
                        if leader_map_name and m_engine:
                            m_engine.send_chat(f"/move {leader_map_name}")
                            time.sleep(2.0)
                            m_live = ProcessMemoryReader.read_live_state(m_pid)

                    # Mời vào Party
                    if leader_engine and hasattr(leader_engine, "invite_party_by_name") and m_name:
                        res = leader_engine.invite_party_by_name(m_name)
                        logger.info(f"[AutoParty Heal {p_name}] Tự động mời {m_name} vào nhóm {p_name}: {res}")

                    time.sleep(0.3)
