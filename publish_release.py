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
    return "v1.5.3"

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
        with urllib.request.urlopen(req) as resp:
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
                if name_lower in ("license.json", "megamu_offsets.json", "megamu_accounts.json") or name_lower.endswith(".log"):
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
- **Cập nhật GameAssembly Offsets Mới Nhất:** Tương thích 100% với phiên bản MEGAMU mới (Chat, MLocationFrame Helper Start/Stop, Moss, Mirror, Devil Square).
- **Khắc phục Triệt để Lỗi Vứt Đồ & Bảo vệ Trang bị:** Sửa hoàn toàn lỗi tính toán slot (s - 12) khi dọn rác; bổ sung guard cứng bảo vệ 100% trang bị đang mặc (slots 0..11).
- **Bộ lọc An toàn Nâng cao:** Tự động bảo vệ và giữ lại đồ Ruud, Archangel, Ancient (Đồ Thần), Socket, Harmony, Hoàn Hảo (Exc) và đồ cấp độ từ +5 trở lên.
- **Tối ưu hóa Quy trình Auto Devil Square:** Nhận diện chính xác cả vé thường (7187) lẫn vé master (6702); tự động di chuyển tiếp cận NPC Charon tại tọa độ (225, 52) Event Square và phát thông báo ingame khi cổng đóng.
- **Tối ưu Đa luồng Dashboard GUI:** Chuyển toàn bộ tác vụ quét game, đồng bộ telemetry và Bật/Tắt hàng loạt sang chạy ngầm (async background thread), loại bỏ hoàn toàn hiện tượng đơ/lag giao diện.
- **Tự động Cập nhật Trực tiếp (Auto-Updater):** Tự động phát hiện phiên bản mới và cập nhật ghi đè file .exe an toàn cho người dùng.

---
### Tải về:
- **`MEGAMU Auto Train Dashboard.exe`**: File chạy trực tiếp không cần cài đặt (Standalone All-in-One).
- **`MEGAMU_Auto_Train_Dashboard_{version}.zip`**: Trọn bộ gói ứng dụng giải nén kèm thư mục cấu hình và DLL.
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
