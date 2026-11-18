"""Yerel modeli arka planda indirir — kullanıcı bildirimiyle."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from ..cekirdek import indir
from ..cekirdek.yerel import _varsayilan_klasor

ORTAM_DEGISKENI = "CEVIRI_YEREL_MODEL"

_durum: str = "yok"
_kilit = threading.Lock()


def durum() -> str:
    """İndirme durumu: "yok" | "indiriliyor %NN" | "hazir" | "hata"."""
    global _durum
    with _kilit:
        return _durum


def _durum_ayarla(deger: str) -> None:
    global _durum
    with _kilit:
        _durum = deger


def gerekirse_arkaplanda_indir(
    bildir: Callable[..., None],
    *,
    klasor: Path | None = None,
    indirici=None,
    thread_baslat: bool = True,
) -> threading.Thread | None:
    """Model eksikse arka planda indirir; yoksa None döner."""
    if klasor is None:
        klasor = _varsayilan_klasor()
    klasor = Path(klasor)
    if os.environ.get(ORTAM_DEGISKENI):
        return None
    if indir.model_tam_mi(klasor):
        return None
    indirici = indirici or indir.model_indir

    def calis() -> None:
        _durum_ayarla("indiriliyor %0")
        son_yuzde = 0

        def ilerleme(indirilen: int, toplam: int) -> None:
            nonlocal son_yuzde
            yuzde = int(indirilen * 100 / toplam) if toplam else 100
            if yuzde != son_yuzde:
                son_yuzde = yuzde
                _durum_ayarla(f"indiriliyor %{yuzde}")

        try:
            bildir(
                "Yerel model indiriliyor",
                "Yaklaşık 230 MB, bir kez indirilir. Bu sırada Gemini çalışır.",
            )
            indirici(klasor, ilerleme=ilerleme)
        except Exception as e:
            _durum_ayarla("hata")
            bildir("Yerel model indirilemedi", str(e)[:150], "uyari")
            return
        _durum_ayarla("hazir")
        bildir("Yerel model hazır", "Artık internetsiz de çevirebilirsiniz.")

    thread = threading.Thread(target=calis, daemon=True)
    if thread_baslat:
        thread.start()
    return thread
