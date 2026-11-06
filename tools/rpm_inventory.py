"""Đọc inventory trực tiếp qua ReadProcessMemory (không inject, không ghi).

Dùng các con trỏ lấy được từ lần attach Frida trước đó; nếu con trỏ chết sẽ tự
dò lại theo chuỗi static field của GameAssembly.
"""
import ctypes
import ctypes.wintypes as wt
import sys

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 18456

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, PID)
if not h:
    print("OpenProcess failed:", ctypes.get_last_error())
    sys.exit(1)


def rd(addr, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    if not ok or n.value != size:
        return None
    return buf.raw


def u64(addr):
    b = rd(addr, 8)
    return int.from_bytes(b, "little") if b else None


def i32(addr):
    b = rd(addr, 4)
    return int.from_bytes(b, "little", signed=True) if b else None


def u8(addr):
    b = rd(addr, 1)
    return b[0] if b else None


def module_base(name="GameAssembly.dll"):
    """Lấy base module của process đích qua psapi (không cần inject)."""
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    arr = (wt.HMODULE * 1024)()
    needed = wt.DWORD(0)
    ok = psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(needed), 0x03)  # ALL
    if not ok:
        print("EnumProcessModulesEx failed:", ctypes.get_last_error())
        return None
    count = needed.value // ctypes.sizeof(wt.HMODULE)
    buf = ctypes.create_unicode_buffer(260)
    for i in range(count):
        if psapi.GetModuleBaseNameW(h, arr[i], buf, 260):
            if buf.value.lower() == name.lower():
                return arr[i]
    return None


base = module_base()
print(f"GameAssembly base = {hex(base) if base else None}")

# --- dò player qua static field (GameInstance) ---
TYPE_INFO_RVA = 0x553B900
PLAYER_INV = 0x1B0
INV_ITEMS = 0x28
PLAYER_COORD = 0x68

player = None
ti = u64(base + TYPE_INFO_RVA)
print(f"type_info ptr    = {hex(ti) if ti else None}")
if ti:
    static_fields = u64(ti + 0xB8)
    print(f"static fields    = {hex(static_fields) if static_fields else None}")
    if static_fields:
        game_inst = u64(static_fields + 0x8)
        print(f"game instance    = {hex(game_inst) if game_inst else None}")

# fallback: con trỏ lấy từ lần probe trước
CANDIDATE_PLAYER = 0x1D0C6026800
for cand in [CANDIDATE_PLAYER]:
    inv = u64(cand + PLAYER_INV)
    if inv:
        items = u64(inv + INV_ITEMS)
        if items:
            ln = i32(items + 0x18)
            if ln and 0 < ln < 500:
                player = cand
                break

if not player:
    print("Không dò được player ptr")
    sys.exit(2)

print(f"player           = {hex(player)}")
inv = u64(player + PLAYER_INV)
items = u64(inv + INV_ITEMS)
length = i32(items + 0x18)
coord = u64(player + PLAYER_COORD)
x = i32(coord + 0x10) if coord else None
y = i32(coord + 0x14) if coord else None
print(f"inventory        = {hex(inv)}")
print(f"items array      = {hex(items)}  len={length}")
print(f"coord            = ({x},{y})")

print("\nslot  lvl skill luck  exc anc sock harm   (12..{})".format(min(length, 140) - 1))
occupied = []
for s in range(12, min(length, 140)):
    it = u64(items + 0x20 + s * 8)
    if not it:
        continue
    lvl = i32(it + 0x10)
    sk = i32(it + 0x14)
    lk = i32(it + 0x18)
    exc = i32(it + 0x20)
    anc = i32(it + 0x24)
    sock = i32(it + 0x28)
    harm = i32(it + 0x2C)
    occupied.append(s)
    print(f"{s:>4} {lvl:>4} {sk:>5} {lk:>4} {exc:>4} {anc:>3} {sock:>4} {harm:>4}")

print(f"\nTổng: {len(occupied)} ô có đồ -> {occupied}")

# các ô 0..11 (trang bị) để đối chiếu
print("\nÔ 0..11:", [1 if u64(items + 0x20 + s * 8) else 0 for s in range(12)])
