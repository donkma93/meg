# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - PARTY MANAGER SERVICE
Quản lý tự động ghép nhóm (Auto PT) giữa các tài khoản MEGAMU:
- 1 Tài khoản được chỉ định làm Chủ PT (Leader) và các tài khoản còn lại là Thành viên (Members).
- Quản lý lệnh in-game /re auto [password] và /re off qua Direct Engine / Native Chat.
- Giám sát trạng thái Party từ RAM IL2CPP (InParty, IsLeader, LeaderName, Danh sách thành viên).
- Tự động duy trì và khôi phục Party khi nhân vật chết, chuyển map hoặc relogin.
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
    "leader_slot": 1,
    "party_pass": "1234",
    "auto_re_pass": True,
    "auto_reconnect": True,
    "sync_interval_sec": 6.0
}


class PartyManager:
    """Singleton Service quản lý Auto Party cho toàn bộ các Slots."""

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
        leader_slot: Optional[int] = None,
        party_pass: Optional[str] = None,
        auto_re_pass: Optional[bool] = None,
        auto_reconnect: Optional[bool] = None,
        sync_interval_sec: Optional[float] = None
    ) -> bool:
        """Cập nhật các tham số cấu hình Party và ghi đĩa."""
        if enabled is not None:
            self.config["enabled"] = bool(enabled)
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

        return self.save_config()

    @property
    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

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

    def is_leader(self, slot_idx: int) -> bool:
        """Kiểm tra slot_idx có phải là Trưởng nhóm (Leader) theo cấu hình không."""
        return slot_idx == self.leader_slot

    # --------------------------------------------------------------------------
    # ĐỌC TRẠNG THÁI PARTY TỪ RAM
    # --------------------------------------------------------------------------
    def read_slot_party_info(self, ctrl, max_cache_age: float = 1.5) -> Dict[str, Any]:
        """
        Đọc thông tin Party của 1 slot (có cache ngắn hạn tránh đè RAM).
        Returns: {
            "in_party": bool,
            "is_leader": bool,
            "leader_name": str,
            "member_count": int,
            "members": list,
            "role": "leader" | "member"
        }
        """
        slot_idx = getattr(ctrl, "slot_idx", 0)
        now = time.time()

        cached = self._slot_party_cache.get(slot_idx)
        if cached and (now - cached.get("ts", 0) < max_cache_age):
            return cached.get("data", {})

        pid = getattr(ctrl, "assigned_pid", None)
        default_data = {
            "in_party": False,
            "is_leader": False,
            "leader_name": "",
            "member_count": 0,
            "members": [],
            "role": "leader" if self.is_leader(slot_idx) else "member",
            "connected": False
        }

        if not pid:
            self._slot_party_cache[slot_idx] = {"data": default_data, "ts": now}
            return default_data

        party_data = default_data
        try:
            from meg_navigator import ProcessMemoryReader
            if ProcessMemoryReader:
                info = ProcessMemoryReader.read_party_info(pid)
                if info:
                    party_data = {
                        "in_party": info.get("in_party", False),
                        "is_leader": info.get("is_leader", False),
                        "leader_name": info.get("leader_name", ""),
                        "member_count": info.get("member_count", 0),
                        "members": info.get("members", []),
                        "role": "leader" if self.is_leader(slot_idx) else "member",
                        "connected": True
                    }
        except Exception as e:
            logger.debug(f"read_slot_party_info slot {slot_idx} error: {e}")

        self._slot_party_cache[slot_idx] = {"data": party_data, "ts": now}
        return party_data

    # --------------------------------------------------------------------------
    # THỰC THI ĐỒNG BỘ PARTY (FORCE SYNC & AUTO TICK)
    # --------------------------------------------------------------------------
    def force_sync_party_async(
        self,
        controllers: list,
        on_complete: Optional[Callable[[bool, str], None]] = None
    ) -> None:
        """Kích hoạt đồng bộ ghép Party toàn bộ slot trong luồng nền (Zero-Lag UI)."""
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
        """Luồng thực thi đồng bộ Party."""
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
        Thực hiện đồng bộ Auto Party chuyên sâu (Direct Engine):
        1. Xác định Leader Slot và các Member Slots.
        2. Bật /re auto [password] cho toàn bộ Leader và Members để tự động chấp nhận lời mời.
        3. Kiểm tra map: Nếu Member ở map khác, tự động /move sang map của Leader.
        4. Kiểm tra khoảng cách: Nếu quá xa (>14 ô), Member tự di chuyển lại gần Leader.
        5. Leader gửi packet mời Party (C1:40) trực tiếp qua nativePartyInviteByKey trên Main Thread.
        6. Giám sát RAM IL2CPP và xác thực kết quả tạo Party thành công 100%.
        """
        if not controllers:
            return False, "Không có tài khoản nào trong hệ thống!"

        leader_slot = self.leader_slot
        password = self.party_pass

        leader_ctrl = None
        member_ctrls = []

        for ctrl in controllers:
            s_idx = getattr(ctrl, "slot_idx", 0)
            if s_idx == leader_slot:
                leader_ctrl = ctrl
            else:
                member_ctrls.append(ctrl)

        if not leader_ctrl or not getattr(leader_ctrl, "assigned_pid", None):
            return False, f"Chủ PT (Slot {leader_slot}) chưa mở game hoặc chưa được gán PID!"

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

        # 1. Bật /re auto cho Leader trước
        if leader_engine and hasattr(leader_engine, "set_party_auto_mode"):
            leader_engine.set_party_auto_mode(password=password, enable=True)
        elif hasattr(leader_ctrl, "send_chat_command"):
            cmd = f"/re auto {password}" if password else "/re auto"
            leader_ctrl.send_chat_command(cmd)

        time.sleep(0.3)

        # 2. Xử lý từng Member: Bật /re auto, check map, di chuyển và mời Party
        invited_count = 0
        already_in_count = 0
        failed_members = []

        for m_ctrl in member_ctrls:
            m_pid = getattr(m_ctrl, "assigned_pid", None)
            if not m_pid:
                continue

            m_engine = getattr(m_ctrl, "engine", None)
            if not m_engine or not getattr(m_engine, "is_ready", False):
                m_engine = MegDirectEngine.get_engine(m_pid)

            m_name = (
                getattr(m_ctrl, "char_name", "")
                or ProcessMemoryReader.read_character_name(m_pid)
                or f"Slot_{getattr(m_ctrl, 'slot_idx', 0)}"
            )

            # Bật /re auto cho thành viên
            if m_engine and hasattr(m_engine, "set_party_auto_mode"):
                m_engine.set_party_auto_mode(password=password, enable=True)
            elif hasattr(m_ctrl, "send_chat_command"):
                cmd = f"/re auto {password}" if password else "/re auto"
                m_ctrl.send_chat_command(cmd)

            # Kiểm tra xem thành viên đã ở trong nhóm của Leader chưa
            m_party = ProcessMemoryReader.read_party_info(m_pid)
            if m_party.get("in_party", False):
                m_lead = m_party.get("leader_name", "").strip().lower()
                if not leader_name or m_lead == leader_name.lower():
                    already_in_count += 1
                    continue

            # Kiểm tra vị trí / Map của Member
            m_live = ProcessMemoryReader.read_live_state(m_pid)
            m_map_id = m_live[0] if m_live else None
            m_x = m_live[2] if m_live else 0
            m_y = m_live[3] if m_live else 0

            # Nếu khác map, yêu cầu member chuyển sang map của Leader
            if leader_map_id is not None and m_map_id is not None and leader_map_id != m_map_id:
                if leader_map_name and m_engine:
                    logger.info(f"[AutoParty] Di chuyển thành viên {m_name} sang map {leader_map_name} của Leader...")
                    m_engine.send_chat(f"/move {leader_map_name}")
                    time.sleep(2.0)
                    m_live = ProcessMemoryReader.read_live_state(m_pid)
                    if m_live:
                        m_x, m_y = m_live[2], m_live[3]

            # Nếu cùng map nhưng khoảng cách quá xa (> 14 ô), cho member di chuyển lại gần
            if m_live and leader_live:
                dist = ((m_x - leader_x)**2 + (m_y - leader_y)**2)**0.5
                if dist > 14 and m_engine:
                    logger.info(f"[AutoParty] Thành viên {m_name} cách Leader {dist:.1f} ô, di chuyển lại gần...")
                    m_engine.move_to(leader_x, leader_y)
                    time.sleep(1.2)

            # Leader gửi lời mời Party trực tiếp tới Member
            if leader_engine and hasattr(leader_engine, "invite_party_by_name"):
                logger.info(f"[AutoParty] Leader {leader_name} đang gửi lời mời Party tới {m_name}...")
                inv_res = leader_engine.invite_party_by_name(m_name)
                if not inv_res.get("ok") and inv_res.get("error") == "player_not_found_in_viewport":
                    # Thử cho member tiến thẳng vào toạ độ Leader và mời lại
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

            time.sleep(0.4)

        # Chờ 1.5s để server hoàn tất cập nhật packet party
        time.sleep(1.5)

        # Xác thực kết quả từ RAM IL2CPP
        leader_party = ProcessMemoryReader.read_party_info(leader_pid)
        member_count = leader_party.get("member_count", 1)
        members_in_party = [m.get("name") for m in leader_party.get("members", []) if m.get("name")]
        names_str = ", ".join(members_in_party) if members_in_party else leader_name

        if member_count > 1 or already_in_count > 0 or invited_count > 0:
            msg = (
                f"✅ Đã thiết lập Auto PT thành công!\n"
                f"• Chủ nhóm: Slot {leader_slot} ({leader_name})\n"
                f"• Tổng thành viên trong PT: {member_count}/5\n"
                f"• Danh sách: {names_str}\n"
                f"• Mật khẩu: '{password}'"
            )
            if failed_members:
                msg += f"\n• Cần kiểm tra: {', '.join(failed_members)}"
            return True, msg
        else:
            err_details = f": {', '.join(failed_members)}" if failed_members else ""
            return False, f"Chưa thể ghép nhóm{err_details}. Vui lòng kiểm tra các nhân vật đã vào game và ở cùng map!"

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
    # TICK ĐỊNH KỲ TỪ HEARTBEAT
    # --------------------------------------------------------------------------
    def tick(self, controllers: list) -> None:
        """
        Được gọi định kỳ từ Dashboard Heartbeat (Zero-lag).
        Tự động kiểm tra trạng thái và khôi phục Party nếu có thành viên bị rớt hoặc mất PT.
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
        """Kiểm tra và tự động gửi lại lệnh ghép nếu phát hiện thành viên chưa vào PT."""
        if not controllers:
            return

        leader_ctrl = None
        member_ctrls = []
        for ctrl in controllers:
            if getattr(ctrl, "slot_idx", 0) == self.leader_slot:
                leader_ctrl = ctrl
            else:
                member_ctrls.append(ctrl)

        if not leader_ctrl or not getattr(leader_ctrl, "assigned_pid", None):
            return

        leader_pid = leader_ctrl.assigned_pid
        leader_engine = getattr(leader_ctrl, "engine", None)
        if not leader_engine or not getattr(leader_engine, "is_ready", False):
            leader_engine = MegDirectEngine.get_engine(leader_pid)

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

        # Kiểm tra từng Member
        missing_members = []
        for m_ctrl in member_ctrls:
            pid = getattr(m_ctrl, "assigned_pid", None)
            if not pid:
                continue

            m_info = self.read_slot_party_info(m_ctrl, max_cache_age=0.5)
            # Nếu thành viên đang kết nối nhưng KHÔNG ở trong party
            if not m_info.get("in_party", False):
                missing_members.append(m_ctrl)

        if missing_members:
            password = self.party_pass

            # 1. Đảm bảo Leader vẫn bật /re auto
            if leader_engine and hasattr(leader_engine, "set_party_auto_mode"):
                leader_engine.set_party_auto_mode(password=password, enable=True)

            # 2. Xử lý và mời các thành viên chưa có party
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
                    logger.info(f"[AutoParty Heal] Tự động mời {m_name} vào nhóm: {res}")

                time.sleep(0.3)
