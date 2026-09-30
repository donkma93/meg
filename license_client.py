# ==============================================================================
# DONPV LICENSE CLIENT - XÁC THỰC BẢN QUYỀN CLIENT CHO MEGAMU AUTO TRAIN
# TÍCH HỢP NATIVE C++ BRIDGE (meg_license_bridge.dll) & PYTHON FALLBACK
# ==============================================================================
import os
import sys
import json
import hashlib
import platform
import socket
import ctypes
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
LICENSE_FILE = CONFIG_DIR / "license.json"
BRIDGE_DLL_FILE = BASE_DIR / "meg_license_bridge.dll"
# Fallback check for DLL if in _MEIPASS or _internal
if not BRIDGE_DLL_FILE.exists():
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass and (Path(_meipass) / "meg_license_bridge.dll").exists():
        BRIDGE_DLL_FILE = Path(_meipass) / "meg_license_bridge.dll"
    elif (BASE_DIR / "_internal" / "meg_license_bridge.dll").exists():
        BRIDGE_DLL_FILE = BASE_DIR / "_internal" / "meg_license_bridge.dll"

DEFAULT_SERVER_URL = "https://megamuoffical.com"

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

def _get_native_bridge():
    """Tải thư viện Native C++ Bridge DLL (meg_license_bridge.dll) nếu có."""
    global _native_bridge
    if _native_bridge is not None:
        return _native_bridge if _native_bridge is not False else None

    if BRIDGE_DLL_FILE.exists():
        try:
            dll = ctypes.CDLL(str(BRIDGE_DLL_FILE))
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

            # Lớp 2 & 3: Xác thực bộ nhớ C++ và giải mã game offsets
            if hasattr(dll, "Bridge_IsAuthenticated"):
                dll.Bridge_IsAuthenticated.restype = ctypes.c_int
            if hasattr(dll, "Bridge_GetGameOffsets"):
                dll.Bridge_GetGameOffsets.argtypes = [ctypes.c_char_p, ctypes.c_int]
                dll.Bridge_GetGameOffsets.restype = ctypes.c_int
            if hasattr(dll, "Bridge_SetApiUrl"):
                dll.Bridge_SetApiUrl.argtypes = [ctypes.c_char_p]
                dll.Bridge_SetApiUrl.restype = ctypes.c_int

            _native_bridge = dll
            return _native_bridge
        except Exception:
            _native_bridge = False
            return None
    _native_bridge = False
    return None

def is_native_bridge_active() -> bool:
    """Kiểm tra cầu nối C++ Native Bridge có đang hoạt động không."""
    return _get_native_bridge() is not None

def is_native_authenticated() -> bool:
    """Kiểm tra xem C++ Bridge đã xác thực chữ ký HMAC mật mã nội bộ hay chưa."""
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_IsAuthenticated"):
        try:
            return bool(bridge.Bridge_IsAuthenticated())
        except Exception:
            return False
    return False

def get_secure_game_offsets() -> Dict[str, Any]:
    """
    Lớp 3: Giải mã game offsets trực tiếp từ C++ DLL.
    Chỉ trả về offsets khi bản quyền đã được xác thực HMAC hợp lệ và không có debugger.
    """
    bridge = _get_native_bridge()
    if bridge and hasattr(bridge, "Bridge_GetGameOffsets"):
        try:
            buf = ctypes.create_string_buffer(4096)
            if bridge.Bridge_GetGameOffsets(buf, 4096) == 1:
                raw_str = buf.value.decode("utf-8").strip()
                if raw_str and raw_str != "{}":
                    return json.loads(raw_str)
        except Exception:
            pass
    return {}

def get_bridge_version() -> int:
    """Lấy phiên bản của C++ Native Bridge (ví dụ: 100 cho v1.0.0)."""
    bridge = _get_native_bridge()
    return bridge.Bridge_GetVersion() if bridge else 0

def get_machine_hwid() -> str:
    """
    Tạo HWID định danh duy nhất cho máy tính Windows.
    Ưu tiên gọi C++ Native Bridge qua Win32 Crypto API & MachineGuid.
    """
    bridge = _get_native_bridge()
    if bridge:
        try:
            buf = ctypes.create_string_buffer(64)
            if bridge.Bridge_GetHwid(buf, 64) == 1:
                hwid = buf.value.decode("utf-8").strip()
                if hwid:
                    return hwid
        except Exception:
            pass

    # Fallback Pure Python (nếu DLL bị xóa hoặc môi trường không hỗ trợ)
    raw_id = ""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        raw_id = str(guid).strip()
    except Exception:
        pass

    if not raw_id:
        raw_id = f"{socket.gethostname()}-{os.getenv('USERNAME', 'USER')}-{platform.machine()}"

    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16].upper()

def load_license_data() -> Dict[str, Any]:
    """Đọc dữ liệu bản quyền đã lưu từ file config/license.json."""
    if not LICENSE_FILE.exists():
        return {}
    try:
        data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_license_data(data: Dict[str, Any]):
    """Lưu dữ liệu bản quyền vào config/license.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        LICENSE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def activate_license(license_key: str, server_url: str = DEFAULT_SERVER_URL) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Gửi yêu cầu kích hoạt bản quyền tới Laravel License Server.
    Ưu tiên thực hiện bằng WinHTTP trong C++ Native Bridge.
    """
    cleaned_key = license_key.strip()
    if not cleaned_key:
        return False, "Vui lòng nhập mã key.", {}

    bridge = _get_native_bridge()
    if bridge:
        try:
            out_buf = ctypes.create_string_buffer(8192)
            srv_bytes = server_url.encode("utf-8")
            key_bytes = cleaned_key.encode("utf-8")
            prod_bytes = b"megamu-navigator"
            ver_bytes = b"v1.5.1"
            ret = bridge.Bridge_ActivateLicense(srv_bytes, key_bytes, prod_bytes, ver_bytes, out_buf, 8192)
            res_str = out_buf.value.decode("utf-8")
            if res_str:
                data = json.loads(res_str)
                if data.get("success"):
                    lic_info = data.get("data", {})
                    lic_info["server_url"] = server_url
                    save_license_data(lic_info)
                    return True, data.get("message", "Kích hoạt thành công!"), lic_info
                return False, data.get("message", "Kích hoạt thất bại."), {}
        except Exception:
            pass

    # Fallback Pure Python urllib
    hwid = get_machine_hwid()
    machine_name = socket.gethostname()
    payload = {
        "license_key": cleaned_key,
        "hwid": hwid,
        "machine_name": machine_name,
        "client_version": "v1.5.1",
        "product_code": "megamu-navigator"
    }

    url = f"{server_url.rstrip('/')}/api/v1/license/activate"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )

    try:
        ssl_ctx = _get_ssl_context()
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as response:
            res_body = response.read().decode("utf-8")
            data = json.loads(res_body)
            if data.get("success"):
                lic_info = data.get("data", {})
                lic_info["server_url"] = server_url
                save_license_data(lic_info)
                return True, data.get("message", "Kích hoạt thành công!"), lic_info
            return False, data.get("message", "Kích hoạt thất bại."), {}
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_data = json.loads(err_body)
            return False, err_data.get("message", f"Lỗi HTTP {e.code}"), {}
        except Exception:
            return False, f"Lỗi máy chủ HTTP {e.code}", {}
    except Exception as e:
        return False, f"Không thể kết nối máy chủ License ({e})", {}

def verify_license(server_url: str = DEFAULT_SERVER_URL) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Xác thực định kỳ (verify / heartbeat) với Server.
    Ưu tiên thực hiện bằng WinHTTP trong C++ Native Bridge.
    """
    lic_data = load_license_data()
    key = lic_data.get("license_key")
    if not key:
        return False, "Chưa nhập key bản quyền.", {}

    srv = lic_data.get("server_url", server_url) or server_url
    if "127.0.0.1" in srv or "localhost" in srv:
        srv = DEFAULT_SERVER_URL

    bridge = _get_native_bridge()
    if bridge:
        try:
            out_buf = ctypes.create_string_buffer(8192)
            srv_bytes = srv.encode("utf-8")
            key_bytes = str(key).encode("utf-8")
            ver_bytes = b"v1.5.1"
            ret = bridge.Bridge_VerifyLicense(srv_bytes, key_bytes, ver_bytes, out_buf, 8192)
            res_str = out_buf.value.decode("utf-8")
            if res_str:
                data = json.loads(res_str)
                if data.get("valid"):
                    lic_data.update(data)
                    lic_data["server_url"] = srv
                    save_license_data(lic_data)
                    return True, "Bản quyền hợp lệ.", lic_data
                else:
                    lic_data["valid"] = False
                    lic_data["status"] = data.get("status", "invalid")
                    save_license_data(lic_data)
                return False, data.get("message", "Bản quyền không hợp lệ."), lic_data
        except Exception:
            pass

    # Fallback Pure Python
    hwid = get_machine_hwid()
    url = f"{srv.rstrip('/')}/api/v1/license/verify"
    payload = {
        "license_key": key,
        "hwid": hwid,
        "client_version": "v1.5.1"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )

    try:
        ssl_ctx = _get_ssl_context()
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=6) as response:
            res_body = response.read().decode("utf-8")
            data = json.loads(res_body)
            if data.get("valid"):
                lic_data.update(data)
                lic_data["server_url"] = srv
                save_license_data(lic_data)
                return True, "Bản quyền hợp lệ.", lic_data
            else:
                lic_data["valid"] = False
                lic_data["status"] = data.get("status", "invalid")
                save_license_data(lic_data)
            return False, data.get("message", "Bản quyền không hợp lệ."), lic_data
    except Exception as e:
        exp = lic_data.get("expires_at")
        if exp:
            return True, f"Offline mode ({exp})", lic_data
        return False, f"Lỗi kết nối ({e})", lic_data

def deactivate_license() -> bool:
    """Xóa bỏ thông tin bản quyền trên máy và chuyển sang trạng thái chưa kích hoạt."""
    try:
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
        return True
    except Exception:
        save_license_data({"license_key": "", "valid": False, "status": "unregistered"})
        return True

def is_license_valid() -> bool:
    """
    Kiểm tra nhanh xem bản quyền hiện tại có hợp lệ hay không.
    Điều kiện hợp lệ:
    1. Có license_key trong file config/license.json
    2. valid không phải False
    3. status là 'active'
    4. Chưa quá hạn sử dụng (expires_at > hiện tại) hoặc is_lifetime == True
    """
    data = load_license_data()
    if not data or not data.get("license_key"):
        return False
    if data.get("valid") is False:
        return False
    status = data.get("status", "active")
    if status != "active":
        return False
    if data.get("is_lifetime"):
        return True
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
        return dt > datetime.now()
    except Exception:
        return True

def get_license_display_text() -> str:
    """
    Trả về chuỗi hiển thị gọn đẹp cho Header (e.g. 'VIP Pro (Hạn: 2027-09-30)' hoặc '--').
    """
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

def get_secure_game_offsets() -> Dict[str, Any]:
    """
    Trích xuất Game Offsets được giải mã an toàn trong RAM từ Native C++ Bridge.
    Hoàn toàn không cần để file megamu_offsets.json lộ ngoài đĩa.
    """
    bridge = _get_native_bridge()
    if not bridge:
        return {}

    try:
        # Nếu chưa authenticated, thử xác thực offline qua signature đã lưu trong license.json
        if not bridge.Bridge_IsAuthenticated():
            lic = load_license_data()
            k = lic.get("license_key", "")
            sig = lic.get("signature", "")
            if k and sig:
                bridge.Bridge_VerifyOfflineSignature.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                bridge.Bridge_VerifyOfflineSignature.restype = ctypes.c_int
                bridge.Bridge_VerifyOfflineSignature(k.encode("utf-8"), sig.encode("utf-8"))

        bridge.Bridge_GetGameOffsets.argtypes = [ctypes.c_char_p, ctypes.c_int]
        bridge.Bridge_GetGameOffsets.restype = ctypes.c_int
        buf = ctypes.create_string_buffer(4096)
        if bridge.Bridge_GetGameOffsets(buf, 4096) == 1:
            raw = buf.value.decode("utf-8", errors="ignore")
            if raw and raw.startswith("{"):
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("move_to"):
                    return data
    except Exception as e:
        print(f"[LicenseClient] Lỗi trích xuất Native Offsets: {e}", flush=True)

    return {}

