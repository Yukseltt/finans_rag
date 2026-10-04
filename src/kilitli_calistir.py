# Kilitli test, ASAMA 2 (Karar 14): okuyucu ve yargic cagrilari. KURU CALISMA varsayilan; --onayla gercek cagri yapar.
#
# Kullanim:
#   python src/kilitli_calistir.py --okuyucu             kuru calisma (ucretsiz count_tokens + maliyet tahmini)
#   python src/kilitli_calistir.py --okuyucu --onayla    2 okuyucu x 3 kosul x 51 soru = 306 cagri
#   python src/kilitli_calistir.py --yargic --onayla     serbest/bos-anahtar sorulari yargicla puanla (okuyucu cagrilarindan SONRA)
# Girdi:  data/islenmis/kilitli/istekler/{k0,k1_r2_v3,k2}.jsonl (kilitli_hazirla.py --kilitli)
# Cikti:  data/islenmis/kilitli/cevaplar/<model>__<kosul>.jsonl, data/islenmis/kilitli/yargic/...
#
# GUVENCE: bu calistirmanin toplam harcamasi 100 TL'yi gecemez (okuyucu + yargic). Baslangic harcamasi ilk calistirmada
# data/islenmis/kilitli/baslangic_harcama.json dosyasina yazilir. Genel tavan (350 TL) ayrica gecerlidir.
import json
import sys
from pathlib import Path

import cevap_olc as co
import degerlendir as d
import okuyucu_gemini as ok
import yargic_gemini as yg

KOK = Path(__file__).resolve().parent.parent
KILITLI = KOK / "data" / "islenmis" / "kilitli"
CEVAP = KILITLI / "cevaplar"
KOSULLAR = ["k0", "k1_r2_v3", "k2"]
MODELLER = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
KOSU_TL = 100.0


def harcama():
    yol = KILITLI / "baslangic_harcama.json"
    genel = ok.Harcama()  # genel dosya (cevaplar/harcama.json)
    if not yol.exists():
        KILITLI.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps({"baslangic_usd": genel.toplam}), encoding="utf-8")
    baslangic = json.load(open(yol, encoding="utf-8"))["baslangic_usd"]
    genel.tavan_usd = min(genel.tavan_usd, baslangic + KOSU_TL / ok.KUR_TL_USD)
    return genel


def istekler(kosul):
    return [json.loads(s) for s in open(KILITLI / "istekler" / f"{kosul}.jsonl", encoding="utf-8") if s.strip()]


def okuyucu_calistir(onayla):
    from google import genai
    istemci = genai.Client()
    h = harcama()
    toplam_giris = 0
    for m in MODELLER:
        for k in KOSULLAR:
            ist = istekler(k)
            ok.promptu_dogrula(ist)
            okuyucu = ok.Okuyucu(istemci, m, cevap_klasoru=CEVAP, harcama=h)
            onbellek = okuyucu.onbellek(k)
            yeni = [r for r in ist if (r["id"], ok.istek_hash(r, m)) not in onbellek]
            if not onayla:
                giris = sum(istemci.models.count_tokens(model=m, contents=r["sistem"] + "\n\n" + r["kullanici"]).total_tokens for r in yeni)
                toplam_giris += giris
                print(f"{m} / {k}: {len(ist)} istek, gonderilecek {len(yeni)}, gercek girdi {giris} token")
                continue
            try:
                s = okuyucu.calistir(yeni, k)
            except ok.Durdu as e:
                print("DURDU:", e)
                sys.exit(2)
            print(f"{m} / {k}: {s['cagri']} cagri, {s['hata']} hatali, ${s['usd']:.4f}; toplam {h.toplam * ok.KUR_TL_USD:.2f} TL")
    if not onayla:
        print(f"KURU CALISMA: toplam girdi {toplam_giris} token; harcanan {h.toplam * ok.KUR_TL_USD:.2f} TL; bu calistirma tavani {h.tavan_usd * ok.KUR_TL_USD:.2f} TL")


def yargic_ogeleri():
    # Otomatik puanlanamayan cevaplar: serbest gold + anahtar_sayi'si bos gold
    sorular = d.yukle_sorular(kilitli=True)
    gold = co.goldleri_yukle(sorular)
    soru = {s["id"]: s for s in sorular}
    import cevap_metrik as c
    ogeler = []
    for m in MODELLER:
        for k in KOSULLAR:
            for satir in open(CEVAP / f"{m}__{k}.jsonl", encoding="utf-8"):
                x = json.loads(satir)
                if x["hata"] is not None:
                    continue
                v, _ = co.puanla(x["yanit"], gold[x["id"]], soru[x["id"]]["soru"])
                if v is not None:
                    continue
                govde, _ = c.kaynak_ayir(x["yanit"])
                ogeler.append({"anahtar": f"{m}|{k}|{x['id']}", "id": x["id"], "model": m, "kosul": k, "tur": "kilitli",
                               "soru": soru[x["id"]]["soru"], "gold": gold[x["id"]], "final": c.son_cevap(x["yanit"]) or govde.strip(),
                               "govde": govde.strip(), "insan": None})
    return ogeler


def yargic_calistir(onayla):
    from google import genai
    ogeler = yargic_ogeleri()
    print(f"yargic ogesi: {len(ogeler)}")
    if not onayla:
        return
    yarg = yg.Yargic(genel_istemci(genai), "gemini-3.7-flash", None, KILITLI / "yargic", harcama())
    try:
        s = yarg.calistir(ogeler)
    except ok.Durdu as e:
        print("DURDU:", e)
        sys.exit(2)
    print(f"yargic: {s['cagri']} cagri, {s['hata']} hatali, ${s['usd']:.4f}; toplam {yarg.harcama.toplam * ok.KUR_TL_USD:.2f} TL")


def genel_istemci(genai):
    return genai.Client()


def main():
    onayla = "--onayla" in sys.argv
    if "--okuyucu" in sys.argv:
        return okuyucu_calistir(onayla)
    if "--yargic" in sys.argv:
        return yargic_calistir(onayla)
    raise SystemExit("kullanim: python src/kilitli_calistir.py --okuyucu|--yargic [--onayla]")


if __name__ == "__main__":
    main()
