"""Tüm testler için güvenlik ağı: hiçbir test gerçek tarayıcı açamaz (AGENTS.md: testler dış dünyaya dokunmaz)."""
import webbrowser

import pytest


@pytest.fixture(autouse=True)
def _gercek_tarayici_yasak(monkeypatch):
    def yasak(*_a, **_k):
        raise AssertionError("test gerçek tarayıcı açmaya çalıştı; tarayici_ac için sahte kullanın")

    for ad in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, ad, yasak)
