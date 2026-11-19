**Read this in English: [English](https://github.com/PolatOzaslan21/tr2en/blob/main/README.en.md)**

# tr2en — Türkçe → İngilizce çeviri katmanı

**Yerel Türkçe İngilizce çeviri: metni seç, kısayola bas, İngilizcesi yerine gelsin.** Windows için küçük bir tepsi uygulaması. Yapay zekâya (Claude, ChatGPT, Copilot…) İngilizce prompt yazmak, internetsiz çeviri ya da hızlı prompt çevirme için.

> **Durum: 0.1 Beta.** Yeni ve erken bir sürüm; eksikler ve hatalar olabilir. Sorun görürseniz [issue açın](https://github.com/PolatOzaslan21/tr2en/issues).

## Ne yapar?

1. Herhangi bir uygulamada Türkçe metni seçin.
2. **Ctrl+Shift+Space**'e basın.
3. Seçili metin İngilizcesiyle değişir. Panonuz (kopyaladığınız metin, resim, dosya) eski haline geri yüklenir.

Üç çevirmen seçeneği var (tepsi simgesinden değiştirilir):

| Çevirmen | Ne zaman | Gizlilik |
|---|---|---|
| **Gemini** (Google, kendi ücretsiz API anahtarınız) | Önerilen, en iyi kalite | Metin Google'a gider |
| **Kendi modeliniz** (OpenAI uyumlu her API ya da Ollama / LM Studio) | Başka bir servis ya da kendi bilgisayarınızdaki model | Servise göre; Ollama'da metin bilgisayardan çıkmaz |
| **Yerel model** (~230 MB, ilk açılışta bir kez iner) | Diğerleri yoksa / yanıt vermezse yedek, ya da "Yalnızca yerel" seçiliyse | Metin bilgisayardan çıkmaz |

İlk açılışta hangisini kullanmak istediğiniz sorulur.

## Korumalar

- **Kod, URL ve dosya yolları** çeviriye girmez, aynen kalır (`src/main.py`, `https://…`, `` `komut` ``).
- **Olumsuzluk kontrolü:** "silme", "silmemiş", "-madan önce" gibi olumsuzluklar çeviride kaybolursa çeviri yapıştırılmaz, uyarı çıkar. (Bilinen sınır: olumsuzluğun başka kelimeye kaymasını — "yeni değil ama hızlı" → "new but not fast" — her zaman yakalayamaz.)
- **Zaten İngilizce** olan metin ya da cümleler olduğu gibi bırakılır.
- Yapay zekânın kesik, boş ya da "Sure, here is…" gibi açıklamalı yanıtları reddedilir; yerel modele geçilir.
- Parola yöneticilerinde (KeePass, 1Password, Bitwarden) çalışmaz.

## Gizlilik

- Çevrilen metin **hiçbir yere kaydedilmez**. Tepsideki "Son işlemler" yalnızca saat, süre ve karakter sayısını gösterir.
- Klavye kancası yalnızca kısayolu tanımak için kullanılır; tuşlar kaydedilmez.
- Gemini seçiliyse metin Google'a gönderilir; **ücretsiz katmanda Google bu metinleri ürünlerini geliştirmek için kullanabilir.** Hassas metinler için "Yalnızca yerel" seçin.
- API anahtarları yalnızca istek başlığında gider, hiçbir dosyaya ya da log'a yazılmaz.
- "Kendi modelim" seçiliyse metin yalnızca ayarlarda yazdığınız adrese gider.
- tr2en'in kendiliğinden yaptığı tek ağ bağlantısı, yerel model yoksa ilk açılışta modelin Hugging Face'ten (huggingface.co) indirilmesidir. Telemetri ya da kullanım istatistiği yoktur. Güncelleme denetimi yalnızca siz "Güncellemeleri kontrol et"e bastığınızda yapılır (GitHub'a sorulur).

## Kurulum

### Kolay yol: kurulum dosyası (Windows 10/11)

1. [Son sürüm](https://github.com/PolatOzaslan21/tr2en/releases/latest) sayfasından `tr2en-…-windows-x64-kurulum.exe` dosyasını indirip çalıştırın (~38 MB). Python ve yönetici izni gerekmez.
2. Kurulum, Başlat menüsüne **tr2en** kısayolu ekler; isterseniz masaüstü kısayolu ve "Windows açılışında başlat" kutucuklarını da işaretleyin.
3. Saatin yanında kırmızı/mavi **TR → EN** balon simgesi çıkar. Simge önce saatin yanındaki **^** (gizli simgeler) menüsünde görünebilir; sürekli görünsün isterseniz oradan görev çubuğuna sürükleyin. Uygulamayı kapattıysanız Başlat menüsünde "tr2en" yazıp yeniden açabilirsiniz.

- .exe henüz dijital imzalı değil; Windows "bilgisayarınızı korudu" (SmartScreen) uyarısı verirse **Ek bilgi → Yine de çalıştır**'a tıklayın. İndirdiğiniz dosyanın doğruluğunu sürümdeki `.sha256` dosyasıyla kontrol edebilirsiniz.
- **Güncellemek için:** yeni kurulum dosyasını çalıştırmanız yeterli; açıksa tr2en'i kendisi kapatır, ayarlarınız ve model korunur.
- **Kaldırmak için:** Ayarlar → Uygulamalar → tr2en → Kaldır. Ayarlarınızın ve indirilen modelin de silinmesini isteyip istemediğiniz sorulur.
- **Kurulum istemiyorsanız (taşınabilir):** `tr2en-…-windows-x64.zip`'i kalıcı bir klasöre çıkarıp `tr2en.exe`'yi çalıştırın. Güncellerken önce tepsiden **Çıkış** yapıp yeni zip'i aynı klasöre çıkarın.

### Geliştiriciler için: uv ile

[PyPI](https://pypi.org/project/tr2en/)'den, [uv](https://docs.astral.sh/uv/) ile:

```powershell
uv tool install "tr2en[uygulama,yerel]"
tr2en
```

(`pip install "tr2en[uygulama,yerel]"` da olur; Python ≥ 3.11.)

Kaynaktan çalıştırmak için: depoyu klonlayın, `baslat-arkaplan.cmd` (konsolsuz) ya da `baslat.cmd` (konsollu, hata ayıklama) dosyasını çalıştırın.

### Gemini anahtarı (ücretsiz, önerilen)

1. https://aistudio.google.com/apikey adresinde **Create API key** ile anahtar oluşturun ve kopyalayın.
2. PowerShell'de aşağıdakini çalıştırın (panodaki anahtarı kullanıcı ortam değişkenine kaydeder, ekrana yazmaz):

```powershell
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', (Get-Clipboard).Trim(), 'User')
```

3. tr2en'i yeniden başlatın. Anahtar yoksa yalnızca yerel model kullanılır.

Ücretsiz katman (Kasım 2026): Gemini 3.5 Flash-Lite için dakikada 15, günde 500 istek.

### Kendi modelinizi kullanın (isteğe bağlı)

Gemini **önerilen** seçenek, ama zorunlu değil. OpenAI uyumlu API sunan her servisi ya da bilgisayarınızdaki bir modeli bağlayabilirsiniz. `ayarlar.toml`'da dört satırı doldurun, sonra tepsiden **Çevirmen → Kendi modelim**'i seçin:

| Servis | `uyumlu_adres` | `uyumlu_model` (örnek) | `uyumlu_anahtar_degiskeni` |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| OpenRouter (yüzlerce model) | `https://openrouter.ai/api/v1` | `google/gemini-2.5-flash` | `OPENROUTER_API_KEY` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| **Ollama** (yerel, ücretsiz) | `http://localhost:11434/v1` | `qwen3.5:0.8b`, `llama3.2` | *(boş bırakın)* |
| LM Studio (yerel) | `http://localhost:1234/v1` | yüklediğiniz model | *(boş bırakın)* |

- `uyumlu_anahtar_degiskeni` alanına anahtarın **kendisini değil**, kaydettiğiniz ortam değişkeninin **adını** yazın (yukarıdaki PowerShell komutunda `GEMINI_API_KEY` yerine o adı kullanın).
- Ollama'da düşünen modeller (qwen3 ailesi) için `uyumlu_dusunmeyi_kapat = true` yapın: 0,8B'lik qwen3.5'te çeviri 22 sn'den ~1 sn'ye iniyor.
- Yerel LLM'ler yavaşsa `uyumlu_zaman_asimi`'ni artırın (varsayılan 15 sn).
- Güvenlik için `http://` yalnızca kendi bilgisayarınızdaki (localhost) servislerde kabul edilir; uzak servisler `https://` olmalı.
- Korumalar (kod/URL koruma, olumsuzluk kontrolü) bu seçenekte de çalışır. Küçük modeller olumsuzluğu sık kaçırır; tr2en bu durumda çeviriyi yapıştırmaz.

## Ayarlar

Tepsi menüsü: etkinleştir/duraklat, çevirmen, kısayol (Ctrl+Shift+Space / Ctrl+Shift+Y ya da **Kendi kısayolum…**), son işlemler, son çeviriyi göster, son orijinali kopyala, Windows açılışında başlat.

**Kendi kısayolum…:** seçince 10 saniye içinde istediğiniz birleşime basın (ör. Ctrl+Shift+K; Esc vazgeçer). Ctrl ya da Alt gerekir. Kabul edilmeyenler: Ctrl+C/V/X/Z/Y/A/S (tr2en kopyala-yapıştırla çalışır), Alt+F4 ve Ctrl+Alt (Türkçe klavyede AltGr ile aynıdır, ₺ @ yazar). **Uyarı:** kendi kısayolunuz başka bir programın kısayoluyla çakışırsa o programda o işlem ya da tr2en düzgün çalışmayabilir; tek değiştiricili kısayollar (ör. Ctrl+Q) daha sık çakışır. Bilinen çakışmalarda tr2en uyarır. **Önerilen: varsayılan Ctrl+Shift+Space.**

Kısayol tuşu programa gitmez: metin seçiliyse tr2en çevirir; seçim yoksa tuşu programa geri gönderir (ör. kısayolunuz Ctrl+P ise, seçim yokken programın kendi Ctrl+P işi yine çalışır). tr2en duraklatıldığında ve terminalde tuş olduğu gibi programa gider.

Diğer her şey `%APPDATA%\tr2en\ayarlar.toml` dosyasında (tepsiden "Ayarlar dosyasını aç"): zaman aşımı, Gemini modeli, kendi modeliniz, yasaklı uygulamalar, sona boşluk. Değiştirdikten sonra uygulamayı yeniden başlatın.

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

Testler her push'ta GitHub Actions'ta Windows üzerinde çalışır. Kod üzerinde çalışan yapay zekâ ajanları için kurallar: [AGENTS.md](https://github.com/PolatOzaslan21/tr2en/blob/main/AGENTS.md). Kod içindeki adlar Türkçedir.

## Kod imzalama politikası (Code signing policy)

tr2en.exe ve kurulum dosyası **henüz dijital imzalı değil**; ücretsiz açık kaynak imzası için [SignPath Foundation](https://signpath.org/)'a başvuru planlanıyor. İmza geldiğinde:

- Dosyalar yalnızca bu depodaki kaynak koddan GitHub Actions ile derlenir; elle derlenmiş dosya imzalanmaz.
- Roller: yazar, inceleyici ve onaylayan: [PolatOzaslan21](https://github.com/PolatOzaslan21) (depo sahibi). Dışarıdan gelen her değişiklik (pull request) birleştirilmeden önce incelenir; her sürümün imzalanması elle onaylanır.
- Gizlilik: Bu program, kullanıcı ya da programı kuran/çalıştıran kişi özellikle istemedikçe başka ağ sistemlerine bilgi göndermez. Ayrıntılar: [Gizlilik](#gizlilik).

## Lisans

Kod **MIT**. İndirilen yerel model **CC-BY-4.0**: [Helsinki-NLP/opus-mt-tc-big-tr-en](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-tr-en) modelinin CTranslate2 int8 dönüştürmesi, [PolatOz/tr2en-model](https://huggingface.co/PolatOz/tr2en-model).
