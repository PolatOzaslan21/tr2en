"""Sürüm 1: terminal tetiği varsayılan kapalı (Polat, 19.11.2026 — kırılgan bulundu)."""
from __future__ import annotations

import pytest

pynput = pytest.importorskip("pynput")
from pynput.keyboard import Key, KeyCode  # noqa: E402

from ceviri_katmani.uygulama import ayarlar as ayarlar_mod  # noqa: E402
from ceviri_katmani.uygulama.tetik import Dinleyici  # noqa: E402


def _dinleyici(terminal: bool, tetik_etkin: bool, cb=lambda: None) -> Dinleyici:
    return Dinleyici(
        kisayol="<ctrl>+<shift>+t",
        tetik=";en",
        kisayol_cb=lambda: None,
        tetik_cb=lambda m, n: None,
        terminal_mi_cb=lambda: terminal,
        guvensiz_cb=lambda: None,
        tetik_etkin=tetik_etkin,
        terminal_kisayol_cb=cb,
    )


def _yaz(d: Dinleyici, metin: str) -> None:
    for c in metin:
        k = Key.space if c == " " else KeyCode.from_char(c)
        d._on_press(k)
        d._on_release(k)


def test_varsayilan_ayar_kapali():
    assert ayarlar_mod.VARSAYILAN["terminal_tetigi"] is False


def test_tetik_kapaliyken_en_is_uretmez_ve_tampon_bos():
    d = _dinleyici(terminal=True, tetik_etkin=False)
    _yaz(d, "merhaba ;en")
    assert list(d._kuyruk.queue) == []
    assert d._tampon.uzunluk_tetik_dahil() == 0


def test_tetik_acikken_eski_davranis():
    d = _dinleyici(terminal=True, tetik_etkin=True)
    _yaz(d, "merhaba ;en")
    assert list(d._kuyruk.queue) == [("tetik", "merhaba ", 11)]


def _kisayol_bas(d: Dinleyici) -> None:
    for k in (Key.ctrl_l, Key.shift, KeyCode(vk=84, char="\x14")):
        d._on_press(k)


def test_terminalde_kisayol_bilgi_isi_uretir():
    d = _dinleyici(terminal=True, tetik_etkin=False)
    _kisayol_bas(d)
    assert list(d._kuyruk.queue) == [("terminal_kisayol",)]


def test_terminal_disinda_kisayol_normal():
    d = _dinleyici(terminal=False, tetik_etkin=False)
    _kisayol_bas(d)
    assert list(d._kuyruk.queue) == [("kisayol",)]


def test_terminal_kisayol_isi_cb_cagirir():
    cagri = []
    d = _dinleyici(terminal=True, tetik_etkin=False, cb=lambda: cagri.append(1))
    d._isi_yurut(("terminal_kisayol",))
    assert cagri == [1]


def test_kisayol_adi():
    assert ayarlar_mod.kisayol_adi("<ctrl>+<shift>+<space>") == "Ctrl+Shift+Space"
    assert ayarlar_mod.kisayol_adi("<ctrl>+<shift>+y") == "Ctrl+Shift+Y"
    assert ayarlar_mod.VARSAYILAN["kisayol"] == "<ctrl>+<shift>+<space>"


def test_uygulama_kisayol_sec_dinleyiciyi_yeniden_kurar():
    from ceviri_katmani.uygulama.ana import Uygulama

    kurulan, duran, kayit, bildirim = [], [], [], []

    class SahteDinleyici:
        def __init__(self, **kw):
            self.kisayol = kw["kisayol"]
            kurulan.append(self.kisayol)

        def baslat(self):
            pass

        def durdur(self):
            duran.append(self.kisayol)

    ayarlar = {"kisayol": "<ctrl>+<shift>+<space>", "tetik": ";en", "izinli": None, "yasak": set(),
               "dinleyici_sinifi": SahteDinleyici, "kaydet_cb": lambda: kayit.append(1)}
    u = Uygulama(object(), object(), object(), lambda *a: bildirim.append(a), ayarlar)
    u.baslat()
    u.kisayol_sec("<ctrl>+<shift>+y")
    u.kisayol_sec("<ctrl>+<shift>+y")  # aynı: işlem yok
    assert kurulan == ["<ctrl>+<shift>+<space>", "<ctrl>+<shift>+y"]
    assert duran == ["<ctrl>+<shift>+<space>"]
    assert kayit == [1]
    assert bildirim[-1][:2] == ("Kısayol değişti", "Ctrl+Shift+Y")
    assert u.kisayol_simdiki() == "<ctrl>+<shift>+y"
    u.durdur()


def test_her_isten_sonra_tepsi_tazelenir():
    from ceviri_katmani.uygulama.ana import Uygulama

    class SahteTepsi:
        def __init__(self):
            self.adet = 0

        def guncelle(self):
            self.adet += 1

    ayarlar = {"kisayol": "<ctrl>+<shift>+<space>", "tetik": ";en", "izinli": None, "yasak": set()}
    u = Uygulama(object(), object(), object(), lambda *a: None, ayarlar)
    u.tepsi = SahteTepsi()
    u._calis = True
    u._kuyruk.put(("guvensiz", "deneme"))
    u._kuyruk.put(None)
    u._surec_adi = lambda: None
    u._isci_dongusu()
    assert u.tepsi.adet == 1


def test_bitisik_cumleler_bolunur():
    from ceviri_katmani.cekirdek.bolme import parcala

    assert parcala("Hello, how are you?bugün ne yemek istersin") == [["Hello, how are you?", "bugün ne yemek istersin"]]
    assert parcala("Kurulum bitti.Sonra test et") == [["Kurulum bitti.", "Sonra test et"]]
    assert parcala("v1.2 sürümünü example.com adresine yükle") == [["v1.2 sürümünü example.com adresine yükle"]]


def test_ingilizce_parca_yerel_ceviriye_girmez():
    from ceviri_katmani.cekirdek.yerel import _ingilizce_gibi

    assert _ingilizce_gibi("Hello, how are you?")
    assert not _ingilizce_gibi("bugün ne yemek istersin")
    assert not _ingilizce_gibi("deploy et")


def test_otomatik_baslat_gui_baslaticiyi_tercih_eder(tmp_path, monkeypatch):
    import sys

    from ceviri_katmani.uygulama import otomatik_baslat

    (tmp_path / "python.exe").write_bytes(b"")
    (tmp_path / "pythonw.exe").write_bytes(b"")
    (tmp_path / "tr2en.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    assert otomatik_baslat.komut() == f'"{tmp_path / "tr2en.exe"}" --arka'


def test_karisik_secim_turkce_sayilir():
    from ceviri_katmani.cekirdek.kurulum import _turkce_var_mi

    assert _turkce_var_mi("Hello, how are you?bugün ne yemek istersin")
    assert _turkce_var_mi("Hello, how are you? Bugün ne yemek istersin")
    assert not _turkce_var_mi("Hello, how are you? I am fine.")
