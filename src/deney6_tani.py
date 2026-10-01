# Deney 6 tanisi (POST HOC, aciklayici; on kayitli olcut DEGIL): Chroma ile tam arama arasindaki
# ortusme farkinin NEREDEN geldigini ayirir.
#
# Soru: ortak havuzda ilk-50 ortusmesi 0.916 cikti ve ef_search 100/400/1000 icin ayni cikti. Bu fark
#   (1) HNSW'nin yaklasikligindan mi, yoksa (2) referansin fp16 olmasindan mi geliyor?
#
# Yontem: uc siralamayi ortak havuzda karsilastirir (ilk-50 ortusmesi, ortalama):
#   fp16 tam (kaydedilmis referans)  vs  fp32 tam   -> hassasiyet farkinin tavani (arama yaklasik degil)
#   Chroma (HNSW)                    vs  fp32 tam   -> HNSW'nin GERCEK kaybi, hassasiyet farki cikarilmis
#   Chroma                           vs  fp16 tam   -> Deney 6'da raporlanan deger
# Ayrica ef_search ayarinin gercekten uygulandigini kontrol eder (konfigurasyon + eleman sayisi).
#
# Kullanim: python src/deney6_tani.py
# Cikti:    ekrana ozet + sonuclar/olcumler/deney6_tani.json. Sadece gelistirme kumesi.
import json
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

import degerlendir as d
import vektor_deposu as vd

KOK = Path(__file__).resolve().parent.parent
EMB = KOK / "data" / "islenmis" / "embeddings" / "e5-base.npy"


def ortusme(ref, aday, k):
    return sum(len(set(ref[s][:k]) & set(aday[s][:k])) / k for s in ref) / len(ref)


def main():
    sorular = d.yukle_sorular()
    model = SentenceTransformer("intfloat/e5-base-v2", device="cuda")
    model.half()
    model.max_seq_length = 512
    Q = model.encode(["query: " + s["soru"] for s in sorular], batch_size=32, normalize_embeddings=True,
                     convert_to_numpy=True).astype(np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    del model

    idler = [json.loads(l)["chunk_id"] for l in open(d.CHUNKS, encoding="utf-8")]
    E16 = torch.from_numpy(np.load(EMB)).cuda()
    E32 = E16.float()
    fp16_kayitli = json.load(open(KOK / "data" / "islenmis" / "siralamalar" / "dense_e5-base_ortak.json", encoding="utf-8"))
    fp32 = {}
    for i, s in enumerate(sorular):
        sk = E32 @ torch.from_numpy(Q[i]).cuda()
        fp32[s["id"]] = [idler[j] for j in torch.topk(sk, 100).indices.tolist()]

    depo = vd.ChromaDeposu()
    depo.ac()
    sonuc = {"eleman_sayisi": depo.koleksiyon.count(), "yapilandirma_ef_search_baslangic":
             depo.koleksiyon.configuration["hnsw"]["ef_search"], "ef": {}}
    for ef in (10, 100, 1000):
        depo.ef_search_ayarla(ef)
        sonuc["ef"][ef] = {"yapilandirma": depo.koleksiyon.configuration["hnsw"]["ef_search"]}
        chroma = {s["id"]: depo.ara(Q[i], 100) for i, s in enumerate(sorular)}
        sonuc["ef"][ef].update({"chroma_vs_fp32": round(ortusme(fp32, chroma, 50), 4),
                                "chroma_vs_fp16": round(ortusme(fp16_kayitli, chroma, 50), 4)})
    sonuc["fp16_vs_fp32_tam_arama"] = {f"@{k}": round(ortusme(fp32, fp16_kayitli, k), 4) for k in (5, 50, 100)}
    print("fp16 tam vs fp32 tam (arama YAKLASIK DEGIL, sadece hassasiyet farki):", sonuc["fp16_vs_fp32_tam_arama"])
    for ef, r in sonuc["ef"].items():
        print(f"Chroma ef_search={ef} (yapilandirma okundu: {r['yapilandirma']}): ilk-50 ortusmesi  vs fp32 tam {r['chroma_vs_fp32']:.3f} | vs fp16 tam {r['chroma_vs_fp16']:.3f}")
    (KOK / "sonuclar" / "olcumler" / "deney6_tani.json").write_text(json.dumps(sonuc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
