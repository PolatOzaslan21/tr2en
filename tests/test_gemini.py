"""GeminiCevirmen testleri — gerçek ağa çıkmadan httpx.MockTransport ile."""
from __future__ import annotations

import json

import httpx
import pytest

from ceviri_katmani.cekirdek import gemini as gemini_mod
from ceviri_katmani.cekirdek.cevirmen import CeviriHatasi
from ceviri_katmani.cekirdek.gemini import GeminiCevirmen

ANAHTAR = "test-anahtar"


@pytest.fixture
def anahtar(monkeypatch):
    monkeypatch.setattr(gemini_mod, "anahtar_oku", lambda ad: ANAHTAR)
    return ANAHTAR


def istemci(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def govde_oku(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def test_200_cevabini_ayristirir_ve_thought_atlanir(anahtar):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "iç muhakeme", "thought": True},
                                {"text": "Hello "},
                                {"text": "world", "thought": False},
                            ]
                        }
                    }
                ]
            },
        )

    cevirmen = GeminiCevirmen(istemci=istemci(handler))

    assert cevirmen.cevir("Merhaba dünya") == "Hello world"


def test_200_ama_bos_ceviri_hatasi(anahtar):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "x", "thought": True}]}}]},
        )

    cevirmen = GeminiCevirmen(istemci=istemci(handler))

    with pytest.raises(CeviriHatasi):
        cevirmen.cevir("Merhaba")


@pytest.mark.parametrize("kod", [429, 500])
def test_http_hatalari_ceviri_hatasi(anahtar, kod: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(kod, json={"error": {"message": "kota aşıldı"}})

    cevirmen = GeminiCevirmen(istemci=istemci(handler))

    with pytest.raises(CeviriHatasi) as bilgi:
        cevirmen.cevir("Merhaba")

    assert str(kod) in str(bilgi.value)


def test_ag_hatasi_ceviri_hatasi(anahtar):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı kurulamadı", request=request)

    cevirmen = GeminiCevirmen(istemci=istemci(handler))

    with pytest.raises(CeviriHatasi) as bilgi:
        cevirmen.cevir("Merhaba")

    assert "ağ hatası" in str(bilgi.value)


def test_anahtar_yoksa_ceviri_hatasi_ve_istek_atilmaz(monkeypatch):
    monkeypatch.setattr(gemini_mod, "anahtar_oku", lambda ad: None)
    istekler: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        istekler.append(request)
        return httpx.Response(200, json={})

    cevirmen = GeminiCevirmen(istemci=istemci(handler))

    with pytest.raises(CeviriHatasi):
        cevirmen.cevir("Merhaba")

    assert istekler == []


def test_gemma_modelinde_system_instruction_yok_talimat_metinde(anahtar):
    istekler: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        istekler.append(request)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
        )

    cevirmen = GeminiCevirmen(model="gemma-3-27b-it", istemci=istemci(handler))
    assert cevirmen.cevir("Merhaba") == "Hello"

    govde = govde_oku(istekler[0])
    assert "systemInstruction" not in govde
    metin = govde["contents"][0]["parts"][0]["text"]
    assert "Translate" in metin
    assert "Turkish" in metin and "English" in metin
    assert "Merhaba" in metin


def test_gemini_modelinde_system_instruction_var(anahtar):
    istekler: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        istekler.append(request)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
        )

    cevirmen = GeminiCevirmen(model="gemini-3.5-flash-lite", istemci=istemci(handler))
    assert cevirmen.cevir("Merhaba") == "Hello"

    govde = govde_oku(istekler[0])
    assert "systemInstruction" in govde
    assert "Translate" in govde["systemInstruction"]["parts"][0]["text"]
    assert govde["contents"][0]["parts"][0]["text"] == "Merhaba"


def test_anahtar_baslikta_gonderilir_urlde_key_yok(anahtar):
    istekler: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        istekler.append(request)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
        )

    cevirmen = GeminiCevirmen(model="gemini-3.5-flash-lite", istemci=istemci(handler))
    cevirmen.cevir("Merhaba")

    istek = istekler[0]
    assert istek.headers.get("x-goog-api-key") == ANAHTAR
    assert "key=" not in str(istek.url)
    assert "key" not in istek.url.params
    assert ANAHTAR not in str(istek.url)
    assert "gemini-3.5-flash-lite" in str(istek.url)
