import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from meg_direct_engine import DEFAULT_OFFSETS

print("=== 1. KIỂM TRA TỆP CẤU HÌNH OFFSETS JSON VÀ DEFAULT_OFFSETS ===")
with open("megamu_offsets.json", "r", encoding="utf-8") as f:
    root_cfg = json.load(f)

with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
    sub_cfg = json.load(f)

exp_val = "0x22317E0"
assert root_cfg.get("item_storage_move", "").lower() == exp_val.lower(), f"megamu_offsets.json: {root_cfg.get('item_storage_move')} != {exp_val}"
assert sub_cfg.get("item_storage_move", "").lower() == exp_val.lower(), f"config/megamu_offsets.json: {sub_cfg.get('item_storage_move')} != {exp_val}"
assert DEFAULT_OFFSETS.get("item_storage_move", "").lower() == exp_val.lower(), f"DEFAULT_OFFSETS: {DEFAULT_OFFSETS.get('item_storage_move')} != {exp_val}"
print(f"  [PASS] item_storage_move: {exp_val} được đồng bộ nhất quán 100%!")

print("\n=== 2. KIỂM TRA ĐẶC TẢ VÀ DISASSEMBLY TRONG GAMEASSEMBLY.DLL ===")
dll_path = r'C:\Users\donpv\AppData\Local\Programs\MEGAMU\bin\GameAssembly.dll'
pe = pefile.PE(dll_path, fast_load=True)
md = Cs(CS_ARCH_X86, CS_MODE_64)

# 2.1 Kiểm tra ItemStorage.BGGOOIDBJIO (0x22317E0)
offset_move = pe.get_offset_from_rva(0x22317E0)
with open(dll_path, 'rb') as f:
    f.seek(offset_move)
    code_move = f.read(300)

dis_move = list(md.disasm(code_move, 0x1822317E0))
assert len(dis_move) > 0, "Không thể disassemble hàm 0x22317E0"
assert dis_move[0].mnemonic == 'mov' and 'rsp' in dis_move[0].op_str, "Hàm 0x22317E0 không có prologue chuẩn"

# Verify calls BAHMCKPHLBL (0x1448550)
calls_send = any('1448550' in ins.op_str.lower() for ins in dis_move)
assert calls_send, "ItemStorage.BGGOOIDBJIO (0x22317E0) không gọi UserInventory.BAHMCKPHLBL (0x1448550)!"
print("  [PASS] ItemStorage.BGGOOIDBJIO (0x22317E0): Xác thực gọi hàm gửi packet 0x24 (0x1448550)!")

# 2.2 Kiểm tra UserInventory.BAHMCKPHLBL (0x1448550)
offset_send = pe.get_offset_from_rva(0x1448550)
with open(dll_path, 'rb') as f:
    f.seek(offset_send)
    code_send = f.read(400)

dis_send = list(md.disasm(code_send, 0x181448550))
has_opcode_24 = any(('0x24' in ins.op_str.lower()) for ins in dis_send)
assert has_opcode_24, "UserInventory.BAHMCKPHLBL không chứa opcode packet 0x24!"
print("  [PASS] UserInventory.BAHMCKPHLBL (0x1448550): Xác thực khởi tạo opcode 0x24 cho Item Move/Stack!")

print("\n🎉 TOÀN BỘ KIỂM TRA GOM NGỌC (ITEM STORAGE MOVE & PACKET 0x24) THÀNH CÔNG 100%!")

