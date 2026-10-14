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
    candidate_path = os.path.join(os.path.dirname(__file__), "config", "map_commands.json")
    if os.path.exists(candidate_path):
        try:
            with open(candidate_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("maps", []):
                    mid = item.get("map_id")
                    name = item.get("name")
                    if mid is not None and name:
                        mapping[mid] = name
        except Exception:
            pass
    return mapping

MAP_NAMES = load_map_names()


# =========================================================================
# BỘ ĐỌC BỘ NHỚ ZERO-INJECTION QUA READPROCESSMEMORY
# =========================================================================

class MemoryScanner:
    def __init__(self, pid: int):
        self.pid = pid
        self.k32 = ctypes.windll.kernel32
        self.hProc = None
        self.base_addr = 0
        self._open_process()

    def _open_process(self) -> bool:
        try:
            self.hProc = self.k32.OpenProcess(0x0410, False, self.pid)  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
            if not self.hProc:
                return False
            self.base_addr = self._get_module_base("gameassembly.dll")
            return self.base_addr != 0
        except Exception:
            return False

    def _get_module_base(self, target_module: str) -> int:
        try:
            import win32process
            for hMod in win32process.EnumProcessModules(self.hProc):
                name = win32process.GetModuleFileNameEx(self.hProc, hMod)
                if target_module.lower() in name.lower():
                    return hMod
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

    def scan_radar(self, radius: float = 12.0) -> Dict[str, Any]:
        """
        Quét toàn bộ thế giới xung quanh nhân vật:
        - Tọa độ người chơi
        - Bản đồ hiện tại
        - Danh sách quái vật trong bán kính `radius`
        - Danh sách người chơi trong bán kính `radius`
        - Danh sách NPC trong bán kính `radius`
        """
        if not self.hProc or not self.base_addr:
            return {"error": "Không kết nối được vào tiến trình"}

        try:
            # 1. Truy cập Game.Instance qua type_info
            type_info = self.read_ptr(self.base_addr + 0x54A9808)
            if not type_info: return {"error": "Không đọc được Game.TypeInfo"}
            static_fields = self.read_ptr(type_info + 0xB8)
            if not static_fields: return {"error": "Không đọc được Game.StaticFields"}
            game_inst = self.read_ptr(static_fields + 0x8)
            if not game_inst: return {"error": "Game.Instance chưa khởi tạo (chưa vào game?)"}

            # 2. Đọc Bản đồ hiện tại (World tại game_inst + 0x200)
            world = self.read_ptr(game_inst + 0x200)
            map_id = self.read_i32(world + 0x20) if world else -1
            map_name = MAP_NAMES.get(map_id, f"Map {map_id}")

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

            # 4. Quét Viewport (game_inst + 0x110)
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
            total_scanned = 0

            for i in range(min(count, 400)):
                entry_addr = entries + 0x20 + i * 24
                val = self.read_ptr(entry_addr + 16)
                if not val: continue

                # Kiểm tra loại đối tượng qua VTable name
                val_klass = self.read_ptr(val)
                val_klass_name = self.read_cstr(self.read_ptr(val_klass + 0x10))

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

                    # Tính khoảng cách hình học (Distance)
                    dist = round(math.sqrt((bx - px) ** 2 + (by - py) ** 2), 1)

                    # Lọc theo bán kính người dùng chọn
                    if dist > radius:
                        continue

                    b_name = self.read_str(self.read_ptr(body + 0x28)) or "Unknown"
                    b_lvl = self.read_i32(body + 0x30)
                    b_cls_id = self.read_i32(body + 0x34)
                    b_cls_name = CLASS_NAMES.get(b_cls_id, f"Class {b_cls_id}")

                    # Phân loại thực thể
                    if "MonsterBody" in b_klass_name:
                        is_elite = bool(self.read_u8(body + 0x148))
                        monsters.append({
                            "name": b_name,
                            "level": b_lvl,
                            "x": bx, "y": by,
                            "distance": dist,
                            "is_elite": is_elite
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
                            "gens": gens_family
                        })
                    elif "NpcBody" in b_klass_name:
                        npcs.append({
                            "name": b_name,
                            "x": bx, "y": by,
                            "distance": dist
                        })

            # Sắp xếp từ gần tới xa
            monsters.sort(key=lambda x: x["distance"])
            players.sort(key=lambda x: x["distance"])
            npcs.sort(key=lambda x: x["distance"])

            return {
                "player": {
                    "name": p_name,
                    "level": p_lvl,
                    "class": CLASS_NAMES.get(p_cls, f"Class {p_cls}"),
                    "x": px, "y": py
                },
                "map": {
                    "id": map_id,
                    "name": map_name
                },
                "radius": radius,
                "total_scanned": total_scanned,
                "monsters": monsters,
                "players": players,
                "npcs": npcs
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
    print("\n" + "=" * 80)
    print(f"{Fore.GREEN}{Style.BRIGHT}🎯 MEGAMU RADAR & ENTITY SCANNER {Style.RESET_ALL} | "
          f"{Fore.YELLOW}{Style.BRIGHT}{p['name']} ({p['class']} Lv {p['level']}){Style.RESET_ALL} | "
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
            if name in ('megamu.exe', 'megamu'):
                pid = p.info['pid']
                scanner = MemoryScanner(pid)
                char_info = "Đang kết nối..."
                if scanner.base_addr:
                    data = scanner.scan_radar(radius=1.0)
                    if "player" in data and data["player"].get("name"):
                        pl = data["player"]
                        char_info = f"{pl['name']} ({pl['class']} Lv {pl['level']}) - Map: {data['map']['name']}"
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
