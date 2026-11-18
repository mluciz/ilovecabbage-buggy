; CABBAGE Control Studio v1.8 user-scoped GUI installer.
; Build ONLY on Windows after PyInstaller creates dist\CabbageControlStudio.exe
; No auto-start, no system drivers, no Arduino flashing, no elevated privileges.
#define MyAppName "Cabbage Control Studio"
#define MyAppVersion "1.8.2"
#define MyAppExeName "CabbageControlStudio.exe"

[Setup]
AppId={{37A2A77F-6D7B-4E3E-818F-4C22F2CC18B7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion} (Test Candidate)
AppPublisher=CABBAGE Buggy Project
AppPublisherURL=https://github.com/mluciz/ilovecabbage-buggy
AppSupportURL=https://github.com/mluciz/ilovecabbage-buggy/issues
AppUpdatesURL=https://github.com/mluciz/ilovecabbage-buggy
DefaultDirName={localappdata}\Programs\CabbageControlStudio
DefaultGroupName=Cabbage Control Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
DisableProgramGroupPage=yes
AllowNoIcons=no
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName=Cabbage Control Studio (v1.8.2 Live Buggy Candidate)
SetupIconFile=..\branding\CabbageStudio.ico
OutputDir=..\dist\installer
OutputBaseFilename=CabbageControlStudio-v1.8.2-Setup-LiveBuggy-CANDIDATE
Compression=lzma2
SolidCompression=yes
SetupLogging=yes
UsePreviousAppDir=yes
CloseApplications=no
RestartApplications=no
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\CabbageControlStudio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\WHEEL_DOCTOR_FIELD_GUIDE.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\V18_DESIGN_AUDIT.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\INSTALL_WINDOWS.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\SPATIAL_LAB_INTEGRATION.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\..\unreal-visualizer\*"; DestDir: "{app}\unreal-visualizer"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cabbage Control Studio"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Open the buggy controller (starts disconnected)"
Name: "{group}\Uninstall Cabbage Control Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Cabbage Control Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Cabbage Control Studio (disconnected)"; Flags: nowait postinstall skipifsilent unchecked
