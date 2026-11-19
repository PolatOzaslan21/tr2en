"""zincir_kur_v2 testleri — sahte çevirmen sınıflarıyla, gerçek model ve ağ yok."""
from __future__ import annotations

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek import kurulum
from ceviri_katmani.cekirdek.kurulum import zincir_kur_v2


class SahteGemini:
    def __init__(self, model="", zaman_asimi=None, anahtar_saglayici=None, **kw):
        self.model = model
        self.zaman_asimi = zaman_asimi
        self.anahtar_saglayici = anahtar_saglayici
        self.ad = f"gemini:{model}"


class SahteUyumlu:
    def __init__(self, adres="", model="", anahtar_degiskeni="", zaman_asimi=None,
                 dusunmeyi_kapat=False, anahtar_saglayici=None, **kw):
        self.adres = adres
        self.model = model
        self.anahtar_degiskeni = anahtar_degiskeni
        self.zaman_asimi = zaman_asimi
        self.dusunmeyi_kapat = dusunmeyi_kapat
        self.anahtar_saglayici = anahtar_saglayici
        self.ad = f"uyumlu:{model}"


class SahteYerel:
    def __init__(self, model_klasoru=None):
        self.model_klasoru = model_klasoru
        self.ad = f"yerel:{model_klasoru or 'dahili'}"


class SahteSozluklu:
    def __init__(self, ic, sozluk=None):
        self.ic = ic
        self.ad = ic.ad


class SahteKorumali:
    def __init__(self, ic):
        self.ic = ic
        self.ad = ic.ad


@pytest.fixture
def sahteler(monkeypatch):
    monkeypatch.setattr(kurulum, "GeminiCevirmen", SahteGemini)
    monkeypatch.setattr(kurulum, "UyumluCevirmen", SahteUyumlu)
    monkeypatch.setattr(kurulum, "YerelCevirmen", SahteYerel)
    monkeypatch.setattr(kurulum, "SozlukluCevirmen", SahteSozluklu)
    monkeypatch.setattr(kurulum, "KorumaliCevirmen", SahteKorumali)


def saglayici_uret(deger: str = "gizli"):
    cagrilar: list[str] = []

    def saglayici(servis: str):
        cagrilar.append(servis)
        return deger

    return saglayici, cagrilar


def test_bulut_gemini_zincir(sahteler):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": "gemini",
        "bulut_model": "gemini-2.0", "zaman_asimi": 4.0, "bulut_yedek_yerel": True,
    }
    saglayici, _ = saglayici_uret()
    z = zincir_kur_v2(ayar, saglayici)

    assert len(z.cevirmenler) == 2
    ilk, yedek = z.cevirmenler
    assert isinstance(ilk, SahteKorumali)
    assert isinstance(ilk.ic, SahteGemini)
    assert ilk.ic.model == "gemini-2.0"
    assert ilk.ic.zaman_asimi == 4.0
    assert isinstance(yedek, SahteKorumali)
    assert isinstance(yedek.ic, SahteSozluklu)
    assert isinstance(yedek.ic.ic, SahteYerel)
    assert yedek.ic.ic.model_klasoru is None


def test_bulut_gemini_model_bossa_gemini_model_kullanilir(sahteler):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": "gemini",
        "bulut_model": "", "gemini_model": "gemini-3.5-flash-lite", "bulut_yedek_yerel": False,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    assert z.cevirmenler[0].ic.model == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("servis,adres", [
    ("openai", "https://api.openai.com/v1"),
    ("deepseek", "https://api.deepseek.com/v1"),
    ("openrouter", "https://openrouter.ai/api/v1"),
])
def test_bulut_diger_servisler_sabit_adres(sahteler, servis: str, adres: str):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": servis, "bulut_model": "gpt-4o-mini",
        "uyumlu_zaman_asimi": 30.0, "bulut_yedek_yerel": False,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    ic = z.cevirmenler[0].ic
    assert isinstance(ic, SahteUyumlu)
    assert ic.adres == adres
    assert ic.model == "gpt-4o-mini"
    assert ic.zaman_asimi == 30.0
    assert ic.anahtar_degiskeni == ""


def test_bulut_diger_adres_kullanilir(sahteler):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": "diger",
        "bulut_adres": "https://ornek.test/v1", "bulut_model": "ozel-model",
        "bulut_yedek_yerel": False,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    ic = z.cevirmenler[0].ic
    assert isinstance(ic, SahteUyumlu)
    assert ic.adres == "https://ornek.test/v1"
    assert ic.model == "ozel-model"


def test_bulut_model_bossa_ceviri_hatasi(sahteler):
    ayar = {"cevirmen": "bulut", "bulut_servis": "openai", "bulut_model": ""}
    with pytest.raises(CeviriHatasi) as bilgi:
        zincir_kur_v2(ayar, saglayici_uret()[0])
    assert "model" in str(bilgi.value)


def test_bulut_diger_adres_bossa_ceviri_hatasi(sahteler):
    ayar = {"cevirmen": "bulut", "bulut_servis": "diger", "bulut_adres": "", "bulut_model": "m"}
    with pytest.raises(CeviriHatasi):
        zincir_kur_v2(ayar, saglayici_uret()[0])


def test_bulut_yedek_yerel_yalniz(sahteler):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": "gemini",
        "bulut_model": "gemini-2.0", "bulut_yedek_yerel": False,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    assert len(z.cevirmenler) == 1
    assert isinstance(z.cevirmenler[0].ic, SahteGemini)


def test_yerel_dahili(sahteler):
    z = zincir_kur_v2({"cevirmen": "yerel", "yerel_secili": "dahili"}, saglayici_uret()[0])
    assert len(z.cevirmenler) == 1
    ic = z.cevirmenler[0].ic
    assert isinstance(ic, SahteSozluklu)
    assert isinstance(ic.ic, SahteYerel)
    assert ic.ic.model_klasoru is None


@pytest.mark.parametrize("secili", ["ollama", "lmstudio"])
def test_yerel_ollama_lmstudio(sahteler, secili: str):
    ayar = {
        "cevirmen": "yerel", "yerel_secili": secili,
        f"{secili}_adres": "http://localhost:11434/v1", f"{secili}_model": "llama3.2",
        "uyumlu_zaman_asimi": 20.0, "uyumlu_dusunmeyi_kapat": True,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    assert len(z.cevirmenler) == 1
    ic = z.cevirmenler[0].ic
    assert isinstance(ic, SahteUyumlu)
    assert ic.adres == "http://localhost:11434/v1"
    assert ic.model == "llama3.2"
    assert ic.zaman_asimi == 20.0
    assert ic.dusunmeyi_kapat is True
    assert ic.anahtar_saglayici is None
    assert ic.anahtar_degiskeni == ""


def test_yerel_model_bossa_ceviri_hatasi(sahteler):
    ayar = {"cevirmen": "yerel", "yerel_secili": "ollama", "ollama_adres": "http://localhost:11434/v1", "ollama_model": ""}
    with pytest.raises(CeviriHatasi) as bilgi:
        zincir_kur_v2(ayar, saglayici_uret()[0])
    assert "model" in str(bilgi.value)


def test_yerel_klasor(sahteler):
    ayar = {"cevirmen": "yerel", "yerel_secili": "klasor", "klasor_yolu": "C:\\modeller\\tc-big"}
    z = zincir_kur_v2(ayar, saglayici_uret()[0])
    ic = z.cevirmenler[0].ic
    assert isinstance(ic, SahteSozluklu)
    assert isinstance(ic.ic, SahteYerel)
    assert ic.ic.model_klasoru == "C:\\modeller\\tc-big"


def test_yerel_klasor_yolu_bossa_ceviri_hatasi(sahteler):
    ayar = {"cevirmen": "yerel", "yerel_secili": "klasor", "klasor_yolu": ""}
    with pytest.raises(CeviriHatasi):
        zincir_kur_v2(ayar, saglayici_uret()[0])


def test_korumasiz_sarilmaz(sahteler):
    ayar = {
        "cevirmen": "bulut", "bulut_servis": "gemini",
        "bulut_model": "gemini-2.0", "bulut_yedek_yerel": True,
    }
    z = zincir_kur_v2(ayar, saglayici_uret()[0], korumasiz=True)
    assert all(not isinstance(c, SahteKorumali) for c in z.cevirmenler)
    assert isinstance(z.cevirmenler[0], SahteGemini)
    assert isinstance(z.cevirmenler[1], SahteSozluklu)


def test_gecersiz_cevirmen_ceviri_hatasi(sahteler):
    with pytest.raises(CeviriHatasi):
        zincir_kur_v2({"cevirmen": "yok"}, saglayici_uret()[0])


def test_gecersiz_bulut_servis_ceviri_hatasi(sahteler):
    with pytest.raises(CeviriHatasi):
        zincir_kur_v2({"cevirmen": "bulut", "bulut_servis": "yok"}, saglayici_uret()[0])


def test_gecersiz_yerel_secili_ceviri_hatasi(sahteler):
    with pytest.raises(CeviriHatasi):
        zincir_kur_v2({"cevirmen": "yerel", "yerel_secili": "yok"}, saglayici_uret()[0])


def test_anahtar_saglayici_gemini(sahteler):
    saglayici, cagrilar = saglayici_uret("kasadaki-anahtar")
    ayar = {"cevirmen": "bulut", "bulut_servis": "gemini", "bulut_model": "gemini-2.0", "bulut_yedek_yerel": False}
    z = zincir_kur_v2(ayar, saglayici, korumasiz=True)
    ic = z.cevirmenler[0]
    assert cagrilar == []
    assert ic.anahtar_saglayici() == "kasadaki-anahtar"
    assert cagrilar == ["gemini"]


@pytest.mark.parametrize("servis", ["openai", "deepseek", "openrouter", "diger"])
def test_anahtar_saglayici_bulut_servisleri(sahteler, servis: str):
    saglayici, cagrilar = saglayici_uret("kasadaki-anahtar")
    ayar = {
        "cevirmen": "bulut", "bulut_servis": servis, "bulut_model": "m",
        "bulut_adres": "https://ornek.test/v1", "bulut_yedek_yerel": False,
    }
    z = zincir_kur_v2(ayar, saglayici, korumasiz=True)
    assert z.cevirmenler[0].anahtar_saglayici() == "kasadaki-anahtar"
    assert cagrilar == [servis]
