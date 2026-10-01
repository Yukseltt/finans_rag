# Sonuclarin uretildigi ortami kaydeder (python, kutuphane surumleri, GPU).
#
# Neden: requirements.txt "ne kurulmali"yi soyler, bu dosya "sonuclar neyle uretildi"yi kaydeder.
# Yerel ortam ile requirements arasinda fark olursa (orn. torch derlemesi) burada gorunur.
#
# Kullanim: python src/ortam_kaydi.py
# Cikti:    sonuclar/ortam.json
import importlib.metadata as md
import json
import platform
import subprocess
from datetime import date
from pathlib import Path

import torch

KOK = Path(__file__).resolve().parent.parent
PAKETLER = ["sentence-transformers", "transformers", "torch", "rank-bm25", "pymupdf", "numpy", "tokenizers"]


def main():
    gpu = None
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        surucu = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                capture_output=True, text=True).stdout.strip()
        gpu = {"ad": p.name, "bellek_gb": round(p.total_memory / 2**30, 1), "cuda": torch.version.cuda,
               "surucu": surucu, "hesaplama_yetenegi": f"{p.major}.{p.minor}"}
    kayit = {"tarih": date.today().isoformat(), "python": platform.python_version(), "isletim_sistemi": platform.platform(),
             "paketler": {p: md.version(p) for p in PAKETLER}, "gpu": gpu}
    (KOK / "sonuclar" / "ortam.json").write_text(json.dumps(kayit, indent=2), encoding="utf-8")
    print(json.dumps(kayit, indent=2))


if __name__ == "__main__":
    main()
