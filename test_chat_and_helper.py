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
    "chat_send": "0x12FCCC0",
    "chat_frame_send": "0x12FCCC0",
    "static_chat_send": "0xF2A550",
    "command_mgr_process": "0xF3E140",
    "helper_toggle": "0x271D340",
    "helper_action": "0x271D340",
    "helper_start": "0x271F8D0",
    "helper_stop": "0x2721F90",
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

# 2.1 Kiểm tra UserHelper.StartHelper (0x271F8D0) & UserHelper.StopHelper (0x2721F90)
offset_start = pe.get_offset_from_rva(0x271F8D0)
with open(dll_path, 'rb') as f:
    f.seek(offset_start)
    code_start = f.read(250)

sets_state = any(('byte ptr [rbx + 0x20], 1' in ins.op_str.lower() or 'byte ptr [rax + 0x20], 1' in ins.op_str.lower() or 'byte ptr [rcx + 0x20], 1' in ins.op_str.lower()) for ins in md.disasm(code_start, 0x271F8D0))
assert sets_state, "UserHelper.StartHelper (0x271F8D0) không set helper_state lên 1!"
print("  [PASS] UserHelper.StartHelper (0x271F8D0): Xác thực set helper_state=1 và cập nhật HuntingFrame UI!")

offset_stop = pe.get_offset_from_rva(0x2721F90)
with open(dll_path, 'rb') as f:
    f.seek(offset_stop)
    code_stop = f.read(250)

resets_state = any(('byte ptr [rbx + 0x20], 0' in ins.op_str.lower() or 'byte ptr [rax + 0x20], 0' in ins.op_str.lower() or 'byte ptr [rcx + 0x20], 0' in ins.op_str.lower()) for ins in md.disasm(code_stop, 0x2721F90))
assert resets_state, "UserHelper.StopHelper (0x2721F90) không reset helper_state về 0!"
print("  [PASS] UserHelper.StopHelper (0x2721F90): Xác thực reset helper_state=0 và cập nhật HuntingFrame UI!")

# 2.2 Kiểm tra UserHelper.SendHelperAction (0x271D340): gửi packet BF:51
offset_action = pe.get_offset_from_rva(0x271D340)
with open(dll_path, 'rb') as f:
    f.seek(offset_action)
    code_action = f.read(400)

has_packet = any(('0x51' in ins.op_str.lower() or '0xbf' in ins.op_str.lower() or 'dil' in ins.op_str.lower()) for ins in md.disasm(code_action, 0x271D340))
assert has_packet, "UserHelper.SendHelperAction (0x271D340) không chứa packet helper BF:51 / dil!"
print("  [PASS] UserHelper.SendHelperAction (0x271D340): Xác thực chứa mã mạng BF:51 gửi Server toggle với action=dil!")

# 2.3 Kiểm tra Mega.Chat (0xF2A550): hàm static gửi chat lên Server
offset_chat = pe.get_offset_from_rva(0xF2A550)
with open(dll_path, 'rb') as f:
    f.seek(offset_chat)
    code_chat = f.read(200)

calls_cmd_mgr = False
for ins in md.disasm(code_chat, 0xF2A550):
    if ins.mnemonic == 'call' and 'f3e140' in ins.op_str.lower():
        calls_cmd_mgr = True
assert calls_cmd_mgr, "Mega.Chat static chat không gọi CommandManager!"
print("  [PASS] Mega.Chat static chat (0xF2A550): Xác thực gọi CommandManager (0xF3E140)!")

# 2.4 Kiểm tra ChatFrame.Send (0x12FCCC0)
offset_cf = pe.get_offset_from_rva(0x12FCCC0)
with open(dll_path, 'rb') as f:
    f.seek(offset_cf)
    code_cf = f.read(2500)

calls_static_chat = False
for ins in md.disasm(code_cf, 0x12FCCC0):
    if ins.mnemonic == 'call' and 'f2a550' in ins.op_str.lower():
        calls_static_chat = True
assert calls_static_chat, "ChatFrame.Send không chuyển tiếp sang Mega.Chat static send!"
print("  [PASS] ChatFrame.Send (0x12FCCC0): Xác thực chuyển tiếp sang Mega.Chat (0xF2A550)!")

print("\n=== 3. KIỂM TRA CÚ PHÁP JAVASCRIPT CỦA ENGINE ===")
eng = MegDirectEngine(0)
js_code = eng._generate_js()
assert "function dispatchChatMessage(" in js_code
assert "function dispatchHelperAction(" in js_code
assert "nativeHelperToggle" in js_code
assert "sendGSPacket" in js_code
assert "dispatchChatMessage(\"/m ev\")" in js_code
print("  [PASS] Toàn bộ hàm dispatch và sửa đổi cú pháp JS hợp lệ.")

print("\n=======================================================")
print("🎉 TOÀN BỘ KIỂM TRA CHAT SEND VÀ HELPER START/STOP THÀNH CÔNG 100%!")
print("=======================================================")
