# Cevap dogrulugu icin katmanli, once deterministik metrik (Karar 2 revizesi).
#
# Gold cevap turu (gold'un biciminden belirlenir):
#   salt_sayi   : cevap tek bir sayi ($1577.00, 24.26, 1.9%)  -> sayisal eslesme
#   hukum       : "Yes"/"No" ile basliyor                      -> hukum (Yes/No) eslesmesi
#   anahtar_sayi: metin icinde sayi var                        -> anahtar sayilarin bulunma orani
#   serbest     : sayi yok                                     -> deterministik metrik yok (yargic gerekir)
#
# Sayisal eslesme IKI olcut verir (ikisi de raporlanir):
#   hassasiyet : tahmin, gold'un ondalik basamak sayisina YARIM-YUKARI yuvarlaninca gold'a esit
#   tolerans   : goreli sapma <= %1
# Birim: soru "in USD millions/billions/thousands" diyorsa beklenen birim odur; tahmindeki
# "million/billion/thousand" kelimeleri (ve $ ile birlikte m/bn/k) o birime cevrilir.
# Tahmin olcek kelimesi tasimiyorsa deger zaten beklenen birimde sayilir.
#
# Tahmin metninden "son cevap" cikarilir: "Final answer:" isaretinden sonrasi, yoksa tum metin.
# Salt sayida aday sayilar arasindan, gold'un BICIMINE en cok uyani secilir ($ var mi, % var mi,
# ondalikli mi; esitlikte ilki); yil gibi gorunen yalin tam sayilar ve form adlari (10-K, 8-K) aday degildir.
# Boylece "Based on the 10-K (page 59), the result is $1577.00" icin 1577.00 secilir.
#
# Ayristirma kurallari (gercekci model cevaplariyla test edilmistir, tests/test_cevap_metrik.py):
#   - harfe/rakama bitisik sayi sayi degildir: "FY2018", "Q2" icinde 2018/2 ayrismaz
#   - "0.96x" 0.96'dir (carpan soneki)
#   - eksi yalnizca bir kelimeye veya satir basina bitisik degilse isarettir:
#     " -14.76%" negatif; "2018-2019" ve satir basi madde isareti "\n-100%" degil
#   - parantez eksi anlamina gelmez: "($1.8 bn)" 1.8 milyardir (gold'larda muhasebe negatifi yok)
#   - sirket adi "3M": sayiya bitisik BUYUK harf M/K ($ olmadan) sayi sayilmaz; "$5M", "1.5m", "1.8 bn" olcektir
import re
from decimal import ROUND_HALF_UP, Decimal

SAYI = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<eksi>(?<![\w\n])[-−])?\s*(?P<dolar>\$)?\s*"
    r"(?P<sayi>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?P<yuzde>%)?\s*(?P<olcek>trillion|billion|million|thousand|bn|mm|m|k)?(?:x)?(?![A-Za-z0-9])", re.I)
OLCEK = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
TOLERANS = 0.01
YIL = range(1900, 2101)


def son_cevap(tahmin: str) -> str:
    parcalar = re.split(r"final answer\s*[:\-]", tahmin, flags=re.I)
    return parcalar[-1].strip() if len(parcalar) > 1 else tahmin.strip()


def sayilar(metin: str):
    # [(deger, ondalik_sayisi, yuzde_mi, olcek_carpani, dolar_mi)]
    sonuc = []
    for m in SAYI.finditer(metin):
        ham = m.group("sayi").replace(",", "")
        deger = -float(ham) if m.group("eksi") else float(ham)
        ondalik = len(ham.split(".")[1]) if "." in ham else 0
        ham_olcek = m.group("olcek") or ""
        if ham_olcek in ("M", "K") and not m.group("dolar"):
            continue  # "3M" gibi sirket adi: sayi degil ("$5M" ve "1.5m" olcektir)
        if re.match(r"-[KQkq]\b", metin[m.end():m.end() + 3]):
            continue  # "10-K", "8-K", "10-Q" form adi
        adi = ham_olcek.lower()
        sonuc.append((deger, ondalik, bool(m.group("yuzde")), OLCEK.get(adi, 1.0), bool(m.group("dolar"))))
    return sonuc


def yalin_yil(a) -> bool:
    # yil gibi gorunen yalin tam sayi (isaretsiz, yuzdesiz, olceksiz, 1900-2100)
    deger, ondalik, yuzde, olcek, _ = a
    return ondalik == 0 and not yuzde and olcek == 1.0 and deger > 0 and int(deger) in YIL


def yuvarla(x: float, n: int) -> Decimal:
    # yarim-yukari yuvarlama (Python'un yuvarlamasi cifte yuvarlar: round(0.125, 2) == 0.12)
    return Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP)


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
    if not yalin_yil(g):  # gold'un kendisi yil degilse, yil gibi gorunen sayilar aday olmaz
        adaylar = [a for a in adaylar if not yalin_yil(a)] or adaylar
    # gold'un bicimine EN COK uyan aday ($ var mi, % var mi, ondalikli mi: 0-3 puan); esitlikte ilk aday.
    # Model "$" ya da "%" yazmayabilir, bu yuzden tam uyum aranmaz.
    def puan(a):
        return (a[4] == g[4]) + (a[2] == g[2]) + ((a[1] > 0) == (g[1] > 0))
    t = max(adaylar, key=lambda a: (puan(a), -adaylar.index(a)))
    tahmin_deger = _normalize(t[0], t[3], beklenen)
    hassasiyet = yuvarla(tahmin_deger, gold_ondalik) == yuvarla(gold_deger, gold_ondalik)
    fark = abs(tahmin_deger - gold_deger)
    tolerans = fark <= TOLERANS * abs(gold_deger) if gold_deger else fark <= 0.005
    return {"hassasiyet": bool(hassasiyet), "tolerans": bool(tolerans)}


def hukum(tahmin: str, gold: str) -> dict:
    cevap = son_cevap(tahmin)
    beklenen = re.match(r"(yes|no)", gold.strip(), re.I).group(1).lower()
    m = re.match(r"\W*(yes|no)\b", cevap, re.I)
    if not m:
        # cevap Yes/No ile baslamiyorsa: ilk 12 kelimede noktalamayla biten yes/no
        # ("Based on the data, no, 3M is not ..."); "no longer", "no question" eslesmez
        ilk = " ".join(cevap.split()[:12])
        m = re.search(r"\b(yes|no)\b(?=\s*[,.;:!]|\s*$)", ilk, re.I)
    return {"dogru": bool(m and m.group(1).lower() == beklenen)}


def anahtar_sayilar(gold: str):
    # yillar ve 1-2 haneli yalin tam sayilar anahtar sayilmaz (gurultu); yuzdeli, ondalikli,
    # virgullu, olcekli veya >=3 haneli (yil olmayan) sayilar anahtardir.
    # Doner: [(olcekli_deger, ondalik, yuzde_mi, olcek)]
    anahtar = []
    for deger, ondalik, yuzde, olcek, _ in sayilar(gold):
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
        if any(yuvarla(v / olcek, ondalik) == yuvarla(deger / olcek, ondalik)
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
