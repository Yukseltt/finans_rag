# Deney 5, adim 1: okuyucu LLM'e gonderilecek ISTEKLERI uretir (API cagrisi YAPMAZ).
#
# Kullanim: python src/baglam_hazirla.py
# Girdi:    gelistirme sorulari, Chroma koleksiyonu (c200), kayitli c300 siralamasi, sayfa metinleri
# Cikti:    data/islenmis/istekler/{k0,k1_c200,k1_c300,k2}.jsonl   (soru basina bir istek)
#           sonuclar/prompt_<surum>.json                           (DONDURULMUS prompt sablonu + sha256)
#           sonuclar/pilot_idler.json                              (pilot: 12 soru, sadece bicim dogrulamasi)
#
# Kosullar (KARAR_GUNLUGU.md, Deney 5):
#   K0 kapali kitap: baglam yok
#   K1 getirilen: ortak havuz, e5-base -> reranker, ilk 1000 KELIME (tam 1000'de kesilir)
#      c200: Chroma (yeniden acilmis kalici koleksiyon, Deney 6b) uzerinden
#      c300: kayitli tam-arama + reranker siralamasindan (Chroma c300 koleksiyonu dogrulanmadi; protokol notu)
#   K2 oracle: gold kanit sayfalarinin tam metni (kesilmez; referans kosul)
#
# Her baglam parcasi bir etiketle verilir: [belge: <doc_name>, sayfa: <sayfa_idx>]; sayfa numarasi
# gold'daki evidence_page_num ile ayni tabandadir (0 tabanli PDF sirasi, Karar 6).
# Etiketler kelime sayilmaz. Sadece gelistirme kumesi (kilitli kume icin ayri, tek seferlik betik).
#
# DONDURMA: prompt sablonu sonuclar/prompt_<surum>.json'a sha256 ile yazilir. Ayni surum numarasi ile sablon
# degisirse betik reddeder; degisiklik yeni surum numarasi gerektirir (Deney 5 on kaydi, prompt kurali).
import hashlib
import json
import statistics
import sys
from pathlib import Path

import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
ISTEK_KLASORU = KOK / "data" / "islenmis" / "istekler"
SAYFA_KLASORU = KOK / "data" / "islenmis" / "sayfalar"
SIRA = KOK / "data" / "islenmis" / "siralamalar"
PROMPT_SURUM = "v2"
BUTCE_KELIME = 1000
RERANK_DERINLIK = 50  # c200 icin (Deney 4/5 on kaydi); c300 siralamasi kayitli (derinlik 33)
PILOT_SORU_TURU_BASINA = 4

SISTEM = ("You are a careful financial analyst answering questions about public company filings "
          "(10-K, 10-Q, 8-K, earnings releases). Be accurate and concise.")

ORTAK_TALIMAT = """- Follow any rounding, unit or formatting instructions contained in the question.
- Keep the reasoning short (a few sentences or a short calculation).
- If the question is a yes/no question, begin the final answer with "Yes" or "No", then add a brief reason.
- If the answer is a number, state it with its unit (for example "$1,577 million" or "12.3%").
- Keep the final answer short (a number, a Yes/No with a brief reason, or one to three sentences) unless the question asks for a list.
- Write plain text only: no markdown, no bold, no bullet symbols."""

KULLANICI_BAGLAMLI = """Below are passages from company filings. Each passage is labelled with its document and page number (page numbers are PDF page indices starting at 0). The passages may come from different years, quarters or filings; use only those that match the company, period and metric asked.

{BAGLAM}

Question: {SORU}

Instructions:
- Use ONLY the information in the passages above. If they do not contain what is needed, say so briefly and give your best answer anyway.
""" + ORTAK_TALIMAT + """
- End your reply with exactly these two lines:
Final answer: <your answer>
Sources: <DOCUMENT_NAME>, <PAGE>; <DOCUMENT_NAME>, <PAGE>   (copy the document name and page number exactly as they appear in the passage labels; list only the passages you actually used; write "none" if you used none)"""

KULLANICI_KAPALI = """No passages are provided. Answer from your own knowledge of the company and its public filings.

Question: {SORU}

Instructions:
- If you do not know the exact figures, say so briefly and give your best estimate.
""" + ORTAK_TALIMAT + """
- End your reply with exactly this line:
Final answer: <your answer>"""


def sablon_ozeti():
    veri = {"surum": PROMPT_SURUM, "sistem": SISTEM, "kullanici_baglamli": KULLANICI_BAGLAMLI,
            "kullanici_kapali": KULLANICI_KAPALI, "butce_kelime": BUTCE_KELIME}
    veri["sha256"] = hashlib.sha256(json.dumps(veri, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return veri


def sablonu_dondur(yol=None):
    # Ayni surum numarasi ile farkli sablon yazilmasini engeller (prompt dondurma kurali).
    yol = yol or (KOK / "sonuclar" / f"prompt_{PROMPT_SURUM}.json")
    yeni = sablon_ozeti()
    if yol.exists():
        eski = json.load(open(yol, encoding="utf-8"))
        if eski["sha256"] != yeni["sha256"]:
            raise SystemExit(f"prompt sablonu {PROMPT_SURUM} donduruldu ama degisti; yeni surum numarasi gerekir "
                             f"(eski {eski['sha256'][:12]}, yeni {yeni['sha256'][:12]})")
    else:
        yol.write_text(json.dumps(yeni, indent=2, ensure_ascii=False), encoding="utf-8")
    return yeni


def etiket(doc, sayfa):
    return f"[belge: {doc}, sayfa: {sayfa}]"


def baglam_k1(siralama, bilgi, butce=BUTCE_KELIME):
    # Siralanmis chunk'lari birlestirir ve TAM `butce` kelimede keser (son chunk kismen alinabilir).
    # Doner: (metin, [(doc, sayfa, alinan_kelime), ...])
    bloklar, alinan, toplam = [], [], 0
    for cid in siralama:
        if toplam >= butce:
            break
        doc, sayfa, metin = bilgi[cid]
        kelimeler = metin.split()
        al = kelimeler[:butce - toplam]
        bloklar.append(etiket(doc, sayfa) + "\n" + " ".join(al))
        alinan.append((doc, sayfa, len(al)))
        toplam += len(al)
    return "\n\n".join(bloklar), alinan


def sayfa_metni(doc, sayfa, onbellek):
    if doc not in onbellek:
        onbellek[doc] = {}
        with open(SAYFA_KLASORU / f"{doc}.jsonl", encoding="utf-8") as f:
            for satir in f:
                r = json.loads(satir)
                onbellek[doc][r["sayfa_idx"]] = r["metin"]
    return " ".join(onbellek[doc][sayfa].split())  # chunk metniyle ayni temsil: bosluklar tek


def baglam_k2(soru, onbellek):
    # Gold kanit sayfalarinin tam metni (tekrarsiz, belge ve sayfa sirasiyla)
    sayfalar = sorted({(k["doc"], k["sayfa"]) for k in soru["kanitlar"]})
    bloklar, kelime = [], 0
    for doc, sayfa in sayfalar:
        metin = sayfa_metni(doc, sayfa, onbellek)
        bloklar.append(etiket(doc, sayfa) + "\n" + metin)
        kelime += len(metin.split())
    return "\n\n".join(bloklar), [(doc, sayfa) for doc, sayfa in sayfalar], kelime


def istek(soru, kosul, baglam=None):
    if baglam is None:
        kullanici = KULLANICI_KAPALI.replace("{SORU}", soru["soru"])
    else:
        kullanici = KULLANICI_BAGLAMLI.replace("{BAGLAM}", baglam).replace("{SORU}", soru["soru"])
    return {"id": soru["id"], "kosul": kosul, "prompt_surum": PROMPT_SURUM, "sistem": SISTEM, "kullanici": kullanici}


def pilot_idleri(sorular):
    # Deterministik, tur basina ilk 4 (id sirasiyla): pilot yalnizca BICIM dogrulamasidir
    secilen = []
    for tur in sorted({s["tur"] for s in sorular}):
        secilen += sorted(s["id"] for s in sorular if s["tur"] == tur)[:PILOT_SORU_TURU_BASINA]
    return sorted(secilen)


def chroma_siralama(sorular):
    # e5 sorgu vektorleri (dense_baseline ile ayni model/onek) -> Chroma (yeniden acilmis koleksiyon, ef_search=100)
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import vektor_deposu as vd
    model = SentenceTransformer("intfloat/e5-base-v2", device="cuda")
    model.half()
    model.max_seq_length = 512
    Q = model.encode(["query: " + s["soru"] for s in sorular], batch_size=32, normalize_embeddings=True,
                     convert_to_numpy=True).astype(np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    del model
    depo = vd.ChromaDeposu()
    assert depo.ac() is not None, "Chroma koleksiyonu yok; once src/deney6_vdb.py ile kurulmali"
    depo.ef_search_ayarla(100)
    return {s["id"]: depo.ara(Q[i], 100) for i, s in enumerate(sorular)}


def r2_uret():
    # Deney 8: K1-R2 istekleri. Baglam, Deney 7'nin belge yonlendirmeli (R2) reranker siralamasindan; kural ve prompt
    # K1 ile ayni. Siralama dosyasi: data/islenmis/siralamalar/yonlendirme_e5_R2_rerank_ortak.json (deney7_yonlendirme.py).
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    sablonu_dondur()
    bilgi = d.yukle_chunk_bilgi()
    sirali = json.load(open(SIRA / "yonlendirme_e5_R2_rerank_ortak.json", encoding="utf-8"))
    ISTEK_KLASORU.mkdir(parents=True, exist_ok=True)
    kelimeler, gold_var, oran = [], [], []
    with open(ISTEK_KLASORU / "k1_r2.jsonl", "w", encoding="utf-8") as f:
        for s in sorular:
            metin, alinan = baglam_k1(sirali[s["id"]], bilgi)
            r = istek(s, "K1-R2", metin)
            r.update({"baglam_kelime": sum(a[2] for a in alinan), "baglam_sayfalar": [[a[0], a[1]] for a in alinan]})
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            gold = {(k["doc"], k["sayfa"]) for k in s["kanitlar"]}
            bag = {(a[0], a[1]) for a in alinan}
            kelimeler.append(r["baglam_kelime"])
            gold_var.append(bool(gold & bag))
            oran.append(len(gold & bag) / len(gold))
    print(f"k1_r2: {len(sorular)} istek | baglam kelime medyan {statistics.median(kelimeler):.0f} (maks {max(kelimeler)}) | "
          f">=1 gold sayfa var {sum(gold_var) / len(gold_var):.3f} | kanit orani {sum(oran) / len(oran):.3f}")


def main():
    if "--r2" in sys.argv:
        return r2_uret()
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    sablon = sablonu_dondur()
    print(f"prompt {sablon['surum']} sha256 {sablon['sha256'][:16]}... (dondurulmus: sonuclar/prompt_{PROMPT_SURUM}.json)")
    ISTEK_KLASORU.mkdir(parents=True, exist_ok=True)

    # K1-c200: Chroma -> reranker (Deney 2 ile ayni model, derinlik 50, ayni skor onbellegi)
    import rerank as rr
    bilgi200 = d.yukle_chunk_bilgi()
    ham = chroma_siralama(sorular)
    skorlar, hesaplanan, _ = rr.skor_hazirla(sorular, bilgi200, [ham], derinlik=RERANK_DERINLIK)
    sirali200 = rr.yeniden_sirala(sorular, ham, skorlar, RERANK_DERINLIK)
    # K1-c300: kayitli tam-arama + reranker siralamasi (Deney 4)
    bilgi300 = d.yukle_chunk_bilgi(d.chunks_yolu("c300"))
    sirali300 = json.load(open(SIRA / "dense_e5-base_c300_rerank_ortak.json", encoding="utf-8"))

    sayfa_onbellek = {}
    istekler = {"k0": [], "k1_c200": [], "k1_c300": [], "k2": []}
    ist = {k: [] for k in ("k1_c200", "k1_c300", "k2")}
    for s in sorular:
        istekler["k0"].append(istek(s, "K0"))
        for ad, sirali, bilgi in (("k1_c200", sirali200, bilgi200), ("k1_c300", sirali300, bilgi300)):
            metin, alinan = baglam_k1(sirali[s["id"]], bilgi)
            kelime = sum(a[2] for a in alinan)
            r = istek(s, ad.upper().replace("_", "-"), metin)
            r.update({"baglam_kelime": kelime, "baglam_sayfalar": [[a[0], a[1]] for a in alinan]})
            istekler[ad].append(r)
            gold = {(k["doc"], k["sayfa"]) for k in s["kanitlar"]}
            ist[ad].append({"kelime": kelime, "gold_var": bool(gold & {(a[0], a[1]) for a in alinan}),
                            "kanit_orani": len(gold & {(a[0], a[1]) for a in alinan}) / len(gold)})
        metin, sayfalar, kelime = baglam_k2(s, sayfa_onbellek)
        r = istek(s, "K2", metin)
        r.update({"baglam_kelime": kelime, "baglam_sayfalar": [list(p) for p in sayfalar]})
        istekler["k2"].append(r)
        ist["k2"].append({"kelime": kelime, "gold_var": True, "kanit_orani": 1.0})

    for ad, liste in istekler.items():
        with open(ISTEK_KLASORU / f"{ad}.jsonl", "w", encoding="utf-8") as f:
            for r in liste:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pilot = pilot_idleri(sorular)
    (KOK / "sonuclar" / "pilot_idler.json").write_text(json.dumps({"surum": PROMPT_SURUM, "idler": pilot}, indent=2), encoding="utf-8")

    print(f"\n{len(sorular)} gelistirme sorusu; pilot: {len(pilot)} soru (tur basina {PILOT_SORU_TURU_BASINA}, id sirasiyla)")
    print(f"{'kosul':9s} {'baglam kelime (medyan / ort / maks)':38s} {'>=1 gold sayfa var':20s} {'kanit orani (kanit bazli)'}")
    print(f"{'k0':9s} {'0 (baglam yok)':38s} {'-':20s} -")
    for ad, liste in ist.items():
        k = [x["kelime"] for x in liste]
        print(f"{ad:9s} {statistics.median(k):>10.0f} / {statistics.mean(k):>8.0f} / {max(k):>6d}{'':8s} "
              f"{sum(x['gold_var'] for x in liste) / len(liste):>16.3f}     {sum(x['kanit_orani'] for x in liste) / len(liste):.3f}")


if __name__ == "__main__":
    main()
