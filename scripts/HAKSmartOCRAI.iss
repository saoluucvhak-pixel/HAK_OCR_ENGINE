; HAK Smart OCR AI — Inno Setup 6 Windows installer.
; The release build script passes /DMyAppVersion=1.2.0-alpha.
#ifndef MyAppVersion
#define MyAppVersion "1.2.0-alpha"
#endif
#define MyAppName "HAK Smart OCR AI"
#define MyExeName "HAKSmartOCRAI.exe"
[Setup]
AppId={{844BE83B-A7BB-463F-A439-53636C32EE90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\HAK Smart OCR AI
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=HAKSmartOCRAI-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyExeName}
DisableProgramGroupPage=yes
[Files]
Source: "..\dist\HAKSmartOCRAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\HAK Smart OCR AI"; Filename: "{app}\{#MyExeName}"
Name: "{autodesktop}\HAK Smart OCR AI"; Filename: "{app}\{#MyExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng Desktop"; Flags: unchecked
[Run]
Filename: "{app}\{#MyExeName}"; Description: "Mở HAK Smart OCR AI"; Flags: postinstall nowait skipifsilent
