; ==============================================================================
; MEGAMU Auto Train Dashboard - Inno Setup 6 Script
; Kich ban tao ban cai dat chuyen nghiep, gon gang cho nguoi dung
; ==============================================================================

#define MyAppName "MEGAMU Auto Train Dashboard"
#define MyAppPublisher "MEGAMU Auto Train Team"
#define MyAppExeName "MEGAMU Auto Train Dashboard.exe"

#ifndef MyAppVersion
  #define MyAppVersion "1.5.3"
#endif

#ifndef SourceDir
  #define SourceDir "installer_staging"
#endif

#ifndef OutputDir
  #define OutputDir "dist_installer"
#endif

#ifndef OutputFileName
  #define OutputFileName "MEGAMU_AutoTrain_Setup_" + MyAppVersion
#endif

[Setup]
AppId={{E68A8D25-B41F-4B89-9CEE-A89E623E5F3B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputFileName}
SetupIconFile=megamu_dashboard_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\megamu_dashboard_icon.ico
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\config"; Permissions: users-modify

[Files]
; File thuc thi chinh va cac file ho tro can thiet
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\meg_license_bridge.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\megamu_dashboard_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\megamu_dashboard_logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\map_commands.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\megamu_dashboard_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\megamu_dashboard_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall runascurrentuser skipifsilent
