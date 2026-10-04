# Deney 7: belge yonlendirme (sirket ve yil), RETRIEVAL duzeyi, ucretsiz (on kayit: KARAR_GUNLUGU.md).
#
# Kullanim: python src/deney7_yonlendirme.py
# Girdi:    data/islenmis/embeddings/e5-base.npy, chunks.jsonl, siralamalar/dense_e5-base_{ortak,tek}[_rerank].json
# Cikti:    data/islenmis/siralamalar/yonlendirme_e5_{R1,R2}_{ortak,rerank_ortak}.json
#           sonuclar/olcumler/deney7_yonlendirme.json
#
# Yontem: soru metninden sirket/yil cikarilir (yonlendirme.py), aday belgeler uzerinde e5-base TAM arama
# (ilk 100), ardindan Deney 2 ile ayni reranker (derinlik 50, ayni skor onbellegi). Sirket bulunamayan
# sorularda MEVCUT hat (kayitli global siralama) aynen kullanilir. Sadece gelistirme kumesi.
#
# Olcut (on kayitli, sabit): yonlendirme BENIMSENIR ancak (a) yonlendirme isabeti >= 0.90 (gold belge aday
# kumede; TUM sorular uzerinden, yonlendirilmeyenler global arama oldugundan isabet sayilir; yalniz
# yonlendirilenler uzerindeki isabet de raporlanir) VE (b) reranker sonrasi Recall@1000w farkinin
# (yonlendirmeli - mevcut hat) %95 sirket-kumeli bootstrap araliginin ALT SINIRI > 0.
# R2 birincil; R2 saglamazsa ve R1 saglarsa R1; ikisi de saglamazsa mevcut hat kalir.
import json
import statistics
from datetime import date
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

import degerlendir as d
import rerank as rr
import yonlendirme as yo

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
EMB = KOK / "data" / "islenmis" / "embeddings" / "e5-base.npy"
ESIK_ISABET = 0.90
DERINLIK = 50
TOP = 100


def baglamda_soru(siralama, sorular, bilgi):
    # soru duzeyi: ilk 1000 kelimelik pencerede en az bir gold sayfa var mi (butce kurali, degerlendir ile ayni)
    n = 0
    for s in sorular:
        birikim, pencere = 0, []
        for cid in siralama[s["id"]]:
            if birikim >= d.BUTCE:
                break
            birikim += len(bilgi[cid][2].split())
            pencere.append(bilgi[cid][:2])
        gold = {(k["doc"], k["sayfa"]) for k in s["kanitlar"]}
        n += bool(gold & set(pencere))
    return n / len(sorular)


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    kume = d.soru_kumeleri(sorular)
    belgeler = yo.belgeleri_yukle()
    tablo = yo.sirket_tablosu(belgeler)
    sirket_of = d.sirket_haritasi()
    yukle = lambda ad: json.load(open(SIRA / f"{ad}.json", encoding="utf-8"))
    mevcut_ilk, mevcut_rerank = yukle("dense_e5-base_ortak"), yukle("dense_e5-base_rerank_ortak")

    # sorgu vektorleri (dense_baseline ile ayni model/onek/hassasiyet)
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

    siralamalar, tanilar = {}, {}
    for varyant in ("R1", "R2"):
        rank, tani = {}, {}
        for i, s in enumerate(sorular):
            docs, t = yo.belgeleri_sec(s["soru"], belgeler, tablo, varyant)
            gold_sirket = sirket_of[s["doc"]]
            kayit = {"sirketler": t["sirketler"], "yillar": t["yillar"], "yonlendirildi": docs is not None,
                     "gold_sirket_bulundu": gold_sirket in t["sirketler"],
                     "yanlis_sirket_var": any(x != gold_sirket for x in t["sirketler"])}
            if docs is None:
                rank[s["id"]] = mevcut_ilk[s["id"]]
            else:
                idx = torch.tensor([j for dd in docs for j in doc_idx[dd]], device="cuda")
                skor = (torch.from_numpy(Q[i]).cuda().half() @ E[idx].T).float()
                ust = torch.topk(skor, min(TOP, len(idx))).indices.tolist()
                rank[s["id"]] = [idler[int(idx[j])] for j in ust]
                kayit.update({"aday_belge": len(docs), "aday_chunk": len(idx), "gold_belge_adayda": s["doc"] in docs,
                              "varyant_kullanilan": t["varyant_kullanilan"]})
            tani[s["id"]] = kayit
        siralamalar[varyant], tanilar[varyant] = rank, tani

    skorlar, hesaplanan, _ = rr.skor_hazirla(sorular, bilgi, [siralamalar["R1"], siralamalar["R2"]], derinlik=DERINLIK)
    sonuc = {"tarih": date.today().isoformat(), "kume": "gelistirme", "rerank_yeni_cift": hesaplanan, "varyantlar": {}}
    n = len(sorular)
    tavan = d.olc(yukle("dense_e5-base_rerank_tek"), sorular, bilgi, n_boot=500)["metrikler"]["recall_butce"]["deger"]
    taban = d.olc(mevcut_rerank, sorular, bilgi, n_boot=500)["metrikler"]["recall_butce"]["deger"]
    print(f"referans: mevcut hat (global) Recall@1000w {taban:.3f} | oracle tek belge tavani {tavan:.3f}\n")
    kabul = []
    for v in ("R1", "R2"):
        t = tanilar[v]
        yon = [k for k in t.values() if k["yonlendirildi"]]
        isabet_hepsi = sum(1 for k in t.values() if (not k["yonlendirildi"]) or k["gold_belge_adayda"]) / n
        isabet_yon = sum(k["gold_belge_adayda"] for k in yon) / len(yon) if yon else None
        yeni = rr.yeniden_sirala(sorular, siralamalar[v], skorlar, DERINLIK)
        (SIRA / f"yonlendirme_e5_{v}_ortak.json").write_text(json.dumps(siralamalar[v]), encoding="utf-8")
        (SIRA / f"yonlendirme_e5_{v}_rerank_ortak.json").write_text(json.dumps(yeni), encoding="utf-8")
        f_butce = d.karsilastir(mevcut_rerank, yeni, sorular, bilgi, metrik="butce", n_boot=10000, kume=kume)
        f_r5 = d.karsilastir(mevcut_rerank, yeni, sorular, bilgi, metrik="recall", k=5, n_boot=10000, kume=kume)
        f_ilk = d.karsilastir(mevcut_ilk, siralamalar[v], sorular, bilgi, metrik="butce", n_boot=10000, kume=kume)
        a, b = baglamda_soru(mevcut_rerank, sorular, bilgi), baglamda_soru(yeni, sorular, bilgi)
        olcut = {"a_isabet_ge_0.90": isabet_hepsi >= ESIK_ISABET, "b_butce_alt_sinir_pozitif": f_butce["ci95"][0] > 0}
        olcut["saglandi"] = all(olcut.values())
        if olcut["saglandi"]:
            kabul.append(v)
        sonuc["varyantlar"][v] = {
            "yonlendirilen_soru": len(yon), "sirket_bulunamayan_soru": n - len(yon),
            "gold_sirket_bulundu_orani_yonlendirilenler": round(sum(k["gold_sirket_bulundu"] for k in yon) / len(yon), 3),
            "yanlis_sirket_iceren_soru": sum(k["yanlis_sirket_var"] for k in t.values()),
            "isabet_tum_sorular": round(isabet_hepsi, 3), "isabet_yonlendirilenler": round(isabet_yon, 3),
            "ort_aday_belge": round(statistics.mean(k["aday_belge"] for k in yon), 1),
            "ort_aday_chunk": round(statistics.mean(k["aday_chunk"] for k in yon)),
            "recall_butce_rerank": f_butce, "recall5_rerank": f_r5, "recall_butce_ilk_asama": f_ilk,
            "gold_baglamda_soru_orani": {"mevcut": round(a, 3), "yonlendirmeli": round(b, 3)}, "olcut": olcut}
        print(f"=== {v}: yonlendirilen {len(yon)}/{n} (sirket bulunamayan {n - len(yon)}); gold sirket bulundu "
              f"{sum(k['gold_sirket_bulundu'] for k in yon)}/{len(yon)}; yanlis sirket iceren {sum(k['yanlis_sirket_var'] for k in t.values())}")
        print(f"    isabet (gold belge aday kumede): tum sorular {isabet_hepsi:.3f} | yonlendirilenler {isabet_yon:.3f} | "
              f"ort. aday {statistics.mean(k['aday_belge'] for k in yon):.1f} belge / {statistics.mean(k['aday_chunk'] for k in yon):.0f} chunk")
        print(f"    Recall@1000w: ilk asama {f_ilk['a']:.3f} -> {f_ilk['b']:.3f} ({f_ilk['fark']:+.3f}) | RERANK SONRASI {f_butce['a']:.3f} -> {f_butce['b']:.3f}  "
              f"fark {f_butce['fark']:+.3f} [{f_butce['ci95'][0]:+.3f}, {f_butce['ci95'][1]:+.3f}] {'*' if f_butce['anlamli'] else ''}")
        print(f"    Recall@5 (rerank) {f_r5['a']:.3f} -> {f_r5['b']:.3f} ({f_r5['fark']:+.3f}) | gold bagiamda soru orani {a:.3f} -> {b:.3f}")
        print(f"    OLCUT: {olcut}")
    secim = "R2" if "R2" in kabul else ("R1" if "R1" in kabul else "mevcut hat")
    sonuc["karar"] = secim
    sonuc["referans"] = {"mevcut_recall_butce_rerank": round(taban, 4), "oracle_tek_belge_tavani": round(tavan, 4)}
    print(f"\nKARAR (on kayitli kural): {secim}")
    (KOK / "sonuclar" / "olcumler" / "deney7_yonlendirme.json").write_text(
        json.dumps(sonuc, indent=2, ensure_ascii=False), encoding="utf-8")
    json.dump({v: tanilar[v] for v in tanilar}, open(KOK / "data" / "islenmis" / "yonlendirme_tani.json", "w", encoding="utf-8"),
              ensure_ascii=False)


if __name__ == "__main__":
    main()
