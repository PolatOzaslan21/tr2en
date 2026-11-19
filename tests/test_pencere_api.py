"""PencereApi (ayar penceresi köprüsü) testleri.

Ağ, gerçek kasa, gerçek APPDATA yoktur: her bağımlılık sahtedir/enjekte edilir.
Ayarlar tmp_path'te tutulur; anahtar değerlerinin hiçbir dönüşe sızmadığı
json.dumps ile doğrulanır.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ceviri_katmani import __version__
from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.uygulama import ayarlar as ayar_modulu
from ceviri_katmani.uygulama.ayarlar import VARSAYILAN
from ceviri_katmani.uygulama.pencere_api import BEYAZ_LISTE, DENEME_METNI, PencereApi


# ---- sahteler ----


class SahteKasa:
    """Sözlük tabanlı kasa; ortam değişkenleri de sahte sözlükten okunur."""

    def __init__(self, ortam: dict | None = None) -> None:
        self.veri: dict[str, str] = {}
        self.ortam: dict[str, str] = dict(ortam or {})

    def oku(self, servis: str) -> str | None:
        return self.veri.get(servis)

    def yaz(self, servis: str, deger: str) -> bool:
        if not isinstance(deger, str) or not deger.strip():
            return False
        self.veri[servis] = deger.strip()
        return True

    def sil(self, servis: str) -> bool:
        return self.veri.pop(servis, None) is not None

    def var_mi(self, servis: str) -> bool:
        return servis in self.veri

    def anahtar_bul(self, servis: str, ortam_degiskeni: str = "") -> str | None:
        deger = self.veri.get(servis)
        if deger:
            return deger
        if ortam_degiskeni:
            return self.ortam.get(ortam_degiskeni)
        return None


class SahteZincir:
    def __init__(self, ceviri: str = "Hello world", hata: str | None = None) -> None:
        self.ceviri = ceviri
        self.hata = hata
        self.ad = "sahte:1"
        self.son_kullanilan: str | None = None
        self.cagrilar: list[str] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append(metin)
        if self.hata is not None:
            raise CeviriHatasi(self.hata)
        self.son_kullanilan = self.ad
        return self.ceviri


class SahteZincirKurucu:
    """zincir_kurucu yerine geçer; kurulan ayarı ve çekilen anahtarı kaydeder."""

    def __init__(self, zincir: SahteZincir | None = None, hata: str | None = None) -> None:
        self.zincir = zincir or SahteZincir()
        self.hata = hata
        self.kurulan_ayarlar: list[dict] = []
        self.saglayicilar: list = []
        self.anahtarlar: list[str | None] = []

    def __call__(self, ayar: dict, anahtar_saglayici, korumasiz: bool = False):
        self.kurulan_ayarlar.append(dict(ayar))
        self.saglayicilar.append(anahtar_saglayici)
        self.anahtarlar.append(anahtar_saglayici("gemini"))
        if self.hata is not None:
            raise CeviriHatasi(self.hata)
        return self.zincir


class SahteSaat:
    def __init__(self, baslangic: float = 10.0, artis: float = 0.5) -> None:
        self.deger = baslangic
        self.artis = artis

    def __call__(self) -> float:
        suanki = self.deger
        self.deger += self.artis
        return suanki


class SahteBoru:
    """Boru istemcisi sahtesi: istekleri kaydeder, hazır cevap döner."""

    def __init__(self, cevap: dict | None = None, hata: str | None = None) -> None:
        self.cevap = cevap if cevap is not None else {
            "ok": True,
            "ceviri": "Hello world",
            "cevirmen": "Bulut — Google Gemini",
            "durum": "cevrildi",
            "sure_sn": 0.5,
        }
        self.hata = hata
        self.cagrilar: list[dict] = []

    def __call__(self, istek: dict) -> dict:
        self.cagrilar.append(istek)
        if self.hata is not None:
            return {"ok": False, "hata": self.hata}
        return dict(self.cevap)


@pytest.fixture
def yol(tmp_path: Path) -> Path:
    return tmp_path / "ayarlar.toml"


@pytest.fixture
def kasa() -> SahteKasa:
    return SahteKasa()


# ---- ayarlari_al ----


def test_ayarlari_al_basarili(yol, kasa):
    kasa.veri["gemini"] = "GIZLI_GEMINI"
    kasa.ortam["OPENAI_API_KEY"] = "GIZLI_OPENAI"
    api = PencereApi(ayar_yolu=yol, kasa=kasa)
    sonuc = api.ayarlari_al()
    assert sonuc["ok"] is True
    assert sonuc["surum"] == __version__
    assert sonuc["ayarlar"]["cevirmen"] == VARSAYILAN["cevirmen"]
    assert "izinli" in sonuc["ayarlar"] and "ek_terminaller" in sonuc["ayarlar"]
    assert sonuc["anahtarlar"]["gemini"] is True
    assert sonuc["anahtarlar"]["openai"] is True
    assert sonuc["anahtarlar"]["deepseek"] is False
    assert sonuc["anahtarlar"]["openrouter"] is False
    assert sonuc["anahtarlar"]["diger"] is False
    doku = json.dumps(sonuc, ensure_ascii=False)
    assert "GIZLI_GEMINI" not in doku
    assert "GIZLI_OPENAI" not in doku


def test_ayarlari_al_diger_ortam_degiskeni(yol, kasa):
    ayar_modulu.kaydet({"uyumlu_anahtar_degiskeni": "OZEL_KEY"}, yol)
    kasa.ortam["OZEL_KEY"] = "GIZLI_OZEL"
    api = PencereApi(ayar_yolu=yol, kasa=kasa)
    sonuc = api.ayarlari_al()
    assert sonuc["ok"] is True
    assert sonuc["anahtarlar"]["diger"] is True
    assert "GIZLI_OZEL" not in json.dumps(sonuc, ensure_ascii=False)


def test_ayarlari_al_istisna_firlatmaz(yol):
    class BozukKasa:
        def anahtar_bul(self, *a, **k):
            raise RuntimeError("kasa patladı")

    api = PencereApi(ayar_yolu=yol, kasa=BozukKasa())
    sonuc = api.ayarlari_al()
    assert sonuc["ok"] is False
    assert isinstance(sonuc["hata"], str) and sonuc["hata"]


# ---- ayar_kaydet ----


def test_ayar_kaydet_basarili(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    sonuc = api.ayar_kaydet({"tema": "koyu", "kapatinca_sor": False})
    assert sonuc["ok"] is True
    assert sinyaller == ["yenile"]
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["tema"] == "koyu"
    assert yuklenen["kapatinca_sor"] is False


def test_ayar_kaydet_bilinmeyen_anahtar_yok_sayilir(yol):
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.ayar_kaydet({"olmayan_ayar": 1, "tema": "acik"})
    assert sonuc["ok"] is True
    assert any("olmayan_ayar" in u for u in sonuc["uyarilar"])
    assert "olmayan_ayar" not in yol.read_text(encoding="utf-8")
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["tema"] == "acik"


def test_ayar_kaydet_gecersiz_deger_duzeltilir(yol):
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.ayar_kaydet({"tema": "mavi"})
    assert sonuc["ok"] is True
    assert any("tema" in u for u in sonuc["uyarilar"])
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["tema"] == VARSAYILAN["tema"]


def test_ayar_kaydet_yazma_hatasi(yol, monkeypatch):
    monkeypatch.setattr(ayar_modulu, "kaydet", lambda *a, **k: False)
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.ayar_kaydet({"tema": "koyu"})
    assert sonuc["ok"] is False
    assert isinstance(sonuc["hata"], str) and sonuc["hata"]


def test_ayar_kaydet_sozluk_disi_reddedilir(yol):
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.ayar_kaydet(["tema", "koyu"])
    assert sonuc["ok"] is False
    assert isinstance(sonuc["hata"], str) and sonuc["hata"]


# ---- ilk_kurulum_tamamla ----


def test_ilk_kurulum_tamamla_bulut(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    sonuc = api.ilk_kurulum_tamamla("bulut")
    assert sonuc == {"ok": True}
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["gizlilik_onayi"] is True
    assert yuklenen["cevirmen"] == "bulut"
    assert sinyaller == ["yenile"]


def test_ilk_kurulum_tamamla_yerel(yol):
    api = PencereApi(ayar_yolu=yol)
    assert api.ilk_kurulum_tamamla("yerel") == {"ok": True}
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["cevirmen"] == "yerel"
    assert yuklenen["gizlilik_onayi"] is True


def test_ilk_kurulum_tamamla_gizlilik_onayi_dosyaya_yazilir(yol):
    api = PencereApi(ayar_yolu=yol)
    api.ilk_kurulum_tamamla("bulut")
    icerik = yol.read_text(encoding="utf-8")
    assert "gizlilik_onayi = true" in icerik


def test_ilk_kurulum_tamamla_gecersiz_cevirmen(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    for gecersiz in ("", "gemini", "BULUT", "yerel ", None, 3):
        sonuc = api.ilk_kurulum_tamamla(gecersiz)
        assert sonuc["ok"] is False
        assert isinstance(sonuc.get("hata"), str) and sonuc["hata"]
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["gizlilik_onayi"] is False
    assert sinyaller == []


def test_ilk_kurulum_tamamla_yazma_hatasi(yol, monkeypatch):
    monkeypatch.setattr(ayar_modulu, "kaydet", lambda *a, **k: False)
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.ilk_kurulum_tamamla("bulut")
    assert sonuc["ok"] is False
    assert isinstance(sonuc.get("hata"), str) and sonuc["hata"]


# ---- anahtar_kaydet / anahtar_sil ----


def test_anahtar_kaydet_ve_sil(yol, kasa):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, kasa=kasa, sinyal_gonder=sinyaller.append)
    sonuc = api.anahtar_kaydet("gemini", "  GIZLI_DEGER  ")
    assert sonuc == {"ok": True}
    assert kasa.veri["gemini"] == "GIZLI_DEGER"
    assert "GIZLI_DEGER" not in json.dumps(sonuc)
    assert sinyaller == ["yenile"]
    assert api.anahtar_sil("gemini") == {"ok": True}
    assert "gemini" not in kasa.veri
    assert sinyaller == ["yenile", "yenile"]


def test_anahtar_kaydet_bilinmeyen_servis(yol, kasa):
    api = PencereApi(ayar_yolu=yol, kasa=kasa)
    sonuc = api.anahtar_kaydet("amazon", "GIZLI_X")
    assert sonuc["ok"] is False
    assert "GIZLI_X" not in json.dumps(sonuc)


def test_anahtar_kaydet_bos_deger(yol, kasa):
    api = PencereApi(ayar_yolu=yol, kasa=kasa)
    assert api.anahtar_kaydet("gemini", "   ")["ok"] is False


def test_anahtar_sil_olmayan(yol, kasa):
    api = PencereApi(ayar_yolu=yol, kasa=kasa)
    assert api.anahtar_sil("openai")["ok"] is False
    assert api.anahtar_sil("bilinmeyen")["ok"] is False


# ---- baglanti_dene ----


def test_baglanti_dene_basarili(yol, kasa):
    kurucu = SahteZincirKurucu(SahteZincir(ceviri="Hello world, this is a test."))
    api = PencereApi(ayar_yolu=yol, kasa=kasa, zincir_kurucu=kurucu, saat=SahteSaat())
    sonuc = api.baglanti_dene({"bulut_model": "deneme-modeli"}, anahtar="GIZLI_YAZILMAMIS")
    assert sonuc["ok"] is True
    assert sonuc["ceviri"] == "Hello world, this is a test."
    assert sonuc["sure_sn"] == 0.5
    assert sonuc["hata"] == ""
    assert kurucu.zincir.cagrilar == [DENEME_METNI]
    assert kurucu.kurulan_ayarlar[0]["bulut_model"] == "deneme-modeli"
    assert kurucu.anahtarlar == ["GIZLI_YAZILMAMIS"]


def test_baglanti_dene_yedek_kapali_zorlanir(yol):
    ayar_modulu.kaydet({"bulut_yedek_yerel": True}, yol)
    kurucu = SahteZincirKurucu()
    api = PencereApi(ayar_yolu=yol, zincir_kurucu=kurucu)
    api.baglanti_dene({"bulut_model": "m"})
    assert kurucu.kurulan_ayarlar[0]["bulut_yedek_yerel"] is False
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["bulut_yedek_yerel"] is True


def test_baglanti_dene_dosyaya_yazmaz(yol):
    ayar_modulu.kaydet({"tema": "koyu"}, yol)
    once = yol.read_bytes()
    api = PencereApi(ayar_yolu=yol, zincir_kurucu=SahteZincirKurucu())
    api.baglanti_dene({"bulut_model": "m"})
    assert yol.read_bytes() == once
    assert not list(yol.parent.glob("*.tmp"))


def test_baglanti_dene_hata(yol):
    kurucu = SahteZincirKurucu(hata="model adı girilmedi")
    api = PencereApi(ayar_yolu=yol, zincir_kurucu=kurucu)
    sonuc = api.baglanti_dene({})
    assert sonuc["ok"] is False
    assert sonuc["ceviri"] == ""
    assert sonuc["hata"] == "model adı girilmedi"


def test_baglanti_dene_yazilmamis_anahtar_sizmaz(yol, kasa):
    gizli = "GIZLI_YAZILMAMIS_456"
    kurucu = SahteZincirKurucu(SahteZincir(hata=f"anahtar reddedildi: {gizli}"))
    api = PencereApi(ayar_yolu=yol, kasa=kasa, zincir_kurucu=kurucu)
    sonuc = api.baglanti_dene({}, anahtar=gizli)
    assert sonuc["ok"] is False
    assert "istek" not in sonuc["hata"] or gizli not in sonuc["hata"]
    assert gizli not in json.dumps(sonuc, ensure_ascii=False)


def test_baglanti_dene_kasa_anahtari_sizmaz(yol, kasa):
    gizli = "GIZLI_KASA_123"
    kasa.veri["gemini"] = gizli

    def kurucu(ayar, saglayici, korumasiz=False):
        raise CeviriHatasi(f"istek reddedildi: {saglayici('gemini')}")

    api = PencereApi(ayar_yolu=yol, kasa=kasa, zincir_kurucu=kurucu)
    sonuc = api.baglanti_dene({})
    assert sonuc["ok"] is False
    assert "istek reddedildi" in sonuc["hata"]
    assert gizli not in json.dumps(sonuc, ensure_ascii=False)


def test_baglanti_dene_kasa_anahtarini_kullanir(yol, kasa):
    kasa.veri["gemini"] = "KASA_DEGER"
    kasa.ortam["DEEPSEEK_API_KEY"] = "ORTAM_DEGER"
    kurucu = SahteZincirKurucu()
    api = PencereApi(ayar_yolu=yol, kasa=kasa, zincir_kurucu=kurucu)
    api.baglanti_dene({})
    assert kurucu.anahtarlar == ["KASA_DEGER"]


# ---- cevir / cevir_dene (boru üzerinden) ----


def test_cevir_boruya_gider(yol):
    boru = SahteBoru()
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    sonuc = api.cevir("Merhaba dünya")
    assert sonuc["ok"] is True
    assert sonuc["ceviri"] == "Hello world"
    assert sonuc["cevirmen"] == "Bulut — Google Gemini"
    assert sonuc["sure_sn"] == 0.5
    assert sonuc["hata"] == ""
    assert boru.cagrilar == [{"tur": "cevir", "metin": "Merhaba dünya"}]


def test_cevir_pencere_model_yuklemez(yol):
    """Çeviri pencere sürecinde değil, ana süreçte yapılır."""
    kurucu = SahteZincirKurucu()
    boru = SahteBoru()
    api = PencereApi(ayar_yolu=yol, kasa=SahteKasa(), zincir_kurucu=kurucu, boru_istemcisi=boru)
    api.cevir("Merhaba dünya")
    assert kurucu.kurulan_ayarlar == []
    assert kurucu.zincir.cagrilar == []


def test_cevir_bos(yol):
    boru = SahteBoru()
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    for metin in ("", "   ", None, 5):
        sonuc = api.cevir(metin)
        assert sonuc["ok"] is False
        assert sonuc["hata"] == "metin boş"
    assert boru.cagrilar == []


def test_cevir_hata(yol):
    boru = SahteBoru(hata="başka bir çeviri sürüyor")
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    sonuc = api.cevir("Merhaba dünya")
    assert sonuc["ok"] is False
    assert sonuc["ceviri"] == ""
    assert sonuc["hata"] == "başka bir çeviri sürüyor"


def test_cevir_boru_yoksa(yol):
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=lambda istek: {"ok": False, "hata": "tr2en çalışmıyor"})
    sonuc = api.cevir("Merhaba dünya")
    assert sonuc["ok"] is False
    assert sonuc["hata"] == "tr2en çalışmıyor"


def test_cevir_dene_ceviri_caagirir(yol):
    boru = SahteBoru()
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    sonuc = api.cevir_dene("Merhaba dünya")
    assert sonuc["ok"] is True
    assert sonuc["ceviri"] == "Hello world"
    assert boru.cagrilar == [{"tur": "cevir", "metin": "Merhaba dünya"}]


def test_cevir_dene_bos(yol):
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=SahteBoru())
    sonuc = api.cevir_dene("   ")
    assert sonuc["ok"] is False
    assert isinstance(sonuc["hata"], str) and sonuc["hata"]


def test_cevir_dene_hata(yol):
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=SahteBoru(hata="API anahtarı tanımlı değil"))
    sonuc = api.cevir_dene("Merhaba dünya")
    assert sonuc["ok"] is False
    assert sonuc["hata"] == "API anahtarı tanımlı değil"


def test_cevir_metni_kisitlamaz(yol):
    """Sınır ana süreçte (5000 karakter); pencere metni olduğu gibi gönderir."""
    boru = SahteBoru()
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    api.cevir("merhaba " * 400)
    assert len(boru.cagrilar[0]["metin"]) == 3200


# ---- durum / aktif_degistir ----


def test_durum_boruya_gider(yol):
    boru = SahteBoru(cevap={
        "ok": True, "aktif": True, "cevirmen": "bulut",
        "cevirmen_adi": "Bulut — Google Gemini", "kisayol_adi": "Ctrl+Shift+Space",
        "surum": "0.2.0",
    })
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    sonuc = api.durum()
    assert sonuc["ok"] is True
    assert sonuc["aktif"] is True
    assert sonuc["cevirmen"] == "bulut"
    assert sonuc["cevirmen_adi"] == "Bulut — Google Gemini"
    assert sonuc["kisayol_adi"] == "Ctrl+Shift+Space"
    assert sonuc["surum"] == "0.2.0"
    assert boru.cagrilar == [{"tur": "durum"}]


def test_durum_boru_yoksa(yol):
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=lambda istek: {"ok": False, "hata": "tr2en çalışmıyor"})
    sonuc = api.durum()
    assert sonuc["ok"] is False
    assert sonuc["hata"] == "tr2en çalışmıyor"
    assert sonuc["aktif"] is False


def test_aktif_degistir_boruya_gider(yol):
    boru = SahteBoru(cevap={
        "ok": True, "aktif": False, "cevirmen": "bulut",
        "cevirmen_adi": "Bulut — Google Gemini", "kisayol_adi": "Ctrl+Shift+Space",
        "surum": "0.2.0",
    })
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=boru)
    sonuc = api.aktif_degistir()
    assert sonuc["ok"] is True
    assert sonuc["aktif"] is False
    assert boru.cagrilar == [{"tur": "aktif_degistir"}]


def test_aktif_degistir_hata(yol):
    api = PencereApi(ayar_yolu=yol, boru_istemcisi=SahteBoru(hata="tr2en çalışmıyor"))
    sonuc = api.aktif_degistir()
    assert sonuc["ok"] is False
    assert sonuc["hata"] == "tr2en çalışmıyor"


def test_boru_istemcisi_istisnasi_yutulur(yol):
    def patlar(_istek: dict) -> dict:
        raise RuntimeError("boru patladı")

    api = PencereApi(ayar_yolu=yol, boru_istemcisi=patlar)
    assert api.cevir("Merhaba")["ok"] is False
    assert api.durum()["ok"] is False
    assert api.aktif_degistir()["ok"] is False


# ---- ollama_modelleri ----


def test_ollama_modelleri_basarili():
    istekler: list[httpx.Request] = []

    def handler(istek: httpx.Request) -> httpx.Response:
        istekler.append(istek)
        return httpx.Response(200, json={"data": [{"id": "llama3.2"}, {"id": "qwen3"}, {"ad": "bos"}]})

    api = PencereApi(http_istemci=httpx.Client(transport=httpx.MockTransport(handler)))
    sonuc = api.ollama_modelleri("http://localhost:11434/v1")
    assert sonuc["ok"] is True
    assert sonuc["modeller"] == ["llama3.2", "qwen3"]
    assert str(istekler[0].url) == "http://localhost:11434/v1/models"
    assert api.ollama_modelleri("http://[::1]:11434/v1")["ok"] is True
    assert api.ollama_modelleri("http://127.0.0.1:11434/v1")["ok"] is True


def test_ollama_modelleri_yerel_disi_reddedilir():
    istekler: list[httpx.Request] = []

    def handler(istek: httpx.Request) -> httpx.Response:
        istekler.append(istek)
        return httpx.Response(200, json={"data": [{"id": "sizdirilmis"}]})

    api = PencereApi(http_istemci=httpx.Client(transport=httpx.MockTransport(handler)))
    for adres in (
        "http://192.168.1.10:11434/v1",
        "https://api.example.com/v1",
        "http://kotu-localhost.com/v1",
        "file:///etc/passwd",
        "http://localhost.evil.com/v1",
    ):
        sonuc = api.ollama_modelleri(adres)
        assert sonuc["ok"] is False
        assert sonuc["modeller"] == []
        assert isinstance(sonuc["hata"], str) and sonuc["hata"]
    assert istekler == []


def test_ollama_modelleri_baglanti_hatasi():
    def handler(istek: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlanılamadı")

    api = PencereApi(http_istemci=httpx.Client(transport=httpx.MockTransport(handler)))
    sonuc = api.ollama_modelleri("http://localhost:11434/v1")
    assert sonuc["ok"] is False
    assert sonuc["modeller"] == []


def test_ollama_modelleri_beklenmeyen_yanit():
    def handler(istek: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"bes": []})

    api = PencereApi(http_istemci=httpx.Client(transport=httpx.MockTransport(handler)))
    assert api.ollama_modelleri("http://localhost:11434/v1")["ok"] is False

    def handler_500(istek: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"data": []})

    api = PencereApi(http_istemci=httpx.Client(transport=httpx.MockTransport(handler_500)))
    sonuc = api.ollama_modelleri("http://localhost:11434/v1")
    assert sonuc["ok"] is False
    assert "500" in sonuc["hata"]


# ---- klasor_sec ----


def test_klasor_sec_basarili(tmp_path):
    klasor = tmp_path / "model"
    klasor.mkdir()
    (klasor / "model.bin").write_bytes(b"x")
    api = PencereApi(klasor_secici=lambda: str(klasor))
    assert api.klasor_sec() == {"ok": True, "yol": str(klasor)}


def test_klasor_sec_model_yok(tmp_path):
    klasor = tmp_path / "bos"
    klasor.mkdir()
    api = PencereApi(klasor_secici=lambda: str(klasor))
    sonuc = api.klasor_sec()
    assert sonuc["ok"] is False
    assert sonuc["hata"] == "Bu klasörde CTranslate2 modeli yok"


def test_klasor_sec_vazgecildi():
    api = PencereApi(klasor_secici=lambda: None)
    assert api.klasor_sec()["ok"] is False


def test_klasor_secici_yok():
    assert PencereApi().klasor_sec()["ok"] is False


# ---- baglanti_ac ----


def test_baglanti_ac_beyaz_liste():
    tarayici: list[str] = []
    api = PencereApi(tarayici_ac=tarayici.append)
    for ad, url in BEYAZ_LISTE.items():
        assert api.baglanti_ac(ad) == {"ok": True}
        assert tarayici[-1] == url
    assert tarayici == list(BEYAZ_LISTE.values())


def test_baglanti_ac_beyaz_liste_disi_acilmaz():
    tarayici: list[str] = []
    api = PencereApi(tarayici_ac=tarayici.append)
    for ad in ("https://ornek.com", "http://evil", "gemini_anahtar; echo", "", "GITHUB", "github ", "url"):
        assert api.baglanti_ac(ad)["ok"] is False
    assert tarayici == []


def test_baglanti_ac_tarayici_hatasi():
    def bozuk(_url: str) -> None:
        raise RuntimeError("tarayıcı yok")

    api = PencereApi(tarayici_ac=bozuk)
    assert api.baglanti_ac("github")["ok"] is False


# ---- kisayol_kaydet ----


def test_kisayol_kaydet_basarili(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    sonuc = api.kisayol_kaydet(["ctrl", "shift"], "k")
    assert sonuc["ok"] is True
    assert sonuc["kisayol"] == "<ctrl>+<shift>+k"
    assert sonuc["hata"] == ""
    assert sinyaller == ["yenile"]
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["kisayol"] == "<ctrl>+<shift>+k"


def test_kisayol_kaydet_cakisma_uyarir(yol):
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.kisayol_kaydet(["ctrl", "shift"], "t")
    assert sonuc["ok"] is True
    assert "Dikkat" in sonuc["uyari"]


def test_kisayol_kaydet_reddedilen(yol):
    api = PencereApi(ayar_yolu=yol)
    yasak = api.kisayol_kaydet(["ctrl"], "c")
    assert yasak["ok"] is False
    assert isinstance(yasak["hata"], str) and yasak["hata"]
    bos = api.kisayol_kaydet([], "a")
    assert bos["ok"] is False
    gecersiz = api.kisayol_kaydet(["ctrl"], "esc-tusu-disi-gecersiz")
    assert gecersiz["ok"] is False


def test_kisayol_kaydet_vazgecildi(yol):
    api = PencereApi(ayar_yolu=yol)
    sonuc = api.kisayol_kaydet(["ctrl", "shift"], "esc")
    assert sonuc["ok"] is False
    assert sonuc["kisayol"] == ""
    assert sonuc["hata"] == "vazgeçildi"


# ---- kapat_secimi ----


def test_kapat_secimi_kucult_hatirla(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    assert api.kapat_secimi("kucult", True) == {"ok": True}
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["kapatinca_sor"] is False
    assert sinyaller == ["yenile"]


def test_kapat_secimi_kucult_hatirla_yok(yol):
    api = PencereApi(ayar_yolu=yol)
    assert api.kapat_secimi("kucult", False) == {"ok": True}
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["kapatinca_sor"] is True


def test_kapat_secimi_tamamen_hatirla_yok_sayilir(yol):
    sinyaller: list[str] = []
    api = PencereApi(ayar_yolu=yol, sinyal_gonder=sinyaller.append)
    for hatirla in (True, False):
        assert api.kapat_secimi("tamamen", hatirla) == {"ok": True}
    assert sinyaller == ["cikis", "cikis"]
    yuklenen, _ = ayar_modulu.yukle(yol)
    assert yuklenen["kapatinca_sor"] is True


def test_kapat_secimi_gecersiz(yol):
    api = PencereApi(ayar_yolu=yol)
    assert api.kapat_secimi("kapat", True)["ok"] is False


# ---- genel güvenlik ----


def test_anahtar_degeri_hicbir_donusmede_yok(yol, kasa):
    gizli = "GIZLI_HIC_YOK_789"
    kasa.veri["gemini"] = gizli
    kurucu = SahteZincirKurucu(SahteZincir(ceviri=f"ceviri {gizli} son"))
    api = PencereApi(
        ayar_yolu=yol,
        kasa=kasa,
        zincir_kurucu=kurucu,
        tarayici_ac=[].append,
        boru_istemcisi=SahteBoru(cevap={"ok": True, "ceviri": "Hello world",
                                         "cevirmen": "Bulut — Google Gemini",
                                         "durum": "cevrildi", "sure_sn": 0.1}),
    )
    donusler = [
        api.ayarlari_al(),
        api.ayar_kaydet({"tema": "koyu"}),
        api.anahtar_kaydet("openai", gizli),
        api.anahtar_sil("openai"),
        api.baglanti_dene({}, anahtar=gizli),
        api.cevir_dene("Merhaba dünya"),
        api.cevir("Merhaba dünya"),
        api.durum(),
        api.aktif_degistir(),
        api.klasor_sec(),
        api.baglanti_ac("github"),
        api.kisayol_kaydet(["ctrl", "shift"], "k"),
        api.kapat_secimi("tamamen", True),
        api.ilk_kurulum_tamamla("bulut"),
    ]
    for donus in donusler:
        assert gizli not in json.dumps(donus, ensure_ascii=False)
