"""Dọn đồ rác NGAY trên phiên game đang chạy (đọc RVA -> lọc -> vứt/bán -> xác minh).

Ví dụ:
    python tools/drop_junk_now.py                       # chỉ xem, KHÔNG xóa gì
    python tools/drop_junk_now.py --yes                 # dọn thật (auto: vứt -> bán)
    python tools/drop_junk_now.py --yes --max-level 9   # nới ngưỡng cấp cho đồ rác
    python tools/drop_junk_now.py --yes --ignore-type   # bỏ lọc theo tên/loại

An toàn:
  * Không bao giờ đụng slot 0..11 (trang bị đang mặc).
  * Mặc định giữ: Exc / Set / Socket / Harmony / ngọc-vé-cánh / cấp > ngưỡng.
  * Không có --yes thì chỉ in danh sách, không gửi packet nào.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REASON_VI = {
    "divine_or_dragon": "lọc theo tên/loại",
    "excellent": "Exc",
    "ancient": "Set/Ancient",
    "socket": "Socket",
    "harmony": "Harmony",
    "level_over_max": "cấp + vượt ngưỡng",
    "jewel_section": "ngọc/vé/cánh",
    "wrong_moss_category": "khác danh mục",
    "preexisting_snapshot": "có sẵn trước khi quay",
    "unknown_item": "không rõ item",
}


def find_game_pid() -> int | None:
    """Tìm tiến trình GAME (không phải launcher MuClick)."""
    import psutil

    best = None
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            name = (p.info["name"] or "").upper()
            if "MEGAMU" not in name:
                continue
            if "DASHBOARD" in name:      # bỏ qua app dashboard
                continue
            # game thật thường là process mới nhất có tên MEGAMU
            if best is None or (p.info["create_time"] or 0) > best[1]:
                best = (p.info["pid"], p.info["create_time"] or 0)
        except Exception:
            continue
    return best[0] if best else None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--max-level", type=int, default=6)
    ap.add_argument("--ignore-type", action="store_true")
    ap.add_argument("--mode", choices=["auto", "drop", "sell"], default="auto")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--yes", action="store_true", help="thực thi thật (mặc định chỉ xem)")
    args = ap.parse_args()

    pid = args.pid or find_game_pid()
    if not pid:
        print("❌ Không thấy tiến trình game MEGAMU. Mở game trước rồi chạy lại.")
        return 2

    print(f"[i] Game PID = {pid}. Đang kết nối engine ...")
    from meg_direct_engine import MegDirectEngine

    eng = MegDirectEngine.get_engine(pid)
    if not eng.is_ready:
        if not eng.attach():
            print("❌ Không attach được vào game (Frida bị chặn hoặc game chưa vào nhân vật).")
            return 1
    print("[i] Đã kết nối.")

    res = eng.analyze_junk_inventory(
        category=-1,
        max_junk_level=args.max_level,
        protected_slots=[],
        ignore_type_heuristics=args.ignore_type,
    )
    if not res.get("ok"):
        print(f"❌ Không đọc được hòm đồ: {res.get('reason')} {res.get('error', '')}")
        return 1

    coord = res.get("coord") or {}
    print(f"\nToạ độ ({coord.get('x')},{coord.get('y')}) | Merchant "
          f"{'MỞ' if res.get('merchantOpen') else 'ĐÓNG'} | Moss "
          f"{'MỞ' if res.get('mossOpen') else 'ĐÓNG'}")
    print(f"Ô có đồ: {res.get('occupied')} | dọn được: {res.get('junk')} | bị giữ: {res.get('protected')}")

    for k, v in sorted((res.get("byReason") or {}).items(), key=lambda kv: -kv[1]):
        print(f"   giữ {v:>3} món → {REASON_VI.get(k, k)}")

    junk = [s for s in (res.get("slots") or []) if s.get("status") == "junk"]
    if not junk:
        print("\n⚠️ Không có món nào đủ điều kiện. Thử --max-level 9 --ignore-type")
        return 0

    print(f"\nDanh sách {len(junk)} món sẽ dọn:")
    for it in junk[:60]:
        print(f"   slot {int(it['slot']):>3}  {it.get('name') or ('Item #' + str(it.get('index')))}"
              f"  +{it.get('level', 0)}  (idx {it.get('index')})")

    if not args.yes:
        print("\n(Chưa thực thi — thêm --yes để dọn thật.)")
        return 0

    if not res.get("merchantOpen") and args.mode == "auto":
        print("\n[i] Merchant đang đóng → chỉ thử vứt. Nếu bị safe-zone chặn, hãy mở shop rồi chạy lại với --mode sell.")

    print("\n[>] Đang dọn ...")
    out = eng.dispose_junk_items(
        mode=args.mode,
        protected_slots=[],
        category=-1,
        include_extended=True,
        max_junk_level=args.max_level,
        max_batch=args.batch,
        ignore_type_heuristics=args.ignore_type,
    )
    print(f"Kết quả: {out}")
    cleaned = int(out.get("cleaned", 0) or 0)
    print(f"\n✔ Đã dọn {cleaned} món (vứt {out.get('dropped', 0)}, bán {out.get('sold', 0)}), "
          f"còn lại {out.get('failed', 0)} — lý do: {out.get('reason')}")
    return 0 if cleaned > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
