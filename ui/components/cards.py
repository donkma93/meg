# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - COMPACT SLOT CARD COMPONENT (COMPACT DATA TABLE ROW)
Dòng bảng dữ liệu siêu tinh gọn (Chiều cao chỉ 34px - 1 hàng duy nhất):
Chuẩn Data Table với các cột cân đối tuyệt đối, không bị kéo dãn khổng lồ trên màn hình rộng.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts, Radii
from ui.components.icons import UiIconFactory
from ui.components.dropdown import ModernDropdown
from ui.components.tooltip import attach_tooltip


# Màu đặc trưng cho từng hệ nhân vật MU Online
CLASS_COLORS: Dict[str, tuple] = {
    "DK": ("#f87171", "#3b1219"),   # Dark Knight - Đỏ
    "BK": ("#f87171", "#3b1219"),
    "DW": ("#38bdf8", "#082f49"),   # Dark Wizard - Lam
    "SM": ("#38bdf8", "#082f49"),
    "ELF": ("#4ade80", "#052e1c"),  # Fairy Elf - Xanh lá
    "ME": ("#4ade80", "#052e1c"),
    "MG": ("#c084fc", "#2e1065"),   # Magic Gladiator - Tím
    "DM": ("#c084fc", "#2e1065"),
    "DL": ("#fbbf24", "#362005"),   # Dark Lord - Vàng hoàng kim
    "LE": ("#fbbf24", "#362005"),
    "SUM": ("#f472b6", "#3b0724"),  # Summoner - Hồng thạch anh
    "BS": ("#f472b6", "#3b0724"),
    "RF": ("#fb923c", "#381704"),   # Rage Fighter - Cam
    "FM": ("#fb923c", "#381704"),
    "GL": ("#818cf8", "#1e1b4b"),   # Grow Lancer - Chàm
    "RW": ("#2dd4bf", "#042f2e"),   # Rune Wizard - Ngọc lam
    "SLA": ("#cbd5e1", "#1e293b"),  # Slayer - Bạc
    "GC": ("#a3e635", "#1a2e05"),   # Gun Crasher - Chanh
    "KM": ("#e879f9", "#3b0764"),   # Kundun Mephis
    "LM": ("#38bdf8", "#082f49"),   # Lemuria
    "IK": ("#fca5a5", "#450a0a"),   # Illusion Knight
}


class CompactSlotCard(ctk.CTkFrame):
    """Một hàng của bảng dữ liệu Data Table siêu gọn gàng (Height = 34px)."""

    def __init__(
        self,
        parent,
        slot_idx: int,
        on_toggle_run: Optional[Callable[[int], None]] = None,
        on_open_settings: Optional[Callable[[int], None]] = None,
        on_change_process: Optional[Callable[[int, str], None]] = None,
        on_change_profile: Optional[Callable[[int, str], None]] = None,
        on_toggle_point: Optional[Callable[[int], None]] = None,
        on_open_point_config: Optional[Callable[[int], None]] = None,
        process_options: Optional[List[str]] = None,
        profile_options: Optional[List[str]] = None,
        on_change_delay: Optional[Callable[[int, float], None]] = None,
        **kwargs
    ):
        self.base_bg = "#0c1424" if slot_idx % 2 == 1 else "#0f192c"
        super().__init__(
            parent,
            fg_color=self.base_bg,
            border_width=0,
            corner_radius=0,
            height=32,
            **kwargs
        )
        self.slot_idx = slot_idx
        self.on_toggle_run = on_toggle_run
        self.on_open_settings = on_open_settings
        self.on_change_process = on_change_process
        self.on_change_profile = on_change_profile
        self.on_toggle_point = on_toggle_point
        self.on_open_point_config = on_open_point_config
        self.on_change_delay = on_change_delay
        self.process_options = process_options or ["--"]
        self.profile_options = profile_options or self.get_default_profile_options()

        self._is_running = False
        self._auto_add_point = False
        self._last_state: Dict[str, Any] = {}

        self._build_table_row()

    def _build_table_row(self):
        """Dòng bảng dữ liệu đích thực (Data Table Row) phẳng, chuẩn xác từng pixel, ngăn cách bằng đường kẻ mỏng."""
        self.pack_propagate(False)

        # Hairline divider 1px dưới đáy hàng để tạo lưới bảng chuẩn
        self.divider = ctk.CTkFrame(self, fg_color="#152033", height=1, corner_radius=0)
        self.divider.pack(fill="x", side="bottom")

        # 0. GHIM THAO TÁC BÊN PHẢI TRƯỚC TIÊN (176px)
        self.act_box = ctk.CTkFrame(self, fg_color="transparent")
        self.act_box.pack(side="right", padx=(2, 8))

        self.btn_point = ctk.CTkButton(
            self.act_box,
            image=UiIconFactory.get("star", color="#64748b", size=(11, 11)),
            compound="left",
            text="Point",
            width=54,
            height=24,
            corner_radius=Radii.XS,
            font=("Segoe UI", 9, "bold"),
            fg_color="#181c26",
            text_color="#64748b",
            hover_color="#242b3a",
            border_width=1,
            border_color="#2b3244",
            command=self._handle_toggle_point
        )
        self.btn_point.pack(side="left", padx=(0, 4))
        self.btn_point.bind("<Button-3>", lambda e: self._handle_open_point_config())
        attach_tooltip(self.btn_point, f"Slot {self.slot_idx}: Click để Bật/Tắt Tự Động Cộng Point (Chuột phải để mở Cài đặt)")

        self.btn_settings = ctk.CTkButton(
            self.act_box,
            image=UiIconFactory.get("gear", color="#94a3b8", size=(11, 11)),
            compound="left",
            text="Config",
            width=58,
            height=24,
            corner_radius=Radii.XS,
            font=("Segoe UI", 9, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            command=self._handle_open_settings
        )
        self.btn_settings.pack(side="left", padx=(0, 4))
        attach_tooltip(self.btn_settings, f"Mở & chỉnh sửa cấu hình Slot {self.slot_idx} tại Tab 02 Config")

        self.btn_toggle = ctk.CTkButton(
            self.act_box,
            image=UiIconFactory.get("play", color="#ffffff", size=(10, 10)),
            compound="left",
            text="BẬT",
            width=54,
            height=24,
            corner_radius=Radii.XS,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.GREEN,
            hover_color=Colors.GREEN_HOVER,
            command=self._handle_toggle_run
        )
        self.btn_toggle.pack(side="left")
        attach_tooltip(self.btn_toggle, f"Bật / Dừng Auto Train cho Slot {self.slot_idx}")

        # 1. Dải màu trạng thái bên trái (3px)
        self.accent = ctk.CTkFrame(self, fg_color=Colors.BORDER_SUBTLE, width=3, corner_radius=0)
        self.accent.pack(side="left", fill="y", padx=(0, 1))

        # 2. Cột STT (#01, #02...) (38px, căn giữa)
        self.badge_frame = ctk.CTkFrame(self, fg_color="transparent", width=38)
        self.badge_frame.pack(side="left", padx=1)
        self.badge_frame.pack_propagate(False)

        self.slot_num_lbl = ctk.CTkLabel(
            self.badge_frame,
            text=f"#{self.slot_idx:02d}",
            font=Fonts.BADGE,
            text_color="#38bdf8"
        )
        self.slot_num_lbl.pack(expand=True)

        # 3. Cột Hệ nhân vật (DK, DW...) (44px, căn giữa)
        self.class_chip = ctk.CTkFrame(self, fg_color="#182338", width=40, height=20, corner_radius=Radii.XS)
        self.class_chip.pack(side="left", padx=2)
        self.class_chip.pack_propagate(False)

        self.class_lbl = ctk.CTkLabel(
            self.class_chip,
            text="MU",
            font=("Segoe UI", 9, "bold"),
            text_color="#94a3b8"
        )
        self.class_lbl.pack(expand=True)
        attach_tooltip(self.class_chip, f"Hệ nhân vật Slot {self.slot_idx}")

        # 4. Cột Tiến trình Game / PID (Dropdown 180px gọn gàng)
        self.proc_var = ctk.StringVar(value="--")
        self.proc_combo = ModernDropdown(
            self,
            variable=self.proc_var,
            values=self.process_options,
            width=180,
            height=24,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=("Segoe UI", 10),
            command=self._handle_change_process,
            popup_min_width=220
        )
        self.proc_combo.pack(side="left", padx=4)
        attach_tooltip(self.proc_combo, "Cửa sổ game MEGAMU / PID gán cho slot này")

        # 5. Cột Cấu hình Train (Dropdown 105px)
        self.preset_var = ctk.StringVar(value="Config 1")
        self.preset_combo = ModernDropdown(
            self,
            variable=self.preset_var,
            values=self.profile_options,
            width=105,
            height=24,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=("Segoe UI", 10),
            command=self._handle_change_profile,
            popup_min_width=140
        )
        self.preset_combo.pack(side="left", padx=4)
        attach_tooltip(self.preset_combo, "Cấu hình bãi train & kỹ năng gán cho slot")

        # 6. Cột Cấp độ / RS (95px)
        self.level_lbl = ctk.CTkLabel(
            self,
            text="⭐ Lv ---",
            font=("Segoe UI", 10),
            text_color=Colors.TEXT_MAIN,
            width=95,
            anchor="w"
        )
        self.level_lbl.pack(side="left", padx=4)

        # 7. Cột Bản đồ & Tọa độ gộp chung (155px)
        self.map_coords_lbl = ctk.CTkLabel(
            self,
            text="📍 --- (--,--)",
            font=("Segoe UI", 10),
            text_color=Colors.TEXT_MAIN,
            width=155,
            anchor="w"
        )
        self.map_coords_lbl.pack(side="left", padx=4)
        self.map_lbl = self.map_coords_lbl
        self.coords_lbl = self.map_coords_lbl

        # 8. Cột Server (45px, căn giữa)
        self.srv_lbl = ctk.CTkLabel(
            self,
            text="Sv ---",
            font=("Segoe UI", 10),
            text_color=Colors.TEXT_MUTED,
            width=45,
            anchor="center"
        )
        self.srv_lbl.pack(side="left", padx=2)

        # 8.5 Cột Chờ ra bãi (s) (width=80px)
        self.delay_frame = ctk.CTkFrame(self, fg_color="transparent", width=80, height=24)
        self.delay_frame.pack(side="left", padx=3)
        self.delay_frame.pack_propagate(False)

        self.delay_var = ctk.StringVar(value="15")
        self.delay_entry = ctk.CTkEntry(
            self.delay_frame,
            textvariable=self.delay_var,
            width=42,
            height=22,
            font=("Segoe UI", 10, "bold"),
            fg_color="#0b1322",
            border_color="#1e293b",
            border_width=1,
            justify="center",
            text_color="#38bdf8"
        )
        self.delay_entry.pack(side="left", padx=(0, 2), pady=1)
        self.delay_entry.bind("<Return>", self._handle_delay_changed)
        self.delay_entry.bind("<FocusOut>", self._handle_delay_changed)

        self.delay_unit_lbl = ctk.CTkLabel(
            self.delay_frame,
            text="giây",
            font=("Segoe UI", 9),
            text_color=Colors.TEXT_MUTED
        )
        self.delay_unit_lbl.pack(side="left")
        attach_tooltip(self.delay_entry, f"Slot {self.slot_idx}: Thời gian chờ an toàn tại Lorencia trước khi ra lại bãi train (giây). Đổi số và nhấn Enter để lưu.")
        attach_tooltip(self.delay_frame, f"Slot {self.slot_idx}: Thời gian chờ an toàn tại Lorencia trước khi ra lại bãi train (giây).")

        # 9. Cột Trạng thái (Chip 100px)
        self.status_chip = ctk.CTkFrame(self, fg_color=Colors.BG_CHIP, width=100, height=24, corner_radius=Radii.XS)
        self.status_chip.pack(side="left", padx=4)
        self.status_chip.pack_propagate(False)

        self.status_dot = ctk.CTkFrame(self.status_chip, fg_color=Colors.TEXT_DIM, width=6, height=6, corner_radius=3)
        self.status_dot.pack(side="left", padx=(6, 4), pady=9)

        self.status_lbl = ctk.CTkLabel(
            self.status_chip,
            text="Sẵn sàng",
            font=("Segoe UI", 9, "bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.status_lbl.pack(side="left", padx=(0, 6))

        # 10. Đệm co giãn linh hoạt ở giữa (Flexible spacer)
        self.spacer = ctk.CTkFrame(self, fg_color="transparent")
        self.spacer.pack(side="left", fill="both", expand=True)

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
            cur_m = self._last_state.get("map_raw", "---")
            map_coords_txt = f"📍 {cur_m} ({c_xy})"
            if self._last_state.get("map_coords_txt") != map_coords_txt:
                self._last_state["map_coords_txt"] = map_coords_txt
                if hasattr(self, "map_coords_lbl") and self.map_coords_lbl.winfo_exists():
                    self.map_coords_lbl.configure(text=map_coords_txt)
            if srv and srv != "---" and hasattr(self, "srv_lbl") and self.srv_lbl.winfo_exists():
                self.srv_lbl.configure(text=f"Sv {srv}")
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

            # 1. Cập nhật Class Badge
            c_code_clean = (class_code or "").strip().upper()
            if self._last_state.get("class_code") != c_code_clean:
                self._last_state["class_code"] = c_code_clean
                if c_code_clean and c_code_clean in CLASS_COLORS:
                    fg_c, bg_c = CLASS_COLORS[c_code_clean]
                    self.class_chip.configure(fg_color=bg_c)
                    self.class_lbl.configure(text=c_code_clean, text_color=fg_c)
                elif c_code_clean:
                    self.class_chip.configure(fg_color="#182338")
                    self.class_lbl.configure(text=c_code_clean[:4], text_color=Colors.CYAN)
                else:
                    self.class_chip.configure(fg_color="#152038")
                    self.class_lbl.configure(text="MU", text_color="#64748b")

            # 2. Cập nhật Process Dropdown
            if pid:
                matched_opt = None
                for opt in getattr(self, "process_options", []):
                    if f"({pid})" in opt or f"(PID {pid})" in opt or opt.endswith(f"{pid})"):
                        matched_opt = opt
                        break
                if matched_opt:
                    disp_proc = matched_opt
                else:
                    c_tag = f"[{c_code_clean}] " if c_code_clean else ""
                    disp_proc = f"{c_tag}{c_name} (PID {pid})" if (c_name and c_name != "---") else f"MEGAMU (PID {pid})"
                if self.proc_var.get() != disp_proc:
                    self.proc_var.set(disp_proc)
            else:
                if self.proc_var.get() != "--":
                    self.proc_var.set("--")

            # 3. Cập nhật Profile
            cfg_name = state.get("profile")
            if cfg_name and self.preset_var.get() != cfg_name:
                self.preset_var.set(cfg_name)

            # 4. Cập nhật Level, Resets
            level = state.get("level", "---")
            resets = state.get("resets", 0)
            lvl_txt = f"⭐ Lv {level}" if level not in (None, "", "---") else "⭐ Lv ---"
            if resets:
                lvl_txt = f"{lvl_txt} (RS {resets})"
            if self._last_state.get("level_txt") != lvl_txt:
                self._last_state["level_txt"] = lvl_txt
                if self.level_lbl.winfo_exists():
                    self.level_lbl.configure(text=lvl_txt)

            # 5. Cập nhật Map & Tọa độ gộp chung
            map_name = state.get("map")
            clean_m = map_name.replace("Map:", "").strip() if map_name else ""
            m_txt = clean_m if (clean_m and clean_m != "---") else "---"
            self._last_state["map_raw"] = m_txt

            coords = state.get("coords", "--,--")
            c_xy = "--,--"
            if coords and coords.strip() and coords not in ("--,--", "--", "--, --"):
                parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
                if len(parts) >= 2:
                    c_xy = f"{parts[0]},{parts[1]}"
                else:
                    c_xy = coords.strip()

            map_coords_txt = f"📍 {m_txt} ({c_xy})"
            if self._last_state.get("map_coords_txt") != map_coords_txt:
                self._last_state["map_coords_txt"] = map_coords_txt
                if hasattr(self, "map_coords_lbl") and self.map_coords_lbl.winfo_exists():
                    self.map_coords_lbl.configure(text=map_coords_txt)

            # 6. Cập nhật Server
            srv_txt = f"Sv {srv}" if (srv and srv != "---") else "Sv ---"
            if hasattr(self, "srv_lbl") and self.srv_lbl.winfo_exists():
                self.srv_lbl.configure(text=srv_txt)

            # 7. Trạng thái chạy & chip status
            status = state.get("status", "Sẵn sàng")
            st_low = str(status).lower()
            if any(k in st_low for k in ("tự động đánh", "tu dong danh", "auto attack", "running", "đang chạy", "at spot", "tại bãi", "executando")):
                disp_status, color, chip_bg, dot = "Đang chạy", Colors.GREEN, Colors.CHIP_OK_BG, Colors.GREEN
            elif any(k in st_low for k in ("moving", "chạy ra bãi", "di chuyển", "movendo")):
                disp_status, color, chip_bg, dot = "Di chuyển", Colors.YELLOW, Colors.CHIP_WARN_BG, Colors.AMBER
            elif any(k in st_low for k in ("mất kết nối", "game đã đóng", "closed", "disconnect", "desconectado")):
                disp_status, color, chip_bg, dot = "Mất kết nối", Colors.ROSE, Colors.CHIP_ERR_BG, Colors.ROSE
            elif any(k in st_low for k in ("connected", "đã kết nối", "connected_status", "status_connected", "conectado")):
                disp_status, color, chip_bg, dot = "Đã kết nối", Colors.CYAN, Colors.CHIP_INFO_BG, Colors.CYAN
            elif any(k in st_low for k in ("stopped", "đã dừng", "parado")):
                disp_status, color, chip_bg, dot = "Đã dừng", Colors.TEXT_MUTED, Colors.BG_CHIP, Colors.TEXT_DIM
            elif any(k in st_low for k in ("idle", "chờ", "sẵn sàng")):
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

            # 8. Toggle RUNNING UI state
            is_running = bool(state.get("is_running", False))
            if self._is_running != is_running:
                self._is_running = is_running
                if is_running:
                    self.configure(fg_color="#0d2420")
                    self.accent.configure(fg_color=Colors.GREEN_SOFT)
                    if self.slot_num_lbl.winfo_exists():
                        self.slot_num_lbl.configure(text_color="#2dd4bf")
                    if self.btn_toggle.winfo_exists():
                        self.btn_toggle.configure(
                            text="DỪNG",
                            fg_color=Colors.ROSE,
                            hover_color=Colors.ROSE_HOVER,
                            image=UiIconFactory.get("stop", color="#ffffff", size=(10, 10))
                        )
                else:
                    self.configure(fg_color=self.base_bg)
                    self.accent.configure(fg_color=Colors.BORDER_SUBTLE)
                    if self.slot_num_lbl.winfo_exists():
                        self.slot_num_lbl.configure(text_color="#38bdf8")
                    if self.btn_toggle.winfo_exists():
                        self.btn_toggle.configure(
                            text="BẬT",
                            fg_color=Colors.GREEN,
                            hover_color=Colors.GREEN_HOVER,
                            image=UiIconFactory.get("play", color="#ffffff", size=(10, 10))
                        )
            # 9. Cập nhật trạng thái Point nếu có
            if "auto_add_point" in state:
                pt_on = bool(state["auto_add_point"])
                if self._auto_add_point != pt_on:
                    self.set_point_state(pt_on)

            # 10. Cập nhật Thời gian chờ ra bãi nếu có
            if "respawn_delay" in state:
                try:
                    if self.focus_get() != getattr(self, "delay_entry", None):
                        self.set_respawn_delay(state["respawn_delay"])
                except Exception:
                    self.set_respawn_delay(state["respawn_delay"])
        except Exception:
            pass

    def set_respawn_delay(self, val: Any):
        try:
            sec = int(float(val))
            if hasattr(self, "delay_var") and self.delay_var.get() != str(sec):
                self.delay_var.set(str(sec))
        except Exception:
            pass

    def _handle_delay_changed(self, event=None):
        if not hasattr(self, "delay_var"):
            return
        val_str = self.delay_var.get().strip()
        try:
            val = float(val_str)
            if val < 3.0:
                val = 3.0
                self.delay_var.set(str(int(val)))
            if self.on_change_delay:
                self.on_change_delay(self.slot_idx, val)
        except Exception:
            pass

    def set_point_state(self, enabled: bool):
        self._auto_add_point = bool(enabled)
        if hasattr(self, "btn_point") and self.btn_point.winfo_exists():
            if enabled:
                self.btn_point.configure(
                    fg_color="#075985",
                    text_color="#38bdf8",
                    border_color="#0284c7",
                    hover_color="#0369a1",
                    image=UiIconFactory.get("star", color="#38bdf8", size=(11, 11))
                )
            else:
                self.btn_point.configure(
                    fg_color="#181c26",
                    text_color="#64748b",
                    border_color="#2b3244",
                    hover_color="#242b3a",
                    image=UiIconFactory.get("star", color="#64748b", size=(11, 11))
                )

    def _handle_toggle_point(self):
        if self.on_toggle_point:
            self.on_toggle_point(self.slot_idx)

    def _handle_open_point_config(self):
        if self.on_open_point_config:
            self.on_open_point_config(self.slot_idx)

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
