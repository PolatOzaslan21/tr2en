"""CevirmenZinciri ve CeviriHatasi davranış testleri."""
from __future__ import annotations

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi, CevirmenZinciri


class SahteCevirmen:
    def __init__(self, ad: str, sonuc: str | None = None, hata: Exception | None = None):
        self.ad = ad
        self.sonuc = sonuc
        self.hata = hata
        self.cagrilar: list[tuple[str, str, str]] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append((metin, kaynak, hedef))
        if self.hata is not None:
            raise self.hata
        return self.sonuc if self.sonuc is not None else metin


def test_ilk_cevirmen_basarili_olunca_son_kullanilan_first():
    birinci = SahteCevirmen("birinci", sonuc="Hello")
    ikinci = SahteCevirmen("ikinci", sonuc="Salut")
    zincir = CevirmenZinciri([birinci, ikinci])

    assert zincir.cevir("Merhaba") == "Hello"
    assert zincir.son_kullanilan == "birinci"
    assert ikinci.cagrilar == []


def test_ilk_cevirmen_hata_verince_ikinciye_gecer():
    birinci = SahteCevirmen("birinci", hata=CeviriHatasi("kota"))
    ikinci = SahteCevirmen("ikinci", sonuc="Hello")
    zincir = CevirmenZinciri([birinci, ikinci])

    assert zincir.cevir("Merhaba", "tr", "en") == "Hello"
    assert zincir.son_kullanilan == "ikinci"
    assert birinci.cagrilar == [("Merhaba", "tr", "en")]
    assert ikinci.cagrilar == [("Merhaba", "tr", "en")]


def test_ilk_cevirmen_basarisiz_olunca_son_kullanilan_degismez():
    birinci = SahteCevirmen("birinci", hata=CeviriHatasi("ağ"))
    zincir = CevirmenZinciri([birinci])

    with pytest.raises(CeviriHatasi):
        zincir.cevir("Merhaba")
    assert zincir.son_kullanilan is None


def test_tum_cevirmenler_hata_verirse_ceviri_hatasi():
    birinci = SahteCevirmen("birinci", hata=CeviriHatasi("kota"))
    ikinci = SahteCevirmen("ikinci", hata=CeviriHatasi("anahtar yok"))
    zincir = CevirmenZinciri([birinci, ikinci])

    with pytest.raises(CeviriHatasi) as bilgi:
        zincir.cevir("Merhaba")

    mesaj = str(bilgi.value)
    assert "birinci" in mesaj and "kota" in mesaj
    assert "ikinci" in mesaj and "anahtar yok" in mesaj
    assert zincir.son_kullanilan is None
    assert len(birinci.cagrilar) == 1
    assert len(ikinci.cagrilar) == 1


@pytest.mark.parametrize("metin", ["", "   ", "\n\t "])
def test_bos_metin_oldugu_gibi_doner(metin: str):
    birinci = SahteCevirmen("birinci", sonuc="Hello")
    zincir = CevirmenZinciri([birinci])

    assert zincir.cevir(metin) == metin
    assert birinci.cagrilar == []
    assert zincir.son_kullanilan is None


def test_bos_liste_value_error_firlatir():
    with pytest.raises(ValueError):
        CevirmenZinciri([])
