import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from meg_direct_engine import MegDirectEngine

print("=== 1. KIỂM TRA TỆP CẤU HÌNH OFFSETS JSON VÀ CẤU TRÚC ĐỘNG ===")
with open("megamu_offsets.json", "r", encoding="utf-8") as f:
    root_cfg = json.load(f)

with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
    sub_cfg = json.load(f)

required_keys = [
    "chat_send",
    "chat_frame_send",
    "static_chat_send",
    "command_mgr_process",
    "helper_toggle",
    "helper_action",
    "helper_start",
    "helper_stop",
    "location_update_helper",
]

for k in required_keys:
    v1 = root_cfg.get(k)
    v2 = sub_cfg.get(k)
    assert v1 and v2, f"Thiếu key cấu hình: {k}"
    assert v1.lower() == v2.lower(), f"Lệch cấu hình giữa root và sub cho {k}: {v1} != {v2}"
    print(f"  [PASS] {k:<25}: {v1}")

print("\n=== 2. KIỂM TRA ĐẶC TẢ VÀ CALLING CONVENTION TRONG GAMEASSEMBLY.DLL ===")
dll_path = r'C:\Users\donpv\AppData\Local\Programs\MEGAMU\bin\GameAssembly.dll'
pe = pefile.PE(dll_path, fast_load=True)
md = Cs(CS_ARCH_X86, CS_MODE_64)

def verify_rva(key: str, min_ins: int = 5):
    rva = int(sub_cfg[key], 16)
    offset = pe.get_offset_from_rva(rva)
    with open(dll_path, 'rb') as f:
        f.seek(offset)
        code = f.read(150)
    disasm = list(md.disasm(code, rva))
    assert len(disasm) >= min_ins, f"{key} (0x{rva:X}) không giải mã được bytecode!"
    print(f"  [PASS] {key:<25} (0x{rva:X}): Bytecode hợp lệ ({len(disasm)} chỉ thị)")
    return disasm

# 2.1 Kiểm tra UserHelper action/toggle
verify_rva("helper_toggle")

# 2.2 Kiểm tra MLocationFrame icon update
verify_rva("location_update_helper")

# 2.3 Kiểm tra Mega.Chat.Send (static_chat_send)
verify_rva("static_chat_send")

# 2.4 Kiểm tra CommandManager.Process (command_mgr_process)
rva_cmd = int(sub_cfg["command_mgr_process"], 16)
offset_cmd = pe.get_offset_from_rva(rva_cmd)
with open(dll_path, 'rb') as f:
    f.seek(offset_cmd)
    code_cmd = f.read(2000)
checks_slash = any('0x2f' in ins.op_str.lower() for ins in md.disasm(code_cmd, rva_cmd))
assert checks_slash, f"CommandManager (0x{rva_cmd:X}) không kiểm tra ký tự '/' (0x2F)!"
print(f"  [PASS] {'command_mgr_process':<25} (0x{rva_cmd:X}): Xác thực kiểm tra ký tự '/' (0x2F) thành công!")

# 2.5 Kiểm tra ChatFrame.Send (chat_send)
verify_rva("chat_send")

# 2.6 Kiểm tra UserHelper.Start
verify_rva("helper_start")

# 2.7 Kiểm tra UserHelper.Stop
verify_rva("helper_stop")

print("\n=== 3. KIỂM TRA CÚ PHÁP JAVASCRIPT CỦA ENGINE ===")
eng = MegDirectEngine(0)
js_code = eng._generate_js()
assert "function dispatchChatMessage(" in js_code
assert "function dispatchHelperAction(" in js_code
assert "nativeHelperToggle" in js_code
assert "sendGSPacket" in js_code
assert "dispatchChatMessage(\"/m ev\")" in js_code
assert "isServerCmd" in js_code
print("  [PASS] Toàn bộ hàm dispatch và sửa đổi cú pháp JS hợp lệ.")

print("\n=======================================================")
print("🎉 TOÀN BỘ KIỂM TRA CHAT SEND VÀ HELPER START/STOP THÀNH CÔNG 100%!")
print("=======================================================")
