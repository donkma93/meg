"""
Module: meg_crash_tracer.py
Mục đích: Ghi nhận nhật ký giám sát, cảnh báo và truy vết sự cố toàn diện (Audit & Crash Trace Logging)
cho TẤT CẢ các luồng (threads) trong hệ thống. Đảm bảo mọi ngoại lệ (exception) phát sinh
trong bất kỳ luồng nào đều được ghi nhận nguyên nhân, vị trí file/dòng, và đầy đủ call stack traceback
vào nhật ký file (auto_crash_trace.log, app_exceptions.log) và hiển thị lên giao diện UI.
"""

import sys
import os
import time
import re
import traceback
import functools
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import threading
from typing import Optional, Callable, List, Any

BASE_DIR = Path(__file__).resolve().parent
CRASH_TRACE_LOG_FILE = BASE_DIR / "auto_crash_trace.log"
APP_EXCEPTIONS_LOG_FILE = BASE_DIR / "app_exceptions.log"

_log_lock = threading.RLock()
_ui_callbacks: List[Callable[[str, str], Any]] = []
_hooks_installed = False
_orig_thread_run = None
_orig_sys_excepthook = None
_orig_threading_excepthook = None


def register_ui_exception_callback(cb: Callable[[str, str], Any]) -> None:
    """Đăng ký hàm callback nhận thông báo lỗi luồng lên UI (ví dụ app.log_message)."""
    with _log_lock:
        if cb not in _ui_callbacks:
            _ui_callbacks.append(cb)


def unregister_ui_exception_callback(cb: Callable[[str, str], Any]) -> None:
    """Hủy đăng ký hàm callback nhận thông báo lỗi luồng."""
    with _log_lock:
        if cb in _ui_callbacks:
            _ui_callbacks.remove(cb)


def _dispatch_to_ui(msg: str, level: str = "ERROR") -> None:
    """Phát thông báo lỗi đến toàn bộ các callback UI đã đăng ký một cách an toàn."""
    with _log_lock:
        cbs = list(_ui_callbacks)
    for cb in cbs:
        try:
            cb(msg, level=level)
        except Exception:
            pass


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


def log_thread_exception(
    source: str,
    exc: BaseException,
    thread_name: Optional[str] = None,
    details: str = "",
    level: str = "ERROR",
    include_ui: bool = True
) -> None:
    """
    Ghi nhận chi tiết ngoại lệ của luồng:
    - Bắt đầy đủ traceback, kiểu exception, thông điệp lỗi, file và số dòng gây lỗi.
    - Ghi nhận Thread Name, Native Thread ID, Daemon status, Timestamp mili-giây.
    - Ghi vào auto_crash_trace.log và app_exceptions.log với atomic flush.
    - Bắn thông báo có phân loại [Slot XX] lên giao diện GUI để người dùng dễ theo dõi.
    """
    try:
        now_dt = datetime.now()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        cur_thread = threading.current_thread()
        t_name = thread_name or cur_thread.name or f"Thread-{threading.get_ident()}"
        t_ident = threading.get_ident()
        is_daemon = cur_thread.daemon
        
        exc_type = type(exc).__name__
        exc_msg = str(exc).strip() or "(No message)"
        
        # Trích xuất leaf frame (nơi lỗi trực tiếp phát sinh)
        tb_obj = getattr(exc, "__traceback__", None)
        loc_str = "Unknown location"
        file_name = "unknown"
        line_no = 0
        func_name = "unknown"
        
        if tb_obj:
            tb_entries = traceback.extract_tb(tb_obj)
            if tb_entries:
                leaf = tb_entries[-1]
                file_name = Path(leaf.filename).name
                line_no = leaf.lineno
                func_name = leaf.name
                loc_str = f"{file_name}:{line_no} in {func_name}()"
            full_tb = "".join(traceback.format_exception(type(exc), exc, tb_obj)).strip()
        else:
            full_tb = "".join(traceback.format_exception(type(exc), exc, None)).strip()
        
        # Bắt chuỗi chained exceptions (__cause__ hoặc __context__) nếu có
        chained_cause = ""
        if getattr(exc, "__cause__", None):
            cause_exc = exc.__cause__
            chained_cause = f"\n[Chained Cause]: {type(cause_exc).__name__}: {cause_exc}"
        elif getattr(exc, "__context__", None) and not getattr(exc, "__suppress_context__", False):
            context_exc = exc.__context__
            chained_cause = f"\n[Context Exception]: {type(context_exc).__name__}: {context_exc}"
        
        # Định dạng khối nhật ký có cấu trúc rõ ràng
        separator = "=" * 80
        details_part = f"\nChi tiết bổ sung: {details}" if details else ""
        trace_block = (
            f"\n{separator}\n"
            f"[{now_str}] [{level.upper()}] THREAD EXCEPTION TRACE\n"
            f"Tên Luồng   : {t_name} (TID: {t_ident}, Daemon: {is_daemon})\n"
            f"Nguồn/Tác vụ: {source}\n"
            f"Vị trí lỗi  : {loc_str}\n"
            f"Ngoại lệ    : {exc_type}: {exc_msg}{details_part}{chained_cause}\n"
            f"{'-' * 32} CALL STACK TRACEBACK {'-' * 28}\n"
            f"{full_tb}\n"
            f"{separator}\n"
        )
        
        # Ghi đồng thời vào auto_crash_trace.log và app_exceptions.log
        with _log_lock:
            for log_path in (CRASH_TRACE_LOG_FILE, APP_EXCEPTIONS_LOG_FILE):
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(trace_block)
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except Exception:
                            pass
                except Exception:
                    pass
        
        # Ghi 1 dòng vắn tắt vào nhật ký phẳng auto_crash_trace.log
        log_crash_trace(
            source=f"THREAD:{t_name}",
            event="EXCEPTION_CAUGHT",
            details=f"[{exc_type}: {exc_msg}] tại {loc_str}",
            level=level
        )
        
        # Phát thông báo lên giao diện GUI
        if include_ui:
            # Nhận diện tiền tố [Slot XX] nếu tên luồng hoặc nguồn chứa thông tin Slot
            slot_prefix = ""
            full_context = f"{t_name} {source} {details}"
            m = re.search(r"[Ss]lot\s*0?(\d{1,2})", full_context)
            if m:
                try:
                    slot_num = int(m.group(1))
                    slot_prefix = f"[Slot {slot_num:02d}] "
                except Exception:
                    pass
            
            ui_msg = (
                f"{slot_prefix}[LỖI LUỒNG: {t_name}] {exc_type}: {exc_msg} "
                f"({loc_str}) -> Đã ghi chi tiết vào auto_crash_trace.log"
            )
            _dispatch_to_ui(ui_msg, level="ERROR")
            
    except Exception:
        pass


def _traced_thread_run(self, *args, **kwargs):
    """
    Wrapper an toàn tuyệt đối bọc quanh threading.Thread.run():
    Mọi luồng chạy qua Python threading đều được tự động giám sát.
    Nếu có bất kỳ unhandled exception nào xảy ra, toàn bộ traceback và nguyên nhân
    được lưu lại tức thì trước khi lan truyền.
    """
    t_name = self.name or getattr(self, "_target", None) or f"Thread-{threading.get_ident()}"
    try:
        if _orig_thread_run is not None:
            return _orig_thread_run(self, *args, **kwargs)
    except SystemExit:
        raise
    except BaseException as exc:
        if not getattr(exc, "_logged_by_crash_tracer", False):
            try:
                setattr(exc, "_logged_by_crash_tracer", True)
                log_thread_exception(
                    source=f"Thread:{t_name}",
                    exc=exc,
                    thread_name=t_name,
                    details=f"Thread Target: {getattr(self, '_target', None)}"
                )
            except Exception:
                pass
        raise


def _global_threading_excepthook(args):
    """Xử lý unhandled exceptions trong tất cả background threads (Python 3.8+)."""
    exc = args.exc_value
    thread = args.thread
    t_name = thread.name if thread else f"Thread-{threading.get_ident()}"
    
    if not getattr(exc, "_logged_by_crash_tracer", False):
        try:
            setattr(exc, "_logged_by_crash_tracer", True)
            log_thread_exception(
                source=f"Thread:{t_name}",
                exc=exc,
                thread_name=t_name,
                details="Unhandled thread exception via threading.excepthook"
            )
        except Exception:
            pass
            
    if _orig_threading_excepthook is not None:
        try:
            _orig_threading_excepthook(args)
        except Exception:
            pass


def _global_sys_excepthook(exc_type, exc_value, exc_traceback):
    """Xử lý unhandled exceptions trên luồng chính (MainThread)."""
    if not getattr(exc_value, "_logged_by_crash_tracer", False):
        try:
            setattr(exc_value, "_logged_by_crash_tracer", True)
            log_thread_exception(
                source="MainThread",
                exc=exc_value,
                thread_name="MainThread",
                details="Unhandled exception on MainThread via sys.excepthook"
            )
        except Exception:
            pass
            
    if _orig_sys_excepthook is not None:
        try:
            _orig_sys_excepthook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass


def install_global_exception_hooks(ui_callback: Optional[Callable[[str, str], Any]] = None) -> None:
    """
    Cài đặt bẫy ngoại lệ toàn diện 3 lớp cho toàn bộ tiến trình:
    1. Bọc threading.Thread.run() để đón đầu mọi exception trên tất cả luồng con.
    2. Hook threading.excepthook để bắt các exception chưa được xử lý trên background threads.
    3. Hook sys.excepthook để bắt các exception chưa được xử lý trên luồng chính.
    """
    global _hooks_installed, _orig_thread_run, _orig_sys_excepthook, _orig_threading_excepthook
    
    if ui_callback is not None:
        register_ui_exception_callback(ui_callback)
        
    if _hooks_installed:
        return
        
    with _log_lock:
        if _hooks_installed:
            return
            
        # 1. Bọc threading.Thread.run()
        _orig_thread_run = threading.Thread.run
        threading.Thread.run = _traced_thread_run
        
        # 2. Hook threading.excepthook
        if hasattr(threading, "excepthook"):
            _orig_threading_excepthook = threading.excepthook
            threading.excepthook = _global_threading_excepthook
            
        # 3. Hook sys.excepthook
        _orig_sys_excepthook = sys.excepthook
        sys.excepthook = _global_sys_excepthook
        
        _hooks_installed = True
        
    log_crash_trace(
        source="SYSTEM",
        event="EXCEPTION_HOOKS_INSTALLED",
        details="Đã kích hoạt bẫy bắt lỗi toàn cầu cho tất cả luồng (Thread Run + threading.excepthook + sys.excepthook)"
    )


@contextmanager
def traced_thread_scope(source: str, thread_name: Optional[str] = None, details: str = "", swallow: bool = False):
    """
    Context manager ghi nhật ký ngoại lệ trong một phạm vi thực thi luồng:
    with traced_thread_scope("AutoWorker._run", details="Slot 1"):
        do_work()
    """
    try:
        yield
    except Exception as exc:
        log_thread_exception(source=source, exc=exc, thread_name=thread_name, details=details)
        if not swallow:
            raise


def traced_thread(name: Optional[str] = None, source: Optional[str] = None, swallow: bool = False):
    """Decorator tự động ghi nhận ngoại lệ cho bất kỳ hàm worker nào chạy trên luồng riêng."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t_name = name or threading.current_thread().name
            src = source or func.__name__
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                log_thread_exception(source=src, exc=exc, thread_name=t_name)
                if not swallow:
                    raise
        return wrapper
    return decorator


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
