"""Bulut çeviri servislerinin sabit OpenAI uyumlu adresleri (çekirdek; arayüzden bağımsız)."""
from __future__ import annotations

BULUT_SERVIS_ADLARI: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
