# Reranker deneyi (Deney 2, Karar 7 adim 3): ilk asamanin ilk N adayini cross-encoder ile yeniden siralar.
#
# Kullanim: python src/rerank.py            (derinlik 50)
# Girdi:    data/islenmis/siralamalar/<ilk_asama>_{ortak,tek}.json  (kunyesiz siralamalar)
# Cikti:    data/islenmis/siralamalar/<ilk_asama>_rerank_{ortak,tek}.json
#           data/islenmis/rerank_skorlari.json    (cift basina skor onbellegi, tekrar hesaplanmasin)
#           sonuclar/olcumler/rerank_ozet.json    (metrikler, eslestirilmis farklar, olcut sonucu)
#
# Model: BAAI/bge-reranker-v2-m3. Girdi (soru, ORIJINAL chunk metni); kunye yok, fine-tune yok, ayar yok.
# Derinligin otesindeki adaylar orijinal siralariyla listenin sonunda kalir.
# Sadece gelistirme kumesi.
import json
import time
from datetime import date
from pathlib import Path

import torch
from sentence_transformers import CrossEncoder

import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
ONBELLEK = KOK / "data" / "islenmis" / "rerank_skorlari.json"
MODEL = "BAAI/bge-reranker-v2-m3"
DERINLIK = 50
ILK_ASAMALAR = ["bm25", "dense_bge-base-en", "dense_e5-base", "dense_gte-base-en", "dense_bge-m3"]
UZAYLAR = ["ortak", "tek"]


def anahtar(soru_id, chunk_id):
    return f"{soru_id}||{chunk_id}"


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    soru_metni = {s["id"]: s["soru"] for s in sorular}

    siralamalar = {(a, u): json.load(open(SIRA / f"{a}_{u}.json", encoding="utf-8"))
                   for a in ILK_ASAMALAR for u in UZAYLAR}
    skorlar = json.load(open(ONBELLEK, encoding="utf-8")) if ONBELLEK.exists() else {}

    # Gereken tum benzersiz (soru, chunk) ciftleri; yontemler arasi ortusen adaylar bir kez hesaplanir.
    gerekli = {}
    for (a, u), sr in siralamalar.items():
        for s in sorular:
            for c in sr[s["id"]][:DERINLIK]:
                gerekli[anahtar(s["id"], c)] = (s["id"], c)
    eksik = [k for k in gerekli if k not in skorlar]
    print(f"gereken cift: {len(gerekli)}, onbellekte: {len(gerekli) - len(eksik)}, hesaplanacak: {len(eksik)}")

    sure = None
    if eksik:
        model = CrossEncoder(MODEL, max_length=512, device="cuda")
        model.model.half()
        t0 = time.time()
        PARCA = 2000  # skorlar her parcadan sonra diske yazilir; kesilirse kaldigi yerden devam
        for bas in range(0, len(eksik), PARCA):
            parca = eksik[bas:bas + PARCA]
            ciftler = [(soru_metni[gerekli[k][0]], bilgi[gerekli[k][1]][2]) for k in parca]
            sonuc = model.predict(ciftler, batch_size=16, show_progress_bar=False,
                                  activation_fct=torch.nn.Identity())  # ham skor; siralama icin yeterli
            for k, v in zip(parca, sonuc):
                skorlar[k] = float(v)
            ONBELLEK.write_text(json.dumps(skorlar), encoding="utf-8")
            gecen = time.time() - t0
            print(f"  {bas + len(parca)}/{len(eksik)} cift ({gecen:.0f} sn)", flush=True)
        sure = round(time.time() - t0)

    ozet = {"model": MODEL, "derinlik": DERINLIK, "tarih": date.today().isoformat(), "kume": "gelistirme",
            "hesaplanan_cift": len(eksik), "sure_sn": sure, "benzersiz_cift": len(gerekli), "sonuclar": {}}
    for a in ILK_ASAMALAR:
        ozet["sonuclar"][a] = {}
        for u in UZAYLAR:
            eski = siralamalar[(a, u)]
            yeni = {}
            for s in sorular:
                aday = eski[s["id"]][:DERINLIK]
                sirali = sorted(aday, key=lambda c: -skorlar[anahtar(s["id"], c)])
                yeni[s["id"]] = sirali + eski[s["id"]][DERINLIK:]
            (SIRA / f"{a}_rerank_{u}.json").write_text(json.dumps(yeni), encoding="utf-8")
            r = d.olc(yeni, sorular, bilgi)
            fark = {f"{m}@{k}" if m != "mrr" else "mrr":
                    d.karsilastir(eski, yeni, sorular, bilgi, metrik=m, k=k, n_boot=10000)
                    for m, k in (("recall", 1), ("recall", 5), ("recall", 10), ("mrr", 0))}
            ozet["sonuclar"][a][u] = {"rerank": r, "fark": fark}
            f5 = fark["recall@5"]
            print(f"{a:18s} {u:5s} R@5 {f5['a']:.3f} -> {f5['b']:.3f}  fark {f5['fark']:+.3f} "
                  f"[{f5['ci95'][0]:+.3f},{f5['ci95'][1]:+.3f}] anlamli={f5['anlamli']}")

    # Onkayitli olcut: her uzayda, 5 ilk asamanin en az 4'unde anlamli pozitif Recall@5 farki
    olcut = {}
    for u in UZAYLAR:
        pozitif = [a for a in ILK_ASAMALAR
                   if ozet["sonuclar"][a][u]["fark"]["recall@5"]["anlamli"]
                   and ozet["sonuclar"][a][u]["fark"]["recall@5"]["fark"] > 0]
        olcut[u] = {"anlamli_pozitif": pozitif, "sayi": len(pozitif), "saglandi": len(pozitif) >= 4}
    ozet["olcut"] = olcut
    print("OLCUT:", {u: f"{v['sayi']}/5 -> {'SAGLANDI' if v['saglandi'] else 'saglanmadi'}" for u, v in olcut.items()})
    (KOK / "sonuclar" / "olcumler" / "rerank_ozet.json").write_text(
        json.dumps(ozet, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
