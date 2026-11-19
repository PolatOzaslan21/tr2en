"""sinyal.py testleri — gerçek Windows event'i OLUŞTURULMAZ, sahte _win kullanılır."""
from __future__ import annotations

import threading
import time

from ceviri_katmani.uygulama import sinyal
from ceviri_katmani.uygulama.sinyal import ADLAR, Bekleyici, gonder


class SahteWin:
    EVENT_MODIFY_STATE = 0x0002
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    def __init__(self, acik_olaylar: set[str] | None = None) -> None:
        self.acik_olaylar: set[str] = set(acik_olaylar or ())
        self.setli: set[str] = set()
        self.olusturulan: list[tuple] = []
        self.kapatilan: list = []
        self.set_edilen: list = []
        self.siradaki: list[int] = []
        self._kilit = threading.Lock()

    def OpenEvent(self, erisim, miras, ad):
        if ad not in self.acik_olaylar:
            raise RuntimeError("olay yok")
        return ("acik", ad)

    def SetEvent(self, handle):
        self.set_edilen.append(handle)
        with self._kilit:
            self.setli.add(handle[1])

    def CreateEvent(self, sa, manual, initial, ad):
        self.olusturulan.append((ad, manual, initial))
        self.acik_olaylar.add(ad)
        return ("olay", ad)

    def WaitForMultipleObjects(self, handlelar, wait_all, zaman_asimi):
        time.sleep(0.005)
        with self._kilit:
            if self.siradaki:
                return self.siradaki.pop(0)
            for i, handle in enumerate(handlelar):
                if handle[1] in self.setli:
                    self.setli.discard(handle[1])
                    return self.WAIT_OBJECT_0 + i
        return self.WAIT_TIMEOUT

    def CloseHandle(self, handle):
        self.kapatilan.append(handle)


def bekle(kosul, sure: float = 2.0) -> bool:
    son = time.time() + sure
    while time.time() < son:
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


# ---- gonder ----

def test_gonder_olay_varsa_true_doner():
    win = SahteWin({"Local\\Tr2enAyarYenile"})
    assert gonder("yenile", _win=win) is True
    assert win.set_edilen == [("acik", "Local\\Tr2enAyarYenile")]
    assert win.kapatilan == [("acik", "Local\\Tr2enAyarYenile")]


def test_gonder_olay_yoksa_false_doner_cokmez():
    win = SahteWin()
    assert gonder("cikis", _win=win) is False
    assert win.set_edilen == []


def test_gonder_bilinmeyen_ad_false_doner():
    win = SahteWin({"Local\\Tr2enAyarYenile"})
    assert gonder("olmayan", _win=win) is False
    assert gonder("", _win=win) is False


def test_gonder_setevent_hatasinda_false_doner():
    win = SahteWin({"Local\\Tr2enGoster"})

    def bozuk(handle):
        raise RuntimeError("set edilemedi")

    win.SetEvent = bozuk
    assert gonder("goster", _win=win) is False


def test_adlar_duzeni():
    assert ADLAR == {
        "goster": "Local\\Tr2enGoster",
        "yenile": "Local\\Tr2enAyarYenile",
        "cikis": "Local\\Tr2enCikis",
    }


# ---- Bekleyici ----

def test_bekleyici_eventleri_olusturur():
    win = SahteWin()
    b = Bekleyici({"yenile": lambda: None, "cikis": lambda: None}, _win=win)
    assert [ad for ad, _, _ in win.olusturulan] == [
        "Local\\Tr2enAyarYenile",
        "Local\\Tr2enCikis",
    ]
    assert all(manual is False for _, manual, _ in win.olusturulan)
    b.durdur()


def test_bekleyici_sinyal_geldiginde_cagri_yapar():
    win = SahteWin()
    cagrilar: list[str] = []
    b = Bekleyici(
        {"yenile": lambda: cagrilar.append("yenile"), "cikis": lambda: cagrilar.append("cikis")},
        _win=win,
    )
    b.baslat()
    win.siradaki.append(win.WAIT_OBJECT_0 + 1)
    assert bekle(lambda: cagrilar == ["cikis"])
    win.siradaki.append(win.WAIT_OBJECT_0 + 0)
    assert bekle(lambda: cagrilar == ["cikis", "yenile"])
    b.durdur()


def test_bekleyici_istisna_threadi_oldurmez():
    win = SahteWin()
    sayac: list[int] = []

    def bozuk():
        sayac.append(1)
        raise RuntimeError("boom")

    b = Bekleyici({"yenile": bozuk}, _win=win)
    b.baslat()
    win.siradaki.append(win.WAIT_OBJECT_0 + 0)
    assert bekle(lambda: len(sayac) >= 1)
    win.siradaki.append(win.WAIT_OBJECT_0 + 0)
    assert bekle(lambda: len(sayac) >= 2)
    b.durdur()


def test_bekleyici_durdur_handlelari_kapatir():
    win = SahteWin()
    b = Bekleyici({"goster": lambda: None}, _win=win)
    b.baslat()
    b.durdur()
    assert len(win.kapatilan) == 1
    b.durdur()
    assert len(win.kapatilan) == 1


def test_bekleyici_baslat_iki_kez_tek_thread():
    win = SahteWin()
    b = Bekleyici({"goster": lambda: None}, _win=win)
    b.baslat()
    ilk = b._thread
    b.baslat()
    assert b._thread is ilk
    b.durdur()
    assert ilk is not None and not ilk.is_alive()


def test_bekleyici_bilinmeyen_ad_dinlemez():
    win = SahteWin()
    cagrilar: list[str] = []
    b = Bekleyici({"olmayan": lambda: cagrilar.append("x")}, _win=win)
    assert win.olusturulan == []
    b.baslat()
    b.durdur()
    assert cagrilar == []


def test_bekleyici_ile_gonder_uyumlu():
    win = SahteWin()
    cagrilar: list[str] = []
    b = Bekleyici({"yenile": lambda: cagrilar.append("y")}, _win=win)
    b.baslat()
    assert gonder("yenile", _win=win) is True
    assert bekle(lambda: cagrilar == ["y"])
    b.durdur()


def test_bekleyici_zaman_asiminda_donguler():
    win = SahteWin()
    b = Bekleyici({"yenile": lambda: None}, _win=win)
    b.baslat()
    assert bekle(lambda: b._calisiyor.is_set())
    time.sleep(0.05)
    assert b._thread is not None and b._thread.is_alive()
    b.durdur()


def test_sinyal_modulu_win_enjeksiyonu_dokunulmaz():
    assert callable(sinyal.gonder)
