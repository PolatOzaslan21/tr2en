"""Tepsi simgesi testleri (gerçek simge açılmaz; pystray sınıfları kullanılır)."""
from __future__ import annotations

import traceback

import pystray
import pytest

from ceviri_katmani.uygulama.tepsi import Tepsi, simge_uret


class SahteArayuz:
    def __init__(self):
        self.aktif = True
        self.cevirmen_ad = "gemini"
        self.kisayol_deger = "<ctrl>+<shift>+<space>"
        self.islemler = []
        self.son_var = False
        self.otomatik_baslat = False
        self.cagrilar = []

    def aktif_mi(self):
        return self.aktif

    def aktif_degistir(self):
        self.cagrilar.append("aktif_degistir")
        self.aktif = not self.aktif

    def cevirmen(self):
        return self.cevirmen_ad

    def kisayol_simdiki(self):
        return self.kisayol_deger

    def kisayol_sec(self, k):
        self.cagrilar.append(("kisayol_sec", k))
        self.kisayol_deger = k

    def cevirmen_sec(self, ad):
        self.cagrilar.append(("cevirmen_sec", ad))
        self.cevirmen_ad = ad

    def son_islemler(self):
        return list(self.islemler)

    def son_ceviri_var_mi(self):
        return self.son_var

    def son_ceviriyi_goster(self):
        self.cagrilar.append("son_ceviriyi_goster")

    def son_orijinali_kopyala(self):
        self.cagrilar.append("son_orijinali_kopyala")

    def ayarlari_ac(self):
        self.cagrilar.append("ayarlari_ac")

    def otomatik_baslat_acik_mi(self):
        return self.otomatik_baslat

    def otomatik_baslat_degistir(self):
        self.cagrilar.append("otomatik_baslat_degistir")
        self.otomatik_baslat = not self.otomatik_baslat

    def cikis(self):
        self.cagrilar.append("cikis")


@pytest.fixture()
def arayuz():
    return SahteArayuz()


@pytest.fixture()
def tepsi(arayuz):
    return Tepsi(arayuz)


def test_menu_sira_ve_adlar(tepsi):
    ogeler = tepsi.menu_ogeleri()
    adlar = [o.text for o in ogeler if o is not pystray.Menu.SEPARATOR]
    assert adlar == [
        "Etkin",
        "Çevirmen",
        "Son işlemler",
        "Son çeviriyi göster",
        "Son orijinali kopyala",
        "Kısayol",
        "Windows açılışında başlat",
        "Ayarlar dosyasını aç",
        "Çıkış",
    ]
    ayraclar = [o for o in ogeler if o is pystray.Menu.SEPARATOR]
    assert len(ayraclar) == 2


def test_etkin_checked_ve_default(tepsi, arayuz):
    etkin = tepsi.menu_ogeleri()[0]
    assert etkin.default is True
    assert etkin.checked is True
    arayuz.aktif = False
    assert etkin.checked is False


def test_cevirmen_radio_checked(tepsi, arayuz):
    cevirmen = tepsi.menu_ogeleri()[2]
    gemini, yerel = list(cevirmen.submenu)
    assert gemini.radio is True
    assert yerel.radio is True
    assert gemini.checked is True
    assert yerel.checked is False
    arayuz.cevirmen_ad = "yerel"
    assert gemini.checked is False
    assert yerel.checked is True


def test_son_islemler_bos(tepsi, arayuz):
    arayuz.islemler = []
    son = tepsi.menu_ogeleri()[3]
    alt = list(son.submenu)
    assert [o.text for o in alt] == ["Henüz işlem yok"]
    assert alt[0].enabled is False


def test_son_islemler_dolu(tepsi, arayuz):
    arayuz.islemler = ["10:00  cevrildi", "09:59  hata"]
    son = tepsi.menu_ogeleri()[3]
    alt = list(son.submenu)
    assert [o.text for o in alt] == ["10:00  cevrildi", "09:59  hata"]
    assert all(o.enabled is False for o in alt)


def test_etkin_tiklaninca_aktif_degistir(tepsi, arayuz):
    etkin = tepsi.menu_ogeleri()[0]
    etkin(None)
    assert "aktif_degistir" in arayuz.cagrilar


def test_cevirmen_tiklaninca_sec(tepsi, arayuz):
    gemini, yerel = list(tepsi.menu_ogeleri()[2].submenu)
    yerel(None)
    assert ("cevirmen_sec", "yerel") in arayuz.cagrilar
    gemini(None)
    assert ("cevirmen_sec", "gemini") in arayuz.cagrilar


def test_son_ceviri_eylemleri(tepsi, arayuz):
    arayuz.son_var = True
    goster = tepsi.menu_ogeleri()[4]
    kopyala = tepsi.menu_ogeleri()[5]
    assert goster.enabled is True
    assert kopyala.enabled is True
    goster(None)
    kopyala(None)
    assert "son_ceviriyi_goster" in arayuz.cagrilar
    assert "son_orijinali_kopyala" in arayuz.cagrilar


def test_son_ceviri_yoksa_pasif(tepsi, arayuz):
    arayuz.son_var = False
    assert tepsi.menu_ogeleri()[4].enabled is False
    assert tepsi.menu_ogeleri()[5].enabled is False


def test_ayarlar_ve_cikis(tepsi, arayuz):
    ayarlar = tepsi.menu_ogeleri()[9]
    cikis = tepsi.menu_ogeleri()[10]
    ayarlar(None)
    assert "ayarlari_ac" in arayuz.cagrilar
    cikis(None)
    assert "cikis" in arayuz.cagrilar


class SahteIcon:
    def __init__(self):
        self.durdu = False

    def stop(self):
        self.durdu = True


def test_cikis_ikonu_durdurur(tepsi, arayuz):
    sahte = SahteIcon()
    tepsi._icon = sahte
    cikis = tepsi.menu_ogeleri()[10]
    cikis(None)
    assert sahte.durdu is True


def test_geri_cagri_istisnasi_yutulur(tepsi, arayuz, monkeypatch):
    kayit = []
    monkeypatch.setattr(traceback, "print_exc", lambda *a, **k: kayit.append(1))

    def patlar():
        raise RuntimeError("patladi")

    arayuz.aktif_degistir = patlar
    etkin = tepsi.menu_ogeleri()[0]
    etkin(None)  # yükselmemeli
    assert kayit


def test_simge_uret_aktif_mavi():
    img = simge_uret(True)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
    assert img.getpixel((32, 2))[:3] == (37, 99, 235)


def test_simge_uret_pasif_gri():
    img = simge_uret(False)
    assert img.getpixel((32, 2))[:3] == (156, 163, 175)


def test_simge_uret_boyut():
    img = simge_uret(True, boyut=32)
    assert img.size == (32, 32)
    assert img.getpixel((16, 2))[:3] == (37, 99, 235)


def test_kisayol_alt_menusu_secenekler_ve_secim(tepsi):
    alt = list(tepsi.menu_ogeleri()[7].submenu)
    assert [o.text for o in alt] == ["Ctrl+Shift+Space", "Ctrl+Shift+Y", "Ctrl+Shift+T"]
    assert [o.checked for o in alt] == [True, False, False]
    alt[1](None)
    assert ("kisayol_sec", "<ctrl>+<shift>+y") in tepsi.arayuz.cagrilar


def test_kisayol_ozel_deger_gosterilir(tepsi):
    tepsi.arayuz.kisayol_deger = "<ctrl>+<shift>+k"
    alt = list(tepsi.menu_ogeleri()[7].submenu)
    assert alt[-1].text == "Özel: Ctrl+Shift+K (ayar dosyasından)"
    assert alt[-1].enabled is False


def test_otomatik_baslat_oge_sira(tepsi):
    ogeler = tepsi.menu_ogeleri()
    adlar = [o.text for o in ogeler if o is not pystray.Menu.SEPARATOR]
    assert adlar.index("Windows açılışında başlat") == adlar.index("Kısayol") + 1
    assert adlar.index("Windows açılışında başlat") == adlar.index("Ayarlar dosyasını aç") - 1
    assert ogeler[8].text == "Windows açılışında başlat"


def test_otomatik_baslat_checked(tepsi, arayuz):
    oge = tepsi.menu_ogeleri()[8]
    assert oge.checked is False
    arayuz.otomatik_baslat = True
    assert oge.checked is True


def test_otomatik_baslat_tiklaninca_degistir(tepsi, arayuz):
    oge = tepsi.menu_ogeleri()[8]
    oge(None)
    assert "otomatik_baslat_degistir" in arayuz.cagrilar
    assert arayuz.otomatik_baslat is True
