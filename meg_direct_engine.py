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
    "get_player": "0xFABB30",
    "get_game_ui": "0xFABF20",
    "ui_chat_frame": "0x50",
    "move_to": "0xB35B60",
    "start_auto_move": "0xB46370",
    "stop_auto_move": "0xB35DC0",
    "chat_send": "0x1247380",
    "chat_send_cmd": "0xE6C4F0",
    "chat_frame_send": "0x1247380",
    "static_chat_send": "0xE630B0",
    "command_mgr_process": "0xE6C4F0",
    "chat_update": "0x12594B0",
    "game_ui_update": "0x12B31E0",
    "helper_start": "0x2689720",
    "helper_stop": "0x2682B20",
    "helper_action": "0x268CF00",
    "helper_toggle": "0x268CF00",
    "helper_send_bf51": "0x26829C0",
    "helper_req_start": "0x26830F0",
    "helper_req_stop": "0x2683B80",
    "ui_location_frame": "0x80",
    "location_helper_on": "0x60",
    "location_helper_off": "0x68",
    "location_update_helper": "0x244C880",
    "player_name": "0x28",
    "player_level": "0x30",
    "player_class": "0x34",
    "player_coord": "0x68",
    "player_move": "0xE8",
    "player_helper": "0x1E0",
    "player_last_coord": "0x4C8",
    "auto_move_working": "0x480",
    "auto_move_type": "0x484",
    "auto_move_helper": "0x488",
    "auto_move_dest": "0x490",
    "move_flag": "0x3C",
    "helper_state": "0x20",
    "get_world": "0xFAC3F0",
    "game_type_info": "0x5466768",
    "game_world": "0x200",
    "world_scene_index": "0x20",
    "moss_roll": "0x262EE30",
    "moss_open": "0x24C0410",
    "ui_moss_window": "0x1C8",
    "window_show": "0x24C0410",
    "window_hide": "0x1942170",
    "window_set_state": "0x24C0220",
    "moss_roll_handler": "0x262DCB0",
    "moss_init": "0x262DCF0",
    "moss_select_cat": "0x2627DD0",
    "moss_send_roll": "0x22F2200",
    "moss_roll_click": "0x2632710",
    "moss_window_close": "0x2632630",
    "game_object_set_active": "0x45084D0",
    "mirror_enter": "0xEFD7A0",
    "mirror_enter_alt": "0xEFF1B0",
    "mirror_npc_click": "0xEFDE60",
    "mirror_is_event_map": "0xF013A0",
    "mirror_teleport_event": "0x3802C0",
    "item_mirror_ticket": 7279,
    "devil_enter": "0xEF37B0",
    "devil_npc_click": "0xEFA3D0",
    "devil_is_event_map": "0xEF5580",
    "item_devil_ticket": 7187,
    "item_devil_ticket_master": 6702,
    "get_gs_connection": "0xFA9570",
    "gs_send": "0x1115380",
    "gs_send_alt": "0x1119CF0",
    "player_point": "0x238",
    "player_master_point": "0x23C",
    "player_reset_count": "0x2B4",
    "inv_sell_item": "0x1367460",
    "inv_drop_item": "0x1368A30",
    "inv_trash_item": "0x13678A0",
    "player_inventory": "0x1B0",
    "inventory_items": "0x28",
    "get_auto_login": "0xFAC460",
    "set_auto_login": "0xE59220",
    "npc_talk": "0xF8D320",
    "viewport": "0x110",
    "component_get_game_object": "0x45040B0",
    "get_window_handler": "0xFAACF0",
    "npc_close_talk": "0xF85E90",
    "npc_click": "0xF785E0",
    "ui_merchant_window": "0x198",
    "merchant_sell_item": "0x2605BB0",
    "slot_quick_action": "0x22DB330",
    "item_storage_type_info": "0x546C240",
    "mlogin_ui_type_info": "0x5451C68",
    "mlogin_submit": "0x1B6DA50",
    "mlogin_token_login": "0x1B70230",
    "game_update": "0xF97C30",
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
var nativeStartHelper = null;
var nativeStopHelper = null;
var nativeSendHelperAction = null;
var nativeHelperToggle = null;
try {
    var shOff = off('__HELPER_START__');
    if (!shOff.isNull()) {
        nativeStartHelper = new NativeFunction(baseAddr.add(shOff), 'void', ['pointer', 'pointer']);
    }
} catch (eSH) {}
try {
    var sthOff = off('__HELPER_STOP__');
    if (!sthOff.isNull()) {
        nativeStopHelper = new NativeFunction(baseAddr.add(sthOff), 'void', ['pointer', 'pointer']);
    }
} catch (eSTH) {}
try {
    var haOff = off('__HELPER_ACTION__');
    if (!haOff.isNull()) {
        nativeSendHelperAction = new NativeFunction(baseAddr.add(haOff), 'void', ['int', 'pointer']);
    }
} catch (eHA) {}
try {
    var htOff = off('__HELPER_TOGGLE__');
    if (!htOff.isNull()) {
        nativeHelperToggle = new NativeFunction(baseAddr.add(htOff), 'void', ['int', 'pointer']);
    }
} catch (eHT) {}
var nativeHelperSendBf51 = null;
try {
    var hsbOff = off('__HELPER_SEND_BF51__');
    if (!hsbOff.isNull()) {
        nativeHelperSendBf51 = new NativeFunction(baseAddr.add(hsbOff), 'void', ['int', 'pointer']);
    }
} catch (eHSB) {}
var nativeHelperReqStart = null;
try {
    var hrsOff = off('__HELPER_REQ_START__');
    if (!hrsOff.isNull()) {
        nativeHelperReqStart = new NativeFunction(baseAddr.add(hrsOff), 'void', ['pointer', 'pointer']);
    }
} catch (eHRS) {}
var nativeHelperReqStop = null;
try {
    var hrstOff = off('__HELPER_REQ_STOP__');
    if (!hrstOff.isNull()) {
        nativeHelperReqStop = new NativeFunction(baseAddr.add(hrstOff), 'void', ['pointer', 'pointer']);
    }
} catch (eHRST) {}
var nativeLocationFrameUpdate = null;
try {
    var lfuOff = off('__LOCATION_UPDATE_HELPER__');
    if (!lfuOff.isNull()) {
        nativeLocationFrameUpdate = new NativeFunction(baseAddr.add(lfuOff), 'void', ['pointer', 'pointer']);
    }
} catch (eLFU) {}
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

var nativeWindowHide = null;
try {
    var whOff = off('__WINDOW_HIDE__');
    if (!whOff.isNull()) {
        nativeWindowHide = new NativeFunction(baseAddr.add(whOff), 'void', ['pointer', 'pointer']);
    }
} catch (eWHide) {}

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

var nativeMossSendRoll = null;
try {
    var msrOff = off('__MOSS_SEND_ROLL__');
    if (!msrOff.isNull()) {
        nativeMossSendRoll = new NativeFunction(baseAddr.add(msrOff), 'void', ['int32']);
    }
} catch (eMossSR) {}

var nativeMossRollClick = null;
try {
    var mrcOff = off('__MOSS_ROLL_CLICK__');
    if (!mrcOff.isNull()) {
        nativeMossRollClick = new NativeFunction(baseAddr.add(mrcOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMossRC) {}

var nativeMossWindowClose = null;
try {
    var mwcOff = off('__MOSS_WINDOW_CLOSE__');
    if (!mwcOff.isNull()) {
        nativeMossWindowClose = new NativeFunction(baseAddr.add(mwcOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMossWC) {}

var nativeGameObjectSetActive = null;
try {
    var gosaOff = off('__GAME_OBJECT_SET_ACTIVE__');
    if (!gosaOff.isNull()) {
        nativeGameObjectSetActive = new NativeFunction(baseAddr.add(gosaOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eGOSA) {}

var nativeComponentGetGameObject = null;
try {
    var cggoOff = off('__COMPONENT_GET_GAMEOBJECT__');
    if (!cggoOff.isNull()) {
        nativeComponentGetGameObject = new NativeFunction(baseAddr.add(cggoOff), 'pointer', ['pointer']);
    }
} catch (eCGGO) {}

var nativeMirrorEnter = null;
try {
    var meOff = off('__MIRROR_ENTER__');
    if (!meOff.isNull()) {
        nativeMirrorEnter = new NativeFunction(baseAddr.add(meOff), 'void', ['int', 'pointer']);
    }
} catch (eMirrorEnter) {}

var nativeMirrorEnterAlt = null;
try {
    var meaOff = off('__MIRROR_ENTER_ALT__');
    if (!meaOff.isNull()) {
        nativeMirrorEnterAlt = new NativeFunction(baseAddr.add(meaOff), 'void', ['int', 'pointer']);
    } else {
        nativeMirrorEnterAlt = new NativeFunction(baseAddr.add(ptr('0xEFF1B0')), 'void', ['int', 'pointer']);
    }
} catch (eMirrorEnterAlt) {}

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

var nativeMirrorTeleportEventMap = null;
try {
    var mtemOff = off('__MIRROR_TELEPORT_EVENT__');
    if (!mtemOff.isNull()) {
        nativeMirrorTeleportEventMap = new NativeFunction(baseAddr.add(mtemOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eMirrorTeleport) {}

var nativeDevilEnter = null;
try {
    var deOff = off('__DEVIL_ENTER__');
    if (!deOff.isNull()) {
        nativeDevilEnter = new NativeFunction(baseAddr.add(deOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eDevilEnter) {}

var nativeDevilNpcClick = null;
try {
    var dnOff = off('__DEVIL_NPC_CLICK__');
    if (!dnOff.isNull()) {
        nativeDevilNpcClick = new NativeFunction(baseAddr.add(dnOff), 'void', ['pointer', 'pointer']);
    }
} catch (eDevilNpc) {}

var nativeDevilIsEventMap = null;
try {
    var dimOff = off('__DEVIL_IS_EVENT_MAP__');
    if (!dimOff.isNull()) {
        nativeDevilIsEventMap = new NativeFunction(baseAddr.add(dimOff), 'bool', []);
    }
} catch (eDevilMap) {}

var nativeNpcTalk = null;
try {
    var ntOff = off('__NPC_TALK__');
    if (!ntOff.isNull()) {
        nativeNpcTalk = new NativeFunction(baseAddr.add(ntOff), 'void', ['pointer', 'pointer']);
    }
} catch (eNT) {}

var nativeCloseTalk = null;
try {
    var nctOff = off('__NPC_CLOSE_TALK__');
    if (!nctOff.isNull()) {
        nativeCloseTalk = new NativeFunction(baseAddr.add(nctOff), 'void', []);
    }
} catch (eNCT) {}

var nativeUniversalNpcClick = null;
try {
    var uncOff = off('__NPC_CLICK__');
    if (!uncOff.isNull()) {
        nativeUniversalNpcClick = new NativeFunction(baseAddr.add(uncOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eUNC) {}

var nativeGetWindowHandler = null;
try {
    var gwhOff = off('__GET_WINDOW_HANDLER__');
    if (!gwhOff.isNull()) {
        nativeGetWindowHandler = new NativeFunction(baseAddr.add(gwhOff), 'pointer', []);
    }
} catch (eGWH) {}

var nativeInvSellItem = null;
try {
    var isiOff = off('__INV_SELL_ITEM__');
    if (!isiOff.isNull()) {
        nativeInvSellItem = new NativeFunction(baseAddr.add(isiOff), 'pointer', ['pointer', 'int', 'pointer', 'pointer']);
    }
} catch (eInvSell) {}

var nativeMerchantSellItem = null;
try {
    var msiOff = off('__MERCHANT_SELL_ITEM__');
    if (!msiOff.isNull()) {
        nativeMerchantSellItem = new NativeFunction(baseAddr.add(msiOff), 'void', ['pointer', 'int', 'pointer', 'pointer']);
    }
} catch (eMSI) {}

var nativeSlotQuickAction = null;
try {
    var sqaOff = off('__SLOT_QUICK_ACTION__');
    if (!sqaOff.isNull()) {
        nativeSlotQuickAction = new NativeFunction(baseAddr.add(sqaOff), 'void', ['pointer', 'pointer']);
    }
} catch (eSQA) {}

var nativeInvDropItem = null;
try {
    var idiOff = off('__INV_DROP_ITEM__');
    if (!idiOff.isNull()) {
        nativeInvDropItem = new NativeFunction(baseAddr.add(idiOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eInvDrop) {}

var nativeInvTrashItem = null;
try {
    var itiOff = off('__INV_TRASH_ITEM__');
    if (!itiOff.isNull()) {
        nativeInvTrashItem = new NativeFunction(baseAddr.add(itiOff), 'void', ['pointer', 'int', 'pointer']);
    }
} catch (eInvTrash) {}

var nativeInvSellItem = null;
try {
    var isiOff = off('__INV_SELL_ITEM__');
    if (!isiOff.isNull()) {
        nativeInvSellItem = new NativeFunction(baseAddr.add(isiOff), 'void', ['pointer', 'int', 'pointer']);
    }
} catch (eInvSell) {}

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

var nativeMLoginSubmit = null;
try {
    var mlsOff = off('__MLOGIN_SUBMIT__');
    if (!mlsOff.isNull()) {
        nativeMLoginSubmit = new NativeFunction(baseAddr.add(mlsOff), 'void', ['pointer', 'pointer', 'pointer', 'bool', 'pointer']);
    }
} catch (eMLS) {}

var nativeMLoginTokenLogin = null;
try {
    var mltOff = off('__MLOGIN_TOKEN_LOGIN__');
    if (!mltOff.isNull()) {
        nativeMLoginTokenLogin = new NativeFunction(baseAddr.add(mltOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eMLT) {}

var nativeGetGS = null;
try {
    var gsOff = off('__GET_GS_CONNECTION__');
    if (!gsOff.isNull()) {
        nativeGetGS = new NativeFunction(baseAddr.add(gsOff), 'pointer', ['pointer']);
    }
} catch (eGS) {}

var nativeGSSend = null;
try {
    var sendOff = off('__GS_SEND__');
    if (!sendOff.isNull()) {
        nativeGSSend = new NativeFunction(baseAddr.add(sendOff), 'void', ['pointer', 'pointer', 'bool', 'bool', 'pointer']);
    }
} catch (eGSSend) {}

var nativeGSSendAlt = null;
try {
    var sendAltOff = off('__GS_SEND_ALT__');
    if (!sendAltOff.isNull()) {
        nativeGSSendAlt = new NativeFunction(baseAddr.add(sendAltOff), 'void', ['pointer', 'pointer', 'bool', 'bool', 'pointer']);
    }
} catch (eGSSendAlt) {}

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

function getGSConnection() {
    try {
        if (nativeGetGS !== null) {
            var conn = nativeGetGS(ptr(0));
            if (!conn.isNull()) return conn;
        }
    } catch (e1) {}
    try {
        var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
        if (!typeInfo.isNull()) {
            var sf = typeInfo.add(ptr('0xB8')).readPointer();
            if (!sf.isNull()) {
                var gi = sf.add(ptr('0x8')).readPointer();
                if (!gi.isNull()) {
                    var conn2 = gi.add(ptr('0xD0')).readPointer();
                    if (!conn2.isNull()) return conn2;
                }
            }
        }
    } catch (e2) {}
    return ptr(0);
}

var _cachedByteClass = null;
function getByteClass() {
    if (_cachedByteClass !== null && !_cachedByteClass.isNull()) return _cachedByteClass;
    try {
        if (mono_domain_get_corlib !== null && il2cpp_class_from_name !== null) {
            var corlib = mono_domain_get_corlib();
            if (!corlib.isNull()) {
                _cachedByteClass = il2cpp_class_from_name(corlib, Memory.allocUtf8String("System"), Memory.allocUtf8String("Byte"));
            }
        }
    } catch (eBC) {}
    return _cachedByteClass;
}

function sendGSPacket(bytes) {
    try {
        if (il2cpp_array_new === null) return false;
        var gs = getGSConnection();
        if (gs.isNull()) return false;
        var bClass = getByteClass();
        if (!bClass || bClass.isNull()) return false;
        var arr = il2cpp_array_new(bClass, bytes.length);
        if (arr.isNull()) return false;
        var raw = arr.add(0x20);
        for (var i = 0; i < bytes.length; i++) {
            raw.add(i).writeU8(bytes[i] & 0xFF);
        }
        var sent = false;
        if (nativeGSSend !== null) {
            try { nativeGSSend(gs, arr, 0, 0, ptr(0)); sent = true; } catch (eS1) {}
        }
        if (!sent && nativeGSSendAlt !== null) {
            try { nativeGSSendAlt(gs, arr, 0, 0, ptr(0)); sent = true; } catch (eS2) {}
        }
        return sent;
    } catch (ePkt) {
        return false;
    }
}

var pendingMossOpenCategory = null;
var pendingMossRollCategory = null;
var pendingMossInteractPtr = null;
var pendingMerchantInteractPtr = null;

function sendDropPacket(slot, targetX, targetY) {
    try {
        var s = parseInt(slot) & 0xFF;
        var tx = parseInt(targetX) & 0xFF;
        var ty = parseInt(targetY) & 0xFF;
        // In MEGAMU protocol packet 0x23: [0xC1, 0x06, 0x23, targetX, targetY, slot]
        var ok = sendGSPacket([0xC1, 0x06, 0x23, tx, ty, s]);
        if (!ok) {
            var rel = (s >= 12) ? (s - 12) : s;
            ok = sendGSPacket([0xC1, 0x06, 0x23, tx, ty, rel]);
        }
        return ok;
    } catch (eDropPkt) {
        return false;
    }
}

function sendSellPacket(slot) {
    try {
        var rel = (slot >= 12) ? (slot - 12) : slot;
        sendGSPacket([0xC1, 0x04, 0x33, rel & 0xFF]);
        sendGSPacket([0xC1, 0x04, 0x33, slot & 0xFF]);
        return true;
    } catch (eSellPkt) {
        return false;
    }
}

function sendMirrorEnterPacket(slot) {
    try {
        var rel = (slot >= 12) ? (slot - 12) : slot;
        var p1 = sendGSPacket([0xC1, 0x05, 0xBF, 0x0E, rel & 0xFF]);
        var p2 = sendGSPacket([0xC1, 0x05, 0xB0, 0xAB, rel & 0xFF]);
        return (p1 || p2);
    } catch (eMirrorPkt) {
        return false;
    }
}

function sendDevilEnterPacket(level, slot) {
    try {
        var actualSlot = (slot < 12 && slot >= 0) ? (slot + 12) : slot;
        return sendGSPacket([0xC1, 0x05, 0x90, level & 0xFF, actualSlot & 0xFF]);
    } catch (eDevilPkt) {
        return false;
    }
}

function sendGatePacket(gateId) {
    try {
        return sendGSPacket([0xC1, 0x05, 0x1C, gateId & 0xFF, (gateId >> 8) & 0xFF]);
    } catch (eGatePkt) {
        return false;
    }
}

var nativeGetConfig = null;
try {
    nativeGetConfig = new NativeFunction(baseAddr.add(ptr('0x1103450')), 'pointer', []);
} catch (eCfg) {}

var nativeGetUser2FA = null;
try {
    nativeGetUser2FA = new NativeFunction(baseAddr.add(ptr('0x11019B0')), 'pointer', []);
} catch (e2fa) {}

function ensureDropAllowed() {
    var ok = false;
    try {
        if (nativeGetConfig !== null) {
            var cfg = nativeGetConfig();
            if (!cfg.isNull()) {
                var clientInfo = cfg.add(0x20).readPointer();
                if (!clientInfo.isNull()) {
                    clientInfo.add(0xE1).writeU8(1);
                    ok = true;
                }
            }
        }
    } catch (e1) {}
    try {
        if (nativeGetUser2FA !== null) {
            var u2fa = nativeGetUser2FA();
            if (!u2fa.isNull()) {
                u2fa.add(0x20).writeU8(0);
                var lockedArr = u2fa.add(0x28).readPointer();
                if (!lockedArr.isNull()) {
                    var len = lockedArr.add(0x18).readS32();
                    if (len > 13) {
                        lockedArr.add(0x20 + 13).writeU8(0);
                    }
                }
            }
        }
    } catch (e2faErr) {}
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
                                ok = true;
                            }
                        }
                    }
                }
            }
        }
    } catch (e2) {}
    return ok;
}

var nativeGetItemName = null;
try {
    nativeGetItemName = new NativeFunction(baseAddr.add(ptr('0x123ECB0')), 'pointer', ['pointer', 'bool', 'pointer']);
} catch (eNm) {}

function getItemName(itemPtr) {
    if (!itemPtr || itemPtr.isNull()) return "";
    try {
        if (nativeGetItemName !== null) {
            var sPtr = nativeGetItemName(itemPtr, 1, ptr(0));
            if (!sPtr.isNull()) {
                var len = sPtr.add(0x10).readS32();
                if (len > 0 && len < 200) {
                    var str = sPtr.add(0x14).readUtf16String(len);
                    if (str && str.length > 0) return str;
                }
            }
        }
    } catch (e1) {}
    try {
        var te = itemPtr.add(0x58).readPointer();
        if (!te.isNull()) {
            var offsets = [0x38, 0x30, 0x28, 0x20, 0x40, 0x48, 0x50];
            for (var i = 0; i < offsets.length; i++) {
                var sPtr = te.add(offsets[i]).readPointer();
                if (!sPtr.isNull()) {
                    var len = sPtr.add(0x10).readS32();
                    if (len > 0 && len < 200) {
                        var text = sPtr.add(0x14).readUtf16String(len);
                        if (text && text.length > 0) return text;
                    }
                }
            }
        }
    } catch (e2) {}
    return "";
}

function readItemIndex(itemPtr) {
    if (!itemPtr || itemPtr.isNull()) return -1;
    var idx = -1;
    try {
        idx = itemPtr.add(0x60).readS32();
    } catch (e1) {}
    if (idx <= 0) {
        try {
            idx = itemPtr.add(0x10).readS32();
        } catch (e2) {}
    }
    return idx;
}

function checkMirrorItem(itemPtr, idx) {
    var trueIdx = (idx !== undefined && idx !== null && idx > 0) ? idx : readItemIndex(itemPtr);
    var itName = getItemName(itemPtr) || "";
    var lowName = itName.toLowerCase();

    // 1. Nhận diện theo Item Index chuẩn (7279 = Mirror of Dimensions, 7280 = Sign of Dimensions)
    if (trueIdx === 7279) {
        return { isTicket: true, isSign: false, name: itName || "Mirror of Dimensions" };
    }
    if (trueIdx === 7280) {
        return { isTicket: false, isSign: true, name: itName || "Sign of Dimensions" };
    }

    // 2. Nhận diện theo Tên Item (tiếng Anh và tiếng Bồ Đào Nha MEGAMU)
    if (lowName.length > 0) {
        var hasMirrorWord = (lowName.indexOf("mirror") !== -1 || lowName.indexOf("espelho") !== -1);
        var hasDimWord = (lowName.indexOf("dimens") !== -1);
        var hasSignWord = (lowName.indexOf("sign") !== -1 || lowName.indexOf("sinal") !== -1);

        if (hasSignWord && (hasDimWord || hasMirrorWord)) {
            return { isTicket: false, isSign: true, name: itName };
        }
        if (hasMirrorWord || lowName.indexOf("doppelganger") !== -1) {
            return { isTicket: true, isSign: false, name: itName };
        }
    }

    return { isTicket: false, isSign: false, name: itName };
}

function isDivineOrDragonItem(itemPtr, itemIndex) {
    var sec = Math.floor(itemIndex / 512);
    var type = itemIndex % 512;

    // 1. Phân loại theo Item ID cố định trong database MU Online (Bảo vệ cứng 100%):
    // Set Rồng Đỏ (Dragon Set): Sec 7..11, Type 1
    // Set Rồng Đen (Black Dragon): Sec 7..11, Type 16
    // Set Nữ Thần (Divine Set - Elf): Sec 7..11, Type 18
    // Set Dragon Knight (Hiệp sĩ rồng): Sec 7..11, Type 29
    // Set Dark Devil / Dragon Soul / các set rồng mở rộng: Sec 7..11 (Type 30, 31)
    if ((type === 1 || type === 16 || type === 18 || type === 29 || type === 30 || type === 31) && (sec >= 7 && sec <= 11)) {
        return true;
    }
    // Khiên Rồng (Dragon Shield / Dragon Slayer Shield): Sec 6, Type 7, 17
    if (sec === 6 && (type === 7 || type === 17)) return true;
    // Vũ khí Rồng: Chaos Dragon Axe (Sec 1, Type 6), Dragon Spear (Sec 3, Type 10)
    if (sec === 1 && type === 6) return true;
    if (sec === 3 && type === 10) return true;
    // Vũ khí Divine Archangel (Tuyệt Tác Thần / Thiên Sứ):
    // Sec 0: Kiếm (Type 19, 30, 31, 40, 41)
    // Sec 2: Quyền trượng (Type 13, 30)
    // Sec 4: Cung/Nỏ (Type 18, 30)
    // Sec 5: Gậy/Sách (Type 10, 36, 40)
    if (sec === 0 && (type === 19 || type === 30 || type === 31 || type === 40 || type === 41)) return true;
    if (sec === 2 && (type === 13 || type === 30)) return true;
    if (sec === 4 && (type === 18 || type === 30)) return true;
    if (sec === 5 && (type === 10 || type === 36 || type === 40)) return true;

    // 2. Phân loại theo tên native của vật phẩm trong Game Memory (Hỗ trợ đa ngôn ngữ EN, PT, ES, VN):
    var name = getItemName(itemPtr).toLowerCase();
    if (name.length > 0) {
        var keywords = [
            "divine", "divino", "divina", "archangel", "arcanjo", "thiên sứ", "nữ thần",
            "dragon", "dragao", "dragão", "rồng"
        ];
        for (var k = 0; k < keywords.length; k++) {
            if (name.indexOf(keywords[k]) !== -1) {
                return true;
            }
        }
    }
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

    // Mega.Chat.FCIBNHIHDHO (nativeStaticChatSend - RVA 0xF95530):
    // Hàm tĩnh gốc của game xử lý TOÀN BỘ chat và lệnh '/' ngầm:
    // 1. Tự động gọi CommandManager.BDMGLHEGJHO để chạy các lệnh client (/reconnect, /fps...).
    // 2. Nếu là lệnh server (/warp, /move, /f, /a, /e, /c, /post...) hoặc tin nhắn thường,
    //    tự động đóng gói C1:00/C1:02 gửi trực tiếp lên GSConnection.
    // 3. Chạy 100% ngầm (headless), KHÔNG mở ChatFrame, KHÔNG cướp chuột/phím, KHÔNG phụ thuộc UI!
    if (nativeStaticChatSend !== null) {
        try {
            nativeStaticChatSend(str, ptr(0));
            return true;
        } catch (eStatic) {}
    }

    // Fallback: Nếu không có static_chat_send thì thử gọi CommandManager (cho lệnh '/')
    if (cmdText.charAt(0) === '/' && nativeCommandManagerProcess !== null) {
        try {
            nativeCommandManagerProcess(str, ptr(0));
            return true;
        } catch (eCmd) {}
    }

    return false;
}

var pendingHelperAction = null;

function syncHelperUI(isActive) {
    try {
        if (nativeGetGameUI === null) return;
        var gui = nativeGetGameUI();
        if (gui.isNull()) return;

        var locFrame = gui.add(off('__UI_LOCATION_FRAME__')).readPointer();
        if (!locFrame.isNull()) {
            // 1. Gọi trực tiếp hàm cập nhật icon/nút Helper của LocationFrame (0x244C880) hoặc qua vtable + 0x1E8
            if (nativeLocationFrameUpdate !== null) {
                try { nativeLocationFrameUpdate(locFrame, ptr(0)); } catch (eU1) {}
            } else {
                try {
                    var klass = locFrame.readPointer();
                    if (!klass.isNull()) {
                        var updateFnPtr = klass.add(ptr('0x1E8')).readPointer();
                        var methodInfo = klass.add(ptr('0x1F0')).readPointer();
                        if (!updateFnPtr.isNull()) {
                            var callVf = new NativeFunction(updateFnPtr, 'void', ['pointer', 'pointer']);
                            callVf(locFrame, methodInfo);
                        }
                    }
                } catch (eU2) {}
            }

            // 2. Trực tiếp kích hoạt/tắt GameObject của HelperStateOnImage (0x60) và HelperStateOffImage (0x68)
            // Đảm bảo icon Play/Stop trên thanh tọa độ màn hình game đổi trạng thái lập tức!
            if (nativeComponentGetGameObject !== null && nativeGameObjectSetActive !== null) {
                try {
                    var onImg = locFrame.add(off('__LOCATION_HELPER_ON__')).readPointer();
                    if (!onImg.isNull()) {
                        var onGo = nativeComponentGetGameObject(onImg, ptr(0));
                        if (!onGo.isNull()) {
                            nativeGameObjectSetActive(onGo, isActive ? 1 : 0, ptr(0));
                        }
                    }
                    var offImg = locFrame.add(off('__LOCATION_HELPER_OFF__')).readPointer();
                    if (!offImg.isNull()) {
                        var offGo = nativeComponentGetGameObject(offImg, ptr(0));
                        if (!offGo.isNull()) {
                            nativeGameObjectSetActive(offGo, isActive ? 0 : 1, ptr(0));
                        }
                    }
                } catch (eImg) {}
            }
        }
    } catch (eSync) {}
}

function dispatchHelperAction(act) {
    if (!act) return false;
    try {
        var p = getPlayerPtr();
        var h = ptr(0);
        if (!p.isNull()) {
            try { h = p.add(off('__PLAYER_HELPER__')).readPointer(); } catch (eH0) {}
        }

        var isAct = 0;
        if (!h.isNull()) {
            try { isAct = h.add(off('__HELPER_STATE__')).readU8(); } catch (eA) {}
        }

        if (act === 'start') {
            // 1. Cập nhật helper_state lên 1 trong RAM UserHelper
            if (!h.isNull()) {
                try { h.add(off('__HELPER_STATE__')).writeU8(1); } catch (eSW) {}
            }
            // 2. Gọi native StartHelper của UserHelper (0x2689720)
            if (!h.isNull() && nativeStartHelper !== null) {
                try { nativeStartHelper(h, ptr(0)); } catch (eS1) {}
            }
            // 3. Gọi UserHelper.OEKEGKPIANC (0x26830F0) hoặc gửi packet mạng chuẩn BF:51, 00
            if (!h.isNull() && nativeHelperReqStart !== null) {
                try { nativeHelperReqStart(h, ptr(0)); } catch (eRS) {}
            } else if (nativeHelperSendBf51 !== null) {
                try { nativeHelperSendBf51(0, ptr(0)); } catch (eBF0) {}
            }
            // 4. Fallback gửi packet B3:AD
            if (nativeSendHelperAction !== null) {
                try { nativeSendHelperAction(0, ptr(0)); } catch (eS2) {}
            } else if (nativeHelperToggle !== null) {
                try { nativeHelperToggle(0, ptr(0)); } catch (eS3) {}
            }
            // 5. Đồng bộ icon trên giao diện MLocationFrame (Play -> Stop)
            syncHelperUI(true);
            return true;
        } else if (act === 'stop') {
            // 1. Cập nhật helper_state về 0 trong RAM UserHelper
            if (!h.isNull()) {
                try { h.add(off('__HELPER_STATE__')).writeU8(0); } catch (eStW) {}
            }
            // 2. Gọi native StopHelper của UserHelper (0x2682B20)
            if (!h.isNull() && nativeStopHelper !== null) {
                try { nativeStopHelper(h, ptr(0)); } catch (eSt1) {}
            }
            // 3. Gọi UserHelper.JBEEAGHAHAC (0x2683B80) hoặc gửi packet mạng chuẩn BF:51, 01
            if (!h.isNull() && nativeHelperReqStop !== null) {
                try { nativeHelperReqStop(h, ptr(0)); } catch (eRSt) {}
            } else if (nativeHelperSendBf51 !== null) {
                try { nativeHelperSendBf51(1, ptr(0)); } catch (eBF1) {}
            }
            // 4. Fallback gửi packet B3:AD
            if (nativeSendHelperAction !== null) {
                try { nativeSendHelperAction(1, ptr(0)); } catch (eSt2) {}
            } else if (nativeHelperToggle !== null) {
                try { nativeHelperToggle(1, ptr(0)); } catch (eSt3) {}
            }
            // 5. Đồng bộ icon trên giao diện MLocationFrame (Stop -> Play)
            syncHelperUI(false);
            return true;
        } else if (act === 'toggle') {
            if (isAct === 1) {
                return dispatchHelperAction('stop');
            } else {
                return dispatchHelperAction('start');
            }
        }
    } catch (eH) {}
    return false;
}

var pendingMoveTarget = null;

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
                        pendingHelperAction = null;
                        try { dispatchHelperAction(hAct); } catch (eH1) {}
                    }
                    if (pendingMoveTarget !== null) {
                        var target = pendingMoveTarget;
                        pendingMoveTarget = null;
                        try {
                            var pMove = getPlayerPtr();
                            if (!pMove.isNull()) {
                                var destC = ptr(0);
                                try {
                                    var existingC = pMove.add(off('__AUTO_MOVE_DEST__')).readPointer();
                                    if (!existingC.isNull()) destC = existingC;
                                } catch (eD) {}
                                if (!destC.isNull()) {
                                    destC.add(0x10).writeS32(parseInt(target.x));
                                    destC.add(0x14).writeS32(parseInt(target.y));
                                    pMove.add(off('__AUTO_MOVE_DEST__')).writePointer(destC);
                                    pMove.add(off('__AUTO_MOVE_TYPE__')).writeS32(0);
                                    pMove.add(off('__AUTO_MOVE_HELPER__')).writeU8(target.helper ? 1 : 0);
                                    pMove.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
                                    try {
                                        moveToNative(pMove, destC, 0.0, ptr(0), 0, 1, ptr(0));
                                    } catch (eM) {}
                                } else {
                                    var curC = pMove.add(off('__PLAYER_COORD__')).readPointer();
                                    var k = ptr(0);
                                    try { if (!curC.isNull()) k = curC.readPointer(); } catch (eK1) {}
                                    if (k.isNull()) {
                                        try {
                                            var lastC = pMove.add(off('__PLAYER_LAST_COORD__')).readPointer();
                                            if (!lastC.isNull()) k = lastC.readPointer();
                                        } catch (eK2) {}
                                    }
                                    if (k.isNull() && cachedCoordKlass && !cachedCoordKlass.isNull()) {
                                        k = cachedCoordKlass;
                                    }
                                    if (!k.isNull()) {
                                        coordBuf.writePointer(k);
                                        coordBuf.add(0x08).writePointer(ptr(0));
                                        coordBuf.add(0x10).writeS32(parseInt(target.x));
                                        coordBuf.add(0x14).writeS32(parseInt(target.y));
                                        try {
                                            moveToNative(pMove, coordBuf, 0.0, ptr(0), 0, 1, ptr(0));
                                        } catch (eM2) {}
                                    }
                                }
                            }
                        } catch (eQueueMove) {}
                    }
                } catch (eEnter) {}
            }
        });
    }
} catch (eHook) {}

var pendingMossOpenCategory = null;
var pendingMossRollCategory = null;

function isGameObjectValid(goPtr) {
    if (!goPtr || goPtr.isNull()) return false;
    try {
        var m_CachedPtr = goPtr.add(0x10).readPointer();
        return !m_CachedPtr.isNull();
    } catch (e) {
        return false;
    }
}

function ensureMossRollButtonActive(mossWin, resetTimer) {
    if (!mossWin || mossWin.isNull()) return false;
    try {
        // 1. Tắt LoadingImage (offset 0x60)
        var loadingImg = mossWin.add(0x60).readPointer();
        if (!loadingImg.isNull() && isGameObjectValid(loadingImg) && nativeGameObjectSetActive !== null) {
            try {
                nativeGameObjectSetActive(loadingImg, 0, ptr(0));
            } catch (eLI) {}
        }

        // 2. Bật RollButton (offset 0x58)
        var rollBtn = mossWin.add(0x58).readPointer();
        if (!rollBtn.isNull()) {
            var btnObj = ptr(0);
            if (nativeComponentGetGameObject !== null) {
                try {
                    btnObj = nativeComponentGetGameObject(rollBtn);
                } catch (eGO) {}
            }
            if (!btnObj.isNull() && isGameObjectValid(btnObj) && nativeGameObjectSetActive !== null) {
                try {
                    nativeGameObjectSetActive(btnObj, 1, ptr(0));
                } catch (eAct) {}
            }
        }

        // 3. Reset timer quay 0x98 về 0 nếu được yêu cầu (mặc định resetTimer !== false)
        if (resetTimer !== false) {
            mossWin.add(0x98).writeFloat(0.0);
        }
        return true;
    } catch (e) {
        return false;
    }
}

function setupMossWindow(mossWin, cat) {
    if (!mossWin || mossWin.isNull()) return false;
    try {
        var catId = parseInt(cat || 0);

        // 1. Cập nhật Category ID (offset 0x78)
        mossWin.add(0x78).writeS32(catId);

        // 2. Kiểm tra danh sách Category từ Server
        // Tuyệt đối không gọi nativeMossInit để tránh sinh các nút CategoryItemPrefab trùng lặp!
        var catList = mossWin.add(0x80).readPointer();
        var catCount = 0;
        if (!catList.isNull()) {
            try { catCount = catList.add(0x18).readS32(); } catch (eCC) {}
        }

        // 3. Chọn đúng tab Category theo chỉ định
        if (nativeMossSelectCat !== null && !catList.isNull() && catCount > 0) {
            try {
                var items = catList.add(0x10).readPointer();
                if (!items.isNull() && catId < catCount && catId >= 0) {
                    var catObj = items.add(0x20 + catId * 8).readPointer();
                    if (!catObj.isNull()) {
                        nativeMossSelectCat(mossWin, catObj, ptr(0));
                    }
                }
            } catch (eCat) {}
        }

        // 4. Đảm bảo nút quay sẵn sàng và LoadingImage tắt
        ensureMossRollButtonActive(mossWin, true);

        // 5. Hiển thị cửa sổ (MWindow tại offset 0x20)
        var win = mossWin.add(0x20).readPointer();
        if (!win.isNull()) {
            if (nativeWindowShow !== null) {
                try { nativeWindowShow(win, ptr(0)); } catch (eWS) {}
            } else if (nativeWindowSetState !== null) {
                try { nativeWindowSetState(win, 1, ptr(0)); } catch (eWSS) {}
            }
            win.add(0x48).writeU8(1);
        }
        if (nativeComponentGetGameObject !== null && nativeGameObjectSetActive !== null) {
            try {
                var mGo = nativeComponentGetGameObject(mossWin);
                if (!mGo.isNull() && isGameObjectValid(mGo)) {
                    nativeGameObjectSetActive(mGo, 1, ptr(0));
                }
            } catch (eMGO) {}
        }
        return true;
    } catch (eSetup) {
        return false;
    }
}

function findMossNpc() {
    try {
        var localPlayer = getPlayerPtr();
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

            // Bỏ qua chính bản thân nhân vật người chơi
            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;

            var bIdx = body.add(0x20).readS32();
            if (bIdx < 0) continue;

            var npcType = -1;
            try { npcType = body.add(0x34).readS32(); } catch (eT) {}

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
            } else if (npcType === 492) {
                isMoss = true;
            } else if (tx >= 20 && tx <= 26 && ty >= 222 && ty <= 228) {
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

function getNpcManagerPtr() {
    try {
        var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
        if (typeInfo.isNull()) return ptr(0);
        var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
        if (staticFields.isNull()) return ptr(0);
        var gameInstance = staticFields.add(ptr('0x8')).readPointer();
        if (gameInstance.isNull()) return ptr(0);
        return gameInstance.add(ptr('0x120')).readPointer();
    } catch (eNM) {
        return ptr(0);
    }
}

function findLugardNpc() {
    try {
        var localPlayer = getPlayerPtr();
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

            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;

            var npcType = -1;
            try { npcType = body.add(0x34).readS32(); } catch (eT) {}

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

            var lowName = (name || "").toLowerCase();
            // NPC Lugard ID: 723 (Event Square), 540 (Elbeland)
            // Tọa độ Lugard: Event Square (229, 22), Elbeland (49, 216)
            var isLugard = false;
            if (npcType === 723 || npcType === 540) {
                isLugard = true;
            } else if (lowName.indexOf("lugard") !== -1 || lowName.indexOf("doppel") !== -1 || lowName.indexOf("mirror") !== -1 || lowName.indexOf("espelho") !== -1) {
                isLugard = true;
            } else if ((tx >= 226 && tx <= 232 && ty >= 19 && ty <= 25) || (tx >= 46 && tx <= 52 && ty >= 213 && ty <= 219)) {
                isLugard = true;
            }

            if (isLugard) {
                return body;
            }
        }
    } catch (eLugard) {}
    return null;
}

var _syntheticLugardPtr = null;
function getOrCreateLugardPtr(npcPtr) {
    if (npcPtr && npcPtr !== 0 && !ptr(npcPtr).isNull()) {
        return ptr(npcPtr);
    }
    var lugard = findLugardNpc();
    if (lugard && !lugard.isNull()) {
        return lugard;
    }
    if (_syntheticLugardPtr === null) {
        // Cấu trúc Mega.Body tối thiểu cho NPC Lugard Event Square (ID: 723):
        // +0x20: npcKey / index = 723 (để Mega.NpcManager.Talk 0xF8D320 ghi vào packet C1:05:32)
        // +0x34: npcType = 723 (để Mega.DoubleGoer.ILAIHGMFEGF 0xEFDE60 nhận diện đúng Lugard Event Square)
        _syntheticLugardPtr = Memory.alloc(0x100);
        _syntheticLugardPtr.add(0x20).writeS32(723);
        _syntheticLugardPtr.add(0x34).writeS32(723);
    }
    return _syntheticLugardPtr;
}

function findCharonNpc() {
    try {
        var localPlayer = getPlayerPtr();
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

            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;

            var npcType = -1;
            try { npcType = body.add(0x34).readS32(); } catch (eT) {}

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

            var lowName = (name || "").toLowerCase();
            // NPC Charon ID: 236 (Noria/Chuẩn), 237, 720 (Event Square)
            // Tọa độ Charon: Event Square (225, 52), Noria (171, 105)
            var isCharon = false;
            if (npcType === 236 || npcType === 237 || npcType === 720) {
                isCharon = true;
            } else if (lowName.indexOf("charon") !== -1 || lowName.indexOf("devil") !== -1) {
                isCharon = true;
            } else if ((tx >= 222 && tx <= 228 && ty >= 49 && ty <= 55) || (tx >= 168 && tx <= 174 && ty >= 102 && ty <= 108)) {
                isCharon = true;
            }

            if (isCharon) {
                return body;
            }
        }
    } catch (eCharon) {}
    return null;
}

var _syntheticCharonPtr = null;
function getOrCreateCharonPtr(npcPtr) {
    if (npcPtr && npcPtr !== 0 && !ptr(npcPtr).isNull()) {
        return ptr(npcPtr);
    }
    var charon = findCharonNpc();
    if (charon && !charon.isNull()) {
        return charon;
    }
    if (_syntheticCharonPtr === null) {
        // Cấu trúc Mega.Body tối thiểu cho NPC Charon Event Square (ID: 720 / 0x2D0):
        // +0x20: npcKey / index = 720 (để Mega.NpcManager.Talk 0xF8D320 ghi vào packet C1:05:32)
        // +0x34: npcType = 720 (0x2D0) (để Mega.DevilSquare.ILAIHGMFEGF 0xEFA3D0 nhận diện đúng Charon Event Square)
        _syntheticCharonPtr = Memory.alloc(0x100);
        _syntheticCharonPtr.add(0x20).writeS32(720);
        _syntheticCharonPtr.add(0x34).writeS32(720);
    }
    return _syntheticCharonPtr;
}

function checkDevilItem(itemPtr, idx) {
    var trueIdx = (idx !== undefined && idx !== null && idx > 0) ? idx : readItemIndex(itemPtr);
    var itName = getItemName(itemPtr) || "";
    var lowName = itName.toLowerCase();
    var itLevel = 0;
    try { itLevel = itemPtr.add(0x10).readS32(); } catch (eL) {}

    // 1. Nhận diện theo ID: 7187 (0x1C13 - Devil's Invitation thường 1..7) hoặc 6702 (0x1A2E - Master Ticket)
    if (trueIdx === 7187 || trueIdx === 6702) {
        var isMaster = (trueIdx === 6702);
        return {
            isTicket: true,
            isMaster: isMaster,
            level: itLevel,
            name: itName || (isMaster ? "Master Devil's Invitation" : ("Devil's Invitation +" + itLevel))
        };
    }

    // 2. Nhận diện theo Tên (tiếng Anh & tiếng Bồ Đào Nha MEGAMU)
    if (lowName.length > 0) {
        if (lowName.indexOf("devil's invitation") !== -1 ||
            lowName.indexOf("devil invitation") !== -1 ||
            lowName.indexOf("convite do diabo") !== -1 ||
            lowName.indexOf("convite devil") !== -1 ||
            lowName.indexOf("devil square ticket") !== -1 ||
            (lowName.indexOf("devil") !== -1 && lowName.indexOf("invit") !== -1) ||
            (lowName.indexOf("diabo") !== -1 && lowName.indexOf("convite") !== -1)) {
            var isM = (lowName.indexOf("master") !== -1 || trueIdx === 6702);
            return { isTicket: true, isMaster: isM, level: itLevel, name: itName };
        }
    }
    return { isTicket: false, isMaster: false, level: 0, name: itName };
}

function getPlayerDevilSquareLevel() {
    try {
        var p = getPlayerPtr();
        if (p.isNull()) return 0;
        var lvl = p.add(off('__PLAYER_LEVEL__')).readS32();
        var cls = p.add(off('__PLAYER_CLASS__')).readS32();
        var isSpecial = (cls >= 48 && cls <= 67);
        if (lvl >= 400) return 6; // DS 7
        if (isSpecial) {
            if (lvl <= 110) return 0; // DS 1
            if (lvl <= 160) return 1; // DS 2
            if (lvl <= 210) return 2; // DS 3
            if (lvl <= 260) return 3; // DS 4
            if (lvl <= 310) return 4; // DS 5
            return 5;                 // DS 6
        } else {
            if (lvl <= 130) return 0; // DS 1
            if (lvl <= 180) return 1; // DS 2
            if (lvl <= 230) return 2; // DS 3
            if (lvl <= 280) return 3; // DS 4
            if (lvl <= 330) return 4; // DS 5
            return 5;                 // DS 6
        }
    } catch (e) {
        return 0;
    }
}

function findMerchantNpc() {
    try {
        var localPlayer = getPlayerPtr();
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

        var px = 0, py = 0;
        try {
            if (!localPlayer.isNull()) {
                var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                if (!pCoord.isNull()) {
                    px = pCoord.add(0x10).readS32();
                    py = pCoord.add(0x14).readS32();
                }
            }
        } catch (eP) {}

        var bestNpc = null;
        var bestDist = 999999;

        for (var i = 0; i < count; i++) {
            var entryAddr = entries.add(0x20 + i * 24);
            var val = entryAddr.add(16).readPointer();
            if (val.isNull()) continue;
            var body = val.add(ptr('0x18')).readPointer();
            if (body.isNull()) continue;

            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;

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

            // Tuyệt đối loại bỏ mọi NPC / vật thể quanh bệ Moss (20..26, 222..228)
            if (tx >= 20 && tx <= 26 && ty >= 222 && ty <= 228) continue;
            var lowerName = (name || "").toLowerCase();
            if (lowerName.indexOf('moss') !== -1) continue;

            var isMerchant = false;
            // 1. Nhận diện theo tên NPC thương nhân (Rhea Elbeland, Leah, Silvia, Merchant, Potion...)
            if (lowerName.indexOf('rhea') !== -1 || lowerName.indexOf('leah') !== -1 || lowerName.indexOf('lia') !== -1 ||
                lowerName.indexOf('silvia') !== -1 || lowerName.indexOf('merchant') !== -1 ||
                lowerName.indexOf('potion') !== -1 || lowerName.indexOf('tạp hóa') !== -1 ||
                lowerName.indexOf('thuốc') !== -1 || lowerName.indexOf('thương nhân') !== -1 ||
                lowerName.indexOf('poção') !== -1 || lowerName.indexOf('pocion') !== -1) {
                isMerchant = true;
            }
            // 2. Nhận diện theo tọa độ Rhea Elbeland (28..31, 233..237) hoặc Leah/Silvia
            else if ((tx >= 27 && tx <= 31 && ty >= 233 && ty <= 237) ||
                     (tx >= 35 && tx <= 40 && ty >= 234 && ty <= 239) ||
                     (tx >= 42 && tx <= 47 && ty >= 227 && ty <= 232)) {
                isMerchant = true;
            }
            // 3. Nếu nhân vật đã đứng gần khu vực chợ (px >= 27 && px <= 48 && py >= 225 && py <= 242) và đứng cạnh NPC (<= 3 ô)
            else if (px >= 27 && px <= 48 && py >= 225 && py <= 242 && Math.abs(tx - px) <= 3 && Math.abs(ty - py) <= 3) {
                isMerchant = true;
            }

            if (isMerchant) {
                // Ưu tiên NPC gần tọa độ Rhea (29, 235) nhất
                var dist = Math.abs(tx - 29) + Math.abs(ty - 235);
                if (dist < bestDist) {
                    bestDist = dist;
                    bestNpc = {
                        ptr: body,
                        index: bIdx,
                        name: name || "Merchant Rhea",
                        x: tx,
                        y: ty
                    };
                }
            }
        }
        return bestNpc;
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

                        if (pendingMossInteractPtr !== null) {
                            try {
                                var nPtr = pendingMossInteractPtr;
                                pendingMossInteractPtr = null;
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (eCT) {}
                                }
                                if (nativeNpcTalk !== null && !nPtr.isNull()) {
                                    nativeNpcTalk(nPtr, ptr(0));
                                }
                            } catch (eMossNT) {}
                        }

                        if (pendingMerchantInteractPtr !== null) {
                            try {
                                var mPtr = pendingMerchantInteractPtr;
                                pendingMerchantInteractPtr = null;
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (eCTM) {}
                                }
                                if (nativeNpcTalk !== null && !mPtr.isNull()) {
                                    nativeNpcTalk(mPtr, ptr(0));
                                }
                            } catch (eNTM) {}
                        }

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
                        pendingHelperAction = null;
                        try { dispatchHelperAction(hAct); } catch (eH2) {}
                    }
                } catch (eGUIEnter) {}
            }
        });
    }
} catch (eGUIHook) {}

var gameUpdateHook = null;
var pendingAutoLogin = null;
var autoLoginLastStatus = { done: false, submitted: false, stage: "idle" };
var helperSyncCounter = 0;

try {
    var guOff = off('__GAME_UPDATE__');
    if (!guOff.isNull()) {
        gameUpdateHook = Interceptor.attach(baseAddr.add(guOff), {
            onEnter: function(args) {
                if (shuttingDown) return;

                // 1. Luôn ưu tiên xử lý lệnh Helper Toggle & Chat trên vòng lặp Game.Update chính
                // Đảm bảo chạy 60 FPS liên tục kể cả khi game đang chạy ngầm, không cần user phải click chuột vào game!
                if (pendingHelperAction !== null) {
                    var hAct = pendingHelperAction;
                    pendingHelperAction = null;
                    try { dispatchHelperAction(hAct); } catch (eHGU) {}
                }

                helperSyncCounter = (helperSyncCounter || 0) + 1;
                if (helperSyncCounter >= 30) {
                    helperSyncCounter = 0;
                    try {
                        var pHS = getPlayerPtr();
                        if (!pHS.isNull()) {
                            var hPtr = pHS.add(off('__PLAYER_HELPER__')).readPointer();
                            if (!hPtr.isNull()) {
                                var curAct = hPtr.add(off('__HELPER_STATE__')).readU8();
                                syncHelperUI(curAct === 1);
                            }
                        }
                    } catch (eHAutoSync) {}
                }

                if (pendingCommand !== null) {
                    var cmd = pendingCommand;
                    pendingCommand = null;
                    try { dispatchChatMessage(cmd); } catch (eCGU) {}
                }

                if (pendingAutoLogin === null) return;
                try {
                    var pal = pendingAutoLogin;
                    if (!pal || pal.done) return;

                    pal.frames++;

                    // 1. Luôn cấu hình AutoLogin singleton nếu có
                    var autoLogin = null;
                    if (nativeGetAutoLogin !== null) {
                        try { autoLogin = nativeGetAutoLogin(); } catch (eG) {}
                    }
                    if (autoLogin !== null && !autoLogin.isNull()) {
                        try {
                            var accStr = il2cpp_string_new(Memory.allocUtf8String(pal.account));
                            var chrStr = il2cpp_string_new(Memory.allocUtf8String(pal.character));
                            if (nativeSetAutoLogin !== null) {
                                try { nativeSetAutoLogin(autoLogin, pal.server, accStr, chrStr); } catch (eSet) {}
                            }
                            autoLogin.add(0x20).writeU8(0);
                            autoLogin.add(0x21).writeU8(0);
                            autoLogin.add(0x22).writeU8(0);
                            autoLogin.add(0x23).writeU8(0);
                            autoLogin.add(0x24).writeS32(pal.server);
                            autoLogin.add(0x28).writePointer(accStr);
                            autoLogin.add(0x30).writePointer(chrStr);
                        } catch (eAL) {}
                    }

                    // 2. Tìm MLoginUI.Instance
                    var mLoginInst = null;
                    try {
                        var mTypeOff = off('__MLOGIN_UI_TYPE_INFO__');
                        if (!mTypeOff.isNull()) {
                            var mType = baseAddr.add(mTypeOff).readPointer();
                            if (!mType.isNull()) {
                                var sf = mType.add(0xB8).readPointer();
                                if (!sf.isNull()) {
                                    mLoginInst = sf.readPointer();
                                }
                            }
                        }
                    } catch (eType) {}

                    // Nếu MLoginUI.Instance đã tồn tại (Game đã vào màn hình Login!):
                    if (mLoginInst !== null && !mLoginInst.isNull()) {
                        var accStr = il2cpp_string_new(Memory.allocUtf8String(pal.account));

                        if (pal.password && nativeMLoginSubmit !== null) {
                            var pwdStr = il2cpp_string_new(Memory.allocUtf8String(pal.password));
                            nativeMLoginSubmit(mLoginInst, accStr, pwdStr, 1, ptr(0));
                            pal.done = true;
                            pal.submitted = true;
                            autoLoginLastStatus = { done: true, submitted: true, stage: "submitted_password", account: pal.account };
                            send({ type: "autologin_status", ok: true, stage: "submitted_password", account: pal.account });
                            pendingAutoLogin = null;
                            return;
                        } else if (!pal.password && nativeMLoginTokenLogin !== null) {
                            nativeMLoginTokenLogin(mLoginInst, accStr, ptr(0));
                            pal.done = true;
                            pal.submitted = true;
                            autoLoginLastStatus = { done: true, submitted: true, stage: "submitted_token", account: pal.account };
                            send({ type: "autologin_status", ok: true, stage: "submitted_token", account: pal.account });
                            pendingAutoLogin = null;
                            return;
                        } else {
                            pal.done = true;
                            pal.submitted = true;
                            autoLoginLastStatus = { done: true, submitted: true, stage: "configured_autologin", account: pal.account };
                            send({ type: "autologin_status", ok: true, stage: "configured_autologin", account: pal.account });
                            pendingAutoLogin = null;
                            return;
                        }
                    }

                    autoLoginLastStatus = { done: false, submitted: false, stage: "waiting_login_screen", frames: pal.frames, account: pal.account };

                    if (pal.frames % 60 === 0) {
                        send({ type: "autologin_status", ok: false, stage: "waiting_login_screen", frames: pal.frames, account: pal.account });
                    }

                    if (pal.frames > 1800) {
                        autoLoginLastStatus = { done: true, submitted: false, stage: "timeout", account: pal.account };
                        send({ type: "autologin_status", ok: false, stage: "timeout", account: pal.account });
                        pendingAutoLogin = null;
                    }
                } catch (eGU) {}
            }
        });
    }
} catch (eHookGU) {}

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

        var points = 0, masterPoints = 0;
        try {
            var ptOff = off('__PLAYER_POINT__');
            if (!ptOff.isNull()) {
                points = p.add(ptOff).readS32();
            }
        } catch (ePts) {}
        try {
            var mptOff = off('__PLAYER_MASTER_POINT__');
            if (!mptOff.isNull()) {
                masterPoints = p.add(mptOff).readS32();
            }
        } catch (eMpts) {}

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
            helperState: helperState,
            points: (points > 0 ? points : 0),
            masterPoints: (masterPoints > 0 ? masterPoints : 0)
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
        var sig = [info.level, info.mapId, info.tileX, info.tileY, info.isMoving ? 1 : 0, info.helperState, info.points || 0].join('|');
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

var _nativeMirrorTurboTimer = null;
var _nativeMirrorTurboStats = { running: false, packetsSent: 0, startTime: 0, durationMs: 0, activeSlot: -1, relSlot: -1, entered: false };

rpc.exports = {
    getPlayerInfo: function() {
        return readPlayerInfoSnapshot(true);
    },

    moveTo: function(targetX, targetY) {
        try {
            ensureThreadAttached();
            pendingMoveTarget = { x: parseInt(targetX), y: parseInt(targetY), helper: false };
            return true;
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
            var isA = parseInt(val) ? 1 : 0;
            h.add(off('__HELPER_STATE__')).writeU8(isA);
            try { syncHelperUI(isA === 1); } catch (eSync) {}
            return true;
        } catch (e) {
            return false;
        }
    },

    sendChatNative: function(cmd) {
        try {
            cmd = String(cmd || '').trim();
            if (!cmd) return false;
            ensureThreadAttached();
            var ok = dispatchChatMessage(cmd);
            if (!ok) {
                pendingCommand = cmd;
            }
            return true;
        } catch (e) {
            return false;
        }
    },

    send_chat_native: function(cmd) {
        return this.sendChatNative(cmd);
    },

    startHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = 'start';
            try { dispatchHelperAction('start'); } catch (eD1) {}
            return true;
        } catch (eH) {}
        return false;
    },

    stopHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = 'stop';
            try { dispatchHelperAction('stop'); } catch (eD2) {}
            return true;
        } catch (eH) {}
        return false;
    },

    toggleHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = 'toggle';
            try { dispatchHelperAction('toggle'); } catch (eD3) {}
            return true;
        } catch (eT) {}
        return false;
    },

    syncHelperUI: function(active) {
        try {
            ensureThreadAttached();
            syncHelperUI(Boolean(active));
            return true;
        } catch (eS) {}
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

                // Đưa bước di chuyển khởi hành vào hàng đợi Unity Main Thread Hook để thực thi an toàn tuyệt đối, tránh crash
                pendingMoveTarget = { x: parseInt(x), y: parseInt(y), helper: Boolean(helper) };
                return true;
            } else {
                pendingMoveTarget = { x: parseInt(x), y: parseInt(y), helper: Boolean(helper) };
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

    isMossOpen: function() {
        try {
            ensureThreadAttached();
            if (nativeGetGameUI === null) return false;
            var gui = nativeGetGameUI();
            if (gui.isNull()) return false;
            var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
            if (mossWin.isNull()) return false;
            var win = mossWin.add(0x20).readPointer();
            if (win.isNull()) return false;
            return win.add(0x48).readU8() === 1;
        } catch (e) {
            return false;
        }
    },

    isMossReady: function() {
        try {
            ensureThreadAttached();
            if (nativeGetGameUI === null) return false;
            var gui = nativeGetGameUI();
            if (gui.isNull()) return false;
            var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
            if (mossWin.isNull()) return false;
            var win = mossWin.add(0x20).readPointer();
            if (win.isNull()) return false;
            if (win.add(0x48).readU8() !== 1) return false;
            var catList = mossWin.add(0x80).readPointer();
            if (catList.isNull()) return false;
            var count = catList.add(0x18).readS32();
            return count > 0;
        } catch (e) {
            return false;
        }
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
                        // A. Đảm bảo InventoryWindow mở sẵn (offset 0x188 / 0x20)
                        try {
                            var invWin = gui.add(ptr('0x188')).readPointer();
                            if (!invWin.isNull()) {
                                var invMWin = invWin.add(0x20).readPointer();
                                if (!invMWin.isNull() && invMWin.add(0x48).readU8() === 0) {
                                    if (nativeWindowShow !== null) {
                                        try { nativeWindowShow(invMWin, ptr(0)); } catch (eIS) {}
                                    }
                                    invMWin.add(0x48).writeU8(1);
                                }
                            }
                        } catch (eInv) {}

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

                        // 3. GỬI LỆNH QUAY:
                        // Ưu tiên 1: Gửi qua Native Packet RPC trực tiếp (MossMerchantWindow.PPGKJNECJHO - RVA 0x238B780)
                        var sent = false;
                        if (nativeMossSendRoll !== null) {
                            try {
                                nativeMossSendRoll(cat);
                                sent = true;
                            } catch (eSend) {}
                        }

                        // Ưu tiên 2: Fallback qua OnClick của RollButton (MMossMerchantWindow.HHHGKHKLGHB - RVA 0x2791220)
                        if (!sent && nativeMossRollClick !== null) {
                            try {
                                nativeMossRollClick(mossWin, ptr(0));
                                sent = true;
                            } catch (eRC) {}
                        }

                        // 4. Kích hoạt hiệu ứng LoadingImage quay mượt mà trên giao diện
                        try {
                            var loadingImg = mossWin.add(0x60).readPointer();
                            if (!loadingImg.isNull() && isGameObjectValid(loadingImg) && nativeGameObjectSetActive !== null) {
                                nativeGameObjectSetActive(loadingImg, 1, ptr(0));
                            }
                        } catch (eLI) {}

                        return sent;
                    }
                }
            }
            return false;
        } catch (eMR) {
            return false;
        }
    },

    closeMoss: function() {
        try {
            ensureThreadAttached();
            pendingMossOpenCategory = null;

            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (!gui.isNull()) {
                    var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                    if (!mossWin.isNull()) {
                        // 1. Gọi hàm đóng chuẩn của MMossMerchantWindow (RVA 0x27911E0)
                        if (nativeMossWindowClose !== null) {
                            try { nativeMossWindowClose(mossWin, ptr(0)); } catch (eMWC) {}
                        }

                        // 2. Ẩn MWindow tại offset 0x20
                        var win = mossWin.add(0x20).readPointer();
                        if (!win.isNull()) {
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(win, ptr(0)); } catch (eWH) {}
                            } else if (nativeWindowSetState !== null) {
                                try { nativeWindowSetState(win, 0, ptr(0)); } catch (eWSS) {}
                            }
                            win.add(0x48).writeU8(0);
                            if (nativeComponentGetGameObject !== null && nativeGameObjectSetActive !== null) {
                                try {
                                    var wGo = nativeComponentGetGameObject(win);
                                    if (!wGo.isNull() && isGameObjectValid(wGo)) {
                                        nativeGameObjectSetActive(wGo, 0, ptr(0));
                                    }
                                } catch (eWGO) {}
                            }
                        }

                        // 3. Tắt GameObject của MMossMerchantWindow
                        if (nativeComponentGetGameObject !== null && nativeGameObjectSetActive !== null) {
                            try {
                                var mGo = nativeComponentGetGameObject(mossWin);
                                if (!mGo.isNull() && isGameObjectValid(mGo)) {
                                    nativeGameObjectSetActive(mGo, 0, ptr(0));
                                }
                            } catch (eMGO) {}
                        }
                    }
                }
            }

            // 4. Gửi packet C1:31 đóng phiên đàm thoại NPC
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }

            return true;
        } catch (eCM) {
            return false;
        }
    },

    openMoss: function(categoryId) {
        try {
            ensureThreadAttached();
            var cat = parseInt(categoryId || 0);
            var npc = findMossNpc();
            if (npc && !npc.ptr.isNull()) {
                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT) {}
                }
                if (nativeNpcTalk !== null) {
                    nativeNpcTalk(npc.ptr, ptr(0));
                }
            }
            pendingMossOpenCategory = cat;
            return true;
        } catch (eMO) {
            return false;
        }
    },

    resetMossUI: function(categoryId) {
        try {
            ensureThreadAttached();
            var cat = parseInt(categoryId || 0);
            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (!gui.isNull()) {
                    var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                    if (!mossWin.isNull()) {
                        setupMossWindow(mossWin, cat);
                        ensureMossRollButtonActive(mossWin, true);
                        return true;
                    }
                }
            }
            return false;
        } catch (e) {
            return false;
        }
    },

    getMossCategories: function() {
        try {
            ensureThreadAttached();
            var categories = [];
            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (!gui.isNull()) {
                    var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                    if (!mossWin.isNull()) {
                        var catList = mossWin.add(0x80).readPointer();
                        if (!catList.isNull()) {
                            var size = catList.add(0x18).readS32();
                            var itemsArr = catList.add(0x10).readPointer();
                            if (!itemsArr.isNull() && size > 0 && size < 50) {
                                for (var i = 0; i < size; i++) {
                                    var itemPtr = itemsArr.add(0x20 + i * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var catName = "";
                                        try {
                                            var namePtr = itemPtr.add(0x18).readPointer();
                                            if (!namePtr.isNull()) {
                                                var nLen = namePtr.add(0x10).readS32();
                                                if (nLen > 0 && nLen < 100) {
                                                    catName = namePtr.add(0x14).readUtf16String(nLen);
                                                }
                                            }
                                        } catch (eN) {}
                                        var trueId = i;
                                        try {
                                            var rawId = itemPtr.add(0x10).readS32();
                                            if (rawId >= 0 && rawId < 1000) trueId = rawId;
                                        } catch (eId) {}
                                        var reqType = 0;
                                        try { reqType = itemPtr.add(0x24).readS32(); } catch (eR) {}
                                        var reqCount = 0;
                                        try { reqCount = itemPtr.add(0x28).readS32(); } catch (eC) {}
                                        var isActive = false;
                                        try { isActive = itemPtr.add(0x20).readU8() === 1; } catch (eA) {}

                                        var curName = "Zen";
                                        if (reqType === 7183 || reqType === -1) {
                                            curName = "Zen";
                                        } else if (reqType === 7181) {
                                            curName = "Bless";
                                        } else if (reqType === 7182) {
                                            curName = "Soul";
                                        } else if (reqType === 7184) {
                                            curName = "Chaos";
                                        } else if (reqType === 7190) {
                                            curName = "Life";
                                        } else {
                                            curName = "Item #" + reqType;
                                        }

                                        categories.push({
                                            id: trueId,
                                            name: catName || ("Category " + trueId),
                                            active: isActive,
                                            reqType: reqType,
                                            currency: curName,
                                            reqCount: reqCount
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
            return JSON.stringify({ ok: true, categories: categories });
        } catch (e) {
            return JSON.stringify({ ok: false, error: e.toString(), categories: [] });
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

            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            if (nativeNpcTalk !== null && !npc.ptr.isNull()) {
                nativeNpcTalk(npc.ptr, ptr(0));
            }

            pendingMossOpenCategory = cat;

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

    findMerchantNpc: function() {
        try {
            ensureThreadAttached();
            var npc = findMerchantNpc();
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

    interactMerchantNpc: function() {
        try {
            ensureThreadAttached();
            var npc = findMerchantNpc();
            if (!npc) {
                return { success: false, error: "MERCHANT_NOT_FOUND" };
            }

            // Xếp hàng tương tác thương nhân trên Unity Main Thread trong guiHook
            pendingMerchantInteractPtr = npc.ptr;

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

    closeMerchantNpc: function() {
        try {
            ensureThreadAttached();
            // 1. Gửi packet C1:31 đóng đối thoại NPC
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            // 2. Tắt cửa sổ MerchantWindow trong UI qua nativeWindowHide chuẩn
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var merchOff = off('__UI_MERCHANT_WINDOW__');
                        var mWinPtr = merchOff.isNull() ? gui.add(ptr('0x198')).readPointer() : gui.add(merchOff).readPointer();
                        if (!mWinPtr.isNull()) {
                            var mwObj = mWinPtr.add(0x20).readPointer();
                            if (!mwObj.isNull()) {
                                if (nativeWindowHide !== null) {
                                    try { nativeWindowHide(mwObj, ptr(0)); } catch (eWH) {}
                                } else if (nativeWindowSetState !== null) {
                                    try { nativeWindowSetState(mwObj, 0, ptr(0)); } catch (eWSS) {}
                                }
                            }
                        }
                    }
                }
            } catch (eMerchClose) {}
            return { success: true };
        } catch (e) {
            return { success: false, error: e.toString() };
        }
    },

    sellMossPlusItems: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return JSON.stringify({ sold: 0, error: "no_player" });

            var invOff = off('__PLAYER_INVENTORY__');
            var inv = p.add(invOff).readPointer();
            if (inv.isNull()) return JSON.stringify({ sold: 0, error: "no_inventory" });

            var itemsOff = off('__INVENTORY_ITEMS__');
            var itemsArr = inv.add(itemsOff).readPointer();
            if (itemsArr.isNull()) return JSON.stringify({ sold: 0, error: "no_items_arr" });

            if (nativeInvSellItem === null && nativeGetGS === null && nativeSlotQuickAction === null) {
                return JSON.stringify({ sold: 0, error: "no_native_sell_fn" });
            }

            var maxSlot = 140;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            var sold = 0;
            var soldItems = [];
            var candidatesCount = 0;

            // 1. Quản lý static fields của ItemStorage (SellingSlot tại 0x20)
            var itemStorageStatic = ptr(0);
            try {
                var isTypeInfoOff = off('__ITEM_STORAGE_TYPE_INFO__');
                if (!isTypeInfoOff.isNull()) {
                    var isTypeInfo = baseAddr.add(isTypeInfoOff).readPointer();
                    if (!isTypeInfo.isNull()) {
                        itemStorageStatic = isTypeInfo.add(0xB8).readPointer();
                    }
                }
            } catch (eIST) {}

            // 2. Tìm MainStorage trong InventoryWindow và MerchantWindow
            var mainStorage = ptr(0);
            var mWinPtr = ptr(0);
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var invWin = gui.add(ptr('0x188')).readPointer();
                        if (!invWin.isNull()) {
                            mainStorage = invWin.add(ptr('0x58')).readPointer();
                        }
                        var merchOff = off('__UI_MERCHANT_WINDOW__');
                        mWinPtr = merchOff.isNull() ? gui.add(ptr('0x198')).readPointer() : gui.add(merchOff).readPointer();
                    }
                }
            } catch (eUI) {}

            // 3. Đảm bảo cửa sổ MerchantWindow luôn active và không bị chặn bởi popup ExpensiveSellWindow
            function dismissExpensiveSellWindow() {
                try {
                    if (!mWinPtr.isNull()) {
                        var mwObj = mWinPtr.add(0x20).readPointer();
                        if (!mwObj.isNull()) {
                            mwObj.add(0x48).writeU8(1); // Đảm bảo trạng thái Open
                        }
                        var expWin = mWinPtr.add(0x68).readPointer();
                        if (!expWin.isNull()) {
                            expWin.add(0x48).writeU8(0); // Tắt popup cảnh báo đắt tiền
                        }
                    }
                } catch (eExp) {}
            }

            for (var s = 12; s < maxSlot; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x2C).readS32();
                var sec = Math.floor(itemIndex / 512);

                // BẢO VỆ TUYỆT ĐỐI (Không bao giờ bán):
                // 1. Đồ Divine, Đồ Rồng (isDivineOrDragonItem)
                // 2. Đồ Hoàn Hảo (excOpt > 0)
                // 3. Đồ Thần (ancOpt > 0)
                // 4. Đồ Socket (sockOpt > 0)
                // 5. Cấp độ >= +8 (giữ lại đồ xịn +8 trở lên)
                // 6. Toàn bộ ngọc, vé sự kiện, cánh, sách phép (sec >= 12 && sec <= 15)
                if (isDivineOrDragonItem(itemPtr, itemIndex)) continue;
                if (excOpt > 0 || ancOpt > 0 || sockOpt > 0) continue;
                if (sec >= 12 && sec <= 15) continue;
                if (itemLevel > 7) continue; // BÁN TOÀN BỘ ĐỒ RÁC THƯỜNG TỪ +0 ĐẾN +7!

                candidatesCount++;
                var itName = getItemName(itemPtr);

                // 1. Tìm slotObj tương ứng trong MainStorage
                var slotObj = ptr(0);
                if (!mainStorage.isNull()) {
                    try {
                        var cellsDict = mainStorage.add(ptr('0x38')).readPointer();
                        if (!cellsDict.isNull()) {
                            var entriesPtr = cellsDict.add(ptr('0x18')).readPointer();
                            var cCount = cellsDict.add(ptr('0x20')).readS32();
                            for (var ci = 0; ci < cCount; ci++) {
                                var cEntry = entriesPtr.add(0x20 + ci * 24);
                                var cKey = cEntry.add(0x10).readS32();
                                if (cKey === s) {
                                    slotObj = cEntry.add(0x18).readPointer();
                                    break;
                                }
                            }
                        }
                    } catch (eSlotFind) {}
                }

                // 2. Gán SellingSlot trước khi gửi lệnh bán để Client xử lý mượt mà khi Server phản hồi
                if (!itemStorageStatic.isNull() && !slotObj.isNull()) {
                    try {
                        itemStorageStatic.add(0x20).writePointer(slotObj);
                    } catch (eSetSelling) {}
                }

                dismissExpensiveSellWindow();

                var soldSuccess = false;
                try {
                    // PHƯƠNG ÁN 1 (Chuẩn nhất): Slot Quick Action (Mô phỏng click chuột phải ô đồ khi mở shop)
                    if (nativeSlotQuickAction !== null && !slotObj.isNull()) {
                        nativeSlotQuickAction(slotObj, ptr(0));
                        try { Thread.sleep(0.12); } catch (eSleep1) {}
                        dismissExpensiveSellWindow();
                        var verifyPtr1 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (verifyPtr1.isNull() || !verifyPtr1.equals(itemPtr)) {
                            soldSuccess = true;
                        }
                    }

                    // PHƯƠNG ÁN 2: Gọi trực tiếp MMerchantWindow.DCIOGINKECD
                    if (!soldSuccess && nativeMerchantSellItem !== null && !mWinPtr.isNull()) {
                        nativeMerchantSellItem(mWinPtr, s, itemPtr, ptr(0));
                        try { Thread.sleep(0.12); } catch (eSleep2) {}
                        dismissExpensiveSellWindow();
                        var verifyPtr2 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (verifyPtr2.isNull() || !verifyPtr2.equals(itemPtr)) {
                            soldSuccess = true;
                        }
                    }

                    // PHƯƠNG ÁN 3: Gửi trực tiếp packet GS C1:33 (Chuẩn protocol bán đồ vào shop MEGAMU)
                    if (!soldSuccess) {
                        sendSellPacket(s);
                        try { Thread.sleep(0.10); } catch (eSleepPkt) {}
                        dismissExpensiveSellWindow();
                        var verifyPkt = itemsArr.add(0x20 + s * 8).readPointer();
                        if (verifyPkt.isNull() || !verifyPkt.equals(itemPtr)) {
                            soldSuccess = true;
                        }
                    }
                } catch (eSell) {}

                if (soldSuccess) {
                    sold++;
                    soldItems.push({ slot: s, name: itName || ("Item " + itemIndex), level: itemLevel });
                }
            }

            return JSON.stringify({
                sold: sold,
                items: soldItems,
                candidates: candidatesCount,
                error: (sold === 0 && candidatesCount > 0) ? "server_not_confirm" : null
            });
        } catch (e) {
            return JSON.stringify({ sold: 0, error: e.toString() });
        }
    },

    startNativeMirrorTurbo: function(slot, intervalMs, maxDurationMs) {
        try {
            ensureThreadAttached();
            if (_nativeMirrorTurboTimer !== null) {
                clearInterval(_nativeMirrorTurboTimer);
                _nativeMirrorTurboTimer = null;
            }
            var itemSlot = -1;
            if (slot !== undefined && slot !== null && parseInt(slot) >= 0) {
                itemSlot = parseInt(slot);
            } else {
                try {
                    var p = getPlayerPtr();
                    if (!p.isNull()) {
                        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                        if (!inv.isNull()) {
                            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                            if (!itemsArr.isNull()) {
                                var maxSlot = 140;
                                try {
                                    var arrLen = itemsArr.add(0x18).readS32();
                                    if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
                                } catch (eLen) {}
                                var mainTicketSlot = -1;
                                var extTicketSlot = -1;
                                for (var s = 12; s < maxSlot; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = readItemIndex(itemPtr);
                                        var check = checkMirrorItem(itemPtr, idx);
                                        if (check.isTicket) {
                                            if (s < 76 && mainTicketSlot < 0) mainTicketSlot = s;
                                            else if (s >= 76 && extTicketSlot < 0) extTicketSlot = s;
                                        }
                                    }
                                }
                                itemSlot = (mainTicketSlot >= 12) ? mainTicketSlot : extTicketSlot;
                            }
                        }
                    }
                } catch (eScan) {}
            }

            // Đóng bất kỳ cửa sổ đối thoại NPC nào đang mở để tránh bị modal chặn thao tác
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }

            var pLugard = getOrCreateLugardPtr(0);

            if (itemSlot < 0) {
                if (nativeMirrorNpcClick !== null && pLugard && !pLugard.isNull()) {
                    try { nativeMirrorNpcClick(pLugard, ptr(0)); } catch (eMNP) {}
                }
                return JSON.stringify({ success: false, error: "no_ticket" });
            }

            if (nativeNpcTalk !== null && pLugard && !pLugard.isNull()) {
                try { nativeNpcTalk(pLugard, ptr(0)); } catch (eNT) {}
            }

            var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
            var intMs = (intervalMs !== undefined && parseInt(intervalMs) >= 15) ? parseInt(intervalMs) : 35;
            var maxDur = (maxDurationMs !== undefined && parseInt(maxDurationMs) >= 1000) ? parseInt(maxDurationMs) : 15000;

            _nativeMirrorTurboStats = {
                running: true,
                packetsSent: 0,
                startTime: Date.now(),
                durationMs: maxDur,
                activeSlot: itemSlot,
                relSlot: relSlot,
                entered: false
            };

            // Bắn ngay packet đầu tiên không độ trễ (0ms delay) qua cả Native 0xEFF1B0, 0xEFD7A0 và socket
            if (nativeMirrorEnterAlt !== null) {
                try { nativeMirrorEnterAlt(relSlot, ptr(0)); } catch (eNEAlt0) {}
            }
            if (nativeMirrorEnter !== null) {
                try { nativeMirrorEnter(relSlot, ptr(0)); } catch (eNE1) {}
                try { nativeMirrorEnter(itemSlot, ptr(0)); } catch (eNE2) {}
            }
            sendMirrorEnterPacket(relSlot);
            sendMirrorEnterPacket(itemSlot);
            _nativeMirrorTurboStats.packetsSent++;

            var checkMapCounter = 0;
            _nativeMirrorTurboTimer = setInterval(function() {
                try {
                    if (!_nativeMirrorTurboStats.running) {
                        if (_nativeMirrorTurboTimer !== null) {
                            clearInterval(_nativeMirrorTurboTimer);
                            _nativeMirrorTurboTimer = null;
                        }
                        return;
                    }
                    var elapsed = Date.now() - _nativeMirrorTurboStats.startTime;
                    if (elapsed >= _nativeMirrorTurboStats.durationMs) {
                        _nativeMirrorTurboStats.running = false;
                        if (_nativeMirrorTurboTimer !== null) {
                            clearInterval(_nativeMirrorTurboTimer);
                            _nativeMirrorTurboTimer = null;
                        }
                        send({
                            type: "mirror_turbo_timeout",
                            packets: _nativeMirrorTurboStats.packetsSent,
                            elapsed: elapsed
                        });
                        return;
                    }

                    // Bắn packet trực tiếp tốc độ cao đồng thời qua Native 0xEFF1B0, 0xEFD7A0 và Packet BF:0E, B0:AB
                    if (nativeMirrorEnterAlt !== null) {
                        try { nativeMirrorEnterAlt(_nativeMirrorTurboStats.relSlot, ptr(0)); } catch (eLAlt) {}
                    }
                    if (nativeMirrorEnter !== null) {
                        try { nativeMirrorEnter(_nativeMirrorTurboStats.relSlot, ptr(0)); } catch (eL1) {}
                        try { nativeMirrorEnter(_nativeMirrorTurboStats.activeSlot, ptr(0)); } catch (eL2) {}
                    }
                    sendMirrorEnterPacket(_nativeMirrorTurboStats.relSlot);
                    sendMirrorEnterPacket(_nativeMirrorTurboStats.activeSlot);
                    _nativeMirrorTurboStats.packetsSent++;

                    // Mỗi 4 packet (~120-140ms), kiểm tra xem nhân vật đã vào map sự kiện chưa
                    checkMapCounter++;
                    if (checkMapCounter >= 4) {
                        checkMapCounter = 0;
                        var info = readPlayerInfoSnapshot(false);
                        if (info && info.mapId !== undefined && (info.mapId >= 65 && info.mapId <= 68)) {
                            _nativeMirrorTurboStats.running = false;
                            _nativeMirrorTurboStats.entered = true;
                            if (_nativeMirrorTurboTimer !== null) {
                                clearInterval(_nativeMirrorTurboTimer);
                                _nativeMirrorTurboTimer = null;
                            }
                            send({
                                type: "mirror_turbo_entered",
                                packets: _nativeMirrorTurboStats.packetsSent,
                                elapsed: elapsed,
                                mapId: info.mapId
                            });
                        }
                    }
                } catch (eLoop) {}
            }, intMs);

            return JSON.stringify({
                success: true,
                slot: itemSlot,
                relSlot: relSlot,
                intervalMs: intMs
            });
        } catch (eST) {
            return JSON.stringify({ success: false, error: eST.toString() });
        }
    },

    stopNativeMirrorTurbo: function() {
        try {
            if (_nativeMirrorTurboTimer !== null) {
                clearInterval(_nativeMirrorTurboTimer);
                _nativeMirrorTurboTimer = null;
            }
            _nativeMirrorTurboStats.running = false;
            return JSON.stringify({
                stopped: true,
                packetsSent: _nativeMirrorTurboStats.packetsSent,
                entered: _nativeMirrorTurboStats.entered
            });
        } catch (eStop) {
            return JSON.stringify({ stopped: false, error: eStop.toString() });
        }
    },

    getNativeMirrorTurboStatus: function() {
        return JSON.stringify(_nativeMirrorTurboStats);
    },

    enterMirror: function(slot) {
        try {
            ensureThreadAttached();
            var itemSlot = -1;
            if (slot !== undefined && slot !== null && parseInt(slot) >= 0) {
                itemSlot = parseInt(slot);
            } else {
                // Tự động tìm vị trí vé Mirror of Dimensions (ID 7279 hoặc theo tên) trong toàn bộ hòm đồ
                // ƯU TIÊN TUYỆT ĐỐI Hòm đồ chính (slot 12 - 75) vì Game Server MEGAMU yêu cầu vé ở Main Inventory!
                try {
                    var p = getPlayerPtr();
                    if (!p.isNull()) {
                        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                        if (!inv.isNull()) {
                            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                            if (!itemsArr.isNull()) {
                                var maxSlot = 140;
                                try {
                                    var arrLen = itemsArr.add(0x18).readS32();
                                    if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
                                } catch (eLen) {}

                                var mainTicketSlot = -1;
                                var extTicketSlot = -1;

                                for (var s = 12; s < maxSlot; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = readItemIndex(itemPtr);
                                        var check = checkMirrorItem(itemPtr, idx);
                                        if (check.isTicket) {
                                            if (s < 76 && mainTicketSlot < 0) {
                                                mainTicketSlot = s;
                                            } else if (s >= 76 && extTicketSlot < 0) {
                                                extTicketSlot = s;
                                            }
                                        }
                                    }
                                }
                                // Ưu tiên vé ở hòm đồ chính, nếu không có mới lấy ở ba lô mở rộng
                                itemSlot = (mainTicketSlot >= 12) ? mainTicketSlot : extTicketSlot;
                            }
                        }
                    }
                } catch (eScan) {}
            }
            // Đóng bất kỳ cửa sổ đối thoại NPC nào đang mở để không bị chặn confirm modal
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }

            var pLugard = getOrCreateLugardPtr(0);

            // Gửi packet C1:32 đối thoại NPC Lugard để Server gửi thông báo "Cổng chưa mở / Entrance is closed" lên màn hình game (kể cả khi không có NPC trong viewport)
            try {
                if (pLugard && !pLugard.isNull()) {
                    if (nativeNpcTalk !== null) {
                        try { nativeNpcTalk(pLugard, ptr(0)); } catch (eNT) {}
                    }
                }
            } catch (eLugTalk) {}

            if (itemSlot >= 0) {
                var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
                // Bắn trực tiếp qua cả 2 hàm native enter:
                // 1) nativeMirrorEnterAlt (0xEFF1B0) - gửi BF:0E qua GameServer connection
                // 2) nativeMirrorEnter (0xEFD7A0) - gửi B0:AB
                if (nativeMirrorEnterAlt !== null) {
                    try { nativeMirrorEnterAlt(relSlot, ptr(0)); } catch (eNEA) {}
                }
                if (nativeMirrorEnter !== null) {
                    try { nativeMirrorEnter(relSlot, ptr(0)); } catch (eNE1) {}
                    try { nativeMirrorEnter(itemSlot, ptr(0)); } catch (eNE2) {}
                }
                sendMirrorEnterPacket(relSlot);
                sendMirrorEnterPacket(itemSlot);
                return JSON.stringify({
                    success: true,
                    slot: itemSlot,
                    relSlot: relSlot,
                    isExtended: (itemSlot >= 76)
                });
            } else {
                // KHI KHÔNG CÓ VÉ: Kích hoạt nativeMirrorNpcClick với pLugard (kể cả không có NPC trong viewport)
                // để Client game hiển thị popup "You don't have a Mirror of Dimensions"
                if (nativeMirrorNpcClick !== null && pLugard && !pLugard.isNull()) {
                    try { nativeMirrorNpcClick(pLugard, ptr(0)); } catch (eMNP) {}
                }
                sendMirrorEnterPacket(0);
                if (nativeMirrorEnterAlt !== null) {
                    try { nativeMirrorEnterAlt(0, ptr(0)); } catch (eNEA0) {}
                }
                if (nativeMirrorEnter !== null) {
                    try { nativeMirrorEnter(0, ptr(0)); } catch (eNE0) {}
                }
                return JSON.stringify({ success: false, error: "no_ticket" });
            }
        } catch (eME) {
            return JSON.stringify({ success: false, error: eME.toString() });
        }
    },

    getMirrorTicketInfo: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                if (!inv.isNull()) {
                    var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                    if (!itemsArr.isNull()) {
                        var tickets = [];
                        var ticketDetails = [];
                        var signSlots = [];
                        var mainTickets = [];
                        var extTickets = [];
                        var maxSlot = 140;
                        try {
                            var arrLen = itemsArr.add(0x18).readS32();
                            if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
                        } catch (eLen) {}
                        for (var s = 12; s < maxSlot; s++) {
                            var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemPtr.isNull()) {
                                var idx = readItemIndex(itemPtr);
                                var check = checkMirrorItem(itemPtr, idx);
                                if (check.isTicket) {
                                    tickets.push(s);
                                    var isExt = (s >= 76);
                                    if (isExt) extTickets.push(s); else mainTickets.push(s);
                                    ticketDetails.push({ slot: s, relSlot: (s >= 12 ? s - 12 : s), id: idx, name: check.name, isExtended: isExt });
                                } else if (check.isSign) {
                                    signSlots.push(s);
                                }
                            }
                        }
                        return JSON.stringify({
                            hasTicket: tickets.length > 0,
                            count: tickets.length,
                            slots: tickets,
                            mainSlots: mainTickets,
                            extSlots: extTickets,
                            hasMainTicket: mainTickets.length > 0,
                            hasOnlyExtended: (mainTickets.length === 0 && extTickets.length > 0),
                            details: ticketDetails,
                            signs: signSlots,
                            hasOnlySign: (tickets.length === 0 && signSlots.length > 0)
                        });
                    }
                }
            }
        } catch (eScan) {}
        return JSON.stringify({ hasTicket: false, count: 0, slots: [], mainSlots: [], extSlots: [], hasMainTicket: false, hasOnlyExtended: false, details: [], signs: [], hasOnlySign: false });
    },

    clickMirrorNpc: function(npcPtr) {
        try {
            ensureThreadAttached();
            var p = getOrCreateLugardPtr(npcPtr);
            if (p && !p.isNull()) {
                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT) {}
                }
                // 1. Gửi gói tin C1:32 tới GameServer (Server sẽ gửi về thông báo "The entrance is currently closed" nếu cổng đóng)
                if (nativeNpcTalk !== null) {
                    try { nativeNpcTalk(p, ptr(0)); } catch (eNT) {}
                }
                // 2. Gọi client dialog DoubleGoer (0xEFDE60):
                // - Nếu không có vé: hiển thị popup "You don't have a Mirror of Dimensions"
                // - Nếu có vé: hiển thị confirm modal "You have a Mirror of Dimensions. Do you want to enter?"
                if (nativeMirrorNpcClick !== null) {
                    try { nativeMirrorNpcClick(p, ptr(0)); } catch (eMN) {}
                }
                // 3. Gọi Universal NPC Click của NpcManager (0xF785E0) nếu có
                if (nativeUniversalNpcClick !== null) {
                    var nm = getNpcManagerPtr();
                    if (!nm.isNull()) {
                        try { nativeUniversalNpcClick(nm, p, ptr(0)); } catch (eUNC) {}
                    }
                }
                return true;
            }
        } catch (eMN) {}
        return false;
    },

    isMirrorEventMap: function() {
        try {
            ensureThreadAttached();
            if (nativeMirrorIsEventMap !== null) {
                try {
                    if (nativeMirrorIsEventMap()) return true;
                } catch (eNM) {}
            }
            var info = readPlayerInfoSnapshot(false);
            if (info && info.mapId !== undefined && info.mapId >= 0) {
                return (info.mapId >= 65 && info.mapId <= 68);
            }
        } catch (eMM) {}
        return false;
    },

    enterDevil: function(targetLevel, slot) {
        try {
            ensureThreadAttached();
            var dsLevel = (targetLevel !== undefined && targetLevel !== null && parseInt(targetLevel) >= 0) ? parseInt(targetLevel) : getPlayerDevilSquareLevel();
            var itemSlot = -1;
            if (slot !== undefined && slot !== null && parseInt(slot) >= 0) {
                itemSlot = parseInt(slot);
            } else {
                try {
                    var p = getPlayerPtr();
                    if (!p.isNull()) {
                        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                        if (!inv.isNull()) {
                            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                            if (!itemsArr.isNull()) {
                                var maxSlot = 204;
                                try {
                                    var arrLen = itemsArr.add(0x18).readS32();
                                    if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
                                } catch (eLen) {}

                                var mainMatchedSlot = -1;
                                var extMatchedSlot = -1;
                                var anyMainSlot = -1;
                                var anyExtSlot = -1;

                                for (var s = 12; s < maxSlot; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = readItemIndex(itemPtr);
                                        var check = checkDevilItem(itemPtr, idx);
                                        if (check.isTicket) {
                                            var matches = (check.isMaster || check.level === (dsLevel + 1) || check.level === 0 || dsLevel >= 6);
                                            if (matches) {
                                                if (s < 76 && mainMatchedSlot < 0) mainMatchedSlot = s;
                                                else if (s >= 76 && extMatchedSlot < 0) extMatchedSlot = s;
                                            }
                                            if (s < 76 && anyMainSlot < 0) anyMainSlot = s;
                                            else if (s >= 76 && anyExtSlot < 0) anyExtSlot = s;
                                        }
                                    }
                                }
                                if (mainMatchedSlot >= 12) itemSlot = mainMatchedSlot;
                                else if (extMatchedSlot >= 12) itemSlot = extMatchedSlot;
                                else if (anyMainSlot >= 12) itemSlot = anyMainSlot;
                                else if (anyExtSlot >= 12) itemSlot = anyExtSlot;
                            }
                        }
                    }
                } catch (eScan) {}
            }

            // Đóng mọi popup đối thoại trước khi gửi lệnh vào trực tiếp (Zero-prompt, Zero-dialog)
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            try {
                var charon = getOrCreateCharonPtr();
                if (charon && !charon.isNull()) {
                    if (nativeNpcTalk !== null) {
                        try { nativeNpcTalk(charon, ptr(0)); } catch (eNT) {}
                    }
                }
            } catch (eCharonEnter) {}

            if (itemSlot >= 0) {
                var actualSlot = (itemSlot < 12) ? (itemSlot + 12) : itemSlot;
                // Chỉ gửi lệnh vào đúng 1 lần duy nhất, không gửi nhiều packet spam
                if (nativeDevilEnter !== null) {
                    try { nativeDevilEnter(dsLevel, actualSlot, ptr(0)); } catch (eNDE1) {}
                } else {
                    sendDevilEnterPacket(dsLevel, actualSlot);
                }

                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT2) {}
                }

                return JSON.stringify({
                    success: true,
                    dsLevel: dsLevel,
                    slot: actualSlot,
                    isExtended: (actualSlot >= 76)
                });
            }
            return JSON.stringify({ success: false, error: "no_ticket" });
        } catch (eDE) {
            return JSON.stringify({ success: false, error: eDE.toString() });
        }
    },

    getDevilTicketInfo: function() {
        try {
            ensureThreadAttached();
            var dsLevel = getPlayerDevilSquareLevel();
            var p = getPlayerPtr();
            if (!p.isNull()) {
                var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                if (!inv.isNull()) {
                    var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                    if (!itemsArr.isNull()) {
                        var maxSlot = 204;
                        try {
                            var arrLen = itemsArr.add(0x18).readS32();
                            if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
                        } catch (eLen) {}

                        var tickets = [];
                        var matchedTickets = [];
                        var mainSlots = [];
                        var extSlots = [];

                        for (var s = 12; s < maxSlot; s++) {
                            var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemPtr.isNull()) {
                                var idx = readItemIndex(itemPtr);
                                var check = checkDevilItem(itemPtr, idx);
                                if (check.isTicket) {
                                    tickets.push(s);
                                    if (s < 76) mainSlots.push(s);
                                    else extSlots.push(s);
                                    if (check.isMaster || check.level === (dsLevel + 1) || check.level === 0 || dsLevel >= 6) {
                                        matchedTickets.push(s);
                                    }
                                }
                            }
                        }
                        return JSON.stringify({
                            hasTicket: tickets.length > 0,
                            hasMatchedTicket: matchedTickets.length > 0,
                            count: tickets.length,
                            dsLevel: dsLevel,
                            targetTicketLevel: dsLevel + 1,
                            slots: tickets,
                            matchedSlots: matchedTickets,
                            mainSlots: mainSlots,
                            extSlots: extSlots,
                            hasOnlyExtended: (mainSlots.length === 0 && extSlots.length > 0)
                        });
                    }
                }
            }
        } catch (eDTI) {}
        return JSON.stringify({ hasTicket: false, count: 0, slots: [] });
    },

    clickDevilNpc: function(npcPtr) {
        try {
            ensureThreadAttached();
            var p = getOrCreateCharonPtr(npcPtr);
            if (!p.isNull()) {
                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT) {}
                }
                if (nativeNpcTalk !== null) {
                    try { nativeNpcTalk(p, ptr(0)); } catch (eNT) {}
                }
                return true;
            }
        } catch (eDN) {}
        return false;
    },

    isDevilEventMap: function() {
        try {
            ensureThreadAttached();
            if (nativeDevilIsEventMap !== null) {
                try {
                    if (nativeDevilIsEventMap()) return true;
                } catch (eNDM) {}
            }
            var info = readPlayerInfoSnapshot(false);
            if (info && info.mapId !== undefined && info.mapId >= 0) {
                return (info.mapId === 9 || info.mapId === 32);
            }
        } catch (eDM) {}
        return false;
    },

    teleportToEventMap: function() {
        try {
            ensureThreadAttached();
            var info = readPlayerInfoSnapshot(false);
            if (info && info.mapId !== undefined && (info.mapId === 40 || info.mapId === 53 || (info.mapId >= 65 && info.mapId <= 68))) {
                return true;
            }
            dispatchChatMessage("/move ev");
            sendGatePacket(507);
            if (this.sendChatNative) {
                try { this.sendChatNative("/move ev"); } catch (eSC) {}
            }
            if (nativeMirrorTeleportEventMap !== null) {
                try { nativeMirrorTeleportEventMap(ptr(0), 1, ptr(0)); } catch (e) {}
            }
            return true;
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

            var maxSlot = 140;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}
            var totalCount = maxSlot - 12;
            var freeSlots = 0;
            var junkSlots = [];
            var mossPlusSlots = [];
            var keptSlots = [];

            for (var s = 12; s < maxSlot; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) {
                    freeSlots++;
                    continue;
                }
                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x14).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var sec = Math.floor(itemIndex / 512);

                // Bảo tồn nghiêm ngặt theo yêu cầu:
                // 1. Đồ Divine, Đồ Rồng (tuyệt đối không vứt hay bán)
                // 2. Đồ thường từ +5 trở lên (itemLevel >= 5)
                // 3. Đồ Hoàn Hảo (excOpt > 0)
                // 4. Đồ Thần (ancOpt > 0)
                // 5. Đồ Socket (sockOpt > 0)
                // 6. Toàn bộ ngọc, vé sự kiện, cánh, sách phép (sec >= 12 && sec <= 15)
                // -> Còn lại (đồ thường +0 đến +4 không Exc/Set/Socket/Divine/Rồng) là đồ rác có thể vứt.
                var isDivineOrDragon = isDivineOrDragonItem(itemPtr, itemIndex);
                var isKept = isDivineOrDragon || (excOpt > 0) || (ancOpt > 0) || (sockOpt > 0) || (itemLevel >= 5) || (sec >= 12 && sec <= 15);
                var isExt = (s >= 76);
                var itName = getItemName(itemPtr);
                if (isKept) {
                    keptSlots.push({ slot: s, index: itemIndex, name: itName, level: itemLevel, exc: excOpt, anc: ancOpt, sock: sockOpt, isExt: isExt, isSpecial: isDivineOrDragon });
                    // Phân loại đồ Moss rác thông thường <= +7 (không Divine/Rồng, không Exc, không Thần, không Socket, sec < 12)
                    // để tự động mang ra NPC bán khi hòm đồ bị đầy hoặc không thể vứt ra đất
                    if (!isDivineOrDragon && excOpt === 0 && ancOpt === 0 && sockOpt === 0 && (sec < 12 || sec > 15) && itemLevel <= 7) {
                        mossPlusSlots.push({ slot: s, index: itemIndex, name: itName, level: itemLevel, isExt: isExt });
                    }
                } else {
                    junkSlots.push({ slot: s, index: itemIndex, name: itName, level: itemLevel, isExt: isExt });
                }
            }

            return JSON.stringify({
                total: totalCount,
                free: freeSlots,
                used: totalCount - freeSlots,
                junkCount: junkSlots.length,
                mossPlusCount: mossPlusSlots.length,
                keptCount: keptSlots.length,
                junkSlots: junkSlots,
                mossPlusSlots: mossPlusSlots,
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

            if (nativeInvDropItem === null && nativeInvTrashItem === null && nativeInvSellItem === null && nativeGSSend === null) {
                return JSON.stringify({ cleaned: 0, error: "no_native_fn" });
            }

            var dropCoord = ptr(0);
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
                    coordBuf.add(0x10).writeS32(curX + 1);
                    coordBuf.add(0x14).writeS32(curY);
                    dropCoord = coordBuf;
                }
            } catch (eXY) {}

            var cleaned = 0;
            var useMethod = (method || "drop").toLowerCase();

            var maxSlot = 140;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            for (var s = 12; s < maxSlot; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x14).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var sec = Math.floor(itemIndex / 512);

                // Bảo vệ tuyệt đối: Đồ Divine, Đồ Rồng, Đồ thường >= +5, Exc, Ancient, Socket, Ngọc/Vé sự kiện/Cánh/Sách phép (sec 12-15)
                // Cho phép vứt: Đồ thường từ +0 đến +4 không Exc/Ancient/Socket/Divine/Rồng
                if (isDivineOrDragonItem(itemPtr, itemIndex) || excOpt > 0 || ancOpt > 0 || sockOpt > 0 || itemLevel >= 5 || (sec >= 12 && sec <= 15)) {
                    continue;
                }

                var itemHandled = false;
                try {
                    if (useMethod === "drop" || useMethod === "trash" || useMethod === "both") {
                        ensureDropAllowed();
                        // Thao tác 1: Vứt qua nativeInvDropItem (0x1368A30) với coord null (Engine tự sinh tọa độ quanh nhân vật và gửi packet 0x23)
                        if (nativeInvDropItem !== null) {
                            try {
                                nativeInvDropItem(s, ptr(0), ptr(0));
                                try { Thread.sleep(0.06); } catch (eSl1) {}
                                var postPtr1 = itemsArr.add(0x20 + s * 8).readPointer();
                                if (postPtr1.isNull() || !postPtr1.equals(itemPtr)) {
                                    itemHandled = true;
                                }
                            } catch (eDrop1) {}
                        }
                        // Thao tác 2: Vứt qua nativeInvDropItem với tọa độ cạnh bên
                        if (!itemHandled && nativeInvDropItem !== null && !dropCoord.isNull()) {
                            try {
                                nativeInvDropItem(s, dropCoord, ptr(0));
                                try { Thread.sleep(0.06); } catch (eSl2) {}
                                var postPtr2 = itemsArr.add(0x20 + s * 8).readPointer();
                                if (postPtr2.isNull() || !postPtr2.equals(itemPtr)) {
                                    itemHandled = true;
                                }
                            } catch (eDrop2) {}
                        }
                        // Thao tác 3: Gửi trực tiếp packet GS C1:23
                        if (!itemHandled && curX > 0 && curY > 0) {
                            try {
                                sendDropPacket(s, curX + 1, curY);
                                try { Thread.sleep(0.06); } catch (eSl3) {}
                                var postPtr3 = itemsArr.add(0x20 + s * 8).readPointer();
                                if (postPtr3.isNull() || !postPtr3.equals(itemPtr)) {
                                    itemHandled = true;
                                }
                            } catch (eDropPkt) {}
                        }
                        // Thao tác 4: Xóa/hủy qua nativeInvTrashItem (0x13678A0, instance method nhận inv)
                        if (!itemHandled && nativeInvTrashItem !== null && !inv.isNull()) {
                            try {
                                nativeInvTrashItem(inv, s, ptr(0));
                                try { Thread.sleep(0.06); } catch (eSl4) {}
                                var postPtr4 = itemsArr.add(0x20 + s * 8).readPointer();
                                if (postPtr4.isNull() || !postPtr4.equals(itemPtr)) {
                                    itemHandled = true;
                                }
                            } catch (eTrash) {}
                        }
                    }
                    if (!itemHandled && (useMethod === "sell" || useMethod === "both")) {
                        // Thao tác 5: Bán vào NPC shop qua nativeInvSellItem hoặc sendSellPacket
                        if (nativeInvSellItem !== null && !inv.isNull()) {
                            try {
                                nativeInvSellItem(inv, s, ptr(0));
                                try { Thread.sleep(0.06); } catch (eSl5) {}
                                var postPtr5 = itemsArr.add(0x20 + s * 8).readPointer();
                                if (postPtr5.isNull() || !postPtr5.equals(itemPtr)) {
                                    itemHandled = true;
                                }
                            } catch (eSellNative) {}
                        }
                        if (!itemHandled) {
                            sendSellPacket(s);
                            try { Thread.sleep(0.06); } catch (eSl6) {}
                            var postPtrSell = itemsArr.add(0x20 + s * 8).readPointer();
                            if (postPtrSell.isNull() || !postPtrSell.equals(itemPtr)) {
                                itemHandled = true;
                            }
                        }
                    }
                    if (itemHandled) {
                        cleaned++;
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
            if (nativeInvDropItem === null && nativeInvTrashItem === null && nativeGSSend === null) {
                return JSON.stringify({ ok: false, err: "no_drop_native_available" });
            }

            var p = getPlayerPtr();
            var dropCoord = ptr(0);
            var dropX = 0;
            var dropY = 0;
            try {
                if (!p.isNull()) {
                    var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                    if (!curCoord.isNull()) {
                        var klass = curCoord.readPointer();
                        if (!klass.isNull()) coordBuf.writePointer(klass);
                        coordBuf.add(0x08).writePointer(ptr(0));
                        var curX = curCoord.add(0x10).readS32();
                        var curY = curCoord.add(0x14).readS32();
                        dropX = curX + ox;
                        dropY = curY + oy;
                        coordBuf.add(0x10).writeS32(dropX);
                        coordBuf.add(0x14).writeS32(dropY);
                        dropCoord = coordBuf;
                    }
                }
            } catch (ePXY) {}

            var itemP = ptr(0);
            var itemIdx = -1;
            var itemsArr = ptr(0);
            var inv = ptr(0);
            try {
                if (!p.isNull()) {
                    inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            itemP = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemP.isNull()) {
                                itemIdx = itemP.add(0x10).readS32();
                            }
                        }
                    }
                }
            } catch (eCheck) {}

            if (itemP.isNull()) {
                return JSON.stringify({ ok: false, err: "empty_slot", slot: s });
            }

            if (isDivineOrDragonItem(itemP, itemIdx)) {
                return JSON.stringify({ ok: false, err: "protected_item_divine_or_dragon", slot: s });
            }

            var dropped = false;
            // Thao tác 1: Native Drop với null coord (game tự tính tọa độ quanh nhân vật và jitter)
            if (nativeInvDropItem !== null) {
                try {
                    nativeInvDropItem(s, ptr(0), ptr(0));
                    try { Thread.sleep(0.06); } catch (eSl1) {}
                    if (!itemsArr.isNull()) {
                        var chk1 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (chk1.isNull() || !chk1.equals(itemP)) dropped = true;
                    }
                } catch (eD1) {}
            }

            // Thao tác 2: Native Drop với dropCoord
            if (!dropped && nativeInvDropItem !== null && !dropCoord.isNull()) {
                try {
                    nativeInvDropItem(s, dropCoord, ptr(0));
                    try { Thread.sleep(0.06); } catch (eSl2) {}
                    if (!itemsArr.isNull()) {
                        var chk2 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (chk2.isNull() || !chk2.equals(itemP)) dropped = true;
                    }
                } catch (eD2) {}
            }

            // Thao tác 3: Gửi packet GS C1:23
            if (!dropped && dropX > 0 && dropY > 0) {
                try {
                    sendDropPacket(s, dropX, dropY);
                    try { Thread.sleep(0.06); } catch (eSl3) {}
                    if (!itemsArr.isNull()) {
                        var chk3 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (chk3.isNull() || !chk3.equals(itemP)) dropped = true;
                    }
                } catch (eD3) {}
            }

            // Thao tác 4: Native Trash Item (0x13678A0 với inv instance)
            if (!dropped && nativeInvTrashItem !== null && !inv.isNull()) {
                try {
                    nativeInvTrashItem(inv, s, ptr(0));
                    try { Thread.sleep(0.06); } catch (eSl4) {}
                    if (!itemsArr.isNull()) {
                        var chk4 = itemsArr.add(0x20 + s * 8).readPointer();
                        if (chk4.isNull() || !chk4.equals(itemP)) dropped = true;
                    }
                } catch (eD4) {}
            }

            return JSON.stringify({ ok: dropped, allowed: allowed, slot: s, x: dropX, y: dropY });
        } catch (e) {
            return JSON.stringify({ ok: false, err: e.toString() });
        }
    },

    sellInventorySlot: function(slot) {
        try {
            ensureThreadAttached();
            var s = parseInt(slot);
            var itemP = ptr(0);
            var itemIdx = -1;
            var p = getPlayerPtr();
            var itemsArr = ptr(0);
            try {
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            itemP = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemP.isNull()) {
                                itemIdx = itemP.add(0x10).readS32();
                            }
                        }
                    }
                }
            } catch (eP) {}
            if (itemP.isNull()) return false;
            if (isDivineOrDragonItem(itemP, itemIdx)) {
                return false;
            }

            // 1. Gửi gói tin C1:33 bán vào shop NPC
            sendSellPacket(s);
            try { Thread.sleep(0.08); } catch (eSl1) {}
            if (!itemsArr.isNull()) {
                var postSell = itemsArr.add(0x20 + s * 8).readPointer();
                if (postSell.isNull() || !postSell.equals(itemP)) return true;
            }

            // 2. Thử native Slot Quick Action nếu có window shop
            if (nativeSlotQuickAction !== null) {
                try {
                    nativeSlotQuickAction(itemP, ptr(0));
                    try { Thread.sleep(0.08); } catch (eSl2) {}
                    if (!itemsArr.isNull()) {
                        var postQA = itemsArr.add(0x20 + s * 8).readPointer();
                        if (postQA.isNull() || !postQA.equals(itemP)) return true;
                    }
                } catch (eQA) {}
            }

            // 3. Fallback: vứt ra đất hoặc xóa nếu không bán được
            if (nativeInvDropItem !== null || nativeInvTrashItem !== null) {
                ensureDropAllowed();
                if (nativeInvDropItem !== null) {
                    try {
                        nativeInvDropItem(s, ptr(0), ptr(0));
                        try { Thread.sleep(0.06); } catch (eSl3) {}
                        if (!itemsArr.isNull()) {
                            var postDrop = itemsArr.add(0x20 + s * 8).readPointer();
                            if (postDrop.isNull() || !postDrop.equals(itemP)) return true;
                        }
                    } catch (eD) {}
                }
                if (nativeInvTrashItem !== null && !inv.isNull()) {
                    try {
                        nativeInvTrashItem(inv, s, ptr(0));
                        try { Thread.sleep(0.06); } catch (eSl4) {}
                        if (!itemsArr.isNull()) {
                            var postTrash = itemsArr.add(0x20 + s * 8).readPointer();
                            if (postTrash.isNull() || !postTrash.equals(itemP)) return true;
                        }
                    } catch (eT) {}
                }
            }
        } catch (e) {}
        return false;
    },

    autoLogin: function(server, account, character, password) {
        try {
            ensureThreadAttached();
            var s = parseInt(server || 1);
            var acc = account ? String(account) : "";
            var chr = character ? String(character) : "";
            var pwd = (password !== undefined && password !== null) ? String(password) : "";

            // 1. Cấu hình tức thì AutoLogin singleton nếu đã có sẵn
            var autoLogin = null;
            if (nativeGetAutoLogin !== null) {
                try { autoLogin = nativeGetAutoLogin(); } catch (eG) {}
            }
            if (autoLogin !== null && !autoLogin.isNull()) {
                try {
                    var accStr = il2cpp_string_new(Memory.allocUtf8String(acc));
                    var chrStr = il2cpp_string_new(Memory.allocUtf8String(chr));
                    if (nativeSetAutoLogin !== null) {
                        try { nativeSetAutoLogin(autoLogin, s, accStr, chrStr); } catch (eSet) {}
                    }
                    autoLogin.add(0x20).writeU8(0);
                    autoLogin.add(0x21).writeU8(0);
                    autoLogin.add(0x22).writeU8(0);
                    autoLogin.add(0x23).writeU8(0);
                    autoLogin.add(0x24).writeS32(s);
                    autoLogin.add(0x28).writePointer(accStr);
                    autoLogin.add(0x30).writePointer(chrStr);
                } catch (eALInit) {}
            }

            // 2. Đặt lệnh vào hàng đợi Main Thread để Game.Update thực thi chính xác và an toàn
            autoLoginLastStatus = { done: false, submitted: false, stage: "queued", account: acc };
            pendingAutoLogin = {
                server: s,
                account: acc,
                character: chr,
                password: pwd,
                frames: 0,
                done: false,
                submitted: false
            };

            return JSON.stringify({ ok: true, server: s, account: acc, character: chr, queued: true });
        } catch (e) {
            return JSON.stringify({ ok: false, err: e.toString() });
        }
    },

    getAutoLoginStatus: function() {
        return JSON.stringify(autoLoginLastStatus);
    },

    get_auto_login_status: function() {
        return JSON.stringify(autoLoginLastStatus);
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
            if (gameUpdateHook !== null) {
                gameUpdateHook.detach();
                gameUpdateHook = null;
            }
        } catch (eGU) {}
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
        meipass = os.environ.get("NUITKA_ONEFILE_DIRECTORY") or getattr(sys, "_MEIPASS", None)
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
            "__CHAT_SEND__": self.offsets.get("chat_send") or DEFAULT_OFFSETS.get("chat_send", "0x13C0C70"),
            "__CHAT_SEND_CMD__": self.offsets.get("chat_send_cmd") or DEFAULT_OFFSETS.get("chat_send_cmd", "0xFA0A60"),
            "__CHAT_FRAME_SEND__": self.offsets.get("chat_frame_send") or DEFAULT_OFFSETS.get("chat_frame_send", "0x13C0C70"),
            "__STATIC_CHAT_SEND__": self.offsets.get("static_chat_send") or DEFAULT_OFFSETS.get("static_chat_send", "0xF95530"),
            "__COMMAND_MGR_PROCESS__": self.offsets.get("command_mgr_process") or DEFAULT_OFFSETS.get("command_mgr_process", "0xFA0A60"),
            "__CHAT_UPDATE__": self.offsets.get("chat_update") or DEFAULT_OFFSETS.get("chat_update", "0x13BD830"),
            "__GAME_UI_UPDATE__": self.offsets.get("game_ui_update") or DEFAULT_OFFSETS.get("game_ui_update", "0x12B31E0"),
            "__HELPER_START__": self.offsets.get("helper_start") or DEFAULT_OFFSETS.get("helper_start", "0x2689720"),
            "__HELPER_STOP__": self.offsets.get("helper_stop") or DEFAULT_OFFSETS.get("helper_stop", "0x2682B20"),
            "__HELPER_ACTION__": self.offsets.get("helper_action") or DEFAULT_OFFSETS.get("helper_action", "0x268CF00"),
            "__HELPER_TOGGLE__": self.offsets.get("helper_toggle") or DEFAULT_OFFSETS.get("helper_toggle", "0x268CF00"),
            "__HELPER_SEND_BF51__": self.offsets.get("helper_send_bf51") or DEFAULT_OFFSETS.get("helper_send_bf51", "0x26829C0"),
            "__HELPER_REQ_START__": self.offsets.get("helper_req_start") or DEFAULT_OFFSETS.get("helper_req_start", "0x26830F0"),
            "__HELPER_REQ_STOP__": self.offsets.get("helper_req_stop") or DEFAULT_OFFSETS.get("helper_req_stop", "0x2683B80"),
            "__UI_LOCATION_FRAME__": self.offsets.get("ui_location_frame") or DEFAULT_OFFSETS.get("ui_location_frame", "0x80"),
            "__LOCATION_HELPER_ON__": self.offsets.get("location_helper_on") or DEFAULT_OFFSETS.get("location_helper_on", "0x60"),
            "__LOCATION_HELPER_OFF__": self.offsets.get("location_helper_off") or DEFAULT_OFFSETS.get("location_helper_off", "0x68"),
            "__LOCATION_UPDATE_HELPER__": self.offsets.get("location_update_helper") or DEFAULT_OFFSETS.get("location_update_helper", "0x244C880"),
            "__PLAYER_NAME__": self.offsets.get("player_name") or DEFAULT_OFFSETS.get("player_name", "0x28"),
            "__PLAYER_LEVEL__": self.offsets.get("player_level") or DEFAULT_OFFSETS.get("player_level", "0x30"),
            "__PLAYER_CLASS__": self.offsets.get("player_class") or DEFAULT_OFFSETS.get("player_class", "0x34"),
            "__PLAYER_COORD__": self.offsets.get("player_coord") or DEFAULT_OFFSETS.get("player_coord", "0x68"),
            "__PLAYER_MOVE__": self.offsets.get("player_move") or DEFAULT_OFFSETS.get("player_move", "0xF0"),
            "__PLAYER_HELPER__": self.offsets.get("player_helper") or DEFAULT_OFFSETS.get("player_helper", "0x1E0"),
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
            "__MOSS_ROLL__": self.offsets.get("moss_roll") or DEFAULT_OFFSETS.get("moss_roll", "0x262EE30"),
            "__MOSS_OPEN__": self.offsets.get("moss_open") or DEFAULT_OFFSETS.get("moss_open", "0x24C0410"),
            "__UI_MOSS_WINDOW__": self.offsets.get("ui_moss_window") or DEFAULT_OFFSETS.get("ui_moss_window", "0x1C8"),
            "__WINDOW_SHOW__": self.offsets.get("window_show") or DEFAULT_OFFSETS.get("window_show", "0x24C0410"),
            "__WINDOW_HIDE__": self.offsets.get("window_hide") or DEFAULT_OFFSETS.get("window_hide", "0x1942170"),
            "__WINDOW_SET_STATE__": self.offsets.get("window_set_state") or DEFAULT_OFFSETS.get("window_set_state", "0x24C0220"),
            "__MOSS_ROLL_HANDLER__": self.offsets.get("moss_roll_handler") or DEFAULT_OFFSETS.get("moss_roll_handler", "0x262DCB0"),
            "__MOSS_INIT__": self.offsets.get("moss_init") or DEFAULT_OFFSETS.get("moss_init", "0x262DCF0"),
            "__MOSS_SELECT_CAT__": self.offsets.get("moss_select_cat") or DEFAULT_OFFSETS.get("moss_select_cat", "0x2627DD0"),
            "__MOSS_SEND_ROLL__": self.offsets.get("moss_send_roll") or DEFAULT_OFFSETS.get("moss_send_roll", "0x22F2200"),
            "__MOSS_ROLL_CLICK__": self.offsets.get("moss_roll_click") or DEFAULT_OFFSETS.get("moss_roll_click", "0x2632710"),
            "__MOSS_WINDOW_CLOSE__": self.offsets.get("moss_window_close") or DEFAULT_OFFSETS.get("moss_window_close", "0x2632630"),
            "__GAME_OBJECT_SET_ACTIVE__": self.offsets.get("game_object_set_active") or DEFAULT_OFFSETS.get("game_object_set_active", "0x45084D0"),
            "__MIRROR_ENTER__": self.offsets.get("mirror_enter") or DEFAULT_OFFSETS.get("mirror_enter", "0xEFD7A0"),
            "__MIRROR_ENTER_ALT__": self.offsets.get("mirror_enter_alt") or DEFAULT_OFFSETS.get("mirror_enter_alt", "0xEFF1B0"),
            "__MIRROR_NPC_CLICK__": self.offsets.get("mirror_npc_click") or DEFAULT_OFFSETS.get("mirror_npc_click", "0xEFDE60"),
            "__MIRROR_IS_EVENT_MAP__": self.offsets.get("mirror_is_event_map") or DEFAULT_OFFSETS.get("mirror_is_event_map", "0xF013A0"),
            "__MIRROR_TELEPORT_EVENT__": self.offsets.get("mirror_teleport_event") or DEFAULT_OFFSETS.get("mirror_teleport_event", "0x3802C0"),
            "__DEVIL_ENTER__": self.offsets.get("devil_enter") or DEFAULT_OFFSETS.get("devil_enter", "0xEF37B0"),
            "__DEVIL_NPC_CLICK__": self.offsets.get("devil_npc_click") or DEFAULT_OFFSETS.get("devil_npc_click", "0xEFA3D0"),
            "__DEVIL_IS_EVENT_MAP__": self.offsets.get("devil_is_event_map") or DEFAULT_OFFSETS.get("devil_is_event_map", "0xEF5580"),
            "__PLAYER_POINT__": self.offsets.get("player_point") or DEFAULT_OFFSETS.get("player_point", "0x238"),
            "__PLAYER_MASTER_POINT__": self.offsets.get("player_master_point") or DEFAULT_OFFSETS.get("player_master_point", "0x23C"),
            "__PLAYER_RESET_COUNT__": self.offsets.get("player_reset_count") or DEFAULT_OFFSETS.get("player_reset_count", "0x2B4"),
            "__INV_SELL_ITEM__": self.offsets.get("inv_sell_item") or DEFAULT_OFFSETS.get("inv_sell_item", "0x1367460"),
            "__MERCHANT_SELL_ITEM__": self.offsets.get("merchant_sell_item") or DEFAULT_OFFSETS.get("merchant_sell_item", "0x2605BB0"),
            "__SLOT_QUICK_ACTION__": self.offsets.get("slot_quick_action") or DEFAULT_OFFSETS.get("slot_quick_action", "0x22DB330"),
            "__INV_DROP_ITEM__": self.offsets.get("inv_drop_item") or DEFAULT_OFFSETS.get("inv_drop_item", "0x1368A30"),
            "__INV_TRASH_ITEM__": self.offsets.get("inv_trash_item") or DEFAULT_OFFSETS.get("inv_trash_item", "0x13678A0"),
            "__PLAYER_INVENTORY__": self.offsets.get("player_inventory") or DEFAULT_OFFSETS.get("player_inventory", "0x1B0"),
            "__INVENTORY_ITEMS__": self.offsets.get("inventory_items") or DEFAULT_OFFSETS.get("inventory_items", "0x28"),
            "__GET_AUTO_LOGIN__": self.offsets.get("get_auto_login") or DEFAULT_OFFSETS.get("get_auto_login", "0xFAC460"),
            "__SET_AUTO_LOGIN__": self.offsets.get("set_auto_login") or DEFAULT_OFFSETS.get("set_auto_login", "0xE59220"),
            "__NPC_TALK__": self.offsets.get("npc_talk") or DEFAULT_OFFSETS.get("npc_talk", "0xF8D320"),
            "__VIEWPORT__": self.offsets.get("viewport") or DEFAULT_OFFSETS.get("viewport", "0x110"),
            "__COMPONENT_GET_GAMEOBJECT__": self.offsets.get("component_get_game_object") or DEFAULT_OFFSETS.get("component_get_game_object", "0x45040B0"),
            "__GET_WINDOW_HANDLER__": self.offsets.get("get_window_handler") or DEFAULT_OFFSETS.get("get_window_handler", "0xFAACF0"),
            "__NPC_CLOSE_TALK__": self.offsets.get("npc_close_talk") or DEFAULT_OFFSETS.get("npc_close_talk", "0xF85E90"),
            "__NPC_CLICK__": self.offsets.get("npc_click") or DEFAULT_OFFSETS.get("npc_click", "0xF785E0"),
            "__UI_MERCHANT_WINDOW__": self.offsets.get("ui_merchant_window") or DEFAULT_OFFSETS.get("ui_merchant_window", "0x198"),
            "__ITEM_STORAGE_TYPE_INFO__": self.offsets.get("item_storage_type_info") or DEFAULT_OFFSETS.get("item_storage_type_info", "0x546C240"),
            "__MLOGIN_UI_TYPE_INFO__": self.offsets.get("mlogin_ui_type_info") or DEFAULT_OFFSETS.get("mlogin_ui_type_info", "0x5451C68"),
            "__MLOGIN_SUBMIT__": self.offsets.get("mlogin_submit") or DEFAULT_OFFSETS.get("mlogin_submit", "0x1B6DA50"),
            "__MLOGIN_TOKEN_LOGIN__": self.offsets.get("mlogin_token_login") or DEFAULT_OFFSETS.get("mlogin_token_login", "0x1B70230"),
            "__GAME_UPDATE__": self.offsets.get("game_update") or DEFAULT_OFFSETS.get("game_update", "0xF97C30"),
            "__GET_GS_CONNECTION__": self.offsets.get("get_gs_connection") or DEFAULT_OFFSETS.get("get_gs_connection", "0xFA9570"),
            "__GS_SEND__": self.offsets.get("gs_send") or DEFAULT_OFFSETS.get("gs_send", "0x1115380"),
            "__GS_SEND_ALT__": self.offsets.get("gs_send_alt") or DEFAULT_OFFSETS.get("gs_send_alt", "0x1119CF0"),
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
                    elif p_type in ("mirror_turbo_entered", "mirror_turbo_timeout"):
                        self.last_mirror_turbo_result = payload
                        cb = getattr(self, "on_mirror_turbo_event", None)
                        if callable(cb):
                            try:
                                cb(payload)
                            except Exception:
                                pass
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
                err_str = str(e).lower()
                if "unable to find method" not in err_str:
                    _safe_log(f"[MegDirectEngine] RPC _call '{func_name}' error: {e}")
                # Nếu RPC lỗi do script bị mất, đánh dấu cần gắn lại
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

    def get_player_info(self, max_age: float = 0.55, allow_blocking: bool = True) -> Optional[Dict[str, Any]]:
        """Lấy thông tin nhân vật từ Fast Telemetry nếu còn mới, fallback gọi RPC hoặc đọc RAM trực tiếp."""
        now = time.time()
        if self.last_fast_state and (now - self.last_fast_state_time) <= max_age:
            return self.last_fast_state

        if not allow_blocking:
            # Chế độ không khóa luồng dành riêng cho giao diện UI: trả về state mới nhất ngay lập tức
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

        # 1. Luôn ưu tiên tuyệt đối gửi ngầm 100% qua Native Hook (Static Chat Mega.Chat.FCIBNHIHDHO)
        # Hoàn toàn không bao giờ mở khung chat hay cướp tiêu điểm chuột!
        native_sent = False
        if self.is_ready:
            try:
                if self._call("send_chat_native", cmd):
                    time.sleep(0.12)
                    _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat native ngầm (Mega.Chat): '{cmd}'")
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi gọi send_chat_native: {e}")

        if not force_simulator:
            return False

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
        """Kích hoạt bật MuHelper chuẩn giao diện game (Đồng bộ GUI Play->Stop và gửi gói tin máy chủ)."""
        self.last_fast_state = None

        # Nếu cần force_restart (để ghim lại tọa độ gốc cắm bãi): tắt helper cũ trước
        if force_restart and self.is_helper_active(force_refresh=True):
            self.stop_helper()
            time.sleep(0.15)

        tx = int(target_x) if target_x is not None else 0
        ty = int(target_y) if target_y is not None else 0

        # Kênh 1: Native Helper Start trên Unity Main Thread (Game.Update) qua Frida
        if self.is_ready:
            try:
                self._call("startHelper")
            except Exception:
                pass
            for _ in range(12):
                time.sleep(0.04)
                if self.is_helper_active(force_refresh=True):
                    try:
                        self._call("syncHelperUI", True)
                    except Exception:
                        pass
                    return True

        # Kênh 2: Gửi phím Home (VK_HOME = 0x24) chuẩn xác vào cửa sổ game (tương đương nhấn Play trên giao diện)
        if not self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.05) # Phím Home
                for _ in range(10):
                    time.sleep(0.04)
                    if self.is_helper_active(force_refresh=True):
                        try:
                            self._call("syncHelperUI", True)
                        except Exception:
                            pass
                        return True

        act = self.is_helper_active(force_refresh=True)
        if self.is_ready:
            try:
                self._call("syncHelperUI", act)
            except Exception:
                pass
        return act

    def stop_helper(self) -> bool:
        """Kích hoạt tắt MuHelper chuẩn giao diện game (Đồng bộ GUI Stop->Play và gửi gói tin máy chủ)."""
        self.last_fast_state = None

        # Kênh 1: Native Helper Stop & Packet qua Frida (Chạy ngầm headless 100%, không cần click game)
        if self.is_ready:
            try:
                self._call("stopHelper")
            except Exception:
                pass
            for _ in range(15):
                time.sleep(0.04)
                if not self.is_helper_active(force_refresh=True):
                    try:
                        self._call("syncHelperUI", False)
                    except Exception:
                        pass
                    return True

        # Kênh 2: Gửi phím Home (VK_HOME = 0x24) chuẩn xác vào cửa sổ game
        if self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.05) # Phím Home (Toggle)
                for _ in range(10):
                    time.sleep(0.04)
                    if not self.is_helper_active(force_refresh=True):
                        try:
                            self._call("syncHelperUI", False)
                        except Exception:
                            pass
                        return True

        act = self.is_helper_active(force_refresh=True)
        if self.is_ready:
            try:
                self._call("syncHelperUI", act)
            except Exception:
                pass
        return not act

    def is_moss_open(self) -> bool:
        """Kiểm tra xem cửa sổ Moss Merchant có đang hiển thị trên giao diện game hay không."""
        if self.is_ready:
            try:
                return bool(self._call("isMossOpen"))
            except Exception:
                pass
        return False

    def is_moss_ready(self) -> bool:
        """Kiểm tra xem cửa sổ Moss Merchant đã mở và danh sách Category đã được nạp thành công từ Server chưa."""
        if self.is_ready:
            try:
                return bool(self._call("isMossReady"))
            except Exception:
                pass
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

    def close_moss(self) -> bool:
        """Đóng giao diện Moss Merchant trên Game Client, ngắt render và giải phóng tài nguyên an toàn."""
        if self.is_ready:
            try:
                res = self._call("closeMoss")
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi close_moss: {e}")
        return False

    def reset_moss_ui(self, category_id: int = 0) -> bool:
        """Khôi phục trạng thái bảng Moss và đảm bảo nút Quay (RollButton) luôn hiển thị."""
        if self.is_ready:
            try:
                res = self._call("resetMossUI", int(category_id))
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi reset_moss_ui: {e}")
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
                    if b_name:
                        if "moss" in b_name.lower():
                            is_moss = True
                    else:
                        if 21 <= tx <= 25 and 223 <= ty <= 227:
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
    def get_moss_categories(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các Category Moss Merchant thực tế đang nạp trong RAM Game."""
        if self.is_ready:
            try:
                res_str = self._call("getMossCategories")
                if res_str:
                    res = json.loads(res_str) if isinstance(res_str, str) else res_str
                    if isinstance(res, dict) and res.get("ok"):
                        return res.get("categories", [])
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi get_moss_categories: {e}")
        return []

    def find_merchant_npc(self) -> Dict[str, Any]:
        """Tìm NPC thương nhân gần nhất (Leah / Silvia / Potion Merchant) trong tầm nhìn."""
        if self.is_ready:
            try:
                res = self._call("findMerchantNpc")
                if res and isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi find_merchant_npc: {e}")
        return {"found": False}

    def interact_merchant_npc(self) -> Dict[str, Any]:
        """Tương tác/đối thoại với NPC thương nhân (Rhea/Leah/Silvia/...) để mở phiên giao dịch bán đồ."""
        if self.is_ready:
            try:
                res = self._call("interactMerchantNpc")
                if res and isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi interact_merchant_npc: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "NOT_ATTACHED"}

    def close_merchant_npc(self) -> Dict[str, Any]:
        """Đóng phiên giao dịch với NPC thương nhân (gửi packet C1:31, tắt giao diện shop)."""
        if self.is_ready:
            try:
                res = self._call("closeMerchantNpc")
                if res and isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi close_merchant_npc: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "NOT_ATTACHED"}

    def sell_moss_plus_items(self) -> Dict[str, Any]:
        """Tự động bán các món đồ Moss cấp độ +5, +6, +7 cho NPC thương nhân (bảo vệ tuyệt đối Divine/Rồng/Exc/Socket/Set/Ngọc/+8+)."""
        if self.is_ready:
            try:
                res_str = self._call("sellMossPlusItems")
                if res_str:
                    return json.loads(res_str) if isinstance(res_str, str) else res_str
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi sell_moss_plus_items: {e}")
        return {"sold": 0, "error": "not_ready"}


    def start_native_mirror_turbo(self, slot: Optional[int] = None, interval_ms: int = 35, max_duration_ms: int = 15000) -> Dict[str, Any]:
        """Kích hoạt Turbo Sniping Native In-Process bên trong tiến trình game (0ms IPC overhead)."""
        if self.is_ready:
            try:
                arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
                res = self._call("startNativeMirrorTurbo", arg_slot, int(interval_ms), int(max_duration_ms))
                if isinstance(res, str):
                    try:
                        return json.loads(res)
                    except Exception:
                        pass
                if isinstance(res, dict):
                    return res
                if bool(res):
                    return {"success": True}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi start_native_mirror_turbo: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "not_ready"}

    def stop_native_mirror_turbo(self) -> Dict[str, Any]:
        """Dừng Turbo Sniping Native In-Process."""
        if self.is_ready:
            try:
                res = self._call("stopNativeMirrorTurbo")
                if isinstance(res, str):
                    try:
                        return json.loads(res)
                    except Exception:
                        pass
                if isinstance(res, dict):
                    return res
                return {"stopped": True}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi stop_native_mirror_turbo: {e}")
        return {"stopped": False}

    def get_native_mirror_turbo_status(self) -> Dict[str, Any]:
        """Lấy trạng thái Turbo Sniping Native In-Process."""
        if self.is_ready:
            try:
                res = self._call("getNativeMirrorTurboStatus")
                if isinstance(res, str):
                    return json.loads(res)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {"running": False, "packetsSent": 0, "entered": False}

    def enter_mirror(self, slot: Optional[int] = None) -> Dict[str, Any]:
        """Gửi lệnh native vào cửa sự kiện Double Goer (Mirror of Dimensions)."""
        if self.is_ready:
            try:
                arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
                res = self._call("enterMirror", arg_slot)
                if isinstance(res, str):
                    try:
                        res = json.loads(res)
                    except Exception:
                        pass
                if isinstance(res, dict):
                    return res
                if bool(res):
                    return {"success": True}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi enter_mirror: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "not_ready"}

    def get_mirror_ticket_info(self) -> Dict[str, Any]:
        """Kiểm tra vé Mirror of Dimensions (item 7279) trong hòm đồ (có retry nếu đang load map)."""
        if self.is_ready:
            for attempt in range(3):
                try:
                    res = self._call("getMirrorTicketInfo")
                    if isinstance(res, str):
                        res = json.loads(res)
                    if isinstance(res, dict):
                        if res.get("hasTicket") or res.get("hasOnlySign"):
                            return res
                        if res.get("slots") is not None and attempt > 0:
                            return res
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] Lỗi get_mirror_ticket_info (attempt {attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(0.15)
        return {"hasTicket": False, "count": 0, "slots": []}

    def teleport_to_event_map(self) -> bool:
        """Dịch chuyển trực tiếp vào Bản đồ Sự Kiện (Event Map - Gate 507) qua native. Nếu đã ở trong map rồi thì thôi."""
        if self.is_ready:
            try:
                tele = self.get_player_info()
                if tele and tele.get("mapId") in (40, 53, 65, 66, 67, 68):
                    return True
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
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Double Goer (Map ID 65-68) hay không."""
        if self.is_ready:
            try:
                tele = self.get_player_info()
                if tele and "mapId" in tele and tele["mapId"] >= 0:
                    return tele["mapId"] in (65, 66, 67, 68)
                return bool(self._call("isMirrorEventMap"))
            except Exception:
                pass
        return False

    def enter_devil(self, level: Optional[int] = None, slot: Optional[int] = None) -> Dict[str, Any]:
        """Gửi lệnh native vào cửa sự kiện Devil Square (không cần click NPC)."""
        if self.is_ready:
            try:
                arg_lvl = int(level) if (level is not None and int(level) >= 0) else None
                arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
                res = self._call("enterDevil", arg_lvl, arg_slot)
                if isinstance(res, str):
                    try:
                        res = json.loads(res)
                    except Exception:
                        pass
                if isinstance(res, dict):
                    return res
                if bool(res):
                    return {"success": True}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi enter_devil: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "not_ready"}

    def get_devil_ticket_info(self) -> Dict[str, Any]:
        """Kiểm tra vé Devil's Square Invitation (item 7187) trong hòm đồ."""
        if self.is_ready:
            for attempt in range(2):
                try:
                    res = self._call("getDevilTicketInfo")
                    if isinstance(res, str):
                        res = json.loads(res)
                    if isinstance(res, dict):
                        return res
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] Lỗi get_devil_ticket_info: {e}")
                if attempt < 1:
                    time.sleep(0.1)
        return {"hasTicket": False, "count": 0, "slots": []}

    def click_devil_npc(self, npc_ptr: int = 0) -> bool:
        """Kích hoạt đối thoại NPC Charon sự kiện Devil Square."""
        if self.is_ready:
            try:
                res = self._call("clickDevilNpc", int(npc_ptr) if npc_ptr else None)
                if res:
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi click_devil_npc: {e}")
        return False

    def is_devil_event_map(self) -> bool:
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Devil Square (Map ID 9 hoặc 32) hay không."""
        if self.is_ready:
            try:
                tele = self.get_player_info()
                if tele and "mapId" in tele and tele["mapId"] in (9, 32):
                    return True
                return bool(self._call("isDevilEventMap"))
            except Exception:
                pass
        return False

    def add_stats(self, str_pts: int = 0, agi_pts: int = 0, vit_pts: int = 0, ene_pts: int = 0, cmd_pts: int = 0) -> bool:
        """Cộng điểm chỉ số cho nhân vật qua các lệnh chat native /f, /a, /v, /e, /c."""
        if not self.is_ready:
            return False
        try:
            if str_pts > 0:
                self.send_chat(f"/f {str_pts}")
                time.sleep(0.20)
            if agi_pts > 0:
                self.send_chat(f"/a {agi_pts}")
                time.sleep(0.20)
            if vit_pts > 0:
                self.send_chat(f"/v {vit_pts}")
                time.sleep(0.20)
            if ene_pts > 0:
                self.send_chat(f"/e {ene_pts}")
                time.sleep(0.20)
            if cmd_pts > 0:
                self.send_chat(f"/c {cmd_pts}")
                time.sleep(0.20)
            return True
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi add_stats: {e}")
            return False

    def do_reset(self) -> Dict[str, Any]:
        """Gửi lệnh Reset nhân vật qua Native Chat."""
        if not self.is_ready:
            return {"ok": False, "error": "not_ready"}
        try:
            ok = self.send_chat("/reset")
            return {"ok": bool(ok)}
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi do_reset: {e}")
            return {"ok": False, "error": str(e)}

    get_latest_telemetry = get_player_info

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

    def auto_login(self, server: int = 1, account: str = "", character: str = "", password: str = "") -> Dict[str, Any]:
        """Gửi lệnh AutoLogin native vào GameAssembly.dll, hỗ trợ QuickSwitch và submit mật khẩu trực tiếp."""
        if self.is_ready:
            try:
                res = self._call("autoLogin", int(server), str(account), str(character), str(password))
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi auto_login: {e}")
                return {"ok": False, "err": str(e)}
        return {"ok": False, "err": "not_ready"}

    def get_autologin_status(self) -> Dict[str, Any]:
        """Lấy trạng thái thực thi AutoLogin trên Unity Main Thread."""
        if self.is_ready:
            try:
                res = self._call("getAutoLoginStatus")
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception as e:
                pass
        return {"done": False, "submitted": False, "stage": "disconnected"}

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

