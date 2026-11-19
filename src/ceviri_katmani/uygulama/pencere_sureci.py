"""Ayar penceresini ayrı süreçte pywebview ile açar.

Ana uygulama bu modülü ayrı bir süreçte çalıştırır; pencere kapanınca süreç
biter. Tek pencere kuralı: named mutex zaten varsa başlığı ``PENCERE_BASLIGI``
olan açık pencere öne getirilir ve 0 döner. WebView2 yoksa ya da pencere
açılamazsa 2 döner (çağıran tepsi kipinde kalır); hata yalnızca stderr'e yazılır.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import ayarlar as ayar_modulu
from . import sinyal
from . import tek_ornek
from .pencere_api import PencereApi

MUTEX_ADI = "Local\\Tr2enAyarPenceresi"
PENCERE_BASLIGI = "tr2en Ayarlar"
GENISLIK, YUKSEKLIK = 820, 600
MIN_GENISLIK, MIN_YUKSEKLIK = 720, 520


def _gercek_gui() -> SimpleNamespace:
    import win32con
    import win32gui

    return SimpleNamespace(
        FindWindow=win32gui.FindWindow,
        SetForegroundWindow=win32gui.SetForegroundWindow,
        ShowWindow=win32gui.ShowWindow,
        IsIconic=win32gui.IsIconic,
        SW_RESTORE=win32con.SW_RESTORE,
    )


def _one_getir(baslik: str, *, gui=None) -> None:
    """Açık pencereyi bulur, küçülmüşse geri açar ve öne getirir.

    ``gui`` test için: FindWindow, SetForegroundWindow, ShowWindow, IsIconic ve
    SW_RESTORE özniteliklerine sahip sahte nesne. Hata olursa sessiz geçilir.
    """
    if gui is None:
        if sys.platform != "win32":
            return
        gui = _gercek_gui()
    try:
        hwnd = gui.FindWindow(None, baslik)
        if not hwnd:
            return
        if gui.IsIconic(hwnd):
            gui.ShowWindow(hwnd, gui.SW_RESTORE)
        gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _ayarlar_html(sihirbaz: bool = False) -> str:
    """Ayar penceresinin URL'si; ``sihirbaz`` ise ilk açılış sihirbazını açar."""
    url = (Path(__file__).resolve().parent / "arayuz" / "ayarlar.html").as_uri()
    if sihirbaz:
        url += "#sihirbaz"
    return url


def calistir(
    argv: list[str] | None = None,
    *,
    webview_modulu: Any | None = None,
    api: Any | None = None,
    kilit: Any | None = None,
) -> int:
    """Ayar penceresini açar; bitince dönen çıkış kodu.

    ``webview_modulu``: sahte/enjekte webview modülü (varsayılan: gerçek
    pywebview). ``api``: JS köprüsü (varsayılan: PencereApi); verilirse yanına
    ``pencereyi_kapat`` eklenir. ``kilit``: zaten alınmış mutex handle'ı
    (testler için); None ise named mutex alınır. Zaten açık pencere varsa
    öne getirilir ve 0 döner; WebView2/pencere hatasında 2 döner.
    ``argv`` içinde ``--sihirbaz`` varsa pencere ilk açılış sihirbazıyla açılır.
    """
    sihirbaz = "--sihirbaz" in (argv or [])
    kilit_nesnesi = tek_ornek.kilit_al(MUTEX_ADI) if kilit is None else kilit
    if kilit_nesnesi is None:
        _one_getir(PENCERE_BASLIGI)
        return 0
    try:
        webview = webview_modulu
        if webview is None:
            try:
                import webview as gercek_webview
            except Exception as e:
                print(f"pywebview yüklenemedi: {e}", file=sys.stderr)
                return 2
            webview = gercek_webview

        pencere_kutu: list[Any] = []
        kapat_izinli = threading.Event()

        def pencereyi_kapat() -> dict:
            pencere = pencere_kutu[0] if pencere_kutu else None
            if pencere is None:
                return {"ok": False, "hata": "pencere açık değil"}
            kapat_izinli.set()
            try:
                pencere.destroy()
            except Exception as e:
                return {"ok": False, "hata": f"pencere kapatılamadı: {type(e).__name__}"}
            return {"ok": True}

        def klasor_secici() -> str | None:
            pencere = pencere_kutu[0] if pencere_kutu else None
            if pencere is None:
                return None
            try:
                sonuc = pencere.create_file_dialog(webview.FOLDER_DIALOG)
            except Exception:
                return None
            if not sonuc:
                return None
            return str(sonuc[0])

        if api is None:
            api = PencereApi(sinyal_gonder=sinyal.gonder, klasor_secici=klasor_secici)
        api.pencereyi_kapat = pencereyi_kapat

        try:
            pencere = webview.create_window(
                PENCERE_BASLIGI,
                url=_ayarlar_html(sihirbaz),
                js_api=api,
                width=GENISLIK,
                height=YUKSEKLIK,
                min_size=(MIN_GENISLIK, MIN_YUKSEKLIK),
            )
            pencere_kutu.append(pencere)

            def kapatma_olayi() -> bool:
                if kapat_izinli.is_set():
                    return True
                sor = True
                try:
                    ayar, _ = ayar_modulu.yukle(getattr(api, "ayar_yolu", None))
                    sor = bool(ayar.get("kapatinca_sor", True))
                except Exception:
                    sor = True
                if not sor:
                    return True

                def sor_js() -> None:
                    try:
                        pencere.evaluate_js("kapatmaSor()")
                    except Exception:
                        pass

                threading.Thread(target=sor_js, daemon=True).start()
                return False

            pencere.events.closing += kapatma_olayi
            webview.start(gui="edgechromium")
        except Exception as e:
            print(f"ayar penceresi açılamadı: {e}", file=sys.stderr)
            return 2
        return 0
    finally:
        try:
            tek_ornek.kilit_birak(kilit_nesnesi)
        except Exception:
            pass
