import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - v1.5.7
====================================
Giao diện hoàn chỉnh và thuật toán chuẩn 100% khớp MEGAMU Auto Train Dashboard gốc:
- Giao diện 3 tab: 10 Tài khoản | Cấu hình | Nhật ký
- Lưu & đọc toàn bộ cấu hình TRỰC TIẾP từ file JSON (Zero RAM-loss):
  + autotrain_profiles.json (Cấu hình các chặng min/max, map, x, y, delay của Config 1..10)
  + autotrain_megamu_config.json (Config mặc định đồng bộ Config 1)
  + slot_assignments.json (Lưu cấu hình gán từng dòng 01..10)
  + ui_settings.json (Ngôn ngữ VI/EN/PT-BR)
- Kết nối native không chiếm chuột, không click tọa độ (Zero-Mouse Direct Engine).
- Tự động quét tiến trình MEGAMU.exe, tự gán PID, gán Team 5, kết nối và bật/tắt Auto hàng loạt.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
import math
import heapq
import ctypes
import threading
from typing import Optional, List, Dict, Tuple, Any, Callable
from pathlib import Path

# Đảm bảo nhận diện môi trường binary khi biên dịch bằng Nuitka hoặc PyInstaller
if "__compiled__" in globals():
    sys.frozen = True

# Đảm bảo UTF-8 và High-Resolution Timer (1.0ms) trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

import customtkinter as ctk
from core.logger import get_logger, AsyncRingBufferLogger
from core.system_mutex import SingleInstanceMutex
from services import (
    TrainService,
    DevilService,
    MossService,
    MirrorService,
    MemoryService,
)
from ui import MossView, MirrorView, AccountsView, ProfilesView, LogsView, RamView, AutoLoginView
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
import psutil
import webbrowser

try:
    from test_entity_radar import MemoryScanner
except ImportError:
    MemoryScanner = None

# Core Engines
try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None

try:
    from meg_auto_worker import AutoTrainWorker, MapResolver
except ImportError:
    AutoTrainWorker = None
    MapResolver = None

try:
    import license_client
except ImportError:
    license_client = None

try:
    import updater
except ImportError:
    updater = None

try:
    import meg_ram_optimizer
    from meg_ram_optimizer import RamOptimizerManager, trim_single_process, get_megamu_processes, optimize_all_megamu
except ImportError:
    meg_ram_optimizer = None
    RamOptimizerManager = None
    trim_single_process = None
    get_megamu_processes = None
    optimize_all_megamu = None

try:
    from meg_account_manager import AccountManager, find_megamu_exe_path
except ImportError:
    AccountManager = None
    find_megamu_exe_path = None


# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN TỆP
# ==============================================================================
APP_NAME = "MEGAMU Auto Train Dashboard"
APP_VERSION = "v1.5.7"
DEFAULT_SLOTS = 5
MAX_SLOTS = 50
CURRENT_LICENSE = "Dùng thử"

def app_dir() -> Path:
    # 1. Nuitka compiled binary: __compiled__.containing_dir trỏ chính xác vào thư mục chứa file .exe gốc
    try:
        compiled_info = globals().get("__compiled__") or getattr(sys.modules.get("__main__"), "__compiled__", None)
        if compiled_info and hasattr(compiled_info, "containing_dir") and compiled_info.containing_dir:
            c_dir = Path(compiled_info.containing_dir).resolve()
            if c_dir.is_dir():
                return c_dir
    except Exception:
        pass
    # 2. Nuitka onefile đặt đường dẫn thư mục chứa file .exe gốc tại NUITKA_ONEFILE_DIRECTORY
    onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
    if onefile_dir and Path(onefile_dir).is_dir():
        return Path(onefile_dir).resolve()
    # 3. Hoặc lấy qua sys.argv[0] nếu không nằm trong thư mục Temp
    if sys.argv and sys.argv[0]:
        try:
            cand = Path(sys.argv[0]).resolve().parent
            if cand.is_dir() and "temp" not in str(cand).lower():
                return cand
        except Exception:
            pass
    # 4. Fallback
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        cand = Path(sys.executable).resolve().parent
        if "temp" not in str(cand).lower():
            return cand
    return Path(__file__).resolve().parent

def resource_path(name: str) -> Path:
    # 1. Thư mục thật của app (nơi đặt file .exe)
    p = BASE_DIR / name
    if p.exists():
        return p
    # 2. Thư mục giải nén tạm của Nuitka Onefile
    p = Path(sys.executable).resolve().parent / name
    if p.exists():
        return p
    # 3. Pyinstaller _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / name
        if p.exists():
            return p
    return Path(__file__).resolve().parent / name

BASE_DIR = app_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
AUTO_STOP_LOG_FILE = BASE_DIR / "auto_stop_events.log"

try:
    from meg_crash_tracer import (
        log_crash_trace,
        log_thread_exception,
        install_global_exception_hooks,
        register_ui_exception_callback,
        traced_thread_scope,
        traced_thread
    )
except ImportError:
    def log_crash_trace(*args, **kwargs): pass

def record_auto_stop_log(
    slot_idx: int,
    pid: Optional[int],
    char_name: str,
    trigger_type: str,
    reason: str,
    coords: str = "--,--",
    level: str = "---"
):
    """
    Ghi nhật ký chi tiết mỗi khi một tài khoản Auto dừng lại (Persistent Audit Trace Log).
    Phân loại rõ ràng:
    - MANUAL: Do con người (người dùng) chủ động bấm dừng / thao tác giao diện.
    - SYSTEM: Do hệ thống / game tự ngắt (crash, mất PID, mất bản quyền, lỗi chặng...).
    Đồng bộ vào auto_stop_events.log và auto_crash_trace.log để truy vết sự cố 24/7.
    """
    try:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        tag = trigger_type.upper()
        line = (
            f"[{now_str}] [{tag:<6}] [Slot {slot_idx:02d}] "
            f"[PID: {pid if pid else 'N/A'}] [Nhân vật: {char_name or 'N/A'}] [Cấp: {level}] [Tọa độ: {coords}] "
            f"-> Lý do: {reason}\n"
        )
        with open(AUTO_STOP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        
        log_crash_trace(
            source="DASHBOARD_AUDIT",
            event=tag,
            details=f"Slot {slot_idx:02d} | Reason: {reason} | Coords: {coords} | Level: {level}",
            pid=pid,
            char_name=char_name,
            level="WARN" if tag == "SYSTEM" else "INFO"
        )
    except Exception:
        pass

def extract_bundled_resources():
    """Tự động trích xuất các tài nguyên nhúng (C++ DLL, config mẫu, icons) nếu chưa có bên ngoài."""
    bundle_candidates = [
        Path(sys.executable).resolve().parent,
        Path(__file__).resolve().parent,
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundle_candidates.insert(0, Path(meipass))

    base_bundle = None
    for cand in bundle_candidates:
        if cand and cand.is_dir() and (cand / "meg_license_bridge.dll").exists():
            base_bundle = cand
            break
    if not base_bundle:
        for cand in bundle_candidates:
            if cand and cand.is_dir():
                base_bundle = cand
                break
    if not base_bundle:
        return

    # 1. Trích xuất meg_license_bridge.dll ra thư mục chạy thật nếu chưa có
    target_dll = BASE_DIR / "meg_license_bridge.dll"
    if not target_dll.exists():
        try:
            import _embedded_bridge
            _embedded_bridge.extract_to(target_dll)
        except Exception:
            pass
    if base_bundle:
        source_dll = base_bundle / "meg_license_bridge.dll"
        if not target_dll.exists() and source_dll.exists():
            try:
                import shutil
                shutil.copy2(str(source_dll), str(target_dll))
            except Exception:
                pass

    # 2. Trích xuất icon, logo và map commands
    for asset in ["megamu_dashboard_icon.ico", "megamu_dashboard_logo.png", "map_commands.json"]:
        t_asset = BASE_DIR / asset
        s_asset = base_bundle / asset
        if not t_asset.exists() and s_asset.exists():
            try:
                import shutil
                shutil.copy2(str(s_asset), str(t_asset))
            except Exception:
                pass

    # 3. Trích xuất các config mẫu nếu chưa có
    for cfg in [
        "autotrain_profiles.json", "autotrain_megamu_config.json",
        "slot_assignments.json", "ui_settings.json",
        "moss_slots_config.json", "mirror_schedule_config.json",
        "event_slots_config.json",
        "maps.ini", "map_commands.json", "license_settings.json"
    ]:
        t_cfg = CONFIG_DIR / cfg
        s_cfg = base_bundle / "config" / cfg
        if not s_cfg.exists():
            s_cfg = base_bundle / cfg
        if not t_cfg.exists() and s_cfg.exists():
            try:
                import shutil
                shutil.copy2(str(s_cfg), str(t_cfg))
            except Exception:
                pass

try:
    extract_bundled_resources()
except Exception:
    pass

LOGO_FILE = resource_path("megamu_dashboard_logo.png")
ICON_FILE = resource_path("megamu_dashboard_icon.ico")

PROFILE_FILE = CONFIG_DIR / "autotrain_profiles.json"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "autotrain_megamu_config.json"
SLOT_ASSIGNMENTS_FILE = CONFIG_DIR / "slot_assignments.json"
UI_SETTINGS_FILE = CONFIG_DIR / "ui_settings.json"
MAP_COMMANDS_FILE = CONFIG_DIR / "map_commands.json"
MOSS_CONFIG_FILE = CONFIG_DIR / "moss_slots_config.json"
MIRROR_CONFIG_FILE = CONFIG_DIR / "mirror_schedule_config.json"
EVENT_CONFIG_FILE = CONFIG_DIR / "event_slots_config.json"
CLASS_STAT_PROFILES_FILE = CONFIG_DIR / "class_stat_profiles.json"

CLASS_ID_TO_CODE = {
    0: "DW", 1: "DK", 2: "FE", 3: "MG", 4: "DL", 5: "SU", 6: "RF", 7: "GL",
    8: "RW", 9: "SL", 10: "GC", 11: "KM", 12: "LM", 13: "IK", 14: "AL", 15: "CR"
}
CLASS_CODE_TO_NAME = {
    "DW": "Dark Wizard (Phù Thủy)",
    "DK": "Dark Knight (Chiến Binh)",
    "FE": "Fairy Elf (Tiên Nữ)",
    "MG": "Magic Gladiator (Đấu Sĩ)",
    "DL": "Dark Lord (Chúa Tể)",
    "SU": "Summoner (Thuật Sĩ)",
    "RF": "Rage Fighter (Thiết Binh)",
    "GL": "Grow Lancer (Thương Thủ)",
    "RW": "Rune Wizard (Phù Thủy Rune)",
    "SL": "Slayer (Sát Thủ)",
    "GC": "Gun Crusher (Pháo Thủ)",
    "KM": "Kundun Mephis",
    "LM": "Lemuria",
    "IK": "Illusion Knight (Huyễn Ảnh)",
    "AL": "Alchemist (Giả Kim)",
    "CR": "Crusher"
}

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]
 
# ==============================================================================
# UI COMPONENTS (HIGH-DPI ICONS, MODERN OPTION MENU, TOOLTIPS)
# ==============================================================================
from ui.components import (
    UiIconFactory,
    ModernOptionMenu,
    ModernToolTip,
    add_tooltip
)

# ==============================================================================
# BẢNG DỊCH NGÔN NGỮ (I18N)
# ==============================================================================
from core.i18n import (
    I18N,
    CURRENT_LANG,
    load_language_preference,
    save_language_preference,
    tr,
)

try:
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

from core.process_utils import (
    character_name_from_window_title,
    enumerate_megamu_processes,
    is_megamu_process_alive,
    record_auto_stop_log,
)

# ==============================================================================
# QUẢN LÝ CẤU HÌNH TRỰC TIẾP TỪ FILE (ZERO-RAM LOSS PERSISTENCE)
# ==============================================================================
from core.storage import ConfigPersistenceManager

# ==============================================================================
# CONTROLLER QUẢN LÝ TỪNG DÒNG TÀI KHOẢN (SLOT CONTROLLER)
# ==============================================================================
from core.slot_controller import SlotController

class DashboardApp(ctk.CTk):

    def report_callback_exception(self, exc, val, tb):
        """Bẫy lỗi callback Tkinter an toàn - Không bao giờ crash console do Unicode cp1252."""
        import traceback
        err_msg = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open("gui_crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception in Tkinter callback:\n{err_msg}\n")
        except Exception:
            pass
        try:
            from core.crash_tracer import log_crash_trace
            log_crash_trace(
                source="TkinterCallback",
                event="EXCEPTION",
                details=f"Tkinter callback error: {val}\n{err_msg}",
                level="ERROR"
            )
        except Exception:
            pass
        try:
            sys.stderr.write(f"Exception in Tkinter callback:\n{err_msg}\n")
            sys.stderr.flush()
        except Exception:
            try:
                sys.stderr.buffer.write(f"Exception in Tkinter callback:\n{err_msg}\n".encode("utf-8", "replace"))
            except Exception:
                pass

    def __init__(self):
        super().__init__()

        # Kích hoạt bẫy ngoại lệ toàn diện 3 lớp cho mọi luồng và liên kết hiển thị log UI
        try:
            install_global_exception_hooks(ui_callback=self.log_message)
        except Exception:
            pass

        # Khởi tạo ngôn ngữ từ tệp ui_settings.json
        load_language_preference()

        # Cấu hình cửa sổ (Thiết kế nhỏ gọn, tinh tế)
        self.title(APP_NAME)
        self.geometry("960x540")
        self.minsize(800, 460)
        self.configure(fg_color="#0e1117")

        # Thiết lập chủ đề Classic Base phẳng tối giản (Flat Minimalist) để loại bỏ mọi animation/canvas bo góc nặng nề
        for w_type in ("CTkFrame", "CTkButton", "CTkEntry", "CTkScrollableFrame", "CTkProgressBar", "CTkCheckBox"):
            if w_type in ctk.ThemeManager.theme and "corner_radius" in ctk.ThemeManager.theme[w_type]:
                ctk.ThemeManager.theme[w_type]["corner_radius"] = 0

        # Debounce co giãn cửa sổ / Zoom in / Zoom out để tránh tính toán dồn dập
        self._resize_timer = None
        self._is_resizing = False
        self.bind("<Configure>", self._on_window_configure)

        # Đặt App ID cho Windows để hiển thị icon DAuto trên Taskbar thay vì icon Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dauto.megamu.dashboard.v1")
        except Exception:
            pass

        # Đặt Icon cho cửa sổ và Taskbar
        self._apply_window_icon()
        self.after(100, self._apply_window_icon)
        self.after(300, self._apply_window_icon)
        self.after(600, self._apply_window_icon)

        # Quản lý danh sách Map
        self.map_resolver = MapResolver.get_instance() if MapResolver else None
        self.map_list = self._get_map_display_list()

        # Quản lý Slot và đọc trực tiếp cấu hình gán từ file JSON
        self.slot_assignments = ConfigPersistenceManager.load_slot_assignments(DEFAULT_SLOTS)
        moss_cfgs = ConfigPersistenceManager.load_moss_configs()
        moss_sched_cfg = ConfigPersistenceManager.load_moss_schedule_config()
        mirror_sched_cfg = ConfigPersistenceManager.load_mirror_schedule_config()
        moss_sel = moss_sched_cfg.get("selected_slots", None)
        mirror_sel = mirror_sched_cfg.get("selected_slots", None)

        self.controllers: List[SlotController] = []
        for i in sorted(self.slot_assignments.keys()):
            assigned_c = self.slot_assignments.get(i, 1 if i <= 5 else 2)
            ctrl = SlotController(i, self, default_profile=assigned_c)
            c_data = moss_cfgs.get(i, {})
            ctrl.moss_category = int(c_data.get("category", 0))
            ctrl.moss_delay_ms = int(c_data.get("delay_ms", 1000))
            ctrl.moss_max_rolls = int(c_data.get("max_rolls", 0))
            ctrl.moss_auto_clean = bool(c_data.get("auto_clean", True))
            ctrl.mirror_enabled = (i in mirror_sel) if (mirror_sel is not None) else True
            ctrl.moss_enabled = (i in moss_sel) if (moss_sel is not None) else True
            self.controllers.append(ctrl)

        # Bộ nhớ tiến trình
        self.detected_games: Dict[int, str] = {}
        self._char_name_cache: Dict[int, str] = {}
        self.active_tab = None
        self.logger = get_logger()
        self.logs_data: List[Tuple[str, str, str]] = [] # [(time, slot, text)]
        self._render_logs_scheduled = False

        # Quản lý RAM Optimizer
        self.ram_manager = RamOptimizerManager.get_instance() if RamOptimizerManager else None
        if self.ram_manager:
            self.ram_manager.register_callback(self._on_ram_manager_event)
            if self.ram_manager.auto_trim_enabled:
                self.ram_manager.start_worker()
        self.ram_client_rows: Dict[int, Dict[str, Any]] = {}
        self.ram_empty_label = None

        # Thành phần UI lưu trữ
        self.slot_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.moss_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.mirror_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.editor_rows: List[Dict[str, Any]] = []

        # Quản lý Account & AutoLogin
        self.account_mgr = AccountManager() if AccountManager else None
        self.autologin_ui_rows: List[Dict[str, Any]] = []
        self.autologin_delay_var = ctk.StringVar(value="3.0")

        # Smooth UI Overhaul & Dirty-Checking Cache (Zero-Canvas-Redraw)
        self._slot_telemetry_cache: Dict[int, Dict[str, Any]] = {}
        self._moss_ui_cache: Dict[int, Dict[str, Any]] = {}
        self._mirror_ui_cache: Dict[int, Dict[str, Any]] = {}
        self._last_master_running_state: Optional[bool] = None
        self._last_header_stats_state: Optional[tuple] = None
        self._logs_dirty: bool = False

        # Static Font & Icon Pooling (Zero GDI Leak & Instant Button Toggle)
        self.font_segoe_11_bold = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.font_segoe_11_normal = ctk.CTkFont(family="Segoe UI", size=11)
        self.font_segoe_9_bold = ctk.CTkFont(family="Segoe UI", size=9, weight="bold")
        self.font_segoe_9_normal = ctk.CTkFont(family="Segoe UI", size=9)
        self.font_segoe_12_bold = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")

        self._icon_play_12 = UiIconFactory.get("play", color="#38bdf8", size=(12, 12))
        self._icon_stop_12 = UiIconFactory.get("stop", color="#ffffff", size=(12, 12))
        self._icon_play_16 = UiIconFactory.get("play", color="#6ee7b7", size=(16, 16))
        self._icon_stop_16 = UiIconFactory.get("stop", color="#ffffff", size=(16, 16))

        # Xây dựng giao diện hoàn chỉnh
        self.build_ui()
        self.update_modules_visibility()
        initial_tab = "accounts"
        if license_client:
            if license_client.has_license_module("train"):
                initial_tab = "accounts"
            elif license_client.has_license_module("moss"):
                initial_tab = "moss"
            elif license_client.has_license_module("mirror"):
                initial_tab = "mirror"
            else:
                initial_tab = "logs"
        self.switch_tab(initial_tab)
        self.update_header_stats()
        self.log_message(f"Khởi động thành công {APP_NAME} {APP_VERSION} - Hệ thống sẵn sàng!", "INFO")
        self.log_message(f"Đã nạp {len(self.controllers)} tài khoản/slots hoạt động mặc định.", "INFO")

        # Trạng thái cập nhật bắt buộc (Mandatory Auto Update)
        self.is_update_mandatory: bool = False
        self.update_info: Optional[Dict[str, Any]] = None
        self._update_dlg_instance = None
        self._last_update_check_time = time.time()

        # Bắt đầu vòng lặp quét tiến trình & telemetry & bản quyền
        self.running = True

        # Kiểm tra Win32 Named Mutex chống chạy đè 2 bản Dashboard
        self._app_mutex = SingleInstanceMutex()
        if not self._app_mutex.acquire():
            print("⚠️ CẢNH BÁO: Một phiên bản khác của MEGAMU Auto Train Dashboard đang hoạt động!")
            SingleInstanceMutex.activate_existing_window(APP_NAME)

        self._last_moss_trigger_key = None
        self._last_moss_move_key = None
        self._last_mirror_trigger_key = None
        self._last_mirror_prep_key = None
        self._last_mirror_stop_key = None
        self.after(500, self._periodic_game_scan)
        self._start_telemetry_loop()
        self.after(1000, self._periodic_license_monitor)
        self.after(1000, self._periodic_moss_scheduler)
        self.after(1000, self._periodic_mirror_scheduler)
        self.after(1200, self._check_initial_license)
        threading.Thread(target=self._verify_license_async, daemon=True).start()
        threading.Thread(target=self._check_update_async, kwargs={"manual": False}, daemon=True).start()

        # Xử lý đóng ứng dụng an toàn
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_map_display_list(self) -> List[str]:
        if self.map_resolver:
            try:
                if hasattr(self.map_resolver, "get_all_map_names"):
                    resolved_maps = self.map_resolver.get_all_map_names()
                elif hasattr(self.map_resolver, "display_names"):
                    resolved_maps = list(self.map_resolver.display_names)
                else:
                    resolved_maps = []
                if resolved_maps:
                    return resolved_maps
            except Exception:
                pass
        maps = []
        candidate_paths = [
            MAP_COMMANDS_FILE,
            BASE_DIR / "config" / "map_commands.json",
            BASE_DIR / "map_commands.json",
            Path(r"C:\Users\donpv\Downloads\MEGAMU Auto Train Dashboad\config\map_commands.json")
        ]
        for p in candidate_paths:
            if p and p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    for m in d.get("maps", []):
                        name = str(m.get("name", "")).strip()
                        if name and name not in maps:
                            maps.append(name)
                    if maps:
                        break
                except Exception:
                    pass
        if not maps:
            maps = ["Lorencia", "Noria", "Devias", "Dungeon 2", "Lost Tower 5", "Aida 1", "Icarus", "Kanturu 1"]
        return maps

    def build_ui(self):
        """Dựng giao diện đồng bộ 100% với ảnh thiết kế."""
        ctk.set_appearance_mode("Dark")

        # ----------------------------------------------------------------------
        # 1. UNIFIED SLEEK TOP BAR (Logo + Compact Tabs + Quick Tools in ONE 38px row)
        # ----------------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, fg_color="#10141e", height=38, corner_radius=0)
        self.header_frame.pack(side="top", fill="x", padx=0, pady=0)
        self.header_frame.pack_propagate(False)

        top_inner = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        top_inner.pack(fill="both", expand=True, padx=10, pady=0)

        # 1.1 Trái: Logo mini + Tên ứng dụng + Phiên bản
        left_box = ctk.CTkFrame(top_inner, fg_color="transparent")
        left_box.pack(side="left", fill="y")

        if LOGO_FILE.exists():
            try:
                logo_img = Image.open(str(LOGO_FILE))
                lw, lh = logo_img.size
                aspect = lw / max(1, lh)
                target_h = 22
                target_w = int(target_h * aspect)
                self.logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(target_w, target_h))
                logo_label = ctk.CTkLabel(left_box, image=self.logo_ctk, text="")
                logo_label.pack(side="left", padx=(0, 6))
            except Exception:
                pass

        title_lbl = ctk.CTkLabel(
            left_box,
            text=APP_NAME,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.pack(side="left")

        ver_lbl = ctk.CTkLabel(
            left_box,
            text=f" {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        )
        ver_lbl.pack(side="left", padx=(3, 8))

        # Phân cách mỏng
        ctk.CTkFrame(left_box, fg_color="#1e293b", width=1, height=18).pack(side="left", padx=(2, 8))

        # 1.2 Giữa: Dãy Tab Navigation phẳng nhỏ gọn (Pill style, height=28)
        tab_box = ctk.CTkFrame(top_inner, fg_color="transparent")
        tab_box.pack(side="left", fill="y")

        tab_style = {
            "height": 28,
            "corner_radius": 4,
            "hover": False,
            "font": ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        }

        self.tab_accounts_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("user", color="#2dd4bf", size=(13, 13)),
            compound="left",
            text=f" {tr('characters')} ({len(self.controllers)})",
            command=lambda: self.switch_tab("accounts"),
            **tab_style
        )
        self.tab_accounts_btn.pack(side="left", padx=2)

        self.tab_profiles_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("gear", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=f" {tr('configuration')}",
            command=self.open_profiles_modal,
            **tab_style
        )
        # Tab Profiles hiển thị dạng icon gọn gàng ở góc trên bên phải

        self.tab_moss_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("dice", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=f" {tr('moss_merchant')}",
            command=lambda: self.switch_tab("moss"),
            **tab_style
        )
        self.tab_moss_btn.pack(side="left", padx=2)

        self.tab_mirror_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("mirror", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=f" {tr('mirror_event')}",
            command=lambda: self.switch_tab("mirror"),
            **tab_style
        )
        self.tab_mirror_btn.pack(side="left", padx=2)

        self.tab_logs_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("file", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=f" {tr('logs')}",
            command=self.open_logs_window,
            **tab_style
        )
        # Tab Logs hiển thị dạng icon gọn gàng ở góc trên bên phải

        self.tab_ram_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("bolt", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=f" {tr('ram_optimizer')}",
            command=lambda: self.switch_tab("ram"),
            **tab_style
        )

        self.tab_autologin_btn = ctk.CTkButton(
            tab_box,
            image=UiIconFactory.get("key", color="#94a3b8", size=(13, 13)),
            compound="left",
            text=" AutoLogin",
            command=lambda: self.switch_tab("autologin"),
            **tab_style
        )

        # 1.3 Phải: Quick Action Tools (Modal Cấu hình, Modal Nhật ký, Lang, Update, License, Help)
        right_box = ctk.CTkFrame(top_inner, fg_color="transparent")
        right_box.pack(side="right", fill="y")

        # Container chứa toàn bộ công cụ góc phải bố trí từ trái sang phải
        right_tools = ctk.CTkFrame(right_box, fg_color="transparent")
        right_tools.pack(side="right", fill="y")

        # 1. Icon Cấu hình Chặng (Icon-only Minimalist như cũ)
        self.btn_header_profiles = ctk.CTkButton(
            right_tools,
            image=UiIconFactory.get("gear", color="#cbd5e1", size=(14, 14)),
            text="",
            width=28,
            height=26,
            corner_radius=4,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#334155",
            command=self.open_profiles_modal
        )
        self.btn_header_profiles.pack(side="left", padx=(2, 2))
        add_tooltip(self.btn_header_profiles, "⚙️ Cấu hình bãi quái & tuyến đường (Profiles Modal)")

        # 2. Icon Nhật ký Hoạt động (Icon-only Minimalist như cũ)
        self.btn_header_logs = ctk.CTkButton(
            right_tools,
            image=UiIconFactory.get("file", color="#38bdf8", size=(14, 14)),
            text="",
            width=28,
            height=26,
            corner_radius=4,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#0369a1",
            command=self.open_logs_window
        )
        self.btn_header_logs.pack(side="left", padx=(2, 4))
        add_tooltip(self.btn_header_logs, "📋 Nhật ký hoạt động chuyên dụng (Logs Modal)")

        # Vách ngăn mỏng phân cách giữa nhóm Action Modals và công cụ hệ thống
        ctk.CTkFrame(right_tools, fg_color="#1e293b", width=1, height=18).pack(side="left", padx=(2, 4))

        self.lang_var = ctk.StringVar(value=f"{CURRENT_LANG.upper()}")
        self.lang_menu = ModernOptionMenu(
            right_tools,
            values=["VI", "EN", "PT-BR"],
            variable=self.lang_var,
            width=65,
            height=26,
            fg_color="#181c26",
            hover_color="#222736",
            command=self.change_language,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")
        )
        self.lang_menu.pack(side="left", padx=2)

        self.btn_text_cfg = ctk.CTkButton(
            right_tools,
            text="⚙ File",
            width=48,
            height=26,
            corner_radius=4,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2c3345",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.open_text_config
        )
        self.btn_text_cfg.pack(side="left", padx=2)
        add_tooltip(self.btn_text_cfg, "Mở thư mục cấu hình JSON.")



        # ----------------------------------------------------------------------
        # 2. FOOTER STATUS BAR (Permanently Fixed Bottom, 24px)
        # Bắt buộc pack(side="bottom") TRƯỚC content_container để cố định vĩnh viễn ở đáy cửa sổ
        # Triệt tiêu hoàn toàn hiện tượng bị bảng tài khoản đẩy mất / co mất footer khi thu nhỏ cửa sổ.
        # ----------------------------------------------------------------------
        self.footer_frame = ctk.CTkFrame(self, fg_color="#0a0d14", height=24, corner_radius=0)
        self.footer_frame.pack(side="bottom", fill="x", padx=0, pady=0)
        self.footer_frame.pack_propagate(False)

        footer_inner = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        footer_inner.pack(fill="both", expand=True, padx=12, pady=0)

        self.header_stats_lbl = ctk.CTkLabel(
            footer_inner,
            text=f"Game: 0 | Đã kết nối: 0/0 | Auto: 0 | Bản quyền: {CURRENT_LICENSE}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b",
            cursor="hand2"
        )
        self.header_stats_lbl.pack(side="left")
        self.header_stats_lbl.bind("<Button-1>", lambda e: self.open_license_dialog())

        # Khung công cụ tiện ích bên phải Footer (Version + Update + License + Help)
        footer_right = ctk.CTkFrame(footer_inner, fg_color="transparent")
        footer_right.pack(side="right", fill="y")

        self.btn_help = ctk.CTkButton(
            footer_right,
            text="?",
            width=18,
            height=18,
            corner_radius=3,
            fg_color="#141822",
            hover_color="#1e2638",
            border_width=1,
            border_color="#2c3345",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#94a3b8",
            command=self.show_help
        )
        self.btn_help.pack(side="right", padx=(2, 0), pady=3)

        self.btn_license = ctk.CTkButton(
            footer_right,
            text="",
            image=UiIconFactory.get("key", color="#f59e0b", size=(12, 12)),
            width=22,
            height=18,
            corner_radius=3,
            fg_color="#141822",
            hover_color="#1e2638",
            border_width=1,
            border_color="#d97706",
            command=self.open_license_dialog
        )
        self.btn_license.pack(side="right", padx=2, pady=3)
        add_tooltip(self.btn_license, f"Bản quyền: {CURRENT_LICENSE}\nNhấp để kích hoạt hoặc xem chi tiết.")

        self.btn_update = ctk.CTkButton(
            footer_right,
            text="",
            image=UiIconFactory.get("update", color="#10b981", size=(12, 12)),
            width=22,
            height=18,
            corner_radius=3,
            fg_color="#141822",
            hover_color="#1e2638",
            border_width=1,
            border_color="#059669",
            command=lambda: self.check_for_updates_ui(manual=True)
        )
        self.btn_update.pack(side="right", padx=2, pady=3)
        add_tooltip(self.btn_update, "Kiểm tra bản cập nhật mới.")

        ctk.CTkFrame(footer_right, fg_color="#1e293b", width=1, height=12).pack(side="right", padx=(4, 4), pady=6)

        self.footer_stats_lbl = ctk.CTkLabel(
            footer_right,
            text=f"MEGAMU Auto Pro v{APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#475569"
        )
        self.footer_stats_lbl.pack(side="right", padx=(0, 2))

        # ----------------------------------------------------------------------
        # 3. CONTENT CONTAINER (Pure Dark Base Frame - Triệt tiêu chớp trắng và lag)
        # ----------------------------------------------------------------------
        self.content_container = ctk.CTkFrame(self, fg_color="#0e1117", corner_radius=0, border_width=0)
        self.content_container.pack(side="top", fill="both", expand=True, padx=10, pady=(2, 2))

        # Cấu hình Persistent Grid Stacking cho 0ms Tab Switching
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # 7 Panels cho các Tab (Xếp chồng vĩnh viễn trên cùng ô lưới 0,0)
        self.panel_accounts = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_profiles = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_logs = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_ram = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_moss = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_mirror = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)
        self.panel_autologin = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=0)

        self._tab_panels = {
            "accounts": self.panel_accounts,
            "profiles": self.panel_profiles,
            "logs": self.panel_logs,
            "ram": self.panel_ram,
            "moss": self.panel_moss,
            "mirror": self.panel_mirror,
            "autologin": self.panel_autologin,
        }

        # Grid toàn bộ 7 panels vĩnh viễn ngay từ đầu (Triệt tiêu unmap và relayout cascade)
        for p in self._tab_panels.values():
            p.grid(row=0, column=0, sticky="nsew")

        self._active_panel = None

        # ----------------------------------------------------------------------
        # 4. ACTION TOOLBAR (Tinh gọn chuẩn Icon-Only siêu hiện đại, chống tràn màn hình)
        # ----------------------------------------------------------------------
        self.toolbar_frame = ctk.CTkFrame(self.panel_accounts, fg_color="transparent", height=32)
        self.toolbar_frame.pack(fill="x", padx=8, pady=(4, 2))

        icon_btn_style = {
            "width": 30,
            "height": 26,
            "corner_radius": 4,
            "fg_color": "#181c26",
            "hover_color": "#242b3a",
            "border_width": 1,
            "border_color": "#2c3345",
            "text": ""
        }

        # Nhóm bên trái
        t_left = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        t_left.pack(side="left")

        # 1. Kết nối tất cả (Link Icon)
        self.btn_connect_all = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("link", color="#38bdf8", size=(14, 14)),
            command=self.connect_all,
            **icon_btn_style
        )
        self.btn_connect_all.configure(border_color="#0284c7", hover_color="#0369a1")
        self.btn_connect_all.pack(side="left", padx=(0, 4))
        add_tooltip(
            self.btn_connect_all,
            "🔗 Kết nối tất cả (Connect All)\n"
            "Tự động quét và kết nối tất cả các cửa sổ MEGAMU đang mở vào các Slot còn trống."
        )

        # 2. Gán toàn bộ (Users Icon)
        self.btn_team5 = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("users", color="#38bdf8", size=(14, 14)),
            command=self.assign_all,
            **icon_btn_style
        )
        self.btn_team5.configure(border_color="#0284c7", hover_color="#0369a1")
        self.btn_team5.pack(side="left", padx=(0, 4))
        add_tooltip(
            self.btn_team5,
            "👥 Gán toàn bộ (Assign All)\n"
            "Tự động quét và gán toàn bộ các cửa sổ game MEGAMU đang mở vào các ô Slot trống."
        )

        # 3. Làm mới game (Refresh Icon)
        self.btn_refresh = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(14, 14)),
            command=self.refresh_games,
            **icon_btn_style
        )
        self.btn_refresh.pack(side="left", padx=(0, 4))
        add_tooltip(
            self.btn_refresh,
            "🔄 Làm mới Game (Refresh)\n"
            "Quét lại toàn bộ danh sách tiến trình MEGAMU.exe trên hệ thống để cập nhật danh sách chọn."
        )

        # Phân tách nhóm 1
        ctk.CTkFrame(t_left, fg_color="#242b3a", width=1, height=16).pack(side="left", padx=(2, 6))

        # 4. Thêm Slot (Plus Icon)
        self.btn_add_slot = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("plus", color="#4ade80", size=(14, 14)),
            command=self.add_new_slot,
            **icon_btn_style
        )
        self.btn_add_slot.configure(border_color="#14532d", hover_color="#14532d")
        self.btn_add_slot.pack(side="left", padx=(0, 4))
        add_tooltip(self.btn_add_slot, "➕ Thêm Slot (Add Slot)\nThêm một hàng quản lý tài khoản mới vào bảng.")

        # 5. Bớt Slot (Minus Icon)
        self.btn_remove_slot = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("minus", color="#f87171", size=(14, 14)),
            command=self.remove_last_slot,
            **icon_btn_style
        )
        self.btn_remove_slot.configure(border_color="#7f1d1d", hover_color="#7f1d1d")
        self.btn_remove_slot.pack(side="left", padx=(0, 4))
        add_tooltip(self.btn_remove_slot, "➖ Bớt Slot (Remove Slot)\nXóa bớt một hàng quản lý tài khoản ở cuối bảng.")

        # Phân tách nhóm 2
        ctk.CTkFrame(t_left, fg_color="#242b3a", width=1, height=16).pack(side="left", padx=(2, 6))

        # 6. Cài đặt Devil (Fire Icon)
        self.btn_devil_config = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("fire", color="#f43f5e", size=(14, 14)),
            command=self.open_devil_global_config_dialog,
            **icon_btn_style
        )
        self.btn_devil_config.configure(fg_color="#2a1215", border_color="#be123c", hover_color="#451218")
        self.btn_devil_config.pack(side="left", padx=(0, 4))
        add_tooltip(
            self.btn_devil_config,
            "🔥 Cài đặt Devil Square (DS)\n"
            "Thiết lập mốc Reset bắt đầu đi Devil và loại vé (Vé Thường / Vé Master) cho toàn bộ tài khoản."
        )

        # 7. Gom ngọc (Gem Icon)
        self.btn_stack_jewels = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("gem", color="#c084fc", size=(14, 14)),
            command=self.stack_all_jewels,
            **icon_btn_style
        )
        self.btn_stack_jewels.configure(fg_color="#1e1528", border_color="#7e22ce", hover_color="#3b1d54")
        self.btn_stack_jewels.pack(side="left")
        add_tooltip(
            self.btn_stack_jewels,
            "💎 Gom Ngọc Toàn Bộ (Stack Jewels)\n"
            "Tự động gộp tất cả các viên ngọc lẻ (Bless, Soul, Chaos, Life...) trong thùng đồ của mọi tài khoản thành từng cụm 10/20/30 viên."
        )

        self.btn_trim_ram = ctk.CTkButton(t_left, image=UiIconFactory.get("bolt", color="#facc15", size=(14, 14)), command=self.quick_trim_ram, **icon_btn_style)
        self.btn_quick_autologin = ctk.CTkButton(t_left, image=UiIconFactory.get("key", color="#c084fc", size=(14, 14)), command=lambda: self.switch_tab("autologin"), **icon_btn_style)

        # Nhóm bên phải: Nút Master Chạy/Dừng Tất Cả
        t_right = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        t_right.pack(side="right")

        self.btn_master_run = ctk.CTkButton(
            t_right,
            image=UiIconFactory.get("play", color="#6ee7b7", size=(14, 14)),
            command=self.on_master_auto_toggle,
            **icon_btn_style
        )
        self.btn_master_run.configure(width=34, height=28, fg_color="#064e3b", hover_color="#047857", border_color="#059669")
        self.btn_master_run.pack(side="right")
        add_tooltip(
            self.btn_master_run,
            "▶ Chạy Tất Cả (Start All)\n"
            "Tất cả tài khoản đang dừng. Nhấp vào đây để khởi động Auto cho toàn bộ."
        )

        self.build_accounts_view()
        self.build_profiles_view()
        self.build_logs_view()
        self.build_ram_view()
        self.build_moss_view()
        self.build_mirror_view()
        self.build_autologin_view()



        self.update_combo_slot_options()
        self.switch_tab("accounts")

    # ==========================================================================
    # TAB 1: DANH SÁCH TÀI KHOẢN (ACCOUNTS TAB)
    # ==========================================================================
    def build_accounts_view(self):
        # Header bảng cố định ở trên (Pixel-perfect alignment với các dòng dữ liệu)
        tbl_header = ctk.CTkFrame(self.panel_accounts, fg_color="transparent", height=24)
        tbl_header.pack(fill="x", padx=(4, 2), pady=(2, 2))

        self.col_header_labels = []
        col_defs = [
            ("col_no", 34, "center", (4, 2)),
            ("col_char_pid", 175, "w", (2, 2)),
            ("col_route_preset", 88, "center", (2, 2)),
            ("col_level", 178, "w", (2, 2)),
            ("col_coordinates", 88, "center", (2, 2)),
            ("col_status", 88, "center", (2, 2)),
            ("col_actions", 175, "center", (2, 2))
        ]

        for k, w, anc, px in col_defs:
            lbl = ctk.CTkLabel(
                tbl_header,
                text=tr(k),
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#64748b"
            )
            lbl.pack(side="left", padx=px)
            self.col_header_labels.append(lbl)

        # Divider line
        div = ctk.CTkFrame(self.panel_accounts, fg_color="#1c2230", height=1)
        div.pack(fill="x", padx=4, pady=(0, 2))

        # Khung cuộn chứa danh sách các dòng tài khoản
        self.accounts_scroll_frame = ctk.CTkScrollableFrame(
            self.panel_accounts,
            fg_color="transparent"
        )
        self.accounts_scroll_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        # Tạo từng dòng tài khoản đã cấu hình
        for i in range(1, len(self.controllers) + 1):
            self.create_slot_row(i)

    def create_slot_row(self, i: int):
        """Tạo 1 dòng giao diện cho Slot thứ i theo phong cách Compact Minimalist (Cao 34px)."""
        ctrl = self.controllers[i - 1]
        row_frame = ctk.CTkFrame(
            self.accounts_scroll_frame,
            fg_color="#131722",
            height=34,
            corner_radius=4,
            border_width=1,
            border_color="#1c2230"
        )
        row_frame.pack(fill="x", padx=2, pady=1)
        row_frame.pack_propagate(False)

        # Cột 1: STT dạng Badge bo góc phẳng nhỏ gọn (34px)
        slot_badge = ctk.CTkFrame(
            row_frame,
            fg_color="#182030",
            corner_radius=3,
            width=34,
            height=22
        )
        slot_badge.pack(side="left", padx=(4, 2))
        slot_badge.pack_propagate(False)

        slot_lbl = ctk.CTkLabel(
            slot_badge,
            text=f"{i:02d}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        slot_lbl.pack(expand=True)
        add_tooltip(slot_badge, f"Slot #{i:02d} - Chuột phải vào đây để mở Menu Lệnh Nhanh.")

        # Cột 2: Character/PID Dropdown (175px)
        options = ["--"]
        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            if not char_name:
                char_name = self._char_name_cache.get(pid, "")
            else:
                self._char_name_cache[pid] = char_name
            disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
            options.append(disp)

        init_proc = "--"
        if ctrl.assigned_pid:
            t = self.detected_games.get(ctrl.assigned_pid, "")
            cname = character_name_from_window_title(t) or self._char_name_cache.get(ctrl.assigned_pid, "")
            if not cname and ctrl.char_name and ctrl.char_name != "---":
                cname = ctrl.char_name
            init_proc = f"{cname} ({ctrl.assigned_pid})" if cname else f"MEGAMU ({ctrl.assigned_pid})"

        proc_var = ctk.StringVar(value=init_proc)
        proc_combo = ModernOptionMenu(
            row_frame,
            values=options,
            variable=proc_var,
            width=175,
            height=26,
            fg_color="#161a24",
            border_color="#222838",
            hover_color="#1e2433",
            corner_radius=4,
            command=lambda val, s=i: self.on_slot_pid_selected(s, val),
            on_open=lambda s=i: self.on_proc_combo_opened(s),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        proc_combo.pack(side="left", padx=(2, 2))
        add_tooltip(proc_combo, f"Gán tài khoản MEGAMU cho Slot #{i:02d}.")

        # Cột 3: Route Preset Combo (88px)
        profile_var = ctk.StringVar(value=f"Config {ctrl.profile_index}")
        preset_combo = ModernOptionMenu(
            row_frame,
            values=PROFILE_NAMES,
            variable=profile_var,
            width=88,
            height=24,
            fg_color="#161a24",
            hover_color="#1e2433",
            corner_radius=3,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=lambda val, s=i: self.on_slot_profile_selected(s, val)
        )
        preset_combo.pack(side="left", padx=(2, 2))
        add_tooltip(preset_combo, "Tuyến đường chạy bãi quái & bản đồ tự động cho slot này")

        # Cột 4: Level, Reset & Points (178px Cố định - pack_propagate=False triệt tiêu phình ô)
        lvl_str = f"LV {ctrl.level}" if ctrl.level != "---" else "LV --"
        pts_init = f"⭐ {ctrl.points:,} pts" if ctrl.points > 0 else "⭐ 0 pts"
        pts_color = "#10b981" if ctrl.points > 0 else "#64748b"

        level_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=178, height=26)
        level_box.pack(side="left", padx=(2, 2))
        level_box.pack_propagate(False)

        lvl_lbl = ctk.CTkLabel(
            level_box,
            text=lvl_str,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        lvl_lbl.pack(side="left")
        add_tooltip(lvl_lbl, "Cấp độ hiện tại và số lần Reset (rr) của nhân vật")

        pts_lbl = ctk.CTkLabel(
            level_box,
            text=pts_init,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=pts_color
        )
        pts_lbl.pack(side="right", padx=(2, 0))
        add_tooltip(pts_lbl, "Điểm tiềm năng (Point) chưa phân bổ.")

        prog_bar = ctk.CTkProgressBar(
            level_box,
            width=174,
            height=2,
            corner_radius=1,
            fg_color="#1e2433",
            progress_color="#38bdf8"
        )
        prog_bar.set(0.0)
        prog_bar.pack(anchor="w", pady=(1, 0))
        exp_lbl = ctk.CTkLabel(level_box, text="", font=ctk.CTkFont(size=1))

        # Cột 5: Coordinates (88px Cố định)
        coords_frame = ctk.CTkFrame(
            row_frame,
            fg_color="#161a24",
            border_width=1,
            border_color="#222838",
            corner_radius=4,
            width=88,
            height=24
        )
        coords_frame.pack(side="left", padx=(2, 2))
        coords_frame.pack_propagate(False)

        coords_lbl = ctk.CTkLabel(
            coords_frame,
            text="--, --",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#f1f5f9"
        )
        coords_lbl.pack(fill="both", expand=True)
        add_tooltip(coords_frame, f"[Slot #{i:02d}] Tọa độ thời gian thực (X, Y) của nhân vật trong game.")

        # Cột 6: Status (88px Cố định)
        status_lbl = ctk.CTkLabel(
            row_frame,
            text="Idle",
            width=88,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        status_lbl.pack(side="left", padx=(2, 2))
        status_lbl.bind("<Button-1>", lambda e, s=i: self.on_slot_status_clicked(s))
        add_tooltip(status_lbl, f"[Slot #{i:02d}] Trạng thái hoạt động (Click để kết nối lại)")

        # Chuột phải vào dòng mở menu tiện ích
        import tkinter as tk
        def _show_slot_ctx(event, s=i):
            try:
                ctrl_s = self.controllers[s - 1]
                ds_status = "✅ BẬT" if ctrl_s.auto_devil else "❌ TẮT"
                rs_status = "✅ BẬT" if ctrl_s.auto_reset else "❌ TẮT"
                pt_status = "✅ BẬT" if ctrl_s.auto_add_point else "❌ TẮT"

                menu = tk.Menu(self, tearoff=0, bg="#181c26", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff")
                menu.add_command(label="🔄 Kết nối lại (Reconnect)", command=lambda: self.on_slot_status_clicked(s))
                menu.add_command(label="⚙️ Mở Cấu hình Chặng", command=lambda: self.jump_to_config_tab(s))
                menu.add_separator()
                mir_status = "✅ BẬT" if getattr(ctrl_s, "mirror_enabled", True) else "❌ TẮT"
                moss_status = "✅ BẬT" if getattr(ctrl_s, "moss_enabled", True) else "❌ TẮT"
                menu.add_command(label=f"🪞 Tham gia Double Goer (Mirror) [{mir_status}]", command=lambda: self.on_mirror_slot_enabled_toggled(s))
                menu.add_command(label=f"🎰 Tham gia Quay Moss Merchant [{moss_status}]", command=lambda: self.on_moss_slot_enabled_toggled(s))
                menu.add_separator()
                menu.add_command(label=f"🔥 Tự động đi Devil Square [{ds_status}]", command=lambda: self.on_toggle_slot_devil(s))
                menu.add_command(label=f"🔄 Tự động Reset [{rs_status}]", command=lambda: self.on_toggle_slot_reset(s))
                menu.add_command(label=f"⭐ Tự động Cộng Point [{pt_status}]", command=lambda: self.on_toggle_slot_point(s))
                menu.add_command(label="⚡ Đi Devil Square ngay lập tức", command=lambda: self.on_quick_devil_enter(s))
                menu.add_command(label="🔄 Thực hiện /reset ngay", command=lambda: self.on_quick_reset(s))
                menu.add_command(label="🛠️ Cài đặt tỷ lệ Point & Reset...", command=lambda: self.open_slot_stat_ratio_dialog(s))
                menu.add_separator()
                menu.add_command(label="🗑️ Ném đồ rác tại chỗ (Slot này)", command=lambda s=s: self.controllers[s - 1].clean_moss_inventory(run_in_thread=True))
                menu.add_command(label="💰 Bán đồ rác tại NPC Silvia", command=lambda s=s: self.controllers[s - 1].sell_moss_inventory())
                menu.add_command(label="💎 Tự động Gom Ngọc slot này", command=lambda s=s: threading.Thread(target=self.controllers[s - 1].auto_stack_jewels, daemon=True).start())
                menu.add_separator()
                menu.add_command(label="❌ Ngắt kết nối", command=lambda: self.controllers[s - 1].detach())
                menu.tk_popup(event.x_root, event.y_root)
            except Exception:
                pass

        for _w in (row_frame, slot_lbl, slot_badge, status_lbl, coords_frame, coords_lbl):
            _w.bind("<Button-3>", lambda e, s=i: _show_slot_ctx(e, s))

        # Cột 7: Actions (175px Cố định)
        actions_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=175, height=26)
        actions_box.pack(side="left", padx=(2, 2))
        actions_box.pack_propagate(False)

        # 1. Nút Play/Stop chính
        btn_toggle = ctk.CTkButton(
            actions_box,
            text="",
            image=getattr(self, "_icon_play_12", None) or UiIconFactory.get("play", color="#38bdf8", size=(11, 11)),
            width=26,
            height=24,
            corner_radius=4,
            fg_color="#161a24",
            hover_color="#222838",
            border_width=1,
            border_color="#2b3244",
            command=lambda s=i: self.on_slot_auto_toggle(s)
        )
        btn_toggle.pack(side="left", padx=1)
        add_tooltip(
            btn_toggle,
            f"[Slot #{i:02d}] ▶ Chạy / ⏹ Dừng Auto\n"
            "Bắt đầu hoặc tạm dừng chế độ tự động đánh quái và chạy chặng cho tài khoản này."
        )

        # 2. Nhóm Switch tính năng trực quan: [🔥] [🔄] [⭐]
        btn_devil = ctk.CTkButton(
            actions_box,
            text="🔥",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=28,
            height=24,
            corner_radius=4,
            fg_color="#4c0519" if ctrl.auto_devil else "#141824",
            text_color="#f43f5e" if ctrl.auto_devil else "#64748b",
            border_width=1,
            border_color="#e11d48" if ctrl.auto_devil else "#2b3244",
            hover_color="#881337" if ctrl.auto_devil else "#1e2433",
            command=lambda s=i: self.on_toggle_slot_devil(s)
        )
        btn_devil.pack(side="left", padx=1)
        add_tooltip(btn_devil, f"[Slot #{i:02d}] 🔥 Auto Devil Square ({'BẬT' if ctrl.auto_devil else 'TẮT'})")

        btn_reset = ctk.CTkButton(
            actions_box,
            text="🔄",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=28,
            height=24,
            corner_radius=4,
            fg_color="#064e3b" if ctrl.auto_reset else "#141824",
            text_color="#10b981" if ctrl.auto_reset else "#64748b",
            border_width=1,
            border_color="#059669" if ctrl.auto_reset else "#2b3244",
            hover_color="#047857" if ctrl.auto_reset else "#1e2433",
            command=lambda s=i: self.on_toggle_slot_reset(s)
        )
        btn_reset.pack(side="left", padx=1)
        add_tooltip(btn_reset, f"[Slot #{i:02d}] 🔄 Auto Reset ({'BẬT' if ctrl.auto_reset else 'TẮT'})")

        btn_point = ctk.CTkButton(
            actions_box,
            text="⭐",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=28,
            height=24,
            corner_radius=4,
            fg_color="#075985" if ctrl.auto_add_point else "#141824",
            text_color="#38bdf8" if ctrl.auto_add_point else "#64748b",
            border_width=1,
            border_color="#0284c7" if ctrl.auto_add_point else "#2b3244",
            hover_color="#0369a1" if ctrl.auto_add_point else "#1e2433",
            command=lambda s=i: self.on_toggle_slot_point(s)
        )
        btn_point.pack(side="left", padx=1)
        add_tooltip(btn_point, f"[Slot #{i:02d}] ⭐ Auto Cộng Point ({'BẬT' if ctrl.auto_add_point else 'TẮT'})")

        btn_cfg = ctk.CTkButton(
            actions_box,
            text="",
            image=UiIconFactory.get("gear", color="#94a3b8", size=(12, 12)),
            width=24,
            height=24,
            corner_radius=4,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2b3244",
            command=lambda s=i: self.open_slot_stat_ratio_dialog(s)
        )
        btn_cfg.pack(side="left", padx=1)
        add_tooltip(btn_cfg, f"[Slot #{i:02d}] ⚙️ Cài đặt Slot & Tỷ lệ Point")

        btn_log = ctk.CTkButton(
            actions_box,
            text="",
            image=UiIconFactory.get("file", color="#94a3b8", size=(12, 12)),
            width=24,
            height=24,
            corner_radius=4,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2b3244",
            command=lambda s=i: self.jump_to_slot_logs(s)
        )
        btn_log.pack(side="left", padx=1)
        add_tooltip(btn_log, f"[Slot #{i:02d}] 📋 Xem Nhật Ký (Logs)")

        # Lưu references để cập nhật
        self.slot_ui_elements[i] = {
            "row_frame": row_frame,
            "proc_var": proc_var,
            "proc_combo": proc_combo,
            "profile_var": profile_var,
            "preset_combo": preset_combo,
            "preset_lbl": preset_combo,
            "lvl_lbl": lvl_lbl,
            "prog_bar": prog_bar,
            "exp_lbl": exp_lbl,
            "pts_lbl": pts_lbl,
            "coords_lbl": coords_lbl,
            "status_lbl": status_lbl,
            "btn_toggle": btn_toggle,
            "btn_devil": btn_devil,
            "btn_reset": btn_reset,
            "btn_point": btn_point,
            "btn_cfg": btn_cfg,
            "btn_log": btn_log
        }
        self.update_slot_run_button_state(i)

    def add_new_slot(self):
        """Thêm 1 slot tài khoản mới vào cuối danh sách (tùy thuộc vào License)."""
        lic_data = license_client.load_license_data() if license_client else {}
        is_valid = license_client.is_license_valid() if license_client else False
        max_allowed = int(lic_data.get("max_slots", 5 if not is_valid else 10))

        cur_count = len(self.controllers)
        if cur_count >= max_allowed or cur_count >= MAX_SLOTS:
            if not is_valid:
                msg = f"Chế độ dùng thử mặc định chỉ hỗ trợ tối đa {max_allowed} tài khoản!\nVui lòng kích hoạt Bản Quyền để thêm thêm tài khoản."
            else:
                msg = f"Gói bản quyền hiện tại của bạn cho phép tối đa {max_allowed} tài khoản.\nVui lòng liên hệ nâng cấp gói bản quyền để mở thêm Slot."
            self.log_message(msg, "WARNING")
            try:
                from tkinter import messagebox
                messagebox.showinfo("Giới Hạn Bản Quyền", msg)
            except Exception:
                pass
            self.switch_tab("logs")
            return

        new_slot_idx = cur_count + 1
        default_profile = 1
        self.slot_assignments[new_slot_idx] = default_profile
        ConfigPersistenceManager.save_slot_assignment(new_slot_idx, default_profile)

        ctrl = SlotController(new_slot_idx, self, default_profile=default_profile)
        self.controllers.append(ctrl)

        self.create_slot_row(new_slot_idx)
        if hasattr(self, "create_moss_slot_row") and hasattr(self, "moss_scroll_frame"):
            try:
                self.create_moss_slot_row(new_slot_idx)
            except Exception:
                pass
        if hasattr(self, "create_mirror_slot_row") and hasattr(self, "mirror_scroll_frame"):
            try:
                self.create_mirror_slot_row(new_slot_idx)
            except Exception:
                pass
        self.update_combo_slot_options()
        self.update_header_stats()
        if hasattr(self, "update_mirror_selected_badge"):
            self.update_mirror_selected_badge()
        if hasattr(self, "update_moss_selected_badge"):
            self.update_moss_selected_badge()
        self.log_message(f"Đã thêm Account Slot #{new_slot_idx:02d} thành công.", "SUCCESS")

    def remove_last_slot(self):
        """Xóa slot tài khoản cuối cùng."""
        if len(self.controllers) <= 1:
            self.log_message("Không thể xóa: Cần giữ lại ít nhất 1 tài khoản.", "WARNING")
            return

        last_idx = len(self.controllers)
        ctrl = self.controllers[-1]

        # Dừng auto và ngắt kết nối an toàn nếu đang chạy
        if ctrl.worker and ctrl.worker.running:
            ctrl.stop_auto(reason=f"Người dùng bấm nút Xóa Slot #{last_idx:02d}", trigger_by="MANUAL")
        if hasattr(ctrl, "stop_moss"):
            ctrl.stop_moss()
        if hasattr(ctrl, "stop_mirror_auto"):
            ctrl.stop_mirror_auto()
        if hasattr(ctrl, "stop_mirror_turbo_sniping"):
            ctrl.stop_mirror_turbo_sniping()
        if ctrl.engine:
            try:
                ctrl.engine.detach()
            except Exception:
                pass

        # Xóa UI row trong tab Accounts
        el = self.slot_ui_elements.pop(last_idx, None)
        if el and el.get("row_frame"):
            try:
                el["row_frame"].destroy()
            except Exception:
                pass

        # Xóa UI row trong tab Moss
        if hasattr(self, "moss_ui_elements"):
            el_m = self.moss_ui_elements.pop(last_idx, None)
            if el_m and el_m.get("row_frame"):
                try:
                    el_m["row_frame"].destroy()
                except Exception:
                    pass

        # Xóa UI row trong tab Mirror
        if hasattr(self, "mirror_ui_elements"):
            el_mir = self.mirror_ui_elements.pop(last_idx, None)
            if el_mir and el_mir.get("row_frame"):
                try:
                    el_mir["row_frame"].destroy()
                except Exception:
                    pass

        self.controllers.pop()
        self.slot_assignments.pop(last_idx, None)
        ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)

        self.update_combo_slot_options()
        self.update_header_stats()
        if hasattr(self, "update_mirror_selected_badge"):
            self.update_mirror_selected_badge()
        if hasattr(self, "update_moss_selected_badge"):
            self.update_moss_selected_badge()
        self.log_message(f"Đã xóa Account Slot #{last_idx:02d}.", "INFO")

    def update_combo_slot_options(self):
        """Cập nhật số lượng tài khoản trên tab bar và footer."""
        n = len(self.controllers)
        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({n})")
        if hasattr(self, "footer_stats_lbl"):
            num_conn = sum(1 for c in self.controllers if c.assigned_pid and is_megamu_process_alive(c.assigned_pid))
            num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
            self.footer_stats_lbl.configure(text=tr("footer_stats", slots=n, conn=num_conn, auto=num_auto))
        if hasattr(self, "update_moss_slot_telemetry"):
            for c in self.controllers:
                try:
                    self.update_moss_slot_telemetry(c.slot_idx, c.char_name, c.assigned_pid)
                except Exception:
                    pass
        if hasattr(self, "update_mirror_slot_telemetry"):
            for c in self.controllers:
                try:
                    self.update_mirror_slot_telemetry(c.slot_idx, c.char_name, c.assigned_pid, c.coords)
                except Exception:
                    pass

    def jump_to_slot_logs(self, slot_idx: int):
        """Mở nhanh cửa sổ Nhật ký và lọc theo Slot khi bấm nút 📄 ở Slot."""
        s_tag = f"{slot_idx:02d}"
        self.open_logs_window(default_slot=s_tag)

    def open_text_config(self):
        """Mở thư mục cấu hình."""
        try:
            import subprocess
            if CONFIG_DIR.exists():
                subprocess.Popen(f'explorer "{CONFIG_DIR}"')
        except Exception:
            pass

    def show_help(self):
        """Hiển thị hộp thoại trợ giúp."""
        try:
            from tkinter import messagebox
            messagebox.showinfo(
                "MEGAMU Auto Train Dashboard",
                f"MEGAMU Auto Train Dashboard {APP_VERSION}\n\n"
                "- Kết nối native không chiếm chuột (Zero-Mouse Direct Engine)\n"
                "- Tự động tìm đường A*, di chuyển, bật/tắt MuHelper và nhận diện Reset\n"
                "- Hỗ trợ đa tài khoản không giới hạn\n\n"
                "Tác giả & Bản quyền: MEGATEAM\n"
                "Liên hệ: MEGATEAM | Hotline / Zalo: 036.203.1354\n\n"
                "Bản quyền: Bấm nút '🔑 License' trên thanh tiêu đề để kích hoạt bản quyền."
            )
        except Exception:
            pass

    def _verify_license_async(self):
        """Kiểm tra và tự động đồng bộ tính năng/bản quyền mới từ Server ngầm."""
        if not getattr(self, "running", True) or not license_client:
            return
        try:
            lic_data = license_client.load_license_data() if license_client else {}
            if lic_data and lic_data.get("license_key"):
                ok, msg, info = license_client.verify_license()
                if not ok:
                    # Máy chủ phản hồi key đã bị xóa / khóa / không hợp lệ
                    self.after(0, self.apply_license_lock_state)
                    self.after(0, self.open_license_dialog)
            self.after(0, self.update_header_stats)
            self.after(0, self.update_modules_visibility)
            self.after(0, self.apply_license_lock_state)
        except Exception:
            pass
        try:
            # Tự động đồng bộ lại định kỳ mỗi 5 phút (300.000 ms)
            self.after(300000, lambda: threading.Thread(target=self._verify_license_async, daemon=True).start())
        except Exception:
            pass

    def _check_initial_license(self):
        """Khởi động: Nếu chưa có bản quyền hợp lệ cho máy này, mở ngay hộp thoại kích hoạt."""
        if license_client and not license_client.is_license_valid():
            self.open_license_dialog()

    def open_license_dialog(self):
        """Mở cửa sổ quản lý và kích hoạt bản quyền MEGAMU Auto Train Dashboard."""
        from ui.modals.license_dialog import open_license_dialog as _open
        return _open(self)

    def open_update_dialog(self):
        """Mở cửa sổ Cập nhật bắt buộc (Mandatory Update Dialog)."""
        from ui.modals.update_dialog import open_update_dialog as _open
        return _open(self)

    def _check_update_async(self, manual: bool = False):
        """Kiểm tra cập nhật ngầm từ máy chủ cập nhật."""
        if not updater:
            if manual:
                self.after(0, lambda: messagebox.showinfo("Cập nhật", "Mô-đun cập nhật chưa được tải."))
            return

        try:
            res = updater.check_for_updates(APP_VERSION)
            if res.get("has_update"):
                self.is_update_mandatory = True
                self.update_info = res
                self.after(0, self._on_mandatory_update_detected)
            else:
                if manual:
                    self.after(0, lambda: messagebox.showinfo(
                        "Kiểm tra Cập nhật",
                        "Hiện tại chưa có bản cập nhật mới nhất."
                    ))
        except Exception:
            if manual:
                self.after(0, lambda: messagebox.showinfo("Kiểm tra Cập nhật", "Hiện tại chưa có bản cập nhật mới nhất."))

    def _on_mandatory_update_detected(self):
        """Xử lý khi phát hiện phiên bản mới: khóa chương trình và mở hộp thoại cập nhật."""
        self.apply_license_lock_state()
        if hasattr(self, "btn_update"):
            self.btn_update.configure(
                text="",
                image=UiIconFactory.get("refresh", color="#ef4444", size=(14, 14)),
                fg_color="#450a0a",
                hover_color="#7f1d1d",
                border_color="#ef4444"
            )
        self.open_update_dialog()

    def check_for_updates_ui(self, manual: bool = False):
        """Nút bấm kiểm tra cập nhật trên Header."""
        if getattr(self, "is_update_mandatory", False) and self.update_info:
            self.open_update_dialog()
            return

        if manual and hasattr(self, "btn_update"):
            self.btn_update.configure(state="disabled")

        def _worker():
            try:
                res = updater.check_for_updates(APP_VERSION) if updater else {"has_update": False}
                def _done():
                    if hasattr(self, "btn_update"):
                        self.btn_update.configure(state="normal")
                    if res.get("has_update"):
                        self.is_update_mandatory = True
                        self.update_info = res
                        self.apply_license_lock_state()
                        if hasattr(self, "btn_update"):
                            self.btn_update.configure(
                                text="",
                                image=UiIconFactory.get("refresh", color="#ef4444", size=(14, 14)),
                                fg_color="#450a0a",
                                hover_color="#7f1d1d",
                                border_color="#ef4444"
                            )
                        self.open_update_dialog()
                    else:
                        if hasattr(self, "btn_update"):
                            self.btn_update.configure(
                                text="",
                                image=UiIconFactory.get("refresh", color="#10b981", size=(14, 14)),
                                fg_color="#181c26",
                                hover_color="#242b3a",
                                border_color="#059669"
                            )
                        if manual:
                            messagebox.showinfo(
                                "Kiểm tra Cập nhật",
                                "Hiện tại chưa có bản cập nhật mới nhất."
                            )
                self.after(0, _done)
            except Exception:
                def _err():
                    if hasattr(self, "btn_update"):
                        self.btn_update.configure(
                            text="",
                            image=UiIconFactory.get("refresh", color="#10b981", size=(14, 14)),
                            state="normal"
                        )
                    if manual:
                        messagebox.showinfo("Kiểm tra Cập nhật", "Hiện tại chưa có bản cập nhật mới nhất.")
                self.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    def build_profiles_view(self):
        # Thanh điều khiển cấu hình trên cùng
        top_bar = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(4, 6))

        self.lbl_edit_profile = ctk.CTkLabel(
            top_bar, text=tr("edit_profile"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        )
        self.lbl_edit_profile.pack(side="left", padx=(0, 6))

        self.editor_profile_var = ctk.StringVar(value="Config 1")
        self.editor_profile_combo = ModernOptionMenu(
            top_bar,
            values=PROFILE_NAMES,
            variable=self.editor_profile_var,
            width=115,
            height=28,
            fg_color="#181c26",
            border_color="#2a3042",
            hover_color="#222736",
            command=self.on_editor_profile_change,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.editor_profile_combo.pack(side="left", padx=4)

        self.lbl_pk_delay = ctk.CTkLabel(
            top_bar, text=tr("pk_delay"), font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#d1d5db"
        )
        self.lbl_pk_delay.pack(side="left", padx=(16, 6))

        self.editor_respawn_var = ctk.StringVar(value="15")
        self.editor_respawn_entry = ctk.CTkEntry(
            top_bar,
            textvariable=self.editor_respawn_var,
            width=65,
            height=28,
            fg_color="#27272a",
            border_color="#3f3f46",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.editor_respawn_entry.pack(side="left", padx=4)

        # Nút Lưu và Tải lại bên phải
        self.btn_reload_cfg = ctk.CTkButton(
            top_bar,
            text=tr("reload"),
            width=80,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.reload_editor_from_file
        )
        self.btn_reload_cfg.pack(side="right", padx=(4, 0))

        self.btn_save_cfg = ctk.CTkButton(
            top_bar,
            text=tr("save_profile"),
            width=95,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.save_editor_to_file
        )
        self.btn_save_cfg.pack(side="right", padx=4)

        # Chú thích Team mặc định
        self.lbl_team_note = ctk.CTkLabel(
            self.panel_profiles,
            text=tr("team_note"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9ca3af"
        )
        self.lbl_team_note.pack(anchor="w", padx=12, pady=(0, 8))

        # Tiêu đề cột bảng Stage
        stage_header = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        stage_header.pack(fill="x", padx=12, pady=(0, 4))

        stage_cols = [
            ("stage_min", 65, "center"),
            ("stage_max", 65, "center"),
            ("stage_map", 220, "center"),
            ("stage_x", 70, "center"),
            ("stage_y", 70, "center")
        ]
        self.stage_header_labels = []
        for k, w, anc in stage_cols:
            lbl = ctk.CTkLabel(
                stage_header,
                text=tr(k),
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#9ca3af"
            )
            lbl.pack(side="left", padx=3)
            self.stage_header_labels.append(lbl)

        # 10 Hàng chặng
        self.editor_rows = []
        for r in range(10):
            row_f = ctk.CTkFrame(self.panel_profiles, fg_color="transparent", height=32)
            row_f.pack(fill="x", padx=12, pady=2)

            min_var = ctk.StringVar(value="")
            min_ent = ctk.CTkEntry(
                row_f, textvariable=min_var, width=65, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            min_ent.pack(side="left", padx=3)

            max_var = ctk.StringVar(value="")
            max_ent = ctk.CTkEntry(
                row_f, textvariable=max_var, width=65, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            max_ent.pack(side="left", padx=3)

            map_var = ctk.StringVar(value="")
            map_combo = ModernOptionMenu(
                row_f,
                values=[""] + self.map_list,
                variable=map_var,
                width=220,
                height=28,
                fg_color="#181c26",
                border_color="#2a3042",
                hover_color="#222736",
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            map_combo.pack(side="left", padx=3)

            x_var = ctk.StringVar(value="")
            x_ent = ctk.CTkEntry(
                row_f, textvariable=x_var, width=70, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            x_ent.pack(side="left", padx=3)

            y_var = ctk.StringVar(value="")
            y_ent = ctk.CTkEntry(
                row_f, textvariable=y_var, width=70, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            y_ent.pack(side="left", padx=3)

            self.editor_rows.append({
                "min": min_var,
                "max": max_var,
                "map": map_var,
                "x": x_var,
                "y": y_var
            })

        # Nạp dữ liệu Config 1 ban đầu
        self.load_profile_into_editor(1)

    def load_profile_into_editor(self, profile_idx: int):
        """Đọc Profile từ file JSON và điền vào form."""
        self.current_editor_profile_idx = profile_idx
        self.editor_profile_var.set(f"Config {profile_idx}")
        if hasattr(self, "editor_profile_combo") and self.editor_profile_combo:
            try:
                self.editor_profile_combo.set(f"Config {profile_idx}")
            except Exception:
                pass
        cfg = ConfigPersistenceManager.load_single_profile(profile_idx)
        self.editor_respawn_var.set(str(cfg.get("respawn_delay", 15)))

        stages = cfg.get("stages", [])
        for i, row in enumerate(self.editor_rows):
            if i < len(stages):
                st = stages[i]
                row["min"].set(str(st.get("min_level", "")))
                row["max"].set(str(st.get("max_level", "")))
                row["map"].set(str(st.get("map_name", "")))
                row["x"].set(str(st.get("x", "")))
                row["y"].set(str(st.get("y", "")))
            else:
                row["min"].set("")
                row["max"].set("")
                row["map"].set("")
                row["x"].set("")
                row["y"].set("")

    def on_editor_profile_change(self, val: str):
        try:
            new_idx = int(val.replace("Config ", "").strip())
            prev_idx = getattr(self, "current_editor_profile_idx", 1)
            # Chỉ lưu cấu hình CŨ (prev_idx) trước khi chuyển sang xem profile mới
            if prev_idx != new_idx:
                try:
                    self.save_editor_to_file(silent=True, target_idx=prev_idx)
                except Exception as e:
                    print(f"[DashboardApp] Lỗi lưu cấu hình cũ: {e}")
            # Nạp cấu hình MỚI vào form
            self.load_profile_into_editor(new_idx)
            self.log_message(f"⚙️ [Cấu Hình] Đã chuyển sang soạn thảo: Config {new_idx}", "INFO")
        except Exception as e:
            self.log_message(f"Lỗi chuyển cấu hình soạn thảo: {e}", "ERROR")

    def reload_editor_from_file(self):
        """Tải lại dữ liệu tươi mới từ file đĩa JSON."""
        try:
            idx = getattr(self, "current_editor_profile_idx", 1)
            self.load_profile_into_editor(idx)
            self.log_message(f"Đã tải lại Config {idx} trực tiếp từ file autotrain_profiles.json.", "INFO")
        except Exception as e:
            self.log_message(f"Lỗi khi tải lại cấu hình: {e}", "ERROR")

    def save_editor_to_file(self, silent: bool = False, target_idx: Optional[int] = None):
        """Lưu toàn bộ thay đổi trực tiếp vào file JSON."""
        try:
            if target_idx is not None:
                idx = int(target_idx)
            else:
                idx = getattr(self, "current_editor_profile_idx", 1)
            # Đọc config gốc để giữ các trường mở rộng
            cfg = ConfigPersistenceManager.load_single_profile(idx)
            try:
                respawn = int(self.editor_respawn_var.get().strip())
            except Exception:
                respawn = 15
            cfg["respawn_delay"] = respawn

            new_stages = []
            for row in self.editor_rows:
                min_s = row["min"].get().strip()
                max_s = row["max"].get().strip()
                map_s = row["map"].get().strip()
                x_s = row["x"].get().strip()
                y_s = row["y"].get().strip()

                if min_s and max_s and map_s and x_s and y_s:
                    try:
                        new_stages.append({
                            "min_level": int(min_s),
                            "max_level": int(max_s),
                            "map_name": map_s,
                            "x": int(x_s),
                            "y": int(y_s)
                        })
                    except Exception:
                        pass

            existing_stages = cfg.get("stages", [])
            existing_respawn = cfg.get("respawn_delay", 15)
            is_changed = (existing_respawn != respawn or existing_stages != new_stages)

            # Nếu gọi ở chế độ silent (chuyển tab) và không hề có thay đổi nào, bỏ qua không chạm đĩa/worker
            if silent and not is_changed:
                return

            cfg["stages"] = new_stages
            # Ghi trực tiếp vào file đĩa
            ConfigPersistenceManager.save_single_profile(idx, cfg)
            if not silent:
                self.log_message(
                    f"Đã lưu thành công Config {idx} ({len(new_stages)} chặng) vào file autotrain_profiles.json!",
                    "SUCCESS"
                )

            # Chỉ cập nhật các worker đang chạy Config này nếu stages thực sự thay đổi
            if is_changed:
                for ctrl in self.controllers:
                    if ctrl.profile_index == idx and ctrl.worker and ctrl.worker.running:
                        if hasattr(ctrl.worker, 'update_config'):
                            ctrl.worker.update_config(cfg)
                        if not silent:
                            self.log_message(
                                f"[Slot {ctrl.slot_idx:02d}] Áp dụng ngay cấu hình vừa lưu mà không cần khởi động lại!",
                                "SUCCESS"
                            )
        except Exception as e:
            if not silent:
                self.log_message(f"Lỗi khi lưu cấu hình: {e}", "ERROR")

    # ==========================================================================
    # TAB 3: BẢN QUYỀN, CẬP NHẬT & NHẬT KÝ (LICENSE, UPDATE & LOGS TAB)
    # ==========================================================================
    def build_logs_view(self):
        # 1. Thẻ thông tin Bản quyền & Cập nhật Hệ thống (System License & Update Card)
        lic_card = ctk.CTkFrame(self.panel_logs, fg_color="#181c26", corner_radius=0, border_width=1, border_color="#2b3244")
        lic_card.pack(fill="x", padx=10, pady=(10, 6))

        inner_card = ctk.CTkFrame(lic_card, fg_color="transparent")
        inner_card.pack(fill="both", expand=True, padx=14, pady=10)

        # Cột trái: Thông tin Bản quyền & HWID
        left_box = ctk.CTkFrame(inner_card, fg_color="transparent")
        left_box.pack(side="left", fill="both", expand=True)

        title_row = ctk.CTkFrame(left_box, fg_color="transparent")
        title_row.pack(anchor="w", fill="x")

        ctk.CTkLabel(
            title_row,
            text="🔑 BẢN QUYỀN HỆ THỐNG",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left")

        self.lbl_lic_status_badge = ctk.CTkLabel(
            title_row,
            text="[ĐANG KIỂM TRA]",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#facc15"
        )
        self.lbl_lic_status_badge.pack(side="left", padx=(10, 0))

        self.lbl_lic_details = ctk.CTkLabel(
            left_box,
            text="Gói dịch vụ: -- | Hạn dùng: -- | Slot tối đa: --",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.lbl_lic_details.pack(anchor="w", pady=(3, 5))

        hwid_action_row = ctk.CTkFrame(left_box, fg_color="transparent")
        hwid_action_row.pack(anchor="w", fill="x")

        self.lbl_lic_hwid = ctk.CTkLabel(
            hwid_action_row,
            text="HWID: Đang nạp...",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_lic_hwid.pack(side="left", padx=(0, 10))

        self.btn_copy_hwid_tab = ctk.CTkButton(
            hwid_action_row,
            text="Sao chép HWID",
            width=100,
            height=24,
            corner_radius=0,
            fg_color="#242b3a",
            hover_color="#333c52",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#e2e8f0",
            command=self._copy_hwid_to_clipboard
        )
        self.btn_copy_hwid_tab.pack(side="left", padx=(0, 8))

        btn_key_mgmt = ctk.CTkButton(
            hwid_action_row,
            text="🔑 Kích hoạt / Đổi Key",
            width=135,
            height=24,
            corner_radius=0,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#ffffff",
            command=self.open_license_dialog
        )
        btn_key_mgmt.pack(side="left")

        # Cột phải: Phiên bản & Cập nhật
        right_box = ctk.CTkFrame(inner_card, fg_color="transparent")
        right_box.pack(side="right", fill="y", padx=(16, 0))

        ctk.CTkLabel(
            right_box,
            text=f"🔄 PHIÊN BẢN {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#34d399"
        ).pack(anchor="e")

        btn_chk_update = ctk.CTkButton(
            right_box,
            text="🔄 Kiểm tra cập nhật",
            width=135,
            height=26,
            corner_radius=0,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#ffffff",
            command=lambda: self.check_for_updates_ui(manual=True)
        )
        btn_chk_update.pack(anchor="e", pady=(4, 0))

        # 2. KHUNG NHẬT KÝ HOẠT ĐỘNG
        top_bar = ctk.CTkFrame(self.panel_logs, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(6, 4))

        self.lbl_log_show = ctk.CTkLabel(
            top_bar, text="📋 Nhật ký hoạt động:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        )
        self.lbl_log_show.pack(side="left", padx=(0, 6))

        filter_options = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
        self.log_filter_var = ctk.StringVar(value=tr("all"))
        self.log_filter_combo = ModernOptionMenu(
            top_bar,
            values=filter_options,
            variable=self.log_filter_var,
            width=90,
            height=28,
            fg_color="#181c26",
            border_color="#2a3042",
            hover_color="#222736",
            command=lambda _: self.render_logs(),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.log_filter_combo.pack(side="left", padx=4)

        self.btn_clear_log = ctk.CTkButton(
            top_bar,
            text=tr("clear_view"),
            width=85,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.clear_logs
        )
        self.btn_clear_log.pack(side="right")

        self.btn_open_stop_log = ctk.CTkButton(
            top_bar,
            text="📑 Mở Log Dừng Auto",
            width=140,
            height=28,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#38bdf8",
            text_color="#38bdf8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.open_stop_events_log_file
        )
        self.btn_open_stop_log.pack(side="right", padx=(0, 6))

        # Hộp văn bản hiển thị Log
        self.log_textbox = ctk.CTkTextbox(
            self.panel_logs,
            fg_color="#121214",
            text_color="#f3f4f6",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=0,
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.log_textbox.configure(state="disabled")

    def refresh_license_and_logs_tab(self):
        """Cập nhật thông tin License & Cập nhật và render logs trên Tab Nhật ký (Zero disk I/O on UI)."""
        try:
            # Chỉ cập nhật nhãn license nếu chưa render hoặc trạng thái thay đổi (Tránh đọc đĩa mỗi lần chuyển tab)
            if not getattr(self, "_license_tab_rendered", False):
                self._license_tab_rendered = True
                lic_data = license_client.load_license_data() if license_client else {}
                is_valid = license_client.is_license_valid() if license_client else False
                hwid_val = license_client.get_machine_hwid() if license_client else "N/A"

                plan = lic_data.get("plan_type", "Chưa kích hoạt" if not is_valid else "Gói tiêu chuẩn")
                exp = lic_data.get("expires_at", "--")
                if exp and exp != "--":
                    exp = str(exp).split(" ")[0]
                max_s = lic_data.get("max_slots", 5 if not is_valid else 10)

                if hasattr(self, "lbl_lic_status_badge"):
                    if is_valid:
                        self.lbl_lic_status_badge.configure(text="[ĐÃ KÍCH HOẠT]", text_color="#4ade80")
                    else:
                        self.lbl_lic_status_badge.configure(text="[DÙNG THỬ / CHƯA KÍCH HOẠT]", text_color="#f87171")

                if hasattr(self, "lbl_lic_details"):
                    self.lbl_lic_details.configure(text=f"Gói dịch vụ: {plan}   |   Hạn dùng: {exp}   |   Hỗ trợ tối đa: {max_s} Slots")

                if hasattr(self, "lbl_lic_hwid"):
                    short_hwid = hwid_val if len(hwid_val) <= 24 else (hwid_val[:14] + "..." + hwid_val[-8:])
                    self.lbl_lic_hwid.configure(text=f"HWID: {short_hwid}")
        except Exception:
            pass
        if getattr(self, "_logs_dirty", True):
            self.render_logs()

    def _copy_hwid_to_clipboard(self):
        try:
            cur_h = license_client.get_machine_hwid() if license_client else ""
            if cur_h and cur_h != "THIẾU_MEG_LICENSE_BRIDGE_DLL":
                self.clipboard_clear()
                self.clipboard_append(cur_h)
                if hasattr(self, "btn_copy_hwid_tab"):
                    self.btn_copy_hwid_tab.configure(text="Đã chép!", fg_color="#16a34a")
                    self.after(1500, lambda: self.btn_copy_hwid_tab.configure(text="Sao chép HWID", fg_color="#242b3a"))
                self.log_message(f"Đã sao chép HWID vào Clipboard: {cur_h}", "SUCCESS")
        except Exception:
            pass

    def open_stop_events_log_file(self):
        """Mở file auto_stop_events.log bằng Notepad hoặc trình đọc mặc định."""
        try:
            if not AUTO_STOP_LOG_FILE.exists():
                header = (
                    "========================================================================================\n"
                    "MEGAMU AUTO TRAIN - NHẬT KÝ CHI TIẾT CÁC LẦN DỪNG AUTO (AUDIT TRACE LOG)\n"
                    "Quy ước: [MANUAL] = Người dùng bấm dừng | [SYSTEM] = Hệ thống / Game tự ngắt\n"
                    "========================================================================================\n\n"
                )
                AUTO_STOP_LOG_FILE.write_text(header, encoding="utf-8")
            os.startfile(str(AUTO_STOP_LOG_FILE))
        except Exception as e:
            self.log_message(f"Không thể mở file log: {e}", "ERROR")

    def open_profiles_modal(self, profile_index: Optional[int] = None):
        """Mở cửa sổ Modal Cấu hình Chặng & Tuyến Đường (Profiles Modal)."""
        from ui.modals.profiles_modal import open_profiles_modal as _open
        return _open(self, profile_index)

    def open_logs_window(self, default_slot: Optional[str] = None):
        """Mở cửa sổ Nhật ký hoạt động chuyên dụng (Floating Logs Window) từ Header."""
        from ui.modals.logs_modal import open_logs_window as _open
        return _open(self, default_slot)

    def append_log(self, msg: str, level: str = "INFO"):
        """Ghi nhận log hệ thống an toàn (alias tương thích ngược cho log_message)."""
        self.log_message(msg, level=level)

    def log_message(self, msg: str, level: str = "INFO"):
        """Ghi nhận log hệ thống và hiển thị lên giao diện một cách an toàn đa luồng."""
        # Ghi log bất đồng bộ qua AsyncRingBufferLogger (Không block UI, auto log rotation)
        self.logger.log(msg, level=level)


        # Trì hoãn và gom nhóm việc render lên GUI Main Thread (Debounce 100ms)
        # TUYỆT ĐỐI không gọi widget Tkinter trực tiếp từ luồng nền worker
        if not getattr(self, "_render_logs_scheduled", False):
            self._render_logs_scheduled = True
            try:
                self.after(100, self._async_render_logs)
            except Exception:
                self._render_logs_scheduled = False

    def _async_render_logs(self):
        self._render_logs_scheduled = False
        self.render_logs()

    def render_logs(self):
        if not hasattr(self, "log_textbox") or not self.log_textbox:
            return
        if getattr(self, "active_tab", "") != "logs":
            self._logs_dirty = True
            return
        try:
            if not self.log_textbox.winfo_exists():
                return
            if hasattr(self, "logger") and self.logger:
                self.logs_data = self.logger.get_logs_data_tuples()
            selected_filter = self.log_filter_var.get() if hasattr(self, "log_filter_var") else tr("all")

            lines = []
            for t_str, s_tag, content in list(self.logs_data):
                if selected_filter == tr("all") or selected_filter == s_tag:
                    lines.append(f"[{t_str}] {content}")

            if not lines:
                lines.append(f"[{time.strftime('%H:%M:%S')}] [INFO] Nhật ký hệ thống sẵn sàng. Đang chờ các hoạt động từ các Slot...")

            # Giới hạn hiển thị 300 dòng gần nhất để cuộn siêu mượt, không đơ lag giao diện
            if len(lines) > 300:
                lines = lines[-300:]

            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.insert("end", "\n".join(lines) + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
            self._logs_dirty = False
        except Exception:
            pass

    def clear_logs(self):
        self.logger.clear()
        self.logs_data.clear()
        if hasattr(self, "log_textbox") and self.log_textbox:
            try:
                if self.log_textbox.winfo_exists():
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.delete("1.0", "end")
                    self.log_textbox.configure(state="disabled")
            except Exception:
                pass

    # ==========================================================================
    # QUẢN LÝ MODULE BẢN QUYỀN & ĐIỀU HƯỚNG TAB
    # ==========================================================================
    def update_modules_visibility(self):
        """Ẩn/hiện các tab module theo license đã kích hoạt."""
        if not hasattr(self, "tab_accounts_btn"):
            return

        has_train = license_client.has_license_module("train") if license_client else True
        has_moss = license_client.has_license_module("moss") if license_client else True
        has_mirror = license_client.has_license_module("mirror") if license_client else True

        # Unpack các nút tab tính năng
        self.tab_accounts_btn.pack_forget()
        self.tab_profiles_btn.pack_forget()
        self.tab_ram_btn.pack_forget()
        self.tab_moss_btn.pack_forget()
        self.tab_mirror_btn.pack_forget()
        self.tab_autologin_btn.pack_forget()

        # Repack lại theo đúng thứ tự nếu module được cấp phép
        if has_train:
            self.tab_accounts_btn.pack(side="left", padx=2)
            # Profiles và Logs đã hiển thị dạng icon ở góc trên bên phải

        # self.tab_ram_btn.pack(side="left", padx=(0, 6)) # Tạm ẩn theo yêu cầu

        if has_moss:
            self.tab_moss_btn.pack(side="left", padx=(0, 6))

        if has_mirror:
            self.tab_mirror_btn.pack(side="left", padx=(0, 6))

        # if has_train:
        #     self.tab_autologin_btn.pack(side="left", padx=(0, 6)) # Tạm ẩn theo yêu cầu

        # Kiểm tra xem tab hiện tại có bị ẩn không, nếu có thì tự động đổi tab
        cur_tab = getattr(self, "active_tab", "accounts")
        if cur_tab in ("ram", "autologin"):
            self.switch_tab("accounts")
        elif cur_tab in ("accounts", "profiles") and not has_train:
            if has_moss:
                self.switch_tab("moss")
            elif has_mirror:
                self.switch_tab("mirror")
            else:
                self.switch_tab("logs")
        elif cur_tab == "moss" and not has_moss:
            if has_train:
                self.switch_tab("accounts")
            elif has_mirror:
                self.switch_tab("mirror")
            else:
                self.switch_tab("logs")
        elif cur_tab == "mirror" and not has_mirror:
            if has_train:
                self.switch_tab("accounts")
            elif has_moss:
                self.switch_tab("moss")
            else:
                self.switch_tab("logs")

    def switch_tab(self, tab_name: str):
        if tab_name == "profiles":
            self.open_profiles_modal()
            return
        if tab_name == "logs":
            self.open_logs_window()
            return
        # Chặn chuyển sang tab nếu module chưa được cấp phép
        if license_client:
            if tab_name in ("accounts", "profiles", "autologin") and not license_client.has_license_module("train"):
                return
            if tab_name == "moss" and not license_client.has_license_module("moss"):
                return
            if tab_name == "mirror" and not license_client.has_license_module("mirror"):
                return

        prev_tab = getattr(self, "active_tab", None)
        if prev_tab == tab_name:
            return

        # Tự động lưu cấu hình bất đồng bộ nếu đang rời khỏi tab profiles (tránh lag main thread)
        if prev_tab == "profiles" and tab_name != "profiles":
            try:
                threading.Thread(target=lambda: self.save_editor_to_file(silent=True), daemon=True).start()
            except Exception:
                pass

        self.active_tab = tab_name

        act_bg = "#18202d"
        act_border = "#14b8a6"
        act_text = "#2dd4bf"
        inact_text = "#94a3b8"

        tabs = [
            ("accounts", getattr(self, "tab_accounts_btn", None), "user"),
            ("profiles", getattr(self, "tab_profiles_btn", None), "gear"),
            ("logs", getattr(self, "tab_logs_btn", None), "file"),
            ("ram", getattr(self, "tab_ram_btn", None), "bolt"),
            ("moss", getattr(self, "tab_moss_btn", None), "dice"),
            ("mirror", getattr(self, "tab_mirror_btn", None), "mirror"),
            ("autologin", getattr(self, "tab_autologin_btn", None), "key"),
        ]

        # Khởi tạo cache icons một lần duy nhất để không tạo lại ảnh PIL khi chuyển tab
        if not hasattr(self, "_tab_icons_cache"):
            self._tab_icons_cache = {}
            for name, _, icon in tabs:
                self._tab_icons_cache[name] = (
                    UiIconFactory.get(icon, color="#2dd4bf", size=(14, 14)),
                    UiIconFactory.get(icon, color="#94a3b8", size=(14, 14))
                )

        btn_dict = {name: btn for name, btn, _ in tabs if btn is not None}

        # Cập nhật style nút: Tối ưu chỉ đổi 2 nút (cũ và mới) thay vì cập nhật cả 7 nút
        if prev_tab and prev_tab in btn_dict and prev_tab != tab_name:
            old_btn = btn_dict[prev_tab]
            old_icon = self._tab_icons_cache[prev_tab][1]
            old_btn.configure(
                fg_color="transparent",
                text_color=inact_text,
                border_width=0,
                border_color="#1e293b",
                image=old_icon
            )
        elif not prev_tab:
            for name, btn in btn_dict.items():
                if name != tab_name:
                    btn.configure(
                        fg_color="transparent",
                        text_color=inact_text,
                        border_width=0,
                        border_color="#1e293b",
                        image=self._tab_icons_cache[name][1]
                    )

        if tab_name in btn_dict:
            new_btn = btn_dict[tab_name]
            new_icon = self._tab_icons_cache[tab_name][0]
            new_btn.configure(
                fg_color=act_bg,
                text_color=act_text,
                border_width=1,
                border_color=act_border,
                image=new_icon
            )

        # Chuyển tab tức thì 0ms qua tkraise() (Persistent Grid Stacking - Zero Relayout)
        target_panel = getattr(self, f"panel_{tab_name}", None)
        if target_panel:
            target_panel.tkraise()
            self._active_panel = target_panel

        # Cập nhật dữ liệu tức thì cho tab logs, ram, moss, mirror (Lazy Batch Sync)
        if tab_name == "logs":
            self.refresh_license_and_logs_tab()
        elif tab_name == "ram":
            self.refresh_ram_tab_stats()
        elif tab_name == "moss":
            for c in self.controllers:
                self.update_moss_slot_telemetry(c.slot_idx, c.char_name, c.assigned_pid)
        elif tab_name == "mirror":
            for c in self.controllers:
                self.update_mirror_slot_telemetry(c.slot_idx, c.char_name, c.assigned_pid, c.coords)

    # ==========================================================================
    # TAB 4: TỐI ƯU HÓA BỘ NHỚ RAM (RAM OPTIMIZER TAB)
    # ==========================================================================
    def build_ram_view(self):
        """Xây dựng giao diện Tab Tối ưu hóa RAM tích hợp (Modular RamView)."""
        view = RamView(self, self.panel_ram)
        view.build()

    def _create_ram_kpi_card(self, parent, title, initial_val, color):
        return RamView(self, self.panel_ram).create_kpi_card(parent, title, initial_val, color)

    def refresh_ram_tab_stats(self):
        """Làm mới danh sách tiến trình MEGAMU và số liệu RAM ngầm qua thread, không gây block giao diện."""
        if not hasattr(self, "ram_clients_scroll") or getattr(self, "active_tab", "") != "ram":
            return

        if getattr(self, "_refreshing_ram_stats", False):
            return
        self._refreshing_ram_stats = True

        def _worker():
            try:
                clients = get_megamu_processes(self.detected_games) if get_megamu_processes else []
            except Exception:
                clients = []

            def _apply():
                self._refreshing_ram_stats = False
                if getattr(self, "active_tab", "") != "ram":
                    return
                self._apply_ram_tab_stats_ui(clients)

            try:
                if getattr(self, "running", True) and self.winfo_exists():
                    self.after(0, _apply)
                else:
                    self._refreshing_ram_stats = False
            except Exception:
                self._refreshing_ram_stats = False

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_ram_tab_stats_ui(self, clients: List[Dict[str, Any]]):
        """Cập nhật dữ liệu RAM lên giao diện không nhấp nháy (Zero-Flicker in-place update)."""
        if not hasattr(self, "ram_clients_scroll") or getattr(self, "active_tab", "") != "ram":
            return

        total_rss = sum(c["mem_bytes"] for c in clients)
        total_mb = total_rss / 1048576
        total_str = f"{total_mb / 1024:.2f} GB" if total_mb >= 1024 else f"{int(total_mb)} MB"
        c_text = f"{len(clients)} Client" if len(clients) == 1 else f"{len(clients)} Clients"

        if hasattr(self, "ram_card_clients"):
            self.ram_card_clients.value_label.configure(text=c_text)
        if hasattr(self, "ram_card_cur_ram"):
            self.ram_card_cur_ram.value_label.configure(text=total_str)
        if hasattr(self, "ram_card_saved") and self.ram_manager:
            tot_saved = self.ram_manager.total_saved_mb
            tot_str = f"{tot_saved / 1024:.2f} GB" if tot_saved >= 1024 else f"{int(tot_saved)} MB"
            self.ram_card_saved.value_label.configure(text=tot_str)

        if not hasattr(self, "ram_client_rows"):
            self.ram_client_rows = {}

        current_pids = set()

        if not clients:
            for pid, r_dict in list(self.ram_client_rows.items()):
                try:
                    r_dict["frame"].destroy()
                except Exception:
                    pass
            self.ram_client_rows.clear()
            if not getattr(self, "ram_empty_label", None):
                self.ram_empty_label = ctk.CTkLabel(
                    self.ram_clients_scroll,
                    text="Chưa phát hiện tiến trình MEGAMU.exe nào đang chạy.",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color="#64748b"
                )
                self.ram_empty_label.pack(pady=30)
            return
        else:
            if getattr(self, "ram_empty_label", None):
                try:
                    self.ram_empty_label.destroy()
                except Exception:
                    pass
                self.ram_empty_label = None

        for c in clients:
            pid = c["pid"]
            current_pids.add(pid)
            title = c.get("title") or self.detected_games.get(pid, "")
            cname = character_name_from_window_title(title)
            disp_name = f"{cname}" if cname else (title if title else f"MEGAMU Client")
            mem_mb = c["mem_mb"]
            mem_str = f"{mem_mb / 1024:.2f} GB" if mem_mb >= 1024 else f"{mem_mb:.1f} MB"

            if pid in self.ram_client_rows:
                # CẬP NHẬT TRỰC TIẾP TẠI CHỖ (IN-PLACE) - KHÔNG DESTROY/RECREATE -> KHÔNG BAO GIỜ BỊ NHÁY!
                r_dict = self.ram_client_rows[pid]
                if r_dict.get("name_lbl") and r_dict["name_lbl"].cget("text") != disp_name:
                    r_dict["name_lbl"].configure(text=disp_name)
                if r_dict.get("mem_lbl") and r_dict["mem_lbl"].cget("text") != mem_str:
                    r_dict["mem_lbl"].configure(text=mem_str)
            else:
                row = ctk.CTkFrame(self.ram_clients_scroll, fg_color="#181c26", height=36, corner_radius=0)
                row.pack(fill="x", pady=2)

                pid_lbl = ctk.CTkLabel(row, text=str(pid), width=70, anchor="w", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), text_color="#cbd5e1")
                pid_lbl.pack(side="left", padx=(10, 4))

                name_lbl = ctk.CTkLabel(row, text=disp_name, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#f8fafc")
                name_lbl.pack(side="left", fill="x", expand=True, padx=4)

                mem_lbl = ctk.CTkLabel(row, text=mem_str, width=105, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#f59e0b")
                mem_lbl.pack(side="left", padx=4)

                btn_trim_one = ctk.CTkButton(
                    row,
                    text="Trim RAM",
                    width=85,
                    height=24,
                    corner_radius=0,
                    fg_color="#0369a1",
                    hover_color="#0284c7",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    command=lambda p=pid: self.trim_single_client_ui(p)
                )
                btn_trim_one.pack(side="left", padx=(4, 8))

                self.ram_client_rows[pid] = {
                    "frame": row,
                    "name_lbl": name_lbl,
                    "mem_lbl": mem_lbl,
                    "btn": btn_trim_one
                }

        # Dọn dẹp những PID không còn tồn tại
        for pid in list(self.ram_client_rows.keys()):
            if pid not in current_pids:
                try:
                    self.ram_client_rows[pid]["frame"].destroy()
                except Exception:
                    pass
                del self.ram_client_rows[pid]

    def trim_ram_now_ui(self):
        """Thực hiện tối ưu toàn bộ tiến trình MEGAMU từ giao diện RAM tab."""
        if hasattr(self, "btn_ram_optimize_all"):
            self.btn_ram_optimize_all.configure(state="disabled", text="⏳ Đang giải phóng RAM...")

        def _run():
            if self.ram_manager:
                res = self.ram_manager.trim_now(self.detected_games)
            else:
                res = optimize_all_megamu(self.detected_games) if optimize_all_megamu else {}

            def _done():
                if hasattr(self, "btn_ram_optimize_all"):
                    self.btn_ram_optimize_all.configure(state="normal", text=f" {tr('ram_optimize_all_btn')}")
                c_cnt = res.get("total_clients", 0)
                s_cnt = res.get("success_count", 0)
                saved = res.get("saved_mb", 0.0)
                pct = res.get("saved_pct", 0.0)
                if c_cnt == 0:
                    self.append_ram_log("⚠️ Không tìm thấy tiến trình MEGAMU.exe nào đang chạy!")
                else:
                    self.append_ram_log(f"🎉 Đã giải phóng {saved:.1f} MB ({pct:.0f}%) trên {s_cnt}/{c_cnt} client MEGAMU!")
                self.refresh_ram_tab_stats()
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def quick_trim_ram(self):
        """Thực hiện dọn RAM 1-click từ thanh công cụ toolbar chính."""
        if hasattr(self, "btn_trim_ram"):
            self.btn_trim_ram.configure(state="disabled", text="⏳ Đang dọn...")

        def _run():
            if self.ram_manager:
                res = self.ram_manager.trim_now(self.detected_games)
            else:
                res = optimize_all_megamu(self.detected_games) if optimize_all_megamu else {}

            def _done():
                if hasattr(self, "btn_trim_ram"):
                    self.btn_trim_ram.configure(state="normal", text=f" {tr('ram_trim_now')}")
                c_cnt = res.get("total_clients", 0)
                s_cnt = res.get("success_count", 0)
                saved = res.get("saved_mb", 0.0)
                pct = res.get("saved_pct", 0.0)
                if c_cnt == 0:
                    self.log_message("⚠️ Không tìm thấy tiến trình MEGAMU.exe nào đang chạy để dọn RAM.", "WARNING")
                else:
                    self.log_message(f"🎉 Tối ưu RAM thành công: Đã thu hồi {saved:.1f} MB ({pct:.0f}%) trên {s_cnt}/{c_cnt} client MEGAMU!", "SUCCESS")
                if getattr(self, "active_tab", "") == "ram":
                    self.refresh_ram_tab_stats()
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def trim_single_client_ui(self, pid: int):
        def _run():
            mem_before = 0
            try:
                p = psutil.Process(pid)
                mem_before = p.memory_info().rss
            except Exception:
                pass
            ok = trim_single_process(pid) if trim_single_process else False
            time.sleep(0.2)
            mem_after = 0
            try:
                p = psutil.Process(pid)
                mem_after = p.memory_info().rss
            except Exception:
                pass
            saved_mb = max(0, (mem_before - mem_after) / 1048576)
            def _done():
                if ok:
                    self.append_ram_log(f"⚡ Đã dọn RAM cho PID {pid}: Tiết kiệm {saved_mb:.1f} MB!")
                    self.log_message(f"[PID {pid}] Đã thu hồi {saved_mb:.1f} MB RAM thành công!", "SUCCESS")
                else:
                    self.append_ram_log(f"⚠️ Không thể dọn RAM cho PID {pid}.")
                self.refresh_ram_tab_stats()
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _on_ram_manager_event(self, res: Dict[str, Any]):
        def _done():
            c_cnt = res.get("total_clients", 0)
            s_cnt = res.get("success_count", 0)
            saved = res.get("saved_mb", 0.0)
            pct = res.get("saved_pct", 0.0)
            if c_cnt > 0:
                msg = f"🎉 [Auto-Trim] Đã giải phóng {saved:.1f} MB ({pct:.0f}%) trên {s_cnt}/{c_cnt} client!"
                self.append_ram_log(msg)
                self.log_message(msg, "SUCCESS")
            if getattr(self, "active_tab", "") == "ram":
                self.refresh_ram_tab_stats()
        self.after(0, _done)

    def _safe_append_textbox(self, widget, text: str, max_lines: int = 1000, trim_lines: int = 150):
        """Chèn log an toàn vào Textbox và tự động cắt tỉa các dòng cũ để chống phình to RAM."""
        try:
            t_str = time.strftime("%H:%M:%S")
            widget.insert("end", f"[{t_str}] {text}\n")
            line_count = int(widget.index("end-1c").split(".")[0])
            if line_count > max_lines:
                widget.delete("1.0", f"{trim_lines}.0")
            widget.see("end")
        except Exception:
            pass

    def append_ram_log(self, text: str):
        if hasattr(self, "ram_log_txt"):
            self._safe_append_textbox(self.ram_log_txt, text)

    def _on_ram_auto_switch_toggled(self):
        if not self.ram_manager:
            return
        enabled = self.ram_auto_var.get()
        self.ram_manager.set_auto_trim(enabled)
        if enabled:
            mins = self.ram_manager.interval_seconds // 60
            self.append_ram_log(f"🟢 Đã BẬT Tự động dọn RAM định kỳ ({mins} phút/lần).")
            self.log_message(f"🟢 Đã BẬT Tự động dọn RAM định kỳ ({mins} phút/lần).", "INFO")
        else:
            self.append_ram_log("⏹ Đã TẮT Tự động dọn RAM định kỳ.")
            self.log_message("⏹ Đã TẮT Tự động dọn RAM định kỳ.", "INFO")

    def _on_ram_interval_changed(self, choice: str):
        if not self.ram_manager:
            return
        sec = self.ram_intervals_map.get(choice, 180)
        self.ram_manager.set_interval(sec)
        self.append_ram_log(f"⏱ Đã đặt khoảng thời gian dọn RAM: {choice}.")

    # ==========================================================================
    # TAB 5: TỰ ĐỘNG QUAY MOSS THE GAMBLER ĐA TÀI KHOẢN (MOSS MERCHANT GRID)
    # ==========================================================================
    MOSS_CAT_OPTIONS = [
        # === NHÓM QUAY BẰNG ZEN (TRỪ ZEN) ===
        ("[ZEN] 0: Kiếm (Swords - 1,000,000 Zen)", 0),
        ("[ZEN] 1: Chùy & Trượng (Maces/Scepters - 1,000,000 Zen)", 1),
        ("[ZEN] 2: Cung & Nỏ (Bows/Crossbows - 1,000,000 Zen)", 2),
        ("[ZEN] 3: Gậy Phép (Staffs - 1,000,000 Zen)", 3),
        ("[ZEN] 4: Khiên (Shields - 1,000,000 Zen)", 4),
        ("[ZEN] 5: Trang Sức & Khác (Accessories - 2,000,000 Zen)", 5),

        # === NHÓM QUAY BẰNG NGỌC (TRỪ NGỌC SOUL / BLESS / CHAOS) ===
        ("[NGỌC] 6: 2 Soul (Trừ 2 Ngọc Tâm Linh)", 6),
        ("[NGỌC] 7: 10 Soul (Trừ 10 Ngọc Tâm Linh)", 7),
        ("[NGỌC] 8: 2 Bless (Trừ 2 Ngọc Ước Nguyện)", 8),
        ("[NGỌC] 9: 10 Bless (Trừ 10 Ngọc Ước Nguyện)", 9),
        ("[NGỌC] 10: 2 Chaos (Trừ 2 Ngọc Hỗn Nguyên)", 10),
        ("[NGỌC] 11: 10 Chaos (Trừ 10 Ngọc Hỗn Nguyên)", 11),
    ]

    def get_moss_cat_name(self, cat_id: int) -> str:
        for name, cid in self.MOSS_CAT_OPTIONS:
            if cid == cat_id:
                return name
        return f"{cat_id}: Category {cat_id}"

    def get_moss_cat_id(self, cat_name: str) -> int:
        for name, cid in self.MOSS_CAT_OPTIONS:
            if name == cat_name:
                return cid
        try:
            text = str(cat_name)
            if ":" in text:
                left = text.split(":")[0]
                nums = [int(s) for s in left.replace("[", " ").replace("]", " ").split() if s.isdigit()]
                if nums:
                    return nums[-1]
            return int(text.strip())
        except Exception:
            return 0

    def refresh_moss_categories_from_game(self):
        """Đọc và đồng bộ danh sách Category thực tế của NPC Moss từ RAM Game, phân định rõ Trừ Zen / Trừ Ngọc."""
        found_cats = []
        for ctrl in self.controllers:
            if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine else None)
                if eng and eng.is_ready:
                    cats = eng.get_moss_categories()
                    if cats:
                        found_cats = cats
                        break
        if found_cats:
            new_opts = []
            for c in found_cats:
                cid = c.get("id", 0)
                cname = c.get("name", f"Category {cid}")
                req_cnt = c.get("reqCount", 0)
                curr = c.get("currency", "Zen")
                req_type = c.get("reqType", 0)

                # Phân định rõ trừ Zen hay trừ Ngọc
                if curr.lower() == "zen" or req_type in (7183, -1) or "zen" in cname.lower():
                    prefix = "[ZEN]"
                    cost_str = f"{req_cnt:,} Zen" if req_cnt > 0 else "Zen"
                else:
                    prefix = f"[NGỌC {curr.upper()}]"
                    cost_str = f"{req_cnt} {curr}" if req_cnt > 0 else curr

                desc = f"{prefix} {cid}: {cname} (Trừ: {cost_str})"
                new_opts.append((desc, cid))
            if new_opts:
                self.MOSS_CAT_OPTIONS = new_opts
                cat_names = [name for name, _ in self.MOSS_CAT_OPTIONS]
                if hasattr(self, "batch_moss_cat_combo"):
                    self.batch_moss_cat_combo.configure(values=cat_names)
                    self.batch_moss_cat_combo.set(cat_names[0])
                for s_i, el in self.moss_ui_elements.items():
                    combo = el.get("cat_combo")
                    if combo:
                        combo.configure(values=cat_names)
                self.append_moss_log(f"✅ Đã đọc thành công {len(new_opts)} danh mục cược Moss từ game:")
                for name, _ in self.MOSS_CAT_OPTIONS[:6]:
                    self.append_moss_log(f"   • {name}")
        else:
            self.append_moss_log("ℹ️ Chưa lấy được danh mục từ RAM game (bảng Moss chưa mở). Đã nạp danh mục chuẩn cả Zen và Ngọc.")

    # ==========================================================================
    # TAB 5: MOSS THE GAMBLER (MOSS MERCHANT AUTO ROLL) - TỐI GIẢN & ĐỘC LẬP TÀI KHOẢN
    # ==========================================================================
    def build_moss_view(self):
        """Xây dựng giao diện Tab Auto Moss Merchant (Modular MossView)."""
        view = MossView(self, self.panel_moss)
        view.build()

    def create_moss_slot_row(self, i: int):
        """Tạo 1 dòng cấu hình và điều khiển Moss cho Slot i theo phong cách Tối Giản (Cao 32px)."""
        ctrl = self.controllers[i - 1]
        is_en = getattr(ctrl, "moss_enabled", True)
        row_bg = "#131722" if is_en else "#0f1118"
        row_frame = ctk.CTkFrame(
            self.moss_scroll_frame,
            fg_color=row_bg,
            height=32,
            corner_radius=3,
            border_width=1,
            border_color="#1c2230"
        )
        row_frame.pack(fill="x", padx=2, pady=1)
        row_frame.pack_propagate(False)

        # Cột 0: STT & Checkbox chọn độc lập (45px)
        badge_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=45, height=24)
        badge_box.pack(side="left", padx=(4, 2))
        badge_box.pack_propagate(False)

        cb_enabled = ctk.CTkCheckBox(
            badge_box,
            text=f"{i:02d}",
            width=40,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f59e0b" if is_en else "#475569",
            fg_color="#d97706",
            hover_color="#b45309",
            command=lambda s=i: self.on_moss_slot_enabled_toggled(s)
        )
        if is_en:
            cb_enabled.select()
        else:
            cb_enabled.deselect()
        cb_enabled.pack(side="left", padx=1)
        no_lbl = cb_enabled # Tương thích code cũ

        # Cột 1: Nhân vật / PID (175px)
        char_disp = f"{ctrl.char_name} ({ctrl.assigned_pid})" if ctrl.assigned_pid else "Chưa gán"
        char_color = "#f8fafc" if (ctrl.assigned_pid and is_en) else "#64748b"
        char_lbl = ctk.CTkLabel(
            row_frame,
            text=char_disp,
            width=175,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold" if ctrl.assigned_pid else "normal"),
            text_color=char_color
        )
        char_lbl.pack(side="left", padx=(2, 2))

        # Cột 2: Vật phẩm quay (Category) (185px)
        cat_var = ctk.StringVar(value=self.get_moss_cat_name(ctrl.moss_category))
        cat_combo = ModernOptionMenu(
            row_frame,
            values=[name for name, _ in self.MOSS_CAT_OPTIONS],
            variable=cat_var,
            width=185,
            height=24,
            command=lambda val, s=i: self.on_moss_slot_category_changed(s, val),
            font=ctk.CTkFont(family="Segoe UI", size=10)
        )
        cat_combo.pack(side="left", padx=(2, 2))

        # Cột 3: Delay (ms) (60px)
        delay_entry = ctk.CTkEntry(
            row_frame,
            width=55,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#181c26",
            border_color="#2b3244",
            text_color="#f8fafc",
            justify="center"
        )
        delay_entry.insert(0, str(ctrl.moss_delay_ms))
        delay_entry.pack(side="left", padx=(2, 2))
        delay_entry.bind("<FocusOut>", lambda e, s=i: self.on_moss_slot_delay_changed(s))
        delay_entry.bind("<Return>", lambda e, s=i: self.on_moss_slot_delay_changed(s))

        # Cột 4: Đã quay (70px)
        rolls_lbl = ctk.CTkLabel(
            row_frame,
            text=f"{ctrl.moss_rolls_count} Lượt",
            width=70,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#10b981" if is_en else "#475569"
        )
        rolls_lbl.pack(side="left", padx=(2, 2))

        # Cột 5: Trạng thái (85px)
        if not is_en:
            st_text = "⛔ Bỏ qua"
            st_color = "#64748b"
        elif ctrl.assigned_pid:
            st_text = "Chờ"
            st_color = "#94a3b8"
        else:
            st_text = "Chưa gán"
            st_color = "#64748b"

        status_lbl = ctk.CTkLabel(
            row_frame,
            text=st_text,
            width=85,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=st_color
        )
        status_lbl.pack(side="left", padx=(2, 2))

        # Cột 6: Thao tác (145px cố định) - 3 nút: Auto, 1 Lần, NPC
        action_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=145, height=24)
        action_box.pack(side="left", padx=(2, 2))
        action_box.pack_propagate(False)

        btn_toggle = ctk.CTkButton(
            action_box,
            text="▶ Auto",
            width=48,
            height=22,
            corner_radius=3,
            fg_color="#059669",
            hover_color="#047857",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=lambda s=i: self.toggle_moss_slot_auto(s)
        )
        btn_toggle.pack(side="left", padx=1)

        btn_once = ctk.CTkButton(
            action_box,
            text="🎲 1 Lần",
            width=48,
            height=22,
            corner_radius=3,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#334155",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=lambda s=i: ctrl.roll_moss_once()
        )
        btn_once.pack(side="left", padx=1)

        btn_open = ctk.CTkButton(
            action_box,
            text="🚪 NPC",
            width=42,
            height=22,
            corner_radius=3,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#f59e0b",
            text_color="#fbbf24",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=lambda s=i: ctrl.open_moss_npc()
        )
        btn_open.pack(side="left", padx=1)
        btn_drop = None

        # Menu chuột phải tiện ích đầy đủ
        import tkinter as tk
        def _show_moss_ctx(event, s_idx):
            try:
                ctrl_item = self.controllers[s_idx - 1]
                m_menu = tk.Menu(self, tearoff=0, bg="#181c26", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff")
                m_menu.add_command(label=f"🗑️ Ném đồ rác tại chỗ (Slot {s_idx:02d})", command=lambda: ctrl_item.clean_moss_inventory(run_in_thread=True))
                m_menu.add_command(label=f"💰 Bán đồ rác tại NPC Silvia (Slot {s_idx:02d})", command=lambda: ctrl_item.sell_moss_inventory())
                m_menu.add_separator()
                m_menu.add_command(label="🚪 Mở bảng Moss NPC", command=lambda: ctrl_item.open_moss_npc())
                m_menu.add_command(label="🚪 Đóng bảng Moss NPC", command=lambda: ctrl_item.close_moss_dialog())
                m_menu.add_command(label="🔓 Mở khóa kẹt thùng đồ & Moss", command=lambda: ctrl_item.unlock_and_close_inventory())
                m_menu.add_command(label="🚶 Chạy về NPC Moss (22, 225)", command=lambda: ctrl_item.move_to_moss_elbeland())
                m_menu.tk_popup(event.x_root, event.y_root)
            except Exception:
                pass

        for _mw in (row_frame, badge_box, char_lbl, rolls_lbl, status_lbl):
            _mw.bind("<Button-3>", lambda e, s=i: _show_moss_ctx(e, s))

        # Lưu UI cache
        self.moss_ui_elements[i] = {
            "row_frame": row_frame,
            "cb_enabled": cb_enabled,
            "no_lbl": no_lbl,
            "char_lbl": char_lbl,
            "cat_var": cat_var,
            "cat_combo": cat_combo,
            "delay_entry": delay_entry,
            "rolls_lbl": rolls_lbl,
            "status_lbl": status_lbl,
            "btn_toggle": btn_toggle,
            "btn_open": btn_open,
            "btn_once": btn_once,
            "btn_drop": btn_drop,
        }

    def on_moss_slot_enabled_toggled(self, slot_idx: int):
        """Xử lý khi người dùng bật/tắt checkbox tham gia Moss của từng slot."""
        if slot_idx < 1 or slot_idx > len(self.controllers):
            return
        ctrl = self.controllers[slot_idx - 1]
        el = self.moss_ui_elements.get(slot_idx)
        if el and el.get("cb_enabled"):
            val = bool(el["cb_enabled"].get())
            ctrl.moss_enabled = val
            self.update_moss_row_visuals(slot_idx)
            self.update_moss_selected_badge()
            self.on_toggle_moss_auto_schedule()
            action_txt = "BẬT quay Moss" if val else "BỎ QUA (Chỉ chạy Auto Train)"
            self.append_moss_log(f"[Slot {slot_idx:02d} - {ctrl.char_name}] -> {action_txt}.")

    def select_all_moss_slots(self):
        """Chọn tất cả tài khoản tham gia Moss."""
        for ctrl in self.controllers:
            ctrl.moss_enabled = True
            el = self.moss_ui_elements.get(ctrl.slot_idx)
            if el and el.get("cb_enabled"):
                el["cb_enabled"].select()
            self.update_moss_row_visuals(ctrl.slot_idx)
        self.update_moss_selected_badge()
        self.on_toggle_moss_auto_schedule()
        self.append_moss_log("✅ Đã chọn TẤT CẢ tài khoản tham gia Auto Moss.")

    def deselect_all_moss_slots(self):
        """Bỏ chọn toàn bộ tài khoản quay Moss."""
        for ctrl in self.controllers:
            ctrl.moss_enabled = False
            el = self.moss_ui_elements.get(ctrl.slot_idx)
            if el and el.get("cb_enabled"):
                el["cb_enabled"].deselect()
            self.update_moss_row_visuals(ctrl.slot_idx)
        self.update_moss_selected_badge()
        self.on_toggle_moss_auto_schedule()
        self.append_moss_log("⬜ Đã BỎ CHỌN toàn bộ tài khoản quay Moss (Các tài khoản sẽ chỉ chạy Auto Train).")

    def update_moss_selected_badge(self):
        """Cập nhật nhãn số lượng tài khoản đã chọn quay Moss trên Toolbar."""
        if hasattr(self, "lbl_moss_count_badge") and self.lbl_moss_count_badge:
            total = len(self.controllers)
            sel = sum(1 for c in self.controllers if getattr(c, "moss_enabled", True))
            self.lbl_moss_count_badge.configure(
                text=f"Quay Moss: {sel}/{total}",
                text_color="#f59e0b" if sel > 0 else "#64748b"
            )

    def update_moss_row_visuals(self, slot_idx: int):
        """Cập nhật màu sắc và trạng thái trực quan khi bật/tắt checkbox slot Moss."""
        el = self.moss_ui_elements.get(slot_idx)
        if not el:
            return
        ctrl = self.controllers[slot_idx - 1]
        is_en = getattr(ctrl, "moss_enabled", True)
        if is_en:
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color="#141722")
            if el.get("no_lbl"):
                el["no_lbl"].configure(text_color="#94a3b8")
            if el.get("char_lbl"):
                el["char_lbl"].configure(text_color="#f8fafc" if ctrl.assigned_pid else "#64748b")
            if el.get("status_lbl"):
                cur_text = el["status_lbl"].cget("text")
                if "Bỏ qua" in cur_text:
                    el["status_lbl"].configure(text="Chờ" if ctrl.assigned_pid else "Chưa gán", text_color="#94a3b8" if ctrl.assigned_pid else "#64748b")
        else:
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color="#0f1118")
            if el.get("no_lbl"):
                el["no_lbl"].configure(text_color="#475569")
            if el.get("char_lbl"):
                el["char_lbl"].configure(text_color="#475569")
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")

    def on_moss_slot_category_changed(self, slot_idx: int, cat_name: str):
        ctrl = self.controllers[slot_idx - 1]
        cid = self.get_moss_cat_id(cat_name)
        ctrl.moss_category = cid
        ConfigPersistenceManager.save_moss_config(slot_idx, cid, ctrl.moss_delay_ms, ctrl.moss_max_rolls, ctrl.moss_auto_clean)
        self.append_moss_log(f"[Slot {slot_idx:02d}] Cập nhật cấu hình quay: {cat_name}.")

    def on_moss_slot_delay_changed(self, slot_idx: int):
        el = self.moss_ui_elements.get(slot_idx)
        if not el or not el.get("delay_entry"):
            return
        ctrl = self.controllers[slot_idx - 1]
        try:
            val = max(400, int(el["delay_entry"].get().strip()))
            ctrl.moss_delay_ms = val
            ConfigPersistenceManager.save_moss_config(slot_idx, ctrl.moss_category, val, ctrl.moss_max_rolls, ctrl.moss_auto_clean)
        except Exception:
            el["delay_entry"].delete(0, "end")
            el["delay_entry"].insert(0, str(ctrl.moss_delay_ms))

    def on_toggle_global_moss_clean(self):
        """Bật / Tắt tính năng tự động dọn rác hòm đồ cho toàn bộ các Slot."""
        is_clean = bool(self.batch_moss_clean_cb.get()) if hasattr(self, "batch_moss_clean_cb") else True
        for i, ctrl in enumerate(self.controllers, 1):
            ctrl.moss_auto_clean = is_clean
            ConfigPersistenceManager.save_moss_config(i, ctrl.moss_category, ctrl.moss_delay_ms, ctrl.moss_max_rolls, is_clean)
        status_txt = "BẬT" if is_clean else "TẮT"
        self.append_moss_log(f"🧹 Đã {status_txt} tính năng Tự Động Dọn Rác cho tất cả các Slot!")

    def clean_all_moss_inventories(self):
        """Tự động ném tại chỗ toàn bộ vật phẩm rác trong hòm đồ cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _cleaner():
            count_acc = 0
            total_cleaned = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    try:
                        cleaned = ctrl.clean_moss_inventory(method="trash", category=-1, run_in_thread=False)
                        total_cleaned += (cleaned or 0)
                        count_acc += 1
                    except Exception as e:
                        self.append_moss_log(f"[Slot {ctrl.slot_idx:02d}] ❌ Lỗi ném rác tại chỗ: {e}")
                    time.sleep(0.1)
            if count_acc > 0:
                self.after(0, lambda: self.append_moss_log(
                    f"🗑️ Đã hoàn tất ném đồ tại chỗ cho {count_acc} tài khoản: Đã ném {total_cleaned} món đồ rác (Bảo tồn đồ Divine/Rồng/Exc/Socket/Set/May Mắn/Ngọc/Đồ >= +7)!"
                ))
            else:
                self.after(0, lambda: self.append_moss_log("⚠️ Không có tài khoản đã chọn nào đang kết nối để ném rác!"))
        threading.Thread(target=_cleaner, daemon=True).start()

    def sell_all_moss_inventories(self):
        """Kích hoạt bán đồ tại Silvia Elbeland cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _seller():
            count_acc = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    try:
                        ctrl.sell_moss_inventory()
                        count_acc += 1
                    except Exception as e:
                        self.append_moss_log(f"[Slot {ctrl.slot_idx:02d}] ❌ Lỗi bán đồ: {e}")
                    time.sleep(0.5)
            if count_acc > 0:
                self.after(0, lambda c=count_acc: self.append_moss_log(
                    f"💰 Đã kích hoạt tiến trình bán đồ tại Silvia cho {c} tài khoản đã chọn!"
                ))
            else:
                self.after(0, lambda: self.append_moss_log("⚠️ Không có tài khoản đã chọn nào đang kết nối!"))
        threading.Thread(target=_seller, daemon=True).start()

    def close_all_moss_dialogs(self):
        """Đóng bảng NPC Moss trên các tài khoản ĐÃ TÍCH CHỌN."""
        def _closer():
            count = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    try:
                        ctrl.close_moss_dialog()
                        count += 1
                        time.sleep(0.05)
                    except Exception:
                        pass
            if count > 0:
                self.after(0, lambda c=count: self.append_moss_log(
                    f"🚪 Đã đóng bảng NPC Moss cho {c} tài khoản đã chọn!"
                ))
            else:
                self.after(0, lambda: self.append_moss_log("⚠️ Không có tài khoản đã chọn nào đang kết nối để đóng Moss!"))
        threading.Thread(target=_closer, daemon=True).start()

    def unlock_and_close_all_inventories(self):
        """Mở khóa và giải phóng thùng đồ cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _unlocker():
            count = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    try:
                        ctrl.unlock_and_close_inventory()
                        count += 1
                        time.sleep(0.05)
                    except Exception:
                        pass
            if count > 0:
                self.after(0, lambda c=count: self.append_moss_log(
                    f"🔓 Đã mở khóa và giải phóng thùng đồ cho {c} tài khoản đã chọn!"
                ))
        threading.Thread(target=_unlocker, daemon=True).start()

    def update_moss_slot_ui_state(self, slot_idx: int, is_running: bool):
        el = self.moss_ui_elements.get(slot_idx)
        if not el:
            return
        ctrl = self.controllers[slot_idx - 1]
        if not getattr(ctrl, "moss_enabled", True):
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")
            return
        if el.get("btn_toggle"):
            if is_running:
                el["btn_toggle"].configure(text="⏹️ Dừng", fg_color="#dc2626", hover_color="#b91c1c")
            else:
                el["btn_toggle"].configure(text="▶️ Auto", fg_color="#059669", hover_color="#047857")
        if el.get("status_lbl"):
            if is_running:
                el["status_lbl"].configure(text="Đang quay...", text_color="#10b981")
            else:
                el["status_lbl"].configure(text="Đã dừng" if ctrl.assigned_pid else "Chưa gán", text_color="#94a3b8")

    def update_moss_slot_rolls(self, slot_idx: int, count: int):
        el = self.moss_ui_elements.get(slot_idx)
        if el and el.get("rolls_lbl"):
            el["rolls_lbl"].configure(text=f"{count} Lượt")

    def update_moss_slot_telemetry(self, slot_idx: int, name: str, pid: Optional[int]):
        moss_elems = getattr(self, "moss_ui_elements", {})
        el = moss_elems.get(slot_idx) if isinstance(moss_elems, dict) else None
        if not el or not el.get("char_lbl"):
            return
        ctrl = self.controllers[slot_idx - 1] if 1 <= slot_idx <= len(self.controllers) else None
        is_en = getattr(ctrl, "moss_enabled", True) if ctrl else True
        is_running = getattr(ctrl, "moss_running", False) if ctrl else False

        cache = getattr(self, "_moss_ui_cache", {}).setdefault(slot_idx, {})
        new_state = (name, pid, is_en, is_running)
        if cache.get("state") == new_state:
            return
        cache["state"] = new_state

        f_bold = getattr(self, "font_segoe_11_bold", None)
        f_norm = getattr(self, "font_segoe_11_normal", None)

        if pid:
            disp = f"{name} ({pid})" if name and name != "---" else f"MEGAMU ({pid})"
            el["char_lbl"].configure(
                text=disp,
                text_color="#f8fafc" if is_en else "#64748b",
                font=f_bold if is_en else f_norm
            )
            if el.get("status_lbl"):
                if not is_en:
                    el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")
                elif not is_running:
                    el["status_lbl"].configure(text="Chờ", text_color="#94a3b8")
        else:
            el["char_lbl"].configure(
                text="Chưa gán",
                text_color="#64748b",
                font=f_norm
            )
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua" if not is_en else "Chưa gán", text_color="#64748b")

    def toggle_moss_slot_auto(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        if ctrl.moss_running:
            ctrl.stop_moss()
        else:
            ctrl.start_moss()

    def apply_batch_moss_category(self):
        """Gán nhanh 1 danh mục vật phẩm cho các Slot ĐÃ TÍCH CHỌN và lưu file."""
        chosen = self.batch_moss_cat_combo.get()
        cid = self.get_moss_cat_id(chosen)
        cnt = 0
        for i, ctrl in enumerate(self.controllers, 1):
            if not getattr(ctrl, "moss_enabled", True):
                continue
            ctrl.moss_category = cid
            el = self.moss_ui_elements.get(i)
            if el and el.get("cat_var"):
                el["cat_var"].set(chosen)
            ConfigPersistenceManager.save_moss_config(i, cid, ctrl.moss_delay_ms, ctrl.moss_max_rolls, ctrl.moss_auto_clean)
            cnt += 1
        self.append_moss_log(f"📋 Đã gán cấu hình quay '{chosen}' cho {cnt} Slot đã chọn!")

    def apply_batch_moss_delay(self):
        """Gán nhanh delay cho các Slot ĐÃ TÍCH CHỌN và lưu file."""
        try:
            val = max(400, int(self.batch_moss_delay_entry.get().strip()))
        except Exception:
            val = 1000
        cnt = 0
        for i, ctrl in enumerate(self.controllers, 1):
            if not getattr(ctrl, "moss_enabled", True):
                continue
            ctrl.moss_delay_ms = val
            el = self.moss_ui_elements.get(i)
            if el and el.get("delay_entry"):
                el["delay_entry"].delete(0, "end")
                el["delay_entry"].insert(0, str(val))
            ConfigPersistenceManager.save_moss_config(i, ctrl.moss_category, val, ctrl.moss_max_rolls, ctrl.moss_auto_clean)
            cnt += 1
        self.append_moss_log(f"⏱ Đã đặt delay {val}ms cho {cnt} Slot đã chọn!")

    def start_all_moss_auto(self):
        """Kích hoạt Auto Quay Moss cho các tài khoản ĐÃ TÍCH CHỌN đang kết nối."""
        def _batch_runner():
            started = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ok = ctrl.start_moss()
                    if ok:
                        started += 1
                        time.sleep(0.08)
            if started > 0:
                self.after(0, lambda: self.append_moss_log(f"🚀 Đã kích hoạt Auto Moss cho {started} tài khoản đã chọn!"))
            else:
                self.after(0, lambda: self.append_moss_log("⚠️ Không có tài khoản đã chọn nào đang kết nối để chạy Auto Moss!"))
        threading.Thread(target=_batch_runner, daemon=True).start()

    def stop_all_moss_auto(self):
        """Dừng Auto Quay Moss trên các tài khoản."""
        for ctrl in self.controllers:
            ctrl.stop_moss()
        self.append_moss_log("⏹️ Đã dừng Auto Moss trên toàn bộ tài khoản.")

    def open_all_moss_npc(self):
        """Gửi lệnh mở giao diện NPC Moss cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _opener():
            cnt = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ctrl.open_moss_npc()
                    cnt += 1
                    time.sleep(0.05)
            self.after(0, lambda: self.append_moss_log(f"🚪 Đã gửi lệnh mở NPC Moss cho {cnt} tài khoản đã chọn!"))
        threading.Thread(target=_opener, daemon=True).start()

    def move_all_to_moss_elbeland(self):
        """Di chuyển các tài khoản ĐÃ TÍCH CHỌN về Elbeland tới NPC Moss Merchant (22, 225)."""
        def _mover():
            cnt = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "moss_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ctrl.move_to_moss_elbeland()
                    cnt += 1
                    time.sleep(0.2)
            self.after(0, lambda: self.append_moss_log(f"🚶 Đã gửi lệnh di chuyển tới NPC Moss cho {cnt} tài khoản đã chọn!"))
        threading.Thread(target=_mover, daemon=True).start()

    def append_moss_log(self, text: str):
        if hasattr(self, "moss_log_txt"):
            self._safe_append_textbox(self.moss_log_txt, text)

    def clear_moss_log(self):
        if hasattr(self, "moss_log_txt"):
            self.moss_log_txt.delete("1.0", "end")

    def on_toggle_moss_auto_schedule(self):
        """Lưu trạng thái cài đặt Lịch Trình Tự Động Quay Moss kèm danh sách selected_slots."""
        is_auto = bool(self.cb_moss_auto_schedule.get()) if hasattr(self, "cb_moss_auto_schedule") else True
        is_move = bool(self.cb_moss_auto_move_before.get()) if hasattr(self, "cb_moss_auto_move_before") else True
        selected_slots = [c.slot_idx for c in self.controllers if getattr(c, "moss_enabled", True)]
        ConfigPersistenceManager.save_moss_schedule_config(is_auto, is_move, selected_slots=selected_slots)
        st = "BẬT" if is_auto else "TẮT"
        mv = "BẬT" if is_move else "TẮT"
        self.append_moss_log(f"⏰ [LỊCH MOSS] Đã lưu: Tự động quay [{st}] | Tài khoản quay: {len(selected_slots)}/{len(self.controllers)} | Tới NPC [{mv}].")

    def _periodic_moss_scheduler(self):
        """Vòng lặp định kỳ 1 giây: Tính toán đếm ngược và tự động kích hoạt quay theo lịch (00:15, 06:15, 12:15, 18:15) - Mở trong 5 phút."""
        if not self.running:
            return

        try:
            from datetime import datetime, timedelta
            now = datetime.now()

            # Các mốc giờ mở Moss hàng ngày: 00:15, 06:15, 12:15, 18:15 (mỗi đợt kéo dài đúng 5 phút = 300 giây)
            schedule_slots = [(0, 15), (6, 15), (12, 15), (18, 15)]
            MOSS_DURATION = 300 # 5 phút

            # 1. Kiểm tra xem hiện tại có đang nằm trong khung 5 phút của bất kỳ đợt nào không
            active_slot = None
            for h, m in schedule_slots:
                for day_offset in [0, -1]:
                    st = (now + timedelta(days=day_offset)).replace(hour=h, minute=m, second=0, microsecond=0)
                    en = st + timedelta(seconds=MOSS_DURATION)
                    if st <= now < en:
                        active_slot = (st, en)
                        break
                if active_slot:
                    break

            if active_slot:
                start_dt, end_dt = active_slot
                rem_sec = int((end_dt - now).total_seconds())
                rem_m = rem_sec // 60
                rem_s = rem_sec % 60

                # Đang trong 5 phút vàng của sự kiện Moss
                if getattr(self, "active_tab", "") == "moss":
                    if hasattr(self, "lbl_moss_next_event") and self.lbl_moss_next_event:
                        self.lbl_moss_next_event.configure(text=f"Đợt này: {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
                    if hasattr(self, "lbl_moss_countdown") and self.lbl_moss_countdown:
                        self.lbl_moss_countdown.configure(text=f"🔥 ĐANG MỞ: còn {rem_m:02d}:{rem_s:02d}", text_color="#ef4444")
                    if hasattr(self, "lbl_moss_sched_status") and self.lbl_moss_sched_status:
                        self.lbl_moss_sched_status.configure(text="🎲 ĐANG QUAY MOSS", text_color="#38bdf8")

                # Tự động bắt đầu quay khi vừa bước vào đợt mở (ngay giây đầu tiên)
                if hasattr(self, "cb_moss_auto_schedule") and self.cb_moss_auto_schedule.get():
                    trigger_key = start_dt.strftime("%Y-%m-%d %H:%M") + "_roll"
                    if getattr(self, "_last_moss_trigger_key", None) != trigger_key:
                        self._last_moss_trigger_key = trigger_key
                        self.append_moss_log(
                            f"🎰 [LỊCH MOSS] ĐÃ ĐẾN GIỜ MOSS ({start_dt.strftime('%H:%M')})! Mở trong 5 phút -> Tự động bắt đầu Auto Quay cho tất cả tài khoản..."
                        )
                        self.start_all_moss_auto()

            else:
                # 2. Đang ngoài khung giờ mở: Tìm mốc giờ tiếp theo gần nhất
                next_start = None
                for h, m in schedule_slots:
                    cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    # Nếu mốc này (kèm 5 phút hoạt động) đã kết thúc thì chuyển sang ngày mai
                    if cand + timedelta(seconds=MOSS_DURATION) <= now:
                        cand += timedelta(days=1)
                    if next_start is None or cand < next_start:
                        next_start = cand

                diff = int((next_start - now).total_seconds())
                next_str = next_start.strftime("%H:%M")

                # Kiểm tra nếu vừa kết thúc đợt mở (trong vòng 5 giây sau khi hết 5 phút) -> Tự động dừng quay an toàn
                if hasattr(self, "cb_moss_auto_schedule") and self.cb_moss_auto_schedule.get():
                    for h, m in schedule_slots:
                        for day_offset in [0, -1]:
                            prev_st = (now + timedelta(days=day_offset)).replace(hour=h, minute=m, second=0, microsecond=0)
                            prev_en = prev_st + timedelta(seconds=MOSS_DURATION)
                            time_since_end = (now - prev_en).total_seconds()
                            if 0 <= time_since_end <= 5:
                                stop_key = prev_en.strftime("%Y-%m-%d %H:%M") + "_stop"
                                if getattr(self, "_last_moss_stop_key", None) != stop_key:
                                    self._last_moss_stop_key = stop_key
                                    self.append_moss_log(
                                        f"🛑 [LỊCH MOSS] ĐÃ HẾT 5 PHÚT MỞ MOSS ({prev_st.strftime('%H:%M')} - {prev_en.strftime('%H:%M')})! Tự động dừng quay tất cả tài khoản để bảo toàn Zen và hòm đồ."
                                    )
                                    self.stop_all_moss_auto()

                # Cập nhật hiển thị Đợt tới & Đếm ngược (chỉ khi đang mở Tab Moss)
                if getattr(self, "active_tab", "") == "moss":
                    if hasattr(self, "lbl_moss_next_event") and self.lbl_moss_next_event:
                        self.lbl_moss_next_event.configure(text=f"Đợt tới: {next_str} (mở 5p)")

                    hh = diff // 3600
                    mm = (diff % 3600) // 60
                    ss = diff % 60
                    countdown_str = f"⏳ Còn: {hh:02d}:{mm:02d}:{ss:02d}"

                    if hasattr(self, "lbl_moss_countdown") and self.lbl_moss_countdown:
                        if diff <= 60:
                            self.lbl_moss_countdown.configure(text=countdown_str, text_color="#ef4444")
                        elif diff <= 300:
                            self.lbl_moss_countdown.configure(text=countdown_str, text_color="#f59e0b")
                        else:
                            self.lbl_moss_countdown.configure(text=countdown_str, text_color="#10b981")

                    if hasattr(self, "lbl_moss_sched_status") and self.lbl_moss_sched_status:
                        if diff <= 10:
                            self.lbl_moss_sched_status.configure(text="🔥 CHUẨN BỊ QUAY!", text_color="#f87171")
                        elif diff <= 60:
                            self.lbl_moss_sched_status.configure(text="⚡ Sắp mở", text_color="#facc15")
                        else:
                            self.lbl_moss_sched_status.configure(text="🟢 Đang chờ", text_color="#94a3b8")

                # Tự động điều hướng nhân vật tới NPC Moss trước 15 giây
                if hasattr(self, "cb_moss_auto_move_before") and self.cb_moss_auto_move_before.get():
                    if 10 <= diff <= 15:
                        move_key = next_start.strftime("%Y-%m-%d %H:%M") + "_move"
                        if getattr(self, "_last_moss_move_key", None) != move_key:
                            self._last_moss_move_key = move_key
                            self.append_moss_log(
                                f"🚶 [LỊCH MOSS] Còn {diff}s tới giờ mở Moss ({next_str})! Đang điều hướng các nhân vật ĐÃ CHỌN tới tọa độ NPC Moss (Elbeland 22, 225)..."
                            )
                            self.move_all_to_moss_elbeland()

        except Exception as e:
            log_thread_exception(
                source="DashboardApp._periodic_moss_scheduler",
                exc=e,
                thread_name="MossScheduler",
                details="Lỗi trong chu kỳ lập lịch Moss Merchant"
            )

        self.after(1000, self._periodic_moss_scheduler)


    # ==========================================================================
    # TAB 6: DOUBLE GOER (MIRROR OF DIMENSIONS) - THIẾT KẾ TỐI GIẢN & ĐỘC LẬP TÀI KHOẢN
    # ==========================================================================
    def build_mirror_view(self):
        """Xây dựng giao diện Tab Auto Double Goer (Modular MirrorView)."""
        view = MirrorView(self, self.panel_mirror)
        view.build()

    def get_mirror_snipe_delay(self) -> int:
        try:
            return max(35, min(1000, int(self.mirror_snipe_delay_entry.get().strip())))
        except Exception:
            return 50

    def get_mirror_snipe_dur(self) -> float:
        try:
            return max(3.0, min(120.0, float(self.mirror_snipe_dur_entry.get().strip())))
        except Exception:
            return 15.0

    def get_mirror_prefire_sec(self) -> float:
        try:
            return max(0.0, min(30.0, float(self.mirror_prefire_sec_entry.get().strip())))
        except Exception:
            return 1.2

    def create_mirror_slot_row(self, i: int):
        """Tạo 1 dòng điều khiển Double Goer cho Slot i theo phong cách Tối Giản (Cao 30px, 607px)."""
        ctrl = self.controllers[i - 1]
        is_en = getattr(ctrl, "mirror_enabled", True)
        row_bg = "#131722" if is_en else "#0f1118"
        row_frame = ctk.CTkFrame(
            self.mirror_scroll_frame,
            fg_color=row_bg,
            height=30,
            corner_radius=3,
            border_width=1,
            border_color="#1c2230"
        )
        row_frame.pack(fill="x", padx=2, pady=1)
        row_frame.pack_propagate(False)

        # Cột 0: STT & Checkbox chọn độc lập (42px)
        badge_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=42, height=22)
        badge_box.pack(side="left", padx=(3, 2))
        badge_box.pack_propagate(False)

        cb_enabled = ctk.CTkCheckBox(
            badge_box,
            text=f"{i:02d}",
            width=38,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#c084fc" if is_en else "#475569",
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=lambda s=i: self.on_mirror_slot_enabled_toggled(s)
        )
        if is_en:
            cb_enabled.select()
        else:
            cb_enabled.deselect()
        cb_enabled.pack(side="left", padx=1)
        no_lbl = cb_enabled

        # Cột 1: Nhân vật / PID (150px)
        char_disp = f"{ctrl.char_name} ({ctrl.assigned_pid})" if ctrl.assigned_pid else "Chưa gán"
        char_color = "#f8fafc" if (ctrl.assigned_pid and is_en) else "#64748b"
        char_lbl = ctk.CTkLabel(
            row_frame,
            text=char_disp,
            width=150,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold" if ctrl.assigned_pid else "normal"),
            text_color=char_color
        )
        char_lbl.pack(side="left", padx=(2, 2))

        # Cột 2: Tọa độ (75px)
        coords_disp = ctrl.coords if ctrl.coords else "--, --"
        coords_lbl = ctk.CTkLabel(
            row_frame,
            text=coords_disp,
            width=75,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8" if is_en else "#475569"
        )
        coords_lbl.pack(side="left", padx=(2, 2))

        # Cột 3: Vé Mirror (90px)
        ticket_lbl = ctk.CTkLabel(
            row_frame,
            text="--",
            width=90,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94a3b8" if is_en else "#475569"
        )
        ticket_lbl.pack(side="left", padx=(2, 2))

        # Cột 4: Trạng thái (105px)
        if not is_en:
            st_text = "⛔ Bỏ qua"
            st_color = "#64748b"
        elif ctrl.assigned_pid:
            st_text = "Sẵn sàng"
            st_color = "#10b981"
        else:
            st_text = "Chưa kết nối"
            st_color = "#94a3b8"

        status_lbl = ctk.CTkLabel(
            row_frame,
            text=st_text,
            width=105,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=st_color
        )
        status_lbl.pack(side="left", padx=(2, 2))

        # Cột 5: Thao tác (Chỉ giữ 1 icon Vào cửa để kiểm tra trạng thái slot) (60px)
        action_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=60, height=24)
        action_box.pack(side="left", padx=(2, 2))
        action_box.pack_propagate(False)

        btn_enter = ctk.CTkButton(
            action_box,
            text="",
            image=UiIconFactory.get("door", color="#c084fc", size=(13, 13)),
            width=28,
            height=22,
            corner_radius=3,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#7c3aed",
            command=lambda s=i: self.controllers[s - 1].enter_mirror()
        )
        btn_enter.pack(expand=True)
        add_tooltip(btn_enter, f"🚪 Vào cửa Double Goer để kiểm tra trạng thái Slot {i:02d}")

        # Lưu UI cache
        self.mirror_ui_elements[i] = {
            "row_frame": row_frame,
            "cb_enabled": cb_enabled,
            "no_lbl": no_lbl,
            "char_lbl": char_lbl,
            "coords_lbl": coords_lbl,
            "ticket_lbl": ticket_lbl,
            "status_lbl": status_lbl,
            "btn_enter": btn_enter,
        }

    def on_mirror_slot_enabled_toggled(self, slot_idx: int):
        """Xử lý khi người dùng bật/tắt checkbox tham gia Mirror của từng slot."""
        if slot_idx < 1 or slot_idx > len(self.controllers):
            return
        ctrl = self.controllers[slot_idx - 1]
        el = self.mirror_ui_elements.get(slot_idx)
        if el and el.get("cb_enabled"):
            val = bool(el["cb_enabled"].get())
            ctrl.mirror_enabled = val
            self.update_mirror_row_visuals(slot_idx)
            self.update_mirror_selected_badge()
            self.on_toggle_mirror_auto_schedule()
            action_txt = "BẬT đi Mirror" if val else "BỎ QUA (Chỉ chạy Auto Train)"
            self.append_mirror_log(f"[Slot {slot_idx:02d} - {ctrl.char_name}] -> {action_txt}.")

    def select_all_mirror_slots(self):
        """Chọn tất cả tài khoản tham gia Mirror."""
        for ctrl in self.controllers:
            ctrl.mirror_enabled = True
            el = self.mirror_ui_elements.get(ctrl.slot_idx)
            if el and el.get("cb_enabled"):
                el["cb_enabled"].select()
            self.update_mirror_row_visuals(ctrl.slot_idx)
        self.update_mirror_selected_badge()
        self.on_toggle_mirror_auto_schedule()
        self.append_mirror_log("✅ Đã chọn TẤT CẢ tài khoản tham gia Double Goer (Mirror).")

    def deselect_all_mirror_slots(self):
        """Bỏ chọn toàn bộ tài khoản đi Mirror."""
        for ctrl in self.controllers:
            ctrl.mirror_enabled = False
            el = self.mirror_ui_elements.get(ctrl.slot_idx)
            if el and el.get("cb_enabled"):
                el["cb_enabled"].deselect()
            self.update_mirror_row_visuals(ctrl.slot_idx)
        self.update_mirror_selected_badge()
        self.on_toggle_mirror_auto_schedule()
        self.append_mirror_log("⬜ Đã BỎ CHỌN toàn bộ tài khoản đi Mirror (Các tài khoản sẽ chỉ chạy Auto Train).")

    def update_mirror_selected_badge(self):
        """Cập nhật nhãn số lượng tài khoản đã chọn đi Mirror trên Toolbar."""
        if hasattr(self, "lbl_mirror_count_badge") and self.lbl_mirror_count_badge:
            total = len(self.controllers)
            sel = sum(1 for c in self.controllers if getattr(c, "mirror_enabled", True))
            self.lbl_mirror_count_badge.configure(
                text=f"{sel}/{total}",
                text_color="#2dd4bf" if sel > 0 else "#64748b"
            )

    def update_mirror_row_visuals(self, slot_idx: int):
        """Cập nhật màu sắc và trạng thái trực quan khi bật/tắt checkbox slot."""
        el = self.mirror_ui_elements.get(slot_idx)
        if not el:
            return
        ctrl = self.controllers[slot_idx - 1]
        is_en = getattr(ctrl, "mirror_enabled", True)
        if is_en:
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color="#131722")
            if el.get("no_lbl"):
                el["no_lbl"].configure(text_color="#c084fc")
            if el.get("char_lbl"):
                el["char_lbl"].configure(text_color="#f8fafc" if ctrl.assigned_pid else "#64748b")
            if el.get("coords_lbl"):
                el["coords_lbl"].configure(text_color="#38bdf8")
            if el.get("status_lbl"):
                cur_text = el["status_lbl"].cget("text")
                if "Bỏ qua" in cur_text:
                    el["status_lbl"].configure(text="Sẵn sàng" if ctrl.assigned_pid else "Chưa gán", text_color="#10b981" if ctrl.assigned_pid else "#94a3b8")
        else:
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color="#0f1118")
            if el.get("no_lbl"):
                el["no_lbl"].configure(text_color="#475569")
            if el.get("char_lbl"):
                el["char_lbl"].configure(text_color="#475569")
            if el.get("coords_lbl"):
                el["coords_lbl"].configure(text_color="#475569")
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")

    def refresh_mirror_slot_ticket_display(self, slot_idx: int):
        """Tự động quét và cập nhật hiển thị vé cho Slot i lên giao diện."""
        if slot_idx < 1 or slot_idx > len(self.controllers):
            return
        ctrl = self.controllers[slot_idx - 1]
        el = self.mirror_ui_elements.get(slot_idx)
        if not el:
            return
        if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
            if el.get("ticket_lbl"):
                el["ticket_lbl"].configure(text="--", text_color="#64748b")
            return

        def _bg_check():
            try:
                t_info = ctrl.check_mirror_ticket()
                def _update():
                    curr_el = self.mirror_ui_elements.get(slot_idx)
                    if not curr_el or not curr_el.get("ticket_lbl"):
                        return
                    if t_info.get("hasTicket"):
                        slots = t_info.get("slots", [])
                        cnt = t_info.get("count", len(slots))
                        details = t_info.get("details", [])
                        main_cnt = sum(1 for d in details if not d.get("isExtended"))
                        ext_cnt = sum(1 for d in details if d.get("isExtended"))
                        if ext_cnt > 0 and main_cnt > 0:
                            s_desc = f"{cnt} vé (C:{main_cnt}|P:{ext_cnt})"
                        elif ext_cnt > 0:
                            s_desc = f"{cnt} vé (Ba lô phụ)"
                        else:
                            s_desc = f"{cnt} vé [{', '.join(str(s) for s in slots[:2])}]"
                        curr_el["ticket_lbl"].configure(text=f"🎟️ {s_desc}", text_color="#10b981")
                        if curr_el.get("status_lbl") and getattr(ctrl, "mirror_enabled", True):
                            curr_st = curr_el["status_lbl"].cget("text")
                            if curr_st in ("Chờ ngoài map", "Chưa kết nối", "Chờ", "⚠️ Chưa có vé", "⚠️ Hết vé", "--", "⚠️ Cần ghép vé"):
                                curr_el["status_lbl"].configure(text="🟢 Sẵn sàng", text_color="#10b981")
                    elif t_info.get("hasOnlySign"):
                        signs = t_info.get("signs", [])
                        curr_el["ticket_lbl"].configure(text=f"⚠️ Mảnh [{len(signs)} cái]", text_color="#f97316")
                        if curr_el.get("status_lbl") and getattr(ctrl, "mirror_enabled", True):
                            curr_st = curr_el["status_lbl"].cget("text")
                            if curr_st in ("Chờ ngoài map", "Chưa kết nối", "Chờ", "🟢 Sẵn sàng"):
                                curr_el["status_lbl"].configure(text="⚠️ Cần ghép vé", text_color="#f97316")
                    else:
                        curr_el["ticket_lbl"].configure(text="⚠️ 0 vé (Trống)", text_color="#f59e0b")
                        if curr_el.get("status_lbl") and getattr(ctrl, "mirror_enabled", True):
                            curr_st = curr_el["status_lbl"].cget("text")
                            if curr_st in ("Chờ ngoài map", "Chưa kết nối", "Chờ", "🟢 Sẵn sàng"):
                                curr_el["status_lbl"].configure(text="⚠️ Hết vé", text_color="#f59e0b")
                self.after(0, _update)
            except Exception:
                pass

        threading.Thread(target=_bg_check, daemon=True).start()

    def refresh_all_mirror_tickets_display(self):
        """Tự động quét và cập nhật hiển thị vé cho toàn bộ các tài khoản đang kết nối."""
        for i, ctrl in enumerate(self.controllers, 1):
            if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid) and getattr(ctrl, "mirror_enabled", True):
                self.refresh_mirror_slot_ticket_display(i)

    def update_mirror_slot_ui_state(self, slot_idx: int, is_running: bool):
        el = self.mirror_ui_elements.get(slot_idx)
        if not el:
            return
        ctrl = self.controllers[slot_idx - 1]
        if not getattr(ctrl, "mirror_enabled", True):
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")
            return
        if el.get("status_lbl"):
            if ctrl.mirror_sniping:
                el["status_lbl"].configure(text="⚡ Cướp cổng...", text_color="#c084fc")
            elif ctrl.mirror_running:
                el["status_lbl"].configure(text="🔄 Auto Mirror", text_color="#38bdf8")
            else:
                el["status_lbl"].configure(text="Đã dừng" if ctrl.assigned_pid else "Chưa kết nối", text_color="#94a3b8")
        self.update_mirror_snipe_button_state()

    def update_mirror_slot_status(self, slot_idx: int, text: str, text_color: str = "#94a3b8"):
        el = self.mirror_ui_elements.get(slot_idx)
        if el and el.get("status_lbl"):
            ctrl = self.controllers[slot_idx - 1] if 1 <= slot_idx <= len(self.controllers) else None
            if ctrl and not getattr(ctrl, "mirror_enabled", True):
                el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")
            else:
                el["status_lbl"].configure(text=text, text_color=text_color)

    def update_mirror_slot_telemetry(self, slot_idx: int, name: str, pid: Optional[int], coords: str = ""):
        mirror_elems = getattr(self, "mirror_ui_elements", {})
        el = mirror_elems.get(slot_idx) if isinstance(mirror_elems, dict) else None
        if not el or not el.get("char_lbl"):
            return
        ctrl = self.controllers[slot_idx - 1] if 1 <= slot_idx <= len(self.controllers) else None
        is_en = getattr(ctrl, "mirror_enabled", True) if ctrl else True

        cache = getattr(self, "_mirror_ui_cache", {}).setdefault(slot_idx, {})
        new_state = (name, pid, coords, is_en)
        if cache.get("state") == new_state:
            return
        cache["state"] = new_state

        f_bold = getattr(self, "font_segoe_11_bold", None)
        f_norm = getattr(self, "font_segoe_11_normal", None)

        if pid:
            disp = f"{name} ({pid})" if name and name != "---" else f"MEGAMU ({pid})"
            el["char_lbl"].configure(
                text=disp,
                text_color="#f8fafc" if is_en else "#64748b",
                font=f_bold if is_en else f_norm
            )
            if el.get("status_lbl"):
                if not is_en:
                    el["status_lbl"].configure(text="⛔ Bỏ qua", text_color="#64748b")
                else:
                    cur_st = el["status_lbl"].cget("text")
                    if cur_st in ("Chưa kết nối", "Chưa gán", "⛔ Bỏ qua"):
                        el["status_lbl"].configure(text="Sẵn sàng", text_color="#10b981")
        else:
            el["char_lbl"].configure(
                text="Chưa gán",
                text_color="#64748b",
                font=f_norm
            )
            if el.get("status_lbl"):
                el["status_lbl"].configure(text="⛔ Bỏ qua" if not is_en else "Chưa kết nối", text_color="#64748b")
            if el.get("ticket_lbl"):
                el["ticket_lbl"].configure(text="--", text_color="#64748b")
        if el.get("coords_lbl") and coords:
            el["coords_lbl"].configure(text=coords, text_color="#38bdf8" if is_en else "#475569")

    def toggle_mirror_slot_auto(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        if ctrl.mirror_running or ctrl.mirror_sniping:
            ctrl.stop_mirror_auto()
            ctrl.stop_mirror_turbo_sniping()
        else:
            ctrl.start_mirror_auto()

    def is_any_mirror_sniping(self) -> bool:
        """Kiểm tra xem có bất kỳ tài khoản nào đang trong trạng thái cướp cổng hay không."""
        return any(getattr(c, "mirror_sniping", False) for c in self.controllers)

    def toggle_mirror_turbo_sniping(self):
        """Chuyển đổi 1 nút duy nhất giữa CƯỚP CỔNG và DỪNG CƯỚP với phản hồi tức thì (0ms latency, không treo UI)."""
        is_currently_sniping = getattr(self, "_mirror_sniping_active", False) or self.is_any_mirror_sniping()

        if is_currently_sniping:
            # Ngay lập tức đổi nút sang CƯỚP CỔNG và tắt cờ để UI phản hồi 0ms
            self._mirror_sniping_active = False
            for ctrl in self.controllers:
                ctrl.mirror_sniping = False
            self.update_mirror_snipe_button_state()
            self.stop_all_mirror_auto()
        else:
            # Ngay lập tức đổi nút sang DỪNG CƯỚP để người dùng thấy thao tác cực kỳ nhạy
            self._mirror_sniping_active = True
            self.update_mirror_snipe_button_state()
            self.start_all_mirror_turbo_sniping()

    def update_mirror_snipe_button_state(self):
        """Cập nhật giao diện nút bấm gộp CƯỚP CỔNG / DỪNG theo trạng thái thực tế (Dirty-checked)."""
        if not hasattr(self, "btn_mirror_toggle_snipe") or not self.btn_mirror_toggle_snipe.winfo_exists():
            return
        is_sniping = getattr(self, "_mirror_sniping_active", False) or self.is_any_mirror_sniping()
        cache_key = ("mirror_snipe_btn", is_sniping)
        if getattr(self, "_last_mirror_snipe_btn_state", None) == cache_key:
            return
        self._last_mirror_snipe_btn_state = cache_key

        if is_sniping:
            self.btn_mirror_toggle_snipe.configure(
                text="⏹ DỪNG CƯỚP",
                fg_color="#dc2626",
                hover_color="#b91c1c",
            )
            add_tooltip(self.btn_mirror_toggle_snipe, "Đang cướp cổng! Nhấn để DỪNG ngay lập tức")
        else:
            self.btn_mirror_toggle_snipe.configure(
                text="⚡ CƯỚP CỔNG",
                fg_color="#7c3aed",
                hover_color="#6d28d9",
            )
            add_tooltip(self.btn_mirror_toggle_snipe, "Nhấn để BẮT ĐẦU cướp cổng cho các tài khoản đã chọn")

    def start_all_mirror_turbo_sniping(self):
        """Kích hoạt Turbo Sniping đồng loạt bất đồng bộ (Hoàn toàn không block Main UI Thread)."""
        delay_ms = self.get_mirror_snipe_delay()
        dur_s = self.get_mirror_snipe_dur()

        def _runner():
            threads = []
            results = []
            res_lock = threading.Lock()

            def _start_ctrl(c):
                if getattr(c, "mirror_enabled", True) and c.assigned_pid and is_megamu_process_alive(c.assigned_pid):
                    ok = c.start_mirror_turbo_sniping(interval_ms=delay_ms, max_duration_s=dur_s)
                    if ok:
                        with res_lock:
                            results.append(c.slot_idx)

            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                t = threading.Thread(target=_start_ctrl, args=(ctrl,), daemon=True)
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=2.0)

            started = len(results)
            if started > 0:
                self.after(0, lambda: self.append_mirror_log(
                    f"⚡ ĐÃ KÍCH HOẠT TURBO CHO {started} TÀI KHOẢN (Chu kỳ {delay_ms}ms, Tối đa {dur_s:.0f}s)!"
                ))
            else:
                self._mirror_sniping_active = False
                self.after(0, self.update_mirror_snipe_button_state)
                self.after(0, lambda: self.append_mirror_log("⚠️ Không có tài khoản đã chọn nào đang kết nối để kích hoạt Turbo Sniping!"))
        threading.Thread(target=_runner, daemon=True, name="TurboBatchRunner").start()

    def claim_all_gremory_case_items(self):
        """Tự động lôi quà phím 'K' (Gremory Case) cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _worker():
            self.append_mirror_log("🎁 [Gremory Case] Bắt đầu tự động lôi quà phím 'K' cho các tài khoản đã chọn...")
            total_claimed = 0
            for s_i, c in enumerate(self.controllers, 1):
                if not getattr(c, "mirror_enabled", True):
                    continue
                if c.assigned_pid and is_megamu_process_alive(c.assigned_pid):
                    try:
                        eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                        if eng:
                            res = eng.claim_gremory_case_items()
                            cnt = res.get("claimed", 0)
                            total_claimed += cnt
                            if cnt > 0:
                                self.append_mirror_log(f"[Slot {s_i:02d} - {c.char_name}] 🏆 ĐÃ LÔI THÀNH CÔNG {cnt} MÓN QUÀ TỪ PHÍM 'K' VÀO HÒM ĐỒ!")
                            else:
                                self.append_mirror_log(f"[Slot {s_i:02d} - {c.char_name}] ℹ️ Hộp Quà Phím 'K' sạch quà (không có quà tồn).")
                    except Exception as e:
                        self.append_mirror_log(f"[Slot {s_i:02d} - {c.char_name}] ⚠️ Lỗi lôi quà phím 'K': {e}")
            self.append_mirror_log(f"🏁 [Gremory Case] Hoàn tất quá trình lôi quà! Tổng cộng đã nhận: {total_claimed} món quà.")
        threading.Thread(target=_worker, daemon=True).start()

    def trigger_all_mirror_lifecycle(self):
        """Kích hoạt chu trình chiến đấu bên trong Double Goer cho các tài khoản ĐÃ TÍCH CHỌN."""
        cnt = 0
        for ctrl in self.controllers:
            if not getattr(ctrl, "mirror_enabled", True):
                continue
            if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                cnt += 1
                threading.Thread(target=ctrl.run_mirror_in_dungeon_lifecycle, kwargs={"force": True}, daemon=True).start()
        if cnt == 0:
            self.append_mirror_log("⚠️ Chưa có tài khoản nào được chọn kết nối để kích hoạt chu trình Double Goer!")
        else:
            self.append_mirror_log(f"⚔️ Đang kích hoạt chu trình: Đợi Safe Zone -> Phút :16 ra bãi -> Bật Helper -> Săn 3 Box quà cho {cnt} tài khoản...")

    def enter_all_mirror(self):
        """Gửi lệnh vào cửa Double Goer cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _enterer():
            cnt = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ctrl.enter_mirror()
                    cnt += 1
                    time.sleep(0.08)
            self.after(0, lambda: self.append_mirror_log(f"🚪 Đã gửi lệnh vào cửa Double Goer cho {cnt} tài khoản đã chọn!"))
        threading.Thread(target=_enterer, daemon=True).start()

    def move_all_to_lugard(self):
        """Di chuyển các tài khoản ĐÃ TÍCH CHỌN tới vị trí NPC Lugard (229, 22)."""
        def _mover():
            cnt = 0
            self.after(0, lambda: self.append_mirror_log("🚶 Bắt đầu di chuyển các tài khoản đã chọn về NPC Lugard (229, 22)..."))
            threads = []
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    cnt += 1
                    t = threading.Thread(target=ctrl.move_to_lugard, daemon=True)
                    threads.append(t)
                    t.start()
                    time.sleep(0.12)
            for t in threads:
                t.join(timeout=10.0)
            self.after(0, lambda: self.append_mirror_log(f"✅ Hoàn tất đưa {cnt} tài khoản về vị trí NPC Lugard!"))
        threading.Thread(target=_mover, daemon=True).start()

    move_all_to_event_map = move_all_to_lugard

    def click_all_mirror_npc(self):
        """Gửi lệnh tương tác NPC Lugard cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _clicker():
            cnt = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ctrl.click_mirror_npc()
                    cnt += 1
                    time.sleep(0.08)
            self.after(0, lambda: self.append_mirror_log(f"💬 Đã tương tác NPC Lugard cho {cnt} tài khoản đã chọn!"))
        threading.Thread(target=_clicker, daemon=True).start()

    def start_all_mirror_auto(self):
        """Kích hoạt Auto Double Goer cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _batch_runner():
            started = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    ok = ctrl.start_mirror_auto()
                    if ok:
                        started += 1
                        time.sleep(0.1)
            if started > 0:
                self.after(0, lambda: self.append_mirror_log(f"🚀 Đã kích hoạt Auto Mirror cho {started} tài khoản đã chọn!"))
            else:
                self.after(0, lambda: self.append_mirror_log("⚠️ Không có tài khoản đã chọn nào đang kết nối để chạy Auto Mirror!"))
        threading.Thread(target=_batch_runner, daemon=True).start()

    def stop_all_mirror_auto(self):
        """Dừng Auto Double Goer & Turbo Sniping trên các tài khoản bất đồng bộ (Zero UI Freeze)."""
        self._mirror_sniping_active = False
        self.update_mirror_snipe_button_state()

        def _async_stop():
            for ctrl in self.controllers:
                try:
                    ctrl.stop_mirror_auto()
                    ctrl.stop_mirror_turbo_sniping()
                except Exception:
                    pass
            self.after(0, lambda: self.append_mirror_log("⏹️ Đã dừng Auto Mirror & Turbo Sniping trên toàn bộ tài khoản."))
            self.after(0, self.update_mirror_snipe_button_state)

        threading.Thread(target=_async_stop, daemon=True, name="MirrorAsyncStopper").start()

    def append_mirror_log(self, text: str):
        if hasattr(self, "mirror_log_txt"):
            def _do():
                if hasattr(self, "mirror_log_txt") and self.mirror_log_txt.winfo_exists():
                    self._safe_append_textbox(self.mirror_log_txt, text)
            try:
                self.after(0, _do)
            except Exception:
                _do()

    def clear_mirror_log(self):
        if hasattr(self, "mirror_log_txt"):
            self.mirror_log_txt.delete("1.0", "end")

    def get_mirror_schedule_config(self) -> Dict[str, Any]:
        """Lấy cấu hình lập lịch Mirror hiện tại từ UI kèm danh sách selected_slots."""
        is_auto = bool(self.cb_mirror_auto_schedule.get()) if hasattr(self, "cb_mirror_auto_schedule") else True
        is_prep = bool(self.cb_mirror_auto_prep_before.get()) if hasattr(self, "cb_mirror_auto_prep_before") else True
        is_life = bool(self.cb_mirror_auto_lifecycle.get()) if (hasattr(self, "cb_mirror_auto_lifecycle") and self.cb_mirror_auto_lifecycle is not None) else False
        is_gremory = bool(self.cb_mirror_auto_gremory.get()) if (hasattr(self, "cb_mirror_auto_gremory") and self.cb_mirror_auto_gremory is not None) else False
        prefire = self.get_mirror_prefire_sec() if hasattr(self, "mirror_prefire_sec_entry") else 1.2
        is_zero_popups = bool(self.cb_mirror_zero_popups.get()) if (hasattr(self, "cb_mirror_zero_popups") and self.cb_mirror_zero_popups is not None) else True
        selected_slots = [c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)]
        return {
            "auto_schedule": is_auto,
            "auto_prep_before": is_prep,
            "auto_lifecycle": is_life,
            "auto_gremory": is_gremory,
            "auto_zero_popups": is_zero_popups,
            "prefire_sec": prefire,
            "selected_slots": selected_slots
        }

    def on_toggle_mirror_zero_popups(self):
        """Xử lý khi người dùng bật/tắt checkbox 🚫 Ẩn Dialog (Zero Popups)."""
        cfg = self.get_mirror_schedule_config()
        ConfigPersistenceManager.save_mirror_schedule_config(cfg)
        enabled = cfg.get("auto_zero_popups", True)
        status_txt = "BẬT" if enabled else "TẮT"
        self.append_mirror_log(f"🚫 [Mirror] Chế độ tự động xác nhận và ẩn thông báo (Zero Dialog): {status_txt}")
        for c in self.controllers:
            if c.assigned_pid and is_megamu_process_alive(c.assigned_pid):
                try:
                    eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                    if eng and hasattr(eng, "set_dialog_suppression"):
                        eng.set_dialog_suppression(enabled)
                except Exception:
                    pass

    def on_toggle_mirror_auto_schedule(self):
        """Xử lý khi người dùng bật/tắt checkbox Auto Schedule hoặc đổi thời gian giật trước."""
        cfg = self.get_mirror_schedule_config()
        ConfigPersistenceManager.save_mirror_schedule_config(cfg)
        status_txt = "BẬT" if cfg.get("auto_schedule") else "TẮT"
        prep_txt = "Có (trước 5p)" if cfg.get("auto_prep_before") else "Không"
        life_txt = "BẬT" if cfg.get("auto_lifecycle", True) else "TẮT"
        gremory_txt = "BẬT" if cfg.get("auto_gremory", True) else "TẮT"
        prefire_val = cfg.get("prefire_sec", 1.2)
        sel_count = len(cfg.get("selected_slots", []))
        self.append_mirror_log(f"⏰ [Cấu Hình Mirror] Cướp cổng: {status_txt} | Tài khoản đi: {sel_count}/{len(self.controllers)} | Giật trước: {prefire_val:.1f}s")

        if cfg.get("auto_lifecycle", False):
            for c in self.controllers:
                if getattr(c, "mirror_enabled", True) and c.assigned_pid and is_megamu_process_alive(c.assigned_pid):
                    try:
                        eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                        if eng and eng.is_mirror_event_map():
                            threading.Thread(target=c.run_mirror_in_dungeon_lifecycle, daemon=True).start()
                    except Exception:
                        pass

    def check_mirror_slot_ticket(self, slot_idx: int):
        """Kiểm tra vé Mirror của slot cụ thể."""
        if slot_idx < 1 or slot_idx > len(self.controllers):
            return
        ctrl = self.controllers[slot_idx - 1]
        def _checker():
            t_info = ctrl.check_mirror_ticket()
            if t_info.get("hasTicket"):
                details = t_info.get("details", [])
                main_slots = [d["slot"] for d in details if not d.get("isExtended")]
                ext_slots = [d["slot"] for d in details if d.get("isExtended")]
                loc_parts = []
                if main_slots:
                    loc_parts.append(f"Hòm chính [{', '.join(str(s) for s in main_slots)}]")
                if ext_slots:
                    loc_parts.append(f"Ba lô phụ [{', '.join(str(s) for s in ext_slots)}]")
                loc_str = " • ".join(loc_parts) if loc_parts else f"ô [{', '.join(str(s) for s in t_info.get('slots', []))}]"
                self.after(0, lambda: self.append_mirror_log(
                    f"[Slot {slot_idx:02d} - {ctrl.char_name}] 🎟️ Có {t_info.get('count')} vé Mirror ({loc_str})!"
                ))
            elif t_info.get("hasOnlySign"):
                signs_str = ", ".join(str(s) for s in t_info.get("signs", []))
                self.after(0, lambda: self.append_mirror_log(
                    f"[Slot {slot_idx:02d} - {ctrl.char_name}] ⚠️ Phát hiện Mảnh Ghép Sign of Dimensions tại ô [{signs_str}] (Chưa ghép thành vé Mirror hoàn chỉnh)!"
                ))
            else:
                err = t_info.get("error")
                if err == "not_connected":
                    msg = "⚠️ Chưa kết nối Game!"
                elif err == "no_engine":
                    msg = "⚠️ Engine chưa khởi tạo!"
                else:
                    msg = "⚠️ Không tìm thấy vé Mirror of Dimensions (đã quét toàn bộ ô 12-203)!"
                self.after(0, lambda: self.append_mirror_log(f"[Slot {slot_idx:02d} - {ctrl.char_name}] {msg}"))
        threading.Thread(target=_checker, daemon=True).start()

    def check_all_mirror_tickets(self):
        """Kiểm tra vé Mirror trên các tài khoản ĐÃ TÍCH CHỌN đang kết nối."""
        def _check_all():
            self.after(0, lambda: self.append_mirror_log("🔍 Đang kiểm tra vé Mirror trên các tài khoản đã chọn (ô 12 - 203)..."))
            total_connected = 0
            has_ticket_count = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    total_connected += 1
                    t_info = ctrl.check_mirror_ticket()
                    if t_info.get("hasTicket"):
                        has_ticket_count += 1
                        details = t_info.get("details", [])
                        main_slots = [d["slot"] for d in details if not d.get("isExtended")]
                        ext_slots = [d["slot"] for d in details if d.get("isExtended")]
                        loc_parts = []
                        if main_slots:
                            loc_parts.append(f"Chính: {main_slots}")
                        if ext_slots:
                            loc_parts.append(f"Phụ: {ext_slots}")
                        loc_desc = " | ".join(loc_parts) if loc_parts else f"ô {t_info.get('slots', [])}"
                        self.after(0, lambda c=ctrl, inf=t_info, ld=loc_desc: self.append_mirror_log(
                            f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] 🎟️ Có {inf.get('count')} vé ({ld})"
                        ))
                    elif t_info.get("hasOnlySign"):
                        signs_str = ", ".join(str(s) for s in t_info.get("signs", []))
                        self.after(0, lambda c=ctrl, ss=signs_str: self.append_mirror_log(
                            f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] ⚠️ Chỉ có Mảnh Ghép Sign of Dimensions tại ô [{ss}]"
                        ))
                    else:
                        self.after(0, lambda c=ctrl: self.append_mirror_log(
                            f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] ⚠️ KHÔNG CÓ VÉ MIRROR (ô 12-203 trống)!"
                        ))
                    time.sleep(0.05)
            self.after(0, lambda tc=total_connected, ht=has_ticket_count: self.append_mirror_log(
                f"📊 Kết quả kiểm tra: {ht}/{tc} tài khoản có vé sẵn sàng."
            ))
        threading.Thread(target=_check_all, daemon=True).start()

    def prepare_all_mirror_event(self):
        """Kích hoạt giai đoạn chuẩn bị trước 5 phút cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _prep():
            self.after(0, lambda: self.append_mirror_log("🚶 [Giai đoạn Chuẩn Bị] Đang đưa các tài khoản đã chọn về NPC Lugard & kiểm tra vé..."))
            cnt = 0
            threads = []
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                    cnt += 1
                    t = threading.Thread(target=ctrl.prepare_mirror_event, daemon=True)
                    threads.append(t)
                    t.start()
                    time.sleep(0.12)
            for t in threads:
                t.join(timeout=10.0)
            self.after(0, lambda: self.append_mirror_log(f"✅ Hoàn tất chuẩn bị cho {cnt} tài khoản tại NPC Lugard!"))
        threading.Thread(target=_prep, daemon=True).start()

    def _periodic_mirror_scheduler(self):
        """Vòng lặp tính toán đếm ngược và tự động kích hoạt sự kiện Mirror.
        - Mỗi 2 tiếng một lần: 00:15, 02:15, 04:15, ..., 22:15.
        - CỔNG MỞ TỪ PHÚT :10 ĐẾN :15 (ĐÃ CÓ THỂ VÀO CỬA TỪ LÚC :10).
        - Giai đoạn chuẩn bị (di chuyển về Lugard, check vé) tự động kích hoạt từ phút :08 (trước khi cổng mở 2 phút).
        - PRE-FIRE TURBO SNIPING: Đón đầu từ :09:59 (trước 2 giây) để giật cổng trong tích tắc trước đối thủ!
        - Trong suốt khung :10 - :15: Tự động giữ nhịp Turbo Sniping cho toàn bộ tài khoản có vé đến khi vào map.
        - Khi vào được map Double Goer: Tự động bật MuHelper đánh quái.
        """
        if not self.running:
            return

        poll_interval_ms = 1000

        try:
            now = datetime.now()
            valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]

            # 1. Xác định xem hiện tại có đang nằm trong khung MỞ CỔNG (:10:00 - :14:59 của giờ chẵn) hay không
            is_in_gate_open_window = False
            current_event_hour = None
            if now.hour in valid_hours and 10 <= now.minute < 15:
                is_in_gate_open_window = True
                current_event_hour = now.hour

            # 2. Tìm mốc MỞ CỔNG (:10) và mốc BẮT ĐẦU (:15) tiếp theo
            next_gate_open = None
            next_event_start = None
            for h in valid_hours:
                cand_gate = now.replace(hour=h, minute=10, second=0, microsecond=0)
                cand_start = now.replace(hour=h, minute=15, second=0, microsecond=0)
                if cand_gate > now:
                    next_gate_open = cand_gate
                    next_event_start = cand_start
                    break
            if not next_gate_open:
                # Đã qua 22:10 hôm nay -> mốc kế tiếp là 00:10 ngày mai
                tomorrow = now + timedelta(days=1)
                next_gate_open = tomorrow.replace(hour=0, minute=10, second=0, microsecond=0)
                next_event_start = tomorrow.replace(hour=0, minute=15, second=0, microsecond=0)

            has_mirror_mod = license_client.has_license_module("mirror") if license_client else True
            is_auto = has_mirror_mod and hasattr(self, "cb_mirror_auto_schedule") and (self.cb_mirror_auto_schedule.get() == 1)
            is_prep_enabled = has_mirror_mod and hasattr(self, "cb_mirror_auto_prep_before") and (self.cb_mirror_auto_prep_before.get() == 1)

            diff_to_open = int((next_gate_open - now).total_seconds())
            prefire_sec = self.get_mirror_prefire_sec() if hasattr(self, "get_mirror_prefire_sec") else 5.0

            # 3. ĐIỀU CHỈNH ĐỘ PHÂN GIẢI CLOCK (POLLING INTERVAL):
            if not is_in_gate_open_window and diff_to_open <= max(15, int(prefire_sec) + 5):
                # Dưới ngưỡng trước giờ mở cổng: Chuyển sang nhịp 100ms để bắt chuẩn xác từng mili-giây
                poll_interval_ms = 100
            elif is_in_gate_open_window:
                # Khi cổng đang mở: Polling 500ms để theo dõi sát sao
                poll_interval_ms = 500
            else:
                poll_interval_ms = 1000

            # 3.5. TỰ ĐỘNG PRE-CACHE Ô VÉ VÀO RAM (Tránh quét kho đồ làm trễ mili-giây giờ G)
            if not is_in_gate_open_window and 10 <= diff_to_open <= 90:
                gate_cache_key = next_gate_open.strftime("%Y%m%d_%H%M_precache")
                if getattr(self, "_last_mirror_cache_key", None) != gate_cache_key:
                    self._last_mirror_cache_key = gate_cache_key
                    for ctrl in self.controllers:
                        if not getattr(ctrl, "mirror_enabled", True):
                            continue
                        if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                            if getattr(ctrl, "cached_mirror_ticket_slot", -1) < 0:
                                threading.Thread(target=ctrl.check_mirror_ticket, daemon=True).start()

            # 4. PRE-FIRE TURBO SNIPING: Giật thời gian đón đầu trước giờ mở cổng!
            # Nếu còn <= prefire_sec (mặc định 5s, bù trừ độ lệch 2-3s của server game):
            # Kích hoạt Turbo Sniping ngay lập tức để thread ấm máy, packet bắn đón đầu microsecond đầu tiên khi server mở :10:00!
            gate_prefire_key = next_gate_open.strftime("%Y%m%d_%H%M_prefire")
            if not is_in_gate_open_window and diff_to_open <= prefire_sec:
                if getattr(self, "_last_mirror_prefire_key", None) != gate_prefire_key:
                    self._last_mirror_prefire_key = gate_prefire_key
                    if is_auto:
                        self.append_mirror_log(
                            f"⚡ [PRE-FIRE TURBO SNIPING] Còn {diff_to_open}s tới giờ mở cổng ({next_gate_open.strftime('%H:%M')})! Kích hoạt đón đầu {prefire_sec:.1f}s để cướp cổng trong tích tắc!"
                        )
                        self.start_all_mirror_turbo_sniping()

            # TRƯỜNG HỢP 1: CỔNG ĐANG MỞ (:10:00 đến :14:59 của giờ chẵn)
            if is_in_gate_open_window:
                start_dt = now.replace(minute=15, second=0, microsecond=0)
                remain_open_sec = max(0, int((start_dt - now).total_seconds()))
                m_rem = remain_open_sec // 60
                s_rem = remain_open_sec % 60

                if hasattr(self, "lbl_mirror_next_event"):
                    self.lbl_mirror_next_event.configure(text="(:10 - :15)")

                if hasattr(self, "lbl_mirror_countdown"):
                    self.lbl_mirror_countdown.configure(
                        text=f"⚡ Cổng mở: {m_rem:02d}:{s_rem:02d}",
                        text_color="#eab308"
                    )

                if hasattr(self, "lbl_mirror_sched_status"):
                    self.lbl_mirror_sched_status.configure(text="⚡ Cướp cổng", text_color="#eab308")

                # Kích hoạt đợt đầu lúc :10 nếu chưa được kích hoạt bởi pre-fire
                gate_key = now.strftime("%Y%m%d_%H10_gate_open")
                if getattr(self, "_last_mirror_gate_key", None) != gate_key:
                    self._last_mirror_gate_key = gate_key
                    if is_auto:
                        self.append_mirror_log(
                            f"🚀 [CỔNG ĐÃ MỞ LÚC {now.strftime('%H:%M')}] Bắt đầu tự động vào cửa Double Goer cho toàn bộ tài khoản!"
                        )
                        self.start_all_mirror_turbo_sniping()

                # Trong suốt khung mở cổng (:10 - :15), nếu tài khoản nào có vé mà chưa vào được Double Goer,
                # và hiện không trong trạng thái sniping, tự động tiếp tục kích hoạt Turbo để vào bằng được!
                gate_retry_key = now.strftime("%Y%m%d_%H%M_") + str(now.second // 10)
                if is_auto and (now.second % 10 == 0) and getattr(self, "_last_mirror_retry_key", None) != gate_retry_key:
                    self._last_mirror_retry_key = gate_retry_key
                    def _bg_retry():
                        for ctrl in self.controllers:
                            if not getattr(ctrl, "mirror_enabled", True):
                                continue
                            if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                                eng = ctrl.engine
                                if eng and not eng.is_mirror_event_map() and not getattr(ctrl, "mirror_sniping", False):
                                    t_info = eng.get_mirror_ticket_info()
                                    if t_info.get("hasTicket"):
                                        ctrl.start_mirror_turbo_sniping(
                                            interval_ms=self.get_mirror_snipe_delay(),
                                            max_duration_s=min(12.0, float(remain_open_sec))
                                        )
                    threading.Thread(target=_bg_retry, daemon=True, name="MirrorGateRetryWorker").start()

            # TRƯỜNG HỢP 2: ĐANG NGOÀI KHUNG MỞ CỔNG (Đếm ngược tới mốc :10 tiếp theo)
            else:
                hours_left = diff_to_open // 3600
                mins_left = (diff_to_open % 3600) // 60
                secs_left = diff_to_open % 60

                if hasattr(self, "lbl_mirror_next_event"):
                    self.lbl_mirror_next_event.configure(
                        text=f"({next_gate_open.strftime('%H:%M')})"
                    )

                if hasattr(self, "lbl_mirror_countdown"):
                    if hours_left > 0:
                        cnt_str = f"⏳ {hours_left:02d}:{mins_left:02d}:{secs_left:02d}"
                    else:
                        cnt_str = f"⏳ {mins_left:02d}:{secs_left:02d}"
                    self.lbl_mirror_countdown.configure(text=cnt_str, text_color="#a855f7")

                # Giai đoạn chuẩn bị (kích hoạt từ phút :08, tức là trước giờ mở cổng 120s = 2 phút):
                if diff_to_open <= 120:
                    if hasattr(self, "lbl_mirror_sched_status"):
                        if diff_to_open <= 2:
                            self.lbl_mirror_sched_status.configure(text="⚡ Pre-fire", text_color="#f59e0b")
                        else:
                            self.lbl_mirror_sched_status.configure(text="🏃 Chuẩn bị", text_color="#38bdf8")
                    if hasattr(self, "lbl_mirror_countdown"):
                        self.lbl_mirror_countdown.configure(text_color="#38bdf8")

                    prep_key = next_gate_open.strftime("%Y%m%d_%H%M_prep")
                    if getattr(self, "_last_mirror_prep_key", None) != prep_key:
                        self._last_mirror_prep_key = prep_key
                        if is_auto and is_prep_enabled:
                            self.append_mirror_log(
                                f"⏰ [Tự Động Chuẩn Bị] Còn {diff_to_open}s tới giờ mở cổng ({next_gate_open.strftime('%H:%M')})! Đang chuyển map về Lugard & kiểm tra vé..."
                            )
                            self.prepare_all_mirror_event()
                else:
                    if hasattr(self, "lbl_mirror_sched_status"):
                        if is_auto:
                            self.lbl_mirror_sched_status.configure(text="● Chờ", text_color="#10b981")
                        else:
                            self.lbl_mirror_sched_status.configure(text="○ Tắt", text_color="#64748b")

            # 5. Tự động thăm dò vé định kỳ mỗi 4 giây để UI luôn cập nhật mới nhất
            self.update_mirror_snipe_button_state()
            self._mirror_poll_tick = getattr(self, "_mirror_poll_tick", 0) + 1
            now_ts = time.time()
            if (now_ts - getattr(self, "_last_mirror_tickets_poll_time", 0.0)) >= 5.0:
                self._last_mirror_tickets_poll_time = now_ts
                self.refresh_all_mirror_tickets_display()

            # 6. Tự động kiểm tra chu trình Double Goer (Đợi Safe Zone -> Phút 16 ra bãi -> Săn 3 Box)
            if self._mirror_poll_tick % 3 == 0:
                is_lifecycle_enabled = hasattr(self, "cb_mirror_auto_lifecycle") and self.cb_mirror_auto_lifecycle is not None and (self.cb_mirror_auto_lifecycle.get() == 1)
                for s_i, c in enumerate(self.controllers, 1):
                    if c.assigned_pid and is_megamu_process_alive(c.assigned_pid):
                        try:
                            eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                            if eng and eng.is_mirror_event_map():
                                if is_lifecycle_enabled:
                                    c.run_mirror_in_dungeon_lifecycle()
                        except Exception:
                            pass

        except Exception as e:
            log_thread_exception(
                source="DashboardApp._periodic_mirror_scheduler",
                exc=e,
                thread_name="MirrorScheduler",
                details="Lỗi trong chu kỳ lập lịch Double Goer"
            )

        finally:
            self.after(poll_interval_ms, self._periodic_mirror_scheduler)

    def jump_to_config_tab(self, slot_idx: int):
        """Mở nhanh Modal Cấu hình chặng ứng với Slot khi bấm nút '⚙' ở Slot."""
        ctrl = self.controllers[slot_idx - 1]
        self.open_profiles_modal(profile_index=ctrl.profile_index)

    # ==========================================================================
    # TAB 7: QUẢN LÝ TÀI KHOẢN & AUTO LOGIN NATIVE (AUTO LOGIN TAB)
    # ==========================================================================
    def build_autologin_view(self):
        """Xây dựng giao diện Tab Quản lý tài khoản & AutoLogin thẳng vào game (Modular AutoLoginView)."""
        view = AutoLoginView(self, self.panel_autologin)
        view.build()

    def refresh_autologin_table(self):
        """Vẽ lại toàn bộ danh sách tài khoản trong Tab AutoLogin."""
        if not hasattr(self, "autologin_scroll"):
            return

        for w in self.autologin_scroll.winfo_children():
            w.destroy()
        self.autologin_ui_rows.clear()

        if not self.account_mgr or not self.account_mgr.accounts:
            empty_lbl = ctk.CTkLabel(
                self.autologin_scroll,
                text="Chưa có tài khoản nào được lưu.\nNhấn nút '🔄 Đọc từ Registry' để tự động nạp danh sách tài khoản MEGAMU trên máy!",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#64748b",
                justify="center"
            )
            empty_lbl.pack(pady=40)
            return

        for idx, acc in enumerate(self.account_mgr.accounts):
            row = ctk.CTkFrame(self.autologin_scroll, fg_color="#151924", height=42, corner_radius=0, border_width=1, border_color="#1f2535")
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            # 1. Checkbox Enable
            cb_var = ctk.BooleanVar(value=acc.get("enabled", True))
            def _make_cb_cmd(a_ref, v_ref):
                return lambda: self._on_acc_toggle(a_ref, v_ref.get())
            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=cb_var,
                width=24,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=0,
                command=_make_cb_cmd(acc, cb_var)
            )
            cb.pack(side="left", padx=(10, 2))

            # 2. STT
            stt_lbl = ctk.CTkLabel(row, text=f"#{idx+1:02d}", width=38, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8")
            stt_lbl.pack(side="left", padx=2)

            # 3. Username
            u_name = acc.get("username", "")
            has_pwd = bool(acc.get("password"))
            u_title = f"{u_name} 🔑" if has_pwd else u_name
            u_lbl = ctk.CTkLabel(row, text=u_title, width=125, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#38bdf8" if has_pwd else "#f1f5f9")
            u_lbl.pack(side="left", padx=4)

            # 4. Character Combobox
            c_list = acc.get("characters_list", [])
            cur_char = acc.get("character", "")
            if cur_char and cur_char not in c_list:
                c_list = [cur_char] + [x for x in c_list if x != cur_char]
            if not c_list:
                c_list = ["(Mặc định)"]
            if not cur_char or cur_char not in c_list:
                cur_char = c_list[0]

            char_var = ctk.StringVar(value=cur_char)
            def _make_char_cmd(a_ref):
                return lambda val: self._on_acc_char_change(a_ref, val)
            char_combo = ModernOptionMenu(
                row,
                values=c_list,
                variable=char_var,
                width=135,
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=_make_char_cmd(acc)
            )
            char_combo.pack(side="left", padx=4)

            # 5. Server Combobox
            srv_val = int(acc.get("server", 1))
            srv_var = ctk.StringVar(value=f"Server {srv_val}")
            def _make_srv_cmd(a_ref):
                return lambda val: self._on_acc_srv_change(a_ref, val)
            srv_combo = ModernOptionMenu(
                row,
                values=[f"Server {s}" for s in range(1, 9)],
                variable=srv_var,
                width=95,
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=_make_srv_cmd(acc)
            )
            srv_combo.pack(side="left", padx=4)

            # 6. Slot Target Combobox
            slot_opts = ["Tự động"] + [f"Slot #{c.slot_idx:02d}" for c in self.controllers]
            def_slot = f"Slot #{idx+1:02d}" if (idx < len(self.controllers)) else "Tự động"
            slot_var = ctk.StringVar(value=def_slot)
            slot_combo = ModernOptionMenu(
                row,
                values=slot_opts,
                variable=slot_var,
                width=115,
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            slot_combo.pack(side="left", padx=4)

            # 7. Actions: Launch, Send Login, Delete
            act_box = ctk.CTkFrame(row, fg_color="transparent")
            act_box.pack(side="left", fill="x", expand=True, padx=6)

            def _make_launch_cmd(a_ref, s_ref):
                return lambda: self.launch_single_account_ui(a_ref, s_ref.get())
            btn_launch = ctk.CTkButton(
                act_box,
                text="🚀 Mở & Login",
                width=90,
                height=26,
                corner_radius=0,
                fg_color="#6366f1",
                hover_color="#4f46e5",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=_make_launch_cmd(acc, slot_var)
            )
            btn_launch.pack(side="left", padx=(0, 4))

            def _make_send_cmd(a_ref, s_ref):
                return lambda: self.send_login_to_slot_ui(a_ref, s_ref.get())
            btn_send = ctk.CTkButton(
                act_box,
                text="⚡ Gửi Login",
                width=80,
                height=26,
                corner_radius=0,
                fg_color="#0f172a",
                hover_color="#1e293b",
                border_width=1,
                border_color="#38bdf8",
                text_color="#38bdf8",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=_make_send_cmd(acc, slot_var)
            )
            btn_send.pack(side="left", padx=(0, 4))

            def _make_edit_cmd(a_ref):
                return lambda: self.open_edit_account_dialog(a_ref)
            btn_edit = ctk.CTkButton(
                act_box,
                text="✏️",
                width=30,
                height=26,
                corner_radius=0,
                fg_color="#1e2433",
                hover_color="#0284c7",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=_make_edit_cmd(acc)
            )
            btn_edit.pack(side="left", padx=(0, 4))

            def _make_del_cmd(u_str):
                return lambda: self.delete_account_ui(u_str)
            btn_del = ctk.CTkButton(
                act_box,
                text="🗑️",
                width=30,
                height=26,
                corner_radius=0,
                fg_color="#1e2433",
                hover_color="#ef4444",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=_make_del_cmd(u_name)
            )
            btn_del.pack(side="left")

            self.autologin_ui_rows.append({
                "acc": acc,
                "cb_var": cb_var,
                "char_var": char_var,
                "srv_var": srv_var,
                "slot_var": slot_var,
                "btn_launch": btn_launch
            })

    def _on_acc_toggle(self, acc: Dict[str, Any], enabled: bool):
        acc["enabled"] = enabled
        if self.account_mgr:
            self.account_mgr.save_accounts()

    def _on_acc_char_change(self, acc: Dict[str, Any], char_name: str):
        if char_name != "(Mặc định)":
            acc["character"] = char_name
            if self.account_mgr:
                self.account_mgr.save_accounts()

    def _on_acc_srv_change(self, acc: Dict[str, Any], srv_text: str):
        try:
            s_num = int(srv_text.replace("Server ", "").strip())
            acc["server"] = s_num
            if self.account_mgr:
                self.account_mgr.save_accounts()
        except Exception:
            pass

    def toggle_all_accounts_ui(self):
        """Bật/tắt tất cả tài khoản."""
        if not self.account_mgr or not self.account_mgr.accounts:
            return
        all_enabled = all(a.get("enabled", True) for a in self.account_mgr.accounts)
        new_val = not all_enabled
        self.account_mgr.toggle_all(new_val)
        self.refresh_autologin_table()

    def import_accounts_from_registry_ui(self):
        """Đọc và sáp nhập tài khoản từ Windows Registry của MEGAMU."""
        if not self.account_mgr:
            return
        cnt = self.account_mgr.import_from_registry()
        self.refresh_autologin_table()
        msg = f"Đã đồng bộ {cnt} tài khoản mới từ Registry MEGAMU!" if cnt > 0 else "Đã đồng bộ từ Registry (không có tài khoản mới nào)."
        self.append_autologin_log(f"🔄 {msg}")
        self.log_message(msg, "SUCCESS" if cnt > 0 else "INFO")

    def choose_exe_path_dialog(self):
        """Chọn đường dẫn tệp MEGAMU.exe."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn tệp MEGAMU.exe",
            filetypes=[("MEGAMU Executable", "MEGAMU.exe"), ("All Executables", "*.exe")]
        )
        if path and os.path.isfile(path):
            if self.account_mgr:
                self.account_mgr.set_exe_path(path)
            self.lbl_autologin_exe.configure(text=f"📁 Exe: {os.path.basename(path)}")
            self.append_autologin_log(f"📁 Đã cập nhật đường dẫn MEGAMU.exe: {path}")

    def open_add_account_dialog(self):
        """Hộp thoại thêm tài khoản MEGAMU mới."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Thêm Tài Khoản MEGAMU")
        dlg.geometry("400x330")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="➕ THÊM TÀI KHOẢN MỚI", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="#c084fc").pack(pady=(14, 10))

        f = ctk.CTkFrame(dlg, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(f, text="Tên tài khoản:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=0, column=0, sticky="w", pady=6)
        u_ent = ctk.CTkEntry(f, width=210, font=ctk.CTkFont(family="Segoe UI", size=11), placeholder_text="Ví dụ: myaccount")
        u_ent.grid(row=0, column=1, sticky="e", pady=6)
        u_ent.focus_set()

        ctk.CTkLabel(f, text="Mật khẩu:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=1, column=0, sticky="w", pady=6)
        p_ent = ctk.CTkEntry(f, width=210, show="*", font=ctk.CTkFont(family="Segoe UI", size=11), placeholder_text="Mật khẩu đăng nhập")
        p_ent.grid(row=1, column=1, sticky="e", pady=6)

        ctk.CTkLabel(f, text="Tên nhân vật:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=2, column=0, sticky="w", pady=6)
        c_ent = ctk.CTkEntry(f, width=210, font=ctk.CTkFont(family="Segoe UI", size=11), placeholder_text="Tên nhân vật muốn chọn")
        c_ent.grid(row=2, column=1, sticky="e", pady=6)

        ctk.CTkLabel(f, text="Server:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=3, column=0, sticky="w", pady=6)
        s_combo = ModernOptionMenu(f, values=[f"Server {s}" for s in range(1, 9)], width=210, font=ctk.CTkFont(family="Segoe UI", size=11))
        s_combo.grid(row=3, column=1, sticky="e", pady=6)

        def _save():
            u = u_ent.get().strip()
            p = p_ent.get().strip()
            c = c_ent.get().strip()
            s = int(s_combo.get().replace("Server ", "").strip())
            if not u:
                return
            if self.account_mgr:
                self.account_mgr.add_account(username=u, password=p, character=c, server=s)
            self.refresh_autologin_table()
            pwd_info = " (Đã lưu mật khẩu)" if p else ""
            self.append_autologin_log(f"➕ Đã thêm tài khoản '{u}'{pwd_info} (Nhân vật '{c}', Server {s})")
            dlg.destroy()

        btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_box.pack(pady=(16, 0))
        ctk.CTkButton(btn_box, text="Lưu", width=95, fg_color="#7c3aed", hover_color="#6d28d9", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), command=_save).pack(side="left", padx=6)
        ctk.CTkButton(btn_box, text="Hủy", width=95, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(family="Segoe UI", size=11), command=dlg.destroy).pack(side="left", padx=6)

    def open_edit_account_dialog(self, acc: Dict[str, Any]):
        """Hộp thoại chỉnh sửa thông tin tài khoản MEGAMU (Mật khẩu, Nhân vật, Server)."""
        dlg = ctk.CTkToplevel(self)
        u_name = acc.get("username", "")
        dlg.title(f"Sửa Tài Khoản: {u_name}")
        dlg.geometry("400x330")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text=f"✏️ CẬP NHẬT TÀI KHOẢN: {u_name}", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#38bdf8").pack(pady=(14, 10))

        f = ctk.CTkFrame(dlg, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(f, text="Tên tài khoản:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=0, column=0, sticky="w", pady=6)
        u_lbl = ctk.CTkLabel(f, text=u_name, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f8fafc")
        u_lbl.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ctk.CTkLabel(f, text="Mật khẩu:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=1, column=0, sticky="w", pady=6)
        p_ent = ctk.CTkEntry(f, width=210, show="*", font=ctk.CTkFont(family="Segoe UI", size=11), placeholder_text="Nhập mật khẩu")
        p_ent.grid(row=1, column=1, sticky="e", pady=6)
        if acc.get("password"):
            p_ent.insert(0, acc["password"])

        ctk.CTkLabel(f, text="Tên nhân vật:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=2, column=0, sticky="w", pady=6)
        c_ent = ctk.CTkEntry(f, width=210, font=ctk.CTkFont(family="Segoe UI", size=11))
        c_ent.grid(row=2, column=1, sticky="e", pady=6)
        c_ent.insert(0, acc.get("character", ""))

        ctk.CTkLabel(f, text="Server:", font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=3, column=0, sticky="w", pady=6)
        cur_s = int(acc.get("server", 1))
        s_combo = ModernOptionMenu(f, values=[f"Server {s}" for s in range(1, 9)], width=210, font=ctk.CTkFont(family="Segoe UI", size=11))
        s_combo.set(f"Server {cur_s}")
        s_combo.grid(row=3, column=1, sticky="e", pady=6)

        def _save_edit():
            p = p_ent.get().strip()
            c = c_ent.get().strip()
            s = int(s_combo.get().replace("Server ", "").strip())
            if self.account_mgr:
                self.account_mgr.update_account(username=u_name, password=p, character=c, server=s)
            self.refresh_autologin_table()
            self.append_autologin_log(f"✏️ Đã cập nhật tài khoản '{u_name}' (Nhân vật '{c}', Server {s})")
            dlg.destroy()

        btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_box.pack(pady=(16, 0))
        ctk.CTkButton(btn_box, text="Lưu Thay Đổi", width=110, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), command=_save_edit).pack(side="left", padx=6)
        ctk.CTkButton(btn_box, text="Đóng", width=80, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(family="Segoe UI", size=11), command=dlg.destroy).pack(side="left", padx=6)

    def delete_account_ui(self, username: str):
        """Xóa tài khoản khỏi danh sách."""
        if self.account_mgr:
            self.account_mgr.remove_account(username)
        self.refresh_autologin_table()
        self.append_autologin_log(f"🗑️ Đã xóa tài khoản '{username}'")

    def _find_or_allocate_slot(self, slot_choice: str) -> Optional[int]:
        """Xác định hoặc cấp phát Slot cho tài khoản."""
        if slot_choice.startswith("Slot #"):
            try:
                s_idx = int(slot_choice.replace("Slot #", "").strip())
                return s_idx
            except Exception:
                pass

        # Tự động: tìm slot đầu tiên chưa gán PID hoặc PID đã chết
        for ctrl in self.controllers:
            if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
                return ctrl.slot_idx

        # Nếu tất cả slot đều đang dùng, tự động thêm slot mới nếu chưa vượt MAX_SLOTS
        if len(self.controllers) < MAX_SLOTS:
            self.add_new_slot()
            return self.controllers[-1].slot_idx

        return None

    def launch_single_account_ui(self, acc: Dict[str, Any], slot_choice: str = "Tự động"):
        """Khởi chạy và AutoLogin cho 1 tài khoản đơn lẻ trên background thread."""
        u = acc.get("username", "")
        c = acc.get("character", "")
        s = acc.get("server", 1)

        def _worker():
            self.autologin_status_lbl.configure(text=f"Đang mở {u}...", text_color="#f59e0b")
            self.append_autologin_log(f"🚀 [Account: {u}] Bắt đầu mở MEGAMU.exe...")

            target_slot = self._find_or_allocate_slot(slot_choice)
            pid = self.account_mgr.launch_single_account(acc, on_log=self.append_autologin_log)
            if pid:
                if target_slot and 1 <= target_slot <= len(self.controllers):
                    ctrl = self.controllers[target_slot - 1]
                    self.after(0, lambda: self._bind_pid_to_slot_ui(ctrl, pid, c or u))
                self.after(0, lambda: self.autologin_status_lbl.configure(text=f"Đã login {u} (PID {pid})", text_color="#22c55e"))
            else:
                self.after(0, lambda: self.autologin_status_lbl.configure(text=f"Lỗi mở {u}!", text_color="#ef4444"))

        threading.Thread(target=_worker, daemon=True).start()

    def _bind_pid_to_slot_ui(self, ctrl: SlotController, pid: int, char_name: str):
        """Gán PID vào SlotController và cập nhật giao diện Dashboard."""
        ctrl.attach_pid(pid)
        if char_name and char_name != "(Mặc định)":
            ctrl.char_name = char_name
            ctrl.last_known_char_name = char_name
        el = self.slot_ui_elements.get(ctrl.slot_idx)
        if el and el.get("proc_var"):
            el["proc_var"].set(f"{ctrl.char_name} ({pid})")
        self.update_slot_ui_telemetry(ctrl.slot_idx, ctrl.char_name, ctrl.level, ctrl.coords)
        self.update_header_stats()
        self.log_message(f"[Slot {ctrl.slot_idx:02d}] Đã gán PID {pid} ({ctrl.char_name}) và kích hoạt telemetry!", "SUCCESS")

    def send_login_to_slot_ui(self, acc: Dict[str, Any], slot_choice: str):
        """Gửi ngay lệnh AutoLogin native vào game client của Slot đã chọn."""
        target_slot = self._find_or_allocate_slot(slot_choice)
        if not target_slot or target_slot > len(self.controllers):
            self.append_autologin_log(f"⚠️ Không xác định được Slot để gửi lệnh AutoLogin!")
            return
        ctrl = self.controllers[target_slot - 1]
        if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
            self.append_autologin_log(f"⚠️ Slot #{target_slot:02d} chưa có game MEGAMU nào đang mở! Hãy nhấn '🚀 Mở & Login'.")
            return

        def _worker():
            u = acc.get("username", "")
            c = acc.get("character", "")
            s = acc.get("server", 1)
            ok = self.account_mgr.login_existing_pid(ctrl.assigned_pid, acc, on_log=self.append_autologin_log)
            if ok:
                if c and c != "(Mặc định)":
                    ctrl.char_name = c
                    ctrl.last_known_char_name = c
                    self.after(0, lambda: self.update_slot_ui_telemetry(ctrl.slot_idx, ctrl.char_name, ctrl.level, ctrl.coords))

        threading.Thread(target=_worker, daemon=True).start()

    def batch_launch_all_accounts(self):
        """Khởi chạy đồng loạt tất cả tài khoản đang bật theo chế độ Batching giãn cách."""
        if not self.account_mgr:
            return
        enabled = self.account_mgr.get_enabled_accounts()
        if not enabled:
            self.append_autologin_log("⚠️ Không có tài khoản nào được tích chọn để mở!")
            return

        try:
            delay_sec = max(1.0, float(self.autologin_delay_var.get() or 3.0))
        except Exception:
            delay_sec = 3.0

        def _batch_worker():
            self.btn_autologin_all.configure(state="disabled")
            self.append_autologin_log(f"🌟 BẮT ĐẦU MỞ ĐỒNG LOẠT {len(enabled)} TÀI KHOẢN (Giãn cách {delay_sec}s)...")

            for idx, acc in enumerate(enabled):
                u = acc.get("username", "")
                c = acc.get("character", "")
                self.after(0, lambda u_name=u, i=idx: self.autologin_status_lbl.configure(
                    text=f"Đang mở [{i+1}/{len(enabled)}] {u_name}...", text_color="#f59e0b"
                ))

                # Tìm slot tương ứng
                target_slot = self._find_or_allocate_slot("Tự động")
                pid = self.account_mgr.launch_single_account(acc, on_log=self.append_autologin_log)
                if pid and target_slot and 1 <= target_slot <= len(self.controllers):
                    ctrl = self.controllers[target_slot - 1]
                    self.after(0, lambda c_ref=ctrl, p=pid, ch=c or u: self._bind_pid_to_slot_ui(c_ref, p, ch))

                if idx < len(enabled) - 1:
                    self.append_autologin_log(f"⏳ Chờ {delay_sec}s trước khi mở tài khoản kế tiếp...")
                    time.sleep(delay_sec)

            self.after(0, lambda: self.autologin_status_lbl.configure(text=f"Hoàn tất {len(enabled)} tài khoản!", text_color="#22c55e"))
            self.after(0, lambda: self.btn_autologin_all.configure(state="normal"))
            self.append_autologin_log(f"🎉 HOÀN TẤT BATCHING AUTO LOGIN CHO TOÀN BỘ {len(enabled)} TÀI KHOẢN!")

        threading.Thread(target=_batch_worker, daemon=True).start()

    def append_autologin_log(self, text: str):
        if hasattr(self, "autologin_log_txt"):
            t_str = time.strftime("%H:%M:%S")
            self.after(0, lambda: self._do_append_autologin_log(t_str, text))

    def _do_append_autologin_log(self, t_str: str, text: str):
        if hasattr(self, "autologin_log_txt"):
            self._safe_append_textbox(self.autologin_log_txt, text)

    def clear_autologin_log(self):
        if hasattr(self, "autologin_log_txt"):
            self.autologin_log_txt.delete("1.0", "end")

    # ==========================================================================
    # XỬ LÝ SỰ KIỆN TỪNG SLOT
    # ==========================================================================
    def on_slot_pid_selected(self, slot_idx: int, val: str):
        ctrl = self.controllers[slot_idx - 1]
        if val in ("--", tr("select"), "") or not val:
            ctrl.detach()
            ctrl.assigned_pid = None
            self.update_slot_ui_telemetry(slot_idx, "---", "LV --", "---")
            ctrl.set_status(tr("status_disconnected"))
            if hasattr(self, "update_moss_slot_telemetry"):
                self.update_moss_slot_telemetry(slot_idx, "---", None)
            if hasattr(self, "update_mirror_slot_telemetry"):
                self.update_mirror_slot_telemetry(slot_idx, "---", None)
            self.update_slot_run_button_state(slot_idx)
            self.log_message(f"[Slot {slot_idx:02d}] Đã hủy gán game.", "INFO")
            return

        try:
            import re
            m = re.search(r"\((\d+)\)", val)
            if m:
                pid = int(m.group(1))
            else:
                pid = int(val.split(" - ")[0].strip())

            # Nếu PID đã chết, thử tự động reconnect tìm game mới
            if not is_megamu_process_alive(pid):
                self.log_message(f"[Slot {slot_idx:02d}] Cửa sổ MEGAMU (PID {pid}) đã đóng. Đang tự động quét và kết nối lại...", "WARNING")
                ctrl.reconnect_game()
                return

            # Chống gán trùng: Nếu PID này đang gán cho slot khác, tự động hủy ở slot đó
            for other_idx in range(1, len(self.controllers) + 1):
                if other_idx != slot_idx:
                    other_ctrl = self.controllers[other_idx - 1]
                    if other_ctrl.assigned_pid == pid:
                        other_ctrl.detach()
                        other_ctrl.assigned_pid = None
                        other_el = self.slot_ui_elements.get(other_idx)
                        if other_el and other_el.get("proc_combo"):
                            other_el["proc_combo"].set("--")
                        self.update_slot_ui_telemetry(other_idx, "---", "LV --", "---")
                        other_ctrl.set_status(tr("status_disconnected"))
                        self.update_slot_run_button_state(other_idx)
                        self.log_message(f"[Slot {other_idx:02d}] Tự động bỏ gán PID {pid} vì đã chuyển sang Slot {slot_idx:02d}.", "INFO")

            ctrl.attach_pid(pid)
            if hasattr(self, "update_moss_slot_telemetry"):
                self.update_moss_slot_telemetry(slot_idx, ctrl.char_name, pid)
            if hasattr(self, "update_mirror_slot_telemetry"):
                self.update_mirror_slot_telemetry(slot_idx, ctrl.char_name, pid, ctrl.coords)
            self.update_slot_run_button_state(slot_idx)
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Không thể gán PID: {e}", "ERROR")

    def on_slot_status_clicked(self, slot_idx: int):
        """Khi người dùng click vào nhãn trạng thái 'Mất kết nối', tự động kết nối lại."""
        ctrl = self.controllers[slot_idx - 1]
        is_dead = (ctrl.assigned_pid and not is_megamu_process_alive(ctrl.assigned_pid))
        is_disc = ctrl.status in (tr("game_closed"), tr("status_disconnected"), "Game đã đóng", "Mất kết nối")
        if is_dead or is_disc or not ctrl.assigned_pid:
            self.log_message(f"[Slot {slot_idx:02d}] Đang thử kết nối lại tài khoản...", "INFO")
            ok = ctrl.reconnect_game()
            if not ok:
                self.log_message(f"[Slot {slot_idx:02d}] Kết nối lại thất bại: Chưa tìm thấy cửa sổ MEGAMU mới.", "WARNING")

    def on_proc_combo_opened(self, slot_idx: int):
        """Tự động làm mới danh sách Game khi người dùng bấm vào ComboBox."""
        self.refresh_games()

    def on_slot_profile_selected(self, slot_idx: int, val: str):
        try:
            p_idx = int(val.replace("Config ", "").strip())
            ctrl = self.controllers[slot_idx - 1]
            ctrl.set_profile(p_idx)
            self.slot_assignments[slot_idx] = p_idx
            el = self.slot_ui_elements.get(slot_idx)
            if el:
                if el.get("profile_var"):
                    el["profile_var"].set(f"Config {p_idx}")
                if el.get("preset_combo"):
                    el["preset_combo"].set(f"Config {p_idx}")
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
            self.log_message(f"[Slot {slot_idx:02d}] Đã đổi tuyến đường sang: Config {p_idx}", "INFO")
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Lỗi đổi cấu hình: {e}", "ERROR")

    def on_slot_auto_toggle(self, slot_idx: int):
        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng Auto đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để tiếp tục sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        ctrl = self.controllers[slot_idx - 1]
        if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
            self.log_message(f"[Slot {slot_idx:02d}] Chưa gán nhân vật hoặc game chưa kết nối, không thể bật Auto!", "WARNING")
            self.update_slot_run_button_state(slot_idx)
            return
        ctrl.toggle_auto()

    def on_toggle_slot_devil(self, slot_idx: int):
        """Bật/tắt chế độ tự động tham gia Devil Square cho slot."""
        ctrl = self.controllers[slot_idx - 1]
        ctrl.auto_devil = not ctrl.auto_devil
        ConfigPersistenceManager.save_event_config(
            slot_idx=slot_idx,
            auto_devil=ctrl.auto_devil,
            devil_min_resets=ctrl.devil_min_resets,
            devil_max_resets=ctrl.devil_max_resets,
            devil_ticket_type=getattr(ctrl, "devil_ticket_type", "auto"),
            auto_reset=ctrl.auto_reset,
            auto_add_point=ctrl.auto_add_point,
            reset_level=ctrl.reset_level,
            stat_mode=ctrl.stat_mode,
            custom_class=ctrl.custom_class,
            stat_ratio=ctrl.stat_ratio
        )
        if ctrl.worker and ctrl.worker.running and hasattr(ctrl.worker, 'update_config'):
            ctrl.worker.update_config({
                "auto_devil": ctrl.auto_devil,
                "devil_min_resets": ctrl.devil_min_resets,
                "devil_max_resets": ctrl.devil_max_resets
            })

        el = self.slot_ui_elements.get(slot_idx)
        if el and el.get("btn_devil"):
            if ctrl.auto_devil:
                el["btn_devil"].configure(fg_color="#4c0519", text_color="#f43f5e", border_color="#e11d48", hover_color="#881337")
            else:
                el["btn_devil"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")

        state_str = "BẬT" if ctrl.auto_devil else "TẮT"
        self.log_message(f"[Slot {slot_idx:02d}] Đã {state_str} tính năng Tự Động Đi Devil Square.", "SUCCESS" if ctrl.auto_devil else "INFO")

        if ctrl.auto_devil:
            eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine and ctrl.assigned_pid else None)
            if eng and eng.is_ready and hasattr(eng, "get_devil_ticket_info"):
                try:
                    t_info = eng.get_devil_ticket_info()
                    if not t_info.get("hasTicket"):
                        self.log_message(f"[Slot {slot_idx:02d}] ❌ Không có vé Devil Square (cả vé thường lẫn vé master) trong hòm đồ!", "WARNING")
                    else:
                        has_m = bool(t_info.get("hasMasterTicket"))
                        has_n = bool(t_info.get("hasNormalTicket"))
                        if has_m and has_n:
                            self.log_message(f"[Slot {slot_idx:02d}] 🎫 Đã phát hiện cả Vé Master ({t_info.get('masterCount', 1)}) và Vé thường ({t_info.get('normalCount', 1)})!", "INFO")
                        elif has_m:
                            self.log_message(f"[Slot {slot_idx:02d}] 🎫 Đã phát hiện Vé Master Devil Square ({t_info.get('masterCount', 1)} vé)!", "INFO")
                        else:
                            self.log_message(f"[Slot {slot_idx:02d}] 🎫 Đã phát hiện Vé thường Devil Square ({t_info.get('normalCount', 1)} vé)!", "INFO")
                except Exception:
                    pass

    def on_toggle_slot_reset(self, slot_idx: int):
        """Bật/tắt chế độ Auto Reset cho slot."""
        ctrl = self.controllers[slot_idx - 1]
        new_state = not ctrl.auto_reset
        ctrl.auto_reset = new_state
        ConfigPersistenceManager.save_event_config(
            slot_idx=slot_idx,
            auto_devil=ctrl.auto_devil,
            auto_reset=ctrl.auto_reset,
            auto_add_point=ctrl.auto_add_point,
            reset_level=ctrl.reset_level,
            stat_mode=ctrl.stat_mode,
            custom_class=ctrl.custom_class,
            stat_ratio=ctrl.stat_ratio
        )
        if ctrl.worker and ctrl.worker.running and hasattr(ctrl.worker, 'update_config'):
            ctrl.worker.update_config({
                "auto_reset": ctrl.auto_reset,
                "reset_level": ctrl.reset_level
            })

        el = self.slot_ui_elements.get(slot_idx)
        if el and el.get("btn_reset"):
            if new_state:
                el["btn_reset"].configure(fg_color="#064e3b", text_color="#10b981", border_color="#059669", hover_color="#047857")
            else:
                el["btn_reset"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")

        state_str = "BẬT" if new_state else "TẮT"
        self.log_message(f"[Slot {slot_idx:02d}] Đã {state_str} tính năng Tự Động Reset (LV {ctrl.reset_level}).", "SUCCESS" if new_state else "INFO")

    def on_toggle_slot_point(self, slot_idx: int):
        """Bật/tắt chế độ Auto Cộng Point cho slot."""
        ctrl = self.controllers[slot_idx - 1]
        new_state = not ctrl.auto_add_point
        ctrl.auto_add_point = new_state
        ConfigPersistenceManager.save_event_config(
            slot_idx=slot_idx,
            auto_devil=ctrl.auto_devil,
            auto_reset=ctrl.auto_reset,
            auto_add_point=ctrl.auto_add_point,
            reset_level=ctrl.reset_level,
            stat_mode=ctrl.stat_mode,
            custom_class=ctrl.custom_class,
            stat_ratio=ctrl.stat_ratio
        )
        if ctrl.worker and ctrl.worker.running and hasattr(ctrl.worker, 'update_config'):
            ctrl.worker.update_config({
                "auto_add_point": ctrl.auto_add_point,
                "stat_mode": ctrl.stat_mode,
                "custom_class": ctrl.custom_class,
                "stat_ratio": ctrl.stat_ratio
            })

        el = self.slot_ui_elements.get(slot_idx)
        if el and el.get("btn_point"):
            if new_state:
                el["btn_point"].configure(fg_color="#075985", text_color="#38bdf8", border_color="#0284c7", hover_color="#0369a1")
            else:
                el["btn_point"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")

        state_str = "BẬT" if new_state else "TẮT"
        self.log_message(f"[Slot {slot_idx:02d}] Đã {state_str} tính năng Tự Động Cộng Point.", "SUCCESS" if new_state else "INFO")

    def on_quick_devil_enter(self, slot_idx: int):
        """Kích hoạt đi Devil Square ngay lập tức qua native injection (Zero-Mouse, không click NPC)."""
        ctrl = self.controllers[slot_idx - 1]
        if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
            self.log_message(f"[Slot {slot_idx:02d}] Chưa kết nối Game!", "WARNING")
            return
        eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine else None)
        if not eng or not eng.is_ready:
            self.log_message(f"[Slot {slot_idx:02d}] Direct Engine chưa sẵn sàng!", "WARNING")
            return

        def _do_enter():
            # Tạm dừng Auto Train nếu đang chạy để không bị worker gửi lệnh warp giật ngược về bãi train
            was_training = False
            if hasattr(ctrl, "worker") and ctrl.worker and ctrl.worker.running:
                was_training = True
                ctrl.worker.pause_for_event("Người dùng bấm đi Devil Square thủ công")

            # 1. Kiểm tra bản đồ hiện tại. Đi Devil Square bắt buộc phải đứng ở Event Square (map 53 / 40)
            try:
                pinfo = eng.get_player_info()
            except Exception:
                pinfo = None
            if not pinfo:
                self.log_message(f"[Slot {slot_idx:02d}] Chưa đọc được thông tin nhân vật!", "WARNING")
                if was_training and ctrl.worker:
                    ctrl.worker.resume_from_event("Không đọc được thông tin nhân vật")
                return

            cmap = pinfo.get("mapId", -1)
            # Nếu nhân vật đã ở trong map Devil Square
            if DevilService.is_in_devil_map(cmap) or (hasattr(eng, "is_devil_event_map") and eng.is_devil_event_map()):
                self.log_message(f"[Slot {slot_idx:02d}] Nhân vật đã ở trong Devil Square! Đang kiểm tra bật MuHelper...", "INFO")
                if hasattr(eng, "start_helper"):
                    eng.start_helper()
                return

            # Nếu chưa ở Event Square (map 53 hoặc 40), tự động chuyển sang Event Square (/m ev) trước
            if cmap not in (53, 40):
                self.log_message(f"[Slot {slot_idx:02d}] 📍 Đang chuyển sang bản đồ Event Square (/m ev) để tiếp cận NPC Charon...", "INFO")
                eng.send_chat("/m ev")
                in_ev = False
                for step in range(12):  # Chờ tối đa 6 giây
                    time.sleep(0.5)
                    try:
                        fresh_inf = eng.get_player_info()
                        if fresh_inf and fresh_inf.get("mapId", -1) in (53, 40):
                            in_ev = True
                            break
                        if step == 4 and not in_ev:
                            eng.send_chat("/m ev")
                            eng.send_chat("/warp ev")
                    except Exception:
                        pass
                if not in_ev:
                    self.log_message(f"[Slot {slot_idx:02d}] ❌ Không thể sang bản đồ Event Square (/m ev)! Vui lòng kiểm tra lại level hoặc zen của nhân vật.", "WARNING")
                    if was_training and ctrl.worker:
                        ctrl.worker.resume_from_event("Không thể chuyển sang Event Square")
                    return
                time.sleep(0.4)

            # 1.5. Tiếp cận NPC Charon tại Event Square (tọa độ 225, 52):
            char_pos = eng.get_player_info() or {}
            cur_x = char_pos.get("tileX", char_pos.get("x", 0))
            cur_y = char_pos.get("tileY", char_pos.get("y", 0))
            if abs(cur_x - 225) > 5 or abs(cur_y - 52) > 5:
                self.log_message(f"[Slot {slot_idx:02d}] 🚶 Đang di chuyển lại gần NPC Charon (225, 52)...", "INFO")
                if hasattr(eng, "start_auto_move"):
                    eng.start_auto_move(225, 52, helper=False)
                elif hasattr(eng, "move_to"):
                    eng.move_to(225, 52)
                for _ in range(12):  # Chờ tối đa 6 giây cho nhân vật chạy lại gần
                    time.sleep(0.5)
                    pos = eng.get_player_info() or {}
                    nx = pos.get("tileX", pos.get("x", 0))
                    ny = pos.get("tileY", pos.get("y", 0))
                    if abs(nx - 225) <= 5 and abs(ny - 52) <= 5:
                        break
                if hasattr(eng, "cancel_move"):
                    try: eng.cancel_move()
                    except Exception: pass
                if hasattr(eng, "stop_auto_move"):
                    try: eng.stop_auto_move()
                    except Exception: pass
                time.sleep(0.3)

            # Dừng mọi hành động di chuyển dở để nhân vật đứng yên
            if hasattr(eng, "cancel_move"):
                try: eng.cancel_move()
                except Exception: pass
            if hasattr(eng, "stop_auto_move"):
                try: eng.stop_auto_move()
                except Exception: pass

            # 2. Quét thông tin vé trong hòm đồ (Cả vé thường lẫn vé master)
            t_info = eng.get_devil_ticket_info() if hasattr(eng, "get_devil_ticket_info") else {}
            has_ticket = bool(t_info.get("hasTicket"))
            has_master = bool(t_info.get("hasMasterTicket"))
            has_normal = bool(t_info.get("hasNormalTicket"))

            if has_master and has_normal:
                self.log_message(f"[Slot {slot_idx:02d}] 🎫 Có cả Vé Master ({t_info.get('masterCount', 1)}) và Vé thường ({t_info.get('normalCount', 1)})!", "INFO")
            elif has_master:
                self.log_message(f"[Slot {slot_idx:02d}] 🎫 Phát hiện Vé Master Devil Square ({t_info.get('masterCount', 1)} vé)!", "INFO")
            elif has_normal:
                self.log_message(f"[Slot {slot_idx:02d}] 🎫 Phát hiện Vé thường Devil Square ({t_info.get('normalCount', 1)} vé)!", "INFO")
            else:
                self.log_message(f"[Slot {slot_idx:02d}] ℹ️ Không phát hiện vé trong hòm đồ - Đang gọi NPC Charon để Game phát thông báo trực tiếp...", "INFO")
                # Hiển thị thông báo trực tiếp trên màn hình game
                try:
                    eng.send_chat("[DEVIL] Bạn không có Vé Devil Square (hoặc cấp độ vé không phù hợp)!")
                except Exception:
                    pass

            # 3. Gửi lệnh trực tiếp vào NPC Charon tại Event Square:
            # - Bỏ qua hoàn toàn hộp thoại xác nhận (Zero-confirm)
            # - Nếu chưa mở cổng: GameServer sẽ phát thông báo cổng đóng trên màn hình game
            # - Nếu không có vé: NPC Charon sẽ hiển thị popup dialog trong game
            ticket_desc = "Vé Master" if has_master else "Vé thường"
            self.log_message(f"[Slot {slot_idx:02d}] 🚪 Đang tương tác NPC Charon tại Event Square (Bỏ qua confirm)...", "INFO")
            if has_ticket:
                try:
                    eng.send_chat(f"[DEVIL] Đang tương tác NPC Charon vào Devil Square ({ticket_desc})...")
                except Exception:
                    pass

            t_pref = getattr(ctrl, "devil_ticket_type", "auto")
            res = eng.enter_devil(ticket_preference=t_pref)
            ds_lvl = "?"
            if isinstance(res, dict):
                ds_lvl = res.get("ds_level") or res.get("dsLevel") or "?"

            # 4. Xác nhận xem nhân vật đã vào map Devil Square (Map 9 hoặc 32) hay chưa
            entered_ds = False
            for _ in range(8):  # Chờ 4 giây phản hồi từ GameServer
                time.sleep(0.5)
                try:
                    inf = eng.get_player_info()
                    mid = inf.get("mapId", -1) if inf else -1
                    if mid in (9, 32) or (hasattr(eng, "is_devil_event_map") and eng.is_devil_event_map()):
                        entered_ds = True
                        break
                except Exception:
                    pass

            if not entered_ds:
                if not has_ticket:
                    self.log_message(
                        f"[Slot {slot_idx:02d}] ⚠️ Nhân vật không có vé Devil Square (Đã phát thông báo thiếu vé trực tiếp trên màn hình Game)!",
                        "WARNING"
                    )
                else:
                    # Gửi thông báo trực tiếp trên màn hình Game qua lệnh chat native
                    try:
                        eng.send_chat("[DEVIL] Chưa đến giờ mở cửa sự kiện Devil Square! Cổng hiện đang đóng.")
                        if hasattr(eng, "click_devil_npc"):
                            eng.click_devil_npc()
                    except Exception:
                        pass
                    self.log_message(
                        f"[Slot {slot_idx:02d}] ⏰ Đã gửi lệnh vào NPC Charon! Nếu chưa vào được cổng, vui lòng xem thông báo cổng đóng hiển thị trực tiếp trên Game.",
                        "INFO"
                    )
                if was_training and hasattr(ctrl, "worker") and ctrl.worker:
                    ctrl.worker.resume_from_event("Chưa vào được Devil Square")
                return

            # 5. Đã vào map Devil Square thành công: Tự động bật MuHelper & Lập watcher tự Reset khi kết thúc
            self.log_message(f"[Slot {slot_idx:02d}] ✅ Đã vào Devil Square thành công (DS {ds_lvl})! Đang tự động kích hoạt MuHelper...", "SUCCESS")
            time.sleep(1.0)
            if hasattr(eng, "start_helper"):
                eng.start_helper()

            def _devil_watcher():
                # Theo dõi trong suốt quá trình đi Devil Square đến khi rời khỏi map
                while True:
                    try:
                        inf = eng.get_player_info()
                        mid = inf.get("mapId", -1) if inf else -1
                        in_ds = (mid in (9, 32)) or (hasattr(eng, "is_devil_event_map") and eng.is_devil_event_map())
                        if not in_ds:
                            self.log_message(f"[Slot {slot_idx:02d}] 🏁 Sự kiện Devil Square kết thúc! Đang tự động thực hiện /reset...", "SUCCESS")
                            time.sleep(2.0)
                            if hasattr(eng, "do_reset"):
                                eng.do_reset()
                            else:
                                eng.send_chat("/reset")
                            if hasattr(ctrl, "worker") and ctrl.worker:
                                ctrl.worker.current_stage_key = None
                                ctrl.worker.arrived_at_spot = False
                                ctrl.worker.in_devil_square = False
                            break
                    except Exception:
                        pass
                    time.sleep(2.0)

            threading.Thread(target=_devil_watcher, daemon=True).start()

        threading.Thread(target=_do_enter, daemon=True).start()

    def on_quick_reset(self, slot_idx: int):
        """Thực hiện lệnh /reset ngay lập tức."""
        ctrl = self.controllers[slot_idx - 1]
        if not ctrl.assigned_pid or not is_megamu_process_alive(ctrl.assigned_pid):
            self.log_message(f"[Slot {slot_idx:02d}] Chưa kết nối Game!", "WARNING")
            return
        eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine else None)
        if not eng or not eng.is_ready:
            self.log_message(f"[Slot {slot_idx:02d}] Direct Engine chưa sẵn sàng!", "WARNING")
            return
        res = eng.do_reset()
        is_ok = False
        err_msg = "Lỗi gửi lệnh"
        if isinstance(res, dict):
            is_ok = bool(res.get("ok") or res.get("success"))
            err_msg = res.get("error") or res.get("reason") or err_msg
        else:
            is_ok = bool(res)

        if is_ok:
            self.log_message(f"[Slot {slot_idx:02d}] Đã gửi lệnh /reset vào game thành công!", "SUCCESS")
        else:
            self.log_message(f"[Slot {slot_idx:02d}] Gửi lệnh /reset thất bại: {err_msg}", "WARNING")

    def open_devil_global_config_dialog(self):
        """Mở cửa sổ cấu hình mốc Reset & Vé đi Devil Square cho toàn bộ tài khoản."""
        from ui.modals.devil_modal import open_devil_global_config_dialog as _open
        return _open(self)

    def open_slot_stat_ratio_dialog(self, slot_idx: int):
        """Mở hộp thoại cấu hình tỷ lệ cộng điểm (Point Stat Ratio) cho từng Slot."""
        from ui.modals.stats_modal import open_slot_stat_ratio_dialog as _open
        return _open(self, slot_idx)

    def update_slot_ui_status(self, slot_idx: int, text: str):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if not el or not el.get("status_lbl"):
                return
            cache = getattr(self, "_slot_telemetry_cache", {}).setdefault(slot_idx, {})
            if cache.get("status_text") == text:
                return
            cache["status_text"] = text
            lbl = el["status_lbl"]
            tl = str(text).lower()
            if "tự động đánh" in tl or "running" in tl or "đang chạy" in tl or "at spot" in tl or "tại bãi" in tl or "executando" in tl:
                lbl.configure(text=tr("status_running"), text_color="#4ade80", cursor="")
            elif "moving" in tl or "chạy ra bãi" in tl or "di chuyển" in tl or "map" in tl or "movendo" in tl:
                lbl.configure(text=tr("status_moving"), text_color="#facc15", cursor="")
            elif "game đã đóng" in tl or "game_closed" in tl or "closed" in tl or "disconnect" in tl or "pk" in tl or "mất kết nối" in tl or "desconectado" in tl:
                lbl.configure(text=tr("status_disconnected"), text_color="#f87171", cursor="hand2")
            elif "đã kết nối" in tl or "connected" in tl or "stopped" in tl or "đã dừng" in tl or "parado" in tl:
                lbl.configure(text=tr("status_stopped"), text_color="#e2e8f0", cursor="")
            elif "idle" in tl or "chờ" in tl or "aguardando" in tl:
                lbl.configure(text=tr("status_idle"), text_color="#94a3b8", cursor="")
            else:
                lbl.configure(text=str(text), text_color="#94a3b8", cursor="")
        try:
            self.after(0, _apply)
        except Exception:
            pass

    def update_slot_run_button_state(self, slot_idx: int):
        """Cập nhật trạng thái enable/disable và màu sắc của nút Chạy Auto: chỉ kích hoạt khi đã gán nhân vật."""
        el = self.slot_ui_elements.get(slot_idx)
        if not el or not el.get("btn_toggle"):
            return
        btn = el["btn_toggle"]
        if slot_idx < 1 or slot_idx > len(self.controllers):
            return
        ctrl = self.controllers[slot_idx - 1]

        is_running = bool((ctrl.worker and ctrl.worker.running) or ctrl.auto_requested)
        has_character = bool(ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid))

        cache = getattr(self, "_slot_run_btn_cache", {}).setdefault(slot_idx, {})
        current_state = (is_running, has_character)
        if cache.get("state") == current_state:
            return
        cache["state"] = current_state

        if is_running:
            btn.configure(
                state="normal",
                image=getattr(self, "_icon_stop_12", None) or UiIconFactory.get("stop", color="#ffffff", size=(12, 12)),
                text="",
                fg_color="#dc2626",
                hover_color="#b91c1c",
                border_color="#ef4444"
            )
            add_tooltip(
                btn,
                f"[Slot #{slot_idx:02d}] ⏹ Dừng Auto\n"
                "Đang chạy tự động. Nhấn để tạm dừng."
            )
        elif has_character:
            btn.configure(
                state="normal",
                image=getattr(self, "_icon_play_12", None) or UiIconFactory.get("play", color="#38bdf8", size=(11, 11)),
                text="",
                fg_color="#161a24",
                hover_color="#222838",
                border_color="#2b3244"
            )
            add_tooltip(
                btn,
                f"[Slot #{slot_idx:02d}] ▶ Chạy Auto\n"
                f"Đã gán: {ctrl.char_name or 'MEGAMU'} (PID {ctrl.assigned_pid}). Nhấn để bắt đầu."
            )
        else:
            btn.configure(
                state="disabled",
                image=getattr(self, "_icon_play_12_disabled", None) or UiIconFactory.get("play", color="#475569", size=(11, 11)),
                text="",
                fg_color="#0f1219",
                hover_color="#0f1219",
                border_color="#1a202c"
            )
            add_tooltip(
                btn,
                f"[Slot #{slot_idx:02d}] ⚠️ Chưa gán nhân vật\n"
                "Vui lòng chọn nhân vật MEGAMU ở cột 'Nhân vật / PID' để kích hoạt nút chạy."
            )

    def update_slot_ui_auto(self, slot_idx: int, is_on: bool):
        def _apply():
            self.update_slot_run_button_state(slot_idx)
        try:
            self.after(0, _apply)
            self.after(0, self.update_master_run_button)
        except Exception:
            _apply()
            self.update_master_run_button()

    def update_slot_ui_telemetry(self, slot_idx: int, name: str, lvl: str, coords: str, points: Optional[int] = None, class_code: Optional[str] = None):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if not el:
                return
            ctrl = self.controllers[slot_idx - 1]
            cache = getattr(self, "_slot_telemetry_cache", {}).setdefault(slot_idx, {})

            # 1. Proc Combo / Name display (Dirty check)
            c_tag = f"[{class_code}] " if (class_code and class_code.strip()) else (f"[{ctrl.class_code}] " if ctrl.class_code else "")
            if el.get("proc_var") and name and name != "---":
                pid_str = f"{ctrl.assigned_pid}" if ctrl.assigned_pid else ""
                disp_str = f"{c_tag}{name} ({pid_str})" if pid_str else f"{c_tag}{name}"
                if cache.get("disp_str") != disp_str:
                    cache["disp_str"] = disp_str
                    curr = el["proc_var"].get()
                    if curr in ("--", tr("select"), "") or name not in curr or (c_tag and not curr.startswith("[")):
                        el["proc_var"].set(disp_str)

            # 2. Level, Reset, Progress Bar, EXP (Dirty check)
            if lvl and lvl != "---":
                try:
                    lvl_num = int(lvl)
                except Exception:
                    lvl_num = 0
                if lvl_num > 0:
                    rs_cnt = getattr(ctrl, "current_resets", 0)
                    lvl_state = (lvl_num, rs_cnt)
                    if cache.get("lvl_state") != lvl_state:
                        cache["lvl_state"] = lvl_state
                        rr_suffix = f" ({rs_cnt}rr)" if rs_cnt > 0 else ""
                        if el.get("lvl_lbl"):
                            txt = f"M.LV {lvl_num}{rr_suffix}" if lvl_num >= 400 else f"LV {lvl_num}{rr_suffix}"
                            col = "#38bdf8" if lvl_num >= 400 else "#94a3b8"
                            el["lvl_lbl"].configure(text=txt, text_color=col)
                        if el.get("prog_bar"):
                            ratio = round(min(1.0, max(0.05, (lvl_num % 400) / 400.0 if lvl_num >= 400 else lvl_num / 400.0)), 2)
                            el["prog_bar"].set(ratio)
                        if el.get("exp_lbl"):
                            exp_cur = lvl_num * 3717 + 800
                            exp_max = 800 if lvl_num >= 400 else 400
                            el["exp_lbl"].configure(text=f"{exp_cur:,} / {exp_max} EXP".replace(",", "."))

                    # Profile Var (Dirty check)
                    if el.get("profile_var"):
                        expected_cfg = f"Config {ctrl.profile_index}"
                        if cache.get("cfg") != expected_cfg:
                            cache["cfg"] = expected_cfg
                            if el["profile_var"].get() != expected_cfg:
                                el["profile_var"].set(expected_cfg)

            # 3. Points (Dirty check)
            pts_val = points if points is not None else getattr(ctrl, "points", 0)
            if el.get("pts_lbl") and cache.get("pts_val") != pts_val:
                cache["pts_val"] = pts_val
                if pts_val > 0:
                    el["pts_lbl"].configure(text=f"⭐ {pts_val:,} pts", text_color="#10b981")
                else:
                    el["pts_lbl"].configure(text="⭐ 0 pts", text_color="#64748b")

            # 4. Coordinates (Dirty check)
            if el.get("coords_lbl"):
                if coords and coords.strip() and coords not in ("--,--", "--", "--, --"):
                    parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
                    if len(parts) >= 2:
                        c_disp = f"{parts[0]}, {parts[1]}"
                    else:
                        c_disp = coords.strip()
                else:
                    c_disp = "--, --"
                if cache.get("c_disp") != c_disp:
                    cache["c_disp"] = c_disp
                    el["coords_lbl"].configure(text=c_disp)

            # 5. Lazy Tab Update: Chỉ cập nhật widget Moss/Mirror nếu Tab đó ĐANG MỞ
            cur_tab = getattr(self, "active_tab", "")
            if cur_tab == "moss" and hasattr(self, "update_moss_slot_telemetry"):
                try:
                    self.update_moss_slot_telemetry(slot_idx, name, ctrl.assigned_pid)
                except Exception:
                    pass
            elif cur_tab == "mirror" and hasattr(self, "update_mirror_slot_telemetry"):
                try:
                    self.update_mirror_slot_telemetry(slot_idx, name, ctrl.assigned_pid, coords)
                except Exception:
                    pass
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    # ==========================================================================
    # CÁC NÚT ĐIỀU KHIỂN HÀNG LOẠT (BULK ACTIONS)
    # ==========================================================================
    def refresh_games(self):
        """Quét nhanh danh sách MEGAMU.exe không gây đơ lag GUI thread."""
        self.detected_games = enumerate_megamu_processes()
        options = ["--"]
        unresolved_pids = []

        if not hasattr(self, "_char_name_cache"):
            self._char_name_cache = {}

        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            if not char_name:
                char_name = self._char_name_cache.get(pid, "")
                if not char_name:
                    for c in self.controllers:
                        if c.assigned_pid == pid and c.char_name and c.char_name != "---":
                            char_name = c.char_name
                            self._char_name_cache[pid] = char_name
                            break
                if not char_name:
                    unresolved_pids.append(pid)
            else:
                self._char_name_cache[pid] = char_name

            disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
            options.append(disp)

        for i in self.slot_ui_elements.keys():
            el = self.slot_ui_elements.get(i)
            if el and el.get("proc_combo"):
                el["proc_combo"].configure(values=options)

        self.update_header_stats()

        # Nếu có tiến trình chưa rõ tên nhân vật, quét bất đồng bộ trong luồng ngầm
        if unresolved_pids:
            def _async_resolve():
                updated = False
                for p in unresolved_pids:
                    try:
                        from meg_navigator import ProcessMemoryReader
                        nm = ProcessMemoryReader.read_character_name(p)
                        if nm:
                            self._char_name_cache[p] = nm
                            updated = True
                    except Exception:
                        pass
                if updated:
                    def _sync_ui():
                        new_opts = ["--"]
                        for pk, t_str in sorted(self.detected_games.items()):
                            c_n = character_name_from_window_title(t_str) or self._char_name_cache.get(pk, "")
                            new_opts.append(f"{c_n} ({pk})" if c_n else f"MEGAMU ({pk})")
                        for idx_s in self.slot_ui_elements.keys():
                            e_s = self.slot_ui_elements.get(idx_s)
                            if e_s and e_s.get("proc_combo"):
                                e_s["proc_combo"].configure(values=new_opts)
                    self.after(0, _sync_ui)
            import threading
            threading.Thread(target=_async_resolve, daemon=True, name="AsyncResolveCharNames").start()

    def assign_all(self):
        """Gán toàn bộ các tiến trình MEGAMU đang mở vào các Slot trống (hỗ trợ linh hoạt 1, 2, 3, 4, 5, 6, 7, 8... tài khoản)."""
        self.refresh_games()
        # Chỉ coi PID là đã gán nếu PID đó thực sự đang tồn tại trên Windows
        assigned_pids = {c.assigned_pid for c in self.controllers if c.assigned_pid and is_megamu_process_alive(c.assigned_pid)}
        available_pids = [p for p in self.detected_games if p not in assigned_pids]

        if not available_pids:
            self.log_message("Không có tiến trình MEGAMU nào chưa được gán.", "WARNING")
            return

        lic_data = license_client.load_license_data() if license_client else {}
        is_valid = license_client.is_license_valid() if license_client else False
        max_allowed = int(lic_data.get("max_slots", 5 if not is_valid else 10))

        # 1. Tìm các slot trống hiện có
        target_slots = [c for c in self.controllers if not c.assigned_pid or not is_megamu_process_alive(c.assigned_pid)]
        target_slots.sort(key=lambda c: c.slot_idx)

        # 2. Nếu số game cần gán nhiều hơn số slot trống hiện tại -> tự động mở thêm slot mới (nếu chưa vượt giới hạn bản quyền)
        while len(target_slots) < len(available_pids) and len(self.controllers) < max_allowed and len(self.controllers) < MAX_SLOTS:
            cur_len = len(self.controllers)
            self.add_new_slot()
            if len(self.controllers) > cur_len:
                new_ctrl = self.controllers[-1]
                target_slots.append(new_ctrl)
            else:
                break

        assigned_count = 0
        for pid in list(available_pids):
            if not target_slots:
                break
            ctrl = target_slots.pop(0)
            ctrl.attach_pid(pid)
            # Cập nhật dropdown
            el = self.slot_ui_elements.get(ctrl.slot_idx)
            if el:
                title = self.detected_games.get(pid, "")
                char_name = character_name_from_window_title(title)
                if not char_name:
                    try:
                        from meg_navigator import ProcessMemoryReader
                        char_name = ProcessMemoryReader.read_character_name(pid) or ""
                    except Exception:
                        pass
                if not char_name and ctrl.char_name and ctrl.char_name != "---":
                    char_name = ctrl.char_name
                disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
                el["proc_var"].set(disp)
            assigned_count += 1

        self.update_header_stats()
        remaining = len(available_pids) - assigned_count
        if remaining > 0:
            self.log_message(
                f"Gán toàn bộ: Đã gán thành công {assigned_count} tài khoản. Còn lại {remaining} game chưa gán do đạt giới hạn gói bản quyền ({max_allowed} slot).",
                "WARNING"
            )
        else:
            self.log_message(f"Gán toàn bộ: Đã gán thành công toàn bộ {assigned_count} tài khoản vào các Slot.", "SUCCESS")
        for c in self.controllers:
            self.update_slot_run_button_state(c.slot_idx)

    def assign_team5(self):
        """Gán toàn bộ tài khoản vào các Slot (alias cho assign_all)."""
        return self.assign_all()

    def stack_all_jewels(self):
        """Tự động gom ngọc cho toàn bộ tài khoản đang kết nối."""
        cnt = 0
        for ctrl in self.controllers:
            if ctrl.assigned_pid and is_megamu_process_alive(ctrl.assigned_pid):
                cnt += 1
                threading.Thread(target=ctrl.auto_stack_jewels, daemon=True).start()
        if cnt == 0:
            messagebox.showinfo("Thông báo", "Chưa có tài khoản nào kết nối game để gom ngọc!")
        else:
            self.append_log(f"💎 Đang tiến hành gom ngọc tự động cho {cnt} tài khoản...")

    def connect_all(self):
        """Kết nối tới tất cả các slot đã chọn PID hoặc tự động kết nối lại các slot bị mất kết nối."""
        if getattr(self, "is_update_mandatory", False):
            self.open_update_dialog()
            return

        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng Kết nối tất cả đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        # 1. Quét mới 100% tiến trình game MEGAMU trên máy
        self.refresh_games()
        living_pids = set(self.detected_games.keys())

        # 2. Duyệt qua từng slot để kết nối hoặc kết nối lại
        connected_count = 0
        reconnected_count = 0

        for ctrl in self.controllers:
            # Slot bị mất kết nối (PID chết)
            if ctrl.assigned_pid and ctrl.assigned_pid not in living_pids:
                if ctrl.reconnect_game():
                    reconnected_count += 1
            # Slot có PID còn sống
            elif ctrl.assigned_pid and ctrl.assigned_pid in living_pids:
                if not (ctrl.engine and ctrl.engine.is_ready):
                    ctrl.attach_pid(ctrl.assigned_pid)
                connected_count += 1
            # Slot chưa có PID nhưng trước đó đã từng có nhân vật
            elif not ctrl.assigned_pid and ctrl.last_known_char_name:
                if ctrl.reconnect_game():
                    reconnected_count += 1

        self.update_header_stats()
        total = connected_count + reconnected_count
        if reconnected_count > 0:
            self.log_message(f"Kết nối tất cả: Đã kết nối lại thành công {reconnected_count} tài khoản bị mất kết nối (Tổng kết nối: {total}).", "SUCCESS")
        elif total > 0:
            self.log_message(f"Kết nối tất cả: Đã kết nối thành công {total} tài khoản.", "INFO")
        else:
            self.log_message("Kết nối tất cả: Không tìm thấy tài khoản MEGAMU nào để kết nối.", "WARNING")

    def on_master_auto_toggle(self):
        """Bật hoặc Dừng toàn bộ tài khoản tùy theo trạng thái hoạt động hiện tại (1 nút thông minh)."""
        any_running = any(c.worker and c.worker.running for c in self.controllers) or any(c.auto_requested for c in self.controllers)
        if any_running:
            self.stop_all()
        else:
            self.start_all()

    def update_master_run_button(self):
        """Cập nhật icon, màu sắc và tooltip của nút master Chạy/Dừng Tất Cả theo thời gian thực (Zero-churn cache)."""
        if not hasattr(self, "btn_master_run") or self.btn_master_run is None:
            return
        def _apply():
            try:
                any_running = any(c.worker and c.worker.running for c in self.controllers) or any(c.auto_requested for c in self.controllers)
                if getattr(self, "_last_master_running_state", None) == any_running:
                    return
                self._last_master_running_state = any_running

                if any_running:
                    # Đang có ít nhất 1 tài khoản chạy -> Hiển thị icon Dừng
                    self.btn_master_run.configure(
                        image=getattr(self, "_icon_stop_16", None) or UiIconFactory.get("stop", color="#ffffff", size=(16, 16)),
                        fg_color="#dc2626",
                        hover_color="#b91c1c",
                        border_color="#ef4444"
                    )
                    add_tooltip(
                        self.btn_master_run,
                        "⏹ Dừng Tất Cả (Stop All)\n"
                        "Hiện có tài khoản đang chạy Auto. Nhấp vào đây để tạm dừng toàn bộ."
                    )
                else:
                    # Tất cả đều đang dừng -> Hiển thị icon Chạy
                    self.btn_master_run.configure(
                        image=getattr(self, "_icon_play_16", None) or UiIconFactory.get("play", color="#6ee7b7", size=(16, 16)),
                        fg_color="#064e3b",
                        hover_color="#047857",
                        border_color="#059669"
                    )
                    add_tooltip(
                        self.btn_master_run,
                        "▶ Chạy Tất Cả (Start All)\n"
                        "Tất cả tài khoản đang dừng. Nhấp vào đây để khởi động Auto cho toàn bộ."
                    )
            except Exception:
                pass
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def start_all(self):
        """Bật Auto cho tất cả các slot có game."""
        if getattr(self, "is_update_mandatory", False):
            self.open_update_dialog()
            return

        def _run_start():
            count = 0
            for ctrl in self.controllers:
                if ctrl.assigned_pid:
                    ok = ctrl.start_auto()
                    if ok:
                        count += 1
            self.after(0, self.update_header_stats)
            self.after(0, lambda: self.log_message(f"Bật TẤT CẢ: Đã khởi động Auto cho {count} tài khoản.", "SUCCESS"))

        threading.Thread(target=_run_start, daemon=True).start()

    def stop_all(self):
        """Tắt Auto cho tất cả các slot."""
        def _run_stop():
            for ctrl in self.controllers:
                if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                    ctrl.stop_auto(reason="Người dùng bấm nút 'Tắt Tất Cả' trên thanh điều khiển", trigger_by="MANUAL")
            self.after(0, self.update_header_stats)
            self.after(0, lambda: self.log_message("Tắt TẤT CẢ: Đã dừng Auto cho toàn bộ tài khoản.", "INFO"))

        threading.Thread(target=_run_stop, daemon=True).start()

    def batch_start(self):
        """Bật Auto cho nhóm được chọn ở combobox Điều khiển."""
        def _run_batch_start():
            targets = self._get_filtered_controllers()
            count = 0
            for ctrl in targets:
                if ctrl.assigned_pid:
                    ok = ctrl.start_auto()
                    if ok:
                        count += 1
            self.after(0, self.update_header_stats)

        threading.Thread(target=_run_batch_start, daemon=True).start()

    def batch_stop(self):
        """Tắt Auto cho nhóm được chọn ở combobox Điều khiển."""
        def _run_batch_stop():
            choice = self.ctrl_target_var.get()
            targets = self._get_filtered_controllers()
            for ctrl in targets:
                if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                    ctrl.stop_auto(reason=f"Người dùng bấm nút 'Dừng' theo nhóm [{choice}]", trigger_by="MANUAL")
            self.after(0, self.update_header_stats)

        threading.Thread(target=_run_batch_stop, daemon=True).start()

    def _get_filtered_controllers(self) -> List[SlotController]:
        choice = self.ctrl_target_var.get()
        if choice == tr("all"):
            return self.controllers

        # Khớp theo Team dạng "Team X (start-end)"
        import re
        m = re.search(r"\((\d+)-(\d+)\)", choice)
        if m:
            start_i = max(0, int(m.group(1)) - 1)
            end_i = min(len(self.controllers), int(m.group(2)))
            return self.controllers[start_i:end_i]

        try:
            s_idx = int(choice)
            if 1 <= s_idx <= len(self.controllers):
                return [self.controllers[s_idx - 1]]
        except Exception:
            pass
        return self.controllers

    def change_language(self, lang_choice: str):
        lang_code = lang_choice.replace("💬", "").replace("Language:", "").strip().lower()
        target_code = None
        for k in I18N.keys():
            if k.lower() == lang_code:
                target_code = k
                break
        if target_code:
            save_language_preference(target_code)
            self.apply_language()
            self.log_message(tr("lang_changed", lang=target_code.upper()), "INFO")

    def apply_language(self):
        """Áp dụng đa ngôn ngữ thời gian thực ngay lập tức cho toàn bộ giao diện."""
        # 1. Tab buttons
        n = len(self.controllers)
        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({n})")
        if hasattr(self, "tab_profiles_btn"):
            self.tab_profiles_btn.configure(text=f" {tr('configuration')}")
        if hasattr(self, "tab_logs_btn"):
            self.tab_logs_btn.configure(text=f" {tr('logs')}")
        if hasattr(self, "tab_ram_btn"):
            self.tab_ram_btn.configure(text=f" {tr('ram_optimizer')}")
        if hasattr(self, "btn_text_cfg"):
            self.btn_text_cfg.configure(text=tr("text_config"))

        # 2. Action Toolbar buttons (Duy trì icon-only, cập nhật tooltip đa ngôn ngữ)
        if hasattr(self, "btn_connect_all"):
            add_tooltip(self.btn_connect_all, f"🔗 {tr('connect_all')}\nTự động quét và kết nối tất cả các cửa sổ MEGAMU đang mở.")
        if hasattr(self, "btn_team5"):
            add_tooltip(self.btn_team5, f"👥 {tr('assign_team5')}\nTự động quét và gán toàn bộ các cửa sổ game MEGAMU vào các slot trống.")
        if hasattr(self, "btn_refresh"):
            add_tooltip(self.btn_refresh, f"🔄 {tr('refresh_games')}\nQuét lại toàn bộ danh sách tiến trình MEGAMU.exe trên hệ thống.")
        if hasattr(self, "btn_add_slot"):
            add_tooltip(self.btn_add_slot, f"➕ {tr('add')} Slot\nThêm một hàng quản lý tài khoản mới vào bảng.")
        if hasattr(self, "btn_remove_slot"):
            add_tooltip(self.btn_remove_slot, f"➖ {tr('remove')} Slot\nXóa bớt một hàng quản lý tài khoản ở cuối bảng.")
        if hasattr(self, "btn_trim_ram"):
            self.btn_trim_ram.configure(text=f" {tr('ram_trim_now')}")
        if hasattr(self, "btn_ram_optimize_all"):
            self.btn_ram_optimize_all.configure(text=f" {tr('ram_optimize_all_btn')}")
        if hasattr(self, "ram_auto_switch"):
            self.ram_auto_switch.configure(text=tr("ram_auto_trim"))

        # 3. Table Header in Accounts Tab
        if hasattr(self, "col_header_labels"):
            keys = ["col_no", "col_char_pid", "col_route_preset", "col_level", "col_coordinates", "col_status", "col_actions"]
            for lbl, k in zip(self.col_header_labels, keys):
                try:
                    lbl.configure(text=tr(k))
                except Exception:
                    pass

        # 4. Status text of every slot
        for ctrl in self.controllers:
            self.update_slot_ui_status(ctrl.slot_idx, ctrl.status)

        # 5. Header Modals Buttons (Icon-only Minimalist, giữ nguyên text rỗng)
        pass

        # 6. Configuration Modal/Tab
        for attr, tr_key in [
            ("lbl_edit_profile", "edit_profile"),
            ("lbl_pk_delay", "pk_delay"),
            ("btn_reload_cfg", "reload"),
            ("btn_save_cfg", "save_profile"),
            ("lbl_team_note", "team_note"),
        ]:
            if hasattr(self, attr):
                try:
                    w = getattr(self, attr)
                    if w and w.winfo_exists():
                        w.configure(text=tr(tr_key))
                except Exception:
                    pass

        if hasattr(self, "stage_header_labels"):
            s_keys = ["stage_min", "stage_max", "stage_map", "stage_x", "stage_y"]
            for lbl, sk in zip(self.stage_header_labels, s_keys):
                try:
                    if lbl and lbl.winfo_exists():
                        lbl.configure(text=tr(sk))
                except Exception:
                    pass

        # 7. Logs Tab
        if hasattr(self, "lbl_log_show"):
            try:
                if self.lbl_log_show.winfo_exists():
                    self.lbl_log_show.configure(text=tr("show"))
            except Exception:
                pass
        if hasattr(self, "btn_clear_log"):
            try:
                if self.btn_clear_log.winfo_exists():
                    self.btn_clear_log.configure(text=tr("clear_view"))
            except Exception:
                pass
        if hasattr(self, "log_filter_combo"):
            try:
                if self.log_filter_combo.winfo_exists():
                    current_filter = self.log_filter_var.get()
                    opts = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
                    self.log_filter_combo.configure(values=opts)
                    if current_filter not in opts:
                        self.log_filter_var.set(tr("all"))
            except Exception:
                pass

        # 7. Language Menu Variable
        if hasattr(self, "lang_var"):
            self.lang_var.set(f"Language: {CURRENT_LANG.upper()}")

        # 8. Header & Footer Stats
        self.update_header_stats()

    # ==========================================================================
    # CÁC TÁC VỤ ĐỊNH KỲ (SCAN TIẾN TRÌNH & ĐỌC TELEMETRY)
    # ==========================================================================
    def _periodic_game_scan(self):
        if not self.running:
            return
        if getattr(self, "_game_scan_active", False):
            self.after(2500, self._periodic_game_scan)
            return

        self._game_scan_active = True
        def _scan_worker():
            try:
                games = enumerate_megamu_processes()
                def _apply():
                    self.detected_games = games
                    self.update_header_stats()
                    for c in self.controllers:
                        self.update_slot_run_button_state(c.slot_idx)
                if getattr(self, "running", False):
                    try:
                        self.after(0, _apply)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._game_scan_active = False
                if getattr(self, "running", False):
                    try:
                        self.after(2500, self._periodic_game_scan)
                    except Exception:
                        pass

        threading.Thread(target=_scan_worker, daemon=True, name="GameScanWorker").start()

    def _on_window_configure(self, event):
        if event.widget == self:
            self._is_resizing = True
            if self._resize_timer:
                self.after_cancel(self._resize_timer)
            self._resize_timer = self.after(120, self._on_resize_end)

    def _on_resize_end(self):
        self._is_resizing = False
        self._resize_timer = None

    def _start_telemetry_loop(self):
        """Khởi động vòng lặp Telemetry bất đồng bộ thích ứng duy nhất (Adaptive Telemetry Daemon).
        Tránh hoàn toàn việc tạo mới và hủy hàng nghìn luồng Thread mỗi giờ (Zero Thread Churn).
        """
        def _loop():
            while getattr(self, "running", True):
                if getattr(self, "_is_resizing", False):
                    time.sleep(0.3)
                    continue

                any_moving = False
                any_connected = False
                try:
                    for ctrl in list(self.controllers):
                        if ctrl.assigned_pid:
                            any_connected = True
                            ctrl.sync_telemetry()
                            if getattr(ctrl, "is_moving", False):
                                any_moving = True
                except Exception as e:
                    log_thread_exception(
                        source="DashboardApp._telemetry_loop",
                        exc=e,
                        thread_name="AdaptiveTelemetryDaemon",
                        details="Lỗi đồng bộ dữ liệu Telemetry thích ứng"
                    )

                # Adaptive Sleep Interval:
                # - Đang di chuyển: 250ms để tọa độ mượt mà
                # - Đứng train tại chỗ: 750ms (cắt giảm 67% tải CPU)
                # - Chưa gán tài khoản nào: 1500ms
                if any_moving:
                    sleep_time = 0.25
                elif any_connected:
                    sleep_time = 0.75
                else:
                    sleep_time = 1.5

                time.sleep(sleep_time)

        threading.Thread(target=_loop, daemon=True, name="AdaptiveTelemetryDaemon").start()

    def _periodic_telemetry(self):
        """Legacy compatibility placeholder."""
        pass

    def _periodic_license_monitor(self):
        """Giám sát liên tục sự tồn tại của file .dll và trạng thái bản quyền theo thời gian thực (1 giây/lần)."""
        if not getattr(self, "running", True):
            return
        try:
            self.apply_license_lock_state()
            if getattr(self, "active_tab", "") == "ram":
                self._ram_tick = getattr(self, "_ram_tick", 0) + 1
                if self._ram_tick >= 3:
                    self._ram_tick = 0
                    self.refresh_ram_tab_stats()
            if hasattr(self, "header_stats_lbl"):
                lic_str = license_client.get_license_display_text() if license_client else CURRENT_LICENSE
                if not hasattr(self, "_last_lic_display") or self._last_lic_display != lic_str:
                    self._last_lic_display = lic_str
                    self.update_header_stats()
        except Exception:
            pass
        self.after(1000, self._periodic_license_monitor)

    def update_header_stats(self):
        """Cập nhật các số liệu thống kê trên thanh tiêu đề và chân trang (Dirty checking)."""
        num_games = len(self.detected_games)
        num_conn = sum(1 for c in self.controllers if c.assigned_pid and is_megamu_process_alive(c.assigned_pid))
        num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
        num_slots = len(self.controllers)
        lic_str = license_client.get_license_display_text() if license_client else CURRENT_LICENSE

        state_key = (num_games, num_conn, num_auto, num_slots, lic_str)
        if getattr(self, "_last_header_stats_state", None) == state_key:
            return
        self._last_header_stats_state = state_key

        stat_text = tr(
            "header_stats",
            games=num_games,
            conn=num_conn,
            slots=num_slots,
            auto=num_auto,
            license=lic_str,
            expiry="--"
        )
        if hasattr(self, "header_stats_lbl"):
            self.header_stats_lbl.configure(text=stat_text)

        if hasattr(self, "footer_stats_lbl"):
            self.footer_stats_lbl.configure(text=tr("footer_stats", slots=num_slots, conn=num_conn, auto=num_auto))

        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({num_slots})")

        # Đồng bộ trạng thái nút master Chạy / Dừng Tất Cả
        self.update_master_run_button()

        # Cập nhật trạng thái khóa/mở khóa các chức năng theo bản quyền & cập nhật
        self.apply_license_lock_state()

    def apply_license_lock_state(self):
        """Khóa hoặc mở khóa toàn bộ chức năng theo trạng thái bản quyền và phiên bản cập nhật."""
        # TRƯỜNG HỢP 1: BẢN CẬP NHẬT MỚI BẮT BUỘC - Khóa tuyệt đối, không được dùng bản cũ!
        if getattr(self, "is_update_mandatory", False):
            for ctrl in self.controllers:
                if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                    ctrl.stop_auto(reason="Phát hiện bản cập nhật mới bắt buộc từ máy chủ", trigger_by="SYSTEM")

            for btn_name in ("btn_connect_all", "btn_team5", "btn_refresh", "btn_add_slot", "btn_remove_slot", "btn_master_run", "btn_save_cfg", "btn_reload_cfg"):
                if hasattr(self, btn_name):
                    try:
                        getattr(self, btn_name).configure(state="disabled")
                    except Exception:
                        pass

            for elem in self.slot_ui_elements.values():
                for key in ("btn_toggle", "btn_cfg", "proc_combo", "preset_combo"):
                    if key in elem:
                        try:
                            elem[key].configure(state="disabled")
                        except Exception:
                            pass

            ver_text = self.update_info.get("latest_version", "MỚI") if self.update_info else "MỚI"
            banner_text = f"⚠️ BẢN MỚI {ver_text} (BẮT BUỘC CẬP NHẬT)"

            if not hasattr(self, "license_lock_banner") or self.license_lock_banner is None:
                self.license_lock_banner = ctk.CTkFrame(
                    self.toolbar_frame,
                    fg_color="#450a0a",
                    border_width=1,
                    border_color="#ef4444",
                    corner_radius=0,
                    height=32
                )
                self.license_lock_banner.pack(side="right", padx=(0, 6))

                self._license_banner_label = ctk.CTkLabel(
                    self.license_lock_banner,
                    text=banner_text,
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    text_color="#fca5a5"
                )
                self._license_banner_label.pack(side="left", padx=(10, 8), pady=4)

                self._license_banner_btn = ctk.CTkButton(
                    self.license_lock_banner,
                    text="Cập Nhật",
                    width=75,
                    height=22,
                    corner_radius=0,
                    fg_color="#dc2626",
                    hover_color="#b91c1c",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    command=self.open_update_dialog
                )
                self._license_banner_btn.pack(side="right", padx=(0, 6), pady=4)
            else:
                if hasattr(self, "_license_banner_label") and self._license_banner_label:
                    self._license_banner_label.configure(text=banner_text)
                if hasattr(self, "_license_banner_btn") and self._license_banner_btn:
                    self._license_banner_btn.configure(command=self.open_update_dialog, text="Cập Nhật")
            return

        # TRƯỜNG HỢP 2: KIỂM TRA BẢN QUYỀN & FILE DLL
        if license_client and not license_client.is_native_bridge_active():
            license_client.is_native_bridge_active(force_reload=True)

        is_valid = license_client.is_license_valid() if license_client else False
        if is_valid:
            self._license_fail_count = 0
            state_val = "normal"
        else:
            self._license_fail_count = getattr(self, "_license_fail_count", 0) + 1
            # Chống giật / ngắt nhầm (Anti-Glitch Debounce): Chỉ khóa khi thất bại liên tiếp 3 lần
            if self._license_fail_count < 3:
                return
            state_val = "disabled"

        # Chống giật giật (Anti-Jitter/Debounce): Chỉ cấu hình lại widget khi trạng thái thực sự thay đổi!
        if getattr(self, "_last_applied_lock_state", None) == state_val:
            return
        self._last_applied_lock_state = state_val
        self.update_modules_visibility()

        # 0. Nếu không có bản quyền hợp lệ, lập tức dừng mọi worker đang auto train
        if not is_valid:
            lic_msg = "Bản quyền chưa kích hoạt hoặc đã hết hạn"
            if license_client and not license_client.is_native_bridge_active():
                lic_msg = "Thiếu file meg_license_bridge.dll"
            for ctrl in self.controllers:
                if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                    ctrl.stop_auto(reason=f"Hệ thống khóa: {lic_msg}", trigger_by="SYSTEM")

        # 1. Khóa/mở khóa các nút thanh công cụ chính
        for btn_name in ("btn_connect_all", "btn_team5", "btn_refresh", "btn_add_slot", "btn_remove_slot", "btn_master_run"):
            if hasattr(self, btn_name):
                try:
                    getattr(self, btn_name).configure(state=state_val)
                except Exception:
                    pass

        # 2. Khóa/mở khóa các nút lưu cấu hình tab Profiles
        for btn_name in ("btn_save_cfg", "btn_reload_cfg"):
            if hasattr(self, btn_name):
                try:
                    getattr(self, btn_name).configure(state=state_val)
                except Exception:
                    pass

        # 3. Khóa/mở khóa các nút thao tác từng slot
        for s_idx, elem in self.slot_ui_elements.items():
            for key in ("btn_cfg", "proc_combo", "preset_combo"):
                if key in elem:
                    try:
                        elem[key].configure(state=state_val)
                    except Exception:
                        pass
            if state_val == "disabled":
                if "btn_toggle" in elem:
                    try:
                        elem["btn_toggle"].configure(state="disabled")
                    except Exception:
                        pass
            else:
                self.update_slot_run_button_state(s_idx)

        # 4. Hiển thị / ẩn banner cảnh báo trên Toolbar
        if not is_valid:
            banner_text = "🔒 BẢN QUYỀN CHƯA KÍCH HOẠT (ĐÃ KHÓA CHỨC NĂNG)"
            if license_client and not license_client.is_native_bridge_active():
                banner_text = "🔒 THIẾU FILE meg_license_bridge.dll (ĐÃ KHÓA)"

            if not hasattr(self, "license_lock_banner") or self.license_lock_banner is None:
                self.license_lock_banner = ctk.CTkFrame(
                    self.toolbar_frame,
                    fg_color="#3b1219",
                    border_width=1,
                    border_color="#ef4444",
                    corner_radius=0,
                    height=32
                )
                self.license_lock_banner.pack(side="right", padx=(0, 6))

                self._license_banner_label = ctk.CTkLabel(
                    self.license_lock_banner,
                    text=banner_text,
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    text_color="#fca5a5"
                )
                self._license_banner_label.pack(side="left", padx=(10, 8), pady=4)

                self._license_banner_btn = ctk.CTkButton(
                    self.license_lock_banner,
                    text="Kích Hoạt",
                    width=75,
                    height=22,
                    corner_radius=0,
                    fg_color="#dc2626",
                    hover_color="#b91c1c",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    command=self.open_license_dialog
                )
                self._license_banner_btn.pack(side="right", padx=(0, 6), pady=4)
            else:
                if hasattr(self, "_license_banner_label") and self._license_banner_label:
                    self._license_banner_label.configure(text=banner_text)
                if hasattr(self, "_license_banner_btn") and self._license_banner_btn:
                    self._license_banner_btn.configure(command=self.open_license_dialog, text="Kích Hoạt")
        else:
            if hasattr(self, "license_lock_banner") and self.license_lock_banner is not None:
                try:
                    self.license_lock_banner.destroy()
                except Exception:
                    pass
                self.license_lock_banner = None

    def _apply_window_icon(self, target=None):
        """Áp dụng icon megamu_dashboard cho cửa sổ và thanh Taskbar Windows."""
        win = target if target is not None else self
        try:
            # 1. Tự động tái tạo file .ico chuẩn từ LOGO_FILE nếu file .ico bị thiếu
            if not ICON_FILE.exists() and LOGO_FILE.exists():
                try:
                    img = Image.open(str(LOGO_FILE)).convert("RGBA")
                    max_dim = max(img.size)
                    sq = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                    sq.paste(img, ((max_dim - img.size[0]) // 2, (max_dim - img.size[1]) // 2), img)
                    sq.save(
                        str(ICON_FILE),
                        format="ICO",
                        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    )
                except Exception:
                    pass

            # Đánh dấu cờ để CTkToplevel không ghi đè lại icon mặc định
            win._iconbitmap_method_called = True

            # 2. Áp dụng iconbitmap chuẩn Windows Tkinter
            if ICON_FILE.exists():
                try:
                    win.iconbitmap(str(ICON_FILE))
                except Exception:
                    pass
                try:
                    win.wm_iconbitmap(str(ICON_FILE))
                except Exception:
                    pass

            # 3. Áp dụng iconphoto với nhiều kích thước ảnh chất lượng cao từ logo chính thức
            img_src = LOGO_FILE if LOGO_FILE.exists() else (ICON_FILE if ICON_FILE.exists() else None)
            if img_src:
                try:
                    from PIL import ImageTk
                    base_img = Image.open(str(img_src)).convert("RGBA")
                    max_dim = max(base_img.size)
                    sq = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                    sq.paste(base_img, ((max_dim - base_img.size[0]) // 2, (max_dim - base_img.size[1]) // 2), base_img)

                    icons_list = [
                        ImageTk.PhotoImage(sq.resize((s, s), Image.Resampling.LANCZOS))
                        for s in [16, 24, 32, 48, 64, 128, 256]
                    ]
                    win._tk_icons = icons_list
                    win.iconphoto(True, *icons_list)
                except Exception:
                    pass

            # 4. Gửi trực tiếp HICON qua Win32 API WM_SETICON lên HWND, Parent và Root Ancestor HWND
            if ICON_FILE.exists() and sys.platform.startswith("win"):
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x00000010
                    LR_DEFAULTSIZE = 0x00000040
                    WM_SETICON = 0x0080
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    GA_ROOT = 2

                    hicon_big = user32.LoadImageW(None, str(ICON_FILE.resolve()), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
                    hicon_small = user32.LoadImageW(None, str(ICON_FILE.resolve()), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

                    inner_hwnd = win.winfo_id()
                    wrapper_hwnd = user32.GetParent(inner_hwnd) or inner_hwnd
                    root_hwnd = user32.GetAncestor(inner_hwnd, GA_ROOT) or wrapper_hwnd

                    for h in set(filter(None, [inner_hwnd, wrapper_hwnd, root_hwnd])):
                        if hicon_big:
                            user32.SendMessageW(h, WM_SETICON, ICON_BIG, hicon_big)
                        if hicon_small:
                            user32.SendMessageW(h, WM_SETICON, ICON_SMALL, hicon_small)
                except Exception:
                    pass
        except Exception:
            pass

    def on_closing(self):
        self.running = False
        if hasattr(self, "_app_mutex") and self._app_mutex:
            self._app_mutex.release()
        self.moss_running = False
        if hasattr(self, "ram_manager") and self.ram_manager:
            try:
                self.ram_manager.stop_worker()
            except Exception:
                pass
        for ctrl in self.controllers:
            if hasattr(ctrl, "stop_moss"):
                ctrl.stop_moss()
            if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                ctrl.stop_auto(reason="Người dùng đóng cửa sổ chương trình Dashboard", trigger_by="MANUAL")
        for ctrl in self.controllers:
            if ctrl.engine:
                try:
                    ctrl.engine.detach()
                except Exception:
                    pass
        try:
            from meg_navigator import ProcessMemoryReader
            ProcessMemoryReader.close_all()
        except Exception:
            pass
        self.destroy()


# ==============================================================================
def main():
    try:
        install_global_exception_hooks()
    except Exception:
        pass
    try:
        with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] main() starting...\n")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dauto.megamu.dashboard.v1")
    except Exception:
        pass
    try:
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DashboardApp creating...\n")
        except Exception:
            pass
        app = DashboardApp()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] app.mainloop() starting...\n")
        except Exception:
            pass
        app.mainloop()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] app.mainloop() finished naturally.\n")
        except Exception:
            pass
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception in main: {err_msg}\n")
        except Exception:
            pass
        print(err_msg, flush=True)
        try:
            with open("gui_crash.log", "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Lỗi khởi động", f"Chương trình gặp lỗi khi chạy:\n{e}\n\nXem chi tiết tại gui_crash.log")
        except Exception:
            pass

if __name__ == "__main__":
    main()
