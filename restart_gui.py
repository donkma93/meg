import os
import sys
import time
import ctypes
from ctypes import wintypes
import psutil

print("[RESTART] Searching for running meg_gui.py processes...")
killed_count = 0
my_pid = os.getpid()

for proc in psutil.process_iter(['pid', 'name']):
    try:
        name = (proc.info['name'] or '').lower()
        if 'python' not in name:
            continue
        pid = proc.info['pid']
        if pid == my_pid:
            continue
        try:
            cmdline = " ".join(proc.cmdline() or [])
            if "meg_gui.py" in cmdline:
                print(f"[RESTART] Found meg_gui.py at PID {pid}. Terminating...")
                proc.kill()
                killed_count += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    except Exception:
        pass

print(f"[RESTART] Terminated {killed_count} old GUI process(es). Waiting 1s...")
time.sleep(1.0)

class STARTUPINFOW(ctypes.Structure):
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

si = STARTUPINFOW()
si.cb = ctypes.sizeof(si)
si.lpDesktop = "WinSta0\\Default"
si.lpTitle = "MEGAMU Auto Train - Debug Console"
pi = PROCESS_INFORMATION()

py_exe = sys.executable
work_dir = r"c:\Users\donpv\Desktop\meg"
gui_script = os.path.join(work_dir, "meg_gui.py")
cmd = f'"{py_exe}" -u "{gui_script}"'
CREATE_NEW_CONSOLE = 0x00000010

print(f"[RESTART] Spawning: {cmd} on desktop WinSta0\\Default...")
res = ctypes.windll.kernel32.CreateProcessW(
    None,
    cmd,
    None,
    None,
    False,
    CREATE_NEW_CONSOLE,
    None,
    work_dir,
    ctypes.byref(si),
    ctypes.byref(pi)
)

if res:
    new_pid = pi.dwProcessId
    ctypes.windll.kernel32.CloseHandle(pi.hProcess)
    ctypes.windll.kernel32.CloseHandle(pi.hThread)
    print(f"[RESTART] SUCCESS! Launched new MEGAMU GUI with PID: {new_pid}")
    time.sleep(2.0)
    if psutil.pid_exists(new_pid):
        print(f"[RESTART] Verified PID {new_pid} is alive and running!")
    else:
        print(f"[RESTART] PID {new_pid} exited early.")
else:
    err = ctypes.GetLastError()
    print(f"[RESTART] ERROR: CreateProcessW failed with error code {err}")
