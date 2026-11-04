"""
Views package for MEGAMU Auto Train Dashboard.
Houses decoupled presentation builders and view controllers.
"""

from .moss_view import MossView
from .mirror_view import MirrorView
from .accounts_view import AccountsView
from .profiles_view import ProfilesView
from .logs_view import LogsView
from .ram_view import RamView
from .autologin_view import AutoLoginView

__all__ = [
    "MossView",
    "MirrorView",
    "AccountsView",
    "ProfilesView",
    "LogsView",
    "RamView",
    "AutoLoginView",
]
