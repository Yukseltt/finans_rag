# Sayfa metinlerini sabit kelime sayisinda chunk'lara boler (baseline Karar 5; varyantlar Deney 4).
#
# Kullanim: python src/chunk.py                          (baz: 200 kelime, ortusme yok -> chunks.jsonl)
#           python src/chunk.py --kelime 100             (c100 -> chunks_c100.jsonl)
#           python src/chunk.py --kelime 200 --ortusme 50  (c200o50 -> chunks_c200o50.jsonl)
# Girdi:    data/islenmis/sayfalar/*.jsonl   (pdf_parse.py ciktisi)
# Cikti:    data/islenmis/chunks[_etiket].jsonl   (satir basina bir chunk)
#
# Kurallar:
#   - chunk uzunlugu KELIME sayisiyla olculur, tokenla degil (model bagimsiz, Karar 5)
#   - chunk sayfa sinirini asmaz: her chunk tek bir sayfaya aittir (Karar 6 belirsizlik tasimaz)
#   - bos sayfalar atlanir; sayfa sonundaki kisa artik chunk da korunur
#   - ortusme > 0 ise pencere (kelime - ortusme) kadar kayar; sayfa sonunu kapsayan pencereden sonra durur
#   - etiket: c<kelime>[o<ortusme>]; baz (c200, ortusmesiz) eski dosya adini (chunks.jsonl) korur
import argparse
import json
from pathlib import Path

from degerlendir import chunks_yolu, chunk_etiketi

KOK = Path(__file__).resolve().parent.parent
GIRDI = KOK / "data" / "islenmis" / "sayfalar"


def pencereler(n, kelime, ortusme):
    # (baslangic, bitis) ciftleri; son pencere sayfa sonunu kapsar
    adim = kelime - ortusme
    for bas in range(0, n, adim):
        yield bas, min(bas + kelime, n)
        if bas + kelime >= n:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kelime", type=int, default=200)
    ap.add_argument("--ortusme", type=int, default=0)
    args = ap.parse_args()
    assert 0 <= args.ortusme < args.kelime
    etiket = chunk_etiketi(args.kelime, args.ortusme)
    cikti_yolu = chunks_yolu(etiket)

    n_chunk = n_sayfa = 0
    with open(cikti_yolu, "w", encoding="utf-8") as cikti:
        for dosya in sorted(GIRDI.glob("*.jsonl")):
            with open(dosya, encoding="utf-8") as f:
                for satir in f:
                    sayfa = json.loads(satir)
                    kelimeler = sayfa["metin"].split()
                    if not kelimeler:
                        continue
                    n_sayfa += 1
                    for k, (bas, bitis) in enumerate(pencereler(len(kelimeler), args.kelime, args.ortusme)):
                        parca = kelimeler[bas:bitis]
                        cikti.write(json.dumps({
                            "chunk_id": f"{sayfa['doc']}#{sayfa['sayfa_idx']}#{k}",
                            "doc": sayfa["doc"],
                            "sayfa_idx": sayfa["sayfa_idx"],
                            "k": k,
                            "kelime": len(parca),
                            "metin": " ".join(parca),
                        }, ensure_ascii=False) + "\n")
                        n_chunk += 1
    print(f"{etiket}: {n_sayfa} bos olmayan sayfa -> {n_chunk} chunk ({n_chunk / n_sayfa:.2f} chunk/sayfa) -> {cikti_yolu.name}")


if __name__ == "__main__":
    main()
