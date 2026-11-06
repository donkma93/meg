"""Chẩn đoán trực tiếp (read-only) trên tiến trình MEGAMU đang chạy.

Không ghi bộ nhớ, không gửi packet. Chỉ đọc để xác định:
- Frida attach được không, GameAssembly base
- Player ptr, toạ độ
- Inventory: số ô, các slot có đồ, item index / level
- GS connection
"""
import sys
import time

import frida

PID = int(sys.argv[1]) if len(sys.argv) > 1 else None
MODULE = "GameAssembly.dll"

OFF = {
    "get_player": 0x107FBF0,
    "get_game_ui": 0x107FF00,
    "get_gs_connection": 0x1077910,
    "player_inventory": 0x1B0,
    "inventory_items": 0x28,
    "player_coord": 0x68,
    "ui_moss_window": 0x1C8,
    "ui_merchant_window": 0x198,
    "ui_inventory_window": 0x188,
}

AGENT = r"""
const MODULE = "__MODULE__";
const cfg = __CFG__;

let base = null;
try {
    base = Process.getModuleByName(MODULE).base;
} catch (e) {
    send({ kind: "error", msg: "module not found: " + e });
}
function rva(n) { return base.add(n); }

function p(addr) { try { return addr.readPointer(); } catch (e) { return null; } }
function i32(addr) { try { return addr.readS32(); } catch (e) { return null; } }
function u8(addr) { try { return addr.readU8(); } catch (e) { return null; } }

function main() {
    if (!base) return;
    const out = { kind: "diag" };

    let getPlayer = null;
    try { getPlayer = new NativeFunction(rva(cfg.get_player), "pointer", []); } catch (e) { out.errPlayer = String(e); }
    let player = null;
    if (getPlayer) { try { player = getPlayer(); } catch (e) { out.errPlayerCall = String(e); } }
    out.player = player ? player.toString() : null;

    if (player && !player.isNull()) {
        const inv = p(player.add(cfg.player_inventory));
        out.inventory = inv ? inv.toString() : null;
        if (inv && !inv.isNull()) {
            const items = p(inv.add(cfg.inventory_items));
            out.itemsArr = items ? items.toString() : null;
            if (items && !items.isNull()) {
                out.arrLen = i32(items.add(0x18));
                const slots = [];
                let occupied = 0, maxSlot = 140;
                if (out.arrLen && out.arrLen > 12 && out.arrLen < maxSlot) maxSlot = out.arrLen;
                for (let s = 12; s < maxSlot; s++) {
                    const it = p(items.add(0x20 + s * 8));
                    if (it && !it.isNull()) {
                        occupied++;
                        slots.push({
                            slot: s,
                            level: i32(it.add(0x10)),
                            skill: i32(it.add(0x14)),
                            luck: i32(it.add(0x18)),
                            exc: i32(it.add(0x20)),
                            anc: i32(it.add(0x24)),
                            sock: i32(it.add(0x28)),
                            harm: i32(it.add(0x2C)),
                        });
                    }
                }
                out.occupied = occupied;
                out.ms = maxSlot;
                out.slots = slots.slice(0, 60);
                // 12 ô trang bị
                const eq = [];
                for (let s = 0; s < 12; s++) {
                    const it = p(items.add(0x20 + s * 8));
                    eq.push(it && !it.isNull() ? 1 : 0);
                }
                out.equipped = eq;
            }
        }
        const coordP = p(player.add(cfg.player_coord));
        if (coordP && !coordP.isNull()) {
            out.x = i32(coordP.add(0x10));
            out.y = i32(coordP.add(0x14));
        }
        const nameP = p(player.add(0x28));
        out.invPtr = out.inventory;
    }

    let getGS = null;
    try { getGS = new NativeFunction(rva(cfg.get_gs_connection), "pointer", []); } catch (e) { out.errGS = String(e); }
    if (getGS) {
        try {
            const gs = getGS();
            out.gs = gs ? gs.toString() : null;
            out.gsNull = !gs || gs.isNull();
        } catch (e) { out.errGSCall = String(e); }
    }

    let getUI = null;
    try { getUI = new NativeFunction(rva(cfg.get_game_ui), "pointer", []); } catch (e) {}
    if (getUI) {
        try {
            const ui = getUI();
            out.ui = ui ? ui.toString() : null;
            if (ui && !ui.isNull()) {
                const mw = p(ui.add(cfg.ui_moss_window));
                out.mossWin = mw ? mw.toString() : null;
                if (mw && !mw.isNull()) {
                    const w = p(mw.add(0x20));
                    out.mossOpen = w && !w.isNull() ? u8(w.add(0x48)) : null;
                }
                const me = p(ui.add(cfg.ui_merchant_window));
                out.merchantWin = me ? me.toString() : null;
                if (me && !me.isNull()) {
                    const w2 = p(me.add(0x20));
                    out.merchantOpen = w2 && !w2.isNull() ? u8(w2.add(0x48)) : null;
                }
                const invw = p(ui.add(cfg.ui_inventory_window));
                out.invWin = invw ? invw.toString() : null;
                if (invw && !invw.isNull()) {
                    const w3 = p(invw.add(0x20));
                    out.invOpen = w3 && !w3.isNull() ? u8(w3.add(0x48)) : null;
                }
            }
        } catch (e) { out.errUICall = String(e); }
    }

    send(out);
}

setTimeout(main, 50);
"""


def main():
    dev = frida.get_local_device()
    if PID is None:
        target = next((p for p in dev.enumerate_processes() if "MEGAMU" in p.name.upper()), None)
        if not target:
            print("Không tìm thấy tiến trình MEGAMU")
            return 2
        pid = target.pid
    else:
        pid = PID
    print(f"[i] Attach PID {pid} ...")
    session = dev.attach(pid)
    script = session.create_script(
        AGENT.replace("__MODULE__", MODULE).replace("__CFG__", repr(OFF).replace("'", '"'))
    )
    result = {}

    def on_message(message, data):
        if message.get("type") == "send":
            result.update(message["payload"])
        else:
            print("[frida]", message)

    script.on("message", on_message)
    script.load()
    for _ in range(40):
        if result:
            break
        time.sleep(0.1)
    session.detach()

    if not result:
        print("[!] Không nhận được dữ liệu")
        return 1

    for k in sorted(result):
        if k == "slots":
            continue
        print(f"  {k:<14} = {result[k]}")
    slots = result.get("slots") or []
    print(f"\n[i] {len(slots)} slot có đồ (hiển thị tối đa 60):")
    for s in slots:
        print(f"    slot {s['slot']:>3}  lvl={s['level']}  luck={s['luck']}  exc={s['exc']}  anc={s['anc']}  sock={s['sock']}  harm={s['harm']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
