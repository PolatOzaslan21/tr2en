"""Windows toast bildirimleri — hata asla yukarı çıkmaz."""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

if sys.platform == "win32":
    from winotify import Notification, audio
else:  # pragma: no cover
    Notification = None
    audio = None


def bildir(baslik: str, mesaj: str = "", seviye: str = "bilgi") -> None:
    """Winotify ile toast gösterir; çalışmazsa/desteklenmiyorsa sessizce loglar."""
    if sys.platform != "win32":
        raise NotImplementedError("bildir yalnızca Windows'ta çalışır")
    try:
        toast = Notification(app_id="Ceviri Katmani", title=baslik, msg=mesaj)
        if seviye == "hata":
            toast.set_audio(audio.MSError, loop=False)
        elif seviye == "uyari":
            toast.set_audio(audio.Default, loop=False)
        else:
            toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception as e:  # pragma: no cover
        log.warning("Bildirim gösterilemedi: %s", e)
