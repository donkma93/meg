# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - PARTY SETTINGS & MULTI-PT MODAL DIALOG
Hộp thoại cấu hình và điều khiển tính năng Tự Động Ghép Nhiều Party (Multi-PT):
- Hỗ trợ nhiều nhóm PT độc lập, mỗi nhóm có 1 Chủ PT (Leader) và các Thành viên (Members) riêng.
- Hỗ trợ 2 chế độ ghép:
  1. Tự động chia nhóm (5 acc/nhóm): Slot 1-5 vào PT 1, Slot 6-10 vào PT 2...
  2. Tùy chỉnh danh sách nhóm: Tự do chọn Chủ PT và gán thành viên cho từng nhóm.
- Gửi lệnh in-game /re auto [password] trực tiếp qua Direct Engine / Native Chat.
- Hiển thị bảng trạng thái Party thời gian thực từ RAM IL2CPP của từng tiến trình game.
- Hỗ trợ ghép toàn bộ các nhóm tức thì (Force Sync) hoặc tắt Auto PT (/re off).
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
    """Cửa sổ Modal cấu hình và quản lý Multi-PT cho dàn account."""

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

        self.title("🤝 Cấu Hình & Ghép Nhiều Party (Multi-PT)")
        self.geometry("700x760")
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
        self.party_card_elements: List[Dict[str, Any]] = []
        self._is_refreshing_roster = False

        # Chuẩn bị danh sách slot options
        self.slot_options: List[str] = []
        for ctrl in self.controllers:
            s_idx = getattr(ctrl, "slot_idx", 0)
            c_name = getattr(ctrl, "char_name", "---")
            if c_name and c_name != "---":
                self.slot_options.append(f"Slot {s_idx:02d} ({c_name})")
            else:
                self.slot_options.append(f"Slot {s_idx:02d}")

        if not self.slot_options:
            self.slot_options = [f"Slot {i:02d}" for i in range(1, 11)]

        # Danh sách cấu hình parties đang chỉnh sửa trên giao diện
        self.active_parties: List[Dict[str, Any]] = self.party_mgr.get_parties(self.controllers)

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
            text="🤝 TỰ ĐỘNG GHÉP NHIỀU PARTY (MULTI-PT)",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.CYAN
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Hỗ trợ nhiều nhóm PT độc lập, tự động chia 5 acc/nhóm hoặc tùy chỉnh Chủ PT từng nhóm",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")

        self.status_badge = ctk.CTkLabel(
            h_frame,
            text=f"Đang hoạt động ({len(self.active_parties)} nhóm)" if self.party_mgr.is_enabled else "Đã tắt",
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
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # --- SECTION A: CẤU HÌNH AUTO PT & CHẾ ĐỘ ---
        cfg_card = ctk.CTkFrame(body, fg_color=Colors.BG_CARD, corner_radius=Radii.MD, border_width=1, border_color=Colors.BORDER_CARD)
        cfg_card.pack(fill="x", pady=(0, 8), padx=2)

        # Row 1: Bật / Tắt Auto PT + Checkbox Auto Reconnect
        row1 = ctk.CTkFrame(cfg_card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(8, 4))

        self.var_enabled = ctk.BooleanVar(value=self.party_mgr.is_enabled)
        self.sw_enabled = ctk.CTkSwitch(
            row1,
            text="Bật tính năng Auto PT",
            variable=self.var_enabled,
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MAIN,
            progress_color=Colors.CYAN,
            command=self._on_toggle_enabled
        )
        self.sw_enabled.pack(side="left")

        self.var_reconnect = ctk.BooleanVar(value=self.party_mgr.auto_reconnect)
        ctk.CTkCheckBox(
            row1,
            text="Tự động mời lại khi hồi sinh/chuyển map",
            variable=self.var_reconnect,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        ).pack(side="right", padx=(10, 0))

        # Row 2: Chế độ chia nhóm & Mật khẩu mặc định
        row2 = ctk.CTkFrame(cfg_card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 8))

        ctk.CTkLabel(row2, text="Chế độ ghép:", font=Fonts.BODY, width=95, anchor="w").pack(side="left")

        mode_options = ["⚡ Tự động (5 acc/nhóm)", "⚙️ Tùy chỉnh danh sách PT"]
        current_mode_val = mode_options[0] if self.party_mgr.mode == "auto_5" else mode_options[1]
        self.var_mode = ctk.StringVar(value=current_mode_val)

        self.combo_mode = ModernDropdown(
            row2,
            values=mode_options,
            variable=self.var_mode,
            width=200,
            height=28,
            font=Fonts.BODY,
            command=self._on_mode_changed
        )
        self.combo_mode.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row2, text="Mật khẩu PT chung:", font=Fonts.BODY, width=130, anchor="w").pack(side="left")
        self.entry_pass = ctk.CTkEntry(
            row2,
            width=80,
            font=Fonts.BODY,
            fg_color=Colors.BG_INPUT,
            placeholder_text="1234"
        )
        self.entry_pass.insert(0, self.party_mgr.party_pass)
        self.entry_pass.pack(side="left")

        # --- SECTION B: DANH SÁCH CÁC NHÓM PARTY (MULTI-PT) ---
        grp_card = ctk.CTkFrame(body, fg_color=Colors.BG_CARD, corner_radius=Radii.MD, border_width=1, border_color=Colors.BORDER_CARD)
        grp_card.pack(fill="x", pady=(0, 8), padx=2)

        grp_header = ctk.CTkFrame(grp_card, fg_color="transparent")
        grp_header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            grp_header,
            text="👑 DANH SÁCH CÁC NHÓM PARTY ĐANG THIẾT LẬP",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        ).pack(side="left")

        # Nút thêm nhóm
        self.btn_add_group = make_action_button(
            grp_header,
            "➕ Thêm nhóm",
            self._on_add_party_clicked,
            tone="ghost",
            height=24
        )
        self.btn_add_group.pack(side="right", padx=(4, 0))

        # Nút tự động chia lại 5 acc
        self.btn_auto_split = make_action_button(
            grp_header,
            "⚡ Tự động chia 5",
            self._on_auto_split_clicked,
            tone="ghost",
            height=24
        )
        self.btn_auto_split.pack(side="right", padx=(4, 0))

        # Container chứa các Party Card
        self.parties_scroll = ctk.CTkScrollableFrame(
            grp_card,
            fg_color="transparent",
            height=130
        )
        self.parties_scroll.pack(fill="x", expand=False, padx=8, pady=(0, 6))

        # Render các party cards
        self._render_party_cards()

        # --- SECTION C: BẢNG TRẠNG THÁI PARTY TỪNG SLOT (RAM IL2CPP) ---
        roster_header = ctk.CTkFrame(body, fg_color="transparent")
        roster_header.pack(fill="x", pady=(2, 4), padx=2)

        ctk.CTkLabel(
            roster_header,
            text="📋 DANH SÁCH & TRẠNG THÁI PARTY THỜI GIAN THỰC (RAM IL2CPP)",
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
            height=210
        )
        self.roster_frame.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        # Tiêu đề cột bảng
        tbl_h = ctk.CTkFrame(self.roster_frame, fg_color=Colors.BG_HEADER, height=28, corner_radius=Radii.XS)
        tbl_h.pack(fill="x", pady=(0, 4))
        tbl_h.pack_propagate(False)

        ctk.CTkLabel(tbl_h, text="Slot", font=Fonts.CAPTION_BOLD, width=50, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=(10, 4))
        ctk.CTkLabel(tbl_h, text="Tên Nhân Vật", font=Fonts.CAPTION_BOLD, width=130, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_h, text="Nhóm & Vai Trò", font=Fonts.CAPTION_BOLD, width=130, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(tbl_h, text="Trạng Thái In-Game", font=Fonts.CAPTION_BOLD, width=170, anchor="w", text_color=Colors.TEXT_MUTED).pack(side="left", padx=4)
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
        self.lbl_msg.pack(fill="x", padx=4, pady=(2, 2))

        # --- SECTION D: FOOTER / HÀNH ĐỘNG ---
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
            width=115,
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

        # Nút Ghép Toàn Bộ PT Ngay
        self.btn_sync_now = make_action_button(
            footer,
            "⚡ Ghép Toàn Bộ PT Ngay",
            self._force_sync_now,
            tone="purple",
            height=32
        )
        self.btn_sync_now.pack(side="left", padx=6, pady=11)

    # --------------------------------------------------------------------------
    # RENDER DANH SÁCH PARTY CARDS
    # --------------------------------------------------------------------------
    def _render_party_cards(self):
        """Vẽ lại các thẻ Party trong scrollable container."""
        # Xóa các widget cũ
        for widget in self.parties_scroll.winfo_children():
            widget.destroy()

        self.party_card_elements.clear()
        is_auto_mode = ("Tự động" in self.var_mode.get())

        if not self.active_parties:
            ctk.CTkLabel(
                self.parties_scroll,
                text="Chưa có nhóm PT nào. Nhấn '⚡ Tự động chia 5' để tạo nhóm tự động!",
                font=Fonts.BODY,
                text_color=Colors.TEXT_MUTED
            ).pack(pady=10)
            return

        for idx, party in enumerate(self.active_parties):
            p_id = party.get("id", idx + 1)
            p_name = party.get("name", f"PT {p_id}")
            leader_slot = int(party.get("leader_slot", 1))
            member_slots = party.get("member_slots", [])
            p_pass = party.get("party_pass", self.entry_pass.get().strip() or "1234")

            p_frame = ctk.CTkFrame(
                self.parties_scroll,
                fg_color=Colors.BG_SURFACE,
                corner_radius=Radii.SM,
                border_width=1,
                border_color=Colors.BORDER_CARD
            )
            p_frame.pack(fill="x", pady=2, padx=2)

            # Row: Header & Điều khiển nhóm
            r_top = ctk.CTkFrame(p_frame, fg_color="transparent")
            r_top.pack(fill="x", padx=10, pady=(6, 4))

            # Label tên nhóm
            ctk.CTkLabel(
                r_top,
                text=f"👑 {p_name}",
                font=Fonts.BODY_BOLD,
                text_color=Colors.YELLOW,
                width=65,
                anchor="w"
            ).pack(side="left")

            # Dropdown chọn Leader
            ctk.CTkLabel(r_top, text="Chủ PT:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(4, 2))

            init_lead_str = self.slot_options[0]
            for opt in self.slot_options:
                if f"Slot {leader_slot:02d}" in opt:
                    init_lead_str = opt
                    break

            lead_var = ctk.StringVar(value=init_lead_str)
            combo_lead = ModernDropdown(
                r_top,
                values=self.slot_options,
                variable=lead_var,
                width=150,
                height=26,
                font=Fonts.BODY,
                command=lambda val, p_idx=idx: self._on_party_leader_changed(p_idx, val)
            )
            combo_lead.pack(side="left", padx=(2, 10))

            # Entry Thành viên
            ctk.CTkLabel(r_top, text="Thành viên:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 2))
            members_str = ", ".join(str(s) for s in member_slots)

            entry_members = ctk.CTkEntry(
                r_top,
                width=130,
                height=26,
                font=Fonts.BODY,
                fg_color=Colors.BG_INPUT,
                placeholder_text="vd: 2, 3, 4, 5"
            )
            entry_members.insert(0, members_str)
            if is_auto_mode:
                entry_members.configure(state="disabled", fg_color=Colors.BG_CARD)
            entry_members.pack(side="left", padx=(2, 10))

            # Pass nhóm
            ctk.CTkLabel(r_top, text="Pass:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 2))
            entry_pt_pass = ctk.CTkEntry(
                r_top,
                width=65,
                height=26,
                font=Fonts.BODY,
                fg_color=Colors.BG_INPUT
            )
            entry_pt_pass.insert(0, p_pass)
            entry_pt_pass.pack(side="left", padx=(2, 6))

            # Nút xóa nhóm (chỉ khả dụng ở chế độ custom và khi > 1 nhóm)
            if not is_auto_mode and len(self.active_parties) > 1:
                btn_del = make_action_button(
                    r_top,
                    "🗑",
                    lambda p_idx=idx: self._on_delete_party_clicked(p_idx),
                    tone="danger",
                    height=24
                )
                btn_del.pack(side="right", padx=(4, 0))

            self.party_card_elements.append({
                "party_id": p_id,
                "name": p_name,
                "lead_var": lead_var,
                "entry_members": entry_members,
                "entry_pass": entry_pt_pass,
                "frame": p_frame
            })

    def _on_mode_changed(self, choice: str):
        """Xử lý khi người dùng đổi chế độ Tự động / Tùy chỉnh."""
        if "Tự động" in choice:
            # Tự động chia lại 5 acc/nhóm
            self.active_parties = self.party_mgr.auto_split_parties(
                [getattr(c, "slot_idx", 0) for c in self.controllers if getattr(c, "slot_idx", 0) > 0],
                default_pass=self.entry_pass.get().strip() or "1234",
                max_per_pt=5
            )
        self._render_party_cards()
        self._update_roster_roles()

    def _on_auto_split_clicked(self):
        """Nút bấm chia nhanh 5 acc / nhóm."""
        self.var_mode.set("⚡ Tự động (5 acc/nhóm)")
        slots = [getattr(c, "slot_idx", 0) for c in self.controllers if getattr(c, "slot_idx", 0) > 0]
        self.active_parties = self.party_mgr.auto_split_parties(
            slots,
            default_pass=self.entry_pass.get().strip() or "1234",
            max_per_pt=5
        )
        self._render_party_cards()
        self._update_roster_roles()
        self.lbl_msg.configure(
            text=f"⚡ Đã tự động chia {len(slots)} slots thành {len(self.active_parties)} nhóm (5 acc/nhóm).",
            text_color=Colors.CYAN
        )

    def _on_add_party_clicked(self):
        """Thêm 1 nhóm PT tùy chỉnh mới."""
        self.var_mode.set("⚙️ Tùy chỉnh danh sách PT")
        new_id = len(self.active_parties) + 1

        # Tìm slot chưa làm leader
        used_leaders = {int(p.get("leader_slot", 0)) for p in self.active_parties}
        available_slot = 1
        for ctrl in self.controllers:
            s_idx = getattr(ctrl, "slot_idx", 0)
            if s_idx not in used_leaders:
                available_slot = s_idx
                break

        self.active_parties.append({
            "id": new_id,
            "name": f"PT {new_id}",
            "leader_slot": available_slot,
            "member_slots": [],
            "party_pass": self.entry_pass.get().strip() or "1234"
        })
        self._render_party_cards()
        self._update_roster_roles()

    def _on_delete_party_clicked(self, party_idx: int):
        """Xóa 1 nhóm PT."""
        if 0 <= party_idx < len(self.active_parties):
            self.active_parties.pop(party_idx)
            # Đánh lại ID
            for i, p in enumerate(self.active_parties, 1):
                p["id"] = i
                p["name"] = f"PT {i}"
            self._render_party_cards()
            self._update_roster_roles()

    def _on_party_leader_changed(self, party_idx: int, choice: str):
        """Khi chọn Leader mới cho 1 nhóm."""
        try:
            s_num = self._parse_slot_from_str(choice)
            if 0 <= party_idx < len(self.active_parties):
                old_leader = int(self.active_parties[party_idx].get("leader_slot", 1))
                self.active_parties[party_idx]["leader_slot"] = s_num

                is_auto = ("Tự động" in self.var_mode.get())
                if is_auto:
                    # Trong chế độ tự động: tập hợp các slot thuộc nhóm PT này
                    slots_in_pt = [old_leader] + [int(s) for s in self.active_parties[party_idx].get("member_slots", [])]
                    if s_num not in slots_in_pt:
                        slots_in_pt.append(s_num)
                    new_members = sorted([s for s in set(slots_in_pt) if s != s_num and s > 0])[:4]
                    self.active_parties[party_idx]["member_slots"] = new_members

                    if party_idx < len(self.party_card_elements):
                        entry = self.party_card_elements[party_idx]["entry_members"]
                        entry.configure(state="normal")
                        entry.delete(0, "end")
                        entry.insert(0, ", ".join(str(s) for s in new_members))
                        entry.configure(state="disabled")
                else:
                    current_members = [int(s) for s in self.active_parties[party_idx].get("member_slots", []) if int(s) != s_num]
                    if old_leader != s_num and old_leader > 0 and old_leader not in current_members:
                        current_members.insert(0, old_leader)
                    new_members = current_members[:4]
                    self.active_parties[party_idx]["member_slots"] = new_members
                    if party_idx < len(self.party_card_elements):
                        entry = self.party_card_elements[party_idx]["entry_members"]
                        entry.delete(0, "end")
                        entry.insert(0, ", ".join(str(s) for s in new_members))

                self._update_roster_roles()
        except Exception:
            pass

    def _parse_slot_from_str(self, choice: str) -> int:
        try:
            if choice.startswith("Slot "):
                return int(choice.split()[1].split("(")[0])
        except Exception:
            pass
        return 1

    def _get_current_parties_from_ui(self) -> List[Dict[str, Any]]:
        """Đọc toàn bộ cấu hình các nhóm từ các controls trên giao diện."""
        parties = []
        is_auto = ("Tự động" in self.var_mode.get())
        default_pwd = self.entry_pass.get().strip() or "1234"

        for idx, el in enumerate(self.party_card_elements):
            p_id = el["party_id"]
            p_name = el["name"]
            lead_choice = el["lead_var"].get()
            l_slot = self._parse_slot_from_str(lead_choice)
            pwd = el["entry_pass"].get().strip() or default_pwd

            if is_auto:
                if idx < len(self.active_parties):
                    m_slots = [int(s) for s in self.active_parties[idx].get("member_slots", []) if int(s) != l_slot][:4]
                else:
                    m_slots = []
            else:
                raw_members = el["entry_members"].get().replace(";", ",")
                m_slots = []
                for part in raw_members.split(","):
                    part = part.strip()
                    if part.isdigit():
                        s_int = int(part)
                        if s_int != l_slot and s_int > 0:
                            m_slots.append(s_int)
                m_slots = m_slots[:4]

            parties.append({
                "id": p_id,
                "name": p_name,
                "leader_slot": l_slot,
                "member_slots": m_slots,
                "party_pass": pwd
            })

        if not parties:
            slots = [getattr(c, "slot_idx", 0) for c in self.controllers if getattr(c, "slot_idx", 0) > 0]
            parties = self.party_mgr.auto_split_parties(slots, default_pass=default_pwd, max_per_pt=5)

        return parties

    # --------------------------------------------------------------------------
    # BẢNG ROSTER TRẠNG THÁI TỪNG SLOT
    # --------------------------------------------------------------------------
    def _create_slot_row(self, slot_idx: int, ctrl: Any):
        row = ctk.CTkFrame(self.roster_frame, fg_color=Colors.BG_SURFACE, height=32, corner_radius=Radii.XS)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        lbl_slot = ctk.CTkLabel(row, text=f"Slot {slot_idx:02d}", font=Fonts.BODY_BOLD, width=50, anchor="w")
        lbl_slot.pack(side="left", padx=(10, 4))

        c_name = getattr(ctrl, "char_name", "---")
        lbl_name = ctk.CTkLabel(row, text=c_name or "---", font=Fonts.BODY, width=130, anchor="w")
        lbl_name.pack(side="left", padx=4)

        role_info = self.party_mgr.get_slot_party_role(slot_idx, self.controllers)
        role_text = role_info["role_display"]
        role_color = Colors.YELLOW if role_info["is_leader"] else Colors.BLUE
        lbl_role = ctk.CTkLabel(row, text=role_text, font=Fonts.BADGE, text_color=role_color, width=130, anchor="w")
        lbl_role.pack(side="left", padx=4)

        lbl_status = ctk.CTkLabel(row, text="Đang kiểm tra...", font=Fonts.CAPTION, text_color=Colors.TEXT_DIM, width=170, anchor="w")
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

    def _update_roster_roles(self):
        """Cập nhật nhãn Vai trò trên bảng Roster theo cấu hình party hiện tại."""
        # Tạm lưu danh sách parties vào mgr để get_slot_party_role tính toán đúng
        current_parties = self._get_current_parties_from_ui()
        for s_idx, elements in self.slot_rows.items():
            # Tìm trong current_parties
            matched = False
            for p in current_parties:
                p_name = p.get("name", "PT")
                if s_idx == p.get("leader_slot"):
                    elements["lbl_role"].configure(text=f"👑 Chủ {p_name}", text_color=Colors.YELLOW)
                    matched = True
                    break
                elif s_idx in p.get("member_slots", []):
                    elements["lbl_role"].configure(text=f"👥 TV {p_name}", text_color=Colors.BLUE)
                    matched = True
                    break
            if not matched:
                elements["lbl_role"].configure(text="⚪ Chưa gán", text_color=Colors.TEXT_MUTED)

    def _on_toggle_enabled(self):
        val = self.var_enabled.get()
        if val:
            self.status_badge.configure(
                text=f"Đang hoạt động ({len(self.active_parties)} nhóm)",
                text_color=Colors.GREEN,
                fg_color=Colors.CHIP_OK_BG
            )
        else:
            self.status_badge.configure(text="Đã tắt", text_color=Colors.TEXT_DIM, fg_color=Colors.BG_CARD)

    def _save_config(self):
        """Lưu cấu hình Multi-PT vào file JSON."""
        parties = self._get_current_parties_from_ui()
        default_pwd = self.entry_pass.get().strip() or "1234"
        enabled = self.var_enabled.get()
        reconnect = self.var_reconnect.get()
        mode_val = "auto_5" if "Tự động" in self.var_mode.get() else "custom"

        lead_slot = parties[0]["leader_slot"] if parties else 1

        self.party_mgr.update_config(
            enabled=enabled,
            mode=mode_val,
            leader_slot=lead_slot,
            party_pass=default_pwd,
            auto_reconnect=reconnect,
            parties=parties
        )

        self.active_parties = parties
        self.status_badge.configure(
            text=f"Đang hoạt động ({len(parties)} nhóm)" if enabled else "Đã tắt"
        )
        self.lbl_msg.configure(
            text=f"💾 Đã lưu cấu hình Multi-PT: {len(parties)} nhóm, Chế độ '{'Tự động 5/nhóm' if mode_val == 'auto_5' else 'Tùy chỉnh'}'.",
            text_color=Colors.GREEN
        )
        self._update_roster_roles()

        if self.on_save_callback:
            try:
                self.on_save_callback()
            except Exception:
                pass

    def _force_sync_now(self):
        """Kích hoạt đồng bộ ghép Multi-PT tức thì."""
        # Lưu cấu hình trước
        self._save_config()

        self.btn_sync_now.configure(state="disabled")
        self.lbl_msg.configure(text="⏳ Đang gửi lệnh /re auto cho các Chủ nhóm và Thành viên...", text_color=Colors.CYAN)

        def _on_complete(ok: bool, msg: str):
            def _ui_update():
                self.btn_sync_now.configure(state="normal")
                # Format thông báo
                display_msg = msg.split("\n")[0] if "\n" in msg else msg
                self.lbl_msg.configure(text=display_msg, text_color=Colors.GREEN if ok else Colors.ROSE)
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
                info = self.party_mgr.read_slot_party_info(ctrl, max_cache_age=0.0, controllers=self.controllers)
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
                    role_text = info.get("role_display") or elements["lbl_role"].cget("text")
                    p_name = info.get("party_name", "PT")

                    if not connected:
                        elements["lbl_status"].configure(text="⚫ Chưa vào game", text_color=Colors.TEXT_DARK)
                        elements["lbl_count"].configure(text="-/5", text_color=Colors.TEXT_DARK)
                    elif in_pt:
                        if is_lead:
                            st_text = f"🟢 Chủ {p_name} ({m_count}/5 TV)"
                        else:
                            st_text = f"🟢 Trong {p_name} ({lead_name or 'Leader'})"
                        elements["lbl_status"].configure(text=st_text, text_color=Colors.GREEN)
                        elements["lbl_count"].configure(text=f"{m_count}/5", text_color=Colors.TEXT_MAIN)
                    else:
                        elements["lbl_status"].configure(text="⚪ Chưa vào PT", text_color=Colors.AMBER)
                        elements["lbl_count"].configure(text="0/5", text_color=Colors.TEXT_MUTED)

            self.after(0, _apply_ui)

        threading.Thread(target=_worker, name="PartyModal_RefreshRoster", daemon=True).start()
