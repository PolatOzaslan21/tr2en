"""Süreçler arası sinyaller — Windows named event'leri (otomatik sıfırlanan).

Ayar penceresi süreci ``gonder`` ile olay tetikler; ana uygulama ``Bekleyici``
ile dinler. Ana uygulama çalışmıyorsa (olay oluşturulmamışsa) ``gonder``
False döner ve çökmez. Gerçek Windows çağrıları yalnızca ``_win`` verilmediğinde
yapılır; testler sahte ``_win`` nesnesi enjekte eder, gerçek event oluşmaz.
"""
from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from types import SimpleNamespace

ADLAR: dict[str, str] = {
    "goster": "Local\\Tr2enGoster",
    "yenile": "Local\\Tr2enAyarYenile",
    "cikis": "Local\\Tr2enCikis",
}

BEKLEME_MS = 500


def _gercek_win() -> SimpleNamespace:
    import win32api
    import win32event

    return SimpleNamespace(
        OpenEvent=win32event.OpenEvent,
        SetEvent=win32event.SetEvent,
        CreateEvent=win32event.CreateEvent,
        WaitForMultipleObjects=win32event.WaitForMultipleObjects,
        CloseHandle=win32api.CloseHandle,
        EVENT_MODIFY_STATE=win32event.EVENT_MODIFY_STATE,
        WAIT_OBJECT_0=win32event.WAIT_OBJECT_0,
        WAIT_TIMEOUT=win32event.WAIT_TIMEOUT,
    )


def gonder(ad: str, *, _win=None) -> bool:
    """Adı verilen olayı tetikler; olay yoksa False döner, çökmez.

    ``_win`` test için: OpenEvent, SetEvent, CloseHandle ve EVENT_MODIFY_STATE
    özniteliklerine sahip sahte nesne (tek_ornek.py'deki kalıp).
    """
    if ad not in ADLAR:
        return False
    win = _win
    if win is None:
        if sys.platform != "win32":
            return False
        win = _gercek_win()
    handle = None
    try:
        handle = win.OpenEvent(win.EVENT_MODIFY_STATE, False, ADLAR[ad])
        win.SetEvent(handle)
        return True
    except Exception:
        return False
    finally:
        if handle is not None:
            try:
                win.CloseHandle(handle)
            except Exception:
                pass


class Bekleyici:
    """Named event'leri oluşturur, arka plan thread'inde dinler.

    ``geri_cagrilar``: sinyal adı → çağrılacak işlev. Yalnızca ``ADLAR``'daki
    adlar dinlenir. ``_win`` test için: CreateEvent, WaitForMultipleObjects,
    CloseHandle, WAIT_OBJECT_0 özniteliklerine sahip sahte nesne.
    """

    def __init__(self, geri_cagrilar: dict[str, Callable[[], None]], *, _win=None) -> None:
        self.geri_cagrilar: dict[str, Callable[[], None]] = {
            ad: cb for ad, cb in dict(geri_cagrilar).items() if ad in ADLAR
        }
        win = _win
        if win is None:
            if sys.platform != "win32":
                raise NotImplementedError("Bekleyici yalnızca Windows'ta çalışır")
            win = _gercek_win()
        self._win = win
        self._adlar: list[str] = list(self.geri_cagrilar)
        self._handlelar: list = [
            win.CreateEvent(None, False, False, ADLAR[ad]) for ad in self._adlar
        ]
        self._calisiyor = threading.Event()
        self._thread: threading.Thread | None = None
        self._kapandi = False

    def baslat(self) -> None:
        """Arka plan thread'ini başlatır; zaten çalışıyorsa dokunmaz."""
        if self._kapandi or self._calisiyor.is_set() or not self._handlelar:
            return
        self._calisiyor.set()
        self._thread = threading.Thread(
            target=self._dongu, name="tr2en-sinyal", daemon=True
        )
        self._thread.start()

    def _dongu(self) -> None:
        win = self._win
        while self._calisiyor.is_set():
            try:
                sonuc = win.WaitForMultipleObjects(self._handlelar, False, BEKLEME_MS)
            except Exception:
                break
            if not self._calisiyor.is_set():
                break
            index = int(sonuc) - int(win.WAIT_OBJECT_0)
            if 0 <= index < len(self._handlelar):
                try:
                    self.geri_cagrilar[self._adlar[index]]()
                except Exception:
                    pass

    def durdur(self) -> None:
        """Döngüyü bitirir, handle'ları kapatır. Birden çok kez çağrılabilir."""
        self._calisiyor.clear()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._kapandi = True
        for handle in self._handlelar:
            try:
                self._win.CloseHandle(handle)
            except Exception:
                pass
        self._handlelar = []
