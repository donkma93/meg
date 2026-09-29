namespace MegAccountManager;

partial class MainForm
{
    private System.ComponentModel.IContainer components = null!;
    private ListBox listAccounts = null!;
    private ListBox listCharacters = null!;
    private ListView listLiveClients = null!;
    private Button btnAddAccount = null!;
    private Button btnEditAccount = null!;
    private Button btnDeleteAccount = null!;
    private Button btnAddCharacter = null!;
    private Button btnEditCharacter = null!;
    private Button btnDeleteCharacter = null!;
    private Button btnReload = null!;
    private Button btnOpenDataFolder = null!;
    private Button btnScanProcesses = null!;
    private Button btnTrackRealtime = null!;
    private Button btnImportRegistry = null!;
    private Button btnImportLive = null!;
    private Label lblAccounts = null!;
    private Label lblCharacters = null!;
    private Label lblLive = null!;
    private Label lblStatus = null!;
    private TabControl tabMain = null!;
    private TabPage tabAccounts = null!;
    private TabPage tabMaps = null!;
    private SplitContainer splitMain = null!;
    private SplitContainer splitRight = null!;
    private Panel panelAccountButtons = null!;
    private Panel panelCharacterButtons = null!;
    private Panel panelLiveButtons = null!;
    private Panel panelBottom = null!;
    private Panel panelAccountsHeader = null!;
    private Panel panelCharactersHeader = null!;
    private Panel panelLiveHeader = null!;
    private Panel panelMapsToolbar = null!;
    private Panel panelMapsDetail = null!;
    private ListView listMaps = null!;
    private TextBox txtMapSearch = null!;
    private Label lblMapSearch = null!;
    private Label lblMapWatch = null!;
    private Label lblMapLiveMatch = null!;
    private Label lblMapHint = null!;
    private Button btnSetWatchMap = null!;
    private Button btnClearWatchMap = null!;
    private Button btnShowLiveMap = null!;
    private TabPage tabRamInspector = null!;
    private Panel panelRamToolbar = null!;
    private Label lblRamSelectProc = null!;
    private ComboBox cmbRamProcess = null!;
    private Button btnRefreshRamProcesses = null!;
    private Button btnCaptureSnapshot = null!;
    private CheckBox chkAutoTrackRam = null!;
    private Button btnClearRamLog = null!;
    private SplitContainer splitRam = null!;
    private Panel panelRamFieldsHeader = null!;
    private Label lblRamFieldsHeader = null!;
    private ListView listRamFields = null!;
    private Panel panelRamDeltasHeader = null!;
    private Label lblRamDeltasHeader = null!;
    private ListView listRamDeltas = null!;

    private TabPage tabInputSimulator = null!;
    private Panel panelInputTop = null!;
    private Label lblInputProc = null!;
    private ComboBox cmbInputProc = null!;
    private Button btnRefreshInputProcs = null!;
    private Button btnLaunchNotepadTest = null!;
    private GroupBox grpTargetInfo = null!;
    private Label lblTargetDetails = null!;
    private GroupBox grpClickControls = null!;
    private Label lblInputX = null!;
    private NumericUpDown numInputX = null!;
    private Label lblInputY = null!;
    private NumericUpDown numInputY = null!;
    private Label lblInputDuration = null!;
    private NumericUpDown numInputDuration = null!;
    private RadioButton rbLeftClick = null!;
    private RadioButton rbRightClick = null!;
    private CheckBox chkSendActivate = null!;
    private Button btnSendClick = null!;
    private Button btnSendClickCenter = null!;
    private GroupBox grpGameCoord = null!;
    private Label lblPlayerLiveCoord = null!;
    private CheckBox chkLiveTrackingCoord = null!;
    private Label lblTargetMap = null!;
    private ComboBox cmbTargetMap = null!;
    private CheckBox chkAutoWarpMap = null!;
    private Label lblTargetGameCoordX = null!;
    private NumericUpDown numGameTargetX = null!;
    private Label lblTargetGameCoordY = null!;
    private NumericUpDown numGameTargetY = null!;
    private Button btnClickGameCoord = null!;
    private Button btnSendMoveCmd = null!;
    private Button btnAutoGeneratePath = null!;
    private Label lblPtTarget = null!;
    private ComboBox cmbPtTarget = null!;
    private Button btnSyncPtCoord = null!;
    private Label lblCameraAngle = null!;
    private ComboBox cmbCameraAngle = null!;
    private Label lblCoordPreview = null!;
    private Label lblWaypoints = null!;
    private TextBox txtWaypoints = null!;
    private Button btnRunRoute = null!;
    private Button btnStopRoute = null!;
    private CheckBox chkUseMicroHop = null!;
    private GroupBox grpInputLogs = null!;
    private TextBox txtInputLogs = null!;
    private Button btnClearInputLogs = null!;

    protected override void Dispose(bool disposing)
    {
        if (disposing && components is not null)
        {
            components.Dispose();
        }

        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        components = new System.ComponentModel.Container();

        listAccounts = new ListBox();
        listCharacters = new ListBox();
        listLiveClients = new ListView();
        listMaps = new ListView();
        btnAddAccount = new Button();
        btnEditAccount = new Button();
        btnDeleteAccount = new Button();
        btnAddCharacter = new Button();
        btnEditCharacter = new Button();
        btnDeleteCharacter = new Button();
        btnReload = new Button();
        btnOpenDataFolder = new Button();
        btnScanProcesses = new Button();
        btnTrackRealtime = new Button();
        btnImportRegistry = new Button();
        btnImportLive = new Button();
        btnSetWatchMap = new Button();
        btnClearWatchMap = new Button();
        btnShowLiveMap = new Button();
        lblAccounts = new Label();
        lblCharacters = new Label();
        lblLive = new Label();
        lblStatus = new Label();
        lblMapSearch = new Label();
        lblMapWatch = new Label();
        lblMapLiveMatch = new Label();
        lblMapHint = new Label();
        txtMapSearch = new TextBox();
        tabMain = new TabControl();
        tabAccounts = new TabPage();
        tabMaps = new TabPage();
        splitMain = new SplitContainer();
        splitRight = new SplitContainer();
        panelAccountButtons = new Panel();
        panelCharacterButtons = new Panel();
        panelLiveButtons = new Panel();
        panelBottom = new Panel();
        panelAccountsHeader = new Panel();
        panelCharactersHeader = new Panel();
        panelLiveHeader = new Panel();
        panelMapsToolbar = new Panel();
        panelMapsDetail = new Panel();
        tabRamInspector = new TabPage();
        panelRamToolbar = new Panel();
        lblRamSelectProc = new Label();
        cmbRamProcess = new ComboBox();
        btnRefreshRamProcesses = new Button();
        btnCaptureSnapshot = new Button();
        chkAutoTrackRam = new CheckBox();
        btnClearRamLog = new Button();
        splitRam = new SplitContainer();
        panelRamFieldsHeader = new Panel();
        lblRamFieldsHeader = new Label();
        listRamFields = new ListView();
        panelRamDeltasHeader = new Panel();
        lblRamDeltasHeader = new Label();
        listRamDeltas = new ListView();

        tabInputSimulator = new TabPage();
        panelInputTop = new Panel();
        lblInputProc = new Label();
        cmbInputProc = new ComboBox();
        btnRefreshInputProcs = new Button();
        btnLaunchNotepadTest = new Button();
        grpTargetInfo = new GroupBox();
        lblTargetDetails = new Label();
        grpClickControls = new GroupBox();
        lblInputX = new Label();
        numInputX = new NumericUpDown();
        lblInputY = new Label();
        numInputY = new NumericUpDown();
        lblInputDuration = new Label();
        numInputDuration = new NumericUpDown();
        rbLeftClick = new RadioButton();
        rbRightClick = new RadioButton();
        chkSendActivate = new CheckBox();
        btnSendClick = new Button();
        btnSendClickCenter = new Button();
        grpGameCoord = new GroupBox();
        lblPlayerLiveCoord = new Label();
        chkLiveTrackingCoord = new CheckBox();
        lblTargetMap = new Label();
        cmbTargetMap = new ComboBox();
        chkAutoWarpMap = new CheckBox();
        lblTargetGameCoordX = new Label();
        numGameTargetX = new NumericUpDown();
        lblTargetGameCoordY = new Label();
        numGameTargetY = new NumericUpDown();
        btnClickGameCoord = new Button();
        btnSendMoveCmd = new Button();
        btnAutoGeneratePath = new Button();
        lblPtTarget = new Label();
        cmbPtTarget = new ComboBox();
        btnSyncPtCoord = new Button();
        lblCameraAngle = new Label();
        cmbCameraAngle = new ComboBox();
        lblCoordPreview = new Label();
        lblWaypoints = new Label();
        txtWaypoints = new TextBox();
        btnRunRoute = new Button();
        btnStopRoute = new Button();
        chkUseMicroHop = new CheckBox();
        grpInputLogs = new GroupBox();
        txtInputLogs = new TextBox();
        btnClearInputLogs = new Button();

        ((System.ComponentModel.ISupportInitialize)splitMain).BeginInit();
        ((System.ComponentModel.ISupportInitialize)splitRight).BeginInit();
        ((System.ComponentModel.ISupportInitialize)splitRam).BeginInit();
        splitMain.Panel1.SuspendLayout();
        splitMain.Panel2.SuspendLayout();
        splitRight.Panel1.SuspendLayout();
        splitRight.Panel2.SuspendLayout();
        splitRam.Panel1.SuspendLayout();
        splitRam.Panel2.SuspendLayout();
        splitMain.SuspendLayout();
        splitRight.SuspendLayout();
        splitRam.SuspendLayout();
        panelAccountButtons.SuspendLayout();
        panelCharacterButtons.SuspendLayout();
        panelLiveButtons.SuspendLayout();
        panelBottom.SuspendLayout();
        panelAccountsHeader.SuspendLayout();
        panelCharactersHeader.SuspendLayout();
        panelLiveHeader.SuspendLayout();
        panelMapsToolbar.SuspendLayout();
        panelMapsDetail.SuspendLayout();
        panelRamToolbar.SuspendLayout();
        panelRamFieldsHeader.SuspendLayout();
        panelRamDeltasHeader.SuspendLayout();
        tabAccounts.SuspendLayout();
        tabMaps.SuspendLayout();
        tabRamInspector.SuspendLayout();
        tabMain.SuspendLayout();
        SuspendLayout();

        // Headers
        panelAccountsHeader.Dock = DockStyle.Top;
        panelAccountsHeader.Height = 36;
        panelAccountsHeader.Padding = new Padding(12, 10, 12, 0);
        lblAccounts.AutoSize = true;
        lblAccounts.Text = "Tài khoản đăng nhập";
        panelAccountsHeader.Controls.Add(lblAccounts);

        panelCharactersHeader.Dock = DockStyle.Top;
        panelCharactersHeader.Height = 36;
        panelCharactersHeader.Padding = new Padding(12, 10, 12, 0);
        lblCharacters.AutoSize = true;
        lblCharacters.Text = "Nhân vật theo tài khoản";
        panelCharactersHeader.Controls.Add(lblCharacters);

        panelLiveHeader.Dock = DockStyle.Top;
        panelLiveHeader.Height = 36;
        panelLiveHeader.Padding = new Padding(12, 10, 12, 0);
        lblLive.AutoSize = true;
        lblLive.Text = "Process MEGAMU đang chạy";
        panelLiveHeader.Controls.Add(lblLive);

        // Account buttons
        panelAccountButtons.Dock = DockStyle.Bottom;
        panelAccountButtons.Height = 48;
        panelAccountButtons.Padding = new Padding(12, 8, 12, 8);
        btnAddAccount.Text = "Thêm";
        btnAddAccount.Width = 90;
        btnAddAccount.Height = 30;
        btnAddAccount.Location = new Point(12, 8);
        btnAddAccount.UseVisualStyleBackColor = true;
        btnAddAccount.Click += btnAddAccount_Click;
        btnEditAccount.Text = "Sửa";
        btnEditAccount.Width = 90;
        btnEditAccount.Height = 30;
        btnEditAccount.Location = new Point(108, 8);
        btnEditAccount.UseVisualStyleBackColor = true;
        btnEditAccount.Click += btnEditAccount_Click;
        btnDeleteAccount.Text = "Xóa";
        btnDeleteAccount.Width = 90;
        btnDeleteAccount.Height = 30;
        btnDeleteAccount.Location = new Point(204, 8);
        btnDeleteAccount.UseVisualStyleBackColor = true;
        btnDeleteAccount.Click += btnDeleteAccount_Click;
        panelAccountButtons.Controls.Add(btnAddAccount);
        panelAccountButtons.Controls.Add(btnEditAccount);
        panelAccountButtons.Controls.Add(btnDeleteAccount);

        // Character buttons
        panelCharacterButtons.Dock = DockStyle.Bottom;
        panelCharacterButtons.Height = 48;
        panelCharacterButtons.Padding = new Padding(12, 8, 12, 8);
        btnAddCharacter.Text = "Thêm NV";
        btnAddCharacter.Width = 90;
        btnAddCharacter.Height = 30;
        btnAddCharacter.Location = new Point(12, 8);
        btnAddCharacter.UseVisualStyleBackColor = true;
        btnAddCharacter.Click += btnAddCharacter_Click;
        btnEditCharacter.Text = "Sửa NV";
        btnEditCharacter.Width = 90;
        btnEditCharacter.Height = 30;
        btnEditCharacter.Location = new Point(108, 8);
        btnEditCharacter.UseVisualStyleBackColor = true;
        btnEditCharacter.Click += btnEditCharacter_Click;
        btnDeleteCharacter.Text = "Xóa NV";
        btnDeleteCharacter.Width = 90;
        btnDeleteCharacter.Height = 30;
        btnDeleteCharacter.Location = new Point(204, 8);
        btnDeleteCharacter.UseVisualStyleBackColor = true;
        btnDeleteCharacter.Click += btnDeleteCharacter_Click;
        panelCharacterButtons.Controls.Add(btnAddCharacter);
        panelCharacterButtons.Controls.Add(btnEditCharacter);
        panelCharacterButtons.Controls.Add(btnDeleteCharacter);

        // Live buttons
        panelLiveButtons.Dock = DockStyle.Bottom;
        panelLiveButtons.Height = 48;
        panelLiveButtons.Padding = new Padding(12, 8, 12, 8);
        btnScanProcesses.Text = "Quét map/tọa độ";
        btnScanProcesses.Width = 140;
        btnScanProcesses.Height = 30;
        btnScanProcesses.Location = new Point(12, 8);
        btnScanProcesses.UseVisualStyleBackColor = true;
        btnScanProcesses.Click += btnScanProcesses_Click;
        btnTrackRealtime.Text = "Theo dõi realtime";
        btnTrackRealtime.Width = 140;
        btnTrackRealtime.Height = 30;
        btnTrackRealtime.Location = new Point(158, 8);
        btnTrackRealtime.UseVisualStyleBackColor = true;
        btnTrackRealtime.Click += btnTrackRealtime_Click;
        btnImportRegistry.Text = "Đọc AccountList";
        btnImportRegistry.Width = 130;
        btnImportRegistry.Height = 30;
        btnImportRegistry.Location = new Point(304, 8);
        btnImportRegistry.UseVisualStyleBackColor = true;
        btnImportRegistry.Click += btnImportRegistry_Click;
        btnImportLive.Text = "Nhập vào danh sách";
        btnImportLive.Width = 150;
        btnImportLive.Height = 30;
        btnImportLive.Location = new Point(440, 8);
        btnImportLive.UseVisualStyleBackColor = true;
        btnImportLive.Enabled = false;
        btnImportLive.Click += btnImportLive_Click;
        panelLiveButtons.Controls.Add(btnScanProcesses);
        panelLiveButtons.Controls.Add(btnTrackRealtime);
        panelLiveButtons.Controls.Add(btnImportRegistry);
        panelLiveButtons.Controls.Add(btnImportLive);

        // Lists
        listAccounts.Dock = DockStyle.Fill;
        listAccounts.IntegralHeight = false;
        listAccounts.Font = new Font("Segoe UI", 10F);
        listAccounts.SelectedIndexChanged += listAccounts_SelectedIndexChanged;

        listCharacters.Dock = DockStyle.Fill;
        listCharacters.IntegralHeight = false;
        listCharacters.Font = new Font("Segoe UI", 10F);
        listCharacters.SelectedIndexChanged += listCharacters_SelectedIndexChanged;

        listLiveClients.Dock = DockStyle.Fill;
        listLiveClients.FullRowSelect = true;
        listLiveClients.GridLines = true;
        listLiveClients.HideSelection = false;
        listLiveClients.View = View.Details;
        listLiveClients.Font = new Font("Segoe UI", 9F);
        listLiveClients.Columns.Add("PID", 60);
        listLiveClients.Columns.Add("Nhân vật", 110);
        listLiveClients.Columns.Add("Server", 60);
        listLiveClients.Columns.Add("Level", 80);
        listLiveClients.Columns.Add("Tài khoản", 90);
        listLiveClients.Columns.Add("Map", 140);
        listLiveClients.Columns.Add("Tọa độ", 80);
        listLiveClients.Columns.Add("Nguồn", 120);

        // splitRight
        splitRight.Dock = DockStyle.Fill;
        splitRight.Orientation = Orientation.Horizontal;
        splitRight.Panel1MinSize = 50;
        splitRight.Panel2MinSize = 50;
        splitRight.Panel1.Controls.Add(listCharacters);
        splitRight.Panel1.Controls.Add(panelCharacterButtons);
        splitRight.Panel1.Controls.Add(panelCharactersHeader);
        splitRight.Panel2.Controls.Add(listLiveClients);
        splitRight.Panel2.Controls.Add(panelLiveButtons);
        splitRight.Panel2.Controls.Add(panelLiveHeader);

        // splitMain
        splitMain.Dock = DockStyle.Fill;
        splitMain.Panel1MinSize = 50;
        splitMain.Panel2MinSize = 50;
        splitMain.Panel1.Controls.Add(listAccounts);
        splitMain.Panel1.Controls.Add(panelAccountButtons);
        splitMain.Panel1.Controls.Add(panelAccountsHeader);
        splitMain.Panel2.Controls.Add(splitRight);

        // Maps tab
        panelMapsToolbar.Dock = DockStyle.Top;
        panelMapsToolbar.Height = 48;
        panelMapsToolbar.Padding = new Padding(12, 10, 12, 8);
        lblMapSearch.AutoSize = true;
        lblMapSearch.Text = "Tìm map:";
        lblMapSearch.Location = new Point(12, 14);
        txtMapSearch.Width = 260;
        txtMapSearch.Height = 27;
        txtMapSearch.Location = new Point(80, 10);
        txtMapSearch.PlaceholderText = "Tên, ID hoặc nhóm (Town/Field/Event)...";
        txtMapSearch.TextChanged += txtMapSearch_TextChanged;
        btnShowLiveMap.Text = "Map đang đứng";
        btnShowLiveMap.Width = 120;
        btnShowLiveMap.Height = 30;
        btnShowLiveMap.Location = new Point(360, 8);
        btnShowLiveMap.UseVisualStyleBackColor = true;
        btnShowLiveMap.Click += btnShowLiveMap_Click;
        btnSetWatchMap.Text = "Theo dõi map này";
        btnSetWatchMap.Width = 140;
        btnSetWatchMap.Height = 30;
        btnSetWatchMap.Location = new Point(490, 8);
        btnSetWatchMap.UseVisualStyleBackColor = true;
        btnSetWatchMap.Click += btnSetWatchMap_Click;
        btnClearWatchMap.Text = "Bỏ theo dõi";
        btnClearWatchMap.Width = 110;
        btnClearWatchMap.Height = 30;
        btnClearWatchMap.Location = new Point(640, 8);
        btnClearWatchMap.UseVisualStyleBackColor = true;
        btnClearWatchMap.Click += btnClearWatchMap_Click;
        panelMapsToolbar.Controls.Add(lblMapSearch);
        panelMapsToolbar.Controls.Add(txtMapSearch);
        panelMapsToolbar.Controls.Add(btnShowLiveMap);
        panelMapsToolbar.Controls.Add(btnSetWatchMap);
        panelMapsToolbar.Controls.Add(btnClearWatchMap);

        panelMapsDetail.Dock = DockStyle.Bottom;
        panelMapsDetail.Height = 96;
        panelMapsDetail.Padding = new Padding(12, 8, 12, 8);
        lblMapWatch.AutoSize = false;
        lblMapWatch.Dock = DockStyle.Top;
        lblMapWatch.Height = 22;
        lblMapWatch.Text = "Map đang theo dõi: (chưa chọn)";
        lblMapLiveMatch.AutoSize = false;
        lblMapLiveMatch.Dock = DockStyle.Top;
        lblMapLiveMatch.Height = 22;
        lblMapLiveMatch.Text = "Khớp process live: (chưa có dữ liệu)";
        lblMapHint.AutoSize = false;
        lblMapHint.Dock = DockStyle.Fill;
        lblMapHint.Text =
            "Chỉ xem/catalog + theo dõi. App không gửi lệnh chuyển map vào game.";
        panelMapsDetail.Controls.Add(lblMapHint);
        panelMapsDetail.Controls.Add(lblMapLiveMatch);
        panelMapsDetail.Controls.Add(lblMapWatch);

        listMaps.Dock = DockStyle.Fill;
        listMaps.FullRowSelect = true;
        listMaps.GridLines = true;
        listMaps.HideSelection = false;
        listMaps.View = View.Details;
        listMaps.Font = new Font("Segoe UI", 9F);
        listMaps.Columns.Add("ID", 60);
        listMaps.Columns.Add("Tên map", 220);
        listMaps.Columns.Add("Nhóm", 100);
        listMaps.Columns.Add("Live", 220);
        listMaps.SelectedIndexChanged += listMaps_SelectedIndexChanged;
        listMaps.DoubleClick += listMaps_DoubleClick;

        tabAccounts.Text = "Tài khoản / Process";
        tabAccounts.Padding = new Padding(0);
        tabAccounts.Controls.Add(splitMain);

        tabMaps.Text = "Maps";
        tabMaps.Padding = new Padding(0);
        tabMaps.Controls.Add(listMaps);
        tabMaps.Controls.Add(panelMapsDetail);
        tabMaps.Controls.Add(panelMapsToolbar);

        // Ram Toolbar
        panelRamToolbar.Dock = DockStyle.Top;
        panelRamToolbar.Height = 48;
        panelRamToolbar.Padding = new Padding(12, 10, 12, 8);
        lblRamSelectProc.AutoSize = true;
        lblRamSelectProc.Text = "Chọn Process:";
        lblRamSelectProc.Location = new Point(12, 14);
        cmbRamProcess.Location = new Point(105, 10);
        cmbRamProcess.Width = 230;
        cmbRamProcess.DropDownStyle = ComboBoxStyle.DropDownList;
        cmbRamProcess.SelectedIndexChanged += cmbRamProcess_SelectedIndexChanged;
        btnRefreshRamProcesses.Text = "Làm mới";
        btnRefreshRamProcesses.Width = 80;
        btnRefreshRamProcesses.Height = 30;
        btnRefreshRamProcesses.Location = new Point(345, 8);
        btnRefreshRamProcesses.UseVisualStyleBackColor = true;
        btnRefreshRamProcesses.Click += btnRefreshRamProcesses_Click;
        btnCaptureSnapshot.Text = "Chụp Snapshot";
        btnCaptureSnapshot.Width = 120;
        btnCaptureSnapshot.Height = 30;
        btnCaptureSnapshot.Location = new Point(435, 8);
        btnCaptureSnapshot.UseVisualStyleBackColor = true;
        btnCaptureSnapshot.Click += btnCaptureSnapshot_Click;
        chkAutoTrackRam.AutoSize = true;
        chkAutoTrackRam.Text = "Theo dõi biến thiên (1s)";
        chkAutoTrackRam.Location = new Point(565, 13);
        chkAutoTrackRam.UseVisualStyleBackColor = true;
        chkAutoTrackRam.CheckedChanged += chkAutoTrackRam_CheckedChanged;
        btnClearRamLog.Text = "Xóa nhật ký";
        btnClearRamLog.Width = 95;
        btnClearRamLog.Height = 30;
        btnClearRamLog.Location = new Point(730, 8);
        btnClearRamLog.UseVisualStyleBackColor = true;
        btnClearRamLog.Click += btnClearRamLog_Click;
        panelRamToolbar.Controls.Add(lblRamSelectProc);
        panelRamToolbar.Controls.Add(cmbRamProcess);
        panelRamToolbar.Controls.Add(btnRefreshRamProcesses);
        panelRamToolbar.Controls.Add(btnCaptureSnapshot);
        panelRamToolbar.Controls.Add(chkAutoTrackRam);
        panelRamToolbar.Controls.Add(btnClearRamLog);

        // Ram Fields Panel (Top)
        panelRamFieldsHeader.Dock = DockStyle.Top;
        panelRamFieldsHeader.Height = 28;
        panelRamFieldsHeader.Padding = new Padding(12, 6, 12, 0);
        lblRamFieldsHeader.AutoSize = true;
        lblRamFieldsHeader.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        lblRamFieldsHeader.Text = "Cấu trúc đối tượng RAM IL2CPP & Trạng thái Warp (Read-only):";
        panelRamFieldsHeader.Controls.Add(lblRamFieldsHeader);

        listRamFields.Dock = DockStyle.Fill;
        listRamFields.FullRowSelect = true;
        listRamFields.GridLines = true;
        listRamFields.HideSelection = false;
        listRamFields.View = View.Details;
        listRamFields.Font = new Font("Segoe UI", 9F);
        listRamFields.Columns.Add("Nhóm", 130);
        listRamFields.Columns.Add("Thuộc tính", 170);
        listRamFields.Columns.Add("Offset", 120);
        listRamFields.Columns.Add("Địa chỉ RAM", 140);
        listRamFields.Columns.Add("Giá trị hiện tại", 220);
        listRamFields.Columns.Add("Mô tả / Ý nghĩa", 300);

        // Ram Deltas Panel (Bottom)
        panelRamDeltasHeader.Dock = DockStyle.Top;
        panelRamDeltasHeader.Height = 28;
        panelRamDeltasHeader.Padding = new Padding(12, 6, 12, 0);
        lblRamDeltasHeader.AutoSize = true;
        lblRamDeltasHeader.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        lblRamDeltasHeader.Text = "Nhật ký biến thiên RAM theo thời gian thực (Warp & Delta Tracker):";
        panelRamDeltasHeader.Controls.Add(lblRamDeltasHeader);

        listRamDeltas.Dock = DockStyle.Fill;
        listRamDeltas.FullRowSelect = true;
        listRamDeltas.GridLines = true;
        listRamDeltas.HideSelection = false;
        listRamDeltas.View = View.Details;
        listRamDeltas.Font = new Font("Segoe UI", 9F);
        listRamDeltas.Columns.Add("Thời gian", 90);
        listRamDeltas.Columns.Add("Nhóm", 100);
        listRamDeltas.Columns.Add("Thuộc tính", 150);
        listRamDeltas.Columns.Add("Giá trị cũ", 160);
        listRamDeltas.Columns.Add("Giá trị mới", 160);
        listRamDeltas.Columns.Add("Ghi chú biến thiên / Cảnh báo Warp", 270);

        // Split Ram
        splitRam.Dock = DockStyle.Fill;
        splitRam.Orientation = Orientation.Horizontal;
        splitRam.SplitterDistance = 270;
        splitRam.Panel1MinSize = 100;
        splitRam.Panel2MinSize = 100;
        splitRam.Panel1.Controls.Add(listRamFields);
        splitRam.Panel1.Controls.Add(panelRamFieldsHeader);
        splitRam.Panel2.Controls.Add(listRamDeltas);
        splitRam.Panel2.Controls.Add(panelRamDeltasHeader);

        // Tab Ram Inspector
        tabRamInspector.Text = "Phân tích RAM";
        tabRamInspector.Padding = new Padding(0);
        tabRamInspector.Controls.Add(splitRam);
        tabRamInspector.Controls.Add(panelRamToolbar);

        // Panel Input Top
        panelInputTop.Dock = DockStyle.Top;
        panelInputTop.Height = 44;
        panelInputTop.Padding = new Padding(12, 8, 12, 8);
        lblInputProc.AutoSize = true;
        lblInputProc.Location = new Point(12, 12);
        lblInputProc.Text = "Chọn Cửa Sổ / Tiến Trình:";
        cmbInputProc.DropDownStyle = ComboBoxStyle.DropDownList;
        cmbInputProc.Location = new Point(175, 8);
        cmbInputProc.Width = 360;
        cmbInputProc.SelectedIndexChanged += cmbInputProc_SelectedIndexChanged;
        btnRefreshInputProcs.Location = new Point(545, 8);
        btnRefreshInputProcs.Size = new Size(80, 26);
        btnRefreshInputProcs.Text = "Làm mới";
        btnRefreshInputProcs.Click += btnRefreshInputProcs_Click;
        btnLaunchNotepadTest.Location = new Point(635, 8);
        btnLaunchNotepadTest.Size = new Size(170, 26);
        btnLaunchNotepadTest.Text = "⚡ Test Mẫu với Notepad";
        btnLaunchNotepadTest.Click += btnLaunchNotepadTest_Click;
        panelInputTop.Controls.Add(lblInputProc);
        panelInputTop.Controls.Add(cmbInputProc);
        panelInputTop.Controls.Add(btnRefreshInputProcs);
        panelInputTop.Controls.Add(btnLaunchNotepadTest);

        // Group Target Info
        grpTargetInfo.Text = "Thông Tin Cửa Sổ Đích";
        grpTargetInfo.Location = new Point(12, 50);
        grpTargetInfo.Size = new Size(420, 155);
        lblTargetDetails.Dock = DockStyle.Fill;
        lblTargetDetails.Font = new Font("Consolas", 9F);
        lblTargetDetails.Padding = new Padding(8);
        lblTargetDetails.Text = "(Chưa chọn cửa sổ)";
        grpTargetInfo.Controls.Add(lblTargetDetails);

        // Group Click Controls
        grpClickControls.Text = "Thiết Lập Tọa Độ & Mô Phỏng Click (Không Chiếm Chuột)";
        grpClickControls.Location = new Point(440, 50);
        grpClickControls.Size = new Size(550, 155);

        lblInputX.AutoSize = true;
        lblInputX.Location = new Point(15, 25);
        lblInputX.Text = "X (Client):";
        numInputX.Location = new Point(75, 23);
        numInputX.Size = new Size(70, 23);
        numInputX.Maximum = 9999;
        numInputX.Value = 100;

        lblInputY.AutoSize = true;
        lblInputY.Location = new Point(160, 25);
        lblInputY.Text = "Y (Client):";
        numInputY.Location = new Point(220, 23);
        numInputY.Size = new Size(70, 23);
        numInputY.Maximum = 9999;
        numInputY.Value = 100;

        lblInputDuration.AutoSize = true;
        lblInputDuration.Location = new Point(305, 25);
        lblInputDuration.Text = "Độ trễ (ms):";
        numInputDuration.Location = new Point(380, 23);
        numInputDuration.Size = new Size(60, 23);
        numInputDuration.Minimum = 10;
        numInputDuration.Maximum = 3000;
        numInputDuration.Value = 60;

        rbLeftClick.AutoSize = true;
        rbLeftClick.Location = new Point(18, 60);
        rbLeftClick.Text = "Chuột Trái";
        rbLeftClick.Checked = true;

        rbRightClick.AutoSize = true;
        rbRightClick.Location = new Point(115, 60);
        rbRightClick.Text = "Chuột Phải";

        chkSendActivate.AutoSize = true;
        chkSendActivate.Location = new Point(210, 60);
        chkSendActivate.Text = "Gửi WM_ACTIVATE (Kích hoạt nền)";
        chkSendActivate.Checked = true;

        btnSendClick.Location = new Point(15, 95);
        btnSendClick.Size = new Size(240, 36);
        btnSendClick.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        btnSendClick.Text = "▶ Gửi Click tại (X, Y)";
        btnSendClick.Click += btnSendClick_Click;

        btnSendClickCenter.Location = new Point(270, 95);
        btnSendClickCenter.Size = new Size(240, 36);
        btnSendClickCenter.Text = "🎯 Click Tâm Cửa Sổ (50%, 50%)";
        btnSendClickCenter.Click += btnSendClickCenter_Click;

        grpClickControls.Controls.Add(lblInputX);
        grpClickControls.Controls.Add(numInputX);
        grpClickControls.Controls.Add(lblInputY);
        grpClickControls.Controls.Add(numInputY);
        grpClickControls.Controls.Add(lblInputDuration);
        grpClickControls.Controls.Add(numInputDuration);
        grpClickControls.Controls.Add(rbLeftClick);
        grpClickControls.Controls.Add(rbRightClick);
        grpClickControls.Controls.Add(chkSendActivate);
        grpClickControls.Controls.Add(btnSendClick);
        grpClickControls.Controls.Add(btnSendClickCenter);

        // Group Game Coord (Raycast & Waypoints)
        grpGameCoord.Text = "Mô Phỏng Bước Tới Tọa Độ Game (Isometric Vector, Auto-Warp & Waypoints)";
        grpGameCoord.Location = new Point(12, 215);
        grpGameCoord.Size = new Size(980, 168);

        lblPlayerLiveCoord.AutoSize = true;
        lblPlayerLiveCoord.Location = new Point(15, 24);
        lblPlayerLiveCoord.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        lblPlayerLiveCoord.ForeColor = Color.DarkBlue;
        lblPlayerLiveCoord.Text = "Tọa độ NV hiện tại (RAM): Đang đọc...";

        chkLiveTrackingCoord.AutoSize = true;
        chkLiveTrackingCoord.Location = new Point(340, 23);
        chkLiveTrackingCoord.Text = "🔄 Làm mới liên tục (800ms)";
        chkLiveTrackingCoord.Checked = true;
        chkLiveTrackingCoord.UseVisualStyleBackColor = true;
        chkLiveTrackingCoord.CheckedChanged += chkLiveTrackingCoord_CheckedChanged;

        lblCameraAngle.AutoSize = true;
        lblCameraAngle.Location = new Point(545, 24);
        lblCameraAngle.Text = "Góc Cam 3D:";

        cmbCameraAngle.DropDownStyle = ComboBoxStyle.DropDownList;
        cmbCameraAngle.Location = new Point(630, 20);
        cmbCameraAngle.Size = new Size(130, 23);
        cmbCameraAngle.Items.AddRange(new object[] { "0° (MU Mặc định)", "90° (Xoay 90°)", "180° (Xoay 180°)", "270° (Xoay 270°)" });
        cmbCameraAngle.SelectedIndex = 0;
        cmbCameraAngle.SelectedIndexChanged += cmbCameraAngle_SelectedIndexChanged;

        chkAutoWarpMap.AutoSize = true;
        chkAutoWarpMap.Location = new Point(775, 23);
        chkAutoWarpMap.Text = "Tự động /move khi khác map";
        chkAutoWarpMap.Checked = true;
        chkAutoWarpMap.UseVisualStyleBackColor = true;

        // Row 2: Target Map, Target Coord, Path Generator & Party Follow
        lblTargetMap.AutoSize = true;
        lblTargetMap.Location = new Point(15, 57);
        lblTargetMap.Text = "Map đích:";

        cmbTargetMap.Location = new Point(75, 53);
        cmbTargetMap.Size = new Size(95, 23);
        cmbTargetMap.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
        cmbTargetMap.AutoCompleteSource = AutoCompleteSource.ListItems;

        btnSendMoveCmd.Location = new Point(175, 49);
        btnSendMoveCmd.Size = new Size(75, 30);
        btnSendMoveCmd.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        btnSendMoveCmd.Text = "⚡ /move";
        btnSendMoveCmd.Click += btnSendMoveCmd_Click;

        lblTargetGameCoordX.AutoSize = true;
        lblTargetGameCoordX.Location = new Point(255, 57);
        lblTargetGameCoordX.Text = "Đích X:";
        numGameTargetX.Location = new Point(298, 54);
        numGameTargetX.Size = new Size(48, 23);
        numGameTargetX.Maximum = 255;
        numGameTargetX.Value = 100;
        numGameTargetX.ValueChanged += TargetCoord_ValueChanged;

        lblTargetGameCoordY.AutoSize = true;
        lblTargetGameCoordY.Location = new Point(350, 57);
        lblTargetGameCoordY.Text = "Đích Y:";
        numGameTargetY.Location = new Point(393, 54);
        numGameTargetY.Size = new Size(48, 23);
        numGameTargetY.Maximum = 255;
        numGameTargetY.Value = 100;
        numGameTargetY.ValueChanged += TargetCoord_ValueChanged;

        btnClickGameCoord.Location = new Point(446, 49);
        btnClickGameCoord.Size = new Size(130, 30);
        btnClickGameCoord.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        btnClickGameCoord.Text = "🚶 Bước Tới Đích";
        btnClickGameCoord.Click += btnClickGameCoord_Click;

        btnAutoGeneratePath.Location = new Point(582, 49);
        btnAutoGeneratePath.Size = new Size(135, 30);
        btnAutoGeneratePath.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        btnAutoGeneratePath.Text = "⚡ Tự Tạo Lộ Trình";
        btnAutoGeneratePath.Click += btnAutoGeneratePath_Click;

        lblPtTarget.AutoSize = true;
        lblPtTarget.Location = new Point(723, 57);
        lblPtTarget.Text = "Theo PT:";

        cmbPtTarget.DropDownStyle = ComboBoxStyle.DropDownList;
        cmbPtTarget.Location = new Point(775, 53);
        cmbPtTarget.Size = new Size(125, 23);
        cmbPtTarget.SelectedIndexChanged += cmbPtTarget_SelectedIndexChanged;

        btnSyncPtCoord.Location = new Point(905, 49);
        btnSyncPtCoord.Size = new Size(65, 30);
        btnSyncPtCoord.Text = "🎯 Lấy";
        btnSyncPtCoord.Click += btnSyncPtCoord_Click;

        // Row 3: Dedicated Waypoints Route Row
        lblWaypoints.AutoSize = true;
        lblWaypoints.Location = new Point(15, 96);
        lblWaypoints.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        lblWaypoints.Text = "Lộ trình (Waypoints):";

        txtWaypoints.Location = new Point(145, 93);
        txtWaypoints.Size = new Size(670, 23);
        txtWaypoints.Text = "129,113; 117,120; 115,130";

        btnRunRoute.Location = new Point(825, 89);
        btnRunRoute.Size = new Size(75, 30);
        btnRunRoute.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        btnRunRoute.Text = "▶ Chạy";
        btnRunRoute.Click += btnRunRoute_Click;

        btnStopRoute.Location = new Point(905, 89);
        btnStopRoute.Size = new Size(65, 30);
        btnStopRoute.Text = "⏹ Dừng";
        btnStopRoute.Enabled = false;
        btnStopRoute.Click += btnStopRoute_Click;

        // Row 4: Vector Preview & Comparison + Micro-Hop Toggle
        lblCoordPreview.AutoSize = true;
        lblCoordPreview.Location = new Point(15, 133);
        lblCoordPreview.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
        lblCoordPreview.ForeColor = Color.DarkGreen;
        lblCoordPreview.Text = "Dự tính: (Nhập tọa độ đích để xem trước hướng & pixel)";

        chkUseMicroHop.AutoSize = true;
        chkUseMicroHop.Location = new Point(640, 132);
        chkUseMicroHop.Font = new Font("Segoe UI", 9F, FontStyle.Regular);
        chkUseMicroHop.Text = "⚡ Bỏ qua con trỏ cũ (Đồng bộ đích click, chạy ngầm)";
        chkUseMicroHop.Checked = true;
        chkUseMicroHop.UseVisualStyleBackColor = true;

        grpGameCoord.Controls.Add(lblPlayerLiveCoord);
        grpGameCoord.Controls.Add(chkLiveTrackingCoord);
        grpGameCoord.Controls.Add(lblCameraAngle);
        grpGameCoord.Controls.Add(cmbCameraAngle);
        grpGameCoord.Controls.Add(chkAutoWarpMap);
        grpGameCoord.Controls.Add(lblTargetMap);
        grpGameCoord.Controls.Add(cmbTargetMap);
        grpGameCoord.Controls.Add(btnSendMoveCmd);
        grpGameCoord.Controls.Add(lblTargetGameCoordX);
        grpGameCoord.Controls.Add(numGameTargetX);
        grpGameCoord.Controls.Add(lblTargetGameCoordY);
        grpGameCoord.Controls.Add(numGameTargetY);
        grpGameCoord.Controls.Add(btnClickGameCoord);
        grpGameCoord.Controls.Add(btnAutoGeneratePath);
        grpGameCoord.Controls.Add(lblPtTarget);
        grpGameCoord.Controls.Add(cmbPtTarget);
        grpGameCoord.Controls.Add(btnSyncPtCoord);
        grpGameCoord.Controls.Add(lblWaypoints);
        grpGameCoord.Controls.Add(txtWaypoints);
        grpGameCoord.Controls.Add(btnRunRoute);
        grpGameCoord.Controls.Add(btnStopRoute);
        grpGameCoord.Controls.Add(lblCoordPreview);
        grpGameCoord.Controls.Add(chkUseMicroHop);

        // Group Input Logs
        grpInputLogs.Text = "Nhật Ký Mô Phỏng Input & Biến Động RAM";
        grpInputLogs.Location = new Point(12, 395);
        grpInputLogs.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        grpInputLogs.Size = new Size(980, 150);

        btnClearInputLogs.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        btnClearInputLogs.Location = new Point(885, 14);
        btnClearInputLogs.Size = new Size(80, 24);
        btnClearInputLogs.Text = "Xóa Log";
        btnClearInputLogs.Click += btnClearInputLogs_Click;

        txtInputLogs.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        txtInputLogs.Location = new Point(12, 42);
        txtInputLogs.Size = new Size(956, 96);
        txtInputLogs.Multiline = true;
        txtInputLogs.ReadOnly = true;
        txtInputLogs.ScrollBars = ScrollBars.Both;
        txtInputLogs.WordWrap = false;
        txtInputLogs.Font = new Font("Consolas", 9F);
        txtInputLogs.BackColor = Color.FromArgb(248, 249, 250);
        grpInputLogs.Controls.Add(btnClearInputLogs);
        grpInputLogs.Controls.Add(txtInputLogs);

        // Tab Input Simulator
        tabInputSimulator.Text = "Mô phỏng Input (Background)";
        tabInputSimulator.Padding = new Padding(0);
        tabInputSimulator.Controls.Add(grpInputLogs);
        tabInputSimulator.Controls.Add(grpGameCoord);
        tabInputSimulator.Controls.Add(grpClickControls);
        tabInputSimulator.Controls.Add(grpTargetInfo);
        tabInputSimulator.Controls.Add(panelInputTop);

        tabMain.Dock = DockStyle.Fill;
        tabMain.Font = new Font("Segoe UI", 9F);
        tabMain.Controls.Add(tabAccounts);
        tabMain.Controls.Add(tabMaps);
        tabMain.Controls.Add(tabRamInspector);
        tabMain.Controls.Add(tabInputSimulator);

        // panelBottom
        panelBottom.Dock = DockStyle.Bottom;
        panelBottom.Height = 48;
        panelBottom.Padding = new Padding(12, 8, 12, 8);
        lblStatus.AutoEllipsis = true;
        lblStatus.Dock = DockStyle.Fill;
        lblStatus.TextAlign = ContentAlignment.MiddleLeft;
        lblStatus.Text = "Sẵn sàng";
        btnReload.Text = "Tải lại";
        btnReload.Width = 90;
        btnReload.Height = 28;
        btnReload.Dock = DockStyle.Right;
        btnReload.UseVisualStyleBackColor = true;
        btnReload.Click += btnReload_Click;
        btnOpenDataFolder.Text = "Mở thư mục";
        btnOpenDataFolder.Width = 100;
        btnOpenDataFolder.Height = 28;
        btnOpenDataFolder.Dock = DockStyle.Right;
        btnOpenDataFolder.UseVisualStyleBackColor = true;
        btnOpenDataFolder.Click += btnOpenDataFolder_Click;
        panelBottom.Controls.Add(lblStatus);
        panelBottom.Controls.Add(btnReload);
        panelBottom.Controls.Add(btnOpenDataFolder);

        // MainForm
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        ClientSize = new Size(1024, 680);
        Controls.Add(tabMain);
        Controls.Add(panelBottom);
        MinimumSize = new Size(920, 620);
        Name = "MainForm";
        StartPosition = FormStartPosition.CenterScreen;
        Text = "MEGAMU - Quản lý tài khoản & nhân vật";
        Shown += MainForm_Shown;

        ((System.ComponentModel.ISupportInitialize)splitMain).EndInit();
        ((System.ComponentModel.ISupportInitialize)splitRight).EndInit();
        ((System.ComponentModel.ISupportInitialize)splitRam).EndInit();
        splitMain.Panel1.ResumeLayout(false);
        splitMain.Panel2.ResumeLayout(false);
        splitRight.Panel1.ResumeLayout(false);
        splitRight.Panel2.ResumeLayout(false);
        splitRam.Panel1.ResumeLayout(false);
        splitRam.Panel1.PerformLayout();
        splitRam.Panel2.ResumeLayout(false);
        splitRam.Panel2.PerformLayout();
        splitMain.ResumeLayout(false);
        splitRight.ResumeLayout(false);
        splitRam.ResumeLayout(false);
        panelAccountButtons.ResumeLayout(false);
        panelCharacterButtons.ResumeLayout(false);
        panelLiveButtons.ResumeLayout(false);
        panelBottom.ResumeLayout(false);
        panelAccountsHeader.ResumeLayout(false);
        panelAccountsHeader.PerformLayout();
        panelCharactersHeader.ResumeLayout(false);
        panelCharactersHeader.PerformLayout();
        panelLiveHeader.ResumeLayout(false);
        panelLiveHeader.PerformLayout();
        panelMapsToolbar.ResumeLayout(false);
        panelMapsToolbar.PerformLayout();
        panelMapsDetail.ResumeLayout(false);
        panelRamToolbar.ResumeLayout(false);
        panelRamToolbar.PerformLayout();
        panelRamFieldsHeader.ResumeLayout(false);
        panelRamFieldsHeader.PerformLayout();
        panelRamDeltasHeader.ResumeLayout(false);
        panelRamDeltasHeader.PerformLayout();
        tabAccounts.ResumeLayout(false);
        tabMaps.ResumeLayout(false);
        tabRamInspector.ResumeLayout(false);
        tabInputSimulator.ResumeLayout(false);
        tabMain.ResumeLayout(false);
        ResumeLayout(false);
    }
}
