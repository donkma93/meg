using System.Diagnostics;
using System.Text;
using System.Text.Json;
using MegAccountManager.Services;

namespace MegAccountManager;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        if (args.Any(arg => string.Equals(arg, "--enum-all-windows", StringComparison.OrdinalIgnoreCase)))
        {
            var sb = new StringBuilder(512);
            int count = 0;
            BackgroundInputSimulator.EnumAllWindowsDiagnostic((hWnd, pid, title, cls, isVis) =>
            {
                count++;
                if (title.Length > 0 || isVis)
                {
                    Console.WriteLine($"HWND 0x{hWnd.ToInt64():X} | PID {pid} | Vis: {isVis} | Class: {cls} | Title: \"{title}\"");
                }
            });
            Console.WriteLine($"Total windows: {count}");
            return;
        }

        if (args.Any(arg => string.Equals(arg, "--il2cpp-probe", StringComparison.OrdinalIgnoreCase)))
        {
            Environment.ExitCode = RunIl2CppProbe();
            return;
        }

        if (args.Any(arg => string.Equals(arg, "--warp-probe", StringComparison.OrdinalIgnoreCase)))
        {
            Environment.ExitCode = RunWarpProbe();
            return;
        }

        if (args.Any(arg => string.Equals(arg, "--dump-player", StringComparison.OrdinalIgnoreCase)))
        {
            var pidArg = args.SkipWhile(a => !string.Equals(a, "--dump-player", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
            int pid = int.TryParse(pidArg, out var p) ? p : (Process.GetProcessesByName("MEGAMU").FirstOrDefault()?.Id ?? 0);
            if (pid == 0)
            {
                Console.Error.WriteLine("Không tìm thấy tiến trình MEGAMU nào.");
                Environment.ExitCode = 1;
                return;
            }
            Console.WriteLine(ProcessMemory.DumpPlayerMemoryDiagnostic(pid));
            return;
        }

        if (args.Any(arg => string.Equals(arg, "--test-click", StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(arg, "--test-click-center", StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(arg, "--test-click-coord", StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(arg, "--list-windows", StringComparison.OrdinalIgnoreCase)))
        {
            Environment.ExitCode = RunInputSimulationCli(args);
            return;
        }

        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
        Application.ThreadException += (_, e) => ShowFatal(e.Exception);
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
        {
            if (e.ExceptionObject is Exception ex)
            {
                ShowFatal(ex);
            }
        };

        try
        {
            ApplicationConfiguration.Initialize();
            Application.Run(new MainForm());
        }
        catch (Exception ex)
        {
            ShowFatal(ex);
        }
    }

    /// <summary>
    /// Read-only diagnostic for the live MEGAMU IL2CPP object graph. It never writes
    /// process memory, invokes an IL2CPP method, or sends data to the game.
    /// </summary>
    private static int RunIl2CppProbe()
    {
        try
        {
            var clients = ProcessMemory.GetLiveClientsFromWindowTitles().ToList();
            var results = clients.Select(client =>
            {
                ProcessMemory.RefreshClientIl2CppState(client);

                return new
                {
                    client.ProcessId,
                    client.CharacterName,
                    client.Server,
                    CoordinateResolvedFromIl2Cpp =
                                                  client.Source.StartsWith("il2cpp:", StringComparison.OrdinalIgnoreCase),
                    MapResolvedFromIl2Cpp = client.MapId is not null,
                    client.MapId,
                    client.MapName,
                    client.X,
                    client.Y,
                    client.Source
                };
            }).ToList();

            var report = new
            {
                Mode = "read-only IL2CPP probe",
                TestedAtUtc = DateTime.UtcNow,
                ProcessCount = results.Count,
                CoordinatesResolved = results.Count(result => result.CoordinateResolvedFromIl2Cpp),
                MapsResolved = results.Count(result => result.MapResolvedFromIl2Cpp),
                Results = results
            };

            Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            return results.Count == 0 || results.Any(result =>
                !result.CoordinateResolvedFromIl2Cpp || !result.MapResolvedFromIl2Cpp)
                ? 1
                : 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"IL2CPP probe failed: {ex}");
            return 2;
        }
    }

    /// <summary>
    /// Read-only diagnostic probe for MEGAMU Warp (MapServerMove & scene/coord) state across all processes.
    /// </summary>
    private static int RunWarpProbe()
    {
        try
        {
            var clients = ProcessMemory.GetLiveClientsFromWindowTitles().ToList();
            var results = clients.Select(client =>
            {
                var state = ProcessMemory.ReadWarpMemoryState(client.ProcessId);
                return new
                {
                    client.ProcessId,
                    client.CharacterName,
                    client.Server,
                    client.WindowTitle,
                    state?.SceneIndex,
                    state?.MapName,
                    LiveCoord = state?.CurrentCoordDisplay,
                    TargetCoord = state?.TargetCoordDisplay,
                    LastServerCoord = state?.LastServerCoordDisplay,
                    Position3D = state != null ? $"X={state.PosX:F2}, Y={state.PosY:F2}, Z={state.PosZ:F2}" : null,
                    MapServerMove = state != null ? new
                    {
                        Ptr = $"0x{state.MapServerMovePtr:X}",
                        state.IsActive,
                        state.QuitTime,
                        AuthKeysPtr = $"0x{state.AuthKeysPtr:X}",
                        state.AuthKeysNonZero
                    } : null
                };
            }).ToList();

            var report = new
            {
                Mode = "read-only Warp & RAM diagnostic probe",
                TestedAtUtc = DateTime.UtcNow,
                ProcessCount = results.Count,
                Results = results
            };

            Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            return results.Count > 0 ? 0 : 1;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Warp probe failed: {ex}");
            return 2;
        }
    }

    private static int RunInputSimulationCli(string[] args)
    {
        try
        {
            if (args.Any(a => string.Equals(a, "--list-windows", StringComparison.OrdinalIgnoreCase)))
            {
                var targetPidArg = args.SkipWhile(a => !string.Equals(a, "--list-windows", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
                int? targetPid = int.TryParse(targetPidArg, out var p) ? p : null;

                var pids = targetPid.HasValue
                    ? new[] { targetPid.Value }
                    : Process.GetProcessesByName("MEGAMU").Select(x => x.Id).ToArray();

                if (pids.Length == 0)
                {
                    Console.WriteLine("Khong tim thay tien trinh MEGAMU nao dang chay.");
                    return 1;
                }

                foreach (var pid in pids)
                {
                    Console.WriteLine($"=== Windows cho PID {pid} ===");
                    var windows = BackgroundInputSimulator.FindWindowsForProcess(pid);
                    if (windows.Count == 0)
                    {
                        Console.WriteLine("  (Khong tim thay HWND nao)");
                    }
                    foreach (var w in windows)
                    {
                        Console.WriteLine($"  HWND: 0x{w.Hwnd.ToInt64():X} | Title: \"{w.Title}\" | Class: \"{w.ClassName}\" | Size: {w.ClientRect.Width}x{w.ClientRect.Height} | Visible: {w.IsVisible} | Minimized: {w.IsMinimized}");
                    }
                }
                return 0;
            }

            if (args.Any(a => string.Equals(a, "--test-click-center", StringComparison.OrdinalIgnoreCase)))
            {
                var targetArg = args.SkipWhile(a => !string.Equals(a, "--test-click-center", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
                WindowTargetInfo? win = null;
                if (string.IsNullOrWhiteSpace(targetArg))
                {
                    var firstProc = Process.GetProcessesByName("MEGAMU").FirstOrDefault();
                    if (firstProc != null) win = BackgroundInputSimulator.ResolveMainWindow(firstProc.Id);
                    else
                    {
                        Console.Error.WriteLine("Cach dung: --test-click-center <PID hoac 0xHWND>");
                        return 1;
                    }
                }
                else
                {
                    win = ResolveTarget(targetArg);
                }

                if (win == null)
                {
                    Console.Error.WriteLine($"Khong tim thay cua so hop le cho '{targetArg}'.");
                    return 2;
                }

                Console.WriteLine($"Mô phỏng click tâm cửa sổ: {win.DisplayText}");
                var result = BackgroundInputSimulator.SimulateClickCenterAsync(win.Hwnd).GetAwaiter().GetResult();
                Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
                return result.Success ? 0 : 3;
            }

            if (args.Any(a => string.Equals(a, "--test-click", StringComparison.OrdinalIgnoreCase)))
            {
                var remaining = args.SkipWhile(a => !string.Equals(a, "--test-click", StringComparison.OrdinalIgnoreCase)).Skip(1).ToList();
                if (remaining.Count < 3)
                {
                    Console.Error.WriteLine("Cach dung: --test-click <PID hoac 0xHWND> <X> <Y> [DurationMs=60]");
                    return 1;
                }

                var targetArg = remaining[0];
                if (!int.TryParse(remaining[1], out var x) ||
                    !int.TryParse(remaining[2], out var y))
                {
                    Console.Error.WriteLine("Tham so X, Y phai la so nguyen.");
                    return 1;
                }

                var durationMs = remaining.Count > 3 && int.TryParse(remaining[3], out var d) ? d : 60;
                var win = ResolveTarget(targetArg);
                if (win == null)
                {
                    Console.Error.WriteLine($"Khong tim thay cua so hop le cho '{targetArg}'.");
                    return 2;
                }

                Console.WriteLine($"Mô phỏng click toa do ({x}, {y}) tai {win.DisplayText}");
                var result = BackgroundInputSimulator.SimulateClickAsync(win.Hwnd, x, y, durationMs).GetAwaiter().GetResult();
                Console.WriteLine($"{{ \"Success\": {result.Success.ToString().ToLower()}, \"ProcessId\": {result.ProcessId}, \"X\": {result.X}, \"Y\": {result.Y}, \"Message\": \"{result.Message?.Replace("\"", "\\\"")}\" }}");
                return result.Success ? 0 : 3;
            }

            if (args.Any(a => string.Equals(a, "--test-click-coord", StringComparison.OrdinalIgnoreCase)))
            {
                var remaining = args.SkipWhile(a => !string.Equals(a, "--test-click-coord", StringComparison.OrdinalIgnoreCase)).Skip(1).ToList();
                if (remaining.Count < 3)
                {
                    Console.Error.WriteLine("Cach dung: --test-click-coord <PID> <GameTargetX> <GameTargetY> [DurationMs=80]");
                    return 1;
                }

                if (!int.TryParse(remaining[0], out var pid) ||
                    !int.TryParse(remaining[1], out var targetX) ||
                    !int.TryParse(remaining[2], out var targetY))
                {
                    Console.Error.WriteLine("Tham so PID, GameTargetX, GameTargetY phai la so nguyen.");
                    return 1;
                }

                var durationMs = remaining.Count > 3 && int.TryParse(remaining[3], out var d) ? d : 80;
                var angle = remaining.Count > 4 && float.TryParse(remaining[4], out var a) ? a : 0f;
                var useHop = args.Any(a => string.Equals(a, "--hop", StringComparison.OrdinalIgnoreCase));
                var win = BackgroundInputSimulator.ResolveMainWindow(pid);
                if (win == null)
                {
                    Console.Error.WriteLine($"Khong tim thay cua so hop le cho PID {pid}.");
                    return 2;
                }

                Console.WriteLine($"Mô phỏng click huong toi Toa do Game ({targetX}, {targetY}) [Goc cam: {angle}°, Hop: {useHop}] cho {win.DisplayText}");
                var result = BackgroundInputSimulator.SimulateClickGameCoordAsync(win.Hwnd, pid, targetX, targetY, durationMs, angle, true, useHop).GetAwaiter().GetResult();
                Console.WriteLine($"{{ \"Success\": {result.Success.ToString().ToLower()}, \"ProcessId\": {result.ProcessId}, \"X\": {result.X}, \"Y\": {result.Y}, \"DurationMs\": {result.DurationMs}, \"WindowTitle\": \"{result.WindowTitle?.Replace("\"", "\\\"")}\", \"Message\": \"{result.Message?.Replace("\"", "\\\"").Replace("\n", "\\n")}\" }}");
                return result.Success ? 0 : 3;
            }

            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Loi thuc thi click simulation CLI: {ex}");
            return 4;
        }
    }

    private static WindowTargetInfo? ResolveTarget(string targetArg)
    {
        if (targetArg.StartsWith("0x", StringComparison.OrdinalIgnoreCase) &&
            long.TryParse(targetArg.Substring(2), System.Globalization.NumberStyles.HexNumber, null, out var hwndVal))
        {
            return BackgroundInputSimulator.InspectWindow(new IntPtr(hwndVal));
        }

        if (int.TryParse(targetArg, out var pid))
        {
            return BackgroundInputSimulator.ResolveMainWindow(pid);
        }

        return null;
    }

    private static void ShowFatal(Exception ex)
    {
        try
        {
            var logDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "MegAccountManager");
            Directory.CreateDirectory(logDir);
            var logPath = Path.Combine(logDir, "startup-error.log");
            File.WriteAllText(logPath, ex.ToString(), Encoding.UTF8);
            MessageBox.Show(
                $"Lỗi khởi động MegAccountManager:\n{ex.Message}\n\nChi tiết: {logPath}",
                "Lỗi",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
        catch
        {
            MessageBox.Show(ex.ToString(), "Lỗi", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
