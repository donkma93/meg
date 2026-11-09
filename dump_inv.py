import sys
import ctypes
from ctypes import wintypes
import psutil

pid = 27244
print(f"Dumping inventory for PID {pid}...")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

h_proc = k32.OpenProcess(0x0410, False, int(pid))
if not h_proc:
    print(f"Failed to open process {pid}")
    sys.exit(1)

# Find GameAssembly.dll
ga_base = 0
proc = psutil.Process(int(pid))
for m in proc.memory_maps(grouped=False):
    if m.path and "gameassembly.dll" in m.path.lower():
        ga_base = int(m.addr.split('-')[0], 16)
        break

print(f"GameAssembly base: {hex(ga_base)}")

def _to_addr(addr: int):
    if addr is None or addr <= 0:
        return ctypes.c_void_p(0)
    if addr >= 0x8000000000000000:
        return ctypes.c_void_p(addr - 0x10000000000000000)
    return ctypes.c_void_p(addr)

def _rd(addr: int, size: int):
    if not addr or addr < 0x10000:
        return None
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h_proc, _to_addr(addr), buf, size, ctypes.byref(n))
    if not ok or n.value != size:
        return None
    return buf.raw

def _u64(addr: int) -> int:
    b = _rd(addr, 8)
    return int.from_bytes(b, "little") if b else 0

def _i32(addr: int) -> int:
    b = _rd(addr, 4)
    return int.from_bytes(b, "little", signed=True) if b else 0

def _u8(addr: int) -> int:
    b = _rd(addr, 1)
    return b[0] if b else 0

def _il2cpp_str(addr: int) -> str:
    if not addr or addr < 0x10000:
        return ""
    ln = _i32(addr + 0x10)
    if ln <= 0 or ln > 300:
        return ""
    raw = _rd(addr + 0x14, ln * 2)
    if not raw:
        return ""
    return raw.decode("utf-16le", errors="ignore").strip()

ti = _u64(ga_base + 0x553B900)
sf = _u64(ti + 0xB8)
gi = _u64(sf + 0x08)
player = _u64(gi + 0x208)
p_name = _il2cpp_str(_u64(player + 0x28))
p_lvl = _i32(player + 0x30)
p_cls = _i32(player + 0x34)
print(f"Player: {p_name}, Lvl: {p_lvl}, Class: {p_cls}")

inv = _u64(player + 0x1B0)
items_arr = _u64(inv + 0x28)
arr_len = _i32(items_arr + 0x18)
print(f"Items array len: {arr_len}")

results = []
for s in range(12, min(arr_len, 240)):
    it = _u64(items_arr + 0x20 + s * 8)
    if not it:
        continue
    id60 = _i32(it + 0x60)
    te = _u64(it + 0x58)
    te10 = _i32(te + 0x10) if te else -1
    it_lvl = _i32(it + 0x10)
    dur = _u8(it + 0x64)
    
    # scan strings
    strs = []
    if te:
        for off in range(0x18, 0x140, 8):
            st = _il2cpp_str(_u64(te + off))
            if st:
                strs.append(f"+{hex(off)}: {st}")
        # scan dict
        dict_ptr = _u64(te + 0x120)
        if dict_ptr:
            ent = _u64(dict_ptr + 0x18)
            cnt = _i32(dict_ptr + 0x20)
            if ent and 0 < cnt < 50:
                for di in range(min(cnt, 20)):
                    vp = _u64(ent + 0x20 + di * 24 + 16)
                    if vp:
                        sd = _il2cpp_str(vp)
                        if sd: strs.append(f"dict[{di}]: {sd}")
                        for fo in (0x10, 0x18, 0x20, 0x28, 0x30):
                            ss = _il2cpp_str(_u64(vp + fo))
                            if ss: strs.append(f"dict[{di}]+{hex(fo)}: {ss}")

    line = f"Slot {s}: itPtr={hex(it)}, id60={id60}, te10={te10}, lvl={it_lvl}, dur={dur}, strings={strs}"
    print(line)
    results.append(line)

with open("c:\\Users\\donpv\\Desktop\\meg\\dump_inv_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

k32.CloseHandle(h_proc)
print("Done!")

