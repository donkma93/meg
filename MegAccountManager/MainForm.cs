using System.Diagnostics;
using System.Reflection;
using System.Text;
using MegAccountManager.Models;
using MegAccountManager.Services;

namespace MegAccountManager;

public partial class MainForm : Form
{
    private readonly AccountStore _store = new();
    private readonly object _liveClientsGate = new();
    private List<Account> _accounts = new();
    private List<LiveClientInfo> _liveClients = new();
    private bool _suppressSelectionEvents;
    private bool _isScanning;
    private bool _isTrackingRealtime;
    private CancellationTokenSource? _realtimeCts;
    private Task? _realtimeTask;
    private int _realtimeRound;
    private DateTime _lastMapRefreshUtc = DateTime.MinValue;
    private DateTime _lastStatusUiUtc = DateTime.MinValue;
    private string _lastRealtimeStatus = string.Empty;
    private int? _watchedMapId;
    private int? _selectedRamPid;
    private WarpMemoryState? _lastWarpState;
    private System.Windows.Forms.Timer? _ramTrackTimer;

    public MainForm()
    {
        InitializeComponent();
        EnableDoubleBuffering(listLiveClients);
        EnableDoubleBuffering(listMaps);
        EnableDoubleBuffering(listRamFields);
        EnableDoubleBuffering(listRamDeltas);
        listLiveClients.DoubleClick += listLiveClients_DoubleClick;
        DoubleBuffered = true;
        LoadAccounts();
        RefreshMapList();
        UpdateMapWatchLabels();
        UpdateStatus();
        FormClosing += MainForm_FormClosing;
    }

    private static void EnableDoubleBuffering(Control control)
    {
        typeof(Control).InvokeMember(
            "DoubleBuffered",
            BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.SetProperty,
            binder: null,
            target: control,
            args: [true]);
    }

    private void MainForm_FormClosing(object? sender, FormClosingEventArgs e)
    {
        StopRealtimeTracking();
        StopRamAutoTrack();
        _inputCoordTimer?.Stop();
        _inputCoordTimer?.Dispose();
    }

    private void MainForm_Shown(object? sender, EventArgs e)
    {
        try
        {
            BringToFront();
            Activate();
            WindowState = FormWindowState.Normal;

            // Apply splitter sizes after the form has a real size.
            try
            {
                if (splitMain.Width > 300)
                {
                    splitMain.SplitterDistance = Math.Clamp(340, splitMain.Panel1MinSize,
                        Math.Max(splitMain.Panel1MinSize, splitMain.Width - splitMain.Panel2MinSize - splitMain.SplitterWidth));
                }

                if (splitRight.Height > 300)
                {
                    splitRight.SplitterDistance = Math.Clamp(260, splitRight.Panel1MinSize,
                        Math.Max(splitRight.Panel1MinSize, splitRight.Height - splitRight.Panel2MinSize - splitRight.SplitterWidth));
                }
            }
            catch
            {
                // Keep default layout if clamp fails.
            }

            // 1) Show live window titles immediately (no RAM scan yet).
            RefreshLiveFromWindowTitles();

            // 2) If local store is empty, auto-import MEGAMU AccountList from registry.
            if (_accounts.Count == 0)
            {
                ImportRegistryAccounts(showMessage: false);
            }

            // 3) Enrich live rows with account names from registry mapping (fast).
            try
            {
                var liveClients = SnapshotLiveClients();
                var snapshot = RegistryAccountReader.Read();
                RegistryAccountReader.EnrichLiveClients(liveClients, snapshot);
                RefreshLiveClientList();
                btnImportLive.Enabled = liveClients.Count > 0;

                if (_accounts.Count > 0)
                {
                    lblStatus.Text =
                        $"Đã nạp {_accounts.Count} tài khoản, {liveClients.Count} process đang chạy.";
                }
            }
            catch (Exception ex)
            {
                lblStatus.Text = $"Registry lỗi: {ex.Message}";
            }

            UpdateStatus();
            RefreshRamProcessList();
            RefreshInputProcesses();
            InitInputSimulatorTab();

            // Keep scanning coordinates while characters move.
            if (GetLiveClientCount() > 0)
            {
                BeginInvoke(new Action(() =>
                {
                    if (!_isTrackingRealtime && !_isScanning)
                    {
                        StartRealtimeTracking();
                    }
                }));
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Lỗi khi hiển thị form:\n{ex}",
                "Lỗi",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void RefreshLiveFromWindowTitles()
    {
        var clients = ProcessMemory.GetLiveClientsFromWindowTitles().ToList();
        lock (_liveClientsGate)
        {
            _liveClients = clients;
        }

        RefreshLiveClientList();
        btnImportLive.Enabled = clients.Count > 0;
    }

    private void ImportRegistryAccounts(bool showMessage)
    {
        try
        {
            var snapshot = RegistryAccountReader.Read();
            if (snapshot.Accounts.Count == 0)
            {
                if (showMessage)
                {
                    MessageBox.Show(
                        "Không tìm thấy AccountList trong registry MEGAMU.",
                        "Registry trống",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information);
                }

                return;
            }

            var createdAccounts = 0;
            var addedCharacters = 0;
            var alreadyPresent = 0;

            foreach (var incoming in snapshot.Accounts)
            {
                var account = _accounts.FirstOrDefault(a =>
                    string.Equals(a.Username, incoming.Username, StringComparison.OrdinalIgnoreCase));
                if (account is null)
                {
                    account = new Account { Username = incoming.Username };
                    _accounts.Add(account);
                    createdAccounts++;
                }

                foreach (var character in incoming.Characters)
                {
                    if (account.Characters.Any(c =>
                            string.Equals(c, character, StringComparison.OrdinalIgnoreCase)))
                    {
                        alreadyPresent++;
                        continue;
                    }

                    account.Characters.Add(character);
                    addedCharacters++;
                }
            }

            Persist();
            RefreshAccountList();

            if (showMessage)
            {
                var lastInfo = string.IsNullOrWhiteSpace(snapshot.LastUsername)
                    ? ""
                    : $"\nLast login: {snapshot.LastUsername} / {snapshot.LastCharacter} ({snapshot.LastServerLabel})";

                MessageBox.Show(
                    $"Đã đọc {snapshot.Accounts.Count} tài khoản từ registry.\n" +
                    $"Tạo mới tài khoản: {createdAccounts}\n" +
                    $"Thêm nhân vật: {addedCharacters}\n" +
                    $"Nhân vật đã có sẵn: {alreadyPresent}{lastInfo}",
                    "Nhập từ AccountList",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            }
            else
            {
                lblStatus.Text =
                    $"Đã tự nạp {snapshot.Accounts.Count} tài khoản từ registry MEGAMU.";
            }
        }
        catch (Exception ex)
        {
            if (showMessage)
            {
                MessageBox.Show(
                    $"Không đọc được registry:\n{ex.Message}",
                    "Lỗi registry",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
        }
    }

    private async Task ScanProcessesInternalAsync(bool showCompletionMessage)
    {
        if (_isScanning || _isTrackingRealtime)
        {
            return;
        }

        _isScanning = true;
        btnScanProcesses.Enabled = false;
        btnTrackRealtime.Enabled = false;
        btnImportLive.Enabled = false;
        lblStatus.Text = "Đang quét process MEGAMU trong RAM...";

        try
        {
            var clients = await Task.Run(() => ProcessMemory.ScanLiveClients());
            lock (_liveClientsGate)
            {
                _liveClients = clients.ToList();
            }

            RefreshLiveClientList();
            RefreshMapList();

            var withAccount = clients.Count(c => !string.IsNullOrWhiteSpace(c.AccountUsername));
            var withMap = clients.Count(c => c.MapId is not null);
            var withCoord = clients.Count(c => c.X is not null && c.Y is not null);
            lblStatus.Text =
                $"Quét xong: {clients.Count} process | TK: {withAccount} | Map: {withMap} | Tọa độ: {withCoord}";
            btnImportLive.Enabled = clients.Count > 0;

            if (showCompletionMessage)
            {
                MessageBox.Show(
                    $"Quét xong {clients.Count} process.\n" +
                    $"Có tài khoản: {withAccount}\n" +
                    $"Có map: {withMap}\n" +
                    $"Có tọa độ: {withCoord}",
                    "Quét process",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Không quét được process:\n{ex.Message}",
                "Lỗi quét process",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            UpdateStatus();
        }
        finally
        {
            _isScanning = false;
            btnScanProcesses.Enabled = true;
            btnTrackRealtime.Enabled = true;
        }
    }

    private void btnTrackRealtime_Click(object? sender, EventArgs e)
    {
        if (_isTrackingRealtime)
        {
            StopRealtimeTracking();
            lblStatus.Text = "Đã dừng theo dõi realtime.";
            return;
        }

        StartRealtimeTracking(showEmptyMessage: true);
    }

    private void StartRealtimeTracking(bool showEmptyMessage = false)
    {
        if (_isTrackingRealtime || _isScanning)
        {
            return;
        }

        if (GetLiveClientCount() == 0)
        {
            RefreshLiveFromWindowTitles();
        }

        if (GetLiveClientCount() == 0)
        {
            if (showEmptyMessage)
            {
                MessageBox.Show(
                    "Không thấy process MEGAMU đang chạy.",
                    "Theo dõi realtime",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            }

            return;
        }

        _isTrackingRealtime = true;
        _realtimeRound = 0;
        _lastMapRefreshUtc = DateTime.MinValue;
        _lastRealtimeStatus = string.Empty;
        _realtimeCts = new CancellationTokenSource();
        var token = _realtimeCts.Token;

        btnTrackRealtime.Text = "Dừng realtime";
        btnScanProcesses.Enabled = false;
        lblStatus.Text = $"Realtime nền: đang theo dõi {GetLiveClientCount()} nhân vật...";

        // Fire-and-forget background worker so the UI thread stays idle/responsive.
        _realtimeTask = Task.Factory.StartNew(
            () => RunRealtimeLoop(token),
            token,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);

        _ = _realtimeTask.ContinueWith(
            task =>
            {
                if (IsDisposed || !IsHandleCreated)
                {
                    return;
                }

                BeginInvoke(new Action(() =>
                {
                    if (task.IsFaulted)
                    {
                        var message = task.Exception?.GetBaseException().Message ?? "lỗi không rõ";
                        lblStatus.Text = $"Realtime lỗi: {message}";
                        MessageBox.Show(
                            $"Lỗi theo dõi realtime:\n{message}",
                            "Theo dõi realtime",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error);
                    }

                    if (_isTrackingRealtime)
                    {
                        StopRealtimeTracking();
                    }
                }));
            },
            CancellationToken.None,
            TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);
    }

    private async Task StartRealtimeTrackingAsync(bool showEmptyMessage = false)
    {
        // Kept for existing auto-start call sites; starts passive background worker.
        StartRealtimeTracking(showEmptyMessage);
        await Task.CompletedTask;
    }

    private void StopRealtimeTracking()
    {
        var cts = _realtimeCts;
        _realtimeCts = null;
        if (cts is not null)
        {
            try
            {
                cts.Cancel();
            }
            catch
            {
                // Ignore dispose races.
            }

            cts.Dispose();
        }

        _isTrackingRealtime = false;
        _realtimeTask = null;

        if (!IsDisposed && IsHandleCreated)
        {
            btnTrackRealtime.Text = "Theo dõi realtime";
            btnScanProcesses.Enabled = !_isScanning;
            btnImportLive.Enabled = GetLiveClientCount() > 0;
        }
    }

    private void RunRealtimeLoop(CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var membershipChanged = MergeWindowTitlesIntoLiveClients();
                var snapshot = SnapshotLiveClients();
                if (snapshot.Count == 0)
                {
                    PostToUi(() =>
                    {
                        RefreshLiveClientList();
                        lblStatus.Text = "Realtime: không còn process MEGAMU.";
                    });
                    break;
                }

                var before = snapshot.ToDictionary(
                    c => c.ProcessId,
                    c => (c.X, c.Y, c.MapId, c.Source, c.CharacterName, c.Server, c.LevelInfo, c.AccountUsername));

                var refreshMap = DateTime.UtcNow - _lastMapRefreshUtc > TimeSpan.FromSeconds(30);
                var sw = Stopwatch.StartNew();

                Parallel.ForEach(
                    snapshot,
                    new ParallelOptions
                    {
                        CancellationToken = cancellationToken,
                        MaxDegreeOfParallelism = Math.Min(snapshot.Count, 2)
                    },
                    client =>
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        ProcessMemory.RefreshClientCoords(client, cancellationToken);
                        if (refreshMap)
                        {
                            ProcessMemory.RefreshClientMap(client, cancellationToken);
                        }
                    });

                if (refreshMap)
                {
                    _lastMapRefreshUtc = DateTime.UtcNow;
                }

                _realtimeRound++;
                var withCoord = snapshot.Count(c => c.X is not null && c.Y is not null);
                var withIl2Cpp = snapshot.Count(c =>
                    c.Source.StartsWith("il2cpp:", StringComparison.OrdinalIgnoreCase));
                var status =
                    $"Realtime nền #{_realtimeRound}: {withCoord}/{snapshot.Count} tọa độ (IL2CPP {withIl2Cpp}) | {sw.ElapsedMilliseconds} ms";

                var rowChanged = false;
                var mapChanged = membershipChanged;
                foreach (var client in snapshot)
                {
                    var prev = before[client.ProcessId];
                    if (prev.X != client.X ||
                        prev.Y != client.Y ||
                        prev.Source != client.Source ||
                        prev.CharacterName != client.CharacterName ||
                        prev.Server != client.Server ||
                        prev.LevelInfo != client.LevelInfo ||
                        prev.AccountUsername != client.AccountUsername)
                    {
                        rowChanged = true;
                    }

                    if (prev.MapId != client.MapId)
                    {
                        mapChanged = true;
                        rowChanged = true;
                    }
                }

                var statusChanged = !string.Equals(status, _lastRealtimeStatus, StringComparison.Ordinal);
                var shouldPushStatus = statusChanged &&
                                       (membershipChanged ||
                                        rowChanged ||
                                        DateTime.UtcNow - _lastStatusUiUtc > TimeSpan.FromSeconds(2));

                if (membershipChanged || rowChanged || mapChanged || shouldPushStatus)
                {
                    if (shouldPushStatus)
                    {
                        _lastRealtimeStatus = status;
                        _lastStatusUiUtc = DateTime.UtcNow;
                    }

                    var rebuildList = membershipChanged;
                    var updateRows = rowChanged && !membershipChanged;
                    var refreshMaps = mapChanged;
                    var pushStatus = shouldPushStatus;
                    PostToUi(() =>
                    {
                        if (rebuildList)
                        {
                            RefreshLiveClientList(updateMaps: refreshMaps);
                        }
                        else if (updateRows)
                        {
                            UpdateLiveClientListRows(snapshot);
                        }

                        if (refreshMaps)
                        {
                            UpdateMapWatchLabels();
                            RefreshMapLiveColumn();
                        }

                        if (pushStatus)
                        {
                            lblStatus.Text = status;
                        }
                    });
                }

                // Passive idle cadence keeps UI/input responsive while coords stay live.
                if (cancellationToken.WaitHandle.WaitOne(1000))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Stopped by user or form close.
        }
    }

    private void PostToUi(Action action)
    {
        if (IsDisposed || !IsHandleCreated)
        {
            return;
        }

        try
        {
            BeginInvoke(action);
        }
        catch (ObjectDisposedException)
        {
            // Form closed while worker was posting.
        }
        catch (InvalidOperationException)
        {
            // Handle not ready / already destroyed.
        }
    }

    private int GetLiveClientCount()
    {
        lock (_liveClientsGate)
        {
            return _liveClients.Count;
        }
    }

    private List<LiveClientInfo> SnapshotLiveClients()
    {
        lock (_liveClientsGate)
        {
            return _liveClients.ToList();
        }
    }

    private bool MergeWindowTitlesIntoLiveClients()
    {
        var fresh = ProcessMemory.GetLiveClientsFromWindowTitles();
        lock (_liveClientsGate)
        {
            if (fresh.Count == 0)
            {
                var cleared = _liveClients.Count > 0;
                _liveClients = new List<LiveClientInfo>();
                return cleared;
            }

            var byPid = _liveClients.ToDictionary(c => c.ProcessId);
            var merged = new List<LiveClientInfo>(fresh.Count);
            var membershipChanged = fresh.Count != _liveClients.Count;

            foreach (var next in fresh)
            {
                if (byPid.TryGetValue(next.ProcessId, out var existing))
                {
                    // Keep the same object so background scans update the UI row.
                    existing.WindowTitle = next.WindowTitle;
                    existing.CharacterName = next.CharacterName;
                    existing.Server = next.Server;
                    existing.LevelInfo = next.LevelInfo;
                    merged.Add(existing);
                }
                else
                {
                    membershipChanged = true;
                    merged.Add(next);
                }
            }

            if (!membershipChanged)
            {
                for (var i = 0; i < merged.Count; i++)
                {
                    if (merged[i].ProcessId != _liveClients[i].ProcessId)
                    {
                        membershipChanged = true;
                        break;
                    }
                }
            }

            _liveClients = merged;
            return membershipChanged;
        }
    }

    private Account? SelectedAccount
    {
        get
        {
            if (listAccounts.SelectedIndex < 0 || listAccounts.SelectedIndex >= _accounts.Count)
            {
                return null;
            }

            return _accounts[listAccounts.SelectedIndex];
        }
    }

    private void LoadAccounts(string? selectUsername = null)
    {
        try
        {
            _accounts = _store.Load()
                .OrderBy(a => a.Username, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Lỗi đọc dữ liệu", MessageBoxButtons.OK, MessageBoxIcon.Error);
            _accounts = new List<Account>();
        }

        RefreshAccountList(selectUsername);
    }

    private void RefreshAccountList(string? selectUsername = null)
    {
        _suppressSelectionEvents = true;
        listAccounts.BeginUpdate();
        listAccounts.Items.Clear();

        foreach (var account in _accounts)
        {
            listAccounts.Items.Add($"{account.Username}  ({account.Characters.Count})");
        }

        listAccounts.EndUpdate();
        _suppressSelectionEvents = false;

        if (_accounts.Count == 0)
        {
            listAccounts.Items.Add("(Chưa có tài khoản — bấm \"Đọc AccountList\")");
            listAccounts.SelectedIndex = -1;
            RefreshCharacterList();
            UpdateButtonStates();
            UpdateStatus();
            return;
        }

        var index = 0;
        if (!string.IsNullOrWhiteSpace(selectUsername))
        {
            index = _accounts.FindIndex(a =>
                string.Equals(a.Username, selectUsername, StringComparison.OrdinalIgnoreCase));
            if (index < 0)
            {
                index = 0;
            }
        }

        listAccounts.SelectedIndex = index;
        RefreshCharacterList();
        UpdateButtonStates();
        UpdateStatus();
    }

    private void RefreshCharacterList()
    {
        listCharacters.BeginUpdate();
        listCharacters.Items.Clear();

        var account = SelectedAccount;
        if (account is not null)
        {
            foreach (var character in account.Characters
                         .OrderBy(c => c, StringComparer.OrdinalIgnoreCase))
            {
                listCharacters.Items.Add(character);
            }
        }

        listCharacters.EndUpdate();
        UpdateButtonStates();
    }

    private void Persist()
    {
        try
        {
            _store.Save(_accounts);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Không lưu được dữ liệu:\n{ex.Message}",
                "Lỗi lưu dữ liệu",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void UpdateButtonStates()
    {
        var hasAccount = SelectedAccount is not null;
        var hasCharacter = listCharacters.SelectedIndex >= 0;

        btnEditAccount.Enabled = hasAccount;
        btnDeleteAccount.Enabled = hasAccount;
        btnAddCharacter.Enabled = hasAccount;
        btnEditCharacter.Enabled = hasAccount && hasCharacter;
        btnDeleteCharacter.Enabled = hasAccount && hasCharacter;
    }

    private void UpdateStatus()
    {
        var accountCount = _accounts.Count;
        var characterCount = _accounts.Sum(a => a.Characters.Count);
        var liveClients = SnapshotLiveClients();
        var liveCount = liveClients.Count;
        var liveWithAccount = liveClients.Count(c => !string.IsNullOrWhiteSpace(c.AccountUsername));
        lblStatus.Text =
            $"Tài khoản: {accountCount}  |  Nhân vật: {characterCount}  |  Process: {liveCount} (đã map {liveWithAccount})  |  {_store.FilePath}";
    }

    private static string? PromptText(string title, string label, string initialValue = "")
    {
        using var dialog = new Form
        {
            Text = title,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterParent,
            MinimizeBox = false,
            MaximizeBox = false,
            ShowInTaskbar = false,
            ClientSize = new Size(420, 140)
        };

        var lbl = new Label
        {
            Text = label,
            AutoSize = true,
            Location = new Point(16, 18)
        };

        var textBox = new TextBox
        {
            Text = initialValue,
            Location = new Point(16, 46),
            Width = 388
        };

        var btnOk = new Button
        {
            Text = "OK",
            DialogResult = DialogResult.OK,
            Location = new Point(248, 92),
            Width = 75
        };

        var btnCancel = new Button
        {
            Text = "Hủy",
            DialogResult = DialogResult.Cancel,
            Location = new Point(329, 92),
            Width = 75
        };

        dialog.Controls.AddRange(new Control[] { lbl, textBox, btnOk, btnCancel });
        dialog.AcceptButton = btnOk;
        dialog.CancelButton = btnCancel;

        return dialog.ShowDialog() == DialogResult.OK
            ? textBox.Text.Trim()
            : null;
    }

    private void listAccounts_SelectedIndexChanged(object? sender, EventArgs e)
    {
        if (_suppressSelectionEvents)
        {
            return;
        }

        RefreshCharacterList();
        UpdateStatus();
    }

    private void listCharacters_SelectedIndexChanged(object? sender, EventArgs e)
    {
        UpdateButtonStates();
    }

    private void btnAddAccount_Click(object? sender, EventArgs e)
    {
        var username = PromptText("Thêm tài khoản", "Tên đăng nhập:");
        if (username is null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(username))
        {
            MessageBox.Show("Tên đăng nhập không được để trống.", "Thiếu thông tin",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (_accounts.Any(a => string.Equals(a.Username, username, StringComparison.OrdinalIgnoreCase)))
        {
            MessageBox.Show("Tài khoản này đã tồn tại.", "Trùng tài khoản",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        _accounts.Add(new Account { Username = username });
        Persist();
        RefreshAccountList(username);
    }

    private void btnEditAccount_Click(object? sender, EventArgs e)
    {
        var account = SelectedAccount;
        if (account is null)
        {
            return;
        }

        var username = PromptText("Sửa tài khoản", "Tên đăng nhập:", account.Username);
        if (username is null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(username))
        {
            MessageBox.Show("Tên đăng nhập không được để trống.", "Thiếu thông tin",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (_accounts.Any(a =>
                !ReferenceEquals(a, account) &&
                string.Equals(a.Username, username, StringComparison.OrdinalIgnoreCase)))
        {
            MessageBox.Show("Tài khoản này đã tồn tại.", "Trùng tài khoản",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        account.Username = username;
        Persist();
        RefreshAccountList(username);
    }

    private void btnDeleteAccount_Click(object? sender, EventArgs e)
    {
        var account = SelectedAccount;
        if (account is null)
        {
            return;
        }

        var confirm = MessageBox.Show(
            $"Xóa tài khoản \"{account.Username}\" và toàn bộ nhân vật của nó?",
            "Xác nhận xóa",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question);

        if (confirm != DialogResult.Yes)
        {
            return;
        }

        _accounts.Remove(account);
        Persist();
        RefreshAccountList();
    }

    private void btnAddCharacter_Click(object? sender, EventArgs e)
    {
        var account = SelectedAccount;
        if (account is null)
        {
            return;
        }

        var name = PromptText("Thêm nhân vật", $"Tên nhân vật cho \"{account.Username}\":");
        if (name is null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(name))
        {
            MessageBox.Show("Tên nhân vật không được để trống.", "Thiếu thông tin",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (account.Characters.Any(c => string.Equals(c, name, StringComparison.OrdinalIgnoreCase)))
        {
            MessageBox.Show("Nhân vật này đã có trong tài khoản.", "Trùng nhân vật",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        account.Characters.Add(name);
        Persist();
        RefreshAccountList(account.Username);
        listCharacters.SelectedItem = account.Characters
            .First(c => string.Equals(c, name, StringComparison.OrdinalIgnoreCase));
    }

    private void btnEditCharacter_Click(object? sender, EventArgs e)
    {
        var account = SelectedAccount;
        if (account is null || listCharacters.SelectedIndex < 0)
        {
            return;
        }

        var oldName = listCharacters.SelectedItem?.ToString() ?? string.Empty;
        var name = PromptText("Sửa nhân vật", "Tên nhân vật:", oldName);
        if (name is null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(name))
        {
            MessageBox.Show("Tên nhân vật không được để trống.", "Thiếu thông tin",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (account.Characters.Any(c =>
                !string.Equals(c, oldName, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(c, name, StringComparison.OrdinalIgnoreCase)))
        {
            MessageBox.Show("Nhân vật này đã có trong tài khoản.", "Trùng nhân vật",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var index = account.Characters.FindIndex(c =>
            string.Equals(c, oldName, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
        {
            return;
        }

        account.Characters[index] = name;
        Persist();
        RefreshAccountList(account.Username);
        listCharacters.SelectedItem = account.Characters
            .First(c => string.Equals(c, name, StringComparison.OrdinalIgnoreCase));
    }

    private void btnDeleteCharacter_Click(object? sender, EventArgs e)
    {
        var account = SelectedAccount;
        if (account is null || listCharacters.SelectedIndex < 0)
        {
            return;
        }

        var name = listCharacters.SelectedItem?.ToString() ?? string.Empty;
        var confirm = MessageBox.Show(
            $"Xóa nhân vật \"{name}\" khỏi tài khoản \"{account.Username}\"?",
            "Xác nhận xóa",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question);

        if (confirm != DialogResult.Yes)
        {
            return;
        }

        account.Characters.RemoveAll(c =>
            string.Equals(c, name, StringComparison.OrdinalIgnoreCase));
        Persist();
        RefreshAccountList(account.Username);
    }

    private void btnReload_Click(object? sender, EventArgs e)
    {
        var selected = SelectedAccount?.Username;
        LoadAccounts(selected);
    }

    private void btnOpenDataFolder_Click(object? sender, EventArgs e)
    {
        var folder = Path.GetDirectoryName(_store.FilePath);
        if (string.IsNullOrWhiteSpace(folder))
        {
            return;
        }

        Directory.CreateDirectory(folder);
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
        {
            FileName = folder,
            UseShellExecute = true
        });
    }

    private async void btnScanProcesses_Click(object? sender, EventArgs e)
    {
        await ScanProcessesInternalAsync(showCompletionMessage: true);
    }

    private void btnImportLive_Click(object? sender, EventArgs e)
    {
        var liveClients = SnapshotLiveClients();
        if (liveClients.Count == 0)
        {
            MessageBox.Show("Chưa có dữ liệu process. Hãy đợi app nạp hoặc bấm Quét process.", "Thiếu dữ liệu",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var result = LiveClientImporter.MergeIntoAccounts(_accounts, liveClients);
        Persist();
        RefreshAccountList();
        RefreshLiveClientList();

        MessageBox.Show(
            $"Đã xử lý {result.ClientsSeen} process.\n" +
            $"Tạo mới tài khoản: {result.AccountsCreated}\n" +
            $"Thêm nhân vật: {result.CharactersAdded}\n" +
            $"Nhân vật đã có sẵn: {result.CharactersAlreadyPresent}\n" +
            $"Process chưa đọc được tài khoản: {result.ClientsWithoutAccount}",
            "Nhập từ process",
            MessageBoxButtons.OK,
            MessageBoxIcon.Information);

        UpdateStatus();
    }

    private void btnImportRegistry_Click(object? sender, EventArgs e)
    {
        ImportRegistryAccounts(showMessage: true);
        UpdateStatus();
    }

    private void RefreshLiveClientList(bool updateMaps = true)
    {
        var clients = SnapshotLiveClients();
        var selectedPid = listLiveClients.SelectedItems.Count > 0 &&
                          listLiveClients.SelectedItems[0].Tag is LiveClientInfo selected
            ? selected.ProcessId
            : (int?)null;

        listLiveClients.BeginUpdate();
        listLiveClients.Items.Clear();

        ListViewItem? reselect = null;
        foreach (var client in clients)
        {
            var item = CreateLiveClientItem(client);
            listLiveClients.Items.Add(item);
            if (selectedPid == client.ProcessId)
            {
                reselect = item;
            }
        }

        listLiveClients.EndUpdate();

        if (reselect is not null)
        {
            reselect.Selected = true;
            reselect.Focused = true;
            reselect.EnsureVisible();
        }

        if (updateMaps)
        {
            UpdateMapWatchLabels();
            RefreshMapLiveColumn();
        }
    }

    private void txtMapSearch_TextChanged(object? sender, EventArgs e)
    {
        RefreshMapList();
    }

    private void listMaps_SelectedIndexChanged(object? sender, EventArgs e)
    {
        UpdateMapWatchLabels();
    }

    private void listMaps_DoubleClick(object? sender, EventArgs e)
    {
        btnSetWatchMap_Click(sender, e);
    }

    private void btnSetWatchMap_Click(object? sender, EventArgs e)
    {
        var selected = GetSelectedMapInfo();
        if (selected is null)
        {
            MessageBox.Show(
                "Hãy chọn một map trong danh sách.",
                "Maps",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return;
        }

        _watchedMapId = selected.Id;
        UpdateMapWatchLabels();
        RefreshMapLiveColumn();
        lblStatus.Text = $"Đang theo dõi map: {MapCatalog.Format(selected.Id)} (chỉ giám sát, không điều khiển game)";
    }

    private void btnClearWatchMap_Click(object? sender, EventArgs e)
    {
        _watchedMapId = null;
        UpdateMapWatchLabels();
        RefreshMapLiveColumn();
        lblStatus.Text = "Đã bỏ theo dõi map.";
    }

    private void btnShowLiveMap_Click(object? sender, EventArgs e)
    {
        var liveMapId = SnapshotLiveClients()
            .Select(c => c.MapId)
            .FirstOrDefault(id => id is not null);

        if (liveMapId is null)
        {
            MessageBox.Show(
                "Chưa đọc được map từ process live. Hãy bật realtime hoặc quét map/tọa độ trước.",
                "Maps",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return;
        }

        txtMapSearch.Text = liveMapId.Value.ToString();
        RefreshMapList();
        SelectMapInList(liveMapId.Value);
        UpdateMapWatchLabels();
    }

    private void RefreshMapList()
    {
        var maps = MapCatalog.Search(txtMapSearch.Text);
        var liveByMap = SnapshotLiveClients()
            .Where(c => c.MapId is not null)
            .GroupBy(c => c.MapId!.Value)
            .ToDictionary(
                g => g.Key,
                g => string.Join(", ", g.Select(c => c.CharacterName).Where(n => !string.IsNullOrWhiteSpace(n))));

        var selectedId = GetSelectedMapInfo()?.Id;

        listMaps.BeginUpdate();
        listMaps.Items.Clear();
        foreach (var map in maps)
        {
            var item = new ListViewItem(map.Id.ToString("000"));
            item.SubItems.Add(map.Name);
            item.SubItems.Add(map.Category);
            item.SubItems.Add(liveByMap.TryGetValue(map.Id, out var live) ? live : string.Empty);
            item.Tag = map;
            if (_watchedMapId == map.Id)
            {
                item.BackColor = Color.FromArgb(220, 235, 255);
            }

            listMaps.Items.Add(item);
        }

        listMaps.EndUpdate();

        if (selectedId is not null)
        {
            SelectMapInList(selectedId.Value);
        }
    }

    private void RefreshMapLiveColumn()
    {
        if (listMaps.Items.Count == 0)
        {
            return;
        }

        var liveByMap = SnapshotLiveClients()
            .Where(c => c.MapId is not null)
            .GroupBy(c => c.MapId!.Value)
            .ToDictionary(
                g => g.Key,
                g => string.Join(", ", g.Select(c => c.CharacterName).Where(n => !string.IsNullOrWhiteSpace(n))));

        foreach (ListViewItem item in listMaps.Items)
        {
            if (item.Tag is not MapInfo map)
            {
                continue;
            }

            while (item.SubItems.Count < 4)
            {
                item.SubItems.Add(string.Empty);
            }

            var liveText = liveByMap.TryGetValue(map.Id, out var live) ? live : string.Empty;
            if (!string.Equals(item.SubItems[3].Text, liveText, StringComparison.Ordinal))
            {
                item.SubItems[3].Text = liveText;
            }

            var watchColor = _watchedMapId == map.Id
                ? Color.FromArgb(220, 235, 255)
                : listMaps.BackColor;
            if (item.BackColor != watchColor)
            {
                item.BackColor = watchColor;
            }
        }
    }

    private void UpdateMapWatchLabels()
    {
        if (_watchedMapId is null)
        {
            lblMapWatch.Text = "Map đang theo dõi: (chưa chọn)";
        }
        else
        {
            lblMapWatch.Text = $"Map đang theo dõi: {MapCatalog.FormatDetail(_watchedMapId)}";
        }

        var selected = GetSelectedMapInfo();
        if (selected is not null && selected.Id != _watchedMapId)
        {
            lblMapWatch.Text += $"  |  Đang chọn: {selected.Display}";
        }

        var clients = SnapshotLiveClients();
        if (_watchedMapId is null)
        {
            var distinctMaps = clients
                .Where(c => c.MapId is not null)
                .Select(c => c.MapId!.Value)
                .Distinct()
                .OrderBy(id => id)
                .Select(id => MapCatalog.Format(id))
                .ToList();

            lblMapLiveMatch.Text = distinctMaps.Count == 0
                ? "Khớp process live: (chưa có dữ liệu map)"
                : $"Map live hiện có: {string.Join("; ", distinctMaps)}";
            return;
        }

        var matches = clients
            .Where(c => c.MapId == _watchedMapId)
            .Select(c => $"{c.CharacterName} ({c.CoordDisplay})")
            .ToList();

        lblMapLiveMatch.Text = matches.Count == 0
            ? $"Khớp process live: không có nhân vật nào đang ở map {_watchedMapId}"
            : $"Khớp process live ({matches.Count}): {string.Join("; ", matches)}";
    }

    private MapInfo? GetSelectedMapInfo()
    {
        if (listMaps.SelectedItems.Count == 0)
        {
            return null;
        }

        return listMaps.SelectedItems[0].Tag as MapInfo;
    }

    private void SelectMapInList(int mapId)
    {
        foreach (ListViewItem item in listMaps.Items)
        {
            if (item.Tag is MapInfo map && map.Id == mapId)
            {
                item.Selected = true;
                item.Focused = true;
                item.EnsureVisible();
                return;
            }
        }
    }

    private void UpdateLiveClientListRows(IReadOnlyList<LiveClientInfo> clients)
    {
        if (listLiveClients.Items.Count != clients.Count)
        {
            RefreshLiveClientList(updateMaps: false);
            return;
        }

        for (var i = 0; i < clients.Count; i++)
        {
            var client = clients[i];
            var item = listLiveClients.Items[i];
            if (item.Tag is not LiveClientInfo tagged || tagged.ProcessId != client.ProcessId)
            {
                RefreshLiveClientList(updateMaps: false);
                return;
            }

            SetLiveClientItem(item, client);
        }
    }

    private static ListViewItem CreateLiveClientItem(LiveClientInfo client)
    {
        var item = new ListViewItem(client.ProcessId.ToString());
        item.SubItems.Add(client.CharacterName);
        item.SubItems.Add(client.Server);
        item.SubItems.Add(client.LevelInfo);
        item.SubItems.Add(client.AccountUsername ?? "(chưa đọc được)");
        item.SubItems.Add(string.IsNullOrWhiteSpace(client.MapDisplay) ? "(chưa quét)" : client.MapDisplay);
        item.SubItems.Add(string.IsNullOrWhiteSpace(client.CoordDisplay) ? "(chưa quét)" : client.CoordDisplay);
        item.SubItems.Add(client.Source);
        item.Tag = client;
        return item;
    }

    private static void SetLiveClientItem(ListViewItem item, LiveClientInfo client)
    {
        EnsureSubItemCount(item, 7);
        SetSubItemText(item, 0, client.ProcessId.ToString());
        SetSubItemText(item, 1, client.CharacterName);
        SetSubItemText(item, 2, client.Server);
        SetSubItemText(item, 3, client.LevelInfo);
        SetSubItemText(item, 4, client.AccountUsername ?? "(chưa đọc được)");
        SetSubItemText(item, 5, string.IsNullOrWhiteSpace(client.MapDisplay) ? "(chưa quét)" : client.MapDisplay);
        SetSubItemText(item, 6, string.IsNullOrWhiteSpace(client.CoordDisplay) ? "(chưa quét)" : client.CoordDisplay);
        SetSubItemText(item, 7, client.Source);
        item.Tag = client;
    }

    private static void SetSubItemText(ListViewItem item, int index, string value)
    {
        if (index == 0)
        {
            if (!string.Equals(item.Text, value, StringComparison.Ordinal))
            {
                item.Text = value;
            }

            return;
        }

        if (!string.Equals(item.SubItems[index].Text, value, StringComparison.Ordinal))
        {
            item.SubItems[index].Text = value;
        }
    }

    private static void EnsureSubItemCount(ListViewItem item, int subItemCount)
    {
        while (item.SubItems.Count <= subItemCount)
        {
            item.SubItems.Add(string.Empty);
        }
    }

    private void listLiveClients_DoubleClick(object? sender, EventArgs e)
    {
        if (listLiveClients.SelectedItems.Count > 0 &&
            listLiveClients.SelectedItems[0].Tag is LiveClientInfo client)
        {
            tabMain.SelectedTab = tabRamInspector;
            RefreshRamProcessList(client.ProcessId);
        }
    }

    #region RAM Inspector & Warp Delta Tracker

    private void RefreshRamProcessList(int? preservePid = null)
    {
        var targetPid = preservePid ?? _selectedRamPid;
        var clients = ProcessMemory.GetLiveClientsFromWindowTitles();
        cmbRamProcess.BeginUpdate();
        try
        {
            cmbRamProcess.Items.Clear();
            var targetIndex = -1;
            for (var i = 0; i < clients.Count; i++)
            {
                var c = clients[i];
                var label = $"PID {c.ProcessId} - {c.CharacterName} ({c.Server})";
                cmbRamProcess.Items.Add(new RamProcessComboItem(c.ProcessId, label));
                if (targetPid.HasValue && c.ProcessId == targetPid.Value)
                {
                    targetIndex = i;
                }
            }

            if (targetIndex >= 0)
            {
                cmbRamProcess.SelectedIndex = targetIndex;
            }
            else if (cmbRamProcess.Items.Count > 0)
            {
                cmbRamProcess.SelectedIndex = 0;
            }
            else
            {
                _selectedRamPid = null;
                _lastWarpState = null;
                listRamFields.Items.Clear();
            }
        }
        finally
        {
            cmbRamProcess.EndUpdate();
        }
    }

    private void cmbRamProcess_SelectedIndexChanged(object? sender, EventArgs e)
    {
        if (cmbRamProcess.SelectedItem is RamProcessComboItem item)
        {
            _selectedRamPid = item.ProcessId;
            _lastWarpState = null;
            CaptureRamSnapshot(showToast: false);
        }
    }

    private void btnRefreshRamProcesses_Click(object? sender, EventArgs e)
    {
        RefreshRamProcessList(_selectedRamPid);
    }

    private void btnCaptureSnapshot_Click(object? sender, EventArgs e)
    {
        CaptureRamSnapshot(showToast: true);
    }

    private void chkAutoTrackRam_CheckedChanged(object? sender, EventArgs e)
    {
        if (chkAutoTrackRam.Checked)
        {
            StartRamAutoTrack();
        }
        else
        {
            StopRamAutoTrack();
        }
    }

    private void btnClearRamLog_Click(object? sender, EventArgs e)
    {
        listRamDeltas.Items.Clear();
    }

    private void StartRamAutoTrack()
    {
        if (_ramTrackTimer is null)
        {
            _ramTrackTimer = new System.Windows.Forms.Timer
            {
                Interval = 1000
            };
            _ramTrackTimer.Tick += (_, _) => PerformRamDiff();
        }

        _ramTrackTimer.Start();
        lblStatus.Text = $"Đang tự động theo dõi biến thiên RAM (PID: {_selectedRamPid})...";
    }

    private void StopRamAutoTrack()
    {
        _ramTrackTimer?.Stop();
        if (chkAutoTrackRam.Checked)
        {
            chkAutoTrackRam.Checked = false;
        }
    }

    private void CaptureRamSnapshot(bool showToast)
    {
        if (!_selectedRamPid.HasValue)
        {
            if (showToast)
            {
                MessageBox.Show("Vui lòng chọn một tiến trình MEGAMU để phân tích RAM.", "Phân tích RAM", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            return;
        }

        var pid = _selectedRamPid.Value;
        var fields = ProcessMemory.InspectProcessRamFields(pid);
        var state = ProcessMemory.ReadWarpMemoryState(pid);

        listRamFields.BeginUpdate();
        try
        {
            listRamFields.Items.Clear();
            foreach (var f in fields)
            {
                var lvi = new ListViewItem(f.Category);
                lvi.SubItems.Add(f.Name);
                lvi.SubItems.Add(f.Offset);
                lvi.SubItems.Add(f.AddressHex);
                lvi.SubItems.Add(f.ValueDisplay);
                lvi.SubItems.Add(f.Description);

                // Highlight important Warp/Coord rows
                if (f.Category.Contains("Warp"))
                {
                    lvi.BackColor = Color.FromArgb(240, 248, 255); // AliceBlue
                }
                else if (f.Category.Contains("Tọa độ"))
                {
                    lvi.BackColor = Color.FromArgb(245, 255, 250); // MintCream
                }

                listRamFields.Items.Add(lvi);
            }
        }
        finally
        {
            listRamFields.EndUpdate();
        }

        if (_lastWarpState is not null && state is not null)
        {
            var deltas = ProcessMemory.CompareWarpStates(_lastWarpState, state);
            AppendRamDeltas(deltas);
        }

        _lastWarpState = state;

        if (showToast)
        {
            lblStatus.Text = $"Đã chụp snapshot RAM của PID {pid} ({fields.Count} trường dữ liệu).";
        }
    }

    private void PerformRamDiff()
    {
        if (!_selectedRamPid.HasValue)
        {
            return;
        }

        var pid = _selectedRamPid.Value;
        var current = ProcessMemory.ReadWarpMemoryState(pid);
        if (current is null)
        {
            return;
        }

        if (_lastWarpState is not null)
        {
            var deltas = ProcessMemory.CompareWarpStates(_lastWarpState, current);
            if (deltas.Count > 0)
            {
                AppendRamDeltas(deltas);
                UpdateRamFieldValues(current);
            }
        }

        _lastWarpState = current;
    }

    private void UpdateRamFieldValues(WarpMemoryState state)
    {
        foreach (ListViewItem item in listRamFields.Items)
        {
            var name = item.SubItems.Count > 1 ? item.SubItems[1].Text : "";
            if (name.Contains("SceneIndex") && state.SceneIndex.HasValue)
            {
                item.SubItems[4].Text = $"{state.SceneIndex} ({state.MapName})";
            }
            else if (name.Contains("Live Tile Coord"))
            {
                item.SubItems[4].Text = state.CurrentCoordDisplay;
            }
            else if (name.Contains("Target Tile Coord"))
            {
                item.SubItems[4].Text = state.TargetCoordDisplay;
            }
            else if (name.Contains("Last Server Coord"))
            {
                item.SubItems[4].Text = state.LastServerCoordDisplay;
            }
            else if (name.Contains("3D World Position"))
            {
                item.SubItems[4].Text = $"X={state.PosX:F2}, Y={state.PosY:F2}, Z={state.PosZ:F2}";
            }
            else if (name.Contains("QuitTime"))
            {
                item.SubItems[4].Text = $"{state.QuitTime:F1}";
            }
            else if (name.Contains("MSM IsActive"))
            {
                item.SubItems[4].Text = state.IsActive.ToString();
            }
        }
    }

    private void AppendRamDeltas(List<RamDeltaLog> deltas)
    {
        if (deltas.Count == 0) return;

        listRamDeltas.BeginUpdate();
        try
        {
            foreach (var d in deltas)
            {
                var lvi = new ListViewItem(d.Timestamp.ToString("HH:mm:ss"));
                lvi.SubItems.Add(d.Category);
                lvi.SubItems.Add(d.PropertyName);
                lvi.SubItems.Add(d.OldValue);
                lvi.SubItems.Add(d.NewValue);
                lvi.SubItems.Add(d.Note);

                if (d.Note.Contains("[WARP"))
                {
                    lvi.BackColor = Color.FromArgb(255, 235, 238); // Red tint
                    lvi.ForeColor = Color.DarkRed;
                }
                else if (d.Note.Contains("[JUMP") || d.Note.Contains("[TỌA ĐỘ NHẢY"))
                {
                    lvi.BackColor = Color.FromArgb(255, 248, 225); // Amber tint
                }

                listRamDeltas.Items.Insert(0, lvi); // newest at top
            }

            // Cap deltas list to 200 items
            while (listRamDeltas.Items.Count > 200)
            {
                listRamDeltas.Items.RemoveAt(listRamDeltas.Items.Count - 1);
            }
        }
        finally
        {
            listRamDeltas.EndUpdate();
        }
    }

    private sealed record RamProcessComboItem(int ProcessId, string Display)
    {
        public override string ToString() => Display;
    }

    #endregion

    #region Background Input Simulator Tab

    private WindowTargetInfo? _selectedInputTarget;
    private CancellationTokenSource? _routeCts;
    private System.Windows.Forms.Timer? _inputCoordTimer;

    private void InitInputSimulatorTab()
    {
        PopulateTargetMaps();
        PopulatePtTargets();
        _inputCoordTimer = new System.Windows.Forms.Timer { Interval = 800 };
        _inputCoordTimer.Tick += InputCoordTimer_Tick;
        _inputCoordTimer.Start();
    }

    private void PopulateTargetMaps()
    {
        try
        {
            cmbTargetMap.BeginUpdate();
            cmbTargetMap.Items.Clear();
            var maps = MapCatalog.GetAll();
            foreach (var m in maps)
            {
                if (!string.IsNullOrWhiteSpace(m.Name) && !cmbTargetMap.Items.Contains(m.Name))
                {
                    cmbTargetMap.Items.Add(m.Name);
                }
            }
            if (cmbTargetMap.Items.Count > 0 && cmbTargetMap.SelectedIndex < 0)
            {
                cmbTargetMap.Text = "Devias";
            }
        }
        catch
        {
        }
        finally
        {
            cmbTargetMap.EndUpdate();
        }
    }

    private void chkLiveTrackingCoord_CheckedChanged(object? sender, EventArgs e)
    {
        if (_inputCoordTimer != null)
        {
            _inputCoordTimer.Enabled = chkLiveTrackingCoord.Checked;
        }
    }

    private void InputCoordTimer_Tick(object? sender, EventArgs e)
    {
        if (!chkLiveTrackingCoord.Checked || _selectedInputTarget == null)
        {
            return;
        }

        try
        {
            var warpState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
            if (warpState != null && (warpState.CurrentX != null || !string.IsNullOrWhiteSpace(warpState.MapName)))
            {
                lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): {warpState.CurrentCoordDisplay} - Map: {warpState.MapName}";

                if (string.IsNullOrWhiteSpace(cmbTargetMap.Text) && !string.IsNullOrWhiteSpace(warpState.MapName))
                {
                    cmbTargetMap.Text = warpState.MapName;
                }

                UpdateCoordPreview();
            }
        }
        catch
        {
            // Ignore background polling errors
        }
    }

    private void RefreshInputProcesses()
    {
        try
        {
            cmbInputProc.BeginUpdate();
            cmbInputProc.Items.Clear();

            var addedHwnds = new HashSet<IntPtr>();

            // 1. MEGAMU processes
            foreach (var proc in Process.GetProcessesByName("MEGAMU"))
            {
                var wins = BackgroundInputSimulator.FindWindowsForProcess(proc.Id);
                var hasAdded = false;
                foreach (var w in wins)
                {
                    if (addedHwnds.Add(w.Hwnd))
                    {
                        cmbInputProc.Items.Add(new InputTargetComboItem(w));
                        hasAdded = true;
                    }
                }

                if (!hasAdded)
                {
                    var state = ProcessMemory.ReadWarpMemoryState(proc.Id);
                    var loc = !string.IsNullOrWhiteSpace(state?.MapName)
                        ? $"{state.MapName} {state.CurrentCoordDisplay}"
                        : $"PID {proc.Id}";

                    cmbInputProc.Items.Add(new InputTargetComboItem(new WindowTargetInfo
                    {
                        Hwnd = proc.MainWindowHandle,
                        ProcessId = proc.Id,
                        Title = $"MEGAMU [{loc}] (Ẩn/Tray)",
                        ClassName = "UnityWndClass",
                        ClientRect = new Rectangle(0, 0, 1024, 768),
                        WindowRect = new Rectangle(0, 0, 1024, 768),
                        IsVisible = false,
                        IsMinimized = true
                    }));
                }
            }

            // 2. Also add other top-level visible application windows (e.g. Notepad, Calculator, etc. for quick testing)
            var currentPid = Process.GetCurrentProcess().Id;
            foreach (var proc in Process.GetProcesses())
            {
                if (proc.Id == currentPid || proc.ProcessName.Equals("MEGAMU", StringComparison.OrdinalIgnoreCase)) continue;
                try
                {
                    if (proc.MainWindowHandle != IntPtr.Zero && !string.IsNullOrWhiteSpace(proc.MainWindowTitle))
                    {
                        var info = BackgroundInputSimulator.InspectWindow(proc.MainWindowHandle, proc.Id);
                        if (info != null && info.IsVisible && addedHwnds.Add(info.Hwnd))
                        {
                            cmbInputProc.Items.Add(new InputTargetComboItem(info));
                        }
                    }
                }
                catch { }
            }

            if (cmbInputProc.Items.Count > 0)
            {
                cmbInputProc.SelectedIndex = 0;
            }
            else
            {
                lblTargetDetails.Text = "(Không tìm thấy cửa sổ nào. Bấm 'Test Mẫu với Notepad' để kiểm chứng)";
            }
        }
        catch (Exception ex)
        {
            AppendInputLog($"Lỗi làm mới danh sách cửa sổ: {ex.Message}");
        }
        finally
        {
            cmbInputProc.EndUpdate();
        }
    }

    private void cmbInputProc_SelectedIndexChanged(object? sender, EventArgs e)
    {
        if (cmbInputProc.SelectedItem is InputTargetComboItem item)
        {
            _selectedInputTarget = item.Target;
            UpdateSelectedTargetDetails();
        }
    }

    private void UpdateSelectedTargetDetails()
    {
        if (_selectedInputTarget == null)
        {
            lblTargetDetails.Text = "(Chưa chọn cửa sổ)";
            lblPlayerLiveCoord.Text = "Tọa độ NV hiện tại (RAM): (Chưa chọn cửa sổ)";
            return;
        }

        // Refresh bounds
        var fresh = BackgroundInputSimulator.InspectWindow(_selectedInputTarget.Hwnd, _selectedInputTarget.ProcessId);
        if (fresh != null)
        {
            _selectedInputTarget = fresh;
        }

        var sb = new StringBuilder();
        sb.AppendLine($"HWND: 0x{_selectedInputTarget.Hwnd.ToInt64():X}  (PID: {_selectedInputTarget.ProcessId})");
        sb.AppendLine($"Tiêu đề: {_selectedInputTarget.Title}");
        sb.AppendLine($"Class: {_selectedInputTarget.ClassName}");
        sb.AppendLine($"Kích thước Client: {_selectedInputTarget.ClientRect.Width} x {_selectedInputTarget.ClientRect.Height}");
        sb.AppendLine($"Vị trí Màn hình: [{_selectedInputTarget.WindowRect.Left}, {_selectedInputTarget.WindowRect.Top}] - [{_selectedInputTarget.WindowRect.Right}, {_selectedInputTarget.WindowRect.Bottom}]");
        sb.AppendLine($"Trạng thái: {(_selectedInputTarget.IsMinimized ? "Thu nhỏ (Minimized)" : "Bình thường")} | {(_selectedInputTarget.IsVisible ? "Visible" : "Hidden")}");
        lblTargetDetails.Text = sb.ToString();

        if (_selectedInputTarget.ClientRect.Width > 0 && _selectedInputTarget.ClientRect.Height > 0)
        {
            numInputX.Maximum = Math.Max(100, _selectedInputTarget.ClientRect.Width);
            numInputY.Maximum = Math.Max(100, _selectedInputTarget.ClientRect.Height);
            numInputX.Value = Math.Max(1, _selectedInputTarget.ClientRect.Width / 2);
            numInputY.Value = Math.Max(1, _selectedInputTarget.ClientRect.Height / 2);
        }

        // Read Live RAM State to display coordinates for Game Coord mode
        try
        {
            var warpState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
            if (warpState != null && (warpState.CurrentX != null || !string.IsNullOrWhiteSpace(warpState.MapName)))
            {
                lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): {warpState.CurrentCoordDisplay} - Map: {warpState.MapName}";
                if (string.IsNullOrWhiteSpace(cmbTargetMap.Text) && !string.IsNullOrWhiteSpace(warpState.MapName))
                {
                    cmbTargetMap.Text = warpState.MapName;
                }
                if (warpState.CurrentX.HasValue && warpState.CurrentX.Value > 0)
                {
                    numGameTargetX.Value = Math.Clamp(warpState.CurrentX.Value, 0, 255);
                }
                if (warpState.CurrentY.HasValue && warpState.CurrentY.Value > 0)
                {
                    numGameTargetY.Value = Math.Clamp(warpState.CurrentY.Value, 0, 255);
                }
            }
            else
            {
                lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): (PID {_selectedInputTarget.ProcessId} không có dữ liệu RAM IL2CPP)";
            }
        }
        catch
        {
            lblPlayerLiveCoord.Text = "Tọa độ NV hiện tại (RAM): (Không đọc được)";
        }

        UpdateCoordPreview();
        PopulatePtTargets();
    }

    private void btnRefreshInputProcs_Click(object? sender, EventArgs e)
    {
        RefreshInputProcesses();
        AppendInputLog("Đã làm mới danh sách cửa sổ.");
    }

    private async void btnLaunchNotepadTest_Click(object? sender, EventArgs e)
    {
        btnLaunchNotepadTest.Enabled = false;
        try
        {
            AppendInputLog("--- Khởi chạy kiểm chứng mô phỏng Click với Notepad ---");
            AppendInputLog("1. Mở Notepad...");
            var proc = Process.Start(new ProcessStartInfo("notepad.exe") { UseShellExecute = true });
            if (proc == null)
            {
                AppendInputLog("Không thể khởi động Notepad.");
                return;
            }

            // Wait for window to be created
            await Task.Delay(800);
            RefreshInputProcesses();

            // Find Notepad in items
            for (int i = 0; i < cmbInputProc.Items.Count; i++)
            {
                if (cmbInputProc.Items[i] is InputTargetComboItem item && item.Target.ProcessId == proc.Id)
                {
                    cmbInputProc.SelectedIndex = i;
                    break;
                }
            }

            if (_selectedInputTarget == null)
            {
                AppendInputLog($"Không tìm thấy HWND của Notepad (PID {proc.Id}).");
                return;
            }

            AppendInputLog($"2. Đã xác định Notepad HWND: 0x{_selectedInputTarget.Hwnd.ToInt64():X}");
            AppendInputLog("3. Đang gửi PostMessage(WM_LBUTTONDOWN / UP) tại tọa độ (120, 120)... Chuột của bạn sẽ KHÔNG di chuyển!");

            var result = await BackgroundInputSimulator.SimulateClickAsync(
                _selectedInputTarget.Hwnd,
                clientX: 120,
                clientY: 120,
                durationMs: 80,
                button: MouseButton.Left,
                sendPreMove: true,
                sendActivateMessage: true);

            AppendInputLog($"Kết quả: {(result.Success ? "THÀNH CÔNG" : "THẤT BẠI")} - {result.Message}");
            AppendInputLog("Ghi chú: Bạn có thể thấy con trỏ văn bản trong Notepad nhấp nháy tại vị trí click mà chuột máy tính của bạn hoàn toàn đứng yên!");
        }
        catch (Exception ex)
        {
            AppendInputLog($"Lỗi test Notepad: {ex.Message}");
        }
        finally
        {
            btnLaunchNotepadTest.Enabled = true;
        }
    }

    private async void btnSendClick_Click(object? sender, EventArgs e)
    {
        if (_selectedInputTarget == null)
        {
            MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi click.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        btnSendClick.Enabled = false;
        try
        {
            var x = (int)numInputX.Value;
            var y = (int)numInputY.Value;
            var duration = (int)numInputDuration.Value;
            var button = rbRightClick.Checked ? MouseButton.Right : MouseButton.Left;
            var activate = chkSendActivate.Checked;
            var useMicroHop = chkUseMicroHop.Checked;

            AppendInputLog($"[GỬI CLICK] Mục tiêu: {_selectedInputTarget.DisplayText} | Nút: {button} | Tọa độ: ({x}, {y}) | Giữ: {duration}ms | Activate: {activate} | MicroHop: {useMicroHop}");

            var result = await BackgroundInputSimulator.SimulateClickAsync(
                _selectedInputTarget.Hwnd,
                clientX: x,
                clientY: y,
                durationMs: duration,
                button: button,
                sendPreMove: true,
                sendActivateMessage: activate,
                useHardwareFastHop: useMicroHop);

            AppendInputLog($"[KẾT QUẢ] {(result.Success ? "THÀNH CÔNG" : "THẤT BẠI")}: {result.Message}");
        }
        catch (Exception ex)
        {
            AppendInputLog($"[LỖI] Ngoại lệ khi thực hiện click: {ex.Message}");
        }
        finally
        {
            btnSendClick.Enabled = true;
        }
    }

    private async void btnSendClickCenter_Click(object? sender, EventArgs e)
    {
        if (_selectedInputTarget == null)
        {
            MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi click.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        btnSendClickCenter.Enabled = false;
        try
        {
            var duration = (int)numInputDuration.Value;
            var button = rbRightClick.Checked ? MouseButton.Right : MouseButton.Left;
            var activate = chkSendActivate.Checked;

            AppendInputLog($"[CLICK TÂM] Mục tiêu: {_selectedInputTarget.DisplayText} | Nút: {button} | Giữ: {duration}ms");

            var result = await BackgroundInputSimulator.SimulateClickCenterAsync(
                _selectedInputTarget.Hwnd,
                durationMs: duration,
                button: button,
                sendActivateMessage: activate);

            AppendInputLog($"[KẾT QUẢ] {(result.Success ? "THÀNH CÔNG" : "THẤT BẠI")}: {result.Message}");
        }
        catch (Exception ex)
        {
            AppendInputLog($"[LỖI] Ngoại lệ khi click tâm: {ex.Message}");
        }
        finally
        {
            btnSendClickCenter.Enabled = true;
        }
    }

    private float GetSelectedCameraAngle()
    {
        return cmbCameraAngle.SelectedIndex switch
        {
            1 => 90f,
            2 => 180f,
            3 => 270f,
            _ => 0f
        };
    }

    private void cmbCameraAngle_SelectedIndexChanged(object? sender, EventArgs e)
    {
        UpdateCoordPreview();
    }

    private sealed record PtTargetComboItem(int ProcessId, string CharacterName, string MapName, int X, int Y)
    {
        public override string ToString() => $"{CharacterName} (PID {ProcessId}) - {MapName} ({X}, {Y})";
    }

    private void PopulatePtTargets()
    {
        try
        {
            cmbPtTarget.BeginUpdate();
            var prevSelectedPid = (cmbPtTarget.SelectedItem as PtTargetComboItem)?.ProcessId;
            cmbPtTarget.Items.Clear();

            var currentSelectedPid = _selectedInputTarget?.ProcessId ?? 0;
            var clients = ProcessMemory.GetLiveClientsFromWindowTitles();

            foreach (var client in clients)
            {
                if (client.ProcessId == currentSelectedPid) continue; // Skip self

                var state = ProcessMemory.ReadWarpMemoryState(client.ProcessId);
                var charName = !string.IsNullOrWhiteSpace(client.CharacterName) ? client.CharacterName : $"MEGAMU #{client.ProcessId}";
                var mapName = state?.MapName ?? client.MapName;
                int x = state?.CurrentX ?? client.X ?? 0;
                int y = state?.CurrentY ?? client.Y ?? 0;

                var item = new PtTargetComboItem(client.ProcessId, charName, mapName, x, y);
                cmbPtTarget.Items.Add(item);

                if (prevSelectedPid.HasValue && prevSelectedPid.Value == client.ProcessId)
                {
                    cmbPtTarget.SelectedItem = item;
                }
            }

            if (cmbPtTarget.SelectedIndex < 0 && cmbPtTarget.Items.Count > 0)
            {
                cmbPtTarget.SelectedIndex = 0;
            }
        }
        catch
        {
        }
        finally
        {
            cmbPtTarget.EndUpdate();
        }
    }

    private void cmbPtTarget_SelectedIndexChanged(object? sender, EventArgs e)
    {
        ApplySelectedPtTarget(showLog: false);
    }

    private void btnSyncPtCoord_Click(object? sender, EventArgs e)
    {
        PopulatePtTargets();
        ApplySelectedPtTarget(showLog: true);
    }

    private void ApplySelectedPtTarget(bool showLog)
    {
        if (cmbPtTarget.SelectedItem is not PtTargetComboItem ptItem) return;

        // Re-read latest RAM coord of PT target
        var freshPtState = ProcessMemory.ReadWarpMemoryState(ptItem.ProcessId);
        int ptX = freshPtState?.CurrentX ?? ptItem.X;
        int ptY = freshPtState?.CurrentY ?? ptItem.Y;
        string ptMap = freshPtState?.MapName ?? ptItem.MapName;

        numGameTargetX.Value = Math.Clamp(ptX, 0, 255);
        numGameTargetY.Value = Math.Clamp(ptY, 0, 255);

        if (!string.IsNullOrWhiteSpace(ptMap) && !string.Equals(cmbTargetMap.Text, ptMap, StringComparison.OrdinalIgnoreCase))
        {
            cmbTargetMap.Text = ptMap;
        }

        // Auto-generate optimal path to this PT member
        GeneratePathToDestination(silent: !showLog);

        if (showLog)
        {
            AppendInputLog($"[THEO DÕI PT] Đã đọc RAM đồng đội '{ptItem.CharacterName}' (PID {ptItem.ProcessId}): Tọa độ ({ptX}, {ptY}) trên map '{ptMap}'. Đã tạo đường đi ngắn nhất!");
        }
    }

    private void btnAutoGeneratePath_Click(object? sender, EventArgs e)
    {
        GeneratePathToDestination(silent: false);
    }

    private void GeneratePathToDestination(bool silent = false)
    {
        if (_selectedInputTarget == null)
        {
            if (!silent)
            {
                MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi tạo đường đi.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            return;
        }

        var warpState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
        int curX = warpState?.CurrentX ?? 0;
        int curY = warpState?.CurrentY ?? 0;
        int targetX = (int)numGameTargetX.Value;
        int targetY = (int)numGameTargetY.Value;

        if (curX == 0 && curY == 0)
        {
            if (!silent)
            {
                AppendInputLog("[TÌM ĐƯỜNG] Không đọc được tọa độ hiện tại từ RAM. Vui lòng đảm bảo nhân vật đã vào map.");
            }
            return;
        }

        int dx = targetX - curX;
        int dy = targetY - curY;
        int dist = Math.Max(Math.Abs(dx), Math.Abs(dy));

        if (dist == 0)
        {
            txtWaypoints.Text = $"{targetX},{targetY}";
            if (!silent)
            {
                AppendInputLog($"[TÌM ĐƯỜNG] Nhân vật đã ở tại tọa độ đích ({targetX}, {targetY}).");
            }
            return;
        }

        var waypoints = BackgroundInputSimulator.GenerateShortestPathWaypoints(new Point(curX, curY), new Point(targetX, targetY), maxStepDistance: 5);
        txtWaypoints.Text = BackgroundInputSimulator.FormatWaypointsString(waypoints);

        var analysis = BackgroundInputSimulator.AnalyzeMovementAxes(curX, curY, targetX, targetY);

        if (!silent)
        {
            AppendInputLog($"[PHÂN TÍCH ĐƯỜNG ĐI] Từ ({curX}, {curY}) ➔ Đích ({targetX}, {targetY}):");
            AppendInputLog($"  • Trục X: {curX} ➔ {targetX} ({analysis.XDirectionText})");
            AppendInputLog($"  • Trục Y: {curY} ➔ {targetY} ({analysis.YDirectionText})");
            AppendInputLog($"  • Hướng tổng hợp: {analysis.ScreenDirection} | Khoảng cách: {dist} ô");
            AppendInputLog($"  • Lộ trình tối ưu ({waypoints.Count} bước đệm ≤ 5 ô): {txtWaypoints.Text}");
        }

        UpdateCoordPreview();
    }

    private void TargetCoord_ValueChanged(object? sender, EventArgs e)
    {
        GeneratePathToDestination(silent: true);
        UpdateCoordPreview();
    }

    private void UpdateCoordPreview()
    {
        if (_selectedInputTarget == null)
        {
            lblCoordPreview.Text = "Dự tính: (Chưa chọn cửa sổ)";
            return;
        }

        try
        {
            var warpState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
            int currentX = warpState?.CurrentX ?? 0;
            int currentY = warpState?.CurrentY ?? 0;
            int targetX = (int)numGameTargetX.Value;
            int targetY = (int)numGameTargetY.Value;

            var analysis = BackgroundInputSimulator.AnalyzeMovementAxes(currentX, currentY, targetX, targetY);
            int steps = (int)Math.Ceiling(analysis.ChebyshevDistance / 5.0);

            var angle = GetSelectedCameraAngle();
            var pixel = BackgroundInputSimulator.GameCoordToScreenPixel(
                currentX, currentY, targetX, targetY,
                _selectedInputTarget.ClientRect.Width,
                _selectedInputTarget.ClientRect.Height,
                angle);

            var arrivalCond = analysis.ChebyshevDistance == 0 
                ? "ĐÃ TỚI ĐÍCH (0 ô)" 
                : (analysis.IsArrived ? "Thỏa mãn đến đích (≤ 1 ô)" : $"Cần {steps} bước đệm (Thỏa mãn khi dist ≤ 1)");

            lblCoordPreview.Text = $"[PHÂN TÍCH TRỤC RAM] ({currentX}, {currentY}) ➔ ({targetX}, {targetY}) | {analysis.XDirectionText}, {analysis.YDirectionText} | Hướng: {analysis.ScreenDirection} | Cách: {analysis.ChebyshevDistance} ô ➜ Pixel ({pixel.X}, {pixel.Y}) | {arrivalCond}";
        }
        catch
        {
            lblCoordPreview.Text = "Dự tính: (Đang đọc tọa độ RAM...)";
        }
    }

    private async void btnClickGameCoord_Click(object? sender, EventArgs e)
    {
        if (_selectedInputTarget == null)
        {
            MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi click.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        // Re-resolve HWND dynamically in case window was restored from tray or changed
        if (_selectedInputTarget.Hwnd == IntPtr.Zero || !BackgroundInputSimulator.IsWindowValid(_selectedInputTarget.Hwnd))
        {
            var fresh = BackgroundInputSimulator.ResolveMainWindow(_selectedInputTarget.ProcessId);
            if (fresh != null && fresh.Hwnd != IntPtr.Zero)
            {
                _selectedInputTarget = fresh;
            }
        }

        btnClickGameCoord.Enabled = false;
        btnRunRoute.Enabled = false;
        btnStopRoute.Enabled = true;
        _routeCts = new CancellationTokenSource();

        try
        {
            var targetX = (int)numGameTargetX.Value;
            var targetY = (int)numGameTargetY.Value;
            var targetMap = cmbTargetMap.Text.Trim();
            var duration = (int)numInputDuration.Value;
            var activate = chkSendActivate.Checked;
            var angle = GetSelectedCameraAngle();
            var autoWarp = chkAutoWarpMap.Checked && !string.IsNullOrWhiteSpace(targetMap);
            var useMicroHop = chkUseMicroHop.Checked;

            if (autoWarp)
            {
                AppendInputLog($"[GAME NAV] Tự động kiểm tra map '{targetMap}' và điều hướng khép kín tới ({targetX}, {targetY}) [Micro-Hop: {useMicroHop}]...");
                var warpResult = await BackgroundInputSimulator.AutoWarpAndNavigateAsync(
                    _selectedInputTarget.Hwnd,
                    _selectedInputTarget.ProcessId,
                    targetMap,
                    targetX,
                    targetY,
                    angle,
                    msg => AppendInputLog(msg),
                    _routeCts.Token,
                    useMicroHop);

                AppendInputLog($"[KẾT QUẢ ĐIỀU HƯỚNG] {(warpResult.Success ? "THÀNH CÔNG" : "THẤT BẠI")}: {warpResult.Message}");
            }
            else
            {
                var warpState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
                int curX = warpState?.CurrentX ?? targetX;
                int curY = warpState?.CurrentY ?? targetY;

                var analysis = BackgroundInputSimulator.AnalyzeMovementAxes(curX, curY, targetX, targetY);
                AppendInputLog($"=== [BẮT ĐẦU BƯỚC TỚI ĐÍCH CUỐI CÙNG] ===");
                AppendInputLog($"  • Vị trí RAM hiện tại: ({curX}, {curY}) ➔ Đích Cuối: ({targetX}, {targetY})");
                AppendInputLog($"  • Trục X: {analysis.XDirectionText}");
                AppendInputLog($"  • Trục Y: {analysis.YDirectionText}");
                AppendInputLog($"  • Hướng di chuyển màn hình: {analysis.ScreenDirection} | Khoảng cách: {analysis.ChebyshevDistance} ô");

                if (analysis.IsArrived)
                {
                    AppendInputLog($"[🎉 ĐÃ TỚI ĐÍCH] Nhân vật đã ở ({curX}, {curY}) [Cách đích {analysis.ChebyshevDistance} ô ≤ 1 ô]. Thỏa mãn điều kiện dừng!");
                }
                else
                {
                    var waypoints = new List<Point> { new Point(targetX, targetY) };
                    var results = await BackgroundInputSimulator.SimulateWalkRouteAsync(
                        _selectedInputTarget.Hwnd,
                        _selectedInputTarget.ProcessId,
                        waypoints,
                        angle,
                        arrivalRadius: 1,
                        maxWaitSecondsPerStep: 6,
                        onProgress: msg => AppendInputLog(msg),
                        cancellationToken: _routeCts.Token,
                        useHardwareFastHop: useMicroHop);

                    AppendInputLog($"=== [KẾT QUẢ ĐIỀU HƯỚNG] ({results.Count(r => r.Success)}/{results.Count} thao tác thành công) ===");
                }
            }

            // Update live coord display after movement
            var freshState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
            if (freshState != null)
            {
                lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): {freshState.CurrentCoordDisplay} - Map: {freshState.MapName}";
                UpdateCoordPreview();
            }
        }
        catch (OperationCanceledException)
        {
            AppendInputLog("[ĐIỀU HƯỚNG] Người dùng đã bấm '⏹ Dừng'.");
        }
        catch (Exception ex)
        {
            AppendInputLog($"[LỖI] Ngoại lệ khi di chuyển tới tọa độ: {ex.Message}");
        }
        finally
        {
            btnClickGameCoord.Enabled = true;
            btnRunRoute.Enabled = true;
            btnStopRoute.Enabled = false;
            _routeCts?.Dispose();
            _routeCts = null;
        }
    }

    private async void btnSendMoveCmd_Click(object? sender, EventArgs e)
    {
        if (_selectedInputTarget == null)
        {
            MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi chuyển map.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var mapName = cmbTargetMap.Text.Trim();
        if (string.IsNullOrWhiteSpace(mapName))
        {
            MessageBox.Show("Vui lòng chọn hoặc nhập tên map đích (ví dụ: Devias, Lorencia, Noria...).", "Chưa chọn map", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (_selectedInputTarget.Hwnd == IntPtr.Zero || !BackgroundInputSimulator.IsWindowValid(_selectedInputTarget.Hwnd))
        {
            var fresh = BackgroundInputSimulator.ResolveMainWindow(_selectedInputTarget.ProcessId);
            if (fresh != null && fresh.Hwnd != IntPtr.Zero)
            {
                _selectedInputTarget = fresh;
            }
        }

        btnSendMoveCmd.Enabled = false;
        try
        {
            var clean = BackgroundInputSimulator.NormalizeMoveMapName(mapName);
            var initialState = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
            var currentMap = initialState?.MapName ?? string.Empty;
            int? currentSceneIndex = initialState?.SceneIndex;

            AppendInputLog($"[LỆNH CHUYỂN MAP] Đang gửi '/m {clean}' vào PID {_selectedInputTarget.ProcessId} (Map hiện tại: {currentMap})...");

            var ok = await BackgroundInputSimulator.SendChatCommandAsync(_selectedInputTarget.Hwnd, $"/m {clean}");
            if (!ok)
            {
                AppendInputLog("[LỆNH CHUYỂN MAP] Gửi lệnh không thành công.");
                return;
            }

            AppendInputLog("[LỆNH CHUYỂN MAP] Đã gửi lệnh '/m {clean}'. Đang theo dõi RAM kiểm tra đổi map (tối đa 7s)...");

            var sw = Stopwatch.StartNew();
            bool warpSuccess = false;
            while (sw.ElapsedMilliseconds < 7000)
            {
                await Task.Delay(200);
                var check = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
                if (check != null &&
                    (!string.Equals(check.MapName, currentMap, StringComparison.OrdinalIgnoreCase) ||
                     (check.SceneIndex != currentSceneIndex && check.SceneIndex != null)))
                {
                    warpSuccess = true;
                    AppendInputLog($"[LỆNH CHUYỂN MAP THÀNH CÔNG] Đã chuyển sang bản đồ '{check.MapName}' {check.CurrentCoordDisplay}!");
                    lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): {check.CurrentCoordDisplay} - Map: {check.MapName}";
                    UpdateCoordPreview();
                    break;
                }
            }

            if (!warpSuccess)
            {
                var rawClean = mapName.Trim().ToLowerInvariant();
                if (!string.Equals(rawClean, clean, StringComparison.OrdinalIgnoreCase))
                {
                    AppendInputLog($"[LỆNH CHUYỂN MAP THỬ LẠI] Thử lại với '/m {rawClean}'...");
                    await BackgroundInputSimulator.SendChatCommandAsync(_selectedInputTarget.Hwnd, $"/m {rawClean}");

                    var sw2 = Stopwatch.StartNew();
                    while (sw2.ElapsedMilliseconds < 5000)
                    {
                        await Task.Delay(200);
                        var check = ProcessMemory.ReadWarpMemoryState(_selectedInputTarget.ProcessId);
                        if (check != null &&
                            (!string.Equals(check.MapName, currentMap, StringComparison.OrdinalIgnoreCase) ||
                             (check.SceneIndex != currentSceneIndex && check.SceneIndex != null)))
                        {
                            warpSuccess = true;
                            AppendInputLog($"[LỆNH CHUYỂN MAP THÀNH CÔNG] Đã chuyển sang bản đồ '{check.MapName}' {check.CurrentCoordDisplay}!");
                            lblPlayerLiveCoord.Text = $"Tọa độ NV hiện tại (RAM): {check.CurrentCoordDisplay} - Map: {check.MapName}";
                            UpdateCoordPreview();
                            break;
                        }
                    }
                }
            }

            if (!warpSuccess)
            {
                AppendInputLog("[CẢNH BÁO] Không phát hiện đổi map trong RAM. Có thể nhân vật không đủ Zen/Level, hoặc đang đứng trong vùng cấm di chuyển.");
            }
        }
        catch (Exception ex)
        {
            AppendInputLog($"[LỖI] {ex.Message}");
        }
        finally
        {
            btnSendMoveCmd.Enabled = true;
        }
    }

    private async void btnRunRoute_Click(object? sender, EventArgs e)
    {
        if (_selectedInputTarget == null)
        {
            MessageBox.Show("Vui lòng chọn cửa sổ mục tiêu trước khi chạy lộ trình.", "Chưa chọn cửa sổ", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var text = txtWaypoints.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            MessageBox.Show("Vui lòng nhập danh sách tọa độ (Ví dụ: 95,205; 98,212; 102,220).", "Chưa nhập lộ trình", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var waypoints = new List<Point>();
        var segments = text.Split(new[] { ';', '\n', '\r', '|' }, StringSplitOptions.RemoveEmptyEntries);
        foreach (var seg in segments)
        {
            var parts = seg.Split(new[] { ',', ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2 && int.TryParse(parts[0], out var wx) && int.TryParse(parts[1], out var wy))
            {
                waypoints.Add(new Point(wx, wy));
            }
        }

        if (waypoints.Count == 0)
        {
            MessageBox.Show("Không phân tích được điểm tọa độ nào. Định dạng hợp lệ: 95,205; 98,212", "Lỗi định dạng", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        _routeCts = new CancellationTokenSource();
        btnRunRoute.Enabled = false;
        btnClickGameCoord.Enabled = false;
        btnStopRoute.Enabled = true;

        try
        {
            var angle = GetSelectedCameraAngle();
            var useMicroHop = chkUseMicroHop.Checked;
            var wpString = string.Join(" ➔ ", waypoints.Select(p => $"({p.X}, {p.Y})"));
            AppendInputLog($"=== BẮT ĐẦU CHẠY LỘ TRÌNH ({waypoints.Count} mốc chính, Micro-Hop: {useMicroHop}): {wpString} ===");
            var results = await BackgroundInputSimulator.SimulateWalkRouteAsync(
                _selectedInputTarget.Hwnd,
                _selectedInputTarget.ProcessId,
                waypoints,
                angle,
                arrivalRadius: 1,
                maxWaitSecondsPerStep: 6,
                onProgress: msg => AppendInputLog(msg),
                cancellationToken: _routeCts.Token,
                useHardwareFastHop: useMicroHop);

            AppendInputLog($"=== HOÀN TẤT LỘ TRÌNH ({results.Count(r => r.Success)}/{results.Count} thao tác click thành công) ===");
        }
        catch (OperationCanceledException)
        {
            AppendInputLog("[LỘ TRÌNH] Đã hủy lộ trình theo yêu cầu của người dùng.");
        }
        catch (Exception ex)
        {
            AppendInputLog($"[LỖI LỘ TRÌNH] {ex.Message}");
        }
        finally
        {
            btnRunRoute.Enabled = true;
            btnClickGameCoord.Enabled = true;
            btnStopRoute.Enabled = false;
            _routeCts?.Dispose();
            _routeCts = null;
        }
    }

    private void btnStopRoute_Click(object? sender, EventArgs e)
    {
        _routeCts?.Cancel();
    }

    private void btnClearInputLogs_Click(object? sender, EventArgs e)
    {
        txtInputLogs.Clear();
    }

    private static readonly object _logLock = new();
    private static readonly string _logFilePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "MegAccountManager",
        "navigation.log");

    private void AppendInputLog(string message)
    {
        var line = $"[{DateTime.Now:HH:mm:ss.fff}] {message}";
        void append()
        {
            txtInputLogs.AppendText(line + Environment.NewLine);
            txtInputLogs.SelectionStart = txtInputLogs.Text.Length;
            txtInputLogs.ScrollToCaret();
        }

        if (txtInputLogs.InvokeRequired)
        {
            txtInputLogs.Invoke((Action)append);
        }
        else
        {
            append();
        }

        try
        {
            var logDir = Path.GetDirectoryName(_logFilePath);
            if (!string.IsNullOrEmpty(logDir) && !Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }
            lock (_logLock)
            {
                File.AppendAllText(_logFilePath, line + Environment.NewLine);
            }
        }
        catch
        {
        }
    }

    private sealed record InputTargetComboItem(WindowTargetInfo Target)
    {
        public override string ToString() => Target.DisplayText;
    }

    #endregion
}
