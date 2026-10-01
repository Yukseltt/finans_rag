# Cevap dogrulugu icin katmanli, once deterministik metrik (Karar 2 revizesi).
#
# Gold cevap turu (gold'un biciminden belirlenir):
#   salt_sayi   : cevap tek bir sayi ($1577.00, 24.26, 1.9%)  -> sayisal eslesme
#   hukum       : "Yes"/"No" ile basliyor                      -> hukum (Yes/No) eslesmesi
#   anahtar_sayi: metin icinde sayi var                        -> anahtar sayilarin bulunma orani
#   serbest     : sayi yok                                     -> deterministik metrik yok (yargic gerekir)
#
# Sayisal eslesme IKI olcut verir (ikisi de raporlanir):
#   hassasiyet : tahmin, gold'un ondalik basamak sayisina yuvarlaninca gold'a esit
#   tolerans   : goreli sapma <= %1
# Birim: soru "in USD millions/billions/thousands" diyorsa beklenen birim odur; tahmindeki
# "million/billion/thousand/m/bn/k" kelimeleri o birime cevrilir. Sorudaki birim yoksa ham deger.
#
# Tahmin metninden "son cevap" cikarilir: "Final answer:" isaretinden sonrasi, yoksa tum metin.
# Salt sayida ve hukumde bu parcadaki ILK sayi / ILK kelime kullanilir.
import re

SAYI = re.compile(
    r"(?P<eksi>[-−(])?\s*(?P<dolar>\$)?\s*(?P<sayi>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<yuzde>%)?"
    r"\s*(?P<olcek>trillion|billion|million|thousand|bn|mm|m|k)?\b", re.I)
OLCEK = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
TOLERANS = 0.01
YIL = range(1900, 2101)


def son_cevap(tahmin: str) -> str:
    parcalar = re.split(r"final answer\s*[:\-]", tahmin, flags=re.I)
    return parcalar[-1].strip() if len(parcalar) > 1 else tahmin.strip()


def sayilar(metin: str):
    # [(deger, ondalik_sayisi, yuzde_mi, olcek_carpani)]
    sonuc = []
    for m in SAYI.finditer(metin):
        ham = m.group("sayi").replace(",", "")
        deger = float(ham)
        if m.group("eksi") and m.group("eksi") != "(":
            deger = -deger
        elif m.group("eksi") == "(":
            deger = -deger  # (123) muhasebe negatifi
        ondalik = len(ham.split(".")[1]) if "." in ham else 0
        adi = (m.group("olcek") or "").lower()
        # kisa kisaltmalar (m, k, mm, bn) yalnizca $ ile birlikte olcek sayilir: "3M" sirket adi, "$3m" 3 milyon dolar
        if adi in ("m", "k", "mm", "bn") and not m.group("dolar"):
            adi = ""
        olcek = OLCEK.get(adi, 1.0)
        sonuc.append((deger, ondalik, bool(m.group("yuzde")), olcek))
    return sonuc


def beklenen_birim(soru: str):
    m = re.search(r"\bin\s+(?:usd\s+|u\.s\.\s+dollars\s+)?(millions|billions|thousands)\b", soru, re.I)
    return {"millions": 1e6, "billions": 1e9, "thousands": 1e3}[m.group(1).lower()] if m else None


def tur(gold: str) -> str:
    g = gold.strip()
    if re.fullmatch(r"\(?[-−]?\$?\s*[\d,]+(?:\.\d+)?\s*%?\)?", g):
        return "salt_sayi"
    if re.match(r"(yes|no)\b", g, re.I):
        return "hukum"
    if re.search(r"\d", g):
        return "anahtar_sayi"
    return "serbest"


def _normalize(deger, olcek, beklenen):
    # Tahmin olcek kelimesi tasiyorsa (million/billion...) beklenen birime cevrilir; tasimiyorsa
    # deger zaten beklenen birimde varsayilir (soru "in USD millions" diyor ve model sade sayi yazdi).
    if beklenen and olcek != 1.0:
        return deger * olcek / beklenen
    return deger


def salt_sayi(tahmin: str, gold: str, soru: str) -> dict:
    g = sayilar(gold)[0]
    gold_deger, gold_ondalik = g[0], g[1]
    beklenen = beklenen_birim(soru)
    adaylar = sayilar(son_cevap(tahmin))
    if not adaylar:
        return {"hassasiyet": False, "tolerans": False}
    t = adaylar[0]
    tahmin_deger = _normalize(t[0], t[3], beklenen)
    hassasiyet = round(tahmin_deger, gold_ondalik) == round(gold_deger, gold_ondalik)
    fark = abs(tahmin_deger - gold_deger)
    tolerans = fark <= TOLERANS * abs(gold_deger) if gold_deger else fark <= 0.005
    return {"hassasiyet": bool(hassasiyet), "tolerans": bool(tolerans)}


def hukum(tahmin: str, gold: str) -> dict:
    m = re.match(r"\W*(yes|no)\b", son_cevap(tahmin), re.I)
    beklenen = re.match(r"(yes|no)", gold.strip(), re.I).group(1).lower()
    return {"dogru": bool(m and m.group(1).lower() == beklenen)}


def anahtar_sayilar(gold: str):
    # yillar ve 1-2 haneli yalin tam sayilar anahtar sayilmaz (gurultu); yuzdeli, ondalikli,
    # virgullu, olcekli veya >=3 haneli (yil olmayan) sayilar anahtardir.
    # Doner: [(olcekli_deger, ondalik, yuzde_mi, olcek)]
    anahtar = []
    for deger, ondalik, yuzde, olcek in sayilar(gold):
        yalin_tam = ondalik == 0 and not yuzde and olcek == 1.0
        if yalin_tam and (abs(deger) < 100 or int(abs(deger)) in YIL):
            continue
        anahtar.append((deger * olcek, ondalik, yuzde, olcek))
    return anahtar


def anahtar_sayi(tahmin: str, gold: str) -> dict:
    anahtar = anahtar_sayilar(gold)
    if not anahtar:
        return {"oran": None, "hepsi": None, "n": 0}
    bulunan = [b[0] * b[3] for b in sayilar(tahmin)]
    bulundu = 0
    for deger, ondalik, _, olcek in anahtar:
        # gold'un hassasiyetinde (kendi biriminde yuvarlanmis) esitlik VEYA goreli %1 tolerans
        if any(round(v / olcek, ondalik) == round(deger / olcek, ondalik)
               or (abs(v - deger) <= TOLERANS * abs(deger) if deger else False) for v in bulunan):
            bulundu += 1
    return {"oran": bulundu / len(anahtar), "hepsi": bulundu == len(anahtar), "n": len(anahtar)}


def skorla(tahmin: str, gold: str, soru: str) -> dict:
    t = tur(gold)
    if t == "salt_sayi":
        return {"tur": t, **salt_sayi(tahmin, gold, soru)}
    if t == "hukum":
        return {"tur": t, **hukum(tahmin, gold)}
    if t == "anahtar_sayi":
        return {"tur": t, **anahtar_sayi(tahmin, gold)}
    return {"tur": t}
