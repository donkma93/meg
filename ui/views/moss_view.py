"""
UI View: MossView (Auto Moss Merchant).
Tối giản, mỏng phẳng (Minimalist Compact), 2 hàng toolbar, chiều cao dòng 32px, khung log 68px.
"""

from typing import Any, Dict, List
import customtkinter as ctk
from core.storage import ConfigPersistenceManager
from ui.components import ModernOptionMenu, add_tooltip


class MossView:
    """Builder và quản lý giao diện Tab Auto Moss Merchant."""

    def __init__(self, master_app: Any, parent_panel: ctk.CTkFrame):
        self.app = master_app
        self.panel = parent_panel

    def build(self):
        """Khởi dựng toàn bộ layout Tab Moss theo chuẩn Minimalist Compact."""
        # 1. COMPACT TOOLBAR CONTAINER (2 hàng mỏng)
        toolbar_container = ctk.CTkFrame(self.panel, fg_color="#141722", corner_radius=0, border_width=1, border_color="#1c2230")
        toolbar_container.pack(fill="x", padx=10, pady=(6, 3))

        inner_tb = ctk.CTkFrame(toolbar_container, fg_color="transparent")
        inner_tb.pack(fill="x", padx=10, pady=5)

        # Hàng 1: Tiêu đề + Đếm ngược + Checkbox Lịch trình + Nút Start/Stop
        row1 = ctk.CTkFrame(inner_tb, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 4))

        title_lbl = ctk.CTkLabel(
            row1,
            text="🎲 MOSS AUTO ROLL",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f59e0b"
        )
        title_lbl.pack(side="left", padx=(0, 8))

        self.app.lbl_moss_countdown = ctk.CTkLabel(
            row1,
            text="⏳ Còn: --:--:--",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10b981"
        )
        self.app.lbl_moss_countdown.pack(side="left", padx=(0, 6))

        self.app.lbl_moss_next_event = ctk.CTkLabel(
            row1,
            text="(12:15)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        )
        self.app.lbl_moss_next_event.pack(side="left", padx=(0, 8))

        self.app.lbl_moss_sched_status = ctk.CTkLabel(
            row1,
            text="● Chờ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#10b981"
        )
        self.app.lbl_moss_sched_status.pack(side="left", padx=(0, 10))

        # Divider mỏng
        ctk.CTkFrame(row1, fg_color="#1e293b", width=1, height=16).pack(side="left", padx=(0, 10))

        self.app.cb_moss_auto_schedule = ctk.CTkCheckBox(
            row1,
            text="Quay theo lịch",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#38bdf8",
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.app.on_toggle_moss_auto_schedule
        )
        self.app.cb_moss_auto_schedule.pack(side="left", padx=(0, 12))

        self.app.cb_moss_auto_move_before = ctk.CTkCheckBox(
            row1,
            text="Tự chạy NPC",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8",
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.app.on_toggle_moss_auto_schedule
        )
        self.app.cb_moss_auto_move_before.pack(side="left")

        # Nút Start/Stop Master bên phải Hàng 1
        r1_right = ctk.CTkFrame(row1, fg_color="transparent")
        r1_right.pack(side="right")

        self.app.btn_moss_stop_all = ctk.CTkButton(
            r1_right,
            text="⏹ Dừng",
            width=70,
            height=24,
            corner_radius=3,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.stop_all_moss_auto
        )
        self.app.btn_moss_stop_all.pack(side="right", padx=(4, 0))

        self.app.btn_moss_start_all = ctk.CTkButton(
            r1_right,
            text="▶ Bắt đầu quay",
            width=115,
            height=24,
            corner_radius=3,
            fg_color="#059669",
            hover_color="#047857",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.app.start_all_moss_auto
        )
        self.app.btn_moss_start_all.pack(side="right", padx=(6, 0))

        self.app.lbl_moss_count_badge = ctk.CTkLabel(
            r1_right,
            text="0/0",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#f59e0b"
        )
        self.app.lbl_moss_count_badge.pack(side="right")

        # Nạp cấu hình lịch trình từ file
        try:
            sched_cfg = ConfigPersistenceManager.load_moss_schedule_config()
            if sched_cfg.get("auto_schedule", True):
                self.app.cb_moss_auto_schedule.select()
            else:
                self.app.cb_moss_auto_schedule.deselect()

            if sched_cfg.get("auto_move_before", True):
                self.app.cb_moss_auto_move_before.select()
            else:
                self.app.cb_moss_auto_move_before.deselect()
        except Exception:
            self.app.cb_moss_auto_schedule.select()
            self.app.cb_moss_auto_move_before.select()

        # Hàng 2: Chọn tất cả + Gán nhanh danh mục + Delay + Tiện ích dọn rác
        row2 = ctk.CTkFrame(inner_tb, fg_color="transparent")
        row2.pack(fill="x")

        btn_sel_all = ctk.CTkButton(
            row2,
            text="☑ Chọn hết",
            width=70,
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#38bdf8",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=self.app.select_all_moss_slots
        )
        btn_sel_all.pack(side="left", padx=(0, 4))

        btn_desel_all = ctk.CTkButton(
            row2,
            text="☐ Bỏ chọn",
            width=65,
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.deselect_all_moss_slots
        )
        btn_desel_all.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            row2,
            text="Gán nhanh:",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        ).pack(side="left", padx=(0, 3))

        self.app.batch_moss_cat_combo = ModernOptionMenu(
            row2,
            values=[name for name, _ in self.app.MOSS_CAT_OPTIONS],
            width=165,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10)
        )
        self.app.batch_moss_cat_combo.set(self.app.MOSS_CAT_OPTIONS[0][0])
        self.app.batch_moss_cat_combo.pack(side="left", padx=(0, 3))

        btn_apply_cat = ctk.CTkButton(
            row2,
            text="Áp dụng",
            width=55,
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.apply_batch_moss_category
        )
        btn_apply_cat.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            row2,
            text="Delay:",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        ).pack(side="left", padx=(0, 2))

        self.app.batch_moss_delay_entry = ctk.CTkEntry(
            row2,
            width=48,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#181c26",
            border_color="#2b3244",
            text_color="#f8fafc"
        )
        self.app.batch_moss_delay_entry.insert(0, "1000")
        self.app.batch_moss_delay_entry.pack(side="left", padx=(0, 2))

        btn_apply_delay = ctk.CTkButton(
            row2,
            text="Đặt",
            width=36,
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.apply_batch_moss_delay
        )
        btn_apply_delay.pack(side="left", padx=(0, 8))

        # Tiện ích dọn rác & NPC bên phải Hàng 2
        r2_right = ctk.CTkFrame(row2, fg_color="transparent")
        r2_right.pack(side="right")

        self.app.batch_moss_clean_cb = ctk.CTkCheckBox(
            r2_right,
            text="Tự dọn rác",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#f87171",
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self.app.on_toggle_global_moss_clean
        )
        self.app.batch_moss_clean_cb.select()
        self.app.batch_moss_clean_cb.pack(side="left", padx=(0, 6))

        btn_clean_all = ctk.CTkButton(
            r2_right,
            text="🗑 Ném rác",
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#ef4444",
            text_color="#f87171",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.clean_all_moss_inventories
        )
        btn_clean_all.pack(side="left", padx=(0, 4))

        btn_sell_all = ctk.CTkButton(
            r2_right,
            text="💰 Bán Silvia",
            height=24,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#10b981",
            text_color="#34d399",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.sell_all_moss_inventories
        )
        btn_sell_all.pack(side="left")

        # 2. BẢNG CÁC TÀI KHOẢN (MOSS SLOT TABLE)
        table_container = ctk.CTkFrame(self.panel, fg_color="#141722", corner_radius=0, border_width=1, border_color="#1c2230")
        table_container.pack(fill="both", expand=True, padx=10, pady=(2, 3))

        # Header bảng (Pixel-Perfect Alignment)
        tbl_h = ctk.CTkFrame(table_container, fg_color="transparent", height=24)
        tbl_h.pack(fill="x", padx=4, pady=(4, 2))

        headers = [
            ("STT", 45, "center", (4, 2)),
            ("Tài khoản / PID", 175, "w", (2, 2)),
            ("Vật Phẩm Quay (Category)", 185, "w", (2, 2)),
            ("Delay", 60, "center", (2, 2)),
            ("Đã Quay", 70, "center", (2, 2)),
            ("Trạng Thái", 85, "center", (2, 2)),
            ("Thao Tác", 145, "center", (2, 2)),
        ]
        for title, w, anc, px in headers:
            ctk.CTkLabel(
                tbl_h,
                text=title,
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#64748b"
            ).pack(side="left", padx=px)

        div = ctk.CTkFrame(table_container, fg_color="#1c2230", height=1)
        div.pack(fill="x", padx=4, pady=(0, 2))

        # Khung cuộn chứa từng dòng slot Moss
        self.app.moss_scroll_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.app.moss_scroll_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        for ctrl in self.app.controllers:
            self.app.create_moss_slot_row(ctrl.slot_idx)

        # 3. KHUNG NHẬT KÝ LƯỢT QUAY TRỰC TIẾP (68px)
        log_frame = ctk.CTkFrame(self.panel, fg_color="#10131c", height=68, corner_radius=0, border_width=1, border_color="#1c2230")
        log_frame.pack(fill="x", padx=10, pady=(2, 6))
        log_frame.pack_propagate(False)

        lh = ctk.CTkFrame(log_frame, fg_color="transparent", height=20)
        lh.pack(fill="x", padx=8, pady=(2, 1))

        ctk.CTkLabel(
            lh,
            text="📜 NHẬT KÝ QUAY TRỰC TIẾP",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left")

        btn_clear = ctk.CTkButton(
            lh,
            text="Xóa log",
            width=55,
            height=18,
            corner_radius=2,
            fg_color="#181c26",
            hover_color="#242b3a",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self.app.clear_moss_log
        )
        btn_clear.pack(side="right")

        self.app.moss_log_txt = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0b0d13",
            text_color="#cbd5e1"
        )
        self.app.moss_log_txt.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self.app.append_moss_log("🟢 Auto Moss Merchant sẵn sàng.")
        self.app.update_moss_selected_badge()

