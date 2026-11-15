"""Son işlemler geçmişi (metin içeriği asla saklanmaz)."""
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Islem:
    saat: str
    tur: str
    durum: str
    cevirmen: str | None = None
    sure_sn: float | None = None
    giris: int | None = None
    cikis: int | None = None
    ayrinti: str | None = None

    def satir(self) -> str:
        parcalar = [self.saat, self.tur, self.durum]
        if self.cevirmen:
            parcalar.append(self.cevirmen.split(":", 1)[0])
        if self.sure_sn is not None:
            parcalar.append(f"{self.sure_sn:.1f} sn")
        if self.giris is not None and self.cikis is not None:
            parcalar.append(f"{self.giris}→{self.cikis} kr")
        elif self.giris is not None:
            parcalar.append(f"{self.giris} kr")
        elif self.cikis is not None:
            parcalar.append(f"{self.cikis} kr")
        satir = "  ".join(parcalar)
        if self.ayrinti:
            satir += f" ({self.ayrinti[:60]})"
        return satir


class Gecmis:
    def __init__(self, en_fazla: int = 20):
        self.en_fazla = max(0, int(en_fazla))
        self._islemler: list[Islem] = []
        self._kilit = threading.Lock()

    def ekle(self, islem: Islem) -> None:
        with self._kilit:
            self._islemler.insert(0, islem)
            if len(self._islemler) > self.en_fazla:
                del self._islemler[self.en_fazla:]

    def liste(self) -> list[Islem]:
        with self._kilit:
            return list(self._islemler)

    def satirlar(self) -> list[str]:
        return [islem.satir() for islem in self.liste()]

    def temizle(self) -> None:
        with self._kilit:
            self._islemler.clear()
