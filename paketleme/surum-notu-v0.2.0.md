# tr2en v0.2.0 (Beta)

## Yenilikler

- **Pencere.** tr2en artık pencereli bir uygulama. Tepsideki **"tr2en'i aç"** (ya da programı yeniden başlatmak) pencereyi açar; Windows açılışında tr2en sessizce tepside başlar, pencere açılmadan çalışır.
- **Çevir sayfası.** Google Çeviri benzeri: yazdığınız metin yazmayı bıraktığınızda kendiliğinden çevrilir (Ctrl+Enter da çevirir), en fazla 5000 karakter, **Kopyala** ve **Temizle** düğmeleri; altta durum satırı (çalışma durumu, çevirmen, kısayol).
- **Pencereyi kapatma sorusu.** Pencereyi X ile kapatınca "Tepsiye küçült" / "Tamamen kapat" sorulur. "Bir daha sorma" yalnızca küçültme için geçerlidir; soruyu kalıcı olarak kapatmak için Genel sayfasındaki "Pencereyi kapatınca sor" anahtarını kapatın.
- **İlk açılış sihirbazı.** Üç adım: Yerel mi Bulut mu, ücretsiz Gemini anahtarı (yoksa "şimdilik atla"), kısayolu bir kez deneme.
- **Çeviri motoru sayfası.** İki seçenek: **Bulut** (Gemini önerilir; OpenAI, DeepSeek, OpenRouter ya da kendi OpenAI uyumlu adresiniz) ve **Yerel** (dahili model, Ollama, LM Studio, model klasörü). Model adı açılır listeden seçilir; listede yoksa **"Kendin ekle…"** ile elle yazılır. Büyük yerel modellerde hız uyarısı çıkar.
- **"Bulut çalışmazsa yerele geç".** Bulut seçiliyken internet ya da servis yanıt vermezse çeviri yerel modelle devam eder.
- **API anahtarları Windows Kimlik Yöneticisi'nde.** Anahtarlar artık ayar dosyasına ya da ortam değişkenine yazılmaz; penceredeki API anahtarı kutusundan kaydedilir ve Kimlik Yöneticisi'nde şifreli tutulur.
- **Rehber sayfası.** Model adı nedir, yerel model nasıl eklenir, kurulum ve antivirüs uyarıları; ayrıca sorun giderme başlıkları (kısayol çalışmıyor, çeviri yapışmıyor, yönetici olarak çalışan programlar, terminal, API anahtarı/kota hatası, Ollama bağlanmıyor, model inmedi, antivirüs uyarısı, yavaş çeviri).
- **Hakkında sayfası.** **"Güncellemeleri kontrol et"** düğmesi yalnızca basıldığında GitHub'a sorar; sürüm sayfası bağlantısı vardır. Her sürümün kurulum dosyası ve zip'i VirusTotal'da taranır, sonuç sürüm sayfasında.

## Düzeltmeler

- **Windows 11'in yeni Not Defteri'nde kısayol artık çalışıyor.** Yeni Not Defteri gönderilen Ctrl+C/Ctrl+V tuşlarını almadığı için seçim yok sanılıyordu; bu metin alanında seçim doğrudan okunuyor, kopyala-yapıştır mesajla yapılıyor.
- **"denemedir" gibi kelimeler yanlışlıkla olumsuz sayılmıyor.** "denemedir", "dramadır" gibi isim+ek fiil biçimleri olumsuz geçmiş zaman sanılıp çeviri gereksiz yere engelleniyordu.
- **Windows açılışında ayar penceresi açılmıyor.** Eski kurulumlardan kalan başlatma değerleri sessiz başlatma yerine pencereyi açıyordu; başlatma değeri düzeltildi.

## Yükseltme

- **Ayarlar otomatik taşınır.** Eski ayar dosyanız yeni şemaya (Bulut/Yerel) çevrilip aynı dosyaya yeniden yazılır; kısayolunuz, tema, yasaklı uygulamalar ve seçili model korunur; indirilmiş yerel model yeniden indirilmez.
- **API anahtarları otomatik taşınmaz.** Anahtar Kimlik Yöneticisi'nde yoksa eski ortam değişkeniniz (`GEMINI_API_KEY` vb.) okunmaya devam eder. Yeni akışta anahtarı pencerede **Çeviri motoru → API anahtarı** kutusuna yapıştırın; oradan Kimlik Yöneticisi'ne yazılır.
- Kurulum dosyasını çalıştırmak yeterli: açık tr2en kendini kapatır, ayarlarınız ve model korunur.

---

# tr2en v0.2.0 (Beta)

## New features

- **A window.** tr2en is now a windowed app. **"tr2en'i aç"** in the tray — or simply starting the program again — opens the window; on Windows start-up tr2en starts silently in the tray and works without the window.
- **The Çevir (Translate) page.** Like Google Translate: what you type is translated by itself once you stop typing (Ctrl+Enter translates too), up to 5000 characters, with **Kopyala** (Copy) and **Temizle** (Clear) buttons; a status line at the bottom (working state, translator, hotkey).
- **A question when closing the window.** Pressing X asks whether to **minimise to the tray** or **quit completely**. "Bir daha sorma" (don't ask again) only applies to minimising; to turn the question off for good, switch off "Pencereyi kapatınca sor" on the General page.
- **First-start wizard.** Three steps: local or cloud, a free Gemini key (or "skip for now"), and a try of the hotkey.
- **The Çeviri motoru (Translation engine) page.** Two options: **Bulut** (Cloud — Gemini recommended; OpenAI, DeepSeek, OpenRouter or your own OpenAI-compatible address) and **Yerel** (Local — built-in model, Ollama, LM Studio, model folder). The model name is picked from a drop-down; if it is not listed, choose **"Kendin ekle…"** and type it yourself. Big local models get a speed warning.
- **"Fall back to the local model if the cloud fails".** With the cloud selected, translation continues with the local model when there is no internet or the service does not answer.
- **API keys in the Windows Credential Manager.** Keys are no longer written to the settings file or to an environment variable; you save them in the API key box in the window and they are kept encrypted in the Credential Manager.
- **A Guide page.** What a model name is, how to add a local model, install and antivirus notes; plus troubleshooting topics (hotkey does nothing, translation not pasted, programs running as administrator, terminal, API key / quota error, cannot reach Ollama, model not downloaded, antivirus warning, slow translation).
- **An About page.** The **"Güncellemeleri kontrol et"** (Check for updates) button only queries GitHub when you press it; there is a link to the release page. Every release's installer and zip are scanned on VirusTotal, and the result is on the release page.

## Fixes

- **The hotkey now works in the new Windows 11 Notepad.** The new Notepad did not receive the Ctrl+C/Ctrl+V keys, so the selection looked empty; in that text field the selection is read directly and copy/paste is done with messages.
- **Words like "denemedir" are no longer taken for negation.** Forms such as "denemedir" or "dramadır" were mistaken for the negative past tense and translation was blocked for no reason.
- **The settings window no longer opens on Windows start-up.** Start-up values left over from older installs opened the window instead of starting silently; the value is fixed now.

## Upgrading

- **Settings are migrated automatically.** Your old settings file is converted to the new schema (cloud/local) and rewritten in place; your hotkey, theme, blocked apps and selected model are kept; the downloaded local model is not downloaded again.
- **API keys are not migrated automatically.** If the key is not in the Credential Manager, your old environment variable (`GEMINI_API_KEY` etc.) keeps being read. In the new flow, paste the key into **Çeviri motoru → API anahtarı** in the window; it is then written to the Credential Manager.
- Running the installer is enough: it closes a running tr2en and keeps your settings and the model.
