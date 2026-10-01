# cevap_metrik.py'nin dogrulugunu sinar.
#
# NEDEN BU KADAR AYRINTILI: ilk surum yalnizca "gold'u tahmin olarak ver, kabul etmeli" testini
# kullaniyordu; iki taraf ayni hatayla ayristirildigi icin gercek model cevaplarindaki hatalari
# (0.96x, "($1.8 bn)", madde isareti, "In FY2018 ...", 3M sirket adi, yuvarlama) gormuyordu.
# Bu surum gercekci model cevabi SABLONLARI ve BOZMA testleri kullanir.
#
#   1) regresyon: eskiden hatali ayristirilan bicimler
#   2) sablon: her gelistirme gold'u icin gercekci model cevaplari kabul edilmeli
#   3) bozma:  gold'dan %5 sapma tolerans'i, son basamak hassasiyeti reddetmeli; yanlis hukum reddedilmeli
#   4) tur dagilimi Karar 2 revizesiyle ayni (34 / 30 / 28 / 7)
#
# Kullanim: python tests/test_cevap_metrik.py
import collections
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "src"))
import cevap_metrik as c  # noqa: E402
import degerlendir as d  # noqa: E402

S = "What is the FY2018 capital expenditure amount (in USD millions) for 3M?"


def regresyon():
    # el ile kurulmus temel durumlar
    assert c.salt_sayi("$1577", "$1577.00", S) == {"hassasiyet": True, "tolerans": True}
    assert c.salt_sayi("The answer is $1,577 million.", "$1577.00", S)["hassasiyet"]
    assert c.salt_sayi("$1.577 billion", "$1577.00", S)["hassasiyet"]
    assert c.salt_sayi("Final answer: $1,580", "$1577.00", S) == {"hassasiyet": False, "tolerans": True}
    assert c.salt_sayi("$1,700", "$1577.00", S) == {"hassasiyet": False, "tolerans": False}
    assert not c.salt_sayi("I could not find it.", "$1577.00", S)["tolerans"]
    P = "What is the operating margin? Round to one decimal place."
    assert c.salt_sayi("12.34%", "12.3%", P)["hassasiyet"]
    assert not c.salt_sayi("12.4%", "12.3%", P)["hassasiyet"] and c.salt_sayi("12.4%", "12.3%", P)["tolerans"]
    assert c.hukum("Yes, it is.", "Yes. Because ...")["dogru"] and not c.hukum("No.", "Yes. Because ...")["dogru"]
    assert c.hukum("Final answer: No", "No, the company ...")["dogru"]
    assert c.anahtar_sayilar("Decreased by 1.7% in FY2022 in 3 segments") == [(1.7, 1, True, 1.0)]
    assert c.anahtar_sayi("It shrank 0.9%", "The consumer segment shrunk by 0.9% organically.")["hepsi"]
    r = c.anahtar_sayi("margin was 1.7%", "decreased by 1.7% and 2.5%")
    assert r["oran"] == 0.5 and not r["hepsi"]

    # 1) gercek model cevaplarinda yakalanan hatalar
    assert c.salt_sayi("The quick ratio is 0.96x", "0.96", "quick ratio?")["hassasiyet"]                      # 'x' carpani
    assert c.sayilar("0.96x") == [(0.96, 2, False, 1.0, False)]
    assert c.sayilar("($1.8 bn)") == [(1.8, 1, False, 1e9, True)]                                                  # parantez eksi degil
    assert c.anahtar_sayi("Best Buy generated $1.8 billion in operating cash flow.",
                          "Best Buy generated the most cash flow in FY 2023 ($1.8 bn)")["hepsi"]
    assert c.anahtar_sayi("Acquired 100% equity interest of a flexibles manufacturer.",
                          "Amcor completed these acquisitions during FY2023: \n-100% equity interest")["hepsi"]  # madde isareti
    assert c.sayilar(" fell -14.76%")[0][0] == -14.76 and c.sayilar("2018-2019") == [(2018.0, 0, False, 1.0, False), (2019.0, 0, False, 1.0, False)]
    assert c.sayilar("FY2018 Q2") == []                                                                        # harfe bitisik
    assert c.salt_sayi("In FY2018, 3M's capital expenditure was $1,577 million.", "$1577.00", S)["hassasiyet"]  # yil + 3M
    assert c.salt_sayi("3M's capex for 2018 was $1,577 million.", "$1577.00", S)["hassasiyet"]
    assert c.salt_sayi("Final answer: FY2018 capex = $1,577 million", "$1577.00", S)["hassasiyet"]
    assert c.sayilar("3M reported $5M and 1.5m") == [(5.0, 0, False, 1e6, True), (1.5, 1, False, 1e6, False)]              # 3M ad, $5M/1.5m olcek
    assert c.hukum("Based on FY2022 data, no, 3M is not capital-intensive.", "No, the company ...")["dogru"]
    assert not c.hukum("There is no question the company is capital-intensive.", "Yes, it is")["dogru"]      # 'no question'
    assert not c.hukum("It is no longer capital-intensive.", "Yes, it is")["dogru"]                           # 'no longer'
    assert c.sayilar("Form 10-K and 8-K, 10-Q") == []                                                         # form adlari sayi degil
    assert c.salt_sayi("Based on the 10-K for FY2023 (page 59), the result is $1577.00.", "$1577.00", S)["hassasiyet"]
    assert c.salt_sayi("Per page 59 of the 10-K the ratio is 0.96.", "0.96", "ratio?")["hassasiyet"]          # ondalikli aday secilir
    assert c.salt_sayi("0.125", "0.13", "ratio? round to two decimal places")["hassasiyet"]                    # yarim yukari
    assert c.salt_sayi("2.675", "2.68", "x? two decimal places")["hassasiyet"]
    # gold'un kendisi yil ise yil filtresi uygulanmaz
    assert c.salt_sayi("It was 2022.", "2022", "In which fiscal year did X happen?")["hassasiyet"]


def sablonlar(gold, soru):
    # bir salt-sayi gold'u icin gercekci model cevabi bicimleri
    v, ond, yuzde, _, _ = c.sayilar(gold)[0]
    dolar = gold.strip().startswith("$")
    metin = f"{abs(v):.{ond}f}"
    bicimler = [gold, metin, f"${metin}" if dolar else metin, (f"{abs(v):,.{ond}f}" if abs(v) >= 1000 else metin)]
    if yuzde:
        bicimler.append(f"{metin}%")
        bicimler.append(f"{metin} percent")
    cumleler = []
    for b in bicimler:
        cumleler += [b, f"Final answer: {b}", f"The answer is {b}.", f"Approximately {b}",
                     f"In FY2022 the value was {b}.", f"3M's figure for FY2018 was {b}, up from last year.",
                     f"Based on the 10-K for FY2023 (page 59), the result is {b}."]
    if beklenen_milyon(soru) and v >= 1000:
        cumleler.append(f"${v / 1000:g} billion")
    return cumleler


def beklenen_milyon(soru):
    return c.beklenen_birim(soru) == 1e6


def sablon_ve_bozma(dv):
    sayac = collections.Counter()
    for x in dv:
        if c.tur(x["answer"]) != "salt_sayi":
            continue
        gold, soru = x["answer"], x["question"]
        v, ond, _, _, _ = c.sayilar(gold)[0]
        for tahmin in sablonlar(gold, soru):
            r = c.salt_sayi(tahmin, gold, soru)
            assert r["hassasiyet"] and r["tolerans"], (gold, tahmin, r)
            sayac["kabul"] += 1
        # bozma: %5 sapma tolerans'i, son basamak hassasiyeti reddetmeli
        if v:
            asiri = f"{v * 1.05:.6f}"  # yuvarlanmamis: kucuk gold'larda (0.01) yuvarlama bozmayi gizler
            assert not c.salt_sayi(asiri, gold, soru)["tolerans"], (gold, asiri)
            bir = f"{v + 10 ** -ond:.{ond}f}"
            assert not c.salt_sayi(bir, gold, soru)["hassasiyet"], (gold, bir)
            sayac["bozma"] += 2
    return sayac


def hukum_sablonlari(dv):
    sayac = 0
    for x in dv:
        if c.tur(x["answer"]) != "hukum":
            continue
        dogru = c.hukum("Yes", x["answer"])["dogru"] if x["answer"].lower().startswith("yes") else c.hukum("No", x["answer"])["dogru"]
        assert dogru
        v = "Yes" if x["answer"].lower().startswith("yes") else "No"
        ters = "No" if v == "Yes" else "Yes"
        for t in (v, f"{v}.", f"{v}, because of the figures above.", f"Final answer: {v}", f"Based on the filing, {v.lower()}, as shown."):
            assert c.hukum(t, x["answer"])["dogru"], (x["answer"][:40], t)
            sayac += 1
        for t in (ters, f"{ters}, because ...", f"Final answer: {ters}", f"Based on the filing, {ters.lower()}, as shown."):
            assert not c.hukum(t, x["answer"])["dogru"], (x["answer"][:40], t)
            sayac += 1
    return sayac


def anahtar_sablonlari(dv):
    sayac = 0
    for x in dv:
        if c.tur(x["answer"]) != "anahtar_sayi":
            continue
        anahtar = c.anahtar_sayilar(x["answer"])
        if not anahtar:
            continue
        # gold'un onune ek metin: hepsi bulunmali
        r = c.anahtar_sayi("According to the 10-K for FY2022, " + x["answer"], x["answer"])
        assert r["hepsi"], (x["answer"][:60], r)
        # sayilar silinmis cevap: hicbiri bulunmamali
        bos = c.anahtar_sayi("The company's results changed noticeably over the period.", x["answer"])
        assert bos["oran"] == 0.0, (x["answer"][:60], bos)
        sayac += 2
    return sayac


def main():
    regresyon()
    print("regresyon: gecti")

    sorular = {s["id"]: s for s in d.yukle_sorular()}
    fb = [json.loads(l) for l in open(KOK / "data" / "ham" / "financebench" / "sorular.jsonl", encoding="utf-8") if l.strip()]
    dv = [x for x in fb if x["financebench_id"] in sorular]

    turler = collections.Counter(c.tur(x["answer"]) for x in dv)
    print("gold cevap turleri (gelistirme):", dict(turler))
    assert turler == {"salt_sayi": 34, "hukum": 30, "anahtar_sayi": 28, "serbest": 7}, turler

    for x in dv:  # gold = tahmin (ozdeslik)
        r = c.skorla(x["answer"], x["answer"], x["question"])
        if r["tur"] == "salt_sayi":
            assert r["hassasiyet"] and r["tolerans"], (x["answer"], r)
        elif r["tur"] == "hukum":
            assert r["dogru"], (x["answer"], r)
        elif r["tur"] == "anahtar_sayi" and r["n"]:
            assert r["hepsi"], (x["answer"], r)
    print("ozdeslik (gold = tahmin): gecti")

    sayac = sablon_ve_bozma(dv)
    print(f"salt sayi: {sayac['kabul']} gercekci cevap kabul edildi, {sayac['bozma']} bozulmus cevap reddedildi")
    print(f"hukum: {hukum_sablonlari(dv)} sablon (kabul ve ret) gecti")
    print(f"anahtar sayi: {anahtar_sablonlari(dv)} sablon gecti")
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
