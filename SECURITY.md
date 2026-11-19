# Security policy

**English** | [Türkçe](#türkçe)

tr2en installs a keyboard hook, reads and writes the clipboard, and can send text to translation APIs, so security reports are taken seriously.

## Reporting a vulnerability

**Please don't open a public issue.** Report privately through GitHub: [Security → Report a vulnerability](https://github.com/PolatOzaslan21/tr2en/security/advisories/new).

Include what you found, how to reproduce it, and the tr2en and Windows versions. You'll get a reply within 7 days. Please give a reasonable time to fix it before disclosing publicly.

## Supported versions

Only the latest release (currently 0.1 beta) gets fixes.

## What counts

Examples: keystrokes or translated text being recorded or leaked, API keys written to disk or logs or sent anywhere other than the selected API, an `http://` connection to a non-local host, a tampered model download being accepted, or code execution through settings or the downloaded model.

The model is downloaded from [PolatOz/tr2en-model](https://huggingface.co/PolatOz/tr2en-model) and checked against SHA256 hashes in the code.

---

## Türkçe

Güvenlik açığı bulduysanız **herkese açık issue açmayın.** GitHub üzerinden özel olarak bildirin: [Security → Report a vulnerability](https://github.com/PolatOzaslan21/tr2en/security/advisories/new). Ne bulduğunuzu, nasıl tekrarlanacağını, tr2en ve Windows sürümünü yazın; 7 gün içinde dönüş yapılır. Yalnızca son sürüm (şu an 0.1 beta) düzeltme alır.

Örnek güvenlik sorunları: tuşların ya da çevrilen metnin kaydedilmesi/sızması, API anahtarının diske, log'a ya da seçili API dışına gitmesi, uzak sunucuya `http://` bağlantısı, değiştirilmiş model indirmesinin kabul edilmesi, ayarlar ya da model üzerinden kod çalıştırılması.
