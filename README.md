# Ölçülmüş Finans RAG'i

SEC dosyalarından (10-K, 10-Q, 8-K) finansal soruları cevaplayan bir RAG hattı. Her bileşen ölçümle seçildi.
Her deney sonuçtan önce yazılı ölçütle kayıt altına alındı. Olumsuz sonuçlar da raporlandı.

Cevaplar Gemini API ile üretilir. Arama yerelde çalışır (e5-base-v2 + bge-reranker-v2-m3).
Değerlendirme FinanceBench üzerinde, cevap düzeyinde yapılır.

## Sonuç (kilitli test)

51 soru, 11 şirket. Küme baştan ayrıldı ve tek seferde ölçüldü. Sıkı puanlama: "kısmen" yanlış sayılır.

| Okuyucu model | Kapalı kitap (K0) | **Nihai sistem (K1)** | Oracle sayfa (K2) |
|---|---|---|---|
| gemini-3.5-flash-lite | 0,431 | **0,627** | 0,647 |
| gemini-3.8-flash | 0,627 | **0,765** | 0,843 |

- K0: model belge görmez. K1: sistemin bulduğu ilk 1000 kelime. K2: altın kanıt sayfası (üst sınır).
- Nihai sistem − kapalı kitap, %95 aralık (şirket-kümeli bootstrap): flash-lite **+0,196 [+0,024; +0,356]**, 3.8-flash **+0,137 [−0,024; +0,262]**.
- Ön kayıtlı sonuç: **kısmen desteklendi.** Zayıf okuyucuda kanıt var. Güçlü okuyucuda yön pozitif, ama 51 soru yetmedi. Yumuşak puanlamada ("kısmen" doğru) iki okuyucuda da alt sınır 0'ın üstünde.
- Retrieval: Recall@1000w 0,532. Altın sayfa 31/51 soruda bağlama girdi.
- Bağlamda olmayan (uydurma) atıf yok.

Ayrıntı, sınırlar ve tüm sayılar: [KARAR_GUNLUGU.md](KARAR_GUNLUGU.md) (Karar 14).

## Hat

```
PDF → sayfa → 200 kelimelik chunk (sayfa sınırlı)
soru → belge yönlendirme (şirket + yıl kuralları) → e5-base-v2 tam arama (ilk 100)
     → bge-reranker-v2-m3 (derinlik 50) → ilk 1000 kelime → Gemini (prompt v3) → cevap + atıf
```

Bir bağlam bütçesi kullanılır: her sistem aynı 1000 kelimeyi alır. Karşılaştırmalar adil kalır.

## Neyi ölçtük, ne çıktı (geliştirme kümesi: 99 soru, 21 şirket)

| Karar | Sonuç |
|---|---|
| Dense mi, BM25 mi | Dense net üstün. Dört dense model birbirinden ayırt edilemedi (e5-base-v2 seçildi) |
| Reranker | Anlamlı kazanç |
| Chunk boyu | 200 kelime kaldı |
| Künye (başlıkta belge adı) ve BM25 hibriti | İkisi de ön kayıtlı ölçütle **reddedildi** |
| Vektör veritabanı | Chroma (HNSW), tam aramayla ilk-50 örtüşmesi 0,98. Nihai testte kullanılmadı: yönlendirme filtresi doğrulanmadı |
| Belge yönlendirme (şirket + yıl) | Recall@1000w 0,409 → 0,504 (anlamlı). Cevap doğruluğuna tek başına anlamlı katkı yok |
| Prompt v3 ("bağlam yetmezse kendi bilginle cevapla, belirt") | Güçlü okuyucuda +0,081 [+0,034; +0,132] anlamlı. Uydurma atıf artmadı |

Geliştirme doğruluğu (sıkı, 99 soru): kapalı kitap 0,323 / 0,545 → nihai sistem 0,576 / 0,667 → oracle 0,768 / 0,818 (flash-lite / 3.8-flash).

## Cevap metriği

Katmanlı. Önce deterministik kurallar:
- Sayısal cevap: altın ondalıkların hassasiyeti.
- Evet/Hayır cevabı: hüküm eşleşmesi.
- Birden fazla anahtar sayı: hepsi bulunmalı.
- Serbest metin: yargıç model (gemini-3.7-flash, okuyucu değil). Yargıç, insan puanlarına karşı kalibre edildi: 128 cevapta ikili uyum 0,945.

Atıf metrikleri ayrı raporlanır: isabet, kesinlik, bağlamda bulunma.

## Dürüst sınırlar

- 51 test sorusu ve 11 şirket. Aralıklar geniş. "Etki yok" değil, "kanıt yetersiz" denebilir.
- Kilitli testte 306 cevabın 90'ı yargıç modelle puanlandı. Yargıç hafif katı. Tek bir insan puanlayıcıyla kalibre edildi. Yargıç ve okuyucu aynı model ailesinden.
- Geliştirme kümesinde ardışık birkaç müdahale denendi. İyimserlik riski var. Kilitli testte beklenen düşüş görülmedi, ama bu kümenin daha kolay olması da mümkün.
- Başlangıç hattının (yönlendirmesiz, prompt v2) üstünlüğü yalnız geliştirme kümesinde gösterildi. Kilitli testte çalıştırılmadı.
- Ön-eğitilmiş modellerin SEC metnini görmüş olma ihtimali doğrulanamaz.
- Fine-tune yapılmadı. İsteğe bağlı ek olarak ertelendi (Karar 11).

## Maliyet

Okuyucu ve yargıç API çağrılarının toplamı yaklaşık 239 TL (≈ 4,35 USD). Önceden konan sınır 350 TL.
Her çağrı önbelleğe yazılır. Harcama tavanı koddadır.

## Veri

| Veri | Rol | Lisans |
|---|---|---|
| FinanceBench | Değerlendirme: 150 soru, 360 belge, 53.399 sayfa | CC-BY-NC-4.0 (ticari kullanım yok) |
| FinQA | Fine-tune için ayrılmıştı, kullanılmadı | MIT |

Veri repoda **yok** (`data/` gitignore'da). FinanceBench PDF'lerini repoya koymak yeniden dağıtım sayılır.
Veriyi `src/veri_indir.py` ile lokalde indir. Aynı sayfa ve metin örtüşmesi için sızıntı denetimi yapıldı. Bölme şirket bazında: 99 geliştirme + 51 kilitli.

## Yeniden üretme

1. `pip install -r requirements.txt` (sürümler sabit).
2. `GEMINI_API_KEY` ortam değişkenini ayarla. Anahtar koda veya repoya girmez.
3. Çalıştırma sırası ve ön kayıtlar `KARAR_GUNLUGU.md` içinde. Ana betikler:
   - `src/degerlendir.py`: retrieval metrikleri, eşleştirilmiş şirket-kümeli bootstrap, kilitli küme koruması.
   - `src/yonlendirme.py`, `src/rerank.py`, `src/baglam_hazirla.py`: arama hattı ve istekler.
   - `src/okuyucu_gemini.py`: okuyucu (önbellek, harcama tavanı, dry-run varsayılan).
   - `src/yargic_gemini.py`: yargıç ve kalibrasyon.
   - `src/kilitli_hazirla.py`, `kilitli_calistir.py`, `kilitli_olc.py`: tek seferlik kilitli test.
4. `python tests/test_cevap_metrik.py` ve diğer `tests/` dosyaları API'siz çalışır (sahte istemci).

Kilitli küme bir kez kullanıldı. Aynı küme ikinci kez ölçüm için kullanılamaz.

## Lisans

Kod: MIT ([LICENSE](LICENSE)). Veri bu repoda yok. FinanceBench'in kendi lisansı geçerlidir (CC-BY-NC-4.0, ticari kullanım yok).
Veri kaynağı: Patronus AI, FinanceBench. FinQA: MIT.

## Klasör düzeni

```
finans_rag/
├── README.md
├── LICENSE            MIT (yalnız kod)
├── KARAR_GUNLUGU.md   her karar ve deney: gerekçe, ön kayıt, sonuç
├── requirements.txt
├── src/               indirme, parse, retrieval, okuyucu, yargıç, ölçüm betikleri
├── tests/             API'siz testler
├── sonuclar/          ölçüm çıktıları (JSON), dondurulmuş prompt'lar
└── data/              ham ve işlenmiş veri (gitignore)
```
