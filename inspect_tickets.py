import sys
import json

from meg_direct_engine import MegDirectEngine

pid = 27244
eng = MegDirectEngine.get_engine(pid)
print(f"Engine ready: {eng.is_ready}")

ram_info = eng.read_devil_ticket_info_via_ram()
print(f"RAM info: {json.dumps(ram_info, ensure_ascii=False, indent=2)}")

if eng.is_ready:
    frida_info = eng._call("getDevilTicketInfo")
    print(f"Frida info: {frida_info}")
else:
    print("Frida not ready!")

