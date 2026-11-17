# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - UI TOOLTIP UTILITY
Lightweight, snappy dark theme tooltips for buttons, chips, and icons.
"""

import tkinter as tk
from typing import Optional


class UiTooltip:
    """Lightweight high-performance dark theme tooltip."""

    def __init__(self, widget, text: str, delay_ms: int = 250):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._tip: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None

        if hasattr(self.widget, "bind"):
            try:
                self.widget.bind("<Enter>", self._on_enter, add="+")
                self.widget.bind("<Leave>", self._on_leave, add="+")
                self.widget.bind("<Button-1>", self._on_leave, add="+")
                self.widget.bind("<Destroy>", self._on_destroy, add="+")
            except Exception:
                pass

    def _on_enter(self, event=None):
        self._schedule()

    def _on_leave(self, event=None):
        self._hide()

    def _on_destroy(self, event=None):
        self._hide()

    def _schedule(self):
        self._hide()
        if not self.text:
            return
        try:
            self._after_id = self.widget.after(self.delay_ms, self._show)
        except Exception:
            pass

    def _show(self):
        if not self.widget.winfo_exists():
            return
        try:
            # Tọa độ bên dưới widget
            rx = self.widget.winfo_rootx() + max(0, (self.widget.winfo_width() // 2) - 40)
            ry = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            # Kiểm tra tràn màn hình
            screen_w = self.widget.winfo_screenwidth()
            screen_h = self.widget.winfo_screenheight()

            if ry + 30 > screen_h:
                ry = max(10, self.widget.winfo_rooty() - 32)
            if rx + 180 > screen_w:
                rx = max(10, screen_w - 190)

            self._tip = tk.Toplevel(self.widget)
            self._tip.overrideredirect(True)
            self._tip.attributes("-topmost", True)
            self._tip.geometry(f"+{rx}+{ry}")

            frame = tk.Frame(
                self._tip,
                bg="#090d16",
                highlightthickness=1,
                highlightbackground="#243149",
                highlightcolor="#243149"
            )
            frame.pack(fill="both", expand=True)

            lbl = tk.Label(
                frame,
                text=self.text,
                bg="#090d16",
                fg="#e2e8f0",
                font=("Segoe UI", 9),
                padx=8,
                pady=4,
                justify="left"
            )
            lbl.pack()
        except Exception:
            self._hide()

    def _hide(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def attach_tooltip(widget, text: str, delay_ms: int = 250) -> UiTooltip:
    """Gắn tooltip tự động lên bất kỳ widget nào."""
    return UiTooltip(widget, text, delay_ms)
