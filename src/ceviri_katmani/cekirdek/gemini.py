"""Gemini API çevirmeni (Google AI Studio ücretsiz anahtarı)."""
from __future__ import annotations

import httpx

from .anahtar import anahtar_oku
from .cevirmen import CeviriHatasi

DILLER = {"tr": "Turkish", "en": "English"}
TALIMAT = (
    "Translate the user's {kaynak} text to {hedef}. Output ONLY the translation, nothing else. "
    "Keep code, file paths, URLs, commands and technical terms unchanged. "
    "Preserve negations and the exact meaning of instructions."
)
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiCevirmen:
    def __init__(self, model: str = "gemini-3.5-flash-lite", anahtar_degiskeni: str = "GEMINI_API_KEY",
                 zaman_asimi: float = 15.0, istemci: httpx.Client | None = None):
        self.model = model
        self.ad = f"gemini:{model}"
        self.anahtar_degiskeni = anahtar_degiskeni
        self.istemci = istemci or httpx.Client(timeout=zaman_asimi)

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        anahtar = anahtar_oku(self.anahtar_degiskeni)
        if not anahtar:
            raise CeviriHatasi(f"{self.anahtar_degiskeni} tanımlı değil")
        talimat = TALIMAT.format(kaynak=DILLER.get(kaynak, kaynak), hedef=DILLER.get(hedef, hedef))
        gemma = "gemma" in self.model  # Gemma sistem talimatını desteklemiyor
        govde: dict = {
            "contents": [{"role": "user", "parts": [{"text": f"{talimat}\n\nText:\n{metin}" if gemma else metin}]}],
            "generationConfig": {"temperature": 0},
        }
        if not gemma:
            govde["systemInstruction"] = {"parts": [{"text": talimat}]}
        try:
            r = self.istemci.post(URL.format(model=self.model), headers={"x-goog-api-key": anahtar}, json=govde)
        except httpx.HTTPError as e:
            raise CeviriHatasi(f"ağ hatası: {type(e).__name__}") from e
        if r.status_code != 200:
            try:
                mesaj = r.json().get("error", {}).get("message", "")[:120]
            except ValueError:
                mesaj = r.text[:120]
            raise CeviriHatasi(f"HTTP {r.status_code}: {mesaj}")
        try:
            parcalar = r.json()["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, ValueError) as e:
            raise CeviriHatasi("beklenmeyen cevap biçimi") from e
        sonuc = "".join(p.get("text", "") for p in parcalar if not p.get("thought")).strip()
        if not sonuc:
            raise CeviriHatasi("boş çeviri")
        return sonuc
