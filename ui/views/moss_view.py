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
            self, fg_color=Colors.BG_CARD, border_width=1,
            border_color="#14532d", corner_radius=Radii.SM, height=42
        )
        strip.pack(fill="x", padx=10, pady=(8, 4))
        strip.pack_propagate(False)

        ctk.CTkLabel(strip, text="🎲 MOSS", font=Fonts.BODY_BOLD, text_color=Colors.GREEN).pack(side="left", padx=(10, 8), pady=8)

        self.lbl_moss_countdown = ctk.CTkLabel(
            strip, text="00:00:00", font=("Segoe UI", 16, "bold"), text_color=Colors.GREEN, width=78
        )
        self.lbl_moss_countdown.pack(side="left", padx=(0, 8))

        self.lbl_moss_status = ctk.CTkLabel(strip, text="Chờ sự kiện", font=Fonts.BADGE, text_color=Colors.TEXT_MUTED)
        self.lbl_moss_status.pack(side="left", padx=(0, 10))

        self.lbl_moss_next = ctk.CTkLabel(strip, text="Đợt kế: --:15", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM)
        self.lbl_moss_next.pack(side="left")

        self.lbl_moss_count_badge = ctk.CTkLabel(strip, text="0/0 slot", font=Fonts.BODY_BOLD, text_color=Colors.AMBER)
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

        make_action_button(left, "▶️ Quay", self._handle_trigger_moss, tone="success", height=28, width=78).pack(side="left", padx=2, pady=6)
        make_action_button(left, "⏹ Dừng", self._handle_stop_moss, tone="danger", height=28, width=72).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🔍 Phân tích", self._handle_analyze_moss, tone="primary", height=28, width=90).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🧹 Dọn", self._handle_junk_dialog, tone="purple", height=28, width=68).pack(side="left", padx=2, pady=6)
        make_action_button(left, "💰 Silvia", self._handle_sell_moss, tone="success", height=28, width=78).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🗑️ Ném", self._handle_clean_moss, tone="danger", height=28, width=64).pack(side="left", padx=2, pady=6)

        make_action_button(bar, "🛠️ Tiện ích ▾", self._show_batch_tools_menu, tone="ghost", height=28, width=100).pack(side="right", padx=8, pady=6)

    def _build_schedule_row(self):
        row = ctk.CTkFrame(
            self, fg_color=Colors.BG_CARD, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=36
        )
        row.pack(fill="x", padx=10, pady=(0, 4))
        row.pack_propagate(False)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="y", padx=6)

        for text, var, cmd in (
            ("🎰 Tự quay", self.var_moss_auto, self._emit_schedule),
            ("🚶 Tới NPC", self.var_moss_move, self._emit_schedule),
            ("🧹 Tự dọn", self.var_moss_auto_clean, self._emit_moss_batch_flags),
            ("👕 Đồ rác", self.var_moss_clean_equip, self._emit_moss_batch_flags),
        ):
            ctk.CTkCheckBox(
                left, text=text, variable=var, font=Fonts.CAPTION,
                checkbox_width=14, checkbox_height=14, command=cmd,
                text_color="#f87171" if var is self.var_moss_auto_clean else Colors.TEXT_MAIN
            ).pack(side="left", padx=(0, 8), pady=6)

        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right", fill="y", padx=6)

        self.moss_cat_var = ctk.StringVar(value=MOSS_CAT_OPTIONS[0][0])
        self.moss_cat_combo = ModernDropdown(
            right, values=[n for n, _ in MOSS_CAT_OPTIONS], variable=self.moss_cat_var,
            width=160, height=26, fg_color=Colors.BG_SURFACE, border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER, font=Fonts.CAPTION,
            popup_min_width=250,
        )
        self.moss_cat_combo.pack(side="left", padx=(0, 4), pady=6)

        self.moss_delay_var = ctk.StringVar(value="1000")
        ctk.CTkEntry(
            right, textvariable=self.moss_delay_var, width=48, height=24,
            fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.CAPTION, justify="center"
        ).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(right, "Áp dụng", self._handle_apply_batch, tone="primary", height=24, width=72).pack(side="left", padx=(0, 4), pady=6)
        make_action_button(right, "All", lambda: self._set_all(True), tone="ghost", height=24, width=40).pack(side="left", padx=(0, 2), pady=6)
        make_action_button(right, "None", lambda: self._set_all(False), tone="ghost", height=24, width=48).pack(side="left", pady=6)

    def _build_table(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=Colors.BG_CARD, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM
        )
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tools = ctk.CTkFrame(card, fg_color=Colors.BG_SURFACE, height=28, corner_radius=0)
        tools.pack(fill="x")
        tools.pack_propagate(False)
        ctk.CTkLabel(tools, text="Tài khoản Moss", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(side="left", padx=10, pady=3)

        hdr = ctk.CTkFrame(card, fg_color=Colors.BG_HEADER, height=26, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for title, w in (
            ("Slot", 78), ("Nhân vật / PID", 160), ("Vật phẩm quay", 170),
            ("Delay", 64), ("Quay", 58), ("Trạng thái", 90), ("", 110),
        ):
            ctk.CTkLabel(hdr, text=title, width=w, anchor="w", font=Fonts.BADGE, text_color=Colors.TEXT_MUTED).pack(side="left", padx=3, pady=3)

        self.moss_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.moss_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        bind_mousewheel_to_scrollable(self.moss_scroll)

        for ctrl in self.controllers:
            self._create_moss_slot_row(ctrl)
        self._update_moss_badge()

    def _build_log_panel(self, parent):
        log_card = ctk.CTkFrame(
            parent, fg_color=Colors.BG_CARD, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=150
        )
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.pack_propagate(False)

        head = ctk.CTkFrame(log_card, fg_color=Colors.BG_SURFACE, height=28, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text="📋 Nhật ký Moss", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(side="left", padx=10, pady=3)
        make_action_button(head, "Xóa", self.clear_log, tone="ghost", height=22, width=48).pack(side="right", padx=8, pady=3)

        self.log_box = ctk.CTkTextbox(
            log_card, font=Fonts.MONO, fg_color=Colors.BG_INPUT,
            text_color=Colors.TEXT_MAIN, border_width=0, wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.log_box.configure(state="disabled")

    def _create_moss_slot_row(self, ctrl):
        i = ctrl.slot_idx
        is_en = getattr(ctrl, "moss_enabled", True)
        row = ctk.CTkFrame(
            self.moss_scroll,
            fg_color=Colors.BG_SURFACE if is_en else "#0c1018",
            height=34, corner_radius=Radii.SM
        )
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=is_en)
        self.moss_cb_vars[i] = var
        cb = ctk.CTkCheckBox(
            row, text=f"S{i:02d}", variable=var, width=78,
            font=Fonts.CAPTION, text_color=Colors.AMBER if is_en else Colors.TEXT_DIM,
            checkbox_width=14, checkbox_height=14,
            command=lambda s=i, v=var: self._on_moss_enabled(s, v.get())
        )
        cb.pack(side="left", padx=(4, 2), pady=5)

        char_disp = f"● {ctrl.char_name} ({ctrl.assigned_pid})" if ctrl.assigned_pid else "⚪ Chưa kết nối"
        char_lbl = ctk.CTkLabel(
            row, text=char_disp, width=160, anchor="w", font=Fonts.CAPTION,
            text_color=Colors.TEXT_MAIN if (ctrl.assigned_pid and is_en) else Colors.TEXT_DIM
        )
        char_lbl.pack(side="left", padx=2)

        cat_var = ctk.StringVar(value=moss_cat_name(int(getattr(ctrl, "moss_category", 0) or 0)))
        cat_combo = ModernDropdown(
            row, values=[n for n, _ in MOSS_CAT_OPTIONS], variable=cat_var,
            width=170, height=26, fg_color=Colors.BG_CARD, border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER, font=Fonts.CAPTION,
            popup_min_width=250,
            command=lambda val, s=i: self._on_cat_changed(s, val),
        )
        cat_combo.pack(side="left", padx=2)

        delay_f = ctk.CTkFrame(row, fg_color="transparent", width=64)
        delay_f.pack(side="left", padx=2)
        delay_entry = ctk.CTkEntry(
            delay_f, width=44, height=24, font=Fonts.CAPTION, justify="center",
            fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD
        )
        delay_entry.insert(0, str(int(getattr(ctrl, "moss_delay_ms", 1000) or 1000)))
        delay_entry.pack(side="left")
        delay_entry.bind("<FocusOut>", lambda e, s=i: self._on_delay_changed(s))
        delay_entry.bind("<Return>", lambda e, s=i: self._on_delay_changed(s))

        rolls = int(getattr(ctrl, "moss_rolls_count", 0) or 0)
        rolls_lbl = ctk.CTkLabel(
            row, text=f"{rolls}", width=58, anchor="center", font=Fonts.CAPTION,
            text_color=Colors.GREEN if rolls > 0 else Colors.TEXT_DIM
        )
        rolls_lbl.pack(side="left", padx=2)

        if not is_en:
            st_text, st_color = "⛔ Bỏ qua", Colors.TEXT_DIM
        elif ctrl.assigned_pid:
            st_text, st_color = "🟢 Sẵn sàng", Colors.GREEN
        else:
            st_text, st_color = "⚪ Chưa gán", Colors.TEXT_DIM
        status_lbl = ctk.CTkLabel(row, text=st_text, width=90, anchor="center", font=Fonts.CAPTION, text_color=st_color)
        status_lbl.pack(side="left", padx=2)

        action = ctk.CTkFrame(row, fg_color="transparent", width=110)
        action.pack(side="left", padx=2)
        running = bool(getattr(ctrl, "moss_running", False))
        btn_toggle = ctk.CTkButton(
            action,
            text="⏹" if running else "▶️",
            width=48, height=24, corner_radius=Radii.SM, font=Fonts.CAPTION,
            fg_color=Colors.ROSE if running else Colors.GREEN,
            hover_color=Colors.ROSE_HOVER if running else Colors.GREEN_HOVER,
            command=lambda s=i: self._on_toggle_slot_auto(s)
        )
        btn_toggle.pack(side="left", padx=(0, 3))

        btn_more = ctk.CTkButton(
            action, text="⋯", width=28, height=24, corner_radius=Radii.SM,
            fg_color=Colors.BG_CARD, hover_color=Colors.BG_CARD_HOVER,
            border_width=1, border_color=Colors.BORDER_CARD, font=Fonts.BODY_BOLD,
            command=lambda s=i: self._show_row_menu(s)
        )
        btn_more.pack(side="left")

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
                    text="⏹" if running else "▶️",
                    fg_color=Colors.ROSE if running else Colors.GREEN,
                    hover_color=Colors.ROSE_HOVER if running else Colors.GREEN_HOVER,
                )
            if el.get("status_lbl"):
                if running:
                    el["status_lbl"].configure(text="🎲 Quay", text_color=Colors.AMBER)
                elif not is_en:
                    el["status_lbl"].configure(text="⛔ Bỏ qua", text_color=Colors.TEXT_DIM)
                elif pid:
                    el["status_lbl"].configure(text="🟢 Sẵn sàng", text_color=Colors.GREEN)
                else:
                    el["status_lbl"].configure(text="⚪ Chưa gán", text_color=Colors.TEXT_DIM)
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color=Colors.BG_SURFACE if is_en else "#0c1018")
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
        if el and el.get("row_frame"):
            el["row_frame"].configure(fg_color=Colors.BG_SURFACE if enabled else "#0c1018")
        if el and el.get("cb_enabled"):
            el["cb_enabled"].configure(text_color=Colors.AMBER if enabled else Colors.TEXT_DIM)
        if self.on_toggle_participant:
            self.on_toggle_participant(slot_idx, enabled)
        self._update_moss_badge()

    def _update_moss_badge(self):
        total = len(self.controllers)
        sel = sum(1 for c in self.controllers if getattr(c, "moss_enabled", True))
        self.lbl_moss_count_badge.configure(
            text=f"{sel}/{total} slot",
            text_color=Colors.AMBER if sel else Colors.TEXT_DIM
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
