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
import threading
import atexit
from typing import Optional, Dict, Any

try:
    import frida
except ImportError:
    frida = None

def _safe_log(msg: str):
    try:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc), flush=True)
    except Exception:
        pass

DEFAULT_OFFSETS = {
    "game_module": "GameAssembly.dll",
    "get_player": "0x12310D0",
    "move_to": "0xD72750",
    "chat_send": "0x14B9250",
    "chat_update": "0x14B6AF0",
    "helper_start": "0x2A3B580",
    "helper_stop": "0x2A3C660",
    "player_name": "0x28",
    "player_level": "0x30",
    "player_class": "0x34",
    "player_coord": "0x68",
    "player_move": "0xF0",
    "player_helper": "0x1E8",
    "player_last_coord": "0x4E0",
    "move_flag": "0x3C",
    "helper_state": "0x20",
}

FRIDA_AGENT_JS = r"""
var ga = Process.getModuleByName('GameAssembly.dll');
var baseAddr = ga.base;

function off(v) { return ptr(v); }

var getPlayer = new NativeFunction(baseAddr.add(off('__GET_PLAYER__')), 'pointer', ['pointer']);
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
var sendChatMessageNative = new NativeFunction(
    baseAddr.add(off('__CHAT_SEND__')),
    'void',
    ['pointer', 'pointer', 'bool']
);
var nativeStartHelper = new NativeFunction(baseAddr.add(off('__HELPER_START__')), 'void', ['pointer', 'pointer']);
var nativeStopHelper = new NativeFunction(baseAddr.add(off('__HELPER_STOP__')), 'void', ['pointer', 'pointer']);

var coordBuf = Memory.alloc(64);
var cfInstance = null;
var pendingCommand = null;
var pendingMoveTarget = null;
var pendingHelperAction = null;
var shuttingDown = false;
var chatHook = null;

chatHook = Interceptor.attach(baseAddr.add(off('__CHAT_UPDATE__')), {
    onEnter: function(args) {
        if (shuttingDown) return;
        cfInstance = args[0];

        if (pendingMoveTarget !== null) {
            try {
                var p = getPlayer(ptr(0));
                if (!p.isNull()) {
                    var curCoord = p.add(off('__PLAYER_COORD__')).readPointer();
                    var klass = ptr(0);
                    try {
                        if (!curCoord.isNull()) klass = curCoord.readPointer();
                    } catch (e1) {}
                    if (klass.isNull()) {
                        try {
                            var lastCoord = p.add(off('__PLAYER_LAST_COORD__')).readPointer();
                            if (!lastCoord.isNull()) klass = lastCoord.readPointer();
                        } catch (e2) {}
                    }
                    if (!klass.isNull()) {
                        var target = pendingMoveTarget;
                        pendingMoveTarget = null;
                        coordBuf.writePointer(klass);
                        coordBuf.add(0x08).writePointer(ptr(0));
                        coordBuf.add(0x10).writeS32(parseInt(target.x));
                        coordBuf.add(0x14).writeS32(parseInt(target.y));
                        moveToNative(p, coordBuf, 0.0, ptr(0), 0, 1, ptr(0));
                    }
                }
            } catch (e) {}
        }

        if (pendingCommand !== null && cfInstance !== null) {
            var cmd = pendingCommand;
            pendingCommand = null;
            try {
                var str = il2cpp_string_new(Memory.allocUtf8String(cmd));
                sendChatMessageNative(cfInstance, str, 1);
                send({type: 'chat_dispatched', cmd: cmd, success: true});
            } catch (e) {
                send({type: 'chat_dispatched', cmd: cmd, success: false, error: e.toString()});
            }
        }

        if (pendingHelperAction !== null) {
            var act = pendingHelperAction;
            pendingHelperAction = null;
            try {
                var p = getPlayer(ptr(0));
                if (!p.isNull()) {
                    var h = p.add(off('__PLAYER_HELPER__')).readPointer();
                    if (!h.isNull()) {
                        if (act === 'start') nativeStartHelper(h, ptr(0));
                        else if (act === 'stop') nativeStopHelper(h, ptr(0));
                    }
                }
            } catch (e) {}
        }
    }
});

function readPlayerInfoSnapshot(readName) {
    try {
        var p = getPlayer(ptr(0));
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
                mapId = curCoord.add(0x0C).readS32();
                tileX = curCoord.add(0x10).readS32();
                tileY = curCoord.add(0x14).readS32();
            }
        } catch (e) {}

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

        return {name: charName, level: level, classId: classId, mapId: mapId, tileX: tileX, tileY: tileY, isMoving: isMoving, helperState: helperState};
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
        pendingMoveTarget = {x: parseInt(targetX), y: parseInt(targetY)};
        return true;
    },

    cancelMove: function() {
        pendingMoveTarget = null;
        try {
            var p = getPlayer(ptr(0));
            if (!p.isNull()) {
                var move = p.add(off('__PLAYER_MOVE__')).readPointer();
                if (!move.isNull()) {
                    try { move.add(off('__MOVE_FLAG__')).writeU8(0); } catch (e1) {}
                }
            }
            return true;
        } catch (e) {
            return false;
        }
    },

    getHelperState: function() {
        try {
            var p = getPlayer(ptr(0));
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
            var p = getPlayer(ptr(0));
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
        pendingCommand = cmd;
        return true;
    },

    startHelper: function() {
        pendingHelperAction = 'start';
        return true;
    },

    stopHelper: function() {
        pendingHelperAction = 'stop';
        return true;
    },

    cleanup: function() {
        shuttingDown = true;
        pendingCommand = null;
        pendingMoveTarget = null;
        pendingHelperAction = null;
        try {
            if (fastTelemetryTimer !== null) {
                clearInterval(fastTelemetryTimer);
                fastTelemetryTimer = null;
            }
        } catch (e0) {}
        try {
            if (chatHook !== null) {
                chatHook.detach();
                chatHook = null;
            }
        } catch (e) {}
        try { Interceptor.flush(); } catch (e) {}
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

        # Load offsets
        self.offsets = dict(DEFAULT_OFFSETS)
        self._load_offsets_file()

        # Connect
        self._claim_mutex()
        self._attach()

    def _load_offsets_file(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "megamu_offsets.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.offsets.update(data)
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
            "__GET_PLAYER__": self.offsets.get("get_player", "0x12310D0"),
            "__MOVE_TO__": self.offsets.get("move_to", "0xD72750"),
            "__CHAT_SEND__": self.offsets.get("chat_send", "0x14B9250"),
            "__CHAT_UPDATE__": self.offsets.get("chat_update", "0x14B6AF0"),
            "__HELPER_START__": self.offsets.get("helper_start", "0x2A3B580"),
            "__HELPER_STOP__": self.offsets.get("helper_stop", "0x2A3C660"),
            "__PLAYER_NAME__": self.offsets.get("player_name", "0x28"),
            "__PLAYER_LEVEL__": self.offsets.get("player_level", "0x30"),
            "__PLAYER_CLASS__": self.offsets.get("player_class", "0x34"),
            "__PLAYER_COORD__": self.offsets.get("player_coord", "0x68"),
            "__PLAYER_MOVE__": self.offsets.get("player_move", "0xF0"),
            "__PLAYER_HELPER__": self.offsets.get("player_helper", "0x1E8"),
            "__PLAYER_LAST_COORD__": self.offsets.get("player_last_coord", "0x4E0"),
            "__MOVE_FLAG__": self.offsets.get("move_flag", "0x3C"),
            "__HELPER_STATE__": self.offsets.get("helper_state", "0x20"),
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
                        self.last_fast_state = payload.get("info")
                        self.last_fast_state_time = time.time()
                        self.last_fast_seq = payload.get("seq", 0)
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
                if fn:
                    return fn(*args)
            except Exception as e:
                # Nếu RPC lỗi do script bị mất, đánh dấu cần gắn lại
                err_str = str(e).lower()
                if "detached" in err_str or "destroyed" in err_str or "script is destroyed" in err_str:
                    self.is_ready = False
                return None
        return None

    def get_player_info(self, max_age: float = 0.55) -> Optional[Dict[str, Any]]:
        """Lấy thông tin nhân vật từ Fast Telemetry nếu còn mới, fallback gọi RPC nếu cần."""
        now = time.time()
        if self.last_fast_state and (now - self.last_fast_state_time) <= max_age:
            return self.last_fast_state

        res = self._call("getPlayerInfo")
        if res and isinstance(res, dict):
            self.last_fast_state = res
            self.last_fast_state_time = now
            return res

        return self.last_fast_state

    def move_to(self, target_x: int, target_y: int) -> bool:
        """Kích hoạt MoveTo native (game tự động tìm đường qua Unity Navmesh/Grid)."""
        res = self._call("moveTo", int(target_x), int(target_y))
        return bool(res)

    def cancel_move(self) -> bool:
        """Hủy lệnh di chuyển và xóa cờ di chuyển của nhân vật."""
        res = self._call("cancelMove")
        return bool(res)

    def get_hwnd(self) -> Optional[int]:
        """Lấy HWND cửa sổ của tiến trình game qua PID bằng pure ctypes."""
        if sys.platform != "win32" or not self.pid:
            return None
        user32 = ctypes.windll.user32
        result_hwnd = None

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_cb(hwnd, lparam):
            nonlocal result_hwnd
            if user32.IsWindowVisible(hwnd):
                lp_pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lp_pid))
                if lp_pid.value == self.pid:
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    title = buf.value
                    if "megamu" in title.lower():
                        result_hwnd = hwnd
                        return False
            return True

        try:
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception:
            pass
        return result_hwnd

    def send_chat(self, command: str) -> bool:
        """
        Gửi lệnh chat (chuyển map /move hoặc lệnh trong game):
        1. Ưu tiên tuyệt đối gửi qua Frida Native Hook (an toàn, chuẩn xác, không mở khung chat).
        2. Fallback qua Windows Background PostMessage chỉ khi Frida chưa sẵn sàng hoặc gọi native thất bại.
        """
        cmd = str(command).strip()
        if not cmd:
            return False

        native_ok = False
        if self.is_ready:
            try:
                res = self._call("sendChatNative", cmd)
                native_ok = bool(res)
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi gọi sendChatNative: {e}")

        if native_ok:
            return True

        # Fallback Background PostMessage chỉ khi không dùng được native hook
        hwnd = self.get_hwnd()
        if hwnd and sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                WM_KEYDOWN = 0x0100
                WM_KEYUP = 0x0101
                WM_CHAR = 0x0102
                VK_RETURN = 0x0D

                # Enter mở thanh chat
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
                user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
                time.sleep(0.05)

                # Gửi từng ký tự vào ô chat
                for ch in cmd:
                    user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
                    time.sleep(0.005)

                time.sleep(0.05)
                # Enter gửi lệnh
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
                user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
                return True
            except Exception as e:
                _safe_log(f"[MegDirectEngine] Lỗi PostMessage chat: {e}")

        return False

    def is_helper_active(self) -> bool:
        """Kiểm tra trạng thái MuHelper đang BẬT hay TẮT."""
        info = self.get_player_info(max_age=0.8)
        if info:
            return int(info.get("helperState", 0)) == 1
        res = self._call("getHelperState")
        return bool(res)

    def start_helper(self) -> bool:
        """Kích hoạt bật MuHelper."""
        res = self._call("startHelper")
        return bool(res)

    def stop_helper(self) -> bool:
        """Kích hoạt tắt MuHelper."""
        res = self._call("stopHelper")
        return bool(res)

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

