"""
UI View: AutoLoginView (Quản lý Tab Auto Login & Accounts Registry).
Chuyên trách hiển thị bảng tài khoản, toolbar thao tác, và nhật ký autologin.
"""

from typing import Any
import os
import customtkinter as ctk
from ui.components.icons import UiIconFactory


class AutoLoginView:
    """Builder cho Tab Quản lý tài khoản & AutoLogin."""

    def __init__(self, master_app: Any, parent_panel: ctk.CTkFrame):
        self.app = master_app
        self.panel = parent_panel

    def build(self):
        """Xây dựng giao diện Tab Quản lý tài khoản & AutoLogin thẳng vào game."""
        header_card = ctk.CTkFrame(self.panel, fg_color="#181c26", corner_radius=0, border_width=1, border_color="#2b3244")
        header_card.pack(fill="x", padx=14, pady=(10, 6))

        inner_h = ctk.CTkFrame(header_card, fg_color="transparent")
        inner_h.pack(fill="both", expand=True, padx=14, pady=8)

        left_h = ctk.CTkFrame(inner_h, fg_color="transparent")
        left_h.pack(side="left", fill="y")

        title_lbl = ctk.CTkLabel(
            left_h,
            text="🔑 MEGAMU AUTO LOGIN • QUẢN LÝ TÀI KHOẢN & LOGIN THẲNG VÀO GAME",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#c084fc"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            left_h,
            text="Khởi chạy client & Tự động đăng nhập vào nhân vật bằng Token Registry (Bỏ qua hoàn toàn giao diện chọn thủ công)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        right_h = ctk.CTkFrame(inner_h, fg_color="transparent")
        right_h.pack(side="right", fill="y")

        self.app.lbl_autologin_exe = ctk.CTkLabel(
            right_h,
            text=f"📁 Exe: {os.path.basename(getattr(self.app.account_mgr, 'exe_path', '') or 'MEGAMU.exe')}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#cbd5e1"
        )
        self.app.lbl_autologin_exe.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            right_h,
            text="📁 Đổi Exe",
            width=75,
            height=28,
            corner_radius=0,
            fg_color="#272f3d",
            hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.app.choose_exe_path_dialog
        ).pack(side="left")

        # ACTION TOOLBAR
        toolbar_card = ctk.CTkFrame(self.panel, fg_color="#141722", corner_radius=0, border_width=1, border_color="#202430")
        toolbar_card.pack(fill="x", padx=14, pady=(2, 6))

        inner_tb = ctk.CTkFrame(toolbar_card, fg_color="transparent")
        inner_tb.pack(fill="both", expand=True, padx=10, pady=8)

        left_tb = ctk.CTkFrame(inner_tb, fg_color="transparent")
        left_tb.pack(side="left", fill="y")

        self.app.btn_autologin_all = ctk.CTkButton(
            left_tb,
            image=UiIconFactory.get("key", color="#ffffff", size=(13, 13)),
            compound="left",
            text="🚀 MỞ & LOGIN TẤT CẢ",
            height=30,
            corner_radius=0,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            border_width=1,
            border_color="#a78bfa",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.batch_launch_all_accounts
        )
        self.app.btn_autologin_all.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            left_tb,
            image=UiIconFactory.get("refresh", color="#38bdf8", size=(12, 12)),
            compound="left",
            text="🔄 Đọc từ Registry",
            height=30,
            corner_radius=0,
            fg_color="#0f172a",
            hover_color="#1e293b",
            border_width=1,
            border_color="#38bdf8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.import_accounts_from_registry_ui
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            left_tb,
            image=UiIconFactory.get("plus", color="#4ade80", size=(12, 12)),
            compound="left",
            text="➕ Thêm Tài Khoản",
            height=30,
            corner_radius=0,
            fg_color="#0f172a",
            hover_color="#1e293b",
            border_width=1,
            border_color="#22c55e",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.open_add_account_dialog
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            left_tb,
            text="☑️ Chọn/Bỏ Tất Cả",
            height=30,
            corner_radius=0,
            fg_color="#1e2433",
            hover_color="#2b3244",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.app.toggle_all_accounts_ui
        ).pack(side="left", padx=(0, 6))

        right_tb = ctk.CTkFrame(inner_tb, fg_color="transparent")
        right_tb.pack(side="right", fill="y")

        ctk.CTkLabel(
            right_tb,
            text="Giãn cách:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        ).pack(side="left", padx=(0, 4))

        ctk.CTkEntry(
            right_tb,
            textvariable=self.app.autologin_delay_var,
            width=45,
            height=28,
            corner_radius=0,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            justify="center"
        ).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            right_tb,
            text="giây",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        ).pack(side="left", padx=(0, 10))

        self.app.autologin_status_lbl = ctk.CTkLabel(
            right_tb,
            text="Sẵn sàng",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#22c55e"
        )
        self.app.autologin_status_lbl.pack(side="left")

        # BODY CONTAINER (TABLE + RUNTIME LOG)
        body_box = ctk.CTkFrame(self.panel, fg_color="transparent")
        body_box.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # TABLE CONTAINER
        table_container = ctk.CTkFrame(body_box, fg_color="#12151e", corner_radius=0, border_width=1, border_color="#202430")
        table_container.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tbl_hdr = ctk.CTkFrame(table_container, fg_color="#171b26", height=32, corner_radius=0)
        tbl_hdr.pack(fill="x", padx=2, pady=2)
        tbl_hdr.pack_propagate(False)

        ctk.CTkLabel(tbl_hdr, text="BẬT", width=42, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(6, 2))
        ctk.CTkLabel(tbl_hdr, text="STT", width=40, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=2)
        ctk.CTkLabel(tbl_hdr, text="TÀI KHOẢN", width=125, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkLabel(tbl_hdr, text="NHÂN VẬT LOGIN", width=135, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkLabel(tbl_hdr, text="SERVER", width=95, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkLabel(tbl_hdr, text="GÁN VÀO SLOT", width=115, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkLabel(tbl_hdr, text="THAO TÁC", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=6, fill="x", expand=True)

        self.app.autologin_scroll = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.app.autologin_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # LOG CONTAINER (BÊN PHẢI)
        log_box = ctk.CTkFrame(body_box, fg_color="#12151e", corner_radius=0, border_width=1, border_color="#202430", width=340)
        log_box.pack(side="right", fill="y", padx=(6, 0))
        log_box.pack_propagate(False)

        log_hdr = ctk.CTkFrame(log_box, fg_color="#171b26", height=32, corner_radius=0)
        log_hdr.pack(fill="x", padx=2, pady=2)
        log_hdr.pack_propagate(False)

        ctk.CTkLabel(
            log_hdr,
            text="📋 NHẬT KÝ AUTO LOGIN",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#c084fc"
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            log_hdr,
            text="Xóa",
            width=45,
            height=22,
            corner_radius=0,
            fg_color="#1e2433",
            hover_color="#2b3244",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.clear_autologin_log
        ).pack(side="right", padx=6)

        self.app.autologin_log_txt = ctk.CTkTextbox(
            log_box,
            fg_color="#0a0c12",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="Consolas", size=10),
            wrap="word"
        )
        self.app.autologin_log_txt.pack(fill="both", expand=True, padx=4, pady=4)

        self.app.refresh_autologin_table()
        self.app._autologin_table_initialized = True

