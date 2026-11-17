# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - PARTY SETTINGS & AUTO PT MODAL DIALOG
Hộp thoại cấu hình và điều khiển tính năng Tự Động Ghép Nhóm (Auto PT):
- Chỉ định 1 Slot làm Chủ PT (Leader) và các slot khác tự động vào nhóm.
- Gửi lệnh in-game /re auto [password] trực tiếp qua Direct Engine / Native Chat.
- Hiển thị bảng trạng thái Party thời gian thực từ RAM IL2CPP của từng tiến trình game.
- Hỗ trợ ghép nhóm ngay lập tức (Force Sync) hoặc tắt Auto PT (/re off).
"""

import time
import threading
from typing import Callable, Optional, Dict, Any, List
import customtkinter as ctk

from ui.theme import Colors, Fonts, Radii, Spacing
from ui.components.shell import make_action_button
from ui.components.dropdown import ModernDropdown
from services.party_manager import PartyManager


class PartySettingsModal(ctk.CTkToplevel):
    """Cửa sổ Modal cấu hình và quản lý Auto PT cho dàn account."""

    def __init__(
        self,
        parent,
        controllers: list,
        on_save_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.controllers = controllers
        self.on_save_callback = on_save_callback
        self.party_mgr = PartyManager.get_instance()

        self.title("🤝 Cấu Hình & Tự Động Ghép Party (Auto PT)")
        self.geometry("640x680")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_SURFACE)

        # Modal window configuration
        self.transient(parent)
        self.grab_set()

        # Window icon sync
        if hasattr(parent, "_setup_window_icon"):
            parent._setup_window_icon(self)
            self.after(100, lambda: parent._setup_window_icon(self))
        elif hasattr(parent, "_apply_window_icon"):
            parent._apply_window_icon(self)
            self.after(100, lambda: parent._apply_window_icon(self))

        self.slot_rows: Dict[int, Dict[str, Any]] = {}
        self._is_refreshing_roster = False

        self._build_ui()
        self._refresh_roster_async()

    def _build_ui(self):
        # 1. Header Frame
        h_frame = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=54, corner_radius=0)
        h_frame.pack(fill="x")
        h_frame.pack_propagate(False)

        title_box = ctk.CTkFrame(h_frame, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=8)

        ctk.CTkLabel(
            title_box,
            text="🤝 TỰ ĐỘNG GHÉP PARTY (AUTO PT)",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.CYAN
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Tự động đồng bộ nhóm 1 chủ + nhiều thành viên qua lệnh /re auto native",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")

        self.status_badge = ctk.CTkLabel(
            h_frame,
            text="Đang hoạt động" if self.party_mgr.is_enabled else "Đã tắt",
            font=Fonts.BADGE,
            text_color=Colors.GREEN if self.party_mgr.is_enabled else Colors.TEXT_DIM,
            fg_color=Colors.CHIP_OK_BG if self.party_mgr.is_enabled else Colors.BG_CARD,
            corner_radius=Radii.SM,
            padx=10,
            pady=4
        )
        self.status_badge.pack(side="right", padx=16, pady=12)

        # 2. Main Content Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # --- SECTION A: CẤU HÌNH AUTO PT ---
        cfg_card = ctk.CTkFrame(body, fg_color=Colors.BG_CARD, corner_radius=Radii.MD, border_width=1, border_color=Colors.BORDER_CARD)
        cfg_card.pack(fill="x", pady=(0, 10), padx=2)

        cfg_head = ctk.CTkFrame(cfg_card, fg_color="transparent")
        cfg_head.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(
            cfg_head,
            text="⚙️ THIẾT LẬP NHÓM & MẬT KHẨU",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        ).pack(side="left")

        # Row 1: Bật / Tắt Auto PT
        row1 = ctk.CTkFrame(cfg_card, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=4)

        self.var_enabled = ctk.BooleanVar(value=self.party_mgr.is_enabled)
        self.sw_enabled = ctk.CTkSwitch(
            row1,
            text="Bật tính năng Tự động Ghép & Duy trì Party (Auto PT)",
            variable=self.var_enabled,
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MAIN,
            progress_color=Colors.CYAN,
            command=self._on_toggle_enabled
        )
        self.sw_enabled.pack(side="left")

        # Row 2: Chọn Trưởng nhóm (Leader) & Mật khẩu
        row2 = ctk.CTkFrame(cfg_card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(8, 6))

        # Chọn Slot Leader
        ctk.CTkLabel(row2, text="Chủ nhóm (Leader):", font=Fonts.BODY, width=130, anchor="w").pack(side="left")
        
        slot_options = []
        for ctrl in self.controllers:
            s_idx = getattr(ctrl, "slot_idx", 0)
            c_name = getattr(ctrl, "char_name", "---")
            if c_name and c_name != "---":
                slot_options.append(f"Slot {s_idx:02d} ({c_name})")
            else:
                slot_options.append(f"Slot {s_idx:02d}")

        if not slot_options:
            slot_options = [f"Slot {i:02d}" for i in range(1, 11)]

        curr_leader_slot = self.party_mgr.leader_slot
        init_val = slot_options[0]
        for opt in slot_options:
            if f"Slot {curr_leader_slot:02d}" in opt:
                init_val = opt
                break

        self.leader_var = ctk.StringVar(value=init_val)
        self.combo_leader = ModernDropdown(
            row2,
            values=slot_options,
            variable=self.leader_var,
            width=170,
            height=28,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.BODY,
            command=self._on_leader_changed
        )
        self.combo_leader.pack(side="left", padx=(0, 20))

        # Mật khẩu Party
        ctk.CTkLabel(row2, text="Mật khẩu PT:", font=Fonts.BODY, width=80, anchor="w").pack(side="left")
        self.entry_pass = ctk.CTkEntry(
            row2,
            width=90,
            font=Fonts.BODY,
            fg_color=Colors.BG_INPUT,
            placeholder_text="1234"
        )
        self.entry_pass.insert(0, self.party_mgr.party_pass)
        self.entry_pass.pack(side="left")

        # Row 3: Checkbox tự động hồi phục
        row3 = ctk.CTkFrame(cfg_card, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(2, 10))

        self.var_reconnect = ctk.BooleanVar(value=self.party_mgr.auto_reconnect)
        ctk.CTkCheckBox(
            row3,
            text="Tự động mời lại khi thành viên hồi sinh, chuyển map hoặc relogin",
            variable=self.var_reconnect,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(side="left")

        # --- SECTION B: BẢNG TRẠNG THÁI PARTY TỪNG SLOT (RAM IL2CPP) ---
        roster_header = ctk.CTkFrame(body, fg_color="transparent")
        roster_header.pack(fill="x", pady=(4, 4), padx=2)

        ctk.CTkLabel(
            roster_header,
            text="📋 DANH SÁCH & TRẠNG THÁI PARTY HIỆN TẠI (RAM IL2CPP)",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        ).pack(side="left")

        self.btn_refresh_roster = make_action_button(
            roster_header,
            "🔄 Làm mới",
            self._refresh_roster_async,
            tone="ghost",
            height=24
        )
        self.btn_refresh_roster.pack(side="right")

        # Roster Scrollable Frame
        self.roster_frame = ctk.CTkScrollableFrame(
            body,
            fg_color=Colors.BG_CARD,
            corner_radius=Radii.MD,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            height=250
        )
        self.roster_frame.pack(fill="both", expand=True, padx=2, pady=(0, 6))

        # Tiêu đề cột bảng
        tbl_h = ctk.CTkFrame(self.roster_frame, fg_color=Colors.BG_HEADER, height=28, corner_radius=Radii.XS)
        tbl_h.pack(fill="x", pady=(0, 4))
        tbl_h.pack_propagate(False)

        ctk.CTkLabel(tbl_h, text="Slot", font=Fonts.CAPTION_BOLD, width=50, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=(10, 4))
        ctk.CTkLabel(tbl_h, text="Tên Nhân Vật", font=Fonts.CAPTION_BOLD, width=130, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_h, text="Vai Trò", font=Fonts.CAPTION_BOLD, width=100, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_h, text="Trạng Thái Party", font=Fonts.CAPTION_BOLD, width=160, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_h, text="Số TV", font=Fonts.CAPTION_BOLD, width=50, anchor="center", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)

        # Tạo sẵn các hàng slot
        for ctrl in self.controllers:
            s_idx = getattr(ctrl, "slot_idx", 0)
            self._create_slot_row(s_idx, ctrl)

        # Thông báo hoạt động
        self.lbl_msg = ctk.CTkLabel(
            body,
            text="",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_msg.pack(fill="x", padx=4, pady=(2, 4))

        # --- SECTION C: FOOTER / HÀNH ĐỘNG ---
        footer = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=54, corner_radius=0)
        footer.pack(fill="x", side="bottom")

        # Nút đóng
        ctk.CTkButton(
            footer,
            text="Đóng",
            fg_color=Colors.BORDER_SUBTLE,
            hover_color=Colors.BORDER_CARD,
            font=Fonts.BODY_BOLD,
            width=80,
            height=32,
            command=self.destroy
        ).pack(side="right", padx=(6, 16), pady=11)

        # Nút Lưu cấu hình
        ctk.CTkButton(
            footer,
            text="💾 Lưu Cấu Hình",
            fg_color=Colors.CYAN,
            hover_color="#0284c7",
            font=Fonts.BODY_BOLD,
            text_color="#000000",
            width=110,
            height=32,
            command=self._save_config
        ).pack(side="right", padx=6, pady=11)

        # Nút Tắt Auto PT (/re off)
        self.btn_disable = make_action_button(
            footer,
            "⏹ Tắt Auto PT",
            self._disable_all_party,
            tone="danger",
            height=32
        )
        self.btn_disable.pack(side="left", padx=(16, 6), pady=11)

        # Nút Ghép Party Ngay
        self.btn_sync_now = make_action_button(
            footer,
            "⚡ Ghép Party Ngay",
            self._force_sync_now,
            tone="purple",
            height=32
        )
        self.btn_sync_now.pack(side="left", padx=6, pady=11)

    def _create_slot_row(self, slot_idx: int, ctrl: Any):
        row = ctk.CTkFrame(self.roster_frame, fg_color=Colors.BG_SURFACE, height=32, corner_radius=Radii.XS)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        lbl_slot = ctk.CTkLabel(row, text=f"Slot {slot_idx:02d}", font=Fonts.BODY_BOLD, width=50, anchor="w")
        lbl_slot.pack(side="left", padx=(10, 4))

        c_name = getattr(ctrl, "char_name", "---")
        lbl_name = ctk.CTkLabel(row, text=c_name or "---", font=Fonts.BODY, width=130, anchor="w")
        lbl_name.pack(side="left", padx=4)

        is_lead = self.party_mgr.is_leader(slot_idx)
        role_text = "👑 Chủ Nhóm" if is_lead else "👥 Thành Viên"
        role_color = Colors.YELLOW if is_lead else Colors.BLUE
        lbl_role = ctk.CTkLabel(row, text=role_text, font=Fonts.BADGE, text_color=role_color, width=100, anchor="w")
        lbl_role.pack(side="left", padx=4)

        lbl_status = ctk.CTkLabel(row, text="Đang kiểm tra...", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM, width=160, anchor="w")
        lbl_status.pack(side="left", padx=4)

        lbl_count = ctk.CTkLabel(row, text="-/5", font=Fonts.BODY, width=50, anchor="center")
        lbl_count.pack(side="left", padx=4)

        self.slot_rows[slot_idx] = {
            "frame": row,
            "ctrl": ctrl,
            "lbl_name": lbl_name,
            "lbl_role": lbl_role,
            "lbl_status": lbl_status,
            "lbl_count": lbl_count
        }

    def _on_toggle_enabled(self):
        val = self.var_enabled.get()
        if val:
            self.status_badge.configure(text="Đang hoạt động", text_color=Colors.GREEN, fg_color=Colors.CHIP_OK_BG)
        else:
            self.status_badge.configure(text="Đã tắt", text_color=Colors.TEXT_DIM, fg_color=Colors.BG_CARD)

    def _on_leader_changed(self, choice: str):
        try:
            # Parse "Slot XX (...)"
            if choice.startswith("Slot "):
                s_num = int(choice.split()[1].split("(")[0])
                for s_idx, elements in self.slot_rows.items():
                    is_lead = (s_idx == s_num)
                    elements["lbl_role"].configure(
                        text="👑 Chủ Nhóm" if is_lead else "👥 Thành Viên",
                        text_color=Colors.YELLOW if is_lead else Colors.BLUE
                    )
        except Exception:
            pass

    def _get_selected_leader_slot(self) -> int:
        choice = self.leader_var.get()
        try:
            if choice.startswith("Slot "):
                return int(choice.split()[1].split("(")[0])
        except Exception:
            pass
        return 1

    def _save_config(self):
        lead_slot = self._get_selected_leader_slot()
        pwd = self.entry_pass.get().strip() or "1234"
        enabled = self.var_enabled.get()
        reconnect = self.var_reconnect.get()

        self.party_mgr.update_config(
            enabled=enabled,
            leader_slot=lead_slot,
            party_pass=pwd,
            auto_reconnect=reconnect
        )

        self.lbl_msg.configure(text=f"💾 Đã lưu cấu hình Auto PT: Chủ nhóm Slot {lead_slot}, Pass '{pwd}'.", text_color=Colors.GREEN)
        if self.on_save_callback:
            try:
                self.on_save_callback()
            except Exception:
                pass

    def _force_sync_now(self):
        """Kích hoạt đồng bộ ghép Party tức thì."""
        # Lưu cấu hình trước
        self._save_config()

        self.btn_sync_now.configure(state="disabled")
        self.lbl_msg.configure(text="⏳ Đang gửi lệnh /re auto cho Chủ nhóm và các Thành viên...", text_color=Colors.CYAN)

        def _on_complete(ok: bool, msg: str):
            def _ui_update():
                self.btn_sync_now.configure(state="normal")
                self.lbl_msg.configure(text=msg.replace("\n", " "), text_color=Colors.GREEN if ok else Colors.ROSE)
                self._refresh_roster_async()
            self.after(0, _ui_update)

        self.party_mgr.force_sync_party_async(self.controllers, on_complete=_on_complete)

    def _disable_all_party(self):
        """Gửi /re off cho tất cả slot."""
        self.btn_disable.configure(state="disabled")
        self.lbl_msg.configure(text="⏳ Đang gửi lệnh /re off cho toàn bộ slot...", text_color=Colors.AMBER)

        def _on_complete(ok: bool, msg: str):
            def _ui_update():
                self.btn_disable.configure(state="normal")
                self.lbl_msg.configure(text=msg, text_color=Colors.TEXT_MUTED)
                self._refresh_roster_async()
            self.after(0, _ui_update)

        self.party_mgr.disable_all_party_async(self.controllers, on_complete=_on_complete)

    def _refresh_roster_async(self):
        """Đọc RAM IL2CPP của tất cả các slot trong thread nền (Zero-Lag UI)."""
        if self._is_refreshing_roster:
            return
        self._is_refreshing_roster = True

        def _worker():
            results = {}
            for s_idx, elements in self.slot_rows.items():
                ctrl = elements.get("ctrl")
                if not ctrl:
                    continue
                info = self.party_mgr.read_slot_party_info(ctrl, max_cache_age=0.0)
                char_name = getattr(ctrl, "char_name", "---")
                results[s_idx] = {
                    "info": info,
                    "char_name": char_name
                }

            def _apply_ui():
                self._is_refreshing_roster = False
                for s_idx, data in results.items():
                    elements = self.slot_rows.get(s_idx)
                    if not elements:
                        continue

                    c_name = data.get("char_name") or "---"
                    elements["lbl_name"].configure(text=c_name)

                    info = data.get("info", {})
                    connected = info.get("connected", False)
                    in_pt = info.get("in_party", False)
                    is_lead = info.get("is_leader", False)
                    lead_name = info.get("leader_name", "")
                    m_count = info.get("member_count", 0)

                    if not connected:
                        elements["lbl_status"].configure(text="⚫ Chưa vào game", text_color=Colors.TEXT_DARK)
                        elements["lbl_count"].configure(text="-/5", text_color=Colors.TEXT_DARK)
                    elif in_pt:
                        if is_lead:
                            st_text = f"🟢 Chủ PT ({m_count}/5 TV)"
                        else:
                            st_text = f"🟢 Trong PT ({lead_name or 'Leader'})"
                        elements["lbl_status"].configure(text=st_text, text_color=Colors.GREEN)
                        elements["lbl_count"].configure(text=f"{m_count}/5", text_color=Colors.TEXT_MAIN)
                    else:
                        elements["lbl_status"].configure(text="⚪ Chưa vào PT", text_color=Colors.AMBER)
                        elements["lbl_count"].configure(text="0/5", text_color=Colors.TEXT_MUTED)

            self.after(0, _apply_ui)

        threading.Thread(target=_worker, name="PartyModal_RefreshRoster", daemon=True).start()
