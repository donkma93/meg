# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - AUTO LOGIN VIEW
Quản lý danh sách tài khoản, khởi chạy đồng loạt và tự động đăng nhập nhanh, mượt mà.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory

class AutoLoginView(ctk.CTkFrame):
    """View quản lý và tự động đăng nhập tài khoản MEGAMU siêu tốc."""

    def __init__(
        self,
        parent,
        account_mgr,
        on_launch_all: Optional[Callable[[], None]] = None,
        on_add_account: Optional[Callable[[], None]] = None,
        on_launch_single: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_delete_selected: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.account_mgr = account_mgr
        self.on_launch_all = on_launch_all
        self.on_add_account = on_add_account
        self.on_launch_single = on_launch_single
        self.on_delete_selected = on_delete_selected

        self.account_rows: List[Dict[str, Any]] = []
        self.selected_category = "Tất cả"

        self._build_toolbar()
        self._build_table()
        self.refresh_table()

    def _build_toolbar(self):
        """Thanh công cụ quản lý tài khoản trên đỉnh."""
        tb = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, height=44, corner_radius=4)
        tb.pack(fill="x", padx=12, pady=(10, 8))
        tb.pack_propagate(False)

        # Cột Trái: Nút thêm tài khoản & xóa
        left_f = ctk.CTkFrame(tb, fg_color="transparent")
        left_f.pack(side="left", fill="y", padx=8)

        ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("plus", color="#ffffff", size=(12, 12)),
            compound="left",
            text="➕ Thêm Tài Khoản",
            font=Fonts.BODY_BOLD,
            fg_color="#065f46",
            hover_color="#047857",
            width=130,
            height=28,
            corner_radius=2,
            command=self._handle_add_account
        ).pack(side="left", padx=(0, 6), pady=8)

        ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("trash", color="#ffffff", size=(12, 12)),
            compound="left",
            text="Xóa Đã Chọn",
            font=Fonts.BODY_BOLD,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            width=110,
            height=28,
            corner_radius=2,
            command=self._handle_delete_selected
        ).pack(side="left", padx=(0, 6), pady=8)

        # Cột Phải: Nút khởi chạy tất cả & Trạng thái
        right_f = ctk.CTkFrame(tb, fg_color="transparent")
        right_f.pack(side="right", fill="y", padx=8)

        self.btn_launch_all = ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("bolt", color="#ffffff", size=(12, 12)),
            compound="left",
            text="🚀 KHỞI CHẠY TẤT CẢ",
            font=Fonts.BODY_BOLD,
            fg_color=Colors.CYAN,
            hover_color="#0284c7",
            text_color="#000000",
            width=160,
            height=28,
            corner_radius=2,
            command=self._handle_launch_all
        )
        self.btn_launch_all.pack(side="right", pady=8)
        self.btn_autologin_all = self.btn_launch_all

        self.status_lbl = ctk.CTkLabel(
            right_f,
            text="Sẵn sàng",
            font=Fonts.BODY,
            text_color=Colors.TEXT_MUTED
        )
        self.status_lbl.pack(side="right", padx=(0, 10), pady=11)

    def _build_table(self):
        """Khung chứa danh sách tài khoản dạng bảng phẳng gọn gàng."""
        # Header bảng
        tbl_hdr = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, height=30, corner_radius=2)
        tbl_hdr.pack(fill="x", padx=12, pady=(0, 4))
        tbl_hdr.pack_propagate(False)

        ctk.CTkLabel(tbl_hdr, text="BẬT", font=Fonts.CAPTION, width=40).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_hdr, text="TÀI KHOẢN (USER)", font=Fonts.CAPTION, width=150, anchor="w").pack(side="left", padx=6)
        ctk.CTkLabel(tbl_hdr, text="NHÂN VẬT", font=Fonts.CAPTION, width=130, anchor="w").pack(side="left", padx=6)
        ctk.CTkLabel(tbl_hdr, text="SERVER", font=Fonts.CAPTION, width=70, anchor="w").pack(side="left", padx=6)
        ctk.CTkLabel(tbl_hdr, text="NHÓM", font=Fonts.CAPTION, width=90, anchor="w").pack(side="left", padx=6)
        ctk.CTkLabel(tbl_hdr, text="TRẠNG THÁI / PID", font=Fonts.CAPTION, anchor="w").pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkLabel(tbl_hdr, text="THAO TÁC", font=Fonts.CAPTION, width=90, anchor="e").pack(side="right", padx=12)

        # Danh sách tài khoản có thể cuộn
        self.scroll_table = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_table.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Khung nhật ký AutoLogin thu gọn ở dưới
        log_frame = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, height=110, corner_radius=2)
        log_frame.pack(fill="x", padx=12, pady=(0, 8))
        log_frame.pack_propagate(False)

        ctk.CTkLabel(log_frame, text="📋 NHẬT KÝ TIẾN TRÌNH ĐĂNG NHẬP (LOGS)", font=Fonts.CAPTION, text_color=Colors.CYAN).pack(anchor="w", padx=8, pady=(4, 2))
        self.autologin_log_txt = ctk.CTkTextbox(log_frame, fg_color=Colors.BG_SURFACE, font=Fonts.CODE, corner_radius=2)
        self.autologin_log_txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def refresh_table(self):
        """Vẽ lại các hàng tài khoản khi danh sách tài khoản thay đổi."""
        for w in self.scroll_table.winfo_children():
            w.destroy()
        self.account_rows.clear()

        if not self.account_mgr or not getattr(self.account_mgr, "accounts", None):
            ctk.CTkLabel(
                self.scroll_table,
                text="Chưa có tài khoản nào được lưu.\nNhấn nút '➕ Thêm Tài Khoản' ở thanh trên để thêm tài khoản MEGAMU!",
                font=Fonts.BODY,
                text_color=Colors.TEXT_DIM,
                justify="center"
            ).pack(pady=40)
            return

        for acc in self.account_mgr.accounts:
            row_frame = ctk.CTkFrame(self.scroll_table, fg_color=Colors.BG_CARD, height=40, corner_radius=2)
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)

            # Checkbox bật/tắt
            enabled_var = ctk.BooleanVar(value=acc.get("enabled", True))
            cb = ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=enabled_var,
                width=24,
                checkbox_width=18,
                checkbox_height=18,
                command=lambda a=acc, v=enabled_var: self._on_toggle_enabled(a, v)
            )
            cb.pack(side="left", padx=(10, 4))

            # Username
            u_name = acc.get("username", "")
            ctk.CTkLabel(
                row_frame,
                text=u_name,
                font=Fonts.BODY_BOLD,
                text_color=Colors.TEXT_MAIN,
                width=150,
                anchor="w"
            ).pack(side="left", padx=6)

            # Character
            c_name = acc.get("character", "---")
            ctk.CTkLabel(
                row_frame,
                text=c_name,
                font=Fonts.BODY,
                text_color=Colors.TEXT_MUTED,
                width=130,
                anchor="w"
            ).pack(side="left", padx=6)

            # Server
            s_num = acc.get("server", 4)
            ctk.CTkLabel(
                row_frame,
                text=f"Server {s_num}",
                font=Fonts.BODY,
                text_color=Colors.PURPLE,
                width=70,
                anchor="w"
            ).pack(side="left", padx=6)

            # Phân loại
            cat = acc.get("category", "Chung")
            ctk.CTkLabel(
                row_frame,
                text=cat,
                font=Fonts.CAPTION,
                text_color=Colors.CYAN,
                width=90,
                anchor="w"
            ).pack(side="left", padx=6)

            # Trạng thái PID
            pid = acc.get("last_pid")
            status_txt = f"PID {pid} (Đang mở)" if pid else "Chưa mở"
            status_color = Colors.GREEN if pid else Colors.TEXT_DIM
            ctk.CTkLabel(
                row_frame,
                text=status_txt,
                font=Fonts.CAPTION,
                text_color=status_color,
                anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=6)

            # Nút chạy lẻ
            btn_single = ctk.CTkButton(
                row_frame,
                text="Mở",
                font=Fonts.CAPTION,
                fg_color=Colors.BG_SURFACE,
                hover_color=Colors.BORDER_CARD,
                width=50,
                height=24,
                corner_radius=2,
                command=lambda a=acc: self._handle_launch_single(a)
            )
            btn_single.pack(side="right", padx=10)

    def _on_toggle_enabled(self, acc: Dict[str, Any], var: ctk.BooleanVar):
        acc["enabled"] = var.get()
        if self.account_mgr:
            self.account_mgr.save_accounts()

    def _handle_add_account(self):
        if self.on_add_account:
            self.on_add_account()

    def _handle_delete_selected(self):
        if self.on_delete_selected:
            self.on_delete_selected()

    def _handle_launch_all(self):
        if self.on_launch_all:
            self.on_launch_all()

    def _handle_launch_single(self, acc: Dict[str, Any]):
        if self.on_launch_single:
            self.on_launch_single(acc)
