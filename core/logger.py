"""
Async Ring-Buffer Logging System for MEGAMU Auto Train Dashboard.
Provides high-performance, non-blocking asynchronous log ingestion,
bounded in-memory ring buffer (zero RAM leaks), and automated file rotation.
"""

import os
import time
import queue
import threading
from collections import deque
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_FILE = BASE_DIR / "auto_dashboard.log"
MAX_LOG_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per file
MAX_BACKUP_COUNT = 3
RING_BUFFER_CAPACITY = 1500


class LogEntry:
    __slots__ = ("timestamp_str", "slot_tag", "level", "message", "full_formatted")

    def __init__(self, message: str, level: str = "INFO", slot_tag: Optional[str] = None):
        self.timestamp_str = time.strftime("%H:%M:%S")
        self.level = level.upper()
        self.message = message

        if slot_tag is None:
            if message.startswith("[Slot ") and len(message) >= 9:
                try:
                    self.slot_tag = message[6:8]
                except Exception:
                    self.slot_tag = "ALL"
            else:
                self.slot_tag = "ALL"
        else:
            self.slot_tag = slot_tag

        self.full_formatted = f"[{self.timestamp_str}] [{self.level}] {self.message}"

    def __repr__(self) -> str:
        return self.full_formatted


class AsyncRingBufferLogger:
    """
    High-performance Asynchronous Ring Buffer Logger.
    - Thread-safe non-blocking push ($O(1)$)
    - Memory footprint strictly bounded by `RING_BUFFER_CAPACITY`
    - Background worker thread for non-blocking disk I/O and file rotation
    """
    _instance: Optional['AsyncRingBufferLogger'] = None
    _singleton_lock = threading.Lock()

    def __init__(
        self,
        log_file: Path = DEFAULT_LOG_FILE,
        ring_capacity: int = RING_BUFFER_CAPACITY,
        max_bytes: int = MAX_LOG_FILE_BYTES,
        backup_count: int = MAX_BACKUP_COUNT
    ):
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.ring_capacity = ring_capacity

        # Ring buffer in RAM strictly bounded
        self._buffer_lock = threading.RLock()
        self._ring_buffer: deque[LogEntry] = deque(maxlen=self.ring_capacity)

        # Asynchronous queue for disk persistence
        self._queue: queue.Queue[Optional[LogEntry]] = queue.Queue(maxsize=10000)
        self._running = True

        # Callback for UI notification (debounced by UI)
        self._ui_callback: Optional[Callable[[], None]] = None

        # Start worker thread
        self._worker_thread = threading.Thread(target=self._disk_writer_loop, name="AsyncLogWriter", daemon=True)
        self._worker_thread.start()

    @classmethod
    def get_instance(cls) -> 'AsyncRingBufferLogger':
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_ui_callback(self, callback: Callable[[], None]):
        """Registers a callback to notify the UI when new logs arrive."""
        self._ui_callback = callback

    def log(self, message: str, level: str = "INFO", slot_tag: Optional[str] = None):
        """
        Public non-blocking logging method.
        Pushes entry to memory buffer and background disk queue in O(1) time.
        """
        entry = LogEntry(message=message, level=level, slot_tag=slot_tag)

        # 1. Update bounded in-memory buffer
        with self._buffer_lock:
            self._ring_buffer.append(entry)

        # 2. Queue for background disk write (drop if queue is unexpectedly full)
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            pass

        # 3. Trigger UI callback if registered
        cb = self._ui_callback
        if cb:
            try:
                cb()
            except Exception:
                pass

    def get_logs_data_tuples(self) -> List[Tuple[str, str, str]]:
        """
        Returns snapshot of logs compatible with legacy meg_gui:
        List of (timestamp_str, slot_tag, '[LEVEL] message')
        """
        with self._buffer_lock:
            return [(e.timestamp_str, e.slot_tag, f"[{e.level}] {e.message}") for e in self._ring_buffer]

    def get_filtered_lines(self, filter_slot: str = "ALL", limit: int = 500) -> List[str]:
        """Returns pre-formatted log lines filtered by slot tag."""
        with self._buffer_lock:
            snapshot = list(self._ring_buffer)

        is_all = (filter_slot == "ALL" or filter_slot.lower() in ("tất cả", "all"))
        res: List[str] = []
        for entry in snapshot:
            if is_all or entry.slot_tag == filter_slot:
                res.append(entry.full_formatted)

        if limit and len(res) > limit:
            return res[-limit:]
        return res

    def clear(self):
        """Clears the in-memory ring buffer."""
        with self._buffer_lock:
            self._ring_buffer.clear()

    def _rotate_file_if_needed(self):
        """Rotates log file if it exceeds max_bytes."""
        try:
            if not self.log_file.exists():
                return
            if self.log_file.stat().st_size < self.max_bytes:
                return

            # Rotate backups: file.log.3 deleted, file.log.2 -> file.log.3, etc.
            for i in range(self.backup_count - 1, 0, -1):
                s = self.log_file.with_name(f"{self.log_file.name}.{i}")
                d = self.log_file.with_name(f"{self.log_file.name}.{i + 1}")
                if s.exists():
                    try:
                        if d.exists():
                            d.unlink()
                        s.rename(d)
                    except Exception:
                        pass

            # Rename current to .1
            d1 = self.log_file.with_name(f"{self.log_file.name}.1")
            if d1.exists():
                try:
                    d1.unlink()
                except Exception:
                    pass
            try:
                self.log_file.rename(d1)
            except Exception:
                pass
        except Exception:
            pass

    def _disk_writer_loop(self):
        """Background loop reading from queue and appending to log file in batches."""
        batch: List[LogEntry] = []
        last_flush = time.time()

        while self._running:
            try:
                # Wait for up to 0.5s for new entries
                try:
                    entry = self._queue.get(timeout=0.5)
                    if entry is not None:
                        batch.append(entry)
                except queue.Empty:
                    pass

                # Drain remaining available items up to 50
                while len(batch) < 50:
                    try:
                        entry = self._queue.get_nowait()
                        if entry is None:
                            self._running = False
                            break
                        batch.append(entry)
                    except queue.Empty:
                        break

                now = time.time()
                # Flush batch if we have items and (batch is large or 1 second elapsed)
                if batch and (len(batch) >= 20 or (now - last_flush) >= 1.0 or not self._running):
                    self._flush_batch_to_disk(batch)
                    batch.clear()
                    last_flush = now

            except Exception:
                time.sleep(0.5)

        # Flush any remaining items upon shutdown
        if batch:
            try:
                self._flush_batch_to_disk(batch)
            except Exception:
                pass

    def _flush_batch_to_disk(self, batch: List[LogEntry]):
        try:
            self._rotate_file_if_needed()
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            date_prefix = time.strftime("%Y-%m-%d")
            with open(self.log_file, "a", encoding="utf-8") as f:
                for item in batch:
                    f.write(f"[{date_prefix} {item.timestamp_str}] [{item.level}] [{item.slot_tag}] {item.message}\n")
        except Exception:
            pass

    def shutdown(self):
        """Gracefully shuts down writer thread."""
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)


# Module-level convenience functions
def get_logger() -> AsyncRingBufferLogger:
    return AsyncRingBufferLogger.get_instance()


def log_message(message: str, level: str = "INFO", slot_tag: Optional[str] = None):
    get_logger().log(message, level=level, slot_tag=slot_tag)
