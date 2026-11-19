"""Ayar dosyası (TOML): varsayılanlar, doğrulama, okuma ve atomik yazma."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VARSAYILAN: dict[str, Any] = {
    "kisayol": "<ctrl>+<shift>+<space>",
    "tetik": ";en",
    "cevirmen": "bulut",
    "bulut_servis": "gemini",
    "bulut_adres": "",
    "bulut_model": "",
    "bulut_yedek_yerel": True,
    "yerel_secili": "dahili",
    "ollama_adres": "http://localhost:11434/v1",
    "ollama_model": "",
    "lmstudio_adres": "http://localhost:1234/v1",
    "lmstudio_model": "",
    "klasor_yolu": "",
    "kapatinca_sor": True,
    "tema": "sistem",
    "ayar_surumu": 2,
    "uyumlu_adres": "",
    "uyumlu_model": "",
    "uyumlu_anahtar_degiskeni": "",
    "uyumlu_zaman_asimi": 15.0,
    "uyumlu_dusunmeyi_kapat": False,
    "gemini_model": "gemini-3.5-flash-lite",
    "zaman_asimi": 4.0,
    "terminal_tetigi": False,
    "sona_bosluk": True,
    "izinli": [],
    "yasak": ["keepass.exe", "1password.exe", "bitwarden.exe"],
    "ek_terminaller": [],
    "ozet_kaydi": True,
    "gizlilik_onayi": False,
}

GECERLI_CEVIRMENLER = ("bulut", "yerel")
# Şema 1'den kalan değerler; yalnızca göç sırasında kabul edilir (goc_uygula çevirir).
ESKI_CEVIRMENLER = ("gemini", "uyumlu")
GECERLI_BULUT_SERVISLERI = ("gemini", "openai", "deepseek", "openrouter", "diger")
GECERLI_YEREL_SECILILER = ("dahili", "ollama", "lmstudio", "klasor")
GECERLI_TEMALAR = ("sistem", "acik", "koyu")

# Bulut servislerinin sabit uç noktaları (yalnızca "diger" için bulut_adres kullanılır).
from ..cekirdek.servisler import BULUT_SERVIS_ADLARI  # noqa: E402  (yeniden dışa aktarım)

# Anahtarın ORTAM DEĞİŞKENİ adları (anahtarın kendisi değil!).
# "diger" için ayarlardaki uyumlu_anahtar_degiskeni kullanılır.
BULUT_SERVIS_ANAHTARLARI: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "diger": "",
}

ACIKLAMALAR: dict[str, str] = {
    "kisayol": "Global kısayol (pynput biçimi, ör. <ctrl>+<shift>+k)",
    "tetik": "Terminalde mesaj sonuna yazılan tetik (ör. ;en)",
    "cevirmen": "\"bulut\" (çevrimiçi servis, yedek: yerel model) ya da \"yerel\" (metin bilgisayardan çıkmaz)",
    "bulut_servis": "Bulut çevirmeni: \"gemini\", \"openai\", \"deepseek\", \"openrouter\" ya da \"diger\" (kendi OpenAI uyumlu adresiniz)",
    "bulut_adres": "Yalnızca bulut_servis = \"diger\" için OpenAI uyumlu API adresi, ör. https://api.example.com/v1",
    "bulut_model": "Bulut servisinde kullanılacak model adı (boşsa servisin varsayılanı; gemini için gemini_model kullanılır)",
    "bulut_yedek_yerel": "Bulut çalışmazsa dahili yerel modele geç",
    "yerel_secili": "Yerel çevirmen: \"dahili\" (CTranslate2 modeli), \"ollama\", \"lmstudio\" ya da \"klasor\" (model klasörü)",
    "ollama_adres": "Ollama'nın OpenAI uyumlu adresi",
    "ollama_model": "Ollama model adı, ör. llama3.2",
    "lmstudio_adres": "LM Studio'nun OpenAI uyumlu adresi",
    "lmstudio_model": "LM Studio model adı",
    "klasor_yolu": "CTranslate2 model klasörünün yolu (yerel_secili = \"klasor\" için)",
    "kapatinca_sor": "Uygulama kapatılırken onay sor",
    "tema": "Görünüm teması: \"sistem\", \"acik\" ya da \"koyu\"",
    "ayar_surumu": "Ayar dosyası şemasının sürümü (2); elle değiştirmeyin",
    "uyumlu_adres": "Eski şema: OpenAI uyumlu API adresi (göç sırasında yeni anahtarlara taşınır)",
    "uyumlu_model": "Eski şema: model adı (göç sırasında yeni anahtarlara taşınır)",
    "uyumlu_anahtar_degiskeni": "anahtarın ORTAM DEĞİŞKENİ adı (anahtarın kendisi değil!), ör. OPENAI_API_KEY; Ollama için boş",
    "uyumlu_zaman_asimi": "saniye; yerel LLM'ler yavaş olabilir",
    "uyumlu_dusunmeyi_kapat": "Ollama'da akıl yürüten modeller (qwen3 vb.) için true: düşünmeyi kapatır, çok hızlanır",
    "gemini_model": "Gemini isteklerinde kullanılacak model",
    "zaman_asimi": "Gemini isteği zaman aşımı, saniye (0.5-30)",
    "terminal_tetigi": "Deneysel: terminalde mesaj sonuna tetik yazınca çevir (kırılgan, varsayılan kapalı)",
    "sona_bosluk": "Terminal çevirisinin sonuna boşluk ekle",
    "izinli": "Yalnızca bu uygulamalara izin ver (boş = yasaklılar dışında her uygulama)",
    "yasak": "Bu uygulamalarda çeviri yapılmaz (küçük harf exe adları)",
    "ek_terminaller": "Terminal sayılacak ek süreç adları (küçük harf exe)",
    "ozet_kaydi": "Konsola/son işlemlere özet satır yaz (metin içeriği asla)",
    "gizlilik_onayi": "İlk açılış gizlilik bildirimi gösterildi mi",
}


def ayar_klasoru() -> Path:
    """Ayarların tutulduğu klasör; oluşturmaz."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "tr2en"
    return Path.home() / ".tr2en"


def ayar_yolu() -> Path:
    return ayar_klasoru() / "ayarlar.toml"


def _tasima_planlari() -> list[tuple[str, Path, Path]]:
    """(ad, eski klasör, yeni klasör) üçlülerini hazırlar."""
    plan: list[tuple[str, Path, Path]] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        plan.append(("%APPDATA%", Path(appdata) / "ceviri-katmani", Path(appdata) / "tr2en"))
    else:
        plan.append(("ev", Path.home() / ".ceviri-katmani", Path.home() / ".tr2en"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        plan.append(("%LOCALAPPDATA%", Path(local) / "ceviri-katmani", Path(local) / "tr2en"))
    return plan


def eski_klasorleri_tasi() -> list[str]:
    """Eski "ceviri-katmani" veri klasörlerini "tr2en" adına taşır (tek seferlik).

    Yalnızca eski klasör varsa ve yeni klasör yoksa taşır; yapılan taşımaları
    kısa Türkçe satırlar olarak döner. Hata olursa yutar, satıra yazar.
    """
    satirlar: list[str] = []
    for ad, eski, yeni in _tasima_planlari():
        if not eski.is_dir() or yeni.exists():
            continue
        try:
            os.replace(eski, yeni)
            satirlar.append(f"{ad}: '{eski.name}' klasörü '{yeni.name}' adına taşındı")
        except OSError as e:
            satirlar.append(f"{ad}: '{eski.name}' taşınamadı ({e})")
    return satirlar


def _tip_uygun(deger: Any, varsayilan: Any) -> bool:
    if isinstance(varsayilan, bool):
        return isinstance(deger, bool)
    if isinstance(varsayilan, float):
        return isinstance(deger, (int, float)) and not isinstance(deger, bool)
    if isinstance(varsayilan, int):
        return isinstance(deger, int) and not isinstance(deger, bool)
    if isinstance(varsayilan, str):
        return isinstance(deger, str)
    if isinstance(varsayilan, list):
        return isinstance(deger, list) and all(isinstance(e, str) for e in deger)
    return False


def _goc_gerekli_mi(ham: dict[str, Any]) -> bool:
    """Ham sözlükte ayar_surumu yok ya da 2'den küçükse göç gerekir."""
    surum = ham.get("ayar_surumu")
    return not (isinstance(surum, int) and not isinstance(surum, bool) and surum >= 2)


_YEREL_KONAKLAR = ("localhost", "127.0.0.1", "::1")


def goc_uygula(ayarlar: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Şema 1 ("gemini"/"uyumlu"/"yerel") ayarlarını şema 2'ye ("bulut"/"yerel") taşır.

    Sözlüğü yerinde değiştirip aynen döner; ikinci eleman uyarı satırlarıdır.
    Göç bir kez çalışır: ayar_surumu 2 olan dosyada yeniden çalışmaz.
    """
    uyarilar: list[str] = []
    cevirmen = ayarlar.get("cevirmen")
    if cevirmen == "gemini":
        ayarlar["cevirmen"] = "bulut"
        ayarlar["bulut_servis"] = "gemini"
        ayarlar["bulut_yedek_yerel"] = True
    elif cevirmen == "yerel":
        ayarlar["cevirmen"] = "yerel"
        ayarlar["yerel_secili"] = "dahili"
    elif cevirmen == "uyumlu":
        adres = ayarlar.get("uyumlu_adres") or ""
        model = ayarlar.get("uyumlu_model") or ""
        if not (adres and model):
            ayarlar["cevirmen"] = "bulut"
            ayarlar["bulut_servis"] = "gemini"
            uyarilar.append("uyumlu_adres/uyumlu_model boş, gemini'ye geçildi")
        else:
            parca = urlsplit(adres)
            konak = parca.hostname or ""
            try:
                port = parca.port
            except ValueError:
                port = None
            if konak in _YEREL_KONAKLAR:
                ayarlar["cevirmen"] = "yerel"
                if port == 11434:
                    ayarlar["yerel_secili"] = "ollama"
                    ayarlar["ollama_adres"] = adres
                    ayarlar["ollama_model"] = model
                else:
                    ayarlar["yerel_secili"] = "lmstudio"
                    ayarlar["lmstudio_adres"] = adres
                    ayarlar["lmstudio_model"] = model
            else:
                ayarlar["cevirmen"] = "bulut"
                ayarlar["bulut_model"] = model
                if konak == "api.openai.com":
                    ayarlar["bulut_servis"] = "openai"
                elif konak == "api.deepseek.com":
                    ayarlar["bulut_servis"] = "deepseek"
                elif konak == "openrouter.ai":
                    ayarlar["bulut_servis"] = "openrouter"
                else:
                    ayarlar["bulut_servis"] = "diger"
                    ayarlar["bulut_adres"] = adres
    ayarlar["ayar_surumu"] = 2
    return ayarlar, uyarilar


def dogrula(ham: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Ham sözlüğü varsayılanlarla birleştirir; geçersizleri düzeltip uyarı toplar.

    Ham sözlükte ayar_surumu 2'den küçük ya da yoksa sonunda goc_uygula ile
    eski şema değerlerini yenisine çevirir; eski "gemini"/"uyumlu" değerleri
    göç sırasında reddedilmez.
    """
    ayarlar: dict[str, Any] = {
        anahtar: (list(deger) if isinstance(deger, list) else deger)
        for anahtar, deger in VARSAYILAN.items()
    }
    uyarilar: list[str] = []
    gecerli: set[str] = set()

    for anahtar, varsayilan in VARSAYILAN.items():
        if anahtar not in ham:
            continue
        deger = ham[anahtar]
        if not _tip_uygun(deger, varsayilan):
            uyarilar.append(f"{anahtar} geçersiz, varsayılan kullanıldı")
            continue
        if isinstance(varsayilan, float) and isinstance(deger, int):
            deger = float(deger)
        if isinstance(varsayilan, list):
            deger = [eleman.lower() for eleman in deger]
        ayarlar[anahtar] = deger
        gecerli.add(anahtar)

    goc_gerekli = _goc_gerekli_mi(ham)
    gecerli_cevirmenler = GECERLI_CEVIRMENLER + (ESKI_CEVIRMENLER if goc_gerekli else ())

    if "cevirmen" in gecerli and ayarlar["cevirmen"] not in gecerli_cevirmenler:
        ayarlar["cevirmen"] = VARSAYILAN["cevirmen"]
        uyarilar.append("cevirmen geçersiz, varsayılan kullanıldı")

    for anahtar, gecerliler in (
        ("bulut_servis", GECERLI_BULUT_SERVISLERI),
        ("yerel_secili", GECERLI_YEREL_SECILILER),
        ("tema", GECERLI_TEMALAR),
    ):
        if anahtar in gecerli and ayarlar[anahtar] not in gecerliler:
            ayarlar[anahtar] = VARSAYILAN[anahtar]
            uyarilar.append(f"{anahtar} geçersiz, varsayılan kullanıldı")

    if "zaman_asimi" in gecerli and not 0.5 <= ayarlar["zaman_asimi"] <= 30:
        ayarlar["zaman_asimi"] = VARSAYILAN["zaman_asimi"]
        uyarilar.append("zaman_asimi geçersiz, varsayılan kullanıldı")

    if "uyumlu_zaman_asimi" in gecerli and not 1 <= ayarlar["uyumlu_zaman_asimi"] <= 120:
        ayarlar["uyumlu_zaman_asimi"] = VARSAYILAN["uyumlu_zaman_asimi"]
        uyarilar.append("uyumlu_zaman_asimi geçersiz, varsayılan kullanıldı")

    for anahtar in ("kisayol", "tetik"):
        if anahtar in gecerli and not ayarlar[anahtar].strip():
            ayarlar[anahtar] = VARSAYILAN[anahtar]
            uyarilar.append(f"{anahtar} geçersiz, varsayılan kullanıldı")

    for anahtar in ham:
        if anahtar not in VARSAYILAN:
            uyarilar.append(f"bilinmeyen ayar '{anahtar}' atıldı")

    if goc_gerekli:
        ayarlar, goc_uyarilari = goc_uygula(ayarlar)
        uyarilar.extend(goc_uyarilari)

    return ayarlar, uyarilar


def yukle(yol: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    """Ayar dosyasını okur; yoksa varsayılanları yazar, bozuksa yedekleyip yeniden yazar.

    Yazma/yedekleme başarısız olursa çökmez: varsayılanlar döner ve uyarı
    listesine "ayar dosyası yazılamadı" eklenir (INCELEME-1 bulgu 7).
    """
    dosya = Path(yol) if yol is not None else ayar_yolu()
    if not dosya.exists():
        try:
            dosya.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return dogrula({})[0], ["ayar dosyası yazılamadı"]
        if not kaydet(VARSAYILAN, dosya):
            return dogrula({})[0], ["ayar dosyası yazılamadı"]
        return dogrula({})[0], []

    try:
        ham = tomllib.loads(dosya.read_bytes().decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        yedek = dosya.parent / "ayarlar.bozuk.toml"
        uyarilar: list[str] = []
        yazilamadi = False
        try:
            os.replace(dosya, yedek)
            uyarilar.append(
                f"ayar dosyası bozuktu, '{yedek.name}' olarak yedeklendi ve varsayılanlar yazıldı"
            )
        except OSError:
            yazilamadi = True
            uyarilar.append("ayar dosyası bozuktu")
        if not kaydet(VARSAYILAN, dosya):
            yazilamadi = True
        if yazilamadi:
            uyarilar.append("ayar dosyası yazılamadı")
        return dogrula({})[0], uyarilar

    ayarlar, uyarilar = dogrula(ham)
    if _goc_gerekli_mi(ham):
        # Göç yapıldıysa yeni şemayı dosyaya yazar; göç bir kez çalışır.
        if not kaydet(ayarlar, dosya):
            uyarilar.append("ayar dosyası yazılamadı")
    return ayarlar, uyarilar


def _kacis(metin: str) -> str:
    parcalar: list[str] = []
    for karakter in metin:
        if karakter == "\\":
            parcalar.append("\\\\")
        elif karakter == '"':
            parcalar.append('\\"')
        elif karakter == "\b":
            parcalar.append("\\b")
        elif karakter == "\t":
            parcalar.append("\\t")
        elif karakter == "\n":
            parcalar.append("\\n")
        elif karakter == "\f":
            parcalar.append("\\f")
        elif karakter == "\r":
            parcalar.append("\\r")
        elif ord(karakter) < 0x20 or ord(karakter) == 0x7F:
            parcalar.append(f"\\u{ord(karakter):04X}")
        else:
            parcalar.append(karakter)
    return '"' + "".join(parcalar) + '"'


def _deger_yaz(deger: Any) -> str:
    if isinstance(deger, bool):
        return "true" if deger else "false"
    if isinstance(deger, str):
        return _kacis(deger)
    if isinstance(deger, int):
        return str(deger)
    if isinstance(deger, float):
        return repr(deger)
    if isinstance(deger, list):
        return "[" + ", ".join(_kacis(eleman) for eleman in deger) + "]"
    raise TypeError(f"Yazılamayan ayar tipi: {type(deger).__name__}")


def kaydet(ayarlar: dict[str, Any], yol: Path | None = None) -> bool:
    """Doğrulanmış ayarları yorumlu, atomik biçimde UTF-8 TOML olarak yazar.

    Yazma hatası (PermissionError/OSError) yutulur: başarılıysa True, aksi
    hâlde False döner (çağıran kullanıcıyı uyarabilir) — INCELEME-1 bulgu 6.
    """
    dosya = Path(yol) if yol is not None else ayar_yolu()
    dogrulanmis, _ = dogrula(ayarlar)

    satirlar = [
        "# tr2en ayarları",
        "# Değiştirdikten sonra uygulamayı yeniden başlatın.",
    ]
    for anahtar, varsayilan in VARSAYILAN.items():
        satirlar.append(f"# {ACIKLAMALAR[anahtar]}")
        satirlar.append(f"{anahtar} = {_deger_yaz(dogrulanmis[anahtar])}")
    icerik = "\n".join(satirlar) + "\n"

    gecici = dosya.with_name(dosya.name + ".tmp")
    try:
        dosya.parent.mkdir(parents=True, exist_ok=True)
        gecici.write_text(icerik, encoding="utf-8", newline="\n")
        os.replace(gecici, dosya)
    except OSError:
        return False
    finally:
        try:
            if gecici.exists():
                gecici.unlink()
        except OSError:
            pass
    return True


KISAYOL_SECENEKLERI: tuple[str, ...] = (
    "<ctrl>+<shift>+<space>",
    "<ctrl>+<shift>+y",
)
# Ctrl+Shift+T listeden çıkarıldı (tarayıcıda "kapatılan sekmeyi aç"); isteyen
# "Kendi kısayolum…" ile istediği birleşimi kaydeder (19.11.2026).


def kisayol_adi(kisayol: str) -> str:
    """pynput biçimini okunur hale getirir: "<ctrl>+<shift>+<space>" -> "Ctrl+Shift+Space"."""
    parcalar = []
    for p in kisayol.split("+"):
        p = p.strip().strip("<>")
        parcalar.append(p.upper() if len(p) == 1 else p.capitalize())
    return "+".join(parcalar)
