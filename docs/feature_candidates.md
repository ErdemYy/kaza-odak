# Özellik Adayları ve Seçim Gerekçesi — Faz 1

Bu belge, ham veri setindeki 29 sütunun SafeRoute 3D kümeleme deneylerindeki rolünü sınıflandırıyor ve gerekçelendiriyor. Eksik değer oranları `snapshot_20261019T155113Z` üzerinde ölçülmüştür; sütun bazlı ayrıntı için `docs/data_dictionary.md` dosyasına bakın.

**Bu fazda hiçbir model eğitilmedi (fit yapılmadı).** Aşağıdaki deneyler Faz 3 için öneridir.

## 1. Sınıflandırma ilkeleri

Projenin birincil sorusu şudur: *"Kaydedilmiş kazalar şehir içinde mekânsal olarak nerede yoğunlaşıyor ve bu yoğunlaşmalar seçilen zaman, ilçe ve kaza özelliklerine göre nasıl değişiyor?"* Bu nedenle:

- **Küme üyeliğini** yalnızca bu soruya doğrudan karşılık gelen özellikler belirler: önce konum, deneysel olarak zaman.
- **Hangi kayıtların kümeleneceğini** filtre alanları belirler. Filtreler özellik uzayına girmez.
- **Kümeler oluştuktan sonra** onları betimleyici ve sonuç alanları açıklar.
- Kimlikler ve tekrarlı temsiller modele hiç girmez.

## 2. Sınıflar

### A. Coğrafi model özellikleri

| Alan | Anlam / tür | Eksik | Kümeleme için uygun mu | Ön işleme | Gerekçe |
|---|---|---:|---|---|---|
| `latitude` | Enlem, WGS84, ondalık derece | %10,61 (+ 0 değeri %0,33, kutu dışı %0,01) | **Evet** (birincil) | Sayıya çevirme; geçersizlerin nedeniyle dışlanması; DBSCAN/HDBSCAN için radyan + Haversine, K-Means için metrik projeksiyon | Birincil soru mekânsal yoğunlaşmadır |
| `longitude` | Boylam, WGS84, ondalık derece | %10,61 | **Evet** (birincil) | Aynı | Aynı |

**Neden ham derece üzerinde Öklid uzaklığı kullanılmaz?** NYC enleminde (yaklaşık 40,7°) 1° boylam yaklaşık 84 km'ye, 1° enlem yaklaşık 111 km'ye karşılık gelir. Derece uzayındaki Öklid uzaklığı bu yüzden yöne bağlı olarak bozulur. Haversine küresel yay uzaklığını verir. Kullanıcıya metre cinsinden sunulan `eps`, `eps_rad = eps_m / 6 371 008,8` ile açısal değere çevrilir (yerküre ortalama yarıçapı).

### B. Zamansal model özellikleri (deneysel)

| Alan | Anlam / tür | Eksik | Uygun mu | Ön işleme | Gerekçe |
|---|---|---:|---|---|---|
| `crash_date` | Tarih (saat bileşeni her zaman 00:00) | %0 | **Yalnızca deneysel uzay-zaman deneyinde** | Ayrıştırma; yıl/ay/gün; döngüsel haftanın günü | Zamanı konumla aynı uzayda kullanmak açık bir uzaklık tanımı gerektirir |
| `crash_time` | Saat (H:MM) | %0; 00:00 yığılması %1,08 | Aynı | Ayrıştırma; 00:00 bayrağı; döngüsel kodlama (sin/cos, 24 saat) | Saat döngüseldir (23:59 ile 00:00 yakındır); doğrusal kodlanmamalı |

Temel üretim deneyinde (Deney A) zaman **filtre** olarak kullanılır: önce tarih/saat aralığı seçilir, sonra yalnızca konum kümelenir.

### C. Yalnızca filtre alanları

| Alan | Eksik | Neden model özelliği değil | Ön işleme |
|---|---:|---|---|
| `borough` | %30,47 | Konumun bir fonksiyonudur. Modele eklenirse konumu ikinci kez temsil eder ve eksikliği nedeniyle kayıt kaybına yol açar. | Kaydedilen değer korunur; poligonlardan `borough_inferred` ayrı sütun olarak türetilir |
| `zip_code` | %30,48 | Konumun kaba bir türevi; çok eksik | Yalnızca filtre/betimleme |
| `vehicle_type_code1`, `vehicle_type_code2`, `vehicle_type_code_3..5` | %0,75 / %20,41 / %93–99 | Kategorik ve çok dağınık (2.168 normalize değer). Mekânsal soruya ait değil. | Belgelenmiş eşleme ile sınırlı kategori kümesi (ör. binek, ticari, taksi, otobüs, motosiklet, bisiklet, diğer/bilinmiyor) |
| `contributing_factor_vehicle_1..5` | %0,36 / %16,24 / %93–99 | Kategorik ve polis yorumu; `Unspecified` %33,34 | `Unspecified` → "bilinmiyor"; sık kategoriler korunur, nadirler gruplanır |

Bu alanlar örneğin "yalnızca bisikletlilerin karıştığı kazalar" ya da "yalnızca Brooklyn" gibi alt kümeler seçmek için kullanılır. Her filtre sonrası küme sayısı ve gürültü oranı yeniden raporlanır.

### D. Betimleyici / sonuç alanları

| Alan | Eksik | Rol |
|---|---:|---|
| `number_of_persons_injured`, `_killed` | %0,00 (18 kayıt) / %0,39 | Kümelerin şiddet profili: toplam, kaza başına oran, en az bir yaralı/ölü içeren kaza oranı |
| `number_of_pedestrians_*`, `_cyclist_*`, `_motorist_*` | %0 | Yol kullanıcısı türüne göre küme profili |
| `on_street_name`, `off_street_name`, `cross_street_name` | %22,00 / %38,35 / %82,07 | Kümeleri insanların okuyabileceği adlarla etiketleme (ör. en sık cadde) |

**Yaralı/ölü sayıları neden başlangıçta küme üyeliğini belirlemeyecek?**

1. **Soru değişir.** Bu sayılar özellik veya örnek ağırlığı olarak eklenirse kümeler "kaza yoğunluğu" değil "şiddet ağırlıklı yoğunluk" olur. Bu, ayrı bir araştırma sorusudur ve ayrıca tanımlanmalıdır.
2. **Nadir ve gürültülü sinyal.** Ölümlü kazalar yalnızca 3.469 kayıttır (yaklaşık %0,15). Bu kadar seyrek bir sinyal küme sınırlarını orantısız ve kararsız biçimde etkiler.
3. **Döngüsel değerlendirme.** Kümeleri yaralanma profiliyle yorumlamak istiyoruz. Aynı değişken üyeliği de belirlerse "bu küme daha ağır kazalar içeriyor" bulgusu kendini doğrulayan bir sonuca dönüşür.
4. **Ölçek uyumsuzluğu.** Metre cinsinden konum uzaklığıyla kişi sayısını aynı uzaklık fonksiyonunda birleştirmenin savunulabilir, birimden bağımsız bir yolu yok.
5. **Veri kalitesi.** `persons_*` toplamlarında alt kırılımla tutarsız kayıtlar ve eksik değerler var.

Şiddet ağırlıklı kümeleme ileride ayrı bir deney olarak (ör. DBSCAN `sample_weight`) ancak gerekçesi ve karşılaştırmasıyla birlikte ele alınabilir.

### E. Kimlik ve dışlanan alanlar

| Alan | Neden dışlanır |
|---|---|
| `collision_id` | Benzersiz kimliktir ve mekânsal bilgi taşımaz. İzlenebilirlik ve birleştirme için **korunur** ama modele girmez. |
| `location` | `latitude`/`longitude` ile birebir aynı bilgiyi metin olarak tekrarlar. İkisi her satırda birlikte dolu ya da birlikte boş: ölçülen uyumsuzluk sayısı 0. |

## 3. Önerilen deneyler (Faz 3 — bu fazda çalıştırılmadı)

Tüm deneylerde aynı kurallar geçerli olacak:
- Aynı ön işlenmiş veri kümesi ve aynı filtreler kullanılır.
- Konfigürasyon, yazılım sürümleri, rastgele tohumlar, süre ve bellek kaydedilir.
- Gürültü noktaları sıradan bir küme gibi değerlendirilmez.

### Deney A — Coğrafi DBSCAN (Haversine)
- **Özellik uzayı:** `(lat, lon)` radyan cinsinden; `metric="haversine"`, `algorithm="ball_tree"`.
- **Parametreler:** `eps` metre cinsinden (ör. 50–300 m ızgarası) ve `min_samples`.
- **Hesaplama:** Tam ikili uzaklık matrisi **kurulmaz**. Bunun yerine uzamsal indeksle komşuluk sorgusu yapılır.
- **Yinelenen koordinatlar:** 349.124 benzersiz konum `sample_weight` ile değerlendirilebilir. Kayıt düzeyi sonuçla eşdeğerliği, alt örneklemde birebir karşılaştırmayla doğrulanmadan iddia edilmeyecek.
- **Çıktılar:** Küme sayısı, gürültü oranı, küme boyutları, küme merkezleri ve dışbükey zarfları, yaralanma profili, parametre duyarlılığı.

### Deney B — K-Means (metrik projeksiyon)
- **Özellik uzayı:** Koordinatlar metrik bir projeksiyona dönüştürülür. NYC için NAD83 / New York Long Island (EPSG:2263, ABD fiti) veya UTM 18N (EPSG:32618, metre) uygundur; birim tutarlılığı için metre tercih edilecek.
- **Parametreler:** Birden çok `k` değeri (dirsek yöntemi ve siluet ile birlikte raporlanır); sabit `random_state` ve `n_init`.
- **Sınırlılık:** K-Means her noktayı bir kümeye zorlar ve dışbükey, benzer büyüklükte kümeler varsayar. Düzensiz, yoğunluk temelli kaza örüntülerini ve gürültüyü temsil edemez. Karşılaştırma bu farkı açıkça tartışacak.

### Deney C — HDBSCAN
- **Özellik uzayı:** Deney A ile aynı (Haversine, radyan).
- **Parametreler:** `min_cluster_size`, `min_samples`, `cluster_selection_epsilon` (metreden radyana çevrilir).
- **Çıktılar:** Değişken yoğunluklu kümeler, gürültü, küme kararlılığı (persistence) ve üyelik olasılıkları.
- **Uygulama:** scikit-learn `HDBSCAN` veya uyumlu bir kütüphane; sürüm kaydedilecek.

### Deney D — İsteğe bağlı uzay-zaman kümelemesi
- **Uzaklık:** ST-DBSCAN benzeri iki eşikli komşuluk. Bir nokta, ancak hem `haversine(p,q) ≤ eps_s` (metre) hem de `Δt(p,q) ≤ eps_t` (ör. gün veya döngüsel saat farkı) ise komşu sayılır.
- **Gerekçe:** Metre ile saati tek bir ağırlıklı toplamda birleştirmek keyfi bir ölçek katsayısı gerektirir. İki ayrı eşik ise yorumlanabilirdir.
- **Saat farkı:** Döngüsel olarak hesaplanır: `min(|h1−h2|, 24−|h1−h2|)`.
- **Ön koşul:** 00:00 yığılmasındaki kayıtlar bu deneyden dışlanır veya duyarlılık analiziyle ele alınır.

### Değerlendirme notları
- **Siluet skoru ve Davies–Bouldin indeksi:** Gürültü noktaları dışlanarak ve bu dışlama açıkça belirtilerek hesaplanır. Haversine uzayında siluet hesabı metrikle tutarlı yapılır.
- **DBCV:** Yoğunluk temelli yöntemler için uygulanabilir olduğu ölçüde kullanılır.
- **Ölçeklenebilirlik:** Siluet skoru tüm veride O(n²) maliyetlidir; belgelenmiş ve tekrarlanabilir alt örneklemle hesaplanır.
- **Doğruluk iddiası yok:** Denetimsiz kümeleme için yer gerçekliği (ground truth) yoktur; "doğruluk" iddiası yapılmayacak.

## 4. Geometrik ilçe zenginleştirme stratejisi (Faz 2)

1. Resmi DCP *Borough Boundaries* (`gthc-hcne`, su alanları hariç, sürüm 26b) indirilir ve kaynak/sürüm kaydı tutulur.
2. Geçerli koordinatlı kayıtlar için GeoPandas ile **nokta-poligon** (`within`) uzamsal birleştirmesi yapılır. İşlem uzamsal indeksle yürütülür; tam ikili karşılaştırma yapılmaz.
3. Poligona düşmeyen noktalar (köprüler, kıyı ve su alanları) sınırlı bir mesafe eşiğiyle en yakın ilçeye atanır. Bu atama `borough_inferred_method = "nearest"` ve uzaklık değeriyle işaretlenir; eşiği aşan noktalar `outside_nyc` olarak bırakılır.
4. `borough_reported`, `borough_inferred` ve `borough_agreement` ayrı sütunlar olarak tutulur. Bildirilen değer **asla üzerine yazılmaz**.
5. Bildirilen ve çıkarılan ilçenin uyuşma oranı raporlanır. Bu oran, poligon yönteminin doğrulamasıdır.
6. **Kaba sınırlayıcı kutu ile ilçe ataması yapılmaz.**
