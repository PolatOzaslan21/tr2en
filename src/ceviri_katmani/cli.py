"""Komut satırı: ceviri "metin"  ya da  echo metin | ceviri"""
from __future__ import annotations

import argparse
import sys

from .cekirdek import CeviriHatasi
from .cekirdek.kurulum import akilli_cevir, zincir_kur


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ceviri", description="Türkçe metni İngilizceye çevirir.")
    p.add_argument("metin", nargs="*", help="Çevrilecek metin (boşsa stdin)")
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    p.add_argument("--yalniz", choices=["gemini", "yerel"], help="Yalnızca bu çevirmeni kullan")
    p.add_argument("-v", "--ayrinti", action="store_true", help="Hangi çevirmenin kullanıldığını göster")
    p.add_argument("--korumasiz", action="store_true", help="Koruma katmanını devre dışı bırak")
    p.add_argument("--dil-kontrolsuz", action="store_true", help="Zaten İngilizce mi kontrolünü atla")
    a = p.parse_args(argv)
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8")
    metin = " ".join(a.metin) if a.metin else sys.stdin.read()
    zincir = zincir_kur(model=a.model, yalniz=a.yalniz, korumasiz=a.korumasiz)
    try:
        sonuc = akilli_cevir(zincir, metin.strip(), dil_kontrolu=not a.dil_kontrolsuz)
    except CeviriHatasi as e:
        print(f"Hata: {e}", file=sys.stderr)
        return 1
    print(sonuc.metin)
    if a.ayrinti:
        print(f"[{sonuc.durum}{': ' + sonuc.cevirmen if sonuc.cevirmen else ''}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
