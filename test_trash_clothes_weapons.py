#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for Trash Clothes & Weapons disposal and safety protections.
Tests both the Frida JS engine rules via Node.js execution and Python API signatures.
"""

import json
import re
import subprocess
import sys
import unittest

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def _extract_engine_protection_js() -> str:
    with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
        src = f.read()

    # Extract isDivineOrDragonItem, isItemProtected, and itemProtectionReason
    d_start = src.find("function isDivineOrDragonItem(itemPtr, itemIndex) {")
    assert d_start > 0, "Could not find isDivineOrDragonItem in meg_direct_engine.py"
    
    # End right after itemProtectionReason function
    reason_start = src.find("function itemProtectionReason(", d_start)
    assert reason_start > 0, "Could not find itemProtectionReason in meg_direct_engine.py"
    
    # Find matching brace for itemProtectionReason
    cur = reason_start
    brace_count = 0
    found_first = False
    while cur < len(src):
        if src[cur] == '{':
            brace_count += 1
            found_first = True
        elif src[cur] == '}':
            brace_count -= 1
            if found_first and brace_count == 0:
                break
        cur += 1
    
    extracted = src[d_start:cur+1]
    return extracted


HARNESS_NODE = r"""
const fs = require('fs');

// Mock getItemName
function getItemName(itemPtr) {
    if (!itemPtr) return "";
    return itemPtr._mockName || "";
}

// Mock memory pointer & reader
function createMockItem(opts) {
    const fields = {
        0x00: opts.index !== undefined ? opts.index : ((opts.section || 0) * 512 + (opts.type || 0)),
        0x10: opts.level !== undefined ? opts.level : 0,
        0x14: opts.skill !== undefined ? opts.skill : 0,
        0x18: opts.luck !== undefined ? opts.luck : 0,
        0x20: opts.excOpt !== undefined ? opts.excOpt : 0,
        0x24: opts.ancOpt !== undefined ? opts.ancOpt : 0,
        0x28: opts.sockOpt !== undefined ? opts.sockOpt : 0,
        0x2C: opts.harmonyOpt !== undefined ? opts.harmonyOpt : 0,
    };
    
    function makePtr(offset) {
        return {
            _mockName: opts.name || "",
            isNull: () => false,
            add: (n) => makePtr(offset + n),
            readS32: () => (fields[offset] !== undefined ? fields[offset] : 0),
            readU8: () => (fields[offset] !== undefined ? fields[offset] & 0xFF : 0),
        };
    }
    return makePtr(0);
}

// Injected functions from meg_direct_engine.py will be placed here
// %INJECTED_JS%

const testCases = JSON.parse(fs.readFileSync(0, 'utf-8'));
const results = [];

for (const tc of testCases) {
    const itemPtr = createMockItem(tc.item);
    const itemIndex = tc.item.index !== undefined ? tc.item.index : ((tc.item.section || 0) * 512 + (tc.item.type || 0));
    const lvl = tc.item.level !== undefined ? tc.item.level : 0;
    const exc = tc.item.excOpt !== undefined ? tc.item.excOpt : 0;
    const anc = tc.item.ancOpt !== undefined ? tc.item.ancOpt : 0;
    const sock = tc.item.sockOpt !== undefined ? tc.item.sockOpt : 0;
    const harm = tc.item.harmonyOpt !== undefined ? tc.item.harmonyOpt : 0;
    const luck = tc.item.luck !== undefined ? tc.item.luck : 0;
    const mossCat = tc.mossCat !== undefined ? tc.mossCat : -1;
    const maxJunkLvl = tc.maxJunkLevel !== undefined ? tc.maxJunkLevel : 6;
    const ignType = tc.ignoreTypeHeuristics || false;
    const cleanEquip = tc.cleanEquipmentTrash !== undefined ? tc.cleanEquipmentTrash : 0;

    // Outer check simulated from analyzeJunkInventory / cleanInventoryJunk
    let prot = false;
    let reason = null;
    if (tc.slot < 12) {
        prot = true;
        reason = "equipped_slot";
    } else if (tc.protectedSlots && tc.protectedSlots.indexOf(tc.slot) !== -1) {
        prot = true;
        reason = "preexisting_snapshot";
    } else {
        prot = isItemProtected(itemPtr, itemIndex, lvl, exc, anc, sock, harm, luck, mossCat, maxJunkLvl, ignType, cleanEquip);
        reason = itemProtectionReason(itemPtr, itemIndex, lvl, exc, anc, sock, harm, luck, mossCat, maxJunkLvl, ignType, cleanEquip);
    }
    results.push({ name: tc.name, protected: prot, reason: reason });
}

console.log(JSON.stringify(results));
"""


class TestTrashClothesWeapons(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.injected_js = _extract_engine_protection_js()

    def run_node_tests(self, test_cases):
        script = HARNESS_NODE.replace("// %INJECTED_JS%", self.injected_js)
        proc = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(test_cases),
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            print("NODE STDERR:", proc.stderr)
            raise RuntimeError(f"Node execution failed: {proc.stderr}")
        return json.loads(proc.stdout)

    def test_clothes_trash_detection_with_clean_equipment_trash(self):
        """Kiểm tra quần áo rác (sections 7..11) được nhận diện là rác khi bật cleanEquipmentTrash."""
        cases = [
            # Leather Pants +0 (sec 9, type 5)
            {
                "name": "Leather Pants +0",
                "slot": 12,
                "item": {"section": 9, "type": 5, "level": 0},
                "mossCat": 0,  # Moss đang chọn Kiếm/Rìu/Giáo
                "cleanEquipmentTrash": 1,
            },
            # Bronze Helm +3 (sec 7, type 0)
            {
                "name": "Bronze Helm +3",
                "slot": 13,
                "item": {"section": 7, "type": 0, "level": 3},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
            # Scale Armor +6 (sec 8, type 6)
            {
                "name": "Scale Armor +6",
                "slot": 14,
                "item": {"section": 8, "type": 6, "level": 6},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
            # Pad Gloves +4 (sec 10, type 2)
            {
                "name": "Pad Gloves +4",
                "slot": 15,
                "item": {"section": 10, "type": 2, "level": 4},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
            # Vine Boots +1 (sec 11, type 10)
            {
                "name": "Vine Boots +1",
                "slot": 16,
                "item": {"section": 11, "type": 10, "level": 1},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
            # Guardian Gloves +0 (sec 10, type 14) -> Set Elf cấp thấp, không được coi là Jewel of Guardian
            {
                "name": "Guardian Gloves +0",
                "slot": 17,
                "item": {"section": 10, "type": 14, "level": 0, "name": "Guardian Gloves"},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
        ]
        results = self.run_node_tests(cases)
        for r in results:
            self.assertFalse(r["protected"], f"Món {r['name']} phải là RÁC (protected=false) khi cleanEquipmentTrash=1, thực tế: protected={r['protected']}, reason={r['reason']}")
            self.assertIsNone(r["reason"])

    def test_weapons_trash_detection_with_clean_equipment_trash(self):
        """Kiểm tra vũ khí rác (sections 0..6) khác danh mục Moss được nhận diện là rác khi bật cleanEquipmentTrash."""
        cases = [
            # Short Sword +0 (sec 0, type 0)
            {
                "name": "Short Sword +0",
                "slot": 12,
                "item": {"section": 0, "type": 0, "level": 0},
                "mossCat": 2,  # Moss đang chọn Gậy phép (Staffs)
                "cleanEquipmentTrash": 1,
            },
            # Tomahawk Axe +2 (sec 1, type 2)
            {
                "name": "Tomahawk Axe +2",
                "slot": 13,
                "item": {"section": 1, "type": 2, "level": 2},
                "mossCat": 2,
                "cleanEquipmentTrash": 1,
            },
            # Crossbow +1 (sec 4, type 8)
            {
                "name": "Crossbow +1",
                "slot": 14,
                "item": {"section": 4, "type": 8, "level": 1},
                "mossCat": 0,  # Moss đang chọn Kiếm
                "cleanEquipmentTrash": 1,
            },
            # Small Shield +0 (sec 6, type 0)
            {
                "name": "Small Shield +0",
                "slot": 15,
                "item": {"section": 6, "type": 0, "level": 0},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
            },
        ]
        results = self.run_node_tests(cases)
        for r in results:
            self.assertFalse(r["protected"], f"Vũ khí {r['name']} phải là RÁC (protected=false) khi cleanEquipmentTrash=1, thực tế: protected={r['protected']}, reason={r['reason']}")
            self.assertIsNone(r["reason"])

    def test_backward_compatibility_clean_equipment_trash_disabled(self):
        """Khi cleanEquipmentTrash=0 (tắt), đồ ngoài danh mục Moss vẫn được giữ nguyên an toàn (wrong_moss_category)."""
        cases = [
            {
                "name": "Leather Pants +0",
                "slot": 12,
                "item": {"section": 9, "type": 5, "level": 0},
                "mossCat": 0,  # Moss chọn Kiếm -> Quần phải bị giữ vì khác danh mục
                "cleanEquipmentTrash": 0,
            },
            {
                "name": "Crossbow +1",
                "slot": 13,
                "item": {"section": 4, "type": 8, "level": 1},
                "mossCat": 0,  # Moss chọn Kiếm -> Nỏ phải bị giữ vì khác danh mục
                "cleanEquipmentTrash": 0,
            },
        ]
        results = self.run_node_tests(cases)
        for r in results:
            self.assertTrue(r["protected"], f"Món {r['name']} phải ĐƯỢC GIỮ khi cleanEquipmentTrash=0")
            self.assertEqual(r["reason"], "wrong_moss_category")

    def test_absolute_protections_always_preserved(self):
        """Kiểm tra các quy tắc bảo vệ tuyệt đối KHÔNG BAO GIỜ bị xóa dù cleanEquipmentTrash=1."""
        cases = [
            # 1. Trang bị trên người (slot 0..11)
            {
                "name": "Equipped Helm (Slot 2)",
                "slot": 2,
                "item": {"section": 7, "type": 0, "level": 0},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "equipped_slot",
            },
            # 2. Đồ Hoàn Hảo (Exc)
            {
                "name": "Leather Pants Exc +0",
                "slot": 12,
                "item": {"section": 9, "type": 5, "level": 0, "excOpt": 1},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "excellent",
            },
            # 3. Đồ Thần / Set (Ancient)
            {
                "name": "Warrior Leather Pants Ancient +0",
                "slot": 13,
                "item": {"section": 9, "type": 5, "level": 0, "ancOpt": 5},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "ancient",
            },
            # 4. Đồ Socket (380 / Socket)
            {
                "name": "Leather Helm Socket +0",
                "slot": 14,
                "item": {"section": 7, "type": 5, "level": 0, "sockOpt": 1},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "socket",
            },
            # 5. Đồ Gia Cường Đá Tạo Hóa (Harmony)
            {
                "name": "Bronze Helm Harmony +0",
                "slot": 15,
                "item": {"section": 7, "type": 0, "level": 0, "harmonyOpt": 1},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "harmony",
            },
            # 6. Đồ cấp cao hơn maxJunkLevel (+7 với maxJunkLevel=6)
            {
                "name": "Scale Armor +7",
                "slot": 16,
                "item": {"section": 8, "type": 6, "level": 7},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "maxJunkLevel": 6,
                "expected_reason": "level_over_max",
            },
            # 7. Ngọc (Jewel of Chaos sec 12, type 15)
            {
                "name": "Jewel of Chaos",
                "slot": 17,
                "item": {"section": 12, "type": 15, "level": 0},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "jewel_section",
            },
            # 8. Cánh (Wings of Dragon sec 12, type 5)
            {
                "name": "Wings of Dragon",
                "slot": 18,
                "item": {"section": 12, "type": 5, "level": 0},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "jewel_section",
            },
            # 9. Đồ Rồng / Divine cao cấp (Dragon Knight Helm)
            {
                "name": "Dragon Knight Helm",
                "slot": 19,
                "item": {"section": 7, "type": 29, "level": 0, "name": "Dragon Knight Helm"},
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "divine_or_dragon",
            },
            # 10. Đồ trong danh sách protectedSlots (snapshot ban đầu)
            {
                "name": "Snapshot Protected Slot 25",
                "slot": 25,
                "item": {"section": 9, "type": 5, "level": 0},
                "protectedSlots": [25],
                "mossCat": 0,
                "cleanEquipmentTrash": 1,
                "expected_reason": "preexisting_snapshot",
            },
        ]
        results = self.run_node_tests(cases)
        for r, tc in zip(results, cases):
            self.assertTrue(r["protected"], f"Món '{tc['name']}' PHẢI ĐƯỢC BẢO VỆ, thực tế lại bị nhận diện là rác!")
            self.assertEqual(r["reason"], tc["expected_reason"], f"Lý do bảo vệ sai cho '{tc['name']}': mong đợi {tc['expected_reason']}, thực tế {r['reason']}")

    def test_python_codebase_integrity(self):
        """Kiểm tra các hàm trong meg_direct_engine.py, meg_gui.py và meg_auto_worker.py đều hỗ trợ clean_equipment_trash."""
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            eng_src = f.read()
        with open("meg_gui.py", "r", encoding="utf-8") as f:
            gui_src = f.read()
        with open("meg_auto_worker.py", "r", encoding="utf-8") as f:
            worker_src = f.read()

        # Engine checks
        self.assertIn("clean_equipment_trash: bool = False", eng_src)
        self.assertIn("cleanEquipmentTrash", eng_src)

        # GUI checks
        self.assertIn("self.cb_clean_equipment_trash", gui_src)
        self.assertIn("moss_clean_equipment_trash", gui_src)
        self.assertIn("clean_equipment_trash", gui_src)

        # Auto Worker checks
        self.assertIn("self.clean_equipment_trash", worker_src)
        self.assertIn("auto_clean_junk", worker_src)


if __name__ == "__main__":
    unittest.main()
