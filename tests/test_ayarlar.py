"""ayarlar modülü testleri."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

from ceviri_katmani.uygulama.ayarlar import (
    GECERLI_CEVIRMENLER,
    VARSAYILAN,
    ayar_klasoru,
    ayar_yolu,
    dogrula,
    kaydet,
    yukle,
)


def test_ayar_klasoru_appdata_ile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert ayar_klasoru() == tmp_path / "tr2en"
    assert ayar_yolu() == tmp_path / "tr2en" / "ayarlar.toml"


def test_ayar_klasoru_appdata_yoksa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    assert ayar_klasoru().name == ".tr2en"


def test_ayar_klasoru_olusturmaz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    ayar_klasoru()
    assert not (tmp_path / "tr2en").exists()


def test_varsayilan_dosya_olusturma(tmp_path: Path) -> None:
    yol = tmp_path / "alt" / "ayarlar.toml"
    ayarlar, uyarilar = yukle(yol)

    assert yol.exists()
    assert uyarilar == []
    assert ayarlar == copy.deepcopy(VARSAYILAN)
    assert tomllib.loads(yol.read_text(encoding="utf-8")) == copy.deepcopy(VARSAYILAN)
    assert not yol.with_name("ayarlar.toml.tmp").exists()


def test_yaz_oku_gidis_donus(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    ozel = {
        "kisayol": "<ctrl>+<alt>+y",
        "tetik": ";;cevir",
        "cevirmen": "yerel",
        "uyumlu_adres": "https://api.openai.com/v1",
        "uyumlu_model": "gpt-4o-mini",
        "uyumlu_anahtar_degiskeni": "OPENAI_API_KEY",
        "uyumlu_zaman_asimi": 30,
        "uyumlu_dusunmeyi_kapat": False,
        "gemini_model": "gemini-test",
        "zaman_asimi": 7,
        "terminal_tetigi": True,
        "sona_bosluk": False,
        "izinli": ["Code.exe"],
        "yasak": [],
        "ek_terminaller": ["wezterm.exe"],
        "ozet_kaydi": False,
        "gizlilik_onayi": True,
    }
    kaydet(ozel, yol)
    okunan, uyarilar = yukle(yol)

    beklenen = dict(VARSAYILAN, **ozel)
    beklenen.update(zaman_asimi=7.0, uyumlu_zaman_asimi=30.0,
                    izinli=["code.exe"], ek_terminaller=["wezterm.exe"])
    assert uyarilar == []
    assert okunan == beklenen


def test_ozel_karakterli_string_kacisi(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    garip = 'ters\\bölü "tırnak"\tsatır\nson\x01kontrol'
    kaydet(dict(VARSAYILAN, tetik=garip, kisayol="<ctrl>+<shift>+t"), yol)

    metin = yol.read_text(encoding="utf-8")
    assert "\x01" not in metin
    assert tomllib.loads(metin)["tetik"] == garip
    assert yukle(yol)[0]["tetik"] == garip


def test_bozuk_toml_yedeklenir(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    yol.write_text("kisayol = [bozuk\n", encoding="utf-8")

    ayarlar, uyarilar = yukle(yol)

    yedek = tmp_path / "ayarlar.bozuk.toml"
    assert yedek.exists()
    assert yedek.read_text(encoding="utf-8") == "kisayol = [bozuk\n"
    assert ayarlar == copy.deepcopy(VARSAYILAN)
    assert any("bozuk" in u for u in uyarilar)
    assert tomllib.loads(yol.read_text(encoding="utf-8")) == copy.deepcopy(VARSAYILAN)


def test_bozuk_yedek_uzerine_yazilir(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    (tmp_path / "ayarlar.bozuk.toml").write_text("eski", encoding="utf-8")
    yol.write_text("= 1\n", encoding="utf-8")

    yukle(yol)

    assert (tmp_path / "ayarlar.bozuk.toml").read_text(encoding="utf-8") == "= 1\n"


def test_gecerli_dosya_yeniden_yazilmaz(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    icerik = "# elle düzenlendi\nayar_surumu = 2\nkisayol = '<ctrl>+q'\ncevirmen = 'yerel'\n"
    yol.write_text(icerik, encoding="utf-8")

    ayarlar, uyarilar = yukle(yol)

    assert uyarilar == []
    assert ayarlar["kisayol"] == "<ctrl>+q"
    assert ayarlar["cevirmen"] == "yerel"
    assert ayarlar["tetik"] == VARSAYILAN["tetik"]
    assert yol.read_text(encoding="utf-8") == icerik


@pytest.mark.parametrize("cevirmen", ["bulut", "yerel"])
def test_gecerli_cevirmen_kabul(cevirmen: str) -> None:
    ayarlar, uyarilar = dogrula({"cevirmen": cevirmen})
    assert ayarlar["cevirmen"] == cevirmen
    assert uyarilar == []


@pytest.mark.parametrize("cevirmen", ["gemini ", "openai", "", 3, None])
def test_gecersiz_cevirmen_varsayilana_doner(cevirmen: object) -> None:
    ayarlar, uyarilar = dogrula({"cevirmen": cevirmen})
    assert ayarlar["cevirmen"] == VARSAYILAN["cevirmen"]
    assert any("cevirmen" in u for u in uyarilar)
    assert VARSAYILAN["cevirmen"] in GECERLI_CEVIRMENLER


@pytest.mark.parametrize("deger", [0.4, 0.0, -2, 30.1, 100])
def test_zaman_asimi_araligi_disi(deger: float) -> None:
    ayarlar, uyarilar = dogrula({"zaman_asimi": deger})
    assert ayarlar["zaman_asimi"] == VARSAYILAN["zaman_asimi"]
    assert any("zaman_asimi" in u for u in uyarilar)


@pytest.mark.parametrize("deger", [0.5, 4, 30])
def test_zaman_asimi_sinirlar_ve_int(deger: float) -> None:
    ayarlar, uyarilar = dogrula({"zaman_asimi": deger})
    assert ayarlar["zaman_asimi"] == float(deger)
    assert isinstance(ayarlar["zaman_asimi"], float)
    assert uyarilar == []


def test_zaman_asimi_bool_kabul_edilmez() -> None:
    ayarlar, uyarilar = dogrula({"zaman_asimi": True})
    assert ayarlar["zaman_asimi"] == VARSAYILAN["zaman_asimi"]
    assert any("zaman_asimi" in u for u in uyarilar)


@pytest.mark.parametrize("anahtar", ["kisayol", "tetik"])
@pytest.mark.parametrize("deger", ["", "   ", "\t"])
def test_bos_kisayol_ve_tetik_varsayilana_doner(anahtar: str, deger: str) -> None:
    ayarlar, uyarilar = dogrula({anahtar: deger})
    assert ayarlar[anahtar] == VARSAYILAN[anahtar]
    assert any(anahtar in u for u in uyarilar)


def test_bool_alanina_int_kabul_edilmez() -> None:
    ayarlar, uyarilar = dogrula({"sona_bosluk": 1, "ozet_kaydi": 0, "gizlilik_onayi": 1})
    assert ayarlar["sona_bosluk"] is True
    assert ayarlar["ozet_kaydi"] is True
    assert ayarlar["gizlilik_onayi"] is False
    assert sum("varsayılan kullanıldı" in u for u in uyarilar) == 3


def test_listeler_kucuk_harfe_cevrilir() -> None:
    ayarlar, uyarilar = dogrula(
        {"izinli": ["Code.EXE"], "yasak": ["KeePass.exe"], "ek_terminaller": ["WezTerm.exe"]}
    )
    assert ayarlar["izinli"] == ["code.exe"]
    assert ayarlar["yasak"] == ["keepass.exe"]
    assert ayarlar["ek_terminaller"] == ["wezterm.exe"]
    assert uyarilar == []


@pytest.mark.parametrize(
    "anahtar,deger",
    [
        ("izinli", "code.exe"),
        ("yasak", [1, 2]),
        ("ek_terminaller", [None]),
        ("izinli", ("a", "b")),
    ],
)
def test_gecersiz_liste_varsayilana_doner(anahtar: str, deger: object) -> None:
    ayarlar, uyarilar = dogrula({anahtar: deger})
    assert ayarlar[anahtar] == VARSAYILAN[anahtar]
    assert any(anahtar in u for u in uyarilar)


def test_bilinmeyen_anahtar_atilir() -> None:
    ayarlar, uyarilar = dogrula({"bilinmeyen": 5, "kisayol": "<ctrl>+k"})
    assert "bilinmeyen" not in ayarlar
    assert ayarlar["kisayol"] == "<ctrl>+k"
    assert any("bilinmeyen" in u for u in uyarilar)


def test_yanlis_tip_varsayilana_doner() -> None:
    ayarlar, uyarilar = dogrula({"gemini_model": 42})
    assert ayarlar["gemini_model"] == VARSAYILAN["gemini_model"]
    assert any("gemini_model" in u for u in uyarilar)


def test_varsayilanlar_degismez() -> None:
    dogrula({"izinli": ["a.exe"], "yasak": []})
    assert VARSAYILAN["izinli"] == []
    assert VARSAYILAN["yasak"] == ["keepass.exe", "1password.exe", "bitwarden.exe"]


def test_kaydet_yorumlar_ve_sira(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    kaydet({}, yol)

    satirlar = yol.read_text(encoding="utf-8").splitlines()
    assert "tr2en" in satirlar[0]
    assert "yeniden başlatın" in satirlar[1]
    metin = "\n".join(satirlar[2:])
    konumlar = [metin.index(f"\n{anahtar} = ") if f"\n{anahtar} = " in metin else metin.index(f"{anahtar} = ") for anahtar in VARSAYILAN]
    assert konumlar == sorted(konumlar)
    assert all(f"# " in satir for satir in satirlar if satir.startswith("#"))


def test_kaydet_dogrulamadan_gecirir(tmp_path: Path) -> None:
    yol = tmp_path / "ayarlar.toml"
    kaydet({"cevirmen": "yok", "yasak": ["A.EXE"], "zaman_asimi": 99}, yol)

    okunan = tomllib.loads(yol.read_text(encoding="utf-8"))
    assert okunan["cevirmen"] == VARSAYILAN["cevirmen"]
    assert okunan["yasak"] == ["a.exe"]
    assert okunan["zaman_asimi"] == VARSAYILAN["zaman_asimi"]
