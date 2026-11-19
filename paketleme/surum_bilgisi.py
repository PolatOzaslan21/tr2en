"""tr2en.exe için Windows sürüm bilgisi dosyası üretir (PyInstaller --version-file).

Kullanım: python paketleme/surum_bilgisi.py <çıktı-yolu>
Sürüm numarası paketin kendisinden (ceviri_katmani.__version__) okunur.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from ceviri_katmani import __version__

SABLON = """# Otomatik üretildi (paketleme/surum_bilgisi.py); elle düzenlemeyin.
VSVersionInfo(
  ffi=FixedFileInfo(filevers={dortlu}, prodvers={dortlu}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041f04b0', [
      StringStruct('CompanyName', 'PolatOzaslan21'),
      StringStruct('FileDescription', 'tr2en - Türkçe → İngilizce çeviri'),
      StringStruct('FileVersion', '{surum}'),
      StringStruct('InternalName', 'tr2en'),
      StringStruct('LegalCopyright', 'MIT Lisansı - github.com/PolatOzaslan21/tr2en'),
      StringStruct('OriginalFilename', 'tr2en.exe'),
      StringStruct('ProductName', 'tr2en'),
      StringStruct('ProductVersion', '{surum}')])]),
    VarFileInfo([VarStruct('Translation', [0x041f, 1200])])
  ]
)
"""


def dortlu(surum: str) -> tuple[int, int, int, int]:
    sayilar = [int(x) for x in re.findall(r"\d+", surum)[:4]]
    return tuple((sayilar + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def uret(surum: str = __version__) -> str:
    return SABLON.format(dortlu=dortlu(surum), surum=surum)


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(uret(), encoding="utf-8")
