"""anahtar_kasasi modülü testleri.

Gerçek Windows Kimlik Yöneticisi'ne dokunulmaz: her testte sahte arka uç
enjekte edilir. Ortam değişkeni okuması da sahtelenir (kayıt defterine düşmez).
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator

import pytest

from ceviri_katmani.uygulama import anahtar_kasasi as ak


class SahteArkaUc:
    """get_password/set_password/delete_password yöntemli sözlük tabanlı arka uç."""

    def __init__(self) -> None:
        self.veri: dict[tuple[str, str], str] = {}
        self.cagrilar: list[tuple[str, str, str]] = []

    def get_password(self, servis: str, kullanici: str) -> str | None:
        self.cagrilar.append(("get", servis, kullanici))
        return self.veri.get((servis, kullanici))

    def set_password(self, servis: str, kullanici: str, deger: str) -> None:
        self.cagrilar.append(("set", servis, kullanici))
        self.veri[(servis, kullanici)] = deger

    def delete_password(self, servis: str, kullanici: str) -> None:
        self.cagrilar.append(("delete", servis, kullanici))
        self.veri.pop((servis, kullanici), None)


class GetHatasi(SahteArkaUc):
    def __init__(self, mesaj: str) -> None:
        super().__init__()
        self.mesaj = mesaj

    def get_password(self, servis: str, kullanici: str) -> str | None:
        raise RuntimeError(self.mesaj)


class SetHatasi(SahteArkaUc):
    def __init__(self, mesaj: str) -> None:
        super().__init__()
        self.mesaj = mesaj

    def set_password(self, servis: str, kullanici: str, deger: str) -> None:
        raise RuntimeError(f"{self.mesaj}: {deger}")


class DeleteHatasi(SahteArkaUc):
    def delete_password(self, servis: str, kullanici: str) -> None:
        raise RuntimeError("silme hatası")


@pytest.fixture(autouse=True)
def sahte_kasa() -> Iterator[SahteArkaUc]:
    uc = SahteArkaUc()
    ak.arka_uc_ayarla(uc)
    try:
        yield uc
    finally:
        ak.arka_uc_ayarla(None)


@pytest.fixture(autouse=True)
def kayit_defteri_kapali(monkeypatch: pytest.MonkeyPatch) -> None:
    """anahtar.py'deki ortam/kayıt defteri okumasını sahtele."""
    monkeypatch.setattr(
        ak, "anahtar_oku", lambda ad: os.environ.get(ad) or None, raising=True
    )


def test_yaz_oku_gidis_donus(sahte_kasa: SahteArkaUc) -> None:
    assert ak.yaz("gemini", "anahtar-123") is True
    assert ak.oku("gemini") == "anahtar-123"
    assert ak.var_mi("gemini") is True
    assert sahte_kasa.veri[(ak.SERVIS_ADI, "gemini")] == "anahtar-123"


def test_servisler_bagimsiz(sahte_kasa: SahteArkaUc) -> None:
    ak.yaz("gemini", "g-degeri")
    ak.yaz("openai", "o-degeri")
    assert ak.oku("gemini") == "g-degeri"
    assert ak.oku("openai") == "o-degeri"
    ak.sil("gemini")
    assert ak.oku("gemini") is None
    assert ak.oku("openai") == "o-degeri"


def test_bos_deger_kaydedilmez(sahte_kasa: SahteArkaUc) -> None:
    assert ak.yaz("gemini", "") is False
    assert ak.oku("gemini") is None
    assert sahte_kasa.veri == {}


def test_sadece_bosluk_kaydedilmez(sahte_kasa: SahteArkaUc) -> None:
    assert ak.yaz("gemini", "   \t\n ") is False
    assert ak.oku("gemini") is None
    assert sahte_kasa.veri == {}


def test_bastaki_sondaki_bosluk_kirpilir(sahte_kasa: SahteArkaUc) -> None:
    assert ak.yaz("gemini", "  kirp-beni \n") is True
    assert ak.oku("gemini") == "kirp-beni"
    assert sahte_kasa.veri[(ak.SERVIS_ADI, "gemini")] == "kirp-beni"


def test_sil_sonrasi_okunmaz(sahte_kasa: SahteArkaUc) -> None:
    ak.yaz("gemini", "silinecek")
    assert ak.sil("gemini") is True
    assert ak.oku("gemini") is None
    assert ak.var_mi("gemini") is False
    assert (ak.SERVIS_ADI, "gemini") not in sahte_kasa.veri


def test_olmayan_anahtari_silmek_cokmez(sahte_kasa: SahteArkaUc) -> None:
    assert ak.sil("yok-boyle-bir-sey") is False
    assert ak.oku("yok-boyle-bir-sey") is None


def test_get_istisnasi_cokme_ve_none() -> None:
    ak.arka_uc_ayarla(GetHatasi("okuma patladı"))
    assert ak.oku("gemini") is None
    assert ak.var_mi("gemini") is False


def test_set_istisnasi_false() -> None:
    ak.arka_uc_ayarla(SetHatasi("yazma patladı"))
    assert ak.yaz("gemini", "gizli-deger") is False
    assert ak.oku("gemini") is None


def test_delete_istisnasi_false() -> None:
    uc = DeleteHatasi()
    ak.arka_uc_ayarla(uc)
    uc.veri[(ak.SERVIS_ADI, "gemini")] = "mevcut"
    assert ak.sil("gemini") is False
    assert ak.oku("gemini") == "mevcut"


def test_deger_ciktiya_sizmaz_oku(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    gizli = "cok-gizli-anahtar-degeri"
    caplog.set_level(logging.DEBUG)
    ak.arka_uc_ayarla(GetHatasi(f"okuma hatası: {gizli}"))
    assert ak.oku("gemini") is None
    yakalanan = capsys.readouterr()
    assert gizli not in yakalanan.out
    assert gizli not in yakalanan.err
    assert gizli not in caplog.text


def test_deger_ciktiya_sizmaz_yaz(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    gizli = "cok-gizli-yazma-degeri"
    caplog.set_level(logging.DEBUG)
    ak.arka_uc_ayarla(SetHatasi("yazma hatası"))
    assert ak.yaz("gemini", gizli) is False
    yakalanan = capsys.readouterr()
    assert gizli not in yakalanan.out
    assert gizli not in yakalanan.err
    assert gizli not in caplog.text


def test_deger_istisna_mesajina_sizmaz() -> None:
    gizli = "istisnaya-sizmamali"
    ak.arka_uc_ayarla(GetHatasi(f"hata: {gizli}"))
    try:
        sonuc = ak.oku("gemini")
    except Exception as hata:  # çökmemeli; çökerse mesajda değer olmamalı
        assert gizli not in str(hata)
        raise
    assert sonuc is None


def test_anahtar_bul_kasa_onceligi(monkeypatch: pytest.MonkeyPatch) -> None:
    ak.yaz("gemini", "kasadaki")
    monkeypatch.setenv("GEMINI_API_KEY", "ortamdaki")
    assert ak.anahtar_bul("gemini", "GEMINI_API_KEY") == "kasadaki"


def test_anahtar_bul_ortam_degiskeni(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "ortamdaki")
    assert ak.anahtar_bul("gemini", "GEMINI_API_KEY") == "ortamdaki"


def test_anahtar_bul_bos_ortam_adi_sadece_kasa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOS_ADLI_DEGISKEN", "ortamdaki")
    assert ak.anahtar_bul("gemini", "") is None
    ak.yaz("gemini", "kasadaki")
    assert ak.anahtar_bul("gemini", "") == "kasadaki"


def test_anahtar_bul_ikisi_de_yoksa_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ak.anahtar_bul("gemini", "GEMINI_API_KEY") is None


def test_keyring_yuklenemezse(monkeypatch: pytest.MonkeyPatch) -> None:
    ak.arka_uc_ayarla(None)
    monkeypatch.setitem(sys.modules, "keyring", None)
    assert ak.oku("gemini") is None
    assert ak.yaz("gemini", "deger") is False
    assert ak.sil("gemini") is False
