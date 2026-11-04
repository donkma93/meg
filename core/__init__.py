try:
    import license_client
except ImportError:
    license_client = None

"""
Core module for MEGAMU Auto Train Dashboard.
Houses persistent storage, application state, background logging, and system mutex services.
"""

from .storage import (
    ConfigPersistenceManager,
    CONFIG_DIR,
    PROFILE_FILE,
    DEFAULT_CONFIG_FILE,
    SLOT_ASSIGNMENTS_FILE,
    UI_SETTINGS_FILE,
    MAP_COMMANDS_FILE,
    MOSS_CONFIG_FILE,
    MIRROR_CONFIG_FILE,
    EVENT_CONFIG_FILE,
    CLASS_STAT_PROFILES_FILE,
    CLASS_ID_TO_CODE,
    CLASS_CODE_TO_NAME,
    atomic_write_json,
)

from .logger import (
    AsyncRingBufferLogger,
    LogEntry,
    get_logger,
    log_message,
)

from .system_mutex import SingleInstanceMutex
from .slot_controller import SlotController
from .constants import APP_NAME, APP_VERSION, PROFILE_NAMES, MAX_SLOTS, LOGO_FILE, ICON_FILE, get_resource_path
from .i18n import I18N, CURRENT_LANG, load_language_preference, save_language_preference, tr
from .process_utils import record_auto_stop_log, character_name_from_window_title, enumerate_megamu_processes, is_megamu_process_alive

__all__ = [
    "ConfigPersistenceManager",
    "CONFIG_DIR",
    "PROFILE_FILE",
    "DEFAULT_CONFIG_FILE",
    "SLOT_ASSIGNMENTS_FILE",
    "UI_SETTINGS_FILE",
    "MAP_COMMANDS_FILE",
    "MOSS_CONFIG_FILE",
    "MIRROR_CONFIG_FILE",
    "EVENT_CONFIG_FILE",
    "CLASS_STAT_PROFILES_FILE",
    "CLASS_ID_TO_CODE",
    "CLASS_CODE_TO_NAME",
    "atomic_write_json",
    "AsyncRingBufferLogger",
    "LogEntry",
    "get_logger",
    "log_message",
    "SingleInstanceMutex",
    "SlotController",
    "APP_NAME",
    "APP_VERSION",
    "PROFILE_NAMES",
    "MAX_SLOTS",
    "I18N",
    "CURRENT_LANG",
    "load_language_preference",
    "save_language_preference",
    "tr",
    "record_auto_stop_log",
    "character_name_from_window_title",
    "enumerate_megamu_processes",
    "is_megamu_process_alive",
]
