"""
UI Modal: Mandatory Update Dialog.
"""

import os
import sys
import threading
import time
import urllib.request
import subprocess
from tkinter import messagebox
from typing import Any, Dict, Optional
import customtkinter as ctk
from PIL import Image

from ui.components.icons import UiIconFactory

APP_NAME = "MEGAMU Auto Train"
APP_VERSION = "v1.5.7"

def open_update_dialog(self):
    """Mở cửa sổ Cập nhật bắt buộc (Mandatory Update Dialog)."""
    if hasattr(self, "_update_dlg_instance") and self._update_dlg_instance and self._update_dlg_instance.winfo_exists():
        self._update_dlg_instance.lift()
        self._update_dlg_instance.focus_force()
        return

    dialog = ctk.CTkToplevel(self)
    self._update_dlg_instance = dialog
    dialog.title(f"{APP_NAME} - Cập Nhật Phiên Bản Mới")
    dialog.geometry("520x490")
    dialog.resizable(False, False)
    self._apply_window_icon(dialog)

    # Căn giữa màn hình
    dialog.update_idletasks()
    try:
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        w, h = 520, 490
        x = (sw - w) // 2
        y = (sh - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass

    dialog.transient(self)
    dialog.attributes("-topmost", True)
    dialog.grab_set()

    info = self.update_info or {}
    latest_ver = info.get("latest_version", "Mới")
    rel_name = info.get("release_name", f"Bản phát hành {latest_ver}")
    rel_notes = info.get("release_notes", "Đã có phiên bản mới của hệ thống.")
    download_url = info.get("download_url")

    # Khi người dùng cố gắng đóng hộp thoại
    def on_close():
        if getattr(self, "is_update_mandatory", False):
            if messagebox.askyesno(
                "Bắt Buộc Cập Nhật",
                "Chương trình yêu cầu cập nhật bắt buộc lên phiên bản mới nhất để đảm bảo an toàn và tương thích.\n\n"
                "Phiên bản cũ không được phép tiếp tục sử dụng.\n\n"
                "Bạn có muốn thoát chương trình hoàn toàn không?",
                parent=dialog
            ):
                try:
                    dialog.destroy()
                except Exception:
                    pass
                self.on_closing()
                sys.exit(0)
        else:
            dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)

    # UI Content
    # 1. Header Frame
    hdr = ctk.CTkFrame(dialog, fg_color="#181c26", corner_radius=0, height=72)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)

    hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
    hdr_inner.pack(fill="both", expand=True, padx=20, pady=10)

    ctk.CTkLabel(
        hdr_inner,
        text="🏷️ PHÁT HIỆN PHIÊN BẢN MỚI",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color="#f59e0b"
    ).pack(anchor="w")

    ctk.CTkLabel(
        hdr_inner,
        text="Chương trình yêu cầu cập nhật bắt buộc để tiếp tục hoạt động",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#94a3b8"
    ).pack(anchor="w", pady=(2, 0))

    # 2. Main body
    body = ctk.CTkFrame(dialog, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=20, pady=14)

    # Version Badge Row
    ver_card = ctk.CTkFrame(body, fg_color="#141822", border_width=1, border_color="#242b3a", corner_radius=0)
    ver_card.pack(fill="x", pady=(0, 10))

    ver_inner = ctk.CTkFrame(ver_card, fg_color="transparent")
    ver_inner.pack(fill="x", padx=15, pady=10)

    col_curr = ctk.CTkFrame(ver_inner, fg_color="transparent")
    col_curr.pack(side="left", expand=True)
    ctk.CTkLabel(col_curr, text="Phiên bản hiện tại", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#94a3b8").pack()
    ctk.CTkLabel(col_curr, text=APP_VERSION, font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#ef4444").pack()

    ctk.CTkLabel(ver_inner, text="➔", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color="#64748b").pack(side="left", padx=10)

    col_new = ctk.CTkFrame(ver_inner, fg_color="transparent")
    col_new.pack(side="left", expand=True)
    ctk.CTkLabel(col_new, text="Phiên bản mới nhất", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#94a3b8").pack()
    ctk.CTkLabel(col_new, text=latest_ver, font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#10b981").pack()

    # Release Notes Label & Scrollable Text
    ctk.CTkLabel(
        body,
        text=f"Nội dung bản cập nhật ({rel_name}):",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#e2e8f0"
    ).pack(anchor="w", pady=(0, 4))

    notes_box = ctk.CTkTextbox(
        body,
        height=125,
        fg_color="#0d1117",
        border_width=1,
        border_color="#21262d",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#cbd5e1"
    )
    notes_box.pack(fill="x", pady=(0, 10))
    notes_box.insert("1.0", rel_notes.strip() if rel_notes else "Cập nhật tối ưu hóa hệ thống và thuật toán MEGAMU Auto Train.")
    notes_box.configure(state="disabled")

    # Progress / Status Frame
    status_frame = ctk.CTkFrame(body, fg_color="#141822", border_width=1, border_color="#242b3a", corner_radius=0)
    status_frame.pack(fill="x", pady=(0, 10))

    status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
    status_inner.pack(fill="x", padx=12, pady=10)

    lbl_status = ctk.CTkLabel(
        status_inner,
        text="Sẵn sàng cập nhật tự động" if download_url else "Đang chuẩn bị gói cập nhật từ máy chủ...",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#38bdf8" if download_url else "#fbbf24"
    )
    lbl_status.pack(anchor="w")

    pbar = ctk.CTkProgressBar(status_inner, height=8, corner_radius=0)
    pbar.pack(fill="x", pady=(6, 4))
    pbar.set(0.0)

    lbl_detail = ctk.CTkLabel(
        status_inner,
        text=f"Phiên bản: {latest_ver}",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#94a3b8"
    )
    lbl_detail.pack(anchor="w")

    # Action Buttons
    btn_row = ctk.CTkFrame(dialog, fg_color="#181c26", corner_radius=0, height=54)
    btn_row.pack(fill="x", side="bottom")
    btn_row.pack_propagate(False)

    btn_inner = ctk.CTkFrame(btn_row, fg_color="transparent")
    btn_inner.pack(fill="both", expand=True, padx=16, pady=10)

    # Cancel / Exit button
    btn_exit = ctk.CTkButton(
        btn_inner,
        text="Thoát Chương Trình",
        width=140,
        height=32,
        fg_color="#27272a",
        hover_color="#3f3f46",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#f43f5e",
        command=on_close
    )
    btn_exit.pack(side="left")

    # Perform Auto Update
    def start_download_and_update():
        if not download_url:
            lbl_status.configure(
                text="Gói cập nhật tự động đang được chuẩn bị. Vui lòng liên hệ Admin!",
                text_color="#fbbf24"
            )
            return

        btn_update_now.configure(state="disabled", text="⏳ Đang tải...")
        btn_exit.configure(state="disabled")

        def _download_thread():
            target_exe = app_dir() / "temp_update.exe"
            def _prog(dl: int, total: int):
                if total > 0:
                    pct = dl / total
                    mb_dl = dl / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)
                    def _up():
                        pbar.set(pct)
                        lbl_status.configure(text=f"Đang tải xuống: {pct*100:.0f}%")
                        lbl_detail.configure(text=f"{mb_dl:.1f} MB / {mb_tot:.1f} MB")
                    dialog.after(0, _up)

            ok = updater.download_file_with_progress(download_url, target_exe, progress_callback=_prog)
            if ok and target_exe.exists():
                def _applying():
                    lbl_status.configure(text="Tải xong! Đang cài đặt và khởi động lại...", text_color="#10b981")
                    pbar.set(1.0)
                    dialog.after(1000, lambda: updater.apply_exe_update_and_restart(target_exe))
                dialog.after(0, _applying)
            else:
                def _fail():
                    lbl_status.configure(text="❌ Tải cập nhật thất bại!", text_color="#ef4444")
                    btn_update_now.configure(state="normal", text="Thử Lại")
                    btn_exit.configure(state="normal")
                    messagebox.showerror(
                        "Lỗi Cập Nhật",
                        "Không thể tải bản cập nhật tự động. Vui lòng kiểm tra lại kết nối mạng hoặc liên hệ Admin.",
                        parent=dialog
                    )
                dialog.after(0, _fail)

        threading.Thread(target=_download_thread, daemon=True).start()

    btn_update_now = ctk.CTkButton(
        btn_inner,
        text="⬇️ Cập Nhật Tự Động",
        width=160,
        height=32,
        fg_color="#16a34a",
        hover_color="#15803d",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#ffffff",
        command=start_download_and_update
    )
    btn_update_now.pack(side="right")

# ==========================================================================
# TAB 2: CẤU HÌNH (PROFILES TAB)
# ==========================================================================
