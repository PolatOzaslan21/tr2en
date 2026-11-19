# AGENTS.md — rules for AI coding agents

tr2en is a Windows tray app that replaces selected Turkish text with its English translation (hotkey Ctrl+Shift+Space). Read [README.en.md](README.en.md) (English) or [README.md](README.md) (Turkish, default) for what users see. This file is for agents changing the code.

## Setup and tests

- Windows 10/11, Python ≥ 3.11, [uv](https://docs.astral.sh/uv/).
- Run all tests (must pass before any commit):

  ```powershell
  uv run --extra test --extra yerel --extra uygulama pytest -q
  ```

- If the app is running from this checkout, `.venv` is locked. Use a separate environment: set `UV_PROJECT_ENVIRONMENT` to another folder (for example `..\venv-test`) before `uv run`.
- Run the app with a console for debugging: `baslat.cmd` (or `uv run --extra uygulama --extra yerel tr2en-konsol`). Command-line translator for quick checks: `tr2en-cli`.

## Layout

- `src/ceviri_katmani/cekirdek/` — translation core, no UI: translators (`gemini.py`, `uyumlu.py` for OpenAI-compatible APIs, `yerel.py` offline CTranslate2 model), chain builder (`kurulum.py`), safety layer (`korumalar.py`, `cikti.py`), sentence splitting (`bolme.py`), language detection (`dil.py`), glossary (`sozluk.py`, `sozluk.tsv`), model download (`indir.py`).
- `src/ceviri_katmani/uygulama/` — Windows app: hotkey hook (`tetik.py`), clipboard (`pano.py`), tray (`tepsi.py`), settings (`ayarlar.py`, stored in `%APPDATA%\tr2en\ayarlar.toml`), entry points (`ana.py`, `arkaplan.py`).
- `tests/` — pytest, one file per module plus audit regression tests (`test_denetim1_*`, `test_dayaniklilik.py`).

## Conventions

- **Identifiers, comments, commit messages and user-facing strings are Turkish.** Keep it that way; don't rename to English.
- Commit messages: short Turkish prefix — `ozellik:`, `duzeltme:`, `belge:`, `test:`, `surum:` — ASCII only.
- Every translator implements `.ad` and `cevir(metin, kaynak="tr", hedef="en") -> str` and raises `CeviriHatasi` on failure; `kurulum.zincir_kur` wraps each one in `KorumaliCevirmen`.
- No new dependencies without a clear reason; the core depends only on `httpx`.

## Must not break

- **Safety layer** (`korumalar.py`, `cikti.py`): code/URL/path masking with `ZXQ{i}ZXQ` placeholders, negation check, output checks. Write a failing test first, then change. A translation that loses a negation must never be pasted.
- **Privacy:** never log, store or send the user's text anywhere except the selected translator. Never print or write API keys; refer to them by environment variable name (`GEMINI_API_KEY`, or the name in `uyumlu_anahtar_degiskeni`).
- `http://` is allowed only for localhost translators.
- Clipboard: the user's original clipboard (text, image, files) must be restored after every job, including on errors.
- Tests must not touch the network, the real `%APPDATA%`, the registry Run key, the Windows Credential Manager, the real clipboard or the real web browser unless the test is explicitly a Windows integration test (`tests/conftest.py` blocks `webbrowser`).

## Model

The offline model (`PolatOz/tr2en-model` on Hugging Face, CC-BY-4.0) is downloaded at runtime with SHA256 checks; it is not in this repo. Don't commit model files.
