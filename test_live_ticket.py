import sys
import os
import psutil
import json

# Add current dir to sys.path
sys.path.insert(0, r"c:\Users\donpv\Desktop\meg")

from meg_direct_engine import MegDirectEngine

# Find MEGAMU process
pids = [p.pid for p in psutil.process_iter(['name']) if p.info['name'] and 'megamu' in p.info['name'].lower()]
print(f"MEGAMU PIDs found: {pids}")

if not pids:
    print("NO MEGAMU PROCESS RUNNING!")
    sys.exit(0)

pid = pids[0]
eng = MegDirectEngine.get_engine(pid)
print(f"Engine created for PID: {pid}")

print("\n--- Testing read_devil_ticket_info_via_ram ---")
ram_res = eng.read_devil_ticket_info_via_ram()
print(f"RAM result: {json.dumps(ram_res, indent=2, ensure_ascii=False)}")

print("\n--- Testing get_devil_ticket_info ---")
t_info = eng.get_devil_ticket_info()
print(f"Ticket info: {json.dumps(t_info, indent=2, ensure_ascii=False)}")

