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
| 6 | Kanıt eşleştirme kuralı | ERTELENDİ: veri görülünce |
| 7 | Retrieval mimarisi | PLAN ONAYLANDI: sıra belli, her adım ölçümle kapanacak |

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

**Hâlâ açık:**

- Hangi ek modeller (aday listesi 1B'den önce birlikte seçilecek; ilk not: proje
  İngilizce olduğundan İngilizce bir model de değerlendirilmeli).
- Her aday için azami batch size ölçümü (dummy veriyle 50 adım, bellek taşmadan
  çıkılabilen en büyük batch).

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

## Karar 6: Kanıt eşleştirme kuralı — ERTELENDİ

Bir chunk'ın "doğru" sayıldığı kural: sayfa numarası eşleşmesi mi, kanıt metniyle
örtüşme oranı mı? Kural, chunking değiştiğinde sabit kalmalı; yoksa gün 2'deki
karşılaştırmalar geçersiz olur. PDF'lerden ve kanıt alanlarından örnek
görüldükten sonra (1B) karara bağlanacak.

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
