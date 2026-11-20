# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

BASE_DIR = Path.cwd()

datas = [
    ('megamu_dashboard_logo.png', '.'),
    ('megamu_dashboard_icon.ico', '.'),
    ('map_commands.json', '.'),
]

# Configs (loại trừ file nhạy cảm cá nhân)
config_dir = BASE_DIR / "config"
if config_dir.exists():
    for f in config_dir.glob("*.json"):
        if f.name.lower() not in ("license.json", "megamu_accounts.json", "megamu_offsets.json", "telegram_config.json"):
            datas.append((f"config/{f.name}", "config"))
    if (config_dir / "maps.ini").exists():
        datas.append(("config/maps.ini", "config"))

binaries = []
if (BASE_DIR / "meg_license_bridge.dll").exists():
    binaries.append(('meg_license_bridge.dll', '.'))

hiddenimports = [
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'customtkinter',
    'darkdetect',
    'psutil',
    'frida',
    'win32gui',
    'win32process',
    'win32con',
    'win32api',
    'meg_gui',
    'meg_direct_engine',
    'meg_auto_worker',
    'license_client',
    'updater',
    'meg_account_manager',
    'meg_navigator',
    'meg_trash_cleaner',
    'telegram_notifier',
    'meg_crash_tracer',
    'meg_rea_hunter',
]

# Thu thập toàn bộ customtkinter, ui, và services
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

hiddenimports += collect_submodules('ui')
hiddenimports += collect_submodules('services')

a = Analysis(
    ['meg_gui_optimized.py'],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MEGAMU Auto Train Dashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='megamu_dashboard_icon.ico'
)
