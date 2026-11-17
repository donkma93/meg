# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - MOSS VIEW (COMPACT)
Dense ops layout: thin countdown · tools · table · status log.
"""

from typing import Callable, Optional, Dict, Any, List, Tuple
import time
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.shell import make_action_button, bind_mousewheel_to_scrollable
from ui.components.dropdown import ModernDropdown

try:
    from meg_gui import ModernActionMenu
except ImportError:
    ModernActionMenu = None


MOSS_CAT_OPTIONS: List[Tuple[str, int]] = [
    ("[ZEN] 0: Kiếm (Swords)", 0),
    ("[ZEN] 1: Chùy & Trượng", 1),
    ("[ZEN] 2: Cung & Nỏ", 2),
    ("[ZEN] 3: Gậy Phép", 3),
    ("[ZEN] 4: Khiên (Shields)", 4),
    ("[ZEN] 5: Trang Sức & Khác", 5),
    ("[NGỌC] 6: 2 Soul", 6),
    ("[NGỌC] 7: 10 Soul", 7),
    ("[NGỌC] 8: 2 Bless", 8),
    ("[NGỌC] 9: 10 Bless", 9),
    ("[NGỌC] 10: 2 Chaos", 10),
    ("[NGỌC] 11: 10 Chaos", 11),
]


def moss_cat_name(cat_id: int) -> str:
    for name, cid in MOSS_CAT_OPTIONS:
        if cid == cat_id:
            return name
    return f"{cat_id}: Category {cat_id}"


def moss_cat_id(cat_name: str) -> int:
    for name, cid in MOSS_CAT_OPTIONS:
        if name == cat_name:
            return cid
    try:
        return int(str(cat_name).split(":")[0].split("]")[-1].strip().split()[0])
    except Exception:
        return 0


class MossView(ctk.CTkFrame):
    """Tab Moss gọn: ưu tiên bảng slot + nhật ký trạng thái."""

    def __init__(
        self,
        parent,
        controllers: list,
        on_trigger_moss: Optional[Callable[[], None]] = None,
        on_stop_moss: Optional[Callable[[], None]] = None,
        on_toggle_participant: Optional[Callable[[int, bool], None]] = None,
        on_save_schedule: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_apply_moss_batch: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_clean_moss: Optional[Callable[[], None]] = None,
        on_sell_moss: Optional[Callable[[], None]] = None,
        on_analyze_moss: Optional[Callable[[], None]] = None,
        on_open_junk_dialog: Optional[Callable[[], None]] = None,
        on_moss_slot_category: Optional[Callable[[int, str], None]] = None,
        on_moss_slot_delay: Optional[Callable[[int, int], None]] = None,
        on_toggle_moss_slot: Optional[Callable[[int], None]] = None,
        on_moss_row_action: Optional[Callable[[int, str], None]] = None,
        on_moss_batch_tool: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.controllers = controllers
        self.on_trigger_moss = on_trigger_moss
        self.on_stop_moss = on_stop_moss
        self.on_toggle_participant = on_toggle_participant
        self.on_save_schedule = on_save_schedule
        self.on_apply_moss_batch = on_apply_moss_batch
        self.on_clean_moss = on_clean_moss
        self.on_sell_moss = on_sell_moss
        self.on_analyze_moss = on_analyze_moss
        self.on_open_junk_dialog = on_open_junk_dialog
        self.on_moss_slot_category = on_moss_slot_category
        self.on_moss_slot_delay = on_moss_slot_delay
        self.on_toggle_moss_slot = on_toggle_moss_slot
        self.on_moss_row_action = on_moss_row_action
        self.on_moss_batch_tool = on_moss_batch_tool

        self.moss_cb_vars: Dict[int, ctk.BooleanVar] = {}
        self.moss_ui_elements: Dict[int, Dict[str, Any]] = {}
        self._row_menus: Dict[int, Any] = {}

        self.var_moss_auto = ctk.BooleanVar(value=True)
        self.var_moss_move = ctk.BooleanVar(value=True)
        self.var_moss_auto_clean = ctk.BooleanVar(value=True)
        self.var_moss_clean_equip = ctk.BooleanVar(value=True)

        self._build_layout()

    def _build_layout(self):
        self._build_status_strip()
        self._build_tools_row()
        self._build_schedule_row()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        body.grid_rowconfigure(0, weight=3)
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._build_table(body)
        self._build_log_panel(body)

    def _build_status_strip(self):
        strip = ctk.CTkFrame(
            self, fg_color="#0a101d", border_width=1,
            border_color="#14532d", corner_radius=Radii.SM, height=42
        )
        strip.pack(fill="x", padx=10, pady=(8, 4))
        strip.pack_propagate(False)

        # Huy hiệu Moss Merchant nổi bật
        badge = ctk.CTkFrame(strip, fg_color="#064e3b", corner_radius=Radii.XS, height=26)
        badge.pack(side="left", padx=(10, 8), pady=8)
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="🎲 MOSS MERCHANT", font=("Segoe UI", 10, "bold"), text_color="#34d399").pack(padx=8, expand=True)

        self.lbl_moss_countdown = ctk.CTkLabel(
            strip, text="00:00:00", font=("Segoe UI", 16, "bold"), text_color="#22c55e", width=82
        )
        self.lbl_moss_countdown.pack(side="left", padx=(0, 10))

        self.lbl_moss_status = ctk.CTkLabel(strip, text="● Chờ sự kiện", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MUTED)
        self.lbl_moss_status.pack(side="left", padx=(0, 12))

        self.lbl_moss_next = ctk.CTkLabel(strip, text="🕒 Đợt kế: 00:15 / 06:15 / 12:15 / 18:15", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM)
        self.lbl_moss_next.pack(side="left")

        self.lbl_moss_count_badge = ctk.CTkLabel(strip, text="🟢 0/0 slot tham gia", font=Fonts.BODY_BOLD, text_color=Colors.AMBER)
        self.lbl_moss_count_badge.pack(side="right", padx=12)

    def _build_tools_row(self):
        bar = ctk.CTkFrame(
            self, fg_color=Colors.BG_SURFACE, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=40
        )
        bar.pack(fill="x", padx=10, pady=(0, 4))
        bar.pack_propagate(False)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="y", padx=6)

        make_action_button(left, "QUAY TẤT CẢ", self._handle_trigger_moss, image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)), tone="success", height=28, width=120).pack(side="left", padx=(2, 4), pady=6)
        make_action_button(left, "DỪNG TẤT CẢ", self._handle_stop_moss, image=UiIconFactory.get("stop", color="#ffffff", size=(11, 11)), tone="danger", height=28, width=115).pack(side="left", padx=(0, 6), pady=6)

        ctk.CTkFrame(left, fg_color=Colors.BORDER_CARD, width=1, height=18).pack(side="left", padx=4, pady=11)

        make_action_button(left, "Phân Tích Hòm", self._handle_analyze_moss, image=UiIconFactory.get("search", color=Colors.CYAN, size=(13, 13)), tone="primary", height=28, width=118).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(left, "Dọn Hòm Đồ", self._handle_junk_dialog, image=UiIconFactory.get("party", color="#c084fc", size=(13, 13)), tone="neutral", height=28, width=105).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(left, "Bán Silvia", self._handle_sell_moss, image=UiIconFactory.get("gem", color="#fbbf24", size=(13, 13)), tone="neutral", height=28, width=98).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(left, "Ném Rác", self._handle_clean_moss, image=UiIconFactory.get("close", color="#f87171", size=(13, 13)), tone="neutral", height=28, width=90).pack(side="left", padx=(0, 4), pady=6)

        make_action_button(bar, "🛠 Tiện Ích Khác ▾", self._show_batch_tools_menu, tone="ghost", height=28, width=130).pack(side="right", padx=8, pady=6)

    def _build_schedule_row(self):
        row = ctk.CTkFrame(
            self, fg_color="#0b1322", border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=36
        )
        row.pack(fill="x", padx=10, pady=(0, 6))
        row.pack_propagate(False)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="y", padx=8)

        for text, var, cmd in (
            ("Tự quay theo giờ", self.var_moss_auto, self._emit_schedule),
            ("Tới NPC Moss", self.var_moss_move, self._emit_schedule),
            ("Tự dọn hòm", self.var_moss_auto_clean, self._emit_moss_batch_flags),
            ("Ném đồ rác", self.var_moss_clean_equip, self._emit_moss_batch_flags),
        ):
            ctk.CTkCheckBox(
                left, text=text, variable=var, font=Fonts.CAPTION,
                checkbox_width=14, checkbox_height=14, command=cmd,
                text_color=Colors.TEXT_MAIN
            ).pack(side="left", padx=(0, 10), pady=6)

        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right", fill="y", padx=8)

        ctk.CTkLabel(right, text="Cài nhanh toàn bộ:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 6), pady=6)

        self.moss_cat_var = ctk.StringVar(value=MOSS_CAT_OPTIONS[0][0])
        self.moss_cat_combo = ModernDropdown(
            right, values=[n for n, _ in MOSS_CAT_OPTIONS], variable=self.moss_cat_var,
            width=180, height=24, fg_color=Colors.BG_SURFACE, border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER, font=Fonts.CAPTION,
            popup_min_width=250,
        )
        self.moss_cat_combo.pack(side="left", padx=(0, 4), pady=6)

        self.moss_delay_var = ctk.StringVar(value="1000")
        ctk.CTkEntry(
            right, textvariable=self.moss_delay_var, width=48, height=24,
            fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.CAPTION, justify="center"
        ).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(right, "Áp Dụng", self._handle_apply_batch, tone="primary", height=24, width=72).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(right, "Chọn Hết", lambda: self._set_all(True), tone="ghost", height=24, width=68).pack(side="left", padx=(0, 2), pady=6)
        make_action_button(right, "Bỏ Hết", lambda: self._set_all(False), tone="ghost", height=24, width=62).pack(side="left", pady=6)

    def _build_table(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color="#0a101d", border_width=1,
            border_color="#1e293b", corner_radius=Radii.SM
        )
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tools = ctk.CTkFrame(card, fg_color="#0e172a", height=30, corner_radius=0)
        tools.pack(fill="x")
        tools.pack_propagate(False)
        ctk.CTkLabel(tools, text="DANH SÁCH TÀI KHOẢN MOSS", font=Fonts.BODY_BOLD, text_color=Colors.CYAN).pack(side="left", padx=10, pady=4)

        # Hairline
        ctk.CTkFrame(card, fg_color="#1e293b", height=1, corner_radius=0).pack(fill="x")

        # Table Header liền khối
        hdr = ctk.CTkFrame(card, fg_color="#0e172a", height=30, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Cột Thao tác bên phải
        ctk.CTkLabel(hdr, text="Thao tác", width=110, anchor="center", font=Fonts.BADGE, text_color="#94a3b8").pack(side="right", padx=(2, 8))

        # Các cột bên trái
        def _add_th(title, w, anchor="w", padx=4):
            ctk.CTkLabel(hdr, text=title, width=w, anchor=anchor, font=Fonts.BADGE, text_color="#94a3b8").pack(side="left", padx=padx)
            ctk.CTkFrame(hdr, fg_color="#182234", width=1, height=14).pack(side="left", pady=8)

        ctk.CTkFrame(hdr, fg_color="transparent", width=2).pack(side="left")
        _add_th("Slot", 58, anchor="center", padx=2)
        _add_th("Nhân vật / PID", 180, anchor="w", padx=4)
        _add_th("Vật phẩm quay (Category)", 220, anchor="w", padx=4)
        _add_th("Delay (ms)", 75, anchor="center", padx=2)
        _add_th("Đã quay", 65, anchor="center", padx=2)
        _add_th("Trạng thái", 110, anchor="w", padx=4)

        ctk.CTkFrame(hdr, fg_color="transparent").pack(side="left", fill="both", expand=True)

        # Hairline giữa Header và thân bảng
        ctk.CTkFrame(card, fg_color="#1e293b", height=1, corner_radius=0).pack(fill="x")

        self.moss_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", corner_radius=0)
        self.moss_scroll.pack(fill="both", expand=True)
        bind_mousewheel_to_scrollable(self.moss_scroll)

        for ctrl in self.controllers:
            self._create_moss_slot_row(ctrl)
        self._update_moss_badge()

    def _build_log_panel(self, parent):
        log_card = ctk.CTkFrame(
            parent, fg_color="#0a101d", border_width=1,
            border_color="#1e293b", corner_radius=Radii.SM, height=140
        )
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.pack_propagate(False)

        head = ctk.CTkFrame(log_card, fg_color="#0e172a", height=28, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text="📋 NHẬT KÝ SỰ KIỆN MOSS", font=Fonts.BODY_BOLD, text_color=Colors.CYAN).pack(side="left", padx=10, pady=3)
        make_action_button(head, "Xóa Log", self.clear_log, tone="ghost", height=22, width=64).pack(side="right", padx=8, pady=3)

        ctk.CTkFrame(log_card, fg_color="#1e293b", height=1, corner_radius=0).pack(fill="x")

        self.log_box = ctk.CTkTextbox(
            log_card, font=Fonts.MONO, fg_color=Colors.BG_INPUT,
            text_color=Colors.TEXT_MAIN, border_width=0, wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=6, pady=4)
        self.log_box.configure(state="disabled")

    def _create_moss_slot_row(self, ctrl):
        i = ctrl.slot_idx
        is_en = getattr(ctrl, "moss_enabled", True)
        base_bg = "#0c1424" if i % 2 == 1 else "#0f192c"
        row = ctk.CTkFrame(
            self.moss_scroll,
            fg_color=base_bg if is_en else "#080c14",
            height=32, corner_radius=0, border_width=0
        )
        row.pack(fill="x", pady=0)
        row.pack_propagate(False)

        # Hairline 1px dưới đáy hàng để tạo lưới bảng chuẩn
        ctk.CTkFrame(row, fg_color="#152033", height=1, corner_radius=0).pack(fill="x", side="bottom")

        # Ghim Thao tác bên phải trước tiên (110px)
        action = ctk.CTkFrame(row, fg_color="transparent")
        action.pack(side="right", padx=(2, 8))

        running = bool(getattr(ctrl, "moss_running", False))
        btn_toggle = ctk.CTkButton(
            action,
            text="⏹ Dừng" if running else "▶ Quay",
            width=62, height=24, corner_radius=Radii.XS, font=Fonts.CAPTION,
            fg_color=Colors.ROSE if running else Colors.GREEN,
            hover_color=Colors.ROSE_HOVER if running else Colors.GREEN_HOVER,
            command=lambda s=i: self._on_toggle_slot_auto(s)
        )
        btn_toggle.pack(side="left", padx=(0, 4))

        btn_more = ctk.CTkButton(
            action, text="⋯", width=28, height=24, corner_radius=Radii.XS,
            fg_color="#1e293b", hover_color="#334155",
            border_width=1, border_color="#334155", font=Fonts.BODY_BOLD,
            command=lambda s=i: self._show_row_menu(s)
        )
        btn_more.pack(side="left")

        # Cột 1: Checkbox Slot (58px, căn giữa)
        var = ctk.BooleanVar(value=is_en)
        self.moss_cb_vars[i] = var
        cb_f = ctk.CTkFrame(row, fg_color="transparent", width=58)
        cb_f.pack(side="left", padx=2)
        cb_f.pack_propagate(False)

        cb = ctk.CTkCheckBox(
            cb_f, text=f"S{i:02d}", variable=var, width=50,
            font=("Segoe UI", 9, "bold"), text_color=Colors.AMBER if is_en else Colors.TEXT_DIM,
            checkbox_width=14, checkbox_height=14,
            command=lambda s=i, v=var: self._on_moss_enabled(s, v.get())
        )
        cb.pack(side="left", padx=4)

        # Cột 2: Nhân vật / PID (180px, căn trái)
        char_disp = f"● {ctrl.char_name} ({ctrl.assigned_pid})" if ctrl.assigned_pid else "⚪ Chưa kết nối"
        char_lbl = ctk.CTkLabel(
            row, text=char_disp, width=180, anchor="w", font=("Segoe UI", 10),
            text_color=Colors.TEXT_MAIN if (ctrl.assigned_pid and is_en) else Colors.TEXT_DIM
        )
        char_lbl.pack(side="left", padx=4)

        # Cột 3: Vật phẩm quay Category (Dropdown 220px)
        cat_var = ctk.StringVar(value=moss_cat_name(int(getattr(ctrl, "moss_category", 0) or 0)))
        cat_combo = ModernDropdown(
            row, values=[n for n, _ in MOSS_CAT_OPTIONS], variable=cat_var,
            width=220, height=24, fg_color=Colors.BG_CARD, border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER, font=Fonts.CAPTION,
            popup_min_width=250,
            command=lambda val, s=i: self._on_cat_changed(s, val),
        )
        cat_combo.pack(side="left", padx=4)

        # Cột 4: Delay ms (75px, căn giữa)
        delay_f = ctk.CTkFrame(row, fg_color="transparent", width=75)
        delay_f.pack(side="left", padx=2)
        delay_f.pack_propagate(False)

        delay_entry = ctk.CTkEntry(
            delay_f, width=52, height=24, font=Fonts.CAPTION, justify="center",
            fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD
        )
        delay_entry.insert(0, str(int(getattr(ctrl, "moss_delay_ms", 1000) or 1000)))
        delay_entry.pack(expand=True)
        delay_entry.bind("<FocusOut>", lambda e, s=i: self._on_delay_changed(s))
        delay_entry.bind("<Return>", lambda e, s=i: self._on_delay_changed(s))

        # Cột 5: Đã quay (65px, căn giữa)
        rolls = int(getattr(ctrl, "moss_rolls_count", 0) or 0)
        rolls_lbl = ctk.CTkLabel(
            row, text=f"{rolls}", width=65, anchor="center", font=Fonts.CAPTION,
            text_color=Colors.GREEN if rolls > 0 else Colors.TEXT_DIM
        )
        rolls_lbl.pack(side="left", padx=2)

        # Cột 6: Trạng thái (110px, căn trái)
        if not is_en:
            st_text, st_color = "⛔ Bỏ qua", Colors.TEXT_DIM
        elif ctrl.assigned_pid:
            st_text, st_color = "🟢 Sẵn sàng", Colors.GREEN
        else:
            st_text, st_color = "⚪ Chưa gán", Colors.TEXT_DIM
        status_lbl = ctk.CTkLabel(row, text=st_text, width=110, anchor="w", font=Fonts.CAPTION, text_color=st_color)
        status_lbl.pack(side="left", padx=4)

        # Đệm co giãn linh hoạt ở giữa
        ctk.CTkFrame(row, fg_color="transparent").pack(side="left", fill="both", expand=True)

        self.moss_ui_elements[i] = {
            "row_frame": row, "cb_enabled": cb, "char_lbl": char_lbl,
            "cat_var": cat_var, "cat_combo": cat_combo, "delay_entry": delay_entry,
            "rolls_lbl": rolls_lbl, "status_lbl": status_lbl,
            "btn_toggle": btn_toggle, "btn_more": btn_more,
        }

    # ---- log ----
    def append_log(self, text: str):
        try:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
            try:
                lines = int(self.log_box.index("end-1c").split(".")[0])
                if lines > 400:
                    self.log_box.delete("1.0", f"{lines - 300}.0")
            except Exception:
                pass
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    def clear_log(self):
        try:
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    # ---- updates ----
    def apply_schedule_config(self, moss_cfg: Optional[Dict[str, Any]] = None):
        if not moss_cfg:
            return
        self.var_moss_auto.set(bool(moss_cfg.get("auto_schedule", True)))
        self.var_moss_move.set(bool(moss_cfg.get("auto_move_before", True)))

    def apply_moss_flags_from_controllers(self):
        if not self.controllers:
            return
        c0 = self.controllers[0]
        self.var_moss_auto_clean.set(bool(getattr(c0, "moss_auto_clean", True)))
        self.var_moss_clean_equip.set(bool(getattr(c0, "moss_clean_equipment_trash", True)))
        self.moss_cat_var.set(moss_cat_name(int(getattr(c0, "moss_category", 0) or 0)))
        self.moss_delay_var.set(str(int(getattr(c0, "moss_delay_ms", 1000) or 1000)))
        self._update_moss_badge()

    def update_moss_data(self, moss: Dict[str, Any]):
        self.update_countdown(
            moss.get("countdown_sec", 0),
            moss.get("is_open", False),
            moss.get("next_time_str"),
        )
        self.refresh_moss_rows()

    def update_countdown(self, sec: int, is_open: bool, next_str: Optional[str] = None):
        self.lbl_moss_countdown.configure(text=self._format_seconds(sec))
        if is_open:
            self.lbl_moss_status.configure(text="🎲 ĐANG MỞ", text_color=Colors.GREEN)
        else:
            self.lbl_moss_status.configure(text="Chờ sự kiện", text_color=Colors.TEXT_MUTED)
        if next_str:
            self.lbl_moss_next.configure(text=f"Đợt kế: {next_str}")

    def refresh_moss_rows(self):
        for ctrl in self.controllers:
            i = ctrl.slot_idx
            el = self.moss_ui_elements.get(i)
            if not el:
                continue
            is_en = getattr(ctrl, "moss_enabled", True)
            name = getattr(ctrl, "char_name", "---") or "---"
            if name == "---":
                last_k = getattr(ctrl, "last_known_char_name", "")
                if last_k and last_k != "---":
                    name = last_k
                    ctrl.char_name = last_k
                elif hasattr(ctrl, "app") and hasattr(ctrl.app, "state_mgr"):
                    s_data = ctrl.app.state_mgr.get_slot(i)
                    if s_data.get("char_name") and s_data.get("char_name") != "---":
                        name = s_data["char_name"]
                        ctrl.char_name = name

            pid = getattr(ctrl, "assigned_pid", None)
            if el.get("char_lbl"):
                el["char_lbl"].configure(
                    text=f"● {name} ({pid})" if pid else "⚪ Chưa kết nối",
                    text_color=Colors.TEXT_MAIN if (pid and is_en) else Colors.TEXT_DIM
                )
            rolls = int(getattr(ctrl, "moss_rolls_count", 0) or 0)
            if el.get("rolls_lbl"):
                el["rolls_lbl"].configure(text=f"{rolls}", text_color=Colors.GREEN if rolls > 0 else Colors.TEXT_DIM)
            running = bool(getattr(ctrl, "moss_running", False))
            if el.get("btn_toggle"):
                el["btn_toggle"].configure(
                    text="⏹ Dừng" if running else "▶ Quay",
                    fg_color=Colors.ROSE if running else Colors.GREEN,
                    hover_color=Colors.ROSE_HOVER if running else Colors.GREEN_HOVER,
                )
            if el.get("status_lbl"):
                if running:
                    el["status_lbl"].configure(text="🎲 Đang quay", text_color=Colors.AMBER)
                elif not is_en:
                    el["status_lbl"].configure(text="⛔ Bỏ qua", text_color=Colors.TEXT_DIM)
                elif pid:
                    el["status_lbl"].configure(text="🟢 Sẵn sàng", text_color=Colors.GREEN)
                else:
                    el["status_lbl"].configure(text="⚪ Chưa gán", text_color=Colors.TEXT_DIM)
            if el.get("row_frame"):
                base_bg = "#0c1424" if i % 2 == 1 else "#0f192c"
                if running:
                    el["row_frame"].configure(fg_color="#1c160c")
                elif not is_en:
                    el["row_frame"].configure(fg_color="#080c14")
                else:
                    el["row_frame"].configure(fg_color=base_bg)
        self._update_moss_badge()

    @staticmethod
    def _format_seconds(sec: int) -> str:
        if sec < 0:
            sec = 0
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_all(self, enabled: bool):
        for s_idx, var in self.moss_cb_vars.items():
            var.set(enabled)
            self._on_moss_enabled(s_idx, enabled)

    def _on_moss_enabled(self, slot_idx: int, enabled: bool):
        el = self.moss_ui_elements.get(slot_idx)
        base_bg = "#0c1424" if slot_idx % 2 == 1 else "#0f192c"
        if el and el.get("row_frame"):
            el["row_frame"].configure(fg_color=base_bg if enabled else "#080c14")
        if el and el.get("cb_enabled"):
            el["cb_enabled"].configure(text_color=Colors.AMBER if enabled else Colors.TEXT_DIM)
        if self.on_toggle_participant:
            self.on_toggle_participant(slot_idx, enabled)
        self._update_moss_badge()

    def _update_moss_badge(self):
        total = len(self.controllers)
        sel = sum(1 for c in self.controllers if getattr(c, "moss_enabled", True))
        self.lbl_moss_count_badge.configure(
            text=f"🟢 {sel}/{total} slot tham gia",
            text_color=Colors.GREEN if sel else Colors.TEXT_DIM
        )

    def _emit_schedule(self):
        if self.on_save_schedule:
            self.on_save_schedule({
                "auto_schedule": self.var_moss_auto.get(),
                "auto_move_before": self.var_moss_move.get(),
            })

    def _emit_moss_batch_flags(self):
        if self.on_apply_moss_batch:
            self.on_apply_moss_batch({
                "auto_clean": self.var_moss_auto_clean.get(),
                "clean_equipment_trash": self.var_moss_clean_equip.get(),
                "flags_only": True,
            })

    def _handle_apply_batch(self):
        if not self.on_apply_moss_batch:
            return
        try:
            delay = max(400, int(self.moss_delay_var.get().strip() or "1000"))
        except Exception:
            delay = 1000
        cat_name = self.moss_cat_var.get()
        self.on_apply_moss_batch({
            "category": moss_cat_id(cat_name),
            "category_name": cat_name,
            "delay_ms": delay,
            "auto_clean": self.var_moss_auto_clean.get(),
            "clean_equipment_trash": self.var_moss_clean_equip.get(),
            "flags_only": False,
        })
        for ctrl in self.controllers:
            if not getattr(ctrl, "moss_enabled", True):
                continue
            el = self.moss_ui_elements.get(ctrl.slot_idx)
            if not el:
                continue
            if el.get("cat_var"):
                el["cat_var"].set(cat_name)
            if el.get("delay_entry"):
                el["delay_entry"].delete(0, "end")
                el["delay_entry"].insert(0, str(delay))

    def _on_cat_changed(self, slot_idx: int, cat_name: str):
        if self.on_moss_slot_category:
            self.on_moss_slot_category(slot_idx, cat_name)

    def _on_delay_changed(self, slot_idx: int):
        el = self.moss_ui_elements.get(slot_idx)
        if not el or not el.get("delay_entry"):
            return
        try:
            val = max(400, int(el["delay_entry"].get().strip()))
        except Exception:
            ctrl = self.controllers[slot_idx - 1]
            val = int(getattr(ctrl, "moss_delay_ms", 1000) or 1000)
            el["delay_entry"].delete(0, "end")
            el["delay_entry"].insert(0, str(val))
            return
        if self.on_moss_slot_delay:
            self.on_moss_slot_delay(slot_idx, val)

    def _on_toggle_slot_auto(self, slot_idx: int):
        if self.on_toggle_moss_slot:
            self.on_toggle_moss_slot(slot_idx)

    def _show_row_menu(self, slot_idx: int):
        if not ModernActionMenu:
            if self.on_moss_row_action:
                self.on_moss_row_action(slot_idx, "menu_unavailable")
            return
        items = [
            (f"🎲 Quay thử 1 lần (Slot {slot_idx:02d})", lambda: self._row_action(slot_idx, "roll_once"), "#fbbf24"),
            ("🚪 Mở bảng Moss NPC", lambda: self._row_action(slot_idx, "open_npc"), "#38bdf8"),
            ("🚪 Đóng bảng Moss NPC", lambda: self._row_action(slot_idx, "close_npc"), "#94a3b8"),
            ("---", None, ""),
            ("💰 Đi bán đồ rác tại NPC Silvia", lambda: self._row_action(slot_idx, "sell"), "#34d399"),
            ("🗑️ Ném đồ rác tại chỗ ngay", lambda: self._row_action(slot_idx, "clean"), "#f87171"),
            ("---", None, ""),
            ("🚶 Chạy về NPC Moss (Elbeland 22, 225)", lambda: self._row_action(slot_idx, "move"), "#38bdf8"),
            ("🔓 Mở khóa kẹt thùng đồ & Moss", lambda: self._row_action(slot_idx, "unlock"), "#fbbf24"),
        ]
        menu = ModernActionMenu(self.winfo_toplevel(), items=items, min_width=260)
        self._row_menus[slot_idx] = menu
        el = self.moss_ui_elements.get(slot_idx)
        menu.show(anchor_widget=el.get("btn_more") if el else None)

    def _show_batch_tools_menu(self):
        if not ModernActionMenu:
            return
        items = [
            ("💰 Bán đồ rác tại NPC Silvia (Tất cả)", lambda: self._batch_tool("sell"), "#34d399"),
            ("🗑️ Ném đồ rác tại chỗ (Tất cả)", lambda: self._batch_tool("clean"), "#f87171"),
            ("🔍 Phân tích rác hòm đồ", lambda: self._batch_tool("analyze"), "#38bdf8"),
            ("🧹 Hộp thoại dọn rác nâng cao...", lambda: self._batch_tool("junk_dialog"), "#cbd5e1"),
            ("---", None, ""),
            ("🚶 Di chuyển tất cả về NPC Moss", lambda: self._batch_tool("move_all"), "#38bdf8"),
            ("🚪 Mở bảng NPC Moss (Tất cả)", lambda: self._batch_tool("open_all"), "#f1f5f9"),
            ("🚪 Đóng bảng NPC Moss (Tất cả)", lambda: self._batch_tool("close_all"), "#94a3b8"),
            ("🔓 Mở khóa kẹt thùng đồ (Tất cả)", lambda: self._batch_tool("unlock_all"), "#fbbf24"),
        ]
        menu = ModernActionMenu(self.winfo_toplevel(), items=items, min_width=300)
        self._batch_menu = menu
        menu.show(x=self.winfo_pointerx(), y=self.winfo_pointery())

    def _row_action(self, slot_idx: int, action: str):
        if self.on_moss_row_action:
            self.on_moss_row_action(slot_idx, action)

    def _batch_tool(self, action: str):
        if self.on_moss_batch_tool:
            self.on_moss_batch_tool(action)
        elif action == "sell" and self.on_sell_moss:
            self.on_sell_moss()
        elif action == "clean" and self.on_clean_moss:
            self.on_clean_moss()
        elif action == "analyze" and self.on_analyze_moss:
            self.on_analyze_moss()
        elif action == "junk_dialog" and self.on_open_junk_dialog:
            self.on_open_junk_dialog()

    def _handle_trigger_moss(self):
        if self.on_trigger_moss:
            self.on_trigger_moss()

    def _handle_stop_moss(self):
        if self.on_stop_moss:
            self.on_stop_moss()

    def _handle_clean_moss(self):
        if self.on_clean_moss:
            self.on_clean_moss()

    def _handle_sell_moss(self):
        if self.on_sell_moss:
            self.on_sell_moss()

    def _handle_analyze_moss(self):
        if self.on_analyze_moss:
            self.on_analyze_moss()

    def _handle_junk_dialog(self):
        if self.on_open_junk_dialog:
            self.on_open_junk_dialog()
