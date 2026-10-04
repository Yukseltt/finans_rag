# Gemini okuyucu (Deney 5, adim 2): hazirlanmis istekleri Gemini API'ye gonderir, ham yanitlari onbellekler.
#
# Kullanim:
#   python src/okuyucu_gemini.py --model gemini-3.5-flash-lite --kosul k1_c200 --idler pilot
#       (varsayilan: KURU CALISMA; count_tokens ile gercek GIRIS tokenlarini sayar, maliyeti tahmin eder, CAGRI YAPMAZ)
#   python src/okuyucu_gemini.py --model gemini-3.5-flash-lite --kosul k1_c200 --idler pilot --onayla
#       (gercek cagrilar; yanitlar data/islenmis/cevaplar/ altina yazilir)
#   --idler: pilot | hepsi | virgullu soru id listesi
#
# Girdi:  data/islenmis/istekler/<kosul>.jsonl (baglam_hazirla.py), sonuclar/prompt_<surum>.json
# Cikti:  data/islenmis/cevaplar/<model>__<kosul>.jsonl   (soru basina ham yanit + token sayilari + maliyet)
#         data/islenmis/cevaplar/harcama.json             (toplam harcama; TAVAN burada izlenir)
#
# GUVENCELER:
#   - API anahtari yalnizca GEMINI_API_KEY ortam degiskeninden okunur; hicbir yere yazilmaz/yazdirilmaz.
#   - ONBELLEK: ayni (istek, model, ayarlar) ikinci kez GONDERILMEZ; yeniden calistirma ucretsizdir.
#   - HARCAMA TAVANI: toplam harcama TAVAN_TL / KUR_TL_USD dolari asamaz; her cagri oncesi, o cagrinin
#     EN KOTU durum maliyeti de eklenerek kontrol edilir; asilacaksa durur (Durdu hatasi).
#   - Prompt dondurma: istek dosyalarindaki prompt surumu ve sablon hash'i dogrulanmadan cagri yapilmaz.
#   - Hatali/yanitsiz cagri onbellege BASARI olarak yazilmaz (yeniden calistirmada tekrar denenir) ve
#     degerlendirmede YANLIS sayilir (Deney 5 on kaydi).
#
# AYARLAR (Deney 5 on kaydi + protokol notu): sicaklik 0, seed 0 (belirlilik icin eklendi), dusunme ve diger
# parametreler API varsayilani; max_output_tokens=8192 yalnizca MALIYET GUVENCESI (siradan cevap bunun cok altinda).
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import baglam_hazirla as bh

KOK = Path(__file__).resolve().parent.parent
ISTEKLER = KOK / "data" / "islenmis" / "istekler"
CEVAPLAR = KOK / "data" / "islenmis" / "cevaplar"

# USD / 1M token (giris, cikis). Kaynak: Gemini API fiyat sayfasi ozeti, 2026-10-01 (panelden dogrulanmali).
# gemini-3.8-flash fiyati 31.12.2026'ya kadar gecerli (sonra $1.50 / $7.50). Dusunme tokenlari CIKIS olarak faturalanir.
FIYAT = {"gemini-3.8-flash": (0.75, 3.75), "gemini-3.5-flash-lite": (0.30, 2.50)}
TAVAN_TL = 350.0  # 250'den yukseltildi (2026-10-02): gemini-3.8-flash dusunme maliyeti olculdu, KARAR_GUNLUGU.md
KUR_TL_USD = 55.0
MAKS_CIKTI = 8192
DENEME = 3
YENIDEN_DENENIR = (429, 500, 502, 503, 504)


class Durdu(Exception):
    pass


def maliyet_usd(model, prompt_tok, cikti_tok):
    fi, fo = FIYAT[model]
    return (prompt_tok * fi + cikti_tok * fo) / 1e6


def istek_hash(istek, model):
    ozet = {"sistem": istek["sistem"], "kullanici": istek["kullanici"], "model": model, "sicaklik": 0, "seed": 0,
            "maks_cikti": MAKS_CIKTI, "prompt_surum": istek["prompt_surum"]}
    return hashlib.sha256(json.dumps(ozet, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def promptu_dogrula(istekler):
    # Her istegin kendi prompt surumu icin: donmus sablon dosyasi var mi ve kodun o surumun sablonuyla ayni mi
    for surum in sorted({r["prompt_surum"] for r in istekler}):
        yol = KOK / "sonuclar" / f"prompt_{surum}.json"
        if not yol.exists():
            raise SystemExit(f"prompt {surum} dondurulmamis ({yol.name} yok); baglam_hazirla.py calistirilmali")
        if json.load(open(yol, encoding="utf-8"))["sha256"] != bh.sablon_ozeti(surum)["sha256"]:
            raise SystemExit(f"prompt sablonu {surum} donduruldugundan farkli; cagri yapilmaz")


class Harcama:
    def __init__(self, yol=None, tavan_usd=None):
        self.yol = yol or (CEVAPLAR / "harcama.json")
        self.tavan_usd = tavan_usd if tavan_usd is not None else TAVAN_TL / KUR_TL_USD
        self.veri = json.load(open(self.yol, encoding="utf-8")) if self.yol.exists() else {"toplam_usd": 0.0, "cagri": 0, "model": {}}

    @property
    def toplam(self):
        return self.veri["toplam_usd"]

    def kontrol(self, en_kotu_usd):
        if self.toplam + en_kotu_usd > self.tavan_usd:
            raise Durdu(f"harcama tavani asilacak: harcanan ${self.toplam:.4f} + en kotu ${en_kotu_usd:.4f} > "
                        f"tavan ${self.tavan_usd:.4f} ({TAVAN_TL:.0f} TL / {KUR_TL_USD:.0f})")

    def ekle(self, model, usd):
        self.veri["toplam_usd"] += usd
        self.veri["cagri"] += 1
        m = self.veri["model"].setdefault(model, {"usd": 0.0, "cagri": 0})
        m["usd"] += usd
        m["cagri"] += 1
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        self.yol.write_text(json.dumps(self.veri, indent=2), encoding="utf-8")


class Okuyucu:
    def __init__(self, istemci, model, cevap_klasoru=None, harcama=None, bekle=lambda s: time.sleep(s)):
        self.istemci, self.model = istemci, model
        self.klasor = cevap_klasoru or CEVAPLAR
        self.harcama = harcama or Harcama(self.klasor / "harcama.json")
        self.bekle = bekle

    def _yol(self, kosul):
        return self.klasor / f"{self.model}__{kosul}.jsonl"

    def onbellek(self, kosul):
        # (id, istek_hash) -> basarili kayit
        yol = self._yol(kosul)
        sonuc = {}
        if yol.exists():
            for satir in open(yol, encoding="utf-8"):
                if satir.strip():
                    k = json.loads(satir)
                    if k.get("hata") is None:
                        sonuc[(k["id"], k["istek_sha256"])] = k
        return sonuc

    def _cagir(self, istek):
        from google.genai import errors, types
        yapilandirma = types.GenerateContentConfig(system_instruction=istek["sistem"], temperature=0, seed=0,
                                                   max_output_tokens=MAKS_CIKTI)
        son_hata = None
        for deneme in range(DENEME):
            try:
                t0 = time.time()
                r = self.istemci.models.generate_content(model=self.model, contents=istek["kullanici"], config=yapilandirma)
                return r, time.time() - t0, None
            except errors.APIError as e:
                son_hata = f"APIError {getattr(e, 'code', '?')}: {str(e)[:200]}"
                if getattr(e, "code", None) not in YENIDEN_DENENIR:
                    break
            except Exception as e:  # ag kesintisi vb.
                son_hata = f"{type(e).__name__}: {str(e)[:200]}"
            if deneme < DENEME - 1:
                self.bekle(2 ** (deneme + 1))
        return None, 0.0, son_hata

    def calistir(self, istekler, kosul):
        onbellek = self.onbellek(kosul)
        self.klasor.mkdir(parents=True, exist_ok=True)
        istatistik = {"cagri": 0, "onbellekten": 0, "hata": 0, "usd": 0.0}
        for istek in istekler:
            h = istek_hash(istek, self.model)
            if (istek["id"], h) in onbellek:
                istatistik["onbellekten"] += 1
                continue
            # en kotu durum: girdi (karakter/3 token, ihtiyatli) + MAKS_CIKTI cikti tokeni
            fi, fo = FIYAT[self.model]
            self.harcama.kontrol(maliyet_usd(self.model, len(istek["kullanici"] + istek["sistem"]) / 3, MAKS_CIKTI))
            yanit, sure, hata = self._cagir(istek)
            kayit = {"id": istek["id"], "kosul": kosul, "model": self.model, "prompt_surum": istek["prompt_surum"],
                     "istek_sha256": h, "tarih": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "sure_sn": round(sure, 2), "yanit": None, "bitis_nedeni": None, "kullanim": None,
                     "maliyet_usd": 0.0, "hata": hata}
            if yanit is not None:
                kul = getattr(yanit, "usage_metadata", None)
                p = (getattr(kul, "prompt_token_count", 0) or 0) if kul else 0
                c = (getattr(kul, "candidates_token_count", 0) or 0) if kul else 0
                d = (getattr(kul, "thoughts_token_count", 0) or 0) if kul else 0
                try:
                    metin = yanit.text
                except Exception:
                    metin = None
                bitis = None
                if getattr(yanit, "candidates", None):
                    bitis = str(getattr(yanit.candidates[0], "finish_reason", None))
                kayit.update({"yanit": metin, "bitis_nedeni": bitis,
                              "kullanim": {"girdi": p, "cikti": c, "dusunme": d, "toplam": getattr(kul, "total_token_count", None)},
                              "maliyet_usd": maliyet_usd(self.model, p, c + d)})
                if not metin:
                    kayit["hata"] = f"bos yanit (bitis nedeni: {bitis})"
                self.harcama.ekle(self.model, kayit["maliyet_usd"])  # yanit alindiysa ucretlendirilir
            istatistik["cagri"] += 1
            istatistik["usd"] += kayit["maliyet_usd"]
            if kayit["hata"]:
                istatistik["hata"] += 1
            with open(self._yol(kosul), "a", encoding="utf-8") as f:
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        return istatistik


def istekleri_yukle(kosul, idler):
    tum = [json.loads(s) for s in open(ISTEKLER / f"{kosul}.jsonl", encoding="utf-8") if s.strip()]
    if idler == "hepsi":
        return tum
    if idler == "pilot":
        pilot = set(json.load(open(KOK / "sonuclar" / "pilot_idler.json", encoding="utf-8"))["idler"])
    else:
        pilot = set(idler.split(","))
    secilen = [r for r in tum if r["id"] in pilot]
    assert secilen, "secilen soru bulunamadi"
    return secilen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(FIYAT))
    ap.add_argument("--kosul", required=True, choices=["k0", "k1_c200", "k1_c300", "k1_r2", "k1_r2_v3", "k2"])
    ap.add_argument("--idler", default="pilot", help="pilot | hepsi | virgullu id listesi")
    ap.add_argument("--onayla", action="store_true", help="gercek cagrilari yap (yoksa kuru calisma)")
    ap.add_argument("--tahmini-cikti", type=int, default=800, help="kuru calismada cagri basina tahmini cikti+dusunme tokeni")
    args = ap.parse_args()

    istekler = istekleri_yukle(args.kosul, args.idler)
    promptu_dogrula(istekler)
    from google import genai
    istemci = genai.Client()  # GEMINI_API_KEY ortam degiskeninden
    okuyucu = Okuyucu(istemci, args.model)
    onbellek = okuyucu.onbellek(args.kosul)
    yeni = [r for r in istekler if (r["id"], istek_hash(r, args.model)) not in onbellek]
    print(f"{args.model} / {args.kosul}: {len(istekler)} istek, onbellekte {len(istekler) - len(yeni)}, gonderilecek {len(yeni)}")

    if not args.onayla:
        # KURU CALISMA: count_tokens ucretsizdir; gercek giris tokenlari sayilir
        giris = 0
        for r in yeni:
            giris += istemci.models.count_tokens(model=args.model, contents=r["sistem"] + "\n\n" + r["kullanici"]).total_tokens
        cikti = len(yeni) * args.tahmini_cikti
        usd = maliyet_usd(args.model, giris, cikti)
        print(f"KURU CALISMA (cagri yapilmadi): gercek giris {giris} token ({giris / max(len(yeni), 1):.0f}/cagri), "
              f"varsayilan cikti {cikti} token ({args.tahmini_cikti}/cagri, dusunme dahil)")
        print(f"tahmini maliyet: ${usd:.4f} = {usd * KUR_TL_USD:.2f} TL | harcanan: ${okuyucu.harcama.toplam:.4f} "
              f"({okuyucu.harcama.toplam * KUR_TL_USD:.2f} TL) | tavan: {TAVAN_TL:.0f} TL")
        return
    try:
        s = okuyucu.calistir(yeni, args.kosul)
    except Durdu as e:
        print("DURDU:", e)
        sys.exit(2)
    print(f"bitti: {s['cagri']} cagri, {s['hata']} hatali, bu calistirmada ${s['usd']:.4f} ({s['usd'] * KUR_TL_USD:.2f} TL); "
          f"toplam harcama ${okuyucu.harcama.toplam:.4f} ({okuyucu.harcama.toplam * KUR_TL_USD:.2f} TL / {TAVAN_TL:.0f} TL)")


if __name__ == "__main__":
    main()
