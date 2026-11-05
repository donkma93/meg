"""
UI Modal: Character Stat Ratio & Auto Points Dialog.
"""

from typing import Any
from tkinter import messagebox
import customtkinter as ctk

from core.storage import ConfigPersistenceManager
from core.constants import CLASS_ID_TO_CODE, CLASS_CODE_TO_NAME
from ui.components.icons import UiIconFactory
from ui.components.option_menu import ModernOptionMenu

def open_slot_stat_ratio_dialog(self, slot_idx: int):
    """Mở cửa sổ cấu hình Tự Động Đi Devil Square, Tự Động Reset & Chỉ số Point theo từng Class."""
    ctrl = self.controllers[slot_idx - 1]
    dlg = ctk.CTkToplevel(self)
    dlg.title(f"Cài Đặt Slot {slot_idx:02d} - Devil Square, Reset & Point")
    dlg.geometry("520x680")
    dlg.resizable(False, False)
    dlg.configure(fg_color="#0f111a")
    dlg.transient(self)
    dlg.grab_set()

    # Nạp bảng cấu hình chuẩn của 16 Class
    class_profiles = ConfigPersistenceManager.load_class_stat_profiles()

    # Nhận diện class hiện tại của nhân vật
    det_cid = ctrl.class_id
    eng = ctrl.engine or (getattr(self, "direct_engines", {}).get(ctrl.assigned_pid) if ctrl.assigned_pid else None)
    if eng and eng.is_ready:
        try:
            p_inf = eng.get_player_info(max_age=0.5)
            if p_inf:
                if "classId" in p_inf and int(p_inf["classId"]) >= 0:
                    det_cid = int(p_inf["classId"])
                    ctrl.class_id = det_cid
                    ctrl.class_code = CLASS_ID_TO_CODE.get(det_cid, "")
                if "name" in p_inf and p_inf["name"]:
                    ctrl.char_name = p_inf["name"]
                if "points" in p_inf:
                    ctrl.points = int(p_inf["points"])
        except Exception:
            pass

    det_code = ctrl.class_code if ctrl.class_code else CLASS_ID_TO_CODE.get(det_cid, "DK")
    det_fullname = CLASS_CODE_TO_NAME.get(det_code, "Dark Knight")

    # Tiêu đề
    header_frame = ctk.CTkFrame(dlg, fg_color="#181c26", corner_radius=0, height=54)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    cname = ctrl.char_name if ctrl.char_name != "---" else f"Slot {slot_idx:02d}"
    t_lbl = ctk.CTkLabel(
        header_frame,
        text=f"⚙️ CẤU HÌNH TỰ ĐỘNG - {cname.upper()}",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#38bdf8"
    )
    t_lbl.pack(side="left", padx=16, pady=8)

    tag_class = ctk.CTkLabel(
        header_frame,
        text=f"Class: [{det_code}] {det_fullname}",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#10b981",
        fg_color="#064e3b",
        corner_radius=4,
        padx=8,
        pady=2
    )
    tag_class.pack(side="right", padx=16, pady=12)

    content = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=16, pady=10)

    # 1. Devil Square Section
    ds_card = ctk.CTkFrame(content, fg_color="#141722", corner_radius=8, border_width=1, border_color="#242b3a")
    ds_card.pack(fill="x", pady=(0, 10), padx=4)

    ds_header = ctk.CTkLabel(
        ds_card,
        text="🔥 TỰ ĐỘNG THAM GIA DEVIL SQUARE (DS)",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#f43f5e"
    )
    ds_header.pack(anchor="w", padx=12, pady=(8, 2))

    ds_sub = ctk.CTkLabel(
        ds_card,
        text="Tự động warp sang Event Square & vào cửa DS khi mở cổng (:27 - :30 giờ lẻ).",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#94a3b8",
        wraplength=460,
        justify="left"
    )
    ds_sub.pack(anchor="w", padx=12, pady=(0, 6))

    var_ds = ctk.BooleanVar(value=ctrl.auto_devil)
    chk_ds = ctk.CTkCheckBox(
        ds_card,
        text="Kích hoạt tự động đi Devil Square cho nhân vật này",
        variable=var_ds,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f1f5f9",
        fg_color="#e11d48",
        hover_color="#be123c"
    )
    chk_ds.pack(anchor="w", padx=12, pady=(0, 8))

    # Hàng điều kiện Reset bắt đầu đi Devil (CHỈ THEO RESET, KHÔNG THEO LEVEL)
    row_ds_rs = ctk.CTkFrame(ds_card, fg_color="transparent")
    row_ds_rs.pack(fill="x", padx=12, pady=(0, 6))

    ctk.CTkLabel(row_ds_rs, text="Bắt đầu đi Devil khi đạt từ:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#cbd5e1").pack(side="left")
    ent_ds_min_rs = ctk.CTkEntry(row_ds_rs, width=65, height=26, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), justify="center")
    ent_ds_min_rs.pack(side="left", padx=(8, 6))
    ent_ds_min_rs.insert(0, str(getattr(ctrl, "devil_min_resets", 0)))

    ctk.CTkLabel(row_ds_rs, text="Reset trở lên", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#facc15").pack(side="left")

    # Ẩn entry max reset (mặc định 9999)
    ent_ds_max_rs = ctk.CTkEntry(row_ds_rs, width=1, height=1)
    ent_ds_max_rs.insert(0, "9999")

    # Hàng lựa chọn loại vé
    row_ds_ticket = ctk.CTkFrame(ds_card, fg_color="transparent")
    row_ds_ticket.pack(fill="x", padx=12, pady=(0, 8))

    ctk.CTkLabel(row_ds_ticket, text="Loại vé sử dụng:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#cbd5e1").pack(side="left")
    ticket_options = [
        "🎫 Tự động (Ưu tiên Vé Master)",
        "🎫 Chỉ đi Vé Thường (DS 1 - 7)",
        "🎫 Chỉ đi Vé Master (Master DS)"
    ]
    curr_t_val = getattr(ctrl, "devil_ticket_type", "auto")
    init_t_choice = ticket_options[0]
    if curr_t_val == "master":
        init_t_choice = ticket_options[2]
    elif curr_t_val == "normal":
        init_t_choice = ticket_options[1]

    cbo_ds_ticket = ctk.CTkOptionMenu(
        row_ds_ticket,
        values=ticket_options,
        width=245,
        height=26,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        fg_color="#1e293b",
        button_color="#334155"
    )
    cbo_ds_ticket.set(init_t_choice)
    cbo_ds_ticket.pack(side="left", padx=(8, 0))

    # Khung lưu ý nguyên tắc an toàn Auto Train
    ds_notice_frame = ctk.CTkFrame(ds_card, fg_color="#0b1120", corner_radius=6, border_width=1, border_color="#1e293b")
    ds_notice_frame.pack(fill="x", padx=12, pady=(0, 8))
    ds_notice_lbl = ctk.CTkLabel(
        ds_notice_frame,
        text="⏰ Lịch mở cổng MEGAMU: 2 tiếng/lần vào giờ lẻ (:27 - :30) • 12 đợt/ngày.\n"
             "🛡️ Nguyên tắc an toàn: Chỉ ngưng cày quái khi ĐÃ VÀO MAP DEVIL thành công.\n"
             "   Nếu chưa đủ Reset, không có vé hoặc không vào được: tiếp tục cắm bãi train.",
        font=ctk.CTkFont(family="Segoe UI", size=9),
        text_color="#94a3b8",
        justify="left"
    )
    ds_notice_lbl.pack(anchor="w", padx=8, pady=6)

    # Nút áp dụng nhanh cấu hình Devil cho toàn bộ các Slot
    def _apply_devil_to_all_slots():
        try:
            new_ds_val = var_ds.get()
            m_rs = int(ent_ds_min_rs.get().strip() or 0)
            M_rs = int(ent_ds_max_rs.get().strip() or 9999)
            t_choice = cbo_ds_ticket.get()
            t_pref = "master" if ("Master" in t_choice and "Chỉ" in t_choice) else ("normal" if ("Thường" in t_choice and "Chỉ" in t_choice) else "auto")
            for c in self.controllers:
                c.auto_devil = new_ds_val
                c.devil_min_resets = m_rs
                c.devil_max_resets = M_rs
                c.devil_ticket_type = t_pref
                ConfigPersistenceManager.save_event_config(
                    slot_idx=c.slot_idx,
                    auto_devil=new_ds_val,
                    devil_min_resets=m_rs,
                    devil_max_resets=M_rs,
                    devil_ticket_type=t_pref,
                    auto_reset=c.auto_reset,
                    auto_add_point=c.auto_add_point,
                    reset_level=c.reset_level,
                    stat_mode=c.stat_mode,
                    custom_class=c.custom_class,
                    stat_ratio=c.stat_ratio
                )
                if c.worker and c.worker.running and hasattr(c.worker, 'update_config'):
                    c.worker.update_config({
                        "auto_devil": new_ds_val,
                        "devil_min_resets": m_rs,
                        "devil_max_resets": M_rs,
                        "devil_ticket_type": t_pref
                    })
                el = self.slot_ui_elements.get(c.slot_idx)
                if el and el.get("btn_devil"):
                    if new_ds_val:
                        el["btn_devil"].configure(fg_color="#4c0519", text_color="#f43f5e", border_color="#e11d48", hover_color="#881337")
                    else:
                        el["btn_devil"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")
            st = "BẬT" if new_ds_val else "TẮT"
            t_label = "Vé Master" if t_pref == "master" else ("Vé Thường" if t_pref == "normal" else "Tự động")
            self.log_message(f"👥 Đã áp dụng Cấu hình Devil Square [{st} | RS: {m_rs}-{M_rs} | {t_label}] cho toàn bộ {len(self.controllers)} slot!", "SUCCESS")
            messagebox.showinfo("Thành Công", f"Đã áp dụng cấu hình Devil Square cho tất cả {len(self.controllers)} slot:\n• Trạng thái: {st}\n• Mốc Reset: {m_rs} - {M_rs}\n• Loại vé: {t_label}", parent=dlg)
        except Exception as e_all:
            messagebox.showerror("Lỗi", f"Không thể áp dụng cho tất cả slot: {e_all}", parent=dlg)

    btn_apply_devil_all = ctk.CTkButton(
        ds_card,
        text="👥 Áp dụng cấu hình Devil này cho TẤT CẢ các slot",
        height=26,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        fg_color="#4c0519",
        hover_color="#881337",
        text_color="#f43f5e",
        command=_apply_devil_to_all_slots
    )
    btn_apply_devil_all.pack(fill="x", padx=12, pady=(0, 10))

    # 2. Reset Section
    rs_card = ctk.CTkFrame(content, fg_color="#141722", corner_radius=8, border_width=1, border_color="#242b3a")
    rs_card.pack(fill="x", pady=(0, 10), padx=4)

    rs_header = ctk.CTkLabel(
        rs_card,
        text="🔄 TỰ ĐỘNG RESET KHI ĐẠT LEVEL",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#10b981"
    )
    rs_header.pack(anchor="w", padx=12, pady=(8, 2))

    var_rs = ctk.BooleanVar(value=ctrl.auto_reset)
    chk_rs = ctk.CTkCheckBox(
        rs_card,
        text="Kích hoạt tự động gửi lệnh /reset khi đạt cấp độ yêu cầu",
        variable=var_rs,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f1f5f9",
        fg_color="#059669",
        hover_color="#047857"
    )
    chk_rs.pack(anchor="w", padx=12, pady=(0, 6))

    row_rs_lvl = ctk.CTkFrame(rs_card, fg_color="transparent")
    row_rs_lvl.pack(fill="x", padx=12, pady=(0, 10))

    ctk.CTkLabel(row_rs_lvl, text="Cấp độ Reset:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#cbd5e1").pack(side="left")
    ent_rs_lvl = ctk.CTkEntry(row_rs_lvl, width=70, height=26, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
    ent_rs_lvl.pack(side="left", padx=8)
    ent_rs_lvl.insert(0, str(ctrl.reset_level or 400))
    ctk.CTkLabel(row_rs_lvl, text="(Mặc định: 400)", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#64748b").pack(side="left")

    # 3. Stat Ratio Section - THEO CLASS & TÙY CHỌN RIÊNG
    stat_card = ctk.CTkFrame(content, fg_color="#141722", corner_radius=8, border_width=1, border_color="#242b3a")
    stat_card.pack(fill="x", pady=(0, 10), padx=4)

    stat_header = ctk.CTkLabel(
        stat_card,
        text="⭐ CẤU HÌNH CỘNG POINT THEO CLASS & TÙY CHỈNH",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#38bdf8"
    )
    stat_header.pack(anchor="w", padx=12, pady=(8, 2))

    var_stat = ctk.BooleanVar(value=ctrl.auto_add_point)
    chk_stat = ctk.CTkCheckBox(
        stat_card,
        text="Kích hoạt tự động cộng điểm point khi có điểm dư (>= 10 pts)",
        variable=var_stat,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f1f5f9",
        fg_color="#0284c7",
        hover_color="#0369a1"
    )
    chk_stat.pack(anchor="w", padx=12, pady=(0, 8))

    # Chọn Chế Độ: Theo Class (Auto) hoặc Tùy Chỉnh (Custom)
    cur_mode = ctrl.stat_mode if getattr(ctrl, "stat_mode", None) in ("auto_class", "custom") else "auto_class"
    var_mode = ctk.StringVar(value="Theo Class (Tự Động)" if cur_mode == "auto_class" else "Tùy Chỉnh Riêng")

    mode_frame = ctk.CTkFrame(stat_card, fg_color="#181c26", corner_radius=6)
    mode_frame.pack(fill="x", padx=12, pady=(0, 8))

    ctk.CTkLabel(mode_frame, text="Chế độ:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(8, 4), pady=6)

    seg_mode = ctk.CTkSegmentedButton(
        mode_frame,
        values=["Theo Class (Tự Động)", "Tùy Chỉnh Riêng"],
        variable=var_mode,
        height=26,
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        selected_color="#0284c7",
        selected_hover_color="#0369a1",
        unselected_color="#242b3a",
        unselected_hover_color="#334155"
    )
    seg_mode.pack(side="left", padx=4, pady=6)

    # Dropdown Class
    class_options = [f"{code} - {CLASS_CODE_TO_NAME.get(code, code)}" for code in CLASS_ID_TO_CODE.values()]
    init_sel_class = f"{det_code} - {det_fullname}"
    if init_sel_class not in class_options:
        init_sel_class = class_options[0]

    var_sel_class = ctk.StringVar(value=init_sel_class)
    combo_class = ctk.CTkOptionMenu(
        mode_frame,
        values=class_options,
        variable=var_sel_class,
        width=210,
        height=26,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        fg_color="#242b3a",
        button_color="#334155"
    )
    combo_class.pack(side="right", padx=8, pady=6)

    lbl_mode_hint = ctk.CTkLabel(
        stat_card,
        text="💡 Chế độ 'Theo Class': Mọi nhân vật thuộc Class này sẽ tự động nhận tỷ lệ đã cấu hình.",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#38bdf8"
    )
    lbl_mode_hint.pack(anchor="w", padx=12, pady=(0, 6))

    def _on_mode_change(val):
        if val == "Theo Class (Tự Động)":
            lbl_mode_hint.configure(
                text="💡 Chế độ 'Theo Class': Hệ thống tự phát hiện Class của nhân vật từ RAM và áp dụng đúng tỷ lệ.",
                text_color="#38bdf8"
            )
            btn_save_class.configure(state="normal")
        else:
            lbl_mode_hint.configure(
                text="⚠️ Chế độ 'Tùy Chỉnh Riêng': Áp dụng tỷ lệ nhập bên dưới riêng cho Slot này (bỏ qua Class).",
                text_color="#f59e0b"
            )

    seg_mode.configure(command=_on_mode_change)

    # Lưới nhập % Stat
    stat_entries = {}
    grid_frame = ctk.CTkFrame(stat_card, fg_color="transparent")
    grid_frame.pack(fill="x", padx=12, pady=(0, 8))

    # Lấy tỷ lệ ban đầu
    init_ratio = ctrl.stat_ratio
    if cur_mode == "auto_class" and det_code in class_profiles:
        init_ratio = class_profiles[det_code].get("stat_ratio", init_ratio)
    if not init_ratio:
        init_ratio = {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0}

    labels = [
        ("str", "Sức mạnh (Str /f):", int(init_ratio.get("str", 0.4) * 100)),
        ("agi", "Nhanh nhẹn (Agi /a):", int(init_ratio.get("agi", 0.4) * 100)),
        ("vit", "Thể lực (Vit /v):", int(init_ratio.get("vit", 0.1) * 100)),
        ("ene", "Năng lượng (Ene /e):", int(init_ratio.get("ene", 0.1) * 100)),
        ("cmd", "Mệnh lệnh DL (Cmd /c):", int(init_ratio.get("cmd", 0.0) * 100)),
    ]

    for r_idx, (key, title, val) in enumerate(labels):
        lbl_item = ctk.CTkLabel(grid_frame, text=title, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#cbd5e1", width=160, anchor="w")
        lbl_item.grid(row=r_idx, column=0, pady=2, sticky="w")

        ent_item = ctk.CTkEntry(grid_frame, width=65, height=26, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
        ent_item.grid(row=r_idx, column=1, pady=2, padx=(4, 6))
        ent_item.insert(0, str(val))
        stat_entries[key] = ent_item

        unit_lbl = ctk.CTkLabel(grid_frame, text="%", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8")
        unit_lbl.grid(row=r_idx, column=2, pady=2, sticky="w")

    def _apply_stats(s, a, v, e, c):
        stat_entries["str"].delete(0, "end"); stat_entries["str"].insert(0, str(s))
        stat_entries["agi"].delete(0, "end"); stat_entries["agi"].insert(0, str(a))
        stat_entries["vit"].delete(0, "end"); stat_entries["vit"].insert(0, str(v))
        stat_entries["ene"].delete(0, "end"); stat_entries["ene"].insert(0, str(e))
        stat_entries["cmd"].delete(0, "end"); stat_entries["cmd"].insert(0, str(c))

    def _on_class_selected(val):
        code = val.split(" - ")[0].strip()
        # Nạp tươi từ file để luôn đồng bộ mới nhất
        fresh_p = ConfigPersistenceManager.load_class_stat_profiles()
        if code in fresh_p:
            r = fresh_p[code].get("stat_ratio", {})
            _apply_stats(
                int(r.get("str", 0.0) * 100),
                int(r.get("agi", 0.0) * 100),
                int(r.get("vit", 0.0) * 100),
                int(r.get("ene", 0.0) * 100),
                int(r.get("cmd", 0.0) * 100)
            )
        btn_save_class.configure(text=f"💾 Lưu Cấu Hình Chuẩn Cho Class [{code}]")

    combo_class.configure(command=_on_class_selected)

    # Nút presets
    preset_row = ctk.CTkFrame(stat_card, fg_color="transparent")
    preset_row.pack(fill="x", padx=12, pady=(0, 6))

    btn_p1 = ctk.CTkButton(preset_row, text="Chiến (50/50)", width=75, height=22, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color="#181c26", hover_color="#242b3a", command=lambda: _apply_stats(50, 50, 0, 0, 0))
    btn_p1.pack(side="left", padx=2)
    btn_p2 = ctk.CTkButton(preset_row, text="Phép (70/30)", width=75, height=22, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color="#181c26", hover_color="#242b3a", command=lambda: _apply_stats(0, 30, 0, 70, 0))
    btn_p2.pack(side="left", padx=2)
    btn_p3 = ctk.CTkButton(preset_row, text="Elf Cung", width=65, height=22, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color="#181c26", hover_color="#242b3a", command=lambda: _apply_stats(15, 80, 5, 0, 0))
    btn_p3.pack(side="left", padx=2)
    btn_p4 = ctk.CTkButton(preset_row, text="Chúa Tể DL", width=75, height=22, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color="#181c26", hover_color="#242b3a", command=lambda: _apply_stats(30, 30, 0, 10, 30))
    btn_p4.pack(side="left", padx=2)
    btn_p5 = ctk.CTkButton(preset_row, text="Cân Bằng", width=65, height=22, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color="#181c26", hover_color="#242b3a", command=lambda: _apply_stats(40, 40, 10, 10, 0))
    btn_p5.pack(side="left", padx=2)

    # Hàng mốc điểm tối thiểu
    min_pts_row = ctk.CTkFrame(stat_card, fg_color="transparent")
    min_pts_row.pack(fill="x", padx=12, pady=(0, 6))
    ctk.CTkLabel(min_pts_row, text="Cộng khi có tối thiểu:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#cbd5e1").pack(side="left")
    ent_min_pts = ctk.CTkEntry(min_pts_row, width=50, height=24, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
    ent_min_pts.pack(side="left", padx=6)
    ent_min_pts.insert(0, "1")
    ctk.CTkLabel(min_pts_row, text="điểm point (Khuyên dùng: 1 điểm để tăng sức mạnh ngay)", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#94a3b8").pack(side="left")

    # Nút lưu làm mặc định cho Class
    def _save_as_class_default():
        try:
            sel_code = var_sel_class.get().split(" - ")[0].strip()
            raw_s = float(stat_entries["str"].get().strip() or 0)
            raw_a = float(stat_entries["agi"].get().strip() or 0)
            raw_v = float(stat_entries["vit"].get().strip() or 0)
            raw_e = float(stat_entries["ene"].get().strip() or 0)
            raw_c = float(stat_entries["cmd"].get().strip() or 0)
            tot = raw_s + raw_a + raw_v + raw_e + raw_c
            if tot <= 0: tot = 100.0
            new_r = {
                "str": round(raw_s / tot, 3),
                "agi": round(raw_a / tot, 3),
                "vit": round(raw_v / tot, 3),
                "ene": round(raw_e / tot, 3),
                "cmd": round(raw_c / tot, 3),
            }
            ConfigPersistenceManager.save_class_stat_profile(sel_code, new_r)
            fresh_profiles = ConfigPersistenceManager.load_class_stat_profiles()
            ctrl.stat_mode = "auto_class"
            ctrl.custom_class = sel_code
            ctrl.stat_ratio = new_r
            d_min_rs = int(ent_ds_min_rs.get().strip() or 0)
            d_max_rs = int(ent_ds_max_rs.get().strip() or 9999)
            ctrl.devil_min_resets = d_min_rs
            ctrl.devil_max_resets = d_max_rs
            ConfigPersistenceManager.save_event_config(
                slot_idx=slot_idx,
                auto_devil=var_ds.get(),
                devil_min_resets=d_min_rs,
                devil_max_resets=d_max_rs,
                auto_reset=var_rs.get(),
                auto_add_point=var_stat.get(),
                reset_level=int(ent_rs_lvl.get().strip() or 400),
                stat_mode="auto_class",
                custom_class=sel_code,
                stat_ratio=new_r
            )
            if ctrl.worker and ctrl.worker.running and hasattr(ctrl.worker, 'update_config'):
                ctrl.worker.update_config({
                    "stat_mode": "auto_class",
                    "custom_class": sel_code,
                    "stat_ratio": new_r,
                    "min_add_points": 1,
                    "class_profiles": fresh_profiles
                })
            self.log_message(f"Đã lưu tỷ lệ Point chuẩn cho Class [{sel_code}]: {new_r}", "SUCCESS")
            messagebox.showinfo("Thành Công", f"Đã lưu tỷ lệ chuẩn cho Class [{sel_code}]!\n\nMọi nhân vật mang Class [{sel_code}] sẽ tự động áp dụng tỷ lệ này khi cắm auto.\nWorker đang chạy đã được cập nhật ngay lập tức.")
        except Exception as e_cd:
            messagebox.showerror("Lỗi", f"Không thể lưu mặc định Class: {e_cd}")

    btn_save_class = ctk.CTkButton(
        stat_card,
        text=f"💾 Lưu Cấu Hình Chuẩn Cho Class [{det_code}]",
        height=28,
        fg_color="#0f766e",
        hover_color="#115e59",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=_save_as_class_default
    )
    btn_save_class.pack(fill="x", padx=12, pady=(0, 10))

    # Footer Buttons
    footer = ctk.CTkFrame(dlg, fg_color="#141722", height=50, corner_radius=0)
    footer.pack(fill="x", side="bottom")

    def _save_and_close():
        try:
            new_ds = var_ds.get()
            new_rs = var_rs.get()
            new_stat = var_stat.get()
            try:
                new_rs_lvl = int(ent_rs_lvl.get().strip())
            except Exception:
                new_rs_lvl = 400

            try:
                new_min_pts = int(ent_min_pts.get().strip() or 1)
            except Exception:
                new_min_pts = 1

            sel_code = var_sel_class.get().split(" - ")[0].strip()
            raw_s = float(stat_entries["str"].get().strip() or 0)
            raw_a = float(stat_entries["agi"].get().strip() or 0)
            raw_v = float(stat_entries["vit"].get().strip() or 0)
            raw_e = float(stat_entries["ene"].get().strip() or 0)
            raw_c = float(stat_entries["cmd"].get().strip() or 0)
            total = raw_s + raw_a + raw_v + raw_e + raw_c
            if total <= 0:
                new_ratio = {"str": 0.4, "agi": 0.4, "vit": 0.1, "ene": 0.1, "cmd": 0.0}
            else:
                new_ratio = {
                    "str": round(raw_s / total, 3),
                    "agi": round(raw_a / total, 3),
                    "vit": round(raw_v / total, 3),
                    "ene": round(raw_e / total, 3),
                    "cmd": round(raw_c / total, 3),
                }

            is_auto_class = (var_mode.get() == "Theo Class (Tự Động)")
            applied_mode = "auto_class" if is_auto_class else "custom"

            if is_auto_class:
                # Tự động lưu luôn vào class_stat_profiles để mọi nhân vật Class này nhận
                ConfigPersistenceManager.save_class_stat_profile(sel_code, new_ratio)

            fresh_profiles = ConfigPersistenceManager.load_class_stat_profiles()

            d_min_rs = int(ent_ds_min_rs.get().strip() or 0)
            d_max_rs = int(ent_ds_max_rs.get().strip() or 9999)
            t_ch = cbo_ds_ticket.get()
            d_pref = "master" if ("Master" in t_ch and "Chỉ" in t_ch) else ("normal" if ("Thường" in t_ch and "Chỉ" in t_ch) else "auto")
            ctrl.devil_min_resets = d_min_rs
            ctrl.devil_max_resets = d_max_rs
            ctrl.devil_ticket_type = d_pref
            ctrl.auto_devil = new_ds
            ctrl.auto_reset = new_rs
            ctrl.auto_add_point = new_stat
            ctrl.reset_level = new_rs_lvl
            ctrl.stat_mode = applied_mode
            ctrl.custom_class = sel_code
            ctrl.stat_ratio = new_ratio

            ConfigPersistenceManager.save_event_config(
                slot_idx=slot_idx,
                auto_devil=new_ds,
                devil_min_resets=d_min_rs,
                devil_max_resets=d_max_rs,
                devil_ticket_type=d_pref,
                auto_reset=new_rs,
                auto_add_point=new_stat,
                reset_level=new_rs_lvl,
                stat_mode=applied_mode,
                custom_class=sel_code,
                stat_ratio=new_ratio
            )

            if ctrl.worker and ctrl.worker.running and hasattr(ctrl.worker, 'update_config'):
                ctrl.worker.update_config({
                    "auto_devil": new_ds,
                    "devil_min_resets": d_min_rs,
                    "devil_max_resets": d_max_rs,
                    "devil_ticket_type": d_pref,
                    "auto_reset": new_rs,
                    "auto_add_point": new_stat,
                    "reset_level": new_rs_lvl,
                    "stat_mode": applied_mode,
                    "custom_class": sel_code,
                    "stat_ratio": new_ratio,
                    "min_add_points": new_min_pts,
                    "class_profiles": fresh_profiles
                })

            el = self.slot_ui_elements.get(slot_idx)
            if el:
                if el.get("btn_devil"):
                    if new_ds:
                        el["btn_devil"].configure(fg_color="#4c0519", text_color="#f43f5e", border_color="#e11d48", hover_color="#881337")
                    else:
                        el["btn_devil"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")
                if el.get("btn_reset"):
                    if new_rs:
                        el["btn_reset"].configure(fg_color="#064e3b", text_color="#10b981", border_color="#059669", hover_color="#047857")
                    else:
                        el["btn_reset"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")
                if el.get("btn_point"):
                    if new_stat:
                        el["btn_point"].configure(fg_color="#075985", text_color="#38bdf8", border_color="#0284c7", hover_color="#0369a1")
                    else:
                        el["btn_point"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")

            mode_text = f"Theo Class [{sel_code}]" if is_auto_class else "Tùy Chỉnh Riêng"
            self.log_message(f"[Slot {slot_idx:02d}] Đã lưu cài đặt ({mode_text}): DS={new_ds}, RS={new_rs} (LV {new_rs_lvl}), Point={new_stat} (Str:{int(new_ratio['str']*100)}%, Agi:{int(new_ratio['agi']*100)}%, Vit:{int(new_ratio['vit']*100)}%, Ene:{int(new_ratio['ene']*100)}%, Cmd:{int(new_ratio['cmd']*100)}%).", "SUCCESS")
            dlg.destroy()
        except Exception as ex:
            messagebox.showerror("Lỗi Cài Đặt", f"Không thể lưu cài đặt: {ex}")

    btn_save = ctk.CTkButton(
        footer,
        text="Lưu & Áp Dụng",
        width=160,
        height=32,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=_save_and_close
    )
    btn_save.pack(side="right", padx=16, pady=9)

    btn_cancel = ctk.CTkButton(
        footer,
        text="Hủy Bỏ",
        width=80,
        height=32,
        fg_color="#1e293b",
        hover_color="#334155",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        command=dlg.destroy
    )
    btn_cancel.pack(side="right", padx=8, pady=9)

