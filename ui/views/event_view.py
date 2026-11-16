# -*- coding: utf-8 -*-
"""
Compatibility shim.
Mirror/Moss đã tách thành:
  - ui.views.mirror_view.MirrorView
  - ui.views.moss_view.MossView
Giữ export helpers để code cũ import không gãy.
"""

from ui.views.moss_view import (  # noqa: F401
    MOSS_CAT_OPTIONS,
    moss_cat_name,
    moss_cat_id,
    MossView,
)
from ui.views.mirror_view import MirrorView  # noqa: F401

# Alias cũ (nếu chỗ nào còn import EventsView)
EventsView = MossView
