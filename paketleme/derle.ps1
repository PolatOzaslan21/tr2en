# tr2en.exe derleme (PyInstaller, tek klasör, konsolsuz). Hem yerelde hem GitHub Actions'ta kullanılır.
# Kullanım: powershell -File paketleme\derle.ps1 [-Cikti dist] [-Surum v0.1.0-beta]
# Çıktı: <Cikti>\tr2en\tr2en.exe , <Cikti>\tr2en-<Surum>-windows-x64.zip
#        ve Inno Setup varsa <Cikti>\tr2en-<Surum>-windows-x64-kurulum.exe (her birine .sha256)
# -KurulumZorunlu: Inno Setup bulunamazsa hata ver (CI'da kullanılır).
param(
    [string]$Cikti = "dist",
    [string]$Surum = "yerel",
    [switch]$KurulumZorunlu
)
$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
Set-Location $kok
$is = Join-Path $env:TEMP "tr2en-derleme"
$Cikti = [IO.Path]::GetFullPath((Join-Path $kok $Cikti))

uv run --extra uygulama python (Join-Path $PSScriptRoot "simge_olustur.py")
if ($LASTEXITCODE -ne 0) { throw "simge üretilemedi" }

$surumDosyasi = Join-Path $is "surum_bilgisi.txt"
New-Item -ItemType Directory -Force $is | Out-Null
uv run --extra uygulama python (Join-Path $PSScriptRoot "surum_bilgisi.py") $surumDosyasi
if ($LASTEXITCODE -ne 0) { throw "sürüm bilgisi üretilemedi" }

uv run --extra yerel --extra uygulama --with "pyinstaller==6.22.3" pyinstaller `
    (Join-Path $PSScriptRoot "giris.py") `
    --name tr2en --noconsole --onedir --noconfirm --clean `
    --icon (Join-Path $PSScriptRoot "tr2en.ico") `
    --version-file $surumDosyasi `
    --collect-data ceviri_katmani `
    --hidden-import pystray._win32 `
    --hidden-import pynput.keyboard._win32 `
    --hidden-import pynput.mouse._win32 `
    --collect-data webview `
    --collect-binaries webview `
    --hidden-import webview.platforms.edgechromium `
    --hidden-import webview.platforms.winforms `
    --collect-all clr_loader `
    --collect-all pythonnet `
    --hidden-import clr `
    --hidden-import keyring.backends.Windows `
    --copy-metadata keyring `
    --hidden-import win32pipe `
    --hidden-import win32file `
    --hidden-import win32event `
    --distpath $Cikti --workpath (Join-Path $is "build") --specpath $is `
    --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız ($LASTEXITCODE)" }

$klasor = Join-Path $Cikti "tr2en"
if (-not (Test-Path (Join-Path $klasor "tr2en.exe"))) { throw "tr2en.exe oluşmadı" }
if (-not (Test-Path (Join-Path $klasor "_internal\ceviri_katmani\cekirdek\sozluk.tsv"))) { throw "sozluk.tsv pakete girmedi" }
if (-not (Test-Path (Join-Path $klasor "_internal\ceviri_katmani\uygulama\arayuz\ayarlar.html"))) { throw "ayarlar.html pakete girmedi" }
$webviewDll = Get-ChildItem -Path $klasor -Recurse -Filter "Microsoft.Web.WebView2*.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $webviewDll) { throw "webview (WebView2) DLL'leri pakete girmedi" }
$runtimeDll = Get-ChildItem -Path $klasor -Recurse -Filter "Python.Runtime.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $runtimeDll) { throw "Python.Runtime.dll (pythonnet) pakete girmedi" }

$zip = Join-Path $Cikti "tr2en-$Surum-windows-x64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path $klasor -DestinationPath $zip
function Ozet-Yaz([string]$dosya) {
    # Get-FileHash yerine .NET: makinenin PSModulePath ayarı bozuksa da çalışır.
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $ozet = ([BitConverter]::ToString($sha.ComputeHash([System.IO.File]::ReadAllBytes($dosya)))).Replace("-", "").ToLower()
    } finally {
        $sha.Dispose()
    }
    "$ozet  $(Split-Path $dosya -Leaf)" | Set-Content "$dosya.sha256" -Encoding ascii
}
Ozet-Yaz $zip
"klasör: {0:N0} MB, zip: {1:N0} MB" -f ((Get-ChildItem $klasor -Recurse | Measure-Object Length -Sum).Sum / 1MB), ((Get-Item $zip).Length / 1MB)
$zip

# Kurulum dosyası (Inno Setup 6)
$iscc = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    if ($KurulumZorunlu) { throw "Inno Setup 6 (ISCC.exe) bulunamadı" }
    "Inno Setup bulunamadı; kurulum dosyası atlandı (yalnızca zip)."
    return
}
& $iscc /Q "/DSurum=$Surum" "/DKaynak=$klasor" "/DCikti=$Cikti" (Join-Path $PSScriptRoot "tr2en.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız ($LASTEXITCODE)" }
$kurulum = Join-Path $Cikti "tr2en-$Surum-windows-x64-kurulum.exe"
if (-not (Test-Path $kurulum)) { throw "kurulum dosyası oluşmadı" }
Ozet-Yaz $kurulum
"kurulum: {0:N0} MB" -f ((Get-Item $kurulum).Length / 1MB)
$kurulum
