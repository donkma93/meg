#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Auto Navigator - Diagnostic & Verification Tool
=====================================================
Tool kiểm tra chéo tự động:
1. Quét tiến trình MEGAMU client thực sự.
2. Đọc trạng thái live từ RAM (Map, Level, X, Y, Auto Attack).
3. Kiểm tra khả năng hãm phanh RAM (write_target_coord).
4. Kiểm tra độ ổn định vị trí và phát hiện trôi bãi.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from meg_navigator import (
    WindowHelper,
    ProcessMemoryReader,
    MegNavigator,
    scan_all_clients
)

def run_diagnostics():
    print("==================================================", flush=True)
    print(" 🛠️ MEGAMU AUTO NAVIGATOR - SYSTEM DIAGNOSTIC CHECKS", flush=True)
    print("==================================================", flush=True)

    clients = scan_all_clients()
    if not clients:
        print("[!] Không tìm thấy MEGAMU Game Client nào đang chạy trên desktop.", flush=True)
        return

    print(f"[✔] Tìm thấy {len(clients)} client game thực sự:", flush=True)
    for i, c in enumerate(clients, 1):
        print(f"  #{i} | PID: {c.pid} | Tên: {c.char_name} (Lv {c.level or '?'}) | Map: {c.map_name} ({c.x}, {c.y}) | Auto: {'BẬT' if c.is_auto_attack else 'TẮT'}", flush=True)

    target_client = clients[0]
    pid = target_client.pid
    print(f"\n[➔] Đang kiểm tra chéo trên Client PID {pid} ({target_client.char_name})...", flush=True)

    # 1. Đọc RAM
    st = ProcessMemoryReader.read_live_state(pid)
    if not st:
        print("[❌ LỖI] Không thể đọc RAM Live State của process!", flush=True)
        return
    print(f"[✔ RAM READ] Map ID: {st[0]} ({st[1]}), Tọa độ hiện tại: ({st[2]}, {st[3]}), Target: ({st[4]}, {st[5]})", flush=True)

    # 2. Đọc Helper State
    h_st = ProcessMemoryReader.read_helper_state(pid)
    print(f"[✔ HELPER RAM] Active: {h_st[0] if h_st else 'N/A'}, Configured: {h_st[1] if h_st else 'N/A'}, ActiveTime: {h_st[2] if h_st else 'N/A'}s", flush=True)

    # 3. Test Hãm phanh RAM
    if st[2] is not None and st[3] is not None:
        ok = ProcessMemoryReader.write_target_coord(pid, st[2], st[3])
        print(f"[✔ TARGET COORD RAM WRITE] Ghi RAM target_coord = ({st[2]}, {st[3]}): {'THÀNH CÔNG' if ok else 'THẤT BẠI'}", flush=True)

    # 4. Giám sát ổn định vị trí trong 5s
    print("\n[⏱️ SPOT STABILITY MONITOR] Đang theo dõi ổn định vị trí trong 5s...", flush=True)
    start_x, start_y = st[2], st[3]
    max_drift = 0
    for _ in range(5):
        time.sleep(1.0)
        curr = ProcessMemoryReader.read_live_state(pid)
        if curr and curr[2] is not None and curr[3] is not None:
            drift = max(abs(curr[2] - start_x), abs(curr[3] - start_y))
            max_drift = max(max_drift, drift)
            print(f"   • Tọa độ: ({curr[2]}, {curr[3]}) | Trôi: {drift} ô | Auto: {'BẬT' if (curr and ProcessMemoryReader.read_helper_state(pid)[0]) else 'TẮT'}", flush=True)

    print(f"\n[📊 KẾT QUẢ KÍCH THƯỚC TRÔI] Độ trôi vị trí tối đa trong 5s: {max_drift} ô.", flush=True)
    if max_drift > 5:
        print("[⚠️ CẢNH BÁO TRÔI BÃI] Nhân vật có xu hướng trôi xa bãi farm do đuổi quái. Cần bật Spot Guard!", flush=True)
    else:
        print("[✔ ĐẠT CHUẨN] Vị trí nhân vật ổn định trong phạm vi bãi farm!", flush=True)

    print("==================================================", flush=True)

if __name__ == "__main__":
    run_diagnostics()
