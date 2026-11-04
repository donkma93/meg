"""
UI View: MirrorView (Double Goer / Dimensional Mirror).
Tối giản, mỏng phẳng (Minimalist Compact), 1 nút Toggle CƯỚP CỔNG/DỪNG thông minh,
bảng 607px tương thích hoàn hảo màn hình nhỏ.
"""

from typing import Any, Dict
import customtkinter as ctk
from core.storage import ConfigPersistenceManager
from ui.components import add_tooltip


class MirrorView:
    """Builder và quản lý giao diện Tab Double Goer (Mirror)."""

    def __init__(self, master_app: Any, parent_panel: ctk.CTkFrame):
        self.app = master_app
        self.panel = parent_panel

    def build(self):
        """Khởi dựng toàn bộ layout Tab Mirror."""
        # 1. COMPACT TOOLBAR CONTAINER (2 hàng mỏng)
        toolbar_container = ctk.CTkFrame(self.panel, fg_color="#141722", corner_radius=0, border_width=1, border_color="#1c2230")
        toolbar_container.pack(fill="x", padx=8, pady=(4, 2))

        inner_tb = ctk.CTkFrame(toolbar_container, fg_color="transparent")
        inner_tb.pack(fill="x", padx=8, pady=4)

        # Hàng 1: Tiêu đề + Đếm ngược + Checkbox cướp cổng & về Lugard + Nút CƯỚP CỔNG / DỪNG
        row1 = ctk.CTkFrame(inner_tb, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 3))

        # ƯU TIÊN 1: Pack r1_right trước (side="right") với 1 nút TOGGLE duy nhất (CƯỚP CỔNG / DỪNG)
        r1_right = ctk.CTkFrame(row1, fg_color="transparent")
        r1_right.pack(side="right")

        self.app.btn_mirror_toggle_snipe = ctk.CTkButton(
            r1_right,
            text="⚡ CƯỚP CỔNG",
            width=110,
            height=24,
            corner_radius=3,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=self.app.toggle_mirror_turbo_sniping
        )
        self.app.btn_mirror_toggle_snipe.pack(side="right", padx=(4, 0))
        add_tooltip(self.app.btn_mirror_toggle_snipe, "Nhấn để BẮT ĐẦU hoặc DỪNG cướp cổng cho các tài khoản đã chọn")

        # Giữ bí danh tương thích
        self.app.btn_mirror_snipe_all = self.app.btn_mirror_toggle_snipe
        self.app.btn_mirror_stop_all = self.app.btn_mirror_toggle_snipe

        self.app.lbl_mirror_count_badge = ctk.CTkLabel(
            r1_right,
            text="0/0",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#2dd4bf"
        )
        self.app.lbl_mirror_count_badge.pack(side="right")
        add_tooltip(self.app.lbl_mirror_count_badge, "Số tài khoản được chọn tham gia Mirror")

        # Phía trái Hàng 1: Icon/Text tối giản
        title_lbl = ctk.CTkLabel(
            row1,
            text="🪞 Mirror",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#c084fc"
        )
        title_lbl.pack(side="left", padx=(0, 6))

        self.app.lbl_mirror_countdown = ctk.CTkLabel(
            row1,
            text="⏳ --:--",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38bdf8"
        )
        self.app.lbl_mirror_countdown.pack(side="left", padx=(0, 4))
        add_tooltip(self.app.lbl_mirror_countdown, "Đếm ngược tới giờ mở cổng Double Goer")

        self.app.lbl_mirror_next_event = ctk.CTkLabel(
            row1,
            text="(:10)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        )
        self.app.lbl_mirror_next_event.pack(side="left", padx=(0, 6))

        self.app.lbl_mirror_sched_status = ctk.CTkLabel(
            row1,
            text="● Chờ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#10b981"
        )
        self.app.lbl_mirror_sched_status.pack(side="left", padx=(0, 8))

        # Divider mỏng
        ctk.CTkFrame(row1, fg_color="#1e293b", width=1, height=14).pack(side="left", padx=(0, 8))

        self.app.cb_mirror_auto_schedule = ctk.CTkCheckBox(
            row1,
            text="⚡ Cướp :10",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#c084fc",
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=self.app.on_toggle_mirror_auto_schedule
        )
        self.app.cb_mirror_auto_schedule.pack(side="left", padx=(0, 8))
        add_tooltip(self.app.cb_mirror_auto_schedule, "Tự động kích hoạt cướp cổng khi đến phút :10")

        self.app.cb_mirror_auto_prep_before = ctk.CTkCheckBox(
            row1,
            text="🚶 Về :08",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#94a3b8",
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=self.app.on_toggle_mirror_auto_schedule
        )
        self.app.cb_mirror_auto_prep_before.pack(side="left")
        add_tooltip(self.app.cb_mirror_auto_prep_before, "Tự động di chuyển về NPC Lugard lúc :08")

        # Tạm thời bỏ các tính năng không hoạt động ổn định
        self.app.cb_mirror_auto_lifecycle = None
        self.app.cb_mirror_auto_gremory = None

        # Nạp cấu hình lịch trình từ file
        try:
            m_sched_cfg = ConfigPersistenceManager.load_mirror_schedule_config()
            if m_sched_cfg.get("auto_schedule", True):
                self.app.cb_mirror_auto_schedule.select()
            else:
                self.app.cb_mirror_auto_schedule.deselect()

            if m_sched_cfg.get("auto_prep_before", True):
                self.app.cb_mirror_auto_prep_before.select()
            else:
                self.app.cb_mirror_auto_prep_before.deselect()
        except Exception:
            self.app.cb_mirror_auto_schedule.select()
            self.app.cb_mirror_auto_prep_before.select()

        # Hàng 2: Chọn tất cả + Check vé + Về Lugard + Vào cửa + Auto thường + Thông số
        row2 = ctk.CTkFrame(inner_tb, fg_color="transparent")
        row2.pack(fill="x")

        # Ưu tiên pack r2_right trước (side="right")
        r2_right = ctk.CTkFrame(row2, fg_color="transparent")
        r2_right.pack(side="right")

        _init_prefire = 1.2
        try:
            _s_cfg = ConfigPersistenceManager.load_mirror_schedule_config()
            _init_prefire = float(_s_cfg.get("prefire_sec", 1.2))
        except Exception:
            pass

        ctk.CTkLabel(
            r2_right,
            text="s",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        ).pack(side="right")

        self.app.mirror_prefire_sec_entry = ctk.CTkEntry(
            r2_right,
            width=36,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#181c26",
            border_color="#0284c7",
            text_color="#f8fafc"
        )
        self.app.mirror_prefire_sec_entry.insert(0, f"{_init_prefire:.1f}".rstrip('0').rstrip('.') if _init_prefire != int(_init_prefire) else str(int(_init_prefire)))
        self.app.mirror_prefire_sec_entry.pack(side="right", padx=(2, 2))
        self.app.mirror_prefire_sec_entry.bind("<FocusOut>", lambda e: self.app.on_toggle_mirror_auto_schedule())
        self.app.mirror_prefire_sec_entry.bind("<Return>", lambda e: self.app.on_toggle_mirror_auto_schedule())
        add_tooltip(self.app.mirror_prefire_sec_entry, "Thời gian bắn trước (giây) đón đầu giờ mở cổng")

        ctk.CTkLabel(
            r2_right,
            text="Bắn trước:",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8"
        ).pack(side="right", padx=(5, 0))

        ctk.CTkLabel(
            r2_right,
            text="ms",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748b"
        ).pack(side="right")

        self.app.mirror_snipe_delay_entry = ctk.CTkEntry(
            r2_right,
            width=38,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#181c26",
            border_color="#7c3aed",
            text_color="#f8fafc"
        )
        self.app.mirror_snipe_delay_entry.insert(0, "35")
        self.app.mirror_snipe_delay_entry.pack(side="right", padx=(2, 2))
        add_tooltip(self.app.mirror_snipe_delay_entry, "Chu kỳ lặp lại gửi gói tin cướp cổng (ms)")

        ctk.CTkLabel(
            r2_right,
            text="Chu kỳ:",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#c084fc"
        ).pack(side="right")

        self.app.mirror_snipe_dur_entry = ctk.CTkEntry(
            r2_right,
            width=1,
            height=1,
            fg_color="#181c26"
        )
        self.app.mirror_snipe_dur_entry.insert(0, "15")

        # Phía trái Hàng 2: Các nút thao tác tinh gọn
        btn_sel_all = ctk.CTkButton(
            row2,
            text="☑ Tất cả",
            width=54,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#38bdf8",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=self.app.select_all_mirror_slots
        )
        btn_sel_all.pack(side="left", padx=(0, 3))
        add_tooltip(btn_sel_all, "Chọn toàn bộ tài khoản tham gia Mirror")

        btn_desel_all = ctk.CTkButton(
            row2,
            text="☐ Bỏ",
            width=44,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.deselect_all_mirror_slots
        )
        btn_desel_all.pack(side="left", padx=(0, 5))
        add_tooltip(btn_desel_all, "Bỏ chọn toàn bộ tài khoản đi Mirror")

        ctk.CTkFrame(row2, fg_color="#1e293b", width=1, height=14).pack(side="left", padx=(0, 5))

        btn_check_all = ctk.CTkButton(
            row2,
            text="🎟 Vé",
            width=50,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#475569",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.check_all_mirror_tickets
        )
        btn_check_all.pack(side="left", padx=(0, 3))
        add_tooltip(btn_check_all, "Quét kiểm tra vé Mirror trong hòm đồ tất cả tài khoản")

        btn_move_all = ctk.CTkButton(
            row2,
            text="🚶 Lugard",
            width=62,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#38bdf8",
            text_color="#38bdf8",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.move_all_to_event_map
        )
        btn_move_all.pack(side="left", padx=(0, 3))
        add_tooltip(btn_move_all, "Di chuyển toàn bộ tài khoản về NPC Lugard (Elbeland)")

        btn_enter_all = ctk.CTkButton(
            row2,
            text="🚪 Vào",
            width=48,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#a855f7",
            text_color="#c084fc",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.enter_all_mirror
        )
        btn_enter_all.pack(side="left", padx=(0, 3))
        add_tooltip(btn_enter_all, "Gửi lệnh vào cửa sự kiện Mirror")

        self.app.btn_mirror_start_all = ctk.CTkButton(
            row2,
            text="▶ Auto",
            width=54,
            height=22,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#242b3a",
            border_width=1,
            border_color="#059669",
            text_color="#34d399",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.app.start_all_mirror_auto
        )
        self.app.btn_mirror_start_all.pack(side="left")
        add_tooltip(self.app.btn_mirror_start_all, "Chạy Auto Train thường cho các tài khoản")

        # 2. KHUNG NỘI DUNG CHIA ĐÔI: BẢNG TÀI KHOẢN (TRÁI) & NHẬT KÝ (PHẢI)
        body_split_frame = ctk.CTkFrame(self.panel, fg_color="transparent")
        body_split_frame.pack(fill="both", expand=True, padx=8, pady=(2, 4))

        # 2.1 BÊN TRÁI: BẢNG CÁC TÀI KHOẢN (MIRROR SLOT TABLE - 545px)
        table_container = ctk.CTkFrame(body_split_frame, fg_color="#141722", corner_radius=0, border_width=1, border_color="#1c2230", width=545)
        table_container.pack(side="left", fill="both", expand=False, padx=(0, 4), pady=0)
        table_container.pack_propagate(False)

        # Header bảng
        tbl_h = ctk.CTkFrame(table_container, fg_color="transparent", height=24)
        tbl_h.pack(fill="x", padx=4, pady=(3, 2))

        headers = [
            ("STT", 42, "center", (3, 2)),
            ("Tài khoản / PID", 150, "w", (2, 2)),
            ("Tọa độ", 75, "center", (2, 2)),
            ("Vé", 90, "center", (2, 2)),
            ("Trạng Thái", 105, "center", (2, 2)),
            ("Thao Tác", 60, "center", (2, 2)),
        ]
        for title, w, anc, px in headers:
            ctk.CTkLabel(
                tbl_h,
                text=title,
                width=w,
                anchor=anc,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#64748b"
            ).pack(side="left", padx=px)

        div = ctk.CTkFrame(table_container, fg_color="#1c2230", height=1)
        div.pack(fill="x", padx=4, pady=(0, 2))

        # Khung cuộn chứa từng dòng slot Mirror
        self.app.mirror_scroll_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.app.mirror_scroll_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        for ctrl in self.app.controllers:
            self.app.create_mirror_slot_row(ctrl.slot_idx)

        # 2.2 BÊN PHẢI: KHUNG NHẬT KÝ DOUBLE GOER CHI TIẾT (Tận dụng toàn bộ diện tích thừa bên phải)
        log_frame = ctk.CTkFrame(body_split_frame, fg_color="#10131c", corner_radius=0, border_width=1, border_color="#1c2230")
        log_frame.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

        lh = ctk.CTkFrame(log_frame, fg_color="#141722", height=26, corner_radius=0)
        lh.pack(fill="x", padx=0, pady=0)
        lh.pack_propagate(False)

        lh_inner = ctk.CTkFrame(lh, fg_color="transparent")
        lh_inner.pack(fill="both", expand=True, padx=8, pady=0)

        ctk.CTkLabel(
            lh_inner,
            text="📜 NHẬT KÝ DOUBLE GOER",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left")

        btn_clear = ctk.CTkButton(
            lh_inner,
            text="Xóa log",
            width=55,
            height=18,
            corner_radius=2,
            fg_color="#181c26",
            hover_color="#242b3a",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self.app.clear_mirror_log
        )
        btn_clear.pack(side="right")

        ctk.CTkFrame(log_frame, fg_color="#1c2230", height=1).pack(fill="x")

        self.app.mirror_log_txt = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0b0d13",
            text_color="#cbd5e1",
            wrap="char"
        )
        self.app.mirror_log_txt.pack(fill="both", expand=True, padx=4, pady=4)
        self.app.append_mirror_log("🟢 Auto Double Goer (Mirror of Dimensions) sẵn sàng.")
        self.app.update_mirror_selected_badge()

