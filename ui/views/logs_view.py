# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - BATCHED LOGS & TOOLS VIEW
Terminal-style log console + window arrangement tools.
"""

from typing import Callable, Optional, List, Tuple
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.shell import ToolbarBar, make_action_button, SectionCard


class LogsAndToolsView(ctk.CTkFrame):
    """Batched log console and window layout tools."""

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
        self._line_count = 0

        self._build_header()
        self._build_toolbar()
        self._build_terminal()

    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            head,
            text="Nhật ký hệ thống",
            font=Fonts.SECTION,
            text_color=Colors.TEXT_MAIN
        ).pack(side="left")
        self.lbl_log_count = ctk.CTkLabel(
            head,
            text="0 dòng",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM
        )
        self.lbl_log_count.pack(side="right")

    def _build_toolbar(self):
        tb = ToolbarBar(self, height=48)
        tb.pack(fill="x", padx=12, pady=(4, 8))

        # Sắp xếp cửa sổ đã chuyển lên thanh sticky global.
        # Giữ bản rút gọn ở đây chỉ khi caller vẫn truyền callback.
        if self.on_arrange_windows:
            ctk.CTkLabel(
                tb.left,
                text="📐 Sắp xếp cửa sổ",
                font=Fonts.BODY_BOLD,
                text_color=Colors.TEXT_MUTED
            ).pack(side="left", padx=(0, 8), pady=12)

            for preset in ["2x2", "3x2", "3x3", "4x2", "2x1", "4x3"]:
                make_action_button(
                    tb.left,
                    preset,
                    lambda p=preset: self._handle_arrange(p),
                    tone="neutral",
                    width=48,
                    height=26,
                ).pack(side="left", padx=2, pady=11)
        else:
            ctk.CTkLabel(
                tb.left,
                text="Dùng thanh «Cửa sổ game» phía trên để sắp xếp / đóng game",
                font=Fonts.CAPTION,
                text_color=Colors.TEXT_DIM
            ).pack(side="left", pady=14)

        ctk.CTkCheckBox(
            tb.right,
            text="Tự cuộn",
            variable=self.auto_scroll_var,
            font=Fonts.CAPTION,
            checkbox_width=16,
            checkbox_height=16
        ).pack(side="right", padx=(8, 0), pady=12)

        make_action_button(
            tb.right,
            "Xóa nhật ký",
            self._handle_clear_logs,
            image=UiIconFactory.get("trash", color="#ffffff", size=(12, 12)),
            tone="ghost",
            width=110,
            height=26,
        ).pack(side="right", pady=11)

    def _build_terminal(self):
        card = SectionCard(self)
        card.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        card.configure(fg_color=Colors.BG_SURFACE_ELEVATED)

        self.text_box = ctk.CTkTextbox(
            card.body,
            font=Fonts.MONO,
            fg_color=Colors.BG_INPUT,
            text_color=Colors.TEXT_MAIN,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=Radii.SM,
            wrap="none"
        )
        self.text_box.pack(fill="both", expand=True)
        self.text_box.tag_config("INFO", foreground="#38bdf8")
        self.text_box.tag_config("SUCCESS", foreground="#22c55e")
        self.text_box.tag_config("WARN", foreground="#f59e0b")
        self.text_box.tag_config("WARNING", foreground="#f59e0b")
        self.text_box.tag_config("ERROR", foreground="#ef4444")
        self.text_box.tag_config("TIME", foreground="#64748b")
        self.text_box.configure(state="disabled")

    def append_batched_logs(self, logs: List[Tuple[str, str, Optional[int], str]]):
        if not logs:
            return

        self.text_box.configure(state="normal")
        for time_str, level, slot, text in logs:
            prefix = f"[{time_str}] "
            slot_tag = f"[SLOT {slot}] " if slot else ""
            line = f"{prefix}{slot_tag}[{level}] {text}\n"
            tag = level if level in ("INFO", "SUCCESS", "WARN", "WARNING", "ERROR") else "INFO"
            self.text_box.insert("end", line, tag)
            self._line_count += 1

        try:
            line_count = int(self.text_box.index("end-1c").split(".")[0])
            if line_count > 600:
                delete_to = f"{line_count - 500}.0"
                self.text_box.delete("1.0", delete_to)
                self._line_count = 500
        except Exception:
            pass

        if self.auto_scroll_var.get():
            self.text_box.see("end")

        self.text_box.configure(state="disabled")
        self.lbl_log_count.configure(text=f"{self._line_count} dòng")

    def clear(self):
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.configure(state="disabled")
        self._line_count = 0
        self.lbl_log_count.configure(text="0 dòng")

    def _handle_arrange(self, layout: str):
        if self.on_arrange_windows:
            self.on_arrange_windows(layout)

    def _handle_clear_logs(self):
        self.clear()
        if self.on_clear_logs:
            self.on_clear_logs()
