# Sayfa metinlerini sabit kelime sayisinda chunk'lara boler (baseline, Karar 5).
#
# Kullanim: python src/chunk.py
# Girdi:    data/islenmis/sayfalar/*.jsonl   (pdf_parse.py ciktisi)
# Cikti:    data/islenmis/chunks.jsonl       (satir basina bir chunk)
#
# Kurallar (sifir noktasi, bilerek basit):
#   - chunk uzunlugu KELIME sayisiyla olculur, tokenla degil (model bagimsiz, Karar 5)
#   - ortusme yok
#   - chunk sayfa sinirini asmaz: her chunk tek bir sayfaya aittir (Karar 6 belirsizlik tasimaz)
#   - bos sayfalar atlanir; sayfa sonundaki kisa artik chunk da korunur
import json
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
GIRDI = KOK / "data" / "islenmis" / "sayfalar"
CIKTI = KOK / "data" / "islenmis" / "chunks.jsonl"

CHUNK_KELIME = 200


def main():
    n_chunk = n_sayfa = 0
    with open(CIKTI, "w", encoding="utf-8") as cikti:
        for dosya in sorted(GIRDI.glob("*.jsonl")):
            with open(dosya, encoding="utf-8") as f:
                for satir in f:
                    sayfa = json.loads(satir)
                    kelimeler = sayfa["metin"].split()
                    if not kelimeler:
                        continue
                    n_sayfa += 1
                    for k, bas in enumerate(range(0, len(kelimeler), CHUNK_KELIME)):
                        parca = kelimeler[bas:bas + CHUNK_KELIME]
                        cikti.write(json.dumps({
                            "chunk_id": f"{sayfa['doc']}#{sayfa['sayfa_idx']}#{k}",
                            "doc": sayfa["doc"],
                            "sayfa_idx": sayfa["sayfa_idx"],
                            "k": k,
                            "kelime": len(parca),
                            "metin": " ".join(parca),
                        }, ensure_ascii=False) + "\n")
                        n_chunk += 1
    print(f"{n_sayfa} bos olmayan sayfa -> {n_chunk} chunk ({n_chunk / n_sayfa:.2f} chunk/sayfa)")


if __name__ == "__main__":
    main()
