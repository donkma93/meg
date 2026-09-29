using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace MegAccountManager.Services;

public sealed class LiveClientInfo
{
    public int ProcessId { get; init; }
    public string WindowTitle { get; set; } = string.Empty;
    public string CharacterName { get; set; } = string.Empty;
    public string Server { get; set; } = string.Empty;
    public string LevelInfo { get; set; } = string.Empty;
    public string? AccountUsername { get; set; }
    public int? MapId { get; set; }
    public string MapName { get; set; } = string.Empty;
    public int? X { get; set; }
    public int? Y { get; set; }
    public int? TargetX { get; set; }
    public int? TargetY { get; set; }
    public int? LastServerX { get; set; }
    public int? LastServerY { get; set; }
    public int? MapServerMoveActive { get; set; }
    public string Source { get; set; } = "window-title";

    public string MapDisplay => MapId is null ? string.Empty : MapCatalog.Format(MapId);
    public string CoordDisplay => X is null || Y is null ? string.Empty : $"{X}, {Y}";
    public string TargetCoordDisplay => TargetX is null || TargetY is null ? string.Empty : $"{TargetX}, {TargetY}";
    public string LastServerCoordDisplay => LastServerX is null || LastServerY is null ? string.Empty : $"{LastServerX}, {LastServerY}";
}

public sealed class WarpMemoryState
{
    public int ProcessId { get; init; }
    public string ProcessDisplay { get; set; } = string.Empty;
    public long GameAssemblyBase { get; set; }
    public long GameTypeInfo { get; set; }
    public long GameInstance { get; set; }
    public long WorldPtr { get; set; }
    public int? SceneIndex { get; set; }
    public string MapName { get; set; } = string.Empty;
    public long PlayerPtr { get; set; }
    public int? CurrentX { get; set; }
    public int? CurrentY { get; set; }
    public int? TargetX { get; set; }
    public int? TargetY { get; set; }
    public int? LastServerX { get; set; }
    public int? LastServerY { get; set; }
    public long MapServerMovePtr { get; set; }
    public int IsActive { get; set; }
    public int IsServerChange { get; set; }
    public float QuitTime { get; set; }
    public long AuthKeysPtr { get; set; }
    public bool AuthKeysNonZero { get; set; }
    public int? SpotTargetX { get; set; }
    public int? SpotTargetY { get; set; }
    public float PosX { get; set; }
    public float PosY { get; set; }
    public float PosZ { get; set; }
    public DateTime SampledAtUtc { get; set; } = DateTime.UtcNow;

    public string CurrentCoordDisplay => CurrentX is null || CurrentY is null ? "—" : $"({CurrentX}, {CurrentY})";
    public string TargetCoordDisplay => TargetX is null || TargetY is null ? "—" : $"({TargetX}, {TargetY})";
    public string LastServerCoordDisplay => LastServerX is null || LastServerY is null ? "—" : $"({LastServerX}, {LastServerY})";
    public string SpotTargetCoordDisplay => SpotTargetX is null || SpotTargetY is null ? "—" : $"({SpotTargetX}, {SpotTargetY})";
}

public sealed class RamFieldItem
{
    public string Category { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Offset { get; set; } = string.Empty;
    public string AddressHex { get; set; } = string.Empty;
    public string ValueDisplay { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
}

public sealed class RamDeltaLog
{
    public DateTime Timestamp { get; set; } = DateTime.Now;
    public string Category { get; set; } = string.Empty;
    public string PropertyName { get; set; } = string.Empty;
    public string OldValue { get; set; } = string.Empty;
    public string NewValue { get; set; } = string.Empty;
    public string Note { get; set; } = string.Empty;
}

public static class ProcessMemory
{
    private const int ProcessQueryInformation = 0x0400;
    private const int ProcessVmRead = 0x0010;
    private const uint MemCommit = 0x1000;
    private const uint MemPrivate = 0x20000;
    private const uint PageNoAccess = 0x01;
    private const uint PageGuard = 0x100;
    private const uint Th32CsSnapModule = 0x00000008;
    private const uint Th32CsSnapModule32 = 0x00000010;

    // IL2CPP roots from GameAssembly.dll (Il2CppDumper + live probe).
    // GameBehaviour.KAKEPBGBJCG getter resolves through Mega.Game_TypeInfo:
    //   TypeInfo -> static_fields(+0xB8) -> Instance(+0x8) -> _Player(+0x208)
    private const long GameTypeInfoRva = 0x5609F28;
    private const int KlassStaticFieldsOffset = 0xB8;
    private const int GameStaticInstanceOffset = 0x8;
    private const int GamePlayerOffset = 0x208;
    private const int GameWorldOffset = 0x200;
    private const int GameMapServerMoveOffset = 0xC0;
    private const int BodyCurrentCoordOffset = 0x68;
    private const int BodyTargetCoordOffset = 0x70;
    private const int LastServerCoordOffset = 0x4E0;
    private const int WorldSceneIndexOffset = 0x20;
    private const int CoordXOffset = 0x10;
    private const int CoordYOffset = 0x14;
    private const int MapServerMoveAuthKeysOffset = 0x10;
    private const int MapServerMoveQuitTimeOffset = 0x34;
    private const int MapServerMoveIsActiveOffset = 0x6C;

    private static readonly ConcurrentDictionary<int, nint> GameAssemblyBaseCache = new();

    // UTF-16LE "Coord(" — Unity stores these HUD/log strings as wide chars.
    private static readonly byte[] CoordUtf16Needle = Encoding.Unicode.GetBytes("Coord(");

    private static readonly Regex TitleRegex = new(
        @"^(?<char>.+?)\s+\((?<level>[^)]+)\)\s+-\s+MEGAMU\s+(?<server>Sv\d+)\s*$",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex LastUserJsonRegex = new(
        "\"LastCharacter\"\\s*:\\s*\"(?<char>[^\"]+)\"\\s*,\\s*\"LastUsername\"\\s*:\\s*\"(?<user>[^\"]+)\"",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex LastUserLooseRegex = new(
        "LastCharacter.{0,40}(?<char>[A-Za-z0-9_]{2,20}).{0,80}LastUsername.{0,40}(?<user>[A-Za-z0-9_]{2,32})",
        RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.Singleline);

    private static readonly Regex CoordRegex = new(
        @"Coord\((?<x>\d{1,3}),\s*(?<y>\d{1,3})\)",
        RegexOptions.Compiled);

    private static readonly Regex LoadWorldRegex = new(
        @"Load World Scene:\s*(?<id>\d{1,3})",
        RegexOptions.Compiled);

    private static readonly Regex WorldPathRegex = new(
        @"Worlds/Group\d+/World(?<id>\d{1,3})/",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex WorldBundleRegex = new(
        @"world(?<id>\d{1,3})\.bundle",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int VirtualQueryEx(
        IntPtr hProcess,
        IntPtr lpAddress,
        out MemoryBasicInformation lpBuffer,
        uint dwLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(
        IntPtr hProcess,
        IntPtr lpBaseAddress,
        byte[] lpBuffer,
        int dwSize,
        out int lpNumberOfBytesRead);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint dwFlags, uint th32ProcessID);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool Module32FirstW(IntPtr hSnapshot, ref ModuleEntry32W lpme);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool Module32NextW(IntPtr hSnapshot, ref ModuleEntry32W lpme);

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryBasicInformation
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ModuleEntry32W
    {
        public uint dwSize;
        public uint th32ModuleID;
        public uint th32ProcessID;
        public uint GlblcntUsage;
        public uint ProccntUsage;
        public IntPtr modBaseAddr;
        public uint modBaseSize;
        public IntPtr hModule;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
        public string szModule;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szExePath;
    }

    public static IReadOnlyList<LiveClientInfo> GetLiveClientsFromWindowTitles()
    {
        var result = new List<LiveClientInfo>();
        foreach (var process in Process.GetProcessesByName("MEGAMU"))
        {
            try
            {
                var title = process.MainWindowTitle?.Trim() ?? string.Empty;
                var match = string.IsNullOrWhiteSpace(title) ? Match.Empty : TitleRegex.Match(title);

                var charName = match.Success
                    ? match.Groups["char"].Value.Trim()
                    : (!string.IsNullOrWhiteSpace(title) ? title : $"MEGAMU #{process.Id}");

                var levelInfo = match.Success ? match.Groups["level"].Value.Trim() : string.Empty;
                var server = match.Success ? match.Groups["server"].Value.Trim() : string.Empty;
                var source = !string.IsNullOrWhiteSpace(title) ? "window-title" : "process-id";

                result.Add(new LiveClientInfo
                {
                    ProcessId = process.Id,
                    WindowTitle = string.IsNullOrWhiteSpace(title) ? "(Ẩn / Tray)" : title,
                    CharacterName = charName,
                    LevelInfo = levelInfo,
                    Server = server,
                    Source = source
                });
            }
            finally
            {
                process.Dispose();
            }
        }

        return result
            .OrderBy(c => c.Server, StringComparer.OrdinalIgnoreCase)
            .ThenBy(c => c.CharacterName, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public static IReadOnlyList<LiveClientInfo> ScanLiveClients(CancellationToken cancellationToken = default)
    {
        var clients = GetLiveClientsFromWindowTitles().ToList();
        foreach (var client in clients)
        {
            cancellationToken.ThrowIfCancellationRequested();
            EnrichClientFromMemory(client, cancellationToken);
        }

        // Fallback / cross-check with MEGAMU AccountList in registry.
        try
        {
            var snapshot = RegistryAccountReader.Read();
            RegistryAccountReader.EnrichLiveClients(clients, snapshot);
        }
        catch
        {
            // Registry may be unavailable; memory results are still useful.
        }

        return clients;
    }

    public static void EnrichClientFromMemory(LiveClientInfo client, CancellationToken cancellationToken = default)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, client.ProcessId);
        if (handle == IntPtr.Zero)
        {
            return;
        }

        try
        {
            TryApplyIl2CppState(handle, client.ProcessId, client, wantCoords: true, wantMap: true);

            var accountVotes = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            var mapScores = new Dictionary<int, int>();
            var coordScores = new Dictionary<(int X, int Y), int>();

            void consume(string chunk)
            {
                cancellationToken.ThrowIfCancellationRequested();
                CollectUsernameVotes(chunk, client.CharacterName, accountVotes);
                CollectLocationVotes(chunk, mapScores, coordScores);
            }

            // Account / world-path strings often appear as ASCII; Coord is UTF-16.
            ScanTextChunks(handle, unicode: false, consume, cancellationToken);

            if (accountVotes.Count == 0 || mapScores.Count == 0)
            {
                ScanTextChunks(handle, unicode: true, consume, cancellationToken);
            }

            var account = accountVotes
                .OrderByDescending(kv => kv.Value)
                .ThenByDescending(kv => kv.Key.Length)
                .Select(kv => kv.Key)
                .FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(account))
            {
                client.AccountUsername = account;
                if (client.Source is "window-title" or null or "")
                {
                    client.Source = "memory:LastUsername";
                }
            }

            if (client.MapId is null)
            {
                var mapId = mapScores
                    .OrderByDescending(kv => kv.Value)
                    .ThenByDescending(kv => kv.Key)
                    .Select(kv => (int?)kv.Key)
                    .FirstOrDefault();
                if (mapId is not null)
                {
                    client.MapId = mapId;
                    client.MapName = MapCatalog.GetName(mapId);
                }
            }

            if (client.X is null || client.Y is null)
            {
                if (!TryApplyCoordMajority(handle, client, cancellationToken) &&
                    coordScores.Count > 0)
                {
                    var bestCoord = coordScores
                        .OrderByDescending(kv => kv.Value)
                        .Select(kv => kv.Key)
                        .First();
                    client.X = bestCoord.X;
                    client.Y = bestCoord.Y;
                    if (client.Source is "window-title" or null or "")
                    {
                        client.Source = "memory:Coord";
                    }
                }
            }
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    /// <summary>
    /// Fast realtime pass: IL2CPP pointer chain from GameAssembly, with UTF-16 Coord fallback.
    /// </summary>
    public static bool RefreshClientCoords(LiveClientInfo client, CancellationToken cancellationToken = default)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, client.ProcessId);
        if (handle == IntPtr.Zero)
        {
            return false;
        }

        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (TryApplyIl2CppState(handle, client.ProcessId, client, wantCoords: true, wantMap: false))
            {
                return true;
            }

            return TryApplyCoordMajority(handle, client, cancellationToken);
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    /// <summary>
    /// Lightweight map refresh via IL2CPP World.SceneIndex, then World path strings.
    /// </summary>
    public static bool RefreshClientMap(LiveClientInfo client, CancellationToken cancellationToken = default)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, client.ProcessId);
        if (handle == IntPtr.Zero)
        {
            return false;
        }

        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (TryApplyIl2CppState(handle, client.ProcessId, client, wantCoords: false, wantMap: true) &&
                client.MapId is not null)
            {
                return true;
            }

            var mapScores = new Dictionary<int, int>();
            void consume(string chunk)
            {
                cancellationToken.ThrowIfCancellationRequested();
                CollectLocationVotes(chunk, mapScores, coordScores: null);
            }

            ScanTextChunks(handle, unicode: false, consume, cancellationToken, privateOnly: true);
            if (mapScores.Count == 0)
            {
                ScanTextChunks(handle, unicode: true, consume, cancellationToken, privateOnly: true);
            }

            var mapId = mapScores
                .OrderByDescending(kv => kv.Value)
                .ThenByDescending(kv => kv.Key)
                .Select(kv => (int?)kv.Key)
                .FirstOrDefault();
            if (mapId is null)
            {
                return false;
            }

            client.MapId = mapId;
            client.MapName = MapCatalog.GetName(mapId);
            return true;
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    /// <summary>
    /// Reads both player coordinates and world scene directly from the IL2CPP object
    /// graph. Unlike the individual refresh methods, this does not use text-scanning
    /// fallbacks, so it is suitable for diagnostic probes.
    /// </summary>
    public static bool RefreshClientIl2CppState(LiveClientInfo client)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, client.ProcessId);
        if (handle == IntPtr.Zero)
        {
            return false;
        }

        try
        {
            return TryApplyIl2CppState(handle, client.ProcessId, client, wantCoords: true, wantMap: true);
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    /// <summary>
    /// Resolve live player coords / map through:
    /// GameAssembly + Mega.Game_TypeInfo → static Instance → _Player / _World.
    /// </summary>
    private static bool TryApplyIl2CppState(
        IntPtr handle,
        int processId,
        LiveClientInfo client,
        bool wantCoords,
        bool wantMap)
    {
        if (!TryResolveGameAssemblyBase(handle, processId, out var gameAssemblyBase))
        {
            return false;
        }

        if (!TryReadPointer(handle, gameAssemblyBase + GameTypeInfoRva, out var typeInfo) ||
            typeInfo == 0)
        {
            return false;
        }

        if (!TryReadPointer(handle, typeInfo + KlassStaticFieldsOffset, out var staticFields) ||
            staticFields == 0)
        {
            return false;
        }

        if (!TryReadPointer(handle, staticFields + GameStaticInstanceOffset, out var gameInstance) ||
            gameInstance == 0)
        {
            return false;
        }

        var applied = false;

        if (wantCoords &&
            TryReadPointer(handle, gameInstance + GamePlayerOffset, out var player) &&
            player != 0 &&
            TryReadPlayerCoordinates(handle, player, out var x, out var y, out var tx, out var ty, out var sx, out var sy))
        {
            client.X = x;
            client.Y = y;
            client.TargetX = tx;
            client.TargetY = ty;
            client.LastServerX = sx;
            client.LastServerY = sy;
            client.Source = "il2cpp:Body.Coord";
            applied = true;
        }

        if (TryReadPointer(handle, gameInstance + GameMapServerMoveOffset, out var msm) && msm != 0)
        {
            if (TryReadInt32(handle, msm + MapServerMoveIsActiveOffset, out var isActive) ||
                TryReadInt32(handle, msm + 0x70, out isActive))
            {
                client.MapServerMoveActive = isActive;
            }
        }

        if (wantMap &&
            TryReadPointer(handle, gameInstance + GameWorldOffset, out var world) &&
            world != 0 &&
            TryReadInt32(handle, world + WorldSceneIndexOffset, out var sceneIndex) &&
            sceneIndex is >= 0 and <= 255)
        {
            client.MapId = sceneIndex;
            client.MapName = MapCatalog.GetName(sceneIndex);
            applied = true;
        }

        return applied;
    }

    private static bool TryReadPlayerCoordinates(
        IntPtr handle,
        long player,
        out int x,
        out int y)
    {
        return TryReadPlayerCoordinates(handle, player, out x, out y, out _, out _, out _, out _);
    }

    private static bool TryReadPlayerCoordinates(
        IntPtr handle,
        long player,
        out int x,
        out int y,
        out int? targetX,
        out int? targetY,
        out int? serverX,
        out int? serverY)
    {
        x = 0;
        y = 0;
        targetX = null;
        targetY = null;
        serverX = null;
        serverY = null;

        // Target Coord
        if (TryReadPointer(handle, player + BodyTargetCoordOffset, out var targetCoordPtr) && targetCoordPtr != 0)
        {
            if (TryReadInt32(handle, targetCoordPtr + CoordXOffset, out var tcx) &&
                TryReadInt32(handle, targetCoordPtr + CoordYOffset, out var tcy) &&
                tcx is >= 0 and <= 255 && tcy is >= 0 and <= 255)
            {
                targetX = tcx;
                targetY = tcy;
            }
        }

        // Last Server Coord
        if (TryReadPointer(handle, player + LastServerCoordOffset, out var srvCoordPtr) && srvCoordPtr != 0)
        {
            if (TryReadInt32(handle, srvCoordPtr + CoordXOffset, out var scx) &&
                TryReadInt32(handle, srvCoordPtr + CoordYOffset, out var scy) &&
                scx is >= 0 and <= 255 && scy is >= 0 and <= 255)
            {
                serverX = scx;
                serverY = scy;
            }
        }

        // Live Body tile coord
        foreach (var offset in new[] { BodyCurrentCoordOffset, BodyTargetCoordOffset, LastServerCoordOffset })
        {
            if (!TryReadPointer(handle, player + offset, out var coordPtr) || coordPtr == 0)
            {
                continue;
            }

            if (!TryReadInt32(handle, coordPtr + CoordXOffset, out var cx) ||
                !TryReadInt32(handle, coordPtr + CoordYOffset, out var cy))
            {
                continue;
            }

            if (cx is < 0 or > 255 || cy is < 0 or > 255)
            {
                continue;
            }

            // LastServerCoordinates often stays at (0,0) until a server sync; skip that sentinel
            // when a better live Body coord already exists further up the preference list.
            if (offset == LastServerCoordOffset && cx == 0 && cy == 0)
            {
                continue;
            }

            x = cx;
            y = cy;
            return true;
        }

        return false;
    }

    private static bool TryResolveGameAssemblyBase(IntPtr handle, int processId, out long baseAddress)
    {
        baseAddress = 0;
        if (GameAssemblyBaseCache.TryGetValue(processId, out var cached) && cached != 0)
        {
            // Validate cache still points at readable TypeInfo slot.
            if (TryReadPointer(handle, cached + GameTypeInfoRva, out _))
            {
                baseAddress = cached;
                return true;
            }

            GameAssemblyBaseCache.TryRemove(processId, out _);
        }

        var snapshot = CreateToolhelp32Snapshot(Th32CsSnapModule | Th32CsSnapModule32, (uint)processId);
        if (snapshot == IntPtr.Zero || snapshot == new IntPtr(-1))
        {
            return false;
        }

        try
        {
            var entry = new ModuleEntry32W
            {
                dwSize = (uint)Marshal.SizeOf<ModuleEntry32W>()
            };

            if (!Module32FirstW(snapshot, ref entry))
            {
                return false;
            }

            do
            {
                var moduleName = entry.szModule ?? string.Empty;
                if (moduleName.Equals("GameAssembly.dll", StringComparison.OrdinalIgnoreCase))
                {
                    baseAddress = entry.modBaseAddr.ToInt64();
                    if (baseAddress != 0)
                    {
                        GameAssemblyBaseCache[processId] = (nint)baseAddress;
                        return true;
                    }
                }
            }
            while (Module32NextW(snapshot, ref entry));
        }
        finally
        {
            CloseHandle(snapshot);
        }

        return false;
    }

    private static bool TryReadPointer(IntPtr handle, long address, out long value)
    {
        value = 0;
        var buffer = new byte[8];
        if (!ReadProcessMemory(handle, (IntPtr)address, buffer, buffer.Length, out var read) || read != 8)
        {
            return false;
        }

        value = BitConverter.ToInt64(buffer, 0);
        return true;
    }

    private static bool TryReadInt32(IntPtr handle, long address, out int value)
    {
        value = 0;
        var buffer = new byte[4];
        if (!ReadProcessMemory(handle, (IntPtr)address, buffer, buffer.Length, out var read) || read != 4)
        {
            return false;
        }

        value = BitConverter.ToInt32(buffer, 0);
        return true;
    }

    private static bool TryReadFloat(IntPtr handle, long address, out float value)
    {
        value = 0f;
        var buffer = new byte[4];
        if (!ReadProcessMemory(handle, (IntPtr)address, buffer, buffer.Length, out var read) || read != 4)
        {
            return false;
        }

        value = BitConverter.ToSingle(buffer, 0);
        return true;
    }

    public static WarpMemoryState? ReadWarpMemoryState(int processId)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, processId);
        if (handle == IntPtr.Zero)
        {
            return null;
        }

        try
        {
            if (!TryResolveGameAssemblyBase(handle, processId, out var baseAddr))
            {
                return null;
            }

            if (!TryReadPointer(handle, baseAddr + GameTypeInfoRva, out var typeInfo) || typeInfo == 0)
            {
                return null;
            }

            if (!TryReadPointer(handle, typeInfo + KlassStaticFieldsOffset, out var staticFields) || staticFields == 0)
            {
                return null;
            }

            if (!TryReadPointer(handle, staticFields + GameStaticInstanceOffset, out var gameInstance) || gameInstance == 0)
            {
                return null;
            }

            var state = new WarpMemoryState
            {
                ProcessId = processId,
                ProcessDisplay = $"PID {processId}",
                GameAssemblyBase = baseAddr,
                GameTypeInfo = typeInfo,
                GameInstance = gameInstance,
                SampledAtUtc = DateTime.UtcNow
            };

            // World & SceneIndex
            if (TryReadPointer(handle, gameInstance + GameWorldOffset, out var world) && world != 0)
            {
                state.WorldPtr = world;
                if (TryReadInt32(handle, world + WorldSceneIndexOffset, out var sceneIndex) && sceneIndex is >= 0 and <= 255)
                {
                    state.SceneIndex = sceneIndex;
                    state.MapName = MapCatalog.GetName(sceneIndex);
                }
            }

            // Player & Coordinates
            if (TryReadPointer(handle, gameInstance + GamePlayerOffset, out var player) && player != 0)
            {
                state.PlayerPtr = player;
                if (TryReadPlayerCoordinates(handle, player, out var cx, out var cy, out var tx, out var ty, out var sx, out var sy))
                {
                    state.CurrentX = cx;
                    state.CurrentY = cy;
                    state.TargetX = tx;
                    state.TargetY = ty;
                    state.LastServerX = sx;
                    state.LastServerY = sy;
                }

                // 3D Transform position float coords
                TryReadFloat(handle, player + 0x330, out var px);
                TryReadFloat(handle, player + 0x334, out var py);
                TryReadFloat(handle, player + 0x338, out var pz);
                state.PosX = px;
                state.PosY = py;
                state.PosZ = pz;

                // Spot / PT target coord from _Player + 0x4A8
                if (TryReadPointer(handle, player + 0x4A8, out var spotPtr) && spotPtr != 0)
                {
                    if (TryReadInt32(handle, spotPtr + CoordXOffset, out var spx) &&
                        TryReadInt32(handle, spotPtr + CoordYOffset, out var spy) &&
                        spx is >= 0 and <= 255 && spy is >= 0 and <= 255 && (spx > 0 || spy > 0))
                    {
                        state.SpotTargetX = spx;
                        state.SpotTargetY = spy;
                    }
                }
            }

            // MapServerMove (Warp)
            if (TryReadPointer(handle, gameInstance + GameMapServerMoveOffset, out var msm) && msm != 0)
            {
                state.MapServerMovePtr = msm;
                TryReadFloat(handle, msm + MapServerMoveQuitTimeOffset, out var quitTime);
                state.QuitTime = quitTime;

                TryReadPointer(handle, msm + MapServerMoveAuthKeysOffset, out var authKeys);
                state.AuthKeysPtr = authKeys;
                state.AuthKeysNonZero = authKeys != 0;

                if (TryReadInt32(handle, msm + MapServerMoveIsActiveOffset, out var isActive) ||
                    TryReadInt32(handle, msm + 0x70, out isActive))
                {
                    state.IsActive = isActive;
                }
            }

            return state;
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    public static List<RamFieldItem> InspectProcessRamFields(int processId)
    {
        var items = new List<RamFieldItem>();
        var state = ReadWarpMemoryState(processId);
        if (state is null)
        {
            items.Add(new RamFieldItem
            {
                Category = "Trạng thái",
                Name = "Process",
                ValueDisplay = $"Không thể mở hoặc đọc bộ nhớ PID {processId}",
                Description = "Process có thể đã đóng hoặc quyền truy cập bị từ chối."
            });
            return items;
        }

        // Singleton & Runtime
        items.Add(new RamFieldItem
        {
            Category = "Singleton",
            Name = "GameAssembly Base",
            Offset = "Module Base",
            AddressHex = $"0x{state.GameAssemblyBase:X}",
            ValueDisplay = $"0x{state.GameAssemblyBase:X}",
            Description = "Địa chỉ nạp GameAssembly.dll trong RAM 64-bit"
        });
        items.Add(new RamFieldItem
        {
            Category = "Singleton",
            Name = "Mega.Game_TypeInfo",
            Offset = "RVA +0x5609F28",
            AddressHex = $"0x{state.GameTypeInfo:X}",
            ValueDisplay = $"0x{state.GameTypeInfo:X}",
            Description = "Con trỏ bảng kiểu dữ liệu IL2CPP của lớp Mega.Game"
        });
        items.Add(new RamFieldItem
        {
            Category = "Singleton",
            Name = "Mega.Game.Instance",
            Offset = "StaticFields +0x08",
            AddressHex = $"0x{state.GameInstance:X}",
            ValueDisplay = $"0x{state.GameInstance:X}",
            Description = "Singleton quản lý trạng thái toàn cục của game client"
        });

        // World & Map
        items.Add(new RamFieldItem
        {
            Category = "Bản đồ (World)",
            Name = "Game._World Pointer",
            Offset = "+0x200",
            AddressHex = $"0x{state.WorldPtr:X}",
            ValueDisplay = state.WorldPtr != 0 ? $"0x{state.WorldPtr:X}" : "NULL",
            Description = "Con trỏ đối tượng thế giới / scene hiện tại"
        });
        items.Add(new RamFieldItem
        {
            Category = "Bản đồ (World)",
            Name = "SceneIndex (Map ID)",
            Offset = "_World +0x20",
            AddressHex = state.WorldPtr != 0 ? $"0x{state.WorldPtr + WorldSceneIndexOffset:X}" : "—",
            ValueDisplay = state.SceneIndex is not null ? $"{state.SceneIndex} ({state.MapName})" : "Chưa xác định",
            Description = "ID bản đồ hiện tại (0: Lorencia, 2: Devias, 3: Noria, 7: Atlans...)"
        });

        // Player Coordinates
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "Game._Player Pointer",
            Offset = "+0x208",
            AddressHex = $"0x{state.PlayerPtr:X}",
            ValueDisplay = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr:X}" : "NULL",
            Description = "Con trỏ thực thể nhân vật điều khiển (Local Player Body)"
        });
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "Live Tile Coord",
            Offset = "_Player +0x68 -> +0x10, +0x14",
            AddressHex = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr + BodyCurrentCoordOffset:X}" : "—",
            ValueDisplay = state.CurrentCoordDisplay,
            Description = "Tọa độ ô gạch trực tiếp của nhân vật trên mặt lưới bản đồ"
        });
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "Target Tile Coord",
            Offset = "_Player +0x70 -> +0x10, +0x14",
            AddressHex = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr + BodyTargetCoordOffset:X}" : "—",
            ValueDisplay = state.TargetCoordDisplay,
            Description = "Tọa độ ô gạch mục tiêu mà nhân vật đang di chuyển tới"
        });
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "Last Server Coord",
            Offset = "_Player +0x4E0 -> +0x10, +0x14",
            AddressHex = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr + LastServerCoordOffset:X}" : "—",
            ValueDisplay = state.LastServerCoordDisplay,
            Description = "Tọa độ đồng bộ lần gần nhất từ GameServer"
        });
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "3D World Position",
            Offset = "_Player +0x330",
            AddressHex = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr + 0x330:X}" : "—",
            ValueDisplay = $"X={state.PosX:F2}, Y={state.PosY:F2}, Z={state.PosZ:F2}",
            Description = "Tọa độ 3D Transform nội bộ của Unity Engine"
        });
        items.Add(new RamFieldItem
        {
            Category = "Tọa độ (Player)",
            Name = "Spot / PT Target Coord",
            Offset = "_Player +0x4A8 -> +0x10, +0x14",
            AddressHex = state.PlayerPtr != 0 ? $"0x{state.PlayerPtr + 0x4A8:X}" : "—",
            ValueDisplay = state.SpotTargetCoordDisplay,
            Description = "Tọa độ bãi train hoặc vị trí theo sau đồng đội PT được lưu sẵn trong RAM game"
        });

        // Warp & MapServerMove
        items.Add(new RamFieldItem
        {
            Category = "Warp (MapServerMove)",
            Name = "_MapServerMove Pointer",
            Offset = "+0x0C0",
            AddressHex = $"0x{state.MapServerMovePtr:X}",
            ValueDisplay = state.MapServerMovePtr != 0 ? $"0x{state.MapServerMovePtr:X}" : "NULL",
            Description = "Quản lý tiến trình dịch chuyển đổi GameServer (Cross-server warp)"
        });
        items.Add(new RamFieldItem
        {
            Category = "Warp (MapServerMove)",
            Name = "QuitTime (Timestamp)",
            Offset = "_MSM +0x34",
            AddressHex = state.MapServerMovePtr != 0 ? $"0x{state.MapServerMovePtr + MapServerMoveQuitTimeOffset:X}" : "—",
            ValueDisplay = $"{state.QuitTime:F1}",
            Description = "Thời gian Unity Time.time đếm ngược khi thực hiện chuyển server"
        });
        items.Add(new RamFieldItem
        {
            Category = "Warp (MapServerMove)",
            Name = "AuthKeys Pointer",
            Offset = "_MSM +0x10",
            AddressHex = state.MapServerMovePtr != 0 ? $"0x{state.MapServerMovePtr + MapServerMoveAuthKeysOffset:X}" : "—",
            ValueDisplay = state.AuthKeysPtr != 0 ? $"0x{state.AuthKeysPtr:X} (Đã cấp phát)" : "NULL",
            Description = "Con trỏ Token/Session Key xác thực bắt tay với GameServer đích"
        });
        items.Add(new RamFieldItem
        {
            Category = "Warp (MapServerMove)",
            Name = "MSM IsActive",
            Offset = "_MSM +0x6C / +0x70",
            AddressHex = state.MapServerMovePtr != 0 ? $"0x{state.MapServerMovePtr + MapServerMoveIsActiveOffset:X}" : "—",
            ValueDisplay = state.IsActive.ToString(),
            Description = state.IsActive == 1 ? "1 (ĐANG TRONG TIẾN TRÌNH WARP LIÊN SERVER)" : "0 (Bình thường / Idle)"
        });

        return items;
    }

    /// <summary>
    /// Diagnostic probe that dumps the memory layout of _Player and _World in RAM to reveal
    /// internal structures, coordinates, AutoMove properties, and navigation path lists.
    /// </summary>
    public static string DumpPlayerMemoryDiagnostic(int processId)
    {
        var sb = new StringBuilder();
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, processId);
        if (handle == IntPtr.Zero)
        {
            return $"Không thể mở tiến trình PID {processId}";
        }

        try
        {
            if (!TryResolveGameAssemblyBase(handle, processId, out var baseAddr))
                return "Không tìm thấy GameAssembly.dll";

            if (!TryReadPointer(handle, baseAddr + GameTypeInfoRva, out var typeInfo) || typeInfo == 0)
                return "Không đọc được Game_TypeInfo";

            if (!TryReadPointer(handle, typeInfo + KlassStaticFieldsOffset, out var staticFields) || staticFields == 0)
                return "Không đọc được staticFields";

            if (!TryReadPointer(handle, staticFields + GameStaticInstanceOffset, out var gameInstance) || gameInstance == 0)
                return "Không đọc được Game.Instance";

            TryReadPointer(handle, gameInstance + GameWorldOffset, out var worldPtr);
            TryReadPointer(handle, gameInstance + GamePlayerOffset, out var playerPtr);

            sb.AppendLine($"=== DIAGNOSTIC BỘ NHỚ PID {processId} ===");
            sb.AppendLine($"GameAssemblyBase: 0x{baseAddr:X}");
            sb.AppendLine($"Game.Instance:    0x{gameInstance:X}");
            sb.AppendLine($"Game._World:      0x{worldPtr:X}");
            sb.AppendLine($"Game._Player:     0x{playerPtr:X}");

            if (playerPtr != 0)
            {
                var playerBuf = new byte[0x600];
                if (ReadProcessMemory(handle, (IntPtr)playerPtr, playerBuf, playerBuf.Length, out var readBytes))
                {
                    sb.AppendLine($"\n--- DUMP CÁC TRƯỜNG CỦA _Player (LocalCharacterBody: 0x{playerPtr:X}, Read: {readBytes} bytes) ---");
                    for (int off = 0; off < readBytes - 8; off += 8)
                    {
                        var ptrVal = BitConverter.ToInt64(playerBuf, off);
                        var intVal1 = BitConverter.ToInt32(playerBuf, off);
                        var intVal2 = BitConverter.ToInt32(playerBuf, off + 4);
                        var fVal1 = BitConverter.ToSingle(playerBuf, off);
                        var fVal2 = BitConverter.ToSingle(playerBuf, off + 4);

                        var isPointer = ptrVal > 0x10000000000L && ptrVal < 0x7FFFFFFFFFFFL;
                        string detail = "";

                        if (isPointer)
                        {
                            var subBuf = new byte[128];
                            if (ReadProcessMemory(handle, (IntPtr)ptrVal, subBuf, subBuf.Length, out var subRead) && subRead >= 32)
                            {
                                var subIntX = BitConverter.ToInt32(subBuf, 0x10);
                                var subIntY = BitConverter.ToInt32(subBuf, 0x14);

                                if (subIntX >= 0 && subIntX <= 255 && subIntY >= 0 && subIntY <= 255 && (subIntX > 0 || subIntY > 0))
                                {
                                    detail += $" [Coord Object -> ({subIntX}, {subIntY})]";
                                }

                                var listItems = BitConverter.ToInt64(subBuf, 0x10);
                                var listSize = BitConverter.ToInt32(subBuf, 0x18);
                                if (listSize is > 0 and < 500 && listItems > 0x10000000000L && listItems < 0x7FFFFFFFFFFFL)
                                {
                                    detail += $" [List<T> -> Count={listSize}, Items=0x{listItems:X}]";
                                }

                                var arrayLen = BitConverter.ToInt32(subBuf, 0x18);
                                if (arrayLen is > 0 and < 1000)
                                {
                                    detail += $" [Array -> Length={arrayLen}]";
                                    // Read elements of array
                                    var elemDump = new List<string>();
                                    for (int e = 0; e < Math.Min(arrayLen, 10); e++)
                                    {
                                        int elemOff = 0x20 + e * 8;
                                        if (elemOff + 8 <= subRead)
                                        {
                                            var elemPtr = BitConverter.ToInt64(subBuf, elemOff);
                                            elemDump.Add($"0x{elemPtr:X}");
                                        }
                                        else
                                        {
                                            // Read direct from process
                                            if (TryReadPointer(handle, ptrVal + 0x20 + e * 8, out var ep))
                                            {
                                                // check if ep is coord
                                                if (TryReadInt32(handle, ep + 0x10, out var ex) && TryReadInt32(handle, ep + 0x14, out var ey) && ex >= 0 && ex <= 255 && ey >= 0 && ey <= 255)
                                                {
                                                    elemDump.Add($"({ex},{ey})");
                                                }
                                                else
                                                {
                                                    elemDump.Add($"0x{ep:X}");
                                                }
                                            }
                                        }
                                    }
                                    if (elemDump.Count > 0)
                                    {
                                        detail += $" Elements: [{string.Join(", ", elemDump)}]";
                                    }
                                }
                            }
                        }

                        if (off == BodyCurrentCoordOffset) detail += " <== [BodyCurrentCoord (Tọa độ hiện tại)]";
                        if (off == BodyTargetCoordOffset) detail += " <== [BodyTargetCoord (Tọa độ đích đến)]";
                        if (off == LastServerCoordOffset) detail += " <== [LastServerCoord (Tọa độ server)]";
                        if (off == 0x330) detail += $" <== [3D Pos: X={fVal1:F2}, Y={fVal2:F2}]";

                        if (intVal1 is 0 or 1 or -1 && intVal2 is 0 or 1 or -1 && !isPointer)
                        {
                            detail += $" [Ints: ({intVal1}, {intVal2})]";
                        }

                        if (!string.IsNullOrEmpty(detail))
                        {
                            sb.AppendLine($"  +0x{off:X3}: Ptr=0x{ptrVal:X} | i32=({intVal1}, {intVal2}) | f=({fVal1:F2}, {fVal2:F2}){detail}");
                        }
                    }
                }
            }

            if (worldPtr != 0)
            {
                var worldBuf = new byte[0x400];
                if (ReadProcessMemory(handle, (IntPtr)worldPtr, worldBuf, worldBuf.Length, out var wRead))
                {
                    sb.AppendLine($"\n--- DUMP CÁC TRƯỜNG CỦA _World (0x{worldPtr:X}, Read: {wRead} bytes) ---");
                    for (int off = 0; off < wRead - 8; off += 8)
                    {
                        var ptrVal = BitConverter.ToInt64(worldBuf, off);
                        var isPointer = ptrVal > 0x10000000000L && ptrVal < 0x7FFFFFFFFFFFL;
                        string detail = "";

                        if (off == WorldSceneIndexOffset)
                        {
                            var sIdx = BitConverter.ToInt32(worldBuf, off);
                            detail += $" <== [SceneIndex={sIdx} ({MapCatalog.GetName(sIdx)})]";
                        }

                        if (isPointer)
                        {
                            var subBuf = new byte[64];
                            if (ReadProcessMemory(handle, (IntPtr)ptrVal, subBuf, subBuf.Length, out var subRead) && subRead >= 32)
                            {
                                var listItems = BitConverter.ToInt64(subBuf, 0x10);
                                var listSize = BitConverter.ToInt32(subBuf, 0x18);
                                if (listSize is > 0 and < 500 && listItems > 0x10000000000L && listItems < 0x7FFFFFFFFFFFL)
                                {
                                    detail += $" [List<T> -> Count={listSize}, Items=0x{listItems:X}]";
                                }
                            }
                        }

                        if (!string.IsNullOrEmpty(detail))
                        {
                            sb.AppendLine($"  +0x{off:X3}: Ptr=0x{ptrVal:X}{detail}");
                        }
                    }
                }
            }

            return sb.ToString();
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    public static List<RamDeltaLog> CompareWarpStates(WarpMemoryState? before, WarpMemoryState? after)
    {
        var deltas = new List<RamDeltaLog>();
        if (before is null || after is null) return deltas;

        // Map change
        if (before.SceneIndex != after.SceneIndex)
        {
            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Bản đồ",
                PropertyName = "SceneIndex (Map ID)",
                OldValue = before.SceneIndex is not null ? $"{before.SceneIndex} ({before.MapName})" : "Chưa rõ",
                NewValue = after.SceneIndex is not null ? $"{after.SceneIndex} ({after.MapName})" : "Chưa rõ",
                Note = "★ [WARP DETECTED] Nhân vật vừa chuyển đổi sang bản đồ khác!"
            });
        }

        // Live Tile Coord change
        if (before.CurrentX != after.CurrentX || before.CurrentY != after.CurrentY)
        {
            var oldCoord = before.CurrentCoordDisplay;
            var newCoord = after.CurrentCoordDisplay;
            var isJump = false;
            if (before.CurrentX.HasValue && before.CurrentY.HasValue && after.CurrentX.HasValue && after.CurrentY.HasValue)
            {
                var dx = Math.Abs(before.CurrentX.Value - after.CurrentX.Value);
                var dy = Math.Abs(before.CurrentY.Value - after.CurrentY.Value);
                if (dx > 10 || dy > 10)
                {
                    isJump = true;
                }
            }

            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Tọa độ",
                PropertyName = "Live Tile Coord",
                OldValue = oldCoord,
                NewValue = newCoord,
                Note = isJump ? "▲ [TỌA ĐỘ NHẢY BƯỚC LỚN] Nghi vấn dịch chuyển (Gate/Move)" : "Di chuyển bước thông thường"
            });
        }

        // Target Coord change
        if (before.TargetX != after.TargetX || before.TargetY != after.TargetY)
        {
            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Mục tiêu",
                PropertyName = "Target Tile Coord",
                OldValue = before.TargetCoordDisplay,
                NewValue = after.TargetCoordDisplay,
                Note = "Cập nhật điểm đích di chuyển khi click"
            });
        }

        // Last Server Coord change
        if (before.LastServerX != after.LastServerX || before.LastServerY != after.LastServerY)
        {
            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Server Sync",
                PropertyName = "Last Server Coord",
                OldValue = before.LastServerCoordDisplay,
                NewValue = after.LastServerCoordDisplay,
                Note = "Server cập nhật tọa độ đồng bộ"
            });
        }

        // MapServerMove IsActive change
        if (before.IsActive != after.IsActive)
        {
            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Warp MSM",
                PropertyName = "MapServerMove.IsActive",
                OldValue = before.IsActive.ToString(),
                NewValue = after.IsActive.ToString(),
                Note = after.IsActive == 1 ? "★ [MSM BẮT ĐẦU] Client kích hoạt đổi GameServer" : "MSM kết thúc / reset"
            });
        }

        // AuthKeys change
        if (before.AuthKeysPtr != after.AuthKeysPtr)
        {
            deltas.Add(new RamDeltaLog
            {
                Timestamp = after.SampledAtUtc.ToLocalTime(),
                Category = "Warp MSM",
                PropertyName = "AuthKeys Pointer",
                OldValue = $"0x{before.AuthKeysPtr:X}",
                NewValue = $"0x{after.AuthKeysPtr:X}",
                Note = "Cập nhật con trỏ token xác thực liên server"
            });
        }

        return deltas;
    }

    private static bool TryApplyCoordMajority(
        IntPtr handle,
        LiveClientInfo client,
        CancellationToken cancellationToken)
    {
        var scores = new Dictionary<(int X, int Y), int>();
        ScanUtf16CoordNeedle(handle, scores, cancellationToken);
        if (scores.Count == 0)
        {
            return false;
        }

        var best = scores.OrderByDescending(kv => kv.Value).First().Key;
        client.X = best.X;
        client.Y = best.Y;
        if (client.Source is "window-title" or null or "")
        {
            client.Source = "memory:Coord";
        }

        return true;
    }

    private static void ScanUtf16CoordNeedle(
        IntPtr handle,
        Dictionary<(int X, int Y), int> scores,
        CancellationToken cancellationToken)
    {
        long address = 0;
        const long maxAddress = 0x7FFFFFFFFFFF;
        var mbiSize = (uint)Marshal.SizeOf<MemoryBasicInformation>();

        while (address < maxAddress)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (VirtualQueryEx(handle, (IntPtr)address, out var mbi, mbiSize) == 0)
            {
                break;
            }

            long regionSize = mbi.RegionSize.ToInt64();
            if (regionSize <= 0)
            {
                break;
            }

            var readable = mbi.State == MemCommit &&
                           mbi.Type == MemPrivate &&
                           (mbi.Protect & PageNoAccess) == 0 &&
                           (mbi.Protect & PageGuard) == 0 &&
                           regionSize <= 32L * 1024 * 1024;

            if (readable)
            {
                long remaining = regionSize;
                long offset = 0;
                while (remaining > 0)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    var chunkSize = (int)Math.Min(remaining, 2 * 1024 * 1024);
                    var buffer = new byte[chunkSize];
                    if (ReadProcessMemory(handle, (IntPtr)(mbi.BaseAddress.ToInt64() + offset), buffer, chunkSize, out var read)
                        && read > 0)
                    {
                        var idx = IndexOfBytes(buffer, read, CoordUtf16Needle);
                        while (idx >= 0)
                        {
                            var take = Math.Min(48, read - idx);
                            if ((take % 2) == 1)
                            {
                                take--;
                            }

                            if (take >= CoordUtf16Needle.Length)
                            {
                                var text = Encoding.Unicode.GetString(buffer, idx, take);
                                var match = CoordRegex.Match(text);
                                if (match.Success &&
                                    int.TryParse(match.Groups["x"].Value, out var x) &&
                                    int.TryParse(match.Groups["y"].Value, out var y) &&
                                    x <= 255 && y <= 255)
                                {
                                    var key = (x, y);
                                    scores[key] = scores.TryGetValue(key, out var score) ? score + 1 : 1;
                                }
                            }

                            idx = IndexOfBytes(buffer, read, CoordUtf16Needle, idx + CoordUtf16Needle.Length);
                        }
                    }

                    offset += chunkSize;
                    remaining -= chunkSize;
                }
            }

            long next = mbi.BaseAddress.ToInt64() + regionSize;
            if (next <= address)
            {
                break;
            }

            address = next;
        }
    }

    private static int IndexOfBytes(byte[] haystack, int length, byte[] needle, int start = 0)
    {
        for (var i = start; i <= length - needle.Length; i++)
        {
            var ok = true;
            for (var j = 0; j < needle.Length; j++)
            {
                if (haystack[i + j] != needle[j])
                {
                    ok = false;
                    break;
                }
            }

            if (ok)
            {
                return i;
            }
        }

        return -1;
    }

    private static void CollectLocationVotes(
        string chunk,
        Dictionary<int, int> mapScores,
        Dictionary<(int X, int Y), int>? coordScores)
    {
        // Strong signal: currently loaded Unity world path.
        foreach (Match match in WorldPathRegex.Matches(chunk))
        {
            if (int.TryParse(match.Groups["id"].Value, out var id))
            {
                mapScores[id] = mapScores.TryGetValue(id, out var score) ? score + 8 : 8;
            }
        }

        foreach (Match match in LoadWorldRegex.Matches(chunk))
        {
            if (int.TryParse(match.Groups["id"].Value, out var id))
            {
                mapScores[id] = mapScores.TryGetValue(id, out var score) ? score + 5 : 5;
            }
        }

        foreach (Match match in WorldBundleRegex.Matches(chunk))
        {
            if (int.TryParse(match.Groups["id"].Value, out var id) && id > 0)
            {
                mapScores[id] = mapScores.TryGetValue(id, out var score) ? score + 1 : 1;
            }
        }

        if (coordScores is null)
        {
            return;
        }

        foreach (Match match in CoordRegex.Matches(chunk))
        {
            if (!int.TryParse(match.Groups["x"].Value, out var x) ||
                !int.TryParse(match.Groups["y"].Value, out var y))
            {
                continue;
            }

            // MU tile coordinates are typically within 0..255.
            if (x > 255 || y > 255)
            {
                continue;
            }

            var key = (x, y);
            coordScores[key] = coordScores.TryGetValue(key, out var score) ? score + 1 : 1;
        }
    }

    public static string? FindAccountUsername(
        int processId,
        string? expectedCharacter = null,
        CancellationToken cancellationToken = default)
    {
        var handle = OpenProcess(ProcessQueryInformation | ProcessVmRead, false, processId);
        if (handle == IntPtr.Zero)
        {
            return null;
        }

        try
        {
            var votes = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            ScanTextChunks(handle, unicode: false, chunk =>
            {
                cancellationToken.ThrowIfCancellationRequested();
                CollectUsernameVotes(chunk, expectedCharacter, votes);
            }, cancellationToken);

            // Unity often keeps managed strings as UTF-16.
            if (votes.Count == 0)
            {
                ScanTextChunks(handle, unicode: true, chunk =>
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    CollectUsernameVotes(chunk, expectedCharacter, votes);
                }, cancellationToken);
            }

            return votes
                .OrderByDescending(kv => kv.Value)
                .ThenByDescending(kv => kv.Key.Length)
                .Select(kv => kv.Key)
                .FirstOrDefault();
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    private static void CollectUsernameVotes(
        string chunk,
        string? expectedCharacter,
        Dictionary<string, int> votes)
    {
        foreach (Match match in LastUserJsonRegex.Matches(chunk))
        {
            var character = match.Groups["char"].Value.Trim();
            var user = match.Groups["user"].Value.Trim();
            if (string.IsNullOrWhiteSpace(user))
            {
                continue;
            }

            var score = 5;
            if (!string.IsNullOrWhiteSpace(expectedCharacter) &&
                string.Equals(character, expectedCharacter, StringComparison.OrdinalIgnoreCase))
            {
                score += 20;
            }

            votes[user] = votes.TryGetValue(user, out var current) ? current + score : score;
        }

        foreach (Match match in LastUserLooseRegex.Matches(chunk))
        {
            var character = match.Groups["char"].Value.Trim();
            var user = match.Groups["user"].Value.Trim();
            if (string.IsNullOrWhiteSpace(user) || user.Equals("Mode", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var score = 1;
            if (!string.IsNullOrWhiteSpace(expectedCharacter) &&
                string.Equals(character, expectedCharacter, StringComparison.OrdinalIgnoreCase))
            {
                score += 8;
            }

            votes[user] = votes.TryGetValue(user, out var current) ? current + score : score;
        }
    }

    private static void ScanTextChunks(
        IntPtr handle,
        bool unicode,
        Action<string> onChunk,
        CancellationToken cancellationToken,
        bool privateOnly = false)
    {
        long address = 0;
        const long maxAddress = 0x7FFFFFFFFFFF;
        var mbiSize = (uint)Marshal.SizeOf<MemoryBasicInformation>();
        var builder = new StringBuilder(4096);

        while (address < maxAddress)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (VirtualQueryEx(handle, (IntPtr)address, out var mbi, mbiSize) == 0)
            {
                break;
            }

            long regionSize = mbi.RegionSize.ToInt64();
            if (regionSize <= 0)
            {
                break;
            }

            var readable = mbi.State == MemCommit &&
                           (mbi.Protect & PageNoAccess) == 0 &&
                           (mbi.Protect & PageGuard) == 0 &&
                           regionSize <= 16L * 1024 * 1024 &&
                           (!privateOnly || mbi.Type == MemPrivate);

            if (readable)
            {
                long remaining = regionSize;
                long offset = 0;
                while (remaining > 0)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    var chunkSize = (int)Math.Min(remaining, 1024 * 1024);
                    var buffer = new byte[chunkSize];
                    if (ReadProcessMemory(handle, (IntPtr)(mbi.BaseAddress.ToInt64() + offset), buffer, chunkSize, out var read)
                        && read > 0)
                    {
                        if (unicode)
                        {
                            EmitUtf16Chunks(buffer, read, builder, onChunk);
                        }
                        else
                        {
                            EmitAsciiChunks(buffer, read, builder, onChunk);
                        }
                    }

                    offset += chunkSize;
                    remaining -= chunkSize;
                }
            }

            long next = mbi.BaseAddress.ToInt64() + regionSize;
            if (next <= address)
            {
                break;
            }

            address = next;
        }
    }

    private static void EmitAsciiChunks(
        byte[] buffer,
        int read,
        StringBuilder builder,
        Action<string> onChunk)
    {
        builder.Clear();
        for (var i = 0; i < read; i++)
        {
            var value = buffer[i];
            if (value >= 32 && value <= 126)
            {
                builder.Append((char)value);
                continue;
            }

            // Keep short chunks too: "Coord(195, 102)" is only ~16 chars.
            if (builder.Length >= 8)
            {
                onChunk(builder.ToString());
            }

            builder.Clear();
        }

        if (builder.Length >= 8)
        {
            onChunk(builder.ToString());
        }
    }

    private static void EmitUtf16Chunks(
        byte[] buffer,
        int read,
        StringBuilder builder,
        Action<string> onChunk)
    {
        builder.Clear();
        var limit = read - (read % 2);
        for (var i = 0; i < limit; i += 2)
        {
            var ch = (char)(buffer[i] | (buffer[i + 1] << 8));
            if (ch >= 32 && ch <= 126)
            {
                builder.Append(ch);
                continue;
            }

            if (builder.Length >= 8)
            {
                onChunk(builder.ToString());
            }

            builder.Clear();
        }

        if (builder.Length >= 8)
        {
            onChunk(builder.ToString());
        }
    }
}
