"""Pano ve pencere yardımcıları testleri (gerçek Windows panosu)."""
from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows'a özgü")

from ceviri_katmani.uygulama.pano import (
    PanoYedegi,
    _pano_ac,
    _pano_kapat,
    _sira_degisimini_bekle,
    metin_al,
    metin_koy,
    sira_no,
)
from ceviri_katmani.uygulama.pencere import (
    Pencere,
    aktif_pencere,
    izinli_mi,
    terminal_mi,
)

if sys.platform == "win32":
    import win32clipboard


@pytest.fixture()
def pano_yedegi():
    """Test öncesi kullanıcı panosunu saklar, sonunda geri yükler."""
    yedek = PanoYedegi()
    yedek.kaydet()
    yield yedek
    yedek.geri_yukle()


def _bicim_koy(bicim: int, veri) -> None:
    _pano_ac()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(bicim, veri)
    finally:
        _pano_kapat()


def _bicim_al(bicim: int):
    _pano_ac()
    try:
        return win32clipboard.GetClipboardData(bicim)
    finally:
        _pano_kapat()


def test_metin_koy_ve_al(pano_yedegi):
    metin_koy("merhaba dünya")
    assert metin_al() == "merhaba dünya"


def test_sira_no_metin_koyunca_degisir(pano_yedegi):
    once = sira_no()
    metin_koy("sıra testi")
    assert sira_no() != once


def test_yedek_metni_geri_yukler(pano_yedegi):
    metin_koy("orijinal")
    yedek = PanoYedegi()
    yedek.kaydet()
    metin_koy("değişti")
    assert yedek.geri_yukle() is True
    assert metin_al() == "orijinal"


def test_yedek_ozel_bicimi_geri_yukler(pano_yedegi):
    bicim = win32clipboard.RegisterClipboardFormat("CeviriKatmaniTestBicim")
    veri = "özel veri".encode("utf-8")
    _bicim_koy(bicim, veri)
    yedek = PanoYedegi()
    yedek.kaydet()
    metin_koy("değişti")
    assert yedek.geri_yukle() is True
    assert _bicim_al(bicim) == veri


def test_yedek_cf_html_geri_yukler(pano_yedegi):
    bicim = win32clipboard.RegisterClipboardFormat("HTML Format")
    veri = b"<html><body>Merhaba</body></html>"
    _bicim_koy(bicim, veri)
    yedek = PanoYedegi()
    yedek.kaydet()
    metin_koy("değişti")
    assert yedek.geri_yukle() is True
    assert _bicim_al(bicim) == veri


def test_kaydetmeden_geri_yukle_false(pano_yedegi):
    assert PanoYedegi().geri_yukle() is False


def test_bekleme_sira_degisince_true():
    sayac = {"n": 0}

    def sahte_sira():
        sayac["n"] += 1
        return 1 if sayac["n"] < 3 else 2

    assert _sira_degisimini_bekle(1, 1000, sira_oku=sahte_sira, uyku=lambda s: None) is True
    assert sayac["n"] == 3


def test_bekleme_sira_degismezse_false():
    sayac = {"n": 0}

    def sahte_sira():
        sayac["n"] += 1
        return 5

    assert _sira_degisimini_bekle(5, 0, sira_oku=sahte_sira, uyku=lambda s: None) is False
    assert sayac["n"] == 1


def test_bekleme_sifir_gecikmede_degisimi_yakalar():
    assert _sira_degisimini_bekle(1, 0, sira_oku=lambda: 2, uyku=lambda s: None) is True


def test_bekleme_adim_suresiyle_uyur():
    uykular: list[float] = []

    def sahte_sira():
        return 1 if len(uykular) < 2 else 2

    assert (
        _sira_degisimini_bekle(1, 1000, sira_oku=sahte_sira, uyku=uykular.append)
        is True
    )
    assert uykular == [0.01, 0.01]


def test_aktif_pencere_doner():
    p = aktif_pencere()
    assert p is not None
    assert isinstance(p.hwnd, int) and p.hwnd != 0
    assert p.surec.endswith(".exe")
    assert isinstance(p.baslik, str)


@pytest.mark.parametrize(
    "surec,beklenen",
    [
        ("windowsterminal.exe", True),
        ("openconsole.exe", True),
        ("conhost.exe", True),
        ("cmd.exe", True),
        ("powershell.exe", True),
        ("pwsh.exe", True),
        ("mintty.exe", True),
        ("alacritty.exe", True),
        ("wezterm-gui.exe", True),
        ("code.exe", False),
        ("chrome.exe", False),
        ("", False),
    ],
)
def test_terminal_mi(surec: str, beklenen: bool):
    assert terminal_mi(Pencere(1, surec, "Sinif", "Başlık")) is beklenen


@pytest.mark.parametrize(
    "surec,ek,beklenen",
    [
        ("windowsterminal.exe", frozenset(), True),
        ("kitty.exe", {"kitty.exe"}, True),
        ("kitty.exe", frozenset(), False),
        ("code.exe", {"code.exe"}, True),
    ],
)
def test_terminal_mi_ek_surecler(surec: str, ek: set[str], beklenen: bool):
    assert terminal_mi(Pencere(1, surec, "Sinif", "Başlık"), ek) is beklenen


@pytest.mark.parametrize(
    "surec,izinli,beklenen",
    [
        ("notepad.exe", None, True),
        ("keepass.exe", None, False),
        ("notepad.exe", {"notepad.exe"}, True),
        ("chrome.exe", {"notepad.exe"}, False),
        ("keepass.exe", {"keepass.exe"}, False),
    ],
)
def test_izinli_mi(surec: str, izinli: set[str] | None, beklenen: bool):
    yasak = {"keepass.exe", "1password.exe", "bitwarden.exe"}
    assert izinli_mi(Pencere(1, surec, "Sinif", "Başlık"), izinli, yasak) is beklenen
