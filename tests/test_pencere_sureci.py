"""pencere_sureci.py testleri — sahte webview ve sahte win32 ile; gerçek pencere açılmaz.

HTML doğrulaması da bu dosyadadır: ayarlar.html tek parça olmalı, http(s)
src/href içermemeli (dış bağlantılar yalnızca baglanti_ac ile) ve
``window.kapatmaSor`` tanımlı olmalı.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ceviri_katmani.uygulama import ayarlar as ayar_modulu
from ceviri_katmani.uygulama import pencere_sureci, tek_ornek

HTML_YOLU = (
    Path(__file__).resolve().parents[1]
    / "src" / "ceviri_katmani" / "uygulama" / "arayuz" / "ayarlar.html"
)


# ---- sahteler ----


class SahteOlay:
    def __init__(self) -> None:
        self.dinleyiciler: list = []

    def __iadd__(self, islev):
        self.dinleyiciler.append(islev)
        return self


class SahtePencere:
    def __init__(self) -> None:
        self.events = SimpleNamespace(closing=SahteOlay())
        self.js_cagrilar: list[str] = []
        self.destroy_sayisi = 0
        self.diyalog_turleri: list = []

    def evaluate_js(self, kod: str) -> None:
        self.js_cagrilar.append(kod)

    def destroy(self) -> None:
        self.destroy_sayisi += 1

    def create_file_dialog(self, tur, **kwargs):
        self.diyalog_turleri.append(tur)
        return None


class SahteWebview:
    FOLDER_DIALOG = 3

    def __init__(self, pencere: SahtePencere | None = None, hata: Exception | None = None) -> None:
        self.pencere = pencere or SahtePencere()
        self.hata = hata
        self.argumanlar: dict | None = None
        self.start_gui: str | None = None

    def create_window(self, baslik, **kwargs):
        self.argumanlar = {"baslik": baslik, **kwargs}
        return self.pencere

    def start(self, gui: str | None = None) -> None:
        self.start_gui = gui
        if self.hata is not None:
            raise self.hata


class SahteKilitWin:
    ERROR_ALREADY_EXISTS = 183

    def __init__(self) -> None:
        self.varolan: set = set()
        self.son_hata = 0
        self.kapatilan: list = []

    def CreateMutex(self, g1, g2, ad):
        varmis = ad in self.varolan
        self.varolan.add(ad)
        self.son_hata = self.ERROR_ALREADY_EXISTS if varmis else 0
        return object()

    def GetLastError(self):
        return self.son_hata

    def CloseHandle(self, h):
        self.kapatilan.append(h)


class SahteGui:
    SW_RESTORE = 9

    def __init__(self, hwnd: int = 42, kucuk: bool = False) -> None:
        self.hwnd = hwnd
        self.kucuk = kucuk
        self.gosterilen: list = []
        self.one_alinan: list = []

    def FindWindow(self, sinif, baslik):
        self.bulunan_baslik = baslik
        return self.hwnd

    def IsIconic(self, hwnd):
        return self.kucuk

    def ShowWindow(self, hwnd, komut):
        self.gosterilen.append((hwnd, komut))

    def SetForegroundWindow(self, hwnd):
        self.one_alinan.append(hwnd)


def bekle(kosul, sure: float = 2.0) -> bool:
    son = time.time() + sure
    while time.time() < son:
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


@pytest.fixture
def kilit_kayit(monkeypatch):
    """Gerçek win32 mutex çağrılarını kayıtçı sahtelerle değiştirir."""
    kayit = SimpleNamespace(alinan=[], birakilan=[])

    def sahte_al(ad, *, _win=None):
        kayit.alinan.append(ad)
        return object()

    def sahte_birak(kilit):
        kayit.birakilan.append(kilit)

    monkeypatch.setattr(tek_ornek, "kilit_al", sahte_al)
    monkeypatch.setattr(tek_ornek, "kilit_birak", sahte_birak)
    return kayit


def api_yap(tmp_path, **ek):
    return SimpleNamespace(ayar_yolu=tmp_path / "ayarlar.toml", **ek)


def calistir(tmp_path, monkeypatch, kilit_kayit, *, api=None, webview=None, kapatinca_sor=True):
    ayar_modulu.kaydet({"kapatinca_sor": kapatinca_sor}, tmp_path / "ayarlar.toml")
    webview = webview or SahteWebview()
    api = api if api is not None else api_yap(tmp_path)
    kod = pencere_sureci.calistir([], webview_modulu=webview, api=api, kilit=object())
    return kod, webview, api


# ---- HTML doğrulaması ----

def test_html_tek_parca():
    metin = HTML_YOLU.read_text(encoding="utf-8")
    assert metin.lstrip().lower().startswith("<!doctype html>")
    assert re.search(r"<script[^>]\ssrc\s*=", metin, re.I) is None
    assert re.search(r"<link[^>]", metin, re.I) is None
    assert re.search(r"@import", metin) is None
    assert re.search(r"<img[^>]", metin, re.I) is None
    assert re.search(r"url\(\s*['\"]?https?://", metin, re.I) is None


def test_html_dis_kaynak_url_yok():
    metin = HTML_YOLU.read_text(encoding="utf-8")
    assert re.search(r"(?:src|href)\s*=\s*[\"']https?://", metin, re.I) is None
    assert re.search(r"(?:src|href)\s*=\s*[\"']//", metin) is None


def test_html_kapatmasor_tanimli():
    metin = HTML_YOLU.read_text(encoding="utf-8")
    assert "window.kapatmaSor" in metin
    assert "kapatKucult" in metin and "kapatTamamen" in metin and "kapatVazgec" in metin
    assert "kapat_secimi" in metin and "pencereyi_kapat" in metin


def test_html_kopruye_bagli():
    metin = HTML_YOLU.read_text(encoding="utf-8")
    for yontem in ("ayarlari_al", "ayar_kaydet", "anahtar_kaydet", "anahtar_sil",
                   "baglanti_dene", "ollama_modelleri", "klasor_sec", "baglanti_ac",
                   "kisayol_kaydet"):
        assert f"api.{yontem}" in metin
    assert "pywebviewready" in metin


# ---- _one_getir ----

def test_one_getir_kuculmuse_geri_acar_one_getirir():
    gui = SahteGui(hwnd=7, kucuk=True)
    pencere_sureci._one_getir("tr2en Ayarlar", gui=gui)
    assert gui.gosterilen == [(7, gui.SW_RESTORE)]
    assert gui.one_alinan == [7]
    assert gui.bulunan_baslik == "tr2en Ayarlar"


def test_one_getir_yoksa_bir_sey_yapmaz():
    gui = SahteGui(hwnd=0)
    pencere_sureci._one_getir("tr2en Ayarlar", gui=gui)
    assert gui.gosterilen == []
    assert gui.one_alinan == []


def test_one_getir_hata_yutar():
    class Bozuk:
        def FindWindow(self, a, b):
            raise RuntimeError("win32 hatası")

    pencere_sureci._one_getir("tr2en Ayarlar", gui=Bozuk())


# ---- calistir ----

def test_pencere_parametreleri_dogru(tmp_path, monkeypatch, kilit_kayit):
    kod, webview, api = calistir(tmp_path, monkeypatch, kilit_kayit)
    assert kod == 0
    assert webview.argumanlar["baslik"] == "tr2en Ayarlar"
    assert webview.argumanlar["width"] == 820
    assert webview.argumanlar["height"] == 600
    assert webview.argumanlar["min_size"] == (720, 520)
    assert webview.argumanlar["js_api"] is api
    assert webview.argumanlar["url"].endswith("ayarlar.html")
    assert webview.start_gui == "edgechromium"


def test_pencereyi_kapat_destroy_cagirir(tmp_path, monkeypatch, kilit_kayit):
    kod, webview, api = calistir(tmp_path, monkeypatch, kilit_kayit)
    assert kod == 0
    sonuc = api.pencereyi_kapat()
    assert sonuc["ok"] is True
    assert webview.pencere.destroy_sayisi == 1


def test_webview_hatasi_2_doner(tmp_path, monkeypatch, kilit_kayit, capsys):
    webview = SahteWebview(hata=RuntimeError("WebView2 yok"))
    kod, _, _ = calistir(tmp_path, monkeypatch, kilit_kayit, webview=webview)
    assert kod == 2
    assert "WebView2 yok" in capsys.readouterr().err


def test_zaten_acik_pencere_one_getirilir(tmp_path, monkeypatch, kilit_kayit):
    cagrilar: list[str] = []
    alinan: list[str] = []
    monkeypatch.setattr(pencere_sureci, "_one_getir", lambda baslik: cagrilar.append(baslik))
    monkeypatch.setattr(tek_ornek, "kilit_al", lambda ad, *, _win=None: alinan.append(ad) or None)
    kod = pencere_sureci.calistir([], webview_modulu=SahteWebview(), api=api_yap(tmp_path))
    assert kod == 0
    assert cagrilar == ["tr2en Ayarlar"]
    assert alinan == [pencere_sureci.MUTEX_ADI]
    assert kilit_kayit.birakilan == []


def test_mutex_basari_sonunda_birakilir(tmp_path, monkeypatch, kilit_kayit):
    kilit = object()
    kod = pencere_sureci.calistir(
        [], webview_modulu=SahteWebview(), api=api_yap(tmp_path), kilit=kilit
    )
    assert kod == 0
    assert kilit_kayit.birakilan == [kilit]


def test_closing_kapatinca_sor_acikken_sorar(tmp_path, monkeypatch, kilit_kayit):
    kod, webview, api = calistir(tmp_path, monkeypatch, kilit_kayit, kapatinca_sor=True)
    assert kod == 0
    dinleyiciler = webview.pencere.events.closing.dinleyiciler
    assert len(dinleyiciler) == 1
    assert dinleyiciler[0]() is False
    assert bekle(lambda: webview.pencere.js_cagrilar == ["kapatmaSor()"])


def test_closing_kapatinca_sor_kapaliyken_kapatir(tmp_path, monkeypatch, kilit_kayit):
    kod, webview, api = calistir(tmp_path, monkeypatch, kilit_kayit, kapatinca_sor=False)
    assert kod == 0
    assert webview.pencere.events.closing.dinleyiciler[0]() is True
    time.sleep(0.05)
    assert webview.pencere.js_cagrilar == []


def test_closing_pencereyi_kapat_sonrasi_atlanir(tmp_path, monkeypatch, kilit_kayit):
    kod, webview, api = calistir(tmp_path, monkeypatch, kilit_kayit, kapatinca_sor=True)
    assert kod == 0
    api.pencereyi_kapat()
    assert webview.pencere.events.closing.dinleyiciler[0]() is True
    time.sleep(0.05)
    assert webview.pencere.js_cagrilar == []


def test_klasor_secici_diyalogu_sarmalar(tmp_path, monkeypatch, kilit_kayit):
    webview = SahteWebview()
    kod = pencere_sureci.calistir([], webview_modulu=webview, kilit=object())
    assert kod == 0
    api = webview.argumanlar["js_api"]
    assert callable(api.pencereyi_kapat)
    sonuc = api.klasor_sec()
    assert sonuc == {"ok": False, "yol": "", "hata": "klasör seçilmedi"}
    assert webview.pencere.diyalog_turleri == [webview.FOLDER_DIALOG]
