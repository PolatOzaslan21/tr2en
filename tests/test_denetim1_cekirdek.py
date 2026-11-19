"""INCELEME-1 çekirdek bulgularına karşılık gelen yeni testler.

Her bulgu için en az bir test; düzeltme sonrası davranışı sabitler.
Ağ/uygulama/pano kullanılmaz; sahte istemciler ve sahte çevirmenler yeterlidir.
"""
from __future__ import annotations

import builtins
import hashlib
from pathlib import Path

import httpx
import pytest

from ceviri_katmani.cekirdek import gemini as gemini_mod
from ceviri_katmani.cekirdek import indir
from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi, CevirmenZinciri
from ceviri_katmani.cekirdek.cikti import temizle_ve_dogrula
from ceviri_katmani.cekirdek.dil import turkce_mi
from ceviri_katmani.cekirdek.gemini import GeminiCevirmen
from ceviri_katmani.cekirdek.korumalar import (
    KorumaHatasi,
    geri_koy,
    maskele,
    olumsuz_en,
    olumsuz_tr,
    olumsuzluk_kaybi,
)
from ceviri_katmani.cekirdek.kurulum import akilli_cevir
from ceviri_katmani.cekirdek.sozluk import SozlukluCevirmen
from ceviri_katmani.cekirdek.yerel import YerelCevirmen


class _Yanki:
    ad = "yerel:yanki"

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        return metin


class _Kayitli:
    ad = "sahte"

    def __init__(self):
        self.cagrildi = False

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        self.cagrildi = True
        return "translated:" + metin


# --------------------------------------------------------------------------- #
# 1) -mamış/-memiş olumsuz geçmiş
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "metin",
    ["silmemiş", "silmemişler", "gelmemişsin", "yapmamıştım", "Bu dosyayı silmemiş."],
)
def test_olumsuz_tr_olumsuz_gecmis_taninir(metin):
    assert olumsuz_tr(metin) is True


def test_olumsuzluk_kaybi_olumsuz_gecmis_yakalanir():
    assert olumsuzluk_kaybi("Bu dosyayı silmemiş.", "The user deleted this file.") is True


# --------------------------------------------------------------------------- #
# 2) İngilizce olumsuzluk listesi + -ma/-me istisna kümesi
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "metin",
    [
        "I was unable to do this",
        "the operation failed",
        "it fails often",
        "nobody came",
        "nothing happened",
        "nowhere to go",
        "unless you fix it",
        "cannot open",
        "don't",
        "don’t",
        "can’t",
        "isn’t",
        "wouldn't",
    ],
)
def test_olumsuz_en_genisletilmis_liste(metin):
    assert olumsuz_en(metin) is True


def test_olumsuzluk_kaybi_unable_yapisini_yakalamaz():
    assert olumsuzluk_kaybi("Bunu yapamadım.", "I was unable to do this.") is False


def test_olumsuzluk_kaybi_elma_yakalamaz():
    assert olumsuzluk_kaybi("Bu elma.", "This is an apple.") is False


def test_olumsuz_tr_elma_olumsuz_degil():
    assert olumsuz_tr("Bu elma.") is False


def test_olumsuz_tr_silme_emri_olumsuz_kalir():
    assert olumsuz_tr("Dosyayı silme.") is True


# --------------------------------------------------------------------------- #
# 3) cikti: önsöz aynı satırda silinmez; boş çıktı her zaman hata
# --------------------------------------------------------------------------- #
def test_cikti_sure_ayni_satir_korunur():
    assert temizle_ve_dogrula("Tabii, bekle.", "Sure, wait.") == "Sure, wait."


def test_cikti_sure_tek_basina_bos_hata():
    with pytest.raises(KorumaHatasi):
        temizle_ve_dogrula("Hayır", "Sure,")


# --------------------------------------------------------------------------- #
# 4) gemini finishReason denetimi
# --------------------------------------------------------------------------- #
def _gemini_aday(aday: dict) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"candidates": [aday]}))
    )


@pytest.fixture
def anahtar(monkeypatch):
    monkeypatch.setattr(gemini_mod, "anahtar_oku", lambda ad: "test-anahtar")


@pytest.mark.parametrize("bitis", ["MAX_TOKENS", "SAFETY", "RECITATION", "OTHER"])
def test_gemini_tamamlanmamis_ceviri_hata(anahtar, bitis):
    c = GeminiCevirmen(istemci=_gemini_aday({"finishReason": bitis, "content": {"parts": [{"text": "kısmi"}]}}))
    with pytest.raises(CeviriHatasi):
        c.cevir("merhaba")


def test_gemini_stop_kabul_edilir(anahtar):
    c = GeminiCevirmen(istemci=_gemini_aday({"finishReason": "STOP", "content": {"parts": [{"text": "hello"}]}}))
    assert c.cevir("merhaba") == "hello"


# --------------------------------------------------------------------------- #
# 5) dil: kısa Türkçe sözcükler + akilli_cevir kararı
# --------------------------------------------------------------------------- #
def test_turkce_mi_merhaba_gel_kedi():
    assert turkce_mi("Merhaba")
    assert turkce_mi("Gel")
    assert turkce_mi("Kedi")


def test_akilli_cevir_merhaba_cevirmeni_cagirir():
    z = _Kayitli()
    sonuc = akilli_cevir(CevirmenZinciri([z]), "Merhaba")
    assert sonuc.durum == "cevrildi"
    assert z.cagrildi


def test_akilli_cevir_ingilizce_zaten_ingilizce():
    z = _Kayitli()
    sonuc = akilli_cevir(CevirmenZinciri([z]), "Hello, how are you?")
    assert sonuc.durum == "zaten-ingilizce"
    assert not z.cagrildi


# --------------------------------------------------------------------------- #
# 6) yer tutucu tam-sayım + ZXQ/QZS çakışma koruması
# --------------------------------------------------------------------------- #
def test_geri_koy_cogalan_yer_tutucu_hata():
    with pytest.raises(KorumaHatasi):
        geri_koy("ZXQ0ZXQ ve ZXQ0ZXQ", ["parça"])


def test_geri_koy_fazladan_yer_tutucu_hata():
    with pytest.raises(KorumaHatasi):
        geri_koy("ZXQ0ZXQ ve ZXQ1ZXQ", ["parça"])


def test_maskele_zaten_zxq_olan_cakismaz():
    m, p = maskele("ZXQ0ZXQ and https://example.com")
    assert p == ["ZXQ0ZXQ", "https://example.com"]
    assert geri_koy(m, p) == "ZXQ0ZXQ and https://example.com"


def test_sozluk_zaten_qzs_olan_cakismaz():
    s = SozlukluCevirmen(_Yanki(), sozluk=[("commit at", "commit")])
    sonuc = s.cevir("QZS0QZS ve commit at")
    assert "QZS0QZS" in sonuc
    assert "commit" in sonuc


# --------------------------------------------------------------------------- #
# 7) yerel: çevrilecek parça yoksa özgün metin döner (model yüklenmez)
# --------------------------------------------------------------------------- #
def test_yerel_hepsi_ingilizce_ayni_doner(tmp_path):
    c = YerelCevirmen(str(tmp_path / "yok-klasor"))
    assert c.cevir("the cat") == "the cat"
    assert c._translator is None


# --------------------------------------------------------------------------- #
# 8) indir: .eski atomik geçiş (swap başarısızsa önceki model geri gelir)
# --------------------------------------------------------------------------- #
def _dosya_tablosu(icerikler: dict[str, bytes]) -> dict[str, tuple[int, str]]:
    return {ad: (len(ic), hashlib.sha256(ic).hexdigest()) for ad, ic in icerikler.items()}


def test_indir_swap_basarisizsa_eski_geri_gelir(tmp_path, monkeypatch):
    icerikler = {"model.bin": b"yeni"}
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu(icerikler))

    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "model.bin").write_bytes(b"eski-gecerli")

    gercek_replace = indir.os.replace

    def sahte_replace(src, dst, *a, **k):
        if str(dst).endswith("model") and str(src).endswith(".indiriliyor"):
            raise PermissionError(13, "kilitli")
        return gercek_replace(src, dst, *a, **k)

    monkeypatch.setattr(indir.os, "replace", sahte_replace)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=icerikler[request.url.path.rsplit("/", 1)[-1]])

    istemci = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(indir.IndirmeHatasi):
        indir.model_indir(hedef, istemci=istemci)

    assert (hedef / "model.bin").read_bytes() == b"eski-gecerli"
    assert not (tmp_path / "model.eski").exists()
    assert not (tmp_path / "model.indiriliyor").exists()


# --------------------------------------------------------------------------- #
# 9) indir: OSError/PermissionError IndirmeHatasi'na sarılır (kısa Türkçe mesaj)
# --------------------------------------------------------------------------- #
def test_indir_yazma_hatasi_kisa_turkce_mesaj(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", _dosya_tablosu({"model.bin": b"veri"}))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"veri")

    def sahte_open(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(builtins, "open", sahte_open)
    istemci = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(indir.IndirmeHatasi) as bilgi:
        indir.model_indir(tmp_path / "model", istemci=istemci)
    assert "yazılamadı" in str(bilgi.value)
    assert not (tmp_path / "model.indiriliyor").exists()


# --------------------------------------------------------------------------- #
# 10) gemini: model adı doğrulaması
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("model", ["../etc/passwd", "gemini model", "bad/name"])
def test_gemini_gecersiz_model_adi_hata(model):
    with pytest.raises(CeviriHatasi, match="geçersiz model adı"):
        GeminiCevirmen(model=model)


def test_gemini_gecerli_model_adi_kabul():
    c = GeminiCevirmen(model="gemini-3.5-flash-lite")
    assert c.model == "gemini-3.5-flash-lite"
