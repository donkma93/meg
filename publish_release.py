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
    return "v1.6.0"

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
            try:
                patch_url = f"https://api.github.com/repos/{REPO}/releases/{data['id']}"
                patch_payload = {
                    "name": release_title,
                    "body": release_body
                }
                patch_req = urllib.request.Request(
                    patch_url,
                    data=json.dumps(patch_payload).encode("utf-8"),
                    headers={**headers, "Content-Type": "application/json"},
                    method="PATCH"
                )
                with _urlopen_with_retry(patch_req) as p_resp:
                    data = json.loads(p_resp.read().decode("utf-8"))
                    print(f"[OK] Da cap nhat Release body & title moi tren GitHub!")
            except Exception as ep:
                print(f"[!] Khong the update body release: {ep}")
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

def delete_asset(token: str, asset_id: int):
    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "ReleasePublisher/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}"
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        with _urlopen_with_retry(req) as resp:
            print(f"[OK] Da xoa asset cu tren GitHub (ID: {asset_id})")
    except Exception as e:
        print(f"[!] Canh bao khi xoa asset {asset_id}: {e}")

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
                # Bao mat: khong bao gio dong goi license ca nhan, tai khoan, offsets, token
                if name_lower.endswith(".old") or name_lower in ("license.json", "megamu_offsets.json", "megamu_accounts.json", "telegram_config.json") or name_lower.endswith(".log"):
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

### Điểm nổi bật & Nâng cấp quan trọng trong bản {version}:
- **Tự Động Ghép Nhiều Party Độc Lập (Auto Multi-PT System):**
  - **Cơ chế tự động chia nhóm 5 acc**: Hệ thống tự động phân chia toàn bộ dàn tài khoản theo quy tắc 5 acc/nhóm (Slot 1–5 vào PT 1, Slot 6–10 vào PT 2, Slot 11–15 vào PT 3...).
  - **Chủ PT độc lập từng nhóm**: Cho phép tự do chỉ định Chủ PT riêng biệt cho từng nhóm (ví dụ PT 1 chủ Slot 2, PT 2 chủ Slot 8), hệ thống tự động hoán đổi vai trò và bảo lưu vĩnh viễn cấu hình.
  - **Giám sát thời gian thực RAM IL2CPP**: Hiển thị bảng Roster trực quan trạng thái trong nhóm (`👑 Chủ PT`, `👥 TV PT`, `🟢 Đã vào PT`, `⚪ Chưa vào PT`).
  - **Tự động mời và hồi phục (Heartbeat Heal)**: Tự động di chuyển sang map Chủ nhóm, bắt tay bằng Direct Engine Native Hook (Packet C1:40) và tự động mời lại khi nhân vật chết, chuyển map hoặc relogin.

- **Hệ Thống License Client C++ Native Bridge:**
  - Chuẩn hóa đường dẫn nạp DLL tuyệt đối, loại bỏ hoàn toàn lỗi thiếu file DLL trên các môi trường chạy khác nhau.
  - Đồng bộ alias `get_hwid()` và trạng thái hiển thị bản quyền Pro (Vĩnh viễn) trên giao diện.

- **Mirror Turbo Burst & Zero-Confirm:**
  - Tối ưu hóa chu kỳ quét và gửi packet liên tục, triệt tiêu độ trễ chuyển map và gom đồ.
  - Tự động nhận thưởng Gremory Case (phím K) Native Hook.

- **Giao Diện & Cơ Chế Cập Nhật Tự Động (Auto Updater UI):**
  - Tích hợp cửa sổ `UpdateModal` trực quan: so sánh phiên bản hiện tại vs mới nhất, xem ghi chú phát hành, thanh tiến trình tải xuống realtime.
  - Tự động thay thế tệp .exe và khởi động lại phiên bản mới an toàn, không lo lock tiến trình.
  - Tự động kiểm tra bản mới ngầm và báo hiệu trực quan `🔥 Có bản mới!` ngay trên thanh Header.
  - Ưu tiên cập nhật trực tiếp file Dashboard và cung cấp nút mở tải bộ cài đặt trên trình duyệt.

- **Kế thừa toàn diện các tính năng Promax:**
  - Phân loại vé Devil Square chuẩn 7 tầng MEGAMU và vé Master.
  - Tự động bán đồ rác Moss tại NPC Silvia với wire packet opcode 0xF9 (mã hóa XOR 0xCB).
  - Khắc phục triệt để crash GUI bằng Thread-Safe Dispatching và Font/Tooltip caching.
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
    if zip_file.exists():
        try:
            zip_file.unlink()
        except Exception:
            pass
    if release_folder:
        create_release_zip(release_folder, zip_file)

    existing_map = {a["name"]: a["id"] for a in release.get("assets", [])}

    # 1. Tai len file thuc thi Portable .exe
    if exe_file and exe_file.exists():
        if "MEGAMU.Auto.Train.Dashboard.exe" in existing_map:
            delete_asset(token, existing_map["MEGAMU.Auto.Train.Dashboard.exe"])
        try:
            upload_asset(token, upload_url, exe_file, "MEGAMU.Auto.Train.Dashboard.exe", "application/vnd.microsoft.portable-executable")
        except Exception as e:
            print(f"[*] Thong bao asset exe: {e}")
    else:
        print(f"[!] Khong tim thay file exe trong Release_MEGAMU hay Release_MEGAMU_Secure")

    # 2. Tai len file cai dat Installer Setup .exe neu co
    clean_v = version.lstrip("vV")
    installer_candidates = [
        BASE_DIR / "dist_installer" / f"MEGAMU_AutoTrain_Setup_{version}.exe",
        BASE_DIR / "dist_installer" / f"MEGAMU_AutoTrain_Setup_v{clean_v}.exe",
        BASE_DIR / "dist_installer" / f"MEGAMU_AutoTrain_Setup_{clean_v}.exe"
    ]
    for inst_cand in installer_candidates:
        if inst_cand.exists():
            if inst_cand.name in existing_map:
                delete_asset(token, existing_map[inst_cand.name])
            try:
                upload_asset(token, upload_url, inst_cand, inst_cand.name, "application/vnd.microsoft.portable-executable")
            except Exception as e:
                print(f"[*] Thong bao asset installer: {e}")
            break

    # 3. Tai len file nen .zip
    if zip_file.exists():
        if zip_file.name in existing_map:
            delete_asset(token, existing_map[zip_file.name])
        try:
            upload_asset(token, upload_url, zip_file, None, "application/zip")
        except Exception as e:
            print(f"[*] Thong bao asset zip: {e}")
    else:
        print(f"[!] Khong tim thay {zip_file}")

    print("\n[V] HOAN TAT PHAT HANH RELEASE LEN GITHUB!")
