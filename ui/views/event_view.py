# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - UNIFIED EVENTS VIEW (MIRROR & MOSS)
Giao diện quản lý sự kiện Double Goer (Mirror) và Moss Merchant tập trung, mượt mà.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory

class EventsView(ctk.CTkFrame):
    """View sự kiện hợp nhất với đồng hồ đếm ngược lớn và danh sách slot tham gia."""

    def __init__(
        self,
        parent,
        controllers: list,
        on_trigger_mirror: Optional[Callable[[], None]] = None,
        on_trigger_moss: Optional[Callable[[], None]] = None,
        on_toggle_participant: Optional[Callable[[str, int, bool], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.controllers = controllers
        self.on_trigger_mirror = on_trigger_mirror
        self.on_trigger_moss = on_trigger_moss
        self.on_toggle_participant = on_toggle_participant

        self.mirror_cb_vars: Dict[int, ctk.BooleanVar] = {}
        self.moss_cb_vars: Dict[int, ctk.BooleanVar] = {}

        self._build_layout()

    def _build_layout(self):
        # Chia 2 cột: Cột trái cho Double Goer (Mirror), Cột phải cho Moss Merchant
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # CỘT 1: DOUBLE GOER (MIRROR)
        # ----------------------------------------------------------------------
        self.card_mirror = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=6, border_width=1, border_color=Colors.BORDER_CARD)
        self.card_mirror.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        # Tiêu đề card Mirror
        m_hdr = ctk.CTkFrame(self.card_mirror, fg_color=Colors.BG_HEADER, height=44, corner_radius=0)
        m_hdr.pack(fill="x")
        m_hdr.pack_propagate(False)

        ctk.CTkLabel(
            m_hdr,
            text="🚪 DOUBLE GOER (MIRROR)",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.CYAN
        ).pack(side="left", padx=12, pady=10)

        self.lbl_mirror_gate_status = ctk.CTkLabel(
            m_hdr,
            text="Cổng đóng",
            font=Fonts.BADGE,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_mirror_gate_status.pack(side="right", padx=12, pady=10)

        # Body Mirror
        m_body = ctk.CTkFrame(self.card_mirror, fg_color="transparent")
        m_body.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(m_body, text="Lịch trình: Mở mỗi 2 tiếng vào giờ chẵn (:10 - :15)", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(anchor="w")

        # Đồng hồ đếm ngược Mirror
        self.lbl_mirror_countdown = ctk.CTkLabel(
            m_body,
            text="00:00:00",
            font=Fonts.COUNTDOWN,
            text_color=Colors.CYAN
        )
        self.lbl_mirror_countdown.pack(pady=(10, 6))

        # Nút Snipe cướp cổng thủ công
        ctk.CTkButton(
            m_body,
            image=UiIconFactory.get("zap", color="#ffffff", size=(14, 14)),
            compound="left",
            text="⚡ CƯỚP CỔNG NGAY (SNIPE)",
            font=Fonts.BODY_BOLD,
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=32,
            corner_radius=2,
            command=self._handle_trigger_mirror
        ).pack(fill="x", pady=(0, 12))

        # Danh sách chọn Slot tham gia Mirror
        ctk.CTkLabel(m_body, text="Tài khoản tham gia sự kiện Mirror:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(anchor="w", pady=(4, 6))

        m_scroll = ctk.CTkScrollableFrame(m_body, fg_color=Colors.BG_SURFACE, height=180, corner_radius=2)
        m_scroll.pack(fill="both", expand=True)

        for ctrl in self.controllers:
            s_idx = ctrl.slot_idx
            var = ctk.BooleanVar(value=getattr(ctrl, "mirror_enabled", True))
            self.mirror_cb_vars[s_idx] = var

            r = ctk.CTkFrame(m_scroll, fg_color="transparent", height=28)
            r.pack(fill="x", pady=1)

            cb = ctk.CTkCheckBox(
                r,
                text=f"SLOT {s_idx} ({ctrl.char_name})",
                variable=var,
                font=Fonts.BODY,
                checkbox_width=16,
                checkbox_height=16,
                command=lambda s=s_idx, v=var: self._on_toggle_participant("mirror", s, v.get())
            )
            cb.pack(side="left", padx=6)

        # ----------------------------------------------------------------------
        # CỘT 2: MOSS MERCHANT
        # ----------------------------------------------------------------------
        self.card_moss = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=6, border_width=1, border_color=Colors.BORDER_CARD)
        self.card_moss.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        # Tiêu đề card Moss
        moss_hdr = ctk.CTkFrame(self.card_moss, fg_color=Colors.BG_HEADER, height=44, corner_radius=0)
        moss_hdr.pack(fill="x")
        moss_hdr.pack_propagate(False)

        ctk.CTkLabel(
            moss_hdr,
            text="🎲 MOSS MERCHANT",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.GREEN
        ).pack(side="left", padx=12, pady=10)

        self.lbl_moss_status = ctk.CTkLabel(
            moss_hdr,
            text="Chờ sự kiện",
            font=Fonts.BADGE,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_moss_status.pack(side="right", padx=12, pady=10)

        # Body Moss
        moss_body = ctk.CTkFrame(self.card_moss, fg_color="transparent")
        moss_body.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(moss_body, text="Lịch trình: Mở vào :15 các mốc 00h, 06h, 12h, 18h", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(anchor="w")

        # Đồng hồ đếm ngược Moss
        self.lbl_moss_countdown = ctk.CTkLabel(
            moss_body,
            text="00:00:00",
            font=Fonts.COUNTDOWN,
            text_color=Colors.GREEN
        )
        self.lbl_moss_countdown.pack(pady=(10, 6))

        # Nút Kích hoạt quay Moss ngay
        ctk.CTkButton(
            moss_body,
            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)),
            compound="left",
            text="🎲 KÍCH HOẠT QUAY MOSS NGAY",
            font=Fonts.BODY_BOLD,
            fg_color="#059669",
            hover_color="#047857",
            height=32,
            corner_radius=2,
            command=self._handle_trigger_moss
        ).pack(fill="x", pady=(0, 12))

        # Danh sách chọn Slot tham gia Moss
        ctk.CTkLabel(moss_body, text="Tài khoản tham gia quay Moss:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(anchor="w", pady=(4, 6))

        moss_scroll = ctk.CTkScrollableFrame(moss_body, fg_color=Colors.BG_SURFACE, height=180, corner_radius=2)
        moss_scroll.pack(fill="both", expand=True)

        for ctrl in self.controllers:
            s_idx = ctrl.slot_idx
            var = ctk.BooleanVar(value=getattr(ctrl, "moss_enabled", True))
            self.moss_cb_vars[s_idx] = var

            r = ctk.CTkFrame(moss_scroll, fg_color="transparent", height=28)
            r.pack(fill="x", pady=1)

            cb = ctk.CTkCheckBox(
                r,
                text=f"SLOT {s_idx} ({ctrl.char_name})",
                variable=var,
                font=Fonts.BODY,
                checkbox_width=16,
                checkbox_height=16,
                command=lambda s=s_idx, v=var: self._on_toggle_participant("moss", s, v.get())
            )
            cb.pack(side="left", padx=6)

    # --------------------------------------------------------------------------
    # CẬP NHẬT ĐẾM NGƯỢC THỜI GIAN THỰC (ZERO LAG)
    # --------------------------------------------------------------------------
    def update_countdowns(self, mirror_sec: int, mirror_open: bool, moss_sec: int, moss_open: bool):
        """Cập nhật In-Place 100% không render lại khung."""
        # Mirror
        m_str = self._format_seconds(mirror_sec)
        self.lbl_mirror_countdown.configure(text=m_str)
        if mirror_open:
            self.lbl_mirror_gate_status.configure(text="⚡ CỔNG ĐANG MỞ", text_color=Colors.GREEN)
        else:
            self.lbl_mirror_gate_status.configure(text="Cổng đóng", text_color=Colors.TEXT_MUTED)

        # Moss
        moss_str = self._format_seconds(moss_sec)
        self.lbl_moss_countdown.configure(text=moss_str)
        if moss_open:
            self.lbl_moss_status.configure(text="🎲 ĐANG MỞ MOSS", text_color=Colors.GREEN)
        else:
            self.lbl_moss_status.configure(text="Chờ sự kiện", text_color=Colors.TEXT_MUTED)

    @staticmethod
    def _format_seconds(sec: int) -> str:
        if sec < 0:
            sec = 0
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _handle_trigger_mirror(self):
        if self.on_trigger_mirror:
            self.on_trigger_mirror()

    def _handle_trigger_moss(self):
        if self.on_trigger_moss:
            self.on_trigger_moss()

    def _on_toggle_participant(self, event_type: str, slot_idx: int, is_enabled: bool):
        if self.on_toggle_participant:
            self.on_toggle_participant(event_type, slot_idx, is_enabled)
