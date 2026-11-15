"""YerelCevirmen testleri."""
from __future__ import annotations

from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.yerel import YerelCevirmen

MODEL = Path("D:/DevCache/ceviri-modelleri/tc-big-tr-en-int8")
MODEL_VAR = MODEL.is_dir() and (MODEL / "source.spm").is_file() and (MODEL / "target.spm").is_file()
YOK = str(Path(__file__).parent / "bu-klasor-yok-12345")


def test_klasor_yoksa_hata():
    c = YerelCevirmen(YOK)
    with pytest.raises(CeviriHatasi):
        c.cevir("merhaba dünya")


def test_tr_en_disi_hata():
    c = YerelCevirmen(str(MODEL))
    with pytest.raises(CeviriHatasi, match="yalnızca tr->en"):
        c.cevir("hello", kaynak="en", hedef="tr")
    with pytest.raises(CeviriHatasi, match="yalnızca tr->en"):
        c.cevir("merhaba", kaynak="tr", hedef="fr")


def test_tembel_yukleme_ve_ad():
    c = YerelCevirmen(str(MODEL))
    assert c.ad == "yerel:tc-big-tr-en-int8"
    assert c._translator is None
    assert c._src is None
    assert c._tgt is None


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_cevirir():
    c = YerelCevirmen(str(MODEL))
    sonuc = c.cevir("Testleri silme")
    kucuk = sonuc.lower()
    assert "not" in kucuk or "don't" in kucuk


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_satir_sayisi_korunur():
    c = YerelCevirmen(str(MODEL))
    metin = "Merhaba dünya\n\nBu bir test cümlesidir.\n\n\nSon satır burada."
    sonuc = c.cevir(metin)
    assert len(sonuc.split("\n")) == len(metin.split("\n"))
