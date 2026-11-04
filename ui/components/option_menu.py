"""
Modern Option Menu for MEGAMU Auto Train Dashboard.
Custom full-width dropdown replacement for CTkOptionMenu with dark themed popup and smooth event handling.
"""

import time
from typing import Optional, List, Callable, Any
import customtkinter as ctk

from .icons import UiIconFactory


class ModernOptionMenu(ctk.CTkFrame):
    """
    Dropdown menu phong cách hiện đại thay thế CTkOptionMenu:
    - Popup mở rộng 100% khớp đúng chiều rộng nút bấm (full-width), không bị ngắn cụt.
    - Giao diện đen sang trọng đồng bộ Dark mode, không bị viền trắng 3D của Windows Menu.
    - Tự động đóng khi click ra ngoài hoặc chọn xong.
    - Tích hợp 2-way binding với StringVar và hàm callback.
    """
    def __init__(
        self,
        master,
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        command: Optional[Callable[[str], Any]] = None,
        width: int = 220,
        height: int = 32,
        font: Optional[ctk.CTkFont] = None,
        fg_color: str = "#181c26",
        border_color: str = "transparent",
        hover_color: str = "#222736",
        text_color: str = "#f1f5f9",
        on_open: Optional[Callable[[], Any]] = None,
        **kwargs
    ):
        # Bỏ qua các tham số riêng của CTkOptionMenu nếu truyền vào
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)

        c_radius = kwargs.pop("corner_radius", 5)
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=fg_color,
            border_width=1,
            border_color="#242b3a",
            corner_radius=c_radius,
            **kwargs
        )
        self.pack_propagate(False)

        self._base_fg = fg_color
        self._hover_bg = hover_color
        self._text_color = text_color
        self._font = font or ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self._req_width = width
        self._req_height = height
        self._last_close_time = 0.0
        self.on_open = on_open

        self.values = list(values) if values else ["--"]
        self.variable = variable or ctk.StringVar(value=self.values[0] if self.values else "--")
        self.command = command
        self._popup = None

        # Text hiển thị giá trị hiện tại
        self._lbl = ctk.CTkLabel(
            self,
            text=self.variable.get(),
            font=self._font,
            text_color=self._text_color,
            anchor="w"
        )
        self._lbl.pack(side="left", fill="both", expand=True, padx=(10, 4))

        # Vector Icon Chevron Down
        self._chevron = ctk.CTkLabel(
            self,
            text="",
            image=UiIconFactory.get("chevron_down", color="#94a3b8", size=(10, 10))
        )
        self._chevron.pack(side="right", padx=(0, 10))

        # Đồng bộ khi biến StringVar thay đổi từ bên ngoài
        try:
            self.variable.trace_add("write", lambda *_: self._on_var_changed())
        except Exception:
            pass

        # Gán sự kiện click & hover cho toàn bộ frame và label
        for w in (self, self._lbl, self._chevron):
            w.bind("<Button-1>", lambda e: self._toggle_popup())
            w.bind("<Enter>", lambda e: self._on_enter())
            w.bind("<Leave>", lambda e: self._on_leave())
            w.configure(cursor="hand2")

    def _on_enter(self):
        self.configure(fg_color=self._hover_bg)

    def _on_leave(self):
        if not self._popup or not self._popup.winfo_exists():
            self.configure(fg_color=self._base_fg)

    def _on_var_changed(self):
        val = self.variable.get() if self.variable else "--"
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text=val)

    def _toggle_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
            return
        if time.time() - self._last_close_time < 0.15:
            return
        self._open_popup()

    def _open_popup(self):
        if callable(self.on_open):
            try:
                self.on_open()
            except Exception:
                pass
        self._close_popup()
        self.update_idletasks()
        rx = self.winfo_rootx()
        ry = self.winfo_rooty() + self.winfo_height() + 2
        w = max(self.winfo_width(), self._req_width)

        num_items = len(self.values)
        item_h = 30
        h = max(38, min(240, num_items * item_h + 8))

        # Kiểm tra tràn đáy màn hình
        try:
            screen_h = self.winfo_screenheight()
            if ry + h > screen_h - 40:
                ry = max(10, self.winfo_rooty() - h - 2)
        except Exception:
            pass

        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{rx}+{ry}")

        outer = ctk.CTkFrame(
            self._popup,
            fg_color="#141722",
            border_width=1,
            border_color="#242b3a",
            corner_radius=0
        )
        outer.pack(fill="both", expand=True)

        container = outer
        if num_items > 7:
            container = ctk.CTkScrollableFrame(outer, fg_color="transparent", height=h - 8, corner_radius=0)
            container.pack(fill="both", expand=True, padx=2, pady=2)

        cur_val = self.variable.get()
        for val in self.values:
            is_active = (val == cur_val)
            btn = ctk.CTkButton(
                container,
                text=f"  {val}",
                anchor="w",
                height=item_h - 2,
                corner_radius=0,
                font=self._font,
                fg_color="#1c2436" if is_active else "transparent",
                hover_color="#222838",
                text_color="#38bdf8" if is_active else "#f1f5f9",
                command=lambda v=val: self._on_select(v)
            )
            btn.pack(fill="x", padx=3, pady=1)

        # Lắng nghe click bên ngoài thông qua root toplevel
        try:
            top_win = self.winfo_toplevel()
            self._popup.bind("<FocusOut>", lambda e: self._close_popup())
            self._popup.after(80, lambda: top_win.bind("<Button-1>", self._on_global_click, add="+"))
        except Exception:
            pass

    def _on_global_click(self, event):
        if not self._popup or not self._popup.winfo_exists():
            return
        try:
            px = self._popup.winfo_rootx()
            py = self._popup.winfo_rooty()
            pw = self._popup.winfo_width()
            ph = self._popup.winfo_height()
            if not (px <= event.x_root <= px + pw and py <= event.y_root <= py + ph):
                self._close_popup()
        except Exception:
            self._close_popup()

    def _close_popup(self):
        self._last_close_time = time.time()
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        self._on_leave()

    def _on_select(self, value: str):
        self.set(value)
        self._close_popup()
        if self.command:
            self.command(value)

    def set(self, value: str):
        self.variable.set(value)
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text=value)

    def get(self) -> str:
        return self.variable.get()

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs.pop("values"))
        if "variable" in kwargs:
            self.variable = kwargs.pop("variable")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists() and self.variable:
                self._lbl.configure(text=self.variable.get())
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "fg_color" in kwargs:
            self._base_fg = kwargs.pop("fg_color")
            super().configure(fg_color=self._base_fg)
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists():
                self._lbl.configure(text_color=self._text_color)
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)
        if kwargs:
            super().configure(**kwargs)

