# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - TRAIN SLOTS VIEW
Dense dashboard of Auto Train slot cards + icon-optimized action toolbar.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.cards import CompactSlotCard
from ui.components.dropdown import ModernDropdown
from ui.components.shell import ToolbarBar, make_action_button, bind_mousewheel_to_scrollable
from ui.components.tooltip import attach_tooltip


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
        on_arrange_windows: Optional[Callable[[Optional[str]], None]] = None,
        on_slot_pid_selected: Optional[Callable[[int, str], None]] = None,
        on_slot_profile_selected: Optional[Callable[[int, str], None]] = None,
        on_stack_jewels: Optional[Callable[[], None]] = None,
        on_devil_config: Optional[Callable[[], None]] = None,
        on_point_config: Optional[Callable[[], None]] = None,
        on_toggle_point: Optional[Callable[[int], None]] = None,
        on_open_point_config: Optional[Callable[[int], None]] = None,
        on_close_games: Optional[Callable[[], None]] = None,
        on_open_stat_dialog: Optional[Callable[[int], None]] = None,
        on_add_slot: Optional[Callable[[], None]] = None,
        on_remove_slot: Optional[Callable[[], None]] = None,
        on_telegram_config: Optional[Callable[[], None]] = None,
        on_import_accounts: Optional[Callable[[], None]] = None,
        on_party_config: Optional[Callable[[], None]] = None,
        on_slot_delay_changed: Optional[Callable[[int, float], None]] = None,
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
        self.on_point_config = on_point_config
        self.on_toggle_point = on_toggle_point
        self.on_open_point_config = on_open_point_config
        self.on_close_games = on_close_games
        self.on_open_stat_dialog = on_open_stat_dialog
        self.on_add_slot = on_add_slot
        self.on_remove_slot = on_remove_slot
        self.on_telegram_config = on_telegram_config
        self.on_import_accounts = on_import_accounts
        self.on_party_config = on_party_config
        self.on_slot_delay_changed = on_slot_delay_changed

        self.cards: Dict[int, CompactSlotCard] = {}
        self.profile_options = CompactSlotCard.get_default_profile_options()

        self._build_toolbar()
        self._build_shared_utilities_bar()
        self._build_data_table()

    def _build_toolbar(self):
        tb = ToolbarBar(self, height=42)
        tb.pack(fill="x", padx=10, pady=(6, 4))

        # --- Nhóm 1: Master Controls Bên Phải (Ghim trước tiên để luôn hiển thị 100%) ---
        self.btn_master_stop = make_action_button(
            tb.right,
            "DỪNG TẤT CẢ",
            lambda: self._handle_toggle_all(False),
            image=UiIconFactory.get("stop", color="#ffffff", size=(11, 11)),
            tone="danger",
            width=105,
            height=28,
        )
        self.btn_master_stop.pack(side="right", padx=(4, 0), pady=7)
        attach_tooltip(self.btn_master_stop, "Dừng Auto Train trên toàn bộ các slot")

        self.btn_master_run = make_action_button(
            tb.right,
            "BẬT TẤT CẢ",
            lambda: self._handle_toggle_all(True),
            image=UiIconFactory.get("play", color="#ffffff", size=(11, 11)),
            tone="success",
            width=105,
            height=28,
        )
        self.btn_master_run.pack(side="right", padx=(4, 4), pady=7)
        attach_tooltip(self.btn_master_run, "Khởi động Auto Train trên toàn bộ các slot đã kết nối")

        self.lbl_slot_summary = ctk.CTkLabel(
            tb.right,
            text="🟢 0/0 Đang chạy  ·  🔗 0/0 Đã nối",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_slot_summary.pack(side="right", padx=(0, 10), pady=7)

        # --- Nhóm 2: Nhận diện & Kết nối Game ---
        self.btn_refresh = make_action_button(
            tb.left,
            "Quét Game",
            self._handle_refresh_games,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(13, 13)),
            tone="neutral",
            width=86,
            height=28,
        )
        self.btn_refresh.pack(side="left", padx=(0, 4), pady=7)
        attach_tooltip(self.btn_refresh, "Quét lại danh sách tiến trình game MEGAMU đang chạy")

        self.btn_assign_all = make_action_button(
            tb.left,
            "Gán All",
            self._handle_assign_all,
            image=UiIconFactory.get("users", color=Colors.CYAN, size=(13, 13)),
            tone="neutral",
            width=72,
            height=28,
        )
        self.btn_assign_all.pack(side="left", padx=(0, 4), pady=7)
        attach_tooltip(self.btn_assign_all, "Tự động phân bổ cửa sổ game vào các slot")

        self.btn_connect_all = make_action_button(
            tb.left,
            "Nối All",
            self._handle_connect_all,
            image=UiIconFactory.get("link", color=Colors.CYAN, size=(13, 13)),
            tone="neutral",
            width=72,
            height=28,
        )
        self.btn_connect_all.pack(side="left", padx=(0, 5), pady=7)
        attach_tooltip(self.btn_connect_all, "Kích hoạt engine kết nối bộ nhớ cho toàn bộ game")

        # Separator
        ctk.CTkFrame(tb.left, fg_color=Colors.BORDER_CARD, width=1, height=18).pack(side="left", padx=5, pady=12)

        # --- Nhóm 3: Cửa sổ Multi-Client ---
        self.arrange_var = ctk.StringVar(value="3x2")
        self.arrange_combo = ModernDropdown(
            tb.left,
            values=["3x2", "2x2", "3x3", "4x2", "2x1", "1x2", "4x3"],
            variable=self.arrange_var,
            width=54,
            height=28,
            fg_color=Colors.BG_CARD,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY_BOLD,
            popup_min_width=85
        )
        self.arrange_combo.pack(side="left", padx=(2, 3), pady=7)
        attach_tooltip(self.arrange_combo, "Chọn bố cục chia màn hình (cột x dòng)")

        self.btn_arrange_windows = make_action_button(
            tb.left,
            "Xếp",
            self._handle_arrange_windows,
            image=UiIconFactory.get("grid", color=Colors.PURPLE, size=(13, 13)),
            tone="neutral",
            width=58,
            height=28,
        )
        self.btn_arrange_windows.pack(side="left", padx=(0, 4), pady=7)
        attach_tooltip(self.btn_arrange_windows, "Tự động sắp xếp các cửa sổ game theo lưới")

        self.btn_close_all_games = make_action_button(
            tb.left,
            "Đóng",
            self._handle_close_games,
            image=UiIconFactory.get("close", color="#f87171", size=(13, 13)),
            tone="neutral",
            width=60,
            height=28,
        )
        self.btn_close_all_games.pack(side="left", padx=(0, 5), pady=7)
        attach_tooltip(self.btn_close_all_games, "Đóng toàn bộ cửa sổ game MEGAMU đang mở")

        # Separator
        ctk.CTkFrame(tb.left, fg_color=Colors.BORDER_CARD, width=1, height=18).pack(side="left", padx=5, pady=12)

        # --- Nhóm 4: Quản lý Slot ---
        self.btn_add_slot = make_action_button(
            tb.left,
            "+ Slot",
            self._handle_add_slot,
            image=UiIconFactory.get("plus", color="#4ade80", size=(12, 12)),
            tone="neutral",
            width=64,
            height=28,
        )
        self.btn_add_slot.pack(side="left", padx=(2, 3), pady=7)
        attach_tooltip(self.btn_add_slot, "Thêm 1 slot điều khiển mới (theo hạn mức License)")

        self.btn_remove_slot = make_action_button(
            tb.left,
            "- Slot",
            self._handle_remove_slot,
            image=UiIconFactory.get("minus", color="#f87171", size=(12, 12)),
            tone="neutral",
            width=64,
            height=28,
        )
        self.btn_remove_slot.pack(side="left", padx=(0, 5), pady=7)
        attach_tooltip(self.btn_remove_slot, "Xóa slot điều khiển cuối cùng")

    def _build_shared_utilities_bar(self):
        """Thanh Tiện Ích Dùng Chung (Shared Utilities Bar) gom toàn bộ tính năng dùng chung của Auto Train."""
        util_bar = ctk.CTkFrame(
            self,
            fg_color="#0b1322",
            height=34,
            corner_radius=Radii.SM,
            border_width=1,
            border_color="#1e293b"
        )
        util_bar.pack(fill="x", padx=10, pady=(0, 6))
        util_bar.pack_propagate(False)

        # Tiêu đề nhóm tiện ích dùng chung
        lbl_group = ctk.CTkLabel(
            util_bar,
            text="⚡ TIỆN ÍCH DÙNG CHUNG:",
            font=("Segoe UI", 10, "bold"),
            text_color=Colors.CYAN
        )
        lbl_group.pack(side="left", padx=(10, 8), pady=4)

        # 1. Gom Ngọc
        self.btn_stack_jewels = make_action_button(
            util_bar,
            "Gom Ngọc",
            self._handle_stack_jewels,
            image=UiIconFactory.get("gem", color=Colors.PURPLE, size=(13, 13)),
            tone="neutral",
            height=24,
        )
        self.btn_stack_jewels.pack(side="left", padx=(0, 6), pady=5)
        attach_tooltip(self.btn_stack_jewels, "Gom Ngọc: Tự động nén và gom tất cả loại ngọc trong túi đồ")

        # 2. Devil Square
        self.btn_devil_config = make_action_button(
            util_bar,
            "Devil Square",
            self._handle_devil_config,
            image=UiIconFactory.get("fire", color="#f43f5e", size=(13, 13)),
            tone="neutral",
            height=24,
        )
        self.btn_devil_config.pack(side="left", padx=(0, 6), pady=5)
        attach_tooltip(self.btn_devil_config, "Devil Square: Cài đặt lịch trình & tự động tham gia sự kiện")

        # 3. Cộng Point
        self.btn_point_config = make_action_button(
            util_bar,
            "Cộng Point",
            self._handle_point_config,
            image=UiIconFactory.get("star", color="#38bdf8", size=(13, 13)),
            tone="neutral",
            height=24,
        )
        self.btn_point_config.pack(side="left", padx=(0, 6), pady=5)
        attach_tooltip(self.btn_point_config, "Cộng Point: Cài đặt tự động cộng điểm tiềm năng theo Class hoặc Tùy chỉnh cho tất cả các slot")

        # 4. Auto Party
        if self.on_party_config:
            self.btn_party = make_action_button(
                util_bar,
                "Auto PT",
                self.on_party_config,
                image=UiIconFactory.get("party", color="#c084fc", size=(13, 13)),
                tone="neutral",
                height=24,
            )
            self.btn_party.pack(side="left", padx=(0, 6), pady=5)
            attach_tooltip(self.btn_party, "Auto PT: Tự động mời hoặc nhận nhóm Party theo mật khẩu")

        # 4. Telegram Bot
        if self.on_telegram_config:
            self.btn_telegram = make_action_button(
                util_bar,
                "Telegram Bot",
                self.on_telegram_config,
                image=UiIconFactory.get("telegram", color=Colors.CYAN, size=(13, 13)),
                tone="neutral",
                height=24,
            )
            self.btn_telegram.pack(side="left", padx=(0, 6), pady=5)
            attach_tooltip(self.btn_telegram, "Telegram: Cài đặt thông báo & cảnh báo qua Telegram Bot")

        # 5. Import Tài Khoản
        if self.on_import_accounts:
            self.btn_import_accounts = make_action_button(
                util_bar,
                "Nhập Tài Khoản",
                self.on_import_accounts,
                image=UiIconFactory.get("import", color="#cbd5e1", size=(13, 13)),
                tone="neutral",
                height=24,
            )
            self.btn_import_accounts.pack(side="left", padx=(0, 6), pady=5)
            attach_tooltip(self.btn_import_accounts, "Nhập Tài Khoản: Nhập danh sách tài khoản từ Registry hoặc File")

    def _build_data_table(self):
        """Khung Bảng Dữ Liệu Đích Thực (True Data Table Container) thống nhất, phẳng và chuẩn xác."""
        self.table_container = ctk.CTkFrame(
            self,
            fg_color="#0a101d",
            border_width=1,
            border_color="#1e293b",
            corner_radius=Radii.SM
        )
        self.table_container.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # 1. Dòng Tiêu Đề Bảng Liền Khối (Table Header <thead>)
        self._build_table_header(self.table_container)

        # 2. Thân Bảng Dữ Liệu (Table Body <tbody>)
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.table_container,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True)
        bind_mousewheel_to_scrollable(self.scroll_frame)

        slot_indices = [c.slot_idx for c in self.controllers] if self.controllers else list(range(1, 11))
        for i in slot_indices:
            self._create_card(i)
        self._update_summary_count()

    def _build_table_header(self, parent):
        """Dòng tiêu đề bảng liền khối có vạch chia cột chuẩn."""
        hdr = ctk.CTkFrame(parent, fg_color="#0e172a", height=30, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Cột Thao tác bên phải (176px)
        ctk.CTkLabel(
            hdr,
            text="Thao tác",
            font=("Segoe UI", 10, "bold"),
            text_color="#94a3b8",
            width=176,
            anchor="center"
        ).pack(side="right", padx=(2, 8))

        # Các cột bên trái
        def _add_th(title, w, anchor="w", padx=4):
            ctk.CTkLabel(
                hdr,
                text=title,
                font=("Segoe UI", 10, "bold"),
                text_color="#94a3b8",
                width=w,
                anchor=anchor
            ).pack(side="left", padx=padx)
            ctk.CTkFrame(hdr, fg_color="#182234", width=1, height=14).pack(side="left", pady=8)

        # Offset dải màu 3px
        ctk.CTkFrame(hdr, fg_color="transparent", width=4).pack(side="left")

        _add_th("#", 38, anchor="center", padx=1)
        _add_th("Hệ", 44, anchor="center", padx=2)
        _add_th("Tiến trình Game (PID)", 180, anchor="w", padx=4)
        _add_th("Cấu hình", 105, anchor="w", padx=4)
        _add_th("Cấp độ / RS", 95, anchor="w", padx=4)
        _add_th("Bản đồ & Tọa độ", 155, anchor="w", padx=4)
        _add_th("Server", 45, anchor="center", padx=2)
        _add_th("Chờ ra bãi", 80, anchor="center", padx=3)
        _add_th("Trạng thái", 100, anchor="w", padx=4)

        # Đệm co giãn linh hoạt ở giữa
        ctk.CTkFrame(hdr, fg_color="transparent").pack(side="left", fill="both", expand=True)

        # Đường kẻ đáy hairline ngăn cách Header với thân bảng
        ctk.CTkFrame(parent, fg_color="#1e293b", height=1, corner_radius=0).pack(fill="x")

    def _create_card(self, i: int) -> CompactSlotCard:
        card = CompactSlotCard(
            self.scroll_frame,
            slot_idx=i,
            on_toggle_run=self._handle_toggle_slot,
            on_open_settings=self._handle_open_settings,
            on_change_process=self.on_slot_pid_selected,
            on_change_profile=self.on_slot_profile_selected,
            profile_options=self.profile_options,
            on_toggle_point=self.on_toggle_point,
            on_open_point_config=self.on_open_point_config,
            on_change_delay=self.on_slot_delay_changed
        )
        card.pack(fill="x", pady=0)
        if hasattr(self, "_last_proc_options") and self._last_proc_options:
            card.set_process_options(self._last_proc_options)
        self.cards[i] = card
        return card

    def set_slot_respawn_delay(self, slot_idx: int, val: float):
        if slot_idx in self.cards:
            self.cards[slot_idx].set_respawn_delay(val)

    def add_slot_card(self, slot_idx: int):
        if slot_idx in self.cards:
            return
        self._create_card(slot_idx)
        self._update_summary_count()

    def remove_last_card(self):
        if not self.cards:
            return
        last_idx = max(self.cards.keys())
        card = self.cards.pop(last_idx, None)
        if card:
            try:
                card.destroy()
            except Exception:
                pass
        self._update_summary_count()

    def _update_summary_count(self):
        running = sum(1 for card in self.cards.values() if getattr(card, "_is_running", False))
        connected = sum(1 for card in self.cards.values() if card.proc_var.get() not in ("--", "", "Chọn..."))
        total = len(self.cards)
        summary_txt = f"🟢 {running}/{total} Đang chạy  ·  🔗 {connected}/{total} Đã nối"
        if getattr(self, "_last_summary_text", None) == summary_txt:
            return
        self._last_summary_text = summary_txt
        if hasattr(self, "lbl_slot_summary") and self.lbl_slot_summary:
            self.lbl_slot_summary.configure(text=summary_txt)

    def update_slots_data(self, dirty_slots: List[Dict[str, Any]]):
        for s_data in dirty_slots:
            idx = s_data.get("slot_idx")
            if idx in self.cards:
                self.cards[idx].update_state(s_data)
        self._update_summary_count()

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

    def _handle_add_slot(self):
        if self.on_add_slot:
            self.on_add_slot()

    def _handle_remove_slot(self):
        if self.on_remove_slot:
            self.on_remove_slot()

    def _handle_arrange_windows(self):
        if self.on_arrange_windows:
            preset = getattr(self, "arrange_var", None)
            val = preset.get().strip() if preset else "3x2"
            try:
                self.on_arrange_windows(val)
            except TypeError:
                self.on_arrange_windows()

    def _handle_stack_jewels(self):
        if self.on_stack_jewels:
            self.on_stack_jewels()

    def _handle_devil_config(self):
        if self.on_devil_config:
            self.on_devil_config()

    def _handle_point_config(self):
        if self.on_point_config:
            self.on_point_config()

    def _handle_close_games(self):
        if self.on_close_games:
            self.on_close_games()

    def _handle_open_settings(self, slot_idx: int):
        """Chuyển trực tiếp sang Tab 02 Config và nạp đúng Profile của Slot này."""
        if self.on_open_stat_dialog:
            self.on_open_stat_dialog(slot_idx)

    def _on_save_slot_settings(self, slot_idx: int, new_cfg: Dict[str, Any]):
        if self.on_save_slot_config:
            self.on_save_slot_config(slot_idx, new_cfg)
