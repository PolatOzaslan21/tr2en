"""Sistem tepsisi simgesi — ağır bağımlılıklar (pystray, PIL) geç yüklenir."""
from __future__ import annotations

import traceback
from typing import Any


def simge_uret(aktif: bool, boyut: int = 64):
    """Aktifken mavi, pasifken gri; ortasında beyaz "EN" olan yuvarlatılmış kare."""
    from PIL import Image, ImageDraw, ImageFont

    renk = (37, 99, 235) if aktif else (156, 163, 175)  # #2563EB / #9CA3AF
    gorsel = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(gorsel)
    ciz.rounded_rectangle((0, 0, boyut - 1, boyut - 1), radius=boyut // 6, fill=renk)

    font = ImageFont.load_default()
    metin = "EN"
    sol, ust, sag, alt = ciz.textbbox((0, 0), metin, font=font)
    genislik = sag - sol
    yukseklik = alt - ust
    x = (boyut - genislik) / 2 - sol
    y = (boyut - yukseklik) / 2 - ust
    ciz.text((x, y), metin, fill=(255, 255, 255), font=font)
    return gorsel


def _yut(fn) -> None:
    """Geri çağrıyı çalıştırır; istisna olursa yutar (tepsi asla çökmesin)."""
    try:
        fn()
    except Exception:
        traceback.print_exc()


class Tepsi:
    """Windows sistem tepsisi simgesi; arayuz metodlarını çağırır."""

    def __init__(self, arayuz: Any, *, pystray_mod=None, simge_uretici=None) -> None:
        self.arayuz = arayuz
        self._pystray = pystray_mod
        self._simge_uretici = simge_uretici or simge_uret
        self._icon = None

    def _pystray_getir(self):
        if self._pystray is None:
            import pystray

            self._pystray = pystray
        return self._pystray

    # ---- durum/checked yardımcıları (item argümanı pystray tarafından verilir) ----

    def _aktif_durum(self, _item=None) -> bool:
        try:
            return bool(self.arayuz.aktif_mi())
        except Exception:
            traceback.print_exc()
            return False

    def _son_ceviri_durum(self, _item=None) -> bool:
        try:
            return bool(self.arayuz.son_ceviri_var_mi())
        except Exception:
            traceback.print_exc()
            return False

    def _gemini_secili(self, _item=None) -> bool:
        try:
            return self.arayuz.cevirmen() == "gemini"
        except Exception:
            traceback.print_exc()
            return False

    def _yerel_secili(self, _item=None) -> bool:
        try:
            return self.arayuz.cevirmen() == "yerel"
        except Exception:
            traceback.print_exc()
            return False

    # ---- eylem geri çağrıları ----

    def _etkin_tiklandi(self, _icon=None, _item=None) -> None:
        _yut(self.arayuz.aktif_degistir)

    def _gemini_sec(self, _icon=None, _item=None) -> None:
        _yut(lambda: self.arayuz.cevirmen_sec("gemini"))

    def _yerel_sec(self, _icon=None, _item=None) -> None:
        _yut(lambda: self.arayuz.cevirmen_sec("yerel"))

    def _kisayol_simdiki(self) -> str | None:
        try:
            return self.arayuz.kisayol_simdiki()
        except Exception:
            traceback.print_exc()
            return None

    def _kisayol_menu(self):
        """Kısayol alt menüsü: hazır seçenekler (radyo) + ayar dosyasından gelen özel kısayol."""
        from .ayarlar import KISAYOL_SECENEKLERI, kisayol_adi

        pystray = self._pystray_getir()
        simdiki = self._kisayol_simdiki()
        ogeler = []
        for k in KISAYOL_SECENEKLERI:
            ogeler.append(pystray.MenuItem(
                kisayol_adi(k),
                (lambda kk: (lambda _i=None, _t=None: _yut(lambda: self.arayuz.kisayol_sec(kk))))(k),
                checked=(lambda kk: (lambda _i=None: self._kisayol_simdiki() == kk))(k),
                radio=True,
            ))
        if simdiki and simdiki not in KISAYOL_SECENEKLERI:
            ogeler.append(pystray.MenuItem(
                f"Özel: {kisayol_adi(simdiki)} (ayar dosyasından)", None, checked=lambda _i=None: True,
                radio=True, enabled=False,
            ))
        return ogeler

    def _son_ceviriyi_goster(self, _icon=None, _item=None) -> None:
        _yut(self.arayuz.son_ceviriyi_goster)

    def _son_orijinali_kopyala(self, _icon=None, _item=None) -> None:
        _yut(self.arayuz.son_orijinali_kopyala)

    def _ayarlari_ac(self, _icon=None, _item=None) -> None:
        _yut(self.arayuz.ayarlari_ac)

    def _cikis(self, _icon=None, _item=None) -> None:
        _yut(self.arayuz.cikis)
        _yut(self.durdur)

    def _son_islemler_menu(self) -> list:
        """Dinamik "Son işlemler" alt menüsü; menü her açıldığında çağrılır."""
        pystray = self._pystray_getir()
        try:
            satirlar = self.arayuz.son_islemler()
        except Exception:
            traceback.print_exc()
            satirlar = []
        if not satirlar:
            return [pystray.MenuItem("Henüz işlem yok", None, enabled=False)]
        return [pystray.MenuItem(satir, None, enabled=False) for satir in satirlar]

    def menu_ogeleri(self) -> list:
        """pystray.MenuItem / pystray.Menu.SEPARATOR listesi (test edilebilir)."""
        pystray = self._pystray_getir()
        return [
            pystray.MenuItem(
                "Etkin",
                self._etkin_tiklandi,
                checked=self._aktif_durum,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Çevirmen",
                pystray.Menu(
                    pystray.MenuItem(
                        "Gemini (yedek: yerel model)",
                        self._gemini_sec,
                        checked=self._gemini_secili,
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Yalnızca yerel (metin bilgisayardan çıkmaz)",
                        self._yerel_sec,
                        checked=self._yerel_secili,
                        radio=True,
                    ),
                ),
            ),
            pystray.MenuItem("Son işlemler", pystray.Menu(self._son_islemler_menu)),
            pystray.MenuItem(
                "Son çeviriyi göster",
                self._son_ceviriyi_goster,
                enabled=self._son_ceviri_durum,
            ),
            pystray.MenuItem(
                "Son orijinali kopyala",
                self._son_orijinali_kopyala,
                enabled=self._son_ceviri_durum,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Kısayol", pystray.Menu(self._kisayol_menu)),
            pystray.MenuItem("Ayarlar dosyasını aç", self._ayarlari_ac),
            pystray.MenuItem("Çıkış", self._cikis),
        ]

    def calistir(self) -> None:
        """Tepsi simgesini oluşturur ve olay döngüsüne girer (BLOKLAR)."""
        pystray = self._pystray_getir()
        simge = self._simge_uretici(self.arayuz.aktif_mi())
        menu = pystray.Menu(*self.menu_ogeleri())
        self._icon = pystray.Icon("ceviri-katmani", simge, "Çeviri Katmanı", menu)
        self._icon.run()

    def guncelle(self) -> None:
        """Simgeyi aktif/pasif durumuna göre tazeler; simge yoksa sessiz."""
        if self._icon is None:
            return
        try:
            self._icon.icon = self._simge_uretici(self.arayuz.aktif_mi())
            self._icon.update_menu()
        except Exception:
            traceback.print_exc()

    def durdur(self) -> None:
        """Simgeyi durdurur; simge yoksa sessiz."""
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            traceback.print_exc()

    def bildirim(self, baslik: str, mesaj: str = "") -> None:
        """İsteğe bağlı bildirim; hata yutulur."""
        if self._icon is None:
            return
        try:
            self._icon.notify(mesaj, baslik)
        except Exception:
            traceback.print_exc()
