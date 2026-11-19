"""Pencere ile ana süreç arasındaki adlandırılmış boru (named pipe) köprüsü.

Pencere süreci MODEL YÜKLEMEZ; çeviri isteğini tepsideki ana sürece (uygulama)
gönderir, yanıtı alır. Sözleşme: tek satır JSON istek → tek satır JSON yanıt.

Güvenlik: boru "varsayılan güvenlik tanımlayıcısı" ile açılır; yalnızca aynı
kullanıcı yazabilir. Özel izin (security descriptor) VERİLMEZ.

Gerçek Windows çağrıları yalnızca ``_win`` verilmediğinde yapılır; testler sahte
``_win`` nesnesi enjekte eder, gerçek boru AÇMAZ/KURMAZ.
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

EN_FAZLA_ISTEK = 64 * 1024
ZAMAN_ASIMI_SN = 30.0
BUFER_BOYUTU = 64 * 1024
ERROR_PIPE_CONNECTED = 535
ERROR_PIPE_BUSY = 231

_AD_KUYGULU = re.compile(r"[^A-Za-z0-9_-]")


def kullanici_adi() -> str:
    """Borunun adında kullanılacak kullanıcı adı (yalnızca harf/rakam/-/_)."""
    ad = _AD_KUYGULU.sub("", os.environ.get("USERNAME") or "")
    return ad or "kullanici"


BORU_ADI = r"\\.\pipe\tr2en-" + kullanici_adi()


def _gercek_win() -> SimpleNamespace:
    """Gerçek pywin32 çağrıları; pywin32 yoksa hata fırlatır."""
    import win32file
    import win32pipe

    return SimpleNamespace(
        CreateNamedPipe=win32pipe.CreateNamedPipe,
        ConnectNamedPipe=win32pipe.ConnectNamedPipe,
        DisconnectNamedPipe=win32pipe.DisconnectNamedPipe,
        CreateFile=win32file.CreateFile,
        ReadFile=win32file.ReadFile,
        WriteFile=win32file.WriteFile,
        CloseHandle=win32file.CloseHandle,
        PIPE_ACCESS_DUPLEX=win32pipe.PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE=win32pipe.PIPE_TYPE_MESSAGE,
        PIPE_READMODE_MESSAGE=win32pipe.PIPE_READMODE_MESSAGE,
        PIPE_WAIT=win32pipe.PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES=win32pipe.PIPE_UNLIMITED_INSTANCES,
        GENERIC_READ=win32file.GENERIC_READ,
        GENERIC_WRITE=win32file.GENERIC_WRITE,
        OPEN_EXISTING=win32file.OPEN_EXISTING,
    )


def _veri(sonuc: Any) -> bytes:
    """win32file.ReadFile sonucunun bayt kısmını döndürür."""
    if isinstance(sonuc, tuple):
        return sonuc[1] or b""
    return sonuc or b""


class _HataliIstek(Exception):
    """İstek okunamadı/yorumlanamadı; mesajı istemciye gider."""

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj)
        self.mesaj = mesaj


class BoruSunucusu:
    """Arka plan thread'inde bağlantı kabul eder; her bağlantıda tek istek işler.

    ``isleyici(istek)`` sonucu (``dict``) istemciye JSON olarak yazılır. İşleyici
    istisna fırlatırsa ``{"ok": False, "hata": "iç hata"}`` döner.
    """

    def __init__(
        self,
        isleyici: Callable[[dict], dict],
        *,
        ad: str = BORU_ADI,
        _win: Any | None = None,
    ) -> None:
        self.isleyici = isleyici
        self.ad = ad
        self._win = _win
        self._handle: Any | None = None
        self._thread: threading.Thread | None = None
        self._durdu = threading.Event()

    # ---- yaşam döngüsü ----

    def baslat(self) -> None:
        """Boruyu açar ve arka plan thread'ini başlatır; hata olursa yükseltilir."""
        if self._thread is not None:
            return
        win = self._win if self._win is not None else _gercek_win()
        self._win = win
        handle = win.CreateNamedPipe(
            self.ad,
            win.PIPE_ACCESS_DUPLEX,
            win.PIPE_TYPE_MESSAGE | win.PIPE_READMODE_MESSAGE | win.PIPE_WAIT,
            win.PIPE_UNLIMITED_INSTANCES,
            BUFER_BOYUTU,
            BUFER_BOYUTU,
            0,
            None,  # varsayılan güvenlik tanımlayıcısı (özel izin verilmez)
        )
        self._handle = handle
        self._durdu.clear()
        self._thread = threading.Thread(target=self._dongu, name="tr2en-boru", daemon=True)
        self._thread.start()

    def durdur(self) -> None:
        """Thread'i bitirir ve boru handle'ını kapatır; birden çok kez çağrılabilir.

        Sunucu thread'i ``ConnectNamedPipe`` beklemesindeyken handle kapatmak
        onu BLOKLAR; bu yüzden önce kendine bağlanıp thread'i uyandırır, thread
        bitmediyse handle'i açık bırakır (süreç kapanınca Windows temizler).
        """
        self._durdu.set()
        thread = self._thread
        self._thread = None
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        if thread is not None and thread.is_alive():
            self._kendine_baglan()
            thread.join(timeout=2.0)
        if thread is None or not thread.is_alive():
            try:
                self._win.CloseHandle(handle)
            except Exception:
                pass

    def _kendine_baglan(self) -> None:
        """Kendine bağlanıp bağlantıyı kapatır: sunucu thread'i ConnectNamedPipe'den çıkar."""
        try:
            istemci = self._win.CreateFile(
                self.ad,
                self._win.GENERIC_READ | self._win.GENERIC_WRITE,
                0,
                None,
                self._win.OPEN_EXISTING,
                0,
                None,
            )
        except Exception:
            return
        try:
            self._win.CloseHandle(istemci)
        except Exception:
            pass

    # ---- sunucu döngüsü ----

    def _dongu(self) -> None:
        while not self._durdu.is_set():
            try:
                self._win.ConnectNamedPipe(self._handle, None)
            except Exception as e:
                if self._durdu.is_set():
                    break
                if getattr(e, "winerror", None) != ERROR_PIPE_CONNECTED:
                    # Boru hâlâ bekliyor (ya da geçici hata): tekrar dene.
                    continue
                # İstemci ConnectNamedPipe çağrısından önce bağlandı: yine de işle.
            try:
                self._baglanti_isle()
            except Exception:
                pass
            finally:
                try:
                    self._win.DisconnectNamedPipe(self._handle)
                except Exception:
                    pass

    def _baglanti_isle(self) -> None:
        try:
            istek = self._oku()
        except _HataliIstek as e:
            self._yaz({"ok": False, "hata": e.mesaj})
            self._istemciyi_bekle()
            return
        try:
            sonuc = self.isleyici(istek)
        except Exception:
            sonuc = {"ok": False, "hata": "iç hata"}
        if not isinstance(sonuc, dict):
            sonuc = {"ok": False, "hata": "iç hata"}
        self._yaz(sonuc)
        self._istemciyi_bekle()

    def _istemciyi_bekle(self) -> None:
        """İstemci yanıtı okuyup bağlantıyı kapattıktan sonra ayır.

        Windows'ta bağlantı ayrılınca istemcideki okunmamış veri KAYBOLUR
        (ERROR_BROKEN_PIPE); bu yüzden yanıt yazıldıktan sonra istemci
        kapanana kadar beklenir.
        """
        while True:
            try:
                veri = _veri(self._win.ReadFile(self._handle, 1024))
            except Exception:
                return
            if not veri:
                return

    def _oku(self) -> dict:
        """Tek satır JSON isteği okur; hatalı/çok büyük istekte hata fırlatır."""
        ham = b""
        while True:
            parca = _veri(self._win.ReadFile(self._handle, BUFER_BOYUTU))
            if not parca:
                break
            ham += parca
            if len(ham) > EN_FAZLA_ISTEK:
                raise _HataliIstek("istek çok büyük")
            if b"\n" in ham:
                break
        satir = ham.split(b"\n", 1)[0]
        if not satir:
            raise _HataliIstek("geçersiz istek")
        try:
            istek = json.loads(satir.decode("utf-8"))
        except Exception:
            raise _HataliIstek("geçersiz istek") from None
        if not isinstance(istek, dict):
            raise _HataliIstek("geçersiz istek")
        return istek

    def _yaz(self, veri: dict) -> None:
        yazi = json.dumps(veri, ensure_ascii=False) + "\n"
        try:
            self._win.WriteFile(self._handle, yazi.encode("utf-8"))
        except Exception:
            pass


def _oku_yanit(win: Any, handle: Any, zaman_asimi: float) -> dict:
    """Yanıtı zaman aşımıyla bekler; hata/zaman aşımında hata sözlüğü döner."""
    kutu: "queue.Queue[Any]" = queue.Queue()

    def oku() -> None:
        parca = b""
        try:
            while b"\n" not in parca:
                veri = _veri(win.ReadFile(handle, BUFER_BOYUTU))
                if not veri:
                    break
                parca += veri
        except Exception as e:
            kutu.put(e)
            return
        kutu.put(parca)

    threading.Thread(target=oku, daemon=True).start()
    try:
        veri = kutu.get(timeout=max(0.01, zaman_asimi))
    except queue.Empty:
        return {"ok": False, "hata": "zaman aşımı"}
    if isinstance(veri, Exception):
        return {"ok": False, "hata": "tr2en çalışmıyor"}
    try:
        sonuc = json.loads(veri.decode("utf-8", "replace").strip())
    except Exception:
        return {"ok": False, "hata": "geçersiz yanıt"}
    if not isinstance(sonuc, dict):
        return {"ok": False, "hata": "geçersiz yanıt"}
    return sonuc


def _ac(win: Any, ad: str, son: float) -> Any:
    """Boruya bağlanır; boru meşgulse (ERROR_PIPE_BUSY) kısa süre bekleyip yeniden dener.

    Sunucu bir önceki bağlantıyı henüz ayırmışsa boru "meşgul" görünür.
    """
    while True:
        try:
            return win.CreateFile(
                ad,
                win.GENERIC_READ | win.GENERIC_WRITE,
                0,
                None,
                win.OPEN_EXISTING,
                0,
                None,
            )
        except Exception as e:
            if getattr(e, "winerror", None) != ERROR_PIPE_BUSY:
                raise
            if time.monotonic() >= son:
                raise
            time.sleep(0.05)


def istek(
    veri: dict,
    zaman_asimi: float = ZAMAN_ASIMI_SN,
    *,
    ad: str = BORU_ADI,
    _win: Any | None = None,
) -> dict:
    """Ana sürece istek gönderir, yanıtı döner (hata fırlatmaz).

    Boru yoksa ``{"ok": False, "hata": "tr2en çalışmıyor"}``, zaman aşımında
    ``{"ok": False, "hata": "zaman aşımı"}`` döner.
    """
    try:
        win = _win if _win is not None else _gercek_win()
    except Exception:
        return {"ok": False, "hata": "tr2en çalışmıyor"}
    son = time.monotonic() + max(0.05, zaman_asimi)
    handle = None
    try:
        handle = _ac(win, ad, son)
    except Exception:
        return {"ok": False, "hata": "tr2en çalışmıyor"}
    try:
        yazi = json.dumps(veri, ensure_ascii=False) + "\n"
        win.WriteFile(handle, yazi.encode("utf-8"))
    except Exception:
        _kapat(win, handle)
        return {"ok": False, "hata": "tr2en çalışmıyor"}
    try:
        return _oku_yanit(win, handle, max(0.05, son - time.monotonic()))
    finally:
        _kapat(win, handle)


def _kapat(win: Any, handle: Any) -> None:
    """Handle'ı kapatır; hata yutulur."""
    try:
        win.CloseHandle(handle)
    except Exception:
        pass
