# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - MODULAR UI PACKAGE
"""

from ui.theme import Colors, Fonts
from ui.state import AppStateManager
from ui.components.icons import UiIconFactory
from ui.components.dropdown import ModernDropdown
from ui.components.cards import CompactSlotCard
from ui.views.train_view import TrainSlotsView
from ui.views.profiles_view import ProfilesConfigView
from ui.views.autologin_view import AutoLoginView
from ui.views.event_view import EventsView
from ui.views.logs_view import LogsAndToolsView
