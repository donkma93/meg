import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from meg_direct_engine import MegDirectEngine, DEFAULT_OFFSETS

print("=== KIỂM TRA ĐỒNG BỘ ICON HELPER TRÊN GIAO DIỆN GAME (MLOCATIONFRAME) ===")

# 1. Kiểm tra cấu hình offsets
with open("megamu_offsets.json", "r", encoding="utf-8") as f:
    root_cfg = json.load(f)

with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
    sub_cfg = json.load(f)

expected_keys = {
    "ui_location_frame": "0x80",
    "location_helper_on": "0x60",
    "location_helper_off": "0x68",
    "location_update_helper": "0x244C880",
    "helper_send_bf51": "0x26829C0",
    "helper_req_start": "0x26830F0",
    "helper_req_stop": "0x2683B80",
}

for k, v in expected_keys.items():
    assert root_cfg.get(k, "").lower() == v.lower(), f"megamu_offsets.json thiếu/sai {k}"
    assert sub_cfg.get(k, "").lower() == v.lower(), f"config/megamu_offsets.json thiếu/sai {k}"
    assert DEFAULT_OFFSETS.get(k, "").lower() == v.lower(), f"DEFAULT_OFFSETS thiếu/sai {k}"
    print(f"  [PASS] Offset {k:<25}: {v}")

# 2. Kiểm tra JS sinh ra
eng = MegDirectEngine(0)
js = eng._generate_js()
assert "function syncHelperUI(" in js, "Thiếu hàm syncHelperUI trong Frida JS!"
assert "nativeLocationFrameUpdate" in js, "Thiếu nativeLocationFrameUpdate trong Frida JS!"
assert "__LOCATION_HELPER_ON__" not in js, "Placeholder __LOCATION_HELPER_ON__ chưa được replace!"
assert "__LOCATION_HELPER_OFF__" not in js, "Placeholder __LOCATION_HELPER_OFF__ chưa được replace!"
assert "__UI_LOCATION_FRAME__" not in js, "Placeholder __UI_LOCATION_FRAME__ chưa được replace!"
assert "syncHelperUI: function(" in js, "Thiếu RPC export syncHelperUI!"
print("  [PASS] Frida script chứa toàn bộ logic syncHelperUI và RPC export!")

print("\n🎉 TOÀN BỘ KIỂM TRA ĐỒNG BỘ ICON HELPER THÀNH CÔNG 100%!")
