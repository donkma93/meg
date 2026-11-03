#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - Automated Installer Builder (Inno Setup 6)
========================================================================
Tự động đóng gói bản cài đặt (Setup.exe) từ bản build để phân phối cho người dùng khác:
1. Tự động tìm kiếm trình biên dịch Inno Setup 6 (ISCC.exe).
2. Chuẩn bị thư mục staging sạch (loại bỏ tài khoản, license cá nhân, file log).
3. Biên dịch installer.iss thành file cài đặt duy nhất: MEGAMU_AutoTrain_Setup_vX.X.X.exe.
4. Mở thư mục kết quả để người dùng có thể gửi ngay cho người khác.
"""

import os
import sys
import shutil
import subprocess
import re
from pathlib import Path

# Đảm bảo in tiếng Việt có dấu an toàn trên Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent

def log(msg: str, tag: str = "INFO"):
    print(f"[{tag}] {msg}", flush=True)

def find_iscc() -> Path:
    """Tìm đường dẫn Inno Setup Compiler (ISCC.exe)."""
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
    ]
    # Kiểm tra trong PATH
    which_iscc = shutil.which("iscc")
    if which_iscc:
        candidates.insert(0, Path(which_iscc))

    for p in candidates:
        if p.exists():
            return p
    return None

def get_app_version() -> str:
    """Lấy số phiên bản từ meg_gui.py."""
    gui_file = BASE_DIR / "meg_gui.py"
    if gui_file.exists():
        content = gui_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'APP_VERSION\s*=\s*["\']v?([^"\']+)["\']', content)
        if m:
            return m.group(1).strip()
    return "1.5.5"

def prepare_staging_dir(build_dir: Path, staging_dir: Path):
    """Chuẩn bị thư mục staging sạch sẽ, loại bỏ dữ liệu cá nhân."""
    log(f"Đang chuẩn bị thư mục staging từ: {build_dir} -> {staging_dir}")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy file .exe chính
    exe_src = build_dir / "MEGAMU Auto Train Dashboard.exe"
    if not exe_src.exists():
        raise FileNotFoundError(f"Không tìm thấy file thực thi chính: {exe_src}")
    shutil.copy2(exe_src, staging_dir / "MEGAMU Auto Train Dashboard.exe")

    # 2. Copy meg_license_bridge.dll
    dll_src = build_dir / "meg_license_bridge.dll"
    if not dll_src.exists():
        dll_src = BASE_DIR / "meg_license_bridge.dll"
    if dll_src.exists():
        shutil.copy2(dll_src, staging_dir / "meg_license_bridge.dll")
    else:
        raise FileNotFoundError(f"Không tìm thấy meg_license_bridge.dll!")

    # 3. Copy Icons và Logos
    for f in ["megamu_dashboard_icon.ico", "megamu_dashboard_logo.png", "map_commands.json"]:
        src = build_dir / f if (build_dir / f).exists() else BASE_DIR / f
        if src.exists():
            shutil.copy2(src, staging_dir / f)

    # 4. Copy thư mục config sạch sẽ
    staging_cfg = staging_dir / "config"
    staging_cfg.mkdir(parents=True, exist_ok=True)

    src_cfg = build_dir / "config" if (build_dir / "config").exists() else BASE_DIR / "config"
    if src_cfg.exists():
        for item in src_cfg.glob("*"):
            if item.is_file():
                # BẢO MẬT & QUYỀN RIÊNG TƯ:
                # Không copy license.json cá nhân, tài khoản cá nhân, log, và offset nội bộ
                name_lower = item.name.lower()
                if name_lower in ("license.json", "megamu_accounts.json", "megamu_offsets.json") or name_lower.endswith(".log"):
                    continue
                shutil.copy2(item, staging_cfg / item.name)

    log("Chuẩn bị dữ liệu staging hoàn tất (Đã loại bỏ tài khoản & license cá nhân).", "SUCCESS")

def build_installer(iscc_path: Path, version: str, staging_dir: Path, output_dir: Path) -> Path:
    """Gọi Inno Setup Compiler để tạo file Setup.exe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"MEGAMU_AutoTrain_Setup_v{version}"
    iss_script = BASE_DIR / "installer.iss"

    cmd = [
        str(iscc_path),
        f"/DMyAppVersion={version}",
        f"/DSourceDir={staging_dir}",
        f"/DOutputDir={output_dir}",
        f"/DOutputFileName={out_filename}",
        str(iss_script)
    ]

    log(f"Đang biên dịch Installer bằng Inno Setup 6...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode != 0:
        raise RuntimeError(f"Biên dịch Inno Setup thất bại với mã lỗi: {res.returncode}")

    target_setup = output_dir / f"{out_filename}.exe"
    if not target_setup.exists():
        raise FileNotFoundError(f"Không tìm thấy file installer sau khi build: {target_setup}")

    return target_setup

def main():
    print("=" * 76)
    print("      MEGAMU AUTO TRAIN DASHBOARD - CÔNG CỤ TẠO BẢN CÀI ĐẶT (INSTALLER)")
    print("=" * 76)

    # 1. Kiểm tra Inno Setup
    iscc = find_iscc()
    if not iscc:
        log("KHÔNG TÌM THẤY INNO SETUP 6 (ISCC.exe) TRÊN MÁY TÍNH!", "ERROR")
        log("Vui lòng tải và cài đặt Inno Setup 6 miễn phí tại: https://jrsoftware.org/isdl.php", "ERROR")
        sys.exit(1)
    log(f"Đã tìm thấy Inno Setup Compiler: {iscc}", "SUCCESS")

    # 2. Xác định thư mục build nguồn (Tự động chọn bản build có MEGAMU Auto Train Dashboard.exe mới nhất)
    build_dir = None
    candidates = []
    for d_name in ["Release_MEGAMU_Secure", "Release_MEGAMU"]:
        d_path = BASE_DIR / d_name
        exe_path = d_path / "MEGAMU Auto Train Dashboard.exe"
        if exe_path.exists():
            candidates.append((exe_path.stat().st_mtime, d_path))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        build_dir = candidates[0][1]
        log(f"Phát hiện và sử dụng bản build mới nhất từ: {build_dir.name}", "SUCCESS")
    else:
        log("Chưa có bản build nào trong Release_MEGAMU hay Release_MEGAMU_Secure!", "WARNING")
        log("Đang tự động khởi chạy build bản mới qua build_all_to_folder.bat...", "INFO")
        bat_file = BASE_DIR / "build_all_to_folder.bat"
        if bat_file.exists():
            subprocess.run(["cmd.exe", "/c", str(bat_file), "/nopause"], cwd=str(BASE_DIR), check=True)
            build_dir = BASE_DIR / "Release_MEGAMU"
        else:
            log("Không tìm thấy build_all_to_folder.bat để tự động build!", "ERROR")
            sys.exit(1)

    # 3. Chuẩn bị thư mục staging và thông tin phiên bản
    version = get_app_version()
    staging_dir = BASE_DIR / "installer_staging"
    output_dir = BASE_DIR / "dist_installer"

    log(f"Phiên bản ứng dụng: v{version}")
    prepare_staging_dir(build_dir, staging_dir)

    # 4. Biên dịch file cài đặt
    try:
        setup_exe = build_installer(iscc, version, staging_dir, output_dir)
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print("=" * 76)
        log("TẠO BẢN CÀI ĐẶT THÀNH CÔNG RỰC RỠ 100%!", "SUCCESS")
        print(f"  + Tệp cài đặt duy nhất: {setup_exe}")
        print(f"  + Dung lượng tệp Setup: {size_mb:.2f} MB (Đã nén siêu tốc LZMA2)")
        print(f"  + Bạn chỉ cần gửi duy nhất file {setup_exe.name} cho người khác!")
        print("=" * 76)

        # Mở thư mục kết quả
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", str(output_dir)])

    except Exception as e:
        log(f"Quá trình đóng gói gặp sự cố: {e}", "ERROR")
        sys.exit(1)
    finally:
        # Dọn dẹp thư mục staging tạm thời
        if staging_dir.exists():
            try:
                shutil.rmtree(staging_dir)
            except Exception:
                pass

if __name__ == "__main__":
    main()
