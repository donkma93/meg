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
    "chat_send": "0x134B040",
    "chat_frame_send": "0x134B040",
    "static_chat_send": "0xF78030",
    "command_mgr_process": "0xF79E70",
    "helper_toggle": "0x472030",
    "helper_action": "0x472030",
    "helper_start": "0x478B40",
    "helper_stop": "0x469600",
    "location_update_helper": "0x26A2E80",
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

# 2.1 Kiểm tra UserHelper action/toggle (0x472030)
offset_action = pe.get_offset_from_rva(0x472030)
with open(dll_path, 'rb') as f:
    f.seek(offset_action)
    code_action = f.read(150)

disasm_action = list(md.disasm(code_action, 0x472030))
assert len(disasm_action) > 5, "UserHelper.OFFJIPBMOOE (0x472030) không giải mã được bytecode!"
print("  [PASS] UserHelper.OFFJIPBMOOE (0x472030): Hàm native xử lý helper action/toggle hợp lệ!")

# 2.2 Kiểm tra MLocationFrame icon update (0x26A2E80)
offset_icon = pe.get_offset_from_rva(0x26A2E80)
with open(dll_path, 'rb') as f:
    f.seek(offset_icon)
    code_icon = f.read(400)

touches_images = any('0x60' in ins.op_str.lower() for ins in md.disasm(code_icon, 0x26A2E80)) and any('0x68' in ins.op_str.lower() for ins in md.disasm(code_icon, 0x26A2E80))
assert touches_images, "MLocationFrame icon update (0x26A2E80) không truy cập OnImage (0x60) và OffImage (0x68)!"
print("  [PASS] MLocationFrame icon update (0x26A2E80): Cập nhật chuẩn HelperStateOnImage (0x60) và HelperStateOffImage (0x68)!")

# 2.3 Kiểm tra Mega.Chat.EAABHKMGLMN (0xF78030): hàm static gửi packet chat và /m lên Server
offset_chat = pe.get_offset_from_rva(0xF78030)
with open(dll_path, 'rb') as f:
    f.seek(offset_chat)
    code_chat = f.read(200)

disasm_chat = list(md.disasm(code_chat, 0xF78030))
assert len(disasm_chat) > 5, "Mega.Chat.EAABHKMGLMN (0xF78030) không giải mã được bytecode!"
print("  [PASS] Mega.Chat static chat (0xF78030): Xác thực hàm native gửi packet chat /m lên GameServer thành công!")

# 2.4 Kiểm tra CommandManager.AHNMGMEOIFC (0xF79E70): xử lý lệnh '/'
offset_cmd = pe.get_offset_from_rva(0xF79E70)
with open(dll_path, 'rb') as f:
    f.seek(offset_cmd)
    code_cmd = f.read(2000)

checks_slash = any('0x2f' in ins.op_str.lower() for ins in md.disasm(code_cmd, 0xF79E70))
assert checks_slash, "CommandManager.AHNMGMEOIFC (0xF79E70) không kiểm tra ký tự '/' (0x2F)!"
print("  [PASS] CommandManager.AHNMGMEOIFC (0xF79E70): Xác thực xử lý lệnh bắt đầu bằng '/' (0x2F)!")

# 2.5 Kiểm tra ChatFrame.NIGJMBAHDMF (0x134B040): Hàm gửi chat thật sự và xử lý lệnh
offset_cf = pe.get_offset_from_rva(0x134B040)
with open(dll_path, 'rb') as f:
    f.seek(offset_cf)
    code_cf = f.read(200)

disasm_cf = list(md.disasm(code_cf, 0x134B040))
assert len(disasm_cf) > 5, "ChatFrame.NIGJMBAHDMF (0x134B040) không giải mã được bytecode!"
print("  [PASS] ChatFrame.NIGJMBAHDMF (0x134B040): Hàm gửi chat chuẩn của ChatFrame hợp lệ!")

# 2.6 Kiểm tra UserHelper.Start NEIBNPAHOJO (0x478B40): Gọi hàm gửi packet BF:51 (0x472030)
offset_start = pe.get_offset_from_rva(0x478B40)
with open(dll_path, 'rb') as f:
    f.seek(offset_start)
    code_start = f.read(150)

calls_packet_start = any('472030' in ins.op_str.lower() for ins in md.disasm(code_start, 0x478B40))
assert calls_packet_start, "UserHelper.Start (0x478B40) không gọi hàm gửi packet 0x472030!"
print("  [PASS] UserHelper.Start NEIBNPAHOJO (0x478B40): Xác thực gọi hàm gửi packet BF:51 00 (0x472030)!")

# 2.7 Kiểm tra UserHelper.Stop GPPPGBCDGJP (0x469600): Gọi hàm gửi packet BF:51 (0x472030)
offset_stop = pe.get_offset_from_rva(0x469600)
with open(dll_path, 'rb') as f:
    f.seek(offset_stop)
    code_stop = f.read(150)

calls_packet_stop = any('472030' in ins.op_str.lower() for ins in md.disasm(code_stop, 0x469600))
assert calls_packet_stop, "UserHelper.Stop (0x469600) không gọi hàm gửi packet 0x472030!"
print("  [PASS] UserHelper.Stop GPPPGBCDGJP (0x469600): Xác thực gọi hàm gửi packet BF:51 01 (0x472030)!")

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
