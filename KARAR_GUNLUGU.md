# Karar Günlüğü

Her karar burada, gerekçesiyle ve varsa ölçümüyle kaydedilir. Amaç: *"Neden hibrit arama seçtin?"* sorusunun cevabı bir cümle
değil, bir ölçüm olmalı.

**Kayıt biçimi:** seçenekler → takaslar → karar → gerekçe → (varsa) ölçüm.
Karar değişirse eskisi silinmez, altına "revize edildi" notu düşülür.

**Durum özeti (2026-09-30)**

| # | Konu | Durum |
|---|---|---|
| 1 | Korpus ve değerlendirme seti | KAPANDI: c, sıkı sızıntı denetimiyle |
| 2 | Cevap doğruluğu metriği | KAPANDI (b + a); eşik ve ayrıntı veriyle teyit edilecek |
| 3 | Fine-tune modeli ve batch | KISMEN: birden çok model denenecek; aday listesi ve batch ölçümü bekliyor |
| 4 | SEC EDGAR dahil mi | ERTELENDİ: PDF'ler incelenince karar verilecek |
| 5 | Baseline hattı | KAPANDI: önce ayrı ayrı, sonra birleştirilmiş |
| 6 | Kanıt eşleştirme kuralı | KAPANDI: c (sayfa ana metrik, metin ikincil) |
| 7 | Retrieval mimarisi | PLAN ONAYLANDI: sıra belli, her adım ölçümle kapanacak |
| 8 | Kilitli test seti | KAPANDI: FinanceBench 99 geliştirme + 51 kilitli, şirket bazında |
| 9 | Arama uzayı | KAPANDI: başlık ortak havuz (360 belge), teşhis için tek belge |

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
- gte kodu sabit commit'lerle (model ve kod) çalıştırıldı.

---

## Karar 4: SEC EDGAR kapsama dahil mi — ERTELENDİ

FinanceBench kendi PDF'leriyle geliyorsa EDGAR'a gerek olmayabilir. Bir haftalık
projede belirsiz kapsam en büyük risk.

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

## Karar 7: Retrieval mimarisi — PLAN ONAYLANDI, ÖLÇÜMLE KAPANACAK

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
korpus 360 belge. Soruların hiçbiri o 8 belgeye bağlı değil. README'de belirtilecek.

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

