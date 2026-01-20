; Simply AI - Home Edition
; Inno Setup Installer Script
;
; Requirements:
; - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; - PyInstaller output in dist\SimplyAI folder
;
; Build: Open this file in Inno Setup Compiler and click Build > Compile

#define MyAppName "Simply AI - Home Edition"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Simply AI"
#define MyAppURL "https://github.com/your-repo/simply-ai"
#define MyAppExeName "SimplyAI.exe"

[Setup]
; Application information
AppId={{B8F5E9A2-7C34-4D12-9E8F-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\SimplyAI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=..\installer_output
OutputBaseFilename=SimplyAI-Setup-{#MyAppVersion}
SetupIconFile=..\static\images\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes

; Windows version requirements
MinVersion=10.0

; Privileges (user-level install by default)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Visual settings
WizardStyle=modern
WizardSizePercent=120

; License and info pages (optional - uncomment if you have these files)
; LicenseFile=..\LICENSE.txt
; InfoBeforeFile=..\README.txt

; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files from PyInstaller output
Source: "..\dist\SimplyAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Create empty directories for runtime data
; These will be created by the app on first run, but we ensure they exist

[Dirs]
; Data directories (user-writable)
Name: "{app}\instance"; Permissions: users-modify
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\chroma"; Permissions: users-modify
Name: "{app}\uploads"; Permissions: users-modify
Name: "{app}\uploads\images"; Permissions: users-modify
Name: "{app}\uploads\documents"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
; Start menu and desktop shortcuts (icon embedded in exe, with fallback to ico file)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to launch after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data on uninstall (optional - only if user confirms)
Type: filesandordirs; Name: "{app}\instance"
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\uploads"
Type: filesandordirs; Name: "{app}\logs"

[Messages]
; Custom messages
WelcomeLabel2=This will install [name/ver] on your computer.%n%nSimply AI is a unified chat interface for multiple AI providers (Gemini, OpenAI, Anthropic, xAI, LM Studio, Ollama).%n%nFeatures:%n- Multi-provider AI chat%n- User authentication with 2FA%n- File attachments support%n- RAG (document chat)%n%nIt is recommended that you close all other applications before continuing.

[Code]
// Pascal Script for custom installer behavior

var
  PortPage: TInputQueryWizardPage;
  AdminPage: TWizardPage;
  AdminUsernameEdit: TNewEdit;
  AdminEmailEdit: TNewEdit;
  AdminPasswordEdit: TPasswordEdit;
  AdminPasswordConfirmEdit: TPasswordEdit;

procedure InitializeWizard;
var
  UsernameLabel, EmailLabel, PasswordLabel, PasswordConfirmLabel, RequirementsLabel: TNewStaticText;
  TopPos: Integer;
begin
  // Create custom page for port configuration
  PortPage := CreateInputQueryPage(wpSelectDir,
    'Server Configuration',
    'Configure the Simply AI server settings',
    'Please specify the port number for the web server (default: 8080)');
  PortPage.Add('Port:', False);
  PortPage.Values[0] := '8080';

  // Create custom page for admin credentials
  AdminPage := CreateCustomPage(PortPage.ID,
    'Administrator Account',
    'Create your administrator account for Simply AI');

  TopPos := 0;

  // Username field
  UsernameLabel := TNewStaticText.Create(AdminPage);
  UsernameLabel.Parent := AdminPage.Surface;
  UsernameLabel.Caption := 'Username:';
  UsernameLabel.Top := TopPos;
  UsernameLabel.Left := 0;

  AdminUsernameEdit := TNewEdit.Create(AdminPage);
  AdminUsernameEdit.Parent := AdminPage.Surface;
  AdminUsernameEdit.Top := TopPos + 16;
  AdminUsernameEdit.Left := 0;
  AdminUsernameEdit.Width := 300;
  AdminUsernameEdit.Text := 'admin';

  TopPos := TopPos + 48;

  // Email field
  EmailLabel := TNewStaticText.Create(AdminPage);
  EmailLabel.Parent := AdminPage.Surface;
  EmailLabel.Caption := 'Email:';
  EmailLabel.Top := TopPos;
  EmailLabel.Left := 0;

  AdminEmailEdit := TNewEdit.Create(AdminPage);
  AdminEmailEdit.Parent := AdminPage.Surface;
  AdminEmailEdit.Top := TopPos + 16;
  AdminEmailEdit.Left := 0;
  AdminEmailEdit.Width := 300;
  AdminEmailEdit.Text := 'admin@simply.ai';

  TopPos := TopPos + 48;

  // Password field
  PasswordLabel := TNewStaticText.Create(AdminPage);
  PasswordLabel.Parent := AdminPage.Surface;
  PasswordLabel.Caption := 'Password:';
  PasswordLabel.Top := TopPos;
  PasswordLabel.Left := 0;

  AdminPasswordEdit := TPasswordEdit.Create(AdminPage);
  AdminPasswordEdit.Parent := AdminPage.Surface;
  AdminPasswordEdit.Top := TopPos + 16;
  AdminPasswordEdit.Left := 0;
  AdminPasswordEdit.Width := 300;

  TopPos := TopPos + 48;

  // Password confirm field
  PasswordConfirmLabel := TNewStaticText.Create(AdminPage);
  PasswordConfirmLabel.Parent := AdminPage.Surface;
  PasswordConfirmLabel.Caption := 'Confirm Password:';
  PasswordConfirmLabel.Top := TopPos;
  PasswordConfirmLabel.Left := 0;

  AdminPasswordConfirmEdit := TPasswordEdit.Create(AdminPage);
  AdminPasswordConfirmEdit.Parent := AdminPage.Surface;
  AdminPasswordConfirmEdit.Top := TopPos + 16;
  AdminPasswordConfirmEdit.Left := 0;
  AdminPasswordConfirmEdit.Width := 300;

  TopPos := TopPos + 52;

  // Password requirements info
  RequirementsLabel := TNewStaticText.Create(AdminPage);
  RequirementsLabel.Parent := AdminPage.Surface;
  RequirementsLabel.Caption :=
    'Password Requirements:' + #13#10 +
    '  - Minimum 8 characters' + #13#10 +
    '  - At least one uppercase letter (A-Z)' + #13#10 +
    '  - At least one lowercase letter (a-z)' + #13#10 +
    '  - At least one number (0-9)' + #13#10 +
    '  - At least one special character (!@#$%^&*...)';
  RequirementsLabel.Top := TopPos;
  RequirementsLabel.Left := 0;
  RequirementsLabel.AutoSize := True;
  RequirementsLabel.Font.Color := clGray;
end;

function HasUppercase(const S: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to Length(S) do
    if (S[I] >= 'A') and (S[I] <= 'Z') then
    begin
      Result := True;
      Exit;
    end;
end;

function HasLowercase(const S: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to Length(S) do
    if (S[I] >= 'a') and (S[I] <= 'z') then
    begin
      Result := True;
      Exit;
    end;
end;

function HasDigit(const S: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to Length(S) do
    if (S[I] >= '0') and (S[I] <= '9') then
    begin
      Result := True;
      Exit;
    end;
end;

function HasSpecialChar(const S: String): Boolean;
var
  I: Integer;
  C: Char;
begin
  Result := False;
  for I := 1 to Length(S) do
  begin
    C := S[I];
    if not (((C >= 'A') and (C <= 'Z')) or
            ((C >= 'a') and (C <= 'z')) or
            ((C >= '0') and (C <= '9'))) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function IsValidEmail(const Email: String): Boolean;
var
  AtPos, DotPos: Integer;
begin
  Result := False;
  AtPos := Pos('@', Email);
  if AtPos < 2 then Exit;
  DotPos := Pos('.', Copy(Email, AtPos + 1, Length(Email)));
  if DotPos < 2 then Exit;
  Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Port: Integer;
  Username, Email, Password, PasswordConfirm: String;
  ErrorMsg: String;
begin
  Result := True;

  // Validate port number
  if CurPageID = PortPage.ID then
  begin
    Port := StrToIntDef(PortPage.Values[0], 0);
    if (Port < 1) or (Port > 65535) then
    begin
      MsgBox('Please enter a valid port number (1-65535).', mbError, MB_OK);
      Result := False;
    end;
  end;

  // Validate admin credentials
  if CurPageID = AdminPage.ID then
  begin
    Username := Trim(AdminUsernameEdit.Text);
    Email := Trim(AdminEmailEdit.Text);
    Password := AdminPasswordEdit.Text;
    PasswordConfirm := AdminPasswordConfirmEdit.Text;
    ErrorMsg := '';

    // Validate username
    if Length(Username) < 3 then
      ErrorMsg := 'Username must be at least 3 characters long.'
    else if Length(Username) > 50 then
      ErrorMsg := 'Username must be 50 characters or less.'
    // Validate email
    else if not IsValidEmail(Email) then
      ErrorMsg := 'Please enter a valid email address.'
    // Validate password
    else if Length(Password) < 8 then
      ErrorMsg := 'Password must be at least 8 characters long.'
    else if not HasUppercase(Password) then
      ErrorMsg := 'Password must contain at least one uppercase letter.'
    else if not HasLowercase(Password) then
      ErrorMsg := 'Password must contain at least one lowercase letter.'
    else if not HasDigit(Password) then
      ErrorMsg := 'Password must contain at least one number.'
    else if not HasSpecialChar(Password) then
      ErrorMsg := 'Password must contain at least one special character.'
    else if Password <> PasswordConfirm then
      ErrorMsg := 'Passwords do not match.';

    if ErrorMsg <> '' then
    begin
      MsgBox(ErrorMsg, mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function EscapeJsonString(const S: String): String;
var
  I: Integer;
  C: Char;
begin
  Result := '';
  for I := 1 to Length(S) do
  begin
    C := S[I];
    // Escape special characters for JSON
    if C = '"' then
      Result := Result + '\"'
    else if C = #92 then  // backslash
      Result := Result + '\\'
    else if C = #8 then   // backspace
      Result := Result + '\b'
    else if C = #9 then   // tab
      Result := Result + '\t'
    else if C = #10 then  // newline
      Result := Result + '\n'
    else if C = #12 then  // form feed
      Result := Result + '\f'
    else if C = #13 then  // carriage return
      Result := Result + '\r'
    else
      Result := Result + C;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvFile, ConfigFile: String;
  ConfigContent: String;
begin
  // After installation, create configuration files
  if CurStep = ssPostInstall then
  begin
    // Create .env file with configured port
    EnvFile := ExpandConstant('{app}\.env');
    SaveStringToFile(EnvFile,
      'FLASK_ENV=production' + #13#10 +
      'PORT=' + PortPage.Values[0] + #13#10 +
      'SECRET_KEY=' + GetDateTimeString('yyyymmddhhnnss', #0, #0) + '-simply-ai-home' + #13#10,
      False);

    // Create first-run config file with admin credentials
    ConfigFile := ExpandConstant('{app}\first_run_config.json');
    ConfigContent := '{' + #13#10 +
      '  "admin_username": "' + EscapeJsonString(Trim(AdminUsernameEdit.Text)) + '",' + #13#10 +
      '  "admin_email": "' + EscapeJsonString(Trim(AdminEmailEdit.Text)) + '",' + #13#10 +
      '  "admin_password": "' + EscapeJsonString(AdminPasswordEdit.Text) + '"' + #13#10 +
      '}';
    SaveStringToFile(ConfigFile, ConfigContent, False);
  end;
end;

// Check if the application is running before uninstall
function InitializeUninstall(): Boolean;
begin
  Result := True;
  // Could add check for running process here
end;
