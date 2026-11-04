"""
UI Modal: License Management Dialog.
"""

import threading
import time
from tkinter import messagebox
from typing import Any
import customtkinter as ctk
from PIL import Image

try:
    import license_client
except ImportError:
    try:
        from core import license_client
    except ImportError:
        license_client = None

from ui.components.icons import UiIconFactory
from core.constants import LOGO_FILE, ICON_FILE

APP_VERSION = "v1.5.7"

def open_license_dialog(self):
    """Mở cửa sổ quản lý và kích hoạt bản quyền MEGAMU Auto Train Dashboard."""
    if hasattr(self, "_license_dialog") and self._license_dialog is not None and self._license_dialog.winfo_exists():
        self._license_dialog.lift()
        self._license_dialog.focus_force()
        return

    dialog = ctk.CTkToplevel(self)
    self._license_dialog = dialog
    dialog.title("Quản lý Bản Quyền - MEGAMU Auto Train")
    dialog.geometry("510x540")
    dialog.resizable(False, False)
    dialog.configure(fg_color="#0e1117")
    dialog.transient(self)
    dialog.grab_set()

    # Đặt Icon ứng dụng cho cửa sổ dialog quản lý bản quyền
    self._apply_window_icon(dialog)
    dialog.after(50, lambda: self._apply_window_icon(dialog) if dialog.winfo_exists() else None)
    dialog.after(220, lambda: self._apply_window_icon(dialog) if dialog.winfo_exists() else None)
    dialog.after(500, lambda: self._apply_window_icon(dialog) if dialog.winfo_exists() else None)

    try:
        x = self.winfo_x() + (self.winfo_width() // 2) - 255
        y = self.winfo_y() + (self.winfo_height() // 2) - 270
        dialog.geometry(f"+{x}+{y}")
    except Exception:
        pass

    pad = ctk.CTkFrame(dialog, fg_color="transparent")
    pad.pack(fill="both", expand=True, padx=22, pady=18)

    # Header với Logo ứng dụng chính thức
    head_box = ctk.CTkFrame(pad, fg_color="transparent")
    head_box.pack(fill="x", pady=(0, 12))

    if LOGO_FILE.exists():
        try:
            logo_img = Image.open(str(LOGO_FILE))
            lw, lh = logo_img.size
            aspect = lw / max(1, lh)
            target_h = 36
            target_w = int(target_h * aspect)
            self._lic_dialog_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(target_w, target_h))
            ctk.CTkLabel(head_box, image=self._lic_dialog_logo, text="").pack(side="left", padx=(0, 12))
        except Exception:
            pass
    elif ICON_FILE.exists():
        try:
            ico_img = Image.open(str(ICON_FILE))
            self._lic_dialog_logo = ctk.CTkImage(light_image=ico_img, dark_image=ico_img, size=(36, 36))
            ctk.CTkLabel(head_box, image=self._lic_dialog_logo, text="").pack(side="left", padx=(0, 12))
        except Exception:
            pass

    title_text_box = ctk.CTkFrame(head_box, fg_color="transparent")
    title_text_box.pack(side="left", fill="both", expand=True)

    ctk.CTkLabel(
        title_text_box,
        text="QUẢN LÝ BẢN QUYỀN SẢN PHẨM",
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color="#f8fafc"
    ).pack(anchor="w")

    ctk.CTkLabel(
        title_text_box,
        text="Hệ thống xác thực bản quyền & HWID định danh máy tính",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#64748b"
    ).pack(anchor="w", pady=(1, 0))

    # HWID Card
    hwid_card = ctk.CTkFrame(pad, fg_color="#161b26", corner_radius=0, border_width=1, border_color="#232936")
    hwid_card.pack(fill="x", pady=(0, 10))

    hwid_inner = ctk.CTkFrame(hwid_card, fg_color="transparent")
    hwid_inner.pack(fill="x", padx=12, pady=8)

    ctk.CTkLabel(
        hwid_inner,
        text="MÃ ĐỊNH DANH MÁY (HWID):",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#94a3b8"
    ).pack(anchor="w")

    hwid_row = ctk.CTkFrame(hwid_inner, fg_color="transparent")
    hwid_row.pack(fill="x", pady=(3, 0))

    if license_client:
        license_client.is_native_bridge_active(force_reload=True)
    hwid_val = license_client.get_machine_hwid() if license_client else "N/A"
    hwid_is_err = (hwid_val == "THIẾU_MEG_LICENSE_BRIDGE_DLL")
    hwid_display = "⚠️ Thiếu file meg_license_bridge.dll" if hwid_is_err else hwid_val
    hwid_lbl = ctk.CTkLabel(
        hwid_row,
        text=hwid_display,
        font=ctk.CTkFont(family="Consolas", size=12 if hwid_is_err else 13, weight="bold"),
        text_color="#f87171" if hwid_is_err else "#38bdf8"
    )
    hwid_lbl.pack(side="left")

    def copy_hwid():
        cur_h = license_client.get_machine_hwid() if license_client else ""
        if cur_h and cur_h != "THIẾU_MEG_LICENSE_BRIDGE_DLL":
            self.clipboard_clear()
            self.clipboard_append(cur_h)
            copy_btn.configure(text="Đã chép!", fg_color="#16a34a")
            self.after(1500, lambda: copy_btn.configure(text="Sao chép", fg_color="#242b3a"))

    copy_btn = ctk.CTkButton(
        hwid_row,
        text="Sao chép",
        width=70,
        height=24,
        corner_radius=0,
        fg_color="#242b3a",
        hover_color="#333c52",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#e2e8f0",
        command=copy_hwid
    )
    copy_btn.pack(side="right")

    # Tự động quét phát hiện file DLL khi người dùng vừa dán / copy file vào thư mục
    def _poll_dll_in_dialog():
        if not dialog.winfo_exists():
            return
        try:
            if license_client:
                was_missing = not license_client.is_native_bridge_active()
                if was_missing and license_client.is_native_bridge_active(force_reload=True):
                    new_hwid = license_client.get_machine_hwid()
                    hwid_lbl.configure(text=new_hwid, text_color="#38bdf8", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"))
                    self.update_header_stats()
        except Exception:
            pass
        dialog.after(1000, _poll_dll_in_dialog)

    dialog.after(1000, _poll_dll_in_dialog)

    # Current Status Card
    lic_data = license_client.load_license_data() if license_client else {}
    status_card = ctk.CTkFrame(pad, fg_color="#161b26", corner_radius=0, border_width=1, border_color="#232936")
    status_card.pack(fill="x", pady=(0, 12))

    status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
    status_inner.pack(fill="x", padx=12, pady=8)

    plan_type = lic_data.get("plan_type", "Chưa kích hoạt")
    if lic_data.get("is_lifetime"):
        exp_date = "Vĩnh viễn"
    else:
        exp_date = lic_data.get("expires_at", "--")
        if exp_date and exp_date != "--":
            exp_date = str(exp_date).split(" ")[0]
        elif not exp_date:
            exp_date = "--"
    is_active = bool(lic_data.get("license_key") and (lic_data.get("valid", True) or lic_data.get("is_lifetime")))

    stat_title = "Trạng thái: " + ("ĐÃ KÍCH HOẠT (VĨNH VIỄN)" if lic_data.get("is_lifetime") else ("ĐÃ KÍCH HOẠT" if is_active else "CHƯA KÍCH HOẠT"))
    stat_color = "#4ade80" if is_active else "#f87171"

    status_lbl = ctk.CTkLabel(
        status_inner,
        text=stat_title,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color=stat_color
    )
    status_lbl.pack(anchor="w")

    details_lbl = ctk.CTkLabel(
        status_inner,
        text=f"Gói dịch vụ: {plan_type}   |   Hạn dùng: {exp_date}   |   Slot tối đa: {lic_data.get('max_slots', 50)}",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#94a3b8"
    )
    details_lbl.pack(anchor="w", pady=(2, 0))

    # Input License Key
    ctk.CTkLabel(
        pad,
        text="NHẬP KEY BẢN QUYỀN MỚI:",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#94a3b8"
    ).pack(anchor="w", pady=(0, 4))

    key_entry = ctk.CTkEntry(
        pad,
        placeholder_text="Ví dụ: MEG-MEGATEAM-2026-VIP1",
        height=34,
        corner_radius=0,
        fg_color="#181c26",
        border_color="#2c3345",
        font=ctk.CTkFont(family="Consolas", size=12),
        text_color="#f8fafc"
    )
    key_entry.pack(fill="x", pady=(0, 6))
    if lic_data.get("license_key"):
        key_entry.insert(0, lic_data.get("license_key"))

    msg_lbl = ctk.CTkLabel(pad, text="", font=ctk.CTkFont(family="Segoe UI", size=10))
    msg_lbl.pack(anchor="w", pady=(0, 4))

    # Action Buttons
    btn_box = ctk.CTkFrame(pad, fg_color="transparent")
    btn_box.pack(fill="x", pady=(4, 0))

    def do_activate():
        input_key = key_entry.get().strip()
        if not input_key:
            msg_lbl.configure(text="Vui lòng nhập mã key bản quyền!", text_color="#f87171")
            return

        act_btn.configure(state="disabled", text="Đang kích hoạt...")
        msg_lbl.configure(text="Đang kết nối tới máy chủ...", text_color="#94a3b8")
        dialog.update_idletasks()

        def _run():
            success, msg, info = license_client.activate_license(input_key)
            def _done():
                act_btn.configure(state="normal", text="Kích Hoạt")
                if success:
                    msg_lbl.configure(text=f"✓ {msg}", text_color="#4ade80")
                    status_lbl.configure(text="Trạng thái: ĐÃ KÍCH HOẠT", text_color="#4ade80")
                    new_plan = info.get("plan_type", "Pro")
                    new_exp = "Vĩnh viễn" if info.get("is_lifetime") else str(info.get("expires_at", "--")).split(" ")[0]
                    details_lbl.configure(
                        text=f"Gói dịch vụ: {new_plan}   |   Hạn dùng: {new_exp}   |   Slot tối đa: {info.get('max_slots', 50)}"
                    )
                    self.update_header_stats()
                    self.update_modules_visibility()
                else:
                    msg_lbl.configure(text=f"✗ {msg}", text_color="#f87171")
            dialog.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    act_btn = ctk.CTkButton(
        btn_box,
        text="Kích Hoạt",
        width=100,
        height=30,
        corner_radius=0,
        fg_color="#0284c7",
        hover_color="#0369a1",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=do_activate
    )
    act_btn.pack(side="left")

    def do_sync():
        act_btn.configure(state="disabled")
        sync_btn.configure(state="disabled", text="Đang đồng bộ...")
        msg_lbl.configure(text="Đang đồng bộ gói dịch vụ và tính năng mới từ máy chủ...", text_color="#94a3b8")
        dialog.update_idletasks()

        def _run_sync():
            ok, msg, info = license_client.verify_license()
            def _done_sync():
                act_btn.configure(state="normal")
                sync_btn.configure(state="normal", text="🔄 Đồng Bộ")
                if ok:
                    msg_lbl.configure(text=f"✓ Đã đồng bộ thành công tính năng mới!", text_color="#4ade80")
                    status_lbl.configure(text="Trạng thái: ĐÃ KÍCH HOẠT", text_color="#4ade80")
                    new_plan = info.get("plan_type", "Pro")
                    new_exp = "Vĩnh viễn" if info.get("is_lifetime") else str(info.get("expires_at", "--")).split(" ")[0]
                    details_lbl.configure(
                        text=f"Gói dịch vụ: {new_plan}   |   Hạn dùng: {new_exp}   |   Slot tối đa: {info.get('max_slots', 50)}"
                    )
                    self.update_header_stats()
                    self.update_modules_visibility()
                else:
                    msg_lbl.configure(text=f"✗ {msg}", text_color="#f87171")
            dialog.after(0, _done_sync)

        threading.Thread(target=_run_sync, daemon=True).start()

    sync_btn = ctk.CTkButton(
        btn_box,
        text="🔄 Đồng Bộ",
        width=100,
        height=30,
        corner_radius=0,
        fg_color="#0f766e",
        hover_color="#115e59",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=do_sync
    )
    sync_btn.pack(side="left", padx=(8, 0))

    def do_deactivate():
        if license_client:
            license_client.deactivate_license()
        key_entry.delete(0, "end")
        msg_lbl.configure(text="✓ Đã bỏ kích hoạt bản quyền trên máy này.", text_color="#facc15")
        status_lbl.configure(text="Trạng thái: CHƯA KÍCH HOẠT", text_color="#f87171")
        details_lbl.configure(text="Gói dịch vụ: Chưa kích hoạt   |   Hạn dùng: --   |   Slot tối đa: --")
        self.update_header_stats()
        self.update_modules_visibility()

    deact_btn = ctk.CTkButton(
        btn_box,
        text="Bỏ Kích Hoạt",
        width=105,
        height=30,
        corner_radius=0,
        fg_color="#7f1d1d",
        hover_color="#991b1b",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#fca5a5",
        command=do_deactivate
    )
    deact_btn.pack(side="left", padx=(8, 0))

    close_btn = ctk.CTkButton(
        btn_box,
        text="Đóng",
        width=70,
        height=30,
        corner_radius=0,
        fg_color="#1e2430",
        hover_color="#283142",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#94a3b8",
        command=dialog.destroy
    )
    close_btn.pack(side="right")

    # Thẻ thông tin liên hệ bản quyền & hỗ trợ kỹ thuật
    contact_card = ctk.CTkFrame(pad, fg_color="#141824", corner_radius=0, border_width=1, border_color="#232a3b")
    contact_card.pack(fill="x", pady=(12, 0))

    contact_inner = ctk.CTkFrame(contact_card, fg_color="transparent")
    contact_inner.pack(fill="x", padx=12, pady=10)

    ctk.CTkLabel(
        contact_inner,
        text="📞 LIÊN HỆ ĐĂNG KÝ BẢN QUYỀN & HỖ TRỢ KỸ THUẬT:",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#38bdf8"
    ).pack(anchor="w")

    info_grid = ctk.CTkFrame(contact_inner, fg_color="transparent")
    info_grid.pack(fill="x", pady=(4, 0))

    ctk.CTkLabel(
        info_grid,
        text="• Tác giả: MEGATEAM   |   • Hotline / Zalo: 036.203.1354",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f8fafc"
    ).pack(anchor="w")

    ctk.CTkLabel(
        contact_inner,
        text="Hỗ trợ kích hoạt nhanh 24/7, gia hạn bản quyền, nâng cấp slot và fix lỗi.",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#64748b"
    ).pack(anchor="w", pady=(2, 6))

    # Nút copy nhanh SĐT / Zalo
    quick_copy_row = ctk.CTkFrame(contact_inner, fg_color="transparent")
    quick_copy_row.pack(fill="x")

    def copy_phone():
        self.clipboard_clear()
        self.clipboard_append("0362031354")
        cp_phone_btn.configure(text="Đã chép SĐT!", fg_color="#16a34a")
        self.after(1500, lambda: cp_phone_btn.configure(text="Sao chép SĐT", fg_color="#1e2430"))

    def copy_zalo():
        self.clipboard_clear()
        self.clipboard_append("0362031354")
        cp_zalo_btn.configure(text="Đã chép Zalo!", fg_color="#16a34a")
        self.after(1500, lambda: cp_zalo_btn.configure(text="Sao chép Zalo", fg_color="#1e2430"))

    cp_phone_btn = ctk.CTkButton(
        quick_copy_row,
        text="Sao chép SĐT",
        width=100,
        height=24,
        corner_radius=0,
        fg_color="#1e2430",
        hover_color="#2b3548",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#93c5fd",
        command=copy_phone
    )
    cp_phone_btn.pack(side="left", padx=(0, 8))

    cp_zalo_btn = ctk.CTkButton(
        quick_copy_row,
        text="Sao chép Zalo",
        width=105,
        height=24,
        corner_radius=0,
        fg_color="#1e2430",
        hover_color="#2b3548",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#67e8f9",
        command=copy_zalo
    )
    cp_zalo_btn.pack(side="left")

