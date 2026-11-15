"""Yerel (çevrimdışı) çevirmen — ctranslate2 + sentencepiece."""
from __future__ import annotations

import os
from pathlib import Path

from .cevirmen import CeviriHatasi

ORTAM_DEGISKENI = "CEVIRI_YEREL_MODEL"


def _varsayilan_klasor() -> Path:
    yerel = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(yerel) / "ceviri-katmani" / "modeller" / "tc-big-tr-en-int8"


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
        self._yukle()
        satirlar = metin.split("\n")
        girdiler: list[list[str]] = []
        dolu_indeksler: list[int] = []
        for i, satir in enumerate(satirlar):
            if satir.strip():
                girdiler.append(self._src.encode(satir, out_type=str) + ["</s>"])
                dolu_indeksler.append(i)
        cikti = list(satirlar)
        if girdiler:
            ceviriler = self._translator.translate_batch(
                girdiler, beam_size=4, max_decoding_length=256,
            )
            for i, cevirilen in zip(dolu_indeksler, ceviriler):
                tokenlar = [t for t in cevirilen.hypotheses[0] if t != "</s>"]
                cikti[i] = self._tgt.decode(tokenlar)
        return "\n".join(cikti)

    def bosalt(self) -> None:
        """Modeli bellekten atar."""
        self._translator = None
        self._src = None
        self._tgt = None
