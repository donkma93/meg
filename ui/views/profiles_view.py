# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - PROFILES & STAGES CONFIG VIEW
Quản lý cấu hình 10 Profile chặng train (Min/Max Level, Bản đồ, Tọa độ X/Y, Delay hồi sinh).
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory
from ui.components.dropdown import ModernDropdown

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]

class ProfilesConfigView(ctk.CTkFrame):
    """View cấu hình 10 Profile và các chặng đánh quái (Stages Table)."""

    def __init__(
        self,
        parent,
        maps_list: List[str],
        config_persistence_mgr: Any,
        on_profile_saved: Optional[Callable[[int], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.maps_list = maps_list or ["Lorencia", "Noria", "Devias", "Arena"]
        self.persistence_mgr = config_persistence_mgr
        self.on_profile_saved = on_profile_saved
        self.on_log = on_log

        self.current_profile_idx = 1
        self.editor_rows = []

        self._build_toolbar()
        self._build_stages_table()

        # Nạp dữ liệu ban đầu
        self.load_profile_into_editor(1)

    def _build_toolbar(self):
        """Thanh công cụ chọn Profile và các nút thao tác nhanh."""
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            head,
            text="Cấu hình bãi train",
            font=Fonts.SECTION,
            text_color=Colors.TEXT_MAIN
        ).pack(side="left")
        ctk.CTkLabel(
            head,
            text="10 profile · chặng theo level · delay hồi sinh",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM
        ).pack(side="right", pady=4)

        tb = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SURFACE,
            height=48,
            corner_radius=6,
            border_width=1,
            border_color=Colors.BORDER_CARD
        )
        tb.pack(fill="x", padx=12, pady=(6, 6))
        tb.pack_propagate(False)

        # Cột Trái: Chọn Profile & Delay
        left_f = ctk.CTkFrame(tb, fg_color="transparent")
        left_f.pack(side="left", fill="y", padx=8)

        ctk.CTkLabel(
            left_f,
            text="⚙️ Chọn Cấu Hình:",
            font=Fonts.BODY_BOLD,
            text_color=Colors.CYAN
        ).pack(side="left", padx=(0, 6), pady=12)

        self.profile_var = ctk.StringVar(value="Config 1")
        self.combo_profile = ModernDropdown(
            left_f,
            values=PROFILE_NAMES,
            variable=self.profile_var,
            width=110,
            height=28,
            fg_color=Colors.BG_CARD,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            command=self._on_profile_changed,
            font=Fonts.BODY_BOLD
        )
        self.combo_profile.pack(side="left", padx=4, pady=10)

        # Vách ngăn
        ctk.CTkFrame(left_f, fg_color=Colors.BORDER_CARD, width=1, height=20).pack(side="left", padx=8, pady=14)

        ctk.CTkLabel(
            left_f,
            text="⏳ Delay Hồi Sinh (giây):",
            font=Fonts.BODY,
            text_color=Colors.TEXT_MUTED
        ).pack(side="left", padx=(4, 4), pady=12)

        self.respawn_var = ctk.StringVar(value="15")
        self.respawn_entry = ctk.CTkEntry(
            left_f,
            textvariable=self.respawn_var,
            width=55,
            height=28,
            fg_color=Colors.BG_INPUT,
            border_color=Colors.BORDER_CARD,
            font=Fonts.BODY
        )
        self.respawn_entry.pack(side="left", padx=2, pady=10)

        # Cột Phải: Nút Lưu & Tải Lại
        right_f = ctk.CTkFrame(tb, fg_color="transparent")
        right_f.pack(side="right", fill="y", padx=8)

        self.btn_save = ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("check", color="#ffffff", size=(12, 12)),
            compound="left",
            text="Lưu Cấu Hình",
            font=Fonts.BODY_BOLD,
            fg_color=Colors.CYAN,
            text_color="#000000",
            hover_color="#0284c7",
            height=28,
            corner_radius=2,
            command=self.save_current_profile
        )
        self.btn_save.pack(side="right", padx=(4, 0), pady=10)

        self.btn_reload = ctk.CTkButton(
            right_f,
            image=UiIconFactory.get("refresh", color="#cbd5e1", size=(12, 12)),
            compound="left",
            text="Tải Lại",
            font=Fonts.BODY,
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            height=28,
            corner_radius=2,
            command=self.reload_from_file
        )
        self.btn_reload.pack(side="right", padx=4, pady=10)

    def _build_stages_table(self):
        """Khung bảng danh sách 10 chặng train."""
        container = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=4, border_width=1, border_color=Colors.BORDER_CARD)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Header Bảng
        hdr = ctk.CTkFrame(container, fg_color=Colors.BG_HEADER, height=36, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        cols = [
            ("CHẶNG", 60, "center"),
            ("MIN LV", 90, "center"),
            ("MAX LV", 90, "center"),
            ("BẢN ĐỒ (MAP)", 260, "center"),
            ("TỌA ĐỘ X", 110, "center"),
            ("TỌA ĐỘ Y", 110, "center"),
            ("GHI CHÚ / TRẠNG THÁI", 140, "center")
        ]
        for title, w, anc in cols:
            ctk.CTkLabel(
                hdr,
                text=title,
                width=w,
                anchor=anc,
                font=Fonts.BADGE,
                text_color=Colors.TEXT_MUTED
            ).pack(side="left", padx=4, pady=8)

        # Khung cuộn 10 dòng
        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self.editor_rows = []
        map_options = [""] + self.maps_list

        for i in range(1, 11):
            row = ctk.CTkFrame(scroll, fg_color=Colors.BG_SURFACE if i % 2 == 1 else "#0d131f", height=36, corner_radius=2)
            row.pack(fill="x", pady=2)

            # Cột 1: STT Chặng
            ctk.CTkLabel(
                row,
                text=f"#{i:02d}",
                width=60,
                font=Fonts.BADGE,
                text_color=Colors.CYAN
            ).pack(side="left", padx=4, pady=4)

            # Cột 2: Min LV
            min_var = ctk.StringVar(value="")
            min_ent = ctk.CTkEntry(
                row, textvariable=min_var, width=90, height=28,
                fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.BODY, justify="center"
            )
            min_ent.pack(side="left", padx=4, pady=4)

            # Cột 3: Max LV
            max_var = ctk.StringVar(value="")
            max_ent = ctk.CTkEntry(
                row, textvariable=max_var, width=90, height=28,
                fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.BODY, justify="center"
            )
            max_ent.pack(side="left", padx=4, pady=4)

            # Cột 4: Bản đồ
            map_var = ctk.StringVar(value="")
            map_combo = ModernDropdown(
                row,
                values=map_options,
                variable=map_var,
                width=260,
                height=28,
                fg_color=Colors.BG_CARD,
                border_color=Colors.BORDER_CARD,
                hover_color=Colors.BG_CARD_HOVER,
                font=Fonts.BODY
            )
            map_combo.pack(side="left", padx=4, pady=4)

            # Cột 5: Tọa độ X
            x_var = ctk.StringVar(value="")
            x_ent = ctk.CTkEntry(
                row, textvariable=x_var, width=110, height=28,
                fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.BODY, justify="center"
            )
            x_ent.pack(side="left", padx=4, pady=4)

            # Cột 6: Tọa độ Y
            y_var = ctk.StringVar(value="")
            y_ent = ctk.CTkEntry(
                row, textvariable=y_var, width=110, height=28,
                fg_color=Colors.BG_INPUT, border_color=Colors.BORDER_CARD, font=Fonts.BODY, justify="center"
            )
            y_ent.pack(side="left", padx=4, pady=4)

            # Cột 7: Nút xóa trắng dòng
            btn_clr = ctk.CTkButton(
                row,
                text="Xóa",
                width=60,
                height=26,
                fg_color=Colors.BG_CARD,
                hover_color="#450a0a",
                text_color=Colors.TEXT_MUTED,
                font=Fonts.CAPTION,
                command=lambda m=min_var, mx=max_var, mp=map_var, x=x_var, y=y_var: self._clear_row(m, mx, mp, x, y)
            )
            btn_clr.pack(side="left", padx=10, pady=4)

            self.editor_rows.append({
                "min": min_var,
                "max": max_var,
                "map": map_var,
                "x": x_var,
                "y": y_var
            })

    def _clear_row(self, min_var, max_var, map_var, x_var, y_var):
        min_var.set("")
        max_var.set("")
        map_var.set("")
        x_var.set("")
        y_var.set("")

    def _on_profile_changed(self, val: str):
        try:
            new_idx = int(val.replace("Config", "").strip())
            if new_idx != self.current_profile_idx:
                # Tự động lưu cấu hình cũ trước khi chuyển
                self.save_current_profile(silent=True)
                self.load_profile_into_editor(new_idx)
        except Exception:
            pass

    def load_profile_into_editor(self, profile_idx: int):
        """Nạp toàn bộ 10 chặng của Profile từ đĩa JSON vào bảng."""
        self.current_profile_idx = profile_idx
        self.profile_var.set(f"Config {profile_idx}")

        if not self.persistence_mgr:
            return

        cfg = self.persistence_mgr.load_single_profile(profile_idx)
        self.respawn_var.set(str(cfg.get("respawn_delay", 15)))

        stages = cfg.get("stages", [])
        for i, row in enumerate(self.editor_rows):
            if i < len(stages):
                st = stages[i]
                row["min"].set(str(st.get("min_level", "")))
                row["max"].set(str(st.get("max_level", "")))
                row["map"].set(str(st.get("map_name", "")))
                row["x"].set(str(st.get("x", "")))
                row["y"].set(str(st.get("y", "")))
            else:
                row["min"].set("")
                row["max"].set("")
                row["map"].set("")
                row["x"].set("")
                row["y"].set("")

    def save_current_profile(self, silent: bool = False):
        """Lưu lại chặng của Profile hiện tại vào file đĩa."""
        if not self.persistence_mgr:
            return

        idx = self.current_profile_idx
        cfg = self.persistence_mgr.load_single_profile(idx)

        try:
            respawn = int(self.respawn_var.get().strip())
        except Exception:
            respawn = 15
        cfg["respawn_delay"] = respawn

        new_stages = []
        for row in self.editor_rows:
            min_s = row["min"].get().strip()
            max_s = row["max"].get().strip()
            map_s = row["map"].get().strip()
            x_s = row["x"].get().strip()
            y_s = row["y"].get().strip()

            if min_s and max_s and map_s and x_s and y_s:
                try:
                    new_stages.append({
                        "min_level": int(min_s),
                        "max_level": int(max_s),
                        "map_name": map_s,
                        "x": int(x_s),
                        "y": int(y_s)
                    })
                except Exception:
                    pass

        cfg["stages"] = new_stages
        self.persistence_mgr.save_single_profile(idx, cfg)

        if not silent:
            msg = f"Đã lưu thành công Config {idx} ({len(new_stages)} chặng train) vào autotrain_profiles.json!"
            if self.on_log:
                self.on_log(msg, "SUCCESS")

        if self.on_profile_saved:
            self.on_profile_saved(idx)

    def reload_from_file(self):
        self.load_profile_into_editor(self.current_profile_idx)
        if self.on_log:
            self.on_log(f"Đã tải lại dữ liệu Config {self.current_profile_idx} từ file JSON.", "INFO")

