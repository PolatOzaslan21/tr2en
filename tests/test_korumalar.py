"""korumalar modülü birim testleri (modül yazım aşamasında; şimdilik toplama ImportError verir)."""
from __future__ import annotations

import difflib

import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi, CevirmenZinciri
from ceviri_katmani.cekirdek.korumalar import (
    KorumaHatasi,
    KorumaliCevirmen,
    geri_koy,
    maskele,
    olumsuz_en,
    olumsuz_tr,
    olumsuzluk_kaybi,
)

ROUNDTRIP_ORNEKLERI = [
    "Şu betiği çalıştır:\n```python\nprint(1)\n```",
    "kod:\n```\ndüz içerik\n```",
    "kodu `x = 1` çalıştır",
    "ayarı `pip kur` ile değiştir",
    "https://ornek.com/sayfa?a=1 adresine bak",
    "http://localhost:8080/api bağlan",
    "src/proxy.py dosyasını aç",
    "C:\\Users\\test\\rapor.md dosyası",
    "araclar\\yapilandirma.yaml oku",
    "../config/env yolunu izle",
    "README.md güncel mi?",
    "test-seti.txt dosyasını oku",
    "$MODEL adlı değişkeni kullan",
    "%PATH% yolunu kontrol et",
    "${API_KEY} gerekli",
    "--model bayrağını ekle",
    "-v ile çalıştır",
    "Merhaba dünya",
]

TOLERANS_METINLERI = [
    "kodu `x = a` çalıştır",
    "adres https://ornek.com/sayfa burada",
    "yol src/ana.py içinde",
    "bayrak --model ekle",
]

OLUMSUZ_TR_DOGRU = [
    "testleri silme",
    "yeniden yazma, sadece",
    "bu dosyayı bir daha silme ama yedeğini al",
    "kod çalışmıyor",
    "bu işlem hiç çalışmaz",
    "sonuç hiç gelmedi",
    "kaydetmeden çık",
    "sunucuyu başlatmayın",
    "kapansın istemiyorum",
    "bu yol olmaz",
    "hiçbir dosya bulunamadı",
    "asla şifreyi paylaşma",
    "hiç beklemedim",
    "dosyayı güncellemeyeceğiz",
    "bunu yapmamalı",
    "oturum açılmasın",
    "bunu yapma.",
    "değil",
    "hiçbir dosya yok",
    "yok",
]

OLUMSUZ_TR_YANLIS = [
    "bir deneme yaptım",
    "yazma işlemi bitti",
    "kod sorunsuz çalışıyor",
    "bu kodu çalıştır",
    "yaz",
    "tamamlandı",
    "yapılandırmayı güncelle",
    "dün gece çalıştı",
    "her şey hazır",
    "test başarıyla geçti",
]

OLUMSUZ_EN_DOGRU = [
    "this does not work",
    "code isn't running",
    "never run this",
    "there is no output",
    "none of the files matched",
    "nothing changed",
    "avoid deleting files",
    "without saving",
    "instead of rewriting",
    "stop the process",
]

OLUMSUZ_EN_YANLIS = [
    "this works fine",
    "note the difference",
    "another example",
    "i noticed a bug",
    "the notable point",
    "coffee and donuts",
]


class SahteIc:
    def __init__(self, ad: str, sonuc_f):
        self.ad = ad
        self.sonuc_f = sonuc_f
        self.cagrilar: list[tuple[str, str, str]] = []

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrilar.append((metin, kaynak, hedef))
        return self.sonuc_f(metin)


def _yer_tutucu_bolgeleri(maskeli: str, orijinal: str) -> list[str]:
    sm = difflib.SequenceMatcher(None, orijinal, maskeli, autojunk=False)
    return [maskeli[j1:j2] for tag, _i1, _i2, j1, _j2 in sm.get_opcodes() if tag in ("replace", "insert")]


def _tek_yer_tutucu(maskeli: str, orijinal: str) -> str:
    bolge = "".join(_yer_tutucu_bolgeleri(maskeli, orijinal)).strip()
    assert bolge
    return bolge


def _maskele_dogrula(metin: str, beklenen: list[str]) -> tuple[str, list[str]]:
    maskeli, parcalar = maskele(metin)
    assert isinstance(maskeli, str)
    assert isinstance(parcalar, list)
    assert all(isinstance(p, str) for p in parcalar)
    assert len(parcalar) == len(beklenen)
    for parca in beklenen:
        assert parca in parcalar
        assert parca not in maskeli
    assert geri_koy(maskeli, parcalar) == metin
    return maskeli, parcalar


@pytest.mark.parametrize(
    "metin",
    [
        "Şu betiği çalıştır:\n```python\nprint(1)\n```",
        "kod:\n```\ndüz içerik\n```",
        "```python\nprint(2)\n```",
    ],
)
def test_maskele_kod_blogu_maskelenir(metin):
    blok = "```" + metin.split("```")[1] + "```"
    _maskele_dogrula(metin, [blok])


@pytest.mark.parametrize(
    "metin, beklenen",
    [
        ("kodu `x = 1` çalıştır", ["`x = 1`"]),
        ("ayarı `pip kur` ile değiştir", ["`pip kur`"]),
        ("`npm run test` komutunu koş", ["`npm run test`"]),
    ],
)
def test_maskele_satir_ici_kod_maskelenir(metin, beklenen):
    _maskele_dogrula(metin, beklenen)


@pytest.mark.parametrize(
    "metin, beklenen",
    [
        ("https://ornek.com/sayfa?a=1 adresine bak", ["https://ornek.com/sayfa?a=1"]),
        ("http://localhost:8080/api bağlan", ["http://localhost:8080/api"]),
        ("belge https://docs.ornek.org/kurulum sayfasında", ["https://docs.ornek.org/kurulum"]),
    ],
)
def test_maskele_url_maskelenir(metin, beklenen):
    _maskele_dogrula(metin, beklenen)


@pytest.mark.parametrize(
    "yol",
    ["src/proxy.py", "C:\\Users\\test\\rapor.md", "araclar\\yapilandirma.yaml", "../config/env", "README.md", "test-seti.txt"],
)
def test_maskele_dosya_yolu_maskelenir(yol):
    metin = f"şuraya bak: {yol}"
    _maskele_dogrula(metin, [yol])


@pytest.mark.parametrize(
    "metin, beklenen",
    [
        ("$MODEL adlı değişkeni kullan", ["$MODEL"]),
        ("%PATH% yolunu kontrol et", ["%PATH%"]),
        ("${API_KEY} gerekli", ["${API_KEY}"]),
        ("değeri $ORTAMAd'dan oku", ["$ORTAMAd"]),
    ],
)
def test_maskele_ortam_degiskeni_maskelenir(metin, beklenen):
    _maskele_dogrula(metin, beklenen)


@pytest.mark.parametrize(
    "metin, beklenen",
    [
        ("--model bayrağını ekle", ["--model"]),
        ("-v ile çalıştır", ["-v"]),
        ("çalıştırırken --kurulut bypass kullan", ["--kurulut"]),
    ],
)
def test_maskele_komut_bayragi_maskelenir(metin, beklenen):
    _maskele_dogrula(metin, beklenen)


def test_maskele_coklu_parca_sirasi():
    metin = "`pip kur` ve https://ornek.com/a adresi"
    maskeli, parcalar = maskele(metin)
    assert parcalar == ["`pip kur`", "https://ornek.com/a"]
    assert geri_koy(maskeli, parcalar) == metin


def test_maskele_karisik_turler():
    metin = "$MODEL değişkenini --model bayrağıyla kullan"
    maskeli, parcalar = maskele(metin)
    assert len(parcalar) == 2
    assert "$MODEL" in parcalar and "--model" in parcalar
    assert geri_koy(maskeli, parcalar) == metin


@pytest.mark.parametrize(
    "metin",
    ["Merhaba dünya", "bugün hava çok güzel.", "her şey hazır"],
)
def test_maskele_maskelenecek_yok(metin):
    assert maskele(metin) == (metin, [])


@pytest.mark.parametrize(
    "metin",
    [
        "```python\na = `x`\n```",
        "```text\nbak: https://ornek.com/a\n```",
    ],
)
def test_maskele_ic_ice_kod_blogu_tek_parca(metin):
    maskeli, parcalar = maskele(metin)
    assert len(parcalar) == 1
    assert "https://ornek.com/a" not in maskeli
    assert geri_koy(maskeli, parcalar) == metin


def test_maskele_donus_tipleri():
    maskeli, parcalar = maskele("kodu `x` çalıştır")
    assert isinstance(maskeli, str)
    assert isinstance(parcalar, list)
    assert all(isinstance(p, str) for p in parcalar)


@pytest.mark.parametrize("metin", ROUNDTRIP_ORNEKLERI)
def test_geri_koy_roundtrip(metin):
    maskeli, parcalar = maskele(metin)
    assert geri_koy(maskeli, parcalar) == metin


@pytest.mark.parametrize("metin", ["Merhaba dünya", "her şey hazır", "kod çalışmıyor"])
def test_geri_koy_bos_parcalar_ayni_doner(metin):
    assert geri_koy(metin, []) == metin


@pytest.mark.parametrize("metin", TOLERANS_METINLERI)
def test_geri_koy_bosluk_ekleme_toleransi(metin):
    maskeli, parcalar = maskele(metin)
    ph = _tek_yer_tutucu(maskeli, metin)
    yeni = maskeli.replace(ph, f" {ph} ", 1)
    sonuc = geri_koy(yeni, parcalar)
    assert " ".join(sonuc.split()) == " ".join(metin.split())


@pytest.mark.parametrize("metin", TOLERANS_METINLERI)
def test_geri_koy_bosluk_silme_toleransi(metin):
    maskeli, parcalar = maskele(metin)
    ph = _tek_yer_tutucu(maskeli, metin)
    if f" {ph}" in maskeli:
        yeni = maskeli.replace(f" {ph}", ph, 1)
    else:
        yeni = maskeli.replace(f"{ph} ", ph, 1)
    sonuc = geri_koy(yeni, parcalar)
    assert parcalar[0] in sonuc


@pytest.mark.parametrize("metin", TOLERANS_METINLERI[:2])
def test_geri_koy_yer_tutucu_silinince_hata(metin):
    maskeli, parcalar = maskele(metin)
    ph = _tek_yer_tutucu(maskeli, metin)
    yeni = maskeli.replace(ph, "", 1)
    with pytest.raises(KorumaHatasi):
        geri_koy(yeni, parcalar)


def test_geri_koy_yer_tutucu_hic_yoksa_hata():
    with pytest.raises(KorumaHatasi):
        geri_koy("sadece düz metin", ["`x = 1`"])


@pytest.mark.parametrize("metin", OLUMSUZ_TR_DOGRU)
def test_olumsuz_tr_dogrular(metin):
    assert olumsuz_tr(metin) is True


@pytest.mark.parametrize("metin", OLUMSUZ_TR_YANLIS)
def test_olumsuz_tr_yanlislilar(metin):
    assert olumsuz_tr(metin) is False


@pytest.mark.parametrize("metin", OLUMSUZ_EN_DOGRU)
def test_olumsuz_en_dogrular(metin):
    assert olumsuz_en(metin) is True


@pytest.mark.parametrize("metin", OLUMSUZ_EN_YANLIS)
def test_olumsuz_en_yanlislilar(metin):
    assert olumsuz_en(metin) is False


@pytest.mark.parametrize(
    "tr, en, beklenen",
    [
        ("kod çalışmıyor", "the code works", True),
        ("bunu yapma.", "do it", True),
        ("hiçbir dosya yok", "files are present", True),
        ("kod çalışmıyor", "the code does not work", False),
        ("bir deneme yaptım", "i ran a test", False),
        ("hiçbir dosya yok", "there is nothing", False),
    ],
)
def test_olumsuzluk_kaybi(tr, en, beklenen):
    assert olumsuzluk_kaybi(tr, en) is beklenen


def test_koruma_hatasi_ceviri_hatasi_turetidir():
    assert issubclass(KorumaHatasi, CeviriHatasi)
    with pytest.raises(KorumaHatasi) as bilgi:
        geri_koy("yer tutucu yok", ["parça"])
    assert isinstance(bilgi.value, CeviriHatasi)


def test_korumali_cevirmen_ad_ic_cevirmenden():
    ic = SahteIc("gemini", lambda m: m)
    korumali = KorumaliCevirmen(ic)
    assert korumali.ad == "gemini"


def test_korumali_cevirmen_maskeli_metin_gonderir():
    metin = "kodu `x = a` çalıştır"
    ic = SahteIc("ic", lambda m: "run " + m)
    sonuc = KorumaliCevirmen(ic).cevir(metin)
    gelen = ic.cagrilar[0][0]
    assert gelen != metin
    assert "x = a" not in gelen
    assert "x = a" in sonuc
    assert sonuc != gelen


def test_korumali_cevirmen_maskesiz_metin_cevrilir():
    ic = SahteIc("ic", lambda m: "everything is ready")
    sonuc = KorumaliCevirmen(ic).cevir("her şey hazır")
    assert sonuc == "everything is ready"


def test_korumali_cevirmen_olumsuzluk_kaybinda_hata():
    ic = SahteIc("ic", lambda m: "the code works")
    with pytest.raises(KorumaHatasi):
        KorumaliCevirmen(ic).cevir("kod çalışmıyor")
    assert len(ic.cagrilar) == 1


def test_korumali_cevirmen_olumsuzluk_korunursa_gecer():
    ic = SahteIc("ic", lambda m: "the code does not work")
    assert KorumaliCevirmen(ic).cevir("kod çalışmıyor") == "the code does not work"


def test_korumali_cevirmen_yer_tutucu_kaybolunca_hata():
    ic = SahteIc("ic", lambda m: "run it")
    with pytest.raises(KorumaHatasi):
        KorumaliCevirmen(ic).cevir("kodu `x = a` çalıştır")


def test_korumali_cevirmen_kaynak_tr_degilse_olumsuzluk_kontrol_etmez():
    ic = SahteIc("ic", lambda m: "sil")
    sonuc = KorumaliCevirmen(ic).cevir("do not delete the file", kaynak="en", hedef="tr")
    assert sonuc == "sil"
    assert ic.cagrilar[0][1:] == ("en", "tr")


def test_korumali_cevirmen_varsayilan_kaynak_hedef():
    ic = SahteIc("ic", lambda m: m)
    KorumaliCevirmen(ic).cevir("her şey hazır")
    assert ic.cagrilar[0][1:] == ("tr", "en")


def test_zincir_olumsuzluk_kaybinda_sonrakine_gecer():
    birinci = KorumaliCevirmen(SahteIc("bir", lambda m: "delete the file"))
    ikinci_ic = SahteIc("iki", lambda m: "do not delete the file")
    ikinci = KorumaliCevirmen(ikinci_ic)
    zincir = CevirmenZinciri([birinci, ikinci])
    sonuc = zincir.cevir("bu dosyayı silme")
    assert sonuc == "do not delete the file"
    assert zincir.son_kullanilan == "iki"
    assert len(ikinci_ic.cagrilar) == 1


def test_zincir_tumu_kaybederse_ceviri_hatasi():
    birinci = KorumaliCevirmen(SahteIc("bir", lambda m: "remove it"))
    ikinci = KorumaliCevirmen(SahteIc("iki", lambda m: "erase it"))
    zincir = CevirmenZinciri([birinci, ikinci])
    with pytest.raises(CeviriHatasi):
        zincir.cevir("bu dosyayı silme")
