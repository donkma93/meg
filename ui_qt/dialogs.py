# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD QT6 - NATIVE MODAL DIALOGS
Các hộp thoại native Qt6: Dọn Rác Hòm Đồ, Bản Quyền, Devil Square, Cộng Point, Auto PT, Telegram.
"""

from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QFrame, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QSpinBox, QPlainTextEdit,
    QMessageBox, QScrollArea, QWidget, QProgressBar
)


class JunkDisposalDialogQt(QDialog):
    """Hộp thoại xem trước báo cáo đọc RVA và thực thi vứt/bán đồ rác."""

    def __init__(self, reports: list, on_execute: Callable[[list, str], None], parent=None):
        super().__init__(parent)
        self.reports = reports
        self.on_execute = on_execute
        self.setWindowTitle("🧹 Dọn Rác Hòm Đồ (RVA)")
        self.resize(740, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        lbl_h = QLabel("🧹 DỌN RÁC HÒM ĐỒ (Đọc trực tiếp RVA)")
        lbl_h.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 14px;")
        root.addWidget(lbl_h)

        box = QPlainTextEdit()
        box.setReadOnly(True)

        total_junk = 0
        total_held = 0
        lines: List[str] = []
        for ctrl, res in reports:
            if not isinstance(res, dict) or not res.get("ok"):
                lines.append(f"[Slot {ctrl.slot_idx:02d}] ❌ Không đọc được hòm đồ ({(res or {}).get('reason', '?')})\n")
                continue
            slots_list = res.get("slots")
            if isinstance(slots_list, list):
                junk = [s for s in slots_list if isinstance(s, dict) and s.get("status") == "junk"]
                held = [s for s in slots_list if isinstance(s, dict) and s.get("status") == "protected"]
            else:
                raw_j = res.get("junkSlots") or (res.get("junk") if isinstance(res.get("junk"), list) else [])
                raw_h = res.get("keptSlots") or (res.get("kept") if isinstance(res.get("kept"), list) else [])
                junk = raw_j if isinstance(raw_j, list) else []
                held = raw_h if isinstance(raw_h, list) else []
            total_junk += len(junk)
            total_held += len(held)
            coord = res.get("coord") or {}
            lines.append(
                f"[Slot {ctrl.slot_idx:02d} · {getattr(ctrl, 'char_name', '---')}] "
                f"{res.get('occupied', len(junk) + len(held))} món · dọn được {len(junk)} · giữ {len(held)} · "
                f"({coord.get('x', '?')},{coord.get('y', '?')}) · Merchant {'MỞ' if res.get('merchantOpen') else 'ĐÓNG'}"
            )
            reason_labels = getattr(ctrl, "JUNK_REASON_LABELS", {}) or {}
            for k, v in sorted((res.get("byReason") or {}).items(), key=lambda kv: -kv[1]):
                lines.append(f"      giữ {v:>3} → {reason_labels.get(k, k)}")
            for it in junk[:25]:
                if isinstance(it, dict):
                    lines.append(
                        f"  ✔ slot {int(it.get('slot', 0)):>3}: {it.get('name') or ('#' + str(it.get('index', '?')))} +{it.get('level', 0)}"
                    )
                else:
                    lines.append(f"  ✔ {it}")
            if len(junk) > 25:
                lines.append(f"      ... và {len(junk) - 25} món nữa")
            lines.append("")

        box.setPlainText("\n".join(lines) if lines else "Không có dữ liệu.")
        root.addWidget(box, 1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Cách dọn:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Tự động (vứt → bán)", "Chỉ vứt", "Chỉ bán"])
        self.combo_mode.setFixedWidth(220)
        mode_row.addWidget(self.combo_mode)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        lbl_note = QLabel(
            f"Tổng: dọn được {total_junk} món · giữ {total_held} món. "
            "Slot 0–11 (trang bị) và đồ Exc/Set/Socket/Harmony/Ngọc luôn được bảo vệ."
        )
        lbl_note.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_note.setWordWrap(True)
        root.addWidget(lbl_note)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_exec = QPushButton("🗑️ Thực hiện")
        btn_exec.setProperty("tone", "danger")
        btn_exec.setFixedSize(120, 32)
        btn_exec.setEnabled(total_junk > 0)
        btn_exec.clicked.connect(self._do_exec)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setProperty("tone", "ghost")
        btn_cancel.setFixedSize(100, 32)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_exec)
        btns.addWidget(btn_cancel)
        btns.addStretch(1)
        root.addLayout(btns)

    def _do_exec(self):
        mode = {
            "Tự động (vứt → bán)": "auto",
            "Chỉ vứt": "drop",
            "Chỉ bán": "sell",
        }.get(self.combo_mode.currentText(), "auto")
        self.accept()
        self.on_execute(self.reports, mode)


class LicenseDialogQt(QDialog):
    """Hộp thoại xem & kích hoạt License Key."""

    def __init__(self, license_client: Any, on_activated: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.license_client = license_client
        self.on_activated = on_activated
        self.setWindowTitle("🔑 Quản lý Bản Quyền - MEGAMU Auto Train")
        self.setFixedSize(470, 330)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        t = QLabel("QUẢN LÝ BẢN QUYỀN")
        t.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9;")
        root.addWidget(t)

        status = license_client.get_license_display_text() if hasattr(license_client, "get_license_display_text") else "N/A"
        card = QFrame()
        card.setProperty("surface", "card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        lbl_s = QLabel(f"Trạng thái: {status}")
        lbl_s.setStyleSheet("color: #38bdf8; font-weight: 700;")
        cl.addWidget(lbl_s)
        root.addWidget(card)

        hwid = ""
        try:
            hwid = license_client.get_hwid() if hasattr(license_client, "get_hwid") else ""
        except Exception:
            pass

        form = QFormLayout()
        ed_hwid = QLineEdit(hwid)
        ed_hwid.setReadOnly(True)
        form.addRow("HWID:", ed_hwid)

        self.ed_key = QLineEdit()
        self.ed_key.setPlaceholderText("Nhập License Key...")
        form.addRow("License Key:", self.ed_key)
        root.addLayout(form)

        root.addStretch(1)

        btn_act = QPushButton("✔ Kích hoạt bản quyền")
        btn_act.setProperty("tone", "success")
        btn_act.setFixedHeight(34)
        btn_act.clicked.connect(self._activate)
        root.addWidget(btn_act)

        btn_close = QPushButton("Đóng")
        btn_close.setProperty("tone", "ghost")
        btn_close.setFixedHeight(30)
        btn_close.clicked.connect(self.reject)
        root.addWidget(btn_close)

    def _activate(self):
        key = self.ed_key.text().strip()
        if not key:
            QMessageBox.warning(self, "License", "Vui lòng nhập license key.")
            return
        try:
            ok, msg, _info = self.license_client.activate_license(key)
            if ok:
                QMessageBox.information(self, "License", msg or "Kích hoạt thành công.")
                if self.on_activated:
                    self.on_activated()
                self.accept()
            else:
                QMessageBox.critical(self, "License", msg or "Kích hoạt thất bại.")
        except Exception as e:
            QMessageBox.critical(self, "License", str(e))


class DevilConfigDialogQt(QDialog):
    """Cấu hình & kích hoạt nhanh Devil Square."""

    def __init__(self, cfg_mgr: Any, on_trigger_all: Callable[[], None], on_saved: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.cfg_mgr = cfg_mgr
        self.on_trigger_all = on_trigger_all
        self.on_saved = on_saved
        self.setWindowTitle("🔥 Cài Đặt Devil Square (DS)")
        self.setFixedSize(460, 320)

        cfg = cfg_mgr.load_devil_config() if hasattr(cfg_mgr, "load_devil_config") else {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        lbl = QLabel("🔥 CẤU HÌNH AUTO DEVIL SQUARE")
        lbl.setStyleSheet("color: #fb7185; font-weight: 700; font-size: 14px;")
        root.addWidget(lbl)

        self.cb_enable = QCheckBox("Tự động đi Devil Square theo lịch trình")
        self.cb_enable.setChecked(bool(cfg.get("enabled", False)))
        root.addWidget(self.cb_enable)

        form = QFormLayout()
        self.spin_min_lv = QSpinBox()
        self.spin_min_lv.setRange(1, 2000)
        self.spin_min_lv.setValue(int(cfg.get("min_level", 1) or 1))
        form.addRow("Level tối thiểu:", self.spin_min_lv)

        self.spin_max_lv = QSpinBox()
        self.spin_max_lv.setRange(1, 2000)
        self.spin_max_lv.setValue(int(cfg.get("max_level", 400) or 400))
        form.addRow("Level tối đa:", self.spin_max_lv)

        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 255)
        self.spin_x.setValue(int(cfg.get("spot_x", 136) or 136))
        form.addRow("Tọa độ đứng X:", self.spin_x)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 255)
        self.spin_y.setValue(int(cfg.get("spot_y", 91) or 91))
        form.addRow("Tọa độ đứng Y:", self.spin_y)
        root.addLayout(form)

        root.addStretch(1)

        btns = QHBoxLayout()
        b_go = QPushButton("🚀 Vào DS Ngay")
        b_go.setProperty("tone", "fire")
        b_go.setFixedHeight(32)
        b_go.clicked.connect(lambda: (self._save(close=False), self.on_trigger_all()))

        b_save = QPushButton("💾 Lưu")
        b_save.setProperty("tone", "primary")
        b_save.setFixedHeight(32)
        b_save.clicked.connect(lambda: self._save(close=True))

        b_cls = QPushButton("Đóng")
        b_cls.setProperty("tone", "ghost")
        b_cls.setFixedHeight(32)
        b_cls.clicked.connect(self.reject)

        btns.addWidget(b_go)
        btns.addWidget(b_save)
        btns.addWidget(b_cls)
        root.addLayout(btns)

    def _save(self, close: bool = True):
        if hasattr(self.cfg_mgr, "save_devil_config"):
            cfg = self.cfg_mgr.load_devil_config() if hasattr(self.cfg_mgr, "load_devil_config") else {}
            cfg.update({
                "enabled": self.cb_enable.isChecked(),
                "min_level": int(self.spin_min_lv.value()),
                "max_level": int(self.spin_max_lv.value()),
                "spot_x": int(self.spin_x.value()),
                "spot_y": int(self.spin_y.value()),
            })
            self.cfg_mgr.save_devil_config(cfg)
        if self.on_saved:
            self.on_saved()
        if close:
            self.accept()


class PointConfigDialogQt(QDialog):
    """Hộp thoại cấu hình cộng Point tự động theo tỷ lệ & kích hoạt cộng điểm ngay."""

    def __init__(self, controllers: list, cfg_mgr: Any, on_trigger_all: Callable[[], None], parent=None):
        super().__init__(parent)
        self.controllers = controllers
        self.cfg_mgr = cfg_mgr
        self.on_trigger_all = on_trigger_all
        self.setWindowTitle("⭐ Cài Đặt Tự Động Cộng Point")
        self.setFixedSize(480, 340)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        lbl = QLabel("⭐ TỰ ĐỘNG CỘNG ĐIỂM TIỀM NĂNG (AUTO ADD POINT)")
        lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 13px;")
        root.addWidget(lbl)

        self.combo_slot = QComboBox()
        for c in controllers:
            self.combo_slot.addItem(f"Slot #{c.slot_idx:02d} ({getattr(c, 'char_name', '---')})", c.slot_idx)
        self.combo_slot.currentIndexChanged.connect(self._load_slot)
        root.addWidget(self.combo_slot)

        self.cb_auto = QCheckBox("Bật tự động cộng Point cho Slot này")
        root.addWidget(self.cb_auto)

        form = QFormLayout()
        self.spins: Dict[str, QSpinBox] = {}
        for key, label in (("str", "Sức mạnh (STR):"), ("agi", "Nhanh nhẹn (AGI):"), ("vit", "Thể lực (VIT):"), ("ene", "Năng lượng (ENE):"), ("cmd", "Mệnh lệnh (CMD):")):
            sp = QSpinBox()
            sp.setRange(0, 65000)
            self.spins[key] = sp
            form.addRow(label, sp)
        root.addLayout(form)

        self._load_slot()

        btns = QHBoxLayout()
        b_now = QPushButton("⚡ Cộng Tất Cả Ngay")
        b_now.setProperty("tone", "success")
        b_now.setFixedHeight(32)
        b_now.clicked.connect(lambda: (self._save_slot(), self.on_trigger_all()))

        b_save = QPushButton("💾 Lưu Slot")
        b_save.setProperty("tone", "primary")
        b_save.setFixedHeight(32)
        b_save.clicked.connect(lambda: (self._save_slot(), QMessageBox.information(self, "Auto Point", "Đã lưu cấu hình cộng Point.")))

        b_cls = QPushButton("Đóng")
        b_cls.setProperty("tone", "ghost")
        b_cls.setFixedHeight(32)
        b_cls.clicked.connect(self.accept)

        btns.addWidget(b_now)
        btns.addWidget(b_save)
        btns.addWidget(b_cls)
        root.addLayout(btns)

    def _current_ctrl(self):
        s_idx = self.combo_slot.currentData()
        for c in self.controllers:
            if c.slot_idx == s_idx:
                return c
        return self.controllers[0] if self.controllers else None

    def _load_slot(self):
        c = self._current_ctrl()
        if not c:
            return
        self.cb_auto.setChecked(bool(getattr(c, "auto_add_point", False)))
        ratios = getattr(c, "stat_ratios", None) or {}
        for k, sp in self.spins.items():
            sp.setValue(int(ratios.get(k, 0) or 0))

    def _save_slot(self):
        c = self._current_ctrl()
        if not c:
            return
        c.auto_add_point = self.cb_auto.isChecked()
        c.stat_ratios = {k: int(sp.value()) for k, sp in self.spins.items()}
        try:
            if hasattr(self.cfg_mgr, "save_slot_point_config"):
                self.cfg_mgr.save_slot_point_config(c.slot_idx, c.auto_add_point, c.stat_ratios)
        except Exception:
            pass


class PartyConfigDialogQt(QDialog):
    """Hộp thoại cấu hình nhanh Auto Party (Multi-PT)."""

    def __init__(self, party_mgr: Any, controllers: list, on_saved: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.party_mgr = party_mgr
        self.controllers = controllers
        self.on_saved = on_saved
        self.setWindowTitle("🤝 Tự Động Ghép Nhóm Party (Multi-PT)")
        self.setFixedSize(500, 340)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        lbl = QLabel("🤝 CẤU HÌNH AUTO PARTY (CHIA NHÓM 5 ACC/PT)")
        lbl.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 13px;")
        root.addWidget(lbl)

        self.cb_enabled = QCheckBox("Kích hoạt Auto Party (Tự động giữ PT & tái kết nối)")
        self.cb_enabled.setChecked(bool(party_mgr.is_enabled))
        root.addWidget(self.cb_enabled)

        self.cb_repass = QCheckBox("Tự động đặt lại mật khẩu /repass khi lập nhóm")
        self.cb_repass.setChecked(bool(party_mgr.auto_re_pass))
        root.addWidget(self.cb_repass)

        form = QFormLayout()
        self.ed_pass = QLineEdit(str(party_mgr.party_pass))
        form.addRow("Mật khẩu Party:", self.ed_pass)
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(3, 60)
        self.spin_interval.setValue(int(party_mgr.sync_interval))
        self.spin_interval.setSuffix(" giây")
        form.addRow("Chu kỳ kiểm tra:", self.spin_interval)
        root.addLayout(form)

        parties = party_mgr.get_parties(controllers)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setFixedHeight(95)
        p_lines = [
            f"• {p.get('name', 'PT')}: Chủ PT Slot #{p.get('leader_slot'):02d} | Thành viên: {p.get('member_slots', [])} | Pass: {p.get('party_pass')}"
            for p in parties
        ]
        preview.setPlainText("\n".join(p_lines) if p_lines else "Chưa có nhóm PT nào.")
        root.addWidget(preview)

        btns = QHBoxLayout()
        b_save = QPushButton("💾 Lưu cấu hình")
        b_save.setProperty("tone", "primary")
        b_save.setFixedHeight(32)
        b_save.clicked.connect(self._save)
        b_cls = QPushButton("Đóng")
        b_cls.setProperty("tone", "ghost")
        b_cls.setFixedHeight(32)
        b_cls.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(b_save)
        btns.addWidget(b_cls)
        root.addLayout(btns)

    def _save(self):
        cfg = dict(self.party_mgr.config)
        cfg["enabled"] = self.cb_enabled.isChecked()
        cfg["auto_re_pass"] = self.cb_repass.isChecked()
        cfg["party_pass"] = self.ed_pass.text().strip() or "1234"
        cfg["sync_interval_sec"] = float(self.spin_interval.value())
        self.party_mgr.save_config(cfg)
        if self.on_saved:
            self.on_saved()
        self.accept()


class TelegramConfigDialogQt(QDialog):
    """Hộp thoại cấu hình Telegram Bot Notifier."""

    def __init__(self, telegram_cfg: Any, send_raw_fn: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.telegram_cfg = telegram_cfg
        self.send_raw_fn = send_raw_fn
        self.setWindowTitle("📱 Cài Đặt Telegram Bot")
        self.setFixedSize(470, 270)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        lbl = QLabel("📱 THÔNG BÁO TELEGRAM BOT")
        lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 14px;")
        root.addWidget(lbl)

        self.cb_en = QCheckBox("Bật gửi thông báo qua Telegram")
        self.cb_en.setChecked(bool(getattr(telegram_cfg, "enabled", False)))
        root.addWidget(self.cb_en)

        form = QFormLayout()
        self.ed_token = QLineEdit(str(getattr(telegram_cfg, "bot_token", "") or ""))
        self.ed_token.setPlaceholderText("123456:ABC-DEF...")
        form.addRow("Bot Token:", self.ed_token)

        self.ed_chat = QLineEdit(str(getattr(telegram_cfg, "chat_id", "") or ""))
        self.ed_chat.setPlaceholderText("-100123456789")
        form.addRow("Chat ID:", self.ed_chat)
        root.addLayout(form)

        root.addStretch(1)

        btns = QHBoxLayout()
        b_test = QPushButton("📨 Gửi thử")
        b_test.setProperty("tone", "ghost")
        b_test.setFixedHeight(32)
        b_test.clicked.connect(self._test_send)

        b_save = QPushButton("💾 Lưu")
        b_save.setProperty("tone", "primary")
        b_save.setFixedHeight(32)
        b_save.clicked.connect(self._save)

        b_cls = QPushButton("Đóng")
        b_cls.setProperty("tone", "ghost")
        b_cls.setFixedHeight(32)
        b_cls.clicked.connect(self.reject)

        btns.addWidget(b_test)
        btns.addStretch(1)
        btns.addWidget(b_save)
        btns.addWidget(b_cls)
        root.addLayout(btns)

    def _save(self):
        if self.telegram_cfg:
            self.telegram_cfg.enabled = self.cb_en.isChecked()
            self.telegram_cfg.bot_token = self.ed_token.text().strip()
            self.telegram_cfg.chat_id = self.ed_chat.text().strip()
            if hasattr(self.telegram_cfg, "save"):
                self.telegram_cfg.save()
        self.accept()

    def _test_send(self):
        if not self.send_raw_fn:
            QMessageBox.information(self, "Telegram", "Module telegram_notifier chưa khả dụng.")
            return
        tok = self.ed_token.text().strip()
        cid = self.ed_chat.text().strip()
        if not tok or not cid:
            QMessageBox.warning(self, "Telegram", "Vui lòng nhập đầy đủ Bot Token và Chat ID.")
            return
        try:
            ok, msg = self.send_raw_fn(tok, cid, "✅ Kết nối Telegram Bot từ MEGAMU Dashboard Qt6 thành công!")
            if ok:
                QMessageBox.information(self, "Telegram", "Gửi tin nhắn thử thành công!")
            else:
                QMessageBox.warning(self, "Telegram", f"Gửi thất bại: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Telegram", f"Lỗi: {e}")


class UpdateDialogQt(QDialog):
    """Hộp thoại thông báo và tự động tải nâng cấp phiên bản mới trên Qt6."""

    def __init__(self, update_info: Dict[str, Any], current_version: str = "v1.6.6", parent=None):
        super().__init__(parent)
        self.update_info = update_info or {}
        self.current_version = current_version
        self._is_downloading = False
        self.setWindowTitle("🔄 Cập Nhật Phiên Bản Mới")
        self.resize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header
        h_box = QVBoxLayout()
        lbl_h = QLabel("🏷️ PHÁT HIỆN PHIÊN BẢN MỚI")
        lbl_h.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 15px;")
        lbl_sub = QLabel("Đã có bản phát hành chính thức từ hệ thống GitHub Releases")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        h_box.addWidget(lbl_h)
        h_box.addWidget(lbl_sub)
        root.addLayout(h_box)

        # Card comparison
        card = QFrame()
        card.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 10px;")
        c_lay = QHBoxLayout(card)
        c_lay.setContentsMargins(10, 8, 10, 8)

        v_curr = QLabel(f"Hiện tại: <b style='color:#94a3b8'>{self.current_version}</b>")
        arrow = QLabel("➔")
        arrow.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
        latest = self.update_info.get("latest_version", "?")
        v_latest = QLabel(f"Mới nhất: <b style='color:#4ade80'>{latest}</b>")

        c_lay.addWidget(v_curr)
        c_lay.addStretch(1)
        c_lay.addWidget(arrow)
        c_lay.addStretch(1)
        c_lay.addWidget(v_latest)
        root.addWidget(card)

        # Release notes
        lbl_notes = QLabel("Nội dung thay đổi & Điểm mới:")
        lbl_notes.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")
        root.addWidget(lbl_notes)

        self.box_notes = QPlainTextEdit()
        self.box_notes.setReadOnly(True)
        self.box_notes.setStyleSheet(
            "background-color: #0b1120; border: 1px solid #1e293b; border-radius: 6px; "
            "color: #e2e8f0; font-family: Consolas, monospace; font-size: 11px;"
        )
        notes_text = self.update_info.get("release_notes", "") or "Không có ghi chú phát hành."
        self.box_notes.setPlainText(notes_text)
        root.addWidget(self.box_notes, 1)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        self.pbar.setFixedHeight(20)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 3px;
            }
        """)
        root.addWidget(self.pbar)

        self.lbl_status = QLabel("Sẵn sàng cập nhật.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        root.addWidget(self.lbl_status)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)

        b_web = QPushButton("🌐 Xem Trên GitHub")
        b_web.setProperty("tone", "ghost")
        b_web.setFixedHeight(34)
        b_web.clicked.connect(self._open_web)

        self.b_update = QPushButton("⬇️ Cập Nhật Tự Động & Khởi Động Lại")
        self.b_update.setProperty("tone", "primary")
        self.b_update.setFixedHeight(34)
        self.b_update.clicked.connect(self._start_download_and_apply)

        self.b_close = QPushButton("Đóng")
        self.b_close.setProperty("tone", "ghost")
        self.b_close.setFixedHeight(34)
        self.b_close.clicked.connect(self.reject)

        btns.addWidget(b_web)
        btns.addStretch(1)
        btns.addWidget(self.b_update)
        btns.addWidget(self.b_close)
        root.addLayout(btns)

        dl_url = self.update_info.get("download_url")
        if not dl_url:
            self.b_update.setEnabled(False)
            self.lbl_status.setText("Chưa tìm thấy link tải trực tiếp. Vui lòng bấm 'Xem Trên GitHub'.")

    def _open_web(self):
        import webbrowser
        url = self.update_info.get("release_url") or "https://github.com/donkma93/meg/releases"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _start_download_and_apply(self):
        if self._is_downloading:
            return
        download_url = self.update_info.get("download_url")
        if not download_url:
            self.lbl_status.setText("Không tìm thấy link tải bản cập nhật.")
            return

        import threading
        import tempfile
        from pathlib import Path
        import updater

        self._is_downloading = True
        self.b_update.setEnabled(False)
        self.b_update.setText("⏳ Đang tải bản mới...")
        self.b_close.setEnabled(False)
        self.lbl_status.setText("Đang kết nối tới máy chủ GitHub...")

        def _worker():
            temp_dir = Path(tempfile.gettempdir())
            target_exe = temp_dir / "MEGAMU_Update_Payload.exe"

            def _progress(downloaded: int, total: int):
                if total > 0:
                    pct = int(min(100, max(0, (downloaded / total) * 100)))
                    mb_dl = downloaded / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)
                    def _ui():
                        self.pbar.setValue(pct)
                        self.lbl_status.setText(f"Đang tải xuống: {pct}% ({mb_dl:.1f} MB / {mb_tot:.1f} MB)")
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, _ui)

            ok = updater.download_file_with_progress(
                url=download_url,
                dest_path=target_exe,
                progress_callback=_progress
            )

            if ok and target_exe.exists() and target_exe.stat().st_size > 1000000:
                def _success():
                    self.pbar.setValue(100)
                    self.lbl_status.setText("✅ Tải hoàn tất! Đang thay thế file và khởi động lại...")
                    from PySide6.QtCore import QTimer
                    def _do_restart():
                        try:
                            updater.apply_exe_update_and_restart(target_exe)
                        except Exception as e:
                            self.lbl_status.setText(f"Lỗi khởi động lại: {e}")
                            self.b_update.setEnabled(True)
                            self.b_update.setText("Thử Lại")
                            self.b_close.setEnabled(True)
                    QTimer.singleShot(1000, _do_restart)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _success)
            else:
                def _fail():
                    self._is_downloading = False
                    self.pbar.setValue(0)
                    self.lbl_status.setText("❌ Tải cập nhật thất bại!")
                    self.b_update.setEnabled(True)
                    self.b_update.setText("🔄 Thử Lại")
                    self.b_close.setEnabled(True)
                    QMessageBox.warning(
                        self,
                        "Lỗi Tải Cập Nhật",
                        "Không thể tải bản cập nhật từ GitHub. Vui lòng kiểm tra kết nối mạng hoặc mở link web."
                    )
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _fail)

        threading.Thread(target=_worker, name="QtUpdateWorker", daemon=True).start()

