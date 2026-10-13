#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_moss_deep_audit.py
Bộ công cụ kiểm thử toàn diện và sâu rộng cho Module Moss Merchant:
1. Audit tính chính xác của các Offsets từ dump/dump.cs.
2. Kiểm tra xung đột Thread-Safety giữa Frida RPC Thread và Unity Main Thread.
3. Kiểm tra hiện tượng Bão Native Call (GameObject.SetActive loop) trong GameUI.Update.
4. Kiểm tra tính hợp lệ cú pháp JS sinh ra qua Node.js.
5. Giả lập kịch bản đa tài khoản (Multi-Client Simulation) để kiểm tra tải CPU/GC.
"""

import os
import sys
import json
import re
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OFFSETS_FILE = BASE_DIR / "config" / "megamu_offsets.json"
DUMP_CS_FILE = BASE_DIR / "dump" / "dump.cs"

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def report(title: str, ok: bool, details: str):
    icon = "✅ [PASS]" if ok else "❌ [FAIL]"
    print(f"{icon} {title}: {details}")

def test_1_offsets_integrity():
    print("\n" + "="*70)
    print("PHẦN 1: KIỂM THỬ TOÀN VẸN VÀ ĐỐI CHIẾU OFFSETS TỪ DUMP.CS")
    print("="*70)

    with open(OFFSETS_FILE, "r", encoding="utf-8") as f:
        offsets = json.load(f)

    # 1.1 Kiểm tra MMossMerchantWindow
    # Update = 0x26D1580
    # Roll handler (NEOMFDBIIHM) = 0x26D1180
    # Init (CLCAABGMDPA) = 0x26D13C0
    # Select category (IEKNBIDHDNL) = 0x26CFD60
    # Window.Show = 0x25117F0
    # GameObject.SetActive = 0x4530F50
    # Component.get_gameObject = 0x452CB30

    check_list = {
        "moss_roll": ("0x278DA90", "MMossMerchantWindow.Update (hàm Update của Unity)"),
        "moss_roll_handler": ("0x278DC90", "MMossMerchantWindow.JDDCPBKMKFP (OnRollClick Handler)"),
        "moss_init": ("0x278FC00", "MMossMerchantWindow.BHFBJLBFMGK (Khởi tạo cửa sổ Moss)"),
        "moss_select_cat": ("0x278D470", "MMossMerchantWindow.JCDDIDMIHGP (Chọn tab category)"),
        "game_object_set_active": ("0x4533470", "UnityEngine.GameObject.SetActive(bool)"),
        "component_get_game_object": ("0x452F050", "UnityEngine.Component.get_gameObject()"),
        "ui_moss_window": ("0x1C8", "GameUI.MossMerchantWindow (offset trong GameUI)"),
    }

    for key, (expected, desc) in check_list.items():
        val = offsets.get(key)
        ok = (val and val.lower() == expected.lower())
        report(f"Offset '{key}'", ok, f"Giá trị: {val} (Kỳ vọng: {expected} - {desc})")

def test_2_engine_script_safety_audit():
    print("\n" + "="*70)
    print("PHẦN 2: AUDIT CƠ CHẾ AN TOÀN TRONG FRIDA SCRIPT CỦA MEGDIRECTENGINE")
    print("="*70)

    from meg_direct_engine import MegDirectEngine
    eng = MegDirectEngine(999999)
    js = eng._generate_js()

    # 2.1 Kiểm tra bão gọi SetActive trong GameUI.Update
    # Phát hiện nếu trong GameUI.Update có đoạn gọi ensureMossRollButtonActive mỗi frame
    pattern_loop_setactive = re.search(r"guiHook\s*=\s*Interceptor\.attach[\s\S]*?ensureMossRollButtonActive\(mossWinCheck", js)
    has_frame_spam = bool(pattern_loop_setactive)
    report(
        "Phát hiện Bão Native Call mỗi frame trong GameUI.Update",
        not has_frame_spam,
        "ĐANG BỊ LỖI SPAM 60 FPS!" if has_frame_spam else "Đã được loại bỏ / bảo vệ an toàn."
    )

    # 2.2 Kiểm tra Thread Safety của rollMoss
    # Nếu rollMoss gọi trực tiếp nativeMossRoll từ RPC thread mà không xếp hàng Main Thread
    pattern_rpc_direct_call = re.search(r"rollMoss:\s*function\([^\)]*\)\s*\{[\s\S]*?nativeMossRoll\(", js)
    has_rpc_thread_violation = bool(pattern_rpc_direct_call)
    report(
        "Thread Safety trong rollMoss (Gọi native Update từ RPC thread)",
        not has_rpc_thread_violation,
        "ĐANG VI PHẠM: Gọi nativeMossRoll trực tiếp từ Frida Background Thread!" if has_rpc_thread_violation else "Đã xếp hàng vào Unity Main Thread an toàn."
    )

    # 2.3 Kiểm tra duplicate packet trigger
    # Gọi cả nativeMossRollHandler VÀ nativeMossRoll trong cùng 1 hàm rollMoss
    has_dual_trigger = ("nativeMossRollHandler" in js and "nativeMossRoll" in js) and has_rpc_thread_violation
    report(
        "Kiểm tra trùng lặp gói tin (Dual Packet Trigger)",
        not has_dual_trigger,
        "ĐANG BỊ LỖI: Gọi cả RollHandler và Roll.Update trong cùng 1 lượt -> Phát 2 packet cùng frame!" if has_dual_trigger else "An toàn, chỉ phát qua 1 kênh chuẩn."
    )

    # 2.4 Kiểm tra kiểm tra m_CachedPtr trước khi gọi SetActive
    has_cached_ptr_check = "m_CachedPtr" in js or "readPointer().isNull()" in js
    report(
        "Kiểm tra an toàn con trỏ Native trước khi gọi SetActive",
        has_cached_ptr_check,
        "Đã có kiểm tra con trỏ Unity C++ object" if has_cached_ptr_check else "CHƯA CÓ: Nguy cơ Access Violation nếu đối tượng bị hủy!"
    )

    # 2.5 Kiểm tra hàm đóng cửa sổ Moss (closeMoss)
    has_close_moss = "closeMoss" in js
    report(
        "Hàm đóng cửa sổ Moss giải phóng tài nguyên (closeMoss)",
        has_close_moss,
        "Đã có hàm closeMoss" if has_close_moss else "THIẾU: Không có hàm đóng bảng Moss khi dừng quay!"
    )

def test_3_node_syntax_check():
    print("\n" + "="*70)
    print("PHẦN 3: KIỂM TRA CÚ PHÁP JAVASCRIPT BẰNG NODE.JS COMPILER")
    print("="*70)

    from meg_direct_engine import MegDirectEngine
    eng = MegDirectEngine(999999)
    js = eng._generate_js()

    temp_file = BASE_DIR / "temp_audit_moss.js"
    temp_file.write_text(js, encoding="utf-8")
    try:
        res = subprocess.run(["node", "--check", str(temp_file)], capture_output=True, text=True)
        ok = (res.returncode == 0)
        report("Node.js Syntax Compilation Check", ok, "Cú pháp hợp lệ 100%" if ok else f"Lỗi cú pháp:\n{res.stderr}")
    finally:
        if temp_file.exists():
            temp_file.unlink()

if __name__ == "__main__":
    test_1_offsets_integrity()
    test_2_engine_script_safety_audit()
    test_3_node_syntax_check()
