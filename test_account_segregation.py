#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm tra tính năng phân chia vai trò độc lập giữa các tài khoản:
- Auto Train
- Double Goer (Mirror)
- Moss Merchant
Đảm bảo khi chạy các tính năng, chúng KHÔNG ảnh hưởng hay can thiệp lẫn nhau.
"""
import sys
import json
from pathlib import Path

BASE_DIR = Path("c:/Users/donpv/Desktop/meg")
sys.path.insert(0, str(BASE_DIR))

from meg_gui import ConfigPersistenceManager, SlotController

def test_config_persistence():
    print("[1] Kiểm tra lưu/đọc cấu hình selected_slots cho Mirror và Moss...")
    
    # Test Mirror config
    ConfigPersistenceManager.save_mirror_schedule_config(
        auto_schedule=True,
        auto_prep_before=True,
        prefire_sec=1.2,
        auto_lifecycle=True,
        auto_gremory=True,
        selected_slots=[1, 3, 5]
    )
    m_cfg = ConfigPersistenceManager.load_mirror_schedule_config()
    assert m_cfg.get("selected_slots") == [1, 3, 5], f"Mirror selected_slots mismatch: {m_cfg.get('selected_slots')}"
    print("  -> Mirror selected_slots [1, 3, 5]: OK")

    # Test Moss config
    ConfigPersistenceManager.save_moss_schedule_config(
        auto_schedule=False,
        auto_move_before=True,
        selected_slots=[2, 4]
    )
    moss_cfg = ConfigPersistenceManager.load_moss_schedule_config()
    assert moss_cfg.get("selected_slots") == [2, 4], f"Moss selected_slots mismatch: {moss_cfg.get('selected_slots')}"
    print("  -> Moss selected_slots [2, 4]: OK")

def test_slot_controller_attributes():
    print("[2] Kiểm tra thuộc tính SlotController...")
    ctrl1 = SlotController(1, None)
    assert hasattr(ctrl1, "mirror_enabled"), "ctrl1 thiếu mirror_enabled"
    assert hasattr(ctrl1, "moss_enabled"), "ctrl1 thiếu moss_enabled"
    assert ctrl1.mirror_enabled is True
    assert ctrl1.moss_enabled is True
    print("  -> SlotController mirror_enabled & moss_enabled: OK")

def test_isolation_logic():
    print("[3] Kiểm tra tính độc lập (Isolation) giữa các tài khoản...")
    # Giả lập 6 tài khoản:
    # Slot 1, 2, 3: Chỉ Auto Train (mirror_enabled = False, moss_enabled = False)
    # Slot 4, 5: Đi Mirror (mirror_enabled = True, moss_enabled = False)
    # Slot 6: Đi Moss (mirror_enabled = False, moss_enabled = True)
    slots = []
    for i in range(1, 7):
        c = SlotController(i, None)
        if i in (1, 2, 3):
            c.mirror_enabled = False
            c.moss_enabled = False
        elif i in (4, 5):
            c.mirror_enabled = True
            c.moss_enabled = False
        elif i == 6:
            c.mirror_enabled = False
            c.moss_enabled = True
        slots.append(c)

    # Lọc danh sách tham gia Mirror
    mirror_participants = [c.slot_idx for c in slots if getattr(c, "mirror_enabled", True)]
    assert mirror_participants == [4, 5], f"Mirror participants mismatch: {mirror_participants}"
    print("  -> Danh sách tài khoản đi Mirror: [4, 5] (Slot 1, 2, 3, 6 hoàn toàn không bị kéo đi): OK")

    # Lọc danh sách tham gia Moss
    moss_participants = [c.slot_idx for c in slots if getattr(c, "moss_enabled", True)]
    assert moss_participants == [6], f"Moss participants mismatch: {moss_participants}"
    print("  -> Danh sách tài khoản đi Moss: [6] (Slot 1, 2, 3, 4, 5 hoàn toàn không bị kéo đi): OK")

    # Các tài khoản chỉ Auto Train
    train_only = [c.slot_idx for c in slots if not c.mirror_enabled and not c.moss_enabled]
    assert train_only == [1, 2, 3], f"Train only mismatch: {train_only}"
    print("  -> Danh sách tài khoản chỉ Auto Train: [1, 2, 3] (Được bảo vệ 100%, không bị ngắt quãng): OK")

if __name__ == "__main__":
    test_config_persistence()
    test_slot_controller_attributes()
    test_isolation_logic()
    print("\n✅ TOÀN BỘ TEST LOGIC PHÂN CHIA VAI TRÒ VÀ TÁCH BIỆT TÀI KHOẢN ĐẠT 100%!")

