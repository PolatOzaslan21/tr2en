"""Klavye tetikleyicisi: saf tampon mantığı + pynput dinleyicisi (AJAN 2).

``TusTamponu`` Windows'tan bağımsız saf mantıktır; birim test edilir.
``Dinleyici`` ise pynput klavye + fare dinleyicisini sarar. Performans
kritik olduğundan dinleyici geri çağrıları yalnızca tamponu günceller ve
``queue.Queue``ya iş koyar; işler ayrı bir işçi thread'inde yürütülür.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Callable

_IS_WIN = sys.platform == "win32"

_DURDUR = object()

_LLKHF_INJECTED = 0x10


class TusTamponu:
    """Klavye girişini biriktirip tetik dizesini algılayan saf mantık."""

    def __init__(self, tetik: str = ";en", en_fazla: int = 4000):
        self.tetik = tetik
        self.en_fazla = en_fazla
        self.guvenli = True
        self._karakterler: list[str] = []

    def _tetik_ile_bitiyor_mu(self) -> bool:
        if not self.tetik:
            return False
        n = len(self.tetik)
        if len(self._karakterler) < n:
            return False
        return "".join(self._karakterler[-n:]) == self.tetik

    def karakter(self, k: str) -> bool:
        """Bir karakter ekler; tampon tetik ile bitiyorsa True döner."""
        if not k:
            return False
        self._karakterler.append(k)
        if len(self._karakterler) > self.en_fazla:
            self.guvensiz_yap()
            self._karakterler = self._karakterler[-self.en_fazla:]
        return self._tetik_ile_bitiyor_mu()

    def geri(self) -> None:
        """Backspace: son karakteri siler (boşsa güvensiz yapar)."""
        if self._karakterler:
            self._karakterler.pop()
        else:
            self.guvensiz_yap()

    def sifirla(self) -> None:
        """Enter/Esc/Tab ve pencere değişimi için tamponu boşaltır."""
        self._karakterler.clear()
        self.guvenli = True

    def guvensiz_yap(self) -> None:
        """Tamponu güvensiz işaretler (ok tuşu, fare, Ctrl+tuş...)."""
        self.guvenli = False

    def metin(self) -> str:
        """Tetik HARİÇ tampon metni."""
        n = len(self.tetik)
        if self._tetik_ile_bitiyor_mu():
            return "".join(self._karakterler[:-n])
        return "".join(self._karakterler)

    def uzunluk_tetik_dahil(self) -> int:
        """Tetik dahil tampon uzunluğu (geri silinecek karakter sayısı)."""
        return len(self._karakterler)


class Dinleyici:
    """pynput klavye + fare dinleyicisi; işleri ayrı işçi thread'inde yürütür."""

    def __init__(
        self,
        kisayol: str,
        tetik: str,
        kisayol_cb: Callable[[], None],
        tetik_cb: Callable[[str, int], None],
        terminal_mi_cb: Callable[[], bool],
        guvensiz_cb: Callable[[], None] | None = None,
        aktif_hwnd_cb: Callable[[], int | None] | None = None,
    ):
        self.kisayol = kisayol
        self.tetik = tetik
        self._kisayol_cb = kisayol_cb
        self._tetik_cb = tetik_cb
        self._terminal_mi_cb = terminal_mi_cb
        self._guvensiz_cb = guvensiz_cb
        self._aktif_hwnd_cb = aktif_hwnd_cb

        self._kuyruk: queue.Queue = queue.Queue()
        self._tampon = TusTamponu(tetik=tetik)
        self._baslangic_hwnd: int | None = None

        self._ctrl_alt: set = set()
        self._hotkey = None
        self._kb = None

        self._klavye_listener = None
        self._fare_listener = None
        self._isci: threading.Thread | None = None
        self._calisiyor = False

        self._cb_adet = 0
        self._cb_toplam = 0
        self._cb_en_yuksek = 0

    def _klavye_modulu(self):
        if self._kb is None:
            from pynput import keyboard

            self._kb = keyboard
        return self._kb

    def _kanonik(self, key):
        kb = self._klavye_modulu()
        Key = kb.Key
        KeyCode = kb.KeyCode
        nm = kb._NORMAL_MODIFIERS
        if isinstance(key, KeyCode):
            vk = getattr(key, "vk", None)
            # Ctrl basılıyken Windows harfleri kontrol karakteri (ör. Ctrl+T -> '') olarak verir;
            # harf/rakam tuşlarında sanal tuş kodundan gerçek harfe dön.
            if vk is not None and (0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39):
                return KeyCode.from_char(chr(vk).lower())
            if key.char is not None:
                return KeyCode.from_char(key.char.lower())
        if isinstance(key, Key) and key.value in nm:
            return nm[key.value]
        if isinstance(key, Key) and key.value.vk is not None:
            return KeyCode.from_vk(key.value.vk)
        return key

    def _hotkey_nesnesi(self):
        if self._hotkey is None:
            kb = self._klavye_modulu()
            self._hotkey = kb.HotKey(
                kb.HotKey.parse(self.kisayol), self._kisayol_etkin
            )
        return self._hotkey

    def _kisayol_etkin(self):
        terminal = self._terminal_mi_guvenli()
        if not terminal:
            self._kuyruk.put_nowait(("kisayol",))

    def _terminal_mi_guvenli(self) -> bool:
        try:
            return bool(self._terminal_mi_cb())
        except Exception:
            return False

    def _hwnd_al(self) -> int | None:
        if self._aktif_hwnd_cb is None:
            return None
        try:
            return self._aktif_hwnd_cb()
        except Exception:
            return None

    def _hwnd_baslangic_kaydet(self) -> None:
        self._baslangic_hwnd = self._hwnd_al()

    def _zamanla(self, fn: Callable[[], None]) -> None:
        baslangic = time.perf_counter_ns()
        try:
            fn()
        finally:
            sure = time.perf_counter_ns() - baslangic
            self._cb_adet += 1
            self._cb_toplam += sure
            if sure > self._cb_en_yuksek:
                self._cb_en_yuksek = sure

    def olcum(self) -> dict:
        """Ortalama ve en yüksek callback süresini (ns) döner."""
        ortalama = self._cb_toplam // self._cb_adet if self._cb_adet else 0
        return {
            "adet": self._cb_adet,
            "ortalama_ns": ortalama,
            "en_yuksek_ns": self._cb_en_yuksek,
        }

    def _on_press(self, key, injected: bool = False):
        self._zamanla(lambda: self._on_press_ic(key))

    def _on_press_ic(self, key) -> None:
        kanonik = self._kanonik(key)
        self._hotkey_nesnesi().press(kanonik)
        kb = self._klavye_modulu()
        if kanonik in (kb.Key.ctrl, kb.Key.alt):
            self._ctrl_alt.add(kanonik)
            return
        if self._ctrl_alt:
            self._tampon.guvensiz_yap()
            return
        self._tus_tampona(key)

    def _on_release(self, key, injected: bool = False):
        self._zamanla(lambda: self._on_release_ic(key))

    def _on_release_ic(self, key) -> None:
        kanonik = self._kanonik(key)
        self._hotkey_nesnesi().release(kanonik)
        kb = self._klavye_modulu()
        if kanonik in (kb.Key.ctrl, kb.Key.alt):
            self._ctrl_alt.discard(kanonik)

    def _tus_tampona(self, key) -> None:
        kb = self._klavye_modulu()
        Key = kb.Key
        if key is Key.backspace:
            self._tampon.geri()
            return
        if key in (Key.enter, Key.esc, Key.tab):
            self._tampon.sifirla()
            return
        if key in (
            Key.up,
            Key.down,
            Key.left,
            Key.right,
            Key.home,
            Key.end,
            Key.delete,
            Key.page_up,
            Key.page_down,
        ):
            self._tampon.guvensiz_yap()
            return
        if key is Key.space:
            c = " "
        else:
            c = getattr(key, "char", None)
        if not c:
            return
        if self._tampon.uzunluk_tetik_dahil() == 0:
            self._hwnd_baslangic_kaydet()
        if self._tampon.karakter(c):
            self._tetik_tamamlandi()

    def _tetik_tamamlandi(self) -> None:
        terminal = self._terminal_mi_guvenli()
        simdiki = self._hwnd_al()
        if (
            self._baslangic_hwnd is not None
            and simdiki is not None
            and simdiki != self._baslangic_hwnd
        ):
            self._tampon.guvensiz_yap()
        guvenli = self._tampon.guvenli
        metin = self._tampon.metin()
        silinecek = self._tampon.uzunluk_tetik_dahil()
        self._tampon.sifirla()
        if not terminal:
            return
        if guvenli:
            self._kuyruk.put_nowait(("tetik", metin, silinecek))
        else:
            self._kuyruk.put_nowait(("guvensiz",))

    def _on_click(self, x, y, button, pressed):
        self._tampon.guvensiz_yap()

    def _isci_dongusu(self) -> None:
        while True:
            job = self._kuyruk.get()
            if job is _DURDUR:
                break
            try:
                self._isi_yurut(job)
            except Exception:
                pass

    def _isi_yurut(self, job) -> None:
        tur = job[0]
        if tur == "kisayol":
            self._kisayol_cb()
        elif tur == "tetik":
            self._tetik_cb(job[1], job[2])
        elif tur == "guvensiz":
            if self._guvensiz_cb is not None:
                self._guvensiz_cb()

    def baslat(self) -> None:
        if not _IS_WIN:
            raise NotImplementedError("Dinleyici yalnızca Windows'ta çalışır")
        if self._calisiyor:
            return
        kb = self._klavye_modulu()
        from pynput import mouse

        self._calisiyor = True
        self._isci = threading.Thread(
            target=self._isci_dongusu, daemon=True, name="ceviri-isci"
        )
        self._isci.start()
        self._klavye_listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            win32_event_filter=self._win32_event_filter,
        )
        self._fare_listener = mouse.Listener(on_click=self._on_click)
        self._klavye_listener.start()
        self._fare_listener.start()

    def _win32_event_filter(self, msg, data):
        if data.flags & _LLKHF_INJECTED:
            return False
        return True

    def durdur(self) -> None:
        if not self._calisiyor:
            return
        self._calisiyor = False
        if self._klavye_listener is not None:
            self._klavye_listener.stop()
        if self._fare_listener is not None:
            self._fare_listener.stop()
        self._kuyruk.put_nowait(_DURDUR)
        if self._isci is not None:
            self._isci.join(timeout=2.0)
