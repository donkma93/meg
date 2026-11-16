# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - SHARED SHELL WIDGETS
Reusable dashboard surfaces: section cards, metric chips, toolbars.
"""

from typing import Optional, Callable, Any
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii, Spacing


class SectionCard(ctk.CTkFrame):
    """Elevated content card with optional title strip."""

    def __init__(
        self,
        parent,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        accent: str = Colors.CYAN,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_CARD,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=Radii.MD,
            **kwargs
        )
        self.accent = accent
        self.header = None
        self.body = ctk.CTkFrame(self, fg_color="transparent")

        if title:
            self.header = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, height=42, corner_radius=0)
            self.header.pack(fill="x")
            self.header.pack_propagate(False)

            accent_bar = ctk.CTkFrame(self.header, fg_color=accent, width=3, corner_radius=0)
            accent_bar.pack(side="left", fill="y")

            title_box = ctk.CTkFrame(self.header, fg_color="transparent")
            title_box.pack(side="left", fill="both", expand=True, padx=12)

            ctk.CTkLabel(
                title_box,
                text=title,
                font=Fonts.SECTION,
                text_color=Colors.TEXT_MAIN,
                anchor="w"
            ).pack(anchor="w", pady=(6 if not subtitle else 4, 0))

            if subtitle:
                ctk.CTkLabel(
                    title_box,
                    text=subtitle,
                    font=Fonts.CAPTION,
                    text_color=Colors.TEXT_DIM,
                    anchor="w"
                ).pack(anchor="w")

            self.header_right = ctk.CTkFrame(self.header, fg_color="transparent")
            self.header_right.pack(side="right", padx=10)

        self.body.pack(fill="both", expand=True, padx=12, pady=10)


class MetricChip(ctk.CTkFrame):
    """Compact status/metric chip for header and toolbars."""

    def __init__(
        self,
        parent,
        label: str,
        value: str = "0",
        tone: str = "info",
        width: int = 118,
        **kwargs
    ):
        tones = {
            "info": (Colors.CHIP_INFO_BG, Colors.CHIP_INFO_FG, Colors.BORDER_CARD),
            "ok": (Colors.CHIP_OK_BG, Colors.CHIP_OK_FG, "#14532d"),
            "warn": (Colors.CHIP_WARN_BG, Colors.CHIP_WARN_FG, "#854d0e"),
            "err": (Colors.CHIP_ERR_BG, Colors.CHIP_ERR_FG, "#7f1d1d"),
            "neutral": (Colors.BG_CHIP, Colors.TEXT_MUTED, Colors.BORDER_SUBTLE),
        }
        bg, fg, border = tones.get(tone, tones["info"])
        super().__init__(
            parent,
            fg_color=bg,
            border_width=1,
            border_color=border,
            corner_radius=Radii.SM,
            width=width,
            height=34,
            **kwargs
        )
        self.pack_propagate(False)
        self._fg = fg

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8, pady=4)

        self.lbl_label = ctk.CTkLabel(
            inner,
            text=label,
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM,
            anchor="w"
        )
        self.lbl_label.pack(anchor="w")

        self.lbl_value = ctk.CTkLabel(
            inner,
            text=value,
            font=Fonts.METRIC,
            text_color=fg,
            anchor="w"
        )
        self.lbl_value.pack(anchor="w")

    def set_value(self, value: str, tone: Optional[str] = None):
        self.lbl_value.configure(text=value)
        if tone:
            tones = {
                "info": (Colors.CHIP_INFO_BG, Colors.CHIP_INFO_FG, Colors.BORDER_CARD),
                "ok": (Colors.CHIP_OK_BG, Colors.CHIP_OK_FG, "#14532d"),
                "warn": (Colors.CHIP_WARN_BG, Colors.CHIP_WARN_FG, "#854d0e"),
                "err": (Colors.CHIP_ERR_BG, Colors.CHIP_ERR_FG, "#7f1d1d"),
                "neutral": (Colors.BG_CHIP, Colors.TEXT_MUTED, Colors.BORDER_SUBTLE),
            }
            bg, fg, border = tones.get(tone, tones["info"])
            self.configure(fg_color=bg, border_color=border)
            self.lbl_value.configure(text_color=fg)


class ToolbarBar(ctk.CTkFrame):
    """Dense action toolbar used across views."""

    def __init__(self, parent, height: int = 48, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_SURFACE,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=Radii.MD,
            height=height,
            **kwargs
        )
        self.pack_propagate(False)
        self.left = ctk.CTkFrame(self, fg_color="transparent")
        self.left.pack(side="left", fill="y", padx=10)
        self.right = ctk.CTkFrame(self, fg_color="transparent")
        self.right.pack(side="right", fill="y", padx=10)


def make_action_button(
    parent,
    text: str,
    command: Optional[Callable] = None,
    *,
    image: Any = None,
    tone: str = "neutral",
    width: Optional[int] = None,
    height: int = 30,
) -> ctk.CTkButton:
    """Styled toolbar / card action button."""
    palettes = {
        "primary": ("#0c4a6e", "#075985", "#0284c7", Colors.CYAN),
        "success": (Colors.GREEN, Colors.GREEN_HOVER, Colors.GREEN, "#ffffff"),
        "danger": (Colors.ROSE, Colors.ROSE_HOVER, Colors.ROSE, "#ffffff"),
        "purple": ("#2e1065", "#3b0764", "#7e22ce", Colors.PURPLE),
        "fire": ("#450a0a", "#7f1d1d", "#be123c", "#fb7185"),
        "neutral": (Colors.BG_CARD, Colors.BG_CARD_HOVER, Colors.BORDER_CARD, Colors.TEXT_MAIN),
        "ghost": ("transparent", Colors.BG_CARD_HOVER, Colors.BORDER_SUBTLE, Colors.TEXT_MUTED),
    }
    fg, hover, border, text_color = palettes.get(tone, palettes["neutral"])
    kwargs = dict(
        text=text,
        image=image,
        compound="left",
        command=command,
        font=Fonts.BODY_BOLD if tone in ("success", "danger", "primary") else Fonts.BODY,
        fg_color=fg,
        hover_color=hover,
        border_width=1,
        border_color=border,
        text_color=text_color,
        height=height,
        corner_radius=Radii.SM,
    )
    if width is not None:
        kwargs["width"] = width
    return ctk.CTkButton(parent, **kwargs)
