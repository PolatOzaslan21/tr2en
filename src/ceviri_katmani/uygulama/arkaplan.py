"""Konsolsuz başlatma.

uv ortamındaki ``pythonw.exe`` bir KONSOL başlatıcısıdır; ``tr2en.exe`` (gui-scripts) onu
çağırınca Windows Terminal'de boş bir pencere açılıyor ve özet satırları oraya düşüyordu
(Polat'ın testi, 19.11.2026). Çözüm: uygulamayı kendi kendine ``CREATE_NO_WINDOW`` ile
yeniden başlatıp ilk süreçten hemen çıkmak. Alt süreç konsolsuz çalışır.
"""
from __future__ import annotations

import os
import subprocess
import sys

ORTAM = "TR2EN_ARKAPLAN_ALT"
CREATE_NO_WINDOW = 0x08000000


def main(argv: list[str] | None = None, *, popen=subprocess.Popen) -> int:
    """gui-scripts ``tr2en`` ve ``python -m ceviri_katmani.uygulama`` giriş noktası."""
    # PyInstaller .exe'si (frozen) zaten konsolsuz derlenir; orada ``-m`` ile yeniden başlatılamaz.
    if sys.platform != "win32" or os.environ.get(ORTAM) == "1" or getattr(sys, "frozen", False):
        from .ana import main as ana_main

        return ana_main(argv)
    ortam = dict(os.environ)
    ortam[ORTAM] = "1"
    popen(
        [sys.executable, "-m", "ceviri_katmani.uygulama"],
        env=ortam,
        creationflags=CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return 0
