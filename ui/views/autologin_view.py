# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - AUTO LOGIN VIEW (MODERN COMPACT FLAT ARCHITECTURE)
Giao diện quản lý tài khoản & AutoLogin hiện đại, các thẻ tài khoản phẳng tối giản (Compact Card).
Trạng thái PID và Online/Offline nhảy In-Place 100%, không tải lại bảng, chuyển tab siêu tốc 0ms.
"""

from typing import Callable, Optional, Dict, Any, List
import time
import tkinter as tk
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui.components.icons import UiIconFactory
from ui.components.dropdown import ModernDropdown
from ui.components.shell import bind_mousewheel_to_scrollable

class CompactAccountCard(ctk.CTkFrame):
    """Thẻ tài khoản phẳng tối giản, hiện đại, hiển thị 2 dòng thông tin gọn gàng và cập nhật In-Place 100%."""

    def __init__(
        self,
        parent,
        account: Dict[str, Any],
        stt: int,
        controllers: list,
        on_toggle_enabled: Optional[Callable[[Dict[str, Any], bool], None]] = None,
        on_launch: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_send_login: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_close: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_edit: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        on_copy_username: Optional[Callable[[str], None]] = None,
        on_prompt_change_category: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_change_server: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_change_slot: Optional[Callable[[Dict[str, Any], str], None]] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_CARD,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=6,
            height=58,
            **kwargs
        )
        self.account = account
        self.username = str(account.get("username", "")).strip()
        self.stt = stt
        self.controllers = controllers
        self.on_toggle_enabled = on_toggle_enabled
        self.on_launch = on_launch
        self.on_send_login = on_send_login
        self.on_close = on_close
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_copy_username = on_copy_username
        self.on_prompt_change_category = on_prompt_change_category
        self.on_change_server = on_change_server
        self.on_change_slot = on_change_slot

        self._last_state_key = (False, None, None, None, None)
        self._is_online = False
        self._build_card()

    def _build_card(self):
        self.pack_propagate(False)

        # 1. Cột 1: Checkbox [✓] và Huy hiệu STT
        self.cb_var = ctk.BooleanVar(value=self.account.get("enabled", True))
        self.cb = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.cb_var,
            width=20,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=2,
            fg_color=Colors.CYAN,
            hover_color="#0284c7",
            command=self._handle_toggle
        )
        self.cb.pack(side="left", padx=(10, 4), pady=18)

        self.badge_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BORDER_SUBTLE,
            width=46,
            corner_radius=2
        )
        self.badge_frame.pack(side="left", fill="y", padx=(0, 10), pady=8)
        self.badge_frame.pack_propagate(False)

        self.stt_lbl = ctk.CTkLabel(
            self.badge_frame,
            text=f"#{self.stt:02d}",
            font=Fonts.BADGE,
            text_color=Colors.CYAN
        )
        self.stt_lbl.pack(expand=True)

        # 2. Cột 2: Tên Tài khoản & Nhân vật (Sử dụng tk.Frame nhẹ để không tạo canvas CustomTkinter thừa)
        self.col_user = tk.Frame(self, bg=Colors.BG_CARD, width=160)
        self.col_user.pack(side="left", fill="y", pady=6)
        self.col_user.pack_propagate(False)

        has_pwd = bool(self.account.get("password"))
        u_disp = f"{self.username} 🔑" if has_pwd else self.username
        self.user_lbl = ctk.CTkLabel(
            self.col_user,
            text=u_disp,
            font=Fonts.BODY_BOLD,
            text_color=Colors.CYAN if has_pwd else Colors.TEXT_MAIN,
            anchor="w"
        )
        self.user_lbl.pack(fill="x", pady=(2, 0))

        c_name = self.account.get("character") or "(Mặc định)"
        self.char_lbl = ctk.CTkLabel(
            self.col_user,
            text=f"NV: {c_name}",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.char_lbl.pack(fill="x")

        # 3. Cột 3: Server & Gán vào Slot
        self.col_srv = tk.Frame(self, bg=Colors.BG_CARD, width=130)
        self.col_srv.pack(side="left", fill="y", pady=6)
        self.col_srv.pack_propagate(False)

        srv_val = int(self.account.get("server", 3))
        self.srv_var = ctk.StringVar(value=f"Server {srv_val}")
        self.srv_combo = ModernDropdown(
            self.col_srv,
            values=[f"Server {k}" for k in range(1, 9)],
            variable=self.srv_var,
            width=96,
            height=24,
            fg_color=Colors.BG_SURFACE,
            border_color=Colors.BORDER_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.CAPTION,
            command=self._handle_change_server
        )
        self.srv_combo.pack(anchor="w", pady=(1, 2))

        pref_slot = self.account.get("preferred_slot")
        slot_disp = f"Gán: Slot #{pref_slot:02d}" if (pref_slot and pref_slot > 0) else "Gán: Tự động"
        self.slot_lbl = ctk.CTkLabel(
            self.col_srv,
            text=slot_disp,
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.slot_lbl.pack(fill="x")

        # 4. Cột 4: Phân loại nhóm mục đích
        self.col_cat = tk.Frame(self, bg=Colors.BG_CARD, width=115)
        self.col_cat.pack(side="left", fill="y", pady=6)
        self.col_cat.pack_propagate(False)

        cur_cat = (self.account.get("category") or "Chung").strip()
        self.cat_lbl = ctk.CTkLabel(
            self.col_cat,
            text=f"[{cur_cat}]",
            font=Fonts.CAPTION,
            text_color=Colors.CYAN,
            anchor="w"
        )
        self.cat_lbl.pack(fill="x", pady=(16, 0))

        # 5. Cột 5: Trạng thái & PID (Cập nhật In-Place)
        self.col_st = tk.Frame(self, bg=Colors.BG_CARD)
        self.col_st.pack(side="left", fill="both", expand=True, padx=4, pady=6)

        self.status_lbl = ctk.CTkLabel(
            self.col_st,
            text="⚪ Offline",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        self.status_lbl.pack(fill="x", pady=(15, 0))

        # 6. Cột 6: Nút Thao Tác (Cài đặt, Đóng, Đăng nhập)
        self.col_act = tk.Frame(self, bg=Colors.BG_CARD)
        self.col_act.pack(side="right", fill="y", padx=(0, 8), pady=8)

        self._column_frames = [self.col_user, self.col_srv, self.col_cat, self.col_st, self.col_act]

        # Nút Cài đặt (Gear)
        self.btn_edit = ctk.CTkButton(
            self.col_act,
            image=UiIconFactory.get("gear", color=Colors.TEXT_MUTED, size=(14, 14)),
            text="",
            width=32,
            height=32,
            corner_radius=2,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            command=self._handle_edit
        )
        self.btn_edit.pack(side="right", padx=(4, 0))

        # Nút Đóng game client (🛑)
        self.btn_close = ctk.CTkButton(
            self.col_act,
            image=UiIconFactory.get("stop", color="#f87171", size=(12, 12)),
            text="",
            width=32,
            height=32,
            corner_radius=2,
            state="disabled",
            fg_color="#181c26",
            hover_color="#7f1d1d",
            command=self._handle_close
        )
        self.btn_close.pack(side="right", padx=(4, 0))

        # Nút Mở & Login (🚀 Login / 🟢 Online)
        self.btn_launch = ctk.CTkButton(
            self.col_act,
            image=UiIconFactory.get("bolt", color="#000000", size=(12, 12)),
            compound="left",
            text="LOGIN",
            width=85,
            height=32,
            corner_radius=2,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.CYAN,
            hover_color="#0284c7",
            text_color="#000000",
            command=self._handle_launch
        )
        self.btn_launch.pack(side="right")

        self._bind_context_menu()

    def update_state(
        self,
        is_online: bool,
        pid: Optional[int] = None,
        live_srv: Optional[int] = None,
        live_slot: Optional[str] = None,
        status_override: Optional[str] = None
    ) -> bool:
        """Cập nhật trạng thái PID và màu sắc in-place (0ms, không lag, không giật màn hình)."""
        try:
            if not self.winfo_exists():
                return False
            state_key = (is_online, pid, live_srv, live_slot, status_override)
            if self._last_state_key == state_key:
                return False
            self._last_state_key = state_key
            self._is_online = bool(is_online)

            if status_override:
                if self.status_lbl.winfo_exists():
                    self.status_lbl.configure(text=status_override, text_color=Colors.AMBER)
            elif is_online:
                pid_txt = f"🟢 PID {pid} (Online)" if pid else "🟢 Online"
                if self.status_lbl.winfo_exists():
                    self.status_lbl.configure(text=pid_txt, text_color=Colors.GREEN)
                if self.btn_launch.winfo_exists():
                    self.btn_launch.configure(
                        text="ONLINE",
                        state="disabled",
                        fg_color="#064e3b",
                        text_color_disabled="#34d399",
                        image=UiIconFactory.get("bolt", color="#34d399", size=(12, 12))
                    )
                if self.btn_close.winfo_exists():
                    self.btn_close.configure(
                        state="normal",
                        fg_color="#450a0a",
                        hover_color="#7f1d1d"
                    )
                self.configure(fg_color="#0f2327", border_color="#14b8a6")
                if self.badge_frame.winfo_exists():
                    self.badge_frame.configure(fg_color="#134e4a")
                if self.stt_lbl.winfo_exists():
                    self.stt_lbl.configure(text_color="#2dd4bf")
                for col_f in getattr(self, "_column_frames", []):
                    try:
                        col_f.configure(bg="#0f2327")
                    except Exception:
                        pass
            else:
                if self.status_lbl.winfo_exists():
                    self.status_lbl.configure(text="⚪ Offline", text_color=Colors.TEXT_MUTED)
                if self.btn_launch.winfo_exists():
                    self.btn_launch.configure(
                        text="LOGIN",
                        state="normal",
                        fg_color=Colors.CYAN,
                        text_color="#000000",
                        image=UiIconFactory.get("bolt", color="#000000", size=(12, 12))
                    )
                if self.btn_close.winfo_exists():
                    self.btn_close.configure(
                        state="disabled",
                        fg_color="#181c26"
                    )
                self.configure(fg_color=Colors.BG_CARD, border_color=Colors.BORDER_CARD)
                if self.badge_frame.winfo_exists():
                    self.badge_frame.configure(fg_color=Colors.BORDER_SUBTLE)
                if self.stt_lbl.winfo_exists():
                    self.stt_lbl.configure(text_color=Colors.CYAN)
                for col_f in getattr(self, "_column_frames", []):
                    try:
                        col_f.configure(bg=Colors.BG_CARD)
                    except Exception:
                        pass

            if live_srv and live_srv > 0:
                srv_txt = f"Server {live_srv}"
                if hasattr(self, "srv_var") and self.srv_var.get() != srv_txt:
                    self.srv_var.set(srv_txt)

            if live_slot:
                slot_txt = f"Gán: {live_slot}"
                if self.slot_lbl.winfo_exists() and self.slot_lbl.cget("text") != slot_txt:
                    self.slot_lbl.configure(text=slot_txt)
            return True
        except Exception:
            return False

    def _bind_context_menu(self):
        ctx_targets = [self, self.stt_lbl, self.user_lbl, self.char_lbl, self.slot_lbl, self.cat_lbl, self.status_lbl]
        if hasattr(self, "srv_combo"):
            ctx_targets.append(self.srv_combo)
        for w in ctx_targets:
            try:
                w.bind("<Button-3>", self._show_context_menu)
            except Exception:
                pass

    def _show_context_menu(self, event):
        try:
            menu = tk.Menu(
                self,
                tearoff=0,
                bg="#1a202c",
                fg="#f8fafc",
                activebackground="#6366f1",
                activeforeground="#ffffff",
                font=("Segoe UI", 10)
            )
            pid = self.account.get("last_pid")
            is_on = bool(pid and self.btn_launch.cget("state") == "disabled")
            if is_on:
                menu.add_command(label=f"🟢 Đang online ({self.username} - PID: {pid})", state="disabled")
            else:
                menu.add_command(
                    label=f"🚀 Mở & Login ({self.username})",
                    command=self._handle_launch
                )
            slot_pref = self.account.get("preferred_slot")
            slot_target = f"Slot #{slot_pref:02d}" if slot_pref else "Tự động"
            menu.add_command(
                label=f"⚡ Gửi Login vào {slot_target}",
                command=self._handle_send_login
            )
            menu.add_command(
                label=f"🛑 Đóng Client ({self.username})",
                command=self._handle_close,
                state="normal" if is_on else "disabled"
            )
            menu.add_separator()
            menu.add_command(
                label=f"⚙️ Sửa tài khoản '{self.username}'...",
                command=self._handle_edit
            )
            menu.add_command(
                label=f"🏷️ Đổi nhóm phân loại...",
                command=self._handle_prompt_category
            )
            menu.add_command(
                label=f"🗑️ Xóa tài khoản '{self.username}'",
                command=self._handle_delete
            )
            menu.add_separator()
            menu.add_command(
                label="📋 Sao chép tên tài khoản",
                command=self._handle_copy_user
            )
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def _handle_toggle(self):
        val = bool(self.cb_var.get())
        self.account["enabled"] = val
        if self.on_toggle_enabled:
            self.on_toggle_enabled(self.account, val)

    def _handle_change_server(self, new_val: str):
        try:
            s_num = int(new_val.replace("Server ", "").strip())
            self.account["server"] = s_num
        except Exception:
            pass
        if self.on_change_server:
            self.on_change_server(self.account, new_val)

    def _handle_launch(self):
        if self.on_launch:
            pref = self.account.get("preferred_slot")
            slot_arg = str(pref) if pref else "Tự động"
            self.on_launch(self.account, slot_arg)

    def _handle_send_login(self):
        if self.on_send_login:
            pref = self.account.get("preferred_slot")
            slot_arg = str(pref) if pref else "Tự động"
            self.on_send_login(self.account, slot_arg)

    def _handle_close(self):
        if self.on_close:
            self.on_close(self.account)

    def _handle_edit(self):
        if self.on_edit:
            self.on_edit(self.account)

    def _handle_delete(self):
        if self.on_delete:
            self.on_delete(self.username)

    def _handle_copy_user(self):
        if self.on_copy_username:
            self.on_copy_username(self.username)

    def _handle_prompt_category(self):
        if self.on_prompt_change_category:
            self.on_prompt_change_category(self.account)


class AutoLoginView(ctk.CTkFrame):
    """Giao diện quản lý tài khoản & AutoLogin hiện đại, phẳng, siêu mượt."""

    def __init__(
        self,
        parent,
        account_mgr,
        controllers: list,
        on_launch_all: Optional[Callable[[], None]] = None,
        on_close_all: Optional[Callable[[], None]] = None,
        on_add_account: Optional[Callable[[], None]] = None,
        on_delete_selected: Optional[Callable[[], None]] = None,
        on_change_exe: Optional[Callable[[], None]] = None,
        on_arrange_layout: Optional[Callable[[str], None]] = None,
        on_launch_single: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_send_login: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_close_single: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_edit_account: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_delete_account: Optional[Callable[[str], None]] = None,
        on_toggle_account: Optional[Callable[[Dict[str, Any], bool], None]] = None,
        on_change_category: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_change_character: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_change_server: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_change_slot: Optional[Callable[[Dict[str, Any], str], None]] = None,
        on_prompt_add_category: Optional[Callable[[], None]] = None,
        on_prompt_change_category: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_filter_category: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.account_mgr = account_mgr
        self.controllers = controllers
        self.on_launch_all = on_launch_all
        self.on_close_all = on_close_all
        self.on_add_account = on_add_account
        self.on_delete_selected = on_delete_selected
        self.on_change_exe = on_change_exe
        self.on_arrange_layout = on_arrange_layout
        self.on_launch_single = on_launch_single
        self.on_send_login = on_send_login
        self.on_close_single = on_close_single
        self.on_edit_account = on_edit_account
        self.on_delete_account = on_delete_account
        self.on_toggle_account = on_toggle_account
        self.on_change_category = on_change_category
        self.on_change_character = on_change_character
        self.on_change_server = on_change_server
        self.on_change_slot = on_change_slot
        self.on_prompt_add_category = on_prompt_add_category
        self.on_prompt_change_category = on_prompt_change_category
        self.on_filter_category = on_filter_category

        self.cards: Dict[str, CompactAccountCard] = {}
        self.current_category = "Tất cả"
        self.search_keyword = ""
        self._log_visible = True

        self._build_header()
        self._build_toolbar()
        self._build_cards_container()
        self._build_log_drawer()

        # Nạp dữ liệu ban đầu
        if self.account_mgr and getattr(self.account_mgr, "accounts", None):
            self.load_accounts(self.account_mgr.accounts)

    def _build_header(self):
        """Header bar trên cùng."""
        hdr = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, height=40, corner_radius=2, border_width=1, border_color=Colors.BORDER_CARD)
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        hdr.pack_propagate(False)

        left_h = ctk.CTkFrame(hdr, fg_color="transparent")
        left_h.pack(side="left", fill="y", padx=10)

        ctk.CTkLabel(
            left_h,
            text="🔑 MEGAMU AUTO LOGIN",
            font=Fonts.HEADER_TITLE,
            text_color=Colors.PURPLE
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            left_h,
            text="• Quản lý tài khoản & Khởi chạy đăng nhập client",
            font=Fonts.HEADER_SUB,
            text_color=Colors.TEXT_MUTED
        ).pack(side="left")

        right_h = ctk.CTkFrame(hdr, fg_color="transparent")
        right_h.pack(side="right", fill="y", padx=10)

        import os
        exe_file = os.path.basename(getattr(self.account_mgr, 'exe_path', '') or 'MEGAMU.exe')
        self.lbl_exe = ctk.CTkLabel(
            right_h,
            text=f"📁 Exe: {exe_file}",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_exe.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            right_h,
            text="📁 Đổi Exe",
            width=70,
            height=26,
            corner_radius=2,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            font=Fonts.CAPTION,
            command=self._handle_change_exe
        ).pack(side="left")

    def _build_toolbar(self):
        """Thanh tác vụ 2 hàng tinh tế."""
        tb = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, corner_radius=2, border_width=1, border_color=Colors.BORDER_CARD)
        tb.pack(fill="x", padx=12, pady=(0, 4))

        # Hàng 1: Nút vận hành chính
        row1 = ctk.CTkFrame(tb, fg_color="transparent", height=36)
        row1.pack(fill="x", padx=8, pady=(6, 4))

        r1_left = ctk.CTkFrame(row1, fg_color="transparent")
        r1_left.pack(side="left", fill="y")

        self.btn_launch_all = ctk.CTkButton(
            r1_left,
            image=UiIconFactory.get("bolt", color="#ffffff", size=(12, 12)),
            compound="left",
            text="🚀 MỞ & LOGIN TẤT CẢ",
            font=Fonts.BODY_BOLD,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            height=28,
            corner_radius=2,
            command=self._handle_launch_all
        )
        self.btn_launch_all.pack(side="left", padx=(0, 6))

        self.btn_close_all = ctk.CTkButton(
            r1_left,
            image=UiIconFactory.get("stop", color="#f87171", size=(12, 12)),
            compound="left",
            text="🛑 ĐÓNG GAME",
            font=Fonts.BODY_BOLD,
            fg_color="#450a0a",
            hover_color="#7f1d1d",
            border_width=1,
            border_color="#ef4444",
            text_color="#fca5a5",
            height=28,
            corner_radius=2,
            command=self._handle_close_all
        )
        self.btn_close_all.pack(side="left", padx=(0, 6))

        self.btn_add = ctk.CTkButton(
            r1_left,
            image=UiIconFactory.get("plus", color="#ffffff", size=(12, 12)),
            compound="left",
            text="➕ Thêm Tài Khoản",
            font=Fonts.BODY,
            fg_color="#065f46",
            hover_color="#047857",
            height=28,
            corner_radius=2,
            command=self._handle_add_account
        )
        self.btn_add.pack(side="left", padx=(0, 6))

        self.btn_del_selected = ctk.CTkButton(
            r1_left,
            image=UiIconFactory.get("trash", color="#f87171", size=(12, 12)),
            compound="left",
            text="Xóa Đã Chọn",
            font=Fonts.BODY,
            fg_color="#2b1517",
            hover_color="#450a0a",
            border_width=1,
            border_color="#7f1d1d",
            text_color="#fca5a5",
            height=28,
            corner_radius=2,
            command=self._handle_delete_selected
        )
        self.btn_del_selected.pack(side="left", padx=(0, 6))

        self.btn_select_all = ctk.CTkButton(
            r1_left,
            text="✓ Tất Cả",
            font=Fonts.CAPTION,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            text_color=Colors.CYAN,
            width=62,
            height=28,
            corner_radius=2,
            command=lambda: self.select_all_accounts(True)
        )
        self.btn_select_all.pack(side="left", padx=(0, 4))

        self.btn_deselect_all = ctk.CTkButton(
            r1_left,
            text="☐ Bỏ Chọn",
            font=Fonts.CAPTION,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            text_color=Colors.TEXT_MUTED,
            width=68,
            height=28,
            corner_radius=2,
            command=lambda: self.select_all_accounts(False)
        )
        self.btn_deselect_all.pack(side="left", padx=(0, 8))

        ctk.CTkFrame(r1_left, fg_color=Colors.BORDER_CARD, width=1, height=18).pack(side="left", padx=(0, 8))

        # Bố cục lưới
        ctk.CTkLabel(r1_left, text="📐 Lưới:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.arrange_var = ctk.StringVar(value="2x2")
        self.combo_arrange = ctk.CTkOptionMenu(
            r1_left,
            variable=self.arrange_var,
            values=["2x2", "3x2", "3x3", "4x2", "2x1", "1x2", "4x3", "auto", "Tùy biến..."],
            width=78,
            height=26,
            corner_radius=2,
            fg_color=Colors.BG_CARD,
            button_color=Colors.BORDER_CARD,
            button_hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.CAPTION,
            dropdown_font=Fonts.CAPTION,
            command=self._handle_arrange_layout
        )
        self.combo_arrange.pack(side="left", padx=(0, 8))

        # Giãn cách mở client
        ctk.CTkLabel(r1_left, text="⏱️ Giãn cách:", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.delay_var = ctk.StringVar(value="0.5")
        self.delay_ent = ctk.CTkEntry(
            r1_left,
            textvariable=self.delay_var,
            width=42,
            height=26,
            corner_radius=2,
            font=Fonts.CAPTION,
            fg_color=Colors.BG_CARD,
            border_color=Colors.BORDER_CARD
        )
        self.delay_ent.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(r1_left, text="s", font=Fonts.CAPTION, text_color=Colors.TEXT_MUTED).pack(side="left")

        r1_right = ctk.CTkFrame(row1, fg_color="transparent")
        r1_right.pack(side="right", fill="y")

        self.status_lbl = ctk.CTkLabel(
            r1_right,
            text="Sẵn sàng",
            font=Fonts.BODY,
            text_color=Colors.TEXT_MUTED
        )
        self.status_lbl.pack(side="right", padx=4)

        # Hàng 2: Lọc nhóm phân loại & Tìm kiếm
        row2 = ctk.CTkFrame(tb, fg_color="transparent", height=32)
        row2.pack(fill="x", padx=8, pady=(0, 6))

        self.cat_frame = ctk.CTkFrame(row2, fg_color="transparent")
        self.cat_frame.pack(side="left", fill="y")
        self._build_category_pills()

        r2_right = ctk.CTkFrame(row2, fg_color="transparent")
        r2_right.pack(side="right", fill="y")

        self.btn_toggle_log = ctk.CTkButton(
            r2_right,
            text="📋 Nhật ký ▾",
            width=85,
            height=26,
            corner_radius=2,
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED,
            command=self.toggle_log_drawer
        )
        self.btn_toggle_log.pack(side="right", padx=(6, 0))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._handle_search())
        self.search_ent = ctk.CTkEntry(
            r2_right,
            textvariable=self.search_var,
            placeholder_text="🔍 Tìm tài khoản, nhân vật...",
            width=180,
            height=26,
            corner_radius=2,
            font=Fonts.CAPTION,
            fg_color=Colors.BG_CARD,
            border_color=Colors.BORDER_CARD
        )
        self.search_ent.pack(side="right")

    def _build_category_pills(self):
        """Tạo các nút lọc danh mục."""
        for w in self.cat_frame.winfo_children():
            w.destroy()

        cats = ["Tất cả"]
        if self.account_mgr and hasattr(self.account_mgr, "get_categories"):
            user_cats = self.account_mgr.get_categories()
            for c in user_cats:
                if c not in cats:
                    cats.append(c)

        for c_name in cats:
            is_active = (c_name == self.current_category)
            fg = "#1e293b" if is_active else "transparent"
            tc = Colors.CYAN if is_active else Colors.TEXT_MUTED
            bw = 1 if is_active else 0
            bc = "#0284c7" if is_active else None

            btn = ctk.CTkButton(
                self.cat_frame,
                text=f"🌐 {c_name}" if c_name == "Tất cả" else c_name,
                height=24,
                corner_radius=2,
                fg_color=fg,
                hover_color=Colors.BG_CARD_HOVER,
                border_width=bw,
                border_color=bc,
                text_color=tc,
                font=Fonts.CAPTION,
                command=lambda c=c_name: self.filter_by_category(c)
            )
            btn.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            self.cat_frame,
            text="➕ Thêm nhóm",
            height=24,
            corner_radius=2,
            fg_color="transparent",
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_MUTED,
            font=Fonts.CAPTION,
            command=self._handle_prompt_add_category
        ).pack(side="left")

    def _build_cards_container(self):
        """Khung cuộn chứa danh sách các thẻ tài khoản phẳng."""
        self.scroll_table = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_table.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        bind_mousewheel_to_scrollable(self.scroll_table)
        self._bind_drag_scroll()

        self.empty_lbl = ctk.CTkLabel(
            self.scroll_table,
            text="Chưa có tài khoản nào được lưu.\nNhấn nút '➕ Thêm Tài Khoản' ở thanh trên để thêm tài khoản MEGAMU!",
            font=Fonts.BODY,
            text_color=Colors.TEXT_DIM,
            justify="center"
        )

    def _bind_drag_scroll(self):
        """Hỗ trợ kéo rê canvas bằng chuột giữa (Middle Mouse Drag)."""
        try:
            if hasattr(self, "scroll_table") and hasattr(self.scroll_table, "_parent_canvas"):
                canvas = self.scroll_table._parent_canvas
                canvas.bind("<ButtonPress-2>", lambda e: canvas.scan_mark(e.x, e.y), add="+")
                canvas.bind("<B2-Motion>", lambda e: canvas.scan_dragto(e.x, e.y, gain=1), add="+")
        except Exception:
            pass

    def _build_log_drawer(self):
        """Khung nhật ký AutoLogin thu gọn/mở rộng ở dưới."""
        self.log_drawer = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, height=105, corner_radius=2, border_width=1, border_color=Colors.BORDER_CARD)
        self.log_drawer.pack(fill="x", padx=12, pady=(0, 6))
        self.log_drawer.pack_propagate(False)

        lh = ctk.CTkFrame(self.log_drawer, fg_color="transparent", height=22)
        lh.pack(fill="x", padx=6, pady=(3, 1))

        ctk.CTkLabel(
            lh,
            text="📋 NHẬT KÝ TIẾN TRÌNH ĐĂNG NHẬP (LOGS)",
            font=Fonts.CAPTION,
            text_color=Colors.CYAN
        ).pack(side="left")

        ctk.CTkButton(
            lh,
            text="Xóa log",
            width=50,
            height=18,
            corner_radius=2,
            fg_color=Colors.BG_SURFACE,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_MUTED,
            font=Fonts.CAPTION,
            command=self.clear_log
        ).pack(side="right")

        self.log_txt = ctk.CTkTextbox(
            self.log_drawer,
            font=Fonts.MONO,
            fg_color=Colors.BG_SURFACE,
            corner_radius=2
        )
        self.log_txt.pack(fill="both", expand=True, padx=6, pady=(0, 4))

    # --------------------------------------------------------------------------
    # QUẢN LÝ DỮ LIỆU & CẬP NHẬT TRẠNG THÁI IN-PLACE
    # --------------------------------------------------------------------------
    def load_accounts(self, accounts_list: List[Dict[str, Any]]):
        """Tải và đồng bộ danh sách tài khoản theo cơ chế Smart Reconcile (Không hủy thẻ đang dùng)."""
        current_usernames = set()

        for idx, acc in enumerate(accounts_list):
            u_name = str(acc.get("username", "")).strip()
            if not u_name:
                continue
            current_usernames.add(u_name)

            if u_name in self.cards:
                card = self.cards[u_name]
                card.account = acc
                card.stt = idx + 1
                card.stt_lbl.configure(text=f"#{idx+1:02d}")
                card.cb_var.set(acc.get("enabled", True))
                srv_val = int(acc.get("server", 3))
                if hasattr(card, "srv_var"):
                    card.srv_var.set(f"Server {srv_val}")
                c_name = acc.get("character") or "(Mặc định)"
                card.char_lbl.configure(text=f"NV: {c_name}")
                pref_slot = acc.get("preferred_slot")
                slot_disp = f"Gán: Slot #{pref_slot:02d}" if (pref_slot and pref_slot > 0) else "Gán: Tự động"
                card.slot_lbl.configure(text=slot_disp)
            else:
                card = CompactAccountCard(
                    self.scroll_table,
                    account=acc,
                    stt=idx + 1,
                    controllers=self.controllers,
                    on_toggle_enabled=self.on_toggle_account,
                    on_launch=self.on_launch_single,
                    on_send_login=self.on_send_login,
                    on_close=self.on_close_single,
                    on_edit=self.on_edit_account,
                    on_delete=self.on_delete_account,
                    on_copy_username=self._copy_username,
                    on_prompt_change_category=self.on_prompt_change_category,
                    on_change_server=self.on_change_server,
                    on_change_slot=self.on_change_slot
                )
                self.cards[u_name] = card

        for u in list(self.cards.keys()):
            if u not in current_usernames:
                self.cards[u].destroy()
                del self.cards[u]

        self._apply_filters()
        self._update_stats_label()

    def select_all_accounts(self, select: bool = True):
        """Chọn tất cả hoặc bỏ chọn tất cả tài khoản trong nhóm đang hiển thị ngoài UI."""
        cur_cat = self.current_category
        for card in self.cards.values():
            acc = card.account
            a_cat = (acc.get("category") or "Chung").strip()
            if cur_cat == "Tất cả" or a_cat.lower() == cur_cat.lower():
                card.cb_var.set(select)
                card.account["enabled"] = select
                if card.on_toggle_enabled:
                    card.on_toggle_enabled(card.account, select)
        self._update_stats_label()

    def update_account_state(
        self,
        username: str,
        is_online: bool,
        pid: Optional[int] = None,
        live_srv: Optional[int] = None,
        live_slot: Optional[str] = None,
        status_override: Optional[str] = None
    ) -> bool:
        """Cập nhật trạng thái một tài khoản cụ thể In-Place siêu tốc (0ms, Zero-Flicker). Trả về True nếu trạng thái thay đổi."""
        card = self.cards.get(username)
        if card:
            try:
                changed = card.update_state(
                    is_online=is_online,
                    pid=pid,
                    live_srv=live_srv,
                    live_slot=live_slot,
                    status_override=status_override
                )
                if changed:
                    self._update_stats_label()
                return changed
            except Exception:
                pass
        return False

    def filter_by_category(self, category: str):
        self.current_category = category
        self._build_category_pills()
        self._apply_filters()
        self._update_action_buttons()
        if hasattr(self, "on_filter_category") and self.on_filter_category:
            try:
                self.on_filter_category(category)
            except Exception:
                pass

    def _update_action_buttons(self):
        """Cập nhật nhãn nút thao tác theo nhóm đang lọc để hiển thị rõ phạm vi thực thi."""
        try:
            if not hasattr(self, "btn_launch_all") or not self.btn_launch_all.winfo_exists():
                return
            cur = self.current_category
            if cur == "Tất cả":
                self.btn_launch_all.configure(text="🚀 MỞ & LOGIN TẤT CẢ")
                if hasattr(self, "btn_close_all") and self.btn_close_all.winfo_exists():
                    self.btn_close_all.configure(text="🛑 ĐÓNG GAME")
            else:
                self.btn_launch_all.configure(text=f"🚀 MỞ & LOGIN ({cur})")
                if hasattr(self, "btn_close_all") and self.btn_close_all.winfo_exists():
                    self.btn_close_all.configure(text=f"🛑 ĐÓNG ({cur})")
        except Exception:
            pass

    def get_launchable_accounts(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các tài khoản đang được tích chọn [✓] và khớp với nhóm/bộ lọc hiện tại."""
        res = []
        cur_cat = self.current_category
        kw = self.search_keyword
        for card in self.cards.values():
            acc = card.account
            # Checkbox của thẻ phải được tích bật
            if not card.cb_var.get():
                continue
            # Lọc theo danh mục
            a_cat = (acc.get("category") or "Chung").strip()
            cat_match = (cur_cat == "Tất cả" or a_cat.lower() == cur_cat.lower())
            if not cat_match:
                continue
            # Lọc theo từ khóa tìm kiếm (nếu đang tìm kiếm)
            if kw:
                u_str = acc.get("username", "").lower()
                c_str = acc.get("character", "").lower()
                clist_str = " ".join(acc.get("characters_list", [])).lower()
                if not (kw in u_str or kw in c_str or kw in clist_str):
                    continue
            res.append(acc)
        return res

    def _handle_search(self):
        self.search_keyword = self.search_var.get().strip().lower()
        self._apply_filters()

    def _apply_filters(self):
        visible_count = 0
        cur_cat = self.current_category
        kw = self.search_keyword

        for card in self.cards.values():
            acc = card.account
            a_cat = (acc.get("category") or "Chung").strip()
            cat_match = (cur_cat == "Tất cả" or a_cat.lower() == cur_cat.lower())

            kw_match = True
            if kw:
                u_str = acc.get("username", "").lower()
                c_str = acc.get("character", "").lower()
                clist_str = " ".join(acc.get("characters_list", [])).lower()
                kw_match = (kw in u_str or kw in c_str or kw in clist_str)

            if cat_match and kw_match:
                if not bool(card.winfo_manager()):
                    card.pack(fill="x", pady=2)
                visible_count += 1
            else:
                if bool(card.winfo_manager()):
                    card.pack_forget()

        if visible_count == 0:
            if not bool(self.empty_lbl.winfo_manager()):
                self.empty_lbl.pack(pady=40)
        else:
            if bool(self.empty_lbl.winfo_manager()):
                self.empty_lbl.pack_forget()

        self._update_action_buttons()

    def _update_stats_label(self):
        try:
            if not hasattr(self, "status_lbl") or not self.status_lbl.winfo_exists():
                return
            total = len(self.cards)
            online = sum(1 for c in self.cards.values() if getattr(c, "_is_online", False))
            new_text = f"🎯 {total} Tài khoản | 🟢 {online} Online | Sẵn sàng"
            if self.status_lbl.cget("text") != new_text:
                self.status_lbl.configure(text=new_text)
        except Exception:
            pass

    def toggle_log_drawer(self):
        if self._log_visible:
            self.log_drawer.pack_forget()
            self._log_visible = False
            self.btn_toggle_log.configure(text="📋 Nhật ký ▴")
        else:
            self.log_drawer.pack(fill="x", padx=12, pady=(0, 6))
            self._log_visible = True
            self.btn_toggle_log.configure(text="📋 Nhật ký ▾")

    def append_log(self, text: str):
        if not hasattr(self, "_pending_logs"):
            self._pending_logs = []
        t_str = time.strftime("%H:%M:%S")
        self._pending_logs.append(f"[{t_str}] {text}\n")
        if not getattr(self, "_log_flush_scheduled", False):
            self._log_flush_scheduled = True
            try:
                self.after(80, self._flush_logs)
            except Exception:
                self._log_flush_scheduled = False

    def _flush_logs(self):
        self._log_flush_scheduled = False
        pending = getattr(self, "_pending_logs", None)
        if not pending or not hasattr(self, "log_txt"):
            self._pending_logs = []
            return
        self._pending_logs = []
        try:
            if not self.log_txt.winfo_exists():
                return
            self.log_txt.insert("end", "".join(pending))
            line_count = int(self.log_txt.index("end-1c").split(".")[0])
            if line_count > 1000:
                self.log_txt.delete("1.0", "150.0")
            self.log_txt.see("end")
        except Exception:
            pass

    def clear_log(self):
        self.log_txt.delete("1.0", "end")

    def get_selected_usernames(self) -> List[str]:
        return [u for u, card in self.cards.items() if card.cb_var.get()]

    def _copy_username(self, username: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(username)
            self.append_log(f"📋 Đã sao chép tên tài khoản: {username}")
        except Exception:
            pass

    # Callbacks trung gian
    def _handle_launch_all(self):
        if self.on_launch_all:
            self.on_launch_all()

    def _handle_close_all(self):
        if self.on_close_all:
            self.on_close_all()

    def _handle_add_account(self):
        if self.on_add_account:
            self.on_add_account()

    def _handle_delete_selected(self):
        if self.on_delete_selected:
            self.on_delete_selected()

    def _handle_change_exe(self):
        if self.on_change_exe:
            self.on_change_exe()

    def _handle_arrange_layout(self, val: str):
        if self.on_arrange_layout:
            self.on_arrange_layout(val)

    def _handle_prompt_add_category(self):
        if self.on_prompt_add_category:
            self.on_prompt_add_category()
