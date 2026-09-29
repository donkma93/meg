using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Text;

namespace MegAccountManager.Services;

public enum MouseButton
{
    Left,
    Right
}

public sealed class WindowTargetInfo
{
    public IntPtr Hwnd { get; set; }
    public int ProcessId { get; set; }
    public string Title { get; set; } = string.Empty;
    public string ClassName { get; set; } = string.Empty;
    public Rectangle ClientRect { get; set; }
    public Rectangle WindowRect { get; set; }
    public bool IsVisible { get; set; }
    public bool IsMinimized { get; set; }

    public string DisplayText =>
        $"[0x{Hwnd.ToInt64():X}] PID:{ProcessId} - \"{Title}\" ({ClientRect.Width}x{ClientRect.Height})";
}

public sealed class ClickSimulationResult
{
    public bool Success { get; set; }
    public IntPtr Hwnd { get; set; }
    public int ProcessId { get; set; }
    public string WindowTitle { get; set; } = string.Empty;
    public int X { get; set; }
    public int Y { get; set; }
    public int DurationMs { get; set; }
    public MouseButton Button { get; set; }
    public string Message { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
}

/// <summary>
/// Simulates mouse clicks into background windows without moving or capturing the physical mouse cursor.
/// Uses Win32 PostMessage to dispatch WM_LBUTTONDOWN / WM_LBUTTONUP directly into the target window message queue.
/// </summary>
public static class BackgroundInputSimulator
{
    private const uint WmActivate = 0x0006;
    private const uint WmSetFocus = 0x0007;
    private const uint WmNcHitTest = 0x0084;
    private const uint WmSetCursor = 0x0020;
    private const uint WmMouseMove = 0x0200;
    private const uint WmMouseActivate = 0x0021;
    private const uint WmLButtonDown = 0x0201;
    private const uint WmLButtonUp = 0x0202;
    private const uint WmRButtonDown = 0x0204;
    private const uint WmRButtonUp = 0x0205;

    private const uint WmKeyDown = 0x0100;
    private const uint WmKeyUp = 0x0101;
    private const uint WmChar = 0x0102;
    private const int VkReturn = 0x0D;

    private const int MkLButton = 0x0001;
    private const int MkRButton = 0x0002;
    private const int WaActive = 1;
    private const int HtClient = 1;

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern IntPtr OpenInputDesktop(uint dwFlags, bool fInherit, uint dwDesiredAccess);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumDesktopWindows(IntPtr hDesktop, EnumWindowsProc lpfn, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct WinPoint
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out WinPoint lpPoint);

    [DllImport("user32.dll")]
    private static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    private static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);

    [DllImport("user32.dll")]
    private static extern bool ClientToScreen(IntPtr hWnd, ref WinPoint lpPoint);

    private const uint MouseEventfLeftDown = 0x0002;
    private const uint MouseEventfLeftUp = 0x0004;
    private const uint MouseEventfRightDown = 0x0008;
    private const uint MouseEventfRightUp = 0x0010;

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumThreadWindows(int dwThreadId, EnumWindowsProc lpfn, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetClientRect(IntPtr hWnd, out Rect lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(IntPtr hWnd, out Rect lpRect);

    private const int VkEscape = 0x1B;
    private const int SwRestore = 9;
    private const int SwShowNoActivate = 4;

    private static readonly IntPtr HwndTop = IntPtr.Zero;
    private const uint SwpNoSize = 0x0001;
    private const uint SwpNoMove = 0x0002;
    private const uint SwpNoActivate = 0x0010;
    private const uint SwpShowWindow = 0x0040;

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

    [DllImport("user32.dll")]
    private static extern short VkKeyScan(char ch);

    [DllImport("user32.dll")]
    private static extern uint MapVirtualKey(uint uCode, uint uMapType);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindow(IntPtr hWnd);

    public static bool IsWindowValid(IntPtr hWnd) => IsWindow(hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;

        public Rectangle ToRectangle() => new(Left, Top, Right - Left, Bottom - Top);
    }

    /// <summary>
    /// Constructs the 32-bit lParam containing X in the low word and Y in the high word.
    /// </summary>
    public static IntPtr MakeLParam(int x, int y)
    {
        return (IntPtr)((y << 16) | (x & 0xFFFF));
    }

    public static void EnumAllWindowsDiagnostic(Action<IntPtr, int, string, string, bool> callback)
    {
        var sbTitle = new StringBuilder(512);
        var sbClass = new StringBuilder(256);
        try
        {
            var hDesk = OpenInputDesktop(0, false, 0x01FF);
            if (hDesk != IntPtr.Zero)
            {
                EnumDesktopWindows(hDesk, (hWnd, _) =>
                {
                    GetWindowThreadProcessId(hWnd, out var pid);
                    GetWindowText(hWnd, sbTitle, sbTitle.Capacity);
                    GetClassName(hWnd, sbClass, sbClass.Capacity);
                    var isVis = IsWindowVisible(hWnd);
                    callback(hWnd, (int)pid, sbTitle.ToString(), sbClass.ToString(), isVis);
                    return true;
                }, IntPtr.Zero);
                return;
            }
        }
        catch { }

        EnumWindows((hWnd, _) =>
        {
            GetWindowThreadProcessId(hWnd, out var pid);
            GetWindowText(hWnd, sbTitle, sbTitle.Capacity);
            GetClassName(hWnd, sbClass, sbClass.Capacity);
            var isVis = IsWindowVisible(hWnd);
            callback(hWnd, (int)pid, sbTitle.ToString(), sbClass.ToString(), isVis);
            return true;
        }, IntPtr.Zero);
    }

    /// <summary>
    /// Enumerates all windows belonging to the given process ID, checking desktop, top-level, thread, and child windows.
    /// </summary>
    public static List<WindowTargetInfo> FindWindowsForProcess(int processId)
    {
        var windows = new List<WindowTargetInfo>();
        var seenHwnds = new HashSet<IntPtr>();

        // 1. EnumDesktopWindows on interactive desktop (resolves games where EnumWindows fails with 203)
        try
        {
            var hDesk = OpenInputDesktop(0, false, 0x01FF);
            if (hDesk != IntPtr.Zero)
            {
                EnumDesktopWindows(hDesk, (hWnd, _) =>
                {
                    GetWindowThreadProcessId(hWnd, out var pid);
                    if (pid == processId && seenHwnds.Add(hWnd))
                    {
                        var info = InspectWindow(hWnd, (int)pid);
                        if (info != null)
                        {
                            windows.Add(info);
                        }
                    }
                    return true;
                }, IntPtr.Zero);
            }
        }
        catch { }

        // 2. EnumWindows fallback
        try
        {
            EnumWindows((hWnd, _) =>
            {
                GetWindowThreadProcessId(hWnd, out var pid);
                if (pid == processId && seenHwnds.Add(hWnd))
                {
                    var info = InspectWindow(hWnd, (int)pid);
                    if (info != null)
                    {
                        windows.Add(info);
                    }
                }
                return true;
            }, IntPtr.Zero);
        }
        catch { }

        // 3. EnumThreadWindows (for processes where windows are thread-owned or not enumerated by EnumWindows)
        try
        {
            var proc = Process.GetProcessById(processId);
            foreach (ProcessThread th in proc.Threads)
            {
                EnumThreadWindows(th.Id, (hWnd, _) =>
                {
                    if (seenHwnds.Add(hWnd))
                    {
                        var info = InspectWindow(hWnd, processId);
                        if (info != null)
                        {
                            windows.Add(info);
                        }
                    }
                    return true;
                }, IntPtr.Zero);
            }
        }
        catch { }

        // Priority sort: UnityWndClass first, then visible with client area, then largest size
        return windows
            .OrderByDescending(w => string.Equals(w.ClassName, "UnityWndClass", StringComparison.OrdinalIgnoreCase))
            .ThenByDescending(w => w.IsVisible && w.ClientRect.Width > 0 && w.ClientRect.Height > 0)
            .ThenByDescending(w => w.ClientRect.Width * w.ClientRect.Height)
            .ToList();
    }

    /// <summary>
    /// Resolves the primary window handle for a target process.
    /// Prioritizes UnityWndClass if present.
    /// </summary>
    public static WindowTargetInfo? ResolveMainWindow(int processId)
    {
        try
        {
            var proc = Process.GetProcessById(processId);
            var mainHwnd = proc.MainWindowHandle;
            if (mainHwnd != IntPtr.Zero && IsWindow(mainHwnd))
            {
                var info = InspectWindow(mainHwnd, processId);
                if (info != null && info.IsVisible && info.ClientRect.Width > 0 &&
                    string.Equals(info.ClassName, "UnityWndClass", StringComparison.OrdinalIgnoreCase))
                {
                    return info;
                }
            }
        }
        catch { }

        var candidates = FindWindowsForProcess(processId);
        return candidates.FirstOrDefault(c => string.Equals(c.ClassName, "UnityWndClass", StringComparison.OrdinalIgnoreCase) && c.IsVisible)
            ?? candidates.FirstOrDefault(c => string.Equals(c.ClassName, "UnityWndClass", StringComparison.OrdinalIgnoreCase))
            ?? candidates.FirstOrDefault(c => c.IsVisible && c.ClientRect.Width > 0 && c.ClientRect.Height > 0)
            ?? candidates.FirstOrDefault();
    }

    /// <summary>
    /// Inspects window details (title, class, bounds, visibility).
    /// </summary>
    public static WindowTargetInfo? InspectWindow(IntPtr hWnd, int processId = 0)
    {
        if (!IsWindow(hWnd)) return null;

        if (processId == 0)
        {
            GetWindowThreadProcessId(hWnd, out var pid);
            processId = (int)pid;
        }

        var sbTitle = new StringBuilder(512);
        GetWindowText(hWnd, sbTitle, sbTitle.Capacity);

        var sbClass = new StringBuilder(256);
        GetClassName(hWnd, sbClass, sbClass.Capacity);

        GetClientRect(hWnd, out var clientRect);
        GetWindowRect(hWnd, out var windowRect);

        return new WindowTargetInfo
        {
            Hwnd = hWnd,
            ProcessId = processId,
            Title = sbTitle.ToString(),
            ClassName = sbClass.ToString(),
            ClientRect = clientRect.ToRectangle(),
            WindowRect = windowRect.ToRectangle(),
            IsVisible = IsWindowVisible(hWnd),
            IsMinimized = IsIconic(hWnd)
        };
    }

    /// <summary>
    /// Simulates a mouse click at relative client coordinates (x, y) without moving the physical cursor.
    /// </summary>
    public static async Task<ClickSimulationResult> SimulateClickAsync(
        IntPtr hWnd,
        int clientX,
        int clientY,
        int durationMs = 60,
        MouseButton button = MouseButton.Left,
        bool sendPreMove = true,
        bool sendActivateMessage = false,
        bool useHardwareFastHop = false)
    {
        var winInfo = InspectWindow(hWnd);
        if (winInfo == null)
        {
            return new ClickSimulationResult
            {
                Success = false,
                Hwnd = hWnd,
                X = clientX,
                Y = clientY,
                DurationMs = durationMs,
                Button = button,
                Message = $"HWND 0x{hWnd.ToInt64():X} không hợp lệ hoặc cửa sổ đã đóng."
            };
        }

        // Restore window if minimized or client size is 0 so Unity can render and raycast
        if (winInfo.IsMinimized || winInfo.ClientRect.Width <= 0 || winInfo.ClientRect.Height <= 0)
        {
            ShowWindow(hWnd, SwShowNoActivate);
            await Task.Delay(50);
            winInfo = InspectWindow(hWnd) ?? winInfo;
        }

        var lParam = MakeLParam(clientX, clientY);
        uint downMsg = button == MouseButton.Left ? WmLButtonDown : WmRButtonDown;
        uint upMsg = button == MouseButton.Left ? WmLButtonUp : WmRButtonUp;
        var downWParam = (IntPtr)(button == MouseButton.Left ? MkLButton : MkRButton);

        try
        {
            // 0. Auto-recover from Minimized (0x0) state to background normal state without activating
            if (IsIconic(hWnd))
            {
                ShowWindow(hWnd, SwShowNoActivate);
                await Task.Delay(40);
            }

            // 1. Zero-Intrusive Micro-Sync for Unity:
            // Temporarily align cursor position for Unity's GetCursorPos during PostMessage.
            // NO mouse_event (NEVER clicks desktop or other applications)!
            // NO SetWindowPos(HwndTop) (game window stays in the background)!
            bool needCursorSync = useHardwareFastHop;
            WinPoint origPos = default;
            if (needCursorSync)
            {
                GetCursorPos(out origPos);
                var targetPt = new WinPoint { X = clientX, Y = clientY };
                ClientToScreen(hWnd, ref targetPt);
                SetCursorPos(targetPt.X, targetPt.Y);
            }

            // Optional: simulate window activation message in background without stealing foreground focus or moving physical mouse
            if (sendActivateMessage)
            {
                SendMessage(hWnd, WmActivate, (IntPtr)WaActive, IntPtr.Zero);
                SendMessage(hWnd, WmSetFocus, IntPtr.Zero, IntPtr.Zero);
            }

            // Handshake simulating Windows OS mouse event pipeline:
            var screenPt = new WinPoint { X = clientX, Y = clientY };
            ClientToScreen(hWnd, ref screenPt);
            var screenLParam = MakeLParam(screenPt.X, screenPt.Y);
            SendMessage(hWnd, WmNcHitTest, IntPtr.Zero, screenLParam);
            SendMessage(hWnd, WmMouseActivate, hWnd, (IntPtr)((downMsg << 16) | HtClient));
            SendMessage(hWnd, WmSetCursor, hWnd, (IntPtr)((downMsg << 16) | HtClient));

            // Inform window of cursor coordinate before press
            if (sendPreMove)
            {
                PostMessage(hWnd, WmMouseMove, IntPtr.Zero, lParam);
            }

            // 2. Post DOWN message directly to game window
            var downOk = PostMessage(hWnd, downMsg, downWParam, lParam);
            if (!downOk)
            {
                if (needCursorSync) SetCursorPos(origPos.X, origPos.Y);
                var err = Marshal.GetLastWin32Error();
                return new ClickSimulationResult
                {
                    Success = false,
                    Hwnd = hWnd,
                    ProcessId = winInfo.ProcessId,
                    WindowTitle = winInfo.Title,
                    X = clientX,
                    Y = clientY,
                    DurationMs = durationMs,
                    Button = button,
                    Message = $"Lỗi PostMessage(DOWN), Win32 Error: {err}"
                };
            }

            // 3. Hold click for duration so game frame loop registers the click
            int holdMs = Math.Max(durationMs, 25);
            await Task.Delay(holdMs);

            // 4. Post UP message directly to game window
            var upOk = PostMessage(hWnd, upMsg, IntPtr.Zero, lParam);
            SendMessage(hWnd, WmSetCursor, hWnd, (IntPtr)((WmMouseMove << 16) | HtClient));

            // 5. Instantly restore user's physical cursor back to its exact original position
            if (needCursorSync)
            {
                SetCursorPos(origPos.X, origPos.Y);
            }

            if (!upOk)
            {
                var err = Marshal.GetLastWin32Error();
                return new ClickSimulationResult
                {
                    Success = false,
                    Hwnd = hWnd,
                    ProcessId = winInfo.ProcessId,
                    WindowTitle = winInfo.Title,
                    X = clientX,
                    Y = clientY,
                    DurationMs = durationMs,
                    Button = button,
                    Message = $"Lỗi PostMessage(UP), Win32 Error: {err}"
                };
            }

            var modeDesc = useHardwareFastHop ? "Micro-Sync nền (Bỏ qua con trỏ cũ)" : "Pure PostMessage nền";
            return new ClickSimulationResult
            {
                Success = true,
                Hwnd = hWnd,
                ProcessId = winInfo.ProcessId,
                WindowTitle = winInfo.Title,
                X = clientX,
                Y = clientY,
                DurationMs = durationMs,
                Button = button,
                Message = $"Click thành công [{modeDesc}] tại Client ({clientX}, {clientY}) vào \"{winInfo.Title}\" [0x{hWnd.ToInt64():X}]. Chuột vật lý được hoàn trả ngay lập tức."
            };
        }
        catch (Exception ex)
        {
            return new ClickSimulationResult
            {
                Success = false,
                Hwnd = hWnd,
                ProcessId = winInfo.ProcessId,
                WindowTitle = winInfo.Title,
                X = clientX,
                Y = clientY,
                DurationMs = durationMs,
                Button = button,
                Message = $"Ngoại lệ khi mô phỏng click: {ex.Message}"
            };
        }
    }

    /// <summary>
    /// Simulates a mouse click directly at the center of the window's client rectangle.
    /// </summary>
    public static Task<ClickSimulationResult> SimulateClickCenterAsync(
        IntPtr hWnd,
        int durationMs = 60,
        MouseButton button = MouseButton.Left,
        bool sendActivateMessage = false)
    {
        var winInfo = InspectWindow(hWnd);
        if (winInfo == null)
        {
            return Task.FromResult(new ClickSimulationResult
            {
                Success = false,
                Hwnd = hWnd,
                Message = "Không thể lấy thông tin kích thước cửa sổ."
            });
        }

        var centerX = Math.Max(1, winInfo.ClientRect.Width / 2);
        var centerY = Math.Max(1, winInfo.ClientRect.Height / 2);

        return SimulateClickAsync(hWnd, centerX, centerY, durationMs, button, sendPreMove: true, sendActivateMessage: sendActivateMessage);
    }

    /// <summary>
    /// Struct containing detailed mathematical analysis of movement along isometric axes.
    /// </summary>
    public sealed class AxisMovementAnalysis
    {
        public int CurrentX { get; set; }
        public int CurrentY { get; set; }
        public int TargetX { get; set; }
        public int TargetY { get; set; }
        public int DeltaX { get; set; }
        public int DeltaY { get; set; }
        public int ChebyshevDistance { get; set; }
        public string XDirectionText { get; set; } = string.Empty;
        public string YDirectionText { get; set; } = string.Empty;
        public string ScreenDirection { get; set; } = string.Empty;
        public string SummaryText { get; set; } = string.Empty;
        public bool IsArrived { get; set; }
    }

    /// <summary>
    /// Analyzes the movement direction between current RAM coordinate and target destination.
    /// Distinguishes exactly which axis increases (+X East, +Y North) and which decreases (-X West, -Y South).
    /// </summary>
    public static AxisMovementAnalysis AnalyzeMovementAxes(int curX, int curY, int targetX, int targetY)
    {
        int dx = targetX - curX;
        int dy = targetY - curY;
        int dist = Math.Max(Math.Abs(dx), Math.Abs(dy));

        string xText;
        if (dx > 0)
            xText = $"TĂNG X (+{dx} ô, hướng Phải-Xuống)";
        else if (dx < 0)
            xText = $"GIẢM X ({dx} ô, hướng Trái-Lên)";
        else
            xText = "X Giữ nguyên (0 ô)";

        string yText;
        if (dy > 0)
            yText = $"TĂNG Y (+{dy} ô, hướng Trái-Xuống)";
        else if (dy < 0)
            yText = $"GIẢM Y ({dy} ô, hướng Phải-Lên)";
        else
            yText = "Y Giữ nguyên (0 ô)";

        string screenDir = GetDirectionDescription(dx, dy);
        bool isArrived = dist <= 1;

        string summary = $"Từ ({curX}, {curY}) ➔ Đích ({targetX}, {targetY}) | {xText} | {yText} | Hướng tổng: {screenDir} | Cách: {dist} ô. {(isArrived ? "ĐÃ TỚI ĐÍCH (sai số ≤ 1 ô)" : "Cần di chuyển")}";

        return new AxisMovementAnalysis
        {
            CurrentX = curX,
            CurrentY = curY,
            TargetX = targetX,
            TargetY = targetY,
            DeltaX = dx,
            DeltaY = dy,
            ChebyshevDistance = dist,
            XDirectionText = xText,
            YDirectionText = yText,
            ScreenDirection = screenDir,
            SummaryText = summary,
            IsArrived = isArrived
        };
    }

    /// <summary>
    /// Returns the compass direction name based on delta Game X and delta Game Y (MU Online Isometric axis, 0,0 at Top-Left).
    /// Axis: +X → East (Screen Down-Right); +Y → South (Screen Down-Left)
    /// </summary>
    public static string GetDirectionDescription(int dx, int dy)
    {
        if (dx == 0 && dy == 0) return "Tại chỗ (0, 0)";

        var screenVx = (double)(dx - dy);
        var screenVy = (double)(dx + dy) * 0.55;
        var angle = Math.Atan2(screenVy, screenVx) * (180.0 / Math.PI);
        if (angle < 0) angle += 360;

        return angle switch
        {
            >= 337.5 or < 22.5   => "Phải (+X,-Y)",
            >= 22.5 and < 67.5   => "Phải-Xuống (+X)",
            >= 67.5 and < 112.5  => "Xuống (+X,+Y ra xa gốc 0,0)",
            >= 112.5 and < 157.5 => "Trái-Xuống (+Y)",
            >= 157.5 and < 202.5 => "Trái (-X,+Y)",
            >= 202.5 and < 247.5 => "Trái-Lên (-X)",
            >= 247.5 and < 292.5 => "Lên (-X,-Y về phía gốc 0,0)",
            _                    => "Phải-Lên (-Y)"
        };
    }

    /// <summary>
    /// Converts target game coordinate (Grid X, Y) into screen pixel (px, py)
    /// relative to player's current position using isometric camera projection.
    /// </summary>
    public static Point GameCoordToScreenPixel(
        int playerX,
        int playerY,
        int targetX,
        int targetY,
        int clientWidth,
        int clientHeight,
        float cameraAngleDegrees = 0f,
        float stepScale = 22.0f,
        float maxRadiusRatio = 0.35f)
    {
        if (clientWidth <= 0) clientWidth = 1024;
        if (clientHeight <= 0) clientHeight = 768;

        var cx = clientWidth / 2;
        var cy = clientHeight / 2 + 15; // Offset slightly down to align with ground plane beneath character feet

        var dx = targetX - playerX;
        var dy = targetY - playerY;

        if (dx == 0 && dy == 0)
        {
            return new Point(cx, cy);
        }

        // MU Online Isometric Projection (Origin 0,0 at Top-Left of screen):
        // Moving away from (0,0) (+X, +Y) moves Down (+py)
        // Moving towards (0,0) (-X, -Y) moves Up (-py)
        // Solved system:
        //   screenVx = (dx - dy) * 1.0;
        //   screenVy = (dx + dy) * 0.55;
        double baseVx = (dx - dy) * 1.0;
        double baseVy = (dx + dy) * 0.55;

        // Apply camera rotation if player rotated the 3D camera
        double vx = baseVx;
        double vy = baseVy;
        if (Math.Abs(cameraAngleDegrees) > 0.01f)
        {
            var rad = cameraAngleDegrees * (Math.PI / 180.0);
            var cos = Math.Cos(rad);
            var sin = Math.Sin(rad);
            vx = baseVx * cos - baseVy * sin;
            vy = baseVx * sin + baseVy * cos;
        }

        var distance = Math.Sqrt(vx * vx + vy * vy);
        var maxRadius = Math.Max(100.0, clientHeight * maxRadiusRatio);
        // Minimum radius of 75-80px ensures raycast clicks onto terrain ground, avoiding character's own 3D model/hitbox
        var minRadius = Math.Max(75.0, clientHeight * 0.08);
        var radius = Math.Clamp(distance * stepScale, minRadius, maxRadius);

        var normX = vx / distance;
        var normY = vy / distance;

        var px = (int)Math.Round(cx + normX * radius);
        var py = (int)Math.Round(cy + normY * radius);

        // Clamp inside client area bounds to prevent clicking borders/titlebars/taskbar
        px = Math.Clamp(px, 40, clientWidth - 40);
        py = Math.Clamp(py, 60, clientHeight - 80);

        return new Point(px, py);
    }

    /// <summary>
    /// Reads live player position from RAM, computes the screen pixel via isometric projection,
    /// and simulates a background click toward the target game coordinate.
    /// </summary>
    public static async Task<ClickSimulationResult> SimulateClickGameCoordAsync(
        IntPtr hWnd,
        int processId,
        int targetX,
        int targetY,
        int durationMs = 80,
        float cameraAngleDegrees = 0f,
        bool sendActivateMessage = true,
        bool useHardwareFastHop = false)
    {
        if (!IsWindow(hWnd))
        {
            var resolved = ResolveMainWindow(processId);
            if (resolved != null && IsWindow(resolved.Hwnd))
            {
                hWnd = resolved.Hwnd;
            }
        }

        var winInfo = InspectWindow(hWnd, processId);
        if (winInfo == null)
        {
            return new ClickSimulationResult
            {
                Success = false,
                Hwnd = hWnd,
                ProcessId = processId,
                Message = "Cửa sổ mục tiêu không hợp lệ hoặc đang bị thu nhỏ vào khay hệ thống (Tray). Vui lòng hiện cửa sổ game."
            };
        }

        var warpState = ProcessMemory.ReadWarpMemoryState(processId);
        int currentX = warpState?.CurrentX ?? 0;
        int currentY = warpState?.CurrentY ?? 0;

        if (currentX == 0 && currentY == 0)
        {
            // If RAM coord not read, fallback to center or client click
            var fallback = GameCoordToScreenPixel(0, 0, targetX, targetY, winInfo.ClientRect.Width, winInfo.ClientRect.Height, cameraAngleDegrees);
            var res = await SimulateClickAsync(hWnd, fallback.X, fallback.Y, durationMs, MouseButton.Left, true, sendActivateMessage, useHardwareFastHop);
            res.Message = $"[Ước tính pixel] {res.Message}";
            return res;
        }

        var pixel = GameCoordToScreenPixel(currentX, currentY, targetX, targetY, winInfo.ClientRect.Width, winInfo.ClientRect.Height, cameraAngleDegrees);
        var directionName = GetDirectionDescription(targetX - currentX, targetY - currentY);
        var clickResult = await SimulateClickAsync(hWnd, pixel.X, pixel.Y, durationMs, MouseButton.Left, true, sendActivateMessage, useHardwareFastHop);
        
        clickResult.Message = $"[Tọa độ ({currentX}, {currentY}) -> Đích ({targetX}, {targetY}) | {directionName} => Pixel ({pixel.X}, {pixel.Y})] {clickResult.Message}";
        return clickResult;
    }

    /// <summary>
    /// Subdivides a path between two tile points into intermediate steps if Chebyshev distance exceeds maxStepDistance.
    /// This ensures in-game raycasting/pathfinding never clicks too far off-screen.
    /// </summary>
    public static List<Point> SubdividePath(Point start, Point end, int maxStepDistance = 6)
    {
        var steps = new List<Point>();
        int dx = end.X - start.X;
        int dy = end.Y - start.Y;
        int maxDelta = Math.Max(Math.Abs(dx), Math.Abs(dy));

        if (maxDelta <= maxStepDistance)
        {
            steps.Add(end);
            return steps;
        }

        int count = (int)Math.Ceiling((double)maxDelta / maxStepDistance);
        for (int i = 1; i <= count; i++)
        {
            double ratio = (double)i / count;
            int px = (int)Math.Round(start.X + dx * ratio);
            int py = (int)Math.Round(start.Y + dy * ratio);
            steps.Add(new Point(px, py));
        }

        return steps;
    }

    /// <summary>
    /// Generates optimal shortest-path waypoints connecting current position to target destination.
    /// </summary>
    public static List<Point> GenerateShortestPathWaypoints(Point start, Point target, int maxStepDistance = 6)
    {
        return SubdividePath(start, target, maxStepDistance);
    }

    /// <summary>
    /// Formats a list of coordinate points into waypoints string format: "x1,y1; x2,y2; ...".
    /// </summary>
    public static string FormatWaypointsString(IEnumerable<Point> waypoints)
    {
        return string.Join("; ", waypoints.Select(p => $"{p.X},{p.Y}"));
    }

    /// <summary>
    /// Executes sequential background clicks through a list of waypoints with closed-loop RAM feedback.
    /// It automatically breaks long legs into smaller steps (<= 6 tiles), clicks toward each step,
    /// and waits until the character's live RAM coordinates reach the target (within arrivalRadius) before moving to the next.
    /// Emits real-time RAM delta logs as coordinate fields change in memory.
    /// </summary>
    public static async Task<List<ClickSimulationResult>> SimulateWalkRouteAsync(
        IntPtr hWnd,
        int processId,
        IReadOnlyList<Point> waypoints,
        float cameraAngleDegrees = 0f,
        int arrivalRadius = 1,
        int maxWaitSecondsPerStep = 6,
        Action<string>? onProgress = null,
        CancellationToken cancellationToken = default,
        bool useHardwareFastHop = false)
    {
        var results = new List<ClickSimulationResult>();
        if (waypoints == null || waypoints.Count == 0) return results;

        // 1. Final destination to continually compare against
        Point finalTarget = waypoints[^1];

        // 2. Get initial live position from RAM
        var initialWarp = ProcessMemory.ReadWarpMemoryState(processId);
        Point currentPos = new Point(initialWarp?.CurrentX ?? waypoints[0].X, initialWarp?.CurrentY ?? waypoints[0].Y);

        var initAnalysis = AnalyzeMovementAxes(currentPos.X, currentPos.Y, finalTarget.X, finalTarget.Y);
        onProgress?.Invoke($"=== [BẮT ĐẦU ĐIỀU HƯỚNG TỚI ĐÍCH CUỐI ({finalTarget.X}, {finalTarget.Y})] ===");
        onProgress?.Invoke($"  • Vị trí RAM ban đầu: ({currentPos.X}, {currentPos.Y})");
        onProgress?.Invoke($"  • Trục X: {initAnalysis.XDirectionText}");
        onProgress?.Invoke($"  • Trục Y: {initAnalysis.YDirectionText}");
        onProgress?.Invoke($"  • Hướng di chuyển màn hình: {initAnalysis.ScreenDirection} | Khoảng cách: {initAnalysis.ChebyshevDistance} ô");

        if (initAnalysis.IsArrived)
        {
            onProgress?.Invoke($"[🎉 ĐÃ TỚI ĐÍCH CUỐI CÙNG] Nhân vật đã ở ({currentPos.X}, {currentPos.Y}) [Cách đích {initAnalysis.ChebyshevDistance} ô ≤ 1 ô]. Thỏa mãn điều kiện dừng!");
            return results;
        }

        // 3. Expand waypoints by subdividing long legs into micro-steps (<= 5 tiles)
        var detailedRoute = new List<Point>();
        Point trace = currentPos;
        foreach (var wp in waypoints)
        {
            var segments = SubdividePath(trace, wp, maxStepDistance: 5);
            foreach (var seg in segments)
            {
                if (detailedRoute.Count == 0 || detailedRoute[^1] != seg)
                {
                    detailedRoute.Add(seg);
                }
            }
            trace = wp;
        }

        onProgress?.Invoke($"[LỘ TRÌNH THÔNG MINH] Đã chia thành {detailedRoute.Count} bước đệm ngắn nhất (Tối đa 5 ô/bước).");

        float dynamicAngleOffset = 0f;

        for (int i = 0; i < detailedRoute.Count; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var targetStep = detailedRoute[i];

            // Re-read current RAM coord
            var liveState = ProcessMemory.ReadWarpMemoryState(processId);
            int curX = liveState?.CurrentX ?? currentPos.X;
            int curY = liveState?.CurrentY ?? currentPos.Y;
            currentPos = new Point(curX, curY);

            // Check if already reached final destination
            int distToFinal = Math.Max(Math.Abs(curX - finalTarget.X), Math.Abs(curY - finalTarget.Y));
            if (distToFinal <= 1)
            {
                onProgress?.Invoke($"[🎉 ĐÃ TỚI ĐÍCH CUỐI CÙNG] Vị trí RAM ({curX}, {curY}) khớp đích ({finalTarget.X}, {finalTarget.Y}) [Cách {distToFinal} ô ≤ 1 ô]. Thỏa mãn điều kiện dừng!");
                break;
            }

            int distToStep = Math.Max(Math.Abs(curX - targetStep.X), Math.Abs(curY - targetStep.Y));
            if (distToStep <= arrivalRadius && i < detailedRoute.Count - 1)
            {
                // Already at this step, skip to next
                continue;
            }

            int dxFinal = finalTarget.X - curX;
            int dyFinal = finalTarget.Y - curY;
            string xReq = dxFinal > 0 ? $"TĂNG X (+{dxFinal})" : (dxFinal < 0 ? $"GIẢM X ({dxFinal})" : "X Đạt");
            string yReq = dyFinal > 0 ? $"TĂNG Y (+{dyFinal})" : (dyFinal < 0 ? $"GIẢM Y ({dyFinal})" : "Y Đạt");
            string stepDir = GetDirectionDescription(targetStep.X - curX, targetStep.Y - curY);

            float effectiveAngle = (cameraAngleDegrees + dynamicAngleOffset) % 360f;
            onProgress?.Invoke($"[Bước {i + 1}/{detailedRoute.Count}] Đang ở ({curX}, {curY}) | So với ĐÍCH CUỐI ({finalTarget.X}, {finalTarget.Y}): {xReq}, {yReq} (Còn {distToFinal} ô) ➔ Click mốc ({targetStep.X}, {targetStep.Y}) [Hướng {stepDir}]...");

            // Click towards the target
            var clickRes = await SimulateClickGameCoordAsync(hWnd, processId, targetStep.X, targetStep.Y, 80, effectiveAngle, true, useHardwareFastHop);
            results.Add(clickRes);

            // Closed-loop polling from RAM: Wait until character reaches target or time out
            var sw = Stopwatch.StartNew();
            Point lastPos = currentPos;
            int idleTimeMs = 0;

            while (sw.ElapsedMilliseconds < maxWaitSecondsPerStep * 1000)
            {
                await Task.Delay(200, cancellationToken);

                var poll = ProcessMemory.ReadWarpMemoryState(processId);
                if (poll != null && poll.CurrentX.HasValue && poll.CurrentY.HasValue && poll.CurrentX.Value > 0 && poll.CurrentY.Value > 0)
                {
                    currentPos = new Point(poll.CurrentX.Value, poll.CurrentY.Value);
                    int remainingToStep = Math.Max(Math.Abs(currentPos.X - targetStep.X), Math.Abs(currentPos.Y - targetStep.Y));
                    int remainingToFinal = Math.Max(Math.Abs(currentPos.X - finalTarget.X), Math.Abs(currentPos.Y - finalTarget.Y));

                    if (currentPos != lastPos)
                    {
                        int stepDx = currentPos.X - lastPos.X;
                        int stepDy = currentPos.Y - lastPos.Y;
                        string xStep = stepDx > 0 ? $"TĂNG X (+{stepDx})" : (stepDx < 0 ? $"GIẢM X ({stepDx})" : "X giữ");
                        string yStep = stepDy > 0 ? $"TĂNG Y (+{stepDy})" : (stepDy < 0 ? $"GIẢM Y ({stepDy})" : "Y giữ");

                        int distDelta = remainingToFinal - distToFinal;
                        string distTrend = distDelta < 0 
                            ? $"GẦN HƠN ({-distDelta} ô) ✔" 
                            : (distDelta > 0 ? $"XA HƠN (+{distDelta} ô) ✘" : "Khoảng cách giữ nguyên");

                        onProgress?.Invoke($"  [RAM BIẾN ĐỘNG] ({lastPos.X}, {lastPos.Y}) ➔ ({currentPos.X}, {currentPos.Y}) [{xStep}, {yStep}] | So sánh ĐÍCH CUỐI ({finalTarget.X}, {finalTarget.Y}): Còn {remainingToFinal} ô ({distTrend})");

                        // ADAPTIVE FEEDBACK: Nếu phát hiện đang đi xa hơn, lập tức đảo ngược hướng 180° để kéo gần lại đích!
                        if (distDelta > 0)
                        {
                            onProgress?.Invoke($"  [🔄 PHÁT HIỆN ĐI XA HƠN] Khoảng cách tăng từ {distToFinal} lên {remainingToFinal} ô! Lập tức đảo ngược hướng 180°...");
                            dynamicAngleOffset = (dynamicAngleOffset + 180f) % 360f;
                            float correctiveAngle = (cameraAngleDegrees + dynamicAngleOffset) % 360f;

                            int oppositeX = Math.Clamp(currentPos.X - stepDx * 3, 0, 255);
                            int oppositeY = Math.Clamp(currentPos.Y - stepDy * 3, 0, 255);
                            await SimulateClickGameCoordAsync(hWnd, processId, oppositeX, oppositeY, 80, correctiveAngle, true, useHardwareFastHop);
                        }

                        lastPos = currentPos;
                        distToFinal = remainingToFinal;
                        idleTimeMs = 0;
                    }
                    else
                    {
                        idleTimeMs += 200;
                    }

                    // Check final target completion first!
                    if (remainingToFinal <= 1)
                    {
                        onProgress?.Invoke($"  [🎉 ĐÃ TỚI ĐÍCH CUỐI CÙNG] Tọa độ RAM ({currentPos.X}, {currentPos.Y}) đã đạt đích cuối ({finalTarget.X}, {finalTarget.Y}) [Cách {remainingToFinal} ô ≤ 1 ô]. Thỏa mãn điều kiện dừng!");
                        return results;
                    }

                    bool isFinalStep = (i == detailedRoute.Count - 1);
                    int requiredRemaining = isFinalStep ? 1 : arrivalRadius;

                    if (remainingToStep <= requiredRemaining)
                    {
                        var statusDesc = remainingToStep == 0 ? "Chính xác mốc (0 ô)" : $"Trong bán kính thỏa mãn ({remainingToStep} ô)";
                        onProgress?.Invoke($"  [ĐÃ QUA MỐC {i + 1}/{detailedRoute.Count}] Tọa độ RAM: ({currentPos.X}, {currentPos.Y}) - {statusDesc}");
                        break;
                    }

                    // Check if character is stuck/idle (no position change for 1.4s)
                    if (idleTimeMs >= 1400)
                    {
                        int stepDx = targetStep.X - currentPos.X;
                        int stepDy = targetStep.Y - currentPos.Y;
                        // Calculate orthogonal detour vector (né vật cản 45 độ)
                        int detourDx = stepDx != 0 ? Math.Sign(stepDx) : 1;
                        int detourDy = stepDy != 0 ? -Math.Sign(stepDy) : 1;
                        int detourX = Math.Clamp(currentPos.X + detourDx * 3, 0, 255);
                        int detourY = Math.Clamp(currentPos.Y + detourDy * 3, 0, 255);

                        onProgress?.Invoke($"  [NÉ VẬT CẢN] Nhân vật khựng tại ({currentPos.X}, {currentPos.Y}). Lách qua ({detourX}, {detourY}) rồi tái bám đích ({targetStep.X}, {targetStep.Y})...");
                        float effectiveAngleNow = (cameraAngleDegrees + dynamicAngleOffset) % 360f;
                        await SimulateClickGameCoordAsync(hWnd, processId, detourX, detourY, 80, effectiveAngleNow, true, useHardwareFastHop);
                        await Task.Delay(300, cancellationToken);
                        await SimulateClickGameCoordAsync(hWnd, processId, targetStep.X, targetStep.Y, 80, effectiveAngleNow, true, useHardwareFastHop);
                        idleTimeMs = 0;
                    }
                }
            }

            // Brief pause before next step to maintain natural movement
            await Task.Delay(80, cancellationToken);
        }

        return results;
    }

    /// <summary>
    /// Normalizes map name to standard MU Online chat command parameter (lowercase, no spaces).
    /// </summary>
    public static string NormalizeMoveMapName(string mapName)
    {
        var clean = mapName.Trim().ToLowerInvariant();
        return clean switch
        {
            "lorencia" => "lorencia",
            "devias" => "devias",
            "noria" => "noria",
            "lost tower" or "losttower" => "losttower",
            "atlans" => "atlans",
            "tarkan" => "tarkan",
            "icarus" => "icarus",
            "aida" => "aida",
            "crywolf" => "crywolf",
            "kanturu" or "kanturu remains" or "kanturu ruins" => "kanturu",
            "elbeland" => "elbeland",
            "karutan" => "karutan",
            "raklion" => "raklion",
            "vulcanus" => "vulcanus",
            "dungeon" => "dungeon",
            "ferea" => "ferea",
            "nixies lake" or "nixies" => "nixies",
            "swamp of darkness" or "swamp" => "swamp",
            "deep dungeon" or "deep dungeon 1" => "deepdungeon",
            "kubera mine" => "kuberamine",
            _ => clean.Replace(" ", "")
        };
    }

    /// <summary>
    /// Simulates a virtual key press and release into the background window with valid Win32 scan codes.
    /// </summary>
    public static async Task SendVirtualKeyAsync(IntPtr hWnd, int virtualKey, int durationMs = 40)
    {
        uint scanCode = MapVirtualKey((uint)virtualKey, 0);
        var lParamDown = (IntPtr)(1 | (scanCode << 16));
        var lParamUp = (IntPtr)(1 | (scanCode << 16) | (1 << 30) | (1 << 31));

        PostMessage(hWnd, WmKeyDown, (IntPtr)virtualKey, lParamDown);
        if (durationMs > 0)
        {
            await Task.Delay(durationMs);
        }
        PostMessage(hWnd, WmKeyUp, (IntPtr)virtualKey, lParamUp);
    }

    /// <summary>
    /// Simulates typing a character into the background window via WM_CHAR with valid scan code.
    /// Does NOT send WM_KEYDOWN for letters to prevent triggering game hotkeys (e.g. M=Move, I=Inventory, D=Command).
    /// </summary>
    public static async Task SendCharAsync(IntPtr hWnd, char c, int delayMs = 30)
    {
        uint scanCode = MapVirtualKey((uint)c, 0);
        var lParam = (IntPtr)(1 | (scanCode << 16));
        PostMessage(hWnd, WmChar, (IntPtr)c, lParam);
        if (delayMs > 0)
        {
            await Task.Delay(delayMs);
        }
    }

    /// <summary>
    /// Sends an in-game chat command (e.g. "/m devias") by activating window for input (without moving the mouse),
    /// opening chat (Enter), typing characters with WM_CHAR, and submitting (Enter).
    /// </summary>
    public static async Task<bool> SendChatCommandAsync(IntPtr hWnd, string command)
    {
        if (string.IsNullOrWhiteSpace(command)) return false;

        // 0. Ensure target window has keyboard focus (Mouse cursor remains completely unmoved)
        SendMessage(hWnd, WmActivate, (IntPtr)WaActive, IntPtr.Zero);
        SendMessage(hWnd, WmSetFocus, IntPtr.Zero, IntPtr.Zero);
        SetForegroundWindow(hWnd);
        await Task.Delay(120);

        // 1. Open chat box (Enter) - DO NOT send ESC because ESC opens the Game System Menu!
        await SendVirtualKeyAsync(hWnd, VkReturn, 50);
        await Task.Delay(250); // Wait for chat box input field to activate and focus

        // 2. Type characters via WM_CHAR ONLY (Prevents triggering game hotkeys M, I, V, D)
        foreach (char c in command)
        {
            await SendCharAsync(hWnd, c, 30);
        }
        await Task.Delay(180); // Wait for input buffer

        // 3. Submit command (Enter)
        await SendVirtualKeyAsync(hWnd, VkReturn, 50);
        await Task.Delay(200);

        return true;
    }

    /// <summary>
    /// Automatically checks if player is already on the target map.
    /// If not, sends "/m <targetMapName>", polls RAM until map transition completes,
    /// and then navigates to the target coordinate (targetX, targetY).
    /// </summary>
    public static async Task<ClickSimulationResult> AutoWarpAndNavigateAsync(
        IntPtr hWnd,
        int processId,
        string targetMapName,
        int targetX,
        int targetY,
        float cameraAngleDegrees = 0f,
        Action<string>? onProgress = null,
        CancellationToken cancellationToken = default,
        bool useHardwareFastHop = false)
    {
        if (!IsWindow(hWnd) || IsIconic(hWnd))
        {
            var resolved = ResolveMainWindow(processId);
            if (resolved != null && IsWindow(resolved.Hwnd))
            {
                hWnd = resolved.Hwnd;
            }
        }

        var winInfo = InspectWindow(hWnd, processId);
        if (winInfo == null)
        {
            return new ClickSimulationResult
            {
                Success = false,
                Hwnd = hWnd,
                ProcessId = processId,
                Message = "Cửa sổ mục tiêu không hợp lệ hoặc đang bị ẩn. Vui lòng mở lại cửa sổ game."
            };
        }

        if (winInfo.IsMinimized)
        {
            ShowWindow(hWnd, SwRestore);
            await Task.Delay(250, cancellationToken);
            winInfo = InspectWindow(hWnd, processId) ?? winInfo;
        }

        var initialState = ProcessMemory.ReadWarpMemoryState(processId);
        string currentMap = initialState?.MapName ?? string.Empty;
        int? currentSceneIndex = initialState?.SceneIndex;

        var cleanTarget = NormalizeMoveMapName(targetMapName);
        var cleanCurrent = NormalizeMoveMapName(currentMap);

        bool needWarp = !string.IsNullOrWhiteSpace(targetMapName) &&
                        !string.Equals(currentMap, targetMapName, StringComparison.OrdinalIgnoreCase) &&
                        !string.Equals(cleanTarget, cleanCurrent, StringComparison.OrdinalIgnoreCase);

        if (needWarp)
        {
            onProgress?.Invoke($"[MOVE MAP] Nhân vật đang ở '{currentMap}'. Đang gửi lệnh '/m {cleanTarget}'...");
            await SendChatCommandAsync(hWnd, $"/m {cleanTarget}");

            // Wait and poll RAM for map change (up to 7 seconds)
            var sw = Stopwatch.StartNew();
            bool warpSuccess = false;
            while (sw.ElapsedMilliseconds < 7000)
            {
                cancellationToken.ThrowIfCancellationRequested();
                await Task.Delay(200, cancellationToken);

                var checkState = ProcessMemory.ReadWarpMemoryState(processId);
                if (checkState != null &&
                    (!string.Equals(checkState.MapName, currentMap, StringComparison.OrdinalIgnoreCase) ||
                     (checkState.SceneIndex != currentSceneIndex && checkState.SceneIndex != null)))
                {
                    warpSuccess = true;
                    onProgress?.Invoke($"[MOVE MAP THÀNH CÔNG] Đã sang bản đồ '{checkState.MapName}'. Chờ nhân vật xuất hiện...");
                    await Task.Delay(1500, cancellationToken); // Wait for scene rendering
                    break;
                }
            }

            if (!warpSuccess)
            {
                // Fallback attempt: Try with exact map name in lowercase
                var rawClean = targetMapName.Trim().ToLowerInvariant();
                if (!string.Equals(rawClean, cleanTarget, StringComparison.OrdinalIgnoreCase))
                {
                    onProgress?.Invoke($"[MOVE MAP THỬ LẠI] Thử gửi lại với '/m {rawClean}'...");
                    await SendChatCommandAsync(hWnd, $"/m {rawClean}");

                    var sw2 = Stopwatch.StartNew();
                    while (sw2.ElapsedMilliseconds < 5000)
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        await Task.Delay(200, cancellationToken);

                        var checkState = ProcessMemory.ReadWarpMemoryState(processId);
                        if (checkState != null &&
                            (!string.Equals(checkState.MapName, currentMap, StringComparison.OrdinalIgnoreCase) ||
                             (checkState.SceneIndex != currentSceneIndex && checkState.SceneIndex != null)))
                        {
                            warpSuccess = true;
                            onProgress?.Invoke($"[MOVE MAP THÀNH CÔNG] Đã sang bản đồ '{checkState.MapName}'. Chờ nhân vật xuất hiện...");
                            await Task.Delay(1500, cancellationToken);
                            break;
                        }
                    }
                }
            }

            if (!warpSuccess)
            {
                onProgress?.Invoke($"[CẢNH BÁO] Không phát hiện đổi map sau khi gửi lệnh '/m {cleanTarget}'. Có thể nhân vật không đủ Zen/Level, hoặc đang đứng trong vùng cấm di chuyển. Tiếp tục thử bước...");
            }
        }

        // Now step toward target coordinate
        var freshState = ProcessMemory.ReadWarpMemoryState(processId);
        int curX = freshState?.CurrentX ?? 0;
        int curY = freshState?.CurrentY ?? 0;
        int dist = Math.Max(Math.Abs(targetX - curX), Math.Abs(targetY - curY));

        if (curX > 0 && curY > 0 && dist > 1)
        {
            onProgress?.Invoke($"[ĐI TỚI TỌA ĐỘ] Đích cách {dist} ô. Chạy điều hướng khép kín tới đích cuối ({targetX}, {targetY})...");
            var routeResults = await SimulateWalkRouteAsync(
                hWnd,
                processId,
                new[] { new Point(targetX, targetY) },
                cameraAngleDegrees,
                arrivalRadius: 1,
                maxWaitSecondsPerStep: 6,
                onProgress: onProgress,
                cancellationToken: cancellationToken,
                useHardwareFastHop: useHardwareFastHop);

            var lastRes = routeResults.LastOrDefault();
            return lastRes ?? new ClickSimulationResult
            {
                Success = true,
                Hwnd = hWnd,
                ProcessId = processId,
                Message = $"Hoàn tất di chuyển tới ({targetX}, {targetY})."
            };
        }
        else
        {
            onProgress?.Invoke($"[ĐÃ Ở ĐÍCH] Nhân vật hiện ở ({curX}, {curY}) [Cách đích {dist} ô ≤ 1 ô]. Thỏa mãn điều kiện.");
            return new ClickSimulationResult
            {
                Success = true,
                Hwnd = hWnd,
                ProcessId = processId,
                Message = $"Nhân vật đã ở vị trí đích ({targetX}, {targetY})."
            };
        }
    }
}
