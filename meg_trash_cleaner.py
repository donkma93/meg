#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Inventory Trash Cleaner - Tự động vứt đồ thừa trong thùng đồ
==================================================================
Chương trình chuyên biệt quét và tự động vứt các vật phẩm rác/thừa trong thùng đồ (Main Inventory)
ra đất hoặc dọn sạch hòm đồ một cách thông minh và an toàn 100%.

Tiêu chuẩn bảo tồn an toàn (Tuyệt đối không vứt đồ quý):
- Đồ Divine, Vũ khí Thiên Sứ (Archangel), Đồ Rồng (Dragon)
- Đồ Hoàn Hảo (Excellent item)
- Đồ Thần (Ancient / Set item)
- Đồ Socket
- Đồ đã nâng cấp/đập ngọc (+5 trở lên)
- Ngọc các loại (Bless, Soul, Chaos, Life, Creation, Harmony...) và vé, cánh, talisman
- Trang bị đang đeo trên người (Slots 0..11)

Chế độ hoạt động:
1. Giao diện trực quan (GUI): Quét hòm đồ, xem danh sách vật phẩm, vứt 1-click hoặc bật Auto Clean.
2. Dòng lệnh (CLI): python meg_trash_cleaner.py --cli [--all] [--loop]
"""

import sys
import os
import time
import json
import threading
from typing import Optional, List, Dict, Any

# Đảm bảo UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import psutil
try:
    import customtkinter as ctk
    from tkinter import messagebox
except ImportError:
    ctk = None

from meg_direct_engine import MegDirectEngine

# Tên các nhóm Section trang bị trong MU Online
SECTION_NAMES = {
    0: "Kiếm / Dao (Sword)",
    1: "Rìu (Axe)",
    2: "Chùy / Quyền Trượng (Mace/Scepter)",
    3: "Thương / Giáo (Spear)",
    4: "Cung / Nỏ (Bow/Crossbow)",
    5: "Gậy Phép (Staff)",
    6: "Khiên (Shield)",
    7: "Mũ (Helm)",
    8: "Áo (Armor)",
    9: "Quần (Pants)",
    10: "Găng Tay (Gloves)",
    11: "Giày (Boots)",
    12: "Cánh / Quả / Ngọc Hạt (Wings/Seeds)",
    13: "Thú Cưỡi / Nhẫn / Dây Chuyền (Pets/Rings)",
    14: "Ngọc / Thuốc / Vé Sự Kiện (Jewels/Potions/Tickets)",
    15: "Sách Phép / Cuộn Giấy (Scrolls)"
}


def find_megamu_pids() -> List[int]:
    """Tìm tất cả PID tiến trình MEGAMU.exe đang chạy."""
    pids = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = p.info.get('name', '') or ''
            if name.lower() in ('megamu.exe', 'megamu'):
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def clean_junk_for_pid(pid: int, method: str = "both") -> Dict[str, Any]:
    """Dọn đồ rác cho 1 client MEGAMU qua PID."""
    eng = MegDirectEngine.get_engine(pid)
    if not eng:
        return {"cleaned": 0, "error": f"Không tạo được engine cho PID {pid}"}
    if not eng.is_ready:
        if not eng.attach():
            return {"cleaned": 0, "error": f"Không thể attach vào PID {pid}"}
    return eng.clean_inventory_junk(method=method)


class InventoryTrashCleanerApp:
    """Giao diện đồ họa chuyên biệt để quét và vứt đồ thừa trong thùng đồ MEGAMU."""

    def __init__(self):
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("🗑️ MEGAMU INVENTORY TRASH CLEANER • TỰ ĐỘNG VỨT ĐỒ THỪA")
        self.root.geometry("820, 680")
        self.root.minsize(760, 580)

        self.selected_pid: Optional[int] = None
        self.auto_clean_running = False
        self.auto_clean_thread = None

        self._build_ui()
        self.refresh_process_list()

    def _build_ui(self):
        # 1. Header Frame
        header = ctk.CTkFrame(self.root, fg_color="#181c26", corner_radius=10, border_width=1, border_color="#2b3244")
        header.pack(fill="x", padx=14, pady=(12, 6))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            title_box,
            text="🗑️ MEGAMU INVENTORY TRASH CLEANER",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f59e0b"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Tự động quét & vứt sạch đồ rác / đồ thừa trong thùng đồ • Bảo tồn an toàn tuyệt đối đồ Hoàn Hảo, Đồ Thần, Socket, Ngọc và Đồ cộng",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Control Toolbar
        toolbar = ctk.CTkFrame(self.root, fg_color="#141722", corner_radius=8, border_width=1, border_color="#202430")
        toolbar.pack(fill="x", padx=14, pady=(2, 6))

        tb_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tb_inner.pack(fill="both", expand=True, padx=12, pady=8)

        # Chọn Client / Tiến trình
        ctk.CTkLabel(
            tb_inner,
            text="Client:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left", padx=(0, 6))

        self.proc_combo = ctk.CTkOptionMenu(
            tb_inner,
            values=["Đang quét..."],
            width=200,
            height=30,
            command=self._on_proc_selected
        )
        self.proc_combo.pack(side="left", padx=(0, 6))

        btn_refresh_proc = ctk.CTkButton(
            tb_inner,
            text="🔄 Quét Client",
            width=90,
            height=30,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self.refresh_process_list
        )
        btn_refresh_proc.pack(side="left", padx=(0, 10))

        # Nút Quét Hòm Đồ
        btn_scan_inv = ctk.CTkButton(
            tb_inner,
            text="🔍 Xem Hòm Đồ",
            width=100,
            height=30,
            fg_color="#0284c7",
            hover_color="#0369a1",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.scan_inventory
        )
        btn_scan_inv.pack(side="left", padx=(0, 10))

        # Nút Vứt Toàn Bộ Đồ Rác
        btn_clean_now = ctk.CTkButton(
            tb_inner,
            text="🧹 VỨT ĐỒ THỪA NGAY",
            height=30,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.clean_current_client
        )
        btn_clean_now.pack(side="left", padx=(0, 6))

        # Nút Dọn Tất Cả Client
        btn_clean_all = ctk.CTkButton(
            tb_inner,
            text="🧹 Dọn Tất Cả Client",
            height=30,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.clean_all_clients
        )
        btn_clean_all.pack(side="left")

        # 3. Stats Card (Thống kê số lượng ô)
        self.stats_card = ctk.CTkFrame(self.root, fg_color="#141722", corner_radius=8, border_width=1, border_color="#202430")
        self.stats_card.pack(fill="x", padx=14, pady=(2, 6))

        st_inner = ctk.CTkFrame(self.stats_card, fg_color="transparent")
        st_inner.pack(fill="x", padx=12, pady=6)

        self.lbl_char_info = ctk.CTkLabel(
            st_inner,
            text="Nhân vật: Chưa chọn | Tọa độ: -- | Zen: --",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_char_info.pack(side="left")

        self.lbl_inv_stats = ctk.CTkLabel(
            st_inner,
            text="Thùng đồ: 64 ô | Trống: -- | Đồ rác cần vứt: -- | Đồ bảo tồn: --",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10b981"
        )
        self.lbl_inv_stats.pack(side="right")

        # 4. Bảng danh sách vật phẩm trong hòm đồ
        list_container = ctk.CTkFrame(self.root, fg_color="#141722", corner_radius=8, border_width=1, border_color="#202430")
        list_container.pack(fill="both", expand=True, padx=14, pady=(2, 6))

        lh = ctk.CTkFrame(list_container, fg_color="transparent", height=28)
        lh.pack(fill="x", padx=10, pady=(6, 2))

        headers = [
            ("Ô (Slot)", 70, "center"),
            ("Nhóm Vật Phẩm", 210, "w"),
            ("Cấp Độ", 80, "center"),
            ("Thuộc Tính (Exc / Set / Socket)", 200, "w"),
            ("Đánh Giá", 110, "center"),
            ("Thao Tác", 80, "center"),
        ]
        for t, w, a in headers:
            ctk.CTkLabel(
                lh,
                text=t,
                width=w,
                anchor=a,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#94a3b8"
            ).pack(side="left", padx=2)

        div = ctk.CTkFrame(list_container, fg_color="#1f2535", height=1)
        div.pack(fill="x", padx=8, pady=(0, 2))

        self.scroll_items = ctk.CTkScrollableFrame(list_container, fg_color="transparent")
        self.scroll_items.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        # 5. Log Console
        log_frame = ctk.CTkFrame(self.root, fg_color="#141722", height=120, corner_radius=8, border_width=1, border_color="#202430")
        log_frame.pack(fill="x", padx=14, pady=(0, 10))
        log_frame.pack_propagate(False)

        log_h = ctk.CTkFrame(log_frame, fg_color="transparent", height=22)
        log_h.pack(fill="x", padx=10, pady=(4, 2))

        ctk.CTkLabel(
            log_h,
            text="📜 NHẬT KÝ THAO TÁC",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#f1f5f9"
        ).pack(side="left")

        self.log_txt = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0b0d13",
            text_color="#cbd5e1"
        )
        self.log_txt.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.log("🟢 MEGAMU Inventory Trash Cleaner đã sẵn sàng. Hãy bấm 'Quét Client' hoặc chọn tiến trình.")

    def log(self, text: str):
        t_str = time.strftime("%H:%M:%S")
        self.log_txt.insert("end", f"[{t_str}] {text}\n")
        self.log_txt.see("end")

    def refresh_process_list(self):
        pids = find_megamu_pids()
        if not pids:
            self.proc_combo.configure(values=["Không tìm thấy MEGAMU.exe"])
            self.proc_combo.set("Không tìm thấy MEGAMU.exe")
            self.selected_pid = None
            self.log("⚠️ Không phát hiện client MEGAMU.exe nào đang chạy!")
            return

        values = []
        for pid in pids:
            try:
                eng = MegDirectEngine.get_engine(pid)
                if eng and not eng.is_ready:
                    eng.attach()
                p_info = eng.get_player_info() if eng else None
                c_name = p_info.get("name", "MEGAMU") if p_info else "MEGAMU"
                values.append(f"{c_name} (PID: {pid})")
            except Exception:
                values.append(f"MEGAMU (PID: {pid})")

        self.proc_combo.configure(values=values)
        if values:
            self.proc_combo.set(values[0])
            self._on_proc_selected(values[0])
        self.log(f"🔍 Đã tìm thấy {len(pids)} client MEGAMU đang chạy.")

    def _on_proc_selected(self, choice: str):
        try:
            if "PID: " in choice:
                pid_str = choice.split("PID: ")[1].replace(")", "").strip()
                self.selected_pid = int(pid_str)
                self.scan_inventory()
        except Exception as e:
            self.log(f"Lỗi chọn tiến trình: {e}")

    def scan_inventory(self):
        if not self.selected_pid:
            self.log("⚠️ Chưa chọn client MEGAMU!")
            return

        eng = MegDirectEngine.get_engine(self.selected_pid)
        if not eng:
            self.log("❌ Không tìm thấy Direct Engine!")
            return
        if not eng.is_ready:
            eng.attach()

        # Đọc thông tin nhân vật & hòm đồ
        p_info = eng.get_player_info() or {}
        c_name = p_info.get("name", "Nhân vật")
        cur_x = p_info.get("tileX", p_info.get("x", 0))
        cur_y = p_info.get("tileY", p_info.get("y", 0))

        inv = eng.get_inventory_summary()
        if not inv or inv.get("error"):
            self.log(f"❌ Không thể đọc hòm đồ PID {self.selected_pid}: {inv.get('error') if inv else 'None'}")
            return

        zen = int(inv.get("zen", 0))
        free = int(inv.get("free", 64))
        junk_cnt = int(inv.get("junkCount", 0))
        kept_cnt = int(inv.get("keptCount", 0))

        self.lbl_char_info.configure(
            text=f"Nhân vật: {c_name} | PID: {self.selected_pid} | Tọa độ: ({cur_x}, {cur_y}) | Zen: {zen:,}"
        )
        self.lbl_inv_stats.configure(
            text=f"Trống: {free}/64 | Đồ rác cần vứt: {junk_cnt} | Đồ giữ lại: {kept_cnt}"
        )

        # Xóa danh sách cũ
        for widget in self.scroll_items.winfo_children():
            widget.destroy()

        junk_slots = inv.get("junkSlots", [])
        if junk_cnt == 0:
            lbl_empty = ctk.CTkLabel(
                self.scroll_items,
                text="🎉 Hòm đồ KHÔNG CÓ ĐỒ RÁC! Toàn bộ đồ đều là đồ giá trị hoặc ô trống.",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#10b981"
            )
            lbl_empty.pack(pady=20)
            self.log(f"✅ Hòm đồ {c_name} sạch sẽ (còn {free} ô trống, không có đồ rác).")
            return

        self.log(f"📦 Đã quét hòm đồ {c_name}: Phát hiện {junk_cnt} món đồ thừa cần vứt!")

        for item in junk_slots:
            slot = item.get("slot", 0)
            idx = item.get("index", 0)
            lvl = item.get("level", 0)
            sec = idx // 512
            sec_name = SECTION_NAMES.get(sec, f"Loại #{sec}")

            row = ctk.CTkFrame(self.scroll_items, fg_color="#181c26", height=32, corner_radius=4)
            row.pack(fill="x", pady=2, padx=2)

            slot_str = f"MR1 {slot:02d}" if 76 <= slot < 108 else (f"MR2 {slot:02d}" if 108 <= slot < 140 else f"Slot {slot:02d}")
            ctk.CTkLabel(row, text=slot_str, width=70, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=2)
            ctk.CTkLabel(row, text=sec_name, width=210, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#f8fafc").pack(side="left", padx=2)
            ctk.CTkLabel(row, text=f"+{lvl}", width=80, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8").pack(side="left", padx=2)
            ctk.CTkLabel(row, text="Đồ thường (+0..+4 không tính năng)", width=200, anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8").pack(side="left", padx=2)
            ctk.CTkLabel(row, text="🗑️ Rác (Vứt)", width=110, anchor="center", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#ef4444").pack(side="left", padx=2)

            btn_del = ctk.CTkButton(
                row,
                text="Vứt",
                width=65,
                height=24,
                corner_radius=4,
                fg_color="#dc2626",
                hover_color="#b91c1c",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                command=lambda s=slot: self.trash_single_slot(s)
            )
            btn_del.pack(side="left", padx=4)

    def trash_single_slot(self, slot: int):
        if not self.selected_pid:
            return
        eng = MegDirectEngine.get_engine(self.selected_pid)
        if not eng:
            return
        res = eng.trash_inventory_slot(slot)
        if isinstance(res, dict):
            if res.get("ok"):
                self.log(f"🗑️ Đã gửi lệnh vứt đồ tại ô Slot {slot:02d} ra đất!")
                self.root.after(400, self.scan_inventory)
            else:
                err = res.get("err") or res.get("error", "unknown")
                self.log(f"⚠️ Không thể vứt đồ Slot {slot:02d}: {err}")
                if err == "no_coord":
                    self.log("   → Nhân vật chưa có tọa độ! Hãy để nhân vật di chuyển trước.")
                elif err == "no_native_fn":
                    self.log("   → Offset inv_trash_item chưa load được. Kiểm tra megamu_offsets.json.")
        else:
            # Backward compat: bool return
            if res:
                self.log(f"🗑️ Đã vứt Slot {slot:02d}!")
                self.root.after(400, self.scan_inventory)
            else:
                self.log(f"⚠️ Không thể vứt đồ tại ô Slot {slot:02d}.")

    def clean_current_client(self):
        if not self.selected_pid:
            self.log("⚠️ Chưa chọn client để dọn rác!")
            return

        def _do_clean():
            self.log(f"🧹 Bắt đầu vứt toàn bộ đồ thừa cho PID {self.selected_pid}...")
            eng = MegDirectEngine.get_engine(self.selected_pid)
            if not eng:
                self.log("❌ Không tìm thấy engine!")
                return
            if not eng.is_ready:
                eng.attach()
            res = eng.clean_inventory_junk(method="trash")
            cleaned = res.get("cleaned", 0)
            failed  = res.get("failed", 0)
            err     = res.get("error", "")
            if err:
                self.log(f"❌ Lỗi khi dọn rác: {err}")
            elif cleaned > 0:
                self.log(f"🎉 Đã vứt thành công {cleaned} món đồ thừa! (Thất bại: {failed}) Toàn bộ đồ giá trị và ngọc đã được giữ lại an toàn.")
            else:
                self.log(f"ℹ️ Không có món đồ rác nào được vứt (Hòm đồ đã sạch hoặc không có Coord).")
                if failed > 0:
                    self.log(f"   → {failed} slot thất bại - có thể do nhân vật chưa di chuyển (để game tải Coord).")
            self.root.after(600, self.scan_inventory)

        threading.Thread(target=_do_clean, daemon=True).start()

    def clean_all_clients(self):
        pids = find_megamu_pids()
        if not pids:
            self.log("⚠️ Không có client MEGAMU nào đang chạy!")
            return

        def _clean_all():
            total = 0
            for pid in pids:
                res = clean_junk_for_pid(pid, method="trash")
                cnt = res.get("cleaned", 0)
                total += cnt
                self.log(f"🧹 PID {pid}: Đã dọn {cnt} món đồ thừa.")
                time.sleep(0.1)
            self.log(f"🎉 Hoàn tất dọn rác cho tất cả {len(pids)} client! Tổng số đồ rác đã vứt: {total} món.")
            self.root.after(500, self.scan_inventory)

        threading.Thread(target=_clean_all, daemon=True).start()

    def run(self):
        self.root.mainloop()


# CHẾ ĐỘ DÒNG LỆNH (CLI)
def run_cli_cleaner():
    print("=" * 65)
    print("🗑️ MEGAMU INVENTORY TRASH CLEANER - CLI MODE")
    print("Tự động vứt toàn bộ đồ thừa / đồ rác trong thùng đồ ra đất")
    print("=" * 65)

    pids = find_megamu_pids()
    if not pids:
        print("❌ Không tìm thấy tiến trình MEGAMU.exe nào đang chạy!")
        return

    print(f"🔍 Phát hiện {len(pids)} client MEGAMU: {pids}")
    total_cleaned = 0
    for pid in pids:
        print(f"\n[+] Đang xử lý client PID {pid}...")
        res = clean_junk_for_pid(pid, method="trash")
        cleaned = res.get("cleaned", 0)
        total_cleaned += cleaned
        print(f"    -> Đã dọn {cleaned} món đồ thừa.")

    print("\n" + "=" * 65)
    print(f"🎉 HOÀN THÀNH: Đã vứt tổng cộng {total_cleaned} món đồ thừa trên {len(pids)} client!")
    print("=" * 65)


if __name__ == "__main__":
    if "--cli" in sys.argv or "--help" in sys.argv:
        run_cli_cleaner()
    else:
        if ctk is not None:
            app = InventoryTrashCleanerApp()
            app.run()
        else:
            run_cli_cleaner()
