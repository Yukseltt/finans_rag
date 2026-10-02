# baglam_hazirla.py'nin kritik davranislarini sinar (API cagrisi yok):
#   1) K1 baglami TAM 1000 kelimede kesilir, etiketler kelime sayilmaz, son chunk kismen alinabilir
#   2) K2 baglami tekrarsiz gold sayfalarini sirali verir
#   3) K0 isteginde baglam ve etiket yoktur; K1/K2 isteginde baglam ve etiket vardir
#   4) soru metnindeki suslu parantez ve yer tutucu benzeri metin sablonu bozmaz
#   5) prompt dondurma: ayni surum numarasiyla degisen sablon reddedilir
#
# Kullanim: python tests/test_baglam.py
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import baglam_hazirla as b  # noqa: E402


def main():
    # 1) kesme: 3 chunk (400 + 400 + 400 kelime) -> 1000 kelime = 400 + 400 + 200
    bilgi = {c: ("DOC", i, " ".join(f"{c}{j}" for j in range(400))) for i, c in enumerate(("a", "b", "c", "d"))}
    metin, alinan = b.baglam_k1(["a", "b", "c", "d"], bilgi)
    assert [x[2] for x in alinan] == [400, 400, 200], alinan                      # d hic alinmaz
    govde = [s for blok in metin.split("\n\n") for s in blok.split("\n")[1:]]       # etiket satirlari haric
    assert sum(len(g.split()) for g in govde) == 1000
    assert metin.count("[belge: DOC, sayfa: 0]") == 1 and "[belge: DOC, sayfa: 3]" not in metin
    # kisa chunk'lar: toplam butceden az ise hepsi alinir
    kisa = {"x": ("D", 1, "bir iki uc"), "y": ("D", 2, "dort bes")}
    _, alinan = b.baglam_k1(["x", "y"], kisa)
    assert [a[2] for a in alinan] == [3, 2]
    # butce tam doldugunda sonraki chunk'a hic gecilmez
    tam = {"p": ("D", 1, " ".join("w" for _ in range(1000))), "q": ("D", 2, "asla alinmaz")}
    _, alinan = b.baglam_k1(["p", "q"], tam)
    assert len(alinan) == 1 and alinan[0][2] == 1000

    # 2) K2: tekrarsiz, sirali (ayni sayfa iki kez kanit olsa bile bir kez); gercek sayfa dosyasindan
    with tempfile.TemporaryDirectory() as tmp:
        eski = b.SAYFA_KLASORU
        b.SAYFA_KLASORU = Path(tmp)
        with open(Path(tmp) / "DOC.jsonl", "w", encoding="utf-8") as f:
            for i in range(5):
                f.write(json.dumps({"doc": "DOC", "sayfa_idx": i, "metin": f"sayfa  {i}\n\nmetin   burada"}) + "\n")
        soru = {"kanitlar": [{"doc": "DOC", "sayfa": 3}, {"doc": "DOC", "sayfa": 1}, {"doc": "DOC", "sayfa": 3}]}
        metin, sayfalar, kelime = b.baglam_k2(soru, {})
        b.SAYFA_KLASORU = eski
    assert sayfalar == [("DOC", 1), ("DOC", 3)], sayfalar
    assert metin.index("sayfa: 1") < metin.index("sayfa: 3") and metin.count("sayfa: 3]") == 1
    assert "sayfa 1 metin burada" in metin                                           # bosluklar tekil
    assert kelime == 8                                                                # iki sayfa x 4 kelime

    # 3) istek bicimi
    s = {"id": "q1", "soru": "What was the revenue in {FY2022}? Use {BAGLAM} words."}
    k0 = b.istek(s, "K0")
    assert "[belge:" not in k0["kullanici"] and "Sources:" not in k0["kullanici"] and "Final answer:" in k0["kullanici"]
    k1 = b.istek(s, "K1-C200", "[belge: X, sayfa: 1]\nmetin")
    assert "[belge: X, sayfa: 1]" in k1["kullanici"] and "Sources:" in k1["kullanici"]
    # 4) soru metnindeki {BAGLAM} benzeri metin sablonu bozmaz (once baglam yerlestirilir, sonra soru)
    assert k1["kullanici"].count("What was the revenue in {FY2022}? Use {BAGLAM} words.") == 1
    assert k0["kullanici"].count("{FY2022}") == 1
    assert k0["prompt_surum"] == b.PROMPT_SURUM and k0["sistem"] == b.SISTEM

    # 5) dondurma korumasi
    with tempfile.TemporaryDirectory() as tmp:
        yol = Path(tmp) / "prompt_vtest.json"
        b.sablonu_dondur(yol)                                   # ilk kez yazar
        b.sablonu_dondur(yol)                                   # ayni sablon: sorun yok
        eski_sistem = b.SISTEM
        b.SISTEM = eski_sistem + " Degisti."
        try:
            b.sablonu_dondur(yol)
        except SystemExit:
            print("dondurma korumasi: tamam (degisen sablon reddedildi)")
        else:
            raise AssertionError("dondurma korumasi calismadi")
        finally:
            b.SISTEM = eski_sistem

    # pilot secimi deterministik ve dengeli
    ornek = [{"id": f"{t}{i}", "tur": t} for t in ("a", "b", "c") for i in range(9, -1, -1)]
    p = b.pilot_idleri(ornek)
    assert len(p) == 12 and p == b.pilot_idleri(list(reversed(ornek)))
    assert sorted(p) == sorted(f"{t}{i}" for t in "abc" for i in range(4))
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
