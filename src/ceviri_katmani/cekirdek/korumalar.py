"""Çeviri korumaları: kod/URL/yol/negasyon koruma katmanı.

Yer tutucu biçimi: ``ZXQ{i}ZXQ`` (ör. ZXQ0ZXQ, ZXQ1ZXQ).

Gerekçe: yerel Opus-MT modeli (CTranslate2 + sentencepiece) sembollü yer
tutucuları bozuyor — gerçek modelle denendi:
    "⟦0⟧ ..."  ->  "⁇ 0 ⁇ ..."      (parantezler ⁇ oldu)
    "__0__ ..." -> "⁇ 0_ ..."       (alt çizgi koptu)
    "[[0]] ..." -> "[0] ..."        (parantezler azaldı)
    "ZXQ0ZXQ ..." -> "ZXQ0ZXQ ..."  (aynen korundu)
Saf ASCII harf+rakam olan ZXQ öneki her iki çevirmenden de bozulmadan çıkıyor;
günlük metinde bulunmadığından çakışma riski yok.
"""
from __future__ import annotations

import re

from .cevirmen import CeviriHatasi


class KorumaHatasi(CeviriHatasi):
    """Korumalı çeviri sırasında yer tutucu ya da negasyon kaybı."""


_AYRAC = "ZXQ"
_HARF_KUCUK = "a-zçğıöşü"


def _yer(indeks: int) -> str:
    return f"{_AYRAC}{indeks}{_AYRAC}"


_YER_TAMAM = re.compile(r"ZXQ(\d+)ZXQ")


# Öncelik sırası alternasyon sırasıyla aynıdır; finditer soldan sağa,
# çakışmayan eşleşmeler döndürdüğü için iç içe eşleşme olmaz.
_PARCALAR = re.compile(
    # 1) ``` ile çevrili kod bloğu (dil etiketi dahil, çok satırlı)
    r"```[^\n]*\n.*?```"
    # 2) satır içi kod
    r"|`[^`\n]+`"
    # 3) URL
    r"|https?://[^\s]+"
    # 4) dosya yolu: / ya da \ içeren (sürücü harfli dahil)
    r"|[^\s]*[/\\][^\s]*"
    # 5) uzantılı dosya adı
    r"|[A-Za-z0-9_][A-Za-z0-9_.+-]*\.[A-Za-z][A-Za-z0-9]*"
    # 6) ortam değişkeni
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|%[A-Za-z_][A-Za-z0-9_]*%"
    # 7) komut bayrağı
    r"|--?[A-Za-z][A-Za-z0-9-]*",
    re.DOTALL,
)

_SON_NOKTALAMA = ".,;:!?"


def maskele(metin: str) -> tuple[str, list[str]]:
    """Çevrilmemesi gereken parçaları yer tutucuyla değiştirir.

    (maskeli_metin, parcalar) döner; parcalar[i] i'nci yer tutucunun
    orijinal metnidir. Maskelenecek bir şey yoksa (metin, []) döner.
    """
    parcalar: list[str] = []
    cikti: list[str] = []
    son = 0
    for m in _PARCALAR.finditer(metin):
        ham = m.group(0)
        temiz = ham.rstrip(_SON_NOKTALAMA)
        if not temiz:
            continue
        indeks = len(parcalar)
        parcalar.append(temiz)
        cikti.append(metin[son : m.start()])
        cikti.append(_yer(indeks))
        son = m.end() - (len(ham) - len(temiz))
    cikti.append(metin[son:])
    return "".join(cikti), parcalar


def geri_koy(metin: str, parcalar: list[str]) -> str:
    """Yer tutucuları orijinal parçalarla değiştirir.

    Çeviri modeli yer tutucunun etrafına boşluk eklemiş/silmiş olabilir;
    eşleşme yer tutucu simgesinin kendisinde arandığı için bu tolere edilir.
    Herhangi bir yer tutucu bulunamazsa KorumaHatasi fırlatır.
    """
    if not parcalar:
        return metin
    bulunan: set[int] = set()

    def degistir(m: re.Match) -> str:
        indeks = int(m.group(1))
        if indeks < len(parcalar):
            bulunan.add(indeks)
            return parcalar[indeks]
        return m.group(0)

    sonuc = _YER_TAMAM.sub(degistir, metin)
    eksik = [i for i in range(len(parcalar)) if i not in bulunan]
    if eksik:
        raise KorumaHatasi(f"yer tutucu bulunamadı: {eksik}")
    return sonuc


_NEG_SABIT = ("değil", "yok", "asla", "sakın", "hiçbir", "hiç")

_NEG_EK = re.compile(
    rf"[{_HARF_KUCUK}]+(?:"
    # kişi/zaman ekleri gelebilir: istemiyorum, yapmadık, güncellemeyeceğiz
    rf"(?:m[ıiuü]yor|m[ae]d[ıi]|m[ae]y[ae]c[ae][kğ])[{_HARF_KUCUK}]*"
    # -maz/-mez yalnızca sonda ya da s/l ile devam (amazon gibi yanlış eşleşmeyi önler)
    rf"|m[ae]z(?:[sl][{_HARF_KUCUK}]*)?"
    rf"|m[ae]d[ae]n|m[ae]m[ae]l[ıi]|m[ae]y[ıi]n|m[ae]s[ıi]n"
    rf")(?![{_HARF_KUCUK}])"
)

_KELIME = re.compile(rf"[{_HARF_KUCUK}]+")

_SONRASI = re.compile(
    rf"\s*(?:[.,;!?]|(?:ama|ve|sadece|yalnızca|fakat)(?![{_HARF_KUCUK}])|$)"
)


def _kucuk_tr(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _kelime_geciyor(metin: str, kelime: str) -> bool:
    return re.search(
        rf"(?<![{_HARF_KUCUK}]){re.escape(kelime)}(?![{_HARF_KUCUK}])", metin
    ) is not None


def olumsuz_tr(metin: str) -> bool:
    """Türkçe metinde olumsuzluk var mı (sezgisel, maskelenmiş metin üzerinde)."""
    m = _kucuk_tr(metin)
    m = re.sub(r"m[ae]d[ae]n\s+önce", "önce", m)
    for kelime in _NEG_SABIT:
        if _kelime_geciyor(m, kelime):
            return True
    if _NEG_EK.search(m):
        return True
    for mm in _KELIME.finditer(m):
        kelime = mm.group(0)
        if len(kelime) < 4 or not kelime.endswith(("ma", "me")):
            continue
        if _SONRASI.match(m, mm.end()):
            return True
    return False


_NEG_EN = re.compile(
    r"\b(?:not|never|no|none|nothing|nor|without|avoid|stop|ignore|skip|neither|cannot)\b"
    r"|n['’]t\b"
    r"|\binstead\s+of\b",
    re.IGNORECASE,
)


def olumsuz_en(metin: str) -> bool:
    """İngilizcede olumsuzluk var mı (büyük/küçük harf duyarsız)."""
    return _NEG_EN.search(metin) is not None


def olumsuzluk_kaybi(tr: str, en: str) -> bool:
    """Türkçe olumsuzken İngilizce olumluysa True."""
    return olumsuz_tr(tr) and not olumsuz_en(en)


def _cikti_kontrol(girdi: str, cikti: str) -> str:
    from .cikti import temizle_ve_dogrula as f  # döngüsel içe aktarmayı önlemek için geç

    return f(girdi, cikti)


temizle_ve_dogrula = _cikti_kontrol


class KorumaliCevirmen:
    """İçteki çevirmeni koruma katmanıyla saran sarmalayıcı."""

    def __init__(self, ic):
        self.ic = ic
        self.ad = ic.ad

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        maskeli, parcalar = maskele(metin)
        ceviri = temizle_ve_dogrula(maskeli, self.ic.cevir(maskeli, kaynak, hedef))
        sonuc = geri_koy(ceviri, parcalar)  # KorumaHatasi yukarı çıkar
        if kaynak == "tr" and olumsuzluk_kaybi(maskeli, ceviri):
            raise KorumaHatasi("olumsuzluk çeviride kayboldu")
        return sonuc
