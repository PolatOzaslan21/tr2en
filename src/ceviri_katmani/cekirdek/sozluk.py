"""Teknik sözlük ön işlemi: Türkçe geliştirme ifadelerini yer tutucuya çevirir.

Yer tutucu biçimi ``QZS{i}QZS``. Gerekçe: yerel Opus-MT modeli (CTranslate2 +
sentencepiece) ile gerçek ölçüm yapıldı, aşağıdaki biçim her iki çevirmenden de
birebir korunarak çıktı::

    "Değişiklikleri QZS0QZS ve QZS1QZS."  ->  "Changes to QZS0QZS and QZS1QZS."
    "Lütfen QZS0QZS yap."                 ->  "Please make QZS0QZS."

Bu yüzden ``korumalar`` modülündeki ``ZXQ{i}ZXQ`` biçiminden farklı bir önek
kullanılır; böylece iki katmanın yer tutucuları karışmaz.

Eşleşme kuralları: büyük/küçük harf duyarsız (Türkçe İ/I doğru), kelime başı
sınırlı, son kelimeye gelen çekim ekleri tolere edilir ve silinir
("commit at", "commit atın", "commit attım" → commit).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .korumalar import KorumaHatasi

_PAKET_DOSYASI = Path(__file__).with_name("sozluk.tsv")

_AYRAC = "QZS"
_YER_TAMAM = re.compile(r"QZS(\d+)QZS", re.IGNORECASE)

_HARFLER = "a-z0-9çğıöşü_"

# Yalnızca çekim eki parçaları. Tek başına "k", "c" gibi harfler bilerek yok:
# "açık" ve "derleyici" gibi kelimelerin yanlış eşleşmesini engeller.
_EK_LISTE = (
    # çoğul + iyelik + hal
    "lardan", "lerden", "ların", "lerin", "larda", "lerde", "ları", "leri",
    "lar", "ler",
    # iyelik
    "sından", "sinden", "sında", "sinde", "sını", "sini", "sına", "sine",
    "ımız", "imiz", "umuz", "ümüz", "ınız", "iniz", "unuz", "ünüz",
    "sı", "si", "su", "sü", "ım", "im", "um", "üm",
    # hal ekleri
    "nın", "nin", "nun", "nün", "dan", "den", "tan", "ten",
    "da", "de", "ta", "te", "ya", "ye", "la", "le",
    "ın", "in", "un", "ün", "ı", "i", "u", "ü", "a", "e",
    # zaman / kip
    "acaktır", "ecektir", "acağı", "eceği", "acak", "ecek",
    "madan", "meden", "malı", "meli", "mış", "miş", "muş", "müş",
    "ıyor", "iyor", "uyor", "üyor", "yor",
    "dık", "dik", "duk", "dük", "tık", "tik", "tuk", "tük",
    "dı", "di", "du", "dü", "tı", "ti", "tu", "tü",
    "mak", "mek", "ma", "me",
    # zarf-fiil
    "arak", "erek", "ınca", "ince", "unca", "ünce", "ıp", "ip", "up", "üp",
    "ar", "er", "ır", "ir", "ur", "ür", "ken",
    # edilgen / ettirgen
    "ıl", "il", "ul", "ül",
    # kişi ve ek fiil
    "sınız", "siniz", "sunuz", "sünüz", "sın", "sin", "sun", "sün",
    "ız", "iz", "uz", "üz", "dır", "dir", "dur", "dür",
    "tır", "tir", "tur", "tür", "ki", "m",
)

def _desen_parcasi(kelime: str) -> str:
    """Küçük harfli parçayı regex'e çevirir; i/ı ayrımını esnek tutar.

    Türkçede "I" küçültmesi "ı", İngilizce kökenli tamamı büyük kelimelerde
    ("COMMIT") ise "i" beklenir; ikisi de aynı ifadeye eşlensin diye i/ı aynı
    karakter sınıfına alınır.
    """
    return "".join("[iı]" if k in "iı" else re.escape(k) for k in kelime)


_EK = "(?:" + "|".join(
    _desen_parcasi(parca) for parca in sorted(_EK_LISTE, key=len, reverse=True)
) + "){0,4}"


def _kucuk_tr(metin: str) -> str:
    """Türkçe kurallarına uygun küçük harfe çevirir (uzunluk korunur).

    ``str.lower`` "İ" harfini iki kod noktasına açtığı için karakter karakter
    eşlenir; böylece normalize metindeki konumlar orijinal metinle birebir
    örtüşür ve eşleşme aralıkları doğrudan orijinal metne uygulanabilir.
    """
    parcalar: list[str] = []
    for karakter in metin:
        if karakter == "İ":
            parcalar.append("i")
        elif karakter == "I":
            parcalar.append("ı")
        else:
            kucuk = karakter.lower()
            parcalar.append(kucuk if len(kucuk) == 1 else karakter)
    return "".join(parcalar)


def _kullanici_dosyasi() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "ceviri-katmani" / "sozluk.tsv"


def _satirlari_oku(dosya: Path) -> list[tuple[str, str]]:
    if not dosya.is_file():
        return []
    kayitlar: list[tuple[str, str]] = []
    for satir in dosya.read_text(encoding="utf-8-sig").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "\t" not in satir:
            continue
        turkce, ingilizce = satir.split("\t", 1)
        turkce, ingilizce = turkce.strip(), ingilizce.strip()
        if turkce and ingilizce:
            kayitlar.append((turkce, ingilizce))
    return kayitlar


def _sirala(kayitlar: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(kayitlar, key=lambda p: (-len(p[0].split()), -len(p[0])))


def sozluk_yukle(ek_dosya: str | None = None) -> list[tuple[str, str]]:
    """Paket sözlüğünü ve varsa kullanıcı sözlüğünü birleştirir.

    ``ek_dosya`` verilmezse ``%APPDATA%/ceviri-katmani/sozluk.tsv`` okunur.
    Kullanıcı dosyası aynı ifadeyi geçersiz kılar; uzun ifadeler önce gelir.
    """
    kayitlar = _satirlari_oku(_PAKET_DOSYASI)
    ek = Path(ek_dosya) if ek_dosya is not None else _kullanici_dosyasi()
    kayitlar.extend(_satirlari_oku(ek))

    birlesik: dict[str, tuple[str, str]] = {}
    for turkce, ingilizce in kayitlar:
        birlesik[_kucuk_tr(turkce)] = (turkce.strip(), ingilizce.strip())
    return _sirala(list(birlesik.values()))


def _ifade_deseni(ifade: str) -> str:
    kelimeler = ifade.split()
    if not kelimeler:
        return ""
    govde = _desen_parcasi(kelimeler[-1]) + _EK
    if len(kelimeler) > 1:
        govde = (
            r"\s+".join(_desen_parcasi(k) for k in kelimeler[:-1]) + r"\s+" + govde
        )
    return rf"(?<![{_HARFLER}]){govde}(?![{_HARFLER}])"


class SozlukluCevirmen:
    """Sözlük ön işlemini içteki çevirmenin önüne koyan sarmalayıcı."""

    def __init__(self, ic, sozluk: list[tuple[str, str]] | None = None):
        self.ic = ic
        self.ad = ic.ad
        kayitlar = _sirala(list(sozluk)) if sozluk is not None else sozluk_yukle()
        self.sozluk = kayitlar
        self._ingilizceler: list[str] = []
        desenler: list[str] = []
        for turkce, ingilizce in kayitlar:
            desen = _ifade_deseni(_kucuk_tr(turkce))
            if not desen:
                continue
            desenler.append(f"(?P<e{len(self._ingilizceler)}>{desen})")
            self._ingilizceler.append(ingilizce)
        self._desen = re.compile("|".join(desenler)) if desenler else None

    def _maskele(self, metin: str) -> tuple[str, list[str]]:
        if self._desen is None:
            return metin, []
        kucuk = _kucuk_tr(metin)
        parcalar: list[str] = []
        cikti: list[str] = []
        son = 0
        for m in self._desen.finditer(kucuk):
            if m.lastgroup is None:
                continue
            indeks = len(parcalar)
            parcalar.append(self._ingilizceler[int(m.lastgroup[1:])])
            cikti.append(metin[son : m.start()])
            cikti.append(f"{_AYRAC}{indeks}{_AYRAC}")
            son = m.end()
        if not parcalar:
            return metin, []
        cikti.append(metin[son:])
        return "".join(cikti), parcalar

    @staticmethod
    def _geri_koy(metin: str, parcalar: list[str]) -> str:
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
            raise KorumaHatasi(f"sözlük yer tutucusu kayboldu: {eksik}")
        return sonuc

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        if kaynak != "tr" or hedef != "en" or self._desen is None:
            return self.ic.cevir(metin, kaynak, hedef)
        maskeli, parcalar = self._maskele(metin)
        if not parcalar:
            return self.ic.cevir(metin, kaynak, hedef)
        return self._geri_koy(self.ic.cevir(maskeli, kaynak, hedef), parcalar)
