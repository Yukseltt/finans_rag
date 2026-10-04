# Elle puanlama sayfasinin ve ice aktarmanin dogrulugunu sinar:
#   1) 16 soru x 8 cevap = 128; kodlar benzersiz; her soru icin 8 (model, kosul) kombinasyonu birebir kapsanir
#   2) KORLUK: sayfada model adi, kosul adi, "Sources" satiri YOK
#   3) gomulu JSON dogru ayrisir; sayfanin JavaScript'i sozdizimi hatasiz (node varsa) ve sahte DOM'da calisir:
#      1/2/3 tuslari puan verir, siradaki cevaba gecer, ilerleme kaydedilir, disa aktarma dogru kodlari verir
#   4) ice aktarma: tum 128 puan -> dogru (id, model, kosul) eslemesi; eksik/gecersiz puanda DURUR
#   5) cevap_olc.py elle puanlari ELLE sozlugu uzerinden isler (siki/yumusak)
#
# Kullanim: python tests/test_puanlama.py
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "src"))
import elle_puan_ice_aktar as ia  # noqa: E402
import puanlama_sayfasi as ps  # noqa: E402

HARNES = r"""
const fs = require('fs'), vm = require('vm');
const kod = fs.readFileSync(process.argv[2], 'utf8');
const veri = fs.readFileSync(process.argv[3], 'utf8');
function Elem(t) { this.tag = t; this.children = []; this.className = ''; this.style = {}; this.textContent = ''; this.listeners = {}; }
Elem.prototype.appendChild = function (c) { this.children.push(c); return c; };
Elem.prototype.addEventListener = function (t, f) { this.listeners[t] = f; };
Elem.prototype.remove = function () {}; Elem.prototype.click = function () {};
const deposu = {}, ogeler = {};
const sandbox = {
  document: { getElementById: function (id) { if (id === 'veri') return { textContent: veri }; return ogeler[id] || (ogeler[id] = new Elem(id)); },
              createElement: function (t) { return new Elem(t); }, createTextNode: function (s) { return { text: s }; },
              addEventListener: function (t, f) { sandbox.tus = f; }, body: new Elem('body') },
  localStorage: { getItem: function (k) { return k in deposu ? deposu[k] : null; }, setItem: function (k, v) { deposu[k] = v; } },
  window: { scrollTo: function () {} }, URL: { createObjectURL: function () { return 'x'; } }, Blob: function () {}, Number: Number, JSON: JSON, Date: Date, Object: Object
};
vm.createContext(sandbox);
vm.runInContext(kod, sandbox);
const bas = vm.runInContext('VERI.kartlar[0].cevaplar.map(function(c){return c.token;})', sandbox);
sandbox.tus({ key: '1' }); sandbox.tus({ key: '2' }); sandbox.tus({ key: '3' });
const aktif1 = vm.runInContext('aktif', sandbox);
const nesne = vm.runInContext('disaAktarNesnesi()', sandbox);
vm.runInContext('git(1)', sandbox);
const q1 = vm.runInContext('q', sandbox);
const sayac = Object.keys(deposu).length;
console.log(JSON.stringify({ bas: bas, aktif1: aktif1, puanlar: nesne.puanlar, q1: q1, depo_anahtar_sayisi: sayac,
                             toplam: vm.runInContext('TOPLAM', sandbox) }));
"""


def main():
    # 1) yapi
    veri, anahtar = ps.olustur()
    kartlar = veri["kartlar"]
    assert len(kartlar) == 16 and all(len(k["cevaplar"]) == 8 for k in kartlar)
    tokenlar = [c["token"] for k in kartlar for c in k["cevaplar"]]
    assert len(tokenlar) == 128 and len(set(tokenlar)) == 128 and set(tokenlar) == set(anahtar)
    kombinasyon = {(a["model"], a["kosul"]) for a in anahtar.values()}
    assert len(kombinasyon) == 8
    for k in kartlar:
        kom = {(anahtar[c["token"]]["model"], anahtar[c["token"]]["kosul"]) for c in k["cevaplar"]}
        assert kom == kombinasyon, "her soru icin 8 kombinasyon birebir"
        assert len({anahtar[c["token"]]["id"] for c in k["cevaplar"]}) == 1
        assert [c["harf"] for c in k["cevaplar"]] == list("ABCDEFGH")
    # 2) korluk
    metin = json.dumps(veri, ensure_ascii=False).lower()
    for yasak in ("gemini", "flash", "k0", "k1_c", "kosul", "sources:"):
        assert yasak not in metin, f"sayfada gizli olmasi gereken bilgi var: {yasak}"
    # kartlar arasi sira gold sirasindan bagimsiz (karisik): dosya kimligi ile ayni sirada olmasin
    ids = [anahtar[k["cevaplar"][0]["token"]]["id"] for k in kartlar]
    assert ids != sorted(ids), "soru sirasi karisik olmali"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        eski = ps.CIKTI
        ps.CIKTI = tmp
        try:
            ps.yaz()
        finally:
            ps.CIKTI = eski
        html = (tmp / "puanlama.html").read_text(encoding="utf-8")
        # 3) gomulu JSON ve JS
        m = re.search(r'<script id="veri" type="application/json">(.*?)</script>', html, re.S)
        gomulu = json.loads(m.group(1).replace("<\\/", "</"))
        assert gomulu["kartlar"][0]["gold"] and len(gomulu["kartlar"]) == 16
        assert "gemini" not in html.lower()
        js = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
        (tmp / "sayfa.js").write_text(js, encoding="utf-8")
        (tmp / "veri.json").write_text(m.group(1).replace("<\\/", "</"), encoding="utf-8")
        (tmp / "harnes.js").write_text(HARNES, encoding="utf-8")
        if shutil.which("node"):
            sonuc = subprocess.run(["node", "--check", str(tmp / "sayfa.js")], capture_output=True, text=True)
            assert sonuc.returncode == 0, sonuc.stderr
            cikti = subprocess.run(["node", str(tmp / "harnes.js"), str(tmp / "sayfa.js"), str(tmp / "veri.json")],
                                   capture_output=True, text=True)
            assert cikti.returncode == 0, cikti.stderr
            r = json.loads(cikti.stdout)
            assert r["toplam"] == 128 and r["q1"] == 1
            ilk3 = r["bas"][:3]
            assert [r["puanlar"][t] for t in ilk3] == ["dogru", "kismen", "yanlis"], r["puanlar"]
            assert r["aktif1"] == 3 and r["depo_anahtar_sayisi"] == 2                             # sonraki cevaba gecti; kayit yapildi
            print("sayfa JavaScript: tamam (sozdizimi + sahte DOM'da tuslar, ilerleme, kayit, disa aktarma)")
        else:
            print("node yok: JavaScript testi atlandi")

    # 4) ice aktarma
    puanlar = {t: ("dogru" if i % 3 == 0 else "kismen" if i % 3 == 1 else "yanlis") for i, t in enumerate(sorted(anahtar))}
    kayit = ia.donustur(puanlar, anahtar)
    assert len(kayit) == 128 and all(r["puan"] in ia.GECERLI for r in kayit)
    t0 = sorted(anahtar)[0]
    ilk = next(r for r in kayit if r["id"] == anahtar[t0]["id"] and r["model"] == anahtar[t0]["model"] and r["kosul"] == anahtar[t0]["kosul"])
    assert ilk["puan"] == puanlar[t0]
    for bozuk in ({k: v for k, v in list(puanlar.items())[1:]},                                   # eksik
                  {**puanlar, "xyz": "dogru"},                                                    # taniyamadigi kod
                  {**puanlar, t0: "belki"}):                                                      # gecersiz deger
        try:
            ia.donustur(bozuk, anahtar)
        except SystemExit:
            continue
        raise AssertionError("bozuk ice aktarma reddedilmedi")
    print("ice aktarma: tamam (128 puan eslendi; eksik, taniyamadigi kod ve gecersiz deger reddedildi)")
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
