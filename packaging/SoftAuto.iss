#define MyAppName "零禾一智能 SoftAuto"
#define MyAppVersion "0.5.6"
#define MyAppPublisher "零禾一智能"
#define MyAppExeName "SoftAuto.exe"

[Setup]
AppId={{4EC57656-A7C7-4ED1-ADE6-B3701ED95755}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer-dist
OutputBaseFilename=Lingheyi-SoftAuto-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\softauto.ico
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "dist\SoftAuto\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\SoftAutoMCP\*"; DestDir: "{app}\mcp"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "安装与MCP配置.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\零禾一智能 SoftAuto"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\安装与 MCP 配置"; Filename: "{app}\安装与MCP配置.txt"
Name: "{autodesktop}\零禾一智能 SoftAuto"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动零禾一智能 SoftAuto"; Flags: nowait postinstall skipifsilent
