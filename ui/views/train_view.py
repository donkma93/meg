# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - TRAIN SLOTS VIEW
Dense dashboard of 10 Auto Train slot cards + action toolbar.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory
from ui.components.cards import CompactSlotCard
from ui.components.shell import ToolbarBar, make_action_button, SectionCard
from ui.modals.slot_settings import SlotSettingsModal


class TrainSlotsView(ctk.CTkFrame):
    """Auto Train view with modern toolbar and slot card stack."""

    def __init__(
        self,
        parent,
        controllers: list,
        maps_list: list,
        on_toggle_slot: Optional[Callable[[int], None]] = None,
        on_toggle_all: Optional[Callable[[bool], None]] = None,
        on_save_slot_config: Optional[Callable[[int, Dict[str, Any]], None]] = None,
        on_connect_all: Optional[Callable[[], None]] = None,
        on_assign_all: Optional[Callable[[], None]] = None,
        on_refresh_games: Optional[Callable[[], None]] = None,
        on_arrange_windows: Optional[Callable[[], None]] = None,
        on_slot_pid_selected: Optional[Callable[[int, str], None]] = None,
        on_slot_profile_selected: Optional[Callable[[int, str], None]] = None,
        on_stack_jewels: Optional[Callable[[], None]] = None,
        on_devil_config: Optional[Callable[[], None]] = None,
        on_close_games: Optional[Callable[[], None]] = None,
        on_open_stat_dialog: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.controllers = controllers
        self.maps_list = maps_list
        self.on_toggle_slot = on_toggle_slot
        self.on_toggle_all = on_toggle_all
        self.on_save_slot_config = on_save_slot_config
        self.on_connect_all = on_connect_all
        self.on_assign_all = on_assign_all
        self.on_refresh_games = on_refresh_games
        self.on_arrange_windows = on_arrange_windows
        self.on_slot_pid_selected = on_slot_pid_selected
        self.on_slot_profile_selected = on_slot_profile_selected
        self.on_stack_jewels = on_stack_jewels
        self.on_devil_config = on_devil_config
        self.on_close_games = on_close_games
        self.on_open_stat_dialog = on_open_stat_dialog

        self.cards: Dict[int, CompactSlotCard] = {}
        self.profile_options = CompactSlotCard.get_default_profile_options()

        self._build_summary()
        self._build_toolbar()
        self._build_slots_list()

    def _build_summary(self):
        summary = ctk.CTkFrame(self, fg_color="transparent")
        summary.pack(fill="x", padx=12, pady=(10, 4))

        left = ctk.CTkFrame(summary, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left,
            text="Auto Train Control Deck",
            font=Fonts.SECTION,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Quản lý 10 slot · kết nối · gán PID · bật/tắt auto",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM
        ).pack(anchor="w")

        right = ctk.CTkFrame(summary, fg_color="transparent")
        right.pack(side="right")

        self.lbl_slot_summary = ctk.CTkLabel(
            right,
            text="0 running · 0 connected · 10 slots",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_slot_summary.pack(side="right", pady=8)

    def _build_toolbar(self):
        tb = ToolbarBar(self, height=50)
        tb.pack(fill="x", padx=12, pady=(4, 8))

        self.btn_connect_all = make_action_button(
            tb.left,
            "Kết Nối Tất Cả",
            self._handle_connect_all,
            image=UiIconFactory.get("link", color=Colors.CYAN, size=(13, 13)),
            tone="primary",
            height=30,
        )
        self.btn_connect_all.pack(side="left", padx=(0, 6), pady=10)

        self.btn_assign_all = make_action_button(
            tb.left,
            "Gán Toàn Bộ",
            self._handle_assign_all,
            image=UiIconFactory.get("users", color=Colors.CYAN, size=(13, 13)),
            tone="primary",
            height=30,
        )
        self.btn_assign_all.pack(side="left", padx=(0, 6), pady=10)

        self.btn_refresh = make_action_button(
            tb.left,
            "Làm Mới",
            self._handle_refresh_games,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(13, 13)),
            tone="neutral",
            height=30,
        )
        self.btn_refresh.pack(side="left", padx=(0, 6), pady=10)

        # Sắp xếp / Đóng Game nằm ở thanh sticky global — chỉ hiện ở đây nếu caller truyền callback
        self.btn_arrange_windows = None
        if self.on_arrange_windows:
            self.btn_arrange_windows = make_action_button(
                tb.left,
                "Sắp Xếp",
                self._handle_arrange_windows,
                image=UiIconFactory.get("grid", color=Colors.PURPLE, size=(13, 13)),
                tone="purple",
                height=30,
            )
            self.btn_arrange_windows.pack(side="left", padx=(0, 6), pady=10)

        self.btn_stack_jewels = make_action_button(
            tb.left,
            "Gom Ngọc",
            self._handle_stack_jewels,
            image=UiIconFactory.get("gem", color=Colors.PURPLE, size=(13, 13)),
            tone="purple",
            height=30,
        )
        self.btn_stack_jewels.pack(side="left", padx=(0, 6), pady=10)

        self.btn_devil_config = make_action_button(
            tb.left,
            "Devil",
            self._handle_devil_config,
            image=UiIconFactory.get("fire", color="#f43f5e", size=(13, 13)),
            tone="fire",
            height=30,
        )
        self.btn_devil_config.pack(side="left", padx=(0, 6), pady=10)

        self.btn_close_all_games = None
        if self.on_close_games:
            self.btn_close_all_games = make_action_button(
                tb.left,
                "Đóng Game",
                self._handle_close_games,
                image=UiIconFactory.get("stop", color="#f87171", size=(13, 13)),
                tone="danger",
                height=30,
            )
            self.btn_close_all_games.pack(side="left", padx=(0, 6), pady=10)

        self.btn_master_run = make_action_button(
            tb.right,
            "▶ BẬT TẤT CẢ",
            lambda: self._handle_toggle_all(True),
            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)),
            tone="success",
            width=126,
            height=30,
        )
        self.btn_master_run.pack(side="right", padx=(4, 0), pady=10)

        self.btn_master_stop = make_action_button(
            tb.right,
            "⏹ DỪNG TẤT CẢ",
            lambda: self._handle_toggle_all(False),
            image=UiIconFactory.get("stop", color="#ffffff", size=(12, 12)),
            tone="danger",
            width=126,
            height=30,
        )
        self.btn_master_stop.pack(side="right", padx=(0, 4), pady=10)

    def _build_slots_list(self):
        deck = SectionCard(self, title=None)
        deck.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        deck.configure(fg_color=Colors.BG_SURFACE_ELEVATED)

        self.scroll_frame = ctk.CTkScrollableFrame(
            deck.body,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True)

        for i in range(1, 11):
            card = CompactSlotCard(
                self.scroll_frame,
                slot_idx=i,
                on_toggle_run=self._handle_toggle_slot,
                on_open_settings=self._handle_open_settings,
                on_change_process=self.on_slot_pid_selected,
                on_change_profile=self.on_slot_profile_selected,
                profile_options=self.profile_options
            )
            card.pack(fill="x", pady=3)
            self.cards[i] = card

    def update_slots_data(self, dirty_slots: List[Dict[str, Any]]):
        running = 0
        connected = 0
        for s_data in dirty_slots:
            idx = s_data.get("slot_idx")
            if idx in self.cards:
                self.cards[idx].update_state(s_data)
        for card in self.cards.values():
            if getattr(card, "_is_running", False):
                running += 1
            if card.proc_var.get() not in ("--", "", "Chọn..."):
                connected += 1
        self.lbl_slot_summary.configure(
            text=f"{running} running · {connected} connected · {len(self.cards)} slots"
        )

    def update_process_options_all(self, options: List[str]):
        new_opts = list(options or ["--"])
        if new_opts == getattr(self, "_last_proc_options", None):
            return
        self._last_proc_options = new_opts
        for card in self.cards.values():
            card.set_process_options(new_opts)

    def update_profile_options_all(self, options: List[str]):
        new_opts = list(options or [])
        if new_opts == getattr(self, "profile_options", None):
            return
        self.profile_options = new_opts
        for card in self.cards.values():
            card.set_profile_options(new_opts)

    def _handle_toggle_slot(self, slot_idx: int):
        if self.on_toggle_slot:
            self.on_toggle_slot(slot_idx)

    def _handle_toggle_all(self, start_all: bool):
        if self.on_toggle_all:
            self.on_toggle_all(start_all)

    def _handle_connect_all(self):
        if self.on_connect_all:
            self.on_connect_all()

    def _handle_assign_all(self):
        if self.on_assign_all:
            self.on_assign_all()

    def _handle_refresh_games(self):
        if self.on_refresh_games:
            self.on_refresh_games()

    def _handle_arrange_windows(self):
        if self.on_arrange_windows:
            self.on_arrange_windows()

    def _handle_stack_jewels(self):
        if self.on_stack_jewels:
            self.on_stack_jewels()

    def _handle_devil_config(self):
        if self.on_devil_config:
            self.on_devil_config()

    def _handle_close_games(self):
        if self.on_close_games:
            self.on_close_games()

    def _handle_open_settings(self, slot_idx: int):
        ctrl = None
        for c in self.controllers:
            if getattr(c, "slot_idx", None) == slot_idx:
                ctrl = c
                break

        cfg = {
            "map": getattr(ctrl, "spot_map", "Lorencia") if ctrl else "Lorencia",
            "x": getattr(ctrl, "spot_x", 125) if ctrl else 125,
            "y": getattr(ctrl, "spot_y", 125) if ctrl else 125,
            "auto_repair": getattr(ctrl, "auto_repair", True) if ctrl else True,
            "auto_clean_trash": getattr(ctrl, "auto_clean_trash", True) if ctrl else True,
            "mirror_enabled": getattr(ctrl, "mirror_enabled", True) if ctrl else True,
            "moss_enabled": getattr(ctrl, "moss_enabled", True) if ctrl else True,
        }

        SlotSettingsModal(
            self.winfo_toplevel(),
            slot_idx=slot_idx,
            current_config=cfg,
            maps_list=self.maps_list,
            on_save=self._on_save_slot_settings,
            on_open_advanced=self.on_open_stat_dialog
        )

    def _on_save_slot_settings(self, slot_idx: int, new_cfg: Dict[str, Any]):
        if self.on_save_slot_config:
            self.on_save_slot_config(slot_idx, new_cfg)
