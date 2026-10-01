# Butce penceresinde kanit metni kapsamasi (Deney 4 yorumlama kontrolu, POST HOC, betimsel).
#
# Neden: sayfa duzeyi butce Recall'u, ayni kelime butcesinde kucuk chunk'in daha cok FARKLI
# sayfadan parca getirmesinden yapisal fayda gorebilir (isabet "sayfadan herhangi bir chunk").
# Bu betik, penceredeki chunk'larin BIRLESIMININ kanit metnini ne kadar kapsadigini olcer;
# yani getirilen metin gercekten kanitin kendisini iceriyor mu.
#
# Kullanim: python src/butce_kapsama.py
# Girdi:    data/islenmis/siralamalar/dense_<model>[_<varyant>]_rerank_{ortak,tek}.json
# Cikti:    ekrana tablo + sonuclar/olcumler/butce_kapsama.json
# Sadece gelistirme kumesi. On kayitli olcut DEGILDIR; yorumlama amaclidir.
import json
import statistics
from pathlib import Path

import degerlendir as d

KOK = Path(__file__).resolve().parent.parent
SIRA = KOK / "data" / "islenmis" / "siralamalar"
VARYANTLAR = ["c200", "c100", "c200o50", "c300"]
MODELLER = ["bge-base-en", "e5-base"]


def pencere(siralama, bilgi):
    # degerlendir._soru_istatistigi ile ayni kural: birikim BUTCE'ye ulasmadan baslayan chunk dahil
    birikim, secilen = 0, []
    for cid in siralama:
        if birikim >= d.BUTCE:
            break
        birikim += len(bilgi[cid][2].split())
        secilen.append(cid)
    return secilen


def main():
    sorular = d.yukle_sorular()  # varsayilan: gelistirme
    sonuc = {}
    print(f"{'varyant':9s} {'model':12s} {'uzay':5s} {'sayfa isabeti':>13s} {'birlesim kapsama':>17s} {'ort. farkli sayfa':>18s}")
    for v in VARYANTLAR:
        bilgi = d.yukle_chunk_bilgi(d.chunks_yolu(v))
        for m in MODELLER:
            for u in ("ortak", "tek"):
                sr = json.load(open(SIRA / f"dense_{m}{d.ek(v)}_rerank_{u}.json", encoding="utf-8"))
                isabet, kapsamalar, sayfa_sayisi = [], [], []
                for s in sorular:
                    secilen = pencere(sr[s["id"]], bilgi)
                    sayfalar = {bilgi[c][:2] for c in secilen}
                    sayfa_sayisi.append(len(sayfalar))
                    birlesim = set()
                    for c in secilen:
                        birlesim |= d._parcalar(bilgi[c][2])
                    for kn in s["kanitlar"]:
                        isabet.append((kn["doc"], kn["sayfa"]) in sayfalar)
                        ev = d._parcalar(kn["metin"])
                        if ev:
                            kapsamalar.append(len(ev & birlesim) / len(ev))
                kayit = {"sayfa_isabeti": round(sum(isabet) / len(isabet), 3),
                         "birlesim_kapsama": round(sum(kapsamalar) / len(kapsamalar), 3),
                         "ort_farkli_sayfa": round(statistics.mean(sayfa_sayisi), 2)}
                sonuc[f"{v}|{m}|{u}"] = kayit
                print(f"{v:9s} {m:12s} {u:5s} {kayit['sayfa_isabeti']:13.3f} {kayit['birlesim_kapsama']:17.3f} {kayit['ort_farkli_sayfa']:18.2f}")
    (KOK / "sonuclar" / "olcumler" / "butce_kapsama.json").write_text(json.dumps(sonuc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
