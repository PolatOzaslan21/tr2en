"""indir modülü testleri — gerçek ağa çıkmadan httpx.MockTransport ile."""
from __future__ import annotations

import hashlib

import httpx
import pytest

from ceviri_katmani.cekirdek import indir

ICERIKLER = {
    "config.json": b"abc",
    "model.bin": b"defghij",
    "shared_vocabulary.json": b"k",
    "source.spm": b"lmno",
    "target.spm": b"pq",
}


def sahte_dosyalar() -> dict[str, tuple[int, str]]:
    return {ad: (len(ic), hashlib.sha256(ic).hexdigest()) for ad, ic in ICERIKLER.items()}


def toplam_bayt() -> int:
    return sum(len(ic) for ic in ICERIKLER.values())


def istemci(icindekiler: dict[str, bytes] | None = None) -> httpx.Client:
    icindekiler = icindekiler or ICERIKLER

    def handler(request: httpx.Request) -> httpx.Response:
        ad = request.url.path.rsplit("/", 1)[-1]
        if ad in icindekiler:
            return httpx.Response(200, content=icindekiler[ad])
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_basarili_indirme_ve_atomik_tasima(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "eski.txt").write_bytes(b"eski")

    cagrilar: list[tuple[int, int]] = []
    indir.model_indir(hedef, istemci=istemci(), ilerleme=lambda a, b: cagrilar.append((a, b)))

    for ad, ic in ICERIKLER.items():
        assert (hedef / ad).read_bytes() == ic
    assert not (hedef / "eski.txt").exists()
    assert not (tmp_path / "model.indiriliyor").exists()
    assert cagrilar[-1] == (toplam_bayt(), toplam_bayt())


def test_sha_hatasi_hedef_bozulmaz_gecici_silinir(tmp_path, monkeypatch):
    dosyalar = sahte_dosyalar()
    boyut, _sha = dosyalar["model.bin"]
    dosyalar["model.bin"] = (boyut, "0" * 64)
    monkeypatch.setattr(indir, "DOSYALAR", dosyalar)

    hedef = tmp_path / "model"
    hedef.mkdir()
    (hedef / "degerli.txt").write_bytes(b"koru")

    with pytest.raises(indir.IndirmeHatasi, match="doğrulanamadı"):
        indir.model_indir(hedef, istemci=istemci())

    assert (hedef / "degerli.txt").read_bytes() == b"koru"
    assert not (hedef / "model.bin").exists()
    assert not (tmp_path / "model.indiriliyor").exists()


def test_boyut_uyusmazsa_hata(tmp_path, monkeypatch):
    dosyalar = sahte_dosyalar()
    boyut, sha = dosyalar["config.json"]
    dosyalar["config.json"] = (boyut + 1, sha)
    monkeypatch.setattr(indir, "DOSYALAR", dosyalar)

    with pytest.raises(indir.IndirmeHatasi, match="doğrulanamadı"):
        indir.model_indir(tmp_path / "model", istemci=istemci())
    assert not (tmp_path / "model.indiriliyor").exists()


def test_http_404_hata(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    istemci_404 = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(indir.IndirmeHatasi, match="indirilemedi"):
        indir.model_indir(tmp_path / "model", istemci=istemci_404)
    assert not (tmp_path / "model.indiriliyor").exists()


def test_ag_hatasi_hata(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı kurulamadı", request=request)

    istemci_hata = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(indir.IndirmeHatasi, match="indirilemedi"):
        indir.model_indir(tmp_path / "model", istemci=istemci_hata)
    assert not (tmp_path / "model.indiriliyor").exists()


def test_ilerleme_tekduze_ve_toplamda_biter(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    cagrilar: list[tuple[int, int]] = []
    indir.model_indir(tmp_path / "model", istemci=istemci(),
                      ilerleme=lambda a, b: cagrilar.append((a, b)))
    assert cagrilar
    assert cagrilar[-1] == (toplam_bayt(), toplam_bayt())
    for onceki, sonraki in zip(cagrilar, cagrilar[1:]):
        assert onceki[0] <= sonraki[0]


def test_ilerleme_mb_parcalariyla_sinirli(tmp_path, monkeypatch):
    """Büyük dosyada ilerleme ~1 MB parçada bir çağrılır (bayt başına değil)."""
    buyuk = b"x" * (2 * indir.PARCA_BOYU + 12345)
    dosyalar = {"model.bin": (len(buyuk), hashlib.sha256(buyuk).hexdigest())}
    monkeypatch.setattr(indir, "DOSYALAR", dosyalar)

    cagrilar: list[tuple[int, int]] = []
    indir.model_indir(tmp_path / "model", istemci=istemci({"model.bin": buyuk}),
                      ilerleme=lambda a, b: cagrilar.append((a, b)))
    assert 0 < len(cagrilar) <= 3


def test_model_tam_mi(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    klasor = tmp_path / "model"
    assert indir.model_tam_mi(klasor) is False

    klasor.mkdir()
    for ad, ic in ICERIKLER.items():
        (klasor / ad).write_bytes(ic)
    assert indir.model_tam_mi(klasor) is True

    (klasor / "target.spm").unlink()
    assert indir.model_tam_mi(klasor) is False


def test_model_tam_mi_boyut_uyusmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    klasor = tmp_path / "model"
    klasor.mkdir()
    for ad, ic in ICERIKLER.items():
        (klasor / ad).write_bytes(ic)
    (klasor / "config.json").write_bytes(b"x")
    assert indir.model_tam_mi(klasor) is False


def test_depo_ortam_degiskeni_kullanilir(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    monkeypatch.setenv(indir.DEPO_DEGISKENI, "benim/depom")
    urlseen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urlseen.append(str(request.url))
        ad = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=ICERIKLER[ad])

    istemci_ozel = httpx.Client(transport=httpx.MockTransport(handler))
    indir.model_indir(tmp_path / "model", istemci=istemci_ozel)

    assert urlseen and all("benim/depom" in u for u in urlseen)


def test_varsayilan_depo_kullanilir(tmp_path, monkeypatch):
    monkeypatch.setattr(indir, "DOSYALAR", sahte_dosyalar())
    monkeypatch.delenv(indir.DEPO_DEGISKENI, raising=False)
    urlseen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urlseen.append(str(request.url))
        ad = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=ICERIKLER[ad])

    istemci_ozel = httpx.Client(transport=httpx.MockTransport(handler))
    indir.model_indir(tmp_path / "model", istemci=istemci_ozel)

    assert urlseen and all(indir.MODEL_DEPOSU in u for u in urlseen)
