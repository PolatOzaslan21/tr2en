# tr2en — Türkçe → İngilizce çeviri katmanı

**Yerel Türkçe İngilizce çeviri: metni seç, kısayola bas, İngilizcesi yerine gelsin.** Windows için küçük bir tepsi uygulaması. Yapay zekâya (Claude, ChatGPT, Copilot…) İngilizce prompt yazmak, internetsiz çeviri ya da hızlı prompt çevirme için.

*English summary at the bottom.*

## Ne yapar?

1. Herhangi bir uygulamada Türkçe metni seçin.
2. **Ctrl+Shift+Space**'e basın.
3. Seçili metin İngilizcesiyle değişir. Panonuz (kopyaladığınız metin, resim, dosya) eski haline geri yüklenir.

İki çevirmen kullanır:

| Çevirmen | Ne zaman | Gizlilik |
|---|---|---|
| **Gemini** (Google, kendi ücretsiz API anahtarınız) | Varsayılan, en iyi kalite | Metin Google'a gider |
| **Yerel model** (~230 MB, ilk açılışta bir kez iner) | Gemini yoksa / yanıt vermezse, ya da "Yalnızca yerel" seçiliyse | Metin bilgisayardan çıkmaz |

İlk açılışta hangisini kullanmak istediğiniz sorulur; sonra tepsi simgesinden değiştirebilirsiniz.

## Korumalar

- **Kod, URL ve dosya yolları** çeviriye girmez, aynen kalır (`src/main.py`, `https://…`, `` `komut` ``).
- **Olumsuzluk kontrolü:** "silme", "silmemiş", "-madan önce" gibi olumsuzluklar çeviride kaybolursa çeviri yapıştırılmaz, uyarı çıkar. (Bilinen sınır: olumsuzluğun başka kelimeye kaymasını — "yeni değil ama hızlı" → "new but not fast" — her zaman yakalayamaz.)
- **Zaten İngilizce** olan metin ya da cümleler olduğu gibi bırakılır.
- Gemini'nin kesik, boş ya da "Sure, here is…" gibi açıklamalı yanıtları reddedilir; yerel modele geçilir.
- Parola yöneticilerinde (KeePass, 1Password, Bitwarden) çalışmaz.

## Gizlilik

- Çevrilen metin **hiçbir yere kaydedilmez**. Tepsideki "Son işlemler" yalnızca saat, süre ve karakter sayısını gösterir.
- Klavye kancası yalnızca kısayolu tanımak için kullanılır; tuşlar kaydedilmez.
- Gemini seçiliyse metin Google'a gönderilir; **ücretsiz katmanda Google bu metinleri ürünlerini geliştirmek için kullanabilir.** Hassas metinler için "Yalnızca yerel" seçin.
- Gemini anahtarı yalnızca istek başlığında gider, hiçbir dosyaya ya da log'a yazılmaz.

## Kurulum

Gereken: Windows 10/11 ve [uv](https://docs.astral.sh/uv/).

```powershell
uv tool install "tr2en[uygulama,yerel] @ git+https://github.com/PolatOzaslan21/tr2en"
tr2en
```

Saatin yanında mavi **EN** simgesi çıkar. Tepsiden "Windows açılışında başlat"ı açabilirsiniz.

Kaynaktan çalıştırmak için: depoyu klonlayın, `baslat-arkaplan.cmd` (konsolsuz) ya da `baslat.cmd` (konsollu, hata ayıklama) dosyasını çalıştırın.

### Gemini anahtarı (ücretsiz, isteğe bağlı)

1. https://aistudio.google.com/apikey adresinde **Create API key** ile anahtar oluşturun ve kopyalayın.
2. PowerShell'de aşağıdakini çalıştırın (panodaki anahtarı kullanıcı ortam değişkenine kaydeder, ekrana yazmaz):

```powershell
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', (Get-Clipboard).Trim(), 'User')
```

3. tr2en'i yeniden başlatın. Anahtar yoksa yalnızca yerel model kullanılır.

Ücretsiz katman (Kasım 2026): Gemini 3.5 Flash-Lite için dakikada 15, günde 500 istek.

## Ayarlar

Tepsi menüsü: etkinleştir/duraklat, çevirmen, kısayol (Ctrl+Shift+Space / Ctrl+Shift+Y / Ctrl+Shift+T), son işlemler, son çeviriyi göster, son orijinali kopyala, Windows açılışında başlat.

Diğer her şey `%APPDATA%\tr2en\ayarlar.toml` dosyasında (tepsiden "Ayarlar dosyasını aç"): zaman aşımı, Gemini modeli, yasaklı uygulamalar, sona boşluk. Değiştirdikten sonra uygulamayı yeniden başlatın.

## Ölçümler (19.11.2026, Windows 11)

| Durum | Bellek (RAM) |
|---|---|
| Boşta (kanca + tepsi, Gemini ile) | ~35–50 MB |
| Yerel model yüklü | ~300 MB (yüklenirken anlık tepe ~450 MB) |

| Çeviri | Süre |
|---|---|
| Yerel model, cümle başına | 0,1–0,6 sn |
| Gemini | genelde ~1 sn; yoğun saatlerde 4 sn'yi geçerse yerel modele düşülür |

Yerel model yalnızca gerektiğinde yüklenir; yalnızca Gemini kullanıyorsanız ~50 MB'ta kalır.

## Token notu (dürüst haliyle)

Türkçe bir mesaj İngilizceye çevrilince **mesajın kendisi** %10–36 daha az token tutar (10 gerçek mesajla ölçüldü; o200k sayacında %10, cl100k'de %36). Ama Claude Code gibi araçlarda bir isteğin çoğu zaten İngilizce (kod, araç çıktıları, sistem talimatı); kullanıcı mesajı toplamın %1'inden azdır. Yani **faturanızı belirgin düşürmez.** Asıl fayda: modellerin İngilizce prompt'u daha iyi anlaması — özellikle küçük ve yerel modellerde.

## Antivirüs uyarısı

tr2en kısayolu yakalamak için klavye kancası kullanır. Bazı antivirüsler bu davranışı şüpheli bulabilir. Kod açık; kanca yalnızca kısayolu tanır, hiçbir tuşu kaydetmez ya da göndermez.

## Bilinen sınırlar

- **Terminalde çalışmaz** (Windows Terminal, cmd, PowerShell): seçili metin terminalde değiştirilemiyor. Sonraki sürümde kısayolla açılan bir yazma kutusu gelecek.
- Yerel model uzun ve dağınık metinde zayıftır ("tablo" → "painting" gibi); kritik metinde Gemini kullanın ya da sonucu kontrol edin.
- Şimdilik yalnızca Türkçe → İngilizce.

## Geliştirme

```powershell
uv run --extra test --extra yerel --extra uygulama pytest -q
```

Kod denetimi raporu ve tasarım notları proje klasöründe. Lisans: kod **MIT**; indirilen model **CC-BY-4.0** ([Helsinki-NLP/opus-mt-tc-big-tr-en](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-tr-en) dönüştürmesi, [PolatOz/tr2en-model](https://huggingface.co/PolatOz/tr2en-model)).

---

## English

**tr2en** is a small Windows tray app for Turkish → English translation: select Turkish text anywhere, press **Ctrl+Shift+Space**, and the selection is replaced with its English translation. Your clipboard is restored afterwards.

- Translators: Google **Gemini** (your own free API key, `GEMINI_API_KEY`) with an **offline fallback model** (CTranslate2 int8 conversion of Helsinki-NLP opus-mt-tc-big-tr-en, ~230 MB, downloaded once from Hugging Face and SHA256-verified). "Local only" mode keeps text on your machine.
- Safety checks: code/URLs/paths are never translated, lost negations block the paste, truncated or chatty LLM replies are rejected.
- Privacy: translated text is never logged; the keyboard hook only detects the hotkey.
- RAM: ~50 MB idle, ~300 MB with the offline model loaded.
- Install: `uv tool install "tr2en[uygulama,yerel] @ git+https://github.com/PolatOzaslan21/tr2en"`, then run `tr2en`.
- Does not work inside terminals yet. Code: MIT. Model: CC-BY-4.0.
