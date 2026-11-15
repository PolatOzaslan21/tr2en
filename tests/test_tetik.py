"""TusTamponu ve Dinleyici birim testleri."""
from __future__ import annotations

import queue

import pytest

from ceviri_katmani.uygulama.tetik import Dinleyici, TusTamponu

try:
    from pynput import keyboard

    PYNPUT_VAR = True
except ImportError:  # pragma: no cover - yalnızca uygulama extra'sı olmadan
    keyboard = None
    PYNPUT_VAR = False


def _yaz(t: TusTamponu, metin: str) -> bool:
    sonuc = False
    for k in metin:
        sonuc = t.karakter(k)
    return sonuc


# --- TusTamponu ---


def test_tetik_algilanir():
    t = TusTamponu()
    assert t.karakter(";") is False
    assert t.karakter("e") is False
    assert t.karakter("n") is True


def test_tetik_yoksa_false():
    t = TusTamponu()
    assert _yaz(t, "abc") is False


def test_metin_tetik_haric():
    t = TusTamponu()
    _yaz(t, "abc;en")
    assert t.metin() == "abc"


def test_metin_tetik_yoksa_tamami():
    t = TusTamponu()
    _yaz(t, "abc")
    assert t.metin() == "abc"


def test_metin_bos_trigger():
    t = TusTamponu()
    _yaz(t, ";en")
    assert t.metin() == ""


def test_uzunluk_tetik_dahil():
    t = TusTamponu()
    _yaz(t, "abc;en")
    assert t.uzunluk_tetik_dahil() == 6


def test_geri_son_karakteri_siler():
    t = TusTamponu()
    _yaz(t, "abc")
    t.geri()
    assert t.metin() == "ab"


def test_geri_bos_tamponda_etkisiz():
    # Boş tamponda geri silme imleç önündeki eski metni siler; sonradan yazılanlar yine bitişik kalır.
    t = TusTamponu()
    t.geri()
    assert t.guvenli is True


def test_sifirla_tamponu_ve_guvenligi_temizler():
    t = TusTamponu()
    _yaz(t, "abc")
    t.guvensiz_yap()
    t.sifirla()
    assert t.metin() == ""
    assert t.guvenli is True


def test_guvensiz_yap():
    t = TusTamponu()
    assert t.guvenli is True
    t.guvensiz_yap("deneme")  # boş tamponda etkisiz (terminale tıklamak, Alt+Tab)
    assert t.guvenli is True
    t.karakter("a")
    t.guvensiz_yap("deneme")
    assert t.guvenli is False and t.sebep == "deneme"


def test_guvensiz_yap_zorla_bos_tamponda():
    t = TusTamponu()
    t.guvensiz_yap("yapıştırma", zorla=True)
    assert t.guvenli is False


def test_en_fazla_tasmasi_guvensiz_yapar():
    t = TusTamponu(tetik=";en", en_fazla=5)
    _yaz(t, "abcdef")
    assert t.guvenli is False


def test_turkce_karakterler():
    t = TusTamponu()
    assert _yaz(t, "ç ğ ı ö ş ü") is False
    assert t.metin() == "ç ğ ı ö ş ü"


def test_turkce_metin_sonrasi_trigger():
    t = TusTamponu()
    assert _yaz(t, "çalıştır ;en") is True
    assert t.metin() == "çalıştır "


def test_trigger_harfleri_yazilip_silinirse_yanlis_trigger_olmaz():
    t = TusTamponu()
    assert t.karakter(";") is False
    assert t.karakter("e") is False
    t.geri()
    assert t.karakter("n") is False
    assert t.karakter("x") is False
    assert t.guvenli is True


def test_trigger_kelime_ortasinda():
    t = TusTamponu()
    _yaz(t, "hello")
    assert t.karakter(";") is False
    assert t.karakter("e") is False
    assert t.karakter("n") is True
    assert t.metin() == "hello"


def test_sifirla_sonrasi_yeniden_trigger():
    t = TusTamponu()
    assert _yaz(t, "x;en") is True
    t.sifirla()
    assert _yaz(t, ";en") is True
    assert t.metin() == ""


def test_karakter_bos_string_ignore():
    t = TusTamponu()
    assert t.karakter("") is False
    assert t.metin() == ""
    assert t.uzunluk_tetik_dahil() == 0


def test_geri_silme_sonrasi_trigger_dogru_metin():
    t = TusTamponu()
    _yaz(t, "merhaba dünya;en")
    t.geri()
    t.geri()
    t.geri()
    _yaz(t, ";en")
    assert t.metin() == "merhaba dünya"


def test_farkli_tetik_dizesi():
    t = TusTamponu(tetik=";;tr")
    assert _yaz(t, "abc;;tr") is True
    assert t.metin() == "abc"
    assert t.uzunluk_tetik_dahil() == 7


# --- Dinleyici ---

needs_pynput = pytest.mark.skipif(not PYNPUT_VAR, reason="pynput kurulu değil")


def _karakter(c: str):
    return keyboard.KeyCode.from_char(c)


def _bas(d: Dinleyici, key) -> None:
    d._on_press(key)


def _birak(d: Dinleyici, key) -> None:
    d._on_release(key)


def _kuyruk_joblari(d: Dinleyici) -> list:
    jobs = []
    while True:
        try:
            jobs.append(d._kuyruk.get_nowait())
        except queue.Empty:
            return jobs


def _dinleyici(terminal: bool = True, hwnd: int | None = None) -> Dinleyici:
    return Dinleyici(
        kisayol="<ctrl>+<shift>+t",
        tetik=";en",
        kisayol_cb=lambda: None,
        tetik_cb=lambda m, n: None,
        terminal_mi_cb=lambda: terminal,
        guvensiz_cb=lambda: None,
        aktif_hwnd_cb=(lambda: hwnd) if hwnd is not None else None,
    )


@needs_pynput
def test_dinleyici_tetik_guvenli_kuyruga_is_koyar():
    d = _dinleyici(terminal=True)
    for c in "merhaba ":
        _bas(d, _karakter(c))
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("tetik", "merhaba ", 11)]


@needs_pynput
def test_dinleyici_ok_tusu_sonrasi_guvensiz():
    d = _dinleyici(terminal=True)
    for c in "abc":
        _bas(d, _karakter(c))
    _bas(d, keyboard.Key.up)
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("guvensiz", "ok/Home/End/Delete tuşu")]


@needs_pynput
def test_dinleyici_terminal_disinda_tetik_kuyruga_girmez():
    d = _dinleyici(terminal=False)
    for c in ";en":
        _bas(d, _karakter(c))
    assert _kuyruk_joblari(d) == []


@needs_pynput
def test_dinleyici_kisayol_terminal_disinda_kuyruga_girer():
    d = _dinleyici(terminal=False)
    _bas(d, keyboard.Key.ctrl)
    _bas(d, keyboard.Key.shift)
    _bas(d, _karakter("t"))
    assert _kuyruk_joblari(d) == [("kisayol",)]


@needs_pynput
def test_dinleyici_kisayol_terminal_icinde_yok_sayilir():
    d = _dinleyici(terminal=True)
    _bas(d, keyboard.Key.ctrl)
    _bas(d, keyboard.Key.shift)
    _bas(d, _karakter("t"))
    assert _kuyruk_joblari(d) == []


@needs_pynput
def test_dinleyici_ctrl_v_guvensiz():
    d = _dinleyici(terminal=True)
    _bas(d, keyboard.Key.ctrl)
    _bas(d, _karakter("v"))
    _birak(d, keyboard.Key.ctrl)
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("guvensiz", "yapıştırma (Ctrl+V)")]


@needs_pynput
def test_dinleyici_backspace_metni_duzeltir():
    d = _dinleyici(terminal=True)
    for c in "abc":
        _bas(d, _karakter(c))
    _bas(d, keyboard.Key.backspace)
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("tetik", "ab", 5)]


@needs_pynput
def test_dinleyici_enter_sifirlar():
    d = _dinleyici(terminal=True)
    for c in "abc":
        _bas(d, _karakter(c))
    _bas(d, keyboard.Key.enter)
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("tetik", "", 3)]


@needs_pynput
def test_dinleyici_hwnd_degisince_guvensiz():
    d = _dinleyici(terminal=True, hwnd=100)
    for c in "abc":
        _bas(d, _karakter(c))
    d._aktif_hwnd_cb = lambda: 200
    _bas(d, _karakter(";"))
    _bas(d, _karakter("e"))
    _bas(d, _karakter("n"))
    assert _kuyruk_joblari(d) == [("guvensiz", "pencere değişti")]


def test_dinleyici_bos_tamponda_tiklama_ve_alt_tab_sorun_degil():
    """Gerileme (Polat'ın elle testi, 16.11.2026): terminale tıklayıp yazınca 'düzenlediniz' hatası veriyordu."""
    d = _dinleyici(terminal=True)
    d._on_click(0, 0, None, True)
    _bas(d, keyboard.Key.alt)
    _bas(d, keyboard.Key.tab)
    _birak(d, keyboard.Key.alt)
    for c in "merhaba nasılsın ;en":
        _bas(d, keyboard.Key.space if c == " " else _karakter(c))
    joblar = _kuyruk_joblari(d)
    assert joblar and joblar[0][0] == "tetik" and joblar[0][1] == "merhaba nasılsın "


@needs_pynput
def test_dinleyici_olcum_sayaclar_doner():
    d = _dinleyici(terminal=True)
    for c in "abc":
        _bas(d, _karakter(c))
    olcum = d.olcum()
    assert olcum["adet"] == 3
    assert olcum["en_yuksek_ns"] >= 0
    assert olcum["ortalama_ns"] >= 0


def test_kisayol_ctrl_ile_gelen_kontrol_karakterini_tanir():
    """Gerileme (Polat'ın elle testi, 15.11.2026): Windows Ctrl+Shift+T'yi KeyCode(vk=84, char='\x14') olarak verir."""
    from pynput.keyboard import Key, KeyCode

    from ceviri_katmani.uygulama.tetik import Dinleyici

    d = Dinleyici("<ctrl>+<shift>+t", ";en", lambda: None, lambda m, s: None, lambda: False)
    for k in (Key.ctrl_l, Key.shift, KeyCode(vk=84, char="\x14")):
        d._on_press(k)
    assert list(d._kuyruk.queue) == [("kisayol",)]
