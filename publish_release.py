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
import subprocess

REPO = "donkma93/meg"
BASE_DIR = Path(__file__).resolve().parent

def get_current_app_version() -> str:
    gui_file = BASE_DIR / "meg_gui.py"
    if gui_file.exists():
        content = gui_file.read_text(encoding="utf-8")
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            v = m.group(1).strip()
            return v if v.startswith("v") else f"v{v}"
    return "v1.5.1"

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
        with urllib.request.urlopen(req) as resp:
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
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[OK] Tao Release thanh cong! URL: {data.get('html_url')}")
        return data

def upload_asset(token: str, upload_url_tmpl: str, file_path: Path, content_type: str = "application/octet-stream"):
    upload_url = upload_url_tmpl.split("{")[0]
    file_name = file_path.name
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
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Da tai len thanh cong: {data.get('browser_download_url')}")
            return data
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[!] Loi upload ({e.code}): {err_msg}")
        raise

if __name__ == "__main__":
    version = get_current_app_version()
    print(f"[*] Phien ban hien tai: {version}")
    
    token = get_github_token()
    print("[*] Da ket noi GitHub Access Token thanh cong.")

    title = f"MEGAMU Auto Train Dashboard {version} - MEGATEAM"
    body = f"""## Phiên bản chính thức MEGAMU Auto Train Dashboard {version} (MEGATEAM)

### Điểm nổi bật & Tính năng:
- **Đóng gói All-in-One (.EXE Độc lập):** Tích hợp sẵn Native C++ Security Bridge (`meg_license_bridge.dll`), hình ảnh icon/logo và các cấu hình mặc định trực tiếp bên trong 1 file `.exe` duy nhất.
- **Tự động Cập nhật Trực tiếp (Auto-Updater):** Tự động phát hiện phiên bản mới từ GitHub Release/Tag và tự động cập nhật ghi đè file `.exe` an toàn.
- **Hệ thống Bản quyền MEGATEAM:** Kết nối và xác thực bản quyền trực tiếp với License Server (`https://megamuoffical.com`).
- **Chuẩn hóa Hotline / Zalo:** Hotline / Zalo chính thức duy nhất: **036.203.1354**.

---
### Tải về:
- **`MEGAMU Auto Train Dashboard.exe`**: File chạy trực tiếp không cần cài đặt (Standalone All-in-One).
- **`MEGAMU_Auto_Train_Dashboard_{version}.zip`**: Trọn bộ gói cài đặt giải nén kèm thư mục cấu hình và DLL.
"""

    release = create_or_get_release(token, version, title, body)
    upload_url = release["upload_url"]
    existing_assets = [a["name"] for a in release.get("assets", [])]

    exe_file = BASE_DIR / "Release_MEGAMU" / "MEGAMU Auto Train Dashboard.exe"
    zip_file = BASE_DIR / f"MEGAMU_Auto_Train_Dashboard_{version}.zip"

    if exe_file.exists():
        if exe_file.name not in existing_assets:
            upload_asset(token, upload_url, exe_file, "application/vnd.microsoft.portable-executable")
        else:
            print(f"[*] {exe_file.name} da co san trong release.")
    else:
        print(f"[!] Khong tim thay {exe_file}")

    if zip_file.exists():
        if zip_file.name not in existing_assets:
            upload_asset(token, upload_url, zip_file, "application/zip")
        else:
            print(f"[*] {zip_file.name} da co san trong release.")
    else:
        print(f"[!] Khong tim thay {zip_file}")

    print("\n[V] HOAN TAT PHAT HANH RELEASE LEN GITHUB!")
