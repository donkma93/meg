# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - TRAIN SLOTS VIEW
Giao diện quản lý 10 Slot Auto Train tối giản, siêu mượt, không đơ lag.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory
from ui.components.cards import CompactSlotCard
from ui.modals.slot_settings import SlotSettingsModal

class TrainSlotsView(ctk.CTkFrame):
    """View hiển thị 10 thẻ Slot mượt mà với thanh tác vụ tổng."""

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

        self._build_toolbar()
        self._build_slots_list()

    def _build_toolbar(self):
        """Thanh công cụ tác vụ nhanh trên đỉnh màn hình Auto Train."""
        tb = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, height=44, corner_radius=4)
        tb.pack(fill="x", padx=12, pady=(8, 6))
        tb.pack_propagate(False)

        # Cột Trái: Các nút thao tác game nhanh
        left_f = ctk.CTkFrame(tb, fg_color="transparent")
        left_f.pack(side="left", fill="y", padx=8)

        # 1. Kết nối tất cả
        self.btn_connect_all = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("link", color="#38bdf8", size=(13, 13)),
            compound="left",
            text="Kết Nối Tất Cả",
            font=Fonts.BODY_BOLD,
            fg_color="#0f2b48",
            hover_color="#143e69",
            border_width=1,
            border_color="#0284c7",
            height=28,
            corner_radius=2,
            command=self._handle_connect_all
        )
        self.btn_connect_all.pack(side="left", padx=(0, 6), pady=8)

        # 2. Gán toàn bộ
        self.btn_assign_all = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("users", color="#38bdf8", size=(13, 13)),
            compound="left",
            text="Gán Toàn Bộ",
            font=Fonts.BODY_BOLD,
            fg_color="#0f2b48",
            hover_color="#143e69",
            border_width=1,
            border_color="#0284c7",
            height=28,
            corner_radius=2,
            command=self._handle_assign_all
        )
        self.btn_assign_all.pack(side="left", padx=(0, 6), pady=8)

        # 3. Làm mới
        self.btn_refresh = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(13, 13)),
            compound="left",
            text="Làm Mới",
            font=Fonts.BODY,
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            height=28,
            corner_radius=2,
            command=self._handle_refresh_games
        )
        self.btn_refresh.pack(side="left", padx=(0, 6), pady=8)

        # 4. Sắp xếp cửa sổ
        self.btn_arrange_windows = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("grid", color="#c084fc", size=(13, 13)),
            compound="left",
            text="Sắp Xếp",
            font=Fonts.BODY,
            fg_color="#261b3d",
            hover_color="#3b2b5d",
            border_width=1,
            border_color="#7c3aed",
            height=28,
            corner_radius=2,
            command=self._handle_arrange_windows
        )
        self.btn_arrange_windows.pack(side="left", padx=(0, 6), pady=8)

        # 5. Gom ngọc
        self.btn_stack_jewels = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("gem", color="#c084fc", size=(13, 13)),
            compound="left",
            text="Gom Ngọc",
            font=Fonts.BODY,
            fg_color="#2e1065",
            hover_color="#3b0764",
            border_width=1,
            border_color="#7e22ce",
            height=28,
            corner_radius=2,
            command=self._handle_stack_jewels
        )
        self.btn_stack_jewels.pack(side="left", padx=(0, 6), pady=8)

        # 6. Cài đặt Devil
        self.btn_devil_config = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("fire", color="#f43f5e", size=(13, 13)),
            compound="left",
            text="Devil",
            font=Fonts.BODY,
            fg_color="#450a0a",
            hover_color="#7f1d1d",
            border_width=1,
            border_color="#be123c",
            height=28,
            corner_radius=2,
            command=self._handle_devil_config
        )
        self.btn_devil_config.pack(side="left", padx=(0, 6), pady=8)

        # 7. Đóng Game
        self.btn_close_all_games = ctk.CTkButton(
            left_f,
            image=UiIconFactory.get("stop", color="#f87171", size=(13, 13)),
            compound="left",
            text="Đóng Game",
            font=Fonts.BODY,
            fg_color="#3a1215",
            hover_color="#5c1d24",
            border_width=1,
            border_color="#991b1b",
            height=28,
            corner_radius=2,
            command=self._handle_close_games
        )
        self.btn_close_all_games.pack(side="left", padx=(0, 6), pady=8)

        # Cột Phải: Các nút điều khiển tổng Bật/Dừng
        right_f = ctk.CTkFrame(tb, fg_color="transparent")
        right_f.pack(side="right", fill="y", padx=8)

        self.btn_master_run = ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)),
            compound="left",
            text="▶ BẬT TẤT CẢ",
            font=Fonts.BODY_BOLD,
            fg_color=Colors.GREEN,
            hover_color=Colors.GREEN_HOVER,
            width=110,
            height=28,
            corner_radius=2,
            command=lambda: self._handle_toggle_all(True)
        )
        self.btn_master_run.pack(side="right", padx=(4, 0), pady=8)

        self.btn_master_stop = ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("stop", color="#ffffff", size=(12, 12)),
            compound="left",
            text="⏹ DỪNG TẤT CẢ",
            font=Fonts.BODY_BOLD,
            fg_color=Colors.ROSE,
            hover_color=Colors.ROSE_HOVER,
            width=110,
            height=28,
            corner_radius=2,
            command=lambda: self._handle_toggle_all(False)
        )
        self.btn_master_stop.pack(side="right", padx=(0, 4), pady=8)

    def _build_slots_list(self):
        """Khung cuộn chứa 10 Slot Cards."""
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Khởi tạo 10 thẻ Slot MỘT LẦN DUY NHẤT (Zero Destroy)
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
            card.pack(fill="x", pady=2)
            self.cards[i] = card

    def update_slots_data(self, dirty_slots: List[Dict[str, Any]]):
        """Cập nhật dữ liệu vào thẻ In-Place (Chống lag 100%)."""
        for s_data in dirty_slots:
            idx = s_data.get("slot_idx")
            if idx in self.cards:
                self.cards[idx].update_state(s_data)

    def update_process_options_all(self, options: List[str]):
        """Cập nhật danh sách options game vào cả 10 thẻ slot."""
        for card in self.cards.values():
            card.set_process_options(options)

    def update_profile_options_all(self, options: List[str]):
        """Cập nhật toàn bộ danh sách profile vào cả 10 thẻ slot."""
        self.profile_options = options
        for card in self.cards.values():
            card.set_profile_options(options)

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
