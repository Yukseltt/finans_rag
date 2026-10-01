# Retrieval degerlendirme kutuphanesi: tum yontemler (BM25, dense, hibrit, reranker)
# AYNI olcum koduyla olculur. Metrikler Karar 6'daki tanimlara uyar.
#
# Girdi:  her soru icin siralanmis chunk_id listesi (en alakali basta)
# Cikti:  metrikler + %95 guven araliklari (soru bazli bootstrap)
#
# Metrikler (kanit = bir sorunun bir kanit sayfasi; kanitlar ayri sayilir):
#   recall@k        kanit sayfasindan bir chunk ilk k'da mi              (BASLIK metrik)
#   mrr             ilk dogru chunk'in 1/sirasi, kanit ortalamasi
#   soru_tum@k      sorunun TUM kanitlari ilk k'da mi (soru duzeyi)
#   recall_butce    ilk 1000 KELIMELIK baglam penceresinde mi (chunk boyutlarini adil kiyaslar, Deney 4)
#   metin_kapsama@k kanit metninin 5-kelimelik parcalarinin ilk k chunk'tan en iyisinde
#                   kapsanma orani, kanit ortalamasi                      (IKINCIL metrik)
#
# KORUMA: kilitli test kumesi (Karar 8) varsayilan olarak yuklenemez ve olculemez.
# Final olcum disinda kilitli=True kullanilmaz.
import collections
import json
import random
from pathlib import Path

from sizinti_metin import normalize

KOK = Path(__file__).resolve().parent.parent
HAM = KOK / "data" / "ham"
SONUC = KOK / "sonuclar"
CHUNKS = KOK / "data" / "islenmis" / "chunks.jsonl"

KS = (1, 5, 10, 20, 50)
SHINGLE_N = 5
BUTCE = 1000  # eslesmis baglam butcesi (kelime): Deney 4'te chunk boyutlari arasi adil kiyas icin


def chunk_etiketi(kelime, ortusme=0):
    return f"c{kelime}" + (f"o{ortusme}" if ortusme else "")


def chunks_yolu(etiket="c200"):
    # baz (c200) eski dosya adini korur; varyantlar chunks_<etiket>.jsonl
    return CHUNKS if etiket == "c200" else CHUNKS.with_name(f"chunks_{etiket}.jsonl")


def ek(etiket="c200"):
    # dosya adlarina eklenen sonek: baz icin bos, varyantlar icin _<etiket>
    return "" if etiket == "c200" else f"_{etiket}"


def _bolme():
    return json.load(open(SONUC / "fb_bolme.json", encoding="utf-8"))


def yukle_sorular(kilitli: bool = False):
    # Varsayilan: sadece gelistirme kumesi. kilitli=True SADECE final olcum icin.
    bolme = _bolme()
    idler = set(bolme["kilitli"]["idler"] if kilitli else bolme["gelistirme"]["idler"])
    sorular = []
    with open(HAM / "financebench" / "sorular.jsonl", encoding="utf-8") as f:
        for satir in f:
            if not satir.strip():
                continue
            s = json.loads(satir)
            if s["financebench_id"] not in idler:
                continue
            sorular.append({
                "id": s["financebench_id"], "doc": s["doc_name"], "tur": s["question_type"],
                "soru": s["question"],
                "kanitlar": [{"doc": e["doc_name"], "sayfa": e["evidence_page_num"], "metin": e["evidence_text"]}
                             for e in s["evidence"]],
            })
    return sorular


def yukle_chunk_bilgi(yol=None):
    # chunk_id -> (doc, sayfa_idx, metin); yol verilmezse baz chunk dosyasi
    bilgi = {}
    with open(yol or CHUNKS, encoding="utf-8") as f:
        for satir in f:
            c = json.loads(satir)
            bilgi[c["chunk_id"]] = (c["doc"], c["sayfa_idx"], c["metin"])
    return bilgi


def sirket_haritasi():
    # doc_name -> sirket (belgeler.jsonl). Sirket-kumeli bootstrap icin: ayni sirketin sorulari bagimsiz degildir.
    harita = {}
    with open(HAM / "financebench" / "belgeler.jsonl", encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                b = json.loads(satir)
                harita[b["doc_name"]] = b["company"]
    return harita


def soru_kumeleri(sorular):
    # soru_id -> sirket (kume anahtari)
    harita = sirket_haritasi()
    return {s["id"]: harita[s["doc"]] for s in sorular}


def _parcalar(metin):
    k = normalize(metin)
    return {tuple(k[i:i + SHINGLE_N]) for i in range(len(k) - SHINGLE_N + 1)}


def _soru_istatistigi(soru, siralama, bilgi, ks):
    # Bir sorunun toplanabilir istatistikleri (bootstrap icin soru basina saklanir).
    n_kanit = len(soru["kanitlar"])
    # butce penceresi: birikim BUTCE'ye ulasmadan baslayan her chunk dahil (tam 200 kelimelik chunk'larda 5 chunk)
    birikim, n_butce = 0, 0
    for cid in siralama:
        if birikim >= BUTCE:
            break
        birikim += len(bilgi[cid][2].split())
        n_butce += 1
    hit_butce = 0
    hit = {k: 0 for k in ks}
    rr = 0.0
    kapsama = {k: 0.0 for k in ks}
    n_kapsama = 0
    chunk_parcalari = {}  # ayni chunk'i tekrar tekrar parcalamamak icin
    for kanit in soru["kanitlar"]:
        hedef = (kanit["doc"], kanit["sayfa"])
        ilk = next((r for r, cid in enumerate(siralama, 1) if bilgi[cid][:2] == hedef), None)
        if ilk is not None:
            hit_butce += ilk <= n_butce
            rr += 1.0 / ilk
            for k in ks:
                if ilk <= k:
                    hit[k] += 1
        ev = _parcalar(kanit["metin"])
        if ev:
            n_kapsama += 1
            en_iyi = 0.0
            for r, cid in enumerate(siralama[:max(ks)], 1):
                if cid not in chunk_parcalari:
                    chunk_parcalari[cid] = _parcalar(bilgi[cid][2])
                en_iyi = max(en_iyi, len(ev & chunk_parcalari[cid]) / len(ev))
                for k in ks:
                    if r == k:
                        kapsama[k] += en_iyi
            for k in ks:  # liste k'dan kisaysa son degeri tasi
                if len(siralama) < k:
                    kapsama[k] += en_iyi
    # soru duzeyi: tum kanitlar ilk k'da mi
    tum = {k: int(hit[k] == n_kanit) for k in ks}
    return {"n_kanit": n_kanit, "hit": hit, "hit_butce": hit_butce, "rr": rr, "tum": tum, "kapsama": kapsama,
            "n_kapsama": n_kapsama}


def _topla(istatistikler, ks):
    n_kanit = sum(i["n_kanit"] for i in istatistikler)
    n_kapsama = sum(i["n_kapsama"] for i in istatistikler)
    n_soru = len(istatistikler)
    sonuc = {"mrr": sum(i["rr"] for i in istatistikler) / n_kanit,
             "recall_butce": sum(i["hit_butce"] for i in istatistikler) / n_kanit}
    for k in ks:
        sonuc[f"recall@{k}"] = sum(i["hit"][k] for i in istatistikler) / n_kanit
        sonuc[f"soru_tum@{k}"] = sum(i["tum"][k] for i in istatistikler) / n_soru
        sonuc[f"metin_kapsama@{k}"] = (sum(i["kapsama"][k] for i in istatistikler) / n_kapsama) if n_kapsama else None
    return sonuc


def olc(siralamalar, sorular, bilgi, ks=KS, n_boot=2000, tohum=0, kilitli=False):
    # siralamalar: {soru_id: [chunk_id, ...]}. Her sorunun listesi olmak zorunda.
    # kilitli korumasi: kilitli kumedeki bir soru, kilitli=True verilmedikce reddedilir.
    kilitli_idler = set(_bolme()["kilitli"]["idler"])
    if not kilitli and any(s["id"] in kilitli_idler for s in sorular):
        raise ValueError("Kilitli test kumesi sorulari var; kilitli=True yalnizca final olcum icin (Karar 8).")
    eksik = [s["id"] for s in sorular if s["id"] not in siralamalar]
    if eksik:
        raise ValueError(f"siralamasi olmayan sorular: {eksik[:3]}...")

    ist = [_soru_istatistigi(s, siralamalar[s["id"]], bilgi, ks) for s in sorular]
    deger = _topla(ist, ks)

    # Soru bazli bootstrap: sorular (kanitlari birlikte) yerine koyarak yeniden orneklenir.
    rng = random.Random(tohum)
    ornekler = collections.defaultdict(list)
    for _ in range(n_boot):
        kume = [ist[rng.randrange(len(ist))] for _ in ist]
        for ad, v in _topla(kume, ks).items():
            if v is not None:
                ornekler[ad].append(v)
    metrikler = {}
    for ad, v in deger.items():
        o = sorted(ornekler[ad])
        ci = [o[int(0.025 * len(o))], o[min(int(0.975 * len(o)), len(o) - 1)]] if o else None
        metrikler[ad] = {"deger": v, "ci95": ci}
    return {"n_soru": len(sorular), "n_kanit": sum(i["n_kanit"] for i in ist),
            "n_boot": n_boot, "tohum": tohum, "metrikler": metrikler}


def karsilastir(siralama_a, siralama_b, sorular, bilgi, metrik="recall", k=5, n_boot=10000, tohum=0,
                kilitli=False, bilgi_b=None, kume=None):
    # Iki yontemin AYNI sorular uzerindeki farkini (B - A) olcer; fark icin %95 guven araligi
    # ESLESTIRILMIS soru-bazli bootstrap ile hesaplanir: ayni yeniden orneklenen sorular iki
    # yontemin ikisine de uygulanir. Zor/kolay sorular iki olcumde de ortak oldugundan
    # ayri ayri aralik karsilastirmasindan daha dar ve daha dogru bir aralik verir.
    # metrik: "recall" (kanit bazli @k), "soru_tum" (soru bazli @k), "mrr" veya "butce" (1000 kelime penceresi).
    # bilgi_b: B siralamasi farkli bir chunk evrenine aitse (Deney 4) onun chunk bilgisi.
    # kume: {soru_id: kume_anahtari}; verilirse bootstrap SORULAR yerine KUMELER (sirketler) uzerinden
    # yeniden orneklenir (ayni sirketin sorulari bagimli oldugundan; soru_kumeleri(sorular) ile uretilir).
    kilitli_idler = set(_bolme()["kilitli"]["idler"])
    if not kilitli and any(s["id"] in kilitli_idler for s in sorular):
        raise ValueError("Kilitli test kumesi sorulari var; kilitli=True yalnizca final olcum icin (Karar 8).")
    ist_a = [_soru_istatistigi(s, siralama_a[s["id"]], bilgi, (k,)) for s in sorular]
    ist_b = [_soru_istatistigi(s, siralama_b[s["id"]], bilgi_b or bilgi, (k,)) for s in sorular]

    def pay_payda(i):
        if metrik == "recall":
            return i["hit"][k], i["n_kanit"]
        if metrik == "soru_tum":
            return i["tum"][k], 1
        if metrik == "mrr":
            return i["rr"], i["n_kanit"]
        if metrik == "butce":
            return i["hit_butce"], i["n_kanit"]
        raise ValueError(metrik)

    def oran(liste, idx):
        pay = sum(pay_payda(liste[j])[0] for j in idx)
        payda = sum(pay_payda(liste[j])[1] for j in idx)
        return pay / payda

    tum = range(len(sorular))
    a, b = oran(ist_a, tum), oran(ist_b, tum)
    rng = random.Random(tohum)
    farklar = []
    if kume:
        gruplar = collections.defaultdict(list)
        for j, s in enumerate(sorular):
            gruplar[kume[s["id"]]].append(j)
        anahtarlar = list(gruplar)
    for _ in range(n_boot):
        if kume:
            idx = [j for g in (rng.choice(anahtarlar) for _ in anahtarlar) for j in gruplar[g]]
        else:
            idx = [rng.randrange(len(sorular)) for _ in sorular]
        farklar.append(oran(ist_b, idx) - oran(ist_a, idx))
    farklar.sort()
    ci = [farklar[int(0.025 * n_boot)], farklar[min(int(0.975 * n_boot), n_boot - 1)]]
    return {"metrik": f"{metrik}@{k}" if metrik not in ("mrr", "butce") else metrik, "a": a, "b": b, "fark": b - a, "ci95": ci,
            "anlamli": not (ci[0] <= 0 <= ci[1])}


def yazdir(sonuc, baslik=""):
    print(f"{baslik}  ({sonuc['n_soru']} soru, {sonuc['n_kanit']} kanit)")
    m = sonuc["metrikler"]
    satir = lambda ad: f"{m[ad]['deger']:.3f} [{m[ad]['ci95'][0]:.3f}-{m[ad]['ci95'][1]:.3f}]" if m[ad]["ci95"] else "-"
    print("  MRR:", satir("mrr"), "  recall@1000w:", satir("recall_butce"))
    for k in sorted({int(a.split('@')[1]) for a in m if '@' in a}):
        print(f"  @{k:<3d} recall {satir(f'recall@{k}')}  soru_tum {satir(f'soru_tum@{k}')}  metin {satir(f'metin_kapsama@{k}')}")
