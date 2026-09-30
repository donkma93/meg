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
      PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
      bool res = CreateProcess(null, cmdLine, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, workDir, ref si, out pi);
      if (!res) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
      CloseHandle(pi.hProcess);
      CloseHandle(pi.hThread);
      return pi.dwProcessId;
    }
  }
"@

$py = (Get-Command python).Source
$dir = $PSScriptRoot
$script = Join-Path $dir "meg_gui.py"
$cmd = "`"$py`" `"$script`""

$procId = [DesktopProcessLauncher]::Start($cmd, $dir, "WinSta0\Default")
Write-Host "Started MEGAMU Auto Navigator GUI on user desktop with PID: $procId"
Start-Sleep -Seconds 3
$p = Get-Process -Id $procId -ErrorAction SilentlyContinue
if ($p) {
    Write-Host "Process $procId is RUNNING successfully! (CPU: $($p.CPU), Responding: $($p.Responding))"
} else {
    Write-Host "Process $procId exited."
}
