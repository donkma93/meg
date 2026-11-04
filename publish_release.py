#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - Auto Publish Release to GitHub
Tu dong dong goi ban phat hanh, tao Git Tag va day len GitHub Releases.
"""
import os
import sys
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time
import subprocess

REPO = "donkma93/meg"
BASE_DIR = Path(__file__).resolve().parent

def _urlopen_with_retry(req, retries=5, delay=2):
    for attempt in range(1, retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[!] Network retry {attempt}/{retries} ({e}), waiting {delay}s...")
            time.sleep(delay)

def get_current_app_version() -> str:
    gui_file = BASE_DIR / "meg_gui.py"
    if gui_file.exists():
        content = gui_file.read_text(encoding="utf-8")
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            v = m.group(1).strip()
            return v if v.startswith("v") else f"v{v}"
    return "v1.5.7"

def get_github_token() -> str:
    p = subprocess.Popen(
        ["git", "credential", "fill"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, _ = p.communicate("protocol=https\nhost=github.com\n\n")
    creds = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    token = creds.get("password")
    if not token:
        raise RuntimeError("Khong tim thay GitHub Personal Access Token trong Windows Credential Manager.")
    return token

def create_or_get_release(token: str, tag_name: str, release_title: str, release_body: str) -> dict:
    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "ReleasePublisher/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        url = f"https://api.github.com/repos/{REPO}/releases/tags/{tag_name}"
        req = urllib.request.Request(url, headers=headers)
        with _urlopen_with_retry(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Da ton tai Release cho tag {tag_name} (ID: {data['id']})")
            return data
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    print(f"[+] Dang tao Release moi cho tag {tag_name} tren GitHub...")
    url = f"https://api.github.com/repos/{REPO}/releases"
    payload = {
        "tag_name": tag_name,
        "name": release_title,
        "body": release_body,
        "draft": False,
        "prerelease": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST"
    )
    with _urlopen_with_retry(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[OK] Tao Release thanh cong! URL: {data.get('html_url')}")
        return data

def upload_asset(token: str, upload_url_tmpl: str, file_path: Path, asset_display_name: str = None, content_type: str = "application/octet-stream"):
    upload_url = upload_url_tmpl.split("{")[0]
    file_name = asset_display_name or file_path.name
    url = f"{upload_url}?name={urllib.parse.quote(file_name)}"
    
    file_size = file_path.stat().st_size
    print(f"[+] Dang tai len asset: {file_name} ({file_size / (1024*1024):.2f} MB)...")
    
    with open(str(file_path), "rb") as f:
        file_bytes = f.read()

    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "ReleasePublisher/1.0",
        "Content-Type": content_type,
        "Content-Length": str(len(file_bytes))
    }
    
    req = urllib.request.Request(url, data=file_bytes, headers=headers, method="POST")
    try:
        with _urlopen_with_retry(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Da tai len thanh cong: {data.get('browser_download_url')}")
            return data
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[!] Loi upload ({e.code}): {err_msg}")
        raise

def create_release_zip(release_dir: Path, zip_dest: Path):
    import zipfile
    print(f"[+] Dang tao file goi nen zip: {zip_dest.name}...")
    if zip_dest.exists():
        try:
            zip_dest.unlink()
        except Exception:
            pass

    with zipfile.ZipFile(str(zip_dest), "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(str(release_dir)):
            for f in files:
                f_path = Path(root) / f
                name_lower = f.lower()
                # Bao mat: khong bao gio dong goi license ca nhan, tai khoan, offsets
                if name_lower.endswith(".old") or name_lower in ("license.json", "megamu_offsets.json", "megamu_accounts.json") or name_lower.endswith(".log"):
                    continue
                rel_path = f_path.relative_to(release_dir)
                zf.write(str(f_path), str(rel_path))
    print(f"[OK] Da tao xong file zip ({zip_dest.stat().st_size / (1024*1024):.2f} MB).")

if __name__ == "__main__":
    version = get_current_app_version()
    print(f"[*] Phien ban hien tai: {version}")
    
    token = get_github_token()
    print("[*] Da ket noi GitHub Access Token thanh cong.")

    title = f"MEGAMU Auto Train Dashboard {version} - MEGATEAM"
    body = f"""## Phiên bản chính thức MEGAMU Auto Train Dashboard {version} (MEGATEAM)

### Điểm nổi bật & Tính năng mới trong bản {version}:
- **Hệ Thống Đánh Chặn & Ghi Vết Lỗi Luồng Toàn Diện (Tri-Layer Crash Tracer):**
  - Tích hợp 3 tầng bảo vệ lỗi ngoại lệ (`threading.Thread.run wrapping`, `threading.excepthook`, `sys.excepthook`) trong `meg_crash_tracer.py`.
  - Tự động ghi lại toàn bộ call stack traceback và vị trí leaf frame vào `auto_crash_trace.log`, `app_exceptions.log` và log UI với định tuyến slot chính xác.
  - Ngăn ngừa tình trạng luồng ngầm bị crash im lặng (silent crash), đảm bảo bot tự phục hồi an toàn.
- **Tối Ưu & Triệt Tiêu Lỗi Đa Luồng Sự Kiện Double Goer (Mirror Event):**
  - Loại bỏ hoàn toàn bùng nổ luồng (thread explosion) trong bộ lập lịch Double Goer scheduler.
  - Áp dụng cơ chế single-flight kiểm tra vé sự kiện và ngăn chặn triệt để rò rỉ handle tiến trình.
- **Nâng Cấp Direct Engine & Xử Lý Native MLogin:**
  - Chuẩn hóa các offset native và chữ ký hàm cho MLogin và quản lý scene trong `meg_direct_engine.py`.
  - Nâng cao tốc độ phản hồi và độ ổn định khi gán và nhận diện nhân vật game.
- **Kế Thừa Đầy Đủ Các Tính Năng Cao Cấp của v1.5.6:**
  - Auto Devil Square cấu hình chuẩn theo **Số Lần Reset** và loại vé (Master / Thường).
  - Thanh công cụ Toolbar tinh gọn **Icon-Only** (36x30 px) kèm nút Master Toggle Chạy/Dừng Tất Cả thông minh.
"""

    release = create_or_get_release(token, version, title, body)
    upload_url = release["upload_url"]
    existing_assets = [a["name"] for a in release.get("assets", [])]

    # Tim file exe tu Release_MEGAMU hoac Release_MEGAMU_Secure
    cand1 = BASE_DIR / "Release_MEGAMU" / "MEGAMU Auto Train Dashboard.exe"
    cand2 = BASE_DIR / "Release_MEGAMU_Secure" / "MEGAMU Auto Train Dashboard.exe"
    
    release_folder = None
    exe_file = None
    if cand1.exists() and cand2.exists():
        if cand1.stat().st_mtime >= cand2.stat().st_mtime:
            exe_file, release_folder = cand1, BASE_DIR / "Release_MEGAMU"
        else:
            exe_file, release_folder = cand2, BASE_DIR / "Release_MEGAMU_Secure"
    elif cand1.exists():
        exe_file, release_folder = cand1, BASE_DIR / "Release_MEGAMU"
    elif cand2.exists():
        exe_file, release_folder = cand2, BASE_DIR / "Release_MEGAMU_Secure"

    zip_file = BASE_DIR / f"MEGAMU_Auto_Train_Dashboard_{version}.zip"
    if release_folder and not zip_file.exists():
        create_release_zip(release_folder, zip_file)

    if exe_file and exe_file.exists():
        if "MEGAMU.Auto.Train.Dashboard.exe" not in existing_assets:
            try:
                upload_asset(token, upload_url, exe_file, "MEGAMU.Auto.Train.Dashboard.exe", "application/vnd.microsoft.portable-executable")
            except Exception as e:
                print(f"[*] Thong bao asset exe: {e}")
        else:
            print("[*] MEGAMU.Auto.Train.Dashboard.exe da co san trong release.")
    else:
        print(f"[!] Khong tim thay file exe trong Release_MEGAMU hay Release_MEGAMU_Secure")

    if zip_file.exists():
        if zip_file.name not in existing_assets:
            try:
                upload_asset(token, upload_url, zip_file, None, "application/zip")
            except Exception as e:
                print(f"[*] Thong bao asset zip: {e}")
        else:
            print(f"[*] {zip_file.name} da co san trong release.")
    else:
        print(f"[!] Khong tim thay {zip_file}")

    print("\n[V] HOAN TAT PHAT HANH RELEASE LEN GITHUB!")
