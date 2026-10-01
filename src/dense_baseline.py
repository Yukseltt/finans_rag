# Dense (yogun) retrieval baseline: hazir, fine-tune edilmemis embedding modeli (Karar 3 ve 5).
#
# Kullanim: python src/dense_baseline.py --model bge-base-en
#           (model adlari: bge-base-en, bge-m3, e5-base, gte-base-en)
# Girdi:    data/islenmis/chunks.jsonl, sonuclar/fb_bolme.json (SADECE gelistirme kumesi)
# Cikti:    data/islenmis/embeddings/<model>.npy            (chunk gomuleri, tekrar hesaplanmasin)
#           data/islenmis/siralamalar/dense_<model>_*.json  (soru basina ilk 100 chunk_id)
#           sonuclar/olcumler/dense_<model>.json            (metrikler + konfigurasyon)
#
# Iki arama uzayi bm25_baseline.py ile aynidir (Karar 9): ortak havuz (baslik), tek belge (teshis).
# Skor = kosinus benzerligi (gomuler normalize, nokta carpim).
# Ayar yok: modelin kart onerdigi sorgu/pasaj oneklerinden baska bir sey eklenmez.
import argparse
import json
import time
from datetime import date
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

import degerlendir as d
import kunye as kunye_modulu

KOK = Path(__file__).resolve().parent.parent
TOP = 100

# Onekler model kartlarindan (Karar 3). maks: gomme sirasinda kullanilan en buyuk token sayisi;
# 512 sinirli modellerde 512, uzun baglamli modellerde bellek icin 1024 (chunk'larin en uzunu
# ~785 token; sadece birkac nadir uc deger daha uzun, onlar kesilir).
MODELLER = {
    "bge-base-en": {"id": "BAAI/bge-base-en-v1.5", "maks": 512,
                    "sorgu_onek": "Represent this sentence for searching relevant passages: ", "pasaj_onek": ""},
    "bge-m3": {"id": "BAAI/bge-m3", "maks": 1024, "sorgu_onek": "", "pasaj_onek": ""},
    "e5-base": {"id": "intfloat/e5-base-v2", "maks": 512, "sorgu_onek": "query: ", "pasaj_onek": "passage: "},
    # gte uzak kod kullanir. Hem model hem kod deposu sabit commit'e baglanir; kod 2026-10-01'de
    # incelendi (KARAR_GUNLUGU.md, Karar 3): alt surec/ag/eval/pickle yok, xformers istege bagli.
    "gte-base-en": {"id": "Alibaba-NLP/gte-base-en-v1.5", "maks": 1024, "sorgu_onek": "", "pasaj_onek": "",
                    "revision": "a829fd0e060bb84554da0dfd354d0de0f7712b7f",
                    "kod_revision": "40ced75c3017eb27626c9d4ea981bde21a2662f4"},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=MODELLER)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--kunye", action="store_true", help="chunk basina belge kunyesi ekle (Deney 1)")
    args = ap.parse_args()
    m = MODELLER[args.model]

    etiket = args.model + ("_kunye" if args.kunye else "")
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    chunk_idler, belgeler, metinler = [], [], []
    with open(d.CHUNKS, encoding="utf-8") as f:
        for satir in f:
            c = json.loads(satir)
            chunk_idler.append(c["chunk_id"])
            belgeler.append(c["doc"])
            metinler.append(c["metin"])

    if args.kunye:
        # kunye sadece gomme/indeks metnine eklenir; metin kapsama metrigi orijinal chunk metniyle olculur
        kunyeler = kunye_modulu.kunye_sozlugu()
        metinler = [kunyeler[b] + " " + t for b, t in zip(belgeler, metinler)]

    if "kod_revision" in m:
        kod = {"code_revision": m["kod_revision"]}
        model = SentenceTransformer(m["id"], device="cuda", trust_remote_code=True, revision=m["revision"],
                                    config_kwargs=kod, model_kwargs=kod)
    else:
        model = SentenceTransformer(m["id"], device="cuda")
    model.half()
    model.max_seq_length = m["maks"]

    emb_yol = KOK / "data" / "islenmis" / "embeddings" / f"{etiket}.npy"
    emb_yol.parent.mkdir(parents=True, exist_ok=True)
    if emb_yol.exists():
        E = np.load(emb_yol)
        print(f"gomuler onbellekten yuklendi: {E.shape}")
        gomme_sure = None
    else:
        t0 = time.time()
        E = model.encode([m["pasaj_onek"] + t for t in metinler], batch_size=args.batch, normalize_embeddings=True,
                         convert_to_numpy=True, show_progress_bar=True).astype(np.float16)
        gomme_sure = round(time.time() - t0)
        np.save(emb_yol, E)
        print(f"{len(E)} chunk gomuldu ({gomme_sure} sn)")

    Q = model.encode([m["sorgu_onek"] + s["soru"] for s in sorular], batch_size=32, normalize_embeddings=True,
                     convert_to_tensor=True)
    Et = torch.from_numpy(E).to("cuda")
    skor = (Q.half() @ Et.T).float()  # (soru sayisi, chunk sayisi)

    belge_ad = sorted(set(belgeler))
    belge_no = {b: i for i, b in enumerate(belge_ad)}
    belge_idx = torch.tensor([belge_no[b] for b in belgeler], device="cuda")
    ortak, tek = {}, {}
    for i, s in enumerate(sorular):
        ortak[s["id"]] = [chunk_idler[j] for j in torch.topk(skor[i], TOP).indices.tolist()]
        maskeli = torch.where(belge_idx == belge_no[s["doc"]], skor[i], torch.tensor(-1e9, device="cuda"))
        tek[s["id"]] = [chunk_idler[j] for j in torch.topk(maskeli, TOP).indices.tolist()]

    bilgi = d.yukle_chunk_bilgi()
    sonuc = {"yontem": f"dense:{m['id']}", "tarih": date.today().isoformat(),
             "konfigurasyon": {"model": m["id"], "sorgu_onek": m["sorgu_onek"], "pasaj_onek": m["pasaj_onek"],
                               "maks_token": m["maks"], "hassasiyet": "fp16", "benzerlik": "kosinus",
                               "chunk_kelime": 200, "kume": "gelistirme", "top": TOP, "kunye": args.kunye,
                               "gomme_suresi_sn": gomme_sure}}
    for ad, siralama in (("ortak_havuz", ortak), ("tek_belge", tek)):
        r = d.olc(siralama, sorular, bilgi)
        d.yazdir(r, f"{etiket} {ad}")
        sonuc[ad] = r

    (KOK / "sonuclar" / "olcumler").mkdir(parents=True, exist_ok=True)
    (KOK / "sonuclar" / "olcumler" / f"dense_{etiket}.json").write_text(
        json.dumps(sonuc, indent=2, ensure_ascii=False), encoding="utf-8")
    sira = KOK / "data" / "islenmis" / "siralamalar"
    sira.mkdir(parents=True, exist_ok=True)
    (sira / f"dense_{etiket}_ortak.json").write_text(json.dumps(ortak), encoding="utf-8")
    (sira / f"dense_{etiket}_tek.json").write_text(json.dumps(tek), encoding="utf-8")


if __name__ == "__main__":
    main()
