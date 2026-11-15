"""Komut satırı: ceviri "metin"  ya da  echo metin | ceviri"""
from __future__ import annotations

import argparse
import sys

from .cekirdek import CeviriHatasi, CevirmenZinciri
from .cekirdek.gemini import GeminiCevirmen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ceviri", description="Türkçe metni İngilizceye çevirir.")
    p.add_argument("metin", nargs="*", help="Çevrilecek metin (boşsa stdin)")
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    p.add_argument("-v", "--ayrinti", action="store_true", help="Hangi çevirmenin kullanıldığını göster")
    a = p.parse_args(argv)
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8")
    metin = " ".join(a.metin) if a.metin else sys.stdin.read()
    zincir = CevirmenZinciri([GeminiCevirmen(model=a.model)])
    try:
        print(zincir.cevir(metin.strip()))
    except CeviriHatasi as e:
        print(f"Hata: {e}", file=sys.stderr)
        return 1
    if a.ayrinti:
        print(f"[{zincir.son_kullanilan}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
