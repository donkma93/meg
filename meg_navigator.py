#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Navigator (Python Edition)
======================================
Tác giả: Antigravity
Phiên bản: 1.0.0

Tính năng chính:
  1. Đọc trực tiếp bộ nhớ RAM qua IL2CPP Offsets (GameAssembly.dll):
     - Lấy tọa độ thực tế (X, Y) và Map ID trực tiếp từ tiến trình game mà không cần quét hình ảnh hay hook DLL.
  2. Tự động chuyển Map:
     - Gửi lệnh chat '/m <tên map>' qua Win32 Message (WM_CHAR), không kích hoạt phím tắt game.
     - Giám sát RAM cho tới khi chuyển map thành công mới bắt đầu di chuyển.
  3. Di chuyển ngầm - Không chiếm chuột vật lý:
     - Tính toán pixel Isometric chuẩn xác theo hệ trục tọa độ MU Online (Gốc 0,0 ở góc trên bên trái).
     - Kỹ thuật Micro-Sync nền: Đồng bộ đích click trong vài mili-giây và hoàn trả ngay chuột cho người dùng.
     - Chạy ổn định ngay cả khi cửa sổ game ở chế độ nền (un-focused/background).
  4. Thuật toán điều hướng khép kín (Closed-Loop RAM Feedback):
     - Tự động chia nhỏ lộ trình thành các bước ngắn (<= 5 ô).
     - Phân tích trục X (tăng/giảm) và trục Y (tăng/giảm).
     - So sánh liên tục khoảng cách tới đích cuối:
       + Nếu khoảng cách tăng (đi xa hơn) ➔ Tự động đảo hướng 180 độ ngay lập tức để kéo lại đích.
       + Nếu nhân vật bị khựng do vật cản/tường (> 1.4s) ➔ Tự động lách góc né vật cản (+45° / -45°).
     - Dừng chính xác khi khoảng cách tới đích <= 1 ô.
"""

import sys
import os
import json
import time
import math
import struct
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# Đảm bảo UTF-8 console output trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ==============================================================================
# Win32 API Definitions & 64-bit Strict Type Signatures
# ==============================================================================

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_NCHITTEST = 0x0084
WM_SETCURSOR = 0x0020
WM_MOUSEMOVE = 0x0200
WM_MOUSEACTIVATE = 0x0021
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
VK_RETURN = 0x0D

WA_ACTIVE = 1
HTCLIENT = 1
SW_SHOWNOACTIVATE = 4
SW_RESTORE = 9

class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_wchar * 256),
        ("szExePath", ctypes.c_wchar * 260)
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

# Thiết lập nghiêm ngặt kiểu dữ liệu x64 Win32
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.VirtualFreeEx.restype = wintypes.BOOL
kernel32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.VirtualProtectEx.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_char_p]
kernel32.GetProcAddress.restype = ctypes.c_void_p

user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

def ensure_desktop_attached():
    """Gắn thread Python hiện tại vào Interactive Input Desktop để các hàm Win32 hoạt động đầy đủ."""
    try:
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if not h_desk:
            h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

ensure_desktop_attached()

# ==============================================================================
# IL2CPP RVA & Offsets (GameAssembly.dll)
# ==============================================================================

GAME_TYPE_INFO_RVA = 0x5609F28
KLASS_STATIC_FIELDS_OFFSET = 0xB8
GAME_STATIC_INSTANCE_OFFSET = 0x8
GAME_PLAYER_OFFSET = 0x208
GAME_WORLD_OFFSET = 0x200
GAME_HELPER_UI_OFFSET = 0x1F8
GAME_MAP_SERVER_MOVE_OFFSET = 0xC0

BODY_CURRENT_COORD_OFFSET = 0x68
BODY_TARGET_COORD_OFFSET = 0x70
LAST_SERVER_COORD_OFFSET = 0x4E0
WORLD_SCENE_INDEX_OFFSET = 0x20
COORD_X_OFFSET = 0x10
COORD_Y_OFFSET = 0x14

# MuHelper (Auto Attack) Offsets
PLAYER_HELPER_OFFSET = 0x1E8       # UserHelper inside _Player
HELPER_IS_ACTIVE_OFFSET = 0x20     # uint8: 1 = Active (Đang tự đánh), 0 = Inactive
HELPER_IS_CONFIGURED_OFFSET = 0x21 # uint8: 1 = Configured
HELPER_ACTIVE_TIME_OFFSET = 0x24   # uint32: Số giây Helper đã chạy
HELPER_ACTIVE_MONEY_OFFSET = 0x28  # uint64: Lượng Zen đã tiêu
HELPER_OPTION_OFFSET = 0x30        # pointer: Option (Cấu hình kỹ năng, phạm vi, nhặt đồ)
HELPER_SWITCH_REQ_TIME_OFFSET = 0x38 # uint32: SwitchRequestTime

MAPS_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_INI_PATH = os.path.join(MAPS_DIR, "maps.ini")
MAPS_TXT_PATH = os.path.join(MAPS_DIR, "maps.txt")
CONFIG_FILE_PATH = os.path.join(MAPS_DIR, "maps_config.json")

MAP_CATALOG: Dict[int, str] = {}
POPULAR_MAPS: List[str] = []
MAP_ALIASES: Dict[str, str] = {}

def _set_fallback_maps():
    """Khởi tạo danh sách map mặc định khi chưa có file cấu hình nào"""
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    MAP_CATALOG = {
        0: "Lorencia", 1: "Dungeon", 2: "Devias", 3: "Noria", 4: "Lost Tower",
        5: "Exile", 6: "Arena", 7: "Atlans", 8: "Tarkan", 9: "Devil Square",
        10: "Icarus", 33: "Aida", 34: "Crywolf", 37: "Kanturu Remains",
        51: "Elbeland", 57: "Raklion", 63: "Vulcanus", 112: "Ferea",
        113: "Nixies Lake", 115: "Deep Dungeon 1", 116: "Swamp of Darkness", 117: "Kubera Mine"
    }
    POPULAR_MAPS = [
        "Lorencia", "Devias", "Noria", "Lost Tower", "Atlans", "Tarkan",
        "Arena", "Aida", "Crywolf", "Elbeland", "Raklion", "Vulcanus",
        "Ferea", "Nixies Lake", "Deep Dungeon 1", "Swamp of Darkness", "Kubera Mine"
    ]
    MAP_ALIASES = {
        "lost tower": "losttower",
        "kanturu remains": "kanturu",
        "kanturu ruins": "kanturu",
        "nixies lake": "nixies",
        "swamp of darkness": "swamp",
        "deep dungeon 1": "deepdungeon",
        "kubera mine": "kuberamine"
    }

def _load_maps_json(config_path: str = CONFIG_FILE_PATH) -> Tuple[Dict[int, str], List[str], Dict[str, str]]:
    """Đọc từ file JSON cũ nếu có"""
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_maps = data.get("maps", {})
            MAP_CATALOG = {int(k): str(v) for k, v in raw_maps.items()}
            POPULAR_MAPS = data.get("popular_maps", [])
            MAP_ALIASES = data.get("normalize_aliases", {})
            return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
        except Exception as e:
            print(f"[!] Lỗi khi đọc file json '{config_path}': {e}")
    _set_fallback_maps()
    return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

def save_maps_to_ini(
    file_path: str = MAPS_INI_PATH,
    popular_maps: Optional[List[str]] = None,
    map_catalog: Optional[Dict[int, str]] = None,
    aliases: Optional[Dict[str, str]] = None
) -> bool:
    """Lưu danh sách bản đồ ra file định dạng .ini (dễ mở và chỉnh sửa bằng Notepad)"""
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    if popular_maps is None:
        popular_maps = POPULAR_MAPS
    if map_catalog is None:
        map_catalog = MAP_CATALOG
    if aliases is None:
        aliases = MAP_ALIASES

    try:
        lines = [
            "; ==============================================================================",
            "; MEGAMU AUTO NAVIGATOR - CẤU HÌNH DANH SÁCH BẢN ĐỒ (.ini)",
            "; Bạn có thể chỉnh sửa trực tiếp bằng Notepad rồi bấm 'Tải lại' trên GUI.",
            "; ==============================================================================",
            "",
            "[POPULAR_MAPS]",
            "; Danh sách map hiển thị trong menu chọn nhanh trên giao diện",
            "; Bạn có thể nhập thêm map mới tại đây (mỗi dòng 1 map hoặc 1 = Tên Map)",
        ]
        for idx, m in enumerate(popular_maps, start=1):
            lines.append(f"{idx} = {m}")

        lines.extend([
            "",
            "[MAP_CATALOG]",
            "; Ánh xạ mã ID bản đồ đọc từ RAM sang Tên bản đồ (ID = Tên)",
        ])
        for mid in sorted(map_catalog.keys()):
            lines.append(f"{mid} = {map_catalog[mid]}")

        lines.extend([
            "",
            "[ALIASES]",
            "; Tên viết tắt hoặc chuẩn hóa khi gửi lệnh '/m <tên_map>'",
        ])
        for k, v in aliases.items():
            lines.append(f"{k} = {v}")

        lines.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True
    except Exception as e:
        print(f"[!] Lỗi khi lưu file INI '{file_path}': {e}")
        return False

def load_maps_from_ini(file_path: str = MAPS_INI_PATH) -> Tuple[Dict[int, str], List[str], Dict[str, str]]:
    """Đọc danh sách bản đồ từ file .ini"""
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    if not os.path.exists(file_path):
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

    catalog = dict(MAP_CATALOG) if MAP_CATALOG else {}
    popular = []
    aliases = dict(MAP_ALIASES) if MAP_ALIASES else {}
    current_section = ""

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].strip().upper()
                    continue

                if current_section in ("POPULAR_MAPS", "MAPS", "DANH_SACH_MAP"):
                    if "=" in line or ":" in line:
                        sep = "=" if "=" in line else ":"
                        _, val = line.split(sep, 1)
                        name = val.strip()
                    else:
                        name = line
                    if name and name not in popular:
                        popular.append(name)
                elif current_section in ("MAP_CATALOG", "CATALOG", "MAP_IDS"):
                    if "=" in line or ":" in line:
                        sep = "=" if "=" in line else ":"
                        k, v = line.split(sep, 1)
                        k, v = k.strip(), v.strip()
                        if k.isdigit() and v:
                            catalog[int(k)] = v
                elif current_section in ("ALIASES", "NORMALIZE_ALIASES"):
                    if "=" in line or ":" in line:
                        sep = "=" if "=" in line else ":"
                        k, v = line.split(sep, 1)
                        k, v = k.strip().lower(), v.strip().lower()
                        if k and v:
                            aliases[k] = v
                else:
                    # Trường hợp không có section header hoặc file ini đơn giản
                    if "=" in line or ":" in line:
                        sep = "=" if "=" in line else ":"
                        k, v = line.split(sep, 1)
                        k, v = k.strip(), v.strip()
                        if k.isdigit() and v:
                            catalog[int(k)] = v
                            if v not in popular:
                                popular.append(v)
                        else:
                            name = v if v else k
                            if name and name not in popular:
                                popular.append(name)
                    else:
                        if line not in popular:
                            popular.append(line)

        if popular:
            POPULAR_MAPS = popular
        if catalog:
            MAP_CATALOG = catalog
        if aliases:
            MAP_ALIASES = aliases
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    except Exception as e:
        print(f"[!] Lỗi khi đọc file INI '{file_path}': {e}")
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

def save_maps_to_txt(
    file_path: str = MAPS_TXT_PATH,
    popular_maps: Optional[List[str]] = None
) -> bool:
    """Lưu danh sách bản đồ ra file text .txt (mỗi dòng 1 tên bản đồ)"""
    global POPULAR_MAPS
    if popular_maps is None:
        popular_maps = POPULAR_MAPS
    try:
        lines = [
            "# ==============================================================================",
            "# MEGAMU AUTO NAVIGATOR - DANH SÁCH BẢN ĐỒ (.txt)",
            "# Mỗi dòng là 1 tên bản đồ. Bạn có thể mở Notepad thêm/bớt tùy ý rồi bấm lưu.",
            "# ==============================================================================",
            "",
        ]
        for m in popular_maps:
            if m and m.strip():
                lines.append(m.strip())
        lines.append("")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True
    except Exception as e:
        print(f"[!] Lỗi khi lưu file TXT '{file_path}': {e}")
        return False

def load_maps_from_txt(file_path: str = MAPS_TXT_PATH) -> Tuple[Dict[int, str], List[str], Dict[str, str]]:
    """Đọc danh sách bản đồ từ file .txt hoặc .text"""
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    if not os.path.exists(file_path):
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

    catalog = dict(MAP_CATALOG) if MAP_CATALOG else {}
    popular = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if "=" in line or ":" in line:
                    sep = "=" if "=" in line else ":"
                    k, v = line.split(sep, 1)
                    k, v = k.strip(), v.strip()
                    if k.isdigit() and v:
                        catalog[int(k)] = v
                        if v not in popular:
                            popular.append(v)
                    else:
                        name = v if v else k
                        if name and name not in popular:
                            popular.append(name)
                else:
                    if line not in popular:
                        popular.append(line)
        if popular:
            POPULAR_MAPS = popular
        if catalog:
            MAP_CATALOG = catalog
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES
    except Exception as e:
        print(f"[!] Lỗi khi đọc file TXT '{file_path}': {e}")
        return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

def save_all_maps(
    popular_maps: List[str],
    map_catalog: Optional[Dict[int, str]] = None,
    aliases: Optional[Dict[str, str]] = None,
    save_ini: bool = True,
    save_txt: bool = True
) -> bool:
    """Lưu danh sách map vào cả maps.ini và maps.txt để đồng bộ và tiện chỉnh sửa"""
    global POPULAR_MAPS, MAP_CATALOG, MAP_ALIASES
    valid_maps = []
    for m in popular_maps:
        cleaned = m.strip()
        if cleaned and cleaned not in valid_maps:
            valid_maps.append(cleaned)
    POPULAR_MAPS = valid_maps

    if map_catalog is not None:
        MAP_CATALOG = map_catalog
    if aliases is not None:
        MAP_ALIASES = aliases

    ok = True
    if save_ini:
        ok = save_maps_to_ini(MAPS_INI_PATH, POPULAR_MAPS, MAP_CATALOG, MAP_ALIASES) and ok
    if save_txt:
        ok = save_maps_to_txt(MAPS_TXT_PATH, POPULAR_MAPS) and ok
    return ok

def get_active_maps_file() -> str:
    """Trả về đường dẫn file cấu hình map đang được ưu tiên sử dụng"""
    if os.path.exists(MAPS_INI_PATH):
        return MAPS_INI_PATH
    if os.path.exists(MAPS_TXT_PATH):
        return MAPS_TXT_PATH
    if os.path.exists(CONFIG_FILE_PATH):
        return CONFIG_FILE_PATH
    return MAPS_INI_PATH

def load_maps_config(config_path: Optional[str] = None) -> Tuple[Dict[int, str], List[str], Dict[str, str]]:
    """
    Tải cấu hình Map từ file .ini, .txt hoặc .json.
    Ưu tiên:
    1. config_path nếu được chỉ định
    2. maps.ini nếu tồn tại
    3. maps.txt nếu tồn tại
    4. maps_config.json nếu tồn tại (đồng thời tự động tạo maps.ini và maps.txt)
    5. Cấu hình mặc định (đồng thời tự động tạo maps.ini và maps.txt)
    """
    global MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

    if config_path:
        ext = os.path.splitext(config_path)[1].lower()
        if ext == ".ini":
            return load_maps_from_ini(config_path)
        elif ext in (".txt", ".text"):
            return load_maps_from_txt(config_path)
        elif ext == ".json":
            return _load_maps_json(config_path)
        else:
            if os.path.exists(config_path):
                return load_maps_from_ini(config_path)

    # 1. maps.ini
    if os.path.exists(MAPS_INI_PATH):
        return load_maps_from_ini(MAPS_INI_PATH)

    # 2. maps.txt
    if os.path.exists(MAPS_TXT_PATH):
        return load_maps_from_txt(MAPS_TXT_PATH)

    # 3. maps_config.json
    if os.path.exists(CONFIG_FILE_PATH):
        cat, pop, ali = _load_maps_json(CONFIG_FILE_PATH)
        # Tự động xuất ra file maps.ini và maps.txt để người dùng tiện chỉnh sửa
        save_maps_to_ini(MAPS_INI_PATH, pop, cat, ali)
        save_maps_to_txt(MAPS_TXT_PATH, pop)
        return cat, pop, ali

    # 4. Fallback mặc định
    _set_fallback_maps()
    save_maps_to_ini(MAPS_INI_PATH, POPULAR_MAPS, MAP_CATALOG, MAP_ALIASES)
    save_maps_to_txt(MAPS_TXT_PATH, POPULAR_MAPS)
    return MAP_CATALOG, POPULAR_MAPS, MAP_ALIASES

# Tải cấu hình maps khi module được import
load_maps_config()

def normalize_map_name(name: str) -> str:
    clean = name.strip().lower()
    return MAP_ALIASES.get(clean, clean.replace(" ", ""))

# ==============================================================================
# RAM Reader Class
# ==============================================================================

@dataclass
class ClientLiveState:
    pid: int
    hwnd: int
    window_title: str
    char_name: str
    server: str
    map_id: Optional[int]
    map_name: str
    x: Optional[int]
    y: Optional[int]
    target_x: Optional[int]
    target_y: Optional[int]
    is_auto_attack: bool = False
    helper_active_time: int = 0
    level: Optional[int] = None
    resets: Optional[int] = None

class ProcessMemoryReader:
    _module_cache: Dict[int, int] = {}

    @staticmethod
    def get_module_base(pid: int, module_name: str = "GameAssembly.dll") -> Optional[int]:
        if pid in ProcessMemoryReader._module_cache:
            return ProcessMemoryReader._module_cache[pid]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
        if snap == -1 or snap == 0:
            return None

        try:
            entry = MODULEENTRY32W()
            entry.dwSize = ctypes.sizeof(MODULEENTRY32W)
            if kernel32.Module32FirstW(snap, ctypes.byref(entry)):
                while True:
                    if entry.szModule.lower() == module_name.lower():
                        base = entry.modBaseAddr
                        ProcessMemoryReader._module_cache[pid] = base
                        return base
                    if not kernel32.Module32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)
        return None

    @staticmethod
    def read_ptr(handle: int, addr: int) -> int:
        buf = ctypes.c_uint64()
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(read)):
            return buf.value
        return 0

    @staticmethod
    def read_i32(handle: int, addr: int) -> int:
        buf = ctypes.c_int32()
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(read)):
            return buf.value
        return 0

    @staticmethod
    def read_u8(handle: int, addr: int) -> int:
        buf = ctypes.c_uint8()
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(read)):
            return buf.value
        return 0

    @staticmethod
    def read_u32(handle: int, addr: int) -> int:
        buf = ctypes.c_uint32()
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(read)):
            return buf.value
        return 0

    @staticmethod
    def read_u64(handle: int, addr: int) -> int:
        buf = ctypes.c_uint64()
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(read)):
            return buf.value
        return 0

    @classmethod
    def read_helper_state(cls, pid: int) -> Optional[Tuple[bool, bool, int, int]]:
        """
        Đọc RAM IL2CPP trạng thái Tự Động Đánh (MuHelper):
        Returns: (is_active: bool, is_configured: bool, active_time_sec: int, active_money: int)
        """
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return None

        try:
            base = cls.get_module_base(pid)
            if not base:
                return None

            type_info = cls.read_ptr(handle, base + GAME_TYPE_INFO_RVA)
            if not type_info:
                return None

            static_fields = cls.read_ptr(handle, type_info + KLASS_STATIC_FIELDS_OFFSET)
            if not static_fields:
                return None

            game_instance = cls.read_ptr(handle, static_fields + GAME_STATIC_INSTANCE_OFFSET)
            if not game_instance:
                return None

            player_ptr = cls.read_ptr(handle, game_instance + GAME_PLAYER_OFFSET)
            if not player_ptr:
                return None

            helper_ptr = cls.read_ptr(handle, player_ptr + PLAYER_HELPER_OFFSET)
            if not helper_ptr:
                return None

            is_active = bool(cls.read_u8(handle, helper_ptr + HELPER_IS_ACTIVE_OFFSET))
            is_configured = bool(cls.read_u8(handle, helper_ptr + HELPER_IS_CONFIGURED_OFFSET))
            active_time = cls.read_u32(handle, helper_ptr + HELPER_ACTIVE_TIME_OFFSET)
            active_money = cls.read_u64(handle, helper_ptr + HELPER_ACTIVE_MONEY_OFFSET)

            return (is_active, is_configured, active_time, active_money)
        finally:
            kernel32.CloseHandle(handle)

    @classmethod
    def read_character_level(cls, pid: int) -> Optional[int]:
        r"""
        Đọc Level nhân vật thực tế hiện tại:
        - Phân tích Window Title regex r'\((\d+)(?:/(\d+)rr)?\)' (Chuẩn xác 100% cho mọi server MEGAMU có hệ thống reset)
        - Đọc RAM IL2CPP tại player_ptr + 0x030 / 0x034 (Level hiện tại của nhân vật)
        """
        # 1. Thử lấy level trực tiếp từ Window Title (Title client MEGAMU luôn cập nhật realtime theo level thực tế)
        title_lvl = cls._fallback_level_from_title(pid)
        if title_lvl is not None and 1 <= title_lvl <= 2000:
            return title_lvl

        # 2. Đọc trực tiếp từ bộ nhớ RAM IL2CPP
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return title_lvl

        try:
            base = cls.get_module_base(pid)
            if not base:
                return title_lvl

            type_info = cls.read_ptr(handle, base + GAME_TYPE_INFO_RVA)
            if not type_info:
                return title_lvl

            static_fields = cls.read_ptr(handle, type_info + KLASS_STATIC_FIELDS_OFFSET)
            if not static_fields:
                return title_lvl

            game_instance = cls.read_ptr(handle, static_fields + GAME_STATIC_INSTANCE_OFFSET)
            if not game_instance:
                return title_lvl

            player_ptr = cls.read_ptr(handle, game_instance + GAME_PLAYER_OFFSET)
            if not player_ptr:
                return title_lvl

            # player_ptr + 0x030 là level thực tế hiện tại của nhân vật trong RAM
            lvl_030 = cls.read_u32(handle, player_ptr + 0x030)
            if 1 <= lvl_030 <= 2000:
                return lvl_030

            lvl_034 = cls.read_u32(handle, player_ptr + 0x034)
            if 1 <= lvl_034 <= 2000:
                return lvl_034

            return title_lvl
        finally:
            kernel32.CloseHandle(handle)

    @classmethod
    def _fallback_level_from_title(cls, pid: int) -> Optional[int]:
        import re
        windows = WindowHelper.get_unity_windows()
        for p, hwnd, title, w, h in windows:
            if p == pid:
                m = re.search(r'\((\d+)(?:/(\d+)rr)?\)', title)
                if m:
                    return int(m.group(1))
        return None

    @classmethod
    def read_live_state(cls, pid: int) -> Optional[Tuple[Optional[int], str, Optional[int], Optional[int], Optional[int], Optional[int]]]:
        """Đọc RAM: (map_id, map_name, cur_x, cur_y, target_x, target_y)"""
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return None

        try:
            base = cls.get_module_base(pid)
            if not base:
                return None

            type_info = cls.read_ptr(handle, base + GAME_TYPE_INFO_RVA)
            if not type_info:
                return None

            static_fields = cls.read_ptr(handle, type_info + KLASS_STATIC_FIELDS_OFFSET)
            if not static_fields:
                return None

            game_instance = cls.read_ptr(handle, static_fields + GAME_STATIC_INSTANCE_OFFSET)
            if not game_instance:
                return None

            # Read World / Map
            map_id = None
            map_name = "Unknown"
            world_ptr = cls.read_ptr(handle, game_instance + GAME_WORLD_OFFSET)
            if world_ptr:
                scene_idx = cls.read_i32(handle, world_ptr + WORLD_SCENE_INDEX_OFFSET)
                if 0 <= scene_idx <= 255:
                    map_id = scene_idx
                    map_name = MAP_CATALOG.get(scene_idx, f"World {scene_idx}")

            # Read Player Coordinates
            cur_x, cur_y = None, None
            target_x, target_y = None, None

            player_ptr = cls.read_ptr(handle, game_instance + GAME_PLAYER_OFFSET)
            if player_ptr:
                tcoord_ptr = cls.read_ptr(handle, player_ptr + BODY_TARGET_COORD_OFFSET)
                if tcoord_ptr:
                    tx = cls.read_i32(handle, tcoord_ptr + COORD_X_OFFSET)
                    ty = cls.read_i32(handle, tcoord_ptr + COORD_Y_OFFSET)
                    if 0 <= tx <= 255 and 0 <= ty <= 255:
                        target_x, target_y = tx, ty

                for offset in (BODY_CURRENT_COORD_OFFSET, BODY_TARGET_COORD_OFFSET, LAST_SERVER_COORD_OFFSET):
                    coord_ptr = cls.read_ptr(handle, player_ptr + offset)
                    if not coord_ptr:
                        continue
                    cx = cls.read_i32(handle, coord_ptr + COORD_X_OFFSET)
                    cy = cls.read_i32(handle, coord_ptr + COORD_Y_OFFSET)
                    if 0 <= cx <= 255 and 0 <= cy <= 255:
                        if offset == LAST_SERVER_COORD_OFFSET and cx == 0 and cy == 0:
                            continue
                        cur_x, cur_y = cx, cy
                        break

            return (map_id, map_name, cur_x, cur_y, target_x, target_y)
        finally:
            kernel32.CloseHandle(handle)

# ==============================================================================
# Window Helper Class
# ==============================================================================

class WindowHelper:
    @staticmethod
    def get_unity_windows() -> List[Tuple[int, int, str, int, int]]:
        """Tìm tất cả cửa sổ UnityWndClass trên desktop."""
        ensure_desktop_attached()
        results = []

        def enum_proc(hwnd, lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if class_name.value.lower() == "unitywndclass":
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, 512)
                rect = RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                results.append((pid.value, hwnd, title.value, w, h))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        cb = WNDENUMPROC(enum_proc)

        h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
        if h_desk:
            user32.EnumDesktopWindows(h_desk, cb, 0)
            user32.CloseDesktop(h_desk)

        if not results:
            user32.EnumWindows(cb, 0)

        return results

    @staticmethod
    def find_window_for_pid(target_pid: int) -> Optional[Tuple[int, int, int]]:
        """Tìm HWND và (width, height) cho 1 PID cụ thể."""
        windows = WindowHelper.get_unity_windows()
        for pid, hwnd, title, w, h in windows:
            if pid == target_pid:
                # Nếu cửa sổ bị minimize hoặc kích thước 0, khôi phục nhẹ không chiếm tiêu điểm
                if user32.IsIconic(hwnd) or w <= 0 or h <= 0:
                    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                    time.sleep(0.08)
                    rect = RECT()
                    user32.GetClientRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                return (hwnd, w, h)
        return None

# ==============================================================================
# Unity Pure-Background Hook Engine (GetCursorPos IAT Hook)
# ==============================================================================

class UnityBackgroundHook:
    """
    Cơ chế Hook ngầm IAT GetCursorPos (Unity Engine):
    - Đón đầu lời gọi GetCursorPos() của Unity ngay trong RAM.
    - Cung cấp tọa độ click ảo khi bot gửi lệnh bước chạy ngầm.
    - Trả về tọa độ chuột thật của Windows khi không click.
    - TUYỆT ĐỐI KHÔNG CHẠM VÀO CON TRỎ CHUỘT HỆ THỐNG CỦA NGƯỜI DÙNG!
    - KHÔNG DÙNG SetCursorPos, KHÔNG CƯỚP TIÊU ĐIỂM (NO ACTIVATE/FOCUS)!
    """
    _instances: Dict[int, 'UnityBackgroundHook'] = {}

    def __init__(self, pid: int):
        self.pid = pid
        self.handle: Optional[int] = None
        self.alloc_addr: Optional[int] = None
        self.iat_addr: Optional[int] = None
        self.orig_fn: Optional[int] = None
        self.is_ready: bool = False
        self._install()

    @classmethod
    def get_instance(cls, pid: int) -> 'UnityBackgroundHook':
        if pid not in cls._instances or not cls._instances[pid].is_ready:
            cls._instances[pid] = cls(pid)
        return cls._instances[pid]

    def _read_mem(self, addr: int, size: int) -> bytes:
        buf = (ctypes.c_char * size)()
        read = ctypes.c_size_t()
        kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read))
        return bytes(buf)

    def _install(self):
        try:
            self.handle = kernel32.OpenProcess(0x1F0FFF, False, self.pid)
            if not self.handle:
                return

            snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid)
            entry = MODULEENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            up_base = 0
            if kernel32.Module32FirstW(snap, ctypes.byref(entry)):
                while True:
                    if entry.szModule.lower() == 'unityplayer.dll':
                        up_base = entry.modBaseAddr
                        break
                    if not kernel32.Module32NextW(snap, ctypes.byref(entry)):
                        break
            kernel32.CloseHandle(snap)

            if not up_base:
                return

            dos = self._read_mem(up_base, 0x40)
            e_lfanew = int.from_bytes(dos[0x3C:0x40], 'little')
            nt = self._read_mem(up_base + e_lfanew, 0x150)
            import_rva = int.from_bytes(nt[0x18 + 0x78 : 0x18 + 0x78 + 4], 'little')
            curr = up_base + import_rva

            iat_addr = None
            orig_fn = None
            while True:
                desc = self._read_mem(curr, 20)
                if not any(desc):
                    break
                oft = int.from_bytes(desc[0:4], 'little')
                name_rva = int.from_bytes(desc[12:16], 'little')
                ft = int.from_bytes(desc[16:20], 'little')
                mod_name = self._read_mem(up_base + name_rva, 64).split(b'\x00')[0].decode('latin1', 'ignore')
                if 'user32' in mod_name.lower():
                    thunk_idx = 0
                    while True:
                        thunk_ptr = up_base + ft + thunk_idx * 8
                        orig_ptr = up_base + oft + thunk_idx * 8 if oft else thunk_ptr
                        val = int.from_bytes(self._read_mem(thunk_ptr, 8), 'little')
                        orig_val = int.from_bytes(self._read_mem(orig_ptr, 8), 'little')
                        if val == 0:
                            break
                        if not (orig_val & (1 << 63)):
                            fn_name = self._read_mem(up_base + orig_val + 2, 64).split(b'\x00')[0].decode('latin1', 'ignore')
                            if fn_name.lower() == 'getcursorpos':
                                iat_addr = thunk_ptr
                                orig_fn = val
                                break
                        thunk_idx += 1
                    if iat_addr:
                        break
                curr += 20

            if not iat_addr or not orig_fn:
                return

            self.iat_addr = iat_addr

            user32_mod = kernel32.GetModuleHandleW('user32.dll')
            real_user32_get_cursor = kernel32.GetProcAddress(user32_mod, b'GetCursorPos')
            actual_orig_fn = orig_fn if (orig_fn and orig_fn > 0x7FFF00000000) else real_user32_get_cursor

            alloc_addr = kernel32.VirtualAllocEx(self.handle, None, 4096, 0x1000 | 0x2000, 0x40)
            if not alloc_addr:
                return

            self.alloc_addr = alloc_addr

            code_template = (
                b'\x48\x85\xC9'                 # 0x20: test rcx, rcx
                b'\x74\x22'                     # 0x23: jz to_orig
                b'\x8B\x05\xD5\xFF\xFF\xFF'     # 0x25: mov eax, [rip - 0x2B] (target 0x00)
                b'\x83\xF8\x01'                 # 0x2B: cmp eax, 1
                b'\x75\x17'                     # 0x2E: jne to_orig
                b'\x8B\x05\xCE\xFF\xFF\xFF'     # 0x30: mov eax, [rip - 0x32] (target 0x04)
                b'\x89\x01'                     # 0x36: mov [rcx], eax
                b'\x8B\x05\xCA\xFF\xFF\xFF'     # 0x38: mov eax, [rip - 0x36] (target 0x08)
                b'\x89\x41\x04'                 # 0x3E: mov [rcx+4], eax
                b'\xB8\x01\x00\x00\x00'         # 0x41: mov eax, 1
                b'\xC3'                         # 0x46: ret
                b'\xFF\x25\xC3\xFF\xFF\xFF'     # 0x47: jmp qword ptr [rip - 0x3D] (target 0x10)
            )

            data_header = struct.pack('<IIIIQ', 0, 0, 0, 0, actual_orig_fn)
            payload = data_header.ljust(0x20, b'\x00') + code_template

            written = ctypes.c_size_t()
            kernel32.WriteProcessMemory(self.handle, ctypes.c_void_p(alloc_addr), payload, len(payload), ctypes.byref(written))

            hook_entry = alloc_addr + 0x20
            old_protect = wintypes.DWORD()
            kernel32.VirtualProtectEx(self.handle, ctypes.c_void_p(iat_addr), 8, 0x04, ctypes.byref(old_protect))
            hook_val = ctypes.c_uint64(hook_entry)
            kernel32.WriteProcessMemory(self.handle, ctypes.c_void_p(iat_addr), ctypes.byref(hook_val), 8, ctypes.byref(written))
            kernel32.VirtualProtectEx(self.handle, ctypes.c_void_p(iat_addr), 8, old_protect.value, ctypes.byref(old_protect))

            self.is_ready = True
        except Exception:
            self.is_ready = False

    def send_click(self, hwnd: int, client_x: int, client_y: int, duration_ms: int = 35) -> bool:
        """
        Gửi click ngầm 100% không chạm chuột vật lý:
        - Bơm tọa độ pixel đích vào game RAM
        - Gửi PostMessage WM_LBUTTONDOWN/UP
        - Không SetCursorPos, không cướp tiêu điểm!
        """
        if not self.is_ready or not self.handle or not self.alloc_addr:
            return False

        pt = POINT(client_x, client_y)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))

        # 1. Bật tọa độ ảo trong RAM game
        spoof_data = struct.pack('<III', 1, pt.x, pt.y)
        written = ctypes.c_size_t()
        kernel32.WriteProcessMemory(self.handle, ctypes.c_void_p(self.alloc_addr), spoof_data, 12, ctypes.byref(written))

        # 2. Gửi PostMessage ngầm hoàn toàn
        lparam = ((client_y & 0xFFFF) << 16) | (client_x & 0xFFFF)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)

        time.sleep(max(duration_ms, 25) / 1000.0)

        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)

        # 3. Tắt tọa độ ảo, trả lại chuột hệ thống
        time.sleep(0.02)
        deact_data = struct.pack('<I', 0)
        kernel32.WriteProcessMemory(self.handle, ctypes.c_void_p(self.alloc_addr), deact_data, 4, ctypes.byref(written))
        return True

# ==============================================================================
# Background Input Simulator
# ==============================================================================

class BackgroundInputSimulator:
    @staticmethod
    def make_lparam(x: int, y: int) -> int:
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    @staticmethod
    def send_char(hwnd: int, char: str, delay_s: float = 0.03):
        scan_code = user32.MapVirtualKeyW(ord(char), 0)
        lparam = 1 | (scan_code << 16)
        user32.PostMessageW(hwnd, WM_CHAR, ord(char), lparam)
        if delay_s > 0:
            time.sleep(delay_s)

    @staticmethod
    def send_key(hwnd: int, vk_code: int, duration_s: float = 0.04):
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        lparam_down = 1 | (scan_code << 16)
        lparam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, lparam_down)
        if duration_s > 0:
            time.sleep(duration_s)
        user32.PostMessageW(hwnd, WM_KEYUP, vk_code, lparam_up)

    @classmethod
    def send_chat_command(cls, hwnd: int, command: str) -> bool:
        """Gửi lệnh chat (ví dụ '/m devias') an toàn bằng cách kích hoạt chat và gửi ký tự."""
        ensure_desktop_attached()

        cur_tid = kernel32.GetCurrentThreadId()
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)

        attached_fg = False
        attached_target = False
        try:
            # Gắn thread input để đảm bảo quyền chiếm tiêu điểm bàn phím cho client game
            if fg_tid and fg_tid != cur_tid:
                attached_fg = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
            if target_tid and target_tid != cur_tid:
                attached_target = bool(user32.AttachThreadInput(cur_tid, target_tid, True))

            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
            time.sleep(0.18)

            # 1. Bật khung chat bằng phím Enter (keybd_event gửi sự kiện phần cứng chuẩn OS để Unity mở InputField)
            user32.keybd_event(VK_RETURN, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(VK_RETURN, 0, 2, 0)
            time.sleep(0.35)

            # 2. Gửi các ký tự lệnh qua WM_CHAR
            for ch in command:
                user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 1)
                time.sleep(0.03)
            time.sleep(0.20)

            # 3. Gửi phím Enter để thực thi lệnh
            user32.keybd_event(VK_RETURN, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(VK_RETURN, 0, 2, 0)
            time.sleep(0.20)
            return True
        finally:
            try:
                if attached_target:
                    user32.AttachThreadInput(cur_tid, target_tid, False)
                if attached_fg:
                    user32.AttachThreadInput(cur_tid, fg_tid, False)
            except Exception:
                pass

    @classmethod
    def pure_background_click(cls, hwnd: int, client_x: int, client_y: int, duration_ms: int = 70) -> bool:
        """
        Gửi click chuột trực tiếp vào hàng đợi thông điệp của cửa sổ game bằng Win32 PostMessage.
        TUYỆT ĐỐI KHÔNG CHẠM VÀO CON TRỎ CHUỘT VẬT LÝ CỦA HỆ THỐNG:
        - Không dùng SetCursorPos
        - Không dùng mouse_event
        - Chuột của người dùng hoàn toàn tự do, không bị giật, không bị chỉ lung tung!
        """
        ensure_desktop_attached()

        lparam = cls.make_lparam(client_x, client_y)

        user32.SendMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
        user32.SendMessageW(hwnd, WM_SETFOCUS, 0, 0)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)

        time.sleep(max(duration_ms, 30) / 1000.0)

        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        return True

    @classmethod
    def micro_sync_click(cls, hwnd: int, client_x: int, client_y: int, duration_ms: int = 30) -> bool:
        """
        Micro-Sync Click chuyên biệt cho Unity Engine (MEGAMU):
        1. Lưu tọa độ chuột vật lý hiện tại của người dùng.
        2. Chuyển client_x, client_y thành Screen Pixel trên màn hình.
        3. Tạm thời dịch chuyển con trỏ tới điểm click đích (để GetCursorPos() của Unity nhận đúng).
        4. Gửi các thông điệp kích hoạt + PostMessage DOWN/UP (giữ trong khoảng 25-30ms).
        5. NGAY LẬP TỨC trả con trỏ về vị trí ban đầu của người dùng.
        -> Người dùng hoàn toàn không cảm nhận được chuột bị giật (vì chỉ mất 25-30ms),
           nhưng Unity Engine sẽ đọc đúng vị trí mục tiêu thay vì bị chuột vật lý chi phối!
        """
        ensure_desktop_attached()

        # 1. Lưu vị trí con trỏ thật của người dùng
        orig_pt = POINT()
        user32.GetCursorPos(ctypes.byref(orig_pt))

        # 2. Quy đổi sang tọa độ Screen Pixel
        target_pt = POINT(client_x, client_y)
        user32.ClientToScreen(hwnd, ctypes.byref(target_pt))

        # Tạm thời đặt con trỏ tới điểm click
        user32.SetCursorPos(target_pt.x, target_pt.y)

        lparam = cls.make_lparam(client_x, client_y)
        screen_lparam = cls.make_lparam(target_pt.x, target_pt.y)

        # 3. Kích hoạt và gửi thông điệp chuột
        user32.SendMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
        user32.SendMessageW(hwnd, WM_SETFOCUS, 0, 0)
        user32.SendMessageW(hwnd, WM_NCHITTEST, 0, screen_lparam)
        user32.SendMessageW(hwnd, WM_SETCURSOR, hwnd, (WM_LBUTTONDOWN << 16) | HTCLIENT)

        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)

        time.sleep(max(duration_ms, 25) / 1000.0)

        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        user32.SendMessageW(hwnd, WM_SETCURSOR, hwnd, (WM_MOUSEMOVE << 16) | HTCLIENT)

        # 4. Trả con trỏ chuột về vị trí cũ ngay lập tức
        user32.SetCursorPos(orig_pt.x, orig_pt.y)
        return True

# ==============================================================================
# Isometric Projection & Navigation Engine
# ==============================================================================

def get_direction_description(dx: int, dy: int) -> str:
    """Mô tả hướng di chuyển theo góc hình học MU Online chuẩn"""
    if dx == 0 and dy == 0:
        return "Tại chỗ (0, 0)"
    vx = (dx + dy) * 1.0
    vy = (dx - dy) * 0.55
    deg = (math.atan2(vy, vx) * 180.0 / math.pi) % 360.0

    if deg >= 337.5 or deg < 22.5:
        return "Phải (+X, +Y)"
    elif 22.5 <= deg < 67.5:
        return "Phải-Xuống / Đông (+X)"
    elif 67.5 <= deg < 112.5:
        return "Xuống (+X, -Y)"
    elif 112.5 <= deg < 157.5:
        return "Trái-Xuống / Nam (-Y)"
    elif 157.5 <= deg < 202.5:
        return "Trái (-X, -Y)"
    elif 202.5 <= deg < 247.5:
        return "Trái-Lên / Tây (-X)"
    elif 247.5 <= deg < 292.5:
        return "Lên (-X, +Y)"
    else:
        return "Phải-Lên / Bắc (+Y)"

def game_coord_to_screen_pixel(
    cur_x: int, cur_y: int,
    target_x: int, target_y: int,
    client_w: int, client_h: int,
    camera_angle_deg: float = 0.0,
    step_scale: float = 24.0,
    max_radius_ratio: float = 0.35
) -> Tuple[int, int]:
    """
    Chuyển đổi vector chênh lệch tọa độ (dx, dy) sang pixel trên màn hình game (px, py).
    Áp dụng hệ phương trình chiếu Isometric chuẩn xác MU Online:
      vx = (dx + dy) * 1.0
      vy = (dx - dy) * 0.55
    """
    if client_w <= 0: client_w = 1024
    if client_h <= 0: client_h = 768

    cx = client_w // 2
    cy = client_h // 2 + 15

    dx = target_x - cur_x
    dy = target_y - cur_y

    if dx == 0 and dy == 0:
        return (cx, cy)

    base_vx = (dx + dy) * 1.0
    base_vy = (dx - dy) * 0.55

    vx = base_vx
    vy = base_vy

    if abs(camera_angle_deg) > 0.01:
        rad = camera_angle_deg * (math.pi / 180.0)
        cos_val = math.cos(rad)
        sin_val = math.sin(rad)
        vx = base_vx * cos_val - base_vy * sin_val
        vy = base_vx * sin_val + base_vy * cos_val

    dist = math.sqrt(vx * vx + vy * vy)
    max_radius = max(120.0, client_h * max_radius_ratio)
    if dist < 4.0:
        radius = max(35.0, dist * 22.0)
    else:
        min_radius = max(90.0, client_h * 0.09)
        radius = min(max_radius, max(min_radius, dist * step_scale))

    norm_x = vx / dist
    norm_y = vy / dist

    px = int(round(cx + norm_x * radius))
    py = int(round(cy + norm_y * radius))

    px = max(40, min(client_w - 40, px))
    py = max(60, min(client_h - 80, py))
    return (px, py)

def subdivide_path(start_x: int, start_y: int, end_x: int, end_y: int, max_step: int = 2) -> List[Tuple[int, int]]:
    """
    Chia đoạn đường thành các bước siêu ngắn thẳng hướng (<= max_step ô, mặc định 2 ô)
    """
    dx = end_x - start_x
    dy = end_y - start_y
    max_delta = max(abs(dx), abs(dy))

    if max_delta <= max_step:
        return [(end_x, end_y)]

    steps = []
    count = math.ceil(max_delta / max_step)
    for i in range(1, count + 1):
        ratio = i / count
        px = int(round(start_x + dx * ratio))
        py = int(round(start_y + dy * ratio))
        steps.append((px, py))
    return steps

# ==============================================================================
# Main Auto-Navigator Controller
# ==============================================================================

class MegNavigator:
    def __init__(self, pid: int, camera_angle_deg: float = 0.0):
        self.pid = pid
        self.camera_angle_deg = camera_angle_deg

        win_info = WindowHelper.find_window_for_pid(pid)
        if not win_info:
            raise RuntimeError(f"Không tìm thấy cửa sổ UnityWndClass cho PID {pid}!")

        self.hwnd, self.client_w, self.client_h = win_info
        self.hook = UnityBackgroundHook.get_instance(pid)

    def get_live_state(self):
        return ProcessMemoryReader.read_live_state(self.pid)

    def get_helper_state(self) -> Optional[Tuple[bool, bool, int, int]]:
        """Đọc RAM trạng thái Auto Đánh (MuHelper): (is_active, is_configured, active_time, active_money)"""
        return ProcessMemoryReader.read_helper_state(self.pid)

    def get_character_level(self) -> Optional[int]:
        """Đọc Level hiện tại của nhân vật từ RAM"""
        return ProcessMemoryReader.read_character_level(self.pid)

    def enable_auto_attack(self, log_callback=None, max_wait_sec: float = 3.5) -> bool:
        """
        Kích hoạt tự động đánh (MuHelper) chạy ngầm 100%:
        - Đợi ngắn 0.35s để nhân vật dừng hẳn bước chạy và giải phóng HUD click.
        - Kiểm tra trạng thái RAM: Nếu đã BẬT (is_active == True) -> Giữ nguyên, không nhấp lại.
        - Nếu chưa BẬT: Gửi click ngầm vào nút Play trên HUD tại tọa độ chuẩn (341, 88).
        - Nếu chưa ăn, thử tiếp click tại tâm nút (346, 88) và Micro-Sync fallback.
        - Giám sát RAM tới khi is_active == True.
        """
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        time.sleep(0.35)  # Cho nhân vật dừng hẳn động tác di chuyển

        state = self.get_helper_state()
        if state and state[0]:
            _log("[⚔️ AUTO ATTACK] Tự động đánh (MuHelper) đã đang BẬT sẵn từ trước.")
            return True

        _log(f"[⚔️ AUTO ATTACK] Đang gửi click bật Auto Đánh ngầm vào nút Play trên HUD (341, 88)...")
        
        # 1. Click vị trí chuẩn xác trên thanh HUD (341, 88) bằng hook hoặc pure background
        if self.hook and self.hook.is_ready:
            self.hook.send_click(self.hwnd, 341, 88, duration_ms=50)
        else:
            BackgroundInputSimulator.pure_background_click(self.hwnd, 341, 88, duration_ms=50)

        # Chờ RAM cập nhật is_active == 1
        start_t = time.time()
        while time.time() - start_t < 1.0:
            time.sleep(0.12)
            st = self.get_helper_state()
            if st and st[0]:
                _log(f"[⚔️ AUTO ATTACK] ✔ Đã bật Tự Động Đánh (MuHelper) thành công! RAM is_active=1.")
                return True

        # 2. Thử vị trí tâm biểu tượng (346, 88)
        _log(f"[⚔️ AUTO ATTACK] Đang thử lại click tại tâm nút (346, 88)...")
        if self.hook and self.hook.is_ready:
            self.hook.send_click(self.hwnd, 346, 88, duration_ms=60)
        else:
            BackgroundInputSimulator.pure_background_click(self.hwnd, 346, 88, duration_ms=60)

        start_t = time.time()
        while time.time() - start_t < 1.0:
            time.sleep(0.12)
            st = self.get_helper_state()
            if st and st[0]:
                _log(f"[⚔️ AUTO ATTACK] ✔ Đã bật Tự Động Đánh (MuHelper) thành công! RAM is_active=1.")
                return True

        # 3. Fallback pure background click trực tiếp
        _log(f"[⚔️ AUTO ATTACK] Thử dự phòng Pure Background click (341, 88)...")
        BackgroundInputSimulator.pure_background_click(self.hwnd, 341, 88, duration_ms=60)

        start_t = time.time()
        while time.time() - start_t < 1.0:
            time.sleep(0.12)
            st = self.get_helper_state()
            if st and st[0]:
                _log(f"[⚔️ AUTO ATTACK] ✔ Đã bật Tự Động Đánh (MuHelper) thành công! RAM is_active=1.")
                return True

        # 4. Fallback gửi phím Home (VK_HOME = 0x24)
        _log(f"[⚔️ AUTO ATTACK] Thử dự phòng phím Home (VK_HOME)...")
        BackgroundInputSimulator.send_key(self.hwnd, 0x24, 0.05)
        start_t = time.time()
        while time.time() - start_t < 1.0:
            time.sleep(0.12)
            st = self.get_helper_state()
            if st and st[0]:
                _log(f"[⚔️ AUTO ATTACK] ✔ Đã bật Tự Động Đánh (MuHelper) thành công! RAM is_active=1.")
                return True

        _log(f"[!] Chưa nhận được phản hồi bật Auto Đánh từ RAM (Vui lòng kiểm tra đã cài đặt MuHelper trong game chưa).")
        return False

    def toggle_auto_attack(self, log_callback=None) -> bool:
        """Bật hoặc Tắt Auto Đánh (MuHelper) tùy theo trạng thái RAM hiện tại."""
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        state = self.get_helper_state()
        cur_active = state[0] if state else False
        target_str = "TẮT" if cur_active else "BẬT"
        _log(f"[⚔️ AUTO ATTACK] Đang gửi click chuyển đổi trạng thái Auto Đánh -> {target_str}...")

        if self.hook and self.hook.is_ready:
            self.hook.send_click(self.hwnd, 341, 88, duration_ms=50)
        else:
            BackgroundInputSimulator.pure_background_click(self.hwnd, 341, 88, duration_ms=50)

        start_t = time.time()
        while time.time() - start_t < 2.0:
            time.sleep(0.15)
            st = self.get_helper_state()
            if st and st[0] != cur_active:
                new_str = "BẬT" if st[0] else "TẮT"
                _log(f"[⚔️ AUTO ATTACK] ✔ Đã chuyển trạng thái Auto Đánh thành công: {new_str}!")
                return True

        _log(f"[!] Chưa nhận được phản hồi thay đổi trạng thái Auto Đánh từ RAM.")
        return False

    def warp_to_map(self, target_map_name: str, max_wait_sec: float = 7.0, log_callback=None, stop_event=None) -> bool:
        """
        Kiểm tra bản đồ hiện tại qua RAM. Nếu khác target_map_name, gửi lệnh '/m <map>'.
        Chờ RAM cập nhật bản đồ mới.
        """
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)

        state = self.get_live_state()
        if not state:
            _log(f"[!] Không đọc được RAM PID {self.pid}")
            return False

        map_id, cur_map, cur_x, cur_y, _, _ = state
        clean_target = normalize_map_name(target_map_name)
        clean_cur = normalize_map_name(cur_map)

        if clean_target == clean_cur or clean_target.lower() == cur_map.lower():
            _log(f"[*] Nhân vật đã ở đúng bản đồ '{cur_map}'. Không cần chuyển map.")
            return True

        # Tắt MuHelper trước khi chuyển map nếu đang chạy (MU Online cấm warp khi Helper đang đánh)
        h_st = self.get_helper_state()
        if h_st and h_st[0]:
            _log("[⚔️ AUTO ATTACK] Đang tắt MuHelper trước khi chuyển map...")
            self.toggle_auto_attack(log_callback=_log)
            time.sleep(0.5)

        _log(f"[➔] Đang ở '{cur_map}' (Map ID {map_id}). Gửi lệnh '/m {clean_target}'...")
        BackgroundInputSimulator.send_chat_command(self.hwnd, f"/m {clean_target}")

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            if stop_event and stop_event.is_set():
                _log("[⏹] Đã hủy lệnh chuyển map theo yêu cầu.")
                return False
            time.sleep(0.25)
            poll_state = self.get_live_state()
            if poll_state:
                new_map_id, new_map, _, _, _, _ = poll_state
                if new_map_id != map_id or new_map.lower() != cur_map.lower():
                    _log(f"[✔] Đổi map thành công! Đã vào '{new_map}' (Map ID {new_map_id}). Chờ load cảnh 1.5s...")
                    time.sleep(1.5)
                    return True

        _log(f"[!] Hết thời gian chờ đổi map tới '{target_map_name}'. (Lưu ý: Devias yêu cầu Lv 40, hãy kiểm tra cấp độ nhân vật hoặc Zen).")
        return False

    def navigate_continuous(
        self,
        target_x: int,
        target_y: int,
        arrival_radius: int = 1,
        max_wait_seconds: Optional[float] = None,
        log_callback=None,
        stop_event=None,
        progress_callback=None,
        stride_interval: float = 0.85,
        use_micro_sync: bool = False,
        auto_attack_on_arrival: bool = False
    ) -> bool:
        """
        ĐIỀU HƯỚNG CHẠY MỘT MẠCH TỚI ĐÍCH (Continuous Sprint Navigation):
        - Sải bước chạy liên tục không ngừng nghỉ, nhấp chuột định hướng mỗi ~0.85s trước khi nhân vật dừng.
        - Chạy một mạch cho tới khi tới đích (khoảng cách <= arrival_radius) mới dừng lại.
        - Không bị timeout sớm giữa chừng (timeout tự động giãn theo cự ly: max(120s, cự_ly * 4s)).
        - Tự động phát hiện kẹt tường/chướng ngại vật (> 1.2s không đổi tọa độ) -> Lách góc né (+45° / -45°).
        - Tự động kéo lại hướng nếu phát hiện đi lệch xa hơn.
        - Click cực nhanh (~20ms) nên không chiếm chuột hay cướp thao tác của người dùng.
        - Tự động bật Auto Đánh (MuHelper) ngay khi tới vị trí đích nếu auto_attack_on_arrival=True.
        """
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        state = self.get_live_state()
        if not state or state[2] is None or state[3] is None:
            _log(f"[!] Không đọc được tọa độ nhân vật từ RAM!")
            return False

        _, map_name, cur_x, cur_y, _, _ = state
        initial_dist = max(abs(target_x - cur_x), abs(target_y - cur_y))
        total_initial_dist = max(1, initial_dist)

        # Timeout tự động tính toán hào phóng để nhân vật có đủ thời gian chạy tới đích
        if max_wait_seconds is None:
            max_wait_seconds = max(120.0, float(initial_dist * 4.0))

        dx = target_x - cur_x
        dy = target_y - cur_y
        dir_name = get_direction_description(dx, dy)
        x_req = f"TĂNG X (+{dx})" if dx > 0 else (f"GIẢM X ({dx})" if dx < 0 else "X Đạt")
        y_req = f"TĂNG Y (+{dy})" if dy > 0 else (f"GIẢM Y ({dy})" if dy < 0 else "Y Đạt")

        _log(f"========================================================")
        _log(f" 🚀 CHẠY MỘT MẠCH TỚI ĐÍCH ({target_x}, {target_y}) TRÊN BẢN ĐỒ '{map_name}'")
        _log(f" • Tọa độ xuất phát: ({cur_x}, {cur_y}) | Khoảng cách: {initial_dist} ô")
        _log(f" • Hướng di chuyển: {dir_name} [{x_req}, {y_req}]")
        _log(f" • Cơ chế: Sải bước liên tục mỗi {stride_interval}s, chạy một mạch tới đích mới dừng!")
        if auto_attack_on_arrival:
            _log(f" • Auto Đánh: Sẽ tự động kích hoạt MuHelper ngay khi tới đích.")
        _log(f"========================================================")

        if initial_dist <= arrival_radius:
            _log(f"[🎉 ĐÃ Ở TẠI ĐÍCH] Nhân vật đã ở ({cur_x}, {cur_y}) [Cách đích {initial_dist} ô <= {arrival_radius} ô].")
            if auto_attack_on_arrival:
                _log(f"[⚔️ AUTO ATTACK] Đang tự động bật Auto Đánh (MuHelper) tại tọa độ đích...")
                self.enable_auto_attack(log_callback=_log)
            if progress_callback:
                progress_callback(1.0, 0, (cur_x, cur_y))
            return True

        start_time = time.time()
        last_click_time = 0.0
        last_pos = (cur_x, cur_y)
        last_moved_time = time.time()
        bypass_angle_offset = 0.0
        bypass_angles = [45.0, -45.0, 60.0, -60.0, 90.0, -90.0]
        bypass_idx = 0
        prev_dist = initial_dist
        stuck_cycles = 0

        while time.time() - start_time < max_wait_seconds:
            if stop_event and stop_event.is_set():
                _log("[⏹] Đã dừng theo yêu cầu của bạn.")
                return False

            state = self.get_live_state()
            if not state or state[2] is None or state[3] is None:
                time.sleep(0.1)
                continue

            cur_x, cur_y = state[2], state[3]
            rem_dist = max(abs(target_x - cur_x), abs(target_y - cur_y))

            # Báo tiến độ lên UI
            if progress_callback:
                prog = max(0.0, min(1.0, 1.0 - (rem_dist / total_initial_dist)))
                progress_callback(prog, rem_dist, (cur_x, cur_y))

            # 1. ĐÃ TỚI ĐÍCH?
            if rem_dist <= arrival_radius:
                _log(f"[🎉 ĐÃ TỚI ĐÍCH!] Tọa độ RAM ({cur_x}, {cur_y}) đã đạt đích ({target_x}, {target_y}) [Cách {rem_dist} ô <= {arrival_radius} ô]!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                if progress_callback:
                    progress_callback(1.0, 0, (cur_x, cur_y))
                return True

            now = time.time()

            # 2. Kiểm tra tiến độ di chuyển
            if (cur_x, cur_y) != last_pos:
                last_pos = (cur_x, cur_y)
                last_moved_time = now
                stuck_cycles = 0
                if rem_dist < prev_dist:
                    # Đang tiến gần hơn -> Đặt lại góc né vật cản về bình thường
                    bypass_angle_offset = 0.0
                    prev_dist = rem_dist
            else:
                # Đang đứng yên
                if now - last_moved_time > 1.2:
                    stuck_cycles += 1
                    bypass_angle_offset = bypass_angles[bypass_idx % len(bypass_angles)]
                    bypass_idx += 1
                    _log(f"   [🚧 VẬT CẢN/GÓC KẸT] Đứng yên tại ({cur_x}, {cur_y}). Lách góc né {bypass_angle_offset:+0.0f}° để vượt cản...")
                    last_moved_time = now



            # 4. Gửi click sải bước (stride click) - Giới hạn siêu ngắn 1.5 ~ 2 ô sát chân nhân vật
            time_since_click = now - last_click_time
            need_immediate_click = (stuck_cycles > 0 and time_since_click >= 0.45)

            if time_since_click >= stride_interval or need_immediate_click:
                max_step_dist = 1.8  # Bước click siêu ngắn (1.5-2 ô) sát chân nhân vật để không bị trôi lố
                dx_full = target_x - cur_x
                dy_full = target_y - cur_y
                cheby_dist = max(abs(dx_full), abs(dy_full))

                if cheby_dist > max_step_dist:
                    scale = max_step_dist / cheby_dist
                    step_target_x = int(round(cur_x + dx_full * scale))
                    step_target_y = int(round(cur_y + dy_full * scale))
                else:
                    step_target_x = target_x
                    step_target_y = target_y

                eff_angle = (self.camera_angle_deg + bypass_angle_offset) % 360.0
                px, py = game_coord_to_screen_pixel(
                    cur_x, cur_y,
                    step_target_x, step_target_y,
                    self.client_w, self.client_h,
                    camera_angle_deg=eff_angle
                )

                if self.hook and self.hook.is_ready:
                    self.hook.send_click(self.hwnd, px, py, duration_ms=30)
                elif use_micro_sync:
                    BackgroundInputSimulator.micro_sync_click(self.hwnd, px, py, duration_ms=20)
                else:
                    BackgroundInputSimulator.pure_background_click(self.hwnd, px, py, duration_ms=50)

                last_click_time = time.time()
                cur_dir = get_direction_description(target_x - cur_x, target_y - cur_y)
                _log(f"   [🏃 SPRINT NGẦM (1.8 Ô)] ({cur_x}, {cur_y}) ➔ Bước ({step_target_x}, {step_target_y}) -> Đích ({target_x}, {target_y}) | Còn {rem_dist} ô [{cur_dir}]")

            time.sleep(0.12)

        # Hết timeout an toàn
        final_state = self.get_live_state()
        if final_state and final_state[2] is not None and final_state[3] is not None:
            last_dist = max(abs(target_x - final_state[2]), abs(target_y - final_state[3]))
            if last_dist <= arrival_radius:
                _log(f"[🎉 THÀNH CÔNG] Đã tới đích ({final_state[2]}, {final_state[3]})!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                if progress_callback:
                    progress_callback(1.0, 0, (final_state[2], final_state[3]))
                return True
            else:
                _log(f"[!] Hết thời gian chờ tối đa ({max_wait_seconds:.0f}s). Tọa độ hiện tại: ({final_state[2]}, {final_state[3]}) (Cách đích {last_dist} ô).")
                return False
        return False

    def navigate_to_coord(
        self,
        target_x: int,
        target_y: int,
        arrival_radius: int = 1,
        max_wait_seconds: Optional[float] = None,
        log_callback=None,
        stop_event=None,
        progress_callback=None,
        use_micro_sync: bool = False,
        auto_attack_on_arrival: bool = False
    ) -> bool:
        """
        Mặc định điều hướng trực tiếp bằng cơ chế Chạy một mạch tới đích (Continuous Sprint).
        """
        return self.navigate_continuous(
            target_x=target_x,
            target_y=target_y,
            arrival_radius=arrival_radius,
            max_wait_seconds=max_wait_seconds,
            log_callback=log_callback,
            stop_event=stop_event,
            progress_callback=progress_callback,
            stride_interval=0.85,
            use_micro_sync=use_micro_sync,
            auto_attack_on_arrival=auto_attack_on_arrival
        )

    def navigate_single_shot(
        self,
        target_x: int,
        target_y: int,
        arrival_radius: int = 1,
        max_wait_seconds: float = 25.0,
        log_callback=None,
        stop_event=None,
        progress_callback=None,
        auto_attack_on_arrival: bool = False
    ) -> bool:
        """
        ĐIỀU HƯỚNG 1 CLICK DUY NHẤT (Single-Shot):
        - Chỉ nhấp chuột đúng 1 lần duy nhất trong ~20ms ra xa theo vector đích.
        - Nhân vật tự sải bước chạy thẳng theo hướng đó.
        - Theo dõi tọa độ RAM cho tới khi tới đích hoặc dừng lại.
        - TUYỆT ĐỐI KHÔNG CLICK LẶP LẠI, KHÔNG GIẬT CHUỘT LIÊN HỒI!
        - Tự động bật Auto Đánh nếu auto_attack_on_arrival=True.
        """
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        state = self.get_live_state()
        if not state or state[2] is None or state[3] is None:
            _log(f"[!] Không đọc được tọa độ nhân vật từ RAM!")
            return False

        _, map_name, cur_x, cur_y, _, _ = state
        initial_dist = max(abs(target_x - cur_x), abs(target_y - cur_y))
        total_initial_dist = max(1, initial_dist)

        dx = target_x - cur_x
        dy = target_y - cur_y
        dir_name = get_direction_description(dx, dy)

        _log(f"========================================================")
        _log(f" 🚀 ĐIỀU HƯỚNG 1 CLICK (SINGLE-SHOT) TỚI ({target_x}, {target_y})")
        _log(f" • Tọa độ hiện tại: ({cur_x}, {cur_y}) | Khoảng cách: {initial_dist} ô | Hướng: {dir_name}")
        _log(f" • Cơ chế: Chỉ nhấp đúng 1 lần (20ms), tuyệt đối không giật chuột liên tục.")
        if auto_attack_on_arrival:
            _log(f" • Auto Đánh: Sẽ tự động kích hoạt MuHelper ngay khi tới đích.")
        _log(f"========================================================")

        if initial_dist <= arrival_radius:
            _log(f"[🎉 ĐÃ Ở TẠI ĐÍCH] Nhân vật đã ở ({cur_x}, {cur_y}).")
            if auto_attack_on_arrival:
                _log(f"[⚔️ AUTO ATTACK] Tự động bật Auto Đánh tại tọa độ đích...")
                self.enable_auto_attack(log_callback=_log)
            if progress_callback:
                progress_callback(1.0, 0, (cur_x, cur_y))
            return True

        # Tính pixel hướng ra xa theo vector đích
        px, py = game_coord_to_screen_pixel(cur_x, cur_y, target_x, target_y, self.client_w, self.client_h, self.camera_angle_deg)
        _log(f" ➔ Gửi 1 click định hướng duy nhất vào pixel ({px}, {py}). Nhân vật bắt đầu chạy...")

        # Thực hiện 1 click định hướng ngầm hoàn toàn
        if self.hook and self.hook.is_ready:
            self.hook.send_click(self.hwnd, px, py, duration_ms=30)
        else:
            BackgroundInputSimulator.micro_sync_click(self.hwnd, px, py, duration_ms=20)

        # Giám sát RAM khi nhân vật tự chạy
        start_time = time.time()
        last_pos = (cur_x, cur_y)
        last_moved_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            if stop_event and stop_event.is_set():
                _log("[⏹] Đã dừng theo yêu cầu.")
                return False

            time.sleep(0.2)
            state = self.get_live_state()
            if not state or state[2] is None or state[3] is None:
                continue

            cur_x, cur_y = state[2], state[3]
            rem_dist = max(abs(target_x - cur_x), abs(target_y - cur_y))

            if progress_callback:
                prog = max(0.0, min(1.0, 1.0 - (rem_dist / total_initial_dist)))
                progress_callback(prog, rem_dist, (cur_x, cur_y))

            if rem_dist <= arrival_radius:
                _log(f"[🎉 ĐÃ TỚI ĐÍCH] Tọa độ RAM ({cur_x}, {cur_y}) đã đạt ({target_x}, {target_y})!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                if progress_callback:
                    progress_callback(1.0, 0, (cur_x, cur_y))
                return True

            if (cur_x, cur_y) != last_pos:
                last_pos = (cur_x, cur_y)
                last_moved_time = time.time()
                _log(f"   [RAM Live] Đang chạy: ({cur_x}, {cur_y}) | Còn {rem_dist} ô...")
            else:
                # Nếu đã dừng lại quá 1.5s
                if time.time() - last_moved_time > 1.5:
                    _log(f"   [⏹] Nhân vật đã hoàn tất quãng chạy tại ({cur_x}, {cur_y}) (Cách đích {rem_dist} ô).")
                    break

        final_state = self.get_live_state()
        if final_state and final_state[2] is not None and final_state[3] is not None:
            last_dist = max(abs(target_x - final_state[2]), abs(target_y - final_state[3]))
            if last_dist <= arrival_radius:
                _log(f"[🎉 THÀNH CÔNG] Đã tới đích ({final_state[2]}, {final_state[3]})!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                return True
            else:
                _log(f"[i] Kết thúc bước chạy. Tọa độ hiện tại: ({final_state[2]}, {final_state[3]}) (Cách đích {last_dist} ô).")
                return False
        return False

    def navigate_waypoints(
        self,
        target_x: int,
        target_y: int,
        arrival_radius: int = 1,
        max_wait_seconds: Optional[float] = None,
        log_callback=None,
        stop_event=None,
        progress_callback=None,
        use_micro_sync: bool = False,
        auto_attack_on_arrival: bool = False
    ) -> bool:
        """
        ĐIỀU HƯỚNG TỪNG MỐC (Waypoint Navigation - Mỗi mốc ≤ 6 ô):
        - Chia nhỏ lộ trình thành các mốc ngắn 6 ô.
        - Tự động bật Auto Đánh nếu auto_attack_on_arrival=True.
        """
        if max_wait_seconds is None:
            cur_state = self.get_live_state()
            init_d = max(abs(target_x - cur_state[2]), abs(target_y - cur_state[3])) if (cur_state and cur_state[2] is not None) else 30
            max_wait_seconds = max(120.0, float(init_d * 4.0))
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        state = self.get_live_state()
        if not state or state[2] is None or state[3] is None:
            _log(f"[!] Không đọc được tọa độ nhân vật từ RAM!")
            return False

        _, map_name, cur_x, cur_y, _, _ = state
        initial_dist = max(abs(target_x - cur_x), abs(target_y - cur_y))
        total_initial_dist = max(1, initial_dist)

        dx = target_x - cur_x
        dy = target_y - cur_y
        dir_name = get_direction_description(dx, dy)
        x_req = f"TĂNG X (+{dx})" if dx > 0 else (f"GIẢM X ({dx})" if dx < 0 else "X Đạt")
        y_req = f"TĂNG Y (+{dy})" if dy > 0 else (f"GIẢM Y ({dy})" if dy < 0 else "Y Đạt")
        mode_str = "⚡ Micro-Sync (Chống dính chuột vật lý - Chuẩn Unity)" if use_micro_sync else "Pure PostMessage"

        _log(f"========================================================")
        _log(f" BẮT ĐẦU ĐIỀU HƯỚNG TỚI ({target_x}, {target_y}) TRÊN BẢN ĐỒ '{map_name}'")
        _log(f" • Tọa độ RAM hiện tại: ({cur_x}, {cur_y}) | Khoảng cách: {initial_dist} ô")
        _log(f" • Yêu cầu: {x_req}, {y_req} | Hướng tổng: {dir_name}")
        _log(f" • Chế độ click: {mode_str}")
        if auto_attack_on_arrival:
            _log(f" • Auto Đánh: Sẽ tự động kích hoạt MuHelper ngay khi tới đích.")
        _log(f"========================================================")

        if initial_dist <= arrival_radius:
            _log(f"[🎉 ĐÃ Ở TẠI ĐÍCH] Nhân vật đã ở ({cur_x}, {cur_y}) [Cách đích {initial_dist} ô <= {arrival_radius} ô].")
            if auto_attack_on_arrival:
                _log(f"[⚔️ AUTO ATTACK] Tự động bật Auto Đánh tại tọa độ đích...")
                self.enable_auto_attack(log_callback=_log)
            if progress_callback:
                progress_callback(1.0, 0, (cur_x, cur_y))
            return True

        # Chia đường thành các mốc ngắn sát chân (mỗi mốc ≤ 2 ô)
        waypoints = subdivide_path(cur_x, cur_y, target_x, target_y, max_step=2)
        _log(f" ➔ Lộ trình gồm {len(waypoints)} mốc di chuyển (mỗi mốc ≤ 2 ô).")

        start_nav_time = time.time()
        dynamic_angle_offset = 0.0

        for step_idx, (step_x, step_y) in enumerate(waypoints, start=1):
            if stop_event and stop_event.is_set():
                _log("[⏹] Đã dừng điều hướng theo yêu cầu người dùng.")
                return False

            if time.time() - start_nav_time > max_wait_seconds:
                _log("[!] Hết thời gian tối đa cho lộ trình.")
                break

            # Đọc lại tọa độ live
            state = self.get_live_state()
            if not state or state[2] is None or state[3] is None:
                continue
            cur_x, cur_y = state[2], state[3]

            dist_to_final = max(abs(target_x - cur_x), abs(target_y - cur_y))
            if dist_to_final <= arrival_radius:
                _log(f"[🎉 ĐÃ TỚI ĐÍCH CUỐI CÙNG] Tọa độ RAM ({cur_x}, {cur_y}) đã đạt đích ({target_x}, {target_y})!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                if progress_callback:
                    progress_callback(1.0, 0, (cur_x, cur_y))
                return True

            dist_to_step = max(abs(step_x - cur_x), abs(step_y - cur_y))
            if dist_to_step <= 1 and step_idx < len(waypoints):
                continue

            eff_angle = (self.camera_angle_deg + dynamic_angle_offset) % 360.0
            px, py = game_coord_to_screen_pixel(cur_x, cur_y, step_x, step_y, self.client_w, self.client_h, eff_angle)
            step_dir = get_direction_description(step_x - cur_x, step_y - cur_y)
            _log(f" • [Mốc {step_idx}/{len(waypoints)}] Ở ({cur_x}, {cur_y}) ➔ Bước tới ({step_x}, {step_y}) [Hướng {step_dir}] -> Click ({px}, {py})...")

            if self.hook and self.hook.is_ready:
                self.hook.send_click(self.hwnd, px, py, duration_ms=30)
            elif use_micro_sync:
                BackgroundInputSimulator.micro_sync_click(self.hwnd, px, py, duration_ms=30)
            else:
                BackgroundInputSimulator.pure_background_click(self.hwnd, px, py, duration_ms=70)

            # Vòng lặp giám sát RAM từng mốc (tối đa 6s mỗi mốc)
            step_start = time.time()
            last_pos = (cur_x, cur_y)
            last_moved_time = time.time()
            prev_dist_to_final = dist_to_final

            while time.time() - step_start < 6.0:
                if stop_event and stop_event.is_set():
                    _log("[⏹] Đã dừng điều hướng theo yêu cầu người dùng.")
                    return False

                time.sleep(0.18)

                state = self.get_live_state()
                if not state or state[2] is None or state[3] is None:
                    continue

                cur_x, cur_y = state[2], state[3]
                remaining_to_step = max(abs(step_x - cur_x), abs(step_y - cur_y))
                remaining_to_final = max(abs(target_x - cur_x), abs(target_y - cur_y))

                if progress_callback:
                    prog = max(0.0, min(1.0, 1.0 - (remaining_to_final / total_initial_dist)))
                    progress_callback(prog, remaining_to_final, (cur_x, cur_y))

                # Đã tới đích cuối cùng?
                if remaining_to_final <= arrival_radius:
                    _log(f"[🎉 ĐÃ TỚI ĐÍCH] Tọa độ RAM ({cur_x}, {cur_y}) đã đạt đích ({target_x}, {target_y})!")
                    if auto_attack_on_arrival:
                        _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                        self.enable_auto_attack(log_callback=_log)
                    if progress_callback:
                        progress_callback(1.0, 0, (cur_x, cur_y))
                    return True

                # Đã tới mốc hiện tại?
                is_final_step = (step_idx == len(waypoints))
                req_radius = arrival_radius if is_final_step else 1
                if remaining_to_step <= req_radius:
                    _log(f"   [✔ ĐÃ QUA MỐC {step_idx}] Tọa độ ({cur_x}, {cur_y}) - Còn {remaining_to_final} ô tới đích cuối.")
                    break

                # Kiểm tra chuyển động RAM
                if (cur_x, cur_y) != last_pos:
                    last_moved_time = time.time()
                    dist_delta = remaining_to_final - prev_dist_to_final

                    if dist_delta < 0:
                        _log(f"   [RAM Live] ({cur_x}, {cur_y}) -> GẦN HƠN ({-dist_delta} ô) ✔ | Còn {remaining_to_final} ô")
                    elif dist_delta > 0:
                        _log(f"   [RAM Live] ({cur_x}, {cur_y}) -> Tọa độ biến đổi ({+dist_delta} ô) | Còn {remaining_to_final} ô")

                    last_pos = (cur_x, cur_y)
                    prev_dist_to_final = remaining_to_final

                # Nếu bị đứng yên > 1.2s mà chưa tới mốc, gửi lại click
                if time.time() - last_moved_time >= 1.2:
                    _log(f"   [!] Đứng yên, click lại mốc ({step_x}, {step_y})...")
                    px, py = game_coord_to_screen_pixel(cur_x, cur_y, step_x, step_y, self.client_w, self.client_h, eff_angle)
                    if use_micro_sync:
                        BackgroundInputSimulator.micro_sync_click(self.hwnd, px, py, duration_ms=30)
                    else:
                        BackgroundInputSimulator.pure_background_click(self.hwnd, px, py, duration_ms=70)
                    last_moved_time = time.time()

        # Kiểm tra kết quả cuối cùng
        final_state = self.get_live_state()
        if final_state and final_state[2] is not None and final_state[3] is not None:
            last_dist = max(abs(target_x - final_state[2]), abs(target_y - final_state[3]))
            if last_dist <= arrival_radius:
                _log(f"[🎉 THÀNH CÔNG] Đã tới đích ({final_state[2]}, {final_state[3]})!")
                if auto_attack_on_arrival:
                    _log(f"[⚔️ AUTO ATTACK] Đến vị trí đích! Tự động bật Auto Đánh (MuHelper)...")
                    self.enable_auto_attack(log_callback=_log)
                if progress_callback:
                    progress_callback(1.0, 0, (final_state[2], final_state[3]))
                return True
            else:
                _log(f"[!] Dừng lộ trình. Vị trí hiện tại: ({final_state[2]}, {final_state[3]}) (Cách {last_dist} ô).")
                return False
        return False

    def navigate_multi_points(
        self,
        waypoints: List[Tuple[int, int]],
        arrival_radius: int = 1,
        intermediate_radius: int = 1,
        auto_attack_on_arrival: bool = True,
        log_callback=None,
        stop_event=None,
        progress_callback=None,
        stride_interval: float = 0.85,
        use_micro_sync: bool = False
    ) -> bool:
        """
        ĐIỀU HƯỚNG THEO LỘ TRÌNH ĐA ĐIỂM / ĐIỂM TRUNG GIAN (Multi-Waypoint Route):
        - Chạy tuần tự qua danh sách các mốc tọa độ: [(x1, y1), (x2, y2), ..., (xn, yn)]
        - Với các mốc trung gian: Chuyển mốc ngay khi cách mốc <= intermediate_radius (2 ô) để nhân vật chạy lướt liên tục không bị dừng khựng.
        - Với mốc cuối cùng: Dừng chính xác tại arrival_radius (1 ô).
        - Khi đến mốc cuối cùng: Tự động kích hoạt Auto Đánh (MuHelper) nếu auto_attack_on_arrival=True.
        """
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(msg, flush=True)

        if not waypoints:
            _log("[!] Danh sách lộ trình rỗng! Không có mốc nào để di chuyển.")
            return False

        state = self.get_live_state()
        if not state or state[2] is None or state[3] is None:
            _log("[!] Không đọc được tọa độ nhân vật từ RAM!")
            return False

        start_x, start_y = state[2], state[3]
        total_pts = len(waypoints)

        # Tính tổng cự ly toàn bộ lộ trình
        total_route_dist = 0
        prev_p = (start_x, start_y)
        for pt in waypoints:
            total_route_dist += max(abs(pt[0] - prev_p[0]), abs(pt[1] - prev_p[1]))
            prev_p = pt
        total_route_dist = max(1, total_route_dist)

        _log(f"========================================================")
        _log(f" 🗺️ BẮT ĐẦU CHẠY LỘ TRÌNH ĐA ĐIỂM ({total_pts} MỐC DI CHUYỂN)")
        _log(f" • Tọa độ xuất phát: ({start_x}, {start_y}) | Tổng cự ly ước tính: ~{total_route_dist} ô")
        for i, (wx, wy) in enumerate(waypoints, start=1):
            role_str = "ĐÍCH CUỐI CÙNG" if i == total_pts else f"Điểm trung gian #{i}"
            _log(f"   [Mốc {i}/{total_pts}] ({wx}, {wy}) - {role_str}")
        if auto_attack_on_arrival:
            _log(f" • Auto Đánh: Sẽ tự động bật MuHelper khi hoàn tất mốc cuối cùng.")
        _log(f"========================================================")

        # Tự động phân chia tất cả các chặng đường dài thành các mốc nhỏ sát chân (≤ 2 ô)
        dense_waypoints = []
        curr_p = (start_x, start_y)
        for orig_idx, (wx, wy) in enumerate(waypoints, start=1):
            sub_steps = subdivide_path(curr_p[0], curr_p[1], wx, wy, max_step=2)
            is_orig_final = (orig_idx == total_pts)
            for s_idx, (sx, sy) in enumerate(sub_steps, start=1):
                is_sub_final = is_orig_final and (s_idx == len(sub_steps))
                is_orig_target = (s_idx == len(sub_steps))
                dense_waypoints.append({
                    "x": sx,
                    "y": sy,
                    "is_sub_final": is_sub_final,
                    "is_orig_target": is_orig_target,
                    "orig_idx": orig_idx
                })
            curr_p = (wx, wy)

        dist_traveled = 0

        for node in dense_waypoints:
            if stop_event and stop_event.is_set():
                _log("[⏹] Đã dừng lộ trình theo yêu cầu của bạn.")
                return False

            wx, wy = node["x"], node["y"]
            is_final_point = node["is_sub_final"]
            req_radius = arrival_radius if is_final_point else intermediate_radius

            if node["is_orig_target"]:
                point_desc = f"ĐÍCH CUỐI ({wx}, {wy})" if is_final_point else f"Mốc {node['orig_idx']}/{total_pts} ({wx}, {wy})"
                _log(f"\n👉 [LỘ TRÌNH: MỐC {node['orig_idx']}/{total_pts}] Đang hướng tới {point_desc}...")

            curr_state = self.get_live_state()
            leg_start_x = curr_state[2] if (curr_state and curr_state[2] is not None) else wx
            leg_start_y = curr_state[3] if (curr_state and curr_state[3] is not None) else wy
            leg_total_dist = max(1, max(abs(wx - leg_start_x), abs(wy - leg_start_y)))

            def leg_progress_cb(sub_prog, sub_rem, coord):
                if progress_callback:
                    done_dist = dist_traveled + (1.0 - (sub_rem / leg_total_dist)) * leg_total_dist
                    overall_prog = max(0.0, min(1.0, done_dist / total_route_dist))
                    progress_callback(overall_prog, sub_rem, coord, node['orig_idx'], total_pts)

            # Chỉ bật auto attack ở mốc cuối cùng toàn bộ lộ trình
            leg_auto_attack = auto_attack_on_arrival if is_final_point else False

            # Sử dụng continuous sprint để chạy tới mốc micro-step 2-3 ô này
            success = self.navigate_continuous(
                target_x=wx,
                target_y=wy,
                arrival_radius=req_radius,
                log_callback=log_callback if node["is_orig_target"] else None,
                stop_event=stop_event,
                progress_callback=leg_progress_cb,
                stride_interval=stride_interval,
                use_micro_sync=use_micro_sync,
                auto_attack_on_arrival=leg_auto_attack
            )

            if not success:
                if stop_event and stop_event.is_set():
                    return False
                _log(f"[!] Không thể tiếp cận mốc {node['orig_idx']}/{total_pts} ({wx}, {wy}). Lộ trình tạm dừng.")
                return False

            dist_traveled += leg_total_dist

            if not is_final_point:
                if node["is_orig_target"]:
                    _log(f"[✔ ĐÃ QUA MỐC {node['orig_idx']}/{total_pts} ({wx}, {wy})] Tiếp tục chạy mốc tiếp theo...")
                time.sleep(0.05)
            else:
                _log(f"[🎉 HOÀN THÀNH TOÀN BỘ LỘ TRÌNH!] Đã tới đích cuối cùng ({wx}, {wy})!")

        return True

def toggle_auto_attack_via_sendmessage(hwnd: int) -> bool:
    """Tắt/Bật Auto Đánh (MuHelper) qua click nút HUD Play (341, 88) kết hợp phím Home (VK_HOME)"""
    BackgroundInputSimulator.pure_background_click(hwnd, 341, 88, duration_ms=50)
    time.sleep(0.08)
    BackgroundInputSimulator.send_key(hwnd, 0x24, 0.05)
    return True

# ==============================================================================
# Interactive CLI Menu
# ==============================================================================

def scan_all_clients() -> List[ClientLiveState]:
    windows = WindowHelper.get_unity_windows()
    clients = []
    for pid, hwnd, title, w, h in windows:
        state = ProcessMemoryReader.read_live_state(pid)
        map_id = state[0] if state else None
        map_name = state[1] if state else "Unknown"
        cur_x = state[2] if state else None
        cur_y = state[3] if state else None
        target_x = state[4] if state else None
        target_y = state[5] if state else None

        helper_state = ProcessMemoryReader.read_helper_state(pid)
        is_auto_attack = helper_state[0] if helper_state else False
        active_time = helper_state[2] if helper_state else 0

        char_name = title.split(" ")[0] if title else f"Client #{pid}"
        server = ""
        if "MEGAMU" in title:
            parts = title.split("MEGAMU")
            if len(parts) > 1:
                server = parts[1].strip()

        # Đọc Level & Reset
        level = None
        resets = None
        import re
        m = re.search(r'\((\d+)(?:/(\d+)rr)?\)', title)
        if m:
            level = int(m.group(1))
            if m.group(2):
                resets = int(m.group(2))

        if level is None:
            level = ProcessMemoryReader.read_character_level(pid)

        clients.append(ClientLiveState(
            pid=pid,
            hwnd=hwnd,
            window_title=title,
            char_name=char_name,
            server=server,
            map_id=map_id,
            map_name=map_name,
            x=cur_x,
            y=cur_y,
            target_x=target_x,
            target_y=target_y,
            is_auto_attack=is_auto_attack,
            helper_active_time=active_time,
            level=level,
            resets=resets
        ))
    return clients

def print_client_table(clients: List[ClientLiveState]):
    print("\n" + "=" * 92)
    print(f"{'STT':<4} | {'PID':<7} | {'Nhân vật':<16} | {'Server':<8} | {'Map':<15} | {'Tọa độ RAM':<12} | {'Auto Đánh':<10}")
    print("-" * 92)
    for idx, c in enumerate(clients, start=1):
        coord_str = f"({c.x}, {c.y})" if c.x is not None and c.y is not None else "(—, —)"
        map_str = f"{c.map_name}" if c.map_name else "Unknown"
        auto_str = f"BẬT ({c.helper_active_time}s)" if c.is_auto_attack else "TẮT"
        print(f"{idx:<4} | {c.pid:<7} | {c.char_name:<16} | {c.server:<8} | {map_str:<15} | {coord_str:<12} | {auto_str:<10}")
    print("=" * 92)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="MEGAMU Auto Navigator (Python Edition)")
    parser.add_argument("--pid", type=int, help="Process ID của client MEGAMU cần điều khiển")
    parser.add_argument("--map", type=str, help="Tên bản đồ cần chuyển tới (ví dụ: devias, lorencia, atlans)")
    parser.add_argument("--x", type=int, help="Tọa độ X đích đến")
    parser.add_argument("--y", type=int, help="Tọa độ Y đích đến")
    parser.add_argument("--angle", type=float, default=0.0, help="Góc xoay camera (mặc định 0)")
    args = parser.parse_args()

    # Nếu truyền đủ tham số dòng lệnh -> Chạy thẳng không cần menu
    if args.pid and (args.map or (args.x is not None and args.y is not None)):
        nav = MegNavigator(args.pid, camera_angle_deg=args.angle)
        if args.map:
            nav.warp_to_map(args.map)
        if args.x is not None and args.y is not None:
            nav.navigate_to_coord(args.x, args.y)
        return

    # Chế độ giao diện tương tác dòng lệnh (Interactive Menu)
    print("\n" + "#" * 60)
    print("       MEGAMU AUTO NAVIGATOR - PYTHON EDITION")
    print("  Tự động đổi map và di chuyển khép kín theo RAM")
    print("#" * 60)

    clients = scan_all_clients()
    if not clients:
        print("[!] Không tìm thấy tiến trình MEGAMU nào đang chạy!")
        return

    print_client_table(clients)

    while True:
        try:
            choice_str = input(f"\n👉 Chọn số thứ tự client (1 - {len(clients)}) hoặc nhập 'q' để thoát: ").strip()
            if choice_str.lower() in ('q', 'exit', 'quit'):
                print("Tạm biệt!")
                return
            choice = int(choice_str)
            if 1 <= choice <= len(clients):
                selected = clients[choice - 1]
                break
            print("[!] Số thứ tự không hợp lệ. Vui lòng nhập lại.")
        except ValueError:
            print("[!] Vui lòng nhập số nguyên.")

    print(f"\n[+] Đã chọn: {selected.char_name} (PID: {selected.pid}) - Đang ở '{selected.map_name}' ({selected.x}, {selected.y})")

    target_map = input(f"👉 Nhập tên bản đồ cần đến (Enter để giữ nguyên '{selected.map_name}'): ").strip()
    if not target_map:
        target_map = selected.map_name

    while True:
        coord_input = input(f"👉 Nhập tọa độ đích X Y (ví dụ '220 50' hoặc '70, 40', Enter để chỉ chuyển map): ").strip()
        if not coord_input:
            target_x, target_y = None, None
            break
        try:
            cleaned = coord_input.replace(",", " ").split()
            if len(cleaned) >= 2:
                target_x = int(cleaned[0])
                target_y = int(cleaned[1])
                break
            print("[!] Cần nhập đủ cả 2 tọa độ X và Y cách nhau bởi khoảng trắng hoặc dấu phẩy.")
        except ValueError:
            print("[!] Tọa độ phải là số nguyên.")

    nav = MegNavigator(selected.pid)

    if target_map and normalize_map_name(target_map) != normalize_map_name(selected.map_name):
        nav.warp_to_map(target_map)

    if target_x is not None and target_y is not None:
        nav.navigate_to_coord(target_x, target_y)

if __name__ == "__main__":
    main()
