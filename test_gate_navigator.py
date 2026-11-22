#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for MEGAMU Gate REA Navigator Module (meg_gate_navigator.py)."""

import json
import os
import tempfile
import unittest

from meg_gate_navigator import (
    GateCatalog,
    GateEntry,
    MegGateNavigator,
    MoveEntry,
    normalize_map_name,
)


def _sample_world_dump():
    """Giả lập bảng TableWorld.Gate & TableWorld.Move cho cụm Acheron / Elemental."""
    gates = [
        # Acheron Safe Zone (Map 91) -> cổng vào Alkmar (427) & Ubaid (431)
        {"index": 417, "flag": 0, "mapId": 91, "x": 36, "y": 215, "tx": 40, "ty": 219, "targetGate": 0, "minLevel": 1},
        {"index": 426, "flag": 1, "mapId": 91, "x": 65, "y": 210, "tx": 67, "ty": 214, "targetGate": 427, "minLevel": 200},
        {"index": 427, "flag": 0, "mapId": 91, "x": 110, "y": 175, "tx": 114, "ty": 179, "targetGate": 0, "minLevel": 200},
        {"index": 430, "flag": 1, "mapId": 91, "x": 45, "y": 180, "tx": 47, "ty": 184, "targetGate": 431, "minLevel": 250},
        {"index": 431, "flag": 0, "mapId": 91, "x": 195, "y": 130, "tx": 199, "ty": 134, "targetGate": 0, "minLevel": 250},
        # Alkmar (Map 91) -> Debenter (Map 95, Gate 439)
        {"index": 438, "flag": 1, "mapId": 91, "x": 160, "y": 160, "tx": 164, "ty": 164, "targetGate": 439, "minLevel": 300},
        {"index": 439, "flag": 0, "mapId": 95, "x": 30, "y": 50, "tx": 34, "ty": 54, "targetGate": 0, "minLevel": 300},
        # Debenter (Map 95) -> Uruk Mountain (Map 100, Gate 451)
        {"index": 450, "flag": 1, "mapId": 95, "x": 180, "y": 180, "tx": 184, "ty": 184, "targetGate": 451, "minLevel": 350},
        {"index": 451, "flag": 0, "mapId": 100, "x": 20, "y": 40, "tx": 24, "ty": 44, "targetGate": 0, "minLevel": 350},
        # Uruk Mountain (Map 100) -> Nars (Map 110, Gate 471)
        {"index": 470, "flag": 1, "mapId": 100, "x": 210, "y": 210, "tx": 214, "ty": 214, "targetGate": 471, "minLevel": 400},
        {"index": 471, "flag": 0, "mapId": 110, "x": 50, "y": 60, "tx": 54, "ty": 64, "targetGate": 0, "minLevel": 400},
    ]
    moves = [
        {"index": 1, "name": "Acheron", "command": "acheron", "money": 10000, "minLevel": 1, "gateId": 417},
        {"index": 2, "name": "Alkmar", "command": "alkmar", "money": 15000, "minLevel": 200, "accountLevel": 1, "gateId": 427},
        {"index": 3, "name": "Ubaid", "command": "ubaid", "money": 15000, "minLevel": 250, "accountLevel": 1, "gateId": 431},
        {"index": 4, "name": "Debenter", "command": "debenter", "money": 20000, "minLevel": 300, "accountLevel": 1, "gateId": 439},
        {"index": 5, "name": "Uruk", "command": "uruk", "money": 25000, "minLevel": 350, "accountLevel": 1, "gateId": 451},
        {"index": 6, "name": "Nars", "command": "nars", "money": 30000, "minLevel": 400, "accountLevel": 1, "gateId": 471},
    ]
    return {"ok": True, "currentMapId": 91, "currentX": 38, "currentY": 217, "gates": gates, "moves": moves}


class FakeGateEngine:
    """Mock MegDirectEngine mô phỏng server cho phép/từ chối remote C1:1C."""

    def __init__(self, map_id=91, x=38, y=217, require_proximity=False):
        self.is_ready = True
        self.map_id = map_id
        self.x = x
        self.y = y
        self.require_proximity = require_proximity
        self.dump = _sample_world_dump()
        self.gates_map = {g["index"]: g for g in self.dump["gates"]}
        self.chat_sent = []
        self.enter_calls = []
        self.move_calls = []
        self._last_res = {"done": False, "ok": False}

    def get_player_state(self):
        return {"map_id": self.map_id, "x": self.x, "y": self.y}

    def dump_world_gates(self):
        return self.dump

    def get_current_tile_gate(self):
        for g in self.dump["gates"]:
            if g["mapId"] == self.map_id and g["x"] <= self.x <= g["tx"] and g["y"] <= self.y <= g["ty"]:
                return {"ok": True, "found": True, "mapId": self.map_id, "x": self.x, "y": self.y, "gate": g}
        return {"ok": True, "found": False, "mapId": self.map_id, "x": self.x, "y": self.y}

    def move_to(self, tx, ty):
        self.move_calls.append((tx, ty))
        self.x = int(tx)
        self.y = int(ty)
        return True

    def send_chat(self, msg):
        self.chat_sent.append(msg)
        if msg.strip().lower() == "/move acheron":
            self.map_id, self.x, self.y = 91, 38, 217
        return True

    def enter_acheron_npc(self, zone=-1):
        self.map_id, self.x, self.y = 91, 38, 217
        return {"ok": True}

    def enter_gate(self, gate_id, x=-1, y=-1):
        self.enter_calls.append((gate_id, x, y))
        g = self.gates_map.get(gate_id)
        if not g:
            self._last_res = {"done": True, "ok": False, "gateId": gate_id, "error": "unknown_gate"}
            return {"ok": True, "queued": True}

        # Nếu require_proximity=True, chỉ warp khi nhân vật đứng gần cổng nguồn!
        if self.require_proximity:
            cx = (g["x"] + g["tx"]) // 2
            cy = (g["y"] + g["ty"]) // 2
            if g["mapId"] != self.map_id or abs(self.x - cx) > 4 or abs(self.y - cy) > 4:
                self._last_res = {"done": True, "ok": True, "ret": True, "gateId": gate_id}
                return {"ok": True, "queued": True}  # server silently ignores remote C1:1C

        tgt_id = g["targetGate"] if g["targetGate"] > 0 else gate_id
        tgt = self.gates_map.get(tgt_id, g)
        self.map_id = tgt["mapId"]
        self.x = (tgt["x"] + tgt["tx"]) // 2
        self.y = (tgt["y"] + tgt["ty"]) // 2
        self._last_res = {"done": True, "ok": True, "ret": True, "gateId": gate_id}
        return {"ok": True, "queued": True}

    def get_last_gate_enter_result(self):
        return self._last_res


class TestMegGateNavigator(unittest.TestCase):
    def test_alias_normalization(self):
        self.assertEqual(normalize_map_name("Ubail"), "ubaid")
        self.assertEqual(normalize_map_name("ALKA"), "alkmar")
        self.assertEqual(normalize_map_name("Deventer"), "debenter")
        self.assertEqual(normalize_map_name("Uruk Mountain"), "uruk")
        self.assertEqual(normalize_map_name("  Nars  "), "nars")

    def test_catalog_dump_and_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            cpath = os.path.join(td, "gates_cache.json")
            cat = GateCatalog(cache_path=cpath)
            cnt = cat.load_from_dump(_sample_world_dump())
            self.assertEqual(cnt, 11)
            cat.save_cache()
            self.assertTrue(os.path.exists(cpath))

            cat2 = GateCatalog(cache_path=cpath)
            self.assertEqual(cat2.load_cache(), 11)
            res = cat2.resolve_target("ubail")
            self.assertTrue(res["ok"])
            self.assertEqual(res["gate_id"], 431)
            self.assertEqual(res["map_id"], 91)

    def test_bfs_multihop_acheron_to_nars(self):
        cat = GateCatalog()
        cat.load_from_dump(_sample_world_dump())
        path = cat.find_gate_path(91, 110, to_gate_id=471)
        # 91 -> 95 (Gate 438->439) -> 100 (Gate 450->451) -> 110 (Gate 470->471)
        self.assertEqual(len(path), 3)
        self.assertEqual([h.source_gate.index for h in path], [438, 450, 470])
        self.assertEqual([h.to_map for h in path], [95, 100, 110])

    def test_same_map_subzone_alkmar_and_ubaid(self):
        eng = FakeGateEngine(map_id=91, x=38, y=217, require_proximity=False)
        nav = MegGateNavigator(eng, catalog=GateCatalog(cache_path=""))
        nav.refresh_catalog(save_cache=False)

        r_ubail = nav.go_to_gate_map("ubail", mode="auto")
        self.assertTrue(r_ubail.ok)
        self.assertEqual(eng.map_id, 91)
        self.assertEqual((eng.x, eng.y), (197, 132))  # Tọa độ đích Ubaid Gate #431

    def test_auto_fallback_walk_when_server_requires_proximity(self):
        eng = FakeGateEngine(map_id=91, x=38, y=217, require_proximity=True)
        nav = MegGateNavigator(eng, catalog=GateCatalog(cache_path=""))
        nav.refresh_catalog(save_cache=False)

        # Đi tới Nars (3 chặng: 91->95->100->110) khi server yêu cầu phải đứng sát cổng!
        res = nav.go_to_gate_map("nars", mode="auto")
        self.assertTrue(res.ok, res.message)
        self.assertEqual(res.hops_done, 3)
        self.assertEqual(eng.map_id, 110)
        # Phải có lệnh move_to tới từng cổng nguồn: (162,162), (182,182), (212,212)
        self.assertIn((162, 162), eng.move_calls)
        self.assertIn((182, 182), eng.move_calls)
        self.assertIn((212, 212), eng.move_calls)

    def test_bootstrap_from_lorencia_to_debenter(self):
        eng = FakeGateEngine(map_id=0, x=125, y=125, require_proximity=False)
        nav = MegGateNavigator(eng, catalog=GateCatalog(cache_path=""))
        nav.refresh_catalog(save_cache=False)

        res = nav.go_to_gate_map("deventer", mode="auto")
        self.assertTrue(res.ok, res.message)
        self.assertIn("/move acheron", [c.lower() for c in eng.chat_sent])
        self.assertEqual(eng.map_id, 95)

    def test_engine_placeholders_and_zero_offset_policy(self):
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            eng_src = f.read()
        for ph in (
            "__DATA_TYPE_INFO__",
            "__DATA_GET_INSTANCE__",
            "__UNIT_ENTER_GATE__",
            "__ARKA_ENTER_ACHERON__",
            "__ARKA_ENTER_ZONE__",
            "__PROTOCOL_WARP_8E__",
        ):
            self.assertIn(ph, eng_src)

        with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
            offs = json.load(f)
        for key in (
            "data_type_info",
            "data_get_instance",
            "unit_enter_gate",
            "arka_enter_acheron",
            "arka_enter_zone",
            "protocol_warp_8e",
        ):
            self.assertIn(key, offs)

        # Kiểm tra meg_gate_navigator.py không có bất kỳ RVA hardcode nào (6-7 hex digits)
        import re
        for fname in ("meg_gate_navigator.py",):
            with open(fname, "r", encoding="utf-8") as f:
                src_check = f.read()
            for lineno, line in enumerate(src_check.splitlines(), 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                code = s.split("#")[0]
                self.assertEqual(re.findall(r"\b0x[0-9A-Fa-f]{6,7}\b", code), [], f"Hardcoded RVA in {fname}:L{lineno}")

    def test_live_cache_overlapping_portals_resolution(self):
        """Kiểm chứng nhận diện đúng cổng Portal chồng lấn từ cache RAM thật của MegaMU."""
        if not os.path.exists("config/world_gates_cache.json"):
            self.skipTest("Chưa có config/world_gates_cache.json")
        cat = GateCatalog()
        self.assertGreater(cat.load_cache(), 500)

        expected = {
            "alka": (418, 419, 91),
            "ubail": (422, 423, 91),
            "deventer": (435, 436, 95),
            "uruk": (450, 451, 100),
            "nars": (487, 488, 110),
            "nixies": (523, 524, 113),
        }
        for alias, (exp_portal, exp_target, exp_map) in expected.items():
            r = cat.resolve_target(alias)
            self.assertTrue(r["ok"], alias)
            self.assertEqual(r["portal_gate_id"], exp_portal, f"{alias} portal")
            self.assertEqual(r["gate_id"], exp_target, f"{alias} target")
            self.assertEqual(r["map_id"], exp_map, f"{alias} map")

    def test_auto_confirm_gate_hook_wired_in_engine(self):
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            eng_src = f.read()
        for sym in (
            "autoGateConfirmEnabled",
            "isGateTeleportDialog",
            "mhelperShowDialogGenericHook",
            "setAutoGateConfirm",
            "getAutoGateConfirmStatus",
            "def set_auto_gate_confirm",
        ):
            self.assertIn(sym, eng_src)

    def test_no_sir_lesnar_c1_f8_30_in_acheron_bootstrap(self):
        """Đảm bảo _bootstrap_to_acheron KHÔNG BAO GIỜ gọi enter_acheron_npc (tránh popup Sir Lesnar)."""
        eng = FakeGateEngine(map_id=0, x=125, y=125)
        called_lesnar = []
        eng.enter_acheron_npc = lambda zone=-1: called_lesnar.append(zone)
        eng.send_chat = lambda msg: False  # Giả lập /move Acheron fail để test fallback
        nav = MegGateNavigator(eng, catalog=GateCatalog(cache_path=""))
        nav._bootstrap_to_acheron()
        self.assertEqual(called_lesnar, [], "Không được gọi C1:F8:30 Sir Lesnar khi bootstrap Acheron!")

    def test_acheron_safe_zone_vs_alkmar_ubaid_detection(self):
        from meg_gate_navigator import is_in_acheron_safe_zone, is_inside_gate_destination
        # Đảo Safe Zone & các cổng vào trên Map 91
        self.assertTrue(is_in_acheron_safe_zone(91, 55, 193))   # Acheron Town
        self.assertTrue(is_in_acheron_safe_zone(91, 84, 204))   # Portal Ubaid #422
        self.assertTrue(is_in_acheron_safe_zone(91, 27, 170))   # Portal Alkmar #418
        self.assertTrue(is_in_acheron_safe_zone(91, 52, 162))   # Portal Debenter #435
        # Bên trong bãi train Alkmar / Ubaid
        self.assertFalse(is_in_acheron_safe_zone(91, 113, 163)) # Alkmar spawn #419
        self.assertFalse(is_in_acheron_safe_zone(91, 153, 199)) # Ubaid spawn #423

        p_ubaid = GateEntry(index=422, flag=1, map_id=91, x=82, y=204, tx=86, ty=205, target_gate=423)
        p_alkmar = GateEntry(index=418, flag=1, map_id=91, x=26, y=168, tx=28, ty=172, target_gate=419)
        self.assertFalse(is_inside_gate_destination("ubaid", 91, p_ubaid, 91, 55, 193))
        self.assertFalse(is_inside_gate_destination("ubaid", 91, p_ubaid, 91, 84, 204))
        self.assertFalse(is_inside_gate_destination("ubaid", 91, p_ubaid, 91, 113, 163))  # Đang ở Alkmar, không phải Ubaid
        self.assertTrue(is_inside_gate_destination("ubaid", 91, p_ubaid, 91, 153, 199))
        self.assertTrue(is_inside_gate_destination("alkmar", 91, p_alkmar, 91, 113, 163))
        self.assertFalse(is_inside_gate_destination("alkmar", 91, p_alkmar, 91, 153, 199))

    def test_auto_worker_full_gate_flow_to_hunting_spot(self):
        """Kiểm chứng AutoTrainWorker tự bật Auto-Confirm -> /move -> qua cổng C1:1C -> chạy tới tọa độ bãi."""
        if not os.path.exists("config/world_gates_cache.json"):
            self.skipTest("Chưa có config/world_gates_cache.json")
        import time as _t
        from meg_auto_worker import AutoTrainWorker

        class MockCore:
            def __init__(self):
                self.auto_gate_confirm = False
                self.chats = []
                self.gates_entered = []
                self.auto_moves = []
                self.map_id = 0
                self.x = 125
                self.y = 125
            def set_auto_gate_confirm(self, enabled=True):
                self.auto_gate_confirm = bool(enabled)
                return {"ok": True, "enabled": self.auto_gate_confirm}
            def is_helper_active(self, force_refresh=False):
                return False
            def stop_helper(self):
                return True
            def cancel_move(self):
                return True
            def send_chat(self, cmd):
                self.chats.append(cmd)
                if "ubaid" in cmd.lower():
                    # Giả lập MegaMU thả nhân vật đúng lên ô cổng Portal #422 (84, 204)
                    self.map_id, self.x, self.y = 91, 84, 204
                return True
            def enter_gate(self, gid, x=-1, y=-1):
                self.gates_entered.append((gid, x, y))
                if gid == 422:
                    # Xuyên cổng #422 -> đáp bên trong Ubaid #423 (153, 199)
                    self.map_id, self.x, self.y = 91, 153, 199
                return {"ok": True}
            def start_auto_move(self, tx, ty, helper=False):
                self.auto_moves.append((tx, ty, helper))
                return True

        worker = AutoTrainWorker.__new__(AutoTrainWorker)
        worker.pid = 99999
        worker.slot_idx = 1
        worker.config = {}
        worker.log_callback = None
        worker.progress_callback = None
        worker.core = MockCore()
        from meg_auto_worker import MapResolver
        worker.map_resolver = MapResolver.get_instance()
        worker.gate_catalog = None
        worker._gate_auto_confirm_armed = False
        worker.last_gate_c11c_time = 0.0
        worker.last_gate_walk_time = 0.0
        worker.last_px = 125
        worker.last_py = 125
        worker.route_map_name = ""
        worker.expected_map_id = None
        worker.current_target = None
        worker.map_move_sent = False
        worker.map_wait_active = False
        worker.map_command_sent_at = 0.0
        worker.map_id_before_command = None
        worker.map_unknown_fallback_at = 0.0
        worker.map_soft_verify_at = 0.0
        worker.arrived_at_spot = False
        worker.respawn_armed = False
        worker.last_dist = None
        worker.last_move_issue = 0.0
        worker.last_stride_time = 0.0
        worker.last_moved_time = 0.0
        worker.bypass_angle_offset = 0.0
        worker.map_sensor_trusted = False
        worker.map_sensor_suspect = False
        worker.map_retry_count = 0
        worker.next_map_retry_at = 0.0
        worker.state_text = ""

        stage = {"map_name": "Ubaid", "x": 185, "y": 215, "min_level": 240, "max_level": 400}

        # Bước 1: Từ Lorencia (0, 125, 125) -> bật Auto-Confirm + gửi /move ubaid -> đáp lên Portal #422 (84, 204)
        worker._go_to_stage(stage, "Test Ubaid", current_map_id=worker.core.map_id, current_coords=(worker.core.x, worker.core.y))
        self.assertTrue(worker.core.auto_gate_confirm)
        self.assertEqual(worker.core.chats, ["/move ubaid"])
        self.assertEqual((worker.core.map_id, worker.core.x, worker.core.y), (91, 84, 204))

        # Bước 2: Đang đứng trên Portal #422 quá 0.9s -> bắn C1:1C xuyên cổng vào Ubaid (153, 199)
        worker.map_command_sent_at = _t.time() - 1.2
        busy = worker._route_map_gate(stage, worker.core.map_id, current_coords=(worker.core.x, worker.core.y))
        self.assertTrue(busy)
        self.assertEqual(worker.core.gates_entered, [(422, 84, 204)])
        self.assertEqual((worker.core.map_id, worker.core.x, worker.core.y), (91, 153, 199))

        # Bước 3: Đã ở bên trong Ubaid (153, 199) -> tự động chạy thẳng tới tọa độ bãi (185, 215)!
        worker._route_map_gate(stage, worker.core.map_id, current_coords=(worker.core.x, worker.core.y))
        self.assertEqual(worker.core.auto_moves, [(185, 215, False)])
        self.assertTrue(worker.map_move_sent)


if __name__ == "__main__":
    unittest.main()
