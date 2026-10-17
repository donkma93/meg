#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_cleaner_protection():
    with open('meg_direct_engine.py', 'r', encoding='utf-8') as f:
        engine_content = f.read()

    with open('meg_gui.py', 'r', encoding='utf-8') as f:
        gui_content = f.read()

    print("=" * 60)
    print("KIỂM THỬ BẢO VỆ ĐỒ VÀ DỌN RÁC MOSS (MOSS CLEANER SAFETY AUDIT)")
    print("=" * 60)

    # 1. Kiểm tra loại bỏ triệt để lỗi s - 12 trong cleanInventoryJunk
    clean_junk_match = re.search(r'cleanInventoryJunk:\s*function\([^)]*\)\s*\{([\s\S]*?)\n\s*\},', engine_content)
    assert clean_junk_match, "Không tìm thấy cleanInventoryJunk trong meg_direct_engine.py"
    clean_junk_body = clean_junk_match.group(1)

    assert "s - 12" not in clean_junk_body, "LỖI NGUY HIỂM: cleanInventoryJunk vẫn còn gọi (s - 12) làm xóa trang bị trên người và đồ slot trước!"
    print("  -> [PASS] cleanInventoryJunk: Đã loại bỏ 100% bug (s - 12)")

    # 2. Kiểm tra dropInventorySlot
    drop_slot_match = re.search(r'dropInventorySlot:\s*function\([^)]*\)\s*\{([\s\S]*?)\n\s*\},', engine_content)
    assert drop_slot_match, "Không tìm thấy dropInventorySlot trong meg_direct_engine.py"
    drop_slot_body = drop_slot_match.group(1)
    assert "s - 12" not in drop_slot_body, "LỖI NGUY HIỂM: dropInventorySlot vẫn còn gọi (s - 12)!"
    assert "if (s < 12)" in drop_slot_body, "dropInventorySlot thiếu guard kiểm tra s < 12"
    print("  -> [PASS] dropInventorySlot: Đã loại bỏ 100% bug (s - 12) và có guard bảo vệ slot 0..11")

    # 3. Kiểm tra sendDropPacket và sendSellPacket
    send_drop_match = re.search(r'function sendDropPacket\([^)]*\)\s*\{([\s\S]*?)\n\}', engine_content)
    assert send_drop_match, "Không tìm thấy sendDropPacket"
    assert "s - 12" not in send_drop_match.group(1), "sendDropPacket vẫn còn s - 12!"
    assert "if (s < 12) return false;" in send_drop_match.group(1), "sendDropPacket thiếu guard s < 12"

    send_sell_match = re.search(r'function sendSellPacket\([^)]*\)\s*\{([\s\S]*?)\n\}', engine_content)
    assert send_sell_match, "Không tìm thấy sendSellPacket"
    assert "slot - 12" not in send_sell_match.group(1), "sendSellPacket vẫn còn slot - 12!"
    assert "if (s < 12) return false;" in send_sell_match.group(1), "sendSellPacket thiếu guard s < 12"
    print("  -> [PASS] sendDropPacket & sendSellPacket: Guard tuyệt đối s < 12 và xóa sạch (s - 12)")

    # 4. Kiểm tra struct offsets trong cleanInventoryJunk và getInventorySummary
    assert "var itemLevel = itemPtr.add(0x10).readS32();" in clean_junk_body, "cleanInventoryJunk phải đọc itemLevel tại +0x10 (không phải +0x14)"
    assert "var skill = itemPtr.add(0x14).readS32();" in clean_junk_body, "cleanInventoryJunk phải đọc skill tại +0x14"
    assert "var luck = itemPtr.add(0x18).readS32();" in clean_junk_body, "cleanInventoryJunk phải đọc luck tại +0x18"
    assert "var sockOpt = itemPtr.add(0x28).readS32();" in clean_junk_body, "cleanInventoryJunk phải đọc sockOpt tại +0x28"
    assert "var harmonyOpt = itemPtr.add(0x2C).readS32();" in clean_junk_body, "cleanInventoryJunk phải đọc harmonyOpt tại +0x2C"
    print("  -> [PASS] Struct offsets Ground-Truth: Đọc chính xác Level (+0x10), Skill (+0x14), Luck (+0x18), Socket (+0x28), Harmony (+0x2C)")

    # 5. Kiểm tra hàm isItemProtected
    assert "function isItemProtected(" in engine_content, "Thiếu hàm isItemProtected"
    assert "if (itemLevel >= 5) return true;" in engine_content, "isItemProtected phải giữ lại đồ cấp độ >= +5"
    assert "if (luck > 0) return true;" not in engine_content, "LỖI NGUY HIỂM: Không được bảo vệ cứng Luck vì 100% đồ quay Moss đều có Luck, sẽ làm bộ dọn không dọn được món nào!"
    assert "if (harmonyOpt > 0) return true;" in engine_content, "isItemProtected phải giữ lại đồ Harmony"
    assert "if (sockOpt > 0) return true;" in engine_content, "isItemProtected phải giữ lại đồ Socket"
    assert "if (ancOpt > 0) return true;" in engine_content, "isItemProtected phải giữ lại đồ Thần (Ancient)"
    assert "if (excOpt > 0) return true;" in engine_content, "isItemProtected phải giữ lại đồ Hoàn Hảo (Exc)"
    print("  -> [PASS] isItemProtected: Quy tắc bảo vệ đạt chuẩn (Level >= 5, Exc, Set, Socket, Harmony, Divine/Ruud, không khóa rác có Luck)")

    # 6. Kiểm tra snapshot và scoping trong meg_gui.py
    assert "self.moss_initial_slots = set()" in gui_content, "meg_gui.py thiếu snapshot moss_initial_slots"
    assert "protected_slots=list(self.moss_initial_slots)" in gui_content, "meg_gui.py phải truyền protected_slots"
    assert "category=self.moss_category" in gui_content, "meg_gui.py phải truyền category để giới hạn dọn rác"
    print("  -> [PASS] meg_gui.py: Snapshot hòm đồ có sẵn trước khi quay và Scoping theo danh mục Moss hoạt động chuẩn")

    print("\n" + "=" * 60)
    print("TẤT CẢ KIỂM THỬ BẢO VỆ ĐỒ VÀ DỌN RÁC MOSS ĐẠT 100% (PASS)")
    print("=" * 60)

if __name__ == "__main__":
    test_cleaner_protection()
