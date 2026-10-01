# Chunk boyutu ve ortusme deneyi (Deney 4): c100, c200o50, c300 varyantlarini baz (c200) ile kiyaslar.
#
# Kullanim: python src/chunk_deneyi.py
# On kosul: her varyant ve model icin  python src/dense_baseline.py --model <m> --chunk <v>  calismis olmali
# Girdi:    data/islenmis/siralamalar/dense_<model>[_<varyant>]_{ortak,tek}.json
# Cikti:    data/islenmis/siralamalar/dense_<model>_<varyant>_rerank_{ortak,tek}.json
#           data/islenmis/rerank_skorlari_<varyant>.json   (varyanta ozgu skor onbellegi)
#           sonuclar/olcumler/chunk_deneyi.json
#
# ANA METRIK: Recall@1000w (esit baglam butcesi; degerlendir.BUTCE). Chunk sayisina gore Recall@k
# buyuk chunk'a yanlidir, bu yuzden sadece ek olarak raporlanir.
# Reranker derinligi varyanta gore ayarlanir (~10.000 kelimelik aday): c100:100, c200o50:50, c300:33.
# Olcut (on kayitli): varyant, RERANKER SONRASI Recall@1000w'de baz c200'u iki modelde ve iki uzayda
# (4/4) anlamli pozitif farkla gecerse kazanir. Sadece gelistirme kumesi.
import json
from datetime import date
from pathlib import Path

import degerlendir as d
import rerank as rr

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
VARYANTLAR = {"c100": 100, "c200o50": 50, "c300": 33}
MODELLER = ["bge-base-en", "e5-base"]
UZAYLAR = ["ortak", "tek"]


def yukle(ad):
    return json.load(open(SIRA / f"{ad}.json", encoding="utf-8"))


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi_baz = d.yukle_chunk_bilgi()
    ozet = {"tarih": date.today().isoformat(), "kume": "gelistirme", "butce_kelime": d.BUTCE,
            "rerank_derinlik": VARYANTLAR, "varyantlar": {}}

    # baz (c200) metrikleri
    baz = {}
    for m in MODELLER:
        for u in UZAYLAR:
            ilk, rer = yukle(f"dense_{m}_{u}"), yukle(f"dense_{m}_rerank_{u}")
            baz[(m, u)] = (ilk, rer)
    ozet["baz_c200"] = {f"{m}|{u}": {"ilk": d.olc(ilk, sorular, bilgi_baz, n_boot=2000)["metrikler"],
                                     "rerank": d.olc(rer, sorular, bilgi_baz, n_boot=2000)["metrikler"]}
                        for (m, u), (ilk, rer) in baz.items()}

    for v, derinlik in VARYANTLAR.items():
        bilgi_v = d.yukle_chunk_bilgi(d.chunks_yolu(v))
        ek = d.ek(v)
        ilkler = {(m, u): yukle(f"dense_{m}{ek}_{u}") for m in MODELLER for u in UZAYLAR}
        print(f"\n##### {v}: {len(bilgi_v)} chunk, rerank derinligi {derinlik}")
        skorlar, hesaplanan, sure = rr.skor_hazirla(
            sorular, bilgi_v, list(ilkler.values()), derinlik=derinlik,
            onbellek=KOK / "data" / "islenmis" / f"rerank_skorlari{ek}.json")
        kayit = {"chunk_sayisi": len(bilgi_v), "rerank_hesaplanan_cift": hesaplanan, "rerank_sure_sn": sure,
                 "sonuclar": {}}
        kazandi = []
        for m in MODELLER:
            for u in UZAYLAR:
                rerank_v = rr.yeniden_sirala(sorular, ilkler[(m, u)], skorlar, derinlik)
                (SIRA / f"dense_{m}{ek}_rerank_{u}.json").write_text(json.dumps(rerank_v), encoding="utf-8")
                ilk_b, rer_b = baz[(m, u)]
                f = {}
                for asama, a, b in (("ilk", ilk_b, ilkler[(m, u)]), ("rerank", rer_b, rerank_v)):
                    f[asama] = {
                        "butce": d.karsilastir(a, b, sorular, bilgi_baz, metrik="butce", n_boot=10000, bilgi_b=bilgi_v),
                        "recall@5(chunk)": d.karsilastir(a, b, sorular, bilgi_baz, metrik="recall", k=5, n_boot=10000,
                                                         bilgi_b=bilgi_v),
                        "mrr": d.karsilastir(a, b, sorular, bilgi_baz, metrik="mrr", n_boot=10000, bilgi_b=bilgi_v)}
                met = d.olc(rerank_v, sorular, bilgi_v, n_boot=2000)["metrikler"]
                kayit["sonuclar"][f"{m}|{u}"] = {"rerank_metrikler": met, "fark_vs_c200": f}
                fb = f["rerank"]["butce"]
                fi = f["ilk"]["butce"]
                if fb["anlamli"] and fb["fark"] > 0:
                    kazandi.append(f"{m}|{u}")
                print(f"  {m:12s} {u:5s} bütçe-recall ilk {fi['a']:.3f}->{fi['b']:.3f} {fi['fark']:+.3f}"
                      f"{'*' if fi['anlamli'] else ' '} | rerank {fb['a']:.3f}->{fb['b']:.3f} {fb['fark']:+.3f} "
                      f"[{fb['ci95'][0]:+.3f},{fb['ci95'][1]:+.3f}]{'*' if fb['anlamli'] else ' '}")
        kayit["olcut"] = {"anlamli_pozitif": kazandi, "sayi": len(kazandi), "kazandi": len(kazandi) == 4}
        print(f"  OLCUT {v}: {len(kazandi)}/4 -> {'KAZANDI' if len(kazandi) == 4 else 'baz (c200) kalir'}")
        ozet["varyantlar"][v] = kayit

    # ek bilgi: embedding suresi ve kesilme oranlari
    for v in ["c200"] + list(VARYANTLAR):
        ek = d.ek(v)
        ozet.setdefault("ek_bilgi", {})[v] = {
            "gomme_sn": {m: json.load(open(KOK / "sonuclar" / "olcumler" / f"dense_{m}{ek}.json",
                                           encoding="utf-8"))["konfigurasyon"]["gomme_suresi_sn"] for m in MODELLER}}
        kontrol = KOK / "sonuclar" / f"chunk_token_kontrol{ek}.json"
        if kontrol.exists():
            k = json.load(open(kontrol, encoding="utf-8"))
            ozet["ek_bilgi"][v]["kesilme_orani_512"] = {
                "bge-base-en-v1.5": k["BAAI/bge-base-en-v1.5"]["sinir_asan_oran"],
                "e5-base-v2": k["intfloat/e5-base-v2"]["sinir_asan_oran"]}
    (KOK / "sonuclar" / "olcumler" / "chunk_deneyi.json").write_text(
        json.dumps(ozet, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
