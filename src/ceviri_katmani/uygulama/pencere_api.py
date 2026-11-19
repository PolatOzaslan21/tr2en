"""tr2en penceresinin Python köprüsü: JS'in çağırdığı, webview'dan bağımsız API.

Bu modül pywebview KULLANMAZ ve pencere AÇMAZ; ayrı süreçte açılan tr2en
penceresinin çağırdığı yöntemleri uygular (bkz. arayuz/KOPRU.md).

Çeviri pencerede YAPILMAZ: istek, ana sürece (tepsideki uygulama) adlandırılmış
boru ile gönderilir; model yalnızca ana süreçte yüklenir.

Her yöntem JSON'a çevrilebilir sözlük döner ve İSTİSNA FIRLATMAZ: hata olursa
``{"ok": False, "hata": "<kısa Türkçe metin>"}`` tabanlı bir sözlük döner.
ANAHTAR DEĞERİ hiçbir dönüşte yer almaz, hiçbir yere loglanmaz.
"""
from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from .. import __version__
from ..cekirdek.cevirmen import CeviriHatasi
from ..cekirdek.kurulum import akilli_cevir, zincir_kur_v2
from . import anahtar_kasasi
from . import ayarlar as ayar_modulu
from . import boru as boru_modulu
from . import otomatik_baslat as otomatik_baslat_modulu
from .ayarlar import BULUT_SERVIS_ANAHTARLARI, GECERLI_BULUT_SERVISLERI, VARSAYILAN
from .kisayol_kayit import birlesim_olustur

DENEME_METNI = "Merhaba dünya, bu bir denemedir."
YEREL_KONAKLAR = ("localhost", "127.0.0.1", "::1")

# baglanti_ac ile açılabilen TEK adresler; listede olmayan hiçbir URL açılmaz.
BEYAZ_LISTE: dict[str, str] = {
    "gemini_anahtar": "https://aistudio.google.com/apikey",
    "openai_anahtar": "https://platform.openai.com/api-keys",
    "deepseek_anahtar": "https://platform.deepseek.com/api_keys",
    "openrouter_anahtar": "https://openrouter.ai/settings/keys",
    "ollama": "https://ollama.com/download",
    "lmstudio": "https://lmstudio.ai",
    "github": "https://github.com/PolatOzaslan21/tr2en",
    "sorun": "https://github.com/PolatOzaslan21/tr2en/issues",
    "gizlilik": "https://github.com/PolatOzaslan21/tr2en#gizlilik",
}


class PencereApi:
    """tr2en penceresinin JS'ten çağırdığı köprü (webview'dan bağımsız)."""

    def __init__(
        self,
        ayar_yolu: Path | None = None,
        kasa: Any | None = None,
        sinyal_gonder: Callable[[str], None] | None = None,
        tarayici_ac: Callable[[str], None] | None = None,
        http_istemci: Any | None = None,
        zincir_kurucu: Callable[..., Any] | None = None,
        klasor_secici: Callable[[], str | None] | None = None,
        otomatik_baslat: Any | None = None,
        saat: Callable[[], float] = time.perf_counter,
        boru_istemcisi: Callable[[dict], dict] | None = None,
    ) -> None:
        self.ayar_yolu = Path(ayar_yolu) if ayar_yolu is not None else None
        self.kasa = anahtar_kasasi if kasa is None else kasa
        self.sinyal_gonder = sinyal_gonder if sinyal_gonder is not None else (lambda _ad: None)
        self.tarayici_ac = tarayici_ac if tarayici_ac is not None else webbrowser.open
        self.http_istemci = http_istemci if http_istemci is not None else httpx.Client(timeout=3.0)
        self.zincir_kurucu = zincir_kurucu if zincir_kurucu is not None else zincir_kur_v2
        self.klasor_secici = klasor_secici
        self.otomatik_baslat = otomatik_baslat_modulu if otomatik_baslat is None else otomatik_baslat
        self.saat = saat
        self.boru_istemcisi = boru_istemcisi if boru_istemcisi is not None else boru_modulu.istek

    # ---- iç yardımcılar (istisna yutarlar; dışarı sızdırmazlar) ----

    def _sinyal(self, ad: str) -> None:
        try:
            self.sinyal_gonder(ad)
        except Exception:
            pass

    @staticmethod
    def _hata(e: Exception) -> str:
        """Kısa, güvenli Türkçe hata metni. Anahtar değeri içermez."""
        if isinstance(e, CeviriHatasi):
            return str(e) or "çeviri başarısız"
        return f"beklenmeyen hata: {type(e).__name__}"

    @staticmethod
    def _gizli_kirp(metin: str, gizliler: list[str]) -> str:
        for gizli in gizliler:
            if gizli and gizli in metin:
                metin = metin.replace(gizli, "***")
        return metin

    @staticmethod
    def _ortam_adi(servis: str, ayar: dict) -> str:
        if servis == "diger":
            return str(ayar.get("uyumlu_anahtar_degiskeni") or "")
        return BULUT_SERVIS_ANAHTARLARI.get(servis, "")

    def _anahtar_var(self, servis: str, ayar: dict) -> bool:
        return self.kasa.anahtar_bul(servis, self._ortam_adi(servis, ayar)) is not None

    def _anahtar_saglayici(self, ayar: dict, gizliler: list[str], tek: str | None) -> Callable[[str], str | None]:
        def saglayici(servis: str) -> str | None:
            if tek is not None:
                return tek
            deger = self.kasa.anahtar_bul(servis, self._ortam_adi(servis, ayar))
            if deger:
                gizliler.append(deger)
            return deger

        return saglayici

    # ---- JS API'si ----

    def ayarlari_al(self) -> dict:
        try:
            ayar, _ = ayar_modulu.yukle(self.ayar_yolu)
            anahtarlar = {servis: self._anahtar_var(servis, ayar) for servis in GECERLI_BULUT_SERVISLERI}
            return {"ok": True, "ayarlar": ayar, "anahtarlar": anahtarlar, "surum": __version__}
        except Exception as e:
            return {"ok": False, "ayarlar": {}, "anahtarlar": {}, "surum": __version__, "hata": self._hata(e)}

    def ayar_kaydet(self, degisiklikler: dict) -> dict:
        uyarilar: list[str] = []
        try:
            if not isinstance(degisiklikler, dict):
                return {"ok": False, "uyarilar": uyarilar, "hata": "değişiklikler sözlük olmalı"}
            mevcut, yukle_uyarilari = ayar_modulu.yukle(self.ayar_yolu)
            uyarilar.extend(yukle_uyarilari)
            guncel = dict(mevcut)
            for ad, deger in degisiklikler.items():
                if ad in VARSAYILAN:
                    guncel[ad] = deger
                else:
                    uyarilar.append(f"bilinmeyen ayar '{ad}' atıldı")
            dogrulanmis, dogrulama_uyarilari = ayar_modulu.dogrula(guncel)
            uyarilar.extend(dogrulama_uyarilari)
            if not ayar_modulu.kaydet(dogrulanmis, self.ayar_yolu):
                uyarilar.append("ayar dosyası yazılamadı")
                return {"ok": False, "uyarilar": uyarilar, "hata": "ayar dosyası yazılamadı"}
            self._sinyal("yenile")
            return {"ok": True, "uyarilar": uyarilar}
        except Exception as e:
            uyarilar.append(self._hata(e))
            return {"ok": False, "uyarilar": uyarilar, "hata": self._hata(e)}

    def ilk_kurulum_tamamla(self, cevirmen: str) -> dict:
        """İlk açılış sihirbazını kapatır: çevirmen seçimini ve gizlilik onayını kaydeder."""
        try:
            if cevirmen not in ("bulut", "yerel"):
                return {"ok": False, "hata": "geçersiz çevirmen"}
            sonuc = self.ayar_kaydet({"cevirmen": cevirmen, "gizlilik_onayi": True})
            if not sonuc.get("ok"):
                return {"ok": False, "hata": sonuc.get("hata") or "ayar kaydedilemedi"}
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}

    def anahtar_kaydet(self, servis: str, deger: str) -> dict:
        try:
            if servis not in GECERLI_BULUT_SERVISLERI:
                return {"ok": False, "hata": "bilinmeyen servis"}
            if not self.kasa.yaz(servis, deger):
                return {"ok": False, "hata": "anahtar kaydedilemedi"}
            self._sinyal("yenile")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}

    def anahtar_sil(self, servis: str) -> dict:
        try:
            if servis not in GECERLI_BULUT_SERVISLERI:
                return {"ok": False, "hata": "bilinmeyen servis"}
            if not self.kasa.sil(servis):
                return {"ok": False, "hata": "anahtar silinemedi"}
            self._sinyal("yenile")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}

    def baglanti_dene(self, ayar_parcasi: dict, anahtar: str | None = None) -> dict:
        gizliler: list[str] = []
        baslangic = self.saat()
        try:
            kayitli, _ = ayar_modulu.yukle(self.ayar_yolu)
            gecici = dict(kayitli)
            if isinstance(ayar_parcasi, dict):
                gecici.update(ayar_parcasi)
            # Gerçekten seçilen servis denensin diye yerel yedek kapatılır; dosyaya YAZILMAZ.
            gecici["bulut_yedek_yerel"] = False
            if anahtar is not None:
                gizliler.append(anahtar)
            zincir = self.zincir_kurucu(gecici, self._anahtar_saglayici(gecici, gizliler, anahtar))
            sonuc = akilli_cevir(zincir, DENEME_METNI)
            return {
                "ok": True,
                "sure_sn": round(self.saat() - baslangic, 3),
                "ceviri": self._gizli_kirp(sonuc.metin, gizliler),
                "hata": "",
            }
        except Exception as e:
            return {
                "ok": False,
                "sure_sn": round(self.saat() - baslangic, 3),
                "ceviri": "",
                "hata": self._gizli_kirp(self._hata(e), gizliler),
            }

    def cevir(self, metin: str) -> dict:
        """Metni ana süreçte çevirir (boru üzerinden; pencere model YÜKLEMEZ).

        Dönüş: ``{"ok", "ceviri", "cevirmen", "durum", "sure_sn", "hata"}``.
        """
        try:
            if not isinstance(metin, str) or not metin.strip():
                return {"ok": False, "ceviri": "", "cevirmen": None, "sure_sn": 0.0, "hata": "metin boş"}
            sonuc = self.boru_istemcisi({"tur": "cevir", "metin": metin})
            if not isinstance(sonuc, dict):
                return {"ok": False, "ceviri": "", "cevirmen": None, "sure_sn": 0.0,
                        "hata": "tr2en çalışmıyor"}
            if not sonuc.get("ok"):
                return {
                    "ok": False,
                    "ceviri": "",
                    "cevirmen": None,
                    "sure_sn": self._sure(sonuc),
                    "hata": str(sonuc.get("hata") or "çeviri yapılamadı"),
                }
            return {
                "ok": True,
                "ceviri": str(sonuc.get("ceviri") or ""),
                "cevirmen": sonuc.get("cevirmen"),
                "durum": str(sonuc.get("durum") or ""),
                "sure_sn": self._sure(sonuc),
                "hata": "",
            }
        except Exception as e:
            return {"ok": False, "ceviri": "", "cevirmen": None, "sure_sn": 0.0, "hata": self._hata(e)}

    def durum(self) -> dict:
        """Uygulamanın gerçek durumu (boru üzerinden).

        Dönüş: ``{"ok", "aktif", "cevirmen", "cevirmen_adi", "kisayol_adi", "surum", "hata"}``.
        """
        bos = {"ok": False, "aktif": False, "cevirmen": "", "cevirmen_adi": "",
               "kisayol_adi": "", "surum": "", "hata": "tr2en çalışmıyor"}
        try:
            sonuc = self.boru_istemcisi({"tur": "durum"})
            if not isinstance(sonuc, dict) or not sonuc.get("ok"):
                hata = str(sonuc.get("hata")) if isinstance(sonuc, dict) and sonuc.get("hata") else bos["hata"]
                return {**bos, "hata": hata}
            return {
                "ok": True,
                "aktif": bool(sonuc.get("aktif")),
                "cevirmen": str(sonuc.get("cevirmen") or ""),
                "cevirmen_adi": str(sonuc.get("cevirmen_adi") or ""),
                "kisayol_adi": str(sonuc.get("kisayol_adi") or ""),
                "surum": str(sonuc.get("surum") or ""),
                "hata": "",
            }
        except Exception as e:
            return {**bos, "hata": self._hata(e)}

    def aktif_degistir(self) -> dict:
        """tr2en'i duraklatır/etkinleştirir; yeni durumu döner (boru üzerinden)."""
        try:
            sonuc = self.boru_istemcisi({"tur": "aktif_degistir"})
            if not isinstance(sonuc, dict) or not sonuc.get("ok"):
                hata = str(sonuc.get("hata")) if isinstance(sonuc, dict) and sonuc.get("hata") else "tr2en çalışmıyor"
                return {"ok": False, "aktif": False, "cevirmen": "", "cevirmen_adi": "",
                        "kisayol_adi": "", "surum": "", "hata": hata}
            return {
                "ok": True,
                "aktif": bool(sonuc.get("aktif")),
                "cevirmen": str(sonuc.get("cevirmen") or ""),
                "cevirmen_adi": str(sonuc.get("cevirmen_adi") or ""),
                "kisayol_adi": str(sonuc.get("kisayol_adi") or ""),
                "surum": str(sonuc.get("surum") or ""),
                "hata": "",
            }
        except Exception as e:
            return {"ok": False, "aktif": False, "cevirmen": "", "cevirmen_adi": "",
                    "kisayol_adi": "", "surum": "", "hata": self._hata(e)}

    @staticmethod
    def _sure(sonuc: dict) -> float:
        """Boru yanıtındaki süreyi güvenli biçimde döndürür."""
        try:
            return round(float(sonuc.get("sure_sn") or 0.0), 3)
        except (TypeError, ValueError):
            return 0.0

    def cevir_dene(self, metin: str) -> dict:
        """Eski ad; artık ana süreçte çevirir (bkz. ``cevir``)."""
        return self.cevir(metin)

    def ollama_modelleri(self, adres: str) -> dict:
        try:
            parca = urlsplit(str(adres or ""))
            konak = (parca.hostname or "").lower()
            if parca.scheme not in ("http", "https") or konak not in YEREL_KONAKLAR:
                return {"ok": False, "modeller": [], "hata": "yalnızca yerel (localhost) adresler sorgulanabilir"}
            yanit = self.http_istemci.get(str(adres).rstrip("/") + "/models", timeout=3)
            if yanit.status_code != 200:
                return {"ok": False, "modeller": [], "hata": f"sunucu {yanit.status_code} yanıtı verdi"}
            veri = yanit.json()
            liste = veri.get("data") if isinstance(veri, dict) else None
            if not isinstance(liste, list):
                return {"ok": False, "modeller": [], "hata": "beklenmeyen yanıt biçimi"}
            modeller = [k["id"] for k in liste if isinstance(k, dict) and k.get("id")]
            return {"ok": True, "modeller": modeller}
        except Exception as e:
            return {"ok": False, "modeller": [], "hata": self._hata(e)}

    def klasor_sec(self) -> dict:
        try:
            if self.klasor_secici is None:
                return {"ok": False, "yol": "", "hata": "klasör seçici tanımlı değil"}
            yol = self.klasor_secici()
            if not yol:
                return {"ok": False, "yol": "", "hata": "klasör seçilmedi"}
            yol = str(yol)
            if not (Path(yol) / "model.bin").is_file():
                return {"ok": False, "yol": yol, "hata": "Bu klasörde CTranslate2 modeli yok"}
            return {"ok": True, "yol": yol}
        except Exception as e:
            return {"ok": False, "yol": "", "hata": self._hata(e)}

    def baglanti_ac(self, anahtar_ad: str) -> dict:
        try:
            url = BEYAZ_LISTE.get(str(anahtar_ad or ""))
            if not url:
                return {"ok": False, "hata": "bu bağlantı beyaz listede değil"}
            self.tarayici_ac(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}

    def kisayol_kaydet(self, degistiriciler: list[str], tus: str) -> dict:
        try:
            if str(tus).lower() == "esc":
                return {"ok": False, "kisayol": "", "uyari": "", "hata": "vazgeçildi"}
            kisayol, mesaj = birlesim_olustur(set(degistiriciler or []), tus)
            if not kisayol:
                return {"ok": False, "kisayol": "", "uyari": "", "hata": mesaj}
            sonuc = self.ayar_kaydet({"kisayol": kisayol})
            if not sonuc.get("ok"):
                return {"ok": False, "kisayol": kisayol, "uyari": mesaj,
                        "hata": sonuc.get("hata") or "ayar kaydedilemedi"}
            return {"ok": True, "kisayol": kisayol, "uyari": mesaj, "hata": ""}
        except Exception as e:
            return {"ok": False, "kisayol": "", "uyari": "", "hata": self._hata(e)}

    def kapat_secimi(self, secim: str, hatirla: bool) -> dict:
        try:
            if secim == "kucult":
                if hatirla:
                    sonuc = self.ayar_kaydet({"kapatinca_sor": False})
                    if not sonuc.get("ok"):
                        return {"ok": False, "hata": sonuc.get("hata") or "ayar kaydedilemedi"}
                return {"ok": True}
            if secim == "tamamen":
                # hatirla bilerek yok sayılır; pencereyi kapatmak çağıranın işidir.
                self._sinyal("cikis")
                return {"ok": True}
            return {"ok": False, "hata": "geçersiz seçim"}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}

    def otomatik_baslat_durum(self) -> dict:
        try:
            return {"ok": True, "acik": bool(self.otomatik_baslat.acik_mi())}
        except Exception as e:
            return {"ok": False, "acik": False, "hata": self._hata(e)}

    def otomatik_baslat_ayarla(self, acik: bool) -> dict:
        try:
            if acik:
                self.otomatik_baslat.ac()
            else:
                self.otomatik_baslat.kapat()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": self._hata(e)}
