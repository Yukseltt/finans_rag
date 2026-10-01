# Chunk'larin her modelin tokenizer'inda kac token ettigini olcer; 512 sinirli modellerde
# kesilme olup olmadigini gosterir (Karar 5 revizesindeki zorunlu dogrulama).
#
# Kullanim: python src/chunk_kontrol.py
# Girdi:    data/islenmis/chunks.jsonl
# Cikti:    ekrana ozet + sonuclar/chunk_token_kontrol.json
#
# Sadece tokenizer indirilir (model agirligi degil). Pasaj oneki de sayilir, cunku
# e5 gibi modeller pasajin basina metin ekler ve bu da sinira dahildir.
import json
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

KOK = Path(__file__).resolve().parent.parent
CHUNKS = KOK / "data" / "islenmis" / "chunks.jsonl"
CIKTI = KOK / "sonuclar" / "chunk_token_kontrol.json"

# (model, maks. uzunluk, pasaj oneki). Oneklerin kaynagi: model kartlari (Karar 3).
MODELLER = [
    ("BAAI/bge-m3", 8192, ""),
    ("BAAI/bge-base-en-v1.5", 512, ""),
    ("intfloat/e5-base-v2", 512, "passage: "),
    ("Alibaba-NLP/gte-base-en-v1.5", 8192, ""),
]


def main():
    metinler = [json.loads(s)["metin"] for s in open(CHUNKS, encoding="utf-8")]
    print(f"{len(metinler)} chunk")
    rapor = {}
    for model, sinir, onek in MODELLER:
        tok = AutoTokenizer.from_pretrained(model)
        uzunluk = np.array([len(x) for x in tok([onek + m for m in metinler], add_special_tokens=True)["input_ids"]])
        asan = int((uzunluk > sinir).sum())
        rapor[model] = {"sinir": sinir, "medyan": int(np.median(uzunluk)), "p99": int(np.percentile(uzunluk, 99)),
                        "maks": int(uzunluk.max()), "sinir_asan": asan,
                        "sinir_asan_oran": round(asan / len(uzunluk), 4)}
        r = rapor[model]
        print(f"{model:32s} sinir={sinir:5d} medyan={r['medyan']:4d} p99={r['p99']:4d} maks={r['maks']:5d} "
              f"asan={asan} (%{100 * asan / len(uzunluk):.2f})")
    CIKTI.write_text(json.dumps(rapor, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
