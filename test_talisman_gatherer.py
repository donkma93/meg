#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit & Integration Tests cho Gom Bùa Luck (7221) & Bùa Chaos Assembly (7264)
(Hướng A: Gom chồng theo ItemStackInfo/MaxStack + Hướng B: Lôi Thùng K & Cất Kho).
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import meg_talisman_gatherer as mtg

BASE_DIR = Path(__file__).resolve().parent


class FakeTalismanEngine:
    """Giả lập MegDirectEngine cho cả Hướng A (Stack) + Hướng B (Lôi Thùng K + Mở Thủ Kho + Cất Kho)."""

    def __init__(
        self,
        initial_map: int = 7,
        luck_stackable: bool = True,
        luck_max_stack: int = 10,
        chaos_stackable: bool = False,
        chaos_max_stack: int = 1,
        warehouse_open: bool = False,
        wh_free_slots=None,
    ):
        self.is_ready = True
        self.map_id = initial_map
        self.x = 120
        self.y = 120
        self.luck_stackable = luck_stackable
        self.luck_max_stack = luck_max_stack
        self.chaos_stackable = chaos_stackable
        self.chaos_max_stack = chaos_max_stack
        self.warehouse_open = warehouse_open
        self.wh_free_slots = list(wh_free_slots if wh_free_slots is not None else [0, 1, 2, 3, 4, 5, 6, 7])
        self.chat_sent = []
        self.talked_ptrs = []
        self.closed_warehouse = False
        self.gremory_items = [
            {"storageType": 1, "authCode": 11, "guid": 101, "code": 7264, "key": "TalismanOfChaosAssembly", "name": "Talisman of Chaos Assembly"},
            {"storageType": 1, "authCode": 12, "guid": 102, "code": 7221, "key": "TalismanOfLuck", "name": "Talisman of Luck"},
        ]
        self.inv_items = [
            {"slot": 12, "id": 7221, "key": "TalismanOfLuck", "name": "Talisman of Luck", "count": 4, "stackable": luck_stackable, "maxStack": luck_max_stack},
            {"slot": 13, "id": 7221, "key": "TalismanOfLuck", "name": "Talisman of Luck", "count": 3, "stackable": luck_stackable, "maxStack": luck_max_stack},
            {"slot": 14, "id": 7264, "key": "TalismanOfChaosAssembly", "name": "Talisman of Chaos Assembly", "count": 1, "stackable": chaos_stackable, "maxStack": chaos_max_stack},
            {"slot": 15, "id": 7264, "key": "TalismanOfChaosAssembly", "name": "Talisman of Chaos Assembly", "count": 1, "stackable": chaos_stackable, "maxStack": chaos_max_stack},
        ]
        self.wh_items = [
            {"slot": 10, "id": 7221, "key": "TalismanOfLuck", "name": "Talisman of Luck", "count": 2, "stackable": luck_stackable, "maxStack": luck_max_stack, "storage": "Kho chính"},
        ]
        self.next_inv_slot = 20

    def stop_helper(self):
        return True

    def stop_auto_move(self):
        return True

    def send_chat(self, msg: str):
        self.chat_sent.append(msg)
        low = msg.strip().lower()
        if low == "/m lorencia":
            self.map_id, self.x, self.y = 0, 145, 145
        elif low == "/m noria":
            self.map_id, self.x, self.y = 3, 172, 96
        elif low == "/m devias":
            self.map_id, self.x, self.y = 2, 218, 63
        return True

    def get_player_info(self, max_age=0.15):
        return {"mapId": self.map_id, "tileX": self.x, "tileY": self.y}

    def start_auto_move(self, tx: int, ty: int, helper: bool = False):
        self.x, self.y = int(tx), int(ty)
        return True

    def find_vault_keeper_npc(self):
        if self.map_id in (0, 2, 3):
            return {"found": True, "ptr": "0x55AA10", "skin": 240, "name": "Vault Keeper", "x": self.x, "y": self.y, "dist": 1.2}
        return {"found": False}

    def talk_to_npc_by_ptr(self, ptr_str):
        self.talked_ptrs.append(str(ptr_str))
        self.warehouse_open = True
        return {"ok": True}

    def close_warehouse_window(self):
        self.closed_warehouse = True
        self.warehouse_open = False
        return True

    def scan_talismans_info(self):
        totals = {
            "7221": {"inventory": 0, "warehouse": 0, "gremory": 0},
            "7264": {"inventory": 0, "warehouse": 0, "gremory": 0},
        }
        for it in self.inv_items:
            totals[str(it["id"])]["inventory"] += it["count"]
        for it in self.wh_items:
            totals[str(it["id"])]["warehouse"] += it["count"]
        for it in self.gremory_items:
            totals[str(it["code"])]["gremory"] += 1
        return {
            "ok": True,
            "warehouseOpen": self.warehouse_open,
            "extWarehouseOpen": False,
            "warehouseFreeMainCount": len(self.wh_free_slots) if self.warehouse_open else 0,
            "warehouseFreeExtCount": 0,
            "warehouseFreeCount": len(self.wh_free_slots) if self.warehouse_open else 0,
            "stackInfo": {
                "7221": {"seen": True, "stackable": self.luck_stackable, "maxStack": self.luck_max_stack},
                "7264": {"seen": True, "stackable": self.chaos_stackable, "maxStack": self.chaos_max_stack},
            },
            "totals": totals,
            "inventoryItems": list(self.inv_items),
            "warehouseItems": list(self.wh_items),
            "gremoryItems": list(self.gremory_items),
        }

    def claim_gremory_talismans(self, include_luck=True, include_chaos_assembly=True):
        claimed = []
        keep = []
        for it in self.gremory_items:
            code = it["code"]
            if (code == 7221 and include_luck) or (code == 7264 and include_chaos_assembly):
                claimed.append(it)
                self.inv_items.append({
                    "slot": self.next_inv_slot,
                    "id": code,
                    "key": it["key"],
                    "name": it["name"],
                    "count": 1,
                    "stackable": self.luck_stackable if code == 7221 else self.chaos_stackable,
                    "maxStack": self.luck_max_stack if code == 7221 else self.chaos_max_stack,
                })
                self.next_inv_slot += 1
            else:
                keep.append(it)
        self.gremory_items = keep
        return {"ok": True, "claimed": len(claimed), "remaining": 0, "items": claimed}

    def stack_talismans(self, include_luck=True, include_chaos_assembly=True):
        details = []
        moved = 0

        def _stack_bucket(label, arr):
            nonlocal moved
            by_id = {}
            for it in arr:
                if not it["stackable"] or it["maxStack"] <= 1:
                    continue
                if (it["id"] == 7221 and not include_luck) or (it["id"] == 7264 and not include_chaos_assembly):
                    continue
                by_id.setdefault(it["id"], []).append(it)
            for _tid, grp in by_id.items():
                grp.sort(key=lambda x: x["slot"])
                t = 0
                for s in range(1, len(grp)):
                    while grp[s]["count"] > 0 and t < s:
                        sp = grp[t]["maxStack"] - grp[t]["count"]
                        if sp <= 0:
                            t += 1
                            continue
                        mv = min(grp[s]["count"], sp)
                        grp[t]["count"] += mv
                        grp[s]["count"] -= mv
                        moved += 1
                        details.append({
                            "storage": label,
                            "id": grp[s]["id"],
                            "name": grp[s]["name"],
                            "fromSlot": grp[s]["slot"],
                            "toSlot": grp[t]["slot"],
                            "amount": mv,
                            "targetTotal": grp[t]["count"],
                            "maxStack": grp[t]["maxStack"],
                        })
                        if grp[t]["count"] >= grp[t]["maxStack"]:
                            t += 1
            arr[:] = [it for it in arr if it["count"] > 0]

        _stack_bucket("Hòm đồ nhân vật", self.inv_items)
        if self.warehouse_open:
            _stack_bucket("Kho chính", self.wh_items)
        return {"ok": True, "moved": moved, "details": details}

    def deposit_talismans_to_warehouse(self, include_luck=True, include_chaos_assembly=True, prefer_ext=False, max_moves=64):
        if not self.warehouse_open:
            return {"ok": False, "deposited": 0, "warehouseOpen": False, "error": "warehouse_not_open"}
        details = []
        deposited = 0
        rem = []
        wh_full = False
        for it in self.inv_items:
            want = (it["id"] == 7221 and include_luck) or (it["id"] == 7264 and include_chaos_assembly)
            if not want or deposited >= max_moves or wh_full:
                rem.append(it)
                continue
            merged = False
            dst_slot = -1
            if it["stackable"]:
                for wit in self.wh_items:
                    if wit["id"] == it["id"] and wit["count"] + it["count"] <= wit["maxStack"]:
                        wit["count"] += it["count"]
                        dst_slot = wit["slot"]
                        merged = True
                        break
            if dst_slot < 0:
                if not self.wh_free_slots:
                    wh_full = True
                    rem.append(it)
                    continue
                dst_slot = self.wh_free_slots.pop(0)
                new_w = dict(it)
                new_w["slot"] = dst_slot
                new_w["storage"] = "Kho chính"
                self.wh_items.append(new_w)
            deposited += 1
            details.append({
                "id": it["id"],
                "name": it["name"],
                "count": it["count"],
                "fromSlot": it["slot"],
                "toSlot": dst_slot,
                "merged": merged,
            })
        self.inv_items = rem
        return {
            "ok": True,
            "warehouseOpen": True,
            "deposited": deposited,
            "remainingInInventory": len([x for x in self.inv_items if x["id"] in (7221, 7264)]),
            "warehouseFull": wh_full,
            "details": details,
        }


class TestTalismanGatherer(unittest.TestCase):
    def test_01_town_order_and_config_roundtrip(self):
        self.assertEqual(mtg.normalize_vault_town("Davias"), "devias")
        self.assertEqual(mtg.resolve_vault_town_order("auto", current_map_id=mtg.MAP_NORIA), ["noria", "lorencia", "devias"])
        self.assertEqual(mtg.resolve_vault_town_order("devias", current_map_id=0), ["devias", "lorencia", "noria"])

        with tempfile.TemporaryDirectory() as td:
            mgr = mtg.TalismanGatherConfigManager(Path(td))
            d = mgr.load()
            self.assertTrue(d["include_luck"])
            self.assertTrue(d["include_chaos_assembly"])
            self.assertTrue(d["stack_in_inventory"])
            self.assertTrue(d["deposit_to_warehouse"])

            self.assertTrue(mgr.save({"town": "Davias", "vault_number": 5, "prefer_ext_warehouse": True}))
            d2 = mgr.load()
            self.assertEqual(d2["town"], "devias")
            self.assertEqual(d2["vault_number"], 5)
            self.assertTrue(d2["prefer_ext_warehouse"])

    def test_02_both_directions_claim_stack_and_deposit(self):
        eng = FakeTalismanEngine(
            initial_map=7,
            luck_stackable=True,
            luck_max_stack=10,
            chaos_stackable=False,
            chaos_max_stack=1,
            warehouse_open=False,
        )
        with mock.patch("meg_talisman_gatherer._sleep_check", return_value=True):
            res = mtg.execute_talisman_gather(
                eng,
                cfg={
                    "include_luck": True,
                    "include_chaos_assembly": True,
                    "claim_from_gremory": True,
                    "stack_in_inventory": True,
                    "deposit_to_warehouse": True,
                    "town": "noria",
                    "vault_number": 3,
                    "close_warehouse_after": True,
                },
            )

        self.assertTrue(res["ok"])
        # 1. Đã lôi 2 bùa từ Thùng đồ K (1 Luck + 1 Chaos Assembly)
        self.assertEqual(res["claimed_gremory"], 2)
        # 2. Hướng A đã gộp chồng Bùa Luck (4 + 3 + 1 = 8 thành 1 ô) và KHÔNG gộp Chaos Assembly
        self.assertGreaterEqual(res["stacked_moves"], 2)
        # 3. Đã gửi /bau 3, về Noria, mở Thủ Kho (NPC 240), cất toàn bộ bùa vào Kho & đóng Kho
        self.assertIn("/bau 3", eng.chat_sent)
        self.assertIn("/m noria", eng.chat_sent)
        self.assertEqual(eng.talked_ptrs, ["0x55AA10"])
        self.assertTrue(eng.closed_warehouse)
        # 4. Hòm đồ sạch bùa; Kho có tổng 2 + 8 = 10 Bùa Luck (gộp vào đúng 1 ô!) và 3 Bùa Chaos Assembly (3 ô riêng)
        self.assertEqual(len(eng.inv_items), 0)
        wh_luck = [x for x in eng.wh_items if x["id"] == 7221]
        wh_chaos = [x for x in eng.wh_items if x["id"] == 7264]
        self.assertEqual(len(wh_luck), 1)
        self.assertEqual(wh_luck[0]["count"], 10)
        self.assertEqual(len(wh_chaos), 3)

    def test_03_direction_a_only_without_warehouse(self):
        eng = FakeTalismanEngine(initial_map=7, luck_stackable=True, luck_max_stack=10, chaos_stackable=False)
        with mock.patch("meg_talisman_gatherer._sleep_check", return_value=True):
            res = mtg.execute_talisman_gather(
                eng,
                cfg={
                    "include_luck": True,
                    "include_chaos_assembly": True,
                    "claim_from_gremory": False,
                    "stack_in_inventory": True,
                    "deposit_to_warehouse": False,
                },
            )
        self.assertTrue(res["ok"])
        self.assertEqual(res["deposited"], 0)
        self.assertEqual(eng.chat_sent, [])
        inv_luck = [x for x in eng.inv_items if x["id"] == 7221]
        inv_chaos = [x for x in eng.inv_items if x["id"] == 7264]
        self.assertEqual(len(inv_luck), 1)
        self.assertEqual(inv_luck[0]["count"], 7)  # 4 + 3 = 7
        self.assertEqual(len(inv_chaos), 2)        # 2 ô riêng vì không stackable

    def test_04_js_classifier_and_no_chaos_false_match_in_node(self):
        engine_src = (BASE_DIR / "meg_direct_engine.py").read_text(encoding="utf-8")
        for sym in (
            "readItemStackMeta(",
            "classifyTalismanItem(",
            "scanTalismansInfo: function()",
            "claimGremoryTalismans: function(",
            "stackTalismans: function(",
            "depositTalismansToWarehouse: function(",
            "findVaultKeeperNpc: function()",
            "closeWarehouseWindow: function()",
            "def scan_talismans_info(",
            "def claim_gremory_talismans(",
            "def stack_talismans(",
            "def deposit_talismans_to_warehouse(",
            "def find_vault_keeper_npc(",
            "def close_warehouse_window(",
        ):
            self.assertIn(sym, engine_src, f"Missing {sym} in meg_direct_engine.py")

        m_cls = re.search(r"(function classifyTalismanItem\(idx, name\) \{[\s\S]*?\n\})", engine_src)
        self.assertIsNotNone(m_cls)
        node_code = (
            "var TALISMAN_LUCK_ID = 7221;\nvar TALISMAN_CHAOS_ASSEMBLY_ID = 7264;\n"
            + m_cls.group(1)
            + """
const assert = require('assert');
assert.strictEqual(classifyTalismanItem(7221, 'Talisman of Luck').id, 7221);
assert.strictEqual(classifyTalismanItem(7264, 'Talisman of Chaos Assembly').id, 7264);
assert.strictEqual(classifyTalismanItem(7357, 'Elemental Talisman of Luck'), null);
assert.strictEqual(classifyTalismanItem(7358, 'Elemental Talisman of Chaos'), null);
assert.strictEqual(classifyTalismanItem(7182, 'Jewel of Chaos'), null);
console.log('NODE_TALISMAN_CLASSIFY_OK');
"""
        )
        proc = subprocess.run(["node", "-e", node_code], capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NODE_TALISMAN_CLASSIFY_OK", proc.stdout)

    def test_05_zero_offset_leak_in_talisman_gatherer(self):
        src = (BASE_DIR / "meg_talisman_gatherer.py").read_text(encoding="utf-8")
        rvas = re.findall(r"\b0x[0-9a-fA-F]{6,8}\b", src)
        self.assertEqual(rvas, [], f"Leaked RVA in meg_talisman_gatherer.py: {rvas}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
