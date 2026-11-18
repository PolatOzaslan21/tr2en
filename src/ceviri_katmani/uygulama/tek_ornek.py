"""Tek örnek kilidi — aynı uygulamanın ikinci kopyasını engeller."""
from __future__ import annotations

import sys
from types import SimpleNamespace


def _gercek_win():
    import win32api
    import win32event
    import winerror

    return SimpleNamespace(
        CreateMutex=win32event.CreateMutex,
        GetLastError=win32api.GetLastError,
        CloseHandle=win32api.CloseHandle,
        ERROR_ALREADY_EXISTS=winerror.ERROR_ALREADY_EXISTS,
    )


def kilit_al(ad: str = "Local\\Tr2enTekOrnek", *, _win=None) -> object | None:
    """Named mutex alır; zaten varsa handle kapatılıp None döner.

    ``_win`` test için: CreateMutex, GetLastError, CloseHandle ve
    ERROR_ALREADY_EXISTS özniteliklerine sahip sahte nesne.
    """
    win = _win
    if win is None:
        if sys.platform != "win32":
            raise NotImplementedError("kilit_al yalnızca Windows'ta çalışır")
        win = _gercek_win()
    handle = win.CreateMutex(None, False, ad)
    if win.GetLastError() == win.ERROR_ALREADY_EXISTS:
        try:
            win.CloseHandle(handle)
        except Exception:
            pass
        return None
    return handle


def kilit_birak(kilit) -> None:
    """Kilit handle'ını kapatır; None ise sessiz, hata yutulur."""
    if kilit is None:
        return
    try:
        import win32api

        win32api.CloseHandle(kilit)
    except Exception:
        pass
