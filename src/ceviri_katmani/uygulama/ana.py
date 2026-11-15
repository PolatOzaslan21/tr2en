"""Uygulama ana akışı: kısayol ve tetik işleyicileri."""
from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Any

from ..cekirdek.cevirmen import CeviriHatasi
from ..cekirdek.kurulum import akilli_cevir, zincir_kur


class Uygulama:
    """Çeviri uygulamasının iş mantığı; bağımlılıkları dışarıdan alır."""

    def __init__(
        self,
        pano: Any,
        pencere: Any,
        zincir: Any,
        bildir: Any,
        ayarlar: dict,
    ) -> None:
        self.pano = pano
        self.pencere = pencere
        self.zincir = zincir
        self.bildir = bildir
        self.ayarlar = ayarlar
        self._kuyruk: queue.Queue = queue.Queue()
        self._calis = False
        self._meşgul = False
        self._isci = threading.Thread(target=self._isci_dongusu, daemon=True)
        self._dinleyici: Any | None = None

    # ---- dinleyici geri çağrıları (kuyruğa koyar) ----

    def kisayol(self) -> None:
        """Kısayol tetiklendiğinde dinleyici tarafından çağrılır."""
        if self._meşgul:
            self.bildir("Önceki çeviri sürüyor")
            return
        self._kuyruk.put(("kisayol", None))

    def tetik(self, metin: str, silinecek: int) -> None:
        """Tetik tamamlandığında dinleyici tarafından çağrılır."""
        if self._meşgul:
            self.bildir("Önceki çeviri sürüyor")
            return
        self._kuyruk.put(("tetik", (metin, silinecek)))

    def guvensiz(self, sebep: str | None = None) -> None:
        """Güvensiz tamponla tetik geldiğinde dinleyici tarafından çağrılır."""
        if self._meşgul:
            self.bildir("Önceki çeviri sürüyor")
            return
        self._kuyruk.put(("guvensiz", sebep))

    # ---- işçi döngüsü ----

    def _isci_dongusu(self) -> None:
        while True:
            is_ = self._kuyruk.get()
            if is_ is None:
                break
            if not self._calis:
                break
            self._meşgul = True
            try:
                tur, arg = is_
                if tur == "kisayol":
                    self._kisayol_isle()
                elif tur == "tetik":
                    self._tetik_isle(*arg)
                elif tur == "guvensiz":
                    self._guvensiz_isle(arg)
            finally:
                self._meşgul = False

    # ---- özet kaydı (metin İÇERİĞİ asla yazılmaz) ----

    def _kaydet(self, tur: str, durum: str, *, surec: str | None = None, cevirmen: str | None = None,
                baslangic: float | None = None, giris: int | None = None, cikis: int | None = None,
                ayrinti: str | None = None) -> None:
        if not self.ayarlar.get("ozet_kaydi", True):
            return
        parca = [time.strftime("%H:%M:%S"), f"{tur:<8}", f"{durum:<16}"]
        if surec:
            parca.append(surec)
        if cevirmen:
            parca.append(cevirmen)
        if baslangic is not None:
            parca.append(f"{time.perf_counter() - baslangic:.1f} sn")
        if giris is not None:
            parca.append(f"{giris} -> {cikis if cikis is not None else '?'} karakter")
        if ayrinti:
            parca.append(f"({ayrinti})")
        try:
            print("  ".join(parca), flush=True)
        except Exception:
            pass

    def _surec_adi(self) -> str | None:
        try:
            p = self.pencere.aktif_pencere()
            return getattr(p, "surec", None)
        except Exception:
            return None

    # ---- işleyiciler ----

    def _bildir_hata(self, hata: CeviriHatasi) -> None:
        mesaj = str(hata)
        if "olumsuzluk" in mesaj.lower():
            self.bildir("Olumsuzluk şüphesi — çevrilmedi", mesaj, "uyari")
        else:
            self.bildir("Çevrilemedi", mesaj, "hata")

    def _kisayol_isle(self) -> None:
        t0 = time.perf_counter()
        pencere = self.pencere.aktif_pencere()
        if pencere is None:
            self._kaydet("kisayol", "pencere-yok")
            return
        surec = getattr(pencere, "surec", None)
        if not self.pencere.izinli_mi(pencere, self.ayarlar["izinli"], self.ayarlar["yasak"]):
            self._kaydet("kisayol", "izinsiz-pencere", surec=surec)
            return

        yedek = self.pano.PanoYedegi()
        yedek.kaydet()
        try:
            metin = self.pano.secimi_kopyala()
            if not metin:
                self._kaydet("kisayol", "secim-yok", surec=surec, baslangic=t0)
                self.bildir("Seçim yok")
                return

            try:
                sonuc = akilli_cevir(self.zincir, metin)
            except CeviriHatasi as e:
                self._kaydet("kisayol", "hata", surec=surec, baslangic=t0, giris=len(metin), ayrinti=str(e)[:160])
                self._bildir_hata(e)
                return

            if sonuc.durum == "zaten-ingilizce":
                self._kaydet("kisayol", "zaten-ingilizce", surec=surec, baslangic=t0, giris=len(metin))
                self.bildir("Zaten İngilizce")
                return

            if sonuc.durum == "cevrildi":
                self._kaydet("kisayol", "cevrildi", surec=surec, cevirmen=sonuc.cevirmen, baslangic=t0,
                             giris=len(metin), cikis=len(sonuc.metin))
                self.pano.metin_koy(sonuc.metin)
                self.pano.yapistir()
                time.sleep(0.15)
                if sonuc.cevirmen and sonuc.cevirmen.startswith("yerel:"):
                    self.bildir(
                        "Yerel modelle çevrildi — kalite düşük olabilir, kontrol edin",
                        "",
                        "uyari",
                    )
                else:
                    self.bildir("Çevrildi (Gemini)")
        finally:
            yedek.geri_yukle()

    def _tetik_isle(self, metin: str, silinecek: int) -> None:
        t0 = time.perf_counter()
        surec = self._surec_adi()
        yedek = self.pano.PanoYedegi()
        yedek.kaydet()
        tetik = self.ayarlar["tetik"]
        try:
            try:
                sonuc = akilli_cevir(self.zincir, metin)
            except CeviriHatasi as e:
                self._kaydet("tetik", "hata", surec=surec, baslangic=t0, giris=len(metin), ayrinti=str(e)[:160])
                self.pano.geri_sil(len(tetik))
                self._bildir_hata(e)
                return

            if sonuc.durum == "zaten-ingilizce":
                self._kaydet("tetik", "zaten-ingilizce", surec=surec, baslangic=t0, giris=len(metin))
                self.pano.geri_sil(len(tetik))
                self.bildir("Zaten İngilizce")
                return

            if sonuc.durum != "cevrildi":
                self._kaydet("tetik", sonuc.durum, surec=surec, baslangic=t0, giris=len(metin))
                self.pano.geri_sil(len(tetik))
                return

            self._kaydet("tetik", "cevrildi", surec=surec, cevirmen=sonuc.cevirmen, baslangic=t0,
                         giris=len(metin), cikis=len(sonuc.metin))

            self.pano.geri_sil(silinecek)
            self.pano.metin_koy(sonuc.metin)
            self.pano.yapistir()
            time.sleep(0.15)
            if sonuc.cevirmen and sonuc.cevirmen.startswith("yerel:"):
                self.bildir(
                    "Yerel modelle çevrildi — kalite düşük olabilir, kontrol edin",
                    "",
                    "uyari",
                )
            else:
                self.bildir("Çevrildi (Gemini)")
        finally:
            yedek.geri_yukle()

    def _guvensiz_isle(self, sebep: str | None = None) -> None:
        self._kaydet("tetik", "guvensiz", surec=self._surec_adi(), ayrinti=sebep)
        self.bildir(
            "Terminalde metni düzenlediniz — çevrilemedi, ;en'i silin ve tekrar yazın",
            f"Sebep: {sebep}" if sebep else "",
        )

    # ---- yaşam döngüsü ----

    def _terminal_mi(self) -> bool:
        pencere = self.pencere.aktif_pencere()
        if pencere is None:
            return False
        return self.pencere.terminal_mi(pencere)

    def baslat(self) -> None:
        self._calis = True
        self._isci.start()
        dinleyici_sinifi = self.ayarlar.get("dinleyici_sinifi") or self.pencere.Dinleyici
        self._dinleyici = dinleyici_sinifi(
            kisayol=self.ayarlar["kisayol"],
            tetik=self.ayarlar["tetik"],
            kisayol_cb=self.kisayol,
            tetik_cb=self.tetik,
            terminal_mi_cb=self._terminal_mi,
            guvensiz_cb=self.guvensiz,
            **({"aktif_hwnd_cb": self.ayarlar["aktif_hwnd_cb"]} if self.ayarlar.get("aktif_hwnd_cb") else {}),
        )
        self._dinleyici.baslat()

    def durdur(self) -> None:
        self._calis = False
        self._kuyruk.put(None)
        if self._dinleyici is not None:
            self._dinleyici.durdur()
        self._isci.join(timeout=2)

    def calis(self) -> int:
        print(
            f"Ceviri Katmani: kisayol={self.ayarlar['kisayol']} "
            f"tetik={self.ayarlar['tetik']}"
        )
        self.baslat()
        try:
            while self._calis:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            olc = getattr(self._dinleyici, "olcum", None)
            self.durdur()
            if callable(olc):
                o = olc()
                print(f"Kanca olcumu: {o.get('adet', 0)} tus, ortalama {o.get('ortalama_ns', 0) / 1000:.1f} us, "
                      f"en yuksek {o.get('en_yuksek_ns', 0) / 1000:.1f} us")
        return 0


if sys.platform == "win32":

    def _aktif_hwnd() -> int | None:
        import win32gui

        return win32gui.GetForegroundWindow() or None

    def main(argv: list[str] | None = None) -> int:
        """ceviri-uygulama giriş noktası."""
        from . import pano, pencere, tetik
        from .bildirim import bildir

        ayarlar = {
            "kisayol": "<ctrl>+<shift>+t",
            "tetik": ";en",
            "izinli": None,
            "yasak": {"keepass.exe", "1password.exe", "bitwarden.exe"},
            "dinleyici_sinifi": tetik.Dinleyici,
            "aktif_hwnd_cb": _aktif_hwnd,
        }
        zincir = zincir_kur()
        uygulama = Uygulama(pano, pencere, zincir, bildir, ayarlar)
        return uygulama.calis()

else:  # pragma: no cover

    def main(argv: list[str] | None = None) -> int:
        raise NotImplementedError("ceviri-uygulama yalnızca Windows'ta çalışır")
