#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU Direct Frida IL2CPP Engine
=================================
Giao tiếp trực tiếp và an toàn với GameAssembly.dll qua Frida Dynamic Instrumentation.
Mô phỏng 100% cơ chế MEGAMUCore của MEGAMU Auto Train Dashboard gốc:
- Hook onEnter vào chat_update (tải động từ RAM License Vault) trên Unity Main Thread.
- Thực thi MoveTo, ChatSend, HelperStart, HelperStop qua địa chỉ giải mã trong RAM.
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

# ZERO HARDCODED OFFSETS: Toàn bộ giá trị offset thực tế được Server mã hóa AES-256-CBC
# và giải mã tạm trên RAM bởi meg_license_bridge.dll (không lưu trong source hay đĩa phát hành).
DEFAULT_OFFSETS: Dict[str, Any] = {
    "game_module": "GameAssembly.dll",
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

var nativePartyInviteByKey = null;
try {
    var pibkOff = off('__PARTY_INVITE_BY_KEY__');
    if (!pibkOff.isNull()) {
        nativePartyInviteByKey = new NativeFunction(baseAddr.add(pibkOff), 'void', ['int', 'pointer']);
    }
} catch (ePIBK) {}

var nativeButtonPress = null;
try {
    var bpOff = off('__BUTTON_PRESS__');
    if (!bpOff.isNull()) {
        nativeButtonPress = new NativeFunction(baseAddr.add(bpOff), 'void', ['pointer', 'pointer']);
    }
} catch (eBP) {}

var nativeUnityEventInvoke = null;
var nativeUnityEvent_Invoke = null;
try {
    var ueiOff = off('__UNITY_EVENT_INVOKE__');
    if (!ueiOff.isNull()) {
        nativeUnityEventInvoke = new NativeFunction(baseAddr.add(ueiOff), 'void', ['pointer', 'pointer']);
        nativeUnityEvent_Invoke = nativeUnityEventInvoke;
    }
} catch (eUEI) {}

var nativeMDialogConfirmYes = null;
try {
    var mdcyOff = off('__MDIALOG_CONFIRM_YES__');
    if (!mdcyOff.isNull()) {
        nativeMDialogConfirmYes = new NativeFunction(baseAddr.add(mdcyOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMDCY) {}

var nativePartyInviteResponse = null;
try {
    var pirOff = off('__USER_PARTY_SEND_RESPONSE__');
    if (!pirOff.isNull()) {
        nativePartyInviteResponse = new NativeFunction(baseAddr.add(pirOff), 'void', ['int', 'int']);
    }
} catch (ePIR) {}

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
        nativeMossSendRoll = new NativeFunction(baseAddr.add(msrOff), 'void', ['int32', 'pointer']);
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
        nativeMirrorIsEventMap = new NativeFunction(baseAddr.add(mimOff), 'bool', ['pointer']);
    }
} catch (eMirrorMap) {}

var nativeMirrorIsEventMapAlt = null;

var nativeMirrorTeleportEventMap = null;
try {
    var mtemOff = off('__MIRROR_TELEPORT_EVENT__');
    if (!mtemOff.isNull()) {
        nativeMirrorTeleportEventMap = new NativeFunction(baseAddr.add(mtemOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eMirrorTeleport) {}

var nativeDevilClosureEnter = null;
try {
    var dceOff = off('__DEVIL_CLOSURE_ENTER__');
    if (!dceOff.isNull()) {
        nativeDevilClosureEnter = new NativeFunction(baseAddr.add(dceOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eDevilClosure) {}

var nativeDevilEnter = null;
try {
    var deOff = off('__DEVIL_ENTER__');
    if (!deOff.isNull()) {
        nativeDevilEnter = new NativeFunction(baseAddr.add(deOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eDevilEnter) {}

var nativeDevilEnterAlt = null;
try {
    var deaOff = off('__DEVIL_ENTER_ALT__');
    if (!deaOff.isNull()) {
        nativeDevilEnterAlt = new NativeFunction(baseAddr.add(deaOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eDevilEnterAlt) {}

var nativeDevilEnter1E = null;
try {
    var de1eOff = off('__DEVIL_ENTER_1E__');
    if (!de1eOff.isNull()) {
        nativeDevilEnter1E = new NativeFunction(baseAddr.add(de1eOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eDevilEnter1E) {}

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

var nativeHelperUIGetInstance = null;
try {
    var offHUI = off('__HELPER_UI_GET_INSTANCE__');
    if (!offHUI.isNull()) {
        nativeHelperUIGetInstance = new NativeFunction(baseAddr.add(offHUI), 'pointer', []);
    }
} catch (eHUI) {}

var nativeHelperUIShowDialog = null;
try {
    var offHSD = off('__HELPER_UI_SHOW_DIALOG__');
    if (!offHSD.isNull()) {
        nativeHelperUIShowDialog = new NativeFunction(baseAddr.add(offHSD), 'pointer', ['pointer', 'pointer', 'pointer', 'pointer', 'bool', 'pointer', 'float', 'pointer']);
    }
} catch (eHSD) {}

var nativeUIModalBoxManagerGetInstance = null;
try {
    var offInst = off('__MODAL_MGR_GET_INSTANCE__');
    if (!offInst.isNull()) {
        nativeUIModalBoxManagerGetInstance = new NativeFunction(baseAddr.add(offInst), 'pointer', []);
    }
} catch (eOffInst) {}

var nativeUIModalBoxManagerCreate = null;
try {
    var offCreate = off('__MODAL_MGR_CREATE__');
    if (!offCreate.isNull()) {
        nativeUIModalBoxManagerCreate = new NativeFunction(baseAddr.add(offCreate), 'pointer', ['pointer', 'pointer', 'pointer']);
    }
} catch (eOffCreate) {}

var nativeUIModalBoxSetText1 = null;
try {
    var offT1 = off('__MODAL_BOX_SET_TEXT1__');
    if (!offT1.isNull()) {
        nativeUIModalBoxSetText1 = new NativeFunction(baseAddr.add(offT1), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eOffT1) {}

var nativeUIModalBoxSetText2 = null;
try {
    var offT2 = off('__MODAL_BOX_SET_TEXT2__');
    if (!offT2.isNull()) {
        nativeUIModalBoxSetText2 = new NativeFunction(baseAddr.add(offT2), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eOffT2) {}

var nativeUIModalBoxSetConfirmText = null;
try {
    var offCT = off('__MODAL_BOX_SET_CONFIRM_TEXT__');
    if (!offCT.isNull()) {
        nativeUIModalBoxSetConfirmText = new NativeFunction(baseAddr.add(offCT), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eOffCT) {}

var nativeUIModalBoxShow = null;
try {
    var offShow = off('__MODAL_BOX_SHOW__');
    if (!offShow.isNull()) {
        nativeUIModalBoxShow = new NativeFunction(baseAddr.add(offShow), 'void', ['pointer', 'pointer']);
    }
} catch (eOffShow) {}

function showModalBox(title, message, btnText) {
    try {
        ensureThreadAttached();
        title = title || "DEVIL SQUARE";
        message = message || "Entrance is currently closed";
        var tStr = il2cpp_string_new(Memory.allocUtf8String(title));
        var mStr = il2cpp_string_new(Memory.allocUtf8String(message));

        // 1. Phương pháp chính: Sử dụng HelperUI Dialog native của Game (Game.Instance->_HelperUI)
        var helperUI = null;
        if (nativeHelperUIGetInstance !== null) {
            try {
                helperUI = nativeHelperUIGetInstance();
            } catch (eHGet) {}
        }
        if (!helperUI || helperUI.isNull()) {
            try {
                var offGameClass = off('__GAME_CLASS_OFFSET__');
                if (!offGameClass.isNull()) {
                    var gameKlass = baseAddr.add(offGameClass).readPointer();
                    if (!gameKlass.isNull()) {
                        var staticFields = gameKlass.add(0xb8).readPointer();
                        if (!staticFields.isNull()) {
                            var gameInst = staticFields.add(0x8).readPointer();
                            if (!gameInst.isNull()) {
                                helperUI = gameInst.add(0x1f8).readPointer();
                            }
                        }
                    }
                }
            } catch (eGameDirect) {}
        }

        if (helperUI && !helperUI.isNull() && nativeHelperUIShowDialog !== null) {
            try {
                var dlg = nativeHelperUIShowDialog(helperUI, ptr(0), tStr, mStr, 1, ptr(0), 0.0, ptr(0));
                if (dlg && !dlg.isNull()) {
                    return true;
                }
            } catch (eSD) {}
        }

        // 2. Phương pháp dự phòng: DuloGames UIModalBoxManager
        if (nativeUIModalBoxManagerGetInstance !== null && nativeUIModalBoxManagerCreate !== null && nativeUIModalBoxShow !== null) {
            var mgr = nativeUIModalBoxManagerGetInstance();
            if (mgr && !mgr.isNull()) {
                var box = nativeUIModalBoxManagerCreate(mgr, ptr(0), ptr(0));
                if (box && !box.isNull()) {
                    if (nativeUIModalBoxSetText1 !== null && title) {
                        try { nativeUIModalBoxSetText1(box, tStr, ptr(0)); } catch (eT1) {}
                    }
                    if (nativeUIModalBoxSetText2 !== null && message) {
                        try { nativeUIModalBoxSetText2(box, mStr, ptr(0)); } catch (eT2) {}
                    }
                    if (nativeUIModalBoxSetConfirmText !== null && btnText) {
                        try { nativeUIModalBoxSetConfirmText(box, il2cpp_string_new(Memory.allocUtf8String(btnText)), ptr(0)); } catch (eBT) {}
                    }
                    nativeUIModalBoxShow(box, ptr(0));
                    return true;
                }
            }
        }
    } catch (eMB) {}
    return false;
}

var nativeNpcTalk = null;
try {
    var ntOff = off('__NPC_TALK__');
    if (!ntOff.isNull()) {
        nativeNpcTalk = new NativeFunction(baseAddr.add(ntOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eNT) {}

var nativeNpcSendTalk = null;
try {
    var nstOff = off('__NPC_SEND_TALK__');
    if (!nstOff.isNull()) {
        nativeNpcSendTalk = new NativeFunction(baseAddr.add(nstOff), 'void', ['pointer', 'pointer']);
    }
} catch (eNST) {}

var nativeUserInvPickItem = null;
try {
    var uipOff = off('__USER_INV_PICK_ITEM__');
    if (!uipOff.isNull()) {
        nativeUserInvPickItem = new NativeFunction(baseAddr.add(uipOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eUIP) {}

var nativeLocalPickNearest = null;
try {
    var lpnOff = off('__LOCAL_PICK_NEAREST__');
    if (!lpnOff.isNull()) {
        nativeLocalPickNearest = new NativeFunction(baseAddr.add(lpnOff), 'void', []);
    }
} catch (eLPN) {}

function invokeNpcTalk(body, fallbackDirectSend) {
    if (!body || body.isNull()) return false;
    var ok = false;
    var nm = getNpcManagerPtr();
    if (nm && !nm.isNull()) {
        try {
            // Reset LastTalkTime (+0x20) để không bị chặn bởi cooldown 0.5s của NpcManager
            nm.add(0x20).writeFloat(0.0);
        } catch (eRst) {}
    }
    if (nativeNpcTalk !== null) {
        try {
            if (nm && !nm.isNull()) {
                nativeNpcTalk(nm, body, ptr(0));
                // Kiểm tra xem nativeNpcTalk có thực sự gửi C1:30 hay tự hủy âm thầm (LastTalkTime vẫn == 0)
                var afterTalk = 0.0;
                try { afterTalk = nm.add(0x20).readFloat(); } catch (eAT) {}
                ok = (afterTalk > 0.0) || !fallbackDirectSend;
            } else {
                nativeNpcTalk(body, body, ptr(0));
                ok = true;
            }
        } catch (eNT) {}
    }
    if (!ok && nativeNpcSendTalk !== null) {
        try {
            // Fallback khi nativeNpcTalk từ chối âm thầm hoặc lỗi: gửi trực tiếp C1:30 qua NpcManager static send talk
            nativeNpcSendTalk(body, ptr(0));
            ok = true;
        } catch (eNST2) {}
    }
    return ok;
}

var nativeCloseTalk = null;
try {
    var nctOff = off('__NPC_CLOSE_TALK__');
    if (!nctOff.isNull()) {
        nativeCloseTalk = new NativeFunction(baseAddr.add(nctOff), 'void', []);
    }
} catch (eNCT) {}

var nativeQuestGetManager = null;
try {
    var qgmOff = off('__QUEST_GET_MANAGER__');
    if (!qgmOff.isNull()) {
        nativeQuestGetManager = new NativeFunction(baseAddr.add(qgmOff), 'pointer', []);
    }
} catch (eQGM) {}

var nativeQuestSendState = null;
try {
    var qssOff = off('__QUEST_SEND_STATE__');
    if (!qssOff.isNull()) {
        nativeQuestSendState = new NativeFunction(baseAddr.add(qssOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eQSS) {}

var nativeQuestSendStateAlt = null;
try {
    var qssaOff = off('__QUEST_SEND_STATE_ALT__');
    if (!qssaOff.isNull()) {
        nativeQuestSendStateAlt = new NativeFunction(baseAddr.add(qssaOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eQSSA) {}

var nativeQuestNpcNextClick = null;
try {
    var qnncOff = off('__QUEST_NPC_NEXT_CLICK__');
    if (!qnncOff.isNull()) {
        nativeQuestNpcNextClick = new NativeFunction(baseAddr.add(qnncOff), 'void', ['pointer', 'pointer']);
    }
} catch (eQNNC) {}

var nativeNpcEnterBarracks = null;
try {
    var nebOff = off('__NPC_ENTER_BARRACKS__');
    if (!nebOff.isNull()) {
        nativeNpcEnterBarracks = new NativeFunction(baseAddr.add(nebOff), 'void', []);
    }
} catch (eNEB) {}

var nativeNpcEnterRefuge = null;
try {
    var nerOff = off('__NPC_ENTER_REFUGE__');
    if (!nerOff.isNull()) {
        nativeNpcEnterRefuge = new NativeFunction(baseAddr.add(nerOff), 'void', []);
    }
} catch (eNER) {}

// === GATE REA MODULE NATIVES (Unit.HJDEPLPHNBO C1:1C, ArkaWar C1:F8, Protocol C1:8E, Data.Instance) ===
var gateCoordBuf = Memory.alloc(32);

var nativeDataGetInstance = null;
try {
    var dgiOff = off('__DATA_GET_INSTANCE__');
    if (!dgiOff.isNull()) {
        nativeDataGetInstance = new NativeFunction(baseAddr.add(dgiOff), 'pointer', []);
    }
} catch (eDGI) {}

var nativeUnitEnterGate = null;
try {
    var uegOff = off('__UNIT_ENTER_GATE__');
    if (!uegOff.isNull()) {
        nativeUnitEnterGate = new NativeFunction(baseAddr.add(uegOff), 'bool', ['int', 'pointer']);
    }
} catch (eUEG) {}

var nativeArkaEnterAcheron = null;
try {
    var aeaOff = off('__ARKA_ENTER_ACHERON__');
    if (!aeaOff.isNull()) {
        nativeArkaEnterAcheron = new NativeFunction(baseAddr.add(aeaOff), 'void', []);
    }
} catch (eAEA) {}

var nativeArkaEnterZone = null;
try {
    var aezOff = off('__ARKA_ENTER_ZONE__');
    if (!aezOff.isNull()) {
        nativeArkaEnterZone = new NativeFunction(baseAddr.add(aezOff), 'void', ['int']);
    }
} catch (eAEZ) {}

var nativeProtocolWarp8E = null;
try {
    var pw8eOff = off('__PROTOCOL_WARP_8E__');
    if (!pw8eOff.isNull()) {
        nativeProtocolWarp8E = new NativeFunction(baseAddr.add(pw8eOff), 'void', ['int', 'int', 'int']);
    }
} catch (ePW8E) {}

function readIl2CppStrSafe(sPtr) {
    try {
        if (!sPtr || sPtr.isNull()) return "";
        var slen = sPtr.add(0x10).readS32();
        if (slen <= 0 || slen > 256) return "";
        return sPtr.add(0x14).readUtf16String(slen) || "";
    } catch (eS) {
        return "";
    }
}

function getDataInstancePtr() {
    // 1. Thread-safe static read: Mega.Data_TypeInfo -> static_fields (+0xB8) -> ANIDCBBGMOD (+0x0)
    try {
        var dtiOff = off('__DATA_TYPE_INFO__');
        if (!dtiOff.isNull()) {
            var dti = baseAddr.add(dtiOff).readPointer();
            if (dti && !dti.isNull()) {
                var sf = dti.add(ptr('0xB8')).readPointer();
                if (sf && !sf.isNull()) {
                    var inst = sf.readPointer();
                    if (inst && !inst.isNull()) return inst;
                }
            }
        }
    } catch (eDTI) {}
    // 2. Fallback: native Mega.Data.GJLMAKAJBKP()
    try {
        if (nativeDataGetInstance !== null) {
            var inst2 = nativeDataGetInstance();
            if (inst2 && !inst2.isNull()) return inst2;
        }
    } catch (eDGI2) {}
    return ptr(0);
}

function readGateEntryObj(gPtr) {
    if (!gPtr || gPtr.isNull()) return null;
    try {
        return {
            index: gPtr.add(0x10).readS32(),
            flag: gPtr.add(0x18).readS32(),
            mapId: gPtr.add(0x1C).readS32(),
            x: gPtr.add(0x20).readS32(),
            y: gPtr.add(0x24).readS32(),
            tx: gPtr.add(0x28).readS32(),
            ty: gPtr.add(0x2C).readS32(),
            targetGate: gPtr.add(0x30).readS32(),
            targetDir: gPtr.add(0x34).readS32(),
            minLevel: gPtr.add(0x38).readS32(),
            maxLevel: gPtr.add(0x3C).readS32(),
            minReset: gPtr.add(0x40).readS32(),
            maxReset: gPtr.add(0x44).readS32(),
            accountLevel: gPtr.add(0x48).readS32()
        };
    } catch (eG) {
        return null;
    }
}

function readMoveEntryObj(mPtr) {
    if (!mPtr || mPtr.isNull()) return null;
    try {
        return {
            index: mPtr.add(0x10).readS32(),
            name: readIl2CppStrSafe(mPtr.add(0x18).readPointer()),
            command: readIl2CppStrSafe(mPtr.add(0x20).readPointer()),
            money: mPtr.add(0x28).readS32(),
            minLevel: mPtr.add(0x2C).readS32(),
            maxLevel: mPtr.add(0x30).readS32(),
            accountLevel: mPtr.add(0x34).readS32(),
            monsterClass: mPtr.add(0x38).readS32(),
            gateId: mPtr.add(0x3C).readS32()
        };
    } catch (eM) {
        return null;
    }
}

function getQuestManagerPtr() {
    try {
        if (nativeQuestGetManager !== null) {
            var qm = nativeQuestGetManager();
            if (qm && !qm.isNull()) return qm;
        }
    } catch (eQM1) {}
    try {
        var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
        if (!typeInfo.isNull()) {
            var sf = typeInfo.add(ptr('0xB8')).readPointer();
            if (!sf.isNull()) {
                var gi = sf.add(ptr('0x8')).readPointer();
                if (!gi.isNull()) {
                    var qOff = off('__QUEST_INSTANCE_OFFSET__');
                    if (!qOff.isNull()) {
                        var qm2 = gi.add(qOff).readPointer();
                        if (qm2 && !qm2.isNull()) return qm2;
                    }
                }
            }
        }
    } catch (eQM2) {}
    return ptr(0);
}

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

var nativeUserInvSell = null;
try {
    var uisOff = off('__USER_INV_SELL__');
    var uiaOff = off('__USER_INV_ACTION__');
    // GUARD: TUYỆT ĐỐI KHÔNG dùng lệnh BUY/ACTION để bán!
    if (!uisOff.isNull() && (uiaOff.isNull() || !uisOff.equals(uiaOff))) {
        nativeUserInvSell = new NativeFunction(baseAddr.add(uisOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eUIS) {}

var nativeUserInvSell5 = null;
try {
    var uis5Off = off('__USER_INV_SELL_5__');
    if (!uis5Off.isNull() && (uiaOff.isNull() || !uis5Off.equals(uiaOff))) {
        nativeUserInvSell5 = new NativeFunction(baseAddr.add(uis5Off), 'void', ['int', 'int', 'pointer']);
    }
} catch (eUIS5) {}

var nativeItemStorageSell = null;
try {
    var issOff = off('__ITEM_STORAGE_SELL__');
    if (!issOff.isNull()) {
        nativeItemStorageSell = new NativeFunction(baseAddr.add(issOff), 'void', ['pointer']);
    }
} catch (eISS) {}

var nativeMerchantSellItem = null;
try {
    var msiOff = off('__MERCHANT_SELL_ITEM__');
    if (!msiOff.isNull()) {
        nativeMerchantSellItem = new NativeFunction(baseAddr.add(msiOff), 'void', ['pointer', 'int', 'pointer', 'pointer']);
    }
} catch (eMSI) {}

var nativeGremoryClaim = null;
try {
    var gcClaimOff = off('__GREMORY_CLAIM_ITEM__');
    if (!gcClaimOff.isNull()) {
        nativeGremoryClaim = new NativeFunction(baseAddr.add(gcClaimOff), 'void', ['pointer', 'pointer']);
    }
} catch (eGremClaim) {}
var pendingGremoryClaim = null;

function readGremoryCaseSnapshot(storageFilter) {
    var result = { ok: false, items: [], byStorage: {}, reason: "" };
    try {
        var mod = Process.findModuleByName('GameAssembly.dll');
        if (!mod || !mod.base) {
            result.reason = "module_not_found";
            return result;
        }
        var base = mod.base;
        var gTypeOff = off('__GREMORY_TYPE_INFO__');
        if (gTypeOff.isNull()) {
            result.reason = "gremory_type_info_missing";
            return result;
        }
        var typeInfo = base.add(gTypeOff).readPointer();
        if (typeInfo.isNull()) { result.reason = "typeInfo_null"; return result; }
        var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
        if (staticFields.isNull()) { result.reason = "staticFields_null"; return result; }
        var gameInst = staticFields.add(ptr('0x08')).readPointer();
        if (gameInst.isNull()) { result.reason = "gameInst_null"; return result; }
        var gremoryCase = gameInst.add(ptr('0x138')).readPointer();
        if (gremoryCase.isNull()) { result.reason = "gremoryCase_null"; return result; }
        var dictPtr = gremoryCase.add(ptr('0x20')).readPointer();
        if (dictPtr.isNull()) { result.reason = "dictPtr_null"; return result; }

        var outerEntries = dictPtr.add(ptr('0x18')).readPointer();
        var outerCount = 0;
        try { outerCount = dictPtr.add(ptr('0x20')).readS32(); } catch (eOC) { outerCount = 0; }
        if (outerEntries.isNull() || outerCount <= 0) {
            result.ok = true;
            return result;
        }
        var outerArrLen = 0;
        try { outerArrLen = outerEntries.add(ptr('0x18')).readS32(); } catch (eOAL) { outerArrLen = outerCount; }
        var outerLimit = Math.min(outerCount, outerArrLen, 16);
        var filterVal = (storageFilter !== undefined && storageFilter !== null && parseInt(storageFilter, 10) >= 0)
            ? parseInt(storageFilter, 10)
            : -1;

        for (var t = 0; t < outerLimit; t++) {
            var oEntry = outerEntries.add(0x20 + t * 24);
            if (oEntry.readS32() < 0) continue;
            var outerStorageKey = 0;
            try { outerStorageKey = oEntry.add(8).readS32(); } catch (eOSK) { outerStorageKey = t; }
            var subDict = oEntry.add(16).readPointer();
            if (subDict.isNull()) continue;

            var subEntries = subDict.add(ptr('0x18')).readPointer();
            var subCount = 0;
            try { subCount = subDict.add(ptr('0x20')).readS32(); } catch (eSC) { subCount = 0; }
            if (subEntries.isNull() || subCount <= 0) continue;
            var arrLen = 0;
            try { arrLen = subEntries.add(ptr('0x18')).readS32(); } catch (eAL) { arrLen = subCount; }
            var subLimit = Math.min(subCount, arrLen, 100);

            for (var i = 0; i < subLimit; i++) {
                var sEntry = subEntries.add(0x20 + i * 24);
                if (sEntry.readS32() < 0) continue;
                var itemInfo = sEntry.add(16).readPointer();
                if (itemInfo.isNull()) continue;

                var storageType = outerStorageKey;
                var authCode = 0;
                var guid = 0;
                var expireTime = 0;
                try { storageType = itemInfo.add(ptr('0x10')).readS32(); } catch (eST) {}
                try { authCode = itemInfo.add(ptr('0x14')).readU32(); } catch (eAC) {}
                try { guid = itemInfo.add(ptr('0x18')).readU32(); } catch (eGD) {}
                try { expireTime = itemInfo.add(ptr('0x28')).readS32(); } catch (eET) {}

                var sk = String(storageType);
                result.byStorage[sk] = (result.byStorage[sk] || 0) + 1;
                if (filterVal >= 0 && storageType !== filterVal) continue;

                var itemObj = null;
                try { itemObj = itemInfo.add(ptr('0x20')).readPointer(); } catch (eIO) { itemObj = null; }
                if (!itemObj || itemObj.isNull()) continue;

                var itemCode = readItemIndex(itemObj);
                if (itemCode < 0) {
                    try { itemCode = itemObj.add(ptr('0x60')).readU16(); } catch (eCode) { itemCode = 0; }
                }
                var itemLevel = 0;
                try {
                    var lv = itemObj.add(ptr('0x10')).readS32();
                    if (lv >= 0 && lv <= 15) itemLevel = lv;
                } catch (eLv) {}
                var itemName = "";
                try { itemName = getItemName(itemObj) || ""; } catch (eNm) {}
                if (!itemName) itemName = "Item#" + itemCode;

                result.items.push({
                    ptr: itemInfo,
                    storageType: storageType,
                    authCode: authCode,
                    guid: guid,
                    expireTime: expireTime,
                    code: itemCode,
                    level: itemLevel,
                    name: itemName
                });
            }
        }
        result.ok = true;
        return result;
    } catch (eSnap) {
        result.reason = String(eSnap);
        return result;
    }
}

function dispatchGremoryClaim(itemInfoPtr) {
    if (!itemInfoPtr || itemInfoPtr.isNull()) return false;
    if (nativeGremoryClaim === null) {
        try {
            var gcOff = off('__GREMORY_CLAIM_ITEM__');
            if (!gcOff.isNull()) {
                nativeGremoryClaim = new NativeFunction(baseAddr.add(gcOff), 'void', ['pointer', 'pointer']);
            }
        } catch (eInitGC) {}
    }
    if (nativeGremoryClaim === null) return false;

    var req = { itemInfo: itemInfoPtr, ok: false, done: false };
    pendingGremoryClaim = req;
    for (var w = 0; w < 10; w++) {
        Thread.sleep(0.02);
        if (req.done) return !!req.ok;
    }
    // Fallback an toàn nếu Update hook chưa tick trong 200ms
    if (pendingGremoryClaim === req) pendingGremoryClaim = null;
    try {
        nativeGremoryClaim(itemInfoPtr, ptr(0));
        return true;
    } catch (eDirectGC) {
        return false;
    }
}

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
    // Vô hiệu hóa triệt để gọi native C++ function <RVA> nhằm chống crash SEH 0xC0000005
    // Thay vào đó việc ném đồ tại chỗ 100% sử dụng GameServer packet 0x23 an toàn tuyệt đối.
    return false;
}

var nativeInvDropItem = nativeInvTrashItem;

// Hàm drop THẬT của client: UserInventory.NNFBKAIGNEM(int slot, Coord target) @ <RVA>
// (đã đối chiếu dump.cs + kiểm chứng disassembly GameAssembly.dll: gửi C3:23 [0x30..0x3E, 0x06, 0x23^0xCB, x, y, slot]).
var nativeUserInvDrop = null;
try {
    var uidOff = off('__USER_INV_DROP__');
    if (!uidOff.isNull()) {
        nativeUserInvDrop = new NativeFunction(baseAddr.add(uidOff), 'void', ['int', 'pointer', 'pointer']);
    }
} catch (eUID) {}

// Hook đọc phản hồi C1:23 từ Server: UserInventory.BGMBJOKLALH(byte[]) @ <RVA>
// byte[3] = result (1=OK, 0=Server từ chối / safe-zone / ô chặn), byte[4] = slot
var userInvDropRecvHook = null;
var _dropRecvSeq = 0;
var _dropRecvBySlot = {};
try {
    var udrOff = off('__USER_INV_DROP_RECV__');
    if (!udrOff.isNull()) {
        userInvDropRecvHook = Interceptor.attach(baseAddr.add(udrOff), {
            onEnter: function(args) {
                if (shuttingDown) return;
                try {
                    var arrPtr = args[0];
                    if (!arrPtr || arrPtr.isNull()) return;
                    var len = arrPtr.add(0x18).readS32();
                    if (len < 5) return;
                    var resCode = arrPtr.add(0x23).readU8();
                    var rSlot = arrPtr.add(0x24).readU8();
                    _dropRecvSeq += 1;
                    _dropRecvBySlot[rSlot] = { ok: (resCode === 1), code: resCode, seq: _dropRecvSeq, atMs: Date.now() };
                } catch (eDropRecv) {}
            }
        });
    }
} catch (eUDR) {}

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
    }
} catch (eGC) {}

var nativeGetUser2FA = null;
try {
    var u2faOff = off('__GET_USER_2FA__');
    if (!u2faOff.isNull()) {
        nativeGetUser2FA = new NativeFunction(baseAddr.add(u2faOff), 'pointer', []);
    }
} catch (e2fa) {}

var nativeUserInvTrash = null;
try {
    var uitOff = off('__USER_INV_TRASH__');
    if (!uitOff.isNull()) {
        nativeUserInvTrash = new NativeFunction(baseAddr.add(uitOff), 'void', ['int', 'int', 'pointer']);
    }
} catch (eUIT) {}

var nativeUserInvAction = null;
try {
    var uiaOff = off('__USER_INV_ACTION__');
    if (!uiaOff.isNull()) {
        nativeUserInvAction = new NativeFunction(baseAddr.add(uiaOff), 'void', ['int', 'pointer']);
    }
} catch (eUIA) {}

var nativeItemStorageDrop = null;
try {
    var isdOff = off('__ITEM_STORAGE_DROP__');
    if (!isdOff.isNull()) {
        nativeItemStorageDrop = new NativeFunction(baseAddr.add(isdOff), 'void', ['pointer', 'pointer']);
    }
} catch (eISD) {}

var nativeUserInvSub32 = nativeUserInvSell;
var nativeUserInvSub61 = null;
var nativeUserInvSubC7 = null;

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

var nativeRuntimeClassInit = null;
try {
    var rciOff = off('__RUNTIME_CLASS_INIT__');
    if (!rciOff.isNull()) {
        nativeRuntimeClassInit = new NativeFunction(baseAddr.add(rciOff), 'pointer', ['pointer']);
    }
} catch (eRCI) {}

var nativeGetUserAccount = null;
try {
    var guaOff = off('__GET_USER_ACCOUNT__');
    if (!guaOff.isNull()) {
        nativeGetUserAccount = new NativeFunction(baseAddr.add(guaOff), 'pointer', []);
    }
} catch (eGUA) {}

var nativeUserAccountSetUsername = null;
try {
    var uasuOff = off('__USER_ACCOUNT_SET_USERNAME__');
    if (!uasuOff.isNull()) {
        nativeUserAccountSetUsername = new NativeFunction(baseAddr.add(uasuOff), 'void', ['pointer', 'pointer', 'bool']);
    }
} catch (eUASU) {}

var nativeUserAccountSetToken = null;
try {
    var uastOff = off('__USER_ACCOUNT_SET_TOKEN__');
    if (!uastOff.isNull()) {
        nativeUserAccountSetToken = new NativeFunction(baseAddr.add(uastOff), 'void', ['pointer', 'pointer']);
    }
} catch (eUAST) {}

var nativeGetCSConnection = null;
try {
    var gcsOff = off('__GET_CS_CONNECTION__');
    if (!gcsOff.isNull()) {
        nativeGetCSConnection = new NativeFunction(baseAddr.add(gcsOff), 'pointer', []);
    }
} catch (eGCS) {}

var nativeCSConnect = null;
try {
    var cscOff = off('__CS_CONNECT__');
    if (!cscOff.isNull()) {
        nativeCSConnect = new NativeFunction(baseAddr.add(cscOff), 'void', ['pointer', 'int']);
    }
} catch (eCSC) {}

var nativeMLoginSetState = null;
try {
    var mssOff = off('__MLOGIN_SET_STATE__');
    if (!mssOff.isNull()) {
        nativeMLoginSetState = new NativeFunction(baseAddr.add(mssOff), 'void', ['pointer', 'int']);
    }
} catch (eMSS) {}

var nativeAutoSelectCharacter = null;
try {
    var ascOff = off('__AUTO_SELECT_CHARACTER__');
    if (!ascOff.isNull()) {
        nativeAutoSelectCharacter = new NativeFunction(baseAddr.add(ascOff), 'bool', ['pointer', 'pointer', 'pointer']);
    }
} catch (eASC) {}

var nativeUnitSelectCharacter = null;
try {
    var uscOff = off('__UNIT_SELECT_CHARACTER__');
    if (!uscOff.isNull()) {
        nativeUnitSelectCharacter = new NativeFunction(baseAddr.add(uscOff), 'void', ['int', 'pointer']);
    }
} catch (eUSC) {}

var nativeUnitEntryCharacter = null;
try {
    var uecOff = off('__UNIT_ENTRY_CHARACTER__');
    if (!uecOff.isNull()) {
        nativeUnitEntryCharacter = new NativeFunction(baseAddr.add(uecOff), 'void', ['int', 'pointer']);
    }
} catch (eUEC) {}

var nativeConnectServerSelect = null;
try {
    var cssOff = off('__CONNECT_SERVER_SELECT__');
    if (!cssOff.isNull()) {
        nativeConnectServerSelect = new NativeFunction(baseAddr.add(cssOff), 'void', ['int']);
    }
} catch (eCSS) {}

var nativeGetHelperUI = null;
try {
    var ghuOff = off('__GET_HELPER_UI__');
    if (!ghuOff.isNull()) {
        nativeGetHelperUI = new NativeFunction(baseAddr.add(ghuOff), 'pointer', []);
    }
} catch (eGHU) {}

var nativeInputField_set_text = null;
try {
    var ifstOff = off('__INPUT_FIELD_SET_TEXT__');
    if (!ifstOff.isNull()) {
        nativeInputField_set_text = new NativeFunction(baseAddr.add(ifstOff), 'void', ['pointer', 'pointer']);
    }
} catch (eIFST) {}

var nativeMLoginSubmit = null;
try {
    var mlsOff = off('__MLOGIN_SUBMIT__');
    if (!mlsOff.isNull()) {
        nativeMLoginSubmit = new NativeFunction(baseAddr.add(mlsOff), 'void', ['pointer', 'pointer', 'pointer', 'bool']);
    }
} catch (eMLS) {}

var nativeMLoginTokenLogin = null;
try {
    var mltOff = off('__MLOGIN_TOKEN_LOGIN__');
    if (!mltOff.isNull()) {
        nativeMLoginTokenLogin = new NativeFunction(baseAddr.add(mltOff), 'void', ['pointer', 'pointer']);
    }
} catch (eMLT) {}

var nativeGetSceneHandler = null;
try {
    var gshOff = off('__GET_SCENE_HANDLER__');
    if (!gshOff.isNull()) {
        nativeGetSceneHandler = new NativeFunction(baseAddr.add(gshOff), 'pointer', []);
    }
} catch (eGSH) {}

var nativeSetTargetFps = null;
try {
    var stfOff = off('__SET_TARGET_FPS__');
    if (!stfOff.isNull()) {
        nativeSetTargetFps = new NativeFunction(baseAddr.add(stfOff), 'void', ['int']);
    }
} catch (eSTF) {}

var nativeGetTargetFps = null;
try {
    var gtfOff = off('__GET_TARGET_FPS__');
    if (!gtfOff.isNull()) {
        nativeGetTargetFps = new NativeFunction(baseAddr.add(gtfOff), 'int', []);
    }
} catch (eGTF) {}

var nativeSetVSyncCount = null;
try {
    var svcOff = off('__SET_VSYNC_COUNT__');
    if (!svcOff.isNull()) {
        nativeSetVSyncCount = new NativeFunction(baseAddr.add(svcOff), 'void', ['int']);
    }
} catch (eSVC) {}

var nativeGetVSyncCount = null;
try {
    var gvcOff = off('__GET_VSYNC_COUNT__');
    if (!gvcOff.isNull()) {
        nativeGetVSyncCount = new NativeFunction(baseAddr.add(gvcOff), 'int', []);
    }
} catch (eGVC) {}

var nativeGetUnityTime = null;
try {
    var ugtOff = off('__UNITY_GET_TIME__');
    if (!ugtOff.isNull()) {
        nativeGetUnityTime = new NativeFunction(baseAddr.add(ugtOff), 'float', []);
    }
} catch (eUGT) {}

var nativePktEncNikini = null;
try {
    var nikOff = off('__PKT_ENC_NIKINI__');
    if (!nikOff.isNull()) {
        nativePktEncNikini = new NativeFunction(baseAddr.add(nikOff), 'pointer', ['pointer', 'pointer', 'pointer']);
    }
} catch (eNIK) {}

var nativePktEncNgjg = null;
try {
    var ngjOff = off('__PKT_ENC_NGJG__');
    if (!ngjOff.isNull()) {
        nativePktEncNgjg = new NativeFunction(baseAddr.add(ngjOff), 'void', ['pointer', 'pointer', 'pointer']);
    }
} catch (eNGJ) {}

var nativeSocketSendErr = null;
try {
    var sseOff = off('__SOCKET_SEND_ERR__');
    if (!sseOff.isNull()) {
        nativeSocketSendErr = new NativeFunction(baseAddr.add(sseOff), 'int', ['pointer', 'pointer', 'int', 'int', 'int', 'pointer', 'pointer']);
    }
} catch (eSSE) {}

var nativeTcpSetNoDelay = null;
try {
    var tndOff = off('__TCP_SET_NODELAY__');
    if (!tndOff.isNull()) {
        nativeTcpSetNoDelay = new NativeFunction(baseAddr.add(tndOff), 'void', ['pointer', 'bool', 'pointer']);
    }
} catch (eTND) {}
var _lastNoDelayTcpPtrStr = "";
function ensureTcpNoDelay(gs) {
    try {
        if (nativeTcpSetNoDelay === null || !gs || gs.isNull()) return false;
        var tcp = gs.add(0x90).readPointer();
        if (!tcp || tcp.isNull()) return false;
        var key = tcp.toString();
        if (_lastNoDelayTcpPtrStr === key) return true;
        nativeTcpSetNoDelay(tcp, 1, ptr(0));
        _lastNoDelayTcpPtrStr = key;
        if (typeof _nativeMirrorTurboStats !== "undefined" && _nativeMirrorTurboStats) {
            _nativeMirrorTurboStats.tcpNoDelayEnabled = true;
        }
        return true;
    } catch (eND) {
        return false;
    }
}

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

var il2cpp_get_corlib = null;
var mono_domain_get_corlib = null;
var il2cpp_class_from_name = null;
var il2cpp_array_new = null;
var il2cpp_gchandle_new = null;
var il2cpp_gchandle_free = null;
try {
    var expIlCorlib = ga.findExportByName('il2cpp_get_corlib');
    var expCorlib = ga.findExportByName('mono_domain_get_corlib');
    var expClassFromName = ga.findExportByName('il2cpp_class_from_name');
    var expArrayNew = ga.findExportByName('il2cpp_array_new');
    var expGCHandleNew = ga.findExportByName('il2cpp_gchandle_new');
    var expGCHandleFree = ga.findExportByName('il2cpp_gchandle_free');
    if (expIlCorlib && !expIlCorlib.isNull()) il2cpp_get_corlib = new NativeFunction(expIlCorlib, 'pointer', []);
    if (expCorlib && !expCorlib.isNull()) mono_domain_get_corlib = new NativeFunction(expCorlib, 'pointer', []);
    if (expClassFromName && !expClassFromName.isNull()) il2cpp_class_from_name = new NativeFunction(expClassFromName, 'pointer', ['pointer', 'pointer', 'pointer']);
    if (expArrayNew && !expArrayNew.isNull()) il2cpp_array_new = new NativeFunction(expArrayNew, 'pointer', ['pointer', 'size_t']);
    if (expGCHandleNew && !expGCHandleNew.isNull()) il2cpp_gchandle_new = new NativeFunction(expGCHandleNew, 'uint32', ['pointer', 'int']);
    if (expGCHandleFree && !expGCHandleFree.isNull()) il2cpp_gchandle_free = new NativeFunction(expGCHandleFree, 'void', ['uint32']);
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
        if (il2cpp_class_from_name !== null) {
            var corlib = null;
            if (il2cpp_get_corlib !== null) {
                try { corlib = il2cpp_get_corlib(); } catch (eIC) { corlib = null; }
            }
            if ((!corlib || corlib.isNull()) && mono_domain_get_corlib !== null) {
                try { corlib = mono_domain_get_corlib(); } catch (eMC) { corlib = null; }
            }
            if (corlib && !corlib.isNull()) {
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

var lastSendError = "";
var _c1SaltCounter = 0;

function prepareC1FrameBytes(bytes, alreadyXored) {
    if (!bytes || bytes.length < 3) return bytes;
    var out = bytes.slice ? bytes.slice() : Array.prototype.slice.call(bytes);
    // OBEABIOOBHH.CDKODGBGAJH (<RVA>): C1 -> byte[0] trong [0x10..0x1E], byte[2] XOR 0xCB
    // PacketHeader C3 (<RVA> - Drop 0x23 / Sell 0x32): C3 -> byte[0] trong [0x30..0x3E], byte[2] XOR 0xCB
    if (out[0] === 0xC1) {
        _c1SaltCounter = (_c1SaltCounter + 1) % 15;
        out[0] = (0x10 + _c1SaltCounter) & 0xFF;
        if (!alreadyXored) {
            out[2] = (out[2] ^ 0xCB) & 0xFF;
        }
    } else if (out[0] === 0xC3) {
        _c1SaltCounter = (_c1SaltCounter + 1) % 15;
        out[0] = (0x30 + _c1SaltCounter) & 0xFF;
        if (!alreadyXored) {
            out[2] = (out[2] ^ 0xCB) & 0xFF;
        }
    }
    return out;
}

function sendGSPacket(bytes, alreadyXored) {
    lastSendError = "";
    try {
        var gs = getGSConnection();
        if (gs.isNull()) { lastSendError = "no_gs_connection"; return false; }
        var frameBytes = prepareC1FrameBytes(bytes, alreadyXored === true);
        var arr = createManagedByteArray(frameBytes);
        if (!arr || arr.isNull()) {
            lastSendError = (il2cpp_array_new === null) ? "il2cpp_array_new_missing"
                          : ((getByteClass() === null) ? "byte_class_lookup_failed" : "array_alloc_failed");
            return false;
        }
        if (nativeGSSend === null && nativeGSSendAlt === null) {
            lastSendError = "gs_send_binding_missing";
            return false;
        }
        if (nativeGSSend !== null) {
            try { nativeGSSend(gs, arr, 0, 0, ptr(0)); return true; }
            catch (eS1) { lastSendError = "gs_send_threw: " + eS1; }
        }
        if (nativeGSSendAlt !== null) {
            try { nativeGSSendAlt(gs, arr, 0, 0, ptr(0)); return true; }
            catch (eS2) { lastSendError = "gs_send_alt_threw: " + eS2; }
        }
        return false;
    } catch (ePkt) {
        lastSendError = "exception: " + ePkt;
        return false;
    }
}

// Vứt 1 ô bằng chính hàm drop thật của client: UserInventory.NNFBKAIGNEM(int slot, Coord target) @ <RVA>.
// Nếu targetX <= 0 hoặc targetY <= 0 (hoặc không đọc được Coord), truyền target=null để client tự chọn ô ngẫu nhiên quanh người [-2..+2].
function dropSlotNative(slot, targetX, targetY) {
    var s = parseInt(slot);
    if (s < 12 || nativeUserInvDrop === null) return false;
    try {
        var tx = parseInt(targetX || 0);
        var ty = parseInt(targetY || 0);
        var coordArg = ptr(0);
        if (tx > 0 && tx < 255 && ty > 0 && ty < 255) {
            var p = getPlayerPtr();
            if (p && !p.isNull()) {
                var playerCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                if (playerCoord && !playerCoord.isNull()) {
                    var klass = playerCoord.readPointer();
                    if (klass && !klass.isNull()) {
                        coordBuf.writePointer(klass);
                        coordBuf.add(0x08).writePointer(ptr(0));
                        coordBuf.add(0x10).writeS32(tx);
                        coordBuf.add(0x14).writeS32(ty);
                        coordArg = coordBuf;
                    }
                }
            }
        }
        nativeUserInvDrop(s, coordArg, ptr(0));
        return true;
    } catch (eDropNative) {
        lastSendError = "native_drop_threw: " + eDropNative;
        return false;
    }
}

var pendingMossOpenCategory = null;
var pendingMossSelectAfterServerOpen = null;
var pendingMossRollCategory = null;
var pendingMossClose = false;
var pendingMossResetCategory = null;
var pendingMerchantClose = false;
var pendingMossInteractPtr = null;
var pendingMossForceReopen = false;
var pendingMerchantInteractPtr = null;
var pendingQuestNpcTalkPtr = null;
var pendingQuestStateAction = null;
var pendingQuestDungeonAction = null;
var pendingGateEnterAction = null;
var pendingArkaEnterAction = null;
var pendingWarp8EAction = null;
var pendingGateDialogConfirm = null;
var lastGateEnterResult = { done: false, ok: false, gateId: -1, x: -1, y: -1, ret: false, error: "" };

function flushGateActionsOnMainThread() {
    if (pendingGateEnterAction !== null) {
        var act = pendingGateEnterAction;
        pendingGateEnterAction = null;
        var res = { done: true, ok: false, gateId: act.gateId, x: act.x, y: act.y, ret: false, error: "" };
        try {
            if (nativeUnitEnterGate === null) {
                res.error = "unit_enter_gate_offset_missing";
            } else {
                var cPtr = ptr(0);
                if (act.x >= 0 && act.y >= 0) {
                    // Unit.HJDEPLPHNBO reads byte at [coord+0x10] (X) and [coord+0x14] (Y)
                    gateCoordBuf.writeByteArray([0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0]);
                    gateCoordBuf.add(0x10).writeS32(act.x & 0xFF);
                    gateCoordBuf.add(0x14).writeS32(act.y & 0xFF);
                    cPtr = gateCoordBuf;
                }
                var r = nativeUnitEnterGate(act.gateId | 0, cPtr);
                res.ret = !!r;
                res.ok = !!r;
            }
        } catch (eGE) {
            res.error = String(eGE);
        }
        lastGateEnterResult = res;
    }

    if (pendingArkaEnterAction !== null) {
        var aAct = pendingArkaEnterAction;
        pendingArkaEnterAction = null;
        try {
            if (aAct.zone >= 0 && nativeArkaEnterZone !== null) {
                nativeArkaEnterZone(aAct.zone | 0);
            } else if (nativeArkaEnterAcheron !== null) {
                nativeArkaEnterAcheron();
            }
        } catch (eAE) {}
    }

    if (pendingGateDialogConfirm !== null) {
        var gd = pendingGateDialogConfirm;
        if (Date.now() >= gd.readyAtMs) {
            pendingGateDialogConfirm = null;
            try {
                if (gd.dlg && !gd.dlg.isNull()) {
                    // Kiểm tra Unity Object.m_CachedPtr (+0x10) còn sống trước khi bấm YES
                    var cachedPtr = gd.dlg.add(0x10).readPointer();
                    if (cachedPtr && !cachedPtr.isNull()) {
                        if (nativeMDialogConfirmYes !== null) {
                            nativeMDialogConfirmYes(gd.dlg, ptr(0));
                        } else {
                            var yBtn = gd.dlg.add(ptr('0x48')).readPointer();
                            if (yBtn && !yBtn.isNull() && nativeButtonPress !== null) {
                                nativeButtonPress(yBtn, ptr(0));
                            }
                        }
                        autoGateConfirmCount += 1;
                        lastAutoGateConfirmInfo = {
                            count: autoGateConfirmCount,
                            title: gd.title || "",
                            message: gd.message || "",
                            timeMs: Date.now()
                        };
                        send({
                            type: "auto_gate_confirmed",
                            source: gd.source || "deferred_mainthread",
                            title: gd.title || "",
                            message: gd.message || "",
                            count: autoGateConfirmCount
                        });
                    }
                }
            } catch (eGDF) {}
        }
    }

    if (pendingWarp8EAction !== null) {
        var wAct = pendingWarp8EAction;
        pendingWarp8EAction = null;
        try {
            if (nativeProtocolWarp8E !== null) {
                nativeProtocolWarp8E(wAct.type | 0, wAct.param | 0, wAct.extra | 0);
            }
        } catch (eW8E) {}
    }
}
var pendingQuestWindowClose = false;
var pendingPkWindowClose = false;
var pendingWarehouseWindowClose = false;

var TALISMAN_LUCK_ID = 7221;
var TALISMAN_CHAOS_ASSEMBLY_ID = 7264;

function readItemStackMeta(itemPtr) {
    var meta = { stackable: false, maxStack: 1, count: 1 };
    if (!itemPtr || itemPtr.isNull()) return meta;
    var hasStackInfo = false;
    var maxSt = 1;
    try {
        var infoPtr = itemPtr.add(0x58).readPointer();
        if (infoPtr && !infoPtr.isNull()) {
            var stInfoPtr = infoPtr.add(0x118).readPointer();
            if (stInfoPtr && !stInfoPtr.isNull()) {
                var ms = stInfoPtr.add(0x10).readS32();
                if (ms > 1 && ms <= 255) {
                    hasStackInfo = true;
                    maxSt = ms;
                }
            }
        }
    } catch (eSM) {}

    var cnt = 1;
    var gotCount = false;
    try {
        var ovr = itemPtr.add(0x6C).readS32();
        if (ovr >= 1 && ovr <= 255) {
            cnt = ovr;
            gotCount = true;
        }
    } catch (eOvr) {}
    if (!gotCount && hasStackInfo) {
        try {
            var dur64 = itemPtr.add(0x64).readS32();
            if (dur64 >= 1 && dur64 <= 255) {
                cnt = dur64;
                gotCount = true;
            }
        } catch (eD64) {}
    }
    if (!gotCount) {
        try {
            var dur1c = itemPtr.add(0x1C).readS32();
            if (dur1c >= 1 && dur1c <= 255) {
                cnt = dur1c;
                gotCount = true;
            }
        } catch (eD1C) {}
    }
    meta.stackable = hasStackInfo && maxSt > 1;
    meta.maxStack = maxSt;
    meta.count = cnt;
    return meta;
}

function classifyTalismanItem(idx, name) {
    var nmL = String(name || "").toLowerCase();
    if (nmL.indexOf("elemental") !== -1) return null;
    if (idx === TALISMAN_LUCK_ID || nmL.indexOf("talisman of luck") !== -1) {
        return { key: "TalismanOfLuck", id: TALISMAN_LUCK_ID, label: "Talisman of Luck" };
    }
    if (idx === TALISMAN_CHAOS_ASSEMBLY_ID || nmL.indexOf("chaos assembly") !== -1) {
        return { key: "TalismanOfChaosAssembly", id: TALISMAN_CHAOS_ASSEMBLY_ID, label: "Talisman of Chaos Assembly" };
    }
    return null;
}

function isWarehouseWindowActuallyOpen(whWin) {
    if (!whWin || whWin.isNull()) return { mainOpen: false, extOpen: false };
    var mainOpen = false;
    var extOpen = false;
    try {
        var mw = whWin.add(0x48).readPointer();
        if (mw && !mw.isNull()) {
            mainOpen = (mw.add(0x48).readU8() === 1);
        }
    } catch (eM) {}
    try {
        var ew = whWin.add(0x50).readPointer();
        if (ew && !ew.isNull()) {
            extOpen = (ew.add(0x48).readU8() === 1);
        }
    } catch (eE) {}
    return { mainOpen: mainOpen, extOpen: extOpen };
}
var _autoReportConfirmUntilMs = 0;
var _autoReportKillerName = "";
var _autoReportConfirmCount = 0;

function _isPkReportDialogText(idStr, title, msg) {
    var comb = (String(idStr || "") + " " + String(title || "") + " " + String(msg || "")).toLowerCase();
    if (_autoReportKillerName && _autoReportKillerName.length > 0 && comb.indexOf(_autoReportKillerName.toLowerCase()) !== -1) {
        return true;
    }
    var kws = [
        "report", "denunc", "denúncia", "denuncia", "killer", "murder",
        "guard", "bounty", "pk", "tố cáo", "to cao", "cảnh vệ", "lính canh"
    ];
    for (var i = 0; i < kws.length; i++) {
        if (comb.indexOf(kws[i]) !== -1) return true;
    }
    return false;
}
var pendingQuestNextAction = null;
var pendingQuestPickups = [];
var lastQuestPickupDone = 0;
var lastQuestPickupErr = "";

function flushQuestPickupsOnMainThread() {
    if (!pendingQuestPickups || pendingQuestPickups.length === 0) return;
    var batch = pendingQuestPickups.splice(0, pendingQuestPickups.length);
    var picked = 0;
    for (var i = 0; i < batch.length; i++) {
        var it = batch[i];
        try {
            if (nativeUserInvPickItem !== null && it.itemPtr && !it.itemPtr.isNull()) {
                nativeUserInvPickItem(it.vIdx, it.itemPtr, ptr(0));
                picked++;
            }
        } catch (ePK) { lastQuestPickupErr = String(ePK); }
    }
    lastQuestPickupDone += picked;
}
var lastQuestClickDebug = { done: false, ok: false, method: "", qWinOpen: false, nextBtnFound: false, currentData: -1, error: "" };

function performQuestNextClickOnMainThread(gui, wantIndex) {
    var dbg = { done: true, ok: false, method: "", qWinOpen: false, nextBtnFound: false, currentData: -1, error: "" };
    try {
        var qm = getQuestManagerPtr();
        if (qm && !qm.isNull()) {
            try { dbg.currentData = qm.add(0x2C).readS32(); } catch (eCD) {}
        }
        var activeGui = gui;
        if (!activeGui || activeGui.isNull()) {
            try { if (nativeGetGameUI !== null) activeGui = nativeGetGameUI(); } catch (eGG) {}
        }
        var qWin = ptr(0);
        if (activeGui && !activeGui.isNull()) {
            var qwOff = off('__UI_QUEST_NPC_WINDOW__');
            if (!qwOff.isNull()) {
                qWin = activeGui.add(qwOff).readPointer();
            }
        }
        if (qWin && !qWin.isNull()) {
            try {
                var mWin = qWin.add(0x20).readPointer();
                if (!mWin.isNull()) {
                    dbg.qWinOpen = (mWin.add(0x48).readU8() === 1);
                }
            } catch (eMW) {}

            var nextBtn = ptr(0);
            try { nextBtn = qWin.add(0x40).readPointer(); } catch (eNB) {}
            if (nextBtn && !nextBtn.isNull()) {
                dbg.nextBtnFound = true;
                // Ưu tiên 1: Bấm trực tiếp NextButton (ACCEPT / CONTINUE / OK) chuẩn Unity Button.Press()
                if (dbg.qWinOpen && nativeButtonPress !== null) {
                    try {
                        nativeButtonPress(nextBtn, ptr(0));
                        dbg.ok = true;
                        dbg.method = "Button.Press(NextButton)";
                    } catch (eBP) {
                        dbg.error = "Button.Press:" + eBP.toString();
                    }
                }
                // Ưu tiên 2: Kích hoạt trực tiếp NextButton.onClick UnityEvent.Invoke()
                if (!dbg.ok && dbg.qWinOpen) {
                    var invokeFn = nativeUnityEvent_Invoke || nativeUnityEventInvoke;
                    if (invokeFn !== null) {
                        try {
                            var onClick = nextBtn.add(0x100).readPointer();
                            if (onClick && !onClick.isNull()) {
                                invokeFn(onClick, ptr(0));
                                dbg.ok = true;
                                dbg.method = "UnityEvent.Invoke(NextButton.onClick)";
                            }
                        } catch (eUE) {
                            dbg.error = (dbg.error ? dbg.error + "; " : "") + "UnityEvent:" + eUE.toString();
                        }
                    }
                }
            }

            // Ưu tiên 3: Gọi trực tiếp handler MQuestNpcWindow.FELBIIDPABC(qWin)
            if (!dbg.ok && dbg.qWinOpen && nativeQuestNpcNextClick !== null) {
                try {
                    nativeQuestNpcNextClick(qWin, ptr(0));
                    dbg.ok = true;
                    dbg.method = "MQuestNpcWindow.NextClick";
                } catch (eNC) {
                    dbg.error = (dbg.error ? dbg.error + "; " : "") + "NextClick:" + eNC.toString();
                }
            }
        }

        // Ưu tiên 4: Fallback gọi trực tiếp QuestManager.DDPEPNGHBLG(idx, 1) -> gửi gói C1:A2
        if (!dbg.ok) {
            var useIdx = (dbg.currentData >= 0 && dbg.currentData <= 31) ? dbg.currentData : parseInt(wantIndex);
            if (useIdx >= 0 && nativeQuestSendState !== null) {
                try {
                    nativeQuestSendState(useIdx, 1, ptr(0));
                    dbg.ok = true;
                    dbg.method = "QuestManager.SendState(idx=" + useIdx + ")";
                } catch (eQS) {
                    dbg.error = (dbg.error ? dbg.error + "; " : "") + "SendState:" + eQS.toString();
                }
            }
        }
    } catch (eTop) {
        dbg.error = eTop.toString();
    }
    lastQuestClickDebug = dbg;
}

function sendDropPacket(slot, targetX, targetY) {
    try {
        var s = parseInt(slot) & 0xFF;
        // BẢO VỆ TUYỆT ĐỐI: Không bao giờ vứt các slot trang bị trên người (0..11)
        if (s < 12) return false;
        var tx = Math.max(1, Math.min(254, parseInt(targetX || 0))) & 0xFF;
        var ty = Math.max(1, Math.min(254, parseInt(targetY || 0))) & 0xFF;
        // Chuẩn MEGAMU UserInventory.NNFBKAIGNEM (RVA <RVA>) + Header <RVA>:
        // C3 packet (byte[0] = 0x30..0x3E), len = 6, opcode = 0x23 ^ 0xCB = 0xE8, [tx, ty, slot]
        var encDrop = 0x23 ^ 0xCB; // 0xE8
        return sendGSPacket([0xC3, 0x06, encDrop, tx, ty, s], true);
    } catch (eDropPkt) {
        return false;
    }
}

function findInventorySlotObj(slot) {
    // Tìm ItemSlot* tương ứng trong MainStorage (+0x58: 12..75), ExtInventoryStorage1 (+0x60: 76..107), ExtInventoryStorage2 (+0x68: 108..139).
    // Layout Dictionary<int, ItemSlot>.Entry (24 bytes): +0x00 hashCode (>=0), +0x04 next, +0x08 int key (slot), +0x10 ItemSlot* value.
    try {
        var s = parseInt(slot);
        if (s < 12 || nativeGetGameUI === null) return ptr(0);
        var gui = nativeGetGameUI();
        if (!gui || gui.isNull()) return ptr(0);
        var invWinOff = off('__UI_INVENTORY_WINDOW__');
        var invWin = invWinOff.isNull() ? gui.add(ptr('0x190')).readPointer() : gui.add(invWinOff).readPointer();
        if (!invWin || invWin.isNull()) return ptr(0);
        var storageOffsets = (s < 76) ? [0x58, 0x60, 0x68] : [0x60, 0x68, 0x58];
        for (var si = 0; si < storageOffsets.length; si++) {
            try {
                var st = invWin.add(storageOffsets[si]).readPointer();
                if (!st || st.isNull()) continue;
                var cellsDict = st.add(0x38).readPointer();
                if (!cellsDict || cellsDict.isNull()) continue;
                var entriesPtr = cellsDict.add(0x18).readPointer();
                var cCount = cellsDict.add(0x20).readS32();
                if (!entriesPtr || entriesPtr.isNull() || cCount <= 0 || cCount > 256) continue;
                for (var ci = 0; ci < cCount; ci++) {
                    var cEntry = entriesPtr.add(0x20 + ci * 24);
                    if (cEntry.readS32() < 0) continue; // hashCode < 0 -> free entry
                    var cKey = cEntry.add(0x08).readS32();
                    if (cKey === s) {
                        var cand = cEntry.add(0x10).readPointer();
                        if (cand && !cand.isNull()) {
                            try {
                                if (cand.add(0x20).readS32() === s) return cand;
                            } catch (eChkSlot) {
                                return cand;
                            }
                        }
                    }
                }
            } catch (eSt) {}
        }
    } catch (eFindSlot) {}
    return ptr(0);
}

function getItemStorageStaticFields() {
    try {
        var isTypeInfoOff = off('__ITEM_STORAGE_TYPE_INFO__');
        if (!isTypeInfoOff.isNull()) {
            var isTypeInfo = baseAddr.add(isTypeInfoOff).readPointer();
            if (!isTypeInfo.isNull()) {
                return isTypeInfo.add(0xB8).readPointer();
            }
        }
    } catch (eISSF) {}
    return ptr(0);
}

function setItemStorageSellingSlot(slot) {
    // BẮT BUỘC: Khi Server trả gói C3:33 (UserInventory.ALLEPIKEBML -> ItemStorage.LDEPOIPHNOO),
    // Client đọc static ItemStorage.SellingSlot (+0x20) để biết slot nào cần xóa khỏi UserInventory._Items!
    try {
        var isStatic = getItemStorageStaticFields();
        if (isStatic.isNull()) return ptr(0);
        var slotObj = findInventorySlotObj(slot);
        if (!slotObj.isNull()) {
            isStatic.add(0x20).writePointer(slotObj);
            return slotObj;
        }
    } catch (eSetSS) {}
    return ptr(0);
}

function clearItemStorageSellingSlot() {
    try {
        var isStatic = getItemStorageStaticFields();
        if (!isStatic.isNull()) {
            isStatic.add(0x20).writePointer(ptr(0));
        }
    } catch (eClrSS) {}
}

var pendingSellSlot = null;

function sendSellPacket(slot) {
    try {
        var s = parseInt(slot) & 0xFF;
        // BẢO VỆ TUYỆT ĐỐI: Không bao giờ bán các slot trang bị trên người (0..11)
        if (s < 12) return false;

        ensureThreadAttached();

        // 1. Gán ItemStorage.SellingSlot TRƯỚC KHI gửi gói C3:33 để Client xử lý xóa item ngay khi nhận phản hồi C3:33
        setItemStorageSellingSlot(s);

        // 2. Lấy itemPtr hiện tại (nếu có) để truyền cho AFCIKPDMOCC(int slot, MOFAGGHDOFI item)
        var itemPtr = ptr(0);
        try {
            var itemsArr = _getLiveItemsArraySafe();
            if (itemsArr && !itemsArr.isNull()) {
                itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
            }
        } catch (eIP) {}

        // 3. Ưu tiên gọi đúng hàm bán chính thức của client: Mega.UserInventory.AFCIKPDMOCC(slot, item) @ <RVA> -> C3:33
        if (nativeUserInvSell !== null) {
            try {
                nativeUserInvSell(s, itemPtr, ptr(0));
                return true;
            } catch (eUISell) {}
        }

        // 4. Chuẩn protocol bán đồ NPC MEGAMU (verified từ AFCIKPDMOCC @ <RVA> + NCIAEIPCNGI @ <RVA>):
        // Opcode 0x33 = CGItemSellRecv (KHÔNG phải 0x32 BUY!), XOR 0xCB -> 0xF8, 4 byte: [0xC3, 0x04, 0xF8, slot]
        var encSell = 0x33 ^ 0xCB; // 0xF8
        return sendGSPacket([0xC3, 0x04, encSell, s], true);
    } catch (eSellPkt) {
        return false;
    }
}

// ============================================================================
// MOSS JUNK DISPOSAL ENGINE (v2)
// Vứt/bán đồ rác có xác minh từng ô + tự chẩn đoán vì sao server không nhận.
// ============================================================================

function isMerchantWindowOpen() {
    try {
        if (nativeGetGameUI === null) return false;
        var gui = nativeGetGameUI();
        if (gui.isNull()) return false;
        var mo = off('__UI_MERCHANT_WINDOW__');
        var mw = mo.isNull() ? gui.add(ptr('0x1A0')).readPointer() : gui.add(mo).readPointer();
        if (mw.isNull()) return false;
        var win = mw.add(0x20).readPointer();
        if (win.isNull()) return false;
        return win.add(0x48).readU8() === 1;
    } catch (eMWO) {
        return false;
    }
}

function readDisposalContext() {
    // Thu thập mọi thứ cần thiết để chẩn đoán vì sao việc dọn rác thất bại.
    var ctx = { gsOk: false, playerOk: false, invOk: false, x: 0, y: 0, merchantOpen: false, mossOpen: false };
    try { ctx.playerOk = !getPlayerPtr().isNull(); } catch (e1) {}
    try { ctx.gsOk = !getGSConnection().isNull(); } catch (e2) {}
    try {
        var p = getPlayerPtr();
        if (!p.isNull()) {
            var c = p.add(off('__PLAYER_COORD__')).readPointer();
            if (!c.isNull()) {
                ctx.x = c.add(0x10).readS32();
                ctx.y = c.add(0x14).readS32();
            }
            if (ctx.x === 0 && ctx.y === 0) {
                var lc = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                if (!lc.isNull()) {
                    ctx.x = lc.add(0x10).readS32();
                    ctx.y = lc.add(0x14).readS32();
                }
            }
            ctx.invOk = !p.add(off('__PLAYER_INVENTORY__')).readPointer().isNull();
        }
    } catch (e3) {}
    ctx.merchantOpen = isMerchantWindowOpen();
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var mw = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                if (!mw.isNull()) {
                    var w = mw.add(0x20).readPointer();
                    if (!w.isNull()) ctx.mossOpen = (w.add(0x48).readU8() === 1);
                }
            }
        }
    } catch (e4) {}
    return ctx;
}

// Gửi gói drop cho từng slot theo vòng xoắn toạ độ quanh nhân vật, chờ phản hồi C1:23 + xác minh RAM.
// Trả về danh sách slot đã mất khỏi hòm đồ (dropped), còn lại (stayed) và số lần server từ chối (serverRejected).
var _DROP_SPIRAL_OFFSETS = [
    [0, 0], [1, 0], [-1, 0], [0, 1], [0, -1],
    [1, 1], [-1, 1], [1, -1], [-1, -1],
    [2, 0], [-2, 0], [0, 2], [0, -2],
    [2, 1], [2, -1], [-2, 1], [-2, -1],
    [1, 2], [-1, 2], [1, -2], [-1, -2],
    [2, 2], [-2, 2], [2, -2], [-2, -2]
];
function runDropPass(slots, itemsArr, ctx, offsetX, offsetY, useNativeRandom) {
    var out = { dropped: [], stayed: [], sendFailed: 0, attempted: 0, serverRejected: 0, serverAccepted: 0 };
    var startSeq = _dropRecvSeq;
    var triedSlots = [];
    for (var i = 0; i < slots.length; i++) {
        var s = slots[i];
        var before = itemsArr.add(0x20 + s * 8).readPointer();
        if (before.isNull()) continue;
        out.attempted++;
        triedSlots.push(s);
        var sp = _DROP_SPIRAL_OFFSETS[i % _DROP_SPIRAL_OFFSETS.length];
        var tx = (ctx.x > 0) ? Math.max(1, Math.min(254, ctx.x + offsetX + sp[0])) : 0;
        var ty = (ctx.y > 0) ? Math.max(1, Math.min(254, ctx.y + offsetY + sp[1])) : 0;
        var sent = false;
        try {
            // Ưu tiên hàm drop thật của client UserInventory.NNFBKAIGNEM (<RVA>) gửi C3:23 chuẩn,
            // fallback về sendDropPacket (C3:23 wire frame giống hệt).
            if (nativeUserInvDrop !== null) {
                sent = useNativeRandom ? dropSlotNative(s, 0, 0) : dropSlotNative(s, tx, ty);
            }
            if (!sent) sent = sendDropPacket(s, tx || (ctx.x + 1), ty || ctx.y);
        } catch (eSD) { sent = false; }
        if (!sent) {
            out.sendFailed++;
            continue;
        }
        try { Thread.sleep(0.085); } catch (eSl1) {}
    }
    // Chờ server phản hồi C1:23 / xóa item khỏi RAM (bù RTT ~225ms VN-Brazil, tối đa 650ms, thoát sớm khi xong hết)
    if (triedSlots.length > 0 && out.sendFailed < out.attempted) {
        for (var w = 0; w < 13; w++) {
            try { Thread.sleep(0.05); } catch (eSl2) {}
            var allResolved = true;
            for (var k = 0; k < triedSlots.length; k++) {
                var ts = triedSlots[k];
                var curP = itemsArr.add(0x20 + ts * 8).readPointer();
                var rec = _dropRecvBySlot[ts];
                var gotReply = (rec && rec.seq > startSeq);
                if (!curP.isNull() && !gotReply) {
                    allResolved = false;
                    break;
                }
            }
            if (allResolved) break;
        }
    }
    for (var j = 0; j < slots.length; j++) {
        var s2 = slots[j];
        var after = itemsArr.add(0x20 + s2 * 8).readPointer();
        var rec2 = _dropRecvBySlot[s2];
        if (after.isNull()) {
            out.dropped.push(s2);
            if (rec2 && rec2.seq > startSeq && rec2.ok) out.serverAccepted++;
        } else {
            out.stayed.push(s2);
            if (rec2 && rec2.seq > startSeq && !rec2.ok) out.serverRejected++;
        }
    }
    return out;
}

// Bán từng slot cho Merchant đang mở (packet C3:33 + ItemStorage.SellingSlot) + xác minh từng ô bằng RAM.
// LƯU Ý QUAN TRỌNG: ItemStorage.SellingSlot là biến static đơn nên BẮT BUỘC chờ từng món hoàn tất rồi mới gửi món tiếp theo.
function runSellPass(slots, itemsArr) {
    var out = { sold: [], stayed: [], sendFailed: 0, attempted: 0 };
    for (var i = 0; i < slots.length; i++) {
        var s = slots[i];
        var before = itemsArr.add(0x20 + s * 8).readPointer();
        if (before.isNull()) continue;
        out.attempted++;
        var sent = false;
        try { sent = sendSellPacket(s); } catch (eSS) { sent = false; }
        if (!sent) {
            out.sendFailed++;
            out.stayed.push(s);
            continue;
        }
        var gone = false;
        for (var wi = 0; wi < 20; wi++) {
            try { Thread.sleep(0.05); } catch (eSl3) {}
            var cur = itemsArr.add(0x20 + s * 8).readPointer();
            if (cur.isNull() || !cur.equals(before)) {
                gone = true;
                break;
            }
        }
        if (gone) {
            out.sold.push(s);
            try { Thread.sleep(0.18); } catch (eSl4) {}
        } else {
            clearItemStorageSellingSlot();
            out.stayed.push(s);
            try { Thread.sleep(0.22); } catch (eSl5) {}
        }
    }
    return out;
}

// ============================================================================
// NON-BLOCKING UNITY MAINTHREAD JUNK DISPOSAL STATE MACHINE
// 100% chạy trên Unity MainThread (Game.Update) — KHÔNG BAO GIỜ Thread.sleep()
// hay gọi IL2CPP GC / Unity UI từ Frida RPC thread -> TRIỆT TIÊU AppHangB1!
// ============================================================================
var _junkJobSeq = 0;
var _junkDisposalJob = null;
var _singleDropJob = null;
var _pendingUnlockInventory = false;
var _pendingUnlockCharResetAutoMove = false;

function _getLiveItemsArraySafe() {
    try {
        var p = getPlayerPtr();
        if (!p || p.isNull()) return null;
        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
        if (!inv || inv.isNull()) return null;
        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
        return (!itemsArr || itemsArr.isNull()) ? null : itemsArr;
    } catch (eGLIA) {
        return null;
    }
}

function _finalizeJunkDisposalJob(job) {
    if (!job || job.done) return;
    var itemsArr = _getLiveItemsArraySafe();
    var finalRemaining = [];
    for (var i = 0; i < job.candidates.length; i++) {
        var cs = job.candidates[i];
        var stillThere = true;
        try {
            if (itemsArr && !itemsArr.isNull()) {
                stillThere = !itemsArr.add(0x20 + cs * 8).readPointer().isNull();
            }
        } catch (eRem) {}
        if (stillThere) finalRemaining.push(cs);
    }
    var cleaned = job.dropped.length + job.sold.length;
    var merchOpen = isMerchantWindowOpen();
    var reason = "done";
    if (cleaned === 0) {
        if (job.attempted === 0) reason = "not_attempted";
        else if (job.sendFailed === job.attempted) reason = "send_failed";
        else if (job.mode === "sell" && !merchOpen) reason = "merchant_closed";
        else if (!merchOpen) reason = "drop_blocked";
        else reason = "server_rejected";
    } else if (finalRemaining.length > 0) {
        reason = "partial";
    }
    job.active = false;
    job.done = true;
    job.phase = "done";
    job.result = {
        cleaned: cleaned,
        dropped: job.dropped.length,
        sold: job.sold.length,
        total: job.candidates.length,
        failed: finalRemaining.length,
        remaining: finalRemaining.length,
        reason: reason,
        mode: job.mode,
        gsOk: job.ctx.gsOk,
        coord: { x: job.ctx.x, y: job.ctx.y },
        merchantOpen: merchOpen,
        mossOpen: job.ctx.mossOpen,
        droppedSlots: job.dropped,
        soldSlots: job.sold,
        failedSlots: finalRemaining,
        sendFailed: job.sendFailed,
        serverRejected: job.serverRejected,
        serverAccepted: job.serverAccepted,
        sendError: lastSendError,
        nativeDropBound: (nativeUserInvDrop !== null),
        elapsedMs: Date.now() - job.startedAt,
        error: null
    };
}

function tickJunkDisposalMainThread() {
    if (shuttingDown) return;

    // 0. Xử lý unlock inventory/character an toàn trên Unity MainThread
    if (_pendingUnlockInventory) {
        _pendingUnlockInventory = false;
        var doResetAM = _pendingUnlockCharResetAutoMove;
        _pendingUnlockCharResetAutoMove = false;
        try { ensureDropAllowed(true); } catch (eU1) {}
        if (nativeCloseTalk !== null) {
            try { nativeCloseTalk(); } catch (eU2) {}
        }
        try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eU3) {}
        if (doResetAM) {
            try {
                var pAM = getPlayerPtr();
                if (pAM && !pAM.isNull()) pAM.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
            } catch (eU4) {}
        }
    }

    var now = Date.now();

    // 1. Single-slot drop job trên Unity MainThread (cho dropInventorySlot)
    var sj = _singleDropJob;
    if (sj && sj.active && !sj.done) {
        try {
            var sArr = _getLiveItemsArraySafe();
            if (!sArr) {
                sj.done = true; sj.active = false;
                sj.result = { ok: false, err: "no_items_arr", slot: sj.slot };
            } else if (sj.phase === "send1") {
                ensureDropAllowed(true);
                sj.startSeq = _dropRecvSeq;
                var sent1 = false;
                if (nativeUserInvDrop !== null) sent1 = dropSlotNative(sj.slot, sj.x, sj.y);
                if (!sent1) sent1 = sendDropPacket(sj.slot, sj.x, sj.y);
                sj.sent = sent1;
                if (!sent1) {
                    sj.done = true; sj.active = false;
                    sj.result = { ok: false, sent: false, verified: false, serverRejected: false, allowed: true, slot: sj.slot, x: sj.x, y: sj.y, err: lastSendError || "send_failed" };
                } else {
                    sj.phase = "wait1";
                    sj.deadlineMs = now + 500;
                }
            } else if (sj.phase === "wait1" || sj.phase === "wait2") {
                var curP = sArr.add(0x20 + sj.slot * 8).readPointer();
                var rRec = _dropRecvBySlot[sj.slot];
                var gotReply = (rRec && rRec.seq > sj.startSeq);
                if (curP.isNull() || (gotReply && rRec.ok)) {
                    sj.done = true; sj.active = false;
                    sj.result = { ok: true, sent: sj.sent, verified: true, serverRejected: false, allowed: true, slot: sj.slot, x: sj.x, y: sj.y };
                } else if (gotReply && !rRec.ok) {
                    sj.done = true; sj.active = false;
                    sj.result = { ok: false, sent: sj.sent, verified: false, serverRejected: true, allowed: true, slot: sj.slot, x: sj.x, y: sj.y };
                } else if (now >= sj.deadlineMs) {
                    if (sj.phase === "wait1") {
                        sj.startSeq = _dropRecvSeq;
                        var retrySent = (nativeUserInvDrop !== null) ? dropSlotNative(sj.slot, 0, 0) : sendDropPacket(sj.slot, sj.x, sj.y);
                        if (retrySent) {
                            sj.phase = "wait2";
                            sj.deadlineMs = now + 450;
                        } else {
                            sj.done = true; sj.active = false;
                            sj.result = { ok: false, sent: sj.sent, verified: false, serverRejected: false, allowed: true, slot: sj.slot, x: sj.x, y: sj.y };
                        }
                    } else {
                        sj.done = true; sj.active = false;
                        sj.result = { ok: false, sent: sj.sent, verified: false, serverRejected: false, allowed: true, slot: sj.slot, x: sj.x, y: sj.y };
                    }
                }
            }
        } catch (eSJ) {
            sj.done = true; sj.active = false;
            sj.result = { ok: false, err: String(eSJ), slot: sj.slot };
        }
    }

    // 2. Batch junk disposal state machine trên Unity MainThread
    var job = _junkDisposalJob;
    if (!job || !job.active || job.done) return;

    try {
        var itemsArr = _getLiveItemsArraySafe();
        if (!itemsArr) {
            _finalizeJunkDisposalJob(job);
            return;
        }

        if (job.phase === "drop_pass1" || job.phase === "drop_pass2" || job.phase === "drop_pass3") {
            if (!job.dropAllowedApplied) {
                ensureDropAllowed(true);
                job.dropAllowedApplied = true;
            }
            if (now < job.nextActionAtMs) return;

            var isPass2 = (job.phase === "drop_pass2");
            var isPass3 = (job.phase === "drop_pass3");
            while (job.idx < job.queue.length) {
                var s = job.queue[job.idx];
                var curIdx = job.idx;
                job.idx++;
                var beforeP = itemsArr.add(0x20 + s * 8).readPointer();
                if (beforeP.isNull()) continue;

                job.attempted++;
                job.passAttempted++;
                job.triedSlots.push(s);

                var spiralIdx = isPass2 ? ((curIdx + 11) % _DROP_SPIRAL_OFFSETS.length)
                              : (isPass3 ? ((curIdx + 19) % _DROP_SPIRAL_OFFSETS.length) : (curIdx % _DROP_SPIRAL_OFFSETS.length));
                var sp = _DROP_SPIRAL_OFFSETS[spiralIdx];
                var tx = (job.ctx.x > 0) ? Math.max(1, Math.min(254, job.ctx.x + sp[0])) : 0;
                var ty = (job.ctx.y > 0) ? Math.max(1, Math.min(254, job.ctx.y + sp[1])) : 0;

                var sent = false;
                try {
                    if (nativeUserInvDrop !== null) {
                        // Pass 1 & Pass 2: thả theo lưới 25 ô 5x5 tránh trùng ô đã rơi; Pass 3: để client tự chọn ô trống ngẫu nhiên
                        sent = isPass3 ? dropSlotNative(s, 0, 0) : dropSlotNative(s, tx, ty);
                    }
                    if (!sent) sent = sendDropPacket(s, tx || (job.ctx.x + 1), ty || job.ctx.y);
                } catch (eSendDrop) { sent = false; }

                if (!sent) {
                    job.sendFailed++;
                }
                job.nextActionAtMs = now + (isPass3 ? 155 : (isPass2 ? 120 : 95));
                return; // Gửi tối đa 1 món mỗi nhịp -> 0ms lag, tránh rate-limit & trùng ô rơi!
            }

            // Đã gửi hết hàng đợi của pass hiện tại -> chuyển sang pha chờ xác minh non-blocking
            job.phase = isPass3 ? "drop_pass3_wait" : (isPass2 ? "drop_pass2_wait" : "drop_pass1_wait");
            job.verifyDeadlineMs = now + (isPass3 ? 1000 : (isPass2 ? 900 : 850));
            return;
        }

        if (job.phase === "drop_pass1_wait" || job.phase === "drop_pass2_wait" || job.phase === "drop_pass3_wait") {
            var isP1Wait = (job.phase === "drop_pass1_wait");
            var isP2Wait = (job.phase === "drop_pass2_wait");
            var allResolved = true;
            for (var k = 0; k < job.triedSlots.length; k++) {
                var ts = job.triedSlots[k];
                var pCheck = itemsArr.add(0x20 + ts * 8).readPointer();
                var rec = _dropRecvBySlot[ts];
                var gotRep = (rec && rec.seq > job.passStartSeq);
                if (!pCheck.isNull() && !gotRep) {
                    allResolved = false;
                    break;
                }
            }
            if (!allResolved && now < job.verifyDeadlineMs) return;

            var passDropped = 0;
            var passRejected = 0;
            var stayed = [];
            for (var j = 0; j < job.triedSlots.length; j++) {
                var s2 = job.triedSlots[j];
                var afterP = itemsArr.add(0x20 + s2 * 8).readPointer();
                var rec2 = _dropRecvBySlot[s2];
                if (afterP.isNull()) {
                    if (job.dropped.indexOf(s2) === -1) job.dropped.push(s2);
                    passDropped++;
                    if (rec2 && rec2.seq > job.passStartSeq && rec2.ok) job.serverAccepted++;
                } else {
                    stayed.push(s2);
                    if (rec2 && rec2.seq > job.passStartSeq && !rec2.ok) {
                        job.serverRejected++;
                        passRejected++;
                    }
                }
            }

            if (isP1Wait) {
                var allExplicitlyRejected = (job.passAttempted >= 2 && passDropped === 0 && passRejected >= job.passAttempted);
                if (stayed.length > 0 && !allExplicitlyRejected) {
                    job.phase = "drop_pass2";
                    job.queue = stayed;
                    job.idx = 0;
                    job.triedSlots = [];
                    job.passAttempted = 0;
                    job.passStartSeq = _dropRecvSeq;
                    job.nextActionAtMs = now + 120;
                    return;
                }
            } else if (isP2Wait) {
                var allExplicitlyRejected2 = (job.passAttempted >= 2 && passDropped === 0 && passRejected >= job.passAttempted);
                if (stayed.length > 0 && (job.dropped.length > 0 || !allExplicitlyRejected2)) {
                    job.phase = "drop_pass3";
                    job.queue = stayed;
                    job.idx = 0;
                    job.triedSlots = [];
                    job.passAttempted = 0;
                    job.passStartSeq = _dropRecvSeq;
                    job.nextActionAtMs = now + 150;
                    return;
                }
            }

            // Chuyển sang bước bán nếu mode === "auto" và Merchant đang mở
            if (stayed.length > 0 && job.mode === "auto" && isMerchantWindowOpen()) {
                job.phase = "sell_pass";
                job.queue = stayed;
                job.idx = 0;
                job.triedSlots = [];
                job.nextActionAtMs = now;
                return;
            }

            _finalizeJunkDisposalJob(job);
            return;
        }

        if (job.phase === "sell_pass") {
            // Chờ ô đang bán (SellingSlot là biến static đơn — không được gửi chồng ô tiếp theo trước khi Server xác nhận!)
            if (job.currentSellSlot !== undefined && job.currentSellSlot !== null) {
                var curS = job.currentSellSlot;
                var curPtr = itemsArr.add(0x20 + curS * 8).readPointer();
                if (curPtr.isNull()) {
                    if (job.sold.indexOf(curS) === -1) job.sold.push(curS);
                    job.currentSellSlot = null;
                    job.nextActionAtMs = now + 180;
                } else if (now < job.sellWaitUntilMs) {
                    return;
                } else {
                    clearItemStorageSellingSlot();
                    job.currentSellSlot = null;
                    job.nextActionAtMs = now + 220;
                }
            }
            if (now < job.nextActionAtMs) return;
            while (job.idx < job.queue.length) {
                var ss = job.queue[job.idx];
                job.idx++;
                if (itemsArr.add(0x20 + ss * 8).readPointer().isNull()) continue;
                job.attempted++;
                job.triedSlots.push(ss);
                var sOk = false;
                try { sOk = sendSellPacket(ss); } catch (eS) { sOk = false; }
                if (!sOk) {
                    job.sendFailed++;
                    job.nextActionAtMs = now + 60;
                    return;
                }
                job.currentSellSlot = ss;
                job.sellWaitUntilMs = now + 1000;
                return;
            }
            job.phase = "sell_wait";
            job.verifyDeadlineMs = now + 250;
            return;
        }

        if (job.phase === "sell_wait") {
            var allSoldGone = true;
            for (var sk = 0; sk < job.triedSlots.length; sk++) {
                if (!itemsArr.add(0x20 + job.triedSlots[sk] * 8).readPointer().isNull()) {
                    allSoldGone = false;
                    break;
                }
            }
            if (!allSoldGone && now < job.verifyDeadlineMs) return;
            for (var sj2 = 0; sj2 < job.triedSlots.length; sj2++) {
                var slotSold = job.triedSlots[sj2];
                if (itemsArr.add(0x20 + slotSold * 8).readPointer().isNull()) {
                    if (job.sold.indexOf(slotSold) === -1) job.sold.push(slotSold);
                }
            }
            _finalizeJunkDisposalJob(job);
            return;
        }
    } catch (eJobTick) {
        job.active = false;
        job.done = true;
        job.phase = "error";
        job.result = {
            cleaned: job.dropped.length + job.sold.length,
            dropped: job.dropped.length,
            sold: job.sold.length,
            total: job.candidates.length,
            failed: Math.max(0, job.candidates.length - job.dropped.length - job.sold.length),
            reason: "exception",
            error: String(eJobTick),
            elapsedMs: Date.now() - job.startedAt
        };
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
            // Ưu tiên gọi đúng hàm gốc Mega.NpcManager$$PCKGCMNFJND (<RVA>) của GameAssembly.dll
            if (nativeNpcSendTalk !== null) {
                try {
                    nativeNpcSendTalk(lugard, ptr(0));
                    return true;
                } catch (eNST) {}
            }
            // Fallback chuẩn protocol C3:30 Big-Endian (đã xác minh từ <RVA> + <RVA>)
            var npcKey = -1;
            try { npcKey = lugard.add(0x20).readS32(); } catch (eK) {}
            if (npcKey > 0) {
                var kHigh = (npcKey >> 8) & 0xFF;
                var kLow = npcKey & 0xFF;
                sendGSPacket([0xC3, 0x05, 0x30, kHigh, kLow]);
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
        var charon = getOrCreateCharonPtr();
        if (charon && !charon.isNull()) {
            var npcKey = -1;
            try { npcKey = charon.add(0x20).readS32(); } catch (eK) {}
            if (npcKey > 0) {
                var kLow = npcKey & 0xFF;
                var kHigh = (npcKey >> 8) & 0xFF;
                sendGSPacket([0xC1, 0x05, 0x30, kLow, kHigh]);
                sendGSPacket([0xC1, 0x06, 0x30, kLow, kHigh, 0x00]);
                sendGSPacket([0xC1, 0x05, 0xFB, kLow, kHigh]);
                sendGSPacket([0xC1, 0x06, 0xFB, kLow, kHigh, 0x00]);
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
        var relSlot = (actualSlot >= 12) ? (actualSlot - 12) : actualSlot;
        // Bóc tách REA: Client MEGAMU tại RVA <RVA> thực hiện `add dil, 0xc` trước khi ghi vào packet
        // Do đó wireSlot = actualSlot + 12 là byte chuẩn client chính thức gửi lên GameServer
        var wireSlot = (actualSlot + 12) & 0xFF;
        var s1 = actualSlot & 0xFF;
        var s2 = relSlot & 0xFF;
        var lvl = level & 0xFF;

        // 1. Opcode 0x90 (Chuẩn IL2CPP Client chính thống DevilSquare.ECEGJEAOELA.ILEAOLLJKPG - RVA <RVA>)
        // Lưu ý REA: Hàm <RVA> mã hóa opcode bằng XOR 0xCB -> 0x90 ^ 0xCB = 0x5B
        var ok1 = sendGSPacket([0xC1, 0x05, 0x5B, lvl, wireSlot]);
        var ok2 = sendGSPacket([0xC1, 0x05, 0x90, lvl, wireSlot]);
        var ok3 = sendGSPacket([0xC1, 0x05, 0x5B, lvl, s1]);
        var ok4 = sendGSPacket([0xC1, 0x05, 0x90, lvl, s1]);

        // 2. Opcode 0x1E (Phương thức native DevilSquare.OMKNMKGNIPF - RVA <RVA>)
        // 0x1E ^ 0xCB = 0xD5
        var ok5 = sendGSPacket([0xC1, 0x05, 0xD5, lvl, wireSlot]);
        var ok6 = sendGSPacket([0xC1, 0x05, 0x1E, lvl, wireSlot]);

        // 3. Opcode 0xC2 (Phương thức native DevilSquare.HNCDPEIBGPG - RVA <RVA>)
        // 0xC2 ^ 0x9E = 0x5C
        var ok7 = sendGSPacket([0xC1, 0x05, 0x5C, lvl, wireSlot]);
        var ok8 = sendGSPacket([0xC1, 0x05, 0xC2, lvl, wireSlot]);

        return ok1 || ok2 || ok3 || ok4 || ok5 || ok6 || ok7 || ok8;
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

function ensureDropAllowed(allowUiCalls) {
    var ok = true;
    var doUi = (allowUiCalls === true);
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
    // CHỈ gọi hàm Unity UI (nativeWindowHide / ensureMossRollButtonActive) khi đang trên Unity MainThread (allowUiCalls === true)
    // để TUYỆT ĐỐI tránh deadlock/AppHangB1 khi RPC gọi từ luồng nền Frida!
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var invOff = off('__UI_INVENTORY_WINDOW__');
                var invWin = invOff.isNull() ? gui.add(ptr('0x190')).readPointer() : gui.add(invOff).readPointer();
                if (!invWin.isNull()) {
                    // Reset enum tương tác về None (0 = None, 1 = Repair, 2 = Divide, 3 = Disassembly, 4 = QuickMove, 5 = QuickDrop)
                    invWin.add(0x158).writeU32(0); // LDHAEAKCJKE = None
                    invWin.add(0x160).writePointer(ptr(0)); // MKGKAFADNHG = null

                    // Ẩn QuickDropWindow (0xF8) nếu đang kẹt
                    var qdWin = invWin.add(0xF8).readPointer();
                    if (!qdWin.isNull()) {
                        if (doUi && nativeWindowHide !== null) {
                            try { nativeWindowHide(qdWin, ptr(0)); } catch (eQD) {}
                        }
                        qdWin.add(0x48).writeU8(0);
                    }

                    // Ẩn DivideWindow (0xC8) nếu đang kẹt
                    var divWin = invWin.add(0xC8).readPointer();
                    if (!divWin.isNull()) {
                        if (doUi && nativeWindowHide !== null) {
                            try { nativeWindowHide(divWin, ptr(0)); } catch (eDIV) {}
                        }
                        divWin.add(0x48).writeU8(0);
                    }
                }

                // 3. Phục hồi cửa sổ Moss nếu đang kẹt spinner/loading (chỉ gọi trên MainThread)
                if (doUi) {
                    var mossOff = off('__UI_MOSS_WINDOW__');
                    var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
                    if (!mossWin.isNull()) {
                        ensureMossRollButtonActive(mossWin, true);
                    }
                }
            }
        }
    } catch (eInv) {}

    return ok;
}

// <RVA> là RVA cũ không còn tồn tại trên build hiện tại -> luôn dùng JIAFPMMDOPG (TableItem tại +0x58) an toàn 100%
var nativeGetItemName = null;

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
            // Priority 1: Info.Index tại +0x10 (dump: class Info { public int Index; // 0x10 })
            // Lưu ý: giá trị 0 là "chưa set" -> phải rơi xuống Priority 2, KHÔNG được return 0.
            try {
                var fieldIdx = te.add(0x10).readS32();
                if (fieldIdx > 0 && fieldIdx < 65536) return fieldIdx;
            } catch (eF) {}

            // Priority 2: (Section * 512 + Type) from TableItem (+0x58, +0x5C)
            try {
                var sec = te.add(0x58).readS32();
                var type = te.add(0x5C).readS32();
                if (sec >= 0 && sec < 16 && type >= 0 && type < 512 && (sec > 0 || type > 0)) {
                    var calcIdx = (sec * 512) + type;
                    if (calcIdx > 0 && calcIdx < 65536) return calcIdx;
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
        harmonyOpt: 0,
        opt380: 0
    };
    if (!itemPtr || itemPtr.isNull()) return p;
    try {
        p.itemIndex = readItemIndex(itemPtr);
        p.itemLevel = itemPtr.add(0x10).readS32();
        p.skill = itemPtr.add(0x14).readS32();
        p.luck = itemPtr.add(0x18).readS32();
        p.option = itemPtr.add(0x1C).readS32();
        p.excOpt = itemPtr.add(0x20).readS32();
        p.ancOpt = itemPtr.add(0x24).readS32();
        // Xác minh từ GameAssembly.dll (MOFAGGHDOFI$$LBBGNJFOOAK @ <RVA>):
        // +0x28 = HarmonyOpt (byte[10]), +0x2C = Option380 ((byte[9]&8)<<4), +0x38 = int[5] Socket slots (< 0xFF là có socket)
        p.harmonyOpt = itemPtr.add(0x28).readS32();
        p.opt380 = itemPtr.add(0x2C).readS32();
        p.sockOpt = hasItemSocketSlots(itemPtr) ? 1 : 0;
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
    if (isDragonItem(itemPtr, itemIndex)) return true;
    if (isDivineOrArchangelItem(itemPtr, itemIndex)) return true;

    var sec = Math.floor(itemIndex / 512);
    var type = itemIndex % 512;

    // 1. Bảo vệ bổ sung cho chế độ mặc định (không bật bán Exce):
    // Các item Season cao cấp (type >= 30 trong sec 0..11) và các set cao cấp kinh điển
    if (type >= 30 && sec <= 11) return true;
    if ((type === 3 || type === 15 || type === 17 || type === 18 || type === 19 || type === 20 || type === 22 || type === 23 || type === 24 || type === 25) && (sec >= 7 && sec <= 11)) {
        return true;
    }
    if (sec === 6 && type >= 17) return true;

    // 2. Lưới an toàn theo tên cho vật phẩm ngoài nhóm trang bị thường (sec >= 12 hoặc Index lỗi <= 0)
    if (isSafetyProtectedByName(itemPtr, itemIndex)) return true;
    return false;
}

function hasItemSocketSlots(itemPtr) {
    if (!itemPtr || (typeof itemPtr.isNull === "function" && itemPtr.isNull())) return false;
    try {
        if (typeof itemPtr.add !== "function") return false;
        var sockArr = itemPtr.add(0x38).readPointer();
        if (!sockArr || (typeof sockArr.isNull === "function" && sockArr.isNull())) return false;
        var len = sockArr.add(0x18).readS32();
        if (len <= 0 || len > 5) return false;
        for (var i = 0; i < len; i++) {
            var sv = sockArr.add(0x20 + i * 4).readS32();
            // 0xFF (255) = không có lỗ socket; 0xFE (254) = lỗ socket trống; < 254 = đã khảm seed
            if (sv >= 0 && sv < 255) return true;
        }
    } catch (eSockArr) {}
    return false;
}

function isDragonItem(itemPtr, itemIndex) {
    var sec = Math.floor(itemIndex / 512);
    var type = itemIndex % 512;

    // 1. ID Đồ Rồng xác minh 100% từ TableItem trong RAM MEGAMU:
    // - Set Rồng (sec 7..11): Dragon (1), Black Dragon (16), Great Dragon (21), Dragon Knight (29), Dragon mở rộng (67), [Bound] Dragon (130)
    if (sec >= 7 && sec <= 11 && (type === 1 || type === 16 || type === 21 || type === 29 || type === 67 || type === 130)) {
        return true;
    }
    // - Khiên Rồng (sec 6): Dragon Slayer Shield (5), Dragon Shield (13)
    if (sec === 6 && (type === 5 || type === 13)) return true;
    // - Vũ khí Rồng: Chaos Dragon Axe (sec 2, type 6), Dragon Lance (sec 3, type 2), Dragon Spear (sec 3, type 10), Dragon Soul Staff (sec 5, type 9)
    if (sec === 2 && type === 6) return true;
    if (sec === 3 && (type === 2 || type === 10)) return true;
    if (sec === 5 && type === 9) return true;

    // 2. Fallback theo tên vật phẩm (hỗ trợ EN/PT/ES/VN)
    var name = getItemName(itemPtr).toLowerCase();
    if (name.length > 0) {
        if (name.indexOf("dragon") !== -1 || name.indexOf("dragao") !== -1 || name.indexOf("dragão") !== -1 || name.indexOf("rồng") !== -1) {
            return true;
        }
    }
    return false;
}

function isDivineOrArchangelItem(itemPtr, itemIndex) {
    var sec = Math.floor(itemIndex / 512);
    var type = itemIndex % 512;

    // 1. ID Divine / Archangel xác minh 100% từ TableItem trong RAM MEGAMU:
    if (sec === 0 && (type === 19 || type === 31 || type === 32 || type === 51 || type === 60 || type === 76)) return true;
    if (sec === 1 && (type === 18 || type === 19)) return true;
    if (sec === 2 && (type === 13 || type === 21 || type === 25 || type === 34 || type === 35)) return true;
    if (sec === 3 && type === 27) return true;
    if (sec === 4 && (type === 18 || type === 26 || type === 30 || type === 46 || type === 47)) return true;
    if (sec === 5 && (type === 10 || type === 34 || type === 36 || type === 49 || type === 50)) return true;
    if (sec >= 7 && sec <= 11 && (type === 50 || type === 120)) return true; // Divine & Rune Divine Set

    // 2. Từ khóa Divine / Archangel / Ruud Master Tier theo tên
    var name = getItemName(itemPtr).toLowerCase();
    if (name.length > 0) {
        var highKeywords = [
            "divine", "divino", "divina", "archangel", "arcanjo", "thiên sứ", "nữ thần",
            "bloodangel", "darkangel", "holyangel", "awakening", "blue eye", "silver heart",
            "manticore", "brilliant", "apocalypse", "ruud"
        ];
        for (var k = 0; k < highKeywords.length; k++) {
            if (name.indexOf(highKeywords[k]) !== -1) {
                return true;
            }
        }
        // Riêng set Ruud Lightning (quần áo sec 7..11 hoặc type cao), KHÔNG chặn nhầm Lightning Sword/Axe thường (sec 0..5, type < 30)
        if (name.indexOf("lightning") !== -1 && (sec >= 7 || type >= 30 || itemIndex <= 0)) {
            return true;
        }
    }
    return false;
}

function isSafetyProtectedByName(itemPtr, itemIndex) {
    var sec = Math.floor(itemIndex / 512);
    if (sec < 12 && itemIndex > 0) return false;
    var name = getItemName(itemPtr).toLowerCase();
    if (name.length === 0) return false;
    var safetyKeywords = [
        "jewel", "jóia", "joia", "pedra", "gema", "ngọc",
        "bless", "soul", "chaos", "harmony", "creation", "life",
        "jewel of guardian", "joia do guardiao", "jóia do guardião", "đá hộ mệnh",
        "ticket", "vé", "mirror", "gương",
        "box", "rương", "wing", "cánh", "feather", "lông", "cloak",
        "seed", "fruit", "rune", "gem", "stone", "scroll", "horn",
        "pentagram", "errtel", "muun", "dark horse", "dark raven", "fenrir"
    ];
    for (var sk = 0; sk < safetyKeywords.length; sk++) {
        if (name.indexOf(safetyKeywords[sk]) !== -1) {
            return true;
        }
    }
    return false;
}

function isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent) {
    return itemProtectionReason(
        itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck,
        mossCat, maxJunkLvl, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent
    ) !== null;
}

// Trả về MÃ LÝ DO vì sao một món bị GIỮ LẠI (null = được phép dọn/bán).
// allowExcellent = true: cho phép bán đồ Hoàn Hảo (Exce) và đồ +5..+7 thường, nhưng VẪN BẢO VỆ TUYỆT ĐỐI
// Đồ Rồng (Dragon), Divine/Archangel/Ruud, Đồ Thần (Ancient), Đồ Socket, Harmony/380, cấp > maxJunkLvl, Ngọc/Vé/Cánh.
function itemProtectionReason(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent) {
    if (itemIndex < 0) return "unknown_item";
    var allowExc = (allowExcellent === 1 || allowExcellent === true || allowExcellent === "true");

    // 1. Bảo vệ Đồ Rồng / Divine / Archangel / Ruud:
    // - Khi bật bán Exce (allowExc = true): LUÔN bảo vệ Đồ Rồng & Divine/Archangel/Ruud (kể cả khi ignoreType=true),
    //   nhưng KHÔNG chặn nhầm các set thường (Grand Soul, Dark Soul, Dark Phoenix, Spiked Shield, Nikea Axe, type>=30 thường).
    // - Khi tắt bán Exce (allowExc = false): giữ nguyên bộ lọc isDivineOrDragonItem (tương thích 100%).
    if (allowExc) {
        if (isDragonItem(itemPtr, itemIndex)) return "dragon_item";
        if (isDivineOrArchangelItem(itemPtr, itemIndex)) return "divine_or_dragon";
        if (isSafetyProtectedByName(itemPtr, itemIndex)) return "jewel_section";
    } else {
        if (!ignoreTypeHeuristics && isDivineOrDragonItem(itemPtr, itemIndex)) return "divine_or_dragon";
    }

    // 2. Đồ Hoàn Hảo (Excellent) -> chỉ bảo vệ khi KHÔNG bật allowExcellent
    if (!allowExc && excOpt > 0) return "excellent";

    // 3. Đồ Thần (Ancient), Đồ Socket (mảng +0x38 hoặc sockOpt > 0), Harmony / 380 -> LUÔN bảo vệ
    if (ancOpt > 0) return "ancient";
    if (sockOpt > 0 || hasItemSocketSlots(itemPtr)) return "socket";
    if (harmonyOpt > 0) return "harmony";

    // 4. Đồ cấp cao vượt ngưỡng maxJunkLvl (mặc định bán Silvia max=7 -> giữ đồ >= +8)
    var effectiveMax = 4;
    if (maxJunkLvl !== undefined && maxJunkLvl !== null && maxJunkLvl >= 0) {
        effectiveMax = parseInt(maxJunkLvl);
    } else if (mossCat !== null && mossCat !== undefined && mossCat >= 0) {
        effectiveMax = 6;
    }
    if (effectiveMax <= 4) {
        if (itemLevel >= 5) return "level_over_max";
    } else if (itemLevel > effectiveMax) {
        return "level_over_max";
    }

    // 5. Toàn bộ ngọc, vé sự kiện, cánh, thú cưỡi, sách phép, cuộn kỹ năng (sec 12..15)
    var sec = Math.floor(itemIndex / 512);
    var typeInSec = itemIndex % 512;
    var isBasicMossJewelry = (mossCat === 5 && sec === 13 && (
        typeInSec === 8 || typeInSec === 9 || typeInSec === 12 || typeInSec === 13 ||
        (typeInSec >= 21 && typeInSec <= 28)
    ));
    if (!isBasicMossJewelry && sec >= 12 && sec <= 15) return "jewel_section";

    // 6. Giới hạn phạm vi theo danh mục Moss đang quay (trừ khi cleanEquipmentTrash bật hoặc mossCat < 0)
    if (mossCat !== null && mossCat !== undefined && mossCat >= 0) {
        var isEquipTrash = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true") && (sec >= 0 && sec <= 11);
        if (!isEquipTrash) {
            var matchCat = false;
            if (mossCat === 0 && (sec === 0 || sec === 1 || sec === 3)) matchCat = true;
            else if (mossCat === 1 && sec === 2) matchCat = true;
            else if (mossCat === 2 && sec === 4) matchCat = true;
            else if (mossCat === 3 && sec === 5) matchCat = true;
            else if (mossCat === 4 && sec === 6) matchCat = true;
            else if (mossCat === 5 && isBasicMossJewelry) matchCat = true;
            else if (mossCat >= 6 && sec <= 11) matchCat = true;
            if (!matchCat) return "wrong_moss_category";
        }
    }
    return null;
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

        var str = il2cpp_string_new(Memory.allocUtf8String(cmdText));
        if (str.isNull()) return false;

        var isSlashCmd = (cmdText.length > 0 && cmdText.charAt(0) === '/');
        var isServerCmd = (/^\/(m|warp|move|post|pack|unpack|reset|addstr|addagi|addvit|addene|addcmd)\b/i).test(cmdText);

        // 1. Đối với lệnh hệ thống client thuần túy (không phải lệnh server như /m, /post, /pack, /reset...),
        // CommandManager.Process trả về 0 nếu đã xử lý xong nội bộ.
        // Nếu trả về 1 hoặc là lệnh server, cần gửi qua mạng lên GameServer.
        if (isSlashCmd && !isServerCmd && nativeCommandManagerProcess !== null) {
            try {
                var handled = nativeCommandManagerProcess(str, ptr(0));
                if (handled === 0 || handled === false) return true; // Lệnh client đã được xử lý xong
            } catch (eCmd) {}
        }

        // 2. ƯU TIÊN SỐ 1: Gửi qua ChatFrame.Send với cờ force = true (1)
        // Đây là luồng chat UI chuẩn của game, tự động gọi Mega.Chat.Send và đồng bộ input
        var cf = getChatFrameInstance();
        if (!cf.isNull() && sendChatMessageNative !== null) {
            try {
                sendChatMessageNative(cf, str, 1, ptr(0));
                return true;
            } catch (eCF) {}
        }

        // 3. Fallback: Gửi lệnh chat ngầm 100% qua Mega.Chat.Send
        // Đây là hàm static gửi packet mạng trực tiếp lên GameServer trên Unity Main Thread,
        // HOÀN TOÀN NGẦM không mở khung chat, không cướp chuột/phím, không click màn hình.
        if (nativeStaticChatSend !== null) {
            try {
                nativeStaticChatSend(str, ptr(0));
                return true;
            } catch (eStatic) {}
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
        ensureThreadAttached();
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
            if (isAct === 1) {
                return true;
            }
            if (!p.isNull()) {
                // Đảm bảo xóa cờ AutoMove (player+0x4C4 = -1, player+0x4C0 = 0) trước khi bật Helper
                // (Vì UserHelper kiểm tra [player + 0x4C4] == -1 mới thực thi săn quái!)
                try {
                    p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
                    p.add(off('__AUTO_MOVE_TYPE__')).writeS32(-1);
                } catch (eClrAM) {}
            }
            var sent = false;
            // 1. Gọi UserHelper.Start() (NEIBNPAHOJO - RVA <RVA>)
            if (!h.isNull() && nativeStartHelper !== null) {
                try {
                    nativeStartHelper(h, ptr(0));
                    sent = true;
                } catch (eS1) {}
            }
            // 2. Gửi packet BF:51, 00 (Start) trực tiếp qua nativeHelperSendBf51 (OFFJIPBMOOE - RVA <RVA>)
            if (!sent && nativeHelperSendBf51 !== null) {
                try {
                    nativeHelperSendBf51(0, ptr(0));
                    sent = true;
                } catch (eBF0) {}
            }
            return sent;
        } else if (act === 'stop') {
            if (isAct === 0) {
                return true;
            }
            var sentStop = false;
            // 1. Gọi UserHelper.Stop() (GPPPGBCDGJP - RVA <RVA>)
            if (!h.isNull() && nativeStopHelper !== null) {
                try {
                    nativeStopHelper(h, ptr(0));
                    sentStop = true;
                } catch (eSt1) {}
            }
            // 2. Gửi packet BF:51, 01 (Stop) trực tiếp qua nativeHelperSendBf51 (OFFJIPBMOOE - RVA <RVA>)
            if (!sentStop && nativeHelperSendBf51 !== null) {
                try {
                    nativeHelperSendBf51(1, ptr(0));
                    sentStop = true;
                } catch (eBF1) {}
            }
            return sentStop;
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

        var k = ptr(0);
        if (!destC.isNull()) {
            try { k = destC.readPointer(); } catch (eKD) {}
        }
        if (k.isNull()) {
            try {
                var curC = pMove.add(off('__PLAYER_COORD__')).readPointer();
                if (!curC.isNull()) k = curC.readPointer();
            } catch (eK1) {}
        }
        if (k.isNull()) {
            try {
                var lastC = pMove.add(off('__PLAYER_LAST_COORD__')).readPointer();
                if (!lastC.isNull()) k = lastC.readPointer();
            } catch (eK2) {}
        }
        if (!k.isNull()) {
            cachedCoordKlass = k;
        } else if (cachedCoordKlass && !cachedCoordKlass.isNull()) {
            k = cachedCoordKlass;
        }

        // Cấp phát đối tượng Coord Managed trên GC heap nếu __AUTO_MOVE_DEST__ chưa khởi tạo
        // (AFDNIFKGNKN..ctor tại <RVA> lưu con trỏ Coord vào +0x18 và gọi il2cpp_gc_wbarrier_set_field)
        if (destC.isNull() && typeof il2cpp_object_new !== 'undefined' && il2cpp_object_new !== null && !k.isNull()) {
            try {
                ensureThreadAttached();
                destC = il2cpp_object_new(k);
                if (!destC.isNull()) {
                    pMove.add(off('__AUTO_MOVE_DEST__')).writePointer(destC);
                }
            } catch (eAllocC) {}
        }

        var isAutoMove = Boolean(target.autoMove);
        if (!destC.isNull()) {
            destC.add(0x10).writeS32(parseInt(target.x));
            destC.add(0x14).writeS32(parseInt(target.y));
            pMove.add(off('__AUTO_MOVE_DEST__')).writePointer(destC);
            // Chỉ gán __AUTO_MOVE_TYPE__ = 0 khi thực sự chạy AutoMove đường dài;
            // Với moveTo bước ngắn (step-out), giữ -1 để UserHelper (<RVA>) không bị khóa!
            pMove.add(off('__AUTO_MOVE_TYPE__')).writeS32(isAutoMove ? 0 : -1);
            pMove.add(off('__AUTO_MOVE_HELPER__')).writeU8(target.helper ? 1 : 0);
            pMove.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
            try {
                moveToNative(pMove, destC, 0.0, ptr(0), 0, 1, ptr(0));
            } catch (eM) {}
        } else if (!k.isNull()) {
            coordBuf.writePointer(k);
            coordBuf.add(0x08).writePointer(ptr(0));
            coordBuf.add(0x10).writeS32(parseInt(target.x));
            coordBuf.add(0x14).writeS32(parseInt(target.y));
            try {
                moveToNative(pMove, coordBuf, 0.0, ptr(0), 0, 1, ptr(0));
            } catch (eM2) {}
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

// Hook ChatFrame.CFKFOJFEOBA (C1:0D blue system notice) de ghi nhan TUC THI tien do giet quai NV Cap 3
// (VD: 'Dark Elf ( 1/1', 'Balram (Trainee Soldier) ( 20/20') vi MegaMU khong luon day C1:A4 ngay luc quai chet
var questNoticeKills = {};
var questNoticeReq = {};
var questNoticeCharName = "";
var lastQuestNoticeText = "";

function recordQuestNoticeText(rawText) {
    try {
        if (!rawText) return false;
        var clean = String(rawText).replace(/<[^>]+>/g, "").trim();
        if (clean.length < 5 || clean.length > 180) return false;
        var low = clean.toLowerCase();
        var mFrac = low.match(/(\d+)\s*(?:\/|of|de)\s*(\d+)/i) || low.match(/(\d+)\s*\/\s*(\d+)/);
        if (!mFrac) return false;
        var kCur = parseInt(mFrac[1], 10);
        var kMax = parseInt(mFrac[2], 10);
        if (isNaN(kCur) || kCur <= 0 || kCur > 200 || isNaN(kMax) || kMax < 1 || kMax > 200) return false;
        var mid = null;
        if (low.indexOf("dark elf") !== -1 || low.indexOf("darkelf") !== -1 || (low.indexOf("dark") !== -1 && low.indexOf("elf") !== -1)) {
            mid = "412";
        } else if (low.indexOf("balram") !== -1) {
            mid = "409";
        } else if (low.indexOf("death spirit") !== -1 || low.indexOf("deathspirit") !== -1 || low.indexOf("spirit") !== -1) {
            mid = "410";
        } else if (low.indexOf("soram") !== -1) {
            mid = "411";
        }
        if (!mid) return false;
        if (kCur > (questNoticeKills[mid] || 0)) questNoticeKills[mid] = kCur;
        questNoticeReq[mid] = kMax;
        lastQuestNoticeText = clean;
        return true;
    } catch (eQN) {
        return false;
    }
}

var questNoticeHook = null;
try {
    var canOff = off('__CHAT_ADD_NOTICE__');
    if (!canOff.isNull()) {
        questNoticeHook = Interceptor.attach(baseAddr.add(canOff), {
            onEnter: function(args) {
                if (shuttingDown) return;
                try {
                    var strPtr = args[2];
                    if (strPtr && !strPtr.isNull()) {
                        var sLen = strPtr.add(0x10).readS32();
                        if (sLen > 4 && sLen < 200) {
                            var txt = strPtr.add(0x14).readUtf16String(sLen);
                            recordQuestNoticeText(txt);
                        }
                    }
                } catch (eQNH) {}
            }
        });
    }
} catch (eQNHook) {}

function getIl2CppClassNameSafe(objPtr) {
    if (!objPtr || objPtr.isNull()) return "";
    try {
        var klass = objPtr.readPointer();
        if (klass.isNull()) return "";
        var namePtr = klass.add(0x10).readPointer();
        if (namePtr.isNull()) return "";
        return namePtr.readUtf8String() || "";
    } catch (eCls) {
        return "";
    }
}

function getMossWindowPtr(gui) {
    try {
        var g = gui;
        if ((!g || g.isNull()) && nativeGetGameUI !== null) {
            g = nativeGetGameUI();
        }
        if (!g || g.isNull()) return ptr(0);
        var mossOff = off('__UI_MOSS_WINDOW__');
        return mossOff.isNull() ? g.add(ptr('0x1D0')).readPointer() : g.add(mossOff).readPointer();
    } catch (eMW) {
        return ptr(0);
    }
}

function getMossCategoryCount(mossWin) {
    if (!mossWin || mossWin.isNull()) return 0;
    try {
        var catList = mossWin.add(0x80).readPointer();
        if (catList.isNull()) return 0;
        var cnt = catList.add(0x18).readS32();
        return (cnt > 0 && cnt < 100) ? cnt : 0;
    } catch (eCC) {
        return 0;
    }
}

function isMossWindowServerReady(mossWin) {
    if (!mossWin || mossWin.isNull()) return false;
    try {
        var win = mossWin.add(0x20).readPointer();
        if (win.isNull() || win.add(0x48).readU8() !== 1) return false;
        return getMossCategoryCount(mossWin) > 0;
    } catch (eMR) {
        return false;
    }
}

function selectMossCategoryOnly(mossWin, cat) {
    if (!mossWin || mossWin.isNull()) return false;
    try {
        var catId = parseInt(cat || 0);
        var catList = mossWin.add(0x80).readPointer();
        var catCount = getMossCategoryCount(mossWin);
        if (catList.isNull() || catCount <= 0) return false;
        mossWin.add(0x78).writeS32(catId);
        if (nativeMossSelectCat !== null) {
            try {
                var items = catList.add(0x10).readPointer();
                if (!items.isNull()) {
                    var targetCatObj = ptr(0);
                    for (var ci = 0; ci < catCount; ci++) {
                        var candidate = items.add(0x20 + ci * 8).readPointer();
                        if (!candidate.isNull()) {
                            var cId = candidate.add(0x10).readS32();
                            if (cId === catId) {
                                targetCatObj = candidate;
                                break;
                            }
                        }
                    }
                    if (targetCatObj.isNull() && catId < catCount && catId >= 0) {
                        targetCatObj = items.add(0x20 + catId * 8).readPointer();
                    }
                    if (!targetCatObj.isNull()) {
                        nativeMossSelectCat(mossWin, targetCatObj, ptr(0));
                    }
                }
            } catch (eCat) {}
        }
        return true;
    } catch (eSel) {
        return false;
    }
}

function clearBlockingWindowsForNpcTalk(gui) {
    // Dọn cửa sổ local bị kẹt (Moss rỗng / Merchant / Inventory) trước khi gửi C1:30
    // để WindowHandler không chặn NpcManager.IBKEJOGKJDH / PCKGCMNFJND!
    try {
        var g = gui;
        if ((!g || g.isNull()) && nativeGetGameUI !== null) {
            g = nativeGetGameUI();
        }
        if (!g || g.isNull()) return;
        var clearedAny = false;

        // 1. Nếu bảng Moss đang bị mở giả (chưa có category từ server) -> đóng sạch
        var mossWin = getMossWindowPtr(g);
        if (!mossWin.isNull() && !isMossWindowServerReady(mossWin)) {
            try {
                var mWin = mossWin.add(0x20).readPointer();
                if (!mWin.isNull() && mWin.add(0x48).readU8() === 1) {
                    if (nativeWindowHide !== null) {
                        try { nativeWindowHide(mWin, ptr(0)); } catch (eMH) {}
                    } else if (nativeWindowSetState !== null) {
                        try { nativeWindowSetState(mWin, 0, ptr(0)); } catch (eMS) {}
                    }
                    mWin.add(0x48).writeU8(0);
                    clearedAny = true;
                }
            } catch (eMC) {}
        }

        // 2. Nếu cửa sổ Merchant đang mở -> đóng trước khi nói chuyện với Moss
        try {
            var merchOff = off('__UI_MERCHANT_WINDOW__');
            var merchWin = merchOff.isNull() ? g.add(ptr('0x1A0')).readPointer() : g.add(merchOff).readPointer();
            if (!merchWin.isNull()) {
                var mw = merchWin.add(0x20).readPointer();
                if (!mw.isNull() && mw.add(0x48).readU8() === 1) {
                    if (nativeWindowHide !== null) {
                        try { nativeWindowHide(mw, ptr(0)); } catch (eWH) {}
                    }
                    mw.add(0x48).writeU8(0);
                    clearedAny = true;
                }
            }
        } catch (eMerchC) {}

        // 3. Nếu InventoryWindow đang mở cản trở WindowHandler -> ẩn tạm để Server mở lại cùng Moss
        try {
            var invOff = off('__UI_INVENTORY_WINDOW__');
            var invWin = invOff.isNull() ? g.add(ptr('0x190')).readPointer() : g.add(invOff).readPointer();
            if (!invWin.isNull()) {
                var invMWin = invWin.add(0x28).readPointer();
                if (!invMWin.isNull() && invMWin.add(0x48).readU8() === 1) {
                    if (nativeWindowHide !== null) {
                        try { nativeWindowHide(invMWin, ptr(0)); } catch (eIH) {}
                    }
                    invMWin.add(0x48).writeU8(0);
                    clearedAny = true;
                }
            }
        } catch (eInvC) {}

        if (clearedAny && nativeCloseTalk !== null) {
            try { nativeCloseTalk(); } catch (eCT) {}
        }
    } catch (eClr) {}
}

function performMossInteractOnMainThread(gui, nPtr) {
    try {
        var forceReopen = pendingMossForceReopen;
        pendingMossForceReopen = false;
        var mossWin = getMossWindowPtr(gui);
        // Nếu Server đã mở bảng Moss thật sẵn rồi (và không ép mở lại phiên mới) thì chỉ chọn đúng Category, không spam C1:30
        if (!forceReopen && !mossWin.isNull() && isMossWindowServerReady(mossWin)) {
            if (pendingMossSelectAfterServerOpen !== null) {
                selectMossCategoryOnly(mossWin, pendingMossSelectAfterServerOpen.cat);
                ensureMossRollButtonActive(mossWin, true);
                pendingMossSelectAfterServerOpen = null;
            }
            return true;
        }
        if (forceReopen && !mossWin.isNull()) {
            try {
                var rWin = mossWin.add(0x20).readPointer();
                if (!rWin.isNull() && rWin.add(0x48).readU8() === 1) {
                    if (nativeWindowHide !== null) {
                        try { nativeWindowHide(rWin, ptr(0)); } catch (eRWH) {}
                    } else if (nativeWindowSetState !== null) {
                        try { nativeWindowSetState(rWin, 0, ptr(0)); } catch (eRWSS) {}
                    }
                    rWin.add(0x48).writeU8(0);
                }
                ensureMossRollButtonActive(mossWin, true);
            } catch (eForceM) {}
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCTForce) {}
            }
            try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGSForce) {}
        }
        clearBlockingWindowsForNpcTalk(gui);
        return invokeNpcTalk(nPtr, true);
    } catch (eMI) {
        return false;
    }
}

function pollMossSelectAfterServerOpenOnMainThread(gui) {
    if (pendingMossSelectAfterServerOpen === null) return;
    try {
        var now = Date.now();
        if (now > pendingMossSelectAfterServerOpen.untilMs) {
            pendingMossSelectAfterServerOpen = null;
            return;
        }
        var mossWin = getMossWindowPtr(gui);
        if (!mossWin.isNull() && isMossWindowServerReady(mossWin)) {
            var targetCat = pendingMossSelectAfterServerOpen.cat;
            pendingMossSelectAfterServerOpen = null;
            selectMossCategoryOnly(mossWin, targetCat);
            ensureMossRollButtonActive(mossWin, true);
        }
    } catch (ePollSel) {}
}

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
        // Chỉ thao tác chọn tab & mở khóa nút quay khi Server THỰC SỰ đã mở bảng và nạp danh sách Category!
        // TUYỆT ĐỐI KHÔNG cưỡng chế win+0x48 = 1 khi chưa có phiên NPC thật từ Server (sẽ khóa WindowHandler & chặn C1:30).
        if (!isMossWindowServerReady(mossWin)) {
            return false;
        }
        selectMossCategoryOnly(mossWin, cat);
        ensureMossRollButtonActive(mossWin, true);
        return true;
    } catch (eSetup) {
        return false;
    }
}

function performMossCloseNow() {
    pendingMossOpenCategory = null;
    pendingMossSelectAfterServerOpen = null;
    pendingMossForceReopen = false;
    pendingMossClose = false;
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var mossOff = off('__UI_MOSS_WINDOW__');
                var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
                if (!mossWin.isNull()) {
                    // 1. Phục hồi RollButton và tắt LoadingImage để tránh đơ giao diện
                    ensureMossRollButtonActive(mossWin, true);

                    // 2. Đóng MWindow tại offset 0x20 (KHÔNG gọi Window.Hide trực tiếp lên MMossMerchantWindow!)
                    var win = mossWin.add(0x20).readPointer();
                    if (!win.isNull()) {
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

                        if (nativeWindowHide !== null) {
                            try { nativeWindowHide(win, ptr(0)); } catch (eWH) {}
                        } else if (nativeWindowSetState !== null) {
                            try { nativeWindowSetState(win, 0, ptr(0)); } catch (eWSS) {}
                        }

                        win.add(0x48).writeU8(0);
                    }
                }
            }
        }
    } catch (eUIClose) {}

    // 4. Gửi packet C1:31 đóng phiên đàm thoại NPC và mở khóa thùng đồ
    if (nativeCloseTalk !== null) {
        try { nativeCloseTalk(); } catch (eCT) {}
    }
    try { sendGSPacket([0xC1, 0x04, 0x31, 0x00]); } catch (eGS) {}

    // 5. Mở khóa toàn diện thùng đồ & nhân vật (đang trên Unity MainThread)
    ensureDropAllowed(true);
    return true;
}

function performMossResetNow(cat) {
    pendingMossResetCategory = null;
    try {
        var mossWin = getMossWindowPtr(null);
        if (!mossWin.isNull()) {
            ensureMossRollButtonActive(mossWin, true);
            if (isMossWindowServerReady(mossWin)) {
                selectMossCategoryOnly(mossWin, cat);
                return true;
            }
        }
    } catch (eReset) {}
    return false;
}

function performMossRollNow(cat) {
    try {
        if (nativeGetGameUI === null) return false;
        var gui = nativeGetGameUI();
        if (gui.isNull()) return false;
        var mossOff = off('__UI_MOSS_WINDOW__');
        var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
        if (mossWin.isNull()) return false;

        // Chỉ gửi lệnh quay khi cửa sổ Moss đang thực sự mở (MWindow +0x48 == 1)
        var rWin = mossWin.add(0x20).readPointer();
        if (rWin.isNull() || rWin.add(0x48).readU8() !== 1) {
            return false;
        }

        // 1. Cập nhật Category ID (offset 0x78)
        mossWin.add(0x78).writeS32(cat);

        // 2. Kích hoạt chọn category nếu hàm khả dụng
        if (nativeMossSelectCat !== null) {
            try {
                var catList = mossWin.add(0x80).readPointer();
                if (!catList.isNull()) {
                    var count = catList.add(0x18).readS32();
                    var items = catList.add(0x10).readPointer();
                    if (!items.isNull() && count > 0) {
                        var targetCatObj = ptr(0);
                        for (var ci = 0; ci < count; ci++) {
                            var candidate = items.add(0x20 + ci * 8).readPointer();
                            if (!candidate.isNull()) {
                                var cId = candidate.add(0x10).readS32();
                                if (cId === cat) {
                                    targetCatObj = candidate;
                                    break;
                                }
                            }
                        }
                        if (targetCatObj.isNull() && cat < count && cat >= 0) {
                            targetCatObj = items.add(0x20 + cat * 8).readPointer();
                        }
                        if (!targetCatObj.isNull()) {
                            nativeMossSelectCat(mossWin, targetCatObj, ptr(0));
                        }
                    }
                }
            } catch (eCat) {}
        }

        // Đảm bảo RollButton mở khóa & timer quay reset trước khi gửi lệnh quay
        ensureMossRollButtonActive(mossWin, true);

        // 3. GỬI LỆNH QUAY (chạy trực tiếp trên Unity MainThread):
        var sent = false;
        // Ưu tiên 1: Gửi qua Native Packet RPC thật (MossMerchantWindow.SendRoll -> C1:70:10 -> GSConnection.Send)
        if (nativeMossSendRoll !== null) {
            try {
                nativeMossSendRoll(cat, ptr(0));
                sent = true;
            } catch (eSend) {}
        }

        // Ưu tiên 2: Fallback gọi OnClick của RollButton (nếu có)
        if (!sent && nativeMossRollClick !== null) {
            try {
                nativeMossRollClick(mossWin, ptr(0));
                sent = true;
            } catch (eRC) {}
        }

        // 4. Bật hiệu ứng LoadingImage quay mượt mà (dùng mốc thời gian MainThread, KHÔNG dùng setTimeout đa luồng!)
        try {
            var loadingImg = mossWin.add(0x60).readPointer();
            if (!loadingImg.isNull() && isGameObjectValid(loadingImg) && nativeGameObjectSetActive !== null) {
                nativeGameObjectSetActive(loadingImg, 1, ptr(0));
                _mossLoadingClearAtMs = Date.now() + 1200;
            }
        } catch (eLI) {}

        return sent;
    } catch (eNow) {
        return false;
    }
}

var _mossLoadingClearAtMs = 0;

function performMerchantCloseNow() {
    pendingMerchantClose = false;
    if (nativeCloseTalk !== null) {
        try { nativeCloseTalk(); } catch (eCT) {}
    }
    try {
        var encClose = 0x31 ^ 0xCB; // 0xFA
        if (!sendGSPacket([0xC1, 0x04, encClose, 0x00], true)) {
            sendGSPacket([0xC1, 0x04, 0x31, 0x00]);
        }
    } catch (eGS) {}
    try {
        if (nativeGetGameUI !== null) {
            var gui = nativeGetGameUI();
            if (!gui.isNull()) {
                var merchOff = off('__UI_MERCHANT_WINDOW__');
                var mWinPtr = merchOff.isNull() ? gui.add(ptr('0x1A0')).readPointer() : gui.add(merchOff).readPointer();
                if (!mWinPtr.isNull()) {
                    var mwObj = mWinPtr.add(0x20).readPointer();
                    if (!mwObj.isNull()) {
                        if (nativeWindowHide !== null) {
                            try { nativeWindowHide(mwObj, ptr(0)); } catch (eWH) {}
                        } else if (nativeWindowSetState !== null) {
                            try { nativeWindowSetState(mwObj, 0, ptr(0)); } catch (eWSS) {}
                        }
                        mwObj.add(0x48).writeU8(0);
                    }
                }
            }
        }
    } catch (eMerchClose) {}
    ensureDropAllowed();
    return true;
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
        if (count <= 0 || count > 600) return null;

        var best = null;
        var bestScore = -1;
        var bestDist = 999999;

        for (var i = 0; i < count; i++) {
            var entryAddr = entries.add(0x20 + i * 24);
            // Bỏ qua slot Dictionary đã bị xóa (hashCode < 0)
            if (entryAddr.readS32() < 0) continue;
            var val = entryAddr.add(16).readPointer();
            if (val.isNull()) continue;

            // Bắt buộc là ViewportBody (tránh nhầm ViewportItem / ViewportEffect)
            var vKlassName = getIl2CppClassNameSafe(val);
            if (vKlassName.indexOf("ViewportBody") === -1) continue;

            var body = val.add(ptr('0x18')).readPointer();
            if (body.isNull()) continue;

            // Bỏ qua chính bản thân nhân vật người chơi và thực thể đang bị hủy
            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;
            try { if (body.add(0xC0).readU8() !== 0) continue; } catch (eDst) {}

            // TUYỆT ĐỐI LOẠI TRỪ NGƯỜI CHƠI (CharacterBody / MCharacterBody / LocalCharacterBody)!
            var bKlassName = getIl2CppClassNameSafe(body);
            if (bKlassName.indexOf("CharacterBody") !== -1) continue;
            if (bKlassName.length > 0 && bKlassName.indexOf("NpcBody") === -1 && bKlassName.indexOf("MonsterBody") === -1) continue;

            var bIdx = -1;
            try { bIdx = body.add(0x20).readS32(); } catch (eIdx) {}
            if (bIdx < 0) continue;

            // Đọc cả Body._Class (+0x34) VÀ Body.Skin (+0x60 — ID thật của NPC/Monster, Moss = 492)
            var bClass = -1;
            var bSkin = -1;
            try { bClass = body.add(0x34).readS32(); } catch (eT) {}
            try { bSkin = body.add(0x60).readS32(); } catch (eS) {}

            var name = "";
            try {
                var namePtr = body.add(off('__PLAYER_NAME__')).readPointer();
                if (!namePtr.isNull()) {
                    var len = namePtr.add(0x10).readS32();
                    if (len > 0 && len < 64) {
                        name = namePtr.add(0x14).readUtf16String(len) || "";
                    }
                }
            } catch (eN) {}

            // Đọc thêm MonsterBody.MonsterInfo (+0x138 -> +0x18 Name) khi Body.Name trống
            var infoName = "";
            try {
                var mInfo = body.add(0x138).readPointer();
                if (!mInfo.isNull()) {
                    var inPtr = mInfo.add(0x18).readPointer();
                    if (!inPtr.isNull()) {
                        var inLen = inPtr.add(0x10).readS32();
                        if (inLen > 0 && inLen < 64) {
                            infoName = inPtr.add(0x14).readUtf16String(inLen) || "";
                        }
                    }
                }
            } catch (eMI) {}

            var finalName = name || infoName || "";
            var lowName = finalName.toLowerCase();

            // Loại trừ rõ ràng các NPC khác ở Elbeland
            if (lowName.indexOf('james') !== -1 || lowName.indexOf('silvia') !== -1 ||
                lowName.indexOf('rhea') !== -1 || lowName.indexOf('leah') !== -1 ||
                lowName.indexOf('lugard') !== -1 || lowName.indexOf('sartigan') !== -1 ||
                lowName.indexOf('guard') !== -1) {
                continue;
            }

            var tx = -1, ty = -1;
            try {
                var cPtr = body.add(off('__PLAYER_COORD__')).readPointer();
                if (!cPtr.isNull()) {
                    tx = cPtr.add(0x10).readS32();
                    ty = cPtr.add(0x14).readS32();
                }
            } catch (eC) {}

            var score = 0;
            if (bSkin === 492 || bClass === 492) {
                score = 300;
            } else if (lowName.indexOf('moss') !== -1 || lowName.indexOf('gambler') !== -1) {
                score = 200;
            } else if (bKlassName.indexOf("NpcBody") !== -1 && tx >= 20 && tx <= 25 && ty >= 222 && ty <= 227) {
                score = 100;
            }

            if (score > 0) {
                var dist = (tx >= 0 && ty >= 0) ? (Math.abs(tx - 22) + Math.abs(ty - 225)) : 999;
                if (score > bestScore || (score === bestScore && dist < bestDist)) {
                    bestScore = score;
                    bestDist = dist;
                    best = {
                        ptr: body,
                        index: bIdx,
                        skin: bSkin,
                        classId: bClass,
                        klass: bKlassName,
                        name: finalName || "Moss The Gambler",
                        x: tx,
                        y: ty
                    };
                }
            }
        }
        return best;
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

var cachedCharonPtr = null;

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
            var body = val;
            try {
                var pBody = val.add(ptr('0x18')).readPointer();
                if (!pBody.isNull()) body = pBody;
            } catch (eB) {}
            if (body.isNull()) continue;

            if (!localPlayer.isNull()) {
                if (body.equals(localPlayer) || val.equals(localPlayer)) continue;
            }

            var npcType = -1;
            try { npcType = body.add(0x34).readS32(); } catch (eT) {}
            if (npcType === -1) {
                try { npcType = val.add(0x34).readS32(); } catch (eT2) {}
            }

            var name = "";
            try {
                var namePtr = body.add(off('__PLAYER_NAME__')).readPointer();
                if (namePtr.isNull()) namePtr = val.add(off('__PLAYER_NAME__')).readPointer();
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
                if (cPtr.isNull()) cPtr = val.add(off('__PLAYER_COORD__')).readPointer();
                if (!cPtr.isNull()) {
                    tx = cPtr.add(0x10).readS32();
                    ty = cPtr.add(0x14).readS32();
                }
            } catch (eC) {}

            var lowName = (name || "").toLowerCase();
            // Loại trừ NPC Lugard (Mirror)
            var isLugard = (npcType === 45 || npcType === 0x2d || npcType === -76 || npcType === 723 || npcType === 540 || lowName.indexOf("lugard") !== -1 || lowName.indexOf("doppel") !== -1);
            if (isLugard) continue;

            // Nhận diện NPC Charon:
            // 1. Theo npcType:
            //    - Client native OnClick (<RVA>): cmp eax, 0x9d (157) & cmp eax, -0x7e (-126)
            //    - Chuẩn MuOnline: 236, 237, 720, 251, -78
            // 2. Theo tên (tiếng Anh, Bồ Đào Nha MEGAMU Caronte, tiếng Việt):
            //    - charon, caron, caronte, devil, diabo, mestre
            // 3. Theo tọa độ Event Square: (220, 2), (220, 22), (225, 52), Noria (171, 105)
            // 4. Fallback: Bất kỳ NPC nào trong Event Square không phải Lugard
            var isCharon = false;
            if (npcType === 236 || npcType === 237 || npcType === 720 || npcType === 251 || npcType === -126 || npcType === -0x7e || npcType === 157 || npcType === 0x9d || npcType === -78) {
                isCharon = true;
            } else if (lowName.indexOf("charon") !== -1 || lowName.indexOf("caron") !== -1 || lowName.indexOf("caronte") !== -1 || lowName.indexOf("devil") !== -1 || lowName.indexOf("diabo") !== -1 || lowName.indexOf("mestre") !== -1) {
                isCharon = true;
            } else if ((tx >= 210 && tx <= 228 && ((ty >= 0 && ty <= 15) || (ty >= 18 && ty <= 28) || (ty >= 48 && ty <= 56))) || (tx >= 168 && tx <= 174 && ty >= 102 && ty <= 108)) {
                isCharon = true;
            } else if (tx > 0 && Math.abs(tx - 220) <= 6 && (Math.abs(ty - 2) <= 6 || Math.abs(ty - 22) <= 6)) {
                isCharon = true;
            }

            if (isCharon) {
                cachedCharonPtr = body;
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
    if (cachedCharonPtr && !cachedCharonPtr.isNull()) {
        try {
            var cPtr = cachedCharonPtr.add(off('__PLAYER_COORD__')).readPointer();
            if (!cPtr.isNull()) return cachedCharonPtr;
        } catch (eCache) {
            cachedCharonPtr = null;
        }
    }
    var charon = findCharonNpc();
    if (charon && !charon.isNull()) {
        cachedCharonPtr = charon;
        return charon;
    }
    return null;
}

function checkDevilItem(itemPtr, idx) {
    var trueIdx = (idx !== undefined && idx !== null && idx > 0) ? idx : readItemIndex(itemPtr);
    var itName = getItemName(itemPtr) || "";
    var lowName = itName.toLowerCase();
    var itLevel = 0;
    try { itLevel = itemPtr.add(0x10).readS32(); } catch (eL) {}
    if (itLevel <= 0) {
        try {
            var altLvl = itemPtr.add(0x14).readS32();
            if (altLvl > 0 && altLvl <= 15) itLevel = altLvl;
        } catch (eL2) {}
    }
    if (itLevel <= 0 && lowName.length > 0) {
        var m = lowName.match(/\+\s*(\d+)/);
        if (m) {
            try { itLevel = parseInt(m[1], 10); } catch (eM) {}
        }
    }

    // 1. Nhận diện Master Ticket (Vé Master):
    // - ID: 6702 (0x1A2E), 7214 (0x1C2E), 6675, 6705..6709
    // - Hoặc vé 7187 có level >= 7 (Master DS / DS 7)
    // - Hoặc tên có từ 'master' hoặc '+7' kết hợp cùng 'devil'/'invit'/'diabo'/'convite'/'ticket'
    var isMasterId = (
        trueIdx === 6702 || trueIdx === 7214 || trueIdx === 6675 ||
        (trueIdx >= 6705 && trueIdx <= 6709)
    );
    var hasMasterWord = (
        lowName.indexOf("master") !== -1 ||
        lowName.indexOf("+7") !== -1 ||
        lowName.indexOf("+ 7") !== -1
    );
    var hasDevilWord = (
        lowName.indexOf("devil") !== -1 ||
        lowName.indexOf("diabo") !== -1 ||
        lowName.indexOf("square") !== -1 ||
        trueIdx === 7187 ||
        isMasterId
    );
    var hasTicketWord = (
        lowName.indexOf("invit") !== -1 ||
        lowName.indexOf("convite") !== -1 ||
        lowName.indexOf("ticket") !== -1 ||
        lowName.indexOf("vé") !== -1 ||
        trueIdx === 7187 ||
        isMasterId
    );
    var isMasterName = (hasMasterWord && (hasDevilWord || hasTicketWord));
    if (!isMasterName && lowName.length > 0) {
        if (
            lowName.indexOf("master devil") !== -1 ||
            lowName.indexOf("devil master") !== -1 ||
            lowName.indexOf("diabo master") !== -1 ||
            lowName.indexOf("convite master") !== -1 ||
            lowName.indexOf("convite do diabo +7") !== -1 ||
            lowName.indexOf("devil's invitation +7") !== -1 ||
            lowName.indexOf("devil invitation +7") !== -1 ||
            lowName.indexOf("devil square ticket +7") !== -1 ||
            lowName.indexOf("devil square +7") !== -1 ||
            lowName.indexOf("vé devil master") !== -1 ||
            lowName.indexOf("vé master devil") !== -1
        ) {
            isMasterName = true;
        }
    }
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
        lowName.indexOf("vé devil square") !== -1 ||
        lowName.indexOf("vé devil") !== -1 ||
        (lowName.indexOf("devil") !== -1 && lowName.indexOf("invit") !== -1) ||
        (lowName.indexOf("diabo") !== -1 && lowName.indexOf("convite") !== -1)
    );

    if (isMaster) {
        return {
            isTicket: true,
            isMaster: true,
            level: (itLevel > 0) ? itLevel : 7,
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
            if (entryAddr.readS32() < 0) continue;
            var val = entryAddr.add(16).readPointer();
            if (val.isNull()) continue;
            if (getIl2CppClassNameSafe(val).indexOf("ViewportBody") === -1) continue;
            var body = val.add(ptr('0x18')).readPointer();
            if (body.isNull()) continue;

            if (!localPlayer.isNull() && body.equals(localPlayer)) continue;
            try { if (body.add(0xC0).readU8() !== 0) continue; } catch (eMDst) {}
            var mKlass = getIl2CppClassNameSafe(body);
            if (mKlass.indexOf("CharacterBody") !== -1) continue;
            if (mKlass.length > 0 && mKlass.indexOf("NpcBody") === -1 && mKlass.indexOf("MonsterBody") === -1) continue;

            var bIdx = body.add(0x20).readS32();
            if (bIdx < 0) continue;

            var bClass = -1;
            try { bClass = body.add(off('__PLAYER_CLASS__')).readS32(); } catch (eCls) {}

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
            if (lowerName.indexOf('moss') !== -1 || bClass === 492) continue;

            // Tuyệt đối loại bỏ Priest James (class 725, pos 32,239 - Ruud Store) — KHÔNG loại bỏ Rhea (class 416, pos 29,236)!
            if (bClass === 725 || lowerName.indexOf('james') !== -1 || lowerName.indexOf('ruud') !== -1 || lowerName.indexOf('store') !== -1) continue;
            if (tx >= 31 && tx <= 34 && ty >= 238 && ty <= 241) continue;

            var isMerchant = false;
            var isRhea = (bClass === 416 || lowerName.indexOf('rhea') !== -1 ||
                          (tx >= 28 && tx <= 30 && ty >= 235 && ty <= 237));
            // 1. Nhận diện NPC Rhea (ELB1 29,236 - class 416, ngay cạnh Moss & tọa độ 30,235)
            if (isRhea) {
                isMerchant = true;
            }
            // 2. Nhận diện theo tên NPC thương nhân khác (Silvia, Leah, Merchant, Potion...)
            else if (lowerName.indexOf('silvia') !== -1 || lowerName.indexOf('leah') !== -1 || lowerName.indexOf('lia') !== -1 ||
                lowerName.indexOf('merchant') !== -1 || lowerName.indexOf('potion') !== -1 ||
                lowerName.indexOf('tạp hóa') !== -1 || lowerName.indexOf('thuốc') !== -1 ||
                lowerName.indexOf('thương nhân') !== -1 || lowerName.indexOf('poção') !== -1 || lowerName.indexOf('pocion') !== -1) {
                isMerchant = true;
            }
            // 3. Nhận diện theo tọa độ thương nhân Silvia (42..47, 227..232) hoặc Leah (35..40, 234..239)
            else if ((tx >= 42 && tx <= 47 && ty >= 227 && ty <= 232) ||
                     (tx >= 35 && tx <= 40 && ty >= 234 && ty <= 239)) {
                isMerchant = true;
            }
            // 4. Nếu nhân vật đã đứng gần khu vực chợ (px >= 27 && px <= 48 && py >= 225 && py <= 242) và đứng cạnh NPC (<= 3 ô)
            else if (px >= 27 && px <= 48 && py >= 225 && py <= 242 && Math.abs(tx - px) <= 3 && Math.abs(ty - py) <= 3) {
                isMerchant = true;
            }

            if (isMerchant) {
                // Ưu tiên NPC thương nhân gần vị trí nhân vật hiện tại nhất (hoặc Rhea 29,236 nếu chưa đọc được tọa độ)
                var refX = (px > 0 && py > 0) ? px : 30;
                var refY = (px > 0 && py > 0) ? py : 235;
                var dist = Math.abs(tx - refX) + Math.abs(ty - refY);
                if (isRhea && dist <= 12) {
                    dist -= 2; // Ưu tiên nhẹ Rhea ngay ELB1 (29, 236) khi đang đứng gần
                }
                if (dist < bestDist) {
                    bestDist = dist;
                    bestNpc = {
                        ptr: body,
                        index: bIdx,
                        classId: bClass,
                        name: name || (isRhea ? "Rhea" : "Merchant Silvia"),
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
                                performMossInteractOnMainThread(gui, nPtr);
                            } catch (eMossNT) {}
                        }
                        if (pendingMossSelectAfterServerOpen !== null) {
                            try {
                                pollMossSelectAfterServerOpenOnMainThread(gui);
                            } catch (eMossSelUI) {}
                        }

                        if (pendingMerchantInteractPtr !== null) {
                            try {
                                var mPtr = pendingMerchantInteractPtr;
                                pendingMerchantInteractPtr = null;
                                invokeNpcTalk(mPtr, true);
                            } catch (eNTM) {}
                        }

                        if (pendingSellSlot !== null) {
                            try {
                                var pSell = pendingSellSlot;
                                pendingSellSlot = null;
                                pSell.ok = sendSellPacket(pSell.slot);
                                pSell.done = true;
                            } catch (eSellMT) {}
                        }

                        if (pendingGremoryClaim !== null) {
                            try {
                                var pGC = pendingGremoryClaim;
                                pendingGremoryClaim = null;
                                if (nativeGremoryClaim !== null && pGC.itemInfo && !pGC.itemInfo.isNull()) {
                                    nativeGremoryClaim(pGC.itemInfo, ptr(0));
                                    pGC.ok = true;
                                }
                                pGC.done = true;
                            } catch (eGCMT) {
                                if (pGC) { pGC.ok = false; pGC.done = true; }
                            }
                        }

                        if (pendingQuestNpcTalkPtr !== null) {
                            try {
                                var qnPtr = pendingQuestNpcTalkPtr;
                                pendingQuestNpcTalkPtr = null;
                                invokeNpcTalk(qnPtr, true);
                            } catch (eQNT) {}
                        }

                        if (pendingQuestNextAction !== null) {
                            try {
                                var qna = pendingQuestNextAction;
                                pendingQuestNextAction = null;
                                performQuestNextClickOnMainThread(gui, qna.index);
                            } catch (eQNA) {}
                        }
                        if (pendingQuestPickups.length > 0) {
                            try { flushQuestPickupsOnMainThread(); } catch (eQPK1) {}
                        }

                        if (pendingQuestStateAction !== null) {
                            try {
                                var qsa = pendingQuestStateAction;
                                pendingQuestStateAction = null;
                                if (nativeQuestSendState !== null) {
                                    nativeQuestSendState(qsa.index, qsa.flag ? 1 : 0, ptr(0));
                                } else if (nativeQuestSendStateAlt !== null) {
                                    nativeQuestSendStateAlt(qsa.index, qsa.flag ? 1 : 0, ptr(0));
                                }
                            } catch (eQSA) {
                                lastQuestClickDebug = { done: true, ok: false, method: "SendState", error: eQSA.toString() };
                            }
                        }

                        if (pendingQuestDungeonAction !== null) {
                            try {
                                var qda = pendingQuestDungeonAction;
                                pendingQuestDungeonAction = null;
                                if (qda === "barracks" && nativeNpcEnterBarracks !== null) {
                                    nativeNpcEnterBarracks();
                                } else if (qda === "refuge" && nativeNpcEnterRefuge !== null) {
                                    nativeNpcEnterRefuge();
                                }
                            } catch (eQDA) {}
                        }
                        flushGateActionsOnMainThread();

                        if (pendingQuestWindowClose) {
                            try {
                                pendingQuestWindowClose = false;
                                if (gui && !gui.isNull()) {
                                    var qwOff = off('__UI_QUEST_NPC_WINDOW__');
                                    if (!qwOff.isNull()) {
                                        var qWin = gui.add(qwOff).readPointer();
                                        if (!qWin.isNull() && nativeWindowHide !== null) {
                                            try { nativeWindowHide(qWin, ptr(0)); } catch (eQWH) {}
                                        }
                                    }
                                }
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (eQCT) {}
                                }
                            } catch (eQWC) {}
                        }

                        if (pendingPkWindowClose) {
                            try {
                                pendingPkWindowClose = false;
                                if (gui && !gui.isNull()) {
                                    var pkWin = gui.add(0x2A8).readPointer();
                                    if (pkWin && !pkWin.isNull() && nativeWindowHide !== null) {
                                        try { nativeWindowHide(pkWin, ptr(0)); } catch (ePKWH) {}
                                    }
                                }
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (ePKCT) {}
                                }
                            } catch (ePKWC) {}
                        }

                        if (pendingWarehouseWindowClose) {
                            try {
                                pendingWarehouseWindowClose = false;
                                if (gui && !gui.isNull() && nativeWindowHide !== null) {
                                    var whOffC = off('__UI_WAREHOUSE_WINDOW__');
                                    var whWinC = whOffC.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOffC).readPointer();
                                    if (whWinC && !whWinC.isNull()) {
                                        try {
                                            var mwC = whWinC.add(0x48).readPointer();
                                            if (mwC && !mwC.isNull()) nativeWindowHide(mwC, ptr(0));
                                        } catch (eWH1) {}
                                        try {
                                            var ewC = whWinC.add(0x50).readPointer();
                                            if (ewC && !ewC.isNull()) nativeWindowHide(ewC, ptr(0));
                                        } catch (eWH2) {}
                                    }
                                }
                                if (nativeCloseTalk !== null) {
                                    try { nativeCloseTalk(); } catch (eWHCT) {}
                                }
                            } catch (eWHWC) {}
                        }

                        if (pendingMossOpenCategory !== null) {
                            try {
                                var cat = pendingMossOpenCategory;
                                pendingMossOpenCategory = null;
                                var mossWin = gui.add(off('__UI_MOSS_WINDOW__')).readPointer();
                                setupMossWindow(mossWin, cat);
                            } catch (eMossUI) {}
                        }

                        if (pendingMossResetCategory !== null) {
                            try {
                                var rCat = pendingMossResetCategory;
                                pendingMossResetCategory = null;
                                performMossResetNow(rCat);
                            } catch (eMossReset) {}
                        }

                        if (pendingMossRollCategory !== null) {
                            try {
                                var rollCat = pendingMossRollCategory;
                                pendingMossRollCategory = null;
                                performMossRollNow(rollCat);
                            } catch (eMossRoll) {}
                        }

                        if (pendingMossClose) {
                            try {
                                pendingMossClose = false;
                                performMossCloseNow();
                            } catch (eMossClose) {}
                        }

                        if (pendingMerchantClose) {
                            try {
                                pendingMerchantClose = false;
                                performMerchantCloseNow();
                            } catch (eMerchCloseUI) {}
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
var pendingPartyInviteKey = -1;
var lastPartyInviteResult = { done: false, ok: false, err: null, key: -1 };

var autoConfirmPartyEnabled = true;
var autoGateConfirmEnabled = false;
var autoGateConfirmCount = 0;
var lastAutoGateConfirmMs = 0;
var lastAutoGateConfirmInfo = { count: 0, title: "", message: "", timeMs: 0 };

function isGateTeleportDialog(title, msg) {
    var lowT = String(title || "").toLowerCase().trim();
    var lowM = String(msg || "").toLowerCase().trim();
    if (lowM.indexOf("do you want to teleport") !== -1) {
        if (lowM.indexOf("loren market") !== -1 ||
            lowM.indexOf("blood castle") !== -1 ||
            lowM.indexOf("devil square") !== -1 ||
            lowM.indexOf("illusion temple") !== -1 ||
            lowM.indexOf("imperial guardian") !== -1 ||
            lowM.indexOf("complete the quest") !== -1) {
            return false;
        }
        return true;
    }
    if (lowT === "teleport" && lowM.indexOf("teleport") !== -1 && lowM.indexOf("boss respawn") === -1 && lowM.indexOf("wing") === -1) {
        return true;
    }
    return false;
}
var partyConfirmScanCounter = 0;
var confirmedDialogHistory = {};

function isLocalPlayerInParty() {
    try {
        var p = getPlayerPtr();
        if (!p || p.isNull()) return false;
        var party = p.add(ptr('0x1C0')).readPointer();
        if (!party || party.isNull()) return false;
        return party.add(ptr('0x20')).readU8() === 1;
    } catch (e) {
        return false;
    }
}

function checkAndAutoConfirmPartyDialogs() {
    if (!autoConfirmPartyEnabled || shuttingDown) return;

    // Nếu nhân vật đã ở trong Party, hoàn toàn bỏ qua việc quét và xác nhận
    try {
        if (isLocalPlayerInParty()) return;
    } catch (eInParty) {}

    try {
        var helper = null;
        if (nativeGetHelperUI !== null) {
            try { helper = nativeGetHelperUI(); } catch (eG1) {}
        }
        if (!helper || helper.isNull()) {
            try {
                var gtiOff = off('__GAME_TYPE_INFO__');
                if (!gtiOff.isNull()) {
                    var gti = baseAddr.add(gtiOff).readPointer();
                    if (!gti.isNull()) {
                        var sf = gti.add(ptr('0xB8')).readPointer();
                        if (!sf.isNull()) {
                            var gi = sf.add(ptr('0x8')).readPointer();
                            if (!gi.isNull()) {
                                helper = gi.add(ptr('0x1F8')).readPointer();
                            }
                        }
                    }
                }
            } catch (eG2) {}
        }
        if (!helper || helper.isNull()) return;

        var dialogsDict = helper.add(ptr('0x80')).readPointer();
        if (!dialogsDict || dialogsDict.isNull()) return;

        var entries = dialogsDict.add(ptr('0x18')).readPointer();
        if (!entries || entries.isNull()) return;

        var count = 0;
        try { count = dialogsDict.add(ptr('0x20')).readS32(); } catch (eC) {}
        if (count <= 0) return;

        var arrLen = 0;
        try { arrLen = entries.add(ptr('0x18')).readS32(); } catch (eAL) {}
        var scanLimit = (arrLen > 0) ? Math.min(arrLen, 30) : Math.min(count, 30);

        var now = Date.now();

        // Dọn dẹp cache lịch sử xác nhận nếu quá nhiều
        var histKeys = Object.keys(confirmedDialogHistory);
        if (histKeys.length > 50) {
            for (var k = 0; k < histKeys.length; k++) {
                if (now - confirmedDialogHistory[histKeys[k]] > 30000) {
                    delete confirmedDialogHistory[histKeys[k]];
                }
            }
        }

        for (var i = 0; i < scanLimit; i++) {
            var entryPtr = entries.add(ptr('0x20')).add(i * 24);
            var valPtr = entryPtr.add(ptr('0x10')).readPointer();
            if (valPtr.isNull()) continue;

            // 1. Kiểm tra Window (offset 0x80) xem có đang mở (IsOpen: offset 0x48) không.
            // Nếu Window đã đóng hoặc không hiển thị, tuyệt đối không quét và không spam!
            try {
                var winPtr = valPtr.add(ptr('0x80')).readPointer();
                if (winPtr.isNull()) continue;
                var isOpen = winPtr.add(ptr('0x48')).readU8();
                if (isOpen === 0) continue;
            } catch (eWin) {
                continue;
            }

            // 2. Debounce chống spam lặp lại trên cùng 1 Dialog pointer (30 giây)
            var valKey = valPtr.toString();
            if (confirmedDialogHistory[valKey] && (now - confirmedDialogHistory[valKey] < 30000)) {
                continue;
            }

            var tStr = "";
            var mStr = "";

            try {
                var tComp = valPtr.add(ptr('0x30')).readPointer();
                if (!tComp.isNull()) {
                    var tTextPtr = tComp.add(ptr('0xE8')).readPointer();
                    if (!tTextPtr.isNull()) {
                        var tLen = tTextPtr.add(ptr('0x10')).readS32();
                        if (tLen > 0 && tLen < 128) {
                            tStr = tTextPtr.add(ptr('0x14')).readUtf16String(tLen);
                        }
                    }
                }
            } catch (eT) {}

            try {
                var mComp = valPtr.add(ptr('0x38')).readPointer();
                if (!mComp.isNull()) {
                    var mTextPtr = mComp.add(ptr('0xE8')).readPointer();
                    if (!mTextPtr.isNull()) {
                        var mLen = mTextPtr.add(ptr('0x10')).readS32();
                        if (mLen > 0 && mLen < 256) {
                            mStr = mTextPtr.add(ptr('0x14')).readUtf16String(mLen);
                        }
                    }
                }
            } catch (eM) {}

            var checkStr = (tStr + " " + mStr).toLowerCase();
            if (checkStr.indexOf("party") !== -1 || 
                checkStr.indexOf("tổ đội") !== -1 || 
                checkStr.indexOf("to doi") !== -1 || 
                checkStr.indexOf("nhóm") !== -1 || 
                checkStr.indexOf("pt") !== -1) {
                
                // Đánh dấu ngay đã xử lý dialog này để không bị quét lặp ở các frame sau
                confirmedDialogHistory[valKey] = now;

                var confirmedOk = false;

                // 1. ƯU TIÊN SỐ 1: Gọi trực tiếp MDialog.FHBFMDLNFOH (RVA <RVA>)
                // Hàm này tự động gọi ConfirmActionCallback(true) và đóng Dialog qua Window.Close()
                if (nativeMDialogConfirmYes !== null) {
                    try {
                        nativeMDialogConfirmYes(valPtr, ptr(0));
                        confirmedOk = true;
                    } catch (eMDCYCall) {}
                }

                // 2. Kích hoạt trực tiếp delegate ConfirmActionCallback tại offset 0x88 (Chuẩn IL2CPP Calling Convention)
                if (!confirmedOk) {
                    try {
                        var confirmCb = valPtr.add(ptr('0x88')).readPointer();
                        if (!confirmCb.isNull()) {
                            var invoker = confirmCb.add(0x18).readPointer();
                            var target = confirmCb.add(0x40).readPointer();
                            var mInfo = confirmCb.add(0x28).readPointer();
                            if (!invoker.isNull()) {
                                var actFn = new NativeFunction(invoker, 'void', ['pointer', 'bool', 'pointer']);
                                actFn(target, 1, mInfo);
                                confirmedOk = true;
                            }
                        }
                    } catch (eCb) {}
                }

                // 3. Fallback: Kích hoạt YesButton qua Button.Press (RVA <RVA>)
                var yesBtn = valPtr.add(ptr('0x48')).readPointer();
                if (!yesBtn.isNull()) {
                    if (nativeButtonPress !== null) {
                        try { nativeButtonPress(yesBtn, ptr(0)); } catch (eBP2) {}
                    }
                    var invokeFn = nativeUnityEvent_Invoke || nativeUnityEventInvoke;
                    if (invokeFn !== null) {
                        try {
                            var onClick = yesBtn.add(ptr('0x100')).readPointer();
                            if (!onClick.isNull()) invokeFn(onClick, ptr(0));
                        } catch (eEV2) {}
                    }
                }

                // 4. Đóng cửa sổ Dialog qua Window (offset 0x80) -> CloseButton (offset 0x40)
                try {
                    var winPtr = valPtr.add(ptr('0x80')).readPointer();
                    if (!winPtr.isNull()) {
                        var closeBtn = winPtr.add(ptr('0x40')).readPointer();
                        if (!closeBtn.isNull()) {
                            if (nativeButtonPress !== null) {
                                try { nativeButtonPress(closeBtn, ptr(0)); } catch (eCP) {}
                            }
                        }
                    }
                } catch (eWinClose) {}

                send({
                    type: "auto_party_confirmed",
                    source: "game_update_scanner",
                    title: tStr,
                    message: mStr
                });
                break; // Chỉ xác nhận 1 dialog trong 1 chu kỳ quét để tránh spam
            }
        }
    } catch (eScan) {}
}

try {
    var guOff = off('__GAME_UPDATE__');
    if (!guOff.isNull()) {
        gameUpdateHook = Interceptor.attach(baseAddr.add(guOff), {
            onEnter: function(args) {
                if (shuttingDown) return;

                try { tickNativeMirrorTurboMainThread(); } catch (eMTT) {}
                if (!isMirrorCriticalActive()) {
                    try { tickJunkDisposalMainThread(); } catch (eJDT) {}

                    partyConfirmScanCounter++;
                    if (partyConfirmScanCounter % 30 === 0) {
                        try { checkAndAutoConfirmPartyDialogs(); } catch (eAPCD) {}
                    }
                }

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

                if (pendingPartyInviteKey !== -1) {
                    var pKey = pendingPartyInviteKey;
                    pendingPartyInviteKey = -1;
                    try {
                        if (nativePartyInviteByKey !== null) {
                            nativePartyInviteByKey(pKey, ptr(0));
                            lastPartyInviteResult = { done: true, ok: true, err: null, key: pKey };
                        } else {
                            lastPartyInviteResult = { done: true, ok: false, err: "nativePartyInviteByKey_null", key: pKey };
                        }
                    } catch (ePI) {
                        lastPartyInviteResult = { done: true, ok: false, err: String(ePI), key: pKey };
                    }
                }

                if (pendingMoveTarget !== null) {
                    var mTarget = pendingMoveTarget;
                    pendingMoveTarget = null;
                    try { dispatchMoveTarget(mTarget); } catch (eMGU) {}
                }

                if (pendingMossInteractPtr !== null) {
                    try {
                        var mNpcGU = pendingMossInteractPtr;
                        pendingMossInteractPtr = null;
                        performMossInteractOnMainThread(null, mNpcGU);
                    } catch (eMNTGU) {}
                }
                if (pendingMossSelectAfterServerOpen !== null) {
                    try {
                        pollMossSelectAfterServerOpenOnMainThread(null);
                    } catch (eMossSelGU) {}
                }

                if (pendingQuestNpcTalkPtr !== null) {
                    try {
                        var qnPtrGU = pendingQuestNpcTalkPtr;
                        pendingQuestNpcTalkPtr = null;
                        invokeNpcTalk(qnPtrGU, true);
                    } catch (eQNTGU) {}
                }

                if (pendingPkWindowClose) {
                    try {
                        pendingPkWindowClose = false;
                        if (nativeGetGameUI !== null) {
                            var guiPK = nativeGetGameUI();
                            if (guiPK && !guiPK.isNull()) {
                                var pkWinGU = guiPK.add(0x2A8).readPointer();
                                if (pkWinGU && !pkWinGU.isNull() && nativeWindowHide !== null) {
                                    try { nativeWindowHide(pkWinGU, ptr(0)); } catch (ePKWH2) {}
                                }
                            }
                        }
                        if (nativeCloseTalk !== null) {
                            try { nativeCloseTalk(); } catch (ePKCT2) {}
                        }
                    } catch (ePKWC2) {}
                }

                if (pendingWarehouseWindowClose) {
                    try {
                        pendingWarehouseWindowClose = false;
                        if (nativeGetGameUI !== null && nativeWindowHide !== null) {
                            var guiWH = nativeGetGameUI();
                            if (guiWH && !guiWH.isNull()) {
                                var whOffGU = off('__UI_WAREHOUSE_WINDOW__');
                                var whWinGU = whOffGU.isNull() ? guiWH.add(ptr('0x290')).readPointer() : guiWH.add(whOffGU).readPointer();
                                if (whWinGU && !whWinGU.isNull()) {
                                    try {
                                        var mwGU = whWinGU.add(0x48).readPointer();
                                        if (mwGU && !mwGU.isNull()) nativeWindowHide(mwGU, ptr(0));
                                    } catch (eWHG1) {}
                                    try {
                                        var ewGU = whWinGU.add(0x50).readPointer();
                                        if (ewGU && !ewGU.isNull()) nativeWindowHide(ewGU, ptr(0));
                                    } catch (eWHG2) {}
                                }
                            }
                        }
                        if (nativeCloseTalk !== null) {
                            try { nativeCloseTalk(); } catch (eWHGCT) {}
                        }
                    } catch (eWHGWC) {}
                }

                if (pendingQuestNextAction !== null) {
                    try {
                        var qnaGU = pendingQuestNextAction;
                        pendingQuestNextAction = null;
                        performQuestNextClickOnMainThread(null, qnaGU.index);
                    } catch (eQNAGU) {}
                }
                if (pendingQuestPickups.length > 0) {
                    try { flushQuestPickupsOnMainThread(); } catch (eQPK2) {}
                }

                if (pendingQuestStateAction !== null) {
                    try {
                        var qsaGU = pendingQuestStateAction;
                        pendingQuestStateAction = null;
                        if (nativeQuestSendState !== null) {
                            nativeQuestSendState(qsaGU.index, qsaGU.flag ? 1 : 0, ptr(0));
                        }
                    } catch (eQSAGU) {
                        lastQuestClickDebug = { done: true, ok: false, method: "SendState(GU)", error: eQSAGU.toString() };
                    }
                }

                if (pendingQuestDungeonAction !== null) {
                    try {
                        var qdaGU = pendingQuestDungeonAction;
                        pendingQuestDungeonAction = null;
                        if (qdaGU === "barracks" && nativeNpcEnterBarracks !== null) nativeNpcEnterBarracks();
                        else if (qdaGU === "refuge" && nativeNpcEnterRefuge !== null) nativeNpcEnterRefuge();
                    } catch (eQDAGU) {}
                }
                flushGateActionsOnMainThread();

                if (pendingMerchantInteractPtr !== null) {
                    try {
                        var merchNpcGU = pendingMerchantInteractPtr;
                        pendingMerchantInteractPtr = null;
                        invokeNpcTalk(merchNpcGU, true);
                    } catch (eMerchNTGU) {}
                }

                if (pendingSellSlot !== null) {
                    try {
                        var pSellGU = pendingSellSlot;
                        pendingSellSlot = null;
                        pSellGU.ok = sendSellPacket(pSellGU.slot);
                        pSellGU.done = true;
                    } catch (eSellGU) {}
                }

                if (pendingGremoryClaim !== null) {
                    try {
                        var pGCGU = pendingGremoryClaim;
                        pendingGremoryClaim = null;
                        if (nativeGremoryClaim !== null && pGCGU.itemInfo && !pGCGU.itemInfo.isNull()) {
                            nativeGremoryClaim(pGCGU.itemInfo, ptr(0));
                            pGCGU.ok = true;
                        }
                        pGCGU.done = true;
                    } catch (eGCGU) {
                        if (pGCGU) { pGCGU.ok = false; pGCGU.done = true; }
                    }
                }

                if (pendingMossOpenCategory !== null) {
                    try {
                        var openCatGU = pendingMossOpenCategory;
                        pendingMossOpenCategory = null;
                        if (nativeGetGameUI !== null) {
                            var guiOpen = nativeGetGameUI();
                            if (guiOpen && !guiOpen.isNull()) {
                                var mossOffO = off('__UI_MOSS_WINDOW__');
                                var mossWinO = mossOffO.isNull() ? guiOpen.add(ptr('0x1D0')).readPointer() : guiOpen.add(mossOffO).readPointer();
                                if (mossWinO && !mossWinO.isNull()) {
                                    setupMossWindow(mossWinO, openCatGU);
                                }
                            }
                        }
                    } catch (eMOGU) {}
                }

                if (_mossLoadingClearAtMs > 0 && Date.now() >= _mossLoadingClearAtMs) {
                    _mossLoadingClearAtMs = 0;
                    try {
                        if (nativeGetGameUI !== null) {
                            var guiLC = nativeGetGameUI();
                            if (guiLC && !guiLC.isNull()) {
                                var mossOffLC = off('__UI_MOSS_WINDOW__');
                                var mossWinLC = mossOffLC.isNull() ? guiLC.add(ptr('0x1D0')).readPointer() : guiLC.add(mossOffLC).readPointer();
                                if (mossWinLC && !mossWinLC.isNull()) {
                                    ensureMossRollButtonActive(mossWinLC, false);
                                }
                            }
                        }
                    } catch (eMLC) {}
                }

                if (pendingMossClose) {
                    try {
                        pendingMossClose = false;
                        performMossCloseNow();
                    } catch (eMCGU) {}
                }

                if (pendingMossResetCategory !== null) {
                    try {
                        var rCatGU = pendingMossResetCategory;
                        pendingMossResetCategory = null;
                        performMossResetNow(rCatGU);
                    } catch (eMRGU) {}
                }

                if (pendingMossRollCategory !== null) {
                    try {
                        var rollCatGU = pendingMossRollCategory;
                        pendingMossRollCategory = null;
                        performMossRollNow(rollCatGU);
                    } catch (eRollGU) {}
                }

                if (pendingMerchantClose) {
                    try {
                        pendingMerchantClose = false;
                        performMerchantCloseNow();
                    } catch (eMCHGU) {}
                }

                if (pendingAutoLogin === null) return;
                try {
                    var pal = pendingAutoLogin;
                    if (!pal || pal.done) return;

                    pal.frames++;

                    // 1. Kiểm tra SceneHandler.Type (0: None/Loading, 1: Preview, 2: Login, 3: Lobby, 4: Playing)
                    var sceneType = -1;
                    if (nativeGetSceneHandler !== null) {
                        try {
                            var sh = nativeGetSceneHandler();
                            if (!sh.isNull()) {
                                sceneType = sh.add(0x20).readS32();
                            }
                        } catch (eSH) {}
                    }

                    // Nếu game đang ở giai đoạn Load Scene/Splash (0 hoặc 1): Đợi game nạp xong
                    if (sceneType < 2) {
                        autoLoginLastStatus = { done: false, submitted: false, stage: "game_loading_scene", scene: sceneType, frames: pal.frames, account: pal.account };
                        if (pal.frames % 60 === 0) {
                            send({ type: "autologin_status", ok: false, stage: "game_loading_scene", scene: sceneType, frames: pal.frames, account: pal.account });
                        }
                        if (pal.frames > 3600) { // 60s timeout
                            autoLoginLastStatus = { done: true, submitted: false, stage: "timeout_loading", account: pal.account };
                            send({ type: "autologin_status", ok: false, stage: "timeout_loading", account: pal.account });
                            pendingAutoLogin = null;
                        }
                        return;
                    }

                    // Scene 4 (Playing): ĐÃ VÀO THẾ GIỚI GAME!
                    if (sceneType === 4) {
                        pal.done = true;
                        pal.submitted = true;
                        autoLoginLastStatus = { done: true, submitted: true, stage: "in_game_world", scene: sceneType, account: pal.account, character: pal.character };
                        send({ type: "autologin_status", ok: true, stage: "in_game_world", scene: sceneType, account: pal.account, character: pal.character });
                        pendingAutoLogin = null;
                        return;
                    }

                    // Scene 3 (Character Lobby): ĐANG Ở MÀN HÌNH CHỌN NHÂN VẬT -> ĐỌC DANH SÁCH & VÀO THẲNG NHÂN VẬT
                    if (sceneType === 3) {
                        pal.inLobbyFrames = (pal.inLobbyFrames || 0) + 1;
                        var foundChars = [];
                        var uAcc = null;
                        if (nativeGetUserAccount !== null) {
                            try { uAcc = nativeGetUserAccount(); } catch (eGUA) {}
                        }

                        if (uAcc !== null && !uAcc.isNull()) {
                            try {
                                var info = uAcc.add(0x20).readPointer();
                                if (!info.isNull()) {
                                    var charsList = info.add(0x30).readPointer();
                                    if (!charsList.isNull()) {
                                        var count = charsList.add(0x18).readS32();
                                        if (count > 0) {
                                            var itemsArr = charsList.add(0x10).readPointer();
                                            if (!itemsArr.isNull()) {
                                                for (var cIdx = 0; cIdx < count; cIdx++) {
                                                    var cInfo = itemsArr.add(0x20 + cIdx * 8).readPointer();
                                                    if (!cInfo.isNull()) {
                                                        var sNum = cInfo.add(0x18).readS32();
                                                        var nPtr = cInfo.add(0x20).readPointer();
                                                        var cName = "";
                                                        if (!nPtr.isNull()) {
                                                            var nLen = nPtr.add(0x10).readS32();
                                                            if (nLen > 0) {
                                                                cName = nPtr.add(0x14).readUtf16String(nLen);
                                                            }
                                                        }
                                                        var cLvl = cInfo.add(0x28).readS32();
                                                        var cCls = cInfo.add(0x30).readS32();
                                                        if (cName) {
                                                            foundChars.push({ slot: sNum, name: cName, level: cLvl, classCode: cCls, namePtr: nPtr });
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            } catch (eReadChars) {}
                        }

                        // Nếu danh sách nhân vật chưa load xong từ GameServer (count == 0): đợi thêm
                        if (foundChars.length === 0) {
                            if (pal.inLobbyFrames % 30 === 0) {
                                send({ type: "autologin_status", ok: false, stage: "waiting_character_list", scene: 3, account: pal.account });
                            }
                            return;
                        }

                        // Báo cáo danh sách nhân vật đọc được về Python
                        if (!pal.charsReported) {
                            pal.charsReported = true;
                            send({
                                type: "autologin_characters_found",
                                account: pal.account,
                                characters: foundChars.map(function(c) { return { slot: c.slot, name: c.name, level: c.level, classCode: c.classCode }; })
                            });
                        }

                        // Lựa chọn nhân vật mục tiêu:
                        var targetEntry = null;
                        var reqChar = (pal.character || "").trim().toLowerCase();
                        if (reqChar && reqChar !== "(mặc định)") {
                            for (var k = 0; k < foundChars.length; k++) {
                                if (foundChars[k].name.toLowerCase() === reqChar) {
                                    targetEntry = foundChars[k];
                                    break;
                                }
                            }
                        }
                        if (!targetEntry && foundChars.length > 0) {
                            targetEntry = foundChars[0];
                        }

                        // Gửi gói tin chọn nhân vật & vào thẳng game (gửi lại mỗi 20 frames nếu chưa vào Scene 4)
                        if (targetEntry && (!pal.charSelected || pal.inLobbyFrames % 20 === 0)) {
                            pal.charSelected = true;
                            pal.selectedCharName = targetEntry.name;
                            try {
                                var accStr = il2cpp_string_new(Memory.allocUtf8String(pal.account));
                                var chrStr = targetEntry.namePtr ? targetEntry.namePtr : il2cpp_string_new(Memory.allocUtf8String(targetEntry.name));

                                if (nativeAutoSelectCharacter !== null && nativeGetAutoLogin !== null) {
                                    var al = nativeGetAutoLogin();
                                    if (!al.isNull()) {
                                        nativeAutoSelectCharacter(al, accStr, chrStr);
                                    }
                                }

                                if (nativeUnitSelectCharacter !== null) {
                                    nativeUnitSelectCharacter(targetEntry.slot, chrStr);
                                }

                                if (typeof nativeUnitEntryCharacter !== 'undefined' && nativeUnitEntryCharacter !== null) {
                                    nativeUnitEntryCharacter(targetEntry.slot, chrStr);
                                }
                            } catch (eSel) {}

                            autoLoginLastStatus = {
                                done: false,
                                submitted: true,
                                stage: "selected_character",
                                scene: 3,
                                account: pal.account,
                                character: targetEntry.name,
                                slot: targetEntry.slot
                            };
                            send({
                                type: "autologin_status",
                                ok: true,
                                stage: "selected_character",
                                scene: 3,
                                account: pal.account,
                                character: targetEntry.name,
                                slot: targetEntry.slot
                            });
                        }
                        return;
                    }

                    // Scene 2 (Login screen - MLoginUI):
                    // Đảm bảo AutoLogin KHÔNG ở trạng thái QuickSwitch (QuickSwitchServerValue phải bằng -1)
                    if (!pal.configured) {
                        pal.configured = true;
                        var al = null;
                        if (nativeGetAutoLogin !== null) {
                            try { al = nativeGetAutoLogin(); } catch (eG) {}
                        }
                        if (al !== null && !al.isNull()) {
                            try {
                                al.add(0x20).writeU8(0);
                                al.add(0x21).writeU8(0);
                                al.add(0x22).writeU8(0);
                                al.add(0x23).writeU8(0);
                                al.add(0x24).writeS32(-1); // QUAN TRỌNG: -1 để MLoginUI không bị ép vào State 1 (Loading)
                                al.add(0x28).writePointer(ptr(0));
                                al.add(0x30).writePointer(ptr(0));
                            } catch (eAL) {}
                        }
                    }

                    // Tìm MLoginUI.Instance thông qua nativeRuntimeClassInit an toàn tuyệt đối
                    var mLoginInst = null;
                    try {
                        var mTypeOff = off('__MLOGIN_UI_TYPE_INFO__');
                        if (!mTypeOff.isNull()) {
                            var klass = null;
                            if (nativeRuntimeClassInit !== null) {
                                klass = nativeRuntimeClassInit(baseAddr.add(mTypeOff));
                            } else {
                                klass = baseAddr.add(mTypeOff).readPointer();
                            }
                            if (klass !== null && !klass.isNull()) {
                                var sf = klass.add(0xB8).readPointer();
                                if (!sf.isNull()) {
                                    mLoginInst = sf.readPointer();
                                }
                            }
                        }
                    } catch (eType) {}

                    if (mLoginInst === null || mLoginInst.isNull()) {
                        return;
                    }

                    // Đọc CurrentState của MLoginUI (offset 0x24):
                    // 0: None, 1: Loading, 2: Login, 3: ServerList, 4: LoginForm, 5: AccountList, 6: OAuthLoading, 7: OAuthList
                    var currState = -1;
                    try {
                        currState = mLoginInst.add(0x24).readS32();
                    } catch (eCS) {}

                    // Kiểm tra và tự động đóng modal cảnh báo (nếu có dialog HelperUI như "No access" / "Your account does not have permission")
                    try {
                        if (nativeGetHelperUI !== null) {
                            var helper = nativeGetHelperUI();
                            if (helper !== null && !helper.isNull()) {
                                var curDialog = helper.add(0x78).readPointer();
                                if (!curDialog.isNull()) {
                                    var okBtn = curDialog.add(0x40).readPointer();
                                    if (!okBtn.isNull() && nativeUnityEvent_Invoke !== null) {
                                        var onClick = okBtn.add(0x100).readPointer();
                                        if (!onClick.isNull()) {
                                            nativeUnityEvent_Invoke(onClick);
                                            send({ type: "log", msg: "Phát hiện hộp thoại thông báo game (Quyền phòng / Thông báo). Đã tự động nhấn OK." });
                                        }
                                    }
                                    // Nếu vừa bị từ chối quyền vào phòng (No access): tự động hạ về Server 1 (Free / Public) và cho phép kết nối lại!
                                    if (pal.server && pal.server !== 1) {
                                        send({ type: "log", msg: "Tài khoản không có quyền vào Server " + pal.server + ". Đang tự động chuyển hướng kết nối sang Server 1 (Public Free)..." });
                                        pal.server = 1;
                                        pal.serverConnected = false;
                                        try {
                                            if (nativeMLoginSetState !== null) {
                                                nativeMLoginSetState(mLoginInst, 3);
                                            }
                                        } catch (eSt3) {}
                                    }
                                }
                            }
                        }
                    } catch (eDlg) {}

                    // Nếu game đang ở State 1 (Loading) hoặc 0 (None):
                    // Game đang tải tài nguyên / kết nối web API ban đầu -> KIÊN NHẪN ĐỢI
                    if (currState <= 1) {
                        autoLoginLastStatus = { done: false, submitted: pal.submitted, stage: "waiting_login_ui", state: currState, frames: pal.frames, account: pal.account };
                        if (pal.frames % 60 === 0) {
                            send({ type: "autologin_status", ok: false, stage: "waiting_login_ui", state: currState, frames: pal.frames, account: pal.account });
                        }
                        // Nếu bị kẹt ở Loading State 1 quá 180 frames (3s) sau khi đã cố kết nối server, đưa về ServerList (State 3) để thử lại
                        if (pal.serverConnected && pal.frames > 180 && currState === 1) {
                            try {
                                if (nativeMLoginSetState !== null) {
                                    nativeMLoginSetState(mLoginInst, 3);
                                    pal.serverConnected = false;
                                }
                            } catch (eUnstick) {}
                        }
                        return;
                    }

                    // Nếu game ở trạng thái ServerList (State 3): Tự động chọn server mục tiêu (mặc định Server 1 cho mọi tài khoản)
                    if (currState === 3 && !pal.serverConnected) {
                        pal.serverConnected = true;
                        var targetSrv = (pal.server && parseInt(pal.server) >= 1) ? parseInt(pal.server) : 1;
                        try {
                            if (nativeConnectServerSelect !== null) {
                                nativeConnectServerSelect(targetSrv);
                            } else if (nativeGetCSConnection !== null && nativeCSConnect !== null) {
                                var cs = nativeGetCSConnection();
                                if (!cs.isNull()) {
                                    nativeCSConnect(cs, targetSrv);
                                }
                            }
                            if (nativeMLoginSetState !== null) {
                                nativeMLoginSetState(mLoginInst, 1);
                            }
                        } catch (eSrv) {}
                        autoLoginLastStatus = { done: false, submitted: true, stage: "connecting_server", server: targetSrv, account: pal.account };
                        send({ type: "autologin_status", ok: true, stage: "connecting_server", server: targetSrv, account: pal.account });
                        return;
                    }

                    // Khi game đã nạp xong (currState >= 2) và chưa submit:
                    if (!pal.submitted) {
                        var accStr = il2cpp_string_new(Memory.allocUtf8String(pal.account));

                        // 1. Trường hợp có Mật khẩu: Đăng nhập bằng WebAPI Form Submit và UI Automation
                        if (pal.password && (nativeMLoginSubmit !== null || nativeUnityEvent_Invoke !== null)) {
                            // Đảm bảo UI chuyển sang LoginForm panel (State 4)
                            if (currState !== 4) {
                                try {
                                    if (nativeMLoginSetState !== null) {
                                        nativeMLoginSetState(mLoginInst, 4);
                                    }
                                } catch (eSt4) {}
                                return; // Chờ 1 frame để Unity kích hoạt Panel và các InputField
                            }

                            var pwdStr = il2cpp_string_new(Memory.allocUtf8String(pal.password));
                            var uInput = ptr(0);
                            var pInput = ptr(0);
                            try {
                                uInput = mLoginInst.add(0x98).readPointer();
                                pInput = mLoginInst.add(0xA0).readPointer();
                            } catch (eInp) {}

                            // Nếu các ô InputField chưa sẵn sàng thì đợi frame sau
                            if (uInput.isNull() || pInput.isNull()) {
                                return;
                            }

                            pal.submitted = true;

                            // Điền text vào InputField và tick nhớ mật khẩu
                            try {
                                if (nativeInputField_set_text !== null) {
                                    nativeInputField_set_text(uInput, accStr);
                                    nativeInputField_set_text(pInput, pwdStr);
                                }
                                uInput.add(0x180).writePointer(accStr);
                                pInput.add(0x180).writePointer(pwdStr);

                                var remToggle = mLoginInst.add(0xA8).readPointer();
                                if (!remToggle.isNull()) {
                                    remToggle.add(0x120).writeU8(1);
                                }
                            } catch (eFill) {}

                            // Kích hoạt Event Enter Button hoặc gọi direct native submit
                            var clickedEnter = false;
                            try {
                                var enterBtn = mLoginInst.add(0xB0).readPointer();
                                if (!enterBtn.isNull() && nativeUnityEvent_Invoke !== null) {
                                    var onClick = enterBtn.add(0x100).readPointer();
                                    if (!onClick.isNull()) {
                                        nativeUnityEvent_Invoke(onClick);
                                        clickedEnter = true;
                                    }
                                }
                            } catch (eBtn) {}

                            if (!clickedEnter && nativeMLoginSubmit !== null) {
                                try {
                                    nativeMLoginSubmit(mLoginInst, accStr, pwdStr, 1);
                                } catch (eSub) {}
                            }

                            autoLoginLastStatus = { done: false, submitted: true, stage: "submitted_password", account: pal.account };
                            send({ type: "autologin_status", ok: true, stage: "submitted_password", account: pal.account });
                            return;
                        }
                        // 2. Trường hợp Đăng nhập bằng Token Registry hoặc Tài khoản đã lưu
                        else if (pal.token && pal.token.length > 0) {
                            pal.submitted = true;
                            var tokenStr = il2cpp_string_new(Memory.allocUtf8String(pal.token));

                            if (nativeGetUserAccount !== null) {
                                try {
                                    var uAcc = nativeGetUserAccount();
                                    if (!uAcc.isNull()) {
                                        if (nativeUserAccountSetUsername !== null) {
                                            nativeUserAccountSetUsername(uAcc, accStr, 1);
                                        }
                                        if (nativeUserAccountSetToken !== null) {
                                            nativeUserAccountSetToken(uAcc, tokenStr);
                                        }
                                    }
                                } catch (eUA) {}
                            }

                            try {
                                mLoginInst.add(0x2C).writeU8(1);
                                if (nativeMLoginSetState !== null) {
                                    nativeMLoginSetState(mLoginInst, 1);
                                }
                            } catch (eSt) {}

                            if (nativeGetCSConnection !== null && nativeCSConnect !== null) {
                                try {
                                    var cs = nativeGetCSConnection();
                                    if (!cs.isNull()) {
                                        var targetSrv = (pal.server && parseInt(pal.server) >= 1) ? parseInt(pal.server) : 1;
                                        nativeCSConnect(cs, targetSrv);
                                    }
                                } catch (eCS) {}
                            }

                            autoLoginLastStatus = { done: false, submitted: true, stage: "submitted_token", account: pal.account };
                            send({ type: "autologin_status", ok: true, stage: "submitted_token", account: pal.account });
                            return;
                        }
                        // 3. Nếu không có password và không có token: Không làm treo UI, báo thiếu thông tin
                        else {
                            pal.submitted = true;
                            autoLoginLastStatus = { done: true, submitted: false, stage: "need_credentials", account: pal.account, err: "Chưa cấu hình mật khẩu hoặc token registry" };
                            send({ type: "autologin_status", ok: false, stage: "need_credentials", account: pal.account });
                            pendingAutoLogin = null;
                            return;
                        }
                    }
                } catch (eGU) {
                    send({ type: "log", msg: "Error in gameUpdateHook: " + eGU });
                }
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

function getSceneWorldIndex() {
    try {
        var tiOffset = off('__GAME_TYPE_INFO__');
        if (!tiOffset.isNull()) {
            var typeInfo = baseAddr.add(tiOffset).readPointer();
            if (!typeInfo.isNull()) {
                var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                if (!staticFields.isNull()) {
                    var gameInstance = staticFields.add(ptr('0x8')).readPointer();
                    if (!gameInstance.isNull()) {
                        var sceneHandler = gameInstance.add(ptr('0x78')).readPointer();
                        if (!sceneHandler.isNull()) {
                            var wi = sceneHandler.add(ptr('0x40')).readS32();
                            if (wi >= 0 && wi <= 255) return wi;
                        }
                    }
                }
            }
        }
    } catch (eSWI) {}
    return -1;
}

function isCurrentMapDoubleGoer() {
    // Khớp 100% logic gốc GameAssembly.dll: Mega.DoubleGoer$$PAGCDNAAHMO (<RVA>)
    // chỉ trả về true khi 82 <= Game._Scene.WorldIndex (+0x40) <= 90 (KHÔNG bao gồm 65..68!)
    var wi = getSceneWorldIndex();
    if (wi >= 0) {
        return (wi >= 82 && wi <= 90);
    }
    var mid = getCurrentMapId();
    return (mid >= 82 && mid <= 90);
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

        var level = 0, classId = 0, changeUp = 0;
        try {
            level = p.add(off('__PLAYER_LEVEL__')).readS32();
            classId = p.add(off('__PLAYER_CLASS__')).readS32();
            var cuOff = off('__PLAYER_CHANGE_UP__');
            if (!cuOff.isNull()) {
                changeUp = p.add(cuOff).readS32();
            }
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
            changeUp: changeUp,
            mapId: mapId,
            inDoubleGoer: isCurrentMapDoubleGoer(),
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
        if (typeof isMirrorCriticalActive === "function" && isMirrorCriticalActive()) return;
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
var doubleGoerEnterRecvHook = null;
var _mirrorPinnedArrPtr = null;
var _mirrorPinnedHandle = 0;
var _sockErrBuf = null;
var _savedTurboTargetFps = null;
var _savedTurboVSyncCount = null;
var _pendingMirrorFpsBoost = false;
var _pendingMirrorFpsRestore = false;
var _pendingMirrorPreStage = null;
var _pendingMirrorRescanTicket = false;
var _mirrorLastMainTickMs = 0;
var _mirrorZeroConfirmMode = true;
var _suppressMirrorUiUntilMs = 0;

var _nativeMirrorTurboStats = {
    running: false,
    armed: false,
    armStartEpochMs: 0,
    packetsSent: 0,
    mainThreadHits: 0,
    directSocketHits: 0,
    fallbackHits: 0,
    directSocketErrors: 0,
    startTime: 0,
    durationMs: 0,
    intervalMs: 10,
    staggerMs: 0,
    activeSlot: -1,
    relSlot: -1,
    entered: false,
    serverAccepted: false,
    spamPaused: false,
    needLugardWarm: false,
    directSocketFast: true,
    ackPaced: true,
    continuousBurst: true,
    zeroConfirm: true,
    suppressedDialogs: 0,
    suppressedConfirms: 0,
    ackInFlight: false,
    recvSeq: 0,
    lastRecvSeqAtSend: 0,
    lastSendMs: 0,
    firstSendMs: 0,
    firstAckRecorded: false,
    lastRecvMs: 0,
    lastRecvCode: -1,
    prevRecvCode: -1,
    rCodeCounts: {},
    probePendingSendMs: 0,
    probeMode: false,
    probeRemaining: 0,
    probeNextAtMs: 0,
    probeIntervalMs: 320,
    probeRelSlot: -1,
    rttMs: -1,
    minRttMs: -1,
    serverOpenEpochMs: 0,
    targetOpenEpochMs: 0,
    oneWayLatencyMs: 0,
    clockCalibrated: true,
    critLeadMs: 450,
    critTailMs: 1500,
    targetFps: 240,
    activePhase: "idle",
    tcpNoDelayEnabled: false,
    preStagedAtMs: 0,
    fpsBoosted: false
};

function isMirrorCriticalActive() {
    var st = _nativeMirrorTurboStats;
    if (st.running && !st.spamPaused) return true;
    if (st.armed && st.armStartEpochMs > 0) {
        var remain = st.armStartEpochMs - Date.now();
        if (remain <= 1500) return true;
    }
    return false;
}

function isMirrorZeroConfirmSuppressing() {
    if (!_mirrorZeroConfirmMode) return false;
    var st = _nativeMirrorTurboStats;
    if (st.running || st.armed || st.probeMode) return true;
    if (_suppressMirrorUiUntilMs > 0 && Date.now() <= _suppressMirrorUiUntilMs) return true;
    return false;
}

function cleanupNativeTurbo() {
    if (_nativeMirrorTurboTimer !== null) {
        clearInterval(_nativeMirrorTurboTimer);
        _nativeMirrorTurboTimer = null;
    }
}

function freePinnedMirrorPacket() {
    try {
        if (_mirrorPinnedHandle && _mirrorPinnedHandle !== 0 && il2cpp_gchandle_free !== null) {
            il2cpp_gchandle_free(_mirrorPinnedHandle);
        }
    } catch (eFreePin) {}
    _mirrorPinnedHandle = 0;
    _mirrorPinnedArrPtr = null;
}

function ensurePinnedMirrorPacket() {
    if (_mirrorPinnedArrPtr !== null && !_mirrorPinnedArrPtr.isNull()) {
        return _mirrorPinnedArrPtr;
    }
    try {
        var arr = createManagedByteArray([0x10, 0x05, (0xBF ^ 0xCB) & 0xFF, 0x0E, 0x00]);
        if (!arr || arr.isNull()) return null;
        if (il2cpp_gchandle_new !== null) {
            var h = il2cpp_gchandle_new(arr, 1);
            if (!h) return null;
            _mirrorPinnedHandle = h;
            _mirrorPinnedArrPtr = arr;
            return _mirrorPinnedArrPtr;
        }
    } catch (ePinArr) {}
    return null;
}

function writePinnedMirrorFrame(arrPtr, relSlot) {
    _c1SaltCounter = (_c1SaltCounter + 1) % 15;
    var raw = arrPtr.add(0x20);
    raw.writeU8((0x10 + _c1SaltCounter) & 0xFF);
    raw.add(1).writeU8(0x05);
    raw.add(2).writeU8((0xBF ^ 0xCB) & 0xFF);
    raw.add(3).writeU8(0x0E);
    raw.add(4).writeU8(relSlot & 0xFF);
}

function getInventoryItemsArray() {
    try {
        var p = getPlayerPtr();
        if (!p || p.isNull()) return null;
        var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
        if (inv.isNull()) return null;
        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
        return itemsArr.isNull() ? null : itemsArr;
    } catch (eGIIA) {
        return null;
    }
}

function findMirrorTicketSlotSmart() {
    try {
        var itemsArr = getInventoryItemsArray();
        if (!itemsArr || itemsArr.isNull()) return -1;
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
                        break;
                    } else if (s >= 76 && extTicketSlot < 0) {
                        extTicketSlot = s;
                    }
                }
            }
        }
        return (mainTicketSlot >= 12) ? mainTicketSlot : extTicketSlot;
    } catch (eScan) {}
    return -1;
}

function boostMirrorTurboFpsMainThread() {
    _pendingMirrorFpsBoost = false;
    try {
        var desiredFps = (_nativeMirrorTurboStats.targetFps !== undefined && _nativeMirrorTurboStats.targetFps !== null)
            ? parseInt(_nativeMirrorTurboStats.targetFps)
            : 240;
        if (isNaN(desiredFps)) desiredFps = 240;
        if (desiredFps <= 0) {
            _nativeMirrorTurboStats.fpsBoosted = false;
            return;
        }
        desiredFps = Math.max(60, Math.min(240, desiredFps));
        if (_savedTurboTargetFps === null && nativeGetTargetFps !== null) {
            try { _savedTurboTargetFps = nativeGetTargetFps(); } catch (eGF) {}
        }
        if (_savedTurboVSyncCount === null && nativeGetVSyncCount !== null) {
            try { _savedTurboVSyncCount = nativeGetVSyncCount(); } catch (eGV) {}
        }
        if (nativeSetVSyncCount !== null) {
            try { nativeSetVSyncCount(0); } catch (eSV) {}
        }
        if (nativeSetTargetFps !== null) {
            try { nativeSetTargetFps(desiredFps); } catch (eSF) {}
        }
        _nativeMirrorTurboStats.fpsBoosted = true;
    } catch (eBoost) {}
}

function restoreMirrorTurboFpsMainThread() {
    _pendingMirrorFpsRestore = false;
    try {
        if (_savedTurboTargetFps !== null && nativeSetTargetFps !== null) {
            try { nativeSetTargetFps(parseInt(_savedTurboTargetFps)); } catch (eRF) {}
        }
        if (_savedTurboVSyncCount !== null && nativeSetVSyncCount !== null) {
            try { nativeSetVSyncCount(parseInt(_savedTurboVSyncCount)); } catch (eRV) {}
        }
    } catch (eRest) {}
    _savedTurboTargetFps = null;
    _savedTurboVSyncCount = null;
    _nativeMirrorTurboStats.fpsBoosted = false;
}

function dispatchMirrorEnterPacketFast(relSlot) {
    try {
        var gs = getGSConnection();
        var rSlot = relSlot & 0xFF;
        var pinnedPtr = ensurePinnedMirrorPacket();

        if (!gs.isNull() && pinnedPtr !== null && !pinnedPtr.isNull()) {
            writePinnedMirrorFrame(pinnedPtr, rSlot);

            // Method 5: Direct Socket.Send Fast-Path trên Unity MainThread (bỏ qua SendAsync/TaskFactory + TCP_NODELAY)
            if (_nativeMirrorTurboStats.directSocketFast &&
                nativePktEncNikini !== null &&
                nativePktEncNgjg !== null &&
                nativeSocketSendErr !== null) {
                var serialAddr = gs.add(0xC0);
                var prevSerial = 0;
                var serialSaved = false;
                var bytesActuallySent = false;
                try {
                    if (_sockErrBuf === null) _sockErrBuf = Memory.alloc(4);
                    var tcp = gs.add(0x90).readPointer();
                    if (!tcp.isNull()) {
                        ensureTcpNoDelay(gs);
                        var sock = tcp.add(0x10).readPointer();
                        if (!sock.isNull() && sock.add(0x52).readU8() === 1) {
                            prevSerial = serialAddr.readU8();
                            serialSaved = true;
                            var encArr = nativePktEncNikini(pinnedPtr, serialAddr, ptr(0));
                            if (encArr && !encArr.isNull()) {
                                var encLen = encArr.add(0x18).readS32();
                                if (encLen > 0) {
                                    // Stream cipher FONJFGEKJHI (<RVA>) khop 100% GSConnection.INIIKIPJDIJ
                                    nativePktEncNgjg(encArr, encArr, ptr(0));
                                    _sockErrBuf.writeS32(0);
                                    // Socket.Send(byte[], 0, encLen, None, out err) @ <RVA>
                                    var sentBytes = nativeSocketSendErr(sock, encArr, 0, encLen, 0, _sockErrBuf, ptr(0));
                                    var sockErr = _sockErrBuf.readS32();
                                    if (sentBytes > 0 && sockErr === 0) {
                                        bytesActuallySent = true;
                                        if (nativeGetUnityTime !== null) {
                                            try { gs.add(0x74).writeFloat(nativeGetUnityTime()); } catch (eUT) {}
                                        }
                                        try { gs.add(0xB8).writeS32(gs.add(0xB8).readS32() + 1); } catch (eSC) {}
                                        _nativeMirrorTurboStats.directSocketHits += 1;
                                        return true;
                                    }
                                    // Socket khong gui duoc byte nao -> khoi phuc SendSerial de tranh lech sequence voi Server!
                                    if (!bytesActuallySent && serialSaved) {
                                        try { serialAddr.writeU8(prevSerial); } catch (eRB1) {}
                                    }
                                    _nativeMirrorTurboStats.directSocketErrors += 1;
                                    if (_nativeMirrorTurboStats.directSocketErrors >= 3) {
                                        _nativeMirrorTurboStats.directSocketFast = false;
                                    }
                                } else if (serialSaved) {
                                    try { serialAddr.writeU8(prevSerial); } catch (eRB2) {}
                                }
                            } else if (serialSaved) {
                                try { serialAddr.writeU8(prevSerial); } catch (eRB3) {}
                            }
                        }
                    }
                } catch (eSockFast) {
                    // Rollback SendSerial neu exception truoc khi gui byte de tuyet doi khong nhay +2 serial!
                    if (!bytesActuallySent && serialSaved) {
                        try { serialAddr.writeU8(prevSerial); } catch (eRB4) {}
                    }
                    _nativeMirrorTurboStats.directSocketErrors += 1;
                    if (_nativeMirrorTurboStats.directSocketErrors >= 3) {
                        _nativeMirrorTurboStats.directSocketFast = false;
                    }
                }
            }

            // Method 2 fallback: Zero-alloc pinned nativeGSSend trực tiếp trên Unity MainThread
            // Luôn ghi lại 5 byte header trước fallback vì DCBFPGDDCMG (<RVA>) sửa mảng đầu vào tại chỗ!
            writePinnedMirrorFrame(pinnedPtr, rSlot);
            if (sendGSPacketDirect(gs, pinnedPtr)) {
                _nativeMirrorTurboStats.fallbackHits += 1;
                return true;
            }
        }

        // Native/managed fallback cuối
        if (nativeMirrorEnterAlt !== null) {
            try {
                nativeMirrorEnterAlt(rSlot);
                _nativeMirrorTurboStats.fallbackHits += 1;
                return true;
            } catch (eNEA) {}
        }
        if (sendMirrorEnterPacket(rSlot)) {
            _nativeMirrorTurboStats.fallbackHits += 1;
            return true;
        }
    } catch (eDisp) {}
    return false;
}

function finishMirrorTurbo(msgType, enteredFlag) {
    _nativeMirrorTurboStats.running = false;
    _nativeMirrorTurboStats.armed = false;
    _nativeMirrorTurboStats.spamPaused = false;
    _nativeMirrorTurboStats.ackInFlight = false;
    if (enteredFlag) _nativeMirrorTurboStats.entered = true;
    cleanupNativeTurbo();
    _pendingMirrorFpsRestore = true;
    if (_mirrorZeroConfirmMode) {
        _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, Date.now() + 1200);
    }
    try {
        var nowMs = Date.now();
        var elapsed = _nativeMirrorTurboStats.startTime > 0 ? (nowMs - _nativeMirrorTurboStats.startTime) : 0;
        send({
            type: msgType,
            packets: _nativeMirrorTurboStats.packetsSent,
            elapsed: elapsed,
            mainThreadHits: _nativeMirrorTurboStats.mainThreadHits,
            directSocketHits: _nativeMirrorTurboStats.directSocketHits,
            fallbackHits: _nativeMirrorTurboStats.fallbackHits,
            directSocketErrors: _nativeMirrorTurboStats.directSocketErrors,
            tcpNoDelayEnabled: _nativeMirrorTurboStats.tcpNoDelayEnabled,
            rttMs: _nativeMirrorTurboStats.rttMs,
            minRttMs: _nativeMirrorTurboStats.minRttMs,
            lastRecvCode: _nativeMirrorTurboStats.lastRecvCode,
            rCodeCounts: _nativeMirrorTurboStats.rCodeCounts,
            serverOpenEpochMs: _nativeMirrorTurboStats.serverOpenEpochMs,
            zeroConfirm: _nativeMirrorTurboStats.zeroConfirm,
            suppressedDialogs: _nativeMirrorTurboStats.suppressedDialogs,
            suppressedConfirms: _nativeMirrorTurboStats.suppressedConfirms
        });
    } catch (eFin) {}
}

function handleMirrorEnterRecv(rCode, recvAtMs) {
    var st = _nativeMirrorTurboStats;
    st.prevRecvCode = st.lastRecvCode;
    st.lastRecvCode = rCode;
    st.lastRecvMs = recvAtMs;
    st.recvSeq = (st.recvSeq || 0) + 1;
    var kCode = String(rCode);
    st.rCodeCounts[kCode] = (st.rCodeCounts[kCode] || 0) + 1;

    var latestRttSample = -1;
    if (st.probePendingSendMs > 0) {
        var rttSample = recvAtMs - st.probePendingSendMs;
        if (rttSample >= 1 && rttSample <= 2000) {
            latestRttSample = rttSample;
            st.rttMs = (st.rttMs < 0) ? rttSample : Math.round(st.rttMs * 0.6 + rttSample * 0.4);
            st.minRttMs = (st.minRttMs < 0) ? rttSample : Math.min(st.minRttMs, rttSample);
        }
        st.probePendingSendMs = 0;
        if (st.probeRemaining > 0) {
            st.probeNextAtMs = recvAtMs + 45;
        }
    } else if (st.firstSendMs > 0 && !st.firstAckRecorded && st.packetsSent <= 2) {
        var firstRtt = recvAtMs - st.firstSendMs;
        if (firstRtt >= 1 && firstRtt <= 2000) {
            latestRttSample = firstRtt;
            st.rttMs = (st.rttMs < 0) ? firstRtt : Math.round(st.rttMs * 0.6 + firstRtt * 0.4);
            st.minRttMs = (st.minRttMs < 0) ? firstRtt : Math.min(st.minRttMs, firstRtt);
        }
        st.firstAckRecorded = true;
    }

    st.ackInFlight = false;

    // Ước lượng độ trễ 1 chiều để trừ ngược về mốc mở cổng thực trên GameServer
    var estOneWay = (st.oneWayLatencyMs > 0)
        ? st.oneWayLatencyMs
        : ((st.minRttMs > 0) ? (st.minRttMs * 0.5) : ((st.rttMs > 0) ? (st.rttMs * 0.5) : 0));

    if (rCode === 0) {
        if (!st.serverAccepted) {
            st.serverAccepted = true;
            st.spamPaused = true;
            var transR0 = (st.prevRecvCode === 6) ? "R6->R0" : "direct_R0";
            if (st.prevRecvCode === 6 || st.serverOpenEpochMs === 0) {
                st.serverOpenEpochMs = Math.round(recvAtMs - estOneWay);
            }
            try {
                send({
                    type: "mirror_enter_recv",
                    rCode: 0,
                    serverOpenEpochMs: st.serverOpenEpochMs,
                    rawRecvAtMs: recvAtMs,
                    oneWaySubtractedMs: Math.round(estOneWay),
                    transition: transR0,
                    recvAtMs: recvAtMs,
                    rttMs: (latestRttSample > 0) ? latestRttSample : st.rttMs,
                    minRttMs: st.minRttMs,
                    packets: st.packetsSent,
                    elapsed: st.startTime > 0 ? (recvAtMs - st.startTime) : 0,
                    probe: st.probeMode
                });
            } catch (eR0) {}
        }
        st.probeMode = false;
        return;
    }

    // Học mốc mở cổng thật ngay cả khi bị trượt (R=6 chưa mở -> R=2 vừa mở nhưng phòng đầy)
    var learnedOnR2 = false;
    if (rCode === 2 && st.prevRecvCode === 6 && st.serverOpenEpochMs === 0 && st.running) {
        st.serverOpenEpochMs = Math.round(recvAtMs - estOneWay);
        learnedOnR2 = true;
    }

    if (rCode === 1 && st.running) {
        _pendingMirrorRescanTicket = true;
    }

    if (st.probeMode || learnedOnR2 || rCode !== st.prevRecvCode) {
        try {
            var evMsg = {
                type: "mirror_enter_recv",
                rCode: rCode,
                recvAtMs: recvAtMs,
                rttMs: (latestRttSample > 0) ? latestRttSample : st.rttMs,
                minRttMs: st.minRttMs,
                packets: st.packetsSent,
                probe: st.probeMode
            };
            if (learnedOnR2) {
                evMsg.serverOpenEpochMs = st.serverOpenEpochMs;
                evMsg.rawRecvAtMs = recvAtMs;
                evMsg.oneWaySubtractedMs = Math.round(estOneWay);
                evMsg.transition = "R6->R2";
            }
            send(evMsg);
        } catch (eRN) {}
        if (st.probeMode && st.probeRemaining <= 0) st.probeMode = false;
    }
}

function tickNativeMirrorTurboMainThread() {
    var nowMs = Date.now();
    _mirrorLastMainTickMs = nowMs;

    if (_pendingMirrorFpsRestore) {
        restoreMirrorTurboFpsMainThread();
    }
    if (_pendingMirrorFpsBoost) {
        boostMirrorTurboFpsMainThread();
    }

    var st = _nativeMirrorTurboStats;

    if (_pendingMirrorPreStage !== null) {
        var ps = _pendingMirrorPreStage;
        _pendingMirrorPreStage = null;
        try {
            ensurePinnedMirrorPacket();
            ensureTcpNoDelay(getGSConnection());
            if (nativeCloseTalk !== null) {
                try { nativeCloseTalk(); } catch (eCT1) {}
            }
            sendLugardTalkPacket();
            st.preStagedAtMs = nowMs;
            var pCnt = ps.probeCount ? parseInt(ps.probeCount) : (ps.measureProbe ? 1 : 0);
            if (pCnt > 0 && ps.relSlot >= 0) {
                st.probeMode = true;
                st.probeRelSlot = ps.relSlot;
                st.probeRemaining = Math.max(0, pCnt - 1);
                st.probePendingSendMs = Date.now();
                st.probeNextAtMs = nowMs + st.probeIntervalMs;
                dispatchMirrorEnterPacketFast(ps.relSlot);
            }
        } catch (ePS) {}
    } else if (st.probeRemaining > 0 && !st.running && st.probeRelSlot >= 0) {
        // Bắn tiếp các gói thăm dò RTT còn lại (multi-probe burst ở T-15s) để lấy minRTT sạch jitter
        var readyForNextProbe = (st.probePendingSendMs === 0 && nowMs >= st.probeNextAtMs)
            || (st.probePendingSendMs > 0 && (nowMs - st.probePendingSendMs) >= 1200);
        if (readyForNextProbe) {
            st.probeRemaining -= 1;
            st.probeMode = true;
            st.probePendingSendMs = nowMs;
            st.probeNextAtMs = nowMs + st.probeIntervalMs;
            dispatchMirrorEnterPacketFast(st.probeRelSlot);
        }
    }

    if (_pendingMirrorRescanTicket && st.running) {
        _pendingMirrorRescanTicket = false;
        var nextSlot = findMirrorTicketSlotSmart();
        if (nextSlot >= 12) {
            st.activeSlot = nextSlot;
            st.relSlot = nextSlot - 12;
        }
    }

    if (!st.running && !st.armed) return;

    // Kiểm tra đã thực sự vào map Double Goer (WorldIndex 82..90)
    if (isCurrentMapDoubleGoer()) {
        finishMirrorTurbo("mirror_turbo_entered", true);
        return;
    }

    // Chế độ Pre-Armed Gate (Method 4): Đợi đúng mốc startAtEpochMs trên đồng hồ máy
    if (st.armed && !st.running) {
        if (!st.fpsBoosted && (st.armStartEpochMs - nowMs) <= 2000) {
            boostMirrorTurboFpsMainThread();
        }
        if (nowMs >= st.armStartEpochMs) {
            st.armed = false;
            st.running = true;
            st.startTime = nowMs;
            st.firstSendMs = nowMs;
            st.firstAckRecorded = false;
            if (!st.fpsBoosted) boostMirrorTurboFpsMainThread();
        } else {
            return;
        }
    }

    if (!st.running) return;

    var elapsed = nowMs - st.startTime;
    if (elapsed >= st.durationMs) {
        finishMirrorTurbo("mirror_turbo_timeout", false);
        return;
    }

    // Nếu server vừa trả R=0 (accept), tạm dừng spam chờ warp map hoàn tất (tối đa 2500ms)
    if (st.spamPaused) {
        if (st.lastRecvMs > 0 && (nowMs - st.lastRecvMs) < 2500) {
            return;
        }
        st.spamPaused = false;
        st.serverAccepted = false;
    }

    if (st.needLugardWarm) {
        st.needLugardWarm = false;
        if (nativeCloseTalk !== null) {
            try { nativeCloseTalk(); } catch (eCT2) {}
        }
        sendLugardTalkPacket();
        st.preStagedAtMs = nowMs;
    }

    // Adaptive 3-Phase Pacing khi biết mốc mở cổng (targetOpenEpochMs > 0):
    // - Khi chưa hiệu chuẩn offset đồng hồ server (clockCalibrated === false), nới rộng vùng critical sớm 1200ms để không bị ghìm 50ms nếu GameServer chạy sớm hơn NTP!
    // - Khi đã hiệu chuẩn (clockCalibrated === true), giữ vùng critical gọn [-450ms .. +1500ms] tránh xả gói rác sớm.
    var effInterval = st.intervalMs;
    var allowAckRefire = st.ackPaced;
    if (st.targetOpenEpochMs > 0) {
        var oneWay = (st.oneWayLatencyMs > 0) ? st.oneWayLatencyMs : ((st.minRttMs > 0) ? (st.minRttMs * 0.5) : ((st.rttMs > 0) ? (st.rttMs * 0.5) : 0));
        var leadMs = (st.critLeadMs > 0) ? st.critLeadMs : (st.clockCalibrated ? 450 : 1200);
        var tailMs = (st.critTailMs > 0) ? st.critTailMs : (st.clockCalibrated ? 1500 : 2000);
        var critStart = st.targetOpenEpochMs - oneWay - leadMs;
        var critEnd = st.targetOpenEpochMs + tailMs;
        if (nowMs < critStart) {
            st.activePhase = "approach";
            effInterval = Math.max(st.intervalMs, 50);
            allowAckRefire = false;
        } else if (nowMs <= critEnd) {
            st.activePhase = "critical";
            effInterval = st.intervalMs;
            allowAckRefire = st.ackPaced;
        } else {
            st.activePhase = "tail";
            effInterval = Math.max(st.intervalMs, 25);
            allowAckRefire = st.ackPaced;
        }
    } else {
        st.activePhase = "burst";
    }

    // Pacing: effInterval = 0 -> bắn mỗi frame; effInterval >= 1 -> bắn khi đủ effInterval hoặc có ACK mới thật sự về sau gói trước
    var dueByTime = (st.lastSendMs === 0) || ((nowMs - st.lastSendMs) >= effInterval);
    var ackMinGap = Math.max(2, Math.floor(effInterval / 2));
    var dueByAck = allowAckRefire && !st.ackInFlight && (st.recvSeq > st.lastRecvSeqAtSend) && ((nowMs - st.lastSendMs) >= ackMinGap);
    if (!dueByTime && !dueByAck) {
        return;
    }

    st.lastSendMs = nowMs;
    st.lastRecvSeqAtSend = st.recvSeq;
    st.ackInFlight = true;
    dispatchMirrorEnterPacketFast(st.relSlot);
    st.packetsSent += 1;
    st.mainThreadHits += 1;
}

try {
    var dgerOff = off('__DOUBLEGOER_ENTER_RECV__');
    if (!dgerOff.isNull()) {
        doubleGoerEnterRecvHook = Interceptor.attach(baseAddr.add(dgerOff), {
            onEnter: function(args) {
                if (shuttingDown) return;
                try {
                    var arrPtr = args[0];
                    if (arrPtr && !arrPtr.isNull()) {
                        var len = arrPtr.add(0x18).readS32();
                        if (len >= 5) {
                            var rCode = arrPtr.add(0x24).readU8();
                            var recvNow = Date.now();
                            if (rCode !== 0 && isMirrorZeroConfirmSuppressing()) {
                                _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, recvNow + 600);
                            }
                            handleMirrorEnterRecv(rCode, recvNow);
                        }
                    }
                } catch (eDGER) {}
            }
        });
    }
} catch (eHookDGER) {}

function startOrArmMirrorTurboInternal(slot, intervalMs, maxDurationMs, startAtEpochMs, optionsObj) {
    ensureThreadAttached();
    cleanupNativeTurbo();

    var opts = (optionsObj && typeof optionsObj === "object") ? optionsObj : {};
    var itemSlot = -1;
    if (slot !== undefined && slot !== null && parseInt(slot) >= 0) {
        var sCandidate = parseInt(slot);
        try {
            var itemsArr = (typeof getInventoryItemsArray === "function") ? getInventoryItemsArray() : null;
            if (itemsArr !== null && !itemsArr.isNull()) {
                var testPtr = itemsArr.add(0x20 + sCandidate * 8).readPointer();
                if (!testPtr.isNull()) {
                    var idx = readItemIndex(testPtr);
                    var chk = checkMirrorItem(testPtr, idx);
                    if (chk.isTicket) {
                        itemSlot = sCandidate;
                    }
                }
            } else {
                itemSlot = sCandidate;
            }
        } catch (eVer) {
            itemSlot = sCandidate;
        }
    }
    if (itemSlot < 0 && opts.preStaged && _nativeMirrorTurboStats.activeSlot >= 0) {
        itemSlot = _nativeMirrorTurboStats.activeSlot;
    }
    if (itemSlot < 0) {
        itemSlot = findMirrorTicketSlotSmart();
    }

    if (itemSlot < 0) {
        return { success: false, error: "no_ticket" };
    }

    var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
    var parsedInt = (intervalMs !== undefined && intervalMs !== null) ? parseInt(intervalMs) : 10;
    if (isNaN(parsedInt)) parsedInt = 10;
    var intMs = Math.max(0, Math.min(1000, parsedInt));
    var maxDur = (maxDurationMs !== undefined && parseInt(maxDurationMs) >= 1000) ? parseInt(maxDurationMs) : 15000;
    var nowMs = Date.now();
    var targetEpoch = (startAtEpochMs !== undefined && startAtEpochMs !== null) ? Number(startAtEpochMs) : 0;
    var isArmedFuture = !isNaN(targetEpoch) && (targetEpoch > nowMs + 10);
    var recentlyStaged = (_nativeMirrorTurboStats.preStagedAtMs > 0) && ((nowMs - _nativeMirrorTurboStats.preStagedAtMs) <= 15000);
    var zeroConf = (opts.zeroConfirm !== false && opts.suppressDialogs !== false);
    var contBurst = (opts.continuousBurst !== false);

    _mirrorZeroConfirmMode = zeroConf;
    if (zeroConf) {
        var endAt = (isArmedFuture ? targetEpoch : nowMs) + maxDur + 2000;
        _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, endAt);
    } else {
        _suppressMirrorUiUntilMs = 0;
    }

    _nativeMirrorTurboStats.running = !isArmedFuture;
    _nativeMirrorTurboStats.armed = isArmedFuture;
    _nativeMirrorTurboStats.armStartEpochMs = isArmedFuture ? targetEpoch : 0;
    _nativeMirrorTurboStats.packetsSent = 0;
    _nativeMirrorTurboStats.mainThreadHits = 0;
    _nativeMirrorTurboStats.directSocketHits = 0;
    _nativeMirrorTurboStats.fallbackHits = 0;
    _nativeMirrorTurboStats.directSocketErrors = 0;
    _nativeMirrorTurboStats.startTime = isArmedFuture ? 0 : nowMs;
    _nativeMirrorTurboStats.durationMs = maxDur;
    _nativeMirrorTurboStats.intervalMs = intMs;
    _nativeMirrorTurboStats.staggerMs = opts.staggerMs ? Number(opts.staggerMs) : 0;
    _nativeMirrorTurboStats.activeSlot = itemSlot;
    _nativeMirrorTurboStats.relSlot = relSlot;
    _nativeMirrorTurboStats.entered = false;
    _nativeMirrorTurboStats.serverAccepted = false;
    _nativeMirrorTurboStats.spamPaused = false;
    _nativeMirrorTurboStats.needLugardWarm = (opts.preStaged === true || recentlyStaged) ? false : true;
    _nativeMirrorTurboStats.directSocketFast = (opts.directSocket !== false);
    _nativeMirrorTurboStats.ackPaced = (opts.ackPaced !== false);
    _nativeMirrorTurboStats.continuousBurst = contBurst;
    _nativeMirrorTurboStats.zeroConfirm = zeroConf;
    _nativeMirrorTurboStats.suppressedDialogs = 0;
    _nativeMirrorTurboStats.suppressedConfirms = 0;
    _nativeMirrorTurboStats.ackInFlight = false;
    _nativeMirrorTurboStats.recvSeq = 0;
    _nativeMirrorTurboStats.lastRecvSeqAtSend = 0;
    _nativeMirrorTurboStats.lastSendMs = 0;
    _nativeMirrorTurboStats.firstSendMs = isArmedFuture ? 0 : nowMs;
    _nativeMirrorTurboStats.firstAckRecorded = false;
    _nativeMirrorTurboStats.lastRecvCode = -1;
    _nativeMirrorTurboStats.prevRecvCode = -1;
    _nativeMirrorTurboStats.rCodeCounts = {};
    _nativeMirrorTurboStats.probePendingSendMs = 0;
    _nativeMirrorTurboStats.probeMode = false;
    _nativeMirrorTurboStats.probeRemaining = 0;
    _nativeMirrorTurboStats.probeNextAtMs = 0;
    _nativeMirrorTurboStats.serverOpenEpochMs = 0;
    _nativeMirrorTurboStats.targetOpenEpochMs = opts.targetOpenEpochMs ? Number(opts.targetOpenEpochMs) : 0;
    _nativeMirrorTurboStats.oneWayLatencyMs = opts.oneWayLatencyMs ? Number(opts.oneWayLatencyMs) : 0;
    _nativeMirrorTurboStats.clockCalibrated = (opts.clockCalibrated !== false);
    _nativeMirrorTurboStats.critLeadMs = (opts.critLeadMs !== undefined && opts.critLeadMs !== null && Number(opts.critLeadMs) > 0) ? Number(opts.critLeadMs) : 0;
    _nativeMirrorTurboStats.critTailMs = (opts.critTailMs !== undefined && opts.critTailMs !== null && Number(opts.critTailMs) > 0) ? Number(opts.critTailMs) : 0;
    _nativeMirrorTurboStats.targetFps = (opts.targetFps !== undefined && opts.targetFps !== null) ? Number(opts.targetFps) : 240;
    _nativeMirrorTurboStats.activePhase = isArmedFuture ? "armed" : "burst";

    if (!isArmedFuture || (targetEpoch - nowMs) <= 2500) {
        _pendingMirrorFpsBoost = true;
    }

    // Watchdog an toàn (hỗ trợ cả cửa sổ game thu nhỏ/chạy nền nếu Unity Update bị giảm tốc)
    var watchInterval = Math.max(8, Math.min(40, intMs > 0 ? intMs : 12));
    _nativeMirrorTurboTimer = setInterval(function() {
        try {
            ensureThreadAttached();
            var st = _nativeMirrorTurboStats;
            if (!st.running && !st.armed) {
                cleanupNativeTurbo();
                return;
            }
            var tNow = Date.now();
            if (isCurrentMapDoubleGoer()) {
                finishMirrorTurbo("mirror_turbo_entered", true);
                return;
            }
            if (st.armed && !st.running) {
                if (tNow >= st.armStartEpochMs && (_mirrorLastMainTickMs === 0 || (tNow - _mirrorLastMainTickMs) > 45)) {
                    st.armed = false;
                    st.running = true;
                    st.startTime = tNow;
                    st.firstSendMs = tNow;
                } else {
                    return;
                }
            }
            if (st.running && st.startTime > 0 && (tNow - st.startTime) >= st.durationMs) {
                finishMirrorTurbo("mirror_turbo_timeout", false);
                return;
            }
            // Chỉ bắn từ watchdog nếu Unity MainThread Update chưa tick trong >45ms (cửa sổ thu nhỏ/FPS tụt)
            if (st.running && !st.spamPaused && (tNow - _mirrorLastMainTickMs) > 45 && (tNow - st.lastSendMs) >= Math.max(5, st.intervalMs)) {
                st.lastSendMs = tNow;
                if (nativeMirrorEnterAlt !== null) {
                    try { nativeMirrorEnterAlt(st.relSlot); } catch (eWN) {}
                } else {
                    sendMirrorEnterPacket(st.relSlot);
                }
                st.packetsSent += 1;
                st.fallbackHits += 1;
            }
        } catch (eWatch) {}
    }, watchInterval);

    return {
        success: true,
        armed: isArmedFuture,
        startAtEpochMs: isArmedFuture ? targetEpoch : nowMs,
        slot: itemSlot,
        relSlot: relSlot,
        intervalMs: intMs,
        directSocketFast: _nativeMirrorTurboStats.directSocketFast,
        ackPaced: _nativeMirrorTurboStats.ackPaced,
        continuousBurst: _nativeMirrorTurboStats.continuousBurst,
        zeroConfirm: _nativeMirrorTurboStats.zeroConfirm,
        fpsBoostQueued: _pendingMirrorFpsBoost
    };
}

function findTargetKeyByName(targetName) {
    if (!targetName || typeof targetName !== "string") return -1;
    var cleanTarget = targetName.trim().toLowerCase();
    if (!cleanTarget) return -1;

    try {
        var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
        if (typeInfo.isNull()) return -1;
        var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
        if (staticFields.isNull()) return -1;
        var gameInstance = staticFields.add(ptr('0x8')).readPointer();
        if (gameInstance.isNull()) return -1;
        var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
        if (viewport.isNull()) return -1;
        var objDict = viewport.add(ptr('0x20')).readPointer();
        if (objDict.isNull()) return -1;
        var entries = objDict.add(ptr('0x18')).readPointer();
        if (entries.isNull()) return -1;
        var count = objDict.add(ptr('0x20')).readS32();
        var arrLen = 0;
        try { arrLen = entries.add(ptr('0x18')).readS32(); } catch (eAL) {}
        var scanLimit = (arrLen > 0) ? Math.min(arrLen, 500) : Math.min(Math.max(count, 0), 500);
        if (scanLimit <= 0) return -1;

        for (var i = 0; i < scanLimit; i++) {
            var entryAddr = entries.add(0x20 + i * 24);
            var val = entryAddr.add(16).readPointer();
            if (val.isNull()) continue;

            var klass = val.readPointer();
            if (klass.isNull()) continue;
            var klassName = "";
            try {
                klassName = klass.add(0x10).readPointer().readCString() || "";
            } catch (eK) {}
            if (klassName.indexOf("ViewportBody") === -1) continue;

            var body = val.add(ptr('0x18')).readPointer();
            if (body.isNull()) continue;

            var namePtr = body.add(0x28).readPointer();
            if (namePtr.isNull()) continue;
            var len = namePtr.add(0x10).readS32();
            if (len <= 0 || len > 64) continue;
            var bName = namePtr.add(0x14).readUtf16String(len);
            if (bName && bName.trim().toLowerCase() === cleanTarget) {
                var bIdx = body.add(0x20).readS32();
                return bIdx;
            }
        }
    } catch (eF) {}
    return -1;
}

// =========================================================================
// REA HOOK: TableEventEntryLevel.EAJKFGNLDBN (RVA <RVA>)
// Sửa lỗi client MEGAMU trả về -1 cho nhân vật Master (ChangeUp >= 2, vd: Slayer 175/197rr)
// Khi hàm trả về -1, client MEGAMU tự động bỏ qua vòng lặp tìm vé Master (6702) và hiển thị
// popup "You don't have a ticket for your level". Hook này đảm bảo hàm trả về cấp phòng
// Devil Square chuẩn theo level nhân vật, giúp client tự động nhận diện vé Master.
// =========================================================================
var tableEventEntryLevelHook = null;
try {
    var offEntryLevel = off('__TABLE_EVENT_ENTRY_LEVEL__');
    if (!offEntryLevel.isNull()) {
        tableEventEntryLevelHook = Interceptor.attach(baseAddr.add(offEntryLevel), {
            onEnter: function(args) {
                if (shuttingDown) return;
                // args[0] = TableEventEntryLevel this
                // args[1] = type (0 = DevilSquare, 1 = BloodCastle, 2 = ChaosCastle, 3 = IllusionTemple)
                // args[2] = body (Player Body)
                this.isDS = (args[1].toInt32() === 0);
            },
            onLeave: function(retval) {
                if (shuttingDown) return;
                if (this.isDS && retval.toInt32() === -1) {
                    var dsLvl = getPlayerDevilSquareLevel();
                    retval.replace(ptr(dsLvl));
                }
            }
        });
    }
} catch (eHookEntryLevel) {}

// =========================================================================
// REA HOOK: MHelperUI.OLPFNDAEMDG (ShowDialog central funnel Slot 17)
// Chặn triệt để popup báo lỗi Devil Square & toàn bộ thông báo/dialog Mirror
// khi đang chạy Mirror Turbo Zero-Confirm (0 UI overhead trên MainThread)
// =========================================================================
function _isMirrorDialogText(idStr, titleStr, msgStr) {
    var combined = (String(idStr || "") + " " + String(titleStr || "") + " " + String(msgStr || "")).toLowerCase();
    return (
        combined.indexOf("mirror") !== -1 ||
        combined.indexOf("double") !== -1 ||
        combined.indexOf("doppel") !== -1 ||
        combined.indexOf("lugard") !== -1 ||
        combined.indexOf("espelho") !== -1 ||
        combined.indexOf("dimensions") !== -1 ||
        combined.indexOf("dimens") !== -1 ||
        combined.indexOf("duplo") !== -1 ||
        combined.indexOf("gương") !== -1 ||
        combined.indexOf("mê cung") !== -1
    );
}

function _invokeUnityBoolActionTrue(actionPtr) {
    if (!actionPtr || actionPtr.isNull()) return false;
    try {
        // System.Delegate layout (IL2CPP x64): +0x10 method_ptr, +0x18 invoke_impl, +0x20 m_target, +0x28 method (MethodInfo*)
        var mPtr = actionPtr.add(0x10).readPointer();
        var target = actionPtr.add(0x20).readPointer();
        var mInfo = actionPtr.add(0x28).readPointer();
        if (!mPtr || mPtr.isNull()) return false;
        if (target && !target.isNull()) {
            var actInst = new NativeFunction(mPtr, 'void', ['pointer', 'bool', 'pointer']);
            actInst(target, 1, mInfo);
            return true;
        } else {
            var actStatic = new NativeFunction(mPtr, 'void', ['bool', 'pointer']);
            actStatic(1, mInfo);
            return true;
        }
    } catch (eInvAct) {
        return false;
    }
}

var helperUIShowDialogHook = null;
var helperUIShowDialogAddr = null;
var _helperUIShowDialogCb = null;
var _origHelperUIShowDialog = null;
try {
    var offHSDHook = off('__HELPER_UI_SHOW_DIALOG__');
    if (!offHSDHook.isNull()) {
        var hsdTarget = baseAddr.add(offHSDHook);
        if (typeof Interceptor.replaceFast === "function" && typeof NativeCallback === "function") {
            // Slot 17: Dialog OLPFNDAEMDG(this, id, title, message, overlay, action, timeout, methodInfo)
            _helperUIShowDialogCb = new NativeCallback(function(a0, a1, a2, a3, a4, a5, a6, a7) {
                if (!shuttingDown) {
                    if (isMirrorZeroConfirmSuppressing()) {
                        _nativeMirrorTurboStats.suppressedDialogs += 1;
                        return ptr(0);
                    }
                    try {
                        var idS = readIl2CppStrSafe(a1);
                        var titleS = readIl2CppStrSafe(a2);
                        var msgS = readIl2CppStrSafe(a3);
                        var lowMsg = (titleS + " " + msgS).toLowerCase();
                        if (_mirrorZeroConfirmMode && _isMirrorDialogText(idS, titleS, msgS)) {
                            _nativeMirrorTurboStats.suppressedDialogs += 1;
                            return ptr(0);
                        }
                        if (lowMsg.indexOf("ticket for your level") !== -1 || lowMsg.indexOf("don't have a ticket") !== -1) {
                            return ptr(0);
                        }
                    } catch (eMsgR) {}
                }
                if (_origHelperUIShowDialog !== null) {
                    return _origHelperUIShowDialog(a0, a1, a2, a3, a4, a5, a6, a7);
                }
                return ptr(0);
            }, 'pointer', ['pointer', 'pointer', 'pointer', 'pointer', 'bool', 'pointer', 'float', 'pointer']);
            var origHsdPtr = Interceptor.replaceFast(hsdTarget, _helperUIShowDialogCb);
            _origHelperUIShowDialog = new NativeFunction(origHsdPtr, 'pointer', ['pointer', 'pointer', 'pointer', 'pointer', 'bool', 'pointer', 'float', 'pointer']);
            helperUIShowDialogAddr = hsdTarget;
        } else {
            helperUIShowDialogHook = Interceptor.attach(hsdTarget, {
                onEnter: function(args) {
                    this.suppress = false;
                    if (shuttingDown) return;
                    if (isMirrorZeroConfirmSuppressing()) {
                        _nativeMirrorTurboStats.suppressedDialogs += 1;
                        this.suppress = true;
                        return;
                    }
                    try {
                        var idS = readIl2CppStrSafe(args[1]);
                        var titleS = readIl2CppStrSafe(args[2]);
                        var msgS = readIl2CppStrSafe(args[3]);
                        var lowMsg = (titleS + " " + msgS).toLowerCase();
                        if (_mirrorZeroConfirmMode && _isMirrorDialogText(idS, titleS, msgS)) {
                            _nativeMirrorTurboStats.suppressedDialogs += 1;
                            this.suppress = true;
                            return;
                        }
                        if (lowMsg.indexOf("ticket for your level") !== -1 || lowMsg.indexOf("don't have a ticket") !== -1) {
                            this.suppress = true;
                        }
                    } catch (eMsg) {}
                },
                onLeave: function(retval) {
                    if (this.suppress) {
                        retval.replace(ptr(0));
                    }
                }
            });
        }
    }
} catch (eHSDHook) {}

// =========================================================================
// REA HOOK: UIModalBox.Show
// Chặn hiển thị Modal Box thông báo/xác nhận trong chế độ Mirror Zero-Confirm
// để luồng Unity MainThread không bị khựng khi bắn gói Turbo liên tiếp
// =========================================================================
var uiModalBoxShowAddr = null;
var _uiModalBoxShowCb = null;
var _origUIModalBoxShow = null;
try {
    var offMBS = off('__MODAL_BOX_SHOW__');
    if (!offMBS.isNull() && typeof Interceptor.replaceFast === "function" && typeof NativeCallback === "function") {
        var mbsTarget = baseAddr.add(offMBS);
        _uiModalBoxShowCb = new NativeCallback(function(selfPtr, methodPtr) {
            if (!shuttingDown && isMirrorZeroConfirmSuppressing()) {
                _nativeMirrorTurboStats.suppressedDialogs += 1;
                return;
            }
            if (_origUIModalBoxShow !== null) {
                _origUIModalBoxShow(selfPtr, methodPtr);
            }
        }, 'void', ['pointer', 'pointer']);
        var origMbsPtr = Interceptor.replaceFast(mbsTarget, _uiModalBoxShowCb);
        _origUIModalBoxShow = new NativeFunction(origMbsPtr, 'void', ['pointer', 'pointer']);
        uiModalBoxShowAddr = mbsTarget;
    }
} catch (eMBSHook) {}

// =========================================================================
// REA HOOK: MHelperUI.ABCMKJLIBMI (ShowConfirm central funnel Slot 10)
// Tự động xác nhận vào Devil Square, Mirror & Party (100% Zero-Confirm:
// gọi thẳng callback YES với m_target tại +0x20 và KHÔNG hiển thị popup!)
// =========================================================================
var helperUIShowConfirmHook = null;
var helperUIShowConfirmAddr = null;
var _helperUIShowConfirmCb = null;
var _origHelperUIShowConfirm = null;
try {
    var offShowConfirm = off('__HELPER_UI_SHOW_CONFIRM__');
    if (!offShowConfirm.isNull()) {
        var hscTarget = baseAddr.add(offShowConfirm);
        if (typeof Interceptor.replaceFast === "function" && typeof NativeCallback === "function") {
            // Slot 10: Dialog ABCMKJLIBMI(this, id, title, message, overlay, action, timeout, isRemCb, onRemCb, methodInfo)
            _helperUIShowConfirmCb = new NativeCallback(function(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9) {
                if (!shuttingDown) {
                    try {
                        var idStr = readIl2CppStrSafe(a1);
                        var title = readIl2CppStrSafe(a2);
                        var msg = readIl2CppStrSafe(a3);
                        var lowT = title.toLowerCase();
                        var lowM = msg.toLowerCase();
                        var isDevilConfirm = (lowT.indexOf("devil") !== -1 || lowM.indexOf("devil") !== -1);
                        var isMirrorConfirm = _mirrorZeroConfirmMode && (
                            isMirrorZeroConfirmSuppressing() ||
                            _isMirrorDialogText(idStr, title, msg)
                        );
                        var isPartyConfirm = autoConfirmPartyEnabled && (
                            lowT.indexOf("party") !== -1 || lowM.indexOf("party") !== -1 ||
                            lowT.indexOf("tổ đội") !== -1 || lowM.indexOf("tổ đội") !== -1 ||
                            lowT.indexOf("to doi") !== -1 || lowM.indexOf("to doi") !== -1 ||
                            lowT.indexOf("nhóm") !== -1 || lowM.indexOf("nhóm") !== -1 ||
                            lowT.indexOf("pt") !== -1
                        );
                        var isReportConfirm = (_autoReportConfirmUntilMs > Date.now()) && _isPkReportDialogText(idStr, title, msg);

                        if (isDevilConfirm || isMirrorConfirm || isPartyConfirm || isReportConfirm) {
                            var invoked = _invokeUnityBoolActionTrue(a5);
                            if (isMirrorConfirm) {
                                _nativeMirrorTurboStats.suppressedConfirms += 1;
                                _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, Date.now() + 800);
                                return ptr(0);
                            }
                            if (invoked) {
                                if (isReportConfirm) {
                                    _autoReportConfirmCount += 1;
                                    send({
                                        type: "auto_report_confirmed",
                                        source: "show_confirm_hook",
                                        title: title,
                                        message: msg
                                    });
                                } else if (isPartyConfirm) {
                                    send({
                                        type: "auto_party_confirmed",
                                        source: "show_confirm_hook",
                                        title: title,
                                        message: msg
                                    });
                                }
                                return ptr(0);
                            }
                        }
                    } catch (eConfirmR) {}
                }
                if (_origHelperUIShowConfirm !== null) {
                    return _origHelperUIShowConfirm(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9);
                }
                return ptr(0);
            }, 'pointer', ['pointer', 'pointer', 'pointer', 'pointer', 'bool', 'pointer', 'float', 'pointer', 'pointer', 'pointer']);
            var origHscPtr = Interceptor.replaceFast(hscTarget, _helperUIShowConfirmCb);
            _origHelperUIShowConfirm = new NativeFunction(origHscPtr, 'pointer', ['pointer', 'pointer', 'pointer', 'pointer', 'bool', 'pointer', 'float', 'pointer', 'pointer', 'pointer']);
            helperUIShowConfirmAddr = hscTarget;
        } else {
            helperUIShowConfirmHook = Interceptor.attach(hscTarget, {
                onEnter: function(args) {
                    this.autoConfirm = false;
                    if (shuttingDown) return;
                    try {
                        var idStr = readIl2CppStrSafe(args[1]);
                        var title = readIl2CppStrSafe(args[2]);
                        var msg = readIl2CppStrSafe(args[3]);
                        var lowT = title.toLowerCase();
                        var lowM = msg.toLowerCase();
                        var isDevilConfirm = (lowT.indexOf("devil") !== -1 || lowM.indexOf("devil") !== -1);
                        var isMirrorConfirm = _mirrorZeroConfirmMode && (
                            isMirrorZeroConfirmSuppressing() ||
                            _isMirrorDialogText(idStr, title, msg)
                        );
                        var isPartyConfirm = autoConfirmPartyEnabled && (
                            lowT.indexOf("party") !== -1 || lowM.indexOf("party") !== -1 ||
                            lowT.indexOf("tổ đội") !== -1 || lowM.indexOf("tổ đội") !== -1 ||
                            lowT.indexOf("to doi") !== -1 || lowM.indexOf("to doi") !== -1 ||
                            lowT.indexOf("nhóm") !== -1 || lowM.indexOf("nhóm") !== -1 ||
                            lowT.indexOf("pt") !== -1
                        );

                        var isReportConfirm = (_autoReportConfirmUntilMs > Date.now()) && _isPkReportDialogText(idStr, title, msg);

                        if (isDevilConfirm || isMirrorConfirm || isPartyConfirm || isReportConfirm) {
                            var actionPtr = null;
                            try { actionPtr = this.context.rsp.add(0x30).readPointer(); } catch (eStk) {}
                            if (!actionPtr || actionPtr.isNull()) {
                                try { actionPtr = args[5]; } catch (eA5) {}
                            }
                            var invoked = _invokeUnityBoolActionTrue(actionPtr);
                            if (invoked || isMirrorConfirm) {
                                this.autoConfirm = true;
                                if (isMirrorConfirm) {
                                    _nativeMirrorTurboStats.suppressedConfirms += 1;
                                    _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, Date.now() + 800);
                                }
                                if (invoked && isReportConfirm) {
                                    _autoReportConfirmCount += 1;
                                    send({
                                        type: "auto_report_confirmed",
                                        source: "show_confirm_hook",
                                        title: title,
                                        message: msg
                                    });
                                } else if (invoked && isPartyConfirm) {
                                    send({
                                        type: "auto_party_confirmed",
                                        source: "show_confirm_hook",
                                        title: title,
                                        message: msg
                                    });
                                }
                            }
                        }
                    } catch (eConfirm) {}
                },
                onLeave: function(retval) {
                    if (this.autoConfirm) {
                        retval.replace(ptr(0));
                    }
                }
            });
        }
    }
} catch (eHSCFH) {}

// =========================================================================
// REA HOOK: MHelperUI.NIONHKAAMJL (ShowConfirm by ID - RVA <RVA>)
// Tự động xác nhận Party ngay khi nhận được gói tin mời tổ đội
// =========================================================================
// =========================================================================
// REA HOOK: MHelperUI.NIONHKAAMJL (ShowDialog Generic - no id param)
// Bắt trực tiếp popup cổng Gate ("Teleport" / "Do you want to teleport?")
// do LocalCharacterBody.HFCPGMGJDEJ kích hoạt và tự động xác nhận YES (0ms)
// =========================================================================
var mhelperShowDialogGenericHook = null;
try {
    var offGateDlgGen = off('__MHELPER_SHOW_DIALOG_GENERIC__');
    if (!offGateDlgGen.isNull()) {
        mhelperShowDialogGenericHook = Interceptor.attach(baseAddr.add(offGateDlgGen), {
            onEnter: function(args) {
                this.isGateTeleport = false;
                this.gateTitle = "";
                this.gateMsg = "";
                if (shuttingDown || !autoGateConfirmEnabled) return;
                try {
                    var title = readIl2CppStrSafe(args[1]);
                    var msg = readIl2CppStrSafe(args[2]);
                    if (isGateTeleportDialog(title, msg)) {
                        this.isGateTeleport = true;
                        this.gateTitle = title;
                        this.gateMsg = msg;
                    }
                } catch (eGDE) {}
            },
            onLeave: function(retval) {
                if (!this.isGateTeleport || shuttingDown) return;
                if (!retval || retval.isNull()) return;
                var nowMs = Date.now();
                if (nowMs - lastAutoGateConfirmMs < 200) return;
                lastAutoGateConfirmMs = nowMs;
                try {
                    // Trì hoãn 300ms trên MainThread để nhân vật thoát trạng thái IsTeleporting sau /move
                    pendingGateDialogConfirm = {
                        dlg: retval,
                        readyAtMs: nowMs + 300,
                        title: this.gateTitle,
                        message: this.gateMsg,
                        source: "dialog_generic_hook"
                    };
                } catch (eGDL) {}
            }
        });
    }
} catch (eMGDH) {}

var mhelperShowDialogIdHook = null;
try {
    var offPartyDlgId = off('__MHELPER_SHOW_DIALOG_ID__');
    if (!offPartyDlgId.isNull()) {
        mhelperShowDialogIdHook = Interceptor.attach(baseAddr.add(offPartyDlgId), {
            onEnter: function(args) {
                this.isParty = false;
                this.isGateTeleport = false;
                this.actionInvoked = false;
                if (shuttingDown || (!autoConfirmPartyEnabled && !autoGateConfirmEnabled)) return;
                if (autoGateConfirmEnabled) {
                    try {
                        var gTitle = readIl2CppStrSafe(args[2]);
                        var gMsg = readIl2CppStrSafe(args[3]);
                        if (isGateTeleportDialog(gTitle, gMsg)) {
                            this.isGateTeleport = true;
                            this.gateTitle = gTitle;
                            this.gateMsg = gMsg;
                        }
                    } catch (eGIdE) {}
                }
                if (!autoConfirmPartyEnabled) return;
                try {
                    var title = "";
                    if (args[2] && !args[2].isNull()) {
                        var tLen = args[2].add(0x10).readS32();
                        if (tLen > 0 && tLen < 128) title = args[2].add(0x14).readUtf16String(tLen);
                    }
                    var msg = "";
                    if (args[3] && !args[3].isNull()) {
                        var mLen = args[3].add(0x10).readS32();
                        if (mLen > 0 && mLen < 256) msg = args[3].add(0x14).readUtf16String(mLen);
                    }
                    var lowT = title.toLowerCase();
                    var lowM = msg.toLowerCase();
                    if (lowT.indexOf("party") !== -1 || lowM.indexOf("party") !== -1 ||
                        lowT.indexOf("tổ đội") !== -1 || lowM.indexOf("tổ đội") !== -1 ||
                        lowT.indexOf("to doi") !== -1 || lowM.indexOf("to doi") !== -1 ||
                        lowT.indexOf("nhóm") !== -1 || lowM.indexOf("nhóm") !== -1 ||
                        lowT.indexOf("pt") !== -1) {
                        this.isParty = true;
                        this.title = title;
                        this.message = msg;

                        var actionPtr = null;
                        try { actionPtr = this.context.rsp.add(0x30).readPointer(); } catch (eStk) {}
                        if (!actionPtr || actionPtr.isNull()) {
                            try { actionPtr = args[5]; } catch (eA5) {}
                        }
                        if (actionPtr && !actionPtr.isNull()) {
                            if (_invokeUnityBoolActionTrue(actionPtr)) {
                                this.actionInvoked = true;
                                send({
                                    type: "auto_party_confirmed",
                                    source: "dialog_id_hook",
                                    title: title,
                                    message: msg
                                });
                            }
                        }
                    }
                } catch (ePCheck) {}
            },
            onLeave: function(retval) {
                if (this.isGateTeleport && !shuttingDown && retval && !retval.isNull()) {
                    var nowGMs = Date.now();
                    if (nowGMs - lastAutoGateConfirmMs >= 200) {
                        lastAutoGateConfirmMs = nowGMs;
                        try {
                            pendingGateDialogConfirm = {
                                dlg: retval,
                                readyAtMs: nowGMs + 300,
                                title: this.gateTitle || "",
                                message: this.gateMsg || "",
                                source: "dialog_id_hook"
                            };
                        } catch (eGIdL) {}
                    }
                    return;
                }
                if (!this.isParty || !retval || retval.isNull()) return;
                try {
                    var dlg = retval;
                    var yesBtn = dlg.add(ptr('0x48')).readPointer();
                    if (!yesBtn.isNull()) {
                        if (nativeButtonPress !== null) {
                            try { nativeButtonPress(yesBtn, ptr(0)); } catch (eBP) {}
                        }
                        var invokeFn = nativeUnityEvent_Invoke || nativeUnityEventInvoke;
                        if (invokeFn !== null) {
                            try {
                                var onClick = yesBtn.add(ptr('0x100')).readPointer();
                                if (!onClick.isNull()) invokeFn(onClick, ptr(0));
                            } catch (eUE) {}
                        }
                    }
                    if (!this.actionInvoked) {
                        send({
                            type: "auto_party_confirmed",
                            source: "dialog_id_hook_btn",
                            title: this.title,
                            message: this.message
                        });
                    }
                } catch (ePLeave) {}
            }
        });
    }
} catch (eHPDHook) {}

rpc.exports = {
    setAutoConfirmParty: function(enabled) {
        autoConfirmPartyEnabled = !!enabled;
        return true;
    },

    isAutoConfirmPartyEnabled: function() {
        return autoConfirmPartyEnabled;
    },

    setAutoGateConfirm: function(enabled) {
        autoGateConfirmEnabled = !!enabled;
        return JSON.stringify({ ok: true, enabled: autoGateConfirmEnabled, count: autoGateConfirmCount });
    },

    getAutoGateConfirmStatus: function() {
        return JSON.stringify({
            ok: true,
            enabled: autoGateConfirmEnabled,
            count: autoGateConfirmCount,
            last: lastAutoGateConfirmInfo
        });
    },

    getPlayerInfo: function() {
        return readPlayerInfoSnapshot(true);
    },

    invitePartyByKey: function(key) {
        try {
            ensureThreadAttached();
            lastPartyInviteResult = { done: false, ok: false, err: null, key: parseInt(key) };
            pendingPartyInviteKey = parseInt(key);
            return true;
        } catch (e) {
            return false;
        }
    },

    getPartyInviteResult: function() {
        return JSON.stringify(lastPartyInviteResult);
    },

    findNearbyPlayerKey: function(name) {
        return findTargetKeyByName(name);
    },

    invitePartyByName: function(name) {
        try {
            ensureThreadAttached();
            var key = findTargetKeyByName(name);
            if (key === -1) {
                return JSON.stringify({ ok: false, error: "player_not_found_in_viewport", name: name });
            }
            lastPartyInviteResult = { done: false, ok: false, err: null, key: key };
            pendingPartyInviteKey = key;
            return JSON.stringify({ ok: true, key: key, name: name });
        } catch (e) {
            return JSON.stringify({ ok: false, error: String(e), name: name });
        }
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
            // Đưa vào hàng đợi để thực thi 100% trên Unity Main Thread trong vòng lặp Update
            // Tránh crash ntdll 0xc0000005 khi gọi IL2CPP từ external RPC thread
            pendingCommand = cmd;
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
                    var tCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
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

                // Cấu hình cờ Auto Move chuẩn Type 0 để vòng lặp Update của game khởi tạo BodyActivity (<RVA>)
                p.add(off('__AUTO_MOVE_DEST__')).writePointer(destCoord);
                p.add(off('__AUTO_MOVE_TYPE__')).writeS32(0);
                p.add(off('__AUTO_MOVE_HELPER__')).writeU8(helper ? 1 : 0);
                p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);

                // Đưa bước di chuyển khởi hành vào hàng đợi Unity Main Thread Hook để thực thi an toàn tuyệt đối, tránh crash
                pendingMoveTarget = { x: parseInt(x), y: parseInt(y), helper: Boolean(helper), autoMove: true };
                return true;
            } else {
                pendingMoveTarget = { x: parseInt(x), y: parseInt(y), helper: Boolean(helper), autoMove: true };
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

    getPlayerZen: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return -1;
            var inv = p.add(ptr('0x1B0')).readPointer();
            if (inv.isNull()) return -1;
            var zen = inv.add(ptr('0x58')).readS32();
            return zen >= 0 ? zen : 0;
        } catch (e) {
            return -1;
        }
    },

    getPlayerRuud: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return 0;
            var inv = p.add(ptr('0x1B0')).readPointer();
            if (inv.isNull()) return 0;
            var ruud = inv.add(ptr('0x5C')).readU32();
            return ruud >= 0 ? ruud : 0;
        } catch (e) {
            return 0;
        }
    },

    getMossRollStatus: function() {
        try {
            ensureThreadAttached();
            if (nativeGetGameUI === null) return { ready: false, isOpen: false, hasReward: false, itemCount: 0, isLoading: false };
            var gui = nativeGetGameUI();
            if (gui.isNull()) return { ready: false, isOpen: false, hasReward: false, itemCount: 0, isLoading: false };
            var mossOff = off('__UI_MOSS_WINDOW__');
            var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
            if (mossWin.isNull()) return { ready: false, isOpen: false, hasReward: false, itemCount: 0, isLoading: false };

            var win = mossWin.add(0x20).readPointer();
            var isOpen = (!win.isNull() && win.add(0x48).readU8() === 1);

            var rewStorage = mossWin.add(ptr('0x70')).readPointer();
            var itemCount = 0;
            if (!rewStorage.isNull()) {
                try { itemCount = rewStorage.add(ptr('0x4C')).readS32(); } catch (eIC) {}
            }

            var timer = 0.0;
            try { timer = mossWin.add(ptr('0x98')).readFloat(); } catch (eT) {}
            var isLoading = (timer > 0.0);

            return {
                ready: true,
                isOpen: isOpen,
                hasReward: itemCount > 0,
                itemCount: itemCount,
                isLoading: isLoading
            };
        } catch (e) {
            return { ready: false, isOpen: false, hasReward: false, itemCount: 0, isLoading: false, error: e.toString() };
        }
    },

    isMossOpen: function() {
        try {
            ensureThreadAttached();
            if (nativeGetGameUI === null) return false;
            var gui = nativeGetGameUI();
            if (gui.isNull()) return false;
            var mossOff = off('__UI_MOSS_WINDOW__');
            var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
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
            var mossOff = off('__UI_MOSS_WINDOW__');
            var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
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
            var cat = parseInt(categoryId || 0);
            // Non-blocking: đẩy sang Unity MainThread (Game.Update / GameUI.Update), KHÔNG Thread.sleep() giữ Frida lock!
            pendingMossRollCategory = cat;
            return true;
        } catch (eMR) {
            return false;
        }
    },

    closeMoss: function() {
        try {
            pendingMossOpenCategory = null;
            pendingMossSelectAfterServerOpen = null;
            pendingMossClose = true;
            return true;
        } catch (eCM) {
            return false;
        }
    },

    openMoss: function(categoryId) {
        try {
            var cat = parseInt(categoryId || 0);
            var mossWin = getMossWindowPtr(null);
            if (!mossWin.isNull() && isMossWindowServerReady(mossWin)) {
                pendingMossOpenCategory = cat;
                return true;
            }
            var npc = findMossNpc();
            if (npc && !npc.ptr.isNull()) {
                pendingMossOpenCategory = null;
                pendingMossSelectAfterServerOpen = { cat: cat, untilMs: Date.now() + 4500 };
                pendingMossInteractPtr = npc.ptr;
                return true;
            }
            return false;
        } catch (eMO) {
            return false;
        }
    },

    resetMossUI: function(categoryId) {
        try {
            var cat = parseInt(categoryId || 0);
            pendingMossResetCategory = cat;
            return true;
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
            ensureDropAllowed(false);
            _pendingUnlockInventory = true;
            return true;
        } catch (e) {
            return false;
        }
    },

    unlockCharacterAndInventory: function() {
        try {
            ensureDropAllowed(false);
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    p.add(off('__AUTO_MOVE_WORKING__')).writeU8(0);
                }
            } catch (eAM) {}
            _pendingUnlockCharResetAutoMove = true;
            _pendingUnlockInventory = true;
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
                    var invWin = invOff.isNull() ? gui.add(ptr('0x190')).readPointer() : gui.add(invOff).readPointer();
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

                    // 3. Phục hồi RollButton và ẩn MWindow (KHÔNG tắt GameObject của MMossMerchantWindow để có thể mở lại)
                    var mossOff = off('__UI_MOSS_WINDOW__');
                    var mossWin = mossOff.isNull() ? gui.add(ptr('0x1D0')).readPointer() : gui.add(mossOff).readPointer();
                    if (!mossWin.isNull()) {
                        ensureMossRollButtonActive(mossWin, true);
                        var mWin = mossWin.add(0x20).readPointer();
                        if (!mWin.isNull()) {
                            if (nativeWindowHide !== null) {
                                try { nativeWindowHide(mWin, ptr(0)); } catch (eMWH) {}
                            }
                            mWin.add(0x48).writeU8(0);
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
                skin: npc.skin,
                classId: npc.classId,
                klass: npc.klass,
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
            var cat = parseInt(categoryId || 0);
            var forceReopen = (arguments.length > 1) && (arguments[1] === true || arguments[1] === 1 || arguments[1] === "true");
            var npc = findMossNpc();
            if (!npc) {
                return { success: false, error: "NPC_NOT_FOUND" };
            }

            // Đẩy tương tác NPC Moss thật sang Unity MainThread (Game.Update / GameUI.Update).
            // TUYỆT ĐỐI KHÔNG đặt pendingMossOpenCategory cưỡng chế mở cửa sổ cục bộ trước khi Server phản hồi C2:30!
            // Thay vào đó đăng ký pendingMossSelectAfterServerOpen để tự động chọn đúng tab ngay khi Server mở bảng thật.
            pendingMossForceReopen = forceReopen;
            pendingMossOpenCategory = null;
            pendingMossSelectAfterServerOpen = { cat: cat, untilMs: Date.now() + 4500 };
            pendingMossInteractPtr = npc.ptr;

            return {
                success: true,
                index: npc.index,
                skin: npc.skin,
                classId: npc.classId,
                klass: npc.klass,
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

    isMerchantOpen: function() {
        return isMerchantWindowOpen();
    },

    interactMerchantNpc: function() {
        try {
            var npc = findMerchantNpc();
            if (!npc) {
                return { success: false, error: "MERCHANT_NOT_FOUND" };
            }

            // Đẩy tương tác NPC thương nhân sang Unity MainThread (Game.Update / GameUI.Update)
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

    getQuestState: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) {
                return JSON.stringify({ ok: false, error: "player_null" });
            }
            var snap = readPlayerInfoSnapshot(true) || {};
            var zen = 0;
            try {
                var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                if (!inv.isNull()) {
                    var rawZen = inv.add(ptr('0x58')).readS32();
                    zen = rawZen >= 0 ? rawZen : 0;
                }
            } catch (eZ) {}

            var states = {};
            var questCount = 0;
            var currentData = -1;
            var monsterKills = {};
            var qm = getQuestManagerPtr();
            if (qm && !qm.isNull()) {
                try { questCount = qm.add(0x28).readS32(); } catch (eQC) {}
                try { currentData = qm.add(0x2C).readS32(); } catch (eCD) {}
                try {
                    var stateArr = qm.add(0x20).readPointer();
                    if (!stateArr.isNull()) {
                        var arrLen = stateArr.add(0x18).readS32();
                        var maxQ = Math.min(32, Math.max(0, arrLen * 4));
                        for (var qi = 0; qi < maxQ; qi++) {
                            var bIdx = qi >> 2;
                            var shift = (qi & 3) * 2;
                            var bVal = stateArr.add(0x20 + bIdx).readU8();
                            states[String(qi)] = (bVal >> shift) & 3;
                        }
                    }
                } catch (eSA) {}
                try {
                    var mkDict = qm.add(0x30).readPointer();
                    if (!mkDict.isNull()) {
                        var entries = mkDict.add(0x18).readPointer();
                        var count = mkDict.add(0x20).readS32();
                        if (!entries.isNull() && count > 0 && count <= 128) {
                            for (var ei = 0; ei < count; ei++) {
                                var eAddr = entries.add(0x20 + ei * 16);
                                var hc = eAddr.readS32();
                                if (hc < 0) continue;
                                var mKey = eAddr.add(8).readS32();
                                var mVal = eAddr.add(12).readS32();
                                if (mKey > 0) {
                                    monsterKills[String(mKey)] = mVal;
                                }
                            }
                        }
                    }
                } catch (eMK) {}
            }

            var QUEST_ITEM_IDS = { 7191: 1, 7192: 1, 7193: 1, 7194: 1, 7233: 1, 7234: 1, 7235: 1, 7236: 1 };
            var INV_Q_KEYS = ["scroll of emperor", "broken sword", "soul of wizard", "soul of prophet", "tear of elf", "abyssal eye", "ring of honor", "dark stone", "flame of death", "horn of hell", "feather of"];
            var questItems = [];
            try {
                var inv2 = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                if (!inv2.isNull()) {
                    var itemsArr = inv2.add(off('__INVENTORY_ITEMS__')).readPointer();
                    if (!itemsArr.isNull()) {
                        var maxSlot = 204;
                        try {
                            var aLen = itemsArr.add(0x18).readS32();
                            if (aLen > 12 && aLen < maxSlot) maxSlot = aLen;
                        } catch (eAL) {}
                        for (var s = 12; s < maxSlot; s++) {
                            var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                            if (!itemPtr.isNull()) {
                                var idx = readItemIndex(itemPtr);
                                var itName = "";
                                try { itName = getItemName(itemPtr) || ""; } catch (eGN) {}
                                var isQ = !!QUEST_ITEM_IDS[idx];
                                if (!isQ && itName) {
                                    var lowN = itName.toLowerCase();
                                    for (var qk = 0; qk < INV_Q_KEYS.length; qk++) {
                                        if (lowN.indexOf(INV_Q_KEYS[qk]) !== -1) { isQ = true; break; }
                                    }
                                }
                                if (isQ) {
                                    var lv = 0;
                                    try { lv = itemPtr.add(0x10).readS32(); } catch (eLv) {}
                                    questItems.push({ slot: s, id: idx, level: lv, name: itName });
                                }
                            }
                        }
                    }
                }
            } catch (eQI) {}

            // Dong bo & hop nhat tien do giet quai ghi nhan tu System Notice (C1:0D -> Dark Elf 1/1, Balram/DS/Soram 20/20)
            try {
                var curCharN = String(snap.name || "");
                if (curCharN && questNoticeCharName && curCharN !== questNoticeCharName) {
                    questNoticeKills = {};
                    questNoticeReq = {};
                    lastQuestNoticeText = "";
                }
                if (curCharN) questNoticeCharName = curCharN;

                if (states["5"] === 2) {
                    delete questNoticeKills["409"];
                    delete questNoticeKills["410"];
                    delete questNoticeKills["411"];
                } else {
                    var bIds = ["409", "410", "411"];
                    for (var bi = 0; bi < bIds.length; bi++) {
                        var bKey = bIds[bi];
                        var nv = questNoticeKills[bKey] || 0;
                        if (nv > (monsterKills[bKey] || 0)) monsterKills[bKey] = nv;
                    }
                }

                if (states["6"] === 2) {
                    delete questNoticeKills["412"];
                } else {
                    var deVal = questNoticeKills["412"] || 0;
                    if (deVal > (monsterKills["412"] || 0)) monsterKills["412"] = deVal;
                }
            } catch (eMergeQ) {}

            return JSON.stringify({
                ok: true,
                name: snap.name || "",
                level: snap.level || 0,
                class_id: snap.classId !== undefined ? snap.classId : -1,
                change_up: snap.changeUp !== undefined ? snap.changeUp : 0,
                zen: zen,
                map_id: snap.mapId !== undefined ? snap.mapId : -1,
                x: snap.x || 0,
                y: snap.y || 0,
                quest_count: questCount,
                current_data: currentData,
                states: states,
                monster_kills: monsterKills,
                notice_kills: questNoticeKills,
                last_quest_notice: lastQuestNoticeText,
                quest_items: questItems
            });
        } catch (eQS) {
            return JSON.stringify({ ok: false, error: eQS.toString() });
        }
    },

    findNpcByFilter: function(skinId, nameSub) {
        try {
            ensureThreadAttached();
            var wantSkin = parseInt(skinId);
            var wantName = String(nameSub || "").toLowerCase();
            var localPlayer = getPlayerPtr();
            var px = -1, py = -1;
            if (!localPlayer.isNull()) {
                try {
                    var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                    if (!pCoord.isNull()) {
                        px = pCoord.add(0x10).readS32();
                        py = pCoord.add(0x14).readS32();
                    }
                } catch (ePC) {}
            }
            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ found: false });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ found: false });
            var gameInstance = staticFields.add(ptr('0x8')).readPointer();
            if (gameInstance.isNull()) return JSON.stringify({ found: false });
            var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
            if (viewport.isNull()) return JSON.stringify({ found: false });
            var objDict = viewport.add(ptr('0x20')).readPointer();
            if (objDict.isNull()) return JSON.stringify({ found: false });
            var entries = objDict.add(ptr('0x18')).readPointer();
            var count = objDict.add(ptr('0x20')).readS32();
            if (entries.isNull() || count <= 0 || count > 600) return JSON.stringify({ found: false });

            var best = null;
            var bestDist = 999999;
            for (var i = 0; i < count; i++) {
                var entryAddr = entries.add(0x20 + i * 24);
                if (entryAddr.readS32() < 0) continue;
                var val = entryAddr.add(16).readPointer();
                if (val.isNull()) continue;
                var body = ptr(0);
                try {
                    var vk = val.readPointer();
                    if (vk.isNull()) continue;
                    var vkn = vk.add(0x10).readPointer().readUtf8String() || "";
                    if (vkn.indexOf("ViewportBody") === -1) continue;
                    body = val.add(0x18).readPointer();
                } catch (eVB) { continue; }
                if (body.isNull() || (!localPlayer.isNull() && body.equals(localPlayer))) continue;

                var bSkin = -1, bClass = -1, bIdx = -1;
                try { bIdx = body.add(0x20).readS32(); } catch (e1) {}
                try { bClass = body.add(0x34).readS32(); } catch (e2) {}
                try { bSkin = body.add(0x60).readS32(); } catch (e3) {}

                var bName = "";
                try {
                    var np = body.add(off('__PLAYER_NAME__')).readPointer();
                    if (!np.isNull()) {
                        var nl = np.add(0x10).readS32();
                        if (nl > 0 && nl < 64) bName = np.add(0x14).readUtf16String(nl);
                    }
                } catch (e4) {}

                var matchSkin = (wantSkin >= 0 && (bSkin === wantSkin || bClass === wantSkin));
                var matchName = (wantName.length > 0 && bName.toLowerCase().indexOf(wantName) !== -1);
                if (!matchSkin && !matchName) continue;

                var nx = 0, ny = 0;
                try {
                    var nc = body.add(off('__PLAYER_COORD__')).readPointer();
                    if (!nc.isNull()) {
                        nx = nc.add(0x10).readS32();
                        ny = nc.add(0x14).readS32();
                    }
                } catch (e5) {}
                var dist = (px >= 0 && py >= 0) ? Math.sqrt((nx - px) * (nx - px) + (ny - py) * (ny - py)) : 0;
                if (dist < bestDist) {
                    bestDist = dist;
                    best = {
                        found: true,
                        ptr: body.toString(),
                        index: bIdx,
                        skin: bSkin,
                        class_id: bClass,
                        name: bName,
                        x: nx,
                        y: ny,
                        dist: Math.round(dist * 10) / 10
                    };
                }
            }
            return JSON.stringify(best || { found: false });
        } catch (eFN) {
            return JSON.stringify({ found: false, error: eFN.toString() });
        }
    },

    talkToNpcByPtr: function(ptrStr) {
        try {
            if (!ptrStr || ptrStr === "0" || ptrStr === "0x0") return JSON.stringify({ ok: false, error: "invalid_ptr" });
            pendingQuestNpcTalkPtr = ptr(ptrStr);
            return JSON.stringify({ ok: true });
        } catch (eT) {
            return JSON.stringify({ ok: false, error: eT.toString() });
        }
    },

    getQuestNpcWindowState: function() {
        try {
            ensureThreadAttached();
            var isOpen = false;
            var hasNextBtn = false;
            var currentData = -1;
            var qm = getQuestManagerPtr();
            if (qm && !qm.isNull()) {
                try { currentData = qm.add(0x2C).readS32(); } catch (eCD) {}
            }
            if (nativeGetGameUI !== null) {
                var gui = nativeGetGameUI();
                if (gui && !gui.isNull()) {
                    var qwOff = off('__UI_QUEST_NPC_WINDOW__');
                    if (!qwOff.isNull()) {
                        var qWin = gui.add(qwOff).readPointer();
                        if (qWin && !qWin.isNull()) {
                            var mWin = qWin.add(0x20).readPointer();
                            if (mWin && !mWin.isNull()) {
                                isOpen = (mWin.add(0x48).readU8() === 1);
                            }
                            var nb = qWin.add(0x40).readPointer();
                            hasNextBtn = (nb && !nb.isNull());
                        }
                    }
                }
            }
            return JSON.stringify({ ok: true, isOpen: isOpen, hasNextBtn: hasNextBtn, currentData: currentData });
        } catch (eQW) {
            return JSON.stringify({ ok: false, isOpen: false, hasNextBtn: false, currentData: -1, error: eQW.toString() });
        }
    },

    clickQuestNpcNext: function(questIndex) {
        try {
            lastQuestClickDebug = { done: false, ok: false, method: "", qWinOpen: false, nextBtnFound: false, currentData: -1, error: "" };
            pendingQuestNextAction = { index: parseInt(questIndex !== undefined && questIndex !== null ? questIndex : -1) };
            for (var w = 0; w < 20; w++) {
                if (lastQuestClickDebug.done) break;
                Thread.sleep(0.02);
            }
            return JSON.stringify(lastQuestClickDebug);
        } catch (eC) {
            return JSON.stringify({ done: true, ok: false, method: "", error: eC.toString() });
        }
    },

    sendQuestState: function(questIndex, flag) {
        try {
            pendingQuestStateAction = { index: parseInt(questIndex), flag: !!flag };
            return JSON.stringify({ ok: true, index: parseInt(questIndex) });
        } catch (eS) {
            return JSON.stringify({ ok: false, error: eS.toString() });
        }
    },

    enterQuestDungeon: function(dungeonType) {
        try {
            var dt = String(dungeonType || "").toLowerCase();
            if (dt !== "barracks" && dt !== "refuge") {
                return JSON.stringify({ ok: false, error: "invalid_dungeon_type" });
            }
            pendingQuestDungeonAction = dt;
            return JSON.stringify({ ok: true, dungeon: dt });
        } catch (eD) {
            return JSON.stringify({ ok: false, error: eD.toString() });
        }
    },

    dumpWorldGates: function() {
        try {
            ensureThreadAttached();
            var dataInst = getDataInstancePtr();
            if (!dataInst || dataInst.isNull()) {
                return JSON.stringify({ ok: false, error: "data_instance_null", gates: [], moves: [] });
            }
            var tableWorld = dataInst.add(0x90).readPointer();
            if (!tableWorld || tableWorld.isNull()) {
                return JSON.stringify({ ok: false, error: "table_world_null", gates: [], moves: [] });
            }

            var gates = [];
            try {
                var gateCont = tableWorld.add(0x30).readPointer();
                if (gateCont && !gateCont.isNull()) {
                    var gList = gateCont.add(0x10).readPointer();
                    if (gList && !gList.isNull()) {
                        var gCount = gList.add(0x18).readS32();
                        var gArr = gList.add(0x10).readPointer();
                        if (gArr && !gArr.isNull() && gCount > 0 && gCount < 4096) {
                            for (var gi = 0; gi < gCount; gi++) {
                                var gPtr = gArr.add(0x20 + gi * 8).readPointer();
                                var gObj = readGateEntryObj(gPtr);
                                if (gObj !== null) gates.push(gObj);
                            }
                        }
                    }
                }
            } catch (eGL) {}

            var moves = [];
            try {
                var moveCont = tableWorld.add(0x28).readPointer();
                if (moveCont && !moveCont.isNull()) {
                    var mList = moveCont.add(0x10).readPointer();
                    if (mList && !mList.isNull()) {
                        var mCount = mList.add(0x18).readS32();
                        var mArr = mList.add(0x10).readPointer();
                        if (mArr && !mArr.isNull() && mCount > 0 && mCount < 2048) {
                            for (var mi = 0; mi < mCount; mi++) {
                                var mPtr = mArr.add(0x20 + mi * 8).readPointer();
                                var mObj = readMoveEntryObj(mPtr);
                                if (mObj !== null) moves.push(mObj);
                            }
                        }
                    }
                }
            } catch (eML) {}

            var curMap = -1, curX = -1, curY = -1;
            try {
                if (getWorldNative !== null) {
                    var w = getWorldNative();
                    if (w && !w.isNull()) curMap = w.add(0x20).readS32();
                }
            } catch (eWM) {}
            try {
                var lp = getPlayerPtr();
                if (lp && !lp.isNull()) {
                    var c = lp.add(0x68).readPointer();
                    if (c && !c.isNull()) {
                        curX = c.add(0x10).readS32();
                        curY = c.add(0x14).readS32();
                    }
                }
            } catch (eLP) {}

            return JSON.stringify({
                ok: true,
                currentMapId: curMap,
                currentX: curX,
                currentY: curY,
                gateCount: gates.length,
                moveCount: moves.length,
                gates: gates,
                moves: moves
            });
        } catch (eDW) {
            return JSON.stringify({ ok: false, error: eDW.toString(), gates: [], moves: [] });
        }
    },

    getCurrentTileGate: function() {
        try {
            ensureThreadAttached();
            var lp = getPlayerPtr();
            if (!lp || lp.isNull()) return JSON.stringify({ ok: false, found: false, error: "no_player" });
            var c = lp.add(0x68).readPointer();
            if (!c || c.isNull()) return JSON.stringify({ ok: false, found: false, error: "no_coord" });
            var px = c.add(0x10).readS32();
            var py = c.add(0x14).readS32();
            if (px < 0 || px > 255 || py < 0 || py > 255) {
                return JSON.stringify({ ok: true, found: false, x: px, y: py });
            }
            var w = (getWorldNative !== null) ? getWorldNative() : ptr(0);
            if (!w || w.isNull()) return JSON.stringify({ ok: false, found: false, error: "no_world" });
            var mapId = w.add(0x20).readS32();
            var gates2D = w.add(0x218).readPointer();
            if (!gates2D || gates2D.isNull()) {
                return JSON.stringify({ ok: true, found: false, mapId: mapId, x: px, y: py });
            }
            var bounds = gates2D.add(0x10).readPointer();
            var dim0 = bounds.readU32();
            var dim1 = bounds.add(0x10).readU32();
            if (px >= dim0 || py >= dim1) {
                return JSON.stringify({ ok: true, found: false, mapId: mapId, x: px, y: py });
            }
            var gPtr = gates2D.add(0x20 + (px * dim1 + py) * 8).readPointer();
            if (!gPtr || gPtr.isNull()) {
                return JSON.stringify({ ok: true, found: false, mapId: mapId, x: px, y: py });
            }
            var gObj = readGateEntryObj(gPtr);
            return JSON.stringify({ ok: true, found: gObj !== null, mapId: mapId, x: px, y: py, gate: gObj });
        } catch (eTG) {
            return JSON.stringify({ ok: false, found: false, error: eTG.toString() });
        }
    },

    enterGate: function(gateId, x, y) {
        try {
            var gid = parseInt(gateId);
            if (isNaN(gid) || gid < 0 || gid > 65535) {
                return JSON.stringify({ ok: false, error: "invalid_gate_id" });
            }
            var gx = (x !== undefined && x !== null) ? parseInt(x) : -1;
            var gy = (y !== undefined && y !== null) ? parseInt(y) : -1;
            lastGateEnterResult = { done: false, ok: false, gateId: gid, x: gx, y: gy, ret: false, error: "" };
            pendingGateEnterAction = { gateId: gid, x: gx, y: gy };
            return JSON.stringify({ ok: true, queued: true, gateId: gid, x: gx, y: gy });
        } catch (eEG) {
            return JSON.stringify({ ok: false, error: eEG.toString() });
        }
    },

    getLastGateEnterResult: function() {
        try {
            return JSON.stringify(lastGateEnterResult);
        } catch (eR) {
            return JSON.stringify({ done: false, ok: false, error: eR.toString() });
        }
    },

    enterAcheronNpc: function(zone) {
        try {
            var z = (zone !== undefined && zone !== null) ? parseInt(zone) : -1;
            pendingArkaEnterAction = { zone: z };
            return JSON.stringify({ ok: true, queued: true, zone: z });
        } catch (eEA) {
            return JSON.stringify({ ok: false, error: eEA.toString() });
        }
    },

    sendWarp8E: function(warpType, param, extra) {
        try {
            pendingWarp8EAction = {
                type: parseInt(warpType || 0),
                param: parseInt(param || 0),
                extra: parseInt(extra || 0)
            };
            return JSON.stringify({ ok: true, queued: true });
        } catch (eW) {
            return JSON.stringify({ ok: false, error: eW.toString() });
        }
    },

    closeQuestWindow: function() {
        try {
            pendingQuestWindowClose = true;
            return true;
        } catch (eC) {
            return false;
        }
    },

    findGuardNpc: function() {
        try {
            ensureThreadAttached();
            var localPlayer = getPlayerPtr();
            var px = -1, py = -1;
            if (!localPlayer.isNull()) {
                try {
                    var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                    if (!pCoord.isNull()) {
                        px = pCoord.add(0x10).readS32();
                        py = pCoord.add(0x14).readS32();
                    }
                } catch (ePC) {}
            }
            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ found: false });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ found: false });
            var gameInstance = staticFields.add(ptr('0x8')).readPointer();
            if (gameInstance.isNull()) return JSON.stringify({ found: false });
            var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
            if (viewport.isNull()) return JSON.stringify({ found: false });
            var objDict = viewport.add(ptr('0x20')).readPointer();
            if (objDict.isNull()) return JSON.stringify({ found: false });
            var entries = objDict.add(ptr('0x18')).readPointer();
            var count = objDict.add(ptr('0x20')).readS32();
            if (entries.isNull() || count <= 0 || count > 600) return JSON.stringify({ found: false });

            var EXCLUDE_GUARD_NAMES = ["imperial", "jerint", "siege", "guardsman", "guardian", "lugard"];
            var best = null;
            var bestDist = 999999;

            for (var i = 0; i < count; i++) {
                var entryAddr = entries.add(0x20 + i * 24);
                if (entryAddr.readS32() < 0) continue;
                var val = entryAddr.add(16).readPointer();
                if (val.isNull()) continue;
                var body = ptr(0);
                try {
                    var vkn = getIl2CppClassNameSafe(val);
                    if (vkn.indexOf("ViewportBody") === -1) continue;
                    body = val.add(0x18).readPointer();
                } catch (eVB) { continue; }
                if (body.isNull() || (!localPlayer.isNull() && body.equals(localPlayer))) continue;

                // Không bao giờ chọn người chơi khác (PlayerBody / CharacterBody)
                var bodyCls = "";
                try { bodyCls = getIl2CppClassNameSafe(body); } catch (eCls) {}
                if (bodyCls.indexOf("PlayerBody") !== -1 || bodyCls.indexOf("CharacterBody") !== -1) continue;

                var bSkin = -1, bClass = -1, bIdx = -1;
                try { bIdx = body.add(0x20).readS32(); } catch (e1) {}
                try { bClass = body.add(0x34).readS32(); } catch (e2) {}
                try { bSkin = body.add(0x60).readS32(); } catch (e3) {}

                var bName = "";
                try {
                    var np = body.add(off('__PLAYER_NAME__')).readPointer();
                    if (!np.isNull()) {
                        var nl = np.add(0x10).readS32();
                        if (nl > 0 && nl < 64) bName = np.add(0x14).readUtf16String(nl);
                    }
                } catch (e4) {}

                var lowN = bName.toLowerCase();
                var isExcluded = false;
                for (var ex = 0; ex < EXCLUDE_GUARD_NAMES.length; ex++) {
                    if (lowN.indexOf(EXCLUDE_GUARD_NAMES[ex]) !== -1) {
                        isExcluded = true;
                        break;
                    }
                }
                if (isExcluded) continue;

                var isGuardSkin = (bSkin === 247 || bSkin === 249 || bClass === 247 || bClass === 249);
                var isGuardName = (lowN.indexOf("guard") !== -1 || lowN.indexOf("guarda") !== -1 || lowN.indexOf("lính canh") !== -1);
                if (!isGuardSkin && !isGuardName) continue;

                var nx = 0, ny = 0;
                try {
                    var nc = body.add(off('__PLAYER_COORD__')).readPointer();
                    if (!nc.isNull()) {
                        nx = nc.add(0x10).readS32();
                        ny = nc.add(0x14).readS32();
                    }
                } catch (e5) {}
                var dist = (px >= 0 && py >= 0) ? Math.sqrt((nx - px) * (nx - px) + (ny - py) * (ny - py)) : 0;
                if (dist < bestDist) {
                    bestDist = dist;
                    best = {
                        found: true,
                        ptr: body.toString(),
                        index: bIdx,
                        skin: bSkin,
                        class_id: bClass,
                        name: bName || (bSkin === 247 ? "Crossbow Guard" : "Berdysh Guard"),
                        x: nx,
                        y: ny,
                        dist: Math.round(dist * 10) / 10
                    };
                }
            }
            return JSON.stringify(best || { found: false });
        } catch (eFG) {
            return JSON.stringify({ found: false, error: eFG.toString() });
        }
    },

    getPkReportStatus: function() {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (!p || p.isNull()) {
                return JSON.stringify({ ok: false, error: "no_player" });
            }
            var snap = readPlayerInfoSnapshot(true) || {};
            var hp = 0;
            var isDead = false;
            var deathCount = 0;
            var killCount = 0;
            var killerName = "";
            try { hp = p.add(0x3C).readU32(); } catch (e1) {}
            try { isDead = (p.add(0x5C).readU8() !== 0); } catch (e2) {}
            try { deathCount = p.add(0x504).readS32(); } catch (e3) {}
            try { killCount = p.add(0x520).readS32(); } catch (e4) {}
            try {
                var kPtr = p.add(0x528).readPointer();
                if (kPtr && !kPtr.isNull()) {
                    killerName = readIl2CppStrSafe(kPtr);
                }
            } catch (e5) {}

            var pkWindowOpen = false;
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (gui && !gui.isNull()) {
                        var pkWin = gui.add(0x2A8).readPointer();
                        if (pkWin && !pkWin.isNull()) {
                            var mWin = pkWin.add(0x20).readPointer();
                            if (mWin && !mWin.isNull()) {
                                pkWindowOpen = (mWin.add(0x48).readU8() === 1);
                            }
                        }
                    }
                }
            } catch (ePW) {}

            return JSON.stringify({
                ok: true,
                hp: hp,
                isDead: isDead,
                deathCount: deathCount,
                killCount: killCount,
                killerName: killerName,
                mapId: snap.mapId !== undefined ? snap.mapId : -1,
                x: snap.x || 0,
                y: snap.y || 0,
                pkWindowOpen: pkWindowOpen,
                autoReportConfirmCount: _autoReportConfirmCount
            });
        } catch (ePKS) {
            return JSON.stringify({ ok: false, error: ePKS.toString() });
        }
    },

    setAutoConfirmReport: function(enabled, killerName) {
        try {
            var en = !!enabled;
            _autoReportConfirmUntilMs = en ? (Date.now() + 10000) : 0;
            _autoReportKillerName = en ? String(killerName || "") : "";
            return JSON.stringify({
                ok: true,
                enabled: en,
                killerName: _autoReportKillerName,
                confirmCount: _autoReportConfirmCount
            });
        } catch (eACR) {
            return JSON.stringify({ ok: false, error: eACR.toString() });
        }
    },

    closePkWindow: function() {
        try {
            pendingPkWindowClose = true;
            return true;
        } catch (eCPW) {
            return false;
        }
    },

    pickupGroundQuestItems: function(targetIdsJson, maxRadius, targetLevel, targetKeywordsJson) {
        try {
            ensureThreadAttached();
            var radius = (maxRadius !== undefined && maxRadius !== null) ? parseFloat(maxRadius) : 14.0;
            var wantLevel = (targetLevel !== undefined && targetLevel !== null) ? parseInt(targetLevel) : -1;
            var targetIds = {};
            try {
                var arr = JSON.parse(String(targetIdsJson || "[]"));
                for (var k = 0; k < arr.length; k++) targetIds[parseInt(arr[k])] = true;
            } catch (eP) {}

            var targetKeywords = [];
            try {
                var kArr = JSON.parse(String(targetKeywordsJson || "[]"));
                for (var kk = 0; kk < kArr.length; kk++) {
                    var sKw = String(kArr[kk] || "").toLowerCase().trim();
                    if (sKw.length > 0) targetKeywords.push(sKw);
                }
            } catch (eK) {}

            var localPlayer = getPlayerPtr();
            var px = -1, py = -1;
            if (!localPlayer.isNull()) {
                try {
                    var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                    if (!pCoord.isNull()) {
                        px = pCoord.add(0x10).readS32();
                        py = pCoord.add(0x14).readS32();
                    }
                } catch (ePC) {}
            }

            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [] });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [] });
            var gameInstance = staticFields.add(ptr('0x8')).readPointer();
            if (gameInstance.isNull()) return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [] });
            var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
            if (viewport.isNull()) return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [] });
            var objDict = viewport.add(ptr('0x20')).readPointer();
            if (objDict.isNull()) return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [] });

            var entries = objDict.add(ptr('0x18')).readPointer();
            var count = objDict.add(ptr('0x20')).readS32();
            var foundItems = [];
            var queued = 0;
            var pickedIds = [];
            var prevDone = lastQuestPickupDone;

            for (var i = 0; i < count && i < 600; i++) {
                var entryAddr = entries.add(0x20 + i * 24);
                if (entryAddr.readS32() < 0) continue;
                var val = entryAddr.add(16).readPointer();
                if (val.isNull()) continue;
                var vk = val.readPointer();
                if (vk.isNull()) continue;
                var vkn = vk.add(0x10).readPointer().readUtf8String() || "";
                if (vkn.indexOf("ViewportItem") === -1) continue;

                var itemPtr = val.add(0x18).readPointer();
                if (itemPtr.isNull()) continue;
                var itemId = readItemIndex(itemPtr);
                var itemLv = 0;
                try { itemLv = itemPtr.add(0x10).readS32(); } catch (eIL) {}
                var itemName = "";
                try { itemName = getItemName(itemPtr) || ""; } catch (eIN) {}

                // Khớp CHÍNH XÁC vật phẩm nhiệm vụ đang cần (đúng ID + đúng Level, hoặc đúng từ khóa tên riêng của vật phẩm đó)
                var isMatch = false;
                if (targetKeywords.length > 0 && itemName) {
                    var low = itemName.toLowerCase();
                    for (var kw = 0; kw < targetKeywords.length; kw++) {
                        if (low.indexOf(targetKeywords[kw]) !== -1) {
                            isMatch = true;
                            break;
                        }
                    }
                }
                if (!isMatch && targetIds[itemId]) {
                    if (wantLevel < 0 || itemLv === wantLevel) {
                        isMatch = true;
                    }
                }
                if (!isMatch) continue;

                var ix = -1, iy = -1;
                var icPtr = val.add(0x28).readPointer();
                if (!icPtr.isNull()) {
                    ix = icPtr.add(0x10).readS32();
                    iy = icPtr.add(0x14).readS32();
                }
                var dist = (px >= 0 && py >= 0 && ix >= 0 && iy >= 0) ? Math.sqrt((ix - px) * (ix - px) + (iy - py) * (iy - py)) : 0;
                if (dist <= radius) {
                    var vIdx = val.add(0x10).readS32();
                    foundItems.push({
                        vIdx: vIdx,
                        id: itemId,
                        level: itemLv,
                        name: itemName,
                        x: ix,
                        y: iy,
                        dist: Math.round(dist * 10) / 10
                    });
                    if (vIdx >= 0 && dist <= 4.5) {
                        pendingQuestPickups.push({ vIdx: vIdx, itemPtr: itemPtr });
                        queued++;
                        pickedIds.push(itemId);
                    }
                }
            }

            if (queued > 0) {
                for (var w = 0; w < 12; w++) {
                    if (lastQuestPickupDone > prevDone) break;
                    Thread.sleep(0.02);
                }
            }
            var actualPicked = Math.max(0, lastQuestPickupDone - prevDone);
            return JSON.stringify({
                ok: true,
                pickedCount: actualPicked,
                queuedCount: queued,
                pickedIds: pickedIds,
                foundItems: foundItems,
                hasNativePick: (nativeUserInvPickItem !== null),
                pickError: lastQuestPickupErr
            });
        } catch (ePQ) {
            return JSON.stringify({ ok: false, pickedCount: 0, foundItems: [], error: ePQ.toString() });
        }
    },

    closeMerchantNpc: function() {
        try {
            ensureThreadAttached();
            pendingMerchantClose = true;
            for (var w = 0; w < 3; w++) {
                if (!pendingMerchantClose) break;
                Thread.sleep(0.02);
            }
            if (pendingMerchantClose) {
                pendingMerchantClose = false;
                performMerchantCloseNow();
            }
            return { success: true };
        } catch (e) {
            return { success: false, error: e.toString() };
        }
    },

    sellMossPlusItems: function(maxJunkLevel, ignoreTypeHeuristics, allowedSlots, mossCategory, cleanEquipmentTrash, sellExcellent) {
        try {
            ensureThreadAttached();
            var p = getPlayerPtr();
            if (p.isNull()) return JSON.stringify({ sold: 0, error: "no_player" });

            // Kiểm tra shop thương nhân có đang mở hay không
            if (!isMerchantWindowOpen()) {
                return JSON.stringify({ sold: 0, candidates: 0, error: "merchant_not_open" });
            }

            var invOff = off('__PLAYER_INVENTORY__');
            var inv = p.add(invOff).readPointer();
            if (inv.isNull()) return JSON.stringify({ sold: 0, error: "no_inventory" });

            var itemsOff = off('__INVENTORY_ITEMS__');
            var itemsArr = inv.add(itemsOff).readPointer();
            if (itemsArr.isNull()) return JSON.stringify({ sold: 0, error: "no_items_arr" });

            if (nativeGetGS === null && nativeUserInvSell === null) {
                return JSON.stringify({ sold: 0, error: "no_native_sell_fn" });
            }

            var maxLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 7;
            var ignoreType = Boolean(ignoreTypeHeuristics);
            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var cleanEquip = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true");
            var allowExc = (sellExcellent === 1 || sellExcellent === true || sellExcellent === "true");

            var allowedSet = null;
            if (allowedSlots) {
                try {
                    var aArr = (typeof allowedSlots === "string") ? JSON.parse(allowedSlots) : allowedSlots;
                    if (Array.isArray(aArr) && aArr.length > 0) {
                        allowedSet = {};
                        for (var ai = 0; ai < aArr.length; ai++) {
                            allowedSet[parseInt(aArr[ai])] = true;
                        }
                    }
                } catch (eAS) {}
            }

            var maxSlot = 204; // UserInventory.AnyInventoryEnd = 204 (không đụng Personal Shop 204..235)
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            var sold = 0;
            var soldItems = [];
            var candidatesCount = 0;

            // Tìm MerchantWindow để tự ẩn popup ExpensiveSellWindow (KHÔNG ghi đè mwObj+0x48 = 1!)
            var mWinPtr = ptr(0);
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var merchOff = off('__UI_MERCHANT_WINDOW__');
                        mWinPtr = merchOff.isNull() ? gui.add(ptr('0x1A0')).readPointer() : gui.add(merchOff).readPointer();
                    }
                }
            } catch (eUI) {}

            function dismissExpensiveSellWindow() {
                try {
                    if (!mWinPtr.isNull()) {
                        var expWin = mWinPtr.add(0x68).readPointer();
                        if (!expWin.isNull()) {
                            expWin.add(0x48).writeU8(0); // Chỉ tắt popup cảnh báo đắt tiền
                        }
                    }
                } catch (eExp) {}
            }

            function dispatchSellSlotOnMainThread(slotNum) {
                var req = { slot: slotNum, done: false, ok: false };
                pendingSellSlot = req;
                for (var mw = 0; mw < 8; mw++) {
                    if (req.done) break;
                    try { Thread.sleep(0.02); } catch (eMS) {}
                }
                if (!req.done) {
                    pendingSellSlot = null;
                    req.ok = sendSellPacket(slotNum);
                }
                return req.ok;
            }

            function collectSellableMossSlots() {
                var list = [];
                for (var s = 12; s < maxSlot; s++) {
                    // HARD SAFETY GUARD: Tuyệt đối không bao giờ bán trang bị trên người (0..11)
                    if (s < 12) continue;
                    // Nếu có danh sách allowedSet (các slot đồ rác Moss cho phép), chỉ bán các slot trong danh sách này
                    if (allowedSet !== null && !allowedSet[s]) continue;

                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                    if (itemPtr.isNull()) continue;

                    var itemIndex = readItemIndex(itemPtr);
                    var itemLevel = itemPtr.add(0x10).readS32();
                    var skill = itemPtr.add(0x14).readS32();
                    var luck = itemPtr.add(0x18).readS32();
                    var excOpt = itemPtr.add(0x20).readS32();
                    var ancOpt = itemPtr.add(0x24).readS32();
                    var harmRaw = itemPtr.add(0x28).readS32();
                    var opt380Raw = itemPtr.add(0x2C).readS32();
                    var sockOpt = hasItemSocketSlots(itemPtr) ? 1 : 0;
                    var harmonyOpt = (harmRaw > 0 || opt380Raw > 0) ? (harmRaw || opt380Raw) : 0;

                    // BẢO VỆ TUYỆT ĐỐI (Không bao giờ bán):
                    // 1. Đồ Rồng (Dragon) & Divine/Archangel/Ruud (LUÔN bảo vệ, kể cả khi bật allowExc)
                    // 2. Đồ Hoàn Hảo (excOpt > 0) CHỈ bán khi bật allowExc (và KHÔNG phải đồ Rồng / Divine / Archangel)
                    // 3. Đồ Thần (ancOpt > 0), Đồ Socket (mảng +0x38), Harmony/380 (+0x28/+0x2C)
                    // 4. Cấp độ > maxLvl (mặc định maxLvl = 7 -> giữ lại đồ >= +8)
                    // 5. Toàn bộ ngọc, vé sự kiện, cánh, sách phép (sec >= 12 && sec <= 15)
                    if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxLvl, ignoreType, cleanEquip, allowExc)) {
                        continue;
                    }
                    list.push({
                        slot: s,
                        ptr: itemPtr,
                        index: itemIndex,
                        level: itemLevel,
                        exc: excOpt,
                        name: getItemName(itemPtr) || ("Item " + itemIndex)
                    });
                }
                return list;
            }

            var initialTargets = collectSellableMossSlots();
            candidatesCount = initialTargets.length;
            var shopClosedMidway = false;
            var passesDone = 0;
            var curTargets = initialTargets;

            // Bán lần lượt tối đa 3 vòng ngay trong cùng phiên mở Shop cho tới khi sạch đồ rác Moss
            for (var passNum = 1; passNum <= 3 && curTargets.length > 0; passNum++) {
                passesDone = passNum;
                var passSold = 0;

                for (var ti = 0; ti < curTargets.length; ti++) {
                    if (!isMerchantWindowOpen()) {
                        shopClosedMidway = true;
                        break;
                    }
                    var tInfo = curTargets[ti];
                    var s = tInfo.slot;
                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                    if (itemPtr.isNull()) continue;

                    dismissExpensiveSellWindow();

                    var soldSuccess = false;
                    try {
                        // Gửi lệnh bán C3:33 + gán ItemStorage.SellingSlot trên Unity MainThread
                        dispatchSellSlotOnMainThread(s);

                        // Polling verify: Chờ server phản hồi C3:33 xóa item khỏi RAM (tối đa 1400ms, retry 1 lần ở 700ms)
                        for (var vi = 0; vi < 28; vi++) {
                            try { Thread.sleep(0.05); } catch (eSleepPkt) {}
                            dismissExpensiveSellWindow();
                            var verifyPkt = itemsArr.add(0x20 + s * 8).readPointer();
                            if (verifyPkt.isNull() || !verifyPkt.equals(itemPtr)) {
                                soldSuccess = true;
                                break;
                            }
                            if (vi === 13) {
                                if (!isMerchantWindowOpen()) {
                                    shopClosedMidway = true;
                                    break;
                                }
                                dispatchSellSlotOnMainThread(s);
                            }
                        }
                        if (!soldSuccess) {
                            clearItemStorageSellingSlot();
                        }
                    } catch (eSell) {}

                    if (shopClosedMidway) break;

                    if (soldSuccess) {
                        sold++;
                        passSold++;
                        soldItems.push({ slot: s, name: tInfo.name, level: tInfo.level, exc: tInfo.exc });
                        // Giãn nhịp 180ms giữa mỗi món để GameServer xử lý trọn vẹn không bị drop gói C3:33
                        try { Thread.sleep(0.18); } catch (ePaceOk) {}
                    } else {
                        // Nghỉ 250ms sau khi giải phóng SellingSlot trước khi sang món kế tiếp
                        try { Thread.sleep(0.25); } catch (ePaceFail) {}
                    }
                }

                if (shopClosedMidway) break;

                // Chờ 220ms rồi quét lại RAM xác nhận xem còn món rác Moss nào sót lại chưa bán không
                try { Thread.sleep(0.22); } catch (ePassSync) {}
                curTargets = collectSellableMossSlots();
                if (curTargets.length === 0) break;
                if (passNum >= 2 && passSold === 0) break;
                try { Thread.sleep(0.35); } catch (eNextPass) {}
            }

            var finalRem = collectSellableMossSlots();
            var remSlots = [];
            for (var ri = 0; ri < finalRem.length; ri++) {
                remSlots.push(finalRem[ri].slot);
            }
            var errOut = null;
            if (shopClosedMidway) {
                errOut = "merchant_closed_midway";
            } else if (sold === 0 && candidatesCount > 0) {
                errOut = "server_not_confirm";
            }

            return JSON.stringify({
                sold: sold,
                items: soldItems,
                candidates: candidatesCount,
                remaining: remSlots.length,
                remainingSlots: remSlots,
                passes: passesDone,
                error: errOut
            });
        } catch (e) {
            return JSON.stringify({ sold: 0, error: e.toString() });
        }
    },

    preStageMirrorTurbo: function(slot, measureProbe) {
        try {
            ensureThreadAttached();
            var itemSlot = (slot !== undefined && slot !== null && parseInt(slot) >= 0)
                ? parseInt(slot)
                : findMirrorTicketSlotSmart();
            if (itemSlot < 0) {
                return JSON.stringify({ success: false, error: "no_ticket" });
            }
            var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
            var probeCount = 0;
            if (typeof measureProbe === "number") {
                probeCount = Math.max(0, Math.min(6, parseInt(measureProbe)));
            } else if (measureProbe === true) {
                probeCount = 1;
            }
            _nativeMirrorTurboStats.activeSlot = itemSlot;
            _nativeMirrorTurboStats.relSlot = relSlot;
            _pendingMirrorPreStage = {
                slot: itemSlot,
                relSlot: relSlot,
                measureProbe: (probeCount > 0),
                probeCount: probeCount
            };
            return JSON.stringify({
                success: true,
                queued: true,
                slot: itemSlot,
                relSlot: relSlot,
                probeCount: probeCount,
                isExtended: (itemSlot >= 76)
            });
        } catch (ePS) {
            return JSON.stringify({ success: false, error: ePS.toString() });
        }
    },

    probeMirrorGate: function(slot) {
        try {
            ensureThreadAttached();
            var itemSlot = (slot !== undefined && slot !== null && parseInt(slot) >= 0)
                ? parseInt(slot)
                : findMirrorTicketSlotSmart();
            if (itemSlot < 0) {
                return JSON.stringify({ success: false, error: "no_ticket" });
            }
            var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
            _nativeMirrorTurboStats.activeSlot = itemSlot;
            _nativeMirrorTurboStats.relSlot = relSlot;
            _pendingMirrorPreStage = {
                slot: itemSlot,
                relSlot: relSlot,
                measureProbe: true
            };
            return JSON.stringify({
                success: true,
                probing: true,
                slot: itemSlot,
                relSlot: relSlot
            });
        } catch (eProbe) {
            return JSON.stringify({ success: false, error: eProbe.toString() });
        }
    },

    getMirrorTimingStats: function() {
        return JSON.stringify({
            rttMs: _nativeMirrorTurboStats.rttMs,
            minRttMs: _nativeMirrorTurboStats.minRttMs,
            lastRecvCode: _nativeMirrorTurboStats.lastRecvCode,
            rCodeCounts: _nativeMirrorTurboStats.rCodeCounts,
            serverOpenEpochMs: _nativeMirrorTurboStats.serverOpenEpochMs,
            mainThreadHits: _nativeMirrorTurboStats.mainThreadHits,
            directSocketHits: _nativeMirrorTurboStats.directSocketHits,
            fallbackHits: _nativeMirrorTurboStats.fallbackHits,
            directSocketErrors: _nativeMirrorTurboStats.directSocketErrors,
            tcpNoDelayEnabled: _nativeMirrorTurboStats.tcpNoDelayEnabled,
            activePhase: _nativeMirrorTurboStats.activePhase,
            preStagedAtMs: _nativeMirrorTurboStats.preStagedAtMs,
            fpsBoosted: _nativeMirrorTurboStats.fpsBoosted,
            running: _nativeMirrorTurboStats.running,
            armed: _nativeMirrorTurboStats.armed
        });
    },

    armNativeMirrorTurbo: function(slot, intervalMs, maxDurationMs, startAtEpochMs, optionsJson) {
        try {
            var opts = {};
            if (typeof optionsJson === "string" && optionsJson.length > 0) {
                try { opts = JSON.parse(optionsJson); } catch (eOJ) {}
            } else if (optionsJson && typeof optionsJson === "object") {
                opts = optionsJson;
            }
            return JSON.stringify(startOrArmMirrorTurboInternal(slot, intervalMs, maxDurationMs, startAtEpochMs, opts));
        } catch (eArm) {
            return JSON.stringify({ success: false, error: eArm.toString() });
        }
    },

    startNativeMirrorTurbo: function(slot, intervalMs, maxDurationMs, optionsJson) {
        try {
            var opts = {};
            if (typeof optionsJson === "string" && optionsJson.length > 0) {
                try { opts = JSON.parse(optionsJson); } catch (eOJ2) {}
            } else if (optionsJson && typeof optionsJson === "object") {
                opts = optionsJson;
            }
            return JSON.stringify(startOrArmMirrorTurboInternal(slot, intervalMs, maxDurationMs, 0, opts));
        } catch (eST) {
            return JSON.stringify({ success: false, error: eST.toString() });
        }
    },

    stopNativeMirrorTurbo: function() {
        try {
            cleanupNativeTurbo();
            _nativeMirrorTurboStats.running = false;
            _nativeMirrorTurboStats.armed = false;
            _nativeMirrorTurboStats.spamPaused = false;
            _pendingMirrorFpsRestore = true;
            if (_mirrorZeroConfirmMode) {
                _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, Date.now() + 1200);
            }
            return JSON.stringify({
                stopped: true,
                packetsSent: _nativeMirrorTurboStats.packetsSent,
                mainThreadHits: _nativeMirrorTurboStats.mainThreadHits,
                directSocketHits: _nativeMirrorTurboStats.directSocketHits,
                suppressedDialogs: _nativeMirrorTurboStats.suppressedDialogs,
                suppressedConfirms: _nativeMirrorTurboStats.suppressedConfirms,
                entered: _nativeMirrorTurboStats.entered
            });
        } catch (eStop) {
            return JSON.stringify({ stopped: false, error: eStop.toString() });
        }
    },

    setMirrorZeroConfirm: function(enabled) {
        _mirrorZeroConfirmMode = !!enabled;
        _nativeMirrorTurboStats.zeroConfirm = _mirrorZeroConfirmMode;
        if (!_mirrorZeroConfirmMode) {
            _suppressMirrorUiUntilMs = 0;
        }
        return JSON.stringify({ success: true, zeroConfirm: _mirrorZeroConfirmMode });
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

            if (itemSlot >= 0) {
                if (_mirrorZeroConfirmMode) {
                    _suppressMirrorUiUntilMs = Math.max(_suppressMirrorUiUntilMs, Date.now() + 1500);
                }
                // Zero-Confirm Fast-Path: chỉ gửi gói talk mạng nhẹ (không mở UI đối thoại NPC) và bắn thẳng gói vào cửa
                try { sendLugardTalkPacket(); } catch (eLugTalk) {}
                var relSlot = (itemSlot >= 12) ? (itemSlot - 12) : itemSlot;
                if (!dispatchMirrorEnterPacketFast(relSlot)) {
                    if (nativeMirrorEnterAlt !== null) {
                        try { nativeMirrorEnterAlt(relSlot); } catch (eNEA) {}
                    } else {
                        sendMirrorEnterPacket(relSlot);
                    }
                }
                return JSON.stringify({
                    success: true,
                    slot: itemSlot,
                    relSlot: relSlot,
                    zeroConfirm: _mirrorZeroConfirmMode,
                    isExtended: (itemSlot >= 76)
                });
            } else {
                var pLugard = getOrCreateLugardPtr(0);
                if (!_mirrorZeroConfirmMode && nativeMirrorNpcClick !== null && pLugard && !pLugard.isNull()) {
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
                // 2. Gọi client dialog DoubleGoer (<RVA>):
                // - Nếu không có vé: hiển thị popup "You don't have a Mirror of Dimensions"
                // - Nếu có vé: hiển thị confirm modal "You have a Mirror of Dimensions. Do you want to enter?"
                if (nativeMirrorNpcClick !== null) {
                    try { nativeMirrorNpcClick(p, ptr(0)); } catch (eMN) {}
                }
                // 3. Gọi Universal NPC Click của NpcManager (<RVA>) nếu có
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

    getDoubleGoerState: function() {
        try {
            ensureThreadAttached();
            // Đọc trực tiếp Mega.DoubleGoer_TypeInfo (RVA <RVA>) -> staticFields (+0xB8)
            // +0x00: bool PAFCGHEGBBO (isActive)
            // +0x04: int HLEOADFPCCH (remainingTimeSeconds)
            // +0x08: int ECBFKNFEGDP (passedMonsters)
            // +0x0C: int DKNEMBJBPJB (maxPassedMonsters - chuyển > 0 khi trận đấu bắt đầu!)
            var dgOff = off('__DOUBLEGOER_TYPE_INFO__');
            if (dgOff.isNull()) return JSON.stringify({ ok: false, active: false, timer: 0, passed: 0, maxPassed: 0 });
            var dgTypeInfo = baseAddr.add(dgOff).readPointer();
            if (!dgTypeInfo.isNull()) {
                var sf = dgTypeInfo.add(0xB8).readPointer();
                if (!sf.isNull()) {
                    var active = sf.add(0x00).readU8() === 1;
                    var timer = sf.add(0x04).readS32();
                    var passed = sf.add(0x08).readS32();
                    var maxPassed = sf.add(0x0C).readS32();
                    return JSON.stringify({
                        ok: true,
                        active: active,
                        timer: timer,
                        passed: passed,
                        maxPassed: maxPassed
                    });
                }
            }
        } catch (eDG) {}
        return JSON.stringify({ ok: false, active: false, timer: 0, passed: 0, maxPassed: 0 });
    },

    scanMirrorChestsAndItems: function() {
        try {
            ensureThreadAttached();
            var localPlayer = getPlayerPtr();
            if (localPlayer.isNull()) {
                return JSON.stringify({ ok: false, chests: [], items: [] });
            }
            var px = -1, py = -1;
            try {
                var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                if (!pCoord.isNull()) {
                    px = pCoord.add(0x10).readS32();
                    py = pCoord.add(0x14).readS32();
                }
            } catch (ePC) {}

            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });
            var gameInstance = staticFields.add(ptr('0x8')).readPointer();
            if (gameInstance.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });

            var mapId = -1;
            try {
                var worldPtr = gameInstance.add(off('__GAME_WORLD__')).readPointer();
                if (!worldPtr.isNull()) {
                    mapId = worldPtr.add(off('__WORLD_SCENE_INDEX__')).readS32();
                }
            } catch (eW) {}

            var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
            if (viewport.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });
            var objDict = viewport.add(ptr('0x20')).readPointer();
            if (objDict.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });

            var entries = objDict.add(ptr('0x18')).readPointer();
            if (entries.isNull()) return JSON.stringify({ ok: false, chests: [], items: [] });
            var count = objDict.add(ptr('0x20')).readS32();
            if (count <= 0 || count > 600) {
                return JSON.stringify({ ok: true, mapId: mapId, playerX: px, playerY: py, chests: [], items: [] });
            }

            var chests = [];
            var items = [];
            var monsters = [];

            for (var i = 0; i < count; i++) {
                var entryAddr = entries.add(0x20 + i * 24);
                var hashCode = -1;
                try { hashCode = entryAddr.readS32(); } catch (eHC) {}
                if (hashCode < 0) continue;

                var val = entryAddr.add(16).readPointer();
                if (val.isNull()) continue;

                var vKlass = ptr(0);
                try { vKlass = val.readPointer(); } catch (eVK) {}
                if (vKlass.isNull()) continue;
                var vKlassName = "";
                try {
                    var vkNamePtr = vKlass.add(0x10).readPointer();
                    if (!vkNamePtr.isNull()) vKlassName = vkNamePtr.readUtf8String() || "";
                } catch (eVKN) {}

                if (vKlassName.indexOf("ViewportBody") !== -1) {
                    var body = ptr(0);
                    try { body = val.add(0x18).readPointer(); } catch (eB) {}
                    if (body.isNull() || body.equals(localPlayer)) continue;

                    // Kiểm tra Body.IsDestroying (+0xC0) -> bỏ qua rương đã mở hoặc quái đã chết
                    var isDestroying = 0;
                    try { isDestroying = body.add(0xC0).readU8(); } catch (eDst) {}
                    if (isDestroying !== 0) continue;

                    var bKlass = ptr(0);
                    try { bKlass = body.readPointer(); } catch (eBK) {}
                    var bKlassName = "";
                    if (!bKlass.isNull()) {
                        try {
                            var bkNamePtr = bKlass.add(0x10).readPointer();
                            if (!bkNamePtr.isNull()) bKlassName = bkNamePtr.readUtf8String() || "";
                        } catch (eBKN) {}
                    }
                    if (bKlassName.indexOf("CharacterBody") !== -1) continue;

                    var bx = -1, by = -1;
                    try {
                        var bcPtr = body.add(0x68).readPointer();
                        if (!bcPtr.isNull()) {
                            bx = bcPtr.add(0x10).readS32();
                            by = bcPtr.add(0x14).readS32();
                        }
                    } catch (eBC) {}
                    if (bx < 0 || by < 0) continue;

                    var bIdx = -1;
                    try { bIdx = body.add(0x20).readS32(); } catch (eBI) {}
                    var clsId = -1;
                    try { clsId = body.add(0x34).readS32(); } catch (eCI) {}

                    var bName = "";
                    try {
                        var nPtr = body.add(0x28).readPointer();
                        if (!nPtr.isNull()) {
                            var nLen = nPtr.add(0x10).readS32();
                            if (nLen > 0 && nLen < 128) bName = nPtr.add(0x14).readUtf16String(nLen) || "";
                        }
                    } catch (eBN) {}

                    // Đọc MonsterBody.MonsterInfo (+0x138) để lấy tên bảng (MonsterInfo+0x18) và loại thực thể (MonsterInfo+0x30)
                    var infoName = "";
                    var infoType = -1;
                    try {
                        var mInfo = body.add(0x138).readPointer();
                        if (!mInfo.isNull()) {
                            infoType = mInfo.add(0x30).readS32();
                            var inPtr = mInfo.add(0x18).readPointer();
                            if (!inPtr.isNull()) {
                                var inLen = inPtr.add(0x10).readS32();
                                if (inLen > 0 && inLen < 128) infoName = inPtr.add(0x14).readUtf16String(inLen) || "";
                            }
                        }
                    } catch (eMI) {}

                    var finalName = bName || infoName || "";
                    var lowName = finalName.toLowerCase();

                    // Nhận diện Rương Sự Kiện Mirror (Double Goer):
                    // - Class ID 541 (0x21D): Rương Bạc / Interim Reward Chest (Baú de Prata)
                    // - Class ID 542 (0x21E): Rương Vàng / Final Reward Chest (Baú de Ouro)
                    // TUYỆT ĐỐI KHÔNG dùng infoType === 1 || infoType === 4 vì quái Double Goer (529..539) có infoType = 1!
                    var isLugardId = (clsId === 540 || clsId === 723 || clsId === 45 || lowName.indexOf("lugard") !== -1 || lowName.indexOf("sartigan") !== -1);
                    var isMonsterId = (clsId >= 529 && clsId <= 539);
                    var isChestId = (clsId === 541 || clsId === 542 || clsId === 528);
                    var isChestKw = !isMonsterId && !isLugardId && (
                        lowName.indexOf("chest") !== -1 ||
                        lowName.indexOf("baú") !== -1 ||
                        lowName.indexOf("bau") !== -1 ||
                        lowName.indexOf("tesouro") !== -1 ||
                        lowName.indexOf("caixa") !== -1 ||
                        lowName.indexOf("coffer") !== -1 ||
                        lowName.indexOf("rương") !== -1
                    );

                    if (isChestId || isChestKw) {
                        var dist = (px >= 0 && py >= 0) ? Math.sqrt((bx - px) * (bx - px) + (by - py) * (by - py)) : 0;
                        if (!finalName) {
                            finalName = (clsId === 542) ? "Final Reward Chest (Golden)" : "Reward Chest (Silver)";
                        }
                        chests.push({
                            ptr: body.toString(),
                            index: bIdx,
                            classId: clsId,
                            name: finalName,
                            klass: bKlassName,
                            infoType: infoType,
                            x: bx,
                            y: by,
                            distance: Math.round(dist * 10) / 10
                        });
                    } else if (!isLugardId && (isMonsterId || (bKlassName.indexOf("MonsterBody") !== -1 && bKlassName.indexOf("NpcBody") === -1))) {
                        var mdist = (px >= 0 && py >= 0) ? Math.sqrt((bx - px) * (bx - px) + (by - py) * (by - py)) : 0;
                        monsters.push({
                            ptr: body.toString(),
                            index: bIdx,
                            classId: clsId,
                            name: finalName || ("Monster #" + clsId),
                            x: bx,
                            y: by,
                            distance: Math.round(mdist * 10) / 10
                        });
                    }
                } else if (vKlassName.indexOf("ViewportItem") !== -1) {
                    var ix = -1, iy = -1;
                    try {
                        var icPtr = val.add(0x28).readPointer();
                        if (!icPtr.isNull()) {
                            ix = icPtr.add(0x10).readS32();
                            iy = icPtr.add(0x14).readS32();
                        }
                    } catch (eIC) {}
                    if (ix < 0 || iy < 0) continue;

                    var vItemIdx = -1;
                    try { vItemIdx = val.add(0x10).readS32(); } catch (eVI) {}
                    var itemObj = ptr(0);
                    try { itemObj = val.add(0x18).readPointer(); } catch (eIO) {}
                    var itemCode = 0;
                    var itName = "";
                    if (!itemObj.isNull()) {
                        try { itemCode = readItemIndex(itemObj); } catch (eICd) {}
                        try { itName = getItemName(itemObj) || ""; } catch (eIN) {}
                    }
                    var idist = (px >= 0 && py >= 0) ? Math.sqrt((ix - px) * (ix - px) + (iy - py) * (iy - py)) : 0;
                    items.push({
                        viewportItemPtr: val.toString(),
                        itemPtr: itemObj.toString(),
                        index: vItemIdx,
                        itemCode: itemCode,
                        name: itName || ("Item #" + itemCode),
                        x: ix,
                        y: iy,
                        distance: Math.round(idist * 10) / 10
                    });
                }
            }

            return JSON.stringify({
                ok: true,
                mapId: mapId,
                playerX: px,
                playerY: py,
                chests: chests,
                items: items,
                monsters: monsters
            });
        } catch (eScanM) {
            return JSON.stringify({ ok: false, error: eScanM.toString(), chests: [], items: [], monsters: [] });
        }
    },

    interactAndLootMirror: function(chestPtrStr, chestIndex, maxRadius) {
        try {
            ensureThreadAttached();
            var radius = (maxRadius !== undefined && maxRadius !== null) ? parseFloat(maxRadius) : 5.0;
            var openedChest = false;
            var pickedCount = 0;

            // 1. Tương tác mở Rương Sự Kiện (Gửi trực tiếp NpcManager.GEBGEGOEFAD <RVA> -> C3:30 + C1:30 để KHÔNG gây tự động di chuyển)
            var targetBody = ptr(0);
            if (chestPtrStr && chestPtrStr !== "0" && chestPtrStr !== "0x0") {
                try { targetBody = ptr(chestPtrStr); } catch (eTP) {}
            }

            var localPlayer = getPlayerPtr();
            var px = -1, py = -1;
            if (!localPlayer.isNull()) {
                try {
                    var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                    if (!pCoord.isNull()) {
                        px = pCoord.add(0x10).readS32();
                        py = pCoord.add(0x14).readS32();
                    }
                } catch (ePC) {}
            }

            // Nếu chưa truyền con trỏ hoặc cần quét ViewportItem, duyệt Viewport.ObjectList
            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            var objDict = ptr(0);
            if (!typeInfo.isNull()) {
                var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
                if (!staticFields.isNull()) {
                    var gameInstance = staticFields.add(ptr('0x8')).readPointer();
                    if (!gameInstance.isNull()) {
                        var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
                        if (!viewport.isNull()) {
                            objDict = viewport.add(ptr('0x20')).readPointer();
                        }
                    }
                }
            }

            if (targetBody.isNull() && !objDict.isNull() && chestIndex !== undefined && parseInt(chestIndex) >= 0) {
                var wantIdx = parseInt(chestIndex);
                try {
                    var entries0 = objDict.add(ptr('0x18')).readPointer();
                    var count0 = objDict.add(ptr('0x20')).readS32();
                    for (var k = 0; k < count0 && k < 600; k++) {
                        var e0 = entries0.add(0x20 + k * 24);
                        if (e0.readS32() < 0) continue;
                        var v0 = e0.add(16).readPointer();
                        if (v0.isNull()) continue;
                        var vk0 = v0.readPointer();
                        if (vk0.isNull()) continue;
                        var vkn0 = vk0.add(0x10).readPointer().readUtf8String() || "";
                        if (vkn0.indexOf("ViewportBody") !== -1) {
                            var b0 = v0.add(0x18).readPointer();
                            if (!b0.isNull() && b0.add(0x20).readS32() === wantIdx) {
                                targetBody = b0;
                                break;
                            }
                        }
                    }
                } catch (eFindC) {}
            }

            if (!targetBody.isNull()) {
                try {
                    var isDest = targetBody.add(0xC0).readU8();
                    var tClsId = -1;
                    try { tClsId = targetBody.add(0x34).readS32(); } catch (eTCI) {}
                    if (isDest === 0 && !(tClsId >= 529 && tClsId <= 539) && tClsId !== 540 && tClsId !== 723 && tClsId !== 45) {
                        var bIdx = targetBody.add(0x20).readS32();
                        // Ưu tiên gọi trực tiếp NpcManager.GEBGEGOEFAD (<RVA>) gửi C3:30 mà KHÔNG kích hoạt vtable MoveTo của <RVA>
                        if (nativeNpcSendTalk !== null) {
                            try {
                                nativeNpcSendTalk(targetBody, ptr(0));
                                openedChest = true;
                            } catch (eNST) {}
                        }
                        // Fallback gói C1:30 chuẩn little-endian Index
                        if (bIdx >= 0) {
                            var lo = bIdx & 0xFF;
                            var hi = (bIdx >> 8) & 0xFF;
                            sendGSPacket([0xC1, 0x05, 0x30, lo, hi]);
                            openedChest = true;
                        }
                    }
                } catch (eOpen) {}
            }

            // 2. Tự động nhặt ViewportItem rơi trên đất trong bán kính radius
            // LƯU Ý QUAN TRỌNG: Hàm <RVA> (nativeUserInvPickItem) và <RVA> (nativeLocalPickNearest) sẽ gọi MoveTo (<RVA>)
            // làm nhân vật tự chạy đi nếu vật phẩm cách > 2 ô! Do đó chỉ gọi <RVA> khi dist <= 2.0, còn lại gửi thẳng packet C1:22 tại chỗ!
            if (!objDict.isNull()) {
                try {
                    var entries = objDict.add(ptr('0x18')).readPointer();
                    var count = objDict.add(ptr('0x20')).readS32();
                    for (var i = 0; i < count && i < 600; i++) {
                        var entryAddr = entries.add(0x20 + i * 24);
                        if (entryAddr.readS32() < 0) continue;
                        var val = entryAddr.add(16).readPointer();
                        if (val.isNull()) continue;
                        var vKlass = val.readPointer();
                        if (vKlass.isNull()) continue;
                        var vKlassName = vKlass.add(0x10).readPointer().readUtf8String() || "";
                        if (vKlassName.indexOf("ViewportItem") === -1) continue;

                        var ix = -1, iy = -1;
                        var icPtr = val.add(0x28).readPointer();
                        if (!icPtr.isNull()) {
                            ix = icPtr.add(0x10).readS32();
                            iy = icPtr.add(0x14).readS32();
                        }
                        if (ix < 0 || iy < 0) continue;

                        var dist = (px >= 0 && py >= 0) ? Math.sqrt((ix - px) * (ix - px) + (iy - py) * (iy - py)) : 0;
                        if (dist <= radius) {
                            var vIdx = val.add(0x10).readS32();
                            var itemPtr = val.add(0x18).readPointer();
                            if (vIdx >= 0 && !itemPtr.isNull()) {
                                if (dist <= 2.0 && nativeUserInvPickItem !== null) {
                                    try {
                                        nativeUserInvPickItem(vIdx, itemPtr, ptr(0));
                                    } catch (ePick1) {}
                                }
                                // Gửi trực tiếp packet C1:22 little-endian Index (nhặt tại chỗ 100% không gây di chuyển nhân vật)
                                var iLo = vIdx & 0xFF;
                                var iHi = (vIdx >> 8) & 0xFF;
                                sendGSPacket([0xC1, 0x05, 0x22, iLo, iHi]);
                                pickedCount++;
                            }
                        }
                    }
                } catch (ePickLoop) {}
            }

            return JSON.stringify({
                ok: true,
                openedChest: openedChest,
                pickedCount: pickedCount
            });
        } catch (eILM) {
            return JSON.stringify({ ok: false, error: eILM.toString(), openedChest: false, pickedCount: 0 });
        }
    },

    scanJewelsSnapshot: function() {
        try {
            ensureThreadAttached();
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

            function readJewelCount(itemPtr) {
                if (!itemPtr || itemPtr.isNull()) return 1;
                try {
                    var sm = readItemStackMeta(itemPtr);
                    if (sm && sm.count >= 1 && sm.count <= 255) return sm.count;
                } catch (eSMJ) {}
                try {
                    var dur = itemPtr.add(0x1C).readS32();
                    if (dur >= 1 && dur <= 100) return dur;
                } catch (eD) {}
                try {
                    var lv = itemPtr.add(0x10).readS32();
                    if (lv >= 1 && lv <= 100) return lv;
                } catch (eL) {}
                try {
                    var f40 = itemPtr.add(0x40).readS32();
                    if (f40 >= 1 && f40 <= 100) return f40;
                } catch (eF) {}
                return 1;
            }

            function getJewelType(idx, name) {
                var nmL = (name || "").toLowerCase();
                if (nmL.indexOf("darkness") !== -1 || nmL.indexOf("dark") !== -1) return null;
                if (nmL.indexOf("elevation") !== -1 || nmL.indexOf("extension") !== -1) return null;
                if (nmL.indexOf("talisman") !== -1 || nmL.indexOf("chaos assembly") !== -1 || nmL.indexOf("chaos card") !== -1 || idx === TALISMAN_LUCK_ID || idx === TALISMAN_CHAOS_ASSEMBLY_ID) return null;
                if (COMBINABLE_JEWEL_MAP[idx]) return COMBINABLE_JEWEL_MAP[idx];
                if (nmL.indexOf("bless") !== -1) return "Bless";
                if (nmL.indexOf("soul") !== -1) return "Soul";
                if (nmL.indexOf("life") !== -1) return "Life";
                if (nmL.indexOf("jewel of chaos") !== -1 || nmL === "chaos") return "Chaos";
                if (nmL.indexOf("creation") !== -1) return "Creation";
                if (nmL.indexOf("guardian") !== -1) return "Guardian";
                if (nmL.indexOf("harmony") !== -1) return "Harmony";
                if (nmL.indexOf("gemstone") !== -1 || nmL.indexOf("gem of") !== -1) return "Gemstone";
                return null;
            }

            var items = [];
            var counts = {};
            var looseCounts = {};
            var totalJewels = 0;
            var whOpen = false;

            // 1. Quet Thung do Kho (Chinh 0..119 & Mo Rong 120..239)
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
                        if (!whWin.isNull()) {
                            var whDict = {};
                            // A. Doc qua WarehouseWindow.Items (offset 0x30)
                            try {
                                var dictPtr = whWin.add(ptr('0x30')).readPointer();
                                if (!dictPtr.isNull()) {
                                    var entries = dictPtr.add(ptr('0x18')).readPointer();
                                    var count = dictPtr.add(ptr('0x20')).readS32();
                                    if (!entries.isNull() && count > 0 && count <= 300) {
                                        whOpen = true;
                                        for (var di = 0; di < count; di++) {
                                            try {
                                                var ent = entries.add(0x20 + di * 24);
                                                if (ent.readS32() < 0) continue;
                                                var slot = ent.add(0x08).readS32();
                                                var itemPtr = ent.add(0x10).readPointer();
                                                if (!itemPtr.isNull() && slot >= 0 && slot < 240) {
                                                    var idx = readItemIndex(itemPtr);
                                                    var nm = getItemName(itemPtr) || "";
                                                    var jType = getJewelType(idx, nm);
                                                    if (jType) {
                                                        var cnt = readJewelCount(itemPtr);
                                                        whDict[slot] = { slot: slot, id: idx, name: nm, count: cnt, type: jType, storage: slot < 120 ? "Thùng đồ chính" : "Thùng đồ mở rộng" };
                                                    }
                                                }
                                            } catch (eDE) {}
                                        }
                                    }
                                }
                            } catch (eWItems) {}

                            // B. Doc bo sung qua MainStorage (0x58) & ExtStorage (0x60) Cells
                            function scanCells(sPtr, bStart, bEnd, stName) {
                                if (!sPtr || sPtr.isNull()) return;
                                try {
                                    var startIdx = bStart;
                                    try { var s = sPtr.add(0x28).readS32(); if (s >= 0 && s <= 240) startIdx = s; } catch (eS) {}
                                    var cDict = sPtr.add(ptr('0x38')).readPointer();
                                    if (cDict.isNull()) return;
                                    var cEnt = cDict.add(ptr('0x18')).readPointer();
                                    var cCnt = cDict.add(ptr('0x20')).readS32();
                                    if (cEnt.isNull() || cCnt <= 0 || cCnt > 300) return;
                                    whOpen = true;
                                    for (var ci = 0; ci < cCnt; ci++) {
                                        try {
                                            var ce = cEnt.add(0x20 + ci * 24);
                                            if (ce.readS32() < 0) continue;
                                            var sk = ce.add(0x08).readS32();
                                            var so = ce.add(0x10).readPointer();
                                            if (so.isNull()) continue;
                                            var sn = so.add(ptr('0x20')).readS32();
                                            var rs = sn < startIdx ? sn + startIdx : sn;
                                            if (rs < bStart || rs >= bEnd) rs = sk;
                                            if (rs >= bStart && rs < bEnd && !whDict[rs]) {
                                                var io = so.add(ptr('0x48')).readPointer();
                                                if (!io.isNull()) {
                                                    var iIdx = readItemIndex(io);
                                                    var iNm = getItemName(io) || "";
                                                    var iType = getJewelType(iIdx, iNm);
                                                    if (iType) {
                                                        var iCnt = readJewelCount(io);
                                                        whDict[rs] = { slot: rs, id: iIdx, name: iNm, count: iCnt, type: iType, storage: stName };
                                                    }
                                                }
                                            }
                                        } catch (eCI) {}
                                    }
                                } catch (eCS) {}
                            }
                            try { scanCells(whWin.add(ptr('0x58')).readPointer(), 0, 120, "Thùng đồ chính"); } catch (eMS) {}
                            try { scanCells(whWin.add(ptr('0x60')).readPointer(), 120, 240, "Thùng đồ mở rộng"); } catch (eES) {}

                            for (var wSlot in whDict) {
                                var wit = whDict[wSlot];
                                items.push(wit);
                                counts[wit.type] = (counts[wit.type] || 0) + wit.count;
                                if (wit.count < 100) looseCounts[wit.type] = (looseCounts[wit.type] || 0) + 1;
                                totalJewels += wit.count;
                            }
                        }
                    }
                }
            } catch (eWH) {}

            // 2. Quet Hom do Nhan vat (12..203)
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            var arrLen = 204;
                            try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) arrLen = l; } catch (eL) {}
                            for (var s = 12; s < arrLen; s++) {
                                try {
                                    var it = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!it.isNull()) {
                                        var idx2 = readItemIndex(it);
                                        var nm2 = getItemName(it) || "";
                                        var jType2 = getJewelType(idx2, nm2);
                                        if (jType2) {
                                            var cnt2 = readJewelCount(it);
                                            items.push({ slot: s, id: idx2, name: nm2, count: cnt2, type: jType2, storage: "Hòm đồ nhân vật" });
                                            counts[jType2] = (counts[jType2] || 0) + cnt2;
                                            if (cnt2 < 100) looseCounts[jType2] = (looseCounts[jType2] || 0) + 1;
                                            totalJewels += cnt2;
                                        }
                                    }
                                } catch (eIt) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}

            return JSON.stringify({
                ok: true,
                warehouseOpen: whOpen,
                totalJewels: totalJewels,
                counts: counts,
                looseCounts: looseCounts,
                itemCount: items.length
            });
        } catch (eSnap) {
            return JSON.stringify({ ok: false, error: String(eSnap) });
        }
    },

    stackJewelStep: function(filterType) {
        try {
            ensureThreadAttached();
            if (nativeItemStorageMove === null) {
                return JSON.stringify({ ok: false, error: "no_native_move_fn" });
            }

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
            var MAX_STACK = 100;

            function readJewelCount(itemPtr) {
                if (!itemPtr || itemPtr.isNull()) return 1;
                try {
                    var sm = readItemStackMeta(itemPtr);
                    if (sm && sm.count >= 1 && sm.count <= 255) return sm.count;
                } catch (eSMJ) {}
                try {
                    var dur = itemPtr.add(0x1C).readS32();
                    if (dur >= 1 && dur <= 100) return dur;
                } catch (eD) {}
                try {
                    var lv = itemPtr.add(0x10).readS32();
                    if (lv >= 1 && lv <= 100) return lv;
                } catch (eL) {}
                try {
                    var f40 = itemPtr.add(0x40).readS32();
                    if (f40 >= 1 && f40 <= 100) return f40;
                } catch (eF) {}
                return 1;
            }

            function getJewelType(idx, name) {
                var nmL = (name || "").toLowerCase();
                if (nmL.indexOf("darkness") !== -1 || nmL.indexOf("dark") !== -1) return null;
                if (nmL.indexOf("elevation") !== -1 || nmL.indexOf("extension") !== -1) return null;
                if (nmL.indexOf("talisman") !== -1 || nmL.indexOf("chaos assembly") !== -1 || nmL.indexOf("chaos card") !== -1 || idx === TALISMAN_LUCK_ID || idx === TALISMAN_CHAOS_ASSEMBLY_ID) return null;
                if (COMBINABLE_JEWEL_MAP[idx]) return COMBINABLE_JEWEL_MAP[idx];
                if (nmL.indexOf("bless") !== -1) return "Bless";
                if (nmL.indexOf("soul") !== -1) return "Soul";
                if (nmL.indexOf("life") !== -1) return "Life";
                if (nmL.indexOf("jewel of chaos") !== -1 || nmL === "chaos") return "Chaos";
                if (nmL.indexOf("creation") !== -1) return "Creation";
                if (nmL.indexOf("guardian") !== -1) return "Guardian";
                if (nmL.indexOf("harmony") !== -1) return "Harmony";
                if (nmL.indexOf("gemstone") !== -1 || nmL.indexOf("gem of") !== -1) return "Gemstone";
                return null;
            }

            var sections = [];
            var mainWhItems = {};
            var extWhItems = {};

            // 1. Quet Thung do Kho (Chinh 0..119 & Mo Rong 120..239)
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
                        if (!whWin.isNull()) {
                            // A. Doc qua WarehouseWindow.Items (offset 0x30)
                            try {
                                var dictPtr = whWin.add(ptr('0x30')).readPointer();
                                if (!dictPtr.isNull()) {
                                    var entries = dictPtr.add(ptr('0x18')).readPointer();
                                    var count = dictPtr.add(ptr('0x20')).readS32();
                                    if (!entries.isNull() && count > 0 && count <= 300) {
                                        for (var di = 0; di < count; di++) {
                                            try {
                                                var ent = entries.add(0x20 + di * 24);
                                                if (ent.readS32() < 0) continue;
                                                var slot = ent.add(0x08).readS32();
                                                var itemPtr = ent.add(0x10).readPointer();
                                                if (!itemPtr.isNull() && slot >= 0 && slot < 240) {
                                                    var idx = readItemIndex(itemPtr);
                                                    var nm = getItemName(itemPtr) || "";
                                                    var jType = getJewelType(idx, nm);
                                                    if (jType && (!filterType || jType === filterType)) {
                                                        var cnt = readJewelCount(itemPtr);
                                                        var itObj = { slot: slot, ptr: itemPtr, id: idx, name: nm, count: cnt, type: jType };
                                                        if (slot < 120) {
                                                            if (!mainWhItems[slot]) mainWhItems[slot] = itObj;
                                                        } else {
                                                            if (!extWhItems[slot]) extWhItems[slot] = itObj;
                                                        }
                                                    }
                                                }
                                            } catch (eDE) {}
                                        }
                                    }
                                }
                            } catch (eWItems) {}

                            // B. Doc bo sung qua MainStorage (0x58) & ExtStorage (0x60) Cells
                            function scanCellsToDict(sPtr, outDict, bStart, bEnd) {
                                if (!sPtr || sPtr.isNull()) return;
                                try {
                                    var startIdx = bStart;
                                    try { var s = sPtr.add(0x28).readS32(); if (s >= 0 && s <= 240) startIdx = s; } catch (eS) {}
                                    var cDict = sPtr.add(ptr('0x38')).readPointer();
                                    if (cDict.isNull()) return;
                                    var cEnt = cDict.add(ptr('0x18')).readPointer();
                                    var cCnt = cDict.add(ptr('0x20')).readS32();
                                    if (cEnt.isNull() || cCnt <= 0 || cCnt > 300) return;
                                    for (var ci = 0; ci < cCnt; ci++) {
                                        try {
                                            var ce = cEnt.add(0x20 + ci * 24);
                                            if (ce.readS32() < 0) continue;
                                            var sk = ce.add(0x08).readS32();
                                            var so = ce.add(0x10).readPointer();
                                            if (so.isNull()) continue;
                                            var sn = so.add(ptr('0x20')).readS32();
                                            var rs = sn < startIdx ? sn + startIdx : sn;
                                            if (rs < bStart || rs >= bEnd) rs = sk;
                                            if (rs >= bStart && rs < bEnd && !outDict[rs]) {
                                                var io = so.add(ptr('0x48')).readPointer();
                                                if (!io.isNull()) {
                                                    var iIdx = readItemIndex(io);
                                                    var iNm = getItemName(io) || "";
                                                    var iType = getJewelType(iIdx, iNm);
                                                    if (iType && (!filterType || iType === filterType)) {
                                                        var iCnt = readJewelCount(io);
                                                        outDict[rs] = { slot: rs, ptr: io, id: iIdx, name: iNm, count: iCnt, type: iType };
                                                    }
                                                }
                                            }
                                        } catch (eCI) {}
                                    }
                                } catch (eCS) {}
                            }
                            try { scanCellsToDict(whWin.add(ptr('0x58')).readPointer(), mainWhItems, 0, 120); } catch (eMS) {}
                            try { scanCellsToDict(whWin.add(ptr('0x60')).readPointer(), extWhItems, 120, 240); } catch (eES) {}
                        }
                    }
                }
            } catch (eWH) {}

            var mainWhList = [];
            for (var mKey in mainWhItems) mainWhList.push(mainWhItems[mKey]);
            if (mainWhList.length > 0) sections.push({ name: "Thùng đồ chính", flag: 2, items: mainWhList });

            var extWhList = [];
            for (var eKey in extWhItems) extWhList.push(extWhItems[eKey]);
            if (extWhList.length > 0) sections.push({ name: "Thùng đồ mở rộng", flag: 2, items: extWhList });

            // 2. Quet Hom do Nhan vat (12..203)
            var invItems = [];
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            var arrLen = 204;
                            try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) arrLen = l; } catch (eL) {}
                            for (var s = 12; s < arrLen; s++) {
                                try {
                                    var it = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!it.isNull()) {
                                        var idx2 = readItemIndex(it);
                                        var nm2 = getItemName(it) || "";
                                        var jType2 = getJewelType(idx2, nm2);
                                        if (jType2 && (!filterType || jType2 === filterType)) {
                                            var cnt2 = readJewelCount(it);
                                            invItems.push({ slot: s, ptr: it, id: idx2, name: nm2, count: cnt2, type: jType2 });
                                        }
                                    }
                                } catch (eIt) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}
            if (invItems.length > 0) sections.push({ name: "Hòm đồ nhân vật", flag: 0, items: invItems });

            // 3. Tim cap ngoc cung ID de thuc hien ghep (1 buoc duy nhat)
            for (var secIdx = 0; secIdx < sections.length; secIdx++) {
                var sec = sections[secIdx];
                var groups = {};
                for (var gi = 0; gi < sec.items.length; gi++) {
                    var itm = sec.items[gi];
                    if (!groups[itm.id]) groups[itm.id] = [];
                    groups[itm.id].push(itm);
                }

                for (var jId in groups) {
                    var group = groups[jId];
                    if (group.length <= 1) continue;

                    // Sap xep tang dan theo so o
                    group.sort(function(a, b) { return a.slot - b.slot; });

                    for (var tIdx = 0; tIdx < group.length; tIdx++) {
                        var target = group[tIdx];
                        if (target.count >= MAX_STACK) continue;

                        for (var sIdx = tIdx + 1; sIdx < group.length; sIdx++) {
                            var src = group[sIdx];
                            if (src.count <= 0 || src.slot === target.slot) continue;
                            if (!src.ptr || src.ptr.isNull() || !target.ptr || target.ptr.isNull()) continue;
                            if (src.id !== target.id) continue;

                            var toMove = Math.min(src.count, MAX_STACK - target.count);
                            try {
                                nativeItemStorageMove(src.ptr, sec.flag, src.slot, sec.flag, target.slot, ptr(0));
                                return JSON.stringify({
                                    ok: true,
                                    moved: true,
                                    storage: sec.name,
                                    storageFlag: sec.flag,
                                    jewel: target.type,
                                    name: target.name,
                                    id: target.id,
                                    fromSlot: src.slot,
                                    toSlot: target.slot,
                                    fromCount: src.count,
                                    toCount: target.count,
                                    amount: toMove,
                                    targetTotal: target.count + toMove
                                });
                            } catch (eNativeMove) {
                                return JSON.stringify({ ok: false, error: String(eNativeMove) });
                            }
                        }
                    }
                }
            }

            return JSON.stringify({ ok: true, moved: false, jewel: filterType });
        } catch (eStep) {
            return JSON.stringify({ ok: false, error: String(eStep) });
        }
    },

    autoStackJewels: function() {
        try {
            ensureThreadAttached();
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
            var MAX_STACK = 100;

            function readJewelCount(itemPtr) {
                if (!itemPtr || itemPtr.isNull()) return 1;
                try {
                    var sm = readItemStackMeta(itemPtr);
                    if (sm && sm.count >= 1 && sm.count <= 255) return sm.count;
                } catch (eSMJ) {}
                try {
                    var dur = itemPtr.add(0x1C).readS32();
                    if (dur >= 1 && dur <= 100) return dur;
                } catch (eD) {}
                try {
                    var lv = itemPtr.add(0x10).readS32();
                    if (lv >= 1 && lv <= 100) return lv;
                } catch (eL) {}
                try {
                    var f40 = itemPtr.add(0x40).readS32();
                    if (f40 >= 1 && f40 <= 100) return f40;
                } catch (eF) {}
                return 1;
            }

            function getJewelType(idx, name) {
                var nmL = (name || "").toLowerCase();
                if (nmL.indexOf("darkness") !== -1 || nmL.indexOf("dark") !== -1) return null;
                if (nmL.indexOf("elevation") !== -1 || nmL.indexOf("extension") !== -1) return null;
                if (nmL.indexOf("talisman") !== -1 || nmL.indexOf("chaos assembly") !== -1 || nmL.indexOf("chaos card") !== -1 || idx === TALISMAN_LUCK_ID || idx === TALISMAN_CHAOS_ASSEMBLY_ID) return null;
                if (COMBINABLE_JEWEL_MAP[idx]) return COMBINABLE_JEWEL_MAP[idx];
                if (nmL.indexOf("bless") !== -1) return "Bless";
                if (nmL.indexOf("soul") !== -1) return "Soul";
                if (nmL.indexOf("life") !== -1) return "Life";
                if (nmL.indexOf("jewel of chaos") !== -1 || nmL === "chaos") return "Chaos";
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

            function consolidateStorage(storageName, storageFlag, slotsDict) {
                var groups = {};
                for (var sKey in slotsDict) {
                    var it = slotsDict[sKey];
                    if (!it.type) continue;
                    if (!groups[it.id]) groups[it.id] = [];
                    groups[it.id].push(it);
                    totalCounts[it.type] = (totalCounts[it.type] || 0) + it.count;
                    totalJewelsFound += it.count;
                }

                for (var jId in groups) {
                    var group = groups[jId];
                    if (group.length <= 1) continue;
                    group.sort(function(a, b) { return a.slot - b.slot; });

                    var targetIdx = 0;
                    for (var srcIdx = 1; srcIdx < group.length; srcIdx++) {
                        var src = group[srcIdx];
                        if (src.count <= 0) continue;

                        while (src.count > 0 && targetIdx < srcIdx) {
                            var target = group[targetIdx];
                            var spaceInTarget = MAX_STACK - target.count;
                            if (spaceInTarget <= 0) {
                                targetIdx++;
                                continue;
                            }
                            if (!src.ptr || src.ptr.isNull() || !target.ptr || target.ptr.isNull()) break;
                            if (src.id !== target.id || src.slot === target.slot) break;

                            var toMove = Math.min(src.count, spaceInTarget);
                            try {
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
                                try { Thread.sleep(0.2); } catch (eSleep) {}
                            } catch (eMove) {
                                break;
                            }
                            if (target.count >= MAX_STACK) targetIdx++;
                        }
                    }
                }
            }

            var mainWarehouseSlots = {};
            var extWarehouseSlots = {};

            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (!gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
                        if (!whWin.isNull()) {
                            try {
                                var dictPtr = whWin.add(ptr('0x30')).readPointer();
                                if (!dictPtr.isNull()) {
                                    var entries = dictPtr.add(ptr('0x18')).readPointer();
                                    var count = dictPtr.add(ptr('0x20')).readS32();
                                    if (!entries.isNull() && count > 0 && count <= 300) {
                                        for (var di = 0; di < count; di++) {
                                            try {
                                                var ent = entries.add(0x20 + di * 24);
                                                if (ent.readS32() < 0) continue;
                                                var slot = ent.add(0x08).readS32();
                                                var val = ent.add(0x10).readPointer();
                                                if (!val.isNull() && slot >= 0 && slot < 240) {
                                                    var idx2 = readItemIndex(val);
                                                    var nm2 = getItemName(val) || "";
                                                    var jType2 = getJewelType(idx2, nm2);
                                                    if (jType2) {
                                                        var cnt2 = readJewelCount(val);
                                                        var itObj2 = { slot: slot, ptr: val, id: idx2, name: nm2, count: cnt2, type: jType2 };
                                                        if (slot < 120) mainWarehouseSlots[slot] = itObj2;
                                                        else extWarehouseSlots[slot] = itObj2;
                                                    }
                                                }
                                            } catch (eWhEnt) {}
                                        }
                                    }
                                }
                            } catch (eWhItems) {}
                        }
                    }
                }
            } catch (eWH) {}

            if (Object.keys(mainWarehouseSlots).length > 0) {
                consolidateStorage("Thùng đồ chính", 2, mainWarehouseSlots);
            }
            if (Object.keys(extWarehouseSlots).length > 0) {
                consolidateStorage("Thùng đồ mở rộng", 2, extWarehouseSlots);
            }

            var inventorySlots = {};
            var invMaxSlot = 204;
            try {
                var p = getPlayerPtr();
                if (!p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (!inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (!itemsArr.isNull()) {
                            try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) invMaxSlot = l; } catch (eL) {}
                            for (var s = 12; s < invMaxSlot; s++) {
                                try {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var invIdx = readItemIndex(itemPtr);
                                        var invNm = getItemName(itemPtr) || "";
                                        var invJType = getJewelType(invIdx, invNm);
                                        if (invJType) {
                                            var invCnt = readJewelCount(itemPtr);
                                            inventorySlots[s] = { slot: s, ptr: itemPtr, id: invIdx, name: invNm, count: invCnt, type: invJType };
                                        }
                                    }
                                } catch (eIt) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}

            if (Object.keys(inventorySlots).length > 0) {
                consolidateStorage("Hòm đồ nhân vật", 0, inventorySlots);
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

    getGremoryCaseItems: function(storageFilter) {
        try {
            ensureThreadAttached();
            var snap = readGremoryCaseSnapshot(storageFilter);
            if (!snap.ok) {
                return JSON.stringify({ ok: false, count: 0, items: [], byStorage: {}, reason: snap.reason });
            }
            var publicItems = [];
            for (var i = 0; i < snap.items.length; i++) {
                var it = snap.items[i];
                publicItems.push({
                    storageType: it.storageType,
                    authCode: it.authCode,
                    guid: it.guid,
                    expireTime: it.expireTime,
                    code: it.code,
                    level: it.level,
                    name: it.name
                });
            }
            return JSON.stringify({
                ok: true,
                count: publicItems.length,
                items: publicItems,
                byStorage: snap.byStorage
            });
        } catch (e) {
            return JSON.stringify({ ok: false, count: 0, items: [], error: String(e) });
        }
    },

    claimGremoryCaseItems: function(storageFilter) {
        try {
            ensureThreadAttached();
            if (nativeGremoryClaim === null) {
                var gClaimOff = off('__GREMORY_CLAIM_ITEM__');
                if (gClaimOff.isNull()) {
                    return JSON.stringify({ ok: false, success: false, claimed: 0, remaining: 0, reason: "gremory_offsets_missing" });
                }
                nativeGremoryClaim = new NativeFunction(baseAddr.add(gClaimOff), 'void', ['pointer', 'pointer']);
            }

            var initialSnap = readGremoryCaseSnapshot(storageFilter);
            if (!initialSnap.ok) {
                return JSON.stringify({ ok: false, success: false, claimed: 0, remaining: 0, reason: initialSnap.reason });
            }
            if (initialSnap.items.length === 0) {
                return JSON.stringify({ ok: true, success: true, claimed: 0, attempted: 0, remaining: 0, items: [], empty: true });
            }

            var claimedCount = 0;
            var attemptedCount = 0;
            var consecutiveFail = 0;
            var claimedItems = [];

            for (var idx = 0; idx < initialSnap.items.length; idx++) {
                var target = initialSnap.items[idx];
                attemptedCount++;
                dispatchGremoryClaim(target.ptr);

                var removed = false;
                for (var wi = 0; wi < 18; wi++) {
                    Thread.sleep(0.05);
                    var curSnap = readGremoryCaseSnapshot(storageFilter);
                    if (curSnap.ok) {
                        var stillThere = false;
                        for (var j = 0; j < curSnap.items.length; j++) {
                            var ci = curSnap.items[j];
                            if (ci.storageType === target.storageType && ci.authCode === target.authCode && ci.guid === target.guid) {
                                stillThere = true;
                                break;
                            }
                        }
                        if (!stillThere) {
                            removed = true;
                            break;
                        }
                    }
                    if (wi === 8) {
                        dispatchGremoryClaim(target.ptr);
                    }
                }

                if (removed) {
                    claimedCount++;
                    consecutiveFail = 0;
                    claimedItems.push({
                        storageType: target.storageType,
                        authCode: target.authCode,
                        guid: target.guid,
                        code: target.code,
                        level: target.level,
                        name: target.name
                    });
                    Thread.sleep(0.08);
                } else {
                    consecutiveFail++;
                    if (consecutiveFail >= 2) {
                        break;
                    }
                }
            }

            var finalSnap = readGremoryCaseSnapshot(storageFilter);
            var remaining = finalSnap.ok ? finalSnap.items.length : Math.max(0, initialSnap.items.length - claimedCount);
            return JSON.stringify({
                ok: true,
                success: (claimedCount > 0 || remaining === 0),
                claimed: claimedCount,
                attempted: attemptedCount,
                remaining: remaining,
                items: claimedItems,
                empty: false,
                reason: (consecutiveFail >= 2 && remaining > 0) ? "inventory_full_or_rejected" : ""
            });
        } catch (e) {
            return JSON.stringify({ ok: false, success: false, claimed: 0, remaining: 0, error: String(e) });
        }
    },

    // =========================================================================
    // TALISMAN GATHERER (BÙA LUCK 7221 & BÙA CHAOS ASSEMBLY 7264)
    // Hướng A: Gom chồng theo ItemStackInfo (+0x58 -> +0x118 -> MaxStack +0x10)
    // Hướng B: Lôi từ Thùng đồ K -> Mở Thủ Kho (NPC 240) -> Cất gọn vào Kho đồ
    // =========================================================================
    scanTalismansInfo: function() {
        try {
            ensureThreadAttached();
            var invItems = [];
            var whItems = [];
            var gremItems = [];
            var whMainFree = [];
            var whExtFree = [];
            var stackInfo = {};
            stackInfo[String(TALISMAN_LUCK_ID)] = { seen: false, stackable: false, maxStack: 1 };
            stackInfo[String(TALISMAN_CHAOS_ASSEMBLY_ID)] = { seen: false, stackable: false, maxStack: 1 };
            var totals = {};
            totals[String(TALISMAN_LUCK_ID)] = { inventory: 0, warehouse: 0, gremory: 0 };
            totals[String(TALISMAN_CHAOS_ASSEMBLY_ID)] = { inventory: 0, warehouse: 0, gremory: 0 };

            function recordStackMeta(tid, sm) {
                var k = String(tid);
                if (!stackInfo[k]) stackInfo[k] = { seen: false, stackable: false, maxStack: 1 };
                stackInfo[k].seen = true;
                stackInfo[k].stackable = !!sm.stackable;
                stackInfo[k].maxStack = sm.maxStack || 1;
            }

            // 1. Quét Hòm đồ nhân vật (12..203)
            try {
                var p = getPlayerPtr();
                if (p && !p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (inv && !inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (itemsArr && !itemsArr.isNull()) {
                            var arrLen = 204;
                            try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) arrLen = l; } catch (eL) {}
                            for (var s = 12; s < arrLen; s++) {
                                try {
                                    var it = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!it || it.isNull()) continue;
                                    var idx = readItemIndex(it);
                                    var nm = getItemName(it) || "";
                                    var cls = classifyTalismanItem(idx, nm);
                                    if (!cls) continue;
                                    var sm = readItemStackMeta(it);
                                    recordStackMeta(cls.id, sm);
                                    invItems.push({
                                        slot: s,
                                        id: cls.id,
                                        key: cls.key,
                                        name: nm || cls.label,
                                        count: sm.count,
                                        stackable: sm.stackable,
                                        maxStack: sm.maxStack
                                    });
                                    totals[String(cls.id)].inventory += sm.count;
                                } catch (eIt) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}

            // 2. Quét Kho đồ (Thủ Kho: Main 0..119 & Ext 120..239) + danh sách ô trống thật
            var whOpen = false;
            var extWhOpen = false;
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (gui && !gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
                        if (whWin && !whWin.isNull()) {
                            var openSt = isWarehouseWindowActuallyOpen(whWin);
                            whOpen = openSt.mainOpen;
                            extWhOpen = openSt.extOpen;
                            var occupiedSlots = {};
                            var whFoundMap = {};

                            // A. Từ WarehouseWindow.Items (+0x30)
                            try {
                                var dictPtr = whWin.add(ptr('0x30')).readPointer();
                                if (dictPtr && !dictPtr.isNull()) {
                                    var entries = dictPtr.add(ptr('0x18')).readPointer();
                                    var count = dictPtr.add(ptr('0x20')).readS32();
                                    if (entries && !entries.isNull() && count > 0 && count <= 300) {
                                        for (var di = 0; di < count; di++) {
                                            try {
                                                var ent = entries.add(0x20 + di * 24);
                                                if (ent.readS32() < 0) continue;
                                                var wSlot = ent.add(0x08).readS32();
                                                var wItem = ent.add(0x10).readPointer();
                                                if (wItem && !wItem.isNull() && wSlot >= 0 && wSlot < 240) {
                                                    occupiedSlots[wSlot] = true;
                                                    var wIdx = readItemIndex(wItem);
                                                    var wNm = getItemName(wItem) || "";
                                                    var wCls = classifyTalismanItem(wIdx, wNm);
                                                    if (wCls) {
                                                        var wSm = readItemStackMeta(wItem);
                                                        recordStackMeta(wCls.id, wSm);
                                                        whFoundMap[wSlot] = {
                                                            slot: wSlot,
                                                            id: wCls.id,
                                                            key: wCls.key,
                                                            name: wNm || wCls.label,
                                                            count: wSm.count,
                                                            stackable: wSm.stackable,
                                                            maxStack: wSm.maxStack,
                                                            storage: wSlot < 120 ? "Kho chính" : "Kho mở rộng"
                                                        };
                                                    }
                                                }
                                            } catch (eWE) {}
                                        }
                                    }
                                }
                            } catch (eWI) {}

                            // B. Quét từng ItemSlot trong MainStorage (+0x58) & ExtStorage (+0x60) để xác định 100% ô trống (Parent == NULL && Item == NULL)
                            function scanStorageCells(sPtr, bStart, bEnd, freeOut, stLabel) {
                                if (!sPtr || sPtr.isNull()) return;
                                try {
                                    var startIdx = bStart;
                                    try { var stI = sPtr.add(0x28).readS32(); if (stI >= 0 && stI <= 240) startIdx = stI; } catch (eS) {}
                                    var cDict = sPtr.add(ptr('0x38')).readPointer();
                                    if (!cDict || cDict.isNull()) return;
                                    var cEnt = cDict.add(ptr('0x18')).readPointer();
                                    var cCnt = cDict.add(ptr('0x20')).readS32();
                                    if (!cEnt || cEnt.isNull() || cCnt <= 0 || cCnt > 300) return;
                                    var seenSlot = {};
                                    for (var ci = 0; ci < cCnt; ci++) {
                                        try {
                                            var ce = cEnt.add(0x20 + ci * 24);
                                            if (ce.readS32() < 0) continue;
                                            var sk = ce.add(0x08).readS32();
                                            var so = ce.add(0x10).readPointer();
                                            if (!so || so.isNull()) continue;
                                            var sn = so.add(ptr('0x20')).readS32();
                                            var rs = sn < startIdx ? (sn + startIdx) : sn;
                                            if (rs < bStart || rs >= bEnd) rs = sk;
                                            if (rs < bStart || rs >= bEnd || seenSlot[rs]) continue;
                                            seenSlot[rs] = true;

                                            var parentSlot = so.add(0x38).readPointer();
                                            var slotItem = so.add(0x48).readPointer();
                                            var itemAlive = false;
                                            if (slotItem && !slotItem.isNull()) {
                                                var isDel = 0;
                                                try { isDel = slotItem.add(0x80).readU8(); } catch (eD) {}
                                                if (isDel === 0) itemAlive = true;
                                            }
                                            var hasParent = false;
                                            if (parentSlot && !parentSlot.isNull()) {
                                                try {
                                                    var pCached = parentSlot.add(0x10).readPointer();
                                                    if (pCached && !pCached.isNull()) hasParent = true;
                                                } catch (eP) { hasParent = true; }
                                            }

                                            if (itemAlive) {
                                                occupiedSlots[rs] = true;
                                                if (!whFoundMap[rs]) {
                                                    var ciIdx = readItemIndex(slotItem);
                                                    var ciNm = getItemName(slotItem) || "";
                                                    var ciCls = classifyTalismanItem(ciIdx, ciNm);
                                                    if (ciCls) {
                                                        var ciSm = readItemStackMeta(slotItem);
                                                        recordStackMeta(ciCls.id, ciSm);
                                                        whFoundMap[rs] = {
                                                            slot: rs,
                                                            id: ciCls.id,
                                                            key: ciCls.key,
                                                            name: ciNm || ciCls.label,
                                                            count: ciSm.count,
                                                            stackable: ciSm.stackable,
                                                            maxStack: ciSm.maxStack,
                                                            storage: stLabel
                                                        };
                                                    }
                                                }
                                            } else if (!hasParent && !occupiedSlots[rs]) {
                                                freeOut.push(rs);
                                            }
                                        } catch (eC) {}
                                    }
                                } catch (eSC) {}
                            }

                            if (whOpen) {
                                try { scanStorageCells(whWin.add(ptr('0x58')).readPointer(), 0, 120, whMainFree, "Kho chính"); } catch (eM1) {}
                            }
                            if (extWhOpen) {
                                try { scanStorageCells(whWin.add(ptr('0x60')).readPointer(), 120, 240, whExtFree, "Kho mở rộng"); } catch (eE1) {}
                            }
                            whMainFree.sort(function(a, b) { return a - b; });
                            whExtFree.sort(function(a, b) { return a - b; });

                            for (var wk in whFoundMap) {
                                var wi = whFoundMap[wk];
                                whItems.push(wi);
                                totals[String(wi.id)].warehouse += wi.count;
                            }
                        }
                    }
                }
            } catch (eWH) {}

            // 3. Quét Thùng đồ K (Gremory Case) tìm Bùa Luck & Chaos Assembly
            try {
                var gSnap = readGremoryCaseSnapshot(0);
                if (gSnap && gSnap.ok && gSnap.items) {
                    for (var gi = 0; gi < gSnap.items.length; gi++) {
                        var git = gSnap.items[gi];
                        var gCls = classifyTalismanItem(git.code, git.name);
                        if (!gCls) continue;
                        gremItems.push({
                            storageType: git.storageType,
                            authCode: git.authCode,
                            guid: git.guid,
                            code: gCls.id,
                            key: gCls.key,
                            name: git.name || gCls.label
                        });
                        totals[String(gCls.id)].gremory += 1;
                    }
                }
            } catch (eGr) {}

            return JSON.stringify({
                ok: true,
                warehouseOpen: whOpen,
                extWarehouseOpen: extWhOpen,
                warehouseFreeMainCount: whMainFree.length,
                warehouseFreeExtCount: whExtFree.length,
                warehouseFreeCount: whMainFree.length + whExtFree.length,
                stackInfo: stackInfo,
                totals: totals,
                inventoryItems: invItems,
                warehouseItems: whItems,
                gremoryItems: gremItems
            });
        } catch (eTS) {
            return JSON.stringify({ ok: false, error: String(eTS) });
        }
    },

    claimGremoryTalismans: function(includeLuck, includeChaosAssembly) {
        try {
            ensureThreadAttached();
            if (nativeGremoryClaim === null) {
                var gClaimOff = off('__GREMORY_CLAIM_ITEM__');
                if (gClaimOff.isNull()) {
                    return JSON.stringify({ ok: false, claimed: 0, remaining: 0, reason: "gremory_offsets_missing" });
                }
                nativeGremoryClaim = new NativeFunction(baseAddr.add(gClaimOff), 'void', ['pointer', 'pointer']);
            }
            var wantLuck = !!includeLuck;
            var wantChaos = !!includeChaosAssembly;
            var initialSnap = readGremoryCaseSnapshot(0);
            if (!initialSnap || !initialSnap.ok) {
                return JSON.stringify({ ok: false, claimed: 0, remaining: 0, reason: initialSnap ? initialSnap.reason : "snap_failed" });
            }
            var targets = [];
            for (var i = 0; i < initialSnap.items.length; i++) {
                var it = initialSnap.items[i];
                var cls = classifyTalismanItem(it.code, it.name);
                if (!cls) continue;
                if ((cls.id === TALISMAN_LUCK_ID && wantLuck) || (cls.id === TALISMAN_CHAOS_ASSEMBLY_ID && wantChaos)) {
                    targets.push(it);
                }
            }
            if (targets.length === 0) {
                return JSON.stringify({ ok: true, claimed: 0, remaining: 0, items: [] });
            }

            var claimed = 0;
            var failStreak = 0;
            var claimedItems = [];
            for (var ti = 0; ti < targets.length; ti++) {
                var tgt = targets[ti];
                dispatchGremoryClaim(tgt.ptr);
                var removed = false;
                for (var wi = 0; wi < 18; wi++) {
                    Thread.sleep(0.05);
                    var curSnap = readGremoryCaseSnapshot(0);
                    if (curSnap && curSnap.ok) {
                        var still = false;
                        for (var j = 0; j < curSnap.items.length; j++) {
                            var ci = curSnap.items[j];
                            if (ci.storageType === tgt.storageType && ci.authCode === tgt.authCode && ci.guid === tgt.guid) {
                                still = true;
                                break;
                            }
                        }
                        if (!still) { removed = true; break; }
                    }
                    if (wi === 8) dispatchGremoryClaim(tgt.ptr);
                }
                if (removed) {
                    claimed++;
                    failStreak = 0;
                    claimedItems.push({ code: tgt.code, name: tgt.name, guid: tgt.guid });
                    Thread.sleep(0.08);
                } else {
                    failStreak++;
                    if (failStreak >= 2) break;
                }
            }
            return JSON.stringify({
                ok: true,
                claimed: claimed,
                remaining: Math.max(0, targets.length - claimed),
                items: claimedItems
            });
        } catch (eCG) {
            return JSON.stringify({ ok: false, claimed: 0, remaining: 0, error: String(eCG) });
        }
    },

    stackTalismans: function(includeLuck, includeChaosAssembly) {
        try {
            ensureThreadAttached();
            if (nativeItemStorageMove === null) {
                return JSON.stringify({ ok: false, moved: 0, error: "no_native_move_fn" });
            }
            var wantLuck = !!includeLuck;
            var wantChaos = !!includeChaosAssembly;
            var totalMoved = 0;
            var details = [];

            function wantItem(cls) {
                if (!cls) return false;
                if (cls.id === TALISMAN_LUCK_ID && wantLuck) return true;
                if (cls.id === TALISMAN_CHAOS_ASSEMBLY_ID && wantChaos) return true;
                return false;
            }

            function stackList(storageLabel, storageFlag, itemsList) {
                var groups = {};
                for (var i = 0; i < itemsList.length; i++) {
                    var it = itemsList[i];
                    if (!it.stackable || it.maxStack <= 1) continue;
                    if (!groups[it.id]) groups[it.id] = [];
                    groups[it.id].push(it);
                }
                for (var gid in groups) {
                    var grp = groups[gid];
                    if (grp.length <= 1) continue;
                    grp.sort(function(a, b) { return a.slot - b.slot; });
                    var tIdx = 0;
                    for (var sIdx = 1; sIdx < grp.length; sIdx++) {
                        var src = grp[sIdx];
                        if (src.count <= 0) continue;
                        while (src.count > 0 && tIdx < sIdx) {
                            var tgt = grp[tIdx];
                            var maxSt = tgt.maxStack || 1;
                            var space = maxSt - tgt.count;
                            if (space <= 0) { tIdx++; continue; }
                            if (!src.ptr || src.ptr.isNull() || !tgt.ptr || tgt.ptr.isNull()) break;
                            if (src.slot === tgt.slot) break;
                            var toMove = Math.min(src.count, space);
                            try {
                                nativeItemStorageMove(src.ptr, storageFlag, src.slot, storageFlag, tgt.slot, ptr(0));
                                totalMoved++;
                                tgt.count += toMove;
                                src.count -= toMove;
                                details.push({
                                    storage: storageLabel,
                                    id: src.id,
                                    name: src.name,
                                    fromSlot: src.slot,
                                    toSlot: tgt.slot,
                                    amount: toMove,
                                    targetTotal: tgt.count,
                                    maxStack: maxSt
                                });
                                try { Thread.sleep(0.2); } catch (eSl) {}
                            } catch (eMv) {
                                break;
                            }
                            if (tgt.count >= maxSt) tIdx++;
                        }
                    }
                }
            }

            // 1. Gom chồng trong Hòm đồ nhân vật (flag = 0)
            var invList = [];
            try {
                var p = getPlayerPtr();
                if (p && !p.isNull()) {
                    var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                    if (inv && !inv.isNull()) {
                        var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                        if (itemsArr && !itemsArr.isNull()) {
                            var arrLen = 204;
                            try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) arrLen = l; } catch (eL) {}
                            for (var s = 12; s < arrLen; s++) {
                                try {
                                    var it = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!it || it.isNull()) continue;
                                    var idx = readItemIndex(it);
                                    var nm = getItemName(it) || "";
                                    var cls = classifyTalismanItem(idx, nm);
                                    if (!wantItem(cls)) continue;
                                    var sm = readItemStackMeta(it);
                                    invList.push({
                                        slot: s, ptr: it, id: cls.id, name: nm || cls.label,
                                        count: sm.count, stackable: sm.stackable, maxStack: sm.maxStack
                                    });
                                } catch (eI) {}
                            }
                        }
                    }
                }
            } catch (eInv) {}
            if (invList.length > 1) stackList("Hòm đồ nhân vật", 0, invList);

            // 2. Gom chồng trong Kho đồ (flag = 2) nếu Kho đang mở
            try {
                if (nativeGetGameUI !== null) {
                    var gui = nativeGetGameUI();
                    if (gui && !gui.isNull()) {
                        var whOff = off('__UI_WAREHOUSE_WINDOW__');
                        var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
                        if (whWin && !whWin.isNull() && isWarehouseWindowActuallyOpen(whWin).mainOpen) {
                            var mainWh = [];
                            var extWh = [];
                            var dictPtr = whWin.add(ptr('0x30')).readPointer();
                            if (dictPtr && !dictPtr.isNull()) {
                                var entries = dictPtr.add(ptr('0x18')).readPointer();
                                var count = dictPtr.add(ptr('0x20')).readS32();
                                if (entries && !entries.isNull() && count > 0 && count <= 300) {
                                    for (var di = 0; di < count; di++) {
                                        try {
                                            var ent = entries.add(0x20 + di * 24);
                                            if (ent.readS32() < 0) continue;
                                            var wSlot = ent.add(0x08).readS32();
                                            var wIt = ent.add(0x10).readPointer();
                                            if (!wIt || wIt.isNull() || wSlot < 0 || wSlot >= 240) continue;
                                            var wIdx = readItemIndex(wIt);
                                            var wNm = getItemName(wIt) || "";
                                            var wCls = classifyTalismanItem(wIdx, wNm);
                                            if (!wantItem(wCls)) continue;
                                            var wSm = readItemStackMeta(wIt);
                                            var obj = {
                                                slot: wSlot, ptr: wIt, id: wCls.id, name: wNm || wCls.label,
                                                count: wSm.count, stackable: wSm.stackable, maxStack: wSm.maxStack
                                            };
                                            if (wSlot < 120) mainWh.push(obj);
                                            else extWh.push(obj);
                                        } catch (eW) {}
                                    }
                                }
                            }
                            if (mainWh.length > 1) stackList("Kho chính", 2, mainWh);
                            if (extWh.length > 1) stackList("Kho mở rộng", 2, extWh);
                        }
                    }
                }
            } catch (eWH) {}

            return JSON.stringify({ ok: true, moved: totalMoved, details: details });
        } catch (eST) {
            return JSON.stringify({ ok: false, moved: 0, error: String(eST) });
        }
    },

    depositTalismansToWarehouse: function(includeLuck, includeChaosAssembly, preferExt, maxMoves) {
        try {
            ensureThreadAttached();
            if (nativeItemStorageMove === null) {
                return JSON.stringify({ ok: false, deposited: 0, error: "no_native_move_fn" });
            }
            var wantLuck = !!includeLuck;
            var wantChaos = !!includeChaosAssembly;
            var limit = (maxMoves && parseInt(maxMoves) > 0) ? parseInt(maxMoves) : 64;

            if (nativeGetGameUI === null) {
                return JSON.stringify({ ok: false, deposited: 0, error: "no_game_ui" });
            }
            var gui = nativeGetGameUI();
            if (!gui || gui.isNull()) {
                return JSON.stringify({ ok: false, deposited: 0, error: "null_game_ui" });
            }
            var whOff = off('__UI_WAREHOUSE_WINDOW__');
            var whWin = whOff.isNull() ? gui.add(ptr('0x290')).readPointer() : gui.add(whOff).readPointer();
            var openSt = isWarehouseWindowActuallyOpen(whWin);
            if (!openSt.mainOpen) {
                return JSON.stringify({ ok: false, deposited: 0, warehouseOpen: false, error: "warehouse_not_open" });
            }

            // Thu thập các ô bùa đang có trong Kho (để ưu tiên gộp chồng) & các ô trống thật
            var occupied = {};
            var partialStacks = {};
            try {
                var dictPtr = whWin.add(ptr('0x30')).readPointer();
                if (dictPtr && !dictPtr.isNull()) {
                    var entries = dictPtr.add(ptr('0x18')).readPointer();
                    var count = dictPtr.add(ptr('0x20')).readS32();
                    if (entries && !entries.isNull() && count > 0 && count <= 300) {
                        for (var di = 0; di < count; di++) {
                            try {
                                var ent = entries.add(0x20 + di * 24);
                                if (ent.readS32() < 0) continue;
                                var ws = ent.add(0x08).readS32();
                                var wi = ent.add(0x10).readPointer();
                                if (!wi || wi.isNull() || ws < 0 || ws >= 240) continue;
                                occupied[ws] = true;
                                var wIdx = readItemIndex(wi);
                                var wNm = getItemName(wi) || "";
                                var wCls = classifyTalismanItem(wIdx, wNm);
                                if (wCls) {
                                    var wSm = readItemStackMeta(wi);
                                    if (wSm.stackable && wSm.count < wSm.maxStack) {
                                        if (!partialStacks[wCls.id]) partialStacks[wCls.id] = [];
                                        partialStacks[wCls.id].push({ slot: ws, count: wSm.count, maxStack: wSm.maxStack });
                                    }
                                }
                            } catch (eWD) {}
                        }
                    }
                }
            } catch (eW0) {}

            var freeMain = [];
            var freeExt = [];
            function collectFree(sPtr, bStart, bEnd, outArr) {
                if (!sPtr || sPtr.isNull()) return;
                try {
                    var startIdx = bStart;
                    try { var s0 = sPtr.add(0x28).readS32(); if (s0 >= 0 && s0 <= 240) startIdx = s0; } catch (eS) {}
                    var cDict = sPtr.add(ptr('0x38')).readPointer();
                    if (!cDict || cDict.isNull()) return;
                    var cEnt = cDict.add(ptr('0x18')).readPointer();
                    var cCnt = cDict.add(ptr('0x20')).readS32();
                    if (!cEnt || cEnt.isNull() || cCnt <= 0 || cCnt > 300) return;
                    var seen = {};
                    for (var ci = 0; ci < cCnt; ci++) {
                        try {
                            var ce = cEnt.add(0x20 + ci * 24);
                            if (ce.readS32() < 0) continue;
                            var sk = ce.add(0x08).readS32();
                            var so = ce.add(0x10).readPointer();
                            if (!so || so.isNull()) continue;
                            var sn = so.add(ptr('0x20')).readS32();
                            var rs = sn < startIdx ? (sn + startIdx) : sn;
                            if (rs < bStart || rs >= bEnd) rs = sk;
                            if (rs < bStart || rs >= bEnd || seen[rs] || occupied[rs]) continue;
                            seen[rs] = true;
                            var pSlot = so.add(0x38).readPointer();
                            var sIt = so.add(0x48).readPointer();
                            var hasIt = false;
                            if (sIt && !sIt.isNull()) {
                                var del = 0;
                                try { del = sIt.add(0x80).readU8(); } catch (eD) {}
                                if (del === 0) hasIt = true;
                            }
                            var hasPar = false;
                            if (pSlot && !pSlot.isNull()) {
                                try {
                                    var pc = pSlot.add(0x10).readPointer();
                                    if (pc && !pc.isNull()) hasPar = true;
                                } catch (eP) { hasPar = true; }
                            }
                            if (!hasIt && !hasPar) outArr.push(rs);
                        } catch (eCI) {}
                    }
                } catch (eCF) {}
            }
            collectFree(whWin.add(ptr('0x58')).readPointer(), 0, 120, freeMain);
            if (openSt.extOpen) {
                collectFree(whWin.add(ptr('0x60')).readPointer(), 120, 240, freeExt);
            }
            freeMain.sort(function(a, b) { return a - b; });
            freeExt.sort(function(a, b) { return a - b; });
            var freeSlots = preferExt ? freeExt.concat(freeMain) : freeMain.concat(freeExt);

            // Quét bùa trong Hòm đồ nhân vật (flag = 0, slot 12..203)
            var invTargets = [];
            var p = getPlayerPtr();
            if (p && !p.isNull()) {
                var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
                if (inv && !inv.isNull()) {
                    var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
                    if (itemsArr && !itemsArr.isNull()) {
                        var arrLen = 204;
                        try { var l = itemsArr.add(0x18).readS32(); if (l > 12 && l <= 204) arrLen = l; } catch (eL) {}
                        for (var s = 12; s < arrLen; s++) {
                            try {
                                var it = itemsArr.add(0x20 + s * 8).readPointer();
                                if (!it || it.isNull()) continue;
                                var idx = readItemIndex(it);
                                var nm = getItemName(it) || "";
                                var cls = classifyTalismanItem(idx, nm);
                                if (!cls) continue;
                                if ((cls.id === TALISMAN_LUCK_ID && !wantLuck) || (cls.id === TALISMAN_CHAOS_ASSEMBLY_ID && !wantChaos)) continue;
                                var sm = readItemStackMeta(it);
                                invTargets.push({
                                    slot: s, ptr: it, id: cls.id, name: nm || cls.label,
                                    count: sm.count, stackable: sm.stackable, maxStack: sm.maxStack
                                });
                            } catch (eIT) {}
                        }
                    }
                }
            }

            var deposited = 0;
            var details = [];
            var warehouseFull = false;
            var freeIdx = 0;

            for (var k = 0; k < invTargets.length && deposited < limit; k++) {
                var srcIt = invTargets[k];
                var dstSlot = -1;
                var merged = false;

                // Ưu tiên 1: Gộp thẳng vào chồng đang có sẵn trong Kho nếu stackable & đủ chỗ
                if (srcIt.stackable && partialStacks[srcIt.id]) {
                    var psList = partialStacks[srcIt.id];
                    for (var pi = 0; pi < psList.length; pi++) {
                        if (psList[pi].count + srcIt.count <= psList[pi].maxStack) {
                            dstSlot = psList[pi].slot;
                            psList[pi].count += srcIt.count;
                            merged = true;
                            break;
                        }
                    }
                }

                // Ưu tiên 2: Cất vào ô trống tiếp theo trong Kho (bắt buộc cho Chaos Assembly không stack)
                if (dstSlot < 0) {
                    if (freeIdx >= freeSlots.length) {
                        warehouseFull = true;
                        break;
                    }
                    dstSlot = freeSlots[freeIdx++];
                    if (srcIt.stackable && srcIt.count < srcIt.maxStack) {
                        if (!partialStacks[srcIt.id]) partialStacks[srcIt.id] = [];
                        partialStacks[srcIt.id].push({ slot: dstSlot, count: srcIt.count, maxStack: srcIt.maxStack });
                    }
                }

                try {
                    nativeItemStorageMove(srcIt.ptr, 0, srcIt.slot, 2, dstSlot, ptr(0));
                    deposited++;
                    details.push({
                        id: srcIt.id,
                        name: srcIt.name,
                        count: srcIt.count,
                        fromSlot: srcIt.slot,
                        toSlot: dstSlot,
                        merged: merged
                    });
                    try { Thread.sleep(0.22); } catch (eSl2) {}
                } catch (eDep) {
                    break;
                }
            }

            return JSON.stringify({
                ok: true,
                warehouseOpen: true,
                deposited: deposited,
                remainingInInventory: Math.max(0, invTargets.length - deposited),
                warehouseFull: warehouseFull,
                details: details
            });
        } catch (eDW) {
            return JSON.stringify({ ok: false, deposited: 0, error: String(eDW) });
        }
    },

    findVaultKeeperNpc: function() {
        try {
            ensureThreadAttached();
            var localPlayer = getPlayerPtr();
            var px = -1, py = -1;
            if (localPlayer && !localPlayer.isNull()) {
                try {
                    var pCoord = localPlayer.add(off('__PLAYER_COORD__')).readPointer();
                    if (pCoord && !pCoord.isNull()) {
                        px = pCoord.add(0x10).readS32();
                        py = pCoord.add(0x14).readS32();
                    }
                } catch (ePC) {}
            }
            var typeInfo = baseAddr.add(off('__GAME_TYPE_INFO__')).readPointer();
            if (typeInfo.isNull()) return JSON.stringify({ found: false });
            var staticFields = typeInfo.add(ptr('0xB8')).readPointer();
            if (staticFields.isNull()) return JSON.stringify({ found: false });
            var gameInstance = staticFields.add(ptr('0x8')).readPointer();
            if (gameInstance.isNull()) return JSON.stringify({ found: false });
            var viewport = gameInstance.add(off('__VIEWPORT__')).readPointer();
            if (viewport.isNull()) return JSON.stringify({ found: false });
            var objDict = viewport.add(ptr('0x20')).readPointer();
            if (objDict.isNull()) return JSON.stringify({ found: false });
            var entries = objDict.add(ptr('0x18')).readPointer();
            var count = objDict.add(ptr('0x20')).readS32();
            if (entries.isNull() || count <= 0 || count > 600) return JSON.stringify({ found: false });

            var best = null;
            var bestDist = 999999;
            for (var i = 0; i < count; i++) {
                var entryAddr = entries.add(0x20 + i * 24);
                if (entryAddr.readS32() < 0) continue;
                var val = entryAddr.add(16).readPointer();
                if (val.isNull()) continue;
                var body = ptr(0);
                try {
                    if (getIl2CppClassNameSafe(val).indexOf("ViewportBody") === -1) continue;
                    body = val.add(0x18).readPointer();
                } catch (eVB) { continue; }
                if (body.isNull() || (localPlayer && !localPlayer.isNull() && body.equals(localPlayer))) continue;

                var bodyCls = "";
                try { bodyCls = getIl2CppClassNameSafe(body); } catch (eC) {}
                if (bodyCls.indexOf("PlayerBody") !== -1 || bodyCls.indexOf("CharacterBody") !== -1) continue;

                var bSkin = -1, bClass = -1, bIdx = -1;
                try { bIdx = body.add(0x20).readS32(); } catch (e1) {}
                try { bClass = body.add(0x34).readS32(); } catch (e2) {}
                try { bSkin = body.add(0x60).readS32(); } catch (e3) {}
                if (bSkin === 247 || bSkin === 249 || bClass === 247 || bClass === 249) continue;

                var bName = "";
                try {
                    var np = body.add(off('__PLAYER_NAME__')).readPointer();
                    if (!np.isNull()) {
                        var nl = np.add(0x10).readS32();
                        if (nl > 0 && nl < 64) bName = np.add(0x14).readUtf16String(nl);
                    }
                } catch (e4) {}

                var lowN = bName.toLowerCase();
                var isVaultSkin = (bSkin === 240 || bClass === 240);
                var isVaultName = (
                    lowN.indexOf("vault") !== -1 || lowN.indexOf("warehouse") !== -1 ||
                    lowN.indexOf("baú") !== -1 || lowN.indexOf("bau ") !== -1 ||
                    lowN.indexOf("thủ kho") !== -1 || lowN.indexOf("storage") !== -1
                );
                if (!isVaultSkin && !isVaultName) continue;

                var nx = 0, ny = 0;
                try {
                    var nc = body.add(off('__PLAYER_COORD__')).readPointer();
                    if (!nc.isNull()) {
                        nx = nc.add(0x10).readS32();
                        ny = nc.add(0x14).readS32();
                    }
                } catch (e5) {}
                var dist = (px >= 0 && py >= 0) ? Math.sqrt((nx - px) * (nx - px) + (ny - py) * (ny - py)) : 0;
                if (dist < bestDist) {
                    bestDist = dist;
                    best = {
                        found: true,
                        ptr: body.toString(),
                        index: bIdx,
                        skin: bSkin,
                        class_id: bClass,
                        name: bName || "Vault Keeper",
                        x: nx,
                        y: ny,
                        dist: Math.round(dist * 10) / 10
                    };
                }
            }
            return JSON.stringify(best || { found: false });
        } catch (eFV) {
            return JSON.stringify({ found: false, error: String(eFV) });
        }
    },

    closeWarehouseWindow: function() {
        try {
            pendingWarehouseWindowClose = true;
            return true;
        } catch (eCW) {
            return false;
        }
    },

    enterDevil: function(targetLevel, slot, ticketPreference) {
        try {
            ensureThreadAttached();
            var dsLevel = (targetLevel !== undefined && targetLevel !== null && parseInt(targetLevel) >= 0) ? parseInt(targetLevel) : getPlayerDevilSquareLevel();
            var itemSlot = -1;
            var isMasterTicketUsed = false;
            var tPref = (ticketPreference !== undefined && ticketPreference !== null) ? String(ticketPreference).toLowerCase().trim() : "auto";

            var charLvl = 1;
            try {
                var lpInit = getPlayerPtr();
                if (lpInit && !lpInit.isNull()) {
                    charLvl = lpInit.add(off('__PLAYER_LEVEL__')).readS32();
                }
            } catch (eLvlInit) {}
            var isMasterEligible = (charLvl >= 400 || dsLevel >= 6);

            if (slot !== undefined && slot !== null && parseInt(slot) >= 0) {
                itemSlot = parseInt(slot);
                try {
                    var p0 = getPlayerPtr();
                    if (!p0.isNull()) {
                        var inv0 = p0.add(off('__PLAYER_INVENTORY__')).readPointer();
                        if (!inv0.isNull()) {
                            var itemsArr0 = inv0.add(off('__INVENTORY_ITEMS__')).readPointer();
                            if (!itemsArr0.isNull()) {
                                var itP0 = itemsArr0.add(0x20 + itemSlot * 8).readPointer();
                                if (!itP0.isNull()) {
                                    var chk0 = checkDevilItem(itP0);
                                    if (chk0.isMaster) isMasterTicketUsed = true;
                                }
                            }
                        }
                    }
                } catch (eSlotChk) {}
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

                                var masterMainSlot = -1;
                                var masterExtSlot = -1;
                                var normalMatchedMainSlot = -1;
                                var normalMatchedExtSlot = -1;
                                var anyNormalMainSlot = -1;
                                var anyNormalExtSlot = -1;
                                var anyTicketSlot = -1;

                                for (var s = 12; s < maxSlot; s++) {
                                    var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                                    if (!itemPtr.isNull()) {
                                        var idx = readItemIndex(itemPtr);
                                        var check = checkDevilItem(itemPtr, idx);
                                        if (check.isTicket) {
                                            if (anyTicketSlot < 0) anyTicketSlot = s;
                                            var isMain = (s < 76);
                                            if (check.isMaster) {
                                                if (isMain && masterMainSlot < 0) masterMainSlot = s;
                                                else if (!isMain && masterExtSlot < 0) masterExtSlot = s;
                                            } else {
                                                var isNormMatched = (check.level === (dsLevel + 1) || check.level === 0 || (isMasterEligible && check.level >= 7));
                                                if (isNormMatched) {
                                                    if (isMain && normalMatchedMainSlot < 0) normalMatchedMainSlot = s;
                                                    else if (!isMain && normalMatchedExtSlot < 0) normalMatchedExtSlot = s;
                                                }
                                                if (isMain && anyNormalMainSlot < 0) anyNormalMainSlot = s;
                                                else if (!isMain && anyNormalExtSlot < 0) anyNormalExtSlot = s;
                                            }
                                        }
                                    }
                                }

                                var chosenMasterSlot = (masterMainSlot >= 12) ? masterMainSlot : masterExtSlot;
                                var chosenNormalMatchedSlot = (normalMatchedMainSlot >= 12) ? normalMatchedMainSlot : normalMatchedExtSlot;
                                var chosenAnyNormalSlot = (anyNormalMainSlot >= 12) ? anyNormalMainSlot : anyNormalExtSlot;

                                // Lựa chọn vé theo ticketPreference ("master", "normal", "auto")
                                // QUY TẮC MEGAMU: Vé Master vào được tất cả các level có sẵn của Devil Square!
                                if (tPref === "master") {
                                    if (chosenMasterSlot >= 12) {
                                        itemSlot = chosenMasterSlot;
                                        isMasterTicketUsed = true;
                                    } else if (chosenNormalMatchedSlot >= 12) {
                                        itemSlot = chosenNormalMatchedSlot;
                                    } else if (chosenAnyNormalSlot >= 12) {
                                        itemSlot = chosenAnyNormalSlot;
                                    } else if (anyTicketSlot >= 12) {
                                        itemSlot = anyTicketSlot;
                                    }
                                } else if (tPref === "normal") {
                                    if (chosenNormalMatchedSlot >= 12) {
                                        itemSlot = chosenNormalMatchedSlot;
                                    } else if (chosenAnyNormalSlot >= 12) {
                                        itemSlot = chosenAnyNormalSlot;
                                    } else if (chosenMasterSlot >= 12) {
                                        itemSlot = chosenMasterSlot;
                                        isMasterTicketUsed = true;
                                    } else if (anyTicketSlot >= 12) {
                                        itemSlot = anyTicketSlot;
                                    }
                                } else {
                                    // "auto": Ưu tiên vé Master (vì vé Master vào được tất cả các level có sẵn), sau đó vé thường
                                    if (chosenMasterSlot >= 12) {
                                        itemSlot = chosenMasterSlot;
                                        isMasterTicketUsed = true;
                                    } else if (chosenNormalMatchedSlot >= 12) {
                                        itemSlot = chosenNormalMatchedSlot;
                                    } else if (chosenAnyNormalSlot >= 12) {
                                        itemSlot = chosenAnyNormalSlot;
                                    } else if (anyTicketSlot >= 12) {
                                        itemSlot = anyTicketSlot;
                                    }
                                }
                            }
                        }
                    }
                } catch (eScan) {}
            }

            if (itemSlot < 12) {
                return JSON.stringify({ success: false, error: "no_ticket" });
            }

            var charon = getOrCreateCharonPtr();
            // TỰ ĐỘNG KHỞI TẠO TƯƠNG TÁC NPC CHARON (100% ZERO-MANUAL CLICK):
            // Bóc tách REA: GameServer bắt buộc phải có active session với NPC Charon (TargetNpc == Charon)
            // trước khi xử lý packet vào cổng 0x90.
            // Client thực hiện điều này qua NpcManager.GEBGEGOEFAD (RVA <RVA>), thiết lập
            // LocalPlayer + 0x430 = Charon Body và gửi packet mã hóa C3:30.
            if (charon && !charon.isNull()) {
                invokeNpcTalk(charon);
                if (nativeNpcSendTalk !== null) {
                    try { nativeNpcSendTalk(charon, ptr(0)); } catch (eNST) {}
                }
                sendCharonTalkPacket();
            } else {
                sendCharonTalkPacket();
            }

            if (itemSlot >= 0) {
                var actualSlot = (itemSlot < 12) ? (itemSlot + 12) : itemSlot;
                var relSlot = (actualSlot >= 12) ? (actualSlot - 12) : actualSlot;
                // Bóc tách REA: Client MEGAMU tại RVA <RVA> thực hiện `add dil, 0xc` trước khi ghi vào packet
                var wireSlot = (actualSlot + 12) & 0xFF;

                var charLvl = 0;
                try {
                    var lp = getPlayerPtr();
                    if (lp && !lp.isNull()) {
                        charLvl = lp.add(off('__PLAYER_LEVEL__')).readS32();
                    }
                } catch (eLvl) {}

                // Xác định chính xác cấp độ phòng Devil Square (Bóc tách REA từ TableEventEntryLevel - RVA <RVA>):
                // - Cấp phòng chuẩn theo level nhân vật: dsLevel (0..5 tương ứng DS 1..6, hoặc 6 cho DS 7).
                // - Vé Master vào được tất cả các level có sẵn. Khi dùng vé Master, gửi cả cấp phòng dsLevel
                //   và cấp phòng 6 (Master) để GameServer luôn chấp nhận vé dù xử lý theo mốc level nhân vật hay theo mốc vé Master.
                var enterDsLevel = (charLvl >= 400 || dsLevel >= 6) ? 6 : ((dsLevel !== undefined && dsLevel !== null && dsLevel >= 0) ? dsLevel : 0);
                var levelsToSend = [enterDsLevel];
                if (isMasterTicketUsed) {
                    if (levelsToSend.indexOf(dsLevel) === -1) levelsToSend.unshift(dsLevel);
                    if (levelsToSend.indexOf(6) === -1) levelsToSend.push(6);
                } else if (charLvl >= 400 && levelsToSend.indexOf(6) === -1) {
                    levelsToSend.push(6);
                }

                // Gửi trực tiếp vào NPC và bỏ qua xác nhận (Zero-confirm)
                for (var li = 0; li < levelsToSend.length; li++) {
                    var targetDsLvl = levelsToSend[li];

                    // 1. GỌI TRỰC TIẾP CLOSURE IL2CPP NATIVE CỦA CLIENT (RVA <RVA>: DevilSquare.ECEGJEAOELA.ILEAOLLJKPG)
                    // Đây chính là hàm native được client MEGAMU gọi khi người chơi bấm nút xác nhận OK trên popup!
                    // Thực thi trực tiếp closure này trong RAM đảm bảo 100% Zero-Confirm (không hiển thị UI, không dialog)
                    if (nativeDevilClosureEnter !== null && typeof il2cpp_object_new !== 'undefined' && il2cpp_object_new !== null) {
                        try {
                            var pTIAddr = baseAddr.add(off('__DEVIL_CLOSURE_TYPE_INFO__'));
                            if (!pTIAddr.isNull()) {
                                var klass = pTIAddr.readPointer();
                                if (!klass.isNull()) {
                                    var closure = il2cpp_object_new(klass);
                                    if (!closure.isNull()) {
                                        closure.add(0x10).writeS32(targetDsLvl);
                                        closure.add(0x14).writeS32(actualSlot);
                                        nativeDevilClosureEnter(closure, 1, ptr(0));
                                    }
                                }
                            }
                        } catch (eClosure) {}
                    }

                    // 2. GỬI PACKET GIAO THỨC TẦNG MẠNG CHUẨN XÁC 100% THEO CLIENT NATIVE <RVA>:
                    // Packet mã hóa: [0xC1, 0x05, 0x5B (0x90 ^ 0xCB), targetDsLvl, wireSlot]
                    sendGSPacket([0xC1, 0x05, 0x5B, targetDsLvl, wireSlot]);
                    // Fallback raw opcode 0x90
                    sendGSPacket([0xC1, 0x05, 0x90, targetDsLvl, wireSlot]);
                    sendDevilEnterPacket(targetDsLvl, actualSlot);
                }

                return JSON.stringify({
                    success: true,
                    dsLevel: enterDsLevel,
                    slot: actualSlot,
                    wireSlot: wireSlot,
                    isMasterTicket: isMasterTicketUsed,
                    isExtended: (actualSlot >= 76)
                });
            } else {
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
                return (info.mapId === 9 || info.mapId === 32 || info.mapId === 87 || info.mapId === 120 || info.mapId === 209);
            }
        } catch (eDM) {}
        return false;
    },

    showModalBox: function(title, message, btnText) {
        return showModalBox(title, message, btnText);
    },

    teleportToEventMap: function() {
        try {
            ensureThreadAttached();
            var info = readPlayerInfoSnapshot(false);
            if (info && info.mapId !== undefined && (info.mapId === 40 || info.mapId === 53 || (info.mapId >= 82 && info.mapId <= 90))) {
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

    getInventorySummary: function(mossCategory, maxJunkLevel, cleanEquipmentTrash, allowExcellent) {
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

            var maxSlot = 204; // UserInventory.AnyInventoryEnd = 204 (không đụng Personal Shop 204..235)
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
            var cleanEquip = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true");
            var allowExc = (allowExcellent === 1 || allowExcellent === true || allowExcellent === "true");

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
                var harmRaw = itemPtr.add(0x28).readS32();
                var opt380Raw = itemPtr.add(0x2C).readS32();
                var sockOpt = hasItemSocketSlots(itemPtr) ? 1 : 0;
                var harmonyOpt = (harmRaw > 0 || opt380Raw > 0) ? (harmRaw || opt380Raw) : 0;

                var isSpecial = isDragonItem(itemPtr, itemIndex) || isDivineOrArchangelItem(itemPtr, itemIndex);
                var isKept = isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, false, cleanEquip, allowExc);
                var isSellableMossPlus = (
                    ((itemLevel >= 5 && itemLevel <= 7) || (allowExc && excOpt > 0 && itemLevel <= 7)) &&
                    !isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, 7, false, cleanEquip, allowExc)
                );
                var isExt = (s >= 76);
                var itName = getItemName(itemPtr);
                if (isSellableMossPlus) {
                    mossPlusSlots.push({
                        slot: s,
                        index: itemIndex,
                        name: itName,
                        level: itemLevel,
                        skill: skill,
                        luck: luck,
                        isExt: isExt
                    });
                }
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

    cleanInventoryJunk: function(method, protectedSlotsJson, mossCategory, includeExtended, maxJunkLevel, cleanEquipmentTrash) {
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

            // Quét tối đa AnyInventoryEnd = 204 (Main 12..75 + Ext 76..203; KHÔNG đụng Personal Shop 204..235)
            var maxSlot = cleanExt ? 204 : 76;
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
                if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, false, cleanEquipmentTrash)) {
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

    // ------------------------------------------------------------------------
    // DỌN RÁC v3 (100% NON-BLOCKING UNITY MAINTHREAD):
    // startJunkDisposal() chỉ quét RAM read-only (<1ms) rồi đẩy job vào Game.Update,
    // Python poll getJunkDisposalStatus() -> KHÔNG BAO GIỜ Thread.sleep() hay giữ Frida lock!
    // ------------------------------------------------------------------------
    startJunkDisposal: function(mode, protectedSlotsJson, mossCategory, includeExtended, maxJunkLevel, maxBatch, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent) {
        var startedAt = Date.now();
        try {
            var modeVal = String(mode || "auto").toLowerCase();
            var ignType = (ignoreTypeHeuristics === 1 || ignoreTypeHeuristics === true || ignoreTypeHeuristics === "true");
            var cleanEquip = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true");
            var allowExc = (allowExcellent === 1 || allowExcellent === true || allowExcellent === "true");
            var maxJunkLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 6;
            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var cleanExt = (includeExtended === 1 || includeExtended === true || includeExtended === "true" || includeExtended === undefined);
            var batch = (maxBatch !== undefined && maxBatch !== null && parseInt(maxBatch) > 0) ? parseInt(maxBatch) : 80;
            var ctx = readDisposalContext();
            var empty = {
                cleaned: 0, dropped: 0, sold: 0, total: 0, failed: 0, remaining: 0,
                reason: "", mode: modeVal, gsOk: ctx.gsOk, coin: { x: ctx.x, y: ctx.y },
                coord: { x: ctx.x, y: ctx.y }, merchantOpen: ctx.merchantOpen, mossOpen: ctx.mossOpen,
                failedSlots: [], serverRejected: 0, serverAccepted: 0, elapsedMs: 0
            };

            var p = getPlayerPtr();
            if (p.isNull()) { empty.reason = "no_player"; return JSON.stringify({ queued: false, done: true, result: empty }); }
            if (!ctx.gsOk && modeVal !== "sell") { empty.reason = "no_gs_connection"; return JSON.stringify({ queued: false, done: true, result: empty }); }

            var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
            if (inv.isNull()) { empty.reason = "no_inventory"; return JSON.stringify({ queued: false, done: true, result: empty }); }
            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
            if (itemsArr.isNull()) { empty.reason = "no_items_arr"; return JSON.stringify({ queued: false, done: true, result: empty }); }

            var protMap = {};
            if (protectedSlotsJson && typeof protectedSlotsJson === "string") {
                try {
                    var protArr = JSON.parse(protectedSlotsJson);
                    for (var pi = 0; pi < protArr.length; pi++) protMap[parseInt(protArr[pi])] = true;
                } catch (ePJ) {}
            }

            var maxSlot = cleanExt ? 204 : 76;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            var candidates = [];
            for (var s = 12; s < maxSlot; s++) {
                if (s < 12) continue;
                if (protMap[s]) continue;
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;
                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var luck = itemPtr.add(0x18).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var harmRaw = itemPtr.add(0x28).readS32();
                var opt380Raw = itemPtr.add(0x2C).readS32();
                var sockOpt = hasItemSocketSlots(itemPtr) ? 1 : 0;
                var harmonyOpt = (harmRaw > 0 || opt380Raw > 0) ? (harmRaw || opt380Raw) : 0;
                if (ignType) {
                    if (itemProtectionReason(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, true, cleanEquip, allowExc)) continue;
                } else if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, false, cleanEquip, allowExc)) {
                    continue;
                }
                candidates.push(s);
                if (candidates.length >= batch) break;
            }

            empty.total = candidates.length;
            empty.remaining = candidates.length;
            if (candidates.length === 0) {
                empty.reason = "no_candidates";
                empty.elapsedMs = Date.now() - startedAt;
                return JSON.stringify({ queued: false, done: true, result: empty });
            }

            if (modeVal === "sell" && !ctx.merchantOpen) {
                empty.reason = "merchant_closed";
                empty.failed = candidates.length;
                empty.failedSlots = candidates;
                empty.elapsedMs = Date.now() - startedAt;
                return JSON.stringify({ queued: false, done: true, result: empty });
            }

            _junkJobSeq += 1;
            var jid = _junkJobSeq;
            var initPhase = (modeVal === "sell") ? "sell_pass" : "drop_pass1";
            _junkDisposalJob = {
                id: jid,
                active: true,
                done: false,
                phase: initPhase,
                mode: modeVal,
                ctx: ctx,
                candidates: candidates,
                queue: candidates.slice(),
                idx: 0,
                triedSlots: [],
                passAttempted: 0,
                passStartSeq: _dropRecvSeq,
                nextActionAtMs: 0,
                verifyDeadlineMs: 0,
                dropAllowedApplied: false,
                dropped: [],
                sold: [],
                sendFailed: 0,
                attempted: 0,
                serverRejected: 0,
                serverAccepted: 0,
                startedAt: startedAt,
                result: null
            };
            return JSON.stringify({ queued: true, done: false, jobId: jid, total: candidates.length, phase: initPhase });
        } catch (eSJD) {
            return JSON.stringify({
                queued: false, done: true,
                result: { cleaned: 0, dropped: 0, sold: 0, total: 0, failed: 0, reason: "exception", error: String(eSJD), elapsedMs: Date.now() - startedAt }
            });
        }
    },

    getJunkDisposalStatus: function(jobId) {
        try {
            var job = _junkDisposalJob;
            if (!job) return JSON.stringify({ done: true, active: false, phase: "idle", result: null });
            if (jobId !== undefined && jobId !== null && parseInt(jobId) > 0 && job.id !== parseInt(jobId)) {
                return JSON.stringify({ done: true, active: false, phase: "superseded", result: null });
            }
            return JSON.stringify({
                done: !!job.done,
                active: !!job.active,
                phase: job.phase,
                jobId: job.id,
                total: job.candidates.length,
                attempted: job.attempted,
                dropped: job.dropped.length,
                sold: job.sold.length,
                result: job.done ? job.result : null
            });
        } catch (eGJDS) {
            return JSON.stringify({ done: true, active: false, phase: "error", error: String(eGJDS) });
        }
    },

    cancelJunkDisposal: function() {
        try {
            if (_junkDisposalJob && _junkDisposalJob.active && !_junkDisposalJob.done) {
                _finalizeJunkDisposalJob(_junkDisposalJob);
            }
            if (_singleDropJob && _singleDropJob.active && !_singleDropJob.done) {
                _singleDropJob.active = false;
                _singleDropJob.done = true;
            }
            return true;
        } catch (eCJD) {
            return false;
        }
    },

    startDropSingleSlot: function(slot, offX, offY) {
        try {
            var s = parseInt(slot);
            if (s < 12) return JSON.stringify({ queued: false, done: true, result: { ok: false, err: "protected_equipped_slot", slot: s } });
            var ox = parseInt(offX !== undefined ? offX : 1);
            var oy = parseInt(offY !== undefined ? offY : 0);
            var ctx = readDisposalContext();
            var itemsArr = _getLiveItemsArraySafe();
            if (!itemsArr) return JSON.stringify({ queued: false, done: true, result: { ok: false, err: "no_items_arr", slot: s } });
            var itemP = itemsArr.add(0x20 + s * 8).readPointer();
            if (itemP.isNull()) return JSON.stringify({ queued: false, done: true, result: { ok: false, err: "empty_slot", slot: s } });
            var itemIdx = readItemIndex(itemP);
            var pInfo = readItemProps(itemP);
            if (isItemProtected(itemP, itemIdx, pInfo.itemLevel, pInfo.excOpt, pInfo.ancOpt, pInfo.sockOpt, pInfo.harmonyOpt, pInfo.luck, -1, 6)) {
                return JSON.stringify({ queued: false, done: true, result: { ok: false, err: "protected_item", slot: s } });
            }
            _junkJobSeq += 1;
            var jid = _junkJobSeq;
            var dx = (ctx.x > 0) ? Math.max(1, Math.min(254, ctx.x + ox)) : 0;
            var dy = (ctx.y > 0) ? Math.max(1, Math.min(254, ctx.y + oy)) : 0;
            _singleDropJob = {
                id: jid, active: true, done: false, phase: "send1",
                slot: s, x: dx, y: dy, sent: false, startSeq: _dropRecvSeq, deadlineMs: 0, result: null
            };
            return JSON.stringify({ queued: true, done: false, jobId: jid, slot: s, x: dx, y: dy });
        } catch (eSDSS) {
            return JSON.stringify({ queued: false, done: true, result: { ok: false, err: String(eSDSS) } });
        }
    },

    getSingleDropStatus: function(jobId) {
        try {
            var sj = _singleDropJob;
            if (!sj) return JSON.stringify({ done: true, active: false, result: null });
            if (jobId !== undefined && jobId !== null && parseInt(jobId) > 0 && sj.id !== parseInt(jobId)) {
                return JSON.stringify({ done: true, active: false, result: null });
            }
            return JSON.stringify({ done: !!sj.done, active: !!sj.active, jobId: sj.id, result: sj.done ? sj.result : null });
        } catch (eGSDS) {
            return JSON.stringify({ done: true, active: false, result: { ok: false, err: String(eGSDS) } });
        }
    },

    // ------------------------------------------------------------------------
    // DỌN RÁC v2 (legacy sync fallback)
    disposeJunkItems: function(mode, protectedSlotsJson, mossCategory, includeExtended, maxJunkLevel, maxBatch, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent) {
        var startedAt = Date.now();
        try {
            ensureThreadAttached();
            var modeVal = String(mode || "auto").toLowerCase();
            var ignType = (ignoreTypeHeuristics === 1 || ignoreTypeHeuristics === true || ignoreTypeHeuristics === "true");
            var cleanEquip = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true");
            var allowExc = (allowExcellent === 1 || allowExcellent === true || allowExcellent === "true");
            var maxJunkLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 6;
            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var cleanExt = (includeExtended === 1 || includeExtended === true || includeExtended === "true" || includeExtended === undefined);
            var batch = (maxBatch !== undefined && maxBatch !== null && parseInt(maxBatch) > 0) ? parseInt(maxBatch) : 80;
            var ctx = readDisposalContext();
            var empty = {
                cleaned: 0, dropped: 0, sold: 0, total: 0, failed: 0, remaining: 0,
                reason: "", mode: modeVal, gsOk: ctx.gsOk, coin: { x: ctx.x, y: ctx.y },
                coord: { x: ctx.x, y: ctx.y }, merchantOpen: ctx.merchantOpen, mossOpen: ctx.mossOpen,
                failedSlots: [], elapsedMs: 0
            };

            var p = getPlayerPtr();
            if (p.isNull()) { empty.reason = "no_player"; return JSON.stringify(empty); }
            if (!ctx.gsOk && modeVal !== "sell") { empty.reason = "no_gs_connection"; return JSON.stringify(empty); }

            var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
            if (inv.isNull()) { empty.reason = "no_inventory"; return JSON.stringify(empty); }
            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
            if (itemsArr.isNull()) { empty.reason = "no_items_arr"; return JSON.stringify(empty); }

            var protMap = {};
            if (protectedSlotsJson && typeof protectedSlotsJson === "string") {
                try {
                    var protArr = JSON.parse(protectedSlotsJson);
                    for (var pi = 0; pi < protArr.length; pi++) protMap[parseInt(protArr[pi])] = true;
                } catch (ePJ) {}
            }

            // Quét tối đa AnyInventoryEnd = 204 (Main 12..75 + Ext 76..203; KHÔNG đụng Personal Shop 204..235)
            var maxSlot = cleanExt ? 204 : 76;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}

            var candidates = [];
            for (var s = 12; s < maxSlot; s++) {
                if (s < 12) continue;                       // GUARD 1: không đụng trang bị trên người
                if (protMap[s]) continue;                   // GUARD 2: ô có sẵn trước khi quay
                var itemPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itemPtr.isNull()) continue;
                var itemIndex = readItemIndex(itemPtr);
                var itemLevel = itemPtr.add(0x10).readS32();
                var skill = itemPtr.add(0x14).readS32();
                var luck = itemPtr.add(0x18).readS32();
                var excOpt = itemPtr.add(0x20).readS32();
                var ancOpt = itemPtr.add(0x24).readS32();
                var harmRaw = itemPtr.add(0x28).readS32();
                var opt380Raw = itemPtr.add(0x2C).readS32();
                var sockOpt = (typeof hasItemSocketSlots === "function" && hasItemSocketSlots(itemPtr)) ? 1 : 0;
                var harmonyOpt = (harmRaw > 0 || opt380Raw > 0) ? (harmRaw || opt380Raw) : 0;
                // GUARD 3: bảo vệ đồ quý. Nếu người dùng bật "bỏ qua lọc tên/loại"
                // thì chỉ áp bộ lọc thuộc tính (Exc/Set/Socket/Harmony/cấp), bỏ qua
                // isDivineOrDragonItem (vốn chặn nhầm rất nhiều đồ Moss thường).
                if (ignType) {
                    if (itemProtectionReason(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, true, cleanEquip, allowExc)) continue;
                } else if (isItemProtected(itemPtr, itemIndex, itemLevel, excOpt, ancOpt, sockOpt, harmonyOpt, luck, mossCat, maxJunkLvl, false, cleanEquip, allowExc)) {
                    continue;
                }
                candidates.push(s);
                if (candidates.length >= batch) break;
            }

            empty.total = candidates.length;
            empty.remaining = candidates.length;
            if (candidates.length === 0) {
                empty.reason = "no_candidates";
                empty.elapsedMs = Date.now() - startedAt;
                return JSON.stringify(empty);
            }

            var dropped = [];
            var sold = [];
            var sendFailed = 0;
            var attempted = 0;
            var serverRejected = 0;
            var serverAccepted = 0;

            function remainingSlots() {
                var rem = [];
                for (var i = 0; i < candidates.length; i++) {
                    var cs = candidates[i];
                    if (itemsArr.add(0x20 + cs * 8).readPointer().isNull()) continue;
                    rem.push(cs);
                }
                return rem;
            }

            // --- BƯỚC 1: DROP (vứt tại chỗ theo vòng xoắn toạ độ) ---
            if (modeVal === "drop" || modeVal === "auto" || modeVal === "both" || modeVal === "trash") {
                ensureDropAllowed();
                var pass1 = runDropPass(candidates, itemsArr, ctx, 0, 0, false);
                dropped = dropped.concat(pass1.dropped);
                sendFailed += pass1.sendFailed;
                attempted += pass1.attempted;
                serverRejected += (pass1.serverRejected || 0);
                serverAccepted += (pass1.serverAccepted || 0);

                // Thử lại các ô còn lại với toạ độ ngẫu nhiên của client (target=null -> [-2..+2])
                // (chỉ retry khi chưa bị server từ chối toàn bộ ở safe-zone, hoặc khi có ít nhất 1 món rớt được / chưa nhận reply)
                var stayed1 = remainingSlots();
                var allExplicitlyRejected = (pass1.attempted >= 2 && pass1.dropped.length === 0 && (pass1.serverRejected || 0) >= pass1.attempted);
                if (stayed1.length > 0 && !allExplicitlyRejected) {
                    var pass2 = runDropPass(stayed1, itemsArr, ctx, -1, 1, true);
                    dropped = dropped.concat(pass2.dropped);
                    sendFailed += pass2.sendFailed;
                    attempted += pass2.attempted;
                    serverRejected += (pass2.serverRejected || 0);
                    serverAccepted += (pass2.serverAccepted || 0);
                }
            }

            // --- BƯỚC 2: SELL (bán cho Merchant) nếu drop không ăn thua ---
            var afterDrop = remainingSlots();
            var wantSell = (modeVal === "sell" || (modeVal === "auto" && afterDrop.length > 0));
            if (wantSell && afterDrop.length > 0 && isMerchantWindowOpen()) {
                var sp = runSellPass(afterDrop, itemsArr);
                sold = sold.concat(sp.sold);
                sendFailed += sp.sendFailed;
                attempted += sp.attempted;
            }

            var finalRemaining = remainingSlots();
            var cleaned = dropped.length + sold.length;
            var reason = "done";
            if (cleaned === 0) {
                if (attempted === 0) reason = "not_attempted";
                else if (sendFailed === attempted) reason = "send_failed";
                else if (modeVal === "sell" && !isMerchantWindowOpen()) reason = "merchant_closed";
                else if (!isMerchantWindowOpen()) reason = "drop_blocked";   // điển hình: đang ở safe-zone (làng/Elbeland)
                else reason = "server_rejected";
            } else if (finalRemaining.length > 0) {
                reason = "partial";
            }

            return JSON.stringify({
                cleaned: cleaned,
                dropped: dropped.length,
                sold: sold.length,
                total: candidates.length,
                failed: finalRemaining.length,
                remaining: finalRemaining.length,
                reason: reason,
                mode: modeVal,
                gsOk: ctx.gsOk,
                coord: { x: ctx.x, y: ctx.y },
                merchantOpen: isMerchantWindowOpen(),
                mossOpen: ctx.mossOpen,
                droppedSlots: dropped,
                soldSlots: sold,
                failedSlots: finalRemaining,
                sendFailed: sendFailed,
                serverRejected: serverRejected,
                serverAccepted: serverAccepted,
                sendError: lastSendError,
                nativeDropBound: (nativeUserInvDrop !== null),
                elapsedMs: Date.now() - startedAt,
                error: null
            });
        } catch (eDJ) {
            return JSON.stringify({
                cleaned: 0, dropped: 0, sold: 0, total: 0, failed: 0, reason: "exception",
                error: eDJ.toString(), elapsedMs: Date.now() - startedAt
            });
        }
    },

    // ------------------------------------------------------------------------
    // PHÂN TÍCH HÒM ĐỒ: vì sao món nào bị giữ lại, món nào đủ điều kiện dọn.
    // Dùng để trả lời câu hỏi "tại sao bấm Ném mà không mất món nào".
    // ------------------------------------------------------------------------
    analyzeJunkInventory: function(protectedSlotsJson, mossCategory, maxJunkLevel, includeExtended, ignoreTypeHeuristics, cleanEquipmentTrash, allowExcellent) {
        try {
            ensureThreadAttached();
            var ignType = (ignoreTypeHeuristics === 1 || ignoreTypeHeuristics === true || ignoreTypeHeuristics === "true");
            var cleanEquip = (cleanEquipmentTrash === 1 || cleanEquipmentTrash === true || cleanEquipmentTrash === "true");
            var allowExc = (allowExcellent === 1 || allowExcellent === true || allowExcellent === "true");
            var out = {
                ok: false, total: 0, occupied: 0, junk: 0, protected: 0,
                byReason: {}, slots: [], mossOpen: false, merchantOpen: false,
                coord: { x: 0, y: 0 }, reason: "", maxJunkLevel: 6, mossCategory: -1
            };
            var p = getPlayerPtr();
            if (p.isNull()) { out.reason = "no_player"; return JSON.stringify(out); }
            var inv = p.add(off('__PLAYER_INVENTORY__')).readPointer();
            if (inv.isNull()) { out.reason = "no_inventory"; return JSON.stringify(out); }
            var itemsArr = inv.add(off('__INVENTORY_ITEMS__')).readPointer();
            if (itemsArr.isNull()) { out.reason = "no_items_arr"; return JSON.stringify(out); }

            var ctx = readDisposalContext();
            out.mossOpen = ctx.mossOpen;
            out.merchantOpen = ctx.merchantOpen;
            out.coord = { x: ctx.x, y: ctx.y };

            var mossCat = (mossCategory !== undefined && mossCategory !== null) ? parseInt(mossCategory) : -1;
            var maxJunkLvl = (maxJunkLevel !== undefined && maxJunkLevel !== null && maxJunkLevel >= 0) ? parseInt(maxJunkLevel) : 6;
            out.mossCategory = mossCat;
            out.maxJunkLevel = maxJunkLvl;

            var protMap = {};
            if (protectedSlotsJson && typeof protectedSlotsJson === "string") {
                try {
                    var protArr = JSON.parse(protectedSlotsJson);
                    for (var pi = 0; pi < protArr.length; pi++) protMap[parseInt(protArr[pi])] = true;
                } catch (ePJ) {}
            }

            var cleanExt = (includeExtended === 1 || includeExtended === true || includeExtended === "true" || includeExtended === undefined);
            // Quét tối đa AnyInventoryEnd = 204 (Main 12..75 + Ext 76..203; KHÔNG đụng Personal Shop 204..235)
            var maxSlot = cleanExt ? 204 : 76;
            try {
                var arrLen = itemsArr.add(0x18).readS32();
                if (arrLen > 12 && arrLen < maxSlot) maxSlot = arrLen;
            } catch (eLen) {}
            out.total = maxSlot - 12;

            for (var s = 12; s < maxSlot; s++) {
                var itPtr = itemsArr.add(0x20 + s * 8).readPointer();
                if (itPtr.isNull()) continue;
                out.occupied++;
                var idx = readItemIndex(itPtr);
                var lvl = itPtr.add(0x10).readS32();
                var skl = itPtr.add(0x14).readS32();
                var lck = itPtr.add(0x18).readS32();
                var exc = itPtr.add(0x20).readS32();
                var anc = itPtr.add(0x24).readS32();
                var harmRaw = itPtr.add(0x28).readS32();
                var opt380Raw = itPtr.add(0x2C).readS32();
                var sock = hasItemSocketSlots(itPtr) ? 1 : 0;
                var harm = (harmRaw > 0 || opt380Raw > 0) ? (harmRaw || opt380Raw) : 0;
                // Đọc tên khá chậm (native call) nên chỉ đọc khi thật sự cần:
                //  - khi KHÔNG bỏ lọc tên/loại (isDivineOrDragonItem cần tên để phân loại)
                //  - hoặc để hiển thị, tối đa 40 món đầu
                var nm = "";
                var why = null;
                if (!ignType) {
                    why = itemProtectionReason(itPtr, idx, lvl, exc, anc, sock, harm, lck, mossCat, maxJunkLvl, false, cleanEquip, allowExc);
                    if (!why && out.junk < 40) {
                        try { nm = getItemName(itPtr) || ""; } catch (eNm1) {}
                    }
                } else {
                    why = itemProtectionReason(itPtr, idx, lvl, exc, anc, sock, harm, lck, mossCat, maxJunkLvl, true, cleanEquip, allowExc);
                    if (!why && out.junk < 40) {
                        try { nm = getItemName(itPtr) || ""; } catch (eNm2) {}
                    }
                }
                if (protMap[s]) why = "preexisting_snapshot";
                var section = Math.floor(idx / 512);
                var entry = {
                    slot: s, index: idx, name: nm, level: lvl, skill: skl, luck: lck,
                    exc: exc, anc: anc, sock: sock, harm: harm, section: section,
                    status: why ? "protected" : "junk", reason: why || ""
                };
                out.slots.push(entry);
                if (why) {
                    out.protected++;
                    out.byReason[why] = (out.byReason[why] || 0) + 1;
                } else {
                    out.junk++;
                }
            }
            out.ok = true;
            out.reason = "done";
            return JSON.stringify(out);
        } catch (eAJ) {
            return JSON.stringify({ ok: false, reason: "exception", error: eAJ.toString(), slots: [] });
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
            var dropStartSeq = _dropRecvSeq;
            var dropped = false;
            if (nativeUserInvDrop !== null) {
                dropped = dropSlotNative(s, dropX, dropY);
            }
            if (!dropped) {
                dropped = sendDropPacket(s, dropX, dropY);
            }

            // Chờ phản hồi C1:23 / xóa item khỏi RAM (bù RTT ~225ms, tối đa 500ms)
            var verified = false;
            var serverRejected = false;
            try {
                for (var wi = 0; wi < 10; wi++) {
                    try { Thread.sleep(0.05); } catch (eSl) {}
                    var reCheck = itemsArr.add(0x20 + s * 8).readPointer();
                    if (reCheck.isNull()) {
                        verified = true;
                        break;
                    }
                    var rRec = _dropRecvBySlot[s];
                    if (rRec && rRec.seq > dropStartSeq) {
                        if (rRec.ok) { verified = true; break; }
                        else { serverRejected = true; break; }
                    }
                }
                if (!verified && !serverRejected && dropped) {
                    var retryOk = (nativeUserInvDrop !== null) ? dropSlotNative(s, 0, 0) : sendDropPacket(s, dropX, dropY);
                    if (retryOk) {
                        for (var wi2 = 0; wi2 < 8; wi2++) {
                            try { Thread.sleep(0.05); } catch (eSl2) {}
                            if (itemsArr.add(0x20 + s * 8).readPointer().isNull()) {
                                verified = true;
                                break;
                            }
                        }
                    }
                }
            } catch (eVer) {}

            return JSON.stringify({ ok: verified, sent: dropped, verified: verified, serverRejected: serverRejected, allowed: allowed, slot: s, x: dropX, y: dropY });
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

    autoLogin: function(server, account, character, password, token) {
        try {
            ensureThreadAttached();
            var s = parseInt(server || 1);
            var acc = account ? String(account) : "";
            var chr = character ? String(character) : "";
            var pwd = (password !== undefined && password !== null) ? String(password) : "";
            var tok = (token !== undefined && token !== null) ? String(token) : "";

            // Đặt lệnh vào hàng đợi Main Thread để Game.Update thực thi chính xác và an toàn tuyệt đối
            autoLoginLastStatus = { done: false, submitted: false, stage: "queued", account: acc };
            pendingAutoLogin = {
                server: s,
                account: acc,
                character: chr,
                password: pwd,
                token: tok,
                configured: false,
                submitted: false,
                serverConnected: false,
                charSelected: false,
                charsReported: false,
                inLobbyFrames: 0,
                frames: 0,
                done: false
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

    getSceneState: function() {
        try {
            ensureThreadAttached();
            if (nativeGetSceneHandler !== null) {
                var sh = nativeGetSceneHandler();
                if (!sh.isNull()) {
                    var sType = sh.add(0x20).readS32();
                    var isReady = sh.add(0x3A).readU8() === 1;
                    var worldIdx = sh.add(0x40).readS32();
                    return JSON.stringify({ ok: true, type: sType, worldReady: isReady, worldIndex: worldIdx });
                }
            }
        } catch (e) {}
        return JSON.stringify({ ok: false, type: -1, worldReady: false, worldIndex: -1 });
    },

    setTargetFps: function(fps) {
        try {
            ensureThreadAttached();
            if (nativeSetTargetFps !== null) {
                nativeSetTargetFps(parseInt(fps));
                return true;
            }
        } catch (e) {}
        return false;
    },

    getTargetFps: function() {
        try {
            ensureThreadAttached();
            if (nativeGetTargetFps !== null) {
                return nativeGetTargetFps();
            }
        } catch (e) {}
        return -1;
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
            if (userInvDropRecvHook !== null) {
                userInvDropRecvHook.detach();
                userInvDropRecvHook = null;
            }
            if (_junkDisposalJob) { _junkDisposalJob.active = false; _junkDisposalJob.done = true; }
            if (_singleDropJob) { _singleDropJob.active = false; _singleDropJob.done = true; }
        } catch (eUIDR) {}
        try {
            if (doubleGoerEnterRecvHook !== null) {
                doubleGoerEnterRecvHook.detach();
                doubleGoerEnterRecvHook = null;
            }
        } catch (eDGD) {}
        try {
            cleanupNativeTurbo();
            _nativeMirrorTurboStats.running = false;
            _nativeMirrorTurboStats.armed = false;
            freePinnedMirrorPacket();
        } catch (eMTC) {}
        try {
            if (fastTelemetryTimer !== null) {
                clearInterval(fastTelemetryTimer);
                fastTelemetryTimer = null;
            }
        } catch (e0) {}
        try {
            if (tableEventEntryLevelHook !== null) {
                tableEventEntryLevelHook.detach();
                tableEventEntryLevelHook = null;
            }
        } catch (eTEL) {}
        try {
            _suppressMirrorUiUntilMs = 0;
            if (helperUIShowDialogAddr !== null && typeof Interceptor.revert === "function") {
                Interceptor.revert(helperUIShowDialogAddr);
                helperUIShowDialogAddr = null;
                _origHelperUIShowDialog = null;
                _helperUIShowDialogCb = null;
            }
            if (helperUIShowDialogHook !== null) {
                helperUIShowDialogHook.detach();
                helperUIShowDialogHook = null;
            }
        } catch (eHSD) {}
        try {
            if (uiModalBoxShowAddr !== null && typeof Interceptor.revert === "function") {
                Interceptor.revert(uiModalBoxShowAddr);
                uiModalBoxShowAddr = null;
                _origUIModalBoxShow = null;
                _uiModalBoxShowCb = null;
            }
        } catch (eMBS) {}
        try {
            if (helperUIShowConfirmAddr !== null && typeof Interceptor.revert === "function") {
                Interceptor.revert(helperUIShowConfirmAddr);
                helperUIShowConfirmAddr = null;
            }
            if (helperUIShowConfirmHook !== null) {
                helperUIShowConfirmHook.detach();
                helperUIShowConfirmHook = null;
            }
        } catch (eHSC) {}
        try {
            try { if (mhelperShowDialogGenericHook) { mhelperShowDialogGenericHook.detach(); mhelperShowDialogGenericHook = null; } } catch(eCGH) {}
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
    def prune_dead_engines(cls):
        """Dọn dẹp triệt để các session Frida của những tiến trình PID game đã tắt (chống rò rỉ RAM)."""
        import psutil
        with cls._pool_lock:
            dead_pids = [p for p in list(cls._instances.keys()) if not psutil.pid_exists(p)]
            for p in dead_pids:
                try:
                    cls._instances[p].detach()
                except Exception:
                    pass
                cls._instances.pop(p, None)

    @classmethod
    def cleanup_all(cls):
        with cls._pool_lock:
            for pid, eng in list(cls._instances.items()):
                try:
                    eng.detach()
                except BaseException:
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
        self.auto_confirm_party: bool = True

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
        """
        Nạp Game Offsets theo kiến trúc Zero-Offset-On-Disk (RAM-Only):
        1. Ưu tiên tuyệt đối: Lấy trực tiếp từ kho RAM mã hóa của `meg_license_bridge.dll`
           (đã được Web License Server mã hóa AES-256-CBC và giải mã trong RAM).
        2. Nếu RAM chưa có offset mà license đang hợp lệ -> tự động gọi `verify_license()`
           để đồng bộ trực tuyến từ Web Server vào RAM ngay lập tức.
        3. Bản phát hành đóng gói (frozen `.exe`): TUYỆT ĐỐI KHÔNG đọc bất kỳ file
           `megamu_offsets.json` nào từ ổ cứng!
        4. Chỉ khi đang chạy mã nguồn mở (dev local, chưa đóng gói) mới cho phép fallback
           đọc `config/megamu_offsets.json` phục vụ kiểm thử nội bộ.
        """
        self.offsets = dict(DEFAULT_OFFSETS)
        main_mod = sys.modules.get("__main__")
        is_frozen = bool(
            getattr(sys, "frozen", False)
            or "__compiled__" in globals()
            or (main_mod is not None and getattr(main_mod, "__compiled__", None) is not None)
            or os.environ.get("NUITKA_ONEFILE_PARENT")
            or os.environ.get("NUITKA_ONEFILE_DIRECTORY")
        )

        # 1. Nạp từ RAM của Native C++ Security Bridge (Strict Online)
        try:
            from license_client import (
                get_secure_game_offsets,
                is_native_bridge_active,
                is_license_valid,
                verify_license,
            )
            if is_native_bridge_active():
                sec_offsets = get_secure_game_offsets()
                if not sec_offsets and is_frozen and is_license_valid():
                    try:
                        verify_license()
                        sec_offsets = get_secure_game_offsets(force_refresh=True)
                    except Exception:
                        pass
                if sec_offsets and isinstance(sec_offsets, dict):
                    for k, v in sec_offsets.items():
                        if v is not None and v != "":
                            self.offsets[k] = v
                    _safe_log(f"[MegDirectEngine] Đã nạp {len(sec_offsets)} Game Offsets trực tiếp từ RAM (Native C++ Vault).")
                    return
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi trích xuất Native RAM Offsets: {e}")

        # 2. BẢN PHÁT HÀNH ĐÓNG GÓI (.EXE): TUYỆT ĐỐI KHÔNG ĐỌC OFFSET TỪ Ổ CỨNG
        if is_frozen:
            _safe_log("[MegDirectEngine] ⚠️ Chưa có Game Offsets trong RAM — hãy kết nối mạng và Đồng Bộ / Kích Hoạt bản quyền.")
            return

        # 3. CHẾ ĐỘ DEV NỘI BỘ (chỉ hoạt động khi chạy script .py chưa đóng gói)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for p in (
            os.path.join(base_dir, "config", "megamu_offsets.json"),
            os.path.join(base_dir, "megamu_offsets.json"),
        ):
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if v is not None and v != "":
                                self.offsets[k] = v
                        _safe_log(f"[MegDirectEngine] [DEV] Đã nạp offsets từ đĩa cục bộ: {p}")
                        break
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] [DEV] Lỗi đọc offsets cục bộ: {e}")

    def _off(self, key: str, default: str = "0x0") -> str:
        val = self.offsets.get(key)
        if val is None or val == "":
            return default
        return str(val)

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
        # Đảm bảo offsets đã được nạp vào RAM (hoặc dev JSON khi chạy unittest chưa gọi _load_offsets_file)
        if len(self.offsets) <= 1:
            self._load_offsets_file()

        js = FRIDA_AGENT_JS
        o = self._off
        mapping = {
            "__GET_PLAYER__": o("get_player"),
            "__GET_GAME_UI__": o("get_game_ui"),
            "__GET_WORLD__": o("get_world"),
            "__GET_AUTO_LOGIN__": o("get_auto_login"),
            "__GET_WINDOW_HANDLER__": o("get_window_handler"),
            "__GAME_UPDATE__": o("game_update"),
            "__GAME_UI_UPDATE__": o("game_ui_update"),
            "__GAME_TYPE_INFO__": o("game_type_info"),
            "__ITEM_STORAGE_TYPE_INFO__": o("item_storage_type_info"),
            "__MLOGIN_UI_TYPE_INFO__": o("mlogin_ui_type_info"),
            "__MLOGIN_SUBMIT__": o("mlogin_submit"),
            "__MLOGIN_TOKEN_LOGIN__": o("mlogin_token_login"),
            "__SET_AUTO_LOGIN__": o("set_auto_login"),
            "__MOVE_TO__": o("move_to"),
            "__START_AUTO_MOVE__": o("start_auto_move"),
            "__STOP_AUTO_MOVE__": o("stop_auto_move"),
            "__CHAT_SEND__": o("chat_send"),
            "__CHAT_FRAME_SEND__": o("chat_frame_send"),
            "__CHAT_SEND_CMD__": o("chat_send_cmd"),
            "__COMMAND_MGR_PROCESS__": o("command_mgr_process"),
            "__STATIC_CHAT_SEND__": o("static_chat_send"),
            "__MDIALOG_CONFIRM_YES__": o("mdialog_confirm_yes"),
            "__CHAT_UPDATE__": o("chat_update"),
            "__HELPER_START__": o("helper_start"),
            "__HELPER_STOP__": o("helper_stop"),
            "__HELPER_ACTION__": o("helper_action"),
            "__HELPER_TOGGLE__": o("helper_toggle"),
            "__HELPER_SEND_BF51__": o("helper_send_bf51"),
            "__HELPER_REQ_START__": o("helper_req_start"),
            "__HELPER_REQ_STOP__": o("helper_req_stop"),
            "__UI_LOCATION_FRAME__": o("ui_location_frame"),
            "__LOCATION_HELPER_ON__": o("location_helper_on"),
            "__LOCATION_HELPER_OFF__": o("location_helper_off"),
            "__LOCATION_UPDATE_HELPER__": o("location_update_helper"),
            "__NPC_TALK__": o("npc_talk"),
            "__NPC_CLOSE_TALK__": o("npc_close_talk"),
            "__NPC_CLICK__": o("npc_click"),
            "__NPC_SEND_TALK__": o("npc_send_talk"),
            "__USER_INV_PICK_ITEM__": o("user_inv_pick_item"),
            "__LOCAL_PICK_NEAREST__": o("local_pick_nearest"),
            "__GET_CONFIG__": o("get_config"),
            "__GET_USER_2FA__": o("get_user_2fa"),
            "__INV_TRASH_ITEM__": o("inv_trash_item"),
            "__INV_DROP_ITEM__": o("inv_drop_item"),
            "__INV_SELL_ITEM__": o("inv_sell_item"),
            "__USER_INV_TRASH__": o("user_inv_trash"),
            "__USER_INV_DROP__": o("user_inv_drop"),
            "__USER_INV_DROP_RECV__": o("user_inv_drop_recv"),
            "__USER_INV_ACTION__": o("user_inv_action"),
            "__USER_INV_SELL__": o("user_inv_sell"),
            "__USER_INV_SELL_5__": o("user_inv_sell_5"),
            "__ITEM_STORAGE_DROP__": o("item_storage_drop"),
            "__ITEM_STORAGE_SELL__": o("item_storage_sell"),
            "__MERCHANT_SELL_ITEM__": o("merchant_sell_item"),
            "__SLOT_QUICK_ACTION__": o("slot_quick_action"),
            "__ITEM_STORAGE_MOVE__": o("item_storage_move"),
            "__WINDOW_SHOW__": o("window_show"),
            "__WINDOW_HIDE__": o("window_hide"),
            "__WINDOW_SET_STATE__": o("window_set_state"),
            "__WINDOW_TOGGLE__": o("window_toggle"),
            "__BUTTON_PRESS__": o("button_press"),
            "__UNITY_EVENT_INVOKE__": o("unity_event_invoke"),
            "__MOSS_ROLL__": o("moss_roll"),
            "__MOSS_OPEN__": o("moss_open"),
            "__MOSS_ROLL_HANDLER__": o("moss_roll_handler"),
            "__MOSS_INIT__": o("moss_init"),
            "__MOSS_SELECT_CAT__": o("moss_select_cat"),
            "__MOSS_SEND_ROLL__": o("moss_send_roll"),
            "__MOSS_ROLL_CLICK__": o("moss_roll_click"),
            "__MOSS_WINDOW_CLOSE__": o("moss_window_close"),
            "__GAME_OBJECT_SET_ACTIVE__": o("game_object_set_active"),
            "__COMPONENT_GET_GAME_OBJECT__": o("component_get_game_object"),
            "__COMPONENT_GET_GAMEOBJECT__": o("component_get_game_object"),
            "__MIRROR_ENTER__": o("mirror_enter"),
            "__MIRROR_ENTER_ALT__": o("mirror_enter_alt"),
            "__MIRROR_NPC_CLICK__": o("mirror_npc_click"),
            "__MIRROR_IS_EVENT_MAP__": o("mirror_is_event_map"),
            "__MIRROR_IS_EVENT_MAP_ALT__": "0x0",
            "__MIRROR_TELEPORT_EVENT__": o("mirror_teleport_event"),
            "__DOUBLEGOER_TYPE_INFO__": o("doublegoer_type_info"),
            "__DEVIL_CLOSURE_ENTER__": o("devil_closure_enter"),
            "__DEVIL_CLOSURE_TYPE_INFO__": o("devil_closure_type_info"),
            "__DEVIL_ENTER__": o("devil_enter"),
            "__DEVIL_ENTER_ALT__": o("devil_enter_alt"),
            "__DEVIL_ENTER_1E__": o("devil_enter_1e"),
            "__DEVIL_NPC_CLICK__": o("devil_npc_click"),
            "__DEVIL_IS_EVENT_MAP__": o("devil_is_event_map"),
            "__TABLE_EVENT_ENTRY_LEVEL__": o("table_event_entry_level"),
            "__HELPER_UI_GET_INSTANCE__": o("helper_ui_get_instance"),
            "__HELPER_UI_SHOW_DIALOG__": o("helper_ui_show_dialog"),
            "__HELPER_UI_SHOW_CONFIRM__": o("helper_ui_show_confirm"),
            "__MODAL_MGR_GET_INSTANCE__": o("modal_manager_get_instance"),
            "__MODAL_MGR_CREATE__": o("modal_manager_create"),
            "__MODAL_BOX_SET_TEXT1__": o("modal_box_set_text1"),
            "__MODAL_BOX_SET_TEXT2__": o("modal_box_set_text2"),
            "__MODAL_BOX_SET_CONFIRM_TEXT__": o("modal_box_set_confirm_text"),
            "__MODAL_BOX_SHOW__": o("modal_box_show"),
            "__GET_GS_CONNECTION__": o("get_gs_connection"),
            "__GS_SEND__": o("gs_send"),
            "__GS_SEND_ALT__": o("gs_send_alt"),
            "__PLAYER_POINT__": o("player_point"),
            "__PLAYER_MASTER_POINT__": o("player_master_point"),
            "__PLAYER_RESET_COUNT__": o("player_reset_count"),
            "__PLAYER_NAME__": o("player_name"),
            "__PLAYER_LEVEL__": o("player_level"),
            "__PLAYER_CLASS__": o("player_class"),
            "__PLAYER_COORD__": o("player_coord"),
            "__PLAYER_MOVE__": o("player_move"),
            "__PLAYER_INVENTORY__": o("player_inventory"),
            "__PLAYER_HELPER__": o("player_helper"),
            "__PLAYER_LAST_COORD__": o("player_last_coord"),
            "__AUTO_MOVE_WORKING__": o("auto_move_working"),
            "__AUTO_MOVE_TYPE__": o("auto_move_type"),
            "__AUTO_MOVE_HELPER__": o("auto_move_helper"),
            "__AUTO_MOVE_DEST__": o("auto_move_dest"),
            "__MOVE_FLAG__": o("move_flag"),
            "__HELPER_STATE__": o("helper_state"),
            "__INVENTORY_ITEMS__": o("inventory_items"),
            "__GAME_WORLD__": o("game_world"),
            "__WORLD_SCENE_INDEX__": o("world_scene_index"),
            "__VIEWPORT__": o("viewport"),
            "__PARTY_INVITE_BY_KEY__": o("party_invite_by_key"),
            "__UI_CHAT_FRAME__": o("ui_chat_frame"),
            "__UI_MOSS_WINDOW__": o("ui_moss_window"),
            "__UI_MERCHANT_WINDOW__": o("ui_merchant_window"),
            "__UI_INVENTORY_WINDOW__": o("ui_inventory_window"),
            "__UI_WAREHOUSE_WINDOW__": o("ui_warehouse_window"),
            "__GREMORY_INSTANCE_GETTER__": o("gremory_instance_getter"),
            "__GREMORY_CLAIM_ITEM__": o("gremory_claim_item"),
            "__GREMORY_TYPE_INFO__": o("gremory_type_info"),
            "__SET_TARGET_FPS__": o("set_target_framerate"),
            "__GET_TARGET_FPS__": o("get_target_framerate"),
            "__SET_VSYNC_COUNT__": o("set_vsync_count"),
            "__GET_VSYNC_COUNT__": o("get_vsync_count"),
            "__DOUBLEGOER_ENTER_RECV__": o("mirror_enter_recv"),
            "__UNITY_GET_TIME__": o("unity_get_time"),
            "__PKT_ENC_NIKINI__": o("pkt_enc_nikini"),
            "__PKT_ENC_NGJG__": o("pkt_enc_ngjg"),
            "__SOCKET_SEND_ERR__": o("socket_send_err"),
            "__TCP_SET_NODELAY__": o("tcp_set_nodelay"),
            "__GET_SCENE_HANDLER__": o("get_scene_handler"),
            "__RUNTIME_CLASS_INIT__": o("runtime_class_init"),
            "__GET_USER_ACCOUNT__": o("get_user_account"),
            "__USER_ACCOUNT_SET_USERNAME__": o("user_account_set_username"),
            "__USER_ACCOUNT_SET_TOKEN__": o("user_account_set_token"),
            "__GET_CS_CONNECTION__": o("get_cs_connection"),
            "__CS_CONNECT__": o("cs_connection_connect"),
            "__MLOGIN_SET_STATE__": o("mlogin_set_state"),
            "__AUTO_SELECT_CHARACTER__": o("auto_select_character"),
            "__UNIT_SELECT_CHARACTER__": o("unit_select_character"),
            "__UNIT_ENTRY_CHARACTER__": o("unit_entry_character"),
            "__CONNECT_SERVER_SELECT__": o("connect_server_select"),
            "__GET_HELPER_UI__": o("get_helper_ui"),
            "__INPUT_FIELD_SET_TEXT__": o("input_field_set_text"),
            "__MHELPER_SHOW_DIALOG_ID__": o("mhelper_show_dialog_id"),
            "__MHELPER_SHOW_DIALOG_GENERIC__": o("mhelper_show_dialog_generic"),
            "__USER_PARTY_SEND_RESPONSE__": o("user_party_send_response"),
            "__USER_PARTY_C2_40__": o("user_party_c2_40"),
            "__QUEST_GET_MANAGER__": o("quest_get_manager"),
            "__QUEST_INSTANCE_OFFSET__": o("quest_instance_offset"),
            "__QUEST_SEND_STATE__": o("quest_send_state"),
            "__QUEST_SEND_STATE_ALT__": o("quest_send_state_alt"),
            "__NPC_ENTER_BARRACKS__": o("npc_enter_barracks"),
            "__NPC_ENTER_REFUGE__": o("npc_enter_refuge"),
            "__PLAYER_CHANGE_UP__": o("player_change_up"),
            "__UI_QUEST_NPC_WINDOW__": o("ui_quest_npc_window"),
            "__CHAT_ADD_NOTICE__": o("chat_add_notice"),
            "__DATA_TYPE_INFO__": o("data_type_info"),
            "__DATA_GET_INSTANCE__": o("data_get_instance"),
            "__UNIT_ENTER_GATE__": o("unit_enter_gate"),
            "__ARKA_ENTER_ACHERON__": o("arka_enter_acheron"),
            "__ARKA_ENTER_ZONE__": o("arka_enter_zone"),
            "__PROTOCOL_WARP_8E__": o("protocol_warp_8e"),
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
                    elif p_type == "auto_gate_confirmed":
                        cb = getattr(self, "on_gate_confirmed_callback", None)
                        if cb:
                            try:
                                cb(payload)
                            except Exception:
                                pass
                        _safe_log(
                            f"[MegDirectEngine] PID {self.pid} AUTO-CONFIRM GATE (#{payload.get('count', 1)}): "
                            f"{payload.get('title', '')} | {payload.get('message', '')}"
                        )
                    elif p_type == "auto_party_confirmed":
                        title = payload.get("title", "")
                        msg = payload.get("message", "")
                        src = payload.get("source", "unknown")
                        now_log = time.time()
                        last_pt_log = getattr(self, "_last_party_confirm_log_time", 0.0)
                        last_pt_key = getattr(self, "_last_party_confirm_key", "")
                        cur_pt_key = f"{title}_{msg}"
                        if (now_log - last_pt_log >= 10.0) or (cur_pt_key != last_pt_key and now_log - last_pt_log >= 3.0):
                            self._last_party_confirm_log_time = now_log
                            self._last_party_confirm_key = cur_pt_key
                            _safe_log(f"[MegDirectEngine] PID {self.pid} ĐÃ TỰ ĐỘNG XÁC NHẬN LỜI MỜI PARTY [{title} - {msg}] qua {src}!")
                    elif p_type in ("mirror_turbo_entered", "mirror_turbo_timeout", "mirror_enter_recv"):
                        if p_type != "mirror_enter_recv":
                            self.last_mirror_turbo_result = payload
                        else:
                            self.last_mirror_enter_recv = payload
                        # Tự động cập nhật RTT GameServer vào TimeSyncService
                        if isinstance(payload, dict):
                            try:
                                _rtt_val = float(payload.get("rttMs", 0) or 0)
                                if _rtt_val > 0:
                                    from services.time_sync_service import get_time_sync
                                    get_time_sync().record_game_rtt(_rtt_val)
                            except Exception:
                                pass
                        cb = getattr(self, "on_mirror_turbo_event", None)
                        if callable(cb):
                            try:
                                cb(payload)
                            except Exception:
                                pass
                    elif p_type == "autologin_status":
                        self.last_autologin_status = payload
                    elif p_type == "autologin_characters_found":
                        self.last_autologin_characters = payload.get("characters", [])
                        self.last_autologin_account = payload.get("account", "")
                        cb = getattr(self, "on_autologin_characters", None)
                        if callable(cb):
                            try:
                                cb(payload.get("account", ""), payload.get("characters", []))
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

        # BẮT BUỘC phải có Game Offsets trong RAM trước khi attach (Strict Online Zero-Offset-On-Disk)
        if not (self.offsets.get("get_player") or self.offsets.get("move_to") or self.offsets.get("game_type_info")):
            self._load_offsets_file()
        if not (self.offsets.get("get_player") or self.offsets.get("move_to") or self.offsets.get("game_type_info")):
            _safe_log("[MegDirectEngine] 🔒 Từ chối attach: Chưa có Game Offsets trong RAM (cần kích hoạt & đồng bộ bản quyền trực tuyến).")
            self.is_ready = False
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

        # BẮT BUỘC phải có Game Offsets trong RAM trước khi attach (Strict Online Zero-Offset-On-Disk)
        if not (self.offsets.get("get_player") or self.offsets.get("move_to") or self.offsets.get("game_type_info")):
            self._load_offsets_file()
        if not (self.offsets.get("get_player") or self.offsets.get("move_to") or self.offsets.get("game_type_info")):
            _safe_log("[MegDirectEngine] 🔒 Từ chối attach: Chưa có Game Offsets trong RAM (cần kích hoạt & đồng bộ bản quyền trực tuyến).")
            self.is_ready = False
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

                # QUAN TRỌNG (frida-python): ScriptExportsSync.__getattr__ LUÔN trả về proxy function
                # (không bao giờ None) và tự chuyển snake_case -> camelCase khi gửi sang JS rpc.exports.
                # Nếu gọi trực tiếp bằng camelCase (vd: startNativeMirrorTurbo), Frida hạ toàn bộ về
                # chữ thường ("startnativemirrorturbo") -> RPCException("unable to find method")!
                # Do đó phải chuyển sang snake_case TRƯỚC, chỉ fallback về tên gốc nếu method JS không phải camelCase.
                import re as _re
                snake_name = _re.sub(r'(?<!^)(?=[A-Z])', '_', func_name).lower()
                candidates = [snake_name]
                if func_name != snake_name:
                    candidates.append(func_name)
                if "_" in func_name:
                    camel_name = "".join(w.capitalize() if i > 0 else w for i, w in enumerate(func_name.split("_")))
                    if camel_name not in candidates:
                        candidates.append(camel_name)

                last_err = None
                for cand in candidates:
                    fn = getattr(exports, cand, None)
                    if not fn:
                        continue
                    try:
                        return fn(*args)
                    except Exception as e_cand:
                        last_err = e_cand
                        if "unable to find method" in str(e_cand).lower():
                            continue
                        raise
                if last_err is not None:
                    raise last_err
            except Exception as e:
                err_str = str(e).lower()
                is_closed = any(k in err_str for k in ("detached", "destroyed", "script is destroyed", "closed", "transport is closing"))
                if not is_closed and "unable to find method" not in err_str:
                    _safe_log(f"[MegDirectEngine] RPC _call '{func_name}' error: {e}")
                elif is_closed:
                    _safe_log(f"[MegDirectEngine] Game client (PID {self.pid}) đã đóng hoặc ngắt kết nối.")
                # Nếu RPC lỗi do script bị mất, đánh dấu cần gắn lại
                if is_closed:
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

    def direct_move(self, target_x: int, target_y: int, bypass_angle: float = 0.0) -> bool:
        """Alias cho move_to để hỗ trợ gọi di chuyển trực tiếp an toàn."""
        return self.move_to(target_x, target_y, bypass_angle=bypass_angle)

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
        Gửi lệnh chat (chuyển map /m hoặc lệnh trong game):
        1. Ưu tiên tuyệt đối gửi qua Frida Native Hook (Unity Main Thread - Mega.Chat).
           HOÀN TOÀN NGẦM 100%, không mở khung chat trên màn hình, không click chuột, không cướp tiêu điểm.
        2. Chỉ fallback qua Background PostMessage khi force_simulator=True hoặc Frida không sẵn sàng.
        """
        cmd = str(command).strip()
        if not cmd:
            return False

        # MEGAMU chỉ hỗ trợ chuẩn lệnh /m (chuyển đổi toàn bộ /warp và /move sang /m)
        if cmd.startswith("/warp "):
            cmd = "/m " + cmd[6:]
        elif cmd == "/warp":
            cmd = "/m"
        elif cmd.startswith("/move "):
            cmd = "/m " + cmd[6:]
        elif cmd == "/move":
            cmd = "/m"

        # 1. Luôn ưu tiên tuyệt đối gửi ngầm 100% qua Frida Native Hook trên Unity Main Thread
        native_sent = False
        if self.is_ready and not force_simulator:
            try:
                if self._call("send_chat_native", cmd):
                    native_sent = True
                    time.sleep(0.12)
                    _safe_log(f"[MegDirectEngine] Đã gửi lệnh chat native ngầm (Mega.Chat): '{cmd}'")
                    return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi gọi send_chat_native: {e}")

        if native_sent and not force_simulator:
            return True

        # 2. Chỉ gửi qua Background PostMessage nếu force_simulator=True hoặc Native Hook chưa sẵn sàng
        hwnd = self.get_hwnd()
        pm_sent = False
        if hwnd and (force_simulator or not self.is_ready):
            user32 = ctypes.windll.user32
            WM_CHAR = 0x0102
            VK_RETURN = 0x0D
            try:
                # 1. Enter mở khung chat
                self.send_background_key(hwnd, VK_RETURN, 0.05)
                time.sleep(0.12)
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

        # Safeguard: Chống kích hoạt MuHelper tại Event Square (Map 53 / 40) tránh gây lỗi/popup của game
        try:
            p_inf = self.get_player_info(max_age=0.5, allow_blocking=False)
            if not p_inf:
                p_inf = self.read_player_info_via_ram()
            if p_inf:
                cur_mid = int(p_inf.get("mapId", -1))
                if cur_mid in (53, 40):
                    _safe_log(f"[MegDirectEngine] ⚠️ Đang ở Event Square (Map {cur_mid}) - Chặn bật MuHelper để tránh popup cảnh báo của game!")
                    return False
        except Exception:
            pass

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

        # Kênh 1: Native Helper Start trên Unity Main Thread (UserHelper.NEIBNPAHOJO -> packet BF:51, 00)
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

        # Kênh 1: Native Helper Stop & Packet qua Frida (UserHelper.GPPPGBCDGJP -> packet BF:51, 01)
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

    def get_player_zen(self) -> int:
        """Lấy số lượng Zen hiện có trong thùng đồ nhân vật (UserInventory +0x58). Trả về -1 nếu không đọc được."""
        if self.is_ready:
            try:
                res = self._call("getPlayerZen")
                if res is not None:
                    return int(res)
            except Exception:
                pass
        return -1

    def get_player_ruud(self) -> int:
        """Lấy số lượng Ruud hiện có trong thùng đồ nhân vật (UserInventory +0x5C). Trả về 0 nếu không đọc được."""
        if self.is_ready:
            try:
                res = self._call("getPlayerRuud")
                if res is not None:
                    return int(res)
            except Exception:
                pass
        return 0

    def get_moss_roll_status(self) -> Dict[str, Any]:
        """Lấy trạng thái thực tế của cửa sổ Moss (ready, isOpen, hasReward, itemCount, isLoading)."""
        if self.is_ready:
            try:
                res = self._call("getMossRollStatus")
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception:
                pass
        return {"ready": False, "isOpen": False, "hasReward": False, "itemCount": 0, "isLoading": False}

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
                was_open = self.is_moss_open()
                res = self._call("closeMoss")
                # Fallback OS-level Win32 ESC key CHỈ KHI bảng Moss thực sự đang mở mà chưa tắt được
                # (tránh gửi ESC khi không có cửa sổ nào mở khiến game bật bảng System Menu / Settings)
                if was_open and self.is_moss_open():
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
        1. Ưu tiên Frida RPC (findMossNpc) khi đã gắn engine để đồng nhất tuyệt đối với con trỏ tương tác NPC.
        2. Fallback đọc trực tiếp bộ nhớ RAM (ReadProcessMemory) có lọc chặt NpcBody & Skin=492 (tuyệt đối không bắt nhầm Player).
        """
        if self.is_ready:
            try:
                res = self._call("findMossNpc")
                if res and isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi RPC findMossNpc: {e}")

        return self._find_moss_npc_rpm()

    def _find_moss_npc_rpm(self) -> Dict[str, Any]:
        """Fallback quét tìm NPC Moss qua Win32 ReadProcessMemory từ Viewport.ObjectList (lọc chặt NpcBody & Skin=492)."""
        if sys.platform != "win32" or not self.pid:
            return {"found": False}
        try:
            k32 = ctypes.windll.kernel32
            hProc = k32.OpenProcess(0x0410, False, self.pid)
            if not hProc:
                return {"found": False}
            try:
                def read_ptr(addr):
                    if not addr: return 0
                    buf = ctypes.c_ulonglong()
                    if not k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 8, None):
                        return 0
                    return buf.value

                def read_i32(addr):
                    if not addr: return -1
                    buf = ctypes.c_int32()
                    if not k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 4, None):
                        return -1
                    return buf.value

                def read_u8(addr):
                    if not addr: return 0
                    buf = ctypes.c_uint8()
                    if not k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), 1, None):
                        return 0
                    return buf.value

                def read_cstr(addr, max_len=64):
                    if not addr: return ""
                    buf = ctypes.create_string_buffer(max_len)
                    if not k32.ReadProcessMemory(hProc, ctypes.c_void_p(addr), ctypes.byref(buf), max_len - 1, None):
                        return ""
                    return buf.value.decode("utf-8", errors="ignore")

                def read_klass_name(obj_addr):
                    klass = read_ptr(obj_addr)
                    if not klass: return ""
                    return read_cstr(read_ptr(klass + 0x10))

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

                gti_raw = self.offsets.get("game_type_info")
                if not gti_raw:
                    return {"found": False}
                type_info_off = int(gti_raw, 16) if isinstance(gti_raw, str) else int(gti_raw)
                vp_raw = self.offsets.get("viewport") or "0x110"
                vp_off = int(vp_raw, 16) if isinstance(vp_raw, str) else int(vp_raw)

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
                if count <= 0 or count > 600: return {"found": False}

                best = None
                best_score = -1
                best_dist = 999999

                for i in range(count):
                    entry_addr = entries + 0x20 + i * 24
                    if read_i32(entry_addr) < 0:
                        continue
                    val = read_ptr(entry_addr + 16)
                    if not val: continue
                    if "ViewportBody" not in read_klass_name(val):
                        continue
                    body = read_ptr(val + 0x18)
                    if not body: continue
                    if read_u8(body + 0xC0) != 0:
                        continue

                    b_klass = read_klass_name(body)
                    if "CharacterBody" in b_klass:
                        continue
                    if b_klass and ("NpcBody" not in b_klass and "MonsterBody" not in b_klass):
                        continue

                    b_idx = read_i32(body + 0x20)
                    if b_idx < 0: continue

                    b_class = read_i32(body + 0x34)
                    b_skin = read_i32(body + 0x60)
                    b_name = read_str(read_ptr(body + 0x28))
                    m_info = read_ptr(body + 0x138)
                    info_name = read_str(read_ptr(m_info + 0x18)) if m_info else ""
                    final_name = b_name or info_name or ""
                    low_name = final_name.lower()
                    if any(k in low_name for k in ("james", "silvia", "rhea", "leah", "lugard", "sartigan", "guard")):
                        continue

                    c_ptr = read_ptr(body + 0x68)
                    tx, ty = (read_i32(c_ptr + 0x10), read_i32(c_ptr + 0x14)) if c_ptr else (-1, -1)

                    score = 0
                    if b_skin == 492 or b_class == 492:
                        score = 300
                    elif "moss" in low_name or "gambler" in low_name:
                        score = 200
                    elif "NpcBody" in b_klass and 20 <= tx <= 25 and 222 <= ty <= 227:
                        score = 100

                    if score > 0:
                        dist = (abs(tx - 22) + abs(ty - 225)) if (tx >= 0 and ty >= 0) else 999
                        if score > best_score or (score == best_score and dist < best_dist):
                            best_score = score
                            best_dist = dist
                            best = {
                                "found": True,
                                "index": b_idx,
                                "skin": b_skin,
                                "classId": b_class,
                                "klass": b_klass,
                                "name": final_name or "Moss The Gambler",
                                "x": tx,
                                "y": ty
                            }
                if best:
                    return best
            finally:
                k32.CloseHandle(hProc)
        except Exception:
            pass
        return {"found": False}

    def interact_moss_npc(self, category_id: int = 0, force_reopen: bool = False) -> Dict[str, Any]:
        """
        Tương tác/click trực tiếp vào NPC Moss thực tế:
        Phát lệnh Native NPC Talk (Mega.NpcManager) để Server mở phiên đối thoại
        và hiển thị bảng Moss Merchant chính thức.
        """
        if self.is_ready:
            try:
                res = self._call("interactMossNpc", int(category_id), bool(force_reopen))
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

    def is_merchant_open(self) -> bool:
        """Kiểm tra xem cửa sổ Merchant Shop có đang mở trên giao diện game hay không."""
        if self.is_ready:
            try:
                return bool(self._call("isMerchantOpen"))
            except Exception:
                pass
        return False

    def sell_moss_plus_items(
        self,
        max_junk_level: int = 7,
        ignore_type_heuristics: bool = False,
        allowed_slots: Optional[List[int]] = None,
        category: Optional[int] = None,
        clean_equipment_trash: bool = True,
        sell_excellent: bool = False,
    ) -> Dict[str, Any]:
        """Tự động bán đồ rác Moss +0..+7 (và tùy chọn đồ Excellent không phải Đồ Rồng/Divine/Archangel) cho NPC thương nhân."""
        if self.is_ready:
            try:
                lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 7
                ign_val = 1 if ignore_type_heuristics else 0
                slots_val = json.dumps([int(x) for x in allowed_slots]) if (allowed_slots is not None and len(allowed_slots) > 0) else None
                cat_val = int(category) if category is not None and category >= 0 else -1
                clean_eq_val = 1 if clean_equipment_trash else 0
                sell_exc_val = 1 if sell_excellent else 0
                res_str = self._call("sellMossPlusItems", lvl_val, ign_val, slots_val, cat_val, clean_eq_val, sell_exc_val)
                if res_str:
                    return json.loads(res_str) if isinstance(res_str, str) else res_str
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi sell_moss_plus_items: {e}")
        return {"sold": 0, "error": "not_ready"}


    def _call_json(self, method: str, *args: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Gọi Frida RPC trả về JSON và parse thống nhất."""
        if not self.is_ready:
            return dict(default) if default is not None else {"success": False, "error": "not_ready"}
        try:
            res = self._call(method, *args)
            if isinstance(res, str):
                try:
                    parsed = json.loads(res)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
            if isinstance(res, dict):
                return res
            if bool(res):
                return {"success": True}
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi {method}: {e}")
            return {"success": False, "error": str(e)}
        return dict(default) if default is not None else {"success": False, "error": "unknown"}

    def pre_stage_mirror_turbo(self, slot: Optional[int] = None, measure_probe: Any = False) -> Dict[str, Any]:
        """Pre-stage (T-15s): Ghim buffer byte[5], làm nóng Lugard talk trên MainThread và tùy chọn đo 1..6 mẫu RTT."""
        arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
        if isinstance(measure_probe, bool):
            probe_arg: Any = measure_probe
        elif isinstance(measure_probe, int):
            probe_arg = max(0, min(6, measure_probe))
        else:
            probe_arg = bool(measure_probe)
        return self._call_json("preStageMirrorTurbo", arg_slot, probe_arg)

    def probe_mirror_gate(self, slot: Optional[int] = None) -> Dict[str, Any]:
        """Gửi 1 gói thăm dò EnterMirror trên MainThread để đo RTT thực và phản hồi R code."""
        arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
        return self._call_json("probeMirrorGate", arg_slot)

    def get_mirror_timing_stats(self) -> Dict[str, Any]:
        """Đọc thống kê RTT, R code, MainThread/DirectSocket hits của Mirror Sniping."""
        return self._call_json(
            "getMirrorTimingStats",
            default={"rttMs": -1, "minRttMs": -1, "lastRecvCode": -1, "mainThreadHits": 0, "directSocketHits": 0},
        )

    def arm_native_mirror_turbo(
        self,
        slot: Optional[int] = None,
        interval_ms: int = 10,
        max_duration_ms: int = 15000,
        start_at_epoch_ms: int = 0,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Nạp sẵn (Arm) snipe theo mốc epoch ms đồng bộ cho nhiều acc (MainThread + DirectSocket + FPS boost)."""
        arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
        opts_str = json.dumps(options or {})
        return self._call_json(
            "armNativeMirrorTurbo",
            arg_slot,
            int(interval_ms),
            int(max_duration_ms),
            int(start_at_epoch_ms),
            opts_str,
        )

    def start_native_mirror_turbo(
        self,
        slot: Optional[int] = None,
        interval_ms: int = 10,
        max_duration_ms: int = 15000,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Kích hoạt Turbo Sniping Native In-Process trên Unity MainThread (0ms IPC overhead, Zero-Confirm)."""
        arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
        opts_str = json.dumps(options or {}) if options else ""
        return self._call_json("startNativeMirrorTurbo", arg_slot, int(interval_ms), int(max_duration_ms), opts_str)

    def set_mirror_zero_confirm(self, enabled: bool = True) -> Dict[str, Any]:
        """Bật/tắt chế độ Zero-Confirm (bỏ qua toàn bộ popup/dialog thông báo khi cướp cổng Mirror)."""
        return self._call_json("setMirrorZeroConfirm", bool(enabled), default={"success": False})

    def stop_native_mirror_turbo(self) -> Dict[str, Any]:
        """Dừng Turbo Sniping Native In-Process và khôi phục FPS/VSync."""
        return self._call_json("stopNativeMirrorTurbo", default={"stopped": False})

    def get_native_mirror_turbo_status(self) -> Dict[str, Any]:
        """Lấy trạng thái Turbo Sniping Native In-Process."""
        return self._call_json("getNativeMirrorTurboStatus", default={"running": False, "packetsSent": 0, "entered": False})

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
                if tele and tele.get("mapId") in (40, 53, 82, 83, 84, 85, 86, 87, 88, 89, 90):
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
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Double Goer (SceneHandler.WorldIndex 82-90 theo chuẩn Mega.DoubleGoer$$PAGCDNAAHMO RVA_DYNAMIC)."""
        # 1. Thử qua Frida / Fast Telemetry nếu engine đã hook
        if self.is_ready:
            try:
                tele = self.get_player_info(max_age=0.5, allow_blocking=False)
                if tele:
                    if "inDoubleGoer" in tele:
                        return bool(tele["inDoubleGoer"])
                    if "mapId" in tele and tele["mapId"] >= 0:
                        mid = int(tele["mapId"])
                        return (82 <= mid <= 90)
                res = self._call("isMirrorEventMap")
                if isinstance(res, bool):
                    return res
            except Exception:
                pass

        # 2. Fallback Win32 ReadProcessMemory trực tiếp (100% hoạt động dù Frida chưa attach)
        try:
            info = self.read_player_info_via_ram()
            if info and "mapId" in info and info["mapId"] >= 0:
                mid = int(info["mapId"])
                return (82 <= mid <= 90)
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
                    if mid >= 0:
                        return (82 <= mid <= 90)
        except Exception:
            pass

        return False

    def get_double_goer_state(self) -> Dict[str, Any]:
        """Đọc trạng thái sự kiện Double Goer trực tiếp từ Mega.DoubleGoer_TypeInfo."""
        if self.is_ready:
            try:
                res = self._call("getDoubleGoerState")
                if isinstance(res, str):
                    return json.loads(res)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {"ok": False, "active": False, "timer": 0, "passed": 0, "maxPassed": 0}

    def scan_mirror_loot(self) -> Dict[str, Any]:
        """Quét trực tiếp Viewport.ObjectList trong RAM qua Frida để tìm Rương Bạc (541), Rương Vàng (542) và ViewportItem rơi trên đất."""
        if self.is_ready:
            try:
                res = self._call("scanMirrorChestsAndItems")
                if isinstance(res, str):
                    return json.loads(res)
                if isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi scan_mirror_loot: {e}")
        return {"ok": False, "chests": [], "items": []}

    def open_and_loot_mirror(self, chest_ptr: Any = 0, chest_index: int = -1, radius: float = 5.0) -> Dict[str, Any]:
        """Mở rương sự kiện Mirror (gửi C3:30 qua NpcManager) và nhặt vật phẩm rơi xung quanh (gửi C3:22 qua UserInventory)."""
        if self.is_ready:
            try:
                ptr_str = hex(chest_ptr) if isinstance(chest_ptr, int) and chest_ptr > 0 else str(chest_ptr or "0")
                res = self._call("interactAndLootMirror", ptr_str, int(chest_index), float(radius))
                if isinstance(res, str):
                    return json.loads(res)
                if isinstance(res, dict):
                    return res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi open_and_loot_mirror: {e}")
        return {"ok": False, "openedChest": False, "pickedCount": 0}

    def get_gremory_case_items(self, storage_filter: int = -1) -> Dict[str, Any]:
        """Đọc danh sách vật phẩm hiện có trong Thùng đồ K (Gremory Case) trực tiếp từ RAM."""
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.2)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "count": 0, "items": [], "error": "not_ready"}
        try:
            res_str = self._call("getGremoryCaseItems", int(storage_filter))
            if res_str:
                res = json.loads(res_str) if isinstance(res_str, str) else res_str
                if isinstance(res, dict):
                    return res
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi get_gremory_case_items: {e}")
        return {"ok": False, "count": 0, "items": []}

    def claim_gremory_case_items(self, storage_filter: int = -1) -> Dict[str, Any]:
        """Tự động lôi vật phẩm / quà tặng từ Thùng đồ K (Gremory Case - C1:4F:02 trên Unity MainThread) về hòm đồ chính kèm xác minh RAM từng món."""
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.25)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "success": False, "claimed": 0, "remaining": 0, "error": "not_ready"}

        # 1. Đọc & lôi trực tiếp qua Frida Native Hook (Unity MainThread - C1:4F:02) nếu danh sách đã đồng bộ sẵn trong RAM
        last_res: Dict[str, Any] = {"ok": False, "success": False, "claimed": 0, "remaining": 0}
        try:
            res_str = self._call("claimGremoryCaseItems", int(storage_filter))
            if res_str:
                res = json.loads(res_str) if isinstance(res_str, str) else res_str
                if isinstance(res, dict):
                    last_res = res
                    if res.get("claimed", 0) > 0 or res.get("remaining", 0) > 0:
                        res["method"] = "frida_native"
                        return res
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi claimGremoryCaseItems via Frida (thử 1): {e}")

        # 2. Nếu RAM hiện có 0 món, bấm nhẹ phím 'K' (0x4B) ĐÚNG 1 LẦN (KHÔNG click chuột, KHÔNG bấm ESC trước)
        #    để game client tự gửi packet đồng bộ danh sách Gremory Case từ Server về RAM, rồi đóng lại bằng phím 'K'
        hwnd = self.get_hwnd()
        opened_k = False
        if hwnd:
            try:
                self.send_background_key(hwnd, 0x4B, duration_s=0.06)
                opened_k = True
                time.sleep(0.65)
            except Exception:
                pass

        # 3. Đọc lại RAM thật sau khi đồng bộ và lôi về hòm đồ chính
        try:
            for attempt in range(2):
                try:
                    res_str = self._call("claimGremoryCaseItems", int(storage_filter))
                    if res_str:
                        res = json.loads(res_str) if isinstance(res_str, str) else res_str
                        if isinstance(res, dict):
                            last_res = res
                            if res.get("claimed", 0) > 0 or res.get("remaining", 0) > 0:
                                res["method"] = "frida_native"
                                return res
                except Exception as e:
                    _safe_log(f"[MegDirectEngine] Lỗi claimGremoryCaseItems via Frida (thử 2.{attempt + 1}): {e}")
                if attempt == 0:
                    time.sleep(0.30)
        finally:
            if opened_k and hwnd:
                try:
                    time.sleep(0.15)
                    self.send_background_key(hwnd, 0x4B, duration_s=0.05)
                except Exception:
                    pass

        if last_res.get("ok"):
            last_res["claimed"] = int(last_res.get("claimed", 0) or 0)
            last_res["method"] = "frida_native"
            return last_res
        return {"ok": False, "success": False, "claimed": 0, "error": last_res.get("reason") or last_res.get("error") or "sync_failed"}

    def scan_jewels_info(self) -> Dict[str, Any]:
        """Quét toàn bộ snapshot ngọc trong thùng đồ (chính & mở rộng) và hòm đồ."""
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.3)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "error": "not_ready"}
        try:
            res_str = self._call("scanJewelsSnapshot")
            if not res_str:
                return {"ok": False, "error": "scan_failed"}
            res = json.loads(res_str) if isinstance(res_str, str) else res_str
            return res
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi scan_jewels_info: {e}")
            return {"ok": False, "error": str(e)}

    def stack_jewel_step(self, jewel_type: Optional[str] = None) -> Dict[str, Any]:
        """Thực hiện 1 bước gộp ngọc cho loại jewel_type cụ thể (hoặc bất kỳ ngọc nào nếu None)."""
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.3)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "error": "not_ready"}
        try:
            res_str = self._call("stackJewelStep", jewel_type)
            if not res_str:
                return {"ok": False, "error": "call_failed"}
            res = json.loads(res_str) if isinstance(res_str, str) else res_str
            return res
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi stack_jewel_step: {e}")
            return {"ok": False, "error": str(e)}

    def run_auto_stack_all_jewels(
        self,
        progress_cb: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Chạy tiến trình gom ngọc nền đa luồng cho TẤT CẢ các loại ngọc:
        - Bless, Soul, Life, Chaos, Creation, Guardian, Harmony, Gemstone.
        - Quét cả Thùng đồ chính (0..119), Thùng đồ mở rộng (120..239) và Hòm đồ nhân vật (12..203).
        - Thực hiện từng bước (step-by-step) với con trỏ bộ nhớ tươi mới trước mỗi lần di chuyển.
        - Giới hạn tối đa 100 viên (100v) mỗi ô. Tuyệt đối không để mất ngọc.
        - Bỏ qua Jewel of Darkness và tất cả các loại ngọc không ghép được.
        """
        if not self.is_ready:
            try:
                self.attach()
                time.sleep(0.3)
            except Exception:
                pass
        if not self.is_ready:
            return {"ok": False, "error": "not_ready"}

        COMBINABLE_TYPES = [
            "Bless", "Soul", "Life", "Chaos", "Creation", "Guardian", "Harmony", "Gemstone"
        ]

        def _log(msg: str):
            if progress_cb:
                try:
                    progress_cb(msg)
                except Exception:
                    pass
            _safe_log(f"[AutoStackJewels] {msg}")

        # 1. Quét snapshot ban đầu
        snap = self.scan_jewels_info()
        if not snap.get("ok"):
            return snap

        total_jewels = snap.get("totalJewels", 0)
        counts = snap.get("counts", {})
        loose_counts = snap.get("looseCounts", {})
        wh_open = snap.get("warehouseOpen", False)

        loc_str = "Thùng đồ & Hòm đồ" if wh_open else "Hòm đồ nhân vật"
        if total_jewels == 0:
            return {
                "ok": True,
                "moved": 0,
                "total_moved": 0,
                "total_jewels": 0,
                "counts": {},
                "summary": f"{loc_str} không có ngọc lẻ có thể gom."
            }

        # Kiểm tra xem có loại ngọc nào có >= 2 ô lẻ không
        has_loose = any(v >= 2 for v in loose_counts.values())
        if not has_loose:
            return {
                "ok": True,
                "moved": 0,
                "total_moved": 0,
                "total_jewels": total_jewels,
                "counts": counts,
                "summary": "Tất cả các ngọc đã gọn gàng."
            }

        total_moved = 0
        details = []

        # 2. Gọi native Frida autoStackJewels gom 1 lượt duy nhất, không lặp vô tận
        try:
            res_str = self._call("autoStackJewels")
            if res_str:
                res = json.loads(res_str) if isinstance(res_str, str) else res_str
                if isinstance(res, dict) and res.get("ok"):
                    total_moved = res.get("moved", 0)
                    details = res.get("details", [])
                    for d in details:
                        st_name = d.get("storage", loc_str)
                        j_name = d.get("name", d.get("type", "Ngọc"))
                        f_slot = d.get("fromSlot", 0)
                        t_slot = d.get("toSlot", 0)
                        f_cnt = d.get("amount", 1)
                        tot = d.get("targetTotal", 100)
                        _log(f"💎 [{st_name}] Gom {j_name}: ô {f_slot} ➔ ô {t_slot} ({f_cnt}v) -> {min(100, tot)}/100v")
        except Exception as e:
            _safe_log(f"[AutoStackJewels] Lỗi gọi autoStackJewels: {e}")

        # 3. Quét snapshot kết quả sau khi gom
        final_snap = self.scan_jewels_info()
        final_counts = final_snap.get("counts", counts) if final_snap.get("ok") else counts
        final_total = final_snap.get("totalJewels", total_jewels) if final_snap.get("ok") else total_jewels

        if total_moved > 0:
            _log(f"✅ Hoàn tất gom ngọc: Đã gộp thành công {total_moved} lượt ngọc lẻ.")
        else:
            _log("✅ Hoàn tất: Các ô ngọc đã gọn gàng, không cần dồn thêm.")

        return {
            "ok": True,
            "moved": total_moved,
            "total_moved": total_moved,
            "total_jewels": final_total,
            "counts": final_counts,
            "details": details
        }

    def auto_stack_jewels(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Gom và ghép ngọc trong thùng đồ và hòm đồ nhân vật:
        - Đọc toàn bộ thông tin thùng đồ (Kho chính 0..119 & Kho mở rộng 120..239) và hòm đồ nhân vật.
        - Gom toàn bộ các loại ngọc (Bless, Soul, Life, Chaos, Creation, Guardian, Harmony, Gemstone).
        - Ghép các ngọc có ID trùng nhau tại vị trí ô chứa ngọc, tối đa 100 viên (100v) mỗi ô.
        - Tuyệt đối bảo toàn 100% ngọc. Bỏ qua Jewel of Darkness và các ngọc không ghép được.
        - Chạy nền an toàn với phản hồi thời gian thực.
        """
        return self.run_auto_stack_all_jewels(progress_cb=progress_callback)

    def enter_devil(self, level: Optional[int] = None, slot: Optional[int] = None, ticket_preference: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Gửi lệnh native vào cửa sự kiện Devil Square (không cần click NPC)."""
        if self.is_ready:
            try:
                arg_lvl = int(level) if (level is not None and int(level) >= 0) else None
                arg_slot = int(slot) if (slot is not None and int(slot) >= 0) else None
                pref = str(ticket_preference or kwargs.get("ticket_pref") or "auto").lower()
                res = self._call("enterDevil", arg_lvl, arg_slot, pref)
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
        """Kiểm tra nhân vật hiện có đang trong map sự kiện Devil Square (Map 9, 32, 87, 120, 209) hay không."""
        if self.is_ready:
            try:
                tele = self.get_player_info()
                if tele and "mapId" in tele and tele["mapId"] in (9, 32, 87, 120, 209):
                    return True
                return bool(self._call("isDevilEventMap"))
            except Exception:
                pass
        return False

    def show_modal_box(self, title: str = "DEVIL SQUARE", message: str = "Entrance is currently closed", btn_text: str = "OK") -> bool:
        """Hiển thị hộp thoại modal thông báo native trên màn hình game."""
        if self.is_ready:
            try:
                res = self._call("showModalBox", str(title), str(message), str(btn_text))
                return bool(res)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi show_modal_box: {e}")
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

    def read_party_info(self) -> Dict[str, Any]:
        """Đọc thông tin Party hiện tại từ RAM IL2CPP."""
        from meg_navigator import ProcessMemoryReader
        return ProcessMemoryReader.read_party_info(self.pid)


    def set_party_auto_mode(self, password: str = "", enable: bool = True) -> bool:
        """
        Bật/tắt chế độ tự động nhận Party qua lệnh game /re auto.
        - enable = True, password rỗng: "/re auto"
        - enable = True, password có giá trị: "/re auto <password>"
        - enable = False: "/re off"
        """
        if enable:
            p_clean = password.strip() if password else ""
            cmd = f"/re auto {p_clean}" if p_clean else "/re auto"
        else:
            cmd = "/re off"
        _safe_log(f"[MegDirectEngine] PID {self.pid} thiết lập party command: {cmd}")
        return bool(self.send_chat(cmd))

    def find_nearby_player_key(self, char_name: str) -> int:
        """Tìm targetKey (Index trong Viewport) của nhân vật có tên char_name."""
        if not self.is_ready or not char_name:
            return -1
        try:
            res = self._call("findNearbyPlayerKey", str(char_name).strip())
            if res is not None:
                return int(res)
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi find_nearby_player_key: {e}")
        return -1

    def invite_party_by_key(self, target_key: int, wait_confirm: bool = True) -> bool:
        """Gửi packet mời Party C1:40 trực tiếp tới target_key trên Unity Main Thread."""
        if not self.is_ready or target_key is None or int(target_key) < 0:
            return False
        try:
            ok = self._call("invitePartyByKey", int(target_key))
            if not ok:
                return False
            if wait_confirm:
                for _ in range(15):
                    time.sleep(0.05)
                    r = self._call_json("getPartyInviteResult")
                    if r.get("done"):
                        return bool(r.get("ok"))
            return True
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi invite_party_by_key: {e}")
            return False

    def invite_party_by_name(self, target_name: str, wait_confirm: bool = True) -> Dict[str, Any]:
        """
        Mời nhân vật vào Party bằng tên:
        1. Quét Viewport tìm targetKey của nhân vật.
        2. Điều phối nativePartyInviteByKey(targetKey) trên Game.Update (Unity Main Thread).
        """
        if not self.is_ready or not target_name:
            return {"ok": False, "error": "not_ready_or_empty_name"}
        try:
            res = self._call_json("invitePartyByName", str(target_name).strip())
            if not res.get("ok"):
                return res
            if wait_confirm:
                target_key = res.get("key", -1)
                for _ in range(15):
                    time.sleep(0.05)
                    r = self._call_json("getPartyInviteResult")
                    if r.get("done"):
                        res["invite_dispatched"] = bool(r.get("ok"))
                        res["err"] = r.get("err")
                        break
            return res
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi invite_party_by_name: {e}")
            return {"ok": False, "error": str(e)}

    def request_party(self, target_player_name: str = "") -> bool:
        """Gửi yêu cầu ghép Party: nếu truyền tên target_player_name thì Leader chủ động mời, ngược lại bật /re auto."""
        if target_player_name:
            inv = self.invite_party_by_name(target_player_name)
            if inv.get("ok"):
                return True
        return self.set_party_auto_mode(enable=True)

    def set_auto_gate_confirm(self, enabled: bool = True) -> Dict[str, Any]:
        """Bật/tắt chế độ tự động xác nhận popup cổng Gate ('Do you want to teleport?') trong 0ms."""
        self.auto_gate_confirm = bool(enabled)
        return self._call_json("setAutoGateConfirm", bool(enabled), default={"ok": False, "enabled": False, "count": 0})

    def get_auto_gate_confirm_status(self) -> Dict[str, Any]:
        """Lấy trạng thái & số lần đã Auto-Confirm cổng Gate."""
        return self._call_json("getAutoGateConfirmStatus", default={"ok": False, "enabled": False, "count": 0})

    def set_auto_confirm_party(self, enabled: bool = True) -> bool:
        """
        Bật/tắt chế độ tự động đồng ý / xác nhận lời mời Party từ các tài khoản khác.
        """
        self.auto_confirm_party = bool(enabled)
        if self.is_ready:
            try:
                return bool(self._call("setAutoConfirmParty", bool(enabled)))
            except Exception as e:
                _safe_log(f"[MegDirectEngine] PID {self.pid} set_auto_confirm_party error: {e}")
        return False

    def is_auto_confirm_party_enabled(self) -> bool:
        """Kiểm tra trạng thái auto confirm party."""
        if self.is_ready:
            try:
                return bool(self._call("isAutoConfirmPartyEnabled"))
            except Exception:
                pass
        return getattr(self, "auto_confirm_party", True)

    get_latest_telemetry = get_player_info

    def get_inventory_summary(
        self,
        category: Optional[int] = None,
        max_junk_level: int = 4,
        clean_equipment_trash: bool = False,
        allow_excellent: bool = False,
    ) -> Dict[str, Any]:
        """Lấy thông tin tổng quan hòm đồ chính (số ô trống, số đồ rác, đồ giữ lại). Hỗ trợ lọc theo danh mục Moss category, max_junk_level, clean_equipment_trash và allow_excellent."""
        if self.is_ready:
            try:
                cat_val = int(category) if category is not None and category >= 0 else -1
                lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 4
                res_str = self._call(
                    "getInventorySummary",
                    cat_val,
                    lvl_val,
                    1 if clean_equipment_trash else 0,
                    1 if allow_excellent else 0,
                )
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
        max_junk_level: int = 6,
        max_batch: int = 80,
        ignore_type_heuristics: bool = False,
        clean_equipment_trash: bool = False,
        allow_excellent: bool = False,
    ) -> Dict[str, Any]:
        """Dọn rác trong Main Inventory & Ba lô mở rộng, có xác minh từng ô.

        method:
          - "drop"/"trash"/"both" : chỉ vứt ra đất (cần đứng ngoài safe-zone)
          - "sell"                : chỉ bán cho Merchant đang mở
          - "auto"                : vứt trước, nếu server chặn thì tự bán (khuyến nghị)

        clean_equipment_trash:
          - True                  : vứt cả đồ rác của quần áo (sec 7..11) và vũ khí (sec 0..6) ngoài đồ Moss.

        Trả về dict gồm: cleaned, dropped, sold, total, failed, reason, coord, merchantOpen...
        `reason` cho biết chính xác vì sao thất bại: drop_blocked (safe-zone),
        merchant_closed, no_gs_connection, server_rejected, partial, done...
        """
        if not self.is_ready:
            return {"cleaned": 0, "dropped": 0, "sold": 0, "total": 0, "failed": 0, "reason": "not_ready", "error": "not_ready"}

        prot_json = json.dumps(protected_slots or [])
        cat_val = int(category) if category is not None and category >= 0 else -1
        ext_val = 1 if include_extended else 0
        lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 4
        clean_equip_val = 1 if clean_equipment_trash else 0

        m = str(method or "drop").lower()
        if m in ("trash", "both"):
            mode = "drop"
        elif m in ("drop", "sell", "auto"):
            mode = m
        else:
            mode = "drop"

        # Bản v3 (Non-blocking Unity MainThread): startJunkDisposal (<1ms) + poll getJunkDisposalStatus trên luồng Python.
        # TUYỆT ĐỐI không Thread.sleep() hay gọi IL2CPP GC/Unity UI từ Frida RPC thread -> 0% nguy cơ AppHangB1!
        try:
            start_str = self._call(
                "startJunkDisposal", mode, prot_json, cat_val, ext_val, lvl_val, int(max_batch),
                1 if ignore_type_heuristics else 0, clean_equip_val, 1 if allow_excellent else 0
            )
            if start_str:
                sdata = json.loads(start_str)
                if isinstance(sdata, dict):
                    if sdata.get("done") and isinstance(sdata.get("result"), dict):
                        data = sdata["result"]
                        data.setdefault("method", m)
                        data.setdefault("cleaned", int(data.get("dropped", 0)) + int(data.get("sold", 0)))
                        return data
                    if sdata.get("queued"):
                        job_id = int(sdata.get("jobId", 0) or 0)
                        total_items = int(sdata.get("total", 0) or 0)
                        deadline = time.time() + max(15.0, total_items * 0.55 + 8.0)
                        last_status = None
                        while time.time() < deadline:
                            time.sleep(0.08)
                            if not self.is_ready:
                                break
                            st_str = self._call("getJunkDisposalStatus", job_id)
                            if not st_str:
                                continue
                            st = json.loads(st_str)
                            last_status = st
                            if isinstance(st, dict) and st.get("done"):
                                res = st.get("result")
                                if isinstance(res, dict):
                                    res.setdefault("method", m)
                                    res.setdefault("cleaned", int(res.get("dropped", 0)) + int(res.get("sold", 0)))
                                    return res
                                break
                        # Timeout -> hủy an toàn trên MainThread và trả kết quả hiện có
                        try:
                            self._call("cancelJunkDisposal")
                            st_final_str = self._call("getJunkDisposalStatus", job_id)
                            if st_final_str:
                                st_final = json.loads(st_final_str)
                                if isinstance(st_final, dict) and isinstance(st_final.get("result"), dict):
                                    res = st_final["result"]
                                    res.setdefault("method", m)
                                    res.setdefault("cleaned", int(res.get("dropped", 0)) + int(res.get("sold", 0)))
                                    return res
                        except Exception:
                            pass
                        return {
                            "cleaned": int((last_status or {}).get("dropped", 0)) + int((last_status or {}).get("sold", 0)),
                            "dropped": int((last_status or {}).get("dropped", 0)),
                            "sold": int((last_status or {}).get("sold", 0)),
                            "total": total_items,
                            "reason": "timeout",
                            "method": m,
                        }
        except Exception as e:
            _safe_log(f"[MegDirectEngine] startJunkDisposal lỗi: {e}")
        return {"cleaned": 0, "dropped": 0, "sold": 0, "total": 0, "failed": 0, "reason": "error", "error": "not_ready"}

    def dispose_junk_items(
        self,
        mode: str = "auto",
        protected_slots: Optional[List[int]] = None,
        category: Optional[int] = None,
        include_extended: bool = True,
        max_junk_level: int = 6,
        max_batch: int = 80,
        ignore_type_heuristics: bool = False,
        clean_equipment_trash: bool = False,
        allow_excellent: bool = False,
    ) -> Dict[str, Any]:
        """API trực tiếp cho pipeline dọn rác v2 (vứt -> bán -> xác minh)."""
        return self.clean_inventory_junk(
            method=mode,
            protected_slots=protected_slots,
            category=category,
            include_extended=include_extended,
            max_junk_level=max_junk_level,
            max_batch=max_batch,
            ignore_type_heuristics=ignore_type_heuristics,
            clean_equipment_trash=clean_equipment_trash,
            allow_excellent=allow_excellent,
        )

    def analyze_junk_inventory(
        self,
        category: Optional[int] = None,
        max_junk_level: int = 6,
        protected_slots: Optional[List[int]] = None,
        include_extended: bool = True,
        ignore_type_heuristics: bool = False,
        clean_equipment_trash: bool = False,
        allow_excellent: bool = False,
    ) -> Dict[str, Any]:
        """Liệt kê từng món trong hòm đồ + lý do bị giữ lại (nếu có).

        Trả về: {ok, occupied, junk, protected, byReason, slots: [...], mossOpen, merchantOpen, coord}
        Mỗi slot: {slot, index, name, level, exc, anc, sock, harm, status, reason}
        reason ∈ dragon_item | divine_or_dragon | excellent | ancient | socket | harmony |
                 level_over_max | jewel_section | wrong_moss_category | preexisting_snapshot
        """
        if not self.is_ready:
            return {"ok": False, "reason": "not_ready", "slots": []}
        try:
            prot_json = json.dumps(protected_slots or [])
            cat_val = int(category) if category is not None and category >= 0 else -1
            lvl_val = int(max_junk_level) if max_junk_level is not None and max_junk_level >= 0 else 6
            ext_val = 1 if include_extended else 0
            ign_val = 1 if ignore_type_heuristics else 0
            clean_equip_val = 1 if clean_equipment_trash else 0
            allow_exc_val = 1 if allow_excellent else 0
            res_str = self._call("analyzeJunkInventory", prot_json, cat_val, lvl_val, ext_val, ign_val, clean_equip_val, allow_exc_val)
            if res_str:
                return json.loads(res_str)
        except Exception as e:
            _safe_log(f"[MegDirectEngine] Lỗi analyze_junk_inventory: {e}")
        return {"ok": False, "reason": "error", "slots": []}



    def drop_inventory_slot(self, slot: int, off_x: int = 1, off_y: int = 0) -> Dict[str, Any]:
        """Gửi lệnh vứt (drop) 1 slot cụ thể trong Main Inventory trên Unity MainThread (không treo game)."""
        if self.is_ready:
            try:
                start_str = self._call("startDropSingleSlot", int(slot), int(off_x), int(off_y))
                if start_str:
                    sdata = json.loads(start_str)
                    if isinstance(sdata, dict):
                        if sdata.get("done") and isinstance(sdata.get("result"), dict):
                            return sdata["result"]
                        if sdata.get("queued"):
                            jid = int(sdata.get("jobId", 0) or 0)
                            deadline = time.time() + 2.5
                            while time.time() < deadline:
                                time.sleep(0.06)
                                st_str = self._call("getSingleDropStatus", jid)
                                if st_str:
                                    st = json.loads(st_str)
                                    if isinstance(st, dict) and st.get("done") and isinstance(st.get("result"), dict):
                                        return st["result"]
                            return {"ok": False, "err": "timeout", "slot": int(slot)}
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

    def auto_login(self, server: int = 1, account: str = "", character: str = "", password: str = "", token: str = "") -> Dict[str, Any]:
        """Gửi lệnh AutoLogin native vào GameAssembly.dll, hỗ trợ QuickSwitch, token registry và submit mật khẩu trực tiếp."""
        if self.is_ready:
            try:
                res = self._call("autoLogin", int(server), str(account), str(character), str(password), str(token))
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi auto_login: {e}")
                return {"ok": False, "err": str(e)}
        return {"ok": False, "err": "not_ready"}

    def get_scene_state(self) -> dict:
        """Lấy trạng thái SceneHandler hiện tại (type: 2=Login, 3=Lobby, 4=Playing, worldReady: bool, worldIndex: int)."""
        if self.is_ready:
            try:
                res = self._call("getSceneState")
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception:
                pass
        return {"ok": False, "type": -1, "worldReady": False, "worldIndex": -1}

    def set_target_fps(self, fps: int = 15) -> bool:
        """Giới hạn FPS của client MEGAMU (SetTargetFrameRate) để tối ưu hóa CPU/GPU khi chạy nhiều tài khoản."""
        if self.is_ready:
            try:
                return bool(self._call("setTargetFps", int(fps)))
            except Exception:
                pass
        return False

    def get_target_fps(self) -> int:
        """Lấy target FPS hiện tại của client MEGAMU."""
        if self.is_ready:
            try:
                return int(self._call("getTargetFps"))
            except Exception:
                pass
        return -1

    def get_server_code(self) -> int:
        """Đọc Server Code thực tế mà game MEGAMU đang kết nối từ bộ nhớ RAM (GSConnection/CSConnection)."""
        if self.is_ready:
            try:
                res = self._call("getServerCode")
                if res:
                    return int(res)
            except Exception:
                pass
        return 0

    def get_autologin_status(self) -> Dict[str, Any]:
        """Lấy trạng thái thực thi AutoLogin trên Unity Main Thread."""
        if hasattr(self, "last_autologin_status") and self.last_autologin_status:
            return self.last_autologin_status
        if self.is_ready:
            try:
                res = self._call("getAutoLoginStatus")
                if res:
                    return json.loads(res) if isinstance(res, str) else res
            except Exception as e:
                pass
        return {"done": False, "submitted": False, "stage": "disconnected"}

    def get_autologin_characters(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các nhân vật đọc được từ bộ nhớ khi login vào Scene 3 (Lobby)."""
        return getattr(self, "last_autologin_characters", [])

    # ==========================================================================
    # AUTO QUEST (NHIỆM VỤ CẤP 2 / MARLON / CẤP 3) NATIVE RPC WRAPPERS
    # ==========================================================================
    def get_quest_state(self) -> Dict[str, Any]:
        """Đọc toàn bộ trạng thái QuestManager (bitmap nhiệm vụ, MonsterKillCount, ChangeUp, Zen, Quest Items)."""
        return self._call_json("getQuestState", default={"ok": False, "error": "not_ready"})

    def find_npc_by_filter(self, skin_id: int = -1, name_sub: str = "") -> Dict[str, Any]:
        """Tìm NPC trong Viewport theo Skin/Class ID (Sebina=235, Marlon=229, Devin=406, Werewolf=407, Gatekeeper=408) hoặc tên."""
        return self._call_json("findNpcByFilter", int(skin_id), str(name_sub or ""), default={"found": False})

    def talk_to_npc_by_ptr(self, npc_ptr: Any) -> Dict[str, Any]:
        """Gửi lệnh nói chuyện NPC an toàn trên Unity MainThread."""
        ptr_str = hex(npc_ptr) if isinstance(npc_ptr, int) and npc_ptr > 0 else str(npc_ptr or "0")
        return self._call_json("talkToNpcByPtr", ptr_str, default={"ok": False})

    def get_quest_npc_window_state(self) -> Dict[str, Any]:
        """Kiểm tra cửa sổ hội thoại QuestNpcWindow có đang mở và có nút Accept/Continue không."""
        return self._call_json("getQuestNpcWindowState", default={"ok": False, "isOpen": False, "hasNextBtn": False, "currentData": -1})

    def click_quest_npc_next(self, quest_index: int = -1) -> Dict[str, Any]:
        """Bấm nút Accept / Continue / OK trên MQuestNpcWindow trên Unity MainThread (kèm fallback gửi C1:A2)."""
        return self._call_json("clickQuestNpcNext", int(quest_index), default={"done": False, "ok": False, "method": "", "error": "not_ready"})

    def send_quest_state(self, quest_index: int, flag: bool = False) -> Dict[str, Any]:
        """Gửi gói C1:A2 nhận hoặc trả nhiệm vụ (quest_index: 0..6) trên Unity MainThread."""
        return self._call_json("sendQuestState", int(quest_index), bool(flag), default={"ok": False})

    def enter_quest_dungeon(self, dungeon_type: str) -> Dict[str, Any]:
        """Gửi gói C1:D0:07 vào Barracks hoặc C1:D0:08 vào Refuge trên Unity MainThread."""
        return self._call_json("enterQuestDungeon", str(dungeon_type or ""), default={"ok": False})

    def dump_world_gates(self) -> Dict[str, Any]:
        """Đọc toàn bộ bảng TableWorld.Gate và TableWorld.Move trực tiếp từ RAM game."""
        return self._call_json("dumpWorldGates", default={"ok": False, "gates": [], "moves": []})

    def get_current_tile_gate(self) -> Dict[str, Any]:
        """Kiểm tra xem ô tọa độ nhân vật đang đứng có thuộc Gate nào trong World.Gates[,] hay không."""
        return self._call_json("getCurrentTileGate", default={"ok": False, "found": False})

    def enter_gate(self, gate_id: int, x: int = -1, y: int = -1) -> Dict[str, Any]:
        """Gọi trực tiếp Mega.Unit.HJDEPLPHNBO (gửi gói C1:1C) trên Unity MainThread để đi qua Gate."""
        return self._call_json("enterGate", int(gate_id), int(x), int(y), default={"ok": False})

    def get_last_gate_enter_result(self) -> Dict[str, Any]:
        """Đọc kết quả thực thi lần gọi enter_gate gần nhất trên Unity MainThread."""
        return self._call_json("getLastGateEnterResult", default={"done": False, "ok": False})

    def enter_acheron_npc(self, zone: int = -1) -> Dict[str, Any]:
        """Gửi gói C1:F8:30 (vào Acheron) hoặc C1:F8:34 (vào zone ArkaWar) trên Unity MainThread."""
        return self._call_json("enterAcheronNpc", int(zone), default={"ok": False})

    def send_warp_8e(self, warp_type: int, param: int, extra: int = 0) -> Dict[str, Any]:
        """Gửi gói C1:8E (Protocol.EMHENMDBJIG) trên Unity MainThread."""
        return self._call_json("sendWarp8E", int(warp_type), int(param), int(extra), default={"ok": False})

    def close_quest_window(self) -> bool:
        """Đóng cửa sổ hội thoại NPC Quest nếu đang mở."""
        if self.is_ready:
            try:
                return bool(self._call("closeQuestWindow"))
            except Exception:
                pass
        return False

    # ==========================================================================
    # AUTO PK REPORT (LÍNH CANH / GUARD NPC) NATIVE RPC WRAPPERS
    # ==========================================================================
    def find_guard_npc(self) -> Dict[str, Any]:
        """Quét Viewport tìm Lính Canh gần nhất (Berdysh Guard 249 / Crossbow Guard 247 / tên Guard), loại trừ người chơi."""
        return self._call_json("findGuardNpc", default={"found": False})

    def get_pk_report_status(self) -> Dict[str, Any]:
        """Đọc trạng thái PK trực tiếp từ LocalCharacterBody (+0x528 KillerName, +0x504 DeathCount, +0x5C IsDead) & PKWindow."""
        return self._call_json(
            "getPkReportStatus",
            default={
                "ok": False,
                "hp": 0,
                "isDead": False,
                "deathCount": 0,
                "killCount": 0,
                "killerName": "",
                "mapId": -1,
                "x": 0,
                "y": 0,
                "pkWindowOpen": False,
                "autoReportConfirmCount": 0,
            },
        )

    def set_auto_confirm_report(self, enabled: bool = True, killer_name: str = "") -> Dict[str, Any]:
        """Bật/tắt tự động bấm YES cho hộp thoại xác nhận Report khi nói chuyện với Lính Canh."""
        return self._call_json(
            "setAutoConfirmReport",
            bool(enabled),
            str(killer_name or ""),
            default={"ok": False, "enabled": False},
        )

    def close_pk_window(self) -> bool:
        """Đóng cửa sổ PK / hội thoại Lính Canh (C1:31) trên Unity MainThread."""
        if self.is_ready:
            try:
                return bool(self._call("closePkWindow"))
            except Exception:
                pass
        return False

    # ==========================================================================
    # TALISMAN GATHERER (BÙA LUCK 7221 & BÙA CHAOS ASSEMBLY 7264) RPC WRAPPERS
    # ==========================================================================
    def scan_talismans_info(self) -> Dict[str, Any]:
        """Quét RAM lấy số lượng Bùa Luck (7221) & Chaos Assembly (7264), trạng thái ItemStackInfo/MaxStack và ô trống Kho."""
        return self._call_json("scanTalismansInfo", default={"ok": False, "error": "not_ready"})

    def claim_gremory_talismans(self, include_luck: bool = True, include_chaos_assembly: bool = True) -> Dict[str, Any]:
        """Lôi riêng Bùa Luck (7221) và/hoặc Bùa Chaos Assembly (7264) từ Thùng đồ K (Gremory Case)."""
        return self._call_json(
            "claimGremoryTalismans",
            bool(include_luck),
            bool(include_chaos_assembly),
            default={"ok": False, "claimed": 0, "remaining": 0},
        )

    def stack_talismans(self, include_luck: bool = True, include_chaos_assembly: bool = True) -> Dict[str, Any]:
        """Hướng A: Gom chồng các bùa có ItemStackInfo trong Hòm đồ & Kho theo đúng MaxStack từ RAM."""
        return self._call_json(
            "stackTalismans",
            bool(include_luck),
            bool(include_chaos_assembly),
            default={"ok": False, "moved": 0, "details": []},
        )

    def deposit_talismans_to_warehouse(
        self,
        include_luck: bool = True,
        include_chaos_assembly: bool = True,
        prefer_ext: bool = False,
        max_moves: int = 64,
    ) -> Dict[str, Any]:
        """Hướng B: Cất toàn bộ Bùa Luck & Bùa Chaos Assembly từ Hòm đồ vào Kho đồ (ưu tiên gộp chồng nếu stackable)."""
        return self._call_json(
            "depositTalismansToWarehouse",
            bool(include_luck),
            bool(include_chaos_assembly),
            bool(prefer_ext),
            int(max_moves),
            default={"ok": False, "deposited": 0, "details": []},
        )

    def find_vault_keeper_npc(self) -> Dict[str, Any]:
        """Quét Viewport tìm NPC Thủ Kho (Vault Keeper skin 240)."""
        return self._call_json("findVaultKeeperNpc", default={"found": False})

    def close_warehouse_window(self) -> bool:
        """Đóng cửa sổ Kho đồ (MainWindow/ExtWindow) và gửi C1:31 trên Unity MainThread."""
        if self.is_ready:
            try:
                return bool(self._call("closeWarehouseWindow"))
            except Exception:
                pass
        return False

    def pickup_ground_quest_items(
        self,
        target_ids: List[int],
        max_radius: float = 14.0,
        item_level: Optional[int] = None,
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Quét ViewportItem trên đất khớp CHÍNH XÁC Quest Item (ID + Level hoặc từ khóa tên) và gọi UserInventory.MCJFNCGIHPP trên MainThread."""
        payload = json.dumps([int(x) for x in (target_ids or [])])
        lv_arg = int(item_level) if item_level is not None else -1
        kw_payload = json.dumps([str(k) for k in (keywords or [])])
        return self._call_json("pickupGroundQuestItems", payload, float(max_radius), lv_arg, kw_payload, default={"ok": False, "pickedCount": 0, "foundItems": []})

    def get_autologin_account(self) -> str:
        """Lấy tên tài khoản tương ứng với danh sách nhân vật vừa đọc được."""
        return getattr(self, "last_autologin_account", "")

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
                had_script = self.script is not None
                if self.script:
                    try:
                        exports = getattr(self.script, "exports_sync", None)
                        if exports and hasattr(exports, "cleanup"):
                            exports.cleanup()
                    except Exception:
                        pass
                if had_script:
                    try:
                        time.sleep(0.12)
                    except BaseException:
                        pass
                if self.session:
                    try:
                        self.session.detach()
                    except Exception:
                        pass
            except BaseException:
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


