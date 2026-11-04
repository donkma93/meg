"""
Unit tests for core.storage: ConfigPersistenceManager and atomic JSON persistence.
"""

import sys
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import (
    ConfigPersistenceManager,
    atomic_write_json,
    PROFILE_FILE,
    SLOT_ASSIGNMENTS_FILE,
    MOSS_CONFIG_FILE,
    MIRROR_CONFIG_FILE,
    EVENT_CONFIG_FILE,
    CLASS_STAT_PROFILES_FILE,
)


class TestConfigPersistenceManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for config tests
        self.temp_dir = tempfile.mkdtemp()
        t_path = Path(self.temp_dir)
        import core.storage as cs
        self._orig_files = {
            "PROFILE_FILE": cs.PROFILE_FILE,
            "SLOT_ASSIGNMENTS_FILE": cs.SLOT_ASSIGNMENTS_FILE,
            "MOSS_CONFIG_FILE": cs.MOSS_CONFIG_FILE,
            "MIRROR_CONFIG_FILE": cs.MIRROR_CONFIG_FILE,
            "EVENT_CONFIG_FILE": cs.EVENT_CONFIG_FILE,
            "CLASS_STAT_PROFILES_FILE": cs.CLASS_STAT_PROFILES_FILE,
            "DEFAULT_CONFIG_FILE": cs.DEFAULT_CONFIG_FILE,
        }
        cs.PROFILE_FILE = t_path / "autotrain_profiles.json"
        cs.SLOT_ASSIGNMENTS_FILE = t_path / "slot_assignments.json"
        cs.MOSS_CONFIG_FILE = t_path / "moss_slots_config.json"
        cs.MIRROR_CONFIG_FILE = t_path / "mirror_schedule_config.json"
        cs.EVENT_CONFIG_FILE = t_path / "event_slots_config.json"
        cs.CLASS_STAT_PROFILES_FILE = t_path / "class_stat_profiles.json"
        cs.DEFAULT_CONFIG_FILE = t_path / "autotrain_megamu_config.json"

    def tearDown(self):
        import core.storage as cs
        for k, v in self._orig_files.items():
            setattr(cs, k, v)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_fallback_config(self):
        cfg = ConfigPersistenceManager.get_fallback_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("stages", cfg)
        self.assertEqual(len(cfg["stages"]), 4)
        self.assertEqual(cfg["stages"][0]["map_name"], "Lorencia")
        self.assertIn("glide_speed", cfg)

    def test_load_profiles_store_integrity(self):
        store = ConfigPersistenceManager.load_profiles_store()
        self.assertIsInstance(store, dict)
        self.assertIn("profiles", store)
        self.assertEqual(store.get("version"), 2)
        # Verify Config 1 to 10 exist
        for idx in range(1, 11):
            s_idx = str(idx)
            self.assertIn(s_idx, store["profiles"])
            self.assertIn("config", store["profiles"][s_idx])
            self.assertIn("stages", store["profiles"][s_idx]["config"])

    def test_load_and_save_single_profile(self):
        # Load profile 3
        orig_p3 = ConfigPersistenceManager.load_single_profile(3)
        self.assertIsInstance(orig_p3, dict)
        self.assertIn("stages", orig_p3)

        # Modify and save
        modified = dict(orig_p3)
        modified["glide_speed"] = 4.2
        ConfigPersistenceManager.save_single_profile(3, modified)

        # Reload and verify
        reloaded = ConfigPersistenceManager.load_single_profile(3)
        self.assertEqual(reloaded["glide_speed"], 4.2)

        # Restore
        ConfigPersistenceManager.save_single_profile(3, orig_p3)

    def test_slot_assignments(self):
        assignments = ConfigPersistenceManager.load_slot_assignments(min_slots=5)
        self.assertIsInstance(assignments, dict)
        self.assertGreaterEqual(len(assignments), 5)
        self.assertIn(1, assignments)

        # Save and verify
        orig_val = assignments.get(1, 1)
        test_val = 4 if orig_val != 4 else 5
        ConfigPersistenceManager.save_slot_assignment(1, test_val)
        updated = ConfigPersistenceManager.load_slot_assignments(min_slots=5)
        self.assertEqual(updated.get(1), test_val)

        # Restore
        ConfigPersistenceManager.save_slot_assignment(1, orig_val)

    def test_moss_configs(self):
        moss_cfgs = ConfigPersistenceManager.load_moss_configs()
        self.assertIsInstance(moss_cfgs, dict)

        ConfigPersistenceManager.save_moss_config(1, cat=2, delay_ms=800, max_rolls=10, auto_clean=True)
        updated = ConfigPersistenceManager.load_moss_configs()
        self.assertIn(1, updated)
        self.assertEqual(updated[1]["category"], 2)
        self.assertEqual(updated[1]["delay_ms"], 800)
        self.assertEqual(updated[1]["max_rolls"], 10)
        self.assertTrue(updated[1]["auto_clean"])

    def test_mirror_schedule_config(self):
        cfg = ConfigPersistenceManager.load_mirror_schedule_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("auto_schedule", cfg)
        self.assertIn("prefire_sec", cfg)

        ConfigPersistenceManager.save_mirror_schedule_config(
            auto_schedule=True,
            auto_prep_before=True,
            prefire_sec=1.5,
            auto_lifecycle=True,
            auto_gremory=True,
            selected_slots=[1, 2, 3]
        )
        updated = ConfigPersistenceManager.load_mirror_schedule_config()
        self.assertEqual(updated["prefire_sec"], 1.5)
        self.assertEqual(updated["selected_slots"], [1, 2, 3])

    def test_event_configs(self):
        ev = ConfigPersistenceManager.load_event_configs()
        self.assertIsInstance(ev, dict)

        ConfigPersistenceManager.save_event_config(
            slot_idx=1,
            auto_devil=True,
            devil_min_resets=5,
            devil_max_resets=50,
            devil_ticket_type="master",
            auto_reset=True,
            auto_add_point=False,
            reset_level=400,
            stat_mode="custom",
            custom_class="DK"
        )
        updated = ConfigPersistenceManager.load_event_configs()
        self.assertIn(1, updated)
        self.assertTrue(updated[1]["auto_devil"])
        self.assertEqual(updated[1]["devil_min_resets"], 5)
        self.assertEqual(updated[1]["devil_max_resets"], 50)
        self.assertEqual(updated[1]["devil_ticket_type"], "master")
        self.assertTrue(updated[1]["auto_reset"])

    def test_atomic_write_safety(self):
        test_file = Path(self.temp_dir) / "sub" / "test_atomic.json"
        sample_data = {"key": "value", "list": [1, 2, 3], "unicode": "Tiếng Việt có dấu"}

        success = atomic_write_json(test_file, sample_data)
        self.assertTrue(success)
        self.assertTrue(test_file.exists())

        import json
        read_back = json.loads(test_file.read_text(encoding="utf-8"))
        self.assertEqual(read_back, sample_data)


if __name__ == "__main__":
    unittest.main()
