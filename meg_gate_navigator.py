#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Gate REA Navigator Module (meg_gate_navigator.py)
========================================================
Module chuyên biệt xử lý di chuyển & vào các Map GATE (Alkmar/Alka, Ubaid/Ubail,
Debenter/Deventer, Uruk Mountain, Nars và mọi cổng Gate trong TableWorld.Gate)
bằng cơ chế Reverse Engineering Analysis (REA) trực tiếp trên Unity MainThread:

  1. Đọc bảng TableWorld.Gate (NHCCIOLHKFP) & TableWorld.Move (BBJHCKHMLKF)
     trực tiếp từ RAM client (Data.Instance + 0x90 -> +0x30 / +0x28) và lưu cache.
  2. Xây dựng đồ thị cổng GateGraph (BFS shortest-path) giữa các Map / Gate.
  3. Thực thi vào cổng qua Mega.Unit.HJDEPLPHNBO (gửi gói C1:1C trực tiếp trên
     Unity MainThread, bỏ qua popup "Do you want to teleport?").
  4. Hỗ trợ 3 chế độ an toàn:
       - "direct": Gọi C1:1C trực tiếp không cần đi bộ.
       - "walk":   Chạy tới tâm vùng cổng (X..TX, Y..TY) rồi gọi C1:1C.
       - "auto":   Thử direct C1:1C trước (hoặc walk ngay nếu đang đứng cùng map
                   có cổng vật lý), tự fallback sang walk -> C1:1C nếu server
                   kiểm tra khoảng cách đứng gần cổng.
  5. Hỗ trợ vào Acheron qua NPC Sir Lesnar (C1:F8:30 / C1:F8:34) hoặc lệnh /move.

ZERO-OFFSET-ON-DISK: Module này KHÔNG hardcode bất kỳ địa chỉ RVA nào. Toàn bộ
RVA được nạp động qua MegDirectEngine từ License Vault / config/megamu_offsets.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Chuẩn hóa tên & Alias cho cụm Map GATE (Acheron / Elemental + các map khác)
# ---------------------------------------------------------------------------

CANONICAL_MAP_ALIASES: Dict[str, str] = {
    # Acheron Safe Zone
    "acheron": "acheron",
    "acheron town": "acheron",
    "acheron safe": "acheron",
    # Alkmar (Alka)
    "alka": "alkmar",
    "alkmar": "alkmar",
    "alcmar": "alkmar",
    "alcmaru": "alkmar",
    # Ubaid (Ubail)
    "ubail": "ubaid",
    "ubaid": "ubaid",
    # Debenter (Deventer)
    "deventer": "debenter",
    "debenter": "debenter",
    # Uruk Mountain
    "uruk": "uruk",
    "uruk mountain": "uruk",
    "urukmountain": "uruk",
    # Nars
    "nars": "nars",
    # Các map lân cận thường đi kèm
    "ferea": "ferea",
    "nixies": "nixies",
    "nixies lake": "nixies",
}

# Ánh xạ tên map chuẩn -> Map ID trên MEGAMU
CANONICAL_MAP_IDS: Dict[str, int] = {
    "acheron": 91,
    "alkmar": 91,
    "ubaid": 91,
    "debenter": 95,
    "uruk": 100,
    "nars": 110,
    "ferea": 112,
    "nixies": 113,
}

# Gate ID nổi tiếng đã xác nhận từ REA trực tiếp trên MegaMU live RAM (TableWorld.Gate)
# Ánh xạ tên map chuẩn -> (portal_gate_id, target_gate_id, move_cmd)
KNOWN_FALLBACK_GATES: Dict[str, int] = {
    "alkmar": 418,
    "ubaid": 422,
    "debenter": 435,
    "uruk": 450,
    "nars": 487,
    "nixies": 523,
}

KNOWN_MOVE_COMMANDS: Dict[str, str] = {
    "acheron": "Acheron",
    "alkmar": "alcmaru",
    "ubaid": "ubaid",
    "debenter": "debenter",
    "uruk": "uruk",
    "nars": "nars",
    "nixies": "nixies",
    "ferea": "Ferea",
}

# Map ID -> Tên hiển thị chuẩn
MAP_ID_NAMES: Dict[int, str] = {
    0: "Lorencia",
    1: "Dungeon",
    2: "Devias",
    3: "Noria",
    4: "Lost Tower",
    7: "Atlans",
    8: "Tarkan",
    10: "Icarus",
    33: "Aida",
    34: "Crywolf",
    37: "Kanturu Ruins",
    38: "Kanturu Relics",
    41: "Barracks of Balgass",
    42: "Balgass Refuge",
    51: "Elbeland",
    56: "Swamp of Calmness",
    57: "Raklion",
    63: "Vulcanus",
    79: "Loren Market",
    80: "Karutan 1",
    81: "Karutan 2",
    91: "Acheron (Alkmar/Ubaid)",
    92: "Acheron (Alt)",
    95: "Debenter",
    96: "Debenter (Alt)",
    100: "Uruk Mountain",
    101: "Uruk Mountain (Alt)",
    110: "Nars",
    112: "Ferea",
    113: "Nixies Lake",
}

DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "world_gates_cache.json"
)


def normalize_map_name(name: str) -> str:
    """Chuẩn hóa tên map / alias (vd: 'Ubail' -> 'ubaid', 'Alka' -> 'alkmar', 'Deventer' -> 'debenter')."""
    s = " ".join(str(name or "").strip().lower().split())
    return CANONICAL_MAP_ALIASES.get(s, s)


def is_in_acheron_safe_zone(map_id: int, x: int, y: int) -> bool:
    """
    Kiểm tra nhân vật có đang đứng ở đảo Safe Zone Acheron (Map 91) chưa qua cổng hay không.
    Trên MegaMU (xác thực từ TableWorld.Gate):
      - Town spawn #417 (51..60, 190..197) và toàn bộ 5 cổng vào Alkmar/Ubaid/Debenter/Uruk/Nars
        đều nằm gọn trong khung x in [18..104], y in [154..228] trên Map 91.
      - Bên trong Alkmar (#419: 112..114, 161..166) và Ubaid (#423: 151..156, 198..200) đều nằm ngoài khung này.
    """
    return int(map_id) == 91 and (18 <= int(x) <= 104) and (154 <= int(y) <= 228)


def is_inside_gate_destination(
    canonical: str,
    dest_map_id: int,
    portal_gate: Optional["GateEntry"],
    cur_map_id: int,
    px: int,
    py: int,
) -> bool:
    """
    Xác định chính xác nhân vật ĐÃ QUA CỔNG và đang đứng bên trong khu vực săn của map đích chưa.
    Xử lý chuẩn cả trường hợp phân khu cùng Map 91 (Acheron Safe Zone vs Alkmar vs Ubaid).
    """
    cur_map_id = int(cur_map_id)
    dest_map_id = int(dest_map_id)
    if cur_map_id < 0 or dest_map_id < 0 or cur_map_id != dest_map_id:
        return False

    # Nếu vẫn đang đứng đè trên ô Portal nguồn -> CHƯA qua cổng!
    if portal_gate is not None and portal_gate.map_id == cur_map_id and portal_gate.contains(px, py, pad=2):
        return False

    # Phân khu trên cùng Map 91 (Acheron Safe Zone vs Alkmar vs Ubaid) — LUÔN kiểm tra dù portal_gate có hay không!
    if dest_map_id == 91:
        norm = normalize_map_name(canonical)
        if norm == "acheron":
            return is_in_acheron_safe_zone(cur_map_id, px, py)
        if is_in_acheron_safe_zone(cur_map_id, px, py):
            return False
        if norm == "alkmar":
            return px < 145
        if norm == "ubaid":
            return px >= 145
        return True

    # Các map khác Map ID so với map cổng (Debenter=95, Uruk=100, Nars=110, Nixies=113):
    # Chỉ cần đúng Map ID (và không đứng đè trên portal nguồn) là chắc chắn đã xuyên qua cổng!
    return True


# ---------------------------------------------------------------------------
# Dataclasses khớp 100% cấu trúc NHCCIOLHKFP (GateInfo) & BBJHCKHMLKF (MoveInfo)
# ---------------------------------------------------------------------------

@dataclass
class GateEntry:
    index: int
    flag: int = 0
    map_id: int = -1
    x: int = 0
    y: int = 0
    tx: int = 0
    ty: int = 0
    target_gate: int = 0
    target_dir: int = 0
    min_level: int = 0
    max_level: int = 0
    min_reset: int = 0
    max_reset: int = 0
    account_level: int = 0

    @property
    def center(self) -> Tuple[int, int]:
        cx = (self.x + self.tx) // 2 if self.tx >= self.x else self.x
        cy = (self.y + self.ty) // 2 if self.ty >= self.y else self.y
        return (cx, cy)

    @property
    def is_portal(self) -> bool:
        """Cổng có thể đi qua (flag 1 = cổng nguồn hoặc flag 2 = cổng 2 chiều, có target_gate > 0)."""
        return self.target_gate > 0 and self.flag in (1, 2)

    def contains(self, px: int, py: int, pad: int = 0) -> bool:
        x1, x2 = min(self.x, self.tx) - pad, max(self.x, self.tx) + pad
        y1, y2 = min(self.y, self.ty) - pad, max(self.y, self.ty) + pad
        return x1 <= px <= x2 and y1 <= py <= y2

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "GateEntry":
        return cls(
            index=int(raw.get("index", 0)),
            flag=int(raw.get("flag", 0)),
            map_id=int(raw.get("mapId", raw.get("map_id", -1))),
            x=int(raw.get("x", 0)),
            y=int(raw.get("y", 0)),
            tx=int(raw.get("tx", 0)),
            ty=int(raw.get("ty", 0)),
            target_gate=int(raw.get("targetGate", raw.get("target_gate", 0))),
            target_dir=int(raw.get("targetDir", raw.get("target_dir", 0))),
            min_level=int(raw.get("minLevel", raw.get("min_level", 0))),
            max_level=int(raw.get("maxLevel", raw.get("max_level", 0))),
            min_reset=int(raw.get("minReset", raw.get("min_reset", 0))),
            max_reset=int(raw.get("maxReset", raw.get("max_reset", 0))),
            account_level=int(raw.get("accountLevel", raw.get("account_level", 0))),
        )


@dataclass
class MoveEntry:
    index: int
    name: str = ""
    command: str = ""
    money: int = 0
    min_level: int = 0
    max_level: int = 0
    account_level: int = 0
    monster_class: int = 0
    gate_id: int = 0

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "MoveEntry":
        return cls(
            index=int(raw.get("index", 0)),
            name=str(raw.get("name", "") or "").strip(),
            command=str(raw.get("command", "") or "").strip(),
            money=int(raw.get("money", 0)),
            min_level=int(raw.get("minLevel", raw.get("min_level", 0))),
            max_level=int(raw.get("maxLevel", raw.get("max_level", 0))),
            account_level=int(raw.get("accountLevel", raw.get("account_level", 0))),
            monster_class=int(raw.get("monsterClass", raw.get("monster_class", 0))),
            gate_id=int(raw.get("gateId", raw.get("gate_id", 0))),
        )


@dataclass
class GateHop:
    """Một bước nhảy cổng từ source_gate -> target_gate."""
    source_gate: GateEntry
    target_gate: GateEntry
    from_map: int
    to_map: int


@dataclass
class GateResult:
    ok: bool
    message: str = ""
    method: str = ""
    from_map: int = -1
    to_map: int = -1
    gate_id: int = -1
    hops_done: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# GateCatalog & GateGraph: Lưu trữ, tra cứu & tìm đường BFS giữa các Map GATE
# ---------------------------------------------------------------------------

class GateCatalog:
    """Quản lý toàn bộ Gate & Move đọc từ RAM game hoặc từ file cache JSON."""

    def __init__(self, cache_path: str = DEFAULT_CACHE_PATH):
        self.cache_path = cache_path
        self.gates_by_id: Dict[int, GateEntry] = {}
        self.gates_by_map: Dict[int, List[GateEntry]] = collections.defaultdict(list)
        self.moves: List[MoveEntry] = []
        self.moves_by_norm_name: Dict[str, MoveEntry] = {}
        self.updated_at: float = 0.0

    @property
    def is_loaded(self) -> bool:
        return len(self.gates_by_id) > 0

    def load_from_dump(self, dump_data: Dict[str, Any]) -> int:
        """Nạp dữ liệu từ kết quả engine.dump_world_gates()."""
        raw_gates = dump_data.get("gates", []) or []
        raw_moves = dump_data.get("moves", []) or []
        self.gates_by_id.clear()
        self.gates_by_map.clear()
        self.moves.clear()
        self.moves_by_norm_name.clear()

        for rg in raw_gates:
            g = rg if isinstance(rg, GateEntry) else GateEntry.from_raw(rg)
            self.gates_by_id[g.index] = g
            self.gates_by_map[g.map_id].append(g)

        for rm in raw_moves:
            m = rm if isinstance(rm, MoveEntry) else MoveEntry.from_raw(rm)
            self.moves.append(m)
            for key in (m.name, m.command):
                norm = normalize_map_name(key)
                if norm and norm not in self.moves_by_norm_name:
                    self.moves_by_norm_name[norm] = m

        self.updated_at = time.time()
        return len(self.gates_by_id)

    def save_cache(self, path: Optional[str] = None) -> str:
        target = path or self.cache_path
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        payload = {
            "updated_at": self.updated_at or time.time(),
            "gate_count": len(self.gates_by_id),
            "move_count": len(self.moves),
            "gates": [asdict(g) for g in sorted(self.gates_by_id.values(), key=lambda x: x.index)],
            "moves": [asdict(m) for m in sorted(self.moves, key=lambda x: x.index)],
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return target

    def load_cache(self, path: Optional[str] = None) -> int:
        target = path or self.cache_path
        if not target or not os.path.exists(target):
            return 0
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        cnt = self.load_from_dump(data)
        self.updated_at = float(data.get("updated_at", 0.0))
        return cnt

    def get_gate(self, gate_id: int) -> Optional[GateEntry]:
        return self.gates_by_id.get(int(gate_id))

    def get_portals_in_map(self, map_id: int) -> List[GateEntry]:
        return [g for g in self.gates_by_map.get(int(map_id), []) if g.is_portal]

    def find_overlapping_portal(self, ref_gate: GateEntry, pad: int = 3) -> Optional[GateEntry]:
        """
        Trên MegaMU, lệnh /move cho các map [Gate] (vd: /move ubaid -> Gate #804, /move alcmaru -> Gate #807)
        thả nhân vật ĐÚNG TỌA ĐỘ của một cổng Portal vật lý (flag 1/2, target_gate > 0).
        Hàm này tìm chính xác cổng Portal chồng lấn với ref_gate đó.
        """
        if ref_gate is None:
            return None
        if ref_gate.is_portal:
            return ref_gate
        rx1, rx2 = min(ref_gate.x, ref_gate.tx) - pad, max(ref_gate.x, ref_gate.tx) + pad
        ry1, ry2 = min(ref_gate.y, ref_gate.ty) - pad, max(ref_gate.y, ref_gate.ty) + pad
        best: Optional[GateEntry] = None
        best_dist = 999999.0
        rcx, rcy = ref_gate.center
        for cand in self.gates_by_map.get(ref_gate.map_id, []):
            if not cand.is_portal:
                continue
            cx1, cx2 = min(cand.x, cand.tx), max(cand.x, cand.tx)
            cy1, cy2 = min(cand.y, cand.ty), max(cand.y, cand.ty)
            if not (cx2 < rx1 or cx1 > rx2 or cy2 < ry1 or cy1 > ry2):
                ccx, ccy = cand.center
                d = math.hypot(ccx - rcx, ccy - rcy)
                if d < best_dist:
                    best_dist = d
                    best = cand
        return best

    def resolve_target(self, target: str | int) -> Dict[str, Any]:
        """
        Phân giải đích đến từ tên/alias ('ubail', 'alka', 'deventer', 'uruk', 'nars', 'nixies')
        hoặc Gate ID / Map ID số nguyên. Tự động nhận diện cấu trúc [Gate] chồng lấn của MegaMU.
        """
        if isinstance(target, int):
            g = self.get_gate(target)
            if g is not None:
                portal = self.find_overlapping_portal(g)
                tgt = self.get_gate(portal.target_gate) if (portal and portal.target_gate > 0) else None
                return {
                    "ok": True,
                    "kind": "gate",
                    "name": f"Gate {g.index}",
                    "gate_id": tgt.index if tgt else g.index,
                    "portal_gate_id": portal.index if portal else -1,
                    "map_id": tgt.map_id if tgt else g.map_id,
                    "move": None,
                }
            return {
                "ok": True,
                "kind": "map",
                "name": MAP_ID_NAMES.get(target, f"Map {target}"),
                "gate_id": -1,
                "portal_gate_id": -1,
                "map_id": target,
                "move": None,
            }

        raw_str = str(target or "").strip()
        if raw_str.isdigit():
            return self.resolve_target(int(raw_str))

        norm = normalize_map_name(raw_str)
        # 1. Tìm trực tiếp trong bảng Move từ RAM (chính xác nhất vì chứa đúng MoveGate & Command của server!)
        mv = self.moves_by_norm_name.get(norm)
        if mv is None:
            for k, cand in self.moves_by_norm_name.items():
                if norm and (norm in k or k in norm):
                    mv = cand
                    break

        if mv is not None:
            move_gate = self.get_gate(mv.gate_id)
            portal = self.find_overlapping_portal(move_gate) if move_gate else None
            tgt_gate = self.get_gate(portal.target_gate) if (portal and portal.target_gate > 0) else None
            final_gate = tgt_gate or move_gate
            final_map = final_gate.map_id if final_gate else CANONICAL_MAP_IDS.get(norm, -1)
            return {
                "ok": True,
                "kind": "move_gate",
                "name": mv.name or norm,
                "canonical": norm,
                "gate_id": final_gate.index if final_gate else mv.gate_id,
                "move_gate_id": mv.gate_id,
                "portal_gate_id": portal.index if portal else -1,
                "map_id": final_map,
                "move": mv,
            }

        # 2. Fallback theo danh mục chuẩn (khi chưa attach game / chưa dump RAM)
        if norm in CANONICAL_MAP_IDS or norm in KNOWN_FALLBACK_GATES:
            pgid = KNOWN_FALLBACK_GATES.get(norm, -1)
            p_obj = self.get_gate(pgid) if pgid > 0 else None
            tgt = self.get_gate(p_obj.target_gate) if (p_obj and p_obj.target_gate > 0) else None
            mid = tgt.map_id if tgt else CANONICAL_MAP_IDS.get(norm, -1)
            return {
                "ok": True,
                "kind": "canonical",
                "name": norm.title(),
                "canonical": norm,
                "gate_id": tgt.index if tgt else pgid,
                "portal_gate_id": pgid,
                "map_id": mid,
                "move": None,
            }

        return {"ok": False, "error": f"Không nhận diện được map/gate: '{target}'", "canonical": norm}

    def find_incoming_portals_to_gate(self, dest_gate_id: int) -> List[GateEntry]:
        """Tìm tất cả các cổng nguồn có target_gate == dest_gate_id."""
        return [
            g for g in self.gates_by_id.values()
            if g.is_portal and g.target_gate == int(dest_gate_id)
        ]

    def find_incoming_portals_to_map(self, dest_map_id: int) -> List[GateEntry]:
        """Tìm tất cả các cổng nguồn dẫn sang dest_map_id."""
        out: List[GateEntry] = []
        for g in self.gates_by_id.values():
            if not g.is_portal:
                continue
            tgt = self.get_gate(g.target_gate)
            if tgt is not None and tgt.map_id == int(dest_map_id):
                out.append(g)
        return out

    def find_gate_path(
        self,
        from_map_id: int,
        to_map_id: int,
        to_gate_id: int = -1,
        max_hops: int = 8,
    ) -> List[GateHop]:
        """
        BFS tìm chuỗi cổng GATE ngắn nhất từ from_map_id đến to_map_id (hoặc cụ thể tới to_gate_id).
        Hỗ trợ cả chuyển vùng trong cùng 1 map (vd: Acheron Safe Zone -> Alkmar / Ubaid đều là Map 91!).
        """
        from_map_id = int(from_map_id)
        to_map_id = int(to_map_id)
        to_gate_id = int(to_gate_id)

        # Trường hợp đặc biệt: chuyển sub-zone cùng map (vd: Map 91 Acheron -> Gate Alkmar/Ubaid)
        if to_gate_id > 0:
            direct_same_map = [
                g for g in self.get_portals_in_map(from_map_id)
                if g.target_gate == to_gate_id
            ]
            if direct_same_map:
                tgt = self.get_gate(to_gate_id)
                if tgt:
                    return [GateHop(direct_same_map[0], tgt, from_map_id, tgt.map_id)]

        if from_map_id == to_map_id and to_gate_id <= 0:
            return []

        # Xây adjacency list theo map_id
        adj: Dict[int, List[GateHop]] = collections.defaultdict(list)
        for g in self.gates_by_id.values():
            if not g.is_portal:
                continue
            tgt = self.get_gate(g.target_gate)
            if tgt is None:
                continue
            if tgt.map_id == g.map_id and (to_gate_id <= 0 or tgt.index != to_gate_id):
                # Bỏ qua cổng nội bộ nếu không phải cổng đích yêu cầu để tránh vòng lặp vô ích
                continue
            adj[g.map_id].append(GateHop(g, tgt, g.map_id, tgt.map_id))

        # BFS theo trạng thái (map_id, reached_gate_id)
        queue: collections.deque[Tuple[int, List[GateHop]]] = collections.deque()
        queue.append((from_map_id, []))
        visited_maps = {from_map_id}

        while queue:
            cur_map, path = queue.popleft()
            if len(path) >= max_hops:
                continue
            for hop in adj.get(cur_map, []):
                new_path = path + [hop]
                if to_gate_id > 0:
                    if hop.target_gate.index == to_gate_id:
                        return new_path
                elif hop.to_map == to_map_id:
                    return new_path

                if hop.to_map not in visited_maps:
                    visited_maps.add(hop.to_map)
                    queue.append((hop.to_map, new_path))

        # Nếu đích là to_gate_id nhưng cổng dẫn tới to_gate_id nằm trên map đích to_map_id:
        if to_gate_id > 0 and to_map_id >= 0 and from_map_id != to_map_id:
            # Tìm đường tới map chứa cổng vào to_gate_id
            incoming = self.find_incoming_portals_to_gate(to_gate_id)
            for portal in incoming:
                if portal.map_id == from_map_id:
                    tgt = self.get_gate(to_gate_id)
                    if tgt:
                        return [GateHop(portal, tgt, from_map_id, tgt.map_id)]
                prefix = self.find_gate_path(from_map_id, portal.map_id, to_gate_id=-1, max_hops=max_hops - 1)
                if prefix:
                    tgt = self.get_gate(to_gate_id)
                    if tgt:
                        return prefix + [GateHop(portal, tgt, portal.map_id, tgt.map_id)]

        return []

    def summarize_elemental_maps(self) -> Dict[str, Any]:
        """Tổng hợp nhanh thông tin Gate & Move cho cụm map Acheron / Elemental (kèm Portal chồng lấn)."""
        targets = ["acheron", "alkmar", "ubaid", "debenter", "uruk", "nars", "ferea", "nixies"]
        summary: Dict[str, Any] = {}
        for name in targets:
            res = self.resolve_target(name)
            gid = int(res.get("gate_id", -1))
            pgid = int(res.get("portal_gate_id", -1))
            mid = int(res.get("map_id", -1))
            dest_g = self.get_gate(gid) if gid > 0 else None
            portal_g = self.get_gate(pgid) if pgid > 0 else None
            tgt_g = self.get_gate(portal_g.target_gate) if (portal_g and portal_g.target_gate > 0) else dest_g
            portals_in = [portal_g] if portal_g else (
                self.find_incoming_portals_to_gate(gid) if gid > 0 else self.find_incoming_portals_to_map(mid)
            )
            mv = res.get("move")
            cmd_word = mv.command if (mv and mv.command) else KNOWN_MOVE_COMMANDS.get(name, name)
            summary[name] = {
                "map_id": mid,
                "dest_gate_id": gid,
                "portal_gate_id": pgid,
                "portal_gate": asdict(portal_g) if portal_g else None,
                "target_gate": asdict(tgt_g) if tgt_g else None,
                "dest_coords": asdict(dest_g) if dest_g else None,
                "move_cmd": f"/move {cmd_word}",
                "move_account_level": mv.account_level if mv else None,
                "move_min_level": mv.min_level if mv else None,
                "incoming_portals": [
                    {
                        "source_gate_id": p.index,
                        "from_map_id": p.map_id,
                        "from_map_name": MAP_ID_NAMES.get(p.map_id, f"Map {p.map_id}"),
                        "center": p.center,
                        "box": [p.x, p.y, p.tx, p.ty],
                        "target_gate_id": p.target_gate,
                        "min_level": p.min_level,
                        "account_level": p.account_level,
                    }
                    for p in portals_in if p is not None
                ],
            }
        return summary


# ---------------------------------------------------------------------------
# MegGateNavigator: Bộ điều khiển thực thi vào Map GATE bằng REA
# ---------------------------------------------------------------------------

class MegGateNavigator:
    """
    Điều khiển vào các Map GATE (Ubaid/Ubail, Alkmar/Alka, Debenter/Deventer,
    Uruk Mountain, Nars...) sử dụng MegDirectEngine + hàm gốc C1:1C (Unit.HJDEPLPHNBO).
    """

    def __init__(
        self,
        engine: Any,
        catalog: Optional[GateCatalog] = None,
        logger: Optional[Callable[[str, str], None]] = None,
    ):
        self.engine = engine
        self.catalog = catalog or GateCatalog()
        self._logger = logger

    def log(self, msg: str, level: str = "INFO") -> None:
        if self._logger:
            try:
                self._logger(msg, level)
                return
            except Exception:
                pass
        print(f"[GateNav][{level}] {msg}", flush=True)

    # --- Đọc trạng thái sống từ Engine ---

    def _get_player_state(self) -> Tuple[int, int, int]:
        """Trả về (map_id, x, y) hiện tại của nhân vật."""
        try:
            st = self.engine.get_player_state() or {}
            mid = int(st.get("map_id", st.get("mapId", -1)))
            px = int(st.get("x", -1))
            py = int(st.get("y", -1))
            return (mid, px, py)
        except Exception:
            return (-1, -1, -1)

    def refresh_catalog(self, save_cache: bool = True) -> Dict[str, Any]:
        """Đọc trực tiếp bảng TableWorld.Gate & TableWorld.Move từ RAM game."""
        data = self.engine.dump_world_gates()
        if not data or not data.get("ok"):
            err = (data or {}).get("error", "dump_failed")
            self.log(f"Không đọc được TableWorld.Gate từ RAM ({err}), thử nạp cache...", "WARN")
            cached = self.catalog.load_cache()
            return {"ok": cached > 0, "source": "cache" if cached > 0 else "none", "gate_count": cached, "error": err}

        cnt = self.catalog.load_from_dump(data)
        self.log(
            f"Đã đọc trực tiếp từ RAM: {cnt} Gates, {len(self.catalog.moves)} Moves "
            f"(Map hiện tại: {data.get('currentMapId')}, pos=({data.get('currentX')},{data.get('currentY')}))",
            "INFO",
        )
        if save_cache and cnt > 0:
            try:
                saved = self.catalog.save_cache()
                self.log(f"Đã lưu cache Gate tại: {saved}", "INFO")
            except Exception as e:
                self.log(f"Không lưu được cache Gate: {e}", "WARN")
        return {"ok": True, "source": "ram", "gate_count": cnt, "move_count": len(self.catalog.moves)}

    def ensure_catalog(self) -> bool:
        if self.catalog.is_loaded:
            return True
        if self.engine is not None and getattr(self.engine, "is_ready", True):
            res = self.refresh_catalog(save_cache=True)
            if res.get("ok"):
                return True
        return self.catalog.load_cache() > 0

    def inspect_current_tile_gate(self) -> Dict[str, Any]:
        """Kiểm tra ngay ô nhân vật đang đứng có phải là Gate không."""
        return self.engine.get_current_tile_gate()

    # --- Thực thi di chuyển tới tọa độ cổng ---

    def _walk_to_coord(
        self,
        tx: int,
        ty: int,
        tolerance: float = 2.0,
        timeout: float = 25.0,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        """Di chuyển nhân vật tới tọa độ (tx, ty) bằng native move_to của engine."""
        deadline = time.time() + max(2.0, float(timeout))
        last_issue = 0.0
        while time.time() < deadline:
            if stop_event and stop_event.is_set():
                return False
            _, px, py = self._get_player_state()
            if px >= 0 and py >= 0:
                dist = math.hypot(tx - px, ty - py)
                if dist <= tolerance:
                    return True
            now = time.time()
            if now - last_issue >= 1.2:
                try:
                    self.engine.move_to(int(tx), int(ty))
                except Exception as e:
                    self.log(f"Lỗi gọi move_to({tx}, {ty}): {e}", "WARN")
                last_issue = now
            time.sleep(0.25)
        _, px, py = self._get_player_state()
        return px >= 0 and py >= 0 and math.hypot(tx - px, ty - py) <= (tolerance + 1.5)

    def _wait_for_gate_transition(
        self,
        prev_map: int,
        prev_x: int,
        prev_y: int,
        expected_map: int = -1,
        timeout: float = 4.5,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, int, int, int]:
        """Chờ xác nhận server đã dịch chuyển nhân vật sau khi gửi C1:1C."""
        deadline = time.time() + max(0.8, float(timeout))
        while time.time() < deadline:
            if stop_event and stop_event.is_set():
                return (False, prev_map, prev_x, prev_y)
            cur_map, cur_x, cur_y = self._get_player_state()
            if expected_map >= 0 and cur_map == expected_map and (cur_map != prev_map or math.hypot(cur_x - prev_x, cur_y - prev_y) >= 8.0):
                return (True, cur_map, cur_x, cur_y)
            if cur_map >= 0 and prev_map >= 0 and cur_map != prev_map:
                return (True, cur_map, cur_x, cur_y)
            # Trường hợp dịch chuyển sang khu vực khác trong CÙNG 1 map (vd: Acheron Safe -> Alkmar/Ubaid cùng map 91)
            if cur_map == prev_map and prev_x >= 0 and cur_x >= 0:
                if math.hypot(cur_x - prev_x, cur_y - prev_y) >= 18.0:
                    return (True, cur_map, cur_x, cur_y)
            time.sleep(0.2)
        cur_map, cur_x, cur_y = self._get_player_state()
        return (False, cur_map, cur_x, cur_y)

    # --- Thực thi 1 lần qua cổng GATE bằng C1:1C (Unit.HJDEPLPHNBO) ---

    def enter_gate_by_id(
        self,
        gate_id: int,
        mode: str = "auto",
        expected_map: int = -1,
        x: int = -1,
        y: int = -1,
        timeout: float = 4.5,
        walk_timeout: float = 25.0,
        stop_event: Optional[threading.Event] = None,
    ) -> GateResult:
        """
        Gửi gói C1:1C qua hàm gốc Mega.Unit.HJDEPLPHNBO(gate_id, coord) trên MainThread.

        Args:
            gate_id: ID cổng Gate cần bước vào (source gate ID trong TableWorld.Gate).
            mode:
              - "direct": Gọi C1:1C ngay lập tức từ vị trí hiện tại.
              - "walk":   Chạy tới tâm cổng trước rồi gọi C1:1C.
              - "auto":   Thử direct trước; nếu server không warp (do kiểm tra khoảng cách),
                          tự động chạy tới tâm cổng rồi gọi lại C1:1C!
        """
        gate_id = int(gate_id)
        mode = str(mode or "auto").lower().strip()
        prev_map, prev_x, prev_y = self._get_player_state()
        gate_info = self.catalog.get_gate(gate_id)

        if expected_map < 0 and gate_info is not None:
            tgt = self.catalog.get_gate(gate_info.target_gate) if gate_info.target_gate > 0 else gate_info
            if tgt is not None:
                expected_map = tgt.map_id

        def _fire_c1_1c(gx: int, gy: int) -> Tuple[bool, int, int, int, Dict[str, Any]]:
            p_map, p_x, p_y = self._get_player_state()
            q = self.engine.enter_gate(gate_id, gx, gy)
            if not q or not q.get("ok"):
                return (False, p_map, p_x, p_y, {"queue_res": q})
            # Đợi MainThread flush xong
            t0 = time.time()
            mt_res: Dict[str, Any] = {}
            while time.time() - t0 < 1.5:
                mt_res = self.engine.get_last_gate_enter_result() or {}
                if mt_res.get("done"):
                    break
                time.sleep(0.05)
            moved, n_map, n_x, n_y = self._wait_for_gate_transition(
                p_map, p_x, p_y, expected_map=expected_map, timeout=timeout, stop_event=stop_event
            )
            return (moved, n_map, n_x, n_y, {"queue_res": q, "mainthread_res": mt_res})

        # 1. Thử chế độ direct trước nếu mode là "direct" hoặc "auto"
        if mode in ("direct", "auto"):
            self.log(f"Gọi REA C1:1C direct -> Gate #{gate_id} (from map={prev_map}, pos=({prev_x},{prev_y}))")
            moved, n_map, n_x, n_y, dbg = _fire_c1_1c(x, y)
            if moved:
                self.log(f"Đã qua Gate #{gate_id} thành công (direct C1:1C) -> Map {n_map} ({n_x},{n_y})!", "INFO")
                return GateResult(
                    ok=True,
                    message=f"Qua Gate #{gate_id} thành công (direct C1:1C)",
                    method="direct_c1_1c",
                    from_map=prev_map,
                    to_map=n_map,
                    gate_id=gate_id,
                    hops_done=1,
                    details=dbg,
                )
            if mode == "direct":
                return GateResult(
                    ok=False,
                    message=f"Server không phản hồi direct C1:1C cho Gate #{gate_id} (có thể yêu cầu đứng gần cổng hoặc thiếu điều kiện Level/VIP).",
                    method="direct_c1_1c",
                    from_map=prev_map,
                    to_map=n_map,
                    gate_id=gate_id,
                    details=dbg,
                )

        # 2. Chế độ walk (hoặc auto fallback): Chạy tới tâm cổng rồi gửi C1:1C
        if gate_info is None:
            return GateResult(
                ok=False,
                message=f"Không có tọa độ Gate #{gate_id} trong catalog để tự chạy tới cổng (hãy gọi refresh_catalog() trước).",
                method="walk_c1_1c",
                from_map=prev_map,
                to_map=prev_map,
                gate_id=gate_id,
            )

        cur_map, _, _ = self._get_player_state()
        if gate_info.map_id >= 0 and cur_map >= 0 and cur_map != gate_info.map_id:
            return GateResult(
                ok=False,
                message=f"Nhân vật đang ở Map {cur_map}, nhưng cổng Gate #{gate_id} nằm ở Map {gate_info.map_id}.",
                method="walk_c1_1c",
                from_map=cur_map,
                to_map=cur_map,
                gate_id=gate_id,
            )

        cx, cy = gate_info.center
        self.log(f"Fallback: Di chuyển tới tâm cổng Gate #{gate_id} tại ({cx}, {cy}) trên Map {gate_info.map_id}...")
        arrived = self._walk_to_coord(cx, cy, tolerance=2.5, timeout=walk_timeout, stop_event=stop_event)
        if not arrived:
            return GateResult(
                ok=False,
                message=f"Không thể đi tới tọa độ cổng Gate #{gate_id} ({cx}, {cy}) trong {walk_timeout}s.",
                method="walk_c1_1c",
                from_map=prev_map,
                to_map=self._get_player_state()[0],
                gate_id=gate_id,
            )

        # Kiểm tra xem bước tới cổng game đã tự chuyển map chưa
        after_walk_map, aw_x, aw_y = self._get_player_state()
        if expected_map >= 0 and after_walk_map == expected_map and after_walk_map != prev_map:
            return GateResult(
                ok=True,
                message=f"Đã tự qua Gate #{gate_id} khi tới cổng -> Map {after_walk_map}",
                method="walk_auto_trigger",
                from_map=prev_map,
                to_map=after_walk_map,
                gate_id=gate_id,
                hops_done=1,
            )

        self.log(f"Đã tới cổng Gate #{gate_id} ({aw_x},{aw_y}) -> Bắn gói C1:1C xuyên cổng (bỏ qua popup)...")
        moved, n_map, n_x, n_y, dbg = _fire_c1_1c(cx, cy)
        if moved:
            self.log(f"Đã xuyên Gate #{gate_id} thành công (walk + C1:1C) -> Map {n_map} ({n_x},{n_y})!", "INFO")
            return GateResult(
                ok=True,
                message=f"Qua Gate #{gate_id} thành công (walk + C1:1C)",
                method="walk_c1_1c",
                from_map=prev_map,
                to_map=n_map,
                gate_id=gate_id,
                hops_done=1,
                details=dbg,
            )

        return GateResult(
            ok=False,
            message=f"Đã tới cổng Gate #{gate_id} và gửi C1:1C nhưng server chưa chuyển map (kiểm tra MinLevel={gate_info.min_level}, AccountLevel={gate_info.account_level}).",
            method="walk_c1_1c",
            from_map=prev_map,
            to_map=n_map,
            gate_id=gate_id,
            details=dbg,
        )

    # --- Điều hướng trọn gói tới các Map GATE (Ubail, Alkmar, Debenter, Uruk, Nars...) ---

    def _bootstrap_to_acheron(self, stop_event: Optional[threading.Event] = None) -> bool:
        """
        Đưa nhân vật về Acheron Safe Zone (Map 91) làm bàn đạp bằng '/move Acheron'.
        LƯU Ý: TUYỆT ĐỐI không gọi C1:F8:30 (Sir Lesnar) vì đó là gói đăng ký Arka War
        của Guild Master sẽ gây popup 'SIR LESNAR: You are not the guild master'.
        """
        cur_map, cur_x, cur_y = self._get_player_state()
        if cur_map in (91, 92, 95, 96, 100, 101, 110):
            return True

        self.log("Đang ngoài cụm Acheron -> Gửi '/move Acheron' để làm bàn đạp vào hệ thống Gate...")
        try:
            self.engine.send_chat("/move Acheron")
        except Exception as e:
            self.log(f"Lỗi gửi '/move Acheron': {e}", "WARN")

        moved, n_map, _, _ = self._wait_for_gate_transition(
            cur_map, cur_x, cur_y, expected_map=91, timeout=4.5, stop_event=stop_event
        )
        return moved and n_map in (91, 92)

    def go_to_gate_map(
        self,
        target: str | int,
        mode: str = "auto",
        allow_acheron_bootstrap: bool = True,
        try_move_cmd_first: bool = False,
        auto_confirm: bool = True,
        stop_event: Optional[threading.Event] = None,
    ) -> GateResult:
        """
        Điều hướng trọn gói nhân vật tới bất kỳ Map GATE nào:
        Hỗ trợ tên/alias: 'ubail'/'ubaid', 'alka'/'alkmar', 'deventer'/'debenter',
        'uruk', 'nars', 'nixies', 'acheron', hoặc Gate ID / Map ID.

        Trên MegaMU thực tế, lệnh '/move <map>' của các map [Gate] thả nhân vật ĐÚNG TỌA ĐỘ
        của cổng Portal vật lý (vd: '/move ubaid' -> Map 91 (84,204) = Portal #422 -> Ubaid #423).
        Khi auto_confirm=True, bot bật Auto-Confirm Gate hook (0ms) + dự phòng bắn trực tiếp
        C1:1C vào Portal Gate để xuyên cổng ngay lập tức không cần bấm tay!
        """
        self.ensure_catalog()
        resolved = self.catalog.resolve_target(target)
        if not resolved.get("ok"):
            return GateResult(ok=False, message=resolved.get("error", "resolve_failed"))

        dest_name = resolved.get("name", str(target))
        dest_map = int(resolved.get("map_id", -1))
        dest_gate = int(resolved.get("gate_id", -1))
        portal_gate_id = int(resolved.get("portal_gate_id", -1))
        canonical = resolved.get("canonical", "")
        start_map, start_x, start_y = self._get_player_state()

        if auto_confirm and hasattr(self.engine, "set_auto_gate_confirm"):
            try:
                self.engine.set_auto_gate_confirm(True)
            except Exception:
                pass

        self.log(
            f"Mục tiêu GATE: '{target}' -> {dest_name} (map_id={dest_map}, portal={portal_gate_id}, dest_gate={dest_gate}) | "
            f"Hiện tại: Map {start_map} ({start_x},{start_y})"
        )

        # Kiểm tra đã đứng đúng bên trong vùng săn đích chưa (xử lý chuẩn cả Map 91 Safe Zone vs Alkmar vs Ubaid)
        portal_obj = self.catalog.get_gate(portal_gate_id) if portal_gate_id > 0 else None
        if dest_map >= 0 and is_inside_gate_destination(canonical, dest_map, portal_obj, start_map, start_x, start_y):
            return GateResult(
                ok=True,
                message=f"Nhân vật đã ở sẵn bên trong {dest_name} (Map {start_map}, {start_x},{start_y}).",
                method="already_there",
                from_map=start_map,
                to_map=start_map,
                gate_id=dest_gate,
                hops_done=0,
            )

        # Trường hợp chuẩn MegaMU [Gate]: MoveGate chồng lên PortalGate (vd: Alkmar #418, Ubaid #422, Debenter #435, Uruk #450, Nars #487, Nixies #523)
        mv: Optional[MoveEntry] = resolved.get("move")
        mv_cmd = mv.command if (mv and mv.command) else KNOWN_MOVE_COMMANDS.get(canonical, "")

        if portal_obj is not None and mode == "auto" and mv_cmd:
            cur_map, cur_x, cur_y = self._get_player_state()
            on_portal_already = (cur_map == portal_obj.map_id and portal_obj.contains(cur_x, cur_y, pad=2))

            if on_portal_already:
                self.log(f"Đang đứng sẵn trên cổng Portal #{portal_obj.index} ({cur_x},{cur_y}) -> Bắn C1:1C xuyên cổng ngay!")
                return self.enter_gate_by_id(
                    portal_obj.index, mode="direct", expected_map=dest_map, x=cur_x, y=cur_y, stop_event=stop_event
                )

            # Nếu đang đứng sẵn trên đảo Safe Zone chứa cổng (vd đang ở Acheron Town) -> chạy thẳng tới cổng hoặc /move
            self.log(f"Gửi '/move {mv_cmd}' tới cổng Portal #{portal_obj.index} (Auto-Confirm Gate = {auto_confirm})...")
            try:
                self.engine.send_chat(f"/move {mv_cmd}")
            except Exception as e:
                self.log(f"Lỗi gửi '/move {mv_cmd}': {e}", "WARN")

            # Chờ 4.5s xem Auto-Confirm (trì hoãn 300ms) đã xuyên thẳng vào map đích chưa, hoặc dự phòng bắn C1:1C khi đã đáp lên cổng
            deadline = time.time() + 4.5
            last_c11c = 0.0
            while time.time() < deadline:
                if stop_event and stop_event.is_set():
                    return GateResult(ok=False, message="Đã dừng theo yêu cầu.", method="cancelled", from_map=start_map, to_map=start_map)
                cm, cx, cy = self._get_player_state()
                if dest_map >= 0 and is_inside_gate_destination(canonical, dest_map, portal_obj, cm, cx, cy):
                    return GateResult(
                        ok=True,
                        message=f"Đã vào {dest_name} (Map {cm}, {cx},{cy}) qua '/move {mv_cmd}' + Auto-Confirm Gate!",
                        method="move_auto_confirm_gate",
                        from_map=start_map,
                        to_map=cm,
                        gate_id=portal_obj.index,
                        hops_done=1,
                    )
                if cm == portal_obj.map_id and portal_obj.contains(cx, cy, pad=2):
                    now_t = time.time()
                    if now_t - last_c11c >= 1.1:
                        last_c11c = now_t
                        self.log(f"Đã đáp lên cổng Portal #{portal_obj.index} ({cx},{cy}) -> Dự phòng bắn C1:1C xuyên cổng!")
                        try:
                            self.engine.enter_gate(portal_obj.index, cx, cy)
                        except Exception:
                            pass
                time.sleep(0.25)

            # Nếu vẫn đang ở Map chứa cổng (vd Map 91 Acheron Town mà /move không đưa tới cổng), đi bộ tới tâm cổng rồi xuyên cổng!
            cm_after, _, _ = self._get_player_state()
            if cm_after == portal_obj.map_id:
                self.log(f"Chưa qua cổng sau /move -> Tự động chạy tới tâm cổng Portal #{portal_obj.index} {portal_obj.center} rồi bắn C1:1C!")
                return self.enter_gate_by_id(
                    portal_obj.index, mode="walk", expected_map=dest_map, stop_event=stop_event
                )

        # Tùy chọn 0: Nếu user bật try_move_cmd_first (cho map thường không có portal chồng lấn)
        if try_move_cmd_first or (portal_obj is None and mv_cmd and mode == "auto"):
            if mv_cmd:
                self.log(f"Thử lệnh nhanh '/move {mv_cmd}'...")
                try:
                    self.engine.send_chat(f"/move {mv_cmd}")
                except Exception:
                    pass
                moved, n_map, _, _ = self._wait_for_gate_transition(
                    start_map, start_x, start_y, expected_map=dest_map, timeout=3.5, stop_event=stop_event
                )
                if moved and (dest_map < 0 or n_map == dest_map):
                    return GateResult(
                        ok=True,
                        message=f"Đã vào {dest_name} bằng '/move {mv_cmd}' -> Map {n_map}",
                        method="move_cmd",
                        from_map=start_map,
                        to_map=n_map,
                        gate_id=dest_gate,
                        hops_done=1,
                    )

        # 1. Nếu mode == "direct" và biết rõ portal_gate_id (hoặc dest_gate), thử bắn thẳng C1:1C trước
        direct_gid = portal_gate_id if portal_gate_id > 0 else dest_gate
        if mode == "direct" and direct_gid > 0:
            return self.enter_gate_by_id(direct_gid, mode="direct", expected_map=dest_map, stop_event=stop_event)

        # 2. Tìm đường BFS qua các cổng Gate trong catalog
        cur_map, _, _ = self._get_player_state()
        path = self.catalog.find_gate_path(cur_map, dest_map, to_gate_id=dest_gate)

        # 3. Nếu chưa có đường nối trực tiếp từ map hiện tại (vd đang ở Lorencia) và đích thuộc cụm Acheron
        if not path and allow_acheron_bootstrap and dest_map in (91, 92, 95, 96, 100, 101, 110):
            if self._bootstrap_to_acheron(stop_event=stop_event):
                cur_map, _, _ = self._get_player_state()
                if cur_map == dest_map and dest_gate <= 0:
                    return GateResult(
                        ok=True,
                        message=f"Đã vào {dest_name} (Map {cur_map}) qua Acheron bootstrap.",
                        method="acheron_bootstrap",
                        from_map=start_map,
                        to_map=cur_map,
                        hops_done=1,
                    )
                path = self.catalog.find_gate_path(cur_map, dest_map, to_gate_id=dest_gate)

        # 4. Nếu vẫn không có đường BFS nhưng biết cổng -> thử gọi trực tiếp C1:1C
        if not path:
            if direct_gid > 0:
                self.log(f"Không tìm thấy chuỗi Gate từ Map {cur_map}, thử gọi trực tiếp C1:1C -> Gate #{direct_gid}...")
                return self.enter_gate_by_id(direct_gid, mode=mode, expected_map=dest_map, stop_event=stop_event)
            return GateResult(
                ok=False,
                message=f"Không tìm thấy đường Gate từ Map {cur_map} tới {dest_name} (Map {dest_map}). Hãy chạy refresh_catalog() khi đang mở game.",
                method="bfs_not_found",
                from_map=start_map,
                to_map=cur_map,
            )

        # 5. Thực thi từng chặng Gate hop
        self.log(
            "Lộ trình GATE (" + str(len(path)) + " chặng): "
            + " -> ".join(f"Gate#{h.source_gate.index}(Map {h.from_map}->Map {h.to_map})" for h in path)
        )
        hops_done = 0
        for idx, hop in enumerate(path, 1):
            if stop_event and stop_event.is_set():
                return GateResult(
                    ok=False,
                    message="Đã dừng theo yêu cầu (stop_event).",
                    method="cancelled",
                    from_map=start_map,
                    to_map=self._get_player_state()[0],
                    hops_done=hops_done,
                )
            self.log(
                f"Chặng {idx}/{len(path)}: Vào Gate #{hop.source_gate.index} "
                f"(Map {hop.from_map} {hop.source_gate.center} -> TargetGate #{hop.target_gate.index} Map {hop.to_map})"
            )
            step_res = self.enter_gate_by_id(
                gate_id=hop.source_gate.index,
                mode=mode,
                expected_map=hop.to_map,
                stop_event=stop_event,
            )
            if not step_res.ok:
                return GateResult(
                    ok=False,
                    message=f"Thất bại tại chặng {idx}/{len(path)} (Gate #{hop.source_gate.index}): {step_res.message}",
                    method=step_res.method,
                    from_map=start_map,
                    to_map=step_res.to_map,
                    gate_id=hop.source_gate.index,
                    hops_done=hops_done,
                    details=step_res.details,
                )
            hops_done += 1
            time.sleep(0.6)

        final_map, final_x, final_y = self._get_player_state()
        return GateResult(
            ok=True,
            message=f"Đã vào thành công {dest_name} (Map {final_map}, tọa độ {final_x},{final_y}) sau {hops_done} chặng Gate!",
            method="gate_path_c1_1c",
            from_map=start_map,
            to_map=final_map,
            gate_id=dest_gate,
            hops_done=hops_done,
        )


# ---------------------------------------------------------------------------
# CLI Tool để test nhanh / dump bảng Gate trực tiếp từ game đang chạy
# ---------------------------------------------------------------------------

def _find_first_megamu_pid() -> Optional[int]:
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name"]):
            if (p.info.get("name") or "").lower() == "megamu.exe":
                return int(p.info["pid"])
    except Exception:
        pass
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MEGAMU Gate REA Navigator CLI (C1:1C / TableWorld.Gate)")
    parser.add_argument("--pid", type=int, default=0, help="PID của MEGAMU.exe (mặc định tự tìm)")
    parser.add_argument("--dump", action="store_true", help="Đọc toàn bộ TableWorld.Gate & Move từ RAM và lưu cache")
    parser.add_argument("--elemental", action="store_true", help="Hiển thị bảng Gate cho cụm Acheron/Alkmar/Ubaid/Debenter/Uruk/Nars")
    parser.add_argument("--tile-gate", action="store_true", help="Kiểm tra ô tọa độ nhân vật đang đứng có phải Gate không")
    parser.add_argument("--enter-gate", type=int, default=-1, help="Bắn trực tiếp C1:1C vào Gate ID cụ thể")
    parser.add_argument("--goto", type=str, default="", help="Đi tới map GATE theo tên/alias (vd: ubail, alka, deventer, uruk, nars)")
    parser.add_argument("--mode", choices=["auto", "direct", "walk"], default="auto", help="Chế độ qua Gate (mặc định: auto)")
    args = parser.parse_args(argv)

    pid = args.pid or _find_first_megamu_pid()
    if not pid:
        if args.elemental:
            cat = GateCatalog()
            cnt = cat.load_cache()
            print(f"[Offline Cache] Đã nạp {cnt} gates từ {cat.cache_path}")
            print(json.dumps(cat.summarize_elemental_maps(), indent=2, ensure_ascii=False))
            return 0
        print("Không tìm thấy tiến trình MEGAMU.exe đang chạy. Hãy mở game hoặc truyền --pid <PID>.")
        return 1

    from meg_direct_engine import MegDirectEngine
    eng = MegDirectEngine(pid)
    if not eng.attach():
        print(f"Không thể attach Frida vào PID {pid}.")
        return 1

    try:
        nav = MegGateNavigator(eng)
        if args.dump or args.elemental:
            res = nav.refresh_catalog(save_cache=True)
            print("Refresh result:", json.dumps(res, ensure_ascii=False))
            if args.elemental:
                print(json.dumps(nav.catalog.summarize_elemental_maps(), indent=2, ensure_ascii=False))
        if args.tile_gate:
            print("Current Tile Gate:", json.dumps(nav.inspect_current_tile_gate(), indent=2, ensure_ascii=False))
        if args.enter_gate >= 0:
            nav.ensure_catalog()
            r = nav.enter_gate_by_id(args.enter_gate, mode=args.mode)
            print("Enter Gate Result:", json.dumps(asdict(r), indent=2, ensure_ascii=False))
        if args.goto:
            r = nav.go_to_gate_map(args.goto, mode=args.mode)
            print("GoTo Gate Map Result:", json.dumps(asdict(r), indent=2, ensure_ascii=False))
    finally:
        eng.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
