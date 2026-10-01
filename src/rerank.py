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
#
# skor_hazirla ve yeniden_sirala baska betiklerden (hibrit.py) da kullanilir; ayni onbellek paylasilir.
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


def skor_hazirla(sorular, bilgi, siralama_listesi, derinlik=DERINLIK):
    # Verilen siralamalarin ilk `derinlik` adayi icin (soru, chunk) skorlarini onbellekten alir,
    # eksikleri hesaplar ve diske yazar. Doner: (skorlar, hesaplanan_cift, sure_sn)
    soru_metni = {s["id"]: s["soru"] for s in sorular}
    skorlar = json.load(open(ONBELLEK, encoding="utf-8")) if ONBELLEK.exists() else {}
    gerekli = {}
    for sr in siralama_listesi:
        for s in sorular:
            for c in sr[s["id"]][:derinlik]:
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
            print(f"  {bas + len(parca)}/{len(eksik)} cift ({time.time() - t0:.0f} sn)", flush=True)
        sure = round(time.time() - t0)
    return skorlar, len(eksik), sure


def yeniden_sirala(sorular, siralama, skorlar, derinlik=DERINLIK):
    yeni = {}
    for s in sorular:
        aday = siralama[s["id"]][:derinlik]
        sirali = sorted(aday, key=lambda c: -skorlar[anahtar(s["id"], c)])
        yeni[s["id"]] = sirali + siralama[s["id"]][derinlik:]
    return yeni


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    siralamalar = {(a, u): json.load(open(SIRA / f"{a}_{u}.json", encoding="utf-8"))
                   for a in ILK_ASAMALAR for u in UZAYLAR}
    skorlar, hesaplanan, sure = skor_hazirla(sorular, bilgi, list(siralamalar.values()))

    ozet = {"model": MODEL, "derinlik": DERINLIK, "tarih": date.today().isoformat(), "kume": "gelistirme",
            "hesaplanan_cift": hesaplanan, "sure_sn": sure, "sonuclar": {}}
    for a in ILK_ASAMALAR:
        ozet["sonuclar"][a] = {}
        for u in UZAYLAR:
            eski = siralamalar[(a, u)]
            yeni = yeniden_sirala(sorular, eski, skorlar)
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
