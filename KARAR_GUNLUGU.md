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

**Her modelin öneki:** kodda modele özel sorgu/pasaj öneki tablosu tutulur ve
sonuçlarda belirtilir; yanlış önek modeli haksız yere düşürür.

**Hâlâ açık:**

- Her aday için azami batch size ölçümü (dummy veriyle 50 adım, bellek taşmadan
  çıkılabilen en büyük batch).
- Chunk'ın modeller arasında adil tanımı: "512 token" her tokenizer'da farklı
  uzunluk eder ve 512 sınırlı modeller fazlasını keser. Öneri: chunk'ı kelime
  sayısıyla tanımla (~300 kelime). Onay bekliyor; onaylanırsa Karar 5 revize edilir.

| Sonuç | Karar |
|---|---|
| Batch ≥ 32 sığıyor | Modelle devam |
| Batch < 32 | Küçük model, büyük batch; muhtemelen daha iyi sonuç |

Not: gradient accumulation bu sorunu **çözmez**. Mikro-batch'ler ayrı ayrı ileri
geçişten geçer ve birbirlerini görmez; accumulation gradient istatistiğini büyük
batch'e benzetir, negatif havuzunu değil. Gerçekten daha çok negatif için
GradCache gibi bir teknik gerekir.

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
