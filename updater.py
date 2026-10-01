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

def check_for_updates(current_version: str = "v1.5.1") -> Dict[str, Any]:
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

def apply_exe_update_and_restart(new_file_path: Path, current_exe_path: Optional[Path] = None):
    """
    Tạo script batch chạy ngầm để ghi đè file .exe hiện tại và khởi động lại phiên bản mới.
    """
    if current_exe_path is None:
        if getattr(sys, "frozen", False):
            current_exe_path = Path(sys.executable).resolve()
        else:
            cand1 = Path(__file__).resolve().parent / "Release_MEGAMU" / "MEGAMU Auto Train Dashboard.exe"
            cand2 = Path(__file__).resolve().parent / "MEGAMU Auto Train Dashboard.exe"
            current_exe_path = cand1 if cand1.exists() else cand2

    # Neu file tai ve la file .zip, giai nen de tim file .exe ben trong
    actual_exe_source = new_file_path
    if str(new_file_path).lower().endswith(".zip"):
        try:
            import zipfile
            extract_dir = new_file_path.parent / "_unpacked_update"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(new_file_path), "r") as zf:
                zf.extractall(str(extract_dir))
            # Tim file .exe ben trong
            found_exe = None
            for p in extract_dir.rglob("*.exe"):
                found_exe = p
                break
            if found_exe:
                actual_exe_source = found_exe
        except Exception as ez:
            print(f"[Updater] Lỗi giải nén gói cập nhật zip: {ez}", flush=True)

    pid = os.getpid()
    bat_file = current_exe_path.parent / "apply_update.bat"

    bat_content = f"""@echo off
chcp 65001 >nul
echo Dang cap nhat MEGAMU Auto Train Dashboard...
timeout /t 1 /nobreak >nul

:: Cho tien trinh cu ket thuc
taskkill /f /pid {pid} >nul 2>&1
timeout /t 1 /nobreak >nul

:: Ghi de file .exe moi
copy /y "{actual_exe_source}" "{current_exe_path}" >nul

:: Neu thanh cong thi xoa file download tam
if exist "{current_exe_path}" (
    del /f /q "{new_file_path}" >nul 2>&1
    start "" "{current_exe_path}"
)

:: Xoa chinh script batch nay
del "%~f0" >nul 2>&1
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
