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
