"""Koruma katmanı testleri — maskele/geri_koy/negasyon + gerçek yerel model."""
from __future__ import annotations

from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.korumalar import (
    KorumaHatasi,
    KorumaliCevirmen,
    geri_koy,
    maskele,
    olumsuz_en,
    olumsuz_tr,
    olumsuzluk_kaybi,
)
from ceviri_katmani.cekirdek.yerel import YerelCevirmen

MODEL = Path("D:/DevCache/ceviri-modelleri/tc-big-tr-en-int8")
MODEL_VAR = MODEL.is_dir() and (MODEL / "source.spm").is_file() and (MODEL / "target.spm").is_file()


# --- maskele ---

def test_maskele_hicbir_sey_yoksa_bos_doner():
    assert maskele("normal bir cümle") == ("normal bir cümle", [])


def test_maskele_dosya_yolu():
    m, p = maskele("src/proxy.py dosyasındaki hatayı düzelt")
    assert p == ["src/proxy.py"]
    assert "ZXQ0ZXQ" in m
    assert "src/proxy.py" not in m


def test_maskele_inline_kod_ve_url():
    m, p = maskele("`uv sync` komutunu çalıştır ve https://example.com/a?b=1 adresine bak")
    assert p == ["`uv sync`", "https://example.com/a?b=1"]
    assert "ZXQ0ZXQ" in m and "ZXQ1ZXQ" in m
    assert "`uv sync`" not in m and "https://example.com" not in m


def test_maskele_bayrak():
    m, p = maskele("--model bayrağını kaldırma")
    assert p == ["--model"]
    assert "ZXQ0ZXQ" in m and "--model" not in m


# --- geri_koy ---

def test_geri_koy_yerine_koyar():
    assert geri_koy("ZXQ0ZXQ dosyası", ["src/proxy.py"]) == "src/proxy.py dosyası"


def test_geri_koy_bos_parcalar_aynen_doner():
    assert geri_koy("abc", []) == "abc"


def test_geri_koy_etrafinda_bosluk_tolere_eder():
    assert geri_koy("Run  ZXQ0ZXQ  now", ["src/proxy.py"]) == "Run  src/proxy.py  now"


def test_geri_koy_eksik_yer_tutucu_hata():
    with pytest.raises(KorumaHatasi):
        geri_koy("hiç yer tutucu yok", ["src/proxy.py"])


# --- negasyon ---

@pytest.mark.parametrize(
    "metin",
    ["testleri silme", "yeniden yazma, sadece", "çalışmaz", "olmaz", "değil", "yok", "hiçbir şey"],
)
def test_olumsuz_tr_true(metin):
    assert olumsuz_tr(metin)


@pytest.mark.parametrize("metin", ["bir deneme yaptım", "dosyasındaki hatayı düzelt", "komutu çalıştır"])
def test_olumsuz_tr_false(metin):
    assert not olumsuz_tr(metin)


@pytest.mark.parametrize("metin", ["do not delete", "don't", "never", "without", "instead of", "avoid"])
def test_olumsuz_en_true(metin):
    assert olumsuz_en(metin)


def test_olumsuz_en_false():
    assert not olumsuz_en("fix the error")


def test_olumsuzluk_kaybi():
    assert olumsuzluk_kaybi("testleri silme", "delete tests")
    assert not olumsuzluk_kaybi("testleri silme", "do not delete tests")
    assert not olumsuzluk_kaybi("hatayı düzelt", "fix the error")


# --- KorumaliCevirmen (sahte çevirmen) ---

class _Sahte:
    def __init__(self, ad: str = "sahte", donusum=None):
        self.ad = ad
        self.donusum = donusum
        self.cagrilar: list[str] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append(metin)
        return self.donusum(metin) if self.donusum else metin


def test_korumali_cevirmen_ad_ve_passthrough():
    ic = _Sahte("yerel:x")
    k = KorumaliCevirmen(ic)
    assert k.ad == "yerel:x"
    sonuc = k.cevir("src/proxy.py dosyasındaki hatayı düzelt")
    assert "src/proxy.py" in sonuc
    # içteki çevirmene maskeli metin gitmeli
    assert "ZXQ0ZXQ" in ic.cagrilar[0]


def test_korumali_cevirmen_negasyon_kaybi_hata():
    class Kayip:
        ad = "kayip"

        def cevir(self, metin, kaynak="tr", hedef="en"):
            return metin.replace("silme", "delete")

    k = KorumaliCevirmen(Kayip())
    with pytest.raises(KorumaHatasi):
        k.cevir("testleri silme")


# --- gerçek yerel model ---

@pytest.fixture(scope="module")
def yerel():
    return YerelCevirmen(str(MODEL))


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
@pytest.mark.parametrize(
    ("metin", "korunacak"),
    [
        ("src/proxy.py dosyasındaki hatayı düzelt", "src/proxy.py"),
        ("`uv sync` komutunu çalıştır ve https://example.com/a?b=1 adresine bak", "`uv sync`"),
        ("`uv sync` komutunu çalıştır ve https://example.com/a?b=1 adresine bak", "https://example.com/a?b=1"),
        ("--model bayrağını kaldırma", "--model"),
    ],
)
def test_gercek_model_korur(yerel, metin, korunacak):
    maskeli, parcalar = maskele(metin)
    sonuc = geri_koy(yerel.cevir(maskeli), parcalar)
    assert korunacak in sonuc


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_gercek_model_korumali_cevirmen(yerel):
    k = KorumaliCevirmen(yerel)
    sonuc = k.cevir("src/proxy.py dosyasındaki hatayı düzelt")
    assert "src/proxy.py" in sonuc
