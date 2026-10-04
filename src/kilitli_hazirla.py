# Kilitli test, ASAMA 1 (Karar 14): nihai arama hatti + okuyucu istekleri. API CAGRISI YOK (yalniz yerel GPU).
#
# Kullanim:
#   python src/kilitli_hazirla.py --dogrula   GELISTIRME kumesinde calisir; kayitli R2 siralamasini birebir uretmeli (kilitliye dokunmaz)
#   python src/kilitli_hazirla.py --kilitli   KILITLI kumede calisir (51 soru); istekleri ve siralamayi yazar
#
# Hat (Karar 14, donmus): e5-base-v2 sorgu vektoru -> R2 belge yonlendirme (sirket yok ise tum belgelerde) -> TAM arama ilk 100
#   -> bge-reranker-v2-m3 derinlik 50 -> ilk 1000 kelime (K1). Chroma kullanilmaz.
# Cikti (kilitli): data/islenmis/kilitli/siralama_r2_rerank.json, siralama_global.json, istekler/{k0,k1_r2_v3,k2}.jsonl,
#                  data/islenmis/kilitli/rerank_skorlari.json (ayri onbellek: gelistirme onbellegi degismez)
# K0 ve K2: prompt v2 (gelistirmedeki gibi); K1: prompt v3.
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

import baglam_hazirla as bh
import degerlendir as d
import rerank as rr
import yonlendirme as yo

KOK = Path(__file__).resolve().parent.parent
KILITLI = KOK / "data" / "islenmis" / "kilitli"
EMB = KOK / "data" / "islenmis" / "embeddings" / "e5-base.npy"
DERINLIK = 50
TOP = 100


def siralamalar_uret(sorular):
    # Doner: (global tam arama ilk 100, R2 yonlendirmeli tam arama ilk 100); deney7_yonlendirme.py ile ayni islem.
    belgeler = yo.belgeleri_yukle()
    tablo = yo.sirket_tablosu(belgeler)
    model = SentenceTransformer("intfloat/e5-base-v2", device="cuda")
    model.half()
    model.max_seq_length = 512
    Q = model.encode(["query: " + s["soru"] for s in sorular], batch_size=32, normalize_embeddings=True,
                     convert_to_numpy=True).astype(np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    del model
    E = torch.from_numpy(np.load(EMB)).cuda()
    idler, doc_idx = [], {}
    for j, satir in enumerate(open(d.CHUNKS, encoding="utf-8")):
        c = json.loads(satir)
        idler.append(c["chunk_id"])
        doc_idx.setdefault(c["doc"], []).append(j)
    glob, r2, tani = {}, {}, {}
    for i, s in enumerate(sorular):
        q = torch.from_numpy(Q[i]).cuda().half()
        skor = (q @ E.T).float()
        glob[s["id"]] = [idler[int(j)] for j in torch.topk(skor, TOP).indices.tolist()]
        docs, t = yo.belgeleri_sec(s["soru"], belgeler, tablo, "R2")
        if docs is None:
            r2[s["id"]] = glob[s["id"]]
            tani[s["id"]] = {"yonlendirildi": False}
        else:
            idx = torch.tensor([j for dd in docs for j in doc_idx[dd]], device="cuda")
            sk = (q @ E[idx].T).float()
            ust = torch.topk(sk, min(TOP, len(idx))).indices.tolist()
            r2[s["id"]] = [idler[int(idx[j])] for j in ust]
            tani[s["id"]] = {"yonlendirildi": True, "aday_belge": len(docs), "sirketler": t["sirketler"], "yillar": t["yillar"]}
    return glob, r2, tani


def main():
    if "--dogrula" in sys.argv:
        sorular = d.yukle_sorular()  # gelistirme
        bilgi = d.yukle_chunk_bilgi()
        glob, r2, _ = siralamalar_uret(sorular)
        onbellek = KOK / "data" / "islenmis" / "rerank_skorlari.json"  # gelistirme onbellegi: tum ciftler orada olmali
        skorlar, yeni, _ = rr.skor_hazirla(sorular, bilgi, [r2], derinlik=DERINLIK, onbellek=onbellek)
        yeniden = rr.yeniden_sirala(sorular, r2, skorlar, DERINLIK)
        kayitli = json.load(open(KOK / "data" / "islenmis" / "siralamalar" / "yonlendirme_e5_R2_rerank_ortak.json", encoding="utf-8"))
        kayitli_ilk = json.load(open(KOK / "data" / "islenmis" / "siralamalar" / "yonlendirme_e5_R2_ortak.json", encoding="utf-8"))
        kayitli_glob = json.load(open(KOK / "data" / "islenmis" / "siralamalar" / "dense_e5-base_ortak.json", encoding="utf-8"))
        n = len(sorular)
        ayni_rerank = sum(yeniden[s["id"]][:100] == kayitli[s["id"]][:100] for s in sorular)
        ayni_ilk = sum(r2[s["id"]] == kayitli_ilk[s["id"]] for s in sorular)
        # global: kayitli dosya baska sayida aday tutabilir; ilk 100 karsilastirilir
        ayni_glob = sum(glob[s["id"]] == kayitli_glob[s["id"]][:TOP] for s in sorular)
        ayni_bag = 0
        for s in sorular:
            a, _ = bh.baglam_k1(yeniden[s["id"]], bilgi)
            b, _ = bh.baglam_k1(kayitli[s["id"]], bilgi)
            ayni_bag += a == b
        print(f"DOGRULAMA (gelistirme, {n} soru): R2 ilk-asama ayni {ayni_ilk}/{n} | global ayni {ayni_glob}/{n} | "
              f"rerank sonrasi ayni {ayni_rerank}/{n} | K1 baglam metni ayni {ayni_bag}/{n} | yeni rerank cifti {yeni}")
        assert ayni_bag == n and yeni == 0, "hat kayitli gelistirme hattini birebir uretmiyor; kilitliye GECILMEZ"
        print("TAMAM: kilitli hat gelistirme hattiyla ayni baglami uretiyor")
        return
    if "--kilitli" in sys.argv:
        sorular = d.yukle_sorular(kilitli=True)
        bilgi = d.yukle_chunk_bilgi()
        bh.sablonu_dondur(surum="v2")
        bh.sablonu_dondur(surum="v3")
        glob, r2, tani = siralamalar_uret(sorular)
        skorlar, yeni, _ = rr.skor_hazirla(sorular, bilgi, [r2], derinlik=DERINLIK, onbellek=KILITLI / "rerank_skorlari.json")
        yeniden = rr.yeniden_sirala(sorular, r2, skorlar, DERINLIK)
        (KILITLI / "istekler").mkdir(parents=True, exist_ok=True)
        (KILITLI / "siralama_global.json").write_text(json.dumps(glob), encoding="utf-8")
        (KILITLI / "siralama_r2_rerank.json").write_text(json.dumps(yeniden), encoding="utf-8")
        (KILITLI / "yonlendirme_tani.json").write_text(json.dumps(tani, ensure_ascii=False), encoding="utf-8")
        sayfa_onbellek, k0, k1, k2 = {}, [], [], []
        for s in sorular:
            k0.append(bh.istek(s, "K0", surum="v2"))
            metin, alinan = bh.baglam_k1(yeniden[s["id"]], bilgi)
            r = bh.istek(s, "K1-R2-V3", metin, surum="v3")
            r.update({"baglam_kelime": sum(a[2] for a in alinan), "baglam_sayfalar": [[a[0], a[1]] for a in alinan]})
            k1.append(r)
            metin2, sayfalar, kelime = bh.baglam_k2(s, sayfa_onbellek)
            r2_ = bh.istek(s, "K2", metin2, surum="v2")
            r2_.update({"baglam_kelime": kelime, "baglam_sayfalar": [list(p) for p in sayfalar]})
            k2.append(r2_)
        for ad, liste in (("k0", k0), ("k1_r2_v3", k1), ("k2", k2)):
            with open(KILITLI / "istekler" / f"{ad}.jsonl", "w", encoding="utf-8") as f:
                for r in liste:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        n = len(sorular)
        yon = sum(t["yonlendirildi"] for t in tani.values())
        print(f"kilitli: {n} soru, {yon} yonlendirildi; istekler yazildi (k0, k1_r2_v3, k2); yeni rerank cifti {yeni}")
        return
    raise SystemExit("kullanim: python src/kilitli_hazirla.py --dogrula | --kilitli")


if __name__ == "__main__":
    main()
