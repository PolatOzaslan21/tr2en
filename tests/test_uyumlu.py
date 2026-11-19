"""UyumluCevirmen testleri — gerçek ağa çıkmadan httpx.MockTransport ile."""
from __future__ import annotations

import json

import httpx
import pystray
import pytest

from ceviri_katmani.cekirdek import uyumlu as uyumlu_mod
from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.kurulum import zincir_kur
from ceviri_katmani.cekirdek.uyumlu import UyumluCevirmen
from ceviri_katmani.uygulama.ana import Uygulama
from ceviri_katmani.uygulama.ayarlar import GECERLI_CEVIRMENLER, VARSAYILAN, dogrula
from ceviri_katmani.uygulama.tepsi import Tepsi

ADRES = "https://api.openai.com/v1"


def istemci(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def govde_oku(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def basarili_cevap(icerik: str = "Hello", bitis: str | None = "stop") -> dict:
    aday: dict = {"message": {"content": icerik}}
    if bitis is not None:
        aday["finish_reason"] = bitis
    return {"choices": [aday]}


# ---- istek biçimi ----


def test_url_govde_baslik(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "gizli-anahtar")
    istekler: list[httpx.Request] = []

    def handler(request):
        istekler.append(request)
        return httpx.Response(200, json=basarili_cevap())

    c = UyumluCevirmen(ADRES + "/", "gpt-4o-mini", "OPENAI_API_KEY", istemci=istemci(handler))
    assert c.cevir("Merhaba") == "Hello"
    assert c.ad == "uyumlu:gpt-4o-mini"

    istek = istekler[0]
    assert str(istek.url) == ADRES + "/chat/completions"
    assert istek.headers.get("Authorization") == "Bearer gizli-anahtar"
    assert istek.headers.get("User-Agent") == "tr2en"
    govde = govde_oku(istek)
    assert govde["model"] == "gpt-4o-mini"
    assert govde["messages"][0]["role"] == "system"
    assert "Translate" in govde["messages"][0]["content"]
    assert govde["messages"][1] == {"role": "user", "content": "Merhaba"}
    assert govde["temperature"] == 0
    assert govde["stream"] is False


def test_anahtarsiz_authorization_yok():
    istekler: list[httpx.Request] = []

    def handler(request):
        istekler.append(request)
        return httpx.Response(200, json=basarili_cevap())

    c = UyumluCevirmen("http://localhost:11434/v1", "llama3.2", istemci=istemci(handler))
    assert c.cevir("Merhaba") == "Hello"
    assert "Authorization" not in istekler[0].headers


def test_anahtar_tanimsiz_mesajda_deger_yok(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: None)
    istekler: list[httpx.Request] = []

    def handler(request):
        istekler.append(request)
        return httpx.Response(200, json=basarili_cevap())

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert str(bilgi.value) == "OPENAI_API_KEY tanımlı değil"
    assert istekler == []


# ---- adres doğrulama ----


@pytest.mark.parametrize("adres", [
    "http://example.com/v1",
    "http://192.168.1.10/v1",
    "ftp://localhost/v1",
    "",
])
def test_gecersiz_adres_reddedilir(adres: str):
    with pytest.raises(CeviriHatasi):
        UyumluCevirmen(adres, "gpt-4o")


@pytest.mark.parametrize("adres", [
    "http://localhost:11434/v1",
    "http://127.0.0.1:11434/v1",
    "http://[::1]:11434/v1",
    "https://openrouter.ai/api/v1",
])
def test_gecerli_adres_kabul(adres: str):
    c = UyumluCevirmen(adres, "llama3.2", istemci=istemci(lambda r: httpx.Response(200, json=basarili_cevap())))
    assert c.cevir("Merhaba") == "Hello"


@pytest.mark.parametrize("model", ["", "gpt 4", "satır\natla", "boşluk\tile"])
def test_gecersiz_model_reddedilir(model: str):
    with pytest.raises(CeviriHatasi):
        UyumluCevirmen(ADRES, model)


@pytest.mark.parametrize("degisken", ["OPENAI_API_KEY", "_gizli1", "A"])
def test_gecerli_anahtar_degiskeni(degisken: str):
    UyumluCevirmen(ADRES, "gpt-4o", degisken)


@pytest.mark.parametrize("degisken", ["1basliyor", "boşluk var", "tire-li"])
def test_gecersiz_anahtar_degiskeni(degisken: str):
    with pytest.raises(CeviriHatasi):
        UyumluCevirmen(ADRES, "gpt-4o", degisken)


# ---- hata durumları ----


@pytest.mark.parametrize("kod", [401, 429, 500])
def test_http_hatalari(monkeypatch, kod: int):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(kod, json={"error": {"message": "hata mesajı"}})

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert f"HTTP {kod}" in str(bilgi.value)


def test_ag_hatasi(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        raise httpx.ConnectError("bağlantı kurulamadı", request=request)

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert "ağ hatası" in str(bilgi.value)


def test_finish_reason_length(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(200, json=basarili_cevap(bitis="length"))

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert "tamamlanmamış çeviri" in str(bilgi.value)
    assert "length" in str(bilgi.value)


def test_finish_reason_yoksa_kabul(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(200, json=basarili_cevap(bitis=None))

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    assert c.cevir("Merhaba") == "Hello"


def test_bos_icerik(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(200, json=basarili_cevap(icerik=""))

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert "boş çeviri" in str(bilgi.value)


def test_message_yoksa_bos_ceviri(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop"}]})

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert "boş çeviri" in str(bilgi.value)


def test_think_temizlenir(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(
            200, json=basarili_cevap(icerik="<think>iç muhakeme\nçok satır</think>\nHello <think>ikinci</think>world")
        )

    c = UyumluCevirmen(ADRES, "qwen3-32b", "OPENAI_API_KEY", istemci=istemci(handler))
    assert c.cevir("Merhaba") == "Hello world"


def test_bozuk_json(monkeypatch):
    monkeypatch.setattr(uyumlu_mod, "anahtar_oku", lambda ad: "x")

    def handler(request):
        return httpx.Response(200, content=b"bu json degil")

    c = UyumluCevirmen(ADRES, "gpt-4o", "OPENAI_API_KEY", istemci=istemci(handler))
    with pytest.raises(CeviriHatasi) as bilgi:
        c.cevir("Merhaba")
    assert "beklenmeyen cevap biçimi" in str(bilgi.value)


# ---- zincir ----


def test_zincir_kur_uyumlu_sirasi():
    z = zincir_kur(yalniz="uyumlu", uyumlu_adres=ADRES, uyumlu_model="gpt-4o")
    adlar = [c.ad for c in z.cevirmenler]
    assert adlar[0] == "uyumlu:gpt-4o"
    assert adlar[1].startswith("yerel:")


def test_zincir_kur_uyumlu_tanimsiz_hata():
    with pytest.raises(CeviriHatasi) as bilgi:
        zincir_kur(yalniz="uyumlu")
    assert "uyumlu_adres" in str(bilgi.value)
    assert "uyumlu_model" in str(bilgi.value)


def test_zincir_kur_yalniz_yok_eskisi_gibi():
    z = zincir_kur()
    adlar = [c.ad for c in z.cevirmenler]
    assert adlar[0].startswith("gemini:")
    assert adlar[1].startswith("yerel:")


# ---- ayar doğrulama ----


def test_uyumlu_cevirmen_gecerli():
    assert GECERLI_CEVIRMENLER == ("bulut", "yerel")
    assert VARSAYILAN["cevirmen"] == "bulut"
    assert VARSAYILAN["uyumlu_adres"] == ""
    assert VARSAYILAN["uyumlu_model"] == ""
    assert VARSAYILAN["uyumlu_anahtar_degiskeni"] == ""
    assert VARSAYILAN["uyumlu_zaman_asimi"] == 15.0


def test_uyumlu_zaman_asimi_sinirlar():
    ayarlar, uyarilar = dogrula({"uyumlu_zaman_asimi": 60})
    assert ayarlar["uyumlu_zaman_asimi"] == 60.0
    assert uyarilar == []


@pytest.mark.parametrize("deger", [0, 0.5, 121, 500])
def test_uyumlu_zaman_asimi_aralik_disi(deger):
    ayarlar, uyarilar = dogrula({"uyumlu_zaman_asimi": deger})
    assert ayarlar["uyumlu_zaman_asimi"] == VARSAYILAN["uyumlu_zaman_asimi"]
    assert any("uyumlu_zaman_asimi" in u for u in uyarilar)


# ---- tepsi menüsü ----


class _TepsiArayuz:
    def __init__(self, cevirmen="gemini", uyumlu_tanimli=False):
        self._cevirmen = cevirmen
        self._uyumlu_tanimli = uyumlu_tanimli
        self.cagrilar: list[str] = []

    def cevirmen(self):
        return self._cevirmen

    def aktif_mi(self):
        return True

    def son_ceviri_var_mi(self):
        return False

    def kisayol_simdiki(self):
        return "<ctrl>+<shift>+<space>"

    def otomatik_baslat_acik_mi(self):
        return False

    def son_islemler(self):
        return []

    def cevirmen_sec(self, ad):
        self.cagrilar.append(ad)
        self._cevirmen = ad

    def uyumlu_tanimli_mi(self):
        return self._uyumlu_tanimli


def test_tepsi_cevirmen_uc_oge_ve_sira():
    tepsi = Tepsi(_TepsiArayuz(uyumlu_tanimli=True))
    ogeler = list(tepsi.menu_ogeleri()[2].submenu)
    assert [o.text for o in ogeler] == [
        "Gemini (önerilen, yedek: yerel model)",
        "Kendi modelim (OpenAI uyumlu)",
        "Yalnızca yerel (metin bilgisayardan çıkmaz)",
    ]
    assert all(o.radio is True for o in ogeler)


def test_tepsi_uyumlu_tanimsiz_metin_ve_tiklama():
    arayuz = _TepsiArayuz(uyumlu_tanimli=False)
    tepsi = Tepsi(arayuz)
    ogeler = list(tepsi.menu_ogeleri()[2].submenu)
    assert ogeler[1].text == "Kendi modelim — ayar dosyasında tanımlayın"
    ogeler[1](None)
    assert "uyumlu" in arayuz.cagrilar


# ---- cevirmen_sec ----


def test_cevirmen_sec_uyumlu_tanimsiz_zincir_degismez():
    calls: list[tuple[str, str, str]] = []

    def bildir(baslik, mesaj="", seviye="bilgi"):
        calls.append((baslik, mesaj, seviye))

    zincir_cagrilari: list[str] = []

    def zincir_uretici(ad):
        zincir_cagrilari.append(ad)
        return object()

    zincir = object()
    ayarlar = {
        "cevirmen": "gemini",
        "uyumlu_adres": "",
        "uyumlu_model": "",
        "zincir_uretici": zincir_uretici,
        "kaydet_cb": None,
    }
    uyg = Uygulama(None, None, zincir, bildir, ayarlar)
    uyg.cevirmen_sec("uyumlu")

    assert uyg.zincir is zincir
    assert zincir_cagrilari == []
    assert uyg.ayarlar["cevirmen"] == "gemini"
    assert calls == [
        ("Kendi modeliniz tanımlı değil", "Ayar dosyasında uyumlu_adres ve uyumlu_model'i doldurun.", "uyari")
    ]


def test_cevirmen_sec_uyumlu_tanimli_zincir_kurulur():
    calls: list[tuple[str, str, str]] = []

    def bildir(baslik, mesaj="", seviye="bilgi"):
        calls.append((baslik, mesaj, seviye))

    zincir_cagrilari: list[str] = []

    def zincir_uretici(ad):
        zincir_cagrilari.append(ad)
        return object()

    zincir = object()
    ayarlar = {
        "cevirmen": "gemini",
        "uyumlu_adres": ADRES,
        "uyumlu_model": "gpt-4o-mini",
        "zincir_uretici": zincir_uretici,
        "kaydet_cb": None,
    }
    uyg = Uygulama(None, None, zincir, bildir, ayarlar)
    uyg.cevirmen_sec("uyumlu")

    assert zincir_cagrilari == ["uyumlu"]
    assert uyg.ayarlar["cevirmen"] == "uyumlu"
    assert calls == [("Çevirmen: Kendi modelim (gpt-4o-mini)", "", "bilgi")]


def test_dusunmeyi_kapat_istege_bagli():
    import json

    import httpx

    from ceviri_katmani.cekirdek.uyumlu import UyumluCevirmen

    govdeler = []

    def isle(istek):
        govdeler.append(json.loads(istek.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "Hello"}}]})

    for kapat in (False, True):
        c = UyumluCevirmen("http://localhost:11434/v1", "qwen3.5:0.8b", dusunmeyi_kapat=kapat,
                           istemci=httpx.Client(transport=httpx.MockTransport(isle)))
        assert c.cevir("Merhaba") == "Hello"
    assert "reasoning_effort" not in govdeler[0]
    assert govdeler[1]["reasoning_effort"] == "none"
