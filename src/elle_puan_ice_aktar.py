# Elle puanlari ice aktarir: sayfadan indirilen JSON'u (rastgele cevap kodlari) anahtarla soru/model/kosula cevirir.
#
# Kullanim: python src/elle_puan_ice_aktar.py <indirilen_elle_puanlar.json>            (Deney 5 turu)
#           python src/elle_puan_ice_aktar.py <indirilen_elle_puanlar.json> --tur d9   (Deney 8+9 turu)
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


def uyum(yeni, eski):
    # test-tekrar tutarliligi: ayni (id, model, kosul) icin iki turdaki puan; doner (ortak, ayni, kismen_farki, kesin_fark)
    e = {(r["id"], r["model"], r["kosul"]): r["puan"] for r in eski}
    ortak = [(r, e[(r["id"], r["model"], r["kosul"])]) for r in yeni if (r["id"], r["model"], r["kosul"]) in e]
    ayni = sum(1 for r, p in ortak if r["puan"] == p)
    kesin = sum(1 for r, p in ortak if {r["puan"], p} == {"dogru", "yanlis"})
    return len(ortak), ayni, len(ortak) - ayni - kesin, kesin


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != "d9"]
    d9 = "--tur" in sys.argv and sys.argv[sys.argv.index("--tur") + 1] == "d9"
    if len(args) != 1:
        raise SystemExit("kullanim: python src/elle_puan_ice_aktar.py <indirilen_elle_puanlar.json> [--tur d9]")
    yuklenen = json.load(open(args[0], encoding="utf-8"))
    anahtar = json.load(open(KOK / "data" / "islenmis" / "puanlama" / ("anahtar_d9.json" if d9 else "anahtar.json"), encoding="utf-8"))
    kayitlar = donustur(yuklenen["puanlar"], anahtar)
    cikti = {"puanlayan": "kullanici", "tarih": date.today().isoformat(), "kor": True, "n": len(kayitlar), "puanlar": kayitlar}
    hedef = "elle_puanlar_d9.json" if d9 else "elle_puanlar.json"
    (KOK / "sonuclar" / hedef).write_text(json.dumps(cikti, indent=2, ensure_ascii=False), encoding="utf-8")
    sayac = {}
    for r in kayitlar:
        sayac[r["puan"]] = sayac.get(r["puan"], 0) + 1
    print(f"{len(kayitlar)} puan ice aktarildi -> sonuclar/{hedef} | dagilim: {sayac}")
    if d9:
        eski = json.load(open(KOK / "sonuclar" / "elle_puanlar.json", encoding="utf-8"))["puanlar"]
        n, ayni, kismi, kesin = uyum(kayitlar, eski)
        print(f"TEST-TEKRAR (K1-c200, {n} ortak cevap): ayni puan {ayni}/{n} = {ayni / n:.3f} | kismen-farki {kismi} | "
              f"DOGRU<->YANLIS celiskisi {kesin}")


if __name__ == "__main__":
    main()
