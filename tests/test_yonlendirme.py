# yonlendirme.py'yi ON KAYITTAKI TANIMA gore sinar (elle yazilmis ornekler; gelistirme sonucuna bakilarak ayarlanmadi):
#   sirket bulma (adlar, kesme isareti, bitisik yazim, alias, yanlis eslesme korumasi), yil bulma, R1/R2 secimi.
#
# Kullanim: python tests/test_yonlendirme.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import yonlendirme as y  # noqa: E402


def main():
    belgeler = y.belgeleri_yukle()
    tablo = y.sirket_tablosu(belgeler)
    assert len(tablo) == 40

    # --- sirket bulma
    sb = lambda q: y.sirket_bul(q, tablo)
    assert sb("What is the FY2018 capital expenditure amount for 3M?") == ["3M"]
    assert sb("What drove gross margin change as of FY2022 for JnJ?") == ["Johnson & Johnson"]             # alias
    assert sb("Which segment of J&J was discontinued?") == ["Johnson & Johnson"]                          # alias
    assert sb("What is Amex's dividend?") == ["American Express"]                                          # alias
    assert sb("What is Johnson & Johnson's FY2022 revenue?") == ["Johnson & Johnson"]                     # otomatik
    assert sb("What is Coca Cola's FY2022 dividend payout ratio?") == ["Coca-Cola"]                        # bitisik yazim
    assert sb("Is Coca-Cola capital intensive?") == ["Coca-Cola"]
    assert sb("What did McDonald's report?") == ["McDonalds"]                                              # kesme isareti + sondaki s
    assert sb("What was AMCOR's Adjusted EBITDA?") == ["Amcor"]                                            # sahiplik eki
    assert sb("Did PG&E record a wildfire liability?") == ["PG&E Corporation"]                             # & ve Corporation eki
    assert sb("What is Activision Blizzard's revenue?") == ["Activision Blizzard"]
    assert sb("Compare 3M and Intel margins") == ["3M", "Intel"] or set(sb("Compare 3M and Intel margins")) == {"3M", "Intel"}
    # sirket yoksa yonlendirme yok
    assert sb("Which geographic region had the biggest revenue drop?") == []
    # yanlis eslesme korumasi: kisa adlar yalniz TOKEN olarak eslesir
    assert sb("What is the average demand for the product?") == []                                         # 'amd' kelime icinde degil
    assert sb("The company has a strong balance sheet") == []
    # on kayitta OLMAYAN ek kural yok: sadece 'MGM' yazilirsa 'MGM Resorts' bulunmaz (bilinen sinir)
    assert sb("What was MGM's interest coverage ratio?") == []

    # --- yil bulma
    yb = y.yil_bul
    assert yb("FY2018 capex") == [2018] and yb("fy 2019 revenue") == [2019] and yb("In FY22, AMD") == [2022]
    assert yb("as of fiscal year 2021") == [2021]
    assert yb("Q2 2023 revenue") == [2023] and yb("Q22023 year over year") == [2023] and yb("Q2 of FY2023 close") == [2023]
    assert yb("FY2017 - FY2019 3 year average") == [2017, 2019]
    assert yb("from 2015 to 2017") == [2015, 2017]
    assert yb("revenue was $2,018 million") == []                                                          # para tutari yil degil
    assert yb("Form 10-K and 8-K") == [] and yb("What is the quick ratio?") == []

    # --- R1 / R2
    docs, tani = y.belgeleri_sec("What is the FY2018 capex for 3M?", belgeler, tablo, "R1")
    assert docs and all(d.startswith("3M_") for d in docs) and tani["varyant_kullanilan"] == "R1"
    r1_say = len(docs)
    docs2, tani2 = y.belgeleri_sec("What is the FY2018 capex for 3M?", belgeler, tablo, "R2")
    donemler = {y_ for d, s, y_ in belgeler if d in docs2}
    assert donemler <= {2018, 2019} and 2018 in donemler and len(docs2) < r1_say and tani2["varyant_kullanilan"] == "R2"
    # yil yoksa R2 -> R1
    d3, t3 = y.belgeleri_sec("What is the capex for 3M?", belgeler, tablo, "R2")
    assert len(d3) == r1_say and t3["varyant_kullanilan"] == "R1"
    # filtre bos kalirsa (korpusta olmayan yil) R1'e duser
    d4, t4 = y.belgeleri_sec("What is the FY2012 capex for 3M?", belgeler, tablo, "R2")
    assert len(d4) == r1_say and t4["varyant_kullanilan"] == "R1"
    # sirket yoksa None
    d5, t5 = y.belgeleri_sec("Which segment grew the most in FY2022?", belgeler, tablo, "R2")
    assert d5 is None and t5["sirketler"] == [] and t5["yillar"] == [2022]
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
