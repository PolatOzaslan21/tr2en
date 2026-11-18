"""Uygulama ana akışı: kısayol ve tetik işleyicileri."""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import Any

from ..cekirdek.cevirmen import CeviriHatasi
from ..cekirdek.kurulum import akilli_cevir, zincir_kur
from .gecmis import Gecmis, Islem


def _silme_bekle(adet: int) -> float:
    """Terminal geri silmeleri işlerken beklenecek süre (uzun metinde terminal yavaş işler)."""
    return min(1.5, 0.05 + adet * 0.003)


def _yapistirma_bekle(uzunluk: int) -> float:
    """Ctrl+V işlenmeden pano geri yüklenirse hiçbir şey yapıştırılmaz (Polat'ın testi, 16.11.2026)."""
    return min(2.0, 0.35 + uzunluk / 800)


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
        self.gecmis = Gecmis()
        self._aktif = True
        self.tepsi: Any | None = None
        self._son_orijinal: str | None = None
        self._son_ceviri: str | None = None

    # ---- dinleyici geri çağrıları (kuyruğa koyar) ----

    def kisayol(self) -> None:
        """Kısayol tetiklendiğinde dinleyici tarafından çağrılır."""
        if not self._aktif:
            return
        if self._meşgul:
            self.bildir("Önceki çeviri sürüyor")
            return
        self._kuyruk.put(("kisayol", None))

    def terminal_kisayol(self) -> None:
        """Terminal tetiği kapalıyken terminalde kısayola basıldığında çağrılır."""
        if not self._aktif:
            return
        self.bildir("Terminalde henüz desteklenmiyor", "Bu sürümde metni seçip kısayola basma yöntemi normal uygulamalarda çalışır.")

    def tetik(self, metin: str, silinecek: int) -> None:
        """Tetik tamamlandığında dinleyici tarafından çağrılır."""
        if not self._aktif:
            return
        if self._meşgul:
            self.bildir("Önceki çeviri sürüyor")
            return
        self._kuyruk.put(("tetik", (metin, silinecek)))

    def guvensiz(self, sebep: str | None = None) -> None:
        """Güvensiz tamponla tetik geldiğinde dinleyici tarafından çağrılır."""
        if not self._aktif:
            return
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
        sure = time.perf_counter() - baslangic if baslangic is not None else None
        self.gecmis.ekle(
            Islem(
                saat=time.strftime("%H:%M:%S"),
                tur=tur,
                durum=durum,
                cevirmen=cevirmen,
                sure_sn=sure,
                giris=giris,
                cikis=cikis,
                ayrinti=ayrinti,
            )
        )
        parca = [time.strftime("%H:%M:%S"), f"{tur:<8}", f"{durum:<16}"]
        if surec:
            parca.append(surec)
        if cevirmen:
            parca.append(cevirmen)
        if sure is not None:
            parca.append(f"{sure:.1f} sn")
        if giris is not None:
            parca.append(f"{giris} -> {cikis if cikis is not None else '?'} karakter")
        if ayrinti:
            parca.append(f"({ayrinti})")
        try:
            if sys.stdout is not None:
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
                self._son_orijinal = metin
                self._son_ceviri = sonuc.metin
                self._kaydet("kisayol", "cevrildi", surec=surec, cevirmen=sonuc.cevirmen, baslangic=t0,
                             giris=len(metin), cikis=len(sonuc.metin))
                self.pano.metin_koy(sonuc.metin)
                self.pano.yapistir()
                time.sleep(_yapistirma_bekle(len(sonuc.metin)))
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

            self._son_orijinal = metin
            self._son_ceviri = sonuc.metin
            self._kaydet("tetik", "cevrildi", surec=surec, cevirmen=sonuc.cevirmen, baslangic=t0,
                         giris=len(metin), cikis=len(sonuc.metin))

            yapistirilacak = sonuc.metin
            if self.ayarlar.get("sona_bosluk", True) and not yapistirilacak.endswith(" "):
                yapistirilacak = yapistirilacak + " "
            self.pano.geri_sil(silinecek)
            self.pano.metin_koy(yapistirilacak)
            time.sleep(_silme_bekle(silinecek))
            self.pano.yapistir()
            time.sleep(_yapistirma_bekle(len(sonuc.metin)))
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

    # ---- tepsi arayüzü ----

    def aktif_mi(self) -> bool:
        return self._aktif

    def aktif_degistir(self) -> None:
        self._aktif = not self._aktif
        self.bildir("Etkin" if self._aktif else "Duraklatıldı")
        if self.tepsi is not None:
            self.tepsi.guncelle()

    def cevirmen(self) -> str:
        return self.ayarlar.get("cevirmen", "gemini")

    def cevirmen_sec(self, ad: str) -> None:
        if self.cevirmen() == ad:
            return
        zincir_uretici = self.ayarlar.get("zincir_uretici")
        if zincir_uretici is not None:
            self.zincir = zincir_uretici(ad)
        self.ayarlar["cevirmen"] = ad
        kaydet_cb = self.ayarlar.get("kaydet_cb")
        if kaydet_cb is not None:
            kaydet_cb()
        self.bildir("Çevirmen: Gemini" if ad == "gemini" else "Çevirmen: Yalnızca yerel")
        if self.tepsi is not None:
            self.tepsi.guncelle()

    def son_ceviri_var_mi(self) -> bool:
        return self._son_ceviri is not None

    def son_ceviriyi_goster(self) -> None:
        if self._son_ceviri is None:
            return
        self.bildir("Son çeviri", self._son_ceviri[:200])

    def son_orijinali_kopyala(self) -> None:
        if self._son_orijinal is None:
            return
        self.pano.metin_koy(self._son_orijinal)
        self.bildir("Orijinal metin panoya kopyalandı")

    def ayarlari_ac(self) -> None:
        dosya = self.ayarlar.get("ayar_dosyasi")
        if not dosya:
            return
        try:
            os.startfile(str(dosya))
        except Exception:
            self.bildir("Ayar dosyası açılamadı")

    def cikis(self) -> None:
        self._calis = False
        self.durdur()

    def son_islemler(self) -> list[str]:
        return self.gecmis.satirlar()

    # ---- yaşam döngüsü ----

    def _terminal_mi(self) -> bool:
        pencere = self.pencere.aktif_pencere()
        if pencere is None:
            return False
        return self.pencere.terminal_mi(pencere, set(self.ayarlar.get("ek_terminaller", [])))

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
            **({"tetik_etkin": self.ayarlar["terminal_tetigi"], "terminal_kisayol_cb": self.terminal_kisayol}
               if "terminal_tetigi" in self.ayarlar else {}),
        )
        self._dinleyici.baslat()

    def durdur(self) -> None:
        self._calis = False
        self._kuyruk.put(None)
        if self._dinleyici is not None:
            self._dinleyici.durdur()
        if self._isci.is_alive():
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
        from . import gizlilik, pano, pencere, tek_ornek, tepsi, tetik
        from . import ayarlar as ayarlar_mod
        from .bildirim import bildir

        kilit = tek_ornek.kilit_al()
        if kilit is None:
            bildir("Çeviri Katmanı zaten çalışıyor", "Tepsi simgesine bakın")
            return 0

        dosya, uyarilar = ayarlar_mod.yukle()
        if uyarilar:
            bildir("Ayar dosyasında sorun", "  ".join(uyarilar[:2]), "uyari")

        if not dosya["gizlilik_onayi"]:
            secim = gizlilik.gizlilik_sor()
            if secim is None:
                tek_ornek.kilit_birak(kilit)
                return 0
            dosya["cevirmen"] = secim
            dosya["gizlilik_onayi"] = True
            ayarlar_mod.kaydet(dosya)

        def zincir_uretici(ad: str):
            return zincir_kur(
                model=dosya["gemini_model"],
                yalniz=("yerel" if ad == "yerel" else None),
                zaman_asimi=dosya["zaman_asimi"],
            )

        def kaydet_cb() -> None:
            dosya["cevirmen"] = uygulama.cevirmen()
            ayarlar_mod.kaydet(dosya)

        ayarlar = {
            "kisayol": dosya["kisayol"],
            "tetik": dosya["tetik"],
            "izinli": set(dosya["izinli"]) if dosya["izinli"] else None,
            "yasak": set(dosya["yasak"]),
            "ek_terminaller": dosya["ek_terminaller"],
            "terminal_tetigi": dosya["terminal_tetigi"],
            "sona_bosluk": dosya["sona_bosluk"],
            "ozet_kaydi": dosya["ozet_kaydi"],
            "cevirmen": dosya["cevirmen"],
            "dinleyici_sinifi": tetik.Dinleyici,
            "aktif_hwnd_cb": _aktif_hwnd,
            "zincir_uretici": zincir_uretici,
            "ayar_dosyasi": str(ayarlar_mod.ayar_yolu()),
            "kaydet_cb": kaydet_cb,
        }
        uygulama = Uygulama(pano, pencere, zincir_uretici(dosya["cevirmen"]), bildir, ayarlar)
        uygulama.baslat()
        t = tepsi.Tepsi(uygulama)
        uygulama.tepsi = t
        bildir(
            "Çeviri Katmanı çalışıyor",
            f"Kısayol: {dosya['kisayol']}" + (f" · Terminal: {dosya['tetik']}" if dosya["terminal_tetigi"] else ""),
        )

        try:
            t.calistir()
        finally:
            uygulama.durdur()
            tek_ornek.kilit_birak(kilit)
            olc = getattr(uygulama._dinleyici, "olcum", None)
            if callable(olc) and sys.stdout is not None:
                o = olc()
                print(f"Kanca olcumu: {o.get('adet', 0)} tus, ortalama {o.get('ortalama_ns', 0) / 1000:.1f} us, "
                      f"en yuksek {o.get('en_yuksek_ns', 0) / 1000:.1f} us")
        return 0

else:  # pragma: no cover

    def main(argv: list[str] | None = None) -> int:
        raise NotImplementedError("ceviri-uygulama yalnızca Windows'ta çalışır")
