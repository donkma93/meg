import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock

import meg_direct_engine as mde
import meg_gui


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


NODE_FRIDA_HARNESS = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const jsPath = process.argv[2];
const code = fs.readFileSync(jsPath, "utf8");

let mockNowMs = 1700000000000;
let mockTargetFps = 60;
let mockVSync = 1;
let mockSockConnected = 1;
let mockInDoubleGoer = 0;
let mockSendCount = 10;
let mockSendSerial = 42;
let mockTicketSlot = 24;
let mockRttDelayMs = 18;
let sentNativeGSFrames = [];
let sentDirectSockFrames = [];
let tcpNoDelayCalls = [];
let failNextDirectSockSend = false;
let mirrorEnterAltCalls = [];
let lugardTalkCalls = 0;
let closeTalkCalls = 0;
let emittedMessages = [];
let hooks = {};
let nextPtrAddr = 0x20000000;
const memMap = new Map();
const gcPinned = new Map();

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
    constructor(val) {
        this._val = Number(val) >>> 0;
    }
    isNull() { return this._val === 0; }
    add(off) {
        const d = (off instanceof MockPtr) ? off._val : Number(off);
        return new MockPtr((this._val + d) >>> 0);
    }
    sub(off) {
        const d = (off instanceof MockPtr) ? off._val : Number(off);
        return new MockPtr((this._val - d) >>> 0);
    }
    toInt32() { return this._val | 0; }
    equals(other) {
        const v = (other instanceof MockPtr) ? other._val : Number(other);
        return (this._val >>> 0) === (v >>> 0);
    }
    toString() { return "0x" + this._val.toString(16); }
    _readBuf(size) { return ensureBuf(this._val, size); }
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
    readU64() { return BigInt(this.readU32()); }
    writeU64(v) { this.writeU32(Number(v) >>> 0); return this; }
    readPointer() {
        const b = memMap.get(this._val);
        return new MockPtr(b ? b.readUInt32LE(0) : 0);
    }
    writePointer(p) {
        const b = ensureBuf(this._val, 8);
        const v = (p instanceof MockPtr) ? p._val : Number(p);
        b.writeUInt32LE(v >>> 0, 0);
        return this;
    }
    readByteArray(len) {
        const out = Buffer.alloc(len);
        for (let i = 0; i < len; i++) {
            out[i] = new MockPtr(this._val + i).readU8();
        }
        return out.buffer;
    }
    writeByteArray(arr) {
        const u8 = Array.isArray(arr) ? arr : Array.from(new Uint8Array(arr));
        for (let i = 0; i < u8.length; i++) {
            new MockPtr(this._val + i).writeU8(u8[i]);
        }
        return this;
    }
    readUtf16String() { return "TestItem"; }
    writeUtf16String(s) { return this; }
    readUtf8String() { return "TestStr"; }
}

function allocMem(size) {
    const addr = nextPtrAddr;
    nextPtrAddr += Math.max(64, ((size + 63) & ~63));
    memMap.set(addr, Buffer.alloc(Math.max(256, size)));
    return new MockPtr(addr);
}

// Allocate GSConnection + TcpClient + Socket object graph
const gsPtr = allocMem(0x200);
const tcpPtr = allocMem(0x100);
const sockPtr = allocMem(0x100);
gsPtr.add(0x90).writePointer(tcpPtr);
gsPtr.add(0xB8).writeS32(mockSendCount);
gsPtr.add(0xC0).writeU8(mockSendSerial);
tcpPtr.add(0x10).writePointer(sockPtr);
sockPtr.add(0x52).writeU8(mockSockConnected);

// Inventory mock for item slot check
const arrPtr = allocMem(0x100 + 200 * 8);
const itemObj = allocMem(0x80);
itemObj.add(0x10).writeU16(0x1C6F); // item_mirror_ticket = 7279
const invSlotPtr = arrPtr.add(0x20 + mockTicketSlot * 8);
invSlotPtr.writePointer(itemObj);

const baseAddrVal = 0x10000000;
const offMap = {};
const DEFAULT_OFFSETS = JSON.parse(process.argv[3]);
for (const [k, v] of Object.entries(DEFAULT_OFFSETS)) {
    const num = (typeof v === "string") ? parseInt(v, 16) : Number(v);
    offMap[(baseAddrVal + num) >>> 0] = k;
}

const exportFns = {
    LoadLibraryW: 0x01000900,
    il2cpp_thread_attach: 0x01001000,
    il2cpp_domain_get: 0x01001010,
    il2cpp_object_new: 0x01001020,
    il2cpp_array_new: 0x01001030,
    il2cpp_string_new: 0x01001040,
    il2cpp_gchandle_new: 0x01001050,
    il2cpp_gchandle_free: 0x01001060,
    il2cpp_class_from_type: 0x01001070,
    il2cpp_type_get_object: 0x01001080,
    il2cpp_get_corlib: 0x01001088,
    mono_domain_get_corlib: 0x01001090,
    il2cpp_class_from_name: 0x010010A0,
};

function bytesFromIl2CppArr(ilArrPtr) {
    const len = ilArrPtr.add(0x18).readS32();
    const arr = [];
    for (let i = 0; i < len; i++) {
        arr.push(ilArrPtr.add(0x20 + i).readU8());
    }
    return arr;
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
    Date: {
        now: () => mockNowMs
    },
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
    setInterval: () => 123,
    clearInterval: () => {},
    send: (msg) => { emittedMessages.push(msg); },
    rpc: rpcObj,
    Process: {
        getModuleByName: (name) => gaModuleObj,
        findModuleByName: (name) => gaModuleObj,
        getCurrentThreadId: () => 4242,
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
        attach: (addr, callbacks) => {
            const addrNum = (addr instanceof MockPtr) ? addr._val : Number(addr);
            const name = offMap[addrNum] || ("0x" + addrNum.toString(16));
            hooks[addrNum] = callbacks;
            if (!hooks._byOffset) hooks._byOffset = {};
            hooks._byOffset[addrNum] = callbacks;
            return { detach: () => {} };
        },
        detachAll: () => {}
    },
    NativeFunction: function(addrPtr, retType, argTypes) {
        const addrNum = (addrPtr instanceof MockPtr) ? addrPtr._val : Number(addrPtr);
        return function(...args) {
            if (addrNum === exportFns.LoadLibraryW) return new MockPtr(0x01500000);
            if (addrNum === exportFns.il2cpp_get_corlib) return new MockPtr(0x02000100);
            if (addrNum === exportFns.mono_domain_get_corlib) return new MockPtr(0x02000100);
            if (addrNum === exportFns.il2cpp_class_from_name) return new MockPtr(0x02000200);
            if (addrNum === exportFns.il2cpp_domain_get) return new MockPtr(0x02000000);
            if (addrNum === exportFns.il2cpp_thread_attach) return new MockPtr(0x02000010);
            if (addrNum === exportFns.il2cpp_object_new) return allocMem(0x80);
            if (addrNum === exportFns.il2cpp_string_new) return allocMem(0x40);
            if (addrNum === exportFns.il2cpp_array_new) {
                const len = Number(args[1] || 0);
                const p = allocMem(0x30 + len);
                p.add(0x18).writeS32(len);
                return p;
            }
            if (addrNum === exportFns.il2cpp_gchandle_new) {
                const h = gcPinned.size + 1;
                gcPinned.set(h, { obj: args[0], pinned: args[1] });
                return h;
            }
            if (addrNum === exportFns.il2cpp_gchandle_free) {
                gcPinned.delete(args[0]);
                return undefined;
            }
            const sym = offMap[addrNum];
            if (sym === "get_gs_connection" || sym === "gs_get_instance") return gsPtr;
            if (sym === "gs_send" || sym === "gs_send_alt") {
                const raw = bytesFromIl2CppArr(args[1]);
                sentNativeGSFrames.push(raw);
                return undefined;
            }
            if (sym === "set_target_framerate") { mockTargetFps = Number(args[0]); return undefined; }
            if (sym === "get_target_framerate") return mockTargetFps;
            if (sym === "set_vsync_count") { mockVSync = Number(args[0]); return undefined; }
            if (sym === "get_vsync_count") return mockVSync;
            if (sym === "unity_get_time") return mockNowMs / 1000.0;
            if (sym === "pkt_enc_nikini") {
                const srcArr = args[0];
                const raw = bytesFromIl2CppArr(srcArr);
                // Simulate real DCBFPGDDCMG in-place mutation of srcArr[0] & srcArr[2]
                srcArr.add(0x20).writeU8(0x01);
                srcArr.add(0x22).writeU8((raw[2] ^ 0xCB) & 0xFF);
                const enc = allocMem(0x40 + raw.length);
                enc.add(0x18).writeS32(raw.length);
                for (let i = 0; i < raw.length; i++) enc.add(0x20 + i).writeU8(raw[i] ^ 0x55);
                // Increment SendSerial at args[1]
                const serPtr = args[1];
                serPtr.writeU8((serPtr.readU8() + 1) & 0xFF);
                return enc;
            }
            if (sym === "pkt_enc_ngjg") return undefined;
            if (sym === "socket_send_err") {
                if (failNextDirectSockSend) {
                    failNextDirectSockSend = false;
                    throw new Error("Simulated transient Socket.Send error");
                }
                const encArr = args[1];
                const encLen = Number(args[3]);
                const errOut = args[5];
                errOut.writeS32(0);
                const frame = bytesFromIl2CppArr(encArr).map(b => b ^ 0x55);
                sentDirectSockFrames.push(frame);
                return encLen;
            }
            if (sym === "tcp_set_nodelay") {
                tcpNoDelayCalls.push({ tcp: args[0].toString(), val: Number(args[1]) });
                return undefined;
            }
            if (sym === "mirror_is_event_map" || sym === "mirror_is_event_map_alt") return mockInDoubleGoer;
            if (sym === "mirror_enter" || sym === "mirror_enter_alt") { mirrorEnterAltCalls.push(Number(args[0])); return undefined; }
            if (sym === "npc_close_talk" || sym === "close_talk") { closeTalkCalls++; return undefined; }
            if (sym === "get_inventory_items") return arrPtr;
            if (sym === "get_item_id") return 0x1C6F;
            if (sym === "inventory_get_slot") return invSlotPtr;
            if (sym === "socket_connected" || sym === "get_game_state") return 5;
            if (sym === "get_map_id") return 51;
            return (retType === "pointer") ? new MockPtr(0) : 0;
        };
    }
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

// Helper to resolve hook address
function getHook(key) {
    const offVal = parseInt(DEFAULT_OFFSETS[key], 16);
    return hooks[(baseAddrVal + offVal) >>> 0];
}

// 1) Method 2: Verify prepareC1FrameBytes & sendGSPacket XOR / header encoding (0x10..0x1E strictly)
for (let k = 0; k < 20; k++) {
    const fk = sandbox.prepareC1FrameBytes([0xC1, 0x05, 0xBF, 0x0E, 0x0C], false);
    assert(fk[0] >= 0x10 && fk[0] <= 0x1E, "C1 header must stay in 0x10..0x1E (got 0x" + fk[0].toString(16) + ")");
}
const f1 = sandbox.prepareC1FrameBytes([0xC1, 0x05, 0xBF, 0x0E, 0x0C], false);
assert(f1[0] >= 0x10 && f1[0] <= 0x1E, "C1 header must become 0x10..0x1E");
assert.strictEqual(f1[1], 0x05);
assert.strictEqual(f1[2], 0xBF ^ 0xCB, "byte[2] must be XORed with 0xCB");
assert.strictEqual(f1[3], 0x0E);
assert.strictEqual(f1[4], 0x0C);

const f2 = sandbox.prepareC1FrameBytes([0xC1, 0x06, 0xE8, 10, 20, 15], true);
assert(f2[0] >= 0x10 && f2[0] <= 0x1F);
assert.strictEqual(f2[2], 0xE8, "alreadyXored=true must preserve pre-XORed opcode");

sentNativeGSFrames.length = 0;
const okClose = sandbox.sendGSPacket([0xC1, 0x04, 0x31, 0x00]);
assert.strictEqual(okClose, true, "sendGSPacket failed: " + sandbox.lastSendError);
assert.strictEqual(sentNativeGSFrames.length, 1);
assert.strictEqual(sentNativeGSFrames[0][2], 0x31 ^ 0xCB, "sendGSPacket must encode 0x31 -> 0xFA");

// 2) Method 1 + 4 + 5: preStageMirrorTurbo + MainThread tick + Direct Socket.Send + GC pin
const preRes = JSON.parse(rpcObj.exports.preStageMirrorTurbo(24, true));
assert.strictEqual(preRes.success, true);
assert.strictEqual(preRes.relSlot, 12);

// Tick Mega.Game$$Update once on MainThread to execute pre-stage (GC pin on MainThread) + probe
const gameUpdHook = getHook("game_update");
const dgerHook = getHook("mirror_enter_recv");
assert(gameUpdHook && typeof gameUpdHook.onEnter === "function", "game_update hook attached");
assert(dgerHook && typeof dgerHook.onEnter === "function", "mirror_enter_recv hook attached");

gameUpdHook.onEnter([]);
assert(gcPinned.size >= 1, "Pinned byte[5] buffer must hold a pinned GCHandle after MainThread tick");
assert(tcpNoDelayCalls.length >= 1 && tcpNoDelayCalls[0].val === 1, "TCP_NODELAY must be enabled on TcpClient during pre-stage");
assert.strictEqual(sentDirectSockFrames.length, 1, "Probe must go via Direct Socket.Send");
assert(sentDirectSockFrames[0][0] >= 0x10 && sentDirectSockFrames[0][0] <= 0x1E);
assert.strictEqual(sentDirectSockFrames[0][2], 0xBF ^ 0xCB);
assert.strictEqual(sentDirectSockFrames[0][3], 0x0E);
assert.strictEqual(sentDirectSockFrames[0][4], 12);

// Trigger DoubleGoer$$PMADOEGMPPK (R=6) after 18ms
mockNowMs += 18;
const r6Buf = allocMem(0x40);
r6Buf.add(0x18).writeS32(5);
r6Buf.add(0x24).writeU8(6);
dgerHook.onEnter([r6Buf]);

let tStats = JSON.parse(rpcObj.exports.getMirrorTimingStats());
assert.strictEqual(tStats.lastRecvCode, 6);
assert.strictEqual(tStats.rttMs, 18, "Measured RTT from probe must equal 18ms");

// 3) Method 1 + 4: armNativeMirrorTurbo with future epoch + 5ms interval (<20ms old floor)
const openEpoch = mockNowMs + 200;
const armRes = JSON.parse(rpcObj.exports.armNativeMirrorTurbo(24, 5, 15000, openEpoch, JSON.stringify({
    preStaged: true,
    directSocket: true,
    ackPaced: true,
    staggerMs: 0
})));
assert.strictEqual(armRes.success, true);
assert.strictEqual(armRes.armed, true);
assert.strictEqual(armRes.intervalMs, 5, "Interval below old 20ms floor must be preserved");

// Before openEpoch, MainThread ticks MUST NOT spam, while FPS boost applies safely on MainThread
sentDirectSockFrames.length = 0;
mockNowMs += 50;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 0, "Must hold gate cleanly until openEpoch");
assert.strictEqual(mockTargetFps, 240, "FPS boosted to 240 on MainThread");
assert.strictEqual(mockVSync, 0, "vSyncCount set to 0 on MainThread");

// Advance to openEpoch -> fires immediately on MainThread
mockNowMs = openEpoch;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 1, "Must fire immediately on MainThread at openEpoch");

// Advance 5ms -> fires second packet (proves 5ms burst works, not clamped to 20ms)
mockNowMs += 5;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 2, "Must dispatch at 5ms interval (< 20ms)");

// Trigger R=0 from server -> pauses burst immediately and records serverOpenEpochMs
mockNowMs += 14;
const r0Buf = allocMem(0x40);
r0Buf.add(0x18).writeS32(5);
r0Buf.add(0x24).writeU8(0);
dgerHook.onEnter([r0Buf]);
mockNowMs += 20;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 2, "R=0 accept must pause further spam");

// Verify stopNativeMirrorTurbo schedules FPS & VSync restore on next MainThread frame
const stopRes = JSON.parse(rpcObj.exports.stopNativeMirrorTurbo());
assert.strictEqual(stopRes.stopped, true);
gameUpdHook.onEnter([]);
assert.strictEqual(mockTargetFps, 60, "targetFrameRate restored to 60 on MainThread");
assert.strictEqual(mockVSync, 1, "vSyncCount restored to 1 on MainThread");

// 4) Verify SendSerial rollback when Socket.Send throws transiently (ZERO SendSerial desync!)
const serialBeforeErr = gsPtr.add(0xC0).readU8();
failNextDirectSockSend = true;
sentNativeGSFrames.length = 0;
const okAfterRollback = sandbox.dispatchMirrorEnterPacketFast(12);
assert.strictEqual(okAfterRollback, true, "Fallback must still send after DirectSocket error");
assert.strictEqual(sentNativeGSFrames.length, 1, "Fallback sendGSPacketDirect must fire once");
assert(sentNativeGSFrames[0][0] >= 0x10 && sentNativeGSFrames[0][0] <= 0x1E, "Fallback frame byte[0] must be rewritten after in-place DCBFPGDDCMG mutation!");
assert.strictEqual(sentNativeGSFrames[0][2], 0xBF ^ 0xCB, "Fallback frame byte[2] must still be 0xBF^0xCB (not double-XORed)!");
assert.strictEqual(gsPtr.add(0xC0).readU8(), serialBeforeErr, "SendSerial MUST be rolled back cleanly before fallback!");

// 5) Verify 3-Phase Adaptive Pacing (Approach >= 50ms -> Critical Window full-speed 5ms)
sentDirectSockFrames.length = 0;
const gateOpenTarget = mockNowMs + 2000;
const armAdaptive = JSON.parse(rpcObj.exports.armNativeMirrorTurbo(24, 5, 15000, mockNowMs, JSON.stringify({
    preStaged: true,
    directSocket: true,
    ackPaced: true,
    targetOpenEpochMs: gateOpenTarget,
    oneWayLatencyMs: 140
})));
assert.strictEqual(armAdaptive.success, true);
// Approach phase (2000ms before gate): fires 1st packet, then skips at +10ms, fires again at +50ms
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 1, "Approach fires first packet");
mockNowMs += 10;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 1, "Approach must throttle to >=50ms before critical window");
mockNowMs += 45;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 2, "Approach fires at >=50ms");
// Jump into Critical Window (gateOpenTarget - 140ms - 200ms): fires full speed at 5ms!
mockNowMs = gateOpenTarget - 340;
gameUpdHook.onEnter([]);
const countAtCritStart = sentDirectSockFrames.length;
mockNowMs += 5;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, countAtCritStart + 1, "Critical window must fire at full 5ms cadence");
rpcObj.exports.stopNativeMirrorTurbo();

// 6) Verify DirectSocket fallback when sock+0x52 == 0 (disconnected) -> falls back to nativeGSSend
sockPtr.add(0x52).writeU8(0);
sentNativeGSFrames.length = 0;
const startRes = JSON.parse(rpcObj.exports.startNativeMirrorTurbo(24, 5, 15000, JSON.stringify({ directSocket: true })));
assert.strictEqual(startRes.success, true);
mockNowMs += 10;
gameUpdHook.onEnter([]);
assert(sentNativeGSFrames.length >= 1, "Must fall back to pinned nativeGSSend if Socket.Connected != 1");
rpcObj.exports.stopNativeMirrorTurbo();

// 7) Verify R=6 -> R=2 transition learns serverOpenEpochMs with 1-way RTT subtracted + adaptive targetFps + uncalibrated wider critical lead
sockPtr.add(0x52).writeU8(1);
emittedMessages.length = 0;
sentDirectSockFrames.length = 0;
const gateOpenUncalib = mockNowMs + 2000;
const armUncalib = JSON.parse(rpcObj.exports.armNativeMirrorTurbo(24, 8, 15000, mockNowMs, JSON.stringify({
    preStaged: true,
    directSocket: true,
    ackPaced: true,
    targetOpenEpochMs: gateOpenUncalib,
    oneWayLatencyMs: 140,
    clockCalibrated: false,
    targetFps: 90
})));
assert.strictEqual(armUncalib.success, true);
// Jump to gateOpenUncalib - 140 - 900 (inside widened 1200ms uncalibrated critical window, outside old 450ms window)
mockNowMs = gateOpenUncalib - 1040;
gameUpdHook.onEnter([]);
assert.strictEqual(mockTargetFps, 90, "Adaptive targetFps=90 must be applied for multi-acc");
const cntBefore8 = sentDirectSockFrames.length;
mockNowMs += 8;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, cntBefore8 + 1, "Uncalibrated mode must already be in critical 8ms cadence at -900ms");

// Simulate R=6 followed by R=2 (lost race, gate just opened) -> must emit serverOpenEpochMs = recvAtMs - 140
const r6b = allocMem(0x40); r6b.add(0x18).writeS32(5); r6b.add(0x24).writeU8(6);
dgerHook.onEnter([r6b]);
mockNowMs += 20;
const r2RecvAt = mockNowMs;
const r2b = allocMem(0x40); r2b.add(0x18).writeS32(5); r2b.add(0x24).writeU8(2);
dgerHook.onEnter([r2b]);
const r2LearnedMsg = emittedMessages.find(m => m && m.type === "mirror_enter_recv" && m.rCode === 2 && m.transition === "R6->R2");
assert(r2LearnedMsg, "R6->R2 transition must emit calibration telemetry");
assert.strictEqual(r2LearnedMsg.serverOpenEpochMs, r2RecvAt - 140, "serverOpenEpochMs must subtract 1-way latency");
rpcObj.exports.stopNativeMirrorTurbo();
gameUpdHook.onEnter([]);

// 8) Verify multi-probe burst in preStageMirrorTurbo (probeCount = 3)
sentDirectSockFrames.length = 0;
const mpRes = JSON.parse(rpcObj.exports.preStageMirrorTurbo(24, 3));
assert.strictEqual(mpRes.success, true);
assert.strictEqual(mpRes.probeCount, 3);
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 1, "Multi-probe fires probe 1 immediately");
mockNowMs += 20;
dgerHook.onEnter([r6b]); // reply 1 -> schedules next probe after 45ms cooldown
mockNowMs += 50;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 2, "Multi-probe fires probe 2 after reply+cooldown");
mockNowMs += 16;
dgerHook.onEnter([r6b]); // reply 2
mockNowMs += 50;
gameUpdHook.onEnter([]);
assert.strictEqual(sentDirectSockFrames.length, 3, "Multi-probe fires probe 3");

console.log(JSON.stringify({
    ok: true,
    rttMs: tStats.rttMs,
    minRttMs: tStats.minRttMs,
    directFramesAfterR0: sentDirectSockFrames.length,
    fallbackGSFrames: sentNativeGSFrames.length,
    messagesCount: emittedMessages.length
}));
'''


class TestMirrorUltraOptimization(unittest.TestCase):
    def setUp(self):
        self._mirror_cfg_path = str(meg_gui.MIRROR_CONFIG_FILE)
        self._mirror_cfg_backup = None
        if os.path.exists(self._mirror_cfg_path):
            with open(self._mirror_cfg_path, "r", encoding="utf-8") as f:
                self._mirror_cfg_backup = f.read()

    def tearDown(self):
        if self._mirror_cfg_backup is not None:
            with open(self._mirror_cfg_path, "w", encoding="utf-8") as f:
                f.write(self._mirror_cfg_backup)
        elif os.path.exists(self._mirror_cfg_path):
            try:
                os.remove(self._mirror_cfg_path)
            except OSError:
                pass

    def test_offsets_sync_and_placeholders_resolved(self):
        required_offsets = {
            "mirror_enter": "0x10308A0",
            "mirror_enter_alt": "0x10308A0",
            "mirror_npc_click": "0x10341D0",
            "mirror_enter_recv": "0x10328D0",
            "mirror_teleport_event": "0x10359F0",
            "doublegoer_type_info": "0x551D980",
            "set_target_framerate": "0x453E950",
            "get_target_framerate": "0x453E900",
            "set_vsync_count": "0x4553280",
            "get_vsync_count": "0x4553230",
            "pkt_enc_nikini": "0x1293ED0",
            "pkt_enc_ngjg": "0x1291900",
            "socket_send_err": "0x42392F0",
            "tcp_set_nodelay": "0x4245170",
            "unity_get_time": "0x45896F0",
            "helper_ui_show_dialog": "0x1C37CC0",
        }
        with open("megamu_offsets.json", "r", encoding="utf-8") as f:
            root_off = json.load(f)
        with open(os.path.join("config", "megamu_offsets.json"), "r", encoding="utf-8") as f:
            cfg_off = json.load(f)
        with open(os.path.join("license-server", "storage", "app", "private", "game_offsets.json"), "r", encoding="utf-8") as f:
            srv_off = json.load(f)

        for key, expected in required_offsets.items():
            # Zero-Offset-On-Disk: DEFAULT_OFFSETS must NOT hardcode any RVA hex literals!
            self.assertIsNone(mde.DEFAULT_OFFSETS.get(key), f"DEFAULT_OFFSETS leaked RVA: {key}")
            self.assertEqual(srv_off.get(key), expected, f"server game_offsets.json mismatch: {key}")
            self.assertEqual(root_off.get(key), expected, f"megamu_offsets.json mismatch: {key}")
            self.assertEqual(cfg_off.get(key), expected, f"config/megamu_offsets.json mismatch: {key}")

        eng = _make_dummy_engine()
        js = eng._generate_js()
        for ph in (
            "__DOUBLEGOER_ENTER_RECV__",
            "__DOUBLEGOER_TYPE_INFO__",
            "__SET_VSYNC_COUNT__",
            "__GET_VSYNC_COUNT__",
            "__UNITY_GET_TIME__",
            "__PKT_ENC_NIKINI__",
            "__PKT_ENC_NGJG__",
            "__SOCKET_SEND_ERR__",
            "__TCP_SET_NODELAY__",
        ):
            self.assertNotIn(ph, js, f"Unreplaced placeholder {ph} in generated JS")

    def test_js_frida_runtime_behavior_in_node_vm(self):
        eng = _make_dummy_engine()
        js = eng._generate_js()
        with tempfile.TemporaryDirectory() as tmpdir:
            gen_path = os.path.join(tmpdir, "frida_gen.js")
            harness_path = os.path.join(tmpdir, "harness.js")
            with open(gen_path, "w", encoding="utf-8") as f:
                f.write(js)
            with open(harness_path, "w", encoding="utf-8") as f:
                f.write(NODE_FRIDA_HARNESS)

            proc = subprocess.run(
                ["node", harness_path, gen_path, json.dumps(eng.offsets)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Node Frida VM harness failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
            summary = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["rttMs"], 18)
            self.assertGreaterEqual(summary["fallbackGSFrames"], 1)

    def test_python_engine_wrappers_and_message_dispatch(self):
        eng = _make_dummy_engine()
        calls = []

        def fake_call(method, *args):
            calls.append((method, args))
            return json.dumps({"success": True, "method": method, "rttMs": 22})

        eng._call = fake_call
        res_pre = eng.pre_stage_mirror_turbo(slot=24, measure_probe=True)
        self.assertTrue(res_pre["success"])
        self.assertEqual(calls[-1][0], "preStageMirrorTurbo")
        self.assertEqual(calls[-1][1], (24, True))

        res_arm = eng.arm_native_mirror_turbo(
            slot=24,
            interval_ms=6,
            max_duration_ms=15000,
            start_at_epoch_ms=1700000005000,
            options={"staggerMs": 4, "directSocket": True, "ackPaced": True},
        )
        self.assertTrue(res_arm["success"])
        self.assertEqual(calls[-1][0], "armNativeMirrorTurbo")
        self.assertEqual(calls[-1][1][0:4], (24, 6, 15000, 1700000005000))
        self.assertEqual(json.loads(calls[-1][1][4])["staggerMs"], 4)

        events = []
        eng.on_mirror_turbo_event = lambda p: events.append(p)
        eng.last_mirror_turbo_result = {"type": "mirror_turbo_timeout"}
        eng._on_message(
            {"type": "send", "payload": {"type": "mirror_enter_recv", "rCode": 6, "rttMs": 19}},
            None,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(eng.last_mirror_enter_recv["rCode"], 6)
        self.assertEqual(eng.last_mirror_turbo_result["type"], "mirror_turbo_timeout")

    def test_gui_config_telemetry_and_controller_arming(self):
        meg_gui.ConfigPersistenceManager.save_mirror_schedule_config(
            {
                "auto_schedule": True,
                "auto_prep_before": True,
                "auto_lifecycle": True,
                "auto_gremory": False,
                "prefire_sec": 4.5,
                "snipe_interval_ms": 5,
                "stagger_ms": 3,
                "clock_offset_ms": -42.5,
                "selected_slots": [1, 2, 3],
            }
        )
        loaded = meg_gui.ConfigPersistenceManager.load_mirror_schedule_config()
        self.assertEqual(loaded["snipe_interval_ms"], 5)
        self.assertEqual(loaded["stagger_ms"], 3)
        self.assertAlmostEqual(loaded["clock_offset_ms"], -42.5, places=1)

        # Telemetry EWMA + clock offset learning guard (+-8000ms)
        app = meg_gui.DashboardApp.__new__(meg_gui.DashboardApp)
        app._mirror_last_rtt_ms = -1.0
        app._mirror_clock_offset_ms = 0.0
        app._last_scheduled_gate_open_epoch_ms = 1700000000000.0
        app.mirror_schedule_var = MagicMock(get=lambda: True)
        app.mirror_auto_prep_var = MagicMock(get=lambda: True)
        app.mirror_auto_lifecycle_var = MagicMock(get=lambda: True)
        app.mirror_auto_gremory_var = MagicMock(get=lambda: True)
        app.mirror_prefire_sec_entry = MagicMock(get=lambda: "5.0")
        app.mirror_snipe_delay_entry = MagicMock(get=lambda: "0")
        app.mirror_snipe_dur_entry = MagicMock(get=lambda: "15.0")
        app.mirror_stagger_ms_entry = MagicMock(get=lambda: "4")
        app.controllers = []
        app.lbl_mirror_net_calib = MagicMock()

        self.assertEqual(app.get_mirror_snipe_delay(), 0)
        self.assertEqual(app.get_mirror_stagger_ms(), 4)

        app.record_mirror_net_telemetry(r_code=6, rtt_ms=20.0)
        self.assertAlmostEqual(app._mirror_last_rtt_ms, 20.0, places=2)
        app.record_mirror_net_telemetry(r_code=0, rtt_ms=30.0, server_open_epoch_ms=1700000000040.0)
        # EWMA RTT: 20*0.6 + 30*0.4 = 24.0; delta = -40ms
        self.assertAlmostEqual(app._mirror_last_rtt_ms, 24.0, places=2)
        self.assertAlmostEqual(app._mirror_clock_offset_ms, -40.0, places=2)

        # Outlier (> 8000ms) must be ignored
        app.record_mirror_net_telemetry(r_code=0, rtt_ms=25.0, server_open_epoch_ms=1700000025000.0)
        self.assertAlmostEqual(app._mirror_clock_offset_ms, -40.0, places=2)

        # Controller arming + stagger offset forwarding
        ctrl = meg_gui.SlotController.__new__(meg_gui.SlotController)
        ctrl.slot_idx = 2
        ctrl.assigned_pid = os.getpid()
        ctrl.char_name = "TestChar"
        ctrl.mirror_status = "IDLE"
        ctrl.mirror_running = False
        ctrl.mirror_sniping = False
        ctrl.mirror_turbo_active = False
        ctrl._mirror_pre_staged_ts = 0.0
        ctrl._mirror_last_r6_log_ts = 0.0
        ctrl.app = MagicMock()
        ctrl.engine = MagicMock()
        ctrl.engine.is_ready = True
        ctrl.engine.last_fast_state = {"mapId": 51}
        ctrl.engine.get_map_id.return_value = 51
        ctrl.engine.get_mirror_ticket_info.return_value = {"hasTicket": True, "slots": [24], "count": 1}
        ctrl.engine.pre_stage_mirror_turbo.return_value = {"success": True}
        armed_ev = threading.Event()

        def _fake_arm(**kw):
            armed_ev.set()
            ctrl.mirror_sniping = False
            return {"success": True, "armed": True}

        ctrl.engine.arm_native_mirror_turbo.side_effect = _fake_arm
        ctrl.worker = MagicMock(attached=True, direct_engine=ctrl.engine)

        future_epoch_ms = int(time.time() * 1000) + 5000
        ok = ctrl.start_mirror_turbo_sniping(
            interval_ms=5,
            max_duration_s=15.0,
            start_at_epoch_ms=future_epoch_ms,
            stagger_ms=6,
        )
        self.assertTrue(ok)
        self.assertTrue(armed_ev.wait(timeout=2.0), "arm_native_mirror_turbo was not invoked")
        if getattr(ctrl, "mirror_snipe_thread", None):
            ctrl.mirror_snipe_thread.join(timeout=1.5)
        kwargs = ctrl.engine.arm_native_mirror_turbo.call_args.kwargs
        self.assertEqual(kwargs["slot"], 24)
        self.assertEqual(kwargs["interval_ms"], 5)
        self.assertEqual(kwargs["start_at_epoch_ms"], future_epoch_ms)
        self.assertEqual(kwargs["options"]["staggerMs"], 6)

        # Multi-account synchronized stagger distribution via start_all_mirror_turbo_sniping
        c1 = MagicMock(slot_idx=1, mirror_enabled=True, assigned_pid=os.getpid())
        c2 = MagicMock(slot_idx=2, mirror_enabled=True, assigned_pid=os.getpid())
        all_done = threading.Event()
        stagger_calls = []

        def _rec_call(idx):
            def _fn(**kw):
                stagger_calls.append((idx, kw["start_at_epoch_ms"], kw["stagger_ms"]))
                if len(stagger_calls) >= 2:
                    all_done.set()
                return True
            return _fn

        c1.start_mirror_turbo_sniping.side_effect = _rec_call(1)
        c2.start_mirror_turbo_sniping.side_effect = _rec_call(2)
        app.controllers = [c1, c2]
        app.mirror_snipe_delay_entry = MagicMock(get=lambda: "4")
        app.mirror_snipe_dur_entry = MagicMock(get=lambda: "15.0")
        app.mirror_stagger_ms_entry = MagicMock(get=lambda: "5")
        app.after = MagicMock()
        app.append_mirror_log = MagicMock()
        target_ms = int(time.time() * 1000) + 4000
        app.start_all_mirror_turbo_sniping(from_scheduler=True, target_open_epoch_ms=target_ms)
        self.assertTrue(all_done.wait(timeout=2.0), "start_all_mirror_turbo_sniping did not trigger both slots")
        stagger_calls.sort(key=lambda x: x[0])
        self.assertEqual(stagger_calls[0], (1, target_ms, 0))
        self.assertEqual(stagger_calls[1], (2, target_ms + 5, 5))

    def test_no_false_entered_notification_and_strict_map_range(self):
        # 1) is_mirror_event_map() must follow DoubleGoer.PAGCDNAAHMO (82..90 ONLY, never 65..68 or 51)
        eng = _make_dummy_engine()
        eng.is_ready = True
        eng.last_fast_state_time = time.time()
        for mid, expected in [(51, False), (53, False), (65, False), (68, False), (81, False), (82, True), (90, True), (91, False)]:
            eng.last_fast_state = {"mapId": mid}
            self.assertEqual(eng.is_mirror_event_map(), expected, f"mapId={mid} expected {expected}")

        # 2) start_all_mirror_turbo_sniping must NEVER falsely say "đã vào trong map Double Goer" when 0 accounts entered
        app = meg_gui.DashboardApp.__new__(meg_gui.DashboardApp)
        app.controllers = []
        app.mirror_snipe_delay_entry = MagicMock(get=lambda: "10")
        app.mirror_snipe_dur_entry = MagicMock(get=lambda: "15.0")
        app.mirror_stagger_ms_entry = MagicMock(get=lambda: "0")
        app._ensure_mirror_auto_schedule_enabled_from_manual = MagicMock()
        logs = []
        done_ev = threading.Event()
        def _after_cb(_ms, fn):
            fn()
            done_ev.set()
        app.after = _after_cb
        app.append_mirror_log = lambda msg: logs.append(msg)

        app.start_all_mirror_turbo_sniping(from_scheduler=False)
        self.assertTrue(done_ev.wait(timeout=2.0))
        self.assertTrue(logs, "Expected a warning log when 0 connected accounts")
        self.assertNotIn("đã vào trong map Double Goer", logs[-1])
        self.assertIn("Chưa có tài khoản", logs[-1])

        # 3) If an account is sniping (not in map), must say "Đang chạy Turbo Sniping", NOT "đã vào map"
        logs.clear()
        done_ev.clear()
        c_snipe = MagicMock(
            slot_idx=1,
            mirror_enabled=True,
            assigned_pid=os.getpid(),
            mirror_sniping=True,
            _mirror_dungeon_running=False,
        )
        c_snipe.engine = eng
        eng.last_fast_state = {"mapId": 51, "inDoubleGoer": False}
        app.controllers = [c_snipe]
        app.start_all_mirror_turbo_sniping(from_scheduler=False)
        self.assertTrue(done_ev.wait(timeout=2.0))
        self.assertIn("Đang chạy Turbo Sniping", logs[-1])
        self.assertNotIn("Tất cả", logs[-1])

    def test_call_converts_camelcase_to_snake_case_first(self):
        # Verify Frida ScriptExportsSync proxy behavior: __getattr__ ALWAYS returns a callable,
        # and only snake_case maps to camelCase JS rpc.exports (raw camelCase gets lowercased and throws).
        eng = _make_dummy_engine()
        invoked = []

        class FakeFridaExportsSync:
            def __getattr__(self, name):
                def _proxy(*args):
                    invoked.append((name, args))
                    if name == "start_native_mirror_turbo":
                        return json.dumps({"success": True, "via": "snake_case"})
                    if name == "raw_only_method":
                        return "ok-raw"
                    raise RuntimeError(f"unable to find method '{name.lower()}'")
                return _proxy

        eng.script = MagicMock(exports_sync=FakeFridaExportsSync())
        res = eng._call("startNativeMirrorTurbo", 24, 5, 15000, "{}")
        self.assertEqual(json.loads(res)["via"], "snake_case")
        self.assertEqual(invoked[0][0], "start_native_mirror_turbo")
        self.assertEqual(len(invoked), 1, "Should succeed on snake_case first without throwing on camelCase")

    def test_clock_offset_cumulative_no_oscillation_r2_learn_and_auto_stagger(self):
        # 1) Cumulative clock offset learning: Round 1 (base=0 -> -200ms) -> Round 2 (exact hit, residual=0 -> MUST STAY -200ms, NOT reset to 0!)
        app = meg_gui.DashboardApp.__new__(meg_gui.DashboardApp)
        app._mirror_last_rtt_ms = -1.0
        app._mirror_clock_offset_ms = 0.0
        app._mirror_clock_calibrated = False
        app._last_scheduled_offset_base_ms = 0.0
        app._last_scheduled_event_key = "20261123_2210_event"
        app._last_learned_event_key = None
        app._last_scheduled_gate_open_epoch_ms = 1700000000000.0
        app.lbl_mirror_net_calib = MagicMock()
        app.mirror_view = MagicMock()

        # Round 1: R6->R2 lost race still calibrates clock! Server opened 200ms late
        app.record_mirror_net_telemetry(
            r_code=2,
            rtt_ms=280.0,
            server_open_epoch_ms=1700000000200.0,
            transition="R6->R2",
        )
        self.assertAlmostEqual(app._mirror_clock_offset_ms, -200.0, places=1)
        self.assertTrue(app._mirror_clock_calibrated)
        # Verify auto-persisted to config JSON
        loaded_after_r1 = meg_gui.ConfigPersistenceManager.load_mirror_schedule_config()
        self.assertAlmostEqual(loaded_after_r1["clock_offset_ms"], -200.0, places=1)

        # Second slot in SAME event must NOT overwrite learned offset
        app.record_mirror_net_telemetry(
            r_code=0,
            rtt_ms=290.0,
            server_open_epoch_ms=1700000000900.0,
            transition="R6->R0",
        )
        self.assertAlmostEqual(app._mirror_clock_offset_ms, -200.0, places=1)

        # Round 2 (next event): scheduled with learned base=-200 -> last_sched = base + 200; server opens exactly on schedule (residual=0)
        app._last_scheduled_event_key = "20261124_0010_event"
        app._last_learned_event_key = None
        app._last_scheduled_offset_base_ms = app._mirror_clock_offset_ms
        app._last_scheduled_gate_open_epoch_ms = 1700007200200.0
        app.record_mirror_net_telemetry(
            r_code=0,
            rtt_ms=285.0,
            server_open_epoch_ms=1700007200200.0,
            transition="R6->R0",
        )
        self.assertAlmostEqual(app._mirror_clock_offset_ms, -200.0, places=1, msg="Offset must NOT oscillate back to 0!")

        # 2) Fresh min-biased RTT estimator & reset in GameTimeSyncService
        from services.time_sync_service import GameTimeSyncService
        ts = GameTimeSyncService.__new__(GameTimeSyncService)
        ts._lock = threading.Lock()
        ts._game_rtt_ms = 280.0
        ts._game_rtt_samples = []
        ts.record_game_rtt(290.0)
        ts.record_game_rtt(360.0)  # jitter spike
        ts.record_game_rtt(284.0)
        ts.record_game_rtt(288.0)
        # Lower half of [284, 288, 290, 360] = avg(284, 288) = 286.0 (immune to 360ms spike!)
        self.assertAlmostEqual(ts.get_game_rtt_ms(), 286.0, places=1)
        self.assertAlmostEqual(ts.get_game_rtt_jitter_ms(), 76.0, places=1)
        ts.reset_game_rtt_samples()
        ts.record_game_rtt(120.0)
        self.assertAlmostEqual(ts.get_game_rtt_ms(), 120.0, places=1)

        # 3) Auto Phase-Stagger (-1) + Adaptive FPS (6 accounts -> FPS<=90, staggered evenly across 10ms)
        ctrls = []
        stagger_res = []
        fps_res = []
        all_done = threading.Event()
        for idx in range(1, 7):
            c = MagicMock(slot_idx=idx, mirror_enabled=True, assigned_pid=os.getpid())
            def _mk_fn(i):
                def _fn(**kw):
                    stagger_res.append((i, kw["stagger_ms"]))
                    fps_res.append(kw.get("target_fps"))
                    if len(stagger_res) >= 6:
                        all_done.set()
                    return True
                return _fn
            c.start_mirror_turbo_sniping.side_effect = _mk_fn(idx)
            ctrls.append(c)

        app.controllers = ctrls
        app.mirror_snipe_delay_entry = MagicMock(get=lambda: "10")
        app.mirror_snipe_dur_entry = MagicMock(get=lambda: "15.0")
        app.mirror_stagger_ms_entry = MagicMock(get=lambda: "Auto")
        app.after = MagicMock()
        app.append_mirror_log = MagicMock()
        self.assertEqual(app.get_mirror_stagger_ms(), -1)
        t_ms = int(time.time() * 1000) + 4000
        app.start_all_mirror_turbo_sniping(from_scheduler=True, target_open_epoch_ms=t_ms, clock_calibrated=False)
        self.assertTrue(all_done.wait(timeout=2.5))
        stagger_res.sort(key=lambda x: x[0])
        self.assertEqual([x[1] for x in stagger_res], [0, 2, 3, 5, 7, 8])
        self.assertTrue(all(f == 90 for f in fps_res), f"6 accounts must use adaptive targetFps=90, got {fps_res}")



if __name__ == "__main__":
    unittest.main(verbosity=2)