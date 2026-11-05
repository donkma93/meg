"""
Core Module: Single-Instance Mutex.
Ngăn chặn người dùng mở 2 bản MEGAMU Dashboard cùng lúc làm xung đột cổng Frida và tệp JSON.
"""

import sys
import ctypes
from typing import Optional


class SingleInstanceMutex:
    """Quản lý Win32 Named Mutex đơn nhất cho Dashboard."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, mutex_name: str = "Global\\MEGAMU_AutoTrain_Dashboard_App_Mutex"):
        self.mutex_name = mutex_name
        self.handle: Optional[int] = None
        self.already_running: bool = False

    def acquire(self) -> bool:
        """Thử chiếm quyền khóa Mutex. Trả về True nếu là bản duy nhất, False nếu đã có bản đang chạy."""
        if sys.platform != "win32":
            return True

        try:
            kernel32 = ctypes.windll.kernel32
            # CreateMutexW(security_attributes, bInitialOwner, lpName)
            self.handle = kernel32.CreateMutexW(None, True, self.mutex_name)
            last_err = kernel32.GetLastError()
            if last_err == self.ERROR_ALREADY_EXISTS:
                self.already_running = True
                if self.handle:
                    kernel32.CloseHandle(self.handle)
                    self.handle = None
                return False
            self.already_running = False
            return True
        except Exception:
            # Fallback an toàn nếu có lỗi hệ thống
            return True

    def release(self):
        """Giải phóng khóa Mutex khi đóng ứng dụng."""
        if sys.platform == "win32" and self.handle:
            try:
                ctypes.windll.kernel32.ReleaseMutex(self.handle)
                ctypes.windll.kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            finally:
                self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    @staticmethod
    def activate_existing_window(window_title: str) -> bool:
        """Kích hoạt và đưa cửa sổ đang chạy lên màn hình trước (Restore & SetForegroundWindow)."""
        if sys.platform != "win32":
            return False
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
        except Exception:
            pass
        return False
