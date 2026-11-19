"""Çeviri çıktısı temizleme ve doğrulama.

Sıra: kırp -> kod sarısı -> önsöz -> tırnak sarısı -> uzunluk doğrulama.
"""
from __future__ import annotations

import re

from .korumalar import KorumaHatasi

_ONSOZ = re.compile(
    r"(?:"
    r"here(?:'s| is) the translation\b[ \t]*:?"
    r"|translation\b[ \t]*:"
    r"|sure\b[ \t]*[,!:]"
    r"|certainly\b[ \t]*[,!:]*"
    r")[ \t]*",
    re.IGNORECASE,
)


def temizle_ve_dogrula(girdi: str, cikti: str) -> str:
    """Çıktıyı temizler; uzunluk şüpheliyse ya da sonuç boşsa KorumaHatasi fırlatır."""
    g = girdi.strip()
    sonuc = cikti.strip()
    sonuc = _kod_sarisi_kaldir(g, sonuc)
    sonuc = _onsoz_kaldir(sonuc)
    sonuc = _tirnak_sarisi_kaldir(g, sonuc)
    if not sonuc.strip():
        raise KorumaHatasi("çeviri çıktısı boş")
    _uzunluk_dogrula(g, sonuc)
    return sonuc


def _kod_sarisi_kaldir(girdi: str, cikti: str) -> str:
    """Çıktı tamamen ``` ile sarılıysa ve girdi sarılı değilse sarıyı kaldırır."""
    if not (cikti.startswith("```") and cikti.endswith("```") and len(cikti) >= 6):
        return cikti
    if girdi.startswith("```") and girdi.endswith("```") and len(girdi) >= 6:
        return cikti
    icerik = cikti[3:-3]
    if not icerik.startswith("\n"):
        icerik = icerik.partition("\n")[2]
    return icerik.strip()


def _onsoz_kaldir(cikti: str) -> str:
    """Baştaki önsöz satırlarını kaldırır; en fazla 5 tur dener.

    Kural: önsöz yalnızca (a) iki nokta ile bitiyorsa ya da (b) satırın
    tamamı önsözden ibaretse (ayrı satır) kaldırılır. Aynı satırda devam eden
    gerçek çeviri silinmez.
    """
    for _ in range(5):
        ham = cikti.lstrip()
        if not ham:
            return ""
        satir, _, digerleri = ham.partition("\n")
        m = _ONSOZ.match(satir)
        if not m:
            return ham
        son = satir[m.end():]
        if m.group(0).rstrip().endswith(":"):
            # önsöz iki nokta ile bitiyor -> satırın kalanı gerçek çeviri
            cikti = son.lstrip() + ("\n" + digerleri if digerleri else "")
        elif not son.strip():
            # önsöz tek başına bir satır -> satırı düşür, sonrakine geç
            cikti = digerleri
        elif _ONSOZ.match(son.lstrip()):
            # "Sure! Here is the translation:" gibi zincir önsöz -> kalanı işle
            cikti = son.lstrip() + ("\n" + digerleri if digerleri else "")
        else:
            # aynı satırda gerçek çeviri var -> dokunma
            return ham
        if not cikti.strip():
            return ""
    return cikti.lstrip()


def _iki_nokta(son: str, taban: int) -> int | None:
    """Önsözden sonraki iki noktanın konumu; bulunamazsa None.

    Doğrudan ':' kabul edilir; aksi hâlde yalnızca kısa ve yol benzeri
    olmayan aralarda aranır (C:\\Users gibi sürdü etiketleri korunur).
    """
    bosluksuz = son.lstrip()
    if bosluksuz.startswith(":"):
        return taban + (len(son) - len(bosluksuz)) + 1
    c = son.find(":")
    oncesi = son[:c] if c >= 0 else ""
    if (
        0 <= c <= 40
        and "\\" not in oncesi
        and "//" not in oncesi
        and not re.search(r"\b[A-Za-z]$", oncesi)
    ):
        return taban + c + 1
    return None


def _tirnak_sarisi_kaldir(girdi: str, cikti: str) -> str:
    """Girdi tırnaksızsa ve çıktı tamamen çift tırnakla sarılıysa kaldırır."""
    if girdi.startswith('"'):
        return cikti
    if len(cikti) >= 2 and cikti.startswith('"') and cikti.endswith('"'):
        return cikti[1:-1].strip()
    return cikti


def _uzunluk_dogrula(girdi: str, cikti: str) -> None:
    if len(girdi) >= 20:
        oran = len(cikti) / len(girdi)
        if not 0.4 <= oran <= 2.5:
            raise KorumaHatasi("çıktı uzunluğu şüpheli")
    elif len(cikti) > 80:
        raise KorumaHatasi("çıktı uzunluğu şüpheli")
