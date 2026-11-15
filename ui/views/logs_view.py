# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - BATCHED LOGS & TOOLS VIEW
Cửa sổ nhật ký hệ thống tối ưu hiệu năng cao (Batched Log Rendering) và sắp xếp cửa sổ game.
"""

from typing import Callable, Optional, List, Tuple
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory

class LogsAndToolsView(ctk.CTkFrame):
    """View nhật ký hệ thống siêu tốc và công cụ quản trị cửa sổ game."""

    def __init__(
        self,
        parent,
        on_arrange_windows: Optional[Callable[[str], None]] = None,
        on_clear_logs: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_arrange_windows = on_arrange_windows
        self.on_clear_logs = on_clear_logs

        self.auto_scroll_var = ctk.BooleanVar(value=True)

        self._build_toolbar()
        self._build_terminal()

    def _build_toolbar(self):
        """Thanh tác vụ sắp xếp cửa sổ và công cụ log."""
        tb = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, height=44, corner_radius=4)
        tb.pack(fill="x", padx=12, pady=(10, 8))
        tb.pack_propagate(False)

        # Cột Trái: Bộ sắp xếp cửa sổ MEGAMU
        left_f = ctk.CTkFrame(tb, fg_color="transparent")
        left_f.pack(side="left", fill="y", padx=8)

        ctk.CTkLabel(left_f, text="📐 Sắp xếp cửa sổ:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 6), pady=11)

        for preset in ["2x2", "3x2", "3x3", "4x2"]:
            ctk.CTkButton(
                left_f,
                text=preset,
                font=Fonts.CAPTION,
                fg_color=Colors.BG_CARD,
                hover_color=Colors.BG_CARD_HOVER,
                width=42,
                height=26,
                corner_radius=2,
                command=lambda p=preset: self._handle_arrange(p)
            ).pack(side="left", padx=2, pady=9)

        # Cột Phải: Xóa log & Auto scroll
        right_f = ctk.CTkFrame(tb, fg_color="transparent")
        right_f.pack(side="right", fill="y", padx=8)

        ctk.CTkCheckBox(
            right_f,
            text="Tự cuộn theo dòng mới",
            variable=self.auto_scroll_var,
            font=Fonts.CAPTION,
            checkbox_width=16,
            checkbox_height=16
        ).pack(side="right", padx=(6, 4), pady=11)

        ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("trash", color="#ffffff", size=(12, 12)),
            compound="left",
            text="Xóa nhật ký",
            font=Fonts.CAPTION,
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            width=90,
            height=26,
            corner_radius=2,
            command=self._handle_clear_logs
        ).pack(side="right", padx=(0, 6), pady=9)

    def _build_terminal(self):
        """Khung hiển thị Text Log dạng Terminal."""
        self.text_box = ctk.CTkTextbox(
            self,
            font=Fonts.MONO,
            fg_color=Colors.BG_SURFACE,
            text_color=Colors.TEXT_MAIN,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=4,
            wrap="none"
        )
        self.text_box.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Đặt các tag màu sắc cho log terminal
        self.text_box.tag_config("INFO", foreground="#38bdf8")
        self.text_box.tag_config("SUCCESS", foreground="#22c55e")
        self.text_box.tag_config("WARN", foreground="#f59e0b")
        self.text_box.tag_config("ERROR", foreground="#ef4444")
        self.text_box.tag_config("TIME", foreground="#64748b")

    def append_batched_logs(self, logs: List[Tuple[str, str, Optional[int], str]]):
        """Nạp danh sách log dồn toa vào Text Box theo lô (Zero-Lag Batching)."""
        if not logs:
            return

        self.text_box.configure(state="normal")
        for time_str, level, slot, text in logs:
            prefix = f"[{time_str}] "
            slot_tag = f"[SLOT {slot}] " if slot else ""
            line = f"{prefix}{slot_tag}[{level}] {text}\n"

            tag = level if level in ("INFO", "SUCCESS", "WARN", "ERROR") else "INFO"
            self.text_box.insert("end", line, tag)

        # Giới hạn tối đa 600 dòng để chống tràn bộ nhớ và giật layout Tkinter
        try:
            line_count = int(self.text_box.index("end-1c").split(".")[0])
            if line_count > 600:
                delete_to = f"{line_count - 500}.0"
                self.text_box.delete("1.0", delete_to)
        except Exception:
            pass

        if self.auto_scroll_var.get():
            self.text_box.see("end")

        self.text_box.configure(state="disabled")

    def clear(self):
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.configure(state="disabled")

    def _handle_arrange(self, layout: str):
        if self.on_arrange_windows:
            self.on_arrange_windows(layout)

    def _handle_clear_logs(self):
        self.clear()
        if self.on_clear_logs:
            self.on_clear_logs()
