"""Windows açılışında başlatma — HKCU Run anahtarında "tr2en" değeri."""
from __future__ import annotations

import sys
from pathlib import Path

DEGER_ADI = "tr2en"
_ANAHTAR = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _reg_modulu():
    if sys.platform != "win32":
        raise NotImplementedError("otomatik_baslat yalnızca Windows'ta çalışır")
    import winreg

    return winreg


def komut() -> str:
    """Run anahtarına yazılacak komut satırı."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # uv ortamındaki pythonw.exe bir KONSOL başlatıcısı (boş pencere açıyor, 19.11.2026);
    # gui-scripts ile üretilen tr2en.exe gerçek GUI başlatıcısıdır.
    gui = Path(sys.executable).with_name("tr2en.exe")
    if gui.is_file():
        return f'"{gui}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw) if pythonw.is_file() else sys.executable
    return f'"{exe}" -m ceviri_katmani.uygulama'


def acik_mi(*, _reg=None) -> bool:
    """Kayıt defterinde "tr2en" değeri var mı?"""
    reg = _reg if _reg is not None else _reg_modulu()
    try:
        anahtar = reg.OpenKey(reg.HKEY_CURRENT_USER, _ANAHTAR, 0, reg.KEY_READ)
    except OSError:
        return False
    try:
        reg.QueryValueEx(anahtar, DEGER_ADI)
        return True
    except OSError:
        return False
    finally:
        reg.CloseKey(anahtar)


def ac(*, _reg=None) -> None:
    """Açılışta başlatmayı açar."""
    reg = _reg if _reg is not None else _reg_modulu()
    anahtar = reg.OpenKey(reg.HKEY_CURRENT_USER, _ANAHTAR, 0, reg.KEY_SET_VALUE)
    try:
        reg.SetValueEx(anahtar, DEGER_ADI, 0, reg.REG_SZ, komut())
    finally:
        reg.CloseKey(anahtar)


def kapat(*, _reg=None) -> None:
    """Açılışta başlatmayı kapatır; değer yoksa sessizce geçer."""
    reg = _reg if _reg is not None else _reg_modulu()
    try:
        anahtar = reg.OpenKey(reg.HKEY_CURRENT_USER, _ANAHTAR, 0, reg.KEY_SET_VALUE)
    except OSError:
        return
    try:
        reg.DeleteValue(anahtar, DEGER_ADI)
    except OSError:
        pass
    finally:
        reg.CloseKey(anahtar)
