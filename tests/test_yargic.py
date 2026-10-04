# yargic_gemini.py'yi SAHTE istemciyle sinar (API'ye ve anahtara dokunulmaz):
#   1) etiket ayristirma (markdown, buyuk/kucuk harf, eksik satir)  2) maliyet  3) onbellek  4) tavan
#   5) ayristirilamayan yanit hata sayilir ve onbellege BASARI girmez  6) ornek secimi dengeli ve deterministik
#   7) oge kumesi: 128 kalibrasyon (insan puanli) + 64 yeni; yargic prompt'unda model/kosul bilgisi YOK
#
# Kullanim: python tests/test_yargic.py
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import okuyucu_gemini as ok  # noqa: E402
import yargic_gemini as y  # noqa: E402


class Sahte:
    def __init__(self, cevaplar):
        self.cevaplar, self.cagri = list(cevaplar), 0
        self.models = SimpleNamespace(generate_content=self._uret)

    def _uret(self, model, contents, config):
        self.cagri += 1
        return self.cevaplar.pop(0)


def yanit(metin, p=300, c=10, d=200):
    kul = SimpleNamespace(prompt_token_count=p, candidates_token_count=c, thoughts_token_count=d, total_token_count=p + c + d)
    return SimpleNamespace(text=metin, usage_metadata=kul, candidates=[SimpleNamespace(finish_reason="STOP")])


def oge(a="m|k|q", insan="dogru"):
    return {"anahtar": a, "id": "q", "model": "m", "kosul": "k", "tur": "kalibrasyon", "soru": "Q?", "gold": "G", "final": "F",
            "govde": "R", "insan": insan}


def main():
    # 1) etiket ayristirma
    assert y.etiket_oku("Grade: correct") == "dogru" and y.etiket_oku("Grade: partial") == "kismen" and y.etiket_oku("Grade: wrong") == "yanlis"
    assert y.etiket_oku("**Grade:** CORRECT") == "dogru" and y.etiket_oku("The answer.\nGrade: wrong\n") == "yanlis"
    assert y.etiket_oku("I think it is fine") is None and y.etiket_oku("") is None and y.etiket_oku(None) is None
    # 2) maliyet: (300 x 0.75 + 210 x 3.75) / 1e6
    assert abs(y.maliyet("gemini-3.7-flash", 300, 210) - (300 * 0.75 + 210 * 3.75) / 1e6) < 1e-12
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        # 3) onbellek ve harcama kaydi
        ist = Sahte([yanit("Grade: correct")])
        yg = y.Yargic(ist, "gemini-3.7-flash", None, k, ok.Harcama(k / "h.json", 5.0), bekle=lambda s: None)
        s = yg.calistir([oge()])
        assert s["cagri"] == 1 and ist.cagri == 1 and yg.harcama.toplam > 0
        s = y.Yargic(ist, "gemini-3.7-flash", None, k, ok.Harcama(k / "h.json", 5.0)).calistir([oge()])
        assert s["cagri"] == 0 and s["onbellekten"] == 1 and ist.cagri == 1
        # farkli dusunme ayari ayri onbellek (ayri dosya, ayri hash)
        assert y.Yargic(ist, "gemini-3.7-flash", "low", k).yol() != yg.yol()
        # 5) ayristirilamayan yanit hata; onbellege girmez
        ist2 = Sahte([yanit("no idea"), yanit("Grade: partial")])
        yg2 = y.Yargic(ist2, "gemini-3.7-flash", "low", k, ok.Harcama(k / "h2.json", 5.0), bekle=lambda s: None)
        assert yg2.calistir([oge("a")])["hata"] == 1 and not yg2.onbellek()
        assert yg2.calistir([oge("a")])["hata"] == 0 and yg2.onbellek()
    with tempfile.TemporaryDirectory() as tmp:
        # 4) tavan: cagri YAPILMADAN durur
        k = Path(tmp)
        ist = Sahte([yanit("Grade: correct")])
        yg = y.Yargic(ist, "gemini-3.7-flash", None, k, ok.Harcama(k / "h.json", 0.001))
        try:
            yg.calistir([oge()])
        except ok.Durdu:
            assert ist.cagri == 0
        else:
            raise AssertionError("tavan calismadi")
    # 6) ornek secimi
    ogeler = [dict(oge(f"a{i}", ["dogru", "yanlis", "kismen"][i % 3]), anahtar=f"a{i}") for i in range(30)]
    o1, o2 = y.ornek_sec(ogeler, 8), y.ornek_sec(list(reversed(ogeler)), 8)
    assert [x["anahtar"] for x in o1] == [x["anahtar"] for x in o2] and len(o1) == 8
    assert sum(x["insan"] == "dogru" for x in o1) == 4 and sum(x["insan"] == "yanlis" for x in o1) == 3 and sum(x["insan"] == "kismen" for x in o1) == 1
    # 7) gercek oge kumesi
    tum = y.oge_kumesi()
    kal = [o for o in tum if o["tur"] == "kalibrasyon"]
    assert len(tum) == 192 and len(kal) == 128 and all(o["insan"] in ("dogru", "kismen", "yanlis") for o in kal)
    metin = y.prompt(tum[0]).lower()
    for yasak in ("gemini", "k1_r2", "kosul", "sources:"):
        assert yasak not in metin and yasak not in y.SISTEM.lower(), f"yargic prompt'unda gizli bilgi: {yasak}"
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
