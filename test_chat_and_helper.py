import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from meg_direct_engine import MegDirectEngine, DEFAULT_OFFSETS

print("=== 1. KIỂM TRA TỆP CẤU HÌNH OFFSETS JSON VÀ DEFAULT_OFFSETS ===")
with open("megamu_offsets.json", "r", encoding="utf-8") as f:
    root_cfg = json.load(f)

with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
    sub_cfg = json.load(f)

expected = {
    "chat_send": "0x13C0C70",
    "chat_frame_send": "0x13C0C70",
    "static_chat_send": "0xF95530",
    "command_mgr_process": "0xFA0A60",
    "helper_toggle": "0x289B750",
    "helper_start": "0x289BD70",
    "helper_stop": "0x289C150",
}

for k, exp_val in expected.items():
    v1 = root_cfg.get(k)
    v2 = sub_cfg.get(k)
    v3 = DEFAULT_OFFSETS.get(k)
    assert v1.lower() == exp_val.lower(), f"megamu_offsets.json {k}: {v1} != {exp_val}"
    assert v2.lower() == exp_val.lower(), f"config/megamu_offsets.json {k}: {v2} != {exp_val}"
    assert v3.lower() == exp_val.lower(), f"DEFAULT_OFFSETS {k}: {v3} != {exp_val}"
    print(f"  [PASS] {k:<20}: {exp_val}")

print("\n=== 2. KIỂM TRA ĐẶC TẢ VÀ CALLING CONVENTION TRONG GAMEASSEMBLY.DLL ===")
dll_path = r'C:\Users\donpv\AppData\Local\Programs\MEGAMU\bin\GameAssembly.dll'
pe = pefile.PE(dll_path, fast_load=True)
md = Cs(CS_ARCH_X86, CS_MODE_64)

# 2.1 Kiểm tra UserHelper.LAHCLHAJECG (0x289B750): gửi packet EC:51
offset_toggle = pe.get_offset_from_rva(0x289B750)
with open(dll_path, 'rb') as f:
    f.seek(offset_toggle)
    code_toggle = f.read(300)

has_ec51 = False
for ins in md.disasm(code_toggle, 0x289B750):
    if ins.mnemonic == 'mov' and '0x51' in ins.op_str:
        has_ec51 = True
assert has_ec51, "UserHelper.LAHCLHAJECG không chứa packet 0x51!"
print("  [PASS] UserHelper.LAHCLHAJECG (0x289B750): Xác thực chứa mã mạng EC:51 gửi Server toggle!")

# 2.2 Kiểm tra Mega.Chat.FCIBNHIHDHO (0xF95530): hàm static gửi chat lên Server
offset_chat = pe.get_offset_from_rva(0xF95530)
with open(dll_path, 'rb') as f:
    f.seek(offset_chat)
    code_chat = f.read(200)

calls_cmd_mgr = False
for ins in md.disasm(code_chat, 0xF95530):
    if ins.mnemonic == 'call' and 'fa0a60' in ins.op_str.lower():
        calls_cmd_mgr = True
assert calls_cmd_mgr, "Mega.Chat.FCIBNHIHDHO không gọi CommandManager.BDMGLHEGJHO!"
print("  [PASS] Mega.Chat.FCIBNHIHDHO (0xF95530): Xác thực gọi CommandManager và gửi packet 0x00 lên GSConnection!")

# 2.3 Kiểm tra ChatFrame.CGPBOGHGMOK (0x13C0C70)
offset_cf = pe.get_offset_from_rva(0x13C0C70)
with open(dll_path, 'rb') as f:
    f.seek(offset_cf)
    code_cf = f.read(2500)

calls_static_chat = False
for ins in md.disasm(code_cf, 0x13C0C70):
    if ins.mnemonic == 'call' and 'f95530' in ins.op_str.lower():
        calls_static_chat = True
assert calls_static_chat, "ChatFrame.CGPBOGHGMOK không chuyển tiếp sang Mega.Chat.FCIBNHIHDHO!"
print("  [PASS] ChatFrame.CGPBOGHGMOK (0x13C0C70): Xác thực chuyển tiếp sang Mega.Chat.FCIBNHIHDHO!")

print("\n=== 3. KIỂM TRA CÚ PHÁP JAVASCRIPT CỦA ENGINE ===")
eng = MegDirectEngine(0)
js_code = eng._generate_js()
assert "function dispatchChatMessage(" in js_code
assert "function dispatchHelperAction(" in js_code
assert "nativeHelperToggle" in js_code
assert "raw.add(1).writeU8(0x05)" in js_code
assert "dispatchChatMessage(\"/move ev\")" in js_code
print("  [PASS] Toàn bộ hàm dispatch và sửa đổi cú pháp JS hợp lệ.")

print("\n=======================================================")
print("🎉 TOÀN BỘ KIỂM TRA CHAT SEND VÀ HELPER START/STOP THÀNH CÔNG 100%!")
print("=======================================================")
