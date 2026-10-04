# Deney 5: cevaplari puanlar ve on kayitli hipotezleri (H5a-d) hesaplar.
#
# Kullanim: python src/cevap_olc.py
# Girdi:    data/islenmis/cevaplar/<model>__<kosul>.jsonl (okuyucu_gemini.py), istekler (baglam sayfalari),
#           gelistirme sorularinin gold cevaplari
# Cikti:    ekrana tablolar + sonuclar/olcumler/deney5_gelistirme.json
# Sadece gelistirme kumesi (kilitli kume icin ayri, tek seferlik betik).
#
# PUANLAMA (Karar 2 revizesi, cevap_metrik.py):
#   salt_sayi    -> hassasiyet (birincil; tolerans ikincil)       hukum -> Yes/No eslesmesi
#   anahtar_sayi -> TUM anahtar sayilar bulundu mu (gold'da anahtar sayi yoksa elle puanlanir)
#   serbest      -> ELLE puanlanir (kullanici); bu betik otomatik DEGIL, "bekliyor" sayar
# Yanit alinamayan soru (hata/bos) otomatik puanlanabilirse YANLIS sayilir.
# Basliktaki dogruluk: otomatik puanlanabilir sorular uzerinden; elle puanlanacaklar eklenince guncellenir.
#
# Hipotezler (Deney 5 on kaydi; eslestirilmis, SIRKET-KUMELI bootstrap, 10.000 tekrar, %95):
#   H5a: K1-c200 > K0, iki okuyucuda anlamli                       (olcut 2/2)
#   H5b: K2 - K1-c200 (ayristirma; olcutsuz, fark ve aralik)
#   H5c: K1-c300 > K1-c200, iki okuyucuda anlamli                  (olcut 2/2; aksi halde c200 kalir)
#   H5d: H5a ve H5c yonu iki okuyucuda ayni mi (betimsel)
import collections
import json
import statistics
import sys
from datetime import date
from pathlib import Path

import cevap_metrik as c
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
CEVAPLAR = KOK / "data" / "islenmis" / "cevaplar"
ISTEKLER = KOK / "data" / "islenmis" / "istekler"
MODELLER = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
KOSULLAR = ["k0", "k1_c200", "k1_c300", "k2"]
YUMUSAK = "--yumusak" in sys.argv  # elle puanlarda "kismen" DOGRU sayilir (varsayilan siki: kismen = yanlis)


def elle_yukle():
    # sonuclar/elle_puanlar.json (elle_puan_ice_aktar.py ciktisi): (model, kosul, soru_id) -> dogru | kismen | yanlis
    yol = KOK / "sonuclar" / "elle_puanlar.json"
    if not yol.exists():
        return {}
    return {(r["model"], r["kosul"], r["id"]): r["puan"] for r in json.load(open(yol, encoding="utf-8"))["puanlar"]}


ELLE = elle_yukle()


def goldleri_yukle(sorular):
    ids = {s["id"] for s in sorular}
    sonuc = {}
    with open(KOK / "data" / "ham" / "financebench" / "sorular.jsonl", encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                x = json.loads(satir)
                if x["financebench_id"] in ids:
                    sonuc[x["financebench_id"]] = x["answer"]
    return sonuc


def puanla(tahmin, gold, soru):
    # doner: (dogru 0/1 ya da None=elle, ayrinti)
    t = c.tur(gold)
    if t == "salt_sayi":
        r = c.salt_sayi(tahmin or "", gold, soru)
        return int(r["hassasiyet"]), {"tur": t, "tolerans": int(r["tolerans"])}
    if t == "hukum":
        return int(c.hukum(tahmin or "", gold)["dogru"]), {"tur": t}
    if t == "anahtar_sayi":
        r = c.anahtar_sayi(tahmin or "", gold)
        if r["n"] == 0:
            return None, {"tur": "anahtar_sayi_bos"}
        return int(r["hepsi"]), {"tur": t, "oran": r["oran"]}
    return None, {"tur": "serbest"}


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    sid = [s["id"] for s in sorular]
    soru = {s["id"]: s for s in sorular}
    gold = goldleri_yukle(sorular)
    kume = d.soru_kumeleri(sorular)

    sonuc = {}      # (model, kosul) -> {id: 0/1}
    ayrinti = {}
    ozet = {}
    for m in MODELLER:
        for k in KOSULLAR:
            kayitlar = {}
            for satir in open(CEVAPLAR / f"{m}__{k}.jsonl", encoding="utf-8"):
                x = json.loads(satir)
                if x["hata"] is None:
                    kayitlar[x["id"]] = x  # ayni id birden fazla basarili kayit varsa sonuncusu
            istek = {json.loads(l)["id"]: json.loads(l) for l in open(ISTEKLER / f"{k}.jsonl", encoding="utf-8")}
            dogru, ayr, elle = {}, {}, 0
            atif = collections.defaultdict(list)
            for i in sid:
                tahmin = kayitlar[i]["yanit"] if i in kayitlar else None
                v, a = puanla(tahmin, gold[i], soru[i]["soru"])
                if v is None and (m, k, i) in ELLE:  # otomatik puanlanamayan; elle puan var
                    p = ELLE[(m, k, i)]
                    v, a = int(p == "dogru" or (YUMUSAK and p == "kismen")), {"tur": "elle"}
                if v is None:
                    elle += 1
                else:
                    dogru[i] = v
                ayr[i] = a
                if k != "k0" and tahmin:
                    gp = [(z["doc"], z["sayfa"]) for z in soru[i]["kanitlar"]]
                    bp = [tuple(p) for p in istek[i]["baglam_sayfalar"]]
                    r = c.atif_skorla(tahmin, gp, bp)
                    atif["atif_yok"].append(int(r["n"] == 0))
                    atif["isabet"].append(int(r["isabet"]))
                    if r["kesinlik"] is not None:
                        atif["kesinlik"].append(r["kesinlik"])
                        atif["baglamda_oran"].append(r["baglamda_oran"])
            sonuc[(m, k)], ayrinti[(m, k)] = dogru, ayr
            kul = [x["kullanim"] for x in kayitlar.values()]
            tur_say = collections.defaultdict(lambda: [0, 0])
            for i, v in dogru.items():
                tur_say[ayr[i]["tur"]][1] += 1
                tur_say[ayr[i]["tur"]][0] += v
            soru_turu = collections.defaultdict(lambda: [0, 0])
            for i, v in dogru.items():
                soru_turu[soru[i]["tur"]][1] += 1
                soru_turu[soru[i]["tur"]][0] += v
            tol = [ayr[i]["tolerans"] for i in dogru if "tolerans" in ayr[i]]
            ozet[f"{m}|{k}"] = {
                "n_otomatik": len(dogru), "elle_bekleyen": elle, "dogru": sum(dogru.values()),
                "dogruluk": round(sum(dogru.values()) / len(dogru), 4),
                "gold_turu": {t: {"dogru": a, "n": n} for t, (a, n) in sorted(tur_say.items())},
                "soru_turu": {t: {"dogru": a, "n": n} for t, (a, n) in sorted(soru_turu.items())},
                "salt_sayi_tolerans_dogruluk": round(sum(tol) / len(tol), 4) if tol else None,
                "yanit_alinamayan": sum(1 for i in sid if i not in kayitlar),
                "atif": {a: round(statistics.mean(v), 4) for a, v in atif.items()} if atif else None,
                "maliyet_usd": round(sum(x["maliyet_usd"] for x in kayitlar.values()), 4),
                "dusunme_tokeni_ort": round(statistics.mean(u["dusunme"] for u in kul), 1),
                "cikti_tokeni_ort": round(statistics.mean(u["cikti"] for u in kul), 1)}

    # ---- tablo 1: dogruluk
    otomatik = sorted(set.intersection(*[set(v) for v in sonuc.values()]))
    kip = "elle puanlar DAHIL, " + ("YUMUSAK (kismen = dogru)" if YUMUSAK else "SIKI (kismen = yanlis)") if ELLE else "yalnizca otomatik"
    print(f"puanlanan soru: {len(otomatik)} / {len(sid)} ({kip}; elle bekleyen: {len(sid) - len(otomatik)})\n")
    print(f"{'okuyucu':24s} {'K0':>14s} {'K1-c200':>14s} {'K1-c300':>14s} {'K2 oracle':>14s}")
    for m in MODELLER:
        print(f"{m:24s} " + " ".join(f"{ozet[f'{m}|{k}']['dogru']:>5d}/{ozet[f'{m}|{k}']['n_otomatik']:<3d} {ozet[f'{m}|{k}']['dogruluk']:.3f}" for k in KOSULLAR))
    print("\ngold turune gore dogruluk (dogru/n):")
    for m in MODELLER:
        for t in ("salt_sayi", "hukum", "anahtar_sayi"):
            print(f"  {m:24s} {t:13s} " + "  ".join(f"{k}: {ozet[f'{m}|{k}']['gold_turu'][t]['dogru']}/{ozet[f'{m}|{k}']['gold_turu'][t]['n']}" for k in KOSULLAR))
    print("\nsoru turune gore dogruluk:")
    for m in MODELLER:
        for t in ("metrics-generated", "domain-relevant", "novel-generated"):
            print(f"  {m:24s} {t:18s} " + "  ".join(f"{k}: {ozet[f'{m}|{k}']['soru_turu'][t]['dogru']}/{ozet[f'{m}|{k}']['soru_turu'][t]['n']}" for k in KOSULLAR))

    # ---- tablo 2: hipotezler
    def fark(m, ka, kb):
        return d.fark_kume(sonuc[(m, ka)], sonuc[(m, kb)], otomatik, kume, n_boot=10000)
    hip = {}
    print("\nHIPOTEZLER (B - A, eslestirilmis sirket-kumeli bootstrap, %95; * = anlamli)")
    for ad, ka, kb in (("H5a K1-c200 vs K0", "k0", "k1_c200"), ("H5b K2 vs K1-c200", "k1_c200", "k2"),
                       ("H5c K1-c300 vs K1-c200", "k1_c200", "k1_c300"), ("(K2 vs K0)", "k0", "k2")):
        for m in MODELLER:
            r = fark(m, ka, kb)
            hip[f"{ad}|{m}"] = r
            print(f"  {ad:24s} {m:24s} {r['a']:.3f} -> {r['b']:.3f}  fark {r['fark']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] {'*' if r['anlamli'] else ' '}")
    for ad, ka, kb, kural in (("H5a", "k0", "k1_c200", "olcut"), ("H5c", "k1_c200", "k1_c300", "olcut")):
        pozitif = [m for m in MODELLER if hip[f"{'H5a K1-c200 vs K0' if ad == 'H5a' else 'H5c K1-c300 vs K1-c200'}|{m}"]["anlamli"]
                   and hip[f"{'H5a K1-c200 vs K0' if ad == 'H5a' else 'H5c K1-c300 vs K1-c200'}|{m}"]["fark"] > 0]
        hip[f"{ad}_olcut"] = {"anlamli_pozitif": pozitif, "sayi": len(pozitif), "saglandi": len(pozitif) == 2}
        print(f"  {ad} OLCUT (iki okuyucuda anlamli pozitif): {len(pozitif)}/2 -> {'SAGLANDI' if len(pozitif) == 2 else 'saglanmadi'}")
    # ---- okuyucular arasi (betimsel)
    print("\nokuyucu farki (3.8-flash - flash-lite), betimsel:")
    for k in KOSULLAR:
        r = d.fark_kume(sonuc[(MODELLER[0], k)], sonuc[(MODELLER[1], k)], otomatik, kume, n_boot=10000)
        hip[f"okuyucu_farki|{k}"] = r
        print(f"  {k:8s} {r['a']:.3f} -> {r['b']:.3f}  fark {r['fark']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] {'*' if r['anlamli'] else ' '}")
    # ---- atif ve maliyet
    print("\nATIF (K1/K2): atif_yok orani, en az bir gold sayfa atfi (isabet), kesinlik, baglamda bulunma (1 - uydurma)")
    for m in MODELLER:
        for k in KOSULLAR[1:]:
            a = ozet[f"{m}|{k}"]["atif"]
            print(f"  {m:24s} {k:8s} yok {a['atif_yok']:.2f} | isabet {a['isabet']:.2f} | kesinlik {a['kesinlik']:.2f} | baglamda {a['baglamda_oran']:.2f}")
    print("\nMALIYET ve TOKEN (gelistirme, bu kosul icin 99 yanit):")
    for m in MODELLER:
        print(f"  {m:24s} toplam ${sum(ozet[f'{m}|{k}']['maliyet_usd'] for k in KOSULLAR):.3f} ({sum(ozet[f'{m}|{k}']['maliyet_usd'] for k in KOSULLAR) * 55:.1f} TL); "
              f"dusunme ort {statistics.mean(ozet[f'{m}|{k}']['dusunme_tokeni_ort'] for k in KOSULLAR):.0f}, cikti ort {statistics.mean(ozet[f'{m}|{k}']['cikti_tokeni_ort'] for k in KOSULLAR):.0f}")

    ek = "" if not ELLE else ("_elle_yumusak" if YUMUSAK else "_elle_siki")
    (KOK / "sonuclar" / "olcumler" / f"deney5_gelistirme{ek}.json").write_text(
        json.dumps({"tarih": date.today().isoformat(), "kume": "gelistirme", "otomatik_n": len(otomatik),
                    "elle_bekleyen": len(sid) - len(otomatik), "prompt_surum": "v2", "ozet": ozet, "hipotezler": hip},
                   indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
