# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - SYSTEM LOGS VIEW
Nhật ký hệ thống siêu nhẹ với QPlainTextEdit (tự giới hạn 1000 dòng, lọc theo cấp độ & từ khóa).
"""

from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QLineEdit, QPlainTextEdit
)


LEVEL_COLORS = {
    "SUCCESS": "#4ade80",
    "WARNING": "#fbbf24",
    "WARN": "#fbbf24",
    "ERROR": "#f87171",
    "INFO": "#cbd5e1",
}


class LogsTabQt(QWidget):
    """Tab 05 Logs — hiển thị nhật ký hệ thống tốc độ cao."""

    def __init__(self, on_clear: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.on_clear = on_clear
        self._buffer: List[Tuple[str, str, Optional[int], str]] = []
        self._max_lines = 1000
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        tb = QFrame()
        tb.setProperty("surface", "toolbar")
        tb.setFixedHeight(42)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(10, 4, 10, 4)
        tl.setSpacing(8)

        lbl = QLabel("📋 NHẬT KÝ HỆ THỐNG")
        lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px;")
        tl.addWidget(lbl)

        tl.addSpacing(12)
        tl.addWidget(QLabel("Lọc cấp độ:"))
        self.combo_level = QComboBox()
        self.combo_level.addItems(["Tất cả", "INFO", "SUCCESS", "WARNING", "ERROR"])
        self.combo_level.setFixedWidth(110)
        self.combo_level.currentTextChanged.connect(self._rerender)
        tl.addWidget(self.combo_level)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm theo tên nhân vật, slot, từ khóa...")
        self.search_edit.setFixedWidth(260)
        self.search_edit.textChanged.connect(self._rerender)
        tl.addWidget(self.search_edit)

        tl.addStretch(1)

        self.lbl_count = QLabel("0 dòng")
        self.lbl_count.setStyleSheet("color: #64748b; font-size: 11px;")
        tl.addWidget(self.lbl_count)

        btn_clear = QPushButton("🗑 Xóa nhật ký")
        btn_clear.setProperty("tone", "ghost")
        btn_clear.setFixedHeight(28)
        btn_clear.clicked.connect(self.clear_logs)
        tl.addWidget(btn_clear)

        root.addWidget(tb)

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setMaximumBlockCount(self._max_lines)
        root.addWidget(self.text_view, 1)

    def _matches_filter(self, level: str, text: str) -> bool:
        lvl_f = self.combo_level.currentText()
        if lvl_f != "Tất cả":
            norm = "WARNING" if level == "WARN" else level
            if norm != lvl_f:
                return False
        q = self.search_edit.text().strip().lower()
        if q and q not in text.lower():
            return False
        return True

    def _append_formatted(self, ts: str, level: str, slot: Optional[int], text: str):
        prefix = f"[{ts}] "
        if slot is not None:
            prefix += f"[S{slot:02d}] "
        line = f"{prefix}[{level}] {text}"
        cursor = self.text_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LEVEL_COLORS.get(level.upper(), "#cbd5e1")))
        cursor.setCharFormat(fmt)
        if self.text_view.document().characterCount() > 1:
            cursor.insertText("\n" + line)
        else:
            cursor.insertText(line)

    def append_batched_logs(self, logs: List[Tuple[str, str, Optional[int], str]]):
        if not logs:
            return
        sb = self.text_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 10
        appended = False
        for item in logs:
            ts, level, slot, text = item
            self._buffer.append(item)
            if self._matches_filter(level, text):
                self._append_formatted(ts, level, slot, text)
                appended = True
        if len(self._buffer) > self._max_lines:
            self._buffer = self._buffer[-self._max_lines:]
        self.lbl_count.setText(f"{len(self._buffer)} dòng")
        if appended and at_bottom:
            sb.setValue(sb.maximum())

    def _rerender(self):
        self.text_view.clear()
        for ts, level, slot, text in self._buffer:
            if self._matches_filter(level, text):
                self._append_formatted(ts, level, slot, text)
        sb = self.text_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self):
        self._buffer.clear()
        self.text_view.clear()
        self.lbl_count.setText("0 dòng")
        if self.on_clear:
            self.on_clear()
