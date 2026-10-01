# BM25 baseline (Karar 5, sifir noktasi): ayarsiz, model gerektirmez.
#
# Kullanim: python src/bm25_baseline.py
# Girdi:    data/islenmis/chunks.jsonl, sonuclar/fb_bolme.json (SADECE gelistirme kumesi)
# Cikti:    sonuclar/olcumler/bm25_baseline.json  (metrikler + konfigurasyon)
#           data/islenmis/siralamalar/bm25_*.json (soru basina ilk 100 chunk_id; sonraki
#                                                  hibrit/RRF adimi yeniden hesaplamasin diye)
#
# Iki arama uzayi (Karar 9):
#   ortak : 360 belgenin tum chunk'lari tek havuz (BASLIK)
#   tek   : sadece sorunun belgesindeki chunk'lar (TESHIS)
# Tek belgede de IDF tum korpustan hesaplanir; sadece siralama sorunun belgesine kisitlanir.
#
# Ayar yok: tokenizasyon = kucuk harf + harf/rakam disini at (stopword yok, stemming yok);
# BM25 parametreleri kutuphane varsayilani (k1=1.5, b=0.75).
import argparse
import json
import time
from datetime import date
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

import degerlendir as d
import kunye as kunye_modulu
from sizinti_metin import normalize

KOK = Path(__file__).resolve().parent.parent
TOP = 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kunye", action="store_true", help="chunk basina belge kunyesi ekle (Deney 1)")
    args = ap.parse_args()
    etiket = "bm25_kunye" if args.kunye else "bm25"
    kunyeler = kunye_modulu.kunye_sozlugu() if args.kunye else None
    sorular = d.yukle_sorular()  # varsayilan: gelistirme, kilitli kumeye dokunmaz
    t0 = time.time()
    chunk_idler, belgeler, kelimeler = [], [], []
    with open(d.CHUNKS, encoding="utf-8") as f:
        for satir in f:
            c = json.loads(satir)
            chunk_idler.append(c["chunk_id"])
            belgeler.append(c["doc"])
            kelimeler.append(normalize((kunyeler[c["doc"]] + " " if kunyeler else "") + c["metin"]))
    belgeler = np.array(belgeler)
    bm25 = BM25Okapi(kelimeler)
    print(f"{len(chunk_idler)} chunk indekslendi ({time.time() - t0:.0f} sn)")

    ortak, tek = {}, {}
    t0 = time.time()
    for s in sorular:
        skor = bm25.get_scores(normalize(s["soru"]))
        ortak[s["id"]] = [chunk_idler[i] for i in np.argsort(-skor)[:TOP]]
        # tek belge: sorunun belgesi disindaki chunk'lari -sonsuz yap
        maskeli = np.where(belgeler == s["doc"], skor, -np.inf)
        tek[s["id"]] = [chunk_idler[i] for i in np.argsort(-maskeli)[:TOP]]
    print(f"{len(sorular)} soru arandi ({time.time() - t0:.0f} sn)")

    bilgi = d.yukle_chunk_bilgi()
    sonuc = {"yontem": etiket, "tarih": date.today().isoformat(),
             "konfigurasyon": {"tokenizasyon": "kucuk harf, alfanumerik, stopword yok", "k1": 1.5, "b": 0.75,
                               "chunk_kelime": 200, "kume": "gelistirme", "top": TOP, "kunye": args.kunye}}
    for ad, siralama in (("ortak_havuz", ortak), ("tek_belge", tek)):
        r = d.olc(siralama, sorular, bilgi)
        d.yazdir(r, f"{etiket} {ad}")
        sonuc[ad] = r

    (KOK / "sonuclar" / "olcumler").mkdir(parents=True, exist_ok=True)
    (KOK / "sonuclar" / "olcumler" / ("bm25_baseline.json" if not args.kunye else "bm25_kunye.json")).write_text(
        json.dumps(sonuc, indent=2, ensure_ascii=False), encoding="utf-8")
    sira = KOK / "data" / "islenmis" / "siralamalar"
    sira.mkdir(parents=True, exist_ok=True)
    (sira / f"{etiket}_ortak.json").write_text(json.dumps(ortak), encoding="utf-8")
    (sira / f"{etiket}_tek.json").write_text(json.dumps(tek), encoding="utf-8")


if __name__ == "__main__":
    main()
