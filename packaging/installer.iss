#ifndef AHuaCcVersion
  #define AHuaCcVersion "0.1.0"
#endif
#ifndef AHuaCcBundle
  #error "Indica la carpeta que contiene Xandar.exe y _internal con /DAHuaCcBundle."
#endif

[Setup]
AppId={{8B271ED4-F871-4F1A-AB99-D87C975D532B}
AppName=Xandar · ASUS2
AppVersion={#AHuaCcVersion}
AppPublisher=Proyecto ASUS2
AppPublisherURL=https://github.com/alexanderhuahuacccapacc/APP-QUECHUA
DefaultDirName={localappdata}\Programs\ASUS2
DefaultGroupName=ASUS2
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=..\dist
OutputBaseFilename=InstalarASUS2-{#AHuaCcVersion}-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#AHuaCcBundle}\Xandar.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AHuaCcBundle}\_internal\*"; DestDir: "{app}\_internal"; Excludes: ".env,.env.*,.release-keys\*,*.key,*.pfx,*.p12,*.safetensors,*.pt,*.ckpt"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Xandar · ASUS2"; Filename: "{app}\Xandar.exe"; Parameters: "--asus2 ""{code:AHuaCcModelPath}"""; WorkingDir: "{app}"

[Run]
Filename: "{app}\Xandar.exe"; Parameters: "--asus2 ""{code:AHuaCcModelPath}"""; WorkingDir: "{app}"; Description: "Abrir Xandar · ASUS2"; Flags: nowait postinstall skipifsilent; Check: AHuaCcModelAvailable

[Code]
var
  AHuaCcModelPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  AHuaCcModelPage := CreateInputDirPage(wpSelectDir, 'Modelo local de ASUS2',
    'Selecciona la carpeta del paquete completo',
    'El paquete debe contener model_index.json y los pesos de voz y traducción. Si todavía no lo tienes, conserva la ruta propuesta y copia el paquete en ella cuando esté disponible.',
    False, '');
  AHuaCcModelPage.Add('Carpeta del modelo');
  AHuaCcModelPage.Values[0] := ExpandConstant('{param:MODELDIR|}');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = AHuaCcModelPage.ID) and (AHuaCcModelPage.Values[0] = '') then
    AHuaCcModelPage.Values[0] := AddBackslash(WizardDirValue) + 'ASUS2';
end;

function AHuaCcModelPath(AHuaCcParameter: String): String;
begin
  Result := AHuaCcModelPage.Values[0];
  if Result = '' then
    Result := AddBackslash(WizardDirValue) + 'ASUS2';
end;

function AHuaCcModelAvailable: Boolean;
var
  AHuaCcDirectory: String;
begin
  AHuaCcDirectory := AddBackslash(AHuaCcModelPath(''));
  Result := FileExists(AHuaCcDirectory + 'model_index.json') and
    FileExists(AHuaCcDirectory + 'speech\model.safetensors') and
    FileExists(AHuaCcDirectory + 'translation\model.safetensors');
end;
