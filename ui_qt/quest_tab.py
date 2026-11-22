# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - AUTO QUEST (NHIỆM VỤ CẤP 2 / MARLON / CẤP 3) VIEW
Giao diện Native Qt6 60fps với QTableWidget State Diffing, cấu hình bãi farm & nhật ký trực tiếp.
"""

import copy
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from meg_quest_automation import DEFAULT_QUEST_CONFIG


MODE_OPTIONS = [
    ("all_2_3", "Tự động Cấp 2 + Cấp 3"),
    ("class2_only", "Chỉ Cấp 2 (Lv150)"),
    ("marlon_only", "Chỉ Marlon (Lv220)"),
    ("class3_only", "Chỉ Cấp 3 (Lv400)"),
]


class QuestSpotsDialogQt(QDialog):
    """Hộp thoại tùy chỉnh lệnh warp & tọa độ bãi farm nhiệm vụ Cấp 2 / Marlon / Cấp 3."""

    def __init__(self, current_cfg: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ Tùy chỉnh Tọa Độ Bãi Farm Nhiệm Vụ")
        self.resize(680, 520)
        self._cfg = copy.deepcopy(current_cfg or DEFAULT_QUEST_CONFIG)
        self._spot_inputs: Dict[str, Dict[str, Any]] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        lbl_info = QLabel(
            "Chỉnh sửa lệnh dịch chuyển (/move ...) và tọa độ (X, Y) các bãi farm vật phẩm / quái nhiệm vụ.\n"
            "Riêng Barracks và Refuge đi qua NPC Werewolf Quarrel / Gatekeeper nên không cần lệnh /move."
        )
        lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_info.setWordWrap(True)
        root.addWidget(lbl_info)

        # Global numeric settings
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(QLabel("Level tối thiểu NV Cấp 3:"))
        self.sp_c3_lv = QSpinBox()
        self.sp_c3_lv.setRange(400, 400)
        self.sp_c3_lv.setValue(400)
        self.sp_c3_lv.setToolTip("Chuẩn MegaMU bắt buộc Level 400 để nói chuyện Priest Devin (Crywolf)")
        top_row.addWidget(self.sp_c3_lv)

        top_row.addSpacing(10)
        top_row.addWidget(QLabel("Quái Barracks (mỗi loại):"))
        self.sp_barracks_cnt = QSpinBox()
        self.sp_barracks_cnt.setRange(1, 100)
        self.sp_barracks_cnt.setValue(int(self._cfg.get("barracks_req_count", 20) or 20))
        self.sp_barracks_cnt.setToolTip("Số lượng cần giết mỗi loại Balram / Death Spirit / Soram (chuẩn MegaMU: 20)")
        top_row.addWidget(self.sp_barracks_cnt)

        top_row.addSpacing(10)
        top_row.addWidget(QLabel("Timeout bãi (phút):"))
        self.sp_timeout = QSpinBox()
        self.sp_timeout.setRange(5, 240)
        self.sp_timeout.setValue(int(self._cfg.get("farm_timeout_min", 45) or 45))
        top_row.addWidget(self.sp_timeout)
        top_row.addStretch(1)
        root.addLayout(top_row)

        # Scrollable grid for spots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        for col, title in enumerate(("Nhiệm vụ / Bãi", "Lệnh Warp", "X", "Y")):
            lh = QLabel(title)
            lh.setStyleSheet("color: #2dd4bf; font-weight: 700; font-size: 11px;")
            grid.addWidget(lh, 0, col)

        spots = self._cfg.get("spots") or DEFAULT_QUEST_CONFIG["spots"]
        for row_idx, (key, default_sp) in enumerate(DEFAULT_QUEST_CONFIG["spots"].items(), start=1):
            sp = spots.get(key) or default_sp
            lbl = QLabel(str(sp.get("label", key)))
            lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")

            ed_cmd = QLineEdit(str(sp.get("map_cmd", "")))
            ed_cmd.setPlaceholderText("(Vào qua NPC)")
            ed_cmd.setFixedWidth(160)

            sp_x = QSpinBox()
            sp_x.setRange(0, 255)
            sp_x.setValue(int(sp.get("x", 0)))
            sp_x.setFixedWidth(68)

            sp_y = QSpinBox()
            sp_y.setRange(0, 255)
            sp_y.setValue(int(sp.get("y", 0)))
            sp_y.setFixedWidth(68)

            grid.addWidget(lbl, row_idx, 0)
            grid.addWidget(ed_cmd, row_idx, 1)
            grid.addWidget(sp_x, row_idx, 2)
            grid.addWidget(sp_y, row_idx, 3)

            self._spot_inputs[key] = {"cmd": ed_cmd, "x": sp_x, "y": sp_y}

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("↺ Khôi phục mặc định")
        btn_reset.setProperty("tone", "ghost")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch(1)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        btn_row.addWidget(bb)
        root.addLayout(btn_row)

    def _reset_defaults(self):
        self.sp_c3_lv.setValue(int(DEFAULT_QUEST_CONFIG["class3_min_level"]))
        self.sp_barracks_cnt.setValue(int(DEFAULT_QUEST_CONFIG["barracks_req_count"]))
        self.sp_timeout.setValue(int(DEFAULT_QUEST_CONFIG["farm_timeout_min"]))
        for key, sp in DEFAULT_QUEST_CONFIG["spots"].items():
            inp = self._spot_inputs.get(key)
            if inp:
                inp["cmd"].setText(str(sp.get("map_cmd", "")))
                inp["x"].setValue(int(sp.get("x", 0)))
                inp["y"].setValue(int(sp.get("y", 0)))

    def get_updated_config(self) -> Dict[str, Any]:
        out = copy.deepcopy(self._cfg)
        out["class3_min_level"] = int(self.sp_c3_lv.value())
        out["barracks_req_count"] = int(self.sp_barracks_cnt.value())
        out["farm_timeout_min"] = int(self.sp_timeout.value())
        spots = out.setdefault("spots", {})
        for key, inp in self._spot_inputs.items():
            base = copy.deepcopy(spots.get(key) or DEFAULT_QUEST_CONFIG["spots"][key])
            base["map_cmd"] = inp["cmd"].text().strip()
            base["x"] = int(inp["x"].value())
            base["y"] = int(inp["y"].value())
            spots[key] = base
        return out


class QuestTabQt(QWidget):
    """Tab Nhiệm Vụ Cấp 2 / Marlon / Cấp 3 — Native Qt6 60fps."""

    def __init__(
        self,
        controllers: list,
        quest_config: Optional[Dict[str, Any]] = None,
        on_scan_all: Optional[Callable[[], None]] = None,
        on_start_selected: Optional[Callable[[List[int]], None]] = None,
        on_stop_all: Optional[Callable[[], None]] = None,
        on_toggle_slot: Optional[Callable[[int], None]] = None,
        on_scan_slot: Optional[Callable[[int], None]] = None,
        on_config_changed: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_grab_current_coord: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.controllers = controllers
        self._cfg = copy.deepcopy(quest_config or DEFAULT_QUEST_CONFIG)
        self.on_scan_all = on_scan_all
        self.on_start_selected = on_start_selected
        self.on_stop_all = on_stop_all
        self.on_toggle_slot = on_toggle_slot
        self.on_scan_slot = on_scan_slot
        self.on_config_changed = on_config_changed
        self.on_grab_current_coord = on_grab_current_coord

        self._rows: Dict[int, Dict[str, Any]] = {}
        self._slot_states: Dict[int, Dict[str, Any]] = {}
        self._row_cache: Dict[int, Any] = {}
        self._applying_cfg = False

        self._build_ui()
        self.apply_config(self._cfg)
        for ctrl in self.controllers:
            self.add_slot_row(ctrl)
        self._update_badge()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(6)

        # 1. Header strip
        strip = QFrame()
        strip.setProperty("surface", "stripMirror")
        strip.setFixedHeight(42)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(12, 4, 12, 4)
        sl.setSpacing(10)

        lbl_title = QLabel("⚔️ AUTO NHIỆM VỤ CẤP 2 & CẤP 3")
        lbl_title.setStyleSheet("color: #f59e0b; font-weight: 800; font-size: 13px;")
        sl.addWidget(lbl_title)

        lbl_desc = QLabel("Sebina (Lv150) · Marlon (Lv220) · Priest Devin / Barracks / Refuge (Lv400)")
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sl.addWidget(lbl_desc)
        sl.addStretch(1)

        self.lbl_badge = QLabel("0/0 slot")
        self.lbl_badge.setStyleSheet("color: #2dd4bf; font-weight: 700; font-size: 12px;")
        sl.addWidget(self.lbl_badge)
        root.addWidget(strip)

        # 2. Actions toolbar
        bar = QFrame()
        bar.setProperty("surface", "toolbar")
        bar.setFixedHeight(42)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(6)

        def _btn(text, cb, tone="neutral"):
            b = QPushButton(text)
            if tone != "neutral":
                b.setProperty("tone", tone)
            b.setFixedHeight(28)
            if cb:
                b.clicked.connect(cb)
            return b

        bl.addWidget(_btn("🔍 Quét Trạng Thái NV", self._handle_scan_all, "primary"))
        bl.addWidget(_btn("▶ Chạy Đã Chọn", self._handle_start_selected, "success"))
        bl.addWidget(_btn("⏹ Dừng Tất Cả", self._handle_stop_all, "danger"))
        bl.addWidget(_btn("⚙ Tọa độ bãi", self._open_spots_dialog, "ghost"))

        bl.addSpacing(8)
        bl.addWidget(QLabel("Chế độ:"))
        self.cb_mode = QComboBox()
        self.cb_mode.setFixedHeight(28)
        self.cb_mode.setMinimumWidth(175)
        for mode_id, mode_lbl in MODE_OPTIONS:
            self.cb_mode.addItem(mode_lbl, mode_id)
        self.cb_mode.currentIndexChanged.connect(self._emit_config_changed)
        bl.addWidget(self.cb_mode)

        self.chk_marlon = QCheckBox("Kèm Marlon (Lv220)")
        self.chk_marlon.toggled.connect(self._emit_config_changed)
        bl.addWidget(self.chk_marlon)

        self.chk_pickup = QCheckBox("Tự nhặt đồ NV (C1:22)")
        self.chk_pickup.setChecked(True)
        self.chk_pickup.toggled.connect(self._emit_config_changed)
        bl.addWidget(self.chk_pickup)

        bl.addStretch(1)
        root.addWidget(bar)

        # 2.5. Thanh chỉnh nhanh Tọa độ làm nhiệm vụ trực tiếp ngay trên tab
        spot_bar = QFrame()
        spot_bar.setProperty("surface", "card")
        spot_bar.setFixedHeight(40)
        sbl = QHBoxLayout(spot_bar)
        sbl.setContentsMargins(8, 4, 8, 4)
        sbl.setSpacing(6)

        lbl_sp = QLabel("📍 Tọa độ NV:")
        lbl_sp.setStyleSheet("color: #2dd4bf; font-weight: 700; font-size: 11px;")
        sbl.addWidget(lbl_sp)

        self.cb_spot = QComboBox()
        self.cb_spot.setFixedHeight(26)
        self.cb_spot.setMinimumWidth(210)
        for skey, sdef in DEFAULT_QUEST_CONFIG["spots"].items():
            self.cb_spot.addItem(str(sdef.get("label", skey)), skey)
        self.cb_spot.currentIndexChanged.connect(self._load_selected_spot_to_bar)
        sbl.addWidget(self.cb_spot)

        sbl.addWidget(QLabel("Warp:"))
        self.ed_spot_cmd = QLineEdit()
        self.ed_spot_cmd.setFixedHeight(26)
        self.ed_spot_cmd.setFixedWidth(135)
        self.ed_spot_cmd.setPlaceholderText("/move losttower7")
        sbl.addWidget(self.ed_spot_cmd)

        sbl.addWidget(QLabel("X:"))
        self.sp_spot_x = QSpinBox()
        self.sp_spot_x.setRange(0, 255)
        self.sp_spot_x.setFixedSize(60, 26)
        sbl.addWidget(self.sp_spot_x)

        sbl.addWidget(QLabel("Y:"))
        self.sp_spot_y = QSpinBox()
        self.sp_spot_y.setRange(0, 255)
        self.sp_spot_y.setFixedSize(60, 26)
        sbl.addWidget(self.sp_spot_y)

        btn_grab = QPushButton("📌 Lấy tọa độ game")
        btn_grab.setProperty("tone", "ghost")
        btn_grab.setFixedHeight(26)
        btn_grab.setToolTip("Lấy tọa độ X, Y hiện tại của nhân vật đang chọn trong game")
        btn_grab.clicked.connect(self._handle_grab_current_coord)
        sbl.addWidget(btn_grab)

        btn_save_sp = QPushButton("💾 Lưu bãi")
        btn_save_sp.setProperty("tone", "primary")
        btn_save_sp.setFixedHeight(26)
        btn_save_sp.clicked.connect(self._save_selected_spot_from_bar)
        sbl.addWidget(btn_save_sp)
        sbl.addStretch(1)
        root.addWidget(spot_bar)

        # 3. Main splitter: Table (top) + Live log (bottom)
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(5)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Chọn", "Slot", "Nhân vật", "Class / Cấp", "Lv / Zen",
            "Nhiệm vụ hiện tại", "Tiến độ (Vật phẩm / Quái)", "Trạng thái", "Thao tác"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        hdr.setSectionResizeMode(6, QHeaderView.Stretch)
        hdr.setSectionResizeMode(7, QHeaderView.Stretch)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(1, 56)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 108)
        self.table.setColumnWidth(4, 118)
        self.table.setColumnWidth(5, 165)
        self.table.setColumnWidth(8, 124)
        splitter.addWidget(self.table)

        # Log panel
        log_box = QFrame()
        log_box.setProperty("surface", "card")
        ll = QVBoxLayout(log_box)
        ll.setContentsMargins(8, 6, 8, 6)
        ll.setSpacing(4)

        lh = QHBoxLayout()
        lbl_l = QLabel("📜 Nhật ký Auto Nhiệm Vụ")
        lbl_l.setStyleSheet("color: #f59e0b; font-weight: 700; font-size: 11px;")
        lh.addWidget(lbl_l)
        lh.addStretch(1)
        btn_clr = QPushButton("Xóa log")
        btn_clr.setProperty("tone", "ghost")
        btn_clr.setFixedHeight(22)
        btn_clr.clicked.connect(lambda: self.log_view.clear())
        lh.addWidget(btn_clr)
        ll.addLayout(lh)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(400)
        self.log_view.setStyleSheet(
            "QPlainTextEdit { background: #0b1120; color: #cbd5e1; "
            "font-family: Consolas, 'Cascadia Mono', monospace; font-size: 11px; "
            "border: 1px solid #1e293b; border-radius: 6px; }"
        )
        ll.addWidget(self.log_view, 1)
        splitter.addWidget(log_box)

        splitter.setSizes([430, 175])
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # CONFIG SYNC
    # ------------------------------------------------------------------
    def apply_config(self, cfg: Dict[str, Any]):
        self._applying_cfg = True
        try:
            self._cfg = copy.deepcopy(cfg or DEFAULT_QUEST_CONFIG)
            mode = str(self._cfg.get("mode", "all_2_3"))
            idx = self.cb_mode.findData(mode)
            if idx >= 0:
                self.cb_mode.setCurrentIndex(idx)
            self.chk_marlon.setChecked(bool(self._cfg.get("include_marlon", False)))
            self.chk_pickup.setChecked(bool(self._cfg.get("auto_pickup_quest_items", True)))
            self._load_selected_spot_to_bar()
        finally:
            self._applying_cfg = False

    def _load_selected_spot_to_bar(self):
        if not hasattr(self, "cb_spot"):
            return
        skey = str(self.cb_spot.currentData() or "scroll_emperor")
        spots = self._cfg.get("spots") or DEFAULT_QUEST_CONFIG["spots"]
        sp = spots.get(skey) or DEFAULT_QUEST_CONFIG["spots"].get(skey, {})
        self.ed_spot_cmd.setText(str(sp.get("map_cmd", "")))
        self.sp_spot_x.setValue(int(sp.get("x", 0)))
        self.sp_spot_y.setValue(int(sp.get("y", 0)))

    def _save_selected_spot_from_bar(self):
        skey = str(self.cb_spot.currentData() or "scroll_emperor")
        spots = self._cfg.setdefault("spots", copy.deepcopy(DEFAULT_QUEST_CONFIG["spots"]))
        sp = copy.deepcopy(spots.get(skey) or DEFAULT_QUEST_CONFIG["spots"].get(skey, {}))
        sp["map_cmd"] = self.ed_spot_cmd.text().strip()
        sp["x"] = int(self.sp_spot_x.value())
        sp["y"] = int(self.sp_spot_y.value())
        spots[skey] = sp
        self._cfg = self.get_config()
        if self.on_config_changed:
            self.on_config_changed(self._cfg)
        self.append_log(f"💾 Đã lưu tọa độ [{sp.get('label', skey)}]: {sp['map_cmd'] or '(qua NPC)'} ({sp['x']}, {sp['y']})")

    def _handle_grab_current_coord(self):
        if not self.on_grab_current_coord:
            return
        res = self.on_grab_current_coord()
        if res and res.get("ok"):
            self.sp_spot_x.setValue(int(res.get("x", 0)))
            self.sp_spot_y.setValue(int(res.get("y", 0)))
            self.append_log(f"📌 Đã lấy tọa độ từ game (Slot {res.get('slot', 1)}): Map #{res.get('map_id', -1)} ({res.get('x')}, {res.get('y')}) — bấm '💾 Lưu bãi' để áp dụng.")
        else:
            self.append_log("⚠️ Chưa có slot game nào kết nối để lấy tọa độ hiện tại.")

    def get_config(self) -> Dict[str, Any]:
        out = copy.deepcopy(self._cfg)
        out["mode"] = str(self.cb_mode.currentData() or "all_2_3")
        out["include_marlon"] = bool(self.chk_marlon.isChecked())
        out["auto_pickup_quest_items"] = bool(self.chk_pickup.isChecked())
        return out

    def _emit_config_changed(self):
        if self._applying_cfg:
            return
        self._cfg = self.get_config()
        if self.on_config_changed:
            self.on_config_changed(self._cfg)

    def _open_spots_dialog(self):
        dlg = QuestSpotsDialogQt(self.get_config(), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._cfg = dlg.get_updated_config()
            self.apply_config(self._cfg)
            if self.on_config_changed:
                self.on_config_changed(self._cfg)
            self.append_log("💾 Đã lưu cấu hình tọa độ bãi farm nhiệm vụ.")

    # ------------------------------------------------------------------
    # SLOT TABLE MANAGEMENT
    # ------------------------------------------------------------------
    def add_slot_row(self, ctrl):
        s_idx = int(ctrl.slot_idx)
        if s_idx in self._rows:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)

        chk_wrap = QWidget()
        cl = QHBoxLayout(chk_wrap)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setAlignment(Qt.AlignCenter)
        chk = QCheckBox()
        chk.setChecked(True)
        chk.toggled.connect(lambda _: self._update_badge())
        cl.addWidget(chk)
        self.table.setCellWidget(r, 0, chk_wrap)

        def _item(text, align=Qt.AlignVCenter | Qt.AlignLeft, color="#e2e8f0"):
            it = QTableWidgetItem(text)
            it.setTextAlignment(align)
            it.setForeground(QBrush(QColor(color)))
            return it

        it_slot = _item(f"Slot {s_idx}", Qt.AlignCenter, "#38bdf8")
        it_char = _item("--", Qt.AlignVCenter | Qt.AlignLeft, "#f1f5f9")
        it_cls = _item("--", Qt.AlignCenter, "#cbd5e1")
        it_lv = _item("--", Qt.AlignCenter, "#94a3b8")
        it_q = _item("Chưa quét", Qt.AlignVCenter | Qt.AlignLeft, "#94a3b8")
        it_prog = _item("--", Qt.AlignVCenter | Qt.AlignLeft, "#cbd5e1")
        it_status = _item("Chờ lệnh", Qt.AlignVCenter | Qt.AlignLeft, "#94a3b8")

        for col, it in ((1, it_slot), (2, it_char), (3, it_cls), (4, it_lv), (5, it_q), (6, it_prog), (7, it_status)):
            self.table.setItem(r, col, it)

        act_wrap = QWidget()
        al = QHBoxLayout(act_wrap)
        al.setContentsMargins(4, 2, 4, 2)
        al.setSpacing(4)
        btn_toggle = QPushButton("▶ Chạy")
        btn_toggle.setProperty("tone", "success")
        btn_toggle.setFixedHeight(24)
        btn_toggle.clicked.connect(lambda _=False, s=s_idx: self.on_toggle_slot and self.on_toggle_slot(s))

        btn_scan = QPushButton("🔍")
        btn_scan.setProperty("tone", "ghost")
        btn_scan.setFixedSize(28, 24)
        btn_scan.setToolTip("Quét trạng thái nhiệm vụ của slot này")
        btn_scan.clicked.connect(lambda _=False, s=s_idx: self.on_scan_slot and self.on_scan_slot(s))

        al.addWidget(btn_toggle, 1)
        al.addWidget(btn_scan)
        self.table.setCellWidget(r, 8, act_wrap)

        self._rows[s_idx] = {
            "row": r,
            "chk": chk,
            "it_char": it_char,
            "it_cls": it_cls,
            "it_lv": it_lv,
            "it_q": it_q,
            "it_prog": it_prog,
            "it_status": it_status,
            "btn_toggle": btn_toggle,
        }
        self._update_badge()

    def remove_slot_row(self, slot_idx: int):
        info = self._rows.pop(int(slot_idx), None)
        self._slot_states.pop(int(slot_idx), None)
        self._row_cache.pop(int(slot_idx), None)
        if not info:
            return
        row_idx = info["row"]
        self.table.removeRow(row_idx)
        for s_id, meta in self._rows.items():
            if meta["row"] > row_idx:
                meta["row"] -= 1
        self._update_badge()

    def get_selected_slots(self) -> List[int]:
        return [s for s, m in sorted(self._rows.items()) if m["chk"].isChecked()]

    def _update_badge(self):
        sel = len(self.get_selected_slots())
        running = sum(1 for st in self._slot_states.values() if st.get("running"))
        self.lbl_badge.setText(f"{running} đang chạy · {sel}/{len(self._rows)} slot chọn")

    def set_slot_quest_state(self, slot_idx: int, payload: Dict[str, Any]):
        s_idx = int(slot_idx)
        self._slot_states[s_idx] = dict(payload or {})
        meta = self._rows.get(s_idx)
        if not meta:
            return

        running = bool(payload.get("running", False))
        status_text = str(payload.get("status_text", "Chờ lệnh"))
        status_color = str(payload.get("status_color", "#94a3b8"))
        summary = payload.get("summary") or {}

        if summary.get("ok"):
            s_name = str(summary.get("name") or payload.get("char_name") or "").strip()
            s_pid = payload.get("pid")
            if s_name and s_name not in ("--", "---"):
                disp_name = f"{s_name} (#{s_pid})" if s_pid else s_name
                meta["it_char"].setText(disp_name)
                meta["it_char"].setForeground(QBrush(QColor("#f1f5f9")))
            cls_txt = str(summary.get("tier_text", "--"))
            lv = int(summary.get("level", 0))
            zen = int(summary.get("zen", 0))
            zen_m = f"{zen / 1_000_000:.1f}M" if zen >= 1_000_000 else f"{zen:,}"
            lv_txt = f"Lv {lv} · {zen_m}"
            q_txt = str(summary.get("current_quest_label", "--"))
            prog_txt = str(summary.get("progress_text", "--"))
            q_color = "#22c55e" if summary.get("next_action") == "DONE" else "#f59e0b"
        else:
            s_name = str(payload.get("char_name") or "").strip()
            s_pid = payload.get("pid")
            if s_name and s_name not in ("--", "---"):
                meta["it_char"].setText(f"{s_name} (#{s_pid})" if s_pid else s_name)
                meta["it_char"].setForeground(QBrush(QColor("#f1f5f9")))
            cls_txt = "--"
            lv_txt = "--"
            q_txt = str(summary.get("current_quest_label", "Chưa quét"))
            prog_txt = "--"
            q_color = "#64748b"

        meta["it_cls"].setText(cls_txt)
        meta["it_lv"].setText(lv_txt)
        meta["it_q"].setText(q_txt)
        meta["it_q"].setForeground(QBrush(QColor(q_color)))
        meta["it_prog"].setText(prog_txt)
        meta["it_status"].setText(status_text)
        meta["it_status"].setForeground(QBrush(QColor(status_color)))

        btn = meta["btn_toggle"]
        if running:
            btn.setText("⏹ Dừng")
            btn.setProperty("tone", "danger")
        else:
            btn.setText("▶ Chạy")
            btn.setProperty("tone", "success")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        self._update_badge()

    def update_from_state_snapshots(self, snapshots: Dict[int, Any]):
        """Đồng bộ tên nhân vật / trạng thái kết nối từ AppStateManager (dict hoặc object)."""
        for s_idx, meta in self._rows.items():
            snap = snapshots.get(s_idx)
            if not snap:
                continue
            if isinstance(snap, dict):
                char_name = str(snap.get("char_name") or snap.get("character_name") or "").strip()
                pid = snap.get("assigned_pid") or snap.get("pid")
                connected = bool(pid)
            else:
                char_name = str(getattr(snap, "char_name", "") or getattr(snap, "character_name", "") or "").strip()
                pid = getattr(snap, "assigned_pid", None) or getattr(snap, "pid", None)
                connected = bool(getattr(snap, "connected", False) or pid)
            if char_name in ("--", "---"):
                char_name = ""
            disp = f"{char_name} (#{pid})" if (char_name and pid) else (char_name or (f"PID {pid}" if pid else "--"))
            key = (disp, connected)
            if self._row_cache.get(s_idx) != key:
                self._row_cache[s_idx] = key
                meta["it_char"].setText(disp)
                meta["it_char"].setForeground(QBrush(QColor("#f1f5f9" if connected else "#64748b")))

    def append_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    # ------------------------------------------------------------------
    # BUTTON HANDLERS
    # ------------------------------------------------------------------
    def _handle_scan_all(self):
        if self.on_scan_all:
            self.on_scan_all()

    def _handle_start_selected(self):
        if self.on_start_selected:
            self.on_start_selected(self.get_selected_slots())

    def _handle_stop_all(self):
        if self.on_stop_all:
            self.on_stop_all()
