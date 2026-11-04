"""
UI View: ProfilesView (Modal Cấu hình 10 Profile & Bãi Quái).
Chuyên trách quản lý cửa sổ Modal cấu hình độc lập, z-index cao hơn màn hình chính.
"""

from typing import Any, Optional
from ui.modals.profiles_modal import open_profiles_modal


class ProfilesView:
    """Builder và quản trị Modal Cấu hình Profile."""

    def __init__(self, master_app: Any):
        self.app = master_app

    def is_open(self) -> bool:
        dlg = getattr(self.app, "_profiles_window_instance", None)
        return bool(dlg and dlg.winfo_exists())

    def lift(self):
        dlg = getattr(self.app, "_profiles_window_instance", None)
        if dlg and dlg.winfo_exists():
            dlg.lift()
            dlg.focus_force()

    def open(self, profile_index: Optional[int] = None):
        return open_profiles_modal(self.app, profile_index)
