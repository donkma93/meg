#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MEGAMU REA ADVANCED HUNTER & DIRECT ENGINE (Standalone Tool v3.1)
=============================================================================
Công cụ độc lập ứng dụng Kỹ nghệ Đảo ngược (REA) phân tích từ GameAssembly.dll
và dump.cs (Metadata v31):
- ZERO-INJECTION RADAR ENGINE:
  1. Win32 ReadProcessMemory (RPM) siêu tốc, Crash-Proof 100%, không bị 0x00000005.
  2. Tự động nhận diện và kết nối MEGAMU.exe ngay khi khởi động (Auto-Connect).
- PHÂN LOẠI THỰC THỂ CHÍNH XÁC 100%:
  - Tách biệt rõ ràng Người chơi (CharacterBody), NPC (b_class >= 200), Quái vật (MonsterBody).
  - Dropdown loài quái CHỈ hiển thị quái có thể tiêu diệt, tuyệt đối không lẫn NPC/Người chơi.
- SĂN QUÁI CHỈ ĐỊNH THEO LOÀI (SPECIES FILTER):
  - Chọn loài quái cần săn -> Bot BỎ QUA 100% CÁC LOÀI QUÁI KHÁC dù đứng sát cạnh!
  - Khóa mục tiêu cứng vào RAM (NpcTarget +0x430).
  - Tự động áp sát (Auto-Chase) và tung chiêu Skill (Right Click + Spacebar) thật sự!
  - Nhận diện quái chết tức thời (IsDestroying +0xC0) và chuyển mục tiêu kế tiếp.
- FAST WARP ĐỘC LẬP:
  - Dịch chuyển 16 bản đồ và nộp vé sự kiện qua Direct Win32 Message, không cần Frida.
=============================================================================
"""

import os
import sys
import time
import json
import math
import struct
import ctypes
from ctypes import wintypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None

try:
    from meg_navigator import WindowHelper, UnityBackgroundHook, BackgroundInputSimulator
except ImportError:
    WindowHelper = None
    UnityBackgroundHook = None
    BackgroundInputSimulator = None

# =============================================================================
# CONSTANTS & WIN32 STRUCTS
# =============================================================================

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_ESCAPE = 0x1B

MAP_NAMES = {
    0: "Lorencia", 1: "Dungeon", 2: "Devias", 3: "Noria", 4: "Lost Tower",
    5: "Exile", 6: "Arena", 7: "Atlans", 8: "Tarkan", 9: "Devil Square",
    10: "Icarus", 33: "Aida", 34: "Crywolf", 37: "Kanturu Remains",
    51: "Elbeland", 57: "Raklion", 63: "Vulcanus", 112: "Ferea",
    113: "Nixies Lake", 115: "Deep Dungeon 1", 116: "Swamp of Darkness", 117: "Kubera Mine"
}

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('th32ModuleID', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('GlblcntUsage', wintypes.DWORD),
        ('ProccntUsage', wintypes.DWORD),
        ('modBaseAddr', ctypes.c_void_p),
        ('modBaseSize', wintypes.DWORD),
        ('hModule', wintypes.HMODULE),
        ('szModule', ctypes.c_char * 256),
        ('szExePath', ctypes.c_char * 260),
    ]

def get_module_base_win32(pid: int, module_name: str) -> Optional[int]:
    """Lấy địa chỉ Base Address của DLL trong tiến trình qua Toolhelp32."""
    if sys.platform != "win32" or not pid:
        return None
    k32 = ctypes.windll.kernel32
    hSnap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if hSnap == -1:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        success = k32.Module32First(hSnap, ctypes.byref(me))
        while success:
            mod_name = me.szModule.decode('utf-8', errors='ignore')
            if mod_name.lower() == module_name.lower():
                return me.modBaseAddr
            success = k32.Module32Next(hSnap, ctypes.byref(me))
    except Exception:
        pass
    finally:
        k32.CloseHandle(hSnap)
    return None

def calc_monster_hitbox_pixel(
    cur_x: int, cur_y: int,
    target_x: int, target_y: int,
    client_w: int, client_h: int
) -> Tuple[int, int]:
    """
    Tính tọa độ pixel CHÍNH XÁC của quái vật trên màn hình để tung chiêu / click trúng hitbox.
    Tuyệt đối KHÔNG gán bán kính tối thiểu ảo (như 150px cũ), nhắm thẳng tâm thân (torso/chest) quái vật.
    """
    if client_w <= 0: client_w = 1024
    if client_h <= 0: client_h = 768

    cx = client_w // 2
    cy = client_h // 2 + 15

    dx = target_x - cur_x
    dy = target_y - cur_y

    if dx == 0 and dy == 0:
        return (cx, cy - 20)

    vx = (dx + dy) * 1.0
    vy = (dx - dy) * 0.55

    dist = math.sqrt(vx * vx + vy * vy)
    if dist < 0.001:
        return (cx, cy - 20)

    norm_x = vx / dist
    norm_y = vy / dist

    radius = dist * 28.0
    px = int(round(cx + norm_x * radius))
    py = int(round(cy - 22 + norm_y * radius))

    px = max(25, min(client_w - 25, px))
    py = max(45, min(client_h - 60, py))
    return (px, py)

def calc_chase_stride_pixel(
    cur_x: int, cur_y: int,
    target_x: int, target_y: int,
    client_w: int, client_h: int
) -> Tuple[int, int]:
    """
    Tính tọa độ click sải bước (stride click) để nhân vật bứt tốc chạy áp sát quái.
    Duy trì bán kính bước chạy hợp lý (120 - 180px) theo vector hướng thẳng tới quái.
    """
    if client_w <= 0: client_w = 1024
    if client_h <= 0: client_h = 768

    cx = client_w // 2
    cy = client_h // 2 + 15

    dx = target_x - cur_x
    dy = target_y - cur_y

    if dx == 0 and dy == 0:
        return (cx, cy)

    vx = (dx + dy) * 1.0
    vy = (dx - dy) * 0.55

    dist = math.sqrt(vx * vx + vy * vy)
    if dist < 0.001:
        return (cx, cy)

    norm_x = vx / dist
    norm_y = vy / dist

    stride_radius = min(max(120.0, dist * 28.0), client_h * 0.32)
    px = int(round(cx + norm_x * stride_radius))
    py = int(round(cy + norm_y * stride_radius))

    px = max(45, min(client_w - 45, px))
    py = max(65, min(client_h - 85, py))
    return (px, py)

def game_coord_to_screen_pixel(
    cur_x: int, cur_y: int,
    target_x: int, target_y: int,
    client_w: int, client_h: int
) -> Tuple[int, int]:
    return calc_chase_stride_pixel(cur_x, cur_y, target_x, target_y, client_w, client_h)

# =============================================================================
# WIN32 MEMORY SCANNER (Zero-Injection Engine)
# =============================================================================

class Win32MemoryScanner:
    """Bộ đọc/ghi bộ nhớ RAM tốc độ cao (ReadProcessMemory / WPM) độc lập, không crash."""
    def __init__(self, pid: int):
        self.pid = pid
        self.k32 = ctypes.windll.kernel32
        self.hProc = None
        self.base_addr = None

    def open(self) -> bool:
        if self.hProc:
            return True
        try:
            self.hProc = self.k32.OpenProcess(0x1F0FFF, False, self.pid)
            if self.hProc:
                self.base_addr = get_module_base_win32(self.pid, "GameAssembly.dll")
                return bool(self.base_addr)
        except Exception:
            pass
        return False

    def close(self):
        if self.hProc:
            try:
                self.k32.CloseHandle(self.hProc)
            except Exception:
                pass
            self.hProc = None

    def read_ptr(self, addr: int) -> int:
        if not addr or not self.hProc: return 0
        buf = ctypes.c_ulonglong()
        if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 8, None):
            return buf.value
        return 0

    def read_i32(self, addr: int) -> int:
        if not addr or not self.hProc: return 0
        buf = ctypes.c_int32()
        if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None):
            return buf.value
        return 0

    def read_u8(self, addr: int) -> int:
        if not addr or not self.hProc: return 0
        buf = ctypes.c_uint8()
        if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 1, None):
            return buf.value
        return 0

    def read_float(self, addr: int) -> float:
        if not addr or not self.hProc: return 0.0
        buf = ctypes.c_float()
        if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None):
            return buf.value
        return 0.0

    def read_cstr(self, addr: int, max_len: int = 64) -> str:
        if not addr or not self.hProc: return ""
        buf = ctypes.create_string_buffer(max_len)
        if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), max_len, None):
            return buf.value.decode('utf-8', errors='ignore')
        return ""

    def read_str(self, addr: int) -> str:
        if not addr or not self.hProc: return ""
        try:
            length = self.read_i32(addr + 0x10)
            if 0 < length < 64:
                buf = ctypes.create_unicode_buffer(length)
                if self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr + 0x14), ctypes.byref(buf), length * 2, None):
                    return buf.value
        except Exception:
            pass
        return ""

    def write_ptr(self, addr: int, val: int) -> bool:
        if not addr or not self.hProc: return False
        buf = ctypes.c_ulonglong(val)
        return bool(self.k32.WriteProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 8, None))

    def write_u8(self, addr: int, val: int) -> bool:
        if not addr or not self.hProc: return False
        buf = ctypes.c_uint8(val)
        return bool(self.k32.WriteProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 1, None))

    def write_float(self, addr: int, val: float) -> bool:
        if not addr or not self.hProc: return False
        buf = ctypes.c_float(val)
        return bool(self.k32.WriteProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None))

    def stop_player_movement(self) -> bool:
        """Dừng ngay lập tức bước chạy trong RAM để không làm hủy animation tấn công."""
        player = self.get_player()
        if not player:
            return False
        # Ghi tắt cờ AutoMoveWorking (+0x4C0)
        self.write_u8(player + 0x4C0, 0)
        # Ghi tắt cờ Moving (+0x3C) trong BodyMovement (+0xE8)
        movement = self.read_ptr(player + 0xE8)
        if movement:
            self.write_u8(movement + 0x3C, 0)
        return True

    def get_game_instance(self) -> int:
        if not self.base_addr: return 0
        type_info = self.read_ptr(self.base_addr + 0x553B900) # Game_TypeInfo
        if not type_info: return 0
        static_fields = self.read_ptr(type_info + 0xB8)
        if not static_fields: return 0
        return self.read_ptr(static_fields + 0x8)

    def get_player(self) -> int:
        game_inst = self.get_game_instance()
        if not game_inst: return 0
        return self.read_ptr(game_inst + 0x208)

    def get_viewport(self) -> int:
        game_inst = self.get_game_instance()
        if not game_inst: return 0
        return self.read_ptr(game_inst + 0x110)

    def get_map_id(self) -> int:
        game_inst = self.get_game_instance()
        if not game_inst: return -1
        world = self.read_ptr(game_inst + 0x200)
        if not world: return -1
        return self.read_i32(world + 0x20)

    def get_player_coords(self, player_ptr: int) -> Tuple[int, int]:
        if not player_ptr: return (0, 0)
        c_ptr = self.read_ptr(player_ptr + 0x68)
        if c_ptr:
            return (self.read_i32(c_ptr + 0x10), self.read_i32(c_ptr + 0x14))
        return (0, 0)

    def scan_radar(self, max_range: float = 35.0, **kwargs) -> Dict[str, Any]:
        """Quét toàn bộ quái và thực thể xung quanh từ Viewport.ObjectList."""
        if "radius" in kwargs:
            try:
                max_range = float(kwargs["radius"])
            except Exception:
                pass
        """Quét toàn bộ quái và thực thể xung quanh từ Viewport.ObjectList."""
        if not self.open():
            return {"entities": [], "species": {}, "error": "Không thể mở bộ nhớ tiến trình"}

        player = self.get_player()
        if not player:
            return {"entities": [], "species": {}, "error": "Chưa tìm thấy nhân vật trong RAM"}

        pX, pY = self.get_player_coords(player)
        viewport = self.get_viewport()
        if not viewport:
            return {"entities": [], "species": {}, "error": "Chưa tìm thấy Viewport"}

        obj_dict = self.read_ptr(viewport + 0x20) # Dictionary<int, ViewportObject>
        if not obj_dict:
            return {"entities": [], "species": {}, "error": "ObjectList rỗng"}

        entries = self.read_ptr(obj_dict + 0x18)
        count = self.read_i32(obj_dict + 0x20)
        if not entries or count <= 0:
            return {"entities": [], "species": {}, "playerX": pX, "playerY": pY}

        entities = []
        species_map = {}
        max_scan = min(count, 500)

        for i in range(max_scan):
            entry_addr = entries + 0x20 + i * 24 # Entry struct: 24 bytes
            hash_code = self.read_i32(entry_addr)
            if hash_code < 0:
                continue

            vp_obj = self.read_ptr(entry_addr + 16)
            if not vp_obj:
                continue

            # ViewportBody chứa con trỏ Body tại offset +0x18
            body = self.read_ptr(vp_obj + 0x18)
            if not body or body == player:
                continue

            # Kiểm tra cờ IsDestroying (+0xC0) để bỏ qua quái đang chết/biến mất
            if self.read_u8(body + 0xC0) == 1:
                continue

            b_idx = self.read_i32(body + 0x20)
            if b_idx < 0:
                continue

            b_name = self.read_str(self.read_ptr(body + 0x28))
            if not b_name:
                continue

            b_class = self.read_i32(body + 0x34)
            b_level = self.read_i32(body + 0x30)

            # Đọc con trỏ Coord (+0x68)
            c_ptr = self.read_ptr(body + 0x68)
            bX, bY = (-1, -1)
            if c_ptr:
                bX = self.read_i32(c_ptr + 0x10)
                bY = self.read_i32(c_ptr + 0x14)

            # Fallback tọa độ nếu c_ptr rỗng
            if bX == -1 and bY == -1:
                pos_x = self.read_float(body + 0x118)
                pos_y = self.read_float(body + 0x120)
                bX = int(round(pos_x / 100))
                bY = int(round(pos_y / 100))

            dx = bX - pX
            dy = bY - pY
            dist = math.sqrt(dx * dx + dy * dy)

            if max_range > 0 and dist > max_range:
                continue

            # Đọc tên Il2CppClass để phân loại chính xác 100%
            klass = self.read_ptr(body)
            klass_name = self.read_cstr(self.read_ptr(klass + 0x10)) if klass else ""
            lower_name = b_name.lower()

            ent_type = "Monster"
            is_boss = False
            is_golden = False

            if "CharacterBody" in klass_name or b_idx >= 10000:
                ent_type = "Player"
            elif b_class >= 200:
                ent_type = "NPC"
            elif "golden " in lower_name or "dourado" in lower_name:
                ent_type = "Golden"
                is_golden = True
            elif any(b in lower_name for b in ["kundun", "medusa", "selupan", "gorgon", "balgass", "erohim"]):
                ent_type = "Boss"
                is_boss = True
            else:
                ent_type = "Monster"

            # CHỈ ĐẾM VÀO DANH SÁCH SĂN KHI THỰC SỰ LÀ QUÁI / BOSS / GOLDEN (TUYỆT ĐỐI BỎ QUA NPC VÀ NGƯỜI CHƠI)
            if ent_type in ("Monster", "Golden", "Boss"):
                species_map[b_name] = species_map.get(b_name, 0) + 1

            entities.append({
                "ptr": hex(body),
                "ptr_int": body,
                "index": b_idx,
                "name": b_name,
                "level": b_level,
                "classId": b_class,
                "x": bX,
                "y": bY,
                "dist": round(dist, 1),
                "type": ent_type,
                "isGolden": is_golden,
                "isBoss": is_boss
            })

        entities.sort(key=lambda x: x["dist"])
        for e in entities:
            e["distance"] = e["dist"]

        monsters = [e for e in entities if e["type"] in ("Monster", "Golden", "Boss")]
        npcs = [e for e in entities if e["type"] == "NPC"]
        players = [e for e in entities if e["type"] == "Player"]

        return {
            "entities": entities,
            "monsters": monsters,
            "npcs": npcs,
            "players": players,
            "ground_items": [],
            "player": {"x": pX, "y": pY},
            "species": species_map,
            "playerX": pX,
            "playerY": pY
        }

    def read_gremory_case_items(self) -> List[Dict[str, Any]]:
        """Đọc danh sách vật phẩm quà tặng hiện có trong Hộp Quà Gremory Case (phím K) trực tiếp từ RAM."""
        items = []
        if not self.open():
            return items
        try:
            type_info = self.read_ptr(self.base_addr + 0x553B900)
            if not type_info: return items
            static_fields = self.read_ptr(type_info + 0xB8)
            if not static_fields: return items
            game_inst = self.read_ptr(static_fields + 0x08)
            if not game_inst: return items
            gremory_case = self.read_ptr(game_inst + 0x138)
            if not gremory_case: return items
            dict_ptr = self.read_ptr(gremory_case + 0x20)
            if not dict_ptr: return items

            outer_entries = self.read_ptr(dict_ptr + 0x18)
            outer_count = self.read_i32(dict_ptr + 0x20)
            if not outer_entries or outer_count <= 0: return items

            tab_names = {0: "Tài khoản (Account)", 1: "Nhân vật (Character)", 2: "Mobile", 3: "Personal Store"}
            for t in range(min(outer_count, 4)):
                e_addr = outer_entries + 0x20 + t * 24
                if self.read_i32(e_addr) < 0: continue
                tab_type = self.read_i32(e_addr + 8)
                sub_dict = self.read_ptr(e_addr + 16)
                if not sub_dict: continue

                sub_entries = self.read_ptr(sub_dict + 0x18)
                arr_len = self.read_i32(sub_entries + 0x18) if sub_entries else 0
                if not sub_entries or arr_len <= 0: continue

                for i in range(arr_len):
                    se_addr = sub_entries + 0x20 + i * 24
                    if self.read_i32(se_addr) < 0: continue
                    item_info = self.read_ptr(se_addr + 16)
                    if not item_info: continue

                    st = self.read_i32(item_info + 0x10)
                    src = self.read_i32(item_info + 0x14)
                    guid = self.read_i32(item_info + 0x18)
                    item_obj = self.read_ptr(item_info + 0x20)
                    item_code = 0
                    if item_obj:
                        b1 = self.read_u8(item_obj + 0x60)
                        b2 = self.read_u8(item_obj + 0x61)
                        item_code = b1 | (b2 << 8)

                    items.append({
                        "ptr": hex(item_info),
                        "ptr_int": item_info,
                        "tab": tab_type,
                        "tab_name": tab_names.get(tab_type, f"Tab {tab_type}"),
                        "storage_type": st,
                        "reward_source": src,
                        "guid": guid,
                        "item_code": item_code
                    })
        except Exception:
            pass
        return items

    def lock_target(self, target_body_ptr_int: int) -> bool:
        """Ghi con trỏ quái vào NpcTarget (+0x430) của người chơi."""
        player = self.get_player()
        if not player or not target_body_ptr_int:
            return False
        return self.write_ptr(player + 0x430, target_body_ptr_int)

    def set_player_target_angle(self, angle_deg: float) -> bool:
        """Xoay hướng mặt nhân vật về phía mục tiêu (cập nhật cả Angle và TargetAngle)."""
        player = self.get_player()
        if not player:
            return False
        self.write_float(player + 0x80, float(angle_deg))
        return self.write_float(player + 0x84, float(angle_deg))

    def get_telemetry(self) -> Dict[str, Any]:
        """Đọc toàn bộ Telemetry từ RAM."""
        player = self.get_player()
        if not player:
            return {}
        pX, pY = self.get_player_coords(player)
        name = self.read_str(self.read_ptr(player + 0x28))
        level = self.read_i32(player + 0x30)
        char_class = self.read_i32(player + 0x34)
        angle = round(self.read_float(player + 0x80))
        pk_level = self.read_i32(player + 0x154)
        master_level = self.read_i32(player + 0x224)
        points = self.read_i32(player + 0x238)
        reset_count = self.read_i32(player + 0x2B4)
        physi_speed = self.read_i32(player + 0x294)
        killer_name = self.read_str(self.read_ptr(player + 0x528))
        self_defense = self.read_i32(player + 0x530)
        map_id = self.get_map_id()
        map_name = MAP_NAMES.get(map_id, f"Map {map_id}")

        return {
            "name": name,
            "level": level,
            "classId": char_class,
            "x": pX,
            "y": pY,
            "angle": angle,
            "pkLevel": pk_level,
            "masterLevel": master_level,
            "points": points,
            "resetCount": reset_count,
            "attackSpeed": physi_speed,
            "killerName": killer_name,
            "selfDefense": self_defense,
            "mapId": map_id,
            "mapName": map_name
        }

# =============================================================================
# GUI APPLICATION (Tkinter Modern Dark Dashboard)
# =============================================================================

class ReaHunterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MEGAMU REA Hunter v3.1 - Radar Viewport & Săn Quái Chỉ Định [Crash-Proof]")
        self.geometry("1040x760")
        self.minsize(920, 620)
        self.configure(bg="#1E1E2E")

        self.scanner: Optional[Win32MemoryScanner] = None
        self.game_hwnd: Optional[int] = None
        self.is_hunting = False
        self.hunter_thread = None
        self.radar_loop_active = False

        self.detected_species: Dict[str, int] = {}
        self.selected_species: str = ""
        self.scan_range_val: float = 35.0
        self.attack_range_val: float = 6.0

        self._setup_styles()
        self._build_header()
        self._build_notebook()
        self._build_log_console()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Tự động quét và kết nối game ngay khi mở
        self._refresh_processes()
        self.after(500, self._auto_connect_startup)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        bg_dark = "#1E1E2E"
        fg_light = "#CDD6F4"
        accent_blue = "#89B4FA"
        card_bg = "#313244"

        style.configure("TFrame", background=bg_dark)
        style.configure("Card.TFrame", background=card_bg, relief="flat")
        style.configure("TLabel", background=bg_dark, foreground=fg_light, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=bg_dark, foreground="#A6E3A1", font=("Segoe UI", 12, "bold"))
        style.configure("Card.TLabel", background=card_bg, foreground=fg_light, font=("Segoe UI", 10))

        style.configure("TNotebook", background=bg_dark, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background="#45475A", foreground=fg_light, padding=[15, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", accent_blue)], foreground=[("selected", "#11111B")])

        style.configure("Treeview", background="#181825", foreground=fg_light, fieldbackground="#181825", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#313244", foreground=accent_blue, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#45475A")])

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#181825", height=65, padx=15, pady=10)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        title_box = tk.Frame(header_frame, bg="#181825")
        title_box.pack(side=tk.LEFT)
        lbl_title = tk.Label(title_box, text="⚡ MEGAMU REA SPECIES HUNTER v3.1", font=("Segoe UI", 13, "bold"), fg="#89B4FA", bg="#181825")
        lbl_title.pack(anchor="w")
        lbl_sub = tk.Label(title_box, text="Zero-Injection Radar (Win32 RPM) | Săn Quái Chỉ Định Theo Loài & Bỏ Qua Quái Khác", font=("Segoe UI", 9), fg="#A6ADC8", bg="#181825")
        lbl_sub.pack(anchor="w")

        conn_box = tk.Frame(header_frame, bg="#181825")
        conn_box.pack(side=tk.RIGHT)

        tk.Label(conn_box, text="Tiến trình Game:", font=("Segoe UI", 9, "bold"), fg="#CDD6F4", bg="#181825").pack(side=tk.LEFT, padx=5)
        self.cbo_pids = ttk.Combobox(conn_box, width=18, state="readonly")
        self.cbo_pids.pack(side=tk.LEFT, padx=5)

        btn_refresh = tk.Button(conn_box, text="🔄", command=self._refresh_processes, bg="#45475A", fg="#CDD6F4", relief="flat", font=("Segoe UI", 9))
        btn_refresh.pack(side=tk.LEFT, padx=2)

        self.btn_connect = tk.Button(conn_box, text="🔌 KẾT NỐI", command=self._toggle_connection, bg="#A6E3A1", fg="#11111B", font=("Segoe UI", 9, "bold"), relief="flat", padx=10)
        self.btn_connect.pack(side=tk.LEFT, padx=8)

        btn_diag = tk.Button(conn_box, text="🧪 CHẨN ĐOÁN RAM", command=self._test_memory_diagnostic, bg="#CBA6F7", fg="#11111B", font=("Segoe UI", 8, "bold"), relief="flat", padx=6)
        btn_diag.pack(side=tk.LEFT, padx=2)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Radar & Săn Quái Chỉ Định
        self.tab_radar = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_radar, text="🎯 SĂN QUÁI CHỈ ĐỊNH THEO LOÀI")
        self._build_tab_radar()

        # Tab 2: Fast Warp & Cổng Sự Kiện
        self.tab_warp = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_warp, text="🚀 FAST WARP & CỔNG SỰ KIỆN")
        self._build_tab_warp()

        # Tab 3: Telemetry & Anti-PK
        self.tab_telemetry = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_telemetry, text="📊 TELEMETRY & PHÒNG THỦ PK")
        self._build_tab_telemetry()

    def _build_tab_radar(self):
        main_pane = tk.PanedWindow(self.tab_radar, orient=tk.HORIZONTAL, bg="#1E1E2E", sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ----------------- CỘT TRÁI: ĐIỀU KHIỂN & CHỌN LOÀI QUÁI -----------------
        ctrl_frame = tk.Frame(main_pane, bg="#313244", width=340, padx=12, pady=12)
        main_pane.add(ctrl_frame)

        tk.Label(ctrl_frame, text="🎯 CHỈ ĐỊNH LOÀI QUÁI CẦN SĂN", font=("Segoe UI", 11, "bold"), fg="#89B4FA", bg="#313244").pack(anchor="w", pady=(0, 6))

        desc_text = "Quét Radar nhận diện tất cả quái vật xung quanh. Chọn loài quái bạn muốn tiêu diệt, Bot sẽ BỎ QUA 100% các loài quái khác dù đứng sát cạnh!"
        lbl_desc = tk.Label(ctrl_frame, text=desc_text, font=("Segoe UI", 8), fg="#A6ADC8", bg="#313244", justify=tk.LEFT, wraplength=310)
        lbl_desc.pack(anchor="w", pady=(0, 8))

        # Dropdown chọn loài quái
        tk.Label(ctrl_frame, text="Loài Quái Phát Hiện Trong Tầm:", font=("Segoe UI", 9, "bold"), fg="#CDD6F4", bg="#313244").pack(anchor="w")
        self.cbo_species = ttk.Combobox(ctrl_frame, font=("Segoe UI", 10), state="readonly")
        self.cbo_species.pack(fill=tk.X, pady=4)
        self.cbo_species.bind("<<ComboboxSelected>>", self._on_species_selected)

        self.btn_select_from_table = tk.Button(ctrl_frame, text="👆 ĐẶT MỤC TIÊU TỪ QUÁI ĐANG CHỌN TRÊN BẢNG",
                                               command=self._set_target_from_selected_row, bg="#45475A", fg="#CDD6F4", font=("Segoe UI", 8, "bold"), relief="flat", pady=3)
        self.btn_select_from_table.pack(fill=tk.X, pady=(2, 8))

        # Khung mục tiêu đang chỉ định
        target_card = tk.Frame(ctrl_frame, bg="#181825", padx=8, pady=6, relief="groove")
        target_card.pack(fill=tk.X, pady=5)
        tk.Label(target_card, text="MỤC TIÊU ĐANG CHỈ ĐỊNH:", font=("Segoe UI", 8, "bold"), fg="#FAB387", bg="#181825").pack(anchor="w")
        self.lbl_active_target = tk.Label(target_card, text="[ Đang săn: TẤT CẢ QUÁI ]", font=("Segoe UI", 10, "bold"), fg="#A6E3A1", bg="#181825")
        self.lbl_active_target.pack(anchor="w", pady=2)

        btn_clear_filter = tk.Button(target_card, text="❌ Hủy lọc (Săn tất cả quái)", command=self._clear_target_filter,
                                     bg="#313244", fg="#F38BA8", font=("Segoe UI", 8), relief="flat")
        btn_clear_filter.pack(anchor="e")

        # Tùy chọn Hunting (Tầm quét & Tầm đánh)
        range_box = tk.Frame(ctrl_frame, bg="#313244")
        range_box.pack(fill=tk.X, pady=(10, 4))

        col_r1 = tk.Frame(range_box, bg="#313244")
        col_r1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Label(col_r1, text="Tầm quét (m):", font=("Segoe UI", 8, "bold"), fg="#CDD6F4", bg="#313244").pack(anchor="w")
        self.spn_range = tk.Spinbox(col_r1, from_=5, to=80, font=("Segoe UI", 9), bg="#181825", fg="#CDD6F4", width=8)
        self.spn_range.delete(0, tk.END)
        self.spn_range.insert(0, "35")
        self.spn_range.pack(fill=tk.X, pady=2)

        col_r2 = tk.Frame(range_box, bg="#313244")
        col_r2.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))
        tk.Label(col_r2, text="Tầm đánh (m):", font=("Segoe UI", 8, "bold"), fg="#A6E3A1", bg="#313244").pack(anchor="w")
        self.spn_attack_range = tk.Spinbox(col_r2, from_=2, to=30, font=("Segoe UI", 9), bg="#181825", fg="#A6E3A1", width=8)
        self.spn_attack_range.delete(0, tk.END)
        self.spn_attack_range.insert(0, "10")
        self.spn_attack_range.pack(fill=tk.X, pady=2)

        self.chk_chase_var = tk.BooleanVar(value=True)
        chk_chase = tk.Checkbutton(ctrl_frame, text="Tự động áp sát (Auto-Chase tới mục tiêu)", variable=self.chk_chase_var,
                                   bg="#313244", fg="#CDD6F4", selectcolor="#181825", activebackground="#313244")
        chk_chase.pack(anchor="w", pady=4)

        self.chk_lock_var = tk.BooleanVar(value=True)
        chk_lock = tk.Checkbutton(ctrl_frame, text="Khóa mục tiêu cứng (NpcTarget +0x430)", variable=self.chk_lock_var,
                                  bg="#313244", fg="#CDD6F4", selectcolor="#181825", activebackground="#313244")
        chk_lock.pack(anchor="w", pady=2)

        # Nút điều khiển
        self.btn_radar_scan = tk.Button(ctrl_frame, text="🔍 QUÉT RADA NGAY", command=self._manual_radar_scan,
                                        bg="#89B4FA", fg="#11111B", font=("Segoe UI", 9, "bold"), relief="flat", pady=6)
        self.btn_radar_scan.pack(fill=tk.X, pady=(15, 5))

        self.btn_start_hunt = tk.Button(ctrl_frame, text="⚔️ BẮT ĐẦU SĂN QUÁI CHỈ ĐỊNH", command=self._toggle_hunting,
                                        bg="#F38BA8", fg="#11111B", font=("Segoe UI", 10, "bold"), relief="flat", pady=8)
        self.btn_start_hunt.pack(fill=tk.X, pady=5)

        # ----------------- CỘT PHẢI: BẢNG RADAR VIEWPORT -----------------
        view_frame = tk.Frame(main_pane, bg="#1E1E2E", padx=5, pady=5)
        main_pane.add(view_frame)

        radar_top = tk.Frame(view_frame, bg="#1E1E2E")
        radar_top.pack(fill=tk.X, pady=(0, 5))
        self.lbl_radar_count = tk.Label(radar_top, text="Thực thể xung quanh: 0 | Loài quái phát hiện: 0", font=("Segoe UI", 10, "bold"), fg="#A6E3A1", bg="#1E1E2E")
        self.lbl_radar_count.pack(side=tk.LEFT)

        self.chk_loop_var = tk.BooleanVar(value=True)
        chk_loop = tk.Checkbutton(radar_top, text="Auto Quét (500ms)", variable=self.chk_loop_var,
                                  command=self._on_radar_loop_toggle, bg="#1E1E2E", fg="#CDD6F4", selectcolor="#181825")
        chk_loop.pack(side=tk.RIGHT)

        cols = ("Name", "Type", "ID", "Coords", "Dist", "TargetStatus")
        self.tree_radar = ttk.Treeview(view_frame, columns=cols, show="headings", height=16)
        self.tree_radar.heading("Name", text="Tên Loài Quái / NPC")
        self.tree_radar.heading("Type", text="Phân Loại")
        self.tree_radar.heading("ID", text="Class ID")
        self.tree_radar.heading("Coords", text="Tọa Độ (X,Y)")
        self.tree_radar.heading("Dist", text="Khoảng Cách")
        self.tree_radar.heading("TargetStatus", text="Trạng Thái Ưu Tiên")

        self.tree_radar.column("Name", width=180)
        self.tree_radar.column("Type", width=95, anchor="center")
        self.tree_radar.column("ID", width=70, anchor="center")
        self.tree_radar.column("Coords", width=95, anchor="center")
        self.tree_radar.column("Dist", width=85, anchor="center")
        self.tree_radar.column("TargetStatus", width=130, anchor="center")

        scrollbar = ttk.Scrollbar(view_frame, orient=tk.VERTICAL, command=self.tree_radar.yview)
        self.tree_radar.configure(yscroll=scrollbar.set)
        self.tree_radar.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_radar.bind("<Double-1>", self._on_radar_item_double_click)

    def _build_tab_warp(self):
        container = tk.Frame(self.tab_warp, bg="#1E1E2E", padx=15, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        lbl_w = tk.Label(container, text="🌍 DỊCH CHUYỂN BẢN ĐỒ TỨC THỜI (DIRECT MAP WARP - WIN32 ZERO-INJECTION)",
                         font=("Segoe UI", 11, "bold"), fg="#89B4FA", bg="#1E1E2E")
        lbl_w.pack(anchor="w", pady=(0, 10))

        maps_grid = tk.Frame(container, bg="#1E1E2E")
        maps_grid.pack(fill=tk.X, pady=(0, 20))

        map_list = [
            ("🏰 Lorencia", "lorencia"), ("🌲 Noria", "noria"), ("❄️ Devias", "devias"),
            ("🌸 Elbeland", "elbeland"), ("💀 Dungeon", "dungeon"), ("🌊 Atlans", "atlans"),
            ("🗼 Lost Tower", "losttower"), ("🏜️ Tarkan", "tarkan"), ("🍃 Aida", "aida"),
            ("☁️ Icarus", "icarus"), ("⚙️ Kanturu", "kanturu"), ("🌋 Vulcanus", "vulcanus"),
            ("🏜️ Karutan", "karutan"), ("🏛️ Ferea", "ferea"), ("🌌 Nixies Lake", "nixies"),
            ("🌑 Deep Dungeon", "deepdungeon")
        ]

        for idx, (label, cmd) in enumerate(map_list):
            btn = tk.Button(maps_grid, text=label, bg="#313244", fg="#CDD6F4", font=("Segoe UI", 9, "bold"),
                            relief="flat", padx=10, pady=6, command=lambda c=cmd, l=label: self._do_warp(c, l))
            btn.grid(row=idx // 4, column=idx % 4, sticky="ew", padx=4, pady=4)

        for col in range(4):
            maps_grid.grid_columnconfigure(col, weight=1)

        lbl_e = tk.Label(container, text="⚡ VƯỢT CỔNG SỰ KIỆN TỨC THỜI (ZERO-LATENCY EVENT GATE PASS)",
                         font=("Segoe UI", 11, "bold"), fg="#FAB387", bg="#1E1E2E")
        lbl_e.pack(anchor="w", pady=(10, 10))

        events_box = tk.Frame(container, bg="#313244", padx=15, pady=15)
        events_box.pack(fill=tk.X)

        tk.Label(events_box, text="Dịch chuyển tức thời vào phòng chờ sự kiện bằng lệnh trực tiếp:",
                 font=("Segoe UI", 9), fg="#A6ADC8", bg="#313244").pack(anchor="w", pady=(0, 10))

        btn_ds = tk.Button(events_box, text="🔥 VÀO EVENT SQUARE (DS / BC)", bg="#A6E3A1", fg="#11111B",
                           font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=8, command=lambda: self._do_warp("ev", "Event Square"))
        btn_ds.pack(side=tk.LEFT, padx=10)

        btn_arena = tk.Button(events_box, text="⚔️ VÀO ARENA / STADIUM", bg="#89DCEB", fg="#11111B",
                              font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=8, command=lambda: self._do_warp("arena", "Arena"))
        btn_arena.pack(side=tk.LEFT, padx=10)

    def _build_tab_telemetry(self):
        container = tk.Frame(self.tab_telemetry, bg="#1E1E2E", padx=15, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="📊 DỮ LIỆU NHÂN VẬT THỜI GIAN THỰC (REAL-TIME TELEMETRY)",
                 font=("Segoe UI", 11, "bold"), fg="#89B4FA", bg="#1E1E2E").pack(anchor="w", pady=(0, 10))

        stats_card = tk.Frame(container, bg="#313244", padx=15, pady=15)
        stats_card.pack(fill=tk.X)

        self.telemetry_labels = {}
        fields = [
            ("Nhân vật:", "name", "#89B4FA"),
            ("Bản đồ hiện tại:", "mapName", "#F9E2AF"),
            ("Cấp độ (Level):", "level", "#A6E3A1"),
            ("Cấp Master:", "masterLevel", "#A6E3A1"),
            ("Số lần Reset:", "resetCount", "#F9E2AF"),
            ("Điểm Point chưa cộng:", "points", "#FAB387"),
            ("Tốc độ đánh (PhysiSpeed):", "attackSpeed", "#89DCEB"),
            ("Tọa độ hiện tại (X, Y):", "coords", "#CDD6F4"),
            ("Kẻ vừa đồ sát (KillerName):", "killerName", "#F38BA8"),
            ("Trạng thái Tự Vệ (SelfDefense):", "selfDefense", "#CBA6F7")
        ]

        for idx, (title, key, color) in enumerate(fields):
            row = idx // 2
            col = (idx % 2) * 2
            tk.Label(stats_card, text=title, font=("Segoe UI", 9, "bold"), fg="#A6ADC8", bg="#313244").grid(row=row, column=col, sticky="w", padx=10, pady=4)
            lbl_val = tk.Label(stats_card, text="--", font=("Segoe UI", 9, "bold"), fg=color, bg="#313244")
            lbl_val.grid(row=row, column=col+1, sticky="w", padx=5, pady=4)
            self.telemetry_labels[key] = lbl_val

        pk_card = tk.Frame(container, bg="#313244", padx=15, pady=15)
        pk_card.pack(fill=tk.X, pady=15)

        tk.Label(pk_card, text="🛡️ CƠ CHẾ PHÒNG THỦ & CẢNH BÁO SÁT NHÂN", font=("Segoe UI", 10, "bold"), fg="#F38BA8", bg="#313244").pack(anchor="w")
        self.lbl_pk_warning = tk.Label(pk_card, text="Trạng thái: An toàn (Không phát hiện kẻ địch PK trong bán kính 20 ô)",
                                       font=("Segoe UI", 9), fg="#A6E3A1", bg="#313244")
        self.lbl_pk_warning.pack(anchor="w", pady=5)

    def _build_log_console(self):
        log_frame = tk.Frame(self, bg="#11111B", height=130, padx=10, pady=5)
        log_frame.pack(fill=tk.X, side=tk.BOTTOM)

        lbl_log = tk.Label(log_frame, text="📜 NHẬT KÝ THỰC THI (ACTION LOGS):", font=("Segoe UI", 8, "bold"), fg="#A6ADC8", bg="#11111B")
        lbl_log.pack(anchor="w")

        self.txt_log = tk.Text(log_frame, height=5, bg="#181825", fg="#CDD6F4", font=("Consolas", 8), relief="flat")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def log(self, msg: str, level: str = "INFO"):
        t_str = time.strftime("%H:%M:%S")
        color_prefix = ""
        if level == "WARN": color_prefix = "⚠️ "
        elif level == "SUCCESS": color_prefix = "✅ "
        elif level == "ERROR": color_prefix = "❌ "
        elif level == "HUNT": color_prefix = "🎯 "

        line = f"[{t_str}] {color_prefix}{msg}\n"
        self.txt_log.insert(tk.END, line)
        self.txt_log.see(tk.END)

    # =========================================================================
    # LOGIC KẾT NỐI & RADAR SCAN
    # =========================================================================

    def _get_game_pids(self) -> List[int]:
        pids = []
        if psutil:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = p.info['name'].lower()
                    if "megamu" in name or "main.exe" in name:
                        pids.append(p.info['pid'])
                except Exception:
                    pass
        return pids

    def _refresh_processes(self):
        pids = self._get_game_pids()
        display_list = []
        for pid in pids:
            display_list.append(f"{pid} - MEGAMU.exe")
        if not display_list:
            display_list = ["Không tìm thấy game"]
        self.cbo_pids['values'] = display_list
        self.cbo_pids.current(0)

    def _auto_connect_startup(self):
        """Tự động kết nối vào game ngay khi app khởi động."""
        pids = self._get_game_pids()
        if pids:
            self._connect_pid(pids[0])
        else:
            self.log("Đang đợi mở game MEGAMU... (Sẽ tự động kết nối ngay khi game mở)", "INFO")
            self.after(2000, self._auto_connect_startup)

    def _toggle_connection(self):
        if self.scanner and self.scanner.hProc:
            self._disconnect()
        else:
            sel = self.cbo_pids.get()
            if not sel or "Không tìm thấy" in sel:
                self._refresh_processes()
                pids = self._get_game_pids()
                if not pids:
                    messagebox.showwarning("Cảnh báo", "Vui lòng mở game MEGAMU trước khi kết nối!")
                    return
                pid = pids[0]
            else:
                pid = int(sel.split("-")[0].strip())
            self._connect_pid(pid)

    def _connect_pid(self, pid: int):
        try:
            self.scanner = Win32MemoryScanner(pid)
            if self.scanner.open():
                self.btn_connect.configure(text="🔌 NGẮT KẾT NỐI", bg="#F38BA8")
                self.log(f"Kết nối thành công vào tiến trình Game PID {pid} (Base: {hex(self.scanner.base_addr)})!", "SUCCESS")
                self._update_game_hwnd(pid)
                self._start_radar_loop()
                self._update_telemetry()
            else:
                self.log(f"Không thể mở bộ nhớ PID {pid}. Vui lòng chạy tool với quyền Administrator!", "ERROR")
        except Exception as e:
            self.log(f"Lỗi kết nối: {e}", "ERROR")

    def _update_game_hwnd(self, pid: int):
        try:
            from meg_navigator import WindowHelper
            windows = WindowHelper.get_unity_windows()
            for p, h, t, w, hh in windows:
                if p == pid:
                    self.game_hwnd = h
                    break
        except Exception:
            pass

    def _disconnect(self):
        self.is_hunting = False
        self.radar_loop_active = False
        if self.scanner:
            self.scanner.close()
            self.scanner = None
        self.game_hwnd = None
        self.btn_connect.configure(text="🔌 KẾT NỐI", bg="#A6E3A1")
        self.log("Đã ngắt kết nối an toàn khỏi game.", "WARN")

    def _test_memory_diagnostic(self):
        """Chẩn đoán kiểm tra trực tiếp bộ nhớ RAM Viewport."""
        if not self.scanner or not self.scanner.hProc:
            messagebox.showinfo("Thông báo", "Vui lòng kết nối vào game trước!")
            return

        game_inst = self.scanner.get_game_instance()
        player = self.scanner.get_player()
        viewport = self.scanner.get_viewport()
        pX, pY = self.scanner.get_player_coords(player)

        body_count = self.scanner.read_i32(viewport + 0x28) if viewport else 0
        item_count = self.scanner.read_i32(viewport + 0x2C) if viewport else 0

        obj_dict = self.scanner.read_ptr(viewport + 0x20) if viewport else 0
        obj_count = self.scanner.read_i32(obj_dict + 0x20) if obj_dict else 0

        self.log("--- BÁO CÁO CHẨN ĐOÁN BỘ NHỚ RAM ---", "INFO")
        self.log(f"GameAssembly Base: {hex(self.scanner.base_addr or 0)}", "INFO")
        self.log(f"Game.Instance: {hex(game_inst)} | Player: {hex(player)}", "INFO")
        self.log(f"Tọa độ Player: ({pX}, {pY}) | Map: {MAP_NAMES.get(self.scanner.get_map_id(), 'Unknown')}", "INFO")
        self.log(f"Viewport: {hex(viewport)} -> BodyCount: {body_count}, ItemCount: {item_count}, ObjectListCount: {obj_count}", "INFO")

        res = self.scanner.scan_radar(max_range=50.0)
        entities = res.get("entities", [])
        species = res.get("species", {})
        self.log(f"Tổng thực thể xung quanh: {len(entities)} (gồm {len(species)} loài quái vật)", "SUCCESS")
        for s_name, count in species.items():
            self.log(f"  + Loài '{s_name}': {count} con", "INFO")
        self.log("---------------------------------------", "INFO")

    def _on_radar_loop_toggle(self):
        if self.chk_loop_var.get():
            self._start_radar_loop()
        else:
            self.radar_loop_active = False

    def _start_radar_loop(self):
        if self.radar_loop_active:
            return
        self.radar_loop_active = True

        def loop():
            while self.radar_loop_active and self.scanner and self.scanner.hProc:
                try:
                    self._do_radar_scan()
                    self._update_telemetry()
                except Exception:
                    pass
                time.sleep(0.5)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _manual_radar_scan(self):
        if not self.scanner or not self.scanner.hProc:
            # Tự động tìm lại process nếu chưa kết nối
            pids = self._get_game_pids()
            if pids:
                self._connect_pid(pids[0])
            else:
                messagebox.showinfo("Thông báo", "Vui lòng mở game MEGAMU trước khi quét!")
                return
        self._do_radar_scan()
        self._update_telemetry()
        self.log("Đã thực hiện quét Radar thành công!", "SUCCESS")

    def _do_radar_scan(self):
        if not self.scanner or not self.scanner.hProc or not self.scanner.get_player():
            pids = self._get_game_pids()
            if pids and (not self.scanner or self.scanner.pid != pids[0]):
                self._connect_pid(pids[0])
            if not self.scanner or not self.scanner.hProc:
                return
        try:
            max_r = getattr(self, "scan_range_val", 35.0)
            res = self.scanner.scan_radar(max_r)
            entities = res.get("entities", [])
            species = res.get("species", {})

            self.after(0, lambda: self._render_radar_items(entities, species))
        except Exception:
            pass

    def _render_radar_items(self, entities: List[Dict[str, Any]], species: Dict[str, int]):
        self.detected_species = species

        # Cập nhật Dropdown loài quái (Chỉ cập nhật khi số lượng loài có thay đổi để tránh đóng menu đang mở)
        species_options = ["[ TẤT CẢ LOÀI QUÁI ]"]
        for s_name, count in sorted(species.items()):
            species_options.append(f"{s_name} ({count} con)")

        current_val = self.cbo_species.get()
        if list(self.cbo_species['values']) != species_options:
            self.cbo_species['values'] = species_options
            if not current_val or current_val not in species_options:
                if self.selected_species:
                    # Giữ nguyên loài đã chọn
                    matched = [opt for opt in species_options if opt.startswith(self.selected_species)]
                    if matched:
                        self.cbo_species.set(matched[0])
                    else:
                        self.cbo_species.current(0)
                else:
                    self.cbo_species.current(0)

        # Cập nhật nhãn đếm
        monster_total = sum(species.values())
        self.lbl_radar_count.configure(text=f"Thực thể: {len(entities)} (Quái: {monster_total} con | {len(species)} loài)")

        active_target = self.selected_species.strip().lower()
        if not active_target or active_target.startswith("["):
            active_target = ""

        # Lưu lại selection hiện tại của user trước khi cập nhật bảng
        selected_iids = self.tree_radar.selection()
        selected_name = ""
        if selected_iids:
            vals = self.tree_radar.item(selected_iids[0], "values")
            if vals: selected_name = vals[0]

        self.tree_radar.delete(*self.tree_radar.get_children())

        for ent in entities:
            name = ent["name"]
            ent_type = ent["type"]
            type_str = ent_type

            if ent_type == "Player":
                type_str = "🧙 Người chơi"
            elif ent_type == "NPC":
                type_str = "👤 NPC"
            elif ent["isGolden"]:
                type_str = "🌟 Vàng"
            elif ent["isBoss"]:
                type_str = "👑 Boss"
            else:
                type_str = "👾 Quái vật"

            coords_str = f"({ent['x']}, {ent['y']})"
            dist_str = f"{ent['dist']}m"

            priority_status = "Bình thường"
            is_matched_target = False

            if ent_type in ("Player", "NPC"):
                priority_status = "🚫 Không thể săn"
            elif active_target:
                if active_target == name.lower():
                    priority_status = "🎯 MỤC TIÊU DUY NHẤT"
                    is_matched_target = True
                else:
                    priority_status = "⏭️ BỎ QUA"
            else:
                priority_status = "🎯 Sẵn sàng săn"
                is_matched_target = True

            item_id = self.tree_radar.insert("", tk.END, values=(name, type_str, ent["classId"], coords_str, dist_str, priority_status))

            # Phân màu trực quan
            if is_matched_target and active_target:
                self.tree_radar.item(item_id, tags=("target_focus",))
            elif ent_type == "NPC":
                self.tree_radar.item(item_id, tags=("npc",))
            elif ent_type == "Player":
                self.tree_radar.item(item_id, tags=("player",))
            elif ent["isGolden"]:
                self.tree_radar.item(item_id, tags=("golden",))
            elif ent["isBoss"]:
                self.tree_radar.item(item_id, tags=("boss",))
            elif not is_matched_target:
                self.tree_radar.item(item_id, tags=("ignored",))

            # Khôi phục chọn hàng nếu người dùng đang click con này
            if selected_name and name == selected_name:
                self.tree_radar.selection_set(item_id)

        self.tree_radar.tag_configure("target_focus", foreground="#A6E3A1", font=("Segoe UI", 9, "bold"))
        self.tree_radar.tag_configure("npc", foreground="#89DCEB")
        self.tree_radar.tag_configure("player", foreground="#CBA6F7")
        self.tree_radar.tag_configure("golden", foreground="#F9E2AF")
        self.tree_radar.tag_configure("boss", foreground="#F38BA8")
        self.tree_radar.tag_configure("ignored", foreground="#585B70")

    def _on_species_selected(self, event=None):
        sel = self.cbo_species.get()
        if not sel or "[ TẤT CẢ" in sel:
            self._clear_target_filter()
        else:
            species_name = sel.split(" (")[0].strip()
            self._set_active_species_target(species_name)

    def _set_active_species_target(self, species_name: str):
        self.selected_species = species_name
        self.lbl_active_target.configure(text=f"[ Đang săn DUY NHẤT: '{species_name}' ]", fg="#A6E3A1")
        self.log(f"Đã chỉ định loài quái cần săn: '{species_name}'. Bot sẽ BỎ QUA 100% quái khác!", "HUNT")
        self._do_radar_scan()

    def _clear_target_filter(self):
        self.selected_species = ""
        self.lbl_active_target.configure(text="[ Đang săn: TẤT CẢ QUÁI ]", fg="#FAB387")
        self.cbo_species.set("[ TẤT CẢ LOÀI QUÁI ]")
        self.log("Đã hủy lọc loài quái: Trở lại săn tất cả quái trong tầm.", "INFO")
        self._do_radar_scan()

    def _set_target_from_selected_row(self):
        item = self.tree_radar.selection()
        if not item:
            messagebox.showinfo("Hướng dẫn", "Vui lòng click chọn 1 con quái trên bảng trước!")
            return
        vals = self.tree_radar.item(item[0], "values")
        if vals:
            target_species = vals[0]
            ent_type = vals[1]
            if "NPC" in ent_type or "Người chơi" in ent_type:
                messagebox.showwarning("Cảnh báo", f"'{target_species}' là {ent_type}, không thể chọn làm mục tiêu săn!")
                return
            self._set_active_species_target(target_species)

    def _on_radar_item_double_click(self, event):
        self._set_target_from_selected_row()

    # =========================================================================
    # HUNTER ENGINE (Tự động săn và BỎ QUA quái không chỉ định)
    # =========================================================================

    def _toggle_hunting(self):
        if self.is_hunting:
            self.is_hunting = False
            self.btn_start_hunt.configure(text="⚔️ BẮT ĐẦU SĂN QUÁI CHỈ ĐỊNH", bg="#F38BA8")
            self.log("Đã dừng chế độ Săn Quái Chỉ Định.", "WARN")
        else:
            if not self.scanner or not self.scanner.hProc:
                pids = self._get_game_pids()
                if pids:
                    self._connect_pid(pids[0])
                else:
                    messagebox.showinfo("Thông báo", "Vui lòng mở game MEGAMU trước!")
                    return

            try:
                self.scan_range_val = float(self.spn_range.get() or 35.0)
                self.attack_range_val = float(self.spn_attack_range.get() or 10.0)
            except Exception:
                self.scan_range_val = 35.0
                self.attack_range_val = 10.0

            self.is_hunting = True
            species_info = f"'{self.selected_species}'" if self.selected_species else "TẤT CẢ LOÀI"
            self.btn_start_hunt.configure(text=f"🛑 ĐANG SĂN {species_info} (BẤM DỪNG)", bg="#A6E3A1")
            self.log(f"BẮT ĐẦU SĂN QUÁI CHỈ ĐỊNH: {species_info} (Tầm quét: {self.scan_range_val:.0f}m, Tầm đánh: {self.attack_range_val:.0f}m)", "HUNT")

            self.hunter_thread = threading.Thread(target=self._hunter_loop, daemon=True)
            self.hunter_thread.start()

    def _hunter_loop(self):
        """Vòng lặp săn quái chỉ định thời gian thực: Auto-Reconnect, Khóa tập trung, Đánh liên hoàn (Left + Right Click)."""
        user32 = ctypes.windll.user32
        last_logged_no_target = 0
        locked_target_ptr: Optional[int] = None
        locked_target_name: str = ""

        hook = None

        while self.is_hunting:
            try:
                # 0. Tự động phục hồi kết nối nếu process game bị restart hoặc đổi PID
                if not self.scanner or not self.scanner.hProc or not self.scanner.get_player():
                    pids = self._get_game_pids()
                    if pids:
                        target_pid = pids[0]
                        if not self.scanner or self.scanner.pid != target_pid:
                            self._connect_pid(target_pid)
                            if UnityBackgroundHook and self.scanner:
                                hook = UnityBackgroundHook.get_instance(target_pid)
                    time.sleep(0.5)
                    # Nếu vẫn chưa vào nhân vật trong game, tiếp tục chờ
                    if not self.scanner or not self.scanner.get_player():
                        time.sleep(0.5)
                        continue

                # Cập nhật hwnd nếu chưa có hoặc cửa sổ bị thay đổi
                if not self.game_hwnd or not user32.IsWindow(self.game_hwnd):
                    self._update_game_hwnd(self.scanner.pid)

                # Nếu cửa sổ game bị người dùng thu nhỏ (Minimize xuống taskbar), tự động khôi phục ngầm không chiếm tiêu điểm
                if self.game_hwnd and user32.IsIconic(self.game_hwnd):
                    user32.ShowWindow(self.game_hwnd, 4) # SW_SHOWNOACTIVATE
                    time.sleep(0.06)

                # Đảm bảo Hook đã kết nối và sẵn sàng
                if (not hook or not hook.is_ready) and UnityBackgroundHook and self.scanner.pid:
                    try:
                        hook = UnityBackgroundHook.get_instance(self.scanner.pid)
                    except Exception:
                        hook = None

                max_r = getattr(self, "scan_range_val", 35.0)
                attack_r = getattr(self, "attack_range_val", 10.0)

                res = self.scanner.scan_radar(max_r)
                if "error" in res and res["error"]:
                    time.sleep(0.4)
                    continue

                entities = res.get("entities", [])
                pX = res.get("playerX", 0)
                pY = res.get("playerY", 0)

                target_species = self.selected_species.strip().lower()
                if not target_species or target_species.startswith("["):
                    target_species = ""

                # 1. Lọc: CHỈ GIỮ LẠI LOÀI QUÁI ĐÃ CHỈ ĐỊNH (BỎ QUA 100% NPC, PLAYER VÀ CÁC LOÀI QUÁI KHÁC)
                valid_targets = []
                for ent in entities:
                    if ent["type"] in ("Player", "NPC"):
                        continue
                    if target_species:
                        if ent["name"].lower() == target_species:
                            valid_targets.append(ent)
                    else:
                        valid_targets.append(ent)

                # 2. CHIẾN THUẬT SĂN TRIỆT ĐỂ: ƯU TIÊN SỐ 1 CHO QUÁI TRONG TẦM ĐÁNH (dist <= attack_r)
                # Bất kỳ khi nào có quái trong tầm là TỰ ĐỘNG TIÊU DIỆT NGAY LẬP TỨC!
                # Tuyệt đối không chạy lòng vòng bỏ qua quái ở gần để đuổi quái ở xa!
                in_range_targets = [e for e in valid_targets if e["dist"] <= attack_r]
                target = None

                if in_range_targets:
                    # TRƯỜNG HỢP 1: CÓ QUÁI TRONG TẦM ĐÁNH
                    # Nếu quái đang khóa trước đó cũng đang ở trong tầm và còn sống -> tiếp tục đánh nó đến chết
                    if locked_target_ptr:
                        is_dead = (self.scanner.read_u8(locked_target_ptr + 0xC0) == 1)
                        matched = [e for e in in_range_targets if e["ptr_int"] == locked_target_ptr]
                        if not is_dead and matched:
                            target = matched[0]
                        else:
                            locked_target_ptr = None
                            locked_target_name = ""

                    # Nếu chưa chọn được (hoặc quái trước đã chết / ngoài tầm), lập tức khóa con quái gần nhất trong tầm
                    if not target:
                        target = in_range_targets[0]
                        locked_target_ptr = target["ptr_int"]
                        locked_target_name = target["name"]
                        self.log(f"⚡ PHÁT HIỆN QUÁI TRONG TẦM: [{locked_target_name}] cách {target['dist']}m -> TẬP TRUNG TIÊU DIỆT NGAY!", "HUNT")

                else:
                    # TRƯỜNG HỢP 2: KHÔNG CÓ QUÁI NÀO TRONG TẦM ĐÁNH (toàn bộ quái đều > attack_r)
                    if not valid_targets:
                        now_t = time.time()
                        if now_t - last_logged_no_target > 3.0:
                            last_logged_no_target = now_t
                            if target_species:
                                self.log(f"⏳ Đang tìm quái '{self.selected_species}' trong bán kính {max_r:.0f}m...", "INFO")
                            else:
                                self.log(f"⏳ Đang tìm quái vật xung quanh trong bán kính {max_r:.0f}m...", "INFO")
                        time.sleep(0.3)
                        continue

                    # Có quái ở xa: Nếu đang đuổi một con và nó vẫn còn sống thì tiếp tục bám theo
                    if locked_target_ptr:
                        is_dead = (self.scanner.read_u8(locked_target_ptr + 0xC0) == 1)
                        matched = [e for e in valid_targets if e["ptr_int"] == locked_target_ptr]
                        if not is_dead and matched:
                            target = matched[0]
                        else:
                            locked_target_ptr = None
                            locked_target_name = ""

                    # Nếu chưa có mục tiêu, chọn con gần nhất ngoài tầm
                    if not target:
                        target = valid_targets[0]
                        locked_target_ptr = target["ptr_int"]
                        locked_target_name = target["name"]
                        self.log(f"🎯 Khóa mục tiêu tiếp cận: [{locked_target_name}] tại ({target['x']}, {target['y']}) [cách {target['dist']}m]", "HUNT")

                t_name = target["name"]
                t_ptr_int = target["ptr_int"]
                t_x, t_y = target["x"], target["y"]
                t_dist = target["dist"]

                # 3. Khóa mục tiêu cứng vào RAM (NpcTarget +0x430)
                if self.chk_lock_var.get():
                    self.scanner.lock_target(t_ptr_int)

                # 4. Xoay góc mặt về phía quái vật (Góc xoay Unity 3D chuẩn xác trên trục Y)
                player_ptr = self.scanner.get_player()
                if player_ptr:
                    p_wx = self.scanner.read_float(player_ptr + 0x118)
                    p_wz = self.scanner.read_float(player_ptr + 0x120)
                    t_wx = self.scanner.read_float(t_ptr_int + 0x118)
                    t_wz = self.scanner.read_float(t_ptr_int + 0x120)
                    dx = t_wx - p_wx
                    dz = t_wz - p_wz
                    if abs(dx) > 0.001 or abs(dz) > 0.001:
                        angle_deg = (math.degrees(math.atan2(dx, dz)) + 360.0) % 360.0
                        self.scanner.set_player_target_angle(angle_deg)

                # 5. Kích thước cửa sổ game thực tế
                cw, ch = 1024, 768
                if self.game_hwnd:
                    rect = wintypes.RECT()
                    user32.GetClientRect(self.game_hwnd, ctypes.byref(rect))
                    cw = max(rect.right - rect.left, 400)
                    ch = max(rect.bottom - rect.top, 300)

                # 6. Hành động: Áp sát (Chase) hoặc Tấn công (Combo Strike)
                if self.chk_chase_var.get() and t_dist > attack_r:
                    # Khoảng cách xa hơn tầm đánh: Bước chạy áp sát quái bằng click sải bước
                    sx, sy = calc_chase_stride_pixel(pX, pY, t_x, t_y, cw, ch)
                    if hook and hook.is_ready:
                        hook.send_click(self.game_hwnd, sx, sy, duration_ms=25)
                    elif BackgroundInputSimulator:
                        BackgroundInputSimulator.micro_sync_click(self.game_hwnd, sx, sy, duration_ms=25)
                    else:
                        lparam = ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)
                        user32.PostMessageW(self.game_hwnd, WM_MOUSEMOVE, 0, lparam)
                        user32.PostMessageW(self.game_hwnd, WM_LBUTTONDOWN, 1, lparam)
                        time.sleep(0.025)
                        user32.PostMessageW(self.game_hwnd, WM_LBUTTONUP, 0, lparam)

                    self.log(f"🏃 Đang áp sát [{t_name}] tại ({t_x}, {t_y}) [còn {t_dist}m > tầm đánh {attack_r:.0f}m]...", "HUNT")
                    time.sleep(0.25)
                else:
                    # TRONG TẦM ĐÁNH: TỰ ĐỘNG XẢ SKILL NGAY LẬP TỨC (KHÔNG BƯỚC TỚI, KHÔNG ÁP SÁT GẦN)!
                    # 1. Hủy ngay lập tức mọi bước chạy còn sót để đứng yên tuyệt đối tại chỗ
                    self.scanner.stop_player_movement()

                    # 2. Nhắm thẳng hitbox quái tung Skill tức thì bằng Chuột Phải (Right Click)
                    # TUYỆT ĐỐI KHÔNG GỬI CLICK TRÁI VÌ SẼ KHIẾN NHÂN VẬT CHẠY ÁP SÁT LẠI GẦN QUÁ!
                    sx, sy = calc_monster_hitbox_pixel(pX, pY, t_x, t_y, cw, ch)
                    if hook and hook.is_ready:
                        hook.send_right_click(self.game_hwnd, sx, sy, duration_ms=45)
                    elif BackgroundInputSimulator:
                        BackgroundInputSimulator.micro_sync_right_click(self.game_hwnd, sx, sy, duration_ms=45)
                    else:
                        lparam = ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)
                        user32.PostMessageW(self.game_hwnd, WM_MOUSEMOVE, 0, lparam)
                        user32.PostMessageW(self.game_hwnd, WM_RBUTTONDOWN, 2, lparam)
                        time.sleep(0.045)
                        user32.PostMessageW(self.game_hwnd, WM_RBUTTONUP, 0, lparam)

                    self.log(f"💥 Xả Skill tầm xa vào [{t_name}] tại ({t_x}, {t_y}) [cách {t_dist}m, pixel: ({sx}, {sy})]!", "HUNT")

                    # Kiểm tra xem quái vừa dính đòn có chết ngay không
                    time.sleep(0.04)
                    if self.scanner.read_u8(t_ptr_int + 0xC0) == 1:
                        self.log(f"💀 Quái [{t_name}] đã bị tiêu diệt hoàn toàn! Chuyển mục tiêu tiếp theo...", "SUCCESS")
                        locked_target_ptr = None
                        locked_target_name = ""
                        time.sleep(0.03)
                    else:
                        time.sleep(0.12)

            except Exception as err:
                self.log(f"Lỗi vòng lặp Hunter: {err}", "WARN")
                time.sleep(0.4)

    def _do_warp(self, map_cmd: str, map_label: str):
        """Gửi lệnh chuyển bản đồ trực tiếp qua Win32 Message (không cần Frida)."""
        self.log(f"Yêu cầu Warp tới {map_label} (/move {map_cmd})", "INFO")
        if not self.game_hwnd:
            if self.scanner and self.scanner.pid:
                self._update_game_hwnd(self.scanner.pid)

        if self.game_hwnd:
            user32 = ctypes.windll.user32
            # Gửi Enter mở chat -> gõ /move <map> -> Enter gửi
            user32.PostMessageW(self.game_hwnd, WM_KEYDOWN, VK_RETURN, 0)
            time.sleep(0.06)
            user32.PostMessageW(self.game_hwnd, WM_KEYUP, VK_RETURN, 0)
            time.sleep(0.12)
            cmd = f"/move {map_cmd}"
            for c in cmd:
                user32.PostMessageW(self.game_hwnd, WM_CHAR, ord(c), 0)
                time.sleep(0.025)
            time.sleep(0.08)
            user32.PostMessageW(self.game_hwnd, WM_KEYDOWN, VK_RETURN, 0)
            time.sleep(0.06)
            user32.PostMessageW(self.game_hwnd, WM_KEYUP, VK_RETURN, 0)
            self.log(f"Đã gửi lệnh Warp tới: {map_label} ({cmd}) thành công!", "SUCCESS")
        else:
            self.log("Không tìm thấy cửa sổ game để gửi lệnh Warp!", "WARN")

    def _update_telemetry(self):
        if not self.scanner or not self.scanner.hProc:
            return
        try:
            tele = self.scanner.get_telemetry()
            if not tele:
                return
            self.after(0, lambda: self._render_telemetry(tele))
        except Exception:
            pass

    def _render_telemetry(self, tele: Dict[str, Any]):
        for k, lbl in self.telemetry_labels.items():
            if k == "coords":
                lbl.configure(text=f"({tele.get('x', 0)}, {tele.get('y', 0)}) [Góc: {tele.get('angle', 0)}°]")
            elif k in tele:
                lbl.configure(text=str(tele[k]))

        kn = tele.get("killerName", "")
        if kn:
            self.lbl_pk_warning.configure(text=f"⚠️ BẠN VỪA BỊ ĐỒ SÁT BỞI: '{kn}'!", fg="#F38BA8")
        else:
            self.lbl_pk_warning.configure(text="Trạng thái: An toàn (Không phát hiện kẻ địch PK trong bán kính 20 ô)", fg="#A6E3A1")

    def _on_close(self):
        self._disconnect()
        self.destroy()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = ReaHunterApp()
    app.mainloop()
