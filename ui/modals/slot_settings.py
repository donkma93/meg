# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - SLOT SETTINGS MODAL DIALOG
Hộp thoại cấu hình chi tiết cho Slot (Map, Tọa độ, Sự kiện, Dọn rác).
"""

from typing import Callable, Optional, Dict, Any
import customtkinter as ctk
from ui.theme import Colors, Fonts

class SlotSettingsModal(ctk.CTkToplevel):
    """Cửa sổ cấu hình chi tiết cho 1 Slot (Modal popup tinh gọn)."""

    def __init__(
        self,
        parent,
        slot_idx: int,
        current_config: Dict[str, Any],
        maps_list: list,
        on_save: Optional[Callable[[int, Dict[str, Any]], None]] = None,
        on_open_advanced: Optional[Callable[[int], None]] = None
    ):
        super().__init__(parent)
        self.slot_idx = slot_idx
        self.config = dict(current_config)
        self.maps_list = maps_list or ["Lorencia", "Noria", "Devias", "Arena"]
        self.on_save = on_save
        self.on_open_advanced = on_open_advanced

        self.title(f"⚙️ Cài đặt Cấu hình - SLOT {slot_idx}")
        self.geometry("440x530")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_SURFACE)

        # Trở thành modal cửa sổ con
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # Tiêu đề
        h_frame = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=50, corner_radius=0)
        h_frame.pack(fill="x")
        h_frame.pack_propagate(False)

        ctk.CTkLabel(
            h_frame,
            text=f"Thiết lập Tự động cho Slot {self.slot_idx}",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.TEXT_MAIN
        ).pack(side="left", padx=16, pady=12)

        # Thân nội dung
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # 1. Chọn Map & Tọa độ
        ctk.CTkLabel(body, text="📍 BẢN ĐỒ & TỌA ĐỘ BÃI TRAIN", font=Fonts.BADGE, text_color=Colors.CYAN).pack(anchor="w", pady=(4, 6))

        row_map = ctk.CTkFrame(body, fg_color="transparent")
        row_map.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(row_map, text="Bản đồ:", font=Fonts.BODY, width=70, anchor="w").pack(side="left")
        self.map_var = ctk.StringVar(value=self.config.get("map", self.maps_list[0]))
        self.combo_map = ctk.CTkOptionMenu(
            row_map,
            values=self.maps_list,
            variable=self.map_var,
            fg_color=Colors.BG_CARD,
            button_color=Colors.BORDER_CARD,
            button_hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY,
            dropdown_font=Fonts.BODY,
            width=200
        )
        self.combo_map.pack(side="left", fill="x", expand=True)

        row_coords = ctk.CTkFrame(body, fg_color="transparent")
        row_coords.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(row_coords, text="Tọa độ X:", font=Fonts.BODY, width=70, anchor="w").pack(side="left")
        self.entry_x = ctk.CTkEntry(row_coords, width=60, font=Fonts.BODY, fg_color=Colors.BG_INPUT)
        self.entry_x.insert(0, str(self.config.get("x", 125)))
        self.entry_x.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row_coords, text="Tọa độ Y:", font=Fonts.BODY, width=70, anchor="w").pack(side="left")
        self.entry_y = ctk.CTkEntry(row_coords, width=60, font=Fonts.BODY, fg_color=Colors.BG_INPUT)
        self.entry_y.insert(0, str(self.config.get("y", 125)))
        self.entry_y.pack(side="left")

        # 2. Tự động bảo trì & Dọn rác
        ctk.CTkLabel(body, text="🛡️ TỰ ĐỘNG BẢO TRÌ NHÂN VẬT", font=Fonts.BADGE, text_color=Colors.CYAN).pack(anchor="w", pady=(4, 6))

        self.auto_repair_var = ctk.BooleanVar(value=self.config.get("auto_repair", True))
        ctk.CTkCheckBox(
            body,
            text="Tự động sửa chữa trang bị khi độ bền giảm",
            variable=self.auto_repair_var,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w", pady=4)

        self.auto_clean_var = ctk.BooleanVar(value=self.config.get("auto_clean_trash", True))
        ctk.CTkCheckBox(
            body,
            text="Tự động vứt bỏ rác vô giá trị trong hòm đồ",
            variable=self.auto_clean_var,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w", pady=4)

        # 3. Phân chia tham gia Sự kiện
        ctk.CTkLabel(body, text="🌌 THAM GIA SỰ KIỆN TỰ ĐỘNG", font=Fonts.BADGE, text_color=Colors.CYAN).pack(anchor="w", pady=(8, 6))

        self.mirror_var = ctk.BooleanVar(value=self.config.get("mirror_enabled", True))
        ctk.CTkCheckBox(
            body,
            text="Tự động đi Double Goer (Mirror) khi mở cửa (giờ chẵn :10)",
            variable=self.mirror_var,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w", pady=4)

        self.moss_var = ctk.BooleanVar(value=self.config.get("moss_enabled", True))
        ctk.CTkCheckBox(
            body,
            text="Tự động đi quay Moss Merchant khi mở cửa (:15)",
            variable=self.moss_var,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w", pady=4)

        # 4. Cài đặt chi tiết Reset, Point, Devil
        ctk.CTkButton(
            body,
            text="⭐ Cài Đặt Chi Tiết Reset, Point & Devil Square...",
            font=Fonts.BODY_BOLD,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#3b82f6",
            text_color="#60a5fa",
            height=32,
            command=self._handle_advanced
        ).pack(fill="x", pady=(12, 4))

        # Chân trang: Lưu & Hủy
        footer = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=54, corner_radius=0)
        footer.pack(fill="x", side="bottom")

        ctk.CTkButton(
            footer,
            text="Hủy bỏ",
            fg_color=Colors.BORDER_SUBTLE,
            hover_color=Colors.BORDER_CARD,
            font=Fonts.BODY_BOLD,
            width=90,
            height=32,
            command=self.destroy
        ).pack(side="right", padx=(6, 16), pady=11)

        ctk.CTkButton(
            footer,
            text="💾 Lưu cấu hình",
            fg_color=Colors.CYAN,
            hover_color="#0284c7",
            font=Fonts.BODY_BOLD,
            text_color="#000000",
            width=120,
            height=32,
            command=self._save_and_close
        ).pack(side="right", pady=11)

    def _handle_advanced(self):
        if self.on_open_advanced:
            self.on_open_advanced(self.slot_idx)

    def _save_and_close(self):
        try:
            x = int(self.entry_x.get().strip() or 125)
            y = int(self.entry_y.get().strip() or 125)
        except Exception:
            x, y = 125, 125

        saved_data = {
            "map": self.map_var.get(),
            "x": x,
            "y": y,
            "auto_repair": self.auto_repair_var.get(),
            "auto_clean_trash": self.auto_clean_var.get(),
            "mirror_enabled": self.mirror_var.get(),
            "moss_enabled": self.moss_var.get()
        }

        if self.on_save:
            self.on_save(self.slot_idx, saved_data)

        self.destroy()
