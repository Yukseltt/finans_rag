# Deney 6: Chroma (HNSW, yaklasik arama) vs tam arama (Karar 13; on kayit: KARAR_GUNLUGU.md).
#
# Kullanim: python src/deney6_vdb.py
# Girdi:    data/islenmis/embeddings/e5-base.npy, data/islenmis/chunks.jsonl,
#           data/islenmis/siralamalar/dense_e5-base_{ortak,tek}.json (tam arama referansi)
# Cikti:    data/islenmis/chroma/                      (kalici Chroma koleksiyonu, repoya girmez)
#           data/islenmis/siralamalar/chroma_e5_{ortak,tek}.json   (SECILEN ef_search ile siralamalar)
#           sonuclar/olcumler/deney6_vdb.json
#
# Olcut (on kayitli, sabit): DB final hatta kullanilabilir sayilir ancak TUMU saglanirsa:
#   (a) ortak havuzda ortalama ilk-50 ortusmesi >= 0.95
#   (b) tek belgede (filtreli) ortalama ilk-50 ortusmesi >= 0.95
#   (c) reranker sonrasi Recall@1000w farkinin (DB - tam) %95 araliginin alt siniri >= -0.05, iki uzayda
#   (d) filtreli aramada min(100, belgedeki chunk sayisi) sonuc doner ve hepsi filtredeki belgeye aittir
# Tek ayar adimi: ef_search 100 -> 400 -> 1000 (indeks yeniden kurulmaz); ilk saglayan secilir.
# Fark araliklari ESLESTIRILMIS SIRKET-KUMELI bootstrap ile (21 sirket kumesi, 10.000 tekrar, %95).
# Sadece gelistirme kumesi.
import json
import statistics
import time
from datetime import date
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

import degerlendir as d
import rerank as rr
import vektor_deposu as vd

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
EMB = KOK / "data" / "islenmis" / "embeddings" / "e5-base.npy"
EF_MERDIVENI = (100, 400, 1000)
TOP = 100
ESIK_ORTUSME = 0.95
MARJ = -0.05
DERINLIK = 50


def ortusme(ref, aday, k):
    # soru basina |ref[:k] ∩ aday[:k]| / min(k, len(ref)), ortalama (kucuk belgelerde ref k'dan kisa olabilir)
    degerler = []
    for sid, r in ref.items():
        pay = len(set(r[:k]) & set(aday[sid][:k]))
        degerler.append(pay / min(k, len(r)))
    return sum(degerler) / len(degerler)


def ms(liste):
    s = sorted(liste)
    return {"medyan": round(statistics.median(s), 2), "p95": round(s[int(0.95 * (len(s) - 1))], 2)}


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    kume = d.soru_kumeleri(sorular)
    belge_say = {}
    for v in bilgi.values():
        belge_say[v[0]] = belge_say.get(v[0], 0) + 1

    # sorgu vektorleri: tam aramadakiyle ayni model, ayni onek, ayni fp16 (dense_baseline.py)
    model = SentenceTransformer("intfloat/e5-base-v2", device="cuda")
    model.half()
    model.max_seq_length = 512
    Q = model.encode(["query: " + s["soru"] for s in sorular], batch_size=32, normalize_embeddings=True,
                     convert_to_numpy=True).astype(np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    del model

    # tam arama referansi (kaydedilmis siralamalar); tek belge belge ici chunk'lara kirpilir (Deney 6 protokol notu)
    yukle = lambda ad: json.load(open(SIRA / f"{ad}.json", encoding="utf-8"))
    ref = {"ortak": yukle("dense_e5-base_ortak"),
           "tek": {s["id"]: [c for c in yukle("dense_e5-base_tek")[s["id"]] if bilgi[c][0] == s["doc"]]
                   for s in sorular}}

    # --- veritabani kurulumu
    depo = vd.ChromaDeposu()
    kurulum_sn = depo.kur(EMB, d.CHUNKS)
    if kurulum_sn is None:
        depo.ac()
        print("Chroma koleksiyonu zaten kurulu:", depo.koleksiyon.count(), "vektor")
    else:
        print(f"Chroma kuruldu: {depo.koleksiyon.count()} vektor, {kurulum_sn:.0f} sn")
    disk_mb = sum(f.stat().st_size for f in vd.CHROMA_YOLU.rglob("*") if f.is_file()) / 2**20

    # --- tam arama gecikmesi (ayni sorgular; ortak havuz, ilk 100)
    tam_gpu = vd.TamAramaDeposu(EMB, d.CHUNKS)
    import torch
    E32 = np.load(EMB).astype(np.float32)
    gecikme = {"tam_gpu": [], "tam_cpu": []}
    for i in range(len(sorular) + 3):
        q = Q[i % len(sorular)]
        torch.cuda.synchronize(); t = time.perf_counter(); tam_gpu.ara(q, TOP); torch.cuda.synchronize()
        g1 = (time.perf_counter() - t) * 1000
        t = time.perf_counter(); s = E32 @ q; np.argpartition(-s, TOP)[:TOP]; g2 = (time.perf_counter() - t) * 1000
        if i >= 3:  # ilk 3 sorgu isinma
            gecikme["tam_gpu"].append(g1); gecikme["tam_cpu"].append(g2)
    del tam_gpu, E32

    # --- ef_search merdiveni: tum sorular, iki uzay
    sonuclar, siralamalar = {}, {}
    for ef in EF_MERDIVENI:
        depo.ef_search_ayarla(ef)
        ortak, tek, g_ortak, g_tek, d_ihlal = {}, {}, [], [], 0
        for i, s in enumerate(sorular):
            q = Q[i]
            t = time.perf_counter(); ortak[s["id"]] = depo.ara(q, TOP); g_ortak.append((time.perf_counter() - t) * 1000)
            istenen = min(TOP, belge_say[s["doc"]])
            t = time.perf_counter(); tek[s["id"]] = depo.ara(q, istenen, doc=s["doc"]); g_tek.append((time.perf_counter() - t) * 1000)
            if len(tek[s["id"]]) != istenen or any(bilgi[c][0] != s["doc"] for c in tek[s["id"]]):
                d_ihlal += 1  # olcut (d)
        siralamalar[ef] = {"ortak": ortak, "tek": tek}
        sonuclar[ef] = {"gecikme_ms": {"ortak": ms(g_ortak[3:]), "tek_filtreli": ms(g_tek[3:])},
                        "d_ihlal_soru_sayisi": d_ihlal,
                        "ortusme": {u: {f"@{k}": round(ortusme(ref[u], siralamalar[ef][u], k), 4) for k in (5, 50, 100)}
                                    for u in ("ortak", "tek")}}
        print(f"ef_search={ef}: ortusme@50 ortak {sonuclar[ef]['ortusme']['ortak']['@50']:.3f}, "
              f"tek {sonuclar[ef]['ortusme']['tek']['@50']:.3f} | gecikme ortak {sonuclar[ef]['gecikme_ms']['ortak']['medyan']} ms, "
              f"tek {sonuclar[ef]['gecikme_ms']['tek_filtreli']['medyan']} ms | (d) ihlali: {d_ihlal}", flush=True)

    # --- reranker sonrasi (Deney 2 ile ayni model, derinlik 50, ayni skor onbellegi)
    tum_listeler = list(ref.values()) + [siralamalar[ef][u] for ef in EF_MERDIVENI for u in ("ortak", "tek")]
    skorlar, hesaplanan, rerank_sn = rr.skor_hazirla(sorular, bilgi, tum_listeler, derinlik=DERINLIK)
    ref_rerank = {u: rr.yeniden_sirala(sorular, ref[u], skorlar, DERINLIK) for u in ref}

    secilen = None
    for ef in EF_MERDIVENI:
        r = sonuclar[ef]
        r["rerank_oncesi"], r["rerank_sonrasi"] = {}, {}
        for u in ("ortak", "tek"):
            aday = siralamalar[ef][u]
            aday_rerank = rr.yeniden_sirala(sorular, aday, skorlar, DERINLIK)
            r["rerank_oncesi"][u] = {
                "butce": d.karsilastir(ref[u], aday, sorular, bilgi, metrik="butce", n_boot=10000, kume=kume),
                "recall@50": d.karsilastir(ref[u], aday, sorular, bilgi, metrik="recall", k=50, n_boot=10000, kume=kume)}
            r["rerank_sonrasi"][u] = {
                "butce": d.karsilastir(ref_rerank[u], aday_rerank, sorular, bilgi, metrik="butce", n_boot=10000, kume=kume),
                "recall@5": d.karsilastir(ref_rerank[u], aday_rerank, sorular, bilgi, metrik="recall", k=5, n_boot=10000, kume=kume)}
        olcut = {
            "a_ortak_ortusme50": r["ortusme"]["ortak"]["@50"] >= ESIK_ORTUSME,
            "b_tek_ortusme50": r["ortusme"]["tek"]["@50"] >= ESIK_ORTUSME,
            "c_rerank_sonrasi_alt_sinir": all(r["rerank_sonrasi"][u]["butce"]["ci95"][0] >= MARJ for u in ("ortak", "tek")),
            "d_filtre_tam_donus": r["d_ihlal_soru_sayisi"] == 0}
        r["olcut"] = olcut
        r["olcut_saglandi"] = all(olcut.values())
        print(f"ef_search={ef}: olcut {olcut} -> {'SAGLANDI' if r['olcut_saglandi'] else 'saglanmadi'}")
        for u in ("ortak", "tek"):
            f = r["rerank_sonrasi"][u]["butce"]
            print(f"    {u:5s} rerank sonrasi Recall@1000w tam {f['a']:.3f} -> DB {f['b']:.3f}  fark {f['fark']:+.3f} "
                  f"[{f['ci95'][0]:+.3f},{f['ci95'][1]:+.3f}]")
        if secilen is None and r["olcut_saglandi"]:
            secilen = ef

    ozet = {"tarih": date.today().isoformat(), "kume": "gelistirme", "koleksiyon": depo.ad,
            "vektor_sayisi": depo.koleksiyon.count(), "chromadb": "1.5.9",
            "hnsw": {"space": "cosine", "ef_construction": 100, "max_neighbors": 16},
            "kurulum_sn": None if kurulum_sn is None else round(kurulum_sn), "disk_mb": round(disk_mb),
            "gecikme_tam_ms": {"gpu": ms(gecikme["tam_gpu"]), "cpu": ms(gecikme["tam_cpu"])},
            "ef_merdiveni": {str(ef): sonuclar[ef] for ef in EF_MERDIVENI},
            "secilen_ef_search": secilen,
            "karar": ("DB final hatta kullanilabilir" if secilen else "DB final hatta KULLANILMAZ (demo yolu)"),
            "rerank_hesaplanan_cift": hesaplanan}
    (KOK / "sonuclar" / "olcumler" / "deney6_vdb.json").write_text(
        json.dumps(ozet, indent=2, ensure_ascii=False), encoding="utf-8")
    if secilen:
        for u in ("ortak", "tek"):
            (SIRA / f"chroma_e5_{u}.json").write_text(json.dumps(siralamalar[secilen][u]), encoding="utf-8")
    print(f"\nKARAR: {ozet['karar']}" + (f" (ef_search={secilen})" if secilen else ""))
    print(f"disk: {disk_mb:.0f} MB; tam arama gecikmesi (medyan): GPU {ozet['gecikme_tam_ms']['gpu']['medyan']} ms, CPU {ozet['gecikme_tam_ms']['cpu']['medyan']} ms")


if __name__ == "__main__":
    main()
