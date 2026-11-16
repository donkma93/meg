# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - COMPACT SLOT CARD COMPONENT
Dense ops card with in-place updates (no re-render).
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.dropdown import ModernDropdown


class CompactSlotCard(ctk.CTkFrame):
    """Flat ops card for one Auto Train slot."""

    def __init__(
        self,
        parent,
        slot_idx: int,
        on_toggle_run: Optional[Callable[[int], None]] = None,
        on_open_settings: Optional[Callable[[int], None]] = None,
        on_change_process: Optional[Callable[[int, str], None]] = None,
        on_change_profile: Optional[Callable[[int, str], None]] = None,
        process_options: Optional[List[str]] = None,
        profile_options: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_CARD,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=Radii.MD,
            height=72,
            **kwargs
        )
        self.slot_idx = slot_idx
        self.on_toggle_run = on_toggle_run
        self.on_open_settings = on_open_settings
        self.on_change_process = on_change_process
        self.on_change_profile = on_change_profile
        self.process_options = process_options or ["--"]
        self.profile_options = profile_options or self.get_default_profile_options()

        self._is_running = False
        self._last_state: Dict[str, Any] = {}

        self._build_layout()

    def _build_layout(self):
        self.pack_propagate(False)

        # Accent strip
        self.accent = ctk.CTkFrame(self, fg_color=Colors.BORDER_SUBTLE, width=4, corner_radius=0)
        self.accent.pack(side="left", fill="y")

        # Slot badge
        self.badge_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_CHIP,
            width=54,
            corner_radius=Radii.SM
        )
        self.badge_frame.pack(side="left", fill="y", padx=(8, 8), pady=10)
        self.badge_frame.pack_propagate(False)

        self.slot_num_lbl = ctk.CTkLabel(
            self.badge_frame,
            text=f"#{self.slot_idx:02d}",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        )
        self.slot_num_lbl.pack(expand=True)

        # Process + profile
        mid_left = ctk.CTkFrame(self, fg_color="transparent")
        mid_left.pack(side="left", fill="y", pady=10)

        self.proc_var = ctk.StringVar(value="--")
        self.proc_combo = ModernDropdown(
            mid_left,
            variable=self.proc_var,
            values=self.process_options,
            width=188,
            height=28,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY_BOLD,
            command=self._handle_change_process
        )
        self.proc_combo.pack(anchor="w")

        row_cfg = ctk.CTkFrame(mid_left, fg_color="transparent")
        row_cfg.pack(fill="x", pady=(4, 0))

        self.preset_var = ctk.StringVar(value="Config 1")
        self.preset_combo = ModernDropdown(
            row_cfg,
            variable=self.preset_var,
            values=self.profile_options,
            width=108,
            height=24,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.CAPTION,
            command=self._handle_change_profile
        )
        self.preset_combo.pack(side="left")

        self.level_lbl = ctk.CTkLabel(
            row_cfg,
            text="Lv ---",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_DIM,
            width=70,
            anchor="w"
        )
        self.level_lbl.pack(side="left", padx=(8, 0))

        # Map / coords
        self.pos_frame = ctk.CTkFrame(self, fg_color="transparent", width=168)
        self.pos_frame.pack(side="left", fill="y", padx=(10, 6), pady=10)
        self.pos_frame.pack_propagate(False)

        self.map_lbl = ctk.CTkLabel(
            self.pos_frame,
            text="Map: ---",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MAIN,
            anchor="w"
        )
        self.map_lbl.pack(fill="x", pady=(4, 0))

        self.coords_lbl = ctk.CTkLabel(
            self.pos_frame,
            text="XY: --,--  ·  Sv ---",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.coords_lbl.pack(fill="x")

        # Status chip
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=10)

        self.status_chip = ctk.CTkFrame(
            self.status_frame,
            fg_color=Colors.BG_CHIP,
            corner_radius=Radii.SM,
            height=28,
            width=120
        )
        self.status_chip.pack(anchor="w", pady=(14, 0))
        self.status_chip.pack_propagate(False)

        self.status_dot = ctk.CTkFrame(self.status_chip, fg_color=Colors.TEXT_DIM, width=8, height=8, corner_radius=4)
        self.status_dot.pack(side="left", padx=(10, 6), pady=10)

        self.status_lbl = ctk.CTkLabel(
            self.status_chip,
            text="Sẵn sàng",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.status_lbl.pack(side="left", padx=(0, 12), pady=4)

        # Actions
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="right", fill="y", padx=(0, 10), pady=10)

        self.btn_settings = ctk.CTkButton(
            self.action_frame,
            image=UiIconFactory.get("gear", color=Colors.TEXT_MUTED, size=(14, 14)),
            text="",
            width=34,
            height=34,
            corner_radius=Radii.SM,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            command=self._handle_open_settings
        )
        self.btn_settings.pack(side="right", padx=(6, 0), pady=9)

        self.btn_toggle = ctk.CTkButton(
            self.action_frame,
            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)),
            compound="left",
            text="BẬT",
            width=86,
            height=34,
            corner_radius=Radii.SM,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.GREEN,
            hover_color=Colors.GREEN_HOVER,
            command=self._handle_toggle_run
        )
        self.btn_toggle.pack(side="right", pady=9)

    @staticmethod
    def get_default_profile_options() -> List[str]:
        try:
            import json, os
            cfg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config",
                "autotrain_profiles.json"
            )
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles = data.get("profiles", {})
                opts = []
                for k in sorted(profiles.keys(), key=lambda x: int(x) if x.isdigit() else 999):
                    p_name = profiles[k].get("name") or f"Config {k}"
                    opts.append(p_name)
                if opts:
                    return opts
        except Exception:
            pass
        return [f"Config {i}" for i in range(1, 11)]

    def set_process_options(self, options: List[str]):
        # Tránh configure lại dropdown nếu danh sách không đổi (nguyên nhân lag)
        new_opts = list(options or ["--"])
        if new_opts == getattr(self, "process_options", None):
            return
        self.process_options = new_opts
        self.proc_combo.configure(values=new_opts)

    def set_profile_options(self, options: List[str]):
        if not options:
            return
        new_opts = list(options)
        if new_opts == getattr(self, "profile_options", None):
            return
        self.profile_options = new_opts
        self.preset_combo.configure(values=new_opts)

    def stream_coords(self, coords: str, srv: str = ""):
        try:
            if not self.winfo_exists():
                return
            if not coords or coords in ("--,--", "--", "--, --"):
                c_xy = "--,--"
            else:
                parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
                c_xy = f"{parts[0]},{parts[1]}" if len(parts) >= 2 else coords.strip()
            coords_txt = f"XY: {c_xy}  ·  Sv {srv}" if (srv and srv != "---") else f"XY: {c_xy}"
            if self._last_state.get("coords_txt") != coords_txt:
                self._last_state["coords_txt"] = coords_txt
                if self.coords_lbl.winfo_exists():
                    self.coords_lbl.configure(text=coords_txt)
        except Exception:
            pass

    def update_state(self, state: Dict[str, Any]):
        try:
            if not self.winfo_exists():
                return

            c_name = state.get("char_name", "---")
            pid = state.get("assigned_pid")
            class_code = state.get("class_code", "")
            srv = state.get("server", "---")

            if pid:
                c_tag = f"[{class_code}] " if class_code else ""
                disp_proc = f"{c_tag}{c_name} ({pid})" if c_name != "---" else f"MEGAMU ({pid})"
                if self.proc_var.get() != disp_proc:
                    self.proc_var.set(disp_proc)
            elif c_name and c_name != "---":
                if self.proc_var.get() != c_name:
                    self.proc_var.set(c_name)

            cfg_name = state.get("profile")
            if cfg_name and self.preset_var.get() != cfg_name:
                self.preset_var.set(cfg_name)

            level = state.get("level", "---")
            resets = state.get("resets", 0)
            lvl_txt = f"Lv {level}" if level not in (None, "", "---") else "Lv ---"
            if resets:
                lvl_txt = f"{lvl_txt} · RS {resets}"
            if self._last_state.get("level_txt") != lvl_txt:
                self._last_state["level_txt"] = lvl_txt
                if self.level_lbl.winfo_exists():
                    self.level_lbl.configure(text=lvl_txt)

            map_name = state.get("map")
            clean_m = map_name.replace("Map:", "").strip() if map_name else ""
            m_txt = f"Map: {clean_m}" if (clean_m and clean_m != "---") else "Map: ---"
            if self._last_state.get("map") != m_txt:
                self._last_state["map"] = m_txt
                if self.map_lbl.winfo_exists():
                    self.map_lbl.configure(text=m_txt)

            coords = state.get("coords", "--,--")
            c_xy = "--,--"
            if coords and coords.strip() and coords not in ("--,--", "--", "--, --"):
                parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
                if len(parts) >= 2:
                    c_xy = f"{parts[0]},{parts[1]}"
                else:
                    c_xy = coords.strip()
            coords_txt = f"XY: {c_xy}  ·  Sv {srv}" if srv and srv != "---" else f"XY: {c_xy}"
            if self._last_state.get("coords_txt") != coords_txt:
                self._last_state["coords_txt"] = coords_txt
                if self.coords_lbl.winfo_exists():
                    self.coords_lbl.configure(text=coords_txt)

            status = state.get("status", "Sẵn sàng")
            st_low = str(status).lower()
            if "tự động đánh" in st_low or "tu dong danh" in st_low or "auto attack" in st_low or "running" in st_low or "đang chạy" in st_low or "at spot" in st_low or "tại bãi" in st_low or "executando" in st_low:
                disp_status, color, chip_bg, dot = "Đang chạy", Colors.GREEN, Colors.CHIP_OK_BG, Colors.GREEN
            elif "moving" in st_low or "chạy ra bãi" in st_low or "di chuyển" in st_low or "movendo" in st_low:
                disp_status, color, chip_bg, dot = "Di chuyển", Colors.YELLOW, Colors.CHIP_WARN_BG, Colors.AMBER
            elif "mất kết nối" in st_low or "game đã đóng" in st_low or "closed" in st_low or "disconnect" in st_low or "desconectado" in st_low:
                disp_status, color, chip_bg, dot = "Mất kết nối", Colors.ROSE, Colors.CHIP_ERR_BG, Colors.ROSE
            elif "connected" in st_low or "đã kết nối" in st_low or "connected_status" in st_low or "status_connected" in st_low or "conectado" in st_low:
                disp_status, color, chip_bg, dot = "Đã kết nối", Colors.CYAN, Colors.CHIP_INFO_BG, Colors.CYAN
            elif "stopped" in st_low or "đã dừng" in st_low or "parado" in st_low:
                disp_status, color, chip_bg, dot = "Đã dừng", Colors.TEXT_MUTED, Colors.BG_CHIP, Colors.TEXT_DIM
            elif "idle" in st_low or "chờ" in st_low or "sẵn sàng" in st_low:
                disp_status, color, chip_bg, dot = "Sẵn sàng", Colors.TEXT_MUTED, Colors.BG_CHIP, Colors.TEXT_DIM
            else:
                disp_status, color, chip_bg, dot = status, Colors.TEXT_MUTED, Colors.BG_CHIP, Colors.TEXT_DIM

            if self._last_state.get("disp_status") != disp_status:
                self._last_state["disp_status"] = disp_status
                if self.status_lbl.winfo_exists():
                    self.status_lbl.configure(text=disp_status, text_color=color)
                if self.status_chip.winfo_exists():
                    self.status_chip.configure(fg_color=chip_bg)
                if self.status_dot.winfo_exists():
                    self.status_dot.configure(fg_color=dot)

            is_running = bool(state.get("is_running", False))
            if self._is_running != is_running:
                self._is_running = is_running
                if is_running:
                    self.configure(fg_color=Colors.SLOT_RUNNING_BG, border_color=Colors.SLOT_RUNNING_BORDER)
                    self.accent.configure(fg_color=Colors.GREEN_SOFT)
                    if self.badge_frame.winfo_exists():
                        self.badge_frame.configure(fg_color="#134e4a")
                    if self.slot_num_lbl.winfo_exists():
                        self.slot_num_lbl.configure(text_color="#2dd4bf")
                    if self.btn_toggle.winfo_exists():
                        self.btn_toggle.configure(
                            text="DỪNG",
                            fg_color=Colors.ROSE,
                            hover_color=Colors.ROSE_HOVER,
                            image=UiIconFactory.get("stop", color="#ffffff", size=(12, 12))
                        )
                else:
                    self.configure(fg_color=Colors.BG_CARD, border_color=Colors.BORDER_CARD)
                    self.accent.configure(fg_color=Colors.BORDER_SUBTLE)
                    if self.badge_frame.winfo_exists():
                        self.badge_frame.configure(fg_color=Colors.BG_CHIP)
                    if self.slot_num_lbl.winfo_exists():
                        self.slot_num_lbl.configure(text_color=Colors.CYAN)
                    if self.btn_toggle.winfo_exists():
                        self.btn_toggle.configure(
                            text="BẬT",
                            fg_color=Colors.GREEN,
                            hover_color=Colors.GREEN_HOVER,
                            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12))
                        )
        except Exception:
            pass

    def _handle_toggle_run(self):
        if self.on_toggle_run:
            self.on_toggle_run(self.slot_idx)

    def _handle_open_settings(self):
        if self.on_open_settings:
            self.on_open_settings(self.slot_idx)

    def _handle_change_process(self, val: str):
        if self.on_change_process:
            self.on_change_process(self.slot_idx, val)

    def _handle_change_profile(self, val: str):
        if self.on_change_profile:
            self.on_change_profile(self.slot_idx, val)
