"""
UI Modal: Devil Square Global Config Dialog.
"""

from typing import Any
import customtkinter as ctk
from core.storage import ConfigPersistenceManager
from ui.components.icons import UiIconFactory

def open_devil_global_config_dialog(self):
    """Mở cửa sổ cấu hình tập trung cho tính năng Auto Devil Square (DS)."""
    dlg = ctk.CTkToplevel(self)
    dlg.title("Cài Đặt Tự Động Đi Devil Square (DS)")
    dlg.geometry("520x470")
    dlg.resizable(False, False)
    dlg.grab_set()

    # Tiêu đề
    header_frame = ctk.CTkFrame(dlg, fg_color="#141722", corner_radius=8, border_width=1, border_color="#242b3a")
    header_frame.pack(fill="x", padx=16, pady=(16, 10))

    title_lbl = ctk.CTkLabel(
        header_frame,
        text="🔥 CẤU HÌNH TỰ ĐỘNG THAM GIA DEVIL SQUARE (DS)",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#f43f5e"
    )
    title_lbl.pack(anchor="w", padx=14, pady=(10, 4))

    sub_lbl = ctk.CTkLabel(
        header_frame,
        text="Thiết lập số Reset bắt đầu đi Devil và loại vé. Áp dụng ngay cho toàn bộ tài khoản.",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#94a3b8"
    )
    sub_lbl.pack(anchor="w", padx=14, pady=(0, 10))

    # Thân hộp thoại
    body = ctk.CTkFrame(dlg, fg_color="#141722", corner_radius=8, border_width=1, border_color="#242b3a")
    body.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    # 1. Bật / Tắt chung
    var_enable_all = ctk.BooleanVar(value=any(getattr(c, "auto_devil", False) for c in self.controllers))
    chk_enable = ctk.CTkCheckBox(
        body,
        text="Kích hoạt Tự Động Đi Devil Square cho toàn bộ tài khoản",
        variable=var_enable_all,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f1f5f9",
        fg_color="#e11d48",
        hover_color="#be123c"
    )
    chk_enable.pack(anchor="w", padx=16, pady=(14, 10))

    # 2. Điều kiện Reset: "Bao nhiêu Reset thì mới bắt đầu đi Devil?"
    rs_frame = ctk.CTkFrame(body, fg_color="#0e1117", corner_radius=6, border_width=1, border_color="#1e2433")
    rs_frame.pack(fill="x", padx=16, pady=(0, 10))

    rs_label_title = ctk.CTkLabel(
        rs_frame,
        text="🎯 ĐIỀU KIỆN SỐ RESET ĐỂ BẮT ĐẦU ĐI DEVIL:",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#38bdf8"
    )
    rs_label_title.pack(anchor="w", padx=12, pady=(8, 4))

    rs_input_row = ctk.CTkFrame(rs_frame, fg_color="transparent")
    rs_input_row.pack(fill="x", padx=12, pady=(0, 4))

    ctk.CTkLabel(
        rs_input_row,
        text="Bắt đầu đi Devil khi đạt từ:",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#cbd5e1"
    ).pack(side="left")

    first_min_rs = getattr(self.controllers[0], "devil_min_resets", 0) if self.controllers else 0
    ent_min_rs = ctk.CTkEntry(
        rs_input_row,
        width=65,
        height=28,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        justify="center"
    )
    ent_min_rs.pack(side="left", padx=(8, 6))
    ent_min_rs.insert(0, str(first_min_rs))

    ctk.CTkLabel(
        rs_input_row,
        text="Reset trở lên",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#facc15"
    ).pack(side="left")

    rs_note = ctk.CTkLabel(
        rs_frame,
        text="💡 Dưới số Reset này: Nhân vật sẽ KHÔNG đi Devil mà chỉ cắm bãi Auto Train.\n"
             "   Khi đạt từ số Reset này trở lên: Mới tự động tham gia Devil khi mở cổng.",
        font=ctk.CTkFont(family="Segoe UI", size=9),
        text_color="#94a3b8",
        justify="left"
    )
    rs_note.pack(anchor="w", padx=12, pady=(0, 8))

    # 3. Lựa chọn loại vé
    ticket_frame = ctk.CTkFrame(body, fg_color="#0e1117", corner_radius=6, border_width=1, border_color="#1e2433")
    ticket_frame.pack(fill="x", padx=16, pady=(0, 10))

    ctk.CTkLabel(
        ticket_frame,
        text="🎫 LOẠI VÉ SỬ DỤNG:",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#38bdf8"
    ).pack(anchor="w", padx=12, pady=(8, 4))

    ticket_row = ctk.CTkFrame(ticket_frame, fg_color="transparent")
    ticket_row.pack(fill="x", padx=12, pady=(0, 8))

    t_opts = [
        "🎫 Tự động (Ưu tiên Vé Master)",
        "🎫 Chỉ đi Vé Thường (DS 1 - 7)",
        "🎫 Chỉ đi Vé Master (Master DS)"
    ]
    curr_t = getattr(self.controllers[0], "devil_ticket_type", "auto") if self.controllers else "auto"
    sel_t = t_opts[0]
    if curr_t == "master":
        sel_t = t_opts[2]
    elif curr_t == "normal":
        sel_t = t_opts[1]

    cbo_ticket = ctk.CTkOptionMenu(
        ticket_row,
        values=t_opts,
        width=260,
        height=28,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        fg_color="#1e293b",
        button_color="#334155"
    )
    cbo_ticket.set(sel_t)
    cbo_ticket.pack(side="left")

    # 4. Thông tin lịch trình & Nguyên tắc an toàn
    info_frame = ctk.CTkFrame(body, fg_color="#080c14", corner_radius=6, border_width=1, border_color="#1a202c")
    info_frame.pack(fill="x", padx=16, pady=(0, 8))

    info_lbl = ctk.CTkLabel(
        info_frame,
        text="⏰ Lịch mở cổng MEGAMU: 2 tiếng/lần vào giờ lẻ (:27 - :30) • 12 đợt/ngày.\n"
             "🛡️ Nguyên tắc an toàn: Chỉ ngưng train khi ĐÃ VÀO MAP DEVIL thành công.\n"
             "   Nếu chưa đủ Reset, không có vé hoặc không vào được: tiếp tục cắm bãi train.",
        font=ctk.CTkFont(family="Segoe UI", size=9),
        text_color="#94a3b8",
        justify="left"
    )
    info_lbl.pack(anchor="w", padx=10, pady=6)

    # Nút Lưu
    btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_box.pack(fill="x", padx=16, pady=(0, 14))

    def _save_devil_global():
        try:
            en = var_enable_all.get()
            m_rs = int(ent_min_rs.get().strip() or 0)
            t_str = cbo_ticket.get()
            t_pref = "master" if ("Master" in t_str and "Chỉ" in t_str) else ("normal" if ("Thường" in t_str and "Chỉ" in t_str) else "auto")

            for c in self.controllers:
                c.auto_devil = en
                c.devil_min_resets = m_rs
                c.devil_max_resets = 9999
                c.devil_ticket_type = t_pref
                ConfigPersistenceManager.save_event_config(
                    slot_idx=c.slot_idx,
                    auto_devil=en,
                    devil_min_resets=m_rs,
                    devil_max_resets=9999,
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
                        "auto_devil": en,
                        "devil_min_resets": m_rs,
                        "devil_max_resets": 9999,
                        "devil_ticket_type": t_pref
                    })
                el = self.slot_ui_elements.get(c.slot_idx)
                if el and el.get("btn_devil"):
                    if en:
                        el["btn_devil"].configure(fg_color="#4c0519", text_color="#f43f5e", border_color="#e11d48", hover_color="#881337")
                    else:
                        el["btn_devil"].configure(fg_color="#181c26", text_color="#64748b", border_color="#2b3244", hover_color="#242b3a")

            st = "BẬT" if en else "TẮT"
            t_lbl = "Vé Master" if t_pref == "master" else ("Vé Thường" if t_pref == "normal" else "Tự động")
            self.log_message(f"🔥 Đã cập nhật Auto Devil: [{st}] | Bắt đầu đi từ: >= {m_rs} Reset | Loại vé: {t_lbl} cho toàn bộ tài khoản!", "SUCCESS")
            from tkinter import messagebox
            messagebox.showinfo("Thành Công", f"Đã lưu cấu hình Devil Square cho toàn bộ tài khoản:\n• Trạng thái: {st}\n• Bắt đầu đi từ: >= {m_rs} Reset\n• Loại vé: {t_lbl}", parent=dlg)
            dlg.destroy()
        except Exception as ex:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {ex}", parent=dlg)

    btn_save = ctk.CTkButton(
        btn_box,
        text="💾 Áp Dụng Cho Tất Cả Tài Khoản",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        height=34,
        fg_color="#e11d48",
        hover_color="#be123c",
        command=_save_devil_global
    )
    btn_save.pack(side="left", fill="x", expand=True, padx=(0, 8))

    btn_cancel = ctk.CTkButton(
        btn_box,
        text="Đóng",
        font=ctk.CTkFont(family="Segoe UI", size=12),
        height=34,
        width=90,
        fg_color="#27272a",
        hover_color="#3f3f46",
        command=dlg.destroy
    )
    btn_cancel.pack(side="right")

