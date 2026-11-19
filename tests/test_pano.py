"""Doğrudan düzenleyici (yeni Not Defteri) yolu testleri.

Bu testler GERÇEK pencere, pano veya tuş KULLANMAZ: tüm Windows API
çağrıları sahte bir nesneyle değiştirilir (AGENTS.md: testler dış dünyaya
dokunmaz).
"""
from __future__ import annotations

import pytest

from ceviri_katmani.uygulama import pano

ON_PLAN = 100
ODAK = 101
COCUK_GIZLI = 200
COCUK_DUGM = 201
COCUK_EDITOR = 202
DOGRULANMADI = 300


class _SahteApi:
    """pano._WinApi yerine geçen sahte Windows API."""

    def __init__(self) -> None:
        self.on_plan = 0
        self.odak = 0
        self.siniflar: dict[int, str] = {}
        self.alt_penecereler: dict[int, list[int]] = {}
        self.gorunurler: set[int] = set()
        self.aralik: tuple[int, int] | None = None
        self.hata: Exception | None = None
        self.kopya_hwnd: int | None = None
        self.yapistir_hwnd: int | None = None
        self.kopya_basarisiz = False

    def _kontrol(self) -> None:
        if self.hata is not None:
            raise self.hata

    def on_plan_pencere(self) -> int:
        self._kontrol()
        return self.on_plan

    def sinif_adi(self, hwnd: int) -> str:
        self._kontrol()
        return self.siniflar.get(int(hwnd), "")

    def odak_hwnd(self, hwnd: int) -> int:
        self._kontrol()
        return self.odak

    def cocuklar(self, hwnd: int) -> list[int]:
        self._kontrol()
        return list(self.alt_penecereler.get(int(hwnd), []))

    def gorunur(self, hwnd: int) -> bool:
        self._kontrol()
        return int(hwnd) in self.gorunurler

    def secim_araligi(self, hwnd: int) -> tuple[int, int] | None:
        self._kontrol()
        return self.aralik

    def kopyala(self, hwnd: int) -> bool:
        self._kontrol()
        self.kopya_hwnd = int(hwnd)
        return not self.kopya_basarisiz

    def yapistir(self, hwnd: int) -> bool:
        self._kontrol()
        self.yapistir_hwnd = int(hwnd)
        return True


class _Sahne:
    """Test durumu: sahte API, basılan tuşlar ve panodaki metin."""

    def __init__(self, api: _SahteApi, tuslar: list[str], pano_metin: dict) -> None:
        self.api = api
        self.tuslar = tuslar
        self.pano_metin = pano_metin


@pytest.fixture()
def sahne(monkeypatch) -> _Sahne:
    api = _SahteApi()
    tuslar: list[str] = []
    pano_metin = {"deger": "seçili metin"}

    monkeypatch.setattr(pano, "WIN32", True)
    monkeypatch.setattr(pano, "_api", api)
    monkeypatch.setattr(pano, "_ctrl_tus", lambda karakter: tuslar.append(karakter))
    monkeypatch.setattr(pano, "sira_no", lambda: 1)
    monkeypatch.setattr(pano, "metin_al", lambda: pano_metin["deger"])
    monkeypatch.setattr(pano, "_sira_degisimini_bekle", lambda ilk, bekle_ms=300: True)
    return _Sahne(api, tuslar, pano_metin)


def test_dogrudan_siniflar_sabit():
    assert pano.DOGRUDAN_SINIFLAR == frozenset({"RichEditD2DPT"})


# ---- odaktaki_duzenleyici ----


def test_odakta_duzenleyici_odak_richedit_dondurur(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad", ODAK: "RichEditD2DPT"}
    sahne.api.odak = ODAK

    assert pano.odaktaki_duzenleyici() == ODAK


def test_odakta_duzenleyici_notepad_cocugunu_bulur(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {
        ON_PLAN: "Notepad",
        ODAK: "InputSiteWindowClass",
        COCUK_GIZLI: "RichEditD2DPT",
        COCUK_DUGM: "NotepadTextBox",
        COCUK_EDITOR: "RichEditD2DPT",
    }
    sahne.api.odak = ODAK
    sahne.api.alt_penecereler = {ON_PLAN: [COCUK_GIZLI, COCUK_DUGM, COCUK_EDITOR]}
    sahne.api.gorunurler = {COCUK_DUGM, COCUK_EDITOR}

    assert pano.odaktaki_duzenleyici() == COCUK_EDITOR


def test_odakta_duzenleyici_baska_uygulamada_none(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Chrome_WidgetWin_1", ODAK: "Edit"}
    sahne.api.odak = ODAK

    assert pano.odaktaki_duzenleyici() is None


def test_odakta_duzenleyici_baska_uygulamada_odak_richeditse_odagi_dondurur(sahne):
    """Odak denetimi doğrudan sınıftaysa ön plan penceresinin adı önemsenmez."""
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Chrome_WidgetWin_1", ODAK: "RichEditD2DPT"}
    sahne.api.odak = ODAK

    assert pano.odaktaki_duzenleyici() == ODAK


def test_odakta_duzenleyici_api_hatasinda_none(sahne):
    sahne.api.hata = OSError("api çöktü")

    assert pano.odaktaki_duzenleyici() is None


def test_odakta_duzenleyici_on_plan_pencere_yoksa_none(sahne):
    sahne.api.on_plan = 0

    assert pano.odaktaki_duzenleyici() is None


# ---- secimi_kopyala ----


def test_secimi_kopyala_bos_secimde_none_ve_kopya_gonderilmez(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad", ODAK: "RichEditD2DPT"}
    sahne.api.odak = ODAK
    sahne.api.aralik = (7, 7)

    assert pano.secimi_kopyala() is None
    assert sahne.api.kopya_hwnd is None
    assert sahne.tuslar == []


def test_secimi_kopyala_dolu_secimde_wm_copy_ve_pano_metni(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad", ODAK: "RichEditD2DPT"}
    sahne.api.odak = ODAK
    sahne.api.aralik = (3, 10)

    assert pano.secimi_kopyala() == "seçili metin"
    assert sahne.api.kopya_hwnd == ODAK
    assert sahne.tuslar == []


def test_secimi_kopyala_hedef_yoksa_ctrl_c_yolu(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad"}
    sahne.api.odak = DOGRULANMADI

    assert pano.secimi_kopyala() == "seçili metin"
    assert sahne.api.kopya_hwnd is None
    assert sahne.tuslar == ["c"]


def test_secimi_kopyala_hedef_yoksa_pano_degismezse_none(sahne, monkeypatch):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad"}
    monkeypatch.setattr(pano, "_sira_degisimini_bekle", lambda ilk, bekle_ms=300: False)

    assert pano.secimi_kopyala() is None
    assert sahne.tuslar == ["c"]


# ---- yapistir ----


def test_yapistir_hedef_varken_wm_paste(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad", ODAK: "RichEditD2DPT"}
    sahne.api.odak = ODAK

    pano.yapistir()
    assert sahne.api.yapistir_hwnd == ODAK
    assert sahne.tuslar == []


def test_yapistir_hedef_yokken_ctrl_v(sahne):
    sahne.api.on_plan = ON_PLAN
    sahne.api.siniflar = {ON_PLAN: "Notepad"}
    sahne.api.odak = DOGRULANMADI

    pano.yapistir()
    assert sahne.api.yapistir_hwnd is None
    assert sahne.tuslar == ["v"]
