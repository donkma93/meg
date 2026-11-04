"""
UI View: AccountsView (Quản lý 9 Slots Tài Khoản Chính).
Chuyên trách tạo bảng slot, nút Master Run/Stop, và toolbar điều khiển chính.
"""

from typing import Any
import customtkinter as ctk


class AccountsView:
    """Builder và quản trị giao diện Tab Tài Khoản chính."""

    def __init__(self, master_app: Any, parent_panel: ctk.CTkFrame):
        self.app = master_app
        self.panel = parent_panel

    def get_slot_count(self) -> int:
        """Lấy số lượng slots hiện tại."""
        return len(getattr(self.app, "controllers", []))

    def update_master_button(self, is_running: bool):
        """Cập nhật nút Master Run/Stop."""
        btn = getattr(self.app, "btn_master_run", None)
        if btn and btn.winfo_exists():
            if is_running:
                btn.configure(
                    text="⏹ DỪNG TẤT CẢ",
                    fg_color="#dc2626",
                    hover_color="#b91c1c"
                )
            else:
                btn.configure(
                    text="▶ CHẠY TẤT CẢ",
                    fg_color="#059669",
                    hover_color="#047857"
                )

