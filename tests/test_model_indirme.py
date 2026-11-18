"""model_indirme yardımcısı testleri."""
from __future__ import annotations

import threading

import pytest

from ceviri_katmani.cekirdek import indir
from ceviri_katmani.uygulama import model_indirme as mi


@pytest.fixture(autouse=True)
def _durum_sifirla():
    eski = mi._durum
    mi._durum = "yok"
    yield
    mi._durum = eski


def test_ceviri_yerel_model_tanimliyken_hickirsey_yapmaz(tmp_path, monkeypatch):
    monkeypatch.setenv(mi.ORTAM_DEGISKENI, str(tmp_path / "benim-model"))
    cagrilar: list[tuple] = []

    sonuc = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a), klasor=tmp_path / "model"
    )

    assert sonuc is None
    assert cagrilar == []
    assert mi.durum() == "yok"


def test_model_zaten_tamsa_none(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: True)
    cagrilar: list[tuple] = []

    sonuc = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a), klasor=tmp_path / "model"
    )

    assert sonuc is None
    assert cagrilar == []


def test_basari_bildirim_sirasi(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: False)
    cagrilar: list[tuple] = []

    def fake_indirici(klasor, *, ilerleme=None, **kwargs):
        ilerleme(50, 100)
        ilerleme(100, 100)

    t = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a),
        klasor=tmp_path / "model",
        indirici=fake_indirici,
        thread_baslat=False,
    )

    assert isinstance(t, threading.Thread)
    assert not t.is_alive()
    t.run()

    assert [c[0] for c in cagrilar] == ["Yerel model indiriliyor", "Yerel model hazır"]
    assert cagrilar[1][1] == "Artık internetsiz de çevirebilirsiniz."
    assert mi.durum() == "hazir"


def test_hata_bildirimi(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: False)
    cagrilar: list[tuple] = []

    def hata_indirici(klasor, *, ilerleme=None, **kwargs):
        raise indir.IndirmeHatasi("model.bin doğrulanamadı")

    t = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a),
        klasor=tmp_path / "model",
        indirici=hata_indirici,
        thread_baslat=False,
    )
    t.run()

    assert [c[0] for c in cagrilar] == ["Yerel model indiriliyor", "Yerel model indirilemedi"]
    assert cagrilar[1][2] == "uyari"
    assert mi.durum() == "hata"


def test_ilerleme_bildirim_yapmaz(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: False)
    cagrilar: list[tuple] = []

    def fake_indirici(klasor, *, ilerleme=None, **kwargs):
        for i in range(100):
            ilerleme(i, 100)

    t = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a),
        klasor=tmp_path / "model",
        indirici=fake_indirici,
        thread_baslat=False,
    )
    t.run()

    assert [c[0] for c in cagrilar] == ["Yerel model indiriliyor", "Yerel model hazır"]


def test_durum_indiriliyor_ve_hazir(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: False)
    gorulen: list[str] = []

    def fake_indirici(klasor, *, ilerleme=None, **kwargs):
        ilerleme(3, 10)
        gorulen.append(mi.durum())

    t = mi.gerekirse_arkaplanda_indir(
        lambda *a: None,
        klasor=tmp_path / "model",
        indirici=fake_indirici,
        thread_baslat=False,
    )

    assert mi.durum() == "yok"
    t.run()
    assert gorulen == ["indiriliyor %30"]
    assert mi.durum() == "hazir"


def test_thread_baslat_true_ile_daemon_thread(tmp_path, monkeypatch):
    monkeypatch.delenv(mi.ORTAM_DEGISKENI, raising=False)
    monkeypatch.setattr(indir, "model_tam_mi", lambda k: False)
    cagrilar: list[tuple] = []

    def fake_indirici(klasor, *, ilerleme=None, **kwargs):
        ilerleme(100, 100)

    t = mi.gerekirse_arkaplanda_indir(
        lambda *a: cagrilar.append(a),
        klasor=tmp_path / "model",
        indirici=fake_indirici,
    )

    assert isinstance(t, threading.Thread)
    assert t.daemon is True
    t.join(timeout=5)
    assert not t.is_alive()
    assert [c[0] for c in cagrilar] == ["Yerel model indiriliyor", "Yerel model hazır"]
