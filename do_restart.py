import os
import sys
import ctypes
from ctypes import wintypes
import time

log_file = r"c:\Users\donpv\Desktop\meg\restart_status.log"

def log(msg):
    print(msg, flush=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

try:
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] STARTING RESTART...\n")
except Exception:
    pass

cur_pid = os.getpid()
killed_count = 0

try:
    import psutil
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = (p.info['name'] or '').lower()
            if 'python' in name and p.info['pid'] != cur_pid:
                try:
                    cmd = " ".join(p.cmdline())
                    if 'meg_gui.py' in cmd:
                        log(f"KILLED_OLD_PID:{p.info['pid']}")
                        p.kill()
                        killed_count += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        except Exception:
            pass
except Exception as e:
    log(f"PSUTIL_ERROR: {e}")

log(f"KILLED_TOTAL: {killed_count}")
time.sleep(0.5)

class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]

si = STARTUPINFO()
si.cb = ctypes.sizeof(si)
si.lpDesktop = "WinSta0\\Default"
si.lpTitle = "MEGAMU Auto Train - Debug Console"
pi = PROCESS_INFORMATION()

py_exe = sys.executable
cmd = f'"{py_exe}" -u "c:\\Users\\donpv\\Desktop\\meg\\meg_gui.py"'
CREATE_NEW_CONSOLE = 0x00000010

log(f"SPAWNING: {cmd}")
res = ctypes.windll.kernel32.CreateProcessW(
    None, cmd, None, None, False, CREATE_NEW_CONSOLE, None, r"c:\Users\donpv\Desktop\meg", ctypes.byref(si), ctypes.byref(pi)
)

if res:
    new_pid = pi.dwProcessId
    log(f"NEW_PID:{new_pid}")
    ctypes.windll.kernel32.CloseHandle(pi.hProcess)
    ctypes.windll.kernel32.CloseHandle(pi.hThread)
    log("RESTART_COMPLETE_SUCCESS")
else:
    err = ctypes.GetLastError()
    log(f"FAILED_CREATE_PROCESS:{err}")
