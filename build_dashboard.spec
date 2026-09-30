# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas = [
    ('megamu_dashboard_logo.png', '.'),
    ('megamu_dashboard_icon.ico', '.')
]
binaries = []
hiddenimports = [
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'customtkinter',
    'psutil',
    'frida',
    'meg_direct_engine',
    'meg_auto_worker'
]

tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ['meg_gui.py'],
    pathex=[],
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
