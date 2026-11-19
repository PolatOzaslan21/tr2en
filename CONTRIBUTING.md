# Contributing to tr2en

**English** | [Türkçe](#türkçe)

Thanks for helping! tr2en is a 0.1 beta, so bug reports from real use are the most valuable contribution.

## Reporting bugs

Use the [bug report form](https://github.com/PolatOzaslan21/tr2en/issues/new/choose). **Don't paste private text you translated** — write a similar made-up example — and never share an API key. Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## Development setup

Windows 10/11, Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/):

```powershell
git clone https://github.com/PolatOzaslan21/tr2en
cd tr2en
uv run --extra test --extra yerel --extra uygulama pytest -q
baslat.cmd   # run the app with a console
```

Tests run on Windows in GitHub Actions for every push and pull request.

## Pull requests

- Keep a PR to one change, and open an issue first for bigger features.
- Add or update tests; all tests must pass.
- Changing the safety layer (`korumalar.py`, `cikti.py`)? Write the failing test first. A translation that loses a negation must never be pasted.
- Never log or store the user's text, and never write API keys anywhere (refer to them by environment variable name).
- The code uses Turkish identifiers and comments; please keep that style. More rules: [AGENTS.md](AGENTS.md).
- By contributing you agree your code is released under the [MIT License](LICENSE) and you follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Türkçe

Katkınız için teşekkürler! tr2en 0.1 beta; gerçek kullanımdan gelen hata bildirimleri en değerli katkı.

- **Hata bildirimi:** [form](https://github.com/PolatOzaslan21/tr2en/issues/new/choose) ile. Çevirdiğiniz özel metni yapıştırmayın, benzer bir örnek yazın; API anahtarı paylaşmayın. Güvenlik sorunları için [SECURITY.md](SECURITY.md).
- **Kurulum ve test:** yukarıdaki komutlar (`uv run --extra test --extra yerel --extra uygulama pytest -q`).
- **PR:** tek konu; testler geçmeli; korumalara (`korumalar.py`, `cikti.py`) dokunmadan önce başarısız test yazın; kullanıcı metni kaydedilmez, anahtar yazılmaz. Kod adları Türkçe kalır. Ayrıntılar: [AGENTS.md](AGENTS.md).
- Katkınız [MIT lisansı](LICENSE) ile yayınlanır; [davranış kurallarına](CODE_OF_CONDUCT.md) uyulur.
