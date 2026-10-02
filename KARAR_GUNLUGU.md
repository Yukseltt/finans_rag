# Karar Günlüğü

Her karar burada, gerekçesiyle ve varsa ölçümüyle kaydedilir. Amaç: *"Neden hibrit arama seçtin?"* sorusunun cevabı bir cümle
değil, bir ölçüm olmalı.

**Kayıt biçimi:** seçenekler → takaslar → karar → gerekçe → (varsa) ölçüm.
Karar değişirse eskisi silinmez, altına "revize edildi" notu düşülür.

**Durum özeti (2026-10-01, ikinci gözden geçirme sonrası)**

| # | Konu | Durum |
|---|---|---|
| 1 | Korpus ve değerlendirme seti | KAPANDI: c, sıkı sızıntı denetimiyle. FinQA ile fine-tune'ın faydası henüz sınanmadı |
| 2 | Cevap doğruluğu metriği | İlk hâli (b + a) yetersiz çıktı, **2r ile revize edildi** |
| 2r | Karar 2 revizesi | KAPANDI: katmanlı, önce deterministik; kod ve gerçekçi cevap testleri tamam (`src/cevap_metrik.py`) |
| 3 | Fine-tune modeli ve batch | İSTEĞE BAĞLI EK (Karar 11): aday listesi kapandı; batch ölçümü ve strateji yalnızca fine-tune yapılırsa gerekir |
| 4 | SEC EDGAR dahil mi | KAPANDI: kapsam dışı |
| 5 | Baseline hattı | KAPANDI: 200 kelime chunk (revize), BM25 ve dense ayrı ölçüldü |
| 6 | Kanıt eşleştirme kuralı | KAPANDI: c (sayfa ana metrik, metin ikincil) |
| 7 | Retrieval mimarisi | ÖLÇÜMLE SONUÇLANDI: dense ilk aşama + reranker (Deney 2, 3). Dense model: e5-base-v2 (Karar 12) |
| 8 | Kilitli test seti | KAPANDI: 99 geliştirme + 51 kilitli, şirket bazında. 51 soru / 11 şirket yalnızca büyük farkları ayırt eder |
| 9 | Arama uzayı | KAPANDI: başlık ortak havuz (360 belge), teşhis için tek belge |
| 10 | Okuyucu model ve bağlam koşulları | REVİZE EDİLDİ: üç koşul; okuyucu = yalnızca API, iki Gemini katı; model adları ve prompt açık |
| 11 | Proje hedefi ve fine-tune'ın yeri | KAPANDI: asıl hedef finans RAG; fine-tune isteğe bağlı ek, çekirdek sonrası |
| 12 | Final protokolde dense model | KAPANDI: e5-base-v2 (seçim nokta tahmini ve verimlilikle; farklar anlamlı değil) |
| D1 | Deney 1: belge künyesi | REDDEDİLDİ (H1 desteklenmedi) |
| D2 | Deney 2: reranker | DESTEKLENDİ (H2) |
| D3 | Deney 3: hibrit BM25 + dense | REDDEDİLDİ (H3, H3b) |
| D4 | Deney 4: chunk boyutu / örtüşme | c200 kalır (hiçbir varyant 4/4 ölçütünü geçmedi) |
| 13 | Vektör veritabanı | KAPANDI: Chroma; Deney 6b ile doğrulandı, K1'in ilk aşaması (yeniden açılmış koleksiyon) |
| D5 | Deney 5: uçtan uca RAG, cevap düzeyi (final protokol) | Ön kayıt yazıldı; okuyucu betiği ve güvenceleri hazır; henüz canlı çağrı yok |
| D6 | Deney 6: vektör veritabanı (HNSW) vs tam arama | İlk koşu başarısız (kurulum hemen sonrası), **6b geçti (3/3 yeniden açılmış koşu)**: Chroma yeniden açılmış koleksiyon olarak kullanılabilir |

Bekleyen işler (çekirdek RAG): final protokolün ön kaydı, üretim hattı (prompt, atıf, Gemini API),
cevap düzeyinde ölçüm, kilitli test ölçümü. Fine-tune isteğe bağlı ek (Karar 11). Ayrıntı: "İnceleme
notları" ve Karar 10-12.

---

## Karar 1: Korpus ve değerlendirme seti — KAPANDI

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Sadece FinanceBench (150 soru + PDF'leri) | Soru-cevap-kanıt üçlüsü hazır, retrieval doğrudan ölçülür, küçük ve hızlı | 150 soru istatistiksel olarak az, fine-tune verisi çıkmaz |
| b) Sadece FinQA (8.281 örnek) | Binlerce soru, fine-tune'a yeter, kanıt satırları işaretli | Kısa tablo-metin parçaları, "büyük belgede arama" gerçekçiliği düşük |
| c) İkisi birden: FinQA ile eğit, FinanceBench ile test et | Dağılım kaymasını bilerek ölçersin, ikisinin de gücü var | İki formatla uğraşmak gerekir (gün 2'de) |

**Karar: c**, sızıntı riski ciddi bir denetime tabi tutularak.

**Gerekçe:** Retrieval'ın zor kısmı (büyük belgede arama) yalnızca FinanceBench'te
var; FinQA'da bağlam soruya önceden verilmiş. c, eğitim ve test dağılımını bilerek
ayırır ve fine-tune'ın başka dağılıma aktarılıp aktarılmadığını ölçer.

**Sızıntı denetimi (1A'da yapılacak, ayrıntılar veriyle netleşecek):**

- Şirket-yıl kesişimi: FinQA ve FinanceBench'in şirket-yıl listeleri karşılaştırılır.
- Örtüşen örnekler eğitimden çıkarılır ya da örtüşme miktarı açıkça raporlanır.
- Yalnızca belge düzeyi değil, soru ve kanıt metni düzeyinde de benzerlik bakılır.
- Hem ham sayılar hem "örtüşenler çıkarıldıktan sonraki" sonuç raporlanır.
- Sonuç çok örtüşme gösterirse bu karar yeniden açılır.
- Bilinen sınır: ön-eğitilmiş modellerin SEC metinlerini ön-eğitimde görmüş olma
  ihtimali doğrulanamaz. Bu, README'de sınırlılık olarak belirtilir.

**Denetim sonucu (2026-09-30; `src/sizinti_kontrol.py`, `src/sizinti_metin.py`):**

| Düzey | Bulgu |
|---|---|
| Aynı sayfa / aynı metin | Yok. 150 sorunun kanıt sayfalarında FinQA ile kapsama ≥0.3 olan eşleşme 0 (en yüksek ~0.2 = SEC kapak sayfası standart metni) |
| Aynı rapor, farklı sayfa | 2 soru: General Mills 2019 (`04103`), Walmart 2018 (`06247`). FinQA'dan 22 örnek (train 17, dev 3, test 2) |
| Aynı şirket, farklı yıl | 12 şirket, 39 soru. Alan benzerliği, sızıntı sayılmadı |

Metin yöntemi pozitif kontrolle doğrulandı: General Mills 2019 10-K'nın bilinen
kaynak sayfalarında FinQA örnekleri 0.39-0.65 kapsama verdi, yanlış sayfalarda ~0.
Yöntem şirket eşleme tablosundan bağımsızdır. Doğrulama tek belgede yapıldı.

**Politika (karar):**

1. FinanceBench sorusu olan belgeyle aynı şirket-yıl raporundan gelen 22 FinQA
   örneği kullanılmaz (`sonuclar/finqa_haric.json`).
2. Sonuçlar iki satırda raporlanır: tüm sorular ve çıkarılmış hâl.
3. Şirket düzeyi örtüşme (39 soru) çıkarılmaz, alt küme olarak ayrıca raporlanır.
4. Kalan sınır: ön-eğitim sızıntısı doğrulanamaz.

Düzeltme notu: denetim sırasında çıkarılacak örnek sayısı önce 27 diye
yazılmıştı; doğrusu 22 (17 + 5).

---

## Karar 2: Cevap doğruluğu metriği — KAPANDI

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Tam eşleşme (exact match) | Tartışmasız, hızlı, tekrarlanabilir | Sayı biçimi farkı ("1.2 milyar" vs "1,200,000,000") yanlış sayılır |
| b) Sayısal tolerans (örn. %1 sapma) | Biçim farkına dayanıklı, hâlâ nesnel | Sayısal olmayan cevaplarda çalışmaz, eşik keyfi |
| c) LLM-judge | Her cevap tipine uyar | Yargıç model yanılır, kendi ailesinden cevapları kayırabilir, tekrarlanabilirliği düşük |

**Karar: b + a karışımı.** Sayısal cevaplarda tolerans, metin cevaplarda tam
eşleşme veya normalize edilmiş karşılaştırma. LLM-judge kullanılırsa insan
puanlamasıyla kalibre edilmeden tek başına raporlanmaz (30-50 örnekte elle kontrol,
uyum oranı raporlanır).

**Veriyle teyit edilecek:** 150 cevabın kaçı sayısal, %1 eşiği uygun mu, birim ve
ölçek (milyon/milyar) normalizasyonu nasıl yapılacak.

**Revize edildi (2026-10-01):** bu karar yetersiz çıktı; geliştirme kümesinde 99 cevabın yalnızca
34'ü kısa sayısal cevap. Katmanlı revize hâli için bkz. "Karar 4 kapanış ve Karar 2 revizesi"
bölümü ve `src/cevap_metrik.py`.

---

## Karar 3: Fine-tune modeli ve batch stratejisi — KISMEN KAPANDI

BGE-M3 (XLM-RoBERTa-large, ~568M parametre) T4'ün 16 GB'ına gradient
checkpointing ve FP16 ile sığar, ama **kontrastif eğitimde asıl mesele batch
size**: in-batch negatif sayısı doğrudan batch'e bağlı.

**Karar: tek modelle sınırlı kalınmaz.** BGE-M3 ana aday (daha önce başka projede
kullanıldı, aşinalık var), ama başka modeller de eklenerek çeşitlilik sağlanır.
Bu, "neden bu model?" sorusuna ölçümle cevap verir.

**Aday listesi (model kartlarından doğrulandı, 2026-10-01):**

| Model | Parametre | Boyut | Maks. uzunluk | Lisans | Not |
|---|---|---|---|---|---|
| BGE-M3 | kartta yok (~568M, XLM-R large) | 1024 | 8192 | MIT | Çok dilli; dense/sparse/ColBERT |
| bge-base-en-v1.5 | 0,1B | 768 | 512 | MIT | Sorguya "Represent this sentence for searching relevant passages:" öneki |
| e5-base-v2 | 0,1B | 768 | 512 | MIT | `query: ` / `passage: ` önekleri zorunlu |
| gte-base-en-v1.5 | 137M | 768 | 8192 | Apache 2.0 | `trust_remote_code=True` gerekli |

**Plan (karar):**

- **Sıfır atış baseline:** dört model de.
- **Fine-tune:** BGE-M3, bge-base-en-v1.5, gte-base-en-v1.5 (üç aile, farklı
  boyut ve bağlam uzunluğu). e5-base-v2 yalnızca sıfır atışta kalır.
- **Reranker (Karar 7 adım 3):** bge-reranker-v2-m3 (0,6B, Apache 2.0, maks. 512).

**gte uzak kod notu:** modelin kodu kendi deposunda değil, ayrı bir depoda
(`Alibaba-NLP/new-impl`; config'teki `auto_map`). Model sürümünü sabitlemek kodu
sabitlemez; yüklerken `code_revision` ile kod deposunun commit'i de sabitlenmeli ve
çalıştırmadan önce incelenmelidir. Model deposunun doğrulanacak son commit'i
(2026-10-01'de görülen): `a829fd0e060bb84554da0dfd354d0de0f7712b7f`.

**gte kod incelemesi (2026-10-01, sonuç: temiz):**

| | |
|---|---|
| Model deposu | `Alibaba-NLP/gte-base-en-v1.5`, commit `a829fd0e060bb84554da0dfd354d0de0f7712b7f`. Ağırlıklar `safetensors` (pickle yok) |
| Kod deposu | `Alibaba-NLP/new-impl`, commit `40ced75c3017eb27626c9d4ea981bde21a2662f4`, 2 dosya: `configuration.py` (145 satır), `modeling.py` (1418 satır) |
| sha256 | configuration.py `3411088045ffb8a9a0aa9936eae275896b39983a2ee5b08f091b44e6289e4fe4`, modeling.py `374670b416fcc82f081c9cd28b5fd61c2bd91bbe18eb4798fcc48a81f9c250a0` |
| Taranan riskli desenler | `subprocess`, `os.system/popen`, `eval/exec`, `__import__`, `pickle`, `socket`, `urllib`, `requests`, `open(`, `shutil`, `importlib`, `base64`, `ctypes`, `environ`, `torch.load`: **yok** (eşleşenler yalnızca yorumdaki bağlantılar) |
| Bağımlılıklar | `torch`, `transformers`; `xformers` isteğe bağlı (import hatasında `None`, ilgili ayar varsayılan kapalı) |

Sınır: tarama desen aramasıdır, satır satır tam okuma değil; ağ/dosya/süreç erişimi
olmaması ve ağırlıkların safetensors olması riski düşürür ama sıfırlamaz. Kod,
`dense_baseline.py` içinde her iki commit'e sabitlenmiştir.

**Her modelin öneki:** kodda modele özel sorgu/pasaj öneki tablosu tutulur ve
sonuçlarda belirtilir; yanlış önek modeli haksız yere düşürür.

**Hâlâ açık:**

- Her aday için azami batch size ölçümü (dummy veriyle 50 adım, bellek taşmadan
  çıkılabilen en büyük batch).
- (Kapandı) Chunk tanımı: kelime sayısı, aşağıda ve Karar 5'te.

| Sonuç | Karar |
|---|---|
| Batch ≥ 32 sığıyor | Modelle devam |
| Batch < 32 | Küçük model, büyük batch; muhtemelen daha iyi sonuç |

Not: gradient accumulation bu sorunu **çözmez**. Mikro-batch'ler ayrı ayrı ileri
geçişten geçer ve birbirlerini görmez; accumulation gradient istatistiğini büyük
batch'e benzetir, negatif havuzunu değil. Gerçekten daha çok negatif için
GradCache gibi bir teknik gerekir.

**Ölçüm 2: sıfır atış dense baseline (2026-10-01, `src/dense_baseline.py`)**

Geliştirme kümesi (99 soru, 127 kanıt), chunk 200 kelime, fp16, kartın önerdiği öneklerle,
başka ayar yok. Köşeli parantez: Recall@5 için %95 bootstrap aralığı. Gömme süresi yerel
RTX 2060 (6 GB).

| Yöntem | Ortak havuz R@5 | R@10 | R@50 | MRR | Tek belge R@5 | R@10 | R@50 | MRR | Gömme |
|---|---|---|---|---|---|---|---|---|---|
| BM25 | 0,031 [0,01-0,07] | 0,039 | 0,118 | 0,024 | 0,157 [0,09-0,23] | 0,205 | 0,370 | 0,130 | - |
| bge-base-en | 0,157 [0,10-0,23] | 0,260 | 0,488 | 0,108 | 0,480 [0,39-0,57] | 0,661 | 0,953 | 0,371 | 620 sn |
| e5-base | 0,213 [0,14-0,28] | 0,354 | 0,598 | 0,144 | 0,567 [0,48-0,65] | 0,709 | 0,937 | 0,339 | 627 sn |
| BGE-M3 | 0,197 [0,13-0,27] | 0,268 | 0,535 | 0,157 | 0,433 [0,34-0,52] | 0,606 | 0,906 | 0,324 | 1671 sn |
| gte-base-en | 0,189 [0,12-0,26] | 0,276 | 0,449 | 0,122 | 0,449 [0,36-0,54] | 0,567 | 0,890 | 0,358 | 919 sn |

**Bulgular:**

- Dört dense modelin hepsi BM25'in belirgin üstünde (aralıklar çakışmıyor).
- Dense modeller birbirinden **istatistiksel olarak ayırt edilemiyor** (Recall@5
  aralıkları büyük ölçüde çakışıyor). e5-base her iki uzayda sayısal olarak önde ama
  fark anlamlı değil. "e5 daha iyi" iddiası bu veriyle yapılamaz.
- BGE-M3 (en büyük, en yavaş: 1671 sn) sıfır atışta en iyi değil (tek belge R@5 en düşük
  ikinci). Fine-tune için ana aday olmasının gerekçesi sıfır atış sonucu değil, önceki
  deneyim ve fine-tune sonrası potansiyel olmalıdır; bu fine-tune ölçümüyle sınanacak.
- Tek belgede R@50 ≈ 0,89-0,95, R@5 ≈ 0,43-0,57: doğru sayfa ilk 50'de hemen hep var,
  ilk 5'te yarısı. Reranker için alan var (Karar 7, hipotez destekleniyor).
- Ortak havuzda tüm modeller düşük (R@5 ≈ 0,16-0,21): darboğaz doğru belgeyi bulmak.
  **Revize notu (2026-10-01):** bu çıkarım Deney 1'de ölçümle çürütüldü: künyesiz bile belge düzeyi
  isabet @5 = 0,5-0,8; baskın zorluk belge içinde doğru sayfayı bulmak.
- gte kodu sabit commit'lerle (model ve kod) çalıştırıldı.

---

## Karar 4: SEC EDGAR kapsama dahil mi — KAPANDI (2026-10-01): kapsam dışı

FinanceBench kendi PDF'leriyle geliyorsa EDGAR'a gerek olmayabilir. Bir haftalık
projede belirsiz kapsam en büyük risk.

**(Eski durum; 2026-10-01'de kapandı: kapsam dışı. Aşağıdaki "Karar 4 kapanış" bölümüne bkz.)**
**Karar:** şimdilik verilmedi. PDF'ler indirilip incelendikten sonra (1A) karar
verilecek. Varsayılan eğilim: PDF'ler yeterliyse EDGAR kapsam dışı, gerekçesi
README'de. EDGAR kuralları zaten doğrulandı: saniyede 10 istek, zorunlu
`User-Agent`, `Accept-Encoding: gzip, deflate`, `Host: www.sec.gov`.

---

## Karar 5: Baseline hattı — KAPANDI

Gün 1 sonunda çalışır olmalı. Bu bir "iyi sistem" değil, **sıfır noktası**.

**Karar:** sabit 512 token chunk, örtüşme yok, reranker yok. BM25 ve hazır
(fine-tune edilmemiş) yoğun retrieval **ayrı ayrı** raporlanır; birleştirilmiş
(RRF) hâli bunlardan sonra, ayrı bir ölçüm olarak eklenir. Ana sayı: Recall@5.

**Gerekçe:** Birleştirmeyi baştan yaparsak gün 3'te neyin neyi iyileştirdiğini
ayırt edemeyiz. Sonraki her karar bu sayılara karşı ölçülür.

**Revize edildi (2026-10-01):** "sabit 512 token" yerine **sabit 200 kelime** (ilk öneri 300 idi, ölçümle 200'e indi; aşağıya bkz.).
Token, her modelin tokenizer'ında farklı sayıda çıkar; token bazlı kesersek ya her
modelin chunk'ları farklı olur (karşılaştırma bozulur) ya da tek tokenizer'a göre
kesilen chunk, 512 sınırlı bir modelde sessizce kesilir. Kelime sayısı model
bağımsızdır: dört model birebir aynı chunk'ları görür.

- Sayfa sınırı: baseline'da chunk sayfa sınırını **aşmaz** (her chunk tek sayfaya ait;
  Karar 6'nın sayfa metriği belirsizlik taşımaz). Sayfa sınırını aşan yapıya saygılı
  chunking gün 2'nin karşılaştırma konusu.
- Doğrulama zorunlu: her modelin tokenizer'ıyla en uzun chunk token olarak ölçülür;
  512 sınırlı modellerde kesilen chunk çıkarsa kelime sayısı düşürülür.

**Doğrulama sonucu (`src/chunk_kontrol.py`, 2026-10-01):**

| Kelime | Chunk | bge-base-en / e5 (sınır 512) aşan | BGE-M3 / gte (sınır 8192) aşan |
|---|---|---|---|
| 300 | 117.240 | %3,13 / %3,22 | 0 |
| **200** | **163.543** | **%0,24 / %0,25** | **0** |

- 300 kelimede kesilmenin nedeni sayı yoğun tablolardır: sınırı aşan chunk'larda
  token/kelime oranı 2,14 (genel 1,38). Finans cevapları çoğunlukla bu tablolarda
  olduğundan 512 sınırlı modeller haksız dezavantaja düşerdi.
- Noktalı çizgi (içindekiler/ek listesi) sadeleştirmesi denendi: en uzun chunk 4614 →
  1124 token oldu ama sınırı aşan oranı yalnızca %3,13 → %2,97. Kazancı yok, uygulanmadı.
- Kalan sınırlılık: 200 kelimede bile ~%0,25 chunk (≈400) 512 sınırlı modellerde
  kesilir; en uzun chunk'lar noktalı çizgili listeler. Raporda belirtilir.
- Bedel: chunk sayısı ~1,4 kat arttı, chunk başına bağlam azaldı. Bu bir sıfır noktasıdır;
  chunk boyutu gün 2'de ayrıca karşılaştırılacak.

**Ölçüm 1: BM25 baseline (2026-10-01, `src/bm25_baseline.py`, geliştirme kümesi: 99 soru, 127 kanıt)**

Ayarsız: küçük harf + alfanumerik tokenizasyon, stopword/stemming yok, k1=1,5, b=0,75.
Köşeli parantez: %95 bootstrap aralığı.

| Arama uzayı | Recall@1 | Recall@5 | Recall@10 | Recall@50 | MRR |
|---|---|---|---|---|---|
| Ortak havuz (başlık) | 0,008 | **0,031** [0,007-0,066] | 0,039 | 0,118 | 0,024 |
| Tek belge (teşhis) | 0,094 | **0,157** [0,092-0,227] | 0,205 | 0,370 | 0,130 |

**Hat doğrulaması:** sorgu olarak sorunun yerine kanıt metni verilince Recall@5 = 0,974
(30 soru örneği). Chunk-sayfa eşlemesi, BM25 ve ölçüm kodu doğru; düşük sayılar hat
hatası değil, gerçek bulgudur.

**Bulgular:**

- Ortak havuzdan tek belgeye geçince Recall@5 0,031 → 0,157. Büyük kısmı "yanlış belge
  bulma" hatası; ama doğru belge verilse bile BM25 Recall@5 yalnızca 0,157.
  **Revize notu (2026-10-01):** "büyük kısmı yanlış belge bulma" iddiası Deney 1'de abartılı bulundu
  (belge isabeti @5 BM25 için 0,22 ama dense için 0,5-0,8); hata iki aşamalı ve sayfa bulma
  daha baskın.
- Örnek (Coca-Cola temettü oranı): soruda şirket adı var, doğru sayfanın metninde
  genelde yok (ad kapakta/başlıkta). BM25 3M ve PepsiCo sayfalarını getirdi.
  **Hipotez (ölçülecek):** chunk metnine belge künyesi (şirket, yıl, tür) eklemek
  ortak havuz sonuçlarını belirgin iyileştirir. Gün 2'nin ilk deneyi.
- Bu bir "iyi sistem" değil sıfır noktasıdır; sonraki her karar bu sayılara karşı ölçülür.

---

## Karar 6: Kanıt eşleştirme kuralı — KAPANDI

Bir chunk'ın "doğru" sayıldığı kural. Chunking değişse de sabit kalmalı; yoksa gün
2'deki karşılaştırmalar geçersiz olur.

**Doğrulama (PDF parse sonrası):** geliştirme kümesindeki 127 kanıtın 127'sinde,
FinanceBench'in tam sayfa metnine en çok benzeyen PDF sayfası `evidence_page_num`
ile birebir aynı. Yani sayfa numarası **0 tabanlı PDF sırası**, kayma yok. Medyan
benzerlik 1,0; 8 kanıtta <0,6 (Best Buy, Corning; tablo düzeni farkı).

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Sayfa eşleşmesi | Net, doğrulandı, chunking'ten bağımsız | Chunk sayfadan küçükse aynı sayfadaki yanlış chunk da doğru sayılır |
| b) Metin örtüşmesi | Chunk boyutundan bağımsız, ince | Eşik keyfi, tablo metni dağınık |
| c) İkisi birden | Hem sağlam hem ince | İki metrik; başlık baştan sabitlenmezse esneklik doğar |

**Karar: c.**

| | Kural |
|---|---|
| Ana metrik (başlık) | Sayfa düzeyi: getirilen chunk kanıt sayfasındaysa doğru. Tüm raporlar bununla başlar |
| İkincil metrik | Metin düzeyi: getirilen chunk'ın kanıt metninin 5-kelimelik parçalarının ne kadarını kapsadığı (0-1, sürekli) |
| Eşik | Yok; ikincil metrik ikili değil, ortalama kapsama olarak raporlanır |
| Kapsam | Geliştirme kümesi; kilitli test final ölçümde aynı iki metrikle |
| Çoklu kanıt | Her kanıt ayrı sayılır; soru düzeyinde "tüm kanıtlar bulundu mu" ayrıca raporlanır |
| Taşan chunk | Birden fazla sayfaya taşan chunk, kapsadığı tüm sayfalara ait sayılır |

**Başlığın sabitlenme nedeni:** sonuçlar bir metrikte kaybedip diğerinde kazandığında
hangisini sunacağımızı seçmek serbest kalmasın.

**Sınırlılık:** ikincil metrik tablo düzeni farkı olan kanıtlarda (8/127) retrieval
hatası olmadan düşük çıkabilir; raporda belirtilir.

---

## Karar 7: Retrieval mimarisi — ÖLÇÜMLE SONUÇLANDI (Deney 2 ve 3)

Classic, multi-query, reranking ve RAG-Fusion birbirini dışlayan "türler" değil,
hattın farklı noktalarına eklenen bileşenler.

| Teknik | Neyi çözer | Maliyet |
|---|---|---|
| Classic | Sıfır noktası | Yok |
| Reranking | Doğru chunk adaylarda ama üst sıralarda değil | Sorgu başına cross-encoder geçişi |
| Multi-query | Kötü ya da belirsiz sorgu | Her sorguda ekstra LLM çağrısı |
| RAG-Fusion | Multi-query + RRF birleştirme | Multi-query maliyeti + birleştirme |

**Karar (plan):** classic baseline, asıl sistem reranking'li. Multi-query
hata analizine bağlı opsiyonel.

**Sıra (her adım bir öncekine karşı ölçülür):**

1. Classic: BM25 ve dense ayrı (Karar 5)
2. Hibrit: BM25 + dense, RRF
3. Hibrit + reranker
4. Fine-tune edilmiş retriever (tek başına ve reranker ile)
5. Yalnızca hata analizi "sorgu ifadesi yüzünden kaçırılan" örnek gösterirse: multi-query

**Gerekçe (hipotez, ölçülecek):**

- Finans belgelerinde birbirine çok benzeyen sayfalar var; doğru sayfa adaylar
  arasında olup üst sıralara çıkamayabilir. Kanıt: Recall@50 yüksek, Recall@5
  düşük çıkması.
- FinanceBench soruları uzman yazımı ve net; multi-query'nin çözdüğü belirsiz
  sorgu problemi az beklenir.
- Multi-query, LLM çağrısı nedeniyle ölçüme rastgelelik katar ve T4/süre
  kısıtıyla çelişir.
- RAG-Fusion'ın birleştirme (RRF) kısmı, sorgu yeniden yazmadan, adım 2'de
  zaten denenir.

**Kapanış koşulu:** yukarıdaki ölçüm tablosu çıkınca karar, sayılarla revize
edilir ya da doğrulanır.

**Kapanış (2026-10-01):** adım 1-3 ölçüldü. Dense ilk aşama BM25'ten net iyi; reranker anlamlı
kazanç veriyor (Deney 2); hibrit BM25 eklemek kaybettiriyor (Deney 3). **Hat: dense ilk aşama +
bge-reranker-v2-m3.** Açık kalan: hangi dense model (dört model reranker sonrası ayırt
edilemiyor; seçim ön kayıtlı bir final protokolde yapılmalı) ve adım 4 (fine-tune). Multi-query
denenmedi (hata analizi gerekçelendirmedi).

---

## Karar 8: Kilitli test seti — KAPANDI

Sızıntının asıl riski veri setleri arasında değil, bizim test setine bakarak ayar
yapmamızdır: chunking, retrieval ve reranker kararlarını aynı 150 soruya bakarak
verirsek nihai skor seçimlerimize uyarlanmış olur ve iyimser çıkar.

**Karar:** FinanceBench baştan ikiye bölündü (`sonuclar/fb_bolme.json`):

| Küme | Soru | Kullanım |
|---|---|---|
| Geliştirme | 99 (33/33/33 soru türü) | Tüm tasarım ve ayar kararları bunun üzerinde verilir |
| Kilitli test | 51 (17/17/17), 11 şirket | Proje sonuna kadar incelenmez. En sonda **bir kez** ölçülür, sonuç ne olursa olsun raporlanır |

**Bölme kuralı:** şirket bazında (aynı şirketin belgeleri içerik paylaşır), sabit
tohum 447. 10.000 aday tohum arasından seçim yalnızca bölmenin yapısına (soru
sayısı, soru türü dengesi) baktı, hiçbir model sonucuna bakmadı.

**Takas:** kilitli test 51 soru olduğundan güven aralıkları geniştir; küçük
farklar ayırt edilemeyebilir. Bootstrap aralığıyla bu açıkça gösterilir.

**Not:** `04103` (General Mills 2019, aynı rapor sızıntısı) kilitli kümeye düştü.
Bu soru için eğitimden çıkarma politikası (Karar 1) zaten uygulanıyor.

---

## Karar 9: Arama uzayı — KAPANDI

Soru: retrieval bir soruyu cevaplarken nerede arama yapar? 150 soru 84 belgeye bağlı;
korpusta 360 belge ve 53.399 sayfa var.

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Tek belge: sorunun belgesinde ara | Retriever ve chunking kalitesini izole ölçer, hızlı | Doğru belgeyi önceden söylemiş oluruz; gerçek sistemde bu yok. ~150 sayfa içinde sayılar yüksek, yöntemler ayırt edilemez |
| b) Ortak havuz: 360 belgenin tüm sayfaları tek indeks | Gerçekçi, zor, yöntemler arası fark belirgin | Aynı şirketin farklı yılları karışır, sayılar düşük |
| c) İkisi de: b başlık, a teşhis | Hatanın "yanlış belge" mi "doğru belge yanlış sayfa" mı olduğunu gösterir | İki ölçüm; indeks küçük olduğundan ek maliyet düşük |

**Karar: c, başlık olarak b.**

**Gerekçe:**

- Gerçek sistemde belge önceden bilinmez; b'nin sayıları savunulabilir olandır.
- a, hatanın belge bulmada mı sayfa bulmada mı olduğunu ayırır.
- Başlık baştan sabitlenir (Karar 6'daki gibi): sonuçlara göre seçim yapılmaz.
- Reranker etkisi (Karar 7) b'de daha net görünür; benzer belgelerin karışması onun çözdüğü sorundur.

**Not:** FinanceBench reposunda belge listesinde olmayan 8 ek PDF vardı; indirilmedi,
korpus 360 belge. Soruların hiçbiri o 8 belgeye bağlı değil. README'de belirtildi (Durum bölümü).

---

## Deney 1: Belge künyesi (gün 2 ön deneyi) — TAMAMLANDI: H1 DESTEKLENMEDİ (5 yöntemin hiçbirinde anlamlı artış yok)

**Sonuçlardan ÖNCE yazıldı (2026-10-01).** Amaç: sonuçlar gelince ölçütü kaydırmamak.

**Gözlem:** ortak havuzda tüm yöntemler zayıf (Recall@5 ≈ 0,03-0,21), tek belgede çok
daha iyi (≈ 0,16-0,57). Örnek: "Coca Cola FY2022 …" sorusuna BM25 3M ve PepsiCo sayfalarını
getirdi; doğru sayfanın metninde şirket adı yoktu.

**Müdahale:** her chunk'ın başına belge künyesi eklenir (`src/kunye.py`), ör.
`"3M. 10-K annual report, fiscal year 2018."`. Künye yalnızca belge meta verisinden
(şirket, tür, dönem) ve belge adından (çeyrek, tarih) üretilir; soru bilgisi kullanılmaz.
Gerçek bir sistemde de her belge için mevcut bilgidir (sızıntı yok). Künye yalnızca
gömme/indeks metnine eklenir; metin kapsama metriği orijinal chunk metniyle ölçülür.
Chunk'ın kendisi (200 kelime) değişmez, künye ek ~15 token getirir.

**Format tek ve sabit;** geliştirme sonuçlarına bakarak ayarlanmayacak (başka biçimler
denenmeyecek, bu geliştirme kümesine uyarlamak olurdu).

**Hipotez H1:** künye **ortak havuz** Recall@5'ini artırır.
**Kontrol hipotezi H0-tek:** künye **tek belge** Recall@5'ini değiştirmez (künye aynı
belgenin tüm chunk'larında aynı, belge içi sıralamayı ayırt etmez).

**Başarı ölçütü (sabit):**

1. Ortak havuz Recall@5'te, eşleştirilmiş bootstrap farkının (`degerlendir.karsilastir`,
   10.000 tekrar, %95) aralığı 0'ı içermeyen pozitif fark: 5 yöntemden (BM25 + 4 dense)
   **en az 4'ünde**.
2. Kontrol: tek belge Recall@5'te |fark| < 0,05 ve anlamsız. Bu sağlanmazsa künye başka bir
   mekanizmayla etki ediyor demektir ve sonuç ihtiyatla yorumlanır.

**Raporlama:** 5 yöntem × 2 arama uzayı, fark ve aralıklarıyla, sonuç ne olursa olsun.
10 karşılaştırma yapıldığından tek bir "anlamlı" sonuç tek başına güçlü kanıt sayılmaz;
ölçüt 5 yöntemin çoğunda tutarlılık arar.

**Maliyet:** dört modelin yeniden gömülmesi (~64 dk yerel GPU) + BM25 (~3 dk, CPU).

**SONUÇ (2026-10-01; BM25 + 4 dense model, hepsi bitti)**

Recall@5, B = künyeli, A = künyesiz; fark için eşleştirilmiş bootstrap %95 aralığı
(`degerlendir.karsilastir`, 10.000 tekrar):

| Yöntem | Ortak havuz A → B | Fark [aralık] | Tek belge A → B | Fark [aralık] |
|---|---|---|---|---|
| BM25 | 0,031 → 0,055 | +0,024 [0,000; +0,054] | 0,157 → 0,150 | -0,008 [-0,034; +0,017] |
| bge-base-en | 0,157 → 0,173 | +0,016 [-0,047; +0,078] | 0,480 → 0,417 | -0,063 [-0,153; +0,033] |
| e5-base | 0,213 → 0,126 | **-0,087 [-0,157; -0,016]** | 0,567 → 0,268 | **-0,299 [-0,396; -0,203]** |
| gte-base-en | 0,189 → 0,157 | -0,031 [-0,102; +0,041] | 0,449 → 0,441 | -0,008 [-0,110; +0,098] |
| BGE-M3 | 0,197 → 0,252 | +0,055 [-0,008; +0,125] | 0,433 → 0,425 | -0,008 [-0,083; +0,068] |

**Ön kayıtlı ölçütlere göre:**

1. **H1 desteklenmedi.** Ortak havuzda 5 yöntemin hiçbirinde anlamlı pozitif fark yok
   (ölçüt ≥4/5 idi, sonuç 0/5); e5'te anlamlı **negatif** fark. BGE-M3 en büyük sayısal
   artışı verdi (+0,055) ama aralığı 0'ı içeriyor.
2. **Kontrol kısmen tutmadı.** Tek belgede BM25, gte ve BGE-M3 için fark anlamsız ve |fark|
   < 0,05 (beklendiği gibi); ama e5 (R@5 0,567 → 0,268, anlamlı) ve bge-base (R@50 -0,118,
   anlamlı) belirgin kötüleşti. Künye bazı modellerde belge içi sıralamayı bozuyor.

**Ek analiz: belge düzeyi isabet** (`src/belge_isabeti.py`; ortak havuzda ilk k chunk'ın
en az biri doğru belgeden mi):

| Yöntem | Künyesiz @5 | Künyeli @5 | Künyesiz @50 | Künyeli @50 |
|---|---|---|---|---|
| BM25 | 0,222 | 0,293 | 0,646 | 0,727 |
| bge-base-en | 0,495 | 0,586 | 0,919 | 0,980 |
| e5-base | 0,697 | 0,818 | 0,970 | 0,990 |
| gte-base-en | 0,586 | 0,626 | 0,929 | 0,980 |
| bge-m3 | 0,808 | 0,859 | 0,970 | 0,980 |

**Yorum (ölçülmüş olanla hipotez ayrı):**

- Ölçüldü: künye **belgeyi bulmayı iyileştiriyor** (5/5 yöntemde belge isabeti @5 artıyor)
  ama **belge içinde doğru sayfayı bulmayı bozuyor** (özellikle e5); net etki sıfır ya da negatif.
- Ölçüldü: önceki "ortak havuzdaki darboğaz doğru belgeyi bulmak" iddiası **yanlıştı ya da
  abartılıydı.** Künyesiz bile belge isabeti @5 = 0,5-0,8 (e5: 0,70; BGE-M3: 0,81), buna rağmen
  sayfa Recall@5 yalnızca 0,16-0,21. Baskın zorluk **belge içinde doğru sayfayı bulmak**.
- Hipotez (ölçülmedi): künye aynı belgenin tüm chunk'larını birbirine benzetip belge içi
  ayırt ediciliği düşürüyor; ortalama-havuzlamalı e5'in en çok etkilenmesi bununla uyumlu ama
  kanıtlanmadı. Künyenin token sınırını aşan chunk oranına etkisi ölçülmedi.
- Sonuç: künyeyi chunk metnine eklemek **benimsenmez.** Belge bulma ve sayfa bulma
  ayrı aşamalar olarak ele alınabilir (iki aşamalı arama / belge yönlendirme); bu yeni bir
  hipotez olup ayrı ön kayıtla denenmelidir, bu sonuca göre ayarlanmış sayılmaz.

---

## Deney 2: Reranker (Karar 7, adım 3) — TAMAMLANDI: H2 DESTEKLENDİ

**Sonuçlardan ÖNCE yazıldı (2026-10-01).**

**Gözlem:** tek belgede Recall@50 ≈ 0,89-0,95 iken Recall@5 ≈ 0,43-0,57; ortak havuzda
belge düzeyi isabet @50 ≈ 0,92-0,97 ama sayfa Recall@5 ≈ 0,16-0,21. Doğru sayfa aday
kümesinde ama üst sıralarda değil: reranker'ın çözdüğü durum.

**Müdahale:** ilk aşama sıralamasının ilk **50** adayı `BAAI/bge-reranker-v2-m3` (0,6B,
Apache 2.0, maks. 512 token) ile yeniden sıralanır. Girdi: (soru, orijinal chunk metni);
künye yok (Deney 1 sonucu), fine-tune yok, ayar yok. 50'nin ötesindeki adaylar orijinal
sırasıyla listenin sonunda kalır. Derinlik 50, sonuçlara bakmadan sabit.
İlk aşamalar: künyesiz BM25 ve 4 dense model (5 yöntem), iki arama uzayında.

**Hipotez H2:** reranker Recall@5'i artırır.

**Başarı ölçütü (sabit):** eşleştirilmiş bootstrap farkının (%95, 10.000 tekrar) aralığı
0'ı içermeyen pozitif fark, **her iki uzayda ayrı ayrı**, 5 ilk aşamanın **en az 4'ünde**.
Yani ortak havuzda ≥4/5 ve tek belgede ≥4/5.

**Not:** derinlik 50 olduğundan Recall@50 reranker'la değişmez (aynı küme, farklı sıra);
Recall@50 ve üstü bu deneyde bilgi vermez. BM25'in ortak havuz Recall@50'si düşük
(0,118); o ilk aşamada reranker'ın tavanı düşüktür, bu bilinen bir sınırdır.

**Raporlama:** 5 yöntem × 2 uzay, fark ve aralıklarıyla, sonuç ne olursa olsun. Ek olarak
reranker maliyeti (soru başına çift sayısı, süre) raporlanır.

**SONUÇ (2026-10-01; `src/rerank.py`, bge-reranker-v2-m3, derinlik 50, geliştirme kümesi)**

Recall@5, A = ilk aşama, B = reranker sonrası; fark için eşleştirilmiş bootstrap %95
aralığı (10.000 tekrar). `*` = aralık 0'ı içermiyor.

| İlk aşama | Ortak havuz A → B | Fark [aralık] | Tek belge A → B | Fark [aralık] |
|---|---|---|---|---|
| BM25 | 0,031 → 0,087 | +0,055 [+0,016; +0,100] * | 0,157 → 0,268 | +0,110 [+0,041; +0,186] * |
| bge-base-en | 0,157 → 0,354 | +0,197 [+0,117; +0,283] * | 0,480 → 0,630 | +0,150 [+0,062; +0,240] * |
| e5-base | 0,213 → 0,394 | +0,181 [+0,103; +0,266] * | 0,567 → 0,630 | +0,063 [-0,023; +0,156] |
| gte-base-en | 0,189 → 0,323 | +0,134 [+0,061; +0,212] * | 0,449 → 0,630 | +0,181 [+0,096; +0,268] * |
| BGE-M3 | 0,197 → 0,323 | +0,126 [+0,060; +0,197] * | 0,433 → 0,606 | +0,173 [+0,062; +0,283] * |

**Ön kayıtlı ölçüt:** ortak havuzda 5/5 (≥4 gerekliydi), tek belgede 4/5 → **sağlandı, H2 desteklendi.**
MRR de her yöntemde ve iki uzayda anlamlı arttı.

**Gözlemler:**

- Reranker sonrası tek belge Recall@5 dense modellerde ~0,61-0,63'e yaklaştı (ilk aşamada
  0,43-0,57). İlk aşama modelleri arasındaki fark büyük ölçüde silindi: bu ölçekte
  belirleyici bileşen embedding modeli değil reranker.
- e5-base (ilk aşamada en güçlü, tek belge R@5 0,567) tek belgede anlamlı kazanmadı; yukarı
  çıkabileceği alan zaten dardı.
- Hâlâ düşük: ortak havuz R@5 en iyi 0,394; tek belge ~0,63, oysa tek belge R@50 ~0,9.
  Reranker boşluğun yalnızca bir kısmını kapatıyor.
- BM25 ilk aşama olarak reranker ile de en zayıf (ortak havuz R@50 0,118, aday kümede doğru
  sayfa çoğu zaman yok): tavan ilk aşama tarafından belirleniyor.
- Maliyet: 26.193 benzersiz çift 364 sn (72 çift/sn, yerel RTX 2060, fp16); soru başına 50
  çift ≈ 0,7 sn ek gecikme.

**Sınırlar:** 99 soru, tek kümede ölçüm (kilitli test değil); 10 karşılaştırma yapıldı (5
yöntem × 2 uzay), ama sonuç tek bir anlamlı fark değil tutarlı bir örüntü (10/10 yönde
pozitif, 9/10 anlamlı). Reranker fine-tune edilmedi, ayarlanmadı.

---

## Deney 3: Hibrit arama, BM25 + dense (Karar 7, adım 2) — TAMAMLANDI: H3 ve H3b DESTEKLENMEDİ

**Sonuçlardan ÖNCE yazıldı (2026-10-01).**

**Gözlem:** BM25 bu veride dense'ten çok zayıf (ortak havuz R@5 0,03; en iyi dense 0,21).
Sözcük eşleşmesinin dense'in kaçırdığı sayfaları tamamlayıp tamamlamadığı bilinmiyor.

**Müdahale:** Reciprocal Rank Fusion (RRF): skor = Σ 1/(k + sıra), **k = 60** (yaygın
varsayılan; ayarlanmayacak). BM25 sıralaması ile her bir dense modelin sıralaması
birleştirilir (4 hibrit), birleşik ilk 100 tutulur. Künyesiz. Her iki arama uzayında,
geliştirme kümesinde.

Ek, ölçüte dahil olmayan keşif varyantı: `rrf_hepsi` = BM25 + 4 dense (5 liste).

**H3:** hibrit, tek başına dense'e göre Recall@5'i artırır.
**Ölçüt 1 (sabit):** eşleştirilmiş bootstrap farkı (%95, 10.000 tekrar) 0'ı içermeyen
pozitif; **her uzayda ayrı ayrı**, 4 hibritin **en az 3'ünde**.

**H3b:** hibrit + reranker (derinlik 50, Deney 2 ile aynı), dense + reranker'a göre
Recall@5'i artırır.
**Ölçüt 2 (sabit):** aynı biçimde, her uzayda ayrı ayrı, 4 hibritin en az 3'ünde anlamlı
pozitif fark.

**Açık beklenti (tahmin, ölçülmedi):** BM25 çok zayıf olduğundan hibritin kazancının küçük
ya da anlamsız olmasını, hatta zayıf BM25 listesinin sıralamayı bozmasını bekliyorum.
Ölçüt bu beklentiye göre değil, yukarıdaki sabit eşiğe göre değerlendirilecek.

**Raporlama:** 4 hibrit + keşif varyantı × 2 uzay, fark ve aralıklarıyla, sonuç ne olursa
olsun. Çoklu karşılaştırma uyarısı: ölçütler tutarlılık arar (≥3/4).

**SONUÇ (2026-10-01; `src/hibrit.py`, RRF k=60, geliştirme kümesi)**

Recall@5; A = dense tek başına, B = hibrit (BM25 + o dense); fark için eşleştirilmiş
bootstrap %95 aralığı. `*` = aralık 0'ı içermiyor.

**H3: hibrit vs dense (ilk aşama)**

| Dense | Ortak havuz A → B | Fark [aralık] | Tek belge A → B | Fark [aralık] |
|---|---|---|---|---|
| bge-base-en | 0,157 → 0,094 | -0,063 [-0,114; -0,016] * | 0,480 → 0,244 | -0,236 [-0,333; -0,142] * |
| e5-base | 0,213 → 0,142 | -0,071 [-0,137; -0,008] * | 0,567 → 0,244 | -0,323 [-0,417; -0,230] * |
| gte-base-en | 0,189 → 0,118 | -0,071 [-0,136; -0,008] * | 0,449 → 0,205 | -0,244 [-0,336; -0,156] * |
| BGE-M3 | 0,197 → 0,134 | -0,063 [-0,120; -0,008] * | 0,433 → 0,213 | -0,220 [-0,304; -0,138] * |

**H3b: hibrit + reranker vs dense + reranker**

| Dense | Ortak havuz A → B | Fark [aralık] | Tek belge A → B | Fark [aralık] |
|---|---|---|---|---|
| bge-base-en | 0,354 → 0,315 | -0,039 [-0,086; +0,007] | 0,630 → 0,575 | -0,055 [-0,109; -0,008] * |
| e5-base | 0,394 → 0,315 | -0,079 [-0,134; -0,031] * | 0,630 → 0,583 | -0,047 [-0,102; +0,007] |
| gte-base-en | 0,323 → 0,291 | -0,031 [-0,079; +0,016] | 0,630 → 0,512 | -0,118 [-0,185; -0,057] * |
| BGE-M3 | 0,323 → 0,307 | -0,016 [-0,065; +0,032] | 0,606 → 0,504 | -0,102 [-0,163; -0,051] * |

**Ön kayıtlı ölçütler:** Ölçüt 1: 0/4 ortak, 0/4 tek (≥3 gerekliydi). Ölçüt 2: 0/4 ortak,
0/4 tek. **İkisi de sağlanmadı; H3 ve H3b desteklenmedi.** Hibrit dense'ten anlamlı
biçimde **kötü** (ilk aşamada 8/8 karşılaştırmada anlamlı negatif; reranker sonrası 4/8
anlamlı negatif, kalanı anlamsız).

Ön kayıttaki açık beklenti ("zayıf BM25 sıralamayı bozabilir") doğrulandı.

**Keşif (ön kayıt dışı, post hoc; kanıt değil yön göstergesi):** `rrf_hepsi` (BM25 + 4
dense) vs en iyi tek dense (e5-base), R@5: ortak ilk aşama 0,213 → 0,283 (+0,071
[0,000; +0,143], anlamsız); ortak +rerank 0,394 → 0,402 (anlamsız); tek ilk aşama 0,567 →
0,394 (anlamlı kötü); tek +rerank 0,630 → 0,638 (anlamsız). Reranker sonrası fark yok.

**Hipotez (ölçülmedi):** RRF eşit ağırlık verdiğinden belirgin biçimde zayıf BM25 listesi
(tek belge R@5 0,157 vs dense 0,43-0,57) sıralamayı aşağı çekiyor. Ağırlıklı birleştirme
ya da yalnızca dense modellerin birleşimi ayrı ön kayıtlı deney olarak denenebilir; bu
sonuca göre ayarlanmış sayılmaz.

**Karar 7'ye etki:** mimari adımları ölçümle şöyle sonuçlandı: classic dense → +reranker
(**anlamlı kazanç**) ; hibrit BM25 eklemek **kaybettiriyor**. Önerilen hat: dense ilk
aşama + reranker. Fine-tune (adım 4) bu hat üzerinde ölçülecek.

---

## Denetim notları (2026-10-01, fine-tune öncesi gözden geçirme)

**Hata analizi** (`src/hata_analizi.py`, e5 + reranker, geliştirme kümesi, Recall@5):

| | Ortak havuz | Tek belge |
|---|---|---|
| metrics-generated | 27/49 | 35/49 |
| novel-generated | 14/36 | 23/36 |
| domain-relevant | 9/42 | 22/42 |
| 1 kanıtlı soru | 34/75 | 54/75 |
| 2 kanıtlı soru | 16/40 | 26/40 |
| 3+ kanıtlı soru | **0/12** | **0/12** |
| Kanıt sırası ≤5 / 6-10 / 11-50 / 51-100 / yok | 50 / 13 / 13 / 18 / 33 | 80 / 18 / 21 / 5 / 3 |

- En zor tür domain-relevant. 3+ kanıtlı sorularda R@5 = 0/12, ama 12 kanıt çok az soruya
  ait olabilir; örneklem küçük, sonuç yönlendirici.
  **Düzeltme (2026-10-01):** bu 12 kanıt yalnızca **4 soruya** ait ve ikisinde aynı sayfa iki kez
  kanıt olarak sayılmış (CVS s.172, MGM s.3); bağımsız sayfa sayısı 10. "0/12" bu yüzden
  kesin bir bulgu değil, 4 sorunun gözlemi.
- Ortak havuzda kanıtların ~%40'ı ilk 50 dışında (ilk aşama tavanı); tek belgede çoğu
  kaçırma yakın kaçırma (6-50. sıra).
- Kanıt metnindeki rakam oranı bulunanlarda 0,150, kaçırılanlarda 0,152: "tablolar zor
  olduğu için kaçırıyoruz" hipotezi **desteklenmedi**.

**Tekrarlanabilirlik:** bge-base-en gömmesi aynı oturumda iki kez bire bir aynı (fp16, GPU).
Önbellekteki gömüyle (farklı batch bileşimi) en büyük fark 0,0005, minimum kosinüs 0,9991:
ihmal edilebilir. Bootstrap tohumları sabit. Sonuçların üretildiği ortam
`sonuclar/ortam.json` (`src/ortam_kaydi.py`). `requirements.txt` gerçekte kullanılan
paketlere indirildi (kullanılmayan faiss-cpu, datasets, scipy, pandas, python-dotenv
çıkarıldı; torch yerelde 2.7.0+cu118 idi, 2.5.1 değil).

**Karar 2 revizesi gerekli (bulgu):** geliştirme kümesinde 99 cevabın 86'sı rakam içeriyor
ama yalnızca 34'ü kısa (<40 karakter) sayısal cevap; medyan cevap uzunluğu 65 karakter.
Çoğu cevap serbest metin ("No, the company is managing its CAPEX … which is evident from
…"). Karar 2'deki "sayısal tolerans + normalize eşleşme" cevapların yaklaşık üçte birini
kapsar; kalanı için LLM-judge (insan kalibrasyonlu) ya da anahtar-olgu kontrolü gerekir.
Cevap üretimi öncesinde yeniden karara bağlanacak (karar verildi: "Karar 2 revizesi" bölümü).

**Karar 4 (EDGAR):** PDF'ler 150 sorunun tüm belgelerini kapsıyor ve 360/360 belge parse
edildi; EDGAR'a ihtiyaç görünmüyor. Kapatılması kullanıcı onayına bırakıldı (sonra kapandı: kapsam dışı).

**Değerlendirme sınırı (not):** metrik tek bir gold sayfaya bakar; aynı bilgi başka bir
sayfada da geçiyorsa (örneğin 10-K'da özet ve ayrıntılı tablo) o sayfayı getirmek hata
sayılır. Sayfa Recall'u bu yüzden gerçek retrieval başarısını olduğundan düşük gösterebilir;
cevap düzeyi ölçümü (Karar 2) bunu tamamlar.

---

## Deney 4: Chunk boyutu ve örtüşme (gün 2) — TAMAMLANDI: H4 DESTEKLENMEDİ, c200 kalır

**Sonuçlardan ÖNCE yazıldı (2026-10-01).** Varsayım: kullanıcı tasarımı itirazsız onayladı
(üç onay sorusuna ayrıca yanıt vermedi, Karar 2/4'ün ertelenmesiyle devam etmemizi istedi).

**Gözlem:** tek belgede çoğu kaçırma yakın kaçırma (kanıt sayfası 6-50. sırada: 39 / 127);
chunk tasarımı hiç araştırılmadı, yalnızca 200 kelimelik baz kullanıldı.

**Metrik tuzağı:** Recall@k "ilk k chunk" demek; chunk büyüdükçe k chunk daha çok metin demektir
ve üretimde daha çok bağlam tüketir. Chunk sayısına göre kıyaslarsak büyük chunk haksız
kazanır. **Ana metrik eşit bağlam bütçesi:** sıralı chunk'lar, birikmiş kelime sayısı 1000'e
ulaşana kadar alınır (chunk, başlamadan önce birikim < 1000 ise dahil edilir; tam 200
kelimelik chunk'larda bu tam 5 chunk = Recall@5). Kanıt sayfasından chunk bu pencerede mi
= **Recall@1000w**.

**Varyantlar (sabit, hepsi sayfa sınırını aşmaz):**

| Etiket | Chunk | Rerank derinliği (≈10.000 kelime aday) |
|---|---|---|
| c100 | 100 kelime, örtüşme yok | 100 |
| **c200 (baz)** | 200 kelime, örtüşme yok | 50 |
| c200o50 | 200 kelime, 50 kelime örtüşme | 50 |
| c300 | 300 kelime, örtüşme yok | 33 |

Sayfa başına tek chunk **bilerek dışarıda**: ~700 token, 512 sınırlı modellerde ve
reranker'da kesilir, adil kıyas olmaz.

**Modeller:** bge-base-en ve e5-base (künyesiz), ilk aşama ve ilk aşama + reranker
(bge-reranker-v2-m3, Deney 2 ile aynı). Her iki arama uzayı, geliştirme kümesi.

**Hipotez H4:** en az bir varyant, C200'e göre eşit bütçe Recall'unu artırır.
**Ölçüt (sabit):** bir varyant, **reranker sonrası** Recall@1000w'de C200'ü eşleştirilmiş
bootstrap (%95, 10.000 tekrar) ile **4/4** karşılaştırmada (2 model × 2 uzay) anlamlı
pozitif farkla geçerse kazanır. Aksi hâlde C200 kalır. Üç varyant birden denendiği için
ölçüt bilerek sıkıdır.

**Açık beklenti (tahmin, ölçülmedi):** hiçbir varyantın 4/4 ölçütünü geçmesini beklemiyorum;
C200 kalacak diye tahmin ediyorum. Ölçüt bu tahmine göre değil, sabit eşiğe göre değerlendirilir.

**Ek raporlama (ölçüte dahil değil):** chunk sayısı, 512 sınırlı modellerde kesilen chunk
oranı, Recall@k (chunk sayısı), ilk aşama bütçe Recall'u, MRR, metin kapsama (büyük chunk'a
yanlı olduğu bilinir), gömme süresi.

**SONUÇ (2026-10-01; `src/chunk_deneyi.py`; bge-base-en ve e5-base, reranker bge-reranker-v2-m3)**

**Ana metrik: Recall@1000w, reranker sonrası;** A = baz c200, B = varyant; fark için eşleştirilmiş
bootstrap %95 aralığı. `*` = aralık 0'ı içermiyor.

| Varyant | Model | Ortak havuz A → B | Fark [aralık] | Tek belge A → B | Fark [aralık] |
|---|---|---|---|---|---|
| c100 | bge-base-en | 0,362 → 0,409 | +0,047 [-0,016; +0,113] | 0,646 → 0,740 | +0,094 [+0,023; +0,174] * |
| c100 | e5-base | 0,409 → 0,441 | +0,031 [-0,032; +0,098] | 0,646 → 0,740 | +0,094 [+0,030; +0,168] * |
| c200o50 | bge-base-en | 0,362 → 0,346 | -0,016 [-0,055; +0,023] | 0,646 → 0,630 | -0,016 [-0,060; +0,030] |
| c200o50 | e5-base | 0,409 → 0,409 | 0,000 [-0,038; +0,040] | 0,646 → 0,622 | -0,024 [-0,070; +0,023] |
| c300 | bge-base-en | 0,362 → 0,315 | -0,047 [-0,095; 0,000] | 0,646 → 0,669 | +0,024 [-0,043; +0,090] |
| c300 | e5-base | 0,409 → 0,417 | +0,008 [-0,061; +0,073] | 0,646 → 0,646 | 0,000 [-0,067; +0,070] |

**Ön kayıtlı ölçüt (4/4 anlamlı pozitif):** c100 2/4, c200o50 0/4, c300 0/4. **Hiçbir varyant
kazanmadı; baz c200 kalır.** Ön kayıttaki tahmin ("C200 kalacak") doğrulandı.

**İlk aşama (reranker öncesi) Recall@1000w:** c100 dört karşılaştırmanın dördünde anlamlı arttı
(+0,079, +0,189, +0,094, +0,142); c300 e5'te anlamlı düştü (-0,079, -0,102); c200o50'de anlamlı
fark yok. Reranker sonrası c100 avantajı yarıya indi ve ortak havuzda anlamsızlaştı.

**Ek (ölçüt dışı) bilgiler:**

| Varyant | Chunk sayısı | 512'de kesilen (bge/e5) | Gömme süresi (bge/e5) | Rerank çift/sn |
|---|---|---|---|---|
| c100 | 299.169 | %0,03 / %0,04 | 617 / 629 sn | 134 |
| c200 (baz) | 163.543 | %0,24 / %0,25 | 620 / 627 sn | 72 |
| c200o50 | 191.739 | %0,26 / %0,27 | 777 / 783 sn | 75 |
| c300 | 117.240 | %3,13 / %3,22 | 534 / 536 sn | 60 |

**Yorumlama kontrolü (post hoc, betimsel, ölçüt değil; `src/butce_kapsama.py`):** sayfa düzeyi
bütçe Recall'u, eşit kelime bütçesinde küçük chunk'ın daha çok FARKLI sayfadan parça getirmesinden
yapısal fayda görebilir. Bütçe penceresindeki chunk'ların BİRLEŞİMİNİN kanıt metnini
kapsama oranı (reranker sonrası):

| Varyant | Tek belge sayfa isabeti (bge / e5) | Tek belge birleşim kapsama (bge / e5) | Ort. farklı sayfa (tek belge) |
|---|---|---|---|
| c100 | 0,740 / 0,740 | **0,418 / 0,412** | 8,8 |
| c200 (baz) | 0,646 / 0,646 | 0,527 / 0,534 | 5,3 |
| c200o50 | 0,630 / 0,622 | 0,535 / 0,527 | 5,0 |
| c300 | 0,669 / 0,646 | **0,608 / 0,589** | 4,1 |

- **c100'ün sayfa isabeti kazancı, kanıt metninin kapsanmasında kayıp pahasına geliyor:**
  daha çok sayfaya yayılıyor (8,8 vs 5,3 sayfa), kanıt metninin daha azını içeriyor
  (0,42 vs 0,53). Sayfa metriği tek başına bu varyantı olduğundan iyi gösteriyor.
- **c300 ters yönde:** sayfa isabeti benzer, ama kanıt metninin daha çoğunu getiriyor
  (0,60 vs 0,53 tek belge); bedeli %3 kesilme ve ortak havuzda sayfa isabetinde düşüş eğilimi.
- Bu kapsama farkları için anlamlılık testi yapılmadı (betimsel); örtüşme (c200o50) iki
  metrikte de baz ile aynı: fayda yok.

**Sonuç:** üç varyant da baz'ı ön kayıtlı ölçütle geçemedi; **c200 korunur.** Önemli bulgu:
sayfa isabeti ve kanıt kapsaması **farklı yönlere işaret ediyor** (c100 ve c300). Hangisinin
önemli olduğunu, üretilen cevabın doğruluğu belirler (Karar 2); chunk boyutu için nihai
yargı cevap düzeyinde ölçümle verilmelidir. Bu, Karar 2'nin ertelenmiş revizesini daha da
öncelikli kılıyor.

**Sınırlar:** iki model, geliştirme kümesi (99 soru); c100/c300 farkları ölçüte takıldığı için
"baz kalır" kararı sağlam, ama c100'ün ayrı bir hat olarak (ör. küçük chunk ilk aşama + büyük
bağlam penceresi) değeri bu deneyle test edilmedi.

---

## Karar 4 kapanış ve Karar 2 revizesi (2026-10-01)

**Karar 4 — KAPANDI: EDGAR kapsam dışı.** Gerekçe: FinanceBench PDF'leri 150 sorunun tüm
belgelerini kapsıyor, 360/360 belge parse edildi, sorular zaten bu PDF'lerden yazılmış.
EDGAR ek bir istemci, hız sınırı yönetimi ve doğrulama yüzeyi getirirdi.

**Karar 2 revizesi — KAPANDI (yapı):** geliştirme kümesinde 99 cevabın türleri:

| Tür | Adet | Nerede |
|---|---|---|
| Salt sayı | 34 | neredeyse tamamı metrics-generated |
| Evet/hayır + açıklama | 30 | domain-relevant, novel-generated |
| Metin içinde sayı | 28 | domain-relevant, novel-generated |
| Serbest metin (sayı yok) | 7 | çoğunlukla domain-relevant |

Orijinal Karar 2 ("sayısal tolerans + normalize eşleşme") cevapların yaklaşık üçte birini
kapsıyordu. **Revize (karar): katmanlı, önce deterministik metrik:**

| Tür | Metrik |
|---|---|
| Salt sayı | Sayıyı ayrıştır, birim/ölçek normalize et; **gold'un gösterdiği hassasiyette eşleşme** (birincil) ve %1 göreli tolerans (ikincil); ikisi de raporlanır |
| Evet/hayır + açıklama | **Hüküm** (Yes/No) tam eşleşme; açıklama kalitesi ikincil |
| Metin içinde sayı | Gold'daki anahtar sayıların cevapta bulunması |
| Serbest metin | LLM-yargıç, 30-50 örnekte insan kalibrasyonlu; yalnızca birkaç soru |

Yargıç kullanılırsa okuyucudan farklı bir model olmalı (kendi çıktısını kayırma riski),
uyum oranı (insanla) raporlanır. %65'e yakın cevap yargıç olmadan ölçülür.

## Karar 10: Okuyucu model ve bağlam koşulları — KISMEN KAPANDI

**Üç bağlam koşulu (karar, aynı soru ve prompt ile):**

1. **Kapalı kitap:** bağlam yok.
2. **Getirilen bağlam:** hat (dense + reranker, c200) ilk 1000 kelime.
3. **Oracle bağlam:** gold kanıt sayfası(ları).

Ayrıştırma: oracle − getirilen = retrieval kaybı; oracle ve 100 arası = okuyucu kaybı;
getirilen − kapalı kitap = retrieval'ın kattığı değer. Chunk seçimi (c100/c200/c300) ve
fine-tune faydası da cevap düzeyinde bu çerçevede sınanır.

**Okuyucu LLM (karar):** iki okuyucu, aynı prompt ve bağlamlarla:

- **Yerel açık model:** kullanıcının M4 MacBook Air (16 GB birleşik bellek) makinesinde;
  önceki llama deneyimi var. Fizibilite (hangi model, hangi çalışma ortamı, bağlam uzunluğu,
  hız) çalıştırmadan önce doğrulanacak.
- **Gemini:** kullanıcının mevcut kredileriyle. Model adı ve sürümü, güncel dokümantasyondan
  doğrulanıp sabitlenecek (tekrarlanabilirlik). Verinin API'ye gönderilmesi (FinanceBench
  CC-BY-NC) kullanıcının değerlendirmesinde; API anahtarı depoya girmez (ortam değişkeni).

**Gerekçe:** iki farklı okuyucu proje çeşitliliği sağlar ve "retrieval sonuçları okuyucu modelden
bağımsız mı?" sorusunu cevaplar. Yerel model tam tekrarlanabilir açık yığın hikâyesi verir,
Gemini daha güçlü bir üst sınır sunar.

**Hâlâ açık:** model adları ve sürümleri, prompt, çalışma ortamı (Ollama / llama.cpp / MLX),
sıcaklık (0 öneriliyor), bağlam penceresi, yargıç modeli seçimi.

---

## İnceleme notları (2026-10-01, ikinci gözden geçirme)

Kapsam: günlüğün tamamı, README, ölçüm / bölme / cevap metriği / dense retrieval kodu okundu;
dört şüphe veriyle sınandı. Bu bölüm bulguları ve yapılan düzeltmeleri kaydeder.

**1. Cevap metriği gerçek model cevaplarında hatalıydı (düzeltildi).** İlk sürümün testi yalnızca
"gold'u tahmin olarak ver, kabul etmeli" idi; iki taraf aynı hatayla ayrıştırıldığı için gerçek
model biçimlerindeki hataları göremiyordu. Gerçekçi cevaplarla yedi vakanın yedisi yanlış sayıldı:

| Vaka | Kök neden | Çözüm |
|---|---|---|
| `0.96x` → 0 | Sondaki sözcük sınırı sayıyı ondalıkta bölüyordu | Sayıya bitişik harf/rakam olmasın, `x` çarpan kabul |
| `($1.8 bn)` → negatif | Açılış parantezi eksi sayılıyordu | Parantez eksi değil (gold'larda muhasebe negatifi yok) |
| satır başı `-100%` → negatif | Madde işareti eksi sayılıyordu | Satır başı / kelimeye bitişik `-` işaret değil |
| "In FY2018 … $1,577" → 2018 | İlk sayı seçiliyordu; `FY2018` içinde 2018 ayrışıyordu | Harfe bitişik sayı sayı değil; yıl benzeri tam sayılar aday dışı |
| "…, no, 3M is not …" | Yalnızca cevap başındaki Yes/No bakılıyordu | İlk 12 kelimede noktalamayla biten yes/no de kabul |
| `0.125` → `0.12` | Python yuvarlaması çifte yuvarlar | Yarım-yukarı yuvarlama (Decimal) |
| "3M's capex …" → 3 | Şirket adı `3M` ölçekli sayı sanıldı | Sayıya bitişik büyük harf M/K ($ olmadan) sayı değil |

Yeni şablon testi iki hata daha yakaladı: "10-K" içindeki 10 aday seçiliyordu (form adları artık
aday değil), ve model `$` işaretini bırakınca "ilk sayı" kuralı sayfa numarasını seçiyordu (artık
gold'un biçimine en çok uyan aday seçiliyor: $, %, ondalık). `tests/test_cevap_metrik.py` artık
her geliştirme gold'u için gerçekçi cevap şablonları (1.114 kabul), bozulmuş cevaplar (68 ret),
270 hüküm şablonu ve 38 anahtar-sayı şablonu içerir. **Hiçbir model sonucu etkilenmedi**: metrik
henüz hiçbir model çıktısında kullanılmamıştı. Bilinen sınırlar: birim dönüşümü yalnızca soru
"in USD millions/billions/thousands" diyorsa yapılır; yüzdeyi kesir yazmak (0.019 vs 1.9%)
eşleşmez; parantezli negatifler okunmaz.

**2. Güven aralıkları şirket bağımlılığını yok sayıyordu (kontrol edildi).** 99 geliştirme sorusu
yalnızca **21 şirkete** dağılıyor (şirket başına 1-9 soru, medyan 4); aynı şirketin soruları
bağımsız değil. Reranker karşılaştırmaları şirket-kümeli bootstrap ile yeniden hesaplandı:
sonuç aynı kaldı (10 karşılaştırmadan 9'u yine anlamlı pozitif; e5 tek belge yine anlamsız;
örn. bge-base ortak havuz: soru-bazlı [+0,116; +0,283], şirket-bazlı [+0,120; +0,292]).
**Karar:** bundan sonraki ön kayıtlarda şirket-kümeli bootstrap standarttır. Önceki deneylerin
ölçütleri soru-bazlı idi ve yalnızca reranker için yeniden doğrulandı.

**3. fp16 skorlama (kontrol edildi).** e5-base ortak havuz: 14/99 soruda ilk-5 kümesi fp16 ile
fp32 arasında değişiyor ama Recall@5 farkı +0,008 [-0,017; +0,039], yani gürültü. Gelecekteki
skorlamada fp32'ye geçmek bedava ve önerilir.

**4. Günlük tutarlılığı (düzeltildi).** Çürütülen iddialar ("darboğaz doğru belgeyi bulmak",
"büyük kısmı yanlış belge bulma"), yanlış okunabilecek "0/12" ifadesi (gerçekte 4 soru) ve eski
durum satırları (Karar 4 "şimdilik verilmedi", Karar 7 "plan onaylandı", durum tablosunun
tarihi) revize notlarıyla işaretlendi; durum tablosu deney sonuçlarıyla güncellendi.

**5. Kısıtlar değişti.** README'deki "en fazla 1 hafta" ve "Colab T4" kısıtları artık geçerli
değil: zaman kısıtı yok; kaynaklar yerel RTX 2060 (6 GB), Colab T4 (fine-tune), M4 MacBook Air
(yerel okuyucu LLM) ve Gemini kredileri. README güncellendi.

**Açık ve karar gerektiren konular (henüz yapılmadı):**

- **Azami batch ölçümü** (Karar 3, README gün 1) hâlâ yok; yerel 6 GB yetersiz, Colab T4'te yapılmalı.
- **Fine-tune stratejisi.** Reranker sonrası dört embedding modelinin farkı büyük ölçüde siliniyor,
  bu yüzden embedding fine-tune'ının uçtan uca etkisi küçük kalabilir. FinQA tek sayfalık sayısal
  sorulardan oluşuyor (en iyi olduğumuz tür: metrics-generated); en zayıf tür domain-relevant
  FinQA tarafından kapsanmıyor. FinQA metni de küçük harfli ve kelimelere bölünmüş
  ("company 2019s common stock"), PDF chunk'larımıza benzemiyor. Seçenekler: (a) FinQA ile embedding,
  (b) reranker fine-tune, (c) korpus belgelerinden sentetik sorgu. Ayrı karar olarak konuşulacak.
- **Final protokolün ön kaydı:** hangi dense model, kilitli testte ölçülecek en fazla 3 sistem,
  küme bootstrap, 51 soru / 11 şirketin gücü (yalnızca ~0,1 ve üstü farklar ayırt edilebilir).
- **Okuyucu hattı:** prompt şablonu ve "Final answer:" biçimi, Mac ve Gemini betikleri, yargıç modeli.

---

## Karar 11: Proje hedefi ve fine-tune'ın yeri — KAPANDI (2026-10-01)

**Hedefin netleştirilmesi (kullanıcı):** projenin asıl hedefi **finans RAG sistemi geliştirmek**.
Fine-tune "olursa iyi olur" bir ektir; CV'de BGE-M3 fine-tune deneyimi zaten mevcut. Bu projenin
önceki RAG projesinden farkı: orada llama ile yerelde çalışılmıştı, burada **üretim API anahtarıyla**
(Gemini kredileri) yapılacak.

**Düzeltme notu:** ikinci gözden geçirmede fine-tune merkeze konmuştu, çünkü README'deki "CV'ye
kazandıracağı şey" listesi ve gün 5 planı onu öne çıkarıyordu. Kullanıcının önceliği RAG;
README bu çerçeveye göre güncellendi.

**Mevcut durum, RAG'ın dört parçası:**

| Parça | Durum |
|---|---|
| Belge işleme (PDF → sayfa → chunk) | Tamam |
| Arama (dense + reranker) | Tamam, ölçüldü |
| **Üretim (LLM cevabı, atıf)** | **Başlamadı** |
| **Cevap düzeyinde ölçüm** | Metrik kodu hazır; hiçbir model cevabında kullanılmadı |

**Karar:** fine-tune **isteğe bağlı ek, çekirdek sonrası**, bir karar kapısı arkasında:

1. Kapı koşulu: üretim hattı, cevap düzeyinde ölçüm ve kilitli test ölçümü tamamlanmış olmalı.
2. Kullanıcı o noktada fine-tune'a ilgi ve gerek görürse başlanır.
3. Yapılırsa en ucuz anlamlı biçim: bge-base-en'i FinQA ile eğitip öncesi/sonrasını hem ilk aşamada
   hem reranker sonrası ölçmek; olumsuz sonuç da raporlanır. Azami batch ölçümü (Karar 3) o zaman
   yapılır; şimdi bloklamıyor.
4. Beklenti (ölçülmedi): reranker baskın olduğundan embedding fine-tune'ının uçtan uca etkisi küçük
   kalabilir.

## Karar 10 revizesi — okuyucu LLM (2026-10-01)

**Revize edildi:** okuyucu **yalnızca API (Gemini kredileri), iki model katmanı** (hızlı ve güçlü;
"sonuçlar okuyucudan bağımsız mı?" sorusu için). Yerel M4 okuyucu kapsamdan çıktı (önceki projede
yapılmıştı; bu projenin farkı API). Üç bağlam koşulu (kapalı kitap / getirilen / oracle) aynen
kalır.

- **Serbest metin cevaplar** (geliştirmede 7/99) **kullanıcı tarafından elle puanlanır**; LLM yargıç
  ve onun yanlılığı/kalibrasyonu gerekmez. Kısa bir puanlama sayfası hazırlanacak.
- **Tekrarlanabilirlik:** API sıcaklık 0'da bile birebir aynı cevap vermeyebilir. Her ham cevap
  diske önbelleklenir, model sürümü sabitlenir, sonuçlar önbellekten yeniden hesaplanabilir.
- **Güvenlik:** API anahtarı depoya girmez, ortam değişkeninden okunur; kullanıcı kendi
  terminalinde ayarlar.
- **Veri:** FinanceBench CC-BY-NC lisanslı; API'ye göndermek ticari olmayan araştırma kullanımıdır
  ve karar kullanıcıya aittir.
- **Maliyet:** yaklaşık birkaç milyon token öngörülüyor (99 soru × 3 koşul × birkaç yapılandırma);
  fiyat güncel listeden doğrulanacak, tahminle yazılmadı.
- **Hâlâ açık:** model adları ve sürümleri (güncel dokümantasyondan doğrulanacak), prompt şablonu,
  "Final answer:" ve atıf biçimi, bağlam bütçesi.

## Karar 12: Final protokolde dense model — KAPANDI (2026-10-01)

**Karar: e5-base-v2.**

| Model | Ortak havuz R@5 (ilk aşama → +reranker) | Tek belge R@5 (ilk aşama → +reranker) | Gömme |
|---|---|---|---|
| bge-base-en | 0,157 → 0,354 | 0,480 → 0,630 | 620 sn |
| **e5-base** | **0,213 → 0,394** | **0,567 → 0,630** | 627 sn |
| gte-base-en | 0,189 → 0,323 | 0,449 → 0,630 | 919 sn |
| BGE-M3 | 0,197 → 0,323 | 0,433 → 0,606 | 1671 sn |

**Gerekçe ve sınır (açık):** e5-base nokta tahminiyle iki arama uzayında da önde veya eşit ve
küçük/hızlı. **Dört model arasındaki farklar istatistiksel olarak anlamlı değil**; seçim nokta tahmini
ve verimlilik üzerine yapıldı, bunun "e5 daha iyi" kanıtı olmadığı raporlanır. Seçim yalnızca
geliştirme sonuçlarına dayanır (kilitli kümeye bakılmadı). Künye ile e5'in belirgin bozulması
(Deney 1) künye kullanılmadığı için bu seçimi etkilemez.

---

## Deney 5: Uçtan uca RAG, cevap düzeyinde ölçüm (FİNAL PROTOKOL) — ÖN KAYIT, ÇALIŞTIRILMADI

**Sonuçlardan ÖNCE yazıldı (2026-10-01).** Hiçbir okuyucu çağrısı yapılmadı. Bu bölüm sabitlendikten
sonra değişiklik yalnızca "Protokol değişikliği" notuyla ve gerekçesiyle yapılır; sessiz düzeltme yok.

### Amaç

RAG sisteminin gerçek hedefini ölçmek: **doğru cevap**. Soruları: (1) retrieval cevaba değer katıyor
mu, (2) retrieval ne kadar kayıp yaratıyor (okuyucu sınırı mı, arama sınırı mı), (3) chunk boyutu
(Deney 4'te sayfa isabeti ve kanıt kapsaması ters yönlere işaret etti) cevap doğruluğunu nasıl etkiliyor.

### Sistem (sabit)

- **Arama:** künyesiz chunk'lar, **ortak havuz** (360 belge), `intfloat/e5-base-v2` (Karar 12),
  **Chroma vektör veritabanı üzerinden (yeniden açılmış kalıcı koleksiyon, Karar 13 / Deney 6b)**,
  ardından `BAAI/bge-reranker-v2-m3`. Rerank derinliği ≈10.000 kelime aday: c200 için 50, c300 için 33.
- **Bağlam:** reranker sırasıyla chunk'lar birleştirilir, **tam 1000 kelimede kesilir** (sınırı aşan
  chunk'ın kalanı atılır). Böylece c200 ve c300 aynı kelime miktarını görür (Deney 4'teki bütçe kuralı
  c300'e ~1200 kelime verirdi, bu karıştırıcı bu yolla kaldırıldı). Her chunk bir etiketle verilir:
  `[belge: <doc_name>, sayfa: <sayfa_idx>]` (etiket kelime sayılmaz); sayfa numarası gold'daki
  `evidence_page_num` ile aynı tabandadır (0 tabanlı PDF sırası, Karar 6).
- **Okuyucular (iki katman, kararlı sürüm):** `gemini-3.8-flash` (güçlü), `gemini-3.5-flash-lite`
  (hızlı). Sıcaklık 0, tek çağrı (best-of yok), düşünme ve diğer parametreler API varsayılanında;
  kullanılan token sayıları kaydedilir. Model kimliği her kayıtla birlikte yazılır.
- **Prompt:** tek sabit şablon, pilotla biçim doğrulanıp **dondurulur** (aşağıda). Cevap biçimi:
  kısa gerekçe, ardından `Final answer: ...` satırı, ardından `Sources: [belge, sayfa]; ...` satırı
  (kapalı kitapta Sources yok).

### Koşullar (aynı soru ve prompt iskeleti)

| Kod | Koşul | Bağlam |
|---|---|---|
| K0 | Kapalı kitap | Yok |
| K1 | Getirilen (gerçekçi RAG) | Yukarıdaki hat, ortak havuz, ilk 1000 kelime |
| K2 | Oracle | Gold kanıt sayfalarının tam metni (çok kanıtlıysa hepsi) |

K1 için chunk yapılandırması iki varyant: **c200** (baz) ve **c300**. K0 ve K2 chunk'tan bağımsızdır.
Geliştirme kümesi çalıştırmaları: 2 okuyucu × (K0 + K2 + K1-c200 + K1-c300) = 8 çalıştırma × 99 soru.

### Metrikler

**Birincil: cevap doğruluğu** (`src/cevap_metrik.py`, Karar 2 revizesi); soru başına ikili:

| Gold türü | Doğru sayılma kuralı |
|---|---|
| salt_sayi | `hassasiyet` (gold'un ondalık basamağında eşleşme); `tolerans` (%1) ikincil raporlanır |
| hukum | Yes/No hükmü eşleşir |
| anahtar_sayi | Gold'daki tüm anahtar sayılar bulunur (`hepsi`); bulunma oranı da raporlanır |
| serbest | **Kullanıcı elle puanlar** (kör: koşul ve okuyucu etiketi gizli, sıra karıştırılmış) |

Başlık sayısı: doğru soru / toplam soru, ayrıca gold türü bazında doğruluk.

**İkincil:** (a) **atıf doğruluğu** (K1, K2): modelin `Sources` satırındaki (belge, sayfa) çiftlerinin
gold sayfalarıyla örtüşmesi: *atıf isabeti* (en az biri gold sayfa) ve *atıf kesinliği* (anılan
sayfaların gold olanları oranı); (b) maliyet: token, süre; (c) retrieval metrikleri (Recall@1000w
vb.) mevcut kodla; (d) cevapsız/engellenmiş çağrı sayısı.

### Hipotezler ve ön kayıtlı ölçütler

Hepsi **eşleştirilmiş, şirket-kümeli bootstrap** ile (21 şirket kümesi, 10.000 tekrar, %95, tohum 0);
"anlamlı" = aralık 0'ı içermiyor. Farklar soru bazında eşleştirilir.

- **H5a (retrieval değer katıyor):** K1-c200 doğruluğu K0'dan yüksektir. **Ölçüt:** her iki okuyucuda
  anlamlı pozitif fark (2/2).
- **H5b (arama kaybı):** K2 (oracle) K1-c200'den yüksektir. Bu bir **ayrıştırma ölçümüdür**: fark,
  retrieval'ın doğru sayfayı getirememesinin cevaba maliyetidir. Ölçüt yok, fark ve aralığı raporlanır.
- **H5c (chunk boyutu):** K1-c300 doğruluğu K1-c200'den yüksektir. **Ölçüt:** her iki okuyucuda
  anlamlı pozitif fark (2/2); aksi hâlde **c200 kalır.**
- **H5d (okuyucudan bağımsızlık):** H5a ve H5c'nin yönü iki okuyucuda aynıdır (betimsel; testsiz).

**Açık beklenti (tahmin, ölçülmedi):** K0'ın metrics-generated (şirkete ve yıla özgü sayılar)
sorularında çok düşük, K1'in anlamlı yüksek olmasını bekliyorum (H5a destekleniyor). H5c için net
bir beklentim yok; c300 kanıt kapsaması daha yüksek ama %3 kesilme ve ortak havuzda sayfa isabeti
düşüşü var, 2/2 sıkı ölçütünü geçmesini çok olası görmüyorum. Ölçüt bu tahmine göre değil sabit
eşiğe göre değerlendirilir.

### Prompt dondurma kuralı

1. Prompt şablonu bu ön kayıttan sonra yazılır ve ilk çalıştırmadan önce `sonuclar/` altına
   sürüm numarasıyla kaydedilir.
2. **Pilot:** 12 geliştirme sorusunda yalnızca **biçim** doğrulanır (`Final answer:` ve `Sources:`
   ayrıştırma oranı, boş/engellenmiş çağrılar). Pilotta doğruluk **optimize edilmez**; doğruluk
   görülse bile prompt'u doğruluğa göre ayarlamak yasaktır.
3. Pilottan sonra prompt **dondurulur**, geliştirme kümesinde tüm çalıştırmalar donmuş prompt'la
   tek seferde yapılır. Donduktan sonra prompt değişirse yeni sürüm sayılır, tüm çalıştırmalar
   tekrarlanır ve sürüm sayısı raporlanır.

### Kilitli test (Karar 8)

- Geliştirme kümesinde tüm tasarım (prompt, bağlam, chunk seçimi) dondurulduktan sonra, **tek seferde**.
- Kilitli kümede ölçülecek en fazla **3 sistem** (okuyucu başına): **K0, K1 (H5c sonucuna göre c200 ya da
  c300), K2**. Başka yapılandırma eklenmez.
- Sonuçlar ne olursa olsun raporlanır; kilitli test sonrası protokol değişmez. 51 soru / 11 şirketle
  yalnızca büyük farklar (~0,1 ve üstü) ayırt edilebilir; sonuçlar bu çerçevede yorumlanır.
- Kilitli kümede retrieval ilk kez bu aşamada çalıştırılır (`kilitli=True` yalnızca bu betikte).

### Sızıntı politikası bu deneyde

Fine-tune yapılmadığı sürece FinQA ile eğitim yoktur, yani Karar 1'in 22 örneği çıkarma politikası bu
deney için devreye girmez (yalnızca fine-tune yapılırsa). Okuyucu modellerin SEC metnini ön-eğitimde
görmüş olma ihtimali doğrulanamaz; **K0 (kapalı kitap) bunu doğrudan ölçen bir referanstır**:
K0 yüksek çıkarsa ya soruların ezberlenmiş/bilinen bilgiye dayandığı ya da genel finans bilgisiyle
cevaplandığı anlamına gelir, bu sınırlılık olarak raporlanır.

### Uygulama kuralları

- **API anahtarı** depoya girmez, ortam değişkeninden okunur; kullanıcı kendi terminalinde ayarlar.
- Her **ham yanıt** (istek, yanıt, model kimliği, token sayıları, zaman) diske önbelleklenir
  (`data/islenmis/cevaplar/`, repoya girmez); analiz önbellekten yeniden üretilebilir.
- API hataları için sınırlı yeniden deneme; sonuçsuz kalan çağrı **yanlış** sayılır ve ayrıca raporlanır.
- Çalıştırmadan önce toplam token tahmini ve fiyat gösterilir, kullanıcı onayı alınır.
- **Veri ve katman notu:** Gemini kredilerinin ücretsiz mi ücretli katmanda olduğu kullanıcı tarafından
  kontrol edilecek (dokümantasyona göre ücretsiz katmanda içerik ürün iyileştirmede kullanılabilir,
  ücretli katmanda kullanılmaz). **Kullanıcı bildirimi (2026-10-01):** krediler TL bakiyesi olarak var
  (Credit balance: TRY 496,48); bu, faturalama ile ilişkili ücretli bir hesaba işaret eden bir
  göstergedir ama katman doğrulaması DEĞİLDİR. Kesin doğrulama: anahtarın bağlı olduğu projenin planı
  (AI Studio) kullanıcı tarafından teyit edilecek. FinanceBench CC-BY-NC lisanslıdır; kullanım ticari
  olmayan araştırmadır.
- **Harcama tavanı:** çalıştırmadan önce token tahmini TL'ye çevrilip gösterilir; kullanıcı onayı ve
  bakiyeyi aşmayan bir tavan konur (toplam harcama tavanı: kullanıcı belirler).
- Fiyat bilgisi (2026-10-01 dokümantasyon özeti): `gemini-3.8-flash` $0,75 / $3,75 (1M giriş / çıkış
  token, 31.12.2026'ya kadar), `gemini-3.5-flash-lite` $0,30 / $2,50; ilk çağrıdan önce panelden
  doğrulanacak.

### Uygulama sırası

1. Bağlam ve istek üretimi (K0, K1-c200, K1-c300, K2), prompt sürümü kaydı.
2. Gemini okuyucu betiği (önbellek, yeniden deneme, anahtar ortam değişkeninden).
3. Pilot (12 soru, yalnızca biçim) → prompt dondurma.
4. Geliştirme kümesi çalıştırmaları (8 × 99), cevap puanlama, serbest metin elle puanlama sayfası.
5. Küme bootstrap karşılaştırmaları (H5a-d), hata analizi (gold türü, soru türü, çok kanıtlı sorular).
6. Kilitli test (tek sefer), rapor, README.

**Raporlama:** tüm koşullar ve okuyucular, sonuç ne olursa olsun; çoklu karşılaştırma uyarısıyla
(ölçütler tutarlılık arar). Olumsuz sonuç (ör. c300'ün c200'ü geçememesi) bu proje için bulgudur.

---

## Karar 13: Vektör veritabanı — KAPANDI (2026-10-02)

**Soru (kullanıcı):** RAG sistemlerinde vektör veritabanı kullanmamız gerekmiyor mu? **Mevcut durum:**
chunk gömüleri `embeddings/*.npy` dosyalarında, arama `Q @ E.T` + `torch.topk` ile **tam (kaba kuvvet,
flat)** yapılıyor; işlevsel olarak bir flat vektör deposu. Ölçüm (e5-base, 163.543 vektör, 1 sorgu):
CPU 13,9 ms, GPU 1,6 ms. Bu ölçekte tam arama hızlı ve yaklaşıklık hatası taşımaz; tüm önceki
ölçümler bu yüzden birebir tekrarlanabilir. Vektör veritabanlarının asıl değeri: yaklaşık indeksler
(milyon+ ölçek), kalıcılık, ekleme/silme, metadata filtreleme, servis.

**Karar (kullanıcı): gerçek bir vektör veritabanı kullanılacak.** Seçenekler (bu makinede doğrulandı):

| Aday | Bu makinede | Gerçek indeks | Not |
|---|---|---|---|
| **Chroma 1.5.9** | Hazır paket (Py 3.13/Windows); numpy ve torch'a dokunmaz; onnxruntime, protobuf, pydantic yükler | HNSW (cosine; varsayılan ef_construction 100, ef_search 100, max_neighbors 16) | Gömülü, kalıcı, altyapısız. Dokümanda tam arama seçeneği yok |
| Qdrant 1.19.1 | İstemci hazır; sunucu için **Docker gerekir, kurulu değil** | Sunucuda evet | Yerel modu dokümana göre geliştirme/prototip/test içindir |
| LanceDB 0.39.0 | Hazır paket | Evet | Daha az yaygın |
| pgvector | PostgreSQL kurulu değil | Evet | Ek altyapı |

**Seçim: Chroma.** Gerekçe: altyapı gerektirmez, gerçek HNSW indeksi sunar, bu makinede hemen
çalışır. Bir soyutlama katmanı (`vektor_deposu`) ileride Qdrant'a geçişi kolaylaştırır. Chroma'nın
metadata filtreleme ve kalıcı istemci desteği dokümantasyon sayfasında görülemedi; **uygulamada
çalıştırılarak doğrulanacak**.

**Entegrasyon derinliği (kullanıcı): doğrulanırsa K1'in ilk aşaması.** DB doğrudan K1'in yerine
konmaz; önce Deney 6'da tam aramayla karşılaştırılır. Ölçüt geçerse final hattı DB üzerinden çalışır;
geçmezse DB ayrı bir demo/sorgu yolu olarak kalır ve neden raporlanır.

**Bilimsel risk (açık):** vektör veritabanları **yaklaşık** arama yapar. "Tek belge" teşhis ölçümü
yüksek seçicilikte filtre gerektirir (bir belgenin ~460 chunk'ı / 163.543 = %0,3); filtreli HNSW
bilinen bir zayıf durumdur ve isabeti düşürebilir.

---

## Deney 6: Vektör veritabanı (Chroma, HNSW) vs tam arama — ÖN KAYIT, ÇALIŞTIRILMADI

**Sonuçlardan ÖNCE yazıldı (2026-10-02).** Hiçbir Chroma kurulumu/ölçümü yapılmadı.

**Soru:** yaklaşık (HNSW) arama, tam aramanın ürettiği retrieval kalitesini koruyor mu; ve bu, filtreli
(tek belge) aramada da geçerli mi? Cevap evetse final hattı DB üzerinden çalışabilir.

**Kurulum (sabit):** `chromadb==1.5.9`, kalıcı istemci (`data/islenmis/chroma/`, repoya girmez);
koleksiyon mesafesi **cosine**; koleksiyon, **e5-base-v2 c200 künyesiz gömüleriyle** (`embeddings/e5-base.npy`,
163.543 vektör) kurulur, vektörler birebir aynı (yeniden gömme yok). Metadata: `chunk_id`, `doc`,
`sayfa_idx`. İndeks kurulum parametreleri **varsayılan** (ef_construction 100, max_neighbors 16).
Sorgu vektörleri tam aramadakiyle aynı (query: öneki, normalize).

**Arama uzayları (Karar 9):** ortak havuz (filtresiz, ilk 100) ve tek belge (`doc == sorunun belgesi`
filtresi, ilk 100). Geliştirme kümesi, 99 soru.

**Ölçümler:**

1. **Küme örtüşmesi:** soru başına |DB ilk-50 ∩ tam ilk-50| / 50 ortalaması (ayrıca ilk-5 ve ilk-100).
2. **Retrieval kalitesi:** Recall@1000w ve Recall@50, DB sıralaması vs tam arama (eşleştirilmiş,
   şirket-kümeli bootstrap).
3. **Reranker sonrası:** Deney 2'deki aynı reranker ve derinlik 50 ile Recall@1000w, DB vs tam arama.
4. **Gecikme ve maliyet:** sorgu başına ms (medyan ve p95) tam arama (GPU, CPU) vs Chroma; indeksleme
   süresi; disk boyutu.

**Ölçüt (sabit): DB, final hattında kullanılabilir sayılır ancak aşağıdakilerin TÜMÜ sağlanırsa:**

- (a) ortak havuzda ortalama ilk-50 örtüşmesi **≥ 0,95**;
- (b) tek belgede (filtreli) ortalama ilk-50 örtüşmesi **≥ 0,95**;
- (c) reranker sonrası Recall@1000w farkının (DB − tam) %95 aralığının **alt sınırı ≥ −0,05**, her iki
  arama uzayında ("aşağı olmama": en fazla 5 puan kayıp kabul edilir);
- (d) filtreli aramada sorgu başına istenen 100 sonucun hepsi dönüyor (eksik sonuç yok).

**Tek ayar adımı (ön tanımlı):** (a)-(d) sağlanmazsa **yalnızca `ef_search`** sırayla 100 → 400 → 1000
yapılır (indeks yeniden kurulmaz); ilk sağlanan ayar seçilir, üçü de raporlanır. Hiçbiri sağlamazsa DB
final hattında kullanılmaz, demo yolu olarak kalır ve neden raporlanır. Başka ayar (M, ef_construction,
filtre stratejisi) bu deneyde denenmez.

**Açık beklenti (tahmin, ölçülmedi):** filtresiz ortak havuzda varsayılan ayarla yüksek örtüşme (≥0,95)
bekliyorum; **tek belge filtreli aramada en büyük kaybı bekliyorum** (seçici filtre, %0,3) ve
ef_search artırımının gerekebileceğini tahmin ediyorum. Ölçüt bu tahmine göre değil sabit eşiğe göre
değerlendirilir.

**Doğrulama zorunlulukları (uygulama sırasında):** Chroma'nın cosine mesafesinin yorumu (1 − cos)
tam aramayla küçük bir örnekte tutarlılık testiyle doğrulanır; filtre ve kalıcılık davranışı çalıştırılarak
teyit edilir; yeniden başlatmadan sonra koleksiyonun aynı sonuçları verdiği test edilir.

**Raporlama:** üç ef_search ayarı × iki arama uzayı, tüm ölçümler, sonuç ne olursa olsun. Olumsuz sonuç
("HNSW filtreli aramada kaybettiriyor") bu proje için bulgudur.

**Final hatta etkisi:** ölçüt geçerse Deney 5'teki K1 (getirilen) bağlamı DB üzerinden üretilir ve
bu, Deney 5 ön kaydındaki "ortak havuz, e5-base, reranker" tanımıyla uyumludur (aynı vektörler, aynı
reranker); geçmezse K1 tam aramayla üretilir.

**Protokol notu (çalıştırmadan ÖNCE, 2026-10-02): ölçüt (d) ve referans düzeltmesi.** Ön kayıtta (d)
"istenen 100 sonucun hepsi dönüyor" yazıyordu; bu küçük belgeler için yanlış tanımlanmıştı. Geliştirme
kümesinde 17/99 sorunun belgesi 100 chunk'tan küçük (7'si 50'den küçük; ör. Amcor 8-K: 23 chunk). Doğru
tanım: **(d) filtreli aramada sorgu başına min(100, belgedeki chunk sayısı) sonuç dönmeli, ve dönen
sonuçların hepsi filtredeki belgeye ait olmalı.** Örtüşme ölçümlerinde tek belge referansı (tam arama)
da yalnızca belge içi chunk'lara kırpılır. Ölçütlerin eşikleri (0,95; −0,05) ve ef_search merdiveni
değişmedi.

**Önceki sonuçlar hakkında bulgu (etki yok):** önceki tek belge sıralamaları (`dense_baseline.py`,
`bm25_baseline.py`), belgesi 100 chunk'tan küçük 17 soruda belge dışı chunk'larla **dolduruluyordu**
(toplam 785 yabancı chunk). Yabancı chunk'lar atılıp metrikler yeniden hesaplandığında Recall@5 ve
Recall@1000w (e5, bge-base, BGE-M3; ilk aşama ve reranker sonrası) **birebir aynı** çıktı (fark 0,0000):
gold sayfa daima belge içi chunk'lar arasında ve dolgu yalnızca onlardan sonra geliyor. Hiçbir sonuç
değişmedi; yine de gelecekte tek belge sıralamaları belge içi chunk'larla sınırlanmalıdır (Deney 6'da
bu uygulanıyor).

**SONUÇ, Deney 6 ilk koşu (2026-10-02; `src/deney6_vdb.py`, koleksiyon kurulduktan HEMEN SONRA ölçüldü)**

Kurulum 652 sn, 163.543 vektör, disk **2018 MB** (ham vektörler yalnızca 240 MB: chunk metinleri, HNSW
grafiği ve SQLite eklenir).

| ef_search | Örtüşme@50 ortak | Örtüşme@50 tek (filtreli) | Reranker sonrası Recall@1000w farkı (DB − tam), ortak | tek | (d) ihlali |
|---|---|---|---|---|---|
| 100 / 400 / 1000 (üçü aynı) | **0,916** | 0,990 | -0,008 [-0,025; 0,000] | 0,000 [0,000; 0,000] | 0 |

**Ön kayıtlı ölçüt: (a) başarısız** (0,916 < 0,95), (b), (c), (d) sağlandı. Merdivenin üç basamağı da
aynı sonucu verdi. **Karar (ön kayda göre): DB bu koşuyla final hatta kullanılmaz.**

**Yan bulgular (açıklayıcı, ölçüt dışı):**

- **ef_search bu ölçekte etkisiz:** ayar gerçekten uygulanıyor (yapılandırma 10, 100, 1000 olarak
  okundu) ama sonuç değişmiyor; HNSW bu ölçekte doygun.
- **Referansın kendisi gürültülü (`src/deney6_tani.py`, post hoc):** fp16 tam arama ile fp32 tam arama
  arasında bile ilk-50 örtüşmesi 0,988 (@5: 0,972). Yani 0,95 eşiği "tam arama kendisiyle"
  kıyasında bile hassasiyet tavanının yakınındaydı; yaklaşıklığı ölçerken referans hassasiyeti ayrı
  tutulmalıydı (ön kayıtta öngörülmemiş bir tasarım zayıflığı).
- **Tutarsızlık:** aynı koleksiyonu kapatıp yeniden açınca (aynı veri, aynı sorgular) ortak örtüşme **0,982**
  çıktı (tani ve `tekrar` koşusu). Kurulumdan hemen sonraki durum ile yeniden açılmış durum farklı
  davranıyor. Neden: bilinmiyor. Hipotez (ölçülmedi): bulk ekleme sonrasında bellekteki indeks
  henüz tam değil (daha hızlı ama daha az isabetli: ilk koşuda ortak sorgu 1,2 ms, yeniden açılmışta
  3,4 ms).
- **Gecikme (medyan, run'lar arası büyük oynama var):** Chroma ortak 1,2-3,4 ms; **filtreli tek belge
  35-97 ms, yani filtresiz aramadan ~30 kat yavaş**; tam arama GPU 1,5-9,4 ms (ilk koşuda ölçümde
  başka yük vardı), CPU ~14 ms.

### Deney 6b: yeniden açılmış koleksiyonla doğrulama — ÖN KAYIT (SONRADAN YAZILDI)

**Şeffaflık notu:** bu bölüm, ilk koşunun başarısızlığı ve 0,982'lik yeniden açılmış sonuçlar **görüldükten
sonra** yazıldı; bu yüzden ayrı bir deneydir ve ilk koşuyu geçersiz kılmaz, tamamlar. Gerekçe: final hat
koleksiyonu her zaman diskten yeniden açarak kullanacaktır (kurulum bir kez yapılır), dolayısıyla
**yeniden açılmış durum** operasyonel olarak ilgili durumdur.

**Protokol:** koleksiyon kurulur ve kapatılır (yapıldı); ölçüm **üç ayrı yeni Python sürecinde**, her biri
koleksiyonu diskten açarak, Deney 6 ile **aynı betik ve aynı dört ölçütle**, `ef_search=100`. (1) `tekrar`
(yapıldı), (2) `tekrar2`, (3) `tekrar3` yeni süreçlerde. **Ölçüt:** üç koşunun üçünde de (a)-(d) sağlanır.
Referans fp16 tam arama olarak kalır (değiştirilmedi); referans gürültüsü yukarıda raporlandı.

**Karar kuralı:** 6b ölçütü sağlanırsa Chroma, final hatta **yeniden açılmış koleksiyon olarak** kullanılabilir
ve K1 DB üzerinden üretilir; sağlanmazsa K1 tam aramayla üretilir ve DB demo yolu olarak kalır.
Her iki durumda ilk koşunun (kurulum hemen sonrası) başarısızlığı raporda yer alır.

**SONUÇ, Deney 6b (2026-10-02; üç bağımsız süreç, koleksiyon her seferinde diskten açıldı)**

| Koşu | Örtüşme@50 ortak | Örtüşme@50 tek (filtreli) | Reranker sonrası Recall@1000w farkı (DB − tam) ortak / tek | Ölçüt (a)-(d) |
|---|---|---|---|---|
| tekrar | 0,982 | 0,992 | 0,000 [0,000; 0,000] / 0,000 [0,000; 0,000] | Sağlandı |
| tekrar2 | 0,982 | 0,992 | aynı | Sağlandı |
| tekrar3 | 0,982 | 0,992 | aynı | Sağlandı |

**6b ölçütü sağlandı (3/3).** Sonuçlar koşular arasında birebir kararlı. `ef_search=100` yeterli (400 ve 1000
aynı sonucu verir).

**Karar: Chroma final hatta kullanılabilir, yeniden açılmış (kalıcı) koleksiyon olarak.** Deney 5'teki K1
(getirilen) bağlamı Chroma üzerinden üretilir; vektörler ve reranker Deney 5 ön kaydıyla aynı olduğundan
tanım değişmez. Raporda şu üç şey birlikte verilir:

1. **İlk koşu (kurulum hemen sonrası) başarısızdı** (ortak örtüşme 0,916); nedeni bilinmiyor
   (hipotez: bulk eklemeden sonra bellekteki indeks henüz tam değil). Operasyonel kural: **koleksiyon
   kurulduktan sonra kapatılıp yeniden açılmadan kullanılmaz.**
2. **Referans (fp16 tam arama) kendi içinde 0,988 örtüşme tavanına sahip;** 0,982 bu tavana çok
   yakındır, yani HNSW kaybı hassasiyet gürültüsünden ayırt edilemeyecek kadar küçüktür.
3. **Bedeller:** disk 2018 MB (ham vektörler 240 MB); kurulum 652 sn; **filtreli arama ~97 ms**, filtresiz
   aramadan ~30 kat yavaş (ortak ~3,4 ms; tam arama GPU ~1,5 ms, CPU ~14 ms).

**Yorum:** bu ölçekte (163 bin vektör) vektör veritabanı **kaliteyi korur ama hız ya da basitlik kazandırmaz**;
tam arama zaten milisaniye mertebesinde ve yaklaşıklık hatası taşımaz. Veritabanının değeri burada operasyonel:
kalıcılık, metadata filtresi, ölçeklenebilirlik ve standart bir RAG yığınının parçası olması. Bu, README'de
ölçümle gerekçelendirilir.

**Not (6b'nin sınırı):** üç koşu aynı koleksiyonu aynı makinede aynı sorgularla açar; bağımsız bir koleksiyon
kurulumu (yeniden indeksleme) ve başka bir makine ölçülmedi. Kurulum sonrası tutarsızlığın nedeni
çözülmemiştir.

**Protokol notu, Deney 5 uygulama adım 1 (çalıştırmadan ÖNCE, 2026-10-02): bağlam üretimi ve prompt v1.**

- **K1-c200** bağlamı Chroma üzerinden üretilir (yeniden açılmış koleksiyon, `ef_search=100`, Deney 6b),
  reranker Deney 2 ile aynı (derinlik 50). **K1-c300** için Chroma koleksiyonu kurulmadı ve Deney 6b
  doğrulaması yapılmadı; bu yüzden K1-c300 bağlamı **kayıtlı tam-arama + reranker sıralamasından**
  (Deney 4, derinlik 33) alınır. c200 için DB ile tam arama reranker sonrası birebir aynı Recall verdi
  (Deney 6b), bu yüzden karşılaştırmayı bozması beklenmez; yine de c200 (DB) ile c300 (tam arama) arka
  uçları farklıdır ve H5c yorumlanırken bu not edilir.
- **Bağlam kuralı doğrulandı:** her K1 bağlamı tam 1000 kelime (c200 ve c300; 99 sorunun hepsinde),
  etiketler (`[belge: ..., sayfa: ...]`) kelime sayılmaz. **K2** gold sayfaların tam metni, kesilmez
  (medyan 432, ortalama 484, maks 2144 kelime); K1'e kıyasla bağlam miktarı farklıdır, K2 bir **referans**
  koşuldur. Kanıt sayfasını içeren soru oranı K1-c200'de 0,475, K1-c300'de 0,485 (kanıt bazlı oran 0,429 /
  0,424; Deney 4'teki Recall@1000w ile uyumlu).
- **Prompt v1** `sonuclar/prompt_v1.json` içinde sha256 ile kayıtlıdır; aynı sürüm numarasıyla değişen
  şablon reddedilir. İçerik: İngilizce, tek kullanıcı mesajı + kısa sistem mesajı; bağlamlı koşullarda
  "yalnızca bağlamı kullan", biçim talimatları (yuvarlama/birim, kısa gerekçe, evet/hayır sorularında "Yes"
  ya da "No" ile başla, sayıyı birimiyle yaz), çıktı: `Final answer: ...` ve `Sources: <belge>, <sayfa>; ...`
  (kapalı kitapta yalnızca `Final answer`). Yes/No ve birim talimatları gold cevap biçimini taklit eden
  **biçim** talimatlarıdır, doğruluğa göre ayarlanmış değildir (hiçbir model cevabı henüz görülmedi).
  **v1 pilotta biçim hatası verirse v2'ye geçilebilir (yalnızca biçim gerekçesiyle); pilottan sonra
  dondurulur.**
- **Pilot:** 12 geliştirme sorusu, soru türü başına 4, id sırasıyla (`sonuclar/pilot_idler.json`);
  yalnızca biçim doğrulanır (ayrıştırma oranı, boş/engellenmiş çağrılar).
- **Maliyet tahmini (token = kelime × 1,4-2,0, çağrı başına 300-800 çıkış token; Gemini tokenizer'ı
  bilinmiyor, ilk çağrıda `count_tokens` ile doğrulanacak):** geliştirme tek geçiş, iki okuyucu, 4 koşul,
  792 çağrı: `gemini-3.8-flash` $0,79-1,67, `gemini-3.5-flash-lite` $0,43-0,99; toplam **$1,22-2,66**
  (pilot ~%12 ek). Kullanıcı bakiyesi TRY 496,48; tek geçiş bakiyeye, USD/TRY kuru 186'nın altında olduğu
  sürece sığar. Düşünme (thinking) tokenları çıktı olarak faturalanır; üst sınır buna göre bırakılmıştır.

**Protokol notu, Deney 5 (çalıştırmadan ÖNCE, 2026-10-02): harcama tavanı, prompt incelemesi ve v2.**

- **Harcama tavanı (kullanıcı kararı): 250 TL** (kur 55 TL/USD, yaklaşık $4,5; kullanıcı bakiyesi TRY 496,48).
  Planlanan akışın (pilot + geliştirme + kilitli test) tahmini maliyeti 110-240 TL; tavanı aşan her
  harcama için önce kullanıcı onayı alınır, betik her çalıştırmadan önce tahmini maliyeti TL'ye çevirip
  gösterir. Google tarafında da AI Studio "Monthly spend cap" ayarı kullanılır (dokümantasyonda
  proje düzeyinde aylık sınır olarak geçer; para birimi sayfada belirtilmemiş, kullanıcı panelden
  doğrulayacak). Ön ödemeli kredi sıfırlanınca tüm anahtarlar durur (dokümantasyon).
- **Prompt incelemesi (v1, hiçbir çağrı yapılmadan):** gerçek soru kalıpları incelendi (99 soruda 27'si
  "using/relying on/based on", 20'si "round", 11'i birim, 30'u evet/hayır, 4'ü liste isteyen). Gemini
  benzeri gerçekçi çıktı biçimleri (markdown, `Sources:` satırı, ters sıra, `none`) cevap metriğinden
  geçirildi ve **iki sorun** bulundu: (1) `Sources: DOC_2022_10K, 100` satırındaki sayfa numarası
  gold'daki "%100" anahtar sayısıyla yanlış eşleşip hatalı cevabı doğru sayıyordu; (2) atıf doğruluğunu
  ölçecek ayrıştırıcı yoktu. `cevap_metrik.py` düzeltildi: markdown işaretleri temizlenir, `Sources`
  satırı cevabın sayısal içeriğinden ayrılır (ters sırada gelse de), `atiflar` ve `atif_skorla`
  eklendi (isabet, kesinlik, bağlamda bulunma oranı = uydurma atıf ölçüsü); testler gerçekçi çıktı
  biçimleriyle genişletildi.
- **Prompt v2** (v1 hiç çalıştırılmadığı için sürüm yükseltmesi; v1 geçmiş olarak kalır). Değişenler,
  hepsi **biçim ve okuma** talimatları, hiçbiri doğruluğa göre ayarlanmadı: (a) "retrieved" yerine
  tarafsız "passages from company filings"; (b) bağlam parçaları farklı yıl/çeyrek/dosyalardan
  olabileceği, yalnızca şirket-dönem-metrikle eşleşenlerin kullanılması; (c) nihai cevabın kısa olması
  (liste istenmedikçe); (d) düz metin, markdown yok; (e) `Sources` etiketlerinin birebir kopyalanması.
  `sonuclar/prompt_v2.json` sha256 ile dondurulmuştur (pilot sonrası kesin dondurma kuralı aynen geçerli).

**Protokol notu, Deney 5 (çalıştırmadan ÖNCE, 2026-10-02): API hesabı doğrulaması ve okuyucu betiği.**

- **Hesap (kullanıcının ekran görüntülerinden):** tek proje, 1 anahtar, **ücretli katman (Tier 1, ön ödemeli)** (ücretli katman; dokümantasyona göre içerik ürün iyileştirmede kullanılmaz).
  Aylık harcama sınırı sayfasında para birimi **TL** (TRY 250,00). **Yakalanan hata:** sınır ilk başta başka bir
  projeye konmuştu; sınır proje düzeyinde olduğundan anahtarın projesinde geçerli
  olmayacaktı. Kullanıcı düzeltti ve sınırı anahtarın projesine koydu. Google'ın sınırı
  "~10 dakikalık gecikmeyle aşılabilir, deneysel" olduğundan **asıl koruma betiğin kendi harcama takibidir**
  (aşağıda), Google sınırı ikinci emniyettir.
- **Modeller doğrulandı (anahtarla `models.list`, ücretsiz çağrı):** `gemini-3.8-flash` ve
  `gemini-3.5-flash-lite` mevcut, girdi sınırı 1.048.576, çıktı sınırı 65.536 token, ikisi de **düşünen
  (thinking) model**; düşünme tokenları ayrı sayılır (`thoughts_token_count`) ve çıktı fiyatından
  faturalanır, bu yüzden gerçek harcama ilk çağrılardan ölçülecektir.
- **SDK:** `google-genai==2.28.0` (resmî SDK; eski `google-generativeai` kullanımdan kaldırılmış).
  Kurulum, mevcut yığını bozmadı (`pip check` temiz; `websockets` 17,1 → 16,1,1 ve `cffi` 1,17,1 → 2,1,1
  değişti, hiçbir kurulu paket websockets'e bağlı değil).
- **Betik (`src/okuyucu_gemini.py`) güvenceleri:** anahtar yalnızca `GEMINI_API_KEY` ortam
  değişkeninden; **onbellek** (aynı istek ikinci kez gönderilmez); **harcama tavanı 250 TL = $4,545
  (kur 55)**, her çağrıdan önce o çağrının en kötü durum maliyeti birikmiş harcamaya eklenerek kontrol
  edilir ve aşılacaksa **çağrı yapılmadan durur**; prompt dondurma doğrulaması; geçici hatalarda (429, 5xx)
  en fazla 3 deneme (2 sn, 4 sn bekleme), kalıcı hatada (4xx) denemez; hatalı/boş yanıt başarı olarak
  önbelleğe yazılmaz (sonraki çalıştırmada tekrar denenir) ve değerlendirmede **yanlış** sayılır.
  Varsayılan çalışma **kuru çalışmadır** (ücretsiz `count_tokens` ile gerçek girdi tokenları, tahmini
  maliyet); gerçek çağrı için `--onayla` gerekir.
- **Ayar eklemeleri (ön kayıttaki "diğer parametreler varsayılan"a göre küçük sapmalar):** `seed=0`
  (belirlilik için) ve `max_output_tokens=8192` (yalnızca **maliyet güvencesi**: düşünen bir modelin
  kontrolsüz düşünmesini sınırlar; siradan bir cevap bunun çok altındadır, kesilme olursa `bitis_nedeni`
  kaydedilir ve raporlanır). Sıcaklık 0 ve düşünme ayarları API varsayılanıdır.
- **Testler:** API'ye ve anahtara hiç dokunmayan sahte istemciyle (`tests/test_okuyucu.py`): maliyet
  hesabı, önbellek, tavan (çağrı yapılmadan durma), yeniden deneme (503→başarı, 400 deneme yok, hep 429
  → hata kaydı), boş yanıtın hata sayılıp yine de ücretlendirilmesi.

**Protokol notu, Deney 5 (2026-10-02): pilot sonuçları ve harcama tavanının 250 → 350 TL'ye yükseltilmesi.**

**Pilot biçim sonuçları (yalnızca biçim; doğruluğa bakılmadı, doğruluğa göre prompt ayarlanmadı):**
5 çalıştırma, 60 yanıt (flash-lite: K0, K1-c200, K1-c300, K2; 3.8-flash: K1-c200; her biri 12 pilot soru):
hatalı/boş yanıt **0**; `Final answer:` satırı **60/60**; `Sources:` satırı **48/48** (K1/K2'de beklenen);
markdown **1/60** (ayrıştırıcı temizliyor); **uydurma atıf 0/69** (modelin andığı hiçbir sayfa bağlam dışında
değil; model etiketteki "sayfa:" kelimesini de kopyalayabiliyor, ayrıştırıcı bunu kabul ediyor).
**Prompt v2'de değişiklik gerekmedi.**

**Ölçülen maliyet ve düşünme tokenları:**

| Model | Düşünme tokenı (medyan / ort / maks) | Çağrı başına |
|---|---|---|
| gemini-3.5-flash-lite | 0 / 0 / 0 (varsayılan ayarda düşünmüyor) | K0 0,021; K1 0,065; K2 0,043 TL |
| gemini-3.8-flash (K1-c200) | **696 / 928 / 2836** | **0,322 TL** (kur 55) |

3.8-flash çağrı başına ortalama 0,322 TL ile **tetik eşiğini (0,30 TL) aştı**; betik durdu ve kullanıcıya
soruldu. Maliyetin ~%65'i düşünme tokenlarından geliyor (çıktı yalnızca ~108 token). **Planın
ölçülen sayılarla güncellenmiş tahmini:** harcanan 6,2 TL + pilotun kalanı ~10 + geliştirme flash-lite ~19 +
geliştirme 3.8-flash ~111 + kilitli test ~67 = **~213 TL**; 250 TL tavanıyla marj yalnızca ~37 TL (%15) ve
düşünme tokenı çok değişken (maks. 2836), yeniden çalıştırma sığmazdı.

**Karar (kullanıcı): tavan 350 TL** (kur 55: ≈ $6,36; bakiye TRY 496,48). Protokol değişmedi: iki okuyucu,
düşünme API varsayılanı. Alternatifler değerlendirildi ve seçilmedi: Batch API (dokümantasyona göre
%50 indirim; mühendislik ve bekleme maliyeti) ve düşünmeyi kısmak (davranışı değiştirir, yeniden pilot
gerektirir). `src/okuyucu_gemini.py` içindeki `TAVAN_TL` 350 yapıldı. **Kullanıcı Google AI Studio'da
anahtarın projesinin aylık sınırını da 350 TL yapmalıdır** (Google sınırı ikinci emniyettir; birincil
koruma betiğin kendi harcama takibidir).

**Pilot tamamlandı ve prompt v2 KESİN DONDURULDU (2026-10-02).**

Pilot: 2 model × 4 koşul × 12 soru = 96 çağrı (yalnızca biçim). Sonuç: hatalı/boş yanıt **0**; bitiş nedeni
hepsinde `STOP`; `Final answer:` **96/96**; `Sources:` **72/72** (K1/K2'de beklenen); **uydurma atıf 0/95**.
Prompt v2'de değişiklik gerekmedi; **dondurma kuralı gereği v2 artık değişmez** (değişirse yeni sürüm sayılır,
tüm çalıştırmalar tekrarlanır ve sürüm sayısı raporlanır). Pilot yanıtları (aynı prompt, aynı istek özeti)
önbellekte kalır ve geliştirme çalıştırmalarında yeniden kullanılır (12 pilot sorusu için yeniden
çağrı yapılmaz).

**Ölçülen çağrı maliyetleri (TL, kur 55):**

| Koşul | flash-lite | 3.8-flash | 3.8-flash düşünme medyanı |
|---|---|---|---|
| K0 (kapalı kitap) | 0,021 | 0,216 | 742 |
| K1-c200 | 0,065 | 0,322 | 696 |
| K1-c300 | 0,065 | 0,378 | 926 |
| K2 (oracle) | 0,043 | 0,202 | 429 |
| **Soru başına dört koşul** | **0,194** | **1,118** | |

**Geliştirme çalıştırmasının tahmini maliyeti:** 87 yeni soru (99 − 12 önbellekte) × (0,194 + 1,118) ≈ **114 TL**
(flash-lite ~17, 3.8-flash ~97). Harcanan 15,74 TL. Geliştirme sonrası toplam ≈ 130 TL; kilitli test
(51 soru) ek ~67 TL; planın toplamı ≈ 213 TL, tavan 350 TL. Düşünme tokenı çok değişkendir (3.8-flash
maks. 2836), tahmin ±%30 belirsizdir.

