
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
            } catch (e) {}
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

// FAST STATE v1.4.1
// Read RAM locally inside each game process every 150 ms. Python no longer has
// to synchronously poll every row. Only changed state is pushed, plus a 700 ms
// heartbeat to prove freshness while the character is standing still.
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
        // PK-WAIT safety: discard a MoveTo that was queued just before death
        // and clear the current movement flag so the respawned character does
        // not continue walking toward the old training spot during PK WAIT.
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
