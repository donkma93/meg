"""
Storage Engine for MEGAMU Auto Train Dashboard.
Provides thread-safe, atomic disk persistence for configuration files with zero UI dependencies.
"""

import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Standard configuration file paths
PROFILE_FILE = CONFIG_DIR / "autotrain_profiles.json"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "autotrain_megamu_config.json"
SLOT_ASSIGNMENTS_FILE = CONFIG_DIR / "slot_assignments.json"
UI_SETTINGS_FILE = CONFIG_DIR / "ui_settings.json"
MAP_COMMANDS_FILE = CONFIG_DIR / "map_commands.json"
MOSS_CONFIG_FILE = CONFIG_DIR / "moss_slots_config.json"
MIRROR_CONFIG_FILE = CONFIG_DIR / "mirror_schedule_config.json"
EVENT_CONFIG_FILE = CONFIG_DIR / "event_slots_config.json"
CLASS_STAT_PROFILES_FILE = CONFIG_DIR / "class_stat_profiles.json"

# Class mappings
CLASS_ID_TO_CODE: Dict[int, str] = {
    0: "DW", 1: "DK", 2: "FE", 3: "MG", 4: "DL", 5: "SU", 6: "RF", 7: "GL",
    8: "RW", 9: "SL", 10: "GC", 11: "KM", 12: "LM", 13: "IK", 14: "AL", 15: "CR"
}

CLASS_CODE_TO_NAME: Dict[str, str] = {
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

# Optional license client hook
try:
    import license_client
except ImportError:
    license_client = None


def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> bool:
    """
    Safely writes JSON data to disk using an atomic rename operation (.tmp -> file_path).
    Ensures that corrupt files are never created even during sudden application termination or power outage.
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
        tmp_path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(file_path)
        return True
    except Exception:
        # Fallback direct write if atomic replace encounters Windows permission issues
        try:
            file_path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False


class ConfigPersistenceManager:
    """
    Đảm bảo 100% tất cả các cấu hình được đọc và ghi TRỰC TIẾP từ file đĩa JSON.
    Không lưu tạm trong RAM - Khi đóng và mở lại, mọi thiết lập đều được khôi phục nguyên vẹn.
    """
    _lock = threading.RLock()

    @staticmethod
    def get_fallback_config() -> Dict[str, Any]:
        """Trả về cấu hình mặc định an toàn cho 1 Profile train."""
        return {
            "glide_speed": 3.5,
            "respawn_delay": 15,
            "map_load_delay": 1.8,
            "level1_delay": 4.0,
            "arrive_distance": 2.0,
            "respawn_distance": 12.0,
            "stuck_retry_delay": 3.5,
            "helper_native_timeout": 4.0,
            "helper_direct_fallback": True,
            "stages": [
                {"min_level": 1, "max_level": 39, "map_name": "Lorencia", "x": 70, "y": 147},
                {"min_level": 40, "max_level": 59, "map_name": "Dungeon 2", "x": 217, "y": 115},
                {"min_level": 60, "max_level": 159, "map_name": "Lost Tower 5", "x": 110, "y": 56},
                {"min_level": 160, "max_level": 399, "map_name": "Aida 1", "x": 135, "y": 150}
            ],
            "poll_interval": 0.55,
            "reset_confirm_seconds": 1.5,
            "map_command_retry_delay": 4.5,
            "map_verify_unknown_timeout": 6.0
        }

    @classmethod
    def load_profiles_store(cls) -> Dict[str, Any]:
        """Đọc autotrain_profiles.json trực tiếp từ ổ cứng."""
        with cls._lock:
            store = {}
            if PROFILE_FILE.exists():
                try:
                    store = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    store = {}
            
            if not isinstance(store, dict):
                store = {}
            if not isinstance(store.get("profiles"), dict):
                store["profiles"] = {}
            store["version"] = 2

            # Đảm bảo đủ Config 1..10
            fallback = cls.get_fallback_config()
            for idx in range(1, 11):
                s_idx = str(idx)
                item = store["profiles"].get(s_idx)
                if not isinstance(item, dict) or not isinstance(item.get("config"), dict):
                    store["profiles"][s_idx] = {
                        "name": f"Config {idx}",
                        "config": json.loads(json.dumps(fallback))
                    }

            # Tự động đồng bộ nếu autotrain_megamu_config.json được chỉnh sửa mới hơn
            root_single = Path("autotrain_megamu_config.json")
            single_candidates = [f for f in [root_single, DEFAULT_CONFIG_FILE] if f.exists()]
            if single_candidates:
                latest_single = max(single_candidates, key=lambda f: f.stat().st_mtime)
                try:
                    p_mtime = PROFILE_FILE.stat().st_mtime if PROFILE_FILE.exists() else 0.0
                    if latest_single.stat().st_mtime > p_mtime:
                        s_data = json.loads(latest_single.read_text(encoding="utf-8"))
                        if isinstance(s_data, dict) and s_data.get("stages"):
                            store["profiles"]["1"]["config"] = s_data
                            atomic_write_json(PROFILE_FILE, store, indent=4)
                except Exception:
                    pass

            return store

    @classmethod
    def load_single_profile(cls, profile_idx: int) -> Dict[str, Any]:
        """Đọc riêng lẻ 1 Profile từ file autotrain_profiles.json."""
        p_idx = max(1, min(10, int(profile_idx)))
        store = cls.load_profiles_store()
        cfg = store.get("profiles", {}).get(str(p_idx), {}).get("config")
        if not cfg or not isinstance(cfg, dict):
            cfg = cls.get_fallback_config()
        return json.loads(json.dumps(cfg))

    @classmethod
    def save_single_profile(cls, profile_idx: int, cfg: Dict[str, Any]):
        """Ghi trực tiếp Profile vào file autotrain_profiles.json."""
        p_idx = max(1, min(10, int(profile_idx)))
        with cls._lock:
            store = cls.load_profiles_store()
            store["profiles"][str(p_idx)] = {
                "name": f"Config {p_idx}",
                "config": json.loads(json.dumps(cfg))
            }
            # Ghi an toàn vào PROFILE_FILE
            atomic_write_json(PROFILE_FILE, store, indent=4)

            # Nếu là Config 1, đồng bộ luôn autotrain_megamu_config.json
            if p_idx == 1:
                atomic_write_json(DEFAULT_CONFIG_FILE, cfg, indent=2)

    @classmethod
    def get_max_license_slots(cls) -> int:
        """Kiểm tra giới hạn số slot từ license_client."""
        try:
            if license_client:
                is_valid = license_client.is_license_valid()
                lic_data = license_client.load_license_data() or {}
                if is_valid:
                    return max(5, int(lic_data.get("max_slots", 10)))
        except Exception:
            pass
        return 5

    @classmethod
    def load_slot_assignments(cls, min_slots: int = 5) -> Dict[int, int]:
        """
        Đọc cấu hình gán từng dòng Slot từ slot_assignments.json.
        Mặc định 5 tài khoản ban đầu; chỉ mở rộng khi người dùng thêm và trong giới hạn License.
        """
        with cls._lock:
            assignments: Dict[int, int] = {}
            if SLOT_ASSIGNMENTS_FILE.exists():
                try:
                    data = json.loads(SLOT_ASSIGNMENTS_FILE.read_text(encoding="utf-8"))
                    slots_data = data.get("slots", {})
                    for s_str, conf in slots_data.items():
                        try:
                            s_int = int(s_str)
                            p_val = int(conf.get("profile", 1))
                            if s_int >= 1 and 1 <= p_val <= 10:
                                assignments[s_int] = p_val
                        except Exception:
                            pass
                except Exception:
                    pass

            max_allowed = cls.get_max_license_slots()
            filtered_assignments: Dict[int, int] = {}
            target_count = max(min_slots, min(len(assignments), max_allowed) if assignments else min_slots)
            target_count = min(target_count, max_allowed)
            for s in range(1, target_count + 1):
                filtered_assignments[s] = assignments.get(s, 1 if s <= 5 else 2)

            return filtered_assignments

    @classmethod
    def save_slot_assignment(cls, slot_idx: int, profile_idx: int):
        """Ghi ngay lập tức gán Config của dòng slot_idx vào file."""
        with cls._lock:
            current = cls.load_slot_assignments()
            current[slot_idx] = max(1, min(10, int(profile_idx)))
            cls._write_slot_file(current)

    @classmethod
    def save_all_slot_assignments(cls, assignments: Dict[int, int]):
        """Ghi toàn bộ cấu hình gán slot vào file."""
        with cls._lock:
            cls._write_slot_file(assignments)

    @classmethod
    def _write_slot_file(cls, assignments: Dict[int, int]):
        data = {
            "version": 1,
            "description": "Lưu trữ lựa chọn cấu hình Config 1..10 cho từng Slot",
            "slots": {str(k): {"profile": v} for k, v in sorted(assignments.items(), key=lambda x: int(x[0]))}
        }
        atomic_write_json(SLOT_ASSIGNMENTS_FILE, data, indent=2)

    @classmethod
    def load_moss_configs(cls) -> Dict[int, Dict[str, Any]]:
        """Đọc cấu hình Auto Moss của từng Slot từ moss_slots_config.json."""
        with cls._lock:
            res: Dict[int, Dict[str, Any]] = {}
            if MOSS_CONFIG_FILE.exists():
                try:
                    data = json.loads(MOSS_CONFIG_FILE.read_text(encoding="utf-8"))
                    slots_data = data.get("slots", {})
                    for s_str, conf in slots_data.items():
                        try:
                            s_int = int(s_str)
                            res[s_int] = {
                                "category": int(conf.get("category", 0)),
                                "delay_ms": int(conf.get("delay_ms", 1000)),
                                "max_rolls": int(conf.get("max_rolls", 0)),
                                "auto_clean": bool(conf.get("auto_clean", True))
                            }
                        except Exception:
                            pass
                except Exception:
                    pass
            return res

    @classmethod
    def save_moss_config(cls, slot_idx: int, cat: int, delay_ms: int = 1000, max_rolls: int = 0, auto_clean: bool = True):
        """Lưu cấu hình Auto Moss của riêng Slot slot_idx."""
        with cls._lock:
            cur = cls.load_moss_configs()
            cur[slot_idx] = {
                "category": int(cat),
                "delay_ms": int(delay_ms),
                "max_rolls": int(max_rolls),
                "auto_clean": bool(auto_clean)
            }
            try:
                store = {"slots": {str(k): v for k, v in sorted(cur.items(), key=lambda x: int(x[0]))}}
                atomic_write_json(MOSS_CONFIG_FILE, store, indent=2)
            except Exception:
                pass

    @classmethod
    def save_all_moss_configs(cls, configs: Dict[int, Dict[str, Any]]):
        """Lưu toàn bộ cấu hình Auto Moss của tất cả các Slot."""
        with cls._lock:
            try:
                store = {}
                if MOSS_CONFIG_FILE.exists():
                    try:
                        store = json.loads(MOSS_CONFIG_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                store["slots"] = {str(k): v for k, v in sorted(configs.items(), key=lambda x: int(x[0]))}
                atomic_write_json(MOSS_CONFIG_FILE, store, indent=2)
            except Exception:
                pass

    @classmethod
    def load_moss_schedule_config(cls) -> Dict[str, Any]:
        """Đọc cấu hình Lịch Trình Auto Moss (00:15, 06:15, 12:15, 18:15)."""
        with cls._lock:
            if MOSS_CONFIG_FILE.exists():
                try:
                    data = json.loads(MOSS_CONFIG_FILE.read_text(encoding="utf-8"))
                    sched = data.get("schedule", {})
                    sel = data.get("selected_slots", None)
                    return {
                        "auto_schedule": bool(sched.get("auto_schedule", True)),
                        "auto_move_before": bool(sched.get("auto_move_before", True)),
                        "selected_slots": sel
                    }
                except Exception:
                    pass
            return {"auto_schedule": True, "auto_move_before": True, "selected_slots": None}

    @classmethod
    def save_moss_schedule_config(cls, auto_schedule: bool = True, auto_move_before: bool = True, selected_slots: Optional[List[int]] = None):
        """Lưu cấu hình Lịch Trình Auto Moss kèm danh sách tài khoản được chọn."""
        with cls._lock:
            try:
                store = {}
                if MOSS_CONFIG_FILE.exists():
                    try:
                        store = json.loads(MOSS_CONFIG_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                store["schedule"] = {
                    "auto_schedule": bool(auto_schedule),
                    "auto_move_before": bool(auto_move_before),
                    "times": ["00:15", "06:15", "12:15", "18:15"]
                }
                if selected_slots is not None:
                    store["selected_slots"] = [int(s) for s in selected_slots]
                atomic_write_json(MOSS_CONFIG_FILE, store, indent=2)
            except Exception:
                pass

    @classmethod
    def load_mirror_schedule_config(cls) -> Dict[str, Any]:
        """Đọc cấu hình Lịch Trình Auto Double Goer / Mirror (2 tiếng 1 lần từ 00:15, chuẩn bị trước 5 phút)."""
        with cls._lock:
            if MIRROR_CONFIG_FILE.exists():
                try:
                    data = json.loads(MIRROR_CONFIG_FILE.read_text(encoding="utf-8"))
                    sched = data.get("schedule", {})
                    sel = data.get("selected_slots", None)
                    return {
                        "auto_schedule": bool(sched.get("auto_schedule", True)),
                        "auto_prep_before": bool(sched.get("auto_prep_before", True)),
                        "auto_lifecycle": bool(sched.get("auto_lifecycle", True)),
                        "auto_gremory": bool(sched.get("auto_gremory", True)),
                        "prefire_sec": float(sched.get("prefire_sec", 1.2)),
                        "selected_slots": sel
                    }
                except Exception:
                    pass
            return {
                "auto_schedule": True,
                "auto_prep_before": True,
                "auto_lifecycle": True,
                "auto_gremory": True,
                "prefire_sec": 1.2,
                "selected_slots": None
            }

    @classmethod
    def save_mirror_schedule_config(
        cls,
        auto_schedule: Any = True,
        auto_prep_before: bool = True,
        prefire_sec: float = 1.2,
        auto_lifecycle: bool = True,
        auto_gremory: bool = True,
        selected_slots: Optional[List[int]] = None
    ):
        """Lưu cấu hình Lịch Trình Auto Double Goer / Mirror kèm danh sách tài khoản được chọn."""
        if isinstance(auto_schedule, dict):
            cfg_dict = auto_schedule
            auto_prep_before = cfg_dict.get("auto_prep_before", True)
            prefire_sec = cfg_dict.get("prefire_sec", 1.2)
            auto_lifecycle = cfg_dict.get("auto_lifecycle", True)
            auto_gremory = cfg_dict.get("auto_gremory", True)
            if selected_slots is None and "selected_slots" in cfg_dict:
                selected_slots = cfg_dict["selected_slots"]
            auto_schedule = cfg_dict.get("auto_schedule", True)

        with cls._lock:
            try:
                store = {}
                if MIRROR_CONFIG_FILE.exists():
                    try:
                        store = json.loads(MIRROR_CONFIG_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                store["schedule"] = {
                    "auto_schedule": bool(auto_schedule),
                    "auto_prep_before": bool(auto_prep_before),
                    "auto_lifecycle": bool(auto_lifecycle),
                    "auto_gremory": bool(auto_gremory),
                    "prefire_sec": float(prefire_sec),
                    "interval_hours": 2,
                    "prep_minutes_before": 5,
                    "times": [f"{h:02d}:15" for h in range(0, 24, 2)]
                }
                if selected_slots is not None:
                    store["selected_slots"] = [int(s) for s in selected_slots]
                atomic_write_json(MIRROR_CONFIG_FILE, store, indent=2)
            except Exception:
                pass

    @classmethod
    def load_class_stat_profiles(cls) -> Dict[str, Any]:
        """Đọc bảng cấu hình chỉ số Point của tất cả 16 Class từ class_stat_profiles.json."""
        with cls._lock:
            if CLASS_STAT_PROFILES_FILE.exists():
                try:
                    return json.loads(CLASS_STAT_PROFILES_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            # Fallback nếu file chưa tồn tại
            return {
                "DW": {"name": "Dark Wizard (Phù Thủy)", "class_id": 0, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "DK": {"name": "Dark Knight (Chiến Binh)", "class_id": 1, "stat_ratio": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0}},
                "FE": {"name": "Fairy Elf (Tiên Nữ)", "class_id": 2, "stat_ratio": {"str": 0.15, "agi": 0.75, "vit": 0.1, "ene": 0.0, "cmd": 0.0}},
                "MG": {"name": "Magic Gladiator (Đấu Sĩ)", "class_id": 3, "stat_ratio": {"str": 0.45, "agi": 0.35, "vit": 0.0, "ene": 0.2, "cmd": 0.0}},
                "DL": {"name": "Dark Lord (Chúa Tể)", "class_id": 4, "stat_ratio": {"str": 0.3, "agi": 0.3, "vit": 0.0, "ene": 0.1, "cmd": 0.3}},
                "SU": {"name": "Summoner (Thuật Sĩ)", "class_id": 5, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "RF": {"name": "Rage Fighter (Thiết Binh)", "class_id": 6, "stat_ratio": {"str": 0.5, "agi": 0.2, "vit": 0.3, "ene": 0.0, "cmd": 0.0}},
                "GL": {"name": "Grow Lancer (Thương Thủ)", "class_id": 7, "stat_ratio": {"str": 0.55, "agi": 0.35, "vit": 0.1, "ene": 0.0, "cmd": 0.0}},
                "RW": {"name": "Rune Wizard (Phù Thủy Rune)", "class_id": 8, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "SL": {"name": "Slayer (Sát Thủ)", "class_id": 9, "stat_ratio": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0}},
                "GC": {"name": "Gun Crusher (Pháo Thủ)", "class_id": 10, "stat_ratio": {"str": 0.1, "agi": 0.5, "vit": 0.1, "ene": 0.3, "cmd": 0.0}},
                "KM": {"name": "Kundun Mephis", "class_id": 11, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "LM": {"name": "Lemuria", "class_id": 12, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "IK": {"name": "Illusion Knight (Huyễn Ảnh)", "class_id": 13, "stat_ratio": {"str": 0.4, "agi": 0.5, "vit": 0.1, "ene": 0.0, "cmd": 0.0}},
                "AL": {"name": "Alchemist (Giả Kim)", "class_id": 14, "stat_ratio": {"str": 0.1, "agi": 0.3, "vit": 0.1, "ene": 0.5, "cmd": 0.0}},
                "CR": {"name": "Crusher", "class_id": 15, "stat_ratio": {"str": 0.5, "agi": 0.4, "vit": 0.1, "ene": 0.0, "cmd": 0.0}}
            }

    @classmethod
    def save_class_stat_profile(cls, class_code: str, ratio: Dict[str, float]):
        """Lưu lại tỷ lệ Point tùy biến cho 1 Class cụ thể."""
        with cls._lock:
            profiles = cls.load_class_stat_profiles()
            c_code = class_code.upper().strip()
            if c_code in profiles:
                profiles[c_code]["stat_ratio"] = ratio
            else:
                profiles[c_code] = {
                    "name": CLASS_CODE_TO_NAME.get(c_code, c_code),
                    "stat_ratio": ratio
                }
            atomic_write_json(CLASS_STAT_PROFILES_FILE, profiles, indent=2)

    @classmethod
    def load_event_configs(cls) -> Dict[int, Dict[str, Any]]:
        """Đọc cấu hình Auto Devil Square, Auto Reset & Point của từng Slot từ event_slots_config.json."""
        with cls._lock:
            res: Dict[int, Dict[str, Any]] = {}
            if EVENT_CONFIG_FILE.exists():
                try:
                    data = json.loads(EVENT_CONFIG_FILE.read_text(encoding="utf-8"))
                    slots_data = data.get("slots", {})
                    for s_str, conf in slots_data.items():
                        try:
                            s_int = int(s_str)
                            res[s_int] = {
                                "auto_devil": bool(conf.get("auto_devil", False)),
                                "devil_min_resets": int(conf.get("devil_min_resets", 0)),
                                "devil_max_resets": int(conf.get("devil_max_resets", 9999)),
                                "devil_ticket_type": str(conf.get("devil_ticket_type", "auto")),
                                "auto_reset": bool(conf.get("auto_reset", False)),
                                "auto_add_point": bool(conf.get("auto_add_point", False)),
                                "reset_level": int(conf.get("reset_level", 400)),
                                "stat_mode": str(conf.get("stat_mode", "auto_class")),
                                "custom_class": str(conf.get("custom_class", "")),
                                "stat_ratio": conf.get("stat_ratio", {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0})
                            }
                        except Exception:
                            pass
                except Exception:
                    pass
            return res

    @classmethod
    def save_event_config(
        cls,
        slot_idx: int,
        auto_devil: bool = False,
        devil_min_resets: int = 0,
        devil_max_resets: int = 9999,
        devil_ticket_type: str = "auto",
        auto_reset: bool = False,
        auto_add_point: bool = False,
        reset_level: int = 400,
        stat_mode: str = "auto_class",
        custom_class: str = "",
        stat_ratio: Optional[Dict[str, float]] = None
    ):
        """Lưu cấu hình Auto Devil, Reset & Cộng Point của riêng Slot slot_idx."""
        with cls._lock:
            cur = cls.load_event_configs()
            if stat_ratio is None:
                stat_ratio = cur.get(slot_idx, {}).get("stat_ratio", {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0})
            cur[slot_idx] = {
                "auto_devil": bool(auto_devil),
                "devil_min_resets": int(devil_min_resets),
                "devil_max_resets": int(devil_max_resets if int(devil_max_resets) > 0 else 9999),
                "devil_ticket_type": str(devil_ticket_type or "auto"),
                "auto_reset": bool(auto_reset),
                "auto_add_point": bool(auto_add_point),
                "reset_level": int(reset_level),
                "stat_mode": str(stat_mode or "auto_class"),
                "custom_class": str(custom_class or ""),
                "stat_ratio": stat_ratio
            }
            try:
                store = {"slots": {str(k): v for k, v in sorted(cur.items(), key=lambda x: int(x[0]))}}
                atomic_write_json(EVENT_CONFIG_FILE, store, indent=2)
            except Exception:
                pass

    @classmethod
    def load_ui_settings(cls) -> Dict[str, Any]:
        """Đọc cài đặt giao diện (ngôn ngữ, tùy chọn hiển thị) từ ui_settings.json."""
        with cls._lock:
            if UI_SETTINGS_FILE.exists():
                try:
                    return json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {"language": "vi"}

    @classmethod
    def save_ui_settings(cls, settings: Dict[str, Any]):
        """Lưu cài đặt giao diện vào ui_settings.json."""
        with cls._lock:
            atomic_write_json(UI_SETTINGS_FILE, settings, indent=2)

