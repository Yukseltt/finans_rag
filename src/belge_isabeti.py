# Belge duzeyi isabet analizi: ortak havuzda ilk k chunk'in en az biri sorunun kanit belgesinden mi?
#
# Neden: sayfa duzeyi Recall@k iki seyi birlestirir (dogru BELGEYI bulmak + belge icinde dogru
# SAYFAYI bulmak). Bu betik ilkini ayri olcer; hatanin hangi asamada oldugunu gosterir.
#
# Kullanim: python src/belge_isabeti.py
# Girdi:    data/islenmis/siralamalar/*_ortak.json (retrieval betiklerinin kaydettigi siralamalar)
# Cikti:    ekrana tablo + sonuclar/belge_isabeti.json
# Sadece gelistirme kumesi.
import json
from pathlib import Path

import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"

YONTEMLER = [
    ("BM25", "bm25", "bm25_kunye"),
    ("bge-base-en", "dense_bge-base-en", "dense_bge-base-en_kunye"),
    ("e5-base", "dense_e5-base", "dense_e5-base_kunye"),
    ("gte-base-en", "dense_gte-base-en", "dense_gte-base-en_kunye"),
    ("bge-m3", "dense_bge-m3", "dense_bge-m3_kunye"),
]
KS = (1, 5, 10, 50)


def belge_isabeti(siralama, sorular, bilgi, k):
    isabet = 0
    for s in sorular:
        belgeler = {e["doc"] for e in s["kanitlar"]}
        isabet += any(bilgi[c][0] in belgeler for c in siralama[s["id"]][:k])
    return isabet / len(sorular)


def yukle(ad):
    yol = SIRA / f"{ad}_ortak.json"
    return json.load(open(yol, encoding="utf-8")) if yol.exists() else None


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    sonuc = {}
    print(f"{'yontem':13s} " + " ".join(f"{'kunyesiz@' + str(k):>13s}" for k in KS) + " | "
          + " ".join(f"{'kunyeli@' + str(k):>12s}" for k in KS))
    for ad, a, b in YONTEMLER:
        satir, kayit = f"{ad:13s} ", {}
        for etiket, dosya in (("kunyesiz", a), ("kunyeli", b)):
            sr = yukle(dosya)
            if sr is None:
                satir += " (yok)" + " " * 8 * len(KS)
                continue
            kayit[etiket] = {f"@{k}": round(belge_isabeti(sr, sorular, bilgi, k), 3) for k in KS}
            satir += " ".join(f"{kayit[etiket][f'@{k}']:13.3f}" for k in KS) + (" | " if etiket == "kunyesiz" else "")
        sonuc[ad] = kayit
        print(satir)
    (KOK / "sonuclar" / "belge_isabeti.json").write_text(json.dumps(sonuc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
