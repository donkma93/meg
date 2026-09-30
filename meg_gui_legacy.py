#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Navigator - Streamlined Multi-Account Edition
=========================================================
Giao diện All-in-One tối ưu hóa cao độ cho người chơi nhiều tài khoản:
- Toàn bộ tính năng gói gọn trên 1 màn hình thống nhất, KHÔNG CẦN CHUYỂN TAB RƯỜM RÀ
- Cột Trái: Danh sách thẻ tài khoản hiển thị đầy đủ RAM (Level, Map, X, Y, Auto, Tiến độ, Nút điều khiển riêng)
- Cột Phải: Lộ trình mốc level (Dropdown chọn mốc mượt mà, F8 lấy RAM, Waypoints) + Nhật ký Log trực tiếp
- Điều hướng đa luồng song song độc lập, tự động khớp Level từng nhân vật
- Thao tác 1-Click: Bắt đầu tất cả, Dừng tất cả, Auto tất cả, Xếp cửa sổ lưới (Auto Tile)
"""

import sys
import os
import ctypes
from ctypes import wintypes
import time
import math
import json
import threading
import subprocess
from typing import Optional, List, Dict, Tuple, Any
import customtkinter as ctk
from tkinter import messagebox, filedialog

try:
    import winsound
except ImportError:
    winsound = None

# Đảm bảo UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Gắn thread vào interactive desktop Default
if sys.platform == "win32":
    try:
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if not h_desk:
            h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

import meg_navigator
from meg_navigator import (
    ProcessMemoryReader,
    WindowHelper,
    BackgroundInputSimulator,
    MegNavigator,
    ClientLiveState,
    normalize_map_name,
    get_direction_description,
    scan_all_clients,
    load_maps_config,
    save_all_maps,
    save_maps_to_ini,
    save_maps_to_txt,
    load_maps_from_ini,
    load_maps_from_txt,
    get_active_maps_file,
    MAPS_INI_PATH,
    MAPS_TXT_PATH,
    toggle_auto_attack_via_sendmessage,
    ramer_douglas_peucker
)

try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None

try:
    from meg_auto_worker import AutoTrainWorker, MapResolver
except ImportError:
    AutoTrainWorker = None
    MapResolver = None

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MegNavigatorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MEGAMU Auto Navigator - Bảng Điều Khiển Đa Tài Khoản")
        self.geometry("1240x800")
        self.minsize(1100, 680)

        # Trạng thái Đa Tài Khoản
        self.clients: List[ClientLiveState] = []
        self.selected_client: Optional[ClientLiveState] = None
        self.client_selected_vars: Dict[int, ctk.BooleanVar] = {}

        # Quản lý luồng độc lập từng tài khoản (PID -> Thread, Event, Data)
        self.client_nav_threads: Dict[int, threading.Thread] = {}
        self.client_stop_events: Dict[int, threading.Event] = {}
        self.auto_workers: Dict[int, Any] = {}
        self.client_runtime_data: Dict[int, Dict[str, Any]] = {}
        self.client_card_widgets: Dict[int, Dict[str, Any]] = {}

        # Quản lý Lộ Trình Mốc Level
        self.level_stages: List[Dict[str, Any]] = self._get_default_level_stages()
        self.active_stage_idx: int = 0

        # Tự động nạp cấu hình từ auto_config.json nếu có
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                if "stages" in cfg_data and isinstance(cfg_data["stages"], list) and len(cfg_data["stages"]) > 0:
                    self.level_stages = cfg_data["stages"]
                if "current_stage_idx" in cfg_data:
                    self.active_stage_idx = max(0, min(int(cfg_data["current_stage_idx"]), len(self.level_stages) - 1))
            except Exception:
                pass

        # Quản lý Ghi Vết RAM Tự Động & Nén Đường RDP
        self.is_recording_trace: bool = False
        self.recording_stage_idx: Optional[int] = None
        self.last_recorded_pos: Optional[Tuple[int, int]] = None
        self.trace_raw_points: List[Tuple[int, int]] = []

        # Quản lý Phím Nóng F8 Toàn Màn Hình
        self.hotkey_stop_event = threading.Event()
        self.hotkey_enabled = True
        self.last_f8_time = 0.0

        # Xây dựng giao diện All-in-One tinh gọn
        self._build_streamlined_ui()

        # Quét client lần đầu
        self.refresh_clients()

        # Bật luồng đọc RAM nền chu kỳ 1.2s
        self.after(1200, self._auto_update_all_clients_ram)

        # Lắng nghe phím F8
        self._start_f8_hotkey_listener()

        # Xử lý đóng app
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==========================================================================
    # BỐ CỤC ALL-IN-ONE TINH GỌN (SINGLE-DASHBOARD WORKSPACE)
    # ==========================================================================
    def _build_streamlined_ui(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # 1. TOP HEADER BAR: Tiêu đề + Thống kê + Xếp cửa sổ + Quét + Theme
        # ----------------------------------------------------------------------
        header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#13171f"), height=62)
        header_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        header_frame.grid_columnconfigure(1, weight=1)

        # Tiêu đề
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, padx=(16, 10), pady=8, sticky="w")

        title_lbl = ctk.CTkLabel(
            title_box,
            text="⚡ MEGAMU NAVIGATOR PRO",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#1e293b", "#38bdf8")
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Điều Hướng Đa Tài Khoản • Đa Luồng Độc Lập • RAM IL2CPP • Không Chiếm Chuột",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray60")
        )
        sub_lbl.pack(anchor="w")

        # Thống kê nhanh
        stats_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        stats_box.grid(row=0, column=1, padx=6, pady=8, sticky="w")

        self.badge_total = ctk.CTkLabel(
            stats_box, text="🎮 0 Client", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"), corner_radius=6, padx=8, pady=4
        )
        self.badge_total.pack(side="left", padx=3)

        self.badge_running = ctk.CTkLabel(
            stats_box, text="🚀 0 Đang Chạy", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"), text_color=("gray40", "gray65"), corner_radius=6, padx=8, pady=4
        )
        self.badge_running.pack(side="left", padx=3)

        self.badge_auto = ctk.CTkLabel(
            stats_box, text="⚔️ 0 Đang Auto", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"), text_color=("gray40", "gray65"), corner_radius=6, padx=8, pady=4
        )
        self.badge_auto.pack(side="left", padx=3)

        # Nút tiện ích Header
        right_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header.grid(row=0, column=2, padx=16, pady=8, sticky="e")

        btn_tile = ctk.CTkButton(
            right_header, text="🖥️ Xếp Lưới Cửa Sổ", width=115, height=28,
            fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._tile_all_game_windows
        )
        btn_tile.pack(side="left", padx=3)

        btn_refresh = ctk.CTkButton(
            right_header, text="🔄 Quét Client", width=90, height=28,
            fg_color="#334155", hover_color="#1e293b", font=ctk.CTkFont(size=11),
            command=self.refresh_clients
        )
        btn_refresh.pack(side="left", padx=3)

        self.theme_switch = ctk.CTkSwitch(right_header, text="Sáng/Tối", font=ctk.CTkFont(size=11), command=self._toggle_theme)
        self.theme_switch.select()
        self.theme_switch.pack(side="left", padx=(8, 0))

        # ----------------------------------------------------------------------
        # 2. MASTER TOOLBAR: Thanh Thao Tác Hàng Loạt
        # ----------------------------------------------------------------------
        bar = ctk.CTkFrame(self, fg_color=("gray90", "#181d26"), corner_radius=8, height=44)
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(8, 6))

        self.var_select_all = ctk.BooleanVar(value=True)
        chk_all = ctk.CTkCheckBox(
            bar, text="Chọn hết", font=ctk.CTkFont(size=12, weight="bold"),
            variable=self.var_select_all, command=self._toggle_select_all_clients
        )
        chk_all.pack(side="left", padx=(10, 8), pady=6)

        # Nút Bắt Đầu Tất Cả
        self.btn_master_start = ctk.CTkButton(
            bar, text="🚀 BẮT ĐẦU TẤT CẢ (ĐÃ CHỌN)", height=30,
            font=ctk.CTkFont(size=12, weight="bold"), fg_color="#10b981", hover_color="#059669",
            command=self._on_start_selected_clients
        )
        self.btn_master_start.pack(side="left", padx=3, pady=6)

        # Nút Dừng Tất Cả
        self.btn_master_stop = ctk.CTkButton(
            bar, text="⏹ DỪNG TẤT CẢ", height=30,
            font=ctk.CTkFont(size=12, weight="bold"), fg_color="#dc2626", hover_color="#b91c1c",
            command=self._on_stop_all_clients
        )
        self.btn_master_stop.pack(side="left", padx=3, pady=6)

        # Bật / Tắt Auto Tất Cả
        btn_auto_on = ctk.CTkButton(
            bar, text="⚔️ Bật Auto Tất Cả", height=30, width=115, font=ctk.CTkFont(size=11),
            fg_color="#2563eb", hover_color="#1d4ed8", command=lambda: self._batch_set_auto_attack(True)
        )
        btn_auto_on.pack(side="left", padx=3, pady=6)

        btn_auto_off = ctk.CTkButton(
            bar, text="⚔️ Tắt Auto Tất Cả", height=30, width=115, font=ctk.CTkFont(size=11),
            fg_color="#475569", hover_color="#334155", command=lambda: self._batch_set_auto_attack(False)
        )
        btn_auto_off.pack(side="left", padx=3, pady=6)

        # Phím nóng F8 & Góc Camera
        self.sw_hotkey_f8 = ctk.CTkSwitch(
            bar, text="F8 Lấy RAM", font=ctk.CTkFont(size=11), command=self._on_toggle_f8_hotkey
        )
        self.sw_hotkey_f8.select()
        self.sw_hotkey_f8.pack(side="left", padx=(10, 6), pady=6)

        ctk.CTkLabel(bar, text="📷", font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 1))
        self.slider_angle = ctk.CTkSlider(bar, from_=0, to=360, number_of_steps=72, width=65, height=13, command=self._on_angle_change)
        self.slider_angle.set(0)
        self.slider_angle.pack(side="left", padx=1)
        self.lbl_angle_val = ctk.CTkLabel(bar, text="0°", width=24, font=ctk.CTkFont(size=10, weight="bold"))
        self.lbl_angle_val.pack(side="left", padx=(0, 4))

        # Phải: Quản lý bản đồ & Lưu/Nạp JSON
        btn_maps = ctk.CTkButton(
            bar, text="🗺️ DS Map", width=75, height=28, fg_color="#334155", hover_color="#1e293b",
            font=ctk.CTkFont(size=11), command=self._open_map_manager_dialog
        )
        btn_maps.pack(side="right", padx=(2, 8), pady=6)

        btn_save = ctk.CTkButton(
            bar, text="💾 Lưu Kế Hoạch", width=95, height=28, fg_color="#334155", hover_color="#1e293b",
            font=ctk.CTkFont(size=11), command=self._save_level_plan_to_file
        )
        btn_save.pack(side="right", padx=2, pady=6)

        btn_load = ctk.CTkButton(
            bar, text="📂 Nạp Kế Hoạch", width=95, height=28, fg_color="#334155", hover_color="#1e293b",
            font=ctk.CTkFont(size=11), command=self._load_level_plan_from_file
        )
        btn_load.pack(side="right", padx=2, pady=6)

        # ----------------------------------------------------------------------
        # 3. WORKSPACE 2 CỘT CHÍNH (KHÔNG CẦN CHUYỂN TAB)
        # ----------------------------------------------------------------------
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=5, minsize=520)  # Cột trái: Đa tài khoản
        workspace.grid_columnconfigure(1, weight=5, minsize=520)  # Cột phải: Lộ trình & Log

        # ======================================================================
        # CỘT TRÁI: BẢNG TỔNG QUAN TẤT CẢ TÀI KHOẢN (ACCOUNTS LIST)
        # ======================================================================
        col_left = ctk.CTkFrame(workspace, fg_color=("gray95", "#161b22"), corner_radius=10)
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        col_left.grid_rowconfigure(1, weight=1)
        col_left.grid_columnconfigure(0, weight=1)

        # Header cột trái
        cl_head = ctk.CTkFrame(col_left, fg_color=("gray85", "#1c222d"), corner_radius=8, height=36)
        cl_head.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            cl_head, text="🎮 DANH SÁCH TÀI KHOẢN MEGAMU",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=10, pady=6)

        ctk.CTkLabel(
            cl_head, text="Tự động đọc RAM IL2CPP • Click để soi",
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray65")
        ).pack(side="right", padx=10, pady=6)

        # Scrollable chứa các thẻ tài khoản
        self.accounts_scroll = ctk.CTkScrollableFrame(col_left, corner_radius=8)
        self.accounts_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.accounts_scroll.grid_columnconfigure(0, weight=1)

        # ======================================================================
        # CỘT PHẢI: LỘ TRÌNH MỐC LEVEL & NHẬT KÝ HOẠT ĐỘNG
        # ======================================================================
        col_right = ctk.CTkFrame(workspace, fg_color="transparent")
        col_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
        col_right.grid_rowconfigure(0, weight=6)  # Nửa trên: Lộ trình mốc
        col_right.grid_rowconfigure(1, weight=4)  # Nửa dưới: Log trực tiếp
        col_right.grid_columnconfigure(0, weight=1)

        # --- KHUNG NỬA TRÊN: LỘ TRÌNH MỐC LEVEL & TỌA ĐỘ ---
        self.box_stage = ctk.CTkFrame(col_right, fg_color=("gray95", "#161b22"), corner_radius=10)
        self.box_stage.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 6))
        self.box_stage.grid_rowconfigure(2, weight=1)
        self.box_stage.grid_columnconfigure(0, weight=1)

        # Hàng 1: Dropdown chọn mốc + Thêm mốc + Xóa mốc
        stg_top = ctk.CTkFrame(self.box_stage, fg_color=("gray85", "#1c222d"), corner_radius=8, height=38)
        stg_top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            stg_top, text="🗺️ MỐC LỘ TRÌNH:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(10, 6), pady=6)

        self.cmb_stage_selector = ctk.CTkComboBox(
            stg_top, values=[], width=210, font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_stage_dropdown_selected
        )
        self.cmb_stage_selector.pack(side="left", padx=(0, 6), pady=6)

        btn_run_active = ctk.CTkButton(
            stg_top, text="▶️ Chạy Mốc Này", width=115, height=26,
            fg_color="#16a34a", hover_color="#15803d", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_run_active_stage
        )
        btn_run_active.pack(side="left", padx=(0, 6), pady=6)

        btn_add_stg = ctk.CTkButton(
            stg_top, text="➕ Thêm", width=65, height=26,
            fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._add_new_stage
        )
        btn_add_stg.pack(side="left", padx=(0, 4), pady=6)

        btn_del_stg = ctk.CTkButton(
            stg_top, text="🗑️", width=36, height=26,
            fg_color="#b91c1c", hover_color="#991b1b", font=ctk.CTkFont(size=11),
            command=self._delete_active_stage
        )
        btn_del_stg.pack(side="left", padx=(0, 6), pady=6)

        # Hàng 2: Form cấu hình mốc (Tên, Level từ-đến, Bản đồ, Checkboxes)
        self.stage_cfg_box = ctk.CTkFrame(self.box_stage, fg_color=("gray90", "#1a212c"), corner_radius=8)
        self.stage_cfg_box.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        # Dòng config 1
        cfg_r1 = ctk.CTkFrame(self.stage_cfg_box, fg_color="transparent")
        cfg_r1.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(cfg_r1, text="Tên:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 2))
        self.ent_stg_name = ctk.CTkEntry(cfg_r1, width=130, font=ctk.CTkFont(size=11))
        self.ent_stg_name.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(cfg_r1, text="Lv:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        self.ent_stg_min = ctk.CTkEntry(cfg_r1, width=42, font=ctk.CTkFont(size=11, weight="bold"))
        self.ent_stg_min.pack(side="left", padx=(0, 2))

        ctk.CTkLabel(cfg_r1, text="➔", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 2))
        self.ent_stg_max = ctk.CTkEntry(cfg_r1, width=46, font=ctk.CTkFont(size=11, weight="bold"))
        self.ent_stg_max.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(cfg_r1, text="Map:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 2))
        self.cmb_stg_map = ctk.CTkComboBox(cfg_r1, values=meg_navigator.POPULAR_MAPS, width=120, font=ctk.CTkFont(size=11))
        self.cmb_stg_map.pack(side="left", padx=(0, 4))

        btn_warp = ctk.CTkButton(
            cfg_r1, text="Move", width=48, height=24, fg_color="#d97706", hover_color="#b45309",
            font=ctk.CTkFont(size=10), command=self._on_quick_warp_active_map
        )
        btn_warp.pack(side="left")

        # Dòng config 2
        cfg_r2 = ctk.CTkFrame(self.stage_cfg_box, fg_color="transparent")
        cfg_r2.pack(fill="x", padx=8, pady=(2, 6))

        self.chk_auto_warp = ctk.CTkCheckBox(cfg_r2, text="Tự đổi map (/m)", font=ctk.CTkFont(size=11))
        self.chk_auto_warp.pack(side="left", padx=(0, 8))

        self.chk_auto_attack = ctk.CTkCheckBox(cfg_r2, text="⚔️ Tự bật Auto Đánh", font=ctk.CTkFont(size=11, weight="bold"))
        self.chk_auto_attack.pack(side="left", padx=(0, 8))

        self.chk_auto_roadmap = ctk.CTkCheckBox(cfg_r2, text="🔄 Tự chuyển chặng theo Level", font=ctk.CTkFont(size=11))
        self.chk_auto_roadmap.pack(side="left")

        # Gắn callback tự đồng bộ khi gõ
        self.ent_stg_name.bind("<KeyRelease>", self._on_active_stage_form_changed)
        self.ent_stg_min.bind("<KeyRelease>", self._on_active_stage_form_changed)
        self.ent_stg_max.bind("<KeyRelease>", self._on_active_stage_form_changed)
        self.cmb_stg_map.configure(command=lambda val: self._on_active_stage_form_changed())
        self.chk_auto_warp.configure(command=self._on_active_stage_form_changed)
        self.chk_auto_attack.configure(command=self._on_active_stage_form_changed)

        # Hàng 3: Thêm tọa độ (X, Y, F8, Ghi vết) + Danh sách Waypoints
        wp_ctrl = ctk.CTkFrame(self.box_stage, fg_color="transparent")
        wp_ctrl.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 6))
        wp_ctrl.grid_rowconfigure(1, weight=1)
        wp_ctrl.grid_columnconfigure(0, weight=1)

        # Thanh nhập tọa độ
        wp_bar = ctk.CTkFrame(wp_ctrl, fg_color=("gray90", "#181d26"), corner_radius=6, height=32)
        wp_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 4))

        ctk.CTkLabel(wp_bar, text="X:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(6, 2), pady=4)
        self.ent_wp_x = ctk.CTkEntry(wp_bar, width=38, font=ctk.CTkFont(size=11))
        self.ent_wp_x.pack(side="left", padx=(0, 4), pady=4)

        ctk.CTkLabel(wp_bar, text="Y:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(2, 2), pady=4)
        self.ent_wp_y = ctk.CTkEntry(wp_bar, width=38, font=ctk.CTkFont(size=11))
        self.ent_wp_y.pack(side="left", padx=(0, 6), pady=4)

        self.ent_wp_desc = ctk.CTkEntry(wp_bar, placeholder_text="Ghi chú (bãi quái, cổng...)", font=ctk.CTkFont(size=11))
        self.ent_wp_desc.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)

        btn_add_wp = ctk.CTkButton(
            wp_bar, text="➕ Thêm", width=55, height=24, fg_color="#10b981", hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"), command=self._on_add_coord_to_active_stage
        )
        btn_add_wp.pack(side="left", padx=(0, 3), pady=4)

        btn_f8 = ctk.CTkButton(
            wp_bar, text="📍 [F8] RAM", width=75, height=24, fg_color="#0284c7", hover_color="#0369a1",
            font=ctk.CTkFont(size=11), command=lambda: self._capture_ram_coord_to_stage(self.active_stage_idx)
        )
        btn_f8.pack(side="left", padx=(0, 3), pady=4)

        self.btn_trace = ctk.CTkButton(
            wp_bar, text="🔴 Ghi Vết", width=72, height=24, fg_color="#dc2626", hover_color="#b91c1c",
            font=ctk.CTkFont(size=11, weight="bold"), command=self._toggle_trace_recorder
        )
        self.btn_trace.pack(side="left", padx=(0, 3), pady=4)

        btn_clr_wp = ctk.CTkButton(
            wp_bar, text="🗑️", width=28, height=24, fg_color="#ef4444", hover_color="#dc2626",
            font=ctk.CTkFont(size=10), command=self._delete_all_coords_from_active_stage
        )
        btn_clr_wp.pack(side="left", padx=(0, 6), pady=4)

        # Scrollable chứa các tọa độ waypoints của mốc
        self.scroll_waypoints = ctk.CTkScrollableFrame(wp_ctrl, corner_radius=6)
        self.scroll_waypoints.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # Tóm tắt mốc dưới đáy
        self.lbl_stage_summary = ctk.CTkLabel(wp_ctrl, text="", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.lbl_stage_summary.grid(row=2, column=0, sticky="w", padx=4, pady=(2, 0))

        # --- KHUNG NỬA DƯỚI: NHẬT KÝ HOẠT ĐỘNG TRỰC TIẾP (LIVE LOGS) ---
        box_log = ctk.CTkFrame(col_right, fg_color=("gray95", "#161b22"), corner_radius=10)
        box_log.grid(row=1, column=0, sticky="nsew", padx=0, pady=(6, 0))
        box_log.grid_rowconfigure(1, weight=1)
        box_log.grid_columnconfigure(0, weight=1)

        # Header Log kèm bộ lọc
        log_head = ctk.CTkFrame(box_log, fg_color=("gray85", "#1c222d"), corner_radius=8, height=32)
        log_head.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 4))

        ctk.CTkLabel(
            log_head, text="📜 NHẬT KÝ HOẠT ĐỘNG", font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left", padx=(10, 6), pady=4)

        self.cmb_log_filter = ctk.CTkComboBox(
            log_head, values=["Tất Cả Tài Khoản"], width=170, font=ctk.CTkFont(size=10),
            command=self._on_log_filter_changed
        )
        self.cmb_log_filter.set("Tất Cả Tài Khoản")
        self.cmb_log_filter.pack(side="left", padx=(0, 6), pady=4)

        btn_clr_log = ctk.CTkButton(
            log_head, text="Xóa Log", width=65, height=22, fg_color="#475569", hover_color="#334155",
            font=ctk.CTkFont(size=10), command=self._clear_logs
        )
        btn_clr_log.pack(side="right", padx=(2, 6), pady=4)

        # Textbox hiển thị log
        self.txt_logs = ctk.CTkTextbox(
            box_log, font=ctk.CTkFont(family="Consolas", size=10), corner_radius=6, wrap="word"
        )
        self.txt_logs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.raw_logs_store: List[Tuple[Optional[int], str]] = []
        self.log_filter_pid: Optional[int] = None

        # Nạp dữ liệu mốc ban đầu vào form
        self._sync_dropdown_and_form_from_stage(0)

    # ==========================================================================
    # QUẢN LÝ DANH SÁCH THẺ ĐA TÀI KHOẢN (ACCOUNTS LIST)
    # ==========================================================================
    def refresh_clients(self):
        """Quét và làm mới toàn bộ thẻ client game MEGAMU"""
        self.clients = scan_all_clients()

        for w in self.accounts_scroll.winfo_children():
            w.destroy()
        self.client_card_widgets.clear()

        for pid in list(self.client_selected_vars.keys()):
            if not any(c.pid == pid for c in self.clients):
                del self.client_selected_vars[pid]

        if not self.clients:
            lbl_none = ctk.CTkLabel(
                self.accounts_scroll,
                text="❌ Không tìm thấy client MEGAMU nào đang mở!\nVui lòng khởi động game và đăng nhập nhân vật rồi bấm 'Quét Client'.",
                text_color=("red", "#f87171"),
                font=ctk.CTkFont(size=12)
            )
            lbl_none.pack(padx=10, pady=40)
            self._update_header_stats()
            return

        for idx, client in enumerate(self.clients):
            if client.pid not in self.client_selected_vars:
                self.client_selected_vars[client.pid] = ctk.BooleanVar(value=True)
            self._create_account_card(client, idx)

        # Mặc định chọn client đầu tiên
        if not self.selected_client or not any(c.pid == self.selected_client.pid for c in self.clients):
            self._select_client_card(self.clients[0])
        else:
            for c in self.clients:
                if c.pid == self.selected_client.pid:
                    self._select_client_card(c)
                    break

        self._update_header_stats()
        self._update_log_filter_options()

    def _create_account_card(self, client: ClientLiveState, idx: int):
        is_running = client.pid in self.client_nav_threads and self.client_nav_threads[client.pid].is_alive()
        is_selected = bool(self.selected_client and self.selected_client.pid == client.pid)

        border_color = "#38bdf8" if is_selected else ("#10b981" if is_running else ("gray80", "#2a3241"))

        card = ctk.CTkFrame(
            self.accounts_scroll,
            corner_radius=8,
            fg_color=("white", "#1e2430" if not is_selected else "#1a2a3e"),
            border_width=2 if (is_selected or is_running) else 1,
            border_color=border_color
        )
        card.pack(fill="x", padx=2, pady=3)
        card.grid_columnconfigure(2, weight=1)

        # Checkbox chọn hàng loạt
        chk_var = self.client_selected_vars[client.pid]
        chk = ctk.CTkCheckBox(card, text="", width=20, variable=chk_var)
        chk.grid(row=0, column=0, rowspan=2, padx=(8, 2), pady=6)

        # Số thứ tự
        lbl_num = ctk.CTkLabel(card, text=f"#{idx+1}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=24)
        lbl_num.grid(row=0, column=1, rowspan=2, padx=(0, 4), pady=6)

        # Dòng 1: Tên nhân vật, Level/RR, Server
        lvl_str = f"Lv {client.level}" if client.level is not None else "Lv —"
        if client.resets is not None:
            lvl_str += f"/{client.resets}rr"
        server_str = f"[{client.server}]" if client.server else ""

        lbl_char = ctk.CTkLabel(
            card, text=f"⚔️ {client.char_name} ({lvl_str}) {server_str}",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        )
        lbl_char.grid(row=0, column=2, sticky="w", padx=0, pady=(5, 1))

        # Dòng 2: Map, Tọa độ, PID, Auto status
        coord_str = f"({client.x}, {client.y})" if client.x is not None else "(—, —)"
        auto_text = f"⚔️ Auto: BẬT ({client.helper_active_time}s)" if client.is_auto_attack else "⚔️ Auto: Tắt"
        lbl_sub = ctk.CTkLabel(
            card, text=f"🗺️ {client.map_name} | 📍 {coord_str} | PID: {client.pid} | {auto_text}",
            font=ctk.CTkFont(size=10), text_color=("gray45", "gray65"), anchor="w"
        )
        lbl_sub.grid(row=1, column=2, sticky="w", padx=0, pady=(0, 2))

        # Dòng 3: Trạng thái lộ trình & Thanh tiến trình Mini
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.grid(row=2, column=2, sticky="ew", padx=0, pady=(0, 5))
        row3.grid_columnconfigure(1, weight=1)

        lbl_nav = ctk.CTkLabel(
            row3, text="⚪ Sẵn Sàng" if not is_running else "🔵 Đang Chạy...",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b") if not is_running else ("#bfdbfe", "#1e3a8a"),
            corner_radius=4, padx=5, pady=1
        )
        lbl_nav.grid(row=0, column=0, padx=(0, 6), sticky="w")

        prog = ctk.CTkProgressBar(row3, height=6)
        prog.set(0.0)
        prog.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        lbl_pct = ctk.CTkLabel(row3, text="0%", font=ctk.CTkFont(size=10), text_color="#94a3b8", width=28)
        lbl_pct.grid(row=0, column=2, sticky="e")

        # Cột nút điều khiển nhanh bên phải thẻ
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.grid(row=0, column=3, rowspan=3, padx=(4, 8), pady=4, sticky="e")

        btn_run = ctk.CTkButton(
            btn_box, text="⏹ Dừng" if is_running else "▶️ Chạy", width=58, height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#dc2626" if is_running else "#10b981", hover_color="#b91c1c" if is_running else "#059669",
            command=lambda c=client: self._on_toggle_single_client_run(c)
        )
        btn_run.pack(side="left", padx=1)

        btn_auto = ctk.CTkButton(
            btn_box, text="⚔️ Auto", width=52, height=24, font=ctk.CTkFont(size=10),
            fg_color="#2563eb", hover_color="#1d4ed8", command=lambda c=client: self._toggle_client_auto_attack(c)
        )
        btn_auto.pack(side="left", padx=1)

        btn_view = ctk.CTkButton(
            btn_box, text="🖥️", width=32, height=24, font=ctk.CTkFont(size=10),
            fg_color="#334155", hover_color="#1e293b", command=lambda c=client: self._bring_window_to_front(c.hwnd)
        )
        btn_view.pack(side="left", padx=1)

        self.client_card_widgets[client.pid] = {
            "card_frame": card,
            "lbl_char": lbl_char,
            "lbl_sub": lbl_sub,
            "lbl_nav": lbl_nav,
            "prog": prog,
            "lbl_pct": lbl_pct,
            "btn_run": btn_run,
            "btn_auto": btn_auto
        }

        # Bấm vào thẻ để chọn
        for w in (card, lbl_char, lbl_sub, lbl_num):
            w.bind("<Button-1>", lambda e, c=client: self._select_client_card(c))

    def _select_client_card(self, client: ClientLiveState):
        self.selected_client = client
        for pid, widgets in self.client_card_widgets.items():
            card = widgets["card_frame"]
            is_running = pid in self.client_nav_threads and self.client_nav_threads[pid].is_alive()
            if pid == client.pid:
                card.configure(fg_color=("white", "#1a2a3e"), border_width=2, border_color="#38bdf8")
            else:
                card.configure(
                    fg_color=("white", "#1e2430"),
                    border_width=2 if is_running else 1,
                    border_color="#10b981" if is_running else ("gray80", "#2a3241")
                )

    def _update_header_stats(self):
        total = len(self.clients)
        running = sum(1 for pid, t in self.client_nav_threads.items() if t.is_alive())
        auto_cnt = sum(1 for c in self.clients if c.is_auto_attack)

        self.badge_total.configure(text=f"🎮 {total} Client")

        if running > 0:
            self.badge_running.configure(
                text=f"🚀 {running} Đang Chạy", fg_color=("#bfdbfe", "#1e3a8a"), text_color=("#1e40af", "#60a5fa")
            )
        else:
            self.badge_running.configure(
                text="🚀 0 Đang Chạy", fg_color=("#e2e8f0", "#1e293b"), text_color=("gray40", "gray65")
            )

        if auto_cnt > 0:
            self.badge_auto.configure(
                text=f"⚔️ {auto_cnt} Đang Auto", fg_color=("#bbf7d0", "#14532d"), text_color=("#166534", "#4ade80")
            )
        else:
            self.badge_auto.configure(
                text="⚔️ 0 Đang Auto", fg_color=("#e2e8f0", "#1e293b"), text_color=("gray40", "gray65")
            )

    # ==========================================================================
    # ĐỌC RAM NỀN LIÊN TỤC CHO TẤT CẢ TÀI KHOẢN (1.2S)
    # ==========================================================================
    def _auto_update_all_clients_ram(self):
        try:
            for client in self.clients:
                pid = client.pid
                info = None
                if MegDirectEngine and MegDirectEngine.has_engine(pid):
                    eng = MegDirectEngine.get_engine(pid)
                    if eng.is_ready:
                        info = eng.get_player_info(max_age=1.5)

                if info:
                    m_id = info.get("mapId", -1)
                    if m_id is not None and m_id >= 0:
                        client.map_id = m_id
                        if MapResolver:
                            client.map_name = MapResolver.get_instance().get_map_name(m_id)
                    client.x = info.get("tileX", client.x)
                    client.y = info.get("tileY", client.y)
                    lvl = info.get("level")
                    if lvl is not None and lvl > 0:
                        client.level = lvl
                    client.is_auto_attack = (info.get("helperState", 0) == 1)
                    if info.get("name"):
                        client.char_name = info.get("name")
                else:
                    state = ProcessMemoryReader.read_live_state(pid)
                    if state:
                        map_id, map_name, cur_x, cur_y, _, _ = state
                        client.map_id = map_id
                        client.map_name = map_name
                        client.x = cur_x
                        client.y = cur_y

                    cur_lvl = ProcessMemoryReader.read_character_level(pid)
                    if cur_lvl is not None:
                        client.level = cur_lvl

                    h_state = ProcessMemoryReader.read_helper_state(pid)
                    if h_state:
                        is_active, _, active_time, _ = h_state
                        client.is_auto_attack = is_active
                        client.helper_active_time = active_time

                if pid in self.client_card_widgets:
                    w = self.client_card_widgets[pid]
                    lvl_str = f"Lv {client.level}" if client.level is not None else "Lv —"
                    if client.resets is not None:
                        lvl_str += f"/{client.resets}rr"
                    server_str = f"[{client.server}]" if client.server else ""
                    w["lbl_char"].configure(text=f"⚔️ {client.char_name} ({lvl_str}) {server_str}")

                    coord_str = f"({client.x}, {client.y})" if client.x is not None else "(—, —)"
                    auto_text = f"⚔️ Auto: BẬT ({client.helper_active_time}s)" if client.is_auto_attack else "⚔️ Auto: Tắt"
                    w["lbl_sub"].configure(text=f"🗺️ {client.map_name} | 📍 {coord_str} | PID: {client.pid} | {auto_text}")

            # Xử lý Ghi Vết Tự Động (Thu thập các bước chân thực tế)
            if self.is_recording_trace and self.recording_stage_idx is not None and self.selected_client:
                s_idx = self.recording_stage_idx
                if 0 <= s_idx < len(self.level_stages):
                    cx = self.selected_client.x
                    cy = self.selected_client.y
                    if cx is not None and cy is not None:
                        if not self.trace_raw_points or (cx, cy) != self.trace_raw_points[-1]:
                            self.trace_raw_points.append((cx, cy))
                            self.btn_trace.configure(text=f"⏹ Dừng ({len(self.trace_raw_points)})")

            self._update_header_stats()
        except Exception:
            pass

        interval = 400 if self.is_recording_trace else 1200
        self.after(interval, self._auto_update_all_clients_ram)

    # ==========================================================================
    # ĐIỀU HƯỚNG ĐA LUỒNG ĐỘC LẬP TỪNG TÀI KHOẢN
    # ==========================================================================
    def _toggle_select_all_clients(self):
        val = self.var_select_all.get()
        for v in self.client_selected_vars.values():
            v.set(val)

    def _on_run_active_stage(self):
        """Kích hoạt chạy ngay chính xác mốc đang được chọn trên giao diện"""
        if not self.clients:
            messagebox.showwarning("Chưa có Client", "Không tìm thấy client game nào đang chạy!")
            return

        target_client = self.selected_client
        if not target_client:
            target_client = self.clients[0]
            self._select_client_card(target_client)

        stg = self.level_stages[self.active_stage_idx]
        stg_name = stg.get("name", f"Chặng {self.active_stage_idx+1}")
        self.log(f"[{target_client.char_name}] 🚀 KÍCH HOẠT CHẠY RIÊNG MỐC: '{stg_name}' (Mốc #{self.active_stage_idx+1})", pid=target_client.pid)
        self._start_client_thread(target_client, forced_stage_idx=self.active_stage_idx)

    def _on_start_selected_clients(self):
        """Khởi chạy điều hướng song song cho tất cả tài khoản được tích chọn"""
        selected_pids = [pid for pid, var in self.client_selected_vars.items() if var.get()]
        if not selected_pids:
            messagebox.showwarning("Chưa chọn tài khoản", "Vui lòng tích chọn ít nhất 1 tài khoản!")
            return

        cnt = 0
        forced = None if self.chk_auto_roadmap.get() else self.active_stage_idx
        for client in self.clients:
            if client.pid in selected_pids:
                if client.pid not in self.client_nav_threads or not self.client_nav_threads[client.pid].is_alive():
                    self._start_client_thread(client, forced_stage_idx=forced)
                    cnt += 1

        self.log(f"[🚀 BẮT ĐẦU ĐỒNG LOẠT] Đã kích hoạt điều hướng cho {cnt} tài khoản!")
        self._update_header_stats()

    def _on_stop_all_clients(self):
        """Dừng tất cả các tài khoản đang chạy"""
        cnt = 0
        for pid, wkr in list(self.auto_workers.items()):
            try:
                wkr.stop()
            except Exception:
                pass
        for pid, ev in list(self.client_stop_events.items()):
            ev.set()
            cnt += 1
        self.log(f"[⏹ DỪNG TẤT CẢ] Đã phát tín hiệu dừng khẩn cấp cho {cnt} tài khoản!")
        self.after(400, self._update_header_stats)

    def _on_worker_stopped(self, pid: int):
        """Callback khi một AutoTrainWorker hoặc thread di chuyển dừng hẳn"""
        if pid in self.auto_workers:
            del self.auto_workers[pid]
        if pid in self.client_card_widgets:
            w = self.client_card_widgets[pid]
            w["btn_run"].configure(text="▶ Bắt đầu", fg_color=("#3b82f6", "#2563eb"), hover_color=("#2563eb", "#1d4ed8"))
            w["lbl_nav"].configure(text="⚪ Sẵn sàng", fg_color=("#e2e8f0", "#334155"))
        self._update_header_stats()

    def _on_toggle_single_client_run(self, client: ClientLiveState):
        is_worker_running = (client.pid in self.auto_workers and self.auto_workers[client.pid].running)
        is_thread_running = (client.pid in self.client_nav_threads and self.client_nav_threads[client.pid].is_alive())
        is_running = is_worker_running or is_thread_running
        if is_running:
            if client.pid in self.auto_workers:
                self.auto_workers[client.pid].stop()
            if client.pid in self.client_stop_events:
                self.client_stop_events[client.pid].set()
            self._update_client_card_nav_status(client.pid, "🟠 Đang Dừng...", 0)
        else:
            forced = None if self.chk_auto_roadmap.get() else self.active_stage_idx
            self._start_client_thread(client, forced_stage_idx=forced)

    def _start_client_thread(self, client: ClientLiveState, forced_stage_idx: Optional[int] = None):
        pid = client.pid
        char_name = client.char_name
        stop_event = threading.Event()
        self.client_stop_events[pid] = stop_event

        if pid in self.client_card_widgets:
            w = self.client_card_widgets[pid]
            w["btn_run"].configure(text="⏹ Dừng", fg_color="#dc2626", hover_color="#b91c1c")
            w["lbl_nav"].configure(text="🔵 Đang Chạy...", fg_color=("#bfdbfe", "#1e3a8a"))

        # =====================================================================
        # 1. ƯU TIÊN SỬ DỤNG AUTOTRAINWORKER (ZERO-MOUSE NATIVE ENGINE)
        # Khớp 100% cơ chế tự tìm đường MoveTo và chuyển map của Dashboard gốc
        # =====================================================================
        if AutoTrainWorker:
            def log_cb(msg: str, level: str = "INFO"):
                self.log(f"[{char_name}] {msg}", pid=pid)

            def prog_cb(state_str: str, val: int = 0):
                self._update_client_card_nav_status(pid, f"🔵 {state_str}", val)

            worker_stages = list(self.level_stages)
            if forced_stage_idx is not None:
                s_idx = max(0, min(forced_stage_idx, len(self.level_stages) - 1))
                worker_stages = [self.level_stages[s_idx]]
            elif not self.chk_auto_roadmap.get():
                s_idx = max(0, min(self.active_stage_idx, len(self.level_stages) - 1))
                worker_stages = [self.level_stages[s_idx]]

            worker_inst = AutoTrainWorker(
                pid=pid,
                stages=worker_stages,
                log_callback=log_cb,
                progress_callback=prog_cb,
                config={"arrival_distance": 2.0, "stuck_retry_delay": 3.5}
            )
            self.auto_workers[pid] = worker_inst

            def run_worker_thread():
                try:
                    worker_inst.start()
                    while worker_inst.running and not stop_event.is_set():
                        time.sleep(0.3)
                finally:
                    worker_inst.stop()
                    self.after(0, lambda: self._on_worker_stopped(pid))

            th = threading.Thread(target=run_worker_thread, daemon=True, name=f"AutoTrainWorkerThread-{pid}")
            self.client_nav_threads[pid] = th
            th.start()
            return

        # =====================================================================
        # 2. FALLBACK NẾU CHƯA CÀI FRIDA (CLICK CHUỘT NGẦM CŨ)
        # =====================================================================
        angle = self.slider_angle.get()

        def worker():
            try:
                cur_lvl = ProcessMemoryReader.read_character_level(pid)
                if cur_lvl is None:
                    cur_lvl = client.level or 1
                else:
                    client.level = cur_lvl

                self.log(f"[{char_name}] ==================================================", pid=pid)
                self.log(f"[{char_name}] 🚀 BẮT ĐẦU ĐIỀU HƯỚNG | Cấp độ nhân vật: {cur_lvl}", pid=pid)
                self.log(f"[{char_name}] ==================================================", pid=pid)

                # 1. Xác định mốc khởi đầu chính xác
                if forced_stage_idx is not None:
                    start_idx = max(0, min(forced_stage_idx, len(self.level_stages) - 1))
                    stg_name = self.level_stages[start_idx].get("name", f"Chặng {start_idx+1}")
                    self.log(f"[{char_name}] 🎯 CHẾ ĐỘ CHẠY MỐC CỤ THỂ: Chạy ngay mốc #{start_idx+1} '{stg_name}'!", pid=pid)
                elif not self.chk_auto_roadmap.get():
                    start_idx = max(0, min(self.active_stage_idx, len(self.level_stages) - 1))
                    stg_name = self.level_stages[start_idx].get("name", f"Chặng {start_idx+1}")
                    self.log(f"[{char_name}] 🎯 CHẾ ĐỘ CHẠY MỐC ĐANG CHỌN: Chạy mốc #{start_idx+1} '{stg_name}'!", pid=pid)
                else:
                    start_idx = None
                    for i, stg in enumerate(self.level_stages):
                        if stg.get("min_level", 1) <= cur_lvl <= stg.get("max_level", 400):
                            start_idx = i
                            break
                    if start_idx is None:
                        for i, stg in enumerate(self.level_stages):
                            if cur_lvl <= stg.get("max_level", 400):
                                start_idx = i
                                break
                    if start_idx is None:
                        start_idx = len(self.level_stages) - 1
                    self.log(f"[{char_name}] 🔄 CHẾ ĐỘ LỘ TRÌNH LEVEL: Khớp mốc #{start_idx+1} cho Level {cur_lvl}!", pid=pid)

                curr_idx = start_idx
                while curr_idx < len(self.level_stages) and not stop_event.is_set():
                    stg = self.level_stages[curr_idx]
                    stg_name = stg.get("name", f"Chặng {curr_idx+1}")
                    stg_map = stg.get("map", "")
                    min_l = stg.get("min_level", 1)
                    max_l = stg.get("max_level", 400)
                    wps = stg.get("waypoints", [])
                    auto_att = stg.get("auto_attack", True)
                    auto_warp = stg.get("auto_warp", True)

                    self._update_client_card_nav_status(pid, f"🔵 Mốc {curr_idx+1}: {stg_name}", 0)
                    self.log(f"[{char_name}] ▶️ [CHẠY MỐC {curr_idx+1}] {stg_name} | {stg_map} ({min_l}->{max_l})", pid=pid)

                    nav = MegNavigator(pid, camera_angle_deg=angle)

                    # 1. Đổi Map nếu cần
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if stg_map and normalize_map_name(stg_map) != normalize_map_name(cur_m):
                        if auto_warp:
                            self.log(f"[{char_name}] [➔] Đổi sang bản đồ '{stg_map}'...", pid=pid)
                            self._update_client_card_nav_status(pid, f"🟡 Đổi Map {stg_map}...", 10)
                            warp_ok = nav.warp_to_map(
                                stg_map, log_callback=lambda msg, p=pid: self.log(f"[{char_name}] {msg}", pid=p), stop_event=stop_event
                            )
                            if not warp_ok:
                                self.log(f"[{char_name}] [⚠️ CẢNH BÁO] Không thể tự chuyển sang map '{stg_map}' (Có thể thiếu Zen hoặc sai tên).", pid=pid)
                        else:
                            self.log(f"[{char_name}] [ℹ️] Đang ở '{cur_m}' (Map mốc là '{stg_map}'), Tự Đổi Map đang TẮT -> Sẽ chạy tọa độ trên map hiện tại '{cur_m}'.", pid=pid)

                    if stop_event.is_set():
                        break

                    # 2. Di chuyển lần lượt qua các tọa độ
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if auto_warp and stg_map and normalize_map_name(stg_map) != normalize_map_name(cur_m):
                        self.log(f"[{char_name}] [⚠️] Nhân vật đang ở '{cur_m}' (Chưa vào '{stg_map}'). Vui lòng di chuyển nhân vật vào map '{stg_map}' hoặc tắt 'Tự đổi map'!", pid=pid)
                    elif wps:
                        wp_coords = [(w["x"], w["y"]) for w in wps]
                        self.log(f"[{char_name}] [🚶] Bắt đầu di chuyển qua {len(wp_coords)} mốc tọa độ của '{stg_name}'...", pid=pid)

                        def prog_cb(overall_prog: float, rem_dist: int, cur_coord: tuple, cur_pt_idx=1, total_pts=1, p=pid):
                            pct = int(overall_prog * 100)
                            st_txt = f"🔵 Mốc {curr_idx+1} ({cur_pt_idx}/{total_pts})"
                            self._update_client_card_nav_status(p, st_txt, pct)

                        nav.navigate_multi_points(
                            waypoints=wp_coords, arrival_radius=1, intermediate_radius=2.5,
                            auto_attack_on_arrival=auto_att,
                            log_callback=lambda msg, p=pid: self.log(f"[{char_name}] {msg}", pid=p),
                            stop_event=stop_event, progress_callback=prog_cb,
                            stride_interval=0.75, use_micro_sync=False
                        )
                    else:
                        self.log(f"[{char_name}] [ℹ️] Mốc '{stg_name}' không có mốc tọa độ nào (chỉ farm tại chỗ).", pid=pid)
                        if auto_att:
                            h_st = ProcessMemoryReader.read_helper_state(pid)
                            if not h_st or h_st[0] == 0:
                                nav.enable_auto_attack(log_callback=lambda msg, p=pid: self.log(f"[{char_name}] {msg}", pid=p))

                    if stop_event.is_set():
                        break

                    # 3. Farm & Giám sát Level
                    # Nếu chạy mốc cụ thể hoặc KHÔNG bật Tự chuyển chặng theo Level -> Cố định ở mốc này!
                    if forced_stage_idx is not None or not self.chk_auto_roadmap.get():
                        self.log(f"[{char_name}] [⚔️ CẮM BÃI CỐ ĐỊNH] Đang farm tại {stg_name} (Chế độ chạy riêng mốc này).", pid=pid)
                        self._update_client_card_nav_status(pid, f"⚔️ Farm {stg_name}", 100)
                        while not stop_event.is_set():
                            time.sleep(3.0)
                            if auto_att:
                                h_st = ProcessMemoryReader.read_helper_state(pid)
                                if h_st and h_st[0] == 0:
                                    nav.enable_auto_attack(log_callback=lambda msg, p=pid: self.log(f"[{char_name}] {msg}", pid=p))
                        break

                    # Nếu BẬT tự chuyển chặng theo Level:
                    self.log(f"[{char_name}] [👀 FARM & GIÁM SÁT] Đang farm tại {stg_name}. Chờ đạt Level > {max_l}...", pid=pid)
                    self._update_client_card_nav_status(pid, f"⚔️ Farm Mốc {curr_idx+1}", 100)

                    stage_reset = False
                    while not stop_event.is_set():
                        time.sleep(2.0)
                        now_l = ProcessMemoryReader.read_character_level(pid)
                        if now_l is not None:
                            client.level = now_l
                            if now_l > max_l:
                                self.log(f"[{char_name}] 🎉🎉🎉 [LÊN CẤP!] Đạt Level {now_l} (Vượt {max_l})!", pid=pid)
                                break
                            elif now_l < min_l - 5:
                                self.log(f"[{char_name}] 🔄 [RESET DETECTED] Level giảm xuống {now_l}!", pid=pid)
                                stage_reset = True
                                break

                    if stop_event.is_set():
                        break

                    if stage_reset:
                        cur_l = ProcessMemoryReader.read_character_level(pid) or 1
                        nxt = 0
                        for i, s in enumerate(self.level_stages):
                            if s.get("min_level", 1) <= cur_l <= s.get("max_level", 400):
                                nxt = i
                                break
                        curr_idx = nxt
                    else:
                        curr_idx += 1

                if stop_event.is_set():
                    self.log(f"[{char_name}] [⏹] Đã dừng.", pid=pid)
                    self._update_client_card_nav_status(pid, "🟠 Đã Dừng", 0)
                else:
                    self.log(f"[{char_name}] [🏆] Hoàn thành lộ trình!", pid=pid)
                    self._update_client_card_nav_status(pid, "🟢 Hoàn Thành", 100)

            except Exception as ex:
                self.log(f"[{char_name}] [❌ LỖI] {ex}", pid=pid)
                self._update_client_card_nav_status(pid, "🔴 Lỗi", 0)
            finally:
                self._on_client_worker_done(pid)

        t = threading.Thread(target=worker, daemon=True)
        self.client_nav_threads[pid] = t
        t.start()
        self._update_header_stats()

    def _update_client_card_nav_status(self, pid: int, status_text: str, prog_pct: int):
        def _upd():
            if pid in self.client_card_widgets:
                w = self.client_card_widgets[pid]
                w["lbl_nav"].configure(text=status_text)
                w["prog"].set(prog_pct / 100.0)
                w["lbl_pct"].configure(text=f"{prog_pct}%")
        self.after(0, _upd)

    def _on_client_worker_done(self, pid: int):
        def _rst():
            if pid in self.client_card_widgets:
                w = self.client_card_widgets[pid]
                w["btn_run"].configure(text="▶️ Chạy", fg_color="#10b981", hover_color="#059669")
                w["lbl_nav"].configure(text="⚪ Sẵn Sàng", fg_color=("#e2e8f0", "#1e293b"))
            self._update_header_stats()
        self.after(0, _rst)

    def _toggle_client_auto_attack(self, client: ClientLiveState):
        def worker():
            self.log(f"[{client.char_name}] [⚔️] Bật/tắt Auto Attack...", pid=client.pid)
            toggle_auto_attack_via_sendmessage(client.hwnd)
        threading.Thread(target=worker, daemon=True).start()

    def _batch_set_auto_attack(self, enable: bool):
        selected_pids = [pid for pid, var in self.client_selected_vars.items() if var.get()]
        if not selected_pids:
            messagebox.showwarning("Chưa chọn", "Vui lòng tích chọn tài khoản trước!")
            return
        def worker():
            for c in self.clients:
                if c.pid in selected_pids:
                    toggle_auto_attack_via_sendmessage(c.hwnd)
                    time.sleep(0.05)
            st = "BẬT" if enable else "TẮT"
            self.log(f"[⚔️ BATCH AUTO] Đã {st} Auto cho {len(selected_pids)} tài khoản!")
        threading.Thread(target=worker, daemon=True).start()

    def _bring_window_to_front(self, hwnd: int):
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def _tile_all_game_windows(self):
        if not self.clients:
            messagebox.showwarning("Không có client", "Không tìm thấy client MEGAMU nào!")
            return
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.windll.user32
            rect = meg_navigator.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            screen_w = rect.right - rect.left
            screen_h = rect.bottom - rect.top
            off_x = rect.left
            off_y = rect.top

            n = len(self.clients)
            if n == 1:
                cols, rows = 1, 1
            elif n == 2:
                cols, rows = 2, 1
            elif n <= 4:
                cols, rows = 2, 2
            elif n <= 6:
                cols, rows = 3, 2
            elif n <= 8:
                cols, rows = 4, 2
            elif n <= 9:
                cols, rows = 3, 3
            else:
                cols = math.ceil(math.sqrt(n))
                rows = math.ceil(n / cols)

            w = screen_w // cols
            h = screen_h // rows
            for i, client in enumerate(self.clients):
                r = i // cols
                c = i % cols
                wx = off_x + c * w
                wy = off_y + r * h
                user32.ShowWindow(client.hwnd, 9)
                user32.SetWindowPos(client.hwnd, 0, wx, wy, w, h, 0x0004 | 0x0010)

            self.log(f"[🖥️ XẾP CỬA SỔ] Đã xếp {n} cửa sổ game theo lưới {cols}x{rows}!")
        except Exception as ex:
            self.log(f"[❌ LỖI XẾP CỬA SỔ] {ex}")

    # ==========================================================================
    # QUẢN LÝ LỘ TRÌNH MỐC LEVEL & TỌA ĐỘ (DROPDOWN + FORM + WAYPOINTS)
    # ==========================================================================
    def _get_default_level_stages(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Chặng 1: Tân Thủ", "map": "Lorencia", "min_level": 1, "max_level": 39,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 125, "y": 125, "desc": "Cổng thành", "map": "Lorencia"}]
            },
            {
                "name": "Chặng 2: Devias Tuyết", "map": "Devias", "min_level": 40, "max_level": 79,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 220, "y": 60, "desc": "Cổng Bắc", "map": "Devias"}]
            },
            {
                "name": "Chặng 3: Lost Tower", "map": "Lost Tower", "min_level": 80, "max_level": 149,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 208, "y": 78, "desc": "Bãi Lost Tower 1", "map": "Lost Tower"}]
            },
            {
                "name": "Chặng 4: Biển Atlans", "map": "Atlans", "min_level": 150, "max_level": 250,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 24, "y": 19, "desc": "Bãi cá mập", "map": "Atlans"}]
            },
            {
                "name": "Chặng 5: Sa Mạc Tarkan", "map": "Tarkan", "min_level": 251, "max_level": 400,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 130, "y": 110, "desc": "Bãi đốm 1", "map": "Tarkan"}]
            },
            {
                "name": "Chặng 6: Master Level", "map": "Aida", "min_level": 401, "max_level": 1000,
                "auto_attack": True, "auto_warp": True, "waypoints": [{"x": 100, "y": 100, "desc": "Bãi cây Aida 1", "map": "Aida"}]
            }
        ]

    def _sync_dropdown_and_form_from_stage(self, stage_idx: int):
        """Đồng bộ danh sách combobox và nạp dữ liệu mốc chỉ định vào form"""
        if not self.level_stages:
            return
        stage_idx = max(0, min(stage_idx, len(self.level_stages) - 1))
        self.active_stage_idx = stage_idx

        # 1. Cập nhật các lựa chọn trong combobox
        opts = []
        for i, s in enumerate(self.level_stages):
            opts.append(f"#{i+1}: {s.get('name', 'Mốc')} (Lv {s.get('min_level')}-{s.get('max_level')})")
        self.cmb_stage_selector.configure(values=opts)
        if 0 <= stage_idx < len(opts):
            self.cmb_stage_selector.set(opts[stage_idx])

        # 2. Đưa dữ liệu mốc vào form
        stg = self.level_stages[stage_idx]
        self.ent_stg_name.delete(0, "end")
        self.ent_stg_name.insert(0, stg.get("name", ""))

        self.ent_stg_min.delete(0, "end")
        self.ent_stg_min.insert(0, str(stg.get("min_level", 1)))

        self.ent_stg_max.delete(0, "end")
        self.ent_stg_max.insert(0, str(stg.get("max_level", 400)))

        m_name = stg.get("map", "Lorencia")
        if m_name in meg_navigator.POPULAR_MAPS:
            self.cmb_stg_map.set(m_name)
        else:
            self.cmb_stg_map.set("Lorencia")

        if stg.get("auto_warp", True):
            self.chk_auto_warp.select()
        else:
            self.chk_auto_warp.deselect()

        if stg.get("auto_attack", True):
            self.chk_auto_attack.select()
        else:
            self.chk_auto_attack.deselect()

        # 3. Vẽ danh sách tọa độ
        self._render_waypoints_list()

    def _on_stage_dropdown_selected(self, choice: str):
        try:
            idx = int(choice.split(":")[0].replace("#", "").strip()) - 1
            self._sync_dropdown_and_form_from_stage(idx)
        except Exception:
            pass

    def _on_active_stage_form_changed(self, event=None):
        if not (0 <= self.active_stage_idx < len(self.level_stages)):
            return
        stg = self.level_stages[self.active_stage_idx]
        stg["name"] = self.ent_stg_name.get().strip()
        try:
            stg["min_level"] = int(self.ent_stg_min.get().strip())
        except ValueError:
            pass
        try:
            stg["max_level"] = int(self.ent_stg_max.get().strip())
        except ValueError:
            pass
        stg["map"] = self.cmb_stg_map.get().strip()
        stg["auto_warp"] = bool(self.chk_auto_warp.get())
        stg["auto_attack"] = bool(self.chk_auto_attack.get())

        # Cập nhật nhãn combobox
        opts = []
        for i, s in enumerate(self.level_stages):
            opts.append(f"#{i+1}: {s.get('name', 'Mốc')} (Lv {s.get('min_level')}-{s.get('max_level')})")
        self.cmb_stage_selector.configure(values=opts)

    def _add_new_stage(self):
        last_max = self.level_stages[-1].get("max_level", 400) if self.level_stages else 0
        new_min = last_max + 1
        new_max = new_min + 50
        new_stg = {
            "name": f"Chặng {len(self.level_stages)+1}",
            "map": "Lorencia",
            "min_level": new_min,
            "max_level": new_max,
            "auto_attack": True,
            "auto_warp": True,
            "waypoints": []
        }
        self.level_stages.append(new_stg)
        self._sync_dropdown_and_form_from_stage(len(self.level_stages) - 1)
        self.log(f"[➕ THÊM MỐC] Đã tạo mốc mới #{len(self.level_stages)}: '{new_stg['name']}'.")

    def _delete_active_stage(self):
        if len(self.level_stages) <= 1:
            messagebox.showwarning("Không thể xóa", "Phải giữ lại ít nhất 1 mốc lộ trình!")
            return
        stg = self.level_stages[self.active_stage_idx]
        if messagebox.askyesno("Xóa mốc", f"Bạn có chắc muốn xóa mốc '{stg.get('name')}'?"):
            del self.level_stages[self.active_stage_idx]
            new_idx = max(0, self.active_stage_idx - 1)
            self._sync_dropdown_and_form_from_stage(new_idx)
            self.log(f"[🗑️ ĐÃ XÓA MỐC] Đã xóa mốc.")

    def _render_waypoints_list(self):
        for w in self.scroll_waypoints.winfo_children():
            w.destroy()

        if not (0 <= self.active_stage_idx < len(self.level_stages)):
            return

        stage = self.level_stages[self.active_stage_idx]
        wps = stage.get("waypoints", [])
        total = len(wps)
        s_map = stage.get("map", "Lorencia")

        self.lbl_stage_summary.configure(
            text=f"📍 {total} tọa độ | 🗺️ {s_map} | ⚔️ Auto Đánh: {'Bật' if stage.get('auto_attack', True) else 'Tắt'}"
        )

        if not wps:
            ctk.CTkLabel(
                self.scroll_waypoints,
                text=f"📍 Chưa có tọa độ nào trong map '{s_map}'.\n👉 Vào game chạy tới bãi farm và bấm [F8] để lấy tọa độ tức thời!",
                font=ctk.CTkFont(size=11), text_color="#94a3b8"
            ).pack(pady=16)
            return

        for idx, wp in enumerate(wps, start=1):
            is_last = (idx == total)
            card = ctk.CTkFrame(
                self.scroll_waypoints,
                fg_color=("gray95", "#0f2347" if is_last else "#1e293b"),
                corner_radius=6, height=28
            )
            card.pack(fill="x", padx=2, pady=1)

            ctk.CTkLabel(
                card, text=f"#{idx:02d}", width=28, font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#10b981" if is_last else "#38bdf8"
            ).pack(side="left", padx=(4, 2))

            ctk.CTkLabel(
                card, text=f"({wp.get('x', 0)}, {wp.get('y', 0)})",
                font=ctk.CTkFont(size=11, weight="bold"), width=60, anchor="w"
            ).pack(side="left", padx=(2, 4))

            desc = wp.get("desc", "")
            if is_last and stage.get("auto_attack", True):
                if not desc:
                    desc = "Đích Farm [⚔️ Auto]"
                elif "[⚔️" not in desc:
                    desc = f"{desc} [⚔️ Auto]"
            elif not desc:
                desc = "Điểm trung gian"

            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10), anchor="w").pack(side="left", fill="x", expand=True, padx=2)

            btn_del = ctk.CTkButton(
                card, text="🗑️", width=22, height=20, fg_color="#b91c1c", hover_color="#991b1b",
                font=ctk.CTkFont(size=9), command=lambda wp_idx=idx-1: self._delete_coord_from_active_stage(wp_idx)
            )
            btn_del.pack(side="right", padx=(2, 4))

            if idx < total:
                btn_down = ctk.CTkButton(
                    card, text="⬇️", width=22, height=20, fg_color="#475569", hover_color="#334155",
                    font=ctk.CTkFont(size=9), command=lambda wp_idx=idx-1: self._move_coord_in_active_stage(wp_idx, 1)
                )
                btn_down.pack(side="right", padx=(2, 0))

            if idx > 1:
                btn_up = ctk.CTkButton(
                    card, text="⬆️", width=22, height=20, fg_color="#475569", hover_color="#334155",
                    font=ctk.CTkFont(size=9), command=lambda wp_idx=idx-1: self._move_coord_in_active_stage(wp_idx, -1)
                )
                btn_up.pack(side="right", padx=(2, 0))

    def _on_add_coord_to_active_stage(self):
        xs = self.ent_wp_x.get().strip()
        ys = self.ent_wp_y.get().strip()
        if not xs or not ys:
            messagebox.showwarning("Thiếu tọa độ", "Vui lòng nhập X và Y!")
            return
        try:
            x, y = int(xs), int(ys)
        except ValueError:
            messagebox.showerror("Sai định dạng", "Tọa độ X và Y phải là số!")
            return

        desc = self.ent_wp_desc.get().strip()
        stage = self.level_stages[self.active_stage_idx]
        wps = stage.setdefault("waypoints", [])
        if not desc:
            desc = f"Mốc #{len(wps)+1}"

        wps.append({
            "x": x, "y": y, "desc": desc,
            "map": stage.get("map", "Lorencia"), "time": time.strftime("%H:%M:%S")
        })
        self.ent_wp_x.delete(0, "end")
        self.ent_wp_y.delete(0, "end")
        self.ent_wp_desc.delete(0, "end")
        self._render_waypoints_list()
        self.log(f"[➕ TỌA ĐỘ] Đã thêm ({x}, {y}) vào '{stage['name']}'.")

    def _delete_coord_from_active_stage(self, wp_idx: int):
        wps = self.level_stages[self.active_stage_idx].get("waypoints", [])
        if 0 <= wp_idx < len(wps):
            del wps[wp_idx]
            self._render_waypoints_list()

    def _delete_all_coords_from_active_stage(self):
        stage = self.level_stages[self.active_stage_idx]
        wps = stage.get("waypoints", [])
        if not wps:
            return
        if messagebox.askyesno("Xóa hết", f"Bạn có chắc muốn xóa {len(wps)} tọa độ của mốc '{stage.get('name')}'?"):
            stage["waypoints"] = []
            self._render_waypoints_list()

    def _move_coord_in_active_stage(self, wp_idx: int, delta: int):
        wps = self.level_stages[self.active_stage_idx].get("waypoints", [])
        new_idx = wp_idx + delta
        if 0 <= new_idx < len(wps):
            wps[wp_idx], wps[new_idx] = wps[new_idx], wps[wp_idx]
            self._render_waypoints_list()

    def _capture_ram_coord_to_stage(self, stage_idx: int, from_hotkey: bool = False):
        if not self.selected_client:
            if self.clients:
                self._select_client_card(self.clients[0])
            else:
                msg = "Chưa phát hiện client game nào! Hãy khởi động game và đăng nhập nhân vật."
                if from_hotkey:
                    self.log(f"[!] [F8] {msg}")
                else:
                    messagebox.showwarning("Chưa chọn Client", msg)
                return

        state = ProcessMemoryReader.read_live_state(self.selected_client.pid)
        cur_x, cur_y = None, None
        map_name = getattr(self.selected_client, "map_name", "Unknown")

        if state:
            _, m_name, cx, cy, _, _ = state
            if cx is not None and cy is not None and (0 <= cx <= 255) and (0 <= cy <= 255):
                cur_x, cur_y = cx, cy
                if m_name and m_name != "Unknown":
                    map_name = m_name

        if cur_x is None or cur_y is None:
            cur_x = self.selected_client.x
            cur_y = self.selected_client.y

        if cur_x is None or cur_y is None:
            err = f"Không đọc được RAM từ {self.selected_client.char_name}. Hãy đảm bảo nhân vật đã vào game!"
            if from_hotkey:
                self.log(f"[!] [F8] {err}")
            else:
                messagebox.showerror("Lỗi RAM", err)
            return

        if not (0 <= stage_idx < len(self.level_stages)):
            return

        stage = self.level_stages[stage_idx]
        wps = stage.setdefault("waypoints", [])
        wps.append({
            "x": cur_x, "y": cur_y, "desc": f"Mốc #{len(wps)+1} (F8)",
            "map": map_name, "time": time.strftime("%H:%M:%S")
        })
        try:
            if winsound:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        if self.active_stage_idx == stage_idx:
            self.ent_wp_x.delete(0, "end")
            self.ent_wp_x.insert(0, str(cur_x))
            self.ent_wp_y.delete(0, "end")
            self.ent_wp_y.insert(0, str(cur_y))
            self._render_waypoints_list()

        tag = "[📍 F8]" if from_hotkey else "[📍 LẤY RAM]"
        self.log(f"{tag} [{self.selected_client.char_name}] Đã lấy ({cur_x}, {cur_y}) [{map_name}] vào '{stage['name']}'!", pid=self.selected_client.pid)

    def _toggle_trace_recorder(self):
        stage_idx = self.active_stage_idx
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trước!")
            return

        stage = self.level_stages[stage_idx]
        stg_name = stage.get("name", f"Chặng {stage_idx+1}")
        char_name = self.selected_client.char_name
        pid = self.selected_client.pid

        if self.is_recording_trace and self.recording_stage_idx == stage_idx:
            # DỪNG GHI VẾT VÀ CHẠY THUẬT TOÁN TỐI ƯU HÓA LỘ TRÌNH RDP
            self.is_recording_trace = False
            self.recording_stage_idx = None
            self.last_recorded_pos = None
            self.btn_trace.configure(text="🔴 Ghi Vết", fg_color="#dc2626", hover_color="#b91c1c")

            raw_pts = list(self.trace_raw_points)
            self.trace_raw_points.clear()

            if len(raw_pts) >= 2:
                # Chạy thuật toán RDP để lọc sạch các mốc dư thừa, giữ lại góc rẽ và điểm then chốt
                simplified = ramer_douglas_peucker(raw_pts, epsilon=1.2)
                if len(simplified) < 2:
                    simplified = [raw_pts[0], raw_pts[-1]]

                m_name = self.selected_client.map_name or stage.get("map", "")
                new_wps = []
                n_pts = len(simplified)
                for i, (px, py) in enumerate(simplified, start=1):
                    if i == 1:
                        desc = "Xuất phát"
                    elif i == n_pts:
                        desc = "Bãi cắm (Đích)"
                    else:
                        desc = f"Khúc cua #{i-1}"
                    new_wps.append({
                        "x": px,
                        "y": py,
                        "desc": desc,
                        "map": m_name,
                        "time": time.strftime("%H:%M:%S")
                    })

                stage["waypoints"] = new_wps
                if self.active_stage_idx == stage_idx:
                    self._render_waypoints_list()

                self.log(f"[{char_name}] [✅ TỐI ƯU HÓA THÀNH CÔNG] Đã phân tích {len(raw_pts)} bước di chuyển -> Nén lọc thành {n_pts} mốc then chốt (loại bỏ rung lắc, giữ trọn khúc rẽ) cho '{stg_name}'!", pid=pid)
                try:
                    if winsound:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass
            else:
                self.log(f"[{char_name}] [⏹️ DỪNG GHI VẾT] Đã dừng ghi vết cho '{stg_name}' (Chưa có đủ điểm bước chân để tạo lộ trình).", pid=pid)
        else:
            self.is_recording_trace = True
            self.recording_stage_idx = stage_idx
            self.last_recorded_pos = None
            self.trace_raw_points.clear()

            cx = self.selected_client.x
            cy = self.selected_client.y
            if cx is not None and cy is not None:
                self.trace_raw_points.append((cx, cy))
                self.last_recorded_pos = (cx, cy)

            self.btn_trace.configure(text=f"⏹ Dừng ({len(self.trace_raw_points)})", fg_color="#ea580c", hover_color="#c2410c")
            self.log(f"[{char_name}] 🔴 [BẮT ĐẦU GHI VẾT THÔNG MINH] Hãy điều khiển nhân vật chạy theo lộ trình tới bãi cắm... Khi đến nơi, bấm '⏹ Dừng' để thuật toán RDP tự động nén tối ưu lộ trình!", pid=pid)
            try:
                if winsound:
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def _on_quick_warp_active_map(self):
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trước!")
            return
        target_map = self.cmb_stg_map.get().strip()
        if not target_map:
            return
        pid = self.selected_client.pid
        char_name = self.selected_client.char_name
        def worker():
            self.log(f"[{char_name}] [🌐 MOVE MAP] Gửi lệnh '/m {target_map}'...", pid=pid)
            try:
                nav = MegNavigator(pid)
                ok = nav.warp_to_map(target_map, log_callback=lambda msg, p=pid: self.log(f"[{char_name}] {msg}", pid=p))
                if ok:
                    self.log(f"[{char_name}] [✔] Đã đổi sang '{target_map}'!", pid=pid)
            except Exception as ex:
                self.log(f"[{char_name}] [❌ LỖI] {ex}", pid=pid)
        threading.Thread(target=worker, daemon=True).start()

    # ==========================================================================
    # NHẬT KÝ HOẠT ĐỘNG (LOGS FILTER & LOGGING)
    # ==========================================================================
    def _update_log_filter_options(self):
        opts = ["Tất Cả Tài Khoản"]
        for c in self.clients:
            opts.append(f"{c.char_name} (PID: {c.pid})")
        self.cmb_log_filter.configure(values=opts)

    def _on_log_filter_changed(self, choice: str):
        if choice == "Tất Cả Tài Khoản" or not choice:
            self.log_filter_pid = None
        else:
            try:
                pid_str = choice.split("PID:")[-1].replace(")", "").strip()
                self.log_filter_pid = int(pid_str)
            except Exception:
                self.log_filter_pid = None
        self._repopulate_logs_ui()

    def _repopulate_logs_ui(self):
        self.txt_logs.delete("1.0", "end")
        for log_pid, full_line in self.raw_logs_store:
            if self.log_filter_pid is None or log_pid == self.log_filter_pid:
                self.txt_logs.insert("end", full_line)
        self.txt_logs.see("end")

    def log(self, message: str, pid: Optional[int] = None):
        self.after(0, lambda: self._append_log_ui(message, pid))

    def _append_log_ui(self, message: str, pid: Optional[int] = None):
        t_str = time.strftime("[%H:%M:%S] ")
        full_line = t_str + message + "\n"
        self.raw_logs_store.append((pid, full_line))

        if len(self.raw_logs_store) > 2000:
            self.raw_logs_store = self.raw_logs_store[-1500:]

        if self.log_filter_pid is None or pid == self.log_filter_pid:
            self.txt_logs.insert("end", full_line)
            self.txt_logs.see("end")

    def _clear_logs(self):
        self.raw_logs_store.clear()
        self.txt_logs.delete("1.0", "end")

    # ==========================================================================
    # QUẢN LÝ BẢN ĐỒ POPUP DIALOG (.INI / .TXT)
    # ==========================================================================
    def _open_map_manager_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("🗺️ Quản Lý Danh Sách Bản Đồ (.ini / .txt)")
        dialog.geometry("580x520")
        dialog.minsize(500, 420)
        dialog.transient(self)
        dialog.after(100, dialog.lift)

        ctk.CTkLabel(
            dialog, text="🗺️ DANH SÁCH BẢN ĐỒ MEGAMU (.ini / .txt)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=16, pady=(12, 6), anchor="w")

        add_box = ctk.CTkFrame(dialog, fg_color="transparent")
        add_box.pack(fill="x", padx=16, pady=(0, 8))

        ent_new = ctk.CTkEntry(add_box, placeholder_text="Nhập tên map mới...", font=ctk.CTkFont(size=12))
        ent_new.pack(side="left", fill="x", expand=True, padx=(0, 6))

        scroll = ctk.CTkScrollableFrame(dialog, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        def render():
            for w in scroll.winfo_children():
                w.destroy()
            for idx, m in enumerate(meg_navigator.POPULAR_MAPS, start=1):
                r = ctk.CTkFrame(scroll, height=28, fg_color=("gray95", "#1e293b"))
                r.pack(fill="x", padx=2, pady=1)
                ctk.CTkLabel(r, text=f"#{idx:02d}", width=28, font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(side="left", padx=4)
                ctk.CTkLabel(r, text=m, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
                btn_d = ctk.CTkButton(
                    r, text="🗑️", width=24, height=20, fg_color="#b91c1c", hover_color="#991b1b",
                    font=ctk.CTkFont(size=9), command=lambda name=m: delete_map(name)
                )
                btn_d.pack(side="right", padx=4)

        def add_map():
            name = ent_new.get().strip()
            if not name:
                return
            current = list(meg_navigator.POPULAR_MAPS)
            for e in current:
                if e.lower() == name.lower():
                    messagebox.showinfo("Đã có", f"Bản đồ '{e}' đã có trong danh sách!")
                    return
            current.append(name)
            save_all_maps(current)
            ent_new.delete(0, "end")
            self.cmb_stg_map.configure(values=current)
            render()
            self.log(f"[💾 MAP] Đã thêm '{name}' vào maps.ini / maps.txt!")

        def delete_map(name: str):
            if messagebox.askyesno("Xóa", f"Xóa '{name}' khỏi danh sách?"):
                current = [m for m in meg_navigator.POPULAR_MAPS if m.lower() != name.lower()]
                save_all_maps(current)
                self.cmb_stg_map.configure(values=current)
                render()

        btn_add = ctk.CTkButton(
            add_box, text="➕ Thêm", width=70, height=28, fg_color="#10b981", hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"), command=add_map
        )
        btn_add.pack(side="left")

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 10))

        def open_notepad():
            target = get_active_maps_file()
            try:
                subprocess.Popen(["notepad.exe", target])
            except Exception:
                pass

        btn_note = ctk.CTkButton(
            footer, text="📝 Mở bằng Notepad", width=120, height=28, fg_color="#d97706", hover_color="#b45309",
            font=ctk.CTkFont(size=11), command=open_notepad
        )
        btn_note.pack(side="left")

        render()

    # ==========================================================================
    # LƯU / NẠP KẾ HOẠCH JSON
    # ==========================================================================
    def _save_level_plan_to_file(self):
        os.makedirs("plans", exist_ok=True)
        file_path = filedialog.asksaveasfilename(
            initialdir="plans", defaultextension=".json", filetypes=[("JSON files", "*.json")],
            title="Lưu Kế Hoạch Lộ Trình Đa Tài Khoản"
        )
        if file_path:
            try:
                data = {
                    "version": "3.5",
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stages": self.level_stages
                }
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.log(f"[💾 ĐÃ LƯU KẾ HOẠCH] Đã lưu {len(self.level_stages)} mốc vào '{os.path.basename(file_path)}'!")
                messagebox.showinfo("Đã Lưu", f"Lưu thành công vào:\n{file_path}")
            except Exception as ex:
                messagebox.showerror("Lỗi", f"Không thể lưu file:\n{ex}")

    def _load_level_plan_from_file(self):
        os.makedirs("plans", exist_ok=True)
        file_path = filedialog.askopenfilename(
            initialdir="plans", title="Nạp Kế Hoạch Lộ Trình", filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "stages" in data:
                    self.level_stages = data["stages"]
                elif isinstance(data, list):
                    self.level_stages = data
                else:
                    messagebox.showerror("Sai định dạng", "File JSON không hợp lệ!")
                    return
                self._sync_dropdown_and_form_from_stage(0)
                self.log(f"[📂 ĐÃ NẠP KẾ HOẠCH] Nạp thành công {len(self.level_stages)} mốc từ '{os.path.basename(file_path)}'!")
                messagebox.showinfo("Thành công", f"Đã nạp {len(self.level_stages)} mốc từ file!")
            except Exception as ex:
                messagebox.showerror("Lỗi", f"Không thể đọc file:\n{ex}")

    # ==========================================================================
    # CÁC TIỆN ÍCH KHÁC (THEME, F8 HOTKEY, GÓC CAMERA, ĐÓNG APP)
    # ==========================================================================
    def _toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def _on_angle_change(self, val):
        self.lbl_angle_val.configure(text=f"{int(val)}°")

    def _start_f8_hotkey_listener(self):
        def listener():
            if sys.platform != "win32":
                return
            user32 = ctypes.windll.user32
            VK_F8 = 0x77
            self.log("[⌨️ PHÍM NÓNG F8] Sẵn sàng lắng nghe F8 toàn màn hình!")
            while not self.hotkey_stop_event.is_set():
                time.sleep(0.05)
                if not self.hotkey_enabled:
                    continue
                try:
                    state = user32.GetAsyncKeyState(VK_F8)
                    if state & 0x8000:
                        now = time.time()
                        if now - self.last_f8_time > 0.4:
                            self.last_f8_time = now
                            self.after(0, self._on_f8_hotkey_pressed)
                except Exception:
                    pass
        threading.Thread(target=listener, daemon=True).start()

    def _on_toggle_f8_hotkey(self):
        self.hotkey_enabled = bool(self.sw_hotkey_f8.get())
        st = "BẬT" if self.hotkey_enabled else "TẮT"
        self.log(f"[⌨️ PHÍM NÓNG] Đã {st} phím tắt F8.")

    def _on_f8_hotkey_pressed(self):
        self._capture_ram_coord_to_stage(self.active_stage_idx, from_hotkey=True)

    def _on_close(self):
        self.hotkey_stop_event.set()
        for wkr in list(self.auto_workers.values()):
            try:
                wkr.stop()
            except Exception:
                pass
        for ev in self.client_stop_events.values():
            ev.set()
        if MegDirectEngine:
            for pid in list(MegDirectEngine._instances.keys()):
                try:
                    MegDirectEngine.release_engine(pid)
                except Exception:
                    pass
        self.destroy()


def main():
    app = MegNavigatorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
