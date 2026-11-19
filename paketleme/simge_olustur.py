"""paketleme/tr2en.ico dosyasını koddaki çizimden üretir (derle.ps1 çağırır)."""
from pathlib import Path

from ceviri_katmani.uygulama.simge import ico_kaydet

hedef = Path(__file__).with_name("tr2en.ico")
ico_kaydet(hedef)
print(hedef, hedef.stat().st_size, "bayt")
