# Hibrit arama deneyi (Deney 3, Karar 7 adim 2): BM25 + dense siralamalarini RRF ile birlestirir.
#
# Kullanim: python src/hibrit.py
# Girdi:    data/islenmis/siralamalar/{bm25,dense_*}_{ortak,tek}.json (kunyesiz)
# Cikti:    data/islenmis/siralamalar/rrf_<ad>_{ortak,tek}.json         (hibrit siralama)
#           data/islenmis/siralamalar/rrf_<ad>_rerank_{ortak,tek}.json  (hibrit + reranker)
#           sonuclar/olcumler/hibrit_ozet.json
#
# RRF: skor = toplam( 1 / (K + sira) ), sira 1'den baslar, K = 60 (yaygin varsayilan, ayarlanmaz).
# Birlesik ilk 100 tutulur. Reranker Deney 2 ile ayni (derinlik 50, ayni onbellek).
# Sadece gelistirme kumesi.
import collections
import json
from datetime import date
from pathlib import Path

import degerlendir as d
import rerank as rr

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
K = 60
TOP = 100
DENSE = ["dense_bge-base-en", "dense_e5-base", "dense_gte-base-en", "dense_bge-m3"]
UZAYLAR = ["ortak", "tek"]


def rrf(listeler, soru_idleri):
    # listeler: [{soru_id: [chunk_id...]}, ...] -> {soru_id: birlesik ilk TOP chunk_id}
    sonuc = {}
    for sid in soru_idleri:
        skor = collections.defaultdict(float)
        for liste in listeler:
            for sira, cid in enumerate(liste[sid], 1):
                skor[cid] += 1.0 / (K + sira)
        # esit skorlarda deterministik olmasi icin chunk_id ikincil anahtar
        sonuc[sid] = [c for c, _ in sorted(skor.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]]
    return sonuc


def anlamli_pozitif(f):
    return f["anlamli"] and f["fark"] > 0


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    ids = [s["id"] for s in sorular]
    yukle = lambda ad, u: json.load(open(SIRA / f"{ad}_{u}.json", encoding="utf-8"))

    # hibrit siralamalar: 4 hibrit (BM25 + dense_i) ve kesif varyanti (hepsi)
    hibritler = {}  # ad -> (bilesenler)
    for dn in DENSE:
        hibritler[f"rrf_{dn}"] = ["bm25", dn]
    hibritler["rrf_hepsi"] = ["bm25"] + DENSE
    sirali = {}
    for ad, bilesen in hibritler.items():
        for u in UZAYLAR:
            sirali[(ad, u)] = rrf([yukle(b, u) for b in bilesen], ids)
            (SIRA / f"{ad}_{u}.json").write_text(json.dumps(sirali[(ad, u)]), encoding="utf-8")

    # reranker: hibrit adaylari icin eksik ciftleri hesapla (Deney 2 onbellegi yeniden kullanilir)
    skorlar, hesaplanan, sure = rr.skor_hazirla(sorular, bilgi, list(sirali.values()))
    rerank = {(ad, u): rr.yeniden_sirala(sorular, sr, skorlar) for (ad, u), sr in sirali.items()}
    for (ad, u), sr in rerank.items():
        (SIRA / f"{ad}_rerank_{u}.json").write_text(json.dumps(sr), encoding="utf-8")

    ozet = {"tarih": date.today().isoformat(), "rrf_k": K, "kume": "gelistirme",
            "hesaplanan_cift": hesaplanan, "sure_sn": sure, "hibrit": {}}
    olcut1 = {u: [] for u in UZAYLAR}
    olcut2 = {u: [] for u in UZAYLAR}
    for ad, bilesen in hibritler.items():
        dn = bilesen[1] if ad != "rrf_hepsi" else None
        ozet["hibrit"][ad] = {}
        for u in UZAYLAR:
            kayit = {"metrikler": d.olc(sirali[(ad, u)], sorular, bilgi)["metrikler"],
                     "metrikler_rerank": d.olc(rerank[(ad, u)], sorular, bilgi)["metrikler"]}
            if dn:
                # 1) hibrit vs dense (ilk asama)
                f1 = {f"{m}@{k}" if m != "mrr" else "mrr":
                      d.karsilastir(yukle(dn, u), sirali[(ad, u)], sorular, bilgi, metrik=m, k=k, n_boot=10000)
                      for m, k in (("recall", 1), ("recall", 5), ("recall", 10), ("mrr", 0))}
                # 2) hibrit+rerank vs dense+rerank (Deney 2'deki siralama)
                f2 = {f"{m}@{k}" if m != "mrr" else "mrr":
                      d.karsilastir(yukle(f"{dn}_rerank", u), rerank[(ad, u)], sorular, bilgi, metrik=m, k=k,
                                    n_boot=10000)
                      for m, k in (("recall", 1), ("recall", 5), ("recall", 10), ("mrr", 0))}
                kayit["fark_hibrit_vs_dense"], kayit["fark_hibrit_rerank_vs_dense_rerank"] = f1, f2
                if anlamli_pozitif(f1["recall@5"]):
                    olcut1[u].append(ad)
                if anlamli_pozitif(f2["recall@5"]):
                    olcut2[u].append(ad)
                a, b = f1["recall@5"], f2["recall@5"]
                print(f"{ad:22s} {u:5s} hibrit R@5 {a['a']:.3f}->{a['b']:.3f} {a['fark']:+.3f} "
                      f"[{a['ci95'][0]:+.3f},{a['ci95'][1]:+.3f}]{'*' if a['anlamli'] else ' '} | "
                      f"+rerank {b['a']:.3f}->{b['b']:.3f} {b['fark']:+.3f} "
                      f"[{b['ci95'][0]:+.3f},{b['ci95'][1]:+.3f}]{'*' if b['anlamli'] else ' '}")
            else:
                m = kayit["metrikler"]
                mr = kayit["metrikler_rerank"]
                print(f"{ad:22s} {u:5s} (kesif) R@5 {m['recall@5']['deger']:.3f}  +rerank {mr['recall@5']['deger']:.3f}")
            ozet["hibrit"][ad][u] = kayit

    ozet["olcut1_hibrit_vs_dense"] = {u: {"anlamli_pozitif": v, "sayi": len(v), "saglandi": len(v) >= 3}
                                      for u, v in olcut1.items()}
    ozet["olcut2_hibrit_rerank_vs_dense_rerank"] = {u: {"anlamli_pozitif": v, "sayi": len(v), "saglandi": len(v) >= 3}
                                                    for u, v in olcut2.items()}
    print("OLCUT 1 (hibrit vs dense):", {u: f"{len(v)}/4" for u, v in olcut1.items()})
    print("OLCUT 2 (hibrit+rerank vs dense+rerank):", {u: f"{len(v)}/4" for u, v in olcut2.items()})
    (KOK / "sonuclar" / "olcumler" / "hibrit_ozet.json").write_text(
        json.dumps(ozet, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
