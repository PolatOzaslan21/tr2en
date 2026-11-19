"""tr2en simgeleri (Pillow ile çizilir; dosya gerekmez).

- ``buyuk_simge``: koyu yuvarlatılmış kare üstünde kırmızı "TR" ve mavi "EN" konuşma balonları,
  arada tek yönlü ok. .exe simgesi ve 32 px üstü için.
- ``sade_simge``: zeminsiz, yazısız, üst üste binen iki balon. Tepsi (16–24 px) için;
  küçükte de kırmızı-mavi ikilisi olarak okunur.
- Pasif (duraklatılmış) hallerde balonlar gridir.

Kenarlar yumuşak olsun diye 4 kat büyük çizilip küçültülür.
"""
from __future__ import annotations

from pathlib import Path

ZEMIN = (24, 29, 39, 255)
KIRMIZI = (225, 29, 46, 255)
MAVI = (14, 165, 233, 255)
BEYAZ = (255, 255, 255, 255)
GRI_ACIK = (156, 163, 175, 255)
GRI_KOYU = (107, 114, 128, 255)
SEFFAF = (0, 0, 0, 0)

_OLCEK = 4


def _renkler(aktif: bool) -> tuple[tuple, tuple]:
    return (KIRMIZI, MAVI) if aktif else (GRI_ACIK, GRI_KOYU)


def _font(boyut: int):
    from PIL import ImageFont

    for ad in ("segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(ad, boyut)
        except OSError:
            continue
    return ImageFont.load_default(boyut)


def _balon(ciz, x0, y0, x1, y1, renk, kuyruk: str) -> None:
    """Yuvarlatılmış kare + altta kuyruk ("sol" ya da "sag")."""
    g, y = x1 - x0, y1 - y0
    ciz.rounded_rectangle((x0, y0, x1, y1), radius=int(min(g, y) * 0.24), fill=renk)
    if kuyruk == "sol":
        ciz.polygon([(x0 + g * 0.16, y1 - 1), (x0 + g * 0.16, y1 + y * 0.30), (x0 + g * 0.46, y1 - 1)], fill=renk)
    else:
        ciz.polygon([(x1 - g * 0.16, y1 - 1), (x1 - g * 0.16, y1 + y * 0.30), (x1 - g * 0.46, y1 - 1)], fill=renk)


def _ortala(ciz, metin, font, cx, cy, renk) -> None:
    sol, ust, sag, alt = ciz.textbbox((0, 0), metin, font=font)
    ciz.text((cx - (sag - sol) / 2 - sol, cy - (alt - ust) / 2 - ust), metin, font=font, fill=renk)


def buyuk_simge(aktif: bool, boyut: int = 256):
    from PIL import Image, ImageDraw

    S = boyut * _OLCEK
    img = Image.new("RGBA", (S, S), SEFFAF)
    c = ImageDraw.Draw(img)
    c.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.22), fill=ZEMIN)
    sol_renk, sag_renk = _renkler(aktif)

    by0, by1 = S * 0.27, S * 0.63
    _balon(c, S * 0.07, by0, S * 0.47, by1, sol_renk, "sol")
    _balon(c, S * 0.53, by0, S * 0.93, by1, sag_renk, "sag")
    f = _font(int(S * 0.17))
    cy = (by0 + by1) / 2
    _ortala(c, "TR", f, S * 0.25, cy, BEYAZ)
    _ortala(c, "EN", f, S * 0.75, cy, BEYAZ)

    # Tek yönlü ok (→): koyu kenarlı beyaz, iki balonun arasında
    def ok(kalinlik, renk):
        x0, x1, uc = S * 0.41, S * 0.59, S * 0.065
        c.line((x0, cy, x1 - kalinlik * 0.3, cy), fill=renk, width=int(kalinlik))
        c.polygon([(x1 + kalinlik * 0.25, cy), (x1 - uc, cy - uc * 1.05), (x1 - uc, cy + uc * 1.05)], fill=renk)

    ok(S * 0.085, ZEMIN)
    c.ellipse((S * 0.41 - S * 0.0425, cy - S * 0.0425, S * 0.41 + S * 0.0425, cy + S * 0.0425), fill=ZEMIN)
    ok(S * 0.04, BEYAZ)
    return img.resize((boyut, boyut), Image.LANCZOS)


def sade_simge(aktif: bool, boyut: int = 64):
    from PIL import Image, ImageDraw

    S = boyut * _OLCEK
    img = Image.new("RGBA", (S, S), SEFFAF)
    c = ImageDraw.Draw(img)
    arka, on = _renkler(aktif)
    # Arkadaki kırmızı balon (sol üst), öndeki mavi balon (sağ alt); arada şeffaf boşluk
    _balon(c, S * 0.0, S * 0.04, S * 0.66, S * 0.56, arka, "sol")
    bosluk = S * 0.06
    x0, y0, x1, y1 = S * 0.34, S * 0.30, S * 1.0, S * 0.80
    _balon(c, x0 - bosluk, y0 - bosluk, x1 + bosluk, y1 + bosluk, SEFFAF, "sag")
    _balon(c, x0, y0, x1 - 1, y1, on, "sag")
    return img.resize((boyut, boyut), Image.LANCZOS)


ICO_BOYUTLARI = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def ico_kaydet(yol: str | Path) -> None:
    """Windows .ico: 24 px ve altı sade, üstü büyük simge."""
    goruntuler = [sade_simge(True, b) if b <= 24 else buyuk_simge(True, b) for b in ICO_BOYUTLARI]
    en_buyuk = goruntuler[-1]
    en_buyuk.save(yol, format="ICO", sizes=[(b, b) for b in ICO_BOYUTLARI], append_images=goruntuler[:-1])
