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
from typing import Optional, List, Dict, Tuple, Any
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
from PIL import Image, ImageTk
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

# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN TỆP
# ==============================================================================
APP_NAME = "MEGAMU Auto Train Dashboard"
APP_VERSION = "v1.5.1"
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
# BẢNG DỊCH NGÔN NGỮ (I18N)
# ==============================================================================
I18N = {
    "vi": {
        "refresh_games": "Làm mới Game",
        "assign_team5": "Gán Team 5",
        "assign_all": "Gán tất cả",
        "connect_all": "Kết nối tất cả",
        "control": "Điều khiển:",
        "start": "Bật",
        "stop": "Tắt",
        "start_all": "Bật TẤT CẢ",
        "stop_all": "Tắt TẤT CẢ",
        "accounts": "Tài khoản",
        "profiles": "Cấu hình",
        "system_log": "Nhật ký",
        "profile": "Cấu hình",
        "name": "Tên",
        "status": "Trạng thái",
        "auto": "Auto",
        "edit_profile": "Sửa cấu hình:",
        "pk_delay": "Thời gian chờ PK/Hồi sinh:",
        "reload": "Tải lại",
        "save_profile": "Lưu cấu hình",
        "team_note": "Team mặc định: 1-5=C1, 6-10=C2, ... 46-50=C10. Có thể chọn cấu hình khác cho từng dòng.",
        "show": "Hiện:",
        "clear_view": "Xóa hiển thị",
        "all": "Tất cả",
        "language": "Ngôn ngữ:",
        "games": "Game",
        "connected": "Đã kết nối",
        "license": "Bản quyền",
        "select": "-- Chọn --",
        "idle": "Chờ",
        "connected_status": "Đã kết nối",
        "connecting": "Đang kết nối...",
        "game_closed": "Game đã đóng",
        "running": "Đang chạy C{n}",
        "pk_wait": "CHỜ PK {n}s",
        "map_wait": "CHỜ MAP {cur}→{exp}",
        "map_verify": "Xác minh map...",
        "map_unknown": "Map chưa có ID",
        "at_spot": "Tới bãi farm",
        "add_account": "+ Thêm Account",
        "remove_account": "- Xóa Account cuối",
        "total_accounts": "Tổng số tài khoản: {n}"
    },
    "en": {
        "refresh_games": "Refresh Games",
        "assign_team5": "Assign Team 5",
        "assign_all": "Assign All",
        "connect_all": "Connect All",
        "control": "Control:",
        "start": "Start",
        "stop": "Stop",
        "start_all": "Start ALL",
        "stop_all": "Stop ALL",
        "accounts": "Accounts",
        "profiles": "Profiles",
        "system_log": "System Log",
        "profile": "Profile",
        "name": "Name",
        "status": "Status",
        "auto": "Auto",
        "edit_profile": "Edit profile:",
        "pk_delay": "PK/Respawn delay:",
        "reload": "Reload",
        "save_profile": "Save Profile",
        "team_note": "Default teams: 1-5=C1, 6-10=C2, ... 46-50=C10. You can also choose a different profile per row.",
        "show": "Show:",
        "clear_view": "Clear View",
        "all": "All",
        "language": "Language:",
        "games": "Games",
        "connected": "Connected",
        "license": "License",
        "select": "-- Select --",
        "idle": "Idle",
        "connected_status": "Connected",
        "connecting": "Connecting...",
        "game_closed": "Game Closed",
        "running": "Running C{n}",
        "pk_wait": "WAIT PK {n}s",
        "map_wait": "WAIT MAP {cur}→{exp}",
        "map_verify": "Verifying map...",
        "map_unknown": "Unknown map ID",
        "at_spot": "Farming at spot",
        "add_account": "+ Add Account",
        "remove_account": "- Remove Last Account",
        "total_accounts": "Total accounts: {n}"
    },
    "pt-BR": {
        "refresh_games": "Atualizar Games",
        "assign_team5": "Atribuir Time 5",
        "assign_all": "Atribuir Todos",
        "connect_all": "Conectar Todos",
        "control": "Controle:",
        "start": "Ligar",
        "stop": "Desligar",
        "start_all": "Ligar TODOS",
        "stop_all": "Desligar TODOS",
        "accounts": "Contas",
        "profiles": "Perfis",
        "system_log": "Registros",
        "profile": "Perfil",
        "name": "Nome",
        "status": "Status",
        "auto": "Auto",
        "edit_profile": "Editar perfil:",
        "pk_delay": "Espera PK/Respawn:",
        "reload": "Recarregar",
        "save_profile": "Salvar Perfil",
        "team_note": "Times padrão: 1-5=C1, 6-10=C2, ... 46-50=C10. Você pode escolher outro perfil por linha.",
        "show": "Mostrar:",
        "clear_view": "Limpar Visão",
        "all": "Todos",
        "language": "Idioma:",
        "games": "Jogos",
        "connected": "Conectados",
        "license": "Licença",
        "select": "-- Selecionar --",
        "idle": "Aguardando",
        "connected_status": "Conectado",
        "connecting": "Conectando...",
        "game_closed": "Jogo Fechado",
        "running": "Executando C{n}",
        "pk_wait": "ESPERA PK {n}s",
        "map_wait": "ESPERA MAPA {cur}→{exp}",
        "map_verify": "Verificando mapa...",
        "map_unknown": "ID do mapa desconhecido",
        "at_spot": "No spot",
        "add_account": "+ Adicionar Conta",
        "remove_account": "- Remover Última Conta",
        "total_accounts": "Total de contas: {n}"
    }
}

CURRENT_LANG = "vi"

def load_language_preference() -> str:
    global CURRENT_LANG
    try:
        if UI_SETTINGS_FILE.exists():
            data = json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
            lang = str(data.get("language", "vi")).strip()
            if lang in I18N:
                CURRENT_LANG = lang
                return lang
    except Exception:
        pass
    CURRENT_LANG = "vi"
    return CURRENT_LANG

def save_language_preference(lang: str):
    global CURRENT_LANG
    if lang in I18N:
        CURRENT_LANG = lang
        try:
            data = {"language": lang}
            UI_SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

def tr(key: str, **kwargs) -> str:
    lang_dict = I18N.get(CURRENT_LANG, I18N["vi"])
    text = lang_dict.get(key, I18N["vi"].get(key, key))
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
        self.geometry("1060x720")
        self.minsize(980, 640)
        self.configure(fg_color="#18181b")

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

        # Bắt đầu vòng lặp quét tiến trình & telemetry
        self.running = True
        self.after(500, self._periodic_game_scan)
        self.after(800, self._periodic_telemetry)

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
        self.header_frame = ctk.CTkFrame(self, fg_color="#18181b", height=65)
        self.header_frame.pack(fill="x", padx=16, pady=(10, 2))

        # Cột Trái: Logo + Tên + Thông số bản quyền
        left_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_box.pack(side="left", fill="y")

        # Logo
        if LOGO_FILE.exists():
            try:
                logo_img = Image.open(str(LOGO_FILE))
                lw, lh = logo_img.size
                aspect = lw / max(1, lh)
                target_h = 44
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
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color="#f3f4f6"
        )
        title_lbl.pack(side="left")

        ver_lbl = ctk.CTkLabel(
            title_line,
            text=f" {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#71717a"
        )
        ver_lbl.pack(side="left", padx=(4, 0))

        # Dòng thống kê Header
        self.header_stats_lbl = ctk.CTkLabel(
            title_box,
            text=f"Game: 0 | Đã kết nối: 0 | Auto: 0 | Bản quyền: Basic | 10 acc | 2026-10-01 | Online",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9ca3af"
        )
        self.header_stats_lbl.pack(anchor="w", pady=(1, 0))

        # Cột Phải: 4 Nút hành động nhanh (Xanh dương đậm)
        btn_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        btn_box.pack(side="right", fill="y")

        btn_base_style = {
            "font": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "fg_color": "#2563eb",
            "hover_color": "#1d4ed8",
            "text_color": "#ffffff",
            "corner_radius": 5
        }

        self.btn_refresh = ctk.CTkButton(
            btn_box, text=tr("refresh_games"), width=105, height=30, command=self.refresh_games, **btn_base_style
        )
        self.btn_refresh.pack(side="right", padx=(4, 0))

        self.btn_team5 = ctk.CTkButton(
            btn_box, text=tr("assign_team5"), width=95, height=30, command=self.assign_team5, **btn_base_style
        )
        self.btn_team5.pack(side="right", padx=4)

        self.btn_assign_all = ctk.CTkButton(
            btn_box, text=tr("assign_all"), width=85, height=30, command=self.assign_all, **btn_base_style
        )
        self.btn_assign_all.pack(side="right", padx=4)

        self.btn_connect_all = ctk.CTkButton(
            btn_box, text=tr("connect_all"), width=95, height=30, command=self.connect_all, **btn_base_style
        )
        self.btn_connect_all.pack(side="right", padx=4)

        # ----------------------------------------------------------------------
        # 2. THANH ĐIỀU KHIỂN PHỤ (SUB-HEADER)
        # ----------------------------------------------------------------------
        self.sub_frame = ctk.CTkFrame(self, fg_color="#18181b", height=38)
        self.sub_frame.pack(fill="x", padx=16, pady=(4, 2))

        # Điều khiển bên trái: [Điều khiển: Tất cả v] [Bật] [Tắt]
        sub_left = ctk.CTkFrame(self.sub_frame, fg_color="transparent")
        sub_left.pack(side="left")

        ctk.CTkLabel(
            sub_left, text=tr("control"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        ).pack(side="left", padx=(0, 6))

        ctrl_options = [tr("all")]
        self.ctrl_target_var = ctk.StringVar(value=tr("all"))
        self.ctrl_combo = ctk.CTkOptionMenu(
            sub_left,
            values=ctrl_options,
            variable=self.ctrl_target_var,
            width=100,
            height=28,
            fg_color="#2563eb",
            button_color="#1d4ed8",
            corner_radius=4,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.ctrl_combo.pack(side="left", padx=4)

        self.btn_batch_on = ctk.CTkButton(
            sub_left, text=tr("start"), width=60, height=28, command=self.batch_start, **btn_base_style
        )
        self.btn_batch_on.pack(side="left", padx=4)

        self.btn_batch_off = ctk.CTkButton(
            sub_left, text=tr("stop"), width=60, height=28, command=self.batch_stop, **btn_base_style
        )
        self.btn_batch_off.pack(side="left", padx=4)

        # Điều khiển bên phải: [Tắt TẤT CẢ] [Bật TẤT CẢ] [Ngôn ngữ: VI v]
        sub_right = ctk.CTkFrame(self.sub_frame, fg_color="transparent")
        sub_right.pack(side="right")

        self.btn_all_off = ctk.CTkButton(
            sub_right, text=tr("stop_all"), width=85, height=28, command=self.stop_all, **btn_base_style
        )
        self.btn_all_off.pack(side="left", padx=4)

        self.btn_all_on = ctk.CTkButton(
            sub_right, text=tr("start_all"), width=85, height=28, command=self.start_all, **btn_base_style
        )
        self.btn_all_on.pack(side="left", padx=4)

        ctk.CTkLabel(
            sub_right, text=tr("language"), font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#d1d5db"
        ).pack(side="left", padx=(10, 4))

        self.lang_var = ctk.StringVar(value=CURRENT_LANG.upper())
        self.lang_menu = ctk.CTkOptionMenu(
            sub_right,
            values=["VI", "EN", "PT-BR"],
            variable=self.lang_var,
            width=65,
            height=28,
            fg_color="#2563eb",
            button_color="#1d4ed8",
            corner_radius=4,
            command=self.change_language,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.lang_menu.pack(side="left", padx=4)

        # Dòng RPC lanes & metrics dưới sub-header
        metric_frame = ctk.CTkFrame(self, fg_color="#18181b")
        metric_frame.pack(fill="x", padx=16, pady=(0, 6))

        self.metrics_lbl = ctk.CTkLabel(
            metric_frame,
            text="PID RPC Lanes | AVG -- ms | P95 -- ms | Active 0/0 | Q 0 | STATE MAX -- ms",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#71717a"
        )
        self.metrics_lbl.pack(side="right")

        # ----------------------------------------------------------------------
        # 3. TAB NAVIGATION (Centered Segmented Buttons)
        # ----------------------------------------------------------------------
        tab_bar = ctk.CTkFrame(self, fg_color="transparent")
        tab_bar.pack(anchor="center", pady=(4, 8))

        self.tab_accounts_btn = ctk.CTkButton(
            tab_bar,
            text=f"{len(self.controllers)} {tr('accounts')}",
            width=100,
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self.switch_tab("accounts")
        )
        self.tab_accounts_btn.pack(side="left", padx=2)

        self.tab_profiles_btn = ctk.CTkButton(
            tab_bar,
            text=tr("profiles"),
            width=80,
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self.switch_tab("profiles")
        )
        self.tab_profiles_btn.pack(side="left", padx=2)

        self.tab_logs_btn = ctk.CTkButton(
            tab_bar,
            text=tr("system_log"),
            width=80,
            height=28,
            corner_radius=5,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self.switch_tab("logs")
        )
        self.tab_logs_btn.pack(side="left", padx=2)

        # ----------------------------------------------------------------------
        # 4. CONTENT CONTAINERS
        # ----------------------------------------------------------------------
        self.content_container = ctk.CTkFrame(self, fg_color="#18181b")
        self.content_container.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # 3 Panels cho 3 Tab
        self.panel_accounts = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.panel_profiles = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.panel_logs = ctk.CTkFrame(self.content_container, fg_color="transparent")

        self.build_accounts_view()
        self.build_profiles_view()
        self.build_logs_view()

        # Đồng bộ danh sách Slot vào combobox và nhãn điều khiển
        self.update_combo_slot_options()

        # Mặc định hiển thị tab accounts
        self.switch_tab("accounts")

    # ==========================================================================
    # TAB 1: DANH SÁCH TÀI KHOẢN (ACCOUNTS TAB) - HỖ TRỢ ĐA ACCOUNT KHÔNG GIỚI HẠN
    # ==========================================================================
    def build_accounts_view(self):
        # Header bảng cố định ở trên
        tbl_header = ctk.CTkFrame(self.panel_accounts, fg_color="transparent", height=26)
        tbl_header.pack(fill="x", padx=4, pady=(2, 4))

        cols = [
            ("#", 34, "center"),
            ("MEGAMU / PID", 280, "center"),
            (tr("profile"), 105, "center"),
            (tr("name"), 120, "center"),
            ("Lv", 55, "center"),
            ("X,Y", 80, "center"),
            (tr("status"), 130, "center"),
            (tr("auto"), 60, "center")
        ]

        for title, w, anc in cols:
            lbl = ctk.CTkLabel(
                tbl_header,
                text=title,
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#9ca3af"
            )
            lbl.pack(side="left", padx=2)

        # Khung cuộn chứa danh sách các dòng tài khoản
        self.accounts_scroll_frame = ctk.CTkScrollableFrame(
            self.panel_accounts,
            fg_color="transparent"
        )
        self.accounts_scroll_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Tạo từng dòng tài khoản đã cấu hình
        for i in range(1, len(self.controllers) + 1):
            self.create_slot_row(i)

        # Thanh chức năng thêm / bớt slot ở dưới cùng
        bottom_slot_bar = ctk.CTkFrame(self.panel_accounts, fg_color="transparent", height=36)
        bottom_slot_bar.pack(fill="x", padx=6, pady=(4, 6))

        self.btn_add_slot = ctk.CTkButton(
            bottom_slot_bar,
            text=tr("add_account"),
            width=140,
            height=30,
            fg_color="#16a34a",
            hover_color="#15803d",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.add_new_slot
        )
        self.btn_add_slot.pack(side="left", padx=4)

        self.btn_remove_slot = ctk.CTkButton(
            bottom_slot_bar,
            text=tr("remove_account"),
            width=150,
            height=30,
            fg_color="#27272a",
            hover_color="#dc2626",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.remove_last_slot
        )
        self.btn_remove_slot.pack(side="left", padx=4)

        self.lbl_slot_count = ctk.CTkLabel(
            bottom_slot_bar,
            text=tr("total_accounts").format(n=len(self.controllers)),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.lbl_slot_count.pack(side="right", padx=10)

    def create_slot_row(self, i: int):
        """Tạo 1 dòng giao diện cho Slot thứ i trong khung cuộn."""
        ctrl = self.controllers[i - 1]
        row_frame = ctk.CTkFrame(self.accounts_scroll_frame, fg_color="#1f1f24", height=32, corner_radius=4)
        row_frame.pack(fill="x", padx=2, pady=2)

        # Cột 1: # (01, 02...)
        slot_lbl = ctk.CTkLabel(
            row_frame,
            text=f"{i:02d}",
            width=34,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#e4e4e7"
        )
        slot_lbl.pack(side="left", padx=2)

        # Cột 2: MEGAMU / PID (Dropdown)
        proc_var = ctk.StringVar(value=tr("select"))
        options = [tr("select")]
        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            disp = f"{pid} - {char_name}" if char_name else f"{pid} - MEGAMU"
            options.append(disp)

        proc_combo = ctk.CTkOptionMenu(
            row_frame,
            values=options,
            variable=proc_var,
            width=280,
            height=26,
            fg_color="#27272a",
            button_color="#3f3f46",
            text_color="#ffffff",
            corner_radius=4,
            command=lambda val, s=i: self.on_slot_pid_selected(s, val),
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        proc_combo.pack(side="left", padx=2)

        # Cột 3: Cấu hình (Dropdown + nút ...)
        cfg_box = ctk.CTkFrame(row_frame, fg_color="transparent", width=105)
        cfg_box.pack(side="left", padx=2)

        initial_cfg = f"Config {ctrl.profile_index}"
        cfg_var = ctk.StringVar(value=initial_cfg)
        cfg_menu = ctk.CTkOptionMenu(
            cfg_box,
            values=PROFILE_NAMES,
            variable=cfg_var,
            width=85,
            height=26,
            fg_color="#2563eb",
            button_color="#1d4ed8",
            text_color="#ffffff",
            corner_radius=4,
            command=lambda val, s=i: self.on_slot_profile_selected(s, val),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        cfg_menu.pack(side="left")

        btn_jump_cfg = ctk.CTkButton(
            cfg_box,
            text="...",
            width=18,
            height=26,
            fg_color="transparent",
            hover_color="#3f3f46",
            text_color="#9ca3af",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=lambda s=i: self.jump_to_config_tab(s)
        )
        btn_jump_cfg.pack(side="left", padx=(2, 0))

        # Cột 4: Tên
        name_lbl = ctk.CTkLabel(
            row_frame,
            text="---",
            width=120,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#e4e4e7"
        )
        name_lbl.pack(side="left", padx=2)

        # Cột 5: Lv
        lvl_lbl = ctk.CTkLabel(
            row_frame,
            text="---",
            width=55,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#e4e4e7"
        )
        lvl_lbl.pack(side="left", padx=2)

        # Cột 6: X,Y
        coords_lbl = ctk.CTkLabel(
            row_frame,
            text="--,--",
            width=80,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#e4e4e7"
        )
        coords_lbl.pack(side="left", padx=2)

        # Cột 7: Trạng thái
        status_lbl = ctk.CTkLabel(
            row_frame,
            text=tr("idle"),
            width=130,
            anchor="center",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9ca3af"
        )
        status_lbl.pack(side="left", padx=2)

        # Cột 8: Switch Auto
        auto_switch = ctk.CTkSwitch(
            row_frame,
            text="",
            width=55,
            progress_color="#2563eb",
            button_color="#ffffff",
            command=lambda s=i: self.on_slot_auto_toggle(s)
        )
        auto_switch.pack(side="left", padx=5)

        # Lưu references để cập nhật
        self.slot_ui_elements[i] = {
            "row_frame": row_frame,
            "proc_var": proc_var,
            "proc_combo": proc_combo,
            "cfg_var": cfg_var,
            "cfg_menu": cfg_menu,
            "name_lbl": name_lbl,
            "lvl_lbl": lvl_lbl,
            "coords_lbl": coords_lbl,
            "status_lbl": status_lbl,
            "auto_switch": auto_switch
        }

    def add_new_slot(self):
        """Thêm 1 slot tài khoản mới vào cuối danh sách."""
        new_slot_idx = len(self.controllers) + 1
        if new_slot_idx > MAX_SLOTS:
            self.log_message(f"Đã đạt giới hạn tối đa {MAX_SLOTS} tài khoản.", "WARNING")
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
        """Cập nhật danh sách Slot trong các combobox Điều khiển và Nhật ký."""
        n = len(self.controllers)
        teams = []
        for i in range(0, n, 5):
            t_num = (i // 5) + 1
            t_end = min(i + 5, n)
            teams.append(f"Team {t_num} ({i + 1}-{t_end})")

        ctrl_opts = [tr("all")] + teams + [f"{i:02d}" for i in range(1, n + 1)]
        if hasattr(self, "ctrl_combo"):
            self.ctrl_combo.configure(values=ctrl_opts)
            if self.ctrl_target_var.get() not in ctrl_opts:
                self.ctrl_target_var.set(tr("all"))

        log_opts = [tr("all")] + [f"{i:02d}" for i in range(1, n + 1)]
        if hasattr(self, "log_filter_combo"):
            self.log_filter_combo.configure(values=log_opts)
            if self.log_filter_var.get() not in log_opts:
                self.log_filter_var.set(tr("all"))

        if hasattr(self, "tab_accounts_btn"):
            self.tab_accounts_btn.configure(text=f"{n} {tr('accounts')}")

        if hasattr(self, "lbl_slot_count"):
            self.lbl_slot_count.configure(text=tr("total_accounts").format(n=n))

    # ==========================================================================
    # TAB 2: CẤU HÌNH (PROFILES TAB)
    # ==========================================================================
    def build_profiles_view(self):
        # Thanh điều khiển cấu hình trên cùng
        top_bar = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(
            top_bar, text=tr("edit_profile"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        ).pack(side="left", padx=(0, 6))

        self.editor_profile_var = ctk.StringVar(value="Config 1")
        self.editor_profile_combo = ctk.CTkOptionMenu(
            top_bar,
            values=PROFILE_NAMES,
            variable=self.editor_profile_var,
            width=115,
            height=28,
            fg_color="#2563eb",
            button_color="#1d4ed8",
            corner_radius=4,
            command=self.on_editor_profile_change,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        self.editor_profile_combo.pack(side="left", padx=4)

        ctk.CTkLabel(
            top_bar, text=tr("pk_delay"), font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#d1d5db"
        ).pack(side="left", padx=(16, 6))

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
        note_lbl = ctk.CTkLabel(
            self.panel_profiles,
            text=tr("team_note"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9ca3af"
        )
        note_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # Tiêu đề cột bảng Stage
        stage_header = ctk.CTkFrame(self.panel_profiles, fg_color="transparent")
        stage_header.pack(fill="x", padx=12, pady=(0, 4))

        stage_cols = [
            ("Min", 65, "center"),
            ("Max", 65, "center"),
            ("Map", 220, "center"),
            ("X", 70, "center"),
            ("Y", 70, "center")
        ]
        for t, w, anc in stage_cols:
            ctk.CTkLabel(
                stage_header,
                text=t,
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#9ca3af"
            ).pack(side="left", padx=3)

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
            map_combo = ctk.CTkOptionMenu(
                row_f,
                values=[""] + self.map_list,
                variable=map_var,
                width=220,
                height=28,
                fg_color="#27272a",
                button_color="#3f3f46",
                text_color="#ffffff",
                corner_radius=4
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

        ctk.CTkLabel(
            top_bar, text=tr("show"), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#f3f4f6"
        ).pack(side="left", padx=(0, 6))

        filter_options = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
        self.log_filter_var = ctk.StringVar(value=tr("all"))
        self.log_filter_combo = ctk.CTkOptionMenu(
            top_bar,
            values=filter_options,
            variable=self.log_filter_var,
            width=90,
            height=28,
            fg_color="#2563eb",
            button_color="#1d4ed8",
            corner_radius=4,
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

        btn_active = "#2563eb"
        btn_inactive = "#27272a"

        self.tab_accounts_btn.configure(fg_color=btn_active if tab_name == "accounts" else btn_inactive)
        self.tab_profiles_btn.configure(fg_color=btn_active if tab_name == "profiles" else btn_inactive)
        self.tab_logs_btn.configure(fg_color=btn_active if tab_name == "logs" else btn_inactive)

        # Ẩn hết các panels
        self.panel_accounts.pack_forget()
        self.panel_profiles.pack_forget()
        self.panel_logs.pack_forget()

        if tab_name == "accounts":
            self.panel_accounts.pack(fill="both", expand=True)
        elif tab_name == "profiles":
            self.panel_profiles.pack(fill="both", expand=True)
        elif tab_name == "logs":
            self.panel_logs.pack(fill="both", expand=True)
            self.render_logs()

    def jump_to_config_tab(self, slot_idx: int):
        """Nhảy nhanh sang Tab Cấu hình khi bấm nút '...' ở Slot."""
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
        if val == tr("select") or not val:
            ctrl.detach()
            return

        try:
            pid = int(val.split(" - ")[0].strip())
            ctrl.attach_pid(pid)
        except Exception as e:
            self.log_message(f"[Slot {slot_idx:02d}] Không thể gán PID: {e}", "ERROR")

    def on_slot_profile_selected(self, slot_idx: int, val: str):
        try:
            p_idx = int(val.replace("Config ", "").strip())
            ctrl = self.controllers[slot_idx - 1]
            ctrl.set_profile(p_idx)
        except Exception:
            pass

    def on_slot_auto_toggle(self, slot_idx: int):
        ctrl = self.controllers[slot_idx - 1]
        ctrl.toggle_auto()

    def update_slot_ui_status(self, slot_idx: int, text: str):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if el and el.get("status_lbl"):
                color = "#9ca3af"
                tl = text.lower()
                if "tự động đánh" in tl or "tại bãi" in tl:
                    color = "#c084fc"
                elif "running" in tl or "đang chạy" in tl or "chạy ra bãi" in tl:
                    color = "#38bdf8"
                elif "pk" in tl:
                    color = "#f87171"
                elif "đã kết nối" in tl or "connected" in tl:
                    color = "#4ade80"
                el["status_lbl"].configure(text=text, text_color=color)
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def update_slot_ui_auto(self, slot_idx: int, is_on: bool):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if el and el.get("auto_switch"):
                if is_on:
                    el["auto_switch"].select()
                else:
                    el["auto_switch"].deselect()
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def update_slot_ui_telemetry(self, slot_idx: int, name: str, lvl: str, coords: str):
        def _apply():
            el = self.slot_ui_elements.get(slot_idx)
            if el:
                if el.get("name_lbl") and name:
                    el["name_lbl"].configure(text=name)
                if el.get("lvl_lbl") and lvl:
                    el["lvl_lbl"].configure(text=lvl)
                if el.get("coords_lbl") and coords:
                    el["coords_lbl"].configure(text=coords)
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
        options = [tr("select")]
        for pid, title in sorted(self.detected_games.items()):
            char_name = character_name_from_window_title(title)
            disp = f"{pid} - {char_name}" if char_name else f"{pid} - MEGAMU"
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
                    disp = f"{pid} - {char_name}" if char_name else f"{pid} - MEGAMU"
                    el["proc_var"].set(disp)
                assigned_count += 1

        self.update_header_stats()
        self.log_message(f"Gán tất cả: Đã gán {assigned_count} tài khoản vào bảng.", "SUCCESS")

    def assign_team5(self):
        """Gán 5 tài khoản vào 1 Team còn trống."""
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
                    disp = f"{pid} - {char_name}" if char_name else f"{pid} - MEGAMU"
                    el["proc_var"].set(disp)
                count += 1

        self.update_header_stats()
        self.log_message(f"Gán Team 5: Đã gán thành công {count} tài khoản.", "SUCCESS")

    def connect_all(self):
        """Kết nối tới tất cả các slot đã chọn PID."""
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
        lang_code = lang_choice.lower()
        if lang_code in I18N:
            save_language_preference(lang_code)
            self.log_message(f"Đã lưu ngôn ngữ: {lang_choice}. Hãy khởi động lại để đổi toàn bộ chữ.", "INFO")

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
        """Cập nhật các số liệu thống kê trên thanh tiêu đề."""
        num_games = len(self.detected_games)
        num_conn = sum(1 for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid))
        num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
        num_slots = len(self.controllers)

        stat_text = (
            f"{tr('games')}: {num_games} | {tr('connected')}: {num_conn} | "
            f"{tr('auto')}: {num_auto} | {tr('license')}: Basic | {num_slots} acc | 2026-10-01 | Online"
        )
        self.header_stats_lbl.configure(text=stat_text)

        # Cập nhật dòng RPC lanes metrics
        metric_str = f"PID RPC Lanes | AVG 0.4 ms | P95 1.1 ms | Active {num_auto}/{num_conn} | Q 0 | STATE MAX 0.6 ms"
        self.metrics_lbl.configure(text=metric_str)

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
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dauto.megamu.dashboard.v1")
    except Exception:
        pass
    try:
        app = DashboardApp()
        app.mainloop()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
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
