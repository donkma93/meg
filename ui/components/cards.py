# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - COMPACT SLOT CARD COMPONENT
Thẻ điều khiển slot tối giản, đầy đủ chức năng, cập nhật In-Place 100% không render lại, chống giật lag.
"""

from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory

class CompactSlotCard(ctk.CTkFrame):
    """Thẻ điều khiển Slot siêu mượt, thiết kế phẳng hiện đại (Flat Minimalist Card)."""

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
            corner_radius=4,
            height=58,
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

        # Cột 1: Huy hiệu Slot
        self.badge_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BORDER_SUBTLE,
            width=50,
            corner_radius=2
        )
        self.badge_frame.pack(side="left", fill="y", padx=(6, 6), pady=6)
        self.badge_frame.pack_propagate(False)

        self.slot_num_lbl = ctk.CTkLabel(
            self.badge_frame,
            text=f"#{self.slot_idx:02d}",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        )
        self.slot_num_lbl.pack(expand=True)

        # Cột 2: Chọn Game (PID / Nhân vật)
        self.proc_var = ctk.StringVar(value="--")
        self.proc_combo = ctk.CTkOptionMenu(
            self,
            variable=self.proc_var,
            values=self.process_options,
            width=180,
            height=32,
            fg_color=Colors.BG_SURFACE,
            button_color=Colors.BORDER_CARD,
            button_hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY_BOLD,
            dropdown_font=Fonts.BODY,
            corner_radius=2,
            command=self._handle_change_process
        )
        self.proc_combo.pack(side="left", padx=(0, 6), pady=13)

        # Cột 3: Chọn Cấu hình chặng (Config 1 - 10)
        self.preset_var = ctk.StringVar(value="Config 1")
        self.preset_combo = ctk.CTkOptionMenu(
            self,
            variable=self.preset_var,
            values=self.profile_options,
            width=95,
            height=32,
            fg_color=Colors.BG_SURFACE,
            button_color=Colors.BORDER_CARD,
            button_hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY,
            dropdown_font=Fonts.BODY,
            corner_radius=2,
            command=self._handle_change_profile
        )
        self.preset_combo.pack(side="left", padx=(0, 8), pady=13)

        # Cột 4: Vị trí (Map & Tọa độ & Server)
        self.pos_frame = ctk.CTkFrame(self, fg_color="transparent", width=140)
        self.pos_frame.pack(side="left", fill="y", pady=6)
        self.pos_frame.pack_propagate(False)

        self.map_lbl = ctk.CTkLabel(
            self.pos_frame,
            text="Map: ---",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MAIN,
            anchor="w"
        )
        self.map_lbl.pack(fill="x", pady=(2, 0))

        self.coords_lbl = ctk.CTkLabel(
            self.pos_frame,
            text="Tọa độ: --,-- | Sv: ---",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.coords_lbl.pack(fill="x")

        # Cột 5: Trạng thái Hoạt động
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=6)

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="Sẵn sàng",
            font=Fonts.BODY,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.status_lbl.pack(fill="x", pady=(12, 0))

        # Cột 6: Nút Cài đặt (Gear) & Bật/Tắt Auto
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="right", fill="y", padx=(0, 8), pady=6)

        # Nút Cài đặt nhanh
        self.btn_settings = ctk.CTkButton(
            self.action_frame,
            image=UiIconFactory.get("gear", color=Colors.TEXT_MUTED, size=(14, 14)),
            text="",
            width=32,
            height=32,
            corner_radius=2,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            command=self._handle_open_settings
        )
        self.btn_settings.pack(side="right", padx=(4, 0), pady=12)

        # Nút Bật/Tắt Auto
        self.btn_toggle = ctk.CTkButton(
            self.action_frame,
            image=UiIconFactory.get("play", color="#ffffff", size=(12, 12)),
            compound="left",
            text="BẬT",
            width=80,
            height=32,
            corner_radius=2,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.GREEN,
            hover_color=Colors.GREEN_HOVER,
            command=self._handle_toggle_run
        )
        self.btn_toggle.pack(side="right", pady=12)

    @staticmethod
    def get_default_profile_options() -> List[str]:
        """Tải toàn bộ danh sách cấu hình Config từ đĩa (Config 1 - Config 10 hoặc tên tùy chỉnh)."""
        try:
            import json, os
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "autotrain_profiles.json")
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
        """Cập nhật danh sách tiến trình vào dropdown."""
        self.process_options = options
        self.proc_combo.configure(values=options)

    def set_profile_options(self, options: List[str]):
        """Cập nhật toàn bộ danh sách Config vào dropdown."""
        if options:
            self.profile_options = options
            self.preset_combo.configure(values=options)

    def stream_coords(self, coords: str, srv: str = ""):
        """Cập nhật tọa độ dạng luồng siêu mượt (Direct Streaming) không chạm vào bất kỳ phần nào khác của thẻ."""
        if not coords or coords in ("--,--", "--", "--, --"):
            c_xy = "--, --"
        else:
            parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
            c_xy = f"{parts[0]}, {parts[1]}" if len(parts) >= 2 else coords.strip()
        coords_txt = f"Tọa độ: {c_xy} | {srv}" if (srv and srv != "---") else f"Tọa độ: {c_xy}"
        if self._last_state.get("coords_txt") != coords_txt:
            self._last_state["coords_txt"] = coords_txt
            self.coords_lbl.configure(text=coords_txt)

    # --------------------------------------------------------------------------
    # CẬP NHẬT TRẠNG THÁI IN-PLACE (ZERO-LAG DIFFING)
    # --------------------------------------------------------------------------
    def update_state(self, state: Dict[str, Any]):
        """Cập nhật giao diện thẻ cực nhanh, chỉ thay đổi thuộc tính widget cần thiết."""
        # 1. Hiển thị tiến trình / Game
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

        # 2. Config preset
        cfg_name = state.get("profile")
        if cfg_name and self.preset_var.get() != cfg_name:
            self.preset_var.set(cfg_name)

        # 3. Map & Tọa độ & Server
        map_name = state.get("map")
        clean_m = map_name.replace("Map:", "").strip() if map_name else ""
        m_txt = f"Map: {clean_m}" if (clean_m and clean_m != "---") else "Map: ---"
        if self._last_state.get("map") != m_txt:
            self._last_state["map"] = m_txt
            self.map_lbl.configure(text=m_txt)

        coords = state.get("coords", "--,--")
        c_xy = "--, --"
        if coords and coords.strip() and coords not in ("--,--", "--", "--, --"):
            parts = [p.strip() for p in coords.replace("/", ",").split(",") if p.strip()]
            if len(parts) >= 2:
                c_xy = f"{parts[0]}, {parts[1]}"
            else:
                c_xy = coords.strip()
        coords_txt = f"Tọa độ: {c_xy} | {srv}" if srv and srv != "---" else f"Tọa độ: {c_xy}"
        if self._last_state.get("coords_txt") != coords_txt:
            self._last_state["coords_txt"] = coords_txt
            self.coords_lbl.configure(text=coords_txt)

        # 4. Trạng thái (Status text & color) - Chuẩn hóa chống nháy lag
        status = state.get("status", "Sẵn sàng")
        st_low = str(status).lower()
        if "tự động đánh" in st_low or "tu dong danh" in st_low or "auto attack" in st_low or "running" in st_low or "đang chạy" in st_low or "at spot" in st_low or "tại bãi" in st_low or "executando" in st_low:
            disp_status = "Đang chạy"
            color = Colors.GREEN
        elif "moving" in st_low or "chạy ra bãi" in st_low or "di chuyển" in st_low or "movendo" in st_low:
            disp_status = "Di chuyển"
            color = Colors.YELLOW
        elif "mất kết nối" in st_low or "game đã đóng" in st_low or "closed" in st_low or "disconnect" in st_low or "desconectado" in st_low:
            disp_status = "Mất kết nối"
            color = Colors.ROSE
        elif "connected" in st_low or "đã kết nối" in st_low or "connected_status" in st_low:
            disp_status = "Đã kết nối"
            color = "#38bdf8"
        elif "stopped" in st_low or "đã dừng" in st_low or "parado" in st_low:
            disp_status = "Đã dừng"
            color = Colors.TEXT_MUTED
        elif "idle" in st_low or "chờ" in st_low or "sẵn sàng" in st_low:
            disp_status = "Sẵn sàng"
            color = Colors.TEXT_MUTED
        else:
            disp_status = status
            color = Colors.TEXT_MUTED

        if self._last_state.get("disp_status") != disp_status:
            self._last_state["disp_status"] = disp_status
            self.status_lbl.configure(text=disp_status, text_color=color)

        # 5. Nút Bật/Tắt & Màu nền thẻ khi Auto Train
        is_running = bool(state.get("is_running", False))
        if self._is_running != is_running:
            self._is_running = is_running
            if is_running:
                self.configure(fg_color=Colors.SLOT_RUNNING_BG, border_color=Colors.SLOT_RUNNING_BORDER)
                self.badge_frame.configure(fg_color="#134e4a")
                self.slot_num_lbl.configure(text_color="#2dd4bf")
                self.btn_toggle.configure(
                    text="DỪNG",
                    fg_color=Colors.ROSE,
                    hover_color=Colors.ROSE_HOVER,
                    image=UiIconFactory.get("stop", color="#ffffff", size=(12, 12))
                )
            else:
                self.configure(fg_color=Colors.BG_CARD, border_color=Colors.BORDER_CARD)
                self.badge_frame.configure(fg_color=Colors.BORDER_SUBTLE)
                self.slot_num_lbl.configure(text_color=Colors.CYAN)
                self.btn_toggle.configure(
                    text="BẬT",
                    fg_color=Colors.GREEN,
                    hover_color=Colors.GREEN_HOVER,
                    image=UiIconFactory.get("play", color="#ffffff", size=(12, 12))
                )

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
