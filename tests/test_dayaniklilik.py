"""Dayanıklılık (arıza enjeksiyonu) testleri — INCELEME-1.

Amaç: çeviri zincirinin, pano/ayar/uygulama yaşam döngüsünün ve model
indirmenin *bozulma anlarındaki* davranışını yapay arızalarla sınamak.

Kurallar:
- Ürün kodu DEĞİŞTİRİLMEDİ. Başarısız test bir BULGUDUR; ``xfail(strict=False)``
  ile işaretlenir (raporda listelenir). Dayanıklı bulunanlar normal PASS kalır.
- Gerçek ağ, gerçek pano, gerçek klavye kancası, uygulamanın kendisi
  ÇALIŞTIRILMAZ. Her şey mock/sahte nesneyle (httpx.MockTransport, sahte
  win32clipboard, sahte pano/pencere/zincir) enjekte edilir.
- Metin içeriklerinin loglanmadığı gizlilik sözü de sınanır.
"""
from __future__ import annotations

import builtins
import hashlib
import sys
import threading
import time
from dataclasses import dataclass

import httpx
import pytest

from ceviri_katmani.cekirdek import gemini as gemini_mod
from ceviri_katmani.cekirdek import indir
from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi, CevirmenZinciri
from ceviri_katmani.cekirdek.gemini import GeminiCevirmen
from ceviri_katmani.cekirdek.korumalar import KorumaliCevirmen
from ceviri_katmani.cekirdek.kurulum import akilli_cevir
from ceviri_katmani.cekirdek.yerel import YerelCevirmen

WIN32 = sys.platform == "win32"
WINDOWS_YALNIZ = pytest.mark.skipif(not WIN32, reason="Windows'a özgü")
GERCEK_MODEL = "D:/DevCache/ceviri-modelleri/tc-big-tr-en-int8"


# --------------------------------------------------------------------------- #
# Yardımcı sahte nesneler
# --------------------------------------------------------------------------- #
@dataclass
class Pencere:
    hwnd: int
    surec: str
    sinif: str
    baslik: str


class YankiCevirmen:
    """Koruma/parçalama testleri için girdiyi aynen döndüren çevirmen."""

    ad = "yerel:Yanki"

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        return metin


class HazirCevirmen:
    """Sabit çeviri döner ya da sabit hata fırlatır (zincir testleri)."""

    def __init__(self, ad: str, metin: str | None = None, hata: Exception | None = None):
        self.ad = ad
        self._metin = metin
        self._hata = hata

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        if self._hata is not None:
            raise self._hata
        return self._metin


class FakePanoYedegi:
    def __init__(self):
        self.kaydedildi = False
        self.geri_yuklendi = False

    def kaydet(self) -> None:
        self.kaydedildi = True

    def geri_yukle(self) -> bool:
        self.geri_yuklendi = True
        return True


class KaydetHataliYedek(FakePanoYedegi):
    def kaydet(self):
        raise OSError("Pano açılamadı")


class FakePano:
    def __init__(self, secim: str | None = None, koy_raiser_once: bool = False):
        self.secim = secim
        self.koy_raiser_once = koy_raiser_once
        self.koy_cagri = 0
        self.yedek_cagri = 0
        self.kaydet_hatali_kac_kez = 0
        self.son_yedek: FakePanoYedegi | None = None
        self.koyulan: str | None = None
        self.yapistirildi = 0

    def PanoYedegi(self) -> FakePanoYedegi:
        self.yedek_cagri += 1
        if self.yedek_cagri <= self.kaydet_hatali_kac_kez:
            yedek = KaydetHataliYedek()
        else:
            yedek = FakePanoYedegi()
        self.son_yedek = yedek
        return yedek

    def secimi_kopyala(self, bekle_ms: int = 300) -> str | None:
        return self.secim

    def metin_koy(self, metin: str) -> None:
        self.koy_cagri += 1
        if self.koy_raiser_once and self.koy_cagri == 1:
            raise RuntimeError("pano bozuk")
        self.koyulan = metin

    def yapistir(self) -> None:
        self.yapistirildi += 1

    def geri_sil(self, adet: int) -> None:
        pass


class FakePencere:
    def __init__(self, aktif: Pencere | None):
        self.aktif = aktif

    def aktif_pencere(self) -> Pencere | None:
        return self.aktif

    def izinli_mi(self, p, izinli, yasak) -> bool:
        if p.surec in (yasak or set()):
            return False
        if izinli is None:
            return True
        return p.surec in izinli

    def terminal_mi(self, p, ek=None) -> bool:
        return False


class SahteDinleyici:
    def __init__(self, **kwargs):
        self.baslatildi = 0
        self.durduruldu = 0

    def baslat(self) -> None:
        self.baslatildi += 1

    def durdur(self) -> None:
        self.durduruldu += 1


def _uygulama(secim="merhaba dünya", ceviri="hello world", zincir=None,
              koy_raiser_once=False, kaydet_hatali_kac_kez=0):
    from ceviri_katmani.uygulama.ana import Uygulama

    pano = FakePano(secim=secim, koy_raiser_once=koy_raiser_once)
    pano.kaydet_hatali_kac_kez = kaydet_hatali_kac_kez
    pencere = FakePencere(Pencere(1, "notepad.exe", "Edit", "x"))
    if zincir is None:
        zincir = CevirmenZinciri([HazirCevirmen("gemini:sahte", metin=ceviri)])
    calls: list[tuple[str, str, str]] = []

    def bildir(b, m="", s="bilgi"):
        calls.append((b, m, s))

    ayarlar = {
        "kisayol": "<ctrl>+<shift>+<space>",
        "tetik": ";en",
        "izinli": None,
        "yasak": set(),
        "sona_bosluk": False,
        "ozet_kaydi": True,
        "dinleyici_sinifi": SahteDinleyici,
    }
    uyg = Uygulama(pano, pencere, zincir, bildir, ayarlar)
    return uyg, pano, zincir, calls


def _isci_kostur(uyg, *isler, bekle=4.0):
    """Verilen kuyruk işlerini işçi döngüsünde ayrı thread'de koşturur, sonra durdurur."""
    for is_ in isler:
        uyg._kuyruk.put(is_)
    uyg._kuyruk.put(None)
    uyg._calis = True
    t = threading.Thread(target=uyg._isci_dongusu, daemon=True)
    t.start()
    t.join(bekle)
    return t


@pytest.fixture
def gemini_anahtar(monkeypatch):
    monkeypatch.setattr(gemini_mod, "anahtar_oku", lambda ad: "test-anahtar")


def _gemini(handler) -> GeminiCevirmen:
    return GeminiCevirmen(istemci=httpx.Client(transport=httpx.MockTransport(handler)))


def _cevap(**candidate) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [candidate]})


def _govde(text: str) -> dict:
    return {"content": {"parts": [{"text": text}]}}


def _zincir_gemini_yedek(handler, yedek: str = "hello world") -> CevirmenZinciri:
    """Üretim zincirini taklit eder: Korumalı(Gemini) -> Korumalı(yedek yerel)."""
    return CevirmenZinciri([
        KorumaliCevirmen(_gemini(handler)),
        KorumaliCevirmen(HazirCevirmen("yerel:tc-big", metin=yedek)),
    ])


# --------------------------------------------------------------------------- #
# 1) GEMİNİ ARIZALARI → zincir yerele düşüyor mu?
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "ad, handler",
    [
        ("baglanti", lambda r: (_ for _ in ()).throw(httpx.ConnectError("nope", request=r))),
        ("zaman_asimi", lambda r: (_ for _ in ()).throw(httpx.TimeoutException("slow", request=r))),
        ("500", lambda r: httpx.Response(500, json={"error": {"message": "internal"}})),
        ("429", lambda r: httpx.Response(429, json={"error": {"message": "quota"}})),
        ("403", lambda r: httpx.Response(403, json={"error": {"message": "forbidden"}})),
        ("bos_yanit", lambda r: _cevap(content={"parts": []})),
        ("bozuk_json", lambda r: httpx.Response(200, content=b"<!doctype html>bu json degil")),
        ("candidates_bos", lambda r: httpx.Response(200, json={"candidates": []})),
        ("SAFETY", lambda r: _cevap(finishReason="SAFETY", content={"parts": []})),
    ],
)
def test_gemini_arizalari_yerele_duser(gemini_anahtar, ad, handler):
    zincir = _zincir_gemini_yedek(handler)
    assert zincir.cevir("merhaba dünya") == "hello world"
    assert zincir.son_kullanilan == "yerel:tc-big"


def test_gemini_ksa_aciklama_uzunluk_kontrolu_yakalar(gemini_anahtar):
    """Model çeviri yerine kısa bir açıklama dönerse uzunluk denetimi hataya
    çevirip zinciri yerele düşürür (sessiz bozuk çıktı olmaz)."""
    handler = lambda r: _cevap(**_govde("I cannot help."))
    yedek = "Please translate this long Turkish sentence into English for me today"
    zincir = _zincir_gemini_yedek(handler, yedek=yedek)
    girdi = "Lütfen bu uzun Türkçe cümleyi benim için İngilizceye çevirir misin lütfen"
    assert zincir.cevir(girdi) == yedek
    assert zincir.son_kullanilan == "yerel:tc-big"


@pytest.mark.xfail(strict=False, reason="BULGU: finishReason MAX_TOKENS (kesik çeviri) kontrol edilmiyor")
def test_gemini_max_tokens_yarim_ceviri_yakalanmali(gemini_anahtar):
    """finishReason=MAX_TOKENS kesinti demektir. Uzun ve olumsuzluk içermeyen bir
    metnin kesik çevirisi uzunluk denetiminden geçtiği için sessizce kullanıcıya
    döner; kesinti algılanıp yedek çevirmene düşülmeli (ya da hata verilmeli)."""
    handler = lambda r: _cevap(finishReason="MAX_TOKENS", **_govde(
        "Today the weather is very nice and I plan to take a long walk outside then"))
    tam = ("Today the weather is very nice and I plan to take a long walk outside "
           "and then I want to drink coffee")
    zincir = _zincir_gemini_yedek(handler, yedek=tam)
    girdi = ("Bugün hava çok güzel ve dışarıda uzun bir yürüyüş yapmayı planlıyorum "
             "sonra da kahve içmek istiyorum")
    assert zincir.cevir(girdi) == tam  # kesik değil, tam çeviri olmalı
    assert zincir.son_kullanilan == "yerel:tc-big"


def test_gemini_ve_yedek_ikisi_de_duserse_ceviri_hatasi():
    gen = HazirCevirmen("gemini:x", hata=CeviriHatasi("ağ hatası"))
    yer = HazirCevirmen("yerel:x", hata=CeviriHatasi("model klasörü yok"))
    zincir = CevirmenZinciri([gen, yer])
    with pytest.raises(CeviriHatasi):
        zincir.cevir("merhaba dünya")


def test_zincir_hata_mesaji_hicbir_cevirmen_calismadi_yaziyor():
    gen = HazirCevirmen("gemini:a", hata=CeviriHatasi("HTTP 500"))
    yer = HazirCevirmen("yerel:b", hata=CeviriHatasi("model yok"))
    zincir = CevirmenZinciri([gen, yer])
    with pytest.raises(CeviriHatasi, match="Hiçbir çevirmen çalışmadı"):
        zincir.cevir("merhaba dünya")


# --------------------------------------------------------------------------- #
# 2) YEREL ÇEVİRMEN ARIZALARI
# --------------------------------------------------------------------------- #
def test_yerel_klasor_yok_ceviri_hatasi(tmp_path):
    c = YerelCevirmen(str(tmp_path / "yok-klasor"))
    with pytest.raises(CeviriHatasi):
        c.cevir("merhaba dünya")


def test_yerel_bozuk_model_yukleme_hatasi(tmp_path):
    """Bozuk/garip model dosyalarıyla Translator hata verirse CeviriHatasi'na
    sarılmalı (ham RuntimeError/ValueError yukarı sızmamalı)."""
    klasor = tmp_path / "tc-big-tr-en-int8"
    klasor.mkdir()
    (klasor / "config.json").write_text("{ bu bozuk json", encoding="utf-8")
    (klasor / "source.spm").write_bytes(b"junkjunkjunkjunk")
    (klasor / "target.spm").write_bytes(b"junkjunkjunkjunk")
    c = YerelCevirmen(str(klasor))
    with pytest.raises(CeviriHatasi, match="yerel model yüklenemedi"):
        c.cevir("merhaba dünya")


def test_yerel_ctranslate2_kurulu_degil_ceviri_hatasi(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctranslate2", None)
    c = YerelCevirmen(GERCEK_MODEL)
    with pytest.raises(CeviriHatasi, match="uv sync"):
        c.cevir("merhaba dünya")


def test_yerel_sentencepiece_kurulu_degil_ceviri_hatasi(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentencepiece", None)
    c = YerelCevirmen(GERCEK_MODEL)
    with pytest.raises(CeviriHatasi, match="uv sync"):
        c.cevir("merhaba dünya")


def test_yerel_basarisiz_yukleme_geciciiz_birakmaz(tmp_path):
    """Başarısız ilk yükleme sonrası _translator None kalmalı; sonraki çağrıda
    yeniden denenir (yarım/bozuk nesne tekrar kullanılmaz). Bozuk tmp klasörle
    çalışılır, gerçek 230 MB model yüklenmez."""
    klasor = tmp_path / "tc-big-tr-en-int8"
    klasor.mkdir()
    (klasor / "config.json").write_text("{ bozuk json", encoding="utf-8")
    (klasor / "source.spm").write_bytes(b"junkjunkjunk")
    (klasor / "target.spm").write_bytes(b"junkjunkjunk")
    c = YerelCevirmen(str(klasor))
    with pytest.raises(CeviriHatasi):
        c.cevir("merhaba dünya")
    assert c._translator is None
    with pytest.raises(CeviriHatasi):
        c.cevir("ikinci deneme")  # tekrar denenir
    assert c._translator is None


# --------------------------------------------------------------------------- #
# 3) MODEL İNDİRME ARIZALARI
# --------------------------------------------------------------------------- #
def _dosya_tablosu(icerikler: dict[str, bytes]) -> dict[str, tuple[int, str]]:
    return {ad: (len(ic), hashlib.sha256(ic).hexdigest()) for ad, ic in icerikler.items()}


def _sahte_istemci(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_indirme_akis_yarida_koparsa_hedef_korunur(tmp_path, monkeypatch):
    icerikler = {"config.json": b"cfg", "model.bin": b"A" * (2 * indir.PARCA_BOYU + 100)}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "eski.txt").write_bytes(b"kritik")

    def handler(request: httpx.Request) -> httpx.Response:
        ad = request.url.path.rsplit("/", 1)[-1]
        if ad == "model.bin":
            def ugez():
                yield b"A" * indir.PARCA_BOYU
                raise httpx.ReadError("yarıda koptu", request=request)
            return httpx.Response(200, content=ugez())
        return httpx.Response(200, content=icerikler[ad])

    with pytest.raises(indir.IndirmeHatasi):
        indir.model_indir(hedef, istemci=_sahte_istemci(handler))
    assert (hedef / "eski.txt").read_bytes() == b"kritik"
    assert not (tmp_path / "model.indiriliyor").exists()


def test_indirme_sha_tutmazsa_hedef_korunur(tmp_path, monkeypatch):
    icerikler = {"config.json": b"cfg", "model.bin": b"veri"}
    dosyalar = _dosya_tablosu(icerikler)
    boyut, _ = dosyalar["model.bin"]
    dosyalar["model.bin"] = (boyut, "0" * 64)  # yanlış sha
    monkeypatch.setattr(indir, "DOSYALAR", dosyalar)

    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "kor.txt").write_bytes(b"deger")

    def handler(request: httpx.Request) -> httpx.Response:
        ad = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=icerikler[ad])

    with pytest.raises(indir.IndirmeHatasi, match="doğrulanamadı"):
        indir.model_indir(hedef, istemci=_sahte_istemci(handler))
    assert (hedef / "kor.txt").read_bytes() == b"deger"
    assert not (hedef / "model.bin").exists()
    assert not (tmp_path / "model.indiriliyor").exists()


@pytest.mark.xfail(strict=False, reason="BULGU ÖNEMLİ: disk dolu (OSError) IndirmeHatasi'na sarılmıyor, ham sızıyor")
def test_indirme_disk_dolu_indirme_hatasi_olmali(tmp_path, monkeypatch):
    """Disk dolu (OSError) → ham OSError değil IndirmeHatasi beklenir; CLI yalnız
    IndirmeHatasi yakaladığı için aksi hâlde kullanıcıya traceback gösterilir."""
    icerikler = {"model.bin": b"veri"}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"veri")

    def sahte_open(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(builtins, "open", sahte_open)
    with pytest.raises(indir.IndirmeHatasi):
        indir.model_indir(tmp_path / "model", istemci=_sahte_istemci(handler))


@pytest.mark.xfail(strict=False, reason="BULGU ÖNEMLİ: hedef kilitli (PermissionError) IndirmeHatasi'na sarılmıyor")
def test_indirme_hedef_kilitli_indirme_hatasi_olmali(tmp_path, monkeypatch):
    """Hedef klasör kilitli (os.replace PermissionError) → IndirmeHatasi beklenir."""
    icerikler = {"model.bin": b"veri"}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"veri")

    def sahte_replace(src, dst, *a, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(indir.os, "replace", sahte_replace)
    with pytest.raises(indir.IndirmeHatasi):
        indir.model_indir(tmp_path / "model", istemci=_sahte_istemci(handler))


def test_indirme_hata_sonrasi_gecici_klasor_temizlenir(tmp_path, monkeypatch):
    """Swap başarısız olursa .indiriliyor geçici klasörü temiz kalmalı (dayanıklı)."""
    icerikler = {"model.bin": b"veri"}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"veri")

    def sahte_replace(src, dst, *a, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(indir.os, "replace", sahte_replace)
    with pytest.raises(BaseException):
        indir.model_indir(tmp_path / "model", istemci=_sahte_istemci(handler))
    assert not (tmp_path / "model.indiriliyor").exists()


@pytest.mark.xfail(strict=False, reason="BULGU KRİTİK: os.replace başarısız olursa önceki geçerli model rmtree ile silinmiş oluyor")
def test_indirme_kilitli_swap_onceden_kurulu_modeli_kaybetmez(tmp_path, monkeypatch):
    """Zaten indirilmiş geçerli model üzerine yeniden indirme sırasında swap
    başarısız olursa (hedef kilitli), mevcut kurulum YOK OLMAMALI. Şu an kod
    swap'tan ÖNCE hedefi rmtree ile siliyor -> kullanıcı internetsiz çeviriyi kaybeder."""
    icerikler = {"model.bin": b"veri"}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"veri")

    def sahte_replace(src, dst, *a, **k):
        raise PermissionError(13, "Access denied")

    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "model.bin").write_bytes(b"onceki-gecerli-model")
    monkeypatch.setattr(indir.os, "replace", sahte_replace)
    with pytest.raises(BaseException):
        indir.model_indir(hedef, istemci=_sahte_istemci(handler))
    assert (hedef / "model.bin").read_bytes() == b"onceki-gecerli-model"


def test_indirme_yarida_kalirsa_bir_sonraki_acilista_yeniden_dener(tmp_path, monkeypatch):
    """Yarım kalan indirme sonrası model_tam_mi False olmalı ve arka plan
    indirici yeniden iş başlatmalı."""
    icerikler = {"model.bin": b"A" * 2_000_000}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))
    hedef = tmp_path / "model"

    def kopan(request):
        def ugez():
            yield b"A" * 1000
            raise httpx.ReadError("koptu", request=request)
        return httpx.Response(200, content=ugez())

    with pytest.raises(indir.IndirmeHatasi):
        indir.model_indir(hedef, istemci=_sahte_istemci(kopan))

    assert indir.model_tam_mi(hedef) is False  # yarım model "tam" sanılmaz

    monkeypatch.delenv("CEVIRI_YEREL_MODEL", raising=False)
    from ceviri_katmani.uygulama import model_indirme

    cagrildi = {"v": False}

    def indirici(kls, **kw):
        cagrildi["v"] = True

    t = model_indirme.gerekirse_arkaplanda_indir(
        lambda *a, **k: None, klasor=hedef, indirici=indirici, thread_baslat=True
    )
    assert t is not None
    t.join(2.0)
    assert cagrildi["v"] is True


# --------------------------------------------------------------------------- #
# 4) PANO ARIZALARI (gerçek pano kullanılmaz; win32clipboard sahtelenir)
# --------------------------------------------------------------------------- #
class _YapayModul:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@WINDOWS_YALNIZ
def test_pano_ac_kesisik_olmazsa_oserror(monkeypatch):
    from ceviri_katmani.uygulama import pano

    def ac(*a):
        raise RuntimeError("locked")

    monkeypatch.setattr(pano, "win32clipboard", _YapayModul(OpenClipboard=ac))
    monkeypatch.setattr(pano.time, "sleep", lambda s: None)
    with pytest.raises(OSError):
        pano._pano_ac()


@WINDOWS_YALNIZ
def test_pano_yedek_kaydet_acilamazsa_oserror(monkeypatch):
    """Pano açılamazsa kaydet() OSError fırlatır (birim düzeyinde beklenen)."""
    from ceviri_katmani.uygulama import pano

    def ac(*a):
        raise RuntimeError("locked")

    monkeypatch.setattr(pano, "win32clipboard", _YapayModul(OpenClipboard=ac))
    monkeypatch.setattr(pano.time, "sleep", lambda s: None)
    yedek = pano.PanoYedegi()
    with pytest.raises(OSError):
        yedek.kaydet()


@pytest.mark.xfail(strict=False, reason="BULGU KRİTİK: işçi döngüsü istisnayı yutmuyor, thread ölüyor")
def test_pano_kaydet_acilamazsa_isci_yasamali():
    """OpenClipboard sürekli başarısız → ilk işin yedek.kaydet() patlar.
    İşçi döngüsü istisnayı yutmalı ki İKİNCİ kısayol (pano düzeldi) çalışsın."""
    uyg, pano_, zincir, calls = _uygulama(secim="merhaba dünya", kaydet_hatali_kac_kez=1)
    _isci_kostur(uyg, ("kisayol", None), ("kisayol", None))
    # 1. iş: pano hatası, 2. iş: başarılı → "Çevrildi (Gemini)" beklenir
    assert any(c[0] == "Çevrildi (Gemini)" for c in calls), \
        "pano hatası sonrası işçi öldü; sonraki kısayol çalışmadı"
    assert pano_.koyulan == "hello world"


def test_ctrl_c_pano_degismezse_secim_yok():
    uyg, pano_, zincir, calls = _uygulama(secim=None)
    uyg._kisayol_isle()
    assert any(c[0] == "Seçim yok" for c in calls)
    assert pano_.koyulan is None


@WINDOWS_YALNIZ
def test_yalniz_resim_panoda_metin_none(monkeypatch):
    """Panoda yalnızca resim var (CF_UNICODETEXT yok) → metin_al None."""
    from ceviri_katmani.uygulama import pano

    def OpenClipboard(*a):
        return None

    def EnumClipboardFormats(f):
        return 0

    def IsFormatAvailable(f):
        return False

    monkeypatch.setattr(
        pano,
        "win32clipboard",
        _YapayModul(
            OpenClipboard=OpenClipboard,
            CloseClipboard=lambda *a: None,
            EnumClipboardFormats=EnumClipboardFormats,
            IsClipboardFormatAvailable=IsFormatAvailable,
            GetClipboardData=lambda *a: None,
        ),
    )
    assert pano.metin_al() is None


@pytest.mark.xfail(strict=False, reason="BULGU KRİTİK: metin_koy istisnası işçiyi öldürüyor, sonraki kısayol çalışmıyor")
def test_metin_koy_istisnasi_sonrasi_isci_calismali():
    """Çeviri başarılıyken metin_koy (ilk) patlar; işçi istisnayı yutup İKİNCİ
    kısayol işlemeye devam etmeli. Şu an işçi ölüyor (bulgu)."""
    uyg, pano_, zincir, calls = _uygulama(secim="merhaba dünya", koy_raiser_once=True)
    _isci_kostur(uyg, ("kisayol", None), ("kisayol", None))
    assert pano_.koyulan == "hello world", "istisna sonrası işçi öldü, 2. kısayol çalışmadı"
    assert uyg._kuyruk.empty(), "kuyrukta işler birikti (işçi döngüden çıktı)"


# --------------------------------------------------------------------------- #
# 5) AYAR DOSYASI ARIZALARI
# --------------------------------------------------------------------------- #
def test_ayar_bozuk_toml_yedeklenir(tmp_path):
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN, yukle

    yol = tmp_path / "ayarlar.toml"
    yol.write_text("= bozuk [", encoding="utf-8")
    ayarlar, uyarilar = yukle(yol)
    assert ayarlar == VARSAYILAN
    assert (tmp_path / "ayarlar.bozuk.toml").exists()
    assert any("bozuk" in u for u in uyarilar)


def test_ayar_yanlis_tipler_dogrulanir():
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN, dogrula

    ayarlar, uyarilar = dogrula({"kisayol": 123, "izinli": "x", "zaman_asimi": -5})
    assert ayarlar["kisayol"] == VARSAYILAN["kisayol"]
    assert ayarlar["izinli"] == VARSAYILAN["izinli"]
    assert ayarlar["zaman_asimi"] == VARSAYILAN["zaman_asimi"]
    assert len(uyarilar) >= 3


def test_ayar_eksik_klasor_yukle_olusturur(tmp_path):
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN, yukle

    yol = tmp_path / "derin" / "alt" / "ayarlar.toml"
    assert not yol.parent.exists()
    ayarlar, uyarilar = yukle(yol)
    assert yol.exists()
    assert ayarlar == VARSAYILAN


@pytest.mark.xfail(strict=False, reason="BULGU ÖNEMLİ: salt okunur/kilitli hedefte kaydet() PermissionError'ü yutmuyor")
def test_ayar_salt_okunur_klasore_kaydet_cokmemeli(tmp_path, monkeypatch):
    """Kilitli/salt okunur hedefe os.replace başarısız olursa kaydet() hatayı
    yutmalı ya da en azından çağıranı çökertmemeli. Şu an PermissionError sızıyor."""
    from ceviri_katmani.uygulama import ayarlar as a

    def sahte_replace(src, dst, *args, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(a.os, "replace", sahte_replace)
    yol = tmp_path / "ayarlar.toml"
    try:
        a.kaydet({"kisayol": "<ctrl>+<shift>+<space>"}, yol)
        cokmedi = True
    except PermissionError:
        cokmedi = False
    assert cokmedi, "salt okunur hedefte kaydet() çağıranı çökertiyor"


@pytest.mark.xfail(strict=False, reason="BULGU ÖNEMLİ: yazılamaz bozuk ayar dosyasında yukle() çöküyor, varsayılana düşmüyor")
def test_ayar_salt_okunur_bozuk_dosya_uyarili_kurtarilsin(tmp_path, monkeypatch):
    """Bozuk + yazılamaz ayar dosyası: yedekleme başarısız olsa da varsayılanlarla
    dönülmeli; şu an os.replace hatası yayılıyor (başlangıç çökmesi riski)."""
    from ceviri_katmani.uygulama import ayarlar as a
    from ceviri_katmani.uygulama.ayarlar import VARSAYILAN

    yol = tmp_path / "ayarlar.toml"
    yol.write_text("= bozuk [", encoding="utf-8")

    def sahte_replace(src, dst, *args, **k):
        raise PermissionError(13, "Access denied")

    monkeypatch.setattr(a.os, "replace", sahte_replace)
    try:
        ayarlar, uyarilar = a.yukle(yol)
        assert ayarlar == VARSAYILAN
    except PermissionError:
        pytest.fail("yazılamaz bozuk dosyada yukle() çöküyor; varsayılanlara düşmeli")


# --------------------------------------------------------------------------- #
# 6) UYGULAMA YAŞAM DÖNGÜSÜ
# --------------------------------------------------------------------------- #
def test_mesgul_bayragi_istisnadan_sonra_takilmasın():
    uyg, pano_, zincir, calls = _uygulama(secim="merhaba dünya", koy_raiser_once=True)
    _isci_kostur(uyg, ("kisayol", None))
    assert uyg._meşgul is False  # finally bayrağı sıfırlamalı


def test_durdur_iki_kez_guvenli():
    uyg, pano_, zincir, calls = _uygulama()
    uyg.baslat()
    uyg.durdur()
    uyg.durdur()  # ikinci çağrı hata vermemeli
    assert uyg._calis is False


def test_durdur_isci_mesgulken_tumlanmaz():
    uyg, pano_, zincir, calls = _uygulama(secim="merhaba dünya")

    class YavasCevirmen:
        ad = "gemini:yavas"

        def cevir(self, metin, kaynak="tr", hedef="en"):
            time.sleep(0.2)
            return "hello"

    uyg.zincir = CevirmenZinciri([YavasCevirmen()])
    uyg.baslat()
    uyg.kisayol()
    time.sleep(0.05)
    bas = time.perf_counter()
    uyg.durdur()
    assert time.perf_counter() - bas < 2.5  # join(timeout=2) ile en fazla ~2s bekler


@pytest.mark.xfail(strict=False, reason="BULGU ÖNEMLİ: kurulamayan kısayolda kisayol_sec istisna yayıyor (menü çöker)")
def test_kisayol_degisiminde_dinleyici_kurulamassa_patlamamali():
    """Yeni kısayolla dinleyici kurulamazsa: kisayol_sec hata yutmalı, kullanıcıyı
    uyarmalı ve bozuk kısayola geçmemeli. Şu an istisna yayılıyor."""
    uyg, pano_, zincir, calls = _uygulama()
    uyg.baslat()

    def kurus():
        raise RuntimeError("pynput hotkey kaydedilemedi")

    uyg._dinleyici_kur = kurus
    try:
        uyg.kisayol_sec("<ctrl>+<alt>+<shift>+q")
        cokmedi = True
    except Exception:
        cokmedi = False
    assert cokmedi, "kisayol_sec kurulamayan kısayolda patlıyor (menü çöker)"


# --------------------------------------------------------------------------- #
# 7) SINIR GİRDİLERİ (zincirin uç durumları)
# --------------------------------------------------------------------------- #
def test_sinir_bos_metin_bos_durum():
    zincir = CevirmenZinciri([HazirCevirmen("gemini:x", metin="x")])
    assert akilli_cevir(zincir, "").durum == "bos"
    assert akilli_cevir(zincir, "   \n\t ").durum == "bos"


def test_sinir_20000_karakter_cokmez():
    metin = ("Merhaba dünya nasılsın bugün. " * 700)[:20000]
    zincir = CevirmenZinciri([YankiCevirmen()])
    bas = time.perf_counter()
    sonuc = akilli_cevir(zincir, metin)
    sure = time.perf_counter() - bas
    assert sonuc.durum == "cevrildi"
    assert len(sonuc.metin) == len(metin)
    assert sure < 15.0, f"20k metin {sure:.1f}s sürdü (performans)"


def test_sinir_20000_korumali_regex_yavaslamasin():
    metin = ("Merhaba dünya nasılsın bugün. " * 700)[:20000]
    korumali = KorumaliCevirmen(YankiCevirmen())
    bas = time.perf_counter()
    sonuc = korumali.cevir(metin)
    sure = time.perf_counter() - bas
    assert sonuc == metin
    assert sure < 15.0, f"korumalı 20k regex {sure:.1f}s (performans bulgusu)"


def test_sinir_yalniz_emoji_zaten_ingilizce():
    zincir = CevirmenZinciri([YankiCevirmen()])
    sonuc = akilli_cevir(zincir, "😀😁🎉")
    assert sonuc.durum == "zaten-ingilizce"
    assert sonuc.metin == "😀😁🎉"


def test_sinir_yalniz_kod_bloğu_korunur():
    blok = "```python\nprint('merhaba dünya')\n```"
    zincir = CevirmenZinciri([KorumaliCevirmen(YankiCevirmen())])
    sonuc = akilli_cevir(zincir, blok)
    # Kod bloğu maskeleme ile bozulmadan geri gelmeli; çökme/bozulma olmamalı.
    assert sonuc.metin == blok
    assert sonuc.durum in {"cevrildi", "zaten-ingilizce"}


def test_sinir_windows_satir_sonu_satir_sayisini_korur():
    metin = "Birinci satır\r\nİkinci satır\r\nÜçüncü satır"
    zincir = CevirmenZinciri([YankiCevirmen()])
    sonuc = akilli_cevir(zincir, metin)
    assert len(sonuc.metin.splitlines()) == len(metin.splitlines())


def test_sinir_karisik_tr_en_cevrilir():
    zincir = CevirmenZinciri([YankiCevirmen()])
    sonuc = akilli_cevir(zincir, "Hello bugün nasılsın, teşekkürler")
    assert sonuc.durum == "cevrildi"


def test_sinir_maskeleme_yer_tutucu_geri_koyulur():
    metin = "git commit at `npm run build` sonra https://ornek.com adresine bak"
    korumali = KorumaliCevirmen(YankiCevirmen())
    sonuc = korumali.cevir(metin)
    assert sonuc == metin
    assert "ZXQ" not in sonuc


# --------------------------------------------------------------------------- #
# 8) GİZLİLİK: metin içeriği hiçbir yere loglanmamalı
# --------------------------------------------------------------------------- #
def test_gecmis_ozet_metin_icermegi_tutmaz():
    gizli = "şifrem şu: SuperGizli123 merhaba dünya"
    uyg, pano_, zincir, calls = _uygulama(secim=gizli)
    uyg._kisayol_isle()
    for islem in uyg.gecmis.liste():
        assert "SuperGizli123" not in islem.satir()
        assert gizli not in islem.satir()


def test_gemini_ceviri_hatasi_anahtar_icermemeli(gemini_anahtar):
    handler = lambda r: httpx.Response(401, json={"error": {"message": "bad"}})
    with pytest.raises(CeviriHatasi) as bilgi:
        _gemini(handler).cevir("merhaba dünya")
    assert "test-anahtar" not in str(bilgi.value)


def test_hata_mesajlari_metin_icermigi_tasimaz():
    with pytest.raises(CeviriHatasi) as bilgi:
        CevirmenZinciri([HazirCevirmen("g", hata=CeviriHatasi("HTTP 429"))]).cevir("sır metni")
    assert "sır metni" not in str(bilgi.value)
