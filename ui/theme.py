# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - DESIGN SYSTEM & THEME TOKENS
Dark ops dashboard: dense, scannable, Linear/Vercel-inspired.
"""


class Colors:
    # Surfaces
    BG_ROOT = "#070b14"
    BG_HEADER = "#0b1220"
    BG_NAV = "#0c1424"
    BG_SURFACE = "#0f172a"
    BG_SURFACE_ELEVATED = "#121c31"
    BG_CARD = "#131c30"
    BG_CARD_HOVER = "#1a2540"
    BG_CARD_ACTIVE = "#172033"
    BG_INPUT = "#0a101c"
    BG_CHIP = "#152038"
    BG_FOOTER = "#080e18"

    # Borders
    BORDER_SUBTLE = "#1a2438"
    BORDER_CARD = "#243149"
    BORDER_FOCUS = "#38bdf8"
    BORDER_SUCCESS = "#22c55e"
    BORDER_DANGER = "#ef4444"
    BORDER_ACCENT = "#1d4ed8"

    # Typography
    TEXT_MAIN = "#f1f5f9"
    TEXT_MUTED = "#94a3b8"
    TEXT_DIM = "#64748b"
    TEXT_DARK = "#475569"
    TEXT_INVERSE = "#0b1220"

    # Accents
    CYAN = "#38bdf8"
    CYAN_SOFT = "#0ea5e9"
    GREEN = "#22c55e"
    GREEN_HOVER = "#16a34a"
    GREEN_SOFT = "#14b8a6"
    AMBER = "#f59e0b"
    YELLOW = "#eab308"
    ROSE = "#ef4444"
    ROSE_HOVER = "#dc2626"
    PURPLE = "#c084fc"
    BLUE = "#60a5fa"
    TEAL = "#2dd4bf"

    # Slot states
    SLOT_STOPPED_BG = "#111827"
    SLOT_RUNNING_BG = "#0c1f24"
    SLOT_RUNNING_BORDER = "#14b8a6"
    SLOT_WARN_BG = "#1f1808"
    SLOT_WARN_BORDER = "#b45309"

    # Semantic chips
    CHIP_OK_BG = "#052e1c"
    CHIP_OK_FG = "#4ade80"
    CHIP_WARN_BG = "#2a1c05"
    CHIP_WARN_FG = "#fbbf24"
    CHIP_ERR_BG = "#2a0b10"
    CHIP_ERR_FG = "#fb7185"
    CHIP_INFO_BG = "#0b1f33"
    CHIP_INFO_FG = "#7dd3fc"


class Fonts:
    FAMILY = "Segoe UI"
    HEADER_TITLE = (FAMILY, 16, "bold")
    HEADER_SUB = (FAMILY, 11)
    NAV_TAB = (FAMILY, 11, "bold")
    SLOT_TITLE = (FAMILY, 13, "bold")
    BODY = (FAMILY, 11)
    BODY_BOLD = (FAMILY, 11, "bold")
    CAPTION = (FAMILY, 10)
    CAPTION_BOLD = (FAMILY, 10, "bold")
    BADGE = (FAMILY, 10, "bold")
    METRIC = (FAMILY, 12, "bold")
    MONO = ("Consolas", 10)
    COUNTDOWN = (FAMILY, 28, "bold")
    SECTION = (FAMILY, 12, "bold")


class Radii:
    XS = 4
    SM = 6
    MD = 8
    LG = 10
    PILL = 999


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
