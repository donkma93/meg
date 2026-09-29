#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Navigator - Modern GUI Edition
=========================================
Giao diện đồ họa hiện đại (CustomTkinter) cho hệ thống điều hướng tự động MEGAMU:
- Đọc trực tiếp RAM IL2CPP (Tọa độ X, Y, Bản đồ)
- Tự động chuyển map (/m <tên_map>)
- Di chuyển nền thông minh (Không chiếm chuột vật lý)
- Phản hồi khép kín (Tự đảo hướng 180° nếu đi xa hơn, né vật cản, dừng khi tới đích)
"""

import sys
import os
import ctypes

# Gắn thread vào interactive desktop Default để hiển thị cửa sổ lên màn hình chính người dùng
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

import time
import math
import json
import threading
import subprocess
from typing import Optional, List, Dict
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
    toggle_auto_attack_via_sendmessage
)

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MegNavigatorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MEGAMU Auto Navigator - Điều Hướng Tự Động")
        self.geometry("1100x750")
        self.minsize(1020, 680)

        # Trạng thái ứng dụng
        self.clients: List[ClientLiveState] = []
        self.selected_client: Optional[ClientLiveState] = None
        self.nav_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False

        # Quản lý Lộ trình đa điểm (Waypoints) & Phím nóng F8
        self.route_waypoints: List[Dict[str, any]] = []
        self.hotkey_stop_event = threading.Event()
        self.hotkey_enabled = True
        self.last_f8_time = 0.0

        # Quản lý Chặng Level (Auto-Leveling Route Stages)
        self.level_stages: List[Dict[str, any]] = self._get_default_level_stages()
        self.current_stage_idx: int = 0

        # Quản lý Ghi Vết Đường Đi Tự Động (Auto Path Trace Recording)
        self.is_recording_trace: bool = False
        self.recording_stage_idx: Optional[int] = None
        self.last_recorded_pos: Optional[Tuple[int, int]] = None

        self._build_ui()

        # Bắt đầu quét client lần đầu
        self.refresh_clients()

        # Bật luồng tự động cập nhật tọa độ RAM chu kỳ 1.2s
        self.after(1200, self._auto_update_live_ram)

        # Khởi động luồng lắng nghe phím nóng F8 toàn màn hình
        self._start_f8_hotkey_listener()

        # Xử lý khi đóng cửa sổ app
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Grid layout chính (2 cột)
        self.grid_columnconfigure(0, weight=4, minsize=420)
        self.grid_columnconfigure(1, weight=6, minsize=520)
        self.grid_rowconfigure(1, weight=1)

        # ----------------------------------------------------------------------
        # Top Header Bar
        # ----------------------------------------------------------------------
        header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#181b20"), height=65)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)
        header_frame.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="⚡ MEGAMU AUTO NAVIGATOR",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.grid(row=0, column=0, padx=(20, 10), pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text="Hệ thống điều hướng khép kín • Đọc RAM IL2CPP • Không chiếm chuột vật lý",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray65")
        )
        sub_lbl.grid(row=1, column=0, padx=(22, 10), pady=(0, 10), sticky="w")

        # Nút theme & trạng thái
        right_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header.grid(row=0, column=2, rowspan=2, padx=20, pady=10, sticky="e")

        self.theme_switch = ctk.CTkSwitch(
            right_header,
            text="Sáng / Tối",
            command=self._toggle_theme,
            font=ctk.CTkFont(size=12)
        )
        self.theme_switch.select()
        self.theme_switch.pack(side="right", padx=10)

        # ----------------------------------------------------------------------
        # Cột trái: Quản lý Client & Cài đặt lộ trình
        # ----------------------------------------------------------------------
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(15, 8), pady=12)
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=0)
        left_panel.grid_columnconfigure(0, weight=1)

        # Khung 1: Danh sách Client
        clients_box = ctk.CTkFrame(left_panel, corner_radius=10)
        clients_box.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 10))
        clients_box.grid_rowconfigure(1, weight=1)
        clients_box.grid_columnconfigure(0, weight=1)

        clients_header = ctk.CTkFrame(clients_box, fg_color="transparent")
        clients_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        clients_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            clients_header,
            text="🎮 DANH SÁCH CLIENT GAME",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        btn_refresh = ctk.CTkButton(
            clients_header,
            text="🔄 Quét lại",
            width=85,
            height=28,
            command=self.refresh_clients,
            font=ctk.CTkFont(size=12)
        )
        btn_refresh.grid(row=0, column=1, sticky="e")

        # Scrollable list chứa các client
        self.clients_scroll = ctk.CTkScrollableFrame(clients_box, corner_radius=6, height=130)
        self.clients_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.clients_scroll.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # Khung 2: HỆ THỐNG MỐC LEVEL & ĐIỀU HƯỚNG TỰ ĐỘNG (UNIFIED LEVEL TABS)
        # ----------------------------------------------------------------------
        self.level_box = ctk.CTkFrame(left_panel, corner_radius=10)
        self.level_box.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.level_box.grid_rowconfigure(2, weight=1)
        self.level_box.grid_columnconfigure(0, weight=1)

        # Header 1: Nút Bắt Đầu và Dừng lại
        master_bar1 = ctk.CTkFrame(self.level_box, fg_color="transparent")
        master_bar1.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        master_bar1.grid_columnconfigure(0, weight=3)
        master_bar1.grid_columnconfigure(1, weight=1)

        self.btn_level_start = ctk.CTkButton(
            master_bar1,
            text="🚀 BẮT ĐẦU CHẠY CÁC MỐC LEVEL",
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_start_level_route_navigation
        )
        self.btn_level_start.grid(row=0, column=0, padx=(0, 4), sticky="nsew")

        self.btn_level_stop = ctk.CTkButton(
            master_bar1,
            text="⏹ DỪNG LẠI",
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            state="disabled",
            command=self._on_stop_navigation
        )
        self.btn_level_stop.grid(row=0, column=1, sticky="nsew")

        # Aliases backward compatibility
        self.btn_start = self.btn_level_start
        self.btn_stop = self.btn_level_stop
        self.btn_route_start = self.btn_level_start
        self.btn_route_stop = self.btn_level_stop

        # Header 2: Thanh công cụ (Thêm Mốc, Lưu/Nạp Kế Hoạch, Phím F5, Camera)
        master_bar2 = ctk.CTkFrame(self.level_box, fg_color="transparent")
        master_bar2.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self.btn_add_stage = ctk.CTkButton(
            master_bar2,
            text="➕ Thêm Mốc",
            width=85,
            height=26,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._add_new_stage
        )
        self.btn_add_stage.pack(side="left", padx=(0, 4))

        self.btn_save_plan = ctk.CTkButton(
            master_bar2,
            text="💾 Lưu Kế Hoạch",
            width=95,
            height=26,
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=self._save_level_plan_to_file
        )
        self.btn_save_plan.pack(side="left", padx=(0, 4))

        self.btn_load_plan = ctk.CTkButton(
            master_bar2,
            text="📂 Nạp Kế Hoạch",
            width=95,
            height=26,
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=self._load_level_plan_from_file
        )
        self.btn_load_plan.pack(side="left", padx=(0, 6))

        self.sw_hotkey_f8 = ctk.CTkSwitch(
            master_bar2,
            text="Phím F8",
            font=ctk.CTkFont(size=11),
            command=self._on_toggle_f8_hotkey
        )
        self.sw_hotkey_f8.select()
        self.sw_hotkey_f8.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(master_bar2, text="📷", font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 2))
        self.slider_angle = ctk.CTkSlider(
            master_bar2, from_=0, to=360, number_of_steps=72, width=65, height=14, command=self._on_angle_change
        )
        self.slider_angle.set(0)
        self.slider_angle.pack(side="left", padx=2)

        self.lbl_angle_val = ctk.CTkLabel(master_bar2, text="0°", width=25, font=ctk.CTkFont(size=10, weight="bold"))
        self.lbl_angle_val.pack(side="left")

        # Khung Tabview cho từng Mốc Level
        self.stage_tabview = ctk.CTkTabview(self.level_box, corner_radius=8, command=self._on_stage_tab_switched)
        self.stage_tabview.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self.stage_tab_refs = []
        self.all_stage_map_combos = []

        # ----------------------------------------------------------------------
        # Cột phải: Live RAM Monitor & Log Box
        # ----------------------------------------------------------------------
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(8, 15), pady=12)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        # Khung 3: Live HUD Monitor Card
        hud_box = ctk.CTkFrame(right_panel, corner_radius=10)
        hud_box.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
        hud_box.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            hud_box,
            text="📊 GIÁM SÁT THỜI GIAN THỰC (LIVE RAM HUD)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 8))

        # 4 Mini Cards
        self.metric_char = self._create_metric_tile(hud_box, "Nhân vật", "—", row=1, col=0)
        self.metric_map = self._create_metric_tile(hud_box, "Bản đồ", "—", row=1, col=1)
        self.metric_coord = self._create_metric_tile(hud_box, "Tọa độ RAM", "(—, —)", row=1, col=2, accent=True)
        self.metric_dist = self._create_metric_tile(hud_box, "Khoảng cách", "—", row=1, col=3)

        # Thanh tiến trình & Trạng thái hoạt động
        status_bar_frame = ctk.CTkFrame(hud_box, fg_color="transparent")
        status_bar_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(10, 14))
        status_bar_frame.grid_columnconfigure(2, weight=1)

        self.lbl_status_badge = ctk.CTkLabel(
            status_bar_frame,
            text="🟢 SẴN SÀNG",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"),
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.lbl_status_badge.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.lbl_helper_badge = ctk.CTkLabel(
            status_bar_frame,
            text="⚔️ Auto: —",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"),
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.lbl_helper_badge.grid(row=0, column=1, padx=(0, 10), sticky="w")

        self.prog_bar = ctk.CTkProgressBar(status_bar_frame, height=12)
        self.prog_bar.set(0.0)
        self.prog_bar.grid(row=0, column=2, sticky="ew", padx=(0, 10))

        self.lbl_prog_pct = ctk.CTkLabel(status_bar_frame, text="0%", width=45, font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_prog_pct.grid(row=0, column=3, sticky="e")

        # Khung 4: Nhật ký điều hướng (Live Logs)
        logs_box = ctk.CTkFrame(right_panel, corner_radius=10)
        logs_box.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        logs_box.grid_rowconfigure(1, weight=1)
        logs_box.grid_columnconfigure(0, weight=1)

        logs_header = ctk.CTkFrame(logs_box, fg_color="transparent")
        logs_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        logs_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            logs_header,
            text="📜 NHẬT KÝ ĐIỀU HƯỚNG CHI TIẾT",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        btn_clear_log = ctk.CTkButton(
            logs_header,
            text="Xóa log",
            width=70,
            height=26,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            command=self._clear_logs,
            font=ctk.CTkFont(size=11)
        )
        btn_clear_log.grid(row=0, column=1, sticky="e")

        self.txt_logs = ctk.CTkTextbox(
            logs_box,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            corner_radius=6,
            wrap="word"
        )
        self.txt_logs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # Khởi tạo các tab mốc level ban đầu sau khi các widget status/HUD đã sẵn sàng
        self._rebuild_all_stage_tabs(0)

    def _create_metric_tile(self, parent, title: str, init_val: str, row: int, col: int, accent: bool = False):
        frame = ctk.CTkFrame(parent, fg_color=("#f1f5f9", "#111827" if not accent else "#0f2347"), corner_radius=8)
        frame.grid(row=row, column=col, padx=5, pady=4, sticky="nsew")

        lbl_t = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=11), text_color=("gray45", "gray55"))
        lbl_t.pack(anchor="w", padx=10, pady=(6, 0))

        val_color = "#3b82f6" if accent else ("gray20", "gray90")
        lbl_v = ctk.CTkLabel(frame, text=init_val, font=ctk.CTkFont(size=15, weight="bold"), text_color=val_color)
        lbl_v.pack(anchor="w", padx=10, pady=(0, 8))
        return lbl_v

    # --------------------------------------------------------------------------
    # Client Scanning & Selection
    # --------------------------------------------------------------------------
    def refresh_clients(self):
        """Quét và làm mới danh sách client MEGAMU đang chạy"""
        self.clients = scan_all_clients()
        # Xóa các widget client cũ
        for widget in self.clients_scroll.winfo_children():
            widget.destroy()

        if not self.clients:
            lbl_none = ctk.CTkLabel(
                self.clients_scroll,
                text="❌ Không tìm thấy client MEGAMU nào đang mở!\nVui lòng khởi động game.",
                text_color=("red", "#f87171"),
                font=ctk.CTkFont(size=13)
            )
            lbl_none.pack(padx=10, pady=25)
            self._update_hud_display(None)
            return

        self.client_radio_var = ctk.IntVar(value=self.clients[0].pid)

        for client in self.clients:
            self._create_client_card(client)

        # Mặc định chọn client đầu tiên nếu chưa chọn
        if not self.selected_client or not any(c.pid == self.selected_client.pid for c in self.clients):
            self._select_client(self.clients[0])
        else:
            # Cập nhật lại thông tin mới nhất của client đang chọn
            for c in self.clients:
                if c.pid == self.selected_client.pid:
                    self._select_client(c)
                    break

    def _create_client_card(self, client: ClientLiveState):
        card = ctk.CTkFrame(self.clients_scroll, corner_radius=8, fg_color=("#f8fafc", "#1f2937"))
        card.pack(fill="x", padx=4, pady=4)
        card.grid_columnconfigure(1, weight=1)

        rb = ctk.CTkRadioButton(
            card,
            text="",
            value=client.pid,
            variable=self.client_radio_var,
            width=20,
            command=lambda c=client: self._select_client(c)
        )
        rb.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=8)

        lvl_info = ""
        if client.level is not None:
            lvl_info = f" (Lv {client.level}"
            if client.resets is not None:
                lvl_info += f"/{client.resets}rr"
            lvl_info += ")"

        char_text = f"⚔️ {client.char_name}{lvl_info}"
        if client.server:
            char_text += f" [{client.server}]"

        lbl_char = ctk.CTkLabel(
            card,
            text=char_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        lbl_char.grid(row=0, column=1, sticky="w", padx=0, pady=(6, 0))

        coord_str = f"({client.x}, {client.y})" if client.x is not None else "(—, —)"
        auto_str = f"⚔️ Auto: {'BẬT' if client.is_auto_attack else 'TẮT'}"
        lbl_info = ctk.CTkLabel(
            card,
            text=f"PID: {client.pid} | Map: {client.map_name} | {coord_str} | {auto_str}",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray65"),
            anchor="w"
        )
        lbl_info.grid(row=1, column=1, sticky="w", padx=0, pady=(0, 6))

        # Click toàn bộ card để chọn
        for w in (card, lbl_char, lbl_info):
            w.bind("<Button-1>", lambda e, c=client: self._select_client(c))

    def _select_client(self, client: ClientLiveState):
        self.selected_client = client
        self.client_radio_var.set(client.pid)
        self._update_hud_display(client)
        self._update_stage_banner()

    def _update_hud_display(self, client: Optional[ClientLiveState]):
        if not client:
            self.metric_char.configure(text="—")
            self.metric_map.configure(text="—")
            self.metric_coord.configure(text="(—, —)")
            self.lbl_helper_badge.configure(text="⚔️ Auto: —", fg_color=("#e2e8f0", "#1e293b"), text_color=("gray40", "gray70"))
            return

        lvl_info = ""
        if client.level is not None:
            lvl_info = f" (Lv {client.level}"
            if client.resets is not None:
                lvl_info += f"/{client.resets}rr"
            lvl_info += ")"
        self.metric_char.configure(text=f"{client.char_name}{lvl_info} {client.server}")
        self.metric_map.configure(text=f"{client.map_name}")
        coord_text = f"({client.x}, {client.y})" if client.x is not None else "(—, —)"
        self.metric_coord.configure(text=coord_text)
        if client.is_auto_attack:
            self.lbl_helper_badge.configure(
                text=f"⚔️ Auto: BẬT ({client.helper_active_time}s)",
                fg_color=("#bbf7d0", "#14532d"),
                text_color=("#166534", "#4ade80")
            )
        else:
            self.lbl_helper_badge.configure(
                text="⚔️ Auto: TẮT",
                fg_color=("#e2e8f0", "#1e293b"),
                text_color=("gray40", "gray70")
            )

    def _auto_update_live_ram(self):
        """Cập nhật tọa độ RAM chu kỳ nền mỗi 1.2s vào giao diện"""
        if self.selected_client:
            state = ProcessMemoryReader.read_live_state(self.selected_client.pid)
            if state:
                map_id, map_name, cur_x, cur_y, _, _ = state
                self.selected_client.map_id = map_id
                self.selected_client.map_name = map_name
                self.selected_client.x = cur_x
                self.selected_client.y = cur_y
                self.metric_coord.configure(text=f"({cur_x}, {cur_y})")
                self.metric_map.configure(text=f"{map_name}")
                self._update_coord_preview()

            now_lvl = ProcessMemoryReader.read_character_level(self.selected_client.pid)
            if now_lvl is not None:
                self.selected_client.level = now_lvl
                lvl_info = f" (Lv {now_lvl}"
                if self.selected_client.resets is not None:
                    lvl_info += f"/{self.selected_client.resets}rr"
                lvl_info += ")"
                self.metric_char.configure(text=f"{self.selected_client.char_name}{lvl_info} {self.selected_client.server}")

            helper_state = ProcessMemoryReader.read_helper_state(self.selected_client.pid)
            if helper_state:
                is_active, is_conf, active_time, _ = helper_state
                self.selected_client.is_auto_attack = is_active
                self.selected_client.helper_active_time = active_time
                if is_active:
                    self.lbl_helper_badge.configure(
                        text=f"⚔️ Auto: BẬT ({active_time}s)",
                        fg_color=("#bbf7d0", "#14532d"),
                        text_color=("#166534", "#4ade80")
                    )
                else:
                    self.lbl_helper_badge.configure(
                        text="⚔️ Auto: TẮT",
                        fg_color=("#e2e8f0", "#1e293b"),
                        text_color=("gray40", "gray70")
                    )

            # Xử lý Ghi Vết Đường Đi Tự Động (Auto Trace Recorder)
            if self.is_recording_trace and self.recording_stage_idx is not None:
                s_idx = self.recording_stage_idx
                if 0 <= s_idx < len(self.level_stages):
                    cur_x = self.selected_client.x
                    cur_y = self.selected_client.y
                    map_name = self.selected_client.map_name or self.level_stages[s_idx].get("map", "")

                    if cur_x is not None and cur_y is not None:
                        should_rec = False
                        if self.last_recorded_pos is None:
                            should_rec = True
                        else:
                            lx, ly = self.last_recorded_pos
                            d_move = max(abs(cur_x - lx), abs(cur_y - ly))
                            if d_move >= 2:
                                should_rec = True

                        if should_rec:
                            self.last_recorded_pos = (cur_x, cur_y)
                            stage = self.level_stages[s_idx]
                            wps = stage.setdefault("waypoints", [])
                            wps.append({
                                "x": cur_x,
                                "y": cur_y,
                                "desc": f"Vết #{len(wps)+1}",
                                "map": map_name,
                                "time": time.strftime("%H:%M:%S")
                            })
                            self._refresh_stage_waypoints(s_idx)
                            self.log(f"[🔴 GHI VẾT RAM] Đã tự lưu mốc #{len(wps)}: ({cur_x}, {cur_y}) [{map_name}]")
                            try:
                                if winsound:
                                    winsound.MessageBeep(winsound.MB_OK)
                            except Exception:
                                pass

        interval = 400 if self.is_recording_trace else 1200
        self.after(interval, self._auto_update_live_ram)

    # --------------------------------------------------------------------------
    # Event Handlers & Callbacks
    # --------------------------------------------------------------------------
    def _toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def _on_angle_change(self, val):
        self.lbl_angle_val.configure(text=f"{int(val)}°")

    def _update_coord_preview(self, event=None):
        if not self.selected_client or self.selected_client.x is None or self.selected_client.y is None:
            self.metric_dist.configure(text="—")
            return

        cx = self.selected_client.x
        cy = self.selected_client.y

        target_pt = getattr(self, "current_nav_target", None)
        if not target_pt and hasattr(self, "level_stages") and (0 <= getattr(self, "current_stage_idx", -1) < len(self.level_stages)):
            wps = self.level_stages[self.current_stage_idx].get("waypoints", [])
            if wps:
                target_pt = (wps[0].get("x", 0), wps[0].get("y", 0))

        if target_pt:
            tx, ty = target_pt
            dist = max(abs(tx - cx), abs(ty - cy))
            self.metric_dist.configure(text=f"{dist} ô")
        else:
            self.metric_dist.configure(text="—")

    def log(self, message: str):
        """In log an toàn từ bất kỳ luồng nào vào ô nhật ký"""
        self.after(0, lambda: self._append_log_ui(message))

    def _append_log_ui(self, message: str):
        t_str = time.strftime("[%H:%M:%S] ")
        self.txt_logs.insert("end", t_str + message + "\n")
        self.txt_logs.see("end")

    def _clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    def _update_all_map_comboboxes(self, popular_list: List[str], selected_name: Optional[str] = None):
        """Cập nhật giá trị danh sách map trên tất cả các combobox chọn map ở các tab mốc"""
        for cmb in getattr(self, "all_stage_map_combos", []):
            try:
                cmb.configure(values=popular_list)
                if selected_name and selected_name in popular_list:
                    cmb.set(selected_name)
            except Exception:
                pass

    def _on_quick_add_map(self):
        """Thêm map vào danh sách và lưu ngay ra file .ini và .txt"""
        cur_map = ""
        if hasattr(self, "stage_tab_refs") and (0 <= getattr(self, "current_stage_idx", -1) < len(self.stage_tab_refs)):
            cmb = self.stage_tab_refs[self.current_stage_idx].get("cmb_map")
            if cmb:
                cur_map = cmb.get().strip()

        from tkinter import simpledialog
        map_name = simpledialog.askstring("Thêm Bản Đồ Mới", "Nhập tên bản đồ cần thêm vào danh sách:", initialvalue=cur_map, parent=self)
        if not map_name or not map_name.strip():
            return
        map_name = map_name.strip()

        current_popular = list(meg_navigator.POPULAR_MAPS)
        for existing in current_popular:
            if existing.strip().lower() == map_name.lower():
                messagebox.showinfo("Bản đồ đã tồn tại", f"Bản đồ '{existing}' đã có sẵn trong danh sách!")
                return

        current_popular.append(map_name)
        ok = save_all_maps(current_popular)
        if ok:
            self._update_all_map_comboboxes(current_popular, selected_name=map_name)
            active_file = os.path.basename(get_active_maps_file())
            self.log(f"[💾 ĐÃ LƯU MAP] Đã thêm '{map_name}' vào danh sách và lưu vào '{active_file}'!")
            messagebox.showinfo("Đã lưu Bản Đồ", f"Đã thêm thành công '{map_name}' vào danh sách chọn nhanh!\nĐã lưu tự động ra file:\n- maps.ini\n- maps.txt")
        else:
            messagebox.showerror("Lỗi Lưu", "Không thể ghi danh sách map vào file cấu hình!")

    def _reload_map_config(self, show_msg: bool = True):
        """Tải lại file cấu hình maps.ini / maps.txt / maps_config.json"""
        try:
            maps, popular, _ = load_maps_config()
            self._update_all_map_comboboxes(popular)
            active_file = os.path.basename(get_active_maps_file())
            self.log(f"[⚙️ MAP CONFIG] Đã nạp {len(popular)} map từ file '{active_file}' ({len(maps)} catalog ID)!")
            if show_msg:
                messagebox.showinfo("Cấu hình Map", f"Đã nạp thành công {len(popular)} bản đồ từ file '{active_file}'!")
        except Exception as ex:
            self.log(f"[❌ LỖI CONFIG] {ex}")
            if show_msg:
                messagebox.showerror("Lỗi Cấu Hình", f"Không thể tải file cấu hình map:\n{ex}")

    def _open_map_manager_dialog(self):
        """Mở cửa sổ Quản Lý Danh Sách Bản Đồ (.ini / .txt)"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🗺️ Quản Lý Danh Sách Bản Đồ (.ini / .txt)")
        dialog.geometry("640x580")
        dialog.minsize(580, 500)
        dialog.transient(self)
        dialog.after(100, dialog.lift)
        dialog.after(150, dialog.focus_force)

        # Header Frame
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            header,
            text="🗺️ QUẢN LÝ DANH SÁCH BẢN ĐỒ (MAP CONFIG)",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w")

        active_path = get_active_maps_file()
        lbl_active_file = ctk.CTkLabel(
            header,
            text=f"Đang liên kết: {os.path.basename(active_path)} | Hỗ trợ lưu đọc file .ini và file .txt",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        lbl_active_file.pack(anchor="w", pady=(1, 0))

        # Quick Add Bar
        add_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray20"), corner_radius=8)
        add_frame.pack(fill="x", padx=16, pady=(4, 8))

        ctk.CTkLabel(
            add_frame,
            text="Nhập map mới:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(10, 6), pady=8)

        ent_new_map = ctk.CTkEntry(
            add_frame,
            placeholder_text="Ví dụ: Scorched Canyon, Acheron, Karutan 3...",
            font=ctk.CTkFont(size=12),
            height=28
        )
        ent_new_map.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=8)

        # Tabview chứa 2 chế độ: Trực quan & Soạn thảo Text
        tabview = ctk.CTkTabview(dialog, corner_radius=8)
        tabview.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tab_visual = tabview.add("📋 Danh Sách Trực Quan")
        tab_raw = tabview.add("📝 Soạn Thảo Dạng Text (.txt / .ini)")

        # --- TAB 1: TRỰC QUAN ---
        scroll_maps = ctk.CTkScrollableFrame(tab_visual, corner_radius=6)
        scroll_maps.pack(fill="both", expand=True, padx=4, pady=4)

        tab1_footer = ctk.CTkFrame(tab_visual, fg_color="transparent")
        tab1_footer.pack(fill="x", padx=4, pady=(4, 0))
        lbl_map_count = ctk.CTkLabel(tab1_footer, text="", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_map_count.pack(side="left")

        # --- TAB 2: SOẠN THẢO TEXT TRỰC TIẾP ---
        raw_top_bar = ctk.CTkFrame(tab_raw, fg_color="transparent")
        raw_top_bar.pack(fill="x", padx=4, pady=(2, 4))
        ctk.CTkLabel(
            raw_top_bar,
            text="Nhập hoặc dán trực tiếp danh sách map (mỗi dòng 1 tên map):",
            font=ctk.CTkFont(size=11)
        ).pack(side="left")

        txt_raw_editor = ctk.CTkTextbox(tab_raw, font=("Consolas", 12), wrap="none")
        txt_raw_editor.pack(fill="both", expand=True, padx=4, pady=4)

        raw_btn_bar = ctk.CTkFrame(tab_raw, fg_color="transparent")
        raw_btn_bar.pack(fill="x", padx=4, pady=(4, 2))

        # Local state
        dialog_maps: List[str] = list(meg_navigator.POPULAR_MAPS)

        def sync_raw_textbox():
            txt_raw_editor.delete("1.0", "end")
            txt_raw_editor.insert("1.0", "\n".join(dialog_maps))

        def render_visual_list():
            for widget in scroll_maps.winfo_children():
                widget.destroy()

            for idx, map_name in enumerate(dialog_maps, start=1):
                item_row = ctk.CTkFrame(scroll_maps, fg_color=("gray90", "gray17"), corner_radius=6, height=32)
                item_row.pack(fill="x", padx=2, pady=2)

                # Số thứ tự
                badge = ctk.CTkLabel(
                    item_row,
                    text=f"#{idx:02d}",
                    width=38,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#38bdf8"
                )
                badge.pack(side="left", padx=(8, 4), pady=4)

                # Tên map
                name_lbl = ctk.CTkLabel(
                    item_row,
                    text=map_name,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w"
                )
                name_lbl.pack(side="left", fill="x", expand=True, padx=4, pady=4)

                # Nút Chọn làm bản đồ đích
                btn_pick = ctk.CTkButton(
                    item_row,
                    text="🎯 Chọn",
                    width=54,
                    height=24,
                    fg_color="#0284c7",
                    hover_color="#0369a1",
                    font=ctk.CTkFont(size=11),
                    command=lambda m=map_name: on_pick_map(m)
                )
                btn_pick.pack(side="right", padx=(2, 4), pady=4)

                # Nút Xóa
                btn_del = ctk.CTkButton(
                    item_row,
                    text="🗑️",
                    width=32,
                    height=24,
                    fg_color="#b91c1c",
                    hover_color="#991b1b",
                    font=ctk.CTkFont(size=11),
                    command=lambda m=map_name: on_delete_map(m)
                )
                btn_del.pack(side="right", padx=(2, 2), pady=4)

            lbl_map_count.configure(text=f"Tổng số: {len(dialog_maps)} bản đồ")
            sync_raw_textbox()

        def on_pick_map(picked: str):
            self.cmb_target_map.set(picked)
            self.log(f"[🎯 CHỌN MAP] Đã đặt bản đồ đích: '{picked}'")
            messagebox.showinfo("Đã chọn", f"Đã đặt '{picked}' làm Bản đồ đích trên màn hình chính!")

        def on_delete_map(target_map: str):
            if target_map in dialog_maps:
                if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa bản đồ '{target_map}' khỏi danh sách?"):
                    dialog_maps.remove(target_map)
                    save_all_maps(dialog_maps)
                    self._update_all_map_comboboxes(dialog_maps)
                    render_visual_list()
                    self.log(f"[🗑️ ĐÃ XÓA MAP] Đã xóa '{target_map}' và cập nhật file cấu hình.")

        def on_add_map_action():
            new_name = ent_new_map.get().strip()
            if not new_name:
                messagebox.showwarning("Chưa nhập tên", "Vui lòng nhập tên bản đồ trước khi bấm Thêm!")
                return
            for existing in dialog_maps:
                if existing.lower() == new_name.lower():
                    messagebox.showinfo("Trùng lặp", f"Bản đồ '{existing}' đã tồn tại trong danh sách!")
                    return
            dialog_maps.append(new_name)
            ent_new_map.delete(0, "end")
            save_all_maps(dialog_maps)
            self._update_all_map_comboboxes(dialog_maps, selected_name=new_name)
            render_visual_list()
            self.log(f"[💾 ĐÃ LƯU MAP] Đã thêm '{new_name}' vào file .ini/.txt và danh sách!")
            messagebox.showinfo("Thành công", f"Đã thêm và lưu bản đồ '{new_name}' vào file cấu hình!")

        btn_add = ctk.CTkButton(
            add_frame,
            text="➕ Thêm",
            width=70,
            height=28,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=on_add_map_action
        )
        btn_add.pack(side="left", padx=(0, 8), pady=8)
        ent_new_map.bind("<Return>", lambda e: on_add_map_action())

        def on_save_from_raw():
            raw_text = txt_raw_editor.get("1.0", "end")
            parsed = []
            for line in raw_text.splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or clean.startswith(";"):
                    continue
                if "=" in clean or ":" in clean:
                    sep = "=" if "=" in clean else ":"
                    _, val = clean.split(sep, 1)
                    clean = val.strip()
                if clean and clean not in parsed:
                    parsed.append(clean)

            if not parsed:
                messagebox.showwarning("Dữ liệu trống", "Không tìm thấy tên bản đồ hợp lệ nào trong ô soạn thảo!")
                return

            dialog_maps.clear()
            dialog_maps.extend(parsed)
            save_all_maps(dialog_maps)
            self._update_all_map_comboboxes(dialog_maps)
            render_visual_list()
            self.log(f"[💾 ĐÃ LƯU TEXT MAP] Đã nạp và lưu {len(dialog_maps)} bản đồ từ văn bản vào file .ini/.txt!")
            messagebox.showinfo("Đã Lưu", f"Đã cập nhật thành công {len(dialog_maps)} bản đồ vào file cấu hình!")

        btn_save_raw = ctk.CTkButton(
            raw_btn_bar,
            text="💾 Nạp & Lưu Nội Dung Text Vào File (.ini/.txt)",
            fg_color="#10b981",
            hover_color="#059669",
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=on_save_from_raw
        )
        btn_save_raw.pack(side="left", padx=(0, 6))

        btn_reload_raw = ctk.CTkButton(
            raw_btn_bar,
            text="🔄 Nạp lại",
            width=75,
            height=28,
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=sync_raw_textbox
        )
        btn_reload_raw.pack(side="left")

        # --- FOOTER TOOLBAR CHÍNH ---
        footer_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        footer_frame.pack(fill="x", padx=16, pady=(0, 12))

        def open_in_notepad():
            target_path = get_active_maps_file()
            try:
                os.startfile(target_path)
            except Exception:
                subprocess.Popen(["notepad.exe", target_path])

        def on_export_as():
            save_path = filedialog.asksaveasfilename(
                title="Xuất Danh Sách Map Ra File",
                defaultextension=".ini",
                filetypes=[("INI Config (*.ini)", "*.ini"), ("Text File (*.txt)", "*.txt"), ("Tất cả files", "*.*")]
            )
            if save_path:
                ext = os.path.splitext(save_path)[1].lower()
                if ext in (".txt", ".text"):
                    save_maps_to_txt(save_path, dialog_maps)
                else:
                    save_maps_to_ini(save_path, dialog_maps)
                messagebox.showinfo("Đã Xuất", f"Đã xuất thành công {len(dialog_maps)} map ra file:\n{save_path}")

        def on_import_from():
            open_path = filedialog.askopenfilename(
                title="Nhập Danh Sách Map Từ File",
                filetypes=[("Cấu hình Map (*.ini, *.txt, *.json)", "*.ini;*.txt;*.text;*.json"), ("Tất cả files", "*.*")]
            )
            if open_path:
                ext = os.path.splitext(open_path)[1].lower()
                if ext in (".txt", ".text"):
                    _, pop, _ = load_maps_from_txt(open_path)
                elif ext == ".ini":
                    _, pop, _ = load_maps_from_ini(open_path)
                else:
                    _, pop, _ = load_maps_config(open_path)

                if pop:
                    dialog_maps.clear()
                    dialog_maps.extend(pop)
                    save_all_maps(dialog_maps)
                    self._update_all_map_comboboxes(dialog_maps)
                    render_visual_list()
                    self.log(f"[📂 ĐÃ NHẬP MAP] Đã nhập {len(pop)} map từ '{os.path.basename(open_path)}'!")
                    messagebox.showinfo("Đã Nhập", f"Đã nhập thành công {len(pop)} map từ:\n{open_path}")
                else:
                    messagebox.showwarning("Không có dữ liệu", "Không tìm thấy tên map hợp lệ trong file đã chọn!")

        def on_reload_all():
            maps, popular, _ = load_maps_config()
            dialog_maps.clear()
            dialog_maps.extend(popular)
            self._update_all_map_comboboxes(dialog_maps)
            render_visual_list()
            act_file = os.path.basename(get_active_maps_file())
            lbl_active_file.configure(text=f"Đang liên kết: {act_file} | Hỗ trợ lưu đọc file .ini và file .txt")
            messagebox.showinfo("Đã nạp lại", f"Đã nạp lại {len(dialog_maps)} bản đồ từ file '{act_file}'!")

        btn_notepad = ctk.CTkButton(
            footer_frame,
            text="📝 Mở bằng Notepad",
            width=120,
            height=28,
            fg_color="#d97706",
            hover_color="#b45309",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=open_in_notepad
        )
        btn_notepad.pack(side="left", padx=(0, 6))

        btn_reload = ctk.CTkButton(
            footer_frame,
            text="🔄 Nạp lại file",
            width=90,
            height=28,
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=on_reload_all
        )
        btn_reload.pack(side="left", padx=(0, 6))

        btn_import = ctk.CTkButton(
            footer_frame,
            text="📁 Nhập file...",
            width=90,
            height=28,
            fg_color="#334155",
            hover_color="#1e293b",
            font=ctk.CTkFont(size=11),
            command=on_import_from
        )
        btn_import.pack(side="left", padx=(0, 6))

        btn_export = ctk.CTkButton(
            footer_frame,
            text="💾 Xuất file...",
            width=90,
            height=28,
            fg_color="#334155",
            hover_color="#1e293b",
            font=ctk.CTkFont(size=11),
            command=on_export_as
        )
        btn_export.pack(side="left", padx=(0, 6))

        btn_close = ctk.CTkButton(
            footer_frame,
            text="Đóng",
            width=70,
            height=28,
            fg_color="#3f3f46",
            hover_color="#27272a",
            font=ctk.CTkFont(size=11),
            command=dialog.destroy
        )
        btn_close.pack(side="right")

        # Khởi tạo danh sách ban đầu
        render_visual_list()

    # ==========================================================================
    # HỆ THỐNG MỐC LEVEL & ĐIỀU HƯỚNG TỰ ĐỘNG (UNIFIED LEVEL SYSTEM)
    # ==========================================================================
    def _get_default_level_stages(self) -> List[Dict[str, any]]:
        """Danh sách các mốc level mặc định theo tiến trình chuẩn của MEGAMU Online"""
        return [
            {
                "name": "Chặng 1: Tân Thủ",
                "map": "Lorencia",
                "min_level": 1,
                "max_level": 39,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 125, "y": 125, "desc": "Bãi cổng thành", "map": "Lorencia"}
                ]
            },
            {
                "name": "Chặng 2: Devias Tuyết",
                "map": "Devias",
                "min_level": 40,
                "max_level": 79,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 220, "y": 60, "desc": "Bãi quái cổng Bắc", "map": "Devias"}
                ]
            },
            {
                "name": "Chặng 3: Lost Tower",
                "map": "Lost Tower",
                "min_level": 80,
                "max_level": 149,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 208, "y": 78, "desc": "Bãi Lost Tower 1", "map": "Lost Tower"}
                ]
            },
            {
                "name": "Chặng 4: Biển Atlans",
                "map": "Atlans",
                "min_level": 150,
                "max_level": 250,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 24, "y": 19, "desc": "Bãi cá mập Atlans", "map": "Atlans"}
                ]
            },
            {
                "name": "Chặng 5: Sa Mạc Tarkan",
                "map": "Tarkan",
                "min_level": 251,
                "max_level": 400,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 130, "y": 110, "desc": "Bãi đốm Tarkan 1", "map": "Tarkan"}
                ]
            },
            {
                "name": "Chặng 6: Master Level",
                "map": "Aida",
                "min_level": 401,
                "max_level": 1000,
                "auto_attack": True,
                "auto_warp": True,
                "waypoints": [
                    {"x": 100, "y": 100, "desc": "Bãi cây Aida 1", "map": "Aida"}
                ]
            }
        ]

    def _get_stage_tab_title(self, idx: int, stage: dict, used_titles: set) -> str:
        min_l = stage.get("min_level", 1)
        max_l = stage.get("max_level", 400)
        if max_l >= 1000:
            title = f"Lv {min_l}+"
        else:
            title = f"Lv {min_l}-{max_l}"
        if title in used_titles:
            title = f"Mốc {idx+1} ({min_l}-{max_l})"
        used_titles.add(title)
        return title

    def _rebuild_all_stage_tabs(self, select_idx: int = 0):
        """Dựng lại toàn bộ các Tab mốc level trong stage_tabview"""
        existing = list(self.stage_tabview._tab_dict.keys())
        for tname in existing:
            try:
                self.stage_tabview.delete(tname)
            except Exception:
                pass

        self.stage_tab_refs = []
        self.all_stage_map_combos = []
        used = set()

        for i, stage in enumerate(self.level_stages):
            title = self._get_stage_tab_title(i, stage, used)
            tab_frame = self.stage_tabview.add(title)
            refs = self._build_single_stage_tab(tab_frame, i, stage)
            refs["tab_title"] = title
            self.stage_tab_refs.append(refs)

        if self.stage_tab_refs:
            select_idx = max(0, min(select_idx, len(self.stage_tab_refs) - 1))
            self.current_stage_idx = select_idx
            sel_title = self.stage_tab_refs[select_idx]["tab_title"]
            try:
                self.stage_tabview.set(sel_title)
            except Exception:
                pass
            self._update_stage_banner()

    def _build_single_stage_tab(self, tab_frame, stage_idx: int, stage: dict) -> dict:
        """Tạo giao diện chi tiết bên trong một Tab mốc level"""
        # Card 1: Khung thiết lập Mốc & Bản Đồ
        cfg_box = ctk.CTkFrame(tab_frame, fg_color=("gray90", "gray17"), corner_radius=8)
        cfg_box.pack(fill="x", padx=4, pady=(2, 4))

        # Hàng 1: Tên mốc & Khoảng Level & Nút Xóa mốc
        row1 = ctk.CTkFrame(cfg_box, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(6, 3))

        ctk.CTkLabel(row1, text="Tên mốc:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        ent_name = ctk.CTkEntry(row1, width=125, font=ctk.CTkFont(size=11))
        ent_name.insert(0, stage.get("name", f"Chặng {stage_idx+1}"))
        ent_name.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(row1, text="Level từ:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        ent_min = ctk.CTkEntry(row1, width=42, font=ctk.CTkFont(size=11, weight="bold"))
        ent_min.insert(0, str(stage.get("min_level", 1)))
        ent_min.pack(side="left", padx=(0, 4))

        ctk.CTkLabel(row1, text="đến:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        ent_max = ctk.CTkEntry(row1, width=46, font=ctk.CTkFont(size=11, weight="bold"))
        ent_max.insert(0, str(stage.get("max_level", 400)))
        ent_max.pack(side="left", padx=(0, 8))

        btn_del_stage = ctk.CTkButton(
            row1,
            text="🗑️ Xóa Mốc",
            width=70,
            height=24,
            fg_color="#b91c1c",
            hover_color="#991b1b",
            font=ctk.CTkFont(size=11),
            command=lambda idx=stage_idx: self._delete_stage(idx)
        )
        btn_del_stage.pack(side="right")

        # Hàng 2: Bản đồ đích + Nút Move + Thêm Map + Quản lý Map
        row2 = ctk.CTkFrame(cfg_box, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(2, 3))

        ctk.CTkLabel(row2, text="Bản đồ đích:", font=ctk.CTkFont(size=11, weight="bold"), width=72, anchor="w").pack(side="left")
        cmb_map = ctk.CTkComboBox(row2, values=meg_navigator.POPULAR_MAPS, font=ctk.CTkFont(size=11), width=125)
        cur_map = stage.get("map", "Lorencia")
        if cur_map in meg_navigator.POPULAR_MAPS:
            cmb_map.set(cur_map)
        else:
            cmb_map.set("Lorencia")
        cmb_map.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.all_stage_map_combos.append(cmb_map)

        btn_warp = ctk.CTkButton(
            row2,
            text="Chỉ Move",
            width=62,
            height=25,
            fg_color="#d97706",
            hover_color="#b45309",
            font=ctk.CTkFont(size=11),
            command=lambda cmb=cmb_map: self._on_warp_only_from_combo(cmb)
        )
        btn_warp.pack(side="left", padx=(0, 4))

        btn_add_map = ctk.CTkButton(
            row2,
            text="➕ Thêm",
            width=55,
            height=25,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda cmb=cmb_map: self._on_quick_add_map_from_combo(cmb)
        )
        btn_add_map.pack(side="left", padx=(0, 4))

        btn_map_mgr = ctk.CTkButton(
            row2,
            text="📋 DS Map",
            width=65,
            height=25,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11),
            command=self._open_map_manager_dialog
        )
        btn_map_mgr.pack(side="left")

        # Hàng 3: Checkbox tùy chọn
        row3 = ctk.CTkFrame(cfg_box, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(2, 6))

        chk_auto_warp = ctk.CTkCheckBox(
            row3,
            text="Tự động đổi map (/m <tên_map>) nếu nhân vật khác bản đồ",
            font=ctk.CTkFont(size=11)
        )
        if stage.get("auto_warp", True):
            chk_auto_warp.select()
        else:
            chk_auto_warp.deselect()
        chk_auto_warp.pack(side="left", padx=(0, 10))

        chk_auto_attack = ctk.CTkCheckBox(
            row3,
            text="⚔️ Tự bật Auto Đánh (MuHelper) khi đến đích",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if stage.get("auto_attack", True):
            chk_auto_attack.select()
        else:
            chk_auto_attack.deselect()
        chk_auto_attack.pack(side="left")

        # Đồng bộ dữ liệu khi người dùng sửa form
        def on_cfg_changed(*args):
            stage["name"] = ent_name.get().strip()
            try:
                stage["min_level"] = int(ent_min.get().strip())
            except ValueError:
                pass
            try:
                stage["max_level"] = int(ent_max.get().strip())
            except ValueError:
                pass
            stage["map"] = cmb_map.get().strip()
            stage["auto_warp"] = bool(chk_auto_warp.get())
            stage["auto_attack"] = bool(chk_auto_attack.get())
            self._update_stage_banner()

        def on_map_selected(new_val):
            old_m = stage.get("map", "")
            new_m = new_val.strip()
            if old_m and normalize_map_name(old_m) != normalize_map_name(new_m):
                wps = stage.get("waypoints", [])
                if wps:
                    if messagebox.askyesno(
                        "Đổi bản đồ đích",
                        f"Bạn vừa đổi bản đồ từ '{old_m}' sang '{new_m}'.\n\n"
                        f"Hiện mốc này đang có {len(wps)} tọa độ của bản đồ cũ '{old_m}'.\n"
                        f"Bạn có muốn XÓA các tọa độ cũ để nhập tọa độ mới cho '{new_m}' không?"
                    ):
                        stage["waypoints"] = []
                        self._refresh_stage_waypoints(stage_idx)
                        self.log(f"[🗺️ ĐỔI MAP] Đã chuyển sang '{new_m}' và xóa tọa độ cũ của '{old_m}'. Hãy bấm F8 để lấy tọa độ mới!")
            on_cfg_changed()

        ent_name.bind("<KeyRelease>", on_cfg_changed)
        ent_min.bind("<KeyRelease>", on_cfg_changed)
        ent_max.bind("<KeyRelease>", on_cfg_changed)
        cmb_map.configure(command=on_map_selected)
        chk_auto_warp.configure(command=on_cfg_changed)
        chk_auto_attack.configure(command=on_cfg_changed)

        # Card 2: Khu vực Tọa Độ (Waypoints di chuyển lần lượt)
        wp_header = ctk.CTkFrame(tab_frame, fg_color="transparent")
        wp_header.pack(fill="x", padx=4, pady=(3, 1))

        ctk.CTkLabel(
            wp_header,
            text="📍 Các tọa độ cần di chuyển đến trong map này (chạy lần lượt từ trên xuống):",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left")

        # Hàng nhập tọa độ thủ công + F5 + Xóa hết
        wp_add_bar = ctk.CTkFrame(tab_frame, fg_color=("gray85", "gray20"), corner_radius=6)
        wp_add_bar.pack(fill="x", padx=4, pady=(0, 3))

        ctk.CTkLabel(wp_add_bar, text="X:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(6, 2), pady=4)
        ent_x = ctk.CTkEntry(wp_add_bar, width=42, font=ctk.CTkFont(size=11))
        ent_x.pack(side="left", padx=(0, 4), pady=4)

        ctk.CTkLabel(wp_add_bar, text="Y:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(2, 2), pady=4)
        ent_y = ctk.CTkEntry(wp_add_bar, width=42, font=ctk.CTkFont(size=11))
        ent_y.pack(side="left", padx=(0, 6), pady=4)

        ent_desc = ctk.CTkEntry(wp_add_bar, placeholder_text="Ghi chú (VD: Cổng thành, bãi farm...)", font=ctk.CTkFont(size=11))
        ent_desc.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=4)

        btn_add_coord = ctk.CTkButton(
            wp_add_bar,
            text="➕ Thêm",
            width=58,
            height=25,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda idx=stage_idx, ex=ent_x, ey=ent_y, ed=ent_desc: self._on_add_coord_to_stage(idx, ex, ey, ed)
        )
        btn_add_coord.pack(side="left", padx=(0, 4), pady=4)

        btn_f8_coord = ctk.CTkButton(
            wp_add_bar,
            text="📍 Lấy RAM [F8]",
            width=95,
            height=25,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=11),
            command=lambda idx=stage_idx: self._capture_ram_coord_to_stage(idx)
        )
        btn_f8_coord.pack(side="left", padx=(0, 4), pady=4)

        btn_trace_record = ctk.CTkButton(
            wp_add_bar,
            text="🔴 Ghi Vết Tự Động",
            width=115,
            height=25,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda idx=stage_idx: self._toggle_trace_recorder(idx)
        )
        btn_trace_record.pack(side="left", padx=(0, 4), pady=4)

        btn_clear_coords = ctk.CTkButton(
            wp_add_bar,
            text="🗑️ Xóa hết",
            width=68,
            height=25,
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(size=11),
            command=lambda idx=stage_idx: self._delete_all_coords_from_stage(idx)
        )
        btn_clear_coords.pack(side="left", padx=(0, 6), pady=4)

        # Khung danh sách tọa độ (Scrollable)
        scroll_wps = ctk.CTkScrollableFrame(tab_frame, corner_radius=6, height=135)
        scroll_wps.pack(fill="both", expand=True, padx=4, pady=(0, 3))

        # Hàng thao tác dưới cùng của tab
        bottom_bar = ctk.CTkFrame(tab_frame, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=4, pady=(2, 2))

        btn_run_single = ctk.CTkButton(
            bottom_bar,
            text="▶️ Chạy riêng mốc này",
            width=145,
            height=26,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda idx=stage_idx: self._on_start_single_stage(idx)
        )
        btn_run_single.pack(side="left", padx=(0, 8))

        lbl_summary = ctk.CTkLabel(
            bottom_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        lbl_summary.pack(side="left")

        refs = {
            "stage_idx": stage_idx,
            "ent_name": ent_name,
            "ent_min": ent_min,
            "ent_max": ent_max,
            "cmb_map": cmb_map,
            "chk_auto_warp": chk_auto_warp,
            "chk_auto_attack": chk_auto_attack,
            "ent_x": ent_x,
            "ent_y": ent_y,
            "ent_desc": ent_desc,
            "btn_trace_record": btn_trace_record,
            "scroll_wps": scroll_wps,
            "lbl_summary": lbl_summary
        }
        self._render_stage_waypoints_into_scroll(stage_idx, scroll_wps, lbl_summary)
        return refs

    def _render_stage_waypoints_into_scroll(self, stage_idx: int, scroll_frame, lbl_summary):
        """Vẽ danh sách các tọa độ theo bước đi lần lượt vào ScrollableFrame"""
        for widget in scroll_frame.winfo_children():
            widget.destroy()

        stage = self.level_stages[stage_idx]
        wps = stage.get("waypoints", [])
        total_wps = len(wps)
        s_map = stage.get("map", "Lorencia")

        lbl_summary.configure(text=f"📍 {total_wps} tọa độ | 🗺️ {s_map} | ⚔️ Auto Đánh: {'Bật' if stage.get('auto_attack', True) else 'Tắt'}")

        if not wps:
            empty_box = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            empty_box.pack(fill="x", pady=16)
            ctk.CTkLabel(
                empty_box,
                text=f"📍 Chưa có tọa độ nào trong map '{s_map}'.\n👉 Vào game chạy tới bãi farm và bấm [F8] hoặc gõ X, Y để thêm mốc!",
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8",
                justify="center"
            ).pack()
            return

        for idx, wp in enumerate(wps, start=1):
            is_last = (idx == total_wps)
            wp_map = wp.get("map", "")
            is_diff_map = bool(wp_map and s_map and normalize_map_name(wp_map) != normalize_map_name(s_map))

            card = ctk.CTkFrame(
                scroll_frame,
                fg_color=("gray95", "#3f1c1c" if is_diff_map else ("#0f2347" if is_last else "#1e293b")),
                corner_radius=6,
                height=30
            )
            card.pack(fill="x", padx=2, pady=1)

            step_text = f"#{idx:02d}"
            badge_color = "#f87171" if is_diff_map else ("#10b981" if is_last else "#38bdf8")
            ctk.CTkLabel(
                card,
                text=step_text,
                width=32,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=badge_color
            ).pack(side="left", padx=(6, 2))

            coord_str = f"({wp.get('x', 0)}, {wp.get('y', 0)})"
            ctk.CTkLabel(
                card,
                text=coord_str,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=65,
                anchor="w"
            ).pack(side="left", padx=(2, 4))

            desc = wp.get("desc", "")
            if is_diff_map:
                desc = f"{desc} [⚠️ Khác map: {wp_map}]"
            elif is_last and stage.get("auto_attack", True):
                if not desc:
                    desc = "Đích Farm [⚔️ Auto Đánh]"
                elif "[⚔️" not in desc:
                    desc = f"{desc} [⚔️ Auto Đánh]"
            elif not desc:
                desc = "Điểm trung gian"

            ctk.CTkLabel(
                card,
                text=desc,
                font=ctk.CTkFont(size=11),
                anchor="w",
                text_color="#fca5a5" if is_diff_map else ("#f8fafc" if is_last else "#cbd5e1")
            ).pack(side="left", fill="x", expand=True, padx=2)

            btn_try = ctk.CTkButton(
                card,
                text="🎯 Đi thử",
                width=50,
                height=22,
                fg_color="#0284c7",
                hover_color="#0369a1",
                font=ctk.CTkFont(size=10),
                command=lambda x=wp.get('x'), y=wp.get('y'), m=s_map: self._on_try_single_coord(x, y, m)
            )
            btn_try.pack(side="right", padx=(2, 4))

            btn_del = ctk.CTkButton(
                card,
                text="🗑️",
                width=24,
                height=22,
                fg_color="#b91c1c",
                hover_color="#991b1b",
                font=ctk.CTkFont(size=10),
                command=lambda s_idx=stage_idx, wp_idx=idx-1: self._delete_coord_from_stage(s_idx, wp_idx)
            )
            btn_del.pack(side="right", padx=(2, 2))

            if idx < total_wps:
                btn_down = ctk.CTkButton(
                    card,
                    text="⬇️",
                    width=24,
                    height=22,
                    fg_color="#475569",
                    hover_color="#334155",
                    font=ctk.CTkFont(size=10),
                    command=lambda s_idx=stage_idx, wp_idx=idx-1: self._move_coord(s_idx, wp_idx, 1)
                )
                btn_down.pack(side="right", padx=(2, 0))

            if idx > 1:
                btn_up = ctk.CTkButton(
                    card,
                    text="⬆️",
                    width=24,
                    height=22,
                    fg_color="#475569",
                    hover_color="#334155",
                    font=ctk.CTkFont(size=10),
                    command=lambda s_idx=stage_idx, wp_idx=idx-1: self._move_coord(s_idx, wp_idx, -1)
                )
                btn_up.pack(side="right", padx=(2, 0))

    def _refresh_stage_waypoints(self, stage_idx: int):
        """Cập nhật lại danh sách hiển thị tọa độ cho mốc stage_idx"""
        if 0 <= stage_idx < len(self.stage_tab_refs):
            refs = self.stage_tab_refs[stage_idx]
            scroll_wps = refs.get("scroll_wps")
            lbl_summary = refs.get("lbl_summary")
            if scroll_wps and lbl_summary:
                self._render_stage_waypoints_into_scroll(stage_idx, scroll_wps, lbl_summary)

    def _on_stage_tab_switched(self):
        """Kích hoạt khi người dùng nhấn đổi tab mốc level"""
        active_title = self.stage_tabview.get()
        for idx, refs in enumerate(self.stage_tab_refs):
            if refs.get("tab_title") == active_title:
                self.current_stage_idx = idx
                self._update_stage_banner()
                break

    def _update_stage_banner(self):
        if not (0 <= self.current_stage_idx < len(self.level_stages)):
            return
        stage = self.level_stages[self.current_stage_idx]
        name = stage.get("name", f"Chặng {self.current_stage_idx+1}")
        s_map = stage.get("map", "Lorencia")
        min_l = stage.get("min_level", 1)
        max_l = stage.get("max_level", 400)
        wps_count = len(stage.get("waypoints", []))

        if not self.is_running and hasattr(self, "lbl_status_badge") and self.lbl_status_badge:
            self.lbl_status_badge.configure(
                text=f"🎯 MỐC {self.current_stage_idx+1}: {name} [{min_l}-{max_l} | {s_map} | {wps_count} mốc]",
                fg_color=("#e2e8f0", "#1e293b")
            )

    def _add_new_stage(self):
        last_max = self.level_stages[-1].get("max_level", 400) if self.level_stages else 0
        new_min = last_max + 1
        new_max = new_min + 50
        new_stage = {
            "name": f"Chặng {len(self.level_stages)+1}",
            "map": "Lorencia",
            "min_level": new_min,
            "max_level": new_max,
            "auto_attack": True,
            "auto_warp": True,
            "waypoints": []
        }
        self.level_stages.append(new_stage)
        self._rebuild_all_stage_tabs(select_idx=len(self.level_stages) - 1)
        self.log(f"[➕ THÊM MỐC] Đã tạo mốc mới: '{new_stage['name']}' (Level {new_min} -> {new_max}).")

    def _delete_stage(self, stage_idx: int):
        if len(self.level_stages) <= 1:
            messagebox.showwarning("Không thể xóa", "Phải giữ lại ít nhất 1 mốc level trong kế hoạch!")
            return
        stage = self.level_stages[stage_idx]
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa mốc '{stage.get('name')}' khỏi danh sách?"):
            del self.level_stages[stage_idx]
            new_select = max(0, stage_idx - 1)
            self._rebuild_all_stage_tabs(select_idx=new_select)
            self.log(f"[🗑️ ĐÃ XÓA MỐC] Đã xóa mốc level #{stage_idx+1}.")

    def _on_add_coord_to_stage(self, stage_idx: int, ent_x, ent_y, ent_desc):
        x_str = ent_x.get().strip()
        y_str = ent_y.get().strip()
        if not x_str or not y_str:
            messagebox.showwarning("Chưa nhập tọa độ", "Vui lòng nhập đầy đủ tọa độ X và Y!")
            return
        try:
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            messagebox.showerror("Sai định dạng", "Tọa độ X và Y phải là số nguyên!")
            return

        desc = ent_desc.get().strip()
        stage = self.level_stages[stage_idx]
        wps = stage.setdefault("waypoints", [])
        if not desc:
            desc = f"Mốc #{len(wps)+1}"

        wps.append({
            "x": x,
            "y": y,
            "desc": desc,
            "map": stage.get("map", "Lorencia"),
            "time": time.strftime("%H:%M:%S")
        })
        ent_x.delete(0, "end")
        ent_y.delete(0, "end")
        ent_desc.delete(0, "end")
        self._refresh_stage_waypoints(stage_idx)
        self.log(f"[➕ THÊM TỌA ĐỘ] Đã thêm ({x}, {y}) vào mốc '{stage['name']}'.")

    def _capture_ram_coord_to_stage(self, stage_idx: int, from_hotkey: bool = False):
        """Lấy tọa độ nhân vật hiện tại từ RAM đưa vào mốc level stage_idx"""
        # Nếu người dùng đang đứng ở cửa sổ game nào, tự động chọn client đó
        try:
            import ctypes
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            fg_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(fg_pid))
            for c in getattr(self, "clients", []):
                if (c.hwnd == fg_hwnd or c.pid == fg_pid.value) and self.selected_client != c:
                    self._select_client(c)
                    break
        except Exception:
            pass

        if not self.selected_client:
            if getattr(self, "clients", []):
                self._select_client(self.clients[0])
            else:
                msg = "Chưa tìm thấy client game nào! Vui lòng khởi động game và bấm 'Quét lại client'."
                if from_hotkey:
                    self.log(f"[!] [F5] {msg}")
                else:
                    messagebox.showwarning("Chưa chọn Client", msg)
                return

        # Đọc RAM trực tiếp từ PID của nhân vật qua IL2CPP Offsets
        state = ProcessMemoryReader.read_live_state(self.selected_client.pid)
        cur_x = None
        cur_y = None
        map_name = getattr(self.selected_client, "map_name", "Unknown")

        if state:
            map_id, m_name, cx, cy, _, _ = state
            if cx is not None and cy is not None and (0 <= cx <= 255) and (0 <= cy <= 255):
                cur_x, cur_y = cx, cy
                if m_name and m_name != "Unknown":
                    map_name = m_name
                    self.selected_client.map_name = map_name
                self.selected_client.x = cur_x
                self.selected_client.y = cur_y
                if hasattr(self, "metric_coord"):
                    self.metric_coord.configure(text=f"({cur_x}, {cur_y})")
                if hasattr(self, "metric_map"):
                    self.metric_map.configure(text=f"{map_name}")

        # Fallback nếu RAM read tức thời chưa có nhưng client đã lưu tọa độ chu kỳ trước
        if cur_x is None or cur_y is None:
            if getattr(self.selected_client, "x", None) is not None and getattr(self.selected_client, "y", None) is not None:
                cur_x = self.selected_client.x
                cur_y = self.selected_client.y

        if cur_x is None or cur_y is None:
            err_msg = f"Không thể đọc tọa độ RAM từ client {self.selected_client.char_name} (PID: {self.selected_client.pid}). Hãy đảm bảo nhân vật đã đăng nhập vào thế giới game!"
            if from_hotkey:
                self.log(f"[!] [F8] {err_msg}")
            else:
                messagebox.showerror("Lỗi RAM", err_msg)
            return

        if not (0 <= stage_idx < len(self.level_stages)):
            return

        stage = self.level_stages[stage_idx]
        wps = stage.setdefault("waypoints", [])
        wps.append({
            "x": cur_x,
            "y": cur_y,
            "desc": f"Mốc #{len(wps)+1} (F8)",
            "map": map_name,
            "time": time.strftime("%H:%M:%S")
        })
        try:
            if winsound:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        # Cập nhật hiển thị lên ô nhập X, Y của tab để người dùng nhìn thấy
        if 0 <= stage_idx < len(self.stage_tab_refs):
            r = self.stage_tab_refs[stage_idx]
            if "ent_x" in r and "ent_y" in r:
                r["ent_x"].delete(0, "end")
                r["ent_x"].insert(0, str(cur_x))
                r["ent_y"].delete(0, "end")
                r["ent_y"].insert(0, str(cur_y))

        self._refresh_stage_waypoints(stage_idx)
        tag = "[📍 F8]" if from_hotkey else "[📍 LẤY RAM]"
        self.log(f"{tag} Đã thêm tọa độ ({cur_x}, {cur_y}) [Bản đồ: {map_name}] vào Tab '{stage['name']}'!")

    def _toggle_trace_recorder(self, stage_idx: int):
        """Bật/Tắt chế độ Ghi Vết Đường Đi Tự Động cho mốc chỉ định"""
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trong danh sách trước!")
            return

        if self.is_recording_trace and self.recording_stage_idx == stage_idx:
            # Dừng ghi vết
            self.is_recording_trace = False
            self.recording_stage_idx = None
            self.last_recorded_pos = None

            if 0 <= stage_idx < len(self.stage_tab_refs):
                btn = self.stage_tab_refs[stage_idx].get("btn_trace_record")
                if btn:
                    btn.configure(text="🔴 Ghi Vết Tự Động", fg_color="#dc2626", hover_color="#b91c1c")

            stage_name = self.level_stages[stage_idx].get("name", f"Mốc {stage_idx+1}")
            wps_cnt = len(self.level_stages[stage_idx].get("waypoints", []))
            self.log(f"[⏹️ ĐÃ DỪNG GHI VẾT] Đã ghi tổng cộng {wps_cnt} mốc đường đi cho '{stage_name}'!")
            try:
                if winsound:
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass
        else:
            # Nếu đang ghi vết mốc khác -> dừng mốc cũ
            if self.is_recording_trace and self.recording_stage_idx is not None:
                old_idx = self.recording_stage_idx
                if 0 <= old_idx < len(self.stage_tab_refs):
                    btn = self.stage_tab_refs[old_idx].get("btn_trace_record")
                    if btn:
                        btn.configure(text="🔴 Ghi Vết Tự Động", fg_color="#dc2626", hover_color="#b91c1c")

            # Bắt đầu ghi vết mới
            self.is_recording_trace = True
            self.recording_stage_idx = stage_idx
            self.last_recorded_pos = None

            st = ProcessMemoryReader.read_live_state(self.selected_client.pid)
            if st and st[2] is not None and st[3] is not None:
                cur_x, cur_y = st[2], st[3]
                map_name = st[1] if st[1] else self.level_stages[stage_idx].get("map", "")
                self.last_recorded_pos = (cur_x, cur_y)
                stage = self.level_stages[stage_idx]
                wps = stage.setdefault("waypoints", [])
                wps.append({
                    "x": cur_x,
                    "y": cur_y,
                    "desc": f"Xuất phát vết (#{len(wps)+1})",
                    "map": map_name,
                    "time": time.strftime("%H:%M:%S")
                })
                self._refresh_stage_waypoints(stage_idx)

            if 0 <= stage_idx < len(self.stage_tab_refs):
                btn = self.stage_tab_refs[stage_idx].get("btn_trace_record")
                if btn:
                    btn.configure(text="⏹️ DỪNG GHI VẾT", fg_color="#ea580c", hover_color="#c2410c")

            stage_name = self.level_stages[stage_idx].get("name", f"Mốc {stage_idx+1}")
            self.log("==================================================")
            self.log(f"🔴 [BẮT ĐẦU GHI VẾT ĐƯỜNG ĐỊ] Cho mốc '{stage_name}'")
            self.log(f"   Hãy mở game và điều khiển nhân vật chạy từ điểm xuất phát tới bãi farm...")
            self.log(f"   Mỗi khi nhân vật di chuyển 2 ô, ứng dụng sẽ tự động ghi 1 vết tọa độ!")
            self.log("==================================================")
            try:
                if winsound:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def _delete_coord_from_stage(self, stage_idx: int, wp_idx: int):
        wps = self.level_stages[stage_idx].get("waypoints", [])
        if 0 <= wp_idx < len(wps):
            del wps[wp_idx]
            self._refresh_stage_waypoints(stage_idx)

    def _delete_all_coords_from_stage(self, stage_idx: int):
        if not (0 <= stage_idx < len(self.level_stages)):
            return
        stage = self.level_stages[stage_idx]
        wps = stage.get("waypoints", [])
        if not wps:
            messagebox.showinfo("Thông báo", "Danh sách tọa độ của mốc này đang trống!")
            return
        if messagebox.askyesno("Xác nhận xóa hết", f"Bạn có chắc muốn xóa toàn bộ {len(wps)} tọa độ của mốc '{stage.get('name')}'?"):
            stage["waypoints"] = []
            self._refresh_stage_waypoints(stage_idx)
            self.log(f"[🗑️ ĐÃ XÓA TỌA ĐỘ] Đã xóa hết tọa độ của mốc '{stage.get('name')}'. Hãy bấm F5 để lưu lại tọa độ mới!")

    def _move_coord(self, stage_idx: int, wp_idx: int, delta: int):
        wps = self.level_stages[stage_idx].get("waypoints", [])
        new_idx = wp_idx + delta
        if 0 <= new_idx < len(wps):
            wps[wp_idx], wps[new_idx] = wps[new_idx], wps[wp_idx]
            self._refresh_stage_waypoints(stage_idx)

    # --------------------------------------------------------------------------
    # F8 Hotkey Global Listener
    # --------------------------------------------------------------------------
    def _start_f8_hotkey_listener(self):
        """Lắng nghe phím nóng F8 toàn màn hình bằng Win32 GetAsyncKeyState"""
        def listener():
            import ctypes
            user32 = ctypes.windll.user32
            VK_F8 = 0x77
            self.log("[⌨️ PHÍM NÓNG F8] Luồng lắng nghe phím F8 toàn màn hình đã được kích hoạt!")
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
                            self.log("[⌨️ PHÍM NÓNG F8] Đã phát hiện nút F8 được nhấn!")
                            self.after(0, self._on_f8_hotkey_pressed)
                except Exception:
                    pass

        threading.Thread(target=listener, daemon=True).start()

    def _on_toggle_f8_hotkey(self):
        self.hotkey_enabled = bool(self.sw_hotkey_f8.get())
        st = "BẬT" if self.hotkey_enabled else "TẮT"
        self.log(f"[⌨️ PHÍM NÓNG] Đã {st} phím tắt F8 toàn màn hình.")

    def _on_f8_hotkey_pressed(self):
        """Kích hoạt khi người dùng nhấn F8 ở bất kỳ cửa sổ nào trong game"""
        self._capture_ram_coord_to_stage(self.current_stage_idx, from_hotkey=True)

    # --------------------------------------------------------------------------
    # Map Operations from Stage Tabs
    # --------------------------------------------------------------------------
    def _on_warp_only_from_combo(self, cmb):
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trước!")
            return
        target_map = cmb.get().strip()
        if not target_map:
            messagebox.showwarning("Chưa chọn Map", "Vui lòng chọn bản đồ!")
            return

        pid = self.selected_client.pid
        def worker():
            self.log(f"[🌐 MOVE MAP] Đang gửi lệnh '/m {target_map}' cho client PID {pid}...")
            try:
                nav = MegNavigator(pid)
                ok = nav.warp_to_map(target_map, log_callback=self.log)
                if ok:
                    self.log(f"[✔] Đã đổi sang bản đồ '{target_map}' thành công!")
                else:
                    self.log("[!] Chuyển map kết thúc hoặc đã ở sẵn map này.")
            except Exception as ex:
                self.log(f"[❌ LỖI] {ex}")
        threading.Thread(target=worker, daemon=True).start()

    def _on_quick_add_map_from_combo(self, cmb):
        map_name = cmb.get().strip()
        if not map_name:
            messagebox.showwarning("Chưa nhập tên", "Vui lòng nhập tên bản đồ trước!")
            return

        current_popular = list(meg_navigator.POPULAR_MAPS)
        for existing in current_popular:
            if existing.strip().lower() == map_name.lower():
                messagebox.showinfo("Bản đồ đã tồn tại", f"Bản đồ '{existing}' đã có trong danh sách!")
                cmb.set(existing)
                return

        current_popular.append(map_name)
        ok = save_all_maps(current_popular)
        if ok:
            self._update_all_map_comboboxes(current_popular, selected_name=map_name)
            self.log(f"[💾 ĐÃ LƯU MAP] Đã thêm '{map_name}' vào file .ini/.txt!")
            messagebox.showinfo("Đã lưu Bản Đồ", f"Đã thêm '{map_name}' vào danh sách và lưu tự động vào file maps.ini & maps.txt!")

    # --------------------------------------------------------------------------
    # Navigation Worker Threads (Single Stage & Autonomous Level Roadmap)
    # --------------------------------------------------------------------------
    def _on_stop_navigation(self):
        """Dừng khẩn cấp điều hướng"""
        self.log("[⏹] Yêu cầu dừng điều hướng... Đang dừng ngay lập tức.")
        self.stop_event.set()
        self.is_running = False
        self.btn_level_start.configure(state="normal")
        self.btn_level_stop.configure(state="disabled")
        self.lbl_status_badge.configure(text="🟠 ĐÃ DỪNG", fg_color=("#fed7aa", "#9a3412"))

    def _update_progress_ui(self, prog: float, remaining: int, current_coord: tuple):
        self.prog_bar.set(prog)
        pct = int(prog * 100)
        self.lbl_prog_pct.configure(text=f"{pct}%")
        self.metric_coord.configure(text=f"({current_coord[0]}, {current_coord[1]})")
        self.metric_dist.configure(text=f"{remaining} ô")

    def _on_nav_finished(self, success: bool):
        self.is_running = False
        self.btn_level_start.configure(state="normal")
        self.btn_level_stop.configure(state="disabled")
        if success:
            self.lbl_status_badge.configure(text="🟢 ĐÃ TỚI ĐÍCH", fg_color=("#bbf7d0", "#166534"))
            self.prog_bar.set(1.0)
            self.lbl_prog_pct.configure(text="100%")
            self.metric_dist.configure(text="0 ô")
        else:
            self.lbl_status_badge.configure(text="⚪ KẾT THÚC", fg_color=("#e2e8f0", "#1e293b"))

    def _on_try_single_coord(self, x: int, y: int, target_map: str):
        """Đi thử tới một tọa độ riêng lẻ trong danh sách"""
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trước!")
            return

        pid = self.selected_client.pid
        angle = self.slider_angle.get()
        self.is_running = True
        self.stop_event.clear()
        self.btn_level_start.configure(state="disabled")
        self.btn_level_stop.configure(state="normal")
        self.lbl_status_badge.configure(text=f"🔵 ĐI TỚI ({x}, {y})", fg_color=("#bfdbfe", "#1e3a8a"))

        def worker():
            try:
                self.log(f"[🎯 ĐI THỬ] Bắt đầu di chuyển tới ({x}, {y}) trên map '{target_map}'...")
                nav = MegNavigator(pid, camera_angle_deg=angle)
                if target_map:
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if normalize_map_name(target_map) != normalize_map_name(cur_m):
                        nav.warp_to_map(target_map, log_callback=self.log, stop_event=self.stop_event)
                        time.sleep(1.0)

                def prog_cb(prog: float, rem: int, cur_coord: tuple):
                    self.after(0, lambda: self._update_progress_ui(prog, rem, cur_coord))

                nav.navigate_continuous(
                    x, y,
                    arrival_radius=1,
                    log_callback=self.log,
                    stop_event=self.stop_event,
                    progress_callback=prog_cb,
                    stride_interval=0.85,
                    use_micro_sync=False
                )
                self.after(0, lambda: self._on_nav_finished(True))
            except Exception as ex:
                self.log(f"[❌ LỖI] {ex}")
                self.after(0, lambda: self._on_nav_finished(False))

        self.nav_thread = threading.Thread(target=worker, daemon=True)
        self.nav_thread.start()

    def _on_start_single_stage(self, stage_idx: int):
        """Chạy riêng mốc level này (đổi map và chạy qua các tọa độ) mà không cần chờ level"""
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 client game trong danh sách trước!")
            return
        if not (0 <= stage_idx < len(self.level_stages)):
            return

        stage = self.level_stages[stage_idx]
        stg_name = stage.get("name", f"Chặng {stage_idx+1}")
        stg_map = stage.get("map", "Lorencia")
        wps = stage.get("waypoints", [])
        auto_att = stage.get("auto_attack", True)
        auto_warp = stage.get("auto_warp", True)

        pid = self.selected_client.pid
        hwnd = self.selected_client.hwnd
        char_name = self.selected_client.char_name
        angle = self.slider_angle.get()

        self.is_running = True
        self.stop_event.clear()
        self.btn_level_start.configure(state="disabled")
        self.btn_level_stop.configure(state="normal")
        self.lbl_status_badge.configure(text=f"🔵 CHẠY MỐC: {stg_name}", fg_color=("#bfdbfe", "#1e3a8a"))

        def worker():
            try:
                self.log("==================================================")
                self.log(f"▶️ BẮT ĐẦU CHẠY RIÊNG MỐC: {stg_name}")
                self.log(f"   Nhân vật: {char_name} (PID: {pid}) | Bản đồ: {stg_map}")
                self.log(f"   Số tọa độ: {len(wps)} | Auto Đánh: {'Bật' if auto_att else 'Tắt'}")
                self.log("==================================================")

                nav = MegNavigator(pid, camera_angle_deg=angle)

                # 1. Đổi map nếu cần
                if auto_warp and stg_map:
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if normalize_map_name(stg_map) != normalize_map_name(cur_m):
                        self.log(f"[➔] Đang đổi sang bản đồ '{stg_map}'...")
                        self.after(0, lambda: self.lbl_status_badge.configure(text=f"🟡 ĐỔI MAP {stg_map}...", fg_color=("#fef08a", "#854d0e")))
                        warp_ok = nav.warp_to_map(stg_map, log_callback=self.log, stop_event=self.stop_event)
                        if self.stop_event.is_set():
                            return
                        time.sleep(1.0)

                if self.stop_event.is_set():
                    return

                # 2. Di chuyển lần lượt qua các tọa độ
                if wps:
                    wp_coords = [(w["x"], w["y"]) for w in wps]
                    self.log(f"[🚶] Di chuyển qua {len(wp_coords)} mốc tọa độ...")

                    def prog_cb(prog: float, rem: int, cur_coord: tuple, cur_pt=1, total_pts=1):
                        self.after(0, lambda: self._update_progress_ui(prog, rem, cur_coord))

                    nav.navigate_multi_points(
                        waypoints=wp_coords,
                        arrival_radius=1,
                        intermediate_radius=1,
                        auto_attack_on_arrival=auto_att,
                        log_callback=self.log,
                        stop_event=self.stop_event,
                        progress_callback=prog_cb,
                        stride_interval=0.85,
                        use_micro_sync=False
                    )
                else:
                    self.log("[ℹ️] Mốc này không có tọa độ trung gian.")
                    if auto_att:
                        self.log("[⚔️] Tự động bật Auto Đánh (MuHelper)...")
                        meg_navigator.toggle_auto_attack_via_sendmessage(hwnd)

                self.log(f"[✔] Đã hoàn thành điều hướng cho mốc '{stg_name}'!")
                self.after(0, lambda: self._on_nav_finished(True))
            except Exception as ex:
                self.log(f"[❌ LỖI] {ex}")
                self.after(0, lambda: self._on_nav_finished(False))

        self.nav_thread = threading.Thread(target=worker, daemon=True)
        self.nav_thread.start()

    def _sync_all_stages_from_ui(self):
        """Đồng bộ toàn bộ dữ liệu từ các ô nhập trên các tab vào self.level_stages"""
        for r in getattr(self, "stage_tab_refs", []):
            idx = r.get("stage_idx")
            if idx is not None and 0 <= idx < len(self.level_stages):
                stg = self.level_stages[idx]
                if "ent_name" in r:
                    stg["name"] = r["ent_name"].get().strip()
                if "ent_min" in r:
                    try:
                        stg["min_level"] = int(r["ent_min"].get().strip())
                    except ValueError:
                        pass
                if "ent_max" in r:
                    try:
                        stg["max_level"] = int(r["ent_max"].get().strip())
                    except ValueError:
                        pass
                if "cmb_map" in r:
                    stg["map"] = r["cmb_map"].get().strip()
                if "chk_auto_warp" in r:
                    stg["auto_warp"] = bool(r["chk_auto_warp"].get())
                if "chk_auto_attack" in r:
                    stg["auto_attack"] = bool(r["chk_auto_attack"].get())

    def _on_start_level_route_navigation(self):
        """Bắt đầu điều hướng tự động lần lượt qua các mốc level theo tiến trình"""
        if not self.selected_client:
            messagebox.showwarning("Chưa chọn Client", "Vui lòng chọn 1 nhân vật trong danh sách bên trên trước!")
            return
        if not self.level_stages:
            messagebox.showwarning("Chưa có mốc nào", "Kế hoạch lộ trình chưa có mốc level nào!")
            return

        # Đồng bộ các ô cấu hình đang hiển thị trên giao diện vào danh sách mốc
        self._sync_all_stages_from_ui()

        pid = self.selected_client.pid
        hwnd = self.selected_client.hwnd
        char_name = self.selected_client.char_name
        angle = self.slider_angle.get()

        self.is_running = True
        self.stop_event.clear()

        self.btn_level_start.configure(state="disabled")
        self.btn_level_stop.configure(state="normal")

        def level_worker():
            try:
                # Đọc Level hiện tại từ RAM (ưu tiên title và RAM 0x030 chuẩn MEGAMU)
                cur_lvl = ProcessMemoryReader.read_character_level(pid)
                if cur_lvl is None:
                    cur_lvl = self.selected_client.level or 1
                else:
                    self.selected_client.level = cur_lvl

                self.log("==================================================")
                self.log("🚀 BẮT ĐẦU ĐIỀU HƯỚNG TỰ ĐỘNG THEO CÁC MỐC LEVEL")
                self.log(f"   Nhân vật: {char_name} (PID: {pid}) | Level thực tế: {cur_lvl}")
                self.log(f"   Tổng số mốc level cấu hình: {len(self.level_stages)}")
                self.log("==================================================")

                # Tìm chặng khởi đầu phù hợp với Level hiện tại
                start_stage_idx = None
                for i, stg in enumerate(self.level_stages):
                    min_l = stg.get("min_level", 1)
                    max_l = stg.get("max_level", 400)
                    if min_l <= cur_lvl <= max_l:
                        start_stage_idx = i
                        break

                if start_stage_idx is None:
                    for i, stg in enumerate(self.level_stages):
                        if cur_lvl <= stg.get("max_level", 400):
                            start_stage_idx = i
                            break

                if start_stage_idx is None:
                    start_stage_idx = len(self.level_stages) - 1
                    self.log(f"[⚠️] Level hiện tại ({cur_lvl}) đã vượt qua tất cả các mốc. Chạy mốc cuối: '{self.level_stages[start_stage_idx].get('name')}'")
                else:
                    stg_init = self.level_stages[start_stage_idx]
                    self.log(f"🎯 [MỐC KHỞI ĐẦU] Khớp Level {cur_lvl} -> Chạy Mốc #{start_stage_idx+1}: '{stg_init.get('name')}' (Từ Lv {stg_init.get('min_level')} đến {stg_init.get('max_level')})")

                current_idx = start_stage_idx

                while current_idx < len(self.level_stages) and not self.stop_event.is_set():
                    stg = self.level_stages[current_idx]
                    stg_name = stg.get("name", f"Chặng {current_idx+1}")
                    stg_map = stg.get("map", "Lorencia")
                    min_l = stg.get("min_level", 1)
                    max_l = stg.get("max_level", 400)
                    wps = stg.get("waypoints", [])
                    auto_att = stg.get("auto_attack", True)
                    auto_warp = stg.get("auto_warp", True)

                    # Tự động nhảy Tab giao diện sang mốc đang chạy
                    self.current_stage_idx = current_idx
                    if current_idx < len(self.stage_tab_refs):
                        tab_t = self.stage_tab_refs[current_idx]["tab_title"]
                        self.after(0, lambda t=tab_t: self.stage_tabview.set(t))

                    self.after(0, lambda idx=current_idx, name=stg_name: self.lbl_status_badge.configure(
                        text=f"🔵 MỐC {idx+1}: {name}", fg_color=("#bfdbfe", "#1e3a8a")
                    ))

                    self.log(f"\n--------------------------------------------------")
                    self.log(f"▶️ [BẮT ĐẦU MỐC {current_idx+1}/{len(self.level_stages)}] {stg_name}")
                    self.log(f"   Khoảng Level: {min_l} -> {max_l} | Bản đồ: {stg_map}")
                    self.log(f"--------------------------------------------------")

                    nav = MegNavigator(pid, camera_angle_deg=angle)

                    # 1. Đổi Map nếu cần
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if auto_warp and stg_map and normalize_map_name(stg_map) != normalize_map_name(cur_m):
                        self.log(f"[➔] Mốc yêu cầu bản đồ '{stg_map}' (Hiện tại đang ở '{cur_m}'). Đang đổi map...")
                        self.after(0, lambda m=stg_map: self.lbl_status_badge.configure(text=f"🟡 ĐỔI MAP {m}...", fg_color=("#fef08a", "#854d0e")))

                        warp_ok = nav.warp_to_map(stg_map, log_callback=self.log, stop_event=self.stop_event)
                        
                        # Xử lý trường hợp chưa đủ điều kiện đổi map (Ví dụ Devias cần tối thiểu Lv 40, hoặc thiếu Zen)
                        retry_count = 0
                        while not warp_ok and not self.stop_event.is_set():
                            cur_st = nav.get_live_state()
                            cur_m = cur_st[1] if cur_st else ""
                            if normalize_map_name(stg_map) == normalize_map_name(cur_m):
                                warp_ok = True
                                break

                            c_lvl = ProcessMemoryReader.read_character_level(pid) or 0
                            retry_count += 1
                            if retry_count == 1:
                                self.log(f"[⚠️ CHƯA ĐỔI ĐƯỢC MAP] Nhân vật Level {c_lvl} chưa thể qua '{stg_map}'.")
                                self.log(f"   💡 Lưu ý: Map yêu cầu cấp độ tối thiểu (Devias: Lv 40, Lost Tower: Lv 80...) hoặc Zen.")
                                self.log(f"   ➔ Hệ thống sẽ tiếp tục duy trì Farm tại '{cur_m}' tới khi đủ điều kiện đổi map...")

                            if auto_att:
                                h_st = ProcessMemoryReader.read_helper_state(pid)
                                if not h_st or h_st[0] == 0:
                                    nav.enable_auto_attack(log_callback=self.log)

                            for _ in range(6):
                                if self.stop_event.is_set():
                                    break
                                time.sleep(1.0)

                            if self.stop_event.is_set():
                                break

                            new_lvl = ProcessMemoryReader.read_character_level(pid) or 0
                            if new_lvl > c_lvl or new_lvl >= min_l:
                                self.log(f"[➔] Thử gửi lại lệnh đổi map sang '{stg_map}' (Level hiện tại: {new_lvl})...")
                                warp_ok = nav.warp_to_map(stg_map, log_callback=self.log, stop_event=self.stop_event)

                    if self.stop_event.is_set():
                        break

                    # 2. Di chuyển theo lần lượt các tọa độ của mốc
                    cur_st = nav.get_live_state()
                    cur_m = cur_st[1] if cur_st else ""
                    if stg_map and normalize_map_name(stg_map) != normalize_map_name(cur_m):
                        self.log(f"[⚠️] Nhân vật vẫn đang ở '{cur_m}' (Chưa vào '{stg_map}'). Bỏ qua chạy tọa độ mốc.")
                    elif wps:
                        wp_coords = [(w["x"], w["y"]) for w in wps]
                        self.log(f"[🚶] Bắt đầu di chuyển qua {len(wp_coords)} mốc tọa độ trên '{stg_map}'...")

                        def stage_prog_cb(overall_prog: float, rem_dist: int, current_coord: tuple, cur_pt_idx=1, total_pts=1):
                            def _upd():
                                self.prog_bar.set(overall_prog)
                                pct = int(overall_prog * 100)
                                self.lbl_prog_pct.configure(text=f"{pct}%")
                                self.metric_coord.configure(text=f"({current_coord[0]}, {current_coord[1]})")
                                self.metric_dist.configure(text=f"{rem_dist} ô")
                                self.lbl_status_badge.configure(
                                    text=f"🔵 MỐC {current_idx+1} ({cur_pt_idx}/{total_pts})",
                                    fg_color=("#bfdbfe", "#1e3a8a")
                                )
                            self.after(0, _upd)

                        nav.navigate_multi_points(
                            waypoints=wp_coords,
                            arrival_radius=1,
                            intermediate_radius=1,
                            auto_attack_on_arrival=auto_att,
                            log_callback=self.log,
                            stop_event=self.stop_event,
                            progress_callback=stage_prog_cb,
                            stride_interval=0.85,
                            use_micro_sync=False
                        )
                    else:
                        self.log("[ℹ️] Mốc này không có tọa độ trung gian.")
                        if auto_att:
                            h_st = ProcessMemoryReader.read_helper_state(pid)
                            if not h_st or h_st[0] == 0:
                                self.log("[⚔️] Đang bật Auto Đánh (MuHelper)...")
                                nav.enable_auto_attack(log_callback=self.log)

                    if self.stop_event.is_set():
                        break

                    # 3. Vòng lặp giám sát Level (Farm quái & Kiểm tra đạt mốc tiếp theo)
                    self.log(f"[👀 BẮT ĐẦU FARM & GIÁM SÁT] Đang farm tại {stg_name}. Chờ đạt Level > {max_l} để tự chuyển chặng...")
                    self.after(0, lambda: self.lbl_status_badge.configure(
                        text=f"⚔️ ĐANG FARM MỐC {current_idx+1}", fg_color=("#bbf7d0", "#14532d")
                    ))

                    stage_leveled_up = False
                    stage_reset_detected = False
                    while not self.stop_event.is_set():
                        time.sleep(2.0)
                        now_l = ProcessMemoryReader.read_character_level(pid)
                        if now_l is not None:
                            self.selected_client.level = now_l
                            if now_l > max_l:
                                self.log(f"\n🎉🎉🎉 [LÊN CẤP!] Nhân vật đã đạt Level {now_l} (Vượt mốc tối đa {max_l} của '{stg_name}')!")
                                stage_leveled_up = True
                                break
                            elif now_l < min_l - 5:
                                self.log(f"\n🔄 [PHÁT HIỆN RESET] Level nhân vật giảm xuống {now_l} (< {min_l})! Đang quay lại mốc phù hợp...")
                                stage_reset_detected = True
                                break

                    if self.stop_event.is_set():
                        break

                    if stage_reset_detected:
                        h_st = ProcessMemoryReader.read_helper_state(pid)
                        if h_st and h_st[0] == 1:
                            self.log("[⚔️] Tắt Auto Đánh để quay lại mốc khởi đầu sau reset...")
                            meg_navigator.toggle_auto_attack_via_sendmessage(hwnd)
                            time.sleep(0.5)

                        new_start = None
                        for i, st in enumerate(self.level_stages):
                            if st.get("min_level", 1) <= now_l <= st.get("max_level", 400):
                                new_start = i
                                break
                        current_idx = new_start if new_start is not None else 0
                        continue

                    if stage_leveled_up:
                        h_st = ProcessMemoryReader.read_helper_state(pid)
                        if h_st and h_st[0] == 1:
                            self.log("[⚔️] Tắt Auto Đánh để chuẩn bị sang mốc tiếp theo...")
                            meg_navigator.toggle_auto_attack_via_sendmessage(hwnd)
                            time.sleep(0.5)

                        current_idx += 1
                        if current_idx < len(self.level_stages):
                            next_name = self.level_stages[current_idx].get("name")
                            self.log(f"[➔➔] Đang chuyển tiếp sang Mốc {current_idx+1}: '{next_name}'...")
                            time.sleep(1.0)
                        else:
                            self.log("🏆 [HOÀN TẤT TẤT CẢ MỐC] Chúc mừng! Đã hoàn thành toàn bộ các mốc level trong kế hoạch!")
                            try:
                                if winsound:
                                    winsound.MessageBeep(winsound.MB_OK)
                            except Exception:
                                pass
                            self.after(0, lambda: self._on_level_route_finished(True))
                            return

                self.after(0, lambda: self._on_level_route_finished(False))

            except Exception as ex:
                self.log(f"[❌ LỖI LỘ TRÌNH LEVEL] {ex}")
                self.after(0, lambda: self._on_level_route_finished(False))

        self.nav_thread = threading.Thread(target=level_worker, daemon=True)
        self.nav_thread.start()

    def _on_level_route_finished(self, success: bool):
        self.is_running = False
        self.btn_level_start.configure(state="normal")
        self.btn_level_stop.configure(state="disabled")

        if success:
            self.lbl_status_badge.configure(text="🎉 HOÀN THÀNH TẤT CẢ MỐC", fg_color=("#bbf7d0", "#166534"))
            self.prog_bar.set(1.0)
            self.lbl_prog_pct.configure(text="100%")
            self.metric_dist.configure(text="0 ô")
        else:
            self.lbl_status_badge.configure(text="⚪ KẾT THÚC", fg_color=("#e2e8f0", "#1e293b"))

    def _save_level_plan_to_file(self):
        """Lưu toàn bộ kế hoạch mốc level ra file JSON"""
        if not self.level_stages:
            messagebox.showwarning("Kế hoạch trống", "Chưa có mốc level nào để lưu!")
            return
        os.makedirs("plans", exist_ok=True)
        file_path = filedialog.asksaveasfilename(
            initialdir="plans",
            title="Lưu Kế Hoạch Mốc Level",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            try:
                save_data = {
                    "version": "2.0",
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stages": self.level_stages
                }
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                self.log(f"[💾 ĐÃ LƯU KẾ HOẠCH] Đã lưu {len(self.level_stages)} mốc vào file: {os.path.basename(file_path)}")
                messagebox.showinfo("Đã Lưu", f"Lưu thành công {len(self.level_stages)} mốc level vào:\n{file_path}")
            except Exception as ex:
                self.log(f"[❌ LỖI LƯU] {ex}")
                messagebox.showerror("Lỗi", f"Không thể lưu file:\n{ex}")

    def _load_level_plan_from_file(self):
        """Nạp kế hoạch mốc level từ file JSON"""
        os.makedirs("plans", exist_ok=True)
        file_path = filedialog.askopenfilename(
            initialdir="plans",
            title="Nạp Kế Hoạch Mốc Level",
            filetypes=[("JSON files", "*.json")]
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
                    messagebox.showerror("Sai định dạng", "File JSON không đúng cấu trúc kế hoạch mốc level!")
                    return
                self._rebuild_all_stage_tabs(0)
                self.log(f"[📂 ĐÃ TẢI KẾ HOẠCH] Nạp thành công {len(self.level_stages)} mốc từ: {os.path.basename(file_path)}")
                messagebox.showinfo("Thành công", f"Đã nạp thành công {len(self.level_stages)} mốc level từ file!")
            except Exception as ex:
                self.log(f"[❌ LỖI NẠP] {ex}")
                messagebox.showerror("Lỗi", f"Không thể đọc file:\n{ex}")

    def _on_close(self):
        """Xử lý dọn dẹp tài nguyên khi tắt ứng dụng"""
        self.hotkey_stop_event.set()
        self.stop_event.set()
        self.destroy()

def main():
    app = MegNavigatorGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
