"""bolme modülü ve yerel çevirmen bölme entegrasyonu testleri."""
from __future__ import annotations

from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.bolme import birlestir, parcala
from ceviri_katmani.cekirdek.korumalar import KorumaHatasi
from ceviri_katmani.cekirdek.yerel import YerelCevirmen

MODEL = Path("D:/DevCache/ceviri-modelleri/tc-big-tr-en-int8")
MODEL_VAR = MODEL.is_dir() and (MODEL / "source.spm").is_file() and (MODEL / "target.spm").is_file()


def test_bos_metin_bos_liste():
    assert parcala("") == [[]]


def test_bos_satir_bos_parca():
    assert parcala("merhaba\n\ndünya") == [["merhaba"], [], ["dünya"]]


def test_nokta_ile_boler():
    assert parcala("İlk cümle. İkinci cümle.") == [["İlk cümle.", "İkinci cümle."]]


def test_unlem_soru_elips():
    assert parcala("Ne güzel! Gerçekten mi? Devamı… sonra") == [
        ["Ne güzel!", "Gerçekten mi?", "Devamı…", "sonra"]
    ]


@pytest.mark.parametrize(
    "metin, beklenen",
    [
        ("ör. bu bir örnektir. sonra", [["ör. bu bir örnektir.", "sonra"]]),
        ("örn. şöyle yapılır. tamam", [["örn. şöyle yapılır.", "tamam"]]),
        ("bkz. ilgili bölüm. iyi", [["bkz. ilgili bölüm.", "iyi"]]),
        ("vb. gibi şeyler. bitti", [["vb. gibi şeyler.", "bitti"]]),
        ("sn. sonra gelir. tamam", [["sn. sonra gelir.", "tamam"]]),
        ("dr. raporu hazır. tamam", [["dr. raporu hazır.", "tamam"]]),
        ("prof. dr. geldi. bitti", [["prof. dr. geldi.", "bitti"]]),
    ],
)
def test_kisaltma_bolunmez(metin, beklenen):
    assert parcala(metin) == beklenen


def test_surum_bolunmez():
    assert parcala("v1.2 sürümü yayınlandı. sonra güncelle") == [
        ["v1.2 sürümü yayınlandı.", "sonra güncelle"]
    ]


def test_dosya_adi_bolunmez():
    assert parcala("README.md dosyasını aç. sonra oku") == [
        ["README.md dosyasını aç.", "sonra oku"]
    ]


def test_yer_tutucu_bolunmez():
    assert parcala("kodu ZXQ0ZXQ çalıştır. sonra ZXQ1ZXQ ekle") == [
        ["kodu ZXQ0ZXQ çalıştır.", "sonra ZXQ1ZXQ ekle"]
    ]


def test_uzun_noktalamasiz_bolunur():
    kelimeler = [f"kelime{i}" for i in range(120)]
    metin = " ".join(kelimeler)
    parcalar = parcala(metin)
    assert len(parcalar) == 1
    assert len(parcalar[0]) == 3
    for p in parcalar[0]:
        assert len(p.split()) <= 40
    assert birlestir(parcalar).split() == kelimeler


def test_kelime_sinirinda_esit_bolunur():
    kelimeler = [f"k{i}" for i in range(90)]
    parcalar = parcala(" ".join(kelimeler))[0]
    assert [len(p.split()) for p in parcalar] == [40, 40, 10]


def test_virgulden_boler():
    kelimeler = [f"k{i}" for i in range(100)]
    metin = ""
    for i, k in enumerate(kelimeler):
        metin += k
        metin += ", " if i in (19, 39, 59, 79) else " "
    metin = metin.strip()
    sonuc = parcala(metin)
    assert len(sonuc[0]) == 5
    for p in sonuc[0]:
        assert len(p.split()) <= 40
    assert birlestir(sonuc).split() == metin.split()


def test_baglac_sonraki_parcada_kalir():
    once = " ".join(f"a{i}" for i in range(30))
    sonra = " ".join(f"b{i}" for i in range(30))
    metin = f"{once} ama {sonra}"
    sonuc = parcala(metin)
    assert len(sonuc[0]) == 2
    assert sonuc[0][1].startswith("ama")
    assert len(sonuc[0][0].split()) <= 40
    assert len(sonuc[0][1].split()) <= 40
    assert birlestir(sonuc).split() == metin.split()


def test_cok_satirli_yapi_korunur():
    metin = "ilk satır.\n\nikinci satır burada.\n\n\nson satır."
    parcalar = parcala(metin)
    assert len(parcalar) == len(metin.split("\n"))
    assert parcalar[1] == []
    assert parcalar[3] == []
    assert parcalar[4] == []
    assert birlestir(parcalar) == metin


def test_birlestir_parcala_roundtrip():
    metin = "ör. önce bkz. sonra. ve v1.2 sürümü."
    assert birlestir(parcala(metin)) == metin


class _SahteTranslator:
    def __init__(self, token_sayisi: int):
        self.token_sayisi = token_sayisi

    def translate_batch(self, girdiler, beam_size=4, max_decoding_length=256):
        class _Hip:
            def __init__(self, n):
                self.hypotheses = [["tok"] * n]

        return [_Hip(self.token_sayisi) for _ in girdiler]


class _SahteSrc:
    def encode(self, metin, out_type=str):
        return ["t"]


class _SahteTgt:
    def decode(self, tokenlar):
        return " ".join(tokenlar)


def _sahte_cevirmen(token_sayisi: int) -> YerelCevirmen:
    c = YerelCevirmen("kullanilmayan")
    c._translator = _SahteTranslator(token_sayisi)
    c._src = _SahteSrc()
    c._tgt = _SahteTgt()
    return c


def test_kesilme_hatasi():
    c = _sahte_cevirmen(256)
    with pytest.raises(KorumaHatasi, match="kesildi"):
        c.cevir("merhaba dünya")


def test_kesilme_yoksa_cevirir():
    c = _sahte_cevirmen(3)
    assert c.cevir("merhaba dünya") == "tok tok tok"


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_gercek_model_uzun_paragraf():
    paragraf = (
        "yazılım geliştirme süreci birçok adımdan oluşur ve her adım dikkatle "
        "planlanmalıdır önce proje gereksinimleri toplanır ve analiz edilir "
        "ardından sistem mimarisi tasarlanır ve bileşenler ayrıştırılır "
        "geliştiriciler her bileşen için ayrı bir görev oluşturur ve bu görevleri "
        "takip eder kaynak kod bir sürüm kontrol sistemi üzerinde tutulur ve her "
        "değişiklik ayrıntılı olarak kaydedilir yazılan kodun doğruluğunu kontrol "
        "etmek için birim testleri hazırlanır ve bu testler düzenli aralıklarla "
        "çalıştırılır sürekli entegrasyon ortamı her gönderimden sonra tüm "
        "testleri yeniden başlatır ve sonuçları ekip üyelerine bildirir hatalar "
        "bulunduğunda geliştirici ilgili düzeltmeyi yapar ve testleri yeniden "
        "çalıştırır kod inceleme süreci deneyimli geliştiriciler tarafından "
        "yürütülür ve olası sorunlar erkenden yakalanır kurulum paketi "
        "hazırlanırken bağımlılık listesi dikkatle kontrol edilir ve eksikler "
        "giderilir yayın öncesi dokümantasyon güncellenir kullanım kılavuzu "
        "gözden geçirilir ve sürüm notları yazılır son aşamada tüm adımlar "
        "tamamlanır ve proje yayına hazırlanır en son da README dosyasını güncelle"
    )
    assert len(paragraf.split()) >= 120
    sonuc = YerelCevirmen(str(MODEL)).cevir(paragraf)
    assert "readme" in sonuc.lower()
