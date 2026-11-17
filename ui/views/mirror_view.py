# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - MIRROR VIEW (COMPACT)
Dense ops layout: thin countdown strip · actions · table · status log.
"""

from typing import Callable, Optional, Dict, Any
import time
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.shell import make_action_button, bind_mousewheel_to_scrollable


class MirrorView(ctk.CTkFrame):
    """Tab Mirror gọn: ưu tiên bảng slot + nhật ký trạng thái."""

    def __init__(
        self,
        parent,
        controllers: list,
        on_trigger_mirror: Optional[Callable[[], None]] = None,
        on_enter_mirror: Optional[Callable[[], None]] = None,
        on_mirror_lifecycle: Optional[Callable[[], None]] = None,
        on_claim_gremory: Optional[Callable[[], None]] = None,
        on_move_lugard: Optional[Callable[[], None]] = None,
        on_check_tickets: Optional[Callable[[], None]] = None,
        on_prepare_mirror: Optional[Callable[[], None]] = None,
        on_click_mirror_npc: Optional[Callable[[], None]] = None,
        on_stop_mirror: Optional[Callable[[], None]] = None,
        on_toggle_participant: Optional[Callable[[int, bool], None]] = None,
        on_save_schedule: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_toggle_telegram: Optional[Callable[[bool], None]] = None,
        on_telegram_settings: Optional[Callable[[], None]] = None,
        on_snipe_slot: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.controllers = controllers
        self.on_trigger_mirror = on_trigger_mirror
        self.on_enter_mirror = on_enter_mirror
        self.on_mirror_lifecycle = on_mirror_lifecycle
        self.on_claim_gremory = on_claim_gremory
        self.on_move_lugard = on_move_lugard
        self.on_check_tickets = on_check_tickets
        self.on_prepare_mirror = on_prepare_mirror
        self.on_click_mirror_npc = on_click_mirror_npc
        self.on_stop_mirror = on_stop_mirror
        self.on_toggle_participant = on_toggle_participant
        self.on_save_schedule = on_save_schedule
        self.on_toggle_telegram = on_toggle_telegram
        self.on_telegram_settings = on_telegram_settings
        self.on_snipe_slot = on_snipe_slot

        self.mirror_cb_vars: Dict[int, ctk.BooleanVar] = {}
        self.mirror_ui_elements: Dict[int, Dict[str, Any]] = {}

        self.var_mirror_auto = ctk.BooleanVar(value=True)
        self.var_mirror_lifecycle = ctk.BooleanVar(value=True)
        self.var_mirror_gremory = ctk.BooleanVar(value=True)
        self.var_mirror_prep = ctk.BooleanVar(value=True)
        self.var_mirror_telegram = ctk.BooleanVar(value=False)

        self._build_layout()

    def _build_layout(self):
        self._build_status_strip()
        self._build_actions()
        self._build_schedule_row()

        # Split: bảng slot (expand) + log dưới
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        body.grid_rowconfigure(0, weight=3)
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._build_slot_table(body)
        self._build_log_panel(body)

    def _build_status_strip(self):
        strip = ctk.CTkFrame(
            self, fg_color=Colors.BG_CARD, border_width=1,
            border_color="#4c1d95", corner_radius=Radii.SM, height=42
        )
        strip.pack(fill="x", padx=10, pady=(8, 4))
        strip.pack_propagate(False)

        ctk.CTkLabel(
            strip, text="🪞 MIRROR", font=Fonts.BODY_BOLD, text_color=Colors.PURPLE
        ).pack(side="left", padx=(10, 8), pady=8)

        self.lbl_mirror_countdown = ctk.CTkLabel(
            strip, text="00:00:00", font=("Segoe UI", 16, "bold"), text_color=Colors.CYAN, width=78
        )
        self.lbl_mirror_countdown.pack(side="left", padx=(0, 8))

        self.lbl_mirror_gate_status = ctk.CTkLabel(
            strip, text="Cổng đóng", font=Fonts.BADGE, text_color=Colors.TEXT_MUTED
        )
        self.lbl_mirror_gate_status.pack(side="left", padx=(0, 10))

        self.lbl_mirror_next = ctk.CTkLabel(
            strip, text="Đợt kế: --:10", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM
        )
        self.lbl_mirror_next.pack(side="left")

        self.lbl_mirror_count_badge = ctk.CTkLabel(
            strip, text="0/0 slot", font=Fonts.BODY_BOLD, text_color=Colors.PURPLE
        )
        self.lbl_mirror_count_badge.pack(side="right", padx=12)

        make_action_button(
            strip, "🔄 Sync Giờ", self._handle_sync_time, tone="ghost", height=26, width=76
        ).pack(side="right", padx=(4, 6), pady=8)

        self.lbl_mirror_sync = ctk.CTkLabel(
            strip, text="⏱️ Đang đồng bộ...", font=Fonts.CAPTION, text_color=Colors.CYAN
        )
        self.lbl_mirror_sync.pack(side="right", padx=(0, 6))

    def _handle_sync_time(self):
        try:
            from services.time_sync_service import get_time_sync
            svc = get_time_sync()
            self.lbl_mirror_sync.configure(text="⏳ Đang đo NTP...", text_color=Colors.AMBER)
            def _worker():
                ok = svc.sync_ntp(force=True)
                txt = svc.get_sync_status_text()
                clr = Colors.GREEN if ok else Colors.AMBER
                self.after(0, lambda: self.lbl_mirror_sync.configure(text=txt, text_color=clr))
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _build_actions(self):
        bar = ctk.CTkFrame(
            self, fg_color=Colors.BG_SURFACE, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=40
        )
        bar.pack(fill="x", padx=10, pady=(0, 4))
        bar.pack_propagate(False)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="y", padx=6)

        make_action_button(left, "⚡ Cướp cổng", self._handle_trigger_mirror, tone="primary", height=28, width=100).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🚪 Vào cửa", self._handle_enter_mirror, tone="purple", height=28, width=84).pack(side="left", padx=2, pady=6)
        make_action_button(left, "⚔️ Ra bãi", self._handle_mirror_lifecycle, tone="success", height=28, width=78).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🎁 Lôi K", self._handle_claim_gremory, tone="fire", height=28, width=72).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🚶 Lugard", self._handle_move_lugard, tone="ghost", height=28, width=78).pack(side="left", padx=2, pady=6)
        make_action_button(left, "🎟️ Vé", self._handle_check_tickets, tone="ghost", height=28, width=58).pack(side="left", padx=2, pady=6)
        make_action_button(left, "Chuẩn bị", self._handle_prepare, tone="neutral", height=28, width=78).pack(side="left", padx=2, pady=6)
        make_action_button(left, "NPC", self._handle_click_npc, tone="neutral", height=28, width=52).pack(side="left", padx=2, pady=6)

        make_action_button(
            bar, "⏹ Dừng", self._handle_stop_mirror, tone="danger", height=28, width=72
        ).pack(side="right", padx=8, pady=6)

    def _build_schedule_row(self):
        row = ctk.CTkFrame(
            self, fg_color=Colors.BG_CARD, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM, height=36
        )
        row.pack(fill="x", padx=10, pady=(0, 4))
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(side="left", fill="y", padx=8)

        for text, var in (
            ("⚡ Tự cướp", self.var_mirror_auto),
            ("⚔️ Ra bãi", self.var_mirror_lifecycle),
            ("🎁 Lôi K", self.var_mirror_gremory),
            ("🚶 Lugard :08", self.var_mirror_prep),
            ("📱 Telegram", self.var_mirror_telegram),
        ):
            cmd = self._handle_toggle_telegram if var is self.var_mirror_telegram else self._emit_schedule
            ctk.CTkCheckBox(
                inner, text=text, variable=var, font=Fonts.CAPTION,
                checkbox_width=14, checkbox_height=14, command=cmd
            ).pack(side="left", padx=(0, 8), pady=7)

        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right", fill="y", padx=8)

        make_action_button(
            right, "⚙️ Bot", self._handle_telegram_settings, tone="ghost", height=24, width=52
        ).pack(side="right", padx=(4, 0), pady=6)

        ctk.CTkLabel(right, text="s", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="right", padx=(2, 6))
        self.entry_snipe_dur = ctk.CTkEntry(
            right, width=38, height=24, font=Fonts.CAPTION, justify="center",
            fg_color=Colors.BG_SURFACE, border_color=Colors.BORDER_CARD
        )
        self.entry_snipe_dur.insert(0, "15")
        self.entry_snipe_dur.pack(side="right", padx=0, pady=6)
        ctk.CTkLabel(right, text="Tối đa:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="right", padx=(6, 2))

        ctk.CTkLabel(right, text="ms", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="right", padx=(2, 6))
        self.entry_snipe_delay = ctk.CTkEntry(
            right, width=38, height=24, font=Fonts.CAPTION, justify="center",
            fg_color=Colors.BG_SURFACE, border_color=Colors.BORDER_CARD
        )
        self.entry_snipe_delay.insert(0, "35")
        self.entry_snipe_delay.pack(side="right", padx=0, pady=6)
        ctk.CTkLabel(right, text="Chu kỳ:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="right", padx=(6, 2))

        ctk.CTkLabel(right, text="s", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="right", padx=(2, 6))
        self.entry_prefire_sec = ctk.CTkEntry(
            right, width=42, height=24, font=Fonts.BADGE, justify="center",
            fg_color=Colors.BG_SURFACE, border_color=Colors.PURPLE, text_color=Colors.PURPLE
        )
        self.entry_prefire_sec.insert(0, "2.0")
        self.entry_prefire_sec.pack(side="right", padx=0, pady=6)
        ctk.CTkLabel(right, text="⚡ Bắn trước:", font=Fonts.BADGE, text_color=Colors.PURPLE).pack(side="right", padx=(6, 2))

        for entry in (self.entry_prefire_sec, self.entry_snipe_delay, self.entry_snipe_dur):
            entry.bind("<FocusOut>", lambda e: self._emit_schedule())
            entry.bind("<Return>", lambda e: self._emit_schedule())

    def _build_slot_table(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=Colors.BG_CARD, border_width=1,
            border_color=Colors.BORDER_CARD, corner_radius=Radii.SM
        )
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tools = ctk.CTkFrame(card, fg_color=Colors.BG_SURFACE, height=32, corner_radius=0)
        tools.pack(fill="x")
        tools.pack_propagate(False)
        ctk.CTkLabel(tools, text="Tài khoản Mirror", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(side="left", padx=10, pady=4)
        make_action_button(tools, "All", lambda: self._set_all(True), tone="ghost", height=24, width=42).pack(side="right", padx=(0, 8), pady=4)
        make_action_button(tools, "None", lambda: self._set_all(False), tone="ghost", height=24, width=52).pack(side="right", padx=(0, 4), pady=4)

        hdr = ctk.CTkFrame(card, fg_color=Colors.BG_HEADER, height=26, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for title, w in (
            ("Tham gia", 75), ("#", 32), ("Nhân vật / PID", 210),
            ("Vé Mirror", 125), ("Trạng thái", 115), ("", 80),
        ):
            ctk.CTkLabel(hdr, text=title, width=w, anchor="w", font=Fonts.BADGE, text_color=Colors.TEXT_MUTED).pack(side="left", padx=4, pady=3)

        self.mirror_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.mirror_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        bind_mousewheel_to_scrollable(self.mirror_scroll)

        for ctrl in self.controllers:
            self._create_row(ctrl)
        self._update_badge()

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
        ctk.CTkLabel(head, text="📋 Nhật ký Mirror", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_MAIN).pack(side="left", padx=10, pady=3)
        make_action_button(head, "Xóa", self.clear_log, tone="ghost", height=22, width=48).pack(side="right", padx=8, pady=3)

        self.log_box = ctk.CTkTextbox(
            log_card, font=Fonts.MONO, fg_color=Colors.BG_INPUT,
            text_color=Colors.TEXT_MAIN, border_width=0, wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.log_box.configure(state="disabled")

    def _create_row(self, ctrl):
        i = ctrl.slot_idx
        is_en = getattr(ctrl, "mirror_enabled", True)
        row = ctk.CTkFrame(
            self.mirror_scroll,
            fg_color=Colors.BG_SURFACE if is_en else "#0c1018",
            height=34, corner_radius=Radii.SM
        )
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=is_en)
        self.mirror_cb_vars[i] = var
        cb = ctk.CTkCheckBox(
            row, text="Đi", variable=var, width=75,
            font=Fonts.CAPTION, text_color=Colors.PURPLE if is_en else Colors.TEXT_DIM,
            checkbox_width=14, checkbox_height=14,
            command=lambda s=i, v=var: self._on_enabled(s, v.get())
        )
        cb.pack(side="left", padx=(6, 2), pady=5)

        ctk.CTkLabel(row, text=f"{i:02d}", width=32, anchor="w", font=Fonts.BODY_BOLD, text_color=Colors.CYAN).pack(side="left", padx=2)

        char_disp = f"● {ctrl.char_name} ({ctrl.assigned_pid})" if ctrl.assigned_pid else "⚪ Chưa kết nối"
        char_lbl = ctk.CTkLabel(
            row, text=char_disp, width=210, anchor="w", font=Fonts.CAPTION,
            text_color=Colors.TEXT_MAIN if (ctrl.assigned_pid and is_en) else Colors.TEXT_DIM
        )
        char_lbl.pack(side="left", padx=4)

        # Cột Vé Mirror
        ticket_lbl = ctk.CTkLabel(
            row, text="🎟️ -- vé", width=125, anchor="w", font=Fonts.CAPTION, text_color=Colors.PURPLE
        )
        ticket_lbl.pack(side="left", padx=4)

        if not is_en:
            st_text, st_color = "⛔ Bỏ qua", Colors.TEXT_DIM
        elif ctrl.assigned_pid:
            st_text, st_color = "🟢 Sẵn sàng", Colors.GREEN
        else:
            st_text, st_color = "⚪ Chưa gán", Colors.TEXT_DIM
        status_lbl = ctk.CTkLabel(row, text=st_text, width=115, anchor="w", font=Fonts.CAPTION, text_color=st_color)
        status_lbl.pack(side="left", padx=4)

        btn = make_action_button(row, "⚡ Cướp", lambda s=i: self._handle_snipe_slot(s), tone="primary", height=24, width=72)
        btn.pack(side="left", padx=4)

        self.mirror_ui_elements[i] = {
            "row_frame": row, "cb_enabled": cb, "char_lbl": char_lbl,
            "ticket_lbl": ticket_lbl, "status_lbl": status_lbl, "btn_snipe": btn,
        }

    # ---- log ----
    def append_log(self, text: str):
        try:
            # Chống insert trùng liên tiếp cùng nội dung
            last = getattr(self, "_last_log_text", None)
            last_ts = float(getattr(self, "_last_log_ts", 0.0) or 0.0)
            now = time.time()
            if last == text and (now - last_ts) < 1.0:
                return
            self._last_log_text = text
            self._last_log_ts = now

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
    def apply_schedule_config(self, mirror_cfg: Optional[Dict[str, Any]] = None):
        if not mirror_cfg:
            return
        sched = mirror_cfg.get("schedule", mirror_cfg)
        self.var_mirror_auto.set(bool(sched.get("auto_schedule", True)))
        self.var_mirror_lifecycle.set(bool(sched.get("auto_lifecycle", True)))
        self.var_mirror_gremory.set(bool(sched.get("auto_gremory", True)))
        self.var_mirror_prep.set(bool(sched.get("auto_prep_before", True)))
        if hasattr(self, "entry_prefire_sec"):
            pf = float(sched.get("prefire_sec", 2.0) or 2.0)
            self.entry_prefire_sec.delete(0, "end")
            self.entry_prefire_sec.insert(0, f"{pf:.1f}".rstrip('0').rstrip('.') if pf != int(pf) else str(int(pf)))
        if hasattr(self, "entry_snipe_delay"):
            dl = int(sched.get("interval_ms", 35) or 35)
            self.entry_snipe_delay.delete(0, "end")
            self.entry_snipe_delay.insert(0, str(dl))
        if hasattr(self, "entry_snipe_dur"):
            dr = float(sched.get("max_duration_s", 15.0) or 15.0)
            self.entry_snipe_dur.delete(0, "end")
            self.entry_snipe_dur.insert(0, f"{dr:.0f}")

    def update_mirror_data(self, mirror: Dict[str, Any]):
        self.update_countdown(
            mirror.get("countdown_sec", 0),
            mirror.get("is_gate_open", False),
            mirror.get("next_time_str"),
        )
        self.refresh_rows()

    def update_countdown(self, sec: int, is_open: bool, next_str: Optional[str] = None):
        self.lbl_mirror_countdown.configure(text=self._format_seconds(sec))
        if is_open:
            self.lbl_mirror_gate_status.configure(text="⚡ ĐANG MỞ", text_color=Colors.GREEN)
            self.lbl_mirror_countdown.configure(text_color=Colors.GREEN)
        else:
            self.lbl_mirror_gate_status.configure(text="Cổng đóng", text_color=Colors.TEXT_MUTED)
            self.lbl_mirror_countdown.configure(text_color=Colors.CYAN)
        if next_str:
            self.lbl_mirror_next.configure(text=f"Đợt kế: {next_str}")
        if hasattr(self, "lbl_mirror_sync"):
            try:
                from services.time_sync_service import get_time_sync
                st_txt = get_time_sync().get_sync_status_text()
                if st_txt and self.lbl_mirror_sync.cget("text") != st_txt:
                    self.lbl_mirror_sync.configure(text=st_txt)
            except Exception:
                pass

    def refresh_rows(self):
        for ctrl in self.controllers:
            i = ctrl.slot_idx
            el = self.mirror_ui_elements.get(i)
            if not el:
                continue
            is_en = getattr(ctrl, "mirror_enabled", True)
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
            if el.get("status_lbl"):
                if not is_en:
                    el["status_lbl"].configure(text="⛔ Bỏ qua", text_color=Colors.TEXT_DIM)
                elif pid:
                    el["status_lbl"].configure(text="🟢 Sẵn sàng", text_color=Colors.GREEN)
                else:
                    el["status_lbl"].configure(text="⚪ Chưa gán", text_color=Colors.TEXT_DIM)
            if el.get("row_frame"):
                el["row_frame"].configure(fg_color=Colors.BG_SURFACE if is_en else "#0c1018")
            if hasattr(ctrl, "cached_mirror_ticket_info"):
                self.update_slot_ticket_info(i, getattr(ctrl, "cached_mirror_ticket_info", None))
        self._update_badge()

    def update_slot_ticket_info(self, slot_idx: int, t_info: Optional[Dict[str, Any]] = None):
        """Cập nhật nhãn số lượng vé Mirror cho một slot cụ thể."""
        el = self.mirror_ui_elements.get(slot_idx)
        if not el or not el.get("ticket_lbl") or not el["ticket_lbl"].winfo_exists():
            return
        lbl = el["ticket_lbl"]
        if not t_info:
            lbl.configure(text="🎟️ -- vé", text_color=Colors.TEXT_MUTED)
            return

        cnt = int(t_info.get("count", 0) or 0)
        has_ticket = bool(t_info.get("hasTicket"))
        has_only_sign = bool(t_info.get("hasOnlySign"))
        signs = t_info.get("signs", [])

        if has_ticket and cnt > 0:
            lbl.configure(text=f"🎟️ {cnt} vé", text_color=Colors.CYAN)
        elif has_only_sign:
            lbl.configure(text=f"🧩 Mảnh ({len(signs)})", text_color=Colors.AMBER)
        else:
            lbl.configure(text="❌ 0 vé", text_color="#f87171")

    @staticmethod
    def _format_seconds(sec: int) -> str:
        if sec < 0:
            sec = 0
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_all(self, enabled: bool):
        for s_idx, var in self.mirror_cb_vars.items():
            var.set(enabled)
            self._on_enabled(s_idx, enabled)

    def _on_enabled(self, slot_idx: int, enabled: bool):
        el = self.mirror_ui_elements.get(slot_idx)
        if el and el.get("row_frame"):
            el["row_frame"].configure(fg_color=Colors.BG_SURFACE if enabled else "#0c1018")
        if el and el.get("cb_enabled"):
            el["cb_enabled"].configure(text_color=Colors.PURPLE if enabled else Colors.TEXT_DIM)
        if self.on_toggle_participant:
            self.on_toggle_participant(slot_idx, enabled)
        self._update_badge()

    def _update_badge(self):
        total = len(self.controllers)
        sel = sum(1 for c in self.controllers if getattr(c, "mirror_enabled", True))
        self.lbl_mirror_count_badge.configure(
            text=f"{sel}/{total} slot",
            text_color=Colors.PURPLE if sel else Colors.TEXT_DIM
        )

    def _emit_schedule(self):
        if self.on_save_schedule:
            self.on_save_schedule({
                "auto_schedule": self.var_mirror_auto.get(),
                "auto_lifecycle": self.var_mirror_lifecycle.get(),
                "auto_gremory": self.var_mirror_gremory.get(),
                "auto_prep_before": self.var_mirror_prep.get(),
                "prefire_sec": self.get_prefire_sec(),
                "interval_ms": self.get_snipe_delay(),
                "max_duration_s": self.get_snipe_dur(),
            })

    def get_prefire_sec(self) -> float:
        try:
            return max(0.0, min(30.0, float(self.entry_prefire_sec.get().strip())))
        except Exception:
            return 2.0

    def get_snipe_delay(self) -> int:
        try:
            return max(15, min(1000, int(self.entry_snipe_delay.get().strip())))
        except Exception:
            return 35

    def get_snipe_dur(self) -> float:
        try:
            return max(3.0, min(120.0, float(self.entry_snipe_dur.get().strip())))
        except Exception:
            return 15.0

    def _handle_trigger_mirror(self):
        if self.on_trigger_mirror:
            self.on_trigger_mirror()

    def _handle_enter_mirror(self):
        if self.on_enter_mirror:
            self.on_enter_mirror()

    def _handle_mirror_lifecycle(self):
        if self.on_mirror_lifecycle:
            self.on_mirror_lifecycle()

    def _handle_claim_gremory(self):
        if self.on_claim_gremory:
            self.on_claim_gremory()

    def _handle_move_lugard(self):
        if self.on_move_lugard:
            self.on_move_lugard()

    def _handle_check_tickets(self):
        if self.on_check_tickets:
            self.on_check_tickets()

    def _handle_prepare(self):
        if self.on_prepare_mirror:
            self.on_prepare_mirror()

    def _handle_click_npc(self):
        if self.on_click_mirror_npc:
            self.on_click_mirror_npc()

    def _handle_stop_mirror(self):
        if self.on_stop_mirror:
            self.on_stop_mirror()

    def _handle_toggle_telegram(self):
        if self.on_toggle_telegram:
            self.on_toggle_telegram(bool(self.var_mirror_telegram.get()))
        else:
            self._emit_schedule()

    def _handle_telegram_settings(self):
        if self.on_telegram_settings:
            self.on_telegram_settings()

    def _handle_snipe_slot(self, slot_idx: int):
        if self.on_snipe_slot:
            self.on_snipe_slot(slot_idx)
