"""Tuş yutma: kısayolun ana tuşu programa gitmez; seçim yoksa programa geri gönderilir."""
import queue

import pytest

from ceviri_katmani.uygulama.kisayol_kayit import kisayol_vk_coz

KD, KU, SKD, SKU = 0x100, 0x101, 0x104, 0x105
CTRL, SHIFT, ALT, P, SPACE = 0xA2, 0xA0, 0xA4, 0x50, 0x20


@pytest.mark.parametrize("k,beklenen", [
    ("<ctrl>+p", (frozenset({"ctrl"}), 0x50, "p")),
    ("<ctrl>+<shift>+<space>", (frozenset({"ctrl", "shift"}), 0x20, "space")),
    ("<ctrl>+<f9>", (frozenset({"ctrl"}), 0x78, "f9")),
    ("<alt>+5", (frozenset({"alt"}), 0x35, "5")),
    ("<shift>+<alt>+<page_up>", (frozenset({"shift", "alt"}), 0x21, "page_up")),
])
def test_vk_coz(k, beklenen):
    assert kisayol_vk_coz(k) == beklenen


@pytest.mark.parametrize("k", ["p", "<ctrl>+<tab>", "<ctrl>+p+q", "<cmd>+p", ""])
def test_vk_coz_cozulemeyen(k):
    assert kisayol_vk_coz(k) is None


def _d(kisayol="<ctrl>+p", aktif=True, terminal=False):
    from ceviri_katmani.uygulama.tetik import Dinleyici
    d = Dinleyici(kisayol=kisayol, tetik=";en", kisayol_cb=lambda: None, tetik_cb=lambda *a: None,
                  terminal_mi_cb=lambda: terminal, yut_cb=lambda: aktif)
    return d


def _isler(d):
    out = []
    while True:
        try:
            out.append(d._kuyruk.get_nowait())
        except queue.Empty:
            return out


def test_ctrl_p_yutulur_ve_kisayol_isi_kuyruga_girer():
    d = _d()
    assert d._yutulmali_mi(KD, CTRL) is False      # Ctrl programa gider
    assert d._yutulmali_mi(KD, P) is True          # P yutulur
    assert d._yutulmali_mi(KD, P) is True          # basılı tutma tekrarı da yutulur, iş tekrar eklenmez
    assert d._yutulmali_mi(KU, P) is True          # bırakma da yutulur
    assert d._yutulmali_mi(KU, CTRL) is False
    assert _isler(d) == [("kisayol",)]
    assert d._bekleyen_geri == (frozenset({"ctrl"}), P, "p")


def test_fazla_degistiricide_yutulmaz():
    d = _d()
    d._yutulmali_mi(KD, CTRL); d._yutulmali_mi(KD, SHIFT)
    assert d._yutulmali_mi(KD, P) is False  # Ctrl+Shift+P bizim kısayol değil
    assert _isler(d) == []


def test_degistiricisiz_harf_yutulmaz():
    d = _d()
    assert d._yutulmali_mi(KD, P) is False


def test_duraklatilmisken_ve_terminalde_yutulmaz():
    for d in (_d(aktif=False), _d(terminal=True)):
        d._yutulmali_mi(KD, CTRL)
        assert d._yutulmali_mi(KD, P) is False
        assert _isler(d) == []


def test_kayit_modunda_yutulmaz():
    d = _d()
    d.kayit_baslat(lambda m, t: None)
    d._yutulmali_mi(KD, CTRL)
    assert d._yutulmali_mi(KD, P) is False


def test_yut_cb_yoksa_eski_davranis():
    from ceviri_katmani.uygulama.tetik import Dinleyici
    d = Dinleyici(kisayol="<ctrl>+p", tetik=";en", kisayol_cb=lambda: None, tetik_cb=lambda *a: None,
                  terminal_mi_cb=lambda: False)
    d._yutulmali_mi(KD, CTRL)
    assert d._yutulmali_mi(KD, P) is False


def test_alt_kisayolda_bos_tus_gonderilir(monkeypatch):
    d = _d("<alt>+j")
    gonderilen = []
    monkeypatch.setattr(d, "_bos_tus_gonder", lambda: gonderilen.append(1))
    d._yutulmali_mi(SKD, ALT)
    assert d._yutulmali_mi(SKD, 0x4A) is True
    import time; time.sleep(0.05)
    assert gonderilen == [1]


def test_filtre_hatasi_klavyeyi_bozmaz(monkeypatch):
    d = _d()
    monkeypatch.setattr(d, "_yutulmali_mi", lambda *a: 1 / 0)
    veri = type("V", (), {"flags": 0, "vkCode": P})()
    assert d._win32_event_filter(KD, veri) is True


def test_geri_gonder_degistiricilerle_basar(monkeypatch):
    import pynput.keyboard as kbm
    olaylar = []

    class SahteKontrol:
        def press(self, k): olaylar.append(("bas", k))
        def release(self, k): olaylar.append(("birak", k))
        def pressed(self, *ks):
            import contextlib
            @contextlib.contextmanager
            def cm():
                for k in ks: olaylar.append(("bas", k))
                yield
                for k in reversed(ks): olaylar.append(("birak", k))
            return cm()

    monkeypatch.setattr(kbm, "Controller", SahteKontrol)
    d = _d("<ctrl>+<shift>+<space>")
    assert d.geri_gonder() is False  # bekleyen yok
    d._yutulmali_mi(KD, CTRL); d._yutulmali_mi(KD, SHIFT); d._yutulmali_mi(KD, SPACE)
    assert d.geri_gonder() is True
    assert olaylar == [("bas", kbm.Key.ctrl), ("bas", kbm.Key.shift), ("bas", kbm.Key.space),
                       ("birak", kbm.Key.space), ("birak", kbm.Key.shift), ("birak", kbm.Key.ctrl)]
    assert d.geri_gonder() is False  # bir kez


def test_normal_yoldan_tetik_bekleyeni_siler():
    d = _d()
    d._bekleyen_geri = (frozenset({"ctrl"}), P, "p")
    d._kisayol_etkin()
    assert d._bekleyen_geri is None


# ---- uygulama: seçim yoksa geri gönder ----

def _uyg(kisayol, secim=None, geri=True):
    from tests.test_denetim1_uygulama import _uygulama
    uyg, pano, pencere, zincir, calls = _uygulama(secim=secim)
    uyg.ayarlar["kisayol"] = kisayol
    gonderilen = []

    class D:
        def geri_gonder(self):
            gonderilen.append(1)
            return geri
    uyg._dinleyici = D()
    return uyg, calls, gonderilen


def test_kendi_kisayolda_secim_yoksa_geri_gonderir_bildirim_yok():
    uyg, calls, gonderilen = _uyg("<ctrl>+p", secim=None)
    uyg._kisayol_isle()
    assert gonderilen == [1]
    assert not any(c[0] == "Seçim yok" for c in calls)


def test_varsayilan_kisayolda_secim_yoksa_bildirim_kalir():
    uyg, calls, gonderilen = _uyg("<ctrl>+<shift>+<space>", secim=None)
    uyg._kisayol_isle()
    assert gonderilen == [1]
    assert any(c[0] == "Seçim yok" for c in calls)


def test_yutulmamissa_secim_yok_bildirimi_gelir():
    uyg, calls, _ = _uyg("<ctrl>+p", secim=None, geri=False)
    uyg._kisayol_isle()
    assert any(c[0] == "Seçim yok" for c in calls)


def test_secim_varsa_geri_gonderilmez():
    uyg, calls, gonderilen = _uyg("<ctrl>+p", secim="merhaba dünya")
    uyg._kisayol_isle()
    assert gonderilen == []


def test_dinleyiciye_yut_cb_verilir():
    from tests.test_denetim1_uygulama import _uygulama
    uyg, *_ = _uygulama()
    uyg._dinleyici_kur()
    yut = uyg._dinleyici.kwargs["yut_cb"]
    uyg._aktif = True
    assert yut() is True
    uyg._aktif = False
    assert yut() is False


# ---- uyarlanır pano beklemesi ----

def test_kopya_beklemesi_programa_gore_kisalir():
    from tests.test_denetim1_uygulama import _uygulama
    uyg, *_ = _uygulama()
    assert uyg._kopya_bekleme_ms("claude.exe") == 150          # bilinen hızlı program: hazır değer
    assert uyg._kopya_bekleme_ms("bilinmeyen.exe") == 300      # bilinmeyen: tam bekleme
    uyg._kopya_suresi_kaydet("claude.exe", 20)
    assert uyg._kopya_bekleme_ms("claude.exe") == 120          # hızlı program: en az 120 ms
    uyg._kopya_suresi_kaydet("claude.exe", 60)
    assert uyg._kopya_bekleme_ms("claude.exe") == 220          # en yavaşın 3 katı + 40
    uyg._kopya_suresi_kaydet("winword.exe", 250)
    assert uyg._kopya_bekleme_ms("winword.exe") == 300         # üst sınır
    assert uyg._kopya_bekleme_ms("excel.exe") == 300           # diğer program etkilenmez


def test_basarili_kopyalama_suresi_kaydedilir_ve_bekleme_iletilir():
    from tests.test_denetim1_uygulama import _uygulama
    uyg, pano, *_ = _uygulama(secim="merhaba dünya")
    beklemeler = []
    asil = pano.secimi_kopyala
    pano.secimi_kopyala = lambda bekle_ms=300: (beklemeler.append(bekle_ms), asil(bekle_ms))[1]
    uyg._kisayol_isle()
    uyg._kisayol_isle()
    assert beklemeler[0] == 150 and beklemeler[1] == 120  # notepad: hazır değer, sonra öğrenilen


def test_kopya_sureleri_diske_yazilir_ve_okunur(tmp_path):
    from tests.test_denetim1_uygulama import _uygulama
    yol = tmp_path / "kopya_sureleri.json"
    uyg, *_ = _uygulama()
    uyg.ayarlar["kopya_sureleri_yolu"] = str(yol)
    uyg._kopya_suresi_kaydet("winword.exe", 80)
    uyg._kopya_suresi_kaydet("winword.exe", 50)   # daha hızlı: en yavaş değişmez
    yeni, *_ = _uygulama()
    yeni.ayarlar["kopya_sureleri_yolu"] = str(yol)
    assert yeni._kopya_bekleme_ms("winword.exe") == 280
    assert "merhaba" not in yol.read_text(encoding="utf-8")


def test_bozuk_kopya_dosyasi_yok_sayilir(tmp_path):
    from tests.test_denetim1_uygulama import _uygulama
    yol = tmp_path / "k.json"
    yol.write_text("{bozuk", encoding="utf-8")
    uyg, *_ = _uygulama()
    uyg.ayarlar["kopya_sureleri_yolu"] = str(yol)
    assert uyg._kopya_bekleme_ms("claude.exe") == 150
