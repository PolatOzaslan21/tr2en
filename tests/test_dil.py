"""dil modülü birim testleri."""
from __future__ import annotations

import pytest

from ceviri_katmani.cekirdek.dil import turkce_mi

TURKCE = [
    "commit at ve PR aç",
    "npm install çalışmıyor, node sürümünü kontrol et",
    "src/proxy.py dosyasındaki bug'ı fixle",
    "deploy etmeden önce test et",
    "bu ram kullanımı aşırı yüksek",
    "Kart hizası mobilde kayıyor, CSS grid'i düzelt",
    "yapma",
    "tamam bu iyi",
    "önce istediğim projeyi netleştirelim",
    "bunu test et",
    "şunu düzelt",
    "açıklama gerekli mi",
    "kod incelemesi yapılır mı",
    "hata raporları nereye gidiyor",
    "dosyalar kaydedilmiş",
]

YABANCI = [
    "Fix the bug in src/proxy.py",
    "Do not delete the tests",
    "npm install is not working",
    "Let's clarify the project first",
    "OK",
    "git status",
    "https://example.com",
    "",
    "Run the tests and deploy to production",
    "Check if the file exists before deleting it",
    "This is a bug in the parser module",
    "Please review my pull request",
]


@pytest.mark.parametrize("metin", TURKCE)
def test_turkce(metin: str) -> None:
    assert turkce_mi(metin)


@pytest.mark.parametrize("metin", YABANCI)
def test_yabanci(metin: str) -> None:
    assert not turkce_mi(metin)


def test_yalnizca_bosluk() -> None:
    assert not turkce_mi("   ")
