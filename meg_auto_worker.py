#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Smart AutoTrain Worker (Zero-Mouse Native Engine)
======================================================
Mô phỏng 100% thuật toán điều hướng và tự động cắm bãi của MEGAMU Auto Train Dashboard:
- Tuyệt đối KHÔNG đụng chuột, KHÔNG cướp tiêu điểm, KHÔNG click tọa độ màn hình.
- Sử dụng hàm native MoveTo (GameAssembly.dll + 0xD72750) để game tự A* pathfinding.
- Chuyển map chuẩn xác qua MapResolver (/move <map>) và xác thực Map ID từ Telemetry.
- Tự động bật MuHelper khi tới bãi và tự động recheck duy trì trạng thái farm.
- Tự động nhận diện Reset (Level giảm về 1), chờ hồi sinh và tự động chạy lại từ mốc 1.
- Tự động lên cấp và chuyển tiếp chặng bãi tiếp theo mà không dừng khựng.
"""

import os
import sys
import json
import time
import math
import threading
from typing import Optional, Dict, Any, List, Tuple, Callable
from datetime import datetime
try:
    import psutil
except ImportError:
    psutil = None

from meg_direct_engine import MegDirectEngine
try:
    from meg_crash_tracer import log_thread_exception
except ImportError:
    def log_thread_exception(*args, **kwargs): pass

CLASS_ID_TO_CODE = {
    0: "DW", 1: "DK", 2: "FE", 3: "MG", 4: "DL", 5: "SU", 6: "RF", 7: "GL",
    8: "RW", 9: "SL", 10: "GC", 11: "KM", 12: "LM", 13: "IK", 14: "AL", 15: "CR"
}
CLASS_CODE_TO_NAME = {
    "DW": "Dark Wizard (Phù Thủy)",
    "DK": "Dark Knight (Chiến Binh)",
    "FE": "Fairy Elf (Tiên Nữ)",
    "MG": "Magic Gladiator (Đấu Sĩ)",
    "DL": "Dark Lord (Chúa Tể)",
    "SU": "Summoner (Thuật Sĩ)",
    "RF": "Rage Fighter (Thiết Binh)",
    "GL": "Grow Lancer (Thương Thủ)",
    "RW": "Rune Wizard (Phù Thủy Rune)",
    "SL": "Slayer (Sát Thủ)",
    "GC": "Gun Crusher (Pháo Thủ)",
    "KM": "Kundun Mephis",
    "LM": "Lemuria",
    "IK": "Illusion Knight (Huyễn Ảnh)",
    "AL": "Alchemist (Giả Kim)",
    "CR": "Crusher"
}

class MapResolver:
    """
    Bộ phân giải lệnh chuyển map và Map ID chuẩn xác từ map_commands.json.
    (Khớp 100% cơ chế của MEGAMU Auto Train Dashboard gốc).
    """
    _instance = None

    def __init__(self, json_path: Optional[str] = None):
        self.aliases: Dict[str, str] = {}
        self.map_ids: Dict[str, int] = {}
        self.id_to_name: Dict[int, str] = {}
        self.display_names: List[str] = []

        candidate_paths = []
        if json_path:
            candidate_paths.append(json_path)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_paths.append(os.path.join(base_dir, "config", "map_commands.json"))
        candidate_paths.append(os.path.join(base_dir, "map_commands.json"))

        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            candidate_paths.append(os.path.join(exe_dir, "config", "map_commands.json"))
            candidate_paths.append(os.path.join(exe_dir, "map_commands.json"))
            if hasattr(sys, "_MEIPASS"):
                candidate_paths.append(os.path.join(sys._MEIPASS, "config", "map_commands.json"))
                candidate_paths.append(os.path.join(sys._MEIPASS, "map_commands.json"))

        found_path = None
        for p in candidate_paths:
            if p and os.path.exists(p):
                found_path = p
                break

        if found_path:
            try:
                with open(found_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("maps", []):
                    display_name = str(item.get("name", "")).strip()
                    command = str(item.get("command", "")).strip()
                    prefix = str(item.get("prefix", "/move")).strip() or "/move"
                    static_map_id = None
                    try:
                        raw_id = item.get("map_id")
                        if raw_id is not None:
                            static_map_id = int(raw_id)
                    except Exception:
                        pass

                    if display_name and display_name not in self.display_names:
                        self.display_names.append(display_name)

                    if static_map_id is not None and static_map_id not in self.id_to_name:
                        self.id_to_name[static_map_id] = display_name

                    if command.startswith("/"):
                        full_command = command
                    else:
                        full_command = f"{prefix} {command}".strip()

                    names = [display_name, command] + item.get("aliases", [])
                    for name in names:
                        norm = self._norm(name)
                        if norm:
                            self.aliases[norm] = full_command
                            if static_map_id is not None:
                                self.map_ids[norm] = static_map_id
            except Exception as e:
                print(f"[MapResolver] Lỗi đọc file map_commands.json: {e}", flush=True)

        # Tích hợp thêm cấu hình từ maps.ini (MAP_CATALOG & ALIASES)
        ini_candidates = [
            os.path.join(base_dir, "maps.ini"),
            os.path.join(base_dir, "config", "maps.ini"),
        ]
        if getattr(sys, "frozen", False):
            ini_candidates.append(os.path.join(exe_dir, "maps.ini"))
            ini_candidates.append(os.path.join(exe_dir, "config", "maps.ini"))
        for ip in ini_candidates:
            if ip and os.path.exists(ip):
                try:
                    import configparser
                    cp = configparser.ConfigParser(interpolation=None)
                    cp.read(ip, encoding="utf-8")
                    if "MAP_CATALOG" in cp:
                        for raw_id, map_name in cp["MAP_CATALOG"].items():
                            try:
                                m_id = int(str(raw_id).strip())
                                name_str = str(map_name).strip()
                                if m_id not in self.id_to_name:
                                    self.id_to_name[m_id] = name_str
                                norm_n = self._norm(name_str)
                                if norm_n and norm_n not in self.map_ids:
                                    self.map_ids[norm_n] = m_id
                                if name_str and name_str not in self.display_names:
                                    self.display_names.append(name_str)
                                if norm_n and norm_n not in self.aliases:
                                    clean_cmd = name_str.lower().replace(" ", "")
                                    self.aliases[norm_n] = f"/move {clean_cmd}"
                            except Exception:
                                pass
                    if "ALIASES" in cp:
                        for alias_k, cmd_v in cp["ALIASES"].items():
                            norm_k = self._norm(str(alias_k).strip())
                            cmd_clean = str(cmd_v).strip().lower()
                            if norm_k:
                                if cmd_clean.startswith("/"):
                                    self.aliases[norm_k] = cmd_clean
                                else:
                                    self.aliases[norm_k] = f"/move {cmd_clean}"
                                norm_cmd = self._norm(cmd_clean)
                                if norm_cmd in self.map_ids and norm_k not in self.map_ids:
                                    self.map_ids[norm_k] = self.map_ids[norm_cmd]
                    if "POPULAR_MAPS" in cp:
                        for _, pop_name in cp["POPULAR_MAPS"].items():
                            name_str = str(pop_name).strip()
                            if name_str and name_str not in self.display_names:
                                self.display_names.append(name_str)
                            norm_p = self._norm(name_str)
                            if norm_p and norm_p not in self.aliases:
                                clean_cmd = name_str.lower().replace(" ", "")
                                self.aliases[norm_p] = f"/move {clean_cmd}"
                    break
                except Exception as e_ini:
                    print(f"[MapResolver] Lỗi đọc maps.ini: {e_ini}", flush=True)

        # Luôn đăng ký Event Square với lệnh chuẩn /m ev
        for ev_key in ["ev", "eventsquare", "event square", "eventsq", "event"]:
            norm_ev = self._norm(ev_key)
            self.aliases[norm_ev] = "/m ev"
            self.map_ids[norm_ev] = 53
        self.id_to_name[53] = "Event Square"
        self.id_to_name[40] = "Event Square"
        if "Event Square" not in self.display_names:
            self.display_names.append("Event Square")

    @classmethod
    def get_instance(cls) -> "MapResolver":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_all_map_names(self) -> List[str]:
        """Trả về toàn bộ danh sách tên bản đồ đã hợp nhất từ map_commands.json và maps.ini."""
        return list(self.display_names)

    @staticmethod
    def _norm(text: str) -> str:
        return "".join(ch.lower() for ch in str(text).strip() if ch.isalnum())

    def resolve(self, value: str, alternate: bool = False) -> str:
        s = str(value).strip()
        if not s:
            return ""
        if s.startswith("/"):
            cmd = s
        else:
            norm = self._norm(s)
            if norm in self.aliases:
                cmd = self.aliases[norm]
            else:
                cmd = f"/move {s}"

        if alternate:
            if cmd.startswith("/move "):
                return "/warp " + cmd[6:]
            elif cmd.startswith("/warp "):
                return "/move " + cmd[6:]
            elif cmd.startswith("/m "):
                return "/warp " + cmd[3:]
        return cmd

    def expected_map_id(self, value: str) -> Optional[int]:
        norm = self._norm(value)
        if not norm:
            return None
        return self.map_ids.get(norm)

    def get_map_name(self, map_id: int) -> str:
        return self.id_to_name.get(map_id, f"Map #{map_id}")


class AutoTrainWorker:
    """
    Worker xử lý logic tự động chuyển map, di chuyển ra bãi và farm thông minh
    cho 1 Client MEGAMU (PID).
    """

    def __init__(
        self,
        pid: int,
        stages: List[Dict[str, Any]],
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        config: Optional[Dict[str, Any]] = None,
        slot_idx: int = 1
    ):
        self.pid = pid
        self.stages = stages
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.config = config or {}
        self.slot_idx = slot_idx

        # Core Direct Native Engine
        self.core = MegDirectEngine.get_engine(pid)
        self.map_resolver = MapResolver.get_instance()

        # Cấu hình chu kỳ Poll & Recheck
        base_poll = max(0.2, float(self.config.get("poll_interval", 0.55)))
        self.poll_interval = base_poll + ((slot_idx - 1) % 10) * 0.03
        self.stable_poll_interval = 0.22 + ((slot_idx - 1) % 8) * 0.004
        self.helper_recheck_interval = 2.5 + ((slot_idx - 1) % 5) * 0.15
        self.next_helper_check = 0.0

        # Trạng thái luồng
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_paused_for_event = False

        # Trạng thái di chuyển & Chặng
        self.current_stage_key = None
        self.current_target: Optional[Tuple[int, int]] = None
        self.arrived_at_spot = False
        self.last_level: Optional[int] = None
        self.last_px: Optional[int] = None
        self.last_py: Optional[int] = None
        self.last_dist: Optional[float] = None
        self.last_progress_log_time = 0.0
        self.last_move_issue = 0.0
        self.last_stride_time = 0.0
        self.last_moved_time = 0.0
        self.bypass_angle_offset = 0.0
        self.bypass_idx = 0
        self.last_helper_stop_check = 0.0

        # Tự động Reset & Cộng điểm Point
        self.last_reset_cmd_time = 0.0
        self.last_add_point_time = 0.0
        self.auto_reset = bool(self.config.get("auto_reset", False))
        self.auto_add_point = bool(self.config.get("auto_add_point", False))
        self.reset_level = int(self.config.get("reset_level", 400))
        self.stat_ratio = self.config.get("stat_ratio", {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0})

        # Đồng bộ sự kiện Devil Square
        self.last_devil_attempt_time = 0.0
        self.last_devil_gate_attempt = 0.0
        self.last_devil_attempt_hour = -1
        self.in_devil_square = False
        self.preparing_devil = False
        self.devil_entry_attempts = 0
        self.devil_no_ticket_hour = -1
        self.auto_devil = bool(self.config.get("auto_devil", False))
        self.devil_min_resets = int(self.config.get("devil_min_resets", 0))
        self.devil_max_resets = int(self.config.get("devil_max_resets", 9999))
        if self.devil_max_resets <= 0:
            self.devil_max_resets = 9999
        self.devil_ticket_type = str(self.config.get("devil_ticket_type", "auto")).lower()
        self.current_resets = int(self.config.get("resets", 0))
        self.last_devil_ineligible_log_hour = -1

        # Xử lý Hồi sinh / Reset Level
        self.respawn_until = 0.0
        self.respawn_armed = False
        self.reset_candidate_since = 0.0
        self.invalid_level_logged = False
        self.state_text = ""
        self.out_of_range_logged = False

        # Quản lý Đổi Map
        self.expected_map_id: Optional[int] = None
        self.route_map_name = ""
        self.map_wait_active = False
        self.map_command_sent_at = 0.0
        self.map_id_before_command: Optional[int] = None
        self.map_unknown_fallback_at = 0.0
        self.map_move_sent = False
        self.next_map_retry_at = 0.0
        self.map_retry_count = 0

    def _log(self, msg: str, level: str = "INFO"):
        if self.log_callback:
            try:
                self.log_callback(msg, level)
            except Exception:
                pass
        else:
            print(f"[{level}] {msg}", flush=True)

    def _set_state(self, st: str):
        self.state_text = st
        if self.progress_callback:
            try:
                self.progress_callback(st, 0)
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"AutoTrainWorker-{self.pid}")
        self.thread.start()

    def stop(self, reason: str = "Dừng Auto"):
        self.running = False
        self.stop_event.set()
        self.preparing_devil = False
        self.in_devil_square = False

        # Đợi worker thread kết thúc để tránh race condition gọi di chuyển dở dang
        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            try:
                self.thread.join(timeout=0.6)
            except Exception:
                pass

        if self.core:
            try:
                # 1. Tắt Auto Move nếu đang chạy
                if hasattr(self.core, "stop_auto_move"):
                    self.core.stop_auto_move()

                # 2. Tắt MuHelper an toàn
                self.core.stop_helper()

                # 3. Hãm phanh cố định nhân vật đứng yên tại vị trí hiện tại
                self.core.cancel_move()

                # Lấy tọa độ hiện tại để ghi log trạng thái dừng
                info = self.core.get_player_info(max_age=0.2)
                if info and info.get("tileX") and info.get("tileY"):
                    cx = int(info["tileX"])
                    cy = int(info["tileY"])
                    self._log(f"Đã dừng Auto [{reason}]: Nhân vật đứng yên tại ({cx}, {cy}), MuHelper đã TẮT.", "INFO")
                else:
                    self._log(f"Đã dừng Auto [{reason}]: Đã hãm phanh di chuyển và tắt MuHelper.", "INFO")
            except Exception as e:
                self._log(f"Lỗi khi dừng auto [{reason}]: {e}", "WARNING")
        else:
            self._log(f"Worker đã dừng [{reason}].", "INFO")

    def pause_for_event(self, reason: str = "Tạm dừng cho sự kiện"):
        """Tạm dừng AutoTrain để nhường quyền ưu tiên cho các sự kiện như Double Goer."""
        self.is_paused_for_event = True
        self._log(f"AutoTrain tạm dừng: {reason}", "INFO")
        if self.core:
            try:
                if hasattr(self.core, "stop_auto_move"):
                    self.core.stop_auto_move()
                self.core.cancel_move()
            except Exception:
                pass

    def resume_from_event(self, reason: str = "Khôi phục AutoTrain"):
        """Khôi phục AutoTrain và đặt lại mục tiêu để đưa nhân vật về bãi train."""
        self.is_paused_for_event = False
        self.current_stage_key = None
        self.arrived_at_spot = False
        self.map_move_sent = False
        self.map_wait_active = False
        self._log(f"AutoTrain khôi phục sau sự kiện: {reason}", "SUCCESS")

    def update_config(self, new_config: Dict[str, Any]):
        """Cập nhật cấu hình trực tiếp khi worker đang chạy (Hot-Reload thông minh)."""
        try:
            self.config.update(new_config)
            if "auto_devil" in new_config:
                self.auto_devil = bool(new_config["auto_devil"])
            if "devil_min_resets" in new_config:
                self.devil_min_resets = int(new_config["devil_min_resets"])
            if "devil_max_resets" in new_config:
                self.devil_max_resets = int(new_config["devil_max_resets"])
                if self.devil_max_resets <= 0:
                    self.devil_max_resets = 9999
            if "devil_ticket_type" in new_config:
                self.devil_ticket_type = str(new_config["devil_ticket_type"]).lower()
            if "resets" in new_config and int(new_config["resets"]) > 0:
                self.current_resets = int(new_config["resets"])
            if "auto_reset" in new_config:
                self.auto_reset = bool(new_config["auto_reset"])
            if "auto_add_point" in new_config:
                self.auto_add_point = bool(new_config["auto_add_point"])
            if "reset_level" in new_config:
                self.reset_level = int(new_config["reset_level"])
            if "stat_ratio" in new_config:
                self.stat_ratio = new_config["stat_ratio"]
            if "stat_mode" in new_config:
                self.config["stat_mode"] = new_config["stat_mode"]
            if "class_profiles" in new_config:
                self.config["class_profiles"] = new_config["class_profiles"]
            if "custom_class" in new_config:
                self.config["custom_class"] = new_config["custom_class"]
            if "min_add_points" in new_config:
                self.config["min_add_points"] = int(new_config["min_add_points"])

            new_stages = new_config.get("stages", [])
            if not new_stages:
                return

            # Nếu danh sách stages không có gì thay đổi so với hiện tại, TUYỆT ĐỐI không reset trạng thái!
            if self.stages == new_stages:
                return

            self.stages = new_stages

            # Đánh giá xem với level hiện tại, chặng mới có gì khác với chặng đang cắm không
            if self.last_level is not None:
                new_idx, new_stage = self._match_stage(self.last_level)
                if new_stage:
                    new_tx, new_ty = self._get_stage_target(new_stage)
                    new_key = (
                        new_idx,
                        int(new_stage.get("min_level", 1)),
                        int(new_stage.get("max_level", 400)),
                        str(new_stage.get("map_name") or new_stage.get("map", "")),
                        new_tx, new_ty
                    )
                    # Nếu chặng phù hợp cho level hiện tại KHÔNG ĐỔI và bot ĐÃ Ở BÃI, giữ nguyên trạng thái cắm bãi!
                    if new_key == self.current_stage_key and self.arrived_at_spot:
                        self._log(f"Cập nhật cấu hình: Chặng hiện tại ({new_stage.get('map_name')}) không đổi, giữ nguyên vị trí cắm bãi.", "INFO")
                        return

            # Chỉ reset lộ trình khi chặng thực sự thay đổi mục tiêu
            self.current_stage_key = None
            self.arrived_at_spot = False
            self.map_move_sent = False
            self.map_wait_active = False
            self._log(f"Đã nạp nóng cấu hình mới ({len(new_stages)} chặng)! Đang điều hướng lại theo chặng mới...", "SUCCESS")
        except Exception as e:
            self._log(f"Lỗi khi nạp nóng cấu hình: {e}", "ERROR")

    def _get_stage_target(self, stage: Dict[str, Any]) -> Tuple[int, int]:
        wps = stage.get("waypoints", [])
        if wps and isinstance(wps, list) and len(wps) > 0:
            last_wp = wps[-1]
            return int(last_wp.get("x", 0)), int(last_wp.get("y", 0))
        if "x" in stage and "y" in stage:
            return int(stage.get("x", 0)), int(stage.get("y", 0))
        return 0, 0

    def _match_stage(self, level: int) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Khớp chặng bãi train tương ứng với cấp độ nhân vật hiện tại (ưu tiên chặng cụ thể nhất)."""
        if not self.stages:
            return None, None
        if len(self.stages) == 1:
            return 0, self.stages[0]

        # Thu thập các chặng thỏa mãn min_level <= level <= max_level
        candidates = []
        for idx, stage in enumerate(self.stages):
            min_l = int(stage.get("min_level", 1))
            max_l = int(stage.get("max_level", 400))
            if min_l <= level <= max_l:
                candidates.append((idx, stage, max_l - min_l))

        if candidates:
            # Ưu tiên dải hẹp nhất (ví dụ chặng 400-400 ưu tiên trước 400-1000)
            candidates.sort(key=lambda c: (c[2], c[0]))
            best_idx, best_stage, _ = candidates[0]
            return best_idx, best_stage

        # Nếu level lớn hơn tất cả các chặng đã cấu hình, chọn chặng cuối
        if level > int(self.stages[-1].get("max_level", 400)):
            return len(self.stages) - 1, self.stages[-1]
        if level < int(self.stages[0].get("min_level", 1)):
            return 0, self.stages[0]

        return None, None

    def _reset_route_tracking(self, stage: Dict[str, Any]):
        map_name = stage.get("map_name") or stage.get("map", "")
        self.route_map_name = map_name
        self.expected_map_id = self.map_resolver.expected_map_id(map_name)

        # Lấy tọa độ đích từ waypoints[-1] hoặc stage['x'], stage['y']
        self.current_target = self._get_stage_target(stage)
        self.map_move_sent = False
        self.map_wait_active = False
        self.map_command_sent_at = 0.0
        self.map_id_before_command = None
        self.map_unknown_fallback_at = 0.0
        self.map_soft_verify_at = 0.0
        self.arrived_at_spot = False
        self.respawn_armed = False
        self.last_dist = None
        self.last_move_issue = 0.0
        self.map_sensor_trusted = False
        self.map_sensor_suspect = False
        self.map_retry_count = 0

    def _send_map_command(self, stage: Dict[str, Any], reason: str, current_map_id: Optional[int], use_alternate: bool = False) -> bool:
        map_name = stage.get("map_name") or stage.get("map", "")
        command = self.map_resolver.resolve(map_name, alternate=use_alternate)
        if not command:
            self._log(f"Stage has no map command for '{map_name}'.", "ERROR")
            return False

        x, y = self._get_stage_target(stage)
        self.route_map_name = str(map_name).strip()
        self.expected_map_id = self.map_resolver.expected_map_id(self.route_map_name)
        self.current_target = (x, y)

        # 1. Nếu cấu hình tắt auto_warp: Không gửi lệnh chuyển map, chỉ đi thẳng ra bãi
        if stage.get("auto_warp") is False:
            self._log(f"Bỏ qua lệnh chuyển map '{map_name}' (auto_warp tắt); chỉ cần đi thẳng tới tọa độ ({x}, {y}).", "SUCCESS")
            self._move_to_target_after_map_verified()
            return True

        # 2. Nếu nhân vật đã ở đúng Map ID: Tuyệt đối không dịch chuyển lại, chỉ cần đi đến tọa độ cần đến
        if current_map_id is not None and self.expected_map_id is not None:
            try:
                cur_id = int(current_map_id)
                exp_id = int(self.expected_map_id)
                if cur_id >= 0 and cur_id == exp_id:
                    self._log(
                        f"Nhân vật đã ở tại map '{map_name}' (MapID {exp_id}); "
                        f"không cần dịch chuyển lại, chỉ cần đi đến tọa độ ({x}, {y}).",
                        "SUCCESS"
                    )
                    self._move_to_target_after_map_verified()
                    return True
            except Exception:
                pass

        exp_str = f" [MapID: {self.expected_map_id}]" if self.expected_map_id is not None else ""
        self._log(f"{reason}: {command} -> ({x}, {y}){exp_str}")

        # TRƯỚC KHI GỬI LỆNH CHUYỂN MAP: TẮT MUHELPER VÀ HÃM PHANH DI CHUYỂN!
        # Game MU / MEGAMU chặn tuyệt đối lệnh /move khi đang bật auto đánh hoặc đang di chuyển (In-Combat / Busy)!
        try:
            self.core.stop_helper()
            self.core.cancel_move()
            time.sleep(0.35)  # Chờ 350ms để animation ra chiêu dừng hẳn và thoát trạng thái combat
        except Exception:
            pass

        if not self.core.send_chat(command):
            self._log("Could not send map command.", "WARNING")
            return False

        now = time.time()
        self.map_command_sent_at = now
        self.map_wait_active = True
        self.map_id_before_command = current_map_id
        self.map_unknown_fallback_at = now + max(4.0, float(self.config.get("map_verify_unknown_timeout", 6.0)))
        self.map_soft_verify_at = now + max(2.2, float(self.config.get("map_verify_grace_seconds", 2.8)))
        self.map_move_sent = False
        self.next_map_retry_at = now + max(3.5, float(self.config.get("map_command_retry_delay", 4.5)))
        self.arrived_at_spot = False
        self.respawn_armed = False
        self.last_move_issue = 0.0
        self.last_dist = None

        if self.expected_map_id is not None:
            self._set_state("MAP VERIFY")
        else:
            self._set_state("MAP ID UNKNOWN")
        return True

    def _move_to_target_after_map_verified(self):
        if not self.current_target or self.map_move_sent:
            return
        x, y = self.current_target
        now = time.time()
        self.bypass_angle_offset = 0.0
        self.last_move_issue = now
        self.last_stride_time = now
        self.last_moved_time = now
        self.map_sensor_trusted = True
        self.map_sensor_suspect = False
        self.map_retry_count = 0
        # Đảm bảo tắt MuHelper trước khi chạy để không vừa chạy vừa đánh quái dọc đường
        try:
            if self.core.is_helper_active():
                self.core.stop_helper()
        except Exception:
            pass
        if hasattr(self.core, "start_auto_move"):
            self.core.start_auto_move(x, y, helper=False)
        else:
            self.core.move_to(x, y, bypass_angle=0.0)
        self.map_move_sent = True
        self.map_wait_active = False
        self._set_state(f"CHẠY RA BÃI ({x}, {y})")
        self._log(f"Đã xác thực bản đồ; chỉ cần đi đến tọa độ ({x}, {y}).", "SUCCESS")

    def _route_map_gate(self, stage: Dict[str, Any], current_map_id: Optional[int]) -> bool:
        """
        Cổng kiểm soát chuyển bản đồ chuẩn v1.3.6 từ MEGAMU Dashboard gốc:
        - Khớp MapID lập tức chuyển trusted và cho phép chạy ra bãi.
        - Lệch MapID kích hoạt lệnh /move hoặc đi bộ qua cổng nếu chưa đủ level.
        - Chống kẹt: Tuyệt đối không ép nhân vật chạy tọa độ của map đích khi vẫn đang ở map cũ.
        """
        now = time.time()
        expected = self.map_resolver.expected_map_id(stage.get("map_name") or stage.get("map", ""))
        if expected is not None:
            self.expected_map_id = expected

        if self.expected_map_id is None:
            return False

        # 0. Nếu tắt auto_warp: Không kiểm soát cổng chuyển map, đi thẳng ra bãi
        if stage.get("auto_warp") is False:
            if not self.map_move_sent:
                self._move_to_target_after_map_verified()
            return False

        try:
            cur = int(current_map_id) if current_map_id is not None else -1
            exp = int(self.expected_map_id)
        except Exception:
            return False

        # 1. Đang tải map (cur < 0)
        if cur < 0:
            if self.map_wait_active and self.map_command_sent_at > 0:
                self._set_state("MAP VERIFY")
                if self.map_soft_verify_at > 0 and now >= self.map_soft_verify_at:
                    self.map_sensor_suspect = True
                    self.map_wait_active = False
                    self._log("MapID telemetry invalid after /move; using safe XY fallback for this route.", "WARNING")
                    self._move_to_target_after_map_verified()
                return True
            return False

        # 2. Đã đúng MapID mong muốn (cur == exp)
        if cur == exp:
            self.map_sensor_trusted = True
            self.map_sensor_suspect = False
            if self.map_wait_active or not self.map_move_sent:
                self._move_to_target_after_map_verified()
                return True
            return False

        # 3. Sensor đã từng trusted nhưng hiện tại bị lệch map
        if self.map_sensor_trusted and not self.map_wait_active:
            self._set_state(f"MAP WAIT {cur}→{exp}")
            self._send_map_command(stage, reason=f"Wrong map {cur}; expected {exp}", current_map_id=cur)
            return True

        # 4. Chưa gửi lệnh chuyển map lần nào
        if not self.map_wait_active and self.map_command_sent_at <= 0.0:
            self._set_state(f"MAP CHECK {cur}→{exp}")
            self._send_map_command(stage, reason=f"Map check {cur}; expected {exp}", current_map_id=cur)
            return True

        # 5. Đang trong thời gian chờ map sau khi đã gửi lệnh chuyển map
        if self.map_wait_active:
            if cur == exp:
                self.map_sensor_trusted = True
                self.map_sensor_suspect = False
                self._move_to_target_after_map_verified()
                return True

            # Thử lại lệnh chuyển map định kỳ nếu MapID vẫn chưa đổi
            if now >= self.next_map_retry_at:
                self.map_retry_count += 1
                self.next_map_retry_at = now + max(4.0, float(self.config.get("map_command_retry_delay", 5.0)))
                self._log(
                    f"MapID vẫn là {cur} (chưa chuyển sang {exp}) [Lần thử {self.map_retry_count}]. Đang thử lại lệnh chuyển map... "
                    "(Lưu ý: Nếu server game từ chối lệnh, hãy kiểm tra điều kiện Level tối thiểu và Zen của nhân vật)",
                    "WARNING"
                )

                # NẾU THỬ LẠI TỪ LẦN 1 TRỞ ĐI: CÓ THỂ NHÂN VẬT VỪA HỒI SINH BỊ KẸT TỌA ĐỘ / ĐÓNG BĂNG TRẠNG THÁI (RESPAWN FREEZE / NON-WARP TILE)
                # Tự động đóng dialog (ESC) và bước nhẹ 2-3 bước để gửi gói tin Move giải phóng trạng thái kẹt!
                if self.map_retry_count >= 1:
                    try:
                        # 1. Nhấn ESC đóng các pop-up/dialog/khung chat rác kẹt
                        hwnd = getattr(self.core, "get_hwnd", lambda: None)()
                        if hwnd:
                            from meg_direct_engine import MegDirectEngine
                            MegDirectEngine.send_background_key(hwnd, 0x1B, 0.05)  # VK_ESCAPE
                            time.sleep(0.12)

                        # 2. Lấy tọa độ hiện tại và nhích nhẹ 2-3 ô gỡ kẹt
                        pinfo = self.core.get_player_info(max_age=0.2)
                        if pinfo:
                            c_px = int(pinfo.get("tileX", 0))
                            c_py = int(pinfo.get("tileY", 0))
                            if c_px > 0 and c_py > 0:
                                jiggle_offsets = [(2, 2), (-2, 2), (2, -2), (-2, -2), (3, 0), (0, 3), (-3, 0), (0, -3)]
                                jox, joy = jiggle_offsets[(self.map_retry_count - 1) % len(jiggle_offsets)]
                                jx, jy = c_px + jox, c_py + joy
                                self._log(f"⚡ Nghi ngờ kẹt điểm hồi sinh/SafeZone tại ({c_px}, {c_py}); tự động bước sang ({jx}, {jy}) để mở khóa trạng thái trước khi warp...", "INFO")
                                if hasattr(self.core, "start_auto_move"):
                                    self.core.start_auto_move(jx, jy, helper=False)
                                else:
                                    self.core.move_to(jx, jy, bypass_angle=0.0)
                                time.sleep(0.55)
                                self.core.cancel_move()
                                time.sleep(0.15)
                    except Exception as e:
                        pass

                self._send_map_command(stage, reason=f"Thử lại chuyển map {cur}→{exp}", current_map_id=cur, use_alternate=True)
                return True

            # Quá thời gian kiểm chứng mềm CHỈ ÁP DỤNG KHI cur < 0 (sensor thực sự mất tín hiệu)
            if cur < 0 and self.map_soft_verify_at > 0 and now >= self.map_soft_verify_at:
                self.map_sensor_suspect = True
                self.map_wait_active = False
                self._log(
                    "MapID telemetry không xác định sau /move; áp dụng fallback XY an toàn cho chặng này.",
                    "WARNING"
                )
                self._move_to_target_after_map_verified()
                return True

            self._set_state(f"MAP CHECK {cur}→{exp}")
            return True

        return False

    def _go_to_stage(
        self,
        stage: Dict[str, Any],
        reason: str,
        current_map_id: Optional[int],
        force_command: bool = False,
        current_coords: Optional[Tuple[int, int]] = None
    ) -> bool:
        prev_map_name = self.route_map_name
        prev_expected = self.expected_map_id

        self._reset_route_tracking(stage)
        expected = self.expected_map_id
        map_name = stage.get("map_name") or stage.get("map", "")
        tx, ty = self.current_target if self.current_target else (0, 0)

        # Kiểm tra xem nhân vật đã ở tại map hay chưa
        already_at_map = False
        skip_reason = ""

        # A. Kiểm tra theo MapID từ Telemetry
        if current_map_id is not None and expected is not None:
            try:
                cur_id = int(current_map_id)
                exp_id = int(expected)
                if cur_id >= 0 and exp_id >= 0:
                    if cur_id == exp_id:
                        already_at_map = True
                        skip_reason = f"Đang ở đúng MapID {exp_id} ({map_name})"
                    else:
                        # Khác MapID: Nhân vật đang ở map khác (VD: ELF ở Noria MapID 3, hoặc ở Elbeland MapID 51 muốn về Lorencia MapID 0)
                        # Trong MEGAMU level đầu vẫn chuyển map bình thường -> Bắt buộc gửi lệnh chuyển map, không được coi là đã ở tại map!
                        already_at_map = False
            except Exception:
                pass

        # B. Kiểm tra nếu cùng tên bản đồ với chặng trước đó (chỉ áp dụng khi telemetry chưa xác định được MapID)
        if not already_at_map and (current_map_id is None or int(current_map_id) < 0):
            if prev_map_name and map_name:
                norm_prev = self.map_resolver._norm(prev_map_name)
                norm_new = self.map_resolver._norm(map_name)
                if norm_prev and norm_new and norm_prev == norm_new:
                    already_at_map = True
                    skip_reason = f"Cùng bản đồ '{map_name}' với chặng trước"

        # C. Cấu hình auto_warp = false
        if stage.get("auto_warp") is False:
            already_at_map = True
            skip_reason = "auto_warp đã tắt trong cấu hình"

        # Khi nhân vật thực sự ở tại map rồi thì không cần dịch chuyển lại, chỉ cần đi đến tọa độ cần đến
        if already_at_map and not force_command:
            self._log(
                f"{reason}: {skip_reason} -> Không cần dịch chuyển lại, chỉ cần đi đến tọa độ ({tx}, {ty}).",
                "SUCCESS"
            )
            self._move_to_target_after_map_verified()
            return True

        return self._send_map_command(stage, reason, current_map_id)

    def _ensure_helper(self, target_x: Optional[int] = None, target_y: Optional[int] = None, force_restart: bool = False) -> bool:
        """Đảm bảo bật Auto Đánh (MuHelper) khi đã tới bãi."""
        if not force_restart and self.core.is_helper_active(force_refresh=True):
            return True

        tx = int(target_x) if target_x is not None else (self.current_target[0] if self.current_target else 0)
        ty = int(target_y) if target_y is not None else (self.current_target[1] if self.current_target else 0)

        self._log(f"Đã tới bãi đích ({tx}, {ty}). Đang kích hoạt bật Auto Đánh (MuHelper)...", "SUCCESS")
        ok = self.core.start_helper(target_x=tx, target_y=ty, force_restart=force_restart)
        if ok or self.core.is_helper_active(force_refresh=True):
            self._log("🎉 Auto Đánh (MuHelper) đã BẬT thành công tại đúng tọa độ bãi.", "SUCCESS")
            return True

        self._log("Chưa phát hiện phản hồi bật MuHelper từ game; sẽ tự động thử lại ở chu kỳ tiếp theo...", "WARNING")
        return False

    def _get_stat_ratio_for_player(self, class_id: int) -> Tuple[str, Dict[str, float]]:
        """Lấy tỷ lệ cộng Point chuẩn theo Class hoặc theo cấu hình Tùy Chỉnh của người dùng."""
        stat_mode = self.config.get("stat_mode", "auto_class")
        custom_ratio = self.config.get("stat_ratio")

        # 1. Nếu người dùng chọn Tùy Chỉnh (Custom)
        if stat_mode == "custom" and custom_ratio and isinstance(custom_ratio, dict):
            c_code = self.config.get("custom_class") or CLASS_ID_TO_CODE.get(class_id, "CUSTOM")
            return c_code, custom_ratio

        # 2. Nếu chọn Theo Class (Tự Động)
        class_code = CLASS_ID_TO_CODE.get(class_id, "DK")
        profiles = None
        try:
            from pathlib import Path
            f_path = Path("config/class_stat_profiles.json")
            if not f_path.exists():
                f_path = Path(__file__).resolve().parent / "config" / "class_stat_profiles.json"
            if f_path.exists():
                profiles = json.loads(f_path.read_text(encoding="utf-8"))
        except Exception:
            profiles = None

        if not profiles:
            profiles = self.config.get("class_profiles")

        if profiles and class_code in profiles and "stat_ratio" in profiles[class_code]:
            return class_code, profiles[class_code]["stat_ratio"]

        # 3. Bảng mặc định chuẩn nếu không đọc được file
        defaults = {
            "DW": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "DK": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
            "FE": {"str": 0.15, "agi": 0.75, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
            "MG": {"str": 0.45, "agi": 0.35, "vit": 0.0, "ene": 0.2, "cmd": 0.0},
            "DL": {"str": 0.3, "agi": 0.3, "vit": 0.0, "ene": 0.1, "cmd": 0.3},
            "SU": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "RF": {"str": 0.5, "agi": 0.2, "vit": 0.3, "ene": 0.0, "cmd": 0.0},
            "GL": {"str": 0.55, "agi": 0.35, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
            "RW": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "SL": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
            "GC": {"str": 0.1, "agi": 0.5, "vit": 0.1, "ene": 0.3, "cmd": 0.0},
            "KM": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "LM": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "IK": {"str": 0.4, "agi": 0.5, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
            "AL": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0},
            "CR": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0},
        }
        return class_code, defaults.get(class_code, {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0})

    def _run(self):
        """Vòng lặp chính điều hướng và cắm bãi (Smart AutoTrain Main Loop)."""
        time.sleep(((self.slot_idx - 1) % 50) * 0.035)
        self._log(f"Smart AutoTrain worker đã bắt đầu (Chu kỳ poll: {self.poll_interval:.3f}s).", "SUCCESS")

        while self.running and not self.stop_event.is_set():
            now = time.time()
            try:
                # 0. Kiểm tra xem tiến trình game có còn tồn tại không
                if psutil and not psutil.pid_exists(self.pid):
                    self._log(f"Tiến trình MEGAMU.exe (PID {self.pid}) đã biến mất hoặc bị văng/crash. Luồng worker dừng lại.", "ERROR")
                    break

                # 1. Lấy thông tin nhân vật từ Fast Telemetry
                cache_age = 0.55 if not self.arrived_at_spot else 0.9
                info = self.core.get_player_info(max_age=cache_age)
                if info is None:
                    time.sleep(0.18)
                    continue

                level = int(info.get("level", 0))
                current_map_id = info.get("mapId", -1)
                px = int(info.get("tileX", 0))
                py = int(info.get("tileY", 0))
                is_moving = bool(info.get("isMoving", False))
                info_resets = int(info.get("resets", 0)) if info.get("resets") is not None else 0
                if info_resets > 0:
                    self.current_resets = info_resets
                elif self.current_resets <= 0:
                    if (now - getattr(self, "_last_reset_check_time", 0.0)) >= 5.0:
                        self._last_reset_check_time = now
                        try:
                            from meg_navigator import ProcessMemoryReader
                            r_title = ProcessMemoryReader.read_character_resets(self.pid)
                            if r_title is not None and r_title > 0:
                                self.current_resets = r_title
                        except Exception:
                            pass

                # 1.1. Đang trong map phó bản Double Goer (Map 65, 66, 67, 68) -> Tạm ngưng bãi train nhường quyền cho sự kiện
                if current_map_id in (65, 66, 67, 68):
                    time.sleep(self.poll_interval)
                    continue

                # 1.2. Nếu AutoTrain ĐANG TẠM DỪNG CHO SỰ KIỆN (Double Goer / Devil Square / ...)
                if self.is_paused_for_event:
                    is_near_lugard = (
                        (current_map_id in (53, 40) and math.hypot(px - 229, py - 22) <= 14) or
                        (current_map_id == 51 and math.hypot(px - 49, py - 216) <= 14)
                    )
                    if is_near_lugard:
                        if getattr(self, '_last_lugard_state_log', 0) != 1:
                            self._set_state(f'CHỜ SỰ KIỆN LUGARD ({px}, {py})')
                            self._log(f'📍 Nhân vật đang đứng tại NPC Lugard ({px}, {py}). Tạm ngưng bãi train nhường quyền cho sự kiện Double Goer.', 'INFO')
                            self._last_lugard_state_log = 1
                    time.sleep(max(1.0, self.poll_interval))
                    continue
                else:
                    self._last_lugard_state_log = 0

                # 2. Xử lý trạng thái nhân vật chưa tải xong
                if level <= 0:
                    if not self.invalid_level_logged:
                        self._log("Nhân vật đang tải cảnh hoặc chuyển đổi trạng thái...", "WARNING")
                        self.invalid_level_logged = True
                    time.sleep(max(0.45, self.poll_interval))
                    continue
                self.invalid_level_logged = False

                # 2.0. Tự động cộng point nếu có point chưa cộng (Hoạt động ở MỌI map: map ngoài, Devil Square, Blood Castle,...)
                if self.config.get("auto_add_point", False):
                    pts = int(info.get("points", 0))
                    min_pts = int(self.config.get("min_add_points", 1))
                    if pts >= min_pts and (now - self.last_add_point_time) >= 5.0:
                        self.last_add_point_time = now
                        class_id = int(info.get("classId", -1))
                        class_code, ratio = self._get_stat_ratio_for_player(class_id)

                        raw_str = pts * float(ratio.get("str", 0.0))
                        raw_agi = pts * float(ratio.get("agi", 0.0))
                        raw_vit = pts * float(ratio.get("vit", 0.0))
                        raw_ene = pts * float(ratio.get("ene", 0.0))
                        raw_cmd = pts * float(ratio.get("cmd", 0.0))

                        p_str = int(raw_str)
                        p_agi = int(raw_agi)
                        p_vit = int(raw_vit)
                        p_ene = int(raw_ene)
                        p_cmd = int(raw_cmd)

                        # Bù điểm dư do làm tròn số nguyên vào chỉ số có tỷ lệ cao nhất
                        rem = pts - (p_str + p_agi + p_vit + p_ene + p_cmd)
                        if rem > 0:
                            top_stat = max(ratio.items(), key=lambda x: x[1])[0]
                            if top_stat == "str": p_str += rem
                            elif top_stat == "agi": p_agi += rem
                            elif top_stat == "vit": p_vit += rem
                            elif top_stat == "ene": p_ene += rem
                            elif top_stat == "cmd": p_cmd += rem

                        if hasattr(self.core, "add_stats"):
                            stat_parts = []
                            if p_str > 0: stat_parts.append(f"Str +{p_str}")
                            if p_agi > 0: stat_parts.append(f"Agi +{p_agi}")
                            if p_vit > 0: stat_parts.append(f"Vit +{p_vit}")
                            if p_ene > 0: stat_parts.append(f"Ene +{p_ene}")
                            if p_cmd > 0: stat_parts.append(f"Cmd +{p_cmd}")
                            stat_desc = ", ".join(stat_parts) if stat_parts else "0"
                            self._log(f"⭐ Auto Cộng Point [{class_code}]: +{pts} pts ({stat_desc})", "SUCCESS")
                            self.core.add_stats(p_str, p_agi, p_vit, p_ene, p_cmd)

                # 2.1. Xử lý trạng thái đang trong Map Devil Square (Map 9 hoặc 32)
                is_in_ds = (current_map_id in (9, 32)) or (hasattr(self.core, 'is_devil_event_map') and self.core.is_devil_event_map())
                if is_in_ds:
                    if not self.in_devil_square:
                        self.in_devil_square = True
                        self.preparing_devil = False
                        self.devil_entry_attempts = 0
                        self._log(f"🔥 NHÂN VẬT ĐÃ VÀO DEVIL SQUARE (Map {current_map_id})! Bật MuHelper cày quái...", "SUCCESS")
                        self._set_state(f"DEVIL SQUARE ({px}, {py})")
                        self.core.cancel_move()
                        self.core.start_helper()
                    if now >= self.next_helper_check:
                        self._ensure_helper()
                        self.next_helper_check = now + self.helper_recheck_interval
                    time.sleep(self.stable_poll_interval)
                    continue
                elif self.in_devil_square:
                    # Trước đó đang ở trong DS mà giờ không còn ở map 9/32 -> Sự kiện kết thúc
                    self.in_devil_square = False
                    self.preparing_devil = False
                    self.current_stage_key = None
                    self.arrived_at_spot = False
                    try:
                        self.core.stop_helper()
                        self.core.cancel_move()
                    except Exception:
                        pass
                    self._log("🏁 Sự kiện Devil Square đã kết thúc / Nhân vật đã rời map DS.", "SUCCESS")
                    rs_lvl = int(self.config.get("reset_level", 400))
                    if (self.auto_reset or self.config.get("auto_reset", False)) and level >= rs_lvl:
                        self._log(f"⚡ Level {level} đạt mốc Reset ({rs_lvl}) sau Devil Square. Tự động thực hiện /reset...", "SUCCESS")
                        if hasattr(self.core, "do_reset"):
                            self.core.do_reset()
                        else:
                            self.core.send_chat("/reset")
                    else:
                        self._log(f"📍 Rời Devil Square với Level {level} (mốc reset: {rs_lvl}). Tự động định tuyến di chuyển ra bãi train...", "INFO")
                    time.sleep(2.0)
                    continue

                # 2.2. Kiểm tra lịch mở cổng Devil Square nếu bật tùy chọn auto_devil
                is_devil_enabled = self.auto_devil or self.config.get("auto_devil", False)
                if is_devil_enabled and not self.in_devil_square:
                    cur_dt = datetime.now()
                    is_odd_hour = (cur_dt.hour % 2 == 1)

                    # Khung giờ mở cổng chuẩn MEGAMU (Giờ lẻ :27 - :30, chuẩn bị trước 30s từ :26:30)
                    is_prep_window = is_odd_hour and (cur_dt.minute == 26 and cur_dt.second >= 30)
                    is_gate_open_window = is_odd_hour and ((cur_dt.minute == 27 and cur_dt.second >= 5) or (28 <= cur_dt.minute < 30))

                    if is_prep_window or is_gate_open_window:
                        min_rs = self.devil_min_resets
                        max_rs = self.devil_max_resets
                        cur_rs = self.current_resets

                        # 1. KIỂM TRA ĐIỀU KIỆN SỐ RESET:
                        if not (min_rs <= cur_rs <= max_rs):
                            if self.last_devil_ineligible_log_hour != cur_dt.hour:
                                self.last_devil_ineligible_log_hour = cur_dt.hour
                                self._log(
                                    f"⏰ Khung giờ Devil Square (:26-:30): Nhân vật hiện có {cur_rs} Reset "
                                    f"(yêu cầu mốc [{min_rs} - {max_rs}] Reset). "
                                    f"Bỏ qua Devil, tiếp tục cắm bãi train bình thường.",
                                    "INFO"
                                )
                            # Nếu nhân vật lỡ đang ở Event Square mà không đủ reset thì kéo về bãi train
                            if self.preparing_devil or current_map_id in (53, 40):
                                self.preparing_devil = False
                                self.current_stage_key = None
                                self.arrived_at_spot = False
                            # CHƯA ĐỦ RESET: KHÔNG DỪNG TRAIN! Trôi tiếp xuống dưới để Auto Train bình thường

                        else:
                            # 2. ĐỦ RESET -> KIỂM TRA VÉ TRONG HÒM ĐỒ THEO ĐÚNG LOẠI VÉ ĐÃ CẤU HÌNH
                            t_pref = getattr(self, "devil_ticket_type", "auto").lower()
                            t_info = self.core.get_devil_ticket_info() if hasattr(self.core, "get_devil_ticket_info") else {}

                            has_valid_ticket = False
                            ticket_desc = ""
                            if t_pref == "master":
                                has_valid_ticket = bool(t_info.get("hasMasterTicket") and t_info.get("masterCount", 0) > 0)
                                ticket_desc = f"Vé Master ({t_info.get('masterCount', 0)} vé)"
                            elif t_pref == "normal":
                                has_valid_ticket = bool(t_info.get("hasNormalTicket") and t_info.get("normalCount", 0) > 0)
                                ticket_desc = f"Vé Thường ({t_info.get('normalCount', 0)} vé)"
                            else:  # "auto"
                                has_valid_ticket = bool(t_info.get("hasTicket") and t_info.get("count", 0) > 0)
                                if t_info.get("hasMasterTicket"):
                                    ticket_desc = f"Vé Master ({t_info.get('masterCount', 0)} vé)"
                                else:
                                    ticket_desc = f"Vé Thường ({t_info.get('normalCount', 0)} vé)"

                            if not has_valid_ticket:
                                if self.devil_no_ticket_hour != cur_dt.hour:
                                    self.devil_no_ticket_hour = cur_dt.hour
                                    type_str = "Vé Master" if t_pref == "master" else ("Vé Thường" if t_pref == "normal" else "Vé Devil Square")
                                    self._log(f"❌ Khung giờ Devil Square: Không tìm thấy {type_str} trong hòm đồ! Bỏ qua Devil, tiếp tục cắm bãi train.", "WARNING")
                                if self.preparing_devil or current_map_id in (53, 40):
                                    self.preparing_devil = False
                                    self.current_stage_key = None
                                    self.arrived_at_spot = False
                                # KHÔNG CÓ VÉ HỢP LỆ: KHÔNG DỪNG TRAIN! Trôi tiếp xuống dưới để Auto Train bình thường

                            else:
                                if self.devil_no_ticket_hour != -2:
                                    self.devil_no_ticket_hour = -2
                                    self._log(f"🎫 Phát hiện {ticket_desc} hợp lệ trong hòm đồ. Chuẩn bị tham gia Devil Square...", "INFO")

                                # 3. ĐỦ RESET VÀ CÓ VÉ HỢP LỆ -> TIẾP CẬN CỔNG EVENT SQUARE
                                if not self.preparing_devil:
                                    self.preparing_devil = True
                                    self.arrived_at_spot = False
                                    self.current_stage_key = None
                                    self._log(f"⏰ Khung giờ Devil Square ({cur_dt.strftime('%H:%M:%S')}) [Reset {cur_rs} ({min_rs}-{max_rs}) | {ticket_desc}]! Tạm chuyển hướng vào cổng...", "INFO")
                                    try:
                                        self.core.stop_helper()
                                        self.core.cancel_move()
                                        if hasattr(self.core, "stop_auto_move"):
                                            self.core.stop_auto_move()
                                    except Exception:
                                        pass

                                # Chuyển sang Event Square (Map 53 hoặc 40)
                                if current_map_id not in (53, 40):
                                    if (now - self.last_devil_attempt_time) >= 6.0:
                                        self.last_devil_attempt_time = now
                                        self._log("📍 Đang chuyển sang Event Square (/m ev) để đi Devil Square...", "INFO")
                                        self.core.send_chat("/m ev")
                                        self._set_state("CHUYỂN SANG EVENT SQUARE")
                                    time.sleep(0.8)
                                    continue

                                # Nhân vật đã ở Event Square: Tiếp cận vị trí NPC Charon (225, 52)
                                if abs(px - 225) > 5 or abs(py - 52) > 5:
                                    if hasattr(self.core, "start_auto_move"):
                                        self.core.start_auto_move(225, 52, helper=False)
                                    elif hasattr(self.core, "move_to"):
                                        self.core.move_to(225, 52)
                                    self._set_state("DEVIL: TIẾP CẬN CHARON (225, 52)")
                                    time.sleep(0.8)
                                    continue
                                else:
                                    if hasattr(self.core, "cancel_move"):
                                        self.core.cancel_move()

                                if is_prep_window:
                                    self._set_state("DEVIL: CHỜ CỔNG MỞ (NPC CHARON)")
                                    time.sleep(0.8)
                                    continue

                                if is_gate_open_window:
                                    # Tiến hành gửi lệnh vào cửa native mỗi 1.8s
                                    if (now - self.last_devil_gate_attempt) >= 1.8:
                                        self.last_devil_gate_attempt = now
                                        self.devil_entry_attempts += 1
                                        self._set_state(f"DEVIL: ĐANG VÀO CỔNG... (#{self.devil_entry_attempts})")
                                        if self.devil_entry_attempts % 3 == 1:
                                            self._log(f"🚪 Đang gửi lệnh native vào Devil Square (Lần {self.devil_entry_attempts} - {ticket_desc})...", "INFO")
                                        res = self.core.enter_devil(ticket_preference=t_pref) if hasattr(self.core, "enter_devil") else {}
                                        if res.get("success") or res.get("ok"):
                                            self._log(f"✅ Đã gửi lệnh vào Devil Square! Chờ xác nhận map...", "SUCCESS")
                                    time.sleep(0.5)
                                    continue

                    else:
                        # 4. NGOÀI KHUNG GIỜ MỞ CỔNG:
                        # Nếu trước đó đang chuẩn bị mà KHÔNG VÀO ĐƯỢC MAP (Hết giờ, phòng đầy, server lỗi):
                        if self.preparing_devil:
                            self.preparing_devil = False
                            self.devil_entry_attempts = 0
                            self._log(f"⏰ Đã hết khung giờ mở cổng Devil Square ({cur_dt.strftime('%H:%M:%S')}) mà không vào được. Tự động QUAY LẠI BÃI TRAIN ngay lập tức!", "WARNING")
                            self.current_stage_key = None
                            self.arrived_at_spot = False
                            # Sẽ tự động trôi xuống logic Auto Train và đưa nhân vật về bãi train!

                # 2.3. Kiểm tra Auto Reset nếu bật cấu hình
                if self.config.get("auto_reset", False) and level >= int(self.config.get("reset_level", 400)):
                    if (now - self.last_reset_cmd_time) >= 15.0:
                        self.last_reset_cmd_time = now
                        self._log(f"⚡ Level {level} đạt mốc Reset ({self.config.get('reset_level', 400)}). Đang gửi lệnh /reset...", "SUCCESS")
                        self.core.send_chat("/reset")
                        time.sleep(1.0)
                        continue

                # 3. Phát hiện Reset (Level từ > 1 giảm xuống 1)
                if self.last_level is not None and self.last_level > 1 and level == 1:
                    if self.reset_candidate_since <= 0:
                        self.reset_candidate_since = now
                        self._log("Phát hiện nhân vật đạt Level 1 (Reset); đang xác nhận...")
                    confirm_s = float(self.config.get("reset_confirm_seconds", 1.5))
                    if (now - self.reset_candidate_since) < confirm_s:
                        time.sleep(max(0.35, self.poll_interval))
                        continue

                    self.current_resets += 1
                    self._log(f"🎉 Xác nhận nhân vật vừa Reset! (Tổng Reset: {self.current_resets}). Đang chờ khởi tạo lại...")
                    time.sleep(float(self.config.get("level1_delay", 4.0)))
                    self.current_stage_key = None
                    self.arrived_at_spot = False
                    self.reset_candidate_since = 0.0
                    self._set_state("")

                self.last_level = level

                # 4. Khớp chặng bãi train tương ứng với Level
                idx, stage = self._match_stage(level)
                if not stage:
                    if not self.out_of_range_logged:
                        self._log(f"Level {level} không nằm trong chặng nào đã cấu hình. Tạm dừng di chuyển.", "WARNING")
                        self.out_of_range_logged = True
                    time.sleep(0.75)
                    continue
                self.out_of_range_logged = False

                # Tạo khóa nhận diện chặng (bất biến từ cấu hình stage)
                tx, ty = self._get_stage_target(stage)
                stage_key = (
                    idx,
                    int(stage.get("min_level", 1)),
                    int(stage.get("max_level", 400)),
                    str(stage.get("map_name") or stage.get("map", "")),
                    tx, ty
                )

                # 5. Nếu chuyển chặng mới -> bắt đầu chuyển map hoặc chạy tới bãi mới
                if stage_key != self.current_stage_key:
                    self.current_stage_key = stage_key
                    stg_title = stage.get("name", f"Chặng #{idx + 1}")
                    map_str = stage.get("map_name") or stage.get("map", "")
                    self._log(f"Level {level} khớp {stg_title} [{stage.get('min_level')}-{stage.get('max_level')}] tại '{map_str}'.")
                    self._go_to_stage(stage, reason=f"Bắt đầu {stg_title}", current_map_id=current_map_id, current_coords=(px, py))
                    time.sleep(0.3)
                    continue

                # 6. Kiểm tra cổng chuyển map (Safe Map Gate matching v1.3.6)
                if self._route_map_gate(stage, current_map_id):
                    time.sleep(min(0.7, max(0.25, self.poll_interval)))
                    continue

                # 7. Di chuyển tới bãi train (Movement & Anti-Stuck Tracking)
                if not self.current_target:
                    time.sleep(0.5)
                    continue

                tx, ty = self.current_target
                dist = math.hypot(px - tx, py - ty)
                arrive_thresh = max(4.0, float(self.config.get("arrive_distance", self.config.get("arrival_distance", 4.0))))

                # Trường hợp bãi không yêu cầu tọa độ (tx=0, ty=0) -> tự đánh ngay khi vào map
                if tx == 0 and ty == 0:
                    if not self.arrived_at_spot:
                        self.arrived_at_spot = True
                        self.core.cancel_move()
                        self._log(f"🎉 ĐÃ VÀO MAP ({px}, {py})! Kích hoạt Auto Đánh (MuHelper)...", "SUCCESS")
                        self._set_state(f"TỰ ĐỘNG ĐÁNH ({px}, {py})")
                        self.next_helper_check = now + self.helper_recheck_interval
                        if stage.get("auto_attack", True):
                            self._ensure_helper()
                    if now >= self.next_helper_check:
                        if stage.get("auto_attack", True):
                            self._ensure_helper()
                        self.next_helper_check = now + self.helper_recheck_interval
                    time.sleep(self.stable_poll_interval)
                    continue

                # A. Đã tới đích bãi train
                # Hysteresis Leash:
                # - Khi chưa tới bãi: Cần tiếp cận sát đích (dist <= 1.2 ô) HOẶC đứng yên sát bãi (dist <= arrive_thresh và not is_moving)
                #   TUYỆT ĐỐI không bật helper khi nhân vật vẫn đang chạy (is_moving) để tránh ghim sai tọa độ gốc!
                # - Khi ĐÃ tới bãi: cho phép MuHelper tự do di chuyển săn quái trong bán kính cắm bãi camp_leash (14.0 ô).
                #   Chỉ khi nào bị chết văng về thành (dist > camp_leash) mới coi là rời bãi để bắt đầu lộ trình chạy lại.
                camp_leash = max(14.0, float(self.config.get("respawn_distance", 15.0)))
                raw_arrive = float(self.config.get("arrive_distance", self.config.get("arrival_distance", 1.5)))
                arrive_thresh = max(1.0, min(2.0, raw_arrive))

                if self.arrived_at_spot:
                    is_arrived = (dist <= camp_leash)
                else:
                    is_at_spot = (dist <= 1.2) or (dist <= arrive_thresh and not is_moving)
                    is_arrived = is_at_spot and (not is_moving)

                if is_arrived:
                    if not self.arrived_at_spot:
                        self.arrived_at_spot = True
                        if hasattr(self.core, "stop_auto_move"):
                            self.core.stop_auto_move()
                        self.core.cancel_move()

                        # Chờ 350ms để nhân vật dừng hẳn quán tính và đứng yên hoàn toàn tại đúng tọa độ bãi
                        time.sleep(0.35)

                        # Cập nhật lại tọa độ thực tế sau khi dừng hẳn
                        latest_info = self.core.get_player_info(max_age=0.1)
                        if latest_info:
                            px = int(latest_info.get("tileX", px))
                            py = int(latest_info.get("tileY", py))
                            dist = math.hypot(px - tx, py - ty)

                        self._log(f"🎉 ĐÃ ĐỨNG YÊN TẠI BÃI ({px}, {py}) [Mục tiêu: ({tx}, {ty}) | Lệch: {dist:.1f} ô]! Kích hoạt Auto Đánh (MuHelper)...", "SUCCESS")
                        self._set_state(f"TỰ ĐỘNG ĐÁNH ({tx}, {ty})")

                        if stage.get("auto_attack", True):
                            # Force restart để đảm bảo MuHelper lưu đúng tọa độ bãi (tx, ty) làm tọa độ gốc cắm bãi
                            self._ensure_helper(target_x=tx, target_y=ty, force_restart=True)
                        self.next_helper_check = now + self.helper_recheck_interval

                    # Kiểm tra định kỳ để giữ MuHelper luôn BẬT khi đang cắm bãi
                    if now >= self.next_helper_check:
                        if stage.get("auto_attack", True):
                            self._ensure_helper(target_x=tx, target_y=ty, force_restart=False)
                        self.next_helper_check = now + self.helper_recheck_interval

                    self.last_dist = dist
                    self.last_px = px
                    self.last_py = py
                    time.sleep(self.stable_poll_interval)
                    continue

                # B. Đang trên đường chạy ra bãi (Continuous Sprint Navigation)
                self.arrived_at_spot = False
                self.next_helper_check = 0.0

                # ĐẢM BẢO TẮT MUHELPER TRONG SUỐT QUÁ TRÌNH CHẠY RA BÃI (chưa tới đích)
                # Tuyệt đối không để MuHelper bật sớm trước khi đến vị trí
                if (now - self.last_helper_stop_check) >= 0.75:
                    self.last_helper_stop_check = now
                    try:
                        if self.core.is_helper_active():
                            self._log(f"Đang trên đường chạy tới ({tx}, {ty}) [còn {dist:.1f} ô]; tắt MuHelper để tập trung di chuyển...", "INFO")
                            self.core.stop_helper()
                    except Exception:
                        pass

                if (now - self.last_progress_log_time) >= 1.5:
                    self._log(f"Đang tự tìm đường tới ({tx}, {ty}) [Hiện tại: ({px}, {py})] | Cự ly còn: {dist:.1f} ô...")
                    self._set_state(f"ĐANG CHẠY ({dist:.0f} ô)")
                    self.last_progress_log_time = now

                # 1. Giám sát dịch chuyển tọa độ & phát hiện vật cản
                if (px, py) != (self.last_px, self.last_py):
                    self.last_moved_time = now
                    if self.last_dist is not None and dist < self.last_dist:
                        # Đang tiến gần hơn tới đích -> trả lại góc chạy thẳng
                        self.bypass_angle_offset = 0.0
                else:
                    # Đứng yên tại 1 ô: Nếu quá 1.1s không đổi tọa độ -> có vật cản/hàng rào
                    if self.last_moved_time > 0 and (now - self.last_moved_time) >= 1.1:
                        bypass_angles = [55.0, -55.0, 85.0, -85.0, 120.0, -120.0]
                        self.bypass_angle_offset = bypass_angles[self.bypass_idx % len(bypass_angles)]
                        self.bypass_idx += 1
                        self._log(f"Gặp vật cản tại ({px}, {py}). Lách tiếp tuyến {self.bypass_angle_offset:+.0f}° để vượt chướng ngại vật...")
                        self.last_moved_time = now

                # 2. Sải bước liên tục mỗi 0.85s để nhân vật duy trì chạy một mạch không khựng
                if not self.running or self.stop_event.is_set():
                    break

                time_since_stride = now - self.last_stride_time
                need_stride = (
                    (self.last_stride_time == 0.0) or
                    (time_since_stride >= 0.85) or
                    (self.bypass_angle_offset != 0.0 and time_since_stride >= 0.40)
                )

                if need_stride:
                    if self.last_stride_time == 0.0:
                        self._log(f"Bắt đầu chạy ra bãi: ({px}, {py}) ➔ ({tx}, {ty}) [Còn {dist:.1f} ô]...")

                    if self.bypass_angle_offset == 0.0:
                        is_am_active = hasattr(self.core, "is_auto_move_active") and self.core.is_auto_move_active()
                        if not is_am_active or not is_moving:
                            if hasattr(self.core, "start_auto_move"):
                                self.core.start_auto_move(tx, ty, helper=False)
                            else:
                                self.core.move_to(tx, ty, bypass_angle=0.0)
                    else:
                        if hasattr(self.core, "is_auto_move_active") and self.core.is_auto_move_active():
                            if hasattr(self.core, "stop_auto_move"):
                                self.core.stop_auto_move()
                        self.core.move_to(tx, ty, bypass_angle=self.bypass_angle_offset)

                    self.last_stride_time = now
                    self.last_move_issue = now
                    if self.last_moved_time == 0.0:
                        self.last_moved_time = now

                self.last_dist = dist
                self.last_px = px
                self.last_py = py
                time.sleep(0.12)
            except Exception as e:
                log_thread_exception(
                    source=f"AutoWorker-{self.pid}",
                    exc=e,
                    thread_name=f"Slot{self.slot_idx:02d}_AutoTrainWorker",
                    details=f"Slot: {self.slot_idx}, PID: {self.pid}, Char: {self.char_name or 'N/A'}"
                )
                self._log(f"Lỗi vòng lặp worker: {e} -> Xem chi tiết tại auto_crash_trace.log", "ERROR")
                time.sleep(0.5)
