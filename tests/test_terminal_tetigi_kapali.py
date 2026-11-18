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
