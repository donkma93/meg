# -*- coding: utf-8 -*-
"""
MEGAMU RAM OPTIMIZER MODULE & STANDALONE TOOL
============================================
Công cụ tối ưu và giải phóng bộ nhớ RAM cho tiến trình MEGAMU.exe.
- Thu hồi (Trim) bộ nhớ Working Set của toàn bộ hoặc từng client MEGAMU.
- Giảm dung lượng RAM từ ~1GB xuống ~200MB - 300MB / client.
- Hỗ trợ chế độ Tự Động Tối Ưu Định Kỳ (Auto-Trim) trong nền.
- Tích hợp liền mạch vào MEGAMU Auto Train Dashboard và có thể chạy độc lập.
"""

import os
import sys
import json
import time
import ctypes
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import psutil
except ImportError:
    psutil = None

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

try:
    from tkinter import messagebox
    import tkinter as tk
except ImportError:
    messagebox = None
    tk = None

# ==============================================================================
# HẰNG SỐ & ĐƯỜNG DẪN CẤU HÌNH
# ==============================================================================
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR = app_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
RAM_CONFIG_FILE = CONFIG_DIR / "ram_optimizer_config.json"

# PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_SET_QUOTA (0x0100) | PROCESS_VM_READ (0x0010) = 0x510 (1296)
PROCESS_PERMS = 0x0510

# Kích hoạt đặc quyền SeDebugPrivilege để truy cập process khi chạy quyền Admin
def enable_debug_privilege() -> bool:
    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        h_token = ctypes.c_void_p()
        TOKEN_ADJUST_PRIVILEGES = 0x0020
        TOKEN_QUERY = 0x0008

        if kernel32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token)
        ):
            class LUID(ctypes.Structure):
                _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]

            class LUID_AND_ATTRIBUTES(ctypes.Structure):
                _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]

            class TOKEN_PRIVILEGES(ctypes.Structure):
                _fields_ = [("PrivilegeCount", ctypes.c_ulong), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

            luid = LUID()
            SE_DEBUG_NAME = "SeDebugPrivilege"
            if advapi32.LookupPrivilegeValueW(None, SE_DEBUG_NAME, ctypes.byref(luid)):
                tp = TOKEN_PRIVILEGES()
                tp.PrivilegeCount = 1
                tp.Privileges[0].Luid = luid
                tp.Privileges[0].Attributes = 0x00000002  # SE_PRIVILEGE_ENABLED
                advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
            kernel32.CloseHandle(h_token)
            return True
    except Exception:
        pass
    return False

# Gọi kích hoạt SeDebugPrivilege khi load module
enable_debug_privilege()


# ==============================================================================
# HÀM THU HỒI BỘ NHỚ RAM TIẾN TRÌNH (CORE RAM TRIM ENGINE)
# ==============================================================================
def trim_single_process(pid: int) -> bool:
    """
    Thu hồi Working Set RAM của tiến trình MEGAMU về cho hệ thống.
    Kết hợp SetProcessWorkingSetSize(-1, -1) và EmptyWorkingSet để giải phóng tối đa.
    """
    try:
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_PERMS, False, pid)
        if not h:
            # Fallback nếu cần quyền khác
            h = ctypes.windll.kernel32.OpenProcess(0x0100 | 0x0400, False, pid)
        if h:
            try:
                ctypes.windll.kernel32.SetProcessWorkingSetSize(h, -1, -1)
            except Exception:
                pass
            try:
                ret = ctypes.windll.psapi.EmptyWorkingSet(h)
            except Exception:
                ret = 1
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ret)
        return False
    except Exception:
        return False


def get_megamu_processes(proc_titles: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
    """
    Quét và trả về danh sách các tiến trình MEGAMU.exe đang chạy kèm dung lượng RAM.
    """
    clients: List[Dict[str, Any]] = []
    if not psutil:
        return clients

    for p in psutil.process_iter(["pid", "name"]):
        try:
            pname = p.info.get("name")
            if pname and "megamu.exe" in pname.lower():
                pid = p.info["pid"]
                mem_rss = p.memory_info().rss
                title = ""
                if proc_titles and pid in proc_titles:
                    title = proc_titles[pid]
                clients.append({
                    "pid": pid,
                    "title": title,
                    "mem_bytes": mem_rss,
                    "mem_mb": round(mem_rss / 1048576, 1),
                })
        except Exception:
            continue
    return clients


def optimize_all_megamu(proc_titles: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """
    Dọn RAM toàn bộ client MEGAMU đang chạy.
    Trả về thông số trước và sau khi dọn.
    """
    clients_before = get_megamu_processes(proc_titles)
    if not clients_before:
        return {
            "total_clients": 0,
            "success_count": 0,
            "before_mb": 0.0,
            "after_mb": 0.0,
            "saved_mb": 0.0,
            "saved_pct": 0.0,
        }

    total_before_b = sum(c["mem_bytes"] for c in clients_before)
    count_ok = 0
    for c in clients_before:
        if trim_single_process(c["pid"]):
            count_ok += 1
        time.sleep(0.03)

    time.sleep(0.3)
    clients_after = get_megamu_processes(proc_titles)
    total_after_b = sum(c["mem_bytes"] for c in clients_after)
    diff_b = max(0, total_before_b - total_after_b)

    before_mb = total_before_b / 1048576
    after_mb = total_after_b / 1048576
    saved_mb = diff_b / 1048576
    saved_pct = (diff_b / total_before_b * 100) if total_before_b > 0 else 0.0

    return {
        "total_clients": len(clients_before),
        "success_count": count_ok,
        "before_mb": round(before_mb, 1),
        "after_mb": round(after_mb, 1),
        "saved_mb": round(saved_mb, 1),
        "saved_pct": round(saved_pct, 1),
    }


# ==============================================================================
# BỘ QUẢN LÝ TỰ ĐỘNG TỐI ƯU RAM (RAM OPTIMIZER MANAGER)
# ==============================================================================
class RamOptimizerManager:
    """Quản lý trạng thái, cấu hình lưu trữ và luồng Auto-Trim chạy nền."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.auto_trim_enabled: bool = True  # Mặc định BẬT chạy ngầm tự động
        self.interval_seconds: int = 180  # Mặc định 3 phút
        self.total_saved_mb: float = 0.0
        self.worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.load_config()

    def load_config(self):
        try:
            if RAM_CONFIG_FILE.exists():
                data = json.loads(RAM_CONFIG_FILE.read_text(encoding="utf-8"))
                self.auto_trim_enabled = bool(data.get("auto_trim_enabled", True))
                self.interval_seconds = int(data.get("interval_seconds", 180))
                self.total_saved_mb = float(data.get("total_saved_mb", 0.0))
            else:
                self.auto_trim_enabled = True
                self.save_config()
        except Exception:
            self.auto_trim_enabled = True

    def save_config(self):
        try:
            data = {
                "auto_trim_enabled": self.auto_trim_enabled,
                "interval_seconds": self.interval_seconds,
                "total_saved_mb": round(self.total_saved_mb, 1)
            }
            RAM_CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def register_callback(self, cb: Callable[[Dict[str, Any]], None]):
        if cb not in self.callbacks:
            self.callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[Dict[str, Any]], None]):
        if cb in self.callbacks:
            self.callbacks.remove(cb)

    def _notify_callbacks(self, res: Dict[str, Any]):
        for cb in list(self.callbacks):
            try:
                cb(res)
            except Exception:
                pass

    def set_interval(self, seconds: int):
        self.interval_seconds = max(10, seconds)
        self.save_config()

    def set_auto_trim(self, enabled: bool):
        self.auto_trim_enabled = enabled
        self.save_config()
        if enabled:
            self.start_worker()
        else:
            self.stop_worker()

    def start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self._stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop_worker(self):
        self._stop_event.set()

    def _worker_loop(self):
        while not self._stop_event.is_set():
            # Chờ theo từng giây để có thể dừng ngay lập tức khi tắt
            elapsed = 0
            while elapsed < self.interval_seconds and not self._stop_event.is_set():
                time.sleep(1)
                elapsed += 1
                if not self.auto_trim_enabled:
                    return

            if self._stop_event.is_set() or not self.auto_trim_enabled:
                break

            # Thực hiện dọn RAM định kỳ
            res = optimize_all_megamu()
            if res.get("saved_mb", 0) > 0:
                self.total_saved_mb += res["saved_mb"]
                self.save_config()
            self._notify_callbacks(res)

    def trim_now(self, proc_titles: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
        res = optimize_all_megamu(proc_titles)
        if res.get("saved_mb", 0) > 0:
            self.total_saved_mb += res["saved_mb"]
            self.save_config()
        self._notify_callbacks(res)
        return res


# ==============================================================================
# GIAO DIỆN ĐỘC LẬP (STANDALONE GUI CHO MEGA RAM OPTIMIZER)
# ==============================================================================
class StandaloneRAMOptimizerApp(ctk.CTk if ctk else tk.Tk):
    """Cửa sổ giao diện tối ưu hóa RAM chạy độc lập nếu người dùng chạy trực tiếp file này."""
    def __init__(self):
        super().__init__()
        self.title("⚡ MEGAMU RAM OPTIMIZER PRO")
        self.geometry("520x460")
        self.resizable(False, False)
        self.configure(fg_color="#0e1117")

        self.manager = RamOptimizerManager.get_instance()
        self.manager.register_callback(self._on_trim_finished)

        self._build_ui()
        self._start_monitor_loop()

        if self.manager.auto_trim_enabled:
            self.manager.start_worker()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#181c26", corner_radius=8, border_width=1, border_color="#2b3244")
        header.pack(fill="x", padx=14, pady=(12, 8))

        inner_h = ctk.CTkFrame(header, fg_color="transparent")
        inner_h.pack(fill="both", expand=True, padx=14, pady=10)

        title_lbl = ctk.CTkLabel(
            inner_h,
            text="⚡ MEGAMU RAM OPTIMIZER",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            inner_h,
            text="Tự động thu hồi bộ nhớ Working Set • Tiết kiệm ~70% dung lượng RAM",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w")

        # Metric Cards
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=14, pady=4)

        self.card_clients = self._create_card(stats_frame, "CLIENT HOẠT ĐỘNG", "0 Clients", "#38bdf8")
        self.card_clients.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.card_cur_ram = self._create_card(stats_frame, "RAM ĐANG DÙNG", "0 MB", "#f59e0b")
        self.card_cur_ram.pack(side="left", fill="both", expand=True, padx=4)

        self.card_saved = self._create_card(stats_frame, "TỔNG ĐÃ TIẾT KIỆM", f"{int(self.manager.total_saved_mb)} MB", "#10b981")
        self.card_saved.pack(side="left", fill="both", expand=True, padx=(4, 0))

        # Action: Nút Tối ưu ngay
        self.btn_optimize_all = ctk.CTkButton(
            self,
            text="⚡ TỐI ƯU TOÀN BỘ MEGAMU (TRIM RAM NGAY)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=40,
            corner_radius=6,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._do_optimize_now
        )
        self.btn_optimize_all.pack(fill="x", padx=14, pady=(10, 6))

        # Auto-trim config card
        auto_frame = ctk.CTkFrame(self, corner_radius=6, fg_color="#181c26", border_width=1, border_color="#2b3244")
        auto_frame.pack(fill="x", padx=14, pady=4)

        auto_inner = ctk.CTkFrame(auto_frame, fg_color="transparent")
        auto_inner.pack(fill="x", padx=12, pady=8)

        self.auto_switch_var = ctk.BooleanVar(value=self.manager.auto_trim_enabled)
        self.auto_switch = ctk.CTkSwitch(
            auto_inner,
            text="Tự động dọn RAM định kỳ:",
            variable=self.auto_switch_var,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f8fafc",
            progress_color="#10b981",
            command=self._on_auto_switch_toggle
        )
        self.auto_switch.pack(side="left")

        # Map interval seconds to labels
        self.intervals_map = {
            "1 Phút": 60,
            "2 Phút": 120,
            "3 Phút": 180,
            "5 Phút": 300,
            "10 Phút": 600,
            "15 Phút": 900,
            "30 Phút": 1800
        }
        init_label = "3 Phút"
        for lbl, sec in self.intervals_map.items():
            if sec == self.manager.interval_seconds:
                init_label = lbl
                break

        self.interval_combo = ctk.CTkComboBox(
            auto_inner,
            values=list(self.intervals_map.keys()),
            width=110,
            height=28,
            state="readonly",
            command=self._on_interval_selected
        )
        self.interval_combo.set(init_label)
        self.interval_combo.pack(side="right")

        # Log & Status
        log_frame = ctk.CTkFrame(self, corner_radius=6, fg_color="#13161f", border_width=1, border_color="#202430")
        log_frame.pack(fill="both", expand=True, padx=14, pady=(6, 12))

        self.log_txt = ctk.CTkTextbox(
            log_frame,
            fg_color="transparent",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#cbd5e1"
        )
        self.log_txt.pack(fill="both", expand=True, padx=8, pady=8)
        self._append_log("🟢 Hệ thống sẵn sàng. Nhấn 'TRIM RAM NGAY' để giải phóng bộ nhớ.")

    def _create_card(self, parent, title, initial_val, color):
        card = ctk.CTkFrame(parent, corner_radius=6, fg_color="#181c26", border_width=1, border_color="#2b3244")
        lbl_t = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#94a3b8")
        lbl_t.pack(anchor="w", padx=10, pady=(6, 0))
        lbl_v = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=color)
        lbl_v.pack(anchor="w", padx=10, pady=(1, 6))
        card.value_label = lbl_v
        return card

    def _append_log(self, text: str):
        t_str = time.strftime("%H:%M:%S")
        self.log_txt.insert("end", f"[{t_str}] {text}\n")
        self.log_txt.see("end")

    def _do_optimize_now(self):
        self.btn_optimize_all.configure(state="disabled", text="⏳ Đang giải phóng RAM...")
        def _run():
            res = self.manager.trim_now()
            def _done():
                self.btn_optimize_all.configure(state="normal", text="⚡ TỐI ƯU TOÀN BỘ MEGAMU (TRIM RAM NGAY)")
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _on_trim_finished(self, res: Dict[str, Any]):
        def _update():
            c_cnt = res.get("total_clients", 0)
            s_cnt = res.get("success_count", 0)
            saved = res.get("saved_mb", 0.0)
            pct = res.get("saved_pct", 0.0)
            if c_cnt == 0:
                self._append_log("⚠️ Không tìm thấy tiến trình MEGAMU.exe nào đang chạy!")
            else:
                self._append_log(f"🎉 Đã giải phóng {saved:.1f} MB ({pct:.0f}%) trên {s_cnt}/{c_cnt} client MEGAMU!")

            tot_saved = self.manager.total_saved_mb
            tot_str = f"{tot_saved / 1024:.2f} GB" if tot_saved >= 1024 else f"{int(tot_saved)} MB"
            self.card_saved.value_label.configure(text=tot_str)
            self._refresh_client_stats()
        self.after(0, _update)

    def _on_auto_switch_toggle(self):
        enabled = self.auto_switch_var.get()
        self.manager.set_auto_trim(enabled)
        if enabled:
            mins = self.manager.interval_seconds // 60
            self._append_log(f"🟢 Đã BẬT Tự động dọn RAM định kỳ ({mins} phút/lần).")
        else:
            self._append_log("⏹ Đã TẮT Tự động dọn RAM định kỳ.")

    def _on_interval_selected(self, choice: str):
        sec = self.intervals_map.get(choice, 180)
        self.manager.set_interval(sec)
        self._append_log(f"⏱ Đã đặt khoảng thời gian tự động dọn RAM: {choice}.")

    def _refresh_client_stats(self):
        clients = get_megamu_processes()
        total_rss = sum(c["mem_bytes"] for c in clients)
        total_mb = total_rss / 1048576
        total_str = f"{total_mb / 1024:.2f} GB" if total_mb >= 1024 else f"{int(total_mb)} MB"
        c_text = f"{len(clients)} Client" if len(clients) == 1 else f"{len(clients)} Clients"
        self.card_clients.value_label.configure(text=c_text)
        self.card_cur_ram.value_label.configure(text=total_str)

    def _start_monitor_loop(self):
        def _worker():
            while True:
                try:
                    self._refresh_client_stats()
                except Exception:
                    pass
                time.sleep(2.5)
        threading.Thread(target=_worker, daemon=True).start()


def main():
    if ctk is None:
        print("Yêu cầu thư viện customtkinter để chạy giao diện.", flush=True)
        sys.exit(1)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = StandaloneRAMOptimizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
