# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - AUTO TRAIN SLOTS TAB
Bảng điều khiển đa slot (hỗ trợ 1..50+ slot mượt 60fps) dùng QTableWidget + State Diffing.
"""

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

_PID_RE = re.compile(r"\((?:PID\s*)?(\d+)\)")
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from ui_qt.theme import CLASS_COLORS


def get_default_profile_options() -> List[str]:
    try:
        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "autotrain_profiles.json",
        )
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profiles", {})
            opts = [
                profiles[k].get("name") or f"Config {k}"
                for k in sorted(profiles.keys(), key=lambda x: int(x) if str(x).isdigit() else 999)
            ]
            if opts:
                return opts
    except Exception:
        pass
    return [f"Config {i}" for i in range(1, 11)]


class TrainTabQt(QWidget):
    """Tab 01 Auto Train — Native Qt6 60fps."""

    def __init__(
        self,
        controllers: list,
        on_toggle_slot: Optional[Callable[[int], None]] = None,
        on_toggle_all: Optional[Callable[[bool], None]] = None,
        on_connect_all: Optional[Callable[[], None]] = None,
        on_assign_all: Optional[Callable[[], None]] = None,
        on_refresh_games: Optional[Callable[[], None]] = None,
        on_arrange_windows: Optional[Callable[[str], None]] = None,
        on_slot_pid_selected: Optional[Callable[[int, str], None]] = None,
        on_slot_profile_selected: Optional[Callable[[int, str], None]] = None,
        on_stack_jewels: Optional[Callable[[], None]] = None,
        on_devil_config: Optional[Callable[[], None]] = None,
        on_point_config: Optional[Callable[[], None]] = None,
        on_toggle_point: Optional[Callable[[int], None]] = None,
        on_open_point_config: Optional[Callable[[int], None]] = None,
        on_close_games: Optional[Callable[[], None]] = None,
        on_open_slot_config: Optional[Callable[[int], None]] = None,
        on_add_slot: Optional[Callable[[], None]] = None,
        on_remove_slot: Optional[Callable[[], None]] = None,
        on_telegram_config: Optional[Callable[[], None]] = None,
        on_party_config: Optional[Callable[[], None]] = None,
        on_slot_delay_changed: Optional[Callable[[int, float], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.controllers = controllers
        self.on_toggle_slot = on_toggle_slot
        self.on_toggle_all = on_toggle_all
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
        self.on_open_slot_config = on_open_slot_config
        self.on_add_slot = on_add_slot
        self.on_remove_slot = on_remove_slot
        self.on_telegram_config = on_telegram_config
        self.on_party_config = on_party_config
        self.on_slot_delay_changed = on_slot_delay_changed

        self.process_options: List[str] = ["--"]
        self.profile_options: List[str] = get_default_profile_options()
        self._rows: Dict[int, Dict[str, Any]] = {}
        self._row_state_cache: Dict[int, Dict[str, Any]] = {}
        self._last_summary: str = ""

        self._build_ui()
        for ctrl in self.controllers:
            self.add_slot_row(ctrl.slot_idx, ctrl)
        self._update_summary()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)

        # 1. Main action toolbar
        tb = QFrame()
        tb.setProperty("surface", "toolbar")
        tb.setFixedHeight(42)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(5)

        def _btn(text, cb, tone="neutral", w=None, tip=""):
            b = QPushButton(text)
            if tone != "neutral":
                b.setProperty("tone", tone)
            b.setFixedHeight(28)
            if w:
                b.setFixedWidth(w)
            if tip:
                b.setToolTip(tip)
            if cb:
                b.clicked.connect(cb)
            return b

        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.VLine)
            s.setFixedHeight(18)
            s.setStyleSheet("color: #243149;")
            return s

        tl.addWidget(_btn("🔄 Quét Game", self.on_refresh_games, tip="Quét lại danh sách tiến trình MEGAMU đang chạy"))
        tl.addWidget(_btn("👥 Gán All", self.on_assign_all, tip="Tự động phân bổ toàn bộ cửa sổ MEGAMU vào các slot (tự mở thêm slot theo License)"))
        tl.addWidget(_btn("🔗 Nối All", self.on_connect_all, tip="Kết nối / nối lại Direct Engine cho toàn bộ slot"))
        tl.addWidget(_sep())

        self.combo_arrange = QComboBox()
        self.combo_arrange.addItems(["3x2", "2x2", "3x3", "4x2", "4x3", "2x1", "1x2", "auto"])
        self.combo_arrange.setFixedSize(78, 28)
        self.combo_arrange.setToolTip("Chọn bố cục chia lưới cửa sổ game")
        tl.addWidget(self.combo_arrange)

        tl.addWidget(_btn("⊞ Xếp", lambda: self.on_arrange_windows and self.on_arrange_windows(self.combo_arrange.currentText()), tip="Sắp xếp các cửa sổ game theo lưới"))
        tl.addWidget(_btn("✕ Đóng", self.on_close_games, tip="Đóng toàn bộ cửa sổ MEGAMU.exe"))
        tl.addWidget(_sep())

        tl.addWidget(_btn("+ Slot", self.on_add_slot, tip="Thêm 1 slot mới (tối đa theo License)"))
        tl.addWidget(_btn("- Slot", self.on_remove_slot, tip="Xóa slot cuối cùng"))

        tl.addStretch(1)

        self.lbl_summary = QLabel("🟢 0/0 Đang chạy  ·  🔗 0/0 Đã nối")
        self.lbl_summary.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px; padding-right: 6px;")
        tl.addWidget(self.lbl_summary)

        btn_start_all = _btn("▶ BẬT TẤT CẢ", lambda: self.on_toggle_all and self.on_toggle_all(True), tone="success")
        btn_start_all.setMinimumWidth(116)
        btn_stop_all = _btn("⏹ DỪNG TẤT CẢ", lambda: self.on_toggle_all and self.on_toggle_all(False), tone="danger")
        btn_stop_all.setMinimumWidth(118)
        tl.addWidget(btn_start_all)
        tl.addWidget(btn_stop_all)
        root.addWidget(tb)

        # 2. Shared Utilities Bar (không chứa Auto Login / Nhập Tài Khoản)
        ub = QFrame()
        ub.setProperty("surface", "utilbar")
        ub.setFixedHeight(34)
        ul = QHBoxLayout(ub)
        ul.setContentsMargins(10, 3, 10, 3)
        ul.setSpacing(6)

        lbl_u = QLabel("⚡ TIỆN ÍCH DÙNG CHUNG:")
        lbl_u.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 10px;")
        ul.addWidget(lbl_u)

        for label, cb, tip in (
            ("💎 Gom Ngọc", self.on_stack_jewels, "Tự động nén và gom tất cả loại ngọc trong túi đồ"),
            ("🔥 Devil Square", self.on_devil_config, "Cài đặt & đi sự kiện Devil Square"),
            ("⭐ Cộng Point", self.on_point_config, "Cấu hình tự động cộng điểm tiềm năng"),
            ("🤝 Auto PT", self.on_party_config, "Tự động ghép nhiều nhóm Party theo mật khẩu"),
            ("📱 Telegram Bot", self.on_telegram_config, "Cấu hình thông báo Telegram"),
        ):
            if cb:
                b = QPushButton(label)
                b.setFixedHeight(24)
                b.setToolTip(tip)
                b.clicked.connect(cb)
                ul.addWidget(b)
        ul.addStretch(1)
        root.addWidget(ub)

        # 3. High-Performance Native QTableWidget
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "#", "Hệ", "Tiến trình Game (PID)", "Cấu hình",
            "Cấp độ / RS", "Bản đồ & Tọa độ", "Server",
            "Chờ ra bãi", "Trạng thái", "Thao tác"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(False)
        for col in range(10):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive if col in (2, 3, 4, 5, 8) else QHeaderView.Fixed)

        # Cột cố định + tỷ lệ cân đối tự co giãn đều trên mọi độ phân giải (1200px / 1920px / 2560px)
        self._fixed_cols = {0: 46, 1: 52, 6: 66, 7: 84, 9: 246}
        self._flex_weights = {
            2: (0.31, 195),  # Tiến trình Game (PID)
            3: (0.15, 124),  # Cấu hình (hiển thị trọn vẹn "Config 10")
            4: (0.16, 110),  # Cấp độ / RS
            5: (0.22, 160),  # Bản đồ & Tọa độ (vừa mắt, không giãn quá rộng)
            8: (0.16, 110),  # Trạng thái
        }
        for col, w in self._fixed_cols.items():
            self.table.setColumnWidth(col, w)
        for col, (_ratio, min_w) in self._flex_weights.items():
            self.table.setColumnWidth(col, min_w)

        root.addWidget(self.table, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebalance_columns()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebalance_columns()

    def _rebalance_columns(self):
        try:
            avail = self.table.viewport().width()
            if avail <= 200:
                return
            fixed_sum = sum(self._fixed_cols.values())
            flex_space = max(600, avail - fixed_sum - 2)
            allocated = 0
            flex_cols = list(self._flex_weights.items())
            for idx, (col, (ratio, min_w)) in enumerate(flex_cols):
                if idx == len(flex_cols) - 1:
                    w = max(min_w, flex_space - allocated)
                else:
                    w = max(min_w, int(flex_space * ratio))
                    allocated += w
                if self.table.columnWidth(col) != w:
                    self.table.setColumnWidth(col, w)
        except Exception:
            pass

    def add_slot_row(self, slot_idx: int, ctrl: Any = None):
        if slot_idx in self._rows:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 38)

        # Col 0: #01
        it_num = QTableWidgetItem(f"#{slot_idx:02d}")
        it_num.setTextAlignment(Qt.AlignCenter)
        it_num.setForeground(QBrush(QColor("#38bdf8")))
        self.table.setItem(r, 0, it_num)

        # Col 1: Class badge (pure QTableWidgetItem — 0 child widgets!)
        it_cls = QTableWidgetItem("MU")
        it_cls.setTextAlignment(Qt.AlignCenter)
        it_cls.setBackground(QBrush(QColor("#152038")))
        it_cls.setForeground(QBrush(QColor("#64748b")))
        self.table.setItem(r, 1, it_cls)

        # Col 2: Process combo (direct cell widget — 0 wrapper frames)
        cb_proc = QComboBox()
        cb_proc.addItems(self.process_options)
        cb_proc.currentTextChanged.connect(
            lambda val, s=slot_idx: self.on_slot_pid_selected and self.on_slot_pid_selected(s, val)
        )
        self.table.setCellWidget(r, 2, cb_proc)

        # Col 3: Profile combo (direct cell widget)
        cb_prof = QComboBox()
        cb_prof.addItems(self.profile_options)
        if ctrl is not None:
            p_idx = int(getattr(ctrl, "profile_index", 1) or 1)
            target_p = f"Config {p_idx}"
            if cb_prof.findText(target_p) >= 0:
                cb_prof.setCurrentText(target_p)
        cb_prof.currentTextChanged.connect(
            lambda val, s=slot_idx: self.on_slot_profile_selected and self.on_slot_profile_selected(s, val)
        )
        self.table.setCellWidget(r, 3, cb_prof)

        # Col 4: Level / RS
        it_lvl = QTableWidgetItem("⭐ Lv ---")
        self.table.setItem(r, 4, it_lvl)

        # Col 5: Map & Coords
        it_map = QTableWidgetItem("📍 --- (--,--)")
        self.table.setItem(r, 5, it_map)

        # Col 6: Server
        it_srv = QTableWidgetItem("Sv ---")
        it_srv.setTextAlignment(Qt.AlignCenter)
        it_srv.setForeground(QBrush(QColor("#94a3b8")))
        self.table.setItem(r, 6, it_srv)

        # Col 7: Respawn delay (direct cell widget)
        sp_delay = QSpinBox()
        sp_delay.setRange(3, 600)
        sp_delay.setSuffix("s")
        sp_delay.setAlignment(Qt.AlignCenter)
        init_delay = int(float(getattr(ctrl, "respawn_delay", 15.0) or 15.0)) if ctrl else 15
        sp_delay.setValue(init_delay)
        sp_delay.editingFinished.connect(
            lambda s=slot_idx, sp=sp_delay: self.on_slot_delay_changed and self.on_slot_delay_changed(s, float(sp.value()))
        )
        self.table.setCellWidget(r, 7, sp_delay)

        # Col 8: Status chip (pure QTableWidgetItem — 0 child widgets!)
        it_status = QTableWidgetItem("● Sẵn sàng")
        it_status.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        it_status.setBackground(QBrush(QColor("#152038")))
        it_status.setForeground(QBrush(QColor("#94a3b8")))
        self.table.setItem(r, 8, it_status)

        # Col 9: Action buttons (Point / Config / BẬT) — nút sắc nét, cân đối
        act_w = QWidget()
        act_w.setObjectName("CellBox")
        al = QHBoxLayout(act_w)
        al.setContentsMargins(6, 0, 6, 0)
        al.setSpacing(6)
        al.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)

        btn_pt = QPushButton("Point")
        btn_pt.setProperty("rowBtn", True)
        btn_pt.setProperty("tone", "pointOn" if (ctrl and getattr(ctrl, "auto_add_point", False)) else "pointOff")
        btn_pt.setFixedSize(64, 26)
        btn_pt.setCursor(Qt.PointingHandCursor)
        btn_pt.setToolTip("Click trái: Bật/Tắt Tự Cộng Point · Click phải: Mở Cài đặt Point")
        btn_pt.setContextMenuPolicy(Qt.CustomContextMenu)
        btn_pt.clicked.connect(lambda _=False, s=slot_idx: self.on_toggle_point and self.on_toggle_point(s))
        btn_pt.customContextMenuRequested.connect(lambda _p, s=slot_idx: self.on_open_point_config and self.on_open_point_config(s))

        btn_cfg = QPushButton("Config")
        btn_cfg.setProperty("rowBtn", True)
        btn_cfg.setProperty("tone", "cfgBtn")
        btn_cfg.setFixedSize(66, 26)
        btn_cfg.setCursor(Qt.PointingHandCursor)
        btn_cfg.setToolTip(f"Mở cấu hình bãi train cho Slot #{slot_idx:02d}")
        btn_cfg.clicked.connect(lambda _=False, s=slot_idx: self.on_open_slot_config and self.on_open_slot_config(s))

        btn_run = QPushButton("▶ BẬT")
        btn_run.setProperty("rowBtn", True)
        btn_run.setProperty("tone", "success")
        btn_run.setFixedSize(86, 26)
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.clicked.connect(lambda _=False, s=slot_idx: self.on_toggle_slot and self.on_toggle_slot(s))

        al.addWidget(btn_pt)
        al.addWidget(btn_cfg)
        al.addWidget(btn_run)
        self.table.setCellWidget(r, 9, act_w)

        self._rows[slot_idx] = {
            "row": r,
            "it_num": it_num,
            "it_cls": it_cls,
            "cb_proc": cb_proc,
            "cb_prof": cb_prof,
            "it_lvl": it_lvl,
            "it_map": it_map,
            "it_srv": it_srv,
            "sp_delay": sp_delay,
            "it_status": it_status,
            "btn_pt": btn_pt,
            "btn_run": btn_run,
            "is_running": False,
            "auto_add_point": bool(getattr(ctrl, "auto_add_point", False)) if ctrl else False,
            "connected": False,
        }
        self._row_state_cache[slot_idx] = {}
        self._update_summary()

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
        self._row_state_cache.pop(last_idx, None)
        if info is not None:
            self.table.removeRow(info["row"])
        self._update_summary()

    def set_slot_point_state(self, slot_idx: int, enabled: bool):
        info = self._rows.get(slot_idx)
        if not info:
            return
        info["auto_add_point"] = bool(enabled)
        btn = info["btn_pt"]
        btn.setProperty("tone", "pointOn" if enabled else "pointOff")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    @staticmethod
    def _extract_pid(text: str) -> Optional[int]:
        if not text:
            return None
        m = _PID_RE.search(text)
        return int(m.group(1)) if m else None

    def update_process_options_all(self, options: List[str]):
        # Loại trùng theo PID (mỗi PID chỉ giữ đúng 1 nhãn mới nhất)
        deduped: List[str] = []
        seen_pids = set()
        seen_texts = set()
        for opt in (options or ["--"]):
            if not opt or opt in seen_texts:
                continue
            p = self._extract_pid(opt)
            if p is not None:
                if p in seen_pids:
                    continue
                seen_pids.add(p)
            seen_texts.add(opt)
            deduped.append(opt)
        if not deduped:
            deduped = ["--"]

        if deduped == self.process_options:
            return
        self.process_options = deduped
        pid_to_opt = {}
        for opt in deduped:
            p = self._extract_pid(opt)
            if p is not None:
                pid_to_opt[p] = opt

        for slot_idx, info in self._rows.items():
            cb: QComboBox = info["cb_proc"]
            cur = cb.currentText()
            cur_pid = self._extract_pid(cur)
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(deduped)
            if cur and cb.findText(cur) >= 0:
                cb.setCurrentText(cur)
            elif cur_pid is not None and cur_pid in pid_to_opt:
                # Cùng PID nhưng đổi tên/server (VD: Sv2 -> Sv30): cập nhật sang nhãn mới, KHÔNG thêm nhãn cũ!
                new_label = pid_to_opt[cur_pid]
                cb.setCurrentText(new_label)
                self._row_state_cache.setdefault(slot_idx, {})["disp_proc"] = new_label
            elif cur and cur != "--" and info.get("connected"):
                cb.addItem(cur)
                cb.setCurrentText(cur)
            else:
                cb.setCurrentText("--")
            cb.blockSignals(False)

    def update_profile_options_all(self, options: List[str]):
        new_opts = list(options or [])
        if not new_opts or new_opts == self.profile_options:
            return
        self.profile_options = new_opts
        for info in self._rows.values():
            cb: QComboBox = info["cb_prof"]
            cur = cb.currentText()
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(new_opts)
            if cur and cb.findText(cur) >= 0:
                cb.setCurrentText(cur)
            cb.blockSignals(False)

    def update_slots_data(self, dirty_slots: List[Dict[str, Any]]):
        if not dirty_slots:
            return
        for s_data in dirty_slots:
            idx = s_data.get("slot_idx")
            info = self._rows.get(idx)
            if not info:
                continue
            cache = self._row_state_cache[idx]

            # 1. Class badge (pure QTableWidgetItem — 0 QSS re-parse!)
            c_code = (s_data.get("class_code") or "").strip().upper()
            if cache.get("class_code") != c_code:
                cache["class_code"] = c_code
                it_cls = info["it_cls"]
                if c_code in CLASS_COLORS:
                    fg_c, bg_c = CLASS_COLORS[c_code]
                    it_cls.setText(c_code)
                    it_cls.setBackground(QBrush(QColor(bg_c)))
                    it_cls.setForeground(QBrush(QColor(fg_c)))
                elif c_code:
                    it_cls.setText(c_code[:4])
                    it_cls.setBackground(QBrush(QColor("#182338")))
                    it_cls.setForeground(QBrush(QColor("#38bdf8")))
                else:
                    it_cls.setText("MU")
                    it_cls.setBackground(QBrush(QColor("#152038")))
                    it_cls.setForeground(QBrush(QColor("#64748b")))

            # 2. PID / Process combo
            pid = s_data.get("assigned_pid")
            c_name = s_data.get("char_name", "---")
            info["connected"] = bool(pid)
            if pid:
                matched = None
                for opt in self.process_options:
                    if f"({pid})" in opt or f"(PID {pid})" in opt or opt.endswith(f"{pid})"):
                        matched = opt
                        break
                disp_proc = matched or (
                    f"{c_name} (PID {pid})" if (c_name and c_name != "---") else f"MEGAMU (PID {pid})"
                )
            else:
                disp_proc = "--"

            if cache.get("disp_proc") != disp_proc:
                cache["disp_proc"] = disp_proc
                cb = info["cb_proc"]
                cb.blockSignals(True)
                if pid:
                    # Xóa nhãn cũ trùng PID trước khi đặt nhãn mới (tránh trùng Sv2 + Sv30 cùng 1 PID)
                    for row_i in range(cb.count() - 1, -1, -1):
                        it_txt = cb.itemText(row_i)
                        if it_txt != disp_proc and self._extract_pid(it_txt) == pid:
                            cb.removeItem(row_i)
                if cb.findText(disp_proc) < 0:
                    cb.addItem(disp_proc)
                cb.setCurrentText(disp_proc)
                cb.blockSignals(False)

            # 3. Profile
            prof = s_data.get("profile")
            if prof and cache.get("profile") != prof:
                cache["profile"] = prof
                cb = info["cb_prof"]
                if cb.findText(prof) >= 0:
                    cb.blockSignals(True)
                    cb.setCurrentText(prof)
                    cb.blockSignals(False)

            # 4. Level & Resets
            level = s_data.get("level", "---")
            resets = s_data.get("resets", 0)
            lvl_txt = f"⭐ Lv {level}" if level not in (None, "", "---") else "⭐ Lv ---"
            if resets:
                lvl_txt = f"{lvl_txt} (RS {resets})"
            if cache.get("lvl_txt") != lvl_txt:
                cache["lvl_txt"] = lvl_txt
                info["it_lvl"].setText(lvl_txt)

            # 5. Map & Coords
            map_name = s_data.get("map")
            clean_m = map_name.replace("Map:", "").strip() if map_name else ""
            m_txt = clean_m if (clean_m and clean_m != "---") else "---"
            coords = s_data.get("coords", "--,--")
            c_xy = "--,--"
            if coords and str(coords).strip() not in ("", "--,--", "--", "--, --"):
                parts = [p.strip() for p in str(coords).replace("/", ",").split(",") if p.strip()]
                c_xy = f"{parts[0]},{parts[1]}" if len(parts) >= 2 else str(coords).strip()
            mc_txt = f"📍 {m_txt} ({c_xy})"
            if cache.get("mc_txt") != mc_txt:
                cache["mc_txt"] = mc_txt
                info["it_map"].setText(mc_txt)

            # 6. Server
            srv = s_data.get("server", "---")
            srv_txt = f"Sv {srv}" if (srv and srv != "---" and not str(srv).startswith("Sv")) else (str(srv) if (srv and srv != "---") else "Sv ---")
            if cache.get("srv_txt") != srv_txt:
                cache["srv_txt"] = srv_txt
                info["it_srv"].setText(srv_txt)

            # 7. Status chip
            status = str(s_data.get("status", "Sẵn sàng"))
            st_low = status.lower()
            if any(k in st_low for k in ("tự động đánh", "tu dong danh", "auto attack", "running", "đang chạy", "at spot", "tại bãi")):
                disp_st, fg_s, bg_s = "● Đang chạy", "#4ade80", "#052e1c"
            elif any(k in st_low for k in ("moving", "chạy ra bãi", "di chuyển")):
                disp_st, fg_s, bg_s = "● Di chuyển", "#fbbf24", "#2a1c05"
            elif any(k in st_low for k in ("mất kết nối", "game đã đóng", "closed", "disconnect")):
                disp_st, fg_s, bg_s = "● Mất kết nối", "#fb7185", "#2a0b10"
            elif any(k in st_low for k in ("connected", "đã kết nối")):
                disp_st, fg_s, bg_s = "● Đã kết nối", "#38bdf8", "#0b1f33"
            elif any(k in st_low for k in ("stopped", "đã dừng")):
                disp_st, fg_s, bg_s = "● Đã dừng", "#94a3b8", "#152038"
            elif any(k in st_low for k in ("idle", "chờ", "sẵn sàng")):
                disp_st, fg_s, bg_s = "● Sẵn sàng", "#94a3b8", "#152038"
            else:
                disp_st, fg_s, bg_s = f"● {status[:14]}", "#94a3b8", "#152038"

            if cache.get("disp_st") != disp_st:
                cache["disp_st"] = disp_st
                it_st = info["it_status"]
                it_st.setText(disp_st)
                it_st.setBackground(QBrush(QColor(bg_s)))
                it_st.setForeground(QBrush(QColor(fg_s)))

            # 8. Running toggle button
            is_running = bool(s_data.get("is_running", False))
            if info["is_running"] != is_running:
                info["is_running"] = is_running
                btn = info["btn_run"]
                btn.setText("⏹ DỪNG" if is_running else "▶ BẬT")
                btn.setProperty("tone", "danger" if is_running else "success")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                info["it_num"].setForeground(QBrush(QColor("#2dd4bf" if is_running else "#38bdf8")))

            # 9. Auto add point
            if "auto_add_point" in s_data:
                pt_on = bool(s_data["auto_add_point"])
                if info["auto_add_point"] != pt_on:
                    self.set_slot_point_state(idx, pt_on)

        self._update_summary()

    def _update_summary(self):
        running = sum(1 for r in self._rows.values() if r["is_running"])
        connected = sum(1 for r in self._rows.values() if r["connected"])
        total = len(self._rows)
        txt = f"🟢 {running}/{total} Đang chạy  ·  🔗 {connected}/{total} Đã nối"
        if txt != self._last_summary:
            self._last_summary = txt
            self.lbl_summary.setText(txt)
