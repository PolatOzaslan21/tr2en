"""Ayar dosyası (TOML): varsayılanlar, doğrulama, okuma ve atomik yazma."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

VARSAYILAN: dict[str, Any] = {
    "kisayol": "<ctrl>+<shift>+<space>",
    "tetik": ";en",
    "cevirmen": "gemini",
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

GECERLI_CEVIRMENLER = ("gemini", "yerel")

ACIKLAMALAR: dict[str, str] = {
    "kisayol": "Global kısayol (pynput biçimi, ör. <ctrl>+<shift>+t)",
    "tetik": "Terminalde mesaj sonuna yazılan tetik (ör. ;en)",
    "cevirmen": "\"gemini\" (yedek: yerel model) ya da \"yerel\" (metin bilgisayardan çıkmaz)",
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


def dogrula(ham: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Ham sözlüğü varsayılanlarla birleştirir; geçersizleri düzeltip uyarı toplar."""
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

    if "cevirmen" in gecerli and ayarlar["cevirmen"] not in GECERLI_CEVIRMENLER:
        ayarlar["cevirmen"] = VARSAYILAN["cevirmen"]
        uyarilar.append("cevirmen geçersiz, varsayılan kullanıldı")

    if "zaman_asimi" in gecerli and not 0.5 <= ayarlar["zaman_asimi"] <= 30:
        ayarlar["zaman_asimi"] = VARSAYILAN["zaman_asimi"]
        uyarilar.append("zaman_asimi geçersiz, varsayılan kullanıldı")

    for anahtar in ("kisayol", "tetik"):
        if anahtar in gecerli and not ayarlar[anahtar].strip():
            ayarlar[anahtar] = VARSAYILAN[anahtar]
            uyarilar.append(f"{anahtar} geçersiz, varsayılan kullanıldı")

    for anahtar in ham:
        if anahtar not in VARSAYILAN:
            uyarilar.append(f"bilinmeyen ayar '{anahtar}' atıldı")

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

    return dogrula(ham)


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
    "<ctrl>+<shift>+t",
)


def kisayol_adi(kisayol: str) -> str:
    """pynput biçimini okunur hale getirir: "<ctrl>+<shift>+<space>" -> "Ctrl+Shift+Space"."""
    parcalar = []
    for p in kisayol.split("+"):
        p = p.strip().strip("<>")
        parcalar.append(p.upper() if len(p) == 1 else p.capitalize())
    return "+".join(parcalar)
