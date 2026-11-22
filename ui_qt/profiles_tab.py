# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - PROFILES & STAGES CONFIG VIEW
Quản lý 10 cấu hình bãi train (Config 1..10) với QTableWidget siêu mượt.
"""

from typing import Any, Callable, List, Optional
from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QAbstractItemView
)
from PySide6.QtGui import QColor, QBrush

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]


class ProfilesTabQt(QWidget):
    """Tab 02 Config — cấu hình 10 Profile và 10 chặng train theo level."""

    def __init__(
        self,
        maps_list: List[str],
        config_persistence_mgr: Any,
        on_profile_saved: Optional[Callable[[int], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.maps_list = maps_list or ["Lorencia", "Noria", "Devias", "Arena"]
        self.persistence_mgr = config_persistence_mgr
        self.on_profile_saved = on_profile_saved
        self.on_log = on_log
        self.current_profile_idx = 1
        self._loading = False
        self.editor_rows: List[dict] = []

        self._build_ui()
        self.load_profile_into_editor(1)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Toolbar chọn profile
        tb = QFrame()
        tb.setProperty("surface", "toolbar")
        tb.setFixedHeight(46)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(12, 6, 12, 6)
        tl.setSpacing(8)

        lbl_title = QLabel("⚙ CẤU HÌNH BÃI TRAIN:")
        lbl_title.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px;")
        tl.addWidget(lbl_title)

        self.combo_profile = QComboBox()
        self.combo_profile.addItems(PROFILE_NAMES)
        self.combo_profile.setFixedWidth(120)
        self.combo_profile.currentTextChanged.connect(self._on_profile_changed)
        tl.addWidget(self.combo_profile)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #243149;")
        tl.addWidget(sep)

        lbl_delay = QLabel("⏳ Chờ ra bãi (giây):")
        lbl_delay.setStyleSheet("color: #94a3b8;")
        tl.addWidget(lbl_delay)

        self.spin_respawn = QSpinBox()
        self.spin_respawn.setRange(3, 600)
        self.spin_respawn.setValue(15)
        self.spin_respawn.setFixedWidth(72)
        self.spin_respawn.setToolTip("Thời gian chờ tại Lorencia sau khi chết trước khi tự ra lại bãi")
        tl.addWidget(self.spin_respawn)

        tl.addStretch(1)

        btn_reload = QPushButton("🔄 Tải Lại")
        btn_reload.setProperty("tone", "ghost")
        btn_reload.setFixedHeight(28)
        btn_reload.clicked.connect(self.reload_from_file)
        tl.addWidget(btn_reload)

        btn_save = QPushButton("💾 Lưu Cấu Hình")
        btn_save.setProperty("tone", "primary")
        btn_save.setFixedHeight(28)
        btn_save.clicked.connect(lambda: self.save_current_profile(silent=False))
        tl.addWidget(btn_save)

        root.addWidget(tb)

        # Bảng 10 chặng train
        self.table = QTableWidget(10, 7)
        self.table.setHorizontalHeaderLabels([
            "CHẶNG", "MIN LV", "MAX LV", "BẢN ĐỒ (MAP)", "TỌA ĐỘ X", "TỌA ĐỘ Y", "THAO TÁC"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(True)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 72)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 90)

        self._map_model = QStringListModel([""] + list(self.maps_list), self)
        for r in range(10):
            self.table.setRowHeight(r, 34)

            it_idx = QTableWidgetItem(f"#{r + 1:02d}")
            it_idx.setTextAlignment(Qt.AlignCenter)
            it_idx.setForeground(QBrush(QColor("#38bdf8")))
            self.table.setItem(r, 0, it_idx)

            min_ed = QLineEdit()
            min_ed.setAlignment(Qt.AlignCenter)
            min_ed.setPlaceholderText("1")
            self.table.setCellWidget(r, 1, min_ed)

            max_ed = QLineEdit()
            max_ed.setAlignment(Qt.AlignCenter)
            max_ed.setPlaceholderText("400")
            self.table.setCellWidget(r, 2, max_ed)

            map_cb = QComboBox()
            map_cb.setModel(self._map_model)
            self.table.setCellWidget(r, 3, map_cb)

            x_ed = QLineEdit()
            x_ed.setAlignment(Qt.AlignCenter)
            x_ed.setPlaceholderText("X")
            self.table.setCellWidget(r, 4, x_ed)

            y_ed = QLineEdit()
            y_ed.setAlignment(Qt.AlignCenter)
            y_ed.setPlaceholderText("Y")
            self.table.setCellWidget(r, 5, y_ed)

            btn_clr = QPushButton("Xóa")
            btn_clr.setProperty("tone", "ghost")
            btn_clr.clicked.connect(lambda _=False, row_idx=r: self._clear_row(row_idx))
            self.table.setCellWidget(r, 6, btn_clr)

            self.editor_rows.append({
                "min": min_ed, "max": max_ed, "map": map_cb, "x": x_ed, "y": y_ed
            })

        root.addWidget(self.table, 1)

    @staticmethod
    def _wrap(widget: QWidget) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(5, 4, 5, 4)
        lay.addWidget(widget)
        return box

    def _clear_row(self, r: int):
        row = self.editor_rows[r]
        row["min"].setText("")
        row["max"].setText("")
        row["map"].setCurrentIndex(0)
        row["x"].setText("")
        row["y"].setText("")

    def _on_profile_changed(self, val: str):
        if self._loading:
            return
        try:
            new_idx = int(val.replace("Config", "").strip())
            if new_idx != self.current_profile_idx:
                self.save_current_profile(silent=True)
                self.load_profile_into_editor(new_idx)
        except Exception:
            pass

    def load_profile_into_editor(self, profile_idx: int):
        self._loading = True
        try:
            self.current_profile_idx = profile_idx
            self.combo_profile.setCurrentText(f"Config {profile_idx}")
            if not self.persistence_mgr:
                return
            cfg = self.persistence_mgr.load_single_profile(profile_idx)
            self.spin_respawn.setValue(int(cfg.get("respawn_delay", 15) or 15))
            stages = cfg.get("stages", [])
            for i, row in enumerate(self.editor_rows):
                if i < len(stages):
                    st = stages[i]
                    row["min"].setText(str(st.get("min_level", "")))
                    row["max"].setText(str(st.get("max_level", "")))
                    m_name = str(st.get("map_name", ""))
                    if m_name and row["map"].findText(m_name) < 0:
                        row["map"].addItem(m_name)
                    row["map"].setCurrentText(m_name)
                    row["x"].setText(str(st.get("x", "")))
                    row["y"].setText(str(st.get("y", "")))
                else:
                    row["min"].setText("")
                    row["max"].setText("")
                    row["map"].setCurrentIndex(0)
                    row["x"].setText("")
                    row["y"].setText("")
        finally:
            self._loading = False

    def save_current_profile(self, silent: bool = False):
        if not self.persistence_mgr:
            return
        idx = self.current_profile_idx
        cfg = self.persistence_mgr.load_single_profile(idx)
        cfg["respawn_delay"] = int(self.spin_respawn.value())

        new_stages = []
        for row in self.editor_rows:
            min_s = row["min"].text().strip()
            max_s = row["max"].text().strip()
            map_s = row["map"].currentText().strip()
            x_s = row["x"].text().strip()
            y_s = row["y"].text().strip()
            if min_s and max_s and map_s and x_s and y_s:
                try:
                    new_stages.append({
                        "min_level": int(min_s),
                        "max_level": int(max_s),
                        "map_name": map_s,
                        "x": int(x_s),
                        "y": int(y_s),
                    })
                except Exception:
                    pass
        cfg["stages"] = new_stages
        self.persistence_mgr.save_single_profile(idx, cfg)

        if not silent and self.on_log:
            self.on_log(
                f"Đã lưu thành công Config {idx} ({len(new_stages)} chặng train) vào autotrain_profiles.json!",
                "SUCCESS",
            )
        if self.on_profile_saved:
            self.on_profile_saved(idx)

    def reload_from_file(self):
        self.load_profile_into_editor(self.current_profile_idx)
        if self.on_log:
            self.on_log(f"Đã tải lại dữ liệu Config {self.current_profile_idx} từ file JSON.", "INFO")
