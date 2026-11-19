"""Denetim-1 (INCELEME-1) düzeltmelerinin testleri — uygulama katmanı.

Kurallar:
- Gerçek pano / gerçek klavye / gerçek kayıt defteri / %APPDATA% YOK.
  Her şey sahte pano, sahte pencere, sahte bildirim ve sahte zincirle enjekte edilir.
- Her düzeltme için önce hatayı YAKALAYAN test yazıldı (düzeltmeden önce başarısız).
"""
from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.kurulum import Sonuc
from ceviri_katmani.uygulama.ana import Uygulama

WIN32 = sys.platform == "win32"
WINDOWS_YALNIZ = pytest.mark.skipif(not WIN32, reason="Windows'a özgü")
KOK = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Sahte nesneler
# --------------------------------------------------------------------------- #
@dataclass
class Pencere:
    hwnd: int
    surec: str
    sinif: str
    baslik: str


class SahteYedek:
    """Pano yedeği; geri_yukle sonucu/istisnası ayarlanabilir."""

    def __init__(self, sonuc: bool = True, patlat: bool = False) -> None:
        self.sonuc = sonuc
        self.patlat = patlat
        self.kaydedildi = False
        self.geri_yuklendi = False

    def kaydet(self) -> None:
        self.kaydedildi = True

    def geri_yukle(self) -> bool:
        self.geri_yuklendi = True
        if self.patlat:
            raise RuntimeError("pano kilitli")
        return self.sonuc


class SahtePano:
    def __init__(self, secim: str | None = "merhaba dünya",
                 hata: Exception | None = None,
                 yedek: SahteYedek | None = None) -> None:
        self.secim = secim
        self.hata = hata
        self.yedek = yedek if yedek is not None else SahteYedek()
        self.koyulan: str | None = None
        self.yapistirildi = 0
        self.silinen: list[int] = []

    def PanoYedegi(self) -> SahteYedek:
        return self.yedek

    def secimi_kopyala(self, bekle_ms: int = 300) -> str | None:
        if self.hata is not None:
            raise self.hata
        return self.secim

    def metin_koy(self, metin: str) -> None:
        self.koyulan = metin

    def yapistir(self) -> None:
        self.yapistirildi += 1

    def geri_sil(self, adet: int) -> None:
        self.silinen.append(adet)


class SahtePencere:
    """Gerçek pencere.izinli_mi ile AYNI davranış (boş küme = izin yok)."""

    def __init__(self, surec: str = "notepad.exe") -> None:
        self.surec = surec
        self.cagrilar: list[tuple[str, object, object]] = []

    def aktif_pencere(self) -> Pencere:
        return Pencere(1, self.surec, "Edit", "x")

    def izinli_mi(self, p: Pencere, izinli, yasak) -> bool:
        self.cagrilar.append((p.surec, izinli, yasak))
        if p.surec in (yasak or set()):
            return False
        if izinli is None:
            return True
        return p.surec in izinli

    def terminal_mi(self, p: Pencere, ek=None) -> bool:
        return False


class SahteZincir:
    def __init__(self, metin: str = "hello world", hata: Exception | None = None) -> None:
        self.metin = metin
        self.hata = hata
        self.son_kullanilan: str | None = "gemini:sahte"
        self.cagrilar: list[str] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append(metin)
        if self.hata is not None:
            raise self.hata
        return self.metin


class SahteDinleyici:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.baslatildi = 0
        self.durduruldu = 0

    def baslat(self) -> None:
        self.baslatildi += 1

    def durdur(self) -> None:
        self.durduruldu += 1


def _uygulama(secim: str | None = "merhaba dünya",
              ceviri: str = "hello world",
              hata: Exception | None = None,
              izinli=None,
              yasak=None,
              yedek: SahteYedek | None = None,
              pano_hata: Exception | None = None,
              kaydet_cb=None):
    pano = SahtePano(secim=secim, hata=pano_hata, yedek=yedek)
    pencere = SahtePencere()
    zincir = SahteZincir(metin=ceviri, hata=hata)
    calls: list[tuple[str, str, str]] = []

    def bildir(baslik: str, mesaj: str = "", seviye: str = "bilgi") -> None:
        calls.append((baslik, mesaj, seviye))

    ayarlar = {
        "kisayol": "<ctrl>+<shift>+<space>",
        "tetik": ";en",
        "izinli": izinli,
        "yasak": set(yasak) if yasak else set(),
        "sona_bosluk": False,
        "ozet_kaydi": True,
        "dinleyici_sinifi": SahteDinleyici,
    }
    if kaydet_cb is not None:
        ayarlar["kaydet_cb"] = kaydet_cb
    uyg = Uygulama(pano, pencere, zincir, bildir, ayarlar)
    return uyg, pano, pencere, zincir, calls


def _isci_kostur(uyg, *isler, bekle: float = 5.0) -> None:
    """Verilen işleri işçi döngüsünde koşturur (ayrı thread) ve bitmesini bekler."""
    for is_ in isler:
        uyg._kuyruk.put(is_)
    uyg._kuyruk.put(None)
    uyg._calis = True
    t = threading.Thread(target=uyg._isci_dongusu, daemon=True)
    t.start()
    t.join(bekle)


# --------------------------------------------------------------------------- #
# MADDE 1 — işçi döngüsü beklenmedik istisnada ölmüyor
# --------------------------------------------------------------------------- #
def test_isci_beklenmeyen_hata_yutuyor_sonraki_kisayol_calisiyor():
    """Pano OSError verirse işçi ölmemeli; sonraki kısayol çalışmalı ve
    kullanıcı 'Beklenmeyen hata' bildirimi almalı."""
    uyg, pano, pencere, zincir, calls = _uygulama()
    durum = {"hata": True}

    def secimi_kopyala(bekle_ms: int = 300):
        # İlk çağrı hata verir (pano kilitli), ikinci çağrı normaldir.
        if durum["hata"]:
            durum["hata"] = False
            raise OSError("pano kilitli")
        return "merhaba dünya"

    uyg.pano.secimi_kopyala = secimi_kopyala
    _isci_kostur(uyg, ("kisayol", None), ("kisayol", None))

    assert uyg._meşgul is False, "işçi istisnada takılıp kalmamalı"
    assert any(c[0] == "Beklenmeyen hata" for c in calls), \
        "beklenmeyen hata bildirimi yok"
    assert any(c[0] == "Çevrildi (Gemini)" for c in calls), \
        "istisna sonrası ikinci kısayol çalışmadı (işçi öldü)"
    assert uyg.pano.koyulan == "hello world"


def test_beklenmeyen_hata_ayrintisi_yalnizca_tur_adi():
    """Hata bildirimi ve geçmiş yalnızca hata TÜRÜNÜ taşır; metin içeriği ASLA."""
    gizli = "şifrem SuperGizli123"
    uyg, pano, pencere, zincir, calls = _uygulama(
        secim=gizli,
        pano_hata=OSError("pano kilitli"),
    )
    _isci_kostur(uyg, ("kisayol", None))

    hata_bildirimleri = [c for c in calls if c[0] == "Beklenmeyen hata"]
    assert hata_bildirimleri, "beklenmeyen hata bildirimi yok"
    baslik, mesaj, seviye = hata_bildirimleri[0]
    assert mesaj == "OSError", "bildirim yalnızca kısa hata türü adını taşımalı"
    assert seviye == "hata"
    assert gizli not in mesaj

    islemler = uyg.gecmis.liste()
    hatali = [i for i in islemler if i.durum == "hata"]
    assert hatali, "geçmişe hata kaydı yazılmadı"
    assert hatali[0].ayrinti == "OSError"
    for islem in islemler:
        assert gizli not in islem.satir()


# --------------------------------------------------------------------------- #
# MADDE 2 — pano yedeği geri yüklenemezse kullanıcı bilgilendiriliyor
# --------------------------------------------------------------------------- #
@WINDOWS_YALNIZ
def test_pano_yedegi_kismi_hata_dursa_false_doner(monkeypatch):
    """Bir biçim SetClipboardData ile yazılamazsa geri_yukle False dönmeli;
    diğer biçimler yine denemeli."""
    from ceviri_katmani.uygulama import pano

    denenen: list[int] = []

    def set_clipboard_data(bicim, veri):
        denenen.append(bicim)
        if bicim == 2:
            raise RuntimeError("biçim yazılamadı")
        return None

    class Yapay:
        OpenClipboard = staticmethod(lambda *a: None)
        CloseClipboard = staticmethod(lambda *a: None)
        EmptyClipboard = staticmethod(lambda *a: None)
        SetClipboardData = staticmethod(set_clipboard_data)

    monkeypatch.setattr(pano, "win32clipboard", Yapay)

    yedek = pano.PanoYedegi()
    yedek._veriler = {1: "metin", 2: "resim", 3: "html"}
    yedek._kaydedildi = True

    assert yedek.geri_yukle() is False, "kısmi başarısızlık False dönmeli"
    assert denenen == [1, 2, 3], "başarısız biçimden sonrakiler de denenmeli"


@WINDOWS_YALNIZ
def test_pano_yedegi_basarisiz_geri_yukleme_false(monkeypatch):
    """Pano hiç açılamıyorsa geri_yukle False döner (mevcut davranış korunur)."""
    from ceviri_katmani.uygulama import pano

    def ac(*a):
        raise RuntimeError("locked")

    class Yapay:
        OpenClipboard = staticmethod(ac)
        CloseClipboard = staticmethod(lambda *a: None)
        EmptyClipboard = staticmethod(lambda *a: None)
        SetClipboardData = staticmethod(lambda *a: None)

    monkeypatch.setattr(pano, "win32clipboard", Yapay)
    monkeypatch.setattr(pano.time, "sleep", lambda s: None)

    yedek = pano.PanoYedegi()
    yedek._veriler = {1: "metin"}
    yedek._kaydedildi = True
    assert yedek.geri_yukle() is False


def test_kisayol_yolunda_pano_geri_yuklenemezse_uyarilir():
    """geri_yukle() False dönerse kullanıcı uyarılmalı."""
    yedek = SahteYedek(sonuc=False)
    uyg, pano, pencere, zincir, calls = _uygulama(yedek=yedek)
    uyg._kisayol_isle()
    assert ("Panonuz tam geri yüklenemedi",
            "Kopyaladığınız son içerik kaybolmuş olabilir.",
            "uyari") in calls


def test_tetik_yolunda_pano_geri_yuklenemezse_uyarilir():
    """Tetik yolunda da aynı kontrol ve bildirim var."""
    yedek = SahteYedek(sonuc=False)
    uyg, pano, pencere, zincir, calls = _uygulama(yedek=yedek)
    uyg._tetik_isle("merhaba dünya", 3)
    assert ("Panonuz tam geri yüklenemedi",
            "Kopyaladığınız son içerik kaybolmuş olabilir.",
            "uyari") in calls


def test_pano_geri_yukleme_istisna_olursa_uyarilir():
    """geri_yukle() istisna atarsa da uyarı gösterilmeli (çökme yok)."""
    yedek = SahteYedek(patlat=True)
    uyg, pano, pencere, zincir, calls = _uygulama(yedek=yedek)
    uyg._kisayol_isle()
    assert ("Panonuz tam geri yüklenemedi",
            "Kopyaladığınız son içerik kaybolmuş olabilir.",
            "uyari") in calls


# --------------------------------------------------------------------------- #
# MADDE 3 — yerel model indiriliyorken özel bildirim
# --------------------------------------------------------------------------- #
def test_yerel_model_indirilirken_ozel_bildirim(monkeypatch):
    """Model indiriliyorken 'model klasörü yok' hatası genel hata olarak
    gösterilmemeli; 'Yerel model henüz indiriliyor' uyarısı çıkmalı."""
    from ceviri_katmani.uygulama import model_indirme

    monkeypatch.setattr(model_indirme, "durum", lambda: "indiriliyor %42")
    uyg, pano, pencere, zincir, calls = _uygulama(
        hata=CeviriHatasi("model klasörü yok: C:/x/tc-big-tr-en-int8"),
    )
    uyg._kisayol_isle()
    assert ("Yerel model henüz indiriliyor",
            "%42 — bitince tekrar deneyin. Bu sırada Gemini kullanılabilir.",
            "uyari") in calls
    assert not any(c[0] == "Çevrilemedi" for c in calls), \
        "genel hata bildirimi de gösterilmemeli"


def test_tetik_yolunda_yerel_model_indirilirken_ozel_bildirim(monkeypatch):
    from ceviri_katmani.uygulama import model_indirme

    monkeypatch.setattr(model_indirme, "durum", lambda: "indiriliyor %7")
    uyg, pano, pencere, zincir, calls = _uygulama(
        hata=CeviriHatasi("model klasörü yok: C:/x/tc-big-tr-en-int8"),
    )
    uyg._tetik_isle("merhaba dünya", 3)
    assert ("Yerel model henüz indiriliyor",
            "%7 — bitince tekrar deneyin. Bu sırada Gemini kullanılabilir.",
            "uyari") in calls


def test_indirme_yokken_genel_hata_gosterilir(monkeypatch):
    """Model indirilmiyorsa (durum 'yok'/'hazir') eski genel hata akışı korunur."""
    from ceviri_katmani.uygulama import model_indirme

    monkeypatch.setattr(model_indirme, "durum", lambda: "yok")
    uyg, pano, pencere, zincir, calls = _uygulama(
        hata=CeviriHatasi("model klasörü yok: C:/x/tc-big-tr-en-int8"),
    )
    uyg._kisayol_isle()
    assert any(c[0] == "Çevrilemedi" for c in calls)
    assert not any(c[0] == "Yerel model henüz indiriliyor" for c in calls)


def test_indirme_durumu_bilinmiyorsa_genel_hata(monkeypatch):
    """durum() 'indiriliyor' ile başlamıyorsa özel bildirim gösterilmez."""
    from ceviri_katmani.uygulama import model_indirme

    monkeypatch.setattr(model_indirme, "durum", lambda: "hata")
    uyg, pano, pencere, zincir, calls = _uygulama(
        hata=CeviriHatasi("model klasörü yok: C:/x/tc-big-tr-en-int8"),
    )
    uyg._kisayol_isle()
    assert any(c[0] == "Çevrilemedi" for c in calls)
    assert not any(c[0] == "Yerel model henüz indiriliyor" for c in calls)


# --------------------------------------------------------------------------- #
# MADDE 4 — ayar dosyası yazılamıyor
# --------------------------------------------------------------------------- #
def test_ayarlar_kaydet_basarisizda_false_doner(tmp_path, monkeypatch):
    """Yazma hatasında kaydet() istisna yerine False dönmeli."""
    from ceviri_katmani.uygulama import ayarlar as a

    def sahte_replace(src, dst, *args, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(a.os, "replace", sahte_replace)
    yol = tmp_path / "ayarlar.toml"
    assert a.kaydet({"kisayol": "<ctrl>+<shift>+<space>"}, yol) is False
    assert not yol.exists(), "başarısız kayıttan sonra ayar dosyası oluşmamalı"


def test_ayarlar_kaydet_basarisizda_true_doner(tmp_path):
    """Başarılı kayıt True dönmeli."""
    from ceviri_katmani.uygulama import ayarlar as a

    yol = tmp_path / "ayarlar.toml"
    assert a.kaydet({"kisayol": "<ctrl>+<shift>+<space>"}, yol) is True
    assert yol.exists()


def test_yazilamaz_bozuk_ayar_dosyasinda_varsayilanlar_ve_uyari(tmp_path, monkeypatch):
    """Bozuk + yazılamaz ayar dosyasında yukle() çökmemeli; varsayılanlar
    dönmeli ve uyarı listesinde 'ayar dosyası yazılamadı' yer almalı."""
    from ceviri_katmani.uygulama import ayarlar as a
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN

    yol = tmp_path / "ayarlar.toml"
    yol.write_text("= bozuk [", encoding="utf-8")

    def sahte_replace(src, dst, *args, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(a.os, "replace", sahte_replace)
    ayarlar, uyarilar = a.yukle(yol)
    assert ayarlar == VARSAYILAN
    assert any("ayar dosyası yazılamadı" in u for u in uyarilar), \
        "yazılamadı uyarısı yok"


def test_yedeklenemeyen_bozuk_ayar_dosyasinda_uyari(tmp_path, monkeypatch):
    """Yedekleme başarısız olsa bile 'ayar dosyası yazılamadı' uyarısı verilmeli."""
    from ceviri_katmani.uygulama import ayarlar as a
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN

    yol = tmp_path / "ayarlar.toml"
    yol.write_text("= bozuk [", encoding="utf-8")

    gercek_replace = a.os.replace
    sayac = {"n": 0}

    def sahte_replace(src, dst, *args, **k):
        sayac["n"] += 1
        if sayac["n"] == 1:  # ilk çağrı: yedekleme
            raise PermissionError(13, "Access denied")
        return gercek_replace(src, dst, *args, **k)

    monkeypatch.setattr(a.os, "replace", sahte_replace)
    ayarlar, uyarilar = a.yukle(yol)
    assert ayarlar == VARSAYILAN
    assert any("ayar dosyası yazılamadı" in u for u in uyarilar), \
        "yedeklenemedi uyarısı yok"


def test_ana_kaydet_basarisiz_olursa_uyarir():
    """kaydet_cb False dönerse 'Ayar kaydedilemedi' uyarısı gösterilmeli."""
    uyg, pano, pencere, zincir, calls = _uygulama(
        kaydet_cb=lambda: False,
    )
    uyg.cevirmen_sec("yerel")
    assert any(c[0] == "Ayar kaydedilemedi" for c in calls), \
        "ayar kaydedilemedi uyarısı yok"
    assert any(c[2] == "uyari" for c in calls if c[0] == "Ayar kaydedilemedi")


def test_ana_kaydet_basarisiz_olursa_kisayol_yolunda_uyarir():
    uyg, pano, pencere, zincir, calls = _uygulama(
        kaydet_cb=lambda: False,
    )
    uyg.kisayol_sec("<ctrl>+<shift>+t")
    assert any(c[0] == "Ayar kaydedilemedi" for c in calls)


def test_ana_kaydet_basarisiz_olursa_hata_uretmez():
    """kaydet_cb istisna atarsa da çökme olmamalı, uyarı gösterilmeli."""
    def patlayan():
        raise OSError("disk dolu")

    uyg, pano, pencere, zincir, calls = _uygulama(kaydet_cb=patlayan)
    uyg.cevirmen_sec("yerel")
    assert any(c[0] == "Ayar kaydedilemedi" for c in calls)


# --------------------------------------------------------------------------- #
# MADDE 5 — kurulamayan kısayolda geri alma
# --------------------------------------------------------------------------- #
def test_kisayol_kurulamazsa_eskisi_korunur():
    """Yeni dinleyici kurulamazsa: eski kısayol geri gelir, eski dinleyici
    yeniden kurulur, kullanıcı uyarılır ve ayar dosyasına YENİ DEĞER YAZILMAZ."""
    yazilan: list[str] = []
    uyg, pano, pencere, zincir, calls = _uygulama(
        kaydet_cb=lambda: yazilan.append(uyg.ayarlar["kisayol"]),
    )
    uyg.baslat()
    eski_dinleyici = uyg._dinleyici
    eski_kisayol = uyg.ayarlar["kisayol"]

    def kurus():
        raise RuntimeError("pynput hotkey kaydedilemedi")

    uyg._dinleyici_kur = kurus
    uyg.kisayol_sec("<ctrl>+<alt>+<shift>+q")

    assert uyg.ayarlar["kisayol"] == eski_kisayol, "eski kısayol geri gelmedi"
    assert uyg._dinleyici is eski_dinleyici, "eski dinleyici geri yüklenmedi"
    assert eski_dinleyici.baslatildi >= 2, "eski dinleyici yeniden kurulmadı"
    assert not yazilan, "ayar dosyasına yeni (bozuk) kısayol yazıldı"
    assert any(c[0] == "Kısayol değiştirilemedi" for c in calls), \
        "kısayol değiştirilemedi uyarısı yok"
    assert any(c[2] == "uyari" for c in calls if c[0] == "Kısayol değiştirilemedi")


def test_kisayol_basariyla_degisir():
    """Normal yolda kısayol değişir ve ayar dosyasına yazılır."""
    yazilan: list[str] = []
    uyg, pano, pencere, zincir, calls = _uygulama(
        kaydet_cb=lambda: yazilan.append(uyg.ayarlar["kisayol"]),
    )
    uyg.baslat()
    uyg.kisayol_sec("<ctrl>+<shift>+t")
    assert uyg.ayarlar["kisayol"] == "<ctrl>+<shift>+t"
    assert yazilan == ["<ctrl>+<shift>+t"]
    assert any(c[0] == "Kısayol değişti" for c in calls)


# --------------------------------------------------------------------------- #
# MADDE 6 — boş izinli listesi "hepsine izin" demek
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("izinli", [[], set(), frozenset()])
def test_bos_izinli_liste_her_uygulamaya_izin_verir(izinli):
    """izinli boş liste/küme ise 'hepsine izin' olmalı (None'a çevrilir)."""
    uyg, pano, pencere, zincir, calls = _uygulama(izinli=izinli)
    uyg._kisayol_isle()
    assert zincir.cagrilar == ["merhaba dünya"], "çeviri yapılmadı (izin yok sayıldı)"
    assert pencere.cagrilar and pencere.cagrilar[0][1] is None, \
        "izinli_mi'ye boş liste geçti, None olmalı"


def test_izinli_dolu_liste_yine_sinirli_calisir():
    """Dolu izinli listesi ile sınırlama korunmalı."""
    uyg, pano, pencere, zincir, calls = _uygulama(izinli={"chrome.exe"})
    uyg._kisayol_isle()
    assert zincir.cagrilar == [], "izin verilmeyen uygulamada çeviri yapıldı"
    assert pencere.cagrilar[0][1] == {"chrome.exe"}


def test_yasakli_uygulama_hicbir_zaman_iznli_degil():
    uyg, pano, pencere, zincir, calls = _uygulama(
        izinli=[], yasak={"notepad.exe"},
    )
    uyg._kisayol_isle()
    assert zincir.cagrilar == [], "yasaklı uygulamada çeviri yapıldı"


# --------------------------------------------------------------------------- #
# MADDE 7 — .gitignore
# --------------------------------------------------------------------------- #
def test_gitignore_guvenli_desenleri_iceriyor():
    """Log, gizli anahtar, veritabanı ve derleme çıktıları git'e girmemeli."""
    icerik = (KOK / ".gitignore").read_text(encoding="utf-8")
    satirlar = {s.strip() for s in icerik.splitlines()}
    for desen in ("*.log", ".env", ".env.*", "*.db", "*.sqlite",
                  "ayarlar.toml", "*.bozuk.toml", "dist/", "build/", "*.spec"):
        assert desen in satirlar, f".gitignore'da '{desen}' eksik"
