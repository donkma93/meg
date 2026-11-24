#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto PK Reporter — Tự động về thành tìm Lính Canh Report khi bị PK
=========================================================================
Khi nhân vật bị người chơi khác PK (KillerName != "" tại LocalCharacterBody + 0x528):
  1. Dừng MuHelper, chờ hoàn tất hồi sinh (isDead == False, hp > 0).
  2. Chuyển về thành đã chọn: Tự động (ưu tiên thành hiện tại nếu đang ở Lorencia/Noria/Devias)
     hoặc cố định Lorencia / Noria / Devias (có tự chuyển thành dự phòng nếu chưa thấy Lính Canh).
  3. Quét Viewport tìm Lính Canh gần nhất (Berdysh Guard skin 249 / Crossbow Guard skin 247 / tên Guard),
     tuần tra qua các cổng thành nếu Lính Canh chưa vào tầm nhìn.
  4. Di chuyển sát Lính Canh (<= 2.5 ô), bật auto-confirm dialog Report (MHelperUI Slot 10),
     gửi gói nói chuyện C1:30 trên Unity MainThread và xác minh KillerName trong RAM đã được xóa.
  5. Đóng cửa sổ PK / hội thoại (C1:31) gọn gàng để Auto Train tiếp tục chu trình ra bãi.
"""

import copy
import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# Map IDs chuẩn MU Online / MEGAMU
MAP_LORENCIA = 0
MAP_DEVIAS = 2
MAP_NORIA = 3

# Skin IDs chuẩn của Lính Canh (Guard) trong MU Online / MEGAMU
GUARD_NPC_SKINS = (249, 247)  # 249 = Berdysh Guard, 247 = Crossbow Guard

# Danh sách các thành hỗ trợ tìm Lính Canh kèm điểm tuần tra cổng thành
TOWN_GUARD_CATALOG: Dict[str, Dict[str, Any]] = {
    "lorencia": {
        "label": "Lorencia",
        "map_id": MAP_LORENCIA,
        "map_cmd": "/m lorencia",
        "waypoints": [
            (131, 88),   # Cổng Nam (Berdysh Guard hay đứng tuần tra nhất)
            (131, 165),  # Cổng Bắc
            (173, 125),  # Cổng Đông
            (94, 125),   # Cổng Tây
            (141, 127),  # Trung tâm
        ],
    },
    "noria": {
        "label": "Noria",
        "map_id": MAP_NORIA,
        "map_cmd": "/m noria",
        "waypoints": [
            (167, 118),  # Trung tâm / lối Tây
            (195, 113),  # Cổng Đông
            (171, 85),   # Cổng Nam
            (152, 102),  # Lối Tây Bắc
        ],
    },
    "devias": {
        "label": "Devias",
        "map_id": MAP_DEVIAS,
        "map_cmd": "/m devias",
        "waypoints": [
            (209, 30),   # Cổng Nam
            (226, 45),   # Cổng Đông
            (191, 45),   # Lối Tây / trung tâm
            (217, 63),   # Cổng Bắc
        ],
    },
}

MAP_ID_TO_TOWN: Dict[int, str] = {
    MAP_LORENCIA: "lorencia",
    MAP_DEVIAS: "devias",
    MAP_NORIA: "noria",
}

DEFAULT_PK_REPORT_CONFIG: Dict[str, Any] = {
    "enabled": True,                 # Bật/tắt tự động về thành tìm Lính Canh Report khi bị PK
    "town": "auto",                  # "auto" | "lorencia" | "noria" | "devias"
    "only_when_killer_known": True,  # Chỉ đi Report khi có tên người chơi PK (bỏ qua nếu chết do quái)
    "fallback_towns": True,          # Nếu không thấy Lính Canh ở thành đầu tiên thì tự thử sang 2 thành còn lại
    "max_duration_s": 55.0,          # Giới hạn thời gian tối đa cho 1 lượt tìm & Report
}


def normalize_town_key(town: Optional[str]) -> str:
    raw = str(town or "auto").strip().lower()
    if raw in ("davias", "devias", "devias1", "devias 1"):
        return "devias"
    if raw in ("noria",):
        return "noria"
    if raw in ("lorencia", "lor"):
        return "lorencia"
    return "auto"


def resolve_report_town_order(
    preferred_town: str,
    current_map_id: int = -1,
    fallback_towns: bool = True,
) -> List[str]:
    """Xác định thứ tự các thành (lorencia / noria / devias) sẽ đi tìm Lính Canh."""
    pref = normalize_town_key(preferred_town)
    all_towns = ["lorencia", "noria", "devias"]

    if pref == "auto":
        cur_town = MAP_ID_TO_TOWN.get(int(current_map_id)) if current_map_id is not None else None
        order: List[str] = []
        if cur_town:
            order.append(cur_town)
        for t in all_towns:
            if t not in order:
                order.append(t)
        return order if fallback_towns else order[:1]

    order = [pref]
    if fallback_towns:
        for t in all_towns:
            if t not in order:
                order.append(t)
    return order


class PkReportConfigManager:
    """Lưu & đọc cấu hình Auto Report PK tại config/pk_report_config.json."""

    def __init__(self, base_dir: Path):
        self.config_path = Path(base_dir) / "config" / "pk_report_config.json"

    def load(self) -> Dict[str, Any]:
        cfg = copy.deepcopy(DEFAULT_PK_REPORT_CONFIG)
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
            except Exception:
                pass
        cfg["town"] = normalize_town_key(cfg.get("town", "auto"))
        cfg["enabled"] = bool(cfg.get("enabled", True))
        cfg["only_when_killer_known"] = bool(cfg.get("only_when_killer_known", True))
        cfg["fallback_towns"] = bool(cfg.get("fallback_towns", True))
        cfg["max_duration_s"] = max(20.0, float(cfg.get("max_duration_s", 55.0) or 55.0))
        return cfg

    def save(self, cfg: Dict[str, Any]) -> bool:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            merged = copy.deepcopy(DEFAULT_PK_REPORT_CONFIG)
            if isinstance(cfg, dict):
                merged.update(cfg)
            merged["town"] = normalize_town_key(merged.get("town", "auto"))
            merged["enabled"] = bool(merged.get("enabled", True))
            merged["only_when_killer_known"] = bool(merged.get("only_when_killer_known", True))
            merged["fallback_towns"] = bool(merged.get("fallback_towns", True))
            merged["max_duration_s"] = max(20.0, float(merged.get("max_duration_s", 55.0) or 55.0))
            self.config_path.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False


def _sleep_check(seconds: float, stop_event: Optional[threading.Event] = None) -> bool:
    """Ngủ theo lát 0.15s để phản hồi dừng tức thì. Trả về False nếu bị dừng."""
    end = time.time() + max(0.0, seconds)
    while time.time() < end:
        if stop_event is not None and stop_event.is_set():
            return False
        time.sleep(min(0.15, max(0.02, end - time.time())))
    return not (stop_event is not None and stop_event.is_set())


def _read_pos(eng: Any) -> Tuple[int, int, int]:
    """Trả về (map_id, x, y) hiện tại từ engine."""
    info = {}
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


def _warp_to_town(
    eng: Any,
    town_key: str,
    stop_event: Optional[threading.Event] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
) -> bool:
    spec = TOWN_GUARD_CATALOG[town_key]
    target_map = int(spec["map_id"])
    map_cmd = str(spec["map_cmd"])
    label = str(spec["label"])

    cur_map, _, _ = _read_pos(eng)
    if cur_map == target_map:
        return True

    try:
        eng.stop_helper()
    except Exception:
        pass
    if hasattr(eng, "stop_auto_move"):
        try:
            eng.stop_auto_move()
        except Exception:
            pass
    if not _sleep_check(0.25, stop_event):
        return False

    for attempt in range(3):
        if stop_event is not None and stop_event.is_set():
            return False
        if log_cb:
            log_cb(f"🛡️ [Auto Report] Dịch chuyển về {label} ({map_cmd}, lần {attempt + 1}/3)...", "INFO")
        try:
            eng.send_chat(map_cmd)
        except Exception:
            pass
        deadline = time.time() + 6.0
        while time.time() < deadline:
            if not _sleep_check(0.3, stop_event):
                return False
            cm, _, _ = _read_pos(eng)
            if cm == target_map:
                _sleep_check(0.55, stop_event)
                return True
    return False


def _move_towards_with_guard_scan(
    eng: Any,
    tx: int,
    ty: int,
    expected_map_id: int,
    stop_on_guard_found: bool = True,
    arrive_dist: float = 2.6,
    timeout_s: float = 12.0,
    stop_event: Optional[threading.Event] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Di chuyển về (tx, ty) và quét Lính Canh dọc đường nếu `stop_on_guard_found=True`."""
    deadline = time.time() + max(2.0, timeout_s)
    last_cmd = 0.0
    while time.time() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False, None

        if stop_on_guard_found and hasattr(eng, "find_guard_npc"):
            try:
                g = eng.find_guard_npc() or {}
                if g.get("found"):
                    return True, g
            except Exception:
                pass

        cm, px, py = _read_pos(eng)
        if expected_map_id >= 0 and cm >= 0 and cm != expected_map_id:
            return False, None
        if px > 0 and py > 0 and math.hypot(tx - px, ty - py) <= arrive_dist:
            try:
                if hasattr(eng, "stop_auto_move"):
                    eng.stop_auto_move()
            except Exception:
                pass
            return True, None

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

        if not _sleep_check(0.35, stop_event):
            return False, None

    try:
        if hasattr(eng, "stop_auto_move"):
            eng.stop_auto_move()
    except Exception:
        pass
    return False, None


def execute_pk_report(
    eng: Any,
    cfg: Optional[Dict[str, Any]] = None,
    killer_name: str = "",
    force: bool = False,
    stop_event: Optional[threading.Event] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Thực hiện trọn vẹn quy trình:
      Về thành (Noria / Lorencia / Devias) -> tìm Lính Canh (Guard) -> nói chuyện (C1:30)
      + tự bấm xác nhận Report nếu hiện popup -> kiểm chứng KillerName đã xóa -> đóng hộp thoại.
    """
    conf = copy.deepcopy(DEFAULT_PK_REPORT_CONFIG)
    if isinstance(cfg, dict):
        conf.update(cfg)

    def _log(msg: str, level: str = "INFO"):
        if log_cb:
            try:
                log_cb(msg, level)
            except Exception:
                pass

    def _st(text: str):
        if status_cb:
            try:
                status_cb(text)
            except Exception:
                pass

    if not eng or not getattr(eng, "is_ready", False):
        return {"ok": False, "reported": False, "reason": "engine_not_ready"}

    # 1. Đọc trạng thái PK / KillerName từ RAM
    pk_before = eng.get_pk_report_status() if hasattr(eng, "get_pk_report_status") else {}
    ram_killer = str((pk_before or {}).get("killerName") or "").strip()
    eff_killer = ram_killer or str(killer_name or "").strip()

    if not force and conf.get("only_when_killer_known", True) and not eff_killer:
        return {"ok": True, "reported": False, "skipped": True, "reason": "no_pk_killer"}

    # 2. Chờ nhân vật hồi sinh xong (tránh warp khi animation chết chưa dứt)
    wait_alive_until = time.time() + 6.0
    while time.time() < wait_alive_until:
        if stop_event is not None and stop_event.is_set():
            return {"ok": False, "reported": False, "reason": "stopped"}
        st_now = eng.get_pk_report_status() if hasattr(eng, "get_pk_report_status") else {}
        if not st_now.get("isDead", False) and int(st_now.get("hp", 1) or 0) > 0:
            if not eff_killer and st_now.get("killerName"):
                eff_killer = str(st_now.get("killerName")).strip()
            break
        if not _sleep_check(0.35, stop_event):
            return {"ok": False, "reported": False, "reason": "stopped"}

    if not force and conf.get("only_when_killer_known", True) and not eff_killer:
        return {"ok": True, "reported": False, "skipped": True, "reason": "no_pk_killer"}

    cur_map, _, _ = _read_pos(eng)
    town_order = resolve_report_town_order(
        preferred_town=str(conf.get("town", "auto")),
        current_map_id=cur_map,
        fallback_towns=bool(conf.get("fallback_towns", True)),
    )
    max_deadline = time.time() + max(20.0, float(conf.get("max_duration_s", 55.0) or 55.0))
    killer_tag = f" kẻ PK '{eff_killer}'" if eff_killer else ""
    _log(
        f"🚨 [Auto Report] Bắt đầu đi tìm Lính Canh để Report{killer_tag} (thứ tự thành: {' → '.join(TOWN_GUARD_CATALOG[t]['label'] for t in town_order)})...",
        "WARNING",
    )

    try:
        for town_key in town_order:
            if time.time() >= max_deadline or (stop_event is not None and stop_event.is_set()):
                break

            spec = TOWN_GUARD_CATALOG[town_key]
            town_label = spec["label"]
            town_map_id = int(spec["map_id"])
            _st(f"REPORT PK ({town_label})")

            if not _warp_to_town(eng, town_key, stop_event=stop_event, log_cb=log_cb):
                _log(f"⚠️ [Auto Report] Không thể dịch chuyển về {town_label}, chuyển thành kế tiếp...", "WARN")
                continue

            # Quét Lính Canh ngay tại điểm hồi sinh/cổng trước khi đi tuần tra
            guard = eng.find_guard_npc() if hasattr(eng, "find_guard_npc") else {}
            if not (guard and guard.get("found")):
                for wp_x, wp_y in spec["waypoints"]:
                    if time.time() >= max_deadline or (stop_event is not None and stop_event.is_set()):
                        break
                    _st(f"TÌM LÍNH CANH ({town_label} {wp_x},{wp_y})")
                    _, found_g = _move_towards_with_guard_scan(
                        eng,
                        wp_x,
                        wp_y,
                        expected_map_id=town_map_id,
                        stop_on_guard_found=True,
                        arrive_dist=4.0,
                        timeout_s=10.0,
                        stop_event=stop_event,
                    )
                    if found_g and found_g.get("found"):
                        guard = found_g
                        break
                    # Quét lại 1 nhịp tại waypoint vừa tới
                    if hasattr(eng, "find_guard_npc"):
                        g_wp = eng.find_guard_npc() or {}
                        if g_wp.get("found"):
                            guard = g_wp
                            break

            if not (guard and guard.get("found")):
                _log(f"⚠️ [Auto Report] Chưa thấy Lính Canh quanh các cổng {town_label}.", "WARN")
                continue

            gx = int(guard.get("x", 0) or 0)
            gy = int(guard.get("y", 0) or 0)
            gname = str(guard.get("name") or f"Guard#{guard.get('skin', 249)}")
            _log(f"🎯 [Auto Report] Phát hiện Lính Canh '{gname}' tại {town_label} ({gx}, {gy}) -> chạy lại nói chuyện...", "INFO")
            _st(f"REPORT LÍNH CANH ({town_label})")

            # Tiến sát lại Lính Canh (<= 2.5 ô) để đảm bảo C1:30 trong tầm tương tác
            if float(guard.get("dist", 0) or 0) > 2.6 and gx > 0 and gy > 0:
                _move_towards_with_guard_scan(
                    eng,
                    gx,
                    gy,
                    expected_map_id=town_map_id,
                    stop_on_guard_found=False,
                    arrive_dist=2.4,
                    timeout_s=12.0,
                    stop_event=stop_event,
                )
                # Cập nhật lại ptr & tọa độ mới nhất (Lính Canh có thể vừa bước đi 1-2 ô)
                if hasattr(eng, "find_guard_npc"):
                    g_fresh = eng.find_guard_npc() or {}
                    if g_fresh.get("found"):
                        guard = g_fresh
                        gx = int(guard.get("x", gx) or gx)
                        gy = int(guard.get("y", gy) or gy)

            # Bật auto-confirm dialog Report (MHelperUI Slot 10) trước khi gửi C1:30
            if hasattr(eng, "set_auto_confirm_report"):
                try:
                    eng.set_auto_confirm_report(True, eff_killer)
                except Exception:
                    pass

            reported_ok = False
            confirm_method = "npc_talk"
            try:
                for talk_try in range(3):
                    if stop_event is not None and stop_event.is_set():
                        break
                    # Cập nhật lại vị trí Lính Canh nếu lần trước chưa thành công
                    if talk_try > 0 and hasattr(eng, "find_guard_npc"):
                        g2 = eng.find_guard_npc() or {}
                        if g2.get("found"):
                            guard = g2
                            if float(g2.get("dist", 0) or 0) > 2.8:
                                _move_towards_with_guard_scan(
                                    eng,
                                    int(g2.get("x", gx)),
                                    int(g2.get("y", gy)),
                                    expected_map_id=town_map_id,
                                    stop_on_guard_found=False,
                                    arrive_dist=2.4,
                                    timeout_s=6.0,
                                    stop_event=stop_event,
                                )

                    eng.talk_to_npc_by_ptr(guard.get("ptr"))

                    # Chờ tối đa 2.4s kiểm tra phản hồi: KillerName biến mất / xác nhận dialog / PKWindow mở
                    poll_end = time.time() + 2.4
                    while time.time() < poll_end:
                        if not _sleep_check(0.25, stop_event):
                            break
                        after_st = eng.get_pk_report_status() if hasattr(eng, "get_pk_report_status") else {}
                        after_killer = str((after_st or {}).get("killerName") or "").strip()
                        confirm_cnt = int((after_st or {}).get("autoReportConfirmCount", 0) or 0)
                        if confirm_cnt > int((pk_before or {}).get("autoReportConfirmCount", 0) or 0):
                            reported_ok = True
                            confirm_method = "confirm_dialog"
                            break
                        if ram_killer and not after_killer:
                            reported_ok = True
                            confirm_method = "killer_cleared"
                            break
                        if (after_st or {}).get("pkWindowOpen"):
                            reported_ok = True
                            confirm_method = "pk_window_opened"
                            break
                    if reported_ok:
                        break
            finally:
                if hasattr(eng, "set_auto_confirm_report"):
                    try:
                        eng.set_auto_confirm_report(False, "")
                    except Exception:
                        pass
                if hasattr(eng, "close_pk_window"):
                    try:
                        eng.close_pk_window()
                    except Exception:
                        pass

            # Ngay cả khi test thủ công (không có ram_killer ban đầu) vẫn coi là đã tương tác xong với Lính Canh
            if reported_ok or (force and not ram_killer):
                _log(
                    f"✅ [Auto Report] Đã tương tác Lính Canh '{gname}' tại {town_label} ({gx}, {gy}) thành công"
                    + (f" — Report '{eff_killer}' ({confirm_method})!" if eff_killer else f" ({confirm_method})!"),
                    "SUCCESS",
                )
                return {
                    "ok": True,
                    "reported": True,
                    "killer_name": eff_killer,
                    "town": town_key,
                    "town_label": town_label,
                    "guard_name": gname,
                    "guard_x": gx,
                    "guard_y": gy,
                    "method": confirm_method,
                }

            _log(
                f"⚠️ [Auto Report] Đã nói chuyện Lính Canh '{gname}' tại {town_label} nhưng chưa thấy xác nhận xóa KillerName.",
                "WARN",
            )
            # Đã gặp & gửi C1:30 tới Lính Canh 3 lần rồi -> không cần chạy vòng thêm các thành khác gây tốn thời gian
            return {
                "ok": True,
                "reported": False,
                "killer_name": eff_killer,
                "town": town_key,
                "town_label": town_label,
                "guard_name": gname,
                "reason": "talk_sent_unconfirmed",
            }
    except Exception as exc:
        _log(f"❌ [Auto Report] Lỗi khi đi tìm Lính Canh: {exc}", "ERROR")
        return {"ok": False, "reported": False, "error": str(exc)}

    _log("⚠️ [Auto Report] Không tìm thấy Lính Canh trong thời gian cho phép, tiếp tục chu trình Auto Train.", "WARN")
    return {"ok": False, "reported": False, "killer_name": eff_killer, "reason": "guard_not_found"}
