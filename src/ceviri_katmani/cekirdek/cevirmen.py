"""Ortak çevirmen arayüzü ve geri düşmeli zincir."""
from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class CeviriHatasi(Exception):
    """Çevirmen bu metni çeviremedi (kota, ağ, anahtar yok...)."""


class Cevirmen(Protocol):
    ad: str

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str: ...


class CevirmenZinciri:
    """Sırayla dener; biri hata verirse sonrakine geçer."""

    def __init__(self, cevirmenler: list[Cevirmen]):
        if not cevirmenler:
            raise ValueError("En az bir çevirmen gerekli")
        self.cevirmenler = cevirmenler
        self.son_kullanilan: str | None = None

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        if not metin.strip():
            return metin
        hatalar = []
        for c in self.cevirmenler:
            try:
                sonuc = c.cevir(metin, kaynak, hedef)
                self.son_kullanilan = c.ad
                return sonuc
            except CeviriHatasi as e:
                log.warning("%s başarısız: %s", c.ad, e)
                hatalar.append(f"{c.ad}: {e}")
        raise CeviriHatasi("Hiçbir çevirmen çalışmadı → " + " | ".join(hatalar))
