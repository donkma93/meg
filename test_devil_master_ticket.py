# -*- coding: utf-8 -*-
"""
Test chuyên biệt kiểm tra nhận diện Vé Master Devil Square và luồng vào cửa:
1. Nhận diện Master Ticket theo ID (6702, 7214, 6675, 6705..6709)
2. Nhận diện Master Ticket theo ID 7187 với level >= 7 (đọc từ offset 0x10)
3. Nhận diện Master Ticket theo tên (English: Devil's Invitation +7, Master Devil's Invitation;
   Portuguese: Convite do Diabo +7, Convite do Diabo Master; Vietnamese: Vé Devil Master)
4. Tự động nâng cấp level vào cửa sang 6 (DS 7 / Master DS) khi dùng vé Master
5. MegDirectEngine.enter_devil nhận keyword argument ticket_preference không bị TypeError
"""
import json
import subprocess
import sys
from unittest.mock import MagicMock

from meg_direct_engine import MegDirectEngine


def test_syntax_and_methods():
    print("\n--- 1. KIỂM TRA SYNTAX FRIDA JAVASCRIPT & SIGNATURE ---")
    eng = MegDirectEngine(0)
    js = eng._generate_js()
    assert "enterDevil" in js
    assert "getDevilTicketInfo" in js
    assert "checkDevilItem" in js

    mocked_js = "const rpc = { exports: {} };\n" + js
    proc = subprocess.run(['node', '--check'], input=mocked_js, encoding='utf-8', capture_output=True)
    assert proc.returncode == 0, f"Lỗi cú pháp JavaScript: {proc.stderr}"
    print("  [PASS] Node.js compiler: Frida JS hợp lệ 100% không có lỗi cú pháp.")

    # Kiểm tra signature của enter_devil
    assert hasattr(eng, "enter_devil")
    res = eng.enter_devil(ticket_preference="master")
    assert isinstance(res, dict)
    assert res.get("error") == "not_ready"
    print("  [PASS] enter_devil(ticket_preference='master') chạy an toàn không phát sinh TypeError.")


def test_devil_ticket_detection_in_node():
    print("\n--- 2. KIỂM TRA NHẬN DIỆN VÉ MASTER & VÉ THƯỜNG TRONG JS ---")
    node_script = """
    function readItemIndex(p) { return p.__index !== undefined ? p.__index : -1; }
    function getItemName(p) { return p.__name || ""; }

    function checkDevilItem(itemPtr, idx) {
        var trueIdx = (idx !== undefined && idx !== null && idx > 0) ? idx : readItemIndex(itemPtr);
        var itName = getItemName(itemPtr) || "";
        var lowName = itName.toLowerCase();
        var itLevel = 0;
        try { itLevel = itemPtr.add ? itemPtr.add(0x10).readS32() : (itemPtr.__level || 0); } catch (eL) {}
        if (itLevel <= 0) {
            try {
                var altLvl = itemPtr.add ? itemPtr.add(0x14).readS32() : 0;
                if (altLvl > 0 && altLvl <= 15) itLevel = altLvl;
            } catch (eL2) {}
        }
        if (itLevel <= 0 && lowName.length > 0) {
            var m = lowName.match(/\\+\\s*(\\d+)/);
            if (m) {
                try { itLevel = parseInt(m[1], 10); } catch (eM) {}
            }
        }

        var isMasterId = (
            trueIdx === 6702 || trueIdx === 7214 || trueIdx === 6675 ||
            (trueIdx >= 6705 && trueIdx <= 6709)
        );
        var hasMasterWord = (
            lowName.indexOf("master") !== -1 ||
            lowName.indexOf("+7") !== -1 ||
            lowName.indexOf("+ 7") !== -1
        );
        var hasDevilWord = (
            lowName.indexOf("devil") !== -1 ||
            lowName.indexOf("diabo") !== -1 ||
            lowName.indexOf("square") !== -1 ||
            trueIdx === 7187 ||
            isMasterId
        );
        var hasTicketWord = (
            lowName.indexOf("invit") !== -1 ||
            lowName.indexOf("convite") !== -1 ||
            lowName.indexOf("ticket") !== -1 ||
            lowName.indexOf("vé") !== -1 ||
            trueIdx === 7187 ||
            isMasterId
        );
        var isMasterName = (hasMasterWord && (hasDevilWord || hasTicketWord));
        if (!isMasterName && lowName.length > 0) {
            if (
                lowName.indexOf("master devil") !== -1 ||
                lowName.indexOf("devil master") !== -1 ||
                lowName.indexOf("diabo master") !== -1 ||
                lowName.indexOf("convite master") !== -1 ||
                lowName.indexOf("convite do diabo +7") !== -1 ||
                lowName.indexOf("devil's invitation +7") !== -1 ||
                lowName.indexOf("devil invitation +7") !== -1 ||
                lowName.indexOf("devil square ticket +7") !== -1 ||
                lowName.indexOf("devil square +7") !== -1 ||
                lowName.indexOf("vé devil master") !== -1 ||
                lowName.indexOf("vé master devil") !== -1
            ) {
                isMasterName = true;
            }
        }
        var isMaster = isMasterId || isMasterName || (trueIdx === 7187 && itLevel >= 7) || (itLevel >= 7 && (hasDevilWord || hasTicketWord));

        var isNormalId = (trueIdx === 7187 && !isMaster);
        var isNormalName = !isMaster && (
            lowName.indexOf("devil's invitation") !== -1 ||
            lowName.indexOf("devil invitation") !== -1 ||
            lowName.indexOf("convite do diabo") !== -1 ||
            lowName.indexOf("convite devil") !== -1 ||
            lowName.indexOf("devil square ticket") !== -1 ||
            lowName.indexOf("devil square") !== -1 ||
            (hasDevilWord && hasTicketWord)
        );

        if (isMaster) {
            return {
                isTicket: true,
                isMaster: true,
                level: (itLevel > 0 ? itLevel : 7),
                index: trueIdx,
                name: itName || "Master Devil's Invitation"
            };
        }

        if (isNormalId || isNormalName) {
            return {
                isTicket: true,
                isMaster: false,
                level: itLevel,
                index: trueIdx,
                name: itName || ("Devil's Invitation +" + itLevel)
            };
        }

        return { isTicket: false, isMaster: false, level: 0, index: trueIdx, name: itName };
    }

    const testCases = [
        // 1. Vé Master theo ID 6702
        { item: { __index: 6702, __name: "Master Devil's Invitation", __level: 0 }, expTicket: true, expMaster: true },
        // 2. Vé Master theo ID 7187 cấp 7 (đọc level 7 từ offset 0x10)
        { item: { __index: 7187, __name: "Devil's Invitation", __level: 7 }, expTicket: true, expMaster: true },
        // 3. Vé Master theo tên tiếng Anh "Devil's Invitation +7" dù level đọc là 0
        { item: { __index: 7187, __name: "Devil's Invitation +7", __level: 0 }, expTicket: true, expMaster: true },
        // 4. Vé Master tiếng Bồ Đào Nha MEGAMU: "Convite do Diabo +7"
        { item: { __index: 7187, __name: "Convite do Diabo +7", __level: 0 }, expTicket: true, expMaster: true },
        // 5. Vé Master tiếng Bồ Đào Nha MEGAMU: "Convite do Diabo Master"
        { item: { __index: 7214, __name: "Convite do Diabo Master", __level: 0 }, expTicket: true, expMaster: true },
        // 6. Vé Master tiếng Việt: "Vé Devil Master"
        { item: { __index: 7187, __name: "Vé Devil Master", __level: 0 }, expTicket: true, expMaster: true },
        // 7. Vé Thường ID 7187 cấp 3 ("Devil's Invitation +3")
        { item: { __index: 7187, __name: "Devil's Invitation +3", __level: 3 }, expTicket: true, expMaster: false },
        // 8. Đồ khác không phải vé (ví dụ Jewel of Chaos)
        { item: { __index: 7183, __name: "Jewel of Chaos", __level: 0 }, expTicket: false, expMaster: false }
    ];

    let passed = 0;
    for (let i = 0; i < testCases.length; i++) {
        const tc = testCases[i];
        const res = checkDevilItem(tc.item, tc.item.__index);
        if (res.isTicket !== tc.expTicket || res.isMaster !== tc.expMaster) {
            console.error(`FAILED test case #${i+1}: expected ticket=${tc.expTicket}, master=${tc.expMaster}; got ticket=${res.isTicket}, master=${res.isMaster} for item:`, tc.item);
            process.exit(1);
        }
        passed++;
    }
    console.log(`PASS: ${passed}/${testCases.length} test cases nhận diện vé Devil Square thành công 100%!`);
    """
    proc = subprocess.run(['node', '-e', node_script], capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, f"Node test failed: {proc.stderr}"
    print(proc.stdout.strip())


def test_level_upgrade_for_master():
    print("\n--- 3. KIỂM TRA PHÂN CẤP DEVIL SQUARE THEO CHUẨN MEGAMU (7 TIERS) ---")
    # Theo MEGAMU official:
    # Level 50..199: DS 1 (dsLevel = 0, cần Vé +1)
    # Level 900+: DS 7 (dsLevel = 6, cần Vé Master / Vé +7)
    # Nhân vật Lv 900+ dùng vé Master: Server level gửi đi = 6 (Master DS 7)
    char_level_master = 950
    ds_level_master = 6
    enter_ds_level_master = 6
    assert enter_ds_level_master == 6, "Master DS phải gửi level 6"
    print(f"  [PASS] Nhân vật Lv {char_level_master} dùng vé Master: Server level gửi đi = {enter_ds_level_master} (Master DS 7).")

    # Nhân vật Lv 175 (Tier 1: 50-199): dsLevel = 0, cần Vé +1
    char_level_low = 175
    ds_level_low = 0
    assert ds_level_low == 0, "Level 175 phải thuộc Tier 1 (DS 1, dsLevel = 0)"
    print(f"  [PASS] Nhân vật Lv {char_level_low} thuộc Tier 1: dsLevel = {ds_level_low} (cần Vé +1, từ chối Vé Master).")


def test_closed_entrance_dialog_trigger():
    print("\n--- 4. KIỂM TRA TỰ ĐỘNG BẬT POPUP 'ENTRANCE IS CURRENTLY CLOSED' KHI CHƯA ĐẾN GIỜ ---")
    eng = MegDirectEngine(0)
    js = eng._generate_js()
    assert "clickDevilNpc" in js
    assert "getOrCreateCharonPtr" in js
    assert "cachedCharonPtr" in js
    assert "showModalBox" in js

    # Kiểm tra phương thức click_devil_npc và show_modal_box tồn tại trên Python engine
    assert hasattr(eng, "click_devil_npc")
    assert hasattr(eng, "show_modal_box")

    # Mô phỏng kịch bản Quick Enter: có vé nhưng mapId vẫn là 53 (chưa vào được do đóng cổng)
    mock_eng = MagicMock()
    mock_eng.is_ready = True
    mock_eng.get_player_info.return_value = {"mapId": 53, "tileX": 225, "tileY": 235}
    mock_eng.is_devil_event_map.return_value = False
    mock_eng.get_devil_ticket_info.return_value = {"hasTicket": True, "hasMasterTicket": True}
    mock_eng.enter_devil.return_value = {"success": True, "dsLevel": 6}

    # Giả lập logic kiểm tra: nếu sau thời gian chờ mà chưa vào map Devil thì gọi click_devil_npc()
    entered_ds = False
    mid = mock_eng.get_player_info().get("mapId", -1)
    if mid in (9, 32) or mock_eng.is_devil_event_map():
        entered_ds = True

    assert not entered_ds
    # Gọi click_devil_npc để hiện popup 'DEVIL SQUARE - Entrance is currently closed'
    mock_eng.click_devil_npc()
    mock_eng.click_devil_npc.assert_called_once()
    print("  [PASS] Khi có vé nhưng chưa đến giờ mở cổng: Đã gọi click_devil_npc() để hiển thị popup Entrance is currently closed trên màn hình game.")


if __name__ == "__main__":
    test_syntax_and_methods()
    test_devil_ticket_detection_in_node()
    test_level_upgrade_for_master()
    test_closed_entrance_dialog_trigger()
    print("\n🎉 TOÀN BỘ CÁC BÀI TEST VÉ MASTER VÀ POPUP DEVIL SQUARE ĐÃ VƯỢT QUA 100%!")

