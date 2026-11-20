# tr2en — Turkish → English translation layer

[Türkçe](https://github.com/PolatOzaslan21/tr2en/blob/main/README.md) | **English**

**Local Turkish to English translation for Windows: select text, press a hotkey, the English replaces it.** A small tray and window app for writing English prompts to AI assistants (Claude, ChatGPT, Copilot…), offline translation, or quick prompt translation.

> **Status: 0.2 beta.** A new release; expect rough edges. Please [open an issue](https://github.com/PolatOzaslan21/tr2en/issues) if something breaks.
>
> The app is made for Turkish speakers, so its tray menu, notifications and window pages are in Turkish.

## What it does

1. Select Turkish text in any application.
2. Press **Ctrl+Shift+Space**.
3. The selection is replaced with its English translation. Your clipboard (text, image, files) is restored afterwards.

tr2en is now a windowed app: **"tr2en'i aç"** in the tray — or simply starting the program again — opens the window. The window opens on the **Çevir** (Translate) page, which works like Google Translate: what you type is translated by itself once you stop typing (or press **Ctrl+Enter**), up to 5000 characters; take the result with **Kopyala** (Copy) and clear it with **Temizle** (Clear). The status line at the bottom of the page shows the working state, the translator and the hotkey.

On Windows start-up tr2en starts silently in the tray and works without the window. Closing the window with the X asks whether to **minimise to the tray** or **quit completely**; **"Bir daha sorma" (don't ask again) only applies to minimising** (General → "Pencereyi kapatınca sor").

There are two translator options:

| Translator | When | Privacy |
|---|---|---|
| **Cloud** (Gemini recommended; OpenAI, DeepSeek, OpenRouter, or your own OpenAI-compatible address) | Best quality | Text is sent to the service you picked |
| **Local** (built-in model, Ollama, LM Studio, model folder) | No internet, or you want the text to never leave your PC | Text never leaves your PC |

On first start a wizard asks: local or cloud, requests a Gemini key and lets you try the hotkey once.

## Safety checks

- **Code, URLs and file paths** are never translated (`src/main.py`, `https://…`, `` `command` ``).
- **Negation check:** if a negation (such as "silme", "don't delete") is lost in translation, the result is not pasted and you get a warning. (Known limit: a negation that moves to another word — "new but not fast" instead of "not new but fast" — is not always caught.)
- Text or sentences that are **already English** are left as they are.
- Truncated, empty or chatty AI replies ("Sure, here is…") are rejected; the local model takes over.
- Disabled in password managers (KeePass, 1Password, Bitwarden).

## Privacy

- Translated text is **never stored**. "Son işlemler" (recent jobs) in the tray only shows time, duration and character count.
- The keyboard hook is only used to detect the hotkey; keystrokes are not recorded.
- With the cloud translator, text is sent to the service you picked; **on Gemini's free tier Google may use it to improve its products.** Use "Yerel" (local) for sensitive text.
- **API keys are stored encrypted in the Windows Credential Manager**; they are not written to the settings file or to an environment variable, never reach a log, and only travel in the request header.
- With local models, text stays on your PC.
- The only network connection tr2en makes on its own is downloading the local model from Hugging Face (huggingface.co) on first start if it is missing. No telemetry or usage statistics. The update check is only made when you press "Güncellemeleri kontrol et" (Check for updates) — it asks GitHub.

## Install

### Easy way: installer (Windows 10/11)

1. Download and run `tr2en-…-windows-x64-kurulum.exe` (~38 MB) from the [latest release](https://github.com/PolatOzaslan21/tr2en/releases/latest) ("kurulum" means "setup"). No Python and no admin rights needed.
2. The installer adds a **tr2en** Start menu shortcut; you can also tick a desktop shortcut and "start with Windows". Starting the program opens the window; closing it keeps tr2en running in the tray.
3. A red/blue **TR → EN** speech-bubble icon appears next to the clock. Windows may first put it in the hidden icons menu (the **^** next to the clock); drag it to the taskbar to keep it visible. If you quit the app, type "tr2en" in the Start menu to open it again.

- The .exe is not code-signed yet; if Windows shows "Windows protected your PC" (SmartScreen), click **More info → Run anyway**. You can verify the download with the `.sha256` file in the release.
- **Release installers and zips are scanned on VirusTotal**; when every engine reports them clean, the result link is added to the end of the release notes.
- **To ask whether a newer version exists:** open **Hakkında → Güncellemeleri kontrol et** (About → Check for updates). tr2en does not ask GitHub on its own; it only queries when you press that button.
- **To update:** just run the new installer; it closes a running tr2en itself and keeps your settings and the model.
- **To uninstall:** Settings → Apps → tr2en → Uninstall. It asks whether to delete your settings and the downloaded model too.
- **Portable (no install):** extract `tr2en-…-windows-x64.zip` to a permanent folder and run `tr2en.exe`. To update, quit from the tray (**Çıkış**) first and extract the new zip into the same folder.

### For developers: with uv

From [PyPI](https://pypi.org/project/tr2en/), with [uv](https://docs.astral.sh/uv/):

```powershell
uv tool install "tr2en[uygulama,yerel]"
tr2en
```

(`pip install "tr2en[uygulama,yerel]"` works too; Python ≥ 3.11.)

To run from source: clone the repo and run `baslat-arkaplan.cmd` (no console) or `baslat.cmd` (with console, for debugging).

### Gemini key (free, recommended)

1. Create a key with **Create API key** at https://aistudio.google.com/apikey and copy it.
2. Open the **Çeviri motoru** (Translation engine) page in the tr2en window. With **Bulut** (Cloud) selected, paste the key into the **API anahtarı** (API key) box.
3. Click **Bağlantıyı dene** (Test connection); you should see "Çalışıyor" (Working).

The key is stored encrypted in the Windows Credential Manager — not in the settings file and not in an environment variable. Use the **Sil** (Delete) button in the same box to remove it. On first start the wizard walks through all of this.

Free tier (November 2026): 15 requests per minute and 500 per day for Gemini 3.5 Flash-Lite.

> Advanced: the key is still read from the `GEMINI_API_KEY` environment variable when it is not in the Credential Manager. The window is the easier way.

### Use your own model (optional)

Gemini is **recommended**, not required. On the **Çeviri motoru** page with **Bulut** (Cloud) selected:

- **Servis** (service): Google Gemini (recommended) · OpenAI · DeepSeek · OpenRouter · Other (your own OpenAI-compatible address).
- **Adres** (address): only needed for "Other" (e.g. `https://api.openai.com/v1`).
- **API anahtarı** (API key): your service key; it is written to the Credential Manager.
- **Model**: picked from a drop-down that lists the recommended models. For a model that is not listed, choose **"Kendin ekle…"** (add it yourself) and type the name.

For local translation select **Yerel** (Local) and then **Model ekle** (Add model): **Ollama**, **LM Studio** or (advanced) a CTranslate2 model folder. The Ollama address must be `http://localhost:11434/v1` and LM Studio `http://localhost:1234/v1`; you can check the model list with **Listele** (List) and pick one.

- Big local models are slow and use a lot of memory; the page shows a speed warning.
- Thinking models in Ollama (qwen3 family) are slow; pick a smaller model.
- For security, `http://` is only accepted for services on your own PC (localhost); remote services must use `https://`.
- The safety checks (code/URL protection, negation check) apply here too. Small models often drop negations; tr2en then refuses to paste.

## Settings

Settings are made in the window now. Pages: **Çevir** (Translate), **Genel** (General), **Çeviri motoru** (Translation engine), **Kısayol** (Hotkey), **Hakkında** (About), **Rehber** (Guide).

- **Genel:** ask when closing the window, start with Windows, add a trailing space after translation, keep recent jobs, theme (system / light / dark).
- **Çeviri motoru:** cloud / local, service, address, API key, model, "fall back to the local model if the cloud fails".
- **Kısayol:** Ctrl+Shift+Space (recommended), Ctrl+Shift+Y or **Kendi kısayolum…** (your own hotkey); pick it, then press the combination within 10 seconds (e.g. Ctrl+Shift+K; Esc cancels). Ctrl or Alt is required. Rejected: Ctrl+C/V/X/Z/Y/A/S (tr2en itself copies and pastes), Alt+F4 and Ctrl+Alt (equals AltGr on many layouts). **Note:** if your own hotkey clashes with another program, that program or tr2en may not work properly; single-modifier hotkeys (e.g. Ctrl+Q) clash more often. tr2en warns about well-known conflicts.
- **Rehber:** getting started, local or cloud, getting a key, what a model name is, adding a local model and troubleshooting (hotkey does nothing, translation not pasted, programs running as administrator, terminal, API key / quota error, cannot reach Ollama, model not downloaded, antivirus warning, slow translation).

Tray menu: Etkin (active / pause), translator (cloud / local), recent jobs, show last translation, copy last original, hotkey, start with Windows, quit.

The hotkey does not reach the program: with text selected, tr2en translates it; with nothing selected, it sends the hotkey back to the program (e.g. with Ctrl+P as your hotkey, the program's own Ctrl+P still works when nothing is selected). When tr2en is paused, and in terminals, keys pass through unchanged.

> Advanced: all settings are kept in `%APPDATA%\tr2en\ayarlar.toml`. A few of them — blocked apps, timeouts, "turn thinking off" — are not in the window; you can edit the file by hand. Restart tr2en after editing.

## Measurements (2026-11-19, Windows 11)

| State | Memory (RAM) |
|---|---|
| Idle (hook + tray, with Gemini) | ~35–50 MB |
| Offline model loaded | ~300 MB (brief peak ~450 MB while loading) |

| Translation | Time |
|---|---|
| Offline model, per sentence | 0.1–0.6 s |
| Gemini | usually ~1 s; if it takes over 4 s at busy hours, the offline model takes over |

The offline model is loaded only when needed; with Gemini only, the app stays around 50 MB. The window runs as a separate process; closing it gives the memory back.

## A note on tokens (the honest version)

Translated to English, a Turkish message **itself** uses 10–36% fewer tokens (measured on 10 real messages: 10% with o200k, 36% with cl100k). But in tools like Claude Code most of a request is already English (code, tool output, system prompt); the user message is under 1% of the total. So it **won't noticeably lower your bill.** The real benefit is that models understand English prompts better, especially small and local models.

## Antivirus warning

tr2en uses a keyboard hook to catch the hotkey. Some antivirus programs may flag this. The code is open; the hook only detects the hotkey and never records or sends keystrokes.

## Known limits

- **The hotkey does not work in terminals** (Windows Terminal, cmd, PowerShell): selected text can't be replaced there. Copy the text, paste it into the **Çevir** (Translate) page of the window and translate it there.
- The local model is weak on long, messy text (e.g. "tablo" → "painting" instead of "table"); use a cloud service for important text or check the result.
- Turkish → English only for now.

## Development

```powershell
uv run --extra test --extra yerel --extra uygulama pytest -q
```

Tests run on Windows in GitHub Actions on every push. Rules for AI coding agents: [AGENTS.md](https://github.com/PolatOzaslan21/tr2en/blob/main/AGENTS.md). Identifiers in the code are in Turkish.

## Code signing policy

tr2en.exe and the installer are **not code-signed yet**; an application to [SignPath Foundation](https://signpath.org/) for free open source signing is planned. Once signing is in place:

- Files are built only from the source code in this repository by GitHub Actions; manually built files are never signed.
- Roles: author, reviewer and approver: [PolatOzaslan21](https://github.com/PolatOzaslan21) (repository owner). Every outside change (pull request) is reviewed before merging; signing of each release is approved manually.
- Privacy: This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it. Details: [Privacy](#privacy).

## License

Code: **MIT**. The downloaded offline model: **CC-BY-4.0**, a CTranslate2 int8 conversion of [Helsinki-NLP/opus-mt-tc-big-tr-en](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-tr-en), hosted at [PolatOz/tr2en-model](https://huggingface.co/PolatOz/tr2en-model).
