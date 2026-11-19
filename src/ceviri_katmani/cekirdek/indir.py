"""Yerel çeviri modelini Hugging Face'ten güvenli indirme."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Callable

import httpx

MODEL_DEPOSU = "PolatOz/tr2en-model"
DEPO_DEGISKENI = "TR2EN_MODEL_DEPOSU"

DOSYALAR: dict[str, tuple[int, str]] = {
    "config.json": (233, "72901fbd8abd89fb5cf4a388f26fc681f5c4c58a1e1a88b30b879f107270e7ee"),
    "model.bin": (237977893, "61df8aed31762eaefa0e3a9807a8caa91894d305a2eb5a56156699d1d1ebfbac"),
    "shared_vocabulary.json": (1170026, "44dd886d9f538a4b22e58d89758bd336e73b06c753a436f7531436daafcaedee"),
    "source.spm": (833378, "a6946a00a5cbd04044bb1c25b48ea798561a2fd12d872e5d1452bdc3dc076e77"),
    "target.spm": (796940, "cfd9506b675c3f26850ae08995f5a7c8baf56db49d9784a80f418fb8a9210d48"),
}

PARCA_BOYU = 1_048_576  # 1 MB
KULLANICI_AGENTI = "tr2en"


class IndirmeHatasi(Exception):
    """Model indirilemedi ya da doğrulanamadı."""


def model_tam_mi(klasor: Path) -> bool:
    """5 dosya var ve boyutları tabloyla aynı mı (SHA hesaplamaz; hızlı kontrol)."""
    klasor = Path(klasor)
    if not klasor.is_dir():
        return False
    for ad, (boyut, _sha) in DOSYALAR.items():
        yol = klasor / ad
        if not yol.is_file():
            return False
        if yol.stat().st_size != boyut:
            return False
    return True


def model_indir(
    klasor: Path,
    *,
    ilerleme: Callable[[int, int], None] | None = None,
    istemci: httpx.Client | None = None,
    depo: str | None = None,
) -> None:
    """Modeli akışla indirir, SHA256 ile doğrular ve atomik olarak hedefe taşır."""
    klasor = Path(klasor)
    depo = depo or os.environ.get(DEPO_DEGISKENI, MODEL_DEPOSU)
    gecici = klasor.parent / (klasor.name + ".indiriliyor")

    klasor.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(gecici, ignore_errors=True)
    gecici.mkdir()

    sahip_istemci = istemci is None
    if sahip_istemci:
        istemci = httpx.Client(
            headers={"User-Agent": KULLANICI_AGENTI},
            follow_redirects=True,
            timeout=httpx.Timeout(10.0, read=60.0),
        )

    toplam = sum(boyut for boyut, _sha in DOSYALAR.values())
    try:
        indirilen = 0
        for ad, (boyut, sha) in DOSYALAR.items():
            url = f"https://huggingface.co/{depo}/resolve/main/{ad}"
            hedef = gecici / ad
            try:
                with istemci.stream("GET", url) as r:
                    if r.status_code != 200:
                        raise IndirmeHatasi(f"{ad} indirilemedi (HTTP {r.status_code})")
                    ozet = hashlib.sha256()
                    alinan = 0
                    with open(hedef, "wb") as f:
                        for parca in r.iter_bytes(PARCA_BOYU):
                            f.write(parca)
                            ozet.update(parca)
                            alinan += len(parca)
                            indirilen += len(parca)
                            if ilerleme is not None:
                                ilerleme(indirilen, toplam)
            except IndirmeHatasi:
                raise
            except OSError as e:
                raise IndirmeHatasi(f"{ad} yazılamadı: {type(e).__name__}") from e
            except httpx.HTTPError as e:
                raise IndirmeHatasi(f"{ad} indirilemedi: {type(e).__name__}") from e
            if alinan != boyut or ozet.hexdigest() != sha:
                raise IndirmeHatasi(f"{ad} doğrulanamadı")

        eski = klasor.parent / (klasor.name + ".eski")
        if klasor.exists():
            shutil.rmtree(eski, ignore_errors=True)
            try:
                os.replace(klasor, eski)
            except OSError as e:
                raise IndirmeHatasi(f"mevcut model yedeklenemedi: {type(e).__name__}") from e
        try:
            os.replace(gecici, klasor)
        except OSError as e:
            if eski.exists() and not klasor.exists():
                try:
                    os.replace(eski, klasor)
                except OSError:
                    pass
            raise IndirmeHatasi(f"model taşınamadı: {type(e).__name__}") from e
        shutil.rmtree(eski, ignore_errors=True)
    except BaseException:
        shutil.rmtree(gecici, ignore_errors=True)
        raise
    finally:
        if sahip_istemci:
            istemci.close()


def main() -> None:
    """CLI: `python -m ceviri_katmani.cekirdek.indir` modeli varsayılan klasöre indirir."""
    from .yerel import _varsayilan_klasor

    klasor = _varsayilan_klasor()
    son_yuzde = -1

    def goster(indirilen: int, toplam: int) -> None:
        nonlocal son_yuzde
        yuzde = int(indirilen * 100 / toplam) if toplam else 100
        if yuzde != son_yuzde:
            son_yuzde = yuzde
            print(f"\r%{yuzde}", end="", flush=True)

    print(f"Yerel model indiriliyor: {klasor}", flush=True)
    try:
        model_indir(klasor, ilerleme=goster)
    except IndirmeHatasi as e:
        print(f"\nHata: {e}", flush=True)
        raise SystemExit(1)
    print("\nTamam.", flush=True)


if __name__ == "__main__":
    main()
