# FinQA (egitim) ile FinanceBench (test) arasindaki sirket ve sirket-yil ortusmesini olcer.
#
# Kullanim: python src/sizinti_kontrol.py
# Girdi:    data/ham/..., sonuclar/sirket_eslesme.json
# Cikti:    ekrana ozet + sonuclar/sizinti_raporu.json
#
# FinQA id bicimi: "TICKER/YIL/page_N.pdf-k"; YIL, 10-K'nin mali yilidir.
# FinanceBench doc_period de mali yildir, bu yuzden (ticker, yil) dogrudan karsilastirilir.
import collections
import json
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "data" / "ham"
SONUC = KOK / "sonuclar"


def jsonl(yol):
    with open(yol, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


def main():
    eslesme = json.load(open(SONUC / "sirket_eslesme.json", encoding="utf-8"))["eslesme"]
    belgeler = jsonl(HAM / "financebench" / "belgeler.jsonl")
    sorular = jsonl(HAM / "financebench" / "sorular.jsonl")

    # Eslemesi olmayan sirket varsa sessizce atlamak yerine dur: denetim eksik olurdu.
    eksik = {b["company"] for b in belgeler} - set(eslesme)
    assert not eksik, f"eslemesi olmayan sirketler: {eksik}"
    # ters tablo: ticker -> FinanceBench sirket adi
    ters = {t: ad for ad, kodlar in eslesme.items() for t in kodlar}

    # FinQA: her ornek icin (ticker, yil, bolum)
    finqa = []
    for bolum in ("train", "dev", "test"):
        for e in json.load(open(HAM / "finqa" / f"{bolum}.json", encoding="utf-8")):
            ticker, yil = e["id"].split("/")[:2]
            finqa.append((ticker, int(yil), bolum))

    # 1) Sirket duzeyi
    finqa_tickerlar = {t for t, _, _ in finqa}
    ortak_tickerlar = sorted(finqa_tickerlar & set(ters))
    ortak_sirketler = sorted({ters[t] for t in ortak_tickerlar})

    # 2) Sirket-yil duzeyi. FinanceBench anahtari: belgenin (sirket, doc_period) cifti.
    fb_anahtar = collections.defaultdict(list)  # (sirket, yil) -> doc_name listesi
    for b in belgeler:
        fb_anahtar[(b["company"], int(b["doc_period"]))].append((b["doc_name"], b["doc_type"]))

    ortusen = {}  # (sirket, yil) -> {"finqa": {bolum: adet}, "fb_belgeler": [...]}
    for ticker, yil, bolum in finqa:
        sirket = ters.get(ticker)
        if sirket and (sirket, yil) in fb_anahtar:
            kayit = ortusen.setdefault(
                (sirket, yil),
                {"finqa": collections.Counter(), "fb_belgeler": fb_anahtar[(sirket, yil)]},
            )
            kayit["finqa"][bolum] += 1

    # 3) Hangi FinanceBench sorulari ortusen belgelere bagli?
    belge_turu = {b["doc_name"]: (b["company"], int(b["doc_period"]), b["doc_type"]) for b in belgeler}
    etkilenen_sorular = []
    for s in sorular:
        sirket, yil, tur = belge_turu[s["doc_name"]]
        if (sirket, yil) in ortusen:
            etkilenen_sorular.append(
                {"id": s["financebench_id"], "doc_name": s["doc_name"], "doc_type": tur,
                 "finqa_ornek_sayisi": dict(ortusen[(sirket, yil)]["finqa"])}
            )

    # 4) Sirket duzeyinde etkilenen soru sayisi (yil farkli olsa da ayni sirket)
    sirket_duzeyi_soru = sum(1 for s in sorular if s["company"] in set(ortak_sirketler))

    # 5) Sayfa duzeyi: FinQA (sirket, yil, sayfa) ile FinanceBench kanit sayfasi.
    # UYARI: bu karsilastirma GECERSIZ sayilmali. FinQA'nin page_N numarasi baski sayfa
    # numarasi (PDF sirasindan farkli; GIS 2019'da PDF idx = N-5), FinanceBench ise 0 tabanli
    # PDF sirasi kullanir (pdf_parse sonrasi 127/127 kanitla dogrulandi). Gecerli sayfa/metin
    # kontrolu sizinti_metin.py'dir; bu blok yalnizca tarihsel kayit olarak duruyor.
    finqa_sayfalar = set()
    for bolum in ("train", "dev", "test"):
        for e in json.load(open(HAM / "finqa" / f"{bolum}.json", encoding="utf-8")):
            ticker, yil, sayfa = e["id"].split("/")[:3]
            finqa_sayfalar.add((ters.get(ticker), int(yil), int(sayfa.split("_")[1].split(".")[0])))
    sayfa_eslesen = {}
    for kayma in (0, 1):
        bulunan = set()
        for s in sorular:
            sirket, yil, _ = belge_turu[s["doc_name"]]
            for ev in s["evidence"]:
                if (sirket, yil, ev["evidence_page_num"] + kayma) in finqa_sayfalar:
                    bulunan.add(s["financebench_id"])
        sayfa_eslesen[f"fb_sayfa_+{kayma}"] = sorted(bulunan)

    toplam = collections.Counter(b for _, _, b in finqa)
    etkilenen_finqa = collections.Counter()
    for (_, _), k in ortusen.items():
        etkilenen_finqa.update(k["finqa"])

    print(f"FinanceBench sirketi: {len(eslesme)}, FinQA ticker: {len(finqa_tickerlar)}")
    print(f"Sirket duzeyinde ortak: {len(ortak_sirketler)} -> {ortak_sirketler}")
    print(f"Sirket-yil duzeyinde ortusen: {len(ortusen)}")
    for (sirket, yil), k in sorted(ortusen.items()):
        turler = ",".join(t for _, t in k["fb_belgeler"])
        print(f"  {sirket} {yil}  FinQA: {dict(k['finqa'])}  FB belge turu: {turler}")
    print(f"Etkilenen FinQA ornegi: {dict(etkilenen_finqa)} / toplam {dict(toplam)}")
    print(f"Etkilenen FinanceBench sorusu (sirket-yil): {len(etkilenen_sorular)} / {len(sorular)}")
    print(f"Etkilenen FinanceBench sorusu (sadece sirket): {sirket_duzeyi_soru} / {len(sorular)}")
    for ad, liste in sayfa_eslesen.items():
        print(f"Sayfa duzeyi eslesme ({ad}): {len(liste)} soru {liste}")

    rapor = {
        "sirket_duzeyi_ortak": ortak_sirketler,
        "sirket_yil_ortusen": [
            {"sirket": s, "yil": y, "finqa": dict(k["finqa"]),
             "fb_belgeler": [d for d, _ in k["fb_belgeler"]]}
            for (s, y), k in sorted(ortusen.items())
        ],
        "etkilenen_finqa_ornek": dict(etkilenen_finqa),
        "finqa_toplam": dict(toplam),
        "etkilenen_fb_soru": etkilenen_sorular,
        "etkilenen_fb_soru_sadece_sirket": sirket_duzeyi_soru,
        "sayfa_duzeyi_eslesen_fb_soru": sayfa_eslesen,
        "fb_soru_toplam": len(sorular),
    }
    (SONUC / "sizinti_raporu.json").write_text(
        json.dumps(rapor, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
