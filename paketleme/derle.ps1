# tr2en.exe derleme (PyInstaller, tek klasör, konsolsuz). Hem yerelde hem GitHub Actions'ta kullanılır.
# Kullanım: powershell -File paketleme\derle.ps1 [-Cikti dist] [-Surum v0.1.0-beta]
# Çıktı: <Cikti>\tr2en\tr2en.exe ve <Cikti>\tr2en-<Surum>-windows-x64.zip (+ .sha256)
param(
    [string]$Cikti = "dist",
    [string]$Surum = "yerel"
)
$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
Set-Location $kok
$is = Join-Path $env:TEMP "tr2en-derleme"
$Cikti = [IO.Path]::GetFullPath((Join-Path $kok $Cikti))

uv run --extra yerel --extra uygulama --with "pyinstaller==6.22.3" pyinstaller `
    (Join-Path $PSScriptRoot "giris.py") `
    --name tr2en --noconsole --onedir --noconfirm --clean `
    --icon (Join-Path $PSScriptRoot "tr2en.ico") `
    --collect-data ceviri_katmani `
    --hidden-import pystray._win32 `
    --hidden-import pynput.keyboard._win32 `
    --hidden-import pynput.mouse._win32 `
    --distpath $Cikti --workpath (Join-Path $is "build") --specpath $is `
    --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız ($LASTEXITCODE)" }

$klasor = Join-Path $Cikti "tr2en"
if (-not (Test-Path (Join-Path $klasor "tr2en.exe"))) { throw "tr2en.exe oluşmadı" }
if (-not (Test-Path (Join-Path $klasor "_internal\ceviri_katmani\cekirdek\sozluk.tsv"))) { throw "sozluk.tsv pakete girmedi" }

$zip = Join-Path $Cikti "tr2en-$Surum-windows-x64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path $klasor -DestinationPath $zip
$ozet = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$ozet  $(Split-Path $zip -Leaf)" | Set-Content "$zip.sha256" -Encoding ascii
"klasör: {0:N0} MB, zip: {1:N0} MB" -f ((Get-ChildItem $klasor -Recurse | Measure-Object Length -Sum).Sum / 1MB), ((Get-Item $zip).Length / 1MB)
$zip
