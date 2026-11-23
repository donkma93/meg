# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - MIRROR (DOUBLE GOER) VIEW
Giao diện Mirror Native Qt6: QSplitter kéo giãn, QTableWidget 60fps, State Diffing 100%.
"""

import time
import threading
from typing import Any, Callable, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QPlainTextEdit, QSplitter
)


class MirrorTabQt(QWidget):
    """Tab 03 Mirror — Native Qt6 60fps."""

    def __init__(
        self,
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
        parent=None,
    ):
        super().__init__(parent)
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

        self._rows: Dict[int, Dict[str, Any]] = {}
        self._row_cache: Dict[int, Any] = {}
        self._custom_status: Dict[int, tuple] = {}
        self._countdown_cache = None
        self._badge_cache = None
        self._last_sync_txt = ""
        self._last_log_text = ""
        self._last_log_ts = 0.0
        self._applying_cfg = False

        self._build_ui()
        for ctrl in self.controllers:
            self.add_slot_row(ctrl)
        self._update_badge()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)

        # 1. Countdown strip
        strip = QFrame()
        strip.setProperty("surface", "stripMirror")
        strip.setFixedHeight(42)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(12, 4, 12, 4)
        sl.setSpacing(10)

        lbl_m = QLabel("🪞 MIRROR")
        lbl_m.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 13px;")
        sl.addWidget(lbl_m)

        self.lbl_countdown = QLabel("00:00:00")
        self.lbl_countdown.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 17px;")
        sl.addWidget(self.lbl_countdown)

        self.lbl_gate = QLabel("Cổng đóng")
        self.lbl_gate.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        sl.addWidget(self.lbl_gate)

        self.lbl_next = QLabel("Đợt kế: --:10")
        self.lbl_next.setStyleSheet("color: #64748b; font-size: 11px;")
        sl.addWidget(self.lbl_next)

        sl.addStretch(1)

        self.lbl_net_calib = QLabel("📡 RTT: --ms | Offset: +0ms")
        self.lbl_net_calib.setStyleSheet("color: #a78bfa; font-weight: 700; font-size: 11px;")
        self.lbl_net_calib.setToolTip("Ping thực tế tới GameServer và độ lệch giờ tự học (Offset) so với NTP")
        sl.addWidget(self.lbl_net_calib)

        self.lbl_sync = QLabel("⏱️ Đang đồng bộ...")
        self.lbl_sync.setStyleSheet("color: #38bdf8; font-size: 11px;")
        sl.addWidget(self.lbl_sync)

        btn_sync = QPushButton("🔄 Sync Giờ")
        btn_sync.setProperty("tone", "ghost")
        btn_sync.setFixedHeight(26)
        btn_sync.clicked.connect(self._handle_sync_time)
        sl.addWidget(btn_sync)

        self.lbl_badge = QLabel("0/0 slot")
        self.lbl_badge.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 12px;")
        sl.addWidget(self.lbl_badge)
        root.addWidget(strip)

        # 2. Actions toolbar
        bar = QFrame()
        bar.setProperty("surface", "toolbar")
        bar.setFixedHeight(40)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(5)

        def _ab(text, cb, tone="neutral"):
            b = QPushButton(text)
            if tone != "neutral":
                b.setProperty("tone", tone)
            b.setFixedHeight(28)
            if cb:
                b.clicked.connect(cb)
            return b

        bl.addWidget(_ab("⚡ Cướp cổng", self.on_trigger_mirror, "primary"))
        bl.addWidget(_ab("🚪 Vào cửa", self.on_enter_mirror, "purple"))
        bl.addWidget(_ab("⚔️ Ra bãi", self.on_mirror_lifecycle, "success"))
        bl.addWidget(_ab("🎁 Lôi K", self.on_claim_gremory, "fire"))
        bl.addWidget(_ab("🚶 Lugard", self.on_move_lugard, "ghost"))
        bl.addWidget(_ab("🎟️ Vé", self.on_check_tickets, "ghost"))
        bl.addWidget(_ab("Chuẩn bị", self.on_prepare_mirror, "neutral"))
        bl.addWidget(_ab("NPC", self.on_click_mirror_npc, "neutral"))
        bl.addStretch(1)
        bl.addWidget(_ab("⏹ Dừng", self.on_stop_mirror, "danger"))
        root.addWidget(bar)

        # 3. Schedule row
        srow = QFrame()
        srow.setProperty("surface", "card")
        srow.setFixedHeight(38)
        rl = QHBoxLayout(srow)
        rl.setContentsMargins(10, 4, 10, 4)
        rl.setSpacing(10)

        self.cb_auto = QCheckBox("⚡ Tự cướp")
        self.cb_zero_confirm = QCheckBox("🔇 Zero-Confirm")
        self.cb_zero_confirm.setToolTip("Bỏ qua hộp thoại xác nhận trong game để bắn gói Turbo độ trễ thấp nhất")
        self.cb_lifecycle = QCheckBox("⚔️ Ra bãi")
        self.cb_gremory = QCheckBox("🎁 Lôi K")
        self.cb_prep = QCheckBox("🚶 Lugard :08")
        self.cb_telegram = QCheckBox("📱 Telegram")

        for cb in (self.cb_auto, self.cb_zero_confirm, self.cb_lifecycle, self.cb_gremory, self.cb_prep):
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_schedule)
            rl.addWidget(cb)
        self.cb_telegram.stateChanged.connect(
            lambda _s: (not self._applying_cfg) and self.on_toggle_telegram and self.on_toggle_telegram(self.cb_telegram.isChecked())
        )
        rl.addWidget(self.cb_telegram)

        rl.addStretch(1)

        lbl_pf = QLabel("⚡ Bắn trước:")
        lbl_pf.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 11px;")
        rl.addWidget(lbl_pf)
        self.ed_prefire = QLineEdit("2")
        self.ed_prefire.setFixedSize(40, 24)
        self.ed_prefire.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.ed_prefire)
        rl.addWidget(QLabel("s"))

        rl.addWidget(QLabel("Chu kỳ:"))
        self.ed_delay = QLineEdit("10")
        self.ed_delay.setFixedSize(38, 24)
        self.ed_delay.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.ed_delay)
        rl.addWidget(QLabel("ms"))

        rl.addWidget(QLabel("Rải pha:"))
        self.ed_stagger = QLineEdit("Auto")
        self.ed_stagger.setFixedSize(44, 24)
        self.ed_stagger.setAlignment(Qt.AlignCenter)
        self.ed_stagger.setToolTip("Auto (-1): tự trải đều pha giữa các acc phủ kín chu kỳ | 0: bắn cùng lúc | 1..100: lệch tay (ms)")
        rl.addWidget(self.ed_stagger)

        rl.addWidget(QLabel("Offset:"))
        self.ed_offset = QLineEdit("0")
        self.ed_offset.setFixedSize(50, 24)
        self.ed_offset.setAlignment(Qt.AlignCenter)
        self.ed_offset.setToolTip("Độ lệch đồng hồ GameServer so với NTP (ms, tự học sau mỗi lượt hoặc chỉnh tay)")
        rl.addWidget(self.ed_offset)
        rl.addWidget(QLabel("ms"))

        rl.addWidget(QLabel("Tối đa:"))
        self.ed_dur = QLineEdit("15")
        self.ed_dur.setFixedSize(38, 24)
        self.ed_dur.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.ed_dur)
        rl.addWidget(QLabel("s"))

        for ed in (self.ed_prefire, self.ed_delay, self.ed_stagger, self.ed_offset, self.ed_dur):
            ed.editingFinished.connect(self._emit_schedule)

        btn_bot = QPushButton("⚙️ Bot")
        btn_bot.setProperty("tone", "ghost")
        btn_bot.setFixedHeight(24)
        if self.on_telegram_settings:
            btn_bot.clicked.connect(self.on_telegram_settings)
        rl.addWidget(btn_bot)
        root.addWidget(srow)

        # 4. Splitter: Slot Table + Mirror Log
        splitter = QSplitter(Qt.Vertical)

        tbl_card = QFrame()
        tbl_card.setProperty("surface", "card")
        tbl_lay = QVBoxLayout(tbl_card)
        tbl_lay.setContentsMargins(6, 4, 6, 6)
        tbl_lay.setSpacing(4)

        t_hdr = QHBoxLayout()
        lbl_t = QLabel("Tài khoản Mirror")
        lbl_t.setStyleSheet("color: #e2e8f0; font-weight: 700;")
        t_hdr.addWidget(lbl_t)
        t_hdr.addStretch(1)
        b_all = QPushButton("All")
        b_all.setProperty("tone", "ghost")
        b_all.setFixedSize(48, 22)
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("None")
        b_none.setProperty("tone", "ghost")
        b_none.setFixedSize(54, 22)
        b_none.clicked.connect(lambda: self._set_all(False))
        t_hdr.addWidget(b_none)
        t_hdr.addWidget(b_all)
        tbl_lay.addLayout(t_hdr)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Tham gia", "#", "Nhân vật / PID", "Vé Mirror", "Trạng thái", "Thao tác"])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        hh = self.table.horizontalHeader()
        for col, (mode, w) in enumerate([
            (QHeaderView.Fixed, 82),
            (QHeaderView.Fixed, 44),
            (QHeaderView.Stretch, 220),
            (QHeaderView.Fixed, 130),
            (QHeaderView.Fixed, 135),
            (QHeaderView.Fixed, 92),
        ]):
            hh.setSectionResizeMode(col, mode)
            self.table.setColumnWidth(col, w)

        tbl_lay.addWidget(self.table, 1)
        splitter.addWidget(tbl_card)

        # Log panel
        log_card = QFrame()
        log_card.setProperty("surface", "card")
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(6, 4, 6, 6)
        ll.setSpacing(4)

        lh = QHBoxLayout()
        lbl_l = QLabel("📋 Nhật ký Mirror")
        lbl_l.setStyleSheet("color: #c084fc; font-weight: 700;")
        lh.addWidget(lbl_l)
        lh.addStretch(1)
        b_clr = QPushButton("Xóa")
        b_clr.setProperty("tone", "ghost")
        b_clr.setFixedSize(52, 22)
        b_clr.clicked.connect(lambda: self.log_box.clear())
        lh.addWidget(b_clr)
        ll.addLayout(lh)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(400)
        ll.addWidget(self.log_box, 1)
        splitter.addWidget(log_card)

        splitter.setSizes([420, 150])
        root.addWidget(splitter, 1)

    def add_slot_row(self, ctrl: Any):
        i = ctrl.slot_idx
        if i in self._rows:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 32)
        is_en = bool(getattr(ctrl, "mirror_enabled", True))

        cb = QCheckBox("Đi")
        cb.setChecked(is_en)
        cb.setStyleSheet("padding-left: 8px;")
        cb.stateChanged.connect(lambda _s, s=i, c=cb: self._on_enabled(s, c.isChecked()))
        self.table.setCellWidget(r, 0, cb)

        it_num = QTableWidgetItem(f"{i:02d}")
        it_num.setTextAlignment(Qt.AlignCenter)
        it_num.setForeground(QBrush(QColor("#38bdf8")))
        self.table.setItem(r, 1, it_num)

        it_char = QTableWidgetItem("⚪ Chưa kết nối")
        it_char.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 2, it_char)

        it_ticket = QTableWidgetItem("🎟️ -- vé")
        it_ticket.setForeground(QBrush(QColor("#c084fc")))
        self.table.setItem(r, 3, it_ticket)

        it_status = QTableWidgetItem("⚪ Chưa gán")
        it_status.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 4, it_status)

        btn = QPushButton("⚡ Cướp")
        btn.setProperty("tone", "primary")
        btn.clicked.connect(lambda _=False, s=i: self.on_snipe_slot and self.on_snipe_slot(s))
        self.table.setCellWidget(r, 5, btn)

        self._rows[i] = {
            "row": r, "cb": cb, "it_char": it_char,
            "it_ticket": it_ticket, "it_status": it_status, "btn": btn,
        }
        self._row_cache.pop(i, None)
        self._update_badge()

    def remove_last_row(self):
        if not self._rows:
            return
        last_idx = max(self._rows.keys())
        info = self._rows.pop(last_idx, None)
        self._row_cache.pop(last_idx, None)
        self._custom_status.pop(last_idx, None)
        if info:
            self.table.removeRow(info["row"])
        self._update_badge()

    def apply_schedule_config(self, mirror_cfg: Optional[Dict[str, Any]] = None):
        if not mirror_cfg:
            return
        self._applying_cfg = True
        try:
            sched = mirror_cfg.get("schedule", mirror_cfg)
            self.cb_auto.setChecked(bool(sched.get("auto_schedule", True)))
            self.cb_zero_confirm.setChecked(bool(sched.get("zero_confirm", True)))
            self.cb_lifecycle.setChecked(bool(sched.get("auto_lifecycle", True)))
            self.cb_gremory.setChecked(bool(sched.get("auto_gremory", True)))
            self.cb_prep.setChecked(bool(sched.get("auto_prep_before", True)))
            pf = float(sched.get("prefire_sec", 2.0) if sched.get("prefire_sec") is not None else 2.0)
            self.ed_prefire.setText(f"{pf:.1f}".rstrip("0").rstrip(".") if pf != int(pf) else str(int(pf)))
            dl_raw = sched.get("interval_ms", sched.get("snipe_interval_ms", 10))
            self.ed_delay.setText(str(int(dl_raw) if dl_raw is not None else 10))
            st_raw = sched.get("stagger_ms", -1)
            st_val = int(st_raw) if st_raw is not None else -1
            self.ed_stagger.setText("Auto" if st_val < 0 else str(st_val))
            off_raw = float(sched.get("clock_offset_ms", 0.0) or 0.0)
            self.ed_offset.setText(f"{off_raw:.0f}" if abs(off_raw - round(off_raw)) < 0.05 else f"{off_raw:.1f}")
            dr = float(sched.get("max_duration_s", 15.0) or 15.0)
            self.ed_dur.setText(f"{dr:.0f}")
            self.update_net_telemetry(-1.0, off_raw)
        finally:
            self._applying_cfg = False

    def get_snipe_delay(self) -> int:
        try:
            return max(0, min(1000, int(self.ed_delay.text().strip() or "10")))
        except Exception:
            return 10

    def get_stagger_ms(self) -> int:
        try:
            raw = self.ed_stagger.text().strip().lower()
            if raw in ("", "auto", "-1"):
                return -1
            return max(-1, min(100, int(raw)))
        except Exception:
            return -1

    def get_clock_offset_ms(self) -> float:
        try:
            raw = self.ed_offset.text().strip()
            if not raw:
                return 0.0
            return max(-8000.0, min(8000.0, float(raw)))
        except Exception:
            return 0.0

    def update_net_telemetry(self, rtt_ms: float = -1.0, offset_ms: float = 0.0):
        try:
            rtt_txt = f"{rtt_ms:.0f}ms" if (rtt_ms is not None and float(rtt_ms) > 0) else "--ms"
            off_val = float(offset_ms or 0.0)
            self.lbl_net_calib.setText(f"📡 RTT: {rtt_txt} | Offset: {off_val:+.0f}ms")
            if not self.ed_offset.hasFocus():
                prev_apply = self._applying_cfg
                self._applying_cfg = True
                try:
                    self.ed_offset.setText(f"{off_val:.0f}" if abs(off_val - round(off_val)) < 0.05 else f"{off_val:.1f}")
                finally:
                    self._applying_cfg = prev_apply
        except Exception:
            pass

    def get_zero_confirm(self) -> bool:
        return bool(self.cb_zero_confirm.isChecked())

    def get_snipe_dur(self) -> float:
        try:
            return max(3.0, min(120.0, float(self.ed_dur.text().strip() or "15")))
        except Exception:
            return 15.0

    def get_prefire_sec(self) -> float:
        try:
            return max(0.0, min(30.0, float(self.ed_prefire.text().strip() or "5.0")))
        except Exception:
            return 5.0

    def update_countdown(self, sec: int, is_open: bool, next_str: Optional[str] = None):
        sec = max(0, int(sec or 0))
        cd_txt = f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
        key = (cd_txt, bool(is_open), next_str)
        if self._countdown_cache != key:
            self._countdown_cache = key
            self.lbl_countdown.setText(cd_txt)
            self.lbl_countdown.setStyleSheet(
                f"color: {'#22c55e' if is_open else '#38bdf8'}; font-weight: 800; font-size: 17px;"
            )
            self.lbl_gate.setText("⚡ ĐANG MỞ" if is_open else "Cổng đóng")
            self.lbl_gate.setStyleSheet(
                f"color: {'#22c55e' if is_open else '#94a3b8'}; font-weight: 700; font-size: 11px;"
            )
            if next_str:
                self.lbl_next.setText(f"Đợt kế: {next_str}")
        try:
            from services.time_sync_service import get_time_sync
            st_txt = get_time_sync().get_sync_status_text()
            if st_txt and st_txt != self._last_sync_txt:
                self._last_sync_txt = st_txt
                self.lbl_sync.setText(st_txt)
        except Exception:
            pass

    def refresh_rows(self):
        for ctrl in self.controllers:
            i = ctrl.slot_idx
            info = self._rows.get(i)
            if not info:
                continue
            is_en = bool(getattr(ctrl, "mirror_enabled", True))
            name = getattr(ctrl, "char_name", "---") or "---"
            if name == "---":
                last_k = getattr(ctrl, "last_known_char_name", "")
                if last_k and last_k != "---":
                    name = last_k
                    ctrl.char_name = last_k
                elif hasattr(ctrl, "app") and hasattr(ctrl.app, "state_mgr"):
                    sd = ctrl.app.state_mgr.get_slot(i)
                    if sd.get("char_name") and sd.get("char_name") != "---":
                        name = sd["char_name"]
                        ctrl.char_name = name

            pid = getattr(ctrl, "assigned_pid", None)
            sniping = bool(getattr(ctrl, "mirror_sniping", False))
            in_dung = bool(getattr(ctrl, "_mirror_dungeon_running", False))
            t_info = getattr(ctrl, "cached_mirror_ticket_info", None)
            t_key = (
                int(t_info.get("count", 0) or 0),
                bool(t_info.get("hasTicket")),
                bool(t_info.get("hasOnlySign")),
                len(t_info.get("signs", [])),
            ) if isinstance(t_info, dict) else None

            custom_st = self._custom_status.get(i)
            row_key = (is_en, name, pid, sniping, in_dung, t_key, custom_st)
            if self._row_cache.get(i) == row_key:
                continue
            self._row_cache[i] = row_key

            info["it_char"].setText(f"● {name} ({pid})" if pid else "⚪ Chưa kết nối")
            info["it_char"].setForeground(QBrush(QColor("#f1f5f9" if (pid and is_en) else "#64748b")))

            if not is_en:
                st_t, st_c = "⛔ Bỏ qua", "#64748b"
            elif not pid:
                st_t, st_c = "⚪ Chưa gán", "#64748b"
            elif custom_st and custom_st[0]:
                st_t, st_c = custom_st
            elif sniping:
                st_t, st_c = "⚡ Đang cướp cổng", "#c084fc"
            elif in_dung:
                st_t, st_c = "🏆 Trong Mirror", "#f59e0b"
            else:
                st_t, st_c = "🟢 Sẵn sàng", "#22c55e"
            info["it_status"].setText(st_t)
            info["it_status"].setForeground(QBrush(QColor(st_c)))
            btn = info.get("btn")
            if btn is not None:
                want_txt = "⏹ Dừng" if sniping else "⚡ Cướp"
                if btn.text() != want_txt:
                    btn.setText(want_txt)
            if t_info is not None:
                self.update_slot_ticket_info(i, t_info)
        self._update_badge()

    def set_slot_status(self, slot_idx: int, text: str = "", text_color: Optional[str] = None):
        color = text_color or "#94a3b8"
        if text:
            self._custom_status[slot_idx] = (text, color)
        else:
            self._custom_status.pop(slot_idx, None)
        self._row_cache.pop(slot_idx, None)
        info = self._rows.get(slot_idx)
        if info and text:
            info["it_status"].setText(text)
            info["it_status"].setForeground(QBrush(QColor(color)))

    def update_slot_ticket_info(self, slot_idx: int, t_info: Optional[Dict[str, Any]] = None):
        info = self._rows.get(slot_idx)
        if not info:
            return
        it = info["it_ticket"]
        if not t_info:
            it.setText("🎟️ -- vé")
            it.setForeground(QBrush(QColor("#94a3b8")))
            return
        cnt = int(t_info.get("count", 0) or 0)
        if t_info.get("hasTicket") and cnt > 0:
            it.setText(f"🎟️ {cnt} vé")
            it.setForeground(QBrush(QColor("#38bdf8")))
        elif t_info.get("hasOnlySign"):
            it.setText(f"🧩 Mảnh ({len(t_info.get('signs', []))})")
            it.setForeground(QBrush(QColor("#f59e0b")))
        else:
            it.setText("❌ 0 vé")
            it.setForeground(QBrush(QColor("#f87171")))

    def append_log(self, text: str):
        now = time.time()
        if self._last_log_text == text and (now - self._last_log_ts) < 1.0:
            return
        self._last_log_text = text
        self._last_log_ts = now
        self.log_box.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def _handle_sync_time(self):
        try:
            from services.time_sync_service import get_time_sync
            svc = get_time_sync()
            self.lbl_sync.setText("⏳ Đang đo NTP...")
            def _w():
                svc.sync_ntp(force=True)
                self._last_sync_txt = ""
            threading.Thread(target=_w, daemon=True).start()
        except Exception:
            pass

    def _set_all(self, enabled: bool):
        for s_idx, info in self._rows.items():
            cb: QCheckBox = info["cb"]
            cb.blockSignals(True)
            cb.setChecked(enabled)
            cb.blockSignals(False)
            self._on_enabled(s_idx, enabled)

    def _on_enabled(self, slot_idx: int, enabled: bool):
        self._row_cache.pop(slot_idx, None)
        if self.on_toggle_participant:
            self.on_toggle_participant(slot_idx, enabled)
        self._update_badge()

    def _update_badge(self):
        total = len(self.controllers)
        sel = sum(1 for c in self.controllers if getattr(c, "mirror_enabled", True))
        if self._badge_cache == (sel, total):
            return
        self._badge_cache = (sel, total)
        self.lbl_badge.setText(f"{sel}/{total} slot")

    def _emit_schedule(self):
        if self._applying_cfg or not self.on_save_schedule:
            return
        self.on_save_schedule({
            "auto_schedule": self.cb_auto.isChecked(),
            "zero_confirm": self.cb_zero_confirm.isChecked(),
            "auto_lifecycle": self.cb_lifecycle.isChecked(),
            "auto_gremory": self.cb_gremory.isChecked(),
            "auto_prep_before": self.cb_prep.isChecked(),
            "prefire_sec": self.get_prefire_sec(),
            "interval_ms": self.get_snipe_delay(),
            "stagger_ms": self.get_stagger_ms(),
            "clock_offset_ms": self.get_clock_offset_ms(),
            "max_duration_s": self.get_snipe_dur(),
        })
