# okuyucu_gemini.py'nin guvencelerini SAHTE istemciyle sinar: API'ye ve anahtara HIC dokunulmaz.
#   1) maliyet hesabi (dusunme tokenlari cikis olarak faturalanir)
#   2) onbellek: ayni istek ikinci kez gonderilmez; istek degisirse yeniden gonderilir
#   3) harcama tavani: asilacaksa cagri YAPILMADAN durur
#   4) yeniden deneme: gecici hatalarda (503) tekrar dener; kalici hatada (400) denemez; basarisiz kayit
#      onbellege BASARI olarak girmez ve sonraki calistirmada tekrar denenir
#   5) bos yanit hata sayilir
#
# Kullanim: python tests/test_okuyucu.py
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import okuyucu_gemini as o  # noqa: E402
from google.genai import errors  # noqa: E402


def api_hatasi(kod):
    return errors.APIError(kod, {"error": {"message": f"sahte hata {kod}", "status": "X"}})


class SahteIstemci:
    # cevaplar: sirayla donecek sonuclar (yanit nesnesi ya da firlatilacak istisna)
    def __init__(self, cevaplar):
        self.cevaplar = list(cevaplar)
        self.cagri = 0
        self.models = SimpleNamespace(generate_content=self._uret)

    def _uret(self, model, contents, config):
        self.cagri += 1
        s = self.cevaplar.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def yanit(metin="Final answer: 5", p=1000, c=100, d=400):
    kul = SimpleNamespace(prompt_token_count=p, candidates_token_count=c, thoughts_token_count=d, total_token_count=p + c + d)
    return SimpleNamespace(text=metin, usage_metadata=kul, candidates=[SimpleNamespace(finish_reason="STOP")])


def istek(i="q1", kullanici="soru"):
    return {"id": i, "sistem": "sistem", "kullanici": kullanici, "prompt_surum": "vtest"}


def main():
    # 1) maliyet: (1000 x 0.75 + (100 + 400) x 3.75) / 1e6
    assert abs(o.maliyet_usd("gemini-3.8-flash", 1000, 500) - 0.002625) < 1e-12
    assert abs(o.maliyet_usd("gemini-3.5-flash-lite", 1000, 500) - (1000 * 0.30 + 500 * 2.50) / 1e6) < 1e-12

    with tempfile.TemporaryDirectory() as tmp:
        klasor = Path(tmp)
        bekleme = []
        # 2) onbellek
        ist = SahteIstemci([yanit(), yanit()])
        ok = o.Okuyucu(ist, "gemini-3.8-flash", klasor, bekle=bekleme.append)
        s = ok.calistir([istek()], "k0")
        assert s["cagri"] == 1 and ist.cagri == 1 and abs(ok.harcama.toplam - 0.002625) < 1e-12
        kayit = json.loads(open(klasor / "gemini-3.8-flash__k0.jsonl", encoding="utf-8").readline())
        assert kayit["kullanim"] == {"girdi": 1000, "cikti": 100, "dusunme": 400, "toplam": 1500} and kayit["hata"] is None
        s = o.Okuyucu(ist, "gemini-3.8-flash", klasor, bekle=bekleme.append).calistir([istek()], "k0")
        assert s["cagri"] == 0 and s["onbellekten"] == 1 and ist.cagri == 1                      # ikinci kez gonderilmez
        s = o.Okuyucu(ist, "gemini-3.8-flash", klasor, bekle=bekleme.append).calistir([istek(kullanici="degisti")], "k0")
        assert s["cagri"] == 1 and ist.cagri == 2                                                # istek degisti: yeniden gonderilir
        ok2 = o.Okuyucu(ist, "gemini-3.8-flash", klasor)
        assert abs(ok2.harcama.toplam - 2 * 0.002625) < 1e-12                                   # harcama diske kalici

    with tempfile.TemporaryDirectory() as tmp:
        klasor = Path(tmp)
        # 3) tavan: kucuk tavan; cagri HIC yapilmadan Durdu
        ist = SahteIstemci([yanit()])
        ok = o.Okuyucu(ist, "gemini-3.8-flash", klasor, harcama=o.Harcama(klasor / "h.json", tavan_usd=0.001))
        try:
            ok.calistir([istek()], "k0")
        except o.Durdu:
            assert ist.cagri == 0
            print("harcama tavani: tamam (cagri yapilmadan durdu)")
        else:
            raise AssertionError("tavan calismadi")
        # tavan, birikmis harcama ile de calisir
        h = o.Harcama(klasor / "h2.json", tavan_usd=0.05)
        h.ekle("gemini-3.8-flash", 0.04)
        ok = o.Okuyucu(SahteIstemci([yanit()]), "gemini-3.8-flash", klasor, harcama=h)
        try:
            ok.calistir([istek("q9")], "k0")
        except o.Durdu:
            pass
        else:
            raise AssertionError("birikmis harcamayla tavan calismadi")

    with tempfile.TemporaryDirectory() as tmp:
        klasor = Path(tmp)
        # 4) gecici hata: 503, 503, sonra basari -> 3 cagri, 2 bekleme, basarili kayit
        bekleme = []
        ist = SahteIstemci([api_hatasi(503), api_hatasi(503), yanit()])
        ok = o.Okuyucu(ist, "gemini-3.5-flash-lite", klasor, bekle=bekleme.append)
        s = ok.calistir([istek()], "k0")
        assert ist.cagri == 3 and bekleme == [2, 4] and s["hata"] == 0
        # kalici hata: 400 -> yeniden denenmez; kayit hata ile yazilir, onbellege BASARI girmez
        ist = SahteIstemci([api_hatasi(400)])
        ok = o.Okuyucu(ist, "gemini-3.5-flash-lite", klasor, bekle=bekleme.append)
        s = ok.calistir([istek("q2")], "k0")
        assert ist.cagri == 1 and s["hata"] == 1
        assert ("q2", o.istek_hash(istek("q2"), "gemini-3.5-flash-lite")) not in ok.onbellek("k0")
        ist = SahteIstemci([yanit()])                                                             # sonraki calistirmada tekrar denenir
        s = o.Okuyucu(ist, "gemini-3.5-flash-lite", klasor, bekle=bekleme.append).calistir([istek("q2")], "k0")
        assert ist.cagri == 1 and s["hata"] == 0
        # hep gecici hata: DENEME kadar dener, sonra hata kaydi
        ist = SahteIstemci([api_hatasi(429)] * o.DENEME)
        s = o.Okuyucu(ist, "gemini-3.5-flash-lite", klasor, bekle=bekleme.append).calistir([istek("q3")], "k0")
        assert ist.cagri == o.DENEME and s["hata"] == 1
        # 5) bos yanit hata sayilir ama ucretlendirilir
        ist = SahteIstemci([yanit(metin="")])
        ok = o.Okuyucu(ist, "gemini-3.5-flash-lite", klasor, bekle=bekleme.append)
        onceki = ok.harcama.toplam
        s = ok.calistir([istek("q4")], "k0")
        assert s["hata"] == 1 and ok.harcama.toplam > onceki

    # istek hash'i kararli ve model/ayara duyarli
    a = istek()
    assert o.istek_hash(a, "gemini-3.8-flash") == o.istek_hash(dict(a), "gemini-3.8-flash")
    assert o.istek_hash(a, "gemini-3.8-flash") != o.istek_hash(a, "gemini-3.5-flash-lite")
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
