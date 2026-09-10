#define MyAppName "Eclipse Flow"
#define MyAppVersion "5.4.0"
#define MyAppExeName "Eclipse Downloader.exe"

[Setup]
AppId={{6F9A355E-301B-4DA7-B67D-27041CCEE807}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Eclipse Flow
DefaultDirName={localappdata}\Programs\Eclipse Flow
DefaultGroupName=Eclipse Flow
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=.
OutputBaseFilename=EclipseFlow-Instalador-Windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=5.4.0.0
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Eclipse Flow"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Eclipse Flow"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o Eclipse Flow"; Flags: nowait postinstall skipifsilent
