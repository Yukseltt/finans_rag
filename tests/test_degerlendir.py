# degerlendir.py'nin kendi dogrulugunu sinar. Metrik kodu yanlissa tum sonuclar yanlis olur,
# bu yuzden uc bilinen durumda beklenen cevabi kontrol eder:
#   1) kusursuz siralama (dogru sayfa en basta)  -> recall 1, MRR 1
#   2) kanit hic yok                              -> recall 0, MRR 0
#   3) rastgele siralama                          -> recall ~0
#   4) kilitli koruma: kilitli soru olculmeye calisilirsa hata verir
#
# Kullanim: python tests/test_degerlendir.py
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import degerlendir as d  # noqa: E402


def main():
    sorular = d.yukle_sorular()
    bilgi = d.yukle_chunk_bilgi()
    sayfa_chunk = {}
    for cid, (doc, sayfa, _) in bilgi.items():
        sayfa_chunk.setdefault((doc, sayfa), []).append(cid)
    tum = list(bilgi)
    print(f"{len(sorular)} gelistirme sorusu, {len(bilgi)} chunk")

    # 1) kusursuz: her kanit sayfasinin chunk'lari en basta
    mukemmel = {}
    for s in sorular:
        liste = []
        for k in s["kanitlar"]:
            liste += sayfa_chunk[(k["doc"], k["sayfa"])]
        mukemmel[s["id"]] = liste[:50]
    r = d.olc(mukemmel, sorular, bilgi, n_boot=200)
    m = r["metrikler"]
    d.yazdir(r, "kusursuz")
    assert m["recall@50"]["deger"] == 1.0, m["recall@50"]
    assert m["soru_tum@50"]["deger"] == 1.0
    assert m["mrr"]["deger"] > 0.5  # birden fazla kanit ayni anda en basta olamaz
    assert m["metin_kapsama@50"]["deger"] > 0.5

    # 2) kanit yok: kanit sayfalari disindan chunk'lar
    rng = random.Random(0)
    yok = {}
    for s in sorular:
        yasak = {(k["doc"], k["sayfa"]) for k in s["kanitlar"]}
        adaylar = rng.sample(tum, 60)
        yok[s["id"]] = [c for c in adaylar if bilgi[c][:2] not in yasak][:50]
    r = d.olc(yok, sorular, bilgi, n_boot=200)
    d.yazdir(r, "kanit yok")
    assert r["metrikler"]["recall@50"]["deger"] == 0.0
    assert r["metrikler"]["mrr"]["deger"] == 0.0

    # 2b) butce metrigi: kusursuz siralamada ~ recall@5'e yakin, kanit yokken 0, her zaman recall@1 <= butce <= recall@50
    mk = d.olc(mukemmel, sorular, bilgi, n_boot=50)["metrikler"]
    assert mk["recall@1"]["deger"] <= mk["recall_butce"]["deger"] <= mk["recall@50"]["deger"], mk["recall_butce"]
    assert abs(mk["recall_butce"]["deger"] - mk["recall@5"]["deger"]) < 0.15, (mk["recall_butce"], mk["recall@5"])
    assert d.olc(yok, sorular, bilgi, n_boot=50)["metrikler"]["recall_butce"]["deger"] == 0.0
    # elle kontrol: tek soru, 3 chunk, kelime sayilari 600+300+300 -> butce 1000'de ilk iki chunk (birikim 600<1000, 900<1000, sonra 1200>=1000 -> uc chunk)
    kucuk_bilgi = {"a": ("D", 1, "w " * 600), "b": ("D", 2, "w " * 300), "c": ("D", 3, "w " * 300), "e": ("D", 9, "w " * 10)}
    kucuk_soru = [{"id": "q", "doc": "D", "tur": "t", "soru": "?", "kanitlar": [{"doc": "D", "sayfa": 3, "metin": "w w w w w w"}]}]
    r = d.olc({"q": ["a", "b", "c", "e"]}, kucuk_soru, kucuk_bilgi, n_boot=5, kilitli=True)["metrikler"]
    assert r["recall_butce"]["deger"] == 1.0, r["recall_butce"]  # c, birikim 900 < 1000 iken basliyor -> dahil
    r = d.olc({"q": ["a", "c", "b", "e"]}, kucuk_soru, kucuk_bilgi, n_boot=5, kilitli=True)["metrikler"]
    assert r["recall_butce"]["deger"] == 1.0                    # c ikinci: birikim 600 < 1000 -> dahil
    # c'den once birikim tam 1000 (600+300+100): 1000 < 1000 degil -> c penceredisi, recall_butce 0
    kucuk_bilgi["f"] = ("D", 8, "w " * 100)
    r = d.olc({"q": ["a", "b", "f", "c"]}, kucuk_soru, kucuk_bilgi, n_boot=5, kilitli=True)["metrikler"]
    assert r["recall_butce"]["deger"] == 0.0, r["recall_butce"]
    # ayni siralama ama c'den once birikim 910 (<1000): c dahil -> 1.0
    r = d.olc({"q": ["a", "b", "e", "c"]}, kucuk_soru, kucuk_bilgi, n_boot=5, kilitli=True)["metrikler"]
    assert r["recall_butce"]["deger"] == 1.0, r["recall_butce"]
    # 3) rastgele: 163 bin chunk icinden 50 tane; beklenen recall@50 ~ 0.0003
    rastgele = {s["id"]: rng.sample(tum, 50) for s in sorular}
    r = d.olc(rastgele, sorular, bilgi, n_boot=200)
    d.yazdir(r, "rastgele")
    assert r["metrikler"]["recall@50"]["deger"] < 0.05

    # 3b) eslestirilmis karsilastirma: ayni sey kendisiyle -> fark 0; kusursuz vs rastgele -> pozitif ve anlamli
    k = d.karsilastir(mukemmel, mukemmel, sorular, bilgi, k=5, n_boot=500)
    assert k["fark"] == 0 and k["ci95"] == [0, 0] and not k["anlamli"], k
    k = d.karsilastir(rastgele, mukemmel, sorular, bilgi, k=5, n_boot=500)
    print("karsilastir (rastgele -> kusursuz, recall@5):", {a: (round(v, 3) if isinstance(v, float) else v) for a, v in k.items()})
    assert k["fark"] > 0.9 and k["anlamli"]

    # 3c) sirket-kumeli bootstrap: kendisiyle karsilastirma 0; her soru ayri kume ise soru-bazliya yakin; kumeler daha genis aralik verir
    kume = d.soru_kumeleri(sorular)
    k = d.karsilastir(mukemmel, mukemmel, sorular, bilgi, k=5, n_boot=500, kume=kume)
    assert k["fark"] == 0 and k["ci95"] == [0, 0], k
    tek_kume = {s["id"]: s["id"] for s in sorular}
    soru_bazli = d.karsilastir(rastgele, mukemmel, sorular, bilgi, k=5, n_boot=2000)
    tekil = d.karsilastir(rastgele, mukemmel, sorular, bilgi, k=5, n_boot=2000, kume=tek_kume)
    assert abs(soru_bazli["fark"] - tekil["fark"]) < 1e-12
    assert abs(soru_bazli["ci95"][0] - tekil["ci95"][0]) < 0.03 and abs(soru_bazli["ci95"][1] - tekil["ci95"][1]) < 0.03
    sirketli = d.karsilastir(rastgele, mukemmel, sorular, bilgi, k=5, n_boot=2000, kume=kume)
    assert sirketli["fark"] == soru_bazli["fark"] and sirketli["anlamli"]
    print("kume bootstrap: tamam (21 sirket kumesi,", len(set(kume.values())), "kume)")

    # 4) kilitli koruma
    kilitli_sorular = d.yukle_sorular(kilitli=True)
    try:
        d.olc({s["id"]: [] for s in kilitli_sorular}, kilitli_sorular, bilgi)
    except ValueError:
        print("kilitli koruma: tamam (hata verdi)")
    else:
        raise AssertionError("kilitli koruma calismadi")
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
