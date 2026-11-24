#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit & Integration Tests cho Auto Report PK (meg_pk_reporter + meg_direct_engine + Qt6 UI).
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import meg_pk_reporter as mpr

BASE_DIR = Path(__file__).resolve().parent


class FakePkEngine:
    """Giả lập MegDirectEngine để kiểm thử trọn vẹn luồng về thành tìm Lính Canh & Report."""

    def __init__(
        self,
        initial_map: int = 7,  # Atlans
        killer_name: str = "BadPKer",
        guard_by_town: dict = None,
        clear_killer_on_talk: bool = True,
        confirm_dialog_on_talk: bool = False,
        guard_appears_after_moves: int = 1,
    ):
        self.is_ready = True
        self.map_id = initial_map
        self.x = 120
        self.y = 120
        self.hp = 1500
        self.is_dead = False
        self.killer_name = killer_name
        self.pk_window_open = False
        self.confirm_count = 0
        self.guard_by_town = guard_by_town if guard_by_town is not None else {
            3: {"found": True, "ptr": "0x123450", "skin": 247, "name": "Crossbow Guard", "x": 167, "y": 118, "dist": 1.8},
        }
        self.clear_killer_on_talk = clear_killer_on_talk
        self.confirm_dialog_on_talk = confirm_dialog_on_talk
        self.guard_appears_after_moves = guard_appears_after_moves
        self.move_calls_in_town = 0
        self.chat_sent = []
        self.talked_ptrs = []
        self.auto_confirm_history = []
        self.closed_pk_window = False
        self.stopped_helper = False

    def stop_helper(self):
        self.stopped_helper = True
        return True

    def stop_auto_move(self):
        return True

    def cancel_move(self):
        return True

    def send_chat(self, msg: str):
        self.chat_sent.append(msg)
        low = msg.strip().lower()
        if low == "/m lorencia":
            self.map_id, self.x, self.y = 0, 125, 125
            self.move_calls_in_town = 0
        elif low == "/m devias":
            self.map_id, self.x, self.y = 2, 210, 40
            self.move_calls_in_town = 0
        elif low == "/m noria":
            self.map_id, self.x, self.y = 3, 174, 110
            self.move_calls_in_town = 0
        return True

    def get_player_info(self, max_age=0.15):
        return {"mapId": self.map_id, "tileX": self.x, "tileY": self.y}

    def start_auto_move(self, tx: int, ty: int, helper: bool = False):
        self.move_calls_in_town += 1
        self.x, self.y = int(tx), int(ty)
        return True

    def move_to(self, tx: int, ty: int):
        return self.start_auto_move(tx, ty)

    def find_guard_npc(self):
        if self.move_calls_in_town < self.guard_appears_after_moves:
            return {"found": False}
        g = self.guard_by_town.get(self.map_id)
        if not g:
            return {"found": False}
        res = dict(g)
        dx = res["x"] - self.x
        dy = res["y"] - self.y
        res["dist"] = round((dx * dx + dy * dy) ** 0.5, 1)
        return res

    def get_pk_report_status(self):
        return {
            "ok": True,
            "hp": self.hp,
            "isDead": self.is_dead,
            "deathCount": 1,
            "killCount": 0,
            "killerName": self.killer_name,
            "mapId": self.map_id,
            "x": self.x,
            "y": self.y,
            "pkWindowOpen": self.pk_window_open,
            "autoReportConfirmCount": self.confirm_count,
        }

    def set_auto_confirm_report(self, enabled: bool = True, killer_name: str = ""):
        self.auto_confirm_history.append((bool(enabled), str(killer_name)))
        return {"ok": True, "enabled": bool(enabled)}

    def talk_to_npc_by_ptr(self, npc_ptr):
        self.talked_ptrs.append(str(npc_ptr))
        if self.clear_killer_on_talk:
            self.killer_name = ""
        if self.confirm_dialog_on_talk:
            self.confirm_count += 1
        return {"ok": True}

    def close_pk_window(self):
        self.closed_pk_window = True
        self.pk_window_open = False
        return True


class TestPkReportCore(unittest.TestCase):
    def test_01_town_normalization_and_order(self):
        self.assertEqual(mpr.normalize_town_key("Davias"), "devias")
        self.assertEqual(mpr.normalize_town_key("DEVIAS"), "devias")
        self.assertEqual(mpr.normalize_town_key("noria"), "noria")
        self.assertEqual(mpr.normalize_town_key("lorencia"), "lorencia")
        self.assertEqual(mpr.normalize_town_key("unknown"), "auto")

        # Auto khi đang ở Noria -> ưu tiên Noria trước
        self.assertEqual(
            mpr.resolve_report_town_order("auto", current_map_id=mpr.MAP_NORIA, fallback_towns=True),
            ["noria", "lorencia", "devias"],
        )
        # Auto khi đang ở Devias -> ưu tiên Devias trước
        self.assertEqual(
            mpr.resolve_report_town_order("auto", current_map_id=mpr.MAP_DEVIAS, fallback_towns=True),
            ["devias", "lorencia", "noria"],
        )
        # Auto khi đang ở map train (Atlans = 7) -> Lorencia -> Noria -> Devias
        self.assertEqual(
            mpr.resolve_report_town_order("auto", current_map_id=7, fallback_towns=True),
            ["lorencia", "noria", "devias"],
        )
        # Chỉ định Davias, tắt fallback -> chỉ đi devias
        self.assertEqual(
            mpr.resolve_report_town_order("davias", current_map_id=0, fallback_towns=False),
            ["devias"],
        )

    def test_02_config_manager_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = mpr.PkReportConfigManager(Path(td))
            default_cfg = mgr.load()
            self.assertTrue(default_cfg["enabled"])
            self.assertEqual(default_cfg["town"], "auto")

            ok = mgr.save({
                "enabled": False,
                "town": "Davias",
                "only_when_killer_known": False,
                "fallback_towns": False,
                "max_duration_s": 40.0,
            })
            self.assertTrue(ok)
            loaded = mgr.load()
            self.assertFalse(loaded["enabled"])
            self.assertEqual(loaded["town"], "devias")
            self.assertFalse(loaded["only_when_killer_known"])
            self.assertFalse(loaded["fallback_towns"])
            self.assertEqual(loaded["max_duration_s"], 40.0)

    def test_03_skip_monster_death_when_only_pk_enabled(self):
        eng = FakePkEngine(initial_map=7, killer_name="")
        res = mpr.execute_pk_report(
            eng,
            cfg={"enabled": True, "town": "noria", "only_when_killer_known": True},
            killer_name="",
            force=False,
        )
        self.assertTrue(res["ok"])
        self.assertFalse(res["reported"])
        self.assertTrue(res.get("skipped"))
        self.assertEqual(eng.chat_sent, [])

    def test_04_full_noria_pk_report_flow(self):
        eng = FakePkEngine(
            initial_map=7,
            killer_name="RedKiller",
            guard_by_town={
                3: {"found": True, "ptr": "0xABCD01", "skin": 247, "name": "Crossbow Guard", "x": 167, "y": 118, "dist": 10.0}
            },
            clear_killer_on_talk=True,
            guard_appears_after_moves=1,
        )
        logs = []
        with mock.patch("meg_pk_reporter._sleep_check", return_value=True):
            res = mpr.execute_pk_report(
                eng,
                cfg={"enabled": True, "town": "noria", "only_when_killer_known": True, "fallback_towns": True},
                killer_name="RedKiller",
                log_cb=lambda m, lv: logs.append((lv, m)),
            )

        self.assertTrue(res["ok"])
        self.assertTrue(res["reported"])
        self.assertEqual(res["town"], "noria")
        self.assertEqual(res["killer_name"], "RedKiller")
        self.assertEqual(res["method"], "killer_cleared")
        self.assertIn("/m noria", eng.chat_sent)
        self.assertEqual(eng.talked_ptrs, ["0xABCD01"])
        # Phải bật auto-confirm trước và tắt sau khi xong
        self.assertEqual(eng.auto_confirm_history[0], (True, "RedKiller"))
        self.assertEqual(eng.auto_confirm_history[-1], (False, ""))
        self.assertTrue(eng.closed_pk_window)

    def test_05_fallback_lorencia_to_devias_when_guard_missing(self):
        eng = FakePkEngine(
            initial_map=7,
            killer_name="ShadowPK",
            guard_by_town={
                # Lorencia (0) & Noria (3) không có lính canh, Devias (2) có Berdysh Guard
                2: {"found": True, "ptr": "0xDEADB1", "skin": 249, "name": "Berdysh Guard", "x": 209, "y": 30, "dist": 1.5}
            },
            clear_killer_on_talk=False,
            confirm_dialog_on_talk=True,
            guard_appears_after_moves=0,
        )
        with mock.patch("meg_pk_reporter._sleep_check", return_value=True):
            res = mpr.execute_pk_report(
                eng,
                cfg={"enabled": True, "town": "lorencia", "fallback_towns": True, "max_duration_s": 55.0},
                killer_name="ShadowPK",
            )

        self.assertTrue(res["ok"])
        self.assertTrue(res["reported"])
        self.assertEqual(res["town"], "devias")
        self.assertEqual(res["method"], "confirm_dialog")
        self.assertIn("/m lorencia", eng.chat_sent)
        self.assertIn("/m noria", eng.chat_sent)
        self.assertIn("/m devias", eng.chat_sent)
        self.assertEqual(eng.talked_ptrs, ["0xDEADB1"])
        self.assertTrue(eng.closed_pk_window)

    def test_06_frida_js_guard_filter_and_dialog_matcher_in_node(self):
        engine_src = (BASE_DIR / "meg_direct_engine.py").read_text(encoding="utf-8")
        self.assertIn("findGuardNpc: function()", engine_src)
        self.assertIn("getPkReportStatus: function()", engine_src)
        self.assertIn("setAutoConfirmReport: function(enabled, killerName)", engine_src)
        self.assertIn("closePkWindow: function()", engine_src)
        self.assertIn("def find_guard_npc(", engine_src)
        self.assertIn("def get_pk_report_status(", engine_src)
        self.assertIn("def set_auto_confirm_report(", engine_src)
        self.assertIn("def close_pk_window(", engine_src)

        # Kiểm tra logic lọc dialog _isPkReportDialogText và Guard NPC filter trực tiếp bằng Node.js
        m_fn = re.search(r"(function _isPkReportDialogText\(idStr, title, msg\) \{[\s\S]*?\n\})", engine_src)
        self.assertIsNotNone(m_fn, "Không tìm thấy hàm _isPkReportDialogText trong meg_direct_engine.py")

        node_script = (
            "var _autoReportKillerName = 'BadPKer';\n"
            + m_fn.group(1)
            + "\n"
            + """
const assert = require('assert');
assert.strictEqual(_isPkReportDialogText('', 'Guard', 'Do you want to report BadPKer?'), true);
assert.strictEqual(_isPkReportDialogText('', 'Denúncia', 'Deseja denunciar este jogador?'), true);
assert.strictEqual(_isPkReportDialogText('', 'Notice', 'BadPKer killed you'), true);
assert.strictEqual(_isPkReportDialogText('', 'Shop', 'Buy Apple for 100 Zen?'), false);
console.log('NODE_PK_DIALOG_OK');
"""
        )
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, f"Node test failed: {proc.stderr}")
        self.assertIn("NODE_PK_DIALOG_OK", proc.stdout)

    def test_07_zero_offset_leak_in_pk_reporter(self):
        src = (BASE_DIR / "meg_pk_reporter.py").read_text(encoding="utf-8")
        # Không được chứa hằng số RVA 6-8 chữ số hex
        rvas = re.findall(r"\b0x[0-9a-fA-F]{6,8}\b", src)
        self.assertEqual(rvas, [], f"Phát hiện rò rỉ RVA trong meg_pk_reporter.py: {rvas}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
