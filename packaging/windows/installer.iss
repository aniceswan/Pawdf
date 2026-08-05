; Pawdf per-user Windows installer.
#ifndef AppVersion
#define AppVersion "0.2.1"
#endif
#define AppName "Pawdf"
#define AppPublisher "Pawdf contributors"
#define AppExeName "pawdf.exe"

[Setup]
AppId={{B5E1B6B2-6B7E-4B7B-9C1A-0DF700000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExeName}
OutputBaseFilename=Pawdf-Windows-x86_64-Setup
OutputDir=..\..\dist
; lzma2/ultra64 (Inno Setup's most aggressive preset) ran a GitHub-hosted
; Windows runner out of memory compiling this installer: solid-compressing a
; ~460 MiB payload at a 64 MiB dictionary across 4 parallel block threads
; multiplies peak memory well past what a standard hosted runner has
; available. lzma2/max keeps solid LZMA2 compression with an 8 MiB
; dictionary - still clearly better than the plain "lzma" preset - at a
; fraction of the memory, and drops the explicit thread count so Inno Setup
; picks a safe default instead of forcing 4-way parallelism.
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\icons\icon.ico
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\..\dist\pawdf\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
