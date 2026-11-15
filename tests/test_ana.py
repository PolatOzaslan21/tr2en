"""ana.py birim testleri — gerçek pano/pencere/tetik içe aktarmaz."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.kurulum import Sonuc
from ceviri_katmani.uygulama.ana import Uygulama


@dataclass
class Pencere:
    hwnd: int
    surec: str
    sinif: str
    baslik: str


class FakePanoYedegi:
    def __init__(self):
        self.kaydedildi = False
        self.geri_yuklendi = False

    def kaydet(self) -> None:
        self.kaydedildi = True

    def geri_yukle(self) -> bool:
        self.geri_yuklendi = True
        return True


class FakePano:
    def __init__(self, secim: str | None = None):
        self.secim = secim
        self.son_yedek: FakePanoYedegi | None = None
        self.koyulan: str | None = None
        self.yapistirildi = 0
        self.silinen: list[int] = []
        self.koparma = False

    def PanoYedegi(self) -> FakePanoYedegi:
        yedek = FakePanoYedegi()
        self.son_yedek = yedek
        return yedek

    def secimi_kopyala(self, bekle_ms: int = 300) -> str | None:
        return self.secim

    def metin_koy(self, metin: str) -> None:
        if self.koparma:
            raise RuntimeError("panik")
        self.koyulan = metin

    def yapistir(self) -> None:
        self.yapistirildi += 1

    def geri_sil(self, adet: int) -> None:
        self.silinen.append(adet)


class FakePencere:
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
    Pencere = Pencere

    def __init__(self, aktif: Pencere | None = None):
        self.aktif = aktif

    def aktif_pencere(self) -> Pencere | None:
        return self.aktif

    def terminal_mi(self, p: Pencere, ek: set[str] = frozenset()) -> bool:  # type: ignore[assignment]
        return p.surec in (self.TERMINAL_SURECLERI | set(ek))

    def izinli_mi(self, p: Pencere, izinli: set[str] | None, yasak: set[str]) -> bool:
        if p.surec in yasak:
            return False
        if izinli is None:
            return True
        return p.surec in izinli


class FakeZincir:
    def __init__(self, sonuc: Sonuc | None = None, hata: Exception | None = None):
        self.sonuc = sonuc
        self.hata = hata
        self.son_kullanilan: str | None = None
        self.cagrilar: list[str] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append(metin)
        if self.hata:
            raise self.hata
        if self.sonuc is None:
            return metin
        self.son_kullanilan = self.sonuc.cevirmen or "gemini:test"
        return self.sonuc.metin


def make_bildir():
    calls: list[tuple[str, str, str]] = []

    def bildir(baslik: str, mesaj: str = "", seviye: str = "bilgi") -> None:
        calls.append((baslik, mesaj, seviye))

    return calls, bildir


def make_uygulama(secim=None, sonuc=None, hata=None, aktif_surec="notepad.exe"):
    pano = FakePano(secim=secim)
    pencere = FakePencere(
        aktif=Pencere(hwnd=1, surec=aktif_surec, sinif="Edit", baslik="x")
    )
    zincir = FakeZincir(sonuc=sonuc, hata=hata)
    calls, bildir = make_bildir()
    ayarlar = {
        "kisayol": "<ctrl>+<shift>+t",
        "tetik": ";en",
        "izinli": None,
        "yasak": {"keepass.exe", "1password.exe", "bitwarden.exe"},
        "sona_bosluk": False,
        "ek_terminaller": [],
    }
    uyg = Uygulama(pano, pencere, zincir, bildir, ayarlar)
    return uyg, pano, pencere, zincir, calls


# ---- kısayol testleri ----


def test_kisayol_basari_sirasi():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        sonuc=Sonuc(metin="hello how are you", durum="cevrildi", cevirmen="gemini:flash"),
    )
    uyg._kisayol_isle()
    assert zincir.cagrilar == ["merhaba nasılsın"]
    assert pano.koyulan == "hello how are you"
    assert pano.yapistirildi == 1
    assert pano.son_yedek is not None
    assert pano.son_yedek.kaydedildi
    assert pano.son_yedek.geri_yuklendi
    assert calls[0] == ("Çevrildi (Gemini)", "", "bilgi")


def test_kisayol_secim_yok():
    uyg, pano, pencere, zincir, calls = make_uygulama(secim="")
    uyg._kisayol_isle()
    assert zincir.cagrilar == []
    assert calls == [("Seçim yok", "", "bilgi")]


def test_kisayol_zaten_ingilizce():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="hello",
        sonuc=Sonuc(metin="hello", durum="zaten-ingilizce", cevirmen=None),
    )
    uyg._kisayol_isle()
    assert zincir.cagrilar == []
    assert calls == [("Zaten İngilizce", "", "bilgi")]


def test_kisayol_ceviri_hatasi():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        hata=CeviriHatasi("ağ hatası"),
    )
    uyg._kisayol_isle()
    assert zincir.cagrilar == ["merhaba nasılsın"]
    assert pano.koyulan is None
    assert calls == [("Çevrilemedi", "ağ hatası", "hata")]


def test_kisayol_olumsuzluk_hatasi():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="yapma",
        hata=CeviriHatasi("olumsuzluk çeviride kayboldu"),
    )
    uyg._kisayol_isle()
    assert calls == [
        ("Olumsuzluk şüphesi — çevrilmedi", "olumsuzluk çeviride kayboldu", "uyari")
    ]


def test_kisayol_yerel_uyarisi():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        sonuc=Sonuc(metin="hello how are you", durum="cevrildi", cevirmen="yerel:tc-big"),
    )
    uyg._kisayol_isle()
    assert calls[0] == (
        "Yerel modelle çevrildi — kalite düşük olabilir, kontrol edin",
        "",
        "uyari",
    )


def test_kisayol_izinsiz_pencere():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        aktif_surec="keepass.exe",
    )
    uyg._kisayol_isle()
    assert zincir.cagrilar == []
    assert pano.koyulan is None
    assert calls == []


# ---- tetik testleri ----


def test_tetik_basari():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        sonuc=Sonuc(metin="hello how are you", durum="cevrildi", cevirmen="gemini:flash"),
    )
    uyg._tetik_isle("merhaba nasılsın", silinecek=16)
    assert zincir.cagrilar == ["merhaba nasılsın"]
    assert pano.silinen == [16]
    assert pano.koyulan == "hello how are you"
    assert pano.yapistirildi == 1
    assert calls[0] == ("Çevrildi (Gemini)", "", "bilgi")


def test_tetik_basarisiz():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        hata=CeviriHatasi("boş çeviri"),
    )
    uyg._tetik_isle("merhaba nasılsın", silinecek=16)
    assert zincir.cagrilar == ["merhaba nasılsın"]
    assert pano.silinen == [3]
    assert pano.koyulan is None
    assert calls == [("Çevrilemedi", "boş çeviri", "hata")]


def test_guvensiz_bildirim():
    uyg, pano, pencere, zincir, calls = make_uygulama()
    uyg._guvensiz_isle()
    assert calls == [
        (
            "Terminalde metni düzenlediniz — çevrilemedi, ;en'i silin ve tekrar yazın",
            "",
            "bilgi",
        )
    ]


# ---- genel davranış ----


def test_mesgulken_ikinci_istek_yok_sayilir():
    uyg, pano, pencere, zincir, calls = make_uygulama(secim="merhaba nasılsın")
    uyg._meşgul = True
    uyg.kisayol()
    assert uyg._kuyruk.empty()
    assert calls == [("Önceki çeviri sürüyor", "", "bilgi")]


def test_pano_her_yolda_geri_yukleniyor():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        sonuc=Sonuc(metin="hello how are you", durum="cevrildi", cevirmen="gemini:flash"),
    )
    pano.koparma = True
    with pytest.raises(RuntimeError):
        uyg._kisayol_isle()
    assert pano.son_yedek is not None
    assert pano.son_yedek.geri_yuklendi


def test_tetik_zaten_ingilizce_sil():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        sonuc=Sonuc(metin="hello", durum="zaten-ingilizce", cevirmen=None),
    )
    uyg._tetik_isle("hello", silinecek=8)
    assert pano.silinen == [3]
    assert calls == [("Zaten İngilizce", "", "bilgi")]


def test_kisayol_pano_kaydet_geri_yukle():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim="merhaba nasılsın",
        sonuc=Sonuc(metin="hello how are you", durum="cevrildi", cevirmen="gemini:flash"),
    )
    uyg._kisayol_isle()
    assert pano.son_yedek is not None
    assert pano.son_yedek.kaydedildi
    assert pano.son_yedek.geri_yuklendi
    assert pano.yapistirildi == 1
    assert pano.koyulan == "hello how are you"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_uzun_metinde_bekleme_sureleri_uzar():
    """Gerileme (Polat'ın testi, 16.11.2026): 300 karakterlik metin silinip yapıştırılmadan kayboluyordu."""
    from ceviri_katmani.uygulama.ana import _silme_bekle, _yapistirma_bekle

    assert _silme_bekle(303) > _silme_bekle(17) and _silme_bekle(303) >= 0.9
    assert _yapistirma_bekle(330) > _yapistirma_bekle(19) and _yapistirma_bekle(330) >= 0.7
    assert _silme_bekle(10_000) <= 1.5 and _yapistirma_bekle(10_000) <= 2.0
