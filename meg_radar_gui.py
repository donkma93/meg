#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Radar & Entity Scanner GUI (Bản Đồ Radar Sci-Fi)
======================================================
Giao diện Radar trực quan hiển thị quái vật và người chơi xung quanh nhân vật:
- Bản đồ Radar hình tròn (Concentric Distance Rings & Sweep Animation).
- Quái vật: Chấm đỏ (Quái Tinh Anh: Chấm viền vàng phát sáng).
- Người chơi: Chấm xanh Cyan (Sát thủ Quỷ Đỏ PK: Chấm đỏ nhấp nháy báo động).
- NPC: Chấm vàng cam.
- Tâm bản đồ: Nhân vật của bạn kèm tọa độ (X, Y) và Map ID hiện tại.
- Hỗ trợ Ghim trên cùng (Always on Top) & Thanh chỉnh độ mờ (Transparency) làm Overlay.
- Hỗ trợ Lăn chuột (Mouse Wheel) để Phóng to / Thu nhỏ bán kính radar (Zoom In / Out).
- Bảng danh sách chi tiết bên cạnh kèm bộ lọc theo bán kính.
- Cơ chế 100% Zero-Injection: Đọc trực tiếp RAM bằng ReadProcessMemory, siêu an toàn.
"""

import os
import sys
import math
import time
import json
import ctypes
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import psutil
except ImportError:
    print("[ERROR] Cần thư viện psutil: pip install psutil")
    sys.exit(1)

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QRadialGradient, QFont, QPolygonF,
    QPainterPath, QCursor
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QCheckBox, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QToolTip
)

# Nạp MemoryScanner từ file test_entity_radar đã viết
try:
    from test_entity_radar import MemoryScanner, CLASS_NAMES, PK_LEVEL_MAP, MAP_NAMES
except ImportError:
    print("[ERROR] Không tìm thấy module test_entity_radar.py!")
    sys.exit(1)


class RadarScanThread(QThread):
    """Thread quét RAM nền để UI luôn đạt 60 FPS mượt mà."""
    data_ready = pyqtSignal(dict)

    def __init__(self, pid: int, radius: float = 15.0):
        super().__init__()
        self.pid = pid
        self.radius = radius
        self.running = True
        self.scanner = MemoryScanner(pid)

    def set_pid(self, pid: int):
        self.pid = pid
        if self.scanner:
            self.scanner.close()
        self.scanner = MemoryScanner(pid)

    def set_radius(self, radius: float):
        self.radius = radius

    def run(self):
        while self.running:
            if self.scanner and self.scanner.base_addr:
                data = self.scanner.scan_radar(radius=self.radius)
                self.data_ready.emit(data)
            else:
                if self.scanner:
                    self.scanner._open_process()
            time.sleep(0.35)  # Cập nhật mỗi 350ms

    def stop(self):
        self.running = False
        if self.scanner:
            self.scanner.close()


class CircularRadarWidget(QWidget):
    """Widget vẽ bản đồ Radar hình tròn với đồ họa vector chống răng cưa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self.radar_data: Dict[str, Any] = {}
        self.radius_tiles = 15.0
        self.sweep_angle = 0.0

        # Bộ lọc hiển thị
        self.show_monsters = True
        self.show_players = True
        self.show_npcs = True
        self.show_labels = True

        # Timer quét tia radar xoay 360 độ
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._rotate_sweep)
        self.anim_timer.start(30)  # ~33 FPS cho hiệu ứng xoay radar

        # Bật tracking chuột để hiển thị tooltip khi rê vào chấm
        self.setMouseTracking(True)
        self.hovered_entity = None

    def _rotate_sweep(self):
        self.sweep_angle = (self.sweep_angle + 3.0) % 360.0
        self.update()

    def update_data(self, data: Dict[str, Any]):
        self.radar_data = data
        self.update()

    def wheelEvent(self, event):
        """Lăn chuột để phóng to / thu nhỏ bán kính radar (Zoom In / Zoom Out)."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.radius_tiles = max(5.0, self.radius_tiles - 1.0)
        else:
            self.radius_tiles = min(35.0, self.radius_tiles + 1.0)
        if hasattr(self.parent(), "slider_radius"):
            self.parent().slider_radius.setValue(int(self.radius_tiles))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0
        radar_radius = min(width, height) / 2.0 - 20.0

        if radar_radius <= 10:
            return

        # 1. Nền Radar (Gradient tỏa tròn kiểu Sci-Fi Navy Dark)
        grad = QRadialGradient(center_x, center_y, radar_radius)
        grad.setColorAt(0.0, QColor(8, 28, 36, 230))
        grad.setColorAt(0.7, QColor(4, 16, 22, 240))
        grad.setColorAt(1.0, QColor(2, 8, 12, 255))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(0, 180, 216, 180), 2))
        painter.drawEllipse(QPointF(center_x, center_y), radar_radius, radar_radius)

        # 2. Vòng tròn đồng tâm chỉ khoảng cách (Distance Rings)
        step_tile = 5.0
        max_tiles = self.radius_tiles
        scale = radar_radius / max_tiles  # pixels trên mỗi ô bản đồ

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        current_ring = step_tile
        while current_ring <= max_tiles:
            r_px = current_ring * scale
            if r_px < radar_radius:
                painter.setPen(QPen(QColor(0, 180, 216, 60), 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(center_x, center_y), r_px, r_px)

                # Nhãn khoảng cách trên vòng tròn
                painter.setPen(QColor(0, 220, 255, 120))
                painter.drawText(int(center_x + 5), int(center_y - r_px + 12), f"{int(current_ring)} ô")
            current_ring += step_tile

        # 3. Trục tọa độ chữ thập (Crosshair)
        painter.setPen(QPen(QColor(0, 180, 216, 80), 1))
        painter.drawLine(int(center_x - radar_radius), int(center_y), int(center_x + radar_radius), int(center_y))
        painter.drawLine(int(center_x), int(center_y - radar_radius), int(center_x), int(center_y + radar_radius))

        # Nhãn 4 hướng Đông Tây Nam Bắc
        painter.setPen(QColor(0, 220, 255, 180))
        painter.drawText(int(center_x - 4), int(center_y - radar_radius + 15), "B")
        painter.drawText(int(center_x - 4), int(center_y + radar_radius - 5), "N")
        painter.drawText(int(center_x + radar_radius - 15), int(center_y + 4), "Đ")
        painter.drawText(int(center_x - radar_radius + 5), int(center_y + 4), "T")

        # 4. Tia quét Radar xoay 360 độ (Radar Sweep Effect)
        sweep_rad = math.radians(self.sweep_angle)
        sweep_x = center_x + radar_radius * math.cos(sweep_rad)
        sweep_y = center_y + radar_radius * math.sin(sweep_rad)

        sweep_pen = QPen(QColor(0, 255, 200, 160), 2)
        painter.setPen(sweep_pen)
        painter.drawLine(int(center_x), int(center_y), int(sweep_x), int(sweep_y))

        # Quạt mờ phía sau tia quét
        sweep_path = QPainterPath()
        sweep_path.moveTo(center_x, center_y)
        sweep_path.arcTo(
            QRectF(center_x - radar_radius, center_y - radar_radius, radar_radius * 2, radar_radius * 2),
            -self.sweep_angle, 35.0
        )
        sweep_path.closeSubpath()
        painter.setPen(Qt.NoPen)
        sweep_brush = QRadialGradient(center_x, center_y, radar_radius)
        sweep_brush.setColorAt(0.0, QColor(0, 255, 200, 40))
        sweep_brush.setColorAt(1.0, QColor(0, 255, 200, 5))
        painter.setBrush(QBrush(sweep_brush))
        painter.drawPath(sweep_path)

        if not self.radar_data or "player" not in self.radar_data:
            painter.setPen(QColor(255, 255, 255, 120))
            painter.drawText(int(center_x - 70), int(center_y), "Đang chờ dữ liệu game...")
            return

        p = self.radar_data["player"]
        px, py = p["x"], p["y"]

        # 5. Vẽ Quái vật (Chấm Đỏ / Vàng nếu Elite)
        if self.show_monsters:
            for mon in self.radar_data.get("monsters", []):
                dx = mon["x"] - px
                dy = mon["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale

                # Kiểm tra nằm trong vòng tròn radar
                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    if mon["is_elite"]:
                        # Quái Tinh Anh (Chấm to, phát sáng vàng đỏ)
                        painter.setPen(QPen(QColor(255, 215, 0, 220), 2))
                        painter.setBrush(QBrush(QColor(255, 50, 50, 240)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 5.5, 5.5)
                    else:
                        painter.setPen(QPen(QColor(255, 80, 80, 180), 1))
                        painter.setBrush(QBrush(QColor(255, 30, 30, 220)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 3.5, 3.5)

                    if self.show_labels:
                        painter.setFont(QFont("Segoe UI", 7))
                        painter.setPen(QColor(255, 200, 200, 180))
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), mon["name"][:12])

        # 6. Vẽ NPC (Chấm Vàng Cam)
        if self.show_npcs:
            for npc in self.radar_data.get("npcs", []):
                dx = npc["x"] - px
                dy = npc["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale
                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    painter.setPen(QPen(QColor(255, 180, 0, 200), 1))
                    painter.setBrush(QBrush(QColor(255, 215, 0, 230)))
                    painter.drawRect(int(screen_x - 3), int(screen_y - 3), 6, 6)

                    if self.show_labels:
                        painter.setFont(QFont("Segoe UI", 7))
                        painter.setPen(QColor(255, 220, 100, 200))
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), npc["name"][:12])

        # 7. Vẽ Người chơi khác (Chấm Xanh Cyan / Đỏ nhấp nháy nếu PK)
        if self.show_players:
            for pl in self.radar_data.get("players", []):
                dx = pl["x"] - px
                dy = pl["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale

                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    if pl["is_pk"]:
                        # SÁT THỦ QUỶ ĐỎ PK (Nhấp nháy đỏ rực)
                        flash_color = QColor(255, 0, 0, 255) if int(time.time() * 4) % 2 == 0 else QColor(255, 120, 0, 255)
                        painter.setPen(QPen(QColor(255, 255, 255), 2))
                        painter.setBrush(QBrush(flash_color))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 6.5, 6.5)
                    elif pl["is_gm"]:
                        # ADMIN / GM (Chấm Tím Vàng nổi bật)
                        painter.setPen(QPen(QColor(255, 215, 0), 2))
                        painter.setBrush(QBrush(QColor(180, 0, 255, 240)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 6.0, 6.0)
                    else:
                        # Người chơi bình thường (Chấm Xanh Lơ / Cyan)
                        painter.setPen(QPen(QColor(0, 255, 255, 200), 1))
                        painter.setBrush(QBrush(QColor(0, 180, 255, 230)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 4.5, 4.5)

                    if self.show_labels:
                        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
                        label_col = QColor(255, 80, 80) if pl["is_pk"] else QColor(100, 240, 255)
                        painter.setPen(label_col)
                        g_tag = f" [{pl['guild_name']}]" if pl.get("guild_name") else ""
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), f"{pl['name'][:12]}{g_tag}")

        # 8. Vẽ Nhân vật của bản thân ở chính giữa Radar (Tâm trắng xanh hào quang)
        painter.setPen(QPen(QColor(0, 255, 120, 100), 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), 8.0, 8.0)

        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(0, 255, 150, 255)))
        painter.drawEllipse(QPointF(center_x, center_y), 4.5, 4.5)

        # Nhãn tọa độ của bạn
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(int(center_x - 30), int(center_y + 22), f"({px}, {py})")


class RadarMainWindow(QMainWindow):
    """Cửa sổ chính của Tool Radar Sci-Fi."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEGAMU Radar & Entity Scanner - [Live Radar HUD]")
        self.resize(960, 620)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b1116;
            }
            QWidget {
                color: #c9d1d9;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QFrame#panelFrame {
                background-color: #121d24;
                border: 1px solid #1f333f;
                border-radius: 8px;
            }
            QLabel {
                font-size: 12px;
            }
            QLabel#headerLabel {
                font-size: 15px;
                font-weight: bold;
                color: #00e5ff;
            }
            QLabel#alertBanner {
                background-color: #3b1114;
                color: #ff4d4f;
                border: 1px solid #ff4d4f;
                border-radius: 4px;
                padding: 6px;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #0d161c;
                border: 1px solid #1a2c38;
                gridline-color: #1a2c38;
                border-radius: 4px;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #007799;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #15242e;
                color: #00e5ff;
                padding: 4px;
                border: 1px solid #1f333f;
                font-weight: bold;
            }
            QComboBox, QSlider {
                background-color: #162631;
                border: 1px solid #244154;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #0088a8;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #00a4cc;
            }
            QPushButton:pressed {
                background-color: #006b85;
            }
            QCheckBox {
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
        """)

        self.scan_thread: Optional[RadarScanThread] = None
        self._init_ui()
        self._refresh_clients()

    def _init_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)

        # ----------------- CỘT TRÁI: BẢN ĐỒ RADAR -----------------
        radar_container = QFrame()
        radar_container.setObjectName("panelFrame")
        radar_layout = QVBoxLayout(radar_container)

        radar_header = QHBoxLayout()
        self.lbl_map_info = QLabel("BẢN ĐỒ: Đang tải...")
        self.lbl_map_info.setObjectName("headerLabel")
        radar_header.addWidget(self.lbl_map_info)
        radar_header.addStretch()

        self.btn_refresh = QPushButton("🔄 Quét lại Client")
        self.btn_refresh.clicked.connect(self._refresh_clients)
        radar_header.addWidget(self.btn_refresh)
        radar_layout.addLayout(radar_header)

        # Canvas Radar
        self.radar_widget = CircularRadarWidget(self)
        radar_layout.addWidget(self.radar_widget, stretch=1)

        # Cảnh báo an toàn (PK / GM)
        self.lbl_alert = QLabel("✔ Khu vực an toàn - Không có Sát nhân PK hoặc GM")
        self.lbl_alert.setObjectName("alertBanner")
        self.lbl_alert.setStyleSheet("background-color: #10291f; color: #00e676; border: 1px solid #00e676;")
        radar_layout.addWidget(self.lbl_alert)

        splitter.addWidget(radar_container)

        # ----------------- CỘT PHẢI: BẢNG ĐIỀU KHIỂN & DANH SÁCH -----------------
        side_panel = QFrame()
        side_panel.setObjectName("panelFrame")
        side_panel.setMinimumWidth(440)
        side_layout = QVBoxLayout(side_panel)

        # 1. Chọn Client Game
        client_box = QHBoxLayout()
        client_box.addWidget(QLabel("Client Game:"))
        self.cb_clients = QComboBox()
        self.cb_clients.currentIndexChanged.connect(self._on_client_changed)
        client_box.addWidget(self.cb_clients, stretch=1)
        side_layout.addLayout(client_box)

        # 2. Điều khiển Radar (Bán kính & Overlay)
        ctrl_grid = QHBoxLayout()
        self.lbl_radius_val = QLabel("Bán kính: 15 ô")
        ctrl_grid.addWidget(self.lbl_radius_val)

        self.slider_radius = QSlider(Qt.Horizontal)
        self.slider_radius.setRange(5, 30)
        self.slider_radius.setValue(15)
        self.slider_radius.valueChanged.connect(self._on_radius_changed)
        ctrl_grid.addWidget(self.slider_radius)
        side_layout.addLayout(ctrl_grid)

        # Checkboxes (Always on Top & Mờ & Lọc)
        chk_layout1 = QHBoxLayout()
        self.chk_ontop = QCheckBox("Ghim trên cùng (Overlay)")
        self.chk_ontop.toggled.connect(self._on_ontop_toggled)
        chk_layout1.addWidget(self.chk_ontop)

        chk_layout1.addWidget(QLabel("Độ mờ:"))
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(40, 100)
        self.slider_opacity.setValue(95)
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        chk_layout1.addWidget(self.slider_opacity)
        side_layout.addLayout(chk_layout1)

        # Bộ lọc đối tượng
        filter_layout = QHBoxLayout()
        self.chk_mon = QCheckBox("Quái vật")
        self.chk_mon.setChecked(True)
        self.chk_mon.toggled.connect(lambda v: setattr(self.radar_widget, "show_monsters", v))
        filter_layout.addWidget(self.chk_mon)

        self.chk_pl = QCheckBox("Người chơi")
        self.chk_pl.setChecked(True)
        self.chk_pl.toggled.connect(lambda v: setattr(self.radar_widget, "show_players", v))
        filter_layout.addWidget(self.chk_pl)

        self.chk_npc = QCheckBox("NPC")
        self.chk_npc.setChecked(True)
        self.chk_npc.toggled.connect(lambda v: setattr(self.radar_widget, "show_npcs", v))
        filter_layout.addWidget(self.chk_npc)

        self.chk_lbl = QCheckBox("Tên nhãn")
        self.chk_lbl.setChecked(True)
        self.chk_lbl.toggled.connect(lambda v: setattr(self.radar_widget, "show_labels", v))
        filter_layout.addWidget(self.chk_lbl)
        side_layout.addLayout(filter_layout)

        side_layout.addSpacing(6)

        # 3. Bảng Quái vật
        self.lbl_table_mon = QLabel("👾 Danh sách Quái vật trong bán kính (0 con):")
        self.lbl_table_mon.setStyleSheet("font-weight: bold; color: #ffb74d;")
        side_layout.addWidget(self.lbl_table_mon)

        self.table_monsters = QTableWidget()
        self.table_monsters.setColumnCount(4)
        self.table_monsters.setHorizontalHeaderLabels(["Tên Quái vật", "Cấp", "Tọa độ", "Cách (ô)"])
        self.table_monsters.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_monsters.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_monsters.setFixedHeight(170)
        side_layout.addWidget(self.table_monsters)

        # 4. Bảng Người chơi
        self.lbl_table_pl = QLabel("👤 Danh sách Người chơi xung quanh (0 người):")
        self.lbl_table_pl.setStyleSheet("font-weight: bold; color: #4fc3f7;")
        side_layout.addWidget(self.lbl_table_pl)

        self.table_players = QTableWidget()
        self.table_players.setColumnCount(6)
        self.table_players.setHorizontalHeaderLabels(["Tên Người chơi", "Bang hội (Guild)", "Class", "Tọa độ", "Cách (ô)", "Trạng thái"])
        self.table_players.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_players.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        side_layout.addWidget(self.table_players, stretch=1)

        splitter.addWidget(side_panel)
        main_layout.addWidget(splitter)

    def _refresh_clients(self):
        """Quét và nạp danh sách các cửa sổ MEGAMU đang chạy."""
        self.cb_clients.blockSignals(True)
        self.cb_clients.clear()

        pids = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = (p.info.get('name') or '').lower()
                if name in ('megamu.exe', 'megamu'):
                    pids.append(p.info['pid'])
            except Exception:
                pass

        if not pids:
            self.cb_clients.addItem("Không tìm thấy MEGAMU.exe", 0)
            self.lbl_map_info.setText("CHƯA MỞ GAME MEGAMU")
        else:
            for pid in pids:
                scanner = MemoryScanner(pid)
                desc = f"PID {pid}"
                if scanner.base_addr:
                    data = scanner.scan_radar(radius=1.0)
                    if "player" in data and data["player"].get("name"):
                        pl = data["player"]
                        desc = f"{pl['name']} ({pl['class']}) - PID {pid}"
                scanner.close()
                self.cb_clients.addItem(desc, pid)

        self.cb_clients.blockSignals(False)

        if pids:
            self._start_scanning(pids[0])

    def _on_client_changed(self, index: int):
        pid = self.cb_clients.itemData(index)
        if pid and pid > 0:
            self._start_scanning(pid)

    def _start_scanning(self, pid: int):
        if self.scan_thread:
            self.scan_thread.stop()
            self.scan_thread.wait()

        self.scan_thread = RadarScanThread(pid, radius=self.slider_radius.value())
        self.scan_thread.data_ready.connect(self._on_data_received)
        self.scan_thread.start()

    def _on_radius_changed(self, val: int):
        self.lbl_radius_val.setText(f"Bán kính: {val} ô")
        self.radar_widget.radius_tiles = float(val)
        if self.scan_thread:
            self.scan_thread.set_radius(float(val))

    def _on_ontop_toggled(self, checked: bool):
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _on_opacity_changed(self, val: int):
        self.setWindowOpacity(val / 100.0)

    def _on_data_received(self, data: Dict[str, Any]):
        if "error" in data:
            self.lbl_map_info.setText(f"LỖI: {data['error']}")
            return

        p = data["player"]
        m = data["map"]
        monsters = data["monsters"]
        players = data["players"]

        # Cập nhật Header
        self.lbl_map_info.setText(f"📍 {m['name']} (ID {m['id']}) | {p['name']} ({p['class']} Lv {p['level']}) - ({p['x']}, {p['y']})")

        # Cập nhật Radar Canvas
        self.radar_widget.update_data(data)

        # Cập nhật Bảng Quái vật
        self.lbl_table_mon.setText(f"👾 Quái vật trong bán kính ({len(monsters)} con):")
        self.table_monsters.setRowCount(len(monsters))
        for row, mon in enumerate(monsters):
            elite_tag = " [TINH ANH]" if mon["is_elite"] else ""
            self.table_monsters.setItem(row, 0, QTableWidgetItem(mon["name"] + elite_tag))
            self.table_monsters.setItem(row, 1, QTableWidgetItem(str(mon["level"])))
            self.table_monsters.setItem(row, 2, QTableWidgetItem(f"({mon['x']}, {mon['y']})"))
            self.table_monsters.setItem(row, 3, QTableWidgetItem(f"{mon['distance']} ô"))

        # Cập nhật Bảng Người chơi & Báo động PK / GM
        self.lbl_table_pl.setText(f"👤 Người chơi xung quanh ({len(players)} người):")
        self.table_players.setRowCount(len(players))

        has_pk = False
        has_gm = False
        for row, pl in enumerate(players):
            self.table_players.setItem(row, 0, QTableWidgetItem(pl["name"]))

            # Cột 1: Thông tin Guild
            guild_text = "-"
            if pl.get("guild_name"):
                role_tag = f" [{pl['guild_role']}]" if pl.get("guild_role") else ""
                union_tag = f" (LM: {pl['union_name']})" if pl.get("union_name") else ""
                guild_text = f"{pl['guild_name']}{role_tag}{union_tag}"
            item_guild = QTableWidgetItem(guild_text)
            if pl.get("guild_role") == "Chủ Bang":
                item_guild.setForeground(QColor(255, 215, 0)) # Vàng hoàng kim cho Chủ Bang
            elif pl.get("guild_role") == "Phó Bang":
                item_guild.setForeground(QColor(0, 230, 255))
            self.table_players.setItem(row, 1, item_guild)

            self.table_players.setItem(row, 2, QTableWidgetItem(pl["class"]))
            self.table_players.setItem(row, 3, QTableWidgetItem(f"({pl['x']}, {pl['y']})"))
            self.table_players.setItem(row, 4, QTableWidgetItem(f"{pl['distance']} ô"))

            status_text = "Bình thường"
            if pl["is_pk"]:
                status_text = "⚠️ SÁT THỦ QUỶ ĐỎ"
                has_pk = True
            elif pl["is_gm"]:
                status_text = "🚨 ADMIN / GM"
                has_gm = True
            elif pl.get("guild_rel") == 2:
                status_text = "⚔️ GUILD ĐỐI ĐỊCH"
            elif pl["store_name"]:
                status_text = f"Shop: {pl['store_name'][:10]}"

            item_status = QTableWidgetItem(status_text)
            if pl["is_pk"]:
                item_status.setForeground(QColor(255, 77, 79))
            elif pl["is_gm"]:
                item_status.setForeground(QColor(255, 215, 0))
            elif pl.get("guild_rel") == 2:
                item_status.setForeground(QColor(255, 69, 0))
            self.table_players.setItem(row, 5, item_status)

        # Cập nhật Banner cảnh báo
        if has_pk:
            self.lbl_alert.setText("🚨 CẢNH BÁO NGUY HIỂM: CÓ SÁT THỦ QUỶ ĐỎ PK ÁP SÁT BẠN!")
            self.lbl_alert.setStyleSheet("background-color: #5c1418; color: #ff4d4f; border: 1px solid #ff4d4f;")
        elif has_gm:
            self.lbl_alert.setText("🚨 CẢNH BÁO BẢO MẬT: PHÁT HIỆN GAME MASTER (ADMIN) ĐỨNG GẦN!")
            self.lbl_alert.setStyleSheet("background-color: #4a3800; color: #ffd666; border: 1px solid #ffd666;")
        else:
            self.lbl_alert.setText("✔ Khu vực an toàn - Không có Sát nhân PK hoặc GM")
            self.lbl_alert.setStyleSheet("background-color: #10291f; color: #00e676; border: 1px solid #00e676;")

    def closeEvent(self, event):
        if self.scan_thread:
            self.scan_thread.stop()
            self.scan_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = RadarMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
