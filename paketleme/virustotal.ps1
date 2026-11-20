# tr2en — VirusTotal taraması ve sürüm notuna sonuç ekleme.
#
# Kullanım (GitHub Actions, sürüm etiketi):
#   ./paketleme/virustotal.ps1 -Dosyalar "dist/*-kurulum.exe", "dist/*.zip" -Surum $env:SURUM [-Bekle 15]
#
# - API anahtarı YALNIZCA ortam değişkeninden okunur (VT_API_KEY). Anahtar hiçbir
#   çıktıda, günlükte ya da hata mesajında görünmez.
# - Anahtar yoksa tarama atlanır (exit 0). Ağ hatası/zaman aşımı uyarı yazar (exit 0).
#   Böylece sürüm yayını hiçbir koşulda bozmaz.
param(
    [string[]]$Dosyalar = @(),
    [string]$Surum = "",
    [int]$Bekle = 20
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$VtKok = "https://www.virustotal.com/api/v3"
$AzamiYukBoyut = 32MB
$AnketAraligiSn = 20
$DakikaBazinaIstek = 4
$UyariSatiri = "tr2en kısayol için klavye kancası kullanır; bazı antivirüsler bunu şüpheli bulabilir. Kod açıktır."
$script:IstekZamanlari = [System.Collections.Generic.List[datetime]]::new()
$script:VtBasliklar = @{}

# ---- yardımcılar ----

function Guvenli-Metin {
    # Anahtar bir hata mesajına sızmasın.
    param([string]$Metin)
    if ([string]::IsNullOrEmpty($Metin)) { return "" }
    $k = $env:VT_API_KEY
    if ($k) { return $Metin.Replace($k, "***") }
    return $Metin
}

function VT-Izin-Al {
    # Ücretsiz kota: dakikada en fazla 4 istek. Zaman damgalarını tut, gerekirse bekle.
    $simdi = Get-Date
    foreach ($t in @($script:IstekZamanlari)) {
        if (($simdi - $t).TotalSeconds -ge 60) { [void]$script:IstekZamanlari.Remove($t) }
    }
    if ($script:IstekZamanlari.Count -ge $DakikaBazinaIstek) {
        $enEski = ($script:IstekZamanlari | Sort-Object | Select-Object -First 1)
        $bekleSn = 61 - [int][math]::Ceiling(((Get-Date) - $enEski).TotalSeconds)
        if ($bekleSn -gt 0) { Start-Sleep -Seconds $bekleSn }
        $simdi = Get-Date
        foreach ($t in @($script:IstekZamanlari)) {
            if (($simdi - $t).TotalSeconds -ge 60) { [void]$script:IstekZamanlari.Remove($t) }
        }
    }
    [void]$script:IstekZamanlari.Add((Get-Date))
}

function Sayi-Al {
    param($deger)
    if ($null -eq $deger) { return 0 }
    try { return [int]$deger } catch { return 0 }
}

function Dosya-Listesi {
    # Jokerli yolları genişletir (GitHub Actions'ta "dist/*.zip" literal gelir).
    param([string[]]$Girdiler)
    $liste = @()
    foreach ($g in $Girdiler) {
        if ([string]::IsNullOrWhiteSpace($g)) { continue }
        if ($g -match '[\*\?\[]') {
            foreach ($b in @(Get-ChildItem -Path $g -File -ErrorAction SilentlyContinue)) {
                $liste += $b.FullName
            }
        } elseif (Test-Path -LiteralPath $g -PathType Leaf) {
            $liste += (Resolve-Path -LiteralPath $g).Path
        } else {
            Write-Host "Dosya bulunamadı, atlandı: $g"
        }
    }
    return $liste
}

function VT-Cok-Parcali-Gonder {
    # Invoke-RestMethod -Form, VT'nin reddettiği biçim üretiyor ("Malformed multipart body":
    # tırnaklı boundary + filename*). Gövde burada elle, sade biçimde kurulur.
    param([string]$Adres, [System.IO.FileInfo]$Bilgi)
    Add-Type -AssemblyName System.Net.Http
    $sinir = "tr2en" + [guid]::NewGuid().ToString("N")
    $istemci = [System.Net.Http.HttpClient]::new()
    $istemci.Timeout = [TimeSpan]::FromMinutes(10)
    $akis = [System.IO.File]::OpenRead($Bilgi.FullName)
    try {
        $govde = [System.Net.Http.MultipartFormDataContent]::new($sinir)
        $govde.Headers.Remove("Content-Type") | Out-Null
        $govde.Headers.TryAddWithoutValidation("Content-Type", "multipart/form-data; boundary=$sinir") | Out-Null
        $parca = [System.Net.Http.StreamContent]::new($akis)
        $parca.Headers.TryAddWithoutValidation("Content-Disposition", "form-data; name=`"file`"; filename=`"$($Bilgi.Name)`"") | Out-Null
        $parca.Headers.TryAddWithoutValidation("Content-Type", "application/octet-stream") | Out-Null
        $govde.Add($parca)
        $istek = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, $Adres)
        foreach ($k in $script:VtBasliklar.Keys) { $istek.Headers.TryAddWithoutValidation($k, [string]$script:VtBasliklar[$k]) | Out-Null }
        $istek.Content = $govde
        $yanit = $istemci.SendAsync($istek).GetAwaiter().GetResult()
        $metin = $yanit.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $yanit.IsSuccessStatusCode) {
            throw "VT yükleme $([int]$yanit.StatusCode): $metin"
        }
        return ($metin | ConvertFrom-Json)
    } finally {
        $akis.Dispose()
        $istemci.Dispose()
    }
}

function VT-Dosya-Yukle {
    # Dosyayı yükler; analiz kimliğini döndürür. 32 MB üstü dosyalar için önce
    # upload_url alınır (VT'nin büyük dosya yolu).
    param([string]$Yol)
    $bilgi = Get-Item -LiteralPath $Yol
    if ($bilgi.Length -gt $AzamiYukBoyut) {
        VT-Izin-Al
        $yu = Invoke-RestMethod -Uri "$VtKok/files/upload_url" -Method Get -Headers $script:VtBasliklar
        $adres = $yu.data
        if ([string]::IsNullOrWhiteSpace($adres)) { throw "upload_url boş döndü" }
        VT-Izin-Al
        # VT belgesi: upload_url'ye POST da x-apikey başlığı ister.
        return (VT-Cok-Parcali-Gonder -Adres $adres -Bilgi $bilgi)
    }
    VT-Izin-Al
    return (VT-Cok-Parcali-Gonder -Adres "$VtKok/files" -Bilgi $bilgi)
}

function VT-Dosya-Raporu {
    # VT'de zaten bilinen dosya: istatistikler doğrudan rapordan alınır.
    param([string]$Kimlik)
    VT-Izin-Al
    $rapor = Invoke-RestMethod -Uri "$VtKok/files/$Kimlik" -Method Get -Headers $script:VtBasliklar
    return $rapor.data.last_analysis_stats
}

function Bolum-Yerine-Koy {
    # Sürüm notunda varsa "### VirusTotal" bölümünü değiştirir, yoksa sona ekler.
    param([string]$Metin, [string]$Bolum)
    $satirlar = @($Metin -split "`r?`n")
    $cikti = [System.Collections.Generic.List[string]]::new()
    $atlandi = $false
    foreach ($s in $satirlar) {
        if ($s -match '^###\s+VirusTotal\b') { $atlandi = $true; continue }
        if ($atlandi) {
            if ($s -match '^###\s') { $atlandi = $false } else { continue }
        }
        [void]$cikti.Add($s)
    }
    $goven = ($cikti -join "`n").TrimEnd()
    if ([string]::IsNullOrWhiteSpace($goven)) { return ($Bolum.Trim() + "`n") }
    return ($goven + "`n`n" + $Bolum.Trim() + "`n")
}

# ---- ana akış ----

$anahtar = $env:VT_API_KEY
if ([string]::IsNullOrWhiteSpace($anahtar)) {
    Write-Host "VT_API_KEY yok, tarama atlandı"
    exit 0
}
$script:VtBasliklar = @{ "x-apikey" = $anahtar }

try {
    $yollar = @(Dosya-Listesi $Dosyalar)
    if ($yollar.Count -eq 0) {
        Write-Host "Taranacak dosya yok, tarama atlandı"
        exit 0
    }

    # ---- dosyaları yükle ----
    $isler = @()
    $yuklenen = 0
    foreach ($yol in $yollar) {
        $sha = (Get-FileHash -LiteralPath $yol -Algorithm SHA256).Hash.ToLower()
        $is = [pscustomobject]@{
            yol        = $yol
            ad         = (Split-Path $yol -Leaf)
            sha        = $sha
            kimlik     = ""
            tur        = "analysis"
            bitti      = $true
            istatistik = $false
            zararli    = 0
            supheli    = 0
            tespit     = 0
            zararsiz   = 0
        }
        # Dosya VT'de zaten taranmışsa yeniden yükleme; mevcut raporu kullan
        # (ücretsiz kuyruk yavaş; elle yeniden çalıştırma sonucu böyle alır).
        try {
            $hazir = VT-Dosya-Raporu $sha
            $toplam = (Sayi-Al $hazir.malicious) + (Sayi-Al $hazir.suspicious) + (Sayi-Al $hazir.undetected) + (Sayi-Al $hazir.harmless)
            if ($toplam -gt 0) {
                Write-Host "Zaten taranmış, rapor kullanılıyor: $($is.ad)"
                $is.kimlik = $sha; $is.tur = "file"; $is.bitti = $false; $yuklenen++
                $isler += $is
                continue
            }
        } catch {
            # 404: VT bu dosyayı bilmiyor; yüklenecek. Başka hata ise görünsün (v0.2.0'da rapor okunamadı).
            Write-Host "Rapor okunamadı ($($is.ad)): $(Guvenli-Metin $_.Exception.Message)"
        }
        Write-Host "Yükleniyor: $($is.ad)"
        try {
            $cevap = VT-Dosya-Yukle $yol
            # Sonuç /analyses/<id> yerine dosya raporundan (/files/<sha256>) beklenir: v0.2.0'da analiz
            # durumu 15 dk boyunca "completed" görünmedi; dosya raporu ilk tarama bitince 404'ten çıkar.
            if (-not [string]::IsNullOrWhiteSpace($cevap.data.id)) { $is.kimlik = $sha; $is.tur = "file" }
            if (-not [string]::IsNullOrWhiteSpace($is.kimlik)) {
                $is.bitti = $false
                $yuklenen++
            } else {
                Write-Host "Analiz kimliği alınamadı: $($is.ad)"
            }
        } catch {
            Write-Host "Yükleme başarısız: $($is.ad) — $(Guvenli-Metin $_.Exception.Message)"
            # VT hata gövdesi (ör. {"error":{"code":...,"message":...}}); anahtar içermez, yine de süzülür.
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                Write-Host "  ayrıntı: $(Guvenli-Metin $_.ErrorDetails.Message)"
            }
            Write-Host "  adım: $($_.InvocationInfo.ScriptLineNumber). satır"
        }
        $isler += $is
    }
    if ($yuklenen -eq 0) {
        Write-Host "Hiçbir dosya yüklenemedi; sürüm notu değiştirilmedi"
        exit 0
    }

    # ---- analizleri bekle ----
    $son = (Get-Date).AddMinutes([math]::Max($Bekle, 1))
    while ($true) {
        $bekleyen = @($isler | Where-Object { -not $_.bitti })
        if ($bekleyen.Count -eq 0) { break }
        if ((Get-Date) -ge $son) {
            Write-Host "Bekleme süresi doldu; tarama sürüyor."
            break
        }
        foreach ($is in $bekleyen) {
            try {
                if ($is.tur -eq "file") {
                    $st = VT-Dosya-Raporu $is.kimlik
                    $toplamSt = (Sayi-Al $st.malicious) + (Sayi-Al $st.suspicious) + (Sayi-Al $st.undetected) + (Sayi-Al $st.harmless)
                    if ($toplamSt -eq 0) {
                        Write-Host "Analiz sürüyor: $($is.ad)"
                        continue
                    }
                } else {
                    VT-Izin-Al
                    $an = Invoke-RestMethod -Uri "$VtKok/analyses/$($is.kimlik)" -Method Get -Headers $script:VtBasliklar
                    if ($an.data.status -ne "completed") {
                        Write-Host "Analiz sürüyor: $($is.ad)"
                        continue
                    }
                    $st = $an.data.stats
                }
                $is.zararli = Sayi-Al $st.malicious
                $is.supheli = Sayi-Al $st.suspicious
                $is.tespit = Sayi-Al $st.undetected
                $is.zararsiz = Sayi-Al $st.harmless
                $is.istatistik = $true
                $is.bitti = $true
            } catch {
                # Analiz henüz hazır değil ya da geçici hata: süre dolana kadar yeniden dene.
                Write-Host "Analiz bekleniyor: $($is.ad) — $(Guvenli-Metin $_.Exception.Message)"
            }
        }
        if (@($isler | Where-Object { -not $_.bitti }).Count -eq 0) { break }
        Start-Sleep -Seconds $AnketAraligiSn
    }

    # ---- markdown bölümü ----
    $satirlar = @("### VirusTotal", "| Dosya | Sonuç | Bağlantı |", "| --- | --- | --- |")
    foreach ($is in $isler) {
        $baglanti = "https://www.virustotal.com/gui/file/$($is.sha)"
        if ($is.istatistik) {
            $toplam = $is.zararli + $is.supheli + $is.tespit + $is.zararsiz
            $sonuc = "$($is.zararli) / $toplam motor zararlı buldu"
            if ($is.supheli -gt 0) { $sonuc += " ($($is.supheli) şüpheli)" }
        } else {
            $sonuc = "tarama sürüyor, bağlantıdan bakın"
        }
        $satirlar += "| $($is.ad) | $sonuc | [rapor]($baglanti) |"
    }
    $satirlar += ""
    $satirlar += $UyariSatiri
    $bolum = ($satirlar -join "`n")

    Write-Host ""
    Write-Host $bolum
    Write-Host ""

    # Polat (21.11.2026): tek bir motor bile (ör. 1/69 ML yanlış alarmı) zararlı/şüpheli derse ya da
    # tarama bitmediyse sürüm notuna YAZILMAZ — temiz uygulama hakkında yanlış izlenim yaratmasın.
    # Sonuç yalnızca bu günlükte kalır; yanlış alarmı ilgili firmaya bildirip yeniden çalıştırın.
    $bitmeyen = @($isler | Where-Object { -not $_.istatistik })
    $tespitli = @($isler | Where-Object { $_.istatistik -and ($_.zararli + $_.supheli) -gt 0 })
    if ($bitmeyen.Count -gt 0 -or $tespitli.Count -gt 0) {
        foreach ($is in $tespitli) {
            Write-Host "Tespit var, sürüm notuna eklenmedi: $($is.ad) ($($is.zararli) zararlı, $($is.supheli) şüpheli) https://www.virustotal.com/gui/file/$($is.sha)/detection"
        }
        foreach ($is in $bitmeyen) {
            Write-Host "Tarama bitmedi, sürüm notuna eklenmedi: $($is.ad)"
        }
        exit 0
    }

    # ---- sürüm notu ----
    if ([string]::IsNullOrWhiteSpace($Surum)) {
        Write-Host "Sürüm verilmedi; sürüm notu güncellenmedi"
        exit 0
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Host "gh bulunamadı; sürüm notu güncellenmedi"
        exit 0
    }

    $hataDosya = [IO.Path]::GetTempFileName()
    $gecici = [IO.Path]::GetTempFileName()
    try {
        $mevcut = (& gh release view $Surum --json body -q .body 2> $hataDosya) -join "`n"
        $kod = $LASTEXITCODE
        if ($kod -ne 0) {
            $neden = (Get-Content -LiteralPath $hataDosya -Raw -ErrorAction SilentlyContinue)
            Write-Host "Sürüm notu okunamadı ($kod): $(Guvenli-Metin $neden)"
            exit 0
        }
        $yeniNot = Bolum-Yerine-Koy $mevcut $bolum
        Set-Content -LiteralPath $gecici -Value $yeniNot -Encoding utf8
        & gh release edit $Surum --notes-file $gecici 2> $hataDosya
        if ($LASTEXITCODE -ne 0) {
            $neden = (Get-Content -LiteralPath $hataDosya -Raw -ErrorAction SilentlyContinue)
            Write-Host "Sürüm notu güncellenemedi: $(Guvenli-Metin $neden)"
            exit 0
        }
        Write-Host "Sürüm notu güncellendi: $Surum"
    } finally {
        Remove-Item -LiteralPath $hataDosya -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $gecici -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "VirusTotal uyarısı: $(Guvenli-Metin $_.Exception.Message)"
    exit 0
}
exit 0
