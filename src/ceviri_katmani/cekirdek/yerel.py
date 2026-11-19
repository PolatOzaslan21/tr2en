"""Yerel (çevrimdışı) çevirmen — ctranslate2 + sentencepiece."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .bolme import birlestir, parcala
from .cevirmen import CeviriHatasi
from .korumalar import KorumaHatasi

ORTAM_DEGISKENI = "CEVIRI_YEREL_MODEL"
MAX_DECODING_LENGTH = 256


def _varsayilan_klasor() -> Path:
    yerel = os.environ.get("LOCALAPPDATA")
    if yerel:
        return Path(yerel) / "tr2en" / "modeller" / "tc-big-tr-en-int8"
    return Path.home() / ".tr2en" / "modeller" / "tc-big-tr-en-int8"


def _ingilizce_gibi(parca: str) -> bool:
    """Türkçe işareti yok ve en az bir yaygın İngilizce kelime var."""
    from . import dil

    if dil.turkce_mi(parca):
        return False
    kelimeler = re.findall(r"[a-z]+", parca.lower())
    return any(k in dil._EN_KELIMELER for k in kelimeler)


class YerelCevirmen:
    """İlk cevir() çağrısında modeli yükleyen çevrimdışı tr→en çevirmeni."""

    def __init__(self, model_klasoru: str | None = None):
        klasor = model_klasoru or os.environ.get(ORTAM_DEGISKENI) or str(_varsayilan_klasor())
        self.klasor = klasor
        self.ad = f"yerel:{Path(klasor).name}"
        self._translator = None
        self._src = None
        self._tgt = None

    def _yukle(self) -> None:
        if self._translator is not None:
            return
        if not Path(self.klasor).is_dir():
            raise CeviriHatasi(f"model klasörü yok: {self.klasor}")
        try:
            import ctranslate2
            from sentencepiece import SentencePieceProcessor
        except ImportError as e:
            raise CeviriHatasi("yerel çevirmen için: uv sync --extra yerel") from e
        klasor = Path(self.klasor)
        try:
            self._translator = ctranslate2.Translator(
                str(klasor), device="cpu", compute_type="int8",
                inter_threads=1, intra_threads=4,
            )
            self._src = SentencePieceProcessor(model_file=str(klasor / "source.spm"))
            self._tgt = SentencePieceProcessor(model_file=str(klasor / "target.spm"))
        except Exception as e:
            raise CeviriHatasi(f"yerel model yüklenemedi: {e}") from e

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        if kaynak != "tr" or hedef != "en":
            raise CeviriHatasi("yerel model yalnızca tr->en")
        if not metin.strip():
            return metin
        satir_parcalari = parcala(metin)
        girdiler: list[str] = []
        konumlar: list[tuple[int, int]] = []
        for satir_i, parcalar in enumerate(satir_parcalari):
            for parca_i, parca in enumerate(parcalar):
                if _ingilizce_gibi(parca):
                    continue  # zaten İngilizce parça olduğu gibi kalır (önceki çeviriyle karışık seçim)
                girdiler.append(parca)
                konumlar.append((satir_i, parca_i))
        if not girdiler:
            # çevrilecek parça yok -> özgün metni aynen döndür (model yüklenmez)
            return metin
        self._yukle()
        kodlanmis = [self._src.encode(parca, out_type=str) + ["</s>"] for parca in girdiler]
        ceviriler = self._translator.translate_batch(
            kodlanmis, beam_size=4, max_decoding_length=MAX_DECODING_LENGTH,
        )
        cikti = [list(p) for p in satir_parcalari]
        for (satir_i, parca_i), cevirilen in zip(konumlar, ceviriler):
            tokenlar = [t for t in cevirilen.hypotheses[0] if t != "</s>"]
            if len(tokenlar) >= MAX_DECODING_LENGTH:
                raise KorumaHatasi("yerel çeviri kesildi")
            cikti[satir_i][parca_i] = self._tgt.decode(tokenlar)
        return birlestir(cikti)

    def bosalt(self) -> None:
        """Modeli bellekten atar."""
        self._translator = None
        self._src = None
        self._tgt = None
