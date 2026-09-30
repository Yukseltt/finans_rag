# Karar Günlüğü

Her karar burada, gerekçesiyle ve varsa ölçümüyle kaydedilir. Amaç: *"Neden hibrit arama seçtin?"* sorusunun cevabı bir cümle
değil, bir ölçüm olmalı.

**Kayıt biçimi:** seçenekler → takaslar → karar → gerekçe → (varsa) ölçüm.
Karar değişirse eskisi silinmez, altına "revize edildi" notu düşülür.

---

## Karar 1: Korpus ve değerlendirme seti — AÇIK

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Sadece FinanceBench (150 soru + PDF'leri) | Soru-cevap-kanıt üçlüsü hazır, retrieval doğrudan ölçülür, küçük ve hızlı | 150 soru istatistiksel olarak az, fine-tune verisi çıkmaz |
| b) Sadece FinQA (8.281 örnek) | Binlerce soru, fine-tune'a yeter, kanıt satırları işaretli | Kısa tablo-metin parçaları, "büyük belgede arama" gerçekçiliği düşük |
| c) İkisi birden: FinQA ile eğit, FinanceBench ile test et | Dağılım kaymasını bilerek ölçersin, ikisinin de gücü var | İki formatla uğraşmak gerekir (gün 2'de) |

**Öneri: c.** Karar bekleniyor.

Seçenek (c) seçilirse gün 1'de **mutlaka** yapılacak: FinQA ve FinanceBench'in
şirket-yıl listelerini kesiştir. Örtüşme varsa ya o örnekler eğitimden çıkarılır
ya da "örtüşen kısım şu kadar" diye açıkça raporlanır. Aksi hâlde "dağılım
kaymasını ölçtük" iddiası savunulamaz.

---

## Karar 2: Cevap doğruluğu metriği — AÇIK

Gün 1'de karara bağlanmalı. Sonradan değişirse önceki tüm ölçümler geçersiz olur.

| Seçenek | Artı | Eksi |
|---|---|---|
| a) Tam eşleşme (exact match) | Tartışmasız, hızlı, tekrarlanabilir | Sayı biçimi farkı ("1.2 milyar" vs "1,200,000,000") yanlış sayılır |
| b) Sayısal tolerans (örn. %1 sapma) | Biçim farkına dayanıklı, hâlâ nesnel | Sayısal olmayan cevaplarda çalışmaz, eşik keyfi |
| c) LLM-judge | Her cevap tipine uyar | Yargıç model yanılır, kendi ailesinden cevapları kayırabilir, tekrarlanabilirliği düşük |

**Öneri: b + a karışımı.** Sayısal cevaplarda tolerans, metin cevaplarda tam
eşleşme veya normalize edilmiş karşılaştırma. LLM-judge kullanılacaksa **insan
puanlamasıyla kalibre edilmeden** tek başına raporlanmaz — 30-50 örnekte elle
kontrol edilip uyum oranı verilir.

---

## Karar 3: Fine-tune modeli ve batch stratejisi — AÇIK, ÖLÇÜM BEKLİYOR

BGE-M3 (XLM-RoBERTa-large, ~568M parametre) T4'ün 16 GB'ına gradient
checkpointing ve FP16 ile sığar, ama **kontrastif eğitimde asıl mesele batch
size**: in-batch negatif sayısı doğrudan batch'e bağlı.

Gün 1'de ölçülecek: dummy veriyle 50 adım koş, bellek taşmadan çıkılabilen azami
batch size'ı bul.

| Sonuç | Karar |
|---|---|
| Batch ≥ 32 sığıyor | BGE-M3 ile devam |
| Batch < 32 | `bge-base` veya `bge-small`'a geç — küçük model, büyük batch, muhtemelen daha iyi sonuç |

Not: gradient accumulation bu sorunu **çözmez**. Mikro-batch'ler ayrı ayrı ileri
geçişten geçer ve birbirlerini görmez; accumulation gradient istatistiğini büyük
batch'e benzetir, negatif havuzunu değil. Gerçekten daha çok negatif için
GradCache gibi bir teknik gerekir.

---

## Karar 4: SEC EDGAR kapsama dahil mi — AÇIK

FinanceBench kendi PDF'leriyle geliyorsa EDGAR'a gerek olmayabilir. Bir haftalık
projede belirsiz kapsam en büyük risk.

**Öneri:** gün 1'de FinanceBench PDF'lerinin erişilebilirliğini kontrol et.
Yeterliyse EDGAR'ı kapsam dışına al ve README'de gerekçesini yaz. Gerekirse
EDGAR kuralları zaten doğrulandı: saniyede 10 istek, zorunlu `User-Agent`,
`Accept-Encoding: gzip, deflate`, `Host: www.sec.gov`.

---

## Karar 5: Baseline hattı — AÇIK

Gün 1 sonunda çalışır olmalı. Bu bir "iyi sistem" değil, **sıfır noktası**.

**Öneri:** sabit 512 token chunk, örtüşme yok, BM25 + hazır (fine-tune edilmemiş)
BGE-M3, reranker yok, RRF ile birleştirme yok. Tek bir sayı üret: Recall@5.

Sonraki her karar bu sayıya karşı ölçülür. Gün 2'de "yapıya saygılı chunking
daha iyi" demek için elde karşılaştırma zemini olmalı.
