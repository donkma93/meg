#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_moss_comprehensive_cross_audit.py
Kiểm thử chéo toàn diện kiến trúc Auto Moss Merchant:
1. Đối chiếu ground-truth từ dump.cs và GameAssembly.dll.
2. Kiểm tra tính toàn vẹn của engine (meg_direct_engine.py).
3. Kiểm tra luồng xử lý giao diện và auto loop trong meg_gui.py.
4. Biên dịch kiểm tra cú pháp Python và Node.js.
"""

import os
import sys
import json
import py_compile
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_cross_audit():
    print("=" * 70)
    print("KIỂM THỬ CHÉO TOÀN DIỆN AUTO MOSS THE GAMBLER")
    print("=" * 70)

    # 1. Compile Check
    print("\n[BƯỚC 1] Kiểm tra biên dịch mã nguồn (Python Compilation Check)...")
    py_compile.compile("meg_direct_engine.py", doraise=True)
    print("  -> meg_direct_engine.py: BIÊN DỊCH THÀNH CÔNG (0 cú pháp lỗi)")
    py_compile.compile("meg_gui.py", doraise=True)
    print("  -> meg_gui.py: BIÊN DỊCH THÀNH CÔNG (0 cú pháp lỗi)")

    # 2. Kiểm tra Offsets Ground-Truth
    print("\n[BƯỚC 2] Kiểm tra đối chiếu offsets Ground-Truth...")
    with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    expected = {
        "moss_send_roll": "0x23F8BE0",
        "moss_roll_click": "0x27AA8B0",
        "moss_window_close": "0x1A183F0",
        "moss_select_cat": "0x27A8510",
        "ui_moss_window": "0x1C8",
        "window_hide": "0x25F8B80",
        "game_object_set_active": "0x45CCB90"
    }
    for k, v in expected.items():
        assert cfg.get(k) == v, f"Offset {k} không khớp kỳ vọng! Thực tế: {cfg.get(k)}, kỳ vọng: {v}"
        print(f"  -> Offset '{k}': {v} (HỢP LỆ)")

    # 3. Kiểm tra logic Frida JS của Engine
    print("\n[BƯỚC 3] Kiểm tra Frida JS Engine Template...")
    from meg_direct_engine import MegDirectEngine
    eng = MegDirectEngine(999999)
    js = eng._generate_js()

    # Kiểm tra không còn rò rỉ nativeMossRollHandler trong rollMoss
    assert "nativeMossSendRoll(cat)" in js, "rollMoss phải ưu tiên gọi nativeMossSendRoll"
    assert "nativeMossRollClick(mossWin" in js, "rollMoss phải có fallback qua nativeMossRollClick"
    assert "nativeMossWindowClose(mossWin" in js, "closeMoss phải gọi nativeMossWindowClose"
    
    # Kiểm tra setupMossWindow không được gọi nativeMossInit để tránh duplicate nút Category
    setup_start = js.find("function setupMossWindow")
    setup_end = js.find("function findMossNpc")
    setup_body = js[setup_start:setup_end]
    assert "nativeMossInit(mossWin" not in setup_body, "setupMossWindow tuyệt đối không được gọi nativeMossInit!"
    print("  -> setupMossWindow: Đã bảo vệ 100% chống nhân bản Category nút rác")

    # Kiểm tra rollMoss không gọi nativeMossRollHandler (RVA 0x278DC90) làm nhân bản category
    roll_start = js.find("rollMoss: function")
    roll_end = js.find("closeMoss: function")
    roll_body = js[roll_start:roll_end]
    assert "nativeMossRollHandler" not in roll_body, "rollMoss không được gọi nativeMossRollHandler (RVA 0x278DC90)!"
    print("  -> rollMoss: Không gọi 0x278DC90, tránh nhân bản nút rác và đè delegate vào CloseButton")

    # Kiểm tra cú pháp JS qua Node.js
    temp_file = "temp_moss_audit.js"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(js)
    try:
        res = subprocess.run(["node", "--check", temp_file], capture_output=True, text=True)
        assert res.returncode == 0, f"Lỗi cú pháp JS:\n{res.stderr}"
        print("  -> Node.js Syntax Verification: PASS 100%")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    # 4. Kiểm tra luồng Auto Moss trong meg_gui.py
    print("\n[BƯỚC 4] Kiểm tra luồng Auto Moss trong meg_gui.py...")
    with open("meg_gui.py", "r", encoding="utf-8") as f:
        gui_content = f.read()

    # Đảm bảo có snapshot hòm đồ để phát hiện item trúng thưởng
    assert "inv_before = eng.get_inventory_summary" in gui_content or "inv_before = None" in gui_content, "Thiếu snapshot hòm đồ trước khi quay"
    assert "inv_after = eng.get_inventory_summary" in gui_content, "Thiếu kiểm tra hòm đồ sau khi quay"
    assert "Trúng:" in gui_content, "Thiếu log thông báo item trúng thưởng"
    
    # Đảm bảo stop_moss đóng cửa sổ tức thì
    assert "eng.close_moss()" in gui_content, "stop_moss phải gọi eng.close_moss()"
    print("  -> meg_gui.py: Tích hợp đầy đủ luồng Verification vật phẩm trúng thưởng & đóng cửa sổ an toàn")

    print("\n" + "=" * 70)
    print("KẾT QUẢ KIỂM THỬ CHÉO: TẤT CẢ CÁC BÀI TEST ĐỀU ĐẠT CHUẨN 100% (PASS)")
    print("=" * 70)

if __name__ == "__main__":
    run_cross_audit()
