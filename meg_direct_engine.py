#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Direct Frida IL2CPP Engine
=================================
Giao tiếp trực tiếp và an toàn với GameAssembly.dll qua Frida Dynamic Instrumentation.
Mô phỏng 100% cơ chế MEGAMUCore của MEGAMU Auto Train Dashboard gốc:
- Hook onEnter vào chat_update (offset 0x14B6AF0) trên Unity Main Thread.
- Thực thi MoveTo (0xD72750), ChatSend (0x14B9250), HelperStart (0x2A3B580), HelperStop (0x2A3C660).
- Push Fast Telemetry mỗi 150ms từ trong RAM tiến trình game ra Python (Zero-Polling).
- 3-Phase Safe Detach với Interceptor.flush() chống crash 0xc0000005 frida-agent.dll_unloaded.
- Mutex Process Guard tránh đa phiên Frida đồng thời trên cùng 1 Game PID.
"""

import os
import sys
import json
import time
import ctypes
if sys.platform == "win32":
    from ctypes import wintypes
import threading
import atexit
from typing import Optional, Dict, Any, List, Callable

try:
    import frida
except ImportError:
    frida = None

try:
    import psutil
except ImportError:
    psutil = None

def _safe_log(msg: str):
    try:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc), flush=True)
    except Exception:
        pass

DEFAULT_OFFSETS = {
    "game_module": "GameAssembly.dll",
    "get_player": "0x12310D0",
    "move_to": "0xB75230",
    "start_auto_move": "0xB89240",
    "stop_auto_move": "0xB86A20",
    "chat_send": "0xF69D10",
    "chat_send_cmd": "0xF5F870",
    "chat_frame_send": "0x1322DA0",
    "chat_update": "0x1317710",
    "helper_start": "0x26FE8E0",
    "helper_stop": "0x26FEA90",
    "player_name": "0x28",
    "player_level": "0x30",
    "player_class": "0x34",
    "player_coord": "0x68",
    "player_move": "0xF0",
    "player_helper": "0x1E8",
    "player_last_coord": "0x4E0",
    "auto_move_working": "0x498",
    "auto_move_type": "0x49C",
    "auto_move_helper": "0x4A0",
    "auto_move_dest": "0x4A8",
    "move_flag": "0x3C",
    "helper_state": "0x20",
    "game_type_info": "0x54E7140",
    "world_scene_index": "0x20",
    "moss_roll": "0x238B380",
    "moss_open": "0x238B0A0",
    "mirror_enter": "0xFDCA30",
    "mirror_npc_click": "0xFCE6E0",
    "mirror_is_event_map": "0xFCF820",
    "inv_sell_item": "0x1428D20",
    "inv_trash_item": "0x14281C0",
    "player_inventory": "0x1B8",
    "inventory_items": "0x28",
}

FRIDA_AGENT_JS = r"""
var ga = Process.getModuleByName('GameAssembly.dll');
var baseAddr = ga.base;

function off(v) { return ptr(v); }

var getPlayerNative = null;
try {
    var gpOffset = off('__GET_PLAYER__');
    if (!gpOffset.isNull()) {
        getPlayerNative = new NativeFunction(baseAddr.add(gpOffset), 'pointer', ['pointer']);
    }
} catch (eNative) {}

function getPlayerPtr() {
    // 1. Thử hàm native get_player
    try {
        if (getPlayerNative !== null) {
            var p = getPlayerNative(ptr(0));
            if (!p.isNull()) return p;
        }
    } catch (e1) {}

    // 2. Fallback qua Mega.Game_TypeInfo -> static_fields (+0xB8) -> Instance (+0x8) -> _Player (+0x208)
    try {
        var tiOffset = off('__GAME_TYPE_INFO__');
        if (!tiOffset.isNull()) {
            var typeInfo = baseAddr.add(tiOffset).readPointer();
            if (!typeInfo.isNull()) {
                var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                if (!staticFields.isNull()) {
                    var gameInstance = staticFields.add(ptr('0x8')).readPointer();
                    if (!gameInstance.isNull()) {
                        var p2 = gameInstance.add(ptr('0x208')).readPointer();
                        if (!p2.isNull()) return p2;
                    }
                }
            }
        }
    } catch (e2) {}

    return ptr(0);
}

var moveToNative = new NativeFunction(
    baseAddr.add(off('__MOVE_TO__')),
    'bool',
    ['pointer', 'pointer', 'float', 'pointer', 'bool', 'bool', 'pointer']
);
var il2cpp_string_new = new NativeFunction(
    ga.findExportByName('il2cpp_string_new'),
    'pointer',
    ['pointer']
);
var nativeStartHelper = new NativeFunction(baseAddr.add(off('__HELPER_START__')), 'void', ['pointer', 'pointer']);
var nativeStopHelper = new NativeFunction(baseAddr.add(off('__HELPER_STOP__')), 'void', ['pointer', 'pointer']);
var nativeStartAutoMove = new NativeFunction(baseAddr.add(off('__START_AUTO_MOVE__')), 'void', ['pointer', 'pointer', 'int', 'bool', 'pointer']);
var nativeStopAutoMove = new NativeFunction(baseAddr.add(off('__STOP_AUTO_MOVE__')), 'void', ['pointer', 'bool', 'pointer']);
var nativeChatCmd = new NativeFunction(baseAddr.add(off('__CHAT_SEND_CMD__')), 'void', ['pointer', 'pointer']);
var nativeChatGeneral = new NativeFunction(baseAddr.add(off('__CHAT_SEND__')), 'void', ['pointer', 'pointer']);
var nativeChatFrameSend = new NativeFunction(baseAddr.add(off('__CHAT_FRAME_SEND__')), 'void', ['pointer', 'pointer', 'bool', 'pointer']);

var nativeMossRoll = null;
try {
    var mrOff = off('__MOSS_ROLL__');
    if (!mrOff.isNull()) {
        nativeMossRoll = new NativeFunction(baseAddr.add(mrOff), 'void', ['int', 'pointer']);
    }
} catch (eMossRoll) {}

var nativeMossOpen = null;
try {
    var moOff = off('__MOSS_OPEN__');
    if (!moOff.isNull()) {
        nativeMossOpen = new NativeFunction(baseAddr.add(moOff), 'void', ['int', 'pointer']);
    }
} catch (eMossOpen) {}

var nativeMirrorEnter = null;
try {
    var meOff = off('__MIRROR_ENTER__');
    if (!meOff.isNull()) {
        nativeMirrorEnter = new NativeFunction(baseAddr.add(meOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMirrorEnter) {}

var nativeMirrorNpcClick = null;
try {
    var mnOff = off('__MIRROR_NPC_CLICK__');
    if (!mnOff.isNull()) {
        nativeMirrorNpcClick = new NativeFunction(baseAddr.add(mnOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMirrorNpc) {}

var nativeMirrorIsEventMap = null;
try {
    var mimOff = off('__MIRROR_IS_EVENT_MAP__');
    if (!mimOff.isNull()) {
        nativeMirrorIsEventMap = new NativeFunction(baseAddr.add(mimOff), 'bool', []);
    }
} catch (eMirrorMap) {}

var nativeInvSellItem = null;
try {
    var isiOff = off('__INV_SELL_ITEM__');
    if (!isiOff.isNull()) {
        nativeInvSellItem = new NativeFunction(baseAddr.add(isiOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eInvSell) {}

var nativeInvTrashItem = null;
try {
    var itiOff = off('__INV_TRASH_ITEM__');
    if (!itiOff.isNull()) {
        nativeInvTrashItem = new NativeFunction(baseAddr.add(itiOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eInvTrash) {}

var cfInstance = null;
var pendingCommand = null;
var chatHook = null;

try {
    var cuOff = off('__CHAT_UPDATE__');
    if (!cuOff.isNull()) {
        chatHook = Interceptor.attach(baseAddr.add(cuOff), {
            onEnter: function(args) {
                if (shuttingDown) return;
                try {
                    cfInstance = args[0];
                    if (pendingCommand !== null) {
                        var cmd = pendingCommand;
                        pendingCommand = null;
                        var str = il2cpp_string_new(Memory.allocUtf8String(cmd));
                        if (!str.isNull()) {
                            if (cmd.indexOf('/') === 0) {
                                nativeChatCmd(str, ptr(0));
                            } else {
                                nativeChatGeneral(str, ptr(0));
                            }
                            if (cfInstance && !cfInstance.isNull()) {
                                try {
                                    nativeChatFrameSend(cfInstance, str, 1, ptr(0));
                                } catch (eF) {}
                            }
                        }
                    }
                } catch (eEnter) {}
            }
        });
    }
} catch (eHook) {}

var pDomainGet = ga.findExportByName('il2cpp_domain_get');
var pThreadAttach = ga.findExportByName('il2cpp_thread_attach');
var il2cpp_domain_get = pDomainGet ? new NativeFunction(pDomainGet, 'pointer', []) : null;
var il2cpp_thread_attach = pThreadAttach ? new NativeFunction(pThreadAttach, 'pointer', ['pointer']) : null;

function ensureThreadAttached() {
    try {
        if (il2cpp_domain_get && il2cpp_thread_attach) {
            var domain = il2cpp_domain_get();
            if (!domain.isNull()) {
                il2cpp_thread_attach(domain);
            }
        }
    } catch (e) {}
}

var coordBuf = Memory.alloc(64);
var autoMoveCoordBuf = Memory.alloc(64);
var cachedCoordKlass = ptr(0);
var shuttingDown = false;

function readPlayerInfoSnapshot(readName) {
    try {
        var p = getPlayerPtr();
        if (p.isNull()) return null;

        var charName = lastFastCharName;
        if (readName || !charName) {
            try {
                var namePtr = p.add(off('__PLAYER_NAME__')).readPointer();
                if (!namePtr.isNull()) {
                    var len = namePtr.add(0x10).readS32();
                    if (len > 0 && len < 64) {
                        charName = namePtr.add(0x14).readUtf16String(len);
                        lastFastCharName = charName;
                    }
                }
            } catch (e) {}
        }

        var level = 0, classId = 0;
        try {
            level = p.add(off('__PLAYER_LEVEL__')).readS32();
            classId = p.add(off('__PLAYER_CLASS__')).readS32();
        } catch (e) {}

        var tileX = 0, tileY = 0, mapId = -1;
        try {
            var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
            if (!curCoord.isNull()) {
                tileX = curCoord.add(0x10).readS32();
                tileY = curCoord.add(0x14).readS32();
            }
            if ((tileX === 0 && tileY === 0) || curCoord.isNull()) {
                var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                if (!lastCoord.isNull()) {
                    var lx = lastCoord.add(0x10).readS32();
                    var ly = lastCoord.add(0x14).readS32();
                    if (tileX === 0 && tileY === 0 && (lx > 0 || ly > 0)) {
                        tileX = lx;
                        tileY = ly;
                    }
                }
            }
        } catch (eCoord) {}

        // Đọc Map ID (SceneIndex) chuẩn xác 100% từ Mega.Game_TypeInfo -> Instance -> World
        try {
            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (!typeInfo.isNull()) {
                var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                if (!staticFields.isNull()) {
                    var gameInstance = staticFields.add(ptr('0x8')).readPointer();
                    if (!gameInstance.isNull()) {
                        var world = gameInstance.add(off('__GAME_WORLD__')).readPointer();
                        if (!world.isNull()) {
                            var sc = world.add(off('__WORLD_SCENE_INDEX__')).readS32();
                            if (sc >= 0 && sc <= 255) mapId = sc;
                        }
                    }
                }
            }
        } catch (eWorld) {}

        var isMoving = false;
        try {
            var move = p.add(off('__PLAYER_MOVE__')).readPointer();
            if (!move.isNull()) isMoving = move.add(off('__MOVE_FLAG__')).readU8() === 1;
        } catch (e) {}

        var helperState = 0;
        try {
            var h = p.add(off('__PLAYER_HELPER__')).readPointer();
            if (!h.isNull()) helperState = h.add(off('__HELPER_STATE__')).readU8();
        } catch (e) {}

        return {
            name: charName,
            level: level,
            classId: classId,
            mapId: mapId,
            tileX: tileX,
            tileY: tileY,
            x: tileX,
            y: tileY,
            isMoving: isMoving,
            helperState: helperState
        };
    } catch (e) {
        return null;
    }
}

var fastTelemetryTimer = null;
var lastFastSignature = '';
var lastFastSentAt = 0;
var lastFastNameReadAt = 0;
var lastFastCharName = '';
var fastTelemetrySeq = 0;
function fastTelemetryTick() {
    if (shuttingDown) return;
    try {
        var nowMs = Date.now();
        var readName = (!lastFastCharName || (nowMs - lastFastNameReadAt) >= 2000);
        if (readName) lastFastNameReadAt = nowMs;
        var info = readPlayerInfoSnapshot(readName);
        if (info === null) return;
        var sig = [info.level, info.mapId, info.tileX, info.tileY, info.isMoving ? 1 : 0, info.helperState].join('|');
        if (sig !== lastFastSignature || (nowMs - lastFastSentAt) >= 700) {
            lastFastSignature = sig;
            lastFastSentAt = nowMs;
            fastTelemetrySeq += 1;
            send({type: 'fast_state', info: info, ts: nowMs, seq: fastTelemetrySeq});
        }
    } catch (e) {}
}
fastTelemetryTimer = setInterval(fastTelemetryTick, 150);
fastTelemetryTick();

rpc.exports = {
    getPlayerInfo: function() {
        return readPlayerInfoSnapshot(true);
    },

    moveTo: function(targetX, targetY) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return false;
            var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
            var klass = ptr(0);
            try { if (!curCoord.isNull()) klass = curCoord.readPointer(); } catch (e1) {}
            if (klass.isNull()) {
                try {
                    var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                    if (!lastCoord.isNull()) klass = lastCoord.readPointer();
                } catch (e2) {}
            }
            if (klass.isNull()) {
                try {
                    var destCoord = p.add(off('__AUTO_MOVE_DEST__')).readPointer();
                    if (!destCoord.isNull()) klass = destCoord.readPointer();
                } catch (e3) {}
            }
            if (klass.isNull()) {
                try {
                    var tCoord = p.add(ptr('0x18')).readPointer();
                    if (!tCoord.isNull()) klass = tCoord.readPointer();
                } catch (e4) {}
            }
            if (!klass.isNull()) {
                cachedCoordKlass = klass;
            } else if (!cachedCoordKlass.isNull()) {
                klass = cachedCoordKlass;
            }

            if (!klass.isNull()) {
                coordBuf.writePointer(klass);
                coordBuf.add(0x08).writePointer(ptr(0));
                coordBuf.add(0x10).writeS32(parseInt(targetX));
                coordBuf.add(0x14).writeS32(parseInt(targetY));
                var ok = moveToNative(p, coordBuf, 0.0, ptr(0), 0, 1, ptr(0));
                return Boolean(ok);
            }
        } catch (eM) {}
        return false;
    },

    cancelMove: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                nativeStopAutoMove(p, 1, ptr(0));
                return true;
            }
        } catch (eC) {}
        return false;
    },

    getHelperState: function() {
        try {
            var p = getPlayerPtr();
            if (p.isNull()) return 0;
            var h = p.add(off('__PLAYER_HELPER__')).readPointer();
            if (h.isNull()) return 0;
            return h.add(off('__HELPER_STATE__')).readU8();
        } catch (e) {
            return 0;
        }
    },

    setHelperStateDirect: function(val) {
        try {
            var p = getPlayerPtr();
            if (p.isNull()) return false;
            var h = p.add(off('__PLAYER_HELPER__')).readPointer();
            if (h.isNull()) return false;
            h.add(off('__HELPER_STATE__')).writeU8(parseInt(val) ? 1 : 0);
            return true;
        } catch (e) {
            return false;
        }
    },

    sendChatNative: function(cmd) {
        try {
            ensureThreadAttached();
            cmd = String(cmd || '').trim();
            if (!cmd) return false;

            // 1. Ưu tiên queue pendingCommand chạy ngay trên Unity Main Thread (thông qua chatHook Update)
            if (chatHook !== null) {
                pendingCommand = cmd;
                return true;
            }

            // 2. Direct call nếu hook chưa active
            var str = il2cpp_string_new(Memory.allocUtf8String(cmd));
            if (!str.isNull()) {
                if (cmd.indexOf('/') === 0) {
                    nativeChatCmd(str, ptr(0));
                } else {
                    nativeChatGeneral(str, ptr(0));
                }
                return true;
            }
        } catch (e) {}
        return false;
    },

    send_chat_native: function(cmd) {
        return this.sendChatNative(cmd);
    },

    startHelper: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                var h = p.add(off('__PLAYER_HELPER__')).readPointer();
                if (!h.isNull()) {
                    nativeStartHelper(h, ptr(0));
                    return true;
                }
            }
        } catch (eH) {}
        return false;
    },

    stopHelper: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                var h = p.add(off('__PLAYER_HELPER__')).readPointer();
                if (!h.isNull()) {
                    nativeStopHelper(h, ptr(0));
                    return true;
                }
            }
        } catch (eH) {}
        return false;
    },

    startAutoMove: function(x, y, helper) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return false;
            var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
            var klass = ptr(0);
            try { if (!curCoord.isNull()) klass = curCoord.readPointer(); } catch (e1) {}
            if (klass.isNull()) {
                try {
                    var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                    if (!lastCoord.isNull()) klass = lastCoord.readPointer();
                } catch (e2) {}
            }
            if (klass.isNull()) {
                try {
                    var destCoord = p.add(off('__AUTO_MOVE_DEST__')).readPointer();
                    if (!destCoord.isNull()) klass = destCoord.readPointer();
                } catch (e3) {}
            }
            if (klass.isNull()) {
                try {
                    var tCoord = p.add(ptr('0x18')).readPointer();
                    if (!tCoord.isNull()) klass = tCoord.readPointer();
                } catch (e4) {}
            }
            if (!klass.isNull()) {
                cachedCoordKlass = klass;
            } else if (!cachedCoordKlass.isNull()) {
                klass = cachedCoordKlass;
            }

            if (!klass.isNull()) {
                autoMoveCoordBuf.writePointer(klass);
                autoMoveCoordBuf.add(0x08).writePointer(ptr(0));
                autoMoveCoordBuf.add(0x10).writeS32(parseInt(x));
                autoMoveCoordBuf.add(0x14).writeS32(parseInt(y));

                // 1. Cấu hình cờ Auto Move chuẩn Type 0 để vòng lặp Update của game khởi tạo BodyActivity (0xabb8d0)
                p.add(off('__AUTO_MOVE_DEST__')).writePointer(autoMoveCoordBuf);
                p.add(off('__AUTO_MOVE_TYPE__')).writeS32(0);
                p.add(off('__AUTO_MOVE_HELPER__')).writeU8(helper ? 1 : 0);
                p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);

                // 2. Kích hoạt trực tiếp bước di chuyển khởi hành qua moveToNative (BJKOMKOAAOG)
                // Giúp nhân vật lập tức bước đi về hướng đích mà KHÔNG CẦN người chơi phải click chuột mồi!
                try {
                    moveToNative(p, autoMoveCoordBuf, 0.0, ptr(0), 0, 1, ptr(0));
                } catch (eMove) {}

                return true;
            }
        } catch (eAM) {}
        return false;
    },

    isAutoMoveActive: function() {
        try {
            var p = getPlayerPtr();
            if (p.isNull()) return false;
            return Boolean(p.add(off('__AUTO_MOVE_WORKING__')).readU8());
        } catch (e) {
            return false;
        }
    },

    stopAutoMove: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                nativeStopAutoMove(p, 1, ptr(0));
                return true;
            }
        } catch (eSM) {}
        return false;
    },

    rollMoss: function(categoryId) {
        try {
            ensureThreadAttached();
            if (nativeMossRoll !== null) {
                nativeMossRoll(parseInt(categoryId), ptr(0));
                return true;
            }
        } catch (eMR) {}
        return false;
    },

    openMoss: function(categoryId) {
        try {
            ensureThreadAttached();
            if (nativeMossOpen !== null) {
                nativeMossOpen(parseInt(categoryId || 0), ptr(0));
                return true;
            }
        } catch (eMO) {}
        return false;
    },

    enterMirror: function() {
        try {
            ensureThreadAttached();
            if (nativeMirrorEnter !== null) {
                nativeMirrorEnter(ptr(0), ptr(0));
                return true;
            }
        } catch (eME) {}
        return false;
    },

    clickMirrorNpc: function(npcPtr) {
        try {
            ensureThreadAttached();
            if (nativeMirrorNpcClick !== null) {
                var p = (npcPtr && npcPtr !== 0) ? ptr(npcPtr) : ptr(0);
                nativeMirrorNpcClick(p, ptr(0));
                return true;
            }
        } catch (eMN) {}
        return false;
    },

    isMirrorEventMap: function() {
        try {
            ensureThreadAttached();
            if (nativeMirrorIsEventMap !== null) {
                return Boolean(nativeMirrorIsEventMap());
            }
        } catch (eMM) {}
        return false;
    },

    getInventorySummary: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return JSON.stringify({ error: "no_player" });

            var invOff = off('__PLAYER_INVENTORY__');
            var inv = p.add(invOff).readPointer();
            if (inv.isNull()) return JSON.stringify({ error: "no_inventory" });

            var itemsOff = off('__INVENTORY_ITEMS__');
            var itemsArr = inv.add(itemsOff).readPointer();
            if (itemsArr.isNull()) return JSON.stringify({ error: "no_items_arr" });

            var totalMain = 64;
            var freeSlots = 0;
            var junkSlots = [];
            var keptSlots = [];

            for (var s = 12; s < 76; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) {
                    freeSlots++;
                    continue;
                }
                var itemIndex = itemPtr.add(0x10).readS32();
                var itemLevel = itemPtr.add(0x14).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var sec = Math.floor(itemIndex / 512);

                // Bảo tồn nghiêm ngặt:
                // 1. Đồ Hoàn Hảo (excOpt > 0)
                // 2. Đồ Thần (ancOpt > 0)
                // 3. Đồ Socket (sockOpt > 0)
                // 4. Đồ đã nâng cấp/đập ngọc (itemLevel > 0)
                // 5. Ngọc và nguyên liệu/vé/talisman (sec >= 12 && sec <= 15)
                var isKept = (excOpt > 0) || (ancOpt > 0) || (sockOpt > 0) || (itemLevel > 0) || (sec >= 12 && sec <= 15);
                if (isKept) {
                    keptSlots.push({ slot: s, index: itemIndex, level: itemLevel, exc: excOpt, anc: ancOpt, sock: sockOpt });
                } else {
                    junkSlots.push({ slot: s, index: itemIndex, level: itemLevel });
                }
            }

            return JSON.stringify({
                total: totalMain,
                free: freeSlots,
                used: totalMain - freeSlots,
                junkCount: junkSlots.length,
                keptCount: keptSlots.length,
                junkSlots: junkSlots
            });
        } catch (eInv) {
            return JSON.stringify({ error: eInv.toString() });
        }
    },

    cleanInventoryJunk: function(method) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return JSON.stringify({ cleaned: 0, error: "no_player" });

            var invOff = off('__PLAYER_INVENTORY__');
            var inv = p.add(invOff).readPointer();
            if (inv.isNull()) return JSON.stringify({ cleaned: 0, error: "no_inventory" });

            var itemsOff = off('__INVENTORY_ITEMS__');
            var itemsArr = inv.add(itemsOff).readPointer();
            if (itemsArr.isNull()) return JSON.stringify({ cleaned: 0, error: "no_items_arr" });

            var cleaned = 0;
            var useMethod = method || "both";

            for (var s = 12; s < 76; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = itemPtr.add(0x10).readS32();
                var itemLevel = itemPtr.add(0x14).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var sec = Math.floor(itemIndex / 512);

                // Giữ lại tuyệt đối mọi đồ giá trị
                if (excOpt > 0 || ancOpt > 0 || sockOpt > 0 || itemLevel > 0 || (sec >= 12 && sec <= 15)) {
                    continue;
                }

                var itemHandled = false;
                try {
                    if (useMethod === "sell" || useMethod === "both") {
                        if (nativeInvSellItem !== null) {
                            nativeInvSellItem(s, itemPtr, ptr(0));
                            itemHandled = true;
                        }
                    }
                    if (!itemHandled && (useMethod === "trash" || useMethod === "both")) {
                        if (nativeInvTrashItem !== null) {
                            nativeInvTrashItem(s, ptr(0), ptr(0));
                            itemHandled = true;
                        }
                    }
                    if (itemHandled) {
                        cleaned++;
                        try { Thread.sleep(0.015); } catch (eSleep) {}
                    }
                } catch (eAct) {}
            }
            return JSON.stringify({ cleaned: cleaned });
        } catch (e) {
            return JSON.stringify({ cleaned: 0, error: e.toString() });
        }
    },

    sellInventorySlot: function(slot) {
        try {
            ensureThreadAttached();
            var s = parseInt(slot);
            var itemP = ptr(0);
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            itemP = itemsArr.add(0x20 + s * 8).readPointer();
                        }
                    }
                }
            } catch (eP) {}
            if (nativeInvSellItem !== null) {
                nativeInvSellItem(s, itemP, ptr(0));
                return true;
            }
            if (nativeInvTrashItem !== null) {
                nativeInvTrashItem(s, ptr(0), ptr(0));
                return true;
            }
        } catch (e) {}
        return false;
    },

    cleanup: function() {
        shuttingDown = true;
        try {
            if (chatHook !== null) {
                chatHook.detach();
                chatHook = null;
            }
        } catch (eH) {}
        try {
            if (fastTelemetryTimer !== null) {
                clearInterval(fastTelemetryTimer);
                fastTelemetryTimer = null;
            }
        } catch (e0) {}
        return true;
    }
};
"""


class MegDirectEngine:
    """
    Direct Hook Engine cho 1 Game Client PID qua Frida.
    Quản lý luồng gọi an toàn, tự phục hồi và chia sẻ trạng thái cho AutoTrainWorker.
    """
    _instances: Dict[int, "MegDirectEngine"] = {}
    _pool_lock = threading.Lock()

    @classmethod
    def get_engine(cls, pid: int) -> "MegDirectEngine":
        with cls._pool_lock:
            if pid not in cls._instances:
                cls._instances[pid] = cls(pid)
            return cls._instances[pid]

    @classmethod
    def has_engine(cls, pid: int) -> bool:
        with cls._pool_lock:
            return pid in cls._instances

    @classmethod
    def release_engine(cls, pid: int):
        with cls._pool_lock:
            if pid in cls._instances:
                try:
                    cls._instances[pid].detach()
                except Exception:
                    pass
                del cls._instances[pid]

    @classmethod
    def cleanup_all(cls):
        with cls._pool_lock:
            for pid, eng in list(cls._instances.items()):
                try:
                    eng.detach()
                except Exception:
                    pass
            cls._instances.clear()

    def __init__(self, pid: int):
        self.pid = pid
        self._rpc_lock = threading.RLock()
        self.session: Optional[Any] = None
        self.script: Optional[Any] = None
        self.is_ready = False
        self._mutex_handle = None

        # Fast Telemetry Cache
        self.last_fast_state: Optional[Dict[str, Any]] = None
        self.last_fast_state_time: float = 0.0
        self.last_fast_seq: int = 0
        self.telemetry_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Load offsets
        self.offsets = dict(DEFAULT_OFFSETS)
        self._load_offsets_file()

        # Connect
        self._claim_mutex()
        self._attach()

    def register_telemetry_callback(self, cb: Callable[[Dict[str, Any]], None]):
        """Đăng ký callback nhận dữ liệu telemetry RAM thời gian thực (150ms)."""
        if cb and cb not in self.telemetry_callbacks:
            self.telemetry_callbacks.append(cb)

    def unregister_telemetry_callback(self, cb: Callable[[Dict[str, Any]], None]):
        if cb in self.telemetry_callbacks:
            self.telemetry_callbacks.remove(cb)

    def _load_offsets_file(self):
        # 1. Khởi tạo toàn bộ offset mặc định
        self.offsets = dict(DEFAULT_OFFSETS)

        # 2. Nạp Game Offsets từ Native C++ Security Bridge nếu có (lớp nền tảng)
        try:
            from license_client import get_secure_game_offsets, is_native_bridge_active
            if is_native_bridge_active():
                sec_offsets = get_secure_game_offsets()
                if sec_offsets and isinstance(sec_offsets, dict):
                    for k, v in sec_offsets.items():
                        if v:
                            self.offsets[k] = v
                    _safe_log("[MegDirectEngine] Đã nạp thành công Game Offsets từ Native C++ Security Bridge.")
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi trích xuất Native Offsets: {e}")

        # 3. Đọc cấu hình đĩa JSON để nạp bản cập nhật mới nhất (ƯU TIÊN TUYỆT ĐỐI ghi đè)
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_paths = [
            os.path.join(base_dir, "config", "megamu_offsets.json"),
            os.path.join(base_dir, "megamu_offsets.json"),
        ]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_paths.append(os.path.join(meipass, "config", "megamu_offsets.json"))
            candidate_paths.append(os.path.join(meipass, "megamu_offsets.json"))

        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if v:
                                self.offsets[k] = v
                        _safe_log(f"[MegDirectEngine] Đã nạp và ưu tiên cấu hình offsets từ tệp đĩa: {p}")
                        break
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] Lỗi đọc megamu_offsets.json: {e}")

    def _claim_mutex(self):
        """Khóa Named Mutex trên Windows để đảm bảo mỗi PID chỉ gắn 1 Frida engine duy nhất."""
        if sys.platform != "win32":
            return
        try:
            m_name = f"Local\\MEGAMU_AutoTrain_Rebuild_GamePID_{self.pid}"
            handle = ctypes.windll.kernel32.CreateMutexW(None, True, m_name)
            if handle:
                self._mutex_handle = handle
        except Exception:
            pass

    def _release_mutex(self):
        if self._mutex_handle and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            except Exception:
                pass
            self._mutex_handle = None

    def _generate_js(self) -> str:
        js = FRIDA_AGENT_JS
        mapping = {
            "__GET_PLAYER__": self.offsets.get("get_player") or DEFAULT_OFFSETS.get("get_player", "0x12310D0"),
            "__MOVE_TO__": self.offsets.get("move_to") or DEFAULT_OFFSETS.get("move_to", "0xB75230"),
            "__CHAT_SEND__": self.offsets.get("chat_send") or DEFAULT_OFFSETS.get("chat_send", "0xF69D10"),
            "__CHAT_SEND_CMD__": self.offsets.get("chat_send_cmd") or DEFAULT_OFFSETS.get("chat_send_cmd", "0xF5F870"),
            "__CHAT_FRAME_SEND__": self.offsets.get("chat_frame_send") or DEFAULT_OFFSETS.get("chat_frame_send", "0x1322DA0"),
            "__CHAT_UPDATE__": self.offsets.get("chat_update") or DEFAULT_OFFSETS.get("chat_update", "0x1317710"),
            "__HELPER_START__": self.offsets.get("helper_start") or DEFAULT_OFFSETS.get("helper_start", "0x26FE8E0"),
            "__HELPER_STOP__": self.offsets.get("helper_stop") or DEFAULT_OFFSETS.get("helper_stop", "0x26FEA90"),
            "__PLAYER_NAME__": self.offsets.get("player_name") or DEFAULT_OFFSETS.get("player_name", "0x28"),
            "__PLAYER_LEVEL__": self.offsets.get("player_level") or DEFAULT_OFFSETS.get("player_level", "0x30"),
            "__PLAYER_CLASS__": self.offsets.get("player_class") or DEFAULT_OFFSETS.get("player_class", "0x34"),
            "__PLAYER_COORD__": self.offsets.get("player_coord") or DEFAULT_OFFSETS.get("player_coord", "0x68"),
            "__PLAYER_MOVE__": self.offsets.get("player_move") or DEFAULT_OFFSETS.get("player_move", "0xF0"),
            "__PLAYER_HELPER__": self.offsets.get("player_helper") or DEFAULT_OFFSETS.get("player_helper", "0x1E8"),
            "__PLAYER_LAST_COORD__": self.offsets.get("player_last_coord") or DEFAULT_OFFSETS.get("player_last_coord", "0x4E0"),
            "__MOVE_FLAG__": self.offsets.get("move_flag") or DEFAULT_OFFSETS.get("move_flag", "0x3C"),
            "__HELPER_STATE__": self.offsets.get("helper_state") or DEFAULT_OFFSETS.get("helper_state", "0x20"),
            "__GAME_TYPE_INFO__": self.offsets.get("game_type_info") or DEFAULT_OFFSETS.get("game_type_info", "0x54E7140"),
            "__GAME_WORLD__": self.offsets.get("game_world") or DEFAULT_OFFSETS.get("game_world", "0x200"),
            "__START_AUTO_MOVE__": self.offsets.get("start_auto_move") or DEFAULT_OFFSETS.get("start_auto_move", "0xB89240"),
            "__STOP_AUTO_MOVE__": self.offsets.get("stop_auto_move") or DEFAULT_OFFSETS.get("stop_auto_move", "0xB86A20"),
            "__AUTO_MOVE_WORKING__": self.offsets.get("auto_move_working") or DEFAULT_OFFSETS.get("auto_move_working", "0x498"),
            "__AUTO_MOVE_TYPE__": self.offsets.get("auto_move_type") or DEFAULT_OFFSETS.get("auto_move_type", "0x49C"),
            "__AUTO_MOVE_HELPER__": self.offsets.get("auto_move_helper") or DEFAULT_OFFSETS.get("auto_move_helper", "0x4A0"),
            "__AUTO_MOVE_DEST__": self.offsets.get("auto_move_dest") or DEFAULT_OFFSETS.get("auto_move_dest", "0x4A8"),
            "__WORLD_SCENE_INDEX__": self.offsets.get("world_scene_index") or DEFAULT_OFFSETS.get("world_scene_index", "0x20"),
            "__MOSS_ROLL__": self.offsets.get("moss_roll") or DEFAULT_OFFSETS.get("moss_roll", "0x238B380"),
            "__MOSS_OPEN__": self.offsets.get("moss_open") or DEFAULT_OFFSETS.get("moss_open", "0x238B0A0"),
            "__MIRROR_ENTER__": self.offsets.get("mirror_enter") or DEFAULT_OFFSETS.get("mirror_enter", "0xFDCA30"),
            "__MIRROR_NPC_CLICK__": self.offsets.get("mirror_npc_click") or DEFAULT_OFFSETS.get("mirror_npc_click", "0xFCE6E0"),
            "__MIRROR_IS_EVENT_MAP__": self.offsets.get("mirror_is_event_map") or DEFAULT_OFFSETS.get("mirror_is_event_map", "0xFCF820"),
            "__INV_SELL_ITEM__": self.offsets.get("inv_sell_item") or DEFAULT_OFFSETS.get("inv_sell_item", "0x1428D20"),
            "__INV_TRASH_ITEM__": self.offsets.get("inv_trash_item") or DEFAULT_OFFSETS.get("inv_trash_item", "0x14281C0"),
            "__PLAYER_INVENTORY__": self.offsets.get("player_inventory") or DEFAULT_OFFSETS.get("player_inventory", "0x1B8"),
            "__INVENTORY_ITEMS__": self.offsets.get("inventory_items") or DEFAULT_OFFSETS.get("inventory_items", "0x28"),
        }
        for k, v in mapping.items():
            js = js.replace(k, str(v))
        return js

    def _on_message(self, message: Dict[str, Any], data: Any):
        try:
            if message.get("type") == "send":
                payload = message.get("payload")
                if isinstance(payload, dict):
                    p_type = payload.get("type")
                    if p_type == "fast_state":
                        info = payload.get("info")
                        if isinstance(info, dict):
                            if "tileX" in info and "x" not in info:
                                info["x"] = info["tileX"]
                            if "tileY" in info and "y" not in info:
                                info["y"] = info["tileY"]
                            if "x" in info and "tileX" not in info:
                                info["tileX"] = info["x"]
                            if "y" in info and "tileY" not in info:
                                info["tileY"] = info["y"]
                            self.last_fast_state = info
                            self.last_fast_state_time = time.time()
                            self.last_fast_seq = payload.get("seq", 0)
                            for cb in list(self.telemetry_callbacks):
                                try:
                                    cb(info)
                                except Exception:
                                    pass
                    elif p_type == "chat_dispatched":
                        cmd_val = payload.get("cmd")
                        if payload.get("success"):
                            _safe_log(f"[MegDirectEngine] Native Chat đã gửi thành công: '{cmd_val}'")
                        else:
                            _safe_log(f"[MegDirectEngine] Native Chat gửi lỗi '{cmd_val}': {payload.get('error')}")
        except Exception:
            pass

    def attach(self) -> bool:
        if self.is_ready:
            return True
        return self._attach()

    def _attach(self) -> bool:
        if frida is None:
            _safe_log("[MegDirectEngine] Thư viện frida chưa được cài đặt trong môi trường python.")
            return False

        try:
            self.session = frida.attach(self.pid)
            js_code = self._generate_js()
            self.script = self.session.create_script(js_code)
            self.script.on("message", self._on_message)
            self.script.load()
            self.is_ready = True
            return True
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi attach Frida tới PID {self.pid}: {e}")
            self.is_ready = False
            return False

    def _call(self, func_name: str, *args, timeout: float = 4.0) -> Any:
        if not self.is_ready or not self.script:
            return None
        with self._rpc_lock:
            try:
                fn = getattr(self.script.exports_sync, func_name, None)
                if not fn:
                    if "_" in func_name:
                        camel = "".join(w.capitalize() if i > 0 else w for i, w in enumerate(func_name.split("_")))
                        fn = getattr(self.script.exports_sync, camel, None)
                    else:
                        import re
                        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', func_name).lower()
                        fn = getattr(self.script.exports_sync, snake, None)
                if fn:
                    return fn(*args)
            except Exception as e:
                # Nếu RPC lỗi do script bị mất, đánh dấu cần gắn lại
                err_str = str(e).lower()
                if "detached" in err_str or "destroyed" in err_str or "script is destroyed" in err_str:
                    self.is_ready = False
                return None
        return None

    def read_player_info_via_ram(self) -> Optional[Dict[str, Any]]:
        """Đọc trực tiếp thông tin nhân vật qua Win32 ReadProcessMemory từ GameAssembly.dll (Zero-Injection Fallback)."""
        if not self.pid or (psutil and not psutil.pid_exists(self.pid)):
            return None
        try:
            from meg_navigator import ProcessMemoryReader
            live = ProcessMemoryReader.read_live_state(self.pid)
            lvl = ProcessMemoryReader.read_character_level(self.pid)
            helper = ProcessMemoryReader.read_helper_state(self.pid)
            char_name = ProcessMemoryReader.read_character_name(self.pid) if hasattr(ProcessMemoryReader, "read_character_name") else ""

            tileX, tileY = 0, 0
            mapId = -1
            if live:
                mapId = live[0] if live[0] is not None else -1
                tileX = live[2] if live[2] is not None else 0
                tileY = live[3] if live[3] is not None else 0

            is_helper = 1 if (helper and helper[0]) else 0

            is_moving = ProcessMemoryReader.read_movement_state(self.pid) if hasattr(ProcessMemoryReader, "read_movement_state") else False
            auto_move = ProcessMemoryReader.read_auto_move_state(self.pid) if hasattr(ProcessMemoryReader, "read_auto_move_state") else (False, -1, False, None)

            if (lvl is None or lvl == 0) and tileX == 0 and tileY == 0 and not char_name:
                return None

            return {
                "name": char_name or "",
                "level": lvl or 0,
                "tileX": tileX,
                "tileY": tileY,
                "x": tileX,
                "y": tileY,
                "mapId": mapId,
                "isMoving": is_moving,
                "helperState": is_helper,
                "autoMoveWorking": auto_move[0],
                "autoMoveType": auto_move[1],
                "autoMoveHelper": auto_move[2],
                "autoMoveDest": auto_move[3],
            }
        except Exception:
            return None

    def get_player_info(self, max_age: float = 0.55) -> Optional[Dict[str, Any]]:
        """Lấy thông tin nhân vật từ Fast Telemetry nếu còn mới, fallback gọi RPC hoặc đọc RAM trực tiếp."""
        now = time.time()
        if self.last_fast_state and (now - self.last_fast_state_time) <= max_age:
            return self.last_fast_state

        if self.is_ready:
            res = self._call("getPlayerInfo")
            if res and isinstance(res, dict):
                if "tileX" in res and "x" not in res:
                    res["x"] = res["tileX"]
                if "tileY" in res and "y" not in res:
                    res["y"] = res["tileY"]
                if "x" in res and "tileX" not in res:
                    res["tileX"] = res["x"]
                if "y" in res and "tileY" not in res:
                    res["tileY"] = res["y"]

                # Nếu Frida trả về nhưng tọa độ = 0, bù tọa độ qua RAM reader
                if res.get("tileX", 0) == 0 and res.get("tileY", 0) == 0:
                    ram_fallback = self.read_player_info_via_ram()
                    if ram_fallback and (ram_fallback.get("tileX", 0) > 0 or ram_fallback.get("tileY", 0) > 0):
                        res["tileX"] = ram_fallback["tileX"]
                        res["tileY"] = ram_fallback["tileY"]
                        res["x"] = ram_fallback["tileX"]
                        res["y"] = ram_fallback["tileY"]

                self.last_fast_state = res
                self.last_fast_state_time = now
                return res

        # Fallback đọc trực tiếp RAM nếu Frida chưa sẵn sàng hoặc RPC không trả về
        ram_res = self.read_player_info_via_ram()
        if ram_res:
            self.last_fast_state = ram_res
            self.last_fast_state_time = now
            return ram_res

        return self.last_fast_state

    def start_auto_move(self, target_x: int, target_y: int, helper: bool = False) -> bool:
        """Kích hoạt Auto Move của game tới tọa độ (target_x, target_y).
        1. Ưu tiên Frida Native Hook (startAutoMove).
        2. Thử kích hoạt trực tiếp vào RAM game (write_auto_move_state).
        3. Fallback sang Background Input Simulator nếu RAM/Native chưa hỗ trợ.
        """
        if self.is_ready:
            try:
                res = self._call("startAutoMove", int(target_x), int(target_y), bool(helper))
                if res:
                    return True
            except Exception:
                pass

        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "write_auto_move_state"):
                ok_ram = ProcessMemoryReader.write_auto_move_state(self.pid, int(target_x), int(target_y), helper=helper)
                if ok_ram:
                    return True
        except Exception:
            pass

        return self.move_to(target_x, target_y)

    def stop_auto_move(self) -> bool:
        """Dừng Auto Move của game."""
        if self.is_ready:
            try:
                self._call("stopAutoMove")
            except Exception:
                pass

        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "cancel_auto_move_state"):
                ProcessMemoryReader.cancel_auto_move_state(self.pid)
        except Exception:
            pass

        return self.cancel_move()

    def is_auto_move_active(self) -> bool:
        """Kiểm tra Auto Move có đang hoạt động hay không."""
        if self.is_ready:
            try:
                res = self._call("isAutoMoveActive")
                if res is not None:
                    return bool(res)
            except Exception:
                pass

        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "read_auto_move_state"):
                st = ProcessMemoryReader.read_auto_move_state(self.pid)
                return bool(st[0])
        except Exception:
            pass
        return False

    def move_to(self, target_x: int, target_y: int, bypass_angle: float = 0.0) -> bool:
        """Kích hoạt di chuyển tới tọa độ (target_x, target_y).
        1. Ưu tiên Frida Native Hook nếu có (Unity Navmesh).
        2. Thử kích hoạt Auto Move trực tiếp qua RAM game (Zero-Injection).
        3. Fallback sang Zero-Focus Background Input Simulator (Isometric Projection + Micro-Sync).
        """
        if self.is_ready:
            try:
                res = self._call("startAutoMove", int(target_x), int(target_y), False)
                if res:
                    return True
            except Exception:
                pass
            try:
                res = self._call("moveTo", int(target_x), int(target_y))
                if res:
                    return True
            except Exception:
                pass

        # Thử kích hoạt Auto Move RAM
        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "write_auto_move_state"):
                ok_ram = ProcessMemoryReader.write_auto_move_state(self.pid, int(target_x), int(target_y), helper=False)
                if ok_ram:
                    return True
        except Exception:
            pass

        # Fallback: Zero-Focus Background Input Simulator (PostMessage / Micro-Sync)
        hwnd = self.get_hwnd()
        if not hwnd or sys.platform != "win32":
            return False

        try:
            from meg_navigator import game_coord_to_screen_pixel, BackgroundInputSimulator, ProcessMemoryReader
            user32 = ctypes.windll.user32

            cur_x, cur_y = 0, 0
            if self.last_fast_state:
                cur_x = int(self.last_fast_state.get("tileX", 0))
                cur_y = int(self.last_fast_state.get("tileY", 0))
            if cur_x == 0 and cur_y == 0:
                live = ProcessMemoryReader.read_live_state(self.pid)
                if live and live[2] is not None and live[3] is not None:
                    cur_x, cur_y = int(live[2]), int(live[3])

            if cur_x == 0 and cur_y == 0:
                return False

            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            cw = max(rect.right - rect.left, 1024)
            ch = max(rect.bottom - rect.top, 768)

            dist = max(abs(int(target_x) - cur_x), abs(int(target_y) - cur_y))
            is_touchdown = (dist <= 2)

            px, py = game_coord_to_screen_pixel(
                cur_x, cur_y,
                int(target_x), int(target_y),
                cw, ch,
                camera_angle_deg=float(bypass_angle),
                is_final_touchdown=is_touchdown
            )

            # Micro-sync click đảm bảo Unity Engine bắt đúng tọa độ click kể cả khi đang un-focus
            ok = BackgroundInputSimulator.micro_sync_click(hwnd, px, py, duration_ms=25)
            return bool(ok)
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi move_to fallback: {e}")
            return False

    def cancel_move(self) -> bool:
        """Hủy lệnh di chuyển và xóa cờ di chuyển của nhân vật."""
        if self.is_ready:
            try:
                res = self._call("cancelMove")
                if res:
                    return True
            except Exception:
                pass

        # Hủy Auto Move RAM nếu có
        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "cancel_auto_move_state"):
                ProcessMemoryReader.cancel_auto_move_state(self.pid)
        except Exception:
            pass

        # Fallback: click ngay dưới chân nhân vật để dừng bước
        hwnd = self.get_hwnd()
        if hwnd and sys.platform != "win32":
            try:
                from meg_navigator import BackgroundInputSimulator
                user32 = ctypes.windll.user32
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                cw = max(rect.right - rect.left, 1024)
                ch = max(rect.bottom - rect.top, 768)
                cx = cw // 2
                cy = (ch // 2) + 15
                BackgroundInputSimulator.micro_sync_click(hwnd, cx, cy, duration_ms=20)
                return True
            except Exception:
                pass
        return False

    def get_hwnd(self) -> Optional[int]:
        """Lấy HWND cửa sổ Unity của tiến trình game qua PID."""
        if sys.platform != "win32" or not self.pid:
            return None
        user32 = ctypes.windll.user32
        cached = getattr(self, "_cached_hwnd", None)
        if cached:
            try:
                if user32.IsWindow(cached):
                    lp_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(cached, ctypes.byref(lp_pid))
                    if lp_pid.value == self.pid:
                        return cached
            except Exception:
                pass

        # 1. Thử qua WindowHelper đã chuẩn hóa cho MEGAMU
        try:
            from meg_navigator import WindowHelper
            win = WindowHelper.find_window_for_pid(self.pid)
            if win and win[0]:
                self._cached_hwnd = win[0]
                return win[0]
        except Exception:
            pass

        # 2. Fallback duyệt trực tiếp Desktop Windows (bọc try-except tuyệt đối chống văng callback)
        candidates = []

        def enum_cb(hwnd, lparam):
            try:
                if not hwnd:
                    return True
                lp_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lp_pid))
                if lp_pid.value == self.pid:
                    class_name = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_name, 256)
                    is_unity = (class_name.value.lower() == "unitywndclass")
                    rect = wintypes.RECT()
                    w, h = 0, 0
                    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                    score = (10000000 if is_unity else 0) + (w * h)
                    candidates.append((score, hwnd))
            except Exception:
                pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        cb = WNDENUMPROC(enum_cb)

        try:
            h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
            if h_desk:
                user32.EnumDesktopWindows(h_desk, cb, 0)
                user32.CloseDesktop(h_desk)
        except Exception:
            pass

        if not candidates:
            try:
                user32.EnumWindows(cb, 0)
            except Exception:
                pass

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            self._cached_hwnd = candidates[0][1]
            return candidates[0][1]
        return None

    @staticmethod
    def send_background_click(hwnd: int, client_x: int, client_y: int, duration_ms: int = 50) -> bool:
        """Gửi click chuột nền vào cửa sổ Unity bằng Win32 PostMessage (không cướp chuột vật lý)."""
        if not hwnd or sys.platform != "win32":
            return False
        user32 = ctypes.windll.user32
        WM_ACTIVATE = 0x0006
        WM_SETFOCUS = 0x0007
        WM_MOUSEMOVE = 0x0200
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WA_ACTIVE = 1
        lparam = ((int(client_y) & 0xFFFF) << 16) | (int(client_x) & 0xFFFF)
        try:
            # Gửi PostMessage ngầm thuần túy, tuyệt đối không gửi WM_ACTIVATE hay cướp focus
            user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lparam)
            time.sleep(max(duration_ms, 30) / 1000.0)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
            return True
        except Exception:
            return False

    @staticmethod
    def send_background_key(hwnd: int, vk_code: int, duration_s: float = 0.05) -> bool:
        """Gửi phím nền chuẩn Unity lParam scan-code vào cửa sổ game (Zero-Focus, không chiếm phím OS)."""
        if not hwnd or sys.platform != "win32":
            return False
        user32 = ctypes.windll.user32
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        lparam_down = 1 | (scan_code << 16) | (1 << 24)
        lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)
        try:
            user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, lparam_down)
            if duration_s > 0:
                time.sleep(duration_s)
            user32.PostMessageW(hwnd, WM_KEYUP, vk_code, lparam_up)
            return True
        except Exception:
            return False

    @staticmethod
    def send_hardware_key(hwnd: int, vk_code: int, duration_s: float = 0.04) -> bool:
        """
        Gửi phím ngầm an toàn qua send_background_key.
        TUYỆT ĐỐI KHÔNG dùng SetForegroundWindow hay keybd_event để chống cướp tiêu điểm và không ảnh hưởng process khác.
        """
        return MegDirectEngine.send_background_key(hwnd, vk_code, duration_s)

    def send_chat(self, command: str) -> bool:
        """
        Gửi lệnh chat (chuyển map /move hoặc lệnh trong game):
        1. Gọi Frida Native Hook (chuẩn 100% như MEGAMU Dashboard gốc: nhanh, không phụ thuộc focus cửa sổ).
        2. Nếu Native Hook chưa sẵn sàng hoặc thất bại, fallback sang PostMessage nền.
        """
        cmd = str(command).strip()
        if not cmd:
            return False

        # 1. Gọi Frida Native Hook (chuẩn theo cơ chế MEGAMUCore của dashboard gốc)
        if self.is_ready:
            try:
                native_ok = self._call("send_chat_native", cmd)
                if native_ok:
                    _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat native: '{cmd}'")
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi gọi send_chat_native: {e}")

        # 2. Gửi lệnh chat an toàn qua BackgroundInputSimulator hoặc PostMessage
        hwnd = self.get_hwnd()
        if not hwnd:
            _safe_log(f"[MegDirectEngine] PID {self.pid}: Không tìm thấy HWND cửa sổ game để gửi lệnh chat fallback.")
            return False

        try:
            from meg_navigator import BackgroundInputSimulator
            ok = BackgroundInputSimulator.send_chat_command(hwnd, cmd)
            if ok:
                _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat qua BackgroundInputSimulator: '{cmd}' vào HWND 0x{hwnd:X}.")
                return True
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi BackgroundInputSimulator.send_chat_command: {e}")

        # Fallback PostMessage thuần
        user32 = ctypes.windll.user32
        WM_CHAR = 0x0102
        VK_RETURN = 0x0D
        try:
            self.send_background_key(hwnd, VK_RETURN, 0.04)
            time.sleep(0.08)
            for ch in cmd:
                scan_code = user32.MapVirtualKeyW(ord(ch), 0)
                lparam = 1 | (scan_code << 16)
                user32.PostMessageW(hwnd, WM_CHAR, ord(ch), lparam)
                time.sleep(0.01)
            time.sleep(0.08)
            self.send_background_key(hwnd, VK_RETURN, 0.04)
            _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat PostMessage fallback: '{cmd}' vào HWND 0x{hwnd:X}.")
            return True
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi PostMessage chat fallback: {e}")
            return False

    def is_helper_active(self, force_refresh: bool = False) -> bool:
        """Kiểm tra trạng thái MuHelper đang BẬT hay TẮT."""
        if not force_refresh:
            info = self.get_player_info(max_age=0.35)
            if info and "helperState" in info:
                try:
                    return int(info.get("helperState", 0)) == 1
                except Exception:
                    pass
        res = self._call("getHelperState")
        if res is not None:
            try:
                return int(res) == 1
            except Exception:
                pass
        if self.last_fast_state and "helperState" in self.last_fast_state:
            try:
                return int(self.last_fast_state.get("helperState", 0)) == 1
            except Exception:
                pass
        return False

    def start_helper(self) -> bool:
        """Kích hoạt bật MuHelper (Ưu tiên Native Memory Hook, tuyệt đối chạy ngầm và không ảnh hưởng process khác)."""
        self.last_fast_state = None
        if self.is_helper_active(force_refresh=True):
            return True

        # Kênh 1: Frida Native Hook (trực tiếp bộ nhớ của đúng game PID này, Zero-Focus)
        if self.is_ready:
            self._call("startHelper")
            for _ in range(6):
                time.sleep(0.06)
                if self.is_helper_active(force_refresh=True):
                    return True

        hwnd = self.get_hwnd()
        if hwnd and sys.platform == "win32":
            # Kênh 2: Gửi phím Home ngầm Win32 PostMessage trực tiếp vào HWND game (Zero-Focus)
            self.send_background_key(hwnd, 0x24, 0.05)
            for _ in range(5):
                time.sleep(0.06)
                if self.is_helper_active(force_refresh=True):
                    return True

            # Kênh 3: Gửi phím Z ngầm Win32 PostMessage trực tiếp vào HWND game (Zero-Focus)
            self.send_background_key(hwnd, 0x5A, 0.05)
            for _ in range(4):
                time.sleep(0.06)
                if self.is_helper_active(force_refresh=True):
                    return True

            # Kênh 4: Click nút Play trên HUD bằng PostMessage ngầm (Zero-Focus)
            self.send_background_click(hwnd, 341, 88, duration_ms=40)
            for _ in range(4):
                time.sleep(0.06)
                if self.is_helper_active(force_refresh=True):
                    return True

        # Kênh 5: Thử lại Frida Native Hook
        if self.is_ready:
            self._call("startHelper")
            time.sleep(0.12)
            return self.is_helper_active(force_refresh=True)

        return False

    def stop_helper(self) -> bool:
        """Kích hoạt tắt MuHelper (Ưu tiên Native Memory Hook, tuyệt đối chạy ngầm và không ảnh hưởng process khác)."""
        self.last_fast_state = None
        # NẾU ĐÃ TẮT RỒI -> TUYỆT ĐỐI KHÔNG GỬI GÌ CẢ (chống vô tình bật lên)
        if not self.is_helper_active(force_refresh=True):
            return True

        # Kênh 1: Frida Native Hook (trực tiếp bộ nhớ của đúng game PID này, Zero-Focus)
        if self.is_ready:
            self._call("stopHelper")
            for _ in range(6):
                time.sleep(0.06)
                if not self.is_helper_active(force_refresh=True):
                    return True

        hwnd = self.get_hwnd()
        if hwnd and sys.platform == "win32":
            # Kênh 2: Phím Home ngầm Win32 PostMessage trực tiếp vào HWND game (Zero-Focus)
            self.send_background_key(hwnd, 0x24, 0.05)
            for _ in range(5):
                time.sleep(0.06)
                if not self.is_helper_active(force_refresh=True):
                    return True

            # Kênh 3: Click nút Play/Stop trên thanh HUD (341, 88) bằng PostMessage ngầm
            self.send_background_click(hwnd, 341, 88, duration_ms=40)
            for _ in range(4):
                time.sleep(0.06)
                if not self.is_helper_active(force_refresh=True):
                    return True

        if self.is_ready:
            self._call("stopHelper")
            time.sleep(0.12)
            return not self.is_helper_active(force_refresh=True)

        return False

    def roll_moss(self, category_id: int) -> bool:
        """Gửi gói tin quay đồ Moss Merchant cho Category ID (Zero-Focus, Native Memory)."""
        if self.is_ready:
            try:
                res = self._call("rollMoss", int(category_id))
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi roll_moss: {e}")
        return False

    def open_moss(self, category_id: int = 0) -> bool:
        """Gửi gói tin yêu cầu mở giao diện Moss Merchant với Category ID (mặc định 0)."""
        if self.is_ready:
            try:
                res = self._call("openMoss", int(category_id))
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi open_moss: {e}")
        return False

    def enter_mirror(self) -> bool:
        """Gửi lệnh native vào cửa sự kiện Double Goer (Mirror of Dimensions)."""
        if self.is_ready:
            try:
                res = self._call("enterMirror")
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi enter_mirror: {e}")
        return False

    def click_mirror_npc(self, npc_ptr: int = 0) -> bool:
        """Kích hoạt đối thoại NPC Lugard sự kiện Double Goer."""
        if self.is_ready:
            try:
                res = self._call("clickMirrorNpc", int(npc_ptr))
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi click_mirror_npc: {e}")
        return False

    def is_mirror_event_map(self) -> bool:
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Double Goer hay không."""
        if self.is_ready:
            try:
                return bool(self._call("isMirrorEventMap"))
            except Exception:
                pass
        return False

    def get_inventory_summary(self) -> Dict[str, Any]:
        """Lấy thông tin tổng quan hòm đồ chính (số ô trống, số đồ rác, đồ giữ lại)."""
        if self.is_ready:
            try:
                res_str = self._call("getInventorySummary")
                if res_str:
                    return json.loads(res_str)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi get_inventory_summary: {e}")
        return {"error": "not_ready", "free": 64, "junkCount": 0}

    def clean_inventory_junk(self, method: str = "both") -> Dict[str, Any]:
        """Tự động bán / dọn toàn bộ vật phẩm rác trong Main Inventory (bảo toàn đồ Exc/Socket/Set/Ngọc/Đồ cộng)."""
        if self.is_ready:
            try:
                res_str = self._call("cleanInventoryJunk", str(method))
                if res_str:
                    return json.loads(res_str)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi clean_inventory_junk: {e}")
        return {"cleaned": 0, "error": "not_ready"}

    def sell_inventory_slot(self, slot: int) -> bool:
        """Gửi lệnh bán 1 slot cụ thể trong Main Inventory vào Merchant."""
        if self.is_ready:
            try:
                return bool(self._call("sellInventorySlot", int(slot)))
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi sell_inventory_slot: {e}")
        return False

    def detach(self):
        """
        Ngắt kết nối an toàn 3 pha tuyệt đối chống crash ntdll/frida-agent.dll_unloaded:
        1. Gọi exports.cleanup() gỡ Interceptor hook và flush
        2. Chờ 50ms cho các hook thread thoát hẳn
        3. Dỡ bỏ script và phiên attach
        """
        self.is_ready = False
        with self._rpc_lock:
            try:
                if self.script:
                    try:
                        self.script.exports_sync.cleanup()
                    except Exception:
                        pass
                    time.sleep(0.12)
                    try:
                        self.script.unload()
                    except Exception:
                        pass
                time.sleep(0.04)
                if self.session:
                    try:
                        self.session.detach()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self.script = None
                self.session = None
                self._release_mutex()

    def __del__(self):
        try:
            self.detach()
        except Exception:
            pass


atexit.register(MegDirectEngine.cleanup_all)

