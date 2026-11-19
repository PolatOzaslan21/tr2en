"""Şema 2 ayarları ve göç (goc_uygula) testleri."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

from ceviri_katmani.uygulama.ayarlar import (
    ACIKLAMALAR,
    BULUT_SERVIS_ADLARI,
    BULUT_SERVIS_ANAHTARLARI,
    GECERLI_BULUT_SERVISLERI,
    GECERLI_CEVIRMENLER,
    GECERLI_TEMALAR,
    GECERLI_YEREL_SECILILER,
    VARSAYILAN,
    dogrula,
    goc_uygula,
    kaydet,
    yukle,
)


# ---- varsayılanlar ve sabitler ----


def test_sema2_varsayilanlar():
    assert VARSAYILAN["cevirmen"] == "bulut"
    assert VARSAYILAN["bulut_servis"] == "gemini"
    assert VARSAYILAN["bulut_adres"] == ""
    assert VARSAYILAN["bulut_model"] == ""
    assert VARSAYILAN["bulut_yedek_yerel"] is True
    assert VARSAYILAN["yerel_secili"] == "dahili"
    assert VARSAYILAN["ollama_adres"] == "http://localhost:11434/v1"
    assert VARSAYILAN["ollama_model"] == ""
    assert VARSAYILAN["lmstudio_adres"] == "http://localhost:1234/v1"
    assert VARSAYILAN["lmstudio_model"] == ""
    assert VARSAYILAN["klasor_yolu"] == ""
    assert VARSAYILAN["kapatinca_sor"] is True
    assert VARSAYILAN["tema"] == "sistem"
    assert VARSAYILAN["ayar_surumu"] == 2
    assert GECERLI_CEVIRMENLER == ("bulut", "yerel")


def test_eski_anahtarlar_kaldi():
    assert VARSAYILAN["uyumlu_adres"] == ""
    assert VARSAYILAN["uyumlu_model"] == ""
    assert VARSAYILAN["uyumlu_anahtar_degiskeni"] == ""
    assert VARSAYILAN["gemini_model"] == "gemini-3.5-flash-lite"
    assert VARSAYILAN["gizlilik_onayi"] is False


def test_servis_sabitleri():
    assert BULUT_SERVIS_ADLARI["openai"] == "https://api.openai.com/v1"
    assert BULUT_SERVIS_ADLARI["deepseek"] == "https://api.deepseek.com/v1"
    assert BULUT_SERVIS_ADLARI["openrouter"] == "https://openrouter.ai/api/v1"
    assert BULUT_SERVIS_ANAHTARLARI["gemini"] == "GEMINI_API_KEY"
    assert BULUT_SERVIS_ANAHTARLARI["openai"] == "OPENAI_API_KEY"
    assert BULUT_SERVIS_ANAHTARLARI["deepseek"] == "DEEPSEEK_API_KEY"
    assert BULUT_SERVIS_ANAHTARLARI["openrouter"] == "OPENROUTER_API_KEY"
    assert BULUT_SERVIS_ANAHTARLARI["diger"] == ""


def test_enum_sabitleri():
    assert GECERLI_BULUT_SERVISLERI == ("gemini", "openai", "deepseek", "openrouter", "diger")
    assert GECERLI_YEREL_SECILILER == ("dahili", "ollama", "lmstudio", "klasor")
    assert GECERLI_TEMALAR == ("sistem", "acik", "koyu")


def test_her_anahtarin_aciklamasi_var():
    for anahtar in VARSAYILAN:
        assert anahtar in ACIKLAMALAR
        assert ACIKLAMALAR[anahtar].strip()


# ---- göç dalları ----


def test_goc_gemini():
    ayarlar, uyarilar = goc_uygula({"cevirmen": "gemini"})
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == "gemini"
    assert ayarlar["bulut_yedek_yerel"] is True
    assert ayarlar["ayar_surumu"] == 2


def test_goc_yerel():
    ayarlar, uyarilar = goc_uygula({"cevirmen": "yerel"})
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "yerel"
    assert ayarlar["yerel_secili"] == "dahili"
    assert ayarlar["ayar_surumu"] == 2


def test_goc_uyumlu_ollama():
    ayarlar, uyarilar = goc_uygula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": "http://localhost:11434/v1",
        "uyumlu_model": "llama3.2",
    })
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "yerel"
    assert ayarlar["yerel_secili"] == "ollama"
    assert ayarlar["ollama_adres"] == "http://localhost:11434/v1"
    assert ayarlar["ollama_model"] == "llama3.2"
    assert ayarlar["ayar_surumu"] == 2


@pytest.mark.parametrize("adres", ["http://localhost:1234/v1", "http://127.0.0.1:1234/v1"])
def test_goc_uyumlu_lmstudio(adres: str):
    ayarlar, uyarilar = goc_uygula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": adres,
        "uyumlu_model": "qwen2.5",
    })
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "yerel"
    assert ayarlar["yerel_secili"] == "lmstudio"
    assert ayarlar["lmstudio_adres"] == adres
    assert ayarlar["lmstudio_model"] == "qwen2.5"


@pytest.mark.parametrize("adres,servis", [
    ("https://api.openai.com/v1", "openai"),
    ("https://api.deepseek.com/v1", "deepseek"),
    ("https://openrouter.ai/api/v1", "openrouter"),
])
def test_goc_uyumlu_bulut_servisleri(adres: str, servis: str):
    ayarlar, uyarilar = goc_uygula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": adres,
        "uyumlu_model": "gpt-4o-mini",
    })
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == servis
    assert ayarlar["bulut_model"] == "gpt-4o-mini"
    assert ayarlar["ayar_surumu"] == 2


def test_goc_uyumlu_diger_host():
    ayarlar, uyarilar = goc_uygula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": "https://ornek.test/v1",
        "uyumlu_model": "ozel-model",
    })
    assert uyarilar == []
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == "diger"
    assert ayarlar["bulut_adres"] == "https://ornek.test/v1"
    assert ayarlar["bulut_model"] == "ozel-model"


@pytest.mark.parametrize("adres,model", [("", "gpt-4o-mini"), ("https://api.openai.com/v1", ""), ("", "")])
def test_goc_uyumlu_bos_adres_veya_model_geminiye(adres: str, model: str):
    ayarlar, uyarilar = goc_uygula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": adres,
        "uyumlu_model": model,
    })
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == "gemini"
    assert any("boş" in u for u in uyarilar)


def test_goc_zaten_yeni_sema_dokunmaz():
    ayarlar, uyarilar = goc_uygula({"cevirmen": "bulut"})
    assert ayarlar["cevirmen"] == "bulut"
    assert uyarilar == []
    assert ayarlar["ayar_surumu"] == 2


# ---- dogrula ile göç ----


def test_dogrula_eski_degerleri_reddetmez():
    ayarlar, uyarilar = dogrula({"cevirmen": "gemini"})
    assert ayarlar["cevirmen"] == "bulut"
    assert not any("cevirmen" in u for u in uyarilar)

    ayarlar, uyarilar = dogrula({
        "cevirmen": "uyumlu",
        "uyumlu_adres": "https://api.openai.com/v1",
        "uyumlu_model": "gpt-4o-mini",
    })
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == "openai"
    assert uyarilar == []


def test_dogrula_surum2_eski_degeri_reddeder():
    ayarlar, uyarilar = dogrula({"cevirmen": "gemini", "ayar_surumu": 2})
    assert ayarlar["cevirmen"] == VARSAYILAN["cevirmen"]
    assert any("cevirmen" in u for u in uyarilar)


def test_dogrula_goc_bir_kez_calisir():
    ayarlar, _ = dogrula({"cevirmen": "gemini", "ayar_surumu": 1})
    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["ayar_surumu"] == 2
    ayarlar, uyarilar = dogrula(dict(ayarlar))
    assert ayarlar["cevirmen"] == "bulut"
    assert uyarilar == []


# ---- geçersiz enum düzeltmesi ----


@pytest.mark.parametrize("anahtar,gecersiz,varsayilan", [
    ("bulut_servis", "yok", "gemini"),
    ("yerel_secili", "yok", "dahili"),
    ("tema", "gece", "sistem"),
])
def test_gecersiz_enum_varsayilana_doner(anahtar: str, gecersiz: str, varsayilan: str):
    ayarlar, uyarilar = dogrula({anahtar: gecersiz, "ayar_surumu": 2})
    assert ayarlar[anahtar] == varsayilan
    assert any(anahtar in u for u in uyarilar)


@pytest.mark.parametrize("anahtar,deger", [
    ("bulut_servis", "openai"),
    ("yerel_secili", "ollama"),
    ("tema", "koyu"),
])
def test_gecerli_enum_kabul(anahtar: str, deger: str):
    ayarlar, uyarilar = dogrula({anahtar: deger, "ayar_surumu": 2})
    assert ayarlar[anahtar] == deger
    assert uyarilar == []


# ---- yukle: göç dosyaya yazılır, bir kez çalışır ----


def test_yukle_goc_dosyayi_yeniden_yazar(tmp_path: Path):
    yol = tmp_path / "ayarlar.toml"
    yol.write_text('cevirmen = "gemini"\ngemini_model = "gemini-x"\n', encoding="utf-8")

    ayarlar, uyarilar = yukle(yol)

    assert ayarlar["cevirmen"] == "bulut"
    assert ayarlar["bulut_servis"] == "gemini"
    assert ayarlar["gemini_model"] == "gemini-x"
    assert uyarilar == []
    yazilan = tomllib.loads(yol.read_text(encoding="utf-8"))
    assert yazilan["ayar_surumu"] == 2
    assert yazilan["cevirmen"] == "bulut"


def test_yukle_goc_bir_kez_calisir(tmp_path: Path):
    yol = tmp_path / "ayarlar.toml"
    yol.write_text(
        'cevirmen = "uyumlu"\nuyumlu_adres = "http://localhost:11434/v1"\nuyumlu_model = "llama3.2"\n',
        encoding="utf-8",
    )
    ilk, _ = yukle(yol)
    assert ilk["yerel_secili"] == "ollama"
    icerik = yol.read_text(encoding="utf-8")

    ikinci, uyarilar = yukle(yol)
    assert yol.read_text(encoding="utf-8") == icerik
    assert ikinci == ilk
    assert uyarilar == []
    assert ikinci["ayar_surumu"] == 2


def test_yukle_surum2_dosyayi_yeniden_yazmaz(tmp_path: Path):
    yol = tmp_path / "ayarlar.toml"
    icerik = 'ayar_surumu = 2\ncevirmen = "bulut"\n'
    yol.write_text(icerik, encoding="utf-8")

    ayarlar, uyarilar = yukle(yol)

    assert ayarlar["cevirmen"] == "bulut"
    assert uyarilar == []
    assert yol.read_text(encoding="utf-8") == icerik


# ---- kaydet -> yukle gidiş dönüşü ----


def test_kaydet_yukle_gidis_donusu(tmp_path: Path):
    yol = tmp_path / "ayarlar.toml"
    ozel = dict(
        VARSAYILAN,
        cevirmen="yerel",
        yerel_secili="ollama",
        ollama_model="llama3.2",
        tema="koyu",
        kapatinca_sor=False,
        bulut_servis="openai",
        bulut_model="gpt-4o-mini",
    )
    assert kaydet(ozel, yol)

    okunan, uyarilar = yukle(yol)

    assert uyarilar == []
    assert okunan == copy.deepcopy(ozel)
    assert tomllib.loads(yol.read_text(encoding="utf-8")) == copy.deepcopy(ozel)
