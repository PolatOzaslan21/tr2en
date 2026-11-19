"""boru.py testleri — sahte win32 ile; gerçek named pipe AÇILMAZ/KURULMAZ.

Ağ, gerçek boru ve gerçek pencere yoktur: her şey sahte `_win` nesnesiyle
taklit edilir.
"""
from __future__ import annotations

import re
import threading
import time

import pytest

from ceviri_katmani.uygulama import boru


# ---- sahte boru ----


class _Kayit:
    """Bir boru adına karşılık gelen sunucu kaydı."""

    def __init__(self, ad: str) -> None:
        self.ad = ad
        self.baglanti: "_IstemciHandle | None" = None
        self.baglanti_sayisi = 0
        self.servilen = 0
        self.kapandi = False
        self.durduruldu = False


class _SunucuHandle:
    def __init__(self, kayit: _Kayit) -> None:
        self.kayit = kayit


class _IstemciHandle:
    def __init__(self, kayit: _Kayit) -> None:
        self.kayit = kayit
        self.istek = b""
        self.istek_hazir = threading.Event()
        self.yanit = b""
        self.yanit_hazir = threading.Event()


class SahteBoru:
    """Tek süreçte çalışan sahte named pipe (sunucu + istemci tarafı)."""

    PIPE_ACCESS_DUPLEX = 1
    PIPE_TYPE_MESSAGE = 2
    PIPE_READMODE_MESSAGE = 4
    PIPE_WAIT = 0
    PIPE_UNLIMITED_INSTANCES = 255
    GENERIC_READ = 1
    GENERIC_WRITE = 2
    OPEN_EXISTING = 3

    def __init__(self) -> None:
        self.kayitlar: dict[str, _Kayit] = {}
        self.kilit = threading.Lock()
        self.yanit_gelmez = False

    # ---- sunucu tarafı ----

    def CreateNamedPipe(self, ad, *_args, **_kw):
        with self.kilit:
            self.kayitlar[ad] = _Kayit(ad)
        return _SunucuHandle(self.kayitlar[ad])

    def ConnectNamedPipe(self, handle, _overlapped=None):
        """Yeni bir istemci bağlanana kadar bekler (kendine bağlanma da sayılır)."""
        kayit = handle.kayit
        while kayit.baglanti_sayisi <= kayit.servilen:
            if kayit.durduruldu:
                raise RuntimeError("bağlantı yok")
            time.sleep(0.005)
        kayit.servilen = kayit.baglanti_sayisi

    def DisconnectNamedPipe(self, handle):
        """Sunucu bağlantıyı ayırır; istemcinin handle'ı kendi durumunu yönetir."""
        return None

    def _sunucu_oku(self, handle):
        """Sunucu okuması: istek gelene kadar bekler, sonra bağlantı kapanana dek bekler."""
        kayit = handle.kayit
        while kayit.baglanti is None and not kayit.kapandi:
            if kayit.durduruldu:
                return (0, b"")
            time.sleep(0.005)
        istemci = kayit.baglanti
        if istemci is None:
            return (0, b"")  # istemci kapandı: EOF
        while not istemci.istek_hazir.is_set():
            if kayit.baglanti is not istemci:
                return (0, b"")
            time.sleep(0.005)
        veri = istemci.istek
        istemci.istek = b""
        istemci.istek_hazir.clear()
        return (0, veri)

    def _sunucu_yaz(self, handle, veri):
        if self.yanit_gelmez:
            return
        istemci = handle.kayit.baglanti
        if istemci is None:
            return
        istemci.yanit += veri
        istemci.yanit_hazir.set()

    # ---- istemci tarafı ----

    def CreateFile(self, ad, *_args, **_kw):
        with self.kilit:
            kayit = self.kayitlar.get(ad)
        if kayit is None:
            raise OSError(2, "dosya bulunamadı")
        # Boru kuyruğu: bağlantı varken yeni istemci sıraya girer.
        son = time.time() + 5.0
        while kayit.baglanti is not None:
            if time.time() > son:
                raise OSError(231, "boru meşgul")
            time.sleep(0.005)
        istemci = _IstemciHandle(kayit)
        kayit.baglanti = istemci
        kayit.kapandi = False
        kayit.baglanti_sayisi += 1
        return istemci

    def _istemci_oku(self, handle):
        while not handle.yanit_hazir.is_set():
            time.sleep(0.005)
        veri = handle.yanit
        handle.yanit = b""
        return (0, veri)

    def _istemci_yaz(self, handle, veri):
        handle.istek += veri
        handle.istek_hazir.set()

    # ---- ortak ----

    def ReadFile(self, handle, _boyut):
        if isinstance(handle, _IstemciHandle):
            return self._istemci_oku(handle)
        return self._sunucu_oku(handle)

    def WriteFile(self, handle, veri):
        if isinstance(handle, _IstemciHandle):
            self._istemci_yaz(handle, veri)
            return
        self._sunucu_yaz(handle, veri)

    def CloseHandle(self, handle):
        if isinstance(handle, _IstemciHandle):
            # İstemci kapandı: sunucu bunu EOF olarak görür.
            handle.kayit.baglanti = None
            handle.kayit.kapandi = True
        else:
            handle.kayit.durduruldu = True
            with self.kilit:
                if self.kayitlar.get(handle.kayit.ad) is handle.kayit:
                    del self.kayitlar[handle.kayit.ad]


BORU_ADI = r"\\.\pipe\tr2en-test"


@pytest.fixture
def sahte() -> SahteBoru:
    return SahteBoru()


def sunucu_baslat(sahte: SahteBoru, isleyici, ad: str = BORU_ADI) -> boru.BoruSunucusu:
    sunucu = boru.BoruSunucusu(isleyici, ad=ad, _win=sahte)
    sunucu.baslat()
    return sunucu


# ---- boru adı ----


def test_boru_adi_kullanici_adi_ile():
    assert boru.BORU_ADI.startswith(r"\\.\pipe\tr2en-")
    ek = boru.BORU_ADI[len(r"\\.\pipe\tr2en-"):]
    assert ek
    assert re.fullmatch(r"[A-Za-z0-9_-]+", ek)


def test_kullanici_adi_ayiklanir(monkeypatch):
    monkeypatch.setenv("USERNAME", "Polat Ozaslan! 42")
    assert boru.kullanici_adi() == "PolatOzaslan42"
    monkeypatch.setenv("USERNAME", "")
    assert boru.kullanici_adi() == "kullanici"
    monkeypatch.delenv("USERNAME", raising=False)
    assert boru.kullanici_adi() == "kullanici"


# ---- istek/yanıt ----


def test_istek_yanit_donusu(sahte):
    gorulen: list[dict] = []

    def isleyici(istek: dict) -> dict:
        gorulen.append(istek)
        return {"ok": True, "ceviri": "hello", "durum": "cevrildi"}

    sunucu = sunucu_baslat(sahte, isleyici)
    try:
        sonuc = boru.istek({"tur": "cevir", "metin": "merhaba"}, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
    assert sonuc == {"ok": True, "ceviri": "hello", "durum": "cevrildi"}
    assert gorulen == [{"tur": "cevir", "metin": "merhaba"}]


def test_istemci_boru_yoksa(sahte):
    sonuc = boru.istek({"tur": "durum"}, _win=sahte, ad=r"\\.\pipe\tr2en-yok")
    assert sonuc == {"ok": False, "hata": "tr2en çalışmıyor"}


def test_buyuk_istek_reddedilir(sahte):
    cagrilar: list[dict] = []
    sunucu = sunucu_baslat(sahte, lambda i: cagrilar.append(i) or {"ok": True})
    try:
        sonuc = boru.istek({"tur": "cevir", "metin": "x" * 70_000}, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
    assert sonuc == {"ok": False, "hata": "istek çok büyük"}
    assert cagrilar == []


def test_isleyici_istisnasi_ice_hata(sahte):
    def patlar(_istek: dict) -> dict:
        raise RuntimeError("patladı")

    sunucu = sunucu_baslat(sahte, patlar)
    try:
        sonuc = boru.istek({"tur": "durum"}, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
    assert sonuc == {"ok": False, "hata": "iç hata"}


def test_gecersiz_yanit_hata_doner(sahte):
    sunucu = sunucu_baslat(sahte, lambda i: "metin degil")  # dict olmayan sonuç
    try:
        sonuc = boru.istek({"tur": "durum"}, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
    assert sonuc == {"ok": False, "hata": "iç hata"}


def test_zaman_asimi(sahte):
    sahte.yanit_gelmez = True
    sunucu = sunucu_baslat(sahte, lambda i: {"ok": True})
    try:
        sonuc = boru.istek({"tur": "durum"}, zaman_asimi=0.2, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
    assert sonuc == {"ok": False, "hata": "zaman aşımı"}


def test_sunucu_durduruldu_istemci_calismiyor(sahte):
    sunucu = sunucu_baslat(sahte, lambda i: {"ok": True})
    sunucu.durdur()
    sonuc = boru.istek({"tur": "durum"}, _win=sahte, ad=BORU_ADI)
    assert sonuc == {"ok": False, "hata": "tr2en çalışmıyor"}


class _BoruHatasi(Exception):
    """winerror taşıyan sahte hata (ERROR_PIPE_BUSY taklidi)."""

    def __init__(self, winerror: int) -> None:
        super().__init__("boru hatası")
        self.winerror = winerror


def test_boru_meshgulse_bekleyip_tekrar_denenir(sahte):
    """Sunucu önceki bağlantıyı ayırmamışsa istemci bekler (ERROR_PIPE_BUSY)."""
    gercek = sahte.CreateFile
    durum = {"sayac": 0}

    def meshul_create(ad, *args, **kw):
        durum["sayac"] += 1
        if durum["sayac"] == 1:
            raise _BoruHatasi(231)
        return gercek(ad, *args, **kw)

    sunucu = sunucu_baslat(sahte, lambda i: {"ok": True, "tur": i.get("tur")})
    sahte.CreateFile = meshul_create
    try:
        sonuc = boru.istek({"tur": "durum"}, 5, _win=sahte, ad=BORU_ADI)
    finally:
        sunucu.durdur()
        sahte.CreateFile = gercek
    assert sonuc == {"ok": True, "tur": "durum"}
    assert durum["sayac"] >= 2


def test_boru_yoksa_tekrar_denemez(sahte):
    """Boru hiç yoksa (ERROR_FILE_NOT_FOUND) beklemeden döner."""
    sonuc = boru.istek({"tur": "durum"}, 5, _win=sahte, ad=r"\\.\pipe\tr2en-yok")
    assert sonuc == {"ok": False, "hata": "tr2en çalışmıyor"}


def test_birden_fazla_istek_sirayla_islenir(sahte):
    sayac: list[str] = []

    def isleyici(istek: dict) -> dict:
        sayac.append(istek["tur"])
        return {"ok": True, "tur": istek["tur"]}

    sunucu = sunucu_baslat(sahte, isleyici)
    try:
        for tur in ("durum", "cevir", "aktif_degistir"):
            sonuc = boru.istek({"tur": tur}, _win=sahte, ad=BORU_ADI)
            assert sonuc == {"ok": True, "tur": tur}
    finally:
        sunucu.durdur()
    assert sayac == ["durum", "cevir", "aktif_degistir"]
