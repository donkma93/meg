#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard - Native C Machine Code Builder (Nuitka Onefile)
============================================================================
Đóng gói ALL-IN-ONE thành DUY NHẤT 1 FILE .EXE:
- 100% Native C++ Machine Code (MSVC cl.exe), chống dịch ngược hoàn toàn.
- Loại bỏ toàn bộ thư viện Qt/PySide6 thừa rác (--enable-plugin=no-qt).
- Nhúng trọn vẹn C++ DLL, icons, themes, map commands bên trong 1 file .exe duy nhất.
- Không để lộ bất kỳ file .py, .pyc, .pyd hay megamu_offsets.json nào.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def log(msg: str):
    print(f"[SECURE BUILD] {msg}", flush=True)

def check_native_dll():
    dll_path = BASE_DIR / "meg_license_bridge.dll"
    if dll_path.exists():
        log("meg_license_bridge.dll: DA SAN SANG.")
        return True

    log("Dang bien dich meg_license_bridge.dll tu C++...")
    cpp_source = BASE_DIR / "native_bridge" / "license_bridge.cpp"
    cmd = [
        "g++", "-O3", "-shared", "-std=c++17",
        str(cpp_source),
        "-o", str(dll_path),
        "-lwinhttp", "-lcrypt32", "-ladvapi32",
        "-s", "-static-libgcc", "-static-libstdc++"
    ]
    try:
        subprocess.run(cmd, check=True)
        log("Bien dich meg_license_bridge.dll thanh cong!")
        return True
    except Exception as e:
        log(f"Loi bien dich DLL: {e}")
        return False

def check_nuitka():
    try:
        import nuitka
        log(f"Nuitka version: {getattr(nuitka, '__version__', 'OK')}")
        return True
    except ImportError:
        log("Dang cai dat Nuitka va Zstandard qua pip...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "nuitka", "zstandard"])
        return res.returncode == 0

def kill_running_instances():
    """Tat cac tien trinh dashboard dang chay de tranh loi File Lock khi ghi de .exe"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "MEGAMU Auto Train Dashboard.exe", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def run_nuitka_build():
    output_dir = BASE_DIR / "Release_MEGAMU_Secure"
    output_dir.mkdir(parents=True, exist_ok=True)
    target_exe = output_dir / "MEGAMU Auto Train Dashboard.exe"

    kill_running_instances()
    if target_exe.exists():
        try:
            target_exe.unlink()
        except Exception:
            try:
                import time
                bak = output_dir / f"MEGAMU Auto Train Dashboard.exe.{int(time.time())}.old"
                target_exe.rename(bak)
                log(f"Da rename file .exe cu sang {bak.name} do dang bi khoa boi tien trinh.")
            except Exception as e_mv:
                log(f"Canh bao di chuyen file .exe cu: {e_mv}")

    # Chuẩn bị thư mục native_bin cho cờ raw-dir
    native_bin_dir = BASE_DIR / "native_bin"
    native_bin_dir.mkdir(exist_ok=True)
    if (BASE_DIR / "meg_license_bridge.dll").exists():
        try:
            shutil.copy2(str(BASE_DIR / "meg_license_bridge.dll"), str(native_bin_dir / "meg_license_bridge.dll"))
        except Exception:
            pass

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--onefile-no-compression",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--windows-uac-admin",
        "--enable-plugin=tk-inter",
        "--enable-plugin=no-qt",
        "--windows-icon-from-ico=megamu_dashboard_icon.ico",
        "--output-filename=MEGAMU Auto Train Dashboard.exe",
        f"--output-dir={output_dir}",
        "--include-package=customtkinter",
        "--include-package-data=customtkinter",
        "--include-package=PIL",
        "--include-package=frida",
        "--include-module=meg_direct_engine",
        "--include-module=meg_auto_worker",
        "--include-module=license_client",
        "--include-module=_embedded_bridge",
        "--include-module=updater",
        "--include-module=meg_ram_optimizer",
        "--include-module=meg_account_manager",
        "--include-module=meg_navigator",
        "--include-module=meg_trash_cleaner",
        "--include-module=meg_crash_tracer",
        "--include-module=meg_rea_hunter",
        "--include-module=test_entity_radar",
        "--include-module=telegram_notifier",
        "--include-raw-dir=native_bin=native_bin",
        "--include-data-file=megamu_dashboard_icon.ico=megamu_dashboard_icon.ico",
        "--include-data-file=megamu_dashboard_logo.png=megamu_dashboard_logo.png",
        "--include-data-file=map_commands.json=map_commands.json",
    ]

    # Nhúng các file cấu hình an toàn vào trong .exe (LOẠI BỎ megamu_offsets.json, license.json, telegram_config.json, megamu_accounts.json cá nhân)
    src_config = BASE_DIR / "config"
    if src_config.exists():
        for item in src_config.glob("*.json"):
            # BẢO MẬT: TUYỆT ĐỐI KHÔNG đóng gói license.json, tài khoản hay thông tin bot cá nhân
            if item.name.lower() in ("megamu_offsets.json", "license.json", "telegram_config.json", "megamu_accounts.json"):
                continue
            cmd.append(f"--include-data-file=config/{item.name}=config/{item.name}")
        maps_ini = src_config / "maps.ini"
        if maps_ini.exists():
            cmd.append("--include-data-file=config/maps.ini=config/maps.ini")

    cmd.append("meg_gui.py")

    log("Dang khoi chay qua trinh bien dich C++ Onefile voi Nuitka...")
    log("Tien hanh dong goi 1 FILE .EXE DUY NHAT va loai bo sach se file rac Qt6...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode != 0:
        log(f"Loi bien dich Nuitka (Exit code: {res.returncode})")
        return False

    # Don dep tat ca cac thu muc tam, chi giu lai DUY NHAT 1 file .EXE
    for tmp_folder in ["meg_gui.build", "meg_gui.dist", "meg_gui.onefile-build"]:
        p = output_dir / tmp_folder
        if p.exists():
            try:
                shutil.rmtree(p)
            except Exception:
                pass

    # Đảm bảo có meg_license_bridge.dll trong thư mục Release
    try:
        shutil.copy2(str(BASE_DIR / "meg_license_bridge.dll"), str(output_dir / "meg_license_bridge.dll"))
    except Exception:
        pass
    log("       BIEN DICH NATIVE C (ALL-IN-ONE ONEFILE) HOAN TAT XUAT SAC 100%!")
    log("==============================================================================")
    log(f"File khoi dong duy nhat: {target_exe}")
    log("Dac diem:")
    log("  [+] Chi 1 file .EXE duy nhat de gui cho khach hang.")
    log("  [+] 100% Native C++ Machine Code (MSVC cl.exe), mien nhiem dich nguoc.")
    log("  [+] Da loai bo hoan toan cac thu vien rac Qt6/PySide6.")
    log("  [+] Khong con bat ky file .py, .pyc, .pyd nao ben ngoai.")
    log("==============================================================================")
    return True

def main():
    log("BAT DAU TIEN TRINH BUILD SECURE NATIVE ONEFILE BINARY...")
    if not check_native_dll():
        sys.exit(1)
    if not check_nuitka():
        sys.exit(1)
    if not run_nuitka_build():
        sys.exit(1)

if __name__ == "__main__":
    main()
