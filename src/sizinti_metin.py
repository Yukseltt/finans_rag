# FinQA ile FinanceBench arasinda metin duzeyinde ortusme arar (sirket eslemesinden bagimsiz).
#
# Yontem: metinler normalize edilir, 8 kelimelik parcalara (shingle) bolunur.
# Her FinanceBench kanit sayfasi icin, her FinQA ornegine su oran hesaplanir:
#     kapsama = (FinQA ornegi parcalarindan sayfada da gecenler) / (FinQA ornegi parca sayisi)
# Kapsama 1'e yakinsa FinQA ornegi o sayfadan alinmis demektir.
#
# Kullanim: python src/sizinti_metin.py
# Cikti:    ekrana ozet + sonuclar/sizinti_metin_raporu.json
import collections
import json
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "data" / "ham"
SONUC = KOK / "sonuclar"

N = 8            # parca uzunlugu (kelime)
ESIK = 0.3       # raporlanacak en dusuk kapsama; keyfi, dagilim da yazdirilir


def normalize(metin: str) -> list[str]:
    # kucuk harf, harf-rakam disindaki her sey bosluk, tokenlara ayir
    return re.sub(r"[^a-z0-9]+", " ", metin.lower()).split()


def parcalar(kelimeler: list[str]) -> set[tuple]:
    return {tuple(kelimeler[i:i + N]) for i in range(len(kelimeler) - N + 1)}


def finqa_metni(e: dict) -> str:
    tablo = " ".join(" ".join(str(h) for h in satir) for satir in e["table"])
    return " ".join(e["pre_text"]) + " " + tablo + " " + " ".join(e["post_text"])


def main():
    # FinQA: her ornegin parca kumesi + tersine indeks (parca -> ornek numaralari)
    ornekler = []
    for bolum in ("train", "dev", "test"):
        for e in json.load(open(HAM / "finqa" / f"{bolum}.json", encoding="utf-8")):
            ornekler.append((e["id"], bolum, parcalar(normalize(finqa_metni(e)))))
    indeks = collections.defaultdict(list)
    for i, (_, _, p) in enumerate(ornekler):
        for parca in p:
            indeks[parca].append(i)
    print(f"FinQA: {len(ornekler)} ornek, {len(indeks)} benzersiz parca")

    sorular = [json.loads(s) for s in open(HAM / "financebench" / "sorular.jsonl", encoding="utf-8") if s.strip()]

    sonuclar = []
    for s in sorular:
        for ev in s["evidence"]:
            # tam sayfa metni: FinQA ornegi bu sayfadan alinmis mi sorusuna cevap verir
            sayfa = parcalar(normalize(ev["evidence_text_full_page"]))
            ortak = collections.Counter()
            for parca in sayfa:
                for i in indeks.get(parca, ()):
                    ortak[i] += 1
            if not ortak:
                continue
            i, adet = max(ortak.items(), key=lambda kv: kv[1] / max(len(ornekler[kv[0]][2]), 1))
            kapsama = adet / max(len(ornekler[i][2]), 1)
            sonuclar.append({
                "fb_soru": s["financebench_id"], "fb_belge": s["doc_name"],
                "fb_sayfa": ev["evidence_page_num"],
                "finqa_id": ornekler[i][0], "finqa_bolum": ornekler[i][1],
                "ortak_parca": adet, "kapsama": round(kapsama, 3),
            })

    sonuclar.sort(key=lambda r: -r["kapsama"])
    kapsamalar = [r["kapsama"] for r in sonuclar]
    print(f"Kanit sayfasi sayisi (en az 1 ortak parca): {len(sonuclar)}")
    for esik in (0.1, 0.3, 0.5, 0.8):
        print(f"  kapsama >= {esik}: {sum(1 for k in kapsamalar if k >= esik)}")
    print(f"En yuksek {ESIK} ustu eslesmeler:")
    for r in sonuclar:
        if r["kapsama"] >= ESIK:
            print(f"  {r['fb_soru']} {r['fb_belge']} s.{r['fb_sayfa']} <- {r['finqa_id']} "
                  f"({r['finqa_bolum']}) kapsama={r['kapsama']} ortak={r['ortak_parca']}")

    (SONUC / "sizinti_metin_raporu.json").write_text(
        json.dumps({"parca_uzunlugu": N, "esik": ESIK, "eslesmeler": sonuclar},
                   indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
