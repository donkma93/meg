"""Đối chiếu offset trong config/megamu_offsets.json với dump.cs và GameAssembly.dll.

Mục đích: phát hiện "offset chết" sau mỗi lần game update — nguyên nhân số 1 khiến
các tính năng native (Moss open/close, drop, sell...) im lặng không hoạt động.

Cách dùng:
    python tools/verify_offsets.py                    # chỉ so với dump.cs
    python tools/verify_offsets.py --dll              # thêm kiểm tra prologue trên DLL
    python tools/verify_offsets.py --dll --dump dump_current/dump.cs

Kết quả: bảng trạng thái + exit code 1 nếu có offset không tồn tại trong dump hiện tại.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Các offset không phải RVA hàm (field offset) nên không tra trong dump.cs.
FIELD_KEYS = {
    "game_module", "player_point", "player_master_point", "player_reset_count",
    "player_name", "player_level", "player_class", "player_coord", "player_move",
    "player_inventory", "player_helper", "player_last_coord", "auto_move_working",
    "auto_move_type", "auto_move_helper", "auto_move_dest", "move_flag",
    "helper_state", "inventory_items", "game_world", "world_scene_index",
    "viewport", "ui_chat_frame", "ui_moss_window", "ui_merchant_window",
    "ui_inventory_window", "ui_warehouse_window", "ui_gremory_window",
    "gremory_instance_offset", "gremory_dict_offset",
    "item_mirror_ticket", "item_devil_ticket", "item_devil_ticket_master",
    "ui_location_frame", "location_helper_on", "location_helper_off",
}


def load_dump_rvas(path: Path) -> set[str]:
    rvas: set[str] = set()
    rx = re.compile(r"// RVA: (0x[0-9A-Fa-f]+)")
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.search(line)
            if m:
                rvas.add(m.group(1).upper())
    return rvas


def dll_reader(dll: Path):
    """Trả về (pdata_starts, hàm kiểm tra 'địa chỉ này có phải đầu hàm')."""
    import pefile

    pe = pefile.PE(str(dll), fast_load=True)
    secs = [(s.VirtualAddress, max(s.Misc_VirtualSize, s.SizeOfRawData), s.PointerToRawData)
            for s in pe.sections]
    raw = dll.read_bytes()
    starts: set[int] = set()
    for sec in pe.sections:
        if sec.Name.rstrip(b"\x00") == b".pdata":
            data = pe.get_data(sec.VirtualAddress, sec.Misc_VirtualSize)
            for i in range(0, len(data) - 12 + 1, 12):
                begin, end = (int.from_bytes(data[i:i + 4], "little"),
                              int.from_bytes(data[i + 4:i + 8], "little"))
                if begin and end > begin:
                    starts.add(begin)

    def rva2off(rva: int):
        for va, sz, pr in secs:
            if va <= rva < va + sz:
                return pr + (rva - va)
        return None

    def is_func_start(rva: int) -> bool:
        if rva in starts:
            return True
        off = rva2off(rva)
        if off is None or off < 8:
            return False
        prev = raw[max(0, off - 8):off]
        # Hàm lá không có unwind info: phía trước là padding CC/90/00
        return all(b in (0xCC, 0x90, 0x00) for b in prev) and any(b == 0xCC for b in prev)

    return starts, is_func_start


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(ROOT / "dump_current" / "dump.cs"))
    ap.add_argument("--config", default=str(ROOT / "config" / "megamu_offsets.json"))
    ap.add_argument("--dll", nargs="?", const=r"C:\Users\donpv\AppData\Local\Programs\MEGAMU\bin\GameAssembly.dll",
                    default=None)
    args = ap.parse_args()

    dump_path = Path(args.dump)
    cfg_path = Path(args.config)
    if not dump_path.exists():
        print(f"[!] Không thấy dump: {dump_path}")
        return 2
    if not cfg_path.exists():
        print(f"[!] Không thấy config: {cfg_path}")
        return 2

    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    dump_rvas = load_dump_rvas(dump_path)
    starts = None
    is_func_start = None
    if args.dll:
        dll = Path(args.dll)
        if not dll.exists():
            print(f"[!] Không thấy DLL: {dll}")
        else:
            starts, is_func_start = dll_reader(dll)
            print(f"[i] DLL: {dll}  ({len(starts)} hàm có unwind info)")

    ok, missing, warn, skipped = [], [], [], []
    for key, val in cfg.items():
        if key in FIELD_KEYS or key.endswith("_type_info"):
            skipped.append((key, val))
            continue
        if not isinstance(val, str) or not val.lower().startswith("0x"):
            skipped.append((key, val))
            continue
        if int(val, 16) == 0:
            skipped.append((key, "0x0 (đã tắt)"))
            continue
        rva = val.upper()
        in_dump = rva in dump_rvas
        in_dll = None if is_func_start is None else is_func_start(int(rva, 16))
        if in_dump and (in_dll is None or in_dll):
            ok.append((key, val))
        elif in_dump and in_dll is False:
            # Có trong dump nhưng không nhận diện được đầu hàm (hàm lá / hàm engine)
            warn.append((key, val))
        elif in_dll and not in_dump:
            # Hàm runtime IL2CPP, không nằm trong metadata
            warn.append((key, val))
        else:
            missing.append((key, val, in_dump, in_dll))

    print(f"\n[OK]   {len(ok)} offset khớp build hiện tại")
    print(f"[--]   {len(skipped)} key là field/offset dữ liệu hoặc đã tắt (bỏ qua)")
    if warn:
        print(f"[??]   {len(warn)} offset cần xem tay (không kết luận được): "
              + ", ".join(k for k, _ in warn))
    if missing:
        print(f"\n[FAIL] {len(missing)} offset KHÔNG khớp — cần map lại:")
        print(f"    {'key':<28}{'RVA':<14}{'trong dump':<12}{'đầu hàm DLL'}")
        for key, val, in_dump, in_pdata in missing:
            print(f"    {key:<28}{val:<14}{str(in_dump):<12}{str(in_pdata)}")
        print("\nGợi ý: tìm hàm tương ứng trong dump mới (theo field/offset mà nó thao tác),"
              "\nrồi cập nhật ĐỒNG THỜI megamu_offsets.json, config/megamu_offsets.json và DEFAULT_OFFSETS.")
        return 1

    print("\nTất cả offset hàm đều khớp build hiện tại.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
