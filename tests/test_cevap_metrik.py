# cevap_metrik.py'nin dogrulugunu sinar. Metrik yanlissa tum cevap sonuclari yanlis olur, bu yuzden:
#   1) gold cevap kendi kendine tahmin olarak verilince deterministik turlerin HEPSI gecmeli (kendi gold'unu reddetmemeli)
#   2) bilinen birim/bicim varyantlari dogru kabul edilmeli, bilinen hatalar reddedilmeli
#   3) tur dagilimi, Karar 2 revizesindeki sayilarla ayni olmali (34 / 30 / 28 / 7, gelistirme kumesi)
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


def main():
    # 2) el ile kurulmus durumlar
    S = "What is the FY2018 capital expenditure amount (in USD millions) for 3M?"
    assert c.salt_sayi("$1577", "$1577.00", S) == {"hassasiyet": True, "tolerans": True}
    assert c.salt_sayi("The answer is $1,577 million.", "$1577.00", S)["hassasiyet"]          # virgul + olcek kelimesi
    assert c.salt_sayi("$1.577 billion", "$1577.00", S)["hassasiyet"]                        # milyar -> milyon
    assert c.salt_sayi("Final answer: $1,580", "$1577.00", S) == {"hassasiyet": False, "tolerans": True}  # %0.2 sapma
    assert c.salt_sayi("$1,700", "$1577.00", S) == {"hassasiyet": False, "tolerans": False}  # %7.8 sapma
    assert not c.salt_sayi("I could not find it.", "$1577.00", S)["tolerans"]
    P = "What is the operating margin? Round to one decimal place."
    assert c.salt_sayi("12.34%", "12.3%", P)["hassasiyet"]                                   # gold 1 ondalik -> yuvarla
    assert not c.salt_sayi("12.4%", "12.3%", P)["hassasiyet"] and c.salt_sayi("12.4%", "12.3%", P)["tolerans"]
    assert c.salt_sayi("Final answer: 0.66", "0.66", "ratio?")["hassasiyet"]
    assert c.hukum("Yes, it is.", "Yes. Because ...")["dogru"] and not c.hukum("No.", "Yes. Because ...")["dogru"]
    assert c.hukum("Final answer: No", "No, the company ...")["dogru"]
    assert c.anahtar_sayilar("Decreased by 1.7% in FY2022 in 3 segments") == [(1.7, 1, True, 1.0)]  # yil ve '3' anahtar degil
    r = c.anahtar_sayi("It shrank 0.9%", "The consumer segment shrunk by 0.9% organically.")
    assert r["hepsi"] and r["oran"] == 1.0
    r = c.anahtar_sayi("margin was 1.7%", "decreased by 1.7% and 2.5%")
    assert r["oran"] == 0.5 and not r["hepsi"]

    # 1) ve 3) gelistirme kumesinde
    sorular = {s["id"]: s for s in d.yukle_sorular()}
    fb = [json.loads(l) for l in open(KOK / "data" / "ham" / "financebench" / "sorular.jsonl", encoding="utf-8") if l.strip()]
    dv = [x for x in fb if x["financebench_id"] in sorular]
    turler = collections.Counter(c.tur(x["answer"]) for x in dv)
    print("gold cevap turleri (gelistirme):", dict(turler))
    assert turler == {"salt_sayi": 34, "hukum": 30, "anahtar_sayi": 28, "serbest": 7}, turler
    for x in dv:
        r = c.skorla(x["answer"], x["answer"], x["question"])
        if r["tur"] == "salt_sayi":
            assert r["hassasiyet"] and r["tolerans"], (x["answer"], r)
        elif r["tur"] == "hukum":
            assert r["dogru"], (x["answer"], r)
        elif r["tur"] == "anahtar_sayi" and r["n"]:
            assert r["hepsi"], (x["answer"], r)
    print("gold = tahmin: tum deterministik turler gecti")
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
