"""Tek örnek kilidi ve gizlilik sorusu testleri (gerçek Windows çağrısı yok)."""
from __future__ import annotations

from ceviri_katmani.uygulama.gizlilik import METIN, gizlilik_sor
from ceviri_katmani.uygulama.tek_ornek import kilit_al, kilit_birak


class SahteWin:
    ERROR_ALREADY_EXISTS = 183

    def __init__(self):
        self.varolan = set()
        self.son_hata = 0
        self.kapatilan = []

    def CreateMutex(self, g1, g2, ad):
        varmis = ad in self.varolan
        self.varolan.add(ad)
        self.son_hata = self.ERROR_ALREADY_EXISTS if varmis else 0
        return object()

    def GetLastError(self):
        return self.son_hata

    def CloseHandle(self, h):
        self.kapatilan.append(h)


def test_kilit_al_ilk_cagri_handle_doner():
    sahte = SahteWin()
    assert kilit_al("Test", _win=sahte) is not None


def test_kilit_al_ikinci_cagri_none_doner():
    sahte = SahteWin()
    kilit_al("Test", _win=sahte)
    assert kilit_al("Test", _win=sahte) is None
    assert len(sahte.kapatilan) == 1


def test_kilit_al_farkli_ad_ayri_kilit():
    sahte = SahteWin()
    kilit_al("Bir", _win=sahte)
    assert kilit_al("Iki", _win=sahte) is not None


def test_kilit_birak_none_sessiz():
    kilit_birak(None)


def test_gizlilik_sor_evet_gemini():
    def kutu(metin, baslik, bayrak):
        assert baslik == "Çeviri Katmanı — Gizlilik"
        return 6

    assert gizlilik_sor(mesaj_kutusu=kutu) == "gemini"


def test_gizlilik_sor_hayir_yerel():
    assert gizlilik_sor(mesaj_kutusu=lambda m, b, f: 7) == "yerel"


def test_gizlilik_sor_iptal_none():
    assert gizlilik_sor(mesaj_kutusu=lambda m, b, f: 2) is None


def test_gizlilik_metin_dolu():
    assert "Gemini" in METIN
    assert "Yalnızca yerel" in METIN
    assert "bilgisayarınızdan çıkmaz" in METIN
