# Faz 2 Kapanış Raporu — Veri Ön İşleme, Öznitelik Mühendisliği ve Öznitelik Seçimi

**Proje:** SafeRoute 3D · **Faz:** 2 / 7 · **Tarih:** 2026-10-19 · **Durum:** Kabul ölçütleri karşılandı; Faz 3 için onay bekleniyor

**Kaynaklar:**
- **Kaza anlık görüntüsü:** `snapshot_20261019T155113Z`, SHA-256 `2fe1297c…10be5e`
- **İlçe sınırları:** `gthc-hcne` `snapshot_20261019T170733Z`, sürüm 26b, SHA-256 `7aa44d9f…87f443c`
- **Hat:** sürüm 2.1.1, yapılandırma SHA-256 `c7ffbfdc…0f6985`

**Ayrıntılı ölçümler:** `reports/phase2/ON_ISLEME_RAPORU.md`, `reports/phase2/preprocessing_summary.json`

**Öznitelik tablosu:** `docs/feature_selection_report.md`

Bu rapordaki tüm sayılar gerçek veriden ölçülmüştür. Bu fazda **hiçbir model eğitilmedi**.

---

## 1. Gerçek veri seti boyutu

- **Ham veri:** 2.269.187 satır × 29 sütun.
- **Faz 1 sayılarının yeniden hesaplanması:** Faz 1 raporundaki 11 sayının tamamı bu koşuda ham veriden yeniden hesaplandı ve **birebir eşleşti**:
  - Satır ve sütun sayısı.
  - Kaba kutu yöntemiyle geçerli koordinat 2.020.640.
  - Eksik koordinat 240.806, sıfır koordinat 7.591, kutu dışı 150.
  - Eksik ilçe 691.375; geçerli koordinatlı ama ilçesi eksik 487.026.
  - Benzersiz geçerli konum 349.124.
  - 00:00 kayıtları 24.566; ham araç türü etiketi 3.149.
- **Ham verinin korunması:** İşlemden önce ve sonra SHA-256 doğrulaması yapıldı; ham veri değişmedi. Testler ayrıca parça dosyalarının salt-okunur kaldığını doğruluyor.

## 2. İşlenen satır sayısı

| Katman | Dosya | Satır | Sütun |
|---|---|---:|---:|
| raw | `data/raw/h9gi-nx95/snapshot_…/part-*.csv` | 2.269.187 | 29 |
| interim | `data/interim/…/crashes_interim.parquet` (39 MB) | 2.269.187 | 31 |
| processed | `data/processed/…/crashes_processed.parquet` | 2.269.187 | 87 |
| features | `data/processed/…/features/*.parquet` (7 dosya) | bkz. §13–15 | — |

Hiçbir kayıt silinmedi. Her çıktı dosyasının yanında bir yan kayıt (`.json`) bulunur ve şunları içerir:
- Kaynak SHA-256 ve ilçe sınırı SHA-256.
- Yapılandırma ve yapılandırma özeti.
- Hat sürümü.
- Satır/sütun sayısı.
- Dosya SHA-256 ve içerik özeti.

## 3. Coğrafi olarak uygun kayıt sayısı

- **Mekânsal kümelemeye uygun: 2.020.638** (%89,05).
- Bu kayıtların tamamı aynı zamanda geçerli coğrafi kayıttır. Bileşimi:
  - Resmî ilçe sınırı içinde: 2.011.244.
  - Poligon dışı ama kıyıya yakın (≤ 500 m): 9.394.

## 4. Kurtarılan ilçe bilgisi

- **478.280 kaydın** ilçesi resmî DCP poligonlarıyla (point-in-polygon) kurtarıldı. Bu, bildirilen ilçesi eksik 691.375 kaydın %69,2'si.
- **Yöntem:**
  - Benzersiz 349.140 koordinat üzerinde, hazırlanmış (prepared) poligonlarla vektörel `intersects_xy` / `contains_xy` testi yapıldı.
  - İşlemden önce iki taraf için de CRS doğrulandı: CRS84 → EPSG:4326, NYC derece aralığı kontrolü.
  - Süre: 10 saniye.

## 5. Hâlâ eksik kalan ilçe

**213.095 kayıt** ilçesiz kaldı. Nedenleri:
- Geçerli koordinat yok: 204.307.
- Poligon dışında: 8.788 kayıt. Bunlar kıyıya yakın ya da uzak noktalar ve politika gereği hiçbir ilçeye atanmadı.

## 6. İlçe uyuşmazlıkları

- **2.365 kayıt**, yani hem bildirilen hem çıkarılan ilçesi olan 1.532.964 kaydın %0,15'i. Bu kayıtlar sessizce düzeltilmedi: `borough_final` bildirilen değeri koruyor, `borough_conflict_flag` işaretli.
- **En sık çiftler:** Bronx → Manhattan 845, Queens → Brooklyn 711, Brooklyn → Queens 341.
- **Bildirilen ilçe poligonuna uzaklık:** medyan 126,8 m, %90'lık dilim 7.045 m. 895 kayıt 10 m içinde, 1.786 kayıt 1 km içinde.
- **Üç ayrı çelişki kaynağı ölçüldü:**
  1. **Sınır caddeleri:** Örneğin Brooklyn–Queens sınırındaki Wyckoff ve Cypress Avenue'da çelişkiler 0,1–1,2 m mesafede.
  2. **İdari/coğrafi ayrışma:** Marble Hill (Marble Hill Ave, Broadway/W 228 St). Polisin "Bronx" olarak bildirdiği bu bölge, resmî poligonda Manhattan'a ait.
  3. **Yedek geokodlama noktaları:** Örneğin 40.7136, −74.0091 noktasındaki 192 kaydın hepsi 2016 yılına ait, beş farklı ilçeden bildirilmiş ve Brooklyn/Queens cadde adları taşıyor.
     - Kural: aynı koordinatta en az 3 farklı bildirilmiş ilçe.
     - Bu kurala göre **15 konum, 1.844 kayıt** `geocode_fallback_suspect_flag` ile işaretlendi.
     - Kayıtlar silinmedi; Faz 3'te bu kayıtlarla ve onlarsız duyarlılık analizi yapılacak.

## 7. Geçersiz koordinat dağılımı

Durumlar birbirini dışlar; her kayda açıklayıcı bir `coordinate_quality_status` atanır:

| Durum | Kayıt | Kümeleme |
|---|---:|:---:|
| Eksik (`missing`) | 240.806 | ✗ |
| Ayrıştırılamaz (`unparseable`) | 0 | ✗ |
| Sonlu değil (`non_finite`) | 0 | ✗ |
| Sıfır (`zero`) | 7.591 | ✗ |
| Geçersiz aralık (`invalid_range`, \|enlem\|>90 veya \|boylam\|>180) | 106 | ✗ |
| NYC dışı, uzak (> 500 m; maks. ≈ 3.608 km) | 46 | ✗ |
| Poligon dışı, kıyıya yakın (≤ 500 m) | 9.394 | ✓ (ilçe atanmaz) |
| Sınırda belirsiz (≥ 2 ilçe) | 0 | ✓ |
| Resmî ilçe sınırı içinde | 2.011.244 | ✓ |

- **Kıyı tamponu:** Poligon dışı noktaların uzaklığı medyan 33,5 m, %99'luk dilim 470,8 m. 500–1000 m arasında hiç nokta yok; 500 m eşiği bu doğal kırılmaya dayanıyor.
- **Çakışan nedenler** (raporlandı):
  - Geçersiz koordinat ∧ ilçe eksik: 204.351.
  - Geçersiz koordinat ∧ 00:00: 1.850.
  - Geçersiz koordinat ∧ yaralı bayrağı ≠ ok: 741.
- **Alanlar:** `exclusion_reason`, `is_valid_geographic_record`, `eligible_for_spatial_clustering`.

## 8. Tekrarlanan koordinat analizi

- **Genel tablo:** Kümelemeye uygun 2.020.638 kayıt **349.122 benzersiz konumda** toplanıyor. Konum başına ortalama 5,79 kayıt (medyan 1, en fazla 887).
- **Tekrar oranı:** Tekrarlı konum sayısı 149.166; kazaların **%90,10'u** bu konumlarda.
- **En çok tekrarlanan konumlar:**
  - Verrazzano Köprüsü üst katı (887 kaza; ilçesiz, poligon dışı).
  - Tillary St / Flatbush Ave Ext (Brooklyn, 712 kaza).
  - W Fordham Rd / Major Deegan Expwy (Bronx, 685 kaza).
- **İlçelere göre tekrarlı konumlar:** Brooklyn 44.367 konum / 548.224 kaza, Queens 46.744 / 518.326, Manhattan 23.785 / 391.741, Bronx 23.546 / 270.553, Staten Island 10.578 / 83.866, ilçesiz 146 / 7.972.
- **DBSCAN etkisi:** Ağırlığı `min_samples` değerine ulaşan bir konum, `eps` ne olursa olsun tek başına çekirdek noktadır:

  | min_samples | Tek başına çekirdek olan konum | Bu konumlardaki kaza |
  |---:|---:|---:|
  | 5 | 72.012 | 1.622.685 |
  | 10 | 44.920 | 1.444.170 |
  | 20 | 23.820 | 1.154.779 |
  | 50 | 6.889 | 645.860 |
  | 100 | 1.980 | 315.968 |

  Bu yüzden Faz 3'te `min_samples` parametre duyarlılığının odağı olacak.
- **Strateji:** Kayıtlar silinmedi. Benzersiz konum + ağırlık (= olay sayısı) temsili ayrıca hazırlandı (bkz. §13–14).
  - scikit-learn 1.9.1 imzaları doğrulandı: `DBSCAN.fit` ve `KMeans.fit` `sample_weight` destekliyor, `HDBSCAN.fit` desteklemiyor.
  - Ağırlıklı DBSCAN'in kayıt düzeyiyle **aynı bölümlemeyi** verdiği sentetik testte doğrulandı.

## 9. Tarih/saat ve anomali işlemleri

- **Üretilen öznitelikler:** `crash_year`, `crash_month`, `crash_day`, `crash_hour`, `crash_minute`, `day_of_week`, `is_weekend`, `time_period`, `hour_sin/cos`, `month_sin/cos`, `dow_sin/cos`, `days_since_epoch`.
- **Döngüsel kodlama:**
  - Saat: `2π·(saat + dakika/60)/24`. 23:59 ile 00:01 arasındaki çember uzaklığı 0,0087, 00:00 ile 12:00 arasındaki 2,0.
  - Ay: `2π·(ay−1)/12`.
  - Gün: `2π·gün/7`.
  - Gerçek veride sin² + cos² = 1 doğrulandı.
- **Gün dilimleri:** gece (00–06) 240.343, sabah (06–12) 592.449, öğleden sonra (12–18) 862.976, akşam (18–24) 573.419.
- **00:00 analizi:**
  - 24.566 kayıt (%1,08) `midnight_suspect_flag` ile işaretlendi.
  - Ölçüt "tam saat yığılma oranı", yani HH:00 sayısının o saatin diğer dakikalarının ortalamasına oranı.
  - Tüm saatlerde tam saate yuvarlama var: diğer saatlerin oranı medyan 13,31, en yüksek 15,71.
  - 00:00'da oran **28,29**, yani genel yuvarlamanın yaklaşık iki katı. Bu, 00:00 kayıtlarının bir kısmının "saat bilinmiyor" yer tutucusu olabileceğini gösteriyor; ama hangilerinin olduğu ayırt edilemiyor.
  - **Karar:** Kayıtlar silinmedi ve saatleri değiştirilmedi. Mekânsal A/B/C modelleri saati kullanmadığı için etkilenmiyor. D modeli için 00:00 hariç duyarlılık seti (1.997.922 satır) üretildi.

## 10. Araç türü eşleme sonuçları

- **Etiket sayıları:** Ham **3.149** → normalize (kırpma, boşluk tekleme, büyük harf) **2.165** → **12 üst kategori**.
- **Kurallar:** 15 sıralı ve açık düzenli ifade kuralı uygulanıyor; ilk eşleşen kazanır. Örnekler: E-BIKE önce elektrikli mikromobiliteye eşlenir (bisiklete değil), FDNY TRUCK önce acil durum aracına (kamyona değil).
- **Eşleşmeyenler:** **1.473 etiket**, etiket geçişlerinin %0,14'ü. Bunlar `OTHER/unmatched` olarak tutuldu ve zorla atanmadı. En sık olanlar: `STANDING S` 1.413, `UN/C` 245, `ESST` 199.
- **Kategoriler** (beş araç sütunundaki etiket geçişi):
  - Binek otomobil 2.041.765, SUV/station wagon 1.280.685, kamyon/ticari 291.719, taksi/kiralık 181.229.
  - Bilinmiyor 106.872, bisiklet 78.703, otobüs 75.905, van 71.626, diğer 54.085.
  - Motosiklet 40.690, elektrikli mikromobilite 20.893, acil durum 18.079.
- **Kaza düzeyinde filtre bayrakları:** `involves_<kategori>`. Örneğin bisiklet içeren kaza 77.651, elektrikli mikromobilite içeren 20.686.
- **Tablolar:** `reports/phase2/vehicle_type_mapping.csv` (tam eşleme), kurallar ise `saferoute/preprocess/vehicles.py` dosyasında.

## 11. Oluşturulan yeni öznitelikler (processed katmanı, 56 yeni sütun)

- **Coğrafi:** `coord_parse_status`, `coordinate_quality_status`, `on_boundary_line`, `distance_outside_nyc_m`, `is_valid_geographic_record`, `eligible_for_spatial_clustering`, `exclusion_reason`
- **İlçe:** `borough_original`, `borough_inferred`, `borough_final`, `borough_source`, `borough_conflict_flag`, `borough_inference_status`
- **Konum:** `lat_rad`, `lon_rad`, `x_m`, `y_m`, `location_id`, `location_reported_borough_count`, `geocode_fallback_suspect_flag`
- **Zaman:** §9'daki 13 alan + `midnight_suspect_flag`
- **Araç:** `vehicle_category_1..5`, 12 adet `involves_<kategori>`, `vehicle_count_reported`
- **Yaralanma:** `injury_data_quality_flag`, `fatality_data_quality_flag`, `has_reported_injury` (558.805), `has_reported_fatality` (3.494), `injury_component_sum`, `fatality_component_sum`

Yaralı/ölü bayrakları (ham değerlerin üzerine yazılmadı):

| Bayrak | Yaralı | Ölü |
|---|---:|---:|
| Tutarlı | 2.258.255 | 2.260.190 |
| Toplam > alt alanlar | 10.687 | 78 |
| Toplam < alt alanlar | 227 | 6 |
| Toplam eksik | 18 | 8.913 |
| Negatif / alt alan eksik | 0 / 0 | 0 / 0 |

## 12. Elenen veya yalnızca filtrede kullanılan öznitelikler

| Öznitelik | Karar | Neden |
|---|---|---|
| `collision_id` | Model dışı (izlenebilirlik anahtarı) | Kimlik; mesafe uzayında anlamsız |
| `location` | Model dışı, interim'e taşınmadı | `latitude`/`longitude` ile birebir aynı: 2.028.381 karşılaştırmanın tamamı eşit, fark 0 (adres önekli Socrata biçimi dahil) |
| `borough_original`, `borough_final`, `zip_code` | Yalnızca filtre | Konumun türevi; modele eklenirse coğrafyayı iki kez kodlar; yaklaşık %30 eksik |
| Sokak adları (3 sütun) | Yalnızca yorum | Yüksek kardinaliteli serbest metin |
| Araç türü ve faktör (10 sütun) | Filtre ve küme profili | Kategorik; mekânsal soruya ait değil; faktörlerin %33'ü "Unspecified" |
| Yaralı/ölü (8 sütun) | Küme profili (sonuç değişkeni) | Bkz. §22 |
| Doğrusal `crash_hour`, `crash_month`, `day_of_week` | Filtre | Döngüsel süreksizlik; D modelinde sin/cos kullanılıyor |
| `month_sin/cos` | D'nin ilk sürümünde kullanılmıyor | D kapsamı: konum + gün + saat |

## 13. DBSCAN için hazırlanan matris (Model A)

- **`A_dbscan_haversine.parquet`:** 2.020.638 × [`lat_rad`, `lon_rad`]
  - Anahtar `collision_id`. Sütun sırası scikit-learn haversine için [enlem, boylam].
  - Değer aralığı: lat_rad 0,70684–0,71406, lon_rad −1,29599 – −1,28632. NaN yok, tüm değerler sonlu.
- **`A_dbscan_haversine_weighted.parquet`:** 349.122 × [`lat_rad`, `lon_rad`] + `weight`. Ağırlık toplamı 2.020.638; kullanım `fit(X, sample_weight=weight)`.
- **`eps` dönüşümü:** `eps_rad = eps_m / 6 371 008,8`. Örnekler: 50 m → 7,848·10⁻⁶; 100 m → 1,570·10⁻⁵; 200 m → 3,139·10⁻⁵.
- **Testlerle doğrulananlar:**
  - Sütun sırası: ters sıra yakalanıyor.
  - scikit-learn `haversine_distances` ile bizim Haversine'imiz 10⁻⁹ göreli farkla eşleşiyor.
  - Bilinen mesafeler (1° enlem = 111.195 m).

## 14. K-Means için hazırlanan matris (Model B)

- **`B_kmeans_projected.parquet`:** 2.020.638 × [`x_m`, `y_m`], EPSG:32618 (WGS 84 / UTM zone 18N). Değer aralığı: x 563.123–609.722 m, y 4.483.412–4.529.666 m.
- **Ağırlıklı sürüm:** `B_kmeans_projected_weighted.parquet`, 349.122 satır.
- **Projeksiyonun uygunluğu:**
  - Kullanım alanı 78°B–72°B; noktaların tamamı bu alanın içinde.
  - Gidiş-dönüş hatası en fazla 2,8·10⁻⁹ m.
- **Doğruluk** (WGS84 elipsoidi üzerindeki jeodezik mesafeye göre, 19.998 rastgele çift, tohum 0):
  - UTM Öklid hatası medyan **%0,030**, en fazla %0,035. İşaret negatif; ölçek faktörünün 1'in altında olmasıyla tutarlı.
  - Karşılaştırma için küresel Haversine'in hatası medyan %0,11.

## 15. HDBSCAN için hazırlanan matris (Model C) ve deneysel Model D

- **`C_hdbscan_haversine.parquet`:** 2.020.638 × [`lat_rad`, `lon_rad`], metrik haversine.
  - scikit-learn HDBSCAN `sample_weight` desteklemediği için yalnızca kayıt düzeyi kullanılmalı.
  - Benzersiz konuma indirgemek çekirdek mesafelerini değiştirir, yani eşdeğer değildir.
  - Alternatif temsil: `x_m`/`y_m` + Öklid uzaklığı (KD-ağacı; UTM hatası %0,03).
- **`D_spatiotemporal_experimental.parquet`:** 2.020.638 × [`x_m`, `y_m`, `days_since_epoch`, `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`], ayrıca `midnight_suspect_flag`.
  - 00:00 hariç duyarlılık seti 1.997.922 satır.
  - **Mesafe:** Ayrı eşikli komşuluk (ST-DBSCAN benzeri): `mesafe_m ≤ eps_s` **ve** `|Δgün| ≤ eps_t`, isteğe bağlı olarak döngüsel saat farkı ≤ `eps_h`. Metre ile zaman keyfi bir katsayıyla toplanmıyor.
  - D farklı bir soruyu yanıtladığı için A/B/C ile aynı değerlendirme bağlamında doğrudan karşılaştırılamaz.

## 16. Notebook doğrulama sonucu

- **`notebooks/02_preprocessing_feature_engineering.ipynb`:** 15 bölüm, **21 kod hücresinin tamamı sırayla hatasız** çalıştı (`scripts/execute_notebook.py`).
- **Ortak mantık:** Defter `saferoute.preprocess` fonksiyonlarını kullanıyor ve hattı idempotent olarak çağırıyor; çıktılar güncelse doğrulanıp atlanıyor.
- **Elle sayı yok:** Markdown hücrelerinde elle yazılmış istatistik bulunmuyor.
- **Faz 1 defteri:** `01_dataset_exploration.ipynb` değiştirilmedi.

## 17. Test sonuçları

**108 test, 108 geçti:** Faz 1'den 60, Faz 2'den 48.

| İstenen test | Karşılık |
|---|---|
| Boundary point handling | Ortak kenar → belirsiz, dış kenar → `covered_by`, yüklem sayımları |
| Missing coordinate handling | `missing` durumu, dışlama nedeni |
| Zero coordinate rejection | `zero` durumu, kümeleme dışı |
| Incorrect CRS detection | CRS yok / farklı CRS / yanlış etiketlenmiş projeksiyonlu veri / iki tarafın uyuşmazlığı |
| Borough inference | Kurtarma ve kaynak alanı |
| Original/inferred conflict | Bayrak; bildirilen değerin korunması |
| Unknown vehicle categories | `UNKNOWN`/`missing`/`unmatched`, 15 parametrik etiket |
| Midnight suspect flag | Yalnız kesin 00:00; 00:01 bayraklanmaz |
| Cyclical hour encoding | 23:59–00:01 yakınlığı, karşıt saatler, birim çember |
| Haversine transformation | Bilinen mesafeler, scikit-learn uyumu, sütun sırası, eps dönüşümü |
| Meter-based projection | UTM merkez meridyeni = 500 km, mesafe korunumu, kapsama alanı |
| Duplicate coordinate preservation | Ağırlıklar, kayıt korunumu, ağırlıklı DBSCAN eşdeğerliği |
| Injury/fatality flags | 5 bayrak türü; ham değerin üzerine yazılmaması |
| Feature column selection | A/B sütunları ve sırası; kimlik, yaralanma ve ilçe öznitelik değil |
| Raw data immutability | SHA-256 öncesi/sonrası; salt-okunur dosyalar |
| Pipeline idempotence | İkinci koşu atlanır; `--force` aynı içerik özetini verir; yapılandırma değişince yeniden üretilir |
| Output row-count consistency | raw = interim = processed; öznitelik satırları = uygun kayıt |

Ek testler: sınır doğrulama (eksik ilçe, geçersiz bowtie geometrisi, çizgi geometrisi), Socrata konum öneki, `map_uniques`, standardizasyon, dakika yığılma oranı (sıfır sayımlı dakikalar dahil) ve raporların üretilmesi.

## 18. Çalışma süresi ve bellek

Ölçüm `saferoute preprocess --force` ile, Windows 11 makinede (16 mantıksal çekirdek, 15,2 GB RAM) yapıldı:

| Adım | Süre (sn) | Bellek tepe (MB) |
|---|---:|---:|
| Girdi doğrulama (SHA-256) | 0,9 | 160 |
| Ham yükleme | 1,1 | 1.000 |
| Standardizasyon (interim) | 27,8 | 2.360 |
| Koordinat sınıflaması + ilçe çıkarımı | 10,4 | 2.360 |
| Zaman | 1,2 | 2.360 |
| Araç eşleme | 9,2 | 2.360 |
| Yaralı/ölü | 1,6 | 2.360 |
| Dönüşümler (radyan, UTM) | 5,1 | 2.360 |
| Konum tablosu + öznitelik matrisleri | 11,4 | 3.703 |
| Ham veri değişmedi doğrulaması | 1,0 | 3.703 |
| **Toplam** | **100,0** | **3.703** |

- **Tekrar koşusu:** Çıktılar güncelse hat yaklaşık 1–2 saniyede atlanıyor.
- **Hız optimizasyonları:**
  - Ayrıştırma benzersiz değerler üzerinden yapılıyor (factorize + take).
  - İlçe çıkarımı 2,27 milyon satır yerine 349.140 benzersiz noktada çalışıyor.
  - İkili uzaklık matrisi kurulmuyor.
- **Bellek tepe noktası:** Son adımda işlenmiş katmanın (87 sütun) bellekte tutulmasından kaynaklanıyor; 8 GB RAM'li bir makinede de çalışabilir düzeyde.

## 19. Graphify güncelleme durumu

- **Kurulum:** Mevcut Graphify v0.9.90 yapılandırması değiştirilmedi.
- **Güncelleme:** Bilgi grafiği, kod değişikliklerinden sonra `graphify update .` ile güncellendi: 469 düğümden **770 düğüm, 1.898 kenara** çıktı ve `preprocess` paketinin 16 dosyasının tamamı grafikte.
- **Sağlık kontrolü** (`graphify diagnose multigraph`): eksik uçlu kenar 0, sarkan kenar 0, kendine dönen kenar 0, birebir tekrar 0, çökmüş kenar 0 (yönlü ve yönsüz).
- **Tarihli yedek klasör:** `graphify-out/2026-10-19/` incelendi. Faz 1 öncesindeki 19 düğümlü grafiğin, yeniden üretilebilir yedeği; içeriği git geçmişinde de var. **Silinmedi**, `.gitignore` kuralıyla git dışında tutuluyor (K-21).
- **Etiketler:** `graphify update` topluluk kimliklerini yeniden hesaplıyor ve etiketleri dosya adlarından otomatik üretiyor. `.graphify_labels.json` Faz 1'de de `{}` olarak commit edilmişti; grafik yapısı bu durumdan etkilenmiyor.

## 20. Git commit kimliği

Commit mesajı: `feat: complete SafeRoute 3D phase 2 preprocessing`. Kimlik kapanış özetinde raporlanacak (bu dosya commit'in içinde olduğu için kendi kimliğini içeremez).

## 21. Bilinen sınırlılıklar

1. **Ağırlıklı DBSCAN eşdeğerliği** yalnızca sentetik veride test edildi; gerçek veride alt örneklemle doğrulanması Faz 3'te yapılacak.
2. **Kıyı tamponu (500 m)** veriye dayalı bir eşik. Tampon içindeki noktaların bir kısmı gerçekte suda olabilir (geokodlama sapması); bunlar ilçeye atanmıyor, yalnızca kümelemeye alınıyor.
3. **Yedek geokodlama kuralı** (≥ 3 ilçe) yalnızca bu yapıdaki hataları yakalar. Tek ilçeden bildirilmiş ama yanlış konumlanmış kayıtlar tespit edilemez.
4. **00:00 kayıtları:** Hangilerinin gerçek gece yarısı olduğu ayırt edilemiyor; bayrak bir şüpheyi ifade ediyor, kesin hatayı değil.
5. **Araç türü eşlemesi** kural tabanlı ve elle tasarlandı. Etiket geçişlerinin %0,14'ü eşleşmedi; kurallar yeni etiketlerle güncellenmeli.
6. **Datum:** Koordinatlar WGS84 olarak varsayıldı. NAD83 ile WGS84 arasındaki fark NYC'de metre düzeyinde ve kümeleme ölçeğinde ihmal edilebilir, ancak kaynakta açıkça belgelenmemiş.
7. **Kaynak güncelliği:** Faz 1'deki güncellik sınırlılığı sürüyor; kaynak 2026-06-15'ten beri güncellenmemiş.
8. **Bellek:** Tepe değeri 3,7 GB; daha küçük makineler için sütun-seçmeli işleme gerekebilir.
9. **Lisans:** İlçe sınırı verisinin meta verisinde de lisans alanı boş; NYC Open Data kullanım koşulları akademik raporda belirtilmeli.

## 22. Faz 3'e geçiş önerileri

1. Önce A modelinin kayıt düzeyi ve ağırlıklı sonuçlarını gerçek verinin bir alt örnekleminde birebir karşılaştırmak, ardından tam veride ağırlıklı DBSCAN çalıştırmak.
2. `eps` (ör. 25–300 m) × `min_samples` ızgarası kurmak. `min_samples` seçiminde tek başına çekirdek olan konum sayısı (§8) mutlaka raporlanmalı.
3. Yedek geokodlama şüphesi olan kayıtlar ile ve onlarsız duyarlılık analizi yapmak.
4. HDBSCAN'i kayıt düzeyinde çalıştırmak; bellek ve süreyi ölçmek, gerekirse belgelenmiş bir alt örneklem kullanmak.
5. K-Means'te birden çok `k` için ağırlıklı fit; sabit `random_state` ve `n_init`.
6. Değerlendirme: gürültüyü dışlayarak siluet (Haversine ile tutarlı) ve Davies–Bouldin; büyük veride belgelenmiş alt örneklem; uygun olduğu ölçüde DBCV.
7. Küme profilleri: `has_reported_injury/fatality`, `involves_*`, `borough_final`, zaman dilimleri. Bunlar yalnızca betimleyici olarak kullanılacak.
8. scikit-learn'ü ana bağımlılıklara taşımak; deney yapılandırmalarını ve sürümleri kaydetmek.

---

## Hocanın sorabileceği sorular

**Hangi öznitelikleri kullandınız?**
Coğrafi modellerde yalnızca konumu kullandık:
- A (DBSCAN) ve C (HDBSCAN): `[lat_rad, lon_rad]`, Haversine metriği.
- B (K-Means): `[x_m, y_m]`, EPSG:32618 metre.
- D (deneysel uzay-zaman): `x_m`, `y_m`, `days_since_epoch` ve döngüsel saat/gün (sin/cos).

**Hangi öznitelikleri elediniz, neden?**
29 ham sütunun hiçbiri körü körüne modele girmedi (§12):
- Kimlik (`collision_id`) mesafe uzayında anlamsızdır.
- `location`, enlem/boylamın birebir tekrarıdır; ölçülen fark 0.
- İlçe ve posta kodu konumun türevidir ve yaklaşık %30 eksiktir.
- Sokak adları yüksek kardinaliteli serbest metindir.
- Araç türü ve faktör kategoriktir, mekânsal soruya ait değildir.
- Yaralı/ölü sonuç değişkenidir.

Elenen alanlar silinmedi; filtre ve küme yorumu için korunuyor.

**Eksik verileri nasıl işlediniz?**
Hiçbir değeri doldurmadık. İlçe yalnızca güvenilir bir dış kaynaktan, resmî poligondan çıkarıldı (478.280 kayıt). Koordinatı eksik veya geçersiz kayıtlar silinmedi; nedenleriyle (`exclusion_reason`) ve sayılarıyla yalnızca mekânsal kümelemeden dışlandı. Saat ve yaralı/ölü sorunları bayraklandı.

**Normalizasyon veya ölçekleme yaptınız mı?**
Hayır, bilinçli olarak. Radyan (Haversine) ve metre (UTM) fiziksel olarak anlamlı ve eksenler arasında tutarlı birimlerdir. Z-skoru gibi bir ölçekleme enlem ve boylamı farklı katsayılarla esneterek gerçek mesafeyi bozar ve `eps`'in metre karşılığını anlamsız kılardı. Ölçekleme yerine birim dönüşümü yapıldı: derece → radyan / metre.

**Aykırı değerleri nasıl belirlediniz?**
İstatistiksel bir eşikle değil, alan bilgisine dayalı ve dışlayıcı kurallarla:
- Eksik, ayrıştırılamaz ve sonlu olmayan değerler.
- Sıfır yer tutucusu.
- Geçersiz derece aralığı.
- Resmî NYC poligonları ile veriye dayalı 500 m kıyı tamponunun dışı.

Yoğun bölgeler aykırı sayılmadı; yoğunluk, kümelemenin öğreneceği sinyaldir. Ayrıca iki tür şüpheli değer bayraklandı:
- Yedek geokodlama noktaları (≥ 3 ilçe).
- 00:00 saatleri.

**İlçe bilgisini nasıl çıkardınız?**
Resmî DCP Borough Boundaries (`gthc-hcne`, sürüm 26b) indirildi ve doğrulandı: 5 ilçe, MultiPolygon, geometriler geçerli, CRS84 → EPSG:4326, SHA-256 kaydı. Ardından CRS'ler eşleştirilerek benzersiz noktalarda point-in-polygon (`covered_by`) uygulandı.
- Tam olarak tek ilçe → atama yapıldı.
- Birden fazla ilçe → belirsiz, atama yok.
- Poligon dışı → atama yok.

Bildirilen değer hiçbir zaman ezilmedi. Çelişkiler ayrıca analiz edildi: sınır caddeleri, Marble Hill, yedek geokodlama.

**Hangi verileri model eğitimine hazırladınız?**
`eligible_for_spatial_clustering` bayrağı taşıyan 2.020.638 kayıttan 7 öznitelik matrisi:
- A: kayıt düzeyi + ağırlıklı.
- B: kayıt düzeyi + ağırlıklı.
- C: kayıt düzeyi.
- D: tam set + 00:00 hariç duyarlılık seti.

Her matrisin kaynağı, yapılandırması ve satır sayısı yan kayıtlarda tutuluyor.

**Neden bu öznitelikleri DBSCAN için seçtiniz?**
Araştırma sorusu "kaydedilmiş kazalar mekânda nerede yoğunlaşıyor?" sorusudur. DBSCAN yoğunluk tabanlıdır ve "yakınlık" kavramı gerektirir. Bu yakınlığın tek doğru tanımı yerküre üzerindeki gerçek mesafedir; bu yüzden radyan cinsinden enlem/boylam ve Haversine metriği kullanıldı. Böylece kullanıcıya metre cinsinden sunulan `eps` doğrudan yorumlanabilir.

Başka bir öznitelik eklemek kümelerin anlamını değiştirirdi. Örneğin yaralanma sayısı kümeleri "şiddet ağırlıklı yoğunluğa" çevirir ve değerlendirmeyi döngüsel hale getirir.

**K-Means için verileri neden farklı temsil ettiniz?**
K-Means Öklid uzaklığını ve merkezlerin aritmetik ortalamasını kullanır. Derece cinsinden enlem/boylamda Öklid uzaklığı yöne bağlı olarak bozulur: NYC'de 1° boylam ≈ 84 km, 1° enlem ≈ 111 km. Haversine ise K-Means'in ortalama-merkez mantığıyla uyumlu değildir.

Bu yüzden koordinatlar NYC'yi kapsayan UTM 18N (EPSG:32618) metrik projeksiyonuna dönüştürüldü. Bu düzlemde Öklid uzaklığı, jeodezik mesafeyi medyan %0,03 hatayla temsil ediyor.
