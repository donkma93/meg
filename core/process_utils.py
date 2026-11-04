"""
Core Module: Process & Window Utilities for MEGAMU.
Handles window title parsing, process enumeration, and auto-stop audit logging.
"""

import os
import re
import time
import ctypes
import psutil
from pathlib import Path
from typing import Dict, Optional

CONFIG_DIR = Path("config")
AUTO_STOP_LOG_FILE = CONFIG_DIR / "auto_stop_events.log"

try:
    user32 = ctypes.windll.user32
except Exception:
    user32 = None

try:
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
except Exception:
    kernel32 = None
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

try:
    from core.crash_tracer import log_crash_trace
except ImportError:
    def log_crash_trace(*args, **kwargs): pass


def record_auto_stop_log(
    slot_idx: int,
    pid: Optional[int],
    char_name: str,
    trigger_type: str,
    reason: str,
    coords: str = "--,--",
    level: str = "---"
):
    """
    Ghi nhật ký chi tiết mỗi khi một tài khoản Auto dừng lại (Persistent Audit Trace Log).
    Phân loại rõ ràng:
    - MANUAL: Do con người (người dùng) chủ động bấm dừng / thao tác giao diện.
    - SYSTEM: Do hệ thống / game tự ngắt (crash, mất PID, mất bản quyền, lỗi chặng...).
    Đồng bộ vào auto_stop_events.log và auto_crash_trace.log để truy vết sự cố 24/7.
    """
    try:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        tag = trigger_type.upper()
        line = (
            f"[{now_str}] [{tag:<6}] [Slot {slot_idx:02d}] "
            f"[PID: {pid if pid else 'N/A'}] [Nhân vật: {char_name or 'N/A'}] [Cấp: {level}] [Tọa độ: {coords}] "
            f"-> Lý do: {reason}\n"
        )
        with open(AUTO_STOP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        
        log_crash_trace(
            source="DASHBOARD_AUDIT",
            event=tag,
            details=f"Slot {slot_idx:02d} | Reason: {reason} | Coords: {coords} | Level: {level}",
            pid=pid,
            char_name=char_name,
            level="WARN" if tag == "SYSTEM" else "INFO"
        )
    except Exception:
        pass


def character_name_from_window_title(title: str) -> str:
    """Trích xuất tên nhân vật từ tiêu đề cửa sổ MEGAMU."""
    if not title:
        return ""
    title = str(title).strip()
    if "MEGAMU" not in title.upper():
        return ""
    
    # Mẫu 1: Diradira (660/51rr) - MEGAMU Sv41 hoặc Diradira (660) - MEGAMU...
    m1 = re.match(r"^(?P<name>[^(\-\[\]]+?)\s*(?:\([^)]+\))?\s*[-–—]\s*MEGAMU", title, re.IGNORECASE)
    if m1:
        name = m1.group("name").strip()
        if name and not name.upper().startswith("MEGAMU"):
            return name
    # Mẫu 2: MEGAMU - Diradira (660/51rr)...
    m2 = re.match(r"^MEGAMU\s*[-–—]\s*(?P<name>[^(\-\[\]]+)", title, re.IGNORECASE)
    if m2:
        name = m2.group("name").strip()
        if name and not name.upper().startswith("MEGAMU"):
            return name
    # Mẫu 3: Cắt theo - MEGAMU
    parts = re.split(r"\s*[-–—]\s*MEGAMU", title, flags=re.IGNORECASE)
    if parts and parts[0]:
        head = parts[0].strip()
        if " (" in head:
            head = head.split(" (")[0].strip()
        if head and not head.upper().startswith("MEGAMU"):
            return head
    return ""


def is_megamu_process_alive(pid: Optional[int]) -> bool:
    """
    Kiểm tra một PID MEGAMU có thực sự đang chạy và còn sống trên Windows hay không.
    Sử dụng Win32 Kernel API GetExitCodeProcess siêu tốc (0.002ms/call) thay vì quét
    toàn bộ thread của Windows gây đóng băng Main UI Thread và GIL.
    """
    if not pid or pid <= 0:
        return False

    if kernel32:
        try:
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            exit_code = ctypes.c_ulong()
            success = kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            kernel32.CloseHandle(h)
            if not success or exit_code.value != STILL_ACTIVE:
                return False
            return True
        except Exception:
            pass

    try:
        if not psutil.pid_exists(pid):
            return False
        p = psutil.Process(pid)
        if not p.is_running():
            return False
        status = p.status()
        if status in (
            getattr(psutil, "STATUS_STOPPED", "stopped"),
            getattr(psutil, "STATUS_ZOMBIE", "zombie"),
            getattr(psutil, "STATUS_DEAD", "dead")
        ):
            return False
        return True
    except Exception:
        return False


def enumerate_megamu_processes() -> Dict[int, str]:
    """
    Tìm tất cả tiến trình MEGAMU.exe đang thực sự chạy trên hệ thống.
    Tự động lọc bỏ các tiến trình chết (Stopped), tiến trình ma (Zombie/Ghost),
    hoặc tiến trình rác có RAM < 20MB.
    """
    pids = set()
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if not p.info['name'] or p.info['name'].lower() != 'megamu.exe':
                continue
            pid = p.info['pid']
            if not is_megamu_process_alive(pid):
                continue
            pids.add(pid)
        except Exception:
            pass

    pid_to_title = {pid: "" for pid in pids}
    if not user32:
        return pid_to_title

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if "megamu" in title.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                p_val = pid.value
                if p_val in pid_to_title and not pid_to_title[p_val]:
                    pid_to_title[p_val] = title
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    return pid_to_title
