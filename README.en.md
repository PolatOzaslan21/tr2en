# tr2en — Turkish → English translation layer

[Türkçe](README.md) | **English**

**Local Turkish to English translation for Windows: select text, press a hotkey, the English replaces it.** A small tray app for writing English prompts to AI assistants (Claude, ChatGPT, Copilot…), offline translation, or quick prompt translation.

> **Status: 0.1 beta.** An early release; expect rough edges. Please [open an issue](https://github.com/PolatOzaslan21/tr2en/issues) if something breaks.
>
> The app is made for Turkish speakers, so its tray menu, notifications and settings keys are in Turkish.

## What it does

1. Select Turkish text in any application.
2. Press **Ctrl+Shift+Space**.
3. The selection is replaced with its English translation. Your clipboard (text, image, files) is restored afterwards.

Three translator options (switch from the tray icon):

| Translator | When | Privacy |
|---|---|---|
| **Gemini** (Google, your own free API key) | Recommended, best quality | Text is sent to Google |
| **Your own model** (any OpenAI-compatible API, or Ollama / LM Studio) | Another provider, or a model on your own PC | Depends on the provider; with Ollama, text stays on your PC |
| **Offline model** (~230 MB, downloaded once on first start) | Fallback when the others are missing or slow, or when "local only" is selected | Text never leaves your PC |

On first start the app asks which one you want to use.

## Safety checks

- **Code, URLs and file paths** are never translated (`src/main.py`, `https://…`, `` `command` ``).
- **Negation check:** if a negation (such as "silme", "don't delete") is lost in translation, the result is not pasted and you get a warning. (Known limit: a negation that moves to another word — "new but not fast" instead of "not new but fast" — is not always caught.)
- Text or sentences that are **already English** are left as they are.
- Truncated, empty or chatty AI replies ("Sure, here is…") are rejected; the offline model takes over.
- Disabled in password managers (KeePass, 1Password, Bitwarden).

## Privacy

- Translated text is **never stored**. "Son işlemler" (recent jobs) in the tray only shows time, duration and character count.
- The keyboard hook is only used to detect the hotkey; keystrokes are not recorded.
- With Gemini, text is sent to Google; **on the free tier Google may use it to improve its products.** Use "local only" for sensitive text.
- API keys are only sent in the request header, never written to a file or log.

## Install

### Easy way: download and run (Windows 10/11)

1. Download `tr2en-…-windows-x64.zip` (~58 MB) from the [latest release](https://github.com/PolatOzaslan21/tr2en/releases/latest).
2. Extract it to a permanent folder (e.g. `Documents\tr2en`) and run **`tr2en.exe`**. No Python needed.
3. A blue **EN** icon appears next to the clock. You can enable "Windows açılışında başlat" (start with Windows) from the tray (if you move the folder later, turn it off and on again).

- The .exe is not code-signed yet; if Windows shows "Windows protected your PC" (SmartScreen), click **More info → Run anyway**. You can verify the download with the `.sha256` file in the release.
- To update: quit from the tray (**Çıkış**), extract the new zip into the same folder (your settings and the model stay in `%APPDATA%` / `%LOCALAPPDATA%`).

### For developers: with uv

Requirements: [uv](https://docs.astral.sh/uv/).

```powershell
uv tool install "tr2en[uygulama,yerel] @ git+https://github.com/PolatOzaslan21/tr2en"
tr2en
```

To run from source: clone the repo and run `baslat-arkaplan.cmd` (no console) or `baslat.cmd` (with console, for debugging).

### Gemini key (free, recommended)

1. Create a key with **Create API key** at https://aistudio.google.com/apikey and copy it.
2. Run this in PowerShell (stores the key from your clipboard as a user environment variable without printing it):

```powershell
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', (Get-Clipboard).Trim(), 'User')
```

3. Restart tr2en. Without a key, only the offline model is used.

Free tier (November 2026): 15 requests per minute and 500 per day for Gemini 3.5 Flash-Lite.

### Use your own model (optional)

Gemini is **recommended**, not required. You can connect any service with an OpenAI-compatible API, or a model running on your PC. Fill in four lines in `ayarlar.toml`, then choose **Çevirmen → Kendi modelim** (Translator → My own model) in the tray:

| Service | `uyumlu_adres` | `uyumlu_model` (example) | `uyumlu_anahtar_degiskeni` |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| OpenRouter (hundreds of models) | `https://openrouter.ai/api/v1` | `google/gemini-2.5-flash` | `OPENROUTER_API_KEY` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| **Ollama** (local, free) | `http://localhost:11434/v1` | `qwen3.5:0.8b`, `llama3.2` | *(leave empty)* |
| LM Studio (local) | `http://localhost:1234/v1` | the model you loaded | *(leave empty)* |

- In `uyumlu_anahtar_degiskeni`, put the **name** of the environment variable that holds your key, **not the key itself** (use the PowerShell command above with that name instead of `GEMINI_API_KEY`).
- For thinking models in Ollama (qwen3 family), set `uyumlu_dusunmeyi_kapat = true`: with the 0.8B qwen3.5, translation drops from 22 s to ~1 s.
- If your local LLM is slow, raise `uyumlu_zaman_asimi` (default 15 s).
- For security, `http://` is only accepted for services on your own PC (localhost); remote services must use `https://`.
- The safety checks (code/URL protection, negation check) apply here too. Small models often drop negations; tr2en then refuses to paste.

## Settings

Tray menu: enable/pause, translator, hotkey (Ctrl+Shift+Space / Ctrl+Shift+Y / Ctrl+Shift+T), recent jobs, show last translation, copy last original, start with Windows.

Everything else is in `%APPDATA%\tr2en\ayarlar.toml` (tray: "Ayarlar dosyasını aç"): timeout, Gemini model, your own model, blocked apps, trailing space. Restart the app after editing.

## Measurements (2026-11-19, Windows 11)

| State | Memory (RAM) |
|---|---|
| Idle (hook + tray, with Gemini) | ~35–50 MB |
| Offline model loaded | ~300 MB (brief peak ~450 MB while loading) |

| Translation | Time |
|---|---|
| Offline model, per sentence | 0.1–0.6 s |
| Gemini | usually ~1 s; if it takes over 4 s at busy hours, the offline model takes over |

The offline model is loaded only when needed; with Gemini only, the app stays around 50 MB.

## A note on tokens (the honest version)

Translated to English, a Turkish message **itself** uses 10–36% fewer tokens (measured on 10 real messages: 10% with o200k, 36% with cl100k). But in tools like Claude Code most of a request is already English (code, tool output, system prompt); the user message is under 1% of the total. So it **won't noticeably lower your bill.** The real benefit is that models understand English prompts better, especially small and local models.

## Antivirus warning

tr2en uses a keyboard hook to catch the hotkey. Some antivirus programs may flag this. The code is open; the hook only detects the hotkey and never records or sends keystrokes.

## Known limits

- **Does not work in terminals** (Windows Terminal, cmd, PowerShell): selected text can't be replaced there. A hotkey-opened input box is planned for the next version.
- The offline model is weak on long, messy text (e.g. "tablo" → "painting" instead of "table"); use Gemini for important text or check the result.
- Turkish → English only for now.

## Development

```powershell
uv run --extra test --extra yerel --extra uygulama pytest -q
```

Tests run on Windows in GitHub Actions on every push. Rules for AI coding agents: [AGENTS.md](AGENTS.md). Identifiers in the code are in Turkish.

## License

Code: **MIT**. The downloaded offline model: **CC-BY-4.0**, a CTranslate2 int8 conversion of [Helsinki-NLP/opus-mt-tc-big-tr-en](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-tr-en), hosted at [PolatOz/tr2en-model](https://huggingface.co/PolatOz/tr2en-model).
