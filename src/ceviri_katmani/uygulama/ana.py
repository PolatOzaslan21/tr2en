"""Uygulama ana akışı: kısayol ve tetik işleyicileri."""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import traceback
from typing import Any

from ..cekirdek.cevirmen import CeviriHatasi
from ..cekirdek.kurulum import akilli_cevir, zincir_kur_v2
from .gecmis import Gecmis, Islem

BULUT_GORUNEN_ADLARI = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
    "diger": "Diğer servis",
}
YEREL_GORUNEN_ADLARI = {
    "dahili": "dahili model",
    "ollama": "Ollama",
    "lmstudio": "LM Studio",
    "klasor": "model klasörü",
}


def dahili_zincir_kur() -> Any:
    """Zincir kurulamazsa kullanılan dahili yerel model zinciri (cevirmen "yerel", yerel_secili "dahili")."""
    return zincir_kur_v2({"cevirmen": "yerel", "yerel_secili": "dahili"}, lambda _servis: None)


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
            self._geri_gonder()
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
            tur = "bilinmeyen"
            try:
                try:
                    tur, arg = is_
                    if tur == "kisayol":
                        self._kisayol_isle()
                    elif tur == "tetik":
                        self._tetik_isle(*arg)
                    elif tur == "guvensiz":
                        self._guvensiz_isle(arg)
                    elif tur == "kisayol_kayit":
                        self._kisayol_kaydi_isle(*arg)
                except Exception as e:
                    # Beklenmedik hata işçiyi ÖLDÜRMEZ: kullanıcı bilgilendirilir,
                    # döngü devam eder ve sonraki kısayol çalışır (INCELEME-1 bulgu 1).
                    self._beklenmeyen_hata(tur, e)
            finally:
                self._meşgul = False
                # Tepsi menüsü Windows'ta önbellekli; her işten sonra tazelenmezse
                # "Son işlemler" / "Son çeviriyi göster" bir sonraki işe kadar eski kalıyor (Polat'ın testi, 19.11.2026).
                if self.tepsi is not None:
                    try:
                        self.tepsi.guncelle()
                    except Exception:
                        pass

    def _beklenmeyen_hata(self, tur: str, hata: Exception) -> None:
        """Beklenmedik hatayı yutar: yalnızca hata TÜRÜ kaydedilir, metin içeriği asla."""
        try:
            if sys.stderr is not None:
                traceback.print_exc()
        except Exception:
            pass
        tur_adi = type(hata).__name__
        try:
            self.bildir("Beklenmeyen hata", tur_adi, "hata")
        except Exception:
            pass
        try:
            self._kaydet(tur, "hata", ayrinti=tur_adi)
        except Exception:
            pass

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
        yuzde = self._yerel_model_indiriliyor(mesaj)
        if yuzde is not None:
            # Yerel model henüz indiriliyor: genel hata yerine bilgilendirme.
            self.bildir(
                "Yerel model henüz indiriliyor",
                f"%{yuzde} — bitince tekrar deneyin. Bu sırada Gemini kullanılabilir.",
                "uyari",
            )
            return
        if "olumsuzluk" in mesaj.lower():
            self.bildir("Olumsuzluk şüphesi — çevrilmedi", mesaj, "uyari")
        else:
            self.bildir("Çevrilemedi", mesaj, "hata")

    def _basari_bildir(self, cevirmen: str | None) -> None:
        """Başarı bildirimini kullanılan çevirmenin adına göre verir."""
        if cevirmen and cevirmen.startswith("yerel:"):
            self.bildir("Yerel modelle çevrildi — kalite düşük olabilir, kontrol edin", "", "uyari")
        elif cevirmen and cevirmen.startswith("uyumlu:"):
            model = cevirmen.partition(":")[2] or self.ayarlar.get("uyumlu_model") or ""
            self.bildir(f"Çevrildi ({model})")
        else:
            self.bildir("Çevrildi (Gemini)")

    @staticmethod
    def _yerel_model_indiriliyor(mesaj: str) -> str | None:
        """Yerel model indiriliyorsa indirme yüzdesini döner; değilse None."""
        if "model klasörü yok" not in mesaj:
            return None
        try:
            from . import model_indirme

            durum = model_indirme.durum()
        except Exception:
            return None
        if not durum.startswith("indiriliyor"):
            return None
        yuzde = durum[len("indiriliyor"):].strip().lstrip("%").strip()
        return yuzde or "0"

    def _pano_geri_yukle(self, yedek: Any) -> None:
        """Pano yedeğini geri yükler; geri yüklenemezse kullanıcıyı uyarır."""
        try:
            tamam = bool(yedek.geri_yukle())
        except Exception:
            tamam = False
        if not tamam:
            self.bildir(
                "Panonuz tam geri yüklenemedi",
                "Kopyaladığınız son içerik kaybolmuş olabilir.",
                "uyari",
            )

    def _kisayol_isle(self) -> None:
        t0 = time.perf_counter()
        pencere = self.pencere.aktif_pencere()
        if pencere is None:
            self._geri_gonder()
            self._kaydet("kisayol", "pencere-yok")
            return
        surec = getattr(pencere, "surec", None)
        izinli = self.ayarlar.get("izinli")
        if not izinli:
            izinli = None  # boş liste/küme "hepsine izin" demek
        if not self.pencere.izinli_mi(pencere, izinli, self.ayarlar["yasak"]):
            self._geri_gonder()
            self._kaydet("kisayol", "izinsiz-pencere", surec=surec)
            return

        yedek = self.pano.PanoYedegi()
        yedek.kaydet()
        try:
            t_kopya = time.perf_counter()
            metin = self.pano.secimi_kopyala(bekle_ms=self._kopya_bekleme_ms(surec))
            if metin:
                self._kopya_suresi_kaydet(surec, (time.perf_counter() - t_kopya) * 1000)
            if not metin:
                self._kaydet("kisayol", "secim-yok", surec=surec, baslangic=t0)
                # Yutulan kısayolu programa geri ver (ör. Ctrl+P: seçim yoksa programın kendi işi çalışsın).
                # Kendi kısayolunda "Seçim yok" bildirimi gösterilmez; programın işi zaten çalıştı.
                from .ayarlar import KISAYOL_SECENEKLERI

                if not self._geri_gonder() or self.ayarlar.get("kisayol") in KISAYOL_SECENEKLERI:
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
                self._basari_bildir(sonuc.cevirmen)
        finally:
            self._pano_geri_yukle(yedek)

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
            self._basari_bildir(sonuc.cevirmen)
        finally:
            self._pano_geri_yukle(yedek)

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
        return self.ayarlar.get("cevirmen", "bulut")

    def bulut_adi(self) -> str:
        servis = self.ayarlar.get("bulut_servis") or "gemini"
        return BULUT_GORUNEN_ADLARI.get(servis, servis)

    def yerel_adi(self) -> str:
        secili = self.ayarlar.get("yerel_secili") or "dahili"
        return YEREL_GORUNEN_ADLARI.get(secili, secili)

    def cevirmen_sec(self, ad: str) -> None:
        if ad not in ("bulut", "yerel"):
            return
        if self.cevirmen() == ad:
            return
        zincir_uretici = self.ayarlar.get("zincir_uretici")
        if zincir_uretici is not None:
            try:
                self.zincir = zincir_uretici(ad)
            except CeviriHatasi as e:
                self.bildir("Çeviri ayarı eksik", str(e)[:160], "uyari")
                self.ayarlar["cevirmen"] = "yerel"
                self.ayarlar["yerel_secili"] = "dahili"
                self.zincir = dahili_zincir_kur()
                self._ayarlari_kaydet()
                if self.tepsi is not None:
                    self.tepsi.guncelle()
                return
        self.ayarlar["cevirmen"] = ad
        self._ayarlari_kaydet()
        if ad == "bulut":
            self.bildir(f"Çevirmen: Bulut ({self.bulut_adi()})")
        else:
            self.bildir(f"Çevirmen: Yerel ({self.yerel_adi()})")
        if self.tepsi is not None:
            self.tepsi.guncelle()

    def _ayarlari_kaydet(self) -> bool:
        """Ayar dosyasını yazar; yazılamazsa kullanıcıyı uyarır."""
        kaydet_cb = self.ayarlar.get("kaydet_cb")
        if kaydet_cb is None:
            return True
        try:
            sonuc = kaydet_cb()
        except Exception:
            sonuc = False
        if sonuc is False:
            self.bildir(
                "Ayar kaydedilemedi",
                "Ayarlar dosyaya yazılamadı; dosya kilitli olabilir.",
                "uyari",
            )
            return False
        return True

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

    def otomatik_baslat_acik_mi(self) -> bool:
        from . import otomatik_baslat

        try:
            return otomatik_baslat.acik_mi()
        except Exception:
            return False

    def otomatik_baslat_degistir(self) -> None:
        from . import otomatik_baslat

        try:
            if otomatik_baslat.acik_mi():
                otomatik_baslat.kapat()
                self.bildir("Windows açılışında başlamayacak")
            else:
                otomatik_baslat.ac()
                self.bildir("Windows açılışında başlayacak")
        except Exception as e:
            self.bildir("Ayar değiştirilemedi", str(e), "uyari")
            return
        if self.tepsi is not None:
            self.tepsi.guncelle()

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

    def kisayol_simdiki(self) -> str:
        """Tepsi için: geçerli kısayol (pynput biçimi)."""
        return self.ayarlar["kisayol"]

    def kisayol_adi(self) -> str:
        from .ayarlar import kisayol_adi

        return kisayol_adi(self.ayarlar["kisayol"])

    def kisayol_sec(self, kisayol: str) -> None:
        """Kısayolu değiştirir; dinleyiciyi yeni kısayolla yeniden başlatır ve ayar dosyasına yazar.

        Yeni kısayol kurulamazsa eski kısayola dönülür, eski dinleyici yeniden
        kurulur ve ayar dosyasına yeni değer YAZILMAZ (INCELEME-1 bulgu 8).
        """
        if self.ayarlar.get("kisayol") == kisayol:
            return
        eski_kisayol = self.ayarlar.get("kisayol")
        eski_dinleyici = self._dinleyici
        self.ayarlar["kisayol"] = kisayol
        if eski_dinleyici is not None:
            try:
                eski_dinleyici.durdur()
            except Exception:
                pass
            try:
                self._dinleyici_kur()
            except Exception:
                self.ayarlar["kisayol"] = eski_kisayol
                self._dinleyici = eski_dinleyici
                try:
                    eski_dinleyici.baslat()
                except Exception:
                    pass
                self.bildir(
                    "Kısayol değiştirilemedi",
                    "Yeni kısayol kurulamadı; eski kısayol korundu.",
                    "uyari",
                )
                return
        self._ayarlari_kaydet()
        self.bildir("Kısayol değişti", self.kisayol_adi())
        if self.tepsi is not None:
            self.tepsi.guncelle()

    # Seçim yokken pano değişmez; o bekleme kısayolun geri gönderilmesini geciktirir.
    # Program başına en yavaş başarılı kopyalamayı hatırlayıp (diske de yazıp) beklemeyi kısaltırız.
    # Dosyada yalnızca exe adı ve milisaniye durur; metin asla.
    KOPYA_BEKLEME_EN_AZ = 120
    KOPYA_BEKLEME_EN_COK = 300
    HAZIR_KOPYA_BEKLEME = 150
    HIZLI_PROGRAMLAR = frozenset({
        "claude.exe", "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe",
        "code.exe", "notepad.exe",
    })

    def _kopya_sureleri_al(self) -> dict[str, float]:
        if getattr(self, "_kopya_sureleri", None) is None:
            self._kopya_sureleri = {}
            yol = self.ayarlar.get("kopya_sureleri_yolu")
            if yol:
                try:
                    import json
                    from pathlib import Path

                    veri = json.loads(Path(yol).read_text(encoding="utf-8"))
                    self._kopya_sureleri = {
                        str(k): float(v) for k, v in veri.items()
                        if isinstance(v, (int, float)) and 0 < v < 10_000
                    }
                except (OSError, ValueError, AttributeError):
                    pass
        return self._kopya_sureleri

    def _kopya_bekleme_ms(self, surec: str | None) -> int:
        en_yavas = self._kopya_sureleri_al().get(surec or "")
        if en_yavas is None:
            if (surec or "") in self.HIZLI_PROGRAMLAR:
                return self.HAZIR_KOPYA_BEKLEME
            return self.KOPYA_BEKLEME_EN_COK
        return int(min(self.KOPYA_BEKLEME_EN_COK, max(self.KOPYA_BEKLEME_EN_AZ, 3 * en_yavas + 40)))

    def _kopya_suresi_kaydet(self, surec: str | None, ms: float) -> None:
        sureler = self._kopya_sureleri_al()
        anahtar = surec or ""
        if not anahtar or ms <= sureler.get(anahtar, 0.0):
            return
        sureler[anahtar] = round(ms, 1)
        yol = self.ayarlar.get("kopya_sureleri_yolu")
        if yol:
            try:
                import json
                from pathlib import Path

                Path(yol).parent.mkdir(parents=True, exist_ok=True)
                Path(yol).write_text(json.dumps(sureler, ensure_ascii=False, indent=0), encoding="utf-8")
            except OSError:
                pass

    def _geri_gonder(self) -> bool:
        """Dinleyicinin yuttuğu kısayolu programa geri gönderir; gönderdiyse True."""
        dinleyici = self._dinleyici
        geri = getattr(dinleyici, "geri_gonder", None)
        if geri is None:
            return False
        try:
            return bool(geri())
        except Exception:
            traceback.print_exc()
            return False

    KAYIT_SURESI = 10.0

    def kisayol_kaydet_baslat(self) -> None:
        """Tepsiden "Kendi kısayolum…": sonraki tuş birleşimini kısayol yapar (10 sn, Esc vazgeçer)."""
        dinleyici = self._dinleyici
        if dinleyici is None or not hasattr(dinleyici, "kayit_baslat"):
            self.bildir("Kısayol kaydedilemiyor", "Klavye dinleyicisi çalışmıyor.", "uyari")
            return
        dinleyici.kayit_baslat(self._kisayol_kaydi_geldi)
        self.bildir(
            "Yeni kısayola şimdi basın",
            f"{int(self.KAYIT_SURESI)} sn içinde birleşime basın (ör. Ctrl+Shift+K). Vazgeçmek için Esc.",
        )

        def _sure_doldu() -> None:
            if self._dinleyici is dinleyici and dinleyici.kayitta_mi():
                dinleyici.kayit_bitir()
                self.bildir("Kısayol değişmedi", "Süre doldu; eski kısayol geçerli.")

        zamanlayici = threading.Timer(self.KAYIT_SURESI, _sure_doldu)
        zamanlayici.daemon = True
        zamanlayici.start()

    def _kisayol_kaydi_geldi(self, degistiriciler: set, tus: str | None) -> None:
        """Dinleyici thread'inden çağrılır; işi kuyruğa bırakır (dinleyici burada yeniden kurulamaz)."""
        self._kuyruk.put(("kisayol_kayit", (degistiriciler, tus)))

    def _kisayol_kaydi_isle(self, degistiriciler: set, tus: str | None) -> None:
        from .kisayol_kayit import birlesim_olustur

        if tus == "esc":
            self.bildir("Kısayol değişmedi", "Vazgeçildi; eski kısayol geçerli.")
            return
        kisayol, mesaj = birlesim_olustur(degistiriciler, tus)
        if kisayol is None:
            self.bildir("Kısayol değişmedi", mesaj, "uyari")
            return
        if self.ayarlar.get("kisayol") == kisayol:
            self.bildir("Kısayol değişmedi", f"{self.kisayol_adi()} zaten kullanılıyor.")
            return
        self.kisayol_sec(kisayol)
        if mesaj and self.ayarlar.get("kisayol") == kisayol:
            self.bildir(f"Kısayol: {self.kisayol_adi()}", mesaj, "uyari")

    def baslat(self) -> None:
        self._calis = True
        self._isci.start()
        self._dinleyici_kur()

    def _dinleyici_kur(self) -> None:
        dinleyici_sinifi = self.ayarlar.get("dinleyici_sinifi") or self.pencere.Dinleyici
        self._dinleyici = dinleyici_sinifi(
            kisayol=self.ayarlar["kisayol"],
            tetik=self.ayarlar["tetik"],
            kisayol_cb=self.kisayol,
            yut_cb=lambda: self._aktif,
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
        if sys.stdout is not None:
            print(
                f"tr2en: kisayol={self.ayarlar['kisayol']} "
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
            if callable(olc) and sys.stdout is not None:
                o = olc()
                print(f"Kanca olcumu: {o.get('adet', 0)} tus, ortalama {o.get('ortalama_ns', 0) / 1000:.1f} us, "
                      f"en yuksek {o.get('en_yuksek_ns', 0) / 1000:.1f} us")
        return 0


if sys.platform == "win32":

    def _aktif_hwnd() -> int | None:
        import win32gui

        return win32gui.GetForegroundWindow() or None

    def main(argv: list[str] | None = None) -> int:
        """tr2en giriş noktası."""
        from . import anahtar_kasasi, gizlilik, pano, pencere, tek_ornek, tepsi, tetik
        from . import ayarlar as ayarlar_mod
        from .bildirim import bildir

        kilit = tek_ornek.kilit_al()
        if kilit is None:
            bildir("tr2en zaten çalışıyor", "Tepsi simgesine bakın")
            return 0

        for satir in ayarlar_mod.eski_klasorleri_tasi():
            if sys.stdout is not None:
                print(satir)

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
            if not ayarlar_mod.kaydet(dosya):
                bildir(
                    "Ayar kaydedilemedi",
                    "Ayarlar dosyaya yazılamadı; dosya kilitli olabilir.",
                    "uyari",
                )

        def anahtar_saglayici(servis: str) -> str | None:
            if servis == "diger":
                ortam = dosya.get("uyumlu_anahtar_degiskeni") or ""
            else:
                ortam = ayarlar_mod.BULUT_SERVIS_ANAHTARLARI.get(servis, "")
            return anahtar_kasasi.anahtar_bul(servis, ortam)

        def zincir_uretici(ad: str):
            gecici = dict(dosya)
            gecici["cevirmen"] = ad
            return zincir_kur_v2(gecici, anahtar_saglayici)

        def kaydet_cb() -> bool:
            dosya["cevirmen"] = uygulama.cevirmen()
            dosya["kisayol"] = uygulama.kisayol_simdiki()
            return ayarlar_mod.kaydet(dosya)

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
            "bulut_servis": dosya["bulut_servis"],
            "yerel_secili": dosya["yerel_secili"],
            "uyumlu_adres": dosya["uyumlu_adres"],
            "uyumlu_model": dosya["uyumlu_model"],
            "dinleyici_sinifi": tetik.Dinleyici,
            "aktif_hwnd_cb": _aktif_hwnd,
            "zincir_uretici": zincir_uretici,
            "ayar_dosyasi": str(ayarlar_mod.ayar_yolu()),
            "kopya_sureleri_yolu": str(ayarlar_mod.ayar_klasoru() / "kopya_sureleri.json"),
            "kaydet_cb": kaydet_cb,
        }
        try:
            zincir = zincir_uretici(dosya["cevirmen"])
        except CeviriHatasi as e:
            bildir("Çeviri ayarı eksik", str(e)[:160], "uyari")
            dosya["cevirmen"] = "yerel"
            dosya["yerel_secili"] = "dahili"
            ayarlar["cevirmen"] = "yerel"
            ayarlar["yerel_secili"] = "dahili"
            zincir = dahili_zincir_kur()
        uygulama = Uygulama(pano, pencere, zincir, bildir, ayarlar)
        uygulama.baslat()
        # Yerel model yoksa arka planda indir (Hugging Face, SHA256 doğrulamalı); bu sırada Gemini çalışır.
        from .model_indirme import gerekirse_arkaplanda_indir

        gerekirse_arkaplanda_indir(bildir)
        t = tepsi.Tepsi(uygulama)
        uygulama.tepsi = t
        bildir(
            "tr2en çalışıyor",
            f"Kısayol: {ayarlar_mod.kisayol_adi(dosya['kisayol'])}" + (f" · Terminal: {dosya['tetik']}" if dosya["terminal_tetigi"] else ""),
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
        raise NotImplementedError("tr2en yalnızca Windows'ta çalışır")
