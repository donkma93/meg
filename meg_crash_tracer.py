"""
Module: meg_crash_tracer.py
Mục đích: Ghi nhận nhật ký giám sát, cảnh báo và truy vết sự cố (Audit & Crash Trace Logging)
để đảm bảo hệ thống vận hành 24/7 ổn định, không bị crash ngầm và có đầy đủ bằng chứng kỹ thuật.
"""

import sys
import os
import time
from datetime import datetime
from pathlib import Path
import threading
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
CRASH_TRACE_LOG_FILE = BASE_DIR / "auto_crash_trace.log"

_log_lock = threading.Lock()


def log_crash_trace(
    source: str,
    event: str,
    details: str,
    pid: Optional[int] = None,
    char_name: Optional[str] = None,
    level: str = "INFO"
) -> None:
    """
    Ghi nhật ký trace có cấu trúc vào auto_crash_trace.log.
    Hỗ trợ flush tức thì để không bị mất dữ liệu khi tiến trình gặp sự cố bất ngờ.
    """
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        pid_str = f"PID: {pid}" if pid else "PID: N/A"
        char_str = f"Char: {char_name}" if char_name else "Char: N/A"
        lvl_str = f"{level.upper():<5}"
        
        line = f"[{now_str}] [{lvl_str}] [{source}] [{pid_str}] [{char_str}] [{event}] -> {details}\n"
        
        with _log_lock:
            with open(CRASH_TRACE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
    except Exception:
        pass


def trace_gc_protection(event: str, details: str, pid: Optional[int] = None, char_name: Optional[str] = None):
    """Ghi nhận các sự kiện bảo vệ Unity IL2CPP Boehm GC và cấp phát bộ nhớ an toàn."""
    log_crash_trace(
        source="GC_GUARD",
        event=event,
        details=details,
        pid=pid,
        char_name=char_name,
        level="INFO"
    )


def trace_ram_trim(event: str, details: str, pid: Optional[int] = None):
    """Ghi nhận sự kiện dọn RAM Working Set, ngăn ngừa bão hard page faults."""
    log_crash_trace(
        source="RAM_TRIM",
        event=event,
        details=details,
        pid=pid,
        level="WARN" if "BLOCK" in event.upper() or "SKIP" in event.upper() else "INFO"
    )


def trace_frida_event(event: str, details: str, pid: Optional[int] = None, level: str = "INFO"):
    """Ghi nhận sự kiện Frida hooks, telemetry ticks, detach, hoặc exception."""
    log_crash_trace(
        source="FRIDA_ENGINE",
        event=event,
        details=details,
        pid=pid,
        level=level
    )


def trace_process_exit(pid: int, reason: str, char_name: Optional[str] = None):
    """Ghi nhận sự kiện tiến trình game MEGAMU.exe thoát hoặc crash."""
    log_crash_trace(
        source="PROCESS_LIFECYCLE",
        event="PROCESS_TERMINATED",
        details=reason,
        pid=pid,
        char_name=char_name,
        level="ERROR" if "crash" in reason.lower() or "exception" in reason.lower() else "WARN"
    )
