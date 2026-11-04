"""
Domain Service: MemoryService.
Chuyên trách quản lý bộ nhớ, dọn dẹp RAM, và tối ưu Working Set cho các tiến trình game MEGAMU và Dashboard.
"""

import ctypes
import os
import psutil
from typing import Dict, Any, List


class MemoryService:
    """Domain service tối ưu hóa và dọn dẹp bộ nhớ RAM cho hệ thống."""

    @classmethod
    def get_system_memory_info(cls) -> Dict[str, Any]:
        """Lấy thông tin tổng quan về RAM của toàn hệ điều hành."""
        mem = psutil.virtual_memory()
        return {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "available_mb": round(mem.available / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "percent": mem.percent
        }

    @classmethod
    def trim_process_working_set(cls, pid: int) -> bool:
        """Thu hồi bộ nhớ RAM đệm (Working Set) của 1 tiến trình qua Win32 API."""
        if not psutil.pid_exists(pid):
            return False
        try:
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_QUERY_INFORMATION = 0x0400
            h_proc = ctypes.windll.kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION,
                False,
                pid
            )
            if not h_proc:
                return False
            try:
                ctypes.windll.kernel32.SetProcessWorkingSetSize(h_proc, -1, -1)
                ctypes.windll.psapi.EmptyWorkingSet(h_proc)
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(h_proc)
        except Exception:
            return False

    @classmethod
    def trim_all_game_processes(cls, pids: List[int]) -> Dict[str, int]:
        """Dọn dẹp RAM đồng loạt cho toàn bộ danh sách tiến trình game đã phát hiện."""
        trimmed = 0
        failed = 0
        for pid in pids:
            if cls.trim_process_working_set(pid):
                trimmed += 1
            else:
                failed += 1
        return {"trimmed": trimmed, "failed": failed}

    @classmethod
    def trim_self(cls) -> bool:
        """Tự thu hồi RAM đệm của chính ứng dụng Dashboard."""
        return cls.trim_process_working_set(os.getpid())

