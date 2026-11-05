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
        proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", errors="replace")
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



if __name__ == "__main__":
    unittest.main()
