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
    import win32gui
    import win32process

__all__ = [
    "DOGRUDAN_SINIFLAR",
    "PanoYedegi",
    "geri_sil",
    "metin_al",
    "metin_koy",
    "odaktaki_duzenleyici",
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


# ---- Doğrudan pencere mesajı ile düzenleyiciye erişim ----
# Windows 11'in yeni Not Defteri'nde (sınıf "Notepad") gönderilen Ctrl+C /
# Ctrl+V tuşları ulaşmaz: pynput/SendInput tuşları hedef pencereye
# iletilemez. Bu metin alanlarında tuş yerine pencere mesajı
# (WM_COPY / WM_PASTE) gönderilir.

DOGRUDAN_SINIFLAR = frozenset({"RichEditD2DPT"})

_EM_GETSEL = 0x00B0
_WM_COPY = 0x0301
_WM_PASTE = 0x0302
_SMTO_ABORTIFHUNG = 0x0002
_NOTEPAD_SINIF = "Notepad"
_MESAJ_ZAMANI_MS = 1000


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _cvp(deger):
    """None / tam sayı / işaretçiyi c_void_p'ye çevirir."""
    if deger is None:
        return None
    if isinstance(deger, ctypes.c_void_p):
        return deger
    if isinstance(deger, int):
        return ctypes.c_void_p(deger)
    return ctypes.cast(deger, ctypes.c_void_p)


class _WinApi:
    """Windows API sarmalayıcıları; testlerde sahte nesneyle değiştirilir."""

    def __init__(self) -> None:
        self._user32 = None

    def _u32(self):
        if self._user32 is None:
            u32 = ctypes.WinDLL("user32", use_last_error=True)
            u32.GetGUIThreadInfo.argtypes = [
                wintypes.DWORD,
                ctypes.POINTER(_GUITHREADINFO),
            ]
            u32.GetGUIThreadInfo.restype = wintypes.BOOL
            u32.SendMessageTimeoutW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.UINT,
                wintypes.UINT,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            u32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
            self._user32 = u32
        return self._user32

    def on_plan_pencere(self) -> int:
        """Ön plandaki üst düzey pencere; yoksa 0."""
        return int(win32gui.GetForegroundWindow() or 0)

    def sinif_adi(self, hwnd: int) -> str:
        return str(win32gui.GetClassName(hwnd) or "")

    def odak_hwnd(self, hwnd: int) -> int:
        """Ön plan penceresinin iş parçacığında odaklı denetim; yoksa 0."""
        is_parcacik, _surec = win32process.GetWindowThreadProcessId(hwnd)
        if not is_parcacik:
            return 0
        bilgi = _GUITHREADINFO()
        bilgi.cbSize = ctypes.sizeof(_GUITHREADINFO)
        if not self._u32().GetGUIThreadInfo(is_parcacik, ctypes.byref(bilgi)):
            return 0
        return int(bilgi.hwndFocus or 0)

    def cocuklar(self, hwnd: int) -> list[int]:
        """Pencerenin tüm alt pencereleri (torunlar dâhil)."""
        liste: list[int] = []

        def _cb(cocuk, _ek):
            liste.append(int(cocuk))
            return True

        win32gui.EnumChildWindows(hwnd, _cb, None)
        return liste

    def gorunur(self, hwnd: int) -> bool:
        return bool(win32gui.IsWindowVisible(hwnd))

    def secim_araligi(self, hwnd: int) -> tuple[int, int] | None:
        """EM_GETSEL ile (baş, son); okunamazsa None."""
        bas = ctypes.c_uint32(0)
        son = ctypes.c_uint32(0)
        ok, paket = self._mesaj(
            hwnd,
            _EM_GETSEL,
            ctypes.cast(ctypes.pointer(bas), ctypes.c_void_p),
            ctypes.cast(ctypes.pointer(son), ctypes.c_void_p),
        )
        if not ok:
            return None
        if bas.value == son.value:
            # Bazı denetimler aralığı yalnızca dönüş değerinde verir.
            p_bas = paket & 0xFFFF
            p_son = (paket >> 16) & 0xFFFF
            if p_son > p_bas:
                return (p_bas, p_son)
        return (int(bas.value), int(son.value))

    def kopyala(self, hwnd: int) -> bool:
        """WM_COPY gönderir; başarılıysa True."""
        ok, _ = self._mesaj(hwnd, _WM_COPY)
        return ok

    def yapistir(self, hwnd: int) -> bool:
        """WM_PASTE gönderir; başarılıysa True."""
        ok, _ = self._mesaj(hwnd, _WM_PASTE)
        return ok

    def _mesaj(self, hwnd, mesaj, wparam=None, lparam=None) -> tuple[bool, int]:
        """SendMessageTimeoutW ile mesaj gönderir: (başarılı, dönüş değeri)."""
        sonuc = ctypes.c_size_t(0)
        ok = self._u32().SendMessageTimeoutW(
            int(hwnd),
            int(mesaj),
            _cvp(wparam),
            _cvp(lparam),
            _SMTO_ABORTIFHUNG,
            _MESAJ_ZAMANI_MS,
            ctypes.byref(sonuc),
        )
        return bool(ok), int(sonuc.value)


_api = _WinApi()


def odaktaki_duzenleyici() -> int | None:
    """Odaktaki doğrudan düzenlenebilir denetimin HWND'si; yoksa None.

    Önce odak denetiminin sınıfı DOGRUDAN_SINIFLAR'da mı bakılır; değilse
    ön plan penceresi "Notepad" ise onun görünür alt pencereleri içinde
    ilk DOGRUDAN_SINIFLAR sınıfındaki pencere seçilir. Her Windows çağrısı
    hata verirse None döner (istisna fırlatılmaz).
    """
    try:
        on_plan = _api.on_plan_pencere()
        if not on_plan:
            return None
        odak = _api.odak_hwnd(on_plan)
        if odak and _api.sinif_adi(odak) in DOGRUDAN_SINIFLAR:
            return int(odak)
        if _api.sinif_adi(on_plan) != _NOTEPAD_SINIF:
            return None
        for cocuk in _api.cocuklar(on_plan):
            if not _api.gorunur(cocuk):
                continue
            if _api.sinif_adi(cocuk) in DOGRUDAN_SINIFLAR:
                return int(cocuk)
        return None
    except Exception:
        return None


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
    """Seçimi kopyalar; pano değişene kadar bekler, değişmezse None.

    Doğrudan düzenlenebilir denetim (ör. Windows 11 yeni Not Defteri)
    varsa WM_COPY mesajı gönderilir; yoksa Ctrl+C tuşları basılır.
    """
    _win_denetle()
    hedef = odaktaki_duzenleyici()
    if hedef is not None:
        try:
            aralik = _api.secim_araligi(hedef)
        except Exception:
            return None
        if not aralik:
            return None
        bas, son = aralik
        if bas == son:
            return None  # seçim yok: beklemeden çık
        ilk = sira_no()
        try:
            if not _api.kopyala(hedef):
                return None
        except Exception:
            return None
        if not _sira_degisimini_bekle(ilk, bekle_ms):
            return None
        return metin_al()
    ilk = sira_no()
    _ctrl_tus("c")
    if not _sira_degisimini_bekle(ilk, bekle_ms):
        return None
    return metin_al()


def yapistir() -> None:
    """Panodaki metni yapıştırır.

    Doğrudan düzenlenebilir denetim varsa WM_PASTE mesajı gönderilir;
    yoksa Ctrl+V tuşları basılır (önce basılı kalmış değiştirici tuşları
    bırakılır).
    """
    _win_denetle()
    hedef = odaktaki_duzenleyici()
    if hedef is not None:
        try:
            _api.yapistir(hedef)
        except Exception:
            pass
        return
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
