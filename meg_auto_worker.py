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

from meg_direct_engine import MegDirectEngine

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

        if not json_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, "map_commands.json")

        if json_path and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
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

    @classmethod
    def get_instance(cls) -> "MapResolver":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _norm(text: str) -> str:
        return "".join(ch.lower() for ch in str(text).strip() if ch.isalnum())

    def resolve(self, value: str) -> str:
        s = str(value).strip()
        if not s:
            return ""
        if s.startswith("/"):
            return s
        norm = self._norm(s)
        if norm in self.aliases:
            return self.aliases[norm]
        return f"/move {s}"

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
        self.map_soft_verify_at = 0.0

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

    def stop(self):
        self.running = False
        self.stop_event.set()
        if self.core and self.core.is_ready:
            try:
                self.core.cancel_move()
            except Exception:
                pass

    def _get_stage_target(self, stage: Dict[str, Any]) -> Tuple[int, int]:
        wps = stage.get("waypoints", [])
        if wps and isinstance(wps, list) and len(wps) > 0:
            last_wp = wps[-1]
            return int(last_wp.get("x", 0)), int(last_wp.get("y", 0))
        if "x" in stage and "y" in stage:
            return int(stage.get("x", 0)), int(stage.get("y", 0))
        return 0, 0

    def _match_stage(self, level: int) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Khớp chặng bãi train tương ứng với cấp độ nhân vật hiện tại."""
        if not self.stages:
            return None, None
        if len(self.stages) == 1:
            return 0, self.stages[0]

        for idx, stage in enumerate(self.stages):
            min_l = int(stage.get("min_level", 1))
            max_l = int(stage.get("max_level", 400))
            if min_l <= level <= max_l:
                return idx, stage

        # Nếu level lớn hơn tất cả các chặng đã cấu hình (ví dụ lv 400), chọn chặng cuối
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
        self.arrived_at_spot = False
        self.last_dist = None
        self.last_move_issue = 0.0

    def _send_map_command(self, stage: Dict[str, Any], reason: str, current_map_id: Optional[int]) -> bool:
        map_name = stage.get("map_name") or stage.get("map", "")
        command = self.map_resolver.resolve(map_name)
        if not command:
            self._log(f"Không thể phân giải lệnh chuyển map cho '{map_name}'.", "WARNING")
            return False

        exp_str = f" [MapID: {self.expected_map_id}]" if self.expected_map_id is not None else ""
        self._log(f"{reason}: Gửi lệnh chuyển map '{command}'{exp_str}...")

        if not self.core.send_chat(command):
            self._log("Không thể gửi lệnh chat chuyển map.", "WARNING")
            return False

        now = time.time()
        self.map_command_sent_at = now
        self.map_wait_active = True
        self.map_id_before_command = current_map_id
        self.map_unknown_fallback_at = now + max(4.0, float(self.config.get("map_verify_unknown_timeout", 6.0)))
        self.map_move_sent = False
        self.map_soft_verify_at = now + max(2.2, float(self.config.get("map_verify_grace_seconds", 2.8)))
        self.arrived_at_spot = False
        self.respawn_armed = False
        self.last_move_issue = 0.0
        self.last_dist = None

        if self.expected_map_id is not None:
            self._set_state(f"XÁC THỰC MAP {self.expected_map_id}")
        else:
            self._set_state("CHỜ VÀO MAP MỚI")
        return True

    def _move_to_target_after_map_verified(self):
        if not self.current_target or self.map_move_sent:
            return
        x, y = self.current_target
        self.core.move_to(x, y)
        self.last_move_issue = time.time()
        self.map_move_sent = True
        self.map_wait_active = False
        self._set_state(f"CHẠY RA BÃI ({x}, {y})")
        self._log(f"Đã xác thực bản đồ; game đang tự tìm đường tới bãi ({x}, {y}).", "SUCCESS")

    def _go_to_stage(self, stage: Dict[str, Any], reason: str, current_map_id: Optional[int], force_command: bool = False) -> bool:
        self._reset_route_tracking(stage)
        expected = self.expected_map_id

        # Nếu đã ở đúng map thì chạy thẳng tới bãi luôn
        if not force_command and expected is not None and current_map_id is not None:
            try:
                if int(current_map_id) == int(expected):
                    self._log(f"{reason}: Đã ở đúng MapID {expected}; chạy thẳng tới bãi {self.current_target}.", "SUCCESS")
                    self._move_to_target_after_map_verified()
                    return True
            except Exception:
                pass

        # Nếu cấu hình tắt auto_warp thì không gửi lệnh chuyển map mà chạy luôn
        if stage.get("auto_warp") is False:
            self._log(f"{reason}: Bỏ qua chuyển map (auto_warp tắt); chạy thẳng tới bãi {self.current_target}.", "SUCCESS")
            self._move_to_target_after_map_verified()
            return True

        return self._send_map_command(stage, reason, current_map_id)

    def _ensure_helper(self) -> bool:
        """Đảm bảo bật Auto Đánh (MuHelper) khi đã tới bãi."""
        if self.core.is_helper_active():
            return True

        self._log("Auto Đánh (MuHelper) đang Tắt. Đang bật...")
        self.core.start_helper()

        deadline = time.time() + float(self.config.get("helper_native_timeout", 3.5))
        while self.running and time.time() < deadline:
            time.sleep(0.35)
            if self.core.is_helper_active():
                self._log("Auto Đánh (MuHelper) đã BẬT thành công.", "SUCCESS")
                return True

        # Fallback bật trực tiếp trạng thái RAM nếu hàm gọi native bị trễ
        if self.config.get("helper_direct_fallback", True):
            if hasattr(self.core, "_call"):
                self.core._call("setHelperStateDirect", 1)
                time.sleep(0.25)
                if self.core.is_helper_active():
                    self._log("Auto Đánh đã được kích hoạt qua direct state fallback.", "SUCCESS")
                    return True
        return False

    def _run(self):
        """Vòng lặp chính điều hướng và cắm bãi (Smart AutoTrain Main Loop)."""
        time.sleep(((self.slot_idx - 1) % 50) * 0.035)
        self._log(f"Smart AutoTrain worker đã bắt đầu (Chu kỳ poll: {self.poll_interval:.3f}s).", "SUCCESS")

        while self.running and not self.stop_event.is_set():
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

            # 2. Xử lý trạng thái nhân vật chưa tải xong
            if level <= 0:
                if not self.invalid_level_logged:
                    self._log("Nhân vật đang tải cảnh hoặc chuyển đổi trạng thái...", "WARNING")
                    self.invalid_level_logged = True
                time.sleep(max(0.45, self.poll_interval))
                continue
            self.invalid_level_logged = False

            # 3. Phát hiện Reset (Level từ > 1 giảm xuống 1)
            if self.last_level is not None and self.last_level > 1 and level == 1:
                now_mono = time.monotonic()
                if self.reset_candidate_since <= 0:
                    self.reset_candidate_since = now_mono
                    self._log("Phát hiện nhân vật đạt Level 1 (Reset); đang xác nhận...")
                confirm_s = float(self.config.get("reset_confirm_seconds", 1.5))
                if (now_mono - self.reset_candidate_since) < confirm_s:
                    time.sleep(max(0.35, self.poll_interval))
                    continue

                self._log("Xác nhận nhân vật vừa Reset! Đang chờ khởi tạo lại...")
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
                self._go_to_stage(stage, reason=f"Bắt đầu {stg_title}", current_map_id=current_map_id)
                time.sleep(0.3)
                continue

            # 6. Kiểm tra cổng đổi map (Gate Verification)
            now = time.time()
            if self.map_wait_active:
                expected = self.expected_map_id
                map_matched = False
                if expected is not None and current_map_id is not None:
                    try:
                        map_matched = (int(current_map_id) == int(expected))
                    except Exception:
                        pass

                # A. Map đã khớp chính xác
                if map_matched:
                    self._log(f"Đã vào map '{self.route_map_name}' (MapID {current_map_id}) thành công!", "SUCCESS")
                    self._move_to_target_after_map_verified()
                    time.sleep(0.3)
                    continue

                # B. Hết thời gian chờ xác thực mềm (Grace Period 2.8s)
                # Tự động xuất phát ra bãi nếu nhân vật đã ở sẵn trong map hoặc MapID không cập nhật kịp
                if self.map_soft_verify_at > 0 and now >= self.map_soft_verify_at:
                    self._log(f"Đã hết thời gian chờ chuyển map ({self.route_map_name}). Kích hoạt tự tìm đường ra bãi {self.current_target}...", "SUCCESS")
                    self._move_to_target_after_map_verified()
                    time.sleep(0.3)
                    continue

                # C. Thử lại nếu chờ quá 10s
                if (now - self.map_command_sent_at) > 10.0:
                    self._log(f"Chờ đổi map '{self.route_map_name}' quá 10s. Gửi lại lệnh...", "WARNING")
                    self._send_map_command(stage, reason="Thử lại đổi map", current_map_id=current_map_id)

                time.sleep(0.35)
                continue

            # 7. Di chuyển tới bãi train (Movement & Anti-Stuck Tracking)
            if not self.current_target:
                time.sleep(0.5)
                continue

            tx, ty = self.current_target
            dist = math.hypot(px - tx, py - ty)
            arrive_thresh = float(self.config.get("arrival_distance", 2.0))

            # A. Đã tới đích bãi train
            if dist <= arrive_thresh:
                if not self.arrived_at_spot:
                    self.arrived_at_spot = True
                    self.core.cancel_move()
                    self._log(f"🎉 ĐÃ TỚI BÃI TRAIN ({px}, {py})! Khoảng cách tới đích: {dist:.1f} ô.", "SUCCESS")
                    self._set_state(f"TẠI BÃI ({tx}, {ty})")
                    if stage.get("auto_attack", True):
                        self._ensure_helper()

                # Kiểm tra định kỳ để giữ MuHelper luôn BẬT khi đang cắm bãi
                if now >= self.next_helper_check:
                    if stage.get("auto_attack", True):
                        self._ensure_helper()
                    self.next_helper_check = time.monotonic() + self.helper_recheck_interval

                self.last_dist = dist
                self.last_px = px
                self.last_py = py
                time.sleep(self.stable_poll_interval)
                continue

            # B. Đang trên đường chạy ra bãi
            self.arrived_at_spot = False
            self.next_helper_check = 0.0

            if (now - self.last_progress_log_time) >= 2.0:
                self._log(f"Đang tự tìm đường tới ({tx}, {ty}) | Cự ly còn: {dist:.1f} ô...")
                self._set_state(f"ĐANG CHẠY ({dist:.0f} ô)")
                self.last_progress_log_time = now

            # Phát hiện kẹt (Stuck Check): đứng yên tại 1 ô hoặc cự ly không giảm sau 3.5s
            stuck_retry = float(self.config.get("stuck_retry_delay", 3.5))
            time_since_move = now - self.last_move_issue
            is_stuck = False
            if self.last_dist is not None and dist >= (self.last_dist - 0.25) and time_since_move >= stuck_retry:
                is_stuck = True
            elif px == self.last_px and py == self.last_py and time_since_move >= stuck_retry:
                is_stuck = True

            if is_stuck or self.last_move_issue == 0.0:
                self.core.move_to(tx, ty)
                self.last_move_issue = now
                if is_stuck:
                    self._log(f"Khựng bước tại ({px}, {py}). Tự động kích hoạt lại MoveTo tới bãi ({tx}, {ty}) [Còn {dist:.1f} ô]...")
                else:
                    self._log(f"Bắt đầu chạy ra bãi: ({px}, {py}) ➔ ({tx}, {ty}) [Còn {dist:.1f} ô]...")

            self.last_dist = dist
            self.last_px = px
            self.last_py = py
            time.sleep(0.2)
