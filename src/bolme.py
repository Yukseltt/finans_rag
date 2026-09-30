# FinanceBench'i gelistirme / kilitli test olarak boler ve egitimden cikarilacak FinQA orneklerini listeler.
#
# Kullanim: python src/bolme.py
# Girdi:    data/ham/..., sonuclar/sizinti_raporu.json
# Cikti:    sonuclar/fb_bolme.json, sonuclar/finqa_haric.json
#
# Bolme kurali: SIRKET bazinda (ayni sirketin belgeleri icerik paylasir), ~50 soruluk
# kilitli test. Rastgelelik sabit tohumla; aday tohumlar arasindan secim SADECE bolmenin
# yapisina (soru sayisi ve soru turu dengesi) bakar, hicbir model sonucuna bakmaz.
# Kilitli testin icerigi proje sonuna kadar incelenmez ve ayar icin kullanilmaz.
import collections
import json
import random
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "data" / "ham"
SONUC = KOK / "sonuclar"

HEDEF_KILITLI = 50
TOHUM_ADAY_SAYISI = 10000


def jsonl(yol):
    with open(yol, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


def bolme_dene(tohum, sirketler, sirket_sorulari, turler):
    # Sirketleri karistir, kilitli test hedefe ulasana kadar sirket ekle.
    sira = sorted(sirketler)
    random.Random(tohum).shuffle(sira)
    kilitli, n = [], 0
    for s in sira:
        if n >= HEDEF_KILITLI:
            break
        kilitli.append(s)
        n += len(sirket_sorulari[s])
    sayac = collections.Counter(turler[q] for s in kilitli for q in sirket_sorulari[s])
    # puan: hedeften sapma + soru turu dengesizligi (kucuk iyi)
    ideal = n / 3
    puan = abs(n - HEDEF_KILITLI) + sum(abs(sayac[t] - ideal) for t in set(turler.values()))
    return puan, kilitli, n


def main():
    sorular = jsonl(HAM / "financebench" / "sorular.jsonl")
    sirket_sorulari = collections.defaultdict(list)
    turler = {}
    for s in sorular:
        sirket_sorulari[s["company"]].append(s["financebench_id"])
        turler[s["financebench_id"]] = s["question_type"]

    en_iyi = min(
        (bolme_dene(t, sirket_sorulari, sirket_sorulari, turler) + (t,) for t in range(TOHUM_ADAY_SAYISI)),
        key=lambda x: x[0],
    )
    puan, kilitli_sirketler, _, tohum = en_iyi
    kilitli_ids = sorted(q for s in kilitli_sirketler for q in sirket_sorulari[s])
    gelistirme_ids = sorted(set(turler) - set(kilitli_ids))

    sayac = lambda ids: dict(collections.Counter(turler[q] for q in ids))
    bolme = {
        "tohum": tohum, "kural": "sirket bazinda, ~50 soruluk kilitli test",
        "kilitli_sirketler": sorted(kilitli_sirketler),
        "gelistirme": {"soru_sayisi": len(gelistirme_ids), "turler": sayac(gelistirme_ids), "idler": gelistirme_ids},
        "kilitli": {"soru_sayisi": len(kilitli_ids), "turler": sayac(kilitli_ids), "idler": kilitli_ids},
    }
    (SONUC / "fb_bolme.json").write_text(json.dumps(bolme, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"tohum={tohum}  gelistirme={len(gelistirme_ids)} {sayac(gelistirme_ids)}")
    print(f"                kilitli={len(kilitli_ids)} {sayac(kilitli_ids)}  sirket sayisi={len(kilitli_sirketler)}")

    # Egitimden cikarilacak FinQA ornekleri: FinanceBench sorusu olan belgelerle
    # ayni (sirket, yil) raporundan gelenler.
    rapor = json.load(open(SONUC / "sizinti_raporu.json", encoding="utf-8"))
    eslesme = json.load(open(SONUC / "sirket_eslesme.json", encoding="utf-8"))["eslesme"]
    ters = {t: ad for ad, kodlar in eslesme.items() for t in kodlar}
    belgeler = {b["doc_name"]: b for b in jsonl(HAM / "financebench" / "belgeler.jsonl")}
    hedef = {(belgeler[q["doc_name"]]["company"], int(belgeler[q["doc_name"]]["doc_period"]))
             for q in rapor["etkilenen_fb_soru"]}
    haric = []
    for bolum in ("train", "dev", "test"):
        for e in json.load(open(HAM / "finqa" / f"{bolum}.json", encoding="utf-8")):
            ticker, yil = e["id"].split("/")[:2]
            if (ters.get(ticker), int(yil)) in hedef:
                haric.append({"id": e["id"], "bolum": bolum})
    (SONUC / "finqa_haric.json").write_text(
        json.dumps({"neden": "FinanceBench sorusu olan belgeyle ayni sirket-yil raporu",
                    "sirket_yil": sorted(f"{s} {y}" for s, y in hedef), "ornekler": haric},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"FinQA'dan cikarilacak: {len(haric)} ornek {dict(collections.Counter(h['bolum'] for h in haric))}")


if __name__ == "__main__":
    main()
