"""eski_klasorleri_tasi testleri — gerçek %APPDATA% klasörlerine dokunulmaz."""
from __future__ import annotations

from pathlib import Path

import pytest

from ceviri_katmani.uygulama.ayarlar import eski_klasorleri_tasi


@pytest.fixture()
def ortam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    roaming = tmp_path / "roaming"
    local = tmp_path / "local"
    roaming.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return {"roaming": roaming, "local": local}


def test_appdata_klasoru_tasinir(ortam: dict[str, Path]) -> None:
    eski = ortam["roaming"] / "ceviri-katmani"
    eski.mkdir()
    (eski / "ayarlar.toml").write_text("kisayol = 'x'", encoding="utf-8")
    (eski / "sozluk.tsv").write_text("a\tb", encoding="utf-8")

    satirlar = eski_klasorleri_tasi()

    assert not eski.exists()
    yeni = ortam["roaming"] / "tr2en"
    assert (yeni / "ayarlar.toml").read_text(encoding="utf-8") == "kisayol = 'x'"
    assert (yeni / "sozluk.tsv").read_text(encoding="utf-8") == "a\tb"
    assert len(satirlar) == 1
    assert "taşındı" in satirlar[0]
    assert "APPDATA" in satirlar[0]


def test_localappdata_klasoru_tasinir(ortam: dict[str, Path]) -> None:
    eski = ortam["local"] / "ceviri-katmani"
    model = eski / "modeller" / "tc-big-tr-en-int8"
    model.mkdir(parents=True)
    (model / "model.bin").write_bytes(b"\x00\x01")

    satirlar = eski_klasorleri_tasi()

    assert not eski.exists()
    yeni = ortam["local"] / "tr2en" / "modeller" / "tc-big-tr-en-int8"
    assert (yeni / "model.bin").read_bytes() == b"\x00\x01"
    assert len(satirlar) == 1
    assert "LOCALAPPDATA" in satirlar[0]


def test_iki_klasor_de_tasinir(ortam: dict[str, Path]) -> None:
    (ortam["roaming"] / "ceviri-katmani").mkdir()
    (ortam["local"] / "ceviri-katmani").mkdir()

    satirlar = eski_klasorleri_tasi()

    assert len(satirlar) == 2
    assert not (ortam["roaming"] / "ceviri-katmani").exists()
    assert not (ortam["local"] / "ceviri-katmani").exists()
    assert (ortam["roaming"] / "tr2en").is_dir()
    assert (ortam["local"] / "tr2en").is_dir()


def test_yeni_klasor_varsa_tasimaz(ortam: dict[str, Path]) -> None:
    eski = ortam["roaming"] / "ceviri-katmani"
    yeni = ortam["roaming"] / "tr2en"
    eski.mkdir()
    yeni.mkdir()
    (eski / "ayarlar.toml").write_text("eski", encoding="utf-8")
    (yeni / "ayarlar.toml").write_text("yeni", encoding="utf-8")

    satirlar = eski_klasorleri_tasi()

    assert eski.exists()
    assert (eski / "ayarlar.toml").read_text(encoding="utf-8") == "eski"
    assert (yeni / "ayarlar.toml").read_text(encoding="utf-8") == "yeni"
    assert satirlar == []


def test_eski_klasor_yoksa_bos_doner(ortam: dict[str, Path]) -> None:
    assert eski_klasorleri_tasi() == []


def test_hata_yutulur_satira_yazilir(
    ortam: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    (ortam["roaming"] / "ceviri-katmani").mkdir()

    def patlar(eski, yeni):
        raise OSError("kilitli")

    monkeypatch.setattr("ceviri_katmani.uygulama.ayarlar.os.replace", patlar)

    satirlar = eski_klasorleri_tasi()

    assert len(satirlar) == 1
    assert "taşınamadı" in satirlar[0]
    assert "kilitli" in satirlar[0]
    assert (ortam["roaming"] / "ceviri-katmani").exists()
