#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Radar & Entity Scanner GUI (Bản Đồ Radar Sci-Fi + Sóng Dò Ngoài Tầm Mắt)
=============================================================================
Giao diện Radar trực quan hiển thị quái vật, người chơi và vật phẩm xung quanh:
- TÍCH HỢP QUÉT NGOÀI TẦM MẮT CHO TẤT CẢ CÁC CLASS (ELF, DK, DW, SUMMONER, SLAYER...):
  1. BỘ NHỚ THÁM THÍNH (PERSISTENT SCOUT MEMORY):
     * Ghi nhớ mọi quái vật, bãi quái, elite mob và vật phẩm rơi khi nhân vật di chuyển qua.
     * Khi nhân vật (kể cả ELF) đi xa (ngoài tầm mắt 3D 15 ô), Radar VẪN HIỂN THỊ quái và vật phẩm
       ở cự ly 30 - 100+ ô với khoảng cách thực tế, không bị biến mất!
  2. BÃI QUÁI BẢN ĐỒ MẶC ĐỊNH (MAP SPOTS CATALOG):
     * Tự động hiển thị trước vị trí các bãi quái nổi tiếng của map (Dungeon 1-3, Devias, Lorencia,
       Noria, Lost Tower, Atlans, Tarkan, Aida, Ferea...) trên Radar bằng biểu tượng 🎯 Spot.
  3. TIẾP SÓNG SÓNG DÒ LIÊN CLIENT (CROSS-CLIENT SLAYER RELAY):
     * Nếu có Slayer chạy cùng máy, ELF tự động nhận tiếp sóng Slayer Detection toàn map!
  4. SÓNG DÒ SLAYER TRỰC TIẾP (NẾU NHÂN VẬT LÀ SLAYER):
     * Đọc MinimapManager.PinList, kích hoạt phím tắt chiêu Detection nền bằng Win32 PostMessage.
  5. QUÉT VẬT PHẨM RƠI TRÊN ĐẤT (GROUND ITEMS):
     * Phát hiện Ngọc (Bless, Soul, Chaos...), Đồ Exl, Đồ Thần, Zen rơi ngoài tầm nhìn.
- Bản đồ Radar hình tròn Sci-Fi (Concentric Distance Rings & Sweep Animation).
- Mở rộng bán kính radar lên tới 100+ ô.
- 4 Tabs danh sách: 👾 Quái vật, 🎯 Bãi quái Map, 💎 Vật phẩm rơi, 👤 Người chơi & Cổng.
- Cơ chế 100% Zero-Injection: Đọc trực tiếp RAM bằng ReadProcessMemory, siêu an toàn.
"""

import os
import sys
import math
import time
import json
import ctypes
import threading
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
    QPainterPath, QCursor, QPixmap, QIcon
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QCheckBox, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QToolTip,
    QTabWidget, QMessageBox
)

# Nạp MemoryScanner từ file test_entity_radar đã viết
try:
    from test_entity_radar import MemoryScanner, CLASS_NAMES, PK_LEVEL_MAP, MAP_NAMES, MAP_SPOTS, get_resource_path
except ImportError:
    print("[ERROR] Không tìm thấy module test_entity_radar.py!")
    sys.exit(1)

try:
    from meg_navigator import WindowHelper, ensure_desktop_attached, MegNavigator
except ImportError:
    WindowHelper = None
    MegNavigator = None
    def ensure_desktop_attached(): pass


def cast_slayer_detection_win32(pid: int, slot: int = 0) -> bool:
    """
    Gửi phím tắt kích hoạt kỹ năng Slayer Detection tới cửa sổ MEGAMU nền.
    Cơ chế gửi Win32 PostMessage không chiếm tiêu điểm, không giật màn hình.
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = None
        if WindowHelper:
            try:
                ensure_desktop_attached()
                for p, h, title, w, h_sz in WindowHelper.get_unity_windows():
                    if p == pid:
                        hwnd = h
                        break
            except Exception:
                pass

        if not hwnd:
            import win32gui, win32process
            def enum_cb(h, l):
                if win32gui.IsWindowVisible(h):
                    _, proc_pid = win32process.GetWindowThreadProcessId(h)
                    if proc_pid == pid:
                        l.append(h)
                return True
            hwnds = []
            win32gui.EnumWindows(enum_cb, hwnds)
            if hwnds:
                hwnd = hwnds[0]

        if not hwnd:
            return False

        vk_key = (0x30 + slot) if (1 <= slot <= 9) else 0x33
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        WM_RBUTTONDOWN = 0x0204
        WM_RBUTTONUP = 0x0205
        WM_MOUSEMOVE = 0x0200

        user32.PostMessageW(hwnd, WM_KEYDOWN, vk_key, 0)
        time.sleep(0.04)
        user32.PostMessageW(hwnd, WM_KEYUP, vk_key, 0)
        time.sleep(0.08)

        lparam = ((225 & 0xFFFF) << 16) | (310 & 0xFFFF)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        user32.PostMessageW(hwnd, WM_RBUTTONDOWN, 2, lparam)
        time.sleep(0.06)
        user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam)
        return True
    except Exception:
        return False


class RadarScanThread(QThread):
    """Thread quét RAM nền để UI luôn đạt 60 FPS mượt mà."""
    data_ready = pyqtSignal(dict)

    def __init__(self, pid: int, radius: float = 30.0):
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

    def clear_cache(self):
        if self.scanner:
            self.scanner.clear_scout_cache()

    def run(self):
        while self.running:
            if self.scanner and self.scanner.base_addr:
                data = self.scanner.scan_radar(radius=self.radius)
                self.data_ready.emit(data)
            else:
                if self.scanner:
                    self.scanner._open_process()
            time.sleep(0.08)  # Quét siêu tốc 12.5 Hz (mượt mà, không giật lag)

    def stop(self):
        self.running = False
        if self.scanner:
            self.scanner.close()


class CircularRadarWidget(QWidget):
    """Widget vẽ bản đồ Radar hình tròn tối ưu hóa 60 FPS, không giật lag."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(440, 440)
        self.radar_data: Dict[str, Any] = {}
        self.radius_tiles = 30.0
        self.sweep_angle = 0.0
        self.sonar_wave_radius = 0.0

        # Bộ lọc hiển thị
        self.show_monsters = True
        self.show_scout_memory = True
        self.show_map_spots = True
        self.show_players = True
        self.show_npcs = True
        self.show_ground_items = True
        self.show_slayer_sonar = True
        self.show_gates = True
        self.show_labels = True

        # Cache tĩnh để không vẽ lại nền và vòng tròn mỗi frame
        self._bg_cache: Optional[QPixmap] = None
        self._tooltip_active = False

        # Pre-allocate fonts và pens để tránh rò rỉ bộ nhớ & giật lag Garbage Collector
        self.font_mini = QFont("Segoe UI", 7)
        self.font_mini_bold = QFont("Segoe UI", 7, QFont.Bold)
        self.font_badge = QFont("Segoe UI", 8, QFont.Bold)
        self.font_coords = QFont("Segoe UI", 8, QFont.Bold)

        # Timer quét tia radar chuẩn 60 FPS chính xác cao (PreciseTimer)
        self.anim_timer = QTimer(self)
        self.anim_timer.setTimerType(Qt.PreciseTimer)
        self.anim_timer.timeout.connect(self._on_animation_tick)
        self.last_anim_time = time.perf_counter()
        self.anim_timer.start(16)  # ~60 FPS mượt mà

        # Bật tracking chuột để hiển thị tooltip khi rê vào chấm
        self.setMouseTracking(True)

    def _on_animation_tick(self):
        now = time.perf_counter()
        dt = now - self.last_anim_time
        self.last_anim_time = now
        # Quay mượt mà theo delta time (1 vòng mỗi 4 giây)
        self.sweep_angle = (self.sweep_angle + dt * 90.0) % 360.0
        self.sonar_wave_radius = (self.sonar_wave_radius + dt * 40.0) % 100.0
        self.update()

    def update_data(self, data: Dict[str, Any]):
        self.radar_data = data
        self.update()

    def resizeEvent(self, event):
        self._bg_cache = None
        super().resizeEvent(event)

    def wheelEvent(self, event):
        """Lăn chuột để phóng to / thu nhỏ bán kính radar (Zoom In / Out 5..100 ô)."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.radius_tiles = max(5.0, self.radius_tiles - 2.0)
        else:
            self.radius_tiles = min(100.0, self.radius_tiles + 2.0)
        self._bg_cache = None
        if hasattr(self.parent(), "slider_radius"):
            self.parent().slider_radius.setValue(int(self.radius_tiles))
        self.update()

    def leaveEvent(self, event):
        if self._tooltip_active:
            self._tooltip_active = False
            QToolTip.hideText()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Hiển thị Tooltip HUD khi rê chuột vào các thực thể trên bản đồ."""
        if not self.radar_data or "player" not in self.radar_data:
            return

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0
        radar_radius = min(width, height) / 2.0 - 20.0
        scale = radar_radius / max(1.0, self.radius_tiles)

        p = self.radar_data["player"]
        px, py = p["x"], p["y"]
        mx, my = event.x(), event.y()

        found = None

        # Kiểm tra Bãi Quái Mặc Định Của Map
        if self.show_map_spots:
            for sp in self.radar_data.get("map_spots", []):
                sx = center_x + (sp["x"] - px) * scale
                sy = center_y - (sp["y"] - py) * scale
                if math.hypot(mx - sx, my - sy) <= 9.0:
                    tier_str = sp.get("tier_label", "🆓 Miễn Phí")
                    req_str = sp.get("req", "Tự do")
                    status_note = sp.get("status_note", "")
                    found = f"🎯 <b>[BÃI QUÁI BẢN ĐỒ]</b><br>" \
                            f"Tên: <b>{sp['name']}</b><br>" \
                            f"Phân cấp bãi: <b>{tier_str}</b> ({req_str})<br>" \
                            f"Điều kiện ra bãi: {status_note}<br>" \
                            f"Tọa độ: ({sp['x']}, {sp['y']})<br>" \
                            f"Cách bạn: {sp['distance']} ô"
                    break

        # Kiểm tra Vật phẩm rơi
        if not found and self.show_ground_items:
            for it in self.radar_data.get("ground_items", []):
                if it.get("is_scout") and not self.show_scout_memory:
                    continue
                sx = center_x + (it["x"] - px) * scale
                sy = center_y - (it["y"] - py) * scale
                if math.hypot(mx - sx, my - sy) <= 9.0:
                    scout_tag = " [Ghi nhớ ngoài tầm]" if it.get("is_scout") else ""
                    found = f"💎 <b>{it['name']}</b> ({it['category']}){scout_tag}<br>Cấp: +{it['level']} | Tọa độ: ({it['x']}, {it['y']})<br>Cách bạn: {it['distance']} ô"
                    break

        # Kiểm tra Quái vật & NPC
        if not found and (self.show_monsters or self.show_npcs):
            for mon in self.radar_data.get("monsters", []):
                is_npc = mon.get("is_npc", False)
                if is_npc and not self.show_npcs:
                    continue
                if not is_npc and not self.show_monsters:
                    continue
                if mon.get("is_scout") and not self.show_scout_memory:
                    continue
                if mon.get("is_sonar") and not mon.get("is_scout") and not self.show_slayer_sonar:
                    continue

                sx = center_x + (mon["x"] - px) * scale
                sy = center_y - (mon["y"] - py) * scale
                if math.hypot(mx - sx, my - sy) <= 9.0:
                    cat = mon.get("category", "👾 Quái Thường")
                    if is_npc:
                        found = f"🧙 <b>[NPC BẢN ĐỒ]</b><br>Tên: <b>{mon['name']}</b><br>Phân loại: <font color='#00e5ff'><b>{cat}</b></font><br>Tọa độ: ({mon['x']}, {mon['y']})<br>Cách bạn: {mon['distance']} ô"
                    elif mon.get("is_boss"):
                        found = f"👑 <b>[BOSS THẾ GIỚI]</b><br>Tên: <font color='#ffd700'><b>{mon['name']}</b></font><br>Phân loại: <b>{cat}</b> | Lv: {mon['level']}<br>Tọa độ: ({mon['x']}, {mon['y']})<br>Cách bạn: {mon['distance']} ô"
                    else:
                        if mon.get("is_scout"):
                            tag = "📡 <b>[THÁM THÍNH - NGOÀI TẦM MẮT]</b><br>"
                        elif mon.get("is_sonar"):
                            tag = "🦇 <b>[SÓNG DÒ SLAYER - NGOÀI TẦM MẮT]</b><br>"
                        else:
                            tag = "👁️ <b>[TRONG TẦM NHÌN 3D]</b><br>"
                        elite = " [TINH ANH]" if mon.get("is_elite") else ""
                        found = f"{tag}👾 <b>{mon['name']}</b>{elite}<br>Phân loại: <b>{cat}</b> | Lv: {mon['level']}<br>Tọa độ: ({mon['x']}, {mon['y']})<br>Cách bạn: {mon['distance']} ô"
                    break

        # Kiểm tra Người chơi
        if not found and self.show_players:
            for pl in self.radar_data.get("players", []):
                sx = center_x + (pl["x"] - px) * scale
                sy = center_y - (pl["y"] - py) * scale
                if math.hypot(mx - sx, my - sy) <= 9.0:
                    pk_str = " ⚠️ [SÁT NHÂN PK]" if pl.get("is_pk") else ""
                    sonar_tag = "🦇 [Sóng Dò Ngoài Tầm Mắt]<br>" if pl.get("is_sonar") else ""
                    g_info = f"Guild: {pl['guild_name']}<br>" if pl.get("guild_name") else ""
                    found = f"{sonar_tag}👤 <b>{pl['name']}</b> ({pl['class']}){pk_str}<br>{g_info}Tọa độ: ({pl['x']}, {pl['y']}) | Cách: {pl['distance']} ô"
                    break

        # Kiểm tra Cổng Map
        if not found and self.show_gates:
            for g in self.radar_data.get("gates", []):
                sx = center_x + (g["x"] - px) * scale
                sy = center_y - (g["y"] - py) * scale
                if math.hypot(mx - sx, my - sy) <= 9.0:
                    found = f"🚪 <b>{g['name']}</b><br>Tọa độ: ({g['x']}, {g['y']}) | Cách: {g['distance']} ô"
                    break

        # Kiểm tra Bản thân Người chơi (Player Center)
        if not found and math.hypot(mx - center_x, my - center_y) <= 12.0:
            vip_tag = p.get("vip_tag", "Free")
            vip_desc = p.get("vip_desc", "Tài khoản bình thường")
            acc_lvl = p.get("account_level", 0)
            found = f"👑 <b>[NHÂN VẬT CỦA BẠN]</b><br>" \
                    f"Tên: <b>{p['name']}</b> ({p['class']} Lv {p['level']})<br>" \
                    f"Phân cấp tài khoản: <b>{vip_tag}</b> (Level {acc_lvl})<br>" \
                    f"Quyền lợi ra bãi: {vip_desc}<br>" \
                    f"Tọa độ hiện tại: ({px}, {py})"

        if found:
            self._tooltip_active = True
            QToolTip.showText(self.mapToGlobal(event.pos()), found, self)
        elif self._tooltip_active:
            self._tooltip_active = False
            QToolTip.hideText()

    def _render_bg_cache(self, width: int, height: int, center_x: float, center_y: float, radar_radius: float):
        """Vẽ trước nền radar tĩnh và các vòng tròn vào QPixmap để đạt 60 FPS mượt mà."""
        pix = QPixmap(width, height)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        # 1. Nền Radar (Gradient tỏa tròn Sci-Fi Dark)
        grad = QRadialGradient(center_x, center_y, radar_radius)
        grad.setColorAt(0.0, QColor(6, 24, 32, 235))
        grad.setColorAt(0.7, QColor(4, 15, 20, 245))
        grad.setColorAt(1.0, QColor(2, 6, 10, 255))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(0, 180, 216, 200), 2))
        p.drawEllipse(QPointF(center_x, center_y), radar_radius, radar_radius)

        # 2. Vòng tròn đồng tâm khoảng cách
        max_tiles = self.radius_tiles
        scale = radar_radius / max_tiles

        if max_tiles <= 20:
            step_tile = 5.0
        elif max_tiles <= 50:
            step_tile = 10.0
        else:
            step_tile = 20.0

        p.setFont(self.font_badge)
        current_ring = step_tile
        while current_ring <= max_tiles:
            r_px = current_ring * scale
            if r_px < radar_radius:
                p.setPen(QPen(QColor(0, 180, 216, 60), 1, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(center_x, center_y), r_px, r_px)

                p.setPen(QColor(0, 220, 255, 120))
                p.drawText(int(center_x + 5), int(center_y - r_px + 12), f"{int(current_ring)} ô")
            current_ring += step_tile

        # 3. Trục tọa độ chữ thập & Nhãn 4 hướng
        p.setPen(QPen(QColor(0, 180, 216, 80), 1))
        p.drawLine(int(center_x - radar_radius), int(center_y), int(center_x + radar_radius), int(center_y))
        p.drawLine(int(center_x), int(center_y - radar_radius), int(center_x), int(center_y + radar_radius))

        p.setPen(QColor(0, 220, 255, 180))
        p.drawText(int(center_x - 4), int(center_y - radar_radius + 15), "B")
        p.drawText(int(center_x - 4), int(center_y + radar_radius - 5), "N")
        p.drawText(int(center_x + radar_radius - 15), int(center_y + 4), "Đ")
        p.drawText(int(center_x - radar_radius + 5), int(center_y + 4), "T")

        p.end()
        self._bg_cache = pix

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

        # 1. Vẽ nền tĩnh từ QPixmap Cache (Cực nhanh, < 0.1ms)
        if self._bg_cache is None or self._bg_cache.size() != self.size():
            self._render_bg_cache(width, height, center_x, center_y, radar_radius)
        if self._bg_cache:
            painter.drawPixmap(0, 0, self._bg_cache)

        scale = radar_radius / self.radius_tiles

        # 2. Hiệu ứng SÓNG SIÊU ÂM (Sonar Ripple Waves)
        slayer_info = self.radar_data.get("slayer_sonar", {})
        sonar_active = slayer_info.get("active", False)

        if sonar_active or self.show_slayer_sonar:
            wave_px = (self.sonar_wave_radius / 100.0) * radar_radius
            if wave_px > 5:
                alpha = int(max(0, 180 * (1.0 - (wave_px / radar_radius))))
                sonar_pen = QPen(QColor(180, 0, 255, alpha), 2)
                painter.setPen(sonar_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(center_x, center_y), wave_px, wave_px)

                wave_px2 = ((self.sonar_wave_radius + 50.0) % 100.0 / 100.0) * radar_radius
                alpha2 = int(max(0, 130 * (1.0 - (wave_px2 / radar_radius))))
                painter.setPen(QPen(QColor(0, 255, 200, alpha2), 1.5))
                painter.drawEllipse(QPointF(center_x, center_y), wave_px2, wave_px2)

        # 3. Tia quét Radar xoay 360 độ
        sweep_rad = math.radians(self.sweep_angle)
        sweep_x = center_x + radar_radius * math.cos(sweep_rad)
        sweep_y = center_y + radar_radius * math.sin(sweep_rad)

        sweep_pen = QPen(QColor(0, 255, 200, 160), 2)
        painter.setPen(sweep_pen)
        painter.drawLine(int(center_x), int(center_y), int(sweep_x), int(sweep_y))

        sweep_path = QPainterPath()
        sweep_path.moveTo(center_x, center_y)
        sweep_path.arcTo(
            QRectF(center_x - radar_radius, center_y - radar_radius, radar_radius * 2, radar_radius * 2),
            -self.sweep_angle, 35.0
        )
        sweep_path.closeSubpath()
        painter.setPen(Qt.NoPen)
        sweep_brush = QRadialGradient(center_x, center_y, radar_radius)
        sweep_brush.setColorAt(0.0, QColor(0, 255, 200, 45))
        sweep_brush.setColorAt(1.0, QColor(0, 255, 200, 5))
        painter.setBrush(QBrush(sweep_brush))
        painter.drawPath(sweep_path)

        # 4. Badge trạng thái (Sử dụng Font cache sẵn)
        if sonar_active:
            painter.setFont(self.font_badge)
            painter.setPen(QColor(224, 64, 251, 230))
            painter.drawText(25, 30, "🦇 SLAYER DETECTION ACTIVE")
        elif slayer_info.get("scout_count", 0) > 0:
            painter.setFont(self.font_badge)
            painter.setPen(QColor(255, 171, 0, 230))
            painter.drawText(25, 30, f"📡 ELF SCOUT RADAR: {slayer_info.get('scout_count')} QUÁI NGOÀI TẦM")
        elif self.show_slayer_sonar:
            painter.setFont(self.font_mini)
            painter.setPen(QColor(0, 229, 255, 140))
            painter.drawText(25, 30, "📡 CHẾ ĐỘ QUÉT SIÊU ÂM (SONAR)")

        if not self.radar_data or "player" not in self.radar_data:
            painter.setFont(self.font_badge)
            painter.setPen(QColor(255, 255, 255, 120))
            painter.drawText(int(center_x - 70), int(center_y), "Đang chờ dữ liệu game...")
            return

        p = self.radar_data["player"]
        px, py = p["x"], p["y"]

        # Thiết lập Font chung cho các thực thể để không tạo lại QFont liên tục
        painter.setFont(self.font_mini)

        # 5. Vẽ BÃI QUÁI BẢN ĐỒ MẶC ĐỊNH (🎯 Map Spots)
        if self.show_map_spots:
            for spot in self.radar_data.get("map_spots", []):
                dx = spot["x"] - px
                dy = spot["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale
                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    s_tier = spot.get("tier", "free")
                    if s_tier == "megavip":
                        border_color = QColor(255, 215, 0, 190)
                        dot_color = QColor(255, 215, 0, 240)
                    elif s_tier == "vip":
                        border_color = QColor(0, 229, 255, 190)
                        dot_color = QColor(0, 229, 255, 240)
                    else:
                        border_color = QColor(100, 255, 120, 170)
                        dot_color = QColor(0, 230, 118, 220)

                    painter.setPen(QPen(border_color, 1.5, Qt.DashLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(screen_x, screen_y), 8.0, 8.0)

                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(QPointF(screen_x, screen_y), 3.0, 3.0)

                    if self.show_labels:
                        painter.setFont(self.font_mini_bold)
                        painter.setPen(dot_color)
                        tier_badge = f" [{spot.get('tier_label', '')}]" if spot.get('tier_label') else ""
                        painter.drawText(int(screen_x + 8), int(screen_y + 3), f"🎯 {spot['name']}{tier_badge}")
                        painter.setFont(self.font_mini)

        # 6. Vẽ CỔNG MAP (Square Cyan Icon)
        if self.show_gates:
            for g in self.radar_data.get("gates", []):
                dx = g["x"] - px
                dy = g["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale
                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    painter.setPen(QPen(QColor(0, 229, 255, 220), 1.5))
                    painter.setBrush(QBrush(QColor(0, 150, 180, 150)))
                    painter.drawRect(int(screen_x - 4), int(screen_y - 4), 8, 8)
                    if self.show_labels:
                        painter.setPen(QColor(0, 229, 255, 180))
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), g["name"][:12])

        # 7. Vẽ VẬT PHẨM RƠI TRÊN ĐẤT (Ground Items) - Hình Thoi Kim Cương ✦
        if self.show_ground_items:
            for it in self.radar_data.get("ground_items", []):
                is_scout = it.get("is_scout", False)
                if is_scout and not self.show_scout_memory:
                    continue

                dx = it["x"] - px
                dy = it["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale

                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    if it.get("is_jewel"):
                        color_border = QColor(255, 255, 255, 230)
                        color_fill = QColor(224, 64, 251, 240)
                        d_size = 5.0
                    elif it.get("is_exc"):
                        color_border = QColor(255, 215, 0, 230)
                        color_fill = QColor(0, 230, 118, 240)
                        d_size = 5.5
                    elif it.get("is_anc"):
                        color_border = QColor(255, 255, 255, 230)
                        color_fill = QColor(0, 176, 255, 240)
                        d_size = 5.5
                    elif it.get("is_zen"):
                        color_border = QColor(255, 215, 0, 180)
                        color_fill = QColor(255, 215, 0, 210)
                        d_size = 4.0
                    else:
                        color_border = QColor(176, 190, 197, 180)
                        color_fill = QColor(144, 164, 174, 200)
                        d_size = 4.0

                    diamond = QPolygonF([
                        QPointF(screen_x, screen_y - d_size),
                        QPointF(screen_x + d_size, screen_y),
                        QPointF(screen_x, screen_y + d_size),
                        QPointF(screen_x - d_size, screen_y)
                    ])
                    painter.setPen(QPen(color_border, 1))
                    painter.setBrush(QBrush(color_fill))
                    painter.drawPolygon(diamond)

                    if self.show_labels:
                        if it.get("is_jewel") or it.get("is_exc"):
                            painter.setFont(self.font_mini_bold)
                        painter.setPen(color_fill)
                        scout_prefix = "📡 " if is_scout else ""
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), f"{scout_prefix}{it['name'][:14]}")
                        if it.get("is_jewel") or it.get("is_exc"):
                            painter.setFont(self.font_mini)

        # 8. Vẽ QUÁI VẬT & NPC & BOSS (Gồm Quái trực tiếp, Boss, NPC, Quái Slayer Sonar, và Quái Đã Thám Thính)
        drawn_npcs = set()
        if self.show_monsters or self.show_npcs:
            for mon in self.radar_data.get("monsters", []):
                is_scout = mon.get("is_scout", False)
                is_sonar = mon.get("is_sonar", False)
                is_npc = mon.get("is_npc", False)
                is_boss = mon.get("is_boss", False)
                is_elite = mon.get("is_elite", False)

                # Bộ lọc hiển thị
                if is_npc:
                    if not self.show_npcs:
                        continue
                    drawn_npcs.add((mon["x"], mon["y"]))
                else:
                    if not self.show_monsters:
                        continue
                    if is_scout and not self.show_scout_memory:
                        continue
                    if is_sonar and not is_scout and not self.show_slayer_sonar:
                        continue

                dx = mon["x"] - px
                dy = mon["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale

                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    if is_npc:
                        # NPC BẢN ĐỒ (Hình vuông xanh lam Cyan dạ quang)
                        painter.setPen(QPen(QColor(0, 229, 255, 230), 1.5))
                        painter.setBrush(QBrush(QColor(0, 180, 216, 210)))
                        painter.drawRect(int(screen_x - 3.5), int(screen_y - 3.5), 7, 7)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(0, 229, 255, 220))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"🧙 {mon['name'][:10]}")
                            painter.setFont(self.font_mini)

                    elif is_boss:
                        # BOSS THẾ GIỚI (Vòng tròn hoàng kim tỏa sáng)
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2, Qt.DashLine))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(screen_x, screen_y), 8.5, 8.5)

                        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                        painter.setBrush(QBrush(QColor(255, 30, 0, 250)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 5.5, 5.5)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(255, 215, 0))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"👑 {mon['name'][:12]}")
                            painter.setFont(self.font_mini)

                    elif is_scout:
                        # QUÁI GHI NHỚ THÁM THÍNH (NGOÀI TẦM MẮT CỦA ELF)
                        painter.setPen(QPen(QColor(255, 152, 0, 190), 1, Qt.DashLine))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(screen_x, screen_y), 7.0, 7.0)

                        painter.setPen(QPen(QColor(255, 255, 255), 1))
                        painter.setBrush(QBrush(QColor(255, 109, 0, 220)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 4.0, 4.0)

                        if self.show_labels:
                            painter.setPen(QColor(255, 183, 77))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"📡 {mon['name'][:10]}")

                    elif is_sonar:
                        # QUÁI NGOÀI TẦM MẮT TỪ SLAYER SONAR
                        painter.setPen(QPen(QColor(255, 64, 129, 210), 1, Qt.DashLine))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(screen_x, screen_y), 7.5, 7.5)

                        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                        painter.setBrush(QBrush(QColor(255, 23, 68, 240)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 4.5, 4.5)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(255, 128, 171))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"🦇 {mon['name'][:10]}")
                            painter.setFont(self.font_mini)

                    else:
                        # QUÁI TRONG TẦM NHÌN TRỰC TIẾP (3D VIEWPORT)
                        if is_elite:
                            painter.setPen(QPen(QColor(255, 215, 0, 220), 2))
                            painter.setBrush(QBrush(QColor(255, 50, 50, 240)))
                            painter.drawEllipse(QPointF(screen_x, screen_y), 5.5, 5.5)
                        else:
                            painter.setPen(QPen(QColor(255, 80, 80, 180), 1))
                            painter.setBrush(QBrush(QColor(255, 30, 30, 220)))
                            painter.drawEllipse(QPointF(screen_x, screen_y), 3.5, 3.5)

                        if self.show_labels:
                            painter.setPen(QColor(255, 200, 200, 180))
                            prefix = "🌟 " if is_elite else ""
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"{prefix}{mon['name'][:12]}")

        # 9. Vẽ NPC Bổ Sung (nếu còn NPC chưa vẽ trong npcs list)
        if self.show_npcs:
            for npc in self.radar_data.get("npcs", []):
                if (npc["x"], npc["y"]) in drawn_npcs:
                    continue
                dx = npc["x"] - px
                dy = npc["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale
                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    painter.setPen(QPen(QColor(0, 229, 255, 230), 1.5))
                    painter.setBrush(QBrush(QColor(0, 180, 216, 210)))
                    painter.drawRect(int(screen_x - 3.5), int(screen_y - 3.5), 7, 7)

                    if self.show_labels:
                        painter.setFont(self.font_mini_bold)
                        painter.setPen(QColor(0, 229, 255, 220))
                        painter.drawText(int(screen_x + 6), int(screen_y + 3), f"🧙 {npc['name'][:10]}")
                        painter.setFont(self.font_mini)

        # 10. Vẽ NGƯỜI CHƠI KHÁC
        if self.show_players:
            for pl in self.radar_data.get("players", []):
                is_sonar = pl.get("is_sonar", False)
                if is_sonar and not self.show_slayer_sonar:
                    continue

                dx = pl["x"] - px
                dy = pl["y"] - py
                screen_x = center_x + dx * scale
                screen_y = center_y - dy * scale

                if math.hypot(screen_x - center_x, screen_y - center_y) <= radar_radius:
                    if is_sonar:
                        painter.setPen(QPen(QColor(0, 229, 255, 180), 1, Qt.DashLine))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(screen_x, screen_y), 7.0, 7.0)

                        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                        painter.setBrush(QBrush(QColor(0, 229, 255, 230)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 4.5, 4.5)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(128, 222, 234))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"🦇 {pl['name'][:10]}")
                            painter.setFont(self.font_mini)
                    elif pl.get("is_pk"):
                        flash_color = QColor(255, 0, 0, 255) if int(time.time() * 4) % 2 == 0 else QColor(255, 120, 0, 255)
                        painter.setPen(QPen(QColor(255, 255, 255), 2))
                        painter.setBrush(QBrush(flash_color))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 6.5, 6.5)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(255, 80, 80))
                            g_tag = f" [{pl['guild_name']}]" if pl.get("guild_name") else ""
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"⚠️ {pl['name'][:12]}{g_tag}")
                            painter.setFont(self.font_mini)
                    elif pl.get("is_gm"):
                        painter.setPen(QPen(QColor(255, 215, 0), 2))
                        painter.setBrush(QBrush(QColor(180, 0, 255, 240)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 6.0, 6.0)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            painter.setPen(QColor(255, 215, 0))
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"👑 {pl['name'][:12]}")
                            painter.setFont(self.font_mini)
                    else:
                        painter.setPen(QPen(QColor(0, 255, 255, 200), 1))
                        painter.setBrush(QBrush(QColor(0, 180, 255, 230)))
                        painter.drawEllipse(QPointF(screen_x, screen_y), 4.5, 4.5)

                        if self.show_labels:
                            painter.setFont(self.font_mini_bold)
                            label_col = QColor(100, 240, 255)
                            painter.setPen(label_col)
                            g_tag = f" [{pl['guild_name']}]" if pl.get("guild_name") else ""
                            painter.drawText(int(screen_x + 6), int(screen_y + 3), f"{pl['name'][:12]}{g_tag}")
                            painter.setFont(self.font_mini)

        # 11. Vẽ Nhân vật của bản thân ở tâm
        painter.setPen(QPen(QColor(0, 255, 120, 100), 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), 8.0, 8.0)

        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(0, 255, 150, 255)))
        painter.drawEllipse(QPointF(center_x, center_y), 4.5, 4.5)

        painter.setFont(self.font_coords)
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(int(center_x - 30), int(center_y + 22), f"({px}, {py})")

        # VIP Badge ở tâm nhân vật
        vip_tag = p.get("vip_tag", "")
        if vip_tag:
            painter.setFont(self.font_mini_bold)
            if p.get("is_megavip"):
                painter.setPen(QColor(255, 215, 0))  # Vàng gold MEGAVIP
            elif p.get("is_vip"):
                painter.setPen(QColor(0, 229, 255))  # Xanh ngọc VIP
            else:
                painter.setPen(QColor(180, 180, 180))  # Xám bạc Free
            painter.drawText(int(center_x - 34), int(center_y - 12), vip_tag)


class RadarMainWindow(QMainWindow):
    """Cửa sổ chính của Tool Radar Sci-Fi hỗ trợ ELF & mọi Class."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEGAMU Radar & Entity Scanner - [Universal Scout HUD]")
        self.resize(1060, 700)

        ico = get_resource_path("megamu_dashboard_icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

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
            QFrame#sonarBox {
                background-color: #161b26;
                border: 1px solid #5c2d91;
                border-radius: 6px;
                padding: 6px;
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
            QTabWidget::pane {
                border: 1px solid #1f333f;
                background-color: #0d161c;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #121d24;
                color: #8b949e;
                padding: 6px 12px;
                border: 1px solid #1f333f;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #0d161c;
                color: #00e5ff;
                border-bottom: 2px solid #00e5ff;
            }
            QTabBar::tab:hover {
                color: #ffffff;
            }
            QTableWidget {
                background-color: #0d161c;
                border: none;
                gridline-color: #1a2c38;
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
            QPushButton#btnSonar {
                background-color: #6a1b9a;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #ab47bc;
            }
            QPushButton#btnSonar:hover {
                background-color: #8e24aa;
            }
            QPushButton#btnClear {
                background-color: #2e1a20;
                color: #ff7875;
                border: 1px solid #5c2429;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton#btnClear:hover {
                background-color: #431b22;
            }
            QPushButton#btnPreset {
                background-color: #182833;
                border: 1px solid #284457;
                color: #70cbf4;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton#btnPreset:hover {
                background-color: #244154;
                color: #ffffff;
            }
            QCheckBox {
                spacing: 5px;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
        """)

        self.scan_thread: Optional[RadarScanThread] = None
        self.last_radar_data: Dict[str, Any] = {}
        self.auto_maintain_sonar = False
        self._last_table_update = 0.0
        self.nav_thread: Optional[threading.Thread] = None
        self.nav_stop_event = threading.Event()

        self.auto_sonar_timer = QTimer(self)
        self.auto_sonar_timer.timeout.connect(self._check_and_maintain_sonar)
        self.auto_sonar_timer.start(5000)

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

        # Cảnh báo an toàn
        self.lbl_alert = QLabel("✔ Khu vực an toàn - Không có Sát nhân PK hoặc GM")
        self.lbl_alert.setObjectName("alertBanner")
        self.lbl_alert.setStyleSheet("background-color: #10291f; color: #00e676; border: 1px solid #00e676;")
        radar_layout.addWidget(self.lbl_alert)

        splitter.addWidget(radar_container)

        # ----------------- CỘT PHẢI: BẢNG ĐIỀU KHIỂN & DANH SÁCH -----------------
        side_panel = QFrame()
        side_panel.setObjectName("panelFrame")
        side_panel.setMinimumWidth(500)
        side_layout = QVBoxLayout(side_panel)

        # 1. Chọn Client Game
        client_box = QHBoxLayout()
        client_box.addWidget(QLabel("Client Game:"))
        self.cb_clients = QComboBox()
        self.cb_clients.currentIndexChanged.connect(self._on_client_changed)
        client_box.addWidget(self.cb_clients, stretch=1)
        side_layout.addLayout(client_box)

        # 2. KHUNG ĐIỀU KHIỂN SÓNG DÒ & THÁM THÍNH (UNIVERSAL SCOUT CONSOLE)
        sonar_frame = QFrame()
        sonar_frame.setObjectName("sonarBox")
        sonar_layout = QVBoxLayout(sonar_frame)
        sonar_layout.setContentsMargins(8, 8, 8, 8)
        sonar_layout.setSpacing(6)

        sonar_top = QHBoxLayout()
        self.lbl_sonar_status = QLabel("📡 Sóng Dò & Thám Thính: Khởi tạo...")
        self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #00e5ff; font-size: 12px;")
        sonar_top.addWidget(self.lbl_sonar_status)
        sonar_top.addStretch()

        self.btn_cast_sonar = QPushButton("📡 Kích Hoạt Sóng")
        self.btn_cast_sonar.setObjectName("btnSonar")
        self.btn_cast_sonar.clicked.connect(self._on_cast_sonar_clicked)
        sonar_top.addWidget(self.btn_cast_sonar)

        self.btn_clear_scout = QPushButton("🗑️ Xóa Bộ Nhớ")
        self.btn_clear_scout.setObjectName("btnClear")
        self.btn_clear_scout.setToolTip("Xóa trắng các quái và vật phẩm đã thám thính để làm mới radar")
        self.btn_clear_scout.clicked.connect(self._on_clear_scout_clicked)
        sonar_top.addWidget(self.btn_clear_scout)
        sonar_layout.addLayout(sonar_top)

        sonar_bot = QHBoxLayout()
        self.chk_auto_sonar = QCheckBox("⚡ Tự duy trì Sóng Dò (Auto Keep Active)")
        self.chk_auto_sonar.toggled.connect(self._on_auto_sonar_toggled)
        sonar_bot.addWidget(self.chk_auto_sonar)

        self.lbl_sonar_hint = QLabel("(Tự động ghi nhớ quái & vật phẩm ngoài tầm mắt)")
        self.lbl_sonar_hint.setStyleSheet("color: #8b949e; font-size: 10px;")
        sonar_bot.addWidget(self.lbl_sonar_hint)
        sonar_layout.addLayout(sonar_bot)

        side_layout.addWidget(sonar_frame)

        # 3. Điều khiển Bán kính Radar (Zoom & Presets)
        radius_ctrl = QVBoxLayout()
        radius_header = QHBoxLayout()
        self.lbl_radius_val = QLabel("Bán kính quét: 30 ô")
        self.lbl_radius_val.setStyleSheet("font-weight: bold; color: #00e5ff;")
        radius_header.addWidget(self.lbl_radius_val)
        radius_header.addStretch()

        for p_val, p_lbl in [(15, "15 ô (Mắt)"), (30, "30 ô (Gần)"), (60, "60 ô (Xa)"), (100, "100 ô (Toàn map)")]:
            btn = QPushButton(p_lbl)
            btn.setObjectName("btnPreset")
            btn.clicked.connect(lambda _, v=p_val: self.slider_radius.setValue(v))
            radius_header.addWidget(btn)
        radius_ctrl.addLayout(radius_header)

        self.slider_radius = QSlider(Qt.Horizontal)
        self.slider_radius.setRange(5, 100)
        self.slider_radius.setValue(30)
        self.slider_radius.valueChanged.connect(self._on_radius_changed)
        radius_ctrl.addWidget(self.slider_radius)
        side_layout.addLayout(radius_ctrl)

        # Checkboxes Overlay
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

        # Bộ lọc đối tượng Radar (Có Bãi Quái & Thám Thính ngoài tầm mắt)
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(4)

        row_filt1 = QHBoxLayout()
        self.chk_mon = QCheckBox("👾 Quái vật")
        self.chk_mon.setChecked(True)
        self.chk_mon.toggled.connect(lambda v: setattr(self.radar_widget, "show_monsters", v))
        row_filt1.addWidget(self.chk_mon)

        self.chk_npc = QCheckBox("🧙 NPC")
        self.chk_npc.setChecked(True)
        self.chk_npc.toggled.connect(lambda v: setattr(self.radar_widget, "show_npcs", v))
        row_filt1.addWidget(self.chk_npc)

        self.chk_spots = QCheckBox("🎯 Bãi Quái")
        self.chk_spots.setChecked(True)
        self.chk_spots.setToolTip("Hiển thị các bãi quái mặc định của map (Dungeon, Devias, Lorencia...)")
        self.chk_spots.toggled.connect(lambda v: setattr(self.radar_widget, "show_map_spots", v))
        row_filt1.addWidget(self.chk_spots)

        self.chk_items = QCheckBox("💎 Vật phẩm")
        self.chk_items.setChecked(True)
        self.chk_items.toggled.connect(lambda v: setattr(self.radar_widget, "show_ground_items", v))
        row_filt1.addWidget(self.chk_items)
        filter_layout.addLayout(row_filt1)

        row_filt2 = QHBoxLayout()
        self.chk_pl = QCheckBox("👤 Người chơi")
        self.chk_pl.setChecked(True)
        self.chk_pl.toggled.connect(lambda v: setattr(self.radar_widget, "show_players", v))
        row_filt2.addWidget(self.chk_pl)

        self.chk_scout = QCheckBox("🧠 Đã Thám Thính")
        self.chk_scout.setChecked(True)
        self.chk_scout.setToolTip("Hiển thị các quái vật & vật phẩm đã thám thính dù nhân vật đã đi ra xa ngoài tầm mắt")
        self.chk_scout.toggled.connect(lambda v: setattr(self.radar_widget, "show_scout_memory", v))
        row_filt2.addWidget(self.chk_scout)

        self.chk_lbl = QCheckBox("🏷️ Nhãn")
        self.chk_lbl.setChecked(True)
        self.chk_lbl.toggled.connect(lambda v: setattr(self.radar_widget, "show_labels", v))
        row_filt2.addWidget(self.chk_lbl)
        filter_layout.addLayout(row_filt2)

        side_layout.addLayout(filter_layout)

        side_layout.addSpacing(4)

        # 4. HỆ THỐNG 4 TABS DANH SÁCH CHI TIẾT
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # TAB 1: THỰC THỂ BẢN ĐỒ (QUÁI VẬT, NPC, BOSS)
        tab_mon_widget = QWidget()
        tab_mon_layout = QVBoxLayout(tab_mon_widget)
        tab_mon_layout.setContentsMargins(4, 4, 4, 4)
        self.table_monsters = QTableWidget()
        self.table_monsters.setColumnCount(6)
        self.table_monsters.setHorizontalHeaderLabels(["Tên Thực Thể", "Phân Loại", "Nguồn Quét", "Cấp", "Tọa độ", "Cách (ô)"])
        self.table_monsters.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_monsters.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_monsters.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        tab_mon_layout.addWidget(self.table_monsters)
        self.tab_widget.addTab(tab_mon_widget, "👾 Quái & 🧙 NPC (0)")

        # TAB 2: BÃI QUÁI MAP (MAP SPOTS)
        tab_spot_widget = QWidget()
        tab_spot_layout = QVBoxLayout(tab_spot_widget)
        tab_spot_layout.setContentsMargins(4, 4, 4, 4)
        self.table_spots = QTableWidget()
        self.table_spots.setColumnCount(5)
        self.table_spots.setHorizontalHeaderLabels(["Tên Bãi Quái", "Phân Cấp Bãi", "Tọa độ", "Cách (ô)", "Điều Kiện Ra Bãi"])
        self.table_spots.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_spots.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_spots.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_spots.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_spots.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        tab_spot_layout.addWidget(self.table_spots)

        # Thanh nút điều khiển ra bãi quái
        row_spot_actions = QHBoxLayout()
        self.btn_go_spot = QPushButton("🚀 Tự Động Chạy Ra Bãi (Click đúp dòng)")
        self.btn_go_spot.setStyleSheet("background-color: #00796b; color: #ffffff; font-weight: bold; padding: 6px;")
        self.btn_go_spot.clicked.connect(self._navigate_to_selected_spot)

        self.btn_stop_spot = QPushButton("🛑 Dừng Chạy")
        self.btn_stop_spot.setStyleSheet("background-color: #5c1418; color: #ff4d4f; font-weight: bold; padding: 6px;")
        self.btn_stop_spot.clicked.connect(self._stop_navigation)

        row_spot_actions.addWidget(self.btn_go_spot, stretch=3)
        row_spot_actions.addWidget(self.btn_stop_spot, stretch=1)
        tab_spot_layout.addLayout(row_spot_actions)

        self.table_spots.cellDoubleClicked.connect(lambda r, c: self._navigate_to_selected_spot())
        self.tab_widget.addTab(tab_spot_widget, "🎯 Bãi quái Map (0)")

        # TAB 3: VẬT PHẨM RƠI
        tab_item_widget = QWidget()
        tab_item_layout = QVBoxLayout(tab_item_widget)
        tab_item_layout.setContentsMargins(4, 4, 4, 4)
        self.table_items = QTableWidget()
        self.table_items.setColumnCount(5)
        self.table_items.setHorizontalHeaderLabels(["Tên Vật phẩm", "Phân loại", "Cấp", "Tọa độ", "Cách (ô)"])
        self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        tab_item_layout.addWidget(self.table_items)
        self.tab_widget.addTab(tab_item_widget, "💎 Vật phẩm rơi (0)")

        # TAB 4: NGƯỜI CHƠI & CỔNG MAP
        tab_pl_widget = QWidget()
        tab_pl_layout = QVBoxLayout(tab_pl_widget)
        tab_pl_layout.setContentsMargins(4, 4, 4, 4)
        self.table_players = QTableWidget()
        self.table_players.setColumnCount(7)
        self.table_players.setHorizontalHeaderLabels(["Tên Đối tượng", "Nguồn", "Guild", "Class", "Tọa độ", "Cách (ô)", "Trạng thái"])
        self.table_players.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_players.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_players.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        tab_pl_layout.addWidget(self.table_players)
        self.tab_widget.addTab(tab_pl_widget, "👤 Người chơi & Cổng (0)")

        side_layout.addWidget(self.tab_widget, stretch=1)

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
                if name in ('megamu.exe', 'megamu') or 'megamu' in name:
                    if 'dashboard' not in name and 'auto' not in name and 'bot' not in name:
                        pids.append(p.info['pid'])
            except Exception:
                pass

        if WindowHelper:
            try:
                ensure_desktop_attached()
                for pid, hwnd, title, w, h in WindowHelper.get_unity_windows():
                    if pid not in pids:
                        pids.append(pid)
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
                        vip_str = f" [{pl.get('vip_tag', 'Free')}]" if pl.get("vip_tag") else ""
                        desc = f"{pl['name']} ({pl['class']}){vip_str} - PID {pid}"
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
        self.lbl_radius_val.setText(f"Bán kính quét: {val} ô")
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

    def _on_clear_scout_clicked(self):
        """Xóa bộ nhớ thám thính để làm mới radar."""
        if self.scan_thread:
            self.scan_thread.clear_cache()
        self.lbl_sonar_hint.setText("(Đã xóa bộ nhớ thám thính, đang quét lại...)")

    def _on_cast_sonar_clicked(self):
        """Kích hoạt thủ công kỹ năng Slayer Detection (chạy background thread, không đơ UI)."""
        pid = self.cb_clients.currentData()
        if not pid or pid <= 0:
            return

        sonar = self.last_radar_data.get("slayer_sonar", {})
        target_pid = pid

        if not sonar.get("has_skill") and sonar.get("relay_pid"):
            target_pid = sonar["relay_pid"]
            slot = 3
        else:
            slot = sonar.get("slot", 3)

        self.lbl_sonar_status.setText("📡 ĐANG GỬI LỆNH PHÁT SÓNG...")
        threading.Thread(target=cast_slayer_detection_win32, args=(target_pid, slot), daemon=True).start()

    def _on_auto_sonar_toggled(self, checked: bool):
        self.auto_maintain_sonar = checked

    def _check_and_maintain_sonar(self):
        """Tự động kiểm tra và hồi chiêu Slayer Detection nếu bật chế độ duy trì (chạy background thread)."""
        if not self.auto_maintain_sonar:
            return

        sonar = self.last_radar_data.get("slayer_sonar", {})
        pid = self.cb_clients.currentData()
        if not pid or pid <= 0:
            return

        target_pid = None
        slot = 3

        if sonar.get("has_skill"):
            target_pid = pid
            slot = sonar.get("slot", 3)
        elif sonar.get("relay_pid"):
            target_pid = sonar["relay_pid"]
            slot = 3

        if target_pid and not sonar.get("active"):
            threading.Thread(target=cast_slayer_detection_win32, args=(target_pid, slot), daemon=True).start()

    def _navigate_to_selected_spot(self):
        """Kích hoạt điều hướng nhân vật tự động chạy thẳng ra bãi quái đã chọn (hỗ trợ cả Free và VIP)."""
        row = self.table_spots.currentRow()
        if row < 0:
            QMessageBox.information(self, "Chọn bãi quái", "Vui lòng click chọn 1 bãi quái trong danh sách để chạy ra bãi!")
            return

        map_spots = self.last_radar_data.get("map_spots", [])
        if row >= len(map_spots):
            return
        sp = map_spots[row]
        tx, ty = sp["x"], sp["y"]
        s_name = sp["name"]

        pid = self.cb_clients.currentData()
        if not pid or pid <= 0:
            QMessageBox.warning(self, "Chưa chọn Client", "Vui lòng chọn một cửa sổ game MEGAMU đang chạy!")
            return

        if not MegNavigator:
            QMessageBox.warning(self, "Lỗi Module", "Không tìm thấy MegNavigator để điều hướng!")
            return

        self.nav_stop_event.set()
        time.sleep(0.05)
        self.nav_stop_event.clear()

        self.lbl_alert.setText(f"🏃 ĐANG CHẠY RA BÃI: {s_name} ({tx}, {ty})... (Bấm 'Dừng Chạy' để hủy)")
        self.lbl_alert.setStyleSheet("background-color: #0d3b66; color: #00e5ff; border: 1px solid #00e5ff;")

        def _nav_worker():
            try:
                nav = MegNavigator(pid)
                ok = nav.navigate_continuous(
                    target_x=tx,
                    target_y=ty,
                    arrival_radius=2,
                    auto_attack_on_arrival=True,
                    stop_event=self.nav_stop_event,
                    log_callback=lambda msg: print(f"[RADAR NAV] {msg}")
                )
                if ok:
                    self.lbl_alert.setText(f"🎉 ĐÃ ĐẾN BÃI: {s_name} ({tx}, {ty})! Tự động bật tấn công MuHelper.")
                    self.lbl_alert.setStyleSheet("background-color: #10291f; color: #00e676; border: 1px solid #00e676;")
            except Exception as e:
                print(f"[RADAR NAV ERROR] {e}")

        self.nav_thread = threading.Thread(target=_nav_worker, daemon=True)
        self.nav_thread.start()

    def _stop_navigation(self):
        """Hủy lệnh chạy ra bãi."""
        self.nav_stop_event.set()
        self.lbl_alert.setText("⏹ ĐÃ DỪNG LỆNH CHẠY RA BÃI.")
        self.lbl_alert.setStyleSheet("background-color: #3b1114; color: #ff7875; border: 1px solid #ff4d4f;")

    def _on_tab_changed(self, index: int):
        """Khi người dùng chuyển tab, lập tức nạp dữ liệu cho tab mới."""
        self._refresh_active_tab()

    @staticmethod
    def _set_cell(table: QTableWidget, row: int, col: int, text: str, color: Optional[QColor] = None):
        """Tái sử dụng QTableWidgetItem để tránh cấp phát bộ nhớ & lag UI."""
        item = table.item(row, col)
        if not item:
            item = QTableWidgetItem(text)
            if color:
                item.setForeground(color)
            table.setItem(row, col, item)
        else:
            if item.text() != text:
                item.setText(text)
            if color:
                item.setForeground(color)

    def _refresh_active_tab(self):
        """Chỉ vẽ lại dữ liệu của DUY NHẤT tab đang hiển thị để tiết kiệm 75% CPU UI."""
        if not self.last_radar_data:
            return
        idx = self.tab_widget.currentIndex()
        if idx == 0:
            self._update_monsters_table(self.last_radar_data.get("monsters", []))
        elif idx == 1:
            self._update_spots_table(self.last_radar_data.get("map_spots", []))
        elif idx == 2:
            self._update_items_table(self.last_radar_data.get("ground_items", []))
        elif idx == 3:
            self._update_players_table(
                self.last_radar_data.get("players", []),
                self.last_radar_data.get("gates", [])
            )

    def _update_monsters_table(self, monsters: List[Dict[str, Any]]):
        self.table_monsters.setUpdatesEnabled(False)
        self.table_monsters.setRowCount(len(monsters))
        col_scout = QColor(255, 171, 0)
        col_sonar = QColor(255, 64, 129)
        col_elite = QColor(255, 215, 0)
        col_boss = QColor(255, 215, 0)
        col_npc = QColor(0, 229, 255)
        col_summon = QColor(179, 136, 255)
        col_sonar_src = QColor(224, 64, 251)

        for row, mon in enumerate(monsters):
            is_npc = mon.get("is_npc", False)
            is_boss = mon.get("is_boss", False)
            is_elite = mon.get("is_elite", False)
            is_scout = mon.get("is_scout", False)
            is_sonar = mon.get("is_sonar", False)
            category = mon.get("category", "👾 Quái Thường")
            sub_type = mon.get("sub_type", "normal")

            # Col 0: Tên Thực Thể
            prefix = ""
            if is_boss:
                prefix = "👑 [BOSS] "
                color_name = col_boss
            elif is_elite:
                prefix = "🌟 [TINH ANH] "
                color_name = col_elite
            elif is_npc:
                prefix = "🧙 "
                color_name = col_npc
            elif sub_type == "summon":
                prefix = "🐾 "
                color_name = col_summon
            elif is_scout:
                prefix = "📡 "
                color_name = col_scout
            elif is_sonar:
                prefix = "🦇 "
                color_name = col_sonar
            else:
                color_name = None

            self._set_cell(self.table_monsters, row, 0, f"{prefix}{mon['name']}", color_name)

            # Col 1: Phân Loại
            if is_npc:
                cat_color = col_npc
            elif is_boss:
                cat_color = col_boss
            elif is_elite:
                cat_color = col_elite
            elif sub_type == "summon":
                cat_color = col_summon
            elif is_scout:
                cat_color = col_scout
            elif is_sonar:
                cat_color = col_sonar
            else:
                cat_color = None
            self._set_cell(self.table_monsters, row, 1, category, cat_color)

            # Col 2: Nguồn Quét
            src_text = "📡 Thám thính (Ngoài tầm)" if is_scout else ("🦇 Sóng Dò (Ngoài tầm)" if is_sonar else "👁️ Tầm mắt (3D)")
            src_color = col_scout if is_scout else (col_sonar_src if is_sonar else None)
            self._set_cell(self.table_monsters, row, 2, src_text, src_color)

            # Col 3: Cấp
            lvl = mon.get("level", 0)
            lvl_str = str(lvl) if (lvl > 0 and not is_npc) else "-"
            self._set_cell(self.table_monsters, row, 3, lvl_str)

            # Col 4: Tọa độ
            self._set_cell(self.table_monsters, row, 4, f"({mon['x']}, {mon['y']})")

            # Col 5: Cách (ô)
            self._set_cell(self.table_monsters, row, 5, f"{mon['distance']} ô")
        self.table_monsters.setUpdatesEnabled(True)

    def _update_spots_table(self, map_spots: List[Dict[str, Any]]):
        self.table_spots.setUpdatesEnabled(False)
        self.table_spots.setRowCount(len(map_spots))
        col_gold = QColor(255, 215, 0)
        col_cyan = QColor(0, 229, 255)
        col_green = QColor(0, 230, 118)
        col_red = QColor(255, 77, 79)
        col_white = QColor(220, 220, 220)

        for row, sp in enumerate(map_spots):
            s_tier = sp.get("tier", "free")
            can_farm = sp.get("can_farm", True)

            # Col 0: Tên Bãi Quái
            self._set_cell(self.table_spots, row, 0, f"🎯 {sp['name']}", col_gold if s_tier == "megavip" else None)

            # Col 1: Phân Cấp Bãi
            tier_col = col_gold if s_tier == "megavip" else (col_cyan if s_tier == "vip" else col_white)
            self._set_cell(self.table_spots, row, 1, sp.get("tier_label", "🆓 Miễn Phí"), tier_col)

            # Col 2: Tọa độ
            self._set_cell(self.table_spots, row, 2, f"({sp['x']}, {sp['y']})")

            # Col 3: Cách (ô)
            self._set_cell(self.table_spots, row, 3, f"{sp['distance']} ô")

            # Col 4: Điều Kiện Ra Bãi
            status_text = sp.get("status_note", "✅ Tự do")
            status_col = col_green if can_farm else col_red
            self._set_cell(self.table_spots, row, 4, status_text, status_col)

        self.table_spots.setUpdatesEnabled(True)

    def _update_items_table(self, ground_items: List[Dict[str, Any]]):
        self.table_items.setUpdatesEnabled(False)
        self.table_items.setRowCount(len(ground_items))
        col_jewel = QColor(224, 64, 251)
        col_exc = QColor(0, 230, 118)
        col_anc = QColor(0, 176, 255)
        col_zen = QColor(255, 215, 0)

        for row, it in enumerate(ground_items):
            scout_tag = " [Ngoài tầm]" if it.get("is_scout") else ""
            color = col_jewel if it.get("is_jewel") else (col_exc if it.get("is_exc") else (col_anc if it.get("is_anc") else (col_zen if it.get("is_zen") else None)))
            self._set_cell(self.table_items, row, 0, it["name"] + scout_tag, color)
            self._set_cell(self.table_items, row, 1, it.get("category", "Vật phẩm"))
            self._set_cell(self.table_items, row, 2, f"+{it['level']}")
            self._set_cell(self.table_items, row, 3, f"({it['x']}, {it['y']})")
            self._set_cell(self.table_items, row, 4, f"{it['distance']} ô")
        self.table_items.setUpdatesEnabled(True)

    def _update_players_table(self, players: List[Dict[str, Any]], gates: List[Dict[str, Any]]):
        self.table_players.setUpdatesEnabled(False)
        total_pl_entries = len(players) + len(gates)
        self.table_players.setRowCount(total_pl_entries)
        cur_row = 0

        col_cyan = QColor(0, 229, 255)
        col_gold = QColor(255, 215, 0)
        col_red = QColor(255, 77, 79)

        for pl in players:
            is_sonar = pl.get("is_sonar", False)
            self._set_cell(self.table_players, cur_row, 0, pl["name"], col_cyan if is_sonar else None)
            self._set_cell(self.table_players, cur_row, 1, "🦇 Sóng Dò" if is_sonar else "👁️ Tầm mắt")

            guild_text = "-"
            if pl.get("guild_name"):
                role_tag = f" [{pl['guild_role']}]" if pl.get("guild_role") else ""
                union_tag = f" (LM: {pl['union_name']})" if pl.get("union_name") else ""
                guild_text = f"{pl['guild_name']}{role_tag}{union_tag}"
            g_color = col_gold if pl.get("guild_role") == "Chủ Bang" else (col_cyan if pl.get("guild_role") == "Phó Bang" else None)
            self._set_cell(self.table_players, cur_row, 2, guild_text, g_color)

            self._set_cell(self.table_players, cur_row, 3, pl["class"])
            self._set_cell(self.table_players, cur_row, 4, f"({pl['x']}, {pl['y']})")
            self._set_cell(self.table_players, cur_row, 5, f"{pl['distance']} ô")

            status_text = "Bình thường"
            s_color = None
            if pl.get("is_pk"):
                status_text = "⚠️ SÁT THỦ QUỶ ĐỎ"
                s_color = col_red
            elif pl.get("is_gm"):
                status_text = "🚨 ADMIN / GM"
                s_color = col_gold
            elif pl.get("guild_rel") == 2:
                status_text = "⚔️ GUILD ĐỐI ĐỊCH"
            elif pl.get("store_name"):
                status_text = f"Shop: {pl['store_name'][:10]}"
            self._set_cell(self.table_players, cur_row, 6, status_text, s_color)
            cur_row += 1

        for g in gates:
            self._set_cell(self.table_players, cur_row, 0, f"🚪 {g['name']}", col_cyan)
            self._set_cell(self.table_players, cur_row, 1, "Bản đồ")
            self._set_cell(self.table_players, cur_row, 2, "-")
            self._set_cell(self.table_players, cur_row, 3, "Cổng di chuyển")
            self._set_cell(self.table_players, cur_row, 4, f"({g['x']}, {g['y']})")
            self._set_cell(self.table_players, cur_row, 5, f"{g['distance']} ô")
            self._set_cell(self.table_players, cur_row, 6, "Cố định")
            cur_row += 1

        self.table_players.setUpdatesEnabled(True)

    def _on_data_received(self, data: Dict[str, Any]):
        if "error" in data:
            self.lbl_map_info.setText(f"LỖI: {data['error']}")
            return

        self.last_radar_data = data

        p = data["player"]
        m = data["map"]
        monsters = data.get("monsters", [])
        players = data.get("players", [])
        ground_items = data.get("ground_items", [])
        gates = data.get("gates", [])
        map_spots = data.get("map_spots", [])
        sonar = data.get("slayer_sonar", {})

        # 1. Cập nhật Header
        vip_tag = p.get("vip_tag", "Free")
        self.lbl_map_info.setText(f"📍 {m['name']} (ID {m['id']}) | {p['name']} ({p['class']} Lv {p['level']}) [{vip_tag}] - ({p['x']}, {p['y']})")

        # 2. Cập nhật Universal Scout & Slayer Sonar Console
        is_sonar_active = sonar.get("active", False)
        has_skill = sonar.get("has_skill", False)
        is_relay = sonar.get("is_relay", False)
        relay_name = sonar.get("relay_name", "")
        scout_count = sonar.get("scout_count", 0)
        scout_total = sonar.get("scout_total", 0)

        if has_skill:
            # Nhân vật là Slayer
            slot = sonar.get("slot", 0)
            skill_name = sonar.get("skill_name", "")
            self.lbl_sonar_hint.setText(f"Phím tắt: [{slot}] - {skill_name}")
            if is_sonar_active:
                self.lbl_sonar_status.setText(f"🟢 SÓNG DÒ SLAYER ĐANG BẬT ({sonar.get('sonar_monsters', 0)} quái ngoài tầm)")
                self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #00e676; font-size: 12px;")
                self.btn_cast_sonar.setText("⚡ Sóng Đang Quét")
            else:
                self.lbl_sonar_status.setText("⚪ SÓNG DÒ SLAYER: CHỜ KÍCH HOẠT")
                self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #ffd600; font-size: 12px;")
                self.btn_cast_sonar.setText("📡 Phát Sóng Slayer")
        elif is_relay:
            # Nhân vật là ELF nhưng tiếp sóng từ Slayer chạy cùng máy!
            self.lbl_sonar_hint.setText(f"(Tiếp sóng từ Slayer: {relay_name})")
            self.lbl_sonar_status.setText(f"🟢 TIẾP SÓNG SLAYER: ĐANG HOẠT ĐỘNG ({sonar.get('sonar_monsters', 0)} quái ngoài tầm)")
            self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #00e5ff; font-size: 12px;")
            self.btn_cast_sonar.setText("⚡ Kích Hoạt Qua Slayer")
        else:
            # Nhân vật là ELF chạy solo (Sử dụng Bộ Nhớ Thám Thính Scout Radar)
            self.lbl_sonar_hint.setText(f"Bộ nhớ thám thính: Đang lưu {scout_total} quái & vật phẩm đã gặp")
            if scout_count > 0:
                self.lbl_sonar_status.setText(f"📡 THÁM THÍNH ELF: ĐANG QUÉT {scout_count} QUÁI NGOÀI TẦM MẮT")
                self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #ff9100; font-size: 12px;")
            else:
                self.lbl_sonar_status.setText("📡 SÓNG DÒ THÁM THÍNH: ĐANG TỰ ĐỘNG GHI NHỚ VẾT")
                self.lbl_sonar_status.setStyleSheet("font-weight: bold; color: #70cbf4; font-size: 12px;")
            self.btn_cast_sonar.setText("📡 Quét Bản Đồ")

        # 3. Cập nhật Canvas Radar với tần số cao (12.5 Hz mượt mà)
        self.radar_widget.update_data(data)

        # 4. Cập nhật Badge số lượng trên tiêu đề các Tab (chỉ đổi text, siêu nhanh)
        npc_count = len([m for m in monsters if m.get("is_npc")])
        mon_count = len(monsters) - npc_count
        if npc_count > 0 and mon_count > 0:
            tab0_title = f"👾 Quái ({mon_count}) & 🧙 NPC ({npc_count})"
        elif npc_count > 0:
            tab0_title = f"🧙 NPC ({npc_count})"
        else:
            tab0_title = f"👾 Quái vật ({mon_count})"
        self.tab_widget.setTabText(0, tab0_title)
        self.tab_widget.setTabText(1, f"🎯 Bãi quái Map ({len(map_spots)})")
        self.tab_widget.setTabText(2, f"💎 Vật phẩm ({len(ground_items)})")
        self.tab_widget.setTabText(3, f"👤 Người chơi & Cổng ({len(players) + len(gates)})")

        # 5. Cập nhật Cảnh báo an toàn
        has_pk = any(pl.get("is_pk") for pl in players)
        has_gm = any(pl.get("is_gm") for pl in players)
        if has_pk:
            self.lbl_alert.setText("🚨 CẢNH BÁO NGUY HIỂM: CÓ SÁT THỦ QUỶ ĐỎ PK ÁP SÁT BẠN!")
            self.lbl_alert.setStyleSheet("background-color: #5c1418; color: #ff4d4f; border: 1px solid #ff4d4f;")
        elif has_gm:
            self.lbl_alert.setText("🚨 CẢNH BÁO BẢO MẬT: PHÁT HIỆN GAME MASTER (ADMIN) ĐỨNG GẦN!")
            self.lbl_alert.setStyleSheet("background-color: #4a3800; color: #ffd666; border: 1px solid #ffd666;")
        else:
            self.lbl_alert.setText("✔ Khu vực an toàn - Không có Sát nhân PK hoặc GM")
            self.lbl_alert.setStyleSheet("background-color: #10291f; color: #00e676; border: 1px solid #00e676;")

        # 6. Điều tiết cập nhật Bảng danh sách: Throttle 250ms & Chỉ cập nhật DUY NHẤT Tab đang mở
        now = time.time()
        if now - self._last_table_update >= 0.25:
            self._last_table_update = now
            self._refresh_active_tab()

    def closeEvent(self, event):
        if self.auto_sonar_timer:
            self.auto_sonar_timer.stop()
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

