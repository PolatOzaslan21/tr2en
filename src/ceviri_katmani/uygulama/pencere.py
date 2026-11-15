"""Aktif pencere bilgisi ve terminal/izin mantığı."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

WIN32 = sys.platform == "win32"

if WIN32:
    import win32api
    import win32con
    import win32gui
    import win32process

__all__ = [
    "TERMINAL_SURECLERI",
    "Pencere",
    "aktif_pencere",
    "izinli_mi",
    "terminal_mi",
]

TERMINAL_SURECLERI = {
    "windowsterminal.exe",
    "openconsole.exe",
    "conhost.exe",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "wt.exe",
    "mintty.exe",
    "alacritty.exe",
    "wezterm-gui.exe",
}

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass
class Pencere:
    hwnd: int
    surec: str  # küçük harf exe adı
    sinif: str
    baslik: str


def _surec_adi(hwnd: int) -> str:
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if not pid:
        return ""
    try:
        handle = win32api.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    except Exception:
        return ""
    try:
        try:
            yol = win32process.GetModuleFileNameEx(handle, 0)
        except Exception:
            yol = _tam_yol_sorgula(handle)
        return os.path.basename(yol or "").lower()
    finally:
        try:
            win32api.CloseHandle(handle)
        except Exception:
            pass


def _tam_yol_sorgula(handle) -> str:
    """QueryFullProcessImageNameW ile tam yolu dener."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    boyut = wintypes.DWORD(32768)
    tampon = ctypes.create_unicode_buffer(boyut.value)
    if kernel32.QueryFullProcessImageNameW(
        int(handle), 0, tampon, ctypes.byref(boyut)
    ):
        return tampon.value
    return ""


def aktif_pencere() -> Pencere | None:
    """Ön plandaki pencere; alınamazsa None."""
    if not WIN32:
        raise NotImplementedError("Pencere yardımcıları yalnızca Windows'ta çalışır")
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    try:
        sinif = win32gui.GetClassName(hwnd)
        baslik = win32gui.GetWindowText(hwnd)
    except Exception:
        return None
    return Pencere(hwnd=hwnd, surec=_surec_adi(hwnd), sinif=sinif, baslik=baslik)


def terminal_mi(p: Pencere, ek: set[str] = frozenset()) -> bool:
    """Terminal süreçlerinden biri mi; VS Code terminal sayılmaz."""
    return p.surec in TERMINAL_SURECLERI or p.surec in ek


def izinli_mi(p: Pencere, izinli: set[str] | None, yasak: set[str]) -> bool:
    """izinli None ise yasak dışındaki her şey izinli."""
    if p.surec in yasak:
        return False
    if izinli is None:
        return True
    return p.surec in izinli
