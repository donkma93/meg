"""
Modern Option Menu for MEGAMU Auto Train Dashboard.
Custom full-width dropdown replacement for CTkOptionMenu with dark themed popup, smooth event handling,
and non-blocking interaction.
"""

import time
import tkinter as tk
from typing import Optional, List, Callable, Any, Tuple
import customtkinter as ctk

from .icons import UiIconFactory


class ModernOptionMenu(ctk.CTkFrame):
    """
    Dropdown menu phong cách hiện đại thay thế CTkOptionMenu:
    - Popup mở rộng khớp nút bấm hoặc mở rộng tối thiểu 105px để không bị ngắn cụt.
    - Giao diện đen sang trọng đồng bộ Dark mode, không bị viền trắng 3D của Windows Menu.
    - Hiển thị đầy đủ danh sách cấu hình (Config 1..10) trực quan, không cần thanh cuộn che chữ.
    - Tự động đóng khi click ra ngoài hoặc bấm Escape hoặc chọn xong.
    - Tích hợp 2-way binding với StringVar và hàm callback.
    - Xử lý sự kiện click trực tiếp, không bị trễ hoặc nuốt click.
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
        border_color: str = "#242b3a",
        hover_color: str = "#222736",
        text_color: str = "#f1f5f9",
        on_open: Optional[Callable[[], Any]] = None,
        state: str = "normal",
        **kwargs
    ):
        # Bỏ qua các tham số riêng của CTkOptionMenu nếu truyền vào
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)

        c_radius = kwargs.pop("corner_radius", 4)
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=fg_color,
            border_width=1,
            border_color=border_color,
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
        self._state = state
        self._last_close_time = 0.0
        self._after_bind_id = None
        self._global_listeners: List[Tuple[Any, str, str]] = []
        self.on_open = on_open

        self.values = list(values) if values else ["--"]
        self.variable = variable or ctk.StringVar(value=self.values[0] if self.values else "--")
        self.command = command
        self._popup: Optional[tk.Toplevel] = None

        # Text hiển thị giá trị hiện tại
        self._lbl = ctk.CTkLabel(
            self,
            text=self.variable.get(),
            font=self._font,
            text_color=self._text_color,
            anchor="w"
        )
        self._lbl.pack(side="left", fill="both", expand=True, padx=(8, 2))

        # Vector Icon Chevron Down
        self._chevron = ctk.CTkLabel(
            self,
            text="",
            image=UiIconFactory.get("chevron_down", color="#94a3b8", size=(9, 9))
        )
        self._chevron.pack(side="right", padx=(0, 6))

        # Đồng bộ khi biến StringVar thay đổi từ bên ngoài
        try:
            self.variable.trace_add("write", lambda *_: self._on_var_changed())
        except Exception:
            pass

        # Gán sự kiện click & hover cho toàn bộ frame và label
        cursor_style = "hand2" if self._state != "disabled" else "arrow"
        for w in (self, self._lbl, self._chevron):
            w.bind("<Button-1>", self._on_trigger_click)
            w.bind("<Enter>", lambda e: self._on_enter())
            w.bind("<Leave>", lambda e: self._on_leave())
            try:
                w.configure(cursor=cursor_style)
            except Exception:
                pass

        if self._state == "disabled":
            self._apply_disabled_style()

    def _apply_disabled_style(self):
        self.configure(fg_color="#12151d", border_color="#1a1e28")
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text_color="#475569")
        for w in (self, self._lbl, self._chevron):
            try:
                w.configure(cursor="arrow")
            except Exception:
                pass

    def _apply_normal_style(self):
        self.configure(fg_color=self._base_fg, border_color="#242b3a")
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text_color=self._text_color)
        for w in (self, self._lbl, self._chevron):
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    def _on_enter(self):
        if self._state == "disabled":
            return
        self.configure(fg_color=self._hover_bg)

    def _on_leave(self):
        if self._state == "disabled":
            return
        if not self._popup or not self._popup.winfo_exists():
            self.configure(fg_color=self._base_fg)

    def _on_var_changed(self):
        val = self.variable.get() if self.variable else "--"
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text=val)

    def _on_trigger_click(self, event=None):
        if self._state == "disabled":
            return "break"
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
            return "break"
        if time.time() - self._last_close_time < 0.12:
            return "break"
        self._open_popup()
        return "break"

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
        # Tối thiểu 105px để đảm bảo Config 1..10 hiển thị rộng rãi, không bị che chữ
        w = max(self.winfo_width(), self._req_width, 105)

        num_items = len(self.values)
        item_h = 26

        # Nếu danh sách <= 12 mục (ví dụ Config 1..10), hiển thị trực tiếp dạng phẳng không cần thanh cuộn
        if num_items <= 12:
            h = num_items * item_h + 6
            use_scroll = False
        else:
            h = min(320, num_items * item_h + 8)
            use_scroll = True
            w = max(w, 140)

        # Kiểm tra tràn đáy và cạnh màn hình
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            if ry + h > screen_h - 40:
                ry = max(10, self.winfo_rooty() - h - 2)
            if rx + w > screen_w - 10:
                rx = max(10, screen_w - w - 10)
        except Exception:
            pass

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{rx}+{ry}")
        self._popup.lift()

        outer = ctk.CTkFrame(
            self._popup,
            fg_color="#141722",
            border_width=1,
            border_color="#242b3a",
            corner_radius=0
        )
        outer.pack(fill="both", expand=True)

        if use_scroll:
            container = ctk.CTkScrollableFrame(
                outer,
                fg_color="transparent",
                height=h - 8,
                corner_radius=0
            )
            container.pack(fill="both", expand=True, padx=2, pady=2)
        else:
            container = outer

        cur_val = self.variable.get()
        for val in self.values:
            is_active = (val == cur_val)
            row = ctk.CTkFrame(
                container,
                fg_color="#1c2436" if is_active else "transparent",
                corner_radius=3,
                height=item_h - 2,
                cursor="hand2"
            )
            row.pack(fill="x", padx=2, pady=1)
            row.pack_propagate(False)

            lbl = ctk.CTkLabel(
                row,
                text=f"  {val}",
                anchor="w",
                font=self._font,
                text_color="#38bdf8" if is_active else "#f1f5f9",
                cursor="hand2"
            )
            lbl.pack(fill="both", expand=True, padx=4)

            # Đảm bảo hover và click hoạt động mượt mà tức thì 100%
            def _bind_item_events(row_widget, is_act, item_val):
                def _enter(e):
                    row_widget.configure(fg_color="#242d42")
                def _leave(e):
                    row_widget.configure(fg_color="#1c2436" if is_act else "transparent")
                def _click(e):
                    self._on_select(item_val)
                    return "break"

                for target in (row_widget, lbl):
                    target.bind("<Enter>", _enter)
                    target.bind("<Leave>", _leave)
                    target.bind("<Button-1>", _click)

            _bind_item_events(row, is_active, val)

        # Lắng nghe click bên ngoài sau một độ trễ nhỏ để tránh xung đột sự kiện mở
        self._after_bind_id = self.after(50, self._bind_global_listeners)
        self._popup.bind("<Escape>", lambda e: self._close_popup())

    def _bind_global_listeners(self):
        if not self._popup or not self._popup.winfo_exists():
            return
        try:
            # Lắng nghe click bên ngoài trên cả Toplevel hiện tại và cửa sổ Root
            windows_to_bind = {self.winfo_toplevel()}
            try:
                root = self.nametowidget(".")
                if root:
                    windows_to_bind.add(root)
            except Exception:
                pass

            for win in windows_to_bind:
                b1 = win.bind("<Button-1>", self._on_global_click, add="+")
                self._global_listeners.append((win, "<Button-1>", b1))
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
        if self._after_bind_id:
            try:
                self.after_cancel(self._after_bind_id)
            except Exception:
                pass
            self._after_bind_id = None

        for top_w, ev_name, bind_id in self._global_listeners:
            try:
                top_w.unbind(ev_name, bind_id)
            except Exception:
                pass
        self._global_listeners.clear()

        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        self._on_leave()

    def destroy(self):
        self._close_popup()
        super().destroy()

    def _on_select(self, value: str):
        self.set(value)
        self._close_popup()
        if self.command:
            try:
                self.command(value)
            except Exception:
                pass

    def set(self, value: str):
        if self.variable:
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
        if "border_color" in kwargs:
            super().configure(border_color=kwargs.pop("border_color"))
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists():
                self._lbl.configure(text_color=self._text_color)
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            if self._state == "disabled":
                self._apply_disabled_style()
            else:
                self._apply_normal_style()
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)
        if kwargs:
            super().configure(**kwargs)
