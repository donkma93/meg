"""
UI Modal: Logs Window Modal (Nhật ký Hệ thống Ring Buffer).
"""

from typing import Any, Optional
import customtkinter as ctk
from core.i18n import tr
from ui.components.option_menu import ModernOptionMenu
from ui.components.icons import UiIconFactory

MAX_SLOTS = 10

def open_logs_window(self, default_slot: Optional[str] = None):
    """Mở cửa sổ Nhật ký hoạt động chuyên dụng (Floating Logs Window) từ Header."""
    if hasattr(self, "_logs_window_instance") and self._logs_window_instance is not None:
        try:
            if self._logs_window_instance.winfo_exists():
                self._logs_window_instance.deiconify()
                self._logs_window_instance.transient(self)
                self._logs_window_instance.lift()
                self._logs_window_instance.after(10, lambda: self._logs_window_instance.lift() if self._logs_window_instance and self._logs_window_instance.winfo_exists() else None)
                self._logs_window_instance.focus_force()
                if default_slot and hasattr(self, "log_filter_var"):
                    self.log_filter_var.set(default_slot)
                self.render_logs()
                return
        except Exception:
            pass

    dlg = ctk.CTkToplevel(self)
    dlg.title("📋 Nhật ký Hoạt động Hệ thống - MEGAMU Auto Train")
    dlg.geometry("780x560")
    dlg.minsize(620, 420)
    dlg.configure(fg_color="#0e1117")
    dlg.transient(self)
    dlg.lift()
    dlg.after(10, lambda: dlg.lift() if dlg.winfo_exists() else None)
    dlg.after(50, lambda: dlg.focus_force() if dlg.winfo_exists() else None)
    try:
        x = self.winfo_x() + (self.winfo_width() // 2) - 390
        y = self.winfo_y() + (self.winfo_height() // 2) - 280
        dlg.geometry(f"+{max(10, x)}+{max(10, y)}")
    except Exception:
        pass
    self._logs_window_instance = dlg

    try:
        self._apply_window_icon(dlg)
        dlg.after(50, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
        dlg.after(220, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
        dlg.after(500, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
    except Exception:
        pass

    # Top bar
    top_bar = ctk.CTkFrame(dlg, fg_color="#141822", height=42, corner_radius=0)
    top_bar.pack(fill="x", padx=0, pady=0)

    inner_tb = ctk.CTkFrame(top_bar, fg_color="transparent")
    inner_tb.pack(fill="both", expand=True, padx=12, pady=6)

    # Logo / Icon đồng bộ góc trái phía trên
    if hasattr(self, "logo_ctk") and self.logo_ctk:
        ctk.CTkLabel(inner_tb, image=self.logo_ctk, text="").pack(side="left", padx=(0, 8))

    ctk.CTkLabel(
        inner_tb,
        text="📋 NHẬT KÝ HOẠT ĐỘNG",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#38bdf8"
    ).pack(side="left", padx=(0, 10))

    # Filter
    filter_options = [tr("all")] + [f"{i:02d}" for i in range(1, MAX_SLOTS + 1)]
    if not hasattr(self, "log_filter_var"):
        self.log_filter_var = ctk.StringVar(value=tr("all"))
    if default_slot:
        self.log_filter_var.set(default_slot)

    self.log_filter_combo = ModernOptionMenu(
        inner_tb,
        values=filter_options,
        variable=self.log_filter_var,
        width=90,
        height=28,
        fg_color="#181c26",
        border_color="#2a3042",
        hover_color="#222736",
        command=lambda _: self.render_logs(),
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
    )
    self.log_filter_combo.pack(side="left", padx=4)

    # Clear
    btn_clear = ctk.CTkButton(
        inner_tb,
        text=tr("clear_view"),
        width=85,
        height=28,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=self.clear_logs
    )
    btn_clear.pack(side="right")

    # Open stop logs
    btn_stop_log = ctk.CTkButton(
        inner_tb,
        text="📑 Log Dừng Auto",
        width=125,
        height=28,
        fg_color="#1e293b",
        hover_color="#334155",
        border_width=1,
        border_color="#38bdf8",
        text_color="#38bdf8",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=self.open_stop_events_log_file
    )
    btn_stop_log.pack(side="right", padx=(0, 6))

    # Textbox
    self.log_textbox = ctk.CTkTextbox(
        dlg,
        fg_color="#121214",
        text_color="#f3f4f6",
        font=ctk.CTkFont(family="Consolas", size=11),
        corner_radius=0,
        wrap="word"
    )
    self.log_textbox.pack(fill="both", expand=True, padx=12, pady=10)
    self.log_textbox.configure(state="disabled")

    def _on_close_logs():
        try:
            dlg.destroy()
        except Exception:
            pass
        self._logs_window_instance = None
    dlg.protocol("WM_DELETE_WINDOW", _on_close_logs)

    self.render_logs()

