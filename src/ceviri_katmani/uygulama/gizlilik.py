"""İlk açılışta gösterilen gizlilik sorusu (MessageBox)."""
from __future__ import annotations

import sys

METIN = (
    "tr2en seçtiğiniz/yazdığınız metni İngilizceye çevirir.\n\n"
    "• Bulut (önerilen: Google Gemini) seçerseniz metin Google'a gönderilir. Ücretsiz katmanda Google bu metinleri "
    "ürünlerini geliştirmek için kullanabilir.\n"
    "• Yalnızca yerel seçerseniz metin bilgisayarınızdan çıkmaz (kalite daha düşük olabilir).\n\n"
    "Bulut (önerilen: Google Gemini) kullanılsın mı?\n\n"
    "Evet = Bulut (yedek: yerel)   Hayır = Yerel   İptal = Kapat\n"
    "Daha sonra tepsi simgesinden değiştirebilirsiniz."
)

BASLIK = "tr2en — Gizlilik"

MB_YESNOCANCEL = 0x00000003
MB_ICONINFORMATION = 0x00000040
MB_TOPMOST = 0x00040000
MB_SETFOREGROUND = 0x00010000

IDYES = 6
IDNO = 7


def gizlilik_sor(*, mesaj_kutusu=None) -> str | None:
    """Gizlilik sorusunu sorar; Evet->"bulut", Hayır->"yerel", İptal->None.

    ``mesaj_kutusu`` test için: ``(metin, baslik, bayrak) -> int`` callable.
    """
    if mesaj_kutusu is None:
        if sys.platform != "win32":
            raise NotImplementedError("gizlilik_sor yalnızca Windows'ta çalışır")
        import ctypes

        def gercek(metin, baslik, bayrak):
            return ctypes.windll.user32.MessageBoxW(None, metin, baslik, bayrak)

        mesaj_kutusu = gercek
    bayrak = MB_YESNOCANCEL | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    sonuc = mesaj_kutusu(METIN, BASLIK, bayrak)
    if sonuc == IDYES:
        return "bulut"
    if sonuc == IDNO:
        return "yerel"
    return None
