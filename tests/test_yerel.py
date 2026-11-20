"""YerelCevirmen testleri."""
from __future__ import annotations

from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.korumalar import KorumaHatasi
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


class _EslemeliTranslator:
    """Her parçayı tek belirteç sayar; çeviriyi sözlükten verir, gördüğü parçaları kaydeder."""

    def __init__(self, esleme: dict[str, str]):
        self.esleme = esleme
        self.gorulen: list[str] = []

    def translate_batch(self, girdiler, beam_size=4, max_decoding_length=256):
        class _Hip:
            def __init__(self, metin):
                self.hypotheses = [[metin]]

        sonuc = []
        for g in girdiler:
            parca = g[0]
            self.gorulen.append(parca)
            sonuc.append(_Hip(self.esleme[parca]))
        return sonuc


class _TekBelirtecSrc:
    def encode(self, metin, out_type=str):
        return [metin]


class _TekBelirtecTgt:
    def decode(self, tokenlar):
        return "".join(tokenlar)


def _eslemeli(esleme: dict[str, str]) -> YerelCevirmen:
    c = YerelCevirmen("kullanilmayan")
    c._translator = _EslemeliTranslator(esleme)
    c._src = _TekBelirtecSrc()
    c._tgt = _TekBelirtecTgt()
    return c


def test_numarali_liste_numarasi_modele_gitmez():
    # Çevrimdışı test (21.11.2026): "2. Toplantı…" -> "The 2nd meeting…" oluyordu.
    c = _eslemeli({
        "Toplantı ertelendi.": "The meeting was postponed.",
        "Siparişiniz yolda.": "Your order is on the way.",
    })
    sonuc = c.cevir("1. Toplantı ertelendi.\n2) Siparişiniz yolda.")
    assert sonuc == "1. The meeting was postponed.\n2) Your order is on the way."
    assert c._translator.gorulen == ["Toplantı ertelendi.", "Siparişiniz yolda."]


def test_numarali_listede_kucuk_harfle_baslayan_madde():
    # "7. npm install komutunu…" küçük harfle başlıyor; listede olduğu için yine ayrılmalı.
    c = _eslemeli({"Uygulamayı aç.": "Open the app.", "npm install çalıştır.": "Run npm install."})
    assert c.cevir("6. Uygulamayı aç.\n7. npm install çalıştır.") == "6. Open the app.\n7. Run npm install."


def test_madde_isareti_korunur():
    c = _eslemeli({"yarın gelirim": "I'll come tomorrow", "Dosyayı gönder.": "Send the file."})
    assert c.cevir("- yarın gelirim\n  • Dosyayı gönder.") == "- I'll come tomorrow\n  • Send the file."


def test_sira_sayisi_liste_sanilmaz():
    # "3. maddeye" sıra sayısıdır (küçük harfle devam eder), olduğu gibi modele gider.
    c = _eslemeli({"3. maddeye göre taraflar yükümlüdür.": "Under article 3 the parties are obliged."})
    assert c.cevir("3. maddeye göre taraflar yükümlüdür.") == "Under article 3 the parties are obliged."


def test_karsitlik_olumsuzlugu_kaybolursa_hata():
    # Çevrimdışı test #19 (21.11.2026): anlamı ters çeviri koruma katmanından geçiyordu.
    tr = "Yapamayacaklarımızdan değil, yapabileceklerimizden bahsedelim."
    c = _eslemeli({tr: "Let's not talk about what we can do, but what we can."})
    with pytest.raises(KorumaHatasi, match="olumsuzluk"):
        c.cevir(tr)


def test_karsitlik_dogru_ceviri_gecer():
    tr = "Yapamayacaklarımızdan değil, yapabileceklerimizden bahsedelim."
    c = _eslemeli({tr: "Let's talk about what we can do, not what we can't do."})
    assert c.cevir(tr) == "Let's talk about what we can do, not what we can't do."


def test_bir_cumlede_kaybolan_olumsuzluk_yakalanir():
    # Bütün metinde başka bir "n't" olsa da kaybolan cümle yakalanmalı.
    c = _eslemeli({"Bunu yapma.": "Don't do this.", "Testleri silme.": "Delete the tests."})
    with pytest.raises(KorumaHatasi, match="olumsuzluk"):
        c.cevir("Bunu yapma. Testleri silme.")


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_satir_sayisi_korunur():
    c = YerelCevirmen(str(MODEL))
    metin = "Merhaba dünya\n\nBu bir test cümlesidir.\n\n\nSon satır burada."
    sonuc = c.cevir(metin)
    assert len(sonuc.split("\n")) == len(metin.split("\n"))
