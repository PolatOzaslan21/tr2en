"""API anahtarlarını Windows Kimlik Yöneticisi (keyring) içinde saklayan kasa.

Kasa adı SERVIS_ADI, kullanıcı adı bulut servis adıdır ("gemini", "openai", ...).
Arka uç enjekte edilebilir (arka_uc_ayarla); ayarlanmazsa ilk kullanımda
``import keyring`` ile gerçek arka uca bağlanır. keyring yoksa ya da hata
verirse çökmez: oku None, yaz/sil False döner.

ANAHTAR DEĞERİ HİÇBİR YERE YAZDIRILMAZ: loglanmaz, istisna mesajına
eklenmez, hata metinlerinde görünmez.
"""
from __future__ import annotations

from typing import Any

from ..cekirdek.anahtar import anahtar_oku

SERVIS_ADI = "tr2en"

_enjekte_arka_uc: Any = None
_gercek_arka_uc: Any = None
_gercek_arandi = False


def arka_uc_ayarla(nesne: Any) -> None:
    """Kasanın arka ucunu enjekte eder (get_password/set_password/delete_password).

    None verilirse gerçek keyring arka ucuna dönülür.
    """
    global _enjekte_arka_uc, _gercek_arka_uc, _gercek_arandi
    _enjekte_arka_uc = nesne
    if nesne is None:
        _gercek_arka_uc = None
        _gercek_arandi = False


def _arka_uc() -> Any:
    global _gercek_arka_uc, _gercek_arandi
    if _enjekte_arka_uc is not None:
        return _enjekte_arka_uc
    if not _gercek_arandi:
        _gercek_arandi = True
        try:
            import keyring

            _gercek_arka_uc = keyring
        except Exception:
            _gercek_arka_uc = None
    return _gercek_arka_uc


def oku(servis: str) -> str | None:
    """Kasadan anahtar okur; yoksa ya da hata olursa None döner. Değer loglanmaz."""
    uc = _arka_uc()
    if uc is None:
        return None
    try:
        deger = uc.get_password(SERVIS_ADI, servis)
    except Exception:
        return None
    return deger or None


def yaz(servis: str, deger: str) -> bool:
    """Anahtarı kasaya yazar. Boş/boşluklu değeri kaydetmez (False).

    Değerin başındaki/sonundaki boşluklar kırpılır. Hata olursa False döner.
    """
    uc = _arka_uc()
    if uc is None:
        return False
    if not isinstance(deger, str):
        return False
    kirpilmis = deger.strip()
    if not kirpilmis:
        return False
    try:
        uc.set_password(SERVIS_ADI, servis, kirpilmis)
    except Exception:
        return False
    return True


def sil(servis: str) -> bool:
    """Kasadaki anahtarı siler. Yalnızca gerçekten silinirse True döner."""
    uc = _arka_uc()
    if uc is None:
        return False
    if oku(servis) is None:
        return False
    try:
        uc.delete_password(SERVIS_ADI, servis)
    except Exception:
        return False
    return True


def var_mi(servis: str) -> bool:
    """Kasada bu servis için anahtar var mı?"""
    return oku(servis) is not None


def anahtar_bul(servis: str, ortam_degiskeni: str = "") -> str | None:
    """Önce kasadan, orada yoksa ortam değişkeninden okur.

    ortam_degiskeni boşsa ortam değişkeni adımına geçilmez.
    """
    deger = oku(servis)
    if deger:
        return deger
    if ortam_degiskeni:
        return anahtar_oku(ortam_degiskeni)
    return None
