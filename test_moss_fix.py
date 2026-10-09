#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_moss_fix.py - Kiểm tra toàn diện bản sửa lỗi tính năng Moss Merchant
1. Kiểm tra cấu hình offsets trong config/megamu_offsets.json và megamu_offsets.json.
2. Kiểm tra các hàm RPC và phương thức xử lý Moss trên MegDirectEngine.
3. Kiểm tra Frida JS script sinh ra không chứa placeholder lỗi và cú pháp hợp lệ.
"""

import os
import sys
import json
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_offsets():
    print("[1] Kiểm tra file offsets...")
    paths = [
        os.path.join(os.path.dirname(__file__), "megamu_offsets.json"),
        os.path.join(os.path.dirname(__file__), "config", "megamu_offsets.json")
    ]
    required_keys = [
        "moss_roll", "moss_roll_handler", "moss_init", "moss_select_cat",
        "game_object_set_active", "component_get_game_object",
        "npc_talk", "get_window_handler", "ui_moss_window"
    ]
    for p in paths:
        assert os.path.exists(p), f"Không tìm thấy file: {p}"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in required_keys:
            assert k in data, f"Thiếu key '{k}' trong {p}"
            assert str(data[k]).startswith("0x"), f"Giá trị '{k}' không hợp lệ: {data[k]}"
        print(f"  -> File {os.path.basename(p)}: OK")

def test_engine_moss_methods():
    print("[2] Kiểm tra phương thức xử lý Moss trên MegDirectEngine...")
    from meg_direct_engine import MegDirectEngine
    
    methods = [
        "roll_moss", "open_moss", "reset_moss_ui", "find_moss_npc",
        "interact_moss_npc", "sell_moss_plus_items", "get_moss_categories"
    ]
    for m in methods:
        assert hasattr(MegDirectEngine, m), f"MegDirectEngine thiếu phương thức '{m}'"
    print("  -> Tất cả phương thức Moss trên MegDirectEngine đã sẵn sàng: OK")

def test_frida_js_template():
    print("[3] Kiểm tra Frida JS Script sinh ra...")
    from meg_direct_engine import MegDirectEngine
    eng = MegDirectEngine(999999)
    js = eng._generate_js()
    
    # Kiểm tra không còn placeholder chưa được thay thế
    forbidden_placeholders = [
        "__GET_WINDOW_HANDLER__",
        "__COMPONENT_GET_GAMEOBJECT__",
        "__MOSS_ROLL__",
        "__MOSS_ROLL_HANDLER__",
        "__MOSS_INIT__",
        "__MOSS_SELECT_CAT__",
        "__GAME_OBJECT_SET_ACTIVE__",
        "__NPC_TALK__",
        "__UI_MOSS_WINDOW__"
    ]
    for ph in forbidden_placeholders:
        assert ph not in js, f"Placeholder '{ph}' chưa được thay thế trong JS!"

    # Kiểm tra sự hiện diện của các hàm quan trọng
    assert "ensureMossRollButtonActive" in js, "Thiếu ensureMossRollButtonActive trong JS"
    assert "nativeGetWindowHandler" in js, "Thiếu nativeGetWindowHandler trong JS"
    assert "interactMossNpc" in js, "Thiếu interactMossNpc trong JS"
    assert "rollMoss" in js, "Thiếu rollMoss trong JS"
    assert "findMossNpc" in js, "Thiếu findMossNpc trong JS"

    # Kiểm tra cú pháp bằng Node.js nếu có
    temp_file = os.path.join(os.path.dirname(__file__), "temp_check_moss.js")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(js)
    try:
        res = subprocess.run(["node", "--check", temp_file], capture_output=True, text=True)
        assert res.returncode == 0, f"Cú pháp JS không hợp lệ:\n{res.stderr}"
        print("  -> Kiểm tra cú pháp bằng Node.js: OK")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    print("  -> Frida JS script: OK")

if __name__ == "__main__":
    try:
        test_offsets()
        test_engine_moss_methods()
        test_frida_js_template()
        print("\n=== TẤT CẢ KIỂM TRA MOSS ĐỀU THÀNH CÔNG (PASS 100%) ===")
    except Exception as e:
        print(f"\n[FAIL] Kiểm tra thất bại: {e}")
        sys.exit(1)
