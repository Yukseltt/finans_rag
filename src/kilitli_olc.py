# Kilitli test, ASAMA 3 (Karar 14): puanlama ve hipotezler (HF1-HF4).
#
# Kullanim:
#   python src/kilitli_olc.py --deneme [--yumusak]   GELISTIRME verisiyle kodu sinar (kilitliye dokunmaz; K0, K1-R2-V3, K2)
#   python src/kilitli_olc.py [--yumusak]            KILITLI sonuclari olcer (tum cevaplar ve yargic puanlari tamam olmali)
# Cikti:  ekrana tablolar + sonuclar/olcumler/kilitli_olc[_yumusak].json  (deneme: kilitli_olc_deneme[_yumusak].json)
#
# Puanlama: otomatik metrik (cevap_olc.puanla); otomatik puanlanamayan cevaplarda yargic puani (kilitli) ya da
# kayitli elle puan (deneme). Siki: yalniz "dogru". Yumusak: "dogru" ve "kismen".
# Eksik cevap ya da eksik yargic puani varsa DURUR (kismi analiz yok).
import json
import statistics
import sys
from datetime import date
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
KILITLI = KOK / "data" / "islenmis" / "kilitli"
KOSULLAR = ["k0", "k1_r2_v3", "k2"]
YUMUSAK = "--yumusak" in sys.argv
DENEME = "--deneme" in sys.argv
MODELLER = co.MODELLER
GELISTIRME_K1 = {"gemini-3.5-flash-lite": 0.576, "gemini-3.8-flash": 0.667}  # HF4: geliştirme, sıkı, 99 soru


def jsonl(yol):
    return [json.loads(s) for s in open(yol, encoding="utf-8") if s.strip()]


def yargic_puanlari():
    p = {}
    for yol in (KILITLI / "yargic").glob("*.jsonl"):
        for x in jsonl(yol):
            if x["hata"] is None:
                p[x["anahtar"]] = x["puan"]
    return p


def elle_deneme():
    # ilk tur (K0, K2 dahil) + d9 turu (K1-R2 v3; yargic puanli)
    sonuc = {}
    for ad in ("elle_puanlar.json", "elle_puanlar_d9.json"):
        for r in json.load(open(KOK / "sonuclar" / ad, encoding="utf-8"))["puanlar"]:
            sonuc[(r["model"], r["kosul"], r["id"])] = r["puan"]
    return sonuc


def main():
    sorular = d.yukle_sorular(kilitli=not DENEME)
    sid = [s["id"] for s in sorular]
    soru = {s["id"]: s for s in sorular}
    gold = co.goldleri_yukle(sorular)
    kume = d.soru_kumeleri(sorular)
    cevap_dir = co.CEVAPLAR if DENEME else KILITLI / "cevaplar"
    istek_dir = co.ISTEKLER if DENEME else KILITLI / "istekler"
    kosul_istek = {k: {r["id"]: r for r in jsonl(istek_dir / f"{k}.jsonl")} for k in KOSULLAR}
    yarg = {} if DENEME else yargic_puanlari()
    elle = elle_deneme() if DENEME else {}

    yanit, puan, sade = {}, {}, {}
    yargicli = 0
    for m in MODELLER:
        for k in KOSULLAR:
            yanit[(m, k)] = {x["id"]: x for x in jsonl(cevap_dir / f"{m}__{k}.jsonl") if x["hata"] is None}
            eksik = [i for i in sid if i not in yanit[(m, k)]]
            if eksik:
                raise SystemExit(f"DURDU: {m}/{k} icin {len(eksik)} soruda cevap yok")
            puan[(m, k)], sade[(m, k)] = {}, {}
            for i in sid:
                tahmin = yanit[(m, k)][i]["yanit"]
                v, _ = co.puanla(tahmin, gold[i], soru[i]["soru"])
                if v is None:
                    p = elle.get((m, k, i)) if DENEME else yarg.get(f"{m}|{k}|{i}")
                    if p is None:
                        raise SystemExit(f"DURDU: {m}/{k}/{i} icin yargic/elle puan yok")
                    yargicli += 1
                    v = int(p == "dogru" or (YUMUSAK and p == "kismen"))
                puan[(m, k)][i] = v
    kip = "YUMUSAK (kismen = dogru)" if YUMUSAK else "SIKI (kismen = yanlis)"
    print(f"{'DENEME (gelistirme)' if DENEME else 'KILITLI'}: {len(sid)} soru, {len(set(kume.values()))} sirket | {kip} | "
          f"otomatik olmayan puan: {yargicli}\n")
    print(f"{'okuyucu':24s} " + " ".join(f"{k:>14s}" for k in KOSULLAR))
    ozet = {}
    for m in MODELLER:
        satir = []
        for k in KOSULLAR:
            dg = sum(puan[(m, k)].values())
            ozet[f"{m}|{k}"] = {"dogru": dg, "n": len(sid), "dogruluk": round(dg / len(sid), 4)}
            satir.append(f"{dg:>3d}/{len(sid):<3d} {dg / len(sid):.3f}")
        print(f"{m:24s} " + " ".join(f"{x:>14s}" for x in satir))

    hip = {}
    print("\nHIPOTEZLER (B - A, eslestirilmis sirket-kumeli bootstrap, 10.000, %95; * = anlamli)")
    for ad, ka, kb in (("HF1 K1 vs K0", "k0", "k1_r2_v3"), ("HF2 K2 vs K1", "k1_r2_v3", "k2"), ("(K2 vs K0)", "k0", "k2")):
        for m in MODELLER:
            r = d.fark_kume(puan[(m, ka)], puan[(m, kb)], sid, kume, n_boot=10000)
            hip[f"{ad}|{m}"] = r
            print(f"  {ad:14s} {m:24s} {r['a']:.3f} -> {r['b']:.3f}  fark {r['fark']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] {'*' if r['anlamli'] else ' '}")
    destek = [m for m in MODELLER if hip[f"HF1 K1 vs K0|{m}"]["ci95"][0] > 0]
    sonuc = "DESTEKLENDI" if len(destek) == 2 else ("KISMEN desteklendi: " + ", ".join(destek) if destek else "AYIRT EDILEMEDI")
    hip["HF1_olcut"] = {"alt_sinir_pozitif_okuyucular": destek, "sonuc": sonuc}
    print(f"  HF1 OLCUT (iki okuyucuda alt sinir > 0): {len(destek)}/2 -> {sonuc}")
    print("\nHF4: gelistirme (siki, 99 soru) -> kilitli, K1-R2-V3 dogrulugu" + ("" if not YUMUSAK else " (gelistirme degerleri SIKI; karsilastirma icin --yumusak kullanma)"))
    for m in MODELLER:
        kil = ozet[f"{m}|k1_r2_v3"]["dogruluk"]
        print(f"  {m:24s} {GELISTIRME_K1[m]:.3f} -> {kil:.3f}  ({kil - GELISTIRME_K1[m]:+.3f})")
        hip[f"HF4|{m}"] = {"gelistirme": GELISTIRME_K1[m], "kilitli": kil, "fark": round(kil - GELISTIRME_K1[m], 4)}

    print("\nTANI: kanit sayfasi K1 baglaminda VAR / YOK")
    var = [i for i in sid if {(q["doc"], q["sayfa"]) for q in soru[i]["kanitlar"]} & {tuple(p) for p in kosul_istek["k1_r2_v3"][i]["baglam_sayfalar"]}]
    yok = [i for i in sid if i not in var]
    tani = {"n_var": len(var), "n_yok": len(yok)}
    print(f"  kanit VAR {len(var)}, YOK {len(yok)}")
    for m in MODELLER:
        f = lambda k, ids: (sum(puan[(m, k)][i] for i in ids) / len(ids)) if ids else float("nan")
        print(f"  {m:24s} VAR: K0 {f('k0', var):.2f} K1 {f('k1_r2_v3', var):.2f} K2 {f('k2', var):.2f} | YOK: K0 {f('k0', yok):.2f} K1 {f('k1_r2_v3', yok):.2f} K2 {f('k2', yok):.2f}")
        tani[m] = {"var": {k: round(f(k, var), 3) for k in KOSULLAR}, "yok": {k: round(f(k, yok), 3) for k in KOSULLAR}}

    print("\nATIF (K1, K2): atif yok | isabet | kesinlik | baglamda (1 - uydurma)")
    for m in MODELLER:
        for k in ("k1_r2_v3", "k2"):
            yokk = isabet = 0
            kes, bag = [], []
            for i in sid:
                gp = [(q["doc"], q["sayfa"]) for q in soru[i]["kanitlar"]]
                r = c.atif_skorla(yanit[(m, k)][i]["yanit"], gp, [tuple(p) for p in kosul_istek[k][i]["baglam_sayfalar"]])
                yokk += int(r["n"] == 0)
                isabet += int(r["isabet"])
                if r["kesinlik"] is not None:
                    kes.append(r["kesinlik"])
                    bag.append(r["baglamda_oran"])
            a = {"atif_yok": round(yokk / len(sid), 3), "isabet": round(isabet / len(sid), 3),
                 "kesinlik": round(statistics.mean(kes), 3) if kes else None, "baglamda": round(statistics.mean(bag), 3) if bag else None}
            tani[f"atif|{m}|{k}"] = a
            print(f"  {m:24s} {k:9s} {a['atif_yok']:.2f} | {a['isabet']:.2f} | {a['kesinlik']} | {a['baglamda']}")

    # HF3: retrieval (ucretsiz), nihai hat: R2 + rerank
    sira_yol = (KOK / "data" / "islenmis" / "siralamalar" / "yonlendirme_e5_R2_rerank_ortak.json") if DENEME else (KILITLI / "siralama_r2_rerank.json")
    bilgi = d.yukle_chunk_bilgi()
    sira = json.load(open(sira_yol, encoding="utf-8"))
    ret = d.olc(sira, sorular, bilgi, n_boot=2000, kilitli=not DENEME)["metrikler"]
    print("\nHF3 RETRIEVAL (nihai hat; Recall@1000w, Recall@5, MRR):")
    rm = {}
    for ad in ("recall_butce", "recall@5", "mrr"):
        if ad in ret:
            rm[ad] = ret[ad]
            print(f"  {ad:14s} {ret[ad]['deger']:.3f}  ci95 {ret[ad].get('ci95')}")
    mal = {m: sum(x["maliyet_usd"] for k in KOSULLAR for x in yanit[(m, k)].values()) for m in MODELLER}
    print("\nOKUYUCU MALIYETI: " + " | ".join(f"{m} ${v:.3f} ({v * 55:.1f} TL)" for m, v in mal.items()))
    ek = ("_deneme" if DENEME else "") + ("_yumusak" if YUMUSAK else "")
    (KOK / "sonuclar" / "olcumler" / f"kilitli_olc{ek}.json").write_text(
        json.dumps({"tarih": date.today().isoformat(), "kume": "gelistirme (DENEME)" if DENEME else "kilitli", "n": len(sid),
                    "puanlama": kip, "otomatik_olmayan_puan": yargicli, "ozet": ozet, "hipotezler": hip, "tani": tani, "retrieval": rm},
                   indent=2, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
