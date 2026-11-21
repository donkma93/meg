# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - MOSS MERCHANT VIEW
Giao diện Moss Native Qt6: QSplitter kéo giãn, QTableWidget 60fps, QMenu thao tác nhanh, State Diffing 100%.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QCheckBox, QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPlainTextEdit, QSplitter, QMenu
)

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


class MossTabQt(QWidget):
    """Tab 04 Moss — Native Qt6 60fps."""

    def __init__(
        self,
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
        parent=None,
    ):
        super().__init__(parent)
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

        self._rows: Dict[int, Dict[str, Any]] = {}
        self._row_cache: Dict[int, Any] = {}
        self._countdown_cache = None
        self._badge_cache = None
        self._applying_cfg = False

        self._build_ui()
        for ctrl in self.controllers:
            self.add_slot_row(ctrl)
        self._update_moss_badge()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)

        # 1. Status strip
        strip = QFrame()
        strip.setProperty("surface", "stripMoss")
        strip.setFixedHeight(42)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(12, 4, 12, 4)
        sl.setSpacing(10)

        lbl_b = QLabel("🎲 MOSS MERCHANT")
        lbl_b.setStyleSheet("background-color: #064e3b; color: #34d399; border-radius: 4px; padding: 3px 8px; font-weight: 700; font-size: 11px;")
        sl.addWidget(lbl_b)

        self.lbl_countdown = QLabel("00:00:00")
        self.lbl_countdown.setStyleSheet("color: #22c55e; font-weight: 800; font-size: 17px;")
        sl.addWidget(self.lbl_countdown)

        self.lbl_status = QLabel("● Chờ sự kiện")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")
        sl.addWidget(self.lbl_status)

        self.lbl_next = QLabel("🕒 Đợt kế: 00:15 / 06:15 / 12:15 / 18:15")
        self.lbl_next.setStyleSheet("color: #64748b; font-size: 11px;")
        sl.addWidget(self.lbl_next)

        sl.addStretch(1)

        self.lbl_badge = QLabel("🟢 0/0 slot tham gia")
        self.lbl_badge.setStyleSheet("color: #22c55e; font-weight: 700; font-size: 11px;")
        sl.addWidget(self.lbl_badge)
        root.addWidget(strip)

        # 2. Tools bar
        bar = QFrame()
        bar.setProperty("surface", "toolbar")
        bar.setFixedHeight(40)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(5)

        def _mb(text, cb, tone="neutral"):
            b = QPushButton(text)
            if tone != "neutral":
                b.setProperty("tone", tone)
            b.setFixedHeight(28)
            if cb:
                b.clicked.connect(cb)
            return b

        bl.addWidget(_mb("▶ QUAY TẤT CẢ", self.on_trigger_moss, "success"))
        bl.addWidget(_mb("⏹ DỪNG TẤT CẢ", self.on_stop_moss, "danger"))

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(18)
        sep.setStyleSheet("color: #243149;")
        bl.addWidget(sep)

        bl.addWidget(_mb("🔍 Phân Tích Hòm", self.on_analyze_moss, "primary"))
        bl.addWidget(_mb("🧹 Dọn Hòm Đồ", self.on_open_junk_dialog, "neutral"))
        bl.addWidget(_mb("💰 Bán Silvia", self.on_sell_moss, "neutral"))
        bl.addWidget(_mb("🗑️ Ném Rác", self.on_clean_moss, "neutral"))
        bl.addStretch(1)

        self.btn_more_tools = QPushButton("🛠 Tiện Ích Khác ▾")
        self.btn_more_tools.setProperty("tone", "ghost")
        self.btn_more_tools.setFixedHeight(28)
        self.btn_more_tools.clicked.connect(self._show_batch_tools_menu)
        bl.addWidget(self.btn_more_tools)
        root.addWidget(bar)

        # 3. Schedule + Batch config row
        srow = QFrame()
        srow.setProperty("surface", "utilbar")
        srow.setFixedHeight(38)
        rl = QHBoxLayout(srow)
        rl.setContentsMargins(10, 4, 10, 4)
        rl.setSpacing(8)

        self.cb_auto = QCheckBox("Tự quay theo giờ")
        self.cb_move = QCheckBox("Tới NPC Moss")
        self.cb_auto_clean = QCheckBox("Tự dọn hòm")
        self.cb_clean_equip = QCheckBox("Ném đồ rác")
        for cb in (self.cb_auto, self.cb_move):
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_schedule)
            rl.addWidget(cb)
        for cb in (self.cb_auto_clean, self.cb_clean_equip):
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_flags)
            rl.addWidget(cb)

        rl.addStretch(1)

        lbl_q = QLabel("Cài nhanh:")
        lbl_q.setStyleSheet("color: #94a3b8; font-size: 11px;")
        rl.addWidget(lbl_q)

        self.combo_batch_cat = QComboBox()
        self.combo_batch_cat.addItems([n for n, _ in MOSS_CAT_OPTIONS])
        self.combo_batch_cat.setFixedSize(185, 25)
        rl.addWidget(self.combo_batch_cat)

        self.spin_batch_delay = QSpinBox()
        self.spin_batch_delay.setRange(100, 30000)
        self.spin_batch_delay.setSingleStep(100)
        self.spin_batch_delay.setValue(1000)
        self.spin_batch_delay.setFixedSize(72, 25)
        self.spin_batch_delay.setSuffix("ms")
        rl.addWidget(self.spin_batch_delay)

        b_apply = QPushButton("Áp Dụng")
        b_apply.setProperty("tone", "primary")
        b_apply.setFixedHeight(25)
        b_apply.clicked.connect(self._handle_apply_batch)
        rl.addWidget(b_apply)

        b_all = QPushButton("Chọn Hết")
        b_all.setProperty("tone", "ghost")
        b_all.setFixedHeight(25)
        b_all.clicked.connect(lambda: self._set_all(True))
        rl.addWidget(b_all)

        b_none = QPushButton("Bỏ Hết")
        b_none.setProperty("tone", "ghost")
        b_none.setFixedHeight(25)
        b_none.clicked.connect(lambda: self._set_all(False))
        rl.addWidget(b_none)
        root.addWidget(srow)

        # 4. Splitter: Table + Log
        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Slot", "Nhân vật / PID", "Vật phẩm quay (Category)",
            "Delay (ms)", "Đã quay", "Trạng thái", "Thao tác"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        for col, (mode, w) in enumerate([
            (QHeaderView.Fixed, 72),
            (QHeaderView.Stretch, 240),
            (QHeaderView.Interactive, 270),
            (QHeaderView.Fixed, 96),
            (QHeaderView.Fixed, 78),
            (QHeaderView.Interactive, 150),
            (QHeaderView.Fixed, 128),
        ]):
            hh.setSectionResizeMode(col, mode)
            self.table.setColumnWidth(col, w)

        splitter.addWidget(self.table)

        log_card = QFrame()
        log_card.setProperty("surface", "card")
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(6, 4, 6, 6)
        ll.setSpacing(4)

        lh = QHBoxLayout()
        lbl_l = QLabel("📋 NHẬT KÝ SỰ KIỆN MOSS")
        lbl_l.setStyleSheet("color: #38bdf8; font-weight: 700;")
        lh.addWidget(lbl_l)
        lh.addStretch(1)
        b_clr = QPushButton("Xóa Log")
        b_clr.setProperty("tone", "ghost")
        b_clr.setFixedSize(64, 22)
        b_clr.clicked.connect(lambda: self.log_box.clear())
        lh.addWidget(b_clr)
        ll.addLayout(lh)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(400)
        ll.addWidget(self.log_box, 1)
        splitter.addWidget(log_card)

        splitter.setSizes([420, 145])
        root.addWidget(splitter, 1)

    def add_slot_row(self, ctrl: Any):
        i = ctrl.slot_idx
        if i in self._rows:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 34)
        is_en = bool(getattr(ctrl, "moss_enabled", True))
        running = bool(getattr(ctrl, "moss_running", False))

        # Col 0: Slot checkbox (direct cell widget — 0 wrapper)
        cb = QCheckBox(f"S{i:02d}")
        cb.setChecked(is_en)
        cb.setStyleSheet("padding-left: 8px;")
        cb.stateChanged.connect(lambda _s, s=i, c=cb: self._on_enabled(s, c.isChecked()))
        self.table.setCellWidget(r, 0, cb)

        # Col 1: Char / PID
        it_char = QTableWidgetItem("⚪ Chưa kết nối")
        it_char.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 1, it_char)

        # Col 2: Category combo (chia sẻ 1 QStringListModel duy nhất — nhanh gấp 5x)
        if not hasattr(self, "_cat_model"):
            from PySide6.QtCore import QStringListModel
            self._cat_model = QStringListModel([n for n, _ in MOSS_CAT_OPTIONS], self)
        cb_cat = QComboBox()
        cb_cat.setModel(self._cat_model)
        cb_cat.setCurrentText(moss_cat_name(int(getattr(ctrl, "moss_category", 0) or 0)))
        cb_cat.currentTextChanged.connect(
            lambda val, s=i: self.on_moss_slot_category and self.on_moss_slot_category(s, val)
        )
        self.table.setCellWidget(r, 2, cb_cat)

        # Col 3: Delay spinbox (direct cell widget)
        sp_delay = QSpinBox()
        sp_delay.setRange(100, 30000)
        sp_delay.setSingleStep(100)
        sp_delay.setAlignment(Qt.AlignCenter)
        sp_delay.setValue(int(getattr(ctrl, "moss_delay_ms", 1000) or 1000))
        sp_delay.editingFinished.connect(
            lambda s=i, sp=sp_delay: self.on_moss_slot_delay and self.on_moss_slot_delay(s, int(sp.value()))
        )
        self.table.setCellWidget(r, 3, sp_delay)

        # Col 4: Rolls count
        it_rolls = QTableWidgetItem(str(int(getattr(ctrl, "moss_rolls_count", 0) or 0)))
        it_rolls.setTextAlignment(Qt.AlignCenter)
        it_rolls.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 4, it_rolls)

        # Col 5: Status
        it_status = QTableWidgetItem("⚪ Chưa gán")
        it_status.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 5, it_status)

        # Col 6: Toggle + More menu — dùng objectName="CellBox" để giữ nguyên màu nền nút con!
        act_w = QWidget()
        act_w.setObjectName("CellBox")
        al = QHBoxLayout(act_w)
        al.setContentsMargins(6, 0, 6, 0)
        al.setSpacing(5)
        al.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)

        btn_run = QPushButton("⏹ Dừng" if running else "▶ Quay")
        btn_run.setProperty("rowBtn", True)
        btn_run.setProperty("tone", "danger" if running else "success")
        btn_run.setFixedSize(68, 24)
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.clicked.connect(lambda _=False, s=i: self.on_toggle_moss_slot and self.on_toggle_moss_slot(s))

        btn_more = QPushButton("⋯")
        btn_more.setProperty("rowBtn", True)
        btn_more.setProperty("tone", "cfgBtn")
        btn_more.setFixedSize(28, 24)
        btn_more.setCursor(Qt.PointingHandCursor)
        btn_more.clicked.connect(lambda _=False, s=i, b=btn_more: self._show_row_menu(s, b))

        al.addWidget(btn_run)
        al.addWidget(btn_more)
        self.table.setCellWidget(r, 6, act_w)

        self._rows[i] = {
            "row": r, "cb": cb, "it_char": it_char, "cb_cat": cb_cat,
            "sp_delay": sp_delay, "it_rolls": it_rolls, "it_status": it_status,
            "btn_run": btn_run, "btn_more": btn_more, "running": running,
        }
        self._row_cache.pop(i, None)
        self._update_moss_badge()

    @staticmethod
    def _pad(w: QWidget) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.addWidget(w)
        return box

    def remove_last_row(self):
        if not self._rows:
            return
        last_idx = max(self._rows.keys())
        info = self._rows.pop(last_idx, None)
        self._row_cache.pop(last_idx, None)
        if info:
            self.table.removeRow(info["row"])
        self._update_moss_badge()

    def apply_schedule_config(self, moss_cfg: Optional[Dict[str, Any]] = None):
        if not moss_cfg:
            return
        self._applying_cfg = True
        try:
            self.cb_auto.setChecked(bool(moss_cfg.get("auto_schedule", True)))
            self.cb_move.setChecked(bool(moss_cfg.get("auto_move_before", True)))
        finally:
            self._applying_cfg = False

    def apply_moss_flags_from_controllers(self):
        if not self.controllers:
            return
        self._applying_cfg = True
        try:
            c0 = self.controllers[0]
            self.cb_auto_clean.setChecked(bool(getattr(c0, "moss_auto_clean", True)))
            self.cb_clean_equip.setChecked(bool(getattr(c0, "moss_clean_equipment_trash", True)))
            self.combo_batch_cat.setCurrentText(moss_cat_name(int(getattr(c0, "moss_category", 0) or 0)))
            self.spin_batch_delay.setValue(int(getattr(c0, "moss_delay_ms", 1000) or 1000))
        finally:
            self._applying_cfg = False
        self._update_moss_badge()

    def update_countdown(self, sec: int, is_open: bool, next_str: Optional[str] = None):
        sec = max(0, int(sec or 0))
        cd_txt = f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
        key = (cd_txt, bool(is_open), next_str)
        if self._countdown_cache == key:
            return
        self._countdown_cache = key
        self.lbl_countdown.setText(cd_txt)
        self.lbl_status.setText("🎲 ĐANG MỞ" if is_open else "● Chờ sự kiện")
        self.lbl_status.setStyleSheet(
            f"color: {'#22c55e' if is_open else '#94a3b8'}; font-weight: 700; font-size: 11px;"
        )
        if next_str:
            self.lbl_next.setText(f"Đợt kế: {next_str}")

    def refresh_moss_rows(self):
        for ctrl in self.controllers:
            i = ctrl.slot_idx
            info = self._rows.get(i)
            if not info:
                continue
            is_en = bool(getattr(ctrl, "moss_enabled", True))
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
            rolls = int(getattr(ctrl, "moss_rolls_count", 0) or 0)
            running = bool(getattr(ctrl, "moss_running", False))
            row_key = (is_en, name, pid, rolls, running)
            if self._row_cache.get(i) == row_key:
                continue
            self._row_cache[i] = row_key

            info["it_char"].setText(f"● {name} ({pid})" if pid else "⚪ Chưa kết nối")
            info["it_char"].setForeground(QBrush(QColor("#f1f5f9" if (pid and is_en) else "#64748b")))

            info["it_rolls"].setText(str(rolls))
            info["it_rolls"].setForeground(QBrush(QColor("#22c55e" if rolls > 0 else "#64748b")))

            if info["running"] != running:
                info["running"] = running
                btn = info["btn_run"]
                btn.setText("⏹ Dừng" if running else "▶ Quay")
                btn.setProperty("tone", "danger" if running else "success")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            if running:
                st_t, st_c = "🎲 Đang quay", "#f59e0b"
            elif not is_en:
                st_t, st_c = "⛔ Bỏ qua", "#64748b"
            elif pid:
                st_t, st_c = "🟢 Sẵn sàng", "#22c55e"
            else:
                st_t, st_c = "⚪ Chưa gán", "#64748b"
            info["it_status"].setText(st_t)
            info["it_status"].setForeground(QBrush(QColor(st_c)))
        self._update_moss_badge()

    def append_log(self, text: str):
        self.log_box.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def _show_row_menu(self, slot_idx: int, btn: QPushButton):
        menu = QMenu(self)
        actions = [
            (f"🎲 Quay thử 1 lần (Slot {slot_idx:02d})", "roll_once"),
            ("🚪 Mở bảng Moss NPC", "open_npc"),
            ("🚪 Đóng bảng Moss NPC", "close_npc"),
            (None, None),
            ("💰 Đi bán đồ rác tại NPC Silvia", "sell"),
            ("🗑️ Ném đồ rác tại chỗ ngay", "clean"),
            (None, None),
            ("🚶 Chạy về NPC Moss (Elbeland 22, 225)", "move"),
            ("🔓 Mở khóa kẹt thùng đồ & Moss", "unlock"),
        ]
        for label, key in actions:
            if label is None:
                menu.addSeparator()
            else:
                act = QAction(label, menu)
                act.triggered.connect(lambda _=False, s=slot_idx, k=key: self.on_moss_row_action and self.on_moss_row_action(s, k))
                menu.addAction(act)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _show_batch_tools_menu(self):
        menu = QMenu(self)
        items = [
            ("🚶 Chạy về NPC Moss (Tất cả đã chọn)", "move_all"),
            ("🚪 Mở bảng Moss NPC (Tất cả đã chọn)", "open_all"),
            ("🚪 Đóng bảng Moss NPC (Tất cả đã chọn)", "close_all"),
            ("🔓 Mở khóa kẹt thùng đồ (Tất cả đã chọn)", "unlock_all"),
        ]
        for label, key in items:
            act = QAction(label, menu)
            act.triggered.connect(lambda _=False, k=key: self.on_moss_batch_tool and self.on_moss_batch_tool(k))
            menu.addAction(act)
        menu.exec(self.btn_more_tools.mapToGlobal(self.btn_more_tools.rect().bottomLeft()))

    def _handle_apply_batch(self):
        cat_name = self.combo_batch_cat.currentText()
        cat_id = moss_cat_id(cat_name)
        delay = int(self.spin_batch_delay.value())
        for ctrl in self.controllers:
            if not getattr(ctrl, "moss_enabled", True):
                continue
            info = self._rows.get(ctrl.slot_idx)
            if info:
                info["cb_cat"].blockSignals(True)
                info["cb_cat"].setCurrentText(cat_name)
                info["cb_cat"].blockSignals(False)
                info["sp_delay"].blockSignals(True)
                info["sp_delay"].setValue(delay)
                info["sp_delay"].blockSignals(False)
        if self.on_apply_moss_batch:
            self.on_apply_moss_batch({
                "category": cat_id,
                "category_name": cat_name,
                "delay_ms": delay,
                "auto_clean": self.cb_auto_clean.isChecked(),
                "clean_equipment_trash": self.cb_clean_equip.isChecked(),
                "flags_only": False,
            })

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
        self._update_moss_badge()

    def _update_moss_badge(self):
        total = len(self.controllers)
        sel = sum(1 for c in self.controllers if getattr(c, "moss_enabled", True))
        if self._badge_cache == (sel, total):
            return
        self._badge_cache = (sel, total)
        self.lbl_badge.setText(f"🟢 {sel}/{total} slot tham gia")

    def _emit_schedule(self):
        if self._applying_cfg or not self.on_save_schedule:
            return
        self.on_save_schedule({
            "auto_schedule": self.cb_auto.isChecked(),
            "auto_move_before": self.cb_move.isChecked(),
        })

    def _emit_flags(self):
        if self._applying_cfg or not self.on_apply_moss_batch:
            return
        self.on_apply_moss_batch({
            "auto_clean": self.cb_auto_clean.isChecked(),
            "clean_equipment_trash": self.cb_clean_equip.isChecked(),
            "flags_only": True,
        })
