# FinanceBench PDF'lerinden sayfa bazinda ham metin cikarir.
#
# Kullanim: python src/pdf_parse.py
# Girdi:    data/ham/financebench/pdfs/*.pdf
# Cikti:    data/islenmis/sayfalar/<doc_name>.jsonl  (satir basina bir sayfa)
#           sonuclar/parse_ozeti.json                (belge basina sayfa/bos sayfa/hata)
#
# Her satir: {"doc": ..., "sayfa_idx": 0 tabanli PDF sirasi, "metin": ...}
# Sayfa numarasi PDF sirasidir; FinanceBench'in evidence_page_num alaninin hangi
# tabanda oldugu Karar 6'da dogrulanacak, burada hicbir kayma uygulanmaz.
# Metin ham birakilir (temizlik ve chunking sonraki adimlarin isi).
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pymupdf

KOK = Path(__file__).resolve().parent.parent
PDF_KLASOR = KOK / "data" / "ham" / "financebench" / "pdfs"
CIKTI = KOK / "data" / "islenmis" / "sayfalar"
OZET = KOK / "sonuclar" / "parse_ozeti.json"

BOS_ESIK = 20  # bu kadar karakterden azi "bos sayfa" (taranmis gorsel olabilir)


def isle(pdf_yolu: str) -> dict:
    yol = Path(pdf_yolu)
    ad = yol.stem
    hedef = CIKTI / f"{ad}.jsonl"
    try:
        with pymupdf.open(yol) as belge, open(hedef, "w", encoding="utf-8") as f:
            sayfa_sayisi, bos, karakter = len(belge), 0, 0
            for idx, sayfa in enumerate(belge):
                metin = sayfa.get_text()
                if len(metin.strip()) < BOS_ESIK:
                    bos += 1
                karakter += len(metin)
                f.write(json.dumps({"doc": ad, "sayfa_idx": idx, "metin": metin}, ensure_ascii=False) + "\n")
        return {"doc": ad, "sayfa": sayfa_sayisi, "bos_sayfa": bos, "karakter": karakter, "hata": None}
    except Exception as e:  # tek bozuk PDF tum calismayi durdurmasin
        hedef.unlink(missing_ok=True)
        return {"doc": ad, "sayfa": 0, "bos_sayfa": 0, "karakter": 0, "hata": f"{type(e).__name__}: {e}"}


def main():
    CIKTI.mkdir(parents=True, exist_ok=True)
    pdfler = sorted(str(p) for p in PDF_KLASOR.glob("*.pdf"))
    t0 = time.time()
    with ProcessPoolExecutor() as havuz:
        sonuclar = list(havuz.map(isle, pdfler, chunksize=4))
    sure = time.time() - t0

    hatalar = [s for s in sonuclar if s["hata"]]
    toplam_sayfa = sum(s["sayfa"] for s in sonuclar)
    toplam_bos = sum(s["bos_sayfa"] for s in sonuclar)
    print(f"{len(sonuclar)} belge, {toplam_sayfa} sayfa, {sure:.0f} sn")
    print(f"bos sayfa (<{BOS_ESIK} karakter): {toplam_bos}  hatali belge: {len(hatalar)}")
    for h in hatalar:
        print("  HATA", h["doc"], h["hata"])

    OZET.write_text(json.dumps({"bos_esigi": BOS_ESIK, "pymupdf": pymupdf.VersionBind,
                                "belgeler": sonuclar}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
