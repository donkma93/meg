#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Quest Engine — Tự động làm Nhiệm Vụ Chuyển Cấp 2, Marlon (Lv220) & Cấp 3 (Master)
=============================================================================================
- Đọc trực tiếp trạng thái QuestManager trong RAM qua Frida Native RPC (0% OCR, 0% hardcode RVA)
- Tự nhận diện Class nhân vật, ChangeUp (0=Cấp 1, 1=Cấp 2, 2=Cấp 3), Level, Zen
- Tự động:
  1. Cấp 2 (Lv150): Sebina the Priest (Devias) -> Scroll of Emperor (Lost Tower 7) -> Món Class 2 (Lost Tower 7) -> Trả NV
  2. Marlon (Lv220, tùy chọn): NPC Marlon cố định tại Devias ngay cạnh Sebina -> Ring of Honor (+ Dark Stone cho DK) -> Trả NV
  3. Cấp 3 (Lv400):
     - Bước 1 (Quest 4): Priest Devin (Crywolf) -> Flame of Death Beam Knight (Tarkan 2) + Horn of Hell Maine (Aida 2) + Feather of Dark Phoenix (Icarus)
     - Bước 2 (Quest 5): Werewolf Quarrel (Crywolf -> Barracks) -> Giết 20 Balram + 20 Death Spirit + 20 Soram tại 3 khu vực riêng biệt (đọc MonsterKillCount trực tiếp) -> Về Crywolf trả Priest Devin
     - Bước 3 (Quest 6): Barracks -> Gatekeeper -> Refuge -> Giết 1 Dark Elf -> Về Crywolf trả Priest Devin -> Thăng Cấp 3!
- Chủ động quét & nhặt Quest Item rơi trên đất (gói C1:22 tại chỗ) ngay cả khi người chơi chưa cài bộ lọc Helper.
"""

import copy
import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ==============================================================================
# BẢNG HẰNG SỐ CHUẨN MU ONLINE / MEGAMU (KHÔNG CHỨA BẤT KỲ RVA OFFSET NÀO)
# ==============================================================================

QUEST_STATE_STANDBY = 0
QUEST_STATE_ACCEPT = 1
QUEST_STATE_FINISH = 2
QUEST_STATE_CANCEL = 3

QUEST_STATE_LABELS = {
    QUEST_STATE_STANDBY: "Chưa nhận",
    QUEST_STATE_ACCEPT: "Đang làm",
    QUEST_STATE_FINISH: "Hoàn thành",
    QUEST_STATE_CANCEL: "Chưa mở",
}

# Mapping chuẩn enum DGPKBMOFOPF.HJBGBDKAHPM của MegaMU
CLASS_NAMES: Dict[int, str] = {
    0: "DW",
    1: "DK",
    2: "Elf",
    3: "MG",
    4: "DL",
    5: "Sum",
    6: "RF",
    7: "GL",
    8: "RW",
    9: "SL",
    10: "GC",
    11: "KM",
    12: "LM",
    13: "IK",
    14: "AL",
    15: "CR",
}

# Các class đặc biệt không phải làm nhiệm vụ Cấp 2 (Sebina) & Marlon mà lên thẳng Cấp 3
SKIP_CLASS2_CLASSES = {3, 4, 6, 7}  # MG, DL, RF, GL

# Các class có nhiệm vụ Marlon bước 2: Dark Stone / Combo (Quest 3)
DARK_STONE_CLASSES = {1, 9, 13, 15}  # DK, Slayer (SL), Illusion Knight (IK), Crusader (CR)

# Item IDs (Section * 512 + Index) & Level chuẩn MU Online / MegaMU
# Lưu ý quan trọng:
#   14,23 (7191): Level 0 = Scroll of Emperor | Level 1 = Ring of Honor (Marlon)
#   14,24 (7192): Level 0 = Broken Sword      | Level 1 = Dark Stone (Marlon DK)
#   14,25 (7193): Tear of Elf
#   14,26 (7194): Soul of Wizard
#   14,68 (7236): Abyssal Eye (Summoner)
ITEM_SCROLL_OF_EMPEROR = 14 * 512 + 23   # 7191 (Level 0)
ITEM_CLASS2_PART2 = 14 * 512 + 24        # 7192 (Level 0: Broken Sword; các class khác 7193/7194/7236)
ITEM_TEAR_OF_ELF = 14 * 512 + 25         # 7193 (Tear of Elf)
ITEM_SOUL_OF_WIZARD = 14 * 512 + 26      # 7194 (Soul of Wizard)
ITEM_ABYSSAL_EYE = 14 * 512 + 68         # 7236 (Abyssal Eye)
ITEM_RING_OF_HONOR = 14 * 512 + 23       # 7191 (Level 1 — Ring of Honor!)
ITEM_DARK_STONE = 14 * 512 + 24          # 7192 (Level 1 — Dark Stone!)
ITEM_FLAME_DEATH_BEAM = 14 * 512 + 65    # 7233 (Flame of Death Beam Knight - Tarkan 2)
ITEM_HORN_HELL_MAINE = 14 * 512 + 66     # 7234 (Horn of Hell Maine - Aida 2)
ITEM_FEATHER_PHOENIX = 14 * 512 + 67     # 7235 (Feather of Dark Phoenix - Icarus)

CLASS2_PART2_ITEM_IDS = [ITEM_CLASS2_PART2, ITEM_TEAR_OF_ELF, ITEM_SOUL_OF_WIZARD, ITEM_ABYSSAL_EYE]

QUEST_ITEM_NAMES: Dict[int, str] = {
    ITEM_SCROLL_OF_EMPEROR: "Scroll of Emperor / Ring of Honor",
    ITEM_CLASS2_PART2: "Broken Sword / Dark Stone",
    ITEM_TEAR_OF_ELF: "Tear of Elf",
    ITEM_SOUL_OF_WIZARD: "Soul of Wizard",
    ITEM_ABYSSAL_EYE: "Abyssal Eye",
    ITEM_FLAME_DEATH_BEAM: "Flame of Death Beam Knight",
    ITEM_HORN_HELL_MAINE: "Horn of Hell Maine",
    ITEM_FEATHER_PHOENIX: "Feather of Dark Phoenix",
}

# Bảng vật phẩm Cấp 2 Bước 2 (Quest 1) CHÍNH XÁC theo từng Class:
#   (item_id, item_level, label, name_keywords)
CLASS2_PART2_SPECS: Dict[int, Tuple[int, int, str, Tuple[str, ...]]] = {
    0: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    1: (ITEM_CLASS2_PART2, 0, "Broken Sword", ("broken sword",)),
    2: (ITEM_TEAR_OF_ELF, 0, "Tear of Elf", ("tear of elf",)),
    5: (ITEM_ABYSSAL_EYE, 0, "Abyssal Eye", ("abyssal eye",)),
    8: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    9: (ITEM_CLASS2_PART2, 0, "Broken Sword", ("broken sword",)),      # Slayer (SL) -> Broken Sword!
    10: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    11: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    12: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    13: (ITEM_CLASS2_PART2, 0, "Broken Sword", ("broken sword",)),      # Illusion Knight (IK) -> Broken Sword
    14: (ITEM_SOUL_OF_WIZARD, 0, "Soul of Wizard", ("soul of wizard", "soul of prophet")),
    15: (ITEM_CLASS2_PART2, 0, "Broken Sword", ("broken sword",)),      # Crusader (CR) -> Broken Sword
}

CLASS2_PART2_LABELS: Dict[int, str] = {k: v[2] for k, v in CLASS2_PART2_SPECS.items()}


def get_class2_part2_spec(cls_id: int) -> Tuple[int, int, str, Tuple[str, ...]]:
    """Trả về (item_id, item_level, label, keywords) chính xác cho NV Cấp 2 Bước 2 theo Class."""
    return CLASS2_PART2_SPECS.get(int(cls_id), (ITEM_CLASS2_PART2, 0, "Broken Sword", ("broken sword",)))

# Monster IDs nhiệm vụ Cấp 3 (Barracks & Refuge)
MONSTER_BALRAM = 409
MONSTER_DEATH_SPIRIT = 410
MONSTER_SORAM = 411
MONSTER_DARK_ELF = 412

BARRACKS_REQ_COUNT = 20

BARRACKS_MONSTERS = [
    (MONSTER_BALRAM, "Balram", BARRACKS_REQ_COUNT, "barracks_balram"),
    (MONSTER_DEATH_SPIRIT, "Death Spirit", BARRACKS_REQ_COUNT, "barracks_death_spirit"),
    (MONSTER_SORAM, "Soram", BARRACKS_REQ_COUNT, "barracks_soram"),
]

# Điểm tuần tra dự phòng trong từng khu vực Barracks nếu đứng >45s chưa thấy tăng số kill
BARRACKS_ZONE_PATROL: Dict[str, List[Tuple[int, int]]] = {
    "barracks_balram": [(51, 137), (40, 108), (62, 138)],
    "barracks_death_spirit": [(78, 90), (76, 82), (95, 72)],
    "barracks_soram": [(133, 145), (140, 153), (118, 135)],
}

# NPC Skins (Class ID trong Viewport)
NPC_SEBINA = 235
NPC_MARLON = 229
NPC_PRIEST_DEVIN = 406
NPC_WEREWOLF_QUARREL = 407
NPC_GATEKEEPER = 408

# Map IDs chuẩn MU
MAP_LORENCIA = 0
MAP_DEVIAS = 2
MAP_NORIA = 3
MAP_LOST_TOWER = 4
MAP_ATLANS = 7
MAP_TARKAN = 8
MAP_ICARUS = 10
MAP_AIDA = 33
MAP_CRYWOLF = 34
MAP_BARRACKS = 41
MAP_REFUGE = 42

# Cấu hình mặc định (có thể tùy chỉnh và lưu vào config/quest_config.json)
DEFAULT_QUEST_CONFIG: Dict[str, Any] = {
    "mode": "all_2_3",             # "all_2_3" | "class2_only" | "marlon_only" | "class3_only"
    "include_marlon": True,        # Kèm NV Marlon Lv220 (Ring of Honor + Dark Stone)
    "auto_pickup_quest_items": True,
    "class3_min_level": 400,       # Chuẩn MegaMU: bắt buộc Level 400 mới nói chuyện được Priest Devin ở Crywolf
    "barracks_req_count": 20,      # Chuẩn MegaMU: 20 Balram + 20 Death Spirit + 20 Soram (3 khu riêng biệt)
    "farm_timeout_min": 45,        # Thời gian tối đa ở 1 bãi trước khi cảnh báo (phút)
    "npcs": {
        "sebina": {"map_cmd": "/move devias", "map_id": MAP_DEVIAS, "x": 183, "y": 32, "skin": NPC_SEBINA, "name": "Sebina"},
        "marlon": {"map_cmd": "/move devias", "map_id": MAP_DEVIAS, "x": 185, "y": 32, "skin": NPC_MARLON, "name": "Marlon"},
        "devin": {"map_cmd": "/move crywolf", "map_id": MAP_CRYWOLF, "x": 228, "y": 48, "skin": NPC_PRIEST_DEVIN, "name": "Devin"},
        "werewolf": {"map_cmd": "/move crywolf", "map_id": MAP_CRYWOLF, "x": 62, "y": 239, "skin": NPC_WEREWOLF_QUARREL, "name": "Werewolf"},
        "gatekeeper": {"map_cmd": "", "map_id": MAP_BARRACKS, "x": 119, "y": 168, "skin": NPC_GATEKEEPER, "name": "Gatekeeper"},
    },
    "spots": {
        "scroll_emperor": {"label": "Scroll of Emperor (Lost 7)", "map_cmd": "/move losttower7", "map_id": MAP_LOST_TOWER, "x": 53, "y": 93},
        "class2_part2": {"label": "Vật phẩm Cấp 2 (Lost 7)", "map_cmd": "/move losttower7", "map_id": MAP_LOST_TOWER, "x": 53, "y": 93},
        "ring_of_honor": {"label": "Ring of Honor (Tarkan)", "map_cmd": "/move tarkan", "map_id": MAP_TARKAN, "x": 162, "y": 65},
        "dark_stone": {"label": "Dark Stone (Tarkan)", "map_cmd": "/move tarkan", "map_id": MAP_TARKAN, "x": 162, "y": 65},
        "flame_death_beam": {"label": "Flame of Death Beam Knight (Tarkan 2)", "map_cmd": "/move tarkan2", "map_id": MAP_TARKAN, "x": 162, "y": 224},
        "horn_hell_maine": {"label": "Horn of Hell Maine (Aida 2)", "map_cmd": "/move aida2", "map_id": MAP_AIDA, "x": 118, "y": 128},
        "feather_phoenix": {"label": "Feather of Dark Phoenix (Icarus)", "map_cmd": "/move icarus", "map_id": MAP_ICARUS, "x": 37, "y": 238},
        "barracks_balram": {"label": "Barracks — Khu 1: Balram (20 con)", "map_cmd": "", "map_id": MAP_BARRACKS, "x": 51, "y": 137},
        "barracks_death_spirit": {"label": "Barracks — Khu 2: Death Spirit (20 con)", "map_cmd": "", "map_id": MAP_BARRACKS, "x": 78, "y": 90},
        "barracks_soram": {"label": "Barracks — Khu 3: Soram (20 con)", "map_cmd": "", "map_id": MAP_BARRACKS, "x": 133, "y": 145},
        "refuge_dark_elf": {"label": "Refuge — Dark Elf", "map_cmd": "", "map_id": MAP_REFUGE, "x": 96, "y": 175},
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _read_map_id(info: Optional[Dict[str, Any]]) -> int:
    """Đọc Map ID tương thích cả camelCase (`mapId` từ get_player_info) và snake_case (`map_id`)."""
    if not isinstance(info, dict):
        return -1
    val = info.get("map_id")
    if val is None:
        val = info.get("mapId")
    try:
        return int(val) if val is not None else -1
    except Exception:
        return -1


def _read_xy(info: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    """Đọc tọa độ (x, y) tương thích cả `x/y` và `tileX/tileY`."""
    if not isinstance(info, dict):
        return (0, 0)
    rx = info.get("x") if info.get("x") is not None else info.get("tileX", 0)
    ry = info.get("y") if info.get("y") is not None else info.get("tileY", 0)
    try:
        return (int(rx or 0), int(ry or 0))
    except Exception:
        return (0, 0)


def _is_subzone_warp_cmd(map_cmd: str) -> bool:
    """Trả về True CHỈ KHI lệnh warp nhắm tới phân khu/tầng phụ cùng Map ID (VD: /move losttower7, /move tarkan2, /move aida2).
    Các map 1 cổng duy nhất như `/move icarus`, `/move tarkan`, `/move crywolf` trả về False
    để KHÔNG BAO GIỜ bị warp giật ngược về đầu map khi đang đi bộ tới bãi xa (VD: Icarus Phoenix 37,238 cách cổng ~226 ô).
    """
    parts = str(map_cmd or "").strip().lower().split()
    if not parts:
        return False
    target = parts[-1]
    if target.isdigit() and len(parts) >= 2:
        return int(target) >= 2
    return len(target) >= 2 and target[-1] in "23456789" and target[-2].isalpha()


class QuestConfigManager:
    """Lưu & đọc cấu hình Auto Nhiệm Vụ từ config/quest_config.json."""

    def __init__(self, base_dir: Path):
        self.config_path = Path(base_dir) / "config" / "quest_config.json"

    def load(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return _deep_merge(DEFAULT_QUEST_CONFIG, data)
            except Exception:
                pass
        return copy.deepcopy(DEFAULT_QUEST_CONFIG)

    def save(self, cfg: Dict[str, Any]) -> bool:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            merged = _deep_merge(DEFAULT_QUEST_CONFIG, cfg)
            self.config_path.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False


# ==============================================================================
# HÀM PHÂN TÍCH TRẠNG THÁI NHIỆM VỤ (PURE LOGIC — DỄ UNIT TEST 100%)
# ==============================================================================

def get_quest_bit_state(states: Dict[str, int], quest_index: int) -> int:
    """Trả về trạng thái 0..3 của quest_index từ dict trả về bởi Frida."""
    if not isinstance(states, dict):
        return QUEST_STATE_CANCEL
    val = states.get(str(quest_index), states.get(quest_index, QUEST_STATE_CANCEL))
    try:
        return int(val)
    except Exception:
        return QUEST_STATE_CANCEL


def has_quest_item(
    quest_items: List[Dict[str, Any]],
    item_id: int,
    item_level: Optional[int] = None,
    name_keywords: Optional[Tuple[str, ...]] = None,
    extra_ids: Optional[Tuple[int, ...]] = None,
) -> bool:
    """Kiểm tra vật phẩm nhiệm vụ trong hòm theo (item_id + item_level) hoặc từ khóa tên."""
    for it in (quest_items or []):
        try:
            iid = int(it.get("id", -1))
            ilv = int(it.get("level", 0) or 0)
            iname = str(it.get("name") or "").lower()

            if name_keywords and iname:
                if any(kw in iname for kw in name_keywords):
                    return True

            if extra_ids and iid in extra_ids:
                return True

            if iid == int(item_id):
                if item_level is None or ilv == int(item_level):
                    return True
        except Exception:
            continue
    return False


def _has_scroll_of_emperor(items: List[Dict[str, Any]]) -> bool:
    return has_quest_item(items, ITEM_SCROLL_OF_EMPEROR, item_level=0, name_keywords=("scroll of emperor",))


def _has_class2_part2(items: List[Dict[str, Any]], cls_id: int) -> bool:
    item_id, item_lv, _lbl, keywords = get_class2_part2_spec(cls_id)
    return has_quest_item(items, item_id, item_level=item_lv, name_keywords=keywords)


def _has_ring_of_honor(items: List[Dict[str, Any]]) -> bool:
    return has_quest_item(items, ITEM_RING_OF_HONOR, item_level=1, name_keywords=("ring of honor",))


def _has_dark_stone(items: List[Dict[str, Any]]) -> bool:
    return has_quest_item(items, ITEM_DARK_STONE, item_level=1, name_keywords=("dark stone",))


def get_monster_kill_count(monster_kills: Dict[str, int], monster_id: int) -> int:
    if not isinstance(monster_kills, dict):
        return 0
    val = monster_kills.get(str(monster_id), monster_kills.get(monster_id, 0))
    try:
        return int(val)
    except Exception:
        return 0


def summarize_quest_snapshot(snap: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Phân tích snapshot từ `engine.get_quest_state()` thành thông tin hiển thị & bước kế tiếp cần làm.
    Trả về dict chuẩn:
      - ok, class_name, change_up, tier_text, level, zen
      - next_action: mã hành động cụ thể ("DONE", "NEED_LEVEL", "NEED_ZEN", "Q0_...", ..., "Q6_...")
      - current_quest_label: nhãn ngắn cho bảng UI
      - progress_text: tiến độ vật phẩm / số quái
      - reason: giải thích chi tiết nếu chưa đủ điều kiện
    """
    cfg = _deep_merge(DEFAULT_QUEST_CONFIG, cfg or {})
    if not snap or not snap.get("ok"):
        return {
            "ok": False,
            "class_name": "--",
            "change_up": -1,
            "tier_text": "--",
            "level": 0,
            "zen": 0,
            "next_action": "NOT_CONNECTED",
            "current_quest_label": "Chưa kết nối",
            "progress_text": "--",
            "reason": snap.get("error", "Chưa attach game") if isinstance(snap, dict) else "Chưa attach game",
        }

    cls_id = int(snap.get("class_id", -1))
    cls_name = CLASS_NAMES.get(cls_id, f"Class#{cls_id}")
    change_up = int(snap.get("change_up", 0))
    level = int(snap.get("level", 0))
    zen = int(snap.get("zen", 0))
    states = snap.get("states") or {}
    items = snap.get("quest_items") or []
    kills = snap.get("monster_kills") or {}

    tier_map = {0: "Cấp 1", 1: "Cấp 2", 2: "Cấp 3", 3: "Cấp 4"}
    tier_text = f"{cls_name} ({tier_map.get(change_up, f'C{change_up+1}')})"

    mode = str(cfg.get("mode", "all_2_3"))
    c3_min_lv = max(400, int(cfg.get("class3_min_level", 400) or 400))

    q0 = get_quest_bit_state(states, 0)
    q1 = get_quest_bit_state(states, 1)
    q2 = get_quest_bit_state(states, 2)
    q3 = get_quest_bit_state(states, 3)
    q4 = get_quest_bit_state(states, 4)
    q5 = get_quest_bit_state(states, 5)
    q6 = get_quest_bit_state(states, 6)

    include_marlon = (
        bool(cfg.get("include_marlon", False))
        or (mode == "marlon_only")
        or (q2 == QUEST_STATE_ACCEPT)
        or (q3 == QUEST_STATE_ACCEPT)
    )

    has_scroll = _has_scroll_of_emperor(items)
    has_c2_part2 = _has_class2_part2(items, cls_id)
    has_ring = _has_ring_of_honor(items)
    has_dark_stone = _has_dark_stone(items)
    has_flame = has_quest_item(items, ITEM_FLAME_DEATH_BEAM, name_keywords=("flame of death",))
    has_horn = has_quest_item(items, ITEM_HORN_HELL_MAINE, name_keywords=("horn of hell",))
    has_feather = has_quest_item(items, ITEM_FEATHER_PHOENIX, name_keywords=("feather of", "phoenix"))

    k_balram = get_monster_kill_count(kills, MONSTER_BALRAM)
    k_death = get_monster_kill_count(kills, MONSTER_DEATH_SPIRIT)
    k_soram = get_monster_kill_count(kills, MONSTER_SORAM)
    k_darkelf = get_monster_kill_count(kills, MONSTER_DARK_ELF)

    is_special_no_c2 = cls_id in SKIP_CLASS2_CLASSES

    def _result(next_action: str, q_label: str, prog: str, reason: str = "") -> Dict[str, Any]:
        return {
            "ok": True,
            "name": str(snap.get("name") or ""),
            "class_id": cls_id,
            "class_name": cls_name,
            "change_up": change_up,
            "tier_text": tier_text,
            "level": level,
            "zen": zen,
            "next_action": next_action,
            "current_quest_label": q_label,
            "progress_text": prog,
            "reason": reason,
            "states": states,
            "quest_items": items,
            "monster_kills": kills,
        }

    # --- 1. NHIỆM VỤ CẤP 2 (Sebina the Priest — Quest 0 & 1) ---
    if mode in ("all_2_3", "class2_only") and not is_special_no_c2 and change_up == 0:
        if q0 != QUEST_STATE_FINISH:
            if level < 150:
                return _result("NEED_LEVEL", "Cấp 2 (B1: Scroll)", f"Lv {level}/150", "Cần đạt Level 150 để làm NV Cấp 2")
            if q0 != QUEST_STATE_ACCEPT:
                if zen < 1_000_000:
                    return _result("NEED_ZEN", "Cấp 2 (B1: Scroll)", f"Zen {zen:,}/1M", "Cần tối thiểu 1.000.000 Zen để nhận NV Cấp 2 (B1)")
                return _result("Q0_ACCEPT", "Cấp 2 (B1: Scroll)", "Chưa nhận NV (Sebina)")
            if has_scroll:
                return _result("Q0_COMPLETE", "Cấp 2 (B1: Scroll)", "Scroll: 1/1 · Về trả Sebina")
            return _result("Q0_FARM", "Cấp 2 (B1: Scroll)", "Scroll of Emperor: 0/1")

        # Q0 đã xong -> Q1 (món Class 2 Part 2)
        p2_name = CLASS2_PART2_LABELS.get(cls_id, "Món Cấp 2")
        if q1 != QUEST_STATE_FINISH:
            if q1 != QUEST_STATE_ACCEPT:
                if zen < 2_000_000:
                    return _result("NEED_ZEN", f"Cấp 2 (B2: {p2_name})", f"Zen {zen:,}/2M", "Cần tối thiểu 2.000.000 Zen để nhận NV Cấp 2 (B2)")
                return _result("Q1_ACCEPT", f"Cấp 2 (B2: {p2_name})", "Chưa nhận NV (Sebina)")
            if has_c2_part2:
                return _result("Q1_COMPLETE", f"Cấp 2 (B2: {p2_name})", f"{p2_name}: 1/1 · Về trả Sebina")
            return _result("Q1_FARM", f"Cấp 2 (B2: {p2_name})", f"{p2_name}: 0/1")

    if mode == "class2_only":
        if is_special_no_c2:
            return _result("DONE", "Bỏ qua Cấp 2", f"{cls_name} lên thẳng Cấp 3")
        return _result("DONE", "Đã xong Cấp 2", "Hoàn tất chuyển cấp 2 ✓")

    # --- 2. NHIỆM VỤ MARLON Lv220 (Quest 2 Ring of Honor & Quest 3 Dark Stone cho DK) ---
    if include_marlon and not is_special_no_c2 and change_up >= 1:
        if q2 != QUEST_STATE_FINISH:
            if level < 220:
                return _result("NEED_LEVEL", "Marlon (Ring of Honor)", f"Lv {level}/220", "Cần đạt Level 220 để làm NV Marlon")
            if q2 != QUEST_STATE_ACCEPT:
                if zen < 2_000_000:
                    return _result("NEED_ZEN", "Marlon (Ring of Honor)", f"Zen {zen:,}/2M", "Cần tối thiểu 2.000.000 Zen cho Marlon")
                return _result("Q2_ACCEPT", "Marlon (Ring of Honor)", "Chưa nhận NV (Marlon)")
            if has_ring:
                return _result("Q2_COMPLETE", "Marlon (Ring of Honor)", "Ring of Honor: 1/1 · Về trả Marlon")
            return _result("Q2_FARM", "Marlon (Ring of Honor)", "Ring of Honor: 0/1")

        # Các class có Dark Stone / Combo tại Marlon (DK, Slayer, Illusion Knight, Crusader — hoặc bất kỳ class nào đang nhận Q3)
        if (cls_id in DARK_STONE_CLASSES or q3 == QUEST_STATE_ACCEPT) and q3 != QUEST_STATE_FINISH:
            if level < 220:
                return _result("NEED_LEVEL", "Marlon (Dark Stone)", f"Lv {level}/220", "Cần đạt Level 220 để làm NV Dark Stone")
            if q3 != QUEST_STATE_ACCEPT:
                if zen < 2_000_000:
                    return _result("NEED_ZEN", "Marlon (Dark Stone)", f"Zen {zen:,}/2M", "Cần tối thiểu 2.000.000 Zen cho NV Dark Stone")
                return _result("Q3_ACCEPT", "Marlon (Dark Stone)", "Chưa nhận NV (Marlon)")
            if has_dark_stone:
                return _result("Q3_COMPLETE", "Marlon (Dark Stone)", "Dark Stone: 1/1 · Về trả Marlon")
            return _result("Q3_FARM", "Marlon (Dark Stone)", "Dark Stone: 0/1")

    if mode == "marlon_only":
        return _result("DONE", "Đã xong Marlon", "Hoàn tất NV Marlon ✓")

    # --- 3. NHIỆM VỤ CẤP 3 (Priest Devin — Quest 4, 5, 6) ---
    if mode in ("all_2_3", "class3_only"):
        if change_up >= 2:
            return _result("DONE", "Đã đạt Cấp 3+", f"Hoàn tất {tier_text} ✓")

        if not is_special_no_c2 and change_up < 1:
            return _result("NEED_CLASS2", "Cần xong Cấp 2 trước", f"Hiện tại: {tier_text}", "Hãy chọn chế độ Cấp 2 + Cấp 3 hoặc làm Cấp 2 trước")

        # Quest 4: 3 nguyên liệu (Flame + Horn + Feather)
        if q4 != QUEST_STATE_FINISH:
            if level < c3_min_lv:
                return _result("NEED_LEVEL", "Cấp 3 (B1: 3 Nguyên liệu)", f"Lv {level}/{c3_min_lv}", f"Cần đạt Level {c3_min_lv} để làm NV Cấp 3")
            prog_q4 = f"F:{int(has_flame)} H:{int(has_horn)} P:{int(has_feather)}"
            if q4 != QUEST_STATE_ACCEPT:
                if zen < 5_000_000:
                    return _result("NEED_ZEN", "Cấp 3 (B1: 3 Nguyên liệu)", f"Zen {zen:,}/5M", "Cần tối thiểu 5.000.000 Zen cho Cấp 3 (B1)")
                return _result("Q4_ACCEPT", "Cấp 3 (B1: 3 Nguyên liệu)", f"Chưa nhận · {prog_q4}")
            if has_flame and has_horn and has_feather:
                return _result("Q4_COMPLETE", "Cấp 3 (B1: 3 Nguyên liệu)", f"{prog_q4} · Về trả Devin")
            if not has_flame:
                return _result("Q4_FARM_FLAME", "Cấp 3 (B1: Flame)", f"{prog_q4} · Farm Tarkan 2")
            if not has_horn:
                return _result("Q4_FARM_HORN", "Cấp 3 (B1: Horn)", f"{prog_q4} · Farm Aida 2")
            return _result("Q4_FARM_FEATHER", "Cấp 3 (B1: Feather)", f"{prog_q4} · Farm Icarus")

        # Quest 5: Barracks of Balgass (20 Balram + 20 Death Spirit + 20 Soram tại 3 khu riêng biệt)
        if q5 != QUEST_STATE_FINISH:
            if level < 400:
                return _result("NEED_LEVEL", "Cấp 3 (B2: Barracks)", f"Lv {level}/400", "Cần đạt Level 400 để làm NV Barracks")
            req_b = max(1, int(cfg.get("barracks_req_count", BARRACKS_REQ_COUNT) or BARRACKS_REQ_COUNT))
            prog_q5 = f"Bal:{k_balram}/{req_b} · DS:{k_death}/{req_b} · Sor:{k_soram}/{req_b}"
            if q5 != QUEST_STATE_ACCEPT:
                if zen < 7_000_000:
                    return _result("NEED_ZEN", "Cấp 3 (B2: Barracks)", f"Zen {zen:,}/7M", "Cần tối thiểu 7.000.000 Zen cho Cấp 3 (B2)")
                return _result("Q5_ACCEPT", "Cấp 3 (B2: Barracks)", "Chưa nhận (Priest Devin)")
            if k_balram >= req_b and k_death >= req_b and k_soram >= req_b:
                return _result("Q5_COMPLETE", "Cấp 3 (B2: Barracks)", f"{prog_q5} · Về trả Devin")
            return _result("Q5_FARM_BARRACKS", "Cấp 3 (B2: Barracks)", prog_q5)

        # Quest 6: Refuge of Balgass (1 Dark Elf)
        if q6 != QUEST_STATE_FINISH:
            if level < 400:
                return _result("NEED_LEVEL", "Cấp 3 (B3: Dark Elf)", f"Lv {level}/400", "Cần đạt Level 400 để vào Refuge")
            prog_q6 = f"Dark Elf: {k_darkelf}/1"
            if q6 != QUEST_STATE_ACCEPT:
                if zen < 10_000_000:
                    return _result("NEED_ZEN", "Cấp 3 (B3: Dark Elf)", f"Zen {zen:,}/10M", "Cần tối thiểu 10.000.000 Zen cho Cấp 3 (B3)")
                return _result("Q6_ACCEPT", "Cấp 3 (B3: Dark Elf)", "Chưa nhận (Priest Devin)")
            if k_darkelf >= 1:
                return _result("Q6_COMPLETE", "Cấp 3 (B3: Dark Elf)", f"{prog_q6} · Về trả Devin")
            return _result("Q6_FARM_REFUGE", "Cấp 3 (B3: Dark Elf)", prog_q6)

    return _result("DONE", "Hoàn tất tất cả NV", f"{tier_text} ✓")


# ==============================================================================
# WORKER TỰ ĐỘNG LÀM NHIỆM VỤ CHO TỪNG SLOT
# ==============================================================================

class QuestSlotRunner:
    """Điều phối chuỗi hành động tự động làm Nhiệm Vụ Cấp 2 / Marlon / Cấp 3 cho 1 SlotController."""

    def __init__(
        self,
        slot_idx: int,
        engine_getter: Callable[[], Any],
        config_getter: Callable[[], Dict[str, Any]],
        on_log: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[int, Dict[str, Any]], None]] = None,
        on_stop_train: Optional[Callable[[], None]] = None,
    ):
        self.slot_idx = int(slot_idx)
        self._get_engine = engine_getter
        self._get_config = config_getter
        self._on_log = on_log
        self._on_status = on_status
        self._on_stop_train = on_stop_train

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.running = False
        self.last_status_text = "Chờ lệnh"
        self.last_summary: Dict[str, Any] = {}

    def log(self, msg: str, level: str = "INFO"):
        if self._on_log:
            try:
                self._on_log(f"[Slot {self.slot_idx}] {msg}", level)
            except Exception:
                pass

    def _emit_status(self, status_text: str, summary: Optional[Dict[str, Any]] = None, color: str = "#cbd5e1"):
        self.last_status_text = status_text
        if summary is not None:
            self.last_summary = summary
        if self._on_status:
            try:
                self._on_status(
                    self.slot_idx,
                    {
                        "running": self.running,
                        "status_text": status_text,
                        "status_color": color,
                        "summary": self.last_summary,
                    },
                )
            except Exception:
                pass

    def start(self) -> bool:
        if self.running and self._thread and self._thread.is_alive():
            return False
        self._stop_event.clear()
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, name=f"QuestWorker-S{self.slot_idx}", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()
        self.running = False
        try:
            eng = self._get_engine()
            if eng and getattr(eng, "is_ready", False):
                eng.stop_helper()
        except Exception:
            pass
        self._emit_status("Đã dừng", color="#94a3b8")

    def _sleep(self, seconds: float) -> bool:
        """Ngủ theo từng lát 0.2s để dừng tức thì khi người dùng bấm Stop. Trả về False nếu bị dừng."""
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if self._stop_event.is_set():
                return False
            time.sleep(min(0.2, max(0.02, end - time.time())))
        return not self._stop_event.is_set()

    # ------------------------------------------------------------------
    # PRIMITIVES: WARP, MOVE, NPC TALK, QUEST ACTION, FARM & PICKUP
    # ------------------------------------------------------------------
    def _ensure_engine(self) -> Any:
        eng = self._get_engine()
        if not eng:
            return None
        if not getattr(eng, "is_ready", False):
            try:
                eng.attach()
                self._sleep(0.5)
            except Exception:
                return None
        return eng if getattr(eng, "is_ready", False) else None

    def _warp_to_map(self, eng: Any, map_cmd: str, target_map_id: int, timeout_s: float = 10.0) -> bool:
        info = eng.get_player_info() or {}
        if _read_map_id(info) == int(target_map_id):
            return True
        if not map_cmd:
            return False

        try:
            eng.stop_helper()
        except Exception:
            pass
        self._sleep(0.25)

        for attempt in range(3):
            if self._stop_event.is_set():
                return False
            self.log(f"Dịch chuyển: {map_cmd} (lần {attempt + 1}/3)")
            try:
                eng.send_chat(map_cmd)
            except Exception as e:
                self.log(f"Lỗi gửi lệnh {map_cmd}: {e}", "WARN")
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                if not self._sleep(0.4):
                    return False
                cur = eng.get_player_info(max_age=0.1) or {}
                if _read_map_id(cur) == int(target_map_id):
                    self._sleep(0.8)  # chờ map load xong entity/NPC
                    return True
        return False

    def _move_to_coord(
        self,
        eng: Any,
        tx: int,
        ty: int,
        arrive_dist: float = 3.5,
        timeout_s: float = 40.0,
        expected_map_id: Optional[int] = None,
        status_label: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        init_info = eng.get_player_info(max_age=0.15) or {}
        if expected_map_id is not None and _read_map_id(init_info) != int(expected_map_id):
            return False
        ix0, iy0 = _read_xy(init_info)
        init_dist = math.hypot(tx - ix0, ty - iy0)
        if init_dist <= arrive_dist:
            try:
                eng.stop_auto_move()
            except Exception:
                pass
            return True

        # Tự co giãn timeout theo khoảng cách thực tế (VD: Icarus cổng 15,13 -> Phoenix 37,238 cách ~226 ô cần ~120-220s)
        eff_timeout = max(float(timeout_s), min(240.0, init_dist * 1.15 + 45.0))
        deadline = time.time() + eff_timeout
        last_issue = 0.0
        last_status_emit = 0.0
        has_auto_move_check = hasattr(eng, "is_auto_move_active")
        while time.time() < deadline:
            if self._stop_event.is_set():
                return False
            info = eng.get_player_info(max_age=0.15) or {}
            if expected_map_id is not None and _read_map_id(info) != int(expected_map_id):
                return False
            px, py = _read_xy(info)
            dist = math.hypot(tx - px, ty - py)
            if dist <= arrive_dist:
                try:
                    eng.stop_auto_move()
                except Exception:
                    pass
                return True

            now = time.time()
            moving_now = False
            if has_auto_move_check:
                try:
                    moving_now = bool(eng.is_auto_move_active())
                except Exception:
                    moving_now = False
            # Đang chạy Auto Move mượt trên cầu dài (Icarus) chỉ refresh nhẹ mỗi 5s; nếu bị ngắt thì gọi lại sau 1.4s
            reissue_gap = 5.0 if moving_now else (1.4 if has_auto_move_check else 2.2)
            if last_issue == 0.0 or (now - last_issue) >= reissue_gap:
                try:
                    eng.start_auto_move(int(tx), int(ty), helper=False)
                except Exception:
                    try:
                        eng.move_to(int(tx), int(ty))
                    except Exception:
                        pass
                last_issue = now

            if status_label and (now - last_status_emit) >= 2.0:
                self._emit_status(
                    f"{status_label} ({px},{py}) -> ({tx},{ty}) [còn {int(dist)} ô]",
                    summary,
                    color="#38bdf8",
                )
                last_status_emit = now

            if not self._sleep(0.45):
                return False
        return False

    def _wait_quest_window_open(self, eng: Any, timeout_s: float = 5.0) -> Dict[str, Any]:
        """Chờ nhân vật chạy tới sát NPC và cửa sổ MQuestNpcWindow thực sự mở ra trước khi bấm Accept/Continue."""
        deadline = time.time() + timeout_s
        last_w = {"ok": False, "isOpen": False, "hasNextBtn": False, "currentData": -1}
        while time.time() < deadline:
            if self._stop_event.is_set():
                return last_w
            if hasattr(eng, "get_quest_npc_window_state"):
                last_w = eng.get_quest_npc_window_state() or last_w
                if last_w.get("isOpen"):
                    return last_w
            else:
                return {"ok": True, "isOpen": True, "hasNextBtn": True, "currentData": -1}
            if not self._sleep(0.25):
                return last_w
        return last_w

    def _click_accept_or_continue(self, eng: Any, quest_index: int, expected_state: int, action_label: str) -> bool:
        """Bấm nút Accept / Continue trên MQuestNpcWindow (tối đa 2 nhịp nếu hội thoại nhiều bước) rồi xác nhận RAM."""
        for click_step in range(2):
            if self._stop_event.is_set():
                return False
            if hasattr(eng, "click_quest_npc_next"):
                res = eng.click_quest_npc_next(quest_index) or {}
                self.log(
                    f"Bấm nút NV #{quest_index} ({action_label}, nhịp {click_step + 1}): "
                    f"ok={res.get('ok')} via={res.get('method') or 'none'} "
                    f"winOpen={res.get('qWinOpen')} curData={res.get('currentData')}"
                    + (f" err={res.get('error')}" if res.get("error") else ""),
                    "INFO",
                )
            else:
                eng.send_quest_state(quest_index, True)

            if not self._sleep(1.15):
                return False

            snap = eng.get_quest_state() or {}
            st = get_quest_bit_state(snap.get("states") or {}, quest_index)
            if st == expected_state:
                try:
                    eng.close_quest_window()
                except Exception:
                    pass
                self.log(f"✓ Thành công: NV #{quest_index} -> {QUEST_STATE_LABELS.get(st, st)}", "SUCCESS")
                return True

            # Nếu cửa sổ vẫn còn mở (ví dụ nút chuyển từ Accept -> Continue), tiếp tục nhịp 2; nếu đóng rồi thì thoát vòng nhịp
            if hasattr(eng, "get_quest_npc_window_state"):
                w_st = eng.get_quest_npc_window_state() or {}
                if not w_st.get("isOpen"):
                    break
        return False

    def _interact_npc_and_send_quest(
        self,
        eng: Any,
        npc_cfg: Dict[str, Any],
        quest_index: int,
        expected_state: int,
        action_label: str,
    ) -> bool:
        map_cmd = str(npc_cfg.get("map_cmd", ""))
        map_id = int(npc_cfg.get("map_id", -1))
        nx = int(npc_cfg.get("x", 0))
        ny = int(npc_cfg.get("y", 0))
        skin = int(npc_cfg.get("skin", -1))
        name_sub = str(npc_cfg.get("name", ""))

        self._emit_status(f"Đi tới {name_sub} ({action_label})", color="#38bdf8")
        if map_id >= 0 and not self._warp_to_map(eng, map_cmd, map_id):
            self.log(f"Không thể dịch chuyển tới map của NPC {name_sub} ({map_cmd}).", "ERROR")
            return False

        if not self._move_to_coord(eng, nx, ny, arrive_dist=3.0, timeout_s=45.0, expected_map_id=map_id):
            self.log(f"Chưa tới được tọa độ NPC {name_sub} ({nx}, {ny}).", "WARN")

        # Quét NPC trong Viewport -> nói chuyện -> CHỜ MQuestNpcWindow mở -> bấm thật nút Accept/Continue!
        for attempt in range(4):
            if self._stop_event.is_set():
                return False
            npc = eng.find_npc_by_filter(skin_id=skin, name_sub=name_sub) or {}
            if npc.get("found"):
                # Tiến sát lại NPC <= 2.5 ô để mở hội thoại tức thì (tránh độ trễ tự chạy bộ)
                if float(npc.get("dist", 0)) > 2.8:
                    self._move_to_coord(eng, int(npc.get("x", nx)), int(npc.get("y", ny)), arrive_dist=2.5, timeout_s=15.0)
                self.log(f"Mở hội thoại NPC {npc.get('name') or name_sub} cho NV #{quest_index} ({action_label})...")
                eng.talk_to_npc_by_ptr(npc.get("ptr"))
                w_state = self._wait_quest_window_open(eng, timeout_s=4.5)
                if not w_state.get("isOpen"):
                    self.log(f"Cửa sổ NPC {name_sub} chưa mở sau 4.5s, thử gửi trực tiếp lệnh NV #{quest_index}...", "WARN")
                if self._click_accept_or_continue(eng, quest_index, expected_state, action_label):
                    return True
                try:
                    eng.close_quest_window()
                except Exception:
                    pass
                snap = eng.get_quest_state() or {}
                st = get_quest_bit_state(snap.get("states") or {}, quest_index)
                self.log(
                    f"Chưa thấy trạng thái NV #{quest_index} chuyển sang {QUEST_STATE_LABELS.get(expected_state)} "
                    f"(hiện tại={QUEST_STATE_LABELS.get(st, st)}, CurrentData={snap.get('current_data', -1)}, thử lại {attempt + 1}/4)...",
                    "WARN",
                )
            else:
                self.log(f"Đang tìm NPC {name_sub} quanh ({nx}, {ny}) (lần {attempt + 1}/4)...", "WARN")
                self._move_to_coord(eng, nx, ny, arrive_dist=2.5, timeout_s=10.0)
            if not self._sleep(1.0):
                return False
        return False

    def _find_and_interact_marlon(self, eng: Any, cfg: Dict[str, Any], quest_index: int, expected_state: int, action_label: str) -> bool:
        """Marlon trên MegaMU cố định 1 vị trí tại Devias ngay cạnh NPC nhiệm vụ Cấp 2 (Sebina)."""
        marlon_cfg = (cfg.get("npcs") or {}).get("marlon") or DEFAULT_QUEST_CONFIG["npcs"]["marlon"]
        return self._interact_npc_and_send_quest(eng, marlon_cfg, quest_index, expected_state, action_label)

    def _enter_barracks(self, eng: Any, cfg: Dict[str, Any]) -> bool:
        info = eng.get_player_info() or {}
        if _read_map_id(info) == MAP_BARRACKS:
            return True
        ww = (cfg.get("npcs") or {}).get("werewolf") or DEFAULT_QUEST_CONFIG["npcs"]["werewolf"]
        self._emit_status("Tới Werewolf Quarrel vào Barracks", color="#38bdf8")
        if not self._warp_to_map(eng, str(ww.get("map_cmd", "/move crywolf")), MAP_CRYWOLF):
            return False
        self._move_to_coord(eng, int(ww.get("x", 62)), int(ww.get("y", 239)), arrive_dist=4.5, timeout_s=60.0, expected_map_id=MAP_CRYWOLF)
        for attempt in range(4):
            if self._stop_event.is_set():
                return False
            npc = eng.find_npc_by_filter(skin_id=NPC_WEREWOLF_QUARREL, name_sub="Werewolf") or {}
            if npc.get("found"):
                eng.talk_to_npc_by_ptr(npc.get("ptr"))
                self._sleep(0.5)
            eng.enter_quest_dungeon("barracks")
            deadline = time.time() + 6.0
            while time.time() < deadline:
                if not self._sleep(0.4):
                    return False
                cur = eng.get_player_info(max_age=0.1) or {}
                if _read_map_id(cur) == MAP_BARRACKS:
                    self.log("✓ Đã vào Barracks of Balgass!", "SUCCESS")
                    self._sleep(1.0)
                    return True
            self.log(f"Đang thử lại vào Barracks (lần {attempt + 1}/4)...", "WARN")
        return False

    def _enter_refuge(self, eng: Any, cfg: Dict[str, Any]) -> bool:
        info = eng.get_player_info() or {}
        if _read_map_id(info) == MAP_REFUGE:
            return True
        if _read_map_id(info) != MAP_BARRACKS:
            if not self._enter_barracks(eng, cfg):
                return False
        gk = (cfg.get("npcs") or {}).get("gatekeeper") or DEFAULT_QUEST_CONFIG["npcs"]["gatekeeper"]
        self._emit_status("Đi tới Gatekeeper vào Refuge", color="#38bdf8")
        self._move_to_coord(eng, int(gk.get("x", 119)), int(gk.get("y", 168)), arrive_dist=4.5, timeout_s=65.0, expected_map_id=MAP_BARRACKS)
        for attempt in range(4):
            if self._stop_event.is_set():
                return False
            npc = eng.find_npc_by_filter(skin_id=NPC_GATEKEEPER, name_sub="Gatekeeper") or {}
            if npc.get("found"):
                eng.talk_to_npc_by_ptr(npc.get("ptr"))
                self._sleep(0.5)
            eng.enter_quest_dungeon("refuge")
            deadline = time.time() + 6.0
            while time.time() < deadline:
                if not self._sleep(0.4):
                    return False
                cur = eng.get_player_info(max_age=0.1) or {}
                if _read_map_id(cur) == MAP_REFUGE:
                    self.log("✓ Đã vào Refuge of Balgass!", "SUCCESS")
                    self._sleep(1.0)
                    return True
            self.log(f"Đang thử lại vào Refuge (lần {attempt + 1}/4)...", "WARN")
        return False

    def _farm_until_item(
        self,
        eng: Any,
        cfg: Dict[str, Any],
        spot_key: str,
        item_id: int,
        label: str,
        item_level: Optional[int] = None,
        pickup_ids: Optional[List[int]] = None,
        name_keywords: Optional[Tuple[str, ...]] = None,
        extra_ids: Optional[Tuple[int, ...]] = None,
    ) -> bool:
        spot = (cfg.get("spots") or {}).get(spot_key) or DEFAULT_QUEST_CONFIG["spots"][spot_key]
        map_cmd = str(spot.get("map_cmd", ""))
        map_id = int(spot.get("map_id", -1))
        sx = int(spot.get("x", 0))
        sy = int(spot.get("y", 0))
        auto_pickup = bool(cfg.get("auto_pickup_quest_items", True))
        timeout_s = max(60.0, float(cfg.get("farm_timeout_min", 45) or 45) * 60.0)
        want_pick_ids = list(pickup_ids) if pickup_ids else [item_id]

        self.log(f"Bắt đầu farm [{label}] tại {spot.get('label', map_cmd)} ({sx}, {sy})")
        start_ts = time.time()
        did_subwarp = False
        can_subwarp = _is_subzone_warp_cmd(map_cmd)

        while not self._stop_event.is_set():
            if time.time() - start_ts > timeout_s:
                self.log(f"Quá thời gian farm [{label}] ({int(timeout_s // 60)} phút), tạm dừng kiểm tra lại.", "WARN")
                return False

            snap = eng.get_quest_state() or {}
            summary = summarize_quest_snapshot(snap, cfg)
            if has_quest_item(
                snap.get("quest_items") or [],
                item_id,
                item_level=item_level,
                name_keywords=name_keywords,
                extra_ids=extra_ids,
            ):
                try:
                    eng.stop_helper()
                except Exception:
                    pass
                self.log(f"✓ Đã nhặt được [{label}]!", "SUCCESS")
                self._emit_status(f"Đã có {label}!", summary, color="#22c55e")
                return True

            cur_map = _read_map_id(snap)
            px, py = _read_xy(snap)
            dist_to_spot = math.hypot(sx - px, sy - py)

            if map_id >= 0 and cur_map != map_id:
                did_subwarp = False
                self._emit_status(f"Warp tới {spot.get('label', map_cmd)} ({sx},{sy})", summary, color="#38bdf8")
                if not self._warp_to_map(eng, map_cmd, map_id):
                    self._sleep(2.0)
                    continue
                arrived = self._move_to_coord(
                    eng, sx, sy, arrive_dist=4.5, timeout_s=60.0, expected_map_id=map_id,
                    status_label=f"Chạy tới bãi {label}", summary=summary,
                )
                if arrived:
                    eng.start_helper(sx, sy, force_restart=True)
                else:
                    self.log(f"Chưa tới bãi [{label}] ({sx},{sy}) sau lượt di chuyển đầu, tiếp tục chạy tới bãi (không warp lại).", "WARN")
                    continue
            elif dist_to_spot > 48.0 and can_subwarp and not did_subwarp:
                # CHỈ warp chuyển tầng 1 lần duy nhất cho map có nhiều phân khu cùng Map ID (Lost 1->7, Tarkan 1->2, Aida 1->2)
                # Tuyệt đối KHÔNG gửi lại /move icarus khi đã ở Icarus (1 cổng duy nhất, bãi Phoenix cách cổng ~226 ô!)
                did_subwarp = True
                self._emit_status(f"Dịch chuyển {map_cmd} -> ({sx},{sy})", summary, color="#38bdf8")
                try:
                    eng.stop_helper()
                except Exception:
                    pass
                self.log(f"Cùng map #{cur_map} nhưng cách bãi {int(dist_to_spot)} ô -> gửi {map_cmd} (1 lần) tới đúng khu vực.")
                try:
                    eng.send_chat(map_cmd)
                except Exception:
                    pass
                self._sleep(1.5)
                arrived = self._move_to_coord(
                    eng, sx, sy, arrive_dist=4.5, timeout_s=60.0, expected_map_id=map_id,
                    status_label=f"Chạy tới bãi {label}", summary=summary,
                )
                if arrived:
                    eng.start_helper(sx, sy, force_restart=True)
                else:
                    self.log(f"Chưa tới bãi [{label}] ({sx},{sy}) sau khi chuyển tầng, tiếp tục đi bộ tới bãi.", "WARN")
                    continue
            elif dist_to_spot > 18.0:
                self._emit_status(f"Chạy tới bãi {label} ({px},{py}) -> ({sx},{sy})", summary, color="#f59e0b")
                try:
                    eng.stop_helper()
                except Exception:
                    pass
                arrived = self._move_to_coord(
                    eng, sx, sy, arrive_dist=4.5, timeout_s=60.0, expected_map_id=map_id,
                    status_label=f"Chạy tới bãi {label}", summary=summary,
                )
                if arrived:
                    eng.start_helper(sx, sy, force_restart=True)
                else:
                    self.log(f"Đang tiến về bãi [{label}] ({sx},{sy}), chưa bật Helper khi chưa tới bãi.", "WARN")
                    continue
            else:
                if not eng.is_helper_active():
                    eng.start_helper(sx, sy, force_restart=False)
                self._emit_status(f"Đang farm {label} ({px},{py}) -> ({sx},{sy})", summary, color="#2dd4bf")

            # Chủ động quét & nhặt ĐÚNG Quest Item rơi trên đất (lọc chặt theo ID + Level + tên riêng)
            if auto_pickup:
                try:
                    kw_list = list(name_keywords) if name_keywords else []
                    pick = eng.pickup_ground_quest_items(
                        want_pick_ids, max_radius=14.0, item_level=item_level, keywords=kw_list
                    ) or {}
                    if int(pick.get("pickedCount", 0)) > 0:
                        self.log(f"✓ Đã tự động nhặt vật phẩm NV [{label}] trên đất!", "SUCCESS")
                    else:
                        found_items = pick.get("foundItems") or []
                        if found_items:
                            nearest = min(found_items, key=lambda it: float(it.get("dist", 99.0)))
                            ix, iy = int(nearest.get("x", 0)), int(nearest.get("y", 0))
                            idist = float(nearest.get("dist", 0.0))
                            if ix > 0 and iy > 0 and idist > 3.0:
                                self.log(f"Phát hiện [{nearest.get('name') or label}] rơi tại ({ix}, {iy}) cách {idist:.1f} ô -> chạy lại nhặt!", "INFO")
                                self._emit_status(f"Chạy nhặt {label} ({ix},{iy})", summary, color="#22c55e")
                                try:
                                    eng.stop_helper()
                                except Exception:
                                    pass
                                self._move_to_coord(eng, ix, iy, arrive_dist=2.2, timeout_s=10.0, expected_map_id=map_id)
                                pick2 = eng.pickup_ground_quest_items(
                                    want_pick_ids, max_radius=5.0, item_level=item_level, keywords=kw_list
                                ) or {}
                                if int(pick2.get("pickedCount", 0)) > 0:
                                    self.log(f"✓ Đã chạy tới nhặt xong [{nearest.get('name') or label}]!", "SUCCESS")
                except Exception:
                    pass

            if not self._sleep(1.3):
                return False
        return False

    def _farm_barracks(self, eng: Any, cfg: Dict[str, Any]) -> bool:
        timeout_s = max(60.0, float(cfg.get("farm_timeout_min", 45) or 45) * 60.0)
        req_b = max(1, int(cfg.get("barracks_req_count", BARRACKS_REQ_COUNT) or BARRACKS_REQ_COUNT))
        start_ts = time.time()
        active_spot_key: Optional[str] = None
        patrol_idx = 0
        last_mob_kills = -1
        last_kill_ts = time.time()

        while not self._stop_event.is_set():
            if time.time() - start_ts > timeout_s:
                self.log("Quá thời gian farm Barracks, tạm dừng.", "WARN")
                return False

            snap = eng.get_quest_state() or {}
            summary = summarize_quest_snapshot(snap, cfg)
            kills = snap.get("monster_kills") or {}

            # Tìm loại quái chưa đủ số lượng (mặc định 20/20/20 tại 3 khu riêng biệt)
            target_mob = None
            for z_idx, (mob_id, mob_name, _default_req, spot_key) in enumerate(BARRACKS_MONSTERS, start=1):
                if get_monster_kill_count(kills, mob_id) < req_b:
                    target_mob = (z_idx, mob_id, mob_name, req_b, spot_key)
                    break

            if target_mob is None:
                try:
                    eng.stop_helper()
                except Exception:
                    pass
                self.log(
                    f"✓ Đã hạ đủ {req_b} Balram + {req_b} Death Spirit + {req_b} Soram tại 3 khu Barracks!",
                    "SUCCESS",
                )
                self._emit_status("Đủ quái Barracks · Về trả Devin", summary, color="#22c55e")
                return True

            z_idx, mob_id, mob_name, req_cnt, spot_key = target_mob
            cur_cnt = get_monster_kill_count(kills, mob_id)
            spot = (cfg.get("spots") or {}).get(spot_key) or DEFAULT_QUEST_CONFIG["spots"][spot_key]
            base_sx, base_sy = int(spot.get("x", 51)), int(spot.get("y", 137))

            # Danh sách điểm trong khu vực: luôn ưu tiên tọa độ user cấu hình đầu tiên, kèm điểm tuần tra dự phòng
            patrol_pts: List[Tuple[int, int]] = [(base_sx, base_sy)]
            for pt in BARRACKS_ZONE_PATROL.get(spot_key, []):
                if math.hypot(pt[0] - base_sx, pt[1] - base_sy) >= 8.0:
                    patrol_pts.append(pt)

            zone_switched = (active_spot_key != spot_key)
            if zone_switched:
                active_spot_key = spot_key
                patrol_idx = 0
                last_mob_kills = cur_cnt
                last_kill_ts = time.time()
                self.log(
                    f"→ Chuyển sang Khu {z_idx}/3 Barracks [{mob_name}] ({base_sx}, {base_sy}) · hiện có {cur_cnt}/{req_cnt}",
                    "INFO",
                )
            elif cur_cnt != last_mob_kills:
                last_mob_kills = cur_cnt
                last_kill_ts = time.time()
            elif len(patrol_pts) > 1 and (time.time() - last_kill_ts) >= 45.0:
                # Đứng quá 45s không tăng số kill của loại quái mục tiêu -> dịch chuyển sang điểm kế tiếp trong khu vực đó
                patrol_idx = (patrol_idx + 1) % len(patrol_pts)
                last_kill_ts = time.time()
                nx_pt, ny_pt = patrol_pts[patrol_idx]
                self.log(
                    f"Khu {z_idx}/3 [{mob_name}] chưa tăng kill sau 45s -> dịch chuyển tìm bãi ({nx_pt}, {ny_pt})",
                    "INFO",
                )
                zone_switched = True

            sx, sy = patrol_pts[patrol_idx % len(patrol_pts)]

            if _read_map_id(snap) != MAP_BARRACKS:
                if not self._enter_barracks(eng, cfg):
                    self._sleep(2.0)
                    continue
                if self._move_to_coord(
                    eng, sx, sy, arrive_dist=4.5, timeout_s=90.0, expected_map_id=MAP_BARRACKS,
                    status_label=f"Chạy sang Khu {z_idx}/3 ({mob_name})", summary=summary,
                ):
                    eng.start_helper(sx, sy, force_restart=True)
                    last_kill_ts = time.time()
            else:
                px, py = _read_xy(snap)
                need_move = zone_switched or (math.hypot(sx - px, sy - py) > 8.0)
                if need_move:
                    try:
                        eng.stop_helper()
                    except Exception:
                        pass
                    self._emit_status(f"Chạy sang Khu {z_idx}/3: {mob_name} ({sx},{sy})", summary, color="#38bdf8")
                    if self._move_to_coord(
                        eng, sx, sy, arrive_dist=4.5, timeout_s=90.0, expected_map_id=MAP_BARRACKS,
                        status_label=f"Chạy sang Khu {z_idx}/3 ({mob_name})", summary=summary,
                    ):
                        eng.start_helper(sx, sy, force_restart=True)
                        last_kill_ts = time.time()
                else:
                    if not eng.is_helper_active():
                        eng.start_helper(sx, sy, force_restart=False)
                    self._emit_status(f"Barracks Khu {z_idx}/3: {mob_name} {cur_cnt}/{req_cnt}", summary, color="#2dd4bf")

            if not self._sleep(2.0):
                return False
        return False

    def _farm_refuge_dark_elf(self, eng: Any, cfg: Dict[str, Any]) -> bool:
        timeout_s = max(60.0, float(cfg.get("farm_timeout_min", 45) or 45) * 60.0)
        start_ts = time.time()
        spot = (cfg.get("spots") or {}).get("refuge_dark_elf") or DEFAULT_QUEST_CONFIG["spots"]["refuge_dark_elf"]
        sx, sy = int(spot.get("x", 96)), int(spot.get("y", 175))

        while not self._stop_event.is_set():
            if time.time() - start_ts > timeout_s:
                self.log("Quá thời gian đánh Dark Elf (Refuge), tạm dừng.", "WARN")
                return False

            snap = eng.get_quest_state() or {}
            summary = summarize_quest_snapshot(snap, cfg)
            if get_monster_kill_count(snap.get("monster_kills") or {}, MONSTER_DARK_ELF) >= 1:
                try:
                    eng.stop_helper()
                except Exception:
                    pass
                self.log("✓ Đã hạ gục Dark Elf tại Refuge of Balgass!", "SUCCESS")
                self._emit_status("Hạ xong Dark Elf · Về trả Devin", summary, color="#22c55e")
                return True

            if _read_map_id(snap) != MAP_REFUGE:
                if not self._enter_refuge(eng, cfg):
                    self._sleep(2.0)
                    continue
                if self._move_to_coord(
                    eng, sx, sy, arrive_dist=4.5, timeout_s=55.0, expected_map_id=MAP_REFUGE,
                    status_label="Chạy tới Dark Elf", summary=summary,
                ):
                    eng.start_helper(sx, sy, force_restart=True)
            else:
                px, py = _read_xy(snap)
                if math.hypot(sx - px, sy - py) > 18.0:
                    try:
                        eng.stop_helper()
                    except Exception:
                        pass
                    if self._move_to_coord(
                        eng, sx, sy, arrive_dist=4.5, timeout_s=55.0, expected_map_id=MAP_REFUGE,
                        status_label="Chạy tới Dark Elf", summary=summary,
                    ):
                        eng.start_helper(sx, sy, force_restart=True)
                else:
                    if not eng.is_helper_active():
                        eng.start_helper(sx, sy, force_restart=False)
                    self._emit_status("Đang đánh Dark Elf (Refuge)", summary, color="#2dd4bf")

            if not self._sleep(2.0):
                return False
        return False

    # ------------------------------------------------------------------
    # MAIN STATE MACHINE LOOP
    # ------------------------------------------------------------------
    def _run_loop(self):
        try:
            if self._on_stop_train:
                try:
                    self._on_stop_train()
                except Exception:
                    pass

            self.log("Bắt đầu Auto Nhiệm Vụ Cấp 2 / Cấp 3...", "INFO")
            self._emit_status("Đang đọc trạng thái NV...", color="#38bdf8")

            while not self._stop_event.is_set():
                eng = self._ensure_engine()
                if not eng:
                    self.log("Chưa kết nối được game cho slot này.", "ERROR")
                    self._emit_status("Chưa kết nối game", color="#ef4444")
                    break

                cfg = self._get_config() or DEFAULT_QUEST_CONFIG
                snap = eng.get_quest_state() or {}
                summary = summarize_quest_snapshot(snap, cfg)
                action = summary.get("next_action", "DONE")
                self._emit_status(summary.get("current_quest_label", action), summary, color="#38bdf8")

                if action == "DONE":
                    try:
                        eng.stop_helper()
                    except Exception:
                        pass
                    self.log(f"🎉 Hoàn tất chuỗi nhiệm vụ: {summary.get('progress_text', '')}", "SUCCESS")
                    self._emit_status("Hoàn tất ✓", summary, color="#22c55e")
                    break

                if action in ("NEED_LEVEL", "NEED_ZEN", "NEED_CLASS2", "NOT_CONNECTED"):
                    reason = summary.get("reason") or summary.get("progress_text") or action
                    self.log(f"⏸ Dừng: {reason}", "WARN")
                    self._emit_status(reason, summary, color="#f59e0b")
                    break

                npcs = cfg.get("npcs") or DEFAULT_QUEST_CONFIG["npcs"]
                sebina = npcs.get("sebina") or DEFAULT_QUEST_CONFIG["npcs"]["sebina"]
                devin = npcs.get("devin") or DEFAULT_QUEST_CONFIG["npcs"]["devin"]

                # --- CLASS 2 (SEBINA) ---
                if action == "Q0_ACCEPT":
                    ok = self._interact_npc_and_send_quest(eng, sebina, 0, QUEST_STATE_ACCEPT, "Nhận NV Cấp 2 B1")
                elif action == "Q0_FARM":
                    ok = self._farm_until_item(
                        eng, cfg, "scroll_emperor", ITEM_SCROLL_OF_EMPEROR, "Scroll of Emperor",
                        item_level=0, name_keywords=("scroll of emperor",),
                    )
                elif action == "Q0_COMPLETE":
                    ok = self._interact_npc_and_send_quest(eng, sebina, 0, QUEST_STATE_FINISH, "Trả NV Cấp 2 B1")
                elif action == "Q1_ACCEPT":
                    ok = self._interact_npc_and_send_quest(eng, sebina, 1, QUEST_STATE_ACCEPT, "Nhận NV Cấp 2 B2")
                elif action == "Q1_FARM":
                    p2_id, p2_lv, p2_lbl, p2_kws = get_class2_part2_spec(int(summary.get("class_id", -1)))
                    ok = self._farm_until_item(
                        eng, cfg, "class2_part2", p2_id, p2_lbl,
                        item_level=p2_lv,
                        pickup_ids=[p2_id],
                        name_keywords=p2_kws,
                    )
                elif action == "Q1_COMPLETE":
                    ok = self._interact_npc_and_send_quest(eng, sebina, 1, QUEST_STATE_FINISH, "Trả NV Cấp 2 B2")

                # --- MARLON Lv220 ---
                elif action == "Q2_ACCEPT":
                    ok = self._find_and_interact_marlon(eng, cfg, 2, QUEST_STATE_ACCEPT, "Nhận Ring of Honor")
                elif action == "Q2_FARM":
                    ok = self._farm_until_item(
                        eng, cfg, "ring_of_honor", ITEM_RING_OF_HONOR, "Ring of Honor",
                        item_level=1, name_keywords=("ring of honor",),
                    )
                elif action == "Q2_COMPLETE":
                    ok = self._find_and_interact_marlon(eng, cfg, 2, QUEST_STATE_FINISH, "Trả Ring of Honor")
                elif action == "Q3_ACCEPT":
                    ok = self._find_and_interact_marlon(eng, cfg, 3, QUEST_STATE_ACCEPT, "Nhận Dark Stone")
                elif action == "Q3_FARM":
                    ok = self._farm_until_item(
                        eng, cfg, "dark_stone", ITEM_DARK_STONE, "Dark Stone",
                        item_level=1, name_keywords=("dark stone",),
                    )
                elif action == "Q3_COMPLETE":
                    ok = self._find_and_interact_marlon(eng, cfg, 3, QUEST_STATE_FINISH, "Trả Dark Stone")

                # --- CLASS 3 (PRIEST DEVIN + BARRACKS + REFUGE) ---
                elif action == "Q4_ACCEPT":
                    ok = self._interact_npc_and_send_quest(eng, devin, 4, QUEST_STATE_ACCEPT, "Nhận NV Cấp 3 B1")
                elif action == "Q4_FARM_FLAME":
                    ok = self._farm_until_item(
                        eng, cfg, "flame_death_beam", ITEM_FLAME_DEATH_BEAM, "Flame of Death Beam Knight",
                        name_keywords=("flame of death",),
                    )
                elif action == "Q4_FARM_HORN":
                    ok = self._farm_until_item(
                        eng, cfg, "horn_hell_maine", ITEM_HORN_HELL_MAINE, "Horn of Hell Maine",
                        name_keywords=("horn of hell",),
                    )
                elif action == "Q4_FARM_FEATHER":
                    ok = self._farm_until_item(
                        eng, cfg, "feather_phoenix", ITEM_FEATHER_PHOENIX, "Feather of Dark Phoenix",
                        name_keywords=("feather of", "phoenix"),
                    )
                elif action == "Q4_COMPLETE":
                    ok = self._interact_npc_and_send_quest(eng, devin, 4, QUEST_STATE_FINISH, "Trả NV Cấp 3 B1")
                elif action == "Q5_ACCEPT":
                    ok = self._interact_npc_and_send_quest(eng, devin, 5, QUEST_STATE_ACCEPT, "Nhận NV Barracks")
                elif action == "Q5_FARM_BARRACKS":
                    ok = self._farm_barracks(eng, cfg)
                elif action == "Q5_COMPLETE":
                    ok = self._interact_npc_and_send_quest(eng, devin, 5, QUEST_STATE_FINISH, "Trả NV Barracks")
                elif action == "Q6_ACCEPT":
                    ok = self._interact_npc_and_send_quest(eng, devin, 6, QUEST_STATE_ACCEPT, "Nhận NV Refuge")
                elif action == "Q6_FARM_REFUGE":
                    ok = self._farm_refuge_dark_elf(eng, cfg)
                elif action == "Q6_COMPLETE":
                    ok = self._interact_npc_and_send_quest(eng, devin, 6, QUEST_STATE_FINISH, "Trả NV Cấp 3 (Thăng Cấp!)")
                else:
                    self.log(f"Trạng thái không xác định: {action}", "WARN")
                    break

                if not ok and not self._stop_event.is_set():
                    self.log(f"Bước [{action}] chưa hoàn tất, thử kiểm tra lại sau 3 giây...", "WARN")
                    if not self._sleep(3.0):
                        break
                else:
                    if not self._sleep(0.8):
                        break
        except Exception as exc:
            self.log(f"Lỗi ngoài ý muốn trong Auto Quest: {exc}", "ERROR")
            self._emit_status(f"Lỗi: {exc}", color="#ef4444")
        finally:
            self.running = False
            if self._stop_event.is_set():
                self._emit_status("Đã dừng", color="#94a3b8")
