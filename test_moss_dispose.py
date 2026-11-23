"""Kiểm thử hành vi pipeline dọn rác Moss v2 (disposeJunkItems).

Test này KHÔNG chỉ grep source: nó trích JS thật từ meg_direct_engine.py, dựng một
mô hình bộ nhớ giả (inventory/slot/item) rồi chạy bằng Node.js để kiểm chứng:

  1. Ngoài safe-zone  -> vứt được, không bán.
  2. Trong safe-zone  -> vứt bị server bỏ qua, tự chuyển sang bán, bán sạch.
  3. Safe-zone + chưa mở Merchant -> báo đúng reason "drop_blocked", không mất đồ.
  4. Không có rác -> reason "no_candidates".
  5. Đồ được bảo vệ (level >= 7) và slot trang bị (0..11) không bao giờ bị đụng.
  6. Trần batch (maxBatch) được tôn trọng.
"""

import subprocess
import unittest


def _extract_js() -> str:
    with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
        src = f.read()

    h_start = src.find("function isMerchantWindowOpen() {")
    h_end = src.find("function sendMirrorEnterPacket(slot) {")
    assert h_start > 0 and h_end > h_start, "Không tìm thấy khối helper disposal"

    d_start = src.find("disposeJunkItems: function(mode")
    d_end = src.find("dropInventorySlot: function(slot, offX, offY)")
    assert d_start > 0 and d_end > d_start, "Không tìm thấy disposeJunkItems"

    helpers = src[h_start:h_end]
    dispose = src[d_start:d_end].rstrip()
    while dispose.endswith(","):
        dispose = dispose[:-1].rstrip()

    return helpers + "\nvar __api = {\n" + dispose + "\n};\n"


HARNESS = r"""
// ------------------------- mô hình bộ nhớ giả -------------------------
const OFF = {};
let offSeq = 0x1000;
function off(name) {
    if (!(name in OFF)) { OFF[name] = offSeq; offSeq += 8; }
    const v = OFF[name];
    return { __v: v, isNull() { return false; }, valueOf() { return v; }, toString() { return String(v); } };
}
function readVal(obj, o) {
    if (!obj || !obj.__f) return 0;
    return Object.prototype.hasOwnProperty.call(obj.__f, o) ? obj.__f[o] : 0;
}
function W(obj, o) {
    return {
        __obj: obj, __off: o,
        isNull() { return !obj; },
        add(n) { return W(obj, (+o) + (+n)); },
        readPointer() { return W(readVal(obj, o), 0); },
        readS32() { const v = readVal(obj, o); return (v | 0); },
        readU8() { return readVal(obj, o) & 0xFF; },
        writeS32() {}, writeU8() {}, writeFloat() {}, writePointer() {},
        equals(other) { return !!other && other.__obj === obj; },
    };
}
function ptr(v) { return W(typeof v === "number" ? { __f: {} } : v, 0); }

let ID = 1;
function obj(fields) { return { __id: ID++, __f: fields || {} }; }

const SLOTS = 140;
const STATE = {
    safeZone: true,
    merchantOpen: false,
    gsOk: true,
    items: new Array(SLOTS).fill(null),
    dropCalls: [],
    sellCalls: [],
};

function item(level, index) {
    return obj({ 0x10: level, 0x14: 0, 0x18: 0, 0x20: 0, 0x24: 0, 0x28: 0, 0x2C: 0, __index: index });
}

function buildWorld() {
    const itemsArr = obj({ 0x18: SLOTS });
    for (let s = 0; s < SLOTS; s++) {
        if (STATE.items[s]) itemsArr.__f[0x20 + s * 8] = STATE.items[s];
    }
    const inv = obj({});
    inv.__f[off("__INVENTORY_ITEMS__")] = itemsArr;

    const coord = obj({ 0x10: 22, 0x14: 225 });
    const player = obj({});
    player.__f[off("__PLAYER_INVENTORY__")] = inv;
    player.__f[off("__PLAYER_COORD__")] = coord;
    player.__f[off("__PLAYER_LAST_COORD__")] = coord;

    const mossWin = obj({});
    const mossMWin = obj({ 0x48: 1 });
    mossWin.__f[0x20] = mossMWin;

    const merchant = STATE.merchantOpen ? obj({}) : null;
    let merchantMWin = null;
    if (merchant) {
        merchantMWin = obj({ 0x48: 1 });
        merchant.__f[0x20] = merchantMWin;
    }

    const gui = obj({});
    gui.__f[off("__UI_MOSS_WINDOW__")] = mossWin;
    gui.__f[off("__UI_MERCHANT_WINDOW__")] = merchant;

    return { player, gui, itemsArr };
}

let WORLD = null;
var nativeUserInvDrop = null;   // test chạy đường packet thuần
var lastSendError = "";
var _dropRecvSeq = 0;
var _dropRecvBySlot = {};
function getPlayerPtr() { return W(WORLD.player, 0); }
function getGSConnection() { return W(STATE.gsOk ? obj({}) : null, 0); }
const nativeGetGameUI = () => W(WORLD.gui, 0);
const Thread = { sleep() {} };
function ensureThreadAttached() {}
function ensureDropAllowed() {}
function readItemIndex(p) { return p.__obj ? p.__obj.__index : -1; }

// Bộ lọc bảo vệ giả lập: level >= 7 giữ lại, còn lại là rác.
function isItemProtected(itemPtr, itemIndex, itemLevel) { return itemLevel >= 7; }

function clearSlot(slot) {
    STATE.items[slot] = null;
    if (WORLD && WORLD.itemsArr) delete WORLD.itemsArr.__f[0x20 + slot * 8];
}

function sendDropPacket(slot, tx, ty) {
    STATE.dropCalls.push({ slot, tx, ty });
    if (STATE.safeZone) return true;          // server nhận gói nhưng KHÔNG rơi đồ
    clearSlot(slot);
    return true;
}
function sendSellPacket(slot) {
    STATE.sellCalls.push(slot);
    if (!STATE.merchantOpen) return true;     // không có shop -> server bỏ qua
    clearSlot(slot);
    return true;
}

// ------------------------- test cases -------------------------
function reset(items, opts) {
    STATE.items = new Array(SLOTS).fill(null);
    for (const k in (items || {})) STATE.items[parseInt(k)] = items[k];
    STATE.dropCalls = [];
    STATE.sellCalls = [];
    STATE.safeZone = !!(opts || {}).safeZone;
    STATE.merchantOpen = !!(opts || {}).merchantOpen;
    STATE.gsOk = (opts || {}).gsOk !== false;
    WORLD = buildWorld();
}

function check(name, cond, detail) {
    if (!cond) {
        console.error("FAILED: " + name + (detail ? " -> " + detail : ""));
        process.exit(1);
    }
    console.log("ok - " + name);
}

// 1) Ngoài safe-zone: vứt sạch, không bán
reset({ 12: item(0, 100), 13: item(3, 101), 14: item(6, 102) }, { safeZone: false, merchantOpen: false });
let r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("drop ngoài safe-zone", r.cleaned === 3 && r.dropped === 3 && r.sold === 0 && r.reason === "done", JSON.stringify(r));
check("drop thực sự gọi 3 gói", STATE.dropCalls.length >= 3, JSON.stringify(STATE.dropCalls));

// 2) Trong safe-zone + Merchant mở: tự chuyển sang bán
reset({ 12: item(0, 100), 13: item(4, 101) }, { safeZone: true, merchantOpen: true });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("safe-zone -> tự bán", r.cleaned === 2 && r.dropped === 0 && r.sold === 2 && r.reason === "done", JSON.stringify(r));
check("có gọi bán 2 slot", STATE.sellCalls.length >= 2, JSON.stringify(STATE.sellCalls));

// 3) Trong safe-zone + chưa mở Merchant: báo đúng lý do, KHÔNG mất đồ
reset({ 12: item(0, 100) }, { safeZone: true, merchantOpen: false });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("safe-zone + no merchant -> drop_blocked", r.cleaned === 0 && r.reason === "drop_blocked" && r.failed === 1, JSON.stringify(r));
check("đồ vẫn còn nguyên", STATE.items[12] !== null, "item bị mất!");

// 4) Không có rác
reset({}, { safeZone: true });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("không có rác", r.cleaned === 0 && r.reason === "no_candidates", JSON.stringify(r));

// 5) Bảo vệ: slot 0..11 và đồ level >= 7
reset({ 5: item(0, 1), 12: item(7, 102), 13: item(0, 103) }, { safeZone: false });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("không đụng slot trang bị", STATE.items[5] !== null, "slot 5 bị xóa!");
check("không đụng đồ +7", STATE.items[12] !== null, "item +7 bị xóa!");
check("chỉ dọn đúng 1 món rác", r.cleaned === 1 && r.dropped === 1, JSON.stringify(r));

// 6) Tôn trọng maxBatch
const many = {};
for (let i = 0; i < 10; i++) many[20 + i] = item(0, 200 + i);
reset(many, { safeZone: false });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 4));
check("maxBatch = 4", r.total === 4 && r.dropped === 4, JSON.stringify(r));

// 7) Mất GS -> báo no_gs_connection, không gửi gói
reset({ 12: item(0, 100) }, { safeZone: false, gsOk: false });
r = JSON.parse(__api.disposeJunkItems("auto", "[]", -1, 1, 6, 40));
check("mất GS", r.cleaned === 0 && r.reason === "no_gs_connection", JSON.stringify(r));

console.log("ALL_PASSED");
"""


class TestMossDispose(unittest.TestCase):
    def test_dispose_pipeline(self):
        js = _extract_js() + HARNESS
        proc = subprocess.run(["node"], input=js, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"Node test failed:\n{proc.stderr}\n{proc.stdout}")
        self.assertIn("ALL_PASSED", proc.stdout)

    def test_protection_reason_matches_is_protected(self):
        """itemProtectionReason() phải cho cùng kết quả với isItemProtected() khi không bật ignoreType.

        Đây là chốt chống phân kỳ: bảng phân tích dùng reason, pipeline dọn rác dùng reason,
        còn code cũ vẫn dùng isItemProtected — hai bên phải luôn khớp nhau.
        """
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            src = f.read()
        start = src.find("function isDivineOrDragonItem")
        end = src.find("var nativeGetGameUI = null;")
        self.assertGreater(start, 0)
        self.assertGreater(end, start)
        block = src[start:end]

        runner = (
            'function getItemName(p){ return (p && p.name) ? p.name : ""; }\n'
            + block
            + r"""
const cases = [
    { n: "Dark Stinger Bow", idx: 4*512+24, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 1, cat: 2 },
    { n: "Albatross Bow",    idx: 4*512+22, lvl: 4, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 2 },
    { n: "Brilliant Sword",  idx: 0*512+5,  lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    { n: "Lightning Axe",    idx: 1*512+3,  lvl: 2, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    { n: "Type 35 item",     idx: 0*512+35, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    { n: "Slot +7",          idx: 0*512+5,  lvl: 7, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    { n: "Exc item",         idx: 0*512+5,  lvl: 0, exc: 1, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    { n: "Jewel",            idx: 14*512+15, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Wrong category",   idx: 2*512+10, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: 0 },
    // Lưới an toàn theo TÊN: ngọc/vé/rương/cánh phải bị giữ dù Index đọc sai (= 0)
    { n: "Jewel of Bless",   idx: 0, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Jewel of Chaos",   idx: 0, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Jewel of Harmony", idx: 0, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Devil Square Ticket", idx: 0, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Mirror of Dimensions", idx: 0, lvl: 0, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 },
    { n: "Box of Luck",      idx: 0, lvl: 6, exc: 0, anc: 0, sock: 0, harm: 0, luck: 0, cat: -1 }
];
let bad = 0;
for (const c of cases) {
    const prot = isItemProtected({ name: c.n }, c.idx, c.lvl, c.exc, c.anc, c.sock, c.harm, c.luck, c.cat, 6);
    const reason = itemProtectionReason({ name: c.n }, c.idx, c.lvl, c.exc, c.anc, c.sock, c.harm, c.luck, c.cat, 6, false);
    const derived = reason !== null;
    if (prot !== derived) {
        console.error("MISMATCH " + c.n + " isItemProtected=" + prot + " reason=" + reason);
        bad++;
    }
    if (prot && !reason) {
        console.error("MISSING REASON " + c.n);
        bad++;
    }
}
// Bật ignoreType: 2 món bị lọc theo tên/loại phải trở thành dọn được
const r1 = itemProtectionReason({ name: "Brilliant Sword" }, 0*512+5, 0, 0, 0, 0, 0, 0, 0, 6, true);
const r2 = itemProtectionReason({ name: "Type 35 item" }, 0*512+35, 0, 0, 0, 0, 0, 0, 0, 6, true);
if (r1 !== null) { console.error("ignoreType không bỏ qua lọc tên: " + r1); bad++; }
if (r2 !== null) { console.error("ignoreType không bỏ qua lọc loại: " + r2); bad++; }
// Nhưng vẫn phải giữ Exc / cấp cao / ngọc
if (itemProtectionReason(null, 0*512+5, 0, 1, 0, 0, 0, 0, 0, 6, true) !== "excellent") { console.error("ignoreType vẫn phải giữ Exc"); bad++; }
if (itemProtectionReason(null, 0*512+5, 9, 0, 0, 0, 0, 0, 0, 6, true) !== "level_over_max") { console.error("ignoreType vẫn phải giữ cấp cao"); bad++; }
if (itemProtectionReason(null, 14*512+15, 0, 0, 0, 0, 0, 0, -1, 6, true) !== "jewel_section") { console.error("ignoreType vẫn phải giữ ngọc"); bad++; }

if (bad) process.exit(1);
console.log("PROTECTION_MATCH_OK");
"""
        )
        proc = subprocess.run(["node", "-e", runner], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"Node test failed:\n{proc.stderr}\n{proc.stdout}")
        self.assertIn("PROTECTION_MATCH_OK", proc.stdout)

    def test_sell_plus5_to_7_and_excellent_excluding_dragon_and_true_socket(self):
        """Kiểm thử bán đồ +5..+7 và đồ Excellent (allowExcellent=true) với bảng ID MEGAMU chuẩn:
        - Bán được: đồ thường +5..+7, đồ Exce thường (+0..+7), các món từng bị ID sai chặn nhầm (Spiked Shield [6,7], Nikea Axe [1,6], Grand Soul [7,18]).
        - LUÔN GIỮ: mọi Đồ Rồng (ID chuẩn từ TableItem RAM), Divine/Archangel, Đồ Thần (Ancient), Đồ Socket thật (+0x38), Harmony/380, cấp >= +8, Ngọc/Vé.
        """
        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            src = f.read()
        start = src.find("function isDivineOrDragonItem")
        end = src.find("var nativeGetGameUI = null;")
        self.assertGreater(start, 0)
        self.assertGreater(end, start)
        block = src[start:end]

        runner = (
            'function getItemName(p){ return (p && p.name) ? p.name : ""; }\n'
            + block
            + r"""
function makeSocketPtr(slots, name) {
    const arr = {
        isNull() { return false; },
        add(o) {
            return {
                readS32() {
                    if (o === 0x18) return slots.length;
                    const idx = (o - 0x20) / 4;
                    return (idx >= 0 && idx < slots.length) ? slots[idx] : 255;
                }
            };
        }
    };
    return {
        name: name || "",
        isNull() { return false; },
        add(o) {
            return {
                readPointer() { return o === 0x38 ? arr : { isNull() { return true; } }; }
            };
        }
    };
}

function assertReason(label, got, expected) {
    if (got !== expected) {
        console.error("FAIL [" + label + "]: expected=" + expected + " got=" + got);
        process.exit(1);
    }
}

// 1) Đồ Rồng chuẩn TableItem MEGAMU -> LUÔN GIỮ dù allowExcellent=true và ignoreType=true!
const dragonCases = [
    ["Dragon Helm (7,1)", 7*512+1, "Dragon Helm"],
    ["Black Dragon Armor (8,16)", 8*512+16, "Black Dragon Armor"],
    ["Great Dragon Pants (9,21)", 9*512+21, "Great Dragon Pants"],
    ["Dragon Knight Gloves (10,29)", 10*512+29, "Dragon Knight Gloves"],
    ["Dragon Boots ext (11,67)", 11*512+67, "Dragon Boots"],
    ["Bound Dragon Helm (7,130)", 7*512+130, "[Bound] Dragon Helm"],
    ["Dragon Slayer Shield (6,5)", 6*512+5, "Dragon Slayer Shield"],
    ["Dragon Shield (6,13)", 6*512+13, "Dragon Shield"],
    ["Chaos Dragon Axe (2,6)", 2*512+6, "Chaos Dragon Axe"],
    ["Dragon Lance (3,2)", 3*512+2, "Dragon Lance"],
    ["Dragon Spear (3,10)", 3*512+10, "Dragon Spear"],
    ["Dragon Soul Staff (5,9)", 5*512+9, "Dragon Soul Staff"],
    ["Dragon by ID only (no name)", 6*512+13, ""],
    ["Dragon by Name only", 0*512+5, "Super Dragon Blade"],
];
for (const [lbl, idx, nm] of dragonCases) {
    const r = itemProtectionReason({ name: nm }, idx, 6, 1, 0, 0, 0, 1, -1, 7, true, true, true);
    assertReason(lbl, r, "dragon_item");
}

// 2) Divine / Archangel -> LUÔN GIỮ kể cả khi allowExcellent=true
assertReason("Divine Sword (0,19)", itemProtectionReason({ name: "Divine Sword of Archangel" }, 0*512+19, 6, 1, 0, 0, 0, 1, -1, 7, false, true, true), "divine_or_dragon");
assertReason("Divine Helm (7,50)", itemProtectionReason({ name: "Divine Helm" }, 7*512+50, 5, 1, 0, 0, 0, 0, -1, 7, false, true, true), "divine_or_dragon");

// 3) Đồ +5..+7 thường & Đồ Excellent KHÔNG phải Rồng -> BÁN ĐƯỢC (reason === null) khi allowExcellent=true!
const sellableCases = [
    ["Normal Sword +5", 0*512+5, "Blade", 5, 0],
    ["Normal Bow +7", 4*512+22, "Albatross Bow", 7, 0],
    ["Exc Sword +0", 0*512+5, "Blade", 0, 1],
    ["Exc Sword +7", 0*512+10, "Light Saber", 7, 3],
    ["Spiked Shield (6,7) Exc +6 (was misclassified)", 6*512+7, "Spiked Shield", 6, 1],
    ["Nikea Axe (1,6) Exc +5 (was misclassified)", 1*512+6, "Nikea Axe", 5, 1],
    ["Grand Soul Helm (7,18) Exc +7 (was misclassified)", 7*512+18, "Grand Soul Helm", 7, 2],
    ["Type 35 normal Exc +6", 0*512+35, "Crystal Sword", 6, 1],
];
for (const [lbl, idx, nm, lvl, exc] of sellableCases) {
    const r = itemProtectionReason({ name: nm }, idx, lvl, exc, 0, 0, 0, 1, -1, 7, false, true, true);
    assertReason(lbl, r, null);
}

// 4) Các chốt bảo vệ khác vẫn giữ chặt kể cả khi allowExcellent=true:
assertReason("Exc +8 over max", itemProtectionReason({ name: "Blade" }, 0*512+5, 8, 1, 0, 0, 0, 1, -1, 7, false, true, true), "level_over_max");
assertReason("Ancient +6", itemProtectionReason({ name: "Hyon Sword" }, 0*512+5, 6, 0, 5, 0, 0, 1, -1, 7, false, true, true), "ancient");
assertReason("Harmony +6", itemProtectionReason({ name: "Blade" }, 0*512+5, 6, 1, 0, 0, 12, 1, -1, 7, false, true, true), "harmony");
assertReason("True Socket (+0x38 empty 0xFE)", itemProtectionReason(makeSocketPtr([254, 255, 255, 255, 255], "Brave Helm"), 7*512+45, 5, 0, 0, 0, 0, 0, -1, 7, false, true, true), "socket");
assertReason("Non-Socket (+0x38 all 0xFF) Exc +5 sellable", itemProtectionReason(makeSocketPtr([255, 255, 255, 255, 255], "Blade"), 0*512+5, 5, 1, 0, 0, 0, 0, -1, 7, false, true, true), null);
assertReason("Jewel of Bless", itemProtectionReason({ name: "Jewel of Bless" }, 14*512+13, 0, 0, 0, 0, 0, 0, -1, 7, false, true, true), "jewel_section");

console.log("EXCE_DRAGON_SOCKET_OK");
"""
        )
        proc = subprocess.run(["node", "-e", runner], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"Node test failed:\n{proc.stderr}\n{proc.stdout}")
        self.assertIn("EXCE_DRAGON_SOCKET_OK", proc.stdout)

    def test_sell_protocol_c3_33_and_selling_slot_and_rhea_npc(self):
        """Kiểm chứng 4 sửa lỗi cốt lõi:
        1. config/megamu_offsets.json trỏ user_inv_sell -> 0x1450640 (AFCIKPDMOCC = C3:33 SELL, KHÔNG phải 0x14521D0 BUY).
        2. sendSellPacket gửi đúng C3:33 (0x33 ^ 0xCB = 0xF8) và gán ItemStorage.SellingSlot (+0x20) bằng layout Dictionary Entry (+0x08 key, +0x10 value) trên cả MainStorage (+0x58), Ext1 (+0x60), Ext2 (+0x68).
        3. findMerchantNpc nhận diện NPC Rhea (class=416, pos=29,236) ngay ELB1 (30,235), loại tuyệt đối Priest James (class=725, pos=32,239) và Moss (22,225), đồng thời vẫn chọn Silvia (44,229) khi đứng gần Silvia.
        4. Không còn ép mwObj+0x48 = 1 trong dismissExpensiveSellWindow().
        """
        import json
        with open("config/megamu_offsets.json", "r", encoding="utf-8") as f:
            offs = json.load(f)
        self.assertEqual(offs.get("user_inv_sell"), "0x1450640")

        with open("meg_direct_engine.py", "r", encoding="utf-8") as f:
            src = f.read()

        # Verify sendSellPacket + findInventorySlotObj + setItemStorageSellingSlot via Node
        s1 = src.find("function findInventorySlotObj(slot)")
        e1 = src.find("// MOSS JUNK DISPOSAL ENGINE (v2)")
        self.assertGreater(s1, 0)
        self.assertGreater(e1, s1)
        sell_block = src[s1:e1]

        s2 = src.find("function findMerchantNpc()")
        e2 = src.find("try {\n    var guiUpdateOff")
        if e2 == -1:
            e2 = src.find("try {\r\n    var guiUpdateOff")
        self.assertGreater(s2, 0)
        self.assertGreater(e2, s2)
        npc_block = src[s2:e2]

        # Ensure dismissExpensiveSellWindow no longer writes mwObj.add(0x48).writeU8(1)
        s3 = src.find("function dismissExpensiveSellWindow()")
        e3 = src.find("function dispatchSellSlotOnMainThread", s3)
        self.assertGreater(s3, 0)
        self.assertGreater(e3, s3)
        self.assertNotIn("writeU8(1)", src[s3:e3])

        runner = (
            r"""
function ptr(v) {
    if (v && typeof v === "object" && v.__ptr) return v;
    const n = (typeof v === "string") ? parseInt(v, 16) : (v || 0);
    return {
        __ptr: true, addr: n, _mem: {},
        isNull() { return this.addr === 0; },
        equals(o) { return o && o.addr === this.addr; },
        add(off) {
            const d = (typeof off === "object" && off.__ptr) ? off.addr : (typeof off === "string" ? parseInt(off, 16) : off);
            return makePtr(this.addr + d, this._store);
        }
    };
}
const STORE = new Map();
function makePtr(addr, store) {
    const s = store || STORE;
    return {
        __ptr: true, addr, _store: s,
        isNull() { return addr === 0; },
        equals(o) { return o && o.addr === addr; },
        add(off) {
            const d = (typeof off === "object" && off.__ptr) ? off.addr : (typeof off === "string" ? parseInt(off, 16) : off);
            return makePtr(addr + d, s);
        },
        readPointer() { return s.get(addr) || makePtr(0, s); },
        writePointer(p) { s.set(addr, p); },
        readS32() { const v = s.get(addr); return typeof v === "number" ? v : 0; },
        readU8() { const v = s.get(addr); return typeof v === "number" ? v : 0; },
        readUtf16String(len) { return s.get(addr) || ""; },
    };
}
function alloc(base) { return makePtr(base, STORE); }
function off(name) {
    const map = {
        __UI_INVENTORY_WINDOW__: 0x190,
        __ITEM_STORAGE_TYPE_INFO__: 0x5574B18,
        __GAME_TYPE_INFO__: 0x55A4D00,
        __VIEWPORT__: 0x110,
        __PLAYER_COORD__: 0x68,
        __PLAYER_CLASS__: 0x34,
        __PLAYER_NAME__: 0x28,
    };
    return makePtr(map[name] || 0, STORE);
}
const baseAddr = makePtr(0x10000000, STORE);
let SENT_PKTS = [];
var nativeUserInvSell = null;
function ensureThreadAttached() {}
function _getLiveItemsArraySafe() { return makePtr(0, STORE); }
function sendGSPacket(bytes, xored) { SENT_PKTS.push({ bytes, xored }); return true; }

// Build fake GameUI -> MInventoryWindow -> MainStorage (+0x58: slot 15), Ext1 (+0x60: slot 80), Ext2 (+0x68: slot 112)
const GUI = alloc(0x200000);
const INV_WIN = alloc(0x210000);
GUI.add(0x190).writePointer(INV_WIN);
function nativeGetGameUI() { return GUI; }

const IS_TI = alloc(0x220000);
const IS_STATIC = alloc(0x221000);
baseAddr.add(0x5574B18).writePointer(IS_TI);
IS_TI.add(0xB8).writePointer(IS_STATIC);

function buildStorage(stAddr, dictAddr, entAddr, slotList) {
    const st = alloc(stAddr);
    const dict = alloc(dictAddr);
    const ent = alloc(entAddr);
    st.add(0x38).writePointer(dict);
    dict.add(0x18).writePointer(ent);
    STORE.set(dictAddr + 0x20, slotList.length);
    slotList.forEach((sl, idx) => {
        const slotObj = alloc(stAddr + 0x5000 + idx * 0x100);
        STORE.set(slotObj.addr + 0x20, sl); // SlotNumber
        const e = ent.add(0x20 + idx * 24);
        STORE.set(e.addr + 0x00, sl);       // hashCode >= 0
        STORE.set(e.addr + 0x04, -1);       // next
        STORE.set(e.addr + 0x08, sl);       // int key (verified +0x08!)
        e.add(0x10).writePointer(slotObj);  // ItemSlot* value (verified +0x10!)
    });
    return st;
}
INV_WIN.add(0x58).writePointer(buildStorage(0x300000, 0x301000, 0x302000, [12, 15, 20]));
INV_WIN.add(0x60).writePointer(buildStorage(0x310000, 0x311000, 0x312000, [76, 80]));
INV_WIN.add(0x68).writePointer(buildStorage(0x320000, 0x321000, 0x322000, [108, 112]));
"""
            + sell_block
            + r"""
// Check 1: Main slot 15, Ext1 slot 80, Ext2 slot 112 all set SellingSlot & send C3:33 (0xF8)
for (const sl of [15, 80, 112]) {
    SENT_PKTS = [];
    IS_STATIC.add(0x20).writePointer(makePtr(0, STORE));
    const ok = sendSellPacket(sl);
    const ss = IS_STATIC.add(0x20).readPointer();
    if (!ok || ss.isNull() || ss.add(0x20).readS32() !== sl) {
        console.error("SellingSlot FAILED for slot", sl, ok, ss.addr);
        process.exit(1);
    }
    if (SENT_PKTS.length !== 1) { console.error("Expected 1 pkt, got", SENT_PKTS); process.exit(1); }
    const b = SENT_PKTS[0].bytes;
    if (!(b[0] === 0xC3 && b[1] === 0x04 && b[2] === (0x33 ^ 0xCB) && b[3] === sl)) {
        console.error("Wrong C3:33 sell packet:", b);
        process.exit(1);
    }
}
// Check 2: Equipped slot < 12 blocked
if (sendSellPacket(5) !== false) { console.error("Equipped slot 5 must be blocked!"); process.exit(1); }

// Check 3: findMerchantNpc with Rhea (29,236, class=416), Priest James (32,239, class=725), Moss (22,225, class=492), Silvia (44,229, class=415)
const GAME_TI = alloc(0x400000);
const GAME_SF = alloc(0x401000);
const GAME_INST = alloc(0x402000);
const VP = alloc(0x403000);
const OD = alloc(0x404000);
const ENT = alloc(0x405000);
const PLAYER = alloc(0x406000);
const PCOORD = alloc(0x406100);
baseAddr.add(0x55A4D00).writePointer(GAME_TI);
GAME_TI.add(0xB8).writePointer(GAME_SF);
GAME_SF.add(0x08).writePointer(GAME_INST);
GAME_INST.add(0x110).writePointer(VP);
VP.add(0x20).writePointer(OD);
OD.add(0x18).writePointer(ENT);
PLAYER.add(0x68).writePointer(PCOORD);
function getPlayerPtr() { return PLAYER; }

const CLASS_NAMES = new Map();
function getIl2CppClassNameSafe(p) { return CLASS_NAMES.get(p.addr) || ""; }

const npcs = [
    { key: 4334, cls: 492, name: "Moss", x: 22, y: 225 },
    { key: 4345, cls: 725, name: "Priest James", x: 32, y: 239 },
    { key: 4335, cls: 416, name: "Rhea", x: 29, y: 236 },
    { key: 4350, cls: 415, name: "Silvia", x: 44, y: 229 },
];
STORE.set(OD.addr + 0x20, npcs.length);
npcs.forEach((n, i) => {
    const vpBody = alloc(0x500000 + i * 0x1000);
    const body = alloc(0x500200 + i * 0x1000);
    const coord = alloc(0x500400 + i * 0x1000);
    const nstr = alloc(0x500600 + i * 0x1000);
    CLASS_NAMES.set(vpBody.addr, "ViewportBody");
    CLASS_NAMES.set(body.addr, "MonsterBody");
    vpBody.add(0x18).writePointer(body);
    STORE.set(body.addr + 0x20, n.key);
    STORE.set(body.addr + 0x34, n.cls);
    STORE.set(body.addr + 0xC0, 0);
    body.add(0x28).writePointer(nstr);
    STORE.set(nstr.addr + 0x10, n.name.length);
    STORE.set(nstr.addr + 0x14, n.name);
    body.add(0x68).writePointer(coord);
    STORE.set(coord.addr + 0x10, n.x);
    STORE.set(coord.addr + 0x14, n.y);
    const e = ENT.add(0x20 + i * 24);
    STORE.set(e.addr + 0x00, i + 1);
    e.add(16).writePointer(vpBody);
});
"""
            + npc_block
            + r"""
// Standing at ELB1 (30, 235) -> must pick Rhea (29, 236), NEVER Priest James!
STORE.set(PCOORD.addr + 0x10, 30); STORE.set(PCOORD.addr + 0x14, 235);
let found = findMerchantNpc();
if (!found || found.name !== "Rhea" || found.x !== 29 || found.y !== 236) {
    console.error("Expected Rhea at (30,235), got:", found);
    process.exit(1);
}
// Standing at Moss (22, 225) -> must pick Rhea (29, 236)
STORE.set(PCOORD.addr + 0x10, 22); STORE.set(PCOORD.addr + 0x14, 225);
found = findMerchantNpc();
if (!found || found.name !== "Rhea") {
    console.error("Expected Rhea from Moss (22,225), got:", found);
    process.exit(1);
}
// Standing right next to Priest James (32, 239) -> still picks Rhea, NEVER Priest James!
STORE.set(PCOORD.addr + 0x10, 32); STORE.set(PCOORD.addr + 0x14, 239);
found = findMerchantNpc();
if (!found || found.name === "Priest James" || found.classId === 725) {
    console.error("Must NEVER pick Priest James:", found);
    process.exit(1);
}
// Standing at Silvia (44, 229) -> picks Silvia
STORE.set(PCOORD.addr + 0x10, 44); STORE.set(PCOORD.addr + 0x14, 229);
found = findMerchantNpc();
if (!found || found.name !== "Silvia") {
    console.error("Expected Silvia at (44,229), got:", found);
    process.exit(1);
}
console.log("SELL_C3_33_AND_RHEA_OK");
"""
        )
        proc = subprocess.run(["node", "-e", runner], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"Node test failed:\n{proc.stderr}\n{proc.stdout}")
        self.assertIn("SELL_C3_33_AND_RHEA_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
