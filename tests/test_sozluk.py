"""Teknik sözlük (sozluk.tsv + SozlukluCevirmen) testleri."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ceviri_katmani.cekirdek.korumalar import KorumaHatasi
from ceviri_katmani.cekirdek.sozluk import SozlukluCevirmen, sozluk_yukle
from ceviri_katmani.cekirdek.yerel import YerelCevirmen

MODEL = Path(
    os.environ.get("CEVIRI_YEREL_MODEL", "D:/DevCache/ceviri-modelleri/tc-big-tr-en-int8")
)
MODEL_VAR = (
    MODEL.is_dir() and (MODEL / "source.spm").is_file() and (MODEL / "target.spm").is_file()
)


class Sahte:
    def __init__(self, ad: str = "sahte", donusum=None):
        self.ad = ad
        self.donusum = donusum
        self.cagrilar: list[str] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append(metin)
        return self.donusum(metin) if self.donusum else metin


# --- sozluk_yukle ---

def test_paket_sozlugu_en_az_40_kayit_ve_ornekler():
    kayitlar = sozluk_yukle()
    assert len(kayitlar) >= 40
    for turkce, ingilizce in kayitlar:
        assert turkce and ingilizce
        assert not turkce.startswith("#")
    assert ("commit at", "commit") in kayitlar
    assert ("yayına al", "deploy") in kayitlar


def test_uzun_ifadeler_once_gelir():
    kayitlar = sozluk_yukle()
    kelime_sayilari = [len(t.split()) for t, _ in kayitlar]
    assert kelime_sayilari == sorted(kelime_sayilari, reverse=True)


def test_ek_dosya_ve_ayni_ifadeyi_gecersiz_kilar(tmp_path):
    ek = tmp_path / "sozluk.tsv"
    ek.write_text(
        "# yorum\n\ncommit at\tgit commit\nözel ifade\tcustom phrase\ngeçersiz satır\n",
        encoding="utf-8",
    )
    kayitlar = sozluk_yukle(str(ek))
    tablo = dict(kayitlar)
    assert tablo["commit at"] == "git commit"
    assert tablo["özel ifade"] == "custom phrase"
    assert tablo["yayına al"] == "deploy"
    assert "geçersiz satır" not in tablo


def test_olmayan_ek_dosya_yok_sayilir(tmp_path):
    kayitlar = sozluk_yukle(str(tmp_path / "yok.tsv"))
    assert ("commit at", "commit") in kayitlar


# --- SozlukluCevirmen ---

def test_ad_icten_gelir():
    assert SozlukluCevirmen(Sahte("yerel:x")).ad == "yerel:x"


def test_tr_en_disi_dogrudan_ic_cevirmene_gider():
    ic = Sahte()
    s = SozlukluCevirmen(ic)
    assert s.cevir("PR aç", kaynak="en", hedef="tr") == "PR aç"
    assert ic.cagrilar == ["PR aç"]


def test_eslesen_ifadeler_ingilizceye_doner():
    s = SozlukluCevirmen(Sahte())
    sonuc = s.cevir("Değişiklikleri commit at ve PR aç")
    assert "commit" in sonuc
    assert "open a PR" in sonuc
    assert "PR aç" not in sonuc


def test_buyuk_kucuk_harf_duyarsiz():
    s = SozlukluCevirmen(Sahte())
    assert "commit" in s.cevir("COMMIT AT")
    assert "open a PR" in s.cevir("Pr Aç")
    assert "debug" in s.cevir("HATA AYIKLA")


def test_turkce_i_harfleri_dogru_eslesir():
    s = SozlukluCevirmen(Sahte())
    sonuc = s.cevir("İSSUE'YU KAPAT")
    assert sonuc == "close the issue"


def test_cekim_ekleri_eslesir_ve_silinir():
    s = SozlukluCevirmen(Sahte())
    assert "commit" in s.cevir("commit attım")
    assert "attım" not in s.cevir("commit attım")
    assert "commit" in s.cevir("commit atın")
    assert "open a PR" in s.cevir("PR açtım")
    assert "açtım" not in s.cevir("PR açtım")


def test_kelime_basi_siniri():
    s = SozlukluCevirmen(Sahte())
    assert s.cevir("xcommit at") == "xcommit at"
    assert s.cevir("commit atx") == "commit atx"


def test_kismi_kelime_eslesmez():
    s = SozlukluCevirmen(Sahte())
    assert "open a PR" not in s.cevir("PR açıklaması")
    s2 = SozlukluCevirmen(Sahte(), sozluk=[("derle", "build")])
    assert s2.cevir("derleyici") == "derleyici"


def test_ic_cevirmene_yer_tutucu_gider():
    ic = Sahte()
    s = SozlukluCevirmen(ic)
    s.cevir("PR aç ve testleri çalıştır")
    assert "QZS0QZS" in ic.cagrilar[0]
    assert "QZS1QZS" in ic.cagrilar[0]
    assert "PR aç" not in ic.cagrilar[0]


def test_eslesme_yoksa_metin_aynen_ic_cevirmene_gider():
    ic = Sahte()
    s = SozlukluCevirmen(ic, sozluk=[("commit at", "commit")])
    assert s.cevir("alakasız cümle") == "alakasız cümle"
    assert ic.cagrilar == ["alakasız cümle"]


def test_yer_tutucu_kaybolursa_koruma_hatasi():
    s = SozlukluCevirmen(Sahte(donusum=lambda _: "bozuk çeviri"))
    with pytest.raises(KorumaHatasi):
        s.cevir("PR aç")


def test_ozel_sozluk_ve_ek_silme():
    s = SozlukluCevirmen(Sahte(), sozluk=[("yayına al", "deploy")])
    assert s.cevir("yayına aldık") == "deploy"
    assert s.cevir("yayına almadan") == "deploy"


def test_yer_tutucu_yerine_ingilizce_konur():
    s = SozlukluCevirmen(
        Sahte(donusum=lambda m: "Before: " + m), sozluk=[("PR aç", "open a PR")]
    )
    assert s.cevir("PR aç") == "Before: open a PR"


# --- gerçek yerel model ---

@pytest.fixture(scope="module")
def yerel():
    return SozlukluCevirmen(YerelCevirmen(str(MODEL)))


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_gercek_model_commit_ve_pr(yerel):
    sonuc = yerel.cevir("Değişiklikleri commit at ve PR aç")
    assert "commit" in sonuc
    assert "open a PR" in sonuc


@pytest.mark.skipif(not MODEL_VAR, reason="test model klasörü yok")
def test_gercek_model_deploy_ve_testler(yerel):
    sonuc = yerel.cevir("Bunu yayına almadan önce testleri çalıştır")
    assert "deploy" in sonuc
    assert "run the tests" in sonuc
