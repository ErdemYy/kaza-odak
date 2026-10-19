# SafeRoute 3D — Faz 3 Teknik Raporu: Mekânsal Kümeleme

> Tarih: 2026-10-19 · Veri sürümü `raw:2fe1297c24f7|p2cfg:c7ffbfdc478d|p2:2.1.1` ·
> İşlem sürümü `phase3-code:3.0.0|phase3-config:977132f9821d`
> Otomatik deney raporu: [`reports/phase3/KUMELEME_RAPORU.md`](../../reports/phase3/KUMELEME_RAPORU.md) ·
> Defter: [`notebooks/03_clustering_experiments.ipynb`](../../notebooks/03_clustering_experiments.ipynb)

Bu rapordaki tüm sayılar deney kaydından (`experiments_registry.json`) ve `results.json`'dan alınmıştır;
defter aynı değerleri etiket dosyalarından yeniden sayarak doğrular.

## 1. Amaç ve kapsam

NYC trafik kazası verisinde (2.020.638 uygun olay, 349.122 benzersiz konum) tekrar eden mekânsal kaza
yoğunlaşmalarını bulmak; DBSCAN, K-Means ve HDBSCAN'i ortak bir değerlendirme çerçevesinde karşılaştırmak;
seçilen modelin zamansal kararlılığını ve veri kalitesine duyarlılığını ölçmek; Faz 4 için sürümlü sonuç
dosyaları üretmek.

## 2. Yöntem

| Bileşen | Uygulama |
|---|---|
| Deney kaydı | Her deney deterministik kimlikle (`algoritma + parametre + öznitelik seti + kapsam + veri sürümü`) kaydedilir; başarılı ve etiket dosyası mevcut deney yeniden çalıştırılmaz. |
| Yalıtım | Her deney ayrı bir süreçte (spawn) çalışır; bellek tepe değeri deneye aittir, bellek hatası ana süreci düşürmez. |
| Bellek kapısı | Deney başlamadan önce ≥ 3.500 MB boş fiziksel bellek ve ≤ 300 milyon komşu çifti şartı; sağlanmazsa `skipped_resource_limit` olarak kaydedilir, sonuç uydurulmaz. |
| Kontrol noktası | Her aşamadan sonra `results_checkpoint.json` (yapılandırma SHA-256 + veri sürümüyle bağlı) atomik olarak yazılır. |
| DBSCAN | Haversine, `[lat_rad, lon_rad]`, benzersiz konum + `sample_weight` (kayıt düzeyiyle eşdeğerliği gerçek veride gösterildi). |
| K-Means | EPSG:32618 metre, ağırlıklı, `n_init=10`. |
| HDBSCAN | `sample_weight` desteklemediği ve ~karesel ölçeklendiği için 100.000 olaylık sabit tohumlu örneklem. |
| Ortak değerlendirme | HDBSCAN örneklemiyle aynı 100k olay; siluet ve Davies–Bouldin gürültü hariç, tabakalı 20k örneklem; DBCV 4k örneklem. |
| Seçim ölçütleri | Sonuçlardan **önce** tanımlandı: en büyük küme ≤ %5, ≥ 20 küme; DBSCAN için komşu ızgara ARI, eşitlikte siluet; K-Means için siluet; HDBSCAN için DBCV. |

## 3. Deney envanteri

| Aşama | Başarılı | Kaynak sınırı | Not |
|---|---:|---:|---|
| Eşdeğerlik (kayıt vs ağırlıklı) | 34 | 1 | Tam veri kayıt düzeyi (eps=50, ms=10): tahmini 310,7 M komşu çifti > 300 M sınır, çalıştırılmadı |
| DBSCAN ızgarası (5 eps × 4 ms) | 20 | 0 | |
| K-Means ızgarası (k ∈ {5,10,20,40,80}) | 5 | 0 | |
| HDBSCAN ızgarası (4 mcs × 3 ms) | 12 | 0 | |
| Zamansal (13 yıl × [sabit DBSCAN, ölçekli DBSCAN, K-Means]) | 39 | 0 | |
| Veri kalitesi duyarlılığı | 4 | 0 | |
| **Toplam** | **114** | **1** | 115 kayıt |

Bu oturumda yeni model eğitilmedi: kesintiden önce tüm 115 deney kaydedilmişti (26 yıllık DBSCAN deneyinin —
13 sabit eşikli, 13 hacme ölçekli — tamamı dahil). Bu oturumda yalnızca kayıtlı etiketlerden çalışan yeni
**seçim incelemesi** aşaması eklendi; profiller, raporlar, tablolar ve Faz 4 dosyaları yeniden üretildi.

## 4. Sonuçlar

### 4.1 Seçilen konfigürasyonlar

| Algoritma | Parametreler | Küme | Gürültü | Siluet (ortak) | Davies–Bouldin | DBCV | Fit süresi | Kabul |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| DBSCAN | eps=25 m, min_samples=100 | 4.179 (tam veri) | 0,597 | 0,945 | 0,090 | 0,394 | 3,9 sn | ✓ |
| K-Means | k=5 | 5 | 0 (tanım gereği) | 0,458 | 0,691 | −0,852 | 0,8 sn | ✗ (en büyük küme %28) |
| HDBSCAN | min_cluster_size=25, min_samples=25 | 768 (100k örneklem) | 0,547 | 0,601 | 0,477 | 0,260 | 68,9 sn | ✓ |

DBSCAN için haversine siluet 0,945; komşu ızgara ARI 0,480. K-Means'te dirsek noktası k=20; siluet kuralı k=5'i
seçti, ancak k=5 kabul ölçütlerini sağlamaz ve yalnızca kaba bölgeleme taban çizgisi olarak raporlanır
(ölçütleri sağlayan tek K-Means k=80'dir). **Ana model: DBSCAN** (tam veride uygulanabilir, gürültüyü ayırır,
kabul ölçütlerini sağlar).

### 4.2 `eps=25 m, min_samples=100` seçiminin yeniden değerlendirilmesi

Önceki oturumdaki seçim sorgusuz kabul edilmedi. Seçim kuralı değiştirilmeden (sonradan kural değiştirmek
seçim yanlılığı yaratır), kabul edilebilir altı aday kayıtlı etiketlerinden sınandı:

| eps/ms | Küme | Gürültü | Medyan olay · konum · uzanım | Maks uzanım | >200 m küme | 13 yıl etkin | ARI | DBCV |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| 25/10 | 31.615 | 0,093 | 31 · 5 · 24 m | 1.192 m | %0,75 | %25,3 | 0,197 | 0,776 |
| 25/25 | 19.619 | 0,205 | 53 · 6 · 30 m | 488 m | %0,22 | %42,5 | 0,357 | 0,718 |
| 25/50 | 10.462 | 0,376 | 86 · 7 · 37 m | 315 m | %0,05 | %67,5 | 0,440 | 0,576 |
| **25/100** | **4.179** | **0,597** | **151 · 8 · 41 m** | **174 m** | **%0,00** | **%85,0** | **0,480** | **0,394** |
| 50/50 | 7.134 | 0,213 | 97 · 12 · 103 m | 7.544 m | %17,80 | %72,2 | 0,301 | 0,337 |
| 50/100 | 4.570 | 0,396 | 153 · 14 · 109 m | 4.394 m | %16,21 | %86,1 | 0,290 | 0,352 |

- **Yoğunluk zincirlenmesi:** eps=50 m adaylarında kümeler cadde boyunca birleşir (98.152 olaylık, 7,5 km'lik
  küme). eps=25/ms=100'de hiçbir küme 200 m'yi aşmaz; zincirlenme yoktur.
- **Coğrafi anlamlılık:** medyan küme 8 benzersiz konum ve 41 m uzanımdır (kavşak ölçeği). Tek koordinattan
  oluşan küme payı %0,7; kümeler salt tekrar eden geokod değildir. Haritada kümeler bulvar ve kavşak
  dizilimlerini izler.
- **Küme büyüklüğü:** medyan 151, en büyük 1.444 olay (%0,07); tek bir küme sonuçlara baskın değildir.
- **Zaman kararlılığı:** kümelerin %85'i 13 yılın tamamında, %97,5'i 10+ yılda etkindir; ardışık yıl
  Spearman korelasyonu 0,50–0,80.
- **Bedel ve yorum sınırı:** olayların %59,7'si gürültüdür. Model şehrin tamamını değil, **kronik kavşak
  ölçeğindeki yoğunlaşmaları** temsil eder. Siluetin 0,945 çıkması kümelerin kompakt ve birbirinden uzak
  olmasından kaynaklanır; yoğunluk geçerliliği (DBCV) min_samples arttıkça düşer (0,776 → 0,394). Daha geniş
  kapsam gerekiyorsa eps=25/ms=50 (gürültü %37,6, zincirlenme yok denecek kadar az, ARI 0,440) en makul
  alternatiftir; bu, Faz 4'te karar verilecek bir kullanım tercihidir, Faz 3 seçimi değişmez.

**Sonuç:** seçim; zincirlenme olmaması, kavşak ölçeği ve zamansal süreklilik bakımından gerekçelidir. Yüksek
gürültü oranı bir kusur değil, modelin "kronik sıcak nokta" tanımının açık bir sonucudur ve Faz 4'te bu şekilde
etiketlenmelidir.

### 4.3 Zamansal kararlılık ve kaza hacmi

| Dönem | Yıllık olay (medyan) | (a) Sabit eşik küme (medyan) | (c) Ölçekli ms | (c) Küme (medyan) | (c) Jaccard (medyan) |
|---|---:|---:|---|---:|---:|
| 2013–2019 | 192.150 | 13 | 9–11 | 4.251 | 0,555 |
| 2020–2025 | 91.047 | 0 | 4–5 | 5.256 | 0,416 |

**Zamansal kararlılık ile hacim değişimi farklı olgulardır.** (a) Sabit eşikte `min_samples=100` tam veri
(13,5 yıl) için seçilmiştir; tek bir yılın hacmiyle 25 m içinde 100 olaya ulaşan konum çok azdır (gürültü
≥ 0,984). 2020 sonrası olay hacmi yaklaşık yarıya inince küme sayısı 0–1'e düşer ve Jaccard 2022–2024'te
tanımsız kalır. Bu düşüş sıcak noktaların kaybolduğunu değil, eşiğin yıllık hacme göre çok yüksek olduğunu
gösterir; (a) bu nedenle kararlılık ölçüsü olarak kullanılmamalıdır. (a)'nın 2020'deki %100'lük "önceki yıl
kümesinde" oranı tek bir kümeye dayanır ve anlamsızdır.

(c) Hacme ölçekli eşikte küme sayısı yıllar boyunca benzer düzeyde kalır (≈4–6 bin), ardışık yıl Jaccard
medyanı 0,555'ten 0,416'ya iner. Bu daha küçük düşüş hacim etkisinden büyük ölçüde arındırılmış mekânsal
değişimdir; ancak eşik 4–5'e indiğinde rastlantısal küçük kümeler de oluşabildiği için bir kısmı ölçüm
gürültüsüdür. Hacimden bağımsız en doğrudan ölçü (b) kalıcılıktır: tam veri kümelerinin %85'i her yıl,
%97,5'i en az 10 yıl etkindir; üst-50 kümenin ardışık yıl örtüşmesi %40–78. K-Means (k=5) merkezleri
yıllar arasında medyan 69–215 m kayar (2020'de 600 m).

### 4.4 Veri kalitesi duyarlılığı

| Varyant | Hariç olay | Küme | Gürültü | ARI (ortak olaylar) | Korunan temel küme |
|---|---:|---:|---:|---:|---:|
| Yedek geokodlama şüphesi hariç | 1.844 | 4.175 | 0,598 | 0,9997 | %99,9 |
| İlçe çelişkisi hariç | 2.365 | 4.173 | 0,597 | 0,9996 | %99,9 |
| Kıyıya yakın hariç | 9.394 | 4.152 | 0,598 | 1,0000 | %100,0 |
| Tekrar ağırlığı 99. yüzdelikte (73) kırpılmış | 0 | 4.059 | 0,607 | 0,974 | %97,1 |

Kalite bayraklı kayıtlar sonuçları pratikte değiştirmez. En büyük etki tekrar ağırlığı kırpmadadır (120 küme
kaybı): bazı kümeler tek koordinatta yoğunlaşan tekrar kayıtlarına dayanır; Faz 4'te bu kümeler
`n_unique_locations` ile ayırt edilebilir.

### 4.5 En önemli gerçek kaza kümeleri (seçilen DBSCAN, olay sayısına göre)

4.179 küme toplam 814.578 olay, 207.412 yaralanmalı ve 1.324 ölümlü kazayı içerir.

| # | Olay | Konum | İlçe | Merkez | Yaralanmalı | Ölümlü | Zirve saat | Başlıca cadde / kesişen |
|---:|---:|---:|---|---|---:|---:|---:|---|
| 1 | 1.444 | 10 | Brooklyn | 40.69603, −73.98453 | 203 | 1 | 12 | Tillary St / Flatbush Ave Ext |
| 2 | 1.358 | 17 | Bronx | 40.82021, −73.89067 | 366 | 1 | 16 | Bruckner Blvd / Hunts Point Ave |
| 3 | 1.284 | 9 | Bronx | 40.86186, −73.91278 | 382 | 0 | 16 | W Fordham Rd / Major Deegan Expwy |
| 4 | 1.105 | 26 | Brooklyn | 40.67817, −73.89752 | 296 | 0 | 16 | Pennsylvania Ave / Jamaica Ave |
| 5 | 1.103 | 9 | Queens | 40.76220, −73.75694 | 239 | 1 | 17 | Northern Blvd / Cross Island Pkwy |
| 6 | 1.100 | 12 | Brooklyn | 40.69161, −73.99924 | 220 | 0 | 0* | Brooklyn–Queens Expwy |
| 7 | 1.099 | 16 | Brooklyn | 40.67574, −73.89686 | 264 | 1 | 16 | Pennsylvania Ave / Atlantic Ave |
| 8 | 1.018 | 14 | Brooklyn | 40.65858, −73.89063 | 295 | 2 | 14 | Pennsylvania Ave / Linden Blvd |
| 9 | 1.007 | 29 | Bronx | 40.80470, −73.91239 | 282 | 5 | 16 | Bruckner Blvd / E 138 St |
| 10 | 965 | 8 | Manhattan | 40.76060, −73.96433 | 118 | 1 | 17 | E 59 St / 2 Ave |

\* 00:00 zirvesi, Faz 2'de işaretlenen gece yarısı yuvarlama şüphesiyle (K-17) tutarlıdır; saat profili
dikkatle yorumlanmalıdır. Pennsylvania Avenue (East New York) üç ayrı kümeyle ilk 10'da yer alır.

İlçelere göre: Manhattan 1.307 küme / 259.833 olay, Brooklyn 1.150 / 223.567, Queens 1.009 / 194.308,
Bronx 560 / 110.194, Staten Island 133 / 21.672.

## 5. Faz 4 için üretilen dosyalar

`data/processed/h9gi-nx95/snapshot_20261019T155113Z/phase3/` (büyük dosyalar git dışında; bütünlük
`phase4_manifest.json` içindeki SHA-256 ile doğrulanır):

| Dosya | Satır/öğe | İçerik |
|---|---:|---|
| `cluster_points_dbscan.parquet` | 2.020.638 | olay → küme (`-1` gürültü), `is_core`, `location_id` |
| `cluster_summary_dbscan.parquet` | 4.179 | küme profilleri (merkez, zarf, yaralanma, saat, cadde) |
| `cluster_geometries_dbscan.geojson` | 4.179 | küme dışbükey zarfları (lon, lat; 15 m görselleştirme tamponu) |
| `cluster_points_kmeans.parquet` | 2.020.638 | K-Means taban çizgisi üyelikleri |
| `cluster_summary_kmeans.parquet` / `cluster_geometries_kmeans.geojson` | 5 | K-Means profilleri |
| `model_metadata.json`, `algorithm_comparison.json`, `experiments.json` | — | seçim, metrik ve kayıt |
| `phase4_manifest.json` | — | tüm dosyaların SHA-256, boyut ve satır sayısı |

Depoda izlenen kopyalar: `reports/phase3/` (ilk 200 küme CSV/GeoJSON, `tables/*.csv` akademik tablolar,
14 şekil, `results.json`, `phase4_manifest.json`).

## 6. Doğrulama

- Testler: Faz 1–3 test paketi (bkz. kapanış), birim testlerinde yapı tanıları; hat testlerinde seçim
  incelemesi, manifest SHA-256 doğrulaması, aşamalı sürdürmede yeni deney açılmaması, akademik tabloların
  yazılması.
- Defter: 21 kod hücresi hatasız; seçilen modellerin küme sayısı ve gürültü oranı etiket dosyalarından
  yeniden sayılıp `results.json` ile eşleştirildi; 39 yıllık deneyin kayıtta başarılı olduğu; profil olay
  toplamının üyeliklerle eşleştiği; Faz 4 dosyalarının SHA-256 özetleri doğrulandı.
- Şekiller: 14 şeklin varlığı ve boyutu doğrulandı; zamansal şekil (a)/(c) ölçek farkı nedeniyle symlog eksene
  ve üç panele ayrıldı, eksik yıllarda çizgiler birleştirilmez.

## 7. Bu oturumda yapılan kod düzeltmeleri

- `report.py`: şekildeki elle yazılmış "349.122" sayısı sonuçtan okunur hâle getirildi; `error=None`
  durumunda dilimleme hatası giderildi; zamansal şekil yeniden düzenlendi; akademik CSV tabloları,
  seçim incelemesi ve zamansal yorum bölümleri eklendi (tüm sayılar sonuçlardan türetilir).
- `runner.py`: `review` aşaması (kayıtlı etiketlerden, yeniden fit yok), `phase4_manifest.json`,
  `final_choice` içinde ölçekli Jaccard medyanı.
- `evaluation.py`: `structure_diagnostics` (uzanım, tek konumlu küme, etkin yıl).
- `perf.py`: iki fonksiyonda yinelenen Windows bellek yapısı tek yardımcıya toplandı. `worker.py`: çift
  `multiprocessing` importu kaldırıldı.

## 8. Sınırlılıklar

1. HDBSCAN tam veride değil 100k olay örnekleminde çalıştı; küme sayısı doğrudan karşılaştırılamaz.
2. Tam veri kayıt düzeyi DBSCAN kaynak sınırı nedeniyle çalıştırılmadı; eşdeğerlik bölgesel ve 2019 şehir
   senaryolarında gösterildi.
3. Seçilen DBSCAN olayların %59,7'sini gürültü sayar; kapsam ihtiyacı Faz 4'te ayrıca değerlendirilmelidir.
4. K-Means seçim kuralı (siluet) kabul ölçütlerini sağlamayan k=5'i seçti; K-Means yalnızca taban çizgisidir.
5. Yıllık sabit eşik (a) kararlılık ölçüsü değildir; ölçekli eşik (c) 2020 sonrasında düşük ms nedeniyle
   gürültülüdür.
6. Küme numaraları koşular arasında eşleştirilemez; yıllık karşılaştırma 100 m ızgara kapsaması üzerindendir.
7. Siluet, kompakt kavşak kümelerinde yüksek çıkar; tek başına model kalitesinin kanıtı sayılmamalıdır.
