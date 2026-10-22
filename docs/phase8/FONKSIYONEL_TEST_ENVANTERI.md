# SafeRoute 3D — Faz 8: Fonksiyonel Test Envanteri

> Bu belgedeki satırlar `scripts/phase8_inventory.py` ile `reports/phase8/interaction_results.json` dosyasından
> üretildi; "Gerçek davranış" sütunu testin çalışma anında ölçtüğü değerdir (elle yazılmadı).

## Yöntem

- **Araç:** Playwright 1.64 (Chromium), `frontend/e2e/phase8.spec.ts` — 19 test, 125 kimlikli etkileşim adımı.
- **Ortam:** Gerçek FastAPI sunucusu (`saferoute serve --port 8000`), gerçek NYC verisi (2.020.638 uygun olay),
  doğrulanmış Faz 3 çıktıları, derlenmiş ön yüz (`frontend/dist`), gerçek OpenFreeMap karoları. Mock API **yok**;
  yalnızca üç adımda hata/boş/yavaş durum üretmek için tarayıcıda tek bir yanıt değiştirildi ve bu adımlarda açıkça
  yazılıdır (`S01` 500 hatası, `S02` boş iş geçmişi, `S03` gecikme, `L20` bellek yetersiz yanıtı, `E20` altlık kesintisi).
- **Dinamik laboratuvar işleri** ana iş kaydını değiştirmemek için yalıtılmış ikinci sunucuda (port 8012, ayrı
  `--lab-root`, `SAFEROUTE_LAB_TEST_DELAY_S=6` ile iptal edilebilecek kadar uzun) gerçek ayrı süreçte çalıştı.
  Veri kapsamı küçük ve belgelidir: **Staten Island · 2019 = 6.686 olay**, DBSCAN eps 25 m / min_samples 10.
- **Her adım:** kimlik, ekran, bileşen, beklenen davranış, ölçülen gerçek davranış, sonuç, başarısızsa neden.
  Beklenen değerler mümkün olduğunda aynı anda API'den alınıp arayüzle karşılaştırıldı (ör. küme kayıt sayısı,
  filtre önizlemesi, merkez sayısı, zaman kovası).
- **Konsol ve ağ:** her test için konsol hata/uyarıları, başarısız istekler ve ≥ 400 yanıtlar kaydedildi; uygulama
  (127.0.0.1) ile üçüncü taraf (`openfreemap.org`) ayrı listelenir (bkz. `logs` alanı ve Teknik Rapor §8).
- **Tekrarlanabilirlik:** `cd frontend && npx playwright test e2e/phase8.spec.ts` (sunucu 8000'de çalışırken).
  `SAFEROUTE_PHASE8_OUT` ile çıktı yönlendirilebilir.

## Düzeltmeler öncesi ve sonrası

| Çalıştırma | Klasör | Kaydedilen etkileşim | Geçti | Başarısız | Test (19) |
|---|---|---:|---:|---:|---|
| İlk (düzeltmeler öncesi derleme) | `reports/phase8/ilk-calistirma/` | 59 | 56 | 3 | 8 geçti, 10 başarısız/zaman aşımı* |
| Son (tüm düzeltmeler) | `reports/phase8/` | **125** | **125** | **0** | **19 geçti** |

\* İlk çalıştırma 18 testti (altlık testi `E20` sonradan H01 için eklendi). Başarısızlıkların çoğunda 3D ekranı
hiç "hazır" olamadığından adımlar kaydedilemedi (H01). Diğer nedenler: H02, H07, G1 (axe) ve test kodu seçici
hataları (bkz. `BULUNAN_VE_DUZELTILEN_HATALAR.md`).

## Kapsam dışında kalan / yalnızca kodla doğrulanan

- Ekran okuyucuyla elle test yapılmadı (axe otomatik denetimi ve klavye testleri yapıldı).
- Sunucu yeniden başlatmada iş kalıcılığı bu pakette değil, Faz 6 `phase6-restart.spec.ts` regresyonuyla gerçek
  süreç çökertilerek doğrulandı (Teknik Rapor §6).
- 3D varlık inceleyici telefon genişliğinde (< 640 px) gizlidir; orada test edilmedi.

## Sonuçlar

Kaynak: `reports/phase8/interaction_results.json` · üretim 2026-10-22T12:32:56.130Z

**Toplam 125 etkileşim · 125 geçti · 0 başarısız**

| Ekran | Etkileşim | Geçti | Başarısız |
|---|---:|---:|---:|
| 3D Şehir | 45 | 45 | 0 |
| 3D Şehir › Filtreler | 15 | 15 | 0 |
| Genel | 11 | 11 | 0 |
| Genel (mobil) | 1 | 1 | 0 |
| Genel bakış | 9 | 9 | 0 |
| Laboratuvar | 21 | 21 | 0 |
| Model karşılaştırma | 7 | 7 | 0 |
| Tüm ekranlar | 5 | 5 | 0 |
| Veri Gezgini | 6 | 6 | 0 |
| genel-bakis | 1 | 1 | 0 |
| kesif | 1 | 1 | 0 |
| laboratuvar | 1 | 1 | 0 |
| modeller | 1 | 1 | 0 |
| veri | 1 | 1 | 0 |

| Kimlik | Ekran | Bileşen | Beklenen davranış | Gerçek davranış (ölçülen) | Sonuç | Neden (başarısızsa) |
|---|---|---|---|---|---|---|
| F01 | 3D Şehir › Filtreler | İlçe çipleri (çoklu) | Seçilen ilçeler önizlemeyi API sayısıyla günceller | Staten Island 99.401 · + Bronx 401.198 | ✅ geçti |  |
| F03 | 3D Şehir › Filtreler | Yıl çipleri | Yıl seçimi önizlemeyi günceller; kısmi yıllar kesikli kenarlı | 6.686 kayıt · 2012 kenarı dashed | ✅ geçti |  |
| F04 | 3D Şehir › Filtreler | Ay çipleri | Ay seçimi uygulanır | 813 kayıt | ✅ geçti |  |
| F05 | 3D Şehir › Filtreler | Haftanın günü çipleri | Gün seçimi uygulanır (çoklu) | 165 kayıt (hafta sonu) | ✅ geçti |  |
| F06 | 3D Şehir › Filtreler | Saat aralığı anahtarı + seçiciler + gece örneği | Anahtar 07–10'u açar; seçici değeri değiştirir; gece örneği 22–04 yapar | 07–10 → 07–12 → 22–04 (30 kayıt) → kapalı | ✅ geçti |  |
| F07 | 3D Şehir › Filtreler | Araç türü çipleri | Kategori seçimi uygulanır | 94 kayıt (SUV), sonra kaldırıldı | ✅ geçti |  |
| F08 | 3D Şehir › Filtreler | Katkı faktörü seçici | Faktör seçimi uygulanır; 'Tümü' kaldırır | 66 kayıt, sonra Tümü | ✅ geçti |  |
| F09 | 3D Şehir › Filtreler | Yaralanma durumu (tekli seçim) | Yaralanmalı seçimi uygulanır | 28 kayıt | ✅ geçti |  |
| F11 | 3D Şehir › Filtreler | 00:00 şüpheli kayıtları hariç tut | Onay kutusu uygulanır | 164 kayıt | ✅ geçti |  |
| F13 | 3D Şehir › Filtreler | Mevcut kümelerde göster | Filtrelenmiş mod: bant 'yeniden kümeleme yapılmadı'; merkez kimlikleri model kimliklerinin alt kümesi; sayaç API ile aynı | 33 / 4.179 küme; tüm kimlikler tam veri modelinde | ✅ geçti |  |
| F18 | 3D Şehir › Filtreler | Filtre etkinken küme ayrıntısı | Tam küme ve filtrelenmiş sayılar ayrı; küme kimliği değişmez | Küme #243: tam 255 / filtrelenmiş 4 | ✅ geçti |  |
| F15 | 3D Şehir › Filtreler | Geçersiz tarih aralığı | Başlangıç > bitiş: hata mesajı, Uygula ve Laboratuvar düğmeleri devre dışı | hata gösterildi, düğmeler kilitli | ✅ geçti |  |
| F16 | 3D Şehir › Filtreler | Boş sonuç birleşimi | 0 kayıt: önizleme 0, haritada 0 küme ve açık bir boş durum mesajı | 0 kayıt, 0 küme, boş durum: "Bu filtreyle haritada küme yok Seçilen filtre birleşimine uyan kaza kaydı bulunmuyor. Küme etiketleri değiştirilmedi; fi" | ✅ geçti |  |
| F14 | 3D Şehir › Filtreler | Filtreleri sıfırla | Tüm filtreler temizlenir, seçili model moduna dönülür (4.179 küme) | 4.179 küme, bant yok | ✅ geçti |  |
| F17 | 3D Şehir › Filtreler | Bu filtreyle yeni kümeleme başlat | Filtre uygulanır ve Laboratuvar filtre kapsamıyla açılır; kapsam sayısı API ile aynı | Laboratuvar: kapsam 6.686 kayıt | ✅ geçti |  |
| F19 | Laboratuvar | Kapsam › Filtreleri düzenle (3D Keşif) | 3D Keşif Filtreler sekmesiyle açılır, filtreler korunur | Filtreler sekmesi açık, Staten Island seçili | ✅ geçti |  |
| E01 | 3D Şehir | Sol panel sekmeleri (Görünüm/Filtreler) | Sekmeler panel içeriğini değiştirir | Filtreler ↔ Görünüm | ✅ geçti |  |
| E02 | 3D Şehir | Araç çubuğu › Filtreler | Düğme Filtreler sekmesini açıp kapatır (aria-pressed) | aria-pressed true → false | ✅ geçti |  |
| E03-MANHATTAN | 3D Şehir | İlçe kamerası › MANHATTAN | Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir | merkez -73.968, 40.771 · zoom 10.7 | ✅ geçti |  |
| E03-BROOKLYN | 3D Şehir | İlçe kamerası › BROOKLYN | Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir | merkez -73.929, 40.644 · zoom 10.8 | ✅ geçti |  |
| E03-QUEENS | 3D Şehir | İlçe kamerası › QUEENS | Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir | merkez -73.819, 40.657 · zoom 10.2 | ✅ geçti |  |
| E03-BRONX | 3D Şehir | İlçe kamerası › BRONX | Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir | merkez -73.843, 40.843 · zoom 11.1 | ✅ geçti |  |
| E03-STATEN ISLAND | 3D Şehir | İlçe kamerası › STATEN ISLAND | Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir | merkez -74.145, 40.563 · zoom 10.8 | ✅ geçti |  |
| E03-TUM | 3D Şehir | İlçe kamerası › Tüm NYC | Kamera şehir ölçeğine döner | zoom 9.40 | ✅ geçti |  |
| E05-zoom | 3D Şehir | Kamera › Yakınlaştır / Uzaklaştır | Zoom +1 / −1 | 9.40 → 10.40 → 9.40 | ✅ geçti |  |
| E05-rotate | 3D Şehir | Kamera › Sola / Sağa döndür | Yön ∓30° | -17° → -47° → -17° | ✅ geçti |  |
| E05-pitch | 3D Şehir | Kamera › Eğimi artır / azalt | Eğim ±10° | 45° → 35° → 45° | ✅ geçti |  |
| E05-north | 3D Şehir | Kamera › Kuzeye çevir | Yön 0° | yön 0.0° | ✅ geçti |  |
| E17 | 3D Şehir | Fareyle harita döndürme (sağ tık sürükle) | Sağ tuşla sürüklemek yönü değiştirir | yön 0.0° → 120.0° | ✅ geçti |  |
| E05-reset | 3D Şehir | Kamera › Görünümü sıfırla | Tüm NYC görünümüne döner, ilçe seçimi temizlenir | zoom 9.40, Tüm NYC seçili | ✅ geçti |  |
| E04-boroughs | 3D Şehir | Katman anahtarı › İlçe sınırları | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (borough-line) | ✅ geçti |  |
| E04-density | 3D Şehir | Katman anahtarı › Yoğunluk | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (density-heat-1000) | ✅ geçti |  |
| E04-centroids | 3D Şehir | Katman anahtarı › Küme merkezleri | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (centroid-circle) | ✅ geçti |  |
| E04-geometries | 3D Şehir | Katman anahtarı › Küme geometrileri | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (geom-fill) | ✅ geçti |  |
| E04-clustered | 3D Şehir | Katman anahtarı › Kümelenmiş noktalar | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (points-clustered) | ✅ geçti |  |
| E04-noise | 3D Şehir | Katman anahtarı › Gürültü noktaları | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | kapalı → visible → kapalı (points-noise) | ✅ geçti |  |
| E04-buildings | 3D Şehir | Katman anahtarı › 3D binalar | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (building-3d) | ✅ geçti |  |
| E04-models | 3D Şehir | Katman anahtarı › 3D modeller | Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner | açık → none → açık (city-models) | ✅ geçti |  |
| E06 | 3D Şehir | Gece/Gündüz düğmesi | Tema arka plan rengini değiştirir; etiket güncellenir | #0B1120 → #E8EDF3 → #0B1120 | ✅ geçti |  |
| E07 | 3D Şehir | Animasyon düzeyi seçicisi | tam/azaltılmış/kapalı: belge ve 3D katman hareket düzeyi değişir | off → reduced → full | ✅ geçti |  |
| E09 | 3D Şehir | Haritada küme merkezine tıklama | Tıklanan küme seçilir; panelde kimlik ve kayıt sayısı API ile aynı | Küme #1344: 1.444 kayıt, dbscan-52abd2c018 | ✅ geçti |  |
| E21 | 3D Şehir | Seçim sonrası kamera / bina engeli | Kümeye yaklaşınca merkez bir 3D binanın arkasında kalmaz; temsili araç notu gösterilir | bina örtüşmesi 0, zoom 19.2, eğim 62° · not: "6 temsili araç, küme yakınındaki gerçek bir yol (OSM) üzerinde hareket eden bir simülasyon…" | ✅ geçti |  |
| E22 | 3D Şehir | Temsili araç sahnesi (GLB) | Seçili küme çevresinde GLB araçlar yüklenir; gerçek kaza animasyonu olarak sunulmaz | yüklenen GLB: taxi, sedan, suv, truck, delivery, traffic-light, road-sign-stop | ✅ geçti |  |
| E10 | 3D Şehir | Küme ayrıntısı › Odakla | Kamera seçili kümeye geri uçar | merkeze uzaklık 0.00000°, zoom 19.2 | ✅ geçti |  |
| E11 | 3D Şehir | Küme ayrıntısı › Kapat (X) | Seçim temizlenir, ipucu metni geri gelir | seçim yok | ✅ geçti |  |
| E12 | 3D Şehir | Zoom'a göre nokta yükleme | zoom < 15 'yakınlaştırın'; zoom ≥ 15 görünen alan sayıları sunucudan gelir | Görünen alan: 290 konum · 10.431 olay | ✅ geçti |  |
| E13 | 3D Şehir | Gürültü noktaları anahtarı | Açılınca gürültü (−1) ve kümelenmiş noktalar ayrı katmanlarda; gürültüde küme kimliği yok | gürültü 1014 konum (küme kimliği yok), kümelenmiş 290 konum | ✅ geçti |  |
| E08 | 3D Şehir | 3D varlıklar › model yerleştir / düzenle / kaldır | Panel açılır; model seçince GLB yerleştirilir; alanlar ve 'Harita merkezine taşı' çalışır; 'Modeli kaldır' sahneden siler | sedan yerleştirildi (1 nesne), yön 90°, merkeze taşındı, kaldırıldı (0 nesne), panel kapandı | ✅ geçti |  |
| E14-month | 3D Şehir | Zaman ölçeği › month | Ölçek değişince kova sayısı ve kaydırıcı aralığı değişir; dilim sıfırlanır | 168 kova | ✅ geçti |  |
| E14-dow | 3D Şehir | Zaman ölçeği › dow | Ölçek değişince kova sayısı ve kaydırıcı aralığı değişir; dilim sıfırlanır | 7 kova | ✅ geçti |  |
| E14-hour | 3D Şehir | Zaman ölçeği › hour | Ölçek değişince kova sayısı ve kaydırıcı aralığı değişir; dilim sıfırlanır | 24 kova | ✅ geçti |  |
| E14-year | 3D Şehir | Zaman ölçeği › year | Ölçek değişince kova sayısı ve kaydırıcı aralığı değişir; dilim sıfırlanır | 15 kova | ✅ geçti |  |
| E15-next | 3D Şehir | Zaman › Sonraki/Önceki adım | Dilim ilerler/geriler; okuma alanında yıl ve kayıt sayısı API kovasıyla aynı | 2012 (85.458 kayıt) ↔ 2013 | ✅ geçti |  |
| E15-slice-map | 3D Şehir | Zaman dilimi › harita verisi | Dilim seçilince merkezler /api/records/clusters'tan gelir; kimlikler modelin alt kümesi (etiket değişmez) | 3.929 küme (tümü model kimliği) · mod model\|years=2012 | ✅ geçti |  |
| E15-play | 3D Şehir | Zaman › Oynat / Duraklat | Oynat dilimi otomatik ilerletir; Duraklat durdurur | 2012 → 2012 (duraklatınca sabit) | ✅ geçti |  |
| E15-slider | 3D Şehir | Zaman kaydırıcısı (klavye) | Ok tuşu dilimi değiştirir; aria-valuetext güncellenir | değer 0 → 1; 2013, 171.941 kayıt | ✅ geçti |  |
| E16 | 3D Şehir | Zaman histogramı çubuğuna tıklama | Tıklanan kova seçilir | "2024 — 83.692 kayıt" seçildi | ✅ geçti |  |
| E15-clear | 3D Şehir | Zaman › Dilimi kaldır (X) | Tüm dönem görünümüne döner | Tüm dönem | ✅ geçti |  |
| E20 | 3D Şehir | Üçüncü taraf altlık (OpenFreeMap) kesintisi | Karo/tilejson/glif istekleri engellense de yerel API'den 4.179 küme merkezi yüklenir ve durum 'hazır' olur | 1 altlık isteği engellendi; kaza verisi 0.7 sn'de hazır, 4.179 merkez | ✅ geçti |  |
| O01 | Genel bakış | Özeti dışa aktar (menü) | Menü üç biçim sunar; her bağlantı 200 ve doğru içerik türü döner | /api/export/records?format=md → text/markdown 3.614 B · /api/export/records?format=csv → text/csv 2.996 B · /api/export/records?format=json → application/json 17.747 B · indirme: saferoute-kayit-ozeti-6cb81d88.csv | ✅ geçti |  |
| O02 | Genel bakış | Yıllara göre grafik › Tablo/Grafik düğmesi | Tablo görünümü yıl satırlarını, Grafik görünümü çubuk grafiği gösterir | 15 yıl satırı ↔ grafik | ✅ geçti |  |
| O03 | Genel bakış | Yıl grafiği › çubuk ipucu | Çubuğun üzerine gelince yıl ve kaza sayısı ipucu görünür | 2018 Kaza 216.108 | ✅ geçti |  |
| O04 | Genel bakış | Gürültü oranı › bilgi ipucu | Bilgi simgesine odaklanınca açıklama (hata ölçüsü değildir) görünür | ipucu klavye odağıyla açıldı | ✅ geçti |  |
| O05 | Genel bakış | Kaynak bağlantısı | NYC Open Data bağlantısı yeni sekmede, rel=noopener | https://data.cityofnewyork.us/d/h9gi-nx95 | ✅ geçti |  |
| O06 | Genel bakış | Model kartları | Küme 4.179, gürültü %59,7, eligible 2.020.638 — API ile aynı | küme 4.179, gürültü %59.69 | ✅ geçti |  |
| O07 | Genel bakış | 3D haritada aç | 3D Şehir Keşfi açılır | #/kesif, harita hazır | ✅ geçti |  |
| O08 | Genel bakış | En yüksek kümeler › Haritada | İlk küme haritada seçilir; ayrıntıdaki kayıt sayısı API ile aynı | Küme #1344: 1.444 kayıt (genel bakış = ayrıntı = API) | ✅ geçti |  |
| S01 | Genel bakış | API hatası + Yeniden dene | Sunucu 500 dönerse hata kutusu ve Yeniden dene; düzelince içerik gelir | hata → yeniden dene → içerik | ✅ geçti |  |
| S02 | Laboratuvar | Boş iş geçmişi / sonuç yok durumu | İş yokken açıklayıcı boş durum | boş durum metni gösterildi | ✅ geçti |  |
| S03 | Model karşılaştırma | Yüklenme durumu | Yanıt gelene kadar iskelet (role=status) gösterilir | iskelet → tablo | ✅ geçti |  |
| A01 | Genel | Odak göstergesi | Klavyeyle odaklanan gezinme bağlantısında görünür odak halkası (odaklı/odaksız stil farklı) | odaklı: rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rg… | ✅ geçti |  |
| A02 | 3D Şehir | prefers-reduced-motion | İşletim sistemi azaltılmış hareket isterse animasyon düzeyi 'azaltılmış' başlar | motion-select = reduced | ✅ geçti |  |
| A03-genel-bakis | genel-bakis | axe-core (WCAG 2.0/2.1/2.2 A–AA) | Ciddi/kritik ihlal yok | 0 ihlal (yok), 31 geçen kural | ✅ geçti |  |
| A03-kesif | kesif | axe-core (WCAG 2.0/2.1/2.2 A–AA) | Ciddi/kritik ihlal yok | 0 ihlal (yok), 32 geçen kural | ✅ geçti |  |
| A03-laboratuvar | laboratuvar | axe-core (WCAG 2.0/2.1/2.2 A–AA) | Ciddi/kritik ihlal yok | 0 ihlal (yok), 32 geçen kural | ✅ geçti |  |
| A03-modeller | modeller | axe-core (WCAG 2.0/2.1/2.2 A–AA) | Ciddi/kritik ihlal yok | 0 ihlal (yok), 29 geçen kural | ✅ geçti |  |
| A03-veri | veri | axe-core (WCAG 2.0/2.1/2.2 A–AA) | Ciddi/kritik ihlal yok | 0 ihlal (yok), 31 geçen kural | ✅ geçti |  |
| L01 | Laboratuvar | Algoritma seçimi (DBSCAN/K-Means/HDBSCAN) | Algoritma parametre alanlarını değiştirir | k / min_cluster_size + örneklem 100.000 / eps | ✅ geçti |  |
| L02 | Laboratuvar | Öznitelik seti radyo düğmeleri | Desteklenmeyen setler devre dışı ve gerekçeli; uzay-zaman seçilince eps_gün alanı çıkar | 2 devre dışı set (gerekçeli); uzay-zaman → eps_gün | ✅ geçti |  |
| L03 | Laboratuvar | Parametre doğrulama (istemci) | Sayı olmayan / aralık dışı değer hata verir, gönder düğmesi kilitlenir | abc → 'Sayı girin', 99999 → aralık hatası, 2.5 → tamsayı hatası | ✅ geçti |  |
| L18 | Laboratuvar | Sunucu tarafı doğrulama (API) | Geçersiz parametreler 422 ve Türkçe gerekçeyle reddedilir | {"eps_m":-5,"min_samples":10} → 422 "eps_m 5–500 aralığında olmalı: -5" · {"eps_m":25,"min_samples":10,"foo":1} → 422 "DBSCAN için tanımsız parametre: ['foo']" | ✅ geçti |  |
| L04 | Laboratuvar | HDBSCAN › min_samples otomatik + eom/leaf | Onay kutusu min_samples alanını kilitler; küme seçim yöntemi değişir | min_samples kilitli, leaf seçili | ✅ geçti |  |
| L17 | Laboratuvar | Kaynak bütçesi engeli | HDBSCAN örneklemsiz tam veride bütçe uyarısı, gönder kilitli | Kaynak bütçesi aşılıyor HDBSCAN kayıt düzeyidir ve ~karesel ölçeklenir: 2.020.638 olay > 100.000 bütçe. Örneklem kullanın veya filtreyi dara | ✅ geçti |  |
| L05 | Laboratuvar | Örneklem boyutu / tohum doğrulaması | Geçersiz örneklem boyutu hata verir | 10 → hata; 100.000 geri | ✅ geçti |  |
| L07 | Laboratuvar | Kayıtlı konfigürasyon eşleşmesi → Kayıtlı sonucu yükle | DBSCAN 25 m/100 (filtresiz) Faz 3 kaydıyla eşleşir; yeniden fit yok; 4.179 küme | deney dbscan-52abd2c018 · iş 7e6d78d55275 | ✅ geçti |  |
| L13 | Laboratuvar | Kayıtlı deneyler › süzgeçler | Algoritma ve aşama seçicileri satırları süzer | K-Means ızgara: 5 / 115 deney; tüm aşamalar: 18 / 115 deney | ✅ geçti |  |
| L13b | Laboratuvar | Kayıtlı deney seçimi | K-Means k=5 sonucu: 5 küme, gürültü 'Uygulanamaz' | 5 küme, gürültü Uygulanamaz | ✅ geçti |  |
| L15 | Laboratuvar | Sonucu dışa aktar | Menü bağlantıları 200 döner | text/markdown, text/csv, application/json | ✅ geçti |  |
| L14 | Laboratuvar | Kayıtlı sonuç › Haritada göster | 3D Keşif sonuç modunda açılır; merkez sayısı sonuçla aynı; 'Seçili modele dön' çalışır | HDBSCAN 768 küme / 100.000 olay kapsamı → modele dönüş 4.179 | ✅ geçti |  |
| L16 | Laboratuvar | İş geçmişi | Geçmiş listelenir; bir işe tıklayınca iş görünümü açılır; kaynak sınırı işi gerekçesiyle görünür | 14 iş; Kaynak sınırı — iş tamamlanmadı Bellek yetersiz: kullanılabilir fiziksel bellek 1.260 MB < gereken 1.500 MB. Diğer uygul | ✅ geçti |  |
| L20 | Laboratuvar | Bellek yetersiz uyarısı (kaynak ölçümü) | can_start=false iken açık uyarı ve gerekçe (yanıt tarayıcıda değiştirildi; gerçek ölçüm aşağıda) | uyarı gösterildi · gerçek boş bellek 5.952,1 MB (eşik 1.500 MB) | ✅ geçti |  |
| L08 | Laboratuvar | Analizi başlat (gerçek ayrı süreç) | İş kuyruğa alınır ve çalışır; aşama bilgisi gösterilir (ilerleme yüzdesi uydurulmaz) | iş afe87b555107: Aşama: Kaynak gereksinimi ölçülüyor · geçen süre 0,7 sn | ✅ geçti |  |
| L09 | Laboratuvar | İptal et | Çalışan iş iptal edilir; durum 'İptal edildi'; çalışan süreç sonlandırılır | durum cancelled; sonlandırma doğrulandı: true | ✅ geçti |  |
| L10 | Laboratuvar | Yeniden dene | Yeni iş kimliği, retry_of bağlantısı; iş gerçek olarak tamamlanır | iş 4e415eac71ee: 6.686 olay → 72 küme, fit 0.03 sn | ✅ geçti |  |
| L11 | Laboratuvar | Aynı istek yeniden → önbellek | Aynı istek yeniden hesaplanmaz; 'Önbellekten' rozeti | iş c8440975915b önbellekten | ✅ geçti |  |
| L14b | Laboratuvar | Dinamik sonuç › Haritada göster | Sonuç modunda merkez sayısı sonuç özetiyle aynı; bant 'Dinamik analiz sonucu' | 72 merkez = sonuç özeti | ✅ geçti |  |
| G01 | Genel | Navigation › Brand | Yeni SVG logo (simge + SafeRoute 3D wordmark) kenar çubuğunda görünür | simge 5 vektör öğe; wordmark "SafeRoute 3D" | ✅ geçti |  |
| G02 | Genel | index.html › favikon | SVG favikon ve PNG yedekleri 200 döner, <link rel=icon> bunları gösterir | /favicon.svg image/svg+xml · /brand/icon-32.png image/png · /brand/icon-180.png image/png | ✅ geçti |  |
| G03-overview | Genel | Navigation › Genel bakış | Tıklayınca #/genel-bakis, başlık "Genel bakış · SafeRoute 3D", ekran içeriği görünür | URL #/genel-bakis, aria-current=page | ✅ geçti |  |
| G03-explorer | Genel | Navigation › 3D Şehir Keşfi | Tıklayınca #/kesif, başlık "3D Şehir Keşfi · SafeRoute 3D", ekran içeriği görünür | URL #/kesif, aria-current=page | ✅ geçti |  |
| G03-lab | Genel | Navigation › Kümeleme Laboratuvarı | Tıklayınca #/laboratuvar, başlık "Kümeleme Laboratuvarı · SafeRoute 3D", ekran içeriği görünür | URL #/laboratuvar, aria-current=page | ✅ geçti |  |
| G03-models | Genel | Navigation › Model Karşılaştırma | Tıklayınca #/modeller, başlık "Model Karşılaştırma · SafeRoute 3D", ekran içeriği görünür | URL #/modeller, aria-current=page | ✅ geçti |  |
| G03-data | Genel | Navigation › Veri Gezgini | Tıklayınca #/veri, başlık "Veri Gezgini · SafeRoute 3D", ekran içeriği görünür | URL #/veri, aria-current=page | ✅ geçti |  |
| G04 | Genel | Navigation › Daralt/Genişlet | Kenar çubuğu 248↔64 px; daraltılmışken simge ve ipucu görünür | 64 px (ipucu + simge) → 248 px | ✅ geçti |  |
| G05 | Genel | Atlama bağlantısı | İlk Tab 'İçeriğe geç'e odaklanır; Enter odağı ana içeriğe taşır | odak #main | ✅ geçti |  |
| G06 | Genel | Tarayıcı geri / doğrudan hash | Geri tuşu önceki ekrana döner; #/modeller doğrudan açılır | geri → Genel bakış; #/modeller → Model karşılaştırma | ✅ geçti |  |
| G07 | Genel (mobil) | Mobil üst çubuk › Menü çekmecesi | 390 px'te menü düğmesi çekmeceyi açar; logo görünür; bağlantı ekranı değiştirip çekmeceyi kapatır | çekmece açıldı, Veri Gezgini'ne geçildi, çekmece kapandı | ✅ geçti |  |
| M01 | Model karşılaştırma | Karşılaştırma tablosu | DBSCAN 4.179 küme / %59,7 / 0,945; K-Means k=5 gürültü 'Uygulanamaz'; HDBSCAN 100.000 örneklem | DBSCAN 4.179 / %59.69 / 0.945; K-Means k=5; HDBSCAN 100.000 olay | ✅ geçti |  |
| M02 | Model karşılaştırma | Siluet ≠ doğruluk | Sayfada 'doğruluk/accuracy' etiketli metrik yok; %94,5 yalnızca olumsuzlanmış uyarıda geçer | 1 satırda %94,5 (hepsi olumsuz); satır başlıkları: Siluet, Davies–Bouldin, DBCV | ✅ geçti |  |
| M03-dbscan-grid | Model karşılaştırma | dbscan-grid › metrik seçici | Metrik düğmesi hücre değerlerini değiştirir | Küme → Siluet → Küme | ✅ geçti |  |
| M03-hdbscan-grid | Model karşılaştırma | hdbscan-grid › metrik seçici | Metrik düğmesi hücre değerlerini değiştirir | Küme → Siluet → Küme | ✅ geçti |  |
| M04 | Model karşılaştırma | Bilgi ipuçları (Siluet satırı) | İpucu 'doğruluk DEĞİLDİR' açıklamasını gösterir | ipucu görünür | ✅ geçti |  |
| M05 | Model karşılaştırma | K-Means k taraması grafiği ipucu | Noktanın üzerine gelince k ve siluet değeri görünür | k = 10 Siluet 0,398 | ✅ geçti |  |
| R-1280x720 | Tüm ekranlar | Görüntü alanı 1280x720 | Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır | genel-bakis: taşma 0 · kesif: taşma 0 · laboratuvar: taşma 0 · modeller: taşma 0 · veri: taşma 0 | ✅ geçti |  |
| R-1440x900 | Tüm ekranlar | Görüntü alanı 1440x900 | Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır | genel-bakis: taşma 0 · kesif: taşma 0 · laboratuvar: taşma 0 · modeller: taşma 0 · veri: taşma 0 | ✅ geçti |  |
| R-1920x1080 | Tüm ekranlar | Görüntü alanı 1920x1080 | Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır | genel-bakis: taşma 0 · kesif: taşma 0 · laboratuvar: taşma 0 · modeller: taşma 0 · veri: taşma 0 | ✅ geçti |  |
| R-390x844 | Tüm ekranlar | Görüntü alanı 390x844 | Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır | genel-bakis: taşma 0 · kesif: taşma 0 · laboratuvar: taşma 0 · modeller: taşma 0 · veri: taşma 0 · mobil katman çekmecesi açıldı · mobil animasyon seçicisi görünür | ✅ geçti |  |
| R-768x1024 | Tüm ekranlar | Görüntü alanı 768x1024 | Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır | genel-bakis: taşma 0 · kesif: taşma 0 · laboratuvar: taşma 0 · modeller: taşma 0 · veri: taşma 0 | ✅ geçti |  |
| D01 | Veri Gezgini | Sekmeler (Veri hattı / Ham / İşlenmiş / Setler) | Her sekme kendi içeriğini gösterir | 4 sekme | ✅ geçti |  |
| D02 | Veri Gezgini | Ham sütunlar: 29 sütun ve açıklamalar | 29/29 sütun; her satırda anlam | 29 sütun; anlamı boş olan 0 | ✅ geçti |  |
| D03 | Veri Gezgini | Arama kutusu + boş sonuç | Arama satırları süzer; eşleşme yoksa boş durum | "borough" → 1 sütun; "zzzyok" → boş durum | ✅ geçti |  |
| D04 | Veri Gezgini | Grup ve 'Modele giriş' seçicileri | Seçiciler satırları süzer | modele girenler: 2 / 29 sütun; ilk grup: 5 / 29 sütun | ✅ geçti |  |
| D05 | Veri Gezgini | Sütun ayrıntı çekmecesi | Sütuna tıklayınca anlam/model/dönüşüm/gerekçe/eksik değer çekmecesi açılır ve kapanır | latitude çekmecesi açıldı/kapandı (Esc) | ✅ geçti |  |
| D06 | Veri Gezgini | İşlenmiş sütunlar (87) ve öznitelik setleri | 87 sütun; model setleri listelenir | 87 sütun, 7 öznitelik seti | ✅ geçti |  |
| E18 | 3D Şehir | WebGL bağlam kaybı → geri yükleme | Bağlam geri gelince veri katmanları, 4.179 merkez ve 3D katman yeniden kurulur | toparlanma 1.6 sn; 4.179 merkez, city-models katmanı var | ✅ geçti |  |
