# Yargic model (Karar 10 degisikligi): 16 elle-puanlanan soru icin cevaplari puanlar; kullanicinin ilk tur
# puanlariyla KALIBRE edilir.
#
# Kullanim:
#   python src/yargic_gemini.py                                 kuru calisma: ucretsiz token sayimi + maliyet tablosu
#   python src/yargic_gemini.py --model M --ornek 8 --onayla    8 oge (gercek cagri; maliyeti OLCMEK icin)
#   python src/yargic_gemini.py --model M --hepsi --onayla      192 oge (kalibrasyon 128 + yeni 64)
#   --dusunme minimal|low|medium|high   dusunme seviyesi (verilmezse API varsayilani)
# Girdi:  gelistirme gold cevaplari, data/islenmis/cevaplar/*.jsonl, sonuclar/elle_puanlar.json (kullanici, tur 1)
# Cikti:  data/islenmis/cevaplar/yargic/<model>__<dusunme>.jsonl (ham yanit, puan, token, maliyet)
#
# Ogeler (192): kalibrasyon 128 (K0, K1-c200, K1-c300, K2 x 2 okuyucu x 16 soru; kullanicinin puani VAR) +
# yeni 64 (K1-R2 v2/v3 x 2 okuyucu x 16 soru). Yargic okuyucu OLMAYAN bir modeldir, model/kosul bilgisini GORMEZ.
# GUVENCELER okuyucu betigindeki gibi: onbellek, ortak harcama tavani (okuyucu_gemini.Harcama), sinirli yeniden deneme.
import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d
import okuyucu_gemini as ok
import puanlama_sayfasi as ps

KOK = Path(__file__).resolve().parent.parent
YARGIC = KOK / "data" / "islenmis" / "cevaplar" / "yargic"

SISTEM = "You are a strict and fair grader. You compare a model answer with a gold answer."
KULLANICI = """Question: {SORU}

Gold answer: {GOLD}

Model answer (final answer): {FINAL}

Model reasoning (for context only): {GOVDE}

Grade the model answer against the gold answer. Use the gold answer as the standard.
- correct: the answer gives the main information of the gold answer and does not contradict it. Extra correct detail, different wording, spelling or format differences are fine.
- partial: only part of the main information is correct or complete (for example 2 of 3 items), or the direction is right but the answer is vague.
- wrong: the main information is wrong, it contradicts the gold answer, or the model says it cannot find the answer.
Reply with exactly one line: Grade: correct, Grade: partial, or Grade: wrong"""

# USD / 1M token (giris, cikis); kaynak: fiyat sayfasi ozeti 2026-10-01 (panelden dogrulanmali)
FIYAT = {"gemini-3.7-flash": (0.75, 3.75), "gemini-3.6-flash": (0.75, 3.75), "gemini-3.5-flash": (1.50, 9.00),
         "gemini-3.1-pro-preview": (2.00, 12.00)}
ETIKET = {"correct": "dogru", "partial": "kismen", "wrong": "yanlis"}
MAKS_CIKTI = 4096  # maliyet guvencesi (yargic cevabi tek satirdir; dusunmeyi sinirlar)


def prompt(oge):
    return KULLANICI.replace("{SORU}", oge["soru"]).replace("{GOLD}", oge["gold"]) \
        .replace("{FINAL}", oge["final"]).replace("{GOVDE}", oge["govde"] or "(none)")


def etiket_oku(metin):
    # "Grade: correct|partial|wrong" -> dogru|kismen|yanlis; ayrisamazsa None
    m = re.search(r"grade\s*:\s*\**\s*(correct|partial|wrong)", (metin or "").replace("*", ""), re.I)
    return ETIKET[m.group(1).lower()] if m else None


def maliyet(model, girdi, cikti):
    fi, fo = FIYAT[model]
    return (girdi * fi + cikti * fo) / 1e6


def oge_kumesi():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    gold = co.goldleri_yukle(sorular)
    soru = {s["id"]: s for s in sorular}
    ids = ps.elle_sorular(sorular, gold)
    insan = {(r["model"], r["kosul"], r["id"]): r["puan"]
             for r in json.load(open(KOK / "sonuclar" / "elle_puanlar.json", encoding="utf-8"))["puanlar"]}
    yanit = {(m, k): ps.govdeler(m, k) for m in co.MODELLER for k in ("k0", "k1_c200", "k1_c300", "k1_r2", "k1_r2_v3", "k2")}
    ogeler = []
    for tur, kosullar in (("kalibrasyon", ("k0", "k1_c200", "k1_c300", "k2")), ("yeni", ("k1_r2", "k1_r2_v3"))):
        for m in co.MODELLER:
            for k in kosullar:
                for i in ids:
                    tam = yanit[(m, k)].get(i)
                    if tam is None:
                        continue
                    govde, _ = c.kaynak_ayir(tam)
                    ogeler.append({"anahtar": f"{m}|{k}|{i}", "id": i, "model": m, "kosul": k, "tur": tur,
                                   "soru": soru[i]["soru"], "gold": gold[i], "final": c.son_cevap(tam) or govde.strip(),
                                   "govde": govde.strip(), "insan": insan.get((m, k, i))})
    return ogeler


def ornek_sec(ogeler, n=8):
    # Deterministik, etiket dengeli ornek (kalibrasyondan): 4 dogru, 3 yanlis, kalan kismen; sira sha256(anahtar)
    kota = {"dogru": n // 2, "yanlis": n * 3 // 8, "kismen": n - n // 2 - n * 3 // 8}
    sirali = sorted((o for o in ogeler if o["tur"] == "kalibrasyon"), key=lambda o: hashlib.sha256(o["anahtar"].encode()).hexdigest())
    secilen = []
    for o in sirali:
        if kota.get(o["insan"], 0) > 0:
            kota[o["insan"]] -= 1
            secilen.append(o)
    return secilen


def istek_hash(oge, model, dusunme):
    return hashlib.sha256(json.dumps({"s": SISTEM, "u": prompt(oge), "m": model, "d": dusunme, "maks": MAKS_CIKTI},
                                     sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class Yargic:
    def __init__(self, istemci, model, dusunme=None, klasor=None, harcama=None, bekle=lambda s: time.sleep(s)):
        self.istemci, self.model, self.dusunme = istemci, model, dusunme
        self.klasor = klasor or YARGIC
        self.harcama = harcama or ok.Harcama()
        self.bekle = bekle

    def yol(self):
        return self.klasor / f"{self.model}__{self.dusunme or 'varsayilan'}.jsonl"

    def onbellek(self):
        sonuc = {}
        if self.yol().exists():
            for satir in open(self.yol(), encoding="utf-8"):
                if satir.strip():
                    k = json.loads(satir)
                    if k.get("hata") is None:
                        sonuc[(k["anahtar"], k["istek_sha256"])] = k
        return sonuc

    def _cagir(self, oge):
        from google.genai import errors, types
        ayar = {"system_instruction": SISTEM, "temperature": 0, "seed": 0, "max_output_tokens": MAKS_CIKTI}
        if self.dusunme:
            ayar["thinking_config"] = types.ThinkingConfig(thinking_level=self.dusunme.upper())
        yapilandirma = types.GenerateContentConfig(**ayar)
        son = None
        for deneme in range(ok.DENEME):
            try:
                t0 = time.time()
                return self.istemci.models.generate_content(model=self.model, contents=prompt(oge), config=yapilandirma), time.time() - t0, None
            except errors.APIError as e:
                son = f"APIError {getattr(e, 'code', '?')}: {str(e)[:200]}"
                if getattr(e, "code", None) not in ok.YENIDEN_DENENIR:
                    break
            except Exception as e:
                son = f"{type(e).__name__}: {str(e)[:200]}"
            if deneme < ok.DENEME - 1:
                self.bekle(2 ** (deneme + 1))
        return None, 0.0, son

    def calistir(self, ogeler):
        onbellek = self.onbellek()
        self.klasor.mkdir(parents=True, exist_ok=True)
        ist = {"cagri": 0, "onbellekten": 0, "hata": 0, "usd": 0.0}
        for oge in ogeler:
            h = istek_hash(oge, self.model, self.dusunme)
            if (oge["anahtar"], h) in onbellek:
                ist["onbellekten"] += 1
                continue
            fi, fo = FIYAT[self.model]
            self.harcama.kontrol(maliyet(self.model, len(prompt(oge)) / 3, MAKS_CIKTI))
            yanit, sure, hata = self._cagir(oge)
            kayit = {"anahtar": oge["anahtar"], "id": oge["id"], "model": self.model, "dusunme_ayari": self.dusunme,
                     "istek_sha256": h, "tarih": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sure_sn": round(sure, 2),
                     "yanit": None, "puan": None, "kullanim": None, "maliyet_usd": 0.0, "hata": hata}
            if yanit is not None:
                kul = getattr(yanit, "usage_metadata", None)
                p = (getattr(kul, "prompt_token_count", 0) or 0) if kul else 0
                cik = (getattr(kul, "candidates_token_count", 0) or 0) if kul else 0
                dus = (getattr(kul, "thoughts_token_count", 0) or 0) if kul else 0
                try:
                    metin = yanit.text
                except Exception:
                    metin = None
                puan = etiket_oku(metin)
                kayit.update({"yanit": metin, "puan": puan, "kullanim": {"girdi": p, "cikti": cik, "dusunme": dus},
                              "maliyet_usd": maliyet(self.model, p, cik + dus)})
                if puan is None:
                    kayit["hata"] = f"puan ayrisamadi: {(metin or '')[:80]!r}"
                self.harcama.ekle(self.model, kayit["maliyet_usd"])
            ist["cagri"] += 1
            ist["usd"] += kayit["maliyet_usd"]
            ist["hata"] += bool(kayit["hata"])
            with open(self.yol(), "a", encoding="utf-8") as f:
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        return ist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.7-flash", choices=list(FIYAT))
    ap.add_argument("--ornek", type=int, default=0, help="etiket dengeli N ogelik ornek")
    ap.add_argument("--hepsi", action="store_true")
    ap.add_argument("--dusunme", choices=["minimal", "low", "medium", "high"], default=None)
    ap.add_argument("--onayla", action="store_true", help="gercek cagrilari yap (yoksa kuru calisma)")
    args = ap.parse_args()
    ogeler = oge_kumesi()
    kal = [o for o in ogeler if o["tur"] == "kalibrasyon"]
    assert all(o["insan"] for o in kal), "kalibrasyon ogelerinin hepsinde insan puani olmali"
    secim = ornek_sec(ogeler, args.ornek) if args.ornek else (ogeler if args.hepsi else None)
    from google import genai
    istemci = genai.Client()  # GEMINI_API_KEY ortam degiskeninden
    if secim is None or not args.onayla:
        girdi = [istemci.models.count_tokens(model=args.model, contents=SISTEM + "\n\n" + prompt(o)).total_tokens for o in ogeler]
        print(f"yargic ogesi: {len(ogeler)} (kalibrasyon {len(kal)}, yeni {len(ogeler) - len(kal)}); GERCEK girdi tokeni toplam {sum(girdi)} "
              f"(cagri basina medyan {statistics.median(girdi):.0f})")
        for mod, (fi, fo) in FIYAT.items():
            print(f"  {mod:24s} " + " | ".join(f"cikti {x}/cagri: {(sum(girdi) * fi + len(ogeler) * x * fo) / 1e6 * 55:5.1f} TL" for x in (150, 400, 800)))
        return
    yarg = Yargic(istemci, args.model, args.dusunme)
    try:
        s = yarg.calistir(secim)
    except ok.Durdu as e:
        print("DURDU:", e)
        sys.exit(2)
    print(f"bitti: {s['cagri']} cagri (onbellekten {s['onbellekten']}), {s['hata']} hatali, bu calistirmada ${s['usd']:.4f} "
          f"({s['usd'] * ok.KUR_TL_USD:.2f} TL); toplam harcama ${yarg.harcama.toplam:.4f} ({yarg.harcama.toplam * ok.KUR_TL_USD:.2f} TL / {ok.TAVAN_TL:.0f} TL)")


if __name__ == "__main__":
    main()
