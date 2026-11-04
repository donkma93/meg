"""
UI View: LogsView (Modal Nhật ký Hệ thống Ring Buffer).
Chuyên trách quản lý cửa sổ Modal nhật ký độc lập, z-index cao hơn màn hình chính.
"""

from typing import Any, Optional
from ui.modals.logs_modal import open_logs_window


class LogsView:
    """Builder và quản trị Modal Nhật ký hệ thống."""

    def __init__(self, master_app: Any):
        self.app = master_app

    def is_open(self) -> bool:
        dlg = getattr(self.app, "_logs_window_instance", None)
        return bool(dlg and dlg.winfo_exists())

    def lift(self):
        dlg = getattr(self.app, "_logs_window_instance", None)
        if dlg and dlg.winfo_exists():
            dlg.lift()
            dlg.focus_force()

    def open(self, default_slot: Optional[str] = None):
        return open_logs_window(self.app, default_slot)
