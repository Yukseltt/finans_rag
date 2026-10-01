# Hata analizi: bir siralamanin (ornegin e5 + reranker) hangi soru turlerinde, hangi kanit
# sayilarinda ve hangi sirada kacirdigini gosterir.
#
# Neden: toplam Recall@k "ne kadar" kacirdigimizi soyler, "neden"i soylemez. Bu betik hatanin
# nerede yogunlastigini gosterir (soru turu, cok kanitli sorular, kacirilan kanitin sirasi,
# kanit metninin sayi yogunlugu).
#
# Kullanim: python src/hata_analizi.py [siralama_adi]     (varsayilan: dense_e5-base_rerank)
# Girdi:    data/islenmis/siralamalar/<ad>_{ortak,tek}.json
# Cikti:    ekrana ozet + sonuclar/hata_analizi.json
# Sadece gelistirme kumesi (kilitli kume incelenmez).
import collections
import json
import re
import statistics
import sys
from pathlib import Path

import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"


def kova(ilk):
    if ilk is None:
        return "yok(>100)"
    return "<=5" if ilk <= 5 else "6-10" if ilk <= 10 else "11-50" if ilk <= 50 else "51-100"


def main():
    ad = sys.argv[1] if len(sys.argv) > 1 else "dense_e5-base_rerank"
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    bilgi = d.yukle_chunk_bilgi()
    rapor = {"siralama": ad, "kume": "gelistirme"}
    for uzay in ("ortak", "tek"):
        sr = json.load(open(SIRA / f"{ad}_{uzay}.json", encoding="utf-8"))
        tur = collections.defaultdict(lambda: [0, 0])
        kanit_sayisi = collections.defaultdict(lambda: [0, 0])
        sira_dagilimi = collections.Counter()
        rakam = {"bulunan": [], "kacirilan": []}
        for s in sorular:
            for kn in s["kanitlar"]:
                hedef = (kn["doc"], kn["sayfa"])
                ilk = next((r for r, c in enumerate(sr[s["id"]], 1) if bilgi[c][:2] == hedef), None)
                bulundu = ilk is not None and ilk <= 5
                tur[s["tur"]][1] += 1
                tur[s["tur"]][0] += bulundu
                n = min(len(s["kanitlar"]), 3)
                kanit_sayisi[n][1] += 1
                kanit_sayisi[n][0] += bulundu
                sira_dagilimi[kova(ilk)] += 1
                rakam["bulunan" if bulundu else "kacirilan"].append(
                    len(re.findall(r"\d", kn["metin"])) / max(len(kn["metin"]), 1))
        rapor[uzay] = {
            "soru_turu_R5": {t: {"bulunan": a, "toplam": b, "oran": round(a / b, 3)} for t, (a, b) in tur.items()},
            "kanit_sayisi_R5(3=3+)": {str(k): {"bulunan": a, "toplam": b, "oran": round(a / b, 3)}
                                      for k, (a, b) in sorted(kanit_sayisi.items())},
            "kanit_sirasi": dict(sira_dagilimi),
            "rakam_orani_medyan": {k: round(statistics.median(v), 3) for k, v in rakam.items() if v},
        }
        print(f"\n== {ad}, {uzay}")
        print("  soru turu R@5:", {t: f"{v['bulunan']}/{v['toplam']}" for t, v in rapor[uzay]["soru_turu_R5"].items()})
        print("  kanit sayisi R@5:", {k: f"{v['bulunan']}/{v['toplam']}" for k, v in rapor[uzay]["kanit_sayisi_R5(3=3+)"].items()})
        print("  kanit sirasi:", rapor[uzay]["kanit_sirasi"])
        print("  rakam orani medyan:", rapor[uzay]["rakam_orani_medyan"])
    (KOK / "sonuclar" / "hata_analizi.json").write_text(json.dumps(rapor, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
