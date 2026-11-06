"""Báo cáo nhanh: vì sao "Ném đồ" không dọn được món nào.

Chạy khi game MEGAMU đang mở (không cần mở dashboard):

    python tools/moss_junk_report.py            # dùng mức mặc định +6
    python tools/moss_junk_report.py --max-level 9
    python tools/moss_junk_report.py --ignore-type

Script chỉ ĐỌC hòm đồ và in lý do từng món bị giữ — không gửi packet, không xóa gì.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REASON_VI = {
    "divine_or_dragon": "bị lọc theo TÊN/LOẠI (Divine/Rồng/keyword)",
    "excellent": "đồ Hoàn Hảo (Exc)",
    "ancient": "đồ Thần/Set",
    "socket": "đồ Socket/380",
    "harmony": "đồ Harmony",
    "level_over_max": "cấp + vượt ngưỡng",
    "jewel_section": "ngọc/vé/cánh (sec 12-15)",
    "wrong_moss_category": "khác danh mục Moss đang quay",
    "preexisting_snapshot": "đã có trước khi quay",
    "unknown_item": "không đọc được item index",
}


def find_pid() -> int | None:
    import psutil

    for p in psutil.process_iter(["pid", "name"]):
        try:
            if "MEGAMU" in (p.info["name"] or "").upper():
                return p.info["pid"]
        except Exception:
            continue
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--max-level", type=int, default=6)
    ap.add_argument("--ignore-type", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="chỉ in N món dọn được đầu tiên (0 = tất cả)")
    args = ap.parse_args()

    pid = args.pid or find_pid()
    if not pid:
        print("❌ Không tìm thấy tiến trình MEGAMU. Hãy mở game trước.")
        return 2

    print(f"[i] Kết nối PID {pid} ...")
    from meg_direct_engine import MegDirectEngine

    eng = MegDirectEngine.get_engine(pid)
    if not eng.is_ready and not eng.attach():
        print("❌ Không attach được vào game (Frida).")
        return 1

    res = eng.analyze_junk_inventory(
        category=-1,
        max_junk_level=args.max_level,
        protected_slots=[],
        ignore_type_heuristics=args.ignore_type,
    )
    if not res.get("ok"):
        print(f"❌ Phân tích thất bại: {res.get('reason')} {res.get('error', '')}")
        return 1

    coord = res.get("coord") or {}
    print(f"\nToạ độ: ({coord.get('x')},{coord.get('y')})  |  Merchant: "
          f"{'MỞ' if res.get('merchantOpen') else 'ĐÓNG'}  |  Bảng Moss: "
          f"{'MỞ' if res.get('mossOpen') else 'ĐÓNG'}")
    print(f"Ngưỡng cấp tối đa cho đồ rác: +{res.get('maxJunkLevel')}"
          f"   (bỏ lọc tên/loại: {'CÓ' if args.ignore_type else 'KHÔNG'})")
    print(f"Tổng ô quét: {res.get('total')}  |  có đồ: {res.get('occupied')}  |  "
          f"dọn được: {res.get('junk')}  |  bị giữ: {res.get('protected')}")

    by = res.get("byReason") or {}
    if by:
        print("\nLý do bị giữ:")
        for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
            print(f"   - {v:>3} món: {REASON_VI.get(k, k)}  [{k}]")

    junk = [s for s in (res.get("slots") or []) if s.get("status") == "junk"]
    if junk:
        print(f"\nCác món SẼ bị dọn ({len(junk)}):")
        for it in (junk if args.limit <= 0 else junk[: args.limit]):
            print(f"   slot {int(it['slot']):>3}  {it.get('name') or ('Item #' + str(it.get('index')))}"
                  f"  +{it.get('level', 0)}  (idx {it.get('index')}, sec {it.get('section')})")
    else:
        print("\n⚠️ Không có món nào đủ điều kiện dọn với cấu hình hiện tại.")
        print("   → thử: python tools/moss_junk_report.py --max-level 9 --ignore-type")

    held = [s for s in (res.get("slots") or []) if s.get("status") == "protected"]
    if held:
        print(f"\nChi tiết món bị giữ ({len(held)}):")
        for it in held[:25]:
            print(f"   slot {int(it['slot']):>3}  {it.get('name') or ('Item #' + str(it.get('index')))}"
                  f"  +{it.get('level', 0)}  → {REASON_VI.get(it.get('reason'), it.get('reason'))}")
        if len(held) > 25:
            print(f"   ... và {len(held) - 25} món nữa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
