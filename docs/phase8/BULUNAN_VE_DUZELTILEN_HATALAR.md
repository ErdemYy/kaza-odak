# SafeRoute 3D — Faz 8: Bulunan ve Düzeltilen Hatalar

> Tarih: 2026-10-22 · Temel commit: `0bfe3b4` (Faz 7). Kanıt: `reports/phase8/ilk-calistirma/` (düzeltmeler öncesi
> gerçek tarayıcı çalıştırması), `reports/phase8/interaction_results.json` (düzeltmeler sonrası, 125/125),
> `reports/phase8/screenshots/`. Her hata gerçek FastAPI sunucusu + gerçek NYC verisi + Chromium (Playwright) ile
> bulundu veya kod incelemesiyle bulunup tarayıcıda doğrulandı; bulunma yolu her satırda yazılıdır.

## Özet

| # | Hata | Ekran | Önem | Bulunma | Durum | Regresyon testi |
|---|---|---|---|---|---|---|
| H01 | Kaza katmanları üçüncü taraf altlık servisinin tam yüklenmesini bekliyordu; servis yavaş/erişilemezken veri hiç görünmüyordu | 3D Şehir | **Yüksek** | Tarayıcı (ilk çalıştırma: 6 test) | Düzeltildi | E2E `E20`; dolaylı tüm 3D testleri |
| H02 | Genel bakış → "Haritada": veri yüklenmeden küme seçimi → boş `experiment_id`, **409**, konsol hataları | Genel bakış → 3D | Orta | Tarayıcı (konsol/ağ kaydı) | Düzeltildi | E2E `O08` (+ temiz konsol) |
| H03 | 768–1023 px tablette masaüstü panelleri haritayı ve zaman çubuğunu eziyor, kamera kontrolleriyle çakışıyordu; MapLibre "cannot fit" uyarısı | 3D Şehir | Orta | Tarayıcı (ekran görüntüsü + konsol) | Düzeltildi | E2E `R-768x1024`; Vitest (kompakt düzen) |
| H04 | HDBSCAN'in zorladığı örneklem, DBSCAN/K-Means'e dönünce açık kalıyordu; ana DBSCAN konfigürasyonu Faz 3 kaydıyla eşleşmiyordu | Laboratuvar | Orta | Tarayıcı (`L07`) | Düzeltildi | E2E `L07`; Vitest |
| H05 | Filtre 0 sonuç verdiğinde haritada açıklama yoktu (boş harita, neden belirsiz) | 3D Şehir | Orta | Kod incelemesi → tarayıcı (`F16`) | Düzeltildi | E2E `F16`; Vitest ×3 |
| H06 | 3D varlık inceleyicide yerleştirilen GLB modeli kaldırmanın yolu yoktu (panel kapanınca model haritada kalıyordu) | 3D Şehir | Düşük | Kod incelemesi → tarayıcı | Düzeltildi | E2E `E08`; Vitest ×2 |
| H07 | Mobilde (< 640 px) animasyon düzeyi seçicisi gizliydi; azaltma/kapama yalnızca işletim sistemi ayarıyla mümkündü | 3D Şehir (mobil) | Düşük | Kod incelemesi → tarayıcı (`R-390x844`) | Düzeltildi | E2E `R-390x844`; Vitest |
| H08 | Bazı OSM bina parçalarında `render_height = null` → konsolda boya uyarıları ve siyah dolgu | 3D Şehir | Düşük | Tarayıcı (konsol kaydı) | Düzeltildi | E2E konsol kaydı (uyarı yok) |
| H09 | Laboratuvar: "Tüm algoritmalar" seçicisi kesik; desteklenmeyen öznitelik seti gerekçeleri 2 satırda "…" ile gizleniyordu; kaynak satırında tek kelime alt satıra düşüyordu | Laboratuvar | Düşük (görsel) | Tarayıcı ekran görüntüsü | Düzeltildi | Ekran görüntüsü `14-…` |
| H10 | Kayıtlı deney tablosunda asıl metrik sütunları (Olay, Küme, Gürültü, Siluet, Süre) 1440 px'te yatay kaydırmanın arkasında kalıyordu | Laboratuvar | Düşük (görsel/işlev) | Tarayıcı ekran görüntüsü | Düzeltildi | Ekran görüntüsü `25-responsive-1440x900-laboratuvar` |

Faz 8 sırasında **kendi değişikliklerimin** yol açtığı ve son çalıştırmadan önce yakalanıp düzeltilen iki gerileme
ayrıca kayıt altındadır (gizlenmemiştir):

| # | Gerileme | Bulunma | Düzeltme |
|---|---|---|---|
| G1 | Yeni wordmark rolsüz `<span>` üzerinde `aria-label` taşıyordu → axe **ciddi** ihlal `aria-prohibited-attr` (Genel bakış) | Tarayıcı axe (`A03-genel-bakis`, ilk çalıştırma) | Wordmark düz metne çevrildi; Vitest "aria-label yok" denetimi |
| G2 | Yeni boş-durum paneli, sarılan mod bandıyla üst üste biniyordu (1440 px'te hafif; 390 ve 768 px'te bant altı 203/173 px > panel üstü 180/132 px) | Ekran görüntüsü + konum ölçümü | Panel haritanın dikey ortasına alındı; 390/768/1280 px'te bant ve zaman çubuğuyla kesişme yok (ölçüldü, `13b-bos-filtre-*.png`) |

## Ayrıntılar

### H01 — Kaza katmanları altlık servisine bağlıydı (Yüksek)

- **Belirti:** 3D Şehir Keşfi "Harita ve doğrulanmış katmanlar yükleniyor…" durumunda kalıyor; ilk çalıştırmada 3D
  ekranını açan 6 test 90 sn içinde "hazır" durumuna ulaşamadı (`openExplorer`), biri WebGL testinde tilejson isteği
  `net::ERR_NETWORK_CHANGED` ile düştüğünde.
- **Ölçüm:** `tiles.openfreemap.org/planet` (tilejson) 4,4 sn, glif dosyası 16,7 sn (curl, aynı gün).
- **Kök neden:** `CityMap.tsx` veri katmanlarını, model meta verisini ve merkezleri MapLibre'nin `load` olayında
  kuruyordu. `load`, stilin TÜM kaynakları (üçüncü taraf vektör karoları, glifler) indirilip ilk tam çizim yapılınca
  tetiklenir. Yerel FastAPI hazır olsa bile altlık yavaşsa veri hiç yüklenmiyor, tilejson isteği başarısızsa `load`
  hiç gelmiyordu.
- **Düzeltme:** Kurulum `style.load` olayına taşındı (stil işlenir işlenmez; kaynak indirmesini beklemez). Harita
  motoru yeniden yazılmadı; yalnızca başlatma olayı değişti, tek seferlik kurulum koruması (`initialized`) eklendi.
- **Doğrulama:** `E20` — OpenFreeMap istekleri tarayıcıda engellenmişken kaza verisi **0,65 sn**'de hazır, 4.179 merkez.
  Düzeltme sonrası 3D testlerinin tamamı geçti. Altlık sokak/bina görüntüsü elbette yine OpenFreeMap'e bağlıdır.

### H02 — "Haritada aç" yarış durumu: 409 ve konsol hataları (Orta)

- **Belirti:** Genel bakıştaki "Haritada" düğmesi, 3D ekranı ilk kez açılırken basıldığında ağda
  `409 /api/clusters/1344?experiment_id=` ve konsolda `MapLibre: The source 'centroids' does not exist`,
  `'geometries' does not exist`.
- **Kök neden:** `ExplorerPage`'deki odak etkisi 300 ms sonra `selectCluster` çağırıyordu; merkezler henüz yüklenmediği
  için küme→deney kimliği dizini boştu (boş kimlik → sunucu doğru biçimde 409 döndü) ve seçim durumu henüz eklenmemiş
  kaynaklara yazılıyordu.
- **Düzeltme:** Odak isteği yalnızca küme katmanı sayıları geldikten sonra işlenir (`dataReady = layerCounts !== null`,
  etki bağımlılığında); `selectCluster` dizinde kimlik yoksa seçili modelin deney kimliğini kullanır.
- **Doğrulama:** `O08` — Küme #1344: genel bakış = ayrıntı paneli = API (1.444 kayıt); testin konsol/ağ kaydı temiz.

### H03 — Tablet düzeni (Orta)

- **Belirti:** 768×1024'te sol panel (320 px) ve sağ panel (340 px) masaüstü gibi açık; zaman paneli ~25 px genişliğe
  sıkışıp "Tüm dönem · 2.020.638 kayıt" kelime kelime kırılıyordu; kamera kontrolleri zaman paneline biniyordu;
  `Map cannot fit within canvas` uyarısı (kenar boşlukları 344 + 364 px > tuval).
- **Kök neden:** Kompakt düzen eşiği 767 px idi; 768–1023 px masaüstü düzenini alıyordu.
- **Düzeltme:** Eşik `(max-width: 1023px)`; kamera kenar boşlukları ve araç çubuğu düğmeleri (`lg:`) buna uyarlandı.
  Tablet artık tam genişlik harita + alttan açılan katman/ayrıntı çekmeceleri kullanır.
- **Doğrulama:** `R-768x1024` (5 ekran, taşma 0), konsol uyarısı yok; `25-responsive-768x1024-kesif.png`.

### H04 — HDBSCAN → DBSCAN geçişinde örneklemin taşınması (Orta)

- **Belirti:** HDBSCAN seçilip DBSCAN'e dönülünce "Basit rastgele olay örneklemi kullan" açık ve 100.000 kalıyordu;
  25 m / 100 konfigürasyonu Faz 3 kaydıyla eşleşmedi, "Kayıtlı sonucu yükle" yerine örneklemli yeni fit önerildi.
- **Kök neden:** `setAlgo`, HDBSCAN için örneklemi zorla açıyor ama başka algoritmaya geçişte geri almıyordu.
- **Düzeltme:** HDBSCAN'den çıkarken zorlanan örneklem kapatılır ve boyut varsayılana (50.000) döner. Kullanıcının
  DBSCAN/K-Means'te kendisinin açtığı örneklem korunur.
- **Doğrulama:** `L07` (gerçek: kayıt eşleşmesi → 4.179 küme, gürültü %59,7, yeniden fit yok) + Vitest.

### H05 — Boş filtre sonucu (Orta)

- **Belirti:** Ör. Staten Island · 2019-02-03 · yalnızca ölümlü → 0 kayıt; harita boş, neden yazılmıyordu.
- **Düzeltme:** Haritada `role="status"` boş durum paneli: 0 kayıt ise "filtre birleşimine uyan kayıt yok"; kayıt var
  ama kümeye düşmüyorsa "N kayıt var; tümü gürültü (−1)". "Küme etiketleri değiştirilmedi" notu, "Filtreleri sıfırla"
  ve "Filtreleri düzenle" düğmeleri. Sayı `/api/records/summary`'den gelir.
- **Doğrulama:** `F16` (gerçek API: 0 kayıt, 0 merkez, panel görünür), Vitest ×3 (0 kayıt / gürültü / filtresiz yok).

### H06 — GLB modelini kaldırma (Düşük)

- **Kök neden:** `AssetInspector` yalnızca yerleştirme/düzenleme sunuyordu; `CityModelsLayer.setInspector(null)` var
  olduğu hâlde arayüzden çağrılamıyordu.
- **Düzeltme:** "Modeli kaldır" düğmesi + "paneli kapatmak modeli bırakır" notu.
- **Doğrulama:** `E08` — inceleyici grubu 1 → 0 nesne (gerçek Three.js sahnesi).

### H07 — Mobil animasyon seçicisi (Düşük)

- **Düzeltme:** Mobil/tablet katman çekmecesine "Animasyon düzeyi" seçicisi (`mobile-motion-select`); aynı depo
  durumunu ve `data-motion` özniteliğini değiştirir.
- **Doğrulama:** `R-390x844`, Vitest.

### H08 — Bina yüksekliği `null` (Düşük)

- **Belirti:** `layers[building-3d].paint.fill-extrusion-height: Expected value to be of type number, but found null`.
- **Düzeltme:** `style.ts` — yükseklik ve renk ifadelerinde `["coalesce", ["get", "render_height"], 0]`.
- **Doğrulama:** Son çalıştırmada küme/bina testlerinin konsol kaydında uyarı yok.

### H09–H10 — Laboratuvar görsel kusurları

- Seçici 150 → 176 px; gerekçeler tam metin; kaynak satırı `text-pretty`.
- Tablo: "Aşama" ve "Kapsam" deney hücresine alt satır olarak taşındı; en küçük genişlik 860 → 640 px.
  Metrik sütunları 1440 px'te kaydırmadan görünür.

## Uygulama hatası OLMAYAN, test kodu kaynaklı bulgular

İlk çalıştırmada bazı başarısızlıklar test kodumdan kaynaklandı; bunlar uygulama hatası olarak sayılmadı:
tek seçimli Radix ToggleGroup'un rolü `radiogroup` (test `group` arıyordu); ham sütun adı `latitude` (test
`LATITUDE`); aynı hash'e `goto` sayfayı yeniden yüklemiyordu (atlama bağlantısı testi); mobilde ilk `brand-mark` gizli
masaüstü kenar çubuğundaydı; zaman ölçeği değişiminde kaydırıcı yanıt gelmeden okunuyordu (`expect.poll`'a çevrildi);
tıklamalarda zaman sınırı yoktu (`actionTimeout: 20 sn` eklendi).

## Düzeltilmeyen / bilinen sınırlılıklar

1. 3D varlık inceleyici (geliştirici aracı) < 640 px'te gizlidir; telefonda kullanılamaz.
2. Zaman ölçeği değiştirildiğinde yanıt gelene kadar (yerelde < 1 sn) önceki ölçeğin kovaları görünür.
3. Altlık harita (sokaklar, binalar) üçüncü taraf OpenFreeMap'e bağlıdır; çevrimdışı karo yoktur. Kaza katmanları
   artık bundan bağımsız yüklenir.
4. MapLibre, WebGL bağlam kaybında `city-models` özel katmanı için uyarı yazar; uygulama katmanı bilinçli olarak
   yeniden ekler (beklenen uyarı).
5. "Bellek yetersiz" uyarısı, makinede yeterli bellek olduğu için tarayıcıda yanıt değiştirilerek gösterildi (`L20`);
   gerçek bir kaynak sınırı işi (Faz 6, boş bellek 1.260 MB < 1.500 MB) iş geçmişinden açılarak doğrulandı (`L16`).
