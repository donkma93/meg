#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - v3.0 (PySide6 / Qt6 Native 60FPS Edition)
=======================================================================
Giao diện Desktop Native sử dụng Qt6 (PySide6):
- Chuyển tab tức thì < 1ms bằng QStackedWidget
- Bảng đa slot (1..50 acc) mượt 60fps bằng QTableWidget + State Diffing
- Kéo cửa sổ & cuộn chuột siêu mượt (GPU/Direct2D native)
- Tái sử dụng 100% logic lõi (SlotController, DirectEngine, Mirror, Moss, Auto Train, Party, License)
- Đã ẩn hoàn toàn chức năng Auto Login để tối ưu tối đa độ nhẹ
"""

import os
import sys
import json
import time
import ctypes
import signal
import threading
import traceback
import faulthandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


_BOOT_TRACE_PATH = Path(os.environ.get("TEMP", os.environ.get("TMP", "."))) / "megamu_qt_boot.log"
try:
    _fh_file = open(_BOOT_TRACE_PATH, "w", encoding="utf-8")
    faulthandler.enable(file=_fh_file, all_threads=True)
except Exception:
    _fh_file = None


def _boot_trace(step: str) -> None:
    try:
        with open(_BOOT_TRACE_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {step}\n")
            f.flush()
    except Exception:
        pass


def _report_fatal_startup_error(err: BaseException) -> None:
    """Ghi log và hiển thị hộp thoại Windows nếu ứng dụng lỗi ngay lúc khởi động."""
    tb_txt = traceback.format_exc()
    log_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] FATAL STARTUP ERROR:\n{tb_txt}\n"
    candidates = []
    try:
        onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
        if onefile_dir:
            candidates.append(Path(onefile_dir) / "gui_crash.log")
        candidates.append(Path(sys.executable).resolve().parent / "gui_crash.log")
    except Exception:
        pass
    try:
        candidates.append(Path(os.environ.get("TEMP", os.environ.get("TMP", "."))) / "megamu_qt_crash.log")
    except Exception:
        pass
    saved_log = ""
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(log_msg)
            saved_log = str(p)
            break
        except Exception:
            continue
    if sys.platform == "win32":
        try:
            detail = f"Ứng dụng gặp lỗi khi khởi động:\n\n{type(err).__name__}: {err}"
            if saved_log:
                detail += f"\n\nChi tiết đã lưu tại:\n{saved_log}"
            ctypes.windll.user32.MessageBoxW(0, detail, "MEGAMU Auto Train Dashboard - Lỗi khởi động", 0x10)
        except Exception:
            pass


def _install_fatal_excepthook():
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        tb_txt = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            err = exc_value if isinstance(exc_value, BaseException) else RuntimeError(str(exc_value))
            try:
                onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
                p = (Path(onefile_dir) if onefile_dir else Path(sys.executable).resolve().parent) / "gui_crash.log"
                with open(p, "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNCAUGHT:\n{tb_txt}\n")
            except Exception:
                pass
            if sys.platform == "win32":
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Lỗi không mong muốn:\n\n{exc_type.__name__}: {exc_value}",
                    "MEGAMU Auto Train Dashboard - Lỗi",
                    0x10,
                )
        except Exception:
            pass
    sys.excepthook = _hook


_install_fatal_excepthook()

try:
    import psutil
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QFrame, QLabel, QPushButton, QStackedWidget, QMessageBox
    )
except BaseException as _boot_err:
    _report_fatal_startup_error(_boot_err)
    raise

# UTF-8 + high-resolution Windows timer
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("megamu.auto.dashboard.qt6")
    except Exception:
        pass

try:
    from ui.state import AppStateManager
    from ui.engine_sync import BackgroundEngineSync, build_enhanced_detected_games
    from services.party_manager import PartyManager

    from ui_qt.theme import DARK_OPS_QSS, build_dark_palette
    from ui_qt.train_tab import TrainTabQt, get_default_profile_options
    from ui_qt.profiles_tab import ProfilesTabQt
    from ui_qt.mirror_tab import MirrorTabQt
    from ui_qt.moss_tab import MossTabQt, moss_cat_id, moss_cat_name, MOSS_CAT_OPTIONS
    from ui_qt.quest_tab import QuestTabQt
    from ui_qt.logs_tab import LogsTabQt
    from meg_quest_automation import QuestConfigManager, QuestSlotRunner, summarize_quest_snapshot
    from meg_pk_reporter import PkReportConfigManager, execute_pk_report
    from ui_qt.dialogs import (
        JunkDisposalDialogQt,
        LicenseDialogQt,
        DevilConfigDialogQt,
        PointConfigDialogQt,
        PartyConfigDialogQt,
        PkReportConfigDialogQt,
        TelegramConfigDialogQt,
        UpdateDialogQt,
    )

    from meg_gui import (
        BASE_DIR,
        APP_NAME,
        APP_VERSION,
        LOGO_FILE,
        ICON_FILE,
        SlotController,
        ConfigPersistenceManager,
        DEFAULT_SLOTS,
        MAX_SLOTS,
        character_name_from_window_title,
        server_from_window_title,
        DashboardApp,
        MEGAMUWindowManager,
    )
except BaseException as _imp_err:
    _report_fatal_startup_error(_imp_err)
    raise

try:
    from meg_direct_engine import MegDirectEngine
except ImportError:
    MegDirectEngine = None

try:
    import license_client
except ImportError:
    license_client = None

try:
    from telegram_notifier import send_telegram_raw, TelegramConfig, MirrorTelegramNotifier
except ImportError:
    send_telegram_raw = None
    TelegramConfig = None
    MirrorTelegramNotifier = None

try:
    import updater
except ImportError:
    updater = None


class _BoolCheckboxProxy:
    """Proxy tương thích .get()/.select()/.deselect() cho SlotController & Schedulers."""

    def __init__(self, initial: bool = True):
        self._value = 1 if initial else 0

    def get(self):
        return self._value

    def select(self):
        self._value = 1

    def deselect(self):
        self._value = 0

    def set(self, enabled: bool):
        self._value = 1 if enabled else 0


class _FakeEntry:
    def __init__(self, value):
        self._value = str(value)

    def get(self):
        return self._value

    def delete(self, *a, **k):
        self._value = ""

    def insert(self, idx, text):
        self._value = str(text)


def get_map_names() -> List[str]:
    cfg = BASE_DIR / "config" / "map_commands.json"
    if not cfg.exists():
        cfg = BASE_DIR / "map_commands.json"
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
            names = [m["name"] for m in d.get("maps", []) if m.get("name")]
            if names:
                return names
        except Exception:
            pass
    return ["Lorencia", "Noria", "Devias", "Dungeon", "Lost Tower", "Atlans", "Tarkan", "Aida", "Kanturu", "Karutan"]


def parse_slot_game_choice(val: str) -> Tuple[Optional[int], str, str]:
    """Trích xuất (pid, char_name, server_str) từ chuỗi dropdown tiến trình."""
    if not val or val in ("--", "Chọn...", ""):
        return None, "", ""
    import re
    m = re.search(r"(?:PID\s*[:#]?\s*)?(\d+)\s*\)", val)
    if not m:
        m = re.search(r"\b\d+\b", val)
    if not m:
        return None, "", ""
    pid = int(m.group(1) if m.groups() else m.group(0))

    raw_prefix = val.split("(")[0].strip()
    c_name = ""
    srv_str = ""
    if "[" in raw_prefix and "]" in raw_prefix:
        c_name = raw_prefix.split("[")[0].strip()
        srv_str = raw_prefix.split("[")[1].split("]")[0].strip()
    else:
        c_name = raw_prefix.strip()
    if c_name.upper().startswith("MEGAMU"):
        c_name = ""
    return pid, c_name, srv_str


class MetricChipQt(QFrame):
    """Chip thống kê nhỏ trên Header với State Diffing."""

    def __init__(self, title: str, value: str = "0", tone: str = "info", width: int = 86, clickable: bool = False, on_click=None):
        super().__init__()
        self.setProperty("metricChip", True)
        self.setProperty("tone", tone)
        self.setFixedSize(width, 38)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        self._on_click = on_click
        self._last = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(0)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 700;")
        self.lbl_v = QLabel(value)
        self.lbl_v.setStyleSheet("color: #7dd3fc; font-size: 12px; font-weight: 800;")
        lay.addWidget(lbl_t)
        lay.addWidget(self.lbl_v)
        self.set_value(value, tone)

    def set_value(self, value: str, tone: str = "info"):
        val_s = str(value)
        if self._last == (val_s, tone):
            return
        self._last = (val_s, tone)
        self.lbl_v.setText(val_s)
        fg_map = {
            "info": "#7dd3fc",
            "ok": "#4ade80",
            "warn": "#fbbf24",
            "danger": "#fb7185",
            "neutral": "#94a3b8",
        }
        self.lbl_v.setStyleSheet(f"color: {fg_map.get(tone, '#7dd3fc')}; font-size: 12px; font-weight: 800;")
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if callable(self._on_click):
            self._on_click()
        super().mousePressEvent(event)


class DashboardAppQt(QMainWindow):
    """MEGAMU Dashboard V3 — PySide6 (Qt6) Native 60FPS."""

    _after_signal = Signal(int, object)

    MOSS_CAT_OPTIONS = MOSS_CAT_OPTIONS

    def __init__(self):
        _boot_trace("DashboardAppQt.__init__: start")
        super().__init__()
        self._after_signal.connect(self._exec_on_main_thread, Qt.QueuedConnection)

        self.state_mgr = AppStateManager()
        self.running = True
        self._is_closing = False
        self.active_tab_name = "train"
        self.active_tab = "train"
        self.detected_games: Dict[int, str] = {}
        self.slot_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.moss_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.mirror_ui_elements: Dict[int, Dict[str, Any]] = {}
        self.account_manager = None
        self.account_mgr = None
        self.update_info = None
        self.is_update_mandatory = False
        self._last_proc_options_cache: Optional[List[str]] = None
        self._last_mirror_tab_ticket_scan = 0.0

        self.setWindowTitle(f"{APP_NAME} - v3.0 Qt6 Native")
        self.resize(1240, 790)
        self.setMinimumSize(1080, 660)
        self._setup_window_icon()

        # Load configs & controllers
        self.maps_list = get_map_names()
        self.slot_assignments = ConfigPersistenceManager.load_slot_assignments(DEFAULT_SLOTS)
        moss_cfgs = ConfigPersistenceManager.load_moss_configs()
        moss_sched_cfg = ConfigPersistenceManager.load_moss_schedule_config()
        mirror_sched_cfg = ConfigPersistenceManager.load_mirror_schedule_config()
        moss_sel = moss_sched_cfg.get("selected_slots", None)
        mirror_sel = mirror_sched_cfg.get("selected_slots", None)

        self.controllers: List[SlotController] = []
        for i in sorted(self.slot_assignments.keys()):
            assigned_c = self.slot_assignments.get(i, 1 if i <= 5 else 2)
            ctrl = SlotController(i, self, default_profile=assigned_c)
            c_data = moss_cfgs.get(i, {})
            ctrl.moss_category = int(c_data.get("category", 0))
            ctrl.moss_delay_ms = int(c_data.get("delay_ms", 1000))
            ctrl.moss_max_rolls = int(c_data.get("max_rolls", 0))
            ctrl.moss_auto_clean = bool(c_data.get("auto_clean", True))
            ctrl.moss_clean_equipment_trash = bool(c_data.get("clean_equipment_trash", True))
            ctrl.moss_sell_excellent = bool(c_data.get("sell_excellent", True))
            ctrl.mirror_enabled = (i in mirror_sel) if (mirror_sel is not None) else True
            ctrl.moss_enabled = (i in moss_sel) if (moss_sel is not None) else True
            self.controllers.append(ctrl)

        self.state_mgr.sync_slots([c.slot_idx for c in self.controllers])

        # Telegram + Scheduler proxies (tương thích 100% SlotController & DashboardApp schedulers)
        self.telegram_config = TelegramConfig() if TelegramConfig else None
        self.mirror_telegram_notifier = (
            MirrorTelegramNotifier(self.telegram_config)
            if (MirrorTelegramNotifier and self.telegram_config) else None
        )
        self.cb_mirror_telegram_notify = _BoolCheckboxProxy(
            bool(getattr(self.telegram_config, "enabled", False)) if self.telegram_config else False
        )
        self.cb_mirror_auto_schedule = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_schedule", True)))
        self.cb_mirror_auto_lifecycle = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_lifecycle", True)))
        self.cb_mirror_auto_gremory = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_gremory", True)))
        self.cb_mirror_auto_prep_before = _BoolCheckboxProxy(bool(mirror_sched_cfg.get("auto_prep_before", True)))
        self.cb_moss_auto_schedule = _BoolCheckboxProxy(bool(moss_sched_cfg.get("auto_schedule", True)))
        self.cb_moss_auto_move_before = _BoolCheckboxProxy(bool(moss_sched_cfg.get("auto_move_before", True)))
        self.cb_clean_equipment_trash = _BoolCheckboxProxy(True)
        self.cb_sell_excellent = _BoolCheckboxProxy(True)
        self.batch_moss_clean_cb = _BoolCheckboxProxy(True)

        raw_delay_val = mirror_sched_cfg.get("interval_ms", mirror_sched_cfg.get("snipe_interval_ms", 10))
        self.mirror_snipe_delay_ms = int(raw_delay_val) if raw_delay_val is not None else 10
        self.mirror_snipe_dur_s = float(mirror_sched_cfg.get("max_duration_s", 15.0) or 15.0)
        self.mirror_prefire_sec = float(mirror_sched_cfg.get("prefire_sec", 2.0) if mirror_sched_cfg.get("prefire_sec") is not None else 2.0)
        self.mirror_zero_confirm = bool(mirror_sched_cfg.get("zero_confirm", True))
        raw_stag_val = mirror_sched_cfg.get("stagger_ms", -1)
        self.mirror_stagger_ms = int(raw_stag_val) if raw_stag_val is not None else -1
        self._mirror_last_rtt_ms = -1.0
        self._mirror_clock_offset_ms = float(mirror_sched_cfg.get("clock_offset_ms", 0.0) or 0.0)
        self._mirror_clock_calibrated = abs(self._mirror_clock_offset_ms) > 0.5
        self._last_scheduled_gate_open_epoch_ms = 0.0
        self._last_scheduled_offset_base_ms = self._mirror_clock_offset_ms
        self._last_scheduled_event_key = None
        self._last_learned_event_key = None
        self._last_mirror_ntpsync_key = None
        self._last_mirror_prestage_key = None
        self._last_mirror_arm_key = None
        self._last_moss_trigger_key = None
        self._last_moss_stop_key = None
        self._last_moss_move_key = None
        self._last_mirror_event_snipe_key = None
        self._last_mirror_cache_key = None
        self._last_gate_open_retry_ts = 0.0
        self._last_mirror_prefire_key = None
        self._last_mirror_prep_key = None
        self._mirror_poll_tick = 0
        self._mirror_sched_cfg_init = mirror_sched_cfg
        self._moss_sched_cfg_init = moss_sched_cfg

        self.mirror_snipe_delay_entry = _FakeEntry(self.mirror_snipe_delay_ms)
        self.mirror_snipe_dur_entry = _FakeEntry(self.mirror_snipe_dur_s)
        self.mirror_prefire_sec_entry = _FakeEntry(self.mirror_prefire_sec)
        self.mirror_stagger_ms_entry = _FakeEntry(self.mirror_stagger_ms)

        # Auto Quest (Nhiệm vụ Cấp 2 / Marlon / Cấp 3)
        self.quest_config_mgr = QuestConfigManager(BASE_DIR)
        self.quest_config: Dict[str, Any] = self.quest_config_mgr.load()
        self.quest_runners: Dict[int, QuestSlotRunner] = {}

        # Auto Report PK (Về Noria / Lorencia / Devias tìm Lính Canh)
        self.pk_report_config_mgr = PkReportConfigManager(BASE_DIR)
        self.pk_report_config: Dict[str, Any] = self.pk_report_config_mgr.load()

        # Build Qt6 Shell
        _boot_trace("DashboardAppQt.__init__: _build_shell")
        self._build_shell()

        # Start background sync
        _boot_trace("DashboardAppQt.__init__: BackgroundEngineSync")
        self.engine_sync = BackgroundEngineSync(
            controllers_provider=lambda: self.controllers,
            state_mgr=self.state_mgr,
        )
        self.engine_sync.start()

        # Qt Main Thread Heartbeat (250ms, Zero-Lag)
        _boot_trace("DashboardAppQt.__init__: timers/schedulers")
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(250)
        self._heartbeat_timer.timeout.connect(self._ui_heartbeat)
        self._heartbeat_timer.start()

        # Schedulers (Mirror / Moss / Telegram / License / Update)
        self.after(3000, self._periodic_moss_scheduler)
        self.after(3500, self._periodic_mirror_scheduler)
        if hasattr(self, "_monitor_mirror_telemetry_for_telegram"):
            self.after(8000, self._monitor_mirror_telemetry_for_telegram)
        self.after(3000, self._periodic_license_monitor)
        self.after(1200, lambda: threading.Thread(target=self._verify_license_async, daemon=True).start())
        self.after(2800, self._check_initial_license)
        self.after(3500, lambda: threading.Thread(target=self._check_update_async, daemon=True).start())

        # Dựng trước nhẹ nhàng các tab Qt6 từng tab một sau khi cửa sổ hiện (~10-30ms/tab) để lần bấm đầu tiên cũng tức thì
        self.after(350, self._warmup_qt_tabs_step)

        _boot_trace("DashboardAppQt.__init__: log_message + stats")
        self.log_message("🚀 MEGAMU Dashboard V3 (Qt6 Native 60FPS) đã khởi động.", "SUCCESS")
        self.log_message(f"Đang quản lý {len(self.controllers)} slots · Auto Login đã ẩn theo yêu cầu.", "INFO")
        self._update_header_stats_internal()
        self.update_modules_visibility()
        self.apply_license_lock_state()
        _boot_trace("DashboardAppQt.__init__: done")

    # ==========================================================================
    # THREAD-SAFE `after()` BRIDGE (TƯƠNG THÍCH 100% TKINTER API)
    # ==========================================================================
    def after(self, delay_ms: int, func: Callable, *args):
        """Cho phép mọi luồng nền gọi `self.app.after(ms, fn)` an toàn trên Main Qt Thread."""
        if not self.running and self._is_closing:
            return
        cb = (lambda: func(*args)) if args else func
        self._after_signal.emit(max(0, int(delay_ms or 0)), cb)

    def _exec_on_main_thread(self, delay_ms: int, cb: Callable):
        if self._is_closing:
            return
        if delay_ms <= 0:
            try:
                cb()
            except Exception:
                pass
        else:
            QTimer.singleShot(delay_ms, cb)

    def _setup_window_icon(self):
        try:
            ico_p = ICON_FILE if (hasattr(ICON_FILE, "exists") and ICON_FILE.exists()) else (BASE_DIR / "megamu_dashboard_icon.ico")
            logo_p = LOGO_FILE if (hasattr(LOGO_FILE, "exists") and LOGO_FILE.exists()) else (BASE_DIR / "megamu_dashboard_logo.png")
            if ico_p.exists():
                self.setWindowIcon(QIcon(str(ico_p)))
            elif logo_p.exists():
                self.setWindowIcon(QIcon(str(logo_p)))
        except Exception:
            pass

    # ==========================================================================
    # SHELL: HEADER + NAV + STACKED VIEWS + FOOTER
    # ==========================================================================
    def _build_shell(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Header bar
        hdr = QFrame()
        hdr.setObjectName("HeaderBar")
        hdr.setFixedHeight(60)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 8, 14, 8)
        hl.setSpacing(10)

        if LOGO_FILE.exists():
            pix = QPixmap(str(LOGO_FILE))
            if not pix.isNull():
                lbl_logo = QLabel()
                lbl_logo.setPixmap(pix.scaledToHeight(34, Qt.SmoothTransformation))
                hl.addWidget(lbl_logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        t_row = QHBoxLayout()
        t_row.setSpacing(8)
        lbl_title = QLabel("MEGAMU AUTO TRAIN")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f1f5f9;")
        lbl_ver = QLabel(f"{APP_VERSION} · Qt6 Native 60FPS")
        lbl_ver.setStyleSheet("font-size: 10px; font-weight: 700; color: #2dd4bf;")
        t_row.addWidget(lbl_title)
        t_row.addWidget(lbl_ver)
        t_row.addStretch(1)
        lbl_sub = QLabel("Native Desktop Dashboard · GPU-accelerated · hỗ trợ 1–50 tài khoản")
        lbl_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        title_col.addLayout(t_row)
        title_col.addWidget(lbl_sub)
        hl.addLayout(title_col)

        hl.addStretch(1)

        # Metric chips
        self.chip_games = MetricChipQt("GAME", "0", "info", 74)
        self.chip_conn = MetricChipQt("KẾT NỐI", "0", "ok", 82)
        self.chip_auto = MetricChipQt("AUTO", "0", "warn", 74)
        self.chip_license = MetricChipQt("LICENSE", "...", "neutral", 142, clickable=True, on_click=self.open_license_dialog)
        for ch in (self.chip_games, self.chip_conn, self.chip_auto, self.chip_license):
            hl.addWidget(ch)

        hl.addSpacing(6)

        btn_logs = QPushButton("📋 Nhật ký")
        btn_logs.setProperty("tone", "ghost")
        btn_logs.setFixedHeight(30)
        btn_logs.clicked.connect(lambda: self.switch_tab("logs"))

        self.btn_update = QPushButton("🔄 Cập nhật")
        self.btn_update.setProperty("tone", "ghost")
        self.btn_update.setFixedHeight(30)
        self.btn_update.clicked.connect(lambda: self.check_for_updates_ui(manual=True))

        btn_lic = QPushButton("🔑 License")
        btn_lic.setProperty("tone", "primary")
        btn_lic.setFixedHeight(30)
        btn_lic.clicked.connect(self.open_license_dialog)

        btn_help = QPushButton("?")
        btn_help.setProperty("tone", "ghost")
        btn_help.setFixedSize(32, 30)
        btn_help.clicked.connect(self.show_help)

        for b in (btn_logs, self.btn_update, btn_lic, btn_help):
            hl.addWidget(b)
        root.addWidget(hdr)

        # 1.5. License Lock Banner (chỉ hiện khi chưa kích hoạt / hết hạn / thiếu DLL / bản cập nhật bắt buộc)
        self.license_lock_banner = QFrame()
        self.license_lock_banner.setStyleSheet(
            "QFrame { background-color: #3b1219; border-bottom: 1px solid #ef4444; }"
        )
        self.license_lock_banner.setFixedHeight(34)
        bl_lock = QHBoxLayout(self.license_lock_banner)
        bl_lock.setContentsMargins(16, 2, 14, 2)
        bl_lock.setSpacing(10)
        self._license_banner_lbl = QLabel("🔒 BẢN QUYỀN CHƯA KÍCH HOẠT — CHỨC NĂNG ĐANG BỊ KHÓA")
        self._license_banner_lbl.setStyleSheet("color: #fca5a5; font-weight: 700; font-size: 12px;")
        self._license_banner_btn = QPushButton("🔑 Kích hoạt / Đồng Bộ")
        self._license_banner_btn.setProperty("tone", "danger")
        self._license_banner_btn.setFixedHeight(24)
        self._license_banner_btn.clicked.connect(self.open_license_dialog)
        bl_lock.addWidget(self._license_banner_lbl)
        bl_lock.addStretch(1)
        bl_lock.addWidget(self._license_banner_btn)
        self.license_lock_banner.setVisible(False)
        root.addWidget(self.license_lock_banner)

        # 2. Navigation Tabs Bar (ẩn Auto Login hoàn toàn)
        nav = QFrame()
        nav.setObjectName("NavBar")
        nav.setFixedHeight(42)
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(12, 4, 14, 4)
        nl.setSpacing(6)

        self.nav_buttons: Dict[str, QPushButton] = {}
        tab_defs = [
            ("train", "▶  01  Auto Train"),
            ("profiles", "⚙  02  Config"),
            ("mirror", "⚡  03  Mirror"),
            ("moss", "🎲  04  Moss"),
            ("quest", "⚔  05  Nhiệm Vụ"),
            ("logs", "📋  06  Logs"),
        ]
        for tid, label in tab_defs:
            btn = QPushButton(label)
            btn.setProperty("navTab", True)
            btn.setCheckable(True)
            btn.setChecked(tid == "train")
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=tid: self.switch_tab(t))
            nl.addWidget(btn)
            self.nav_buttons[tid] = btn

        nl.addStretch(1)
        lbl_brand = QLabel("MEGATEAM")
        lbl_brand.setStyleSheet("color: #2dd4bf; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        nl.addWidget(lbl_brand)
        root.addWidget(nav)

        # 3. QStackedWidget (0ms instant tab switching!)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.train_view = TrainTabQt(
            controllers=self.controllers,
            on_toggle_slot=self.on_slot_auto_toggle,
            on_toggle_all=self.toggle_all_auto,
            on_connect_all=self.connect_all,
            on_assign_all=self.assign_all,
            on_refresh_games=self.refresh_games,
            on_arrange_windows=self.arrange_windows_by_preset,
            on_slot_pid_selected=self.on_slot_pid_selected,
            on_slot_profile_selected=self.on_slot_profile_selected,
            on_stack_jewels=self.stack_all_jewels,
            on_devil_config=self.open_devil_global_config_dialog,
            on_point_config=self.open_point_global_config_dialog,
            on_toggle_point=self.on_toggle_slot_point,
            on_open_point_config=lambda _s: self.open_point_global_config_dialog(),
            on_close_games=self.close_all_games,
            on_open_slot_config=self.open_slot_profile_editor,
            on_add_slot=self.add_new_slot,
            on_remove_slot=self.remove_last_slot,
            on_telegram_config=self.open_telegram_settings_dialog,
            on_party_config=self.open_party_config_dialog,
            on_pk_report_config=self.open_pk_report_config_dialog,
            on_slot_delay_changed=self.on_slot_delay_changed,
        )
        self.stack.addWidget(self.train_view)

        self.profiles_view: Optional[ProfilesTabQt] = None
        self.mirror_view: Optional[MirrorTabQt] = None
        self.moss_view: Optional[MossTabQt] = None
        self.quest_view: Optional[QuestTabQt] = None
        self.logs_view: Optional[LogsTabQt] = None

        # 4. Footer bar
        ftr = QFrame()
        ftr.setObjectName("FooterBar")
        ftr.setFixedHeight(26)
        fl = QHBoxLayout(ftr)
        fl.setContentsMargins(14, 2, 14, 2)
        self.footer_stats_lbl = QLabel(f"Total: {len(self.controllers)} slots · Connected: 0 · Running: 0 · Games: 0")
        self.footer_stats_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_hotline = QLabel("Phát triển bởi MEGATEAM · Hotline 036.203.1354")
        lbl_hotline.setStyleSheet("color: #64748b; font-size: 11px;")
        fl.addWidget(self.footer_stats_lbl)
        fl.addStretch(1)
        fl.addWidget(lbl_hotline)
        root.addWidget(ftr)

    # ==========================================================================
    # TAB SWITCHING (0ms QStackedWidget + On-Demand Views)
    # ==========================================================================
    def _ensure_profiles_view(self) -> ProfilesTabQt:
        if self.profiles_view is None:
            self.profiles_view = ProfilesTabQt(
                maps_list=self.maps_list,
                config_persistence_mgr=ConfigPersistenceManager,
                on_profile_saved=self._on_profile_saved,
                on_log=self.log_message,
            )
            self.stack.addWidget(self.profiles_view)
        return self.profiles_view

    def _ensure_mirror_view(self) -> MirrorTabQt:
        if self.mirror_view is None:
            self.mirror_view = MirrorTabQt(
                controllers=self.controllers,
                on_trigger_mirror=self.trigger_mirror_snipe,
                on_enter_mirror=self.enter_all_mirror,
                on_mirror_lifecycle=self.trigger_all_mirror_lifecycle,
                on_claim_gremory=self.claim_all_gremory_case_items,
                on_move_lugard=self.move_all_to_event_map,
                on_check_tickets=self.check_all_mirror_tickets,
                on_prepare_mirror=getattr(self, "prepare_all_mirror_event", None),
                on_click_mirror_npc=getattr(self, "click_all_mirror_npc", None),
                on_stop_mirror=getattr(self, "stop_all_mirror_auto", None),
                on_toggle_participant=lambda s, en: self.toggle_event_participant("mirror", s, en),
                on_save_schedule=lambda opts: self.save_event_schedule("mirror", opts),
                on_toggle_telegram=self._on_events_telegram_toggle,
                on_telegram_settings=self.open_telegram_settings_dialog,
                on_snipe_slot=getattr(self, "manual_snipe_mirror_slot", None),
            )
            self.mirror_view.apply_schedule_config(self._mirror_sched_cfg_init)
            self.mirror_view.cb_telegram.setChecked(bool(self.cb_mirror_telegram_notify.get()))
            self.mirror_view.append_log("🪞 Scheduler Mirror đã sẵn sàng (cổng :10 giờ chẵn).")
            self.stack.addWidget(self.mirror_view)
        return self.mirror_view

    def _ensure_moss_view(self) -> MossTabQt:
        if self.moss_view is None:
            self.moss_view = MossTabQt(
                controllers=self.controllers,
                on_trigger_moss=self.trigger_moss_merchant,
                on_stop_moss=self.stop_all_moss,
                on_toggle_participant=lambda s, en: self.toggle_event_participant("moss", s, en),
                on_save_schedule=lambda opts: self.save_event_schedule("moss", opts),
                on_apply_moss_batch=self.apply_moss_batch_settings,
                on_clean_moss=self.clean_all_moss_inventories,
                on_sell_moss=self.sell_all_moss_inventories,
                on_analyze_moss=self.analyze_all_moss_inventories,
                on_open_junk_dialog=self.open_junk_disposal_dialog,
                on_moss_slot_category=self.on_moss_slot_category_changed,
                on_moss_slot_delay=self.on_moss_slot_delay_changed,
                on_toggle_moss_slot=self.toggle_moss_slot_auto,
                on_moss_row_action=self.on_moss_row_action,
                on_moss_batch_tool=self.on_moss_batch_tool,
            )
            self.moss_view.apply_schedule_config(self._moss_sched_cfg_init)
            self.moss_view.apply_moss_flags_from_controllers()
            self.moss_view.append_log("🎲 Scheduler Moss đã sẵn sàng (00:15 / 06:15 / 12:15 / 18:15).")
            self.stack.addWidget(self.moss_view)
        return self.moss_view

    def _ensure_quest_view(self) -> QuestTabQt:
        if self.quest_view is None:
            self.quest_view = QuestTabQt(
                controllers=self.controllers,
                quest_config=self.quest_config,
                on_scan_all=self.scan_all_quests,
                on_start_selected=self.start_selected_quests,
                on_stop_all=self.stop_all_quests,
                on_toggle_slot=self.toggle_quest_slot,
                on_scan_slot=self.scan_quest_slot,
                on_config_changed=self._on_quest_config_changed,
                on_grab_current_coord=self.grab_current_quest_coord,
            )
            self.quest_view.append_log("⚔️ Auto Nhiệm Vụ Cấp 2 & Cấp 3 đã sẵn sàng. Nhấn 'Quét Trạng Thái NV' để đọc dữ liệu RAM.")
            self.stack.addWidget(self.quest_view)
        return self.quest_view

    def _ensure_logs_view(self) -> LogsTabQt:
        if self.logs_view is None:
            self.logs_view = LogsTabQt(on_clear=lambda: self.log_message("Nhật ký đã được làm sạch.", "INFO"))
            self.stack.addWidget(self.logs_view)
        return self.logs_view

    def _warmup_qt_tabs_step(self):
        """Khởi tạo trước từng tab Qt6 siêu nhẹ (~10-30ms mỗi bước) để lần chuyển tab đầu tiên 0 giật."""
        if not self.running or self._is_closing:
            return
        if self.logs_view is None:
            self._ensure_logs_view()
            self.after(120, self._warmup_qt_tabs_step)
        elif self.mirror_view is None:
            self._ensure_mirror_view()
            self.after(120, self._warmup_qt_tabs_step)
        elif self.moss_view is None:
            self._ensure_moss_view()
            self.after(120, self._warmup_qt_tabs_step)
        elif self.quest_view is None:
            self._ensure_quest_view()
            self.after(120, self._warmup_qt_tabs_step)
        elif self.profiles_view is None:
            self._ensure_profiles_view()

    def update_modules_visibility(self):
        """Ẩn/hiện các tab tính năng theo module bản quyền đã kích hoạt (train / mirror / moss)."""
        if not hasattr(self, "nav_buttons"):
            return
        has_train = license_client.has_license_module("train") if license_client else True
        has_moss = license_client.has_license_module("moss") if license_client else True
        has_mirror = license_client.has_license_module("mirror") if license_client else True

        for tid, visible in (
            ("train", has_train),
            ("profiles", has_train),
            ("mirror", has_mirror),
            ("moss", has_moss),
            ("quest", has_train),
            ("logs", True),
        ):
            btn = self.nav_buttons.get(tid)
            if btn is not None:
                btn.setVisible(bool(visible))

        cur = getattr(self, "active_tab_name", "train")
        allowed = {
            "train": has_train,
            "profiles": has_train,
            "mirror": has_mirror,
            "moss": has_moss,
            "quest": has_train,
            "logs": True,
        }
        if not allowed.get(cur, True):
            for fallback in ("train", "mirror", "moss", "quest", "logs"):
                if allowed.get(fallback, False):
                    self.switch_tab(fallback)
                    break

    def switch_tab(self, tab_id: str):
        if tab_id == "autologin":
            return
        if tab_id == "events":
            tab_id = "moss"
        if license_client:
            if tab_id in ("train", "profiles", "quest") and not license_client.has_license_module("train"):
                return
            if tab_id == "mirror" and not license_client.has_license_module("mirror"):
                return
            if tab_id == "moss" and not license_client.has_license_module("moss"):
                return
        view_map = {
            "train": lambda: self.train_view,
            "profiles": self._ensure_profiles_view,
            "mirror": self._ensure_mirror_view,
            "moss": self._ensure_moss_view,
            "quest": self._ensure_quest_view,
            "logs": self._ensure_logs_view,
        }
        getter = view_map.get(tab_id)
        if not getter:
            return
        widget = getter()
        self.stack.setCurrentWidget(widget)
        self.active_tab_name = tab_id
        self.active_tab = tab_id

        # Chuyển trạng thái nút tab bằng :checked native (0 unpolish/polish QSS!)
        for tid, btn in self.nav_buttons.items():
            want = tid == tab_id
            if btn.isChecked() != want:
                btn.setChecked(want)

        now = time.time()
        if tab_id == "train":
            dirty = self.state_mgr.get_dirty_slots()
            if dirty:
                self.train_view.update_slots_data(dirty)
        elif tab_id == "mirror" and self.mirror_view:
            m = self.state_mgr.events.get("mirror", {})
            self.mirror_view.update_countdown(m.get("countdown_sec", 0), m.get("is_gate_open", False), m.get("next_time_str"))
            self.mirror_view.refresh_rows()
            if now - self._last_mirror_tab_ticket_scan >= 25.0:
                self._last_mirror_tab_ticket_scan = now
                self.trigger_mirror_ticket_scan()
        elif tab_id == "moss" and self.moss_view:
            ms = self.state_mgr.events.get("moss", {})
            self.moss_view.update_countdown(ms.get("countdown_sec", 0), ms.get("is_open", False), ms.get("next_time_str"))
            self.moss_view.refresh_moss_rows()
        elif tab_id == "quest" and self.quest_view:
            self.quest_view.update_from_state_snapshots(self.state_mgr.slots)
        elif tab_id == "logs" and self.logs_view:
            new_logs = self.state_mgr.pop_pending_logs()
            if new_logs:
                self.logs_view.append_batched_logs(new_logs)

    # ==========================================================================
    # UI HEARTBEAT (ONLY VISIBLE TAB UPDATED — 0 OVERHEAD)
    # ==========================================================================
    def _ui_heartbeat(self):
        if not self.running or self._is_closing:
            return
        try:
            now = time.time()
            try:
                PartyManager.get_instance().tick(self.controllers)
            except Exception:
                pass

            if self.active_tab_name == "train":
                dirty = self.state_mgr.get_dirty_slots()
                if dirty:
                    self.train_view.update_slots_data(dirty)
            elif self.active_tab_name == "logs" and self.logs_view:
                new_logs = self.state_mgr.pop_pending_logs()
                if new_logs:
                    self.logs_view.append_batched_logs(new_logs)
            elif self.active_tab_name == "mirror" and self.mirror_view:
                if now - getattr(self, "_last_mirror_ref_ts", 0.0) >= 1.0:
                    self._last_mirror_ref_ts = now
                    self.mirror_view.refresh_rows()
            elif self.active_tab_name == "moss" and self.moss_view:
                if now - getattr(self, "_last_moss_ref_ts", 0.0) >= 1.0:
                    self._last_moss_ref_ts = now
                    self.moss_view.refresh_moss_rows()
            elif self.active_tab_name == "quest" and self.quest_view:
                if now - getattr(self, "_last_quest_ref_ts", 0.0) >= 0.8:
                    self._last_quest_ref_ts = now
                    self.quest_view.update_from_state_snapshots(self.state_mgr.slots)

            if self.state_mgr.is_events_dirty():
                ev = self.state_mgr.events
                if self.active_tab_name == "mirror" and self.mirror_view:
                    m = ev.get("mirror", {})
                    self.mirror_view.update_countdown(m.get("countdown_sec", 0), m.get("is_gate_open", False), m.get("next_time_str"))
                elif self.active_tab_name == "moss" and self.moss_view:
                    ms = ev.get("moss", {})
                    self.moss_view.update_countdown(ms.get("countdown_sec", 0), ms.get("is_open", False), ms.get("next_time_str"))

            if getattr(self.state_mgr, "global_dirty", False):
                self.state_mgr.global_dirty = False
                games = self.state_mgr.get_detected_games()
                self.detected_games = games
                proc_options = ["--"] + list(games.values())
                if proc_options != self._last_proc_options_cache:
                    self._last_proc_options_cache = proc_options
                    self.train_view.update_process_options_all(proc_options)
                self._update_header_stats_internal()
        except Exception:
            pass

    def _update_header_stats_internal(self):
        num_games = len(self.detected_games)
        num_conn = sum(1 for c in self.controllers if c.assigned_pid and c.assigned_pid in self.detected_games)
        num_auto = sum(1 for c in self.controllers if c.worker and c.worker.running)
        lic_str = license_client.get_license_display_text() if license_client else "Free"
        lic_valid = license_client.is_license_valid() if license_client else False
        short_lic = (lic_str[:18] + "…") if len(lic_str) > 19 else lic_str

        self.chip_games.set_value(str(num_games), "info" if num_games else "neutral")
        self.chip_conn.set_value(str(num_conn), "ok" if num_conn else "neutral")
        self.chip_auto.set_value(str(num_auto), "warn" if num_auto else "neutral")
        lic_tone = "ok" if lic_valid else ("danger" if "🔒" in lic_str else "neutral")
        self.chip_license.set_value(short_lic, lic_tone)
        self.footer_stats_lbl.setText(
            f"Total: {len(self.controllers)} slots · Connected: {num_conn} · Running: {num_auto} · Games: {num_games}"
        )

    def update_header_stats(self):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self._update_header_stats_internal)
            return
        self._update_header_stats_internal()

    # ==========================================================================
    # AUTO TRAIN ACTIONS (1..50 SLOTS)
    # ==========================================================================
    def _require_valid_license(self) -> bool:
        if license_client and not license_client.is_license_valid():
            self.apply_license_lock_state(force=True)
            self.open_license_dialog()
            return False
        return True

    def on_slot_auto_toggle(self, slot_idx: int):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        ctrl = self.controllers[slot_idx - 1]
        if ctrl.worker and ctrl.worker.running:
            ctrl.stop_auto(reason="Người dùng nhấn nút DỪNG trên giao diện")
        else:
            if not self._require_valid_license():
                return
            ctrl.start_auto()

    def toggle_all_auto(self, start_all: bool):
        if start_all:
            if not self._require_valid_license():
                return
            self.log_message("▶ Đang bật Auto cho tất cả các slot có game...", "INFO")
            for ctrl in self.controllers:
                if ctrl.assigned_pid and not (ctrl.worker and ctrl.worker.running):
                    ctrl.start_auto()
        else:
            self.log_message("⏹ Đang dừng Auto cho tất cả các slot...", "INFO")
            for ctrl in self.controllers:
                if ctrl.worker and ctrl.worker.running:
                    ctrl.stop_auto(reason="Dừng hàng loạt")

    def refresh_games(self):
        self.log_message("🔄 Đang quét lại danh sách tiến trình MEGAMU...", "INFO")
        self.engine_sync.trigger_scan_now()

    def connect_all(self):
        if not self._require_valid_license():
            return
        self.log_message("🔗 Đang kiểm tra và kết nối lại các Slot...", "INFO")
        threading.Thread(target=self._worker_connect_all, daemon=True, name="ConnectAllQt").start()

    def _worker_connect_all(self):
        try:
            fresh = build_enhanced_detected_games()
            if fresh:
                self.state_mgr.update_detected_games(fresh)
                self.detected_games = fresh
            living_pids = set(self.detected_games.keys())
            connected, reconnected = 0, 0
            for ctrl in list(self.controllers):
                try:
                    if ctrl.assigned_pid and ctrl.assigned_pid not in living_pids:
                        if hasattr(ctrl, "reconnect_game") and ctrl.reconnect_game():
                            reconnected += 1
                    elif ctrl.assigned_pid and ctrl.assigned_pid in living_pids:
                        if not (ctrl.engine and ctrl.engine.is_ready):
                            ctrl.attach_pid(ctrl.assigned_pid)
                        connected += 1
                    elif not ctrl.assigned_pid and getattr(ctrl, "last_known_char_name", None):
                        if hasattr(ctrl, "reconnect_game") and ctrl.reconnect_game():
                            reconnected += 1
                except Exception as e_s:
                    self.log_message(f"[Slot {ctrl.slot_idx:02d}] Lỗi kết nối: {e_s}", "WARNING")
            total = connected + reconnected
            if total > 0:
                self.log_message(f"🔗 Kết nối tất cả: {total} slot sẵn sàng (nối lại {reconnected}).", "SUCCESS")
            else:
                self.log_message("🔗 Không tìm thấy tiến trình MEGAMU nào để kết nối.", "WARNING")
            self.state_mgr.global_dirty = True
            self.update_header_stats()
        except Exception as e:
            self.log_message(f"Lỗi connect_all: {e}", "ERROR")

    def assign_all(self):
        if not self._require_valid_license():
            return
        self.log_message("👥 Đang tự động gán tiến trình MEGAMU vào các Slot trống...", "INFO")
        threading.Thread(target=self._worker_assign_all, daemon=True, name="AssignAllQt").start()

    def _worker_assign_all(self):
        try:
            fresh_games = build_enhanced_detected_games()
            if fresh_games:
                self.state_mgr.update_detected_games(fresh_games)
                games = fresh_games
            else:
                games = self.state_mgr.get_detected_games()
        except Exception:
            games = self.state_mgr.get_detected_games()

        assigned_pids = {c.assigned_pid for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid)}
        available = sorted(p for p in games if p not in assigned_pids)
        if not available:
            self.log_message("Không có tiến trình MEGAMU nào chưa được gán.", "WARNING")
            return

        lic_data = license_client.load_license_data() if license_client else {}
        is_valid = license_client.is_license_valid() if license_client else False
        max_allowed = min(int(lic_data.get("max_slots", 5 if not is_valid else 10)), MAX_SLOTS)

        target_slots = [c for c in self.controllers if not c.assigned_pid or not psutil.pid_exists(c.assigned_pid)]
        target_slots.sort(key=lambda c: c.slot_idx)

        while len(target_slots) < len(available) and len(self.controllers) < max_allowed:
            cur_len = len(self.controllers)
            new_ctrl = self.add_new_slot(silent=True)
            if new_ctrl is not None and len(self.controllers) > cur_len:
                target_slots.append(new_ctrl)
            else:
                break

        count = 0
        for pid in available:
            if not target_slots:
                break
            ctrl = target_slots.pop(0)
            self.state_mgr.ensure_slot(ctrl.slot_idx)
            ctrl.attach_pid(pid)
            title = games.get(pid, "")
            _, t_name, srv_str = parse_slot_game_choice(title)
            if not t_name and character_name_from_window_title:
                t_name = character_name_from_window_title(title)
            if not t_name:
                try:
                    from meg_navigator import ProcessMemoryReader
                    t_name = ProcessMemoryReader.read_character_name(pid) or ""
                except Exception:
                    pass
            if t_name and t_name != "---":
                ctrl.char_name = t_name
                ctrl.last_known_char_name = t_name
            if srv_str:
                ctrl.server_name = srv_str if srv_str.startswith("Sv") else f"Sv{srv_str}"
            self.state_mgr.update_slot_telemetry(
                ctrl.slot_idx,
                assigned_pid=pid,
                char_name=ctrl.char_name,
                server=getattr(ctrl, "server_name", "---"),
                status="Đã kết nối",
            )
            count += 1

        remaining = len(available) - count
        if remaining > 0:
            self.log_message(
                f"Đã gán {count} tài khoản. Còn {remaining} game chưa gán do đạt giới hạn bản quyền ({max_allowed} slot).",
                "WARNING",
            )
        else:
            self.log_message(f"Đã gán thành công toàn bộ {count} tài khoản vào các Slot.", "SUCCESS")

        self.state_mgr.global_dirty = True
        self.update_header_stats()

        def _post_ui():
            proc_opts = ["--"] + list(self.state_mgr.get_detected_games().values())
            self._last_proc_options_cache = proc_opts
            self.train_view.update_process_options_all(proc_opts)
            self.train_view.update_slots_data(self.state_mgr.get_all_slots_data())
            if self.mirror_view:
                self.mirror_view.refresh_rows()
            if self.moss_view:
                self.moss_view.refresh_moss_rows()

        self.after(0, _post_ui)

    def on_slot_pid_selected(self, slot_idx: int, val: str):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        self.state_mgr.ensure_slot(slot_idx)
        ctrl = self.controllers[slot_idx - 1]
        pid, c_name, srv_str = parse_slot_game_choice(val)

        if pid is None:
            ctrl.assigned_pid = None
            ctrl.engine = None
            ctrl.char_name = "---"
            self.state_mgr.update_slot_telemetry(
                slot_idx, assigned_pid=None, status="Chưa kết nối", char_name="---", level="---", coords="--,--"
            )
            self.state_mgr.global_dirty = True
            self.train_view.update_slots_data([self.state_mgr.get_slot(slot_idx)])
            self.log_message(f"[Slot {slot_idx:02d}] Đã hủy gán PID.", "INFO")
            return

        for other_c in self.controllers:
            if other_c.slot_idx != slot_idx and other_c.assigned_pid == pid:
                other_c.assigned_pid = None
                other_c.engine = None
                other_c.char_name = "---"
                self.state_mgr.update_slot_telemetry(
                    other_c.slot_idx, assigned_pid=None, status="Chưa kết nối", char_name="---", level="---", coords="--,--"
                )
                self.train_view.update_slots_data([self.state_mgr.get_slot(other_c.slot_idx)])

        ok = ctrl.attach_pid(pid)
        if not c_name:
            try:
                from meg_navigator import ProcessMemoryReader
                c_name = ProcessMemoryReader.read_character_name(pid) or ""
            except Exception:
                pass
        if c_name and c_name != "---":
            ctrl.char_name = c_name
            ctrl.last_known_char_name = c_name
        if srv_str:
            ctrl.server_name = srv_str if srv_str.startswith("Sv") else f"Sv{srv_str}"

        self.state_mgr.update_slot_telemetry(
            slot_idx=slot_idx,
            assigned_pid=pid,
            char_name=ctrl.char_name,
            server=getattr(ctrl, "server_name", "---"),
            status="Đã kết nối" if ok else "Đang kết nối...",
        )
        self.state_mgr.global_dirty = True
        self.update_header_stats()
        self.train_view.update_slots_data([self.state_mgr.get_slot(slot_idx)])
        self.log_message(f"[Slot {slot_idx:02d}] Đã gán PID {pid} ({ctrl.char_name}).", "SUCCESS")

    def on_slot_profile_selected(self, slot_idx: int, val: str):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        ctrl = self.controllers[slot_idx - 1]
        try:
            digits = "".join(ch for ch in val if ch.isdigit())
            p_idx = int(digits) if digits else 1
            ctrl.profile_index = p_idx
            self.slot_assignments[slot_idx] = p_idx
            ConfigPersistenceManager.save_slot_assignment(slot_idx, p_idx)
            self.state_mgr.update_slot_telemetry(slot_idx, profile=val)
            self.log_message(f"[Slot {slot_idx:02d}] Đã đổi cấu hình sang {val}.", "INFO")
        except Exception:
            pass

    def on_slot_delay_changed(self, slot_idx: int, delay_s: float):
        if 1 <= slot_idx <= len(self.controllers):
            self.controllers[slot_idx - 1].respawn_delay = max(3.0, float(delay_s))

    def on_toggle_slot_point(self, slot_idx: int):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        ctrl = self.controllers[slot_idx - 1]
        new_st = not bool(getattr(ctrl, "auto_add_point", False))
        ctrl.auto_add_point = new_st
        self.state_mgr.update_slot_telemetry(slot_idx, auto_add_point=new_st)
        self.train_view.set_slot_point_state(slot_idx, new_st)
        self.log_message(f"[Slot {slot_idx:02d}] Tự động cộng Point: {'BẬT' if new_st else 'TẮT'}.", "INFO")

    def open_slot_profile_editor(self, slot_idx: int):
        if 1 <= slot_idx <= len(self.controllers):
            p_idx = int(getattr(self.controllers[slot_idx - 1], "profile_index", 1) or 1)
            pv = self._ensure_profiles_view()
            pv.load_profile_into_editor(p_idx)
            self.switch_tab("profiles")

    def _on_profile_saved(self, _profile_idx: int):
        self.train_view.update_profile_options_all(get_default_profile_options())

    def add_new_slot(self, silent: bool = False):
        """Thêm slot mới (hỗ trợ gọi an toàn từ mọi luồng, tôn trọng hạn mức License)."""
        if threading.current_thread() is not threading.main_thread():
            done = threading.Event()
            res = [None]
            def _run():
                try:
                    res[0] = self.add_new_slot(silent=silent)
                finally:
                    done.set()
            self.after(0, _run)
            done.wait(timeout=3.0)
            return res[0]

        lic_data = license_client.load_license_data() if license_client else {}
        is_valid = license_client.is_license_valid() if license_client else False
        max_allowed = int(lic_data.get("max_slots", 5 if not is_valid else 10))
        cur_count = len(self.controllers)
        if cur_count >= max_allowed or cur_count >= MAX_SLOTS:
            msg = (
                f"Chế độ dùng thử chỉ hỗ trợ tối đa {max_allowed} tài khoản!"
                if not is_valid else
                f"Gói bản quyền hiện tại cho phép tối đa {max_allowed} tài khoản."
            )
            self.log_message(msg, "WARNING")
            if not silent:
                QMessageBox.information(self, "Giới Hạn Bản Quyền", msg)
            return None

        new_idx = cur_count + 1
        self.slot_assignments[new_idx] = 1
        try:
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
        except Exception:
            pass

        ctrl = SlotController(new_idx, self, default_profile=1)
        self.controllers.append(ctrl)
        self.state_mgr.ensure_slot(new_idx)
        self.train_view.add_slot_row(new_idx, ctrl)
        if self.mirror_view:
            self.mirror_view.add_slot_row(ctrl)
        if self.moss_view:
            self.moss_view.add_slot_row(ctrl)
        if self.quest_view:
            self.quest_view.add_slot_row(ctrl)

        self.update_header_stats()
        self.log_message(f"➕ Đã thêm Account Slot #{new_idx:02d} (Hiện có {len(self.controllers)} slot).", "SUCCESS")
        return ctrl

    def remove_last_slot(self):
        if len(self.controllers) <= 1:
            QMessageBox.warning(self, "Cảnh Báo", "Cần giữ lại ít nhất 1 tài khoản trong danh sách.")
            return
        last_idx = len(self.controllers)
        ctrl = self.controllers.pop()
        if ctrl.worker and ctrl.worker.running:
            ctrl.stop_auto(reason=f"Xóa Slot #{last_idx:02d}", trigger_by="MANUAL")
        for fn_name in ("stop_moss", "stop_mirror_auto", "stop_mirror_turbo_sniping"):
            if hasattr(ctrl, fn_name):
                try:
                    getattr(ctrl, fn_name)()
                except Exception:
                    pass
        if ctrl.engine:
            try:
                ctrl.engine.detach()
            except Exception:
                pass

        self.slot_assignments.pop(last_idx, None)
        self.state_mgr.remove_slot(last_idx)
        try:
            ConfigPersistenceManager.save_all_slot_assignments(self.slot_assignments)
        except Exception:
            pass

        self.train_view.remove_last_row()
        if self.mirror_view:
            self.mirror_view.remove_last_row()
        if self.moss_view:
            self.moss_view.remove_last_row()
        q_runner = self.quest_runners.pop(last_idx, None)
        if q_runner:
            try:
                q_runner.stop()
            except Exception:
                pass
        if self.quest_view:
            self.quest_view.remove_slot_row(last_idx)
        self.update_header_stats()
        self.log_message(f"➖ Đã xóa Slot #{last_idx:02d} (Còn {len(self.controllers)} slot).", "INFO")

    # ==========================================================================
    # SHARED UTILITIES: JEWELS, ARRANGE, CLOSE, DEVIL, POINT, PARTY, TELEGRAM
    # ==========================================================================
    def stack_all_jewels(self):
        if getattr(self, "_stack_all_in_progress", False):
            self.log_message("⏳ Đang gom ngọc, vui lòng đợi...", "WARNING")
            return
        self._stack_all_in_progress = True
        def _w():
            try:
                active = [c for c in self.controllers if c.assigned_pid and psutil.pid_exists(c.assigned_pid)]
                if not active:
                    self.log_message("⚠️ Không có slot nào kết nối để gom ngọc.", "WARNING")
                    return
                self.log_message(f"💎 Bắt đầu gom ngọc cho {len(active)} slot...", "INFO")
                for c in active:
                    try:
                        c.auto_stack_jewels()
                    except Exception as e:
                        self.log_message(f"[Slot {c.slot_idx:02d}] Lỗi gom ngọc: {e}", "WARNING")
                self.log_message("✅ Hoàn tất gom ngọc.", "SUCCESS")
            finally:
                self._stack_all_in_progress = False
        threading.Thread(target=_w, daemon=True).start()

    def arrange_windows_by_preset(self, preset: str = "3x2"):
        cfg = ConfigPersistenceManager.load_window_arrangement_config()
        res = MEGAMUWindowManager.arrange_windows(
            layout=preset or "auto",
            custom_cols=cfg.get("custom_cols", 2),
            custom_rows=cfg.get("custom_rows", 2),
            monitor_idx=cfg.get("monitor_idx", 0),
            margin=cfg.get("margin", 0),
            controllers=self.controllers,
        )
        msg = res.get("msg", "")
        self.log_message(f"📐 {msg}" if res.get("ok") else f"⚠️ {msg}", "SUCCESS" if res.get("ok") else "WARNING")

    def close_all_games(self):
        ans = QMessageBox.question(self, "Xác nhận", "Bạn có chắc chắn muốn đóng toàn bộ các cửa sổ game MEGAMU?")
        if ans != QMessageBox.Yes:
            return
        closed = 0
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"] and p.info["name"].lower() == "megamu.exe":
                    p.kill()
                    closed += 1
            except Exception:
                pass
        self.log_message(f"Đã đóng {closed} tiến trình MEGAMU.exe.", "INFO")
        self.engine_sync.trigger_scan_now()

    def trigger_devil_all(self):
        cnt = 0
        for c in self.controllers:
            if c.assigned_pid and psutil.pid_exists(c.assigned_pid) and hasattr(c, "enter_devil_square"):
                cnt += 1
                threading.Thread(target=c.enter_devil_square, daemon=True).start()
        self.log_message(f"🔥 Đã gửi lệnh vào Devil Square cho {cnt} slot.", "INFO" if cnt else "WARNING")

    def open_devil_global_config_dialog(self):
        dlg = DevilConfigDialogQt(
            ConfigPersistenceManager,
            on_trigger_all=self.trigger_devil_all,
            on_saved=lambda: self.log_message("Đã lưu cấu hình Devil Square.", "SUCCESS"),
            parent=self,
        )
        dlg.exec()

    def trigger_add_points_all(self):
        def _w():
            cnt = 0
            for c in self.controllers:
                if c.assigned_pid and psutil.pid_exists(c.assigned_pid) and hasattr(c, "auto_distribute_points"):
                    try:
                        c.auto_distribute_points()
                        cnt += 1
                    except Exception:
                        pass
            self.log_message(f"⭐ Đã kích hoạt cộng Point cho {cnt} slot.", "SUCCESS" if cnt else "WARNING")
        threading.Thread(target=_w, daemon=True).start()

    def open_point_global_config_dialog(self):
        dlg = PointConfigDialogQt(self.controllers, ConfigPersistenceManager, on_trigger_all=self.trigger_add_points_all, parent=self)
        dlg.exec()
        for c in self.controllers:
            self.train_view.set_slot_point_state(c.slot_idx, bool(getattr(c, "auto_add_point", False)))

    def open_party_config_dialog(self):
        dlg = PartyConfigDialogQt(
            PartyManager.get_instance(),
            self.controllers,
            on_saved=lambda: self.log_message("Đã lưu cấu hình Auto PT.", "SUCCESS"),
            parent=self,
        )
        dlg.exec()

    def open_pk_report_config_dialog(self):
        self.pk_report_config = self.pk_report_config_mgr.load()

        def _on_save(new_cfg: Dict[str, Any]):
            self.pk_report_config = dict(new_cfg)
            self.pk_report_config_mgr.save(self.pk_report_config)
            st_lbl = "BẬT" if self.pk_report_config.get("enabled") else "TẮT"
            town_lbl = str(self.pk_report_config.get("town", "auto")).upper()
            self.log_message(f"🚨 Đã lưu cấu hình Auto Report PK: {st_lbl} · Thành: {town_lbl}.", "SUCCESS")

        def _on_test_now(run_cfg: Dict[str, Any]):
            self.run_manual_pk_report_all(run_cfg)

        dlg = PkReportConfigDialogQt(
            self.pk_report_config,
            on_save=_on_save,
            on_test_now=_on_test_now,
            parent=self,
        )
        dlg.exec()

    def run_manual_pk_report_all(self, cfg: Optional[Dict[str, Any]] = None):
        """Chạy thử quy trình về thành tìm Lính Canh Report cho các slot đang kết nối."""
        use_cfg = dict(cfg or self.pk_report_config_mgr.load())
        targets = [c for c in self.controllers if getattr(c, "engine", None) and getattr(c.engine, "is_ready", False)]
        if not targets:
            self.log_message("⚠️ Chưa có Slot nào đang kết nối Direct Engine để chạy Report.", "WARN")
            return
        self.log_message(f"🚨 Khởi chạy tìm Lính Canh Report thủ công cho {len(targets)} slot đang kết nối...", "INFO")

        def _run_slot(ctrl):
            slot_tag = f"[Slot {ctrl.slot_idx}]"
            execute_pk_report(
                ctrl.engine,
                cfg=use_cfg,
                killer_name="",
                force=True,
                log_cb=lambda m, lv="INFO": self.log_message(f"{slot_tag} {m}", lv),
            )

        for ctrl in targets:
            threading.Thread(target=_run_slot, args=(ctrl,), name=f"PkReportSlot-{ctrl.slot_idx}", daemon=True).start()

    def open_telegram_settings_dialog(self):
        dlg = TelegramConfigDialogQt(self.telegram_config, send_raw_fn=send_telegram_raw, parent=self)
        dlg.exec()
        if self.telegram_config:
            en = bool(getattr(self.telegram_config, "enabled", False))
            self.cb_mirror_telegram_notify.set(en)
            if self.mirror_view:
                self.mirror_view.cb_telegram.setChecked(en)

    # ==========================================================================
    # MIRROR & MOSS ACTIONS
    # ==========================================================================
    def _sync_event_checkbox_proxies_from_view(self):
        if self.mirror_view:
            self.cb_mirror_auto_schedule.set(self.mirror_view.cb_auto.isChecked())
            self.cb_mirror_auto_lifecycle.set(self.mirror_view.cb_lifecycle.isChecked())
            self.cb_mirror_auto_gremory.set(self.mirror_view.cb_gremory.isChecked())
            self.cb_mirror_auto_prep_before.set(self.mirror_view.cb_prep.isChecked())
            self.cb_mirror_telegram_notify.set(self.mirror_view.cb_telegram.isChecked())
        if self.moss_view:
            self.cb_moss_auto_schedule.set(self.moss_view.cb_auto.isChecked())
            self.cb_moss_auto_move_before.set(self.moss_view.cb_move.isChecked())
            self.batch_moss_clean_cb.set(self.moss_view.cb_auto_clean.isChecked())
            self.cb_clean_equipment_trash.set(self.moss_view.cb_clean_equip.isChecked())
            if hasattr(self.moss_view, "cb_sell_exc"):
                self.cb_sell_excellent.set(self.moss_view.cb_sell_exc.isChecked())

    def get_mirror_snipe_delay(self) -> int:
        return self.mirror_view.get_snipe_delay() if self.mirror_view else int(self.mirror_snipe_delay_ms)

    def get_mirror_zero_confirm(self) -> bool:
        return self.mirror_view.get_zero_confirm() if self.mirror_view else bool(self.mirror_zero_confirm)

    def get_mirror_snipe_dur(self) -> float:
        return self.mirror_view.get_snipe_dur() if self.mirror_view else float(self.mirror_snipe_dur_s)

    def get_mirror_prefire_sec(self) -> float:
        return self.mirror_view.get_prefire_sec() if self.mirror_view else float(self.mirror_prefire_sec)

    def get_mirror_stagger_ms(self) -> int:
        if self.mirror_view and hasattr(self.mirror_view, "get_stagger_ms"):
            return self.mirror_view.get_stagger_ms()
        try:
            raw = str(self.mirror_stagger_ms_entry.get()).strip().lower()
            if raw in ("auto", "-1"):
                return -1
            return max(-1, min(100, int(raw)))
        except Exception:
            return -1

    def _ensure_mirror_auto_schedule_enabled_from_manual(self):
        """Khi bấm cướp cổng bằng tay, tự động bật lịch hẹn cướp cổng và khóa lượt cướp duy nhất của đợt hiện tại."""
        try:
            if hasattr(self, "_get_current_or_upcoming_mirror_event_key"):
                ev_key = self._get_current_or_upcoming_mirror_event_key()
                if ev_key:
                    self._last_mirror_event_snipe_key = ev_key
                    self._last_mirror_prefire_key = ev_key.replace("_event", "_prefire")
            if self.cb_mirror_auto_schedule.get() != 1:
                self.cb_mirror_auto_schedule.select()
                if self.mirror_view:
                    self.after(0, lambda: self.mirror_view.cb_auto.setChecked(True))
                cfg = self.get_mirror_schedule_config()
                ConfigPersistenceManager.save_mirror_schedule_config(
                    auto_schedule=True,
                    auto_prep_before=cfg.get("auto_prep_before", True),
                    prefire_sec=cfg.get("prefire_sec", 5.0),
                    auto_lifecycle=cfg.get("auto_lifecycle", True),
                    auto_gremory=cfg.get("auto_gremory", True),
                    interval_ms=cfg.get("interval_ms", 10),
                    max_duration_s=cfg.get("max_duration_s", 15.0),
                    zero_confirm=cfg.get("zero_confirm", True),
                    selected_slots=cfg.get("selected_slots", []),
                )
                self.append_mirror_log("⚡ [Tự động cướp cổng] Đã tự động BẬT lịch hẹn cướp cổng (1 lần duy nhất trước 5s cho các đợt kế tiếp)!")
        except Exception:
            pass

    def refresh_mirror_slot_ticket_display(self, slot_idx: int, t_info: Optional[Dict[str, Any]] = None):
        if self.mirror_view:
            self.after(0, lambda s=slot_idx, d=t_info: self.mirror_view.update_slot_ticket_info(s, d))

    def refresh_all_mirror_tickets_display(self):
        self.trigger_mirror_ticket_scan()

    def move_all_to_moss_elbeland(self):
        self.on_moss_batch_tool("move_all")

    def get_mirror_schedule_config(self) -> Dict[str, Any]:
        self._sync_event_checkbox_proxies_from_view()
        return {
            "auto_schedule": bool(self.cb_mirror_auto_schedule.get()),
            "auto_prep_before": bool(self.cb_mirror_auto_prep_before.get()),
            "auto_lifecycle": bool(self.cb_mirror_auto_lifecycle.get()),
            "auto_gremory": bool(self.cb_mirror_auto_gremory.get()),
            "zero_confirm": self.get_mirror_zero_confirm(),
            "prefire_sec": self.get_mirror_prefire_sec(),
            "interval_ms": self.get_mirror_snipe_delay(),
            "max_duration_s": self.get_mirror_snipe_dur(),
            "selected_slots": [c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)],
        }

    def trigger_mirror_snipe(self):
        self._sync_event_checkbox_proxies_from_view()
        if hasattr(self, "start_all_mirror_turbo_sniping"):
            self.start_all_mirror_turbo_sniping(from_scheduler=False)

    def enter_all_mirror(self):
        zc = self.get_mirror_zero_confirm()
        selected = [c for c in self.controllers if getattr(c, "mirror_enabled", True) and c.assigned_pid and psutil.pid_exists(c.assigned_pid)]
        def _enter(ctrl):
            try:
                eng = ctrl.engine or (MegDirectEngine.get_engine(ctrl.assigned_pid) if MegDirectEngine else None)
                if eng and hasattr(eng, "set_mirror_zero_confirm"):
                    eng.set_mirror_zero_confirm(zc)
            except Exception:
                pass
            ctrl.enter_mirror()
        for c in selected:
            threading.Thread(target=_enter, args=(c,), daemon=True).start()
        self.append_mirror_log(f"🚪 Đã gửi lệnh vào cửa Double Goer đồng loạt cho {len(selected)} tài khoản!")

    def trigger_all_mirror_lifecycle(self):
        self._sync_event_checkbox_proxies_from_view()
        selected = [c for c in self.controllers if getattr(c, "mirror_enabled", True) and c.assigned_pid and psutil.pid_exists(c.assigned_pid)]
        for c in selected:
            threading.Thread(target=c.run_mirror_in_dungeon_lifecycle, kwargs={"force": True}, daemon=True).start()
        self.append_mirror_log(
            f"⚔️ Đang kích hoạt chu trình ra bãi Mirror (Đợi Safe Zone -> Phút :16 ra bãi -> Helper -> Săn Box) cho {len(selected)} tài khoản..."
            if selected else "⚠️ Chưa có tài khoản Mirror nào được tích chọn & kết nối!"
        )

    def claim_all_gremory_case_items(self):
        def _w():
            self.append_mirror_log("🎁 [Gremory Case] Bắt đầu lôi đồ từ Thùng K cho các tài khoản đã chọn...")
            total = 0
            total_rem = 0
            checked = 0
            for c in self.controllers:
                if getattr(c, "mirror_enabled", True) and c.assigned_pid and psutil.pid_exists(c.assigned_pid):
                    checked += 1
                    try:
                        eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                        if eng:
                            res = eng.claim_gremory_case_items() or {}
                            cnt = int(res.get("claimed", 0) or 0)
                            rem = int(res.get("remaining", 0) or 0)
                            items_list = res.get("items", []) or []
                            total += cnt
                            total_rem += rem
                            if cnt > 0:
                                names = [
                                    f"{it.get('name', 'Item')}+{it.get('level', 0)}" if it.get('level', 0) > 0 else f"{it.get('name', 'Item')}"
                                    for it in items_list[:5]
                                ]
                                desc = ", ".join(names) + (f" ... (+{len(items_list) - 5} món)" if len(items_list) > 5 else "")
                                rem_tag = f" (còn {rem} món - hòm đầy)" if rem > 0 else ""
                                self.append_mirror_log(
                                    f"[Slot {c.slot_idx:02d} - {c.char_name}] 🏆 Đã lôi {cnt} món từ Thùng K ({desc}){rem_tag}!"
                                )
                            elif rem > 0:
                                self.append_mirror_log(
                                    f"[Slot {c.slot_idx:02d} - {c.char_name}] ⚠️ Thùng K còn {rem} món nhưng không lôi được (hòm đồ chính đầy)."
                                )
                            elif res.get("ok"):
                                self.append_mirror_log(
                                    f"[Slot {c.slot_idx:02d} - {c.char_name}] ℹ️ Thùng K sạch đồ (không có quà/đồ tồn)."
                                )
                            else:
                                err_r = res.get("error") or res.get("reason") or "không rõ"
                                self.append_mirror_log(
                                    f"[Slot {c.slot_idx:02d} - {c.char_name}] ⚠️ Không lôi được đồ Thùng K: {err_r}"
                                )
                    except Exception as e:
                        self.append_mirror_log(f"[Slot {c.slot_idx:02d} - {c.char_name}] ⚠️ Lỗi lôi đồ Thùng K: {e}")
            if checked == 0:
                self.append_mirror_log("⚠️ [Gremory Case] Không có tài khoản nào được tích 'Đi' và đang kết nối Game.")
            else:
                rem_msg = f" | Còn tồn {total_rem} món (hòm đầy)." if total_rem > 0 else "."
                self.append_mirror_log(f"🏁 [Gremory Case] Hoàn tất lôi đồ Thùng K cho {checked} slot: tổng {total} món{rem_msg}")
        threading.Thread(target=_w, daemon=True).start()

    def move_all_to_event_map(self):
        selected = [c for c in self.controllers if getattr(c, "mirror_enabled", True) and c.assigned_pid and psutil.pid_exists(c.assigned_pid)]
        for c in selected:
            threading.Thread(target=c.move_to_event_map, daemon=True).start()
        self.append_mirror_log(f"🚶 Đang chuyển Event Map (Lugard) cho {len(selected)} tài khoản." if selected else "⚠️ Không có tài khoản kết nối.")

    def trigger_mirror_ticket_scan(self, slot_idx: Optional[int] = None):
        def _scan():
            targets = [self.controllers[slot_idx - 1]] if (slot_idx and 1 <= slot_idx <= len(self.controllers)) else list(self.controllers)
            for c in targets:
                try:
                    if c.assigned_pid and psutil.pid_exists(c.assigned_pid):
                        inf = c.check_mirror_ticket()
                        c.cached_mirror_ticket_info = inf
                        if self.mirror_view:
                            self.after(0, lambda s=c.slot_idx, d=inf: self.mirror_view.update_slot_ticket_info(s, d))
                        time.sleep(0.04)
                except Exception:
                    pass
        threading.Thread(target=_scan, daemon=True).start()

    def check_all_mirror_tickets(self):
        def _chk():
            self.append_mirror_log("🔍 Đang kiểm tra vé Mirror trên các tài khoản đã chọn...")
            total, has_t = 0, 0
            for c in self.controllers:
                if not getattr(c, "mirror_enabled", True):
                    continue
                if c.assigned_pid and psutil.pid_exists(c.assigned_pid):
                    total += 1
                    inf = c.check_mirror_ticket()
                    c.cached_mirror_ticket_info = inf
                    if self.mirror_view:
                        self.after(0, lambda s=c.slot_idx, d=inf: self.mirror_view.update_slot_ticket_info(s, d))
                    if inf.get("hasTicket"):
                        has_t += 1
                        self.append_mirror_log(f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] 🎟️ Có {inf.get('count')} vé")
                    elif inf.get("hasOnlySign"):
                        self.append_mirror_log(f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] 🧩 Chỉ có mảnh Sign")
                    else:
                        self.append_mirror_log(f"  -> [Slot {c.slot_idx:02d} - {c.char_name}] ❌ 0 vé")
                    time.sleep(0.05)
            self.append_mirror_log(f"📊 Kết quả kiểm tra: {has_t}/{total} tài khoản có vé.")
        threading.Thread(target=_chk, daemon=True).start()

    def _on_events_telegram_toggle(self, enabled: bool):
        self.cb_mirror_telegram_notify.set(bool(enabled))
        if self.telegram_config:
            self.telegram_config.enabled = bool(enabled)
            if hasattr(self.telegram_config, "save"):
                try:
                    self.telegram_config.save()
                except Exception:
                    pass

    def _iter_selected_moss(self):
        for c in self.controllers:
            if getattr(c, "moss_enabled", True) and c.assigned_pid and psutil.pid_exists(c.assigned_pid):
                yield c

    def trigger_moss_merchant(self):
        self._sync_event_checkbox_proxies_from_view()
        if hasattr(self, "start_all_moss_auto"):
            self.start_all_moss_auto()
        else:
            for c in self._iter_selected_moss():
                c.start_moss()

    def stop_all_moss(self):
        if hasattr(self, "stop_all_moss_auto"):
            self.stop_all_moss_auto()
            return
        for c in self.controllers:
            if hasattr(c, "stop_moss"):
                c.stop_moss()
        self.append_moss_log("⏹️ Đã dừng Auto Moss toàn bộ tài khoản.")

    def apply_moss_batch_settings(self, opts: Dict[str, Any]):
        flags_only = bool(opts.get("flags_only", False))
        auto_clean = bool(opts.get("auto_clean", True))
        clean_equip = bool(opts.get("clean_equipment_trash", True))
        sell_exc = bool(opts.get("sell_excellent", True))
        cat = int(opts.get("category", 0) or 0)
        delay = int(opts.get("delay_ms", 1000) or 1000)
        cnt = 0
        for c in self.controllers:
            if not getattr(c, "moss_enabled", True):
                continue
            c.moss_auto_clean = auto_clean
            c.moss_clean_equipment_trash = clean_equip
            c.moss_sell_excellent = sell_exc
            if not flags_only:
                c.moss_category = cat
                c.moss_delay_ms = delay
            try:
                ConfigPersistenceManager.save_moss_config(
                    c.slot_idx, int(c.moss_category), int(c.moss_delay_ms),
                    int(getattr(c, "moss_max_rolls", 0) or 0), auto_clean, clean_equip, sell_exc
                )
            except Exception:
                pass
            cnt += 1
        exc_lbl = " · Bán Exce (trừ Rồng): BẬT" if sell_exc else " · Bán Exce: TẮT"
        self.append_moss_log(f"⚡ Đã cập nhật cấu hình Moss cho {cnt} slot đã chọn{exc_lbl}.")

    def on_moss_slot_category_changed(self, slot_idx: int, cat_name: str):
        if 1 <= slot_idx <= len(self.controllers):
            c = self.controllers[slot_idx - 1]
            c.moss_category = moss_cat_id(cat_name)
            try:
                ConfigPersistenceManager.save_moss_config(
                    c.slot_idx, c.moss_category, c.moss_delay_ms, c.moss_max_rolls,
                    c.moss_auto_clean, c.moss_clean_equipment_trash, getattr(c, "moss_sell_excellent", True)
                )
            except Exception:
                pass

    def on_moss_slot_delay_changed(self, slot_idx: int, delay_ms: int):
        if 1 <= slot_idx <= len(self.controllers):
            c = self.controllers[slot_idx - 1]
            c.moss_delay_ms = max(100, int(delay_ms))
            try:
                ConfigPersistenceManager.save_moss_config(
                    c.slot_idx, c.moss_category, c.moss_delay_ms, c.moss_max_rolls,
                    c.moss_auto_clean, c.moss_clean_equipment_trash, getattr(c, "moss_sell_excellent", True)
                )
            except Exception:
                pass

    def toggle_moss_slot_auto(self, slot_idx: int):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        c = self.controllers[slot_idx - 1]
        if getattr(c, "moss_running", False):
            c.stop_moss()
        else:
            c.start_moss()

    def on_moss_row_action(self, slot_idx: int, action: str):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        c = self.controllers[slot_idx - 1]
        mapping = {
            "roll_once": (getattr(c, "roll_moss_once", None), "🎲 Quay thử 1 lần"),
            "open_npc": (getattr(c, "open_moss_npc", None), "🚪 Mở bảng Moss NPC"),
            "close_npc": (getattr(c, "close_moss_dialog", None), "🚪 Đóng bảng Moss NPC"),
            "sell": (getattr(c, "sell_moss_inventory", None), "💰 Bán Shop (Rhea)"),
            "clean": (lambda: c.clean_moss_inventory(run_in_thread=False), "🗑️ Ném rác tại chỗ"),
            "move": (getattr(c, "move_to_moss_elbeland", None), "🚶 Về NPC Moss"),
            "unlock": (getattr(c, "unlock_and_close_inventory", None), "🔓 Mở khóa thùng đồ"),
        }
        fn, lbl = mapping.get(action, (None, action))
        if fn:
            def _run():
                try:
                    fn()
                    self.append_moss_log(f"[Slot {slot_idx:02d}] {lbl}")
                except Exception as e:
                    self.append_moss_log(f"[Slot {slot_idx:02d}] ❌ {lbl}: {e}")
            threading.Thread(target=_run, daemon=True).start()

    def on_moss_batch_tool(self, action: str):
        selected = list(self._iter_selected_moss())
        if not selected:
            self.append_moss_log("⚠️ Không có tài khoản Moss kết nối!")
            return
        fn_map = {
            "move_all": ("move_to_moss_elbeland", "🚶 Đang chạy về NPC Moss"),
            "open_all": ("open_moss_npc", "🚪 Đang mở bảng Moss NPC"),
            "close_all": ("close_moss_dialog", "🚪 Đang đóng bảng Moss NPC"),
            "unlock_all": ("unlock_and_close_inventory", "🔓 Đang mở khóa thùng đồ"),
        }
        m_name, label = fn_map.get(action, (None, ""))
        if m_name:
            for c in selected:
                fn = getattr(c, m_name, None)
                if fn:
                    threading.Thread(target=fn, daemon=True).start()
            self.append_moss_log(f"{label} cho {len(selected)} tài khoản.")

    def clean_all_moss_inventories(self):
        def _w():
            cnt, tot = 0, 0
            for c in self._iter_selected_moss():
                try:
                    tot += (c.clean_moss_inventory(method="trash", category=-1, run_in_thread=False) or 0)
                    cnt += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {c.slot_idx:02d}] ❌ Lỗi ném rác: {e}")
                time.sleep(0.1)
            self.append_moss_log(f"🗑️ Hoàn tất ném rác cho {cnt} tài khoản: {tot} món." if cnt else "⚠️ Không có tài khoản Moss kết nối.")
        threading.Thread(target=_w, daemon=True).start()

    def sell_all_moss_inventories(self):
        def _w():
            cnt = 0
            for c in self._iter_selected_moss():
                try:
                    c.sell_moss_inventory()
                    cnt += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {c.slot_idx:02d}] ❌ Lỗi bán đồ: {e}")
                time.sleep(0.4)
            self.append_moss_log(f"💰 Đã kích hoạt bán đồ tại NPC Rhea (30, 235) cho {cnt} tài khoản." if cnt else "⚠️ Không có tài khoản Moss kết nối.")
        threading.Thread(target=_w, daemon=True).start()

    def analyze_all_moss_inventories(self):
        def _w():
            cnt = 0
            for c in self._iter_selected_moss():
                try:
                    c.analyze_junk(max_items=10)
                    cnt += 1
                except Exception as e:
                    self.append_moss_log(f"[Slot {c.slot_idx:02d}] ❌ Lỗi phân tích: {e}")
                time.sleep(0.15)
            if cnt == 0:
                self.append_moss_log("⚠️ Không có tài khoản Moss kết nối.")
        threading.Thread(target=_w, daemon=True).start()

    def open_junk_disposal_dialog(self):
        targets = list(self._iter_selected_moss())
        if not targets or not MegDirectEngine:
            self.append_moss_log("⚠️ Không có tài khoản kết nối để dọn rác.")
            return
        self.append_moss_log(f"🔍 Đang đọc hòm đồ của {len(targets)} tài khoản...")
        def _scan():
            reports = []
            for c in targets:
                try:
                    eng = c.engine or MegDirectEngine.get_engine(c.assigned_pid)
                    if eng and not eng.is_ready:
                        eng.attach()
                    if eng:
                        res = eng.analyze_junk_inventory(
                            category=-1,
                            max_junk_level=7 if bool(getattr(c, "moss_sell_excellent", True)) else int(getattr(c, "moss_max_junk_level", 6) or 6),
                            protected_slots=[],
                            ignore_type_heuristics=bool(getattr(c, "moss_ignore_junk_type", False)),
                            clean_equipment_trash=bool(getattr(c, "moss_clean_equipment_trash", True)),
                            allow_excellent=bool(getattr(c, "moss_sell_excellent", True)),
                        )
                        reports.append((c, res))
                except Exception as e:
                    self.append_moss_log(f"[Slot {c.slot_idx:02d}] ❌ Lỗi đọc hòm đồ: {e}")
            self.after(0, lambda: JunkDisposalDialogQt(reports, self._run_junk_disposal, parent=self).exec())
        threading.Thread(target=_scan, daemon=True).start()

    def _run_junk_disposal(self, reports, mode: str):
        def _w():
            total = 0
            for c, _res in reports:
                try:
                    eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if MegDirectEngine else None)
                    if eng and not eng.is_ready:
                        eng.attach()
                    if eng:
                        sell_exc = bool(getattr(c, "moss_sell_excellent", True))
                        out = eng.dispose_junk_items(
                            mode=mode, protected_slots=[], category=-1, include_extended=True,
                            max_junk_level=7 if (mode == "sell" or sell_exc) else int(getattr(c, "moss_max_junk_level", 6) or 6),
                            ignore_type_heuristics=bool(getattr(c, "moss_ignore_junk_type", False)),
                            clean_equipment_trash=bool(getattr(c, "moss_clean_equipment_trash", True)),
                            allow_excellent=sell_exc if mode in ("sell", "auto") else False,
                        )
                        n = int((out or {}).get("cleaned", 0) or 0)
                        total += n
                        self.append_moss_log(
                            f"[Slot {c.slot_idx:02d} - {c.char_name}] 🗑️ Dọn {n} món (vứt {out.get('dropped', 0)}, bán {out.get('sold', 0)})"
                        )
                        time.sleep(0.2)
                except Exception as e:
                    self.append_moss_log(f"[Slot {c.slot_idx:02d}] ❌ Lỗi dọn rác: {e}")
            self.append_moss_log(f"🧹 Hoàn tất: đã dọn tổng cộng {total} món.")
        threading.Thread(target=_w, daemon=True).start()

    def toggle_event_participant(self, event_type: str, slot_idx: int, is_enabled: bool):
        if not (1 <= slot_idx <= len(self.controllers)):
            return
        ctrl = self.controllers[slot_idx - 1]
        if event_type == "mirror":
            ctrl.mirror_enabled = is_enabled
            try:
                cfg = ConfigPersistenceManager.load_mirror_schedule_config()
                ConfigPersistenceManager.save_mirror_schedule_config(
                    auto_schedule=cfg.get("auto_schedule", True),
                    auto_prep_before=cfg.get("auto_prep_before", True),
                    prefire_sec=cfg.get("prefire_sec", 2.0),
                    auto_lifecycle=cfg.get("auto_lifecycle", True),
                    auto_gremory=cfg.get("auto_gremory", True),
                    interval_ms=cfg.get("interval_ms", 10),
                    max_duration_s=cfg.get("max_duration_s", 15.0),
                    zero_confirm=cfg.get("zero_confirm", True),
                    selected_slots=[c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)],
                )
            except Exception:
                pass
        elif event_type == "moss":
            ctrl.moss_enabled = is_enabled
            try:
                cfg = ConfigPersistenceManager.load_moss_schedule_config()
                ConfigPersistenceManager.save_moss_schedule_config(
                    auto_schedule=cfg.get("auto_schedule", True),
                    auto_move_before=cfg.get("auto_move_before", True),
                    selected_slots=[c.slot_idx for c in self.controllers if getattr(c, "moss_enabled", True)],
                )
            except Exception:
                pass

    def save_event_schedule(self, event_type: str, opts: Dict[str, Any]):
        try:
            if event_type == "mirror":
                self._sync_event_checkbox_proxies_from_view()
                self.mirror_snipe_delay_ms = int(opts.get("interval_ms", 10))
                self.mirror_snipe_dur_s = float(opts.get("max_duration_s", 15.0))
                self.mirror_prefire_sec = float(opts.get("prefire_sec", 2.0))
                self.mirror_zero_confirm = bool(opts.get("zero_confirm", True))
                if "stagger_ms" in opts and opts["stagger_ms"] is not None:
                    self.mirror_stagger_ms = int(opts["stagger_ms"])
                    self.mirror_stagger_ms_entry = _FakeEntry(self.mirror_stagger_ms)
                if "clock_offset_ms" in opts and opts["clock_offset_ms"] is not None:
                    self._mirror_clock_offset_ms = max(-8000.0, min(8000.0, float(opts["clock_offset_ms"])))
                    if abs(self._mirror_clock_offset_ms) > 0.5:
                        self._mirror_clock_calibrated = True

                # Đồng bộ tức thì cờ Zero-Confirm xuống các Direct Engine đang attach (tránh chặn popup khi đã tắt)
                zc_val = self.mirror_zero_confirm
                def _push_zc(val=zc_val):
                    for c in list(self.controllers):
                        try:
                            eng = c.engine or (MegDirectEngine.get_engine(c.assigned_pid) if (MegDirectEngine and c.assigned_pid) else None)
                            if eng and eng.is_ready and hasattr(eng, "set_mirror_zero_confirm"):
                                eng.set_mirror_zero_confirm(val)
                        except Exception:
                            pass
                threading.Thread(target=_push_zc, daemon=True).start()

                ConfigPersistenceManager.save_mirror_schedule_config(
                    auto_schedule=bool(opts.get("auto_schedule", True)),
                    auto_prep_before=bool(opts.get("auto_prep_before", True)),
                    prefire_sec=self.mirror_prefire_sec,
                    auto_lifecycle=bool(opts.get("auto_lifecycle", True)),
                    auto_gremory=bool(opts.get("auto_gremory", True)),
                    interval_ms=self.mirror_snipe_delay_ms,
                    max_duration_s=self.mirror_snipe_dur_s,
                    zero_confirm=self.mirror_zero_confirm,
                    stagger_ms=int(getattr(self, "mirror_stagger_ms", -1)),
                    clock_offset_ms=float(getattr(self, "_mirror_clock_offset_ms", 0.0) or 0.0),
                    selected_slots=[c.slot_idx for c in self.controllers if getattr(c, "mirror_enabled", True)],
                )
                if self.mirror_view and hasattr(self.mirror_view, "update_net_telemetry"):
                    self.mirror_view.update_net_telemetry(
                        float(getattr(self, "_mirror_last_rtt_ms", -1.0) or -1.0),
                        float(getattr(self, "_mirror_clock_offset_ms", 0.0) or 0.0),
                    )
                zc_lbl = "BẬT" if self.mirror_zero_confirm else "TẮT"
                st_val = int(getattr(self, "mirror_stagger_ms", -1))
                st_lbl = "Auto" if st_val < 0 else f"{st_val}ms"
                self.append_mirror_log(
                    f"Đã lưu cấu hình Mirror (Bắn trước: {self.mirror_prefire_sec:.1f}s, Chu kỳ: {self.mirror_snipe_delay_ms}ms, Rải pha: {st_lbl}, Offset: {self._mirror_clock_offset_ms:+.0f}ms, Zero-Confirm: {zc_lbl})."
                )
            elif event_type == "moss":
                self._sync_event_checkbox_proxies_from_view()
                ConfigPersistenceManager.save_moss_schedule_config(
                    auto_schedule=bool(opts.get("auto_schedule", True)),
                    auto_move_before=bool(opts.get("auto_move_before", True)),
                    selected_slots=[c.slot_idx for c in self.controllers if getattr(c, "moss_enabled", True)],
                )
        except Exception:
            pass

    # ==========================================================================
    # LICENSE / UPDATE / HELP
    # ==========================================================================
    def _on_license_changed(self):
        """Đồng bộ toàn diện sau khi kích hoạt / đồng bộ / bỏ kích hoạt bản quyền."""
        try:
            import meg_navigator
            if hasattr(meg_navigator, "refresh_navigator_offsets"):
                meg_navigator.refresh_navigator_offsets()
        except Exception:
            pass
        self._last_applied_lock_state = None
        self._license_fail_count = 0
        self._update_header_stats_internal()
        self.update_modules_visibility()
        self.apply_license_lock_state(force=True)

    def _check_initial_license(self):
        if not self.running or self._is_closing:
            return
        if license_client and not license_client.is_license_valid():
            self.apply_license_lock_state(force=True)
            self.open_license_dialog()

    def open_license_dialog(self):
        if not license_client:
            QMessageBox.information(self, "License", "Module license_client chưa khả dụng.")
            return
        if getattr(self, "_license_dialog_open", False):
            return
        self._license_dialog_open = True
        try:
            LicenseDialogQt(license_client, on_activated=self._on_license_changed, parent=self).exec()
        finally:
            self._license_dialog_open = False

    def _verify_license_async(self):
        """Tự động đồng bộ bản quyền + RAM Offsets từ Web Server khi khởi động và định kỳ mỗi 5 phút."""
        if not self.running or self._is_closing or not license_client:
            return
        try:
            lic_data = license_client.load_license_data() if hasattr(license_client, "load_license_data") else {}
            if lic_data and lic_data.get("license_key") and hasattr(license_client, "verify_license"):
                ok, msg, _info = license_client.verify_license()
                if not ok:
                    self.after(0, lambda m=msg: self.log_message(f"🔒 Xác thực bản quyền thất bại: {m}", "WARNING"))
                    self.after(0, lambda: self.apply_license_lock_state(force=True))
                    self.after(0, self.open_license_dialog)
                else:
                    try:
                        import meg_navigator
                        if hasattr(meg_navigator, "refresh_navigator_offsets"):
                            meg_navigator.refresh_navigator_offsets()
                    except Exception:
                        pass
            self.after(0, self._update_header_stats_internal)
            self.after(0, self.update_modules_visibility)
            self.after(0, self.apply_license_lock_state)
        except Exception:
            pass
        if self.running and not self._is_closing:
            self.after(300_000, lambda: threading.Thread(target=self._verify_license_async, daemon=True).start())

    def _periodic_license_monitor(self):
        """Giám sát liên tục sự tồn tại của meg_license_bridge.dll & trạng thái bản quyền mỗi 3 giây."""
        if not self.running or self._is_closing:
            return
        try:
            self.apply_license_lock_state()
            lic_str = license_client.get_license_display_text() if license_client else "Free"
            if getattr(self, "_last_lic_display", None) != lic_str:
                self._last_lic_display = lic_str
                self._update_header_stats_internal()
        except Exception:
            pass
        if self.running and not self._is_closing:
            self.after(3000, self._periodic_license_monitor)

    def _check_update_async(self, manual: bool = False):
        time.sleep(3)
        if not updater:
            return
        try:
            res = updater.check_for_updates(APP_VERSION)
            if isinstance(res, dict) and res.get("has_update"):
                self.update_info = res
                latest = res.get("latest_version", "?")
                def _notify():
                    self.btn_update.setText(f"🔥 Có bản {latest}!")
                    self.btn_update.setProperty("tone", "warn")
                    self.btn_update.style().unpolish(self.btn_update)
                    self.btn_update.style().polish(self.btn_update)
                    self.log_message(f"🔔 Phát hiện phiên bản mới {latest}!", "WARNING")
                self.after(0, _notify)
        except Exception:
            pass

    def open_update_dialog(self, update_info=None):
        info = update_info or self.update_info
        if info and info.get("has_update"):
            dlg = UpdateDialogQt(info, APP_VERSION, self)
            dlg.exec()
        else:
            self.check_for_updates_ui(manual=True)

    def check_for_updates_ui(self, manual: bool = False):
        if not updater:
            if manual:
                QMessageBox.information(self, "Cập nhật", "Module updater chưa khả dụng.")
            return
        if manual and self.update_info and self.update_info.get("has_update"):
            self.open_update_dialog(self.update_info)
            return

        self.btn_update.setEnabled(False)
        self.btn_update.setText("⏳ Kiểm tra...")
        def _w():
            try:
                res = updater.check_for_updates(APP_VERSION)
                has_u = bool(res.get("has_update")) if isinstance(res, dict) else False
                def _done():
                    self.btn_update.setEnabled(True)
                    if has_u:
                        self.update_info = res
                        latest = res.get("latest_version", "?")
                        self.btn_update.setText(f"🔥 Có bản {latest}!")
                        dlg = UpdateDialogQt(res, APP_VERSION, self)
                        dlg.exec()
                    else:
                        self.btn_update.setText("🔄 Cập nhật")
                        if manual:
                            QMessageBox.information(self, "Cập nhật", f"Bạn đang dùng phiên bản mới nhất ({APP_VERSION}).")
                self.after(0, _done)
            except Exception as e:
                self.after(0, lambda: (self.btn_update.setEnabled(True), self.btn_update.setText("🔄 Cập nhật"), manual and QMessageBox.warning(self, "Cập nhật", str(e))))
        threading.Thread(target=_w, daemon=True).start()

    def show_help(self):
        QMessageBox.information(
            self,
            "Hướng dẫn - MEGAMU Dashboard Qt6",
            f"MEGAMU Auto Train Dashboard {APP_VERSION} (Qt6 Native)\n\n"
            "• 01 Auto Train: Quét, gán & điều khiển 1–50 nhân vật mượt 60fps\n"
            "• 02 Config: Thiết lập 10 cấu hình bãi train theo level\n"
            "• 03 Mirror: Cướp cổng Double Goer Turbo + Lôi quà K + Telegram\n"
            "• 04 Moss: Tự động quay Moss Merchant + Dọn rác / Bán Silvia\n"
            "• 05 Logs: Nhật ký hệ thống có bộ lọc tức thì\n\n"
            "Hotline / Zalo: 036.203.1354",
        )

    # ==========================================================================
    # SLOTCONTROLLER COMPATIBILITY CALLBACKS
    # ==========================================================================
    def log_message(self, msg: str, level: str = "INFO"):
        self.state_mgr.append_log(msg, level)

    def append_log(self, msg: str, level: str = "INFO"):
        self.state_mgr.append_log(msg, level)

    def append_mirror_log(self, text: str):
        self.state_mgr.append_log(text, "INFO")
        if self.mirror_view:
            self.after(0, lambda t=text: self.mirror_view.append_log(t))

    def append_moss_log(self, text: str):
        self.state_mgr.append_log(text, "INFO")
        if self.moss_view:
            self.after(0, lambda t=text: self.moss_view.append_log(t))

    def get_moss_cat_name(self, cat_id: int) -> str:
        return moss_cat_name(int(cat_id or 0))

    def update_slot_ui_status(self, slot_idx: int, text: str):
        self.state_mgr.update_slot_telemetry(slot_idx, status=text)

    def update_slot_ui_auto(self, slot_idx: int, is_on: bool):
        self.state_mgr.update_slot_telemetry(slot_idx, is_running=is_on)

    def update_slot_ui_telemetry(self, slot_idx: int, name: str, lvl: str, coords: str, points=None, class_code=None, server=None, resets=None):
        if 1 <= slot_idx <= len(self.controllers):
            c = self.controllers[slot_idx - 1]
            if name and name != "---":
                c.char_name = name
                c.last_known_char_name = name
            if lvl and lvl != "---":
                c.level = lvl
            if coords and coords != "--,--":
                c.coords = coords
            if server and server != "---":
                c.server_name = server
        self.state_mgr.update_slot_telemetry(
            slot_idx=slot_idx, char_name=name, level=lvl, coords=coords,
            points=points, class_code=class_code, server=server, resets=resets,
        )

    def stream_slot_coords(self, slot_idx: int, coords: str, server: str = ""):
        self.state_mgr.update_slot_telemetry(slot_idx, coords=coords, server=server)

    def update_moss_slot_rolls(self, slot_idx: int, count: int):
        if 1 <= slot_idx <= len(self.controllers):
            self.controllers[slot_idx - 1].moss_rolls_count = count
        if self.moss_view and self.active_tab_name == "moss":
            self.after(0, self.moss_view.refresh_moss_rows)

    def update_moss_slot_ui_state(self, slot_idx: int, is_running: bool):
        if 1 <= slot_idx <= len(self.controllers):
            self.controllers[slot_idx - 1].moss_running = is_running
        if self.moss_view and self.active_tab_name == "moss":
            self.after(0, self.moss_view.refresh_moss_rows)

    def update_mirror_slot_ui_state(self, slot_idx: int, is_running: bool):
        if 1 <= slot_idx <= len(self.controllers):
            self.controllers[slot_idx - 1].mirror_sniping = is_running
        if self.mirror_view:
            self.after(0, self.mirror_view.refresh_rows)

    def update_mirror_slot_status(self, slot_idx: int, text: str = "", text_color: str = "#94a3b8", *args, **kwargs):
        if self.mirror_view:
            self.after(0, lambda s=slot_idx, t=text, c=text_color: self.mirror_view.set_slot_status(s, t, c))

    def save_editor_to_file(self, silent: bool = False, target_idx: Optional[int] = None):
        if self.profiles_view:
            if threading.current_thread() is threading.main_thread():
                self.profiles_view.save_current_profile(silent=silent)
            else:
                self.after(0, lambda s=silent: self.profiles_view and self.profiles_view.save_current_profile(silent=s))

    def apply_license_lock_state(self, force: bool = False, *args, **kwargs):
        """Khóa hoặc mở khóa toàn bộ chức năng trên giao diện Qt6 theo trạng thái bản quyền & DLL."""
        if not hasattr(self, "license_lock_banner"):
            return

        if license_client and not license_client.is_native_bridge_active():
            license_client.is_native_bridge_active(force_reload=True)

        is_mandatory_upd = bool(getattr(self, "is_update_mandatory", False))
        is_valid = (not is_mandatory_upd) and (license_client.is_license_valid() if license_client else False)

        if is_valid:
            self._license_fail_count = 0
            want_locked = False
        else:
            self._license_fail_count = getattr(self, "_license_fail_count", 0) + 1
            if not force and not is_mandatory_upd and self._license_fail_count < 3:
                return
            want_locked = True

        prev_locked = getattr(self, "_last_applied_lock_state", None)
        if prev_locked == want_locked and not force:
            return
        self._last_applied_lock_state = want_locked

        if want_locked:
            # Dừng lập tức mọi luồng Auto Train / Moss / Mirror đang chạy
            reason = "Phát hiện bản cập nhật bắt buộc" if is_mandatory_upd else (
                "Thiếu file meg_license_bridge.dll"
                if (license_client and not license_client.is_native_bridge_active())
                else "Bản quyền chưa kích hoạt hoặc đã hết hạn"
            )
            for ctrl in list(self.controllers):
                try:
                    if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                        ctrl.stop_auto(reason=f"Hệ thống khóa: {reason}", trigger_by="SYSTEM")
                    for fn_name in ("stop_moss", "stop_mirror_auto", "stop_mirror_turbo_sniping"):
                        if hasattr(ctrl, fn_name):
                            getattr(ctrl, fn_name)()
                except Exception:
                    pass
            if is_mandatory_upd:
                ver_t = (self.update_info or {}).get("latest_version", "MỚI")
                self._license_banner_lbl.setText(f"⚠️ BẢN CẬP NHẬT BẮT BUỘC {ver_t} — VUI LÒNG CẬP NHẬT ĐỂ TIẾP TỤC")
                self._license_banner_btn.setText("🔄 Cập Nhật")
            elif license_client and not license_client.is_native_bridge_active():
                self._license_banner_lbl.setText("🔒 THIẾU TỆP BẢO MẬT meg_license_bridge.dll — ĐÃ KHÓA CHỨC NĂNG")
                self._license_banner_btn.setText("🔑 Kiểm Tra License")
            else:
                self._license_banner_lbl.setText("🔒 BẢN QUYỀN CHƯA KÍCH HOẠT HOẶC HẾT HẠN — ĐÃ KHÓA CHỨC NĂNG")
                self._license_banner_btn.setText("🔑 Kích hoạt / Đồng Bộ")
            self.license_lock_banner.setVisible(True)
        else:
            self.license_lock_banner.setVisible(False)

        for view in (self.train_view, self.mirror_view, self.moss_view, self.quest_view, self.profiles_view):
            if view is not None:
                view.setEnabled(not want_locked)
        if want_locked:
            self.stop_all_quests(silent=True)

        self.update_modules_visibility()
        self._update_header_stats_internal()

    # ==========================================================================
    # AUTO QUEST (NHIỆM VỤ CẤP 2 / MARLON / CẤP 3) CONTROLLERS
    # ==========================================================================
    def _find_controller_by_slot(self, slot_idx: int):
        for c in self.controllers:
            if int(c.slot_idx) == int(slot_idx):
                return c
        return None

    def _on_quest_config_changed(self, new_cfg: Dict[str, Any]):
        self.quest_config = dict(new_cfg or {})
        self.quest_config_mgr.save(self.quest_config)

    def grab_current_quest_coord(self) -> Optional[Dict[str, Any]]:
        """Lấy tọa độ (X, Y) hiện tại của slot đang chọn (hoặc slot kết nối đầu tiên) cho thanh tọa độ NV."""
        sel = self.quest_view.get_selected_slots() if self.quest_view else []
        candidates = list(sel) + [c.slot_idx for c in self.controllers if c.slot_idx not in sel]
        for s_idx in candidates:
            ctrl = self._find_controller_by_slot(s_idx)
            if not ctrl or not ctrl.assigned_pid or not psutil.pid_exists(ctrl.assigned_pid):
                continue
            eng = ctrl.engine
            if eng and getattr(eng, "is_ready", False):
                info = eng.get_player_info(max_age=0.2) or {}
                x = info.get("x") if info.get("x") is not None else info.get("tileX")
                y = info.get("y") if info.get("y") is not None else info.get("tileY")
                mid = info.get("mapId") if info.get("mapId") is not None else info.get("map_id", -1)
                if x is not None and y is not None:
                    return {"ok": True, "slot": s_idx, "map_id": int(mid), "x": int(x), "y": int(y)}
        return {"ok": False}

    def _on_quest_log(self, msg: str, level: str = "INFO"):
        def _ui():
            if self.quest_view:
                self.quest_view.append_log(msg)
        self.after(0, _ui)
        self.log_message(f"[Quest] {msg}", level)

    def _on_quest_slot_status(self, slot_idx: int, payload: Dict[str, Any]):
        enriched = dict(payload or {})
        ctrl = self._find_controller_by_slot(slot_idx)
        slot_state = self.state_mgr.slots.get(int(slot_idx), {}) if hasattr(self, "state_mgr") else {}
        if ctrl:
            enriched.setdefault("pid", ctrl.assigned_pid)
            c_name = (slot_state.get("char_name") if isinstance(slot_state, dict) else "") or getattr(ctrl, "char_name", "")
            if c_name and c_name not in ("--", "---"):
                enriched.setdefault("char_name", c_name)
        def _ui():
            if self.quest_view:
                self.quest_view.set_slot_quest_state(slot_idx, enriched)
        self.after(0, _ui)

    def _get_or_create_quest_runner(self, slot_idx: int) -> QuestSlotRunner:
        s_idx = int(slot_idx)
        runner = self.quest_runners.get(s_idx)
        if runner is not None:
            return runner

        def _get_eng():
            ctrl = self._find_controller_by_slot(s_idx)
            if not ctrl or not ctrl.assigned_pid or not psutil.pid_exists(ctrl.assigned_pid):
                return None
            if not ctrl.engine and MegDirectEngine:
                try:
                    ctrl.engine = MegDirectEngine.get_engine(ctrl.assigned_pid)
                except Exception:
                    return None
            return ctrl.engine

        def _stop_train():
            ctrl = self._find_controller_by_slot(s_idx)
            if ctrl and (ctrl.auto_requested or (ctrl.worker and ctrl.worker.running)):
                ctrl.stop_auto(reason="Tạm dừng Auto Train để chạy Auto Nhiệm Vụ", trigger_by="AUTO")

        runner = QuestSlotRunner(
            slot_idx=s_idx,
            engine_getter=_get_eng,
            config_getter=lambda: self.quest_config,
            on_log=self._on_quest_log,
            on_status=self._on_quest_slot_status,
            on_stop_train=_stop_train,
        )
        self.quest_runners[s_idx] = runner
        return runner

    def scan_quest_slot(self, slot_idx: int):
        s_idx = int(slot_idx)
        def _worker():
            ctrl = self._find_controller_by_slot(s_idx)
            runner = self.quest_runners.get(s_idx)
            is_running = bool(runner and runner.running)
            if not ctrl or not ctrl.assigned_pid or not psutil.pid_exists(ctrl.assigned_pid):
                self._on_quest_slot_status(
                    s_idx,
                    {"running": is_running, "status_text": "Chưa gán game", "status_color": "#64748b", "summary": {}},
                )
                return
            eng = ctrl.engine
            if not eng and MegDirectEngine:
                try:
                    eng = MegDirectEngine.get_engine(ctrl.assigned_pid)
                    ctrl.engine = eng
                except Exception as e:
                    self._on_quest_log(f"[Slot {s_idx}] Lỗi attach engine: {e}", "ERROR")
                    return
            if not eng:
                return
            if not getattr(eng, "is_ready", False):
                try:
                    eng.attach()
                    time.sleep(0.4)
                except Exception:
                    pass
            snap = eng.get_quest_state() if getattr(eng, "is_ready", False) else {"ok": False, "error": "Chưa kết nối Frida"}
            summary = summarize_quest_snapshot(snap, self.quest_config)
            st_txt = summary.get("reason") or (
                "Hoàn tất ✓" if summary.get("next_action") == "DONE" else "Sẵn sàng chạy"
            )
            st_col = "#22c55e" if summary.get("next_action") == "DONE" else ("#f59e0b" if summary.get("reason") else "#38bdf8")
            self._on_quest_slot_status(
                s_idx,
                {"running": is_running, "status_text": st_txt, "status_color": st_col, "summary": summary},
            )
        threading.Thread(target=_worker, daemon=True).start()

    def scan_all_quests(self):
        self._on_quest_log("🔍 Đang quét trạng thái nhiệm vụ cho toàn bộ slot đã kết nối...", "INFO")
        if self.quest_view:
            self.quest_view.update_from_state_snapshots(self.state_mgr.slots)
        for ctrl in self.controllers:
            if ctrl.assigned_pid and psutil.pid_exists(ctrl.assigned_pid):
                self.scan_quest_slot(ctrl.slot_idx)

    def toggle_quest_slot(self, slot_idx: int):
        s_idx = int(slot_idx)
        runner = self._get_or_create_quest_runner(s_idx)
        if runner.running:
            runner.stop()
            self._on_quest_log(f"[Slot {s_idx}] ⏹ Đã dừng Auto Nhiệm Vụ.", "INFO")
        else:
            if license_client and not license_client.is_license_valid():
                QMessageBox.warning(self, "Bản quyền", "Vui lòng kích hoạt bản quyền trước khi chạy Auto Nhiệm Vụ.")
                return
            runner.start()

    def start_selected_quests(self, slot_ids: List[int]):
        if license_client and not license_client.is_license_valid():
            QMessageBox.warning(self, "Bản quyền", "Vui lòng kích hoạt bản quyền trước khi chạy Auto Nhiệm Vụ.")
            return
        started = 0
        for s_idx in (slot_ids or []):
            ctrl = self._find_controller_by_slot(s_idx)
            if not ctrl or not ctrl.assigned_pid or not psutil.pid_exists(ctrl.assigned_pid):
                continue
            runner = self._get_or_create_quest_runner(s_idx)
            if not runner.running and runner.start():
                started += 1
        self._on_quest_log(
            f"▶ Đã khởi chạy Auto Nhiệm Vụ cho {started} slot." if started else "⚠️ Không có slot nào đã kết nối trong danh sách chọn.",
            "SUCCESS" if started else "WARNING",
        )

    def stop_all_quests(self, silent: bool = False):
        stopped = 0
        for runner in list(self.quest_runners.values()):
            if runner.running:
                runner.stop()
                stopped += 1
        if not silent:
            self._on_quest_log(f"⏹ Đã dừng Auto Nhiệm Vụ ({stopped} slot).", "INFO")

    # ==========================================================================
    # SHUTDOWN
    # ==========================================================================
    def on_closing(self):
        if self._is_closing:
            return
        self._is_closing = True
        self.running = False
        try:
            self.stop_all_quests(silent=True)
        except Exception:
            pass
        try:
            self._heartbeat_timer.stop()
        except Exception:
            pass
        try:
            self.engine_sync.stop()
        except Exception:
            pass
        for ctrl in list(self.controllers):
            try:
                if hasattr(ctrl, "stop_moss"):
                    ctrl.stop_moss()
                if ctrl.auto_requested or (ctrl.worker and ctrl.worker.running):
                    ctrl.stop_auto(reason="Người dùng đóng Dashboard Qt6", trigger_by="MANUAL")
            except Exception:
                pass
        for ctrl in list(self.controllers):
            if ctrl.engine:
                try:
                    ctrl.engine.detach()
                except Exception:
                    pass
        if license_client and hasattr(license_client, "clear_secure_game_offsets"):
            try:
                license_client.clear_secure_game_offsets()
            except Exception:
                pass

    def closeEvent(self, event):
        self.on_closing()
        event.accept()


# ==============================================================================
# BIND HEADLESS SCHEDULERS & EVENT LOGIC TỪ DashboardApp (KHÔNG DÙNG TKINTER)
# ==============================================================================
_HEADLESS_METHODS = (
    "_periodic_mirror_scheduler",
    "_periodic_moss_scheduler",
    "_monitor_mirror_telemetry_for_telegram",
    "_periodic_license_monitor",
    "_get_current_or_upcoming_mirror_event_key",
    "start_all_mirror_turbo_sniping",
    "stop_all_mirror_auto",
    "prepare_all_mirror_event",
    "click_all_mirror_npc",
    "manual_snipe_mirror_slot",
    "start_all_moss_auto",
    "stop_all_moss_auto",
    "record_mirror_net_telemetry",
)

_bound = 0
for _m_name in _HEADLESS_METHODS:
    if not hasattr(DashboardAppQt, _m_name) and hasattr(DashboardApp, _m_name):
        setattr(DashboardAppQt, _m_name, getattr(DashboardApp, _m_name))
        _bound += 1
print(f"[meg_gui_qt] Bound {_bound} headless scheduler/event methods from DashboardApp.")


def _enable_win11_dark_titlebar(win: QMainWindow):
    if sys.platform != "win32":
        return
    try:
        hwnd = int(win.winId())
        val = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11 / Win10)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), ctypes.c_int(attr), ctypes.byref(val), ctypes.sizeof(val)
            )
    except Exception:
        pass


def main():
    try:
        _boot_trace("main: creating QApplication")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setPalette(build_dark_palette())
        app.setStyleSheet(DARK_OPS_QSS)

        _boot_trace("main: creating DashboardAppQt")
        win = DashboardAppQt()
        _boot_trace("main: calling win.show()")
        win.show()
        _boot_trace("main: calling _enable_win11_dark_titlebar")
        _enable_win11_dark_titlebar(win)
        _boot_trace("main: entering event loop")

        if "--smoke-test" in sys.argv:
            QTimer.singleShot(600, lambda: (win.on_closing(), app.quit()))

        # Cho phép Ctrl+C thoát sạch sẽ trên Windows PowerShell
        _shutting = {"active": False}

        def _sigint(_signum, _frame):
            if _shutting["active"]:
                return
            _shutting["active"] = True
            try:
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            except Exception:
                pass
            print("\n[INFO] Đã nhận Ctrl+C. Đang đóng MEGAMU Dashboard Qt6 an toàn...")
            win.on_closing()
            app.quit()

        try:
            signal.signal(signal.SIGINT, _sigint)
        except Exception:
            pass

        sig_timer = QTimer()
        sig_timer.setInterval(250)
        sig_timer.timeout.connect(lambda: None)
        sig_timer.start()

        sys.exit(app.exec())
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        _report_fatal_startup_error(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
