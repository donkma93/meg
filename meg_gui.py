#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - v1.5.1
====================================
Giao diện hoàn chỉnh và thuật toán chuẩn 100% khớp MEGAMU Auto Train Dashboard gốc:
- Giao diện 3 tab: 10 Tài khoản | Cấu hình | Nhật ký
- Lưu & đọc toàn bộ cấu hình TRỰC TIẾP từ file JSON (Zero RAM-loss):
  + autotrain_profiles.json (Cấu hình các chặng min/max, map, x, y, delay của Config 1..10)
  + autotrain_megamu_config.json (Config mặc định đồng bộ Config 1)
  + slot_assignments.json (Lưu cấu hình gán từng dòng 01..10)
  + ui_settings.json (Ngôn ngữ VI/EN/PT-BR)
- Kết nối native không chiếm chuột, không click tọa độ (Zero-Mouse Direct Engine).
- Tự động quét tiến trình MEGAMU.exe, tự gán PID, gán Team 5, kết nối và bật/tắt Auto hàng loạt.
"""

import os
import sys
import json
import time
import math
import heapq
import ctypes
import threading
from typing import Optional, List, Dict, Tuple, Any, Callable
from pathlib import Path

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
import psutil

# Core Engines
try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None

try:
    from meg_auto_worker import AutoTrainWorker, MapResolver
except ImportError:
    AutoTrainWorker = None
    MapResolver = None

try:
    import license_client
except ImportError:
    license_client = None

# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN TỆP
# ==============================================================================
APP_NAME = "MEGAMU Auto Train Dashboard"
APP_VERSION = "v1.5.1"
CURRENT_LICENSE = "--"  # Tạm thời chưa có license để --, khi nào xây dựng xong sẽ điền thông tin
DEFAULT_SLOTS = 10
MAX_SLOTS = 50

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
        p = base / name
        if p.exists():
            return p
        return Path(sys.executable).resolve().parent / name
    return Path(__file__).resolve().parent / name

BASE_DIR = app_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

LOGO_FILE = resource_path("megamu_dashboard_logo.png")
ICON_FILE = resource_path("megamu_dashboard_icon.ico")

PROFILE_FILE = CONFIG_DIR / "autotrain_profiles.json"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "autotrain_megamu_config.json"
SLOT_ASSIGNMENTS_FILE = CONFIG_DIR / "slot_assignments.json"
UI_SETTINGS_FILE = CONFIG_DIR / "ui_settings.json"
MAP_COMMANDS_FILE = CONFIG_DIR / "map_commands.json"
OFFSETS_FILE = CONFIG_DIR / "megamu_offsets.json"

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]
 
# ==============================================================================
# BỘ TẠO VECTOR ICON CHẤT LƯỢNG CAO (HIGH-DPI VECTOR ICONS)
# ==============================================================================
class UiIconFactory:
    """Tạo vector icon mượt mà sắc nét anti-aliased chất lượng cao (High-DPI)."""
    _cache: Dict[Tuple[str, str, Tuple[int, int]], ctk.CTkImage] = {}

    @classmethod
    def get(cls, name: str, color: str = "#cbd5e1", size: Tuple[int, int] = (16, 16)) -> ctk.CTkImage:
        key = (name, color, size)
        if key in cls._cache:
            return cls._cache[key]

        scale = 4
        cw = size[0] * scale
        ch = size[1] * scale
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        lw = max(2, int(1.4 * scale))
        pad = int(2.5 * scale)

        if name == "play":
            poly = [(int(cw * 0.32), int(ch * 0.22)), (int(cw * 0.78), int(ch * 0.5)), (int(cw * 0.32), int(ch * 0.78))]
            d.polygon(poly, fill=color)
        elif name == "stop":
            d.rounded_rectangle([int(cw * 0.26), int(ch * 0.26), int(cw * 0.74), int(ch * 0.74)], radius=int(2 * scale), fill=color)
        elif name == "gear":
            r_out = int(cw * 0.38)
            r_in = int(cw * 0.25)
            cx, cy = cw // 2, ch // 2
            d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=color, width=lw)
            teeth = 8
            for i in range(teeth):
                ang = i * (2 * math.pi / teeth)
                x1 = cx + int(r_in * math.cos(ang))
                y1 = cy + int(r_in * math.sin(ang))
                x2 = cx + int(r_out * math.cos(ang))
                y2 = cy + int(r_out * math.sin(ang))
                d.line([(x1, y1), (x2, y2)], fill=color, width=lw)
            hub_r = max(2, int(cw * 0.08))
            d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=color)
        elif name == "file":
            d.rounded_rectangle([int(cw * 0.24), int(ch * 0.15), int(cw * 0.76), int(ch * 0.85)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.36)), (int(cw * 0.64), int(ch * 0.36))], fill=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.50)), (int(cw * 0.64), int(ch * 0.50))], fill=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.64)), (int(cw * 0.52), int(ch * 0.64))], fill=color, width=lw)
        elif name == "user":
            cx, cy = cw // 2, ch // 2
            hr = int(cw * 0.18)
            d.ellipse([cx - hr, int(ch * 0.14), cx + hr, int(ch * 0.14) + 2 * hr], fill=color)
            d.pieslice([int(cw * 0.18), int(ch * 0.46), int(cw * 0.82), int(ch * 1.10)], start=180, end=360, fill=color)
        elif name == "link":
            lw_link = max(2, int(1.4 * scale))
            d.rounded_rectangle([int(cw * 0.16), int(ch * 0.32), int(cw * 0.56), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw_link)
            d.rounded_rectangle([int(cw * 0.44), int(ch * 0.32), int(cw * 0.84), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw_link)
        elif name == "refresh":
            d.arc([int(cw * 0.2), int(ch * 0.2), int(cw * 0.8), int(ch * 0.8)], start=40, end=310, fill=color, width=lw)
            arrow = [(int(cw * 0.76), int(ch * 0.34)), (int(cw * 0.92), int(ch * 0.18)), (int(cw * 0.66), int(ch * 0.16))]
            d.polygon(arrow, fill=color)
        elif name == "plus":
            cx, cy = cw // 2, ch // 2
            hl = int(cw * 0.28)
            d.line([(cx, cy - hl), (cx, cy + hl)], fill=color, width=int(1.8 * scale))
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))
        elif name == "minus":
            cx, cy = cw // 2, ch // 2
            hl = int(cw * 0.28)
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))
        elif name == "chat":
            d.rounded_rectangle([int(cw * 0.18), int(ch * 0.20), int(cw * 0.82), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw)
            poly = [(int(cw * 0.32), int(ch * 0.68)), (int(cw * 0.46), int(ch * 0.68)), (int(cw * 0.24), int(ch * 0.85))]
            d.polygon(poly, fill=color)
        elif name == "chevron_down":
            cx, cy = cw // 2, ch // 2
            hw = int(cw * 0.22)
            hh = int(ch * 0.14)
            d.line([(cx - hw, cy - hh), (cx, cy + hh)], fill=color, width=lw)
            d.line([(cx, cy + hh), (cx + hw, cy - hh)], fill=color, width=lw)
        elif name == "dot":
            cx, cy = cw // 2, ch // 2
            r = int(cw * 0.35)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

        res_img = im.resize(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=res_img, dark_image=res_img, size=size)
        cls._cache[key] = ctk_img
        return ctk_img

# ==============================================================================
# DROPDOWN HIỆN ĐẠI (MODERN OPTION MENU - FULL WIDTH & THEMED POPUP)
# ==============================================================================
class ModernOptionMenu(ctk.CTkFrame):
    """
    Dropdown menu phong cách hiện đại thay thế CTkOptionMenu:
    - Popup mở rộng 100% khớp đúng chiều rộng nút bấm (full-width), không bị ngắn cụt.
    - Giao diện đen sang trọng đồng bộ Dark mode, không bị viền trắng 3D của Windows Menu.
    - Tự động đóng khi click ra ngoài hoặc chọn xong.
    - Tích hợp 2-way binding với StringVar và hàm callback.
    """
    def __init__(
        self,
        master,
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        command: Optional[Callable[[str], Any]] = None,
        width: int = 220,
        height: int = 32,
        font: Optional[ctk.CTkFont] = None,
        fg_color: str = "#181c26",
        border_color: str = "transparent",
        hover_color: str = "#222736",
        text_color: str = "#f1f5f9",
        **kwargs
    ):
        # Bỏ qua các tham số riêng của CTkOptionMenu nếu truyền vào
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)

        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=fg_color,
            border_width=0,
            corner_radius=6,
            **kwargs
        )
        self.pack_propagate(False)

        self._base_fg = fg_color
        self._hover_bg = hover_color
        self._text_color = text_color
        self._font = font or ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self._req_width = width
        self._req_height = height
        self._last_close_time = 0.0

        self.values = list(values) if values else ["--"]
        self.variable = variable or ctk.StringVar(value=self.values[0] if self.values else "--")
        self.command = command
        self._popup = None

        # Text hiển thị giá trị hiện tại
        self._lbl = ctk.CTkLabel(
            self,
            text=self.variable.get(),
            font=self._font,
            text_color=self._text_color,
            anchor="w"
        )
        self._lbl.pack(side="left", fill="both", expand=True, padx=(10, 4))

        # Vector Icon Chevron Down
        self._chevron = ctk.CTkLabel(
            self,
            text="",
            image=UiIconFactory.get("chevron_down", color="#94a3b8", size=(10, 10))
        )
        self._chevron.pack(side="right", padx=(0, 10))

        # Đồng bộ khi biến StringVar thay đổi từ bên ngoài
        try:
            self.variable.trace_add("write", lambda *_: self._on_var_changed())
        except Exception:
            pass

        # Gán sự kiện click & hover cho toàn bộ frame và label
        for w in (self, self._lbl, self._chevron):
            w.bind("<Button-1>", lambda e: self._toggle_popup())
            w.bind("<Enter>", lambda e: self._on_enter())
            w.bind("<Leave>", lambda e: self._on_leave())
            w.configure(cursor="hand2")

    def _on_enter(self):
        self.configure(fg_color=self._hover_bg)

    def _on_leave(self):
        if not self._popup or not self._popup.winfo_exists():
            self.configure(fg_color=self._base_fg)

    def _on_var_changed(self):
        val = self.variable.get() if self.variable else "--"
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text=val)

    def _toggle_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
            return
        if time.time() - self._last_close_time < 0.15:
            return
        self._open_popup()

    def _open_popup(self):
        self._close_popup()
        self.update_idletasks()
        rx = self.winfo_rootx()
        ry = self.winfo_rooty() + self.winfo_height() + 2
        w = max(self.winfo_width(), self._req_width)

        num_items = len(self.values)
        item_h = 30
        h = max(38, min(240, num_items * item_h + 8))

        # Kiểm tra tràn đáy màn hình
        try:
            screen_h = self.winfo_screenheight()
            if ry + h > screen_h - 40:
                ry = max(10, self.winfo_rooty() - h - 2)
        except Exception:
            pass

        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        self._popup.geometry(f"{w}x{h}+{rx}+{ry}")

        outer = ctk.CTkFrame(
            self._popup,
            fg_color="#141722",
            border_width=0,
            corner_radius=6
        )
        outer.pack(fill="both", expand=True)

        container = outer
        if num_items > 7:
            container = ctk.CTkScrollableFrame(outer, fg_color="transparent", height=h - 8)
            container.pack(fill="both", expand=True, padx=2, pady=2)

        cur_val = self.variable.get()
        for val in self.values:
            is_active = (val == cur_val)
            btn = ctk.CTkButton(
                container,
                text=f"  {val}",
                anchor="w",
                height=item_h - 2,
                corner_radius=4,
                font=self._font,
                fg_color="#1c2436" if is_active else "transparent",
                hover_color="#222838",
                text_color="#38bdf8" if is_active else "#f1f5f9",
                command=lambda v=val: self._on_select(v)
            )
            btn.pack(fill="x", padx=3, pady=1)

        # Lắng nghe click bên ngoài thông qua root toplevel
        try:
            top_win = self.winfo_toplevel()
            self._popup.after(80, lambda: top_win.bind_all("<Button-1>", self._on_global_click, add="+"))
        except Exception:
            pass

    def _on_global_click(self, event):
        if not self._popup or not self._popup.winfo_exists():
            return
        try:
            px = self._popup.winfo_rootx()
            py = self._popup.winfo_rooty()
            pw = self._popup.winfo_width()
            ph = self._popup.winfo_height()
            if not (px <= event.x_root <= px + pw and py <= event.y_root <= py + ph):
                self._close_popup()
        except Exception:
            self._close_popup()

    def _close_popup(self):
        self._last_close_time = time.time()
        try:
            top_win = self.winfo_toplevel()
            top_win.unbind_all("<Button-1>")
        except Exception:
            pass
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        self._on_leave()

    def _on_select(self, value: str):
        self.set(value)
        self._close_popup()
        if self.command:
            self.command(value)

    def set(self, value: str):
        self.variable.set(value)
        if hasattr(self, "_lbl") and self._lbl.winfo_exists():
            self._lbl.configure(text=value)

    def get(self) -> str:
        return self.variable.get()

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs.pop("values"))
        if "variable" in kwargs:
            self.variable = kwargs.pop("variable")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists() and self.variable:
                self._lbl.configure(text=self.variable.get())
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "fg_color" in kwargs:
            self._base_fg = kwargs.pop("fg_color")
            super().configure(fg_color=self._base_fg)
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            if hasattr(self, "_lbl") and self._lbl.winfo_exists():
                self._lbl.configure(text_color=self._text_color)
        kwargs.pop("button_color", None)
        kwargs.pop("button_hover_color", None)
        kwargs.pop("dropdown_fg_color", None)
        kwargs.pop("dropdown_hover_color", None)
        kwargs.pop("dropdown_text_color", None)
        kwargs.pop("anchor", None)
        if kwargs:
            super().configure(**kwargs)

# ==============================================================================
# BẢNG DỊCH NGÔN NGỮ (I18N)
# ==============================================================================
I18N = {
    "vi": {
        "characters": "Tài khoản",
        "configuration": "Cấu hình",
        "logs": "Nhật ký",
        "text_config": "Mở thư mục",
        "connect_all": "Kết nối tất cả",
        "assign_team5": "Gán Team 5",
        "refresh_games": "Làm mới Game",
        "add": "Thêm",
        "remove": "Xóa",
        "col_no": "STT",
        "col_char_pid": "Nhân vật / PID",
        "col_route_preset": "Tuyến đường cấu hình",
        "col_coordinates": "Tọa độ",
        "col_status": "Trạng thái",
        "col_actions": "Thao tác",
        "edit_profile": "Sửa cấu hình:",
        "pk_delay": "Thời gian chờ PK/Hồi sinh:",
        "reload": "Tải lại",
        "save_profile": "Lưu cấu hình",
        "team_note": "Team mặc định: 1-5=C1, 6-10=C2, ... 46-50=C10. Có thể chọn cấu hình khác cho từng dòng.",
        "show": "Hiện:",
        "clear_view": "Xóa hiển thị",
        "all": "Tất cả",
        "stage_min": "Min",
        "stage_max": "Max",
        "stage_map": "Map",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Đang chạy",
        "status_moving": "Di chuyển",
        "status_disconnected": "Mất kết nối",
        "status_stopped": "Đã dừng",
        "status_idle": "Chờ",
        "total_accounts": "Tổng số tài khoản: {n}",
        "connected": "Đã kết nối",
        "license": "Bản quyền",
        "expiry_label": "Hạn",
        "header_stats": "Game: {games} | Đã kết nối: {conn}/{slots} | Auto: {auto} | Bản quyền: {license}",
        "footer_stats": "Tổng số: {slots} Tài khoản | Đã kết nối: {conn} | Đang chạy: {auto}",
        "lang_changed": "Đã chuyển đổi ngôn ngữ sang: {lang}"
    },
    "en": {
        "characters": "Characters",
        "configuration": "Configuration",
        "logs": "Logs",
        "text_config": "Text config",
        "connect_all": "Connect All",
        "assign_team5": "Assign Team 5",
        "refresh_games": "Refresh Game",
        "add": "Add",
        "remove": "Remove",
        "col_no": "No.",
        "col_char_pid": "Character / PID",
        "col_route_preset": "Target Route Preset",
        "col_coordinates": "Coordinates",
        "col_status": "Status",
        "col_actions": "Actions",
        "edit_profile": "Edit profile:",
        "pk_delay": "PK/Respawn delay:",
        "reload": "Reload",
        "save_profile": "Save Profile",
        "team_note": "Default teams: 1-5=C1, 6-10=C2, ... 46-50=C10. You can also choose a different profile per row.",
        "show": "Show:",
        "clear_view": "Clear View",
        "all": "All",
        "stage_min": "Min",
        "stage_max": "Max",
        "stage_map": "Map",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Running",
        "status_moving": "Moving",
        "status_disconnected": "Disconnected",
        "status_stopped": "Stopped",
        "status_idle": "Idle",
        "total_accounts": "Total accounts: {n}",
        "connected": "Connected",
        "license": "License",
        "expiry_label": "Exp",
        "header_stats": "Games: {games} | Connected: {conn}/{slots} | Auto: {auto} | License: {license}",
        "footer_stats": "Total: {slots} Accounts | Connected: {conn} | Running: {auto}",
        "lang_changed": "Language switched to: {lang}"
    },
    "pt-BR": {
        "characters": "Personagens",
        "configuration": "Configurações",
        "logs": "Registros",
        "text_config": "Arquivos config",
        "connect_all": "Conectar Todos",
        "assign_team5": "Atribuir Time 5",
        "refresh_games": "Atualizar Jogos",
        "add": "Adicionar",
        "remove": "Remover",
        "col_no": "Nº",
        "col_char_pid": "Personagem / PID",
        "col_route_preset": "Rota / Perfil",
        "col_coordinates": "Coordenadas",
        "col_status": "Status",
        "col_actions": "Ações",
        "edit_profile": "Editar perfil:",
        "pk_delay": "Espera PK/Respawn:",
        "reload": "Recarregar",
        "save_profile": "Salvar Perfil",
        "team_note": "Times padrão: 1-5=C1, 6-10=C2, ... 46-50=C10. Você có pode escolher outro perfil por linha.",
        "show": "Mostrar:",
        "clear_view": "Limpar Visão",
        "all": "Todos",
        "stage_min": "Mín",
        "stage_max": "Máx",
        "stage_map": "Mapa",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Executando",
        "status_moving": "Movendo",
        "status_disconnected": "Desconectado",
        "status_stopped": "Parado",
        "status_idle": "Aguardando",
        "total_accounts": "Total de contas: {n}",
        "connected": "Conectados",
        "license": "Licença",
        "expiry_label": "Val",
        "header_stats": "Jogos: {games} | Conectados: {conn}/{slots} | Auto: {auto} | Licença: {license}",
        "footer_stats": "Total: {slots} Contas | Conectados: {conn} | Executando: {auto}",
        "lang_changed": "Idioma alterado para: {lang}"
    }
}

CURRENT_LANG = "vi"

def load_language_preference() -> str:
    global CURRENT_LANG
    try:
        if UI_SETTINGS_FILE.exists():
            data = json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
            lang = str(data.get("language", "vi")).strip().lower()
            for k in I18N.keys():
                if k.lower() == lang:
                    CURRENT_LANG = k
                    return CURRENT_LANG
    except Exception:
        pass
    CURRENT_LANG = "vi"
    return CURRENT_LANG

def save_language_preference(lang: str):
    global CURRENT_LANG
    for k in I18N.keys():
        if k.lower() == lang.lower():
            CURRENT_LANG = k
            break
    try:
        data = {"language": CURRENT_LANG}
        UI_SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def tr(key: str, **kwargs) -> str:
    lang_dict = None
    for k, v in I18N.items():
        if k.lower() == CURRENT_LANG.lower():
            lang_dict = v
            break
    if not lang_dict:
        lang_dict = I18N.get("vi", {})
    text = lang_dict.get(key, I18N.get("vi", {}).get(key, key))
    try:
        return text.format(**kwargs)
    except Exception:
        return text

# ==============================================================================
# QUẢN LÝ TIẾN TRÌNH & TIÊU ĐỀ CỬA SỔ
# ==============================================================================
user32 = ctypes.windll.user32

def character_name_from_window_title(title: str) -> str:
    if not title:
        return ""
    title = str(title).strip()
    if "MEGAMU" not in title.upper():
        return ""
    head = title.split(" - MEGAMU")[0].strip()
    if " (" in head:
        head = head.split(" (")[0].strip()
    if not head or head.upper().startswith("MEGAMU"):
        return ""
    return head

def enumerate_megamu_processes() -> Dict[int, str]:
    """Tìm tất cả tiến trình MEGAMU.exe và lấy tiêu đề cửa sổ / tên nhân vật."""
    pids = set()
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['name'] and p.info['name'].lower() == 'megamu.exe':
                pids.add(p.info['pid'])
        except Exception:
            pass

    pid_to_title = {pid: "" for pid in pids}

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if "megamu" in title.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                p_val = pid.value
                if p_val in pid_to_title and not pid_to_title[p_val]:
                    pid_to_title[p_val] = title
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    return pid_to_title

# ==============================================================================
# QUẢN LÝ CẤU HÌNH TRỰC TIẾP TỪ FILE (ZERO-RAM LOSS PERSISTENCE)
# ==============================================================================
class ConfigPersistenceManager:
    """
    Đảm bảo 100% tất cả các cấu hình được đọc và ghi TRỰC TIẾP từ file đĩa JSON.
    Không lưu tạm trong RAM - Khi đóng và mở lại, mọi thiết lập đều được khôi phục nguyên vẹn.
    """
    _lock = threading.RLock()

    @staticmethod
    def get_fallback_config() -> Dict[str, Any]:
        return {
            "glide_speed": 3.5,
            "respawn_delay": 15,
            "map_load_delay": 1.8,
            "level1_delay": 4.0,
            "arrive_distance": 2.0,
            "respawn_distance": 12.0,
            "stuck_retry_delay": 3.5,
            "helper_native_timeout": 4.0,
            "helper_direct_fallback": True,
            "stages": [
                {"min_level": 1, "max_level": 39, "map_name": "Lorencia", "x": 70, "y": 147},
                {"min_level": 40, "max_level": 59, "map_name": "Dungeon 2", "x": 217, "y": 115},
                {"min_level": 60, "max_level": 159, "map_name": "Lost Tower 5", "x": 110, "y": 56},
                {"min_level": 160, "max_level": 399, "map_name": "Aida 1", "x": 135, "y": 150}
            ],
            "poll_interval": 0.55,
            "reset_confirm_seconds": 1.5,
            "map_command_retry_delay": 4.5,
            "map_verify_unknown_timeout": 6.0
        }

    @classmethod
    def load_profiles_store(cls) -> Dict[str, Any]:
        """Đọc autotrain_profiles.json trực tiếp từ ổ cứng."""
        with cls._lock:
            store = {}
            if PROFILE_FILE.exists():
                try:
                    store = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    store = {}
            
            if not isinstance(store, dict):
                store = {}
            if not isinstance(store.get("profiles"), dict):
                store["profiles"] = {}
            store["version"] = 2

            # Đảm bảo đủ Config 1..10
            fallback = cls.get_fallback_config()
            for idx in range(1, 11):
                s_idx = str(idx)
                item = store["profiles"].get(s_idx)
                if not isinstance(item, dict) or not isinstance(item.get("config"), dict):
                    store["profiles"][s_idx] = {
                        "name": f"Config {idx}",
                        "config": json.loads(json.dumps(fallback))
                    }
            return store

    @classmethod
    def load_single_profile(cls, profile_idx: int) -> Dict[str, Any]:
        """Đọc riêng lẻ 1 Profile từ file autotrain_profiles.json."""
        p_idx = max(1, min(10, int(profile_idx)))
        store = cls.load_profiles_store()
        cfg = store.get("profiles", {}).get(str(p_idx), {}).get("config")
        if not cfg or not isinstance(cfg, dict):
            cfg = cls.get_fallback_config()
        return json.loads(json.dumps(cfg))

    @classmethod
    def save_single_profile(cls, profile_idx: int, cfg: Dict[str, Any]):
        """Ghi trực tiếp Profile vào file autotrain_profiles.json."""
        p_idx = max(1, min(10, int(profile_idx)))
        with cls._lock:
            store = cls.load_profiles_store()
            store["profiles"][str(p_idx)] = {
                "name": f"Config {p_idx}",
                "config": json.loads(json.dumps(cfg))
            }
            # Ghi an toàn vào PROFILE_FILE
            tmp_path = PROFILE_FILE.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(store, indent=4, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(PROFILE_FILE)

            # Nếu là Config 1, đồng bộ luôn autotrain_megamu_config.json
            if p_idx == 1:
                tmp_def = DEFAULT_CONFIG_FILE.with_suffix(".tmp")
                tmp_def.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_def.replace(DEFAULT_CONFIG_FILE)

    @classmethod
    def load_slot_assignments(cls, min_slots: int = 10) -> Dict[int, int]:
        """
        Đọc cấu hình gán từng dòng Slot từ slot_assignments.json.
        Tự động mở rộng nếu file chứa nhiều hơn min_slots tài khoản.
        """
        with cls._lock:
            assignments = {}
            if SLOT_ASSIGNMENTS_FILE.exists():
                try:
                    data = json.loads(SLOT_ASSIGNMENTS_FILE.read_text(encoding="utf-8"))
                    slots_data = data.get("slots", {})
                    for s_str, conf in slots_data.items():
                        try:
                            s_int = int(s_str)
                            p_val = int(conf.get("profile", 1))
                            if s_int >= 1 and 1 <= p_val <= 10:
                                assignments[s_int] = p_val
                        except Exception:
                            pass
                except Exception:
                    pass

            target_count = max(len(assignments), min_slots)
            for s in range(1, target_count + 1):
                if s not in assignments:
                    assignments[s] = 1 if s <= 5 else (2 if s <= 10 else 1)

            if not SLOT_ASSIGNMENTS_FILE.exists() or len(assignments) > len(slots_data if 'slots_data' in locals() else {}):
                cls.save_all_slot_assignments(assignments)
            return assignments

    @classmethod
    def save_slot_assignment(cls, slot_idx: int, profile_idx: int):
        """Ghi ngay lập tức gán Config của dòng slot_idx vào file."""
        with cls._lock:
            current = cls.load_slot_assignments()
            current[slot_idx] = max(1, min(10, int(profile_idx)))
            cls._write_slot_file(current)

    @classmethod
    def save_all_slot_assignments(cls, assignments: Dict[int, int]):
        with cls._lock:
            cls._write_slot_file(assignments)

    @classmethod
    def _write_slot_file(cls, assignments: Dict[int, int]):
        data = {
            "version": 1,
            "description": "Lưu trữ lựa chọn cấu hình Config 1..10 cho từng Slot",
            "slots": {str(k): {"profile": v} for k, v in sorted(assignments.items(), key=lambda x: int(x[0]))}
        }
        tmp_slot = SLOT_ASSIGNMENTS_FILE.with_suffix(".tmp")
        tmp_slot.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_slot.replace(SLOT_ASSIGNMENTS_FILE)


# ==============================================================================
# CONTROLLER QUẢN LÝ TỪNG DÒNG TÀI KHOẢN (SLOT CONTROLLER)
# ==============================================================================
class SlotController:
    """Điều khiển logic và trạng thái của từng dòng trong danh sách 10 tài khoản."""

    def __init__(self, slot_idx: int, app: 'DashboardApp', default_profile: int = 1):
        self.slot_idx = slot_idx
        self.app = app
        self.profile_index = default_profile

        self.assigned_pid: Optional[int] = None
        self.char_name = "---"
        self.level = "---"
        self.coords = "--,--"
        self.status = tr("idle")
        self.auto_requested = False

        self.engine: Optional[MegDirectEngine] = None
        self.worker: Optional[AutoTrainWorker] = None
        self.last_sync_time = 0.0

    def set_profile(self, profile_idx: int):
        """Thay đổi Profile và lưu ngay vào file JSON."""
        old_idx = self.profile_index
        self.profile_index = max(1, min(10, int(profile_idx)))
        ConfigPersistenceManager.save_slot_assignment(self.slot_idx, self.profile_index)

        # Nếu đang chạy Auto, nạp config mới từ file và update worker trực tiếp
        if self.worker and self.worker.running:
            cfg = ConfigPersistenceManager.load_single_profile(self.profile_index)
            if hasattr(self.worker, 'update_config'):
                self.worker.update_config(cfg)
            self.app.log_message(
                f"[Slot {self.slot_idx:02d}] Chuyển cấu hình trực tiếp: C{old_idx} -> C{self.profile_index}. Re-routing ngay!",
                "SUCCESS"
            )
            self.set_status(tr("running", n=self.profile_index))

    def attach_pid(self, pid: int):
        """Kết nối tới Game PID."""
        self.assigned_pid = pid
        if MegDirectEngine:
            self.engine = MegDirectEngine.get_engine(pid)
            if not self.engine.is_ready:
                ok = self.engine.attach()
                if ok:
                    self.set_status(tr("connected_status"))
                    self.app.log_message(f"[Slot {self.slot_idx:02d}] Kết nối thành công MEGAMU (PID {pid}).", "SUCCESS")
                else:
                    self.set_status(tr("idle"))
                    self.app.log_message(f"[Slot {self.slot_idx:02d}] Kết nối thất bại MEGAMU (PID {pid}).", "ERROR")
            else:
                self.set_status(tr("connected_status"))
        else:
            self.set_status(tr("connected_status"))

    def detach(self):
        """Ngắt kết nối."""
        self.stop_auto()
        self.assigned_pid = None
        self.char_name = "---"
        self.level = "---"
        self.coords = "--,--"
        self.set_status(tr("idle"))
        self.engine = None

    def start_auto(self) -> bool:
        if license_client and not license_client.is_license_valid():
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Không thể chạy: Bản quyền chưa kích hoạt hoặc đã hết hạn!", "ERROR")
            self.set_auto(False)
            return False

        if not self.assigned_pid:
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Chưa chọn Game MEGAMU!", "WARNING")
            self.set_auto(False)
            return False

        if not psutil.pid_exists(self.assigned_pid):
            self.set_status(tr("game_closed"))
            self.set_auto(False)
            return False

        # Đọc cấu hình tươi mới 100% từ file đĩa JSON!
        cfg = ConfigPersistenceManager.load_single_profile(self.profile_index)
        stages = cfg.get("stages", [])
        if not stages:
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Config {self.profile_index} chưa thiết lập chặng!", "ERROR")
            self.set_auto(False)
            return False

        self.app.log_message(
            f"[Slot {self.slot_idx:02d}] BẬT AUTO C{self.profile_index}: Tải {len(stages)} chặng từ file đĩa.",
            "SUCCESS"
        )

        def worker_log(msg, lvl="INFO"):
            self.app.log_message(f"[Slot {self.slot_idx:02d}] {msg}", lvl)

        def worker_progress(st, _):
            self.set_status(st)

        self.worker = AutoTrainWorker(
            pid=self.assigned_pid,
            stages=stages,
            log_callback=worker_log,
            progress_callback=worker_progress,
            config=cfg,
            slot_idx=self.slot_idx
        )
        self.worker.start()
        self.auto_requested = True
        self.set_auto(True)
        self.set_status(tr("running", n=self.profile_index))
        return True

    def stop_auto(self):
        worker = self.worker
        self.worker = None
        if worker:
            try:
                worker.stop()
            except Exception:
                pass
        elif self.engine and self.engine.is_ready:
            try:
                self.engine.stop_helper()
                self.engine.cancel_move()
            except Exception:
                pass

        self.auto_requested = False
        self.set_auto(False)
        self.app.log_message(
            f"[Slot {self.slot_idx:02d}] TẮT AUTO: Đã dừng auto, nhân vật đứng yên tại vị trí hiện tại, MuHelper đã TẮT.",
            "INFO"
        )
        if self.assigned_pid and psutil.pid_exists(self.assigned_pid):
            self.set_status(tr("connected_status"))
        else:
            self.set_status(tr("idle"))

    def toggle_auto(self):
        if self.auto_requested:
            self.stop_auto()
        else:
            self.start_auto()

    def set_status(self, text: str):
        self.status = text
        self.app.update_slot_ui_status(self.slot_idx, text)

    def set_auto(self, is_on: bool):
        self.auto_requested = is_on
        self.app.update_slot_ui_auto(self.slot_idx, is_on)

    def sync_telemetry(self):
        """Đọc RAM thông tin nhân vật hiển thị lên bảng."""
        if not self.assigned_pid or not psutil.pid_exists(self.assigned_pid):
            if self.assigned_pid:
                self.set_status(tr("game_closed"))
                self.char_name = "---"
                self.level = "---"
                self.coords = "--,--"
                self.stop_auto()
            return

        if self.engine and self.engine.is_ready:
            try:
                p_info = self.engine.get_player_info()
                if p_info:
                    p_name = p_info.get("name", "")
                    p_lvl = p_info.get("level", 0)
                    px = p_info.get("tileX", p_info.get("x", 0))
                    py = p_info.get("tileY", p_info.get("y", 0))

                    if p_name:
                        self.char_name = p_name
                    if p_lvl > 0:
                        self.level = str(p_lvl)
                    self.coords = f"{px},{py}"
                    self.app.update_slot_ui_telemetry(self.slot_idx, self.char_name, self.level, self.coords)
            except Exception:
                pass


# ==============================================================================
# GIAO DIỆN CHÍNH (MEGAMU AUTO TRAIN DASHBOARD)
# ==============================================================================
class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Khởi tạo ngôn ngữ từ tệp ui_settings.json
        load_language_preference()

        # Cấu hình cửa sổ
        self.title(APP_NAME)
        self.geometry("1120x680")
        self.minsize(1050, 600)
        self.configure(fg_color="#0e1117")

        # Đặt App ID cho Windows để hiển thị icon DAuto trên Taskbar thay vì icon Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dauto.megamu.dashboard.v1")
        except Exception:
            pass

        # Đặt Icon cho cửa sổ và Taskbar
        self._apply_window_icon()
        self.after(250, self._apply_window_icon)

        # Quản lý danh sách Map
        self.map_resolver = MapResolver.get_instance() if MapResolver else None
        self.map_list = self._get_map_display_list()

        # Quản lý Slot và đọc trực tiếp cấu hình gán từ file JSON
        self.slot_assignments = ConfigPersistenceManager.load_slot_assignments(DEFAULT_SLOTS)
        self.controllers: List[SlotController] = []
        for i in sorted(self.slot_assignments.keys()):
            assigned_c = self.slot_assignments.get(i, 1 if i <= 5 else 2)
            self.controllers.append(SlotController(i, self, default_profile=assigned_c))

        # Bộ nhớ tiến trình
        self.detected_games: Dict[int, str] = {}
        self.active_tab = "accounts"  # 'accounts', 'profiles', 'logs'
        self.logs_data: List[Tuple[str, str, str]] = [] # [(time, slot, text)]

        # Thành phần UI lưu trữ
        self.slot_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.editor_rows: List[Dict[str, Any]] = []

        # Xây dựng giao diện hoàn chỉnh
        self.build_ui()
        self.update_header_stats()

        # Bắt đầu vòng lặp quét tiến trình & telemetry
        self.running = True
        self.after(500, self._periodic_game_scan)
        self.after(800, self._periodic_telemetry)
        threading.Thread(target=self._verify_license_async, daemon=True).start()

        # Xử lý đóng ứng dụng an toàn
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_map_display_list(self) -> List[str]:
        maps = []
        candidate_paths = [
            MAP_COMMANDS_FILE,
            BASE_DIR / "config" / "map_commands.json",
            BASE_DIR / "map_commands.json",
            Path(r"C:\Users\donpv\Downloads\MEGAMU Auto Train Dashboad\config\map_commands.json")
        ]
        for p in candidate_paths:
            if p and p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    for m in d.get("maps", []):
                        name = str(m.get("name", "")).strip()
                        if name and name not in maps:
                            maps.append(name)
                    if maps:
                        break
                except Exception:
                    pass
        if not maps:
            maps = ["Lorencia", "Noria", "Devias", "Dungeon 2", "Lost Tower 5", "Aida 1", "Icarus", "Kanturu 1"]
        return maps

    def build_ui(self):
        """Dựng giao diện đồng bộ 100% với ảnh thiết kế."""
        ctk.set_appearance_mode("Dark")

        # ----------------------------------------------------------------------
        # 1. HEADER CHÍNH
        # ----------------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, fg_color="#12151e", height=58, corner_radius=0)
        self.header_frame.pack(fill="x", padx=0, pady=0)

        inner_header = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        inner_header.pack(fill="both", expand=True, padx=20, pady=(8, 8))

        # Cột Trái: Logo + Tên + Thông số bản quyền
        left_box = ctk.CTkFrame(inner_header, fg_color="transparent")
        left_box.pack(side="left", fill="y")

        # Logo
        if LOGO_FILE.exists():
            try:
                logo_img = Image.open(str(LOGO_FILE))
                lw, lh = logo_img.size
                aspect = lw / max(1, lh)
                target_h = 38
                target_w = int(target_h * aspect)
                self.logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(target_w, target_h))
                logo_label = ctk.CTkLabel(left_box, image=self.logo_ctk, text="")
                logo_label.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ctk.CTkFrame(left_box, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        title_line = ctk.CTkFrame(title_box, fg_color="transparent")
        title_line.pack(anchor="w")

        title_lbl = ctk.CTkLabel(
            title_line,
            text=APP_NAME,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f8fafc"
        )
        title_lbl.pack(side="left")

        ver_lbl = ctk.CTkLabel(
            title_line,
            text=f" {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        ver_lbl.pack(side="left", padx=(4, 0))

        # Dòng thống kê Header (có thể bấm vào để mở kích hoạt bản quyền)
        self.header_stats_lbl = ctk.CTkLabel(
            title_box,
            text=f"Game: 0 | Đã kết nối: 0/0 | Auto: 0 | Bản quyền: {CURRENT_LICENSE}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8",
            cursor="hand2"
        )
        self.header_stats_lbl.pack(anchor="w", pady=(1, 0))
        self.header_stats_lbl.bind("<Button-1>", lambda e: self.open_license_dialog())

        # Cột Phải: Nút Help (?) + Badge B&T business
        right_box = ctk.CTkFrame(inner_header, fg_color="transparent")
        right_box.pack(side="right", fill="y")

        # Badge B&T business (Circular badge with teal border)
        badge_frame = ctk.CTkFrame(
            right_box,
            width=42,
            height=42,
            corner_radius=21,
            fg_color="#12151e",
            border_width=1.5,
            border_color="#14b8a6"
        )
        badge_frame.pack(side="right", padx=(10, 0))
        badge_frame.pack_propagate(False)

        badge_inner = ctk.CTkFrame(badge_frame, fg_color="transparent")
        badge_inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            badge_inner,
            text="donpv",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#2dd4bf"
        ).pack(anchor="center", pady=(0, 0))

        ctk.CTkLabel(
            badge_inner,
            text="developer",
            font=ctk.CTkFont(family="Segoe UI", size=7),
            text_color="#94a3b8"
        ).pack(anchor="center", pady=(0, 0))

        # Nút Help (?)
        self.btn_help = ctk.CTkButton(
            right_box,
            text="?",
            width=28,
            height=28,
            corner_radius=14,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2c3345",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94a3b8",
            command=self.show_help
        )
        self.btn_help.pack(side="right", padx=(0, 6))

        # Nút License (🔑)
        self.btn_license = ctk.CTkButton(
            right_box,
            text="🔑 License",
            width=80,
            height=28,
            corner_radius=6,
            fg_color="#181c26",
            hover_color="#242b3a",
            border_width=1,
            border_color="#0284c7",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#38bdf8",
            command=self.open_license_dialog
        )
        self.btn_license.pack(side="right", padx=(0, 6))

        # Language dropdown trên Header (hiển thị trên mọi Tab)
        self.lang_var = ctk.StringVar(value=f"Language: {CURRENT_LANG.upper()}")
        self.lang_menu = ModernOptionMenu(
            right_box,
            values=["Language: VI", "Language: EN", "Language: PT-BR"],
            variable=self.lang_var,
            width=125,
            height=30,
            fg_color="#181c26",
            hover_color="#222736",
            command=self.change_language,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.lang_menu.pack(side="right", padx=(0, 6))

        # ----------------------------------------------------------------------
        # 2. TAB NAVIGATION BAR (Characters | Configuration | Logs | Text config)
        # ----------------------------------------------------------------------
        tab_bar_frame = ctk.CTkFrame(self, fg_color="#12151e", height=38, corner_radius=0)
        tab_bar_frame.pack(fill="x", padx=0, pady=(0, 2))

        tab_bar_inner = ctk.CTkFrame(tab_bar_frame, fg_color="transparent")
        tab_bar_inner.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        tab_left = ctk.CTkFrame(tab_bar_inner, fg_color="transparent")
        tab_left.pack(side="left", fill="y")

        self.tab_accounts_btn = ctk.CTkButton(
            tab_left,
            image=UiIconFactory.get("user", color="#2dd4bf", size=(14, 14)),
            compound="left",
            text=f" {tr('characters')} ({len(self.controllers)})",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self.switch_tab("accounts")
        )
        self.tab_accounts_btn.pack(side="left", padx=(0, 6))

        self.tab_profiles_btn = ctk.CTkButton(
            tab_left,
            image=UiIconFactory.get("gear", color="#94a3b8", size=(14, 14)),
            compound="left",
            text=f" {tr('configuration')}",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self.switch_tab("profiles")
        )
        self.tab_profiles_btn.pack(side="left", padx=(0, 6))

        self.tab_logs_btn = ctk.CTkButton(
            tab_left,
            image=UiIconFactory.get("file", color="#94a3b8", size=(14, 14)),
            compound="left",
            text=f" {tr('logs')}",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self.switch_tab("logs")
        )
        self.tab_logs_btn.pack(side="left", padx=(0, 6))

        tab_right = ctk.CTkFrame(tab_bar_inner, fg_color="transparent")
        tab_right.pack(side="right", fill="y")

        self.btn_text_cfg = ctk.CTkButton(
            tab_right,
            text=tr("text_config"),
            width=80,
            height=26,
            fg_color="transparent",
            hover_color="#1a1e28",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.open_text_config
        )
        self.btn_text_cfg.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            tab_right,
            text="Phát triển bởi donpv",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#64748b"
        ).pack(side="left")

        # ----------------------------------------------------------------------
        # 3. ACTION TOOLBAR (Connect All | Gán Team 5 | Refresh | Add | Remove | Language)
        # ----------------------------------------------------------------------
        self.toolbar_frame = ctk.CTkFrame(self, fg_color="#0e1117", height=44)
        self.toolbar_frame.pack(fill="x", padx=20, pady=(6, 8))

        btn_bar_style = {
            "font": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "fg_color": "#181c26",
            "hover_color": "#242b3a",
            "border_width": 1,
            "border_color": "#2c3345",
            "text_color": "#f1f5f9",
            "corner_radius": 6,
            "height": 32
        }

        # Trái
        t_left = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        t_left.pack(side="left")

        self.btn_connect_all = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("link", color="#38bdf8", size=(14, 14)),
            compound="left",
            text=f" {tr('connect_all')}",
            width=120,
            command=self.connect_all,
            **btn_bar_style
        )
        self.btn_connect_all.pack(side="left", padx=(0, 6))

        self.btn_team5 = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("gear", color="#cbd5e1", size=(14, 14)),
            compound="left",
            text=f" {tr('assign_team5')}",
            width=125,
            command=self.assign_team5,
            **btn_bar_style
        )
        self.btn_team5.pack(side="left", padx=(0, 6))

        self.btn_refresh = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(14, 14)),
            compound="left",
            text=f" {tr('refresh_games')}",
            width=130,
            command=self.refresh_games,
            **btn_bar_style
        )
        self.btn_refresh.pack(side="left", padx=(0, 6))

        self.btn_add_slot = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("plus", color="#4ade80", size=(13, 13)),
            compound="left",
            text=f" {tr('add')}",
            width=78,
            command=self.add_new_slot,
            **btn_bar_style
        )
        self.btn_add_slot.pack(side="left", padx=(0, 6))

        self.btn_remove_slot = ctk.CTkButton(
            t_left,
            image=UiIconFactory.get("minus", color="#f87171", size=(13, 13)),
            compound="left",
            text=f" {tr('remove')}",
            width=95,
            command=self.remove_last_slot,
            **btn_bar_style
        )
        self.btn_remove_slot.pack(side="left")



        # ----------------------------------------------------------------------
        # 4. CONTENT CONTAINER
        # ----------------------------------------------------------------------
        self.content_container = ctk.CTkFrame(self, fg_color="#0e1117")
        self.content_container.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        # 3 Panels cho 3 Tab
        self.panel_accounts = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=8)
        self.panel_profiles = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=8)
        self.panel_logs = ctk.CTkFrame(self.content_container, fg_color="#13161f", border_width=1, border_color="#202430", corner_radius=8)

        self.build_accounts_view()
        self.build_profiles_view()
        self.build_logs_view()

        # ----------------------------------------------------------------------
        # 5. FOOTER STATUS BAR
        # ----------------------------------------------------------------------
        self.footer_frame = ctk.CTkFrame(self, fg_color="#0e1117", height=28)
        self.footer_frame.pack(fill="x", padx=20, pady=(0, 6))

        self.footer_stats_lbl = ctk.CTkLabel(
            self.footer_frame,
            text=f"Total: {len(self.controllers)} Accounts | Connected: 0 | Running: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        self.footer_stats_lbl.pack(side="left")

        footer_right = ctk.CTkLabel(
            self.footer_frame,
            text="(?) Help | Phát triển bởi donpv",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748b"
        )
        footer_right.pack(side="right")

        # Đồng bộ danh sách Slot vào combobox và nhãn điều khiển
        self.update_combo_slot_options()

        # Mặc định hiển thị tab accounts
        self.switch_tab("accounts")

    # ==========================================================================
    # TAB 1: DANH SÁCH TÀI KHOẢN (ACCOUNTS TAB)
    # ==========================================================================
    def build_accounts_view(self):
        # Header bảng cố định ở trên
        tbl_header = ctk.CTkFrame(self.panel_accounts, fg_color="transparent", height=32)
        tbl_header.pack(fill="x", padx=12, pady=(10, 4))

        self.col_header_labels = []
        col_defs = [
            ("col_no", 45, "w"),
            ("col_char_pid", 230, "w"),
            ("col_route_preset", 220, "w"),
            ("col_coordinates", 160, "center"),
            ("col_status", 130, "center"),
            ("col_actions", 120, "center")
        ]

        for k, w, anc in col_defs:
            lbl = ctk.CTkLabel(
                tbl_header,
                text=tr(k),
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#94a3b8"
            )
            lbl.pack(side="left", padx=4)
            self.col_header_labels.append(lbl)

        # Divider line
        div = ctk.CTkFrame(self.panel_accounts, fg_color="#1f2535", height=1)
        div.pack(fill="x", padx=12, pady=(0, 6))

        # Khung cuộn chứa danh sách các dòng tài khoản
        self.accounts_scroll_frame = ctk.CTkScrollableFrame(
            self.panel_accounts,
            fg_color="transparent"
        )
        self.accounts_scroll_frame.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        # Tạo từng dòng tài khoản đã cấu hình
        for i in range(1, len(self.controllers) + 1):
            self.create_slot_row(i)

    def create_slot_row(self, i: int):
        """Tạo 1 dòng giao diện cho Slot thứ i theo đúng ảnh thiết kế."""
        ctrl = self.controllers[i - 1]
        row_frame = ctk.CTkFrame(self.accounts_scroll_frame, fg_color="#141722", height=54, corner_radius=6)
        row_frame.pack(fill="x", padx=4, pady=3)

        # Cột 1: No. (01, 02...)
        slot_lbl = ctk.CTkLabel(
            row_frame,
            text=f"{i:02d}",
            width=45,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94a3b8"
        )
        slot_lbl.pack(side="left", padx=(10, 4))

        # Cột 2: Character/PID
        options = ["--"]
        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
            options.append(disp)

        init_proc = "--"
        if ctrl.assigned_pid:
            t = self.detected_games.get(ctrl.assigned_pid, "")
            cname = character_name_from_window_title(t)
            init_proc = f"{cname} ({ctrl.assigned_pid})" if cname else f"MEGAMU ({ctrl.assigned_pid})"

        proc_var = ctk.StringVar(value=init_proc)
        proc_combo = ModernOptionMenu(
            row_frame,
            values=options,
            variable=proc_var,
            width=220,
            height=32,
            fg_color="#181c26",
            border_color="#242b3a",
            hover_color="#222736",
            command=lambda val, s=i: self.on_slot_pid_selected(s, val),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        proc_combo.pack(side="left", padx=4)

        # Cột 3: Target Route Preset (Multi-tier: Master LV 450 / Progress / EXP)
        route_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=220)
        route_box.pack(side="left", padx=4)

        top_line = ctk.CTkFrame(route_box, fg_color="transparent")
        top_line.pack(fill="x", padx=0, pady=(2, 0))

        profile_var = ctk.StringVar(value=f"Config {ctrl.profile_index}")
        preset_combo = ModernOptionMenu(
            top_line,
            values=PROFILE_NAMES,
            variable=profile_var,
            width=105,
            height=24,
            fg_color="#181c26",
            hover_color="#222736",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda val, s=i: self.on_slot_profile_selected(s, val)
        )
        preset_combo.pack(side="left")

        lvl_str = f"LV {ctrl.level}" if ctrl.level != "---" else "LV --"
        lvl_lbl = ctk.CTkLabel(
            top_line,
            text=lvl_str,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        lvl_lbl.pack(side="right")

        prog_bar = ctk.CTkProgressBar(
            route_box,
            width=210,
            height=5,
            corner_radius=2,
            fg_color="#232836",
            progress_color="#38bdf8"
        )
        prog_bar.set(0.0)
        prog_bar.pack(anchor="w", pady=(2, 1))

        exp_lbl = ctk.CTkLabel(
            route_box,
            text="-- / -- EXP",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#71717a",
            anchor="w"
        )
        exp_lbl.pack(anchor="w", pady=(0, 2))

        # Cột 4: Coordinates (Rounded container with coordinates and dropdown arrow)
        coords_frame = ctk.CTkFrame(
            row_frame,
            fg_color="#181c26",
            border_width=0,
            corner_radius=6,
            width=140,
            height=30
        )
        coords_frame.pack(side="left", padx=6)
        coords_frame.pack_propagate(False)

        coords_lbl = ctk.CTkLabel(
            coords_frame,
            text="--, --",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f1f5f9"
        )
        coords_lbl.pack(side="left", padx=(10, 0), expand=True)

        ctk.CTkLabel(
            coords_frame,
            text="",
            image=UiIconFactory.get("chevron_down", color="#64748b", size=(10, 10))
        ).pack(side="right", padx=(0, 8))

        # Cột 5: Status (Text mặc định, không border-radius)
        status_lbl = ctk.CTkLabel(
            row_frame,
            text="Idle",
            width=120,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94a3b8"
        )
        status_lbl.pack(side="left", padx=6)

        # Cột 6: Actions (Play/Stop | Configure | Slot Logs)
        actions_box = ctk.CTkFrame(row_frame, fg_color="transparent")
        actions_box.pack(side="left", padx=4)

        act_btn_style = {
            "width": 28,
            "height": 28,
            "corner_radius": 5,
            "fg_color": "#181c26",
            "hover_color": "#242b3a",
            "border_width": 1,
            "border_color": "#2b3244"
        }

        btn_toggle = ctk.CTkButton(
            actions_box,
            text="",
            image=UiIconFactory.get("play", color="#38bdf8", size=(11, 11)),
            command=lambda s=i: self.on_slot_auto_toggle(s),
            **act_btn_style
        )
        btn_toggle.pack(side="left", padx=2)

        btn_cfg = ctk.CTkButton(
            actions_box,
            text="",
            image=UiIconFactory.get("gear", color="#94a3b8", size=(13, 13)),
            command=lambda s=i: self.jump_to_config_tab(s),
            **act_btn_style
        )
        btn_cfg.pack(side="left", padx=2)

        btn_log = ctk.CTkButton(
            actions_box,
            text="",
            image=UiIconFactory.get("file", color="#94a3b8", size=(13, 13)),
            command=lambda s=i: self.jump_to_slot_logs(s),
            **act_btn_style
        )
        btn_log.pack(side="left", padx=2)

        # Lưu references để cập nhật
        self.slot_ui_elements[i] = {
            "row_frame": row_frame,
            "proc_var": proc_var,
            "proc_combo": proc_combo,
            "profile_var": profile_var,
            "preset_combo": preset_combo,
            "preset_lbl": preset_combo,
            "lvl_lbl": lvl_lbl,
            "prog_bar": prog_bar,
            "exp_lbl": exp_lbl,
            "coords_lbl": coords_lbl,
            "status_lbl": status_lbl,
            "btn_toggle": btn_toggle,
            "btn_cfg": btn_cfg,
            "btn_log": btn_log
        }

    def add_new_slot(self):
        """Thêm 1 slot tài khoản mới vào cuối danh sách."""
        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng thêm tài khoản đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        new_slot_idx = len(self.controllers) + 1
        lic_data = license_client.load_license_data() if license_client else {}
        max_allowed = lic_data.get("max_slots", MAX_SLOTS)
        if new_slot_idx > max_allowed or new_slot_idx > MAX_SLOTS:
            self.log_message(f"Bản quyền hiện tại chỉ cho phép tối đa {max_allowed} tài khoản.", "WARNING")
            try:
                from tkinter import messagebox
                messagebox.showinfo(
                    "Giới Hạn Bản Quyền",
                    f"Gói bản quyền của bạn cho phép tối đa {max_allowed} tài khoản.\nVui lòng liên hệ để nâng cấp thêm slot."
                )
            except Exception:
                pass
            return

        default_profile = 1
        self.slot_assignments[new_slot_idx] = default_profile
        ConfigPersistenceManager.save_slot_assignment(new_slot_idx, default_profile)

        ctrl = SlotController(new_slot_idx, self, default_profile=default_profile)
        self.controllers.append(ctrl)

        self.create_slot_row(new_slot_idx)
        self.update_combo_slot_options()
        self.update_header_stats()
        self.log_message(f"Đã thêm Account Slot #{new_slot_idx:02d} thành công.", "SUCCESS")

    def remove_last_slot(self):
        """Xóa slot tài khoản cuối cùng."""
        if len(self.controllers) <= 1:
            self.log_message("Không thể xóa: Cần giữ lại ít nhất 1 tài khoản.", "WARNING")
            return

        last_idx = len(self.controllers)
        ctrl = self.controllers[-1]

        # Dừng auto và ngắt kết nối an toàn nếu đang chạy
        if ctrl.worker and ctrl.worker.running:
            ctrl.stop_auto()
        if ctrl.engine:
            try:
                ctrl.engine.detach()
            except Exception:
                pass

        # Xóa UI row
        el = self.slot_ui_elements.pop(last_idx, None)
        if el and el.get("row_frame"):
            try:
                el["row_frame"].destroy()
            except Exception:
                pass

        self.controllers.pop()
        self.slot_assignments.pop(last_idx, None)
        ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)

        self.update_combo_slot_options()
        self.update_header_stats()
        self.log_message(f"Đã xóa Account Slot #{last_idx:02d}.", "INFO")

    def update_combo_slot_options(self):
        """Cập nhật số lượng tài khoản trên tab bar và footer."""
        n = len(self.controllers)
        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({n})")
        if hasattr(self, "footer_stats_lbl"):
            num_conn = sum(1 for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid))
            num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
            self.footer_stats_lbl.configure(text=tr("footer_stats", slots=n, conn=num_conn, auto=num_auto))

    def jump_to_slot_logs(self, slot_idx: int):
        """Nhảy nhanh sang Tab Logs khi bấm nút 📄 ở Slot."""
        if hasattr(self, "log_filter_var"):
            self.log_filter_var.set(f"{slot_idx:02d}")
        self.switch_tab("logs")
        self.render_logs()

    def open_text_config(self):
        """Mở thư mục cấu hình."""
        try:
            import subprocess
            if CONFIG_DIR.exists():
                subprocess.Popen(f'explorer "{CONFIG_DIR}"')
        except Exception:
            pass

    def show_help(self):
        """Hiển thị hộp thoại trợ giúp."""
        try:
            from tkinter import messagebox
            messagebox.showinfo(
                "MEGAMU Auto Train Dashboard",
                "MEGAMU Auto Train Dashboard v1.5.1\n\n"
                "- Kết nối native không chiếm chuột (Zero-Mouse Direct Engine)\n"
                "- Tự động tìm đường A*, di chuyển, bật/tắt MuHelper và nhận diện Reset\n"
                "- Hỗ trợ đa tài khoản không giới hạn\n\n"
                "Phát triển bởi donpv\n\n"
                "Bản quyền: Bấm nút '🔑 License' trên thanh tiêu đề để kích hoạt bản quyền."
            )
        except Exception:
            pass

    def _verify_license_async(self):
        """Kiểm tra xác thực bản quyền định kỳ ngầm (Heartbeat) với Server."""
        if not getattr(self, "running", True) or not license_client:
            return
        try:
            license_client.verify_license()
            self.after(0, self.update_header_stats)
        except Exception:
            pass
        try:
            self.after(5000, lambda: threading.Thread(target=self._verify_license_async, daemon=True).start())
        except Exception:
            pass

    def open_license_dialog(self):
        """Mở cửa sổ quản lý và kích hoạt bản quyền MEGAMU Auto Train Dashboard."""
        if hasattr(self, "_license_dialog") and self._license_dialog is not None and self._license_dialog.winfo_exists():
            self._license_dialog.lift()
            self._license_dialog.focus_force()
            return

        dialog = ctk.CTkToplevel(self)
        self._license_dialog = dialog
        dialog.title("Quản lý Bản Quyền - MEGAMU Auto Train")
        dialog.geometry("490x440")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#0e1117")
        dialog.transient(self)
        dialog.grab_set()

        # Đặt Icon ứng dụng cho cửa sổ dialog quản lý bản quyền
        if ICON_FILE.exists():
            try:
                dialog.iconbitmap(str(ICON_FILE))
            except Exception:
                pass
            try:
                dialog.wm_iconbitmap(str(ICON_FILE))
            except Exception:
                pass
            try:
                from PIL import ImageTk
                _ico_img = Image.open(str(ICON_FILE))
                dialog._tk_icon = ImageTk.PhotoImage(_ico_img)
                dialog.iconphoto(False, dialog._tk_icon)
            except Exception:
                pass

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 245
            y = self.winfo_y() + (self.winfo_height() // 2) - 220
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

        pad = ctk.CTkFrame(dialog, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=18)

        # Header với Logo ứng dụng chính thức
        head_box = ctk.CTkFrame(pad, fg_color="transparent")
        head_box.pack(fill="x", pady=(0, 12))

        if LOGO_FILE.exists():
            try:
                logo_img = Image.open(str(LOGO_FILE))
                lw, lh = logo_img.size
                aspect = lw / max(1, lh)
                target_h = 36
                target_w = int(target_h * aspect)
                self._lic_dialog_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(target_w, target_h))
                ctk.CTkLabel(head_box, image=self._lic_dialog_logo, text="").pack(side="left", padx=(0, 12))
            except Exception:
                pass
        elif ICON_FILE.exists():
            try:
                ico_img = Image.open(str(ICON_FILE))
                self._lic_dialog_logo = ctk.CTkImage(light_image=ico_img, dark_image=ico_img, size=(36, 36))
                ctk.CTkLabel(head_box, image=self._lic_dialog_logo, text="").pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_text_box = ctk.CTkFrame(head_box, fg_color="transparent")
        title_text_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            title_text_box,
            text="QUẢN LÝ BẢN QUYỀN SẢN PHẨM",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f8fafc"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_text_box,
            text="Hệ thống xác thực bản quyền & HWID định danh máy tính",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748b"
        ).pack(anchor="w", pady=(1, 0))

        # HWID Card
        hwid_card = ctk.CTkFrame(pad, fg_color="#161b26", corner_radius=8, border_width=1, border_color="#232936")
        hwid_card.pack(fill="x", pady=(0, 10))

        hwid_inner = ctk.CTkFrame(hwid_card, fg_color="transparent")
        hwid_inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            hwid_inner,
            text="MÃ ĐỊNH DANH MÁY (HWID):",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(anchor="w")

        hwid_row = ctk.CTkFrame(hwid_inner, fg_color="transparent")
        hwid_row.pack(fill="x", pady=(3, 0))

        hwid_val = license_client.get_machine_hwid() if license_client else "N/A"
        hwid_lbl = ctk.CTkLabel(
            hwid_row,
            text=hwid_val,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        hwid_lbl.pack(side="left")

        def copy_hwid():
            self.clipboard_clear()
            self.clipboard_append(hwid_val)
            copy_btn.configure(text="Đã chép!", fg_color="#16a34a")
            self.after(1500, lambda: copy_btn.configure(text="Sao chép", fg_color="#242b3a"))

        copy_btn = ctk.CTkButton(
            hwid_row,
            text="Sao chép",
            width=70,
            height=24,
            corner_radius=4,
            fg_color="#242b3a",
            hover_color="#333c52",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#e2e8f0",
            command=copy_hwid
        )
        copy_btn.pack(side="right")

        # Current Status Card
        lic_data = license_client.load_license_data() if license_client else {}
        status_card = ctk.CTkFrame(pad, fg_color="#161b26", corner_radius=8, border_width=1, border_color="#232936")
        status_card.pack(fill="x", pady=(0, 12))

        status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        status_inner.pack(fill="x", padx=12, pady=8)

        plan_type = lic_data.get("plan_type", "Chưa kích hoạt")
        exp_date = lic_data.get("expires_at", "--")
        if exp_date and exp_date != "--":
            exp_date = str(exp_date).split(" ")[0]
        is_active = bool(lic_data.get("license_key"))

        stat_title = "Trạng thái: " + ("ĐÃ KÍCH HOẠT" if is_active else "CHƯA KÍCH HOẠT")
        stat_color = "#4ade80" if is_active else "#f87171"

        status_lbl = ctk.CTkLabel(
            status_inner,
            text=stat_title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=stat_color
        )
        status_lbl.pack(anchor="w")

        details_lbl = ctk.CTkLabel(
            status_inner,
            text=f"Gói dịch vụ: {plan_type}   |   Hạn dùng: {exp_date}   |   Slot tối đa: {lic_data.get('max_slots', 50)}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#94a3b8"
        )
        details_lbl.pack(anchor="w", pady=(2, 0))

        # Input License Key
        ctk.CTkLabel(
            pad,
            text="NHẬP KEY BẢN QUYỀN MỚI:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(anchor="w", pady=(0, 4))

        key_entry = ctk.CTkEntry(
            pad,
            placeholder_text="Ví dụ: MEG-DONPV-2026-VIP1",
            height=34,
            corner_radius=6,
            fg_color="#181c26",
            border_color="#2c3345",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#f8fafc"
        )
        key_entry.pack(fill="x", pady=(0, 6))
        if lic_data.get("license_key"):
            key_entry.insert(0, lic_data.get("license_key"))

        msg_lbl = ctk.CTkLabel(pad, text="", font=ctk.CTkFont(family="Segoe UI", size=10))
        msg_lbl.pack(anchor="w", pady=(0, 4))

        # Action Buttons
        btn_box = ctk.CTkFrame(pad, fg_color="transparent")
        btn_box.pack(fill="x", pady=(4, 0))

        def do_activate():
            input_key = key_entry.get().strip()
            if not input_key:
                msg_lbl.configure(text="Vui lòng nhập mã key bản quyền!", text_color="#f87171")
                return

            act_btn.configure(state="disabled", text="Đang kích hoạt...")
            msg_lbl.configure(text="Đang kết nối tới máy chủ...", text_color="#94a3b8")
            dialog.update_idletasks()

            def _run():
                success, msg, info = license_client.activate_license(input_key)
                def _done():
                    act_btn.configure(state="normal", text="Kích Hoạt")
                    if success:
                        msg_lbl.configure(text=f"✓ {msg}", text_color="#4ade80")
                        status_lbl.configure(text="Trạng thái: ĐÃ KÍCH HOẠT", text_color="#4ade80")
                        new_plan = info.get("plan_type", "Pro")
                        new_exp = str(info.get("expires_at", "--")).split(" ")[0]
                        details_lbl.configure(
                            text=f"Gói dịch vụ: {new_plan}   |   Hạn dùng: {new_exp}   |   Slot tối đa: {info.get('max_slots', 50)}"
                        )
                        self.update_header_stats()
                    else:
                        msg_lbl.configure(text=f"✗ {msg}", text_color="#f87171")
                dialog.after(0, _done)

            threading.Thread(target=_run, daemon=True).start()

        act_btn = ctk.CTkButton(
            btn_box,
            text="Kích Hoạt",
            width=100,
            height=30,
            corner_radius=6,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=do_activate
        )
        act_btn.pack(side="left")

        def do_deactivate():
            if license_client:
                license_client.deactivate_license()
            key_entry.delete(0, "end")
            msg_lbl.configure(text="✓ Đã bỏ kích hoạt bản quyền trên máy này.", text_color="#facc15")
            status_lbl.configure(text="Trạng thái: CHƯA KÍCH HOẠT", text_color="#f87171")
            details_lbl.configure(text="Gói dịch vụ: Chưa kích hoạt   |   Hạn dùng: --   |   Slot tối đa: --")
            self.update_header_stats()

        deact_btn = ctk.CTkButton(
            btn_box,
            text="Bỏ Kích Hoạt",
            width=105,
            height=30,
            corner_radius=6,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#fca5a5",
            command=do_deactivate
        )
        deact_btn.pack(side="left", padx=(8, 0))

        close_btn = ctk.CTkButton(
            btn_box,
            text="Đóng",
            width=70,
            height=30,
            corner_radius=6,
            fg_color="#1e2430",
            hover_color="#283142",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8",
            command=dialog.destroy
        )
        close_btn.pack(side="right")

    # ==========================================================================
    # TAB 2: CẤU HÌNH (PROFILES TAB)
    # ==========================================================================
    def build_profiles_view(self):
        # Thanh điều khiển cấu hình trên cùng
        top_bar = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(4, 6))

        self.lbl_edit_profile = ctk.CTkLabel(
            top_bar, text=tr("edit_profile"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        )
        self.lbl_edit_profile.pack(side="left", padx=(0, 6))

        self.editor_profile_var = ctk.StringVar(value="Config 1")
        self.editor_profile_combo = ModernOptionMenu(
            top_bar,
            values=PROFILE_NAMES,
            variable=self.editor_profile_var,
            width=115,
            height=28,
            fg_color="#181c26",
            border_color="#2a3042",
            hover_color="#222736",
            command=self.on_editor_profile_change,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.editor_profile_combo.pack(side="left", padx=4)

        self.lbl_pk_delay = ctk.CTkLabel(
            top_bar, text=tr("pk_delay"), font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#d1d5db"
        )
        self.lbl_pk_delay.pack(side="left", padx=(16, 6))

        self.editor_respawn_var = ctk.StringVar(value="15")
        self.editor_respawn_entry = ctk.CTkEntry(
            top_bar,
            textvariable=self.editor_respawn_var,
            width=65,
            height=28,
            fg_color="#27272a",
            border_color="#3f3f46",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.editor_respawn_entry.pack(side="left", padx=4)

        # Nút Lưu và Tải lại bên phải
        self.btn_reload_cfg = ctk.CTkButton(
            top_bar,
            text=tr("reload"),
            width=80,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.reload_editor_from_file
        )
        self.btn_reload_cfg.pack(side="right", padx=(4, 0))

        self.btn_save_cfg = ctk.CTkButton(
            top_bar,
            text=tr("save_profile"),
            width=95,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.save_editor_to_file
        )
        self.btn_save_cfg.pack(side="right", padx=4)

        # Chú thích Team mặc định
        self.lbl_team_note = ctk.CTkLabel(
            self.panel_profiles,
            text=tr("team_note"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9ca3af"
        )
        self.lbl_team_note.pack(anchor="w", padx=12, pady=(0, 8))

        # Tiêu đề cột bảng Stage
        stage_header = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        stage_header.pack(fill="x", padx=12, pady=(0, 4))

        stage_cols = [
            ("stage_min", 65, "center"),
            ("stage_max", 65, "center"),
            ("stage_map", 220, "center"),
            ("stage_x", 70, "center"),
            ("stage_y", 70, "center")
        ]
        self.stage_header_labels = []
        for k, w, anc in stage_cols:
            lbl = ctk.CTkLabel(
                stage_header,
                text=tr(k),
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#9ca3af"
            )
            lbl.pack(side="left", padx=3)
            self.stage_header_labels.append(lbl)

        # 10 Hàng chặng
        self.editor_rows = []
        for r in range(10):
            row_f = ctk.CTkFrame(self.panel_profiles, fg_color="transparent", height=32)
            row_f.pack(fill="x", padx=12, pady=2)

            min_var = ctk.StringVar(value="")
            min_ent = ctk.CTkEntry(
                row_f, textvariable=min_var, width=65, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            min_ent.pack(side="left", padx=3)

            max_var = ctk.StringVar(value="")
            max_ent = ctk.CTkEntry(
                row_f, textvariable=max_var, width=65, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            max_ent.pack(side="left", padx=3)

            map_var = ctk.StringVar(value="")
            map_combo = ModernOptionMenu(
                row_f,
                values=[""] + self.map_list,
                variable=map_var,
                width=220,
                height=28,
                fg_color="#181c26",
                border_color="#2a3042",
                hover_color="#222736",
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            map_combo.pack(side="left", padx=3)

            x_var = ctk.StringVar(value="")
            x_ent = ctk.CTkEntry(
                row_f, textvariable=x_var, width=70, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            x_ent.pack(side="left", padx=3)

            y_var = ctk.StringVar(value="")
            y_ent = ctk.CTkEntry(
                row_f, textvariable=y_var, width=70, height=28, fg_color="#27272a", border_color="#3f3f46"
            )
            y_ent.pack(side="left", padx=3)

            self.editor_rows.append({
                "min": min_var,
                "max": max_var,
                "map": map_var,
                "x": x_var,
                "y": y_var
            })

        # Nạp dữ liệu Config 1 ban đầu
        self.load_profile_into_editor(1)

    def load_profile_into_editor(self, profile_idx: int):
        """Đọc Profile từ file JSON và điền vào form."""
        cfg = ConfigPersistenceManager.load_single_profile(profile_idx)
        self.editor_respawn_var.set(str(cfg.get("respawn_delay", 15)))

        stages = cfg.get("stages", [])
        for i, row in enumerate(self.editor_rows):
            if i < len(stages):
                st = stages[i]
                row["min"].set(str(st.get("min_level", "")))
                row["max"].set(str(st.get("max_level", "")))
                row["map"].set(str(st.get("map_name", "")))
                row["x"].set(str(st.get("x", "")))
                row["y"].set(str(st.get("y", "")))
            else:
                row["min"].set("")
                row["max"].set("")
                row["map"].set("")
                row["x"].set("")
                row["y"].set("")

    def on_editor_profile_change(self, val: str):
        try:
            idx = int(val.replace("Config ", "").strip())
            self.load_profile_into_editor(idx)
        except Exception:
            pass

    def reload_editor_from_file(self):
        """Tải lại dữ liệu tươi mới từ file đĩa JSON."""
        try:
            idx = int(self.editor_profile_var.get().replace("Config ", "").strip())
            self.load_profile_into_editor(idx)
            self.log_message(f"Đã tải lại Config {idx} trực tiếp từ file autotrain_profiles.json.", "INFO")
        except Exception as e:
            self.log_message(f"Lỗi khi tải lại cấu hình: {e}", "ERROR")

    def save_editor_to_file(self):
        """Lưu toàn bộ thay đổi trực tiếp vào file JSON."""
        try:
            idx = int(self.editor_profile_var.get().replace("Config ", "").strip())
            # Đọc config gốc để giữ các trường mở rộng
            cfg = ConfigPersistenceManager.load_single_profile(idx)
            try:
                respawn = int(self.editor_respawn_var.get().strip())
            except Exception:
                respawn = 15
            cfg["respawn_delay"] = respawn

            new_stages = []
            for row in self.editor_rows:
                min_s = row["min"].get().strip()
                max_s = row["max"].get().strip()
                map_s = row["map"].get().strip()
                x_s = row["x"].get().strip()
                y_s = row["y"].get().strip()

                if min_s and max_s and map_s and x_s and y_s:
                    try:
                        new_stages.append({
                            "min_level": int(min_s),
                            "max_level": int(max_s),
                            "map_name": map_s,
                            "x": int(x_s),
                            "y": int(y_s)
                        })
                    except Exception:
                        pass

            cfg["stages"] = new_stages
            # Ghi trực tiếp vào file đĩa
            ConfigPersistenceManager.save_single_profile(idx, cfg)
            self.log_message(
                f"Đã lưu thành công Config {idx} ({len(new_stages)} chặng) vào file autotrain_profiles.json!",
                "SUCCESS"
            )

            # Cập nhật các worker đang chạy Config này
            for ctrl in self.controllers:
                if ctrl.profile_index == idx and ctrl.worker and ctrl.worker.running:
                    if hasattr(ctrl.worker, 'update_config'):
                        ctrl.worker.update_config(cfg)
                    self.log_message(
                        f"[Slot {ctrl.slot_idx:02d}] Áp dụng ngay cấu hình vừa lưu mà không cần khởi động lại!",
                        "SUCCESS"
                    )
        except Exception as e:
            self.log_message(f"Lỗi khi lưu cấu hình: {e}", "ERROR")

    # ==========================================================================
    # TAB 3: NHẬT KÝ (LOGS TAB)
    # ==========================================================================
    def build_logs_view(self):
        # Top filter bar
        top_bar = ctk.CTkFrame(self.panel_logs, fg_color="transparent")
        top_bar.pack(fill="x", padx=6, pady=(4, 6))

        self.lbl_log_show = ctk.CTkLabel(
            top_bar, text=tr("show"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        )
        self.lbl_log_show.pack(side="left", padx=(0, 6))

        filter_options = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
        self.log_filter_var = ctk.StringVar(value=tr("all"))
        self.log_filter_combo = ModernOptionMenu(
            top_bar,
            values=filter_options,
            variable=self.log_filter_var,
            width=90,
            height=28,
            fg_color="#181c26",
            border_color="#2a3042",
            hover_color="#222736",
            command=lambda _: self.render_logs(),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.log_filter_combo.pack(side="left", padx=4)

        self.btn_clear_log = ctk.CTkButton(
            top_bar,
            text=tr("clear_view"),
            width=85,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.clear_logs
        )
        self.btn_clear_log.pack(side="right")

        # Hộp văn bản hiển thị Log tối màu
        self.log_textbox = ctk.CTkTextbox(
            self.panel_logs,
            fg_color="#121214",
            text_color="#f3f4f6",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=6,
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_textbox.configure(state="disabled")

    def log_message(self, msg: str, level: str = "INFO"):
        """Ghi nhận log hệ thống và hiển thị lên giao diện."""
        t_str = time.strftime("%H:%M:%S")
        # Phân loại slot nếu có [Slot XX]
        slot_tag = "ALL"
        if msg.startswith("[Slot ") and len(msg) >= 9:
            try:
                slot_tag = msg[6:8]
            except Exception:
                slot_tag = "ALL"

        self.logs_data.append((t_str, slot_tag, f"[{level}] {msg}"))
        if len(self.logs_data) > 1500:
            self.logs_data.pop(0)

        # Cập nhật nếu đang mở tab logs
        if self.active_tab == "logs":
            self.render_logs()

    def render_logs(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        selected_filter = self.log_filter_var.get()

        lines = []
        for t_str, s_tag, content in self.logs_data:
            if selected_filter == tr("all") or selected_filter == s_tag:
                lines.append(f"[{t_str}] {content}")

        self.log_textbox.insert("end", "\n".join(lines) + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def clear_logs(self):
        self.logs_data.clear()
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    # ==========================================================================
    # ĐIỀU HƯỚNG TAB
    # ==========================================================================
    def switch_tab(self, tab_name: str):
        self.active_tab = tab_name

        act_bg = "#18202d"
        act_border = "#14b8a6"
        act_text = "#2dd4bf"
        inact_text = "#94a3b8"

        if tab_name == "accounts":
            self.tab_accounts_btn.configure(fg_color=act_bg, text_color=act_text, border_width=1, border_color=act_border, image=UiIconFactory.get("user", color="#2dd4bf", size=(14, 14)))
            self.tab_profiles_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("gear", color="#94a3b8", size=(14, 14)))
            self.tab_logs_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("file", color="#94a3b8", size=(14, 14)))
        elif tab_name == "profiles":
            self.tab_accounts_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("user", color="#94a3b8", size=(14, 14)))
            self.tab_profiles_btn.configure(fg_color=act_bg, text_color=act_text, border_width=1, border_color=act_border, image=UiIconFactory.get("gear", color="#2dd4bf", size=(14, 14)))
            self.tab_logs_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("file", color="#94a3b8", size=(14, 14)))
        elif tab_name == "logs":
            self.tab_accounts_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("user", color="#94a3b8", size=(14, 14)))
            self.tab_profiles_btn.configure(fg_color="transparent", text_color=inact_text, border_width=0, image=UiIconFactory.get("gear", color="#94a3b8", size=(14, 14)))
            self.tab_logs_btn.configure(fg_color=act_bg, text_color=act_text, border_width=1, border_color=act_border, image=UiIconFactory.get("file", color="#2dd4bf", size=(14, 14)))

        # Ẩn hết các panels và toolbar hành động
        if hasattr(self, "toolbar_frame"):
            self.toolbar_frame.pack_forget()
        self.panel_accounts.pack_forget()
        self.panel_profiles.pack_forget()
        self.panel_logs.pack_forget()

        if tab_name == "accounts":
            if hasattr(self, "toolbar_frame") and hasattr(self, "content_container"):
                self.toolbar_frame.pack(fill="x", padx=20, pady=(6, 8), before=self.content_container)
            self.panel_accounts.pack(fill="both", expand=True)
        elif tab_name == "profiles":
            self.panel_profiles.pack(fill="both", expand=True)
        elif tab_name == "logs":
            self.panel_logs.pack(fill="both", expand=True)
            self.render_logs()

    def jump_to_config_tab(self, slot_idx: int):
        """Nhảy nhanh sang Tab Cấu hình khi bấm nút '⚙' ở Slot."""
        ctrl = self.controllers[slot_idx - 1]
        cfg_name = f"Config {ctrl.profile_index}"
        self.editor_profile_var.set(cfg_name)
        self.load_profile_into_editor(ctrl.profile_index)
        self.switch_tab("profiles")

    # ==========================================================================
    # XỬ LÝ SỰ KIỆN TỪNG SLOT
    # ==========================================================================
    def on_slot_pid_selected(self, slot_idx: int, val: str):
        ctrl = self.controllers[slot_idx - 1]
        if val in ("--", tr("select"), "") or not val:
            ctrl.detach()
            return

        try:
            import re
            m = re.search(r"\((\d+)\)", val)
            if m:
                pid = int(m.group(1))
            else:
                pid = int(val.split(" - ")[0].strip())
            ctrl.attach_pid(pid)
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Không thể gán PID: {e}", "ERROR")

    def on_slot_profile_selected(self, slot_idx: int, val: str):
        try:
            p_idx = int(val.replace("Config ", "").strip())
            ctrl = self.controllers[slot_idx - 1]
            ctrl.set_profile(p_idx)
            self.slot_assignments[slot_idx] = p_idx
            el = self.slot_ui_elements.get(slot_idx)
            if el and el.get("profile_var"):
                el["profile_var"].set(f"Config {p_idx}")
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
            self.log_message(f"[Slot {slot_idx:02d}] Đã đổi tuyến đường sang: Config {p_idx}", "INFO")
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Lỗi đổi cấu hình: {e}", "ERROR")

    def on_slot_auto_toggle(self, slot_idx: int):
        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng Auto đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để tiếp tục sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        ctrl = self.controllers[slot_idx - 1]
        ctrl.toggle_auto()

    def update_slot_ui_status(self, slot_idx: int, text: str):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if el and el.get("status_lbl"):
                lbl = el["status_lbl"]
                tl = str(text).lower()
                if "tự động đánh" in tl or "running" in tl or "đang chạy" in tl or "at spot" in tl or "tại bãi" in tl or "executando" in tl:
                    lbl.configure(text=tr("status_running"), text_color="#4ade80")
                elif "moving" in tl or "chạy ra bãi" in tl or "di chuyển" in tl or "map" in tl or "movendo" in tl:
                    lbl.configure(text=tr("status_moving"), text_color="#facc15")
                elif "game đã đóng" in tl or "game_closed" in tl or "closed" in tl or "disconnect" in tl or "pk" in tl or "mất kết nối" in tl or "desconectado" in tl:
                    lbl.configure(text=tr("status_disconnected"), text_color="#f87171")
                elif "đã kết nối" in tl or "connected" in tl or "stopped" in tl or "đã dừng" in tl or "parado" in tl:
                    lbl.configure(text=tr("status_stopped"), text_color="#e2e8f0")
                elif "idle" in tl or "chờ" in tl or "aguardando" in tl:
                    lbl.configure(text=tr("status_idle"), text_color="#94a3b8")
                else:
                    lbl.configure(text=str(text), text_color="#94a3b8")
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def update_slot_ui_auto(self, slot_idx: int, is_on: bool):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if el and el.get("btn_toggle"):
                btn = el["btn_toggle"]
                if is_on:
                    btn.configure(
                        image=UiIconFactory.get("stop", color="#ffffff", size=(11, 11)),
                        text="",
                        fg_color="#2563eb",
                        hover_color="#1d4ed8",
                        border_color="#3b82f6"
                    )
                else:
                    btn.configure(
                        image=UiIconFactory.get("play", color="#38bdf8", size=(11, 11)),
                        text="",
                        fg_color="#181c26",
                        hover_color="#242b3a",
                        border_color="#2b3244"
                    )
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def update_slot_ui_telemetry(self, slot_idx: int, name: str, lvl: str, coords: str):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if not el:
                return
            ctrl = self.controllers[slot_idx - 1]
            if el.get("proc_var") and name and name != "---":
                curr = el["proc_var"].get()
                if curr in ("--", tr("select"), "") or name not in curr:
                    pid_str = f"{ctrl.assigned_pid}" if ctrl.assigned_pid else ""
                    el["proc_var"].set(f"{name} ({pid_str})" if pid_str else name)

            if lvl and lvl != "---":
                try:
                    lvl_num = int(lvl)
                except Exception:
                    lvl_num = 0
                if lvl_num > 0:
                    if el.get("lvl_lbl"):
                        if lvl_num >= 400:
                            el["lvl_lbl"].configure(text=f"M.LV {lvl_num}", text_color="#38bdf8")
                        else:
                            el["lvl_lbl"].configure(text=f"LV {lvl_num}", text_color="#94a3b8")
                    if el.get("prog_bar"):
                        ratio = min(1.0, max(0.05, (lvl_num % 400) / 400.0 if lvl_num >= 400 else lvl_num / 400.0))
                        el["prog_bar"].set(ratio)
                    if el.get("exp_lbl"):
                        exp_cur = lvl_num * 3717 + 800
                        exp_max = 800 if lvl_num >= 400 else 400
                        el["exp_lbl"].configure(text=f"{exp_cur:,} / {exp_max} EXP".replace(",", "."))

                    if el.get("profile_var"):
                        expected_cfg = f"Config {ctrl.profile_index}"
                        if el["profile_var"].get() != expected_cfg:
                            el["profile_var"].set(expected_cfg)

            if el.get("coords_lbl"):
                if coords and coords.strip() and coords not in ("--,--", "--", "--, --"):
                    parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
                    if len(parts) >= 2:
                        c_disp = f"{parts[0]}, {parts[1]}"
                    else:
                        c_disp = coords.strip()
                    el["coords_lbl"].configure(text=c_disp)
                else:
                    el["coords_lbl"].configure(text="--, --")
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    # ==========================================================================
    # CÁC NÚT ĐIỀU KHIỂN HÀNG LOẠT (BULK ACTIONS)
    # ==========================================================================
    def refresh_games(self):
        """Quét lại danh sách MEGAMU.exe."""
        self.detected_games = enumerate_megamu_processes()
        options = ["--"]
        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
            options.append(disp)

        for i in self.slot_ui_elements.keys():
            el = self.slot_ui_elements.get(i)
            if el and el.get("proc_combo"):
                el["proc_combo"].configure(values=options)

        self.update_header_stats()
        self.log_message(f"Đã làm mới: Phát hiện {len(self.detected_games)} cửa sổ MEGAMU.exe.", "INFO")

    def assign_all(self):
        """Gán tất cả tiến trình MEGAMU vào các Slot trống."""
        self.refresh_games()
        assigned_pids = {c.assigned_pid for c in self.controllers if c.assigned_pid}
        available_pids = [p for p in self.detected_games if p not in assigned_pids]

        assigned_count = 0
        for ctrl in self.controllers:
            if not ctrl.assigned_pid and available_pids:
                pid = available_pids.pop(0)
                ctrl.attach_pid(pid)
                # Cập nhật dropdown
                el = self.slot_ui_elements.get(ctrl.slot_idx)
                if el:
                    title = self.detected_games.get(pid, "")
                    char_name = character_name_from_window_title(title)
                    disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
                    el["proc_var"].set(disp)
                assigned_count += 1

        self.update_header_stats()
        self.log_message(f"Gán tất cả: Đã gán {assigned_count} tài khoản vào bảng.", "SUCCESS")

    def assign_team5(self):
        """Gán 5 tài khoản vào 1 Team còn trống."""
        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng gán Team đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        self.refresh_games()
        assigned_pids = {c.assigned_pid for c in self.controllers if c.assigned_pid}
        available_pids = [p for p in self.detected_games if p not in assigned_pids]

        if len(available_pids) < 1:
            self.log_message("Không có tiến trình MEGAMU nào chưa được gán.", "WARNING")
            return

        # Tìm nhóm 5 slot (Team 1, Team 2, Team 3...) còn trống nhiều nhất
        groups = []
        n = len(self.controllers)
        for i in range(0, n, 5):
            groups.append((i + 1, min(i + 5, n)))

        target_slots = None
        for g_start, g_end in groups:
            empty_slots = [c for c in self.controllers if g_start <= c.slot_idx <= g_end and not c.assigned_pid]
            if len(empty_slots) >= min(5, len(available_pids)):
                target_slots = empty_slots
                break

        if not target_slots:
            target_slots = [c for c in self.controllers if not c.assigned_pid]

        count = 0
        for ctrl in target_slots[:5]:
            if available_pids:
                pid = available_pids.pop(0)
                ctrl.attach_pid(pid)
                el = self.slot_ui_elements.get(ctrl.slot_idx)
                if el:
                    title = self.detected_games.get(pid, "")
                    char_name = character_name_from_window_title(title)
                    disp = f"{char_name} ({pid})" if char_name else f"MEGAMU ({pid})"
                    el["proc_var"].set(disp)
                count += 1

        self.update_header_stats()
        self.log_message(f"Gán Team 5: Đã gán thành công {count} tài khoản.", "SUCCESS")

    def connect_all(self):
        """Kết nối tới tất cả các slot đã chọn PID."""
        if license_client and not license_client.is_license_valid():
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Khóa Chức Năng",
                    "Chức năng Kết nối tất cả đã bị khóa vì bản quyền chưa được kích hoạt hoặc đã hết hạn!\n\nVui lòng kích hoạt bản quyền để sử dụng."
                )
            except Exception:
                pass
            self.open_license_dialog()
            return

        for ctrl in self.controllers:
            if ctrl.assigned_pid and not (ctrl.engine and ctrl.engine.is_ready):
                ctrl.attach_pid(ctrl.assigned_pid)
        self.update_header_stats()

    def start_all(self):
        """Bật Auto cho tất cả các slot có game."""
        count = 0
        for ctrl in self.controllers:
            if ctrl.assigned_pid:
                ok = ctrl.start_auto()
                if ok:
                    count += 1
        self.update_header_stats()
        self.log_message(f"Bật TẤT CẢ: Đã khởi động Auto cho {count} tài khoản.", "SUCCESS")

    def stop_all(self):
        """Tắt Auto cho tất cả các slot."""
        for ctrl in self.controllers:
            ctrl.stop_auto()
        self.update_header_stats()
        self.log_message("Tắt TẤT CẢ: Đã dừng Auto cho toàn bộ tài khoản.", "INFO")

    def batch_start(self):
        """Bật Auto cho nhóm được chọn ở combobox Điều khiển."""
        targets = self._get_filtered_controllers()
        count = 0
        for ctrl in targets:
            if ctrl.assigned_pid:
                ok = ctrl.start_auto()
                if ok:
                    count += 1
        self.update_header_stats()

    def batch_stop(self):
        """Tắt Auto cho nhóm được chọn ở combobox Điều khiển."""
        targets = self._get_filtered_controllers()
        for ctrl in targets:
            ctrl.stop_auto()
        self.update_header_stats()

    def _get_filtered_controllers(self) -> List[SlotController]:
        choice = self.ctrl_target_var.get()
        if choice == tr("all"):
            return self.controllers

        # Khớp theo Team dạng "Team X (start-end)"
        import re
        m = re.search(r"\((\d+)-(\d+)\)", choice)
        if m:
            start_i = max(0, int(m.group(1)) - 1)
            end_i = min(len(self.controllers), int(m.group(2)))
            return self.controllers[start_i:end_i]

        try:
            s_idx = int(choice)
            if 1 <= s_idx <= len(self.controllers):
                return [self.controllers[s_idx - 1]]
        except Exception:
            pass
        return self.controllers

    def change_language(self, lang_choice: str):
        lang_code = lang_choice.replace("💬", "").replace("Language:", "").strip().lower()
        target_code = None
        for k in I18N.keys():
            if k.lower() == lang_code:
                target_code = k
                break
        if target_code:
            save_language_preference(target_code)
            self.apply_language()
            self.log_message(tr("lang_changed", lang=target_code.upper()), "INFO")

    def apply_language(self):
        """Áp dụng đa ngôn ngữ thời gian thực ngay lập tức cho toàn bộ giao diện."""
        # 1. Tab buttons
        n = len(self.controllers)
        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({n})")
        if hasattr(self, "tab_profiles_btn"):
            self.tab_profiles_btn.configure(text=f" {tr('configuration')}")
        if hasattr(self, "tab_logs_btn"):
            self.tab_logs_btn.configure(text=f" {tr('logs')}")
        if hasattr(self, "btn_text_cfg"):
            self.btn_text_cfg.configure(text=tr("text_config"))

        # 2. Action Toolbar buttons
        if hasattr(self, "btn_connect_all"):
            self.btn_connect_all.configure(text=f" {tr('connect_all')}")
        if hasattr(self, "btn_team5"):
            self.btn_team5.configure(text=f" {tr('assign_team5')}")
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.configure(text=f" {tr('refresh_games')}")
        if hasattr(self, "btn_add_slot"):
            self.btn_add_slot.configure(text=f" {tr('add')}")
        if hasattr(self, "btn_remove_slot"):
            self.btn_remove_slot.configure(text=f" {tr('remove')}")

        # 3. Table Header in Accounts Tab
        if hasattr(self, "col_header_labels"):
            keys = ["col_no", "col_char_pid", "col_route_preset", "col_coordinates", "col_status", "col_actions"]
            for lbl, k in zip(self.col_header_labels, keys):
                try:
                    lbl.configure(text=tr(k))
                except Exception:
                    pass

        # 4. Status text of every slot
        for ctrl in self.controllers:
            self.update_slot_ui_status(ctrl.slot_idx, ctrl.status)

        # 5. Configuration Tab
        if hasattr(self, "lbl_edit_profile"):
            self.lbl_edit_profile.configure(text=tr("edit_profile"))
        if hasattr(self, "lbl_pk_delay"):
            self.lbl_pk_delay.configure(text=tr("pk_delay"))
        if hasattr(self, "btn_reload_cfg"):
            self.btn_reload_cfg.configure(text=tr("reload"))
        if hasattr(self, "btn_save_cfg"):
            self.btn_save_cfg.configure(text=tr("save_profile"))
        if hasattr(self, "lbl_team_note"):
            self.lbl_team_note.configure(text=tr("team_note"))
        if hasattr(self, "stage_header_labels"):
            s_keys = ["stage_min", "stage_max", "stage_map", "stage_x", "stage_y"]
            for lbl, sk in zip(self.stage_header_labels, s_keys):
                try:
                    lbl.configure(text=tr(sk))
                except Exception:
                    pass

        # 6. Logs Tab
        if hasattr(self, "lbl_log_show"):
            self.lbl_log_show.configure(text=tr("show"))
        if hasattr(self, "btn_clear_log"):
            self.btn_clear_log.configure(text=tr("clear_view"))
        if hasattr(self, "log_filter_combo"):
            current_filter = self.log_filter_var.get()
            opts = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
            self.log_filter_combo.configure(values=opts)
            if current_filter not in opts:
                self.log_filter_var.set(tr("all"))

        # 7. Language Menu Variable
        if hasattr(self, "lang_var"):
            self.lang_var.set(f"Language: {CURRENT_LANG.upper()}")

        # 8. Header & Footer Stats
        self.update_header_stats()

    # ==========================================================================
    # CÁC TÁC VỤ ĐỊNH KỲ (SCAN TIẾN TRÌNH & ĐỌC TELEMETRY)
    # ==========================================================================
    def _periodic_game_scan(self):
        if not self.running:
            return
        try:
            self.detected_games = enumerate_megamu_processes()
            self.update_header_stats()
        except Exception:
            pass
        self.after(2500, self._periodic_game_scan)

    def _periodic_telemetry(self):
        if not self.running:
            return
        try:
            for ctrl in self.controllers:
                if ctrl.assigned_pid:
                    ctrl.sync_telemetry()
        except Exception:
            pass
        self.after(200, self._periodic_telemetry)

    def update_header_stats(self):
        """Cập nhật các số liệu thống kê trên thanh tiêu đề và chân trang."""
        num_games = len(self.detected_games)
        num_conn = sum(1 for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid))
        num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
        num_slots = len(self.controllers)

        lic_str = license_client.get_license_display_text() if license_client else CURRENT_LICENSE
        stat_text = tr(
            "header_stats",
            games=num_games,
            conn=num_conn,
            slots=num_slots,
            auto=num_auto,
            license=lic_str,
            expiry="--"
        )
        if hasattr(self, "header_stats_lbl"):
            self.header_stats_lbl.configure(text=stat_text)

        if hasattr(self, "footer_stats_lbl"):
            self.footer_stats_lbl.configure(text=tr("footer_stats", slots=num_slots, conn=num_conn, auto=num_auto))

        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f" {tr('characters')} ({num_slots})")

        # Cập nhật trạng thái khóa/mở khóa các chức năng theo bản quyền
        self.apply_license_lock_state()

    def apply_license_lock_state(self):
        """Khóa hoặc mở khóa toàn bộ chức năng theo trạng thái bản quyền."""
        is_valid = license_client.is_license_valid() if license_client else False
        state_val = "normal" if is_valid else "disabled"

        # 0. Nếu không có bản quyền hợp lệ, lập tức dừng mọi worker đang auto train
        if not is_valid:
            for ctrl in self.controllers:
                if ctrl.worker and ctrl.worker.running:
                    ctrl.stop_auto()

        # 1. Khóa/mở khóa các nút thanh công cụ chính
        for btn_name in ("btn_connect_all", "btn_team5", "btn_refresh", "btn_add_slot", "btn_remove_slot"):
            if hasattr(self, btn_name):
                try:
                    getattr(self, btn_name).configure(state=state_val)
                except Exception:
                    pass

        # 2. Khóa/mở khóa các nút lưu cấu hình tab Profiles
        for btn_name in ("btn_save_cfg", "btn_reload_cfg"):
            if hasattr(self, btn_name):
                try:
                    getattr(self, btn_name).configure(state=state_val)
                except Exception:
                    pass

        # 3. Khóa/mở khóa các nút thao tác từng slot
        for elem in self.slot_ui_elements.values():
            for key in ("btn_toggle", "btn_cfg", "proc_combo", "preset_combo"):
                if key in elem:
                    try:
                        elem[key].configure(state=state_val)
                    except Exception:
                        pass

        # 4. Hiển thị / ẩn banner cảnh báo trên Toolbar
        if not is_valid:
            if not hasattr(self, "license_lock_banner") or self.license_lock_banner is None:
                self.license_lock_banner = ctk.CTkFrame(
                    self.toolbar_frame,
                    fg_color="#3b1219",
                    border_width=1,
                    border_color="#ef4444",
                    corner_radius=6,
                    height=32
                )
                self.license_lock_banner.pack(side="right", padx=(0, 6))

                ctk.CTkLabel(
                    self.license_lock_banner,
                    text="🔒 BẢN QUYỀN CHƯA KÍCH HOẠT (ĐÃ KHÓA CHỨC NĂNG)",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    text_color="#fca5a5"
                ).pack(side="left", padx=(10, 8), pady=4)

                ctk.CTkButton(
                    self.license_lock_banner,
                    text="Kích Hoạt",
                    width=75,
                    height=22,
                    corner_radius=4,
                    fg_color="#dc2626",
                    hover_color="#b91c1c",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    command=self.open_license_dialog
                ).pack(side="right", padx=(0, 6), pady=4)
        else:
            if hasattr(self, "license_lock_banner") and self.license_lock_banner is not None:
                try:
                    self.license_lock_banner.destroy()
                except Exception:
                    pass
                self.license_lock_banner = None

    def _apply_window_icon(self):
        """Áp dụng icon DAuto cho cửa sổ và thanh Taskbar Windows."""
        if ICON_FILE.exists():
            try:
                self.iconbitmap(str(ICON_FILE))
            except Exception:
                pass
            try:
                self.wm_iconbitmap(str(ICON_FILE))
            except Exception:
                pass
            try:
                from PIL import ImageTk
                _ico_img = Image.open(str(ICON_FILE))
                self._tk_icon = ImageTk.PhotoImage(_ico_img)
                self.iconphoto(False, self._tk_icon)
            except Exception:
                pass

    def on_closing(self):
        self.running = False
        self.stop_all()
        for ctrl in self.controllers:
            if ctrl.engine:
                try:
                    ctrl.engine.detach()
                except Exception:
                    pass
        self.destroy()


# ==============================================================================
def main():
    try:
        with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] main() starting...\n")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dauto.megamu.dashboard.v1")
    except Exception:
        pass
    try:
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DashboardApp creating...\n")
        except Exception:
            pass
        app = DashboardApp()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] app.mainloop() starting...\n")
        except Exception:
            pass
        app.mainloop()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] app.mainloop() finished naturally.\n")
        except Exception:
            pass
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open("gui_lifecycle.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception in main: {err_msg}\n")
        except Exception:
            pass
        print(err_msg, flush=True)
        try:
            with open("gui_crash.log", "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Lỗi khởi động", f"Chương trình gặp lỗi khi chạy:\n{e}\n\nXem chi tiết tại gui_crash.log")
        except Exception:
            pass

if __name__ == "__main__":
    main()
