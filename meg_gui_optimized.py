#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - v2.0 (Zero-Lag Optimized Architecture)
==================================================================
Giao diện dashboard/card hiện đại, giữ đầy đủ chức năng lõi của meg_gui:
- State Decoupled + In-Place UI Rendering
- Background engine sync + 250ms heartbeat
- Modular views trong ui/
"""

import os
import sys
import json
import time
import ctypes
import threading
from typing import Optional, List, Dict, Tuple, Any

import psutil
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# UTF-8 + high-resolution timer on Windows
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
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("megamu.auto.dashboard.v2")
    except Exception:
        pass

from ui.theme import Colors, Fonts, Radii
from ui.state import AppStateManager
from ui.components.icons import UiIconFactory
from ui.components.cards import CompactSlotCard
from ui.components.shell import MetricChip, make_action_button
from ui.components.dropdown import ModernDropdown
from ui.views.train_view import TrainSlotsView
from ui.views.profiles_view import ProfilesConfigView
from ui.views.autologin_view import AutoLoginView
from ui.views.mirror_view import MirrorView
from ui.views.moss_view import MossView, moss_cat_id, moss_cat_name
from ui.views.logs_view import LogsAndToolsView
from ui.modals.slot_settings import SlotSettingsModal
from ui.engine_sync import BackgroundEngineSync, enumerate_megamu_processes

from meg_gui import (
    BASE_DIR,
    APP_NAME,
    APP_VERSION,
    LOGO_FILE,
    ICON_FILE,
    SlotController,
    ConfigPersistenceManager,
    DEFAULT_SLOTS,
    MAX_SLOTS,
    tr,
    CURRENT_LANG,
    character_name_from_window_title,
    DashboardApp,
    MEGAMUWindowManager,
    ModernOptionMenu,
    server_from_window_title,
)


class _BoolCheckboxProxy:
    """Proxy giống CTkCheckBox.get()/select()/deselect() để SlotController đọc được."""

    def __init__(self, initial: bool = True):
        self._value = 1 if initial else 0

    def get(self):
        return self._value

    def select(self):
        self._value = 1

    def deselect(self):
        self._value = 0

    def set(self, enabled: bool):
        self._value = 1 if enabled else 0

try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None


def get_map_names() -> List[str]:
    cfg = BASE_DIR / "config" / "map_commands.json"
    if not cfg.exists():
        cfg = BASE_DIR / "map_commands.json"
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
            names = [m["name"] for m in d.get("maps", []) if m.get("name")]
            if names:
                return names
        except Exception:
            pass
    return ["Lorencia", "Noria", "Devias", "Dungeon", "Lost Tower", "Atlans", "Tarkan", "Aida", "Kanturu", "Karutan"]


try:
    from meg_account_manager import AccountManager
except ImportError:
    AccountManager = None

try:
    import license_client
except ImportError:
    license_client = None

try:
    from telegram_notifier import send_telegram_raw, TelegramConfig, MirrorTelegramNotifier
except ImportError:
    send_telegram_raw = None
    TelegramConfig = None
    MirrorTelegramNotifier = None

try:
    import updater
except ImportError:
    updater = None


def parse_slot_game_choice(val: str) -> Tuple[Optional[int], str, str]:
    """
    Trích xuất (pid, char_name, server_str) từ chuỗi dropdown tiến trình.
    Hỗ trợ mọi định dạng:
    - 'HSmart [Sv2] (PID 23376)' -> (23376, 'HSmart', 'Sv2')
    - 'HSmart (PID 23376)' -> (23376, 'HSmart', '')
    - 'HSmart [Sv2] (23376)' -> (23376, 'HSmart', 'Sv2')
    - 'MEGAMU (PID 23376)' -> (23376, '', '')
    - 'MEGAMU (23376)' -> (23376, '', '')
    - '23376' -> (23376, '', '')
    - '--' -> (None, '', '')
    """
    if not val or val in ("--", "Chọn...", ""):
        return None, "", ""

    import re
    # 1. Tìm PID là số nguyên bên trong ngoặc hoặc số đứng một mình
    m = re.search(r"(?:PID\s*[:#]?\s*)?(\d+)\s*\)", val)
    if not m:
        m = re.search(r"\b\d+\b", val)
    if not m:
        return None, "", ""
    pid = int(m.group(1) if m.groups() else m.group(0))

    # 2. Tìm tên nhân vật và server
    raw_prefix = val.split("(")[0].strip()
    c_name = ""
    srv_str = ""
    if "[" in raw_prefix and "]" in raw_prefix:
        c_name = raw_prefix.split("[")[0].strip()
        srv_str = raw_prefix.split("[")[1].split("]")[0].strip()
    else:
        c_name = raw_prefix.strip()

    if c_name.upper().startswith("MEGAMU"):
        c_name = ""

    return pid, c_name, srv_str


class DashboardAppOptimized(ctk.CTk):
    """Dashboard V2: modern card UI + zero-lag engine."""

    # Giữ cùng danh mục Moss như meg_gui để method bind dùng được
    MOSS_CAT_OPTIONS = [
        ("[ZEN] 0: Kiếm (Swords - 1,000,000 Zen)", 0),
        ("[ZEN] 1: Chùy & Trượng (Maces/Scepters - 1,000,000 Zen)", 1),
        ("[ZEN] 2: Cung & Nỏ (Bows/Crossbows - 1,000,000 Zen)", 2),
        ("[ZEN] 3: Gậy Phép (Staffs - 1,000,000 Zen)", 3),
        ("[ZEN] 4: Khiên (Shields - 1,000,000 Zen)", 4),
        ("[ZEN] 5: Trang Sức & Khác (Accessories - 2,000,000 Zen)", 5),
        ("[NGỌC] 6: 2 Soul (Trừ 2 Ngọc Tâm Linh)", 6),
        ("[NGỌC] 7: 10 Soul (Trừ 10 Ngọc Tâm Linh)", 7),
        ("[NGỌC] 8: 2 Bless (Trừ 2 Ngọc Ước Nguyện)", 8),
        ("[NGỌC] 9: 10 Bless (Trừ 10 Ngọc Ước Nguyện)", 9),
        ("[NGỌC] 10: 2 Chaos (Trừ 2 Ngọc Hỗn Nguyên)", 10),
        ("[NGỌC] 11: 10 Chaos (Trừ 10 Ngọc Hỗn Nguyên)", 11),
    ]

    def __init__(self):
        super().__init__()

        self.state_mgr = AppStateManager()
        self.running = True
        self._logo_ctk = None

        self.title(f"{APP_NAME} - v2.0 Zero-Lag")
        self.geometry("1200x780")
        self.minsize(1080, 660)
        self.configure(fg_color=Colors.BG_ROOT)
        ctk.set_appearance_mode("dark")

        self._setup_window_icon()
        self.after(100, self._setup_window_icon)
        self.after(300, self._setup_window_icon)
        self.after(600, self._setup_window_icon)

        self.maps_list = get_map_names()
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
            ctrl.moss_clean_equipment_trash = bool(c_data.get("clean_equipment_trash", True))
            ctrl.mirror_enabled = (i in mirror_sel) if (mirror_sel is not None) else True
            ctrl.moss_enabled = (i in moss_sel) if (moss_sel is not None) else True
            self.controllers.append(ctrl)

        self.account_manager = AccountManager() if AccountManager else None
        # Alias tương thích với các hàm Auto Login của meg_gui.DashboardApp
        self.account_mgr = self.account_manager
        self.detected_games = {}
        self.slot_ui_elements = {}
        self.moss_ui_elements = {}
        self.mirror_ui_elements = {}
        self.autologin_ui_rows = []
        self.current_autologin_category = "Tất cả"
        self._last_bg_scan_time = 0.0
        self.active_tab = "train"
        self._moss_ignore_junk_type_val = False
        self.cb_ignore_junk_type = None
        self.cb_clean_equipment_trash = _BoolCheckboxProxy(True)
        self.batch_moss_clean_cb = _BoolCheckboxProxy(True)

        # Telegram (Mirror notify) — cùng nguồn với meg_gui
        self.telegram_config = TelegramConfig() if TelegramConfig else None
        self.mirror_telegram_notifier = (
            MirrorTelegramNotifier(self.telegram_config)
            if (MirrorTelegramNotifier and self.telegram_config) else None
        )
        self.cb_mirror_telegram_notify = _BoolCheckboxProxy(
            bool(getattr(self.telegram_config, "enabled", False)) if self.telegram_config else False
        )

        # Proxy checkbox cho SlotController / scheduler (đọc .get() == 1)
        self.cb_mirror_auto_schedule = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_schedule", True)))
        self.cb_mirror_auto_lifecycle = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_lifecycle", True)))
        self.cb_mirror_auto_gremory = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_gremory", True)))
        self.cb_mirror_auto_prep_before = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_prep_before", True)))
        self.cb_moss_auto_schedule = _BoolCheckboxProxy(bool(moss_sched_cfg.get("auto_schedule", True)))
        self.cb_moss_auto_move_before = _BoolCheckboxProxy(bool(moss_sched_cfg.get("auto_move_before", True)))
        self.mirror_snipe_delay_ms = int(mirror_sched_cfg.get("interval_ms", 35) or 35)
        self.mirror_snipe_dur_s = float(mirror_sched_cfg.get("max_duration_s", 15.0) or 15.0)
        self.mirror_prefire_sec = float(mirror_sched_cfg.get("prefire_sec", 2.0) or 2.0)
        self._last_moss_trigger_key = None
        self._last_moss_stop_key = None
        self._last_moss_move_key = None
        self._last_mirror_event_snipe_key = None
        self._last_mirror_cache_key = None

        # Entry giả lập cho get_mirror_snipe_delay/dur/prefire của meg_gui (nếu bị bind)
        class _FakeEntry:
            def __init__(self, value):
                self._value = str(value)
            def get(self):
                return self._value
            def delete(self, *a, **k):
                self._value = ""
            def insert(self, idx, text):
                self._value = str(text)
        self.mirror_snipe_delay_entry = _FakeEntry(self.mirror_snipe_delay_ms)
        self.mirror_snipe_dur_entry = _FakeEntry(self.mirror_snipe_dur_s)
        self.mirror_prefire_sec_entry = _FakeEntry(self.mirror_prefire_sec)

        # Fake OptionMenu/Entry cho apply_batch_moss_* của meg_gui
        class _FakeCombo:
            def __init__(self, value=""):
                self._value = value
            def get(self):
                return self._value
            def set(self, value):
                self._value = value
            def configure(self, **kwargs):
                if "values" in kwargs:
                    self._values = kwargs["values"]
        self.batch_moss_cat_combo = _FakeCombo(self.MOSS_CAT_OPTIONS[0][0])
        self.batch_moss_delay_entry = _FakeEntry("1000")

        self._build_header()
        self._build_nav_tabs()
        self._build_global_toolbar()
        self._build_body_views()
        self._build_footer()

        # Apply schedule checkboxes from disk + sync proxies
        if hasattr(self, "mirror_view"):
            self.mirror_view.apply_schedule_config(mirror_sched_cfg)
        if hasattr(self, "moss_view"):
            self.moss_view.apply_schedule_config(moss_sched_cfg)
            self.moss_view.apply_moss_flags_from_controllers()
        self._sync_event_checkbox_proxies_from_view()

        self.engine_sync = BackgroundEngineSync(
            controllers_provider=lambda: self.controllers,
            state_mgr=self.state_mgr
        )
        self.engine_sync.start()
        self.after(200, self._ui_heartbeat)

        # Scheduler vào cổng Mirror / Moss (giống meg_gui)
        self.after(1000, self._periodic_moss_scheduler)
        self.after(1000, self._periodic_mirror_scheduler)

        # Telegram telemetry monitor + license monitor (nếu đã bind từ DashboardApp)
        if hasattr(self, "_monitor_mirror_telemetry_for_telegram"):
            self.after(5000, self._monitor_mirror_telemetry_for_telegram)
        if hasattr(self, "_periodic_license_monitor"):
            self.after(60_000, self._periodic_license_monitor)

        # License check in background
        threading.Thread(target=self._verify_license_async, daemon=True).start()
        if hasattr(self, "_check_update_async"):
            threading.Thread(target=self._check_update_async, daemon=True).start()

        self.log_message("🚀 MEGAMU Dashboard V2 (Zero-Lag) đã khởi động.", "SUCCESS")
        self.log_message(f"Điều khiển {len(self.controllers)} slots · logic DashboardApp đã gắn vào shell mới.", "INFO")
        self.append_mirror_log("🪞 Scheduler Mirror đã sẵn sàng (cổng :10 giờ chẵn).")
        self.append_moss_log("🎲 Scheduler Moss đã sẵn sàng (00:15 / 06:15 / 12:15 / 18:15).")

    def _setup_window_icon(self, target_win=None):
        win = target_win or self
        try:
            ico_p = ICON_FILE if (hasattr(ICON_FILE, "exists") and ICON_FILE.exists()) else (BASE_DIR / "megamu_dashboard_icon.ico")
            logo_p = LOGO_FILE if (hasattr(LOGO_FILE, "exists") and LOGO_FILE.exists()) else (BASE_DIR / "megamu_dashboard_logo.png")

            # 1. Tự động đảm bảo file .ico chứa đầy đủ mọi kích thước chuẩn Windows
            if logo_p.exists() and not ico_p.exists():
                try:
                    img = Image.open(str(logo_p)).convert("RGBA")
                    max_dim = max(img.size)
                    sq = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                    sq.paste(img, ((max_dim - img.size[0]) // 2, (max_dim - img.size[1]) // 2), img)
                    sq.save(
                        str(ico_p),
                        format="ICO",
                        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
                    )
                except Exception:
                    pass

            # 2. Áp dụng iconbitmap & wm_iconbitmap
            if ico_p.exists():
                try:
                    win.iconbitmap(str(ico_p))
                except Exception:
                    pass
                try:
                    win.wm_iconbitmap(str(ico_p))
                except Exception:
                    pass

            # 3. Áp dụng iconphoto với các kích thước chuẩn từ logo
            img_src = logo_p if logo_p.exists() else (ico_p if ico_p.exists() else None)
            if img_src:
                try:
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

            # 4. Gửi trực tiếp HICON qua Win32 API WM_SETICON lên HWND và Wrapper HWND
            if ico_p.exists() and sys.platform == "win32":
                try:
                    user32 = ctypes.windll.user32
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x00000010
                    LR_DEFAULTSIZE = 0x00000040
                    WM_SETICON = 0x0080
                    ICON_SMALL = 0
                    ICON_BIG = 1

                    hicon_big = user32.LoadImageW(None, str(ico_p.resolve()), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
                    hicon_small = user32.LoadImageW(None, str(ico_p.resolve()), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

                    inner_hwnd = win.winfo_id()
                    wrapper_hwnd = user32.GetParent(inner_hwnd) or inner_hwnd

                    for h in (inner_hwnd, wrapper_hwnd):
                        if hicon_big:
                            user32.SendMessageW(h, WM_SETICON, ICON_BIG, hicon_big)
                        if hicon_small:
                            user32.SendMessageW(h, WM_SETICON, ICON_SMALL, hicon_small)
                except Exception:
                    pass
        except Exception:
            pass

    # ==========================================================================
    # HEADER / NAV / FOOTER
    # ==========================================================================
    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=64, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        left_h = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_h.pack(side="left", padx=16, fill="y")

        if LOGO_FILE.exists():
            try:
                logo_img = Image.open(str(LOGO_FILE))
                lw, lh = logo_img.size
                aspect = lw / max(1, lh)
                target_h = 36
                target_w = int(target_h * aspect)
                self._logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(target_w, target_h))
                ctk.CTkLabel(left_h, image=self._logo_ctk, text="").pack(side="left", padx=(0, 10), pady=14)
            except Exception:
                pass

        title_box = ctk.CTkFrame(left_h, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        title_line = ctk.CTkFrame(title_box, fg_color="transparent")
        title_line.pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(
            title_line,
            text="MEGAMU AUTO TRAIN",
            font=Fonts.HEADER_TITLE,
            text_color=Colors.TEXT_MAIN
        ).pack(side="left")
        ctk.CTkLabel(
            title_line,
            text=f"  {APP_VERSION} · Zero-Lag",
            font=Fonts.BADGE,
            text_color=Colors.TEAL
        ).pack(side="left", padx=(4, 0))

        self.lbl_header_sub = ctk.CTkLabel(
            title_box,
            text="Ops dashboard · dense · card layout",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM,
            cursor="hand2"
        )
        self.lbl_header_sub.pack(anchor="w")
        self.lbl_header_sub.bind("<Button-1>", lambda e: self.open_license_dialog())

        right_h = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_h.pack(side="right", padx=14, fill="y")

        # Metric chips
        chips = ctk.CTkFrame(right_h, fg_color="transparent")
        chips.pack(side="left", padx=(0, 10), pady=14)
        self.chip_games = MetricChip(chips, "GAME", "0", tone="info", width=78)
        self.chip_games.pack(side="left", padx=3)
        self.chip_conn = MetricChip(chips, "KẾT NỐI", "0", tone="ok", width=88)
        self.chip_conn.pack(side="left", padx=3)
        self.chip_auto = MetricChip(chips, "AUTO", "0", tone="warn", width=78)
        self.chip_auto.pack(side="left", padx=3)
        self.chip_license = MetricChip(chips, "LICENSE", "...", tone="neutral", width=140)
        self.chip_license.pack(side="left", padx=3)
        self.chip_license.bind("<Button-1>", lambda e: self.open_license_dialog())

        make_action_button(
            right_h, "📋 Nhật ký", lambda: self.switch_tab("logs"),
            tone="ghost", width=92, height=30
        ).pack(side="right", padx=3, pady=17)
        make_action_button(
            right_h, "🔄 Cập nhật", lambda: self.check_for_updates_ui(manual=True),
            tone="ghost", width=96, height=30
        ).pack(side="right", padx=3, pady=17)
        make_action_button(
            right_h, "🔑 License", self.open_license_dialog,
            tone="primary", width=96, height=30
        ).pack(side="right", padx=3, pady=17)
        make_action_button(
            right_h, "?", self.show_help,
            tone="ghost", width=34, height=30
        ).pack(side="right", padx=3, pady=17)

    def _build_nav_tabs(self):
        self.nav_frame = ctk.CTkFrame(self, fg_color=Colors.BG_NAV, height=44, corner_radius=0)
        self.nav_frame.pack(fill="x", side="top")
        self.nav_frame.pack_propagate(False)

        inner = ctk.CTkFrame(self.nav_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12)

        self.tabs_map = {}
        self.active_tab_name = "train"

        tab_defs = [
            ("train", "01  Auto Train", "play"),
            ("profiles", "02  Config", "gear"),
            ("autologin", "03  Auto Login", "users"),
            ("mirror", "04  Mirror", "zap"),
            ("moss", "05  Moss", "gem"),
            ("logs", "06  Logs", "terminal"),
        ]

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")

        for tab_id, tab_label, icon_name in tab_defs:
            btn = ctk.CTkButton(
                left,
                image=UiIconFactory.get(icon_name, color=Colors.TEXT_MUTED, size=(13, 13)),
                compound="left",
                text=tab_label,
                font=Fonts.NAV_TAB,
                fg_color="transparent",
                hover_color=Colors.BG_CARD_HOVER,
                text_color=Colors.TEXT_MUTED,
                corner_radius=Radii.SM,
                height=32,
                border_width=0,
                command=lambda t=tab_id: self.switch_tab(t)
            )
            btn.pack(side="left", padx=3, pady=6)
            self.tabs_map[tab_id] = btn

        ctk.CTkLabel(
            inner,
            text="MEGATEAM",
            font=Fonts.BADGE,
            text_color=Colors.TEAL
        ).pack(side="right", padx=6, pady=10)

    def _build_global_toolbar(self):
        """Thanh công cụ sticky đã được tích hợp trực tiếp vào thanh điều khiển của Auto Train để tối giản giao diện."""
        self.global_toolbar = None
        self.lbl_global_hint = None

    def _build_body_views(self):
        self.body_container = ctk.CTkFrame(self, fg_color="transparent")
        self.body_container.pack(fill="both", expand=True)
        self.body_container.grid_rowconfigure(0, weight=1)
        self.body_container.grid_columnconfigure(0, weight=1)

        self.train_view = TrainSlotsView(
            self.body_container,
            controllers=self.controllers,
            maps_list=self.maps_list,
            on_toggle_slot=self.on_slot_auto_toggle,
            on_toggle_all=self.toggle_all_auto,
            on_save_slot_config=self.save_slot_settings,
            on_connect_all=self.connect_all,
            on_assign_all=self.assign_all,
            on_refresh_games=self.refresh_games,
            on_arrange_windows=self.arrange_windows_by_preset,
            on_slot_pid_selected=self.on_slot_pid_selected,
            on_slot_profile_selected=self.on_slot_profile_selected,
            on_stack_jewels=self.stack_all_jewels,
            on_devil_config=self.open_devil_global_config_dialog,
            on_close_games=self.close_all_games,
            on_open_stat_dialog=self.open_slot_profile_editor,
            on_add_slot=self.add_new_slot,
            on_remove_slot=self.remove_last_slot,
            on_telegram_config=getattr(self, "open_mirror_telegram_settings_dialog", None),
            on_import_accounts=getattr(self, "import_accounts_from_registry_ui", None),
        )
        self.train_view.grid(row=0, column=0, sticky="nsew")

        self.profiles_view = ProfilesConfigView(
            self.body_container,
            maps_list=self.maps_list,
            config_persistence_mgr=ConfigPersistenceManager,
            on_profile_saved=self._on_profile_saved,
            on_log=self.log_message
        )
        self.profiles_view.grid(row=0, column=0, sticky="nsew")

        self.autologin_view = None
        if self.account_mgr:
            try:
                self.autologin_view = AutoLoginView(
                    self.body_container,
                    account_mgr=self.account_mgr,
                    controllers=self.controllers,
                    on_launch_all=self.batch_launch_all_accounts,
                    on_close_all=self.on_click_close_games_ui,
                    on_add_account=self.open_add_account_dialog,
                    on_delete_selected=self.delete_selected_accounts_ui,
                    on_change_exe=self.choose_exe_path_dialog,
                    on_arrange_layout=self._on_arrange_preset_selected,
                    on_launch_single=self.launch_single_account_ui,
                    on_send_login=self.send_login_to_slot_ui,
                    on_close_single=self.close_single_account_game,
                    on_edit_account=self.open_edit_account_dialog,
                    on_delete_account=self.delete_account_ui,
                    on_toggle_account=self._on_acc_toggle,
                    on_change_category=self._on_acc_cat_change,
                    on_change_character=self._on_acc_char_change,
                    on_change_server=self._on_acc_srv_change,
                    on_change_slot=self._on_acc_slot_change,
                    on_prompt_add_category=self.prompt_add_new_category,
                    on_prompt_change_category=self.prompt_change_account_category,
                    on_filter_category=self.select_autologin_category,
                )
                self.autologin_view.grid(row=0, column=0, sticky="nsew")

                # Thuộc tính tương thích ngược với logic Auto Login của meg_gui
                self.btn_autologin_all = self.autologin_view.btn_launch_all
                self.btn_autologin_close = self.autologin_view.btn_close_all
                self.lbl_autologin_exe = self.autologin_view.lbl_exe
                self.autologin_status_lbl = self.autologin_view.status_lbl
                self.autologin_delay_var = self.autologin_view.delay_var
                self.autologin_log_txt = self.autologin_view.log_txt
                self._autologin_table_initialized = True
            except Exception as e_al:
                self.log_message(f"Lỗi khởi tạo AutoLoginView: {e_al}", "WARNING")
                import traceback
                self.log_message(traceback.format_exc(), "ERROR")

        self.mirror_view = MirrorView(
            self.body_container,
            controllers=self.controllers,
            on_trigger_mirror=self.trigger_mirror_snipe,
            on_enter_mirror=self.enter_all_mirror,
            on_mirror_lifecycle=self.trigger_all_mirror_lifecycle,
            on_claim_gremory=self.claim_all_gremory_case_items,
            on_move_lugard=self.move_all_to_event_map,
            on_check_tickets=self.check_all_mirror_tickets,
            on_prepare_mirror=getattr(self, "prepare_all_mirror_event", None),
            on_click_mirror_npc=getattr(self, "click_all_mirror_npc", None),
            on_stop_mirror=getattr(self, "stop_all_mirror_auto", None),
            on_toggle_participant=lambda s, en: self.toggle_event_participant("mirror", s, en),
            on_save_schedule=lambda opts: self.save_event_schedule("mirror", opts),
            on_toggle_telegram=self._on_events_telegram_toggle,
            on_telegram_settings=getattr(self, "open_mirror_telegram_settings_dialog", None),
            on_snipe_slot=getattr(self, "manual_snipe_mirror_slot", None),
        )
        self.mirror_view.grid(row=0, column=0, sticky="nsew")

        self.moss_view = MossView(
            self.body_container,
            controllers=self.controllers,
            on_trigger_moss=self.trigger_moss_merchant,
            on_stop_moss=self.stop_all_moss,
            on_toggle_participant=lambda s, en: self.toggle_event_participant("moss", s, en),
            on_save_schedule=lambda opts: self.save_event_schedule("moss", opts),
            on_apply_moss_batch=self.apply_moss_batch_settings,
            on_clean_moss=self.clean_all_moss_inventories,
            on_sell_moss=self.sell_all_moss_inventories,
            on_analyze_moss=self.analyze_all_moss_inventories,
            on_open_junk_dialog=self.open_junk_disposal_dialog,
            on_moss_slot_category=self.on_moss_slot_category_changed,
            on_moss_slot_delay=self.on_moss_slot_delay_changed,
            on_toggle_moss_slot=self.toggle_moss_slot_auto,
            on_moss_row_action=self.on_moss_row_action,
            on_moss_batch_tool=self.on_moss_batch_tool,
        )
        self.moss_view.grid(row=0, column=0, sticky="nsew")

        # Alias tương thích ngược cho code/shim còn gọi events_view
        self.events_view = self.moss_view

        # Sync Telegram checkbox from loaded config
        try:
            tg_on = bool(getattr(self.telegram_config, "enabled", False)) if self.telegram_config else False
            self.mirror_view.var_mirror_telegram.set(tg_on)
            self.cb_mirror_telegram_notify.set(tg_on)
        except Exception:
            pass

        self.logs_view = LogsAndToolsView(
            self.body_container,
            on_arrange_windows=None,
            on_clear_logs=lambda: self.log_message("Nhật ký đã được làm sạch.", "INFO")
        )
        self.logs_view.grid(row=0, column=0, sticky="nsew")

        self.train_view.lift()
        self._update_tab_button_visuals("train")

    def _build_footer(self):
        self.footer_frame = ctk.CTkFrame(self, fg_color=Colors.BG_FOOTER, height=28, corner_radius=0)
        self.footer_frame.pack(fill="x", side="bottom")
        self.footer_frame.pack_propagate(False)

        self.footer_stats_lbl = ctk.CTkLabel(
            self.footer_frame,
            text=f"Total: {len(self.controllers)} slots · Connected: 0 · Running: 0",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        )
        self.footer_stats_lbl.pack(side="left", padx=16, pady=5)

        ctk.CTkLabel(
            self.footer_frame,
            text="Phát triển bởi MEGATEAM · Hotline 036.203.1354",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM
        ).pack(side="right", padx=16, pady=5)

    def switch_tab(self, tab_id: str):
        if self.active_tab_name == tab_id:
            return
        new_view = self._get_view_by_id(tab_id)
        if new_view:
            new_view.lift()
        self.active_tab_name = tab_id
        # Tương thích logic Auto Login của meg_gui (dùng self.active_tab)
        self.active_tab = tab_id
        self._update_tab_button_visuals(tab_id)
        if tab_id == "autologin" and hasattr(self, "sync_autologin_table_values"):
            try:
                self.sync_autologin_table_values()
            except Exception:
                pass
        elif tab_id == "mirror" and hasattr(self, "mirror_view") and self.mirror_view:
            try:
                self.mirror_view.refresh_rows()
                self.trigger_mirror_ticket_scan()
            except Exception:
                pass
        elif tab_id == "moss" and hasattr(self, "moss_view") and self.moss_view:
            try:
                self.moss_view.refresh_moss_rows()
            except Exception:
                pass
        elif tab_id == "train" and hasattr(self, "train_view") and self.train_view:
            try:
                all_data = self.state_mgr.get_all_slots_data()
                if all_data:
                    self.train_view.update_slots_data(all_data)
            except Exception:
                pass

    def _get_view_by_id(self, tab_id: str):
        return {
            "train": getattr(self, "train_view", None),
            "profiles": getattr(self, "profiles_view", None),
            "autologin": getattr(self, "autologin_view", None),
            "mirror": getattr(self, "mirror_view", None),
            "moss": getattr(self, "moss_view", None),
            "events": getattr(self, "moss_view", None),  # legacy alias
            "logs": getattr(self, "logs_view", None),
        }.get(tab_id)

    def _on_profile_saved(self, profile_idx: int):
        if hasattr(self, "train_view"):
            self.train_view.update_profile_options_all(CompactSlotCard.get_default_profile_options())

    def open_slot_profile_editor(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        p_idx = getattr(ctrl, "profile_index", 1)
        if hasattr(self, "profiles_view"):
            self.profiles_view.load_profile_into_editor(p_idx)
        self.switch_tab("profiles")

    def _update_tab_button_visuals(self, active_id: str):
        for tid, btn in self.tabs_map.items():
            if tid == active_id:
                btn.configure(
                    fg_color="#122033",
                    text_color=Colors.CYAN,
                    border_width=1,
                    border_color=Colors.CYAN
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=Colors.TEXT_MUTED,
                    border_width=0
                )

    # ==========================================================================
    # HEARTBEAT
    # ==========================================================================
    def _ui_heartbeat(self):
        if not self.running:
            return
        try:
            now = time.time()
            dirty_slots = self.state_mgr.get_dirty_slots()
            if dirty_slots and hasattr(self, "train_view"):
                self.train_view.update_slots_data(dirty_slots)

            new_logs = self.state_mgr.pop_pending_logs()
            if new_logs and hasattr(self, "logs_view"):
                self.logs_view.append_batched_logs(new_logs)

            # Events countdown: chỉ khi dirty (engine_sync đánh dấu ~1s/lần)
            if self.state_mgr.is_events_dirty():
                ev = self.state_mgr.events
                if hasattr(self, "mirror_view") and self.mirror_view:
                    # Chỉ cập nhật countdown; bảng slot throttle riêng
                    mirror = ev.get("mirror", {})
                    self.mirror_view.update_countdown(
                        mirror.get("countdown_sec", 0),
                        mirror.get("is_gate_open", False),
                        mirror.get("next_time_str"),
                    )
                if hasattr(self, "moss_view") and self.moss_view:
                    moss = ev.get("moss", {})
                    self.moss_view.update_countdown(
                        moss.get("countdown_sec", 0),
                        moss.get("is_open", False),
                        moss.get("next_time_str"),
                    )

            # Bảng Mirror/Moss: tối đa ~1 lần/giây khi đang mở tab (tránh lag configure hàng loạt)
            if self.active_tab_name == "moss" and hasattr(self, "moss_view") and self.moss_view:
                if now - getattr(self, "_last_moss_table_refresh", 0) >= 1.0:
                    self._last_moss_table_refresh = now
                    self.moss_view.refresh_moss_rows()
            elif self.active_tab_name == "mirror" and hasattr(self, "mirror_view") and self.mirror_view:
                if now - getattr(self, "_last_mirror_table_refresh", 0) >= 1.0:
                    self._last_mirror_table_refresh = now
                    self.mirror_view.refresh_rows()

            if getattr(self.state_mgr, "global_dirty", False):
                self.state_mgr.global_dirty = False
                games = self.state_mgr.get_detected_games()
                self.detected_games = games
                proc_options = ["--"] + list(games.values())
                # Chỉ đụng dropdown Train khi danh sách PID thực sự đổi
                if proc_options != getattr(self, "_last_proc_options_cache", None):
                    self._last_proc_options_cache = proc_options
                    if hasattr(self, "train_view"):
                        self.train_view.update_process_options_all(proc_options)
                if now - getattr(self, "_last_header_stats_ts", 0) >= 0.8:
                    self._last_header_stats_ts = now
                    self._update_header_stats_internal()

            # Auto Login: tối đa ~1.2s/lần (không sync 4 lần/giây)
            if self.active_tab_name == "autologin" and hasattr(self, "sync_autologin_table_values"):
                if now - getattr(self, "_last_autologin_sync_ts", 0) >= 1.2:
                    self._last_autologin_sync_ts = now
                    self.sync_autologin_table_values()
        except Exception:
            pass

        if self.running:
            self.after(300, self._ui_heartbeat)

    def _update_header_stats_internal(self):
        num_games = len(self.detected_games)
        num_conn = sum(1 for c in self.controllers if c.assigned_pid and c.assigned_pid in self.detected_games)
        num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
        lic_str = license_client.get_license_display_text() if license_client else "Free"
        short_lic = (lic_str[:18] + "…") if len(lic_str) > 19 else lic_str

        self.chip_games.set_value(str(num_games), "info" if num_games else "neutral")
        self.chip_conn.set_value(str(num_conn), "ok" if num_conn else "neutral")
        self.chip_auto.set_value(str(num_auto), "warn" if num_auto else "neutral")
        self.chip_license.set_value(short_lic, "ok" if "valid" in lic_str.lower() or "ok" in lic_str.lower() or "còn" in lic_str.lower() else "neutral")
        self.footer_stats_lbl.configure(
            text=f"Total: {len(self.controllers)} slots · Connected: {num_conn} · Running: {num_auto} · Games: {num_games}"
        )

    # ==========================================================================
    # USER ACTIONS
    # ==========================================================================
    def on_slot_auto_toggle(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        if ctrl.worker and ctrl.worker.running:
            ctrl.stop_auto(reason="Người dùng nhấn nút DỪNG trên giao diện")
        else:
            ctrl.start_auto()

    def toggle_all_auto(self, start_all: bool):
        if start_all:
            self.log_message("▶ Đang bật Auto cho tất cả các slot có game...", "INFO")
            for ctrl in self.controllers:
                if ctrl.assigned_pid and not (ctrl.worker and ctrl.worker.running):
                    ctrl.start_auto()
        else:
            self.log_message("⏹ Đang dừng Auto cho tất cả các slot...", "INFO")
            for ctrl in self.controllers:
                if ctrl.worker and ctrl.worker.running:
                    ctrl.stop_auto(reason="Dừng hàng loạt")

    def connect_all(self):
        self.log_message("🔗 Đang kiểm tra và kết nối lại các Slot...", "INFO")
        threading.Thread(target=self._worker_connect_all, daemon=True, name="ConnectAllWorker").start()

    def _worker_connect_all(self):
        try:
            self.refresh_games()
            living_pids = set(getattr(self, "detected_games", {}).keys())
            connected_count = 0
            reconnected_count = 0

            for ctrl in self.controllers:
                try:
                    # Slot bị mất kết nối (PID đã chết)
                    if ctrl.assigned_pid and ctrl.assigned_pid not in living_pids:
                        if hasattr(ctrl, "reconnect_game") and ctrl.reconnect_game():
                            reconnected_count += 1
                        elif hasattr(ctrl, "reconnect_if_needed") and ctrl.reconnect_if_needed():
                            reconnected_count += 1
                    # Slot có PID đang sống
                    elif ctrl.assigned_pid and ctrl.assigned_pid in living_pids:
                        if not (ctrl.engine and ctrl.engine.is_ready):
                            ctrl.attach_pid(ctrl.assigned_pid)
                        connected_count += 1
                    # Slot chưa có PID nhưng đã từng gắn nhân vật
                    elif not ctrl.assigned_pid and getattr(ctrl, "last_known_char_name", None):
                        if hasattr(ctrl, "reconnect_game") and ctrl.reconnect_game():
                            reconnected_count += 1
                        elif hasattr(ctrl, "reconnect_if_needed") and ctrl.reconnect_if_needed():
                            reconnected_count += 1
                except Exception as e_slot:
                    self.log_message(f"[Slot {ctrl.slot_idx:02d}] Lỗi kết nối: {e_slot}", "WARNING")

            total = connected_count + reconnected_count
            if reconnected_count > 0:
                self.log_message(f"🔗 Kết nối tất cả: Đã kết nối lại thành công {reconnected_count} slot bị mất kết nối (Tổng: {total}).", "SUCCESS")
            elif total > 0:
                self.log_message(f"🔗 Kết nối tất cả: Đã kết nối thành công {total} slot.", "SUCCESS")
            else:
                self.log_message("🔗 Kết nối tất cả: Không tìm thấy tiến trình MEGAMU nào để kết nối.", "WARNING")

            self.state_mgr.global_dirty = True
            if hasattr(self, "update_header_stats"):
                self.update_header_stats()
            if hasattr(self, "mirror_view") and self.mirror_view:
                self.mirror_view.refresh_rows()
                self.trigger_mirror_ticket_scan()
            if hasattr(self, "moss_view") and self.moss_view:
                self.moss_view.refresh_moss_rows()
        except Exception as e:
            self.log_message(f"Lỗi connect_all: {e}", "ERROR")

    def assign_all(self):
        self.log_message("👥 Đang tự động gán tiến trình MEGAMU vào các ô Slot trống...", "INFO")
        threading.Thread(target=self._worker_assign_all, daemon=True).start()

    def _worker_assign_all(self):
        games = self.state_mgr.get_detected_games()
        assigned_pids = {c.assigned_pid for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid)}
        available = [p for p in games if p not in assigned_pids]
        target_slots = [c for c in self.controllers if not c.assigned_pid or not psutil.pid_exists(c.assigned_pid)]

        count = 0
        for pid in available:
            if not target_slots:
                break
            ctrl = target_slots.pop(0)
            ctrl.attach_pid(pid)
            title = games.get(pid, "")
            _, t_name, srv_str = parse_slot_game_choice(title)
            if not t_name and character_name_from_window_title:
                t_name = character_name_from_window_title(title)
            if t_name and t_name != "---":
                ctrl.char_name = t_name
                ctrl.last_known_char_name = t_name
            if srv_str:
                ctrl.server_name = srv_str if srv_str.startswith("Sv") else f"Sv{srv_str}"
            self.state_mgr.update_slot_telemetry(
                ctrl.slot_idx,
                assigned_pid=pid,
                char_name=ctrl.char_name,
                server=getattr(ctrl, "server_name", "---"),
                status="Đã kết nối"
            )
            count += 1

        self.log_message(f"Đã gán thành công {count} tài khoản vào các Slot.", "SUCCESS")
        self.state_mgr.global_dirty = True
        if hasattr(self, "mirror_view") and self.mirror_view:
            self.mirror_view.refresh_rows()
            self.trigger_mirror_ticket_scan()
        if hasattr(self, "moss_view") and self.moss_view:
            self.moss_view.refresh_moss_rows()
        if hasattr(self, "train_view") and self.train_view:
            all_data = self.state_mgr.get_all_slots_data()
            if all_data:
                self.train_view.update_slots_data(all_data)

    def refresh_games(self):
        self.log_message("🔄 Đang quét lại danh sách tiến trình MEGAMU...", "INFO")
        self.engine_sync.trigger_scan_now()

    def on_slot_pid_selected(self, slot_idx: int, val: str):
        ctrl = self.controllers[slot_idx - 1]
        pid, c_name, srv_str = parse_slot_game_choice(val)

        if pid is None:
            ctrl.assigned_pid = None
            ctrl.engine = None
            ctrl.char_name = "---"
            self.state_mgr.update_slot_telemetry(
                slot_idx,
                assigned_pid=None,
                status="Chưa kết nối",
                char_name="---",
                level="---",
                coords="--,--"
            )
            self.state_mgr.global_dirty = True
            if hasattr(self, "mirror_view") and self.mirror_view:
                self.mirror_view.refresh_rows()
            if hasattr(self, "moss_view") and self.moss_view:
                self.moss_view.refresh_moss_rows()
            if hasattr(self, "train_view") and self.train_view:
                self.train_view.update_slots_data([self.state_mgr.get_slot(slot_idx)])
            self.log_message(f"[Slot {slot_idx:02d}] Đã hủy gán PID.", "INFO")
            return

        try:
            # Nhả PID nếu đang được gán ở slot khác để tránh xung đột
            for other_c in self.controllers:
                if other_c.slot_idx != slot_idx and other_c.assigned_pid == pid:
                    other_c.assigned_pid = None
                    other_c.engine = None
                    other_c.char_name = "---"
                    self.state_mgr.update_slot_telemetry(
                        other_c.slot_idx,
                        assigned_pid=None,
                        status="Chưa kết nối",
                        char_name="---",
                        level="---",
                        coords="--,--"
                    )
                    self.log_message(f"[Slot {other_c.slot_idx:02d}] Đã nhả PID {pid} để chuyển sang Slot #{slot_idx:02d}.", "INFO")
                    if hasattr(self, "train_view") and self.train_view:
                        self.train_view.update_slots_data([self.state_mgr.get_slot(other_c.slot_idx)])

            ok = ctrl.attach_pid(pid)
            if c_name and c_name != "---":
                ctrl.char_name = c_name
                ctrl.last_known_char_name = c_name
            if srv_str:
                ctrl.server_name = srv_str if srv_str.startswith("Sv") else f"Sv{srv_str}"

            self.state_mgr.update_slot_telemetry(
                slot_idx=slot_idx,
                assigned_pid=pid,
                char_name=ctrl.char_name,
                server=getattr(ctrl, "server_name", "---"),
                status="Đã kết nối" if ok else "Đang kết nối..."
            )
            self.state_mgr.global_dirty = True
            if hasattr(self, "update_header_stats"):
                self.update_header_stats()

            self.log_message(f"[Slot {slot_idx:02d}] Đã gán PID {pid} ({ctrl.char_name}).", "SUCCESS")

            if hasattr(self, "mirror_view") and self.mirror_view:
                self.mirror_view.refresh_rows()
                self.trigger_mirror_ticket_scan(slot_idx)
            if hasattr(self, "moss_view") and self.moss_view:
                self.moss_view.refresh_moss_rows()
            if hasattr(self, "train_view") and self.train_view:
                self.train_view.update_slots_data([self.state_mgr.get_slot(slot_idx)])
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Lỗi khi gán PID ({val}): {e}", "ERROR")

    def trigger_mirror_ticket_scan(self, slot_idx: Optional[int] = None):
        """Quét số lượng vé Mirror trên nền và hiển thị trực tiếp lên bảng Mirror."""
        def _scan_worker():
            targets = [self.controllers[slot_idx - 1]] if (slot_idx and 1 <= slot_idx <= len(self.controllers)) else self.controllers
            for ctrl in targets:
                try:
                    if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
                        t_info = ctrl.check_mirror_ticket()
                        ctrl.cached_mirror_ticket_info = t_info
                        if hasattr(self, "mirror_view") and self.mirror_view:
                            self.after(0, lambda s=ctrl.slot_idx, inf=t_info: self.mirror_view.update_slot_ticket_info(s, inf))
                        time.sleep(0.04)
                except Exception:
                    pass
        threading.Thread(target=_scan_worker, daemon=True, name="MirrorTicketScan").start()

    def on_slot_profile_selected(self, slot_idx: int, val: str):
        ctrl = self.controllers[slot_idx - 1]
        try:
            digits = "".join(ch for ch in val if ch.isdigit())
            p_idx = int(digits) if digits else int(val.replace("Config", "").strip())
            ctrl.profile_index = p_idx
            self.state_mgr.update_slot_telemetry(slot_idx, profile=val)
            self.log_message(f"[Slot {slot_idx:02d}] Đã đổi cấu hình sang {val}.", "INFO")
        except Exception:
            pass

    def save_slot_settings(self, slot_idx: int, new_cfg: Dict[str, Any]):
        ctrl = self.controllers[slot_idx - 1]
        try:
            if "map" in new_cfg:
                ctrl.spot_map = new_cfg["map"]
            if "x" in new_cfg:
                ctrl.spot_x = int(new_cfg["x"])
            if "y" in new_cfg:
                ctrl.spot_y = int(new_cfg["y"])
            if "auto_repair" in new_cfg:
                ctrl.auto_repair = bool(new_cfg["auto_repair"])
            if "auto_clean_trash" in new_cfg:
                ctrl.auto_clean_trash = bool(new_cfg["auto_clean_trash"])
            if "mirror_enabled" in new_cfg:
                ctrl.mirror_enabled = bool(new_cfg["mirror_enabled"])
            if "moss_enabled" in new_cfg:
                ctrl.moss_enabled = bool(new_cfg["moss_enabled"])
        except Exception:
            pass
        self.log_message(f"[Slot {slot_idx:02d}] Cấu hình đã được lưu thành công.", "SUCCESS")

    def stack_all_jewels(self):
        if getattr(self, "_stack_all_in_progress", False):
            self.log_message("⏳ Đang trong tiến trình gom ngọc, vui lòng đợi đợt gom hiện tại hoàn tất...", "WARNING")
            return
        self._stack_all_in_progress = True

        def _worker():
            try:
                active_ctrls = [c for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid)]
                if not active_ctrls:
                    self.log_message("⚠️ Không có slot nào đang kết nối game để gom ngọc.", "WARNING")
                    return
                self.log_message(f"💎 Bắt đầu gom ngọc cho {len(active_ctrls)} slot kết nối...", "INFO")
                for ctrl in active_ctrls:
                    try:
                        ctrl.auto_stack_jewels()
                    except Exception as e:
                        self.log_message(f"[Slot {ctrl.slot_idx:02d}] Lỗi gom ngọc: {e}", "WARNING")
                self.log_message("✅ Hoàn tất gom ngọc cho toàn bộ slot kết nối.", "SUCCESS")
            finally:
                self._stack_all_in_progress = False

        threading.Thread(target=_worker, daemon=True, name="StackAllJewelsWorker").start()

    def close_all_games(self):
        if not messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn đóng toàn bộ các cửa sổ game MEGAMU?"):
            return
        closed = 0
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'] and p.info['name'].lower() == 'megamu.exe':
                    p.kill()
                    closed += 1
            except Exception:
                pass
        self.log_message(f"Đã đóng {closed} tiến trình MEGAMU.exe.", "INFO")
        self.engine_sync.trigger_scan_now()

    def arrange_windows_default(self):
        self.arrange_windows_by_preset("auto")

    def arrange_windows_by_preset(self, preset: Optional[str] = "3x2"):
        """Sắp xếp tất cả cửa sổ game MEGAMU theo lưới chuẩn bằng MEGAMUWindowManager (pure ctypes, không phụ thuộc win32gui)."""
        target_layout = preset or "auto"
        if hasattr(self, "train_view") and hasattr(self.train_view, "layout_combo"):
            combo_val = self.train_view.layout_combo.get()
            if combo_val and combo_val not in ("Tự động", "auto"):
                target_layout = combo_val

        if hasattr(self, "execute_window_arrangement"):
            res = self.execute_window_arrangement(layout=target_layout)
            return res

        cfg = ConfigPersistenceManager.load_window_arrangement_config()
        res = MEGAMUWindowManager.arrange_windows(
            layout=target_layout,
            custom_cols=cfg.get("custom_cols", 2),
            custom_rows=cfg.get("custom_rows", 2),
            monitor_idx=cfg.get("monitor_idx", 0),
            margin=cfg.get("margin", 0),
            controllers=self.controllers
        )
        msg = res.get("msg", "")
        if res.get("ok"):
            self.log_message(f"📐 {msg}", "SUCCESS")
        else:
            self.log_message(f"⚠️ {msg}", "WARNING")
        return res

    def trigger_mirror_snipe(self):
        """Cướp cổng Mirror — dùng luồng đầy đủ của meg_gui (turbo + khóa event key)."""
        self._sync_event_checkbox_proxies_from_view()
        if hasattr(self, "start_all_mirror_turbo_sniping"):
            self.start_all_mirror_turbo_sniping(from_scheduler=False)
        else:
            self.append_mirror_log("⚡ Kích hoạt Cướp Cổng Mirror...")
            for ctrl in self.controllers:
                if ctrl.assigned_pid and getattr(ctrl, "mirror_enabled", True):
                    threading.Thread(target=ctrl.start_mirror_turbo_sniping, daemon=True).start()

    def trigger_all_mirror_lifecycle(self):
        """Kích hoạt chu trình chiến đấu bên trong Double Goer cho các tài khoản ĐÃ TÍCH CHỌN."""
        cnt = 0
        for ctrl in self.controllers:
            if not getattr(ctrl, "mirror_enabled", True):
                continue
            if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
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
                if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
                    ctrl.enter_mirror()
                    cnt += 1
                    time.sleep(0.08)
            self.after(0, lambda: self.append_mirror_log(f"🚪 Đã gửi lệnh vào cửa Double Goer cho {cnt} tài khoản đã chọn!"))
        threading.Thread(target=_enterer, daemon=True).start()

    def claim_all_gremory_case_items(self):
        """Tự động lôi quà phím 'K' (Gremory Case) cho các tài khoản ĐÃ TÍCH CHỌN."""
        def _worker():
            self.append_mirror_log("🎁 [Gremory Case] Bắt đầu tự động lôi quà phím 'K' cho các tài khoản đã chọn...")
            total_claimed = 0
            for s_i, c in enumerate(self.controllers, 1):
                if not getattr(c, "mirror_enabled", True):
                    continue
                if c.assigned_pid and psutil.pid_exists(c.assigned_pid):
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

    def move_all_to_event_map(self):
        """Di chuyển ĐỒNG THỜI (Parallel Multi-threading) các tài khoản ĐÃ TÍCH CHỌN tới Event Map (Lugard)."""
        selected_ctrls = [
            ctrl for ctrl in self.controllers
            if getattr(ctrl, "mirror_enabled", True) and ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid)
        ]
        if not selected_ctrls:
            self.append_mirror_log("⚠️ Không có tài khoản Mirror đã chọn nào đang kết nối!")
            return

        cnt = len(selected_ctrls)
        self.append_mirror_log(f"🚶 [Đồng thời] Đang chuyển Event Map song song cho {cnt} tài khoản...")
        for ctrl in selected_ctrls:
            threading.Thread(
                target=ctrl.move_to_event_map,
                name=f"MirrorMoveSlot_{ctrl.slot_idx}",
                daemon=True
            ).start()

    def check_all_mirror_tickets(self):
        """Kiểm tra vé Mirror cho toàn bộ tài khoản ĐÃ TÍCH CHỌN và cập nhật UI."""
        def _checker():
            self.after(0, lambda: self.append_mirror_log("🔍 Đang kiểm tra vé Mirror trên các tài khoản đã chọn (ô 12 - 203)..."))
            total_connected = 0
            has_ticket_count = 0
            for ctrl in self.controllers:
                if not getattr(ctrl, "mirror_enabled", True):
                    continue
                if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
                    total_connected += 1
                    t_info = ctrl.check_mirror_ticket()
                    # Cập nhật nhãn vé trên hàng slot
                    if hasattr(self, "mirror_view") and hasattr(self.mirror_view, "update_slot_ticket_info"):
                        self.after(0, lambda s=ctrl.slot_idx, inf=t_info: self.mirror_view.update_slot_ticket_info(s, inf))

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
        threading.Thread(target=_checker, daemon=True).start()

    def trigger_moss_merchant(self):
        """Bắt đầu Auto Moss cho các slot đã chọn."""
        self._sync_event_checkbox_proxies_from_view()
        if hasattr(self, "start_all_moss_auto"):
            self.start_all_moss_auto()
        else:
            self.append_moss_log("🎲 Bắt đầu Auto Quay Moss Merchant...")
            for ctrl in self.controllers:
                if ctrl.assigned_pid and getattr(ctrl, "moss_enabled", True):
                    ctrl.start_moss()

    def stop_all_moss(self):
        if hasattr(self, "stop_all_moss_auto"):
            self.stop_all_moss_auto()
            return
        for ctrl in self.controllers:
            if hasattr(ctrl, "stop_moss"):
                try:
                    ctrl.stop_moss()
                except Exception:
                    pass
        self.append_moss_log("⏹️ Đã dừng Auto Moss trên toàn bộ tài khoản.")

    def _sync_event_checkbox_proxies_from_view(self):
        """Đồng bộ BooleanVar trên MirrorView/MossView → proxy checkbox SlotController đọc."""
        try:
            mv = getattr(self, "mirror_view", None)
            if mv:
                if hasattr(mv, "var_mirror_auto"):
                    self.cb_mirror_auto_schedule.set(bool(mv.var_mirror_auto.get()))
                if hasattr(mv, "var_mirror_lifecycle"):
                    self.cb_mirror_auto_lifecycle.set(bool(mv.var_mirror_lifecycle.get()))
                if hasattr(mv, "var_mirror_gremory"):
                    self.cb_mirror_auto_gremory.set(bool(mv.var_mirror_gremory.get()))
                if hasattr(mv, "var_mirror_prep"):
                    self.cb_mirror_auto_prep_before.set(bool(mv.var_mirror_prep.get()))
                if hasattr(mv, "var_mirror_telegram"):
                    self.cb_mirror_telegram_notify.set(bool(mv.var_mirror_telegram.get()))

            moss = getattr(self, "moss_view", None)
            if moss:
                if hasattr(moss, "var_moss_auto"):
                    self.cb_moss_auto_schedule.set(bool(moss.var_moss_auto.get()))
                if hasattr(moss, "var_moss_move"):
                    self.cb_moss_auto_move_before.set(bool(moss.var_moss_move.get()))
                if hasattr(moss, "var_moss_auto_clean"):
                    self.batch_moss_clean_cb.set(bool(moss.var_moss_auto_clean.get()))
                if hasattr(moss, "var_moss_clean_equip"):
                    self.cb_clean_equipment_trash.set(bool(moss.var_moss_clean_equip.get()))
        except Exception:
            pass

    def _on_events_telegram_toggle(self, enabled: bool):
        """Đồng bộ checkbox Telegram trên MirrorView với logic meg_gui."""
        self.cb_mirror_telegram_notify.set(bool(enabled))
        if hasattr(self, "on_toggle_mirror_telegram_notify"):
            self.on_toggle_mirror_telegram_notify()
        try:
            if hasattr(self, "mirror_view") and self.mirror_view:
                self.mirror_view.var_mirror_telegram.set(bool(self.cb_mirror_telegram_notify.get()))
        except Exception:
            pass

    def get_mirror_snipe_delay(self) -> int:
        if hasattr(self, "mirror_view") and hasattr(self.mirror_view, "get_snipe_delay"):
            return self.mirror_view.get_snipe_delay()
        return max(15, min(1000, int(getattr(self, "mirror_snipe_delay_ms", 35) or 35)))

    def get_mirror_snipe_dur(self) -> float:
        if hasattr(self, "mirror_view") and hasattr(self.mirror_view, "get_snipe_dur"):
            return self.mirror_view.get_snipe_dur()
        return max(3.0, min(120.0, float(getattr(self, "mirror_snipe_dur_s", 15.0) or 15.0)))

    def get_mirror_prefire_sec(self) -> float:
        if hasattr(self, "mirror_view") and hasattr(self.mirror_view, "get_prefire_sec"):
            return self.mirror_view.get_prefire_sec()
        return max(0.0, min(30.0, float(getattr(self, "mirror_prefire_sec", 2.0) or 2.0)))

    def get_mirror_schedule_config(self) -> Dict[str, Any]:
        self._sync_event_checkbox_proxies_from_view()
        return {
            "auto_schedule": bool(self.cb_mirror_auto_schedule.get()),
            "auto_prep_before": bool(self.cb_mirror_auto_prep_before.get()),
            "auto_lifecycle": bool(self.cb_mirror_auto_lifecycle.get()),
            "auto_gremory": bool(self.cb_mirror_auto_gremory.get()),
            "prefire_sec": self.get_mirror_prefire_sec(),
            "interval_ms": self.get_mirror_snipe_delay(),
            "max_duration_s": self.get_mirror_snipe_dur(),
            "selected_slots": [c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)],
        }

    def apply_moss_batch_settings(self, opts: Dict[str, Any]):
        """Áp dụng category/delay/auto_clean cho các slot Moss đã chọn."""
        flags_only = bool(opts.get("flags_only", False))
        auto_clean = bool(opts.get("auto_clean", True))
        clean_equip = bool(opts.get("clean_equipment_trash", True))
        cat = int(opts.get("category", 0) or 0)
        delay = int(opts.get("delay_ms", 1000) or 1000)
        cat_name = opts.get("category_name") or str(cat)
        count = 0
        for ctrl in self.controllers:
            if not getattr(ctrl, "moss_enabled", True):
                continue
            ctrl.moss_auto_clean = auto_clean
            ctrl.moss_clean_equipment_trash = clean_equip
            if not flags_only:
                ctrl.moss_category = cat
                ctrl.moss_delay_ms = delay
            try:
                ConfigPersistenceManager.save_moss_config(
                    ctrl.slot_idx,
                    int(getattr(ctrl, "moss_category", 0) or 0),
                    int(getattr(ctrl, "moss_delay_ms", 1000) or 1000),
                    int(getattr(ctrl, "moss_max_rolls", 0) or 0),
                    bool(getattr(ctrl, "moss_auto_clean", True)),
                    bool(getattr(ctrl, "moss_clean_equipment_trash", True)),
                )
            except Exception:
                pass
            count += 1
        if flags_only:
            self.append_moss_log(
                f"🧹 Đã cập nhật cờ dọn rác cho {count} slot Moss "
                f"(auto_clean={auto_clean}, kèm đồ rác={clean_equip})."
            )
        else:
            self.append_moss_log(
                f"⚡ Đã áp dụng '{cat_name}', delay={delay}ms cho {count} slot Moss đã chọn."
            )

    def on_moss_slot_category_changed(self, slot_idx: int, cat_name: str):
        ctrl = self.controllers[slot_idx - 1]
        cid = moss_cat_id(cat_name)
        ctrl.moss_category = cid
        try:
            ConfigPersistenceManager.save_moss_config(
                slot_idx, cid, ctrl.moss_delay_ms, ctrl.moss_max_rolls,
                ctrl.moss_auto_clean, getattr(ctrl, "moss_clean_equipment_trash", True)
            )
        except Exception:
            pass
        self.append_moss_log(f"[Slot {slot_idx:02d}] Cập nhật cấu hình quay: {cat_name}.")

    def on_moss_slot_delay_changed(self, slot_idx: int, delay_ms: int):
        ctrl = self.controllers[slot_idx - 1]
        ctrl.moss_delay_ms = int(delay_ms)
        try:
            ConfigPersistenceManager.save_moss_config(
                slot_idx, ctrl.moss_category, ctrl.moss_delay_ms, ctrl.moss_max_rolls,
                ctrl.moss_auto_clean, getattr(ctrl, "moss_clean_equipment_trash", True)
            )
        except Exception:
            pass
        self.append_moss_log(f"[Slot {slot_idx:02d}] Delay Moss = {delay_ms}ms.")

    def toggle_moss_slot_auto(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        if getattr(ctrl, "moss_running", False):
            ctrl.stop_moss()
            self.append_moss_log(f"[Slot {slot_idx:02d}] ⏹ Đã dừng Auto Moss.")
        else:
            ok = ctrl.start_moss()
            if ok:
                self.append_moss_log(f"[Slot {slot_idx:02d}] ▶️ Đã bắt đầu Auto Moss.")
            else:
                self.append_moss_log(f"[Slot {slot_idx:02d}] ⚠️ Không thể bắt đầu Moss (chưa kết nối?).")

    def on_moss_row_action(self, slot_idx: int, action: str):
        ctrl = self.controllers[slot_idx - 1]

        def _run(fn, label):
            def _w():
                try:
                    fn()
                    self.after(0, lambda: self.append_moss_log(f"[Slot {slot_idx:02d}] {label}"))
                except Exception as e:
                    self.after(0, lambda: self.append_moss_log(f"[Slot {slot_idx:02d}] ❌ {label}: {e}"))
            threading.Thread(target=_w, daemon=True).start()

        if action == "roll_once" and hasattr(ctrl, "roll_moss_once"):
            _run(ctrl.roll_moss_once, "🎲 Quay thử 1 lần")
        elif action == "open_npc" and hasattr(ctrl, "open_moss_npc"):
            _run(ctrl.open_moss_npc, "🚪 Mở bảng Moss NPC")
        elif action == "close_npc" and hasattr(ctrl, "close_moss_dialog"):
            _run(ctrl.close_moss_dialog, "🚪 Đóng bảng Moss NPC")
        elif action == "sell" and hasattr(ctrl, "sell_moss_inventory"):
            _run(ctrl.sell_moss_inventory, "💰 Bán Silvia")
        elif action == "clean" and hasattr(ctrl, "clean_moss_inventory"):
            _run(lambda: ctrl.clean_moss_inventory(run_in_thread=False), "🗑️ Ném rác tại chỗ")
        elif action == "move" and hasattr(ctrl, "move_to_moss_elbeland"):
            _run(ctrl.move_to_moss_elbeland, "🚶 Về NPC Moss")
        elif action == "unlock" and hasattr(ctrl, "unlock_and_close_inventory"):
            _run(ctrl.unlock_and_close_inventory, "🔓 Mở khóa thùng đồ")
        elif action == "menu_unavailable":
            self.append_moss_log("⚠️ Menu tiện ích không khả dụng (thiếu ModernActionMenu).")

    def on_moss_batch_tool(self, action: str):
        if action == "sell":
            self.sell_all_moss_inventories()
        elif action == "clean":
            self.clean_all_moss_inventories()
        elif action == "analyze":
            self.analyze_all_moss_inventories()
        elif action == "junk_dialog":
            self.open_junk_disposal_dialog()
        elif action == "move_all":
            self.move_all_to_moss_elbeland()
        elif action == "open_all":
            self.open_all_moss_npc()
        elif action == "close_all":
            self.close_all_moss_dialogs()
        elif action == "unlock_all":
            self.unlock_all_moss_inventories()
        elif action == "prepare_mirror":
            if hasattr(self, "prepare_all_mirror_event"):
                self.prepare_all_mirror_event()
            else:
                self.move_all_to_event_map()
                self.check_all_mirror_tickets()
        elif action == "click_mirror_npc":
            if hasattr(self, "click_all_mirror_npc"):
                self.click_all_mirror_npc()
            else:
                self.append_mirror_log("⚠️ click_all_mirror_npc chưa khả dụng.")

    def move_all_to_moss_elbeland(self):
        """Di chuyển ĐỒNG THỜI (Parallel Multi-threading) tất cả tài khoản Moss đã chọn về Elbeland tới NPC Moss (22, 225)."""
        selected_ctrls = list(self._iter_selected_moss_controllers())
        if not selected_ctrls:
            self.append_moss_log("⚠️ Không có tài khoản Moss đã chọn nào đang kết nối!")
            return

        cnt = len(selected_ctrls)
        self.append_moss_log(f"🚶 [Đồng thời] Bắt đầu phát lệnh di chuyển song song về NPC Moss (Elbeland 22, 225) cho {cnt} tài khoản...")

        for ctrl in selected_ctrls:
            threading.Thread(
                target=ctrl.move_to_moss_elbeland,
                name=f"MossMoveSlot_{ctrl.slot_idx}",
                daemon=True
            ).start()

    def open_all_moss_npc(self):
        """Gửi lệnh mở giao diện NPC Moss ĐỒNG THỜI cho các tài khoản Moss đã chọn."""
        selected_ctrls = list(self._iter_selected_moss_controllers())
        if not selected_ctrls:
            self.append_moss_log("⚠️ Không có tài khoản Moss đã chọn nào đang kết nối!")
            return

        cnt = len(selected_ctrls)
        self.append_moss_log(f"🚪 [Đồng thời] Đang gửi lệnh mở NPC Moss song song cho {cnt} tài khoản...")
        for ctrl in selected_ctrls:
            threading.Thread(
                target=ctrl.open_moss_npc,
                name=f"MossOpenSlot_{ctrl.slot_idx}",
                daemon=True
            ).start()

    def close_all_moss_dialogs(self):
        """Đóng bảng NPC Moss ĐỒNG THỜI cho các tài khoản Moss đã chọn."""
        selected_ctrls = list(self._iter_selected_moss_controllers())
        if not selected_ctrls:
            return
        for ctrl in selected_ctrls:
            threading.Thread(
                target=ctrl.close_moss_dialog,
                name=f"MossCloseSlot_{ctrl.slot_idx}",
                daemon=True
            ).start()
        self.append_moss_log(f"🚪 Đã gửi lệnh đóng bảng Moss cho {len(selected_ctrls)} tài khoản.")

    def unlock_all_moss_inventories(self):
        """Mở khóa kẹt thùng đồ ĐỒNG THỜI cho các tài khoản Moss đã chọn."""
        selected_ctrls = list(self._iter_selected_moss_controllers())
        if not selected_ctrls:
            return
        for ctrl in selected_ctrls:
            threading.Thread(
                target=ctrl.unlock_and_close_inventory,
                name=f"MossUnlockSlot_{ctrl.slot_idx}",
                daemon=True
            ).start()
        self.append_moss_log(f"🔓 Đã gửi lệnh mở khóa kẹt cho {len(selected_ctrls)} tài khoản.")

    def _run_on_selected_moss(self, method_name: str, ok_label: str, parallel: bool = True):
        selected_ctrls = list(self._iter_selected_moss_controllers())
        if not selected_ctrls:
            self.append_moss_log("⚠️ Không có tài khoản Moss đã chọn nào đang kết nối!")
            return

        if parallel:
            def _runner(c):
                fn = getattr(c, method_name, None)
                if fn:
                    try:
                        fn()
                    except Exception as e:
                        self.after(0, lambda ctrl=c, err=e: self.append_moss_log(
                            f"[Slot {ctrl.slot_idx:02d}] ❌ {method_name}: {err}"
                        ))

            for ctrl in selected_ctrls:
                threading.Thread(target=_runner, args=(ctrl,), daemon=True).start()
            self.after(0, lambda: self.append_moss_log(f"⚡ [Đồng thời] {ok_label} cho {len(selected_ctrls)} tài khoản đã chọn."))
        else:
            def _work():
                cnt = 0
                for ctrl in selected_ctrls:
                    fn = getattr(ctrl, method_name, None)
                    if not fn:
                        continue
                    try:
                        fn()
                        cnt += 1
                        time.sleep(0.05)
                    except Exception as e:
                        self.after(0, lambda c=ctrl, err=e: self.append_moss_log(
                            f"[Slot {c.slot_idx:02d}] ❌ {method_name}: {err}"
                        ))
                self.after(0, lambda: self.append_moss_log(f"{ok_label} cho {cnt} tài khoản đã chọn."))
            threading.Thread(target=_work, daemon=True).start()

    def _iter_selected_moss_controllers(self):
        for ctrl in self.controllers:
            if not getattr(ctrl, "moss_enabled", True):
                continue
            if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
                yield ctrl

    def clean_all_moss_inventories(self):
        """Ném tại chỗ đồ rác trên các slot Moss đã chọn."""
        def _cleaner():
            count_acc = 0
            total_cleaned = 0
            for ctrl in self._iter_selected_moss_controllers():
                try:
                    cleaned = ctrl.clean_moss_inventory(method="trash", category=-1, run_in_thread=False)
                    total_cleaned += (cleaned or 0)
                    count_acc += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {ctrl.slot_idx:02d}] ❌ Lỗi ném rác tại chỗ: {e}")
                time.sleep(0.1)
            if count_acc > 0:
                self.after(0, lambda: self.append_moss_log(
                    f"🗑️ Đã hoàn tất ném đồ tại chỗ cho {count_acc} tài khoản: Đã ném {total_cleaned} món đồ rác."
                ))
            else:
                self.after(0, lambda: self.append_moss_log(
                    "⚠️ Không có tài khoản Moss đã chọn nào đang kết nối để ném rác!"
                ))
        threading.Thread(target=_cleaner, daemon=True).start()

    def sell_all_moss_inventories(self):
        """Bán đồ rác tại Silvia cho các slot Moss đã chọn."""
        def _seller():
            count_acc = 0
            for ctrl in self._iter_selected_moss_controllers():
                try:
                    if hasattr(ctrl, "sell_moss_inventory"):
                        ctrl.sell_moss_inventory()
                        count_acc += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {ctrl.slot_idx:02d}] ❌ Lỗi bán đồ: {e}")
                time.sleep(0.5)
            if count_acc > 0:
                self.after(0, lambda c=count_acc: self.append_moss_log(
                    f"💰 Đã kích hoạt bán đồ tại Silvia cho {c} tài khoản đã chọn!"
                ))
            else:
                self.after(0, lambda: self.append_moss_log(
                    "⚠️ Không có tài khoản Moss đã chọn nào đang kết nối!"
                ))
        threading.Thread(target=_seller, daemon=True).start()

    def analyze_all_moss_inventories(self):
        """Phân tích rác hòm đồ các slot Moss đã chọn."""
        def _analyzer():
            count_acc = 0
            for ctrl in self._iter_selected_moss_controllers():
                try:
                    if hasattr(ctrl, "analyze_junk"):
                        ctrl.analyze_junk(max_items=10)
                        count_acc += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {ctrl.slot_idx:02d}] ❌ Lỗi phân tích rác: {e}")
                time.sleep(0.15)
            if count_acc == 0:
                self.after(0, lambda: self.append_moss_log(
                    "⚠️ Không có tài khoản Moss đã chọn nào đang kết nối để phân tích!"
                ))
        threading.Thread(target=_analyzer, daemon=True).start()

    def open_junk_disposal_dialog(self):
        """Hộp thoại xem trước rồi dọn rác (vứt / bán / auto)."""
        targets = list(self._iter_selected_moss_controllers())
        if not targets:
            self.append_moss_log("⚠️ Không có tài khoản nào đang kết nối để dọn rác. Hãy vào game trước.")
            return
        if not MegDirectEngine:
            self.append_moss_log("❌ Thiếu meg_direct_engine — không đọc được hòm đồ.")
            return

        self.append_moss_log(f"🔍 Đang đọc hòm đồ của {len(targets)} tài khoản ...")

        def _scan():
            reports = []
            for ctrl in targets:
                try:
                    eng = ctrl.engine or MegDirectEngine.get_engine(ctrl.assigned_pid)
                    if not eng:
                        continue
                    if not eng.is_ready:
                        eng.attach()
                    res = eng.analyze_junk_inventory(
                        category=-1,
                        max_junk_level=int(getattr(ctrl, "moss_max_junk_level", 6) or 6),
                        protected_slots=[],
                        ignore_type_heuristics=bool(getattr(ctrl, "moss_ignore_junk_type", False)),
                        clean_equipment_trash=bool(getattr(ctrl, "moss_clean_equipment_trash", True)),
                    )
                    reports.append((ctrl, res))
                except Exception as e:
                    self.after(0, lambda c=ctrl, err=e: self.append_moss_log(
                        f"[Slot {c.slot_idx:02d}] ❌ Lỗi đọc hòm đồ: {err}"
                    ))
            self.after(0, lambda: self._show_junk_disposal_dialog(reports))

        threading.Thread(target=_scan, daemon=True).start()

    def _show_junk_disposal_dialog(self, reports):
        if not reports:
            self.append_moss_log("⚠️ Không đọc được hòm đồ của tài khoản nào.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Dọn Rác Hòm Đồ")
        dlg.geometry("720x560")
        dlg.configure(fg_color=Colors.BG_ROOT)
        dlg.transient(self)
        dlg.grab_set()
        self._setup_window_icon(dlg)
        dlg.after(100, lambda: self._setup_window_icon(dlg))

        ctk.CTkLabel(
            dlg, text="🧹 DỌN RÁC HÒM ĐỒ (đọc RVA)",
            font=Fonts.SECTION, text_color=Colors.PURPLE
        ).pack(pady=(12, 6))

        box = ctk.CTkTextbox(dlg, width=680, height=380, font=Fonts.MONO,
                             fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD)
        box.pack(padx=14, pady=6, fill="both", expand=True)

        total_junk = 0
        total_held = 0
        lines = []
        for ctrl, res in reports:
            if not isinstance(res, dict) or not res.get("ok"):
                lines.append(f"[Slot {ctrl.slot_idx:02d}] ❌ Không đọc được hòm đồ")
                lines.append("")
                continue
            junk = res.get("junk", []) or res.get("junkSlots", []) or []
            held = res.get("kept", []) or res.get("keptSlots", []) or []
            total_junk += len(junk)
            total_held += len(held)
            lines.append(f"[Slot {ctrl.slot_idx:02d} · {getattr(ctrl, 'char_name', '---')}] "
                         f"dọn được {len(junk)} · giữ {len(held)}")
            for it in junk[:25]:
                if isinstance(it, dict):
                    lines.append(
                        f"  - slot {it.get('slot', '?')}: {it.get('name', '?')} +{it.get('level', 0)}"
                    )
                else:
                    lines.append(f"  - {it}")
            if len(junk) > 25:
                lines.append(f"      ... và {len(junk) - 25} món nữa")
            lines.append("")
        box.insert("1.0", "\n".join(lines) if lines else "Không có dữ liệu.")
        box.configure(state="disabled")

        mode_bar = ctk.CTkFrame(dlg, fg_color="transparent")
        mode_bar.pack(fill="x", padx=14, pady=(4, 0))
        ctk.CTkLabel(mode_bar, text="Cách dọn:", font=Fonts.BODY).pack(side="left", padx=(0, 8))
        mode_var = ctk.StringVar(value="Tự động (vứt → bán)")
        ctk.CTkOptionMenu(
            mode_bar,
            values=["Tự động (vứt → bán)", "Chỉ vứt", "Chỉ bán"],
            variable=mode_var,
            width=220,
            font=Fonts.BODY
        ).pack(side="left")

        ctk.CTkLabel(
            dlg,
            text=f"Tổng: dọn được {total_junk} món · giữ {total_held} món. "
                 f"Slot 0-11 (trang bị) và đồ Exc/Set/Socket/Harmony/Ngọc luôn được bảo vệ.",
            font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED
        ).pack(pady=(6, 0))

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=10)

        def _execute():
            mode = {
                "Tự động (vứt → bán)": "auto",
                "Chỉ vứt": "drop",
                "Chỉ bán": "sell",
            }.get(mode_var.get(), "auto")
            dlg.destroy()
            self._run_junk_disposal(reports, mode)

        exec_btn = ctk.CTkButton(
            btns, text="Thực hiện", width=120, fg_color=Colors.ROSE, hover_color=Colors.ROSE_HOVER,
            font=Fonts.BODY_BOLD, command=_execute
        )
        exec_btn.pack(side="left", padx=6)
        ctk.CTkButton(
            btns, text="Hủy", width=120, fg_color="#334155", hover_color="#475569",
            font=Fonts.BODY, command=dlg.destroy
        ).pack(side="left", padx=6)
        if total_junk == 0:
            exec_btn.configure(state="disabled")
            self.append_moss_log("⚠️ Không có món nào đủ điều kiện dọn.")

    def _run_junk_disposal(self, reports, mode: str):
        def _work():
            total = 0
            for ctrl, _res in reports:
                try:
                    eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine else None)
                    if not eng:
                        continue
                    if not eng.is_ready:
                        eng.attach()
                    out = eng.dispose_junk_items(
                        mode=mode,
                        protected_slots=[],
                        category=-1,
                        include_extended=True,
                        max_junk_level=int(getattr(ctrl, "moss_max_junk_level", 6) or 6),
                        ignore_type_heuristics=bool(getattr(ctrl, "moss_ignore_junk_type", False)),
                        clean_equipment_trash=bool(getattr(ctrl, "moss_clean_equipment_trash", True)),
                    )
                    cleaned = int((out or {}).get("cleaned", 0) or 0)
                    total += cleaned
                    self.after(0, lambda c=ctrl, o=out, n=cleaned: self.append_moss_log(
                        f"[Slot {c.slot_idx:02d} - {c.char_name}] 🗑️ Dọn {n} món "
                        f"(vứt {o.get('dropped', 0)}, bán {o.get('sold', 0)}) — {o.get('reason')}"
                    ))
                    time.sleep(0.2)
                except Exception as e:
                    self.after(0, lambda c=ctrl, err=e: self.append_moss_log(
                        f"[Slot {c.slot_idx:02d}] ❌ Lỗi dọn rác: {err}"
                    ))
            self.after(0, lambda t=total: self.append_moss_log(f"🧹 Hoàn tất: đã dọn tổng cộng {t} món."))

        threading.Thread(target=_work, daemon=True).start()

    def toggle_event_participant(self, event_type: str, slot_idx: int, is_enabled: bool):
        ctrl = self.controllers[slot_idx - 1]
        if event_type == "mirror":
            ctrl.mirror_enabled = is_enabled
        elif event_type == "moss":
            ctrl.moss_enabled = is_enabled
        # Persist selected slots
        try:
            if event_type == "mirror":
                selected = [c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)]
                cfg = ConfigPersistenceManager.load_mirror_schedule_config()
                ConfigPersistenceManager.save_mirror_schedule_config(
                    auto_schedule=cfg.get("auto_schedule", True),
                    auto_prep_before=cfg.get("auto_prep_before", True),
                    prefire_sec=cfg.get("prefire_sec", 5.0),
                    auto_lifecycle=cfg.get("auto_lifecycle", True),
                    auto_gremory=cfg.get("auto_gremory", True),
                    selected_slots=selected,
                )
            else:
                selected = [c.slot_idx for c in self.controllers if getattr(c, "moss_enabled", True)]
                cfg = ConfigPersistenceManager.load_moss_schedule_config()
                ConfigPersistenceManager.save_moss_schedule_config(
                    auto_schedule=cfg.get("auto_schedule", True),
                    auto_move_before=cfg.get("auto_move_before", True),
                    selected_slots=selected,
                )
        except Exception:
            pass

    def save_event_schedule(self, event_type: str, opts: Dict[str, Any]):
        try:
            if event_type == "mirror":
                # Sync proxies trước khi lưu / kích hoạt lifecycle
                if "auto_schedule" in opts:
                    self.cb_mirror_auto_schedule.set(bool(opts.get("auto_schedule", True)))
                if "auto_prep_before" in opts:
                    self.cb_mirror_auto_prep_before.set(bool(opts.get("auto_prep_before", True)))
                if "auto_lifecycle" in opts:
                    self.cb_mirror_auto_lifecycle.set(bool(opts.get("auto_lifecycle", True)))
                if "auto_gremory" in opts:
                    self.cb_mirror_auto_gremory.set(bool(opts.get("auto_gremory", True)))
                if "prefire_sec" in opts:
                    self.mirror_prefire_sec = float(opts["prefire_sec"])
                if "interval_ms" in opts:
                    self.mirror_snipe_delay_ms = int(opts["interval_ms"])
                if "max_duration_s" in opts:
                    self.mirror_snipe_dur_s = float(opts["max_duration_s"])

                selected = [c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)]
                ConfigPersistenceManager.save_mirror_schedule_config(
                    auto_schedule=opts.get("auto_schedule", True),
                    auto_prep_before=opts.get("auto_prep_before", True),
                    auto_lifecycle=opts.get("auto_lifecycle", True),
                    auto_gremory=opts.get("auto_gremory", True),
                    prefire_sec=self.get_mirror_prefire_sec(),
                    interval_ms=self.get_mirror_snipe_delay(),
                    max_duration_s=self.get_mirror_snipe_dur(),
                    selected_slots=selected,
                )
                self.append_mirror_log(f"Đã lưu cấu hình Mirror (Bắn trước: {self.get_mirror_prefire_sec():.1f}s, Chu kỳ: {self.get_mirror_snipe_delay()}ms).")
            else:
                if "auto_schedule" in opts:
                    self.cb_moss_auto_schedule.set(bool(opts.get("auto_schedule", True)))
                if "auto_move_before" in opts:
                    self.cb_moss_auto_move_before.set(bool(opts.get("auto_move_before", True)))
                if hasattr(self, "on_toggle_moss_auto_schedule"):
                    self.on_toggle_moss_auto_schedule()
                else:
                    selected = [c.slot_idx for c in self.controllers if getattr(c, "moss_enabled", True)]
                    ConfigPersistenceManager.save_moss_schedule_config(
                        auto_schedule=opts.get("auto_schedule", True),
                        auto_move_before=opts.get("auto_move_before", True),
                        selected_slots=selected,
                    )
                    self.append_moss_log("Đã lưu lịch Moss.")
        except Exception as e:
            self.log_message(f"Lỗi lưu lịch sự kiện: {e}", "ERROR")

    # ==========================================================================
    # DIALOGS / LICENSE / UPDATES / DEVIL
    # ==========================================================================
    def show_help(self):
        messagebox.showinfo(
            "MEGAMU Auto Train Dashboard",
            f"{APP_NAME} {APP_VERSION} (Zero-Lag UI)\n\n"
            "- Kết nối native không chiếm chuột\n"
            "- Auto train đa slot, Mirror, Moss, Auto Login\n"
            "- Dashboard card layout tối ưu quét nhanh\n\n"
            "Tác giả: MEGATEAM\n"
            "Hotline / Zalo: 036.203.1354"
        )

    def open_license_dialog(self):
        """Delegate to meg_gui license dialog by temporarily hosting methods if possible."""
        try:
            # Prefer license_client based simple dialog if meg_gui dialog is too heavy to bind
            if not license_client:
                messagebox.showinfo("License", "Module license_client chưa khả dụng.")
                return

            if hasattr(self, "_license_dialog") and self._license_dialog is not None and self._license_dialog.winfo_exists():
                self._license_dialog.lift()
                self._license_dialog.focus_force()
                return

            dialog = ctk.CTkToplevel(self)
            self._license_dialog = dialog
            dialog.title("Quản lý Bản Quyền - MEGAMU Auto Train")
            dialog.geometry("480x420")
            dialog.resizable(False, False)
            dialog.configure(fg_color=Colors.BG_ROOT)
            dialog.transient(self)
            dialog.grab_set()
            self._setup_window_icon(dialog)
            dialog.after(100, lambda: self._setup_window_icon(dialog))

            pad = ctk.CTkFrame(dialog, fg_color="transparent")
            pad.pack(fill="both", expand=True, padx=20, pady=18)

            ctk.CTkLabel(pad, text="QUẢN LÝ BẢN QUYỀN", font=Fonts.SECTION, text_color=Colors.TEXT_MAIN).pack(anchor="w")
            ctk.CTkLabel(pad, text="Kích hoạt key & xem trạng thái HWID", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM).pack(anchor="w", pady=(0, 12))

            status = license_client.get_license_display_text() if hasattr(license_client, "get_license_display_text") else "N/A"
            card = ctk.CTkFrame(pad, fg_color=Colors.BG_CARD, border_width=1, border_color=Colors.BORDER_CARD, corner_radius=Radii.MD)
            card.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(card, text=f"Trạng thái: {status}", font=Fonts.BODY_BOLD, text_color=Colors.CYAN).pack(anchor="w", padx=12, pady=12)

            hwid = ""
            try:
                hwid = license_client.get_hwid() if hasattr(license_client, "get_hwid") else ""
            except Exception:
                hwid = ""
            ctk.CTkLabel(pad, text="HWID", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM).pack(anchor="w")
            ent_hwid = ctk.CTkEntry(pad, height=32, fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD)
            ent_hwid.pack(fill="x", pady=(2, 10))
            ent_hwid.insert(0, hwid)
            ent_hwid.configure(state="readonly")

            ctk.CTkLabel(pad, text="License Key", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM).pack(anchor="w")
            ent_key = ctk.CTkEntry(pad, height=32, fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD)
            ent_key.pack(fill="x", pady=(2, 12))

            def do_activate():
                key = ent_key.get().strip()
                if not key:
                    messagebox.showwarning("License", "Vui lòng nhập license key.")
                    return
                try:
                    ok, msg, _info = license_client.activate_license(key) if hasattr(license_client, "activate_license") else (False, "API không hỗ trợ", None)
                    if ok:
                        messagebox.showinfo("License", msg or "Kích hoạt thành công.")
                        self._update_header_stats_internal()
                        dialog.destroy()
                    else:
                        messagebox.showerror("License", msg or "Kích hoạt thất bại.")
                except Exception as e:
                    messagebox.showerror("License", str(e))

            make_action_button(pad, "Kích hoạt", do_activate, tone="success", height=34).pack(fill="x")
            make_action_button(pad, "Đóng", dialog.destroy, tone="ghost", height=30).pack(fill="x", pady=(8, 0))
        except Exception as e:
            messagebox.showerror("License", f"Không mở được hộp thoại: {e}")

    def _verify_license_async(self):
        if not license_client:
            return
        try:
            lic_data = license_client.load_license_data() if hasattr(license_client, "load_license_data") else {}
            if lic_data and lic_data.get("license_key") and hasattr(license_client, "verify_license"):
                license_client.verify_license()
            self.after(0, self._update_header_stats_internal)
        except Exception:
            pass

    def check_for_updates_ui(self, manual: bool = False):
        def worker():
            try:
                if not updater:
                    self.after(0, lambda: messagebox.showinfo("Cập nhật", "Module updater chưa khả dụng."))
                    return
                res = updater.check_for_updates(APP_VERSION)
                has_update = bool(res.get("has_update")) if isinstance(res, dict) else False
                if has_update:
                    latest = res.get("latest_version", "?")
                    notes = res.get("notes") or res.get("changelog") or ""
                    msg = f"Có bản mới: {latest}\n\n{notes}"
                    self.after(0, lambda: messagebox.showinfo("Cập nhật", msg))
                elif manual:
                    self.after(0, lambda: messagebox.showinfo("Cập nhật", f"Bạn đang dùng bản mới nhất ({APP_VERSION})."))
            except Exception as e:
                if manual:
                    self.after(0, lambda: messagebox.showerror("Cập nhật", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def open_devil_global_config_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Cài Đặt Devil Square (DS)")
        dlg.geometry("520x430")
        dlg.resizable(False, False)
        dlg.configure(fg_color=Colors.BG_ROOT)
        dlg.transient(self)
        dlg.grab_set()
        self._setup_window_icon(dlg)
        dlg.after(100, lambda: self._setup_window_icon(dlg))

        pad = ctk.CTkFrame(dlg, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(pad, text="🔥 CẤU HÌNH AUTO DEVIL SQUARE", font=Fonts.SECTION, text_color="#f43f5e").pack(anchor="w")
        ctk.CTkLabel(pad, text="Áp dụng cho toàn bộ slot đang quản lý", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM).pack(anchor="w", pady=(0, 12))

        body = ctk.CTkFrame(pad, fg_color=Colors.BG_CARD, border_width=1, border_color=Colors.BORDER_CARD, corner_radius=Radii.MD)
        body.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(body, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        var_enable_all = ctk.BooleanVar(value=any(getattr(c, "auto_devil", False) for c in self.controllers))
        ctk.CTkCheckBox(
            inner,
            text="Bật Auto Devil Square cho toàn bộ tài khoản",
            variable=var_enable_all,
            font=Fonts.BODY_BOLD,
            checkbox_width=16,
            checkbox_height=16,
            fg_color="#e11d48",
            hover_color="#be123c"
        ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(inner, text="Bắt đầu đi Devil từ số Reset:", font=Fonts.BODY, text_color=Colors.TEXT_MUTED).pack(anchor="w")
        first_min_rs = getattr(self.controllers[0], "devil_min_resets", 0) if self.controllers else 0
        ent_min_rs = ctk.CTkEntry(inner, width=80, height=30, justify="center", fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD)
        ent_min_rs.pack(anchor="w", pady=(4, 12))
        ent_min_rs.insert(0, str(first_min_rs))

        ctk.CTkLabel(inner, text="Ưu tiên loại vé:", font=Fonts.BODY, text_color=Colors.TEXT_MUTED).pack(anchor="w")
        ticket_var = ctk.StringVar(value=getattr(self.controllers[0], "devil_ticket_mode", "auto") if self.controllers else "auto")
        for label, val in (("Tự động", "auto"), ("Vé thường", "normal"), ("Vé VIP", "vip")):
            ctk.CTkRadioButton(inner, text=label, variable=ticket_var, value=val, font=Fonts.BODY).pack(anchor="w", pady=2)

        def save_devil():
            try:
                min_rs = int(ent_min_rs.get().strip() or "0")
            except Exception:
                min_rs = 0
            mode = ticket_var.get()
            enabled = var_enable_all.get()
            for c in self.controllers:
                c.auto_devil = enabled
                c.devil_min_resets = min_rs
                c.devil_ticket_mode = mode
            self.log_message(f"Đã lưu Devil Square: enable={enabled}, min_rs={min_rs}, ticket={mode}", "SUCCESS")
            dlg.destroy()

        make_action_button(inner, "Lưu cấu hình", save_devil, tone="success", height=34).pack(fill="x", pady=(16, 0))

    # ==========================================================================
    # LOG + SLOTCONTROLLER COMPAT
    # ==========================================================================
    def log_message(self, text: str, level: str = "INFO"):
        self.state_mgr.append_log(text, level)

    def append_log(self, text: str, level: str = "INFO"):
        self.log_message(text, level)

    def _dedupe_event_log(self, channel: str, text: str, window_s: float = 1.2) -> bool:
        """Trả True nếu nên ghi log; False nếu trùng message gần đây."""
        try:
            store = getattr(self, "_event_log_dedupe", None)
            if store is None:
                store = {}
                self._event_log_dedupe = store
            key = f"{channel}|{text}"
            now = time.time()
            last = float(store.get(key, 0.0) or 0.0)
            if now - last < window_s:
                return False
            store[key] = now
            # Giữ map nhỏ
            if len(store) > 200:
                cutoff = now - 10.0
                self._event_log_dedupe = {k: v for k, v in store.items() if v >= cutoff}
            return True
        except Exception:
            return True

    def append_mirror_log(self, text: str):
        if not self._dedupe_event_log("mirror", text):
            return
        # Chỉ đẩy vào panel Mirror + state log 1 lần (tránh trùng dòng trên UI)
        try:
            if hasattr(self, "mirror_view") and self.mirror_view and hasattr(self.mirror_view, "append_log"):
                self.mirror_view.append_log(text)
            else:
                self.log_message(text, "INFO")
        except Exception:
            self.log_message(text, "INFO")

    def append_moss_log(self, text: str):
        if not self._dedupe_event_log("moss", text):
            return
        try:
            if hasattr(self, "moss_view") and self.moss_view and hasattr(self.moss_view, "append_log"):
                self.moss_view.append_log(text)
            else:
                self.log_message(text, "INFO")
        except Exception:
            self.log_message(text, "INFO")

    def batch_launch_all_accounts(self):
        """Xác nhận số màn sẽ mở trước khi chạy batch login của meg_gui."""
        if not self.account_mgr:
            return

        if hasattr(self, "autologin_view") and hasattr(self.autologin_view, "get_launchable_accounts"):
            cur_cat = getattr(self.autologin_view, "current_category", "Tất cả")
            enabled = self.autologin_view.get_launchable_accounts()
        else:
            cur_cat = getattr(self, "current_autologin_category", "Tất cả")
            enabled = self.account_mgr.get_enabled_accounts(category=cur_cat)

        if not enabled:
            cat_str = f" trong nhóm '{cur_cat}'" if cur_cat != "Tất cả" else ""
            self.append_autologin_log(f"⚠️ Không có tài khoản nào được tích chọn để mở{cat_str}!")
            try:
                messagebox.showwarning(
                    "Mở & Login",
                    f"Không có tài khoản nào được chọn để mở{cat_str}."
                )
            except Exception:
                pass
            return

        online_count = 0
        will_open = 0
        for acc in enabled:
            try:
                is_online, _pid = self.is_account_logged_in(acc)
            except Exception:
                is_online = False
            if is_online:
                online_count += 1
            else:
                will_open += 1

        cat_tag = f"\nNhóm: {cur_cat}" if cur_cat and cur_cat != "Tất cả" else ""
        if will_open <= 0:
            msg = (
                f"Đã chọn {len(enabled)} tài khoản{cat_tag}\n"
                f"Đang online: {online_count}\n"
                f"Số màn sẽ mở mới: 0\n\n"
                "Tất cả tài khoản đã chọn đều đang chạy.\n"
                "Bạn vẫn muốn tiếp tục kiểm tra / đồng bộ không?"
            )
        else:
            msg = (
                f"Đã chọn {len(enabled)} tài khoản{cat_tag}\n"
                f"Đang online (bỏ qua): {online_count}\n"
                f"Số màn sẽ mở: {will_open}\n\n"
                f"Bạn có đồng ý mở {will_open} cửa sổ MEGAMU và login không?"
            )

        if not messagebox.askyesno("Xác nhận Mở & Login", msg):
            self.append_autologin_log(
                f"⏹️ Đã hủy Mở & Login tất cả (dự kiến mở {will_open}/{len(enabled)} màn)."
            )
            return

        self.append_autologin_log(
            f"✅ Đã xác nhận mở {will_open} màn (chọn {len(enabled)}, online {online_count})."
        )
        return DashboardApp.batch_launch_all_accounts(self)

    def update_slot_ui_status(self, slot_idx: int, text: str):
        self.state_mgr.update_slot_telemetry(slot_idx, status=text)

    def update_slot_ui_auto(self, slot_idx: int, is_on: bool):
        self.state_mgr.update_slot_telemetry(slot_idx, is_running=is_on)

    def update_slot_ui_telemetry(self, slot_idx: int, name: str, lvl: str, coords: str, points: Optional[int] = None, class_code: Optional[str] = None, server: Optional[str] = None, resets: Optional[int] = None):
        if 1 <= slot_idx <= len(self.controllers):
            ctrl = self.controllers[slot_idx - 1]
            if name and name != "---":
                ctrl.char_name = name
                ctrl.last_known_char_name = name
            if lvl and lvl != "---":
                ctrl.level = lvl
            if coords and coords != "--,--":
                ctrl.coords = coords
            if server and server != "---":
                ctrl.server_name = server
        self.state_mgr.update_slot_telemetry(
            slot_idx=slot_idx,
            char_name=name,
            level=lvl,
            coords=coords,
            points=points,
            class_code=class_code,
            server=server,
            resets=resets
        )

    def _bind_pid_to_slot_ui(self, ctrl, pid: int, char_name: str):
        """Gán PID vào SlotController và cập nhật giao diện Dashboard."""
        try:
            ctrl.attach_pid(pid)
            if char_name and char_name != "(Mặc định)":
                ctrl.char_name = char_name
                ctrl.last_known_char_name = char_name
            self.update_slot_ui_telemetry(ctrl.slot_idx, ctrl.char_name, ctrl.level, ctrl.coords, server=ctrl.server_name)
            self.state_mgr.update_slot_telemetry(ctrl.slot_idx, assigned_pid=pid, char_name=ctrl.char_name)
            self.state_mgr.global_dirty = True
            if hasattr(self, "update_header_stats"):
                self.update_header_stats()
            self.log_message(f"[Slot {ctrl.slot_idx:02d}] Đã gán PID {pid} ({ctrl.char_name}) và kích hoạt telemetry!", "SUCCESS")
            # Đồng bộ ngay sang Mirror & Moss View
            if hasattr(self, "mirror_view") and self.mirror_view:
                self.after(0, self.mirror_view.refresh_rows)
                self.trigger_mirror_ticket_scan(ctrl.slot_idx)
            if hasattr(self, "moss_view") and self.moss_view:
                self.after(0, self.moss_view.refresh_moss_rows)
        except Exception:
            pass

    bind_pid_to_slot_ui = _bind_pid_to_slot_ui

    def stream_slot_coords(self, slot_idx: int, coords: str, server: str = ""):
        self.state_mgr.update_slot_telemetry(slot_idx, coords=coords, server=server)

    def update_header_stats(self):
        self._update_header_stats_internal()

    def _on_acc_toggle(self, acc: Dict[str, Any], enabled: bool):
        acc["enabled"] = bool(enabled)
        if self.account_mgr:
            self.account_mgr.save_accounts()

    def _on_acc_srv_change(self, acc: Dict[str, Any], srv_text: str):
        try:
            s_num = int(srv_text.replace("Server ", "").strip())
            acc["server"] = s_num
            if self.account_mgr:
                self.account_mgr.save_accounts()
            try:
                from meg_account_manager import configure_megamu_registry_for_server
                configure_megamu_registry_for_server(s_num, acc.get("username", ""), acc.get("character", ""))
            except Exception:
                pass
            self.append_autologin_log(f"⚙️ [Account: {acc.get('username')}] Đã chuyển mục tiêu sang Server {s_num} (đã ghi Registry)")
        except Exception:
            pass

    def open_update_dialog(self):
        self.check_for_updates_ui(manual=True)

    def on_closing(self):
        self.running = False
        if hasattr(self, "engine_sync"):
            self.engine_sync.stop()
        self.destroy()

    # ------------------------------------------------------------------
    # AUTO LOGIN SHIMS (tương thích DashboardApp của meg_gui)
    # ------------------------------------------------------------------
    def _safe_append_textbox(self, textbox, text: str):
        try:
            if textbox is None:
                return
            textbox.configure(state="normal")
            t_str = time.strftime("%H:%M:%S")
            textbox.insert("end", f"[{t_str}] {text}\n")
            textbox.see("end")
            # Giới hạn dòng
            try:
                line_count = int(textbox.index("end-1c").split(".")[0])
                if line_count > 500:
                    textbox.delete("1.0", f"{line_count - 400}.0")
            except Exception:
                pass
            textbox.configure(state="disabled")
        except Exception:
            pass

    def create_slot_row(self, slot_idx: int):
        """Tạo card slot mới trong TrainSlotsView (tương thích các hàm tự động thêm slot)."""
        if hasattr(self, "train_view") and self.train_view:
            self.train_view.add_slot_card(slot_idx)

    def add_new_slot(self):
        """Thêm slot mới nếu còn hạn mức License (tối đa MAX_SLOTS)."""
        lic_data = license_client.load_license_data() if license_client else {}
        is_valid = license_client.is_license_valid() if license_client else False
        max_allowed = int(lic_data.get("max_slots", 5 if not is_valid else 10))
        cur_count = len(self.controllers)
        if cur_count >= max_allowed or cur_count >= MAX_SLOTS:
            if not is_valid:
                msg = f"Chế độ dùng thử mặc định chỉ hỗ trợ tối đa {max_allowed} tài khoản!\nVui lòng kích hoạt Bản Quyền để thêm tài khoản."
            else:
                msg = f"Gói bản quyền hiện tại của bạn cho phép tối đa {max_allowed} tài khoản.\nVui lòng liên hệ nâng cấp gói bản quyền để mở thêm Slot."
            self.log_message(msg, "WARNING")
            try:
                messagebox.showinfo("Giới Hạn Bản Quyền", msg)
            except Exception:
                pass
            return

        new_slot_idx = cur_count + 1
        default_profile = 1
        self.slot_assignments[new_slot_idx] = default_profile
        try:
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
        except Exception:
            pass

        ctrl = SlotController(new_slot_idx, self, default_profile=default_profile)
        self.controllers.append(ctrl)

        # 1. Thêm UI card vào TrainSlotsView
        if hasattr(self, "train_view") and self.train_view:
            self.train_view.add_slot_card(new_slot_idx)

        # 2. Thêm UI row vào MirrorView
        if hasattr(self, "mirror_view") and self.mirror_view:
            if hasattr(self.mirror_view, "_create_row"):
                try:
                    self.mirror_view._create_row(ctrl)
                except Exception:
                    pass

        # 3. Thêm UI row vào MossView
        if hasattr(self, "moss_view") and self.moss_view:
            if hasattr(self.moss_view, "_create_moss_slot_row"):
                try:
                    self.moss_view._create_moss_slot_row(ctrl)
                except Exception:
                    pass

        self.update_header_stats()
        self.log_message(f"➕ Đã thêm Account Slot #{new_slot_idx:02d} thành công (Hiện có {len(self.controllers)} slot).", "SUCCESS")

    def remove_last_slot(self):
        """Xóa slot tài khoản cuối cùng."""
        if len(self.controllers) <= 1:
            self.log_message("Không thể xóa: Cần giữ lại ít nhất 1 tài khoản.", "WARNING")
            try:
                messagebox.showwarning("Cảnh Báo", "Cần giữ lại ít nhất 1 tài khoản trong danh sách.")
            except Exception:
                pass
            return

        last_idx = len(self.controllers)
        ctrl = self.controllers.pop()

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

        # Xóa khỏi slot_assignments và lưu lại file
        self.slot_assignments.pop(last_idx, None)
        try:
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
        except Exception:
            pass

        # 1. Xóa UI card trong TrainSlotsView
        if hasattr(self, "train_view") and self.train_view:
            self.train_view.remove_last_card()

        # 2. Xóa UI row trong MirrorView
        if hasattr(self, "mirror_view") and self.mirror_view:
            if hasattr(self.mirror_view, "mirror_ui_elements"):
                el_mir = self.mirror_view.mirror_ui_elements.pop(last_idx, None)
                if el_mir and el_mir.get("row_frame"):
                    try:
                        el_mir["row_frame"].destroy()
                    except Exception:
                        pass
            if hasattr(self.mirror_view, "mirror_cb_vars"):
                self.mirror_view.mirror_cb_vars.pop(last_idx, None)
            if hasattr(self.mirror_view, "_update_badge"):
                self.mirror_view._update_badge()

        # 3. Xóa UI row trong MossView
        if hasattr(self, "moss_view") and self.moss_view:
            if hasattr(self.moss_view, "moss_ui_elements"):
                el_m = self.moss_view.moss_ui_elements.pop(last_idx, None)
                if el_m and el_m.get("row_frame"):
                    try:
                        el_m["row_frame"].destroy()
                    except Exception:
                        pass
            if hasattr(self.moss_view, "moss_cb_vars"):
                self.moss_view.moss_cb_vars.pop(last_idx, None)
            if hasattr(self.moss_view, "_update_moss_badge"):
                self.moss_view._update_moss_badge()

        self.update_header_stats()
        self.log_message(f"➖ Đã xóa Slot #{last_idx:02d} thành công (Còn lại {len(self.controllers)} slot).", "INFO")

    def _background_scan_games(self):
        """Quét tiến trình MEGAMU — ưu tiên dữ liệu từ engine_sync, tránh EnumWindows dày."""
        try:
            # Nếu BackgroundEngineSync vừa cập nhật gần đây thì dùng luôn, không EnumWindows lại
            cached = None
            try:
                cached = self.state_mgr.get_detected_games()
            except Exception:
                cached = None
            if cached is not None and (time.time() - getattr(self, "_last_forced_game_enum_ts", 0) < 5.0):
                self.detected_games = cached
                return

            games = enumerate_megamu_processes()
            self.detected_games = {pid: (title or f"MEGAMU ({pid})") for pid, title in games.items()}
            self._last_forced_game_enum_ts = time.time()
            self.state_mgr.global_dirty = True
        except Exception:
            pass

    def sync_autologin_table_values(self):
        """Đồng bộ Online/Offline Auto Login — throttle + dùng cache PID đã quét."""
        if not hasattr(self, "autologin_view") or not self.account_mgr:
            return
        if getattr(self, "active_tab", "") != "autologin" and self.active_tab_name != "autologin":
            return

        now = time.time()
        # Quét cửa sổ tối đa mỗi 5s (engine_sync đã nuôi detected_games)
        if now - getattr(self, "_last_bg_scan_time", 0) > 5.0:
            self._last_bg_scan_time = now
            self._background_scan_games()

        detected = getattr(self, "detected_games", {}) or {}
        for acc in self.account_mgr.accounts:
            u = acc.get("username", "")
            is_online, live_pid = self.is_account_logged_in(acc)
            live_srv = None
            if is_online and live_pid:
                p_title = detected.get(live_pid, "")
                try:
                    live_srv = server_from_window_title(p_title)
                except Exception:
                    live_srv = None
                if not live_srv:
                    for c_slot in self.controllers:
                        if c_slot.assigned_pid == live_pid and getattr(c_slot, "server_num", None):
                            live_srv = c_slot.server_num
                            break
                if live_srv and live_srv > 0 and acc.get("server") != live_srv:
                    acc["server"] = live_srv

            self.autologin_view.update_account_state(
                username=u,
                is_online=is_online,
                pid=live_pid,
                live_srv=live_srv
            )


# ---------------------------------------------------------------------------
# Gắn TOÀN BỘ logic DashboardApp (trừ build_* UI monolith) vào shell mới
# ---------------------------------------------------------------------------
import inspect as _inspect

_EXCLUDE_BIND = {
    "build_ui",
    "build_accounts_view",
    "build_autologin_view",
    "build_logs_view",
    "build_mirror_view",
    "build_moss_view",
    "build_profiles_view",
    # Optimized đã có implementation riêng — không đè
    "__init__",
    "on_closing",
    "switch_tab",
    "log_message",
    "append_log",
    "append_mirror_log",
    "append_moss_log",
    "update_slot_ui_status",
    "update_slot_ui_auto",
    "update_slot_ui_telemetry",
    "stream_slot_coords",
    "update_header_stats",
    "get_mirror_snipe_delay",
    "get_mirror_snipe_dur",
    "get_mirror_prefire_sec",
    "get_mirror_schedule_config",
    "trigger_mirror_snipe",
    "trigger_moss_merchant",
    "stop_all_moss",
    "move_all_to_moss_elbeland",
    "open_all_moss_npc",
    "close_all_moss_dialogs",
    "unlock_all_moss_inventories",
    "move_all_to_event_map",
    "save_event_schedule",
    "create_slot_row",
    "add_new_slot",
    "remove_last_slot",
    "arrange_windows_by_preset",
    "arrange_windows_default",
    "close_all_games",
    "refresh_games",
    "connect_all",
    "assign_all",
    "on_slot_auto_toggle",
    "toggle_all_auto",
    "on_slot_pid_selected",
    "on_slot_profile_selected",
    "save_slot_settings",
    "open_license_dialog",
    "check_for_updates_ui",
    "open_devil_global_config_dialog",
    "show_help",
}

_bound_count = 0
_skipped = []
for _name, _fn in _inspect.getmembers(DashboardApp, predicate=_inspect.isfunction):
    if _name.startswith("__"):
        continue
    if _name in _EXCLUDE_BIND or _name.startswith("build_"):
        continue
    if hasattr(DashboardAppOptimized, _name):
        # Giữ implementation optimized nếu đã có
        continue
    setattr(DashboardAppOptimized, _name, _fn)
    _bound_count += 1

# --- Compatibility shims cho method meg_gui còn phụ thuộc widget cũ ---

def _shim_jump_to_config_tab(self):
    self.switch_tab("profiles")


def _shim_jump_to_slot_logs(self, slot_idx: int = None):
    self.switch_tab("logs")
    if slot_idx:
        self.log_message(f"Nhật ký Slot #{slot_idx:02d}", "INFO")


def _shim_clear_logs(self):
    if hasattr(self, "logs_view") and self.logs_view:
        self.logs_view.clear()
    self.log_message("Nhật ký đã được làm sạch.", "INFO")


def _shim_clear_mirror_log(self):
    self.log_message("[Mirror] Nhật ký đã xóa.", "INFO")


def _shim_clear_moss_log(self):
    self.log_message("[Moss] Nhật ký đã xóa.", "INFO")


def _shim_start_all(self):
    self.toggle_all_auto(True)


def _shim_stop_all(self):
    self.toggle_all_auto(False)


def _shim_batch_start(self):
    self.toggle_all_auto(True)


def _shim_batch_stop(self):
    self.toggle_all_auto(False)


def _shim_load_profile_into_editor(self, profile_idx: int):
    if hasattr(self, "profiles_view") and self.profiles_view:
        self.profiles_view.load_profile_into_editor(profile_idx)
    self.switch_tab("profiles")


def _shim_update_moss_slot_rolls(self, slot_idx: int, rolls: int):
    try:
        if 1 <= slot_idx <= len(self.controllers):
            self.controllers[slot_idx - 1].moss_rolls_count = rolls
        moss = getattr(self, "moss_view", None)
        if moss:
            el = getattr(moss, "moss_ui_elements", {}).get(slot_idx)
            if el and el.get("rolls_lbl"):
                el["rolls_lbl"].configure(
                    text=f"🎰 {rolls}",
                    text_color=Colors.GREEN if rolls > 0 else Colors.TEXT_DIM
                )
    except Exception:
        pass


def _shim_update_moss_slot_ui_state(self, slot_idx: int, *args, **kwargs):
    moss = getattr(self, "moss_view", None)
    if moss:
        try:
            moss.refresh_moss_rows()
        except Exception:
            pass


def _shim_update_mirror_slot_ui_state(self, slot_idx: int, *args, **kwargs):
    mv = getattr(self, "mirror_view", None)
    if mv:
        try:
            mv.refresh_rows()
        except Exception:
            pass


def _shim_update_moss_selected_badge(self):
    moss = getattr(self, "moss_view", None)
    if moss and hasattr(moss, "_update_moss_badge"):
        moss._update_moss_badge()


def _shim_update_mirror_selected_badge(self):
    mv = getattr(self, "mirror_view", None)
    if mv and hasattr(mv, "_update_badge"):
        mv._update_badge()


def _shim_select_all_moss_slots(self):
    for c in self.controllers:
        c.moss_enabled = True
    moss = getattr(self, "moss_view", None)
    if moss:
        moss._set_all(True)


def _shim_deselect_all_moss_slots(self):
    for c in self.controllers:
        c.moss_enabled = False
    moss = getattr(self, "moss_view", None)
    if moss:
        moss._set_all(False)


def _shim_select_all_mirror_slots(self):
    for c in self.controllers:
        c.mirror_enabled = True
    mv = getattr(self, "mirror_view", None)
    if mv:
        mv._set_all(True)


def _shim_deselect_all_mirror_slots(self):
    for c in self.controllers:
        c.mirror_enabled = False
    mv = getattr(self, "mirror_view", None)
    if mv:
        mv._set_all(False)


def _shim_create_moss_slot_row(self, i: int):
    return


def _shim_create_mirror_slot_row(self, i: int):
    return


def _shim_get_moss_cat_name(self, cat_id: int) -> str:
    from ui.views.event_view import moss_cat_name
    return moss_cat_name(int(cat_id or 0))


def _shim_get_moss_cat_id(self, cat_name: str) -> int:
    from ui.views.event_view import moss_cat_id
    return moss_cat_id(cat_name)


def _shim_apply_batch_moss_settings(self):
    """Fallback nếu UI cũ gọi — dùng MossView batch."""
    moss = getattr(self, "moss_view", None)
    if moss:
        moss._handle_apply_batch()


def _shim_on_toggle_global_moss_clean(self):
    val = bool(self.batch_moss_clean_cb.get()) if hasattr(self, "batch_moss_clean_cb") else True
    for i, ctrl in enumerate(self.controllers, 1):
        ctrl.moss_auto_clean = val
        try:
            ConfigPersistenceManager.save_moss_config(
                i, ctrl.moss_category, ctrl.moss_delay_ms, ctrl.moss_max_rolls, val,
                getattr(ctrl, "moss_clean_equipment_trash", True)
            )
        except Exception:
            pass
    self.append_moss_log(f"🧹 Đã {'BẬT' if val else 'TẮT'} Tự Động Dọn Rác cho tất cả Slot!")


def _shim_on_toggle_clean_equipment_trash(self):
    val = bool(self.cb_clean_equipment_trash.get()) if hasattr(self, "cb_clean_equipment_trash") else True
    for i, ctrl in enumerate(self.controllers, 1):
        ctrl.moss_clean_equipment_trash = val
        try:
            ConfigPersistenceManager.save_moss_config(
                i, ctrl.moss_category, ctrl.moss_delay_ms, ctrl.moss_max_rolls,
                ctrl.moss_auto_clean, val
            )
        except Exception:
            pass
    self.append_moss_log(
        "👕 Đã BẬT vứt quần áo/vũ khí rác." if val else "ℹ️ Đã TẮT vứt quần áo/vũ khí rác."
    )


def _shim_render_logs(self, *args, **kwargs):
    return


def _shim_apply_license_lock_state(self, *args, **kwargs):
    self._update_header_stats_internal()


def _shim_update_modules_visibility(self, *args, **kwargs):
    return


def _shim_change_language(self, *args, **kwargs):
    self.log_message("Đổi ngôn ngữ: dùng meg_gui gốc nếu cần đầy đủ i18n.", "INFO")


def _shim_open_logs_window(self):
    self.switch_tab("logs")


_SHIMS = {
    "jump_to_config_tab": _shim_jump_to_config_tab,
    "jump_to_slot_logs": _shim_jump_to_slot_logs,
    "clear_logs": _shim_clear_logs,
    "clear_mirror_log": _shim_clear_mirror_log,
    "clear_moss_log": _shim_clear_moss_log,
    "start_all": _shim_start_all,
    "stop_all": _shim_stop_all,
    "batch_start": _shim_batch_start,
    "batch_stop": _shim_batch_stop,
    "load_profile_into_editor": _shim_load_profile_into_editor,
    "update_moss_slot_rolls": _shim_update_moss_slot_rolls,
    "update_moss_slot_ui_state": _shim_update_moss_slot_ui_state,
    "update_mirror_slot_ui_state": _shim_update_mirror_slot_ui_state,
    "update_moss_selected_badge": _shim_update_moss_selected_badge,
    "update_mirror_selected_badge": _shim_update_mirror_selected_badge,
    "select_all_moss_slots": _shim_select_all_moss_slots,
    "deselect_all_moss_slots": _shim_deselect_all_moss_slots,
    "select_all_mirror_slots": _shim_select_all_mirror_slots,
    "deselect_all_mirror_slots": _shim_deselect_all_mirror_slots,
    "create_moss_slot_row": _shim_create_moss_slot_row,
    "create_mirror_slot_row": _shim_create_mirror_slot_row,
    "get_moss_cat_name": _shim_get_moss_cat_name,
    "get_moss_cat_id": _shim_get_moss_cat_id,
    "apply_batch_moss_settings": _shim_apply_batch_moss_settings,
    "on_toggle_global_moss_clean": _shim_on_toggle_global_moss_clean,
    "on_toggle_clean_equipment_trash": _shim_on_toggle_clean_equipment_trash,
    "render_logs": _shim_render_logs,
    "apply_license_lock_state": _shim_apply_license_lock_state,
    "update_modules_visibility": _shim_update_modules_visibility,
    "change_language": _shim_change_language,
    "apply_language": _shim_change_language,
    "open_logs_window": _shim_open_logs_window,
}

for _n, _f in _SHIMS.items():
    # Shim luôn thắng nếu method gốc phụ thuộc widget monolith
    setattr(DashboardAppOptimized, _n, _f)

print(f"[meg_gui_optimized] Bound {_bound_count} DashboardApp methods + {len(_SHIMS)} shims.")


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("megamu.auto.dashboard.v2")
        except Exception:
            pass
    app = None
    try:
        app = DashboardAppOptimized()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except (KeyboardInterrupt, SystemExit):
        print("\n[INFO] Đã nhận tín hiệu dừng (Ctrl+C). Đang đóng ứng dụng an toàn...")
        if app is not None:
            try:
                app.on_closing()
            except Exception:
                try:
                    app.destroy()
                except Exception:
                    pass
    except Exception as e:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

