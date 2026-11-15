"""gecmis modülü testleri."""
from __future__ import annotations

import threading

import pytest

from ceviri_katmani.uygulama.gecmis import Gecmis, Islem


def test_satir_bicimi() -> None:
    islem = Islem(
        saat="14:03:12",
        tur="tetik",
        durum="cevrildi",
        cevirmen="gemini:gemini-3.5-flash-lite",
        sure_sn=1.2,
        giris=45,
        cikis=52,
    )
    assert islem.satir() == "14:03:12  tetik  cevrildi  gemini  1.2 sn  45→52 kr"


def test_satir_none_alanlar_atlanir() -> None:
    islem = Islem(saat="09:00:00", tur="kisayol", durum="secim-yok")
    assert islem.satir() == "09:00:00  kisayol  secim-yok"


def test_satir_ayrinti_kisaltilir() -> None:
    islem = Islem(
        saat="09:00:00",
        tur="tetik",
        durum="hata",
        ayrinti="x" * 80,
    )
    satir = islem.satir()
    assert satir.endswith("(" + "x" * 60 + ")")
    assert satir.count("x") == 60


def test_satir_ayrinti_kisa_oldugu_gibi() -> None:
    islem = Islem(saat="09:00:00", tur="tetik", durum="hata", ayrinti="kota aşıldı")
    assert islem.satir().endswith("(kota aşıldı)")


def test_satir_tek_olcum() -> None:
    assert Islem(saat="01:02:03", tur="tetik", durum="hata", cikis=7).satir() == (
        "01:02:03  tetik  hata  7 kr"
    )


def test_liste_en_yeni_basta() -> None:
    gecmis = Gecmis()
    for i in range(3):
        gecmis.ekle(Islem(saat=f"00:00:0{i}", tur="tetik", durum="cevrildi"))
    assert [i.saat for i in gecmis.liste()] == ["00:00:02", "00:00:01", "00:00:00"]


def test_sinir_asilinca_en_eski_duser() -> None:
    gecmis = Gecmis(en_fazla=3)
    for i in range(5):
        gecmis.ekle(Islem(saat=f"saat-{i}", tur="tetik", durum="cevrildi"))
    assert [i.saat for i in gecmis.liste()] == ["saat-4", "saat-3", "saat-2"]


def test_sifir_sinir() -> None:
    gecmis = Gecmis(en_fazla=0)
    gecmis.ekle(Islem(saat="01:00:00", tur="tetik", durum="cevrildi"))
    assert gecmis.liste() == []


def test_liste_kopya_doner() -> None:
    gecmis = Gecmis()
    gecmis.ekle(Islem(saat="01:00:00", tur="tetik", durum="cevrildi"))

    disari = gecmis.liste()
    disari.clear()
    assert len(gecmis.liste()) == 1


def test_satirlar() -> None:
    gecmis = Gecmis()
    gecmis.ekle(Islem(saat="01:00:00", tur="tetik", durum="cevrildi", cevirmen="yerel:tc-big"))
    gecmis.ekle(Islem(saat="01:00:05", tur="kisayol", durum="guvensiz"))
    assert gecmis.satirlar() == [
        "01:00:05  kisayol  guvensiz",
        "01:00:00  tetik  cevrildi  yerel",
    ]


def test_temizle() -> None:
    gecmis = Gecmis()
    gecmis.ekle(Islem(saat="01:00:00", tur="tetik", durum="cevrildi"))
    gecmis.temizle()
    assert gecmis.liste() == []
    assert gecmis.satirlar() == []


def test_es_zamanli_ekleme() -> None:
    gecmis = Gecmis(en_fazla=20)
    toplam = 8 * 25

    def calisan(indeks: int) -> None:
        for i in range(25):
            gecmis.ekle(Islem(saat=f"{indeks}-{i}", tur="tetik", durum="cevrildi"))

    is_parcalari = [threading.Thread(target=calisan, args=(n,)) for n in range(8)]
    for parca in is_parcalari:
        parca.start()
    for parca in is_parcalari:
        parca.join()

    kayitlar = gecmis.liste()
    assert len(kayitlar) == 20
    assert all(isinstance(k, Islem) for k in kayitlar)
    assert len({k.saat for k in kayitlar}) == 20
    assert toplam > 20


def test_islem_degismez() -> None:
    islem = Islem(saat="01:00:00", tur="tetik", durum="cevrildi")
    with pytest.raises(AttributeError):
        islem.durum = "hata"  # type: ignore[misc]
