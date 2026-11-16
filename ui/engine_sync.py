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

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

def enumerate_megamu_processes() -> Dict[int, str]:
    """Tìm tất cả tiến trình MEGAMU.exe và lấy tiêu đề cửa sổ / tên nhân vật trên Windows."""
    pids = set()
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['name'] and p.info['name'].lower() == 'megamu.exe':
                pids.add(p.info['pid'])
        except Exception:
            pass

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
    # LUỒNG 1: QUÉT TIẾN TRÌNH & THU THẬP THÔNG TIN TIÊU ĐỀ
    # --------------------------------------------------------------------------
    def _game_scan_loop(self):
        while self.running:
            try:
                games = enumerate_megamu_processes()
                enhanced_games = {}
                for pid, raw_title in games.items():
                    # Trích xuất tên nhân vật và server ngầm
                    name = ""
                    server_tag = ""
                    if "[" in raw_title and "]" in raw_title:
                        try:
                            name = raw_title.split("[")[1].split("]")[0].strip()
                        except Exception:
                            pass
                    if not name and ProcessMemoryReader:
                        try:
                            name = ProcessMemoryReader.read_character_name(pid) or ""
                        except Exception:
                            pass

                    # Server code
                    if "Sub" in raw_title or "Sv" in raw_title:
                        for part in raw_title.split():
                            if part.startswith("Sub") or part.startswith("Sv"):
                                server_tag = f" [{part}]"
                                break
                    elif ProcessMemoryReader and hasattr(ProcessMemoryReader, "read_character_server"):
                        try:
                            srv_code = ProcessMemoryReader.read_character_server(pid)
                            if srv_code:
                                server_tag = f" [Sv{srv_code}]"
                        except Exception:
                            pass

                    disp_title = f"{name}{server_tag} (PID {pid})" if name else (raw_title or f"MEGAMU ({pid})")
                    enhanced_games[pid] = disp_title

                self.state_mgr.update_detected_games(enhanced_games)
            except Exception as e:
                pass

            # Ngủ 4.0s hoặc thức dậy ngay nếu có sự kiện quét thủ công
            self._scan_trigger_event.wait(timeout=4.0)
            self._scan_trigger_event.clear()

    # --------------------------------------------------------------------------
    # LUỒNG 2: ĐỌC TELEMETRY 10 SLOT (CHỐNG NGHẼN GUI 100%)
    # --------------------------------------------------------------------------
    def _telemetry_loop(self):
        import gc
        last_gc = time.time()

        while self.running:
            try:
                controllers = self.controllers_provider() or []
                for ctrl in controllers:
                    pid = getattr(ctrl, "assigned_pid", None)
                    s_idx = getattr(ctrl, "slot_idx", 0)
                    if not pid or s_idx <= 0:
                        continue

                    # Kiểm tra PID còn sống không
                    if not psutil.pid_exists(pid):
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
                            p_info = {
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
                    gc.collect()
                except Exception:
                    pass

            time.sleep(0.3)

    # --------------------------------------------------------------------------
    # LUỒNG 3: TÍNH TOÁN SỰ KIỆN DOUBLE GOER (MIRROR) & MOSS ĐẾM NGƯỢC
    # --------------------------------------------------------------------------
    def _events_loop(self):
        """Đếm ngược Mirror/Moss đúng lịch meg_gui:
        - Mirror: giờ chẵn :10-:15 (00,02,...,22)
        - Moss: 00:15, 06:15, 12:15, 18:15 (mỗi đợt 5 phút)
        """
        from datetime import datetime, timedelta

        while self.running:
            try:
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

                # ---- Moss ----
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

