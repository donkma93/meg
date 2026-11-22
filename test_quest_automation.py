#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests cho Auto Nhiệm Vụ Cấp 2 / Marlon / Cấp 3 (`meg_quest_automation.py` + `ui_qt/quest_tab.py`).
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from meg_quest_automation import (
    DEFAULT_QUEST_CONFIG,
    ITEM_CLASS2_PART2,
    ITEM_DARK_STONE,
    ITEM_FEATHER_PHOENIX,
    ITEM_FLAME_DEATH_BEAM,
    ITEM_HORN_HELL_MAINE,
    ITEM_RING_OF_HONOR,
    ITEM_SCROLL_OF_EMPEROR,
    MAP_AIDA,
    MAP_BARRACKS,
    MAP_CRYWOLF,
    MAP_DEVIAS,
    MAP_ICARUS,
    MAP_LOST_TOWER,
    MAP_REFUGE,
    MAP_TARKAN,
    MONSTER_BALRAM,
    MONSTER_DARK_ELF,
    MONSTER_DEATH_SPIRIT,
    MONSTER_SORAM,
    QUEST_STATE_ACCEPT,
    QUEST_STATE_FINISH,
    QUEST_STATE_STANDBY,
    QuestConfigManager,
    QuestSlotRunner,
    _is_subzone_warp_cmd,
    summarize_quest_snapshot,
)


def _snap(
    cls_id=1,
    change_up=0,
    level=150,
    zen=20_000_000,
    states=None,
    items=None,
    kills=None,
    map_id=MAP_DEVIAS,
    x=183,
    y=32,
):
    parsed_items = []
    for i, it in enumerate(items or []):
        if isinstance(it, dict):
            parsed_items.append(it)
        elif isinstance(it, tuple):
            parsed_items.append({"slot": 12 + i, "id": it[0], "level": it[1], "name": it[2] if len(it) > 2 else ""})
        else:
            parsed_items.append({"slot": 12 + i, "id": it, "level": 0, "name": ""})
    return {
        "ok": True,
        "name": "TestHero",
        "class_id": cls_id,
        "change_up": change_up,
        "level": level,
        "zen": zen,
        "states": states or {},
        "quest_items": parsed_items,
        "monster_kills": kills or {},
        "map_id": map_id,
        "x": x,
        "y": y,
    }


class TestQuestSummaryStateMachine(unittest.TestCase):
    def test_class2_full_progression_dk(self):
        # Lv < 150 -> NEED_LEVEL
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=120))
        self.assertEqual(s["next_action"], "NEED_LEVEL")

        # Lv 150, Zen < 1M -> NEED_ZEN
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, zen=500_000))
        self.assertEqual(s["next_action"], "NEED_ZEN")

        # Q0 Standby -> Q0_ACCEPT
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, states={"0": QUEST_STATE_STANDBY}))
        self.assertEqual(s["next_action"], "Q0_ACCEPT")

        # Q0 Accept, no scroll -> Q0_FARM
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, states={"0": QUEST_STATE_ACCEPT}))
        self.assertEqual(s["next_action"], "Q0_FARM")

        # Q0 Accept + Scroll -> Q0_COMPLETE
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, states={"0": QUEST_STATE_ACCEPT}, items=[ITEM_SCROLL_OF_EMPEROR]))
        self.assertEqual(s["next_action"], "Q0_COMPLETE")

        # Q0 Finish, Q1 Standby -> Q1_ACCEPT
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_STANDBY}))
        self.assertEqual(s["next_action"], "Q1_ACCEPT")

        # Q1 Accept -> Q1_FARM -> Q1_COMPLETE (DK/SL chỉ chấp nhận Broken Sword 7192 +0, KHÔNG nhận nhầm Tear of Elf 7193 / Dark Stone 7192 +1)
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=0, level=150, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_ACCEPT}))
        self.assertEqual(s["next_action"], "Q1_FARM")
        s_wrong_elf = summarize_quest_snapshot(_snap(cls_id=9, change_up=0, level=150, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_ACCEPT}, items=[(7193, 0, "Tear of Elf")]))
        self.assertEqual(s_wrong_elf["next_action"], "Q1_FARM")
        s_wrong_ds = summarize_quest_snapshot(_snap(cls_id=9, change_up=0, level=150, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_ACCEPT}, items=[(ITEM_CLASS2_PART2, 1, "Dark Stone")]))
        self.assertEqual(s_wrong_ds["next_action"], "Q1_FARM")
        s = summarize_quest_snapshot(_snap(cls_id=9, change_up=0, level=150, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_ACCEPT}, items=[(ITEM_CLASS2_PART2, 0, "Broken Sword")]))
        self.assertEqual(s["next_action"], "Q1_COMPLETE")

    def test_marlon_dk_includes_dark_stone(self):
        cfg = {"mode": "all_2_3", "include_marlon": True}
        # DK ChangeUp=1, Lv220 -> Q2 Ring of Honor -> Q3 Dark Stone
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=1, level=220), cfg)
        self.assertEqual(s["next_action"], "Q2_ACCEPT")

        # Ring of Honor là Section 14, Index 23, Level 1 (7191 +1)
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=1, level=220, states={"2": QUEST_STATE_ACCEPT}, items=[(ITEM_RING_OF_HONOR, 1, "Ring of Honor")]), cfg)
        self.assertEqual(s["next_action"], "Q2_COMPLETE")

        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=1, level=220, states={"2": QUEST_STATE_FINISH}), cfg)
        self.assertEqual(s["next_action"], "Q3_ACCEPT")

        # Dark Stone là Section 14, Index 24, Level 1 (7192 +1)
        s = summarize_quest_snapshot(_snap(cls_id=1, change_up=1, level=220, states={"2": QUEST_STATE_FINISH, "3": QUEST_STATE_ACCEPT}, items=[(ITEM_DARK_STONE, 1, "Dark Stone")]), cfg)
        self.assertEqual(s["next_action"], "Q3_COMPLETE")

    def test_slayer_marlon_includes_dark_stone(self):
        # Slayer (cls_id=9) sau khi xong Ring of Honor (Q2) vẫn còn Dark Stone (Q3) tại Marlon
        cfg = {"mode": "all_2_3", "include_marlon": True}
        s = summarize_quest_snapshot(_snap(cls_id=9, change_up=1, level=260, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH}), cfg)
        self.assertEqual(s["next_action"], "Q3_ACCEPT")

        s2 = summarize_quest_snapshot(_snap(cls_id=9, change_up=1, level=260, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "3": QUEST_STATE_ACCEPT}), cfg)
        self.assertEqual(s2["next_action"], "Q3_FARM")

        s3 = summarize_quest_snapshot(_snap(cls_id=9, change_up=1, level=260, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "3": QUEST_STATE_ACCEPT}, items=[(ITEM_DARK_STONE, 1, "Dark Stone")]), cfg)
        self.assertEqual(s3["next_action"], "Q3_COMPLETE")

    def test_mg_skips_class2_and_goes_straight_to_class3(self):
        # MG (cls_id=3) at ChangeUp=0, Lv400 skips Sebina and goes straight to Q4 (Priest Devin)
        s = summarize_quest_snapshot(_snap(cls_id=3, change_up=0, level=400))
        self.assertEqual(s["next_action"], "Q4_ACCEPT")

        # class2_only mode for MG -> DONE
        s2 = summarize_quest_snapshot(_snap(cls_id=3, change_up=0, level=200), {"mode": "class2_only"})
        self.assertEqual(s2["next_action"], "DONE")

    def test_class3_full_progression(self):
        # Lv < 400 (kể cả 380 hoặc 399) -> BẮT BUỘC chặn NEED_LEVEL trước khi qua Crywolf gặp Priest Devin
        s_380 = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=380, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH}))
        self.assertEqual(s_380["next_action"], "NEED_LEVEL")
        self.assertIn("400", s_380["progress_text"])

        s_399 = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=399, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH}))
        self.assertEqual(s_399["next_action"], "NEED_LEVEL")

        # Q4 Accept -> Flame -> Horn -> Feather -> Complete (đủ Level 400)
        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_ACCEPT}))
        self.assertEqual(s["next_action"], "Q4_FARM_FLAME")

        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_ACCEPT}, items=[ITEM_FLAME_DEATH_BEAM]))
        self.assertEqual(s["next_action"], "Q4_FARM_HORN")

        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_ACCEPT}, items=[ITEM_FLAME_DEATH_BEAM, ITEM_HORN_HELL_MAINE]))
        self.assertEqual(s["next_action"], "Q4_FARM_FEATHER")

        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_ACCEPT}, items=[ITEM_FLAME_DEATH_BEAM, ITEM_HORN_HELL_MAINE, ITEM_FEATHER_PHOENIX]))
        self.assertEqual(s["next_action"], "Q4_COMPLETE")

        # Q5 Barracks (chuẩn 20 Balram + 20 Death Spirit + 20 Soram)
        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH}))
        self.assertEqual(s["next_action"], "Q5_ACCEPT")

        # 10/10/10 là CHƯA đủ -> vẫn phải tiếp tục Q5_FARM_BARRACKS
        s_ten = summarize_quest_snapshot(
            _snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH, "5": QUEST_STATE_ACCEPT}, kills={str(MONSTER_BALRAM): 10, str(MONSTER_DEATH_SPIRIT): 10, str(MONSTER_SORAM): 10})
        )
        self.assertEqual(s_ten["next_action"], "Q5_FARM_BARRACKS")
        self.assertIn("/20", s_ten["progress_text"])

        s = summarize_quest_snapshot(
            _snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH, "5": QUEST_STATE_ACCEPT}, kills={str(MONSTER_BALRAM): 20, str(MONSTER_DEATH_SPIRIT): 19, str(MONSTER_SORAM): 20})
        )
        self.assertEqual(s["next_action"], "Q5_FARM_BARRACKS")

        s = summarize_quest_snapshot(
            _snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH, "5": QUEST_STATE_ACCEPT}, kills={str(MONSTER_BALRAM): 20, str(MONSTER_DEATH_SPIRIT): 20, str(MONSTER_SORAM): 20})
        )
        self.assertEqual(s["next_action"], "Q5_COMPLETE")

        # Q6 Refuge Dark Elf
        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH, "5": QUEST_STATE_FINISH, "6": QUEST_STATE_ACCEPT}))
        self.assertEqual(s["next_action"], "Q6_FARM_REFUGE")

        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=1, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH, "4": QUEST_STATE_FINISH, "5": QUEST_STATE_FINISH, "6": QUEST_STATE_ACCEPT}, kills={str(MONSTER_DARK_ELF): 1}))
        self.assertEqual(s["next_action"], "Q6_COMPLETE")

        # ChangeUp == 2 -> DONE
        s = summarize_quest_snapshot(_snap(cls_id=0, change_up=2, level=400, states={"0": QUEST_STATE_FINISH, "1": QUEST_STATE_FINISH, "2": QUEST_STATE_FINISH}))
        self.assertEqual(s["next_action"], "DONE")


class _MockQuestEngine:
    """Mock MegDirectEngine mô phỏng toàn bộ hành trình Cấp 2 -> Cấp 3 không cần game thật."""

    def __init__(self):
        self.is_ready = True
        self.map_id = MAP_DEVIAS
        self.x = 183
        self.y = 32
        self.level = 400
        self.class_id = 1  # DK
        self.change_up = 0
        self.zen = 50_000_000
        self.states = {str(i): QUEST_STATE_STANDBY for i in range(7)}
        self.items = []
        self.kills = {}
        self.helper_on = False
        self.actions_log = []

    def get_player_info(self, max_age=0.55, allow_blocking=True):
        # Giống hệt schema thật từ MegDirectEngine.get_player_info(): dùng mapId/tileX/tileY
        return {"mapId": self.map_id, "tileX": self.x, "tileY": self.y, "x": self.x, "y": self.y, "level": self.level, "classId": self.class_id, "changeUp": self.change_up}

    def get_quest_state(self):
        return _snap(
            cls_id=self.class_id,
            change_up=self.change_up,
            level=self.level,
            zen=self.zen,
            states=dict(self.states),
            items=list(self.items),
            kills=dict(self.kills),
            map_id=self.map_id,
            x=self.x,
            y=self.y,
        )

    def send_chat(self, cmd):
        self.actions_log.append(("chat", cmd))
        c = cmd.lower()
        if "devias" in c: self.map_id = MAP_DEVIAS
        elif "losttower" in c: self.map_id = MAP_LOST_TOWER
        elif "tarkan" in c: self.map_id = MAP_TARKAN
        elif "aida" in c: self.map_id = MAP_AIDA
        elif "icarus" in c: self.map_id = MAP_ICARUS
        elif "crywolf" in c: self.map_id = MAP_CRYWOLF

    def start_auto_move(self, tx, ty, helper=False):
        self.x, self.y = int(tx), int(ty)
        return True

    def stop_auto_move(self):
        return True

    def start_helper(self, tx, ty, force_restart=False):
        self.helper_on = True
        # Mô phỏng farm xong ngay vật phẩm / quái tương ứng map hiện tại
        if self.map_id == MAP_LOST_TOWER:
            if self.states["0"] == QUEST_STATE_ACCEPT and ITEM_SCROLL_OF_EMPEROR not in self.items:
                self.items.append(ITEM_SCROLL_OF_EMPEROR)
            elif self.states["1"] == QUEST_STATE_ACCEPT and ITEM_CLASS2_PART2 not in self.items:
                self.items.append(ITEM_CLASS2_PART2)
        elif self.map_id == MAP_TARKAN:
            if self.states["2"] == QUEST_STATE_ACCEPT and not any(isinstance(x, tuple) and x[0] == ITEM_RING_OF_HONOR and x[1] == 1 for x in self.items):
                self.items.append((ITEM_RING_OF_HONOR, 1, "Ring of Honor"))
            elif self.states["3"] == QUEST_STATE_ACCEPT and not any(isinstance(x, tuple) and x[0] == ITEM_DARK_STONE and x[1] == 1 for x in self.items):
                self.items.append((ITEM_DARK_STONE, 1, "Dark Stone"))
            elif self.states["4"] == QUEST_STATE_ACCEPT and ITEM_FLAME_DEATH_BEAM not in self.items:
                self.items.append(ITEM_FLAME_DEATH_BEAM)
        elif self.map_id == MAP_AIDA and self.states["4"] == QUEST_STATE_ACCEPT:
            if ITEM_HORN_HELL_MAINE not in self.items:
                self.items.append(ITEM_HORN_HELL_MAINE)
        elif self.map_id == MAP_ICARUS and self.states["4"] == QUEST_STATE_ACCEPT:
            if ITEM_FEATHER_PHOENIX not in self.items:
                self.items.append(ITEM_FEATHER_PHOENIX)
        elif self.map_id == MAP_BARRACKS and self.states["5"] == QUEST_STATE_ACCEPT:
            self.kills[str(MONSTER_BALRAM)] = 20
            self.kills[str(MONSTER_DEATH_SPIRIT)] = 20
            self.kills[str(MONSTER_SORAM)] = 20
        elif self.map_id == MAP_REFUGE and self.states["6"] == QUEST_STATE_ACCEPT:
            self.kills[str(MONSTER_DARK_ELF)] = 1
        return True

    def stop_helper(self):
        self.helper_on = False
        return True

    def is_helper_active(self):
        return self.helper_on

    def find_npc_by_filter(self, skin_id=-1, name_sub=""):
        return {"found": True, "ptr": "0x1234", "skin": skin_id, "name": name_sub, "x": self.x, "y": self.y, "dist": 1.0}

    def talk_to_npc_by_ptr(self, ptr):
        self.actions_log.append(("talk", ptr))
        self._quest_win_open = True
        return {"ok": True}

    def get_quest_npc_window_state(self):
        return {"ok": True, "isOpen": getattr(self, "_quest_win_open", False), "hasNextBtn": True, "currentData": 0}

    def click_quest_npc_next(self, quest_index=-1):
        self.send_quest_state(quest_index, True)
        self._quest_win_open = False
        return {"done": True, "ok": True, "method": "Button.Press(NextButton)", "qWinOpen": True, "nextBtnFound": True, "currentData": quest_index, "error": ""}

    def send_quest_state(self, quest_index, flag=False):
        self.actions_log.append(("quest_a2", quest_index))
        k = str(quest_index)
        cur = self.states.get(k, QUEST_STATE_STANDBY)
        if cur == QUEST_STATE_STANDBY:
            self.states[k] = QUEST_STATE_ACCEPT
        elif cur == QUEST_STATE_ACCEPT:
            self.states[k] = QUEST_STATE_FINISH
            if quest_index == 1:
                self.change_up = 1
            elif quest_index == 6:
                self.change_up = 2
        return {"ok": True}

    def enter_quest_dungeon(self, dungeon_type):
        self.actions_log.append(("dungeon", dungeon_type))
        if dungeon_type == "barracks":
            self.map_id = MAP_BARRACKS
        elif dungeon_type == "refuge":
            self.map_id = MAP_REFUGE
        return {"ok": True}

    def close_quest_window(self):
        return True

    def pickup_ground_quest_items(self, target_ids, max_radius=14.0, item_level=None, keywords=None):
        return {"ok": True, "pickedCount": 0, "foundItems": []}


class TestQuestRunnerAndConfig(unittest.TestCase):
    def test_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = QuestConfigManager(Path(td))
            cfg = mgr.load()
            cfg["mode"] = "class3_only"
            cfg["spots"]["flame_death_beam"]["x"] = 170
            self.assertTrue(mgr.save(cfg))
            reloaded = mgr.load()
            self.assertEqual(reloaded["mode"], "class3_only")
            self.assertEqual(reloaded["spots"]["flame_death_beam"]["x"], 170)

    def test_e2e_mocked_class2_to_class3_completion(self):
        eng = _MockQuestEngine()
        logs = []
        runner = QuestSlotRunner(
            slot_idx=1,
            engine_getter=lambda: eng,
            config_getter=lambda: DEFAULT_QUEST_CONFIG,
            on_log=lambda m, lvl: logs.append((lvl, m)),
        )
        # Rút ngắn sleep trong unit test
        runner._sleep = lambda _s: not runner._stop_event.is_set()
        runner.start()
        runner._thread.join(timeout=10.0)
        self.assertFalse(runner.running)
        self.assertEqual(eng.change_up, 2)
        self.assertEqual(eng.states["0"], QUEST_STATE_FINISH)
        self.assertEqual(eng.states["1"], QUEST_STATE_FINISH)
        self.assertEqual(eng.states["4"], QUEST_STATE_FINISH)
        self.assertEqual(eng.states["5"], QUEST_STATE_FINISH)
        self.assertEqual(eng.states["6"], QUEST_STATE_FINISH)

    def test_marlon_fixed_in_devias_only(self):
        # Đảm bảo Marlon chỉ cố định tại Devias cạnh Sebina, không nhảy sang Lorencia/Noria/Atlans
        marlon_cfg = DEFAULT_QUEST_CONFIG["npcs"]["marlon"]
        self.assertEqual(marlon_cfg["map_id"], MAP_DEVIAS)
        self.assertEqual(marlon_cfg["map_cmd"], "/move devias")
        self.assertNotIn("marlon_spots", DEFAULT_QUEST_CONFIG["npcs"])

        eng = _MockQuestEngine()
        eng.change_up = 1
        eng.level = 220
        eng.map_id = MAP_DEVIAS
        eng.states["0"] = QUEST_STATE_FINISH
        eng.states["1"] = QUEST_STATE_FINISH
        cfg = dict(DEFAULT_QUEST_CONFIG)
        cfg["mode"] = "marlon_only"
        runner = QuestSlotRunner(
            slot_idx=1,
            engine_getter=lambda: eng,
            config_getter=lambda: cfg,
        )
        runner._sleep = lambda _s: not runner._stop_event.is_set()
        ok = runner._find_and_interact_marlon(eng, cfg, 2, QUEST_STATE_ACCEPT, "Nhận Ring of Honor")
        self.assertTrue(ok)
        warped_cmds = [cmd.lower() for kind, cmd in eng.actions_log if kind == "chat"]
        for forbidden in ("lorencia", "noria", "atlans"):
            self.assertFalse(any(forbidden in c for c in warped_cmds))

    def test_auto_walk_and_pickup_dropped_quest_item(self):
        # Giả lập Scroll of Emperor rơi cách nhân vật 8 ô -> bot phải tự chạy tới (58, 98) rồi gọi pickup_ground_quest_items
        eng = _MockQuestEngine()
        eng.map_id = MAP_LOST_TOWER
        eng.x, eng.y = 53, 93
        eng.states["0"] = QUEST_STATE_ACCEPT
        eng.helper_on = True
        picked_coords = []

        def _no_auto_drop_helper(tx, ty, force_restart=False):
            eng.helper_on = True
            return True

        def _mock_pick(target_ids, max_radius=14.0, item_level=None, keywords=None):
            dist = ((58 - eng.x) ** 2 + (98 - eng.y) ** 2) ** 0.5
            if dist <= 3.0:
                picked_coords.append((eng.x, eng.y))
                eng.items.append(ITEM_SCROLL_OF_EMPEROR)
                return {"ok": True, "pickedCount": 1, "foundItems": [{"vIdx": 77, "id": ITEM_SCROLL_OF_EMPEROR, "name": "Scroll of Emperor", "x": 58, "y": 98, "dist": dist}]}
            return {"ok": True, "pickedCount": 0, "foundItems": [{"vIdx": 77, "id": ITEM_SCROLL_OF_EMPEROR, "name": "Scroll of Emperor", "x": 58, "y": 98, "dist": dist}]}

        eng.start_helper = _no_auto_drop_helper
        eng.pickup_ground_quest_items = _mock_pick

        runner = QuestSlotRunner(slot_idx=1, engine_getter=lambda: eng, config_getter=lambda: DEFAULT_QUEST_CONFIG)
        runner._sleep = lambda _s: not runner._stop_event.is_set()
        ok = runner._farm_until_item(eng, DEFAULT_QUEST_CONFIG, "scroll_emperor", ITEM_SCROLL_OF_EMPEROR, "Scroll of Emperor")
        self.assertTrue(ok)
        self.assertEqual(picked_coords, [(58, 98)])

    def test_subzone_warp_cmd_detection(self):
        self.assertFalse(_is_subzone_warp_cmd("/move icarus"))
        self.assertFalse(_is_subzone_warp_cmd("/move tarkan"))
        self.assertFalse(_is_subzone_warp_cmd("/move losttower"))
        self.assertFalse(_is_subzone_warp_cmd("/move losttower1"))
        self.assertFalse(_is_subzone_warp_cmd(""))
        self.assertTrue(_is_subzone_warp_cmd("/move losttower7"))
        self.assertTrue(_is_subzone_warp_cmd("/move losttower 7"))
        self.assertTrue(_is_subzone_warp_cmd("/move tarkan2"))
        self.assertTrue(_is_subzone_warp_cmd("/move aida2"))

    def test_icarus_does_not_rewarp_or_start_helper_prematurely(self):
        # Đã ở Icarus cổng (15, 13), bãi Phoenix ở (37, 238) cách ~226 ô (> 48 ô):
        # Tuyệt đối KHÔNG gửi lại `/move icarus` và KHÔNG bật Helper giữa đường khi _move_to_coord chưa tới bãi!
        eng = _MockQuestEngine()
        eng.map_id = MAP_ICARUS
        eng.x, eng.y = 15, 13
        eng.level = 400
        eng.change_up = 1
        eng.states["4"] = QUEST_STATE_ACCEPT

        helper_start_positions = []
        orig_start_helper = eng.start_helper

        def _tracked_start_helper(tx, ty, force_restart=False):
            helper_start_positions.append((eng.x, eng.y))
            return orig_start_helper(tx, ty, force_restart=force_restart)

        eng.start_helper = _tracked_start_helper

        runner = QuestSlotRunner(slot_idx=1, engine_getter=lambda: eng, config_getter=lambda: DEFAULT_QUEST_CONFIG)
        runner._sleep = lambda _s: not runner._stop_event.is_set()

        # Giả lập lượt đi bộ 1 mới tới giữa cầu (28, 120) rồi timeout (trả False); lượt 2 đi tới đúng (37, 238) (trả True)
        move_calls = []

        def _step_move(_eng, tx, ty, arrive_dist=3.5, timeout_s=40.0, expected_map_id=None, **_kw):
            move_calls.append((eng.x, eng.y, tx, ty))
            if len(move_calls) == 1:
                eng.x, eng.y = 28, 120
                return False
            eng.x, eng.y = int(tx), int(ty)
            return True

        runner._move_to_coord = _step_move

        ok = runner._farm_until_item(
            eng, DEFAULT_QUEST_CONFIG, "feather_phoenix", ITEM_FEATHER_PHOENIX, "Feather of Dark Phoenix",
            name_keywords=("feather of", "phoenix"),
        )
        self.assertTrue(ok)
        # Không bao giờ gửi /move icarus khi đã ở trong Icarus!
        chat_cmds = [cmd for kind, cmd in eng.actions_log if kind == "chat"]
        self.assertEqual(chat_cmds, [])
        # Phải đi 2 lượt (15,13)->(28,120) rồi (28,120)->(37,238), không bị kéo về (15,13)
        self.assertEqual(move_calls, [(15, 13, 37, 238), (28, 120, 37, 238)])
        # Chỉ bật Helper đúng 1 lần sau khi đã đứng tại (37, 238), KHÔNG bật giữa cầu (28, 120)
        self.assertEqual(helper_start_positions, [(37, 238)])

    def test_barracks_farms_20_each_across_3_distinct_zones(self):
        # Mô phỏng 3 khu vực Barracks tách biệt: mỗi vị trí chỉ có đúng 1 loại quái -> bắt buộc di chuyển qua đủ 3 bãi và đạt 20/20/20
        eng = _MockQuestEngine()
        eng.map_id = MAP_BARRACKS
        eng.x, eng.y = 28, 76  # cổng vào Barracks
        eng.level = 400
        eng.change_up = 1
        eng.states["4"] = QUEST_STATE_FINISH
        eng.states["5"] = QUEST_STATE_ACCEPT

        spots = DEFAULT_QUEST_CONFIG["spots"]
        z1 = (spots["barracks_balram"]["x"], spots["barracks_balram"]["y"])
        z2 = (spots["barracks_death_spirit"]["x"], spots["barracks_death_spirit"]["y"])
        z3 = (spots["barracks_soram"]["x"], spots["barracks_soram"]["y"])
        # Đảm bảo 3 khu vực khác nhau hoàn toàn
        self.assertEqual(len({z1, z2, z3}), 3)

        farmed_zones = []

        def _zone_specific_helper(tx, ty, force_restart=False):
            eng.helper_on = True
            pos = (eng.x, eng.y)
            farmed_zones.append(pos)
            if pos == z1:
                eng.kills[str(MONSTER_BALRAM)] = 20
            elif pos == z2:
                eng.kills[str(MONSTER_DEATH_SPIRIT)] = 20
            elif pos == z3:
                eng.kills[str(MONSTER_SORAM)] = 20
            return True

        eng.start_helper = _zone_specific_helper

        runner = QuestSlotRunner(slot_idx=1, engine_getter=lambda: eng, config_getter=lambda: DEFAULT_QUEST_CONFIG)
        runner._sleep = lambda _s: not runner._stop_event.is_set()
        ok = runner._farm_barracks(eng, DEFAULT_QUEST_CONFIG)
        self.assertTrue(ok)
        self.assertEqual(farmed_zones, [z1, z2, z3])
        self.assertEqual(eng.kills[str(MONSTER_BALRAM)], 20)
        self.assertEqual(eng.kills[str(MONSTER_DEATH_SPIRIT)], 20)
        self.assertEqual(eng.kills[str(MONSTER_SORAM)], 20)

    def test_dark_elf_and_barracks_notice_parser_in_js(self):
        # Xác minh hàm recordQuestNoticeText trong meg_direct_engine.py bắt chính xác thông báo xanh C1:0D (VD: "Dark Elf ( 1/1", Death Spirit, Soram)
        import json, re, subprocess
        src = Path("meg_direct_engine.py").read_text(encoding="utf-8")
        m = re.search(r"var questNoticeKills = \{\};[\s\S]*?function recordQuestNoticeText\(rawText\) \{[\s\S]*?\n\}", src)
        self.assertIsNotNone(m, "Không tìm thấy recordQuestNoticeText trong meg_direct_engine.py")
        js_harness = (
            m.group(0)
            + """
var r1 = recordQuestNoticeText("Dark Elf ( 1/1");
var r2 = recordQuestNoticeText("Balram (Trainee Soldier) ( 14/20");
var r3 = recordQuestNoticeText("<color=#55aaff>Death Spirit (Trainee Soldier) ( 20/20)</color>");
var r4 = recordQuestNoticeText("Soram ( 20/20");
var r5 = recordQuestNoticeText("You are at the max level");
var r6 = recordQuestNoticeText("Death Spirit ( 5/20");
var r7 = recordQuestNoticeText("DeathSpirit ( 8 / 20");
var r8 = recordQuestNoticeText("Spirit ( 10/20");
var r9 = recordQuestNoticeText("Soram (Trainee Soldier) ( 12/20");
console.log(JSON.stringify({r1, r2, r3, r4, r5, r6, r7, r8, r9, kills: questNoticeKills, req: questNoticeReq}));
"""
        )
        proc = subprocess.run(["node", "-e", js_harness], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout.strip())
        self.assertTrue(out["r1"])
        self.assertTrue(out["r2"])
        self.assertTrue(out["r3"])
        self.assertTrue(out["r4"])
        self.assertFalse(out["r5"])
        self.assertTrue(out["r6"])
        self.assertTrue(out["r7"])
        self.assertTrue(out["r8"])
        self.assertTrue(out["r9"])
        self.assertEqual(out["kills"]["412"], 1)
        self.assertEqual(out["kills"]["409"], 14)
        self.assertEqual(out["kills"]["410"], 20)
        self.assertEqual(out["kills"]["411"], 20)


class TestQuestTabQtHeadless(unittest.TestCase):
    def test_qt_tab_instantiation_and_state_update(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui_qt.quest_tab import QuestTabQt, QuestSpotsDialogQt

        app = QApplication.instance() or QApplication(sys.argv)

        class _DummyCtrl:
            def __init__(self, idx):
                self.slot_idx = idx

        tab = QuestTabQt(controllers=[_DummyCtrl(1), _DummyCtrl(2)])
        self.assertEqual(tab.table.rowCount(), 2)
        # Verify dict-based AppStateManager snapshot updates character name
        tab.update_from_state_snapshots({1: {"char_name": "SlayerLive", "assigned_pid": 9999}})
        self.assertEqual(tab.table.item(0, 2).text(), "SlayerLive (#9999)")

        summary = summarize_quest_snapshot(_snap(cls_id=1, change_up=1, level=400, states={"4": QUEST_STATE_ACCEPT}, items=[ITEM_FLAME_DEATH_BEAM]))
        tab.set_slot_quest_state(1, {"running": True, "status_text": "Đang farm Horn", "status_color": "#2dd4bf", "summary": summary, "pid": 9999})
        self.assertIn("TestHero (#9999)", tab.table.item(0, 2).text())
        self.assertIn("DK (Cấp 2)", tab.table.item(0, 3).text())
        self.assertIn("400", tab.table.item(0, 4).text())
        self.assertEqual(tab._rows[1]["btn_toggle"].text(), "⏹ Dừng")

        dlg = QuestSpotsDialogQt(tab.get_config())
        updated = dlg.get_updated_config()
        self.assertIn("flame_death_beam", updated["spots"])
        tab.close()
        dlg.close()


if __name__ == "__main__":
    unittest.main()
