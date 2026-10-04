# Deney 9: prompt v3 ("baglam yetmezse kendi bilginle cevapla") dogruluk, dayanaklilik ve tanilar (on kayit: KARAR_GUNLUGU.md).
#
# Kullanim: python src/deney9_olc.py [--yumusak]
# Girdi:    data/islenmis/cevaplar/<model>__{k0,k1_c200,k1_r2,k1_r2_v3,k2}.jsonl, istekler, gold cevaplar
# Cikti:    ekrana tablolar + sonuclar/olcumler/deney9_olc[_<ek>].json
# Sadece gelistirme kumesi.
#
# Puanlama: cevap_olc.puanla (otomatik); otomatik puanlanamayan 16 soru icin elle puan VARSA kullanilir
# (sonuclar/elle_puanlar_d9.json: kor tur; yoksa Deney 5 turu sonuclar/elle_puanlar.json yalniz K0/K1-c200/K1-c300/K2).
# Elle puani eksik kosul/soru varsa o sorular TUM karsilastirmalardan cikar (puanlanan n yazdirilir).
#
# Hipotez: H9a K1-R2-V3 > K1-R2-V2. OLCUT: guclu okuyucuda (3.8-flash) anlamli pozitif VE zayif okuyucuda
# (flash-lite) anlamli NEGATIF DEGIL. Eslestirilmis, sirket-kumeli bootstrap, 10.000 tekrar, %95.
# H9b/H9c: tani (olcutsuz).
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
KOSULLAR = ["k0", "k1_c200", "k1_r2", "k1_r2_v3", "k2"]
YUMUSAK = "--yumusak" in sys.argv
YETERSIZ = re.compile(r"passages do not contain", re.I)


def elle_d9():
    yol = KOK / "sonuclar" / "elle_puanlar_d9.json"
    if not yol.exists():
        return {}
    return {(r["model"], r["kosul"], r["id"]): r["puan"] for r in json.load(open(yol, encoding="utf-8"))["puanlar"]}


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    sid = [s["id"] for s in sorular]
    soru = {s["id"]: s for s in sorular}
    gold = co.goldleri_yukle(sorular)
    kume = d.soru_kumeleri(sorular)
    d9 = elle_d9()
    yanit = {}
    for m in co.MODELLER:
        for k in KOSULLAR:
            yanit[(m, k)] = {}
            for satir in open(co.CEVAPLAR / f"{m}__{k}.jsonl", encoding="utf-8"):
                x = json.loads(satir)
                if x["hata"] is None:
                    yanit[(m, k)][x["id"]] = x
    istek = {k: {json.loads(l)["id"]: json.loads(l) for l in open(co.ISTEKLER / f"{k}.jsonl", encoding="utf-8")} for k in KOSULLAR}

    puan = {}
    for m in co.MODELLER:
        for k in KOSULLAR:
            puan[(m, k)] = {}
            for i in sid:
                x = yanit[(m, k)].get(i)
                v, _ = co.puanla(x["yanit"] if x else None, gold[i], soru[i]["soru"])
                if v is None:
                    p = d9.get((m, k, i)) or (co.ELLE.get((m, k, i)) if k in ("k0", "k1_c200", "k1_c300", "k2") else None)
                    if p is None:
                        continue
                    v = int(p == "dogru" or (YUMUSAK and p == "kismen"))
                puan[(m, k)][i] = v
    ortak = sorted(set.intersection(*[set(v) for v in puan.values()]))
    kip = ("elle puanlar dahil (" + ("yumusak" if YUMUSAK else "siki") + ")") if (d9 or co.ELLE) else "yalnizca otomatik"
    print(f"puanlanan soru (tum kosullarda): {len(ortak)} / {len(sid)} [{kip}]\n")
    print(f"{'okuyucu':24s} " + " ".join(f"{k:>14s}" for k in KOSULLAR))
    ozet = {}
    for m in co.MODELLER:
        satir = []
        for k in KOSULLAR:
            dg = sum(puan[(m, k)][i] for i in ortak)
            ozet[f"{m}|{k}"] = {"dogru": dg, "n": len(ortak), "dogruluk": round(dg / len(ortak), 4)}
            satir.append(f"{dg:>4d}/{len(ortak):<3d} {dg / len(ortak):.3f}")
        print(f"{m:24s} " + " ".join(f"{x:>14s}" for x in satir))

    hip = {}
    print("\nHIPOTEZLER (B - A, eslestirilmis sirket-kumeli bootstrap, %95; * = anlamli)")
    for ad, ka, kb in (("H9a V3 vs V2 (K1-R2)", "k1_r2", "k1_r2_v3"), ("V3 vs K0", "k0", "k1_r2_v3"),
                       ("V3 vs K1-c200", "k1_c200", "k1_r2_v3"), ("K2 vs V3", "k1_r2_v3", "k2")):
        for m in co.MODELLER:
            r = d.fark_kume(puan[(m, ka)], puan[(m, kb)], ortak, kume, n_boot=10000)
            hip[f"{ad}|{m}"] = r
            print(f"  {ad:22s} {m:24s} {r['a']:.3f} -> {r['b']:.3f}  fark {r['fark']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] {'*' if r['anlamli'] else ' '}")
    g = hip["H9a V3 vs V2 (K1-R2)|gemini-3.8-flash"]
    z = hip["H9a V3 vs V2 (K1-R2)|gemini-3.5-flash-lite"]
    guclu_ok = g["anlamli"] and g["fark"] > 0
    zayif_ok = not (z["anlamli"] and z["fark"] < 0)
    hip["H9a_olcut"] = {"guclu_anlamli_pozitif": guclu_ok, "zayif_anlamli_negatif_degil": zayif_ok, "saglandi": guclu_ok and zayif_ok}
    print(f"  H9a OLCUT: guclu okuyucuda anlamli pozitif = {guclu_ok}; zayif okuyucuda anlamli negatif DEGIL = {zayif_ok} -> "
          f"{'SAGLANDI' if guclu_ok and zayif_ok else 'saglanmadi'}")

    print("\nH9b TANI: kanit sayfasi baglamda VAR / YOK sorularinda dogruluk (puanlanan sorular)")
    var = [i for i in ortak if {(q["doc"], q["sayfa"]) for q in soru[i]["kanitlar"]} & {tuple(p) for p in istek["k1_r2"][i]["baglam_sayfalar"]}]
    yok = [i for i in ortak if i not in var]
    print(f"  K1-R2 baglamlari: kanit VAR {len(var)}, YOK {len(yok)}")
    tani = {}
    for m in co.MODELLER:
        f = lambda k, ids: sum(puan[(m, k)][i] for i in ids) / len(ids)
        print(f"  {m:24s} VAR:  V2 {f('k1_r2', var):.2f} -> V3 {f('k1_r2_v3', var):.2f} (K0 {f('k0', var):.2f}, K2 {f('k2', var):.2f})"
              f" | YOK: V2 {f('k1_r2', yok):.2f} -> V3 {f('k1_r2_v3', yok):.2f} (K0 {f('k0', yok):.2f}, K2 {f('k2', yok):.2f})")
        tani[m] = {"var": {k: round(f(k, var), 3) for k in KOSULLAR}, "yok": {k: round(f(k, yok), 3) for k in KOSULLAR}, "n_var": len(var), "n_yok": len(yok)}

    print("\nH9c DAYANAKLILIK / ATIF")
    for m in co.MODELLER:
        for k in ("k1_r2", "k1_r2_v3"):
            yoksay = none = isabet = yokk = 0; kes, bag = [], []
            n = 0
            for i in sid:
                x = yanit[(m, k)].get(i)
                if not x:
                    continue
                n += 1; t = x["yanit"]
                yoksay += bool(YETERSIZ.search(t))
                gp = [(q["doc"], q["sayfa"]) for q in soru[i]["kanitlar"]]
                r = c.atif_skorla(t, gp, [tuple(p) for p in istek[k][i]["baglam_sayfalar"]])
                yokk += int(r["n"] == 0); isabet += int(r["isabet"])
                if r["kesinlik"] is not None:
                    kes.append(r["kesinlik"]); bag.append(r["baglamda_oran"])
            print(f"  {m:24s} {k:9s} 'passages do not contain' {yoksay / n:.2f} | atif yok {yokk / n:.2f} | isabet {isabet / n:.2f} | "
                  f"kesinlik {statistics.mean(kes):.2f} | baglamda (1-uydurma) {statistics.mean(bag):.2f}")
            tani[f"atif|{m}|{k}"] = {"yetersiz_ifade": round(yoksay / n, 3), "atif_yok": round(yokk / n, 3), "isabet": round(isabet / n, 3),
                                    "baglamda": round(statistics.mean(bag), 3)}
    mal = {m: sum(x["maliyet_usd"] for x in yanit[(m, "k1_r2_v3")].values()) for m in co.MODELLER}
    print("\nK1-R2-V3 maliyeti: " + " | ".join(f"{m} ${v:.3f} ({v * 55:.1f} TL)" for m, v in mal.items()))
    ek = "" if not d9 else ("_elle_yumusak" if YUMUSAK else "_elle_siki")
    (KOK / "sonuclar" / "olcumler" / f"deney9_olc{ek}.json").write_text(
        json.dumps({"tarih": date.today().isoformat(), "kume": "gelistirme", "n": len(ortak), "ozet": ozet, "hipotezler": hip, "tani": tani},
                   indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
