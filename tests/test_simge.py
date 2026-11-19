"""Simge çizimi: büyük (TR → EN balonları, koyu zemin) ve sade tepsi sürümü (yalnızca balonlar)."""
from PIL import Image

from ceviri_katmani.uygulama import simge


def _doygun_mu(px) -> bool:
    r, g, b, a = px
    return a > 200 and max(r, g, b) - min(r, g, b) > 60


def _pikseller(img):
    veri = img.convert("RGBA").tobytes()
    return [tuple(veri[i:i + 4]) for i in range(0, len(veri), 4)]


def _renkler(img):
    return [px for px in _pikseller(img) if px[3] > 200]


def _kirmizi_var(img):
    return any(r > 180 and g < 90 and b < 90 for r, g, b, _ in _renkler(img))


def _mavi_var(img):
    return any(b > 180 and r < 90 for r, g, b, _ in _renkler(img))


def test_buyuk_simge_boyut_ve_koseler_seffaf():
    img = simge.buyuk_simge(True, 256)
    assert img.size == (256, 256) and img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0  # köşe şeffaf (beyaz değil)
    assert img.getpixel((128, 8))[3] == 255  # koyu zemin dolu


def test_buyuk_simge_aktif_kirmizi_ve_mavi_balon():
    img = simge.buyuk_simge(True, 256)
    assert _kirmizi_var(img) and _mavi_var(img)


def test_sade_simge_zeminsiz_ve_iki_renkli():
    img = simge.sade_simge(True, 64)
    assert img.size == (64, 64)
    assert img.getpixel((0, 63))[3] == 0 or img.getpixel((63, 0))[3] == 0
    assert _kirmizi_var(img) and _mavi_var(img)


def test_pasif_simgeler_gri():
    for img in (simge.buyuk_simge(False, 128), simge.sade_simge(False, 64)):
        assert not any(_doygun_mu(px) for px in _pikseller(img)), "pasifte renkli piksel olmamalı"


def test_ico_kucuk_boyutlarda_sade_buyuklerde_buyuk(tmp_path):
    yol = tmp_path / "tr2en.ico"
    simge.ico_kaydet(yol)
    ico = Image.open(yol)
    boyutlar = ico.info["sizes"]
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)} <= set(boyutlar)
    ico.size = (16, 16)
    kucuk = ico.copy().convert("RGBA")
    ico.size = (256, 256)
    buyuk = ico.copy().convert("RGBA")
    assert kucuk.getpixel((8, 0))[3] < 200 or kucuk.getpixel((0, 8))[3] < 200  # sade: koyu zemin yok
    assert buyuk.getpixel((128, 8))[3] == 255  # büyük: koyu zemin var
