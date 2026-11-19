"""Çevirmen zincirini kuran ve dil kontrolüyle çeviren ortak giriş noktası (CLI ve uygulama kullanır)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .cevirmen import CeviriHatasi, CevirmenZinciri
from .bolme import parcala
from .dil import harf_var_mi, ingilizce_var_mi, turkce_mi
from .gemini import GeminiCevirmen
from .korumalar import KorumaliCevirmen
from .sozluk import SozlukluCevirmen
from .uyumlu import UyumluCevirmen
from .yerel import YerelCevirmen
from .servisler import BULUT_SERVIS_ADLARI


def zincir_kur(model: str = "gemini-3.5-flash-lite", yalniz: str | None = None,
               korumasiz: bool = False, zaman_asimi: float = 4.0,
               uyumlu_adres: str = "", uyumlu_model: str = "", uyumlu_anahtar: str = "",
               uyumlu_zaman_asimi: float = 15.0, uyumlu_dusunmeyi_kapat: bool = False) -> CevirmenZinciri:
    gemini = GeminiCevirmen(model=model, zaman_asimi=zaman_asimi)
    yerel = SozlukluCevirmen(YerelCevirmen())  # sözlük yalnızca yerel modele (Gemini terimleri zaten biliyor)
    if yalniz == "uyumlu":
        if not (uyumlu_adres and uyumlu_model):
            raise CeviriHatasi("kendi modeliniz tanımlı değil: ayar dosyasında uyumlu_adres ve uyumlu_model")
        uyumlu = UyumluCevirmen(adres=uyumlu_adres, model=uyumlu_model,
                                anahtar_degiskeni=uyumlu_anahtar, zaman_asimi=uyumlu_zaman_asimi,
                                dusunmeyi_kapat=uyumlu_dusunmeyi_kapat)
        cevirmenler = [uyumlu, yerel]
    else:
        cevirmenler = {"gemini": [gemini], "yerel": [yerel]}.get(yalniz or "", [gemini, yerel])
    if not korumasiz:
        cevirmenler = [KorumaliCevirmen(c) for c in cevirmenler]
    return CevirmenZinciri(cevirmenler)


def zincir_kur_v2(ayar: dict, anahtar_saglayici: Callable[[str], str | None],
                  korumasiz: bool = False) -> CevirmenZinciri:
    """Şema 2 ayarlarından ("bulut"/"yerel") çevirmen zinciri kurar.

    Anahtarları keyring'den okumaz; anahtarı yalnızca anahtar_saglayici(servis)
    çağrısıyla alır. Geçersiz yapılandırmada CeviriHatasi fırlatır.
    """
    cevirmen = ayar.get("cevirmen", "bulut")
    cevirmenler: list = []
    if cevirmen == "bulut":
        servis = ayar.get("bulut_servis", "gemini")
        if servis == "gemini":
            model = ayar.get("bulut_model") or ayar.get("gemini_model") or ""
            cevirmenler.append(GeminiCevirmen(
                model=model,
                zaman_asimi=ayar.get("zaman_asimi", 4.0),
                anahtar_saglayici=lambda: anahtar_saglayici("gemini")))
        elif servis in BULUT_SERVIS_ADLARI or servis == "diger":
            model = ayar.get("bulut_model") or ""
            if not model:
                raise CeviriHatasi("model adı girilmedi")
            if servis == "diger":
                adres = (ayar.get("bulut_adres") or "").rstrip("/")
                if not adres:
                    raise CeviriHatasi("bulut_adres girilmedi")
            else:
                adres = BULUT_SERVIS_ADLARI[servis]
            cevirmenler.append(UyumluCevirmen(
                adres=adres, model=model,
                zaman_asimi=ayar.get("uyumlu_zaman_asimi", 15.0),
                anahtar_saglayici=lambda s=servis: anahtar_saglayici(s)))
        else:
            raise CeviriHatasi("geçersiz bulut_servis")
        if ayar.get("bulut_yedek_yerel", True):
            cevirmenler.append(SozlukluCevirmen(YerelCevirmen()))
    elif cevirmen == "yerel":
        secili = ayar.get("yerel_secili", "dahili")
        if secili == "dahili":
            cevirmenler.append(SozlukluCevirmen(YerelCevirmen()))
        elif secili in ("ollama", "lmstudio"):
            model = ayar.get(f"{secili}_model") or ""
            if not model:
                raise CeviriHatasi("model adı girilmedi")
            cevirmenler.append(UyumluCevirmen(
                adres=ayar.get(f"{secili}_adres") or "", model=model,
                zaman_asimi=ayar.get("uyumlu_zaman_asimi", 15.0),
                dusunmeyi_kapat=bool(ayar.get("uyumlu_dusunmeyi_kapat", False))))
        elif secili == "klasor":
            yol = ayar.get("klasor_yolu") or ""
            if not yol:
                raise CeviriHatasi("model klasörü belirtilmedi")
            cevirmenler.append(SozlukluCevirmen(YerelCevirmen(model_klasoru=yol)))
        else:
            raise CeviriHatasi("geçersiz yerel_secili")
    else:
        raise CeviriHatasi("geçersiz cevirmen")
    if not korumasiz:
        cevirmenler = [KorumaliCevirmen(c) for c in cevirmenler]
    return CevirmenZinciri(cevirmenler)


@dataclass
class Sonuc:
    metin: str
    durum: str  # "cevrildi" | "zaten-ingilizce" | "bos"
    cevirmen: str | None = None


def _turkce_var_mi(metin: str) -> bool:
    """Bütün metin ya da cümlelerinden biri Türkçe mi? Önceki çeviriyle karışık seçimde
    ("Hello, how are you? bugün ne yemek istersin") bütün metnin puanı İngilizceye kayıyordu (19.11.2026)."""
    if turkce_mi(metin):
        return True
    return any(turkce_mi(p) for satir in parcala(metin) for p in satir)


def akilli_cevir(zincir: CevirmenZinciri, metin: str, dil_kontrolu: bool = True) -> Sonuc:
    """Türkçe değilse ve İngilizce olduğu kesinse dokunmaz; çeviremezse CeviriHatasi fırlatır."""
    if not metin.strip():
        return Sonuc(metin, "bos")
    if dil_kontrolu and not _turkce_var_mi(metin) and (ingilizce_var_mi(metin) or not harf_var_mi(metin)):
        return Sonuc(metin, "zaten-ingilizce")
    return Sonuc(zincir.cevir(metin), "cevrildi", zincir.son_kullanilan)
