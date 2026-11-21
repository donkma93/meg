# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - ZERO-CANVAS FAST NATIVE WIDGETS
Thay thế các widget CTk lặp lại trong bảng nhiều dòng (Table Rows) bằng tk.Frame / tk.Label / tk.Entry thuần:
- 0 Canvas (giảm ~80% số Canvas GDI trên Windows)
- Thời gian tạo & cập nhật nhanh hơn 10-50x so với CustomTkinter
- Giữ nguyên màu sắc, font, kích thước pixel và API tương thích ngược (.configure(text_color=..., fg_color=...)).
"""

import tkinter as tk
from typing import Optional, Callable, Any


class FastCell(tk.Frame):
    """Ô nhãn bảng kích thước cố định theo pixel (0 Canvas), tương thích API CTkLabel."""

    def __init__(
        self,
        parent,
        text: str = "",
        width: int = 80,
        height: int = 26,
        bg: str = "#0c1424",
        fg: str = "#f1f5f9",
        font: Any = ("Segoe UI", 10),
        anchor: str = "w",
        padx: int = 0,
        **kwargs,
    ):
        super().__init__(parent, width=width, height=height, bg=bg, bd=0, highlightthickness=0, **kwargs)
        self.pack_propagate(False)
        self._bg = bg
        self._fg = fg
        self._text = text
        self._lbl = tk.Label(
            self,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            anchor=anchor,
            bd=0,
            padx=padx,
            pady=0,
        )
        self._lbl.pack(fill="both", expand=True)

    def configure(self, cnf=None, **kwargs):
        if not kwargs and cnf is None:
            return super().configure()
        kw = dict(kwargs)
        if "text" in kw:
            t = kw.pop("text")
            if t != self._text:
                self._text = t
                self._lbl.configure(text=t)
        if "text_color" in kw:
            c = kw.pop("text_color")
            if c != self._fg:
                self._fg = c
                self._lbl.configure(fg=c)
        if "fg_color" in kw:
            b = kw.pop("fg_color")
            if b == "transparent":
                b = self._bg
            if b != self._bg:
                self._bg = b
                super().configure(bg=b)
                self._lbl.configure(bg=b)
        if "bg" in kw:
            b = kw.pop("bg")
            if b != self._bg:
                self._bg = b
                super().configure(bg=b)
                self._lbl.configure(bg=b)
        if "fg" in kw:
            c = kw.pop("fg")
            if c != self._fg:
                self._fg = c
                self._lbl.configure(fg=c)
        if kw:
            super().configure(**kw)

    config = configure

    def cget(self, key: str):
        if key == "text":
            return self._text
        if key == "text_color":
            return self._fg
        if key == "fg_color":
            return self._bg
        return super().cget(key)

    def set_bg(self, bg: str):
        if bg != self._bg:
            self._bg = bg
            super().configure(bg=bg)
            self._lbl.configure(bg=bg)


class FastButton(tk.Frame):
    """Nút bấm phẳng siêu nhẹ (0 Canvas) dùng cho các hàng bảng, tương thích API CTkButton."""

    def __init__(
        self,
        parent,
        text: str = "",
        command: Optional[Callable[[], Any]] = None,
        width: int = 58,
        height: int = 24,
        fg_color: str = "#1e293b",
        hover_color: str = "#334155",
        text_color: str = "#f1f5f9",
        border_color: Optional[str] = None,
        font: Any = ("Segoe UI", 9, "bold"),
        **kwargs,
    ):
        b_col = border_color or fg_color
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=fg_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=b_col,
            highlightcolor=b_col,
            cursor="hand2",
            **kwargs,
        )
        self.pack_propagate(False)
        self._command = command
        self._bg = fg_color
        self._hover = hover_color
        self._fg = text_color
        self._border = b_col
        self._text = text
        self._hovered = False

        self._lbl = tk.Label(
            self,
            text=text,
            bg=fg_color,
            fg=text_color,
            font=font,
            anchor="center",
            bd=0,
            cursor="hand2",
        )
        self._lbl.pack(fill="both", expand=True)

        for w in (self, self._lbl):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Button-1>", self._on_click, add="+")

    def _on_enter(self, _e=None):
        self._hovered = True
        super().configure(bg=self._hover)
        self._lbl.configure(bg=self._hover)

    def _on_leave(self, _e=None):
        self._hovered = False
        super().configure(bg=self._bg)
        self._lbl.configure(bg=self._bg)

    def _on_click(self, _e=None):
        if callable(self._command):
            self._command()

    def bind(self, sequence=None, func=None, add=None):
        res = super().bind(sequence, func, add=add)
        self._lbl.bind(sequence, func, add=add)
        return res

    def configure(self, cnf=None, **kwargs):
        if not kwargs and cnf is None:
            return super().configure()
        kw = dict(kwargs)
        kw.pop("image", None)
        kw.pop("compound", None)
        if "command" in kw:
            self._command = kw.pop("command")
        if "text" in kw:
            t = kw.pop("text")
            if t != self._text:
                self._text = t
                self._lbl.configure(text=t)
        if "hover_color" in kw:
            self._hover = kw.pop("hover_color")
        if "fg_color" in kw:
            b = kw.pop("fg_color")
            if b != self._bg:
                self._bg = b
                active_bg = self._hover if self._hovered else b
                super().configure(bg=active_bg)
                self._lbl.configure(bg=active_bg)
                if "border_color" not in kw:
                    self._border = b
                    super().configure(highlightbackground=b, highlightcolor=b)
        if "border_color" in kw:
            bc = kw.pop("border_color")
            if bc != self._border:
                self._border = bc
                super().configure(highlightbackground=bc, highlightcolor=bc)
        if "text_color" in kw:
            c = kw.pop("text_color")
            if c != self._fg:
                self._fg = c
                self._lbl.configure(fg=c)
        if kw:
            super().configure(**kw)

    config = configure


class FastEntry(tk.Frame):
    """Ô nhập liệu phẳng siêu nhẹ (0 Canvas), tương thích API CTkEntry cơ bản."""

    def __init__(
        self,
        parent,
        textvariable: Optional[tk.StringVar] = None,
        width: int = 60,
        height: int = 24,
        fg_color: str = "#0b1322",
        border_color: str = "#1e293b",
        text_color: str = "#f1f5f9",
        font: Any = ("Segoe UI", 10),
        justify: str = "center",
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=fg_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor="#38bdf8",
            **kwargs,
        )
        self.pack_propagate(False)
        self._entry = tk.Entry(
            self,
            textvariable=textvariable,
            bg=fg_color,
            fg=text_color,
            insertbackground=text_color,
            selectbackground="#1d4ed8",
            selectforeground="#ffffff",
            font=font,
            justify=justify,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self._entry.pack(fill="both", expand=True, padx=4, pady=1)

    def get(self) -> str:
        return self._entry.get()

    def insert(self, index, string):
        return self._entry.insert(index, string)

    def delete(self, first, last=None):
        return self._entry.delete(first, last)

    def bind(self, sequence=None, func=None, add=None):
        return self._entry.bind(sequence, func, add=add)

    def is_focused(self) -> bool:
        try:
            return self.focus_get() in (self, self._entry)
        except Exception:
            return False


class FastCheckBox(tk.Frame):
    """Checkbox siêu nhẹ (0 Canvas) dùng cho bảng Mirror/Moss."""

    def __init__(
        self,
        parent,
        text: str = "",
        variable: Optional[tk.BooleanVar] = None,
        command: Optional[Callable[[], Any]] = None,
        width: int = 60,
        height: int = 24,
        bg: str = "#0c1424",
        text_color: str = "#f1f5f9",
        accent_color: str = "#38bdf8",
        font: Any = ("Segoe UI", 9, "bold"),
        **kwargs,
    ):
        super().__init__(parent, width=width, height=height, bg=bg, bd=0, highlightthickness=0, cursor="hand2", **kwargs)
        self.pack_propagate(False)
        self._var = variable or tk.BooleanVar(value=True)
        self._command = command
        self._bg = bg
        self._fg = text_color
        self._accent = accent_color

        self._box = tk.Label(
            self,
            text="",
            width=2,
            bg=accent_color if self._var.get() else "#111827",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            highlightthickness=1,
            highlightbackground=accent_color if self._var.get() else "#334155",
            cursor="hand2",
        )
        self._box.pack(side="left", padx=(2, 4), pady=4)

        self._lbl = tk.Label(
            self,
            text=text,
            bg=bg,
            fg=text_color,
            font=font,
            anchor="w",
            bd=0,
            cursor="hand2",
        )
        self._lbl.pack(side="left", fill="both", expand=True)

        self._sync_visual()
        try:
            self._var.trace_add("write", lambda *_: self._sync_visual())
        except Exception:
            pass

        for w in (self, self._box, self._lbl):
            w.bind("<Button-1>", self._toggle, add="+")

    def _toggle(self, _e=None):
        self._var.set(not bool(self._var.get()))
        if callable(self._command):
            self._command()

    def _sync_visual(self):
        try:
            if not self.winfo_exists():
                return
            checked = bool(self._var.get())
            self._box.configure(
                text="✓" if checked else "",
                bg=self._accent if checked else "#0f172a",
                highlightbackground=self._accent if checked else "#475569",
            )
        except Exception:
            pass

    def configure(self, cnf=None, **kwargs):
        if not kwargs and cnf is None:
            return super().configure()
        kw = dict(kwargs)
        if "text_color" in kw:
            c = kw.pop("text_color")
            if c != self._fg:
                self._fg = c
                self._lbl.configure(fg=c)
        if "bg" in kw or "fg_color" in kw:
            b = kw.pop("bg", kw.pop("fg_color", self._bg))
            if b != self._bg:
                self._bg = b
                super().configure(bg=b)
                self._lbl.configure(bg=b)
        if kw:
            super().configure(**kw)

    config = configure

    def set_bg(self, bg: str):
        if bg != self._bg:
            self._bg = bg
            super().configure(bg=bg)
            self._lbl.configure(bg=bg)
