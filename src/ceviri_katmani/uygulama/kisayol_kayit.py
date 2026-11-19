"""Kullanıcının bastığı tuş birleşimini kısayola çevirme (tepside "Kendi kısayolum…").

Saf mantık: pynput'a bağımlı değil; dinleyici tuşları adlara çevirip buraya verir.
"""
from __future__ import annotations

import re

DEGISTIRICILER = ("ctrl", "shift", "alt")

# Desteklenen ana tuşlar: harf, rakam, F1-F24, birkaç adlandırılmış tuş.
_ADLI_TUSLAR = {"space", "enter", "insert", "home", "end", "page_up", "page_down", "pause"}

# Bilinen çakışmalar (engellemez, uyarır). Anahtar: değiştiriciler alfabetik + tuş.
BILINEN_CAKISMALAR: dict[str, str] = {
    "ctrl+shift+t": "tarayıcılarda kapatılan sekmeyi yeniden açar",
    "ctrl+shift+n": "tarayıcılarda gizli pencere açar",
    "ctrl+shift+w": "tarayıcılarda pencereyi kapatır",
    "ctrl+shift+i": "tarayıcılarda geliştirici araçlarını açar",
    "ctrl+shift+j": "tarayıcılarda konsolu açar",
    "ctrl+shift+c": "tarayıcılarda öğe seçiciyi, terminalde kopyalamayı yapar",
    "ctrl+shift+v": "birçok programda biçimsiz yapıştırır",
    "ctrl+shift+b": "tarayıcılarda yer imleri çubuğunu açar/kapatır",
    "ctrl+shift+delete": "tarayıcılarda geçmişi temizleme penceresini açar",
    "ctrl+shift+p": "VS Code'da komut paletini, tarayıcılarda gizli pencereyi açar",
    "ctrl+shift+f": "VS Code'da tüm dosyalarda aramayı açar",
    "ctrl+shift+e": "VS Code'da dosya gezginini açar",
    "ctrl+shift+s": "birçok programda 'Farklı kaydet'tir",
    "ctrl+shift+z": "birçok programda yinele (redo) işlemidir",
    "ctrl+shift+enter": "Excel'de dizi formülü girer",
}


def tus_gecerli_mi(tus: str) -> bool:
    if re.fullmatch(r"[a-z0-9]", tus):
        return True
    if re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", tus):
        return True
    return tus in _ADLI_TUSLAR


def birlesim_olustur(degistiriciler: set[str], tus: str | None) -> tuple[str | None, str]:
    """Basılan değiştiriciler + tek tuştan pynput kısayolu üretir.

    Döner: (kisayol, mesaj). ``kisayol`` None ise mesaj reddetme sebebidir;
    değilse mesaj boş ya da bir çakışma uyarısıdır.
    """
    if not tus or not tus_gecerli_mi(tus):
        return None, "Bu tuş kısayolda kullanılamıyor. Harf, rakam, F1-F24 ya da Space seçin."
    mods = {m for m in degistiriciler if m in DEGISTIRICILER}
    if "ctrl" in mods and "alt" in mods:
        return None, "Ctrl+Alt (AltGr) Türkçe klavyede ₺, @, € gibi işaretleri yazar; başka bir birleşim seçin."
    fonksiyon_tusu = tus.startswith("f") and len(tus) > 1
    if len(mods) < 2 and not (mods and fonksiyon_tusu):
        return None, "En az iki değiştirici tuş gerekir (ör. Ctrl+Shift+K); F tuşlarıyla tek değiştirici yeter (ör. Ctrl+F9)."
    sirali = [m for m in DEGISTIRICILER if m in mods]
    ad = "+".join(sirali + [tus])
    uyari = BILINEN_CAKISMALAR.get(ad, "")
    if uyari:
        uyari = f"Dikkat: bu kısayol {uyari}; orada o işlem çalışmayabilir."
    tus_pynput = tus if len(tus) == 1 else f"<{tus}>"
    return "+".join([f"<{m}>" for m in sirali] + [tus_pynput]), uyari
