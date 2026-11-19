; tr2en kurulum dosyası (Inno Setup 6). derle.ps1 çağırır:
;   ISCC.exe /DSurum=v0.1.3 /DKaynak=<dist\tr2en> /DCikti=<dist> paketleme\tr2en.iss
; Yönetici izni istemez; yalnızca o kullanıcıya %LOCALAPPDATA%\Programs\tr2en altına kurar.
; Ayarlar (%APPDATA%\tr2en) ve model (%LOCALAPPDATA%\tr2en) kurulum klasörünün dışındadır;
; güncellemede korunur, kaldırırken yalnızca kullanıcı "Evet" derse silinir.

#ifndef Surum
  #define Surum "yerel"
#endif
#ifndef Kaynak
  #error "Kaynak (PyInstaller çıktısı dist\tr2en) verilmedi"
#endif
#ifndef Cikti
  #define Cikti "."
#endif

; Sürüm numarası: "v0.1.3" -> "0.1.3"; sayı değilse 0.0.0
#define SurumNo (Copy(Surum, 1, 1) == "v" ? Copy(Surum, 2, 100) : "0.0.0")

[Setup]
; AppId sabit kalmalı: güncellemeler aynı kaydın üstüne kurulur.
AppId={{6B0E2C4A-7D1F-4C3B-9E2A-5F8D1A7C3E21}
AppName=tr2en
AppVersion={#SurumNo}
AppVerName=tr2en {#Surum}
VersionInfoVersion={#SurumNo}
VersionInfoProductName=tr2en
VersionInfoProductVersion={#SurumNo}
VersionInfoDescription=tr2en kurulumu
VersionInfoCompany=PolatOzaslan21
VersionInfoCopyright=MIT Lisansı
AppPublisher=PolatOzaslan21
AppPublisherURL=https://github.com/PolatOzaslan21/tr2en
AppSupportURL=https://github.com/PolatOzaslan21/tr2en/issues
AppUpdatesURL=https://github.com/PolatOzaslan21/tr2en/releases
DefaultDirName={userpf}\tr2en
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Cikti}
OutputBaseFilename=tr2en-{#Surum}-windows-x64-kurulum
SetupIconFile=tr2en.ico
UninstallDisplayIcon={app}\tr2en.exe
UninstallDisplayName=tr2en
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
tr.MasaustuKisayolu=Masaüstüne kısayol oluştur
en.MasaustuKisayolu=Create a desktop shortcut
tr.OtomatikBaslat=Windows açılışında başlat
en.OtomatikBaslat=Start with Windows
tr.EkGorevler=Ek seçenekler:
en.EkGorevler=Additional options:
tr.SimdiBaslat=tr2en'i şimdi başlat
en.SimdiBaslat=Start tr2en now
tr.VeriSilinsinMi=Ayarlarınız ve indirilen çeviri modeli de silinsin mi?%n%n(Hayır derseniz tr2en'i yeniden kurduğunuzda model tekrar indirilmez.)
en.VeriSilinsinMi=Also delete your settings and the downloaded translation model?%n%n(Choose No to keep them for a later reinstall.)

[Tasks]
Name: "masaustu"; Description: "{cm:MasaustuKisayolu}"; GroupDescription: "{cm:EkGorevler}"; Flags: unchecked
Name: "otomatik"; Description: "{cm:OtomatikBaslat}"; GroupDescription: "{cm:EkGorevler}"

[Files]
Source: "{#Kaynak}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Güncellemede eski sürümün kalıntı kütüphaneleri karışmasın.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\tr2en"; Filename: "{app}\tr2en.exe"
Name: "{autodesktop}\tr2en"; Filename: "{app}\tr2en.exe"; Tasks: masaustu

[Registry]
; Uygulamanın kendi "Windows açılışında başlat" seçeneğiyle aynı değer (otomatik_baslat.py).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "tr2en"; ValueData: """{app}\tr2en.exe"" --arka"; Tasks: otomatik

[Run]
Filename: "{app}\tr2en.exe"; Description: "{cm:SimdiBaslat}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Tepsi uygulamasının penceresi yok; kapanma isteğine cevap vermez, durdurmak gerekir.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM tr2en.exe"; Flags: runhidden; RunOnceId: "tr2en-durdur"

[Code]
procedure CalisaniDurdur();
var
  Sonuc: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM tr2en.exe', '', SW_HIDE, ewWaitUntilTerminated, Sonuc);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CalisaniDurdur();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Tepsiden açılmış olsa bile açılış kaydı kalmasın.
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'tr2en');
    if (not UninstallSilent) and
       (MsgBox(CustomMessage('VeriSilinsinMi'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{userappdata}\tr2en'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\tr2en'), True, True, True);
    end;
  end;
end;
