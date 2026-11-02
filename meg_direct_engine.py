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
    "get_player": "0x107FBF0",
    "get_game_ui": "0x107FF00",
    "get_world": "0x107FD40",
    "get_auto_login": "0x107F2D0",
    "get_window_handler": "0x1078690",
    "game_update": "0x10701F0",
    "game_ui_update": "0x1393AC0",
    "game_type_info": "0x553B900",
    "item_storage_type_info": "0x5540838",
    "mlogin_ui_type_info": "0x55286D0",
    "mlogin_submit": "0x1C35790",
    "mlogin_token_login": "0x1C307B0",
    "set_auto_login": "0xEBF7C0",
    "move_to": "0xB893E0",
    "start_auto_move": "0xB93B10",
    "stop_auto_move": "0xB98400",
    "chat_send": "0x1331880",
    "chat_frame_send": "0x1331880",
    "chat_send_cmd": "0xEFE530",
    "command_mgr_process": "0xEFE530",
    "static_chat_send": "0xF1F710",
    "chat_update": "0x1334D30",
    "helper_start": "0x27776F0",
    "helper_stop": "0x277C760",
    "helper_action": "0x25DC620",
    "helper_toggle": "0x25DC620",
    "helper_send_bf51": "0x277BDD0",
    "helper_req_start": "0x27776F0",
    "helper_req_stop": "0x277C760",
    "ui_location_frame": "0x80",
    "location_helper_on": "0x60",
    "location_helper_off": "0x68",
    "location_update_helper": "0x25A5750",
    "npc_talk": "0x1015210",
    "npc_close_talk": "0x1025540",
    "npc_click": "0x1013520",
    "get_config": "0x107B360",
    "get_user_2fa": "0x1077980",
    "inv_trash_item": "0x0",
    "inv_sell_item": "0x0",
    "inv_drop_item": "0x0",
    "user_inv_trash": "0x144C8A0",
    "user_inv_action": "0x1441DF0",
    "item_storage_drop": "0x222CD00",
    "merchant_sell_item": "0x2743520",
    "slot_quick_action": "0x23E24A0",
    "item_storage_move": "0x22317E0",
    "window_show": "0x258FBC0",
    "window_hide": "0x25986B0",
    "window_set_state": "0x258A730",
    "window_toggle": "0x2589E10",
    "button_press": "0x464E520",
    "unity_event_invoke": "0x4588220",
    "moss_roll": "0x27A9760",
    "moss_open": "0x25EA7C0",
    "moss_roll_handler": "0x27A6230",
    "moss_init": "0x27A77C0",
    "moss_select_cat": "0x27A8510",
    "moss_send_roll": "0x23F8BE0",
    "moss_roll_click": "0x27A8F90",
    "moss_window_close": "0x25986B0",
    "game_object_set_active": "0x456F2B0",
    "component_get_game_object": "0x456AE90",
    "mirror_enter": "0xF94450",
    "mirror_enter_alt": "0xF94B00",
    "mirror_npc_click": "0xF927B0",
    "mirror_is_event_map": "0xF93060",
    "mirror_teleport_event": "0x37F2C0",
    "item_mirror_ticket": 7279,
    "devil_enter": "0xF75CF0",
    "devil_npc_click": "0xF760C0",
    "devil_is_event_map": "0xF75C40",
    "item_devil_ticket": 7187,
    "item_devil_ticket_master": 6702,
    "get_gs_connection": "0x1077910",
    "gs_send": "0x11F9280",
    "gs_send_alt": "0x11F9280",
    "player_point": "0x238",
    "player_master_point": "0x23C",
    "player_reset_count": "0x2B4",
    "player_name": "0x28",
    "player_level": "0x30",
    "player_class": "0x34",
    "player_coord": "0x68",
    "player_move": "0xE8",
    "player_inventory": "0x1B0",
    "player_helper": "0x1E0",
    "player_last_coord": "0x508",
    "auto_move_working": "0x4C0",
    "auto_move_type": "0x4C4",
    "auto_move_helper": "0x4C8",
    "auto_move_dest": "0x4D0",
    "move_flag": "0x3C",
    "helper_state": "0x20",
    "inventory_items": "0x28",
    "game_world": "0x200",
    "world_scene_index": "0x20",
    "viewport": "0x110",
    "ui_chat_frame": "0x50",
    "ui_moss_window": "0x1C8",
    "ui_merchant_window": "0x198",
    "ui_inventory_window": "0x188",
    "ui_warehouse_window": "0x288",
    "ui_gremory_window": "0x168",
    "gremory_type_info": "0x553B900",
    "gremory_claim_item": "0xFD85C0",
    "gremory_instance_offset": "0x138",
    "gremory_dict_offset": "0x20"
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

var coordBuf = Memory.alloc(64);

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

var nativeWindowToggle = null;
try {
    var wtOff = off('__WINDOW_TOGGLE__');
    if (!wtOff.isNull()) {
        nativeWindowToggle = new NativeFunction(baseAddr.add(wtOff), 'void', ['pointer', 'pointer']);
    }
} catch (eWT) {}

var nativeButtonPress = null;
try {
    var bpOff = off('__BUTTON_PRESS__');
    if (!bpOff.isNull()) {
        nativeButtonPress = new NativeFunction(baseAddr.add(bpOff), 'void', ['pointer', 'pointer']);
    }
} catch (eBP) {}

var nativeUnityEventInvoke = null;
try {
    var ueiOff = off('__UNITY_EVENT_INVOKE__');
    if (!ueiOff.isNull()) {
        nativeUnityEventInvoke = new NativeFunction(baseAddr.add(ueiOff), 'void', ['pointer', 'pointer']);
    }
} catch (eUEI) {}

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
        nativeMirrorEnter = new NativeFunction(baseAddr.add(meOff), 'void', ['int']);
    }
} catch (eMirrorEnter) {}

var nativeMirrorEnterAlt = null;
try {
    var meaOff = off('__MIRROR_ENTER_ALT__');
    if (!meaOff.isNull()) {
        nativeMirrorEnterAlt = new NativeFunction(baseAddr.add(meaOff), 'void', ['int']);
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
        nativeNpcTalk = new NativeFunction(baseAddr.add(ntOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eNT) {}

function invokeNpcTalk(body) {
    if (!body || body.isNull()) return false;
    var nm = getNpcManagerPtr();
    if (nativeNpcTalk !== null) {
        try {
            if (nm && !nm.isNull()) {
                nativeNpcTalk(nm, body, ptr(0));
            } else {
                nativeNpcTalk(body, body, ptr(0));
            }
            return true;
        } catch (eNT) {}
    }
    return false;
}

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

var nativeItemStorageMove = null;
try {
    var ismOff = off('__ITEM_STORAGE_MOVE__');
    if (!ismOff.isNull()) {
        nativeItemStorageMove = new NativeFunction(baseAddr.add(ismOff), 'void', ['pointer', 'int', 'int', 'int', 'int', 'pointer']);
    }
} catch (eISM) {}

var nativeInvTrashItem = null;
var nativeInvTrashItem3 = null;
try {
    var itiOff = off('__INV_TRASH_ITEM__');
    if (!itiOff.isNull()) {
        try {
            nativeInvTrashItem = new NativeFunction(baseAddr.add(itiOff), 'void', ['int', 'pointer']);
        } catch (eIT1) {}
        try {
            nativeInvTrashItem3 = new NativeFunction(baseAddr.add(itiOff), 'void', ['int', 'pointer', 'pointer']);
        } catch (eIT2) {}
    }
} catch (eInvTrash) {}

function invokeNativeTrash(slotNumber, coordPointer) {
    // Vô hiệu hóa triệt để gọi native C++ function 0x1404AD0 nhằm chống crash SEH 0xC0000005
    // Thay vào đó việc ném đồ tại chỗ 100% sử dụng GameServer packet 0x23 an toàn tuyệt đối.
    return false;
}

var nativeInvDropItem = nativeInvTrashItem;

var nativeInvSellItem = null;
try {
    var isiOff = off('__INV_SELL_ITEM__');
    if (!isiOff.isNull()) {
        nativeInvSellItem = new NativeFunction(baseAddr.add(isiOff), 'void', ['int', 'pointer']);
    }
} catch (eInvSell) {}

var nativeGetConfig = null;
try {
    var gcOff = off('__GET_CONFIG__');
    if (!gcOff.isNull()) {
        nativeGetConfig = new NativeFunction(baseAddr.add(gcOff), 'pointer', []);
    } else {
        nativeGetConfig = new NativeFunction(baseAddr.add(ptr('0x107B360')), 'pointer', []);
    }
} catch (eGC) {}

var nativeGetUser2FA = null;
try {
    var u2faOff = off('__GET_USER_2FA__');
    if (!u2faOff.isNull()) {
        nativeGetUser2FA = new NativeFunction(baseAddr.add(u2faOff), 'pointer', []);
    } else {
        nativeGetUser2FA = new NativeFunction(baseAddr.add(ptr('0x1077980')), 'pointer', []);
    }
} catch (e2fa) {}

var nativeUserInvTrash = null;
try {
    var uitOff = off('__USER_INV_TRASH__');
    if (!uitOff.isNull()) {
        nativeUserInvTrash = new NativeFunction(baseAddr.add(uitOff), 'void', ['int', 'int', 'pointer']);
    } else {
        nativeUserInvTrash = new NativeFunction(baseAddr.add(ptr('0x144C8A0')), 'void', ['int', 'int', 'pointer']);
    }
} catch (eUIT) {}

var nativeUserInvAction = null;
try {
    var uiaOff = off('__USER_INV_ACTION__');
    if (!uiaOff.isNull()) {
        nativeUserInvAction = new NativeFunction(baseAddr.add(uiaOff), 'void', ['int', 'pointer']);
    } else {
        nativeUserInvAction = new NativeFunction(baseAddr.add(ptr('0x1441DF0')), 'void', ['int', 'pointer']);
    }
} catch (eUIA) {}

var nativeItemStorageDrop = null;
try {
    var isdOff = off('__ITEM_STORAGE_DROP__');
    if (!isdOff.isNull()) {
        nativeItemStorageDrop = new NativeFunction(baseAddr.add(isdOff), 'void', ['pointer', 'pointer']);
    } else {
        nativeItemStorageDrop = new NativeFunction(baseAddr.add(ptr('0x222CD00')), 'void', ['pointer', 'pointer']);
    }
} catch (eISD) {}

var nativeUserInvSub32 = null;
try {
    nativeUserInvSub32 = new NativeFunction(baseAddr.add(ptr('0x144B9A0')), 'void', ['int', 'pointer']);
} catch (eSub32) {}

var nativeUserInvSub61 = null;
try {
    nativeUserInvSub61 = new NativeFunction(baseAddr.add(ptr('0x144C370')), 'void', ['int', 'pointer']);
} catch (eSub61) {}

var nativeUserInvSubC7 = null;
try {
    nativeUserInvSubC7 = new NativeFunction(baseAddr.add(ptr('0x144F290')), 'void', ['int', 'pointer']);
} catch (eSubC7) {}

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
var il2cpp_gchandle_new = null;
var il2cpp_gchandle_free = null;
try {
    var expCorlib = ga.findExportByName('mono_domain_get_corlib');
    var expClassFromName = ga.findExportByName('il2cpp_class_from_name');
    var expArrayNew = ga.findExportByName('il2cpp_array_new');
    var expGCHandleNew = ga.findExportByName('il2cpp_gchandle_new');
    var expGCHandleFree = ga.findExportByName('il2cpp_gchandle_free');
    if (expCorlib) mono_domain_get_corlib = new NativeFunction(expCorlib, 'pointer', []);
    if (expClassFromName) il2cpp_class_from_name = new NativeFunction(expClassFromName, 'pointer', ['pointer', 'pointer', 'pointer']);
    if (expArrayNew) il2cpp_array_new = new NativeFunction(expArrayNew, 'pointer', ['pointer', 'size_t']);
    if (expGCHandleNew) il2cpp_gchandle_new = new NativeFunction(expGCHandleNew, 'uint32', ['pointer', 'int']);
    if (expGCHandleFree) il2cpp_gchandle_free = new NativeFunction(expGCHandleFree, 'void', ['uint32']);
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

function createManagedByteArray(bytes) {
    try {
        if (il2cpp_array_new === null) return null;
        var bClass = getByteClass();
        if (!bClass || bClass.isNull()) return null;
        var arr = il2cpp_array_new(bClass, bytes.length);
        if (arr.isNull()) return null;
        var raw = arr.add(0x20);
        for (var i = 0; i < bytes.length; i++) {
            raw.add(i).writeU8(bytes[i] & 0xFF);
        }
        return arr;
    } catch (e) {
        return null;
    }
}

function sendGSPacketDirect(gs, arr) {
    if (!gs || gs.isNull() || !arr || arr.isNull()) return false;
    var sent = false;
    if (nativeGSSend !== null) {
        try { nativeGSSend(gs, arr, 0, 0, ptr(0)); sent = true; } catch (eS1) {}
    }
    if (!sent && nativeGSSendAlt !== null) {
        try { nativeGSSendAlt(gs, arr, 0, 0, ptr(0)); sent = true; } catch (eS2) {}
    }
    return sent;
}

function sendGSPacket(bytes) {
    try {
        var gs = getGSConnection();
        if (gs.isNull()) return false;
        var arr = createManagedByteArray(bytes);
        if (!arr || arr.isNull()) return false;
        return sendGSPacketDirect(gs, arr);
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
        // BẢO VỆ TUYỆT ĐỐI: Không bao giờ vứt các slot trang bị trên người (0..11)
        if (s < 12) return false;
        var tx = parseInt(targetX) & 0xFF;
        var ty = parseInt(targetY) & 0xFF;
        // In MEGAMU protocol packet 0x23: [0xC1, 0x06, 0x23, targetX, targetY, slot]
        return sendGSPacket([0xC1, 0x06, 0x23, tx, ty, s]);
    } catch (eDropPkt) {
        return false;
    }
}

function sendSellPacket(slot) {
    try {
        var s = parseInt(slot) & 0xFF;
        // BẢO VỆ TUYỆT ĐỐI: Không bao giờ bán các slot trang bị trên người (0..11)
        if (s < 12) return false;
        // Chuẩn protocol bán đồ NPC MEGAMU: [0xC1, 0x04, 0x33, slot]
        return sendGSPacket([0xC1, 0x04, 0x33, s]);
    } catch (eSellPkt) {
        return false;
    }
}

function sendMirrorEnterPacket(slot) {
    try {
        var rel = (slot >= 12) ? (slot - 12) : slot;
        return sendGSPacket([0xC1, 0x05, 0xBF, 0x0E, rel & 0xFF]);
    } catch (eMirrorPkt) {
        return false;
    }
}

function sendLugardTalkPacket() {
    try {
        var lugard = findLugardNpc();
        if (lugard && !lugard.isNull()) {
            var npcKey = -1;
            try { npcKey = lugard.add(0x20).readS32(); } catch (eK) {}
            if (npcKey > 0) {
                var kLow = npcKey & 0xFF;
                var kHigh = (npcKey >> 8) & 0xFF;
                sendGSPacket([0xC1, 0x05, 0x30, kLow, kHigh]);
                return true;
            }
        }
        return false;
    } catch (eLTP) {
        return false;
    }
}

function sendCharonTalkPacket() {
    try {
        var charon = findCharonNpc();
        if (charon && !charon.isNull()) {
            var npcKey = -1;
            try { npcKey = charon.add(0x20).readS32(); } catch (eK) {}
            if (npcKey > 0) {
                var kLow = npcKey & 0xFF;
                var kHigh = (npcKey >> 8) & 0xFF;
                sendGSPacket([0xC1, 0x05, 0x30, kLow, kHigh]);
                return true;
            }
        }
        return false;
    } catch (eCTP) {
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

function ensureDropAllowed() {
    var ok = true;
    try {
        if (nativeGetConfig !== null) {
            var cfg = nativeGetConfig();
            if (!cfg.isNull()) {
                var ci = cfg.add(0x20).readPointer();
                if (!ci.isNull()) {
                    ci.add(0xE1).writeU8(0); // 0 = Security2FAEnable false (cho phép ném đồ)
                }
            }
        }
    } catch (eCfg) {}
    try {
        if (nativeGetUser2FA !== null) {
            var u2fa = nativeGetUser2FA();
            if (!u2fa.isNull()) {
                u2fa.add(0x20).writeU8(0); // 0 = Mở khóa 2FA cấm vứt đồ
            }
        }
    } catch (e2FA) {}
    // 1. Bật cờ cho phép tương tác và giải phóng toàn bộ khóa trong ItemStorage
    try {
        var isTiOffset = off('__ITEM_STORAGE_TYPE_INFO__');
        if (!isTiOffset.isNull()) {
            var isTypeInfo = baseAddr.add(isTiOffset).readPointer();
            if (!isTypeInfo.isNull()) {
                var isStatic = isTypeInfo.add(ptr('0xB8')).readPointer();
                if (!isStatic.isNull()) {
                    isStatic.add(0x98).writeU8(1); // InventoryInteractionAvailable = true
                    isStatic.add(0x99).writeU8(0); // InventoryInteractionBlock = false
                    isStatic.add(0x9A).writeU8(0); // IsQuickDropActive = false (TUYỆT ĐỐI PHẢI LÀ 0 ĐỂ MỞ KHÓA THÙNG ĐỒ VÀ NHÂN VẬT!)
                    // Xóa triệt để các con trỏ kẹt thao tác kéo thả/hủy đồ
                    isStatic.add(0x00).writePointer(ptr(0)); // DragSlot = null
                    isStatic.add(0x08).writePointer(ptr(0)); // HoverSlot = null
                    isStatic.add(0x18).writePointer(ptr(0)); // DiscardSlot = null
                    isStatic.add(0x20).writePointer(ptr(0)); // SellingSlot = null
                    isStatic.add(0x28).writePointer(ptr(0)); // _SelectSlot = null
                }
            }
        }
    } catch (e2) {}

    // 2. Mở khóa và reset chế độ tương tác bị kẹt trong MInventoryWindow
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var invOff = off('__UI_INVENTORY_WINDOW__');
                var invWin = invOff.isNull() ? gui.add(ptr('0x188')).readPointer() : gui.add(invOff).readPointer();
                if (!invWin.isNull()) {
                    // Reset enum tương tác về None (0 = None, 1 = Repair, 2 = Divide, 3 = Disassembly, 4 = QuickMove, 5 = QuickDrop)
                    invWin.add(0x158).writeU32(0); // LDHAEAKCJKE = None
                    invWin.add(0x160).writePointer(ptr(0)); // MKGKAFADNHG = null

                    // Ẩn QuickDropWindow (0xF8) nếu đang kẹt
                    var qdWin = invWin.add(0xF8).readPointer();
                    if (!qdWin.isNull()) {
                        if (nativeWindowHide !== null) {
                            try { nativeWindowHide(qdWin, ptr(0)); } catch (eQD) {}
                        }
                        qdWin.add(0x48).writeU8(0);
                    }

                    // Ẩn DivideWindow (0xC8) nếu đang kẹt
                    var divWin = invWin.add(0xC8).readPointer();
                    if (!divWin.isNull()) {
                        if (nativeWindowHide !== null) {
                            try { nativeWindowHide(divWin, ptr(0)); } catch (eDIV) {}
                        }
                        divWin.add(0x48).writeU8(0);
                    }
                }

                // 3. Phục hồi cửa sổ Moss nếu đang kẹt spinner/loading
                var mossOff = off('__UI_MOSS_WINDOW__');
                var mossWin = mossOff.isNull() ? gui.add(ptr('0x1C8')).readPointer() : gui.add(mossOff).readPointer();
                if (!mossWin.isNull()) {
                    ensureMossRollButtonActive(mossWin, true);
                }
            }
        }
    } catch (eInv) {}

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
        var te = itemPtr.add(0x58).readPointer();
        if (!te.isNull()) {
            // Priority 1: TableItem.HKLAHJEGHML (+0x68) = Index
            try {
                var fieldIdx = te.add(0x68).readS32();
                if (fieldIdx >= 0 && fieldIdx < 65536) return fieldIdx;
            } catch (eF) {}

            // Priority 2: (Section * 512 + Type) from TableItem (+0x58, +0x5C)
            try {
                var sec = te.add(0x58).readS32();
                var type = te.add(0x5C).readS32();
                if (sec >= 0 && sec < 16 && type >= 0 && type < 512) {
                    var calcIdx = (sec * 512) + type;
                    if (calcIdx >= 0 && calcIdx < 65536) return calcIdx;
                }
            } catch (eST) {}
        }
    } catch (e1) {}

    // Priority 3: Fallback from Item (+0x60)
    try {
        idx = itemPtr.add(0x60).readS32();
        if (idx >= 0 && idx < 65536) return idx;
    } catch (e2) {}

    return -1;
}

function readItemProps(itemPtr) {
    var p = {
        itemIndex: -1,
        itemLevel: 0,
        durability: 0,
        skill: 0,
        luck: 0,
        option: 0,
        excOpt: 0,
        ancOpt: 0,
        sockOpt: 0,
        harmonyOpt: 0
    };
    if (!itemPtr || itemPtr.isNull()) return p;
    try {
        p.itemIndex = readItemIndex(itemPtr);
        p.itemLevel = itemPtr.add(0x10).readS32();
        p.skill = itemPtr.add(0x14).readS32();
        p.luck = itemPtr.add(0x18).readS32();
        p.excOpt = itemPtr.add(0x20).readS32();
        p.ancOpt = itemPtr.add(0x24).readS32();
        p.sockOpt = itemPtr.add(0x28).readS32();
        p.harmonyOpt = itemPtr.add(0x2C).readS32();
    } catch (eAll) {}
    return p;
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
    // Toàn bộ các item Master / Ruud / Archangel / Season cao cấp (type >= 30 trong sec 0..11):
    if (type >= 30 && sec <= 11) return true;

    // Set Rồng Đỏ (Dragon Set): Sec 7..11, Type 1
    // Set Rồng Đen (Black Dragon): Sec 7..11, Type 16
    // Set Dark Phoenix: Sec 7..11, Type 17
    // Set Great Dragon: Sec 7..11, Type 21
    // Set Nữ Thần (Divine Set - Elf): Sec 7..11, Type 18
    // Set Dragon Knight (Hiệp sĩ rồng): Sec 7..11, Type 29
    // Set Dark Devil / Dragon Soul / các set rồng mở rộng: Sec 7..11 (Type 30, 31)
    if ((type === 1 || type === 16 || type === 17 || type === 18 || type === 21 || type === 29 || type === 30 || type === 31) && (sec >= 7 && sec <= 11)) {
        return true;
    }
    // Các set cao cấp khác: Grand Soul (3), Dark Soul (15), Hurricane (20), Red Spirit (19), Dark Master (22), Storm Crow (23), Valiant (24), Glorious (25)
    if ((type === 3 || type === 15 || type === 19 || type === 20 || type === 22 || type === 23 || type === 24 || type === 25) && (sec >= 7 && sec <= 11)) {
        return true;
    }
    // Khiên Rồng & Khiên cao cấp (Sec 6): Type 7 (Dragon Shield), >= 17 (Dragon Slayer, Crimson Glory, Salamander, Frost Barrier, Guardian, Cross...)
    if (sec === 6 && (type === 7 || type >= 17)) return true;
    // Vũ khí Rồng: Chaos Dragon Axe (Sec 1, Type 6), Dragon Spear (Sec 3, Type 10)
    if (sec === 1 && type === 6) return true;
    if (sec === 3 && type === 10) return true;
    // Vũ khí Divine Archangel (Tuyệt Tác Thần / Thiên Sứ) & vũ khí cao cấp:
    if (sec === 0 && (type === 19 || type === 31 || type === 32)) return true; // DAA Sword, Blessed DAA Sword, DAA Claw
    if (sec === 1 && (type === 18 || type === 19)) return true; // DAA Axe
    if (sec === 2 && (type === 13 || type === 21)) return true; // DAA Scepter, Blessed DAA Scepter
    if (sec === 4 && (type === 18 || type === 26)) return true; // DAA Bow, Blessed DAA Bow
    if (sec === 5 && (type === 10 || type === 34)) return true; // DAA Staff, Blessed DAA Staff

    // 2. Phân loại theo tên native của vật phẩm trong Game Memory (Hỗ trợ đa ngôn ngữ EN, PT, ES, VN):
    var name = getItemName(itemPtr).toLowerCase();
    if (name.length > 0) {
        var keywords = [
            "divine", "divino", "divina", "archangel", "arcanjo", "thiên sứ", "nữ thần",
            "dragon", "dragao", "dragão", "rồng",
            "bloodangel", "darkangel", "holyangel", "awakening", "blue eye", "silver heart", "manticore", "brilliant", "apocalypse", "lightning", "ruud"


        ];
        for (var k = 0; k < keywords.length; k++) {
            if (name.indexOf(keywords[k]) !== -1) {
                return true;
            }
        }
    }
    return false;
}

function isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl) {
    if (itemIndex < 0) return true; // Không rõ item -> bảo vệ an toàn

    // 1. Đồ Divine, Đồ Rồng, Master/Ruud/High-tier
    if (isDivineOrDragonItem(itemPtr, itemIndex)) return true;

    // 2. Đồ Hoàn Hảo (Excellent)
    if (excOpt > 0) return true;

    // 3. Đồ Thần (Ancient / Set Item)
    if (ancOpt > 0) return true;

    // 4. Đồ Socket / 380
    if (sockOpt > 0) return true;

    // 5. Đồ Gia Cường Đá Tạo Hóa (Harmony)
    if (harmonyOpt > 0) return true;

    // 6. Đồ cấp cao: Giữ lại toàn bộ đồ từ +5 trở lên (+5, +6, +7, +8, +9, +10, +11, +12, +13, +14, +15)
    // Cho phép vứt: Đồ thường từ +0 đến +4 không Exc/Ancient/Socket (kể cả có Luck/Skill từ Moss)
    var effectiveMax = 4;
    if (maxJunkLvl !== undefined && maxJunkLvl !== null && maxJunkLvl >= 0) {
        effectiveMax = parseInt(maxJunkLvl);
    } else if (mossCat !== null && mossCat !== undefined && mossCat >= 0) {
        effectiveMax = 6;
    }
    if (effectiveMax <= 4) {
        if (itemLevel >= 5) return true;
    } else {
        if (itemLevel > effectiveMax) return true;
    }

    // 7. Toàn bộ ngọc, vé sự kiện, cánh, thú cưỡi, nhẫn, dây chuyền, sách phép, cuộn kỹ năng (sec 12..15)
    var sec = Math.floor(itemIndex / 512);
    if (sec >= 12 && sec <= 15) return true;

    // 8. Giới hạn phạm vi theo danh mục Moss đang quay:
    // Nếu đang quay Moss danh mục X thì CHỈ các món đồ rác thường thuộc danh mục X mới được phép dọn!
    // Các trang bị khác loại người chơi mang theo người TUYỆT ĐỐI KHÔNG ĐƯỢC ĐỘNG VÀO.
    if (mossCat !== null && mossCat !== undefined && mossCat >= 0) {
        var matchCat = false;
        // Khớp chuẩn 100% với danh mục Moss trong Game MEGAMU (MOSS_CAT_OPTIONS):
        if (mossCat === 0 && (sec === 0 || sec === 1 || sec === 3)) matchCat = true;       // 0: Kiếm, Rìu, Thương (Sword, Axe, Spear)
        else if (mossCat === 1 && sec === 2) matchCat = true;                              // 1: Chùy & Trượng (Mace, Scepter)
        else if (mossCat === 2 && sec === 4) matchCat = true;                              // 2: Cung & Nỏ (Bow, Crossbow)
        else if (mossCat === 3 && sec === 5) matchCat = true;                              // 3: Gậy Phép & Sách (Staff, Book)
        else if (mossCat === 4 && sec === 6) matchCat = true;                              // 4: Khiên (Shield)
        else if (mossCat === 5 && (sec === 12 || sec === 13)) matchCat = true;             // 5: Trang Sức (Pendant, Ring)
        else if (mossCat >= 6 && sec <= 11) matchCat = true;                               // 6..11: Nhóm ngọc (Soul/Bless/Chaos quay ra mọi loại đồ)
        
        // Không thuộc loại đồ đang quay của Moss -> BẢO VỆ TUYỆT ĐỐI
        if (!matchCat) return true;
    }

    return false; // Chỉ những món đồ rác thường (+0..+4 không Exc/Ancient/Socket/Harmony/Divine) mới bị dọn
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
    try {
        ensureThreadAttached();
        var p = getPlayerPtr();
        if (p.isNull()) return false;

        var str = il2cpp_string_new(Memory.allocUtf8String(cmdText));
        if (str.isNull()) return false;

        // 1. Ưu tiên gửi qua static_chat_send (Mega.Chat.LLGBNHILFIE - RVA 0xF1F710)
        if (nativeStaticChatSend !== null) {
            try {
                nativeStaticChatSend(str, ptr(0));
                return true;
            } catch (eStatic) {}
        }

        // 2. Fallback gửi qua ChatFrame (IHMCLDOIMCA - RVA 0x1331880)
        var cf = getChatFrameInstance();
        if (!cf.isNull() && sendChatMessageNative !== null) {
            try {
                sendChatMessageNative(cf, str, 0, ptr(0));
                return true;
            } catch (eCF) {}
        }

        // 3. Fallback cho lệnh '/' qua CommandManager (MLPKNNGGNPL - RVA 0xEFE530)
        if (cmdText.charAt(0) === '/' && nativeCommandManagerProcess !== null) {
            try {
                return nativeCommandManagerProcess(str, ptr(0));
            } catch (eCmd) {}
        }
    } catch (eDispatch) {}
    return false;
}

var pendingHelperAction = null;

function syncHelperUI(isActive) {
    // Để GameServer và client game tự động đồng bộ hóa icon MuHelper Play/Pause
    // một cách tự nhiên trên Main Render Thread khi nhận packet phản hồi từ server.
    // Tuyệt đối không can thiệp cưỡng ép MLocationFrame ngoài luồng tránh làm hỏng/đảo lộn icon game.
    return;
}

function dispatchHelperAction(act) {
    if (!act) return false;
    try {
        var p = getPlayerPtr();
        if (p.isNull()) return false;
        var h = ptr(0);
        try { h = p.add(off('__PLAYER_HELPER__')).readPointer(); } catch (eH0) {}

        var isAct = 0;
        if (!h.isNull()) {
            try { isAct = h.add(off('__HELPER_STATE__')).readU8(); } catch (eA) {}
        }

        if (act === 'start') {
            if (isAct === 1) {
                return true;
            }
            // 1. Gọi UserHelper.ALFOIEJFHLL (0x27776F0) để gửi packet BF:51, 00 (Start)
            var sent = false;
            if (!h.isNull() && nativeStartHelper !== null) {
                try { nativeStartHelper(h, ptr(0)); sent = true; } catch (eS1) {}
            }
            // 2. Fallback trực tiếp hàm gửi packet BF:51 (0x277BDD0) với tham số 0 (Start)
            if (!sent && nativeHelperSendBf51 !== null) {
                try { nativeHelperSendBf51(0, ptr(0)); sent = true; } catch (eBF0) {}
            }
            return true;
        } else if (act === 'stop') {
            if (isAct === 0) {
                return true;
            }
            // 1. Gọi UserHelper.BBLPCMHOBOE (0x277C760) để gửi packet BF:51, 01 (Stop)
            var sentStop = false;
            if (!h.isNull() && nativeStopHelper !== null) {
                try { nativeStopHelper(h, ptr(0)); sentStop = true; } catch (eSt1) {}
            }
            // 2. Fallback trực tiếp hàm gửi packet BF:51 (0x277BDD0) với tham số 1 (Stop)
            if (!sentStop && nativeHelperSendBf51 !== null) {
                try { nativeHelperSendBf51(1, ptr(0)); sentStop = true; } catch (eBF1) {}
            }
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

var coordBuf = Memory.alloc(64);
var cachedCoordKlass = ptr(0);
var shuttingDown = false;
var pendingMoveTarget = null;

function dispatchMoveTarget(target) {
    if (!target) return;
    try {
        var pMove = getPlayerPtr();
        if (pMove.isNull()) return;
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
    } catch (eQueueMove) {}
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
                        pendingHelperAction = null;
                        try { dispatchHelperAction(hAct); } catch (eH1) {}
                    }
                    if (pendingMoveTarget !== null) {
                        var target = pendingMoveTarget;
                        pendingMoveTarget = null;
                        dispatchMoveTarget(target);
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
            } else if (npcType > 0 && tx >= 20 && tx <= 26 && ty >= 222 && ty <= 228) {
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
            // NPC Lugard ID: 723 (Event Square), 540 (Elbeland), Type: 45 (0x2D)
            // Tọa độ Lugard: Event Square (229, 22), Elbeland (49, 216)
            var isLugard = false;
            if (npcType === 45 || npcType === 0x2d || npcType === -76 || npcType === 723 || npcType === 540) {
                isLugard = true;
            } else if (lowName.indexOf("lugard") !== -1 || lowName.indexOf("doppel") !== -1 || lowName.indexOf("mirror") !== -1 || lowName.indexOf("espelho") !== -1) {
                isLugard = true;
            } else if ((tx >= 225 && tx <= 235 && ty >= 18 && ty <= 26) || (tx >= 46 && tx <= 52 && ty >= 213 && ty <= 219)) {
                isLugard = true;
            }

            if (isLugard) {
                return body;
            }
        }
    } catch (eLugard) {}
    return null;
}

function getOrCreateLugardPtr(npcPtr) {
    if (npcPtr && npcPtr !== 0) {
        try {
            var p = ptr(npcPtr);
            if (!p.isNull()) return p;
        } catch (e) {}
    }
    var lugard = findLugardNpc();
    if (lugard && !lugard.isNull()) {
        return lugard;
    }
    return null;
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

function getOrCreateCharonPtr(npcPtr) {
    if (npcPtr && npcPtr !== 0) {
        try {
            var p = ptr(npcPtr);
            if (!p.isNull()) return p;
        } catch (e) {}
    }
    var charon = findCharonNpc();
    if (charon && !charon.isNull()) {
        return charon;
    }
    return null;
}

function checkDevilItem(itemPtr, idx) {
    var trueIdx = (idx !== undefined && idx !== null && idx > 0) ? idx : readItemIndex(itemPtr);
    var itName = getItemName(itemPtr) || "";
    var lowName = itName.toLowerCase();
    var itLevel = 0;
    try { itLevel = itemPtr.add(0x14).readS32(); } catch (eL) {}

    // 1. Nhận diện Master Ticket (Vé Master):
    // - ID: 6702 (0x1A2E), 7214 (0x1C2E), 6675
    // - Hoặc vé 7187 có level >= 7
    // - Hoặc tên có từ 'master' cùng với 'devil'/'invit'/'diabo'/'convite'
    var isMasterId = (trueIdx === 6702 || trueIdx === 7214 || trueIdx === 6675);
    var isMasterName = (lowName.indexOf("master") !== -1 && (
        lowName.indexOf("devil") !== -1 ||
        lowName.indexOf("invit") !== -1 ||
        lowName.indexOf("diabo") !== -1 ||
        lowName.indexOf("convite") !== -1
    ));
    var isMaster = isMasterId || isMasterName || (trueIdx === 7187 && itLevel >= 7);

    // 2. Nhận diện Normal Ticket (Vé thường):
    // - ID 7187 (level 1..6)
    // - Hoặc theo tên gọi chuẩn
    var isNormalId = (trueIdx === 7187 && !isMaster);
    var isNormalName = !isMaster && (
        lowName.indexOf("devil's invitation") !== -1 ||
        lowName.indexOf("devil invitation") !== -1 ||
        lowName.indexOf("convite do diabo") !== -1 ||
        lowName.indexOf("convite devil") !== -1 ||
        lowName.indexOf("devil square ticket") !== -1 ||
        (lowName.indexOf("devil") !== -1 && lowName.indexOf("invit") !== -1) ||
        (lowName.indexOf("diabo") !== -1 && lowName.indexOf("convite") !== -1)
    );

    if (isMaster) {
        return {
            isTicket: true,
            isMaster: true,
            level: itLevel,
            index: trueIdx,
            name: itName || "Master Devil's Invitation"
        };
    }

    if (isNormalId || isNormalName) {
        return {
            isTicket: true,
            isMaster: false,
            level: itLevel,
            index: trueIdx,
            name: itName || ("Devil's Invitation +" + itLevel)
        };
    }

    return { isTicket: false, isMaster: false, level: 0, index: trueIdx, name: itName };
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

            // Tuyệt đối loại bỏ Priest James / Ruud Store / NPC quanh bệ James (27..33, 234..241) để không mở nhầm Ruud Store
            if (lowerName.indexOf('james') !== -1 || lowerName.indexOf('ruud') !== -1 || lowerName.indexOf('store') !== -1) continue;
            if (tx >= 27 && tx <= 33 && ty >= 234 && ty <= 241) continue;

            var isMerchant = false;
            // 1. Nhận diện theo tên NPC thương nhân (Silvia, Leah, Merchant, Potion...)
            if (lowerName.indexOf('silvia') !== -1 || lowerName.indexOf('leah') !== -1 || lowerName.indexOf('lia') !== -1 ||
                lowerName.indexOf('merchant') !== -1 || lowerName.indexOf('potion') !== -1 ||
                lowerName.indexOf('tạp hóa') !== -1 || lowerName.indexOf('thuốc') !== -1 ||
                lowerName.indexOf('thương nhân') !== -1 || lowerName.indexOf('poção') !== -1 || lowerName.indexOf('pocion') !== -1) {
                isMerchant = true;
            }
            // 2. Nhận diện theo tọa độ thương nhân Silvia (42..47, 227..232) hoặc Leah (35..40, 234..239)
            else if ((tx >= 42 && tx <= 47 && ty >= 227 && ty <= 232) ||
                     (tx >= 35 && tx <= 40 && ty >= 234 && ty <= 239)) {
                isMerchant = true;
            }
            // 3. Nếu nhân vật đã đứng gần khu vực chợ (px >= 35 && px <= 48 && py >= 225 && py <= 242) và đứng cạnh NPC (<= 3 ô)
            else if (px >= 35 && px <= 48 && py >= 225 && py <= 242 && Math.abs(tx - px) <= 3 && Math.abs(ty - py) <= 3) {
                isMerchant = true;
            }

            if (isMerchant) {
                // Ưu tiên NPC gần tọa độ Silvia (44, 229) nhất
                var dist = Math.abs(tx - 44) + Math.abs(ty - 229);
                if (dist < bestDist) {
                    bestDist = dist;
                    bestNpc = {
                        ptr: body,
                        index: bIdx,
                        name: name || "Merchant Silvia",
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
                                invokeNpcTalk(nPtr);
                            } catch (eMossNT) {}
                        }

                        if (pendingMerchantInteractPtr !== null) {
                            try {
                                var mPtr = pendingMerchantInteractPtr;
                                pendingMerchantInteractPtr = null;
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (eCTM) {}
                                }
                                invokeNpcTalk(mPtr);
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



                if (pendingCommand !== null) {
                    var cmd = pendingCommand;
                    pendingCommand = null;
                    try { dispatchChatMessage(cmd); } catch (eCGU) {}
                }

                if (pendingMoveTarget !== null) {
                    var mTarget = pendingMoveTarget;
                    pendingMoveTarget = null;
                    try { dispatchMoveTarget(mTarget); } catch (eMGU) {}
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



function getCurrentMapId() {
    var mapId = -1;
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
            var tiOffset = off('__GAME_TYPE_INFO__');
            if (!tiOffset.isNull()) {
                var typeInfo = baseAddr.add(tiOffset).readPointer();
                if (!typeInfo.isNull()) {
                    var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                    if (!staticFields.isNull()) {
                        var gameInstance = staticFields.add(ptr('0x8')).readPointer();
                        if (!gameInstance.isNull()) {
                            var world = gameInstance.add(off('__GAME_WORLD__')).readPointer();
                            if (!world.isNull()) {
                                var sc2 = world.add(off('__WORLD_SCENE_INDEX__')).readS32();
                                if (sc2 >= 0 && sc2 <= 255) mapId = sc2;
                            }
                        }
                    }
                }
            }
        } catch (eWorld) {}
    }
    return mapId;
}

function isCurrentMapDoubleGoer() {
    var mid = getCurrentMapId();
    return (mid >= 65 && mid <= 68);
}

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

        // Đọc Map ID (SceneIndex) chuẩn xác 100% qua getCurrentMapId()
        mapId = getCurrentMapId();

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

        var resetCount = 0;
        try {
            var rstOff = off('__PLAYER_RESET_COUNT__');
            if (!rstOff.isNull()) {
                var ptrRst = p.add(rstOff);
                var hiddenVal = ptrRst.add(0x4).readS32();
                var cryptoKey = ptrRst.add(0x8).readS32();
                var decrypted = hiddenVal ^ cryptoKey;
                if (decrypted >= 0 && decrypted <= 100000) {
                    resetCount = decrypted;
                } else {
                    var fakeVal = ptrRst.add(0xC).readS32();
                    if (fakeVal >= 0 && fakeVal <= 100000) {
                        resetCount = fakeVal;
                    } else {
                        var rawVal = ptrRst.readS32();
                        if (rawVal >= 0 && rawVal <= 100000) resetCount = rawVal;
                    }
                }
            }
        } catch (eRst) {}

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
            masterPoints: (masterPoints > 0 ? masterPoints : 0),
            resets: (resetCount > 0 ? resetCount : 0)
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
        var sig = [info.level, info.mapId, info.tileX, info.tileY, info.isMoving ? 1 : 0, info.helperState, info.points || 0, info.resets || 0].join('|');
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

function cleanupNativeTurbo() {
    if (_nativeMirrorTurboTimer !== null) {
        clearInterval(_nativeMirrorTurboTimer);
        _nativeMirrorTurboTimer = null;
    }
}

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
                    nativeStopAutoMove(p, 0, ptr(0));
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
            pendingHelperAction = null;
            return dispatchHelperAction('start');
        } catch (eH) {}
        return false;
    },

    stopHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = null;
            return dispatchHelperAction('stop');
        } catch (eH) {}
        return false;
    },

    toggleHelper: function() {
        try {
            ensureThreadAttached();
            pendingHelperAction = null;
            return dispatchHelperAction('toggle');
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
                nativeStopAutoMove(p, 0, ptr(0));
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

                        // 4. Kích hoạt hiệu ứng LoadingImage quay mượt mà trên giao diện (Tự phục hồi sau 1.2s nếu Server không trả item)
                        try {
                            var loadingImg = mossWin.add(0x60).readPointer();
                            if (!loadingImg.isNull() && isGameObjectValid(loadingImg) && nativeGameObjectSetActive !== null) {
                                nativeGameObjectSetActive(loadingImg, 1, ptr(0));
                                setTimeout(function() {
                                    try {
                                        ensureMossRollButtonActive(mossWin, false);
                                    } catch (eTO) {}
                                }, 1200);
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
                    var mossOff = off('__UI_MOSS_WINDOW__');
                    var mossWin = mossOff.isNull() ? gui.add(ptr('0x1C8')).readPointer() : gui.add(mossOff).readPointer();
                    if (!mossWin.isNull()) {
                        // 1. Phục hồi RollButton và tắt LoadingImage để tránh đơ giao diện
                        ensureMossRollButtonActive(mossWin, true);

                        if (nativeMossWindowClose !== null) {
                            try { nativeMossWindowClose(mossWin, ptr(0)); } catch (eMWC) {}
                        }

                        // 2. Xử lý MWindow tại offset 0x20
                        var win = mossWin.add(0x20).readPointer();
                        if (!win.isNull()) {
                            // A. Bấm nút CloseButton (offset 0x40 của Window) để kích hoạt chuẩn event đóng của game
                            try {
                                var closeBtn = win.add(0x40).readPointer();
                                if (!closeBtn.isNull()) {
                                    if (nativeButtonPress !== null) {
                                        try { nativeButtonPress(closeBtn, ptr(0)); } catch (eBP) {}
                                    }
                                    var onClick = closeBtn.add(0x100).readPointer();
                                    if (!onClick.isNull() && nativeUnityEventInvoke !== null) {
                                        try { nativeUnityEventInvoke(onClick, ptr(0)); } catch (eUE) {}
                                    }
                                }
                            } catch (eCB) {}

                            // B. Gọi nativeWindowHide chuẩn RVA 0x25986B0 TRƯỚC KHI chỉnh IsOpen
                            // (để điều kiện kiểm tra IsOpen trong Window.Hide vẫn hợp lệ)
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(win, ptr(0)); } catch (eWH) {}
                            } else if (nativeWindowSetState !== null) {
                                try { nativeWindowSetState(win, 0, ptr(0)); } catch (eWSS) {}
                            }

                            // C. Tắt triệt để GameObject của MWindow
                            if (nativeComponentGetGameObject !== null && nativeGameObjectSetActive !== null) {
                                try {
                                    var wGo = nativeComponentGetGameObject(win);
                                    if (!wGo.isNull() && isGameObjectValid(wGo)) {
                                        nativeGameObjectSetActive(wGo, 0, ptr(0));
                                    }
                                } catch (eWGO) {}
                            }

                            // D. Cập nhật IsOpen = false (0)
                            win.add(0x48).writeU8(0);
                        }

                        // 3. Tắt GameObject của MMossMerchantWindow để đảm bảo cửa sổ biến mất 100% khỏi màn hình
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

            // 4. Gửi packet C1:31 đóng phiên đàm thoại NPC và mở khóa thùng đồ
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGS) {}

            // 5. Mở khóa toàn diện thùng đồ & nhân vật
            ensureDropAllowed();

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
                invokeNpcTalk(npc.ptr);
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

    unlockInventory: function() {
        try {
            ensureThreadAttached();
            ensureDropAllowed();
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGS) {}
            return true;
        } catch (e) {
            return false;
        }
    },

    unlockCharacterAndInventory: function() {
        try {
            ensureThreadAttached();
            ensureDropAllowed();
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGS) {}
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
                }
            } catch (eAM) {}
            return true;
        } catch (e) {
            return false;
        }
    },

    closeInventory: function() {
        try {
            ensureThreadAttached();
            ensureDropAllowed();
            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (!gui.isNull()) {
                    var invOff = off('__UI_INVENTORY_WINDOW__');
                    var invWin = invOff.isNull() ? gui.add(ptr('0x188')).readPointer() : gui.add(invOff).readPointer();
                    if (!invWin.isNull()) {
                        // 1. Tắt MInventoryWindow.Window (offset 0x28)
                        var win = invWin.add(0x28).readPointer();
                        if (!win.isNull()) {
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(win, ptr(0)); } catch (eWH) {}
                            }
                            win.add(0x48).writeU8(0);
                        }

                        // 2. Tắt ExtInventoryWindow (offset 0x30 - MỞ RỘNG)
                        var extWin = invWin.add(0x30).readPointer();
                        if (!extWin.isNull()) {
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(extWin, ptr(0)); } catch (eEWH) {}
                            }
                            extWin.add(0x48).writeU8(0);
                        }
                    }

                    // 3. Đóng luôn bảng Moss nếu đang mở
                    var mossOff = off('__UI_MOSS_WINDOW__');
                    var mossWin = mossOff.isNull() ? gui.add(ptr('0x1C8')).readPointer() : gui.add(mossOff).readPointer();
                    if (!mossWin.isNull()) {
                        ensureMossRollButtonActive(mossWin, true);
                        var mWin = mossWin.add(0x20).readPointer();
                        if (!mWin.isNull()) {
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(mWin, ptr(0)); } catch (eMWH) {}
                            }
                            mWin.add(0x48).writeU8(0);
                        }
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
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGS) {}
            return true;
        } catch (e) {
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

            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            var talkOk = invokeNpcTalk(npc.ptr);
            if (!talkOk && nativeUniversalNpcClick !== null) {
                try {
                    var nm = getNpcManagerPtr();
                    nativeUniversalNpcClick(nm, npc.ptr, ptr(0));
                    talkOk = true;
                } catch (eUNC) {}
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
                // HARD SAFETY GUARD: Tuyệt đối không bao giờ bán trang bị trên người (0..11)
                if (s < 12) continue;

                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var skill = itemPtr.add(0x14).readS32();
                var luck = itemPtr.add(0x18).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var harmonyOpt = itemPtr.add(0x2C).readS32();

                // BẢO VỆ TUYỆT ĐỐI (Không bao giờ bán):
                // 1. Đồ Divine, Đồ Rồng, Master/Ruud/High-tier (isDivineOrDragonItem)
                // 2. Đồ Hoàn Hảo (excOpt > 0)
                // 3. Đồ Thần (ancOpt > 0)
                // 4. Đồ Socket / 380 (sockOpt > 0)
                // 5. Đồ Harmony (harmonyOpt > 0)
                // 6. Đồ có May Mắn (luck > 0)
                // 7. Cấp độ >= +7 (giữ lại đồ xịn +7 trở lên)
                // 8. Toàn bộ ngọc, vé sự kiện, cánh, sách phép (sec >= 12 && sec <= 15)
                if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, -1)) {
                    continue;
                }

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
                                var maxSlot = 204;
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

            // Đóng bất kỳ cửa sổ đối thoại NPC nào đang mở
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }

            // Gửi packet C1:30/C1:32 tới GameServer (Server sẽ phản hồi thông báo cổng đóng nếu chưa đến giờ)
            sendLugardTalkPacket();

            if (itemSlot < 0) {
                return JSON.stringify({ success: false, error: "no_ticket" });
            }

            var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
            var intMs = (intervalMs !== undefined && parseInt(intervalMs) >= 20) ? parseInt(intervalMs) : 35;
            var maxDur = (maxDurationMs !== undefined && parseInt(maxDurationMs) >= 1000) ? parseInt(maxDurationMs) : 15000;

            cleanupNativeTurbo();

            _nativeMirrorTurboStats = {
                running: true,
                packetsSent: 0,
                startTime: Date.now(),
                durationMs: maxDur,
                activeSlot: itemSlot,
                relSlot: relSlot,
                entered: false
            };

            // Bắn đợt packet & gọi Native Entry đầu tiên (0ms) - Tối ưu 1 packet chuẩn 0xBF:0x0E duy nhất
            if (nativeMirrorEnterAlt !== null) {
                try { nativeMirrorEnterAlt(relSlot); } catch (eNEA) {}
            } else {
                sendMirrorEnterPacket(relSlot);
            }
            _nativeMirrorTurboStats.packetsSent += 1;

            _nativeMirrorTurboTimer = setInterval(function() {
                try {
                    if (!_nativeMirrorTurboStats.running) {
                        cleanupNativeTurbo();
                        return;
                    }

                    // --- BƯỚC 1: KIỂM TRA ĐÃ VÀO MAP DOUBLE GOER (MAP ID: 65, 66, 67, 68) ---
                    // Tuyệt đối chỉ trigger thành công khi SceneIndex thực sự thuộc 65-68!
                    // Event Square là map 53 sẽ luôn trả về false, không bao giờ trigger ảo!
                    if (isCurrentMapDoubleGoer()) {
                        _nativeMirrorTurboStats.running = false;
                        _nativeMirrorTurboStats.entered = true;
                        cleanupNativeTurbo();
                        send({
                            type: "mirror_turbo_entered",
                            packets: _nativeMirrorTurboStats.packetsSent,
                            elapsed: Date.now() - _nativeMirrorTurboStats.startTime
                        });
                        return;
                    }

                    // --- BƯỚC 2: KIỂM TRA HẾT HẠN THỜI GIAN (TIMEOUT) ---
                    var elapsed = Date.now() - _nativeMirrorTurboStats.startTime;
                    if (elapsed >= _nativeMirrorTurboStats.durationMs) {
                        _nativeMirrorTurboStats.running = false;
                        cleanupNativeTurbo();
                        send({
                            type: "mirror_turbo_timeout",
                            packets: _nativeMirrorTurboStats.packetsSent,
                            elapsed: elapsed
                        });
                        return;
                    }

                    // --- BƯỚC 3: GỌI NATIVE ENTRY VÀ BẮN PACKET CƯỚP CỔNG (Tối ưu 1 packet chuẩn 0xBF:0x0E duy nhất) ---
                    if (nativeMirrorEnterAlt !== null) {
                        try { nativeMirrorEnterAlt(_nativeMirrorTurboStats.relSlot); } catch (eNEA) {}
                    } else {
                        sendMirrorEnterPacket(_nativeMirrorTurboStats.relSlot);
                    }
                    _nativeMirrorTurboStats.packetsSent += 1;

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
            cleanupNativeTurbo();
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
                                var maxSlot = 204;
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

            // Gửi packet C1:30/C1:32 đối thoại NPC Lugard để Server gửi thông báo "The entrance is currently closed" nếu chưa mở cổng
            try {
                sendLugardTalkPacket();
                if (pLugard && !pLugard.isNull()) {
                    invokeNpcTalk(pLugard);
                }
            } catch (eLugTalk) {}

            if (itemSlot >= 0) {
                var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
                if (nativeMirrorEnterAlt !== null) {
                    try { nativeMirrorEnterAlt(relSlot); } catch (eNEA) {}
                } else {
                    sendMirrorEnterPacket(relSlot);
                }
                return JSON.stringify({
                    success: true,
                    slot: itemSlot,
                    relSlot: relSlot,
                    isExtended: (itemSlot >= 76)
                });
            } else {
                if (nativeMirrorNpcClick !== null && pLugard && !pLugard.isNull()) {
                    try { nativeMirrorNpcClick(pLugard, ptr(0)); } catch (eMNP) {}
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
                        var maxSlot = 204;
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
                // 1. Gửi gói tin C1:30/C1:32 tới GameServer (Server sẽ gửi về thông báo "The entrance is currently closed" nếu cổng đóng)
                sendLugardTalkPacket();
                invokeNpcTalk(p);
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
            return isCurrentMapDoubleGoer();
        } catch (eMM) {}
        return false;
    },

    autoStackJewels: function() {
        try {
            ensureThreadAttached();

            // =========================================================================
            // 1. CAU HINH NGOC CO THE GHEP (STACKABLE JEWELS)
            // =========================================================================
            // Chi cac ngoc trong danh sach nay moi duoc phep gom va ghep lai voi nhau.
            // TUYET DOI BO QUA: Jewel of Darkness va tat ca cac loai ngoc / vat pham khac!
            var COMBINABLE_JEWEL_MAP = {
                7182: "Chaos",
                7183: "Bless",
                7184: "Soul",
                7185: "Life",
                7186: "Creation",
                7206: "Guardian",
                7207: "Harmony",
                7280: "Gemstone"
            };
            var MAX_STACK = 100; // Gioi han toi da 100 vien (100v) tren 1 o

            // Ham ho tro doc so luong ngoc (stack count) tu item pointer
            function readJewelCount(itemPtr) {
                if (!itemPtr || itemPtr.isNull()) return 1;
                try {
                    // Durability tai offset 0x1C trong GFEFNEHFNEI (chuan so luong vat pham stack trong MU)
                    var dur = itemPtr.add(0x1C).readS32();
                    if (dur >= 1 && dur <= 100) return dur;
                } catch (eD) {}
                try {
                    // Level field tai offset 0x10
                    var lv = itemPtr.add(0x10).readS32();
                    if (lv >= 1 && lv <= 100) return lv;
                } catch (eL) {}
                try {
                    var f40 = itemPtr.add(0x40).readS32();
                    if (f40 >= 1 && f40 <= 100) return f40;
                } catch (eF) {}
                return 1;
            }

            // Ham kiem tra ngoc co the ghep hay khong
            function getJewelType(idx, name) {
                var nmL = (name || "").toLowerCase();
                // BAO VE TUYET DOI: Loai tru Jewel of Darkness va cac ngoc khong ghep duoc
                if (nmL.indexOf("darkness") !== -1) return null;
                if (nmL.indexOf("dark") !== -1) return null;
                if (nmL.indexOf("elevation") !== -1) return null;
                if (nmL.indexOf("extension") !== -1) return null;

                if (COMBINABLE_JEWEL_MAP[idx]) return COMBINABLE_JEWEL_MAP[idx];

                // Nhan dang bo sung qua ten (neu index bi lech do version table)
                if (nmL.indexOf("bless") !== -1) return "Bless";
                if (nmL.indexOf("soul") !== -1) return "Soul";
                if (nmL.indexOf("life") !== -1) return "Life";
                if (nmL.indexOf("chaos") !== -1) return "Chaos";
                if (nmL.indexOf("creation") !== -1) return "Creation";
                if (nmL.indexOf("guardian") !== -1) return "Guardian";
                if (nmL.indexOf("harmony") !== -1) return "Harmony";
                if (nmL.indexOf("gemstone") !== -1 || nmL.indexOf("gem of") !== -1) return "Gemstone";

                return null;
            }

            if (nativeItemStorageMove === null) {
                return JSON.stringify({ ok: false, error: "no_native_move_fn" });
            }

            var totalMoved = 0;
            var allDetails = [];
            var totalCounts = {};
            var totalJewelsFound = 0;

            // =========================================================================
            // HAM XU LY GHEP NGOC DUNG CHUNG CHO TUNG VUNG LUU TRU
            // (Thung do Kho Chinh, Thung do Kho Mo Rong, Hom do Nhan vat)
            // =========================================================================
            function consolidateStorage(storageName, storageFlag, slotsDict, minSlot, maxSlots) {
                // Xac dinh danh sach o trong trong khoang [minSlot, maxSlots)
                var emptySlots = [];
                for (var s = minSlot; s < maxSlots; s++) {
                    if (!slotsDict[s]) emptySlots.push(s);
                }

                // Nhom cac ngoc co ID trung nhau
                var groups = {};
                for (var sKey in slotsDict) {
                    var it = slotsDict[sKey];
                    if (!it.type) continue; // Bo qua vat pham khong phai ngoc ghep

                    if (!groups[it.id]) groups[it.id] = [];
                    groups[it.id].push(it);

                    totalCounts[it.type] = (totalCounts[it.type] || 0) + it.count;
                    totalJewelsFound += it.count;
                }

                // Thuc hien ghep ngoc cho tung nhom ID
                for (var jId in groups) {
                    var group = groups[jId];
                    if (group.length <= 1) continue; // Chi co 1 o ngoc nay -> khong can ghep

                    // Sap xep tang dan theo so thu tu o (slot)
                    group.sort(function(a, b) { return a.slot - b.slot; });

                    var targetIdx = 0;

                    for (var srcIdx = 1; srcIdx < group.length; srcIdx++) {
                        var src = group[srcIdx];
                        if (src.count <= 0) continue;

                        while (src.count > 0 && targetIdx < srcIdx) {
                            var target = group[targetIdx];
                            var spaceInTarget = MAX_STACK - target.count;

                            if (spaceInTarget <= 0) {
                                // O dich hien tai da day 100 vien -> chuyen sang vi tri ngoc tiep theo
                                targetIdx++;
                                continue;
                            }

                            // KIEM TRA AN TOAN TUYET DOI TRUOC KHI GHEP:
                            if (!src.ptr || src.ptr.isNull() || !target.ptr || target.ptr.isNull()) break;
                            if (src.id !== target.id) break; // Khac loai ngoc -> KHONG BAO GIO GHEP
                            if (src.slot === target.slot) break;

                            var toMove = Math.min(src.count, spaceInTarget);

                            try {
                                // Goi nativeItemStorageMove:
                                // storageFlag = 2 cho Thung do Kho (Chinh & Mo Rong), 0 cho Hom do Nhan vat
                                nativeItemStorageMove(src.ptr, storageFlag, src.slot, storageFlag, target.slot, ptr(0));

                                totalMoved++;
                                allDetails.push({
                                    storage: storageName,
                                    type: src.type,
                                    name: src.name,
                                    fromSlot: src.slot,
                                    toSlot: target.slot,
                                    amount: toMove,
                                    targetTotal: target.count + toMove
                                });

                                target.count += toMove;
                                src.count -= toMove;

                                try { Thread.sleep(0.18); } catch (eSleep) {}
                            } catch (eMove) {
                                // Gap loi native -> dung an toan ngay lap tuc de bao ve ngoc
                                break;
                            }

                            if (target.count >= MAX_STACK) {
                                // O dich da dat du 100 vien (100v) -> chuyen sang vi tri tiep theo
                                targetIdx++;
                            }
                        }

                        // Neu nguon da ghep het -> o tro thanh o trong
                        if (src.count <= 0) {
                            emptySlots.push(src.slot);
                            delete slotsDict[src.slot];
                        }
                    }

                    // XU LY PHAN DU QUA 100v:
                    // Neu sau khi ghep, o cuoi cung con ngoc le nam o vi tri qua xa (> slot dau + 1),
                    // va co o trong phia truoc trong cung vung luu tru -> uu tien don ve o trong phia truoc de gon gang
                    if (targetIdx < group.length) {
                        var leftover = group[targetIdx];
                        if (leftover.count > 0 && emptySlots.length > 0) {
                            emptySlots.sort(function(a, b) { return a - b; });
                            var firstEmpty = -1;
                            for (var e = 0; e < emptySlots.length; e++) {
                                if (emptySlots[e] >= minSlot && emptySlots[e] < leftover.slot && !slotsDict[emptySlots[e]]) {
                                    firstEmpty = emptySlots[e];
                                    break;
                                }
                            }
                            if (firstEmpty >= minSlot && firstEmpty < leftover.slot) {
                                try {
                                    nativeItemStorageMove(leftover.ptr, storageFlag, leftover.slot, storageFlag, firstEmpty, ptr(0));
                                    totalMoved++;
                                    allDetails.push({
                                        storage: storageName,
                                        type: leftover.type,
                                        name: leftover.name,
                                        fromSlot: leftover.slot,
                                        toSlot: firstEmpty,
                                        action: "relocate_to_empty"
                                    });
                                    emptySlots.push(leftover.slot);
                                    leftover.slot = firstEmpty;
                                    slotsDict[firstEmpty] = leftover;
                                    try { Thread.sleep(0.18); } catch (eSl2) {}
                                } catch (eReloc) {}
                            }
                        }
                    }
                }
            }

            // Ham ho tro doc cac o tu 1 ItemStorage bat ky (MainStorage hoac ExtStorage)
            function readStorageComponent(storagePtr, targetDict, baseStartSlot, maxSlotLimit) {
                if (!storagePtr || storagePtr.isNull()) return;
                try {
                    var startIdx = baseStartSlot;
                    try {
                        var stIdx = storagePtr.add(0x28).readS32();
                        if (stIdx >= 0 && stIdx <= 240) startIdx = stIdx;
                    } catch (eSt) {}

                    var cellsDict = storagePtr.add(ptr('0x38')).readPointer();
                    if (!cellsDict.isNull()) {
                        var cEntries = cellsDict.add(ptr('0x18')).readPointer();
                        var cCount = cellsDict.add(ptr('0x20')).readS32();
                        if (!cEntries.isNull() && cCount > 0 && cCount <= 240) {
                            for (var ci = 0; ci < cCount; ci++) {
                                try {
                                    var cent = cEntries.add(0x20 + ci * 24);
                                    var slotObj = cent.add(0x18).readPointer();
                                    if (!slotObj.isNull()) {
                                        var sNum = slotObj.add(ptr('0x20')).readS32();
                                        var realSlot = sNum;
                                        if (realSlot < startIdx) realSlot += startIdx;
                                        if (realSlot >= baseStartSlot && realSlot < maxSlotLimit) {
                                            var itObj = slotObj.add(ptr('0x48')).readPointer();
                                            if (!itObj.isNull()) {
                                                var idx = readItemIndex(itObj);
                                                var nm = getItemName(itObj) || "";
                                                var jType = getJewelType(idx, nm);
                                                var cnt = readJewelCount(itObj);
                                                targetDict[realSlot] = {
                                                    slot: realSlot,
                                                    ptr: itObj,
                                                    id: idx,
                                                    name: nm,
                                                    count: cnt,
                                                    type: jType
                                                };
                                            }
                                        }
                                    }
                                } catch (eC) {}
                            }
                        }
                    }
                } catch (eS) {}
            }

            // =========================================================================
            // 2. QUET THUNG DO KHO (CHINH: 0..119 & MO RONG: 120..239)
            // =========================================================================
            var mainWarehouseSlots = {};
            var extWarehouseSlots = {};

            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x288')).readPointer() : gui.add(whOff).readPointer();
                        if (!whWin.isNull()) {
                            // A. Doc Thung do Kho Chinh qua MainStorage (offset 0x58, slots 0..119)
                            try {
                                var mainStorage = whWin.add(ptr('0x58')).readPointer();
                                readStorageComponent(mainStorage, mainWarehouseSlots, 0, 120);
                            } catch (eWhMain) {}

                            // B. Doc Thung do Kho Mo Rong qua ExtStorage (offset 0x60, slots 120..239)
                            try {
                                var extStorage = whWin.add(ptr('0x60')).readPointer();
                                readStorageComponent(extStorage, extWarehouseSlots, 120, 240);
                            } catch (eWhExt) {}

                            // C. Du phong doc toan bo 240 slots qua WarehouseWindow.Items (offset 0x30)
                            if (Object.keys(mainWarehouseSlots).length === 0 || Object.keys(extWarehouseSlots).length === 0) {
                                try {
                                    var dictPtr = whWin.add(ptr('0x30')).readPointer();
                                    if (!dictPtr.isNull()) {
                                        var entries = dictPtr.add(ptr('0x18')).readPointer();
                                        var count = dictPtr.add(ptr('0x20')).readS32();
                                        for (var di = 0; di < count && di < 240; di++) {
                                            try {
                                                var ent = entries.add(0x20 + di * 24);
                                                var k1 = ent.add(0x8).readS32();
                                                var k2 = ent.add(0x10).readS32();
                                                var v1 = ent.add(0x10).readPointer();
                                                var v2 = ent.add(0x18).readPointer();
                                                var key = (k2 >= 0 && k2 < 240) ? k2 : k1;
                                                var val = (!v2.isNull()) ? v2 : v1;
                                                if (key >= 0 && key < 240 && !val.isNull()) {
                                                    var idx2 = readItemIndex(val);
                                                    var nm2 = getItemName(val) || "";
                                                    var jType2 = getJewelType(idx2, nm2);
                                                    var cnt2 = readJewelCount(val);
                                                    if (jType2) {
                                                        if (key < 120 && !mainWarehouseSlots[key]) {
                                                            mainWarehouseSlots[key] = { slot: key, ptr: val, id: idx2, name: nm2, count: cnt2, type: jType2 };
                                                        } else if (key >= 120 && key < 240 && !extWarehouseSlots[key]) {
                                                            extWarehouseSlots[key] = { slot: key, ptr: val, id: idx2, name: nm2, count: cnt2, type: jType2 };
                                                        }
                                                    }
                                                }
                                            } catch (eWhBDict) {}
                                        }
                                    }
                                } catch (eWhB) {}
                            }
                        }
                    }
                }
            } catch (eWH) {}

            // Thuc hien ghep ngoc Thung do Kho Chinh (slots 0..119)
            if (Object.keys(mainWarehouseSlots).length > 0) {
                consolidateStorage("Thùng đồ chính", 2, mainWarehouseSlots, 0, 120);
            }

            // Thuc hien ghep ngoc Thung do Kho Mo Rong (slots 120..239)
            if (Object.keys(extWarehouseSlots).length > 0) {
                consolidateStorage("Thùng đồ mở rộng", 2, extWarehouseSlots, 120, 240);
            }

            // =========================================================================
            // 3. QUET HOM DO & TUI DO MO RONG NHAN VAT (PLAYER INVENTORY: 12..203)
            // =========================================================================
            var inventorySlots = {};
            var invMaxSlot = 204; // Mac dinh quet toan bo tui do chinh & mo rong (12..203)
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            try {
                                var arrLen = itemsArr.add(0x18).readS32();
                                if (arrLen > 12 && arrLen <= 204) invMaxSlot = arrLen;
                            } catch (eLen) {}

                            for (var s = 12; s < invMaxSlot; s++) {
                                try {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var invIdx = readItemIndex(itemPtr);
                                        var invNm = getItemName(itemPtr) || "";
                                        var invJType = getJewelType(invIdx, invNm);
                                        var invCnt = readJewelCount(itemPtr);
                                        inventorySlots[s] = { slot: s, ptr: itemPtr, id: invIdx, name: invNm, count: invCnt, type: invJType };
                                    }
                                } catch (eIt) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}

            // Thuc hien ghep ngoc Hom do & Tui do mo rong nhan vat (storageFlag = 0)
            if (Object.keys(inventorySlots).length > 0) {
                consolidateStorage("Hòm đồ nhân vật", 0, inventorySlots, 12, invMaxSlot);
            }

            return JSON.stringify({
                ok: true,
                counts: totalCounts,
                totalJewels: totalJewelsFound,
                moved: totalMoved,
                details: allDetails
            });
        } catch (eTop) {
            return JSON.stringify({ ok: false, error: String(eTop) });
        }
    },

    claimGremoryCaseItems: function() {
        try {
            ensureThreadAttached();
            var base = Process.findModuleByName('GameAssembly.dll').base;
            var typeInfo = base.add(ptr('0x553B900')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ ok: false, claimed: 0, reason: "typeInfo_null" });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ ok: false, claimed: 0, reason: "staticFields_null" });
            var gameInst = staticFields.add(ptr('0x08')).readPointer();
            if (gameInst.isNull()) return JSON.stringify({ ok: false, claimed: 0, reason: "gameInst_null" });
            var gremoryCase = gameInst.add(ptr('0x138')).readPointer();
            if (gremoryCase.isNull()) return JSON.stringify({ ok: false, claimed: 0, reason: "gremoryCase_null" });
            var dictPtr = gremoryCase.add(ptr('0x20')).readPointer();
            if (dictPtr.isNull()) return JSON.stringify({ ok: false, claimed: 0, reason: "dictPtr_null" });

            var claimFunc = new NativeFunction(base.add(ptr('0xFD85C0')), 'void', ['pointer', 'pointer']);
            var outerEntries = dictPtr.add(ptr('0x18')).readPointer();
            var outerCount = dictPtr.add(ptr('0x20')).readS32();
            var claimedCount = 0;
            var claimedItems = [];

            for (var t = 0; t < outerCount; t++) {
                var oEntry = outerEntries.add(0x20 + t * 24);
                if (oEntry.readS32() < 0) continue;
                var subDict = oEntry.add(16).readPointer();
                if (subDict.isNull()) continue;

                var subEntries = subDict.add(ptr('0x18')).readPointer();
                if (subEntries.isNull()) continue;
                var arrLen = subEntries.add(ptr('0x18')).readS32();

                for (var i = 0; i < arrLen; i++) {
                    var sEntry = subEntries.add(0x20 + i * 24);
                    if (sEntry.readS32() < 0) continue;
                    var itemInfo = sEntry.add(16).readPointer();
                    if (itemInfo.isNull()) continue;

                    var itemObj = itemInfo.add(ptr('0x20')).readPointer();
                    var itemCode = 0;
                    if (!itemObj.isNull()) {
                        try { itemCode = itemObj.add(ptr('0x60')).readU16(); } catch (eCode) {}
                    }

                    claimFunc(itemInfo, ptr(0));
                    claimedCount++;
                    claimedItems.push({ code: itemCode });
                    Thread.sleep(0.08);
                }
            }
            return JSON.stringify({ ok: true, success: true, claimed: claimedCount, items: claimedItems });
        } catch (e) {
            return JSON.stringify({ ok: false, success: false, claimed: 0, error: String(e) });
        }
    },

    enterDevil: function(targetLevel, slot) {
        try {
            ensureThreadAttached();
            var dsLevel = (targetLevel !== undefined && targetLevel !== null && parseInt(targetLevel) >= 0) ? parseInt(targetLevel) : getPlayerDevilSquareLevel();
            var itemSlot = -1;
            var isMasterTicketUsed = false;
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

                                var masterMatchedSlot = -1;
                                var normalMatchedSlot = -1;
                                var anyMasterSlot = -1;
                                var anyNormalSlot = -1;
                                var anyTicketSlot = -1;

                                for (var s = 12; s < maxSlot; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = readItemIndex(itemPtr);
                                        var check = checkDevilItem(itemPtr, idx);
                                        if (check.isTicket) {
                                            if (anyTicketSlot < 0) anyTicketSlot = s;
                                            if (check.isMaster) {
                                                if (anyMasterSlot < 0) anyMasterSlot = s;
                                                // Master: dsLevel >= 6
                                                if (dsLevel >= 6 && masterMatchedSlot < 0) {
                                                    masterMatchedSlot = s;
                                                }
                                            } else {
                                                if (anyNormalSlot < 0) anyNormalSlot = s;
                                                if (check.level === (dsLevel + 1) || check.level === 0 || (dsLevel >= 6 && check.level >= 7)) {
                                                    if (normalMatchedSlot < 0) normalMatchedSlot = s;
                                                }
                                            }
                                        }
                                    }
                                }

                                // Ưu tiên vé:
                                // Nếu là Master (dsLevel >= 6): Ưu tiên Master Ticket trước, sau đó tới Normal Matched (+7)
                                if (dsLevel >= 6) {
                                    if (masterMatchedSlot >= 12) {
                                        itemSlot = masterMatchedSlot;
                                        isMasterTicketUsed = true;
                                    } else if (anyMasterSlot >= 12) {
                                        itemSlot = anyMasterSlot;
                                        isMasterTicketUsed = true;
                                    } else if (normalMatchedSlot >= 12) {
                                        itemSlot = normalMatchedSlot;
                                    } else if (anyTicketSlot >= 12) {
                                        itemSlot = anyTicketSlot;
                                    }
                                } else {
                                    // Nhân vật thường: Ưu tiên Normal Ticket đúng cấp
                                    if (normalMatchedSlot >= 12) {
                                        itemSlot = normalMatchedSlot;
                                    } else if (anyNormalSlot >= 12) {
                                        itemSlot = anyNormalSlot;
                                    } else if (anyMasterSlot >= 12) {
                                        itemSlot = anyMasterSlot;
                                        isMasterTicketUsed = true;
                                    } else if (anyTicketSlot >= 12) {
                                        itemSlot = anyTicketSlot;
                                    }
                                }
                            }
                        }
                    }
                } catch (eScan) {}
            }

            // Đóng mọi popup đối thoại trước khi gửi lệnh vào trực tiếp (Zero-prompt, Zero-dialog)
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT) {}
            }
            var charon = getOrCreateCharonPtr();

            // 1. Tương tác với NPC Charon: Gửi packet C1:30 đối thoại và gọi NPC Talk
            // Server sẽ gửi thông báo cổng đóng trực tiếp trên màn hình game nếu chưa đến giờ mở cửa!
            try {
                sendCharonTalkPacket();
                if (charon && !charon.isNull()) {
                    invokeNpcTalk(charon);
                }
            } catch (eCharonTalk) {}

            if (itemSlot >= 0) {
                var actualSlot = (itemSlot < 12) ? (itemSlot + 12) : itemSlot;
                // Gửi trực tiếp vào NPC và bỏ qua xác nhận (Zero-confirm)
                if (nativeDevilEnter !== null) {
                    try { nativeDevilEnter(dsLevel, actualSlot, ptr(0)); } catch (eNDE1) {}
                }
                // Fallback qua GS packet [0xC1, 0x05, 0x90, level, slot]
                sendDevilEnterPacket(dsLevel, actualSlot);

                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT2) {}
                }

                return JSON.stringify({
                    success: true,
                    dsLevel: dsLevel,
                    slot: actualSlot,
                    isMasterTicket: isMasterTicketUsed,
                    isExtended: (actualSlot >= 76)
                });
            } else {
                // KHÔNG CÓ VÉ: Kích hoạt client click NPC Charon (0xF760C0)
                // Game sẽ hiển thị popup dialog "You don't have a Devil's Invitation" ngay trên màn hình game!
                if (nativeDevilNpcClick !== null && charon && !charon.isNull()) {
                    try { nativeDevilNpcClick(charon, ptr(0)); } catch (eDNC) {}
                }
                return JSON.stringify({ success: false, error: "no_ticket" });
            }
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
                        var normalSlots = [];
                        var masterSlots = [];
                        var matchedTickets = [];
                        var normalTickets = [];
                        var masterTickets = [];

                        for (var s = 12; s < maxSlot; s++) {
                            var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemPtr.isNull()) {
                                var idx = readItemIndex(itemPtr);
                                var check = checkDevilItem(itemPtr, idx);
                                if (check.isTicket) {
                                    tickets.push(s);
                                    if (check.isMaster) {
                                        masterSlots.push(s);
                                        masterTickets.push({ slot: s, level: check.level, name: check.name });
                                    } else {
                                        normalSlots.push(s);
                                        normalTickets.push({ slot: s, level: check.level, name: check.name });
                                    }

                                    var isMatched = false;
                                    if (check.isMaster) {
                                        if (dsLevel >= 6) isMatched = true;
                                    } else {
                                        if (check.level === (dsLevel + 1) || check.level === 0 || (dsLevel >= 6 && check.level >= 7)) {
                                            isMatched = true;
                                        }
                                    }
                                    if (isMatched) {
                                        matchedTickets.push(s);
                                    }
                                }
                            }
                        }
                        return JSON.stringify({
                            hasTicket: tickets.length > 0,
                            hasNormalTicket: normalSlots.length > 0,
                            hasMasterTicket: masterSlots.length > 0,
                            hasMatchedTicket: matchedTickets.length > 0,
                            count: tickets.length,
                            normalCount: normalSlots.length,
                            masterCount: masterSlots.length,
                            dsLevel: dsLevel,
                            targetTicketLevel: dsLevel + 1,
                            slots: tickets,
                            normalSlots: normalSlots,
                            masterSlots: masterSlots,
                            matchedSlots: matchedTickets,
                            normalTickets: normalTickets,
                            masterTickets: masterTickets
                        });
                    }
                }
            }
        } catch (eDTI) {}
        return JSON.stringify({
            hasTicket: false,
            hasNormalTicket: false,
            hasMasterTicket: false,
            hasMatchedTicket: false,
            count: 0,
            normalCount: 0,
            masterCount: 0,
            slots: []
        });
    },

    clickDevilNpc: function(npcPtr) {
        try {
            ensureThreadAttached();
            var p = getOrCreateCharonPtr(npcPtr);
            if (p && !p.isNull()) {
                if (nativeCloseTalk !== null) {
                    try { nativeCloseTalk(); } catch (eCT) {}
                }
                sendCharonTalkPacket();
                invokeNpcTalk(p);
                if (nativeDevilNpcClick !== null) {
                    try { nativeDevilNpcClick(p, ptr(0)); } catch (eDN) {}
                }
                if (nativeUniversalNpcClick !== null) {
                    var nm = getNpcManagerPtr();
                    if (!nm.isNull()) {
                        try { nativeUniversalNpcClick(nm, p, ptr(0)); } catch (eUNC) {}
                    }
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
            dispatchChatMessage("/m ev");
            sendGatePacket(507);
            if (this.sendChatNative) {
                try { this.sendChatNative("/m ev"); } catch (eSC) {}
            }
            if (nativeMirrorTeleportEventMap !== null) {
                try { nativeMirrorTeleportEventMap(ptr(0), 1, ptr(0)); } catch (e) {}
            }
            return true;
        } catch (eTTEM) {}
        return false;
    },

    getInventorySummary: function(mossCategory, maxJunkLevel) {
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
            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var maxJunkLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 4;

            for (var s = 12; s < maxSlot; s++) {
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) {
                    freeSlots++;
                    continue;
                }
                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var skill = itemPtr.add(0x14).readS32();
                var luck = itemPtr.add(0x18).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var harmonyOpt = itemPtr.add(0x2C).readS32();

                var isSpecial = isDivineOrDragonItem(itemPtr, itemIndex);
                var isKept = isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl);
                var isExt = (s >= 76);
                var itName = getItemName(itemPtr);
                if (isKept) {
                    keptSlots.push({
                        slot: s,
                        index: itemIndex,
                        name: itName,
                        level: itemLevel,
                        skill: skill,
                        luck: luck,
                        exc: excOpt,
                        anc: ancOpt,
                        sock: sockOpt,
                        harmony: harmonyOpt,
                        isExt: isExt,
                        isSpecial: isSpecial
                    });
                } else {
                    junkSlots.push({
                        slot: s,
                        index: itemIndex,
                        name: itName,
                        level: itemLevel,
                        skill: skill,
                        luck: luck,
                        isExt: isExt
                    });
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

    cleanInventoryJunk: function(method, protectedSlotsJson, mossCategory, includeExtended, maxJunkLevel) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return JSON.stringify({ cleaned: 0, error: "no_player" });

            if (nativeGetGS !== null) {
                try {
                    var gs = nativeGetGS(ptr(0));
                    if (gs.isNull()) return JSON.stringify({ cleaned: 0, error: "no_gs_connection" });
                } catch (eGSCheck) {}
            }

            var invOff = off('__PLAYER_INVENTORY__');
            var inv = p.add(invOff).readPointer();
            if (inv.isNull()) return JSON.stringify({ cleaned: 0, error: "no_inventory" });

            var itemsOff = off('__INVENTORY_ITEMS__');
            var itemsArr = inv.add(itemsOff).readPointer();
            if (itemsArr.isNull()) return JSON.stringify({ cleaned: 0, error: "no_items_arr" });

            var protMap = {};
            if (protectedSlotsJson && typeof protectedSlotsJson === "string") {
                try {
                    var protArr = JSON.parse(protectedSlotsJson);
                    for (var pi = 0; pi < protArr.length; pi++) {
                        protMap[parseInt(protArr[pi])] = true;
                    }
                } catch (ePJson) {}
            }

            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var cleanExt = (includeExtended === 1 || includeExtended === true || includeExtended === "true" || includeExtended === undefined);
            var maxJunkLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 4;

            var dropCoord = ptr(0);
            var curX = 0;
            var curY = 0;
            var targetX = 0;
            var targetY = 0;
            try {
                var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                if (!curCoord.isNull()) {
                    var klass = curCoord.readPointer();
                    if (!klass.isNull()) coordBuf.writePointer(klass);
                    coordBuf.add(0x08).writePointer(ptr(0));
                    curX = curCoord.add(0x10).readS32();
                    curY = curCoord.add(0x14).readS32();
                    targetX = curX + 1;
                    targetY = curY;
                    coordBuf.add(0x10).writeS32(targetX);
                    coordBuf.add(0x14).writeS32(targetY);
                    dropCoord = coordBuf;
                }
                if (curX === 0 && curY === 0) {
                    var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                    if (!lastCoord.isNull()) {
                        curX = lastCoord.add(0x10).readS32();
                        curY = lastCoord.add(0x14).readS32();
                        targetX = curX + 1;
                        targetY = curY;
                        coordBuf.add(0x10).writeS32(targetX);
                        coordBuf.add(0x14).writeS32(targetY);
                        dropCoord = coordBuf;
                    }
                }
            } catch (eXY) {}
            if (targetX === 0 && curX > 0) targetX = curX + 1;
            if (targetY === 0 && curY > 0) targetY = curY;
            if (dropCoord.isNull()) {
                dropCoord = coordBuf;
            }

            var useMethod = (method || "trash").toLowerCase();

            // Quét đến arrLen (hỗ trợ cả Ba lô mở rộng 1 & 2 lên tới slot 139)
            var maxSlot = cleanExt ? 140 : 76;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            var candidates = [];
            for (var s = 12; s < maxSlot; s++) {
                // HARD SAFETY GUARD 1: TUYỆT ĐỐI KHÔNG BAO GIỜ ĐỤNG VÀO CÁC Ô TRANG BỊ TRÊN NGƯỜI (0..11)
                if (s < 12) continue;

                // HARD SAFETY GUARD 2: BẢO VỆ CÁC Ô ĐÃ CÓ TRƯỚC KHI BẮT ĐẦU QUAY MOSS
                if (protMap[s]) continue;

                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;

                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var skill = itemPtr.add(0x14).readS32();
                var luck = itemPtr.add(0x18).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var sockOpt = itemPtr.add(0x28).readS32();
                var harmonyOpt = itemPtr.add(0x2C).readS32();

                // HARD SAFETY GUARD 3: BẢO VỆ TOÀN DIỆN VẬT PHẨM GIÁ TRỊ VÀ THEO DANH MỤC MOSS
                if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl)) {
                    continue;
                }

                candidates.push(s);
            }

            ensureDropAllowed();

            var cleaned = 0;
            var failedSlots = [];

            // Đợt 1: Gửi lệnh dọn lần lượt với khoảng giãn cách hợp lý chống server flood
            for (var ci = 0; ci < candidates.length; ci++) {
                var s = candidates[ci];
                var itmCheck = itemsArr.add(0x20 + s * 8).readPointer();
                if (itmCheck.isNull()) continue;

                var itemHandled = false;
                try {
                    if (useMethod === "drop" || useMethod === "trash" || useMethod === "both") {
                        if (sendDropPacket(s, targetX, targetY)) {
                            itemHandled = true;
                        }
                    }
                    if (!itemHandled && (useMethod === "sell" || useMethod === "both")) {
                        if (false && nativeInvSellItem !== null) {
                            try { nativeInvSellItem(s, ptr(0)); itemHandled = true; } catch (eS) { itemHandled = sendSellPacket(s); }
                        } else {
                            itemHandled = sendSellPacket(s);
                        }
                    }

                    if (itemHandled) {
                        try { Thread.sleep(0.06); } catch (eSl) {}
                    }
                } catch (eSlotHandle) {}
            }

            // Chờ server đồng bộ trạng thái hòm đồ (200ms)
            try { Thread.sleep(0.20); } catch (eSync) {}

            // Pass 2: Kiểm tra xác thực các ô đã rỗng thực tế hay còn sót (do packet rate-limit)
            for (var ci2 = 0; ci2 < candidates.length; ci2++) {
                var s2 = candidates[ci2];
                var itmCheck2 = itemsArr.add(0x20 + s2 * 8).readPointer();
                if (itmCheck2.isNull()) {
                    cleaned++;
                } else {
                    failedSlots.push(s2);
                }
            }

            // Nếu còn sót món nào, thử gửi retry trực tiếp bằng packet fallback
            if (failedSlots.length > 0) {
                for (var fi = 0; fi < failedSlots.length; fi++) {
                    var retrySlot = failedSlots[fi];
                    var altX = (fi % 2 === 0) ? (curX - 1) : (curX + 1);
                    var altY = (fi % 4 < 2) ? (curY + 1) : (curY - 1);
                    if (useMethod === "sell") {
                        sendSellPacket(retrySlot);
                    } else {
                        sendDropPacket(retrySlot, altX, altY);
                    }
                    try { Thread.sleep(0.08); } catch (eRSl) {}
                }
                try { Thread.sleep(0.25); } catch (eRSync) {}

                // Đếm lại lần cuối
                cleaned = 0;
                var remainingFailed = 0;
                for (var ci3 = 0; ci3 < candidates.length; ci3++) {
                    var s3 = candidates[ci3];
                    var itmCheck3 = itemsArr.add(0x20 + s3 * 8).readPointer();
                    if (itmCheck3.isNull()) {
                        cleaned++;
                    } else {
                        remainingFailed++;
                    }
                }
                ensureDropAllowed();
                return JSON.stringify({ cleaned: cleaned, totalJunk: candidates.length, failed: remainingFailed });
            }

            ensureDropAllowed();
            return JSON.stringify({ cleaned: cleaned, totalJunk: candidates.length, failed: 0 });
        } catch (e) {
            ensureDropAllowed();
            return JSON.stringify({ cleaned: 0, error: e.toString() });
        }
    },

    dropInventorySlot: function(slot, offX, offY) {
        try {
            ensureThreadAttached();
            var allowed = ensureDropAllowed();
            var s = parseInt(slot);
            if (s < 12) {
                return JSON.stringify({ ok: false, err: "protected_equipped_slot", slot: s });
            }
            var ox = parseInt(offX !== undefined ? offX : 1);
            var oy = parseInt(offY !== undefined ? offY : 0);

            var p = getPlayerPtr();
            var dropCoord = ptr(0);
            var dropX = 0;
            var dropY = 0;
            try {
                if (!p.isNull()) {
                    var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                    if (!curCoord.isNull()) {
                        dropCoord = curCoord;
                        var klass = curCoord.readPointer();
                        if (!klass.isNull()) coordBuf.writePointer(klass);
                        coordBuf.add(0x08).writePointer(ptr(0));
                        var curX = curCoord.add(0x10).readS32();
                        var curY = curCoord.add(0x14).readS32();
                        dropX = curX + ox;
                        dropY = curY + oy;
                        coordBuf.add(0x10).writeS32(dropX);
                        coordBuf.add(0x14).writeS32(dropY);
                        if (ox !== 0 || oy !== 0) {
                            dropCoord = coordBuf;
                        }
                    }
                    if (dropX === 0 && dropY === 0) {
                        var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                        if (!lastCoord.isNull()) {
                            var curX2 = lastCoord.add(0x10).readS32();
                            var curY2 = lastCoord.add(0x14).readS32();
                            dropX = curX2 + ox;
                            dropY = curY2 + oy;
                            coordBuf.add(0x10).writeS32(dropX);
                            coordBuf.add(0x14).writeS32(dropY);
                            dropCoord = coordBuf;
                        }
                    }
                }
            } catch (ePXY) {}
            if (dropCoord.isNull()) {
                dropCoord = coordBuf;
            }

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
                                itemIdx = readItemIndex(itemP);
                            }
                        }
                    }
                }
            } catch (eCheck) {}

            if (itemP.isNull()) {
                return JSON.stringify({ ok: false, err: "empty_slot", slot: s });
            }

            var pInfo = readItemProps(itemP);
            var itemLevel = pInfo.itemLevel;
            var skill = pInfo.skill;
            var luck = pInfo.luck;
            var excOpt = pInfo.excOpt;
            var ancOpt = pInfo.ancOpt;
            var sockOpt = pInfo.sockOpt;
            var harmonyOpt = pInfo.harmonyOpt;

            if (isItemProtected(itemP, itemIdx, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, -1)) {
                return JSON.stringify({ ok: false, err: "protected_item", slot: s });
            }

            ensureDropAllowed();
            var dropped = sendDropPacket(s, dropX, dropY);

            // Chờ ngắn kiểm tra xác thực
            try { Thread.sleep(0.12); } catch (eSl) {}
            var verified = false;
            try {
                var reCheck = itemsArr.add(0x20 + s * 8).readPointer();
                if (reCheck.isNull()) {
                    verified = true;
                } else if (!verified && dropped) {
                    sendDropPacket(s, dropX, dropY);
                    try { Thread.sleep(0.10); } catch (eSl2) {}
                    var reCheck2 = itemsArr.add(0x20 + s * 8).readPointer();
                    if (reCheck2.isNull()) verified = true;
                }
            } catch (eVer) {}

            return JSON.stringify({ ok: dropped || verified, verified: verified, allowed: allowed, slot: s, x: dropX, y: dropY });
        } catch (e) {
            return JSON.stringify({ ok: false, err: e.toString() });
        }
    },

    sellInventorySlot: function(slot) {
        try {
            ensureThreadAttached();
            var s = parseInt(slot);
            if (s < 12) return false;
            var itemP = ptr(0);
            var itemIdx = -1;
            var p = getPlayerPtr();
            var itemsArr = ptr(0);
            try {
                if (!p.isNull()) {
                    inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            itemP = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemP.isNull()) {
                                itemIdx = readItemIndex(itemP);
                            }
                        }
                    }
                }
            } catch (eP) {}
            if (itemP.isNull()) return false;

            var pInfo = readItemProps(itemP);
            var itemLevel = pInfo.itemLevel;
            var skill = pInfo.skill;
            var luck = pInfo.luck;
            var excOpt = pInfo.excOpt;
            var ancOpt = pInfo.ancOpt;
            var sockOpt = pInfo.sockOpt;
            var harmonyOpt = pInfo.harmonyOpt;

            if (isItemProtected(itemP, itemIdx, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, -1)) {
                return false;
            }

            if (nativeInvSellItem !== null) {
                nativeInvSellItem(s, ptr(0));
                return true;
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
        self._last_attach_attempt: float = 0.0
        self._attach_fail_count: int = 0

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
            "__GET_PLAYER__": str(self.offsets.get("get_player") or DEFAULT_OFFSETS.get("get_player", "0x107FBF0")),
            "__GET_GAME_UI__": str(self.offsets.get("get_game_ui") or DEFAULT_OFFSETS.get("get_game_ui", "0x107FF00")),
            "__GET_WORLD__": str(self.offsets.get("get_world") or DEFAULT_OFFSETS.get("get_world", "0x107FD40")),
            "__GET_AUTO_LOGIN__": str(self.offsets.get("get_auto_login") or DEFAULT_OFFSETS.get("get_auto_login", "0x107F2D0")),
            "__GET_WINDOW_HANDLER__": str(self.offsets.get("get_window_handler") or DEFAULT_OFFSETS.get("get_window_handler", "0x1078690")),
            "__GAME_UPDATE__": str(self.offsets.get("game_update") or DEFAULT_OFFSETS.get("game_update", "0x10701F0")),
            "__GAME_UI_UPDATE__": str(self.offsets.get("game_ui_update") or DEFAULT_OFFSETS.get("game_ui_update", "0x1393AC0")),
            "__GAME_TYPE_INFO__": str(self.offsets.get("game_type_info") or DEFAULT_OFFSETS.get("game_type_info", "0x553B900")),
            "__MLOGIN_UI_TYPE_INFO__": str(self.offsets.get("mlogin_ui_type_info") or DEFAULT_OFFSETS.get("mlogin_ui_type_info", "0x55286D0")),
            "__MLOGIN_SUBMIT__": str(self.offsets.get("mlogin_submit") or DEFAULT_OFFSETS.get("mlogin_submit", "0x1C35790")),
            "__MLOGIN_TOKEN_LOGIN__": str(self.offsets.get("mlogin_token_login") or DEFAULT_OFFSETS.get("mlogin_token_login", "0x1C307B0")),
            "__SET_AUTO_LOGIN__": str(self.offsets.get("set_auto_login") or DEFAULT_OFFSETS.get("set_auto_login", "0xEBF7C0")),
            "__MOVE_TO__": str(self.offsets.get("move_to") or DEFAULT_OFFSETS.get("move_to", "0xB893E0")),
            "__START_AUTO_MOVE__": str(self.offsets.get("start_auto_move") or DEFAULT_OFFSETS.get("start_auto_move", "0xB93B10")),
            "__STOP_AUTO_MOVE__": str(self.offsets.get("stop_auto_move") or DEFAULT_OFFSETS.get("stop_auto_move", "0xB98400")),
            "__CHAT_SEND__": str(self.offsets.get("chat_send") or DEFAULT_OFFSETS.get("chat_send", "0x1331880")),
            "__CHAT_FRAME_SEND__": str(self.offsets.get("chat_frame_send") or DEFAULT_OFFSETS.get("chat_frame_send", "0x1331880")),
            "__CHAT_SEND_CMD__": str(self.offsets.get("chat_send_cmd") or DEFAULT_OFFSETS.get("chat_send_cmd", "0xEFE530")),
            "__COMMAND_MGR_PROCESS__": str(self.offsets.get("command_mgr_process") or DEFAULT_OFFSETS.get("command_mgr_process", "0xEFE530")),
            "__STATIC_CHAT_SEND__": str(self.offsets.get("static_chat_send") or DEFAULT_OFFSETS.get("static_chat_send", "0xF1F710")),
            "__CHAT_UPDATE__": str(self.offsets.get("chat_update") or DEFAULT_OFFSETS.get("chat_update", "0x1334D30")),
            "__HELPER_START__": str(self.offsets.get("helper_start") or DEFAULT_OFFSETS.get("helper_start", "0x277E360")),
            "__HELPER_STOP__": str(self.offsets.get("helper_stop") or DEFAULT_OFFSETS.get("helper_stop", "0x277B9C0")),
            "__HELPER_ACTION__": str(self.offsets.get("helper_action") or DEFAULT_OFFSETS.get("helper_action", "0x2776D60")),
            "__HELPER_TOGGLE__": str(self.offsets.get("helper_toggle") or DEFAULT_OFFSETS.get("helper_toggle", "0x2776D60")),
            "__HELPER_SEND_BF51__": str(self.offsets.get("helper_send_bf51") or DEFAULT_OFFSETS.get("helper_send_bf51", "0x2777010")),
            "__HELPER_REQ_START__": str(self.offsets.get("helper_req_start") or DEFAULT_OFFSETS.get("helper_req_start", "0x2776620")),
            "__HELPER_REQ_STOP__": str(self.offsets.get("helper_req_stop") or DEFAULT_OFFSETS.get("helper_req_stop", "0x2777C00")),
            "__UI_LOCATION_FRAME__": str(self.offsets.get("ui_location_frame") or DEFAULT_OFFSETS.get("ui_location_frame", "0x80")),
            "__LOCATION_HELPER_ON__": str(self.offsets.get("location_helper_on") or DEFAULT_OFFSETS.get("location_helper_on", "0x60")),
            "__LOCATION_HELPER_OFF__": str(self.offsets.get("location_helper_off") or DEFAULT_OFFSETS.get("location_helper_off", "0x68")),
            "__LOCATION_UPDATE_HELPER__": str(self.offsets.get("location_update_helper") or DEFAULT_OFFSETS.get("location_update_helper", "0x25B7CF0")),
            "__NPC_TALK__": str(self.offsets.get("npc_talk") or DEFAULT_OFFSETS.get("npc_talk", "0x1015210")),
            "__NPC_CLOSE_TALK__": str(self.offsets.get("npc_close_talk") or DEFAULT_OFFSETS.get("npc_close_talk", "0x1025540")),
            "__NPC_CLICK__": str(self.offsets.get("npc_click") or DEFAULT_OFFSETS.get("npc_click", "0x1013520")),
            "__GET_CONFIG__": str(self.offsets.get("get_config") or DEFAULT_OFFSETS.get("get_config", "0x107B360")),
            "__GET_USER_2FA__": str(self.offsets.get("get_user_2fa") or DEFAULT_OFFSETS.get("get_user_2fa", "0x1077980")),
            "__INV_TRASH_ITEM__": str(self.offsets.get("inv_trash_item") or "0x0"),
            "__INV_DROP_ITEM__": str(self.offsets.get("inv_drop_item") or "0x0"),
            "__INV_SELL_ITEM__": str(self.offsets.get("inv_sell_item") or "0x0"),
            "__USER_INV_TRASH__": str(self.offsets.get("user_inv_trash") or DEFAULT_OFFSETS.get("user_inv_trash", "0x144C8A0")),
            "__USER_INV_ACTION__": str(self.offsets.get("user_inv_action") or DEFAULT_OFFSETS.get("user_inv_action", "0x1441DF0")),
            "__ITEM_STORAGE_DROP__": str(self.offsets.get("item_storage_drop") or DEFAULT_OFFSETS.get("item_storage_drop", "0x222CD00")),
            "__MERCHANT_SELL_ITEM__": str(self.offsets.get("merchant_sell_item") or DEFAULT_OFFSETS.get("merchant_sell_item", "0x2743520")),
            "__SLOT_QUICK_ACTION__": str(self.offsets.get("slot_quick_action") or DEFAULT_OFFSETS.get("slot_quick_action", "0x23E24A0")),
            "__ITEM_STORAGE_MOVE__": str(self.offsets.get("item_storage_move") or DEFAULT_OFFSETS.get("item_storage_move", "0x22317E0")),
            "__WINDOW_SHOW__": str(self.offsets.get("window_show") or DEFAULT_OFFSETS.get("window_show", "0x258FBC0")),
            "__WINDOW_HIDE__": str(self.offsets.get("window_hide") or DEFAULT_OFFSETS.get("window_hide", "0x25986B0")),
            "__WINDOW_SET_STATE__": str(self.offsets.get("window_set_state") or DEFAULT_OFFSETS.get("window_set_state", "0x258A730")),
            "__WINDOW_TOGGLE__": str(self.offsets.get("window_toggle") or DEFAULT_OFFSETS.get("window_toggle", "0x2589E10")),
            "__BUTTON_PRESS__": str(self.offsets.get("button_press") or DEFAULT_OFFSETS.get("button_press", "0x464E520")),
            "__UNITY_EVENT_INVOKE__": str(self.offsets.get("unity_event_invoke") or DEFAULT_OFFSETS.get("unity_event_invoke", "0x4588220")),
            "__MOSS_ROLL__": str(self.offsets.get("moss_roll") or DEFAULT_OFFSETS.get("moss_roll", "0x27A9760")),
            "__MOSS_OPEN__": str(self.offsets.get("moss_open") or DEFAULT_OFFSETS.get("moss_open", "0x25EA7C0")),
            "__MOSS_ROLL_HANDLER__": str(self.offsets.get("moss_roll_handler") or DEFAULT_OFFSETS.get("moss_roll_handler", "0x27A6230")),
            "__MOSS_INIT__": str(self.offsets.get("moss_init") or DEFAULT_OFFSETS.get("moss_init", "0x27A77C0")),
            "__MOSS_SELECT_CAT__": str(self.offsets.get("moss_select_cat") or DEFAULT_OFFSETS.get("moss_select_cat", "0x27A8510")),
            "__MOSS_SEND_ROLL__": str(self.offsets.get("moss_send_roll") or DEFAULT_OFFSETS.get("moss_send_roll", "0x23F8BE0")),
            "__MOSS_ROLL_CLICK__": str(self.offsets.get("moss_roll_click") or DEFAULT_OFFSETS.get("moss_roll_click", "0x27A8F90")),
            "__MOSS_WINDOW_CLOSE__": str(self.offsets.get("moss_window_close") or DEFAULT_OFFSETS.get("moss_window_close", "0x25986B0")),
            "__GAME_OBJECT_SET_ACTIVE__": str(self.offsets.get("game_object_set_active") or DEFAULT_OFFSETS.get("game_object_set_active", "0x456F2B0")),
            "__COMPONENT_GET_GAME_OBJECT__": str(self.offsets.get("component_get_game_object") or DEFAULT_OFFSETS.get("component_get_game_object", "0x456AE90")),
            "__COMPONENT_GET_GAMEOBJECT__": str(self.offsets.get("component_get_game_object") or DEFAULT_OFFSETS.get("component_get_game_object", "0x456AE90")),
            "__MIRROR_ENTER__": str(self.offsets.get("mirror_enter") or DEFAULT_OFFSETS.get("mirror_enter", "0xF94450")),
            "__MIRROR_ENTER_ALT__": str(self.offsets.get("mirror_enter_alt") or DEFAULT_OFFSETS.get("mirror_enter_alt", "0xF94B00")),
            "__MIRROR_NPC_CLICK__": str(self.offsets.get("mirror_npc_click") or DEFAULT_OFFSETS.get("mirror_npc_click", "0xF927B0")),
            "__MIRROR_IS_EVENT_MAP__": str(self.offsets.get("mirror_is_event_map") or DEFAULT_OFFSETS.get("mirror_is_event_map", "0xF93060")),
            "__MIRROR_TELEPORT_EVENT__": str(self.offsets.get("mirror_teleport_event") or DEFAULT_OFFSETS.get("mirror_teleport_event", "0x37F2C0")),
            "__DEVIL_ENTER__": str(self.offsets.get("devil_enter") or DEFAULT_OFFSETS.get("devil_enter", "0xF8E2F0")),
            "__DEVIL_NPC_CLICK__": str(self.offsets.get("devil_npc_click") or DEFAULT_OFFSETS.get("devil_npc_click", "0xF8DAB0")),
            "__DEVIL_IS_EVENT_MAP__": str(self.offsets.get("devil_is_event_map") or DEFAULT_OFFSETS.get("devil_is_event_map", "0xF8D0B0")),
            "__GET_GS_CONNECTION__": str(self.offsets.get("get_gs_connection") or DEFAULT_OFFSETS.get("get_gs_connection", "0x1077910")),
            "__GS_SEND__": str(self.offsets.get("gs_send") or DEFAULT_OFFSETS.get("gs_send", "0x11F9280")),
            "__GS_SEND_ALT__": str(self.offsets.get("gs_send_alt") or DEFAULT_OFFSETS.get("gs_send_alt", "0x11F9280")),
            "__PLAYER_POINT__": str(self.offsets.get("player_point") or DEFAULT_OFFSETS.get("player_point", "0x238")),
            "__PLAYER_MASTER_POINT__": str(self.offsets.get("player_master_point") or DEFAULT_OFFSETS.get("player_master_point", "0x23C")),
            "__PLAYER_RESET_COUNT__": str(self.offsets.get("player_reset_count") or DEFAULT_OFFSETS.get("player_reset_count", "0x2B4")),
            "__PLAYER_NAME__": str(self.offsets.get("player_name") or DEFAULT_OFFSETS.get("player_name", "0x28")),
            "__PLAYER_LEVEL__": str(self.offsets.get("player_level") or DEFAULT_OFFSETS.get("player_level", "0x30")),
            "__PLAYER_CLASS__": str(self.offsets.get("player_class") or DEFAULT_OFFSETS.get("player_class", "0x34")),
            "__PLAYER_COORD__": str(self.offsets.get("player_coord") or DEFAULT_OFFSETS.get("player_coord", "0x68")),
            "__PLAYER_MOVE__": str(self.offsets.get("player_move") or DEFAULT_OFFSETS.get("player_move", "0xE8")),
            "__PLAYER_INVENTORY__": str(self.offsets.get("player_inventory") or DEFAULT_OFFSETS.get("player_inventory", "0x1B0")),
            "__PLAYER_HELPER__": str(self.offsets.get("player_helper") or DEFAULT_OFFSETS.get("player_helper", "0x1E0")),
            "__PLAYER_LAST_COORD__": str(self.offsets.get("player_last_coord") or DEFAULT_OFFSETS.get("player_last_coord", "0x508")),
            "__AUTO_MOVE_WORKING__": str(self.offsets.get("auto_move_working") or DEFAULT_OFFSETS.get("auto_move_working", "0x4C0")),
            "__AUTO_MOVE_TYPE__": str(self.offsets.get("auto_move_type") or DEFAULT_OFFSETS.get("auto_move_type", "0x4C4")),
            "__AUTO_MOVE_HELPER__": str(self.offsets.get("auto_move_helper") or DEFAULT_OFFSETS.get("auto_move_helper", "0x4C8")),
            "__AUTO_MOVE_DEST__": str(self.offsets.get("auto_move_dest") or DEFAULT_OFFSETS.get("auto_move_dest", "0x4D0")),
            "__MOVE_FLAG__": str(self.offsets.get("move_flag") or DEFAULT_OFFSETS.get("move_flag", "0x3C")),
            "__HELPER_STATE__": str(self.offsets.get("helper_state") or DEFAULT_OFFSETS.get("helper_state", "0x20")),
            "__INVENTORY_ITEMS__": str(self.offsets.get("inventory_items") or DEFAULT_OFFSETS.get("inventory_items", "0x28")),
            "__GAME_WORLD__": str(self.offsets.get("game_world") or DEFAULT_OFFSETS.get("game_world", "0x200")),
            "__WORLD_SCENE_INDEX__": str(self.offsets.get("world_scene_index") or DEFAULT_OFFSETS.get("world_scene_index", "0x20")),
            "__VIEWPORT__": str(self.offsets.get("viewport") or DEFAULT_OFFSETS.get("viewport", "0x110")),
            "__UI_CHAT_FRAME__": str(self.offsets.get("ui_chat_frame") or DEFAULT_OFFSETS.get("ui_chat_frame", "0x50")),
            "__UI_MOSS_WINDOW__": str(self.offsets.get("ui_moss_window") or DEFAULT_OFFSETS.get("ui_moss_window", "0x1C8")),
            "__UI_MERCHANT_WINDOW__": str(self.offsets.get("ui_merchant_window") or DEFAULT_OFFSETS.get("ui_merchant_window", "0x198")),
            "__UI_INVENTORY_WINDOW__": str(self.offsets.get("ui_inventory_window") or DEFAULT_OFFSETS.get("ui_inventory_window", "0x188")),
            "__UI_WAREHOUSE_WINDOW__": str(self.offsets.get("ui_warehouse_window") or DEFAULT_OFFSETS.get("ui_warehouse_window", "0x288")),
            "__GREMORY_INSTANCE_GETTER__": str(self.offsets.get("gremory_instance_getter") or DEFAULT_OFFSETS.get("gremory_instance_getter", "0x109AC80")),
            "__GREMORY_CLAIM_ITEM__": str(self.offsets.get("gremory_claim_item") or DEFAULT_OFFSETS.get("gremory_claim_item", "0xFD85C0")),
            "__GREMORY_TYPE_INFO__": str(self.offsets.get("gremory_type_info") or DEFAULT_OFFSETS.get("gremory_type_info", "0x553B900")),
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
        now = time.time()
        if now - getattr(self, "_last_attach_attempt", 0.0) < 3.0:
            return False
        self._last_attach_attempt = now

        if psutil and not psutil.pid_exists(self.pid):
            _safe_log(f"[MegDirectEngine] Tiến trình PID {self.pid} không tồn tại trên hệ thống.")
            self.is_ready = False
            return False

        try:
            p = psutil.Process(self.pid)
            if not p.is_running() or p.status() in (getattr(psutil, "STATUS_ZOMBIE", "zombie"), getattr(psutil, "STATUS_DEAD", "dead")):
                self.is_ready = False
                return False
        except Exception:
            self.is_ready = False
            return False

        if frida is None:
            _safe_log("[MegDirectEngine] Thư viện frida chưa được cài đặt trong môi trường python.")
            return False

        # Dọn sạch session và script cũ nếu còn sót lại để chống rò rỉ RAM / VirtualAllocEx
        if self.script:
            try:
                self.script.unload()
            except Exception:
                pass
            self.script = None
        if self.session:
            try:
                self.session.detach()
            except Exception:
                pass
            self.session = None

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
            self._attach_fail_count = 0
            trace_frida_event("ATTACH_SUCCESS", f"Đã kết nối Frida session thành công tới PID {self.pid}", pid=self.pid)
            return True
        except Exception as e:
            self._attach_fail_count = getattr(self, "_attach_fail_count", 0) + 1
            if self._attach_fail_count <= 2:
                trace_frida_event("ATTACH_ERROR", f"Lỗi attach Frida tới PID {self.pid}: {e}", pid=self.pid, level="ERROR")
                _safe_log(f"[MegDirectEngine] Lỗi attach Frida tới PID {self.pid}: {e}")
            self.is_ready = False
            if self.session:
                try:
                    self.session.detach()
                except Exception:
                    pass
                self.session = None
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
        with self._rpc_lock:
            # Tự động kết nối lại nếu bị ngắt kết nối nhưng tiến trình game vẫn đang sống
            if not self.is_ready or not self.script:
                if self.pid and psutil and psutil.pid_exists(self.pid):
                    try:
                        if not self._attach():
                            return None
                    except Exception:
                        return None
                else:
                    return None

            if not self.script:
                return None

            try:
                exports = getattr(self.script, "exports_sync", None)
                if exports is None:
                    return None

                fn = getattr(exports, func_name, None)
                if not fn:
                    if "_" in func_name:
                        camel = "".join(w.capitalize() if i > 0 else w for i, w in enumerate(func_name.split("_")))
                        fn = getattr(exports, camel, None)
                    else:
                        import re
                        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', func_name).lower()
                        fn = getattr(exports, snake, None)
                if fn:
                    return fn(*args)
            except Exception as e:
                err_str = str(e).lower()
                if "unable to find method" not in err_str:
                    _safe_log(f"[MegDirectEngine] RPC _call '{func_name}' error: {e}")
                # Nếu RPC lỗi do script bị mất, đánh dấu cần gắn lại
                if "detached" in err_str or "destroyed" in err_str or "script is destroyed" in err_str:
                    self.is_ready = False
                    self.script = None
                    self.session = None
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

            resets_val = 0
            try:
                resets_val = ProcessMemoryReader.read_character_resets(self.pid) if hasattr(ProcessMemoryReader, "read_character_resets") else 0
            except Exception:
                pass

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
                "resets": resets_val or 0
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
        """Kích hoạt bật MuHelper chuẩn giao diện game (Đồng bộ GUI Play->Stop và gửi gói tin máy chủ)."""
        self.last_fast_state = None

        # Nếu helper đã bật sẵn và không cần force_restart: trả về True ngay lập tức
        if not force_restart and self.is_helper_active(force_refresh=True):
            if self.is_ready:
                try:
                    self._call("syncHelperUI", True)
                except Exception:
                    pass
            return True

        # Nếu cần force_restart (để ghim lại tọa độ gốc cắm bãi): tắt helper cũ trước
        if force_restart and self.is_helper_active(force_refresh=True):
            self.stop_helper()
            time.sleep(0.15)

        tx = int(target_x) if target_x is not None else 0
        ty = int(target_y) if target_y is not None else 0

        # Kênh 1: Native Helper Start trên Unity Main Thread (UserHelper.ALFOIEJFHLL -> packet BF:51, 00)
        if self.is_ready:
            try:
                self._call("startHelper")
            except Exception:
                pass
            for _ in range(20):
                time.sleep(0.05)
                if self.is_helper_active(force_refresh=True):
                    try:
                        self._call("syncHelperUI", True)
                    except Exception:
                        pass
                    return True

        # Kênh 2: Gửi phím Home (VK_HOME = 0x24) CHỈ KHI helper chưa bật và Frida không sẵn sàng
        if not self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.05) # Phím Home
                for _ in range(15):
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

        # Nếu helper đã tắt sẵn: trả về True ngay lập tức (KHÔNG bấm phím Home tránh vô tình bật lại!)
        if not self.is_helper_active(force_refresh=True):
            if self.is_ready:
                try:
                    self._call("syncHelperUI", False)
                except Exception:
                    pass
            return True

        # Kênh 1: Native Helper Stop & Packet qua Frida (UserHelper.BBLPCMHOBOE -> packet BF:51, 01)
        if self.is_ready:
            try:
                self._call("stopHelper")
            except Exception:
                pass
            for _ in range(20):
                time.sleep(0.05)
                if not self.is_helper_active(force_refresh=True):
                    try:
                        self._call("syncHelperUI", False)
                    except Exception:
                        pass
                    return True

        # Kênh 2: Gửi phím Home (VK_HOME = 0x24) CHỈ KHI helper vẫn còn đang bật
        if self.is_helper_active(force_refresh=True):
            hwnd = self.get_hwnd()
            if hwnd and sys.platform == "win32":
                self.send_background_key(hwnd, 0x24, 0.05) # Phím Home (Toggle)
                for _ in range(15):
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
                # Fallback OS-level Win32 ESC key nếu game window còn mở
                hwnd = self.get_hwnd()
                if hwnd:
                    self.send_background_key(hwnd, 0x1B, 0.05)  # VK_ESCAPE = 0x1B
                    if self.is_moss_open():
                        import time
                        time.sleep(0.08)
                        self.send_background_key(hwnd, 0x1B, 0.05)
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

    def unlock_inventory(self) -> bool:
        """Mở khóa và giải phóng toàn bộ trạng thái kẹt/treo của thùng đồ và nhân vật."""
        if self.is_ready:
            try:
                res = self._call("unlockCharacterAndInventory")
                return bool(res)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi unlock_inventory: {e}")
        return False

    def unlock_character_and_inventory(self) -> bool:
        """Mở khóa và giải phóng toàn bộ thùng đồ & nhân vật (hủy treo quick-drop, loading Moss, đóng đàm thoại NPC)."""
        if self.is_ready:
            try:
                res = self._call("unlockCharacterAndInventory")
                return bool(res)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi unlock_character_and_inventory: {e}")
        return False

    def close_inventory(self) -> bool:
        """Đóng giao diện HÀNH TRANG & MỞ RỘNG (tắt cả bảng Moss nếu mở, giải phóng mọi khóa)."""
        if self.is_ready:
            try:
                res = self._call("closeInventory")
                return bool(res)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi close_inventory: {e}")
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
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Double Goer (Map ID 65-68) hay không (Hỗ trợ cả Frida Hook và Zero-Injection RAM)."""
        # 1. Thử qua Frida / Fast Telemetry nếu engine đã hook
        if self.is_ready:
            try:
                tele = self.get_player_info(max_age=0.5, allow_blocking=False)
                if tele and "mapId" in tele and tele["mapId"] >= 0:
                    if tele["mapId"] in (65, 66, 67, 68):
                        return True
                res = self._call("isMirrorEventMap")
                if res:
                    return True
            except Exception:
                pass

        # 2. Fallback Win32 ReadProcessMemory trực tiếp (100% hoạt động dù Frida chưa attach)
        try:
            info = self.read_player_info_via_ram()
            if info and "mapId" in info and info["mapId"] in (65, 66, 67, 68):
                return True
        except Exception:
            pass

        # 3. Fallback MemoryScanner nếu có
        try:
            if self.pid and psutil and psutil.pid_exists(self.pid):
                from test_entity_radar import MemoryScanner
                sc = MemoryScanner(self.pid)
                if sc and sc.base_addr:
                    sd = sc.scan_radar(radius=5.0)
                    m_info = sd.get("map", {})
                    mid = m_info.get("id", -1)
                    if mid in (65, 66, 67, 68):
                        return True
        except Exception:
            pass

        return False

    def claim_gremory_case_items(self) -> Dict[str, Any]:
        """Tự động nhận toàn bộ vật phẩm / quà tặng đang lưu trong Hộp Quà Gremory Case (phím K) về hòm đồ chính."""
        hwnd = self.get_hwnd()
        if not hwnd and not self.is_ready:
            return {"ok": False, "success": False, "claimed": 0, "error": "not_ready"}

        # 1. Thử qua Frida Hook (0xFD85C0) nếu quà đã được đồng bộ sẵn trong RAM
        if self.is_ready:
            try:
                res_str = self._call("claimGremoryCaseItems")
                if res_str:
                    res = json.loads(res_str) if isinstance(res_str, str) else res_str
                    if res.get("claimed", 0) > 0:
                        return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi claimGremoryCaseItems via Frida (thử 1): {e}")

        # 2. Mở Hộp Quà Gremory bằng phím 'K' (0x4B) để game gửi packet C1:4F:01 lên Server tải danh sách quà về client
        if hwnd:
            try:
                self.send_background_key(hwnd, 0x1B, duration_s=0.04)
                time.sleep(0.15)
                self.send_background_key(hwnd, 0x4B, duration_s=0.06)
                time.sleep(0.65)
            except Exception:
                pass

        # 3. Sau khi mở hộp K, thử lại nhận qua Frida Native Hook (RVA 0xFD85C0)
        if self.is_ready:
            for _ in range(2):
                try:
                    res_str = self._call("claimGremoryCaseItems")
                    if res_str:
                        res = json.loads(res_str) if isinstance(res_str, str) else res_str
                        if res.get("claimed", 0) > 0:
                            if hwnd:
                                time.sleep(0.2)
                                self.send_background_key(hwnd, 0x1B, duration_s=0.05)
                            return res
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] Lỗi claimGremoryCaseItems via Frida (thử 2): {e}")
                time.sleep(0.3)

        # 4. Thao tác Phím K (Background PostMessage) an toàn 100%
        if hwnd:
            try:

                cw, ch = 1024, 768
                try:
                    import ctypes.wintypes
                    rect = ctypes.wintypes.RECT()
                    if ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
                        cw = max(800, rect.right - rect.left)
                        ch = max(600, rect.bottom - rect.top)
                except Exception:
                    pass

                # Tọa độ nút 'Nhận quà' của các hàng item trong Gremory Case
                base_rx = cw // 2 + int(175 * (cw / 1024.0))
                start_ry = ch // 2 - int(115 * (ch / 768.0))
                row_h = int(48 * (ch / 768.0))

                claimed = 0
                for row in range(5):
                    btn_y = start_ry + row * row_h
                    self.send_background_click(hwnd, base_rx, btn_y, duration_ms=40)
                    time.sleep(0.18)
                    self.send_background_key(hwnd, 0x0D, duration_s=0.04) # VK_RETURN
                    time.sleep(0.12)
                    self.send_background_key(hwnd, 0x20, duration_s=0.04) # VK_SPACE
                    time.sleep(0.12)
                    claimed += 1

                # Click tiếp hàng đầu tiên (row 0) thêm 3 lần vì khi nhận xong thì các hàng dưới trôi lên hàng 0
                for _ in range(3):
                    self.send_background_click(hwnd, base_rx, start_ry, duration_ms=40)
                    time.sleep(0.18)
                    self.send_background_key(hwnd, 0x0D, duration_s=0.04)
                    time.sleep(0.12)
                    self.send_background_key(hwnd, 0x20, duration_s=0.04)
                    time.sleep(0.12)

                time.sleep(0.3)
                self.send_background_key(hwnd, 0x1B, duration_s=0.05) # VK_ESCAPE
                return {"ok": True, "success": True, "claimed": claimed, "method": "background_input"}
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi background input claim Gremory: {e}")

        return {"ok": False, "success": False, "claimed": 0, "error": "not_ready"}

    def auto_stack_jewels(self) -> Dict[str, Any]:
        """
        Gom và ghép ngọc trong thùng đồ (Warehouse):
        - Đọc toàn bộ danh sách vật phẩm trong thùng đồ (WarehouseWindow).
        - Nhận diện các ngọc có cùng ID (Bless, Soul, Life, Chaos, Creation, Guardian, Harmony, Gemstone).
        - Ghép ngọc cùng ID thành 1 stack tại vị trí đầu tiên của ngọc đó trên thùng đồ.
        - Giới hạn tối đa 100 viên (100v) mỗi ô. Khi quá 100v, chuyển sang vị trí ngọc tiếp theo hoặc đặt vào ô trống.
        - Tuyệt đối bảo toàn 100% ngọc (kiểm tra an toàn kép trước mọi thao tác di chuyển/ghép).
        - Bỏ qua nguyên trạng các ngọc không ghép được (như Jewel of Darkness).
        """
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.3)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "error": "not_ready"}

        try:
            res_str = self._call("autoStackJewels")
            if not res_str:
                return {"ok": False, "error": "scan_failed"}
            res = json.loads(res_str) if isinstance(res_str, str) else res_str
            if not res.get("ok"):
                return res

            counts = res.get("counts", {})
            moved = res.get("moved", 0)
            details = res.get("details", [])
            total_jewels = res.get("totalJewels", 0)

            return {
                "ok": True,
                "counts": counts,
                "moved": moved,
                "details": details,
                "total_jewels": total_jewels
            }
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Loi auto_stack_jewels: {e}")
            return {"ok": False, "error": str(e)}

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

    def get_inventory_summary(self, category: Optional[int] = None, max_junk_level: int = 4) -> Dict[str, Any]:
        """Lấy thông tin tổng quan hòm đồ chính (số ô trống, số đồ rác, đồ giữ lại). Hỗ trợ lọc theo danh mục Moss category và max_junk_level."""
        if self.is_ready:
            try:
                cat_val = int(category) if category is not None and category >= 0 else -1
                lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 4
                res_str = self._call("getInventorySummary", cat_val, lvl_val)
                if res_str:
                    return json.loads(res_str)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi get_inventory_summary: {e}")
        return {"error": "not_ready", "free": 64, "junkCount": 0}

    def clean_inventory_junk(
        self,
        method: str = "drop",
        protected_slots: Optional[List[int]] = None,
        category: Optional[int] = None,
        include_extended: bool = True,
        max_junk_level: int = 4
    ) -> Dict[str, Any]:
        """Tự động vứt (drop) hoặc bán toàn bộ vật phẩm rác trong Main Inventory & Ba lô mở rộng (bảo toàn tuyệt đối đồ Exc/Socket/Set/Ngọc/Đồ cộng/Đồ có trước khi quay)."""
        if self.is_ready:
            try:
                prot_json = json.dumps(protected_slots or [])
                cat_val = int(category) if category is not None and category >= 0 else -1
                ext_val = 1 if include_extended else 0
                lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 4
                res_str = self._call("cleanInventoryJunk", str(method), prot_json, cat_val, ext_val, lvl_val)
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
                        exports = getattr(self.script, "exports_sync", None)
                        if exports and hasattr(exports, "cleanup"):
                            exports.cleanup()
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

# Module-level convenience export
send_background_key = MegDirectEngine.send_background_key


