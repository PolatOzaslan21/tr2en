"""Kendi kısayolum: birleşim kuralları, dinleyici kayıt modu, uygulama akışı."""
import queue
from types import SimpleNamespace

import pytest

from ceviri_katmani.uygulama.kisayol_kayit import birlesim_olustur


@pytest.mark.parametrize("mods,tus,beklenen", [
    ({"ctrl", "shift"}, "k", "<ctrl>+<shift>+k"),
    ({"shift", "ctrl"}, "space", "<ctrl>+<shift>+<space>"),
    ({"ctrl"}, "f9", "<ctrl>+<f9>"),
    ({"alt", "shift"}, "5", "<shift>+<alt>+5"),
])
def test_gecerli_birlesimler(mods, tus, beklenen):
    assert birlesim_olustur(mods, tus)[0] == beklenen


@pytest.mark.parametrize("mods,tus", [
    ({"ctrl"}, "c"),               # tr2en'in kendi kopyalaması
    ({"ctrl"}, "v"),
    ({"ctrl"}, "z"),
    ({"alt"}, "f4"),
    ({"shift"}, "k"),              # büyük harf yazar
    (set(), "f9"),                 # değiştiricisiz
    ({"ctrl", "alt"}, "t"),        # AltGr
    ({"ctrl", "shift"}, None),     # desteklenmeyen tuş
    ({"ctrl", "shift"}, "tab"),
    ({"ctrl", "shift"}, "ö"),
])
def test_reddedilenler(mods, tus):
    kisayol, mesaj = birlesim_olustur(mods, tus)
    assert kisayol is None and mesaj


def test_tek_degistirici_uyariyla_kabul():
    kisayol, mesaj = birlesim_olustur({"ctrl"}, "k")
    assert kisayol == "<ctrl>+k" and "Ctrl+Shift+Space" in mesaj
    kisayol, mesaj = birlesim_olustur({"alt"}, "j")
    assert kisayol == "<alt>+j" and mesaj
    assert birlesim_olustur({"ctrl", "shift"}, "k") == ("<ctrl>+<shift>+k", "")


def test_bilinen_cakisma_uyarir_ama_kabul_eder():
    kisayol, mesaj = birlesim_olustur({"ctrl", "shift"}, "t")
    assert kisayol == "<ctrl>+<shift>+t"
    assert "sekme" in mesaj


def test_uretilen_kisayol_pynput_ile_ayristirilir():
    from pynput import keyboard
    for mods, tus in [({"ctrl", "shift"}, "k"), ({"ctrl"}, "f9"), ({"ctrl", "shift"}, "page_up")]:
        keyboard.HotKey.parse(birlesim_olustur(mods, tus)[0])


# ---- dinleyici kayıt modu ----

def _dinleyici():
    from ceviri_katmani.uygulama.tetik import Dinleyici
    tetiklenen = []
    d = Dinleyici(kisayol="<ctrl>+<shift>+<space>", tetik=";en",
                  kisayol_cb=lambda: tetiklenen.append(1), tetik_cb=lambda *a: None,
                  terminal_mi_cb=lambda: False)
    return d, tetiklenen


def test_dinleyici_kayitta_birlesimi_bildirir_ve_kisayolu_tetiklemez():
    from pynput.keyboard import Key, KeyCode
    d, tetiklenen = _dinleyici()
    gelen = []
    d.kayit_baslat(lambda m, t: gelen.append((m, t)))
    d._on_press_ic(Key.ctrl_l)
    d._on_press_ic(Key.shift)
    d._on_press_ic(Key.space)
    assert gelen == [({"ctrl", "shift"}, "space")]
    assert not d.kayitta_mi() and tetiklenen == []
    d._on_release_ic(Key.space); d._on_release_ic(Key.shift); d._on_release_ic(Key.ctrl_l)


def test_dinleyici_kayit_ctrl_ile_harf_vk_den_okunur():
    from pynput.keyboard import Key, KeyCode
    d, _ = _dinleyici()
    gelen = []
    d.kayit_baslat(lambda m, t: gelen.append((m, t)))
    d._on_press_ic(Key.ctrl_l); d._on_press_ic(Key.shift)
    d._on_press_ic(KeyCode(vk=0x4B, char="\x0b"))  # Ctrl basılıyken K kontrol karakteri gelir
    assert gelen == [({"ctrl", "shift"}, "k")]


def test_dinleyici_kayit_esc_ve_win():
    from pynput.keyboard import Key
    d, _ = _dinleyici()
    gelen = []
    d.kayit_baslat(lambda m, t: gelen.append((m, t)))
    d._on_press_ic(Key.esc)
    d.kayit_baslat(lambda m, t: gelen.append((m, t)))
    d._on_press_ic(Key.cmd); d._on_press_ic(Key.shift); d._on_press_ic(Key.f9)
    assert gelen == [(set(), "esc"), ({"win", "shift"}, None)]


# ---- uygulama akışı ----

class _Uyg:
    """TercumeUygulamasi'nın yalnızca ilgili yöntemlerini taşıyan sahte nesne."""

    def __init__(self, kisayol="<ctrl>+<shift>+<space>"):
        from ceviri_katmani.uygulama import ana
        self.ayarlar = {"kisayol": kisayol}
        self.bildirimler = []
        self.secilen = []
        self._kuyruk = queue.Queue()
        self._ana = ana
        sinif = self._sinif()
        self._kisayol_kaydi_isle = sinif._kisayol_kaydi_isle.__get__(self)
        self._kisayol_kaydi_geldi = sinif._kisayol_kaydi_geldi.__get__(self)
        self.kisayol_adi = sinif.kisayol_adi.__get__(self)

    @staticmethod
    def _sinif():
        from ceviri_katmani.uygulama import ana
        for ad in dir(ana):
            nesne = getattr(ana, ad)
            if isinstance(nesne, type) and hasattr(nesne, "_kisayol_kaydi_isle"):
                return nesne
        raise AssertionError("uygulama sınıfı bulunamadı")

    def bildir(self, *a):
        self.bildirimler.append(a)

    def kisayol_sec(self, k):
        self.secilen.append(k)
        self.ayarlar["kisayol"] = k


def test_kayit_kuyruga_gider():
    u = _Uyg()
    u._kisayol_kaydi_geldi({"ctrl", "shift"}, "k")
    assert u._kuyruk.get_nowait() == ("kisayol_kayit", ({"ctrl", "shift"}, "k"))


def test_gecerli_kayit_kisayolu_degistirir():
    u = _Uyg()
    u._kisayol_kaydi_isle({"ctrl", "shift"}, "k")
    assert u.secilen == ["<ctrl>+<shift>+k"]


def test_cakisan_kayit_kabul_ve_uyari():
    u = _Uyg()
    u._kisayol_kaydi_isle({"ctrl", "shift"}, "t")
    assert u.secilen == ["<ctrl>+<shift>+t"]
    assert any("sekme" in str(b) for b in u.bildirimler)


@pytest.mark.parametrize("mods,tus", [(set(), "esc"), ({"ctrl", "alt"}, "t"), ({"ctrl", "shift"}, "space")])
def test_vazgecme_red_ve_ayni_kisayol_degistirmez(mods, tus):
    u = _Uyg()
    u._kisayol_kaydi_isle(mods, tus)
    assert u.secilen == [] and u.bildirimler
