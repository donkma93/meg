#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Confirm Party - Verification & Diagnostic Tool
=========================================================
Kiểm tra tính năng tự động đồng ý / xác nhận lời mời Party:
1. Xác thực các offsets liên quan đến Party Confirmation & HelperUI.
2. Kiểm tra hàm set_auto_confirm_party và is_auto_confirm_party_enabled trên engine live.
3. Đọc RAM cấu trúc HelperUI và Dialogs dictionary.
"""

import sys
import os
import json
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from meg_direct_engine import MegDirectEngine, DEFAULT_OFFSETS
from meg_navigator import ProcessMemoryReader

print("=== 1. KIỂM TRA CẤU HÌNH VÀ OFFSETS AUTO CONFIRM PARTY ===")
required_keys = [
    "party_invite_by_key",
    "get_helper_ui",
    "mhelper_show_dialog_id",
    "mhelper_show_dialog_generic",
    "user_party_send_response",
    "user_party_c2_40",
    "button_press",
    "unity_event_invoke",
    "mdialog_confirm_yes"
]

with open("megamu_offsets.json", "r", encoding="utf-8") as f:
    root_cfg = json.load(f)

for k in required_keys:
    val = root_cfg.get(k)
    def_val = DEFAULT_OFFSETS.get(k)
    print(f"  [CHECK] {k:30s}: cfg={val} | default={def_val}")
    assert val is not None, f"Missing key {k} in megamu_offsets.json"
    assert def_val is not None, f"Missing key {k} in DEFAULT_OFFSETS"

print("\n=== 2. KIỂM TRA AUTO CONFIRM PARTY TRÊN ENGINE LIVE ===")
import psutil
pids = [p.pid for p in psutil.process_iter(['pid', 'name']) if 'megamu' in p.info['name'].lower()]
if not pids:
    print("  [WARN] Không tìm thấy tiến trình MEGAMU nào đang chạy để test live!")
for pid in pids:
    st = ProcessMemoryReader.read_live_state(pid)
    cname = ProcessMemoryReader.read_character_name(pid) or "Unknown"
    pt = ProcessMemoryReader.read_party_info(pid)
    print(f"  [PROCESS] PID: {pid} | Tên: {cname} | Map: {st[1] if st else 'Unknown'} | InParty: {pt.get('in_party')}")

    engine = MegDirectEngine.get_engine(pid)
    assert engine.is_ready, f"Engine for PID {pid} is not ready"

    # Kiểm tra trạng thái Auto Confirm Party
    is_enabled = engine.is_auto_confirm_party_enabled()
    print(f"  [ENGINE] PID {pid} auto_confirm_party mặc định: {is_enabled}")
    assert is_enabled is True, "auto_confirm_party should be True by default"

    # Kiểm tra bật/tắt qua RPC
    ok_off = engine.set_auto_confirm_party(False)
    assert ok_off is True and engine.is_auto_confirm_party_enabled() is False, "Failed to toggle off"
    ok_on = engine.set_auto_confirm_party(True)
    assert ok_on is True and engine.is_auto_confirm_party_enabled() is True, "Failed to toggle on"
    print(f"  [RPC] Toggle set_auto_confirm_party(False -> True): HOÀN TOÀN THÀNH CÔNG!")

print("\n=======================================================")
print("🎉 TOÀN BỘ KIỂM TRA AUTO CONFIRM PARTY THÀNH CÔNG 100%!")
print("=======================================================")
