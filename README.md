# Ölçülmüş Finans RAG'i

SEC dosyaları ve finansal soru-cevap veri setleri üzerinde kurulan, her bileşeni
sayıyla savunulan bir RAG hattı. Amaç sadece çalışan bir sistem değil: her mimari
kararın **neden** verildiğini ölçümle gösterebilmek.

## Kısıtlar

| Konu | Değer |
|---|---|
| Süre | En fazla 1 hafta |
| GPU | Google Colab T4 (kredili) |
| Dil | İngilizce |
| Çalışma biçimi | Kararlar birlikte alınır: seçenekler, takaslar, öneri, sonra karar |
| Sonraki proje | Küçük dolandırıcılık tespiti projesi (LightGBM, PR-AUC, ONNX). Bu proje bittikten sonra |

## CV'ye kazandıracağı şey

- Var olan BGE-M3 fine-tune deneyiminin finans alanında tekrarı ve ölçülmesi
- Retrieval ve cevap kalitesi için gerçek metrikler (recall@k, MRR, cevap doğruluğu)
- Fine-tune öncesi ve sonrası karşılaştırma, mümkünse seed'li ve anlamlılık testli
- Eğitim ve test dağılımının bilerek ayrılması

## Veri

| Veri | Rol | Lisans | Doğrulama durumu |
|---|---|---|---|
| FinanceBench | Değerlendirme. 150 soru, cevap, kanıt alıntısı, 10-K/10-Q/8-K PDF'leri | CC-BY-NC-4.0 (ticari kullanım yok) | Sayfadan doğrulandı. Açık kaynak sürüm 150 örnek. **Şirket sayısı sayfada verilmiyor**, tam istatistik için Patronus AI'ya yazmak gerekiyor |
| FinQA | Fine-tune eğitim verisi. Soru, tablo, metin, kanıt satırı indeksi | MIT | **Doğrulandı:** train 6.251, validation 883, test 1.147 — toplam 8.281 |
| SEC EDGAR API | Ham korpus (filing metadata, XBRL) | Kamuya açık | **Doğrulandı:** saniyede en fazla 10 istek. Zorunlu başlıklar: `User-Agent: İsim eposta@alan.com`, `Accept-Encoding: gzip, deflate`, `Host: www.sec.gov`. Botnet ve toplu tarama yasak |

### Veri repoya konmaz

`data/ham/` ve `data/islenmis/` gitignore'da. FinanceBench CC-BY-NC-4.0 lisanslı ve
PDF'leri repoya koymak **yeniden dağıtım** sayılır. Veri, `src/veri_indir.py` ile
lokalde indirilir. Repoda yalnızca indirme betiği ve veri manifestosu (dosya
listesi + hash) bulunur.

Bu kural, geçmişte yaşanan bir sorun yüzünden: büyük dosyaları geçmişten
temizlemek zorunda kaldığımız için baştan konuyor.

## Plan ve karar noktaları

Sıra bilerek böyle: **baseline ölçülmeden hiçbir tasarım kararı verilmez.**

| Gün | İş | Karar |
|---|---|---|
| 1 | Kurulum, veri, **kaba baseline**, fizibilite | Hangi veri, kaç şirket, baseline hattı, cevap metriği |
| 2 | Chunking ve parse | Sabit boy mu, yapıya göre mi. Tablolar nasıl tutulur |
| 3 | Retrieval | Yoğun (BGE-M3), BM25 veya hibrit. Reranker gerekli mi |
| 4 | Metrik setini genişletme | Recall@k, MRR, nDCG, cevap doğruluğu — hepsi tek protokolde |
| 5 | Fine-tune | Fayda var mı, hangi veriyle, hangi kayıp fonksiyonu |
| 6 | Üretim | Hangi LLM (T4 sınırında), prompt, atıf gösterimi |
| 7 | Toparlama | Hata analizi, README, `cv_dogrulama.md` kaydı, CV maddesi |

### Gün 1 neden bu kadar dolu

Üç şey gün 1'de bitmezse sonraki günler ölçüye dayanmaz:

**Kaba baseline.** Sabit 512 token chunk + BM25 + hazır BGE-M3, hiçbir ayar yok.
Bu bir "iyi sistem" değil, bir **sıfır noktası**. Gün 2 ve 3'teki her karar bu
sayıya karşı ölçülür. Baseline gün 4'te kurulursa, gün 2-3 kararları ölçüsüz
verilmiş olur.

**Fine-tune fizibilitesi.** BGE-M3, XLM-RoBERTa-large tabanlı (~568M parametre).
Kontrastif eğitimde batch size doğrudan in-batch negatif sayısı demektir; T4'ün
16 GB'ında gradient checkpointing ve FP16 ile sığar ama batch küçük kalabilir.
20 dakikalık bir koşuyla azami batch'i **şimdi** ölç. Sığmazsa yedek plan
`bge-base` veya `bge-small` — daha küçük model, daha büyük batch, muhtemelen
daha iyi sonuç.

Gün 5'e gelip "sığmıyor" demek projeyi çökertir.

**Cevap metriği tanımı.** FinanceBench cevapları çoğunlukla sayısal. Tam eşleşme
mi, sayısal tolerans mı, LLM-judge mi? Bu karar gün 6-7'nin tamamını belirler ve
sonradan değişirse önceki tüm ölçümler geçersiz olur.

## Karar günlüğü

Her karar `KARAR_GUNLUGU.md` dosyasında, gerekçesiyle birlikte kaydedilir.
Her karar gerekçesiyle kayıtlıdır.

## Durum (2026-10-01)

Ayrıntılı gerekçe, ön kayıtlı deneyler ve tüm sayılar `KARAR_GUNLUGU.md` içinde.

| Konu | Sonuç |
|---|---|
| Veri | FinanceBench 150 soru, 32 şirket (sorularda), 360 belge, 53.399 sayfa; FinQA 8.281 örnek |
| Sızıntı | Aynı sayfa/metin örtüşmesi yok (metin yöntemi doğrulandı); aynı rapor: 2 soru, FinQA'dan 22 örnek eğitimden çıkarılır |
| Değerlendirme | FinanceBench 99 geliştirme + 51 kilitli (şirket bazında); kilitli küme final ölçüme kadar kullanılmaz |
| Dense vs BM25 | Dense net üstün; dört dense model birbirinden ayırt edilemiyor |
| Reranker | Anlamlı kazanç (ortak havuz 5/5, tek belge 4/5) |
| Künye, hibrit (BM25) | İkisi de ön kayıtlı ölçütle **reddedildi** |
| Hat | dense ilk aşama + bge-reranker-v2-m3 |

Açık: chunking karşılaştırması, fine-tune, cevap üretimi ve metriği (Karar 2 revize edilecek),
SEC EDGAR kararı (varsayılan: kapsam dışı), kilitli test ölçümü.

Sınırlılıklar: 99 soruluk geliştirme kümesi küçük (güven aralıkları geniş); ön-eğitilmiş
modellerin SEC metnini görmüş olma ihtimali doğrulanamaz; geliştirme kümesi çok sayıda
karşılaştırmada kullanıldı; reponun belge listesinde olmayan 8 ek PDF korpusa alınmadı
(hiçbir soru onlara bağlı değil).

## Negatif sonuç da bir sonuçtur

Fine-tune fayda vermeyebilir. O durumda **ölçülür ve raporlanır.** Önceki bir projede
Focal Loss ve Class-Balanced Loss'un başarımı artırmadığını raporlamak değerliydi;
Bu yaklaşım raporlamaya değer.

Bu satır buraya, gün 5'te sonucu zorlama baskısı doğmasın diye yazıldı.

## Yeniden üretilebilirlik

- `requirements.txt` sürüm sabitli
- Seed sabitlenir, kaç seed koşulduğu raporlanır
- Veri manifestosu: dosya listesi + hash, `sonuclar/` altında
- Her ölçüm `sonuclar/` altına tarih ve konfigürasyonla yazılır

## Yapılacaklar dışı (kapsam sınırı)

- Canlı üretim servisi, kullanıcı arayüzü, kimlik doğrulama
- Türkçe finans verisi
- Ticari kullanım (FinanceBench lisansı yasaklıyor)
- Ham verinin repoya eklenmesi

## Klasör düzeni

```
finans_rag/
├── README.md              bu dosya: plan, kısıtlar, durum
├── KARAR_GUNLUGU.md       her kararın ve deneyin gerekçesi, ön kayıtlar, sonuçlar
├── requirements.txt
├── data/
│   ├── ham/               indirilen veri (gitignore)
│   └── islenmis/          sayfa metinleri, chunk'lar, gömüler, sıralamalar (gitignore)
├── src/                   indirme, parse, chunk, retrieval, rerank, değerlendirme betikleri
├── tests/                 değerlendirme ve RRF kodunun doğruluk testleri
├── notebooks/             Colab defterleri
└── sonuclar/              ölçümler, veri manifestosu, sızıntı raporları, ortam kaydı
```
