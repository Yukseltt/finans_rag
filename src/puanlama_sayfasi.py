# Elle puanlama sayfasi uretir (Deney 5: otomatik puanlanamayan 16 soru x 8 cevap = 128 cevap).
#
# Kullanim: python src/puanlama_sayfasi.py              (Deney 5 turu: 16 soru x 8 cevap = 128)
#           python src/puanlama_sayfasi.py --tur d9     (Deney 8+9 turu: 16 soru x 6 cevap = 96:
#                                                         K1-c200, K1-R2 (v2), K1-R2 (v3), her biri x 2 okuyucu)
# Girdi:    data/islenmis/cevaplar/*.jsonl, gelistirme gold cevaplari
# Cikti:    data/islenmis/puanlama/puanlama.html   (TARAYICIDA acilan tek dosya; veri icinde gomulu)
#           data/islenmis/puanlama/anahtar.json    (rastgele cevap kodu -> soru, model, kosul; SAYFADA YOK)
#
# KOR PUANLAMA: her soru icin 8 cevap karisik sirada ve A-H harfleriyle gosterilir; model ve kosul GIZLIDIR.
# "Sources:" satiri gizlenir (kapali kitap cevaplarinda yok, kosulu ele verirdi).
# Sayfa FinanceBench icerigi ve model cevaplari tasir: repoya GIRMEZ (data/islenmis gitignore'dadir).
#
# Puan seviyeleri: dogru / kismen / yanlis. Ana analizde "kismen" YANLIS sayilir (siki), yumusak analizde
# DOGRU sayilir; ikisi de raporlanir (cevap_olc.py).
import json
import random
from pathlib import Path

import cevap_metrik as c
import cevap_olc as co
import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "data" / "islenmis" / "puanlama"
SURUM = "v1"
TOHUM = 20261004
HARFLER = "ABCDEFGH"
# tur -> (kosullar, sayfa surumu, tohum, html dosyasi, anahtar dosyasi); d5 varsayilandir ve onceki ciktiyi AYNEN uretir
TURLER = {
    "d5": (co.KOSULLAR, SURUM, TOHUM, "puanlama.html", "anahtar.json"),
    "d9": (["k1_c200", "k1_r2", "k1_r2_v3"], "d9", TOHUM + 9, "puanlama_d9.html", "anahtar_d9.json"),
}

KURALLAR = [
    ("Doğru", "Cevap, gold cevabın ana bilgisini veriyor ve onunla çelişmiyor. Fazladan doğru ayrıntı, farklı ifade, yazım veya biçim farkı sorun değil."),
    ("Kısmen", "Ana bilginin bir kısmı doğru ya da eksik (örn. 3 şirketten 2'si; doğru yönü söylüyor ama belirsiz). Şüphede kalırsan da Kısmen."),
    ("Yanlış", "Ana bilgi yanlış, gold ile çelişiyor, ya da 'bulamadım / bilgi yok' deyip cevap vermiyor."),
    ("Nasıl karar vereceksin", "Gold cevabı esas al: modelin cevabı gerçekte makul olsa bile gold'daki bilgiyi vermiyorsa Yanlış. Önce 'Nihai cevap'a bak; kararsızsan 'Tam cevabı göster' ile gerekçeyi oku."),
]


def elle_sorular(sorular, gold):
    return sorted(i for i in gold if c.tur(gold[i]) == "serbest"
                  or (c.tur(gold[i]) == "anahtar_sayi" and c.anahtar_sayi("x", gold[i])["n"] == 0))


def govdeler(m, k):
    sonuc = {}
    for satir in open(co.CEVAPLAR / f"{m}__{k}.jsonl", encoding="utf-8"):
        x = json.loads(satir)
        if x["hata"] is None:
            sonuc[x["id"]] = x["yanit"]
    return sonuc


def olustur(tur="d5"):
    kosullar, surum, tohum, _, _ = TURLER[tur]
    sorular = d.yukle_sorular()  # varsayilan: gelistirme; kilitli kumeye dokunmaz
    soru = {s["id"]: s for s in sorular}
    gold = co.goldleri_yukle(sorular)
    ids = elle_sorular(sorular, gold)
    yanitlar = {(m, k): govdeler(m, k) for m in co.MODELLER for k in kosullar}
    rng = random.Random(tohum)
    anahtar, kartlar = {}, []
    for n, i in enumerate(sorted(ids, key=lambda x: rng.random()), 1):  # soru sirasi da karisik
        adaylar = [(m, k) for m in co.MODELLER for k in kosullar]
        rng.shuffle(adaylar)
        cevaplar = []
        for harf, (m, k) in zip(HARFLER, adaylar):
            tam = yanitlar[(m, k)].get(i)
            token = f"c{rng.getrandbits(40):010x}"
            anahtar[token] = {"id": i, "model": m, "kosul": k}
            if tam is None:
                cevaplar.append({"token": token, "harf": harf, "final": "(yanıt yok)", "tam": ""})
                continue
            govde, _ = c.kaynak_ayir(tam)        # Sources satiri gizlenir
            cevaplar.append({"token": token, "harf": harf, "final": c.son_cevap(tam) or govde.strip(), "tam": govde.strip()})
        kartlar.append({"n": n, "soru": soru[i]["soru"], "gold": gold[i], "cevaplar": cevaplar})
    return {"surum": surum, "kartlar": kartlar, "kurallar": KURALLAR}, anahtar


SABLON = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cevap puanlama</title>
<style>
:root{--zemin:#f6f7f9;--kart:#fff;--yazi:#1c2330;--ikinci:#5b6677;--cizgi:#d9dee6;--vurgu:#2f5fd0;--dogru:#1b8a4b;--kismen:#b7791f;--yanlis:#c0392b;--gold:#e8f5ec}
@media (prefers-color-scheme:dark){:root{--zemin:#14181f;--kart:#1d232d;--yazi:#e6eaf0;--ikinci:#9aa5b5;--cizgi:#323a48;--vurgu:#7ea2ff;--gold:#17301f}}
body{margin:0;background:var(--zemin);color:var(--yazi);font:15px/1.5 system-ui,Segoe UI,sans-serif}
.kap{max-width:880px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:4px 0 12px}
.ust{position:sticky;top:0;background:var(--zemin);padding:8px 0;z-index:2;border-bottom:1px solid var(--cizgi)}
.ilerleme{height:8px;background:var(--cizgi);border-radius:4px;overflow:hidden;margin-top:6px}
.ilerleme>div{height:100%;background:var(--vurgu)}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:14px;margin:12px 0}
.soru{font-weight:600}
.gold{background:var(--gold);border-left:4px solid var(--dogru);padding:8px 10px;border-radius:6px;margin-top:8px;white-space:pre-wrap}
.gold b,.etiket{display:block;font-size:12px;color:var(--ikinci);font-weight:600;margin-bottom:2px;text-transform:uppercase;letter-spacing:.04em}
.cevap{border:2px solid var(--cizgi);border-radius:10px;padding:10px 12px;margin:10px 0;background:var(--kart)}
.cevap.aktif{border-color:var(--vurgu)}
.cevap .harf{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;background:var(--vurgu);color:#fff;font-weight:700;margin-right:8px}
.final{white-space:pre-wrap;margin:6px 0}
details{color:var(--ikinci);font-size:13px}
details pre{white-space:pre-wrap;margin:6px 0;font:inherit}
.dugmeler{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}
button{font:inherit;cursor:pointer;border:1px solid var(--cizgi);background:var(--kart);color:var(--yazi);border-radius:8px;padding:6px 14px}
button.sec-dogru{background:var(--dogru);color:#fff;border-color:var(--dogru)}
button.sec-kismen{background:var(--kismen);color:#fff;border-color:var(--kismen)}
button.sec-yanlis{background:var(--yanlis);color:#fff;border-color:var(--yanlis)}
.gezinme{display:flex;gap:8px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.not{color:var(--ikinci);font-size:13px}
.kurallar summary{cursor:pointer;color:var(--vurgu)}
.kurallar dt{font-weight:700;margin-top:6px}.kurallar dd{margin:0 0 0 12px;color:var(--ikinci)}
kbd{border:1px solid var(--cizgi);border-radius:4px;padding:0 5px;font-size:12px;background:var(--kart)}
</style></head><body><div class="kap">
<div class="ust"><h1>Cevap puanlama</h1>
<div class="gezinme"><span id="sayac"></span><span class="not" id="durum"></span></div>
<div class="ilerleme"><div id="cubuk" style="width:0%"></div></div></div>
<details class="kurallar kart" open><summary>Puanlama kuralları (okumak için tıkla)</summary><dl id="kurallar"></dl>
<p class="not">Kısayollar: <kbd>1</kbd> Doğru · <kbd>2</kbd> Kısmen · <kbd>3</kbd> Yanlış · <kbd>↑</kbd><kbd>↓</kbd> cevaplar arası · <kbd>←</kbd><kbd>→</kbd> soru. İlerleme bu tarayıcıda otomatik kaydedilir.</p></details>
<div id="alan"></div>
<div class="kart gezinme"><button id="onceki">← Önceki soru</button><button id="indir">Puanları indir (JSON)</button><button id="sonraki">Sonraki soru →</button></div>
<p class="not">Cevapların hangi model/koşuldan geldiği bilerek gizlidir. Bitirince "Puanları indir" ile dosyayı kaydet ve bana ver.</p>
</div>
<script id="veri" type="application/json">__VERI__</script>
<script>
var VERI = JSON.parse(document.getElementById('veri').textContent);
var ANAHTAR = 'finans_rag_puanlama_' + VERI.surum;
var durum = {}, q = 0, aktif = 0;
try { durum = JSON.parse(localStorage.getItem(ANAHTAR) || '{}'); q = Number(localStorage.getItem(ANAHTAR + '_q') || 0); } catch (e) {}
if (!(q >= 0 && q < VERI.kartlar.length)) q = 0;
var TOPLAM = VERI.kartlar.reduce(function (a, k) { return a + k.cevaplar.length; }, 0);

function kaydet() { try { localStorage.setItem(ANAHTAR, JSON.stringify(durum)); localStorage.setItem(ANAHTAR + '_q', String(q)); } catch (e) {} }
function puanlanan() { return Object.keys(durum).length; }
function disaAktarNesnesi() { return { surum: VERI.surum, tarih: new Date().toISOString(), puanlar: durum }; }
function el(etiket, sinif, metin) { var e = document.createElement(etiket); if (sinif) e.className = sinif; if (metin !== undefined) e.textContent = metin; return e; }

function ciz() {
  var k = VERI.kartlar[q], alan = document.getElementById('alan');
  alan.textContent = '';
  var kart = el('div', 'kart');
  kart.appendChild(el('div', 'etiket', 'Soru'));
  kart.appendChild(el('div', 'soru', k.soru));
  var g = el('div', 'gold'); g.appendChild(el('b', '', 'Gold (doğru) cevap')); g.appendChild(document.createTextNode(k.gold));
  kart.appendChild(g); alan.appendChild(kart);
  k.cevaplar.forEach(function (c, i) {
    var kutu = el('div', 'cevap' + (i === aktif ? ' aktif' : ''));
    kutu.addEventListener('click', function () { aktif = i; ciz(); });
    var bas = el('div'); bas.appendChild(el('span', 'harf', c.harf)); bas.appendChild(el('span', 'etiket', 'Nihai cevap'));
    kutu.appendChild(bas); kutu.appendChild(el('div', 'final', c.final));
    if (c.tam) { var d = el('details'); d.appendChild(el('summary', '', 'Tam cevabı göster')); d.appendChild(el('pre', '', c.tam)); kutu.appendChild(d); }
    var dug = el('div', 'dugmeler');
    [['dogru', 'Doğru (1)'], ['kismen', 'Kısmen (2)'], ['yanlis', 'Yanlış (3)']].forEach(function (p) {
      var b = el('button', durum[c.token] === p[0] ? 'sec-' + p[0] : '', p[1]);
      b.addEventListener('click', function (ev) { ev.stopPropagation(); puanla(i, p[0]); });
      dug.appendChild(b);
    });
    kutu.appendChild(dug); alan.appendChild(kutu);
  });
  var biten = k.cevaplar.filter(function (c) { return durum[c.token]; }).length;
  document.getElementById('sayac').textContent = 'Soru ' + (q + 1) + ' / ' + VERI.kartlar.length + '  (bu soruda ' + biten + '/' + k.cevaplar.length + ')';
  document.getElementById('durum').textContent = 'Toplam puanlanan: ' + puanlanan() + ' / ' + TOPLAM;
  document.getElementById('cubuk').style.width = (100 * puanlanan() / TOPLAM) + '%';
}
function puanla(i, deger) {
  var k = VERI.kartlar[q]; durum[k.cevaplar[i].token] = deger; kaydet();
  var sonraki = k.cevaplar.findIndex(function (c, j) { return j > i && !durum[c.token]; });
  if (sonraki >= 0) aktif = sonraki; ciz();
}
function git(yeni) { if (yeni >= 0 && yeni < VERI.kartlar.length) { q = yeni; aktif = 0; kaydet(); ciz(); window.scrollTo(0, 0); } }
function indir() {
  var blob = new Blob([JSON.stringify(disaAktarNesnesi(), null, 2)], { type: 'application/json' });
  var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'elle_puanlar.json';
  document.body.appendChild(a); a.click(); a.remove();
}
document.getElementById('onceki').addEventListener('click', function () { git(q - 1); });
document.getElementById('sonraki').addEventListener('click', function () { git(q + 1); });
document.getElementById('indir').addEventListener('click', indir);
document.addEventListener('keydown', function (e) {
  if (e.key === '1') puanla(aktif, 'dogru'); else if (e.key === '2') puanla(aktif, 'kismen'); else if (e.key === '3') puanla(aktif, 'yanlis');
  else if (e.key === 'ArrowDown') { aktif = Math.min(aktif + 1, VERI.kartlar[q].cevaplar.length - 1); ciz(); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { aktif = Math.max(aktif - 1, 0); ciz(); e.preventDefault(); }
  else if (e.key === 'ArrowRight') git(q + 1); else if (e.key === 'ArrowLeft') git(q - 1);
});
var dl = document.getElementById('kurallar');
VERI.kurallar.forEach(function (r) { dl.appendChild(el('dt', '', r[0])); dl.appendChild(el('dd', '', r[1])); });
ciz();
</script></body></html>
"""


def yaz(tur="d5"):
    veri, anahtar = olustur(tur)
    _, _, _, html_adi, anahtar_adi = TURLER[tur]
    CIKTI.mkdir(parents=True, exist_ok=True)
    govde = json.dumps(veri, ensure_ascii=False).replace("</", "<\\/")  # script etiketini erken kapatmasin
    (CIKTI / html_adi).write_text(SABLON.replace("__VERI__", govde), encoding="utf-8")
    (CIKTI / anahtar_adi).write_text(json.dumps(anahtar, indent=2), encoding="utf-8")
    return veri, anahtar


def main():
    import sys
    tur = sys.argv[sys.argv.index("--tur") + 1] if "--tur" in sys.argv else "d5"
    veri, anahtar = yaz(tur)
    n = sum(len(k["cevaplar"]) for k in veri["kartlar"])
    print(f"{len(veri['kartlar'])} soru, {n} cevap -> {CIKTI / TURLER[tur][3]}")
    print("sayfayi tarayicida ac: dosyaya cift tikla (ya da dosya yolunu tarayici adres cubuguna yapistir)")


if __name__ == "__main__":
    main()
