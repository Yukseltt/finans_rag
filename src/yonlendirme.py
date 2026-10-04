# Belge yonlendirme (Deney 7): soru metninden SIRKET ve MALI YIL cikarir, arama uzayini o belgelere daraltir.
#
# Kurallar KARAR_GUNLUGU.md "Deney 7" on kaydindaki tanimla birebir aynidir; kural disi ekleme yoktur.
#
# Sirket bulma:
#   - belgeler.jsonl'deki sirket adlari otomatik normalize edilir: kucuk harf, noktalama/kesme isareti/&
#     bosluk olur, "corporation/inc/company/co/corp" ekleri atilir; ad ve SONDAKI "s" atilmis varyanti.
#   - soru ayni bicimde normalize edilir ve KELIME SINIRLI eslesir: ad token dizisi soruda bitisik gecmeli;
#     >= 6 karakterli adlar bitisik yazilmis halle de eslesir ("Coca Cola" ~ "cocacola"); kisa adlar yalniz token.
#   - Elle alias YALNIZCA: jnj, j&j -> Johnson & Johnson; amex -> American Express.
#   - sirket bulunamazsa yonlendirme yoktur (None).
# Yil bulma: FY2018 / FY 2018 / FY18 / fiscal year 2018 / Q2 2023 / Q22023 / bagimsiz 4 haneli 2010-2029.
# Varyantlar: R1 = sirketin tum belgeleri; R2 = sirketin soruda gecen yillarin y ve y+1 donemli belgeleri
#             (yil yoksa ya da filtre bos kalirsa R1'e duser).
import json
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
BELGELER = KOK / "data" / "ham" / "financebench" / "belgeler.jsonl"
EK_KELIMELER = {"corporation", "inc", "company", "co", "corp"}
ALIAS = {"jnj": "Johnson & Johnson", "j j": "Johnson & Johnson", "amex": "American Express"}


def norm(metin: str):
    return re.sub(r"[^a-z0-9]+", " ", metin.lower()).split()


def _varyantlar(ad_tokenlari):
    v = [list(ad_tokenlari)]
    son = ad_tokenlari[-1]
    if len(son) > 3 and son.endswith("s"):
        v.append(list(ad_tokenlari[:-1]) + [son[:-1]])
    return v


def belgeleri_yukle():
    # [(doc_name, sirket, mali_yil)]
    sonuc = []
    with open(BELGELER, encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                b = json.loads(satir)
                sonuc.append((b["doc_name"], b["company"], int(b["doc_period"])))
    return sonuc


def sirket_tablosu(belgeler):
    # sirket -> (token varyantlari, bitisik yazim)
    tablo = {}
    for _, sirket, _ in belgeler:
        t = [x for x in norm(sirket) if x not in EK_KELIMELER]
        tablo[sirket] = (_varyantlar(t), "".join(t))
    return tablo


def sirket_bul(soru, tablo):
    q = norm(soru)
    bitisik = "".join(q)
    bulunan = []
    for sirket, (varyantlar, birlesik) in tablo.items():
        eslesti = any(_dizi_var(q, v) for v in varyantlar)
        if not eslesti and len(birlesik) >= 6 and birlesik in bitisik:
            eslesti = True
        if eslesti:
            bulunan.append(sirket)
    for alias, hedef in ALIAS.items():
        if hedef in tablo and hedef not in bulunan and _dizi_var(q, alias.split()):
            bulunan.append(hedef)
    return bulunan


def _dizi_var(token_listesi, dizi):
    n = len(dizi)
    return any(token_listesi[i:i + n] == dizi for i in range(len(token_listesi) - n + 1))


def yil_bul(soru):
    t = soru.lower()
    yillar = set()
    for m in re.finditer(r"\bfy\s*'?\s*(\d{4}|\d{2})\b", t):
        y = int(m.group(1))
        yillar.add(y if y > 99 else 2000 + y)
    for m in re.finditer(r"fiscal\s+year\s+(20[12]\d)", t):
        yillar.add(int(m.group(1)))
    for m in re.finditer(r"\bq[1-4]\s*(?:of\s*)?(20[12]\d)", t):
        yillar.add(int(m.group(1)))
    for m in re.finditer(r"(?<![\d,.$])\b(20[12]\d)\b(?![,.]?\d)", t):
        yillar.add(int(m.group(1)))
    return sorted(y for y in yillar if 2010 <= y <= 2029)


def belgeleri_sec(soru, belgeler, tablo, varyant="R2"):
    # doner: (aday_doc_listesi ya da None, tani sozlugu)
    sirketler = sirket_bul(soru, tablo)
    yillar = yil_bul(soru)
    tani = {"sirketler": sirketler, "yillar": yillar, "varyant_kullanilan": None}
    if not sirketler:
        return None, tani
    r1 = [d for d, s, _ in belgeler if s in sirketler]
    tani["varyant_kullanilan"] = "R1"
    if varyant == "R1" or not yillar:
        return r1, tani
    pencere = set(yillar) | {y + 1 for y in yillar}
    r2 = [d for d, s, y in belgeler if s in sirketler and y in pencere]
    if r2:
        tani["varyant_kullanilan"] = "R2"
        return r2, tani
    return r1, tani  # filtre bos kaldi: R1'e dus
