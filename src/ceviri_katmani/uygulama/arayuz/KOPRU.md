# KÖPRÜ — Ayar Penceresi JS API'si (PencereApi)

JS'ten çağrılan Python köprüsü. İleride Rust/Tauri arka ucu **aynı sözleşmeyi**
uygulayacak. Uygulama: `src/ceviri_katmani/uygulama/pencere_api.py`.

## Güvenlik kuralları (her yöntem için geçerli)

- **İstisna fırlatılmaz.** Hata olursa `{"ok": False, "hata": "<kısa Türkçe metin>"}` tabanlı sözlük döner.
- **Anahtar değeri asla JS'e dönmez**, loglanmaz, hata metinlerinde görünmez (dönüşler `***` ile temizlenir).
- **Yalnızca beyaz liste URL** açılır (`baglanti_ac`); listede olmayan hiçbir adres tarayıcıya verilmez.
- **`http://` yalnızca localhost** (Ollama model listesi yalnızca `localhost` / `127.0.0.1` / `[::1]` adreslerinden okunur).
- Tüm dönüşler JSON'a çevrilebilir sözlüktür.

## Yöntemler

| Yöntem | Parametreler | Dönüş | Not |
|---|---|---|---|
| `ayarlari_al()` | — | `{"ok", "ayarlar", "anahtarlar", "surum"}` | `ayarlar`: şema 2 sözlüğü (izinli/yasak/ek_terminaller dahil). `anahtarlar`: `{servis: bool}` — kasada/ortamda anahtar var mı; DEĞİL anahtarın kendisi. `surum`: uygulama sürümü. |
| `ayar_kaydet(degisiklikler)` | `dict` | `{"ok", "uyarilar"}` | Yalnızca `VARSAYILAN`'daki anahtarlar güncellenir; bilinmeyenler atlanır ve uyarıya eklenir. Doğrula → kaydet; başarılıysa sinyal `yenile`. |
| `ilk_kurulum_tamamla(cevirmen)` | `str` | `{"ok"}` | İlk açılış sihirbazını kapatır. `cevirmen` "bulut" ya da "yerel" olmalı; başka değer → `ok: False`. Geçerliyse `cevirmen` ve `gizlilik_onayi = True` kaydedilir (sinyal `yenile`). |
| `anahtar_kaydet(servis, deger)` | `str, str` | `{"ok"}` | Servisler: `gemini, openai, deepseek, openrouter, diger`. Değer hiçbir yere loglanmaz/dönmez. Başarılıysa sinyal `yenile`. |
| `anahtar_sil(servis)` | `str` | `{"ok"}` | Başarılıysa sinyal `yenile`. |
| `baglanti_dene(ayar_parcasi, anahtar=None)` | `dict, str\|None` | `{"ok", "sure_sn", "ceviri", "hata"}` | Ayarların **geçici** kopyasıyla zincir kurulur (`bulut_yedek_yerel` False zorlanır), `"Merhaba dünya, bu bir denemedir."` çevrilir. Dosyaya YAZMAZ. `anahtar` verilmişse (kaydedilmemiş) o kullanılır. |
| `cevir_dene(metin)` | `str` | `{"ok", "ceviri", "cevirmen", "sure_sn", "hata"}` | Kayıtlı ayarlarla (yerel yedek dahil) akıllı çeviri. Metin 2000 karakterle sınırlı; boşsa `ok: False`. Metin zaten İngilizceyse çevrilmez (`cevirmen: None`). |
| `ollama_modelleri(adres)` | `str` | `{"ok", "modeller"}` | Yalnızca yerel adresler. `GET {adres}/models`, 3 sn zaman aşımı; `data[].id` listesi döner. |
| `klasor_sec()` | — | `{"ok", "yol"}` | `klasor_secici` ile klasör seçimi; `model.bin` yoksa `ok: False` ("Bu klasörde CTranslate2 modeli yok"). |
| `baglanti_ac(anahtar_ad)` | `str` | `{"ok"}` | Yalnızca beyaz liste (`BEYAZ_LISTE`): `gemini_anahtar, openai_anahtar, deepseek_anahtar, openrouter_anahtar, ollama, lmstudio, github, sorun, gizlilik`. |
| `kisayol_kaydet(degistiriciler, tus)` | `list[str], str` | `{"ok", "kisayol", "uyari", "hata"}` | `birlesim_olustur` ile doğrula → `ayar_kaydet`. Çakışma varsa `uyari` dolar. `tus == "esc"` → `{"ok": False, "hata": "vazgeçildi"}`. |
| `kapat_secimi(secim, hatirla)` | `str, bool` | `{"ok"}` | `"kucult"` + `hatirla` → `kapatinca_sor` False kaydedilir. `"tamamen"` → sinyal `cikis` (`hatirla` yok sayılır). Pencereyi çağıran kapatır. |
| `otomatik_baslat_durum()` | — | `{"ok", "acik"}` | HKCU Run anahtarında "tr2en" değeri var mı (Windows açılışında başlat). |
| `otomatik_baslat_ayarla(acik)` | `bool` | `{"ok"}` | `acik=True` → Run değerini `komut()` ile yazar (`--arka` dahil); `False` → değeri siler. |

Başarısızlıkta dönüşler, yöntemdeki alanları nötr değerlerle (`"":`, `[]`, `None`, `0.0`) **artı** `hata` alanını içerir.

## Sinyaller (`sinyal_gonder`)

- `"yenile"` — ayarlar ya da anahtar değişti; arka plandaki uygulama zinciri yeniden kurmalı.
- `"cikis"` — pencere "tamamen kapat" dedi; uygulama kapanmalı.

## Kurucu enjeksiyonları (testler sahte verir)

`ayar_yolu` (Path\|None), `kasa` (anahtar_kasasi arayüzü), `sinyal_gonder`,
`tarayici_ac` (varsayılan `webbrowser.open`), `http_istemci` (httpx.Client benzeri),
`zincir_kurucu` (varsayılan `zincir_kur_v2`), `klasor_secici` (varsayılan None → `ok: False`),
`otomatik_baslat` (varsayılan `otomatik_baslat` modülü; testlerde sahte),
`saat` (varsayılan `time.perf_counter`).
