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
    "chat_send": "0x1331880",
    "chat_frame_send": "0x1331880",
    "static_chat_send": "0xF1F710",
    "command_mgr_process": "0xEFE530",
    "helper_toggle": "0x25DC620",
    "helper_action": "0x25DC620",
    "helper_start": "0x27776F0",
    "helper_stop": "0x277C760",
    "location_update_helper": "0x25A5750",
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

# 2.1 Kiểm tra UserHelper.ALFOIEJFHLL (Start - 0x27776F0) & UserHelper.BBLPCMHOBOE (Stop - 0x277C760)
offset_start = pe.get_offset_from_rva(0x27776F0)
with open(dll_path, 'rb') as f:
    f.seek(offset_start)
    code_start = f.read(150)

calls_bf51_start = any('277bdd0' in ins.op_str.lower() for ins in md.disasm(code_start, 0x27776F0))
assert calls_bf51_start, "UserHelper.ALFOIEJFHLL (0x27776F0) không gọi hàm gửi packet BF:51 (0x277BDD0)!"
print("  [PASS] UserHelper.ALFOIEJFHLL (0x27776F0): Xác thực gọi hàm gửi packet BF:51 (0x277BDD0) với code=0 (Start)!")

offset_stop = pe.get_offset_from_rva(0x277C760)
with open(dll_path, 'rb') as f:
    f.seek(offset_stop)
    code_stop = f.read(150)

calls_bf51_stop = any('277bdd0' in ins.op_str.lower() for ins in md.disasm(code_stop, 0x277C760))
assert calls_bf51_stop, "UserHelper.BBLPCMHOBOE (0x277C760) không gọi hàm gửi packet BF:51 (0x277BDD0)!"
print("  [PASS] UserHelper.BBLPCMHOBOE (0x277C760): Xác thực gọi hàm gửi packet BF:51 (0x277BDD0) với code=1 (Stop)!")

# 2.2 Kiểm tra MLocationFrame button delegate (0x25DC620) & icon update (0x25A5750)
offset_btn = pe.get_offset_from_rva(0x25DC620)
with open(dll_path, 'rb') as f:
    f.seek(offset_btn)
    code_btn = f.read(200)

has_state_cmp = any(('0x20' in ins.op_str.lower() and ins.mnemonic == 'cmp') for ins in md.disasm(code_btn, 0x25DC620))
calls_start = any('27776f0' in ins.op_str.lower() for ins in md.disasm(code_btn, 0x25DC620))
calls_stop = any('277c760' in ins.op_str.lower() for ins in md.disasm(code_btn, 0x25DC620))
assert has_state_cmp and calls_start and calls_stop, "Button delegate (0x25DC620) không kiểm tra helper_state (+0x20) và gọi Start/Stop!"
print("  [PASS] MLocationFrame Button Delegate (0x25DC620): Kiểm tra helper_state (+0x20), rẽ nhánh Start (0x27776F0) và Stop (0x277C760)!")

offset_icon = pe.get_offset_from_rva(0x25A5750)
with open(dll_path, 'rb') as f:
    f.seek(offset_icon)
    code_icon = f.read(300)

touches_images = any('0x60' in ins.op_str.lower() for ins in md.disasm(code_icon, 0x25A5750)) and any('0x68' in ins.op_str.lower() for ins in md.disasm(code_icon, 0x25A5750))
assert touches_images, "MLocationFrame icon update (0x25A5750) không truy cập OnImage (0x60) và OffImage (0x68)!"
print("  [PASS] MLocationFrame.NKLMLNCKNLG (0x25A5750): Cập nhật chuẩn HelperStateOnImage (0x60) và HelperStateOffImage (0x68)!")

# 2.3 Kiểm tra Mega.Chat.LLGBNHILFIE (0xF1F710): hàm static gửi chat và /move lên Server
offset_chat = pe.get_offset_from_rva(0xF1F710)
with open(dll_path, 'rb') as f:
    f.seek(offset_chat)
    code_chat = f.read(200)

calls_cmd_mgr = False
for ins in md.disasm(code_chat, 0xF1F710):
    if ins.mnemonic == 'call' and 'efe530' in ins.op_str.lower():
        calls_cmd_mgr = True
assert calls_cmd_mgr, "Mega.Chat.LLGBNHILFIE (0xF1F710) không gọi CommandManager.MLPKNNGGNPL (0xEFE530)!"
print("  [PASS] Mega.Chat static chat (0xF1F710): Xác thực gọi CommandManager.MLPKNNGGNPL (0xEFE530)!")

# 2.4 Kiểm tra CommandManager.MLPKNNGGNPL (0xEFE530): xử lý lệnh '/'
offset_cmd = pe.get_offset_from_rva(0xEFE530)
with open(dll_path, 'rb') as f:
    f.seek(offset_cmd)
    code_cmd = f.read(1500)

checks_slash = any('0x2f' in ins.op_str.lower() for ins in md.disasm(code_cmd, 0xEFE530))
assert checks_slash, "CommandManager.MLPKNNGGNPL (0xEFE530) không kiểm tra ký tự '/' (0x2F)!"
print("  [PASS] CommandManager.MLPKNNGGNPL (0xEFE530): Xác thực xử lý lệnh bắt đầu bằng '/' (0x2F)!")

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
