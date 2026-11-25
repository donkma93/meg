# ==============================================================================
# MEGATEAM LICENSE CLIENT - XÁC THỰC BẢN QUYỀN CLIENT CHO MEGAMU AUTO TRAIN
# TÍCH HỢP NATIVE C++ BRIDGE (meg_license_bridge.dll) & PYTHON FALLBACK
# ==============================================================================
import os
import sys
import json
import hashlib
import platform
import socket
import ctypes
import threading
import time
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

try:
    import _embedded_bridge
except ImportError:
    _embedded_bridge = None

def is_packaged_app() -> bool:
    """Kiểm tra ứng dụng đang chạy dưới dạng file đóng gói (.exe PyInstaller hoặc Nuitka)."""
    if getattr(sys, "frozen", False):
        return True
    if "__compiled__" in globals():
        return True
    main_mod = sys.modules.get("__main__")
    if main_mod is not None and getattr(main_mod, "__compiled__", None) is not None:
        return True
    return bool(os.environ.get("NUITKA_ONEFILE_PARENT") or os.environ.get("NUITKA_ONEFILE_DIRECTORY"))

def get_real_app_dir() -> Path:
    # 1. Nuitka onefile / standalone binary: __compiled__.containing_dir trỏ chính xác vào thư mục chứa file .exe gốc
    try:
        c_obj = globals().get("__compiled__") or getattr(sys.modules.get("__main__"), "__compiled__", None)
        if c_obj and hasattr(c_obj, "containing_dir") and c_obj.containing_dir:
            c_dir = Path(c_obj.containing_dir).resolve()
            if c_dir.is_dir():
                return c_dir
    except Exception:
        pass
    # 2. Nuitka NUITKA_ONEFILE_DIRECTORY
    onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
    if onefile_dir and Path(onefile_dir).is_dir():
        return Path(onefile_dir).resolve()
    # 3. Khi đóng gói exe (frozen/compiled): ưu tiên sys.executable hoặc sys.argv[0]
    if is_packaged_app():
        try:
            cand = Path(sys.executable).resolve().parent
            if cand.is_dir() and "temp" not in str(cand).lower():
                return cand
        except Exception:
            pass
        if sys.argv and sys.argv[0]:
            try:
                cand = Path(sys.argv[0]).resolve().parent
                if cand.is_dir() and "temp" not in str(cand).lower():
                    return cand
            except Exception:
                pass
    # 4. Khi chạy mã nguồn Python: thư mục chứa file license_client.py
    return Path(__file__).resolve().parent

BASE_DIR = get_real_app_dir()

CONFIG_DIR = BASE_DIR / "config"
LICENSE_FILE = CONFIG_DIR / "license.json"
SETTINGS_FILE = CONFIG_DIR / "license_settings.json"

DEFAULT_SERVER_URL = "https://megamuoffical.com"
LOCAL_SERVER_URL = "http://127.0.0.1:8000"

def get_default_server_url() -> str:
    """Lấy Server URL từ config/license_settings.json nếu có, nếu không dùng DEFAULT_SERVER_URL."""
    try:
        if SETTINGS_FILE.is_file():
            cfg = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            u = str(cfg.get("server_url", "")).strip()
            if u:
                return u
    except Exception:
        pass
    return DEFAULT_SERVER_URL

def find_bridge_dll_path() -> Optional[Path]:
    """
    Tìm đường dẫn tệp meg_license_bridge.dll một cách linh hoạt theo thời gian thực.
    Nếu chưa có trên đĩa, tự động trích xuất từ payload nhúng (Embedded) ra ổ đĩa.
    """
    candidates = [
        # 1. Thư mục thật của app (nơi đặt file .exe)
        (BASE_DIR / "meg_license_bridge.dll").resolve(),
        (BASE_DIR / "_internal" / "meg_license_bridge.dll").resolve(),
        # 2. Thư mục giải nén nội bộ của Nuitka Onefile (nơi chứa DLL nhúng trong .exe)
        (Path(sys.executable).resolve().parent / "meg_license_bridge.dll").resolve(),
        (Path(sys.executable).resolve().parent / "native_bin" / "meg_license_bridge.dll").resolve(),
        # 3. Thư mục mã nguồn / module
        (Path(__file__).resolve().parent / "meg_license_bridge.dll").resolve(),
        # 4. Thư mục làm việc hiện tại
        (Path.cwd() / "meg_license_bridge.dll").resolve(),
        # 5. Thư mục Temp hệ thống
        (Path(os.environ.get("TEMP", os.environ.get("TMP", ""))) / "meg_license_bridge.dll").resolve(),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.insert(0, (Path(meipass) / "meg_license_bridge.dll").resolve())

    for p in candidates:
        try:
            if p.is_file() and p.stat().st_size > 10000:
                return p.resolve()
        except Exception:
            pass

    # TỰ ĐỘNG TRÍCH XUẤT TỪ BẢN NHÚNG NẾU CHƯA CÓ TRÊN ĐĨA
    if _embedded_bridge:
        try:
            # 1. Ưu tiên ghi ra bên cạnh file .exe
            target = (BASE_DIR / "meg_license_bridge.dll").resolve()
            if _embedded_bridge.extract_to(target) and target.is_file():
                return target
        except Exception:
            pass
        try:
            # 2. Dự phòng ghi ra Temp nếu BASE_DIR bị cấm ghi
            temp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", ".")))
            target_temp = (temp_dir / "meg_license_bridge.dll").resolve()
            if _embedded_bridge.extract_to(target_temp) and target_temp.is_file():
                return target_temp
        except Exception:
            pass

    return None

BRIDGE_DLL_FILE = find_bridge_dll_path() or (BASE_DIR / "meg_license_bridge.dll").resolve()

def _get_ssl_context():
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

_native_bridge = None

def _get_native_bridge(force_reload: bool = False):
    """
    Tải thư viện Native C++ Bridge DLL (meg_license_bridge.dll).
    Nếu ban đầu khởi động chưa có file, hàm tự động trích xuất và nạp DLL ngay lập tức.
    """
    global _native_bridge, BRIDGE_DLL_FILE
    if not force_reload and _native_bridge is not None:
        return _native_bridge

    dll_path = find_bridge_dll_path()
    if dll_path:
        dll_path = dll_path.resolve()
        BRIDGE_DLL_FILE = dll_path
        try:
            try:
                os.add_dll_directory(str(dll_path.parent))
            except Exception:
                pass
            dll = ctypes.CDLL(str(dll_path))
            dll.Bridge_GetVersion.restype = ctypes.c_int
            dll.Bridge_GetHwid.argtypes = [ctypes.c_char_p, ctypes.c_int]
            dll.Bridge_GetHwid.restype = ctypes.c_int
            dll.Bridge_ActivateLicense.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int
            ]
            dll.Bridge_ActivateLicense.restype = ctypes.c_int
            dll.Bridge_VerifyLicense.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int
            ]
            dll.Bridge_VerifyLicense.restype = ctypes.c_int

            # Lớp 2 & 3: Xác thực bộ nhớ C++ và kho Game Offsets chỉ lưu trên RAM
            if hasattr(dll, "Bridge_IsAuthenticated"):
                dll.Bridge_IsAuthenticated.restype = ctypes.c_int
            if hasattr(dll, "Bridge_VerifyOfflineSignature"):
                dll.Bridge_VerifyOfflineSignature.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                dll.Bridge_VerifyOfflineSignature.restype = ctypes.c_int
            if hasattr(dll, "Bridge_GetGameOffsets"):
                dll.Bridge_GetGameOffsets.argtypes = [ctypes.c_char_p, ctypes.c_int]
                dll.Bridge_GetGameOffsets.restype = ctypes.c_int
            if hasattr(dll, "Bridge_HasGameOffsets"):
                dll.Bridge_HasGameOffsets.restype = ctypes.c_int
            if hasattr(dll, "Bridge_ClearOffsets"):
                dll.Bridge_ClearOffsets.restype = None
            if hasattr(dll, "Bridge_SetApiUrl"):
                dll.Bridge_SetApiUrl.argtypes = [ctypes.c_char_p]
                dll.Bridge_SetApiUrl.restype = ctypes.c_int

            _native_bridge = dll
            return _native_bridge
        except Exception as e:
            print(f"[LicenseClient] Lỗi nạp DLL {dll_path}: {e}", flush=True)

    # KHÔNG lưu _native_bridge = False vĩnh viễn để các lần gọi sau có thể nhận diện khi người dùng copy file vào
    _native_bridge = None
    return None

def is_native_bridge_active(force_reload: bool = False) -> bool:
    """
    Kiểm tra cầu nối C++ Native Bridge có đang hoạt động và file có đang tồn tại trên đĩa hay không.
    Nếu file .dll bị xóa khỏi thư mục, trạng thái lập tức chuyển sang False ngay trong thời gian thực.
    """
    global _native_bridge
    # 1. Luôn kiểm tra xem file .dll có thực sự tồn tại trên đĩa hay không
    dll_path = find_bridge_dll_path()
    if not dll_path or not dll_path.is_file():
        _native_bridge = None
        return False

    # 2. Nếu file tồn tại trên đĩa, nạp DLL nếu chưa nạp (hoặc nếu yêu cầu force_reload)
    return _get_native_bridge(force_reload=force_reload) is not None

def is_native_authenticated() -> bool:
    """Kiểm tra xem C++ Bridge đã xác thực chữ ký HMAC mật mã nội bộ hay chưa."""
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_IsAuthenticated"):
        try:
            return bool(bridge.Bridge_IsAuthenticated())
        except Exception:
            return False
    return False

_ram_offsets_lock = threading.Lock()
_ram_offsets_cache: Dict[str, Any] = {}

def has_secure_game_offsets() -> bool:
    """Kiểm tra kho RAM trong C++ DLL đã có Game Offsets giải mã từ Server hay chưa."""
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_HasGameOffsets"):
        try:
            return bool(bridge.Bridge_HasGameOffsets() == 1)
        except Exception:
            return False
    return bool(_ram_offsets_cache)

def clear_secure_game_offsets() -> None:
    """Xóa sạch Game Offsets khỏi RAM (cả Python cache lẫn bộ nhớ C++ DLL bằng SecureZeroMemory)."""
    global _ram_offsets_cache
    with _ram_offsets_lock:
        _ram_offsets_cache.clear()
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_ClearOffsets"):
        try:
            bridge.Bridge_ClearOffsets()
        except Exception:
            pass

def get_bridge_version() -> int:
    """Lấy phiên bản của C++ Native Bridge (ví dụ: 100 cho v1.0.0)."""
    bridge = _get_native_bridge()
    return bridge.Bridge_GetVersion() if bridge else 0

_cached_hwid: Optional[str] = None

def get_machine_hwid() -> str:
    """
    Tạo HWID định danh duy nhất cho máy tính Windows.
    BẮT BUỘC gọi C++ Native Bridge qua Win32 Crypto API & MachineGuid (có cache RAM).
    """
    global _cached_hwid
    if _cached_hwid and not _cached_hwid.startswith("THIẾU_"):
        return _cached_hwid

    bridge = _get_native_bridge()
    if bridge:
        try:
            buf = ctypes.create_string_buffer(64)
            if bridge.Bridge_GetHwid(buf, 64) == 1:
                hwid = buf.value.decode("utf-8").strip()
                if hwid:
                    _cached_hwid = hwid
                    return hwid
        except Exception:
            pass

    return "THIẾU_MEG_LICENSE_BRIDGE_DLL"

# Alias tương thích ngược
get_hwid = get_machine_hwid

_license_lock = threading.Lock()
_cached_license_data: Dict[str, Any] = {}
_cached_license_mtime: float = 0.0

def load_license_data() -> Dict[str, Any]:
    """Đọc dữ liệu bản quyền đã lưu từ file config/license.json (Thread-safe có fallback cache & mtime check)."""
    global _cached_license_data, _cached_license_mtime
    with _license_lock:
        if not LICENSE_FILE.exists():
            _cached_license_data = {
                "license_key": "",
                "valid": False,
                "status": "unregistered",
                "modules": []
            }
            _cached_license_mtime = 0.0
            return _cached_license_data

        try:
            cur_mtime = LICENSE_FILE.stat().st_mtime
            if _cached_license_data and _cached_license_mtime == cur_mtime:
                return _cached_license_data
        except Exception:
            cur_mtime = 0.0

        for _ in range(3):
            try:
                content = LICENSE_FILE.read_text(encoding="utf-8")
                if content.strip():
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("license_key"):
                        _cached_license_data = data
                        _cached_license_mtime = cur_mtime
                        return data
            except Exception:
                time.sleep(0.02)
        return _cached_license_data

def save_license_data(data: Dict[str, Any]):
    """Lưu dữ liệu bản quyền vào config/license.json một cách an toàn (Atomic write)."""
    global _cached_license_data, _cached_license_mtime
    with _license_lock:
        _cached_license_data = data
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            temp_file = CONFIG_DIR / "license.json.tmp"
            temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if temp_file.exists():
                os.replace(str(temp_file), str(LICENSE_FILE))
            if LICENSE_FILE.exists():
                _cached_license_mtime = LICENSE_FILE.stat().st_mtime
        except Exception:
            try:
                LICENSE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                if LICENSE_FILE.exists():
                    _cached_license_mtime = LICENSE_FILE.stat().st_mtime
            except Exception:
                pass
                pass

LOCAL_SERVER_URL = "http://127.0.0.1:8000"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
}

def _http_activate(cleaned_key: str, srv: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Gửi yêu cầu kích hoạt qua HTTPS trực tiếp với Browser Headers để bypass WAF/Imunify360 Bot-Protection."""
    import urllib.request
    import urllib.error
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = srv.rstrip("/") + "/api/v1/license/activate"
    hwid = get_machine_hwid()
    payload = json.dumps({
        "license_key": cleaned_key,
        "hwid": hwid,
        "machine_name": os.environ.get("COMPUTERNAME", "PC"),
        "client_version": "v1.6.6",
        "product_code": "megamu-navigator"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if data.get("success"):
                lic_info = data.get("data", {})
                lic_info["server_url"] = srv
                sig = data.get("signature") or lic_info.get("signature")
                if sig:
                    verify_offline_signature(cleaned_key, sig)
                save_license_data(lic_info)
                return True, data.get("message", "Kích hoạt thành công!"), lic_info
            return False, data.get("message", "Kích hoạt thất bại."), {}
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8", errors="ignore"))
            msg = err_data.get("message")
            if msg:
                return False, msg, {}
        except Exception:
            pass
        return False, f"Máy chủ từ chối yêu cầu (HTTP {e.code}).", {}
    except Exception as e:
        return False, f"Lỗi kết nối máy chủ ({e})", {}

def _exec_activate(cleaned_key: str, srv: str) -> Tuple[bool, str, Dict[str, Any]]:
    is_frozen = is_packaged_app()
    bridge = _get_native_bridge()
    if not bridge:
        if is_frozen:
            return False, "Thiếu tệp bảo mật meg_license_bridge.dll!", {}
        return _http_activate(cleaned_key, srv)

    try:
        out_buf = ctypes.create_string_buffer(65536)
        srv_bytes = srv.encode("utf-8")
        key_bytes = cleaned_key.encode("utf-8")
        prod_bytes = b"megamu-navigator"
        ver_bytes = b"v3.0.0"
        ret = bridge.Bridge_ActivateLicense(srv_bytes, key_bytes, prod_bytes, ver_bytes, out_buf, 65536)
        res_str = out_buf.value.decode("utf-8", errors="ignore")

        if res_str:
            if not is_frozen and ("imunify" in res_str.lower() or "bot-protection" in res_str.lower() or "access denied" in res_str.lower()):
                return _http_activate(cleaned_key, srv)

            try:
                data = json.loads(res_str)
            except Exception:
                if is_frozen:
                    return False, "Phản hồi máy chủ không hợp lệ.", {}
                return _http_activate(cleaned_key, srv)

            if data.get("success"):
                lic_info = data.get("data", {})
                lic_info["server_url"] = srv
                for k_strip in ("offsets_blob", "offsets_sig", "offsets_nonce", "offsets_ts"):
                    lic_info.pop(k_strip, None)
                with _ram_offsets_lock:
                    _ram_offsets_cache.clear()
                save_license_data(lic_info)
                # Nạp sẵn RAM offsets ngay sau khi kích hoạt thành công
                get_secure_game_offsets(force_refresh=True)
                return True, data.get("message", "Kích hoạt thành công!"), lic_info

            msg = data.get("message", "")
            if msg and ("key" in msg.lower() or "thiết bị" in msg.lower() or "hết hạn" in msg.lower() or "khóa" in msg.lower() or "debugger" in msg.lower() or "chữ ký" in msg.lower()):
                return False, msg, {}

            if is_frozen:
                return False, msg or "Không thể kết nối máy chủ bản quyền.", {}
            return _http_activate(cleaned_key, srv)
        if is_frozen:
            return False, "Không nhận được phản hồi từ máy chủ bản quyền.", {}
        return _http_activate(cleaned_key, srv)
    except Exception as e:
        if is_frozen:
            return False, f"Lỗi cầu nối bảo mật: {e}", {}
        return _http_activate(cleaned_key, srv)

def activate_license(license_key: str, server_url: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Gửi yêu cầu kích hoạt bản quyền tới Laravel License Server.
    Ưu tiên kết nối Server cấu hình (hoặc megamuoffical.com).
    Nếu server chính thức chưa online hoặc đang deploy, tự động fallback sang
    Local Dev Server (127.0.0.1:8000) để đảm bảo không bị gián đoạn khi test.
    """
    cleaned_key = license_key.strip()
    if not cleaned_key:
        return False, "Vui lòng nhập mã key.", {}

    target_url = server_url or get_default_server_url()

    # 1. Thử server chỉ định (hoặc từ config)
    success, msg, data = _exec_activate(cleaned_key, target_url)
    if success:
        return True, msg, data

    # 2. Nếu server chính thất bại do lỗi mạng/timeout và đang có Localhost chạy
    if server_url != LOCAL_SERVER_URL and ("máy chủ" in msg.lower() or "mạng" in msg.lower() or not data):
        try:
            fb_ok, fb_msg, fb_data = _exec_activate(cleaned_key, LOCAL_SERVER_URL)
            if fb_ok:
                return True, fb_msg, fb_data
        except Exception:
            pass

    return False, msg, data

def verify_offline_signature(license_key: str, signature: str) -> bool:
    """Xác thực chữ ký số offline HMAC-SHA256 theo HWID thông qua C++ Bridge."""
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_VerifyOfflineSignature"):
        try:
            k_bytes = str(license_key).strip().encode("utf-8")
            s_bytes = str(signature).strip().encode("utf-8")
            return bool(bridge.Bridge_VerifyOfflineSignature(k_bytes, s_bytes) == 1)
        except Exception:
            pass
    return False

def _http_verify(key: str, srv: str, lic_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Xác thực định kỳ qua HTTPS Browser Headers nếu C++ Bridge bị WAF/Imunify360 chặn."""
    import urllib.request
    import urllib.error
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = srv.rstrip("/") + "/api/v1/license/verify"
    hwid = get_machine_hwid()
    payload = json.dumps({
        "license_key": str(key).strip(),
        "hwid": hwid,
        "client_version": "v1.6.6"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("valid"):
                lic_data.update(data)
                lic_data["valid"] = True
                lic_data["server_url"] = srv
                lic_data["last_verified_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                sig = data.get("signature")
                if sig:
                    verify_offline_signature(key, sig)
                save_license_data(lic_data)
                return True, "Bản quyền hợp lệ.", lic_data
            else:
                st = data.get("status", "revoked")
                lic_data["valid"] = False
                lic_data["status"] = st
                if st in ("not_found", "revoked", "banned") or not data.get("license_key"):
                    deactivate_license()
                else:
                    save_license_data(lic_data)
                return False, data.get("message", "Bản quyền không hợp lệ."), lic_data
    except urllib.error.HTTPError as e:
        try:
            raw_err = e.read().decode("utf-8", errors="ignore")
            low_err = raw_err.lower()
            # KHÔNG bao giờ đánh dấu revoked nếu bị WAF / Imunify360 / Cloudflare chặn tạm thời!
            if "imunify" in low_err or "bot-protection" in low_err or "cloudflare" in low_err or "access denied by" in low_err:
                return False, "Máy chủ tạm chặn bởi tường lửa WAF (Imunify360). Vui lòng thử lại sau hoặc whitelist IP/API.", lic_data
            err_data = json.loads(raw_err)
            st = str(err_data.get("status") or "").strip().lower()
            # Chỉ khóa/hủy khi Laravel trả về đúng mã trạng thái nghiệp vụ
            if st in ("not_found", "revoked", "banned", "expired", "suspended", "hwid_mismatch"):
                lic_data["valid"] = False
                lic_data["status"] = st
                clear_secure_game_offsets()
                if st in ("not_found", "revoked", "banned"):
                    deactivate_license()
                else:
                    save_license_data(lic_data)
                return False, err_data.get("message", "Bản quyền không hợp lệ."), lic_data
            return False, err_data.get("message", f"Máy chủ trả lỗi HTTP {e.code}."), lic_data
        except Exception:
            pass
        if e.code == 404:
            return False, "Không tìm thấy API xác thực (HTTP 404).", lic_data
    except Exception:
        pass
    return False, "Không nhận được phản hồi từ máy chủ.", lic_data

def _exec_verify(key: str, srv: str, lic_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    is_frozen = is_packaged_app()
    bridge = _get_native_bridge()
    if not bridge:
        if is_frozen:
            return False, "Thiếu tệp bảo mật meg_license_bridge.dll!", lic_data
        return _http_verify(key, srv, lic_data)

    try:
        out_buf = ctypes.create_string_buffer(65536)
        srv_bytes = srv.encode("utf-8")
        key_bytes = str(key).encode("utf-8")
        ver_bytes = b"v3.0.0"
        ret = bridge.Bridge_VerifyLicense(srv_bytes, key_bytes, ver_bytes, out_buf, 65536)
        res_str = out_buf.value.decode("utf-8", errors="ignore")

        if res_str:
            if not is_frozen and ("imunify" in res_str.lower() or "bot-protection" in res_str.lower() or "access denied" in res_str.lower()):
                return _http_verify(key, srv, lic_data)

            try:
                data = json.loads(res_str)
            except Exception:
                if is_frozen:
                    return False, "Phản hồi xác thực không hợp lệ.", lic_data
                return _http_verify(key, srv, lic_data)

            if data.get("valid"):
                for k_strip in ("offsets_blob", "offsets_sig", "offsets_nonce", "offsets_ts"):
                    data.pop(k_strip, None)
                lic_data.update(data)
                lic_data["valid"] = True
                lic_data["server_url"] = srv
                lic_data["last_verified_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with _ram_offsets_lock:
                    _ram_offsets_cache.clear()
                save_license_data(lic_data)
                get_secure_game_offsets(force_refresh=True)
                return True, "Bản quyền hợp lệ.", lic_data
            else:
                st = data.get("status", "")
                if st in ("revoked", "banned", "expired", "hwid_mismatch", "suspended", "not_found", "tampered", "debugger_detected"):
                    lic_data["valid"] = False
                    lic_data["status"] = st
                    clear_secure_game_offsets()
                    if st in ("not_found", "revoked", "banned"):
                        deactivate_license()
                    else:
                        save_license_data(lic_data)
                    return False, data.get("message", "Bản quyền không hợp lệ."), lic_data
                else:
                    if is_frozen:
                        return False, data.get("message", "Không thể xác thực trực tuyến."), lic_data
                    return _http_verify(key, srv, lic_data)
        if is_frozen:
            return False, "Không nhận được phản hồi từ máy chủ bản quyền.", lic_data
        return _http_verify(key, srv, lic_data)
    except Exception as e:
        if is_frozen:
            return False, f"Lỗi cầu nối bảo mật: {e}", lic_data
        return _http_verify(key, srv, lic_data)

def verify_license(server_url: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Xác thực định kỳ (verify / heartbeat) với Server.
    Ưu tiên thực hiện bằng WinHTTP trong C++ Native Bridge.
    Có cơ chế bảo vệ: Không bao giờ hủy bản quyền khi gặp lỗi mạng/timeout tạm thời!
    """
    lic_data = load_license_data()
    key = lic_data.get("license_key")
    if not key:
        return False, "Chưa nhập key bản quyền.", {}

    default_srv = server_url or get_default_server_url()
    saved_srv = lic_data.get("server_url")
    srv = saved_srv if saved_srv else default_srv

    try:
        ok, msg, res_data = _exec_verify(key, srv, lic_data)
        if ok or res_data.get("valid") is False or res_data.get("status") in ("not_found", "suspended", "revoked", "banned", "expired", "hwid_mismatch"):
            return ok, msg, res_data

        # Nếu srv thất bại do mất mạng / chưa deploy, thử server fallback
        alt_srv = LOCAL_SERVER_URL if srv != LOCAL_SERVER_URL else DEFAULT_SERVER_URL
        try:
            alt_ok, alt_msg, alt_data = _exec_verify(key, alt_srv, lic_data)
            if alt_ok:
                return True, alt_msg, alt_data
        except Exception:
            pass

        # Cả hai đều không phản hồi (mất mạng / timeout) -> xóa RAM offset (chỉ dùng offset khi kết nối internet)
        clear_secure_game_offsets()
        exp = lic_data.get("expires_at")
        return True, f"Chế độ ngoại tuyến (hạn dùng: {exp}).", lic_data
    except Exception as e:
        clear_secure_game_offsets()
        exp = lic_data.get("expires_at")
        if exp:
            return True, f"Chế độ ngoại tuyến ({exp})", lic_data
        return False, f"Lỗi xác thực C++ Bridge ({e})", lic_data

def deactivate_license() -> bool:
    """Xóa bỏ thông tin bản quyền trên máy và xóa sạch Game Offsets khỏi RAM."""
    global _cached_license_data, _last_valid_check_time, _last_valid_result
    clear_secure_game_offsets()
    with _license_lock:
        _cached_license_data = {
            "license_key": "",
            "valid": False,
            "status": "unregistered",
            "modules": []
        }
        _last_valid_check_time = 0.0
        _last_valid_result = False
        try:
            if LICENSE_FILE.exists():
                LICENSE_FILE.unlink()
        except Exception:
            pass
        return True

_last_valid_check_time: float = 0.0
_last_valid_result: bool = False

def is_license_valid() -> bool:
    """
    Kiểm tra xem bản quyền hiện tại có hợp lệ hay không.
    Hỗ trợ Chế độ Ngoại tuyến (Offline Grace Period) và cache 2s chống giật lag.
    """
    global _last_valid_check_time, _last_valid_result
    now_ts = time.time()
    if (now_ts - _last_valid_check_time) < 2.0:
        return _last_valid_result

    _last_valid_check_time = now_ts
    _last_valid_result = _do_check_license_valid()
    return _last_valid_result

def _do_check_license_valid() -> bool:
    if not is_native_bridge_active():
        return False

    data = load_license_data()
    if not data or not data.get("license_key") or data.get("valid") is False:
        return False

    # 1. Bắt buộc kiểm tra HWID của máy tính hiện tại
    cur_hwid = get_machine_hwid()
    if not cur_hwid or cur_hwid.startswith("THIẾU_"):
        return False

    saved_hwid = str(data.get("hwid", "")).strip().upper()
    if saved_hwid and saved_hwid != cur_hwid.strip().upper():
        # Khác mã phần cứng (HWID Mismatch) -> Khóa ngay lập tức!
        return False

    # 2. Kiểm tra ngày hết hạn
    if not data.get("is_lifetime"):
        exp = data.get("expires_at")
        if not exp:
            return False
        try:
            from datetime import datetime
            exp_clean = str(exp).strip()
            if " " in exp_clean:
                dt = datetime.strptime(exp_clean.split(".")[0], "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime.strptime(exp_clean, "%Y-%m-%d")
            if dt <= datetime.now():
                # Quá hạn sử dụng
                return False
        except Exception:
            return False

    # 3. Kiểm tra trạng thái bị thu hồi / cấm
    status = data.get("status", "active")
    if status in ("revoked", "banned", "suspended", "expired", "hwid_mismatch", "not_found", "unregistered"):
        return False

    # 4. BẮT BUỘC xác thực chữ ký số HMAC-SHA256 qua C++ Native Bridge
    sig = str(data.get("signature", "")).strip()
    key = str(data.get("license_key", "")).strip()
    if not sig or not key:
        return False

    if not verify_offline_signature(key, sig):
        # Chữ ký số không khớp với HWID máy này hoặc phát hiện Debugger -> KHÓA!
        return False

    return True

def get_license_display_text() -> str:
    """
    Trả về chuỗi hiển thị gọn đẹp cho Header (e.g. 'VIP Pro (Hạn: 2027-09-30)' hoặc '--').
    """
    if not is_native_bridge_active():
        return "🔒 Thiếu file .DLL"

    data = load_license_data()
    if not data or not data.get("license_key"):
        return "--"

    if data.get("valid") is False or data.get("status") in ("suspended", "expired"):
        status_vi = "Bị khóa" if data.get("status") == "suspended" else "Hết hạn"
        return f"🔒 {status_vi}"

    plan = data.get("plan_type", "Pro")
    is_lifetime = data.get("is_lifetime", False)
    exp = data.get("expires_at")

    if is_lifetime or not exp:
        return f"{plan} (Vĩnh viễn)"

    exp_date = str(exp).split(" ")[0] if exp else "--"
    return f"{plan} (Hạn: {exp_date})"

def get_secure_game_offsets(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Trích xuất Game Offsets được Server gửi về & giải mã trực tiếp trong RAM của Native C++ Bridge.
    Strict Online Zero-Offset-On-Disk: tuyệt đối KHÔNG đọc hay ghi file offset xuống đĩa trên bản phát hành!
    """
    global _ram_offsets_cache
    if not is_native_bridge_active() or not has_secure_game_offsets():
        with _ram_offsets_lock:
            _ram_offsets_cache.clear()
        return {}

    with _ram_offsets_lock:
        if _ram_offsets_cache and not force_refresh:
            return dict(_ram_offsets_cache)

    bridge = _get_native_bridge()
    if not bridge:
        return {}

    try:
        bridge.Bridge_GetGameOffsets.argtypes = [ctypes.c_char_p, ctypes.c_int]
        bridge.Bridge_GetGameOffsets.restype = ctypes.c_int
        buf = ctypes.create_string_buffer(65536)
        if bridge.Bridge_GetGameOffsets(buf, 65536) == 1:
            raw = buf.value.decode("utf-8", errors="ignore")
            if raw and raw.startswith("{"):
                data = json.loads(raw)
                if isinstance(data, dict) and (data.get("move_to") or data.get("get_player") or data.get("game_type_info")):
                    with _ram_offsets_lock:
                        _ram_offsets_cache = dict(data)
                    return dict(data)
    except Exception as e:
        print(f"[LicenseClient] Lỗi trích xuất Native RAM Offsets: {e}", flush=True)

    return {}

def get_licensed_modules() -> list[str]:
    """
    Lấy danh sách các module được cấp phép cho key hiện tại.
    Hỗ trợ tương thích ngược:
    Nếu key chưa có trường 'modules' trong license.json (key cũ) hoặc modules=None,
    mặc định cấp toàn quyền: ['train', 'moss', 'mirror'].
    """
    data = load_license_data()
    if not data or not data.get("license_key") or not is_license_valid():
        return []

    mods = data.get("modules")
    if mods is None:
        return ["train", "moss", "mirror"]
    if isinstance(mods, list):
        return [str(m).strip().lower() for m in mods]
    return []

def has_license_module(module_name: str) -> bool:
    """
    Kiểm tra xem module cụ thể ('train', 'moss', 'mirror') có được cấp phép hay không.
    Nếu bản quyền tổng thể không hợp lệ thì trả về False.
    """
    if not is_license_valid():
        return False
    mods = get_licensed_modules()
    return module_name.strip().lower() in mods

