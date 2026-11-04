"""
Modern Tooltip System for MEGAMU Auto Train Dashboard.
Provides elegant, screen-boundary-safe dark floating tooltips with smooth hover detection.
"""

from typing import Optional
import tkinter as tk


class ModernToolTip:
    """
    Hệ thống tooltip nổi hiện đại phong cách Dark Theme:
    - Bo góc, viền sắc nét, hiển thị mượt mà không rung lắc.
    - Tự động canh lề và chống tràn màn hình (Screen Boundary Protection).
    - Tự động hủy khi chuột rời khỏi hoặc khi người dùng click chuột.
    - Hỗ trợ cả CustomTkinter lẫn Tkinter thuần.
    """
    def __init__(self, widget, text: str, delay_ms: int = 250):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tipwindow: Optional[tk.Toplevel] = None
        self.after_id = None

        self._bind_events(widget)

    def _bind_events(self, w):
        try:
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<ButtonPress>", self._on_leave, add="+")
            if hasattr(w, "_canvas") and w._canvas:
                w._canvas.bind("<Enter>", self._on_enter, add="+")
                w._canvas.bind("<Leave>", self._on_leave, add="+")
                w._canvas.bind("<ButtonPress>", self._on_leave, add="+")
            if hasattr(w, "_text_label") and w._text_label:
                w._text_label.bind("<Enter>", self._on_enter, add="+")
                w._text_label.bind("<Leave>", self._on_leave, add="+")
                w._text_label.bind("<ButtonPress>", self._on_leave, add="+")
            if hasattr(w, "_lbl") and w._lbl:
                w._lbl.bind("<Enter>", self._on_enter, add="+")
                w._lbl.bind("<Leave>", self._on_leave, add="+")
                w._lbl.bind("<ButtonPress>", self._on_leave, add="+")
        except Exception:
            pass

    def _on_enter(self, event=None):
        self._unschedule()
        if self.text:
            try:
                self.after_id = self.widget.after(self.delay_ms, self._show_tip)
            except Exception:
                pass

    def _on_leave(self, event=None):
        self._unschedule()
        self._hide_tip()

    def _unschedule(self):
        aid = self.after_id
        self.after_id = None
        if aid:
            try:
                self.widget.after_cancel(aid)
            except Exception:
                pass

    def _show_tip(self):
        if not self.text:
            return
        self._hide_tip()
        try:
            root_x = self.widget.winfo_rootx()
            root_y = self.widget.winfo_rooty()
            w_h = self.widget.winfo_height()
            x = root_x + 8
            y = root_y + w_h + 6

            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)

            border_frame = tk.Frame(tw, bg="#334155", bd=1)
            border_frame.pack(fill="both", expand=True)

            inner_frame = tk.Frame(border_frame, bg="#0b0f19")
            inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

            lbl = tk.Label(
                inner_frame,
                text=self.text,
                justify=tk.LEFT,
                bg="#0b0f19",
                fg="#f1f5f9",
                font=("Segoe UI", 9),
                padx=9,
                pady=6
            )
            lbl.pack()

            tw.update_idletasks()
            tip_w = tw.winfo_reqwidth()
            tip_h = tw.winfo_reqheight()
            screen_w = self.widget.winfo_screenwidth()
            screen_h = self.widget.winfo_screenheight()

            if x + tip_w > screen_w - 12:
                x = screen_w - tip_w - 12
            if x < 12:
                x = 12
            if y + tip_h > screen_h - 45:
                y = root_y - tip_h - 6
                if y < 12:
                    y = 12

            tw.wm_geometry(f"+{x}+{y}")
        except Exception:
            self.tipwindow = None

    def _hide_tip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass

    def update_text(self, new_text: str):
        self.text = new_text


def add_tooltip(widget, text: str, delay_ms: int = 250) -> ModernToolTip:
    """Gắn tooltip chỉ dẫn hiện đại vào widget."""
    return ModernToolTip(widget, text, delay_ms=delay_ms)

