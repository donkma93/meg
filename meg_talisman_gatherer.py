#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Talisman Gatherer — Gom Bùa Luck (7221) & Bùa Chaos Assembly (7264)
==========================================================================
Kết hợp đầy đủ 2 hướng xử lý chuẩn xác theo cấu trúc RAM thực tế của MEGAMU:
  - Hướng A (Gom chồng / Stack):
      Đọc trực tiếp ItemStackInfo ([item + 0x58] -> [+0x118] -> MaxStack +0x10)
      và số lượng thật ([item + 0x64] / +0x6C) từ RAM. Tự động gộp chồng Talisman of Luck
      (và Talisman of Chaos Assembly nếu server cho phép stack) trong Hòm đồ & Kho đồ
      qua gói C1:24 đúng chuẩn MaxStack của server.
  - Hướng B (Gom tập trung về Kho đồ / Vault):
      1. Tùy chọn lôi riêng Talisman of Luck & Talisman of Chaos Assembly từ Thùng đồ K
         (Gremory Case) ra Hòm đồ nhân vật.
      2. Dịch chuyển về thành (Lorencia / Noria / Devias), tìm NPC Thủ Kho (Vault Keeper skin 240),
         gửi lệnh đổi kho `/bau N` (nếu cài đặt), mở Kho đồ qua C1:30.
      3. Cất gọn toàn bộ Bùa Chaos Assembly & Bùa Luck vào Kho chính (0..119) / Kho mở rộng (120..239),
         ưu tiên gộp chồng vào ô sẵn có nếu stackable và chọn ô trống 100% không trùng lắp.
      4. Đóng Kho đồ (C1:31) sạch sẽ.
"""

import copy
import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# Định danh chuẩn MU Online / MEGAMU (Section 14)
TALISMAN_LUCK_ID = 7221            # Section 14, Index 53 -> Talisman of Luck
TALISMAN_CHAOS_ASSEMBLY_ID = 7264  # Section 14, Index 96 -> Talisman of Chaos Assembly
ELEMENTAL_LUCK_ID = 7357           # Section 14, Index 189 -> Elemental Talisman of Luck (non-stackable)
ELEMENTAL_CHAOS_ID = 7358          # Section 14, Index 190 -> Elemental Talisman of Chaos (non-stackable)

VAULT_KEEPER_SKIN = 240            # NPC Vault Keeper / Thủ Kho

MAP_LORENCIA = 0
MAP_DEVIAS = 2
MAP_NORIA = 3

# Vị trí NPC Thủ Kho (Vault Keeper - skin 240) tại 3 thành chính
VAULT_NPC_CATALOG: Dict[str, Dict[str, Any]] = {
    "lorencia": {
        "label": "Lorencia",
        "map_id": MAP_LORENCIA,
        "map_cmd": "/m lorencia",
        "npc_pos": (147, 145),
        "waypoints": [(147, 145), (146, 110)],
    },
    "noria": {
        "label": "Noria",
        "map_id": MAP_NORIA,
        "map_cmd": "/m noria",
        "npc_pos": (172, 96),
        "waypoints": [(172, 96), (174, 108)],
    },
    "devias": {
        "label": "Devias",
        "map_id": MAP_DEVIAS,
        "map_cmd": "/m devias",
        "npc_pos": (218, 63),
        "waypoints": [(218, 63), (210, 50)],
    },
}

MAP_ID_TO_TOWN: Dict[int, str] = {
    MAP_LORENCIA: "lorencia",
    MAP_DEVIAS: "devias",
    MAP_NORIA: "noria",
}

DEFAULT_TALISMAN_GATHER_CONFIG: Dict[str, Any] = {
    "include_luck": True,               # Gom Talisman of Luck (7221)
    "include_chaos_assembly": True,     # Gom Talisman of Chaos Assembly (7264)
    "claim_from_gremory": True,         # Lôi bùa từ Thùng đồ K (Gremory Case) trước khi gom
    "stack_in_inventory": True,         # Hướng A: Gom chồng bùa stackable trong túi/kho theo MaxStack server
    "deposit_to_warehouse": True,       # Hướng B: Tự mở Thủ Kho & cất gọn bùa vào Kho đồ
    "town": "auto",                     # "auto" | "lorencia" | "noria" | "devias"
    "vault_number": 0,                  # 0 = giữ nguyên kho hiện tại, >0 = gửi /bau N trước khi mở kho
    "prefer_ext_warehouse": False,      # Ưu tiên Kho mở rộng (120..239) nếu đang mở
    "close_warehouse_after": True,      # Đóng Kho đồ sau khi cất xong
    "max_duration_s": 60.0,             # Giới hạn thời gian tối đa mỗi lượt gom
}


def normalize_vault_town(town: Optional[str]) -> str:
    raw = str(town or "auto").strip().lower()
    if raw in ("davias", "devias", "devias1", "devias 1"):
        return "devias"
    if raw in ("noria",):
        return "noria"
    if raw in ("lorencia", "lor"):
        return "lorencia"
    return "auto"


def resolve_vault_town_order(preferred_town: str, current_map_id: int = -1) -> List[str]:
    pref = normalize_vault_town(preferred_town)
    all_towns = ["lorencia", "noria", "devias"]
    if pref == "auto":
        cur = MAP_ID_TO_TOWN.get(int(current_map_id)) if current_map_id is not None else None
        order: List[str] = []
        if cur:
            order.append(cur)
        for t in all_towns:
            if t not in order:
                order.append(t)
        return order
    order = [pref]
    for t in all_towns:
        if t not in order:
            order.append(t)
    return order


class TalismanGatherConfigManager:
    """Lưu & đọc cấu hình Gom Bùa tại config/talisman_gatherer_config.json."""

    def __init__(self, base_dir: Path):
        self.config_path = Path(base_dir) / "config" / "talisman_gatherer_config.json"

    def load(self) -> Dict[str, Any]:
        cfg = copy.deepcopy(DEFAULT_TALISMAN_GATHER_CONFIG)
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
            except Exception:
                pass
        cfg["include_luck"] = bool(cfg.get("include_luck", True))
        cfg["include_chaos_assembly"] = bool(cfg.get("include_chaos_assembly", True))
        cfg["claim_from_gremory"] = bool(cfg.get("claim_from_gremory", True))
        cfg["stack_in_inventory"] = bool(cfg.get("stack_in_inventory", True))
        cfg["deposit_to_warehouse"] = bool(cfg.get("deposit_to_warehouse", True))
        cfg["town"] = normalize_vault_town(cfg.get("town", "auto"))
        try:
            cfg["vault_number"] = max(0, min(99, int(cfg.get("vault_number", 0) or 0)))
        except Exception:
            cfg["vault_number"] = 0
        cfg["prefer_ext_warehouse"] = bool(cfg.get("prefer_ext_warehouse", False))
        cfg["close_warehouse_after"] = bool(cfg.get("close_warehouse_after", True))
        cfg["max_duration_s"] = max(20.0, float(cfg.get("max_duration_s", 60.0) or 60.0))
        return cfg

    def save(self, cfg: Dict[str, Any]) -> bool:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            merged = copy.deepcopy(DEFAULT_TALISMAN_GATHER_CONFIG)
            if isinstance(cfg, dict):
                merged.update(cfg)
            merged["include_luck"] = bool(merged.get("include_luck", True))
            merged["include_chaos_assembly"] = bool(merged.get("include_chaos_assembly", True))
            merged["claim_from_gremory"] = bool(merged.get("claim_from_gremory", True))
            merged["stack_in_inventory"] = bool(merged.get("stack_in_inventory", True))
            merged["deposit_to_warehouse"] = bool(merged.get("deposit_to_warehouse", True))
            merged["town"] = normalize_vault_town(merged.get("town", "auto"))
            try:
                merged["vault_number"] = max(0, min(99, int(merged.get("vault_number", 0) or 0)))
            except Exception:
                merged["vault_number"] = 0
            merged["prefer_ext_warehouse"] = bool(merged.get("prefer_ext_warehouse", False))
            merged["close_warehouse_after"] = bool(merged.get("close_warehouse_after", True))
            merged["max_duration_s"] = max(20.0, float(merged.get("max_duration_s", 60.0) or 60.0))
            self.config_path.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False


def format_talisman_scan_summary(snap: Dict[str, Any]) -> str:
    """Tạo chuỗi tóm tắt ngắn gọn kết quả quét RAM Bùa Luck & Bùa Chaos Assembly."""
    if not snap or not snap.get("ok"):
        return f"Lỗi quét RAM: {(snap or {}).get('error', 'unknown')}"
    totals = snap.get("totals") or {}
    st_info = snap.get("stackInfo") or {}

    def _fmt_meta(tid: str, label: str) -> str:
        t = totals.get(tid) or {}
        inv_c = int(t.get("inventory", 0) or 0)
        wh_c = int(t.get("warehouse", 0) or 0)
        gr_c = int(t.get("gremory", 0) or 0)
        si = st_info.get(tid) or {}
        if si.get("seen"):
            ms = int(si.get("maxStack", 1) or 1)
            st_txt = f"Stack tối đa {ms}" if si.get("stackable") else "Không stack (1/ô)"
        else:
            st_txt = "Chưa thấy mẫu"
        return f"{label}: Túi={inv_c} · Kho={wh_c} · Thùng K={gr_c} [{st_txt}]"

    wh_state = "ĐANG MỞ" if snap.get("warehouseOpen") else "Đang đóng"
    free_cnt = int(snap.get("warehouseFreeCount", 0) or 0)
    return (
        f"{_fmt_meta(str(TALISMAN_LUCK_ID), '🍀 Bùa Luck')} | "
        f"{_fmt_meta(str(TALISMAN_CHAOS_ASSEMBLY_ID), '🛡️ Chaos Assembly')} | "
        f"Kho: {wh_state} (trống {free_cnt} ô)"
    )


def _sleep_check(seconds: float, stop_event: Optional[threading.Event] = None) -> bool:
    end = time.time() + max(0.0, seconds)
    while time.time() < end:
        if stop_event is not None and stop_event.is_set():
            return False
        time.sleep(min(0.15, max(0.02, end - time.time())))
    return not (stop_event is not None and stop_event.is_set())


def _read_pos(eng: Any) -> Tuple[int, int, int]:
    try:
        info = eng.get_player_info(max_age=0.15) or {}
    except Exception:
        info = {}
    m = info.get("mapId")
    if m is None:
        m = info.get("map_id", -1)
    x = info.get("tileX") if info.get("tileX") is not None else info.get("x", 0)
    y = info.get("tileY") if info.get("tileY") is not None else info.get("y", 0)
    try:
        return int(m if m is not None else -1), int(x or 0), int(y or 0)
    except Exception:
        return -1, 0, 0


def _move_to_xy(
    eng: Any,
    tx: int,
    ty: int,
    expected_map_id: int,
    arrive_dist: float = 2.6,
    timeout_s: float = 12.0,
    stop_event: Optional[threading.Event] = None,
) -> bool:
    deadline = time.time() + max(2.0, timeout_s)
    last_cmd = 0.0
    while time.time() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        cm, px, py = _read_pos(eng)
        if expected_map_id >= 0 and cm >= 0 and cm != expected_map_id:
            return False
        if px > 0 and py > 0 and math.hypot(tx - px, ty - py) <= arrive_dist:
            if hasattr(eng, "stop_auto_move"):
                try:
                    eng.stop_auto_move()
                except Exception:
                    pass
            return True
        now = time.time()
        if last_cmd == 0.0 or (now - last_cmd) >= 2.2:
            try:
                eng.start_auto_move(int(tx), int(ty), helper=False)
            except Exception:
                try:
                    eng.move_to(int(tx), int(ty))
                except Exception:
                    pass
            last_cmd = now
        if not _sleep_check(0.3, stop_event):
            return False
    if hasattr(eng, "stop_auto_move"):
        try:
            eng.stop_auto_move()
        except Exception:
            pass
    return False


def _open_warehouse_in_town(
    eng: Any,
    cfg: Dict[str, Any],
    deadline: float,
    stop_event: Optional[threading.Event] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Dịch chuyển về thành, tìm Thủ Kho (NPC 240), đổi kho `/bau N` nếu cần, và mở Kho đồ."""
    def _log(m: str, lv: str = "INFO"):
        if log_cb:
            try:
                log_cb(m, lv)
            except Exception:
                pass

    def _st(t: str):
        if status_cb:
            try:
                status_cb(t)
            except Exception:
                pass

    vault_num = int(cfg.get("vault_number", 0) or 0)
    snap0 = eng.scan_talismans_info() if hasattr(eng, "scan_talismans_info") else {}
    if snap0.get("warehouseOpen") and vault_num <= 0:
        return True, "current"

    # Nếu cần đổi số kho /bau N thì đóng kho cũ trước
    if snap0.get("warehouseOpen") and vault_num > 0 and hasattr(eng, "close_warehouse_window"):
        try:
            eng.close_warehouse_window()
            _sleep_check(0.5, stop_event)
        except Exception:
            pass

    if vault_num > 0:
        _log(f"🏦 [Gom Bùa] Chuyển kho sang `/bau {vault_num}`...", "INFO")
        try:
            eng.send_chat(f"/bau {vault_num}")
        except Exception:
            pass
        if not _sleep_check(0.7, stop_event):
            return False, ""

    cur_map, _, _ = _read_pos(eng)
    town_order = resolve_vault_town_order(str(cfg.get("town", "auto")), cur_map)

    try:
        eng.stop_helper()
    except Exception:
        pass

    for town_key in town_order:
        if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
            return False, ""

        spec = VAULT_NPC_CATALOG[town_key]
        label = spec["label"]
        t_map = int(spec["map_id"])
        cmd = str(spec["map_cmd"])
        _st(f"MỞ KHO ({label})")

        cm, _, _ = _read_pos(eng)
        if cm != t_map:
            warped = False
            for attempt in range(3):
                if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
                    return False, ""
                _log(f"🏦 [Gom Bùa] Dịch chuyển về {label} ({cmd}, lần {attempt + 1}/3)...", "INFO")
                try:
                    eng.send_chat(cmd)
                except Exception:
                    pass
                w_end = time.time() + 5.5
                while time.time() < w_end:
                    if not _sleep_check(0.3, stop_event):
                        return False, ""
                    cm2, _, _ = _read_pos(eng)
                    if cm2 == t_map:
                        warped = True
                        _sleep_check(0.5, stop_event)
                        break
                if warped:
                    break
            if not warped:
                continue

        # Tìm Thủ Kho trong tầm nhìn hoặc đi tới tọa độ Thủ Kho chuẩn
        npc = eng.find_vault_keeper_npc() if hasattr(eng, "find_vault_keeper_npc") else {}
        if not (npc and npc.get("found")):
            for wx, wy in spec["waypoints"]:
                if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
                    return False, ""
                _move_to_xy(eng, wx, wy, expected_map_id=t_map, arrive_dist=3.0, timeout_s=10.0, stop_event=stop_event)
                if hasattr(eng, "find_vault_keeper_npc"):
                    npc = eng.find_vault_keeper_npc() or {}
                    if npc.get("found"):
                        break

        if not (npc and npc.get("found")):
            _log(f"⚠️ [Gom Bùa] Chưa thấy NPC Thủ Kho tại {label}, thử thành kế tiếp...", "WARN")
            continue

        nx = int(npc.get("x", spec["npc_pos"][0]) or spec["npc_pos"][0])
        ny = int(npc.get("y", spec["npc_pos"][1]) or spec["npc_pos"][1])
        if float(npc.get("dist", 0) or 0) > 2.8:
            _move_to_xy(eng, nx, ny, expected_map_id=t_map, arrive_dist=2.5, timeout_s=10.0, stop_event=stop_event)
            if hasattr(eng, "find_vault_keeper_npc"):
                npc2 = eng.find_vault_keeper_npc() or {}
                if npc2.get("found"):
                    npc = npc2

        # Nói chuyện Thủ Kho (C1:30) và chờ Kho đồ mở thật
        for talk_try in range(3):
            if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
                return False, ""
            _log(f"🏦 [Gom Bùa] Mở Thủ Kho tại {label} ({nx},{ny}) — lần {talk_try + 1}/3...", "INFO")
            eng.talk_to_npc_by_ptr(npc.get("ptr"))
            wait_open = time.time() + 2.4
            while time.time() < wait_open:
                if not _sleep_check(0.25, stop_event):
                    return False, ""
                st_now = eng.scan_talismans_info() if hasattr(eng, "scan_talismans_info") else {}
                if st_now.get("warehouseOpen"):
                    _sleep_check(0.35, stop_event)
                    return True, label

    return False, ""


def execute_talisman_gather(
    eng: Any,
    cfg: Optional[Dict[str, Any]] = None,
    stop_event: Optional[threading.Event] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Thực thi trọn quy trình Gom Bùa (kết hợp cả Hướng A + Hướng B):
      1. Quét RAM kiểm chứng số lượng & MaxStack của Bùa Luck (7221) và Bùa Chaos Assembly (7264).
      2. Lôi bùa từ Thùng đồ K (nếu bật & có bùa).
      3. Hướng A: Gom chồng bùa stackable trong Hòm đồ (và Kho nếu đang mở).
      4. Hướng B: Nếu còn bùa trong Hòm đồ và bật cất Kho -> tự về thành mở Thủ Kho,
         gom chồng trong Kho, rồi cất sạch bùa vào các ô trống của Kho đồ.
      5. Đóng Kho đồ gọn gàng và trả về báo cáo chi tiết.
    """
    conf = copy.deepcopy(DEFAULT_TALISMAN_GATHER_CONFIG)
    if isinstance(cfg, dict):
        conf.update(cfg)

    inc_luck = bool(conf.get("include_luck", True))
    inc_chaos = bool(conf.get("include_chaos_assembly", True))
    if not inc_luck and not inc_chaos:
        return {"ok": False, "reason": "nothing_selected"}

    def _log(m: str, lv: str = "INFO"):
        if log_cb:
            try:
                log_cb(m, lv)
            except Exception:
                pass

    def _st(t: str):
        if status_cb:
            try:
                status_cb(t)
            except Exception:
                pass

    if not eng or not getattr(eng, "is_ready", False):
        return {"ok": False, "reason": "engine_not_ready"}

    deadline = time.time() + max(20.0, float(conf.get("max_duration_s", 60.0) or 60.0))
    claimed_gremory = 0
    stacked_moves = 0
    deposited_count = 0
    opened_wh_here = False
    vault_town_used = ""

    # 1. Quét ban đầu
    _st("QUÉT BÙA")
    snap_before = eng.scan_talismans_info() if hasattr(eng, "scan_talismans_info") else {"ok": False}
    if not snap_before.get("ok"):
        _log(f"❌ [Gom Bùa] Không thể quét RAM: {snap_before.get('error', 'unknown')}", "ERROR")
        return {"ok": False, "reason": "scan_failed", "detail": snap_before}

    _log(f"🧿 [Gom Bùa] Trước khi chạy: {format_talisman_scan_summary(snap_before)}", "INFO")

    # 2. Lôi riêng Bùa Luck / Chaos Assembly từ Thùng đồ K (Gremory Case)
    if conf.get("claim_from_gremory", True) and hasattr(eng, "claim_gremory_talismans"):
        g_items = snap_before.get("gremoryItems") or []
        want_ids = set()
        if inc_luck:
            want_ids.add(TALISMAN_LUCK_ID)
        if inc_chaos:
            want_ids.add(TALISMAN_CHAOS_ASSEMBLY_ID)
        has_gremory_target = any(int(it.get("code", -1) or -1) in want_ids for it in g_items)
        if has_gremory_target:
            _st("LÔI BÙA THÙNG K")
            _log("📦 [Gom Bùa] Phát hiện bùa trong Thùng đồ K -> đang lôi ra túi đồ...", "INFO")
            g_res = eng.claim_gremory_talismans(inc_luck, inc_chaos) or {}
            claimed_gremory = int(g_res.get("claimed", 0) or 0)
            if claimed_gremory > 0:
                _log(f"✅ [Gom Bùa] Đã lôi {claimed_gremory} bùa từ Thùng đồ K ra túi đồ.", "SUCCESS")
                _sleep_check(0.35, stop_event)

    # 3. Hướng A: Gom chồng (Stack) bùa trong Hòm đồ (& Kho nếu đã mở sẵn)
    if conf.get("stack_in_inventory", True) and hasattr(eng, "stack_talismans"):
        _st("GOM CHỒNG BÙA")
        for _pass in range(2):
            if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
                break
            st_res = eng.stack_talismans(inc_luck, inc_chaos) or {}
            mv = int(st_res.get("moved", 0) or 0)
            stacked_moves += mv
            for d in (st_res.get("details") or []):
                _log(
                    f"✨ [Hướng A · {d.get('storage', 'Hòm đồ')}] Gom chồng {d.get('name', 'Bùa')}: "
                    f"ô {d.get('fromSlot')} ➔ ô {d.get('toSlot')} (+{d.get('amount')}, thành {d.get('targetTotal')}/{d.get('maxStack')})",
                    "SUCCESS",
                )
            if mv == 0:
                break
            if not _sleep_check(0.35, stop_event):
                break

    # 4. Hướng B: Cất toàn bộ Bùa Chaos Assembly & Bùa Luck từ Hòm đồ vào Kho đồ
    if conf.get("deposit_to_warehouse", True) and hasattr(eng, "deposit_talismans_to_warehouse"):
        snap_mid = eng.scan_talismans_info() if hasattr(eng, "scan_talismans_info") else snap_before
        inv_targets = [
            it for it in (snap_mid.get("inventoryItems") or [])
            if (inc_luck and int(it.get("id", -1)) == TALISMAN_LUCK_ID)
            or (inc_chaos and int(it.get("id", -1)) == TALISMAN_CHAOS_ASSEMBLY_ID)
        ]

        if inv_targets:
            wh_was_open = bool(snap_mid.get("warehouseOpen", False))
            ok_wh, vault_town_used = _open_warehouse_in_town(
                eng, conf, deadline, stop_event=stop_event, log_cb=log_cb, status_cb=status_cb
            )
            if ok_wh:
                opened_wh_here = (not wh_was_open) or int(conf.get("vault_number", 0) or 0) > 0
                # Gom chồng trong Kho trước khi cất thêm để tối ưu ô trống
                if conf.get("stack_in_inventory", True) and hasattr(eng, "stack_talismans"):
                    st_wh = eng.stack_talismans(inc_luck, inc_chaos) or {}
                    stacked_moves += int(st_wh.get("moved", 0) or 0)
                    _sleep_check(0.3, stop_event)

                _st("CẤT BÙA VÀO KHO")
                prefer_ext = bool(conf.get("prefer_ext_warehouse", False))
                for _round in range(3):
                    if time.time() >= deadline or (stop_event is not None and stop_event.is_set()):
                        break
                    dep = eng.deposit_talismans_to_warehouse(inc_luck, inc_chaos, prefer_ext, 64) or {}
                    dm = int(dep.get("deposited", 0) or 0)
                    deposited_count += dm
                    for d in (dep.get("details") or []):
                        mode_lbl = "gộp vào ô kho" if d.get("merged") else "cất vào ô kho"
                        _log(
                            f"🏦 [Hướng B] {d.get('name', 'Bùa')} (x{d.get('count', 1)}): "
                            f"túi ô {d.get('fromSlot')} ➔ {mode_lbl} {d.get('toSlot')}",
                            "SUCCESS",
                        )
                    if dep.get("warehouseFull"):
                        _log("⚠️ [Gom Bùa] Kho đồ đã hết ô trống, dừng cất kho.", "WARN")
                        break
                    if dm == 0 or int(dep.get("remainingInInventory", 0) or 0) == 0:
                        break
                    if not _sleep_check(0.4, stop_event):
                        break

                if conf.get("close_warehouse_after", True) and opened_wh_here and hasattr(eng, "close_warehouse_window"):
                    try:
                        eng.close_warehouse_window()
                    except Exception:
                        pass
            else:
                _log("⚠️ [Gom Bùa] Không mở được Kho đồ (Thủ Kho) — đã hoàn tất phần Hướng A trong túi.", "WARN")

    # 5. Quét tổng kết sau khi hoàn tất
    snap_after = eng.scan_talismans_info() if hasattr(eng, "scan_talismans_info") else snap_before
    summary = format_talisman_scan_summary(snap_after)
    _log(
        f"✅ [Gom Bùa] Hoàn tất: Lôi Thùng K={claimed_gremory} · Gom chồng={stacked_moves} lượt · Cất Kho={deposited_count} ô. {summary}",
        "SUCCESS",
    )
    return {
        "ok": True,
        "claimed_gremory": claimed_gremory,
        "stacked_moves": stacked_moves,
        "deposited": deposited_count,
        "vault_town": vault_town_used,
        "before": snap_before,
        "after": snap_after,
        "summary": summary,
    }
