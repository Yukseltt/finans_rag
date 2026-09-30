# FinanceBench ve FinQA verisini data/ham/ altina indirir, manifest uretir.
#
# Kullanim:
#     python src/veri_indir.py              # json dosyalari + tum PDF'ler
#     python src/veri_indir.py --pdf yok    # sadece json dosyalari (hizli)
#
# Veri repoya girmez (CC-BY-NC); repoda sadece bu betik ve manifest bulunur.
# Sadece standart kutuphane kullanir.
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "data" / "ham"
MANIFEST = KOK / "sonuclar" / "veri_manifest.json"

FB = "https://raw.githubusercontent.com/patronus-ai/financebench/main"
FQ = "https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset"

JSON_DOSYALARI = {
    HAM / "financebench" / "sorular.jsonl": f"{FB}/data/financebench_open_source.jsonl",
    HAM / "financebench" / "belgeler.jsonl": f"{FB}/data/financebench_document_information.jsonl",
    HAM / "finqa" / "train.json": f"{FQ}/train.json",
    HAM / "finqa" / "dev.json": f"{FQ}/dev.json",
    HAM / "finqa" / "test.json": f"{FQ}/test.json",
}


def indir(url: str, hedef: Path) -> bool:
    # Dosya yoksa indirir. Indirdiyse True, zaten varsa False doner.
    if hedef.exists() and hedef.stat().st_size > 0:
        return False
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_suffix(hedef.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as yanit, open(gecici, "wb") as f:
        while blok := yanit.read(1 << 20):
            f.write(blok)
    gecici.replace(hedef)  # yarim inmis dosya hedefte asla kalmaz
    return True


def sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        while blok := f.read(1 << 20):
            h.update(blok)
    return h.hexdigest()


def pdf_adlari() -> list[str]:
    # PDF listesi belgeler.jsonl'deki doc_name alanindan gelir.
    adlar = set()
    with open(HAM / "financebench" / "belgeler.jsonl", encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                adlar.add(json.loads(satir)["doc_name"])
    return sorted(adlar)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", choices=["hepsi", "yok"], default="hepsi")
    args = ap.parse_args()

    for hedef, url in JSON_DOSYALARI.items():
        durum = "indirildi" if indir(url, hedef) else "zaten var"
        print(f"{hedef.relative_to(KOK)}: {durum}")

    dosyalar = list(JSON_DOSYALARI)
    if args.pdf == "hepsi":
        adlar = pdf_adlari()
        print(f"{len(adlar)} PDF isleniyor")
        for i, ad in enumerate(adlar, 1):
            hedef = HAM / "financebench" / "pdfs" / f"{ad}.pdf"
            try:
                indir(f"{FB}/pdfs/{ad}.pdf", hedef)
            except Exception as e:  # tek PDF tum indirmeyi oldurmesin
                print(f"  HATA {ad}: {e}", file=sys.stderr)
                continue
            dosyalar.append(hedef)
            if i % 50 == 0:
                print(f"  {i}/{len(adlar)}")

    kayit = {
        "olusturma_tarihi": date.today().isoformat(),
        "kaynaklar": {"financebench": FB, "finqa": FQ},
        "dosyalar": {
            str(d.relative_to(HAM)).replace("\\", "/"): {
                "bayt": d.stat().st_size,
                "sha256": sha256(d),
            }
            for d in sorted(dosyalar) if d.exists()
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(kayit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"manifest: {MANIFEST.relative_to(KOK)} ({len(kayit['dosyalar'])} dosya)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
