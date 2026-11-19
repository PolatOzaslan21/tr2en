"""Pencere bağlantısı testleri (brif-v02-3): başlatma bayrakları, ikinci kopya,
ilk açılış sihirbazı, WebView2 yedekleri, ayar yenileme, "--arka" göçü, tepsi.

Gerçek süreç, pencere, kayıt defteri, Windows event'i, klavye kancası, tarayıcı
ve bildirim YOKTUR; hepsi sahtedir/enjekte edilir.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pystray
import pytest

from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.uygulama import ana, arkaplan, otomatik_baslat, pencere_sureci, sinyal, tek_ornek
from ceviri_katmani.uygulama import ayarlar as ayar_modulu
from ceviri_katmani.uygulama import bildirim as bildirim_mod
from ceviri_katmani.uygulama import gizlilik as gizlilik_mod
from ceviri_katmani.uygulama import model_indirme, tepsi as tepsi_mod, tetik as tetik_mod
from ceviri_katmani.uygulama.pencere_api import PencereApi
from ceviri_katmani.uygulama.tepsi import Tepsi


def bekle(kosul, sure: float = 2.0) -> bool:
    son = time.time() + sure
    while time.time() < son:
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


# ---- sahteler ----


class SahteSurec:
    """subprocess.Popen'ın döndürdüğü süreç nesnesinin sahtesi."""

    def __init__(self, kod: int = 0, calisiyor: bool = False) -> None:
        self.kod = kod
        self.calisiyor = calisiyor
        self.terminated = 0
        self.komut: list | None = None
        self.kw: dict | None = None

    def wait(self, timeout=None):
        if self.calisiyor:
            raise subprocess.TimeoutExpired(self.komut or [], timeout)
        return self.kod

    def poll(self):
        return None if self.calisiyor else self.kod

    def terminate(self) -> None:
        self.terminated += 1
        self.calisiyor = False


class SahtePopen:
    """subprocess.Popen sahtesi; her çağrıda yeni SahteSurec üretir."""

    def __init__(self, kod: int = 0, calisiyor: bool = False) -> None:
        self.kod = kod
        self.calisiyor = calisiyor
        self.cagrilar: list[tuple[list, dict]] = []
        self.surecler: list[SahteSurec] = []

    def __call__(self, komut, **kw) -> SahteSurec:
        surec = SahteSurec(kod=self.kod, calisiyor=self.calisiyor)
        surec.komut, surec.kw = list(komut), kw
        self.cagrilar.append((list(komut), kw))
        self.surecler.append(surec)
        return surec


class SahteReg:
    """winreg benzeri sahte nesne; gerçek kayıt defterine dokunmaz."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.degerler: dict[str, str] = {}
        self.aciklar: list[tuple[str, str]] = []
        self.kapatilan: list[object] = []

    def OpenKey(self, kok, yol, _reserved=0, _erisim=0):
        self.aciklar.append((kok, yol))
        return object()

    def QueryValueEx(self, _anahtar, ad):
        if ad not in self.degerler:
            raise FileNotFoundError(ad)
        return (self.degerler[ad], self.REG_SZ)

    def SetValueEx(self, _anahtar, ad, _reserved, tur, deger):
        assert tur == self.REG_SZ
        self.degerler[ad] = deger

    def DeleteValue(self, _anahtar, ad):
        if ad not in self.degerler:
            raise FileNotFoundError(ad)
        del self.degerler[ad]

    def CloseKey(self, anahtar):
        self.kapatilan.append(anahtar)


class FakeZincir:
    def __init__(self, ayar: dict | None = None) -> None:
        self.ayar = dict(ayar or {})

    def cevir(self, metin: str, kaynak: str = "tr", hedef: str = "en") -> str:
        return metin

    @property
    def son_kullanilan(self) -> str:
        return "sahte:test"


class SahteDinleyici:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.durduruldu = 0

    def baslat(self) -> None:
        pass

    def durdur(self) -> None:
        self.durduruldu += 1


# ---- ana.main için dünya ----


@pytest.fixture
def dunya(monkeypatch, tmp_path):
    """main()'in tüm dış bağımlılıklarını sahtelerle değiştirir."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    ana._pencere_surecleri.clear()
    kayit = SimpleNamespace(
        bildirimler=[],
        sinyaller=[],
        gonder_doner=True,
        kilit_var=True,
        kilit_alinan=[],
        kilit_birakilan=[],
        goc_cagrilari=[],
        gizlilik_cagrilar=[],
        gizlilik_secim="bulut",
        zincir_cagrilar=[],
        zincir_hatasi=None,
        dinleyiciler=[],
        bekleyici=None,
        uygulama=None,
        tepsi=None,
        calistirildi=False,
        calistir_boyunca=None,
        indirme=[],
        acilanlar=[],
        popen=SahtePopen(),
    )

    def kilit_al(*_a, **_k):
        kayit.kilit_alinan.append(1)
        return object() if kayit.kilit_var else None

    def bildir(*args, **_k):
        kayit.bildirimler.append(args)

    def gonder(ad, **_k):
        kayit.sinyaller.append(ad)
        return kayit.gonder_doner

    class SahteBekleyici:
        def __init__(self, geri_cagrilar, **_k):
            kayit.bekleyici = SimpleNamespace(
                geri_cagrilar=dict(geri_cagrilar), baslatildi=0, durduruldu=0
            )

        def baslat(self):
            kayit.bekleyici.baslatildi += 1

        def durdur(self):
            kayit.bekleyici.durduruldu += 1

    def gizlilik_sor(**_k):
        kayit.gizlilik_cagrilar.append(1)
        return kayit.gizlilik_secim

    def zincir_kur_v2(ayar, _saglayici, korumasiz=False):
        kayit.zincir_cagrilar.append(dict(ayar))
        if kayit.zincir_hatasi is not None and ayar.get("cevirmen") != "yerel":
            raise kayit.zincir_hatasi
        return FakeZincir(ayar)

    class SahteTepsi:
        def __init__(self, arayuz):
            kayit.uygulama = arayuz
            kayit.tepsi = self
            self.durdu = 0
            self.guncellemeler = 0

        def calistir(self):
            kayit.calistirildi = True
            if kayit.calistir_boyunca is not None:
                kayit.calistir_boyunca()

        def durdur(self):
            self.durdu += 1

        def guncelle(self):
            self.guncellemeler += 1

        def bildirim(self, _baslik, _mesaj=""):
            pass

    class KayitliDinleyici(SahteDinleyici):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            kayit.dinleyiciler.append(self)

    monkeypatch.setattr(tek_ornek, "kilit_al", kilit_al)
    monkeypatch.setattr(tek_ornek, "kilit_birak", lambda k: kayit.kilit_birakilan.append(k))
    monkeypatch.setattr(otomatik_baslat, "goc_uygula", lambda **_k: kayit.goc_cagrilari.append(1))
    monkeypatch.setattr(bildirim_mod, "bildir", bildir)
    monkeypatch.setattr(sinyal, "gonder", gonder)
    monkeypatch.setattr(sinyal, "Bekleyici", SahteBekleyici)
    monkeypatch.setattr(gizlilik_mod, "gizlilik_sor", gizlilik_sor)
    monkeypatch.setattr(tetik_mod, "Dinleyici", KayitliDinleyici)
    monkeypatch.setattr(tepsi_mod, "Tepsi", SahteTepsi)
    monkeypatch.setattr(model_indirme, "gerekirse_arkaplanda_indir", lambda _b: kayit.indirme.append(1))
    monkeypatch.setattr(ana, "zincir_kur_v2", zincir_kur_v2)
    monkeypatch.setattr(ana, "_pencere_popen", kayit.popen)
    monkeypatch.setattr(os, "startfile", lambda yol: kayit.acilanlar.append(str(yol)))
    yield kayit
    ana._pencere_surecleri.clear()


# ---- 1) argv'nin yeniden başlatmada korunması ----


def test_arkaplan_argv_yeniden_baslatmada_korunur(monkeypatch):
    monkeypatch.delenv(arkaplan.ORTAM, raising=False)
    cagri = {}

    def sahte_popen(komut, **kw):
        cagri["komut"], cagri["kw"] = komut, kw

    assert arkaplan.main(["--arka", "x"], popen=sahte_popen) == 0
    assert cagri["komut"][1:] == ["-m", "ceviri_katmani.uygulama", "--arka", "x"]


def test_arkaplan_argv_none_sys_argv_kullanilir(monkeypatch):
    monkeypatch.delenv(arkaplan.ORTAM, raising=False)
    monkeypatch.setattr(sys, "argv", ["tr2en", "--arka"])
    cagri = {}

    def sahte_popen(komut, **kw):
        cagri["komut"] = komut

    assert arkaplan.main(popen=sahte_popen) == 0
    assert cagri["komut"][1:] == ["-m", "ceviri_katmani.uygulama", "--arka"]


# ---- 2) --ayarlar dalı ----


def test_arkaplan_ayarlar_dali_pencere_surecini_calistirir(monkeypatch):
    cagrilar: list[list] = []
    monkeypatch.setattr(
        pencere_sureci, "calistir", lambda argv=None, **_k: cagrilar.append(list(argv)) or 3
    )
    kod = arkaplan.main(
        ["--ayarlar", "--sihirbaz"], popen=lambda *_a, **_k: pytest.fail("yeniden başlatmamalı")
    )
    assert kod == 3
    assert cagrilar == [["--ayarlar", "--sihirbaz"]]


def test_arkaplan_ayarlar_dali_onceliklidir(monkeypatch):
    monkeypatch.setenv(arkaplan.ORTAM, "1")
    monkeypatch.setattr(pencere_sureci, "calistir", lambda argv=None, **_k: 4)
    import ceviri_katmani.uygulama.ana as ana_mod

    monkeypatch.setattr(ana_mod, "main", lambda argv=None: pytest.fail("ana.main çalışmamalı"))
    assert arkaplan.main(["--ayarlar"]) == 4


# ---- pencere_ac yardımcıları ----


def test_pencere_ac_komut_ve_bayraklar(monkeypatch):
    popen = SahtePopen()
    monkeypatch.delattr(sys, "frozen", raising=False)
    surec = ana.pencere_ac(yedek=lambda: None, popen=popen)
    komut, kw = popen.cagrilar[0]
    assert komut == [sys.executable, "-m", "ceviri_katmani.uygulama", "--ayarlar"]
    assert kw["creationflags"] & ana.CREATE_NO_WINDOW
    assert kw["stdin"] is subprocess.DEVNULL
    assert kw["stdout"] is subprocess.DEVNULL
    assert kw["stderr"] is subprocess.DEVNULL
    assert surec is popen.surecler[0]


def test_pencere_ac_sihirbaz_bayragi(monkeypatch):
    popen = SahtePopen()
    ana.pencere_ac(sihirbaz=True, yedek=lambda: None, popen=popen)
    assert popen.cagrilar[0][0][-1] == "--sihirbaz"


def test_pencere_ac_frozen_komutu(monkeypatch):
    popen = SahtePopen()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    ana.pencere_ac(yedek=lambda: None, popen=popen)
    assert popen.cagrilar[0][0] == [sys.executable, "--ayarlar"]


def test_pencere_ac_kod2_yedek_cagirir():
    cagrilar: list[int] = []
    popen = SahtePopen(kod=2)
    ana.pencere_ac(yedek=lambda: cagrilar.append(1), popen=popen)
    assert bekle(lambda: cagrilar == [1])


def test_pencere_ac_kod0_yedek_cagirmaz():
    cagrilar: list[int] = []
    popen = SahtePopen(kod=0)
    ana.pencere_ac(yedek=lambda: cagrilar.append(1), popen=popen)
    time.sleep(0.05)
    assert cagrilar == []


def test_pencere_ac_hala_calisiyorsa_yedek_yok():
    cagrilar: list[int] = []
    popen = SahtePopen(calisiyor=True)
    ana.pencere_ac(yedek=lambda: cagrilar.append(1), popen=popen)
    time.sleep(0.05)
    assert cagrilar == []


def test_pencere_ac_varsayilan_yedek_bildirim_ve_ayar_dosyasi(monkeypatch):
    bildirimler: list = []
    acilanlar: list[str] = []
    monkeypatch.setattr(bildirim_mod, "bildir", lambda *a, **_k: bildirimler.append(a))
    monkeypatch.setattr(os, "startfile", lambda yol: acilanlar.append(str(yol)))
    popen = SahtePopen(kod=2)
    ana.pencere_ac(popen=popen)
    assert bekle(lambda: acilanlar and bildirimler)
    assert bildirimler[0][0] == "Ayar penceresi açılamadı"
    assert "WebView2" in bildirimler[0][1]
    assert acilanlar[0].endswith("ayarlar.toml")


def test_pencere_surecleri_kapat_calisani_terminate():
    calisan = SahteSurec(calisiyor=True)
    bitmis = SahteSurec(kod=0)
    ana._pencere_surecleri.extend([calisan, bitmis])
    ana.pencere_surecleri_kapat()
    assert calisan.terminated == 1
    assert bitmis.terminated == 0
    assert ana._pencere_surecleri == []


# ---- 3) ikinci kopya ----


def test_ikinci_kopya_goster_sinyali_gonderilir(dunya):
    dunya.kilit_var = False
    assert ana.main([]) == 0
    assert dunya.sinyaller == ["goster"]
    assert [b[0] for b in dunya.bildirimler] == []


def test_ikinci_kopya_gonderilemezse_eski_bildirim(dunya):
    dunya.kilit_var = False
    dunya.gonder_doner = False
    assert ana.main([]) == 0
    assert dunya.sinyaller == ["goster"]
    assert dunya.bildirimler[0][0] == "tr2en zaten çalışıyor"


def test_ikinci_kopya_arka_varsa_sinyal_yok(dunya):
    dunya.kilit_var = False
    assert ana.main(["--arka"]) == 0
    assert dunya.sinyaller == []
    assert dunya.bildirimler == []


# ---- 4) ilk açılış: MessageBox yerine sihirbaz + yerel zorlaması ----


def test_ilk_acilis_mbox_yerine_sihirbaz_ve_yerel_zorlamasi(dunya):
    assert ana.main([]) == 0
    assert dunya.gizlilik_cagrilar == []
    assert dunya.popen.cagrilar
    komut, _kw = dunya.popen.cagrilar[0]
    assert komut[-1] == "--sihirbaz"
    assert komut[-2] == "--ayarlar"
    assert dunya.uygulama.cevirmen() == "yerel"
    assert dunya.uygulama.ayarlar["yerel_zorlamasi"] is True
    assert dunya.zincir_cagrilar[0]["cevirmen"] == "yerel"
    dosya, _ = ayar_modulu.yukle()
    assert dosya["cevirmen"] == "bulut"  # dosyadaki değer değişmedi
    assert dosya["gizlilik_onayi"] is False


# ---- 5) pencere 2 koduyla biterse yedekler ----


def test_ilk_acilis_yedek_gizlilik_sor_onaylar(dunya):
    dunya.popen.kod = 2
    dunya.gizlilik_secim = "bulut"
    assert ana.main([]) == 0
    assert bekle(lambda: dunya.gizlilik_cagrilar == [1])
    assert bekle(lambda: dunya.uygulama.cevirmen() == "bulut")
    assert dunya.uygulama.ayarlar["yerel_zorlamasi"] is False
    assert any(k.get("cevirmen") == "bulut" for k in dunya.zincir_cagrilar[1:])
    dosya, _ = ayar_modulu.yukle()
    assert dosya["gizlilik_onayi"] is True
    assert dosya["cevirmen"] == "bulut"


def test_ilk_acilis_yedek_gizlilik_iptal_kapatir(dunya):
    dunya.popen.kod = 2
    dunya.gizlilik_secim = None
    assert ana.main([]) == 0
    assert bekle(lambda: dunya.gizlilik_cagrilar == [1])
    assert bekle(lambda: dunya.tepsi.durdu >= 1)
    dosya, _ = ayar_modulu.yukle()
    assert dosya["gizlilik_onayi"] is False


def test_sonraki_acilis_yedek_ayar_dosyasi_acilir(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    dunya.popen.kod = 2
    assert ana.main([]) == 0
    assert bekle(lambda: dunya.acilanlar)
    assert dunya.gizlilik_cagrilar == []
    assert any(b[0] == "Ayar penceresi açılamadı" for b in dunya.bildirimler)
    assert any("WebView2" in b[1] for b in dunya.bildirimler if len(b) > 1)
    assert dunya.acilanlar[0].endswith("ayarlar.toml")


# ---- sonraki açılışlar ve --arka ----


def test_sonraki_acilis_pencere_acilir(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    assert ana.main([]) == 0
    assert dunya.popen.cagrilar
    assert "--sihirbaz" not in dunya.popen.cagrilar[0][0]


def test_arka_pencere_acilmaz(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    assert ana.main(["--arka"]) == 0
    assert dunya.popen.cagrilar == []
    assert dunya.calistirildi is True


def test_baslangicta_goc_uygula_cagrilir(dunya):
    assert ana.main([]) == 0
    assert len(dunya.goc_cagrilari) == 1


# ---- 6) yenile sinyali ----


def test_yenile_zincir_kisayol_sona_bosluk_guncellenir(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    beklenecek = {
        "kisayol": "<ctrl>+<shift>+y",
        "sona_bosluk": False,
        "gemini_model": "gemini-yeni",
        "ozet_kaydi": True,
        "gizlilik_onayi": True,
    }

    def boyunca():
        ayar_modulu.kaydet(beklenecek, ayar_modulu.ayar_yolu())
        dunya.bekleyici.geri_cagrilar["yenile"]()

    dunya.calistir_boyunca = boyunca
    assert ana.main([]) == 0
    assert len(dunya.zincir_cagrilar) == 2
    assert dunya.zincir_cagrilar[1]["gemini_model"] == "gemini-yeni"
    assert dunya.uygulama.kisayol_simdiki() == "<ctrl>+<shift>+y"
    assert dunya.uygulama.ayarlar["sona_bosluk"] is False
    assert dunya.tepsi.guncellemeler >= 1
    assert len(dunya.dinleyiciler) == 2  # kisayol_sec dinleyiciyi yeniden kurdu


def test_yenile_zincir_hatasinda_dahiliye_duser(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())

    def boyunca():
        ayar_modulu.kaydet(
            {"gizlilik_onayi": True, "gemini_model": "bozuk"}, ayar_modulu.ayar_yolu()
        )
        dunya.zincir_hatasi = CeviriHatasi("model adı girilmedi")
        dunya.bekleyici.geri_cagrilar["yenile"]()

    dunya.calistir_boyunca = boyunca
    assert ana.main([]) == 0
    assert any(b[0] == "Çeviri ayarı eksik" for b in dunya.bildirimler)
    assert dunya.uygulama.cevirmen() == "yerel"
    assert dunya.uygulama.zincir.ayar["cevirmen"] == "yerel"


def test_yenile_yukleme_hatasinda_cokmez(dunya, monkeypatch):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())

    def bozuk(_yol=None):
        raise RuntimeError("dosya okunamadı")

    def boyunca():
        monkeypatch.setattr(ayar_modulu, "yukle", bozuk)
        dunya.bekleyici.geri_cagrilar["yenile"]()

    dunya.calistir_boyunca = boyunca
    assert ana.main([]) == 0  # uygulama çökmez
    assert any(b[0] == "Ayarlar uygulanamadı" for b in dunya.bildirimler)


def test_ayarlari_yenile_beklenmeyen_hatada_cokmez():
    calls: list[tuple] = []

    def bozuk_zincir(_ad):
        raise RuntimeError("pat")

    uyg = ana.Uygulama(object(), object(), FakeZincir(), lambda *a: calls.append(a), {})
    uyg.ayarlar["zincir_uretici"] = bozuk_zincir
    uyg.ayarlari_yenile({"cevirmen": "bulut", "gizlilik_onayi": True})
    assert any(c[0] == "Ayarlar uygulanamadı" for c in calls)


def test_ayarlari_yenile_zorlama_kalkar():
    calls: list[tuple] = []

    def zincir_uretici(ad):
        return FakeZincir({"cevirmen": ad})

    uyg = ana.Uygulama(
        object(), object(), FakeZincir(), lambda *a: calls.append(a),
        {"cevirmen": "yerel", "yerel_zorlamasi": True, "zincir_uretici": zincir_uretici},
    )
    uyg.ayarlari_yenile({"cevirmen": "bulut", "gizlilik_onayi": False})
    assert uyg.ayarlar["yerel_zorlamasi"] is True
    assert uyg.cevirmen() == "yerel"
    uyg.ayarlari_yenile({"cevirmen": "bulut", "gizlilik_onayi": True})
    assert uyg.ayarlar["yerel_zorlamasi"] is False
    assert uyg.cevirmen() == "bulut"
    assert uyg.zincir.ayar["cevirmen"] == "bulut"


# ---- 7) cikis sinyali ----


def test_cikis_sinyali_tepsiyi_durdurur(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())

    def boyunca():
        dunya.bekleyici.geri_cagrilar["cikis"]()

    dunya.calistir_boyunca = boyunca
    assert ana.main([]) == 0
    assert dunya.tepsi.durdu == 1
    assert dunya.bekleyici.durduruldu == 1


def test_goster_sinyali_pencere_acar(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())

    def boyunca():
        dunya.bekleyici.geri_cagrilar["goster"]()

    dunya.calistir_boyunca = boyunca
    assert ana.main([]) == 0
    assert len(dunya.popen.cagrilar) == 2  # açılış + sinyal
    assert "--sihirbaz" not in dunya.popen.cagrilar[-1][0]


# ---- 8) kapanışta pencere sürecinin sonlandırılması ----


def test_kapanista_calisan_pencere_sureci_terminate(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    dunya.popen.calisiyor = True
    assert ana.main([]) == 0
    assert dunya.popen.surecler
    assert all(s.terminated == 1 for s in dunya.popen.surecler)


def test_kapanista_bitmis_pencere_sureci_dokunulmaz(dunya):
    ayar_modulu.kaydet({"gizlilik_onayi": True}, ayar_modulu.ayar_yolu())
    dunya.popen.kod = 0
    assert ana.main([]) == 0
    assert all(s.terminated == 0 for s in dunya.popen.surecler)


# ---- 9-10) komut() ve --arka göçü ----


def test_komut_arka_bayragi_tasiyor():
    assert otomatik_baslat.komut().endswith(" --arka")


def test_komut_frozen_arka(tmp_path, monkeypatch):
    exe = tmp_path / "tr2en.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert otomatik_baslat.komut() == f'"{exe}" --arka'


def test_goc_bayraksiz_deger_yeniden_yazilir():
    reg = SahteReg()
    reg.degerler[otomatik_baslat.DEGER_ADI] = '"C:\\eski\\tr2en.exe"'
    assert otomatik_baslat.goc_uygula(_reg=reg) is True
    assert reg.degerler[otomatik_baslat.DEGER_ADI] == otomatik_baslat.komut()
    assert "--arka" in reg.degerler[otomatik_baslat.DEGER_ADI]


def test_goc_bayragi_varsa_dokunmaz():
    reg = SahteReg()
    eski = '"C:\\eski\\tr2en.exe" --arka'
    reg.degerler[otomatik_baslat.DEGER_ADI] = eski
    assert otomatik_baslat.goc_uygula(_reg=reg) is False
    assert reg.degerler[otomatik_baslat.DEGER_ADI] == eski


def test_goc_deger_yoksa_yazmaz():
    reg = SahteReg()
    assert otomatik_baslat.goc_uygula(_reg=reg) is False
    assert reg.degerler == {}


# ---- 11) tepside "Ayarları aç" en üstte ve tek default ----


class MinimalArayuz:
    def bulut_adi(self):
        return "Google Gemini"

    def yerel_adi(self):
        return "dahili model"


def test_tepsi_ayarlari_ac_en_ustte_tek_default():
    tepsi = Tepsi(MinimalArayuz())
    ogeler = tepsi.menu_ogeleri()
    assert ogeler[0].text == "Ayarları aç"
    varsayilanlar = [o for o in ogeler if o is not pystray.Menu.SEPARATOR and o.default]
    assert [o.text for o in varsayilanlar] == ["Ayarları aç"]
    adlar = [o.text for o in ogeler if o is not pystray.Menu.SEPARATOR]
    assert "Ayarlar dosyasını aç" not in adlar


# ---- PencereApi: otomatik_baslat_durum / otomatik_baslat_ayarla ----


class SahteOtomatikBaslat:
    def __init__(self, acik: bool = False, hata: Exception | None = None) -> None:
        self.acik = acik
        self.hata = hata
        self.cagrilar: list[str] = []

    def acik_mi(self, **_k):
        if self.hata:
            raise self.hata
        return self.acik

    def ac(self, **_k):
        if self.hata:
            raise self.hata
        self.cagrilar.append("ac")
        self.acik = True

    def kapat(self, **_k):
        if self.hata:
            raise self.hata
        self.cagrilar.append("kapat")
        self.acik = False


def test_pencere_api_otomatik_baslat_durum():
    ob = SahteOtomatikBaslat(acik=True)
    api = PencereApi(otomatik_baslat=ob)
    assert api.otomatik_baslat_durum() == {"ok": True, "acik": True}
    ob.acik = False
    assert api.otomatik_baslat_durum() == {"ok": True, "acik": False}


def test_pencere_api_otomatik_baslat_ayarla():
    ob = SahteOtomatikBaslat()
    api = PencereApi(otomatik_baslat=ob)
    assert api.otomatik_baslat_ayarla(True) == {"ok": True}
    assert ob.cagrilar == ["ac"]
    assert api.otomatik_baslat_ayarla(False) == {"ok": True}
    assert ob.cagrilar == ["ac", "kapat"]


def test_pencere_api_otomatik_baslat_hata_firlatmaz():
    ob = SahteOtomatikBaslat(hata=RuntimeError("erisim yok"))
    api = PencereApi(otomatik_baslat=ob)
    sonuc = api.otomatik_baslat_durum()
    assert sonuc["ok"] is False and sonuc["acik"] is False
    sonuc = api.otomatik_baslat_ayarla(True)
    assert sonuc["ok"] is False and "hata" in sonuc
