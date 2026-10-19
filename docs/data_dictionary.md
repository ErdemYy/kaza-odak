# Veri Sözlüğü — Motor Vehicle Collisions - Crashes (`h9gi-nx95`)

> `saferoute eda` tarafından otomatik üretilmiştir. Anlık görüntü: `snapshot_20261019T155113Z`, 2.269.187 satır. Eksik = boş veya yalnızca boşluk içeren alan.

Veri türü sütunu `kaynak türü → ölçülen tür` biçimindedir. Kaynak türü Socrata meta verisinden, ölçülen tür dolu değerlerin tamamına uyan en dar türden gelir.

| Sütun | Anlam | Veri türü | Eksik | Eksik % | Benzersiz (dolu) | Öngörülen kullanım | Notlar |
|---|---|---|---:|---:|---:|---|---|
| `crash_date` | Kaza tarihi | calendar_date → datetime | 0 | %0,00 | 5.094 | B — Zamansal model özelliği (deneysel) + filtre | Saat bileşeni her zaman 00:00; saat bilgisi crash_time'dadır. Tarih/yıl filtresi. |
| `crash_time` | Kaza saati (H:MM) | text → time | 0 | %0,00 | 1.440 | B — Zamansal model özelliği (deneysel) + filtre | 00:00 değerinde belirgin yığılma var; bilinmeyen saat yerine girilmiş olabilir. |
| `borough` | Kayıtta bildirilen ilçe | text → text | 691.375 | %30,47 | 5 | C — Yalnızca filtre | Model özelliği değil (koordinattan türetilebilir, sızıntı/çift temsil). Geometrik ilçe Faz 2'de ayrı sütun olacak. |
| `zip_code` | Posta kodu | text → integer | 691.703 | %30,48 | 235 | C — Yalnızca filtre | İlçe ile aynı oranda eksik; filtre/betimleme için, modele girmez. |
| `latitude` | Enlem (WGS84) | number → float | 240.806 | %10,61 | 189.606 | A — Coğrafi model özelliği | 0 ve NYC dışı değerler geçersiz sayılır; eksikler doldurulmaz. |
| `longitude` | Boylam (WGS84) | number → float | 240.806 | %10,61 | 141.342 | A — Coğrafi model özelliği | 0 ve NYC dışı değerler geçersiz sayılır; eksikler doldurulmaz. |
| `location` | '(enlem, boylam)' metni | location → text | 240.806 | %10,61 | 397.985 | E — Kimlik / model dışı | latitude/longitude ile birebir aynı bilgi; tekrarlı coğrafi temsil olduğu için dışlanır. |
| `on_street_name` | Kazanın olduğu cadde | text → text | 499.194 | %22,00 | 23.331 | D — Betimleyici / sonuç | Serbest metin, doldurma boşlukları yaygın; küme betimlemesinde kullanılabilir. |
| `off_street_name` | Kesişen/yakın cadde | text → text | 870.164 | %38,35 | 25.403 | D — Betimleyici / sonuç | Serbest metin; betimleme amaçlı. |
| `cross_street_name` | Çapraz sokak / adres metni | text → text | 1.862.411 | %82,07 | 271.299 | D — Betimleyici / sonuç | Çoğunlukla boş; betimleme amaçlı. |
| `number_of_persons_injured` | Yaralanan toplam kişi | number → integer | 18 | <%0,01 | 32 | D — Betimleyici / sonuç | Küme betimlemesi; alt kırılım toplamıyla tutarsız kayıtlar var. |
| `number_of_persons_killed` | Ölen toplam kişi | number → integer | 8.913 | %0,39 | 7 | D — Betimleyici / sonuç | Küme betimlemesi; nadir olay. |
| `number_of_pedestrians_injured` | Yaralanan yaya | number → integer | 0 | %0,00 | 14 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `number_of_pedestrians_killed` | Ölen yaya | number → integer | 0 | %0,00 | 6 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `number_of_cyclist_injured` | Yaralanan bisikletli | number → integer | 0 | %0,00 | 5 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `number_of_cyclist_killed` | Ölen bisikletli | number → integer | 0 | %0,00 | 3 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `number_of_motorist_injured` | Yaralanan motorlu araç kullanıcısı | number → integer | 0 | %0,00 | 31 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `number_of_motorist_killed` | Ölen motorlu araç kullanıcısı | number → integer | 0 | %0,00 | 6 | D — Betimleyici / sonuç | Küme betimlemesi. |
| `contributing_factor_vehicle_1` | Araç 1 için polisin kaydettiği katkıda bulunan faktör | text → text | 8.202 | %0,36 | 66 | C — Yalnızca filtre | Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı. |
| `contributing_factor_vehicle_2` | Araç 2 için polisin kaydettiği katkıda bulunan faktör | text → text | 368.580 | %16,24 | 65 | C — Yalnızca filtre | Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı. |
| `contributing_factor_vehicle_3` | Araç 3 için polisin kaydettiği katkıda bulunan faktör | text → text | 2.104.798 | %92,76 | 56 | C — Yalnızca filtre | Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı. |
| `contributing_factor_vehicle_4` | Araç 4 için polisin kaydettiği katkıda bulunan faktör | text → text | 2.231.554 | %98,34 | 43 | C — Yalnızca filtre | Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı. |
| `contributing_factor_vehicle_5` | Araç 5 için polisin kaydettiği katkıda bulunan faktör | text → text | 2.258.873 | %99,55 | 34 | C — Yalnızca filtre | Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı. |
| `collision_id` | Kaza kimliği | number → integer | 0 | %0,00 | 2.269.187 | E — Kimlik / model dışı | Benzersiz kimlik; birleştirme/izlenebilirlik için tutulur, modele girmez. Aday kimlik sütunu (tümü dolu ve benzersiz). |
| `vehicle_type_code1` | Araç 1 türü | text → text | 17.081 | %0,75 | 1.905 | C — Yalnızca filtre | Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir. |
| `vehicle_type_code2` | Araç 2 türü | text → text | 463.107 | %20,41 | 2.132 | C — Yalnızca filtre | Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir. |
| `vehicle_type_code_3` | Araç 3 türü | text → text | 2.111.354 | %93,04 | 317 | C — Yalnızca filtre | Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir. |
| `vehicle_type_code_4` | Araç 4 türü | text → text | 2.232.943 | %98,40 | 125 | C — Yalnızca filtre | Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir. |
| `vehicle_type_code_5` | Araç 5 türü | text → text | 2.259.199 | %99,56 | 81 | C — Yalnızca filtre | Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir. |

Sınıf tanımları ve gerekçeler için bkz. `docs/feature_candidates.md`.
