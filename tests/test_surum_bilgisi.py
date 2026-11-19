"""paketleme/surum_bilgisi.py: .exe sürüm bilgisi."""
import importlib.util
from pathlib import Path

from ceviri_katmani import __version__

_yol = Path(__file__).resolve().parents[1] / "paketleme" / "surum_bilgisi.py"
_spec = importlib.util.spec_from_file_location("surum_bilgisi", _yol)
surum_bilgisi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(surum_bilgisi)


def test_dortlu():
    assert surum_bilgisi.dortlu("0.1.5") == (0, 1, 5, 0)
    assert surum_bilgisi.dortlu("1.2.3.4.5") == (1, 2, 3, 4)


def test_uretilen_metin_icerik():
    metin = surum_bilgisi.uret()
    assert "StringStruct('ProductName', 'tr2en')" in metin
    assert f"StringStruct('ProductVersion', '{__version__}')" in metin


def test_uretilen_metin_pyinstaller_ile_okunur():
    import pytest
    pytest.importorskip("PyInstaller")
    metin = surum_bilgisi.uret()
    nesne = eval(metin, __import__("PyInstaller.utils.win32.versioninfo", fromlist=["*"]).__dict__)
    assert "ProductName" in str(nesne) and __version__ in str(nesne)
