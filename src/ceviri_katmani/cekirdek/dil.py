"""Türkçe metin algılama (bağımlılıksız sezgi).

Kod/URL/yol parçaları ``korumalar.maskele`` ile yer tutucuya çevrilip
puanlamaya katılmaz; kalan metin üzerinde harf, sık kelime ve ek
kalıplarına göre puanlama yapılır. Karışık metinler Türkçe sayılır.
"""
from __future__ import annotations

import re

from .korumalar import maskele

_TR_HARF = re.compile("[çğıöşü]")

_TR_KELIMELER = frozenset((
    "ve", "bir", "bu", "için", "ama", "değil", "ile", "da", "de",
    "mı", "mi", "mu", "mü", "ne", "çok", "daha", "gibi", "şu", "o",
    "ben", "sen", "var", "yok", "olarak", "sonra", "önce", "şimdi",
    "nasıl", "neden", "tamam",
    # ek yaygın emir/olay kalıpları (test örnekleri gereği)
    "yapma", "et",
))

_EN_KELIMELER = frozenset((
    "the", "and", "is", "are", "to", "of", "in", "for", "with",
    "this", "that", "it", "you", "not", "be", "do", "does",
))

# Kelime sonu ek kalıpları; arkasından en çok 3 harf daha gelebilir
# (isim hâli ekleri: raporlar + ı).
_EK = re.compile("(?:lar|ler|yor|mış|miş|dır|dir|ını|ini)[a-zçğıöşü]{0,3}$")

_KELIME = re.compile("[a-zçğıöşü]+")
_YER = re.compile(r"ZXQ\d+ZXQ")


def _tr_kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def turkce_mi(metin: str) -> bool:
    """Metin Türkçe mi sezgisel karar verir; karışık metin Türkçe sayılır."""
    if not metin or not metin.strip():
        return False
    maskeli, _ = maskele(metin)
    # Tek başına İngilizce "I" Türkçe küçültmede "ı" olup Türkçe puanı veriyordu.
    maskeli = re.sub(r"\bI\b", "i", maskeli)
    temiz = _YER.sub(" ", _tr_kucuk(maskeli))
    kelimeler = _KELIME.findall(temiz)
    puan = len(_TR_HARF.findall(temiz))
    for kelime in kelimeler:
        if kelime in _TR_KELIMELER:
            puan += 1
        elif kelime in _EN_KELIMELER:
            puan -= 1
        elif _EK.search(kelime):
            puan += 1
    return puan > 0
