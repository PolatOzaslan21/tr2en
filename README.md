**Read this in English: [English](https://github.com/PolatOzaslan21/tr2en/blob/main/README.en.md)**

# tr2en — Türkçe → İngilizce çeviri katmanı

**Yerel Türkçe İngilizce çeviri: metni seç, kısayola bas, İngilizcesi yerine gelsin.** Windows için küçük bir tepsi ve pencere uygulaması. Yapay zekâya (Claude, ChatGPT, Copilot…) İngilizce prompt yazmak, internetsiz çeviri ya da hızlı prompt çevirme için.

> **Durum: 0.2 Beta.** Yeni bir sürüm; eksikler ve hatalar olabilir. Sorun görürseniz [issue açın](https://github.com/PolatOzaslan21/tr2en/issues).

## Ne yapar?

1. Herhangi bir uygulamada Türkçe metni seçin.
2. **Ctrl+Shift+Space**'e basın.
3. Seçili metin İngilizcesiyle değişir. Panonuz (kopyaladığınız metin, resim, dosya) eski haline geri yüklenir.

tr2en artık pencereli bir uygulama: tepsideki **"tr2en'i aç"** ya da programı yeniden başlatmak pencereyi açar. Pencere açılınca **Çevir** sayfası çalışır — Google Çeviri'de olduğu gibi yazdığınız metin yazmayı bıraktığınızda kendiliğinden çevrilir (ya da **Ctrl+Enter**), en fazla 5000 karakter; sonucu **Kopyala** ile alabilir, **Temizle** ile silebilirsiniz. Sayfanın altındaki durum satırı çalışma durumunu, çevirmeni ve kısayolu gösterir.

Windows açılışında tr2en sessizce tepside başlar; pencereyi açmadan çalışır. Pencerenin X'ine basınca "Tepsiye küçült" / "Tamamen kapat" sorulur; **"Bir daha sorma" yalnızca küçültme için** geçerlidir (Genel → "Pencereyi kapatınca sor").

Çeviri motoru iki seçeneklidir:

| Çevirmen | Ne zaman | Gizlilik |
|---|---|---|
| **Bulut** (Gemini önerilir; OpenAI, DeepSeek, OpenRouter ya da kendi OpenAI uyumlu adresiniz) | En iyi kalite | Metin seçtiğiniz servise gider |
| **Yerel** (dahili model, Ollama, LM Studio, model klasörü) | İnternet yoksa ya da metin hiç dışarı çıkmasın istiyorsanız | Metin bilgisayardan çıkmaz |

İlk açılışta sihirbaz sorar: Yerel mi Bulut mu, Gemini anahtarı istenir ve kısayol bir kez denenir.

## Korumalar

- **Kod, URL ve dosya yolları** çeviriye girmez, aynen kalır (`src/main.py`, `https://…`, `` `komut` ``).
- **Olumsuzluk kontrolü:** "silme", "silmemiş", "-madan önce" gibi olumsuzluklar çeviride kaybolursa çeviri yapıştırılmaz, uyarı çıkar. (Bilinen sınır: olumsuzluğun başka kelimeye kaymasını — "yeni değil ama hızlı" → "new but not fast" — her zaman yakalayamaz.)
- **Zaten İngilizce** olan metin ya da cümleler olduğu gibi bırakılır.
- Yapay zekânın kesik, boş ya da "Sure, here is…" gibi açıklamalı yanıtları reddedilir; yerel modele geçilir.
- Parola yöneticilerinde (KeePass, 1Password, Bitwarden) çalışmaz.

## Gizlilik

- Çevrilen metin **hiçbir yere kaydedilmez**. Tepsideki "Son işlemler" yalnızca saat, süre ve karakter sayısını gösterir.
- Klavye kancası yalnızca kısayolu tanımak için kullanılır; tuşlar kaydedilmez.
- Bulut seçiliyse metin seçtiğiniz servise gönderilir; **Gemini'nin ücretsiz katmanında Google bu metinleri ürünlerini geliştirmek için kullanabilir.** Hassas metinler için "Yerel"i seçin.
- **API anahtarları Windows Kimlik Yöneticisi'nde şifreli saklanır**; ayar dosyasına ya da ortam değişkenine yazılmaz ve hiçbir log'a girmez, yalnızca istek başlığında gider.
- Yerel modellerde metin bilgisayardan çıkmaz.
- tr2en'in kendiliğinden yaptığı tek ağ bağlantısı, yerel model yoksa ilk açılışta modelin Hugging Face'ten (huggingface.co) indirilmesidir. Telemetri ya da kullanım istatistiği yoktur. Güncelleme denetimi yalnızca siz "Güncellemeleri kontrol et"e bastığınızda yapılır (GitHub'a sorulur).

## Kurulum

### Kolay yol: kurulum dosyası (Windows 10/11)

1. [Son sürüm](https://github.com/PolatOzaslan21/tr2en/releases/latest) sayfasından `tr2en-…-windows-x64-kurulum.exe` dosyasını indirip çalıştırın (~38 MB). Python ve yönetici izni gerekmez.
2. Kurulum, Başlat menüsüne **tr2en** kısayolu ekler; isterseniz masaüstü kısayolu ve "Windows açılışında başlat" kutucuklarını da işaretleyin. Programı açtığınızda pencere gelir; kapatırsanız tepside çalışmaya devam eder.
3. Saatin yanında kırmızı/mavi **TR → EN** balon simgesi çıkar. Simge önce saatin yanındaki **^** (gizli simgeler) menüsünde görünebilir; sürekli görünsün isterseniz oradan görev çubuğuna sürükleyin. Uygulamayı kapattıysanız Başlat menüsünde "tr2en" yazıp yeniden açabilirsiniz.

- .exe henüz dijital imzalı değil; Windows "bilgisayarınızı korudu" (SmartScreen) uyarısı verirse **Ek bilgi → Yine de çalıştır**'a tıklayın. İndirdiğiniz dosyanın doğruluğunu sürümdeki `.sha256` dosyasıyla kontrol edebilirsiniz.
- **Sürümlerin kurulum dosyası ve zip'i VirusTotal'da taranır**; tüm motorlarda temiz çıkarsa sonuç bağlantısı sürüm sayfasındaki notun sonuna eklenir.
- **Yeni sürüm var mı diye sormak için:** pencerede **Hakkında → Güncellemeleri kontrol et**. tr2en kendiliğinden GitHub'a sormaz; yalnızca bu düğmeye basınca sorar.
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
2. tr2en penceresinde **Çeviri motoru** sayfasını açın. **Bulut** seçiliyken **API anahtarı** kutusuna anahtarı yapıştırın.
3. **Bağlantıyı dene**'ye basın; "Çalışıyor" yazmalı.

Anahtar Windows Kimlik Yöneticisi'nde şifreli saklanır — ayar dosyasına ya da ortam değişkenine yazılmaz. Silmek için aynı kutudaki **Sil** düğmesi. İlk açılışta sihirbaz bu adımların hepsini tek tek gösterir.

Ücretsiz katman (Kasım 2026): Gemini 3.5 Flash-Lite için dakikada 15, günde 500 istek.

> İleri düzey: anahtar hâlâ `GEMINI_API_KEY` ortam değişkeninden de okunur (Kimlik Yöneticisi'nde yoksa). Pencere yolu daha kolay.

### Kendi modelinizi kullanın (isteğe bağlı)

Gemini **önerilen** seçenek, ama zorunlu değil. **Çeviri motoru** sayfasında **Bulut** seçiliyken:

- **Servis:** Google Gemini (önerilen) · OpenAI · DeepSeek · OpenRouter · Diğer (OpenAI uyumlu kendi adresiniz).
- **Adres:** yalnızca "Diğer" seçiliyse gerekir (ör. `https://api.openai.com/v1`).
- **API anahtarı:** servis anahtarınız; Kimlik Yöneticisi'ne yazılır.
- **Model:** açılır listeden seçilir; önerilen modeller listelenir. Listede olmayan model için **"Kendin ekle…"** seçip adı elle yazın.

Yerel çeviri için **Yerel**'i seçin, sonra **Model ekle**: **Ollama**, **LM Studio** ya da (ileri düzey) bir CTranslate2 model klasörü. Ollama adresi `http://localhost:11434/v1`, LM Studio `http://localhost:1234/v1` olmalı; model listesini **Listele** ile görüp birini seçebilirsiniz.

- Büyük yerel modeller hem yavaştır hem çok bellek ister; sayfada hız uyarısı çıkar.
- Ollama'da düşünen modeller (qwen3 ailesi) yavaştır; küçük bir model seçin.
- Güvenlik için `http://` yalnızca kendi bilgisayarınızdaki (localhost) servislerde kabul edilir; uzak servisler `https://` olmalı.
- Korumalar (kod/URL koruma, olumsuzluk kontrolü) bu seçenekte de çalışır. Küçük modeller olumsuzluğu sık kaçırır; tr2en bu durumda çeviriyi yapıştırmaz.

## Ayarlar

Ayarlar artık pencereden yapılır. Sayfalar: **Çevir**, **Genel**, **Çeviri motoru**, **Kısayol**, **Hakkında**, **Rehber**.

- **Genel:** pencereyi kapatınca sor, Windows açılışında başlat, çeviri sonrası sona boşluk ekle, son işlemleri tut, tema (sistem / açık / koyu).
- **Çeviri motoru:** Bulut / Yerel, servis, adres, API anahtarı, model, "Bulut çalışmazsa yerele geç".
- **Kısayol:** Ctrl+Shift+Space (önerilen), Ctrl+Shift+Y ya da **Kendi kısayolum…**; seçince 10 saniye içinde istediğiniz birleşime basın (ör. Ctrl+Shift+K; Esc vazgeçer). Ctrl ya da Alt gerekir. Kabul edilmeyenler: Ctrl+C/V/X/Z/Y/A/S (tr2en kopyala-yapıştırla çalışır), Alt+F4 ve Ctrl+Alt (Türkçe klavyede AltGr ile aynıdır, ₺ @ yazar). **Uyarı:** kendi kısayolunuz başka bir programın kısayoluyla çakışırsa o programda o işlem ya da tr2en düzgün çalışmayabilir; tek değiştiricili kısayollar (ör. Ctrl+Q) daha sık çakışır. Bilinen çakışmalarda tr2en uyarır.
- **Rehber:** başlarken, Yerel mi bulut mu, anahtar alma, model adı, yerel model ekleme ve sorun giderme (kısayol çalışmıyor, çeviri yapışmıyor, yönetici olarak çalışan programlar, terminal, API anahtarı/kota hatası, Ollama bağlanmıyor, model inmedi, antivirüs uyarısı, yavaş çeviri).

Tepsi menüsü: Etkin (duraklat), Çevirmen (Bulut / Yerel), Son işlemler, Son çeviriyi göster, Son orijinali kopyala, Kısayol, Windows açılışında başlat, Çıkış.

Kısayol tuşu programa gitmez: metin seçiliyse tr2en çevirir; seçim yoksa tuşu programa geri gönderir (ör. kısayolunuz Ctrl+P ise, seçim yokken programın kendi Ctrl+P işi yine çalışır). tr2en duraklatıldığında ve terminalde tuş olduğu gibi programa gider.

> İleri düzey: ayarların tamamı `%APPDATA%\tr2en\ayarlar.toml` dosyasında tutulur. Yasaklı uygulamalar, zaman aşımları ve "düşünmeyi kapat" gibi birkaç ayar pencerede yoktur; dosyayı elle düzenleyebilirsiniz. Değişiklikten sonra tr2en'i yeniden başlatın.

## Ölçümler (19.11.2026, Windows 11)

| Durum | Bellek (RAM) |
|---|---|
| Boşta (kanca + tepsi, Gemini ile) | ~35–50 MB |
| Yerel model yüklü | ~300 MB (yüklenirken anlık tepe ~450 MB) |

| Çeviri | Süre |
|---|---|
| Yerel model, cümle başına | 0,1–0,6 sn |
| Gemini | genelde ~1 sn; yoğun saatlerde 4 sn'yi geçerse yerel modele düşülür |

Yerel model yalnızca gerektiğinde yüklenir; yalnızca Gemini kullanıyorsanız ~50 MB'ta kalır. Pencere ayrı bir süreçte çalışır; kapatıldığında belleği geri verir.

## Token notu (dürüst haliyle)

Türkçe bir mesaj İngilizceye çevrilince **mesajın kendisi** %10–36 daha az token tutar (10 gerçek mesajla ölçüldü; o200k sayacında %10, cl100k'de %36). Ama Claude Code gibi araçlarda bir isteğin çoğu zaten İngilizce (kod, araç çıktıları, sistem talimatı); kullanıcı mesajı toplamın %1'inden azdır. Yani **faturanızı belirgin düşürmez.** Asıl fayda: modellerin İngilizce prompt'u daha iyi anlaması — özellikle küçük ve yerel modellerde.

## Antivirüs uyarısı

tr2en kısayolu yakalamak için klavye kancası kullanır. Bazı antivirüsler bu davranışı şüpheli bulabilir. Kod açık; kanca yalnızca kısayolu tanır, hiçbir tuşu kaydetmez ya da göndermez.

## Bilinen sınırlar

- **Terminalde kısayol çalışmaz** (Windows Terminal, cmd, PowerShell): seçili metin terminalde değiştirilemiyor. Metni kopyalayıp penceredeki **Çevir** sayfasına yapıştırıp çevirebilirsiniz.
- Yerel model uzun ve dağınık metinde zayıftır ("tablo" → "painting" gibi); kritik metinde bulut servisini kullanın ya da sonucu kontrol edin.
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
