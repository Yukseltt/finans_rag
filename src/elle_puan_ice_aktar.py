# Elle puanlari ice aktarir: sayfadan indirilen JSON'u (rastgele cevap kodlari) anahtarla soru/model/kosula cevirir.
#
# Kullanim: python src/elle_puan_ice_aktar.py <indirilen_elle_puanlar.json>
# Girdi:    puanlama sayfasindan indirilen JSON, data/islenmis/puanlama/anahtar.json
# Cikti:    sonuclar/elle_puanlar.json   [{id, model, kosul, puan}]  (icerik YOK; repoya girebilir)
#
# Tum 128 cevap puanlanmis olmali; eksik ya da gecersiz deger varsa DURUR (kismi ice aktarma yok).
# Puan degerleri: dogru | kismen | yanlis. Analizde: siki (kismen = yanlis) ve yumusak (kismen = dogru).
import json
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
GECERLI = {"dogru", "kismen", "yanlis"}


def donustur(puanlar, anahtar):
    eksik = sorted(set(anahtar) - set(puanlar))
    fazla = sorted(set(puanlar) - set(anahtar))
    gecersiz = sorted(t for t, v in puanlar.items() if v not in GECERLI)
    if eksik or fazla or gecersiz:
        raise SystemExit(f"ice aktarma durdu: eksik {len(eksik)}, taniyamadigim kod {len(fazla)}, gecersiz deger {len(gecersiz)}")
    return sorted(({"id": anahtar[t]["id"], "model": anahtar[t]["model"], "kosul": anahtar[t]["kosul"], "puan": v}
                   for t, v in puanlar.items()), key=lambda r: (r["id"], r["model"], r["kosul"]))


def main():
    if len(sys.argv) != 2:
        raise SystemExit("kullanim: python src/elle_puan_ice_aktar.py <indirilen_elle_puanlar.json>")
    yuklenen = json.load(open(sys.argv[1], encoding="utf-8"))
    anahtar = json.load(open(KOK / "data" / "islenmis" / "puanlama" / "anahtar.json", encoding="utf-8"))
    kayitlar = donustur(yuklenen["puanlar"], anahtar)
    cikti = {"puanlayan": "kullanici", "tarih": date.today().isoformat(), "kor": True, "n": len(kayitlar), "puanlar": kayitlar}
    (KOK / "sonuclar" / "elle_puanlar.json").write_text(json.dumps(cikti, indent=2, ensure_ascii=False), encoding="utf-8")
    sayac = {}
    for r in kayitlar:
        sayac[r["puan"]] = sayac.get(r["puan"], 0) + 1
    print(f"{len(kayitlar)} puan ice aktarildi -> sonuclar/elle_puanlar.json | dagilim: {sayac}")


if __name__ == "__main__":
    main()
