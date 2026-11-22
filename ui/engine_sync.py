# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - BACKGROUND ENGINE SYNCHRONIZER
Bộ điều phối đa luồng độc lập, thu thập telemetry từ game MEGAMU vào AppStateManager.
Tuyệt đối không chạy trên Main UI Thread, không nghẽn Tkinter Event Loop.
"""

import time
import threading
import ctypes
from typing import Dict, Any, List, Optional, Callable
import psutil

from ui.state import AppStateManager

try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None

try:
    from meg_navigator import ProcessMemoryReader, MAP_CATALOG
except ImportError:
    ProcessMemoryReader = None
    MAP_CATALOG = {}

try:
    from meg_gui import (
        character_name_from_window_title as _gui_char_from_title,
        server_from_window_title as _gui_srv_from_title,
        CLASS_ID_TO_CODE as _GUI_CLASS_ID_TO_CODE,
    )
except Exception:
    _gui_char_from_title = None
    _gui_srv_from_title = None
    _GUI_CLASS_ID_TO_CODE = {}

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def _parse_title_char_and_server(raw_title: str):
    """Trích xuất (char_name, server_num_str) nhanh từ Window Title của MEGAMU (hỗ trợ mọi định dạng)."""
    import re
    if not raw_title:
        return "", ""

    name = ""
    if _gui_char_from_title:
        try:
            name = _gui_char_from_title(raw_title) or ""
        except Exception:
            name = ""

    if not name:
        m1 = re.match(r"^(?P<name>[^(\-\[\]]+?)\s*(?:\([^)]+\))?\s*[-–—]\s*MEGAMU", raw_title, re.IGNORECASE)
        if m1:
            cand = m1.group("name").strip()
            if cand and not cand.upper().startswith("MEGAMU"):
                name = cand
        elif "[" in raw_title and "]" in raw_title:
            try:
                cand = raw_title.split("[")[1].split("]")[0].strip()
                if cand and not re.match(r"^(?:Sv|Sub|Server)\s*\d+$", cand, re.IGNORECASE):
                    name = cand
            except Exception:
                pass

    srv_str = ""
    if _gui_srv_from_title:
        try:
            s_num = _gui_srv_from_title(raw_title)
            if s_num:
                srv_str = f"Sv{s_num}"
        except Exception:
            srv_str = ""

    if not srv_str:
        m_srv = re.search(r"(?:Sv|Server|Sub)\.?\s*(\d+)", raw_title, re.IGNORECASE)
        if m_srv:
            srv_str = f"Sv{m_srv.group(1)}"

    return name, srv_str


def _fast_find_megamu_pids() -> set:
    """Tìm nhanh tất cả PID của MEGAMU.exe bằng Win32 CreateToolhelp32Snapshot (~5ms thay vì ~1300ms của psutil.process_iter)."""
    pids = set()
    if hasattr(ctypes, "windll"):
        try:
            from ctypes import wintypes
            TH32CS_SNAPPROCESS = 0x00000002
            INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

            class _PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260),
                ]

            k32 = ctypes.windll.kernel32
            k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
            k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]

            snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snap and snap != INVALID_HANDLE_VALUE:
                try:
                    pe = _PROCESSENTRY32W()
                    pe.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
                    if k32.Process32FirstW(snap, ctypes.byref(pe)):
                        while True:
                            if pe.szExeFile.lower() == "megamu.exe":
                                pids.add(int(pe.th32ProcessID))
                            if not k32.Process32NextW(snap, ctypes.byref(pe)):
                                break
                finally:
                    k32.CloseHandle(snap)
                # Chỉ kiểm tra RSS trên đúng các PID MEGAMU khớp được (rất nhanh, < 1ms)
                valid_pids = set()
                for pid in pids:
                    try:
                        p = psutil.Process(pid)
                        if p.memory_info().rss >= 15 * 1024 * 1024:
                            valid_pids.add(pid)
                    except Exception:
                        pass
                return valid_pids
        except Exception:
            pass

    for p in psutil.process_iter(['pid', 'name', 'status']):
        try:
            if p.info['name'] and p.info['name'].lower() == 'megamu.exe':
                if p.info.get('status') in (getattr(psutil, 'STATUS_ZOMBIE', 'zombie'), getattr(psutil, 'STATUS_DEAD', 'dead')):
                    continue
                if p.memory_info().rss >= 15 * 1024 * 1024:
                    pids.add(p.info['pid'])
        except Exception:
            pass
    return pids


def enumerate_megamu_processes() -> Dict[int, str]:
    """Tìm tất cả tiến trình MEGAMU.exe thực sự đang chạy (~6ms, không nghẽn GIL) và lấy tiêu đề cửa sổ."""
    pids = _fast_find_megamu_pids()
    pid_to_title = {pid: "" for pid in pids}
    if not user32 or not pids:
        return pid_to_title

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if "megamu" in title.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                p_val = pid.value
                if p_val in pid_to_title and not pid_to_title[p_val]:
                    pid_to_title[p_val] = title
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    return pid_to_title


def build_enhanced_detected_games(games: Optional[Dict[int, str]] = None) -> Dict[int, str]:
    """Chuẩn hóa danh sách {pid: 'CharName [SvX] (PID 1234)'} cho toàn bộ cửa sổ MEGAMU (không giới hạn 10 client)."""
    raw_games = games if games is not None else enumerate_megamu_processes()
    enhanced_games: Dict[int, str] = {}
    for pid, raw_title in raw_games.items():
        name, srv_str = _parse_title_char_and_server(raw_title)
        if not name and ProcessMemoryReader:
            try:
                name = ProcessMemoryReader.read_character_name(pid) or ""
            except Exception:
                pass

        server_tag = f" [{srv_str}]" if srv_str else ""
        if not server_tag and ProcessMemoryReader and hasattr(ProcessMemoryReader, "read_character_server"):
            try:
                srv_code = ProcessMemoryReader.read_character_server(pid)
                if srv_code:
                    server_tag = f" [Sv{srv_code}]"
            except Exception:
                pass

        disp_title = f"{name}{server_tag} (PID {pid})" if name else (raw_title or f"MEGAMU ({pid})")
        enhanced_games[pid] = disp_title
    return enhanced_games


class BackgroundEngineSync:
    """Bộ thu thập dữ liệu nền chạy Daemon Thread liên tục."""

    def __init__(self, controllers_provider: Callable[[], list], state_mgr: Optional[AppStateManager] = None):
        self.controllers_provider = controllers_provider
        self.state_mgr = state_mgr or AppStateManager()
        self.running = False
        self._scan_trigger_event = threading.Event()
        self._threads: List[threading.Thread] = []

    def start(self):
        """Khởi động toàn bộ luồng đồng bộ nền."""
        if self.running:
            return
        self.running = True

        t_scan = threading.Thread(target=self._game_scan_loop, daemon=True, name="EngineSync_GameScan")
        t_telem = threading.Thread(target=self._telemetry_loop, daemon=True, name="EngineSync_Telemetry")
        t_events = threading.Thread(target=self._events_loop, daemon=True, name="EngineSync_Events")

        self._threads = [t_scan, t_telem, t_events]
        for t in self._threads:
            t.start()

    def stop(self):
        """Dừng tất cả worker an toàn."""
        self.running = False
        self._scan_trigger_event.set()

    def trigger_scan_now(self):
        """Yêu cầu quét ngay tiến trình mà không cần chờ hết chu kỳ ngủ."""
        self._scan_trigger_event.set()

    # --------------------------------------------------------------------------
    # LUỒNG 1: QUÉT TIẾN TRÌNH & THU THẬP THÔNG TIN TIÊU ĐỀ (KHÔNG GIỚI HẠN 10 CLIENT)
    # --------------------------------------------------------------------------
    def _game_scan_loop(self):
        # Chờ 0.5s để Main UI Thread dựng xong giao diện ban đầu
        time.sleep(0.5)
        while self.running:
            try:
                enhanced_games = build_enhanced_detected_games()
                self.state_mgr.update_detected_games(enhanced_games)
            except Exception:
                pass

            # Ngủ 4.0s hoặc thức dậy ngay nếu có sự kiện quét thủ công
            self._scan_trigger_event.wait(timeout=4.0)
            self._scan_trigger_event.clear()

    # --------------------------------------------------------------------------
    # LUỒNG 2: ĐỌC TELEMETRY TOÀN BỘ SLOTS (HỖ TRỢ 11..50+ SLOTS, CHỐNG NGHẼN GUI 100%)
    # --------------------------------------------------------------------------
    def _telemetry_loop(self):
        import gc
        last_gc = time.time()
        # Chờ 0.8s để Main UI Thread hoàn tất khởi tạo ban đầu
        time.sleep(0.8)

        while self.running:
            try:
                controllers = list(self.controllers_provider() or [])
                detected_snapshot = self.state_mgr.get_detected_games()
                for ctrl in controllers:
                    pid = getattr(ctrl, "assigned_pid", None)
                    s_idx = getattr(ctrl, "slot_idx", 0)
                    if not pid or s_idx <= 0:
                        continue

                    self.state_mgr.ensure_slot(s_idx)

                    # Kiểm tra PID còn sống không
                    if not psutil.pid_exists(pid):
                        if MegDirectEngine:
                            try:
                                MegDirectEngine.release_engine(pid)
                            except Exception:
                                pass
                        ctrl.assigned_pid = None
                        ctrl.engine = None
                        ctrl.char_name = "---"
                        self.state_mgr.update_slot_telemetry(
                            slot_idx=s_idx,
                            status="Game đã đóng",
                            is_running=False,
                            assigned_pid=None,
                            char_name="---",
                            level="---",
                            coords="--,--",
                            server="---"
                        )
                        continue

                    # Đọc dữ liệu từ Direct Engine hoặc MemoryReader
                    p_info = None
                    engine = getattr(ctrl, "engine", None)
                    if engine:
                        try:
                            p_info = engine.get_player_info(max_age=1.2, allow_blocking=False)
                        except Exception:
                            pass

                    if not p_info and ProcessMemoryReader:
                        try:
                            live = ProcessMemoryReader.read_live_state(pid)
                            lvl = ProcessMemoryReader.read_character_level(pid)
                            cname = getattr(ctrl, "char_name", "---")
                            if not cname or cname == "---":
                                disp_t = detected_snapshot.get(pid, "")
                                t_name, t_srv = _parse_title_char_and_server(disp_t)
                                if t_name:
                                    cname = t_name
                                else:
                                    cname = ProcessMemoryReader.read_character_name(pid) or "---"
                                if t_srv and (not getattr(ctrl, "server_name", None) or ctrl.server_name == "---"):
                                    ctrl.server_name = t_srv
                            p_info = {
                                "name": cname,
                                "level": lvl or 0,
                                "tileX": live[2] if live and live[2] is not None else 0,
                                "tileY": live[3] if live and live[3] is not None else 0,
                                "mapId": live[0] if live and live[0] is not None else -1,
                                "mapName": live[1] if live and live[1] else "",
                            }
                        except Exception:
                            pass

                    if p_info:
                        px = p_info.get("tileX", p_info.get("x", 0))
                        py = p_info.get("tileY", p_info.get("y", 0))
                        coords_str = f"{px},{py}" if (px > 0 or py > 0) else "--,--"

                        lvl_val = p_info.get("level", 0)
                        lvl_str = str(lvl_val) if lvl_val > 0 else "---"

                        map_name = p_info.get("mapName", "")
                        if not map_name and "mapId" in p_info:
                            mid = p_info.get("mapId", -1)
                            map_name = MAP_CATALOG.get(mid, f"Map {mid}") if mid >= 0 else "---"

                        # Đồng bộ ngược vào controller để các tab Mirror, Moss đọc chính xác
                        p_name = p_info.get("name")
                        if p_name and p_name != "---":
                            ctrl.char_name = p_name
                            ctrl.last_known_char_name = p_name
                        if lvl_str != "---":
                            ctrl.level = lvl_str
                        if coords_str != "--,--":
                            ctrl.coords = coords_str
                        if map_name != "---":
                            ctrl.current_map = map_name
                        if "classId" in p_info:
                            try:
                                cid = int(p_info.get("classId", -1))
                                if cid >= 0:
                                    ctrl.class_id = cid
                                    c_code = _GUI_CLASS_ID_TO_CODE.get(cid, "")
                                    if c_code:
                                        ctrl.class_code = c_code
                            except Exception:
                                pass
                        if (not getattr(ctrl, "server_name", None) or ctrl.server_name == "---"):
                            disp_t = detected_snapshot.get(pid, "")
                            _, t_srv = _parse_title_char_and_server(disp_t)
                            if t_srv:
                                ctrl.server_name = t_srv

                        # Trạng thái Auto Train của worker
                        worker = getattr(ctrl, "worker", None)
                        is_running = bool(worker and getattr(worker, "running", False))
                        status_str = getattr(ctrl, "status", "Sẵn sàng")

                        # Cập nhật vào AppStateManager bằng State Diffing
                        self.state_mgr.update_slot_telemetry(
                            slot_idx=s_idx,
                            char_name=p_info.get("name") or getattr(ctrl, "char_name", "---"),
                            level=lvl_str,
                            coords=coords_str,
                            server=getattr(ctrl, "server_name", "---"),
                            resets=p_info.get("resets") or getattr(ctrl, "current_resets", 0),
                            points=p_info.get("points") or getattr(ctrl, "points", 0),
                            master_points=p_info.get("masterPoints") or getattr(ctrl, "master_points", 0),
                            class_code=getattr(ctrl, "class_code", ""),
                            status=status_str,
                            is_running=is_running,
                            assigned_pid=pid,
                            map=map_name,
                            profile=f"Config {getattr(ctrl, 'profile_index', 1)}"
                        )

            except Exception:
                pass

            # Dọn rác heap định kỳ 120s
            now = time.time()
            if now - last_gc >= 120.0:
                last_gc = now
                try:
                    if MegDirectEngine:
                        MegDirectEngine.prune_dead_engines()
                    if ProcessMemoryReader:
                        ProcessMemoryReader.prune_dead_pids()
                    gc.collect()
                except Exception:
                    pass

            time.sleep(0.5)

    # --------------------------------------------------------------------------
    # LUỒNG 3: TÍNH TOÁN SỰ KIỆN DOUBLE GOER (MIRROR) & MOSS ĐẾM NGƯỢC
    # --------------------------------------------------------------------------
    def _events_loop(self):
        """Đếm ngược Mirror/Moss chuẩn xác theo Giờ Server đã đồng bộ (NTP Atomic Sync):
        - Mirror: giờ chẵn :10-:15 (00,02,...,22)
        - Moss: 00:15, 06:15, 12:15, 18:15 (mỗi đợt 5 phút)
        """
        from datetime import datetime, timedelta
        try:
            from services.time_sync_service import get_time_sync
            time_sync = get_time_sync()
        except Exception:
            time_sync = None

        while self.running:
            try:
                if time_sync:
                    sched = time_sync.get_mirror_event_schedule()
                    now = sched["server_now"]
                    self.state_mgr.update_event_state(
                        "mirror",
                        countdown_sec=sched["countdown_sec"],
                        countdown_str=sched["countdown_str"],
                        is_gate_open=sched["is_gate_open"],
                        next_time_str=sched["next_time_str"],
                        status_text=sched["status_text"],
                        ntp_offset_sec=sched["ntp_offset_sec"],
                        game_rtt_ms=sched["game_rtt_ms"],
                    )
                else:
                    now = datetime.now()
                    valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]

                    # ---- Mirror ----
                    is_gate_open = (now.hour in valid_hours and 10 <= now.minute < 15)
                    next_gate = None
                    for h in valid_hours:
                        cand = now.replace(hour=h, minute=10, second=0, microsecond=0)
                        if cand > now:
                            next_gate = cand
                            break
                    if next_gate is None:
                        tomorrow = now + timedelta(days=1)
                        next_gate = tomorrow.replace(hour=0, minute=10, second=0, microsecond=0)

                    if is_gate_open:
                        end_open = now.replace(minute=15, second=0, microsecond=0)
                        rem_sec = max(0, int((end_open - now).total_seconds()))
                        next_str = f"{now.hour:02d}:10 - {now.hour:02d}:15"
                        status = "CỔNG ĐANG MỞ!"
                    else:
                        rem_sec = max(0, int((next_gate - now).total_seconds()))
                        next_str = next_gate.strftime("%H:%M")
                        status = f"Mở sau: {rem_sec // 3600:02d}:{(rem_sec % 3600) // 60:02d}:{rem_sec % 60:02d}"

                    cd_str = f"{rem_sec // 3600:02d}:{(rem_sec % 3600) // 60:02d}:{rem_sec % 60:02d}"
                    self.state_mgr.update_event_state(
                        "mirror",
                        countdown_sec=rem_sec,
                        countdown_str=cd_str,
                        is_gate_open=is_gate_open,
                        next_time_str=next_str,
                        status_text=status,
                    )

                # ---- Moss (Dùng srv_now để chuẩn xác 100%) ----
                moss_slots = [(0, 15), (6, 15), (12, 15), (18, 15)]
                MOSS_DURATION = 300
                active = None
                for h, m in moss_slots:
                    for day_offset in (0, -1):
                        st = (now + timedelta(days=day_offset)).replace(hour=h, minute=m, second=0, microsecond=0)
                        en = st + timedelta(seconds=MOSS_DURATION)
                        if st <= now < en:
                            active = (st, en)
                            break
                    if active:
                        break

                if active:
                    st, en = active
                    moss_rem = max(0, int((en - now).total_seconds()))
                    moss_open = True
                    next_str = f"{st.strftime('%H:%M')} - {en.strftime('%H:%M')}"
                    status = f"MOSS ĐANG MỞ · còn {moss_rem // 60:02d}:{moss_rem % 60:02d}"
                else:
                    next_start = None
                    for h, m in moss_slots:
                        cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
                        if cand + timedelta(seconds=MOSS_DURATION) <= now:
                            cand += timedelta(days=1)
                        if next_start is None or cand < next_start:
                            next_start = cand
                    moss_rem = max(0, int((next_start - now).total_seconds()))
                    moss_open = False
                    next_str = next_start.strftime("%H:%M")
                    status = f"Mở sau: {moss_rem // 3600:02d}:{(moss_rem % 3600) // 60:02d}:{moss_rem % 60:02d}"

                moss_cd = f"{moss_rem // 3600:02d}:{(moss_rem % 3600) // 60:02d}:{moss_rem % 60:02d}"
                self.state_mgr.update_event_state(
                    "moss",
                    countdown_sec=moss_rem,
                    countdown_str=moss_cd,
                    is_open=moss_open,
                    next_time_str=next_str,
                    status_text=status,
                )

            except Exception:
                pass

            time.sleep(1.0)

