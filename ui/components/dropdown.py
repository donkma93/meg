# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - MODERN DROPDOWN COMPONENT (PREMIUM FLAT DESIGN)
Dropdown menu cao cấp phong cách Linear / macOS / Windows 11 Fluent:
- Viền bo kín 100%, không bao giờ bị đứt nét hay hở góc.
- Hiệu ứng Focus Ring 2px màu Cyan phát sáng liền mạch khi mở menu.
- Cửa sổ danh sách bo góc mượt mà với Windows 11 DWM Rounded Corners.
- Các mục thả xuống dạng viên nang (Floating Pills) với hiệu ứng hover mượt mà.
- Mục được chọn hiển thị viên nang phát sáng kèm dấu tích checkmark '✓' màu Cyan.
- Tính toán chiều cao chính xác tuyệt đối, KHÔNG BAO GIỜ bị cắt xén chữ hay mất dòng cuối.
- Tự động lật thông minh lên trên (Flip Upwards) nếu gần đáy màn hình.
- Phân nhóm danh mục trực quan cho các mục [ZEN] và [NGỌC].
- Đóng popup an toàn khi click ra ngoài bằng Bind ID chuyên biệt.
"""

import time
import sys
from typing import Optional, List, Callable, Any
import tkinter as tk
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory


# Hỗ trợ Windows DWM bo góc cửa sổ popup
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


def _apply_dwm_rounding(window):
    """Kích hoạt bo tròn góc cửa sổ chuẩn Windows 11 DWM."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes, c_int, byref
        hwnd = window.winfo_id()
        dwmapi = ctypes.windll.dwmapi
        val = c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            c_int(DWMWA_WINDOW_CORNER_PREFERENCE),
            byref(val),
            ctypes.sizeof(val)
        )
    except Exception:
        pass


class ModernDropdown(tk.Frame):
    """Dropdown menu hiện đại (Zero-Canvas native tk.Frame + tk.Label) chống tràn màn hình."""

    def __init__(
        self,
        master,
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        command: Optional[Callable[[str], Any]] = None,
        width: int = 140,
        height: int = 32,
        font: Optional[Any] = None,
        fg_color: Optional[str] = None,
        border_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        text_color: Optional[str] = None,
        on_open: Optional[Callable[[], Any]] = None,
        popup_min_width: Optional[int] = None,
        **kwargs
    ):
        # Bỏ qua các tham số riêng của CTkOptionMenu / CTkFrame nếu truyền vào
        for k in (
            "button_color", "button_hover_color", "dropdown_fg_color",
            "dropdown_hover_color", "dropdown_text_color", "anchor",
            "corner_radius", "border_width",
        ):
            kwargs.pop(k, None)

        base_fg = fg_color or Colors.BG_SURFACE
        base_border = border_color or Colors.BORDER_CARD
        super().__init__(
            master,
            width=width,
            height=height,
            bg=base_fg,
            bd=0,
            highlightthickness=1,
            highlightbackground=base_border,
            highlightcolor=Colors.BORDER_FOCUS,
            cursor="hand2",
            **kwargs
        )
        self.pack_propagate(False)

        self._base_fg = base_fg
        self._base_border = base_border
        self._hover_bg = hover_color or Colors.BG_CARD_HOVER
        self._text_color = text_color or Colors.TEXT_MAIN
        self._font = font or Fonts.BODY_BOLD
        self._req_width = width
        self._req_height = height
        self._popup_min_width = popup_min_width or max(140, width)
        self._last_close_time = 0.0
        self.on_open = on_open

        self.values = list(values) if values else ["--"]
        self.variable = variable or ctk.StringVar(value=self.values[0] if self.values else "--")
        self.command = command
        self._popup: Optional[tk.Toplevel] = None
        self._global_bind_id: Optional[str] = None
        self._last_text = self.variable.get()

        # Text hiển thị giá trị hiện tại (0 Canvas)
        self._lbl = tk.Label(
            self,
            text=self._last_text,
            font=self._font,
            bg=base_fg,
            fg=self._text_color,
            anchor="w",
            bd=0,
            cursor="hand2",
        )
        self._lbl.pack(side="left", fill="both", expand=True, padx=(8, 2), pady=1)

        # Mũi tên Chevron nhẹ (0 Canvas, 0 CTkImage)
        self._chevron = tk.Label(
            self,
            text="▾",
            font=("Segoe UI", 9),
            bg=base_fg,
            fg="#94a3b8",
            bd=0,
            cursor="hand2",
        )
        self._chevron.pack(side="right", padx=(0, 6), pady=1)

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

    def _apply_surface(self, bg: str, border: str, bw: int = 1):
        super().configure(bg=bg, highlightthickness=bw, highlightbackground=border, highlightcolor=border)
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(bg=bg)
        if hasattr(self, "_chevron") and self._chevron.winfo_exists():
            self._chevron.configure(bg=bg)

    def _on_enter(self):
        if not self._popup or not self._popup.winfo_exists():
            self._apply_surface(self._hover_bg, "#38bdf8", 1)

    def _on_leave(self):
        if not self._popup or not self._popup.winfo_exists():
            self._apply_surface(self._base_fg, self._base_border, 1)

    def _on_var_changed(self):
        val = self.variable.get() if self.variable else "--"
        if val != self._last_text and hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._last_text = val
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

        # Hiệu ứng Active Focus Ring 2px hoàn toàn kín, không hở góc
        self._apply_surface(self._hover_bg, Colors.BORDER_FOCUS, 2)
        try:
            self._chevron.configure(text="▴", fg=Colors.CYAN)
        except Exception:
            pass

        num_items = len(self.values)
        item_h = 28
        item_spacing = 2
        outer_pad = 14  # 6px top + 6px bottom + 2px border

        # Kiểm tra danh mục phân nhóm (ZEN vs NGỌC)
        has_zen = any("[ZEN]" in str(v) for v in self.values)
        has_ngoc = any("[NGỌC]" in str(v) for v in self.values)
        has_groups = has_zen and has_ngoc
        header_extra = 60 if has_groups else 0

        total_content_h = num_items * (item_h + item_spacing) + header_extra + outer_pad

        # Nếu danh sách <= 10 items (như Config 1..10): Hiển thị TRỌN VẸN 100%, không cắt xén
        # Nếu > 10 items: giới hạn tối đa 350px và bật cuộn mượt
        needs_scroll = (total_content_h > 350 or num_items > 11)
        h = min(350, total_content_h) if needs_scroll else total_content_h

        # Tính toán tọa độ hiển thị (Floating gap 4px bên dưới trigger)
        rx = self.winfo_rootx()
        ry = self.winfo_rooty() + self.winfo_height() + 4
        w = max(self.winfo_width(), self._req_width, self._popup_min_width)

        # Kiểm tra tràn lề phải màn hình
        try:
            screen_w = self.winfo_screenwidth()
            if rx + w > screen_w - 12:
                rx = max(10, screen_w - w - 12)
        except Exception:
            pass

        # Kiểm tra tràn đáy màn hình (FLIP UPWARDS nếu chạm đáy)
        try:
            screen_h = self.winfo_screenheight()
            if ry + h > screen_h - 40:
                ry = max(10, self.winfo_rooty() - h - 4)
        except Exception:
            pass

        # Tạo popup bằng Native Toplevel cực nhanh
        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{rx}+{ry}")
        self._popup.configure(bg="#0b1220")

        # Áp dụng Windows 11 DWM bo góc mượt mà
        _apply_dwm_rounding(self._popup)

        # Khung viền ngoài tinh tế (Subtle glowing border)
        border_frame = tk.Frame(
            self._popup,
            bg="#0b1220",
            highlightthickness=1,
            highlightbackground="#243452",
            highlightcolor="#38bdf8"
        )
        border_frame.pack(fill="both", expand=True)

        cur_val = self.variable.get() if self.variable else ""
        font_family = self._font[0] if isinstance(self._font, (tuple, list)) else "Segoe UI"
        font_size = 10
        font_normal = (font_family, font_size)
        font_active = (font_family, font_size, "bold")

        if needs_scroll:
            canvas = tk.Canvas(border_frame, bg="#0b1220", highlightthickness=0, bd=0)
            items_frame = tk.Frame(canvas, bg="#0b1220")
            canvas_win = canvas.create_window((0, 0), window=items_frame, anchor="nw")

            def _on_frame_cfg(event):
                canvas.configure(scrollregion=canvas.bbox("all"))

            def _on_canvas_cfg(event):
                canvas.itemconfig(canvas_win, width=event.width)

            items_frame.bind("<Configure>", _on_frame_cfg)
            canvas.bind("<Configure>", _on_canvas_cfg)

            def _on_wheel(event):
                if hasattr(event, "delta") and event.delta:
                    direction = -1 if event.delta > 0 else 1
                    canvas.yview_scroll(direction * 2, "units")

            canvas.bind("<MouseWheel>", _on_wheel)
            items_frame.bind("<MouseWheel>", _on_wheel)
            canvas.pack(fill="both", expand=True, padx=6, pady=6)
            container = items_frame
            wheel_target = canvas
        else:
            container = tk.Frame(border_frame, bg="#0b1220")
            container.pack(fill="both", expand=True, padx=6, pady=6)
            wheel_target = None

        current_group = None

        for val in self.values:
            val_str = str(val)

            # Phân loại nhóm ZEN vs NGỌC
            if has_groups:
                if "[ZEN]" in val_str and current_group != "zen":
                    current_group = "zen"
                    hdr = tk.Label(
                        container,
                        text="  💰  QUAY BẰNG ZEN (1M - 2M ZEN)",
                        font=(font_family, 9, "bold"),
                        fg="#f59e0b",
                        bg="#0b1220",
                        anchor="w",
                        pady=4
                    )
                    hdr.pack(fill="x", padx=4, pady=(2, 2))
                elif "[NGỌC]" in val_str and current_group != "ngoc":
                    current_group = "ngoc"
                    div = tk.Frame(container, height=1, bg="#1e293b")
                    div.pack(fill="x", padx=4, pady=(6, 4))
                    hdr = tk.Label(
                        container,
                        text="  💎  QUAY BẰNG NGỌC (MUUN & HIẾM)",
                        font=(font_family, 9, "bold"),
                        fg="#c084fc",
                        bg="#0b1220",
                        anchor="w",
                        pady=4
                    )
                    hdr.pack(fill="x", padx=4, pady=(2, 2))

            is_active = (val == cur_val)
            item_bg = "#132746" if is_active else "#0b1220"
            item_fg = Colors.CYAN if is_active else "#cbd5e1"
            item_font = font_active if is_active else font_normal
            prefix = " ✓ " if is_active else "   "

            # Từng mục thả xuống thiết kế dạng viên nang (Floating Pill)
            row = tk.Frame(container, bg=item_bg, height=item_h, cursor="hand2")
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            lbl_chk = tk.Label(
                row,
                text=prefix,
                font=(font_family, font_size, "bold"),
                fg=Colors.CYAN if is_active else "#475569",
                bg=item_bg,
                cursor="hand2"
            )
            lbl_chk.pack(side="left", padx=(6, 2))

            lbl_txt = tk.Label(
                row,
                text=val_str,
                font=item_font,
                fg=item_fg,
                bg=item_bg,
                anchor="w",
                cursor="hand2"
            )
            lbl_txt.pack(side="left", fill="both", expand=True, padx=(0, 8))

            # Hiệu ứng hover viên nang (Pill Hover Transition)
            def _bind_item(r, chk, txt, v, active):
                def _enter(e):
                    if not active:
                        r.configure(bg="#18243c")
                        chk.configure(bg="#18243c")
                        txt.configure(bg="#18243c", fg="#ffffff")
                    else:
                        r.configure(bg="#17355a")
                        chk.configure(bg="#17355a")
                        txt.configure(bg="#17355a")

                def _leave(e):
                    if not active:
                        r.configure(bg="#0b1220")
                        chk.configure(bg="#0b1220")
                        txt.configure(bg="#0b1220", fg="#cbd5e1")
                    else:
                        r.configure(bg="#132746")
                        chk.configure(bg="#132746")
                        txt.configure(bg="#132746")

                def _click(e):
                    self._on_select(v)

                for widget in (r, chk, txt):
                    widget.bind("<Enter>", _enter)
                    widget.bind("<Leave>", _leave)
                    widget.bind("<Button-1>", _click)
                    if wheel_target:
                        widget.bind("<MouseWheel>", lambda e: wheel_target.yview_scroll(-1 if e.delta > 0 else 1, "units"))

            _bind_item(row, lbl_chk, lbl_txt, val, is_active)

        # Lắng nghe click bên ngoài an toàn (KHÔNG dùng unbind_all)
        try:
            top_win = self.winfo_toplevel()
            self._global_bind_id = top_win.bind("<Button-1>", self._on_global_click, add="+")
            self._popup.bind("<Escape>", lambda e: self._close_popup())
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
        if self._global_bind_id:
            try:
                top_win = self.winfo_toplevel()
                top_win.unbind("<Button-1>", self._global_bind_id)
            except Exception:
                pass
            self._global_bind_id = None

        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

        # Khôi phục trạng thái viền 1px và chevron
        self._apply_surface(self._base_fg, self._base_border, 1)
        try:
            self._chevron.configure(text="▾", fg="#94a3b8")
        except Exception:
            pass

    def _on_select(self, value: str):
        self.set(value)
        self._close_popup()
        if self.command:
            try:
                self.command(value)
            except Exception:
                pass

    def set(self, value: str):
        self.variable.set(value)
        if value != self._last_text and hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._last_text = value
            self._lbl.configure(text=value)

    def get(self) -> str:
        return self.variable.get()

    def configure(self, cnf=None, **kwargs):
        if not kwargs and cnf is None:
            return super().configure()
        kw = dict(kwargs)
        if "values" in kw:
            self.values = list(kw.pop("values"))
        if "variable" in kw:
            self.variable = kw.pop("variable")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists() and self.variable:
                v = self.variable.get()
                self._last_text = v
                self._lbl.configure(text=v)
        if "command" in kw:
            self.command = kw.pop("command")
        if "fg_color" in kw:
            self._base_fg = kw.pop("fg_color")
            self._apply_surface(self._base_fg, self._base_border, 1)
        if "border_color" in kw:
            self._base_border = kw.pop("border_color")
            super().configure(highlightbackground=self._base_border, highlightcolor=self._base_border)
        if "border_width" in kw:
            bw = int(kw.pop("border_width") or 1)
            super().configure(highlightthickness=bw)
        if "text_color" in kw:
            self._text_color = kw.pop("text_color")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists():
                self._lbl.configure(fg=self._text_color)
        for drop_k in (
            "button_color", "button_hover_color", "dropdown_fg_color",
            "dropdown_hover_color", "dropdown_text_color", "anchor", "corner_radius",
        ):
            kw.pop(drop_k, None)
        if kw:
            super().configure(**kw)

    config = configure
