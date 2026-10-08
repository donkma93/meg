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

try:
    from meg_crash_tracer import trace_gc_protection, trace_frida_event, trace_process_exit, log_crash_trace
except ImportError:
    def trace_gc_protection(*args, **kwargs): pass
    def trace_frida_event(*args, **kwargs): pass
    def trace_process_exit(*args, **kwargs): pass
    def log_crash_trace(*args, **kwargs): pass

def _safe_log(msg: str):
    try:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc), flush=True)
    except Exception:
        pass
    try:
        log_crash_trace("DIRECT_ENGINE", "INFO", msg)
    except Exception:
        pass

DEFAULT_OFFSETS = {
    "game_module": "GameAssembly.dll",
    "get_player": "0x10A8080",
    "get_game_ui": "0x10A80F0",
    "ui_chat_frame": "0x50",
    "move_to": "0xBBA6C0",
    "start_auto_move": "0xBCB280",
    "stop_auto_move": "0xBCB300",
    "chat_send": "0x13408D0",
    "chat_send_cmd": "0xF7CCF0",
    "chat_frame_send": "0x13408D0",
    "static_chat_send": "0xF735B0",
    "command_mgr_process": "0xF7CCF0",
    "chat_update": "0x1323D00",
    "game_ui_update": "0x139FEC0",
    "helper_start": "0x26BB0C0",
    "helper_stop": "0x26BB270",
    "helper_toggle": "0x24F1F10",
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
    "get_world": "0x10ABBE0",
    "game_type_info": "0x549B980",
    "game_world": "0x200",
    "world_scene_index": "0x20",
    "moss_roll": "0x26D1580",
    "moss_open": "0x25117F0",
    "ui_moss_window": "0x1C8",
    "window_show": "0x25117F0",
    "window_set_state": "0x25115F0",
    "moss_roll_handler": "0x26D1180",
    "moss_init": "0x26D13C0",
    "moss_select_cat": "0x26CFD60",
    "game_object_set_active": "0x4530F50",
    "mirror_enter": "0xFF08D0",
    "mirror_npc_click": "0xFED810",
    "mirror_is_event_map": "0xFEFA00",
    "mirror_teleport_event": "0xFF5AF0",
    "inv_sell_item": "0x14B8B30",
    "inv_trash_item": "0x122B8E0",
    "player_inventory": "0x1B8",
    "inventory_items": "0x28",
    "get_auto_login": "0x10A9500",
    "set_auto_login": "0xF4B220",
    "npc_talk": "0x10B2B40",
    "viewport": "0x110",
}

FRIDA_AGENT_JS = r"""
try {
    var k32 = Process.getModuleByName('kernel32.dll');
    var loadLibW = new NativeFunction(k32.getExportByName('LoadLibraryW'), 'pointer', ['pointer']);
    var fridaMod = Process.findModuleByName('frida-agent.dll');
    if (fridaMod) {
        loadLibW(Memory.allocUtf16String(fridaMod.path));
    }
} catch (ePin) {}

var ga = Process.getModuleByName('GameAssembly.dll');
var baseAddr = ga.base;

function off(v) { return ptr(v); }

var getPlayerNative = null;
try {
    var gpOffset = off('__GET_PLAYER__');
    if (!gpOffset.isNull()) {
        getPlayerNative = new NativeFunction(baseAddr.add(gpOffset), 'pointer', []);
    }
} catch (eNative) {}

var getWorldNative = null;
try {
    var gwOffset = off('__GET_WORLD__');
    if (!gwOffset.isNull()) {
        getWorldNative = new NativeFunction(baseAddr.add(gwOffset), 'pointer', []);
    }
} catch (eNativeWorld) {}

function getPlayerPtr() {
    // 1. Thử hàm native get_player (GMMGPDHOEBA - static LocalCharacterBody GMMGPDHOEBA())
    try {
        if (getPlayerNative !== null) {
            var p = getPlayerNative();
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
var nativeHelperToggle = null;
try {
    var htOff = off('__HELPER_TOGGLE__');
    if (!htOff.isNull()) {
        nativeHelperToggle = new NativeFunction(baseAddr.add(htOff), 'void', []);
    }
} catch (eHT) {}
var nativeStartAutoMove = new NativeFunction(baseAddr.add(off('__START_AUTO_MOVE__')), 'void', ['pointer', 'pointer', 'int', 'bool', 'pointer']);
var nativeStopAutoMove = new NativeFunction(baseAddr.add(off('__STOP_AUTO_MOVE__')), 'void', ['pointer', 'bool', 'pointer']);
var nativeChatFrameSend = null;
try {
    var cfsOff = off('__CHAT_FRAME_SEND__');
    if (!cfsOff.isNull()) {
        nativeChatFrameSend = new NativeFunction(baseAddr.add(cfsOff), 'void', ['pointer', 'pointer', 'bool', 'pointer']);
    }
} catch (eCFS) {}

var sendChatMessageNative = null;
try {
    var csOff = off('__CHAT_SEND__');
    if (!csOff.isNull()) {
        sendChatMessageNative = new NativeFunction(baseAddr.add(csOff), 'void', ['pointer', 'pointer', 'bool', 'pointer']);
    }
} catch (eCS) {}

var nativeStaticChatSend = null;
try {
    var scsOff = off('__STATIC_CHAT_SEND__');
    if (!scsOff.isNull()) {
        nativeStaticChatSend = new NativeFunction(baseAddr.add(scsOff), 'void', ['pointer', 'pointer']);
    }
} catch (eSCS) {}

var nativeCommandManagerProcess = null;
try {
    var cmdOff = off('__COMMAND_MGR_PROCESS__');
    if (!cmdOff.isNull()) {
        nativeCommandManagerProcess = new NativeFunction(baseAddr.add(cmdOff), 'bool', ['pointer', 'pointer']);
    }
} catch (eCmd) {}

var nativeMossRoll = null;
try {
    var mrOff = off('__MOSS_ROLL__');
    if (!mrOff.isNull()) {
        nativeMossRoll = new NativeFunction(baseAddr.add(mrOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMossRoll) {}

var nativeMossOpen = null;
try {
    var moOff = off('__MOSS_OPEN__');
    if (!moOff.isNull()) {
        nativeMossOpen = new NativeFunction(baseAddr.add(moOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMossOpen) {}

var nativeWindowShow = null;
try {
    var wsOff = off('__WINDOW_SHOW__');
    if (!wsOff.isNull()) {
        nativeWindowShow = new NativeFunction(baseAddr.add(wsOff), 'void', ['pointer', 'pointer']);
    }
} catch (eWS) {}

var nativeWindowSetState = null;
try {
    var wssOff = off('__WINDOW_SET_STATE__');
    if (!wssOff.isNull()) {
        nativeWindowSetState = new NativeFunction(baseAddr.add(wssOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eWSS) {}

var nativeMossRollHandler = null;
try {
    var mrhOff = off('__MOSS_ROLL_HANDLER__');
    if (!mrhOff.isNull()) {
        nativeMossRollHandler = new NativeFunction(baseAddr.add(mrhOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMRH) {}

var nativeMossInit = null;
try {
    var miOff = off('__MOSS_INIT__');
    if (!miOff.isNull()) {
        nativeMossInit = new NativeFunction(baseAddr.add(miOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMossInit) {}

var nativeMossSelectCat = null;
try {
    var mscOff = off('__MOSS_SELECT_CAT__');
    if (!mscOff.isNull()) {
        nativeMossSelectCat = new NativeFunction(baseAddr.add(mscOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eMossSC) {}

var nativeGameObjectSetActive = null;
try {
    var gosaOff = off('__GAME_OBJECT_SET_ACTIVE__');
    if (!gosaOff.isNull()) {
        nativeGameObjectSetActive = new NativeFunction(baseAddr.add(gosaOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eGOSA) {}

var nativeMirrorEnter = null;
try {
    var meOff = off('__MIRROR_ENTER__');
    if (!meOff.isNull()) {
        nativeMirrorEnter = new NativeFunction(baseAddr.add(meOff), 'void', ['int', 'pointer']);
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
        nativeMirrorIsEventMap = new NativeFunction(baseAddr.add(mimOff), 'bool', ['pointer']);
    }
} catch (eMirrorMap) {}

var nativeMirrorTeleportEventMap = null;
try {
    var mtemOff = off('__MIRROR_TELEPORT_EVENT__');
    if (!mtemOff.isNull()) {
        nativeMirrorTeleportEventMap = new NativeFunction(baseAddr.add(mtemOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eMirrorTeleport) {}

var nativeNpcTalk = null;
try {
    var ntOff = off('__NPC_TALK__');
    if (!ntOff.isNull()) {
        nativeNpcTalk = new NativeFunction(baseAddr.add(ntOff), 'void', ['pointer', 'pointer']);
    }
} catch (eNT) {}

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

var nativeGetAutoLogin = null;
try {
    var galOff = off('__GET_AUTO_LOGIN__');
    if (!galOff.isNull()) {
        nativeGetAutoLogin = new NativeFunction(baseAddr.add(galOff), 'pointer', []);
    }
} catch (eGAL) {}

var nativeSetAutoLogin = null;
try {
    var salOff = off('__SET_AUTO_LOGIN__');
    if (!salOff.isNull()) {
        nativeSetAutoLogin = new NativeFunction(baseAddr.add(salOff), 'void', ['pointer', 'int', 'pointer', 'pointer']);
    }
} catch (eSAL) {}

var nativeGetGS = null;
try {
    nativeGetGS = new NativeFunction(baseAddr.add(off('0x1094370')), 'pointer', ['pointer']);
} catch (eGS) {}

var nativeGSSend = null;
try {
    nativeGSSend = new NativeFunction(baseAddr.add(off('0x11EFCD0')), 'void', ['pointer', 'pointer', 'bool', 'bool', 'pointer']);
} catch (eGSSend) {}

var mono_domain_get_corlib = null;
var il2cpp_class_from_name = null;
var il2cpp_array_new = null;
try {
    var expCorlib = ga.findExportByName('mono_domain_get_corlib');
    var expClassFromName = ga.findExportByName('il2cpp_class_from_name');
    var expArrayNew = ga.findExportByName('il2cpp_array_new');
    if (expCorlib) mono_domain_get_corlib = new NativeFunction(expCorlib, 'pointer', []);
    if (expClassFromName) il2cpp_class_from_name = new NativeFunction(expClassFromName, 'pointer', ['pointer', 'pointer', 'pointer']);
    if (expArrayNew) il2cpp_array_new = new NativeFunction(expArrayNew, 'pointer', ['pointer', 'size_t']);
} catch (eIL2CPP) {}

function sendDropPacket(slot, targetX, targetY) {
    try {
        if (nativeGetGS === null || nativeGSSend === null || mono_domain_get_corlib === null || il2cpp_class_from_name === null || il2cpp_array_new === null) {
            return false;
        }
        var gs = nativeGetGS(ptr(0));
        if (gs.isNull()) return false;
        var corlib = mono_domain_get_corlib();
        if (corlib.isNull()) return false;
        var byteClass = il2cpp_class_from_name(corlib, Memory.allocUtf8String("System"), Memory.allocUtf8String("Byte"));
        if (byteClass.isNull()) return false;
        var arr = il2cpp_array_new(byteClass, 6);
        if (arr.isNull()) return false;
        var raw = arr.add(0x20);
        raw.writeU8(0xC1);
        raw.add(1).writeU8(0x06);
        raw.add(2).writeU8(0x23);
        raw.add(3).writeU8(targetX & 0xFF);
        raw.add(4).writeU8(targetY & 0xFF);
        raw.add(5).writeU8(slot & 0xFF);
        nativeGSSend(gs, arr, 0, 0, ptr(0));
        return true;
    } catch (eDropPkt) {
        return false;
    }
}

var nativeGetConfig = null;
try {
    nativeGetConfig = new NativeFunction(baseAddr.add(off('0x1094130')), 'pointer', ['pointer']);
} catch (eCfg) {}

function ensureDropAllowed() {
    try {
        if (nativeGetConfig !== null) {
            var cfg = nativeGetConfig(ptr(0));
            if (!cfg.isNull()) {
                var clientInfo = cfg.add(0x20).readPointer();
                if (!clientInfo.isNull()) {
                    clientInfo.add(0xE1).writeU8(1);
                    return true;
                }
            }
        }
    } catch (e1) {}
    try {
        var tiOffset = off('__GAME_TYPE_INFO__');
        if (!tiOffset.isNull()) {
            var typeInfo = baseAddr.add(tiOffset).readPointer();
            if (!typeInfo.isNull()) {
                var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                if (!staticFields.isNull()) {
                    var gameInst = staticFields.add(ptr('0x08')).readPointer();
                    if (!gameInst.isNull()) {
                        var cfgObj = gameInst.add(ptr('0xB0')).readPointer();
                        if (!cfgObj.isNull()) {
                            var ci = cfgObj.add(ptr('0x20')).readPointer();
                            if (!ci.isNull()) {
                                ci.add(0xE1).writeU8(1);
                                return true;
                            }
                        }
                    }
                }
            }
        }
    } catch (e2) {}
    return false;
}

var nativeGetGameUI = null;
try {
    var guiOff = off('__GET_GAME_UI__');
    if (!guiOff.isNull()) {
        nativeGetGameUI = new NativeFunction(baseAddr.add(guiOff), 'pointer', []);
    }
} catch (eGUI) {}

var cfInstance = null;
var pendingCommand = null;
var chatHook = null;
var guiHook = null;

function getChatFrameInstance() {
    if (cfInstance !== null && !cfInstance.isNull()) return cfInstance;
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var cf = gui.add(off('__UI_CHAT_FRAME__')).readPointer();
                if (!cf.isNull()) {
                    cfInstance = cf;
                    return cf;
                }
            }
        }
    } catch (eCF) {}
    return ptr(0);
}

function dispatchChatMessage(cmdText) {
    if (!cmdText) return false;
    var str = il2cpp_string_new(Memory.allocUtf8String(cmdText));
    if (str.isNull()) return false;
    var ok = false;

    // 1. Gửi qua ChatFrame instance (HGBCPFJLABE 0x13408D0 / 0x19B8690)
    try {
        var cf = getChatFrameInstance();
        if (!cf.isNull()) {
            if (nativeChatFrameSend !== null) {
                try {
                    nativeChatFrameSend(cf, str, 1, ptr(0));
                    ok = true;
                } catch (e1) {}
            }
            if (!ok && sendChatMessageNative !== null) {
                try {
                    sendChatMessageNative(cf, str, 1, ptr(0));
                    ok = true;
                } catch (e2) {}
            }
        }
    } catch (eCFSend) {}

    // 2. Gửi trực tiếp qua static Mega.Chat.EAMEMDAKDKK (0xF735B0) nếu cfInstance chưa sẵn sàng
    if (!ok && nativeStaticChatSend !== null) {
        try {
            nativeStaticChatSend(str, ptr(0));
            ok = true;
        } catch (eStatic) {}
    }

    // 3. Kích hoạt qua CommandManager.PPKNABFPPIA (0xF7CCF0) nếu là lệnh console '/'
    if (cmdText.charAt(0) === '/' && nativeCommandManagerProcess !== null) {
        try {
            var res = nativeCommandManagerProcess(str, ptr(0));
            if (res) ok = true;
        } catch (eCmd) {}
    }

    return ok;
}

var pendingHelperAction = null;
var pendingHelperTargetX = 0;
var pendingHelperTargetY = 0;

function dispatchHelperAction(act, targetX, targetY) {
    if (!act) return false;
    try {
        var p = getPlayerPtr();
        if (p.isNull()) return false;
        var h = p.add(off('__PLAYER_HELPER__')).readPointer();
        if (h.isNull()) return false;

        if (act === 'start') {
            nativeStartHelper(h, ptr(0));
            h.add(off('__HELPER_STATE__')).writeU8(1);

            // Ghim chặt tọa độ gốc của MuHelper (CBJJBLONOFF tại +0x50) về đúng tọa độ đích (targetX, targetY)
            var tx = parseInt(targetX || 0);
            var ty = parseInt(targetY || 0);
            if (tx > 0 && ty > 0) {
                try {
                    var coordObj = h.add(0x50).readPointer();
                    if (!coordObj.isNull()) {
                        coordObj.add(0x10).writeS32(tx);
                        coordObj.add(0x14).writeS32(ty);
                    }
                } catch (eCoord) {}
            }
            return true;
        } else if (act === 'stop') {
            nativeStopHelper(h, ptr(0));
            h.add(off('__HELPER_STATE__')).writeU8(0);
            return true;
        }
    } catch (eH) {}
    return false;
}

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
                        dispatchChatMessage(cmd);
                    }
                    if (pendingHelperAction !== null) {
                        var hAct = pendingHelperAction;
                        var hTx = pendingHelperTargetX;
                        var hTy = pendingHelperTargetY;
                        pendingHelperAction = null;
                        pendingHelperTargetX = 0;
                        pendingHelperTargetY = 0;
                        dispatchHelperAction(hAct, hTx, hTy);
                    }
                } catch (eEnter) {}
            }
        });
    }
} catch (eHook) {}

var pendingMossOpenCategory = null;

function setupMossWindow(mossWin, cat) {
    if (!mossWin || mossWin.isNull()) return false;
    try {
        var catId = parseInt(cat || 0);

        // 1. Cập nhật Category ID (offset 0x78)
        mossWin.add(0x78).writeS32(catId);

        // 2. Khởi tạo dữ liệu giao diện qua MMossMerchantWindow.CLCAABGMDPA (RVA 0x26D13C0)
        // Hàm gốc sẽ nạp danh mục, bật RollButton.interactable = true, và tắt LoadingImage
        if (nativeMossInit !== null) {
            try {
                nativeMossInit(mossWin, ptr(0));
            } catch (eInit) {}
        }

        // 3. Chọn đúng tab Category theo chỉ định
        if (nativeMossSelectCat !== null) {
            try {
                var catList = mossWin.add(0x80).readPointer();
                if (!catList.isNull()) {
                    var count = catList.add(0x18).readS32();
                    var items = catList.add(0x10).readPointer();
                    if (!items.isNull() && catId < count && catId >= 0) {
                        var catObj = items.add(0x20 + catId * 8).readPointer();
                        if (!catObj.isNull()) {
                            nativeMossSelectCat(mossWin, catObj, ptr(0));
                        }
                    }
                }
            } catch (eCat) {}
        }

        // 4. ÉP BUỘC TẮT LoadingImage (offset 0x60) để KHÔNG BAO GIỜ bị kẹt xoay vòng loading
        try {
            var loadingImg = mossWin.add(0x60).readPointer();
            if (!loadingImg.isNull() && nativeGameObjectSetActive !== null) {
                nativeGameObjectSetActive(loadingImg, 0, ptr(0));
            }
        } catch (eLoad) {}

        // 5. Reset timer quay 0x98 về 0 để sẵn sàng nhận lệnh quay mới
        mossWin.add(0x98).writeFloat(0.0);

        // 6. Hiển thị cửa sổ (MWindow tại offset 0x20)
        var win = mossWin.add(0x20).readPointer();
        if (!win.isNull()) {
            if (nativeWindowShow !== null) {
                nativeWindowShow(win, ptr(0));
            } else if (nativeWindowSetState !== null) {
                nativeWindowSetState(win, 1, ptr(0));
            }
            win.add(0x48).writeU8(1);
        }
        return true;
    } catch (eSetup) {
        return false;
    }
}

function findMossNpc() {
    try {
        var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
        if (typeInfo.isNull()) return null;
        var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
        if (staticFields.isNull()) return null;
        var gameInstance = staticFields.add(ptr('0x8')).readPointer();
        if (gameInstance.isNull()) return null;
        var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
        if (viewport.isNull()) return null;
        var objDict = viewport.add(ptr('0x20')).readPointer();
        if (objDict.isNull()) return null;

        var entries = objDict.add(ptr('0x18')).readPointer();
        if (entries.isNull()) return null;
        var count = objDict.add(ptr('0x20')).readS32();
        if (count <= 0 || count > 500) return null;

        for (var i = 0; i < count; i++) {
            var entryAddr = entries.add(0x20 + i * 24);
            var val = entryAddr.add(16).readPointer();
            if (val.isNull()) continue;
            var body = val.add(ptr('0x18')).readPointer();
            if (body.isNull()) continue;

            var bIdx = body.add(0x20).readS32();
            if (bIdx < 0) continue;

            var name = "";
            try {
                var namePtr = body.add(off('__PLAYER_NAME__')).readPointer();
                if (!namePtr.isNull()) {
                    var len = namePtr.add(0x10).readS32();
                    if (len > 0 && len < 64) {
                        name = namePtr.add(0x14).readUtf16String(len);
                    }
                }
            } catch (eN) {}

            var tx = -1, ty = -1;
            try {
                var cPtr = body.add(off('__PLAYER_COORD__')).readPointer();
                if (!cPtr.isNull()) {
                    tx = cPtr.add(0x10).readS32();
                    ty = cPtr.add(0x14).readS32();
                }
            } catch (eC) {}

            var isMoss = false;
            if (name && name.toLowerCase().indexOf('moss') !== -1) {
                isMoss = true;
            } else if (tx >= 18 && tx <= 26 && ty >= 220 && ty <= 230) {
                isMoss = true;
            }

            if (isMoss) {
                return {
                    ptr: body,
                    index: bIdx,
                    name: name || "Moss The Gambler",
                    x: tx,
                    y: ty
                };
            }
        }
    } catch (eFind) {}
    return null;
}

try {
    var guiUpdateOff = off('__GAME_UI_UPDATE__');
    if (!guiUpdateOff.isNull()) {
        guiHook = Interceptor.attach(baseAddr.add(guiUpdateOff), {
            onEnter: function(args) {
                if (shuttingDown) return;
                try {
                    var gui = args[0];
                    if (gui && !gui.isNull()) {
                        var cf = gui.add(off('__UI_CHAT_FRAME__')).readPointer();
                        if (cf && !cf.isNull()) cfInstance = cf;

                        if (pendingMossOpenCategory !== null) {
                            try {
                                var cat = pendingMossOpenCategory;
                                pendingMossOpenCategory = null;
                                var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                                setupMossWindow(mossWin, cat);
                            } catch (eMossUI) {}
                        }
                    }
                    if (pendingCommand !== null) {
                        var cmd = pendingCommand;
                        pendingCommand = null;
                        dispatchChatMessage(cmd);
                    }
                    if (pendingHelperAction !== null) {
                        var hAct = pendingHelperAction;
                        var hTx = pendingHelperTargetX;
                        var hTy = pendingHelperTargetY;
                        pendingHelperAction = null;
                        pendingHelperTargetX = 0;
                        pendingHelperTargetY = 0;
                        dispatchHelperAction(hAct, hTx, hTy);
                    }
                } catch (eGUIEnter) {}
            }
        });
    }
} catch (eGUIHook) {}

var pDomainGet = ga.findExportByName('il2cpp_domain_get');
var pThreadAttach = ga.findExportByName('il2cpp_thread_attach');
var pObjectNew = ga.findExportByName('il2cpp_object_new');
var il2cpp_domain_get = pDomainGet ? new NativeFunction(pDomainGet, 'pointer', []) : null;
var il2cpp_thread_attach = pThreadAttach ? new NativeFunction(pThreadAttach, 'pointer', ['pointer']) : null;
var il2cpp_object_new = pObjectNew ? new NativeFunction(pObjectNew, 'pointer', ['pointer']) : null;

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

        // Đọc Map ID (SceneIndex) chuẩn xác 100% qua native get_world hoặc static GameInstance
        try {
            if (getWorldNative !== null) {
                var w = getWorldNative();
                if (!w.isNull()) {
                    var sc = w.add(off('__WORLD_SCENE_INDEX__')).readS32();
                    if (sc >= 0 && sc <= 255) mapId = sc;
                }
            }
        } catch (eWorldNative) {}

        if (mapId < 0) {
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
        }

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
        ensureThreadAttached();
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

            var destCoord = ptr(0);
            try {
                var existing = p.add(off('__AUTO_MOVE_DEST__')).readPointer();
                if (!existing.isNull()) destCoord = existing;
            } catch (eD) {}

            if (!destCoord.isNull()) {
                destCoord.add(0x10).writeS32(parseInt(targetX));
                destCoord.add(0x14).writeS32(parseInt(targetY));
                var ok = moveToNative(p, destCoord, 0.0, ptr(0), 0, 1, ptr(0));
                return Boolean(ok);
            }

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
                if (il2cpp_object_new !== null) {
                    try {
                        var managedCoord = il2cpp_object_new(klass);
                        if (!managedCoord.isNull()) {
                            managedCoord.add(0x10).writeS32(parseInt(targetX));
                            managedCoord.add(0x14).writeS32(parseInt(targetY));
                            var okM = moveToNative(p, managedCoord, 0.0, ptr(0), 0, 1, ptr(0));
                            return Boolean(okM);
                        }
                    } catch (eNM) {}
                }
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
                try {
                    var move = p.add(off('__PLAYER_MOVE__')).readPointer();
                    if (!move.isNull()) {
                        move.add(off('__MOVE_FLAG__')).writeU8(0);
                        move.add(ptr('0x30')).writeFloat(0.0);
                    }
                } catch (eM) {}
                try {
                    p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
                    p.add(off('__AUTO_MOVE_TYPE__')).writeS32(-1);
                } catch (eA) {}
                try {
                    nativeStopAutoMove(p, 1, ptr(0));
                } catch (eS) {}
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
            cmd = String(cmd || '').trim();
            if (!cmd) return false;
            pendingCommand = cmd;
            return true;
        } catch (e) {
            return false;
        }
    },

    send_chat_native: function(cmd) {
        return this.sendChatNative(cmd);
    },

    startHelper: function(targetX, targetY) {
        var tx = parseInt(targetX || 0);
        var ty = parseInt(targetY || 0);
        try {
            ensureThreadAttached();
            pendingHelperAction = 'start';
            pendingHelperTargetX = tx;
            pendingHelperTargetY = ty;
            var ok = dispatchHelperAction('start', tx, ty);
            if (ok) {
                pendingHelperAction = null;
                return true;
            }
        } catch (eH) {}
        try {
            if (nativeHelperToggle !== null) {
                var p2 = getPlayerPtr();
                if (!p2.isNull()) {
                    var h2 = p2.add(off('__PLAYER_HELPER__')).readPointer();
                    if (!h2.isNull() && h2.add(off('__HELPER_STATE__')).readU8() === 0) {
                        nativeHelperToggle();
                        if (tx > 0 && ty > 0) {
                            try {
                                var coordObj2 = h2.add(0x50).readPointer();
                                if (!coordObj2.isNull()) {
                                    coordObj2.add(0x10).writeS32(tx);
                                    coordObj2.add(0x14).writeS32(ty);
                                }
                            } catch (eC2) {}
                        }
                        return true;
                    }
                }
            }
        } catch (eHT) {}
        return true;
    },

    stopHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = 'stop';
            pendingHelperTargetX = 0;
            pendingHelperTargetY = 0;
            var ok = dispatchHelperAction('stop', 0, 0);
            if (ok) {
                pendingHelperAction = null;
                return true;
            }
        } catch (eH) {}
        try {
            if (nativeHelperToggle !== null) {
                var p2 = getPlayerPtr();
                if (!p2.isNull()) {
                    var h2 = p2.add(off('__PLAYER_HELPER__')).readPointer();
                    if (!h2.isNull() && h2.add(off('__HELPER_STATE__')).readU8() !== 0) {
                        nativeHelperToggle();
                        return true;
                    }
                }
            }
        } catch (eHT) {}
        return true;
    },

    toggleHelper: function() {
        try {
            ensureThreadAttached();
            if (nativeHelperToggle !== null) {
                nativeHelperToggle();
                return true;
            }
        } catch (eT) {}
        return false;
    },

    startAutoMove: function(x, y, helper) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return false;

            // 1. Tìm Managed Coord object sẵn có trong player instance
            var destCoord = ptr(0);
            try {
                var existing = p.add(off('__AUTO_MOVE_DEST__')).readPointer();
                if (!existing.isNull()) destCoord = existing;
            } catch (eDest) {}

            if (destCoord.isNull()) {
                try {
                    var tCoord = p.add(ptr('0x18')).readPointer();
                    if (!tCoord.isNull()) destCoord = tCoord;
                } catch (eT) {}
            }

            // 2. Tìm vtable / class pointer của Coord
            var klass = ptr(0);
            if (!destCoord.isNull()) {
                try { klass = destCoord.readPointer(); } catch (eK) {}
            }
            if (klass.isNull()) {
                try {
                    var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                    if (!curCoord.isNull()) klass = curCoord.readPointer();
                } catch (e1) {}
            }
            if (klass.isNull()) {
                try {
                    var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                    if (!lastCoord.isNull()) klass = lastCoord.readPointer();
                } catch (e2) {}
            }
            if (!klass.isNull()) {
                cachedCoordKlass = klass;
            } else if (!cachedCoordKlass.isNull()) {
                klass = cachedCoordKlass;
            }

            // 3. Nếu destCoord chưa có, cấp phát đối tượng Managed chuẩn GC heap qua il2cpp_object_new
            if (destCoord.isNull() && il2cpp_object_new !== null && !klass.isNull()) {
                try {
                    destCoord = il2cpp_object_new(klass);
                } catch (eNew) {}
            }

            if (!destCoord.isNull()) {
                destCoord.add(0x10).writeS32(parseInt(x));
                destCoord.add(0x14).writeS32(parseInt(y));

                // Cấu hình cờ Auto Move chuẩn Type 0 để vòng lặp Update của game khởi tạo BodyActivity (0xabb8d0)
                p.add(off('__AUTO_MOVE_DEST__')).writePointer(destCoord);
                p.add(off('__AUTO_MOVE_TYPE__')).writeS32(0);
                p.add(off('__AUTO_MOVE_HELPER__')).writeU8(helper ? 1 : 0);
                p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);

                // Kích hoạt trực tiếp bước di chuyển khởi hành qua moveToNative
                try {
                    moveToNative(p, destCoord, 0.0, ptr(0), 0, 1, ptr(0));
                } catch (eMove) {}

                return true;
            } else {
                // TUYỆT ĐỐI KHÔNG ghi Memory.alloc vào __AUTO_MOVE_DEST__ (0x4A8)!
                // Vì con trỏ ngoài Managed Heap sẽ làm sập Boehm GC 0xC0000005 khi quét dọn rác.
                if (!klass.isNull()) {
                    coordBuf.writePointer(klass);
                    coordBuf.add(0x08).writePointer(ptr(0));
                    coordBuf.add(0x10).writeS32(parseInt(x));
                    coordBuf.add(0x14).writeS32(parseInt(y));
                    try {
                        moveToNative(p, coordBuf, 0.0, ptr(0), 0, 1, ptr(0));
                    } catch (eM2) {}
                    return true;
                }
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
            var cat = parseInt(categoryId || 0);

            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (!gui.isNull()) {
                    var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                    if (!mossWin.isNull()) {
                        // 1. Cập nhật Category ID (offset 0x78)
                        mossWin.add(0x78).writeS32(cat);

                        // 2. Kích hoạt chọn category nếu hàm khả dụng
                        if (nativeMossSelectCat !== null) {
                            try {
                                var catList = mossWin.add(0x80).readPointer();
                                if (!catList.isNull()) {
                                    var count = catList.add(0x18).readS32();
                                    var items = catList.add(0x10).readPointer();
                                    if (!items.isNull() && cat < count && cat >= 0) {
                                        var catObj = items.add(0x20 + cat * 8).readPointer();
                                        if (!catObj.isNull()) {
                                            nativeMossSelectCat(mossWin, catObj, ptr(0));
                                        }
                                    }
                                }
                            } catch (eCat) {}
                        }

                        // 3. Kích hoạt handler bấm nút Roll chuẩn của MEGAMU (NEOMFDBIIHM - RVA 0x26D1180)
                        if (nativeMossRollHandler !== null) {
                            try {
                                nativeMossRollHandler(mossWin, ptr(0));
                            } catch (eRH) {}
                        }

                        // 4. Ép timer AGFHDCHLLIB tại offset 0x98 thành 0.001f (bỏ qua delay 2.0s animation)
                        mossWin.add(0x98).writeFloat(0.001);

                        // 5. Kích hoạt trực tiếp MMossMerchantWindow.Update (RVA 0x26D1580)
                        // Mã máy MEGAMU tại 0x26D16F8-0x26D175B sẽ phát gói tin C1 05 70 10 [cat]
                        // trực tiếp qua GSConnection.SendPacket (0x122AC90)
                        if (nativeMossRoll !== null) {
                            nativeMossRoll(mossWin, ptr(0));
                        }

                        // 6. Ép TẮT LoadingImage để không bị kẹt xoay vòng loading trên giao diện
                        try {
                            var loadingImg = mossWin.add(0x60).readPointer();
                            if (!loadingImg.isNull() && nativeGameObjectSetActive !== null) {
                                nativeGameObjectSetActive(loadingImg, 0, ptr(0));
                            }
                        } catch (eLoad) {}

                        return true;
                    }
                }
            }
            return false;
        } catch (eMR) {
            return false;
        }
    },

    openMoss: function(categoryId) {
        try {
            ensureThreadAttached();
            var cat = parseInt(categoryId || 0);

            // 1. Đặt cờ cho Main Thread Update render an toàn
            pendingMossOpenCategory = cat;

            // 2. Kích hoạt trực tiếp mở UI trên màn hình qua GameUI và thiết lập trạng thái chuẩn
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                        setupMossWindow(mossWin, cat);
                    }
                }
            } catch (eDirectUI) {}

            return true;
        } catch (eMO) {
            return false;
        }
    },

    findMossNpc: function() {
        try {
            ensureThreadAttached();
            var npc = findMossNpc();
            if (!npc) return { found: false };
            return {
                found: true,
                index: npc.index,
                name: npc.name,
                x: npc.x,
                y: npc.y
            };
        } catch (e) {
            return { found: false, error: e.toString() };
        }
    },

    interactMossNpc: function(categoryId) {
        try {
            ensureThreadAttached();
            var cat = parseInt(categoryId || 0);
            var npc = findMossNpc();
            if (!npc) {
                return { success: false, error: "NPC_NOT_FOUND" };
            }

            if (nativeNpcTalk !== null) {
                try {
                    nativeNpcTalk(npc.ptr, ptr(0));
                } catch (eNT) {}
            }

            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                        setupMossWindow(mossWin, cat);
                    }
                }
            } catch (eUI) {}

            return {
                success: true,
                index: npc.index,
                name: npc.name,
                x: npc.x,
                y: npc.y
            };
        } catch (eInteract) {
            return { success: false, error: eInteract.toString() };
        }
    },

    enterMirror: function(slot) {
        try {
            ensureThreadAttached();
            var itemSlot = 0;
            if (slot !== undefined && slot !== null) {
                itemSlot = parseInt(slot);
            } else {
                // Tự động tìm vị trí vé Mirror of Dimensions (itemIndex 7279) trong hòm đồ chính (slot 12 - 75)
                try {
                    var p = getPlayerPtr();
                    if (!p.isNull()) {
                        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                        if (!inv.isNull()) {
                            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                            if (!itemsArr.isNull()) {
                                for (var s = 12; s < 76; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = itemPtr.add(0x10).readS32();
                                        if (idx === 7279) {
                                            itemSlot = s;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                } catch (eScan) {}
            }
            if (nativeMirrorEnter !== null) {
                nativeMirrorEnter(itemSlot, ptr(0));
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
                return Boolean(nativeMirrorIsEventMap(ptr(0)));
            }
        } catch (eMM) {}
        return false;
    },

    teleportToEventMap: function() {
        try {
            ensureThreadAttached();
            if (nativeMirrorTeleportEventMap !== null) {
                nativeMirrorTeleportEventMap(ptr(0), 1, ptr(0));
                return true;
            }
        } catch (eTTEM) {}
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
                junkSlots: junkSlots,
                keptSlots: keptSlots
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

            if (nativeInvTrashItem === null && nativeInvSellItem === null) {
                return JSON.stringify({ cleaned: 0, error: "no_native_fn" });
            }

            var curX = 0;
            var curY = 0;
            try {
                var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                if (!curCoord.isNull()) {
                    var klass = curCoord.readPointer();
                    if (!klass.isNull()) coordBuf.writePointer(klass);
                    coordBuf.add(0x08).writePointer(ptr(0));
                    curX = curCoord.add(0x10).readS32();
                    curY = curCoord.add(0x14).readS32();
                }
            } catch (eXY) {}

            var dropX = curX + 1;
            var dropY = curY;
            coordBuf.add(0x10).writeS32(dropX);
            coordBuf.add(0x14).writeS32(dropY);

            var cleaned = 0;
            var useMethod = (method || "drop").toLowerCase();

            ensureDropAllowed();

            for (var s = 12; s < 76; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = itemPtr.add(0x10).readS32();
                var itemLevel = itemPtr.add(0x14).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var sec = Math.floor(itemIndex / 512);

                // Giữ lại tuyệt đối mọi đồ giá trị: Exc, Ancient, Socket, Đồ đã ép cấp (>0), Ngọc/Vé (sec 12-15)
                if (excOpt > 0 || ancOpt > 0 || sockOpt > 0 || itemLevel > 0 || (sec >= 12 && sec <= 15)) {
                    continue;
                }

                var itemHandled = false;
                try {
                    if (useMethod === "drop" || useMethod === "trash" || useMethod === "both") {
                        if (nativeInvTrashItem !== null) {
                            nativeInvTrashItem(s, coordBuf, ptr(0));
                            itemHandled = true;
                        }
                    }
                    if (!itemHandled && (useMethod === "sell" || useMethod === "both")) {
                        if (nativeInvSellItem !== null) {
                            nativeInvSellItem(s, itemPtr, ptr(0));
                            itemHandled = true;
                        }
                    }
                    if (itemHandled) {
                        cleaned++;
                        try { Thread.sleep(0.06); } catch (eSleep) {}
                    }
                } catch (eAct) {}
            }

            return JSON.stringify({ cleaned: cleaned });
        } catch (e) {
            return JSON.stringify({ cleaned: 0, error: e.toString() });
        }
    },

    dropInventorySlot: function(slot, offX, offY) {
        try {
            ensureThreadAttached();
            var allowed = ensureDropAllowed();
            var s = parseInt(slot);
            var ox = parseInt(offX !== undefined ? offX : 1);
            var oy = parseInt(offY !== undefined ? offY : 0);
            if (nativeInvTrashItem === null) {
                return JSON.stringify({ ok: false, err: "no_drop_native_available" });
            }

            var p = getPlayerPtr();
            var curX = 0;
            var curY = 0;
            try {
                if (!p.isNull()) {
                    var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                    if (!curCoord.isNull()) {
                        var klass = curCoord.readPointer();
                        if (!klass.isNull()) coordBuf.writePointer(klass);
                        coordBuf.add(0x08).writePointer(ptr(0));
                        curX = curCoord.add(0x10).readS32();
                        curY = curCoord.add(0x14).readS32();
                    }
                }
            } catch (ePXY) {}

            var dropX = curX + ox;
            var dropY = curY + oy;

            coordBuf.add(0x10).writeS32(dropX);
            coordBuf.add(0x14).writeS32(dropY);

            nativeInvTrashItem(s, coordBuf, ptr(0));

            return JSON.stringify({ ok: true, allowed: allowed, slot: s, x: dropX, y: dropY });
        } catch (e) {
            return JSON.stringify({ ok: false, err: e.toString() });
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
                ensureDropAllowed();
                nativeInvTrashItem(s, ptr(0), ptr(0));
                return true;
            }
        } catch (e) {}
        return false;
    },

    autoLogin: function(server, account, character) {
        try {
            ensureThreadAttached();
            var autoLogin = null;
            if (nativeGetAutoLogin !== null) {
                try { autoLogin = nativeGetAutoLogin(); } catch (eG) {}
            }
            if (autoLogin === null || autoLogin.isNull()) {
                return JSON.stringify({ ok: false, err: "auto_login_null" });
            }

            var s = parseInt(server || 1);
            var acc = account ? String(account) : "";
            var chr = character ? String(character) : "";

            var accStr = il2cpp_string_new(Memory.allocUtf8String(acc));
            var chrStr = il2cpp_string_new(Memory.allocUtf8String(chr));

            if (nativeSetAutoLogin !== null) {
                try {
                    nativeSetAutoLogin(autoLogin, s, accStr, chrStr);
                } catch (eSet) {}
            }

            // Ghi đè trực tiếp các cờ để đảm bảo client kích hoạt luồng AutoLogin
            try {
                autoLogin.add(0x20).writeU8(0); // IsServerSelectionDisabled = 0
                autoLogin.add(0x21).writeU8(0); // IsAccountSelectionDisabled = 0
                autoLogin.add(0x22).writeU8(0); // IsCharacterSelectionDisabled = 0
                autoLogin.add(0x23).writeU8(0); // QuickSwitchBackToPrevious = 0
                autoLogin.add(0x24).writeS32(s); // QuickSwitchServerValue
                autoLogin.add(0x28).writePointer(accStr); // QuickSwitchAccountValue
                autoLogin.add(0x30).writePointer(chrStr); // QuickSwitchCharacterValue
            } catch (eWrite) {}

            return JSON.stringify({ ok: true, server: s, account: acc, character: chr });
        } catch (e) {
            return JSON.stringify({ ok: false, err: e.toString() });
        }
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
            if (guiHook !== null) {
                guiHook.detach();
                guiHook = null;
            }
        } catch (eG) {}
        try {
            if (fastTelemetryTimer !== null) {
                clearInterval(fastTelemetryTimer);
                fastTelemetryTimer = null;
            }
        } catch (e0) {}
        try {
            Interceptor.flush();
        } catch (eF) {}
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
        # 1. Khởi tạo toàn bộ offset mặc định (Chuẩn xác 100% của bản MEGAMU hiện tại)
        self.offsets = dict(DEFAULT_OFFSETS)

        # 2. Bổ sung các offset mới từ Native C++ Security Bridge nếu chưa có trong DEFAULT_OFFSETS
        try:
            from license_client import get_secure_game_offsets, is_native_bridge_active
            if is_native_bridge_active():
                sec_offsets = get_secure_game_offsets()
                if sec_offsets and isinstance(sec_offsets, dict):
                    for k, v in sec_offsets.items():
                        if v and k not in self.offsets:
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
            "__GET_PLAYER__": self.offsets.get("get_player") or DEFAULT_OFFSETS.get("get_player", "0x10A8080"),
            "__GET_GAME_UI__": self.offsets.get("get_game_ui") or DEFAULT_OFFSETS.get("get_game_ui", "0x10A80F0"),
            "__UI_CHAT_FRAME__": self.offsets.get("ui_chat_frame") or DEFAULT_OFFSETS.get("ui_chat_frame", "0x50"),
            "__MOVE_TO__": self.offsets.get("move_to") or DEFAULT_OFFSETS.get("move_to", "0xBBA6C0"),
            "__CHAT_SEND__": self.offsets.get("chat_send") or DEFAULT_OFFSETS.get("chat_send", "0x13408D0"),
            "__CHAT_SEND_CMD__": self.offsets.get("chat_send_cmd") or DEFAULT_OFFSETS.get("chat_send_cmd", "0xF7CCF0"),
            "__CHAT_FRAME_SEND__": self.offsets.get("chat_frame_send") or DEFAULT_OFFSETS.get("chat_frame_send", "0x13408D0"),
            "__STATIC_CHAT_SEND__": self.offsets.get("static_chat_send") or DEFAULT_OFFSETS.get("static_chat_send", "0xF735B0"),
            "__COMMAND_MGR_PROCESS__": self.offsets.get("command_mgr_process") or DEFAULT_OFFSETS.get("command_mgr_process", "0xF7CCF0"),
            "__CHAT_UPDATE__": self.offsets.get("chat_update") or DEFAULT_OFFSETS.get("chat_update", "0x1323D00"),
            "__GAME_UI_UPDATE__": self.offsets.get("game_ui_update") or DEFAULT_OFFSETS.get("game_ui_update", "0x139FEC0"),
            "__HELPER_START__": self.offsets.get("helper_start") or DEFAULT_OFFSETS.get("helper_start", "0x26BB0C0"),
            "__HELPER_STOP__": self.offsets.get("helper_stop") or DEFAULT_OFFSETS.get("helper_stop", "0x26BB270"),
            "__HELPER_TOGGLE__": self.offsets.get("helper_toggle") or DEFAULT_OFFSETS.get("helper_toggle", "0x24F1F10"),
            "__PLAYER_NAME__": self.offsets.get("player_name") or DEFAULT_OFFSETS.get("player_name", "0x28"),
            "__PLAYER_LEVEL__": self.offsets.get("player_level") or DEFAULT_OFFSETS.get("player_level", "0x30"),
            "__PLAYER_CLASS__": self.offsets.get("player_class") or DEFAULT_OFFSETS.get("player_class", "0x34"),
            "__PLAYER_COORD__": self.offsets.get("player_coord") or DEFAULT_OFFSETS.get("player_coord", "0x68"),
            "__PLAYER_MOVE__": self.offsets.get("player_move") or DEFAULT_OFFSETS.get("player_move", "0xF0"),
            "__PLAYER_HELPER__": self.offsets.get("player_helper") or DEFAULT_OFFSETS.get("player_helper", "0x1E8"),
            "__PLAYER_LAST_COORD__": self.offsets.get("player_last_coord") or DEFAULT_OFFSETS.get("player_last_coord", "0x4E0"),
            "__MOVE_FLAG__": self.offsets.get("move_flag") or DEFAULT_OFFSETS.get("move_flag", "0x3C"),
            "__HELPER_STATE__": self.offsets.get("helper_state") or DEFAULT_OFFSETS.get("helper_state", "0x20"),
            "__GET_WORLD__": self.offsets.get("get_world") or DEFAULT_OFFSETS.get("get_world", "0x10ABBE0"),
            "__GAME_TYPE_INFO__": self.offsets.get("game_type_info") or DEFAULT_OFFSETS.get("game_type_info", "0x549B980"),
            "__GAME_WORLD__": self.offsets.get("game_world") or DEFAULT_OFFSETS.get("game_world", "0x200"),
            "__START_AUTO_MOVE__": self.offsets.get("start_auto_move") or DEFAULT_OFFSETS.get("start_auto_move", "0xBCB280"),
            "__STOP_AUTO_MOVE__": self.offsets.get("stop_auto_move") or DEFAULT_OFFSETS.get("stop_auto_move", "0xBCB300"),
            "__AUTO_MOVE_WORKING__": self.offsets.get("auto_move_working") or DEFAULT_OFFSETS.get("auto_move_working", "0x498"),
            "__AUTO_MOVE_TYPE__": self.offsets.get("auto_move_type") or DEFAULT_OFFSETS.get("auto_move_type", "0x49C"),
            "__AUTO_MOVE_HELPER__": self.offsets.get("auto_move_helper") or DEFAULT_OFFSETS.get("auto_move_helper", "0x4A0"),
            "__AUTO_MOVE_DEST__": self.offsets.get("auto_move_dest") or DEFAULT_OFFSETS.get("auto_move_dest", "0x4A8"),
            "__WORLD_SCENE_INDEX__": self.offsets.get("world_scene_index") or DEFAULT_OFFSETS.get("world_scene_index", "0x20"),
            "__MOSS_ROLL__": self.offsets.get("moss_roll") or DEFAULT_OFFSETS.get("moss_roll", "0x26D1580"),
            "__MOSS_OPEN__": self.offsets.get("moss_open") or DEFAULT_OFFSETS.get("moss_open", "0x25117F0"),
            "__UI_MOSS_WINDOW__": self.offsets.get("ui_moss_window") or DEFAULT_OFFSETS.get("ui_moss_window", "0x1C8"),
            "__WINDOW_SHOW__": self.offsets.get("window_show") or DEFAULT_OFFSETS.get("window_show", "0x25117F0"),
            "__WINDOW_SET_STATE__": self.offsets.get("window_set_state") or DEFAULT_OFFSETS.get("window_set_state", "0x25115F0"),
            "__MOSS_ROLL_HANDLER__": self.offsets.get("moss_roll_handler") or DEFAULT_OFFSETS.get("moss_roll_handler", "0x26D1180"),
            "__MOSS_INIT__": self.offsets.get("moss_init") or DEFAULT_OFFSETS.get("moss_init", "0x26D13C0"),
            "__MOSS_SELECT_CAT__": self.offsets.get("moss_select_cat") or DEFAULT_OFFSETS.get("moss_select_cat", "0x26CFD60"),
            "__GAME_OBJECT_SET_ACTIVE__": self.offsets.get("game_object_set_active") or DEFAULT_OFFSETS.get("game_object_set_active", "0x4530F50"),
            "__MIRROR_ENTER__": self.offsets.get("mirror_enter") or DEFAULT_OFFSETS.get("mirror_enter", "0xFF08D0"),
            "__MIRROR_NPC_CLICK__": self.offsets.get("mirror_npc_click") or DEFAULT_OFFSETS.get("mirror_npc_click", "0xFED810"),
            "__MIRROR_IS_EVENT_MAP__": self.offsets.get("mirror_is_event_map") or DEFAULT_OFFSETS.get("mirror_is_event_map", "0xFEFA00"),
            "__MIRROR_TELEPORT_EVENT__": self.offsets.get("mirror_teleport_event") or DEFAULT_OFFSETS.get("mirror_teleport_event", "0xFF5AF0"),
            "__INV_SELL_ITEM__": self.offsets.get("inv_sell_item") or DEFAULT_OFFSETS.get("inv_sell_item", "0x14B8B30"),
            "__INV_TRASH_ITEM__": self.offsets.get("inv_trash_item") or DEFAULT_OFFSETS.get("inv_trash_item", "0x122B8E0"),
            "__PLAYER_INVENTORY__": self.offsets.get("player_inventory") or DEFAULT_OFFSETS.get("player_inventory", "0x1B8"),
            "__INVENTORY_ITEMS__": self.offsets.get("inventory_items") or DEFAULT_OFFSETS.get("inventory_items", "0x28"),
            "__GET_AUTO_LOGIN__": self.offsets.get("get_auto_login") or DEFAULT_OFFSETS.get("get_auto_login", "0x10A9500"),
            "__SET_AUTO_LOGIN__": self.offsets.get("set_auto_login") or DEFAULT_OFFSETS.get("set_auto_login", "0xF4B220"),
            "__NPC_TALK__": self.offsets.get("npc_talk") or DEFAULT_OFFSETS.get("npc_talk", "0x10B2B40"),
            "__VIEWPORT__": self.offsets.get("viewport") or DEFAULT_OFFSETS.get("viewport", "0x110"),
        }
        for k, v in mapping.items():
            js = js.replace(k, str(v))
        return js

    def _on_message(self, message: Dict[str, Any], data: Any):
        try:
            m_type = message.get("type")
            if m_type == "error":
                desc = message.get("description", "")
                stack = message.get("stack", "")
                trace_frida_event("SCRIPT_ERROR", f"Frida Script Error PID {self.pid}: {desc} | Stack: {stack}", pid=self.pid, level="ERROR")
                _safe_log(f"[MegDirectEngine] SCRIPT_ERROR PID {self.pid}: {desc}")
                return
            if m_type == "send":
                payload = message.get("payload")
                if isinstance(payload, dict):
                    p_type = payload.get("type")
                    if p_type == "fast_state":
                        info = payload.get("info")
                        if isinstance(info, dict):
                            if "name" in info and info["name"]:
                                self.char_name = info["name"]
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

    def _on_detached(self, reason: str, crash: Any = None):
        details = f"Phiên Frida bị ngắt kết nối (reason: {reason})"
        if crash:
            details += f" | Crash report: {crash}"
        level = "WARN" if reason in ("application-requested", "process-terminated") else "ERROR"
        trace_frida_event("FRIDA_DETACHED", details, pid=self.pid, level=level)
        if reason == "crash" or (crash is not None):
            char_display = getattr(self, "char_name", "")
            trace_process_exit(self.pid, f"CRASH: Tiến trình MEGAMU bị sập ngầm! Chi tiết: {reason} - {crash}", char_name=char_display)
        self.is_ready = False

    def reconnect(self) -> bool:
        """Thực hiện ngắt kết nối và kết nối lại sạch sẽ (Safe Reconnect)."""
        self.detach()
        time.sleep(0.08)
        self._claim_mutex()
        return self._attach()

    def attach(self) -> bool:
        if self.is_ready:
            return True
        if self.session is not None or self.script is not None:
            self.detach()
            time.sleep(0.05)
            self._claim_mutex()
        return self._attach()

    def _attach(self) -> bool:
        if psutil and not psutil.pid_exists(self.pid):
            _safe_log(f"[MegDirectEngine] Tiến trình PID {self.pid} không tồn tại trên hệ thống.")
            self.is_ready = False
            return False

        if frida is None:
            _safe_log("[MegDirectEngine] Thư viện frida chưa được cài đặt trong môi trường python.")
            return False

        try:
            self.session = frida.attach(self.pid)
            try:
                self.session.on("detached", self._on_detached)
            except Exception:
                pass
            js_code = self._generate_js()
            self.script = self.session.create_script(js_code)
            self.script.on("message", self._on_message)
            self.script.load()
            self.is_ready = True
            trace_frida_event("ATTACH_SUCCESS", f"Đã kết nối Frida session thành công tới PID {self.pid}", pid=self.pid)
            return True
        except Exception as e:
            trace_frida_event("ATTACH_ERROR", f"Lỗi attach Frida tới PID {self.pid}: {e}", pid=self.pid, level="ERROR")
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
                _safe_log(f"[MegDirectEngine] RPC _call '{func_name}' error: {e}")
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

    auto_move_to = start_auto_move

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
        """Hủy lệnh di chuyển và hãm phanh nhân vật đứng yên ngay tại vị trí hiện tại."""
        res_frida = False
        if self.is_ready:
            try:
                res_frida = bool(self._call("cancelMove"))
            except Exception:
                pass

        # Hủy Auto Move RAM và xóa cờ di chuyển
        try:
            from meg_navigator import ProcessMemoryReader
            if hasattr(ProcessMemoryReader, "cancel_auto_move_state"):
                ProcessMemoryReader.cancel_auto_move_state(self.pid)
        except Exception:
            pass

        return res_frida

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

    def send_chat(self, command: str, force_simulator: bool = False) -> bool:
        """
        Gửi lệnh chat (chuyển map /move hoặc lệnh trong game):
        1. Gửi qua Frida Native Hook (Unity Main Thread).
        2. Đồng thời gửi qua Background PostMessage vào HWND của cửa sổ game (Zero-Focus, không cướp chuột/phím)
           để đảm bảo 100% game nhận lệnh dù Native Hook có bị Unity UI filter hay không.
        """
        cmd = str(command).strip()
        if not cmd:
            return False

        native_sent = False
        if not force_simulator and self.is_ready:
            try:
                if self._call("send_chat_native", cmd):
                    native_sent = True
                    time.sleep(0.12)
                    _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat native (Unity Main Thread): '{cmd}'")
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi gọi send_chat_native: {e}")

        if native_sent and not force_simulator:
            return True

        # Gửi bổ trợ qua Background PostMessage vào HWND cửa sổ game (Zero-Focus) nếu Native chưa gửi hoặc yêu cầu simulator
        hwnd = self.get_hwnd()
        pm_sent = False
        if hwnd:
            user32 = ctypes.windll.user32
            WM_CHAR = 0x0102
            VK_RETURN = 0x0D
            try:
                # 1. Enter mở khung chat
                self.send_background_key(hwnd, VK_RETURN, 0.05)
                time.sleep(0.10)
                # 2. Gõ từng ký tự lệnh
                for ch in cmd:
                    scan_code = user32.MapVirtualKeyW(ord(ch), 0)
                    lparam = 1 | (scan_code << 16)
                    user32.PostMessageW(hwnd, WM_CHAR, ord(ch), lparam)
                    time.sleep(0.015)
                time.sleep(0.08)
                # 3. Enter gửi lệnh
                self.send_background_key(hwnd, VK_RETURN, 0.05)
                time.sleep(0.08)
                pm_sent = True
                _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat '{cmd}' qua Background PostMessage (HWND 0x{hwnd:X}).")
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi PostMessage chat: {e}")

        return native_sent or pm_sent

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

    def start_helper(self, target_x: Optional[int] = None, target_y: Optional[int] = None, force_restart: bool = False) -> bool:
        """Kích hoạt bật MuHelper (Ưu tiên Native Memory Hook trên Unity Main Thread, an toàn tuyệt đối)."""
        self.last_fast_state = None

        # Nếu cần force_restart (để ghim lại tọa độ gốc cắm bãi): tắt helper cũ trước
        if force_restart and self.is_helper_active(force_refresh=True):
            self.stop_helper()
            time.sleep(0.2)

        # Nếu helper ĐÃ BẬT và không yêu cầu force_restart, return True ngay lập tức!
        if not force_restart and self.is_helper_active(force_refresh=True):
            return True

        tx = int(target_x) if target_x is not None else 0
        ty = int(target_y) if target_y is not None else 0

        # Kênh 1: Frida Native Hook (chạy trên Unity Main Thread qua Update Hook)
        if self.is_ready:
            try:
                self._call("startHelper", tx, ty)
            except Exception:
                pass
            for _ in range(6):
                time.sleep(0.04)
                if self.is_helper_active(force_refresh=True):
                    return True

        # Kênh 2: Chỉ khi Frida chưa bật được VÀ helper VẪN ĐANG TẮT, mới gửi phím Home
        if not self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.04) # Phím Home
                for _ in range(5):
                    time.sleep(0.04)
                    if self.is_helper_active(force_refresh=True):
                        return True

                # Kênh 3: Gửi phím Z ngầm (nếu Home chưa nhận)
                if not self.is_helper_active(force_refresh=True):
                    self.send_background_key(hwnd, 0x5A, 0.04) # Phím Z
                    for _ in range(4):
                        time.sleep(0.04)
                        if self.is_helper_active(force_refresh=True):
                            return True

        return self.is_helper_active(force_refresh=True)

    def stop_helper(self) -> bool:
        """Kích hoạt tắt MuHelper (An toàn tuyệt đối, không gửi phím Home bừa bãi khi đã tắt)."""
        self.last_fast_state = None

        # BƯỚC 0: Nếu helper ĐÃ TẮT rồi, không cần làm gì nữa, return True ngay lập tức!
        if not self.is_helper_active(force_refresh=True):
            return True

        # Kênh 1: Frida Native Hook trực tiếp trên Unity Main Thread
        if self.is_ready:
            try:
                self._call("stopHelper")
            except Exception:
                pass
            for _ in range(6):
                time.sleep(0.04)
                if not self.is_helper_active(force_refresh=True):
                    return True

        # Kênh 2: Chỉ khi Frida chưa tắt được VÀ helper VẪN ĐANG BẬT, mới gửi phím Home
        if self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.04) # Phím Home (Toggle)
                for _ in range(5):
                    time.sleep(0.04)
                    if not self.is_helper_active(force_refresh=True):
                        return True

        # Kênh 3: Fallback trực tiếp bộ nhớ nếu vẫn chưa tắt
        if self.is_ready and self.is_helper_active(force_refresh=True):
            try:
                self._call("setHelperStateDirect", 0)
                self._call("stopHelper")
            except Exception:
                pass
            time.sleep(0.05)

        return not self.is_helper_active(force_refresh=True)

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

    def find_moss_npc(self) -> Dict[str, Any]:
        """
        Quét tìm NPC Moss The Gambler thực tế trong Viewport của game:
        1. Ưu tiên đọc trực tiếp bộ nhớ RAM (ReadProcessMemory) từ Viewport.ObjectList (Zero-Injection, siêu tốc, an toàn tuyệt đối 100%).
        2. Fallback qua Frida RPC nếu đang sẵn sàng.
        """
        rpm_res = self._find_moss_npc_rpm()
        if rpm_res and rpm_res.get("found"):
            return rpm_res

        if self.is_ready:
            try:
                res = self._call("findMossNpc")
                if res and isinstance(res, dict) and res.get("found"):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi RPC findMossNpc: {e}")

        return rpm_res

    def _find_moss_npc_rpm(self) -> Dict[str, Any]:
        """Fallback quét tìm NPC Moss qua Win32 ReadProcessMemory từ Viewport.ObjectList."""
        if sys.platform != "win32" or not self.pid:
            return {"found": False}
        try:
            k32 = ctypes.windll.kernel32
            hProc = k32.OpenProcess(0x0410, False, self.pid)
            if not hProc:
                return {"found": False}
            try:
                def read_ptr(addr):
                    buf = ctypes.c_ulonglong()
                    k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 8, None)
                    return buf.value

                def read_i32(addr):
                    buf = ctypes.c_int32()
                    k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None)
                    return buf.value

                def read_str(addr):
                    if not addr: return ""
                    try:
                        l = read_i32(addr + 0x10)
                        if 0 < l < 64:
                            buf = ctypes.create_unicode_buffer(l)
                            k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr + 0x14), ctypes.byref(buf), l * 2, None)
                            return buf.value
                    except Exception:
                        pass
                    return ""

                base = self.get_module_base("GameAssembly.dll")
                if not base:
                    return {"found": False}

                type_info_off = int(self.offsets.get("game_type_info") or "0x549B980", 16)
                vp_off = int(self.offsets.get("viewport") or "0x110", 16)

                type_info = read_ptr(base + type_info_off)
                if not type_info: return {"found": False}
                static_fields = read_ptr(type_info + 0xB8)
                if not static_fields: return {"found": False}
                game_inst = read_ptr(static_fields + 0x8)
                if not game_inst: return {"found": False}
                viewport = read_ptr(game_inst + vp_off)
                if not viewport: return {"found": False}
                obj_dict = read_ptr(viewport + 0x20)
                if not obj_dict: return {"found": False}
                entries = read_ptr(obj_dict + 0x18)
                if not entries: return {"found": False}
                count = read_i32(obj_dict + 0x20)
                if count <= 0 or count > 500: return {"found": False}

                for i in range(count):
                    entry_addr = entries + 0x20 + i * 24
                    val = read_ptr(entry_addr + 16)
                    if not val: continue
                    body = read_ptr(val + 0x18)
                    if not body: continue
                    b_idx = read_i32(body + 0x20)
                    if b_idx < 0: continue

                    b_name = read_str(read_ptr(body + 0x28))
                    c_ptr = read_ptr(body + 0x68)
                    tx, ty = (read_i32(c_ptr + 0x10), read_i32(c_ptr + 0x14)) if c_ptr else (-1, -1)

                    is_moss = False
                    if b_name and "moss" in b_name.lower():
                        is_moss = True
                    elif 18 <= tx <= 26 and 220 <= ty <= 230:
                        is_moss = True

                    if is_moss:
                        return {
                            "found": True,
                            "index": b_idx,
                            "name": b_name or "Moss The Gambler",
                            "x": tx,
                            "y": ty
                        }
            finally:
                k32.CloseHandle(hProc)
        except Exception:
            pass
        return {"found": False}

    def interact_moss_npc(self, category_id: int = 0) -> Dict[str, Any]:
        """
        Tương tác/click trực tiếp vào NPC Moss thực tế:
        Phát lệnh Native NPC Talk (Mega.NpcManager$$JBMPIOPHIHI 0x10B2B40) để Server mở phiên đối thoại
        và hiển thị bảng Moss Merchant chính thức.
        """
        if self.is_ready:
            try:
                res = self._call("interactMossNpc", int(category_id))
                if res and isinstance(res, dict):
                    if res.get("success"):
                        _safe_log(f"[MegDirectEngine] PID {self.pid} tương tác click NPC Moss thành công: {res}")
                        log_crash_trace("DIRECT_ENGINE", "INFO", f"PID {self.pid} interact_moss_npc success: {res}")
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi interact_moss_npc: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "NOT_ATTACHED"}


    def enter_mirror(self, slot: int = 0) -> bool:
        """Gửi lệnh native vào cửa sự kiện Double Goer (Mirror of Dimensions)."""
        if self.is_ready:
            try:
                res = self._call("enterMirror", int(slot))
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi enter_mirror: {e}")
        return False

    def teleport_to_event_map(self) -> bool:
        """Dịch chuyển trực tiếp vào Bản đồ Sự Kiện (Event Map - Gate 507) qua native."""
        if self.is_ready:
            try:
                res = self._call("teleportToEventMap")
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi teleport_to_event_map: {e}")
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

    def clean_inventory_junk(self, method: str = "drop") -> Dict[str, Any]:
        """Tự động vứt (drop) hoặc bán toàn bộ vật phẩm rác trong Main Inventory (bảo toàn đồ Exc/Socket/Set/Ngọc/Đồ cộng)."""
        if self.is_ready:
            try:
                res_str = self._call("cleanInventoryJunk", str(method))
                if res_str:
                    return json.loads(res_str)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi clean_inventory_junk: {e}")
        return {"cleaned": 0, "error": "not_ready"}

    def drop_inventory_slot(self, slot: int, off_x: int = 1, off_y: int = 0) -> Dict[str, Any]:
        """Gửi lệnh vứt (drop) 1 slot cụ thể trong Main Inventory ra mặt đất (mặc định ô kế bên X+1)."""
        if self.is_ready:
            try:
                res = self._call("dropInventorySlot", int(slot), int(off_x), int(off_y))
                if res:
                    try:
                        return json.loads(res)
                    except Exception:
                        return {"ok": bool(res), "raw": res}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi drop_inventory_slot: {e}")
                return {"ok": False, "err": str(e)}
        return {"ok": False, "err": "not_ready"}

    def trash_inventory_slot(self, slot: int, off_x: int = 1, off_y: int = 0) -> Dict[str, Any]:
        """Gửi lệnh vứt/hủy 1 slot cụ thể trong Main Inventory ra mặt đất (alias cho drop_inventory_slot)."""
        return self.drop_inventory_slot(slot, off_x, off_y)

    def sell_inventory_slot(self, slot: int) -> bool:
        """Gửi lệnh bán 1 slot cụ thể trong Main Inventory vào Merchant."""
        if self.is_ready:
            try:
                return bool(self._call("sellInventorySlot", int(slot)))
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi sell_inventory_slot: {e}")
        return False

    def auto_login(self, server: int = 1, account: str = "", character: str = "") -> Dict[str, Any]:
        """Gửi lệnh AutoLogin native vào GameAssembly.dll để tự động đăng nhập vào game."""
        if self.is_ready:
            try:
                res = self._call("autoLogin", int(server), str(account), str(character))
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi auto_login: {e}")
                return {"ok": False, "err": str(e)}
        return {"ok": False, "err": "not_ready"}

    def detach(self):
        """
        Ngắt kết nối an toàn tuyệt đối chống crash GameAssembly / frida-agent do LdrUnloadDll:
        1. Gọi exports.cleanup() gỡ Interceptor hook (chatHook, guiHook), dừng timer telemetry, và Interceptor.flush()
        2. Chờ 120ms để các thread Unity rút sạch hoàn toàn khỏi trampoline
        3. Gọi session.detach() một cách tường minh trước khi dọn dẹp biến
        4. Giải phóng mutex để tiến trình khác có thể kết nối
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

