"""Ortam değişkeninden anahtar okuma. Değer asla loglanmaz."""
from __future__ import annotations

import os
import sys


def anahtar_oku(ad: str) -> str | None:
    deger = os.environ.get(ad)
    if deger:
        return deger
    # Windows: `setx` ile kaydedilen değer açık terminallere yansımaz; kayıt defterinden oku.
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                return winreg.QueryValueEx(k, ad)[0] or None
        except OSError:
            return None
    return None
