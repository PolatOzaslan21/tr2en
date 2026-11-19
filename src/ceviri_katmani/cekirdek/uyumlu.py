"""OpenAI uyumlu uç noktalara çeviri: OpenAI, OpenRouter, Groq, DeepSeek, Mistral, Ollama, LM Studio."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from .anahtar import anahtar_oku
from .cevirmen import CeviriHatasi
from .gemini import DILLER, TALIMAT

_ANAHTAR_KALIBI = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MODEL_KALIBI = re.compile(r"^[^\s\x00-\x1f\x7f]+$")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_YEREL_ADLAR = {"localhost", "127.0.0.1", "::1"}


class UyumluCevirmen:
    def __init__(self, adres: str, model: str, anahtar_degiskeni: str = "",
                 zaman_asimi: float = 15.0, istemci: httpx.Client | None = None,
                 dusunmeyi_kapat: bool = False):
        adres = adres.rstrip("/")
        if not (adres.startswith("https://") or adres.startswith("http://")):
            raise CeviriHatasi("adres http:// ya da https:// ile başlamalı")
        if adres.startswith("http://"):
            konak = urlsplit(adres).hostname or ""
            if konak not in _YEREL_ADLAR:
                raise CeviriHatasi("http:// yalnızca yerel adresler için (anahtar açık gider)")
        if not _MODEL_KALIBI.match(model):
            raise CeviriHatasi("geçersiz model adı")
        if anahtar_degiskeni and not _ANAHTAR_KALIBI.match(anahtar_degiskeni):
            raise CeviriHatasi("geçersiz anahtar değişkeni adı")
        self.adres = adres
        self.model = model
        self.ad = f"uyumlu:{model}"
        self.anahtar_degiskeni = anahtar_degiskeni
        self.istemci = istemci or httpx.Client(timeout=zaman_asimi)
        # Ollama'daki akıl yürüten küçük modeller (qwen3.5 vb.) düşünürken token sınırına takılıp
        # boş "length" dönüyordu; reasoning_effort="none" 22 sn -> 1 sn (19.11.2026 ölçümü).
        # OpenAI'nin normal modelleri bu alanı reddedebilir, bu yüzden isteğe bağlı.
        self.dusunmeyi_kapat = dusunmeyi_kapat

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        anahtar: str | None = None
        if self.anahtar_degiskeni:
            anahtar = anahtar_oku(self.anahtar_degiskeni)
            if not anahtar:
                raise CeviriHatasi(f"{self.anahtar_degiskeni} tanımlı değil")
        talimat = TALIMAT.format(kaynak=DILLER.get(kaynak, kaynak), hedef=DILLER.get(hedef, hedef))
        govde = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": talimat},
                {"role": "user", "content": metin},
            ],
            "temperature": 0,
            "stream": False,
            **({"reasoning_effort": "none"} if self.dusunmeyi_kapat else {}),
        }
        basliklar = {"User-Agent": "tr2en"}
        if anahtar:
            basliklar["Authorization"] = f"Bearer {anahtar}"
        try:
            r = self.istemci.post(f"{self.adres}/chat/completions", headers=basliklar, json=govde)
        except httpx.HTTPError as e:
            raise CeviriHatasi(f"ağ hatası: {type(e).__name__}") from e
        if r.status_code != 200:
            try:
                veri = r.json()
            except ValueError:
                veri = None
            if isinstance(veri, dict):
                hata = veri.get("error")
                mesaj = hata.get("message", "") if isinstance(hata, dict) else (hata or "")
            else:
                mesaj = r.text
            raise CeviriHatasi(f"HTTP {r.status_code}: {str(mesaj)[:120]}")
        try:
            aday = r.json()["choices"][0]
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise CeviriHatasi("beklenmeyen cevap biçimi") from e
        if not isinstance(aday, dict):
            raise CeviriHatasi("beklenmeyen cevap biçimi")
        bitis = aday.get("finish_reason")
        if bitis is not None and bitis != "stop":
            raise CeviriHatasi(f"tamamlanmamış çeviri: {bitis}")
        mesaj = aday.get("message")
        if not isinstance(mesaj, dict):
            raise CeviriHatasi("boş çeviri")
        icerik = mesaj.get("content")
        if not isinstance(icerik, str) or not icerik.strip():
            raise CeviriHatasi("boş çeviri")
        sonuc = _THINK.sub("", icerik).strip()
        if not sonuc:
            raise CeviriHatasi("boş çeviri")
        return sonuc
