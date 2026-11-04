"""
UI View: RamView (Quản lý Tab Tối ưu hóa RAM).
Chuyên trách dựng thẻ KPI RAM, bảng tiến trình client MEGAMU, và khung log RAM.
"""

from typing import Any
import customtkinter as ctk
from ui.components.icons import UiIconFactory
from ui.components.option_menu import ModernOptionMenu


class RamView:
    """Builder cho Tab Tối ưu hóa RAM."""

    def __init__(self, master_app: Any, parent_panel: ctk.CTkFrame):
        self.app = master_app
        self.panel = parent_panel

    def create_kpi_card(self, parent: ctk.CTkFrame, title: str, initial_val: str, color: str):
        card = ctk.CTkFrame(parent, corner_radius=0, fg_color="#181c26", border_width=1, border_color="#2b3244")
        lbl_t = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#94a3b8")
        lbl_t.pack(anchor="w", padx=12, pady=(6, 0))
        lbl_v = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=color)
        lbl_v.pack(anchor="w", padx=12, pady=(1, 6))
        card.value_label = lbl_v
        return card

    def build(self):
        """Xây dựng giao diện Tab Tối ưu hóa RAM tích hợp."""
        tr = getattr(self.app, "_tr", lambda k: k)
        header_card = ctk.CTkFrame(self.panel, fg_color="#181c26", corner_radius=0, border_width=1, border_color="#2b3244")
        header_card.pack(fill="x", padx=14, pady=(12, 6))

        inner_h = ctk.CTkFrame(header_card, fg_color="transparent")
        inner_h.pack(fill="both", expand=True, padx=14, pady=10)

        left_h = ctk.CTkFrame(inner_h, fg_color="transparent")
        left_h.pack(side="left", fill="y")

        title_lbl = ctk.CTkLabel(
            left_h,
            text="⚡ MEGAMU RAM OPTIMIZER PRO",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            left_h,
            text="Tự động thu hồi bộ nhớ Working Set • Tiết kiệm ~70% RAM từ ~1GB còn ~200MB - 300MB / client",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        right_h = ctk.CTkFrame(inner_h, fg_color="transparent")
        right_h.pack(side="right", fill="y")

        self.app.ram_auto_var = ctk.BooleanVar(value=self.app.ram_manager.auto_trim_enabled if self.app.ram_manager else False)
        self.app.ram_auto_switch = ctk.CTkSwitch(
            right_h,
            text=tr("ram_auto_trim"),
            variable=self.app.ram_auto_var,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f8fafc",
            progress_color="#10b981",
            command=self.app._on_ram_auto_switch_toggled
        )
        self.app.ram_auto_switch.pack(side="left", padx=(0, 10))

        self.app.ram_intervals_map = {
            "1 Phút": 60,
            "2 Phút": 120,
            "3 Phút": 180,
            "5 Phút": 300,
            "10 Phút": 600,
            "15 Phút": 900,
            "30 Phút": 1800
        }
        curr_sec = self.app.ram_manager.interval_seconds if self.app.ram_manager else 180
        curr_label = "3 Phút"
        for k, s in self.app.ram_intervals_map.items():
            if s == curr_sec:
                curr_label = k
                break

        self.app.ram_interval_combo = ModernOptionMenu(
            right_h,
            values=list(self.app.ram_intervals_map.keys()),
            width=110,
            height=28,
            fg_color="#141722",
            border_color="#2b3244",
            hover_color="#222736",
            command=self.app._on_ram_interval_changed,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.app.ram_interval_combo.set(curr_label)
        self.app.ram_interval_combo.pack(side="left")

        stats_frame = ctk.CTkFrame(self.panel, fg_color="transparent")
        stats_frame.pack(fill="x", padx=14, pady=4)

        self.app.ram_card_clients = self.create_kpi_card(stats_frame, tr("ram_active_clients"), "0 Clients", "#38bdf8")
        self.app.ram_card_clients.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.app.ram_card_cur_ram = self.create_kpi_card(stats_frame, tr("ram_current_ram"), "0 MB", "#f59e0b")
        self.app.ram_card_cur_ram.pack(side="left", fill="both", expand=True, padx=4)

        saved_init = f"{int(self.app.ram_manager.total_saved_mb)} MB" if self.app.ram_manager else "0 MB"
        self.app.ram_card_saved = self.create_kpi_card(stats_frame, tr("ram_total_saved"), saved_init, "#10b981")
        self.app.ram_card_saved.pack(side="left", fill="both", expand=True, padx=(4, 0))

        action_bar = ctk.CTkFrame(self.panel, fg_color="transparent")
        action_bar.pack(fill="x", padx=14, pady=(8, 6))

        self.app.btn_ram_optimize_all = ctk.CTkButton(
            action_bar,
            text=f" {tr('ram_optimize_all_btn')}",
            image=UiIconFactory.get("bolt", color="#ffffff", size=(15, 15)),
            compound="left",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=0,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.app.trim_ram_now_ui
        )
        self.app.btn_ram_optimize_all.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.app.btn_ram_refresh = ctk.CTkButton(
            action_bar,
            text=f" {tr('refresh_games')}",
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(13, 13)),
            compound="left",
            width=130,
            height=38,
            corner_radius=0,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2b3244",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.refresh_ram_tab_stats
        )
        self.app.btn_ram_refresh.pack(side="right")

        body_split = ctk.CTkFrame(self.panel, fg_color="transparent")
        body_split.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        left_body = ctk.CTkFrame(body_split, fg_color="#141722", corner_radius=0, border_width=1, border_color="#202430")
        left_body.pack(side="left", fill="both", expand=True, padx=(0, 6))

        c_hdr = ctk.CTkFrame(left_body, fg_color="#181c26", height=28, corner_radius=0)
        c_hdr.pack(fill="x", padx=4, pady=(4, 2))

        ctk.CTkLabel(c_hdr, text="PID", width=70, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(10, 4))
        ctk.CTkLabel(c_hdr, text="Cửa Sổ / Nhân Vật", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(c_hdr, text="RAM Sử Dụng", width=105, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkLabel(c_hdr, text="Thao Tác", width=95, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(4, 8))

        self.app.ram_clients_scroll = ctk.CTkScrollableFrame(left_body, fg_color="transparent")
        self.app.ram_clients_scroll.pack(fill="both", expand=True, padx=2, pady=2)

        right_body = ctk.CTkFrame(body_split, fg_color="#141722", corner_radius=0, border_width=1, border_color="#202430", width=380)
        right_body.pack(side="right", fill="both", padx=(6, 0))
        right_body.pack_propagate(False)

        log_hdr = ctk.CTkFrame(right_body, fg_color="#181c26", height=28, corner_radius=0)
        log_hdr.pack(fill="x", padx=4, pady=(4, 2))

        ctk.CTkLabel(log_hdr, text="📝 Nhật Ký Hoạt Động RAM", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#38bdf8").pack(side="left", padx=10)

        self.app.ram_log_txt = ctk.CTkTextbox(
            right_body,
            fg_color="transparent",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#cbd5e1"
        )
        self.app.ram_log_txt.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.app.append_ram_log("🟢 RAM Optimizer đã tích hợp sẵn sàng.")

