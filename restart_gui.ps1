Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class DesktopProcessLauncher {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO {
      public int cb;
      public string lpReserved;
      public string lpDesktop;
      public string lpTitle;
      public int dwX;
      public int dwY;
      public int dwXSize;
      public int dwYSize;
      public int dwXCountChars;
      public int dwYCountChars;
      public int dwFillAttribute;
      public int dwFlags;
      public short wShowWindow;
      public short cbReserved2;
      public IntPtr lpReserved2;
      public IntPtr hStdInput;
      public IntPtr hStdOutput;
      public IntPtr hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION {
      public IntPtr hProcess;
      public IntPtr hThread;
      public int dwProcessId;
      public int dwThreadId;
    }
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CreateProcess(
      string lpApplicationName,
      string lpCommandLine,
      IntPtr lpProcessAttributes,
      IntPtr lpThreadAttributes,
      bool bInheritHandles,
      uint dwCreationFlags,
      IntPtr lpEnvironment,
      string lpCurrentDirectory,
      ref STARTUPINFO lpStartupInfo,
      out PROCESS_INFORMATION lpProcessInformation
    );
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);

    public static int Start(string cmdLine, string workDir, string desktop) {
      STARTUPINFO si = new STARTUPINFO();
      si.cb = Marshal.SizeOf(si);
      si.lpDesktop = desktop;
      si.lpTitle = "MEGAMU Auto Train - Debug Console";
      PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
      bool res = CreateProcess(null, cmdLine, IntPtr.Zero, IntPtr.Zero, false, 0x00000010, IntPtr.Zero, workDir, ref si, out pi);
      if (!res) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
      CloseHandle(pi.hProcess);
      CloseHandle(pi.hThread);
      return pi.dwProcessId;
    }
  }
"@

Write-Host "Searching and stopping existing MEGAMU GUI processes..."
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*meg_gui.py*" }
foreach ($p in $procs) {
    Write-Host "Killing old GUI PID: $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 800

$py = (Get-Command python).Source
$dir = $PSScriptRoot
if (-not $dir) { $dir = "c:\Users\donpv\Desktop\meg" }
$script = Join-Path $dir "meg_gui.py"
$cmd = "`"$py`" -u `"$script`""

$newPid = [DesktopProcessLauncher]::Start($cmd, $dir, "WinSta0\Default")
Write-Host "Started NEW MEGAMU GUI on user desktop with PID: $newPid"
Start-Sleep -Seconds 2
$np = Get-Process -Id $newPid -ErrorAction SilentlyContinue
if ($np) {
    Write-Host "SUCCESS: Process $newPid is running on user desktop!"
} else {
    Write-Host "WARNING: Process $newPid may have exited."
}

