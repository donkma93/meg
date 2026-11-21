import json
import os
import subprocess
import tempfile
import threading
import unittest

import meg_direct_engine as mde


def _make_dummy_engine():
    eng = mde.MegDirectEngine.__new__(mde.MegDirectEngine)
    eng.pid = 99999
    eng._rpc_lock = threading.RLock()
    eng.session = None
    eng.script = None
    eng.is_ready = True
    eng._mutex_handle = None
    eng._last_attach_attempt = 0.0
    eng._attach_fail_count = 0
    eng.last_fast_state = None
    eng.last_fast_state_time = 0.0
    eng.last_fast_seq = 0
    eng.telemetry_callbacks = []
    eng.offsets = dict(mde.DEFAULT_OFFSETS)
    eng._load_offsets_file()
    return eng


NODE_MOSS_DROP_HARNESS = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const jsPath = process.argv[2];
const code = fs.readFileSync(jsPath, "utf8");
const DEFAULT_OFFSETS = JSON.parse(process.argv[3]);

let nextPtrAddr = 0x20000000;
const memMap = new Map();

function ensureBuf(addr, minSize) {
    const k = Number(addr);
    let b = memMap.get(k);
    if (!b || b.length < minSize) {
        b = Buffer.alloc(Math.max(256, minSize || 256));
        memMap.set(k, b);
    }
    return b;
}

class MockPtr {
    constructor(val) { this._val = Number(val) >>> 0; }
    isNull() { return this._val === 0; }
    add(off) { return new MockPtr((this._val + ((off instanceof MockPtr) ? off._val : Number(off))) >>> 0); }
    sub(off) { return new MockPtr((this._val - ((off instanceof MockPtr) ? off._val : Number(off))) >>> 0); }
    toInt32() { return this._val | 0; }
    equals(other) { return (this._val >>> 0) === (((other instanceof MockPtr) ? other._val : Number(other)) >>> 0); }
    toString() { return "0x" + this._val.toString(16); }
    readU8() { return ensureBuf(this._val, 1).readUInt8(0); }
    writeU8(v) { ensureBuf(this._val, 1).writeUInt8(v & 0xFF, 0); return this; }
    readS8() { return ensureBuf(this._val, 1).readInt8(0); }
    writeS8(v) { ensureBuf(this._val, 1).writeInt8(v | 0, 0); return this; }
    readU16() { return ensureBuf(this._val, 2).readUInt16LE(0); }
    writeU16(v) { ensureBuf(this._val, 2).writeUInt16LE(v & 0xFFFF, 0); return this; }
    readS16() { return ensureBuf(this._val, 2).readInt16LE(0); }
    writeS16(v) { ensureBuf(this._val, 2).writeInt16LE(v | 0, 0); return this; }
    readU32() { return ensureBuf(this._val, 4).readUInt32LE(0); }
    writeU32(v) { ensureBuf(this._val, 4).writeUInt32LE(v >>> 0, 0); return this; }
    readS32() { return ensureBuf(this._val, 4).readInt32LE(0); }
    writeS32(v) { ensureBuf(this._val, 4).writeInt32LE(v | 0, 0); return this; }
    readFloat() { return ensureBuf(this._val, 4).readFloatLE(0); }
    writeFloat(v) { ensureBuf(this._val, 4).writeFloatLE(Number(v), 0); return this; }
    readPointer() { const b = memMap.get(this._val); return new MockPtr(b ? b.readUInt32LE(0) : 0); }
    writePointer(p) { ensureBuf(this._val, 8).writeUInt32LE(((p instanceof MockPtr) ? p._val : Number(p)) >>> 0, 0); return this; }
    readUtf16String() { return "Short Sword"; }
    readUtf8String() { return "Short Sword"; }
}

function allocMem(size) {
    const addr = nextPtrAddr;
    nextPtrAddr += Math.max(64, ((size + 63) & ~63));
    memMap.set(addr, Buffer.alloc(Math.max(256, size)));
    return new MockPtr(addr);
}

function bytesFromIl2CppArr(ilArrPtr) {
    const len = ilArrPtr.add(0x18).readS32();
    const arr = [];
    for (let i = 0; i < len; i++) arr.push(ilArrPtr.add(0x20 + i).readU8());
    return arr;
}

const baseAddrVal = 0x10000000;
const offMap = {};
for (const [k, v] of Object.entries(DEFAULT_OFFSETS)) {
    const num = (typeof v === "string") ? parseInt(v, 16) : Number(v);
    if (num > 0) offMap[(baseAddrVal + num) >>> 0] = k;
}

const exportFns = {
    LoadLibraryW: 0x01000900,
    il2cpp_thread_attach: 0x01001000,
    il2cpp_domain_get: 0x01001010,
    il2cpp_array_new: 0x01001030,
    il2cpp_gchandle_new: 0x01001050,
    il2cpp_gchandle_free: 0x01001060,
    il2cpp_get_corlib: 0x01001088,
    mono_domain_get_corlib: 0x01001090,
    il2cpp_class_from_name: 0x010010A0,
};

// Mock player, coord, inventory, itemsArr (239 slots including Personal Shop 204..235)
const gsPtr = allocMem(0x200);
const playerPtr = allocMem(0x600);
const coordKlass = allocMem(0x40);
const coordPtr = allocMem(0x40);
coordPtr.writePointer(coordKlass);
coordPtr.add(0x10).writeS32(22);
coordPtr.add(0x14).writeS32(225);
const invPtr = allocMem(0x100);
const itemsArr = allocMem(0x40 + 239 * 8);
itemsArr.add(0x18).writeS32(239);

playerPtr.add(parseInt(DEFAULT_OFFSETS.player_coord, 16)).writePointer(coordPtr);
playerPtr.add(parseInt(DEFAULT_OFFSETS.player_inventory, 16)).writePointer(invPtr);
invPtr.add(parseInt(DEFAULT_OFFSETS.inventory_items, 16)).writePointer(itemsArr);

function makeItem(itemIndex, level = 0, exc = 0) {
    const item = allocMem(0x100);
    const te = allocMem(0x100);
    te.add(0x10).writeS32(itemIndex);
    te.add(0x58).writeS32(Math.floor(itemIndex / 512));
    te.add(0x5C).writeS32(itemIndex % 512);
    item.add(0x10).writeS32(level);
    item.add(0x20).writeS32(exc);
    item.add(0x58).writePointer(te);
    item.add(0x60).writeS32(itemIndex);
    return item;
}

// Populate slots:
// Slot 12, 13, 14: junk Short Swords (index 1, +2)
// Slot 15: Excellent Sword (index 1, +0, exc=1) -> MUST BE PROTECTED
// Slot 205: Personal Shop item (index 1, +0) -> MUST NEVER BE TOUCHED (AnyInventoryEnd = 204)
itemsArr.add(0x20 + 12 * 8).writePointer(makeItem(1, 2, 0));
itemsArr.add(0x20 + 13 * 8).writePointer(makeItem(1, 1, 0));
itemsArr.add(0x20 + 14 * 8).writePointer(makeItem(1, 0, 0));
itemsArr.add(0x20 + 15 * 8).writePointer(makeItem(1, 0, 1));
itemsArr.add(0x20 + 205 * 8).writePointer(makeItem(1, 0, 0));

const hooks = {};
const nativeDropCalls = [];
const sentGSFrames = [];
let mockServerMode = "accept"; // "accept" | "reject"
let mockNowMs = 1700000000000;
let sleepCalls = 0;

function emitDropRecvReply(slot, resCode) {
    const hook = hooks[(baseAddrVal + parseInt(DEFAULT_OFFSETS.user_inv_drop_recv, 16)) >>> 0];
    if (!hook || !hook.onEnter) return;
    const pkt = allocMem(0x40);
    pkt.add(0x18).writeS32(5);
    pkt.add(0x23).writeU8(resCode);
    pkt.add(0x24).writeU8(slot);
    hook.onEnter([pkt]);
}

const gaModuleObj = {
    base: new MockPtr(baseAddrVal),
    name: "GameAssembly.dll",
    findExportByName: (name) => new MockPtr(exportFns[name] || 0),
    getExportByName: (name) => new MockPtr(exportFns[name] || 0),
};

const rpcObj = { exports: {} };
const sandbox = {
    ptr: (v) => new MockPtr(typeof v === "string" ? parseInt(v, 16) : v),
    uint64: (v) => new MockPtr(v),
    int64: (v) => new MockPtr(v),
    NULL: new MockPtr(0),
    NativePointer: MockPtr,
    console: { log: () => {}, warn: () => {}, error: () => {} },
    Date: { now: () => mockNowMs },
    Math: Math,
    JSON: JSON,
    Array: Array,
    Uint8Array: Uint8Array,
    Number: Number,
    String: String,
    Boolean: Boolean,
    parseInt: parseInt,
    parseFloat: parseFloat,
    isNaN: isNaN,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    setInterval: () => 1,
    clearInterval: () => {},
    Thread: { sleep: () => { sleepCalls++; } },
    send: () => {},
    rpc: rpcObj,
    Process: {
        getModuleByName: () => gaModuleObj,
        findModuleByName: () => gaModuleObj,
        getCurrentThreadId: () => 1,
    },
    Module: {
        findExportByName: (mod, name) => new MockPtr(exportFns[name] || 0),
        getExportByName: (mod, name) => new MockPtr(exportFns[name] || 0),
    },
    Memory: {
        alloc: (size) => allocMem(size),
        allocUtf16String: () => allocMem(64),
        allocUtf8String: () => allocMem(64),
    },
    Interceptor: {
        attach: (addr, cb) => {
            const k = (addr instanceof MockPtr) ? addr._val : Number(addr);
            hooks[k] = cb;
            return { detach: () => {} };
        },
        detachAll: () => {},
    },
    NativeFunction: function(addrPtr, retType) {
        const addrNum = (addrPtr instanceof MockPtr) ? addrPtr._val : Number(addrPtr);
        return function(...args) {
            if (addrNum === exportFns.LoadLibraryW) return new MockPtr(0x01500000);
            if (addrNum === exportFns.il2cpp_get_corlib) return new MockPtr(0x02000100);
            if (addrNum === exportFns.mono_domain_get_corlib) return new MockPtr(0); // prove il2cpp_get_corlib is used!
            if (addrNum === exportFns.il2cpp_class_from_name) return new MockPtr(0x02000200);
            if (addrNum === exportFns.il2cpp_domain_get) return new MockPtr(0x02000000);
            if (addrNum === exportFns.il2cpp_thread_attach) return new MockPtr(0x02000010);
            if (addrNum === exportFns.il2cpp_array_new) {
                const len = Number(args[1] || 0);
                const p = allocMem(0x30 + len);
                p.add(0x18).writeS32(len);
                return p;
            }
            const sym = offMap[addrNum];
            if (sym === "get_player") return playerPtr;
            if (sym === "get_gs_connection") return gsPtr;
            if (sym === "gs_send" || sym === "gs_send_alt") {
                sentGSFrames.push(bytesFromIl2CppArr(args[1]));
                return undefined;
            }
            if (sym === "user_inv_drop") {
                const slot = Number(args[0]);
                const cPtr = args[1];
                const tx = (cPtr && !cPtr.isNull()) ? cPtr.add(0x10).readS32() : -1;
                const ty = (cPtr && !cPtr.isNull()) ? cPtr.add(0x14).readS32() : -1;
                nativeDropCalls.push({ slot, tx, ty });
                if (mockServerMode === "accept") {
                    itemsArr.add(0x20 + slot * 8).writePointer(new MockPtr(0));
                    emitDropRecvReply(slot, 1);
                } else {
                    emitDropRecvReply(slot, 0);
                }
                return undefined;
            }
            return (retType === "pointer") ? new MockPtr(0) : 0;
        };
    }
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

// 1) Verify C3 framing for Drop (0x23) & Sell (0x32)
const dropFrame = sandbox.prepareC1FrameBytes([0xC3, 0x06, 0x23, 22, 225, 12], false);
assert(dropFrame[0] >= 0x30 && dropFrame[0] <= 0x3E, "C3 header must be 0x30..0x3E, got 0x" + dropFrame[0].toString(16));
assert.strictEqual(dropFrame[1], 0x06);
assert.strictEqual(dropFrame[2], 0x23 ^ 0xCB, "Drop opcode must be XORed with 0xCB (0xE8)");
assert.strictEqual(dropFrame[5], 12);

sentGSFrames.length = 0;
assert.strictEqual(sandbox.sendDropPacket(12, 23, 225), true);
assert.strictEqual(sentGSFrames.length, 1);
assert(sentGSFrames[0][0] >= 0x30 && sentGSFrames[0][0] <= 0x3E, "sendDropPacket MUST emit C3 (0x30..0x3E), not C1!");
assert.strictEqual(sentGSFrames[0][2], 0xE8);
assert.strictEqual(sentGSFrames[0][3], 23);
assert.strictEqual(sentGSFrames[0][4], 225);
assert.strictEqual(sentGSFrames[0][5], 12);

// Never drop equipped slots 0..11
assert.strictEqual(sandbox.sendDropPacket(5, 22, 225), false);
assert.strictEqual(sandbox.dropSlotNative(5, 22, 225), false);

// 2) Verify NON-BLOCKING MainThread state machine: startJunkDisposal + gameUpdateHook ticks + getJunkDisposalStatus
//    MUST call ZERO Thread.sleep() (prevents AppHangB1 deadlock!)
const gameUpdHook = hooks[(baseAddrVal + parseInt(DEFAULT_OFFSETS.game_update, 16)) >>> 0];
assert(gameUpdHook && typeof gameUpdHook.onEnter === "function", "game_update hook must be attached");

sleepCalls = 0;
const startOk = JSON.parse(rpcObj.exports.startJunkDisposal("drop", "[]", -1, 1, 6, 40, 0, 1));
assert.strictEqual(startOk.queued, true, "startJunkDisposal must queue immediately: " + JSON.stringify(startOk));
assert.strictEqual(startOk.total, 3);
assert.strictEqual(nativeDropCalls.length, 0, "startJunkDisposal RPC MUST NOT call nativeUserInvDrop on RPC thread!");
assert.strictEqual(sleepCalls, 0, "startJunkDisposal MUST NOT call Thread.sleep!");

let stOk = null;
for (let step = 0; step < 30; step++) {
    mockNowMs += 95;
    gameUpdHook.onEnter([]);
    stOk = JSON.parse(rpcObj.exports.getJunkDisposalStatus(startOk.jobId));
    if (stOk.done) break;
}
assert.strictEqual(sleepCalls, 0, "MainThread state machine MUST NEVER call Thread.sleep!");
assert(stOk && stOk.done && stOk.result, "Junk disposal job must complete cleanly on MainThread");
const resOk = stOk.result;
assert.strictEqual(resOk.dropped, 3, "Must drop 3 junk slots (12, 13, 14): " + JSON.stringify(resOk));
assert.strictEqual(resOk.serverAccepted, 3);
assert.strictEqual(resOk.serverRejected, 0);
assert.strictEqual(nativeDropCalls.length, 3);
// Check spiral spread (different tiles, not all identical!)
const uniqueTiles = new Set(nativeDropCalls.map(c => c.tx + "," + c.ty));
assert.strictEqual(uniqueTiles.size, 3, "Spiral drop must spread items across distinct nearby tiles");
assert(!itemsArr.add(0x20 + 15 * 8).readPointer().isNull(), "Excellent item in slot 15 MUST remain untouched");
assert(!itemsArr.add(0x20 + 205 * 8).readPointer().isNull(), "Personal Shop item in slot 205 MUST NEVER be touched");

// 3) Verify server rejection detection via C1:23 hook (result=0 -> drop_blocked without pointless Pass 2 spam, ZERO sleep!)
itemsArr.add(0x20 + 12 * 8).writePointer(makeItem(1, 0, 0));
itemsArr.add(0x20 + 13 * 8).writePointer(makeItem(1, 0, 0));
mockServerMode = "reject";
nativeDropCalls.length = 0;
sleepCalls = 0;
const startRej = JSON.parse(rpcObj.exports.startJunkDisposal("drop", "[]", -1, 1, 6, 40, 0, 1));
assert.strictEqual(startRej.queued, true);
let stRej = null;
for (let step = 0; step < 30; step++) {
    mockNowMs += 95;
    gameUpdHook.onEnter([]);
    stRej = JSON.parse(rpcObj.exports.getJunkDisposalStatus(startRej.jobId));
    if (stRej.done) break;
}
assert.strictEqual(sleepCalls, 0, "Rejection flow MUST NEVER call Thread.sleep!");
const resRej = stRej.result;
assert.strictEqual(resRej.dropped, 0);
assert.strictEqual(resRej.reason, "drop_blocked");
assert.strictEqual(resRej.serverRejected, 2, "Must report exact C1:23 server rejection count");
assert.strictEqual(nativeDropCalls.length, 2, "Should skip redundant Pass 2 when server explicitly rejected all slots");

// 4) Verify non-blocking single slot drop on MainThread (startDropSingleSlot -> getSingleDropStatus)
mockServerMode = "accept";
const sDropStart = JSON.parse(rpcObj.exports.startDropSingleSlot(12, 1, 0));
assert.strictEqual(sDropStart.queued, true);
let sDropSt = null;
for (let step = 0; step < 10; step++) {
    mockNowMs += 50;
    gameUpdHook.onEnter([]);
    sDropSt = JSON.parse(rpcObj.exports.getSingleDropStatus(sDropStart.jobId));
    if (sDropSt.done) break;
}
assert(sDropSt && sDropSt.done && sDropSt.result.verified === true, "Single slot drop must verify cleanly on MainThread");
assert.strictEqual(sleepCalls, 0, "Single slot drop MUST NEVER call Thread.sleep!");

console.log(JSON.stringify({ ok: true, dropped: resOk.dropped, rejected: resRej.serverRejected, sleepCalls }));
'''


class TestMossDropFix(unittest.TestCase):
    def test_offsets_sync_and_placeholders_resolved(self):
        expected_offsets = {
            "user_inv_drop": "0x14581E0",
            "user_inv_drop_recv": "0x1457C40",
            "user_inv_sell": "0x14521D0",
            "user_inv_sell_5": "0x14557E0",
            "ui_gremory_window": "0x170",
            "ui_inventory_window": "0x190",
            "ui_merchant_window": "0x1A0",
            "ui_moss_window": "0x1D0",
            "ui_warehouse_window": "0x290",
        }
        with open("megamu_offsets.json", "r", encoding="utf-8") as f:
            root_off = json.load(f)
        with open(os.path.join("config", "megamu_offsets.json"), "r", encoding="utf-8") as f:
            cfg_off = json.load(f)

        for k, v in expected_offsets.items():
            self.assertEqual(mde.DEFAULT_OFFSETS.get(k), v, f"DEFAULT_OFFSETS mismatch: {k}")
            self.assertEqual(root_off.get(k), v, f"megamu_offsets.json mismatch: {k}")
            self.assertEqual(cfg_off.get(k), v, f"config/megamu_offsets.json mismatch: {k}")

        eng = _make_dummy_engine()
        js = eng._generate_js()
        for ph in ("__USER_INV_DROP__", "__USER_INV_DROP_RECV__", "__USER_INV_SELL__", "__USER_INV_SELL_5__"):
            self.assertNotIn(ph, js, f"Unreplaced placeholder {ph}")
        self.assertNotIn("0x123ECB0", js.split("var nativeGetItemName")[1][:120], "Dead 0x123ECB0 must not be bound")

    def test_moss_drop_runtime_in_node_vm(self):
        eng = _make_dummy_engine()
        js = eng._generate_js()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen_path = os.path.join(tmpdir, "frida_gen.js")
            harness_path = os.path.join(tmpdir, "harness.js")
            with open(gen_path, "w", encoding="utf-8") as f:
                f.write(js)
            with open(harness_path, "w", encoding="utf-8") as f:
                f.write(NODE_MOSS_DROP_HARNESS)
            proc = subprocess.run(
                ["node", harness_path, gen_path, json.dumps(eng.offsets)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Node Moss Drop VM failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
            summary = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["dropped"], 3)
            self.assertEqual(summary["rejected"], 2)

    def test_gui_optimized_junk_dialog_handles_int_junk_count(self):
        with open("meg_gui_optimized.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('slots_list = res.get("slots")', src)
        self.assertNotIn('junk = res.get("junk", []) or res.get("junkSlots", [])', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
