"""otomatik_baslat testleri — gerçek kayıt defterine asla yazılmaz."""
from __future__ import annotations

import sys

import pytest

from ceviri_katmani.uygulama import otomatik_baslat
from ceviri_katmani.uygulama.ana import Uygulama
from ceviri_katmani.uygulama.otomatik_baslat import ac, acik_mi, kapat, komut


class SahteReg:
    """winreg benzeri sahte nesne; gerçek kayıt defterine dokunmaz."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.degerler: dict[str, str] = {}
        self.aciklar: list[tuple[str, str]] = []
        self.kapatilan: list[object] = []

    def OpenKey(self, kok, yol, _reserved=0, _erisim=0):
        self.aciklar.append((kok, yol))
        return object()

    def QueryValueEx(self, _anahtar, ad):
        if ad not in self.degerler:
            raise FileNotFoundError(ad)
        return (self.degerler[ad], self.REG_SZ)

    def SetValueEx(self, _anahtar, ad, _reserved, tur, deger):
        assert tur == self.REG_SZ
        self.degerler[ad] = deger

    def DeleteValue(self, _anahtar, ad):
        if ad not in self.degerler:
            raise FileNotFoundError(ad)
        del self.degerler[ad]

    def CloseKey(self, anahtar):
        self.kapatilan.append(anahtar)


# ---- acik_mi / ac / kapat ----

def test_acik_mi_bosken_false():
    assert acik_mi(_reg=SahteReg()) is False


def test_ac_yazar_ve_acik_mi_true():
    reg = SahteReg()
    ac(_reg=reg)
    assert acik_mi(_reg=reg) is True
    assert reg.degerler[otomatik_baslat.DEGER_ADI] == komut()


def test_kapat_siler():
    reg = SahteReg()
    ac(_reg=reg)
    kapat(_reg=reg)
    assert acik_mi(_reg=reg) is False
    assert otomatik_baslat.DEGER_ADI not in reg.degerler


def test_kapat_deger_yoksa_sessiz():
    reg = SahteReg()
    kapat(_reg=reg)
    assert reg.degerler == {}


def test_ac_kapat_anahtar_dogru():
    reg = SahteReg()
    ac(_reg=reg)
    kapat(_reg=reg)
    assert reg.aciklar
    assert all(kok == reg.HKEY_CURRENT_USER for kok, _ in reg.aciklar)
    assert all(yol == r"Software\Microsoft\Windows\CurrentVersion\Run" for _, yol in reg.aciklar)
    assert len(reg.kapatilan) == len(reg.aciklar)


def test_deger_adi_tr2en():
    assert otomatik_baslat.DEGER_ADI == "tr2en"


# ---- komut() ----

def test_komut_pythonw_yanindaysa(tmp_path, monkeypatch):
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert komut() == f'"{pythonw}" -m ceviri_katmani.uygulama --arka'


def test_komut_pythonw_yoksa_sys_executable(tmp_path, monkeypatch):
    exe = tmp_path / "python.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert komut() == f'"{exe}" -m ceviri_katmani.uygulama --arka'


def test_komut_frozen(tmp_path, monkeypatch):
    exe = tmp_path / "tr2en.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert komut() == f'"{exe}" --arka'


# ---- Uygulama metodları ----

def _uygulama_olustur(bildirim: list):
    return Uygulama(object(), object(), object(), lambda *a: bildirim.append(a), {})


def test_uygulama_otomatik_baslat_degistir_ac(monkeypatch):
    bildirim: list = []
    uyg = _uygulama_olustur(bildirim)
    cagri = []
    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: False)
    monkeypatch.setattr(otomatik_baslat, "ac", lambda **k: cagri.append("ac"))
    monkeypatch.setattr(otomatik_baslat, "kapat", lambda **k: cagri.append("kapat"))

    uyg.otomatik_baslat_degistir()

    assert cagri == ["ac"]
    assert len(bildirim) == 1
    assert bildirim[0][0] == "Windows açılışında başlayacak"


def test_uygulama_otomatik_baslat_degistir_kapat(monkeypatch):
    bildirim: list = []
    uyg = _uygulama_olustur(bildirim)
    cagri = []
    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: True)
    monkeypatch.setattr(otomatik_baslat, "ac", lambda **k: cagri.append("ac"))
    monkeypatch.setattr(otomatik_baslat, "kapat", lambda **k: cagri.append("kapat"))

    uyg.otomatik_baslat_degistir()

    assert cagri == ["kapat"]
    assert len(bildirim) == 1
    assert bildirim[0][0] == "Windows açılışında başlamayacak"


def test_uygulama_otomatik_baslat_acik_mi(monkeypatch):
    uyg = _uygulama_olustur([])
    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: True)
    assert uyg.otomatik_baslat_acik_mi() is True
    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: False)
    assert uyg.otomatik_baslat_acik_mi() is False


def test_uygulama_otomatik_baslat_hata_uyari(monkeypatch):
    bildirim: list = []
    uyg = _uygulama_olustur(bildirim)

    def patlar(**k):
        raise RuntimeError("erisim yok")

    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: False)
    monkeypatch.setattr(otomatik_baslat, "ac", patlar)

    uyg.otomatik_baslat_degistir()

    assert len(bildirim) == 1
    assert bildirim[0][0] == "Ayar değiştirilemedi"
    assert bildirim[0][2] == "uyari"


def test_uygulama_otomatik_baslat_degistir_tepsi_gunceller(monkeypatch):
    bildirim: list = []
    uyg = _uygulama_olustur(bildirim)
    guncellemeler = []

    class Tepsi:
        def guncelle(self):
            guncellemeler.append(1)

    uyg.tepsi = Tepsi()
    monkeypatch.setattr(otomatik_baslat, "acik_mi", lambda **k: False)
    monkeypatch.setattr(otomatik_baslat, "ac", lambda **k: None)

    uyg.otomatik_baslat_degistir()

    assert guncellemeler == [1]
