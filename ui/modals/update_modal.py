# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - UPDATE MODAL DIALOG
Hộp thoại thông báo, tải xuống và tự động nâng cấp phiên bản mới (Auto Updater).
"""

import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import tkinter.messagebox as messagebox
import customtkinter as ctk

from ui.theme import Colors, Fonts, Radii
from ui.components.shell import make_action_button
import updater


class UpdateModal(ctk.CTkToplevel):
    """Cửa sổ Modal thông báo và điều khiển tải cập nhật phiên bản mới."""

    def __init__(
        self,
        parent,
        update_info: Dict[str, Any],
        current_version: str = "v1.6.1",
        on_close_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.parent_app = parent
        self.update_info = update_info or {}
        self.current_version = current_version
        self.on_close_callback = on_close_callback

        self.title("🔄 Cập Nhật Phiên Bản Mới")
        self.geometry("540x550")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_SURFACE)

        # Căn giữa màn hình
        self.update_idletasks()
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 540, 550
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        # Modal configuration
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()

        # Áp dụng icon đồng bộ
        if hasattr(parent, "_setup_window_icon"):
            parent._setup_window_icon(self)
            self.after(100, lambda: parent._setup_window_icon(self))
        elif hasattr(parent, "_apply_window_icon"):
            parent._apply_window_icon(self)
            self.after(100, lambda: parent._apply_window_icon(self))

        self._is_downloading = False
        self._build_ui()

    def _build_ui(self):
        # 1. Header Frame
        h_frame = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=60, corner_radius=0)
        h_frame.pack(fill="x")
        h_frame.pack_propagate(False)

        title_box = ctk.CTkFrame(h_frame, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=10)

        ctk.CTkLabel(
            title_box,
            text="🏷️ PHÁT HIỆN PHIÊN BẢN MỚI",
            font=Fonts.SLOT_TITLE,
            text_color=Colors.CYAN
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Đã có phiên bản cập nhật chính thức từ hệ thống GitHub Releases",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")

        # 2. Main Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # A. Version Comparison Card
        ver_card = ctk.CTkFrame(body, fg_color=Colors.BG_CARD, border_width=1, border_color=Colors.BORDER_CARD, corner_radius=Radii.MD)
        ver_card.pack(fill="x", pady=(0, 10))

        ver_inner = ctk.CTkFrame(ver_card, fg_color="transparent")
        ver_inner.pack(fill="x", padx=16, pady=12)

        # Cột phiên bản hiện tại
        col_curr = ctk.CTkFrame(ver_inner, fg_color="transparent")
        col_curr.pack(side="left", expand=True)
        ctk.CTkLabel(col_curr, text="Phiên bản hiện tại", font=Fonts.CAPTION_BOLD, text_color=Colors.TEXT_MUTED).pack()
        ctk.CTkLabel(col_curr, text=self.current_version, font=Fonts.HEADER_TITLE, text_color=Colors.ROSE).pack()

        # Mũi tên chuyển tiếp
        ctk.CTkLabel(ver_inner, text="➔", font=Fonts.HEADER_TITLE, text_color=Colors.TEXT_DIM).pack(side="left", padx=12)

        # Cột phiên bản mới
        latest_ver = self.update_info.get("latest_version", "Mới")
        col_new = ctk.CTkFrame(ver_inner, fg_color="transparent")
        col_new.pack(side="left", expand=True)
        ctk.CTkLabel(col_new, text="Phiên bản mới nhất", font=Fonts.CAPTION_BOLD, text_color=Colors.TEXT_MUTED).pack()
        ctk.CTkLabel(col_new, text=latest_ver, font=Fonts.HEADER_TITLE, text_color=Colors.GREEN).pack()

        # B. Release Notes
        rel_name = self.update_info.get("release_name") or f"Bản phát hành {latest_ver}"
        ctk.CTkLabel(
            body,
            text=f"📋 Nội dung cập nhật ({rel_name}):",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_MAIN
        ).pack(anchor="w", pady=(0, 4))

        notes_box = ctk.CTkTextbox(
            body,
            height=130,
            fg_color=Colors.BG_INPUT,
            border_width=1,
            border_color=Colors.BORDER_CARD,
            corner_radius=Radii.SM,
            font=Fonts.BODY,
            text_color=Colors.TEXT_MAIN
        )
        notes_box.pack(fill="x", pady=(0, 10))

        raw_notes = self.update_info.get("release_notes") or ""
        notes_box.insert("1.0", raw_notes.strip() if raw_notes else "Cập nhật tối ưu hóa và nâng cấp tính năng mới nhất.")
        notes_box.configure(state="disabled")

        # C. Progress & Status Card
        status_card = ctk.CTkFrame(body, fg_color=Colors.BG_CARD, border_width=1, border_color=Colors.BORDER_CARD, corner_radius=Radii.MD)
        status_card.pack(fill="x", pady=(0, 10))

        status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        status_inner.pack(fill="x", padx=14, pady=10)

        download_url = self.update_info.get("download_url")
        asset_size = self.update_info.get("asset_size", 0)
        size_str = f"{asset_size / (1024*1024):.1f} MB" if asset_size > 0 else "Tự động"

        top_st = ctk.CTkFrame(status_inner, fg_color="transparent")
        top_st.pack(fill="x")

        self.lbl_status = ctk.CTkLabel(
            top_st,
            text="⚡ Sẵn sàng nâng cấp tự động" if download_url else "⚠️ Chưa tìm thấy gói cập nhật tự động!",
            font=Fonts.BODY_BOLD,
            text_color=Colors.CYAN if download_url else Colors.AMBER
        )
        self.lbl_status.pack(side="left")

        self.lbl_detail = ctk.CTkLabel(
            top_st,
            text=f"Dung lượng: {size_str}",
            font=Fonts.CAPTION,
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_detail.pack(side="right")

        self.pbar = ctk.CTkProgressBar(status_inner, height=8, corner_radius=Radii.XS)
        self.pbar.pack(fill="x", pady=(8, 2))
        self.pbar.set(0.0)

        # 3. Footer Action Buttons
        footer = ctk.CTkFrame(self, fg_color=Colors.BG_HEADER, height=54, corner_radius=0)
        footer.pack(fill="x", side="bottom")

        # Nút Mở GitHub Releases trên trình duyệt
        self.btn_web = make_action_button(
            footer,
            "🌐 Xem Trên GitHub",
            self._open_release_web,
            tone="ghost",
            height=32
        )
        self.btn_web.pack(side="left", padx=(16, 6), pady=11)

        # Nút Đóng
        self.btn_close = ctk.CTkButton(
            footer,
            text="Đóng",
            fg_color=Colors.BORDER_SUBTLE,
            hover_color=Colors.BORDER_CARD,
            font=Fonts.BODY_BOLD,
            width=80,
            height=32,
            command=self.destroy
        )
        self.btn_close.pack(side="right", padx=(6, 16), pady=11)

        # Nút Cập Nhật Tự Động
        self.btn_update = make_action_button(
            footer,
            "⬇️ Cập Nhật Tự Động & Khởi Động Lại",
            self._start_download_and_apply,
            tone="primary",
            height=32
        )
        self.btn_update.pack(side="right", padx=6, pady=11)

        if not download_url:
            self.btn_update.configure(state="disabled")

    def _open_release_web(self):
        """Mở trang phát hành trên trình duyệt."""
        url = self.update_info.get("release_url") or "https://github.com/donkma93/meg/releases"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _start_download_and_apply(self):
        """Khởi chạy luồng tải xuống bản cập nhật và tự động khởi động lại."""
        if self._is_downloading:
            return

        download_url = self.update_info.get("download_url")
        if not download_url:
            self.lbl_status.configure(text="Không tìm thấy link tải bản cập nhật.", text_color=Colors.ROSE)
            return

        self._is_downloading = True
        self.btn_update.configure(state="disabled", text="⏳ Đang tải bản mới...")
        self.btn_close.configure(state="disabled")
        self.lbl_status.configure(text="Đang kết nối tới máy chủ GitHub...", text_color=Colors.CYAN)

        def _worker():
            temp_dir = Path(tempfile.gettempdir())
            target_exe = temp_dir / "MEGAMU_Update_Payload.exe"

            def _progress(downloaded: int, total: int):
                if total > 0:
                    pct = min(1.0, max(0.0, downloaded / total))
                    mb_dl = downloaded / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)

                    def _ui():
                        self.pbar.set(pct)
                        self.lbl_status.configure(
                            text=f"Đang tải xuống: {pct*100:.0f}% ({mb_dl:.1f} MB / {mb_tot:.1f} MB)",
                            text_color=Colors.CYAN
                        )
                        self.lbl_detail.configure(text=f"{mb_dl:.1f}/{mb_tot:.1f} MB")

                    self.after(0, _ui)

            ok = updater.download_file_with_progress(
                url=download_url,
                dest_path=target_exe,
                progress_callback=_progress
            )

            if ok and target_exe.exists() and target_exe.stat().st_size > 1000000:
                def _success():
                    self.pbar.set(1.0)
                    self.lbl_status.configure(
                        text="✅ Tải hoàn tất! Đang thay thế file và khởi động lại...",
                        text_color=Colors.GREEN
                    )

                    # Đợi 1 giây để người dùng thấy thông báo rồi chạy script batch thay thế exe và restart
                    def _do_restart():
                        try:
                            updater.apply_exe_update_and_restart(target_exe)
                        except Exception as e:
                            self.lbl_status.configure(text=f"Lỗi khởi động lại: {e}", text_color=Colors.ROSE)
                            self.btn_update.configure(state="normal", text="Thử Lại")
                            self.btn_close.configure(state="normal")

                    self.after(1000, _do_restart)

                self.after(0, _success)
            else:
                def _fail():
                    self._is_downloading = False
                    self.pbar.set(0.0)
                    self.lbl_status.configure(text="❌ Tải cập nhật thất bại hoặc file bị hỏng!", text_color=Colors.ROSE)
                    self.btn_update.configure(state="normal", text="🔄 Thử Lại")
                    self.btn_close.configure(state="normal")
                    messagebox.showerror(
                        "Lỗi Tải Cập Nhật",
                        "Không thể tải bản cập nhật từ máy chủ GitHub.\nVui lòng kiểm tra lại kết nối mạng hoặc tải thủ công qua nút 'Xem Trên GitHub'.",
                        parent=self
                    )

                self.after(0, _fail)

        threading.Thread(target=_worker, name="UpdateModal_DownloadThread", daemon=True).start()
