# Deney 8: belge yonlendirmenin (K1-R2) cevap dogruluguna etkisi (on kayit: KARAR_GUNLUGU.md).
#
# Kullanim: python src/deney8_olc.py
# Girdi:    data/islenmis/cevaplar/<model>__{k0,k1_c200,k1_r2,k2}.jsonl, istekler, gold cevaplar
# Cikti:    ekrana tablolar + sonuclar/olcumler/deney8_olc[_<ek>].json
# Sadece gelistirme kumesi.
#
# Puanlama: cevap_olc.puanla (otomatik); otomatik puanlanamayan 16 soru icin elle puan VARSA kullanilir.
# Elle puanlar iki kaynaktan gelir: sonuclar/elle_puanlar.json (Deney 5; K0, K1-c200, K1-c300, K2) ve
# sonuclar/elle_puanlar_d8.json (Deney 8 turu; K1-c200 ve K1-R2). K1-c200 icin ikisi de varsa YENI tur birincildir;
# test-tekrar uyumu ayrica raporlanir. Eksik elle puan varsa o sorular analizden cikar (puanlanan n yazdirilir).
#
# Hipotezler (eslestirilmis, sirket-kumeli bootstrap, 10.000 tekrar, %95; olcut iki okuyucuda anlamli pozitif):
#   H8a: K1-R2 > K1-c200     H8b: K1-R2 > K0     H8c: ayrisma (K2 - K1-R2; kanit baglamda olan/olmayan)
import collections
import json
import statistics
import sys
from datetime import date
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
KOSULLAR = ["k0", "k1_c200", "k1_r2", "k2"]
YUMUSAK = "--yumusak" in sys.argv


def elle_d8():
    yol = KOK / "sonuclar" / "elle_puanlar_d8.json"
    if not yol.exists():
        return {}
    return {(r["model"], r["kosul"], r["id"]): r["puan"] for r in json.load(open(yol, encoding="utf-8"))["puanlar"]}


def deger(p):
    return int(p == "dogru" or (YUMUSAK and p == "kismen"))


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    sid = [s["id"] for s in sorular]
    soru = {s["id"]: s for s in sorular}
    gold = co.goldleri_yukle(sorular)
    kume = d.soru_kumeleri(sorular)
    d8 = elle_d8()
    yanit = {}
    for m in co.MODELLER:
        for k in KOSULLAR:
            yanit[(m, k)] = {}
            for satir in open(co.CEVAPLAR / f"{m}__{k}.jsonl", encoding="utf-8"):
                x = json.loads(satir)
                if x["hata"] is None:
                    yanit[(m, k)][x["id"]] = x
    istek = {k: {json.loads(l)["id"]: json.loads(l) for l in open(co.ISTEKLER / f"{k}.jsonl", encoding="utf-8")} for k in KOSULLAR}

    puan, elle_eksik = {}, collections.Counter()
    for m in co.MODELLER:
        for k in KOSULLAR:
            puan[(m, k)] = {}
            for i in sid:
                x = yanit[(m, k)].get(i)
                v, _ = co.puanla(x["yanit"] if x else None, gold[i], soru[i]["soru"])
                if v is None:  # elle puan: Deney 8 turu varsa o, yoksa Deney 5 turu
                    p = d8.get((m, k, i)) or co.ELLE.get((m, k, i))
                    if p is None:
                        elle_eksik[(m, k)] += 1
                        continue
                    v = deger(p)
                puan[(m, k)][i] = v
    ortak = sorted(set.intersection(*[set(v) for v in puan.values()]))
    kip = ("elle puanlar dahil (" + ("yumusak" if YUMUSAK else "siki") + ")") if (d8 or co.ELLE) else "yalnizca otomatik"
    print(f"puanlanan soru (tum kosullarda): {len(ortak)} / {len(sid)} [{kip}]\n")
    print(f"{'okuyucu':24s} " + " ".join(f"{k:>14s}" for k in KOSULLAR))
    ozet = {}
    for m in co.MODELLER:
        satir = []
        for k in KOSULLAR:
            dogru = sum(puan[(m, k)][i] for i in ortak)
            ozet[f"{m}|{k}"] = {"dogru": dogru, "n": len(ortak), "dogruluk": round(dogru / len(ortak), 4)}
            satir.append(f"{dogru:>4d}/{len(ortak):<3d} {dogru / len(ortak):.3f}")
        print(f"{m:24s} " + " ".join(f"{x:>14s}" for x in satir))

    hip = {}
    print("\nHIPOTEZLER (B - A, eslestirilmis sirket-kumeli bootstrap, %95; * = anlamli)")
    for ad, ka, kb in (("H8a K1-R2 vs K1-c200", "k1_c200", "k1_r2"), ("H8b K1-R2 vs K0", "k0", "k1_r2"),
                       ("H8c K2 vs K1-R2", "k1_r2", "k2"), ("(ref) K1-c200 vs K0", "k0", "k1_c200")):
        for m in co.MODELLER:
            r = d.fark_kume(puan[(m, ka)], puan[(m, kb)], ortak, kume, n_boot=10000)
            hip[f"{ad}|{m}"] = r
            print(f"  {ad:22s} {m:24s} {r['a']:.3f} -> {r['b']:.3f}  fark {r['fark']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] {'*' if r['anlamli'] else ' '}")
    for ad, anahtar in (("H8a", "H8a K1-R2 vs K1-c200"), ("H8b", "H8b K1-R2 vs K0")):
        poz = [m for m in co.MODELLER if hip[f"{anahtar}|{m}"]["anlamli"] and hip[f"{anahtar}|{m}"]["fark"] > 0]
        hip[f"{ad}_olcut"] = {"anlamli_pozitif": poz, "sayi": len(poz), "saglandi": len(poz) == 2}
        print(f"  {ad} OLCUT (iki okuyucuda anlamli pozitif): {len(poz)}/2 -> {'SAGLANDI' if len(poz) == 2 else 'saglanmadi'}")

    print("\nH8c TANI: K1 dogrulugu, kanit sayfasi baglamda olan / olmayan sorularda (puanlanan sorular)")
    tani = {}
    for kosul in ("k1_c200", "k1_r2"):
        var = [i for i in ortak if {(z["doc"], z["sayfa"]) for z in soru[i]["kanitlar"]} & {tuple(p) for p in istek[kosul][i]["baglam_sayfalar"]}]
        yok = [i for i in ortak if i not in var]
        print(f"  {kosul}: kanit baglamda olan {len(var)}, olmayan {len(yok)}")
        for m in co.MODELLER:
            f = lambda kk, ids: (sum(puan[(m, kk)][i] for i in ids), len(ids))
            a, b = f(kosul, var), f(kosul, yok)
            print(f"    {m:24s} VAR: {a[0]}/{a[1]} = {a[0] / a[1]:.2f} (K0 {f('k0', var)[0] / a[1]:.2f}, K2 {f('k2', var)[0] / a[1]:.2f}) | "
                  f"YOK: {b[0]}/{b[1]} = {b[0] / b[1]:.2f} (K0 {f('k0', yok)[0] / b[1]:.2f}, K2 {f('k2', yok)[0] / b[1]:.2f})")
            tani[f"{kosul}|{m}"] = {"var": a, "yok": b}

    print("\nATIF (K1-R2 vs K1-c200)")
    for m in co.MODELLER:
        for kosul in ("k1_c200", "k1_r2"):
            isabet, kes, bag, yokk = [], [], [], []
            for i in sid:
                x = yanit[(m, kosul)].get(i)
                if not x:
                    continue
                gp = [(z["doc"], z["sayfa"]) for z in soru[i]["kanitlar"]]
                r = c.atif_skorla(x["yanit"], gp, [tuple(p) for p in istek[kosul][i]["baglam_sayfalar"]])
                yokk.append(int(r["n"] == 0)); isabet.append(int(r["isabet"]))
                if r["kesinlik"] is not None:
                    kes.append(r["kesinlik"]); bag.append(r["baglamda_oran"])
            print(f"  {m:24s} {kosul:8s} atif yok {statistics.mean(yokk):.2f} | isabet {statistics.mean(isabet):.2f} | kesinlik {statistics.mean(kes):.2f} | baglamda {statistics.mean(bag):.2f}")
    maliyet = {m: sum(x["maliyet_usd"] for x in yanit[(m, "k1_r2")].values()) for m in co.MODELLER}
    print("\nK1-R2 maliyeti: " + " | ".join(f"{m} ${v:.3f} ({v * 55:.1f} TL)" for m, v in maliyet.items()))
    ek = "" if not d8 else ("_elle_yumusak" if YUMUSAK else "_elle_siki")
    (KOK / "sonuclar" / "olcumler" / f"deney8_olc{ek}.json").write_text(
        json.dumps({"tarih": date.today().isoformat(), "kume": "gelistirme", "n": len(ortak), "ozet": ozet, "hipotezler": hip,
                    "tani": tani, "elle_eksik": {f"{m}|{k}": v for (m, k), v in elle_eksik.items()}}, indent=2, ensure_ascii=False),
        encoding="utf-8")


if __name__ == "__main__":
    main()
