# -*- coding: utf-8 -*-
"""
MEGAMU MULTI-ACCOUNT MANAGER & AUTO LOGIN ENGINE
Hệ thống quản lý không giới hạn tài khoản, tự động đọc từ Registry MEGAMU và tự động khởi chạy + login đồng loạt.
"""

import os
import sys
import json
import time
import psutil
import winreg
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

CONFIG_DIR = Path(__file__).resolve().parent / "config"
ACCOUNTS_CONFIG_FILE = CONFIG_DIR / "megamu_accounts.json"

DEFAULT_MEGAMU_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MEGAMU" / "bin" / "MEGAMU.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MEGAMU" / "MEGAMU.exe",
    Path("C:/MEGAMU/MEGAMU.exe"),
    Path("D:/MEGAMU/MEGAMU.exe"),
]


def find_megamu_exe_path() -> Optional[str]:
    """Tìm đường dẫn tệp thực thi MEGAMU.exe trên máy tính."""
    for p in DEFAULT_MEGAMU_PATHS:
        try:
            if p.is_file():
                return str(p.resolve())
        except Exception:
            pass

    # Thử tìm qua Registry nếu có
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\MEGAMU") as key:
            try:
                val, _ = winreg.QueryValueEx(key, "InstallLocation")
                if val and os.path.exists(val):
                    exe = os.path.join(val, "bin", "MEGAMU.exe")
                    if os.path.exists(exe):
                        return exe
            except Exception:
                pass
    except Exception:
        pass
    return None


def read_accounts_from_registry() -> List[Dict[str, Any]]:
    """Đọc toàn bộ danh sách tài khoản MEGAMU đã lưu sẵn trong Windows Registry."""
    accounts = []
    try:
        reg_path = r"Software\MEGAMU\MEGAMU"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            val, _ = winreg.QueryValueEx(key, "AccountList_h1682150822")
            if val:
                raw_str = bytes(val).decode("utf-8", errors="ignore").rstrip("\x00")
                data = json.loads(raw_str)
                for item in data.get("List", []):
                    u_name = item.get("Username", "")
                    if not u_name:
                        continue
                    chars = [c.get("Name", "") for c in item.get("Characters", []) if c.get("Name")]
                    default_char = chars[0] if chars else ""
                    accounts.append({
                        "username": u_name,
                        "nickname": item.get("Nickname", u_name),
                        "character": default_char,
                        "characters_list": chars,
                        "server": 1,
                        "enabled": True,
                        "source": "registry"
                    })
    except Exception as e:
        print(f"[AccountManager] Lỗi đọc Registry MEGAMU: {e}")
    return accounts


class AccountManager:
    """Quản lý danh sách tài khoản không giới hạn số lượng và thực thi AutoLogin."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.accounts: List[Dict[str, Any]] = []
        self.exe_path = find_megamu_exe_path() or ""
        self.load_accounts()

    def load_accounts(self) -> List[Dict[str, Any]]:
        """Tải cấu hình tài khoản từ file JSON, nếu chưa có thì đọc từ Registry MEGAMU."""
        if ACCOUNTS_CONFIG_FILE.exists():
            try:
                with open(ACCOUNTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.accounts = data.get("accounts", [])
                    saved_exe = data.get("exe_path", "")
                    if saved_exe and os.path.isfile(saved_exe):
                        self.exe_path = saved_exe
            except Exception as e:
                print(f"[AccountManager] Lỗi đọc config: {e}")

        # Nếu chưa có tài khoản nào, tự động import từ Registry
        if not self.accounts:
            self.accounts = read_accounts_from_registry()
            self.save_accounts()
        return self.accounts

    def save_accounts(self):
        """Lưu toàn bộ danh sách tài khoản ra file JSON."""
        try:
            with open(ACCOUNTS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "exe_path": self.exe_path,
                    "accounts": self.accounts
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AccountManager] Lỗi lưu config: {e}")

    def import_from_registry(self) -> int:
        """Đọc và sáp nhập các tài khoản mới từ Registry vào danh sách hiện tại."""
        reg_accs = read_accounts_from_registry()
        existing_users = {a["username"].lower() for a in self.accounts}
        added = 0
        for ra in reg_accs:
            if ra["username"].lower() not in existing_users:
                self.accounts.append(ra)
                existing_users.add(ra["username"].lower())
                added += 1
            else:
                # Cập nhật danh sách nhân vật mới nếu có
                for a in self.accounts:
                    if a["username"].lower() == ra["username"].lower():
                        if ra.get("characters_list"):
                            a["characters_list"] = ra["characters_list"]
                        break
        if added > 0:
            self.save_accounts()
        return added

    def add_account(self, username: str, character: str = "", server: int = 1) -> bool:
        """Thêm tài khoản mới không giới hạn."""
        username = username.strip()
        if not username:
            return False
        for a in self.accounts:
            if a["username"].lower() == username.lower():
                a["character"] = character
                a["server"] = server
                a["enabled"] = True
                self.save_accounts()
                return True
        self.accounts.append({
            "username": username,
            "nickname": username,
            "character": character,
            "characters_list": [character] if character else [],
            "server": server,
            "enabled": True,
            "source": "manual"
        })
        self.save_accounts()
        return True

    def remove_account(self, username: str) -> bool:
        """Xóa một tài khoản khỏi danh sách."""
        initial_len = len(self.accounts)
        self.accounts = [a for a in self.accounts if a["username"].lower() != username.lower()]
        if len(self.accounts) < initial_len:
            self.save_accounts()
            return True
        return False

    def update_account(self, username: str, character: Optional[str] = None, server: Optional[int] = None) -> bool:
        """Cập nhật nhân vật hoặc server của một tài khoản."""
        for a in self.accounts:
            if a["username"].lower() == username.lower():
                if character is not None:
                    a["character"] = character
                    # Đảm bảo nhân vật có trong characters_list
                    if character and character not in a.get("characters_list", []):
                        a.setdefault("characters_list", []).append(character)
                if server is not None:
                    a["server"] = int(server)
                self.save_accounts()
                return True
        return False

    def toggle_all(self, enabled: bool):
        """Bật hoặc tắt toàn bộ tài khoản trong danh sách."""
        for a in self.accounts:
            a["enabled"] = enabled
        self.save_accounts()

    def set_exe_path(self, path: str):
        """Cập nhật đường dẫn MEGAMU.exe."""
        if path and os.path.isfile(path):
            self.exe_path = path
            self.save_accounts()

    def get_enabled_accounts(self) -> List[Dict[str, Any]]:
        """Lấy tất cả các tài khoản đang được kích hoạt."""
        return [a for a in self.accounts if a.get("enabled", True)]

    def launch_single_account(self, acc: Dict[str, Any], on_log: Optional[Callable[[str], None]] = None) -> Optional[int]:
        """
        Khởi chạy 1 client MEGAMU và tự động đăng nhập vào tài khoản + nhân vật đã chỉ định.
        Returns: PID của tiến trình MEGAMU mới tạo hoặc None nếu thất bại.
        """
        username = acc.get("username", "")
        character = acc.get("character", "")
        server = acc.get("server", 1)

        def _log(msg: str):
            if on_log:
                on_log(msg)
            else:
                print(msg)

        exe = self.exe_path or find_megamu_exe_path()
        if not exe or not os.path.isfile(exe):
            _log(f"❌ Không tìm thấy tệp MEGAMU.exe tại '{exe}'! Vui lòng kiểm tra lại đường dẫn cài đặt.")
            return None

        _log(f"🚀 [Account: {username}] Đang khởi chạy MEGAMU.exe...")
        try:
            proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
            pid = proc.pid
            _log(f"   → Đã tạo tiến trình PID {pid}. Chờ GameAssembly.dll nạp (khoảng 3.5s)...")
        except Exception as ex:
            _log(f"❌ Lỗi khởi chạy tiến trình: {ex}")
            return None

        # Chờ game nạp xong GameAssembly.dll
        time.sleep(3.5)

        # Gắn DirectEngine và gọi AutoLogin native
        try:
            from meg_direct_engine import MegDirectEngine
            eng = MegDirectEngine.get_engine(pid)
            if not eng:
                _log(f"⚠️ [PID {pid}] Không tạo được Direct Engine!")
                return pid

            attached = False
            for retry in range(5):
                if eng.attach():
                    attached = True
                    break
                time.sleep(1.0)

            if not attached:
                _log(f"⚠️ [PID {pid}] Game chưa sẵn sàng để attach Frida. Đăng nhập thủ công hoặc thử lại sau.")
                return pid

            _log(f"🔑 [PID {pid}] Đang gửi lệnh AutoLogin (Server: {server}, Acc: '{username}', NV: '{character}')...")
            res = eng.auto_login(server=server, account=username, character=character)
            if res.get("ok"):
                _log(f"✅ [PID {pid} - {username}] Gửi lệnh AutoLogin thành công! Game đang tự động vào nhân vật '{character}'.")
            else:
                _log(f"⚠️ [PID {pid} - {username}] AutoLogin phản hồi: {res}")
            return pid
        except Exception as eE:
            _log(f"⚠️ [PID {pid}] Lỗi khi gọi AutoLogin: {eE}")
            return pid

    def login_existing_pid(self, pid: int, acc: Dict[str, Any], on_log: Optional[Callable[[str], None]] = None) -> bool:
        """Gửi lệnh AutoLogin native vào một tiến trình MEGAMU đang chạy."""
        username = acc.get("username", "")
        character = acc.get("character", "")
        server = acc.get("server", 1)

        def _log(msg: str):
            if on_log:
                on_log(msg)
            else:
                print(msg)

        if not pid or not psutil.pid_exists(pid):
            _log(f"❌ Tiến trình PID {pid} không tồn tại!")
            return False

        try:
            from meg_direct_engine import MegDirectEngine
            eng = MegDirectEngine.get_engine(pid)
            if not eng.is_ready:
                if not eng.attach():
                    _log(f"⚠️ [PID {pid}] Không thể kết nối Frida engine!")
                    return False
            res = eng.auto_login(server=server, account=username, character=character)
            if res.get("ok"):
                _log(f"✅ [PID {pid} - {username}] Gửi lệnh AutoLogin thành công! (Server {server}, Nhân vật '{character}')")
                return True
            else:
                _log(f"⚠️ [PID {pid} - {username}] AutoLogin phản hồi: {res}")
                return False
        except Exception as ex:
            _log(f"❌ [PID {pid}] Lỗi AutoLogin: {ex}")
            return False

    def launch_all_enabled(
        self,
        delay_sec: float = 3.0,
        on_log: Optional[Callable[[str], None]] = None,
        on_launched: Optional[Callable[[Dict[str, Any], int], None]] = None
    ) -> List[int]:
        """
        Khởi chạy và tự động đăng nhập TẤT CẢ các tài khoản đang bật (KHÔNG GIỚI HẠN SỐ LƯỢNG).
        delay_sec: Thời gian giãn cách giữa các lần mở game để chống nghẽn CPU/RAM.
        """
        def _log(msg: str):
            if on_log:
                on_log(msg)
            else:
                print(msg)

        enabled = self.get_enabled_accounts()
        if not enabled:
            _log("⚠️ Không có tài khoản nào được chọn để mở! Vui lòng tích chọn tài khoản trước.")
            return []

        _log(f"🌟 BẮT ĐẦU KHỞI CHẠY & AUTO LOGIN {len(enabled)} TÀI KHOẢN ĐỒNG LOẠT (Giãn cách {delay_sec}s)...")
        pids = []
        for idx, acc in enumerate(enabled):
            u = acc.get("username", "")
            c = acc.get("character", "")
            _log(f"\n[{idx+1}/{len(enabled)}] Đang xử lý tài khoản: {u} (Nhân vật: {c})")
            pid = self.launch_single_account(acc, on_log=on_log)
            if pid:
                pids.append(pid)
                if on_launched:
                    try:
                        on_launched(acc, pid)
                    except Exception:
                        pass
            if idx < len(enabled) - 1:
                _log(f"⏳ Đang chờ {delay_sec}s trước khi mở tài khoản kế tiếp...")
                time.sleep(delay_sec)

        _log(f"\n🎉 HOÀN TẤT! Đã mở và gửi lệnh AutoLogin cho {len(pids)}/{len(enabled)} tài khoản thành công!")
        return pids
