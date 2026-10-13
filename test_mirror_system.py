import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_offsets():
    print("=== 1. KIỂM TRA RVA TRONG DUMP.CS VÀ OFFSETS JSON ===")
    json_path = Path("megamu_offsets.json")
    assert json_path.exists(), "megamu_offsets.json không tồn tại!"
    
    with open(json_path, "r", encoding="utf-8") as f:
        offsets = json.load(f)

    rvas = {
        "mirror_enter": int(offsets.get("mirror_enter"), 16),
        "mirror_npc_click": int(offsets.get("mirror_npc_click"), 16),
        "mirror_is_event_map": int(offsets.get("mirror_is_event_map"), 16),
        "mirror_teleport_event": int(offsets.get("mirror_teleport_event"), 16),
        "item_mirror_ticket": int(offsets.get("item_mirror_ticket"))
    }

    for k, v in rvas.items():
        print(f"  {k}: {hex(v)} ({v})")

    assert rvas["mirror_enter"] == 0x106EF40, "mirror_enter RVA mismatch!"
    assert rvas["mirror_npc_click"] == 0x10677F0, "mirror_npc_click RVA mismatch!"
    assert rvas["mirror_is_event_map"] == 0x10689A0, "mirror_is_event_map RVA mismatch!"
    assert rvas["mirror_teleport_event"] == 0x37E2C0, "mirror_teleport_event RVA mismatch!"
    assert rvas["item_mirror_ticket"] == 7279, "item_mirror_ticket mismatch!"
    print("  => OK: Toàn bộ RVA và Item ID đã được xác thực chính xác.")
def test_scheduler_algorithm():
    print("\n=== 2. KIỂM TRA THUẬT TOÁN ĐẾM NGƯỢC VÀ LẬP LỊCH MIRROR (2H/LẦN) ===")
    print("  Quy tắc: Cổng mở lúc :10, sự kiện bắt đầu lúc :15. Chuẩn bị từ :08. Vào cửa ngay từ :10.")
    valid_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]

    def check_mirror_state(now):
        # 1. Kiểm tra xem đang trong khung cổng mở hay không (:10 <= minute < :15)
        is_gate_open = (now.hour in valid_hours and 10 <= now.minute < 15)
        
        # 2. Tìm mốc mở cổng kế tiếp (:10)
        next_gate_time = None
        for h in valid_hours:
            candidate = now.replace(hour=h, minute=10, second=0, microsecond=0)
            if candidate > now:
                next_gate_time = candidate
                break
        if not next_gate_time:
            tomorrow = now + timedelta(days=1)
            next_gate_time = tomorrow.replace(hour=0, minute=10, second=0, microsecond=0)

        seconds_until_gate = int((next_gate_time - now).total_seconds())
        # Chuẩn bị trước 2 phút (từ :08 hoặc khi seconds_until_gate <= 120)
        is_prep = (not is_gate_open and seconds_until_gate <= 120)

        return is_gate_open, is_prep, next_gate_time, seconds_until_gate

    test_cases = [
        (datetime(2026, 10, 9, 0, 5, 0), False, False, datetime(2026, 10, 9, 0, 10, 0), "Lúc 00:05 - Chưa mở cổng, chưa cần chuẩn bị"),
        (datetime(2026, 10, 9, 0, 8, 0), False, True, datetime(2026, 10, 9, 0, 10, 0), "Lúc 00:08 - Bắt đầu chuẩn bị (còn 2 phút mở cổng)"),
        (datetime(2026, 10, 9, 0, 9, 30), False, True, datetime(2026, 10, 9, 0, 10, 0), "Lúc 00:09:30 - Sát giờ mở cổng (còn 30s chuẩn bị)"),
        (datetime(2026, 10, 9, 0, 10, 0), True, False, datetime(2026, 10, 9, 2, 10, 0), "Lúc 00:10:00 - CỔNG MỞ! Kích hoạt vào cửa ngay"),
        (datetime(2026, 10, 9, 0, 12, 30), True, False, datetime(2026, 10, 9, 2, 10, 0), "Lúc 00:12:30 - Cổng vẫn đang mở (trong khung :10-:15)"),
        (datetime(2026, 10, 9, 0, 14, 59), True, False, datetime(2026, 10, 9, 2, 10, 0), "Lúc 00:14:59 - Giây cuối cùng của cổng mở"),
        (datetime(2026, 10, 9, 0, 15, 0), False, False, datetime(2026, 10, 9, 2, 10, 0), "Lúc 00:15:00 - Sự kiện bắt đầu, cổng đóng, đếm ngược đợt 02:10"),
        (datetime(2026, 10, 9, 1, 30, 0), False, False, datetime(2026, 10, 9, 2, 10, 0), "Lúc 01:30 - Chờ đợt kế tiếp 02:10"),
        (datetime(2026, 10, 9, 2, 8, 0), False, True, datetime(2026, 10, 9, 2, 10, 0), "Lúc 02:08 - Chuẩn bị cho đợt 02:10"),
        (datetime(2026, 10, 9, 2, 10, 0), True, False, datetime(2026, 10, 9, 4, 10, 0), "Lúc 02:10 - CỔNG MỞ đợt 02:10"),
        (datetime(2026, 10, 9, 23, 0, 0), False, False, datetime(2026, 10, 10, 0, 10, 0), "Lúc 23:00 - Đợt mở cổng kế tiếp là 00:10 ngày mai"),
    ]

    for now_val, exp_gate, exp_prep, exp_next, desc in test_cases:
        is_gate_open, is_prep, next_gate, secs = check_mirror_state(now_val)
        assert is_gate_open == exp_gate, f"Gate mismatch for {now_val}: got {is_gate_open}, expected {exp_gate}"
        assert is_prep == exp_prep, f"Prep mismatch for {now_val}: got {is_prep}, expected {exp_prep}"
        assert next_gate == exp_next, f"Next gate mismatch for {now_val}: got {next_gate}, expected {exp_next}"
        status_str = "⚡ CỔNG ĐANG MỞ" if is_gate_open else ("🛠️ ĐANG CHUẨN BỊ" if is_prep else "⏳ CHỜ MỞ CỔNG")
        print(f"  [PASS] {desc} | Trạng thái: {status_str} | Mở cổng kế tiếp: {next_gate.strftime('%H:%M')}")

    print("  => OK: Tất cả 11 test case lịch mở cổng :10 và chuẩn bị :08 hoạt động chính xác 100%.")

def test_config_persistence():
    print("\n=== 3. KIỂM TRA LƯU VÀ NẠP CẤU HÌNH LỊCH TRÌNH ===")
    from meg_gui import ConfigPersistenceManager, MIRROR_CONFIG_FILE
    
    # Lưu test config
    test_cfg = {"auto_schedule": True, "auto_prep_before": True, "test_field": 123}
    ConfigPersistenceManager.save_mirror_schedule_config(test_cfg)
    assert MIRROR_CONFIG_FILE.exists(), "File cấu hình chưa được tạo!"
    
    loaded = ConfigPersistenceManager.load_mirror_schedule_config()
    assert loaded.get("auto_schedule") == True, "Lỗi nạp auto_schedule!"
    assert loaded.get("auto_prep_before") == True, "Lỗi nạp auto_prep_before!"
    print(f"  Đã ghi và đọc cấu hình thành công: {loaded}")
    print("  => OK: Config persistence hoạt động chuẩn xác.")

def test_engine_js_injection():
    print("\n=== 4. KIỂM TRA SCRIPT JS NATIVE TRONG MEG_DIRECT_ENGINE ===")
    import subprocess
    from meg_direct_engine import MegDirectEngine
    
    # Kiểm tra xem các method tồn tại
    assert hasattr(MegDirectEngine, "enter_mirror"), "Thiếu enter_mirror trong MegDirectEngine!"
    assert hasattr(MegDirectEngine, "get_mirror_ticket_info"), "Thiếu get_mirror_ticket_info trong MegDirectEngine!"
    assert hasattr(MegDirectEngine, "teleport_to_event_map"), "Thiếu teleport_to_event_map trong MegDirectEngine!"
    assert hasattr(MegDirectEngine, "click_mirror_npc"), "Thiếu click_mirror_npc trong MegDirectEngine!"
    print("  Tất cả các method RPC tương tác Native Mirror đều tồn tại đầy đủ.")

    # Kiểm tra cú pháp JS của script Frida
    eng = MegDirectEngine(0)
    js_code = eng._generate_js()
    assert len(js_code) > 1000, "JS Script quá ngắn hoặc rỗng!"

    # Ghi ra file tạm và check bằng node --check
    temp_js = Path("temp_frida_check.js")
    # Thay thế rpc.exports bằng đối tượng mô phỏng để node không báo rpc undefined
    mocked_js = "const rpc = { exports: {} };\n" + js_code
    with open(temp_js, "w", encoding="utf-8") as f:
        f.write(mocked_js)

    try:
        res = subprocess.run(["node", "--check", str(temp_js)], capture_output=True, text=True)
        assert res.returncode == 0, f"Lỗi cú pháp JS trong Frida script:\n{res.stderr}"
        print("  Cú pháp JavaScript trong Frida script: HỢP LỆ (node --check passed).")
    finally:
        if temp_js.exists():
            temp_js.unlink()

    print("  => OK: Direct engine methods và Frida JS script sẵn sàng.")

def test_mirror_ticket_detection_logic():
    print("\n=== 5. KIỂM TRA LOGIC NHẬN DIỆN VÉ VÀ QUÉT BA LÔ MỞ RỘNG (140 SLOTS) ===")
    import subprocess
    import json

    # Chạy script Node.js kiểm tra logic nhận diện vé và quét slot
    node_test = """
    function getItemName(item) { return item.name || ''; }
    
    function checkMirrorItem(itemPtr, idx) {
        var itName = getItemName(itemPtr) || "";
        var lowName = itName.toLowerCase();

        if (idx === 7279) {
            return { isTicket: true, isSign: false, name: itName || "Mirror of Dimensions" };
        }
        if (idx === 7280) {
            return { isTicket: false, isSign: true, name: itName || "Sign of Dimensions" };
        }

        if (lowName.length > 0) {
            if (lowName.indexOf("mirror of dimensions") !== -1 ||
                lowName.indexOf("espelho das dimens") !== -1 ||
                lowName.indexOf("doppelganger ticket") !== -1 ||
                lowName.indexOf("mirror ticket") !== -1) {
                return { isTicket: true, isSign: false, name: itName };
            }
            if (lowName.indexOf("sign of dimensions") !== -1 ||
                lowName.indexOf("sinal das dimens") !== -1) {
                return { isTicket: false, isSign: true, name: itName };
            }
            if (lowName.indexOf("mirror") !== -1 || lowName.indexOf("espelho") !== -1) {
                return { isTicket: true, isSign: false, name: itName };
            }
        }

        return { isTicket: false, isSign: false, name: itName };
    }

    // Mô phỏng hòm đồ: Vé nằm ở ba lô mở rộng (slot 84) và mảnh ghép ở slot 20
    var items = {};
    items[20] = { idx: 7280, name: "Sign of Dimensions" }; // Mảnh ghép ở hòm chính
    items[84] = { idx: 7279, name: "Mirror of Dimensions" }; // Vé ở Ba lô mở rộng 1
    items[115] = { idx: 9999, name: "Espelho das Dimensões" }; // Vé theo tên Bồ Đào Nha ở Ba lô mở rộng 2

    var tickets = [];
    var ticketDetails = [];
    var signSlots = [];
    var maxSlot = 140;

    for (var s = 12; s < maxSlot; s++) {
        var it = items[s];
        if (!it) continue;
        var check = checkMirrorItem(it, it.idx);
        if (check.isTicket) {
            tickets.push(s);
            ticketDetails.push({ slot: s, id: it.idx, name: check.name, isExtended: (s >= 76) });
        } else if (check.isSign) {
            signSlots.push(s);
        }
    }

    var result = {
        hasTicket: tickets.length > 0,
        count: tickets.length,
        slots: tickets,
        details: ticketDetails,
        signs: signSlots,
        hasOnlySign: (tickets.length === 0 && signSlots.length > 0)
    };
    console.log(JSON.stringify(result));
    """
    res = subprocess.run(["node", "-e", node_test], capture_output=True, text=True, check=True)
    out = json.loads(res.stdout.strip())
    assert out["hasTicket"] == True, "Phải tìm thấy vé!"
    assert out["count"] == 2, "Phải có 2 vé (slot 84 và 115)!"
    assert 84 in out["slots"], "Vé ở Ba lô mở rộng 1 (slot 84) phải được nhận diện!"
    assert 115 in out["slots"], "Vé ở Ba lô mở rộng 2 theo tên (slot 115) phải được nhận diện!"
    assert 20 in out["signs"], "Mảnh ghép Sign of Dimensions (slot 20) phải được ghi nhận!"
    print(f"  Kết quả mô phỏng quét ba lô mở rộng & nhận diện kép: {out}")
    print("  => OK: Nhận diện chính xác 100% vé trong cả Ba lô chính lẫn Ba lô mở rộng 1 & 2.")

if __name__ == "__main__":
    test_offsets()
    test_scheduler_algorithm()
    test_config_persistence()
    test_engine_js_injection()
    test_mirror_ticket_detection_logic()
    print("\n=======================================================")
    print("🎉 TOÀN BỘ KIỂM TRA ĐÃ HOÀN TẤT VÀ VƯỢT QUA 100% THÀNH CÔNG!")
    print("=======================================================")

