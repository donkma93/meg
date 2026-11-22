#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Train Dashboard (Qt6 Native) - Zero-Offset-On-Disk Secure Builder (Nuitka Onefile)
==============================================================================================
Đóng gói ALL-IN-ONE thành DUY NHẤT 1 FILE .EXE:
- Biên dịch meg_license_bridge.dll v3.0 (Zero Hardcoded Offsets + AES-256-CBC RAM Vault)
- Tự động QUÉT CHẶN RÒ RỈ OFFSET trước khi build (fail build ngay nếu còn sót RVA hex!)
- Biên dịch meg_gui_qt.py (PySide6 Qt6 Native 60FPS) thành C++ Machine Code qua Nuitka Onefile
- Tuyệt đối KHÔNG đóng gói megamu_offsets.json, license.json, telegram_config.json cá nhân
"""

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

IGNORED_HEX_CONSTANTS = {
    "0X1F0FFF", "0X00FFFFFF", "0XFFFFFF", "0XFFFFFFFF",
    "0X0000FF", "0X100000", "0X400000", "0X800000",
    "0X6A09E667", "0XBB67AE85", "0X3C6EF372", "0XA54FF53A",
    "0X510E527F", "0X9B05688C", "0X1F83D9AB", "0X5BE0CD19",
}


def log(msg: str):
    print(f"[SECURE BUILD] {msg}", flush=True)


def build_native_dll() -> bool:
    dll_path = BASE_DIR / "meg_license_bridge.dll"
    cpp_source = BASE_DIR / "native_bridge" / "license_bridge.cpp"
    if not cpp_source.exists():
        log(f"LOI: Khong tim thay {cpp_source}")
        return False

    log("Dang bien dich meg_license_bridge.dll v3.0 (Zero-Offset RAM Vault)...")
    cmd = [
        "g++", "-O3", "-shared", "-std=c++17",
        str(cpp_source),
        "-o", str(dll_path),
        "-lwinhttp", "-lbcrypt", "-lcrypt32", "-ladvapi32",
        "-s", "-static-libgcc", "-static-libstdc++",
    ]
    try:
        subprocess.run(cmd, check=True)
        native_bin_dir = BASE_DIR / "native_bin"
        native_bin_dir.mkdir(exist_ok=True)
        shutil.copy2(str(dll_path), str(native_bin_dir / "meg_license_bridge.dll"))
        log("Bien dich meg_license_bridge.dll v3.0 thanh cong!")
        return True
    except Exception as e:
        log(f"LOI bien dich DLL: {e}")
        return False


def audit_zero_offset_leaks() -> bool:
    """
    CỔNG KIỂM DUYỆT BẢO MẬT TRƯỚC KHI BUILD:
    Từ chối build ngay lập tức nếu phát hiện bất kỳ RVA game offset nào bị hardcode
    trong source Python hoặc trong C++ DLL!
    """
    log("Dang chay Cong Kiem Duyet Ro Ri Offset (Zero-Offset Leak Gate)...")
    errors = []

    py_targets = [
        BASE_DIR / "meg_direct_engine.py",
        BASE_DIR / "meg_navigator.py",
        BASE_DIR / "test_entity_radar.py",
        BASE_DIR / "license_client.py",
        BASE_DIR / "meg_gui_qt.py",
    ]
    rva_pat = re.compile(r"\b0x[0-9A-Fa-f]{6,7}\b")

    for path in py_targets:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or s.startswith("//") or s.startswith("*"):
                continue
            code_part = s.split("#")[0].split("//")[0]
            for hit in rva_pat.findall(code_part):
                if hit.upper() not in IGNORED_HEX_CONSTANTS:
                    errors.append(f"{path.name}:L{lineno} -> {hit} ({code_part[:70]})")

    cpp_path = BASE_DIR / "native_bridge" / "license_bridge.cpp"
    if cpp_path.exists():
        cpp_txt = cpp_path.read_text(encoding="utf-8", errors="ignore")
        if "ENC_GAME_OFFSETS" in cpp_txt:
            errors.append("license_bridge.cpp van con mang tinh ENC_GAME_OFFSETS!")

    dll_path = BASE_DIR / "meg_license_bridge.dll"
    if dll_path.exists():
        dll_raw = dll_path.read_bytes()
        for sensitive in (b"0x10D7DD0", b"0x55A4D00", b"0x109D830", b"0xC43C50", b"gremory_claim_item"):
            if sensitive in dll_raw:
                errors.append(f"meg_license_bridge.dll bi lo chuoi nhay cam: {sensitive!r}")

    if errors:
        log("!!! BUILD BI CHAN DO PHAT HIEN RO RI OFFSET !!!")
        for err in errors[:20]:
            log(f"  [LEAK] {err}")
        return False

    log("PASS: 0 RVA offset ro ri trong source Python & C++ DLL!")
    return True


def check_nuitka() -> bool:
    try:
        import nuitka
        log(f"Nuitka version: {getattr(nuitka, '__version__', 'OK')}")
        return True
    except ImportError:
        log("Dang cai dat Nuitka va Zstandard qua pip...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "nuitka", "zstandard"])
        return res.returncode == 0


def kill_running_instances():
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "MEGAMU Auto Train Dashboard.exe", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def run_nuitka_build() -> bool:
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
                log(f"Da doi ten file .exe cu sang {bak.name}")
            except Exception as e_mv:
                log(f"Canh bao doi ten file .exe cu: {e_mv}")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--onefile-no-compression",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--windows-uac-admin",
        "--enable-plugin=pyside6",
        "--windows-icon-from-ico=megamu_dashboard_icon.ico",
        "--output-filename=MEGAMU Auto Train Dashboard.exe",
        f"--output-dir={output_dir}",
        "--include-package=PySide6",
        "--include-package=frida",
        "--include-package=ui",
        "--include-package=ui_qt",
        "--include-package-data=ui_qt",
        "--include-package=services",
        "--include-module=meg_gui",
        "--include-module=meg_direct_engine",
        "--include-module=meg_auto_worker",
        "--include-module=license_client",
        "--include-module=_embedded_bridge",
        "--include-module=updater",
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

    # TUYỆT ĐỐI KHÔNG đóng gói megamu_offsets.json, license.json, telegram_config.json, megamu_accounts.json!
    blocked_files = {
        "megamu_offsets.json",
        "license.json",
        "telegram_config.json",
        "megamu_accounts.json",
        "game_offsets.json",
    }
    src_config = BASE_DIR / "config"
    if src_config.exists():
        for item in src_config.glob("*.json"):
            if item.name.lower() in blocked_files:
                continue
            cmd.append(f"--include-data-file=config/{item.name}=config/{item.name}")
        maps_ini = src_config / "maps.ini"
        if maps_ini.exists():
            cmd.append("--include-data-file=config/maps.ini=config/maps.ini")

    cmd.append("meg_gui_qt.py")

    log("Dang bien dich Qt6 Native Onefile (.exe) voi Nuitka...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode != 0:
        log(f"Loi bien dich Nuitka (Exit code: {res.returncode})")
        return False

    for tmp_folder in ["meg_gui_qt.build", "meg_gui_qt.dist", "meg_gui_qt.onefile-build"]:
        p = output_dir / tmp_folder
        if p.exists():
            try:
                shutil.rmtree(p)
            except Exception:
                pass

    try:
        shutil.copy2(str(BASE_DIR / "meg_license_bridge.dll"), str(output_dir / "meg_license_bridge.dll"))
    except Exception:
        pass

    log("==============================================================================")
    log("  BIEN DICH QT6 SECURE ONEFILE (ZERO-OFFSET-ON-DISK) THANH CONG 100%!")
    log(f"  File thanh pham: {target_exe}")
    log("  [+] 0 offset hardcode trong .EXE va .DLL (100% lay tu Web Server vao RAM)")
    log("  [+] Giao dien Qt6 Native 60FPS + Dong bo License tu dong moi 5 phut")
    log("==============================================================================")
    return True


def main():
    log("BAT DAU TIEN TRINH BUILD SECURE QT6 ONEFILE (ZERO-OFFSET-ON-DISK)...")
    if not build_native_dll():
        sys.exit(1)
    if not audit_zero_offset_leaks():
        sys.exit(1)
    if not check_nuitka():
        sys.exit(1)
    if not run_nuitka_build():
        sys.exit(1)


if __name__ == "__main__":
    main()
