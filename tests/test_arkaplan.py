"""Konsolsuz başlatma: ilk süreç kendini CREATE_NO_WINDOW ile yeniden başlatıp çıkar."""
import sys

import pytest

from ceviri_katmani.uygulama import arkaplan


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_ilk_surec_konsolsuz_alt_sureci_baslatir(monkeypatch):
    monkeypatch.delenv(arkaplan.ORTAM, raising=False)
    cagri = {}

    def sahte_popen(komut, **kw):
        cagri["komut"], cagri["kw"] = komut, kw

    assert arkaplan.main([], popen=sahte_popen) == 0
    assert cagri["komut"][1:] == ["-m", "ceviri_katmani.uygulama"]
    assert cagri["kw"]["creationflags"] & arkaplan.CREATE_NO_WINDOW
    assert cagri["kw"]["env"][arkaplan.ORTAM] == "1"


def test_alt_surec_uygulamayi_calistirir(monkeypatch):
    monkeypatch.setenv(arkaplan.ORTAM, "1")
    calisti = []
    import ceviri_katmani.uygulama.ana as ana

    monkeypatch.setattr(ana, "main", lambda argv=None: calisti.append(1) or 7)
    assert arkaplan.main([], popen=lambda *a, **k: pytest.fail("yeniden başlatmamalı")) == 7
    assert calisti == [1]


def test_exe_icinde_yeniden_baslatmadan_calisir(monkeypatch):
    """PyInstaller .exe'si zaten konsolsuz; ``sys.executable -m`` orada çalışmaz."""
    monkeypatch.delenv(arkaplan.ORTAM, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    calisti = []
    import ceviri_katmani.uygulama.ana as ana

    monkeypatch.setattr(ana, "main", lambda argv=None: calisti.append(1) or 0)
    assert arkaplan.main([], popen=lambda *a, **k: pytest.fail("exe yeniden başlatmamalı")) == 0
    assert calisti == [1]
