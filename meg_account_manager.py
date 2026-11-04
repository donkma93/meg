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

DEFAULT_SPOT_CONFIG = {
    "auto_dispatch": True,
    "map": "arena",
    "x": 125,
    "y": 125,
    "auto_helper": True,
    "batch_size": 5,
    "delay_sec": 2.5,
    "throttle_fps": True,
    "target_fps": 15
}

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
                        "token": item.get("Token", ""),
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
        self.spot_config: Dict[str, Any] = dict(DEFAULT_SPOT_CONFIG)
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
                    if "spot_config" in data and isinstance(data["spot_config"], dict):
                        self.spot_config = dict(DEFAULT_SPOT_CONFIG)
                        self.spot_config.update(data["spot_config"])
            except Exception as e:
                print(f"[AccountManager] Lỗi đọc config: {e}")

        # Tự động import và đồng bộ token từ Registry
        self.import_from_registry()
        return self.accounts

    def save_accounts(self):
        """Lưu toàn bộ danh sách tài khoản ra file JSON."""
        try:
            with open(ACCOUNTS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "exe_path": self.exe_path,
                    "spot_config": self.spot_config,
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
                # Cập nhật danh sách nhân vật và token mới nhất từ Registry
                for a in self.accounts:
                    if a["username"].lower() == ra["username"].lower():
                        if ra.get("characters_list"):
                            a["characters_list"] = ra["characters_list"]
                        if ra.get("token"):
                            a["token"] = ra["token"]
                        break
        self.save_accounts()
        return added

    def add_account(self, username: str, password: str = "", character: str = "", server: int = 1) -> bool:
        """Thêm tài khoản mới không giới hạn (hỗ trợ lưu mật khẩu tự động)."""
        username = username.strip()
        if not username:
            return False
        for a in self.accounts:
            if a["username"].lower() == username.lower():
                if password:
                    a["password"] = password
                a["character"] = character
                a["server"] = server
                a["enabled"] = True
                self.save_accounts()
                return True
        acc_data = {
            "username": username,
            "nickname": username,
            "character": character,
            "characters_list": [character] if character else [],
            "server": server,
            "enabled": True,
            "source": "manual"
        }
        if password:
            acc_data["password"] = password
        self.accounts.append(acc_data)
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

    def update_account(
        self,
        username: str,
        password: Optional[str] = None,
        character: Optional[str] = None,
        server: Optional[int] = None,
        spot_map: Optional[str] = None,
        spot_x: Optional[int] = None,
        spot_y: Optional[int] = None
    ) -> bool:
        """Cập nhật mật khẩu, nhân vật, server hoặc tọa độ bãi train riêng của một tài khoản."""
        for a in self.accounts:
            if a["username"].lower() == username.lower():
                if password is not None:
                    if password == "":
                        a.pop("password", None)
                    else:
                        a["password"] = password
                if character is not None:
                    a["character"] = character
                    if character and character not in a.get("characters_list", []):
                        a.setdefault("characters_list", []).append(character)
                if server is not None:
                    a["server"] = int(server)
                if spot_map is not None:
                    if not spot_map.strip():
                        a.pop("spot_map", None)
                    else:
                        a["spot_map"] = spot_map.strip()
                if spot_x is not None:
                    if spot_x < 0:
                        a.pop("spot_x", None)
                    else:
                        a["spot_x"] = spot_x
                if spot_y is not None:
                    if spot_y < 0:
                        a.pop("spot_y", None)
                    else:
                        a["spot_y"] = spot_y
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

    def import_from_txt(self, text_or_path: str) -> int:
        """
        Nhập danh sách tài khoản hàng loạt (hỗ trợ tới 200+ tài khoản) từ file TXT hoặc chuỗi văn bản.
        Hỗ trợ các định dạng dòng:
          username|password|character|server
          username:password:character:server
          username|password
          username password
        """
        lines = []
        if os.path.isfile(text_or_path):
            try:
                with open(text_or_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"[AccountManager] Lỗi đọc file txt: {e}")
                return 0
        else:
            lines = text_or_path.splitlines()

        added_or_updated = 0
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            delim = None
            for d in ["|", "	", ",", ":"]:
                if d in line:
                    delim = d
                    break

            parts = [p.strip() for p in line.split(delim)] if delim else line.split()
            if not parts:
                continue

            u = parts[0]
            p = parts[1] if len(parts) > 1 else ""
            c = parts[2] if len(parts) > 2 else ""
            s = 1
            if len(parts) > 3:
                try:
                    s = int(parts[3].replace("Server", "").replace("server", "").strip())
                except Exception:
                    s = 1

            if self.add_account(username=u, password=p, character=c, server=s):
                added_or_updated += 1

        return added_or_updated

    def export_to_txt(self, file_path: str) -> int:
        """Xuất toàn bộ danh sách tài khoản ra file văn bản chuẩn (username|password|character|server)."""
        cnt = 0
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for a in self.accounts:
                    u = a.get("username", "")
                    p = a.get("password", "")
                    c = a.get("character", "")
                    s = a.get("server", 1)
                    f.write(f"{u}|{p}|{c}|{s}\n")
                    cnt += 1
        except Exception as e:
            print(f"[AccountManager] Lỗi xuất file txt: {e}")
        return cnt

    def get_waves(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """Chia toàn bộ danh sách tài khoản thành các đợt (waves) đánh số thứ tự."""
        if batch_size < 1:
            batch_size = 5
        waves = []
        total = len(self.accounts)
        if total == 0:
            return waves
        for i in range(0, total, batch_size):
            chunk = self.accounts[i:i + batch_size]
            wave_num = (i // batch_size) + 1
            start_num = i + 1
            end_num = min(i + batch_size, total)
            label = f"Đợt {wave_num:02d} (Acc {start_num} - {end_num})"
            waves.append({
                "wave_num": wave_num,
                "label": label,
                "start_idx": i,
                "end_idx": end_num,
                "accounts": chunk
            })
        return waves

    def select_wave(self, wave_num: int, batch_size: int = 5):
        """Chỉ kích hoạt (enabled=True) các tài khoản thuộc Đợt chỉ định, tắt các đợt khác."""
        waves = self.get_waves(batch_size=batch_size)
        target_wave = None
        for w in waves:
            if w["wave_num"] == wave_num:
                target_wave = w
                break
        if not target_wave:
            return

        target_usernames = {a["username"].lower() for a in target_wave["accounts"]}
        for a in self.accounts:
            a["enabled"] = (a["username"].lower() in target_usernames)
        self.save_accounts()

    def launch_single_account(self, acc: Dict[str, Any], on_log: Optional[Callable[[str], None]] = None) -> Optional[int]:
        """
        Khởi chạy 1 client MEGAMU và tự động đăng nhập vào tài khoản + nhân vật đã chỉ định.
        Returns: PID của tiến trình MEGAMU mới tạo hoặc None nếu thất bại.
        """
        username = acc.get("username", "")
        password = acc.get("password", "")
        token = acc.get("token", "")
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
            parent_dir = os.path.dirname(exe)
            if os.path.basename(parent_dir).lower() == "bin":
                work_dir = os.path.dirname(parent_dir)
            else:
                work_dir = parent_dir
            proc = subprocess.Popen([exe], cwd=work_dir)
            pid = proc.pid
            _log(f"   → Đã tạo tiến trình PID {pid}. Đang chờ Game khởi động và nạp GameAssembly.dll (chờ 3.5s)...")
        except Exception as ex:
            _log(f"❌ Lỗi khởi chạy tiến trình: {ex}")
            return None

        # Chờ 3.5s để DirectX Window và GameAssembly hoàn tất nạp DllMain và khởi tạo màn hình ban đầu
        time.sleep(3.5)

        # Gắn DirectEngine và kích hoạt AutoLogin native trên Unity Main Thread
        try:
            from meg_direct_engine import MegDirectEngine
            eng = MegDirectEngine.get_engine(pid)
            if not eng:
                _log(f"⚠️ [PID {pid}] Không tạo được Direct Engine!")
                return pid

            attached = False
            for _ in range(8):
                if not psutil.pid_exists(pid):
                    _log(f"❌ [PID {pid}] Tiến trình game đã bị đóng!")
                    return None
                if eng.attach():
                    attached = True
                    break
                time.sleep(1.0)

            if not attached:
                _log(f"⚠️ [PID {pid}] Game chưa sẵn sàng để attach Frida. Đăng nhập thủ công hoặc thử lại sau.")
                return pid

            has_pwd = bool(password)
            has_tok = bool(token)
            if has_pwd:
                auth_tag = " (Đăng nhập Form & Mật khẩu)"
            elif has_tok:
                auth_tag = " (Đăng nhập Token Registry)"
            else:
                auth_tag = " (Chưa có mật khẩu / token)"
            _log(f"🔑 [PID {pid}] Đã gắn Hook thành công! Đang kích hoạt AutoLogin{auth_tag} (Server: {server}, Acc: '{username}', NV: '{character}')...")
            eng.auto_login(server=server, account=username, character=character, password=password, token=token)

            _log(f"⏳ [PID {pid}] Đang chờ game nạp màn hình MLoginUI trên Main Thread (tối đa 30s)...")
            start_wait = time.time()
            submitted = False
            while time.time() - start_wait < 30.0:
                if not psutil.pid_exists(pid):
                    _log(f"❌ [PID {pid}] Tiến trình game đã bị đóng!")
                    return None
                status = eng.get_autologin_status()
                if status.get("submitted") or status.get("done"):
                    submitted = True
                    stage = status.get("stage", "")
                    if stage == "submitted_password":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ ĐIỀN FORM VÀ SUBMIT MẬT KHẨU THÀNH CÔNG trên Main Thread! Game đang vào nhân vật '{character}'...")
                    elif stage == "submitted_token":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ ĐĂNG NHẬP BẰNG TOKEN REGISTRY THÀNH CÔNG trên Main Thread! Game đang vào nhân vật '{character}'...")
                    elif stage == "in_game_world":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ VÀO THẾ GIỚI GAME THÀNH CÔNG! (Nhân vật '{character}')")
                    elif stage == "in_character_lobby":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ VÀO MÀN HÌNH CHỌN NHÂN VẬT THÀNH CÔNG!")
                    elif stage == "need_credentials":
                        _log(f"⚠️ [PID {pid} - {username}] Tài khoản chưa có Mật khẩu và chưa có Token lưu trong Registry! Vui lòng nhập mật khẩu vào bảng tài khoản.")
                        break
                    else:
                        _log(f"✅ [PID {pid} - {username}] AutoLogin đã kích hoạt thành công trên Main Thread!")
                    break
                time.sleep(0.5)

            if not submitted:
                _log(f"⚠️ [PID {pid} - {username}] Hết 30s chờ MLoginUI. Lệnh đăng nhập vẫn được giữ trong hàng đợi Main Thread.")
            return pid
        except Exception as eE:
            _log(f"⚠️ [PID {pid}] Lỗi khi gọi AutoLogin: {eE}")
            return pid

    def login_existing_pid(self, pid: int, acc: Dict[str, Any], on_log: Optional[Callable[[str], None]] = None) -> bool:
        """Gửi lệnh AutoLogin native vào một tiến trình MEGAMU đang chạy."""
        username = acc.get("username", "")
        password = acc.get("password", "")
        token = acc.get("token", "")
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
            eng.auto_login(server=server, account=username, character=character, password=password, token=token)

            # Chờ Main Thread submit trong tối đa 4 giây
            start_wait = time.time()
            while time.time() - start_wait < 4.0:
                status = eng.get_autologin_status()
                if status.get("submitted") or status.get("done"):
                    stage = status.get("stage", "")
                    if stage == "submitted_password":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ ĐIỀN FORM VÀ SUBMIT MẬT KHẨU THÀNH CÔNG trên Main Thread! (Server {server}, Nhân vật '{character}')")
                    elif stage == "submitted_token":
                        _log(f"✅ [PID {pid} - {username}] ĐÃ ĐĂNG NHẬP BẰNG TOKEN THÀNH CÔNG trên Main Thread! (Server {server}, Nhân vật '{character}')")
                    else:
                        _log(f"✅ [PID {pid} - {username}] Đã kích hoạt AutoLogin thành công!")
                    return True
                time.sleep(0.2)

            _log(f"✅ [PID {pid} - {username}] Đã đưa lệnh AutoLogin vào hàng đợi Main Thread (Server {server}, Nhân vật '{character}')")
            return True
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

    def update_spot_config(self, **kwargs):
        """Cập nhật các thông số cấu hình ra bãi tự động và lưu file JSON."""
        self.spot_config.update(kwargs)
        self.save_accounts()

    def dispatch_account_to_spot(
        self,
        pid: int,
        map_name: str = "arena",
        target_x: int = 125,
        target_y: int = 125,
        enable_helper: bool = True,
        throttle_fps: bool = True,
        target_fps: int = 15,
        on_log: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Tự động đưa nhân vật đã login ra bãi train:
        1. Chờ SceneHandler.Type == 4 (Playing) & worldReady (tối đa 40s)
        2. Dịch chuyển (/m <map_name>) nếu chưa ở đúng map
        3. Dùng Unity NavMesh chạy tự động tới tọa độ (X, Y)
        4. Tự động kích hoạt MuHelper khi đến bãi
        5. Giảm FPS xuống 15 & tối ưu hóa RAM (EmptyWorkingSet)
        """
        def _log(msg: str):
            if on_log:
                on_log(msg)
            else:
                print(msg)

        if not pid or not psutil.pid_exists(pid):
            _log(f"❌ [PID {pid}] Tiến trình game không tồn tại!")
            return False

        try:
            from meg_direct_engine import MegDirectEngine
            eng = MegDirectEngine.get_engine(pid)
            if not eng.is_ready:
                if not eng.attach():
                    _log(f"⚠️ [PID {pid}] Không thể kết nối Frida engine!")
                    return False

            _log(f"⏳ [PID {pid}] Đang chờ game vào thế giới (In-Game World)...")
            start_wait = time.time()
            in_world = False
            while time.time() - start_wait < 40.0:
                if cancel_check and cancel_check():
                    _log(f"⏹️ [PID {pid}] Đã dừng theo yêu cầu của người dùng.")
                    return False
                if not psutil.pid_exists(pid):
                    _log(f"❌ [PID {pid}] Game đã bị đóng!")
                    return False

                sc = eng.get_scene_state()
                # Type 4 = Playing
                if sc.get("type") == 4 and sc.get("worldReady"):
                    in_world = True
                    break

                # Fallback kiểm tra qua player info
                p_info = eng.get_player_info(allow_blocking=False)
                if p_info and p_info.get("mapId", -1) >= 0 and (p_info.get("x", 0) > 0 or p_info.get("y", 0) > 0 or p_info.get("name")):
                    in_world = True
                    break

                time.sleep(0.6)

            if not in_world:
                _log(f"⚠️ [PID {pid}] Hết 40s chờ vào game. Thử gửi lệnh di chuyển...")

            # 2. Xử lý chuyển Map qua MapResolver
            map_name_clean = str(map_name or "arena").strip()
            from meg_auto_worker import MapResolver
            resolver = MapResolver.get_instance()
            cmd = resolver.resolve(map_name_clean)
            if not cmd:
                cmd = f"/m {map_name_clean}" if not map_name_clean.startswith("/") else map_name_clean
            target_map_id = resolver.get_map_id(map_name_clean)

            cur_info = eng.get_player_info()
            cur_map_id = cur_info.get("mapId", -1) if cur_info else -1

            need_warp = True
            if target_map_id is not None and cur_map_id == target_map_id:
                need_warp = False
                _log(f"🗺️ [PID {pid}] Nhân vật đã ở sẵn Map '{map_name_clean}' (MapID {cur_map_id}). Không cần warp.")

            if need_warp:
                _log(f"⚡ [PID {pid}] Đang dịch chuyển đến Map '{map_name_clean}' bằng lệnh: {cmd}...")
                eng.send_chat(cmd)
                time.sleep(1.2)
                # Chờ nạp world sau warp
                for _ in range(15):
                    if cancel_check and cancel_check():
                        return False
                    sc = eng.get_scene_state()
                    if sc.get("worldReady"):
                        break
                    time.sleep(0.4)

            # 3. Chạy NavMesh tới tọa độ bãi (X, Y)
            _log(f"🏃 [PID {pid}] Đang di chuyển NavMesh tới tọa độ bãi ({target_x}, {target_y})...")
            eng.start_auto_move(target_x, target_y, helper=enable_helper)

            # Theo dõi quá trình di chuyển (tối đa 40s)
            start_move = time.time()
            arrived = False
            while time.time() - start_move < 40.0:
                if cancel_check and cancel_check():
                    eng.stop_auto_move()
                    return False
                if not psutil.pid_exists(pid):
                    return False

                info = eng.get_player_info()
                if info:
                    cx = info.get("x", 0)
                    cy = info.get("y", 0)
                    dist = ((cx - target_x) ** 2 + (cy - target_y) ** 2) ** 0.5
                    if dist <= 3.0:
                        arrived = True
                        _log(f"🎯 [PID {pid}] ĐÃ ĐẾN BÃI TRAIN TỌA ĐỘ ({cx}, {cy}) (Khoảng cách {dist:.1f})!")
                        break
                    elif not info.get("isMoving") and dist <= 6.0 and (time.time() - start_move > 4.0):
                        arrived = True
                        _log(f"🎯 [PID {pid}] Đã dừng tại tọa độ bãi ({cx}, {cy})!")
                        break
                time.sleep(0.7)

            if not arrived:
                _log(f"⚠️ [PID {pid}] Đã hết thời gian di chuyển (40s). Kích hoạt trạng thái bãi tại vị trí hiện tại.")

            # 4. Kích hoạt MuHelper nếu chưa bật
            if enable_helper:
                if not eng.is_helper_active():
                    _log(f"🤖 [PID {pid}] Đang kích hoạt MuHelper...")
                    eng.start_helper(target_x, target_y)
                    time.sleep(0.6)
                if eng.is_helper_active():
                    _log(f"✅ [PID {pid}] MuHelper đang hoạt động đánh quái tự động!")
                else:
                    _log(f"⚠️ [PID {pid}] Thử bật lại MuHelper lần 2...")
                    eng.start_helper(target_x, target_y)

            # 5. Tối ưu hóa tài nguyên (Hạ FPS và trim working set RAM)
            if throttle_fps:
                eng.set_target_fps(target_fps)
                _log(f"⚡ [PID {pid}] Đã hạ FPS xuống {target_fps} để tối ưu hóa CPU/GPU.")
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    psapi = ctypes.windll.psapi
                    h_proc = kernel32.OpenProcess(0x1F0FFF, False, pid)
                    if h_proc:
                        psapi.EmptyWorkingSet(h_proc)
                        kernel32.CloseHandle(h_proc)
                except Exception:
                    pass

            _log(f"🎉 [PID {pid}] ĐÃ HOÀN TẤT RA BÃI & ĐANG TRAIN TỰ ĐỘNG THÀNH CÔNG!")
            return True
        except Exception as e:
            _log(f"❌ [PID {pid}] Lỗi khi ra bãi: {e}")
            return False

    def launch_and_dispatch_single(
        self,
        acc: Dict[str, Any],
        spot_cfg: Optional[Dict[str, Any]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Optional[int]:
        """Khởi chạy client, AutoLogin và tự động đưa ra bãi."""
        pid = self.launch_single_account(acc, on_log=on_log)
        if not pid:
            return None

        cfg = dict(self.spot_config)
        if spot_cfg:
            cfg.update(spot_cfg)

        m_name = acc.get("spot_map") or cfg.get("map", "arena")
        tx = int(acc.get("spot_x") if acc.get("spot_x") is not None else cfg.get("x", 125))
        ty = int(acc.get("spot_y") if acc.get("spot_y") is not None else cfg.get("y", 125))
        auto_h = bool(cfg.get("auto_helper", True))
        throt = bool(cfg.get("throttle_fps", True))
        tfps = int(cfg.get("target_fps", 15))

        ok = self.dispatch_account_to_spot(
            pid=pid,
            map_name=m_name,
            target_x=tx,
            target_y=ty,
            enable_helper=auto_h,
            throttle_fps=throt,
            target_fps=tfps,
            on_log=on_log,
            cancel_check=cancel_check
        )
        return pid if ok else None
