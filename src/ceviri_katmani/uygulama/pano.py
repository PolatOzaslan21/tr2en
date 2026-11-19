"""Windows pano yardımcıları: biçim koruyan yedek, metin erişimi ve tuş gönderimi."""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

WIN32 = sys.platform == "win32"

if WIN32:
    import win32clipboard
    import win32con

__all__ = [
    "PanoYedegi",
    "geri_sil",
    "metin_al",
    "metin_koy",
    "secimi_kopyala",
    "sira_no",
    "yapistir",
]

_DENEME = 20
_ARALIK = 0.01


def _win_denetle() -> None:
    if not WIN32:
        raise NotImplementedError("Pano yardımcıları yalnızca Windows'ta çalışır")


def _pano_ac() -> None:
    """Panoyu aç; meşgulse 10 ms aralıkla 20 kez dener."""
    _win_denetle()
    son_hata: Exception | None = None
    for _ in range(_DENEME):
        try:
            win32clipboard.OpenClipboard(None)
            return
        except Exception as hata:  # pywintypes.error
            son_hata = hata
            time.sleep(_ARALIK)
    raise OSError("Pano açılamadı") from son_hata


class PanoYedegi:
    """Panodaki tüm biçimleri saklayıp sonra geri yükler."""

    def __init__(self) -> None:
        self._veriler: dict[int, object] = {}
        self._kaydedildi = False

    def kaydet(self) -> None:
        _pano_ac()
        veriler: dict[int, object] = {}
        try:
            bicim = 0
            while True:
                bicim = win32clipboard.EnumClipboardFormats(bicim)
                if not bicim:
                    break
                try:
                    veriler[bicim] = win32clipboard.GetClipboardData(bicim)
                except Exception:
                    continue
        finally:
            _pano_kapat()
        self._veriler = veriler
        self._kaydedildi = True

    def geri_yukle(self) -> bool:
        """Pano yedeğini geri yükler; herhangi bir biçim yazılamazsa False döner.

        Kısmi başarısızlık da başarısızlıktır: çağıran (ana.py) kullanıcıyı
        "Panonuz tam geri yüklenemedi" uyarısıyla bilgilendirir (INCELEME-1 bulgu 2).
        """
        if not WIN32:
            raise NotImplementedError("Pano yardımcıları yalnızca Windows'ta çalışır")
        if not self._kaydedildi:
            return False
        try:
            _pano_ac()
        except Exception:
            return False
        try:
            try:
                win32clipboard.EmptyClipboard()
            except Exception:
                return False
            basarili = True
            for bicim, veri in self._veriler.items():
                try:
                    win32clipboard.SetClipboardData(bicim, veri)
                except Exception:
                    # Bu biçim geri yüklenemedi; diğerleri yine denenir,
                    # ama sonuç başarısızdır (kullanıcı bilgilendirilir).
                    basarili = False
                    continue
            return basarili
        except Exception:
            return False
        finally:
            _pano_kapat()


def _pano_kapat() -> None:
    try:
        win32clipboard.CloseClipboard()
    except Exception:
        pass


def sira_no() -> int:
    """Pano sıra numarası; her değişimde artar."""
    _win_denetle()
    return win32clipboard.GetClipboardSequenceNumber()


def metin_al() -> str | None:
    """CF_UNICODETEXT içeriği; yoksa None."""
    _pano_ac()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return None
        veri = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return veri if isinstance(veri, str) else None
    except Exception:
        return None
    finally:
        _pano_kapat()


def metin_koy(metin: str) -> None:
    """Panoyu verilen metinle değiştirir (CF_UNICODETEXT)."""
    _pano_ac()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, metin)
    finally:
        _pano_kapat()


def _sira_degisimini_bekle(
    ilk: int,
    bekle_ms: int = 300,
    *,
    sira_oku=sira_no,
    uyku=time.sleep,
    adim_ms: int = 10,
) -> bool:
    """Sıra numarası değişene kadar bekler; değişmezse False."""
    bitis = time.monotonic() + max(0, bekle_ms) / 1000
    while True:
        if sira_oku() != ilk:
            return True
        if time.monotonic() >= bitis:
            return False
        uyku(adim_ms / 1000)


_kontrolcu = None


def _klavye():
    global _kontrolcu
    if _kontrolcu is None:
        from pynput.keyboard import Controller

        _kontrolcu = Controller()
    return _kontrolcu


def _tuslari_birak(k) -> None:
    """Kısayoldan basılı kalmış Shift/Alt/Ctrl/Win tuşlarını bırakır."""
    from pynput.keyboard import Key

    for ad in (
        "shift", "shift_l", "shift_r",
        "alt", "alt_l", "alt_r",
        "ctrl", "ctrl_l", "ctrl_r",
        "cmd", "cmd_l", "cmd_r",
    ):
        tus = getattr(Key, ad, None)
        if tus is None:
            continue
        try:
            k.release(tus)
        except Exception:
            pass


def _ctrl_tus(karakter: str) -> None:
    from pynput.keyboard import Key

    k = _klavye()
    _tuslari_birak(k)
    with k.pressed(Key.ctrl):
        k.press(karakter)
        k.release(karakter)


def secimi_kopyala(bekle_ms: int = 300) -> str | None:
    """Ctrl+C gönderir, pano değişene kadar bekler; değişmezse None."""
    _win_denetle()
    ilk = sira_no()
    _ctrl_tus("c")
    if not _sira_degisimini_bekle(ilk, bekle_ms):
        return None
    return metin_al()


def yapistir() -> None:
    """Ctrl+V gönderir (önce basılı kalmış değiştirici tuşları bırakır)."""
    _win_denetle()
    _ctrl_tus("v")


_VK_BACK = 0x08
_KEYEVENTF_KEYUP = 0x0002
_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_INPUT_KEYBOARD = 1


def geri_sil(adet: int) -> None:
    """adet kez Backspace; tek SendInput dizisiyle hızlıca."""
    _win_denetle()
    if adet <= 0:
        return
    k = _klavye()
    _tuslari_birak(k)
    dizi = (_INPUT * (adet * 2))()
    for i in range(adet):
        bas = dizi[i * 2]
        bas.type = _INPUT_KEYBOARD
        bas.ki.wVk = _VK_BACK
        birak = dizi[i * 2 + 1]
        birak.type = _INPUT_KEYBOARD
        birak.ki.wVk = _VK_BACK
        birak.ki.dwFlags = _KEYEVENTF_KEYUP
    gonderilen = ctypes.windll.user32.SendInput(
        adet * 2, dizi, ctypes.sizeof(_INPUT)
    )
    if gonderilen != adet * 2:
        from pynput.keyboard import Key

        for _ in range(adet):
            k.press(Key.backspace)
            k.release(Key.backspace)
