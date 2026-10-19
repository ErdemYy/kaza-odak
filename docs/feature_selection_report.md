# Öznitelik Seçimi Raporu — Faz 2

> `saferoute preprocess` tarafından otomatik üretilmiştir. Kaynak: `snapshot_20261019T155113Z`, yapılandırma özeti `c7ffbfdc478d…`. Eksik oranları ölçülmüştür.

Modeller: **A** = Spatial DBSCAN (Haversine), **B** = Spatial K-Means (EPSG:32618), **C** = HDBSCAN (Haversine), **D** = deneysel uzay-zaman. Gerekçeler: `docs/feature_candidates.md`, `docs/phase2/TEKNIK_RAPOR.md`.

| Öznitelik | Anlam | Köken | Veri türü | Eksik % | Dönüşüm | Modeller | Dahil edilmeme nedeni | Filtre | Yorum |
|---|---|---|---|---:|---|---|---|---|---|
| `collision_id` | Kaza kimliği | raw | Int64 | %0,00 | Int64'e çevrildi | — | Kimlik; mekânsal/zamansal bilgi taşımaz, modele girerse anlamsız mesafe üretir | Hayır | Kayıtları kümelere ve ham veriye bağlama |
| `crash_date` | Kaza tarihi | raw | datetime64[ns] | %0,00 | datetime64'e ayrıştırıldı | — | Ham tarih doğrudan girmez; türetilmiş eksenler (days_since_epoch) D'de kullanılır | Tarih aralığı | Zamansal profil |
| `crash_time` | Kaza saati (metin) | raw | string | %0,00 | Kırpıldı; saat/dakika ayrıştırıldı | — | Metin; türetilmiş döngüsel saat D'de kullanılır | Saat aralığı | Zamansal profil |
| `borough_original` | Kayıtta bildirilen ilçe | raw | string | %30,47 | Kırpma + büyük harf | — | Konumun türevi (çift temsil) ve %30 eksik; modele eklenirse coğrafyayı ikinci kez kodlar | İlçe seçimi (borough_final üzerinden) | Kaynak karşılaştırması |
| `zip_code` | Posta kodu | raw | string | %30,48 | Kırpma | — | Konumun kaba türevi, %30 eksik | İsteğe bağlı | Betimleme |
| `latitude` | Enlem (WGS84, derece) | raw | float64 | %10,61 | float64; geçersizlik sınıflandırıldı | A,B,C,D (dönüştürülmüş) | Ham derece doğrudan girmez: A/C'de radyan, B/D'de metre | Hayır | Harita, küme merkezi |
| `longitude` | Boylam (WGS84, derece) | raw | float64 | %10,61 | float64; geçersizlik sınıflandırıldı | A,B,C,D (dönüştürülmüş) | Ham derece doğrudan girmez: A/C'de radyan, B/D'de metre | Hayır | Harita, küme merkezi |
| `location` | '(enlem, boylam)' metni | raw | string (ham) | %10,61 | Tutarlılığı ölçüldü, interim'e taşınmadı | — | latitude/longitude ile birebir aynı bilgi (ölçülen fark 0) | Hayır | Hayır |
| `on_street_name` | Sokak/cadde adı | raw | string | %22,00 | Kırpma, boşluk tekleme, büyük harf | — | Yüksek kardinaliteli serbest metin; konumu metinle tekrarlar | Hayır | Kümeleri okunur adlarla etiketleme |
| `off_street_name` | Sokak/cadde adı | raw | string | %38,35 | Kırpma, boşluk tekleme, büyük harf | — | Yüksek kardinaliteli serbest metin; konumu metinle tekrarlar | Hayır | Kümeleri okunur adlarla etiketleme |
| `cross_street_name` | Sokak/cadde adı | raw | string | %82,07 | Kırpma, boşluk tekleme, büyük harf | — | Yüksek kardinaliteli serbest metin; konumu metinle tekrarlar | Hayır | Kümeleri okunur adlarla etiketleme |
| `number_of_persons_injured` | Yaralı/ölü sayısı | raw | Int32 | <%0,01 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_persons_killed` | Yaralı/ölü sayısı | raw | Int32 | %0,39 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_pedestrians_injured` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_pedestrians_killed` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_cyclist_injured` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_cyclist_killed` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_motorist_injured` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `number_of_motorist_killed` | Yaralı/ölü sayısı | raw | Int32 | %0,00 | Int32; üzerine yazılmadı, bayraklandı | — | Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı yoğunluk'a döner ve değerlendirme döngüsel olur | Yaralanmalı/ölümlü kaza filtresi | Küme şiddet profili |
| `contributing_factor_vehicle_1` | Katkıda bulunan faktör | raw | string | %0,36 | Kırpma, boşluk tekleme | — | Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil | Faktöre göre alt küme | Küme faktör profili |
| `contributing_factor_vehicle_2` | Katkıda bulunan faktör | raw | string | %16,24 | Kırpma, boşluk tekleme | — | Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil | Faktöre göre alt küme | Küme faktör profili |
| `contributing_factor_vehicle_3` | Katkıda bulunan faktör | raw | string | %92,76 | Kırpma, boşluk tekleme | — | Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil | Faktöre göre alt küme | Küme faktör profili |
| `contributing_factor_vehicle_4` | Katkıda bulunan faktör | raw | string | %98,34 | Kırpma, boşluk tekleme | — | Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil | Faktöre göre alt küme | Küme faktör profili |
| `contributing_factor_vehicle_5` | Katkıda bulunan faktör | raw | string | %99,55 | Kırpma, boşluk tekleme | — | Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil | Faktöre göre alt küme | Küme faktör profili |
| `vehicle_type_code1` | Araç türü (ham) | raw | string | %0,75 | Normalize edildi, üst kategoriye eşlendi | — | 2.000+ dağınık etiket; mekânsal soruya ait değil | vehicle_category_* / involves_* üzerinden | Küme araç profili |
| `vehicle_type_code2` | Araç türü (ham) | raw | string | %20,41 | Normalize edildi, üst kategoriye eşlendi | — | 2.000+ dağınık etiket; mekânsal soruya ait değil | vehicle_category_* / involves_* üzerinden | Küme araç profili |
| `vehicle_type_code_3` | Araç türü (ham) | raw | string | %93,04 | Normalize edildi, üst kategoriye eşlendi | — | 2.000+ dağınık etiket; mekânsal soruya ait değil | vehicle_category_* / involves_* üzerinden | Küme araç profili |
| `vehicle_type_code_4` | Araç türü (ham) | raw | string | %98,40 | Normalize edildi, üst kategoriye eşlendi | — | 2.000+ dağınık etiket; mekânsal soruya ait değil | vehicle_category_* / involves_* üzerinden | Küme araç profili |
| `vehicle_type_code_5` | Araç türü (ham) | raw | string | %99,56 | Normalize edildi, üst kategoriye eşlendi | — | 2.000+ dağınık etiket; mekânsal soruya ait değil | vehicle_category_* / involves_* üzerinden | Küme araç profili |
| `lat_rad` | Enlem, radyan | engineered | float64 | %10,95 | radians(latitude) | A,C | — | Hayır | Hayır |
| `lon_rad` | Boylam, radyan | engineered | float64 | %10,95 | radians(longitude) | A,C | — | Hayır | Hayır |
| `x_m` | UTM 18N doğu koordinatı (m) | engineered | float64 | %10,95 | EPSG:4326 -> EPSG:32618 | B,D | — | Hayır | Hayır |
| `y_m` | UTM 18N kuzey koordinatı (m) | engineered | float64 | %10,95 | EPSG:4326 -> EPSG:32618 | B,D | — | Hayır | Hayır |
| `location_id` | Benzersiz konum kimliği | engineered | int64 | %0,00 | Sıralı benzersiz (enlem, boylam) | — | Kimlik; ağırlıklı temsilde anahtar | Hayır | Tekrar analizi |
| `coordinate_quality_status` | Koordinat kalite durumu | engineered | category | %0,00 | Öncelikli dışlayıcı sınıflama + resmî poligon | — | Kalite alanı | Uygunluk seçimi | Kalite raporu |
| `is_valid_geographic_record` | Geçerli coğrafi kayıt | engineered | bool | %0,00 | Durumdan türetildi | — | Bayrak | Evet | Kalite raporu |
| `eligible_for_spatial_clustering` | Kümelemeye uygun | engineered | bool | %0,00 | Durum + geçerli tarih | — | Bayrak; öznitelik matrislerinin satır seçimi | Evet | Hayır |
| `borough_inferred` | Poligondan çıkarılan ilçe | engineered | string | %11,37 | Point-in-polygon (covered_by) | — | Konumun türevi | Evet | Bildirilen ilçeyle karşılaştırma |
| `borough_final` | Nihai ilçe | engineered | string | %9,39 | Bildirilen; yoksa poligon | — | Konumun türevi | İlçe seçimi | İlçe özetleri |
| `borough_source` | Nihai ilçenin kaynağı | engineered | category | %0,00 | original / inferred_polygon / none | — | Kaynak alanı | Evet | İzlenebilirlik |
| `borough_conflict_flag` | Bildirilen ≠ çıkarılan ilçe | engineered | bool | %0,00 | Karşılaştırma | — | Kalite bayrağı | Evet | Çelişki raporu |
| `location_reported_borough_count` | Aynı koordinattaki farklı bildirilmiş ilçe sayısı | engineered | int8 | %0,00 | location_id bazında nunique(borough_original) | — | Kalite ölçüsü | Hayır | Geokodlama kalitesi |
| `geocode_fallback_suspect_flag` | Yedek geokodlama noktası şüphesi | engineered | bool | %0,00 | >= 3 farklı bildirilmiş ilçe aynı koordinatta | — | Kalite bayrağı; kayıt silinmez, Faz 3 duyarlılık analizinde kullanılır | Evet | Duyarlılık analizi |
| `crash_year` | Yıl | engineered | Int16 | %0,00 | crash_date.year | — | Filtre | Yıl aralığı | Zamansal profil |
| `crash_month` | Ay | engineered | Int8 | %0,00 | crash_date.month | — | Doğrusal ay modelde kullanılmaz (Aralık–Ocak süreksizliği) | Ay | Mevsimsellik |
| `crash_day` | Ayın günü | engineered | Int8 | %0,00 | crash_date.day | — | Filtre | Evet | Hayır |
| `crash_hour` | Saat | engineered | Int8 | %0,00 | crash_time ayrıştırma | — | Doğrusal saat modelde kullanılmaz (23–00 süreksizliği) | Saat aralığı | Saat profili |
| `crash_minute` | Dakika | engineered | Int8 | %0,00 | crash_time ayrıştırma | — | Ayrıntı | Hayır | 00:00 analizi |
| `day_of_week` | Haftanın günü (0=Pzt) | engineered | Int8 | %0,00 | crash_date.dayofweek | — | Doğrusal kodlama kullanılmaz | Gün | Haftalık profil |
| `is_weekend` | Hafta sonu | engineered | boolean | %0,00 | day_of_week >= 5 | — | Filtre | Evet | Profil |
| `time_period` | Gün dilimi | engineered | category | %0,00 | 00–06 gece, 06–12 sabah, 12–18 öğleden sonra, 18–24 akşam | — | Kaba kategori; filtre | Evet | Profil |
| `hour_sin` | Saat (sin) | engineered | float64 | %0,00 | sin(2π·(saat+dk/60)/24) | D | — | Hayır | Hayır |
| `hour_cos` | Saat (cos) | engineered | float64 | %0,00 | cos(2π·(saat+dk/60)/24) | D | — | Hayır | Hayır |
| `month_sin` | Ay (sin) | engineered | float64 | %0,00 | sin(2π·(ay−1)/12) | — | D'nin ilk sürümünde mevsim ekseni kullanılmaz (kapsam: konum + gün + saat) | Hayır | Mevsimsellik |
| `month_cos` | Ay (cos) | engineered | float64 | %0,00 | cos(2π·(ay−1)/12) | — | Aynı gerekçe | Hayır | Mevsimsellik |
| `dow_sin` | Haftanın günü (sin) | engineered | float64 | %0,00 | sin(2π·gün/7) | D | — | Hayır | Hayır |
| `dow_cos` | Haftanın günü (cos) | engineered | float64 | %0,00 | cos(2π·gün/7) | D | — | Hayır | Hayır |
| `days_since_epoch` | 1970'ten itibaren gün | engineered | Int32 | %0,00 | crash_date − 1970-01-01 | D | — | Hayır | Hayır |
| `midnight_suspect_flag` | Kesin 00:00 saat (şüpheli) | engineered | bool | %0,00 | saat=0 ve dakika=0 | — | Bayrak; D duyarlılık setinde dışlama ölçütü | Evet | Duyarlılık analizi |
| `injury_data_quality_flag` | Yaralı alanı tutarlılığı | engineered | category | %0,00 | Toplam vs alt alanlar | — | Kalite bayrağı | Evet | Profil güvenilirliği |
| `fatality_data_quality_flag` | Ölü alanı tutarlılığı | engineered | category | %0,00 | Toplam vs alt alanlar | — | Kalite bayrağı | Evet | Profil güvenilirliği |
| `has_reported_injury` | En az bir yaralı bildirilmiş | engineered | bool | %0,00 | toplam>0 veya alt alan>0 | — | Sonuç değişkeni | Evet | Küme şiddet profili |
| `has_reported_fatality` | En az bir ölü bildirilmiş | engineered | bool | %0,00 | toplam>0 veya alt alan>0 | — | Sonuç değişkeni | Evet | Küme şiddet profili |
| `vehicle_category_1..5` | Araç üst kategorisi | engineered | category | %0,75 | Kural tabanlı eşleme | — | Kategorik; mekânsal soruya ait değil | Evet | Araç profili |
| `involves_<kategori>` | Kazada kategori var mı | engineered | bool | %0,00 | vehicle_category_* üzerinden | — | Filtre | Evet (ör. bisiklet içeren kazalar) | Araç profili |

## Model öznitelik matrisleri

| Dosya | Model | Düzey | Anahtar | Öznitelikler | Ağırlık | Satır | Metrik |
|---|---|---|---|---|---|---:|---|
| `A_dbscan_haversine.parquet` | DBSCAN (A) | record | `collision_id` | lat_rad, lon_rad | — | 2.020.638 | haversine (scikit-learn: [enlem, boylam] radyan) |
| `A_dbscan_haversine_weighted.parquet` | DBSCAN (A, ağırlıklı) | unique_location | `location_id` | lat_rad, lon_rad | weight | 349.122 | haversine; fit(X, sample_weight=weight) |
| `B_kmeans_projected.parquet` | K-Means (B) | record | `collision_id` | x_m, y_m | — | 2.020.638 | Öklid (EPSG:32618 metre) |
| `B_kmeans_projected_weighted.parquet` | K-Means (B, ağırlıklı) | unique_location | `location_id` | x_m, y_m | weight | 349.122 | Öklid; fit(X, sample_weight=weight) |
| `C_hdbscan_haversine.parquet` | HDBSCAN (C) | record | `collision_id` | lat_rad, lon_rad | — | 2.020.638 | haversine (alternatif: x_m/y_m Öklid) |
| `D_spatiotemporal_experimental.parquet` | Uzay-zaman (D, deneysel) | record | `collision_id` | x_m, y_m, days_since_epoch, hour_sin, hour_cos, dow_sin, dow_cos | — | 2.020.638 | Ayrı eşikli komşuluk: mesafe_m <= eps_s VE |Δgün| <= eps_t (VE isteğe bağlı döngüsel saat farkı <= eps_h) |
| `D_spatiotemporal_experimental_no_midnight.parquet` | Uzay-zaman (D, duyarlılık: 00:00 hariç) | record | `collision_id` | x_m, y_m, days_since_epoch, hour_sin, hour_cos, dow_sin, dow_cos | — | 1.997.922 | D ile aynı |
