"""
Core Module: SlotController.
Quản lý tiến trình, IPC Direct Engine, Train Worker, Moss Merchant, và Double Goer cho từng Slot tài khoản.
"""

import os
import time
import json
import threading
import ctypes
import psutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple

from core.constants import CLASS_ID_TO_CODE, CLASS_CODE_TO_NAME
from core.i18n import tr
from core.process_utils import record_auto_stop_log, character_name_from_window_title, is_megamu_process_alive
from core.storage import ConfigPersistenceManager
from services.train_service import TrainService
from meg_direct_engine import MegDirectEngine
from meg_auto_worker import AutoTrainWorker

try:
    from meg_crash_tracer import log_thread_exception
except ImportError:
    def log_thread_exception(*args, **kwargs): pass

try:
    import license_client
except ImportError:
    try:
        from core import license_client
    except ImportError:
        license_client = None

try:
    from test_entity_radar import MemoryScanner
except ImportError:
    MemoryScanner = None

try:
    from meg_direct_engine import ProcessMemoryReader
except ImportError:
    ProcessMemoryReader = None


class SlotController:
    """Điều khiển logic và trạng thái của từng dòng trong danh sách 10 tài khoản."""

    def __init__(self, slot_idx: int, app: 'DashboardApp', default_profile: int = 1):
        self.slot_idx = slot_idx
        self.app = app
        self.profile_index = default_profile

        self.assigned_pid: Optional[int] = None
        self.char_name = "---"
        self.last_known_char_name = ""
        self.level = "---"
        self.coords = "--,--"
        self.status = tr("idle")
        self.auto_requested = False
        self.is_moving: bool = False

        self.engine: Optional[MegDirectEngine] = None
        self.worker: Optional[AutoTrainWorker] = None
        self.last_sync_time = 0.0

        # Cấu hình Moss Merchant riêng cho Slot này
        self.moss_enabled: bool = True
        self.moss_category: int = 0
        self.moss_delay_ms: int = 1000
        self.moss_max_rolls: int = 0
        self.moss_auto_clean: bool = True
        self.moss_rolls_count: int = 0
        self.moss_running: bool = False
        self.moss_worker_thread: Optional[threading.Thread] = None
        self.moss_paused_worker: bool = False
        self.moss_initial_slots: set = set()

        # Cấu hình Double Goer (Mirror) riêng cho Slot này
        self.mirror_enabled: bool = True
        self.mirror_running: bool = False
        self.mirror_worker_thread: Optional[threading.Thread] = None
        self.mirror_sniping: bool = False
        self.mirror_snipe_thread: Optional[threading.Thread] = None
        self._mirror_lock = threading.Lock()
        self.resume_auto_train_after_mirror: bool = False
        self._mirror_dungeon_running: bool = False

        # Điểm Point & Master Point đọc từ RAM/Engine
        self.points: int = 0
        self.master_points: int = 0
        self.class_id: int = -1
        self.class_code: str = ""

        # Cấu hình Devil Square & Auto Reset & Point riêng cho Slot này
        self.auto_devil: bool = False
        self.devil_min_resets: int = 0
        self.devil_max_resets: int = 9999
        self.devil_ticket_type: str = "auto"
        self.current_resets: int = 0
        self.auto_reset: bool = False
        self.auto_add_point: bool = False
        self.reset_level: int = 400
        self.stat_mode: str = "auto_class"
        self.custom_class: str = ""
        self.stat_ratio: Dict[str, float] = {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0}

        try:
            evt_cfgs = ConfigPersistenceManager.load_event_configs()
            if self.slot_idx in evt_cfgs:
                s_evt = evt_cfgs[self.slot_idx]
                self.auto_devil = bool(s_evt.get("auto_devil", False))
                self.devil_min_resets = int(s_evt.get("devil_min_resets", 0))
                self.devil_max_resets = int(s_evt.get("devil_max_resets", 9999))
                if self.devil_max_resets <= 0:
                    self.devil_max_resets = 9999
                self.devil_ticket_type = str(s_evt.get("devil_ticket_type", "auto"))
                self.auto_reset = bool(s_evt.get("auto_reset", False))
                self.auto_add_point = bool(s_evt.get("auto_add_point", False))
                self.reset_level = int(s_evt.get("reset_level", 400))
                self.stat_mode = str(s_evt.get("stat_mode", "auto_class"))
                self.custom_class = str(s_evt.get("custom_class", ""))
                if isinstance(s_evt.get("stat_ratio"), dict):
                    self.stat_ratio = s_evt["stat_ratio"]
        except Exception:
            pass

    def set_profile(self, profile_idx: int):
        """Thay đổi Profile và lưu ngay vào file JSON."""
        old_idx = self.profile_index
        new_idx = max(1, min(10, int(profile_idx)))
        if old_idx == new_idx:
            return
        self.profile_index = new_idx
        ConfigPersistenceManager.save_slot_assignment(self.slot_idx, self.profile_index)

        # Nếu đang chạy Auto, nạp config mới từ file và update worker trực tiếp
        if self.worker and self.worker.running:
            cfg = ConfigPersistenceManager.load_single_profile(self.profile_index)
            if hasattr(self.worker, 'update_config'):
                self.worker.update_config(cfg)
            self.app.log_message(
                f"[Slot {self.slot_idx:02d}] Chuyển cấu hình trực tiếp: C{old_idx} -> C{self.profile_index}. Re-routing ngay!",
                "SUCCESS"
            )
            self.set_status(tr("running", n=self.profile_index))

    def attach_pid(self, pid: int) -> bool:
        """Kết nối tới Game PID."""
        if not pid or not is_megamu_process_alive(pid):
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Tiến trình MEGAMU (PID {pid}) không tồn tại hoặc đã đóng!", "WARNING")
            self.set_status(tr("game_closed"))
            return False

        # Nếu đang gán PID khác thì dọn dẹp PID cũ
        if self.assigned_pid and self.assigned_pid != pid:
            old_p = self.assigned_pid
            if MegDirectEngine:
                MegDirectEngine.release_engine(old_p)
            self.engine = None

        self.assigned_pid = pid

        # Nạp tức thì tên nhân vật và level từ tiêu đề cửa sổ / RAM để hiển thị ngay lập tức
        title = self.app.detected_games.get(pid, "")
        t_name = character_name_from_window_title(title)
        if not t_name:
            try:
                from meg_navigator import ProcessMemoryReader
                t_name = ProcessMemoryReader.read_character_name(pid) or ""
            except Exception:
                pass
        if t_name:
            self.char_name = t_name
            self.last_known_char_name = t_name

        try:
            from meg_navigator import ProcessMemoryReader
            t_lvl = ProcessMemoryReader._fallback_level_from_title(pid) or ProcessMemoryReader.read_character_level(pid)
            if t_lvl:
                self.level = str(t_lvl)
            live = ProcessMemoryReader.read_live_state(pid)
            if live and live[2] is not None and live[3] is not None and (live[2] > 0 or live[3] > 0):
                self.coords = f"{live[2]},{live[3]}"
        except Exception:
            pass

        self.app.update_slot_ui_telemetry(self.slot_idx, self.char_name, self.level, self.coords)

        self.set_status(tr("connected_status"))
        if MegDirectEngine:
            def _async_engine_connect():
                try:
                    eng = MegDirectEngine.get_engine(pid)
                    if not eng.is_ready:
                        ok = eng.attach()
                        if ok:
                            self.app.log_message(f"[Slot {self.slot_idx:02d}] Kết nối thành công MEGAMU (PID {pid}).", "SUCCESS")
                        else:
                            self.app.log_message(f"[Slot {self.slot_idx:02d}] Kết nối MEGAMU (PID {pid}) qua chế độ RAM telemetry.", "INFO")
                    self.engine = eng
                except Exception:
                    pass
            threading.Thread(target=_async_engine_connect, daemon=True, name=f"EngineAttach_Slot{self.slot_idx:02d}").start()
        return True

    def reconnect_game(self) -> bool:
        """
        Kết nối lại thông minh cho Slot khi bị mất kết nối hoặc game mở lại:
        1. Quét mới tiến trình qua self.app.refresh_games().
        2. Nếu self.assigned_pid còn tồn tại trên Windows -> Kết nối lại PID này.
        3. Nếu self.assigned_pid đã chết hoặc chưa gán:
           - Dọn dẹp engine cũ của PID chết.
           - Tìm trong các PID chưa được gán cho slot khác:
             + Tìm theo tên nhân vật (self.last_known_char_name hoặc self.char_name).
             + Nếu không có tên trùng khớp, lấy PID trống đầu tiên.
           - Gán PID mới, attach, cập nhật UI và dropdown.
        """
        self.app.refresh_games()
        living_games = self.app.detected_games

        # Trường hợp 1: PID hiện tại vẫn còn sống
        if self.assigned_pid and is_megamu_process_alive(self.assigned_pid):
            if MegDirectEngine:
                if self.engine:
                    ok = self.engine.reconnect()
                else:
                    self.engine = MegDirectEngine.get_engine(self.assigned_pid)
                    ok = self.engine.attach()
            else:
                ok = True

            self.sync_telemetry()
            self.set_status(tr("connected_status"))
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Đã kết nối lại thành công MEGAMU (PID {self.assigned_pid}).", "SUCCESS")
            return True

        # Trường hợp 2: PID hiện tại đã chết hoặc rỗng -> Tìm kiếm PID mới
        old_pid = self.assigned_pid
        if old_pid and MegDirectEngine:
            MegDirectEngine.release_engine(old_pid)
        self.engine = None
        self.assigned_pid = None

        # Lấy danh sách PID đã được các slot khác gán (chỉ tính PID còn sống)
        other_assigned_pids = {
            c.assigned_pid for c in self.app.controllers
            if c != self and c.assigned_pid and is_megamu_process_alive(c.assigned_pid)
        }
        available_pids = [p for p in living_games.keys() if p not in other_assigned_pids]

        if not available_pids:
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Không tìm thấy tiến trình MEGAMU mới nào đang chạy để kết nối lại.", "WARNING")
            self.set_status(tr("game_closed"))
            return False

        # Tìm kiếm theo tên nhân vật trước đó
        target_name = (self.last_known_char_name or (self.char_name if self.char_name != "---" else "")).strip().lower()
        matched_pid = None

        if target_name:
            for cand_pid in available_pids:
                cand_title = living_games.get(cand_pid, "")
                cand_name = character_name_from_window_title(cand_title)
                if not cand_name:
                    try:
                        from meg_navigator import ProcessMemoryReader
                        cand_name = ProcessMemoryReader.read_character_name(cand_pid) or ""
                    except Exception:
                        pass
                if cand_name and cand_name.strip().lower() == target_name:
                    matched_pid = cand_pid
                    break

        if matched_pid is None:
            matched_pid = available_pids[0]

        ok = self.attach_pid(matched_pid)
        if ok:
            el = self.app.slot_ui_elements.get(self.slot_idx)
            if el and el.get("proc_var"):
                title = living_games.get(matched_pid, "")
                cname = character_name_from_window_title(title) or self.char_name
                disp = f"{cname} ({matched_pid})" if (cname and cname != "---") else f"MEGAMU ({matched_pid})"
                el["proc_var"].set(disp)

            self.app.update_header_stats()
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Tự động nhận diện và kết nối lại MEGAMU (PID {matched_pid}) thành công!", "SUCCESS")
            return True
        return False

    def send_auto_login(self, server: int = 1, account: str = "", character: str = "", password: str = "") -> bool:
        """Gửi lệnh AutoLogin native vào client MEGAMU được gán cho Slot này."""
        if not self.engine or not self.engine.is_ready:
            if self.assigned_pid and is_megamu_process_alive(self.assigned_pid):
                self.attach_pid(self.assigned_pid)
        if self.engine and self.engine.is_ready:
            res = self.engine.auto_login(server=server, account=account, character=character, password=password)
            if res.get("ok"):
                self.app.log_message(f"[Slot {self.slot_idx:02d}] Đã gửi AutoLogin thành công: Server {server}, Acc '{account}', NV '{character}'", "SUCCESS")
                return True
            else:
                self.app.log_message(f"[Slot {self.slot_idx:02d}] AutoLogin thất bại: {res}", "WARNING")
        return False

    def detach(self):
        """Ngắt kết nối."""
        self.stop_moss()
        if hasattr(self, "stop_mirror_auto"):
            self.stop_mirror_auto()
        if hasattr(self, "stop_mirror_turbo_sniping"):
            self.stop_mirror_turbo_sniping()
        self.stop_auto(reason="Người dùng ngắt kết nối slot hoặc đổi gán game", trigger_by="MANUAL")
        old_pid = self.assigned_pid
        self.assigned_pid = None
        self.char_name = "---"
        self.level = "---"
        self.coords = "--,--"
        self.set_status(tr("idle"))
        if MegDirectEngine and old_pid:
            MegDirectEngine.release_engine(old_pid)
        if old_pid:
            try:
                from meg_navigator import ProcessMemoryReader
                ProcessMemoryReader.close_handle(old_pid)
            except Exception:
                pass
        self.engine = None

    def start_auto(self) -> bool:
        if getattr(self.app, "is_update_mandatory", False):
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Không thể chạy: Có bản cập nhật mới bắt buộc! Vui lòng cập nhật chương trình.", "ERROR")
            self.set_auto(False)
            self.app.open_update_dialog()
            return False

        if license_client and not license_client.is_license_valid():
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Không thể chạy: Bản quyền chưa kích hoạt hoặc đã hết hạn!", "ERROR")
            self.set_auto(False)
            return False

        if license_client and not license_client.has_license_module("train"):
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Không thể chạy: Bản quyền chưa kích hoạt Module Train Auto!", "ERROR")
            self.set_auto(False)
            return False

        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            # Tự động thử kết nối lại nếu có game đang mở
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Game đang mất kết nối. Đang tự động kết nối lại...", "INFO")
            ok_reconn = self.reconnect_game()
            if not ok_reconn:
                self.set_status(tr("game_closed"))
                self.set_auto(False)
                return False

        # Tự động đồng bộ nếu người dùng vừa sửa ở Tab Editor
        if hasattr(self.app, 'save_editor_to_file'):
            try:
                self.app.save_editor_to_file(silent=True)
            except Exception:
                pass

        # Đọc cấu hình tươi mới 100% từ file đĩa JSON!
        cfg = ConfigPersistenceManager.load_single_profile(self.profile_index)
        cfg["auto_devil"] = self.auto_devil
        cfg["devil_min_resets"] = self.devil_min_resets
        cfg["devil_max_resets"] = self.devil_max_resets
        cfg["devil_ticket_type"] = getattr(self, "devil_ticket_type", "auto")
        cfg["resets"] = self.current_resets
        cfg["auto_reset"] = self.auto_reset
        cfg["auto_add_point"] = self.auto_add_point
        cfg["reset_level"] = self.reset_level
        cfg["stat_mode"] = self.stat_mode
        cfg["custom_class"] = self.custom_class
        cfg["stat_ratio"] = self.stat_ratio
        cfg["class_profiles"] = ConfigPersistenceManager.load_class_stat_profiles()
        stages = cfg.get("stages", [])
        if not stages:
            self.app.log_message(f"[Slot {self.slot_idx:02d}] Config {self.profile_index} chưa thiết lập chặng!", "ERROR")
            self.set_auto(False)
            return False

        stage_summary = "; ".join([
            f"C{i+1}:Lv{s.get('min_level')}-{s.get('max_level')} {s.get('map_name')}({s.get('x')},{s.get('y')})"
            for i, s in enumerate(stages)
        ])
        self.app.log_message(
            f"[Slot {self.slot_idx:02d}] BẬT AUTO C{self.profile_index} ({len(stages)} chặng): {stage_summary}",
            "SUCCESS"
        )

        def worker_log(msg, lvl="INFO"):
            self.app.log_message(f"[Slot {self.slot_idx:02d}] {msg}", lvl)

        def worker_progress(st, _):
            self.set_status(st)

        self.worker = TrainService.get_instance().start_train_worker(
            slot_idx=self.slot_idx,
            pid=self.assigned_pid,
            stages=stages,
            config=cfg,
            log_callback=worker_log,
            progress_callback=worker_progress
        )
        self.auto_requested = True
        self.set_auto(True)
        self.set_status(tr("running", n=self.profile_index))
        return True

    def stop_auto(self, reason: str = "Người dùng chủ động tắt Auto", trigger_by: str = "MANUAL"):
        worker = self.worker
        self.worker = None
        was_auto = self.auto_requested
        self.auto_requested = False
        self.set_auto(False)

        if self.assigned_pid and is_megamu_process_alive(self.assigned_pid):
            self.set_status(tr("connected_status"))
        else:
            self.set_status(tr("idle"))

        # Ghi log chi tiết nếu slot thực sự đang chạy auto
        if was_auto or worker:
            record_auto_stop_log(
                slot_idx=self.slot_idx,
                pid=self.assigned_pid,
                char_name=self.char_name,
                trigger_type=trigger_by,
                reason=reason,
                coords=self.coords,
                level=str(self.level)
            )

            prefix = "🛑 [NGƯỜI DÙNG DỪNG]" if trigger_by.upper() == "MANUAL" else "⚠️ [HỆ THỐNG TỰ DỪNG]"
            log_level = "WARNING" if trigger_by.upper() == "MANUAL" else "ERROR"
            self.app.log_message(
                f"[Slot {self.slot_idx:02d}] {prefix} {reason} (NV: '{self.char_name}', PID: {self.assigned_pid or 'N/A'}).",
                log_level
            )

        # Chạy dọn dẹp worker thread và engine trong background để KHÔNG BAO GIỜ làm đơ (Not Responding) giao diện UI!
        def _stop_cleanup():
            TrainService.get_instance().stop_train_worker(self.slot_idx, reason=reason)
            eng = self.engine
            if eng and getattr(eng, "is_ready", False):
                try:
                    eng.stop_helper()
                    eng.cancel_move()
                except Exception:
                    pass

        threading.Thread(target=_stop_cleanup, daemon=True).start()

    def _pause_train_for_mirror(self, reason: str = ""):
        """Tạm dừng AutoTrain cho Slot khi sự kiện Mirror bắt đầu."""
        with self._mirror_lock:
            if self.auto_requested or (self.worker and self.worker.running):
                self.resume_auto_train_after_mirror = True
                TrainService.get_instance().pause_train_worker(self.slot_idx, reason=reason)

    def _resume_train_after_mirror(self, reason: str = ""):
        """Khôi phục AutoTrain cho Slot sau khi sự kiện Mirror kết thúc hoặc hết thời gian chờ."""
        with self._mirror_lock:
            if self.resume_auto_train_after_mirror:
                self.resume_auto_train_after_mirror = False
                TrainService.get_instance().resume_train_worker(self.slot_idx, reason=reason)
                if hasattr(self, "start_auto"):
                    threading.Thread(target=self.start_auto, daemon=True).start()

    def toggle_auto(self):
        if self.auto_requested or (self.worker and self.worker.running):
            self.stop_auto(reason="Người dùng bấm nút Tắt Auto trên dòng tài khoản", trigger_by="MANUAL")
        else:
            threading.Thread(target=self.start_auto, daemon=True).start()

    def set_status(self, text: str):
        self.status = text
        self.app.update_slot_ui_status(self.slot_idx, text)

    def set_auto(self, is_on: bool):
        self.auto_requested = is_on
        self.app.update_slot_ui_auto(self.slot_idx, is_on)

    def sync_telemetry(self):
        """Đọc RAM thông tin nhân vật hiển thị lên bảng."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            if self.assigned_pid:
                p_closed = self.assigned_pid
                c_closed = self.char_name
                if self.char_name and self.char_name != "---":
                    self.last_known_char_name = self.char_name
                self.set_status(tr("game_closed"))
                self.char_name = "---"
                self.level = "---"
                self.coords = "--,--"
                if MegDirectEngine:
                    MegDirectEngine.release_engine(p_closed)
                try:
                    from meg_navigator import ProcessMemoryReader
                    ProcessMemoryReader.close_handle(p_closed)
                except Exception:
                    pass
                self.engine = None
                if self.auto_requested or self.worker:
                    self.stop_auto(
                        reason=f"Tiến trình game MEGAMU.exe (PID {p_closed} - {c_closed}) đã bị đóng hoặc bị văng/crash!",
                        trigger_by="SYSTEM"
                    )
            return

        p_info = None
        if self.engine:
            try:
                p_info = self.engine.get_player_info(max_age=1.5, allow_blocking=False)
            except Exception:
                pass

        # Fallback đọc trực tiếp RAM nếu engine chưa có thông tin (Single-Pass Fast Snapshot)
        if not p_info:
            try:
                from meg_navigator import ProcessMemoryReader
                if hasattr(ProcessMemoryReader, "read_full_player_snapshot"):
                    p_info = ProcessMemoryReader.read_full_player_snapshot(self.assigned_pid)
                else:
                    live = ProcessMemoryReader.read_live_state(self.assigned_pid)
                    lvl = ProcessMemoryReader.read_character_level(self.assigned_pid)
                    p_info = {
                        "level": lvl or 0,
                        "tileX": live[2] if live and live[2] is not None else 0,
                        "tileY": live[3] if live and live[3] is not None else 0,
                    }
            except Exception:
                pass

        # Lấy tên nhân vật từ window title hoặc ProcessMemoryReader (chỉ truy vấn khi chưa có tên để tiết kiệm CPU)
        t_name = self.char_name if (self.char_name and self.char_name != "---") else ""
        if not t_name:
            title = self.app.detected_games.get(self.assigned_pid, "")
            t_name = character_name_from_window_title(title)
            if not t_name:
                try:
                    from meg_navigator import ProcessMemoryReader
                    t_name = ProcessMemoryReader.read_character_name(self.assigned_pid) or ""
                except Exception:
                    pass
            if t_name:
                self.char_name = t_name

        if p_info:
            self.is_moving = bool(p_info.get("isMoving", False))
            p_name = p_info.get("name", "")
            p_lvl = p_info.get("level", 0)
            px = p_info.get("tileX", p_info.get("x", 0))
            py = p_info.get("tileY", p_info.get("y", 0))

            if px == 0 and py == 0:
                try:
                    from meg_navigator import ProcessMemoryReader
                    live = ProcessMemoryReader.read_live_state(self.assigned_pid)
                    if live and live[2] is not None and live[3] is not None and (live[2] > 0 or live[3] > 0):
                        px, py = live[2], live[3]
                        p_info["tileX"] = px
                        p_info["tileY"] = py
                except Exception:
                    pass

            if p_name:
                self.char_name = p_name
            elif t_name:
                self.char_name = t_name

            if p_lvl > 0:
                self.level = str(p_lvl)
            elif self.level == "---":
                try:
                    from meg_navigator import ProcessMemoryReader
                    t_lvl = ProcessMemoryReader._fallback_level_from_title(self.assigned_pid)
                    if t_lvl:
                        self.level = str(t_lvl)
                except Exception:
                    pass

            if px > 0 or py > 0:
                self.coords = f"{px},{py}"

            if "points" in p_info:
                try:
                    self.points = int(p_info.get("points", 0))
                except Exception:
                    pass
            if "masterPoints" in p_info:
                try:
                    self.master_points = int(p_info.get("masterPoints", 0))
                except Exception:
                    pass
            if "classId" in p_info:
                try:
                    cid = int(p_info.get("classId", -1))
                    if cid >= 0:
                        self.class_id = cid
                        self.class_code = CLASS_ID_TO_CODE.get(cid, "")
                except Exception:
                    pass
            if "resets" in p_info:
                try:
                    r_val = int(p_info.get("resets", 0))
                    if r_val > 0:
                        self.current_resets = r_val
                except Exception:
                    pass

            # Luồng ngầm: Nếu chưa có số lần reset, chủ động đọc từ bộ nhớ (Throttle 5 giây chống nghẽn Win32)
            now_ts = time.time()
            if getattr(self, "current_resets", 0) <= 0 and self.assigned_pid:
                if (now_ts - getattr(self, "_last_reset_sync_time", 0.0)) >= 5.0:
                    self._last_reset_sync_time = now_ts
                    try:
                        from meg_navigator import ProcessMemoryReader
                        if hasattr(ProcessMemoryReader, "read_character_resets"):
                            r_mem = ProcessMemoryReader.read_character_resets(self.assigned_pid) or 0
                            if r_mem > 0:
                                self.current_resets = r_mem
                    except Exception:
                        pass

            self.app.update_slot_ui_telemetry(self.slot_idx, self.char_name, self.level, self.coords, points=self.points, class_code=self.class_code)
        elif self.char_name != "---" or self.level != "---":
            self.app.update_slot_ui_telemetry(self.slot_idx, self.char_name, self.level, self.coords, points=self.points, class_code=self.class_code)

    def start_moss(self) -> bool:
        """Kích hoạt Auto Quay Moss cho riêng slot này theo cấu hình đã cài đặt."""
        if self.moss_running:
            return True

        if license_client and not license_client.has_license_module("moss"):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Bản quyền chưa kích hoạt Module Moss Merchant!")
            return False

        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game hoặc Game đã thoát!")
            return False

        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Không tìm thấy Direct Engine!")
            return False
        if not eng.is_ready:
            eng.attach()

        # 1. Tạm dừng Auto Train nếu đang chạy để tránh xung đột di chuyển / giữ bãi
        if self.worker or self.auto_requested:
            self.moss_paused_worker = True
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏸️ Tạm dừng Auto Train để quay Moss...")
            self.stop_auto("Tạm dừng Auto Train để quay Moss", trigger_by="EVENT")
            time.sleep(0.3)

        # 2. Tắt MuHelper nếu đang bật để không gây gián đoạn
        if eng.is_helper_active(force_refresh=True):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚔️ Đang tạm tắt MuHelper...")
            eng.stop_helper()
            time.sleep(0.2)

        self.moss_running = True
        self.app.update_moss_slot_ui_state(self.slot_idx, is_running=True)
        cat_name = self.app.get_moss_cat_name(self.moss_category)
        self.app.append_moss_log(
            f"[Slot {self.slot_idx:02d} - {self.char_name}] ▶️ BẮT ĐẦU AUTO QUAY: {cat_name} | Delay {self.moss_delay_ms}ms"
        )

        def _worker():
            consecutive_fails = 0

            # 1. Quét chờ NPC Moss xuất hiện thực tế quanh Elbeland (22, 225) trước khi mở bảng
            self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                f"[Slot {s:02d} - {c}] 🔍 Đang quét tìm NPC Moss thực tế tại Elbeland (22, 225)..."
            ))

            npc_ready = False
            wait_ticks = 0
            while self.moss_running:
                if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                    self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Game MEGAMU đã thoát! Dừng quay."))
                    break

                npc_info = eng.find_moss_npc() if eng else None
                if npc_info and npc_info.get("found"):
                    # Đã phát hiện NPC Moss xuất hiện -> Tự động click vào NPC để Server mở bảng Moss
                    interact_res = eng.interact_moss_npc(self.moss_category) if eng else None
                    if interact_res and interact_res.get("success"):
                        n_name = interact_res.get("name", "Moss The Gambler")
                        n_idx = interact_res.get("index", "?")
                        n_x = interact_res.get("x", 22)
                        n_y = interact_res.get("y", 225)
                        c_str = self.app.get_moss_cat_name(self.moss_category)
                        # Chờ Server phản hồi gói C2:30 và hoàn tất nạp danh sách vật phẩm
                        for _ in range(20):
                            if eng and eng.is_moss_ready():
                                break
                            time.sleep(0.1)
                        self.app.after(0, lambda s=self.slot_idx, c=self.char_name, n=n_name, i=n_idx, x=n_x, y=n_y, cs=c_str: self.app.append_moss_log(
                            f"[Slot {s:02d} - {c}] 🎯 NPC {n} đã xuất hiện tại ({x},{y}, ID: {i})! Đã click vào NPC mở bảng Moss ({cs}) từ Server. Bắt đầu quay..."
                        ))
                        npc_ready = True
                        time.sleep(0.3)
                        break
                    else:
                        err_msg = interact_res.get("error", "Unknown") if interact_res else "None"
                        self.app.after(0, lambda s=self.slot_idx, err=err_msg: self.app.append_moss_log(
                            f"[Slot {s:02d}] ⚠️ Đã phát hiện NPC Moss nhưng click tương tác chưa thành công ({err}), đang thử lại..."
                        ))
                else:
                    wait_ticks += 1
                    if wait_ticks % 10 == 0:
                        self.app.after(0, lambda s=self.slot_idx: self.app.append_moss_log(
                            f"[Slot {s:02d}] ⏳ NPC Moss chưa xuất hiện. Vẫn đang tiếp tục chờ NPC spawn để click vào..."
                        ))

                time.sleep(0.5)

            if not self.moss_running or not npc_ready:
                self.moss_running = False
                self.app.after(0, lambda s=self.slot_idx: self.app.update_moss_slot_ui_state(s, is_running=False))
                return

            # Snapshot các ô đồ đang có sẵn trước khi bắt đầu quay để bảo vệ tuyệt đối
            self.moss_initial_slots = set()
            if eng and eng.is_ready:
                try:
                    init_inv = eng.get_inventory_summary(category=self.moss_category)
                    if init_inv and not init_inv.get("error"):
                        for item in init_inv.get("keptSlots", []):
                            s_num = item.get("slot")
                            if s_num is not None:
                                self.moss_initial_slots.add(int(s_num))
                        if self.moss_initial_slots:
                            self.app.after(0, lambda s=self.slot_idx, n=len(self.moss_initial_slots): self.app.append_moss_log(
                                f"[Slot {s:02d} - {self.char_name}] 🛡️ Đã kích hoạt vùng bảo vệ an toàn: {n} món đồ có sẵn trong hòm đồ sẽ KHÔNG BAO GIỜ bị xóa/bán!"
                            ))
                except Exception:
                    pass

            while self.moss_running:
                if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                    self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Game MEGAMU đã thoát! Dừng quay."))
                    break

                # Xác định dung lượng ô tối thiểu theo danh mục (Cung/Kiếm/Gậy/Chùy/Trượng: 8 ô; Khiên/Giáp: 6 ô; Trang sức: 2 ô)
                cat = int(getattr(self, "moss_category", 0) or 0)
                min_slots_needed = 8 if cat in [0, 1, 2, 3, 4] else (6 if cat in [6, 8] else 2)

                # 1. Proactive auto-clean: Kiểm tra hòm đồ trước khi quay
                if self.moss_auto_clean and eng and eng.is_ready:
                    try:
                        inv = eng.get_inventory_summary(category=self.moss_category, max_junk_level=6)
                        if inv and not inv.get("error"):
                            free_slots = int(inv.get("free", 64))
                            junk_count = int(inv.get("junkCount", 0))
                            moss_plus = int(inv.get("mossPlusCount", 0))

                            # Nếu còn ít ô trống và có đồ rác thường (+0..+6 thuộc danh mục Moss) -> xóa/hủy trực tiếp an toàn
                            if free_slots < (min_slots_needed + 4) and junk_count > 0:
                                self.app.after(0, lambda s=self.slot_idx, f=free_slots, j=junk_count: self.app.append_moss_log(
                                    f"[Slot {s:02d} - {self.char_name}] 🧹 Hòm đồ sắp đầy (còn {f} ô). Tự động dọn {j} món đồ rác Moss..."
                                ))
                                c_res = eng.clean_inventory_junk(
                                    "trash",
                                    protected_slots=list(self.moss_initial_slots),
                                    category=self.moss_category,
                                    include_extended=True,
                                    max_junk_level=6
                                )
                                cleaned = c_res.get("cleaned", 0)
                                self.app.after(0, lambda s=self.slot_idx, c=cleaned: self.app.append_moss_log(
                                    f"[Slot {s:02d} - {self.char_name}] 🗑️ Đã dọn {c} món đồ rác Moss (Đã bảo vệ đồ Divine / Rồng / Exc / Socket / Set / May mắn / Đồ >= +7). Tiếp tục quay..."
                                ))
                                time.sleep(0.3)
                                inv = eng.get_inventory_summary(category=self.moss_category, max_junk_level=6)
                                if inv and not inv.get("error"):
                                    free_slots = int(inv.get("free", 64))
                                    junk_count = int(inv.get("junkCount", 0))

                            # Nếu hòm đồ đã đầy các vật phẩm quý giá -> Dừng an toàn
                            if free_slots < min_slots_needed and junk_count == 0:
                                self.app.after(0, lambda s=self.slot_idx, f=free_slots, req=min_slots_needed, c=cat: self.app.append_moss_log(
                                    f"[Slot {s:02d} - {self.char_name}] ⚠️ Hòm đồ chỉ còn {f} ô lẻ, không đủ khoảng trống {req} ô cho danh mục {self.app.get_moss_cat_name(c)}. Tự động dừng quay an toàn!"
                                ))
                                break
                    except Exception:
                        pass

                if eng and not eng.is_moss_open():
                    # Đợi một chút kiểm tra nếu người dùng vừa bấm (X) trong game hoặc giao diện vừa đóng
                    time.sleep(0.4)
                    if not self.moss_running:
                        break
                    try:
                        eng.interact_moss_npc(self.moss_category)
                        for _ in range(12):
                            if not self.moss_running or eng.is_moss_open():
                                break
                            time.sleep(0.1)
                    except Exception:
                        pass

                # Chụp lại trạng thái hòm đồ trước khi quay để kiểm tra item trúng thưởng
                inv_before = None
                if eng and eng.is_ready:
                    try:
                        inv_before = eng.get_inventory_summary(category=self.moss_category, max_junk_level=6)
                    except Exception:
                        pass

                ok = eng.roll_moss(self.moss_category) if eng else False
                if ok:
                    # Chờ ngắn để Server trả kết quả packet vật phẩm về hòm đồ
                    time.sleep(0.35)

                    # So sánh hòm đồ để tìm món đồ mới quay được (cả kept và junk)
                    new_item_found = False
                    new_item_desc = ""
                    if eng and eng.is_ready and inv_before:
                        try:
                            inv_after = eng.get_inventory_summary(category=self.moss_category, max_junk_level=6)
                            if inv_after and not inv_after.get("error"):
                                b_kept = {item.get("slot"): item for item in inv_before.get("keptSlots", [])}
                                a_kept = {item.get("slot"): item for item in inv_after.get("keptSlots", [])}
                                b_junk = {item.get("slot"): item for item in inv_before.get("junkSlots", [])}
                                a_junk = {item.get("slot"): item for item in inv_after.get("junkSlots", [])}

                                for s_idx, itm in a_kept.items():
                                    if s_idx not in b_kept:
                                        new_item_found = True
                                        it_name = itm.get("name", "Vật phẩm")
                                        it_lvl = itm.get("level", 0)
                                        is_sp = itm.get("isSpecial", False)
                                        is_exc = itm.get("exc", 0) > 0
                                        is_anc = itm.get("anc", 0) > 0
                                        is_luck = itm.get("luck", 0) > 0
                                        tag = "⭐ DIVINE / RỒNG!" if is_sp else ("💎 HOÀN HẢO!" if is_exc else ("👑 ĐỒ THẦN!" if is_anc else ("🍀 MAY MẮN!" if is_luck else f"+{it_lvl}")))
                                        new_item_desc = f" -> 🎁 Trúng: {it_name} ({tag})"
                                        break

                                if not new_item_found:
                                    for s_idx, itm in a_junk.items():
                                        if s_idx not in b_junk:
                                            new_item_found = True
                                            it_name = itm.get("name", "Vật phẩm")
                                            it_lvl = itm.get("level", 0)
                                            new_item_desc = f" -> 🗑️ Nhận: {it_name} (+{it_lvl})"
                                            break
                        except Exception:
                            pass

                    if new_item_found:
                        consecutive_fails = 0
                        self.moss_rolls_count += 1
                        r_num = self.moss_rolls_count

                        def _update_ui(s=self.slot_idx, r=r_num, c=self.moss_category, desc=new_item_desc):
                            self.app.update_moss_slot_rolls(s, r)
                            c_str = self.app.get_moss_cat_name(c)
                            self.app.append_moss_log(f"[Slot {s:02d} - {self.char_name}] 🎰 Đã quay #{r}: {c_str}{desc}")
                        self.app.after(0, _update_ui)
                    else:
                        # Server KHÔNG gửi item về (Hòm đồ đầy không đủ khối trống, hoặc hết Zen)
                        consecutive_fails += 1
                        # Giải phóng LoadingImage ngay lập tức trên game client
                        try:
                            if eng and eng.is_ready:
                                eng.reset_moss_ui(self.moss_category)
                        except Exception:
                            pass

                        # Thử dọn rác an toàn nếu được bật
                        if self.moss_auto_clean and eng and eng.is_ready:
                            try:
                                c_res = eng.clean_inventory_junk(
                                    "trash",
                                    protected_slots=list(getattr(self, "moss_initial_slots", None) or []),
                                    category=self.moss_category,
                                    include_extended=True,
                                    max_junk_level=6
                                )
                                cleaned_items = c_res.get("cleaned", 0)
                                if cleaned_items > 0:
                                    self.app.after(0, lambda s=self.slot_idx, c=cleaned_items: self.app.append_moss_log(
                                        f"[Slot {s:02d} - {self.char_name}] 🗑️ Đã dọn {c} món rác Moss khi bị đầy (an toàn). Thử quay tiếp..."
                                    ))
                                    time.sleep(0.3)
                                    consecutive_fails = 0
                                    continue
                            except Exception:
                                pass

                        if consecutive_fails >= 2:
                            self.app.after(0, lambda s=self.slot_idx, c=cat, req=min_slots_needed: self.app.append_moss_log(
                                f"[Slot {s:02d} - {self.char_name}] ⚠️ Server không trả vật phẩm (Hòm đồ đầy không đủ khối {req} ô cho {self.app.get_moss_cat_name(c)} hoặc hết Zen). Tự động dừng quay và đóng bảng Moss an toàn!"
                            ))
                            break
                        else:
                            self.app.after(0, lambda s=self.slot_idx: self.app.append_moss_log(
                                f"[Slot {s:02d} - {self.char_name}] ⚠️ Lượt quay chưa nhận được vật phẩm (đang kiểm tra lại hòm đồ và giải phóng giao diện)..."
                            ))
                            time.sleep(0.5)
                else:
                    consecutive_fails += 1
                    # Nếu quay không thành công, giải phóng giao diện
                    try:
                        if eng and eng.is_ready:
                            eng.reset_moss_ui(self.moss_category)
                    except Exception:
                        pass

                    # Kiểm tra xem NPC Moss còn xuất hiện trong thế giới hay đã biến mất (hết giờ sự kiện)
                    npc_check = eng.find_moss_npc() if eng else None
                    if not npc_check or not npc_check.get("found"):
                        self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                            f"[Slot {s:02d} - {c}] 🛑 NPC Moss đã biến mất khỏi game (hết thời gian sự kiện). Tự động dừng quay an toàn!"
                        ))
                        break

                    # Nếu NPC vẫn còn, thử click lại vào NPC để khôi phục phiên giao dịch Server
                    try:
                        eng.interact_moss_npc(self.moss_category)
                        time.sleep(0.3)
                    except Exception:
                        pass

                    if consecutive_fails >= 3:
                        self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Gửi packet quay không thành công 3 lần liên tiếp (Hòm đầy không còn rác, không đủ Zen, hoặc nhân vật chưa đứng gần NPC Moss)."))
                        time.sleep(1.0)
                    else:
                        self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Gửi packet quay không thành công (Hòm đầy, không đủ Zen, hoặc phiên NPC bị ngắt)."))

                if self.moss_max_rolls > 0 and self.moss_rolls_count >= self.moss_max_rolls:
                    self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] 🏁 Đã hoàn thành đủ {self.moss_max_rolls} lượt."))
                    break

                # Sleep an toàn chia nhỏ
                slept = 0
                step = 0.05
                target = max(0.4, self.moss_delay_ms / 1000.0)
                while self.moss_running and slept < target:
                    time.sleep(step)
                    slept += step

            self.moss_running = False
            if eng and eng.is_ready:
                try:
                    eng.reset_moss_ui(self.moss_category)
                    eng.close_moss()
                except Exception:
                    pass
            self.app.after(0, lambda: self.app.update_moss_slot_ui_state(self.slot_idx, is_running=False))

            # Khôi phục Auto Train nếu trước đó bị tạm dừng bởi sự kiện Moss
            if getattr(self, "moss_paused_worker", False):
                self.moss_paused_worker = False
                def _resume_train():
                    self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🔄 Tự động khôi phục Auto Train quay lại bãi train...")
                    self.start_auto()
                self.app.after(1000, _resume_train)

        self.moss_worker_thread = threading.Thread(target=_worker, daemon=True, name=f"Slot{self.slot_idx:02d}_MossWorker")
        self.moss_worker_thread.start()
        return True

    def stop_moss(self):
        """Dừng Auto Quay Moss cho riêng slot này và đóng cửa sổ giải phóng tài nguyên."""
        if self.moss_running:
            self.moss_running = False
            eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
            if eng and eng.is_ready:
                try:
                    eng.reset_moss_ui(self.moss_category)
                    eng.close_moss()
                except Exception:
                    pass
            self.app.update_moss_slot_ui_state(self.slot_idx, is_running=False)
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏹️ Đã dừng Auto Quay Moss và đóng giao diện an toàn.")

            # Khôi phục Auto Train nếu trước đó bị tạm dừng bởi sự kiện Moss
            if getattr(self, "moss_paused_worker", False):
                self.moss_paused_worker = False
                def _resume_train_stop():
                    self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🔄 Tự động khôi phục Auto Train quay lại bãi train...")
                    self.start_auto()
                self.app.after(1000, _resume_train_stop)

    def roll_moss_once(self) -> bool:
        """Quay thử 1 lần cho riêng slot này (Yêu cầu phải có NPC Moss xuất hiện)."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        # Kiểm tra xem NPC Moss có xuất hiện không
        npc_info = eng.find_moss_npc()
        if not npc_info or not npc_info.get("found"):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏳ Chưa thấy NPC Moss xuất hiện tại Elbeland (22, 225)! Không thể quay thử.")
            return False

        # Nếu chưa mở hoặc chưa nạp danh sách từ Server, kích hoạt tương tác NPC trước
        if not eng.is_moss_open():
            try:
                eng.interact_moss_npc(self.moss_category)
                for _ in range(10):
                    time.sleep(0.1)
                    if eng.is_moss_open():
                        break
            except Exception:
                pass
        ok = eng.roll_moss(self.moss_category)
        if ok:
            self.moss_rolls_count += 1
            self.app.update_moss_slot_rolls(self.slot_idx, self.moss_rolls_count)
            c_str = self.app.get_moss_cat_name(self.moss_category)
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🎲 Quay 1 lần thành công: {c_str} (Lượt #{self.moss_rolls_count})")
            return True
        else:
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ❌ Quay 1 lần thất bại.")
            return False

    def open_moss_npc(self) -> bool:
        """Tương tác/click vào NPC Moss thực tế trong thế giới game để mở bảng Moss từ Server."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        # 1. Quét tìm NPC Moss thực tế xuất hiện quanh Elbeland (22, 225)
        npc_info = eng.find_moss_npc()
        if not npc_info or not npc_info.get("found"):
            self.app.append_moss_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏳ Chưa thấy NPC Moss xuất hiện tại Elbeland (22, 225). Phải có NPC Moss xuất hiện mới mở bảng!"
            )
            return False

        # 2. Click tương tác trực tiếp với NPC Moss để Server gửi dữ liệu và mở bảng hợp lệ
        res = eng.interact_moss_npc(self.moss_category)
        if res and res.get("success"):
            c_str = self.app.get_moss_cat_name(self.moss_category)
            n_name = res.get("name", "Moss The Gambler")
            n_idx = res.get("index", "?")
            n_x = res.get("x", 22)
            n_y = res.get("y", 225)
            # Chờ Server phản hồi và hoàn tất khởi tạo danh sách vật phẩm (tối đa 1.5 giây)
            ready = False
            for _ in range(15):
                time.sleep(0.1)
                if eng.is_moss_ready():
                    ready = True
                    break
            if ready:
                self.app.append_moss_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] 🎯 Đã click vào NPC {n_name} ({n_x},{n_y}) -> Bảng Moss ({c_str}) đã nạp thành công từ Server, sẵn sàng quay!"
                )
            else:
                self.app.append_moss_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] 🎯 Đã click vào NPC {n_name} ({n_x},{n_y}) -> Đã gửi yêu cầu đối thoại lên Server."
                )
            return True
        else:
            err = res.get("error", "Unknown") if res else "Failed"
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ❌ Tương tác click NPC Moss thất bại: {err}")
            return False

    def close_moss_dialog(self) -> bool:
        """Đóng bảng NPC Moss và thoát phiên đối thoại để mở khóa thùng đồ."""
        if self.moss_running:
            self.stop_moss()
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()
        try:
            try:
                eng.reset_moss_ui(self.moss_category)
            except Exception:
                pass
            eng.close_moss()
            eng.unlock_character_and_inventory()
            time.sleep(0.15)
            if hasattr(eng, "is_moss_open") and eng.is_moss_open():
                eng.close_moss()
            self.app.append_moss_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] 🚪 Đã đóng bảng Moss & mở khóa thùng đồ (phím V/I/Esc)."
            )
            return True
        except Exception as e:
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Lỗi đóng Moss: {e}")
            return False

    def unlock_inventory(self) -> bool:
        """Mở khóa và giải phóng toàn bộ trạng thái kẹt/treo của thùng đồ và nhân vật."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()
        try:
            ok = eng.unlock_character_and_inventory()
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🔓 Đã mở khóa và giải phóng toàn bộ thùng đồ & nhân vật thành công!")
            return bool(ok)
        except Exception as e:
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Lỗi mở khóa thùng đồ: {e}")
            return False

    def unlock_and_close_inventory(self) -> bool:
        """Mở khóa và đóng ngay thùng đồ + bảng Moss nếu đang bị treo/kẹt."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()
        try:
            eng.unlock_character_and_inventory()
            eng.close_inventory()
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🔓 Đã giải phóng toàn bộ treo/kẹt & đóng thùng đồ + Moss thành công!")
            return True
        except Exception as e:
            self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Lỗi giải phóng thùng đồ: {e}")
            return False

    def clean_moss_inventory(self, method: str = "trash", category: int = -1, run_in_thread: bool = False, force_clean: bool = True) -> int:
        """Dọn dẹp / ném tại chỗ các món đồ rác trong hòm đồ chính của riêng slot này."""
        def _runner() -> int:
            if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!")
                return 0
            eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
            if not eng:
                self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Không tìm thấy Direct Engine!")
                return 0
            if not eng.is_ready:
                eng.attach()
            try:
                # 1. Đảm bảo đóng bảng Moss & mở khóa thùng đồ & nhân vật trước tiên
                eng.close_moss()
                eng.unlock_character_and_inventory()
                time.sleep(0.3)
                if hasattr(eng, "is_moss_open") and eng.is_moss_open():
                    eng.close_moss()
                    time.sleep(0.2)

                # 2. Thực hiện ném đồ rác tại chỗ (category=-1 nghĩa là dọn sạch mọi đồ rác thường +0..+6 trong hòm đồ)
                # (bảo vệ tuyệt đối đồ Divine/Rồng/Exc/Socket/Set/May Mắn/Ngọc/Đồ >= +7)
                c_res = eng.clean_inventory_junk(
                    str(method),
                    protected_slots=[] if force_clean else list(getattr(self, "moss_initial_slots", None) or []),
                    category=category,
                    include_extended=True,
                    max_junk_level=6
                )
                cleaned = int(c_res.get("cleaned", 0)) if isinstance(c_res, dict) else 0
                total_junk = int(c_res.get("totalJunk", 0)) if isinstance(c_res, dict) else 0
                failed = int(c_res.get("failed", 0)) if isinstance(c_res, dict) else 0
                err_msg = c_res.get("error", "") if isinstance(c_res, dict) else ""

                if cleaned > 0:
                    self.app.append_moss_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] 🗑️ Đã ném tại chỗ thành công {cleaned}/{total_junk or cleaned} món đồ rác (Bảo tồn đồ Divine/Rồng/Exc/Socket/Set/May Mắn/Ngọc/Đồ >= +7)!"
                    )
                elif total_junk > 0:
                    self.app.append_moss_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Đã phát hiện {total_junk} món đồ rác nhưng máy chủ chưa cho phép rơi ra đất! Lưu ý: Nếu nhân vật đứng trong Làng / Event Square / Khu an toàn (Safe Zone), Server MU cấm ném đồ ra đất. Hãy di chuyển ra ngoài cổng làng."
                    )
                elif err_msg:
                    self.app.append_moss_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Lỗi ném đồ: {err_msg}"
                    )
                else:
                    self.app.append_moss_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] ℹ️ Thùng đồ không có món đồ rác nào cần ném (hoặc đã sạch)."
                    )
                return cleaned
            except Exception as e:
                self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Lỗi ném đồ tại chỗ: {e}")
                return 0
            finally:
                try:
                    eng.unlock_character_and_inventory()
                except Exception:
                    pass

        if run_in_thread:
            threading.Thread(target=_runner, daemon=True).start()
            return 0
        else:
            return _runner()

    def sell_moss_items_at_merchant(self, eng=None) -> bool:
        """
        Tự động di chuyển ra NPC Rhea (29, 235 Elbeland) bán đồ Moss +5..+7 khi thùng đồ bị đầy,
        sau đó quay lại bệ NPC Moss (22, 225) và mở lại bảng tiếp tục quay.
        Bảo vệ tuyệt đối: Đồ Divine, Đồ Rồng, Hoàn Hảo, Socket, Set Thần, Ngọc/Vé sự kiện/Cánh/Sách phép, Đồ >= +8.
        """
        if not eng:
            if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                return False
            eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng or not eng.is_ready:
            return False

        try:
            # Đóng bảng Moss & mở khóa nhân vật trước khi di chuyển để tránh kẹt trạng thái giao diện
            eng.close_moss()
            eng.unlock_character_and_inventory()
            time.sleep(0.4)
            if hasattr(eng, "is_moss_open") and eng.is_moss_open():
                eng.close_moss()
                time.sleep(0.2)

            # Điểm đích trước mặt thương nhân Silvia: ô (44, 229) Elbeland
            target_rhea_x, target_rhea_y = 44, 229

            self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                f"[Slot {s:02d} - {c}] 🚶 Bắt đầu di chuyển ra NPC Silvia ({target_rhea_x}, {target_rhea_y}) để dọn bán đồ rác..."
            ))

            # BƯỚC 1: Di chuyển tới Rhea (hỗ trợ thử lại nếu bị kẹt hoặc chưa tới)
            reached_rhea = False
            for attempt in range(2):
                eng.start_auto_move(target_rhea_x, target_rhea_y, helper=False)
                start_t = time.time()
                while time.time() - start_t < 12.0:
                    time.sleep(0.4)
                    if not getattr(self, "moss_running", True) and not getattr(self, "_manual_selling", False):
                        eng.stop_auto_move()
                        return False

                    p_info = eng.get_player_info()
                    if p_info:
                        px = p_info.get("x", 0) or p_info.get("tileX", 0)
                        py = p_info.get("y", 0) or p_info.get("tileY", 0)
                        if px > 0 and py > 0:
                            # Nếu đã đứng trong bán kính 3 ô tính từ Rhea (29, 235)
                            dist = max(abs(px - target_rhea_x), abs(py - target_rhea_y))
                            if dist <= 3:
                                reached_rhea = True
                                break

                if reached_rhea:
                    break
                else:
                    self.app.after(0, lambda s=self.slot_idx, c=self.char_name, a=attempt+1: self.app.append_moss_log(
                        f"[Slot {s:02d} - {c}] ⏳ Chưa tới được Silvia (lần {a}/2), đang tiếp tục bước tới..."
                    ))

            # Dừng bước di chuyển và đứng yên hoàn toàn trước khi nói chuyện với NPC
            eng.stop_auto_move()
            time.sleep(0.5)

            p_info = eng.get_player_info()
            px = p_info.get("x", 0) if p_info else 0
            py = p_info.get("y", 0) if p_info else 0

            # BƯỚC 2: Tìm và tương tác với NPC Rhea
            npc_found = eng.find_merchant_npc()
            npc_name = "Merchant Rhea"
            if npc_found and npc_found.get("found"):
                npc_name = npc_found.get("name", "Merchant Rhea")
                self.app.after(0, lambda s=self.slot_idx, c=self.char_name, n=npc_name, nx=npc_found.get('x'), ny=npc_found.get('y'): self.app.append_moss_log(
                    f"[Slot {s:02d} - {c}] 🎯 Đã tiếp cận NPC {n} tại ({nx}, {ny}). Đang mở giao dịch bán đồ..."
                ))
            else:
                self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                    f"[Slot {s:02d} - {c}] 🤝 Đang mở đối thoại với NPC Rhea tại ({px}, {py})..."
                ))

            # Gọi native tương tác đối thoại với NPC
            interact_res = eng.interact_merchant_npc()
            # Chờ Server phản hồi gói tin mở giao dịch Shop
            time.sleep(1.2)
            if isinstance(interact_res, dict) and not interact_res.get("success", False):
                err_name = interact_res.get("error", "UNKNOWN")
                self.app.after(0, lambda s=self.slot_idx, c=self.char_name, err=err_name: self.app.append_moss_log(
                    f"[Slot {s:02d} - {c}] ⚠️ Không thể kết nối đối thoại với NPC ({err}). Hủy lượt bán này."
                ))
                eng.close_merchant_npc()
                return False

            # BƯỚC 3: Gửi lệnh bán các món đồ rác thường (+0..+7, bảo vệ +8+, Divine, Rồng, Exc, Anc, Sock, Ngọc)
            s_res = eng.sell_moss_plus_items()
            sold_count = s_res.get("sold", 0) if isinstance(s_res, dict) else 0
            sold_items = s_res.get("items", []) if isinstance(s_res, dict) else []

            if sold_count > 0:
                summary_names = [f"{it.get('name', 'Item')}+{it.get('level', 0)}" for it in sold_items[:6]]
                sum_text = ", ".join(summary_names)
                if len(sold_items) > 6:
                    sum_text += f" ... (+{len(sold_items)-6} món khác)"
                self.app.after(0, lambda s=self.slot_idx, c=self.char_name, cnt=sold_count, st=sum_text: self.app.append_moss_log(
                    f"[Slot {s:02d} - {c}] 💰 Đã bán thành công {cnt} món đồ rác ({st})!"
                ))
            else:
                err_code = s_res.get("error") if isinstance(s_res, dict) else None
                cand_cnt = s_res.get("candidates", 0) if isinstance(s_res, dict) else 0
                if err_code == "server_not_confirm":
                    self.app.after(0, lambda s=self.slot_idx, c=self.char_name, cc=cand_cnt: self.app.append_moss_log(
                        f"[Slot {s:02d} - {c}] ⚠️ Phát hiện {cc} món đồ rác nhưng Server chưa phản hồi giao dịch bán đồ (Shop Rhea chưa sẵn sàng). Sẽ thử lại ở lượt sau."
                    ))
                else:
                    self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                        f"[Slot {s:02d} - {c}] ℹ️ Không phát hiện món đồ rác nào cần bán (hoặc đã dọn sạch)."
                    ))
            time.sleep(0.4)

            # Đóng phiên giao dịch Shop tại Rhea (gửi C1:31 và dọn WindowHandler)
            eng.close_merchant_npc()
            eng.unlock_character_and_inventory()
            time.sleep(0.4)

            # BƯỚC 4: Di chuyển quay lại bệ NPC Moss (22, 225)
            self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                f"[Slot {s:02d} - {c}] 🚶 Đang quay trở lại bệ NPC Moss (22, 225)..."
            ))

            reached_moss = False
            for attempt2 in range(2):
                eng.start_auto_move(22, 225, helper=False)
                start_t2 = time.time()
                while time.time() - start_t2 < 12.0:
                    time.sleep(0.4)
                    if not getattr(self, "moss_running", True) and not getattr(self, "_manual_selling", False):
                        eng.stop_auto_move()
                        return False

                    p_info = eng.get_player_info()
                    if p_info:
                        px = p_info.get("x", 0) or p_info.get("tileX", 0)
                        py = p_info.get("y", 0) or p_info.get("tileY", 0)
                        if px > 0 and py > 0 and max(abs(px - 22), abs(py - 225)) <= 3:
                            reached_moss = True
                            break

                if reached_moss:
                    break

            eng.stop_auto_move()
            time.sleep(0.6)

            # BƯỚC 5: Tương tác lại với NPC Moss để khôi phục phiên quay thưởng
            eng.interact_moss_npc(self.moss_category)
            time.sleep(0.5)
            self.app.after(0, lambda s=self.slot_idx, c=self.char_name: self.app.append_moss_log(
                f"[Slot {s:02d} - {c}] 🎰 Đã kết nối lại NPC Moss (22, 225). Tiếp tục quay thưởng!"
            ))
            return True
        except Exception as e:
            self.app.after(0, lambda s=self.slot_idx, c=self.char_name, err=str(e): self.app.append_moss_log(
                f"[Slot {s:02d} - {c}] ⚠️ Lỗi trong quá trình tự động đi bán đồ Moss: {err}"
            ))
            return False
        finally:
            try:
                eng.unlock_character_and_inventory()
            except Exception:
                pass

    def sell_moss_inventory(self):
        """Kích hoạt thủ công tiến trình đi bán đồ Moss +5..+7 tại NPC Leah trên luồng riêng."""
        self._manual_selling = True
        def _run():
            try:
                self.sell_moss_items_at_merchant()
            finally:
                self._manual_selling = False
        threading.Thread(target=_run, daemon=True).start()

    def move_to_moss_elbeland(self) -> bool:
        """Tự động chuyển map Elbeland và di chuyển tới tọa độ NPC Moss Merchant (22, 225)."""
        def _exec():
            if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game!"))
                return
            eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
            if not eng:
                self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d}] ❌ Không tìm thấy Direct Engine!"))
                return
            if not eng.is_ready:
                eng.attach()

            # 1. Tạm dừng Auto Train nếu đang chạy để tránh xung đột di chuyển / giữ bãi
            if self.worker or self.auto_requested:
                self.moss_paused_worker = True
                self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏸️ Tạm dừng Auto Train để tham gia sự kiện Moss..."))
                self.stop_auto("Tạm dừng Auto Train tham gia sự kiện Moss Merchant", trigger_by="EVENT")
                time.sleep(0.3)

            # 2. Tắt MuHelper trước khi chuyển map nếu đang chạy (MEGAMU cấm warp khi Helper đang đánh)
            if eng.is_helper_active(force_refresh=True):
                self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚔️ Tạm tắt MuHelper để chuyển map về Elbeland..."))
                eng.stop_helper()
                time.sleep(0.3)

            self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 🚶 Đang chuyển map về Elbeland..."))
            eng.send_chat("/move Elbeland")

            time.sleep(2.0)
            self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 📍 Đang tự động bước tới tọa độ NPC Moss (22, 225)..."))
            eng.start_auto_move(22, 225, helper=False)
            time.sleep(3.5)
            self.app.after(0, lambda: self.app.append_moss_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] 📍 Đã đến tọa độ (22, 225). Sẵn sàng chờ NPC Moss xuất hiện để click mở bảng..."))

        threading.Thread(target=_exec, daemon=True).start()
        return True

    def auto_stack_jewels(self) -> Dict[str, Any]:
        """Tự động gom gọn các ô ngọc lẻ trong hòm đồ cho Slot này."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return {"ok": False, "error": "not_connected"}
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return {"ok": False, "error": "no_engine"}
        if not eng.is_ready:
            eng.attach()

        res = eng.auto_stack_jewels()
        if not res.get("ok", False):
            err_msg = res.get("error", "Unknown")
            self.app.after(0, lambda: self.app.append_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Lỗi gom ngọc: {err_msg}"
            ))
            return res

        moved = res.get("moved", 0)
        details = res.get("details", [])
        total_jewels = res.get("total_jewels", 0)
        counts = res.get("counts", {})
        if moved > 0:
            names = set(d.get("name") for d in details if d.get("name"))
            names_str = f" ({', '.join(names)})" if names else ""
            self.app.after(0, lambda: self.app.append_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] 💎 ĐÃ SẮP XẾP & DỒN GỌN {moved} VIÊN NGỌC{names_str} VÀO CÁC Ô TRỐNG LIỀN KỀ (Bảo toàn 100% ngọc)!"
            ))
        elif total_jewels > 0:
            self.app.after(0, lambda: self.app.append_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] 💎 {total_jewels} viên ngọc trong hòm đồ đã nằm ở vị trí liền kề gọn gàng, không cần dồn thêm."
            ))
        else:
            self.app.after(0, lambda: self.app.append_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] 💎 Hòm đồ không có ngọc lẻ."
            ))
        return res

    def check_mirror_ticket(self) -> Dict[str, Any]:
        """Kiểm tra xem slot này có vé Mirror of Dimensions (item 7279) trong hòm đồ không."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return {"hasTicket": False, "count": 0, "slots": [], "error": "not_connected"}
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return {"hasTicket": False, "count": 0, "slots": [], "error": "no_engine"}
        if not eng.is_ready:
            eng.attach()
        info = eng.get_mirror_ticket_info()
        if info.get("hasTicket") and info.get("slots"):
            self.cached_mirror_ticket_slot = int(info["slots"][0])
        return info

    def prepare_mirror_event(self) -> bool:
        """Giai đoạn chuẩn bị trước 5 phút: Tắt helper, chuyển về Event Map / Lugard, và kiểm tra vé."""
        def _exec():
            if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                return
            eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
            if not eng:
                return
            if not eng.is_ready:
                eng.attach()

            # 1. Tạm dừng Auto Helper / đánh quái ngoài bãi
            try:
                if eng.is_helper_active():
                    eng.stop_helper()
            except Exception:
                pass

            # 2. Dịch chuyển về Event Map & di chuyển sát chân Lugard (229, 22)
            self.move_to_event_map()
            time.sleep(0.3)
            self.move_to_lugard()

            # 3. Chờ client ổn định sau chuyển map rồi kiểm tra vé trong túi đồ (poll tối đa 3.5s)
            t_info = {}
            for _ in range(7):
                time.sleep(0.5)
                t_info = eng.get_mirror_ticket_info()
                if t_info.get("hasTicket") or t_info.get("hasOnlySign"):
                    break
            if t_info.get("hasTicket"):
                if t_info.get("slots"):
                    self.cached_mirror_ticket_slot = int(t_info["slots"][0])
                details = t_info.get("details", [])
                main_slots = [d["slot"] for d in details if not d.get("isExtended")]
                ext_slots = [d["slot"] for d in details if d.get("isExtended")]
                loc_parts = []
                if main_slots:
                    loc_parts.append(f"Hòm chính ô [{', '.join(str(s) for s in main_slots)}]")
                if ext_slots:
                    loc_parts.append(f"Ba lô phụ ô [{', '.join(str(s) for s in ext_slots)}]")
                loc_str = " • ".join(loc_parts) if loc_parts else f"ô [{', '.join(str(s) for s in t_info.get('slots', []))}]"
                self.app.after(0, lambda: self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ✅ Đã sẵn sàng {t_info.get('count')} vé Mirror ({loc_str})!"
                ))
            elif t_info.get("hasOnlySign"):
                signs_str = ", ".join(str(s) for s in t_info.get("signs", []))
                self.app.after(0, lambda: self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ CHÚ Ý: Tìm thấy Mảnh Vé Sign of Dimensions tại ô [{signs_str}], chưa ghép thành vé Mirror hoàn chỉnh!"
                ))
            else:
                self.app.after(0, lambda: self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ CẢNH BÁO: Chưa tìm thấy vé Mirror of Dimensions (Item 7279) trong hòm đồ (đã quét ô 12-203)!"
                ))

        threading.Thread(target=_exec, daemon=True).start()
        return True

    def move_to_lugard(self) -> bool:
        """Di chuyển nhân vật đến sát vị trí NPC Lugard (229, 22 tại Event Square hoặc 49, 216 tại Elbeland)."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng or not eng.is_ready:
            return False
        try:
            pinfo = eng.get_player_info()
            if pinfo:
                cmap = pinfo.get("mapId", -1)
                # Map 53: Event Square, Map 40: Event Square VIP
                if cmap in (53, 40):
                    return eng.move_to(229, 22)
                elif cmap == 51: # Elbeland
                    return eng.move_to(49, 216)
                else:
                    eng.send_chat("/m ev")
                    time.sleep(0.5)
                    return eng.move_to(229, 22)
        except Exception:
            pass
        return True

    def move_to_event_map(self) -> bool:
        """Chuyển sang bản đồ Event Square (/m ev) nếu nhân vật đang ở map khác."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng or not eng.is_ready:
            return False
        try:
            pinfo = eng.get_player_info()
            if pinfo:
                cmap = pinfo.get("mapId", -1)
                # Map 53: Event Square, Map 40: Event Square VIP/Alt, Map 65-68: Double Goer
                if cmap in (53, 40, 65, 66, 67, 68):
                    return True
            eng.send_chat("/m ev")
            time.sleep(0.4)
            return True
        except Exception:
            return False

    move_to_lugard_elbeland = move_to_lugard

    def click_mirror_npc(self) -> bool:
        """Kích hoạt đối thoại NPC Lugard trong Game thật tại vị trí hiện tại (đứng yên, không di chuyển)."""
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        if hasattr(eng, "cancel_move"):
            try:
                eng.cancel_move()
            except Exception:
                pass
        if hasattr(eng, "stop_auto_move"):
            try:
                eng.stop_auto_move()
            except Exception:
                pass

        return eng.click_mirror_npc()

    def run_mirror_in_dungeon_lifecycle(self, force: bool = False):
        """
        Chu trình tự động hoàn chỉnh bên trong Map Double Goer (Map 65-68):
        - Giai đoạn 1: Khi vừa vào cổng (khung :10 - :15), đứng yên trong vùng an toàn (Safe Zone), KHÔNG bật Helper.
        - Giai đoạn 2: Đến phút thứ :16 trở đi, tự động bước ra khỏi vùng an toàn (Step-Out 6-7 bước), sau đó mới bật Helper.
        - Giai đoạn 3: Trong suốt trận đấu, Radar liên tục quét thực thể mặt đất, ƯU TIÊN TUYỆT ĐỐI nhặt 3 rương:
          + 2 "Reward Chest"
          + 1 "Final Reward Chest"
          (Bỏ qua mọi vật phẩm rác khác).
        - Giai đoạn 4: Khi hết sự kiện (bị đá về thành), tự động khôi phục Auto Train và quay lại bãi train ban đầu.
        """
        if getattr(self, "_mirror_dungeon_running", False):
            return

        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return

        is_in_mirror = eng.is_mirror_event_map()
        if not is_in_mirror and not force:
            self.app.after(0, lambda: self.app.append_mirror_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] ℹ️ Nhân vật hiện ở map ngoài, chưa vào Double Goer (Map 65-68). Tính năng tự động ra bãi phút :16 & săn 3 box quà đã BẬT SẴN, sẽ tự chạy ngay khi bước vào cổng!"
            ))
            return

        def _dungeon_worker():
            with self._mirror_lock:
                if self._mirror_dungeon_running:
                    return
                self._mirror_dungeon_running = True

            try:
                self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "⏳ Chờ :16 xuất kích", text_color="#f59e0b"))
                self.app.after(0, lambda: self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏳ ĐÃ VÀO DOUBLE GOER! Đang đứng chờ trong vùng an toàn, chuẩn bị xuất kích ở phút thứ :16..."
                ))

                scanner = None
                if MemoryScanner and self.assigned_pid:
                    try:
                        scanner = MemoryScanner(self.assigned_pid)
                    except Exception:
                        scanner = None

                spawn_x, spawn_y = -1, -1
                if scanner and scanner.base_addr:
                    try:
                        p_data = scanner.scan_radar(radius=6.0)
                        if p_data and "player" in p_data:
                            spawn_x = p_data["player"].get("x", -1)
                            spawn_y = p_data["player"].get("y", -1)
                    except Exception:
                        pass
                if (spawn_x <= 0 or spawn_y <= 0) and eng:
                    try:
                        tele = eng.get_player_info()
                        if tele:
                            spawn_x = tele.get("x", -1)
                            spawn_y = tele.get("y", -1)
                    except Exception:
                        pass

                has_stepped_out = False
                looted_chests = 0

                while eng and eng.is_mirror_event_map():
                    now = datetime.now()

                    # BƯỚC 1: BƯỚC RA KHỎI VÙNG AN TOÀN Ở PHÚT THỨ :16
                    if not has_stepped_out:
                        # Điều kiện kích hoạt: Đã đến phút thứ 16 (16 <= now.minute < 35 hoặc qua 00h)
                        if (now.minute >= 16) or (0 <= now.minute < 10):
                            self.app.after(0, lambda: self.app.append_mirror_log(
                                f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚔️ ĐÃ SANG PHÚT THỨ :16! Bắt đầu bước ra khỏi vùng an toàn..."
                            ))

                            step_done = False
                            px, py = spawn_x, spawn_y

                            if scanner and scanner.base_addr:
                                try:
                                    # Quét xa tới 120 ô để bắt trọn đợt quái vật đầu tiên đang tiến lại dọc hành lang
                                    r_data = scanner.scan_radar(radius=120.0)
                                    monsters = r_data.get("monsters", [])
                                    cur_p = r_data.get("player", {})
                                    px = cur_p.get("x", px)
                                    py = cur_p.get("y", py)

                                    # Nếu có quái vật xuất hiện phía trước (chuẩn hướng hành lang):
                                    if monsters and px > 0 and py > 0:
                                        nearest_m = monsters[0]
                                        mx, my = nearest_m["x"], nearest_m["y"]
                                        dist = max(1.0, nearest_m.get("distance", 1.0))
                                        step_dist = min(7.0, max(4.0, dist - 2.0))
                                        tx = int(px + (mx - px) / dist * step_dist)
                                        ty = int(py + (my - py) / dist * step_dist)
                                        if hasattr(eng, "move_to"):
                                            eng.move_to(tx, ty)
                                            step_done = True
                                            self.app.after(0, lambda: self.app.append_mirror_log(
                                                f"[Slot {self.slot_idx:02d} - {self.char_name}] 🚶 Bước 6 ô về hướng đợt quái ({tx}, {ty}) [cách {dist:.0f}m] để vượt ranh giới Safe Zone..."
                                            ))
                                except Exception as e:
                                    print(f"Error scanning monsters in step-out: {e}")

                            # Nếu chưa thấy quái (chưa spawn kịp), bước tiến theo hướng cổng an toàn
                            if not step_done:
                                try:
                                    tele = eng.get_player_info() or (self.engine.read_player_info_via_ram() if self.engine else None)
                                    if tele:
                                        px = tele.get("x", px)
                                        py = tele.get("y", py)
                                        if hasattr(eng, "move_to") and px > 0 and py > 0:
                                            # Thử bước tiến về phía tâm map (Double Goer luôn hướng về giữa map)
                                            eng.move_to(px + 6, py)
                                            step_done = True
                                            self.app.after(0, lambda: self.app.append_mirror_log(
                                                f"[Slot {self.slot_idx:02d} - {self.char_name}] 🚶 Bước tiến 6 ô ({px + 6}, {py}) ra khỏi Safe Zone..."
                                            ))
                                except Exception:
                                    pass

                            time.sleep(1.5)

                            # Kích hoạt Mu Helper và xác thực Helper đã bật thành công (không bật trong Safe Zone)
                            helper_started = False
                            for attempt in range(1, 4):
                                try:
                                    if not eng.is_helper_active(force_refresh=True):
                                        eng.start_helper()
                                        time.sleep(0.8)
                                    if eng.is_helper_active(force_refresh=True):
                                        helper_started = True
                                        has_stepped_out = True
                                        self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "⚔️ Trong Double Goer", text_color="#10b981"))
                                        self.app.after(0, lambda: self.app.append_mirror_log(
                                            f"[Slot {self.slot_idx:02d} - {self.char_name}] ✅ ĐÃ RA KHỎI VÙNG AN TOÀN! Bật Helper thành công (RVA 0x27776F0), bắt đầu chiến đấu và săn 3 rương!"
                                        ))
                                        break
                                    else:
                                        self.app.after(0, lambda a=attempt: self.app.append_mirror_log(
                                            f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Helper chưa bật (vẫn vướng Safe Zone, lần {a}/3). Bước thêm ra ngoài..."
                                        ))
                                        if hasattr(eng, "move_to") and px > 0 and py > 0:
                                            if monsters:
                                                nearest_m = monsters[0]
                                                mx, my = nearest_m["x"], nearest_m["y"]
                                                dist = max(1.0, nearest_m.get("distance", 1.0))
                                                extra_dist = min(dist - 1.0, 4.0 * attempt + 3.0)
                                                tx2 = int(px + (mx - px) / dist * extra_dist)
                                                ty2 = int(py + (my - py) / dist * extra_dist)
                                                eng.move_to(tx2, ty2)
                                            else:
                                                eng.move_to(px + 4 * attempt + 4, py)
                                        time.sleep(1.2)
                                except Exception as e:
                                    print(f"Error starting helper attempt {attempt}: {e}")

                            if not helper_started:
                                self.app.after(0, lambda: self.app.append_mirror_log(
                                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏳ Sẽ tiếp tục thử bước ra và bật Helper ở chu kỳ kế tiếp..."
                                ))
                        else:
                            # Đang chờ đến phút thứ :16
                            rem_s = (16 - now.minute) * 60 - now.second
                            if rem_s > 0 and rem_s % 15 == 0:
                                self.app.after(0, lambda: self.app.append_mirror_log(
                                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏳ Còn {rem_s}s nữa tới phút :16 để bước ra khỏi vùng an toàn..."
                                ))
                            time.sleep(1.0)
                            continue

                    # BƯỚC 2: KHI ĐÃ CHIẾN ĐẤU - RADAR LIÊN TỤC QUÉT SĂN 3 RƯƠNG (2 REWARD CHEST + 1 FINAL REWARD CHEST)
                    if has_stepped_out and scanner and scanner.base_addr:
                        try:
                            it_data = scanner.scan_radar(radius=35.0)
                            
                            # TẬP HỢP TOÀN BỘ CÁC NGUỒN THỰC THỂ (Ground Items, NPCs, Monsters, Entities)
                            candidates = []
                            candidates.extend(it_data.get("ground_items", []))
                            candidates.extend(it_data.get("npcs", []))
                            candidates.extend(it_data.get("monsters", []))
                            candidates.extend(it_data.get("entities", []))

                            # Lọc rương: 2 Reward Chest + 1 Final Reward Chest (Bao gồm tên EN, PT và class ID)
                            chest_targets = []
                            seen_ptrs = set()
                            for it in candidates:
                                n_low = it.get("name", "").lower()
                                cid = it.get("classId", it.get("class_id", -1))
                                i_key = it.get("ptr", f"{it.get('x')}_{it.get('y')}_{n_low}")
                                if i_key in seen_ptrs:
                                    continue

                                is_chest = (
                                    "reward chest" in n_low or
                                    "final reward" in n_low or
                                    ("chest" in n_low and "box" in n_low) or
                                    n_low == "chest" or
                                    "baú" in n_low or
                                    "tesouro" in n_low or
                                    "caixa" in n_low or
                                    cid in (528, 529, 530, 531, 538, 539)
                                )
                                if is_chest:
                                    seen_ptrs.add(i_key)
                                    dist_val = it.get("distance", it.get("dist", 999))
                                    it["distance"] = dist_val
                                    chest_targets.append(it)

                            if chest_targets:
                                # Chọn rương gần nhất
                                target_chest = sorted(chest_targets, key=lambda x: x.get("distance", 999))[0]
                                cx, cy = target_chest["x"], target_chest["y"]
                                cname = target_chest.get("name", "Reward Chest")
                                cdist = target_chest.get("distance", 0)

                                self.app.after(0, lambda: self.app.append_mirror_log(
                                    f"[Slot {self.slot_idx:02d} - {self.char_name}] 🎁 PHÁT HIỆN RƯƠNG: '{cname}' tại ({cx}, {cy}) cách {cdist:.1f} ô! Đang chạy lại mở & nhặt..."
                                ))

                                # Chạy đến vị trí rương
                                if hasattr(eng, "move_to"):
                                    eng.move_to(cx, cy)

                                # Chờ chạy đến
                                walk_time = min(3.5, max(0.6, cdist * 0.22))
                                time.sleep(walk_time)

                                hwnd = eng.get_hwnd() if hasattr(eng, "get_hwnd") else None
                                if hwnd:
                                    # Lấy kích thước cửa sổ game để tính tọa độ Isometric Click chính xác
                                    cw, ch = 1024, 768
                                    try:
                                        import ctypes.wintypes
                                        rect = ctypes.wintypes.RECT()
                                        if ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
                                            cw = max(800, rect.right - rect.left)
                                            ch = max(600, rect.bottom - rect.top)
                                    except Exception:
                                        pass

                                    # Lấy tọa độ hiện tại của nhân vật
                                    p_now = eng.get_player_info() or {}
                                    cur_px = p_now.get("x", cx)
                                    cur_py = p_now.get("y", cy)

                                    # THAO TÁC 1: CLICK CHUỘT TRỰC TIẾP VÀO NẮP RƯƠNG (Để kích hoạt Mở Rương)
                                    try:
                                        from meg_rea_hunter import calc_monster_hitbox_pixel
                                        sx, sy = calc_monster_hitbox_pixel(cur_px, cur_py, cx, cy, cw, ch)
                                        for _ in range(3):
                                            MegDirectEngine.send_background_click(hwnd, sx, sy, duration_ms=45)
                                            time.sleep(0.12)
                                    except Exception as e_click:
                                        print(f"Error clicking chest: {e_click}")

                                    # THAO TÁC 2: BẤM SPACEBAR (Để hút ngọc / vật phẩm vừa văng ra từ rương)
                                    for _ in range(6):
                                        MegDirectEngine.send_background_key(hwnd, 0x20, duration_s=0.04)
                                        time.sleep(0.08)

                                looted_chests += 1
                                self.app.after(0, lambda: self.app.append_mirror_log(
                                    f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏆 ĐÃ MỞ & NHẶT RƯƠNG THÀNH CÔNG #{looted_chests}: {cname}!"
                                ))

                                # Bật lại Helper nếu bị gián đoạn di chuyển
                                time.sleep(0.4)
                                if not eng.is_helper_active():
                                    eng.start_helper()
                        except Exception as e:
                            print(f"Error looting chest in Double Goer: {e}")

                    # Duy trì Helper nếu đang chiến đấu
                    if has_stepped_out and (now.second % 6 == 0):
                        try:
                            if not eng.is_helper_active():
                                eng.start_helper()
                        except Exception:
                            pass

                    time.sleep(1.0)

                # BƯỚC 3: SỰ KIỆN KẾT THÚC (Rời khỏi map Double Goer)
                self.app.after(0, lambda: self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏁 SỰ KIỆN DOUBLE GOER KẾT THÚC! (Đã nhặt {looted_chests} rương). Khôi phục Auto Train..."
                ))

                # TỰ ĐỘNG LÔI QUÀ TỪ HỘP QUÀ PHÍM "K" (GREMORY CASE) RA HÒM ĐỒ CHÍNH
                try:
                    is_gremory_enabled = hasattr(self.app, "cb_mirror_auto_gremory") and self.app.cb_mirror_auto_gremory is not None and (self.app.cb_mirror_auto_gremory.get() == 1)
                    if is_gremory_enabled:
                        time.sleep(1.0)
                        self.app.after(0, lambda: self.app.append_mirror_log(
                            f"[Slot {self.slot_idx:02d} - {self.char_name}] 🎁 TỰ ĐỘNG LÔI QUÀ: Đang kiểm tra và nhận tất cả quà trong Hộp Quà Phím 'K' (Gremory Case)..."
                        ))
                        res_claim = eng.claim_gremory_case_items() if hasattr(eng, "claim_gremory_case_items") else {"claimed": 0}
                        c_count = res_claim.get("claimed", 0)
                        if c_count > 0:
                            self.app.after(0, lambda c=c_count: self.app.append_mirror_log(
                                f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏆 ĐÃ TỰ ĐỘNG LÔI THÀNH CÔNG {c} MÓN QUÀ TỪ PHÍM 'K' VÀO HÒM ĐỒ CHÍNH!"
                            ))
                        else:
                            self.app.after(0, lambda: self.app.append_mirror_log(
                                f"[Slot {self.slot_idx:02d} - {self.char_name}] ℹ️ Hộp Quà Phím 'K' hiện không còn quà chờ nhận."
                            ))
                except Exception as e_k:
                    print(f"Error auto claiming Gremory gifts: {e_k}")
                self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "Hoàn tất"))
                self._resume_train_after_mirror("Sự kiện Double Goer hoàn tất")

            except Exception as e:
                log_thread_exception(
                    source=f"Slot{self.slot_idx:02d}.MirrorDungeonWorker",
                    exc=e,
                    thread_name=f"Slot{self.slot_idx:02d}_MirrorDungeonWorker",
                    details=f"Char: {self.char_name}"
                )
            finally:
                with self._mirror_lock:
                    self._mirror_dungeon_running = False

        threading.Thread(target=_dungeon_worker, daemon=True, name=f"Slot{self.slot_idx:02d}_MirrorDungeonWorker").start()

    def enter_mirror(self) -> bool:
        """
        ĐỨNG YÊN VỊ TRÍ VÀ GỬI PACKET ĐỂ VÀO CỔNG - TUYỆT ĐỐI KHÔNG DI CHUYỂN!
        Gửi trực tiếp lệnh đối thoại Lugard và packet vào cửa tới Game.
        Nếu chưa vào được (do chưa tới giờ mở cổng hoặc chưa có vé), chính Game sẽ trực tiếp hiển thị thông báo.
        """
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        # Nếu đã ở trong map Double Goer (Map 65-68)
        if hasattr(eng, "is_mirror_event_map") and eng.is_mirror_event_map():
            self.run_mirror_in_dungeon_lifecycle()
            return True

        # ĐẢM BẢO ĐỨNG YÊN HOÀN TOÀN TẠI VỊ TRÍ HIỆN TẠI, KHÔNG DI CHUYỂN
        if hasattr(eng, "cancel_move"):
            try:
                eng.cancel_move()
            except Exception:
                pass
        if hasattr(eng, "stop_auto_move"):
            try:
                eng.stop_auto_move()
            except Exception:
                pass

        # GỬI PACKET VÀO CỔNG TẠI CHỖ:
        # 1. Gọi tương tác Lugard trong Game để Game phát thông báo nếu chưa có vé / chưa mở cổng
        try:
            eng.click_mirror_npc()
            time.sleep(0.04)
        except Exception:
            pass

        # 2. Quét slot vé (nếu có trong túi đồ)
        ticket_slot = None
        try:
            t_info = eng.get_mirror_ticket_info()
            if t_info and t_info.get("slots"):
                ticket_slot = int(t_info["slots"][0])
        except Exception:
            pass

        # 3. Gửi packet vào cửa trực tiếp tới GameServer
        res = eng.enter_mirror(ticket_slot)

        # 4. Kiểm tra xác nhận vào map trong game
        def _verify_entry():
            entered = False
            for _ in range(12):
                time.sleep(0.4)
                if eng and eng.is_mirror_event_map():
                    entered = True
                    break

            if entered:
                self.run_mirror_in_dungeon_lifecycle()

        threading.Thread(target=_verify_entry, daemon=True).start()
        return True

    def start_mirror_auto(self) -> bool:
        """Bắt đầu chạy Auto Double Goer cho slot này (có kiểm tra vé, lịch giờ mở cổng và di chuyển tới Lugard)."""
        if license_client and not license_client.has_license_module("mirror"):
            self.app.append_mirror_log(f"[Slot {self.slot_idx:02d}] ❌ Bản quyền chưa kích hoạt Module Mirror of Dimensions!")
            return False

        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_mirror_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game! Không thể bật Auto Mirror.")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        self.mirror_running = True
        self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=True)
        self.app.append_mirror_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ▶️ BẮT ĐẦU AUTO DOUBLE GOER (MIRROR)")

        def _worker():
            while self.mirror_running:
                if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                    self.app.after(0, lambda: self.app.append_mirror_log(f"[Slot {self.slot_idx:02d}] ⚠️ Game MEGAMU đã thoát! Dừng Auto Mirror."))
                    break

                # 1. Nếu đã ở trong map Double Goer
                if eng and eng.is_mirror_event_map():
                    self.run_mirror_in_dungeon_lifecycle()
                    time.sleep(3.0)
                    continue

                # 2. Kiểm tra vé và lịch giờ mở cổng
                now = datetime.now()
                valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
                is_gate_open = (now.hour in valid_hours and 10 <= now.minute < 15)

                next_gate_open = None
                for h in valid_hours:
                    cand_gate = now.replace(hour=h, minute=10, second=0, microsecond=0)
                    if cand_gate > now:
                        next_gate_open = cand_gate
                        break
                if not next_gate_open:
                    tomorrow = now + timedelta(days=1)
                    next_gate_open = tomorrow.replace(hour=0, minute=10, second=0, microsecond=0)
                # Bỏ qua kiểm tra thời gian trên app theo yêu cầu, luôn gửi lệnh vào cửa trực tiếp xuống game:
                # Nếu chưa tới giờ mở cổng, game sẽ hiển thị popup chuẩn:
                # "DOPPELGANGER: You can't enter at the moment. Try at next time."
                self.enter_mirror()
                time.sleep(3.0)

            self.mirror_running = False
            self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))
            self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "Đã dừng"))

            # Khôi phục AutoTrain nếu trước đó bị tạm dừng bởi sự kiện Mirror
            self._resume_train_after_mirror("Sự kiện Double Goer hoàn tất")

        self.mirror_worker_thread = threading.Thread(target=_worker, daemon=True, name=f"Slot{self.slot_idx:02d}_MirrorWorker")
        self.mirror_worker_thread.start()
        return True

    def stop_mirror_auto(self):
        """Dừng Auto Double Goer cho slot này."""
        if self.mirror_running:
            self.mirror_running = False
            self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False)
            self.app.update_mirror_slot_status(self.slot_idx, "Đã dừng")
            self.app.append_mirror_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏹️ Đã dừng Auto Double Goer.")

    def start_mirror_turbo_sniping(self, interval_ms: int = 80, max_duration_s: float = 15.0) -> bool:
        """Kích hoạt chế độ Turbo Sniping (Spam Packet tốc độ cao) để cướp cổng Double Goer."""
        if license_client and not license_client.has_license_module("mirror"):
            self.app.append_mirror_log(f"[Slot {self.slot_idx:02d}] ❌ Bản quyền chưa kích hoạt Module Mirror of Dimensions!")
            return False
        if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
            self.app.append_mirror_log(f"[Slot {self.slot_idx:02d}] ⚠️ Chưa kết nối Game! Không thể Turbo Snipe.")
            return False
        eng = self.engine or (MegDirectEngine.get_engine(self.assigned_pid) if MegDirectEngine else None)
        if not eng:
            return False
        if not eng.is_ready:
            eng.attach()

        # ĐẢM BẢO ĐỨNG YÊN HOÀN TOÀN TẠI VỊ TRÍ HIỆN TẠI, TUYỆT ĐỐI KHÔNG DI CHUYỂN
        if hasattr(eng, "cancel_move"):
            try:
                eng.cancel_move()
            except Exception:
                pass
        if hasattr(eng, "stop_auto_move"):
            try:
                eng.stop_auto_move()
            except Exception:
                pass

        # 1. Kiểm tra cache vé trước: nếu slot đã cache từ trước thì dùng ngay lập tức (0ms delay)
        cached_slot = getattr(self, "cached_mirror_ticket_slot", -1)
        t_info = {}
        if cached_slot < 0:
            for _try in range(2):
                try:
                    t_info = eng.get_mirror_ticket_info()
                    if t_info.get("hasTicket") and t_info.get("slots"):
                        cached_slot = int(t_info["slots"][0])
                        self.cached_mirror_ticket_slot = cached_slot
                        break
                    if t_info.get("hasOnlySign"):
                        break
                except Exception:
                    pass
                time.sleep(0.02)

        if self.mirror_sniping:
            return True

        self.mirror_sniping = True
        self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=True))
        self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, f"⚡ Turbo ({interval_ms}ms)", text_color="#c084fc"))

        # 1. Kích hoạt Native In-Process Turbo Sniping (0ms IPC, chạy trực tiếp trong RAM Game)
        native_started = False
        if hasattr(eng, "start_native_mirror_turbo"):
            def _on_native_event(payload):
                p_type = payload.get("type")
                if p_type == "mirror_turbo_entered":
                    pkts = payload.get("packets", 0)
                    dur_ms = payload.get("elapsed", 0)
                    self.mirror_sniping = False
                    self.app.after(0, lambda: self.app.append_mirror_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏆 CƯỚP CỔNG THÀNH CÔNG! Đã vào map Double Goer sau {pkts} packets (Native {dur_ms}ms)!"
                    ))
                    self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "⚔️ Trong Double Goer", text_color="#10b981"))
                    self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))
                    def _delayed_start_helper():
                        time.sleep(1.2)
                        try:
                            if not eng.is_helper_active():
                                eng.start_helper()
                        except Exception:
                            pass
                    threading.Thread(target=_delayed_start_helper, daemon=True).start()
                elif p_type == "mirror_turbo_timeout":
                    pkts = payload.get("packets", 0)
                    self.mirror_sniping = False
                    self.app.after(0, lambda: self.app.append_mirror_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏱️ Hết thời gian Turbo Sniping ({max_duration_s:.0f}s). Đã bắn {pkts} packets (Native)."
                    ))
                    self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))
            eng.on_mirror_turbo_event = _on_native_event

            res_nat = eng.start_native_mirror_turbo(slot=cached_slot, interval_ms=interval_ms, max_duration_ms=int(max_duration_s * 1000))
            if res_nat.get("success"):
                native_started = True
                self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚡ BẮT ĐẦU NATIVE TURBO SNIPING CƯỚP CỔNG (0ms IPC, Vé ô {cached_slot}, Chu kỳ: {interval_ms}ms, Tối đa: {max_duration_s:.0f}s)"
                )
            elif res_nat.get("error") == "no_ticket":
                self.mirror_sniping = False
                self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False)
                self.app.update_mirror_slot_status(self.slot_idx, "Thiếu vé")
                self.app.append_mirror_log(
                    f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Không tìm thấy vé Mirror of Dimensions (ID 7279) trong hòm đồ (ô 12-203)! Hãy chuẩn bị vé trước khi bật Turbo."
                )
                return False

        if not native_started:
            self.app.append_mirror_log(
                f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚡ BẮT ĐẦU TURBO SNIPING CƯỚP CỔNG (Fallback RPC, Vé ô {cached_slot}, Chu kỳ: {interval_ms}ms, Tối đa: {max_duration_s:.0f}s)"
            )

        def _sniper():
            start_t = time.time()
            if native_started:
                # Native In-Process đang tự bắn liên thanh 0ms IPC bên trong RAM game.
                # Luồng Python chỉ giám sát fast_state trong RAM Python (Zero GIL/RPC contention)!
                while self.mirror_sniping:
                    time.sleep(0.2)
                    now = time.time()
                    if (now - start_t) > (max_duration_s + 0.5):
                        break
                    if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                        break
                    fast = getattr(eng, "last_fast_state", None) or {}
                    map_id = fast.get("mapId", -1)
                    if map_id in (65, 66, 67, 68):
                        self.mirror_sniping = False
                        self.app.after(0, lambda: self.app.append_mirror_log(
                            f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏆 CƯỚP CỔNG THÀNH CÔNG! Đã vào map Double Goer ({time.time() - start_t:.2f}s)!"
                        ))
                        self.run_mirror_in_dungeon_lifecycle()
                        break
                self.mirror_sniping = False
                if hasattr(eng, "stop_native_mirror_turbo"):
                    try:
                        eng.stop_native_mirror_turbo()
                    except Exception:
                        pass
                self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))
                return

            # Fallback Python High-Speed Loop (nếu native in-process chưa khả dụng)
            base_sleep = max(0.015, interval_ms / 1000.0)
            packets_sent = 0
            check_interval = 4
            iter_cnt = 0
            fail_no_ticket_cnt = 0
            active_slot = cached_slot

            while self.mirror_sniping:
                now = time.time()
                elapsed = now - start_t
                if elapsed > max_duration_s:
                    self.app.after(0, lambda: self.app.append_mirror_log(
                        f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏱️ Hết thời gian Turbo Sniping ({max_duration_s:.0f}s). Đã bắn {packets_sent} packets."
                    ))
                    break

                if not self.assigned_pid or not is_megamu_process_alive(self.assigned_pid):
                    break

                res = eng.enter_mirror(slot=active_slot if active_slot >= 0 else None)
                packets_sent += 1
                iter_cnt += 1

                if not res.get("success") and res.get("error") in ("no_ticket", "only_signs"):
                    fail_no_ticket_cnt += 1
                    if fail_no_ticket_cnt >= 3:
                        fresh_info = eng.get_mirror_ticket_info()
                        if fresh_info.get("hasTicket") and fresh_info.get("slots"):
                            active_slot = int(fresh_info["slots"][0])
                            fail_no_ticket_cnt = 0
                        else:
                            self.app.after(0, lambda: self.app.append_mirror_log(
                                f"[Slot {self.slot_idx:02d} - {self.char_name}] ⚠️ Hủy Turbo Snipe: Vé Mirror đã hết hoặc không còn trong hòm đồ!"
                            ))
                            break

                if iter_cnt >= check_interval:
                    iter_cnt = 0
                    if eng.is_mirror_event_map():
                        elapsed = time.time() - start_t
                        self.app.after(0, lambda: self.app.append_mirror_log(
                            f"[Slot {self.slot_idx:02d} - {self.char_name}] 🏆 CƯỚP CỔNG THÀNH CÔNG! Đã vào map Double Goer sau {packets_sent} packets ({elapsed:.2f}s)!"
                        ))
                        self.run_mirror_in_dungeon_lifecycle()
                        break

                time.sleep(base_sleep)

            self.mirror_sniping = False
            self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))

        self.mirror_snipe_thread = threading.Thread(target=_sniper, daemon=True, name=f"Slot{self.slot_idx:02d}_MirrorSniper")
        self.mirror_snipe_thread.start()
        return True

    def stop_mirror_turbo_sniping(self):
        """Dừng chế độ Turbo Sniping an toàn (Thread-safe & non-blocking)."""
        was_sniping = self.mirror_sniping
        self.mirror_sniping = False
        if was_sniping:
            pid = self.assigned_pid
            def _async_clean():
                if pid and MegDirectEngine:
                    eng = self.engine or MegDirectEngine.get_engine(pid)
                    if eng and hasattr(eng, "stop_native_mirror_turbo"):
                        try:
                            eng.stop_native_mirror_turbo()
                        except Exception:
                            pass
            threading.Thread(target=_async_clean, daemon=True).start()
            self.app.after(0, lambda: self.app.update_mirror_slot_ui_state(self.slot_idx, is_running=False))
            self.app.after(0, lambda: self.app.update_mirror_slot_status(self.slot_idx, "Đã dừng"))
            self.app.after(0, lambda: self.app.append_mirror_log(f"[Slot {self.slot_idx:02d} - {self.char_name}] ⏹️ Đã dừng Turbo Sniping."))


# ==============================================================================
# GIAO DIỆN CHÍNH (MEGAMU AUTO TRAIN DASHBOARD)
# ==============================================================================
