"""
UI Modal: Profiles Modal (Cấu hình 10 Profile & Bãi Quái).
"""

from typing import Any, Optional
import customtkinter as ctk
from core.i18n import tr
from ui.components.option_menu import ModernOptionMenu
from ui.components.icons import UiIconFactory

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]

def open_profiles_modal(self, profile_index: Optional[int] = None):
    """Mở cửa sổ Modal Cấu hình Chặng & Tuyến Đường (Profiles Modal)."""
    if hasattr(self, "_profiles_window_instance") and self._profiles_window_instance is not None:
        try:
            if self._profiles_window_instance.winfo_exists():
                self._profiles_window_instance.deiconify()
                self._profiles_window_instance.transient(self)
                self._profiles_window_instance.lift()
                self._profiles_window_instance.after(10, lambda: self._profiles_window_instance.lift() if self._profiles_window_instance and self._profiles_window_instance.winfo_exists() else None)
                self._profiles_window_instance.focus_force()
                if profile_index:
                    self.load_profile_into_editor(profile_index)
                return
        except Exception:
            pass

    dlg = ctk.CTkToplevel(self)
    dlg.title(f"⚙️ {tr('configuration')} - MEGAMU Auto Train")
    dlg.geometry("860x520")
    dlg.minsize(760, 460)
    dlg.configure(fg_color="#0e1117")
    dlg.transient(self)
    dlg.lift()
    dlg.after(10, lambda: dlg.lift() if dlg.winfo_exists() else None)
    dlg.after(50, lambda: dlg.focus_force() if dlg.winfo_exists() else None)
    try:
        x = self.winfo_x() + (self.winfo_width() // 2) - 430
        y = self.winfo_y() + (self.winfo_height() // 2) - 260
        dlg.geometry(f"+{max(10, x)}+{max(10, y)}")
    except Exception:
        pass
    self._profiles_window_instance = dlg

    try:
        self._apply_window_icon(dlg)
        dlg.after(50, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
        dlg.after(220, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
        dlg.after(500, lambda: self._apply_window_icon(dlg) if dlg.winfo_exists() else None)
    except Exception:
        pass

    def _on_modal_close():
        try:
            self.save_editor_to_file(silent=True)
        except Exception:
            pass
        dlg.destroy()
        self._profiles_window_instance = None

    dlg.protocol("WM_DELETE_WINDOW", _on_modal_close)

    # Header bar của Modal
    top_bar = ctk.CTkFrame(dlg, fg_color="#141822", height=42, corner_radius=0)
    top_bar.pack(fill="x", padx=0, pady=0)

    inner_tb = ctk.CTkFrame(top_bar, fg_color="transparent")
    inner_tb.pack(fill="both", expand=True, padx=12, pady=6)

    # Logo / Icon đồng bộ góc trái phía trên
    if hasattr(self, "logo_ctk") and self.logo_ctk:
        ctk.CTkLabel(inner_tb, image=self.logo_ctk, text="").pack(side="left", padx=(0, 8))

    ctk.CTkLabel(
        inner_tb,
        text=f"⚙️ {tr('configuration').upper()} • BÃI QUÁI & LỘ TRÌNH",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#38bdf8"
    ).pack(side="left", padx=(0, 10))

    if not hasattr(self, "editor_profile_var"):
        self.editor_profile_var = ctk.StringVar(value="Config 1")

    self.editor_profile_combo = ModernOptionMenu(
        inner_tb,
        values=PROFILE_NAMES,
        variable=self.editor_profile_var,
        width=110,
        height=28,
        fg_color="#181c26",
        border_color="#2a3042",
        hover_color="#222736",
        command=self.on_editor_profile_change,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
    )
    self.editor_profile_combo.pack(side="left", padx=4)

    ctk.CTkLabel(
        inner_tb, text=tr("pk_delay"), font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8"
    ).pack(side="left", padx=(10, 4))

    if not hasattr(self, "editor_respawn_var"):
        self.editor_respawn_var = ctk.StringVar(value="15")
    self.editor_respawn_entry = ctk.CTkEntry(
        inner_tb,
        textvariable=self.editor_respawn_var,
        width=55,
        height=28,
        fg_color="#181c26",
        border_color="#2a3042",
        font=ctk.CTkFont(family="Segoe UI", size=11)
    )
    self.editor_respawn_entry.pack(side="left", padx=2)

    # Nút Đóng modal bên phải
    btn_close = ctk.CTkButton(
        inner_tb,
        text="✕ Đóng",
        width=65,
        height=28,
        fg_color="#1e2433",
        hover_color="#334155",
        border_width=1,
        border_color="#334155",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=_on_modal_close
    )
    btn_close.pack(side="right", padx=(4, 0))

    # Nút Lưu cấu hình
    self.btn_save_cfg = ctk.CTkButton(
        inner_tb,
        text=f"💾 {tr('save_profile')}",
        width=105,
        height=28,
        fg_color="#0284c7",
        hover_color="#0369a1",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=self.save_editor_to_file
    )
    self.btn_save_cfg.pack(side="right", padx=4)

    # Nút Tải lại
    self.btn_reload_cfg = ctk.CTkButton(
        inner_tb,
        text=f"🔄 {tr('reload')}",
        width=80,
        height=28,
        fg_color="#1e2433",
        hover_color="#334155",
        border_width=1,
        border_color="#334155",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        command=self.reload_editor_from_file
    )
    self.btn_reload_cfg.pack(side="right", padx=4)

    # Body container
    body = ctk.CTkFrame(dlg, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=12, pady=(6, 8))

    self.lbl_team_note = ctk.CTkLabel(
        body,
        text=tr("team_note"),
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#64748b"
    )
    self.lbl_team_note.pack(anchor="w", padx=4, pady=(0, 4))

    # Stage table header
    stage_header = ctk.CTkFrame(body, fg_color="#141822", height=26, corner_radius=3)
    stage_header.pack(fill="x", padx=2, pady=(0, 4))

    stage_cols = [
        ("stage_min", 70, "center"),
        ("stage_max", 70, "center"),
        ("stage_map", 240, "center"),
        ("stage_x", 80, "center"),
        ("stage_y", 80, "center")
    ]
    self.stage_header_labels = []
    for k, w, anc in stage_cols:
        lbl = ctk.CTkLabel(
            stage_header,
            text=tr(k),
            width=w,
            anchor=anc,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        lbl.pack(side="left", padx=3)
        self.stage_header_labels.append(lbl)

    # 10 Hàng chặng
    self.editor_rows = []
    for r in range(10):
        row_f = ctk.CTkFrame(body, fg_color="#131722", height=32, corner_radius=3, border_width=1, border_color="#1c2230")
        row_f.pack(fill="x", padx=2, pady=1)

        min_var = ctk.StringVar(value="")
        min_ent = ctk.CTkEntry(
            row_f, textvariable=min_var, width=70, height=26, fg_color="#181c26", border_color="#2a3042"
        )
        min_ent.pack(side="left", padx=3)

        max_var = ctk.StringVar(value="")
        max_ent = ctk.CTkEntry(
            row_f, textvariable=max_var, width=70, height=26, fg_color="#181c26", border_color="#2a3042"
        )
        max_ent.pack(side="left", padx=3)

        map_var = ctk.StringVar(value="")
        map_combo = ModernOptionMenu(
            row_f,
            values=[""] + self.map_list,
            variable=map_var,
            width=240,
            height=26,
            fg_color="#181c26",
            border_color="#2a3042",
            hover_color="#222736",
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        map_combo.pack(side="left", padx=3)

        x_var = ctk.StringVar(value="")
        x_ent = ctk.CTkEntry(
            row_f, textvariable=x_var, width=80, height=26, fg_color="#181c26", border_color="#2a3042"
        )
        x_ent.pack(side="left", padx=3)

        y_var = ctk.StringVar(value="")
        y_ent = ctk.CTkEntry(
            row_f, textvariable=y_var, width=80, height=26, fg_color="#181c26", border_color="#2a3042"
        )
        y_ent.pack(side="left", padx=3)

        self.editor_rows.append({
            "min": min_var,
            "max": max_var,
            "map": map_var,
            "x": x_var,
            "y": y_var
        })

    target_p = profile_index if profile_index is not None else getattr(self, "current_editor_profile_idx", 1)
    self.load_profile_into_editor(target_p)

