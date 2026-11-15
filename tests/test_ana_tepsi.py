"""ana.py tepsi/yaşam döngüsü testleri — Windows API ve gerçek tepsi açılmaz."""
from __future__ import annotations

from dataclasses import dataclass

from ceviri_katmani.cekirdek.kurulum import Sonuc
from ceviri_katmani.uygulama.ana import Uygulama


@dataclass
class Pencere:
    hwnd: int
    surec: str
    sinif: str
    baslik: str


class FakePanoYedegi:
    def kaydet(self) -> None:
        pass

    def geri_yukle(self) -> bool:
        return True


class FakePano:
    def __init__(self, secim: str | None = None):
        self.secim = secim
        self.koyulan: str | None = None
        self.yapistirildi = 0
        self.silinen: list[int] = []

    def PanoYedegi(self):
        return FakePanoYedegi()

    def secimi_kopyala(self, bekle_ms: int = 300):
        return self.secim

    def metin_koy(self, metin: str) -> None:
        self.koyulan = metin

    def yapistir(self) -> None:
        self.yapistirildi += 1

    def geri_sil(self, adet: int) -> None:
        self.silinen.append(adet)


class FakePencere:
    TERMINAL_SURECLERI = {"cmd.exe", "powershell.exe"}
    Pencere = Pencere

    def __init__(self, aktif: Pencere | None = None):
        self.aktif = aktif

    def aktif_pencere(self):
        return self.aktif

    def terminal_mi(self, p, ek: set[str] = frozenset()):
        return p.surec in (self.TERMINAL_SURECLERI | set(ek))

    def izinli_mi(self, p, izinli, yasak):
        if p.surec in yasak:
            return False
        if izinli is None:
            return True
        return p.surec in izinli


class FakeZincir:
    def __init__(self, sonuc: Sonuc | None = None):
        self.sonuc = sonuc

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        return self.sonuc.metin if self.sonuc else metin

    @property
    def son_kullanilan(self):
        return (self.sonuc.cevirmen if self.sonuc else None) or "gemini:test"


class FakeTepsi:
    def __init__(self):
        self.guncellendi = 0

    def guncelle(self) -> None:
        self.guncellendi += 1


class FakeDinleyici:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.durduruldu = 0

    def baslat(self) -> None:
        pass

    def durdur(self) -> None:
        self.durduruldu += 1


def make_bildir():
    calls: list[tuple[str, str, str]] = []

    def bildir(baslik: str, mesaj: str = "", seviye: str = "bilgi") -> None:
        calls.append((baslik, mesaj, seviye))

    return calls, bildir


def make_uygulama(secim=None, sonuc=None, aktif_surec="notepad.exe", **ek_ayarlar):
    pano = FakePano(secim=secim)
    pencere = FakePencere(
        aktif=Pencere(hwnd=1, surec=aktif_surec, sinif="Edit", baslik="x")
    )
    zincir = FakeZincir(sonuc=sonuc)
    calls, bildir = make_bildir()
    ayarlar = {
        "kisayol": "<ctrl>+<shift>+t",
        "tetik": ";en",
        "izinli": None,
        "yasak": {"keepass.exe"},
        "sona_bosluk": False,
        "ek_terminaller": [],
    }
    ayarlar.update(ek_ayarlar)
    uyg = Uygulama(pano, pencere, zincir, bildir, ayarlar)
    return uyg, pano, pencere, zincir, calls


CEVRILDI = Sonuc(metin="hello", durum="cevrildi", cevirmen="gemini:flash")

GIRDI = "merhaba nasılsın"


# ---- duraklat / aktif ----

def test_duraklatilmisken_kuyruga_is_girmez():
    uyg, pano, pencere, zincir, calls = make_uygulama(secim="merhaba")
    uyg._aktif = False
    uyg.kisayol()
    uyg.tetik("merhaba", 7)
    uyg.guvensiz("fare")
    assert uyg._kuyruk.empty()
    assert calls == []


def test_aktif_degistir_bildirim_ve_tepsi_guncelle():
    uyg, pano, pencere, zincir, calls = make_uygulama()
    tepsi = FakeTepsi()
    uyg.tepsi = tepsi
    uyg.aktif_degistir()
    assert calls == [("Duraklatıldı", "", "bilgi")]
    assert tepsi.guncellendi == 1
    uyg.aktif_degistir()
    assert calls == [
        ("Duraklatıldı", "", "bilgi"),
        ("Etkin", "", "bilgi"),
    ]
    assert tepsi.guncellendi == 2


# ---- sona boşluk ----

def test_tetik_sona_bosluk_acik():
    uyg, pano, pencere, zincir, calls = make_uygulama(sonuc=CEVRILDI, sona_bosluk=True)
    uyg._tetik_isle(GIRDI, silinecek=16)
    assert pano.koyulan == "hello "


def test_tetik_sona_bosluk_kapali():
    uyg, pano, pencere, zincir, calls = make_uygulama(sonuc=CEVRILDI, sona_bosluk=False)
    uyg._tetik_isle(GIRDI, silinecek=16)
    assert pano.koyulan == "hello"


def test_tetik_sona_bosluk_zaten_bosluk():
    sonuc = Sonuc(metin="hello ", durum="cevrildi", cevirmen="gemini:flash")
    uyg, pano, pencere, zincir, calls = make_uygulama(sonuc=sonuc, sona_bosluk=True)
    uyg._tetik_isle(GIRDI, silinecek=16)
    assert pano.koyulan == "hello "


def test_kisayol_bosluk_eklenmez():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim=GIRDI, sonuc=CEVRILDI, sona_bosluk=True
    )
    uyg._kisayol_isle()
    assert pano.koyulan == "hello"


# ---- son çeviri ----

def test_son_ceviri_saklama_kopyalama():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        secim=GIRDI, sonuc=CEVRILDI
    )
    assert uyg.son_ceviri_var_mi() is False
    uyg._kisayol_isle()
    assert uyg.son_ceviri_var_mi() is True
    uyg.son_ceviriyi_goster()
    assert ("Son çeviri", "hello", "bilgi") in calls
    uyg.son_orijinali_kopyala()
    assert pano.koyulan == GIRDI
    assert ("Orijinal metin panoya kopyalandı", "", "bilgi") in calls


# ---- cevirmen seçimi ----

def test_cevirmen_sec_zincir_uretici_kaydet_cb():
    zincir_cagrilari = []
    kaydet_cagrilari = []

    def zincir_uretici(ad):
        zincir_cagrilari.append(ad)
        return FakeZincir()

    def kaydet_cb():
        kaydet_cagrilari.append(1)

    uyg, pano, pencere, zincir, calls = make_uygulama(
        cevirmen="gemini", zincir_uretici=zincir_uretici, kaydet_cb=kaydet_cb
    )
    uyg.cevirmen_sec("yerel")
    assert zincir_cagrilari == ["yerel"]
    assert kaydet_cagrilari == [1]
    assert uyg.ayarlar["cevirmen"] == "yerel"
    assert uyg.zincir is not zincir
    assert ("Çevirmen: Yalnızca yerel", "", "bilgi") in calls

    uyg.cevirmen_sec("yerel")  # aynı seçim -> erken çıkış
    assert zincir_cagrilari == ["yerel"]
    assert kaydet_cagrilari == [1]


# ---- geçmiş ----

def test_gecmis_ozet_eklenir_metin_yok():
    uyg, pano, pencere, zincir, calls = make_uygulama(sonuc=CEVRILDI)
    uyg._tetik_isle("merhaba nasılsın", silinecek=16)
    satirlar = uyg.gecmis.satirlar()
    assert satirlar
    birlestirilmis = " ".join(satirlar)
    assert "merhaba" not in birlestirilmis
    assert "hello" not in birlestirilmis
    assert "cevrildi" in birlestirilmis


# ---- ek terminaller ----

def test_ek_terminaller_terminal_mi_gecer():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        aktif_surec="myterm.exe", ek_terminaller=["myterm.exe"]
    )
    assert uyg._terminal_mi() is True


def test_ek_terminaller_yoksa_terminal_sayilmaz():
    uyg, pano, pencere, zincir, calls = make_uygulama(aktif_surec="myterm.exe")
    assert uyg._terminal_mi() is False


# ---- durdur iki kez ----

def test_durdur_iki_kez():
    uyg, pano, pencere, zincir, calls = make_uygulama(
        dinleyici_sinifi=FakeDinleyici
    )
    uyg.baslat()
    uyg.durdur()
    uyg.durdur()
    assert uyg._dinleyici.durduruldu == 2
