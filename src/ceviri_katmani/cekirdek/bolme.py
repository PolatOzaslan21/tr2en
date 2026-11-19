"""Cümle/parça bölme: uzun satırları çevirmenin sessizce kesmemesi için böler.

Strateji (bir satır için):
1. ``.`` ``!`` ``?`` ``…`` sonrası boşluktan böl; kısaltmaları (vb. ör. örn.
   bkz. sn. dr. prof.), sayı/sürümleri (v1.2) ve nokta içeren dosya adlarını
   bölme. ``ZXQ{i}ZXQ`` yer tutucuları asla bölünmez (boşluksuz tek belirteç).
2. Hâlâ ``en_fazla_kelime`` uzunsa önce virgülden böl.
3. Sonra bağlaçlardan önce böl (bağlaç sonraki parçada kalır).
4. Son çare kelime sınırından eşit böl.
"""
from __future__ import annotations

import re

_CUMLE_SONU = ".!?…"

_ABREVLER = frozenset({"vb", "ör", "örn", "bkz", "sn", "dr", "prof"})

_BAGLACLAR = ("ama", "fakat", "ve", "sonra", "çünkü", "yani", "ancak")

_BAGLAC_KALIBI = re.compile(
    r"(?<!\w)(" + "|".join(_BAGLACLAR) + r")(?!\w)", re.IGNORECASE
)


def _abrev_mi(satir: str, i: int) -> bool:
    """``i`` konumundaki noktanın kısaltma/sayı sonu olup olmadığını söyler."""
    j = i - 1
    while j >= 0 and satir[j].isalnum():
        j -= 1
    token = satir[j + 1 : i]
    if not token:
        return False
    if token[-1].isdigit():
        return True
    return token.lower() in _ABREVLER


def _cumle_bol(satir: str) -> list[str]:
    parcalar: list[str] = []
    baslangic = 0
    i = 0
    n = len(satir)
    while i < n:
        ch = satir[i]
        sonraki = satir[i + 1] if i + 1 < n else ""
        # Yapıştırmadan sonra boşluksuz kalan cümleler ("you?bugün") de bölünür (Polat'ın testi, 19.11.2026);
        # "." için yalnızca küçük harf + Büyük harf ("bitti.Sonra") — "v1.2", "example.com" bölünmesin.
        bitisik = bool(sonraki) and sonraki.isalpha() and (
            ch in "!?…" or (ch == "." and i > 0 and satir[i - 1].islower() and sonraki.isupper())
        )
        if ch in _CUMLE_SONU and (i + 1 >= n or sonraki.isspace() or bitisik):
            if ch == "." and _abrev_mi(satir, i):
                i += 1
                continue
            parcalar.append(satir[baslangic : i + 1].strip())
            j = i + 1
            while j < n and satir[j].isspace():
                j += 1
            baslangic = j
            i = j
            continue
        i += 1
    kalan = satir[baslangic:].strip()
    if kalan:
        parcalar.append(kalan)
    return parcalar


def _virgulden_bol(parca: str) -> list[str]:
    if "," not in parca:
        return [parca]
    parcalar = parca.split(",")
    sonuc: list[str] = []
    for i, k in enumerate(parcalar):
        if i < len(parcalar) - 1:
            sonuc.append(k + ",")
        else:
            sonuc.append(k)
    return sonuc


def _baglactan_bol(parca: str) -> list[str]:
    eslesmeler = list(_BAGLAC_KALIBI.finditer(parca))
    if not eslesmeler:
        return [parca]
    sonuc: list[str] = []
    baslangic = 0
    for m in eslesmeler:
        onceki = parca[baslangic : m.start()].strip()
        if onceki:
            sonuc.append(onceki)
        baslangic = m.start()
    son = parca[baslangic:].strip()
    if son:
        sonuc.append(son)
    return sonuc if len(sonuc) > 1 else [parca]


def _kelime_sinirindan_bol(kelimeler: list[str], en_fazla: int) -> list[str]:
    return [
        " ".join(kelimeler[i : i + en_fazla])
        for i in range(0, len(kelimeler), en_fazla)
    ]


def _uzun_bol(parca: str, en_fazla: int) -> list[str]:
    parca = parca.strip()
    if not parca:
        return []
    if len(parca.split()) <= en_fazla:
        return [parca]
    for ayirici in (_virgulden_bol, _baglactan_bol):
        parcalar = [p.strip() for p in ayirici(parca) if p.strip()]
        if len(parcalar) > 1:
            sonuc: list[str] = []
            for p in parcalar:
                sonuc.extend(_uzun_bol(p, en_fazla))
            return sonuc
    return _kelime_sinirindan_bol(parca.split(), en_fazla)


def _satir_bol(satir: str, en_fazla: int) -> list[str]:
    if not satir.strip():
        return []
    sonuc: list[str] = []
    for cumle in _cumle_bol(satir):
        sonuc.extend(_uzun_bol(cumle, en_fazla))
    return sonuc


def parcala(metin: str, en_fazla_kelime: int = 40) -> list[list[str]]:
    """Metni satırlara, her satırı da parçalara böler; boş satır -> ``[]``."""
    return [_satir_bol(satir, en_fazla_kelime) for satir in metin.split("\n")]


def birlestir(parcalar: list[list[str]]) -> str:
    """Her satırın parçalarını tek boşlukla, satırları ``\\n`` ile birleştirir."""
    return "\n".join(" ".join(satir) for satir in parcalar)
