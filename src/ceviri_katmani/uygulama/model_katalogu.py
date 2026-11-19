"""Model adı önerileri (açılır listede; sonunda her zaman "Kendin ekle…").

Kaynaklar 19.11.2026'da kontrol edildi: aistudio.google.com/docs/models,
developers.openai.com/api/docs/pricing, api-docs.deepseek.com (list-models),
openrouter.ai/api/v1/models, ollama.com/library. Servisler model adlarını
değiştirebilir; listede olmayan ya da kaldırılan model için kullanıcı "Kendin ekle"
ile adı elle yazar. Liste güncellenirken bu tarih de güncellenmeli.
"""
from __future__ import annotations

KATALOG_TARIHI = "2026-11-19"

# Her öğe: (model adı, kısa açıklama). İlk öğe önerilen.
BULUT: dict[str, list[tuple[str, str]]] = {
    "gemini": [
        ("gemini-3.5-flash-lite", "Önerilen · hızlı, ücretsiz katmanda"),
        ("gemini-3.1-flash-lite", "Bir önceki hızlı model"),
        ("gemini-3.8-flash", "Daha güçlü, biraz daha yavaş"),
    ],
    "openai": [
        ("gpt-6-luna", "Önerilen · en ucuz ve hızlı"),
        ("gpt-5.4-nano", "Ucuz, hızlı"),
        ("gpt-6.1-terra", "Daha güçlü, daha pahalı"),
    ],
    "deepseek": [
        ("deepseek-flash", "Önerilen · ucuz ve hızlı"),
        ("deepseek-v4-pro", "Daha güçlü, daha pahalı"),
    ],
    "openrouter": [
        ("google/gemini-3.5-flash-lite", "Önerilen · hızlı"),
        ("deepseek/deepseek-v4.1-flash", "Ucuz"),
    ],
    "diger": [],
}

# Yerel modeller: boyut, modelin indirme boyutudur (Ollama kütüphanesinden).
YEREL: dict[str, list[tuple[str, str]]] = {
    "ollama": [
        ("translategemma:4b", "Önerilen · çeviri için eğitilmiş, 3,3 GB"),
        ("gemma4:e2b", "Genel amaçlı küçük model, 4,6 GB"),
        ("translategemma:12b", "Daha iyi çeviri, 8,1 GB · güçlü bilgisayar gerekir"),
    ],
    "lmstudio": [],  # LM Studio'da adlar indirilen dosyaya göre değişir: "Listele" ile seçilir.
}

HIZ_UYARISI = (
    "Çeviri hızı seçtiğiniz modele ve bilgisayarınızın gücüne bağlıdır; büyük modeller "
    "yavaş olabilir ve daha çok bellek kullanır."
)


def oneriler(tur: str, servis: str) -> list[dict[str, str]]:
    """tur "bulut" ya da "yerel"; arayüz için [{"ad", "aciklama"}] listesi."""
    kaynak = BULUT if tur == "bulut" else YEREL
    return [{"ad": ad, "aciklama": aciklama} for ad, aciklama in kaynak.get(servis, [])]
