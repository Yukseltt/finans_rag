# Deney 5 tanilari (POST HOC, aciklayici; on kayitli olcut DEGIL): cevap dogrulugu sonuclarinin NEDENINI ayirir.
#
# Kullanim: python src/cevap_tani.py        Cikti: ekrana ozet + sonuclar/olcumler/deney5_tani.json
# Sadece gelistirme kumesi.
#
# 1) Retrieval kaybi: K1 dogrulugu, kanit sayfasi baglamda OLAN ve OLMAYAN sorularda ayri ayri
#    (ayni sorularda K0 ve K2 ile birlikte). Hata retrieval'dan mi okuyucudan mi geliyor?
# 2) Hukum tabani: Yes/No sorularinda hep "Yes" demenin dogrulugu; modellerin hukum dagilimi.
# 3) "Yetersiz baglam" ifadeleri: K1 cevaplarinda model baglamda bilgi bulamadigini soyluyor mu?
# 4) Kapali kitap sayi bilgisi: K0'in salt sayi dogrulugu belge yilina gore (ezber/on-egitim gostergesi).
import collections
import json
import re
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
YETERSIZ = re.compile(r"(do(es)? not (contain|include|provide|specif|mention)|not (provided|available|found|present|disclosed)|"
                      r"cannot (be )?(determine|calculate|find)|unable to|insufficient|no information)", re.I)


def main():
    sorular = d.yukle_sorular()
    sid = [s["id"] for s in sorular]
    soru = {s["id"]: s for s in sorular}
    gold = co.goldleri_yukle(sorular)
    belge_yil = {}
    for satir in open(KOK / "data" / "ham" / "financebench" / "belgeler.jsonl", encoding="utf-8"):
        if satir.strip():
            b = json.loads(satir)
            belge_yil[b["doc_name"]] = int(b["doc_period"])
    veri = {}
    for m in co.MODELLER:
        for k in co.KOSULLAR:
            veri[(m, k)] = {}
            for satir in open(co.CEVAPLAR / f"{m}__{k}.jsonl", encoding="utf-8"):
                x = json.loads(satir)
                if x["hata"] is None:
                    veri[(m, k)][x["id"]] = x["yanit"]
    istek = {k: {json.loads(l)["id"]: json.loads(l) for l in open(co.ISTEKLER / f"{k}.jsonl", encoding="utf-8")} for k in co.KOSULLAR}
    puan = {mk: {i: co.puanla(veri[mk].get(i), gold[i], soru[i]["soru"])[0] for i in sid} for mk in veri}
    oto = [i for i in sid if puan[(co.MODELLER[0], "k0")][i] is not None]
    rapor = {}

    print("1) RETRIEVAL KAYBI: K1 dogrulugu, kanit sayfasi baglamda olan / olmayan sorularda (otomatik puanlananlar)")
    for kosul in ("k1_c200", "k1_c300"):
        var = [i for i in oto if {(z["doc"], z["sayfa"]) for z in soru[i]["kanitlar"]} & {tuple(p) for p in istek[kosul][i]["baglam_sayfalar"]}]
        yok = [i for i in oto if i not in var]
        print(f"  {kosul}: kanit baglamda olan soru {len(var)}, olmayan {len(yok)}")
        for m in co.MODELLER:
            f = lambda kk, ids: (sum(puan[(m, kk)][i] for i in ids), len(ids))
            a, b, e = f(kosul, var), f(kosul, yok), f("k0", var)
            print(f"    {m:24s} K1 | kanit VAR: {a[0]}/{a[1]} = {a[0]/a[1]:.2f} (K0 ayni sorularda {e[0]/e[1]:.2f}, K2 {f('k2', var)[0]/a[1]:.2f}) | kanit YOK: {b[0]}/{b[1]} = {b[0]/b[1]:.2f} (K0 ayni sorularda {f('k0', yok)[0]/b[1]:.2f}, K2 {f('k2', yok)[0]/b[1]:.2f})")
            rapor[f"retrieval|{kosul}|{m}"] = {"var": a, "yok": b}

    print("\n2) HUKUM TABANI (Yes/No sorulari)")
    hukum = [i for i in oto if c.tur(gold[i]) == "hukum"]
    yes = sum(1 for i in hukum if gold[i].strip().lower().startswith("yes"))
    print(f"  gold: {yes} Yes / {len(hukum) - yes} No -> her zaman 'Yes' demenin dogrulugu {yes}/{len(hukum)} = {yes / len(hukum):.3f}")
    for m in co.MODELLER:
        for k in co.KOSULLAR:
            say = collections.Counter()
            for i in hukum:
                mt = re.match(r"\W*(yes|no)\b", c.son_cevap(veri[(m, k)].get(i) or ""), re.I)
                say[mt.group(1).lower() if mt else "diger"] += 1
            print(f"  {m:24s} {k:8s} Yes {say['yes']:>2d} | No {say['no']:>2d} | diger {say['diger']:>2d} | dogru {sum(puan[(m, k)][i] for i in hukum)}/{len(hukum)}")

    print("\n3) 'YETERSIZ BAGLAM' ifadesi (K1 cevaplarinda), soru turune gore")
    for kosul in ("k1_c200", "k2"):
        for m in co.MODELLER:
            say = collections.defaultdict(lambda: [0, 0])
            for i in sid:
                t = soru[i]["tur"]
                say[t][1] += 1
                say[t][0] += bool(YETERSIZ.search(veri[(m, kosul)].get(i) or ""))
            print(f"  {kosul:8s} {m:24s} " + " | ".join(f"{t.split('-')[0]}: {a}/{n}" for t, (a, n) in sorted(say.items())))
            rapor[f"yetersiz|{kosul}|{m}"] = {t: a for t, (a, n) in say.items()}

    print("\n4) K0 SAYI BILGISI: kapali kitap salt sayi dogrulugu, belge yilina gore (ezber gostergesi)")
    sayi = [i for i in oto if c.tur(gold[i]) == "salt_sayi"]
    for m in co.MODELLER:
        gruplar = collections.defaultdict(lambda: [0, 0])
        for i in sayi:
            yil = belge_yil[soru[i]["doc"]]
            g = "<=2019" if yil <= 2019 else "2020-2021" if yil <= 2021 else ">=2022"
            gruplar[g][1] += 1
            gruplar[g][0] += puan[(m, "k0")][i]
        print(f"  {m:24s} " + " | ".join(f"{g}: {a}/{n}" for g, (a, n) in sorted(gruplar.items())))
        rapor[f"k0_yil|{m}"] = {g: a for g, (a, n) in gruplar.items()}
    (KOK / "sonuclar" / "olcumler" / "deney5_tani.json").write_text(json.dumps(rapor, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
