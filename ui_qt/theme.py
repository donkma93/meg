# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - DARK OPS THEME & QSS STYLESHEET
Phong cách Linear / Vercel Dark Ops sắc nét, tối ưu hiệu năng vẽ Native Qt6 (60fps).
"""

from pathlib import Path
from typing import Dict, Tuple
from PySide6.QtGui import QPalette, QColor

_UI_QT_DIR = Path(__file__).resolve().parent
_CHEVRON_DOWN_URL = (_UI_QT_DIR / "chevron_down.png").as_posix()
_CHEVRON_HOVER_URL = (_UI_QT_DIR / "chevron_down_hover.png").as_posix()


def build_dark_palette() -> QPalette:
    """Ép toàn bộ Qt6 Fusion dùng Dark Palette (tránh popup QComboBox / QMenu bị nền trắng theo Windows Light Mode)."""
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#070b14"))
    pal.setColor(QPalette.WindowText, QColor("#f1f5f9"))
    pal.setColor(QPalette.Base, QColor("#0b1220"))
    pal.setColor(QPalette.AlternateBase, QColor("#0f192c"))
    pal.setColor(QPalette.ToolTipBase, QColor("#0b1220"))
    pal.setColor(QPalette.ToolTipText, QColor("#f1f5f9"))
    pal.setColor(QPalette.Text, QColor("#f1f5f9"))
    pal.setColor(QPalette.Button, QColor("#131c30"))
    pal.setColor(QPalette.ButtonText, QColor("#f1f5f9"))
    pal.setColor(QPalette.BrightText, QColor("#38bdf8"))
    pal.setColor(QPalette.Link, QColor("#38bdf8"))
    pal.setColor(QPalette.Highlight, QColor("#132746"))
    pal.setColor(QPalette.HighlightedText, QColor("#38bdf8"))
    pal.setColor(QPalette.PlaceholderText, QColor("#64748b"))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#475569"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#475569"))
    return pal

CLASS_COLORS: Dict[str, Tuple[str, str]] = {
    "DK": ("#f87171", "#3b1219"),
    "BK": ("#f87171", "#3b1219"),
    "DW": ("#38bdf8", "#082f49"),
    "SM": ("#38bdf8", "#082f49"),
    "ELF": ("#4ade80", "#052e1c"),
    "ME": ("#4ade80", "#052e1c"),
    "MG": ("#c084fc", "#2e1065"),
    "DM": ("#c084fc", "#2e1065"),
    "DL": ("#fbbf24", "#362005"),
    "LE": ("#fbbf24", "#362005"),
    "SUM": ("#f472b6", "#3b0724"),
    "SU": ("#f472b6", "#3b0724"),
    "BS": ("#f472b6", "#3b0724"),
    "RF": ("#fb923c", "#381704"),
    "FM": ("#fb923c", "#381704"),
    "GL": ("#818cf8", "#1e1b4b"),
    "RW": ("#2dd4bf", "#042f2e"),
    "SL": ("#cbd5e1", "#1e293b"),
    "SLA": ("#cbd5e1", "#1e293b"),
    "GC": ("#a3e635", "#1a2e05"),
    "KM": ("#e879f9", "#3b0764"),
    "LM": ("#38bdf8", "#082f49"),
    "IK": ("#fca5a5", "#450a0a"),
}

DARK_OPS_QSS = """
QMainWindow, QDialog {
    background-color: #070b14;
    color: #f1f5f9;
    font-family: "Segoe UI", sans-serif;
    font-size: 12px;
}

QWidget {
    color: #f1f5f9;
    font-family: "Segoe UI", sans-serif;
}

/* Header & Navigation */
QFrame#HeaderBar {
    background-color: #0b1220;
    border-bottom: 1px solid #1a2438;
}

QFrame#NavBar {
    background-color: #0c1424;
    border-bottom: 1px solid #1e293b;
}

QFrame#FooterBar {
    background-color: #080e18;
    border-top: 1px solid #1a2438;
}

QPushButton[navTab="true"] {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton[navTab="true"]:hover {
    background-color: #162035;
    color: #e2e8f0;
}
QPushButton[navTab="true"]:checked, QPushButton[navTab="true"][active="true"] {
    background-color: #122033;
    color: #38bdf8;
    border: 1px solid #38bdf8;
}

/* Metric Chips */
QFrame[metricChip="true"] {
    background-color: #131c30;
    border: 1px solid #243149;
    border-radius: 6px;
}
QFrame[metricChip="true"][tone="ok"] {
    background-color: #052e1c;
    border-color: #14532d;
}
QFrame[metricChip="true"][tone="info"] {
    background-color: #0b1f33;
    border-color: #1e3a5f;
}
QFrame[metricChip="true"][tone="warn"] {
    background-color: #2a1c05;
    border-color: #854d0e;
}
QFrame[metricChip="true"][tone="danger"] {
    background-color: #2a0b10;
    border-color: #7f1d1d;
}

/* Surfaces / Cards / Toolbars */
QFrame[surface="toolbar"] {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 7px;
}
QFrame[surface="utilbar"] {
    background-color: #0b1322;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QFrame[surface="card"] {
    background-color: #0a101d;
    border: 1px solid #1e293b;
    border-radius: 7px;
}
QFrame[surface="stripMirror"] {
    background-color: #131c30;
    border: 1px solid #4c1d95;
    border-radius: 7px;
}
QFrame[surface="stripMoss"] {
    background-color: #0a101d;
    border: 1px solid #14532d;
    border-radius: 7px;
}

/* Action Buttons */
QPushButton {
    background-color: #131c30;
    color: #e2e8f0;
    border: 1px solid #243149;
    border-radius: 5px;
    padding: 4px 10px;
    font-weight: 600;
    font-size: 11px;
}
QPushButton:hover {
    background-color: #1a2540;
    border-color: #38bdf8;
}
QPushButton:pressed {
    background-color: #0f172a;
}
QPushButton:disabled {
    background-color: #111827;
    color: #475569;
    border-color: #1e293b;
}

QPushButton[tone="primary"] {
    background-color: #0c4a6e;
    color: #38bdf8;
    border-color: #0284c7;
}
QPushButton[tone="primary"]:hover {
    background-color: #075985;
    color: #e0f2fe;
}

QPushButton[tone="success"] {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #4ade80;
}
QPushButton[tone="success"]:hover {
    background-color: #15803d;
    border-color: #86efac;
}

QPushButton[tone="danger"] {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #f87171;
}
QPushButton[tone="danger"]:hover {
    background-color: #b91c1c;
    border-color: #fca5a5;
}

QPushButton[tone="purple"] {
    background-color: #2e1065;
    color: #c084fc;
    border-color: #7e22ce;
}
QPushButton[tone="purple"]:hover {
    background-color: #3b0764;
    color: #e9d5ff;
}

QPushButton[tone="fire"] {
    background-color: #450a0a;
    color: #fb7185;
    border-color: #be123c;
}
QPushButton[tone="fire"]:hover {
    background-color: #7f1d1d;
    color: #fecdd3;
}

QPushButton[tone="warn"] {
    background-color: #ea580c;
    color: #ffffff;
    border-color: #f97316;
}
QPushButton[tone="warn"]:hover {
    background-color: #c2410c;
}

QPushButton[tone="ghost"] {
    background-color: transparent;
    color: #94a3b8;
    border-color: #1e293b;
}
QPushButton[tone="ghost"]:hover {
    background-color: #1a2540;
    color: #f1f5f9;
    border-color: #334155;
}

QWidget#CellBox {
    background-color: transparent;
}

QPushButton[rowBtn="true"] {
    padding: 0px 4px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 5px;
    min-height: 26px;
    max-height: 26px;
}

QPushButton[tone="pointOn"] {
    background-color: #0369a1;
    color: #ffffff;
    border: 1px solid #38bdf8;
}
QPushButton[tone="pointOn"]:hover {
    background-color: #0284c7;
    border-color: #7dd3fc;
}
QPushButton[tone="pointOff"] {
    background-color: #162033;
    color: #cbd5e1;
    border: 1px solid #334155;
}
QPushButton[tone="pointOff"]:hover {
    background-color: #1e293b;
    color: #ffffff;
    border-color: #38bdf8;
}
QPushButton[tone="cfgBtn"] {
    background-color: #1e293b;
    color: #f1f5f9;
    border: 1px solid #475569;
}
QPushButton[tone="cfgBtn"]:hover {
    background-color: #29384f;
    color: #ffffff;
    border-color: #38bdf8;
}

QTableWidget QComboBox, QTableWidget QSpinBox, QTableWidget QLineEdit {
    margin: 4px 2px;
}

/* Inputs & Dropdowns */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0a101c;
    color: #f1f5f9;
    border: 1px solid #243149;
    border-radius: 5px;
    padding: 2px 5px;
    selection-background-color: #1d4ed8;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #38bdf8;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 14px;
    background-color: #131c30;
    border: none;
}

QComboBox {
    background-color: #0f172a;
    color: #f1f5f9;
    border: 1px solid #243149;
    border-radius: 5px;
    padding: 2px 16px 2px 6px;
    font-size: 11px;
}
QComboBox:hover {
    border-color: #38bdf8;
    background-color: #162035;
}
QComboBox:on {
    border-color: #38bdf8;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 16px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: url(__CHEVRON_DOWN__);
    width: 10px;
    height: 6px;
    margin-right: 4px;
}
QComboBox::down-arrow:hover {
    image: url(__CHEVRON_HOVER__);
}
QComboBoxPrivateContainer, QListView {
    background-color: #0b1220;
    color: #e2e8f0;
    border: 1px solid #38bdf8;
    outline: 0px;
}
QComboBox QAbstractItemView, QComboBox QListView {
    background-color: #0b1220;
    color: #e2e8f0;
    border: 1px solid #38bdf8;
    selection-background-color: #132746;
    selection-color: #38bdf8;
    outline: 0px;
    padding: 3px;
}
QComboBox QAbstractItemView::item, QComboBox QListView::item {
    background-color: #0b1220;
    color: #e2e8f0;
    padding: 5px 8px;
    min-height: 22px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover, QComboBox QListView::item:hover {
    background-color: #1a2540;
    color: #ffffff;
}
QComboBox QAbstractItemView::item:selected, QComboBox QListView::item:selected {
    background-color: #132746;
    color: #38bdf8;
}
QToolTip {
    background-color: #0b1220;
    color: #f1f5f9;
    border: 1px solid #334155;
    padding: 4px 8px;
    border-radius: 4px;
}

/* Checkboxes */
QCheckBox {
    spacing: 6px;
    color: #e2e8f0;
    font-size: 11px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #475569;
    background-color: #0a101c;
}
QCheckBox::indicator:hover {
    border-color: #38bdf8;
}
QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Tables (High-Performance Native QTableWidget) */
QTableWidget {
    background-color: #0a101d;
    alternate-background-color: #0f192c;
    color: #f1f5f9;
    gridline-color: #152033;
    border: 1px solid #1e293b;
    border-radius: 6px;
    selection-background-color: #132746;
    selection-color: #f8fafc;
    outline: none;
}
QTableWidget::item {
    padding: 2px 6px;
    border: none;
}
QHeaderView::section {
    background-color: #0e172a;
    color: #94a3b8;
    font-weight: 700;
    font-size: 11px;
    padding: 5px 6px;
    border: none;
    border-right: 1px solid #182234;
    border-bottom: 1px solid #1e293b;
}

/* Logs / Textboxes */
QPlainTextEdit, QTextEdit {
    background-color: #0a101c;
    color: #e2e8f0;
    border: 1px solid #1e293b;
    border-radius: 6px;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 11px;
    selection-background-color: #1d4ed8;
}

/* Context Menu */
QMenu {
    background-color: #0b1220;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #132746;
    color: #38bdf8;
}
QMenu::separator {
    height: 1px;
    background: #1e293b;
    margin: 4px 6px;
}

/* Splitter */
QSplitter::handle {
    background-color: #1e293b;
    height: 4px;
}
QSplitter::handle:hover {
    background-color: #38bdf8;
}

/* Slim Modern Scrollbars */
QScrollBar:vertical {
    background: #0a101d;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #243149;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #38bdf8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #0a101d;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #243149;
    min-width: 28px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #38bdf8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
""".replace("__CHEVRON_DOWN__", _CHEVRON_DOWN_URL).replace("__CHEVRON_HOVER__", _CHEVRON_HOVER_URL)
