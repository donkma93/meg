"""
Train Domain Service for MEGAMU Auto Train Dashboard.
Manages AutoTrainWorker lifecycle, stage transitions, and safe pause/resume mechanisms.
"""

import threading
from typing import Dict, Any, List, Optional, Callable
from meg_auto_worker import AutoTrainWorker


class TrainService:
    """Domain service managing the Auto Train workers across all slots."""

    _instance: Optional['TrainService'] = None
    _lock = threading.RLock()

    def __init__(self):
        self._workers: Dict[int, AutoTrainWorker] = {}

    @classmethod
    def get_instance(cls) -> 'TrainService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start_train_worker(
        self,
        slot_idx: int,
        pid: int,
        stages: List[Dict[str, Any]],
        config: Dict[str, Any],
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> AutoTrainWorker:
        """Khởi động worker chạy auto train cho 1 slot cụ thể."""
        with self._lock:
            # Dừng worker cũ nếu đang chạy
            self.stop_train_worker(slot_idx, reason="Khởi động lại cấu hình mới")

            worker = AutoTrainWorker(
                pid=pid,
                stages=stages,
                log_callback=log_callback,
                progress_callback=progress_callback,
                config=config,
                slot_idx=slot_idx
            )
            worker.start()
            self._workers[slot_idx] = worker
            return worker

    def stop_train_worker(self, slot_idx: int, reason: str = "Người dùng dừng Auto") -> bool:
        """Dừng an toàn worker auto train của 1 slot."""
        with self._lock:
            worker = self._workers.pop(slot_idx, None)
            if worker:
                try:
                    worker.stop(reason=reason)
                    return True
                except Exception:
                    pass
            return False

    def pause_train_worker(self, slot_idx: int, reason: str = "Tạm dừng cho sự kiện") -> bool:
        """Tạm dừng worker auto train để nhường quyền ưu tiên cho sự kiện (Devil / Moss / Mirror)."""
        with self._lock:
            worker = self._workers.get(slot_idx)
            if worker and worker.running:
                try:
                    worker.pause_for_event(reason=reason)
                    return True
                except Exception:
                    pass
            return False

    def resume_train_worker(self, slot_idx: int, reason: str = "Khôi phục Auto Train") -> bool:
        """Khôi phục worker auto train sau khi sự kiện kết thúc."""
        with self._lock:
            worker = self._workers.get(slot_idx)
            if worker and worker.running:
                try:
                    worker.resume_from_event(reason=reason)
                    return True
                except Exception:
                    pass
            return False

    def get_worker(self, slot_idx: int) -> Optional[AutoTrainWorker]:
        """Lấy tham chiếu worker của slot_idx."""
        with self._lock:
            return self._workers.get(slot_idx)

    def is_worker_running(self, slot_idx: int) -> bool:
        """Kiểm tra worker của slot_idx có đang hoạt động không."""
        with self._lock:
            worker = self._workers.get(slot_idx)
            return bool(worker and worker.running)

    def stop_all(self, reason: str = "Dừng toàn bộ Auto Train"):
        """Dừng toàn bộ workers trên tất cả các slots."""
        with self._lock:
            for s_idx in list(self._workers.keys()):
                self.stop_train_worker(s_idx, reason=reason)

