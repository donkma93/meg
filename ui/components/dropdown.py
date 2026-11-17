# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - MODERN DROPDOWN COMPONENT
Dropdown menu thông minh, phong cách phẳng hiện đại:
- Tự động kiểm tra tràn màn hình (Screen overflow check) và nảy lên trên (Flip Upwards) nếu gần đáy màn hình.
- Tự động cuộn mượt với thanh cuộn siêu mỏng 6px (Slim Scrollbar) hài hòa Dark Theme.
- Chiều rộng bung thông minh (Smart popup width) giúp không bao giờ bị cắt chữ.
- Phân nhóm danh mục trực quan (Group headers & dividers) cho các mục ZEN / NGỌC.
- Trạng thái Active có checkmark nổi bật, viền phát sáng khi Dropdown đang mở.
- Đồng bộ chuẩn giao diện Dark Mode Flat Design.
"""

import time
import sys
from typing import Optional, List, Callable, Any
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory


class ModernDropdown(ctk.CTkFrame):
    """Dropdown menu hiện đại thông minh chống tràn màn hình với phong cách thiết kế cao cấp."""

    def __init__(
        self,
        master,
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        command: Optional[Callable[[str], Any]] = None,
        width: int = 140,
        height: int = 32,
        font: Optional[ctk.CTkFont] = None,
        fg_color: Optional[str] = None,
        border_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        text_color: Optional[str] = None,
        on_open: Optional[Callable[[], Any]] = None,
        popup_min_width: Optional[int] = None,
        **kwargs
    ):
        # Bỏ qua các tham số riêng nếu truyền từ CTkOptionMenu
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)

        c_radius = kwargs.pop("corner_radius", 6)
        base_fg = fg_color or Colors.BG_SURFACE
        base_border = border_color or Colors.BORDER_CARD
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=base_fg,
            border_width=1,
            border_color=base_border,
            corner_radius=c_radius,
            **kwargs
        )
        self.pack_propagate(False)

        self._base_fg = base_fg
        self._base_border = base_border
        self._hover_bg = hover_color or Colors.BG_CARD_HOVER
        self._text_color = text_color or Colors.TEXT_MAIN
        self._font = font or Fonts.CAPTION
        self._req_width = width
        self._req_height = height
        self._popup_min_width = popup_min_width or 240
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
        self._lbl.pack(side="left", fill="both", expand=True, padx=(8, 4))

        # Vector Icon Chevron Down
        self._chevron = ctk.CTkLabel(
            self,
            text="",
            image=UiIconFactory.get("chevron_down", color="#94a3b8", size=(10, 10))
        )
        self._chevron.pack(side="right", padx=(0, 8))

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
        if not self._popup or not self._popup.winfo_exists():
            self.configure(fg_color=self._hover_bg, border_color="#334155")

    def _on_leave(self):
        if not self._popup or not self._popup.winfo_exists():
            self.configure(fg_color=self._base_fg, border_color=self._base_border)

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

        # Hiệu ứng Active Focus cho trigger button
        self.configure(border_color=Colors.BORDER_FOCUS, fg_color=self._hover_bg)
        try:
            self._chevron.configure(image=UiIconFactory.get("chevron_down", color=Colors.CYAN, size=(10, 10)))
        except Exception:
            pass

        rx = self.winfo_rootx()
        ry = self.winfo_rooty() + self.winfo_height() + 3
        w = max(self.winfo_width(), self._req_width, self._popup_min_width)

        # Kiểm tra tràn lề phải màn hình (Right screen bounds check)
        try:
            screen_w = self.winfo_screenwidth()
            if rx + w > screen_w - 12:
                rx = max(10, screen_w - w - 12)
        except Exception:
            pass

        num_items = len(self.values)
        item_h = 28

        # Kiểm tra xem danh sách có phân nhóm (ZEN vs NGỌC) hay không
        has_zen = any("[ZEN]" in str(v) for v in self.values)
        has_ngoc = any("[NGỌC]" in str(v) for v in self.values)
        has_groups = has_zen and has_ngoc
        header_extra = 52 if has_groups else 0

        total_content_h = num_items * (item_h + 2) + header_extra + 12
        h = max(36, min(290, total_content_h))

        # Kiểm tra tràn đáy màn hình (FLIP UPWARDS)
        try:
            screen_h = self.winfo_screenheight()
            if ry + h > screen_h - 45:
                # Nảy lên trên nút
                ry = max(10, self.winfo_rooty() - h - 3)
        except Exception:
            pass

        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{rx}+{ry}")

        outer = ctk.CTkFrame(
            self._popup,
            fg_color="#0e1626",
            border_width=1,
            border_color="#2b3b57",
            corner_radius=8
        )
        outer.pack(fill="both", expand=True)

        needs_scroll = (total_content_h > 290 or num_items > 7)
        if needs_scroll:
            container = ctk.CTkScrollableFrame(
                outer,
                fg_color="transparent",
                scrollbar_fg_color="transparent",
                scrollbar_button_color="#243149",
                scrollbar_button_hover_color="#38bdf8",
                corner_radius=0
            )
            try:
                container._scrollbar.configure(width=6, corner_radius=3)
            except Exception:
                pass
            container.pack(fill="both", expand=True, padx=3, pady=3)
        else:
            container = ctk.CTkFrame(outer, fg_color="transparent")
            container.pack(fill="both", expand=True, padx=3, pady=3)

        cur_val = self.variable.get() if self.variable else ""
        current_group = None

        font_family = self._font[0] if isinstance(self._font, tuple) else "Segoe UI"
        font_active = (font_family, 10, "bold")
        font_normal = (font_family, 10)

        for val in self.values:
            val_str = str(val)

            # Tạo Header phân loại tự động nếu có nhóm ZEN / NGỌC
            if has_groups:
                if "[ZEN]" in val_str and current_group != "zen":
                    current_group = "zen"
                    hdr = ctk.CTkLabel(
                        container,
                        text="  💰  QUAY BẰNG ZEN (1M - 2M ZEN)",
                        font=(font_family, 9, "bold"),
                        text_color="#f59e0b",
                        anchor="w"
                    )
                    hdr.pack(fill="x", padx=6, pady=(3, 1))
                elif "[NGỌC]" in val_str and current_group != "ngoc":
                    current_group = "ngoc"
                    div = ctk.CTkFrame(container, height=1, fg_color="#1e293b")
                    div.pack(fill="x", padx=6, pady=(5, 3))
                    hdr = ctk.CTkLabel(
                        container,
                        text="  💎  QUAY BẰNG NGỌC (MUUN & HIẾM)",
                        font=(font_family, 9, "bold"),
                        text_color="#c084fc",
                        anchor="w"
                    )
                    hdr.pack(fill="x", padx=6, pady=(1, 1))

            is_active = (val == cur_val)
            if is_active:
                btn_text = f"  ✓  {val}"
                btn_fg = "#14243f"
                btn_border = 1
                border_c = "#2563eb"
                txt_c = Colors.CYAN
                btn_font = font_active
            else:
                btn_text = f"      {val}"
                btn_fg = "transparent"
                btn_border = 0
                border_c = None
                txt_c = "#e2e8f0"
                btn_font = font_normal

            btn_kwargs = {
                "master": container,
                "text": btn_text,
                "anchor": "w",
                "height": item_h,
                "corner_radius": 6,
                "font": btn_font,
                "fg_color": btn_fg,
                "border_width": btn_border,
                "hover_color": "#182338",
                "text_color": txt_c,
                "command": lambda v=val: self._on_select(v),
            }
            if border_c is not None:
                btn_kwargs["border_color"] = border_c

            btn = ctk.CTkButton(**btn_kwargs)
            btn.pack(fill="x", padx=2, pady=1)

        # Lắng nghe click bên ngoài thông qua root toplevel
        try:
            top_win = self.winfo_toplevel()
            self._popup.after(80, lambda: top_win.bind_all("<Button-1>", self._on_global_click, add="+"))
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
        try:
            top_win = self.winfo_toplevel()
            top_win.unbind_all("<Button-1>")
        except Exception:
            pass
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        # Khôi phục trạng thái viền và chevron
        self.configure(fg_color=self._base_fg, border_color=self._base_border)
        try:
            self._chevron.configure(image=UiIconFactory.get("chevron_down", color="#94a3b8", size=(10, 10)))
        except Exception:
            pass

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
        if "border_color" in kwargs:
            self._base_border = kwargs.pop("border_color")
            super().configure(border_color=self._base_border)
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
        super().configure(**kwargs)
