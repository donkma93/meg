# ==============================================================================
# MEGAMU AUTO TRAIN - AUTO UPDATER MODULE
# TỰ ĐỘNG KIỂM TRA & CẬP NHẬT TỪ GITHUB RELEASES / TAGS (MANDATORY UPDATE)
# ==============================================================================
import os
import sys
import json
import re
import ssl
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable

GITHUB_REPO = "donkma93/meg"
API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
API_TAGS = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"

def _get_ssl_context():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

def parse_version(v_str: str) -> Tuple[int, ...]:
    """
    Phân tích chuỗi phiên bản dạng 'v1.5.1' hoặc '1.5.2' thành tuple số (1, 5, 1).
    """
    if not v_str:
        return (0, 0, 0)
    cleaned = v_str.strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned)
    if not nums:
        return (0, 0, 0)
    return tuple(int(x) for x in nums)

def is_newer_version(remote_ver: str, current_ver: str) -> bool:
    """So sánh phiên bản mới hơn."""
    v_remote = parse_version(remote_ver)
    v_curr = parse_version(current_ver)
    return v_remote > v_curr

def _get_auth_headers() -> Dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            p = subprocess.Popen(
                ["git", "credential", "fill"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, _ = p.communicate("protocol=https\nhost=github.com\n\n", timeout=1)
            creds = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
            token = creds.get("password")
        except Exception:
            pass
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def check_for_updates(current_version: str = "v1.6.0") -> Dict[str, Any]:
    """
    Kiểm tra phiên bản mới nhất từ GitHub Releases hoặc Tags.
    Trả về dict chi tiết gồm: has_update, latest_version, release_notes, download_url...
    """
    res_data = {
        "has_update": False,
        "latest_version": current_version,
        "current_version": current_version,
        "release_name": "",
        "release_notes": "",
        "release_url": GITHUB_RELEASES_PAGE,
        "download_url": None,
        "asset_name": None,
        "asset_size": 0,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    ctx = _get_ssl_context()
    headers = {
        "User-Agent": f"MEGAMU-AutoTrain-Client/{current_version}",
        "Accept": "application/vnd.github.v3+json"
    }
    headers.update(_get_auth_headers())

    # 1. Thử lấy từ GitHub Releases (bản phát hành)
    try:
        # Thử API /releases (lấy danh sách tất cả các release)
        req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases", headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=7) as resp:
            releases = json.loads(resp.read().decode("utf-8"))
            if isinstance(releases, list) and releases:
                highest_rel = None
                for rel in releases:
                    if rel.get("draft", False):
                        continue
                    tag = rel.get("tag_name", "").strip()
                    if tag and is_newer_version(tag, current_version):
                        if highest_rel is None or is_newer_version(tag, highest_rel.get("tag_name", "")):
                            highest_rel = rel

                if highest_rel:
                    tag = highest_rel.get("tag_name", "").strip()
                    res_data["has_update"] = True
                    res_data["latest_version"] = tag
                    res_data["release_name"] = highest_rel.get("name") or tag
                    res_data["release_notes"] = highest_rel.get("body", "Có bản cập nhật mới từ hệ thống.")
                    res_data["release_url"] = highest_rel.get("html_url", GITHUB_RELEASES_PAGE)

                    # Ưu tiên tìm asset file .exe trước để cập nhật trực tiếp
                    assets = highest_rel.get("assets", [])
                    exe_ast = next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
                    if not exe_ast:
                        exe_ast = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
                    if exe_ast:
                        res_data["download_url"] = exe_ast.get("browser_download_url")
                        res_data["asset_name"] = exe_ast.get("name")
                        res_data["asset_size"] = exe_ast.get("size", 0)
                    return res_data
    except Exception as e:
        # Nếu /releases lỗi, thử tiếp API /releases/latest
        try:
            req = urllib.request.Request(API_LATEST_RELEASE, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tag = data.get("tag_name", "").strip()
                if tag and is_newer_version(tag, current_version):
                    res_data["has_update"] = True
                    res_data["latest_version"] = tag
                    res_data["release_name"] = data.get("name") or tag
                    res_data["release_notes"] = data.get("body", "Có bản cập nhật mới từ hệ thống.")
                    res_data["release_url"] = data.get("html_url", GITHUB_RELEASES_PAGE)
                    assets = data.get("assets", [])
                    exe_ast = next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
                    if not exe_ast:
                        exe_ast = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
                    if exe_ast:
                        res_data["download_url"] = exe_ast.get("browser_download_url")
                        res_data["asset_name"] = exe_ast.get("name")
                        res_data["asset_size"] = exe_ast.get("size", 0)
                    return res_data
        except Exception:
            pass

    # 2. Quét từ danh sách Git Tags nếu Releases chưa có
    try:
        req = urllib.request.Request(API_TAGS, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=7) as resp:
            tags_list = json.loads(resp.read().decode("utf-8"))
            if isinstance(tags_list, list) and tags_list:
                highest_tag = None
                for t in tags_list:
                    tag_name = t.get("name", "").strip()
                    if tag_name and is_newer_version(tag_name, current_version):
                        if highest_tag is None or is_newer_version(tag_name, highest_tag):
                            highest_tag = tag_name

                if highest_tag:
                    res_data["has_update"] = True
                    res_data["latest_version"] = highest_tag
                    res_data["release_name"] = f"Phiên bản {highest_tag}"
                    res_data["release_notes"] = f"Bản phát hành mới {highest_tag}."
                    res_data["release_url"] = f"https://github.com/{GITHUB_REPO}/releases/tag/{highest_tag}"
                    return res_data
    except Exception as e:
        print(f"[Updater] Lỗi kiểm tra máy chủ cập nhật: {e}", flush=True)

    return res_data

def download_file_with_progress(
    url: str,
    dest_path: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None
) -> bool:
    """
    Tải file từ URL về dest_path và gọi progress_callback(downloaded_bytes, total_bytes).
    """
    ctx = _get_ssl_context()
    headers = {
        "User-Agent": "MEGAMU-AutoTrain-Client",
        "Accept": "*/*"
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 64 * 1024  # 64 KB chunk

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(dest_path), "wb") as f:
                while True:
                    if cancel_flag and cancel_flag():
                        return False
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
            return True
    except Exception as e:
        print(f"[Updater] Lỗi tải file: {e}", flush=True)
        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass
        return False

def get_current_executable_path() -> Path:
    """Xác định đường dẫn file .exe gốc đang chạy một cách chính xác tuyệt đối."""
    # 1. Nuitka onefile: Biến môi trường NUITKA_ORIGINAL_ARGV0 lưu đúng đường dẫn file .exe gốc
    orig_argv0 = os.environ.get("NUITKA_ORIGINAL_ARGV0")
    if orig_argv0 and os.path.isfile(orig_argv0):
        return Path(orig_argv0).resolve()

    # 2. Nuitka onefile: Thư mục chứa binary gốc
    onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
    if onefile_dir and os.path.isdir(onefile_dir):
        for name in ("MEGAMU Auto Train Dashboard.exe", "MEGAMU.Auto.Train.Dashboard.exe"):
            cand = Path(onefile_dir) / name
            if cand.is_file():
                return cand.resolve()

    # 3. Qua sys.argv[0] nếu không nằm trong thư mục Temp
    if sys.argv and sys.argv[0]:
        cand = Path(sys.argv[0]).resolve()
        if cand.is_file() and "temp" not in str(cand).lower():
            return cand

    # 4. Qua sys.executable nếu là file .exe và không nằm trong Temp
    if sys.executable:
        cand = Path(sys.executable).resolve()
        if cand.is_file() and "temp" not in str(cand).lower() and cand.name.lower().endswith(".exe"):
            return cand

    # 5. Fallback qua Release_MEGAMU_Secure hoặc thư mục hiện tại
    base = Path(__file__).resolve().parent
    cand_sec = base / "Release_MEGAMU_Secure" / "MEGAMU Auto Train Dashboard.exe"
    if cand_sec.is_file():
        return cand_sec.resolve()

    cand_local = base / "MEGAMU Auto Train Dashboard.exe"
    if cand_local.is_file():
        return cand_local.resolve()

    return Path(sys.executable).resolve()

def apply_exe_update_and_restart(new_file_path: Path, current_exe_path: Optional[Path] = None):
    """
    Tạo script batch chạy ngầm để ghi đè file .exe hiện tại và khởi động lại phiên bản mới.
    Đảm bảo diệt sạch tiến trình cũ (cả parent lẫn child), retry vòng lặp ghi đè và khởi động lại chuẩn xác.
    """
    if current_exe_path is None:
        current_exe_path = get_current_executable_path()

    actual_exe_source = new_file_path
    if str(new_file_path).lower().endswith(".zip"):
        try:
            import zipfile
            extract_dir = new_file_path.parent / "_unpacked_update"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(new_file_path), "r") as zf:
                zf.extractall(str(extract_dir))
            for p in extract_dir.rglob("*.exe"):
                actual_exe_source = p
                break
        except Exception as ez:
            print(f"[Updater] Lỗi giải nén gói cập nhật zip: {ez}", flush=True)

    child_pid = os.getpid()
    parent_pid = os.environ.get("NUITKA_ONEFILE_PARENT", "")
    target_name = current_exe_path.name

    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    bat_file = temp_dir / "meg_apply_update.bat"

    kill_parent_cmd = f'taskkill /f /pid {parent_pid} >nul 2>&1' if parent_pid else ':: no parent pid'

    bat_content = f"""@echo off
chcp 65001 >nul
title Dang cap nhat MEGAMU Auto Train Dashboard...
echo ==============================================================================
echo   HE THONG TU DONG NANG CAP PHIEN BAN - MEGAMU AUTO TRAIN DASHBOARD
echo ==============================================================================
echo.
echo Dang dong cac tien trinh cu dang chay...

:: 1. Dong cac tien trinh cu (Child va Parent bootstrap)
taskkill /f /pid {child_pid} >nul 2>&1
{kill_parent_cmd}
taskkill /f /im "{target_name}" >nul 2>&1

:: 2. Vong lap cho file het khoa va tien hanh ghi de (toi da 20 giay)
set RETRIES=0
:WAIT_RETRY
timeout /t 1 /nobreak >nul
echo Dang ghi de phien ban moi: "{current_exe_path}"...
copy /y "{actual_exe_source}" "{current_exe_path}" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto UPDATE_SUCCESS

set /a RETRIES+=1
if %RETRIES% GEQ 20 goto UPDATE_FAILED
echo File dang duoc he thong dong, thu lai (%RETRIES%/20)...
goto WAIT_RETRY

:UPDATE_SUCCESS
echo.
echo [THANH CONG] Da cap nhat thanh cong phien ban moi!
echo Dang khoi dong lai chuong trinh...
timeout /t 1 /nobreak >nul

:: Xoa file download tam
del /f /q "{new_file_path}" >nul 2>&1

:: Khoi dong lai phien ban moi
start "" "{current_exe_path}"

:: Xoa file batch tam nay
(goto) 2>nul & del "%~f0"
exit

:UPDATE_FAILED
echo.
echo [THAT BAI] Khong the ghi de file "{current_exe_path}".
echo Co the file dang bi khoa boi tien trinh khac hoac can quyen Administrator.
echo File cap nhat da duoc luu tai: "{actual_exe_source}"
pause
(goto) 2>nul & del "%~f0"
exit
"""
    try:
        bat_file.write_text(bat_content, encoding="utf-8")
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_file)],
            creationflags=CREATE_NO_WINDOW,
            close_fds=True
        )
        sys.exit(0)
    except Exception as e:
        print(f"[Updater] Lỗi áp dụng bản cập nhật: {e}", flush=True)
