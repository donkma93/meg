#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Entity Radar & Nearby Tracker (Tool Thử Nghiệm)
=====================================================
Công cụ quét và hiển thị thực thể xung quanh nhân vật theo thời gian thực:
- Nhận biết Bản đồ hiện tại (Map ID & Tên Map) và Tọa độ của bạn (X, Y).
- Quét danh sách Quái vật (Monster) trong bán kính N ô (Tên, Level, Tọa độ, Khoảng cách).
- Quét danh sách Người chơi (Player) trong bán kính N ô (Tên, Class, Level, Tọa độ, PK Level).
- Cảnh báo an toàn: Phát hiện người chơi Sát nhân (Quỷ đỏ PK) hoặc Admin / Game Master (GM).
- Cơ chế 100% Zero-Injection: Đọc trực tiếp bộ nhớ RAM (ReadProcessMemory) siêu tốc, không can thiệp game, không gây gián đoạn hay crash.
"""

import os
import sys
import time
import math
import ctypes
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import psutil
except ImportError:
    print("[ERROR] Cần thư viện psutil: pip install psutil")
    sys.exit(1)

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
        LIGHTRED_EX = LIGHTGREEN_EX = LIGHTYELLOW_EX = LIGHTCYAN_EX = LIGHTWHITE_EX = ""
    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        DIM = NORMAL = BRIGHT = RESET_ALL = ""

# =========================================================================
# BẢNG TRA CỨU CLASS & MAP & PK
# =========================================================================

CLASS_NAMES = {
    0: "Dark Wizard",
    1: "Dark Knight",
    2: "Fairy Elf",
    3: "Magic Gladiator",
    4: "Dark Lord",
    5: "Summoner",
    6: "Rage Fighter",
    7: "Grow Lancer",
    8: "Rune Wizard",
    9: "Slayer",
    10: "Gun Crusher",
    11: "Kundun Mephis",
    12: "Mage Lemuria",
    13: "Illusion Knight",
    # Legacy bitshift fallback
    16: "Dark Knight", 32: "Fairy Elf", 48: "Magic Gladiator",
    64: "Dark Lord", 80: "Summoner", 96: "Rage Fighter",
    112: "Grow Lancer", 128: "Rune Wizard", 144: "Slayer", 160: "Gun Crusher"
}

PK_LEVEL_MAP = {
    1: ("Anh Hùng Cấp 2", Fore.CYAN),
    2: ("Anh Hùng Cấp 1", Fore.LIGHTCYAN_EX),
    3: ("Bình Thường", Fore.GREEN),
    4: ("Cảnh Cáo (1 Mạng)", Fore.YELLOW),
    5: ("Quỷ Đỏ Cấp 1 (PK)", Fore.LIGHTRED_EX),
    6: ("Đại Sát Nhân (PK)", Fore.RED),
}

def get_resource_path(relative_path: str) -> str:
    """Hỗ trợ tìm file cấu hình cả khi chạy file Python trực tiếp lẫn khi đóng gói PyInstaller .exe"""
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(p):
            return p
    if getattr(sys, 'frozen', False):
        p_exe = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(p_exe):
            return p_exe
    p_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
    if os.path.exists(p_file):
        return p_file
    return p_file

def load_map_names() -> Dict[int, str]:
    """Tải tên map từ config/map_commands.json nếu có."""
    mapping = {
        0: "Lorencia", 1: "Dungeon", 2: "Devias", 3: "Noria", 4: "Lost Tower",
        6: "Arena", 7: "Atlans", 8: "Tarkan", 10: "Icarus", 30: "Valley of Loren",
        31: "Land of Trials", 33: "Aida", 34: "Crywolf", 37: "Kanturu Ruins",
        38: "Kanturu Relics", 40: "Silent Map", 41: "Barracks", 42: "Refuge",
        51: "Elbeland", 56: "Calmness", 57: "Karutan 1", 58: "Karutan 2",
        63: "Vulcanus", 80: "Ferea", 81: "Nixies Lake", 91: "Deep Dungeon 1",
        92: "Deep Dungeon 2", 93: "Deep Dungeon 3", 94: "Deep Dungeon 4", 95: "Deep Dungeon 5",
        110: "Nars", 116: "Deep Dungeon", 122: "Swamp of Darkness", 128: "Kubera Mine",
        134: "Abyss of Atlans", 140: "Scorched Canyon", 145: "Red Smoke Icarus", 150: "Arenil Temple",
        155: "Ashen Aida", 160: "Old Kethotum", 165: "Blaze Kethotum"
    }
    candidates = [
        get_resource_path(os.path.join("config", "map_commands.json")),
        get_resource_path("map_commands.json")
    ]
    for candidate_path in candidates:
        if os.path.exists(candidate_path):
            try:
                with open(candidate_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("maps", []):
                        mid = item.get("map_id")
                        name = item.get("name")
                        if mid is not None and name:
                            mapping[mid] = name
                break
            except Exception:
                pass
    return mapping

MAP_NAMES = load_map_names()

# =========================================================================
# PHÂN LOẠI THỰC THỂ BẢN ĐỒ (NPC, BOSS, QUÁI TINH ANH, QUÁI THƯỜNG, SUMMON)
# =========================================================================

NPC_KEYWORDS = [
    "merchant", "assistant", "priest", "guardian", "spirit", "goblin", "soldier",
    "barmaid", "blacksmith", "warehouse", "vault", "master", "phantom", "trainer",
    "potion", "thủ kho", "gác cổng", "trưởng làng", "layla", "marlon", "charon",
    "sevrin", "titus", "lumen", "hanzo", "pasi", "lahap", "amy", "leo", "dercon",
    "david", "moss", "angel", "craftsman", "storage", "guard", "npc", "helper",
    "quest", "event", "safe", "nurse"
]

BOSS_KEYWORDS = [
    "boss", "lord", "kundun", "gorgon", "hell maine", "balgass", "nightmare",
    "medusa", "erohim", "selupan", "death king", "red dragon", "kundum", "ferea",
    "nix", "great heavenly", "god of darkness", "core magriffy", "lord silvester",
    "zaikan", "phượng hoàng lửa", "golden dragon", "golden titan", "golden lizard",
    "golden tantallos", "chúa tể"
]

def classify_entity_type(name: str, level: int = 0, cls_id: int = 0, is_elite: bool = False,
                         summon_owner: str = "", is_scout: bool = False, is_sonar: bool = False) -> Tuple[str, str, bool, bool]:
    """
    Phân loại chính xác thực thể trong bản đồ:
    Returns: (category_name, sub_type, is_npc, is_boss)
    """
    nl = name.lower()

    # 1. Quái Triệu hồi của nhân vật khác
    if summon_owner:
        return f"🐾 Triệu Hồi ({summon_owner})", "summon", False, False

    # 2. NPC (Non-Player Character)
    is_npc_id = (200 <= cls_id <= 259) or (367 <= cls_id <= 415) or (450 <= cls_id <= 580) or (700 <= cls_id <= 799)
    has_npc_kw = any(kw in nl for kw in NPC_KEYWORDS)
    if is_npc_id or has_npc_kw:
        if any(w in nl for w in ["merchant", "potion", "barmaid", "blacksmith", "pasi", "amy", "lumen", "hanzo", "shop", "cửa hàng"]):
            return "🏪 NPC Cửa Hàng", "npc_shop", True, False
        elif any(w in nl for w in ["assistant", "priest", "marlon", "quest", "jerint", "james", "sevrin", "nhiệm vụ"]):
            return "📜 NPC Nhiệm Vụ", "npc_quest", True, False
        elif any(w in nl for w in ["guardian", "guard", "soldier", "gác cổng", "phantom", "bảo vệ"]):
            return "🛡️ NPC Bảo Vệ", "npc_guard", True, False
        elif any(w in nl for w in ["goblin", "trainer", "craftsman", "chaos"]):
            return "🔮 NPC Ép Đồ / Chaos", "npc_craft", True, False
        elif any(w in nl for w in ["warehouse", "vault", "thủ kho", "storage"]):
            return "📦 NPC Thủ Kho", "npc_vault", True, False
        elif any(w in nl for w in ["spirit", "angel", "archer", "event", "sự kiện"]):
            return "👼 NPC Sự Kiện", "npc_event", True, False
        return "🧙 NPC Bản Đồ", "npc_general", True, False

    # 3. Boss Thế Giới
    if any(b in nl for b in BOSS_KEYWORDS):
        return "👑 Boss Thế Giới", "boss", False, True

    # 4. Quái Tinh Anh
    if is_elite:
        return "🌟 Quái Tinh Anh", "elite", False, False

    # 5. Quái Ngoài Tầm (Thám thính / Scout Memory)
    if is_scout:
        return "📡 Quái Ngoài Tầm (Thám thính)", "scout", False, False

    # 6. Quái Ngoài Tầm (Sóng dò Slayer Sonar)
    if is_sonar:
        return "🦇 Quái Ngoài Tầm (Sóng dò)", "sonar", False, False

    # 7. Quái Thường
    return "👾 Quái Thường", "normal", False, False

# =========================================================================
# BÃI QUÁI & ĐIỂM MỐC MẶC ĐỊNH TRÊN CÁC BẢN ĐỒ (MAP SPOTS CATALOG)
# Cho phép nhân vật (kể cả ELF / DK / DW) nhận biết trước các bãi quái ngoài tầm mắt
# =========================================================================
MAP_SPOTS = {
    0: [  # Lorencia
        {"name": "Bãi Nhện (Spider)", "x": 10, "y": 30, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Rồng Con (Budge Dragon)", "x": 185, "y": 128, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Bò Rừng (Bull Fighter)", "x": 15, "y": 145, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Khổng Lồ (Giant)", "x": 235, "y": 235, "tier": "free", "req": "Tự do"},
        {"name": "Cổng Bắc Lorencia", "x": 121, "y": 232, "tier": "free", "req": "Tự do"},
        {"name": "Cổng Đông Lorencia", "x": 216, "y": 248, "tier": "free", "req": "Tự do"},
    ],
    1: [  # Dungeon (Dungeon 1, 2, 3)
        {"name": "Bãi Hell Spider (D3)", "x": 36, "y": 58, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Blade Hunter (D3)", "x": 28, "y": 65, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Ghost (D3)", "x": 38, "y": 71, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Ma Nữ Cung (D3)", "x": 20, "y": 85, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Gorgon Boss (D3)", "x": 10, "y": 10, "tier": "vip", "req": "Boss / VIP"},
        {"name": "Bãi Poison Bull (D2)", "x": 235, "y": 125, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Dark Knight (D1)", "x": 108, "y": 114, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Skeleton (D1)", "x": 177, "y": 126, "tier": "free", "req": "Tự do"},
    ],
    2: [  # Devias
        {"name": "Bãi Sâu Băng (Worm)", "x": 225, "y": 225, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Quái Băng (Ice Monster)", "x": 190, "y": 30, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Người Tuyết (Yeti)", "x": 60, "y": 160, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Yeti Tinh Anh (Elite Yeti)", "x": 20, "y": 20, "tier": "free", "req": "Tự do"},
    ],
    3: [  # Noria
        {"name": "Bãi Yêu Tinh (Goblin)", "x": 150, "y": 10, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Bọ Cánh Cứng (Beetle)", "x": 190, "y": 80, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Thợ Săn (Hunter)", "x": 20, "y": 150, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Ma Cây (Forest Monster)", "x": 100, "y": 200, "tier": "free", "req": "Tự do"},
    ],
    4: [  # Lost Tower
        {"name": "Bãi Bóng Ma (Shadow - LT1)", "x": 208, "y": 78, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Độc Dược (Poison Shadow - LT3)", "x": 86, "y": 166, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Phù Thủy (Cursed Wizard - LT5)", "x": 120, "y": 90, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Ma Vương Balrog (LT7)", "x": 10, "y": 10, "tier": "vip", "req": "Boss / VIP"},
    ],
    7: [  # Atlans
        {"name": "Bãi Cá Mập (Bahamut)", "x": 24, "y": 19, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Thủy Quái (Vepar)", "x": 220, "y": 50, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Rồng Băng (Silver Valkyrie)", "x": 160, "y": 180, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Đại Xà Hydra Boss", "x": 15, "y": 225, "tier": "vip", "req": "Boss / VIP"},
    ],
    8: [  # Tarkan
        {"name": "Bãi Đột Biến (Mutant)", "x": 250, "y": 35, "tier": "free", "req": "Tự do"},
        {"name": "Bãi Sói Đỏ (Bloody Wolf)", "x": 180, "y": 110, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Bánh Xe Sắt (Iron Wheel)", "x": 130, "y": 200, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Sa Mạc Zaikan Boss", "x": 60, "y": 140, "tier": "megavip", "req": "Boss / MEGAVIP"},
    ],
    10: [  # Icarus
        {"name": "Bãi Alquamos", "x": 15, "y": 40, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Mega Crust", "x": 40, "y": 70, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Queen Ranier", "x": 60, "y": 100, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Drakan & Phoenix", "x": 100, "y": 130, "tier": "megavip", "req": "MEGAVIP khuyên dùng"},
    ],
    33: [  # Aida
        {"name": "Bãi Người Đá (Blue Golem)", "x": 80, "y": 12, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Nữ Hoàng Rừng (Witch Queen)", "x": 120, "y": 100, "tier": "vip", "req": "VIP khuyên dùng"},
        {"name": "Bãi Chúa Ngục Hell Maine", "x": 180, "y": 60, "tier": "megavip", "req": "Boss / MEGAVIP"},
    ],
    40: [  # Silent Map
        {"name": "Khu Trung Tâm An Toàn", "x": 230, "y": 25, "tier": "free", "req": "An toàn"},
        {"name": "Bãi Quái Bắc Silent", "x": 200, "y": 60, "tier": "megavip", "req": "MEGAVIP khuyên dùng"},
        {"name": "Bãi Quái Tây Silent", "x": 160, "y": 110, "tier": "megavip", "req": "MEGAVIP khuyên dùng"},
        {"name": "Bãi Quái Nam Silent", "x": 230, "y": 150, "tier": "megavip", "req": "MEGAVIP khuyên dùng"},
    ],
    80: [  # Ferea
        {"name": "Bãi Ferea Cửa Vào", "x": 80, "y": 120, "tier": "megavip", "req": "MEGAVIP cao cấp"},
        {"name": "Bãi Quái Tinh Anh Ferea", "x": 120, "y": 80, "tier": "megavip", "req": "MEGAVIP cao cấp"},
        {"name": "Bãi Chúa Tể Lord Ferea", "x": 60, "y": 60, "tier": "megavip", "req": "Boss / MEGAVIP"},
    ]
}


# =========================================================================
# BỘ ĐỌC BỘ NHỚ ZERO-INJECTION QUA READPROCESSMEMORY
# =========================================================================

def load_game_type_info_offset() -> int:
    try:
        offsets_path = get_resource_path("megamu_offsets.json")
        if os.path.exists(offsets_path):
            with open(offsets_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                val = d.get("game_type_info")
                if val:
                    return int(val, 16) if isinstance(val, str) else int(val)
    except Exception:
        pass
    return 0x553B900

GAME_TYPE_INFO_RVA = load_game_type_info_offset()

class MemoryScanner:
    def __init__(self, pid: int):
        self.pid = pid
        self.k32 = ctypes.windll.kernel32
        self.hProc = None
        self.base_addr = 0
        # Bộ nhớ thám thính thực thể (Persistent Scout Memory)
        # Giúp ghi nhớ quái vật & vật phẩm khi nhân vật (kể cả ELF / DK / DW) di chuyển xa
        self.scout_cache = {
            "monsters": {},      # (x, y, name) -> {"data": m, "time": float}
            "ground_items": {},  # (x, y, name) -> {"data": it, "time": float}
            "map_id": -1
        }
        self._last_relay_check = 0.0
        self._cached_relay_info = None
        self._cached_relay_pid = 0
        self._open_process()

    def clear_scout_cache(self):
        """Xóa trắng bộ nhớ thám thính khi người dùng muốn reset radar."""
        self.scout_cache = {
            "monsters": {},
            "ground_items": {},
            "map_id": -1
        }

    def _open_process(self) -> bool:
        try:
            # PROCESS_ALL_ACCESS (0x1F0FFF) hoặc PROCESS_VM_READ | PROCESS_QUERY_INFORMATION (0x0410)
            self.hProc = self.k32.OpenProcess(0x1F0FFF, False, self.pid)
            if not self.hProc:
                self.hProc = self.k32.OpenProcess(0x0410, False, self.pid)
            if not self.hProc:
                return False
            self.base_addr = self._get_module_base("gameassembly.dll")
            return bool(self.base_addr)
        except Exception:
            return False

    def read_gremory_case_items(self) -> List[Dict[str, Any]]:
        """Đọc danh sách vật phẩm quà tặng hiện có trong Hộp Quà Gremory Case (phím K) trực tiếp từ RAM."""
        items = []
        if not self.hProc or not self.base_addr:
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

    def _get_module_base(self, target_module: str) -> int:
        try:
            import win32process
            for hMod in win32process.EnumProcessModules(self.hProc):
                name = win32process.GetModuleFileNameEx(self.hProc, hMod)
                if target_module.lower() in name.lower():
                    return hMod
        except Exception:
            pass

        # Toolhelp32 snapshot fallback (chuẩn Windows x64)
        try:
            k32 = ctypes.windll.kernel32
            TH32CS_SNAPMODULE = 0x00000008
            TH32CS_SNAPMODULE32 = 0x00000010
            hSnap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid)
            if hSnap != -1:
                class MODULEENTRY32(ctypes.Structure):
                    _fields_ = [
                        ("dwSize", ctypes.c_ulong),
                        ("th32ModuleID", ctypes.c_ulong),
                        ("th32ProcessID", ctypes.c_ulong),
                        ("GlblcntUsage", ctypes.c_ulong),
                        ("ProccntUsage", ctypes.c_ulong),
                        ("modBaseAddr", ctypes.c_size_t),
                        ("modBaseSize", ctypes.c_ulong),
                        ("hModule", ctypes.c_size_t),
                        ("szModule", ctypes.c_char * 256),
                        ("szExePath", ctypes.c_char * 260)
                    ]
                me = MODULEENTRY32()
                me.dwSize = ctypes.sizeof(MODULEENTRY32)
                if k32.Module32First(hSnap, ctypes.byref(me)):
                    while True:
                        mod_name = me.szModule.decode('utf-8', errors='ignore')
                        if target_module.lower() in mod_name.lower():
                            k32.CloseHandle(hSnap)
                            return me.modBaseAddr
                        if not k32.Module32Next(hSnap, ctypes.byref(me)):
                            break
                k32.CloseHandle(hSnap)
        except Exception:
            pass
        return 0

    def close(self):
        if self.hProc:
            try:
                self.k32.CloseHandle(self.hProc)
            except Exception:
                pass
            self.hProc = None

    def read_ptr(self, addr: int) -> int:
        if not self.hProc or not addr: return 0
        buf = ctypes.c_ulonglong()
        res = self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 8, None)
        return buf.value if res else 0

    def read_i32(self, addr: int) -> int:
        if not self.hProc or not addr: return 0
        buf = ctypes.c_int32()
        res = self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None)
        return buf.value if res else 0

    def read_u8(self, addr: int) -> int:
        if not self.hProc or not addr: return 0
        buf = ctypes.c_uint8()
        res = self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 1, None)
        return buf.value if res else 0

    def read_str(self, addr: int) -> str:
        """Đọc chuỗi C# Il2CppString (length ở +0x10, ký tự Unicode UTF-16 ở +0x14)."""
        if not self.hProc or not addr: return ""
        try:
            l = self.read_i32(addr + 0x10)
            if 0 < l < 128:
                buf = ctypes.create_unicode_buffer(l)
                res = self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr + 0x14), ctypes.byref(buf), l * 2, None)
                if res:
                    return buf.value
        except Exception:
            pass
        return ""

    def read_cstr(self, addr: int) -> str:
        """Đọc chuỗi C-style string ASCII / UTF-8."""
        if not self.hProc or not addr: return ""
        try:
            buf = ctypes.create_string_buffer(64)
            res = self.k32.ReadProcessMemory(self.hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 64, None)
            if res:
                return buf.value.decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def get_slayer_detection_info(self, player_ptr: int) -> Dict[str, Any]:
        """Kiểm tra xem nhân vật (đặc biệt là Slayer) có trang bị skill Sóng Dò Detection không."""
        res = {"has_skill": False, "slot": 0, "name": ""}
        if not player_ptr or not self.hProc:
            return res
        try:
            u_skill = self.read_ptr(player_ptr + 0x190)
            if not u_skill:
                return res
            hotkeys = self.read_ptr(u_skill + 0x20)
            if hotkeys:
                alen = self.read_i32(hotkeys + 0x18)
                for i in range(min(alen, 10)):
                    sk_info = self.read_ptr(hotkeys + 0x20 + i * 8)
                    if sk_info:
                        sk_name = self.read_str(self.read_ptr(sk_info + 0x18))
                        if any(w in sk_name.lower() for w in ["detection", "sonar", "dò tìm", "định vị"]):
                            res["has_skill"] = True
                            res["slot"] = i
                            res["name"] = sk_name
                            return res
        except Exception:
            pass
        return res

    def find_slayer_relay(self, current_map_id: int) -> Optional[Dict[str, Any]]:
        """
        Dò tìm các client Slayer khác đang chạy cùng máy để 'tiếp sóng' Sóng Dò Detection.
        Cực kỳ hữu ích khi đang chơi ELF / DK / DW / Summoner không có skill Slayer Detection.
        Được tối ưu hóa bộ nhớ đệm (Cache 2.5s) để loại bỏ 100% tình trạng giật lag CPU do quét tiến trình.
        """
        now = time.time()
        # Nếu chưa quá 2.5s kể từ lần quét trước, tái sử dụng kết quả cache
        if now - self._last_relay_check < 2.5:
            if self._cached_relay_info:
                # Cập nhật xem có cùng map hay không
                self._cached_relay_info["same_map"] = (self._cached_relay_info.get("map_id") == current_map_id)
                return self._cached_relay_info
            return None

        self._last_relay_check = now

        try:
            # Nếu đã có Slayer relay PID từ trước, kiểm tra trực tiếp tiến trình đó trước
            target_pids = []
            if self._cached_relay_pid and psutil.pid_exists(self._cached_relay_pid):
                target_pids.append(self._cached_relay_pid)

            if not target_pids:
                for p in psutil.process_iter(['pid', 'name']):
                    p_pid = p.info['pid']
                    if p_pid == self.pid:
                        continue
                    p_name = (p.info.get('name') or '').lower()
                    if p_name in ('megamu.exe', 'megamu') or ('megamu' in p_name and 'dashboard' not in p_name and 'bot' not in p_name):
                        target_pids.append(p_pid)

            for p_pid in target_pids:
                if p_pid == self.pid:
                    continue
                scanner = MemoryScanner(p_pid)
                if not scanner.base_addr:
                    scanner.close()
                    continue
                try:
                    t_info = scanner.read_ptr(scanner.base_addr + GAME_TYPE_INFO_RVA)
                    if not t_info:
                        scanner.close()
                        continue
                    s_fields = scanner.read_ptr(t_info + 0xB8)
                    g_inst = scanner.read_ptr(s_fields + 0x8)
                    if not g_inst:
                        scanner.close()
                        continue

                    other_player = scanner.read_ptr(g_inst + 0x208)
                    if not other_player:
                        scanner.close()
                        continue
                    other_cls = scanner.read_i32(other_player + 0x34)
                    other_name = scanner.read_str(scanner.read_ptr(other_player + 0x28))

                    other_world = scanner.read_ptr(g_inst + 0x200)
                    other_map = scanner.read_i32(other_world + 0x20) if other_world else -1

                    other_mm = scanner.read_ptr(g_inst + 0x210)
                    is_active = bool(scanner.read_u8(other_mm + 0x28)) if other_mm else False
                    pin_list = scanner.read_ptr(other_mm + 0x20) if other_mm else 0

                    relayed_mons = []
                    relayed_pls = []
                    if pin_list:
                        cnt = scanner.read_i32(pin_list + 0x18)
                        items_ptr = scanner.read_ptr(pin_list + 0x10)
                        if items_ptr and cnt > 0:
                            for i in range(min(cnt, 200)):
                                p_obj = scanner.read_ptr(items_ptr + 0x20 + i * 8)
                                if not p_obj: continue
                                ptype = scanner.read_i32(p_obj + 0x10)
                                pin_x = scanner.read_i32(p_obj + 0x14)
                                pin_y = scanner.read_i32(p_obj + 0x18)
                                pin_t = scanner.read_str(scanner.read_ptr(p_obj + 0x20))
                                if ptype == 8:
                                    relayed_mons.append({"name": pin_t or "Quái ngoài tầm", "x": pin_x, "y": pin_y})
                                elif ptype == 7:
                                    relayed_pls.append({"name": pin_t or "Người chơi ngoài tầm", "x": pin_x, "y": pin_y})

                    scanner.close()

                    # Nếu đây là Slayer hoặc có pin phát hiện
                    if other_cls in (9, 144) or is_active or relayed_mons:
                        res = {
                            "pid": p_pid,
                            "name": other_name,
                            "class": CLASS_NAMES.get(other_cls, f"Class {other_cls}"),
                            "map_id": other_map,
                            "same_map": (other_map == current_map_id),
                            "active": is_active,
                            "monsters": relayed_mons,
                            "players": relayed_pls
                        }
                        self._cached_relay_info = res
                        self._cached_relay_pid = p_pid
                        return res
                except Exception:
                    scanner.close()
        except Exception:
            pass

        self._cached_relay_info = None
        self._cached_relay_pid = 0
        return None

    def scan_radar(self, radius: float = 15.0) -> Dict[str, Any]:
        """
        Quét toàn bộ thế giới xung quanh nhân vật (Chuẩn Slayer Detection & Ground Items):
        - Tọa độ người chơi & Bản đồ hiện tại
        - Danh sách quái vật trong và ngoài tầm mắt (Viewport 3D + Sóng Dò Minimap)
        - Danh sách người chơi xung quanh (Viewport + Sóng Dò Minimap)
        - Danh sách vật phẩm rơi trên mặt đất (Ngọc, Đồ Exl, Đồ Thần, Zen...)
        - Trạng thái kỹ năng Slayer Detection (Sóng siêu âm định vị)
        - Cổng di chuyển & Điểm mốc bản đồ
        """
        if not self.hProc or not self.base_addr:
            return {"error": "Không kết nối được vào tiến trình"}

        try:
            # 1. Truy cập Game.Instance qua type_info
            type_info = self.read_ptr(self.base_addr + GAME_TYPE_INFO_RVA)
            if not type_info: return {"error": "Không đọc được Game.TypeInfo"}
            static_fields = self.read_ptr(type_info + 0xB8)
            if not static_fields: return {"error": "Không đọc được Game.StaticFields"}
            game_inst = self.read_ptr(static_fields + 0x8)
            if not game_inst: return {"error": "Game.Instance chưa khởi tạo (chưa vào game?)"}

            # 2. Đọc Bản đồ hiện tại (World tại game_inst + 0x200)
            world = self.read_ptr(game_inst + 0x200)
            map_id = self.read_i32(world + 0x20) if world else -1
            map_name = MAP_NAMES.get(map_id, f"Map {map_id}")

            # Đồng bộ Map ID cho bộ nhớ thám thính (nếu đổi map thì reset bộ nhớ)
            if map_id != self.scout_cache.get("map_id"):
                self.scout_cache["monsters"].clear()
                self.scout_cache["ground_items"].clear()
                self.scout_cache["map_id"] = map_id

            # 3. Đọc Thông tin bản thân (Player tại game_inst + 0x208)
            player = self.read_ptr(game_inst + 0x208)
            if not player:
                return {"error": "Chưa chọn nhân vật hoặc đang tải màn hình"}

            p_name = self.read_str(self.read_ptr(player + 0x28))
            p_lvl = self.read_i32(player + 0x30)
            p_cls = self.read_i32(player + 0x34)
            p_coord = self.read_ptr(player + 0x68)
            px = self.read_i32(p_coord + 0x10) if p_coord else -1
            py = self.read_i32(p_coord + 0x14) if p_coord else -1

            # Đọc Cấp tài khoản AccountLevel (LocalCharacterBody + 0x304)
            # 0 = Free/Normal, 1 = VIP, 2 = MEGAVIP
            p_acc_lvl = self.read_i32(player + 0x304)
            is_vip = (p_acc_lvl >= 1)
            is_megavip = (p_acc_lvl >= 2)
            if is_megavip:
                vip_tag = "👑 MEGAVIP"
                vip_desc = "Tài khoản MEGAVIP (Tự động cộng điểm, ra bãi VIP/MEGAVIP & Reset tự do)"
            elif is_vip:
                vip_tag = "⭐ VIP"
                vip_desc = "Tài khoản VIP Thường (Ưu đãi EXP, ra mọi bãi quái)"
            else:
                vip_tag = "Free"
                vip_desc = "Tài khoản Miễn phí (Vẫn ra mọi bãi cắm train bình thường, reset qua bot/thủ công)"

            # 4. Kiểm tra kỹ năng Slayer Detection & Sóng Dò MinimapManager (game_inst + 0x210)
            sk_info = self.get_slayer_detection_info(player)
            minimap_mgr = self.read_ptr(game_inst + 0x210)
            skill_detection_state = False
            sonar_monsters = []
            sonar_players = []
            gates = []
            relay_info = None

            if minimap_mgr:
                skill_detection_state = bool(self.read_u8(minimap_mgr + 0x28))
                pin_list = self.read_ptr(minimap_mgr + 0x20)
                if pin_list:
                    pin_count = self.read_i32(pin_list + 0x18)
                    pin_items = self.read_ptr(pin_list + 0x10)
                    if pin_items and pin_count > 0:
                        for i in range(min(pin_count, 300)):
                            pin_obj = self.read_ptr(pin_items + 0x20 + i * 8)
                            if not pin_obj:
                                continue
                            ptype = self.read_i32(pin_obj + 0x10)
                            pin_x = self.read_i32(pin_obj + 0x14)
                            pin_y = self.read_i32(pin_obj + 0x18)
                            pin_text = self.read_str(self.read_ptr(pin_obj + 0x20))
                            dist = round(math.sqrt((pin_x - px) ** 2 + (pin_y - py) ** 2), 1)

                            if dist > radius:
                                continue

                            # 8 = DetectionMonster (Phát hiện quái ngoài tầm mắt qua sóng Slayer)
                            if ptype == 8:
                                cat, stype, is_npc, is_boss = classify_entity_type(pin_text or "Quái ngoài tầm", 0, 0, False, is_sonar=True)
                                sonar_monsters.append({
                                    "name": pin_text or "Quái ngoài tầm mắt",
                                    "level": 0,
                                    "class_id": 0,
                                    "x": pin_x,
                                    "y": pin_y,
                                    "distance": dist,
                                    "category": cat,
                                    "sub_type": stype,
                                    "is_npc": is_npc,
                                    "is_boss": is_boss,
                                    "is_elite": False,
                                    "is_sonar": True,
                                    "is_scout": False,
                                    "source": "slayer_sonar"
                                })
                            # 7 = DetectionPlayer (Phát hiện người chơi ngoài tầm mắt qua sóng Slayer)
                            elif ptype == 7:
                                sonar_players.append({
                                    "name": pin_text or "Người chơi ngoài tầm mắt",
                                    "level": 0,
                                    "class": "Unknown",
                                    "x": pin_x,
                                    "y": pin_y,
                                    "distance": dist,
                                    "pk_level": 3,
                                    "is_pk": False,
                                    "is_gm": False,
                                    "store_name": "",
                                    "guild_name": "",
                                    "union_name": "",
                                    "guild_role": "",
                                    "guild_rel": 0,
                                    "gens": 0,
                                    "is_sonar": True,
                                    "source": "slayer_sonar"
                                })
                            # 0 = Gate (Cổng dịch chuyển / Cổng Map)
                            elif ptype == 0:
                                gates.append({
                                    "name": pin_text or "Cổng map",
                                    "x": pin_x,
                                    "y": pin_y,
                                    "distance": dist
                                })

            # Nếu nhân vật KHÔNG PHẢI Slayer (như ELF / DK / DW):
            # Tự động dò tìm các client Slayer chạy cùng máy để 'mượn' tiếp sóng Sóng Dò toàn map!
            if not sk_info.get("has_skill"):
                relay_info = self.find_slayer_relay(map_id)
                if relay_info and relay_info.get("monsters"):
                    for rm in relay_info["monsters"]:
                        rdist = round(math.sqrt((rm["x"] - px) ** 2 + (rm["y"] - py) ** 2), 1)
                        if rdist <= radius:
                            cat, stype, is_npc, is_boss = classify_entity_type(rm["name"], 0, 0, False, is_sonar=True)
                            sonar_monsters.append({
                                "name": rm["name"],
                                "level": 0,
                                "class_id": 0,
                                "x": rm["x"],
                                "y": rm["y"],
                                "distance": rdist,
                                "category": cat,
                                "sub_type": stype,
                                "is_npc": is_npc,
                                "is_boss": is_boss,
                                "is_elite": False,
                                "is_sonar": True,
                                "is_scout": False,
                                "source": f"relay_{relay_info['name']}"
                            })
                    for rp in relay_info.get("players", []):
                        rdist = round(math.sqrt((rp["x"] - px) ** 2 + (rp["y"] - py) ** 2), 1)
                        if rdist <= radius:
                            sonar_players.append({
                                "name": rp["name"],
                                "level": 0,
                                "class": "Unknown",
                                "x": rp["x"],
                                "y": rp["y"],
                                "distance": rdist,
                                "pk_level": 3,
                                "is_pk": False,
                                "is_gm": False,
                                "store_name": "",
                                "guild_name": "",
                                "union_name": "",
                                "guild_role": "",
                                "guild_rel": 0,
                                "gens": 0,
                                "is_sonar": True,
                                "source": f"relay_{relay_info['name']}"
                            })

            # 5. Quét Viewport (game_inst + 0x110)
            viewport = self.read_ptr(game_inst + 0x110)
            if not viewport: return {"error": "Không tìm thấy Viewport"}

            obj_dict = self.read_ptr(viewport + 0x20)
            if not obj_dict: return {"error": "Không đọc được ObjectList"}

            entries = self.read_ptr(obj_dict + 0x18)
            count = self.read_i32(obj_dict + 0x20)
            if count <= 0:
                count = 0

            monsters = []
            players = []
            npcs = []
            ground_items = []
            total_scanned = 0
            now = time.time()

            for i in range(min(count, 500)):
                entry_addr = entries + 0x20 + i * 24
                val = self.read_ptr(entry_addr + 16)
                if not val: continue

                # Kiểm tra loại đối tượng qua VTable name
                val_klass = self.read_ptr(val)
                val_klass_name = self.read_cstr(self.read_ptr(val_klass + 0x10))

                # A. Xử lý THỰC THỂ SỐNG (ViewportBody)
                if "ViewportBody" in val_klass_name:
                    body = self.read_ptr(val + 0x18)
                    if not body: continue

                    total_scanned += 1
                    b_klass = self.read_ptr(body)
                    b_klass_name = self.read_cstr(self.read_ptr(b_klass + 0x10))

                    # Bỏ qua chính bản thân mình
                    if "LocalCharacterBody" in b_klass_name:
                        continue

                    # Đọc tọa độ thực thể
                    c_ptr = self.read_ptr(body + 0x68)
                    bx = self.read_i32(c_ptr + 0x10) if c_ptr else -1
                    by = self.read_i32(c_ptr + 0x14) if c_ptr else -1
                    if bx < 0 or by < 0:
                        continue

                    dist = round(math.sqrt((bx - px) ** 2 + (by - py) ** 2), 1)
                    b_name = self.read_str(self.read_ptr(body + 0x28)) or "Unknown"
                    b_lvl = self.read_i32(body + 0x30)
                    b_cls_id = self.read_i32(body + 0x34)
                    b_cls_name = CLASS_NAMES.get(b_cls_id, f"Class {b_cls_id}")

                    # Ghi nhận vào bộ nhớ thám thính (Scout Cache) để giữ lại khi đi xa ngoài tầm mắt!
                    if "MonsterBody" in b_klass_name:
                        is_elite = bool(self.read_u8(body + 0x148))
                        summon_owner = self.read_str(self.read_ptr(body + 0xA0))
                        category, sub_type, is_npc, is_boss = classify_entity_type(
                            b_name, b_lvl, b_cls_id, is_elite, summon_owner
                        )

                        self.scout_cache["monsters"][(bx, by, b_name)] = {
                            "name": b_name,
                            "level": b_lvl,
                            "class_id": b_cls_id,
                            "is_elite": is_elite,
                            "is_npc": is_npc,
                            "is_boss": is_boss,
                            "category": category,
                            "sub_type": sub_type,
                            "time": now
                        }

                        if dist <= radius:
                            monsters.append({
                                "name": b_name,
                                "level": b_lvl,
                                "class_id": b_cls_id,
                                "x": bx, "y": by,
                                "distance": dist,
                                "is_elite": is_elite,
                                "is_npc": is_npc,
                                "is_boss": is_boss,
                                "category": category,
                                "sub_type": sub_type,
                                "is_sonar": False,
                                "is_scout": False,
                                "source": "viewport"
                            })
                            if is_npc:
                                npcs.append({
                                    "name": b_name,
                                    "class_id": b_cls_id,
                                    "category": category,
                                    "x": bx, "y": by,
                                    "distance": dist
                                })
                    elif "CharacterBody" in b_klass_name:
                        ctl_code = self.read_i32(body + 0x150)
                        pk_level = self.read_i32(body + 0x154)
                        is_gm = (ctl_code == 32)
                        is_pk = (pk_level >= 4)
                        has_store = bool(self.read_u8(body + 0x95))
                        store_name = self.read_str(self.read_ptr(body + 0x98)) if has_store else ""

                        # Đọc thông tin Bang hội (Guild) & Gia tộc (Gens)
                        guild_num = self.read_i32(body + 0x15C)
                        guild_status_val = self.read_i32(body + 0x160)
                        guild_rel_val = self.read_i32(body + 0x168)
                        guild_info_ptr = self.read_ptr(body + 0x170)
                        guild_name = self.read_str(self.read_ptr(guild_info_ptr + 0x20)) if guild_info_ptr else ""
                        union_name = self.read_str(self.read_ptr(guild_info_ptr + 0x28)) if guild_info_ptr else ""
                        gens_family = self.read_i32(body + 0x178)

                        guild_role = ""
                        if guild_num > 0:
                            if guild_status_val == 128:
                                guild_role = "Chủ Bang"
                            elif guild_status_val == 64:
                                guild_role = "Phó Bang"
                            elif guild_status_val == 32:
                                guild_role = "Battle Master"
                            else:
                                guild_role = "Thành viên"

                        if dist <= radius:
                            players.append({
                                "name": b_name,
                                "level": b_lvl,
                                "class": b_cls_name,
                                "x": bx, "y": by,
                                "distance": dist,
                                "pk_level": pk_level,
                                "is_pk": is_pk,
                                "is_gm": is_gm,
                                "store_name": store_name,
                                "guild_num": guild_num,
                                "guild_name": guild_name,
                                "union_name": union_name,
                                "guild_role": guild_role,
                                "guild_rel": guild_rel_val,
                                "gens": gens_family,
                                "is_sonar": False,
                                "source": "viewport"
                            })
                    elif "NpcBody" in b_klass_name:
                        category, sub_type, is_npc, is_boss = classify_entity_type(b_name, 0, b_cls_id, False)
                        npc_obj = {
                            "name": b_name,
                            "level": 0,
                            "class_id": b_cls_id,
                            "x": bx, "y": by,
                            "distance": dist,
                            "is_elite": False,
                            "is_npc": True,
                            "is_boss": False,
                            "category": category if is_npc else "🧙 NPC Bản Đồ",
                            "sub_type": "npc_general",
                            "is_sonar": False,
                            "is_scout": False,
                            "source": "viewport"
                        }
                        if dist <= radius:
                            npcs.append(npc_obj)
                            monsters.append(npc_obj)

                # B. Xử lý VẬT PHẨM RƠI TRÊN ĐẤT (ViewportItem)
                elif "ViewportItem" in val_klass_name:
                    c_ptr = self.read_ptr(val + 0x28)
                    ix = self.read_i32(c_ptr + 0x10) if c_ptr else -1
                    iy = self.read_i32(c_ptr + 0x14) if c_ptr else -1
                    if ix < 0 or iy < 0:
                        continue

                    dist = round(math.sqrt((ix - px) ** 2 + (iy - py) ** 2), 1)
                    total_scanned += 1
                    item_obj = self.read_ptr(val + 0x18)
                    item_idx = self.read_i32(item_obj + 0x60) if item_obj else 0
                    if item_idx <= 0 and item_obj:
                        item_idx = self.read_i32(item_obj + 0x10)
                    lvl = self.read_i32(item_obj + 0x10) if item_obj else 0
                    exc = self.read_i32(item_obj + 0x20) if item_obj else 0
                    anc = self.read_i32(item_obj + 0x24) if item_obj else 0

                    it_name = ""
                    te = self.read_ptr(item_obj + 0x58) if item_obj else 0
                    if te:
                        for off in [0x18, 0x20, 0x28, 0x30, 0x38]:
                            s_p = self.read_ptr(te + off)
                            it_name = self.read_str(s_p)
                            if it_name:
                                break

                    if not it_name:
                        if item_idx == 7181: it_name = "Zen"
                        elif item_idx == 7182: it_name = "Jewel of Chaos"
                        elif item_idx == 7183: it_name = "Jewel of Bless"
                        elif item_idx == 7184: it_name = "Jewel of Soul"
                        elif item_idx == 7185: it_name = "Jewel of Life"
                        elif item_idx == 7186: it_name = "Jewel of Creation"
                        elif item_idx == 7206: it_name = "Jewel of Harmony"
                        else: it_name = f"Vật phẩm #{item_idx}" if item_idx > 0 else "Vật phẩm"

                    nl = it_name.lower()
                    is_jewel = any(j in nl for j in ["bless", "soul", "chaos", "life", "creation", "harmony", "guardian", "gemstone", "jewel", "ngọc", "talisman", "feather", "flame", "chao"])
                    is_zen = ("zen" in nl or "money" in nl or item_idx == 7181)
                    cat = "Ngọc quý" if is_jewel else ("Đồ Thần" if anc else ("Đồ Exl" if exc else ("Zen" if is_zen else "Trang bị/Khác")))

                    # Ghi nhận vào bộ nhớ vật phẩm
                    self.scout_cache["ground_items"][(ix, iy, it_name)] = {
                        "name": it_name,
                        "category": cat,
                        "level": lvl,
                        "is_exc": bool(exc),
                        "is_anc": bool(anc),
                        "is_jewel": is_jewel,
                        "is_zen": is_zen,
                        "time": now
                    }

                    if dist <= radius:
                        ground_items.append({
                            "name": it_name,
                            "category": cat,
                            "level": lvl,
                            "x": ix, "y": iy,
                            "distance": dist,
                            "is_exc": bool(exc),
                            "is_anc": bool(anc),
                            "is_jewel": is_jewel,
                            "is_zen": is_zen
                        })

            # 6. TÍCH HỢP BỘ NHỚ THÁM THÍNH (GHI NHỚ THỰC THỂ ĐÃ PHÁT HIỆN NGOÀI TẦM MẮT 3D)
            # Giúp ELF / DK / DW dù đi ra xa vẫn nhìn thấy quái và vật phẩm ở bãi cũ!
            existing_mon_coords = {(m["x"], m["y"]) for m in monsters}
            for (cx, cy, cname), cinfo in list(self.scout_cache["monsters"].items()):
                if (cx, cy) not in existing_mon_coords:
                    cdist = round(math.sqrt((cx - px) ** 2 + (cy - py) ** 2), 1)
                    if cdist <= radius:
                        # Chỉ lấy những mục tiêu hiện tại đã lọt ra ngoài tầm mắt 3D (> 13.5 ô)
                        if cdist > 13.5:
                            is_npc = cinfo.get("is_npc", False)
                            is_boss = cinfo.get("is_boss", False)
                            base_cat = cinfo.get("category", "👾 Quái Thường")
                            if is_npc:
                                cat = f"📡 {base_cat} (Ngoài tầm)"
                            elif is_boss:
                                cat = "👑 Boss Ngoài Tầm (Thám thính)"
                            else:
                                cat = "📡 Quái Ngoài Tầm (Thám thính)"

                            monsters.append({
                                "name": cname,
                                "level": cinfo.get("level", 0),
                                "class_id": cinfo.get("class_id", 0),
                                "x": cx,
                                "y": cy,
                                "distance": cdist,
                                "is_elite": cinfo.get("is_elite", False),
                                "is_npc": is_npc,
                                "is_boss": is_boss,
                                "category": cat,
                                "sub_type": cinfo.get("sub_type", "scout"),
                                "is_sonar": True,
                                "is_scout": True,
                                "source": "scout_memory"
                            })
                            existing_mon_coords.add((cx, cy))

            # Bộ nhớ vật phẩm rơi ngoài tầm mắt
            existing_it_coords = {(it["x"], it["y"], it["name"]) for it in ground_items}
            for (cix, ciy, ciname), citem in list(self.scout_cache["ground_items"].items()):
                if (cix, ciy, ciname) not in existing_it_coords:
                    cidist = round(math.sqrt((cix - px) ** 2 + (ciy - py) ** 2), 1)
                    if cidist <= radius and cidist > 13.5:
                        ground_items.append({
                            "name": ciname,
                            "category": citem.get("category", "Vật phẩm"),
                            "level": citem.get("level", 0),
                            "x": cix, "y": ciy,
                            "distance": cidist,
                            "is_exc": citem.get("is_exc", False),
                            "is_anc": citem.get("is_anc", False),
                            "is_jewel": citem.get("is_jewel", False),
                            "is_zen": citem.get("is_zen", False),
                            "is_scout": True
                        })
                        existing_it_coords.add((cix, ciy, ciname))

            # 7. Hợp nhất quái vật & người chơi từ Sóng Dò Slayer Sonar (hoặc tiếp sóng Relay)
            for sm in sonar_monsters:
                if (sm["x"], sm["y"]) not in existing_mon_coords:
                    monsters.append(sm)
                    existing_mon_coords.add((sm["x"], sm["y"]))

            existing_pl_coords = {(p["x"], p["y"]) for p in players}
            for sp in sonar_players:
                if (sp["x"], sp["y"]) not in existing_pl_coords:
                    players.append(sp)
                    existing_pl_coords.add((sp["x"], sp["y"]))

            # 8. Nạp các BÃI QUÁI MẶC ĐỊNH CỦA BẢN ĐỒ (MAP SPOTS)
            # Luôn nạp toàn bộ bãi quái trong map để nhân vật ở bất kỳ đâu (kể cả trong thành) đều thấy và bấm ra bãi được!
            map_spots = []
            for spot in MAP_SPOTS.get(map_id, []):
                sp_dist = round(math.sqrt((spot["x"] - px) ** 2 + (spot["y"] - py) ** 2), 1)
                spot_tier = spot.get("tier", "free")
                req_desc = spot.get("req", "Tự do")

                # Mọi tài khoản (kể cả Free/Normal) đều có thể ra bãi cắm train bình thường 100%!
                can_farm = True
                if spot_tier == "megavip":
                    tier_label = "👑 MEGAVIP"
                    if is_megavip:
                        status_note = "✅ Đủ điều kiện (Auto cộng điểm tại bãi)"
                    else:
                        status_note = "✅ Ra bãi được (Cộng điểm tay / Bot)"
                elif spot_tier == "vip":
                    tier_label = "⭐ VIP"
                    if is_vip:
                        status_note = "✅ Đủ điều kiện (Ưu đãi EXP VIP)"
                    else:
                        status_note = "✅ Ra bãi được (EXP Thường)"
                else:
                    tier_label = "🆓 Miễn Phí"
                    status_note = "✅ Bãi tự do (Mọi tài khoản)"

                map_spots.append({
                    "name": spot["name"],
                    "x": spot["x"],
                    "y": spot["y"],
                    "distance": sp_dist,
                    "tier": spot_tier,
                    "tier_label": tier_label,
                    "req": req_desc,
                    "can_farm": can_farm,
                    "status_note": status_note,
                    "in_radar": (sp_dist <= radius)
                })

            # Sắp xếp từ gần tới xa
            monsters.sort(key=lambda x: x["distance"])
            players.sort(key=lambda x: x["distance"])
            ground_items.sort(key=lambda x: x["distance"])
            npcs.sort(key=lambda x: x["distance"])
            gates.sort(key=lambda x: x["distance"])
            map_spots.sort(key=lambda x: x["distance"])

            # Thống kê Slayer Sonar & Scout
            is_relay = (relay_info is not None and len(sonar_monsters) > 0)
            scout_count = len([m for m in monsters if m.get("is_scout")])

            return {
                "player": {
                    "name": p_name,
                    "level": p_lvl,
                    "class": CLASS_NAMES.get(p_cls, f"Class {p_cls}"),
                    "x": px, "y": py,
                    "account_level": p_acc_lvl,
                    "is_vip": is_vip,
                    "is_megavip": is_megavip,
                    "vip_tag": vip_tag,
                    "vip_desc": vip_desc
                },
                "map": {
                    "id": map_id,
                    "name": map_name
                },
                "radius": radius,
                "total_scanned": total_scanned,
                "slayer_sonar": {
                    "active": skill_detection_state or (relay_info.get("active") if relay_info else False),
                    "has_skill": sk_info["has_skill"],
                    "slot": sk_info["slot"],
                    "skill_name": sk_info["name"],
                    "sonar_monsters": len(sonar_monsters),
                    "sonar_players": len(sonar_players),
                    "is_relay": is_relay,
                    "relay_name": relay_info.get("name", "") if relay_info else "",
                    "relay_pid": relay_info.get("pid", 0) if relay_info else 0,
                    "scout_count": scout_count,
                    "scout_total": len(self.scout_cache["monsters"])
                },
                "monsters": monsters,
                "players": players,
                "npcs": npcs,
                "ground_items": ground_items,
                "gates": gates,
                "map_spots": map_spots
            }

        except Exception as e:
            return {"error": f"Lỗi quét RAM: {e}"}


# =========================================================================
# GIAO DIỆN TERMINAL DASHBOARD
# =========================================================================

def print_dashboard(data: Dict[str, Any]):
    """Vẽ giao diện Radar trực quan trên màn hình Console."""
    if "error" in data:
        print(f"{Fore.RED}[RADAR ERROR] {data['error']}{Style.RESET_ALL}")
        return

    # Xóa màn hình hoặc in header mới
    p = data["player"]
    m = data["map"]
    radius = data["radius"]
    monsters = data["monsters"]
    players = data["players"]
    npcs = data["npcs"]

    # Đếm nhóm quái vật
    monster_summary: Dict[str, int] = {}
    for mon in monsters:
        monster_summary[mon["name"]] = monster_summary.get(mon["name"], 0) + 1

    now_str = datetime.now().strftime("%H:%M:%S")

    # In khung thông tin
    vip_tag = p.get("vip_tag", "Free")
    print("\n" + "=" * 80)
    print(f"{Fore.GREEN}{Style.BRIGHT}🎯 MEGAMU RADAR & ENTITY SCANNER {Style.RESET_ALL} | "
          f"{Fore.YELLOW}{Style.BRIGHT}{p['name']} ({p['class']} Lv {p['level']}) [{vip_tag}]{Style.RESET_ALL} | "
          f"{Fore.CYAN}Map: {m['name']} (ID {m['id']}){Style.RESET_ALL} | "
          f"{Fore.WHITE}Tọa độ: ({p['x']}, {p['y']}){Style.RESET_ALL}")
    print("=" * 80)
    print(f"⏱ Cập nhật lúc: {now_str}  |  📏 Bán kính quét: {Fore.YELLOW}{radius} ô{Style.RESET_ALL}  |  "
          f"👁 Tổng thực thể trong tầm nhìn: {data['total_scanned']}")
    print("-" * 80)

    # 1. Quái vật
    mon_color = Fore.LIGHTYELLOW_EX if monsters else Fore.WHITE
    print(f"{mon_color}{Style.BRIGHT}👾 QUÁI VẬT TRONG BÁN KÍNH ({len(monsters)} con):{Style.RESET_ALL}")
    if not monsters:
        print(f"   {Fore.WHITE}{Style.DIM}(Không có quái vật nào trong phạm vi {radius} ô){Style.RESET_ALL}")
    else:
        for idx, mon in enumerate(monsters[:15]):  # hiển thị tối đa 15 con
            elite_tag = f" {Fore.RED}[TINH ANH]{Style.RESET_ALL}" if mon["is_elite"] else ""
            print(f"   [{idx + 1:2d}] {Fore.YELLOW}{mon['name']:<24}{Style.RESET_ALL} | "
                  f"Lv {mon['level']:<3d} | "
                  f"Tọa độ: ({mon['x']:3d}, {mon['y']:3d}) | "
                  f"Cách bạn: {Fore.LIGHTCYAN_EX}{mon['distance']:4.1f} ô{Style.RESET_ALL}{elite_tag}")
        if len(monsters) > 15:
            print(f"   ... và còn {len(monsters) - 15} quái vật khác gần đó.")

    print("-" * 80)

    # 2. Người chơi
    pl_color = Fore.LIGHTCYAN_EX if players else Fore.WHITE
    print(f"{pl_color}{Style.BRIGHT}👤 NGƯỜI CHƠI XUNG QUANH ({len(players)} người):{Style.RESET_ALL}")
    if not players:
        print(f"   {Fore.WHITE}{Style.DIM}(Khu vực vắng người - không có người chơi nào trong phạm vi {radius} ô){Style.RESET_ALL}")
    else:
        for idx, pl in enumerate(players):
            pk_text, pk_col = PK_LEVEL_MAP.get(pl["pk_level"], ("Bình thường", Fore.GREEN))
            alert_prefix = ""
            if pl["is_pk"]:
                alert_prefix = f"{Back.RED}{Fore.WHITE}[⚠️ SÁT THỦ PK]{Style.RESET_ALL} "
            elif pl["is_gm"]:
                alert_prefix = f"{Back.YELLOW}{Fore.BLACK}[🚨 ADMIN/GM]{Style.RESET_ALL} "

            store_info = f" {Fore.MAGENTA}[Shop: {pl['store_name']}]{Style.RESET_ALL}" if pl["store_name"] else ""
            guild_info = ""
            if pl.get("guild_name"):
                role_tag = f" ({pl['guild_role']})" if pl.get("guild_role") else ""
                guild_info = f" | {Fore.YELLOW}G: {pl['guild_name']}{role_tag}{Style.RESET_ALL}"

            print(f"   [{idx + 1:2d}] {alert_prefix}{Fore.CYAN}{pl['name']:<16}{Style.RESET_ALL} | "
                  f"{pl['class']:<15} Lv {pl['level']:<3d} | "
                  f"({pl['x']:3d}, {pl['y']:3d}) | "
                  f"Cách: {Fore.LIGHTCYAN_EX}{pl['distance']:4.1f} ô{Style.RESET_ALL}{guild_info} | "
                  f"{pk_col}{pk_text}{Style.RESET_ALL}{store_info}")

    # 3. NPC nếu có
    if npcs:
        print("-" * 80)
        print(f"{Fore.LIGHTGREEN_EX}{Style.BRIGHT}🏛️ NPC XUNG QUANH ({len(npcs)} NPC):{Style.RESET_ALL}")
        for idx, npc in enumerate(npcs):
            print(f"   [{idx + 1:2d}] {Fore.GREEN}{npc['name']:<20}{Style.RESET_ALL} | "
                  f"Tọa độ: ({npc['x']:3d}, {npc['y']:3d}) | "
                  f"Cách bạn: {npc['distance']:4.1f} ô")

    # 4. Thống kê tổng quan
    print("-" * 80)
    summary_str = ", ".join([f"{k}: {v}" for k, v in monster_summary.items()]) if monster_summary else "Trống"
    pk_count = sum(1 for p in players if p["is_pk"])
    gm_count = sum(1 for p in players if p["is_gm"])

    pk_alert = f"{Fore.RED}⚠️ {pk_count} SÁT THỦ!{Style.RESET_ALL}" if pk_count else f"{Fore.GREEN}0{Style.RESET_ALL}"
    gm_alert = f"{Fore.YELLOW}🚨 {gm_count} ADMIN!{Style.RESET_ALL}" if gm_count else f"{Fore.GREEN}0{Style.RESET_ALL}"

    print(f"📊 {Fore.WHITE}{Style.BRIGHT}TỔNG HỢP NHANH TRONG BÁN KÍNH {radius} Ô:{Style.RESET_ALL}")
    print(f"   • Quái vật: {Fore.YELLOW}{len(monsters)} con{Style.RESET_ALL} ({summary_str})")
    print(f"   • Người chơi: {Fore.CYAN}{len(players)} người{Style.RESET_ALL} | Cảnh báo Quỷ đỏ: {pk_alert} | Cảnh báo Admin: {gm_alert}")
    print("=" * 80)
    print(f"{Fore.BLACK}{Style.BRIGHT}Nhấn Ctrl + C để dừng chương trình.{Style.RESET_ALL}")


def find_megamu_clients() -> List[Dict[str, Any]]:
    """Tìm tất cả các client MEGAMU đang chạy kèm thông tin tên nhân vật."""
    clients = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = (p.info.get('name') or '').lower()
            if name in ('megamu.exe', 'megamu') or ('megamu' in name and 'dashboard' not in name and 'bot' not in name):
                pid = p.info['pid']
                scanner = MemoryScanner(pid)
                char_info = "Đang kết nối..."
                if scanner.base_addr:
                    data = scanner.scan_radar(radius=1.0)
                    if "player" in data and data["player"].get("name"):
                        pl = data["player"]
                        vip_str = f" [{pl.get('vip_tag', 'Free')}]" if pl.get("vip_tag") else ""
                        char_info = f"{pl['name']} ({pl['class']} Lv {pl['level']}){vip_str} - Map: {data['map']['name']}"
                scanner.close()
                clients.append({"pid": pid, "info": char_info})
        except Exception:
            pass
    return clients


def main():
    print(f"\n{Fore.GREEN}{Style.BRIGHT}======================================================{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}🛰️  CÔNG CỤ QUÉT RADAR THỰC THỂ MEGAMU (ZERO-INJECTION){Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}======================================================{Style.RESET_ALL}")

    clients = find_megamu_clients()
    if not clients:
        print(f"{Fore.RED}[THÔNG BÁO] Không tìm thấy game MEGAMU.exe nào đang chạy!{Style.RESET_ALL}")
        print("Vui lòng mở game và đăng nhập nhân vật trước khi chạy tool.")
        return

    selected_pid = clients[0]["pid"]
    if len(clients) > 1:
        print(f"\n{Fore.CYAN}Tìm thấy {len(clients)} cửa sổ MEGAMU đang mở:{Style.RESET_ALL}")
        for idx, c in enumerate(clients):
            print(f"  [{idx + 1}] PID: {c['pid']} | Nhân vật: {c['info']}")
        try:
            ans = input(f"\nChọn số thứ tự client cần quét (Mặc định 1): ").strip()
            if ans and ans.isdigit():
                choice = int(ans) - 1
                if 0 <= choice < len(clients):
                    selected_pid = clients[choice]["pid"]
        except Exception:
            pass

    # Nhập bán kính quét
    scan_radius = 12.0
    try:
        r_input = input(f"\nNhập bán kính quét (số ô, mặc định 12): ").strip()
        if r_input:
            val = float(r_input)
            if val > 0:
                scan_radius = val
    except Exception:
        pass

    scanner = MemoryScanner(selected_pid)
    if not scanner.base_addr:
        print(f"{Fore.RED}[LỖI] Không thể kết nối bộ nhớ PID {selected_pid}!{Style.RESET_ALL}")
        return

    print(f"\n{Fore.GREEN}✔ Đã kết nối thành công tới Client PID {selected_pid}! Đang bắt đầu quét radar...{Style.RESET_ALL}")
    time.sleep(1)

    try:
        while True:
            # Xóa màn hình terminal để vẽ lại mượt mà
            os.system("cls" if os.name == "nt" else "clear")
            data = scanner.scan_radar(radius=scan_radius)
            print_dashboard(data)
            time.sleep(1.2)  # Quét và cập nhật mỗi 1.2 giây
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Đã dừng Radar Scanner an toàn.{Style.RESET_ALL}")
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
