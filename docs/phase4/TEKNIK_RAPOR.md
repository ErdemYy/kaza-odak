# SafeRoute 3D — Faz 4 Teknik Raporu: Gerçek NYC 3D Şehir Görüntüleyici ve GLB Varlıkları

> Tarih: 2026-10-20 · Katman sürümü `4.0.0` · Veri sürümü `raw:2fe1297c24f7|p2cfg:c7ffbfdc478d|p2:2.1.1` ·
> Model `dbscan-52abd2c018` (Faz 3)
> Varlık kaydı: [`assets/3d/README.md`](../../assets/3d/README.md) · Ekran görüntüleri: [`reports/phase4/screenshots/`](../../reports/phase4/screenshots/)

Bu rapordaki sayılar ölçüm dosyalarından alınmıştır: `layer_manifest.json` (katmanlar), `reports/phase4/api_benchmark.json`,
`reports/phase4/e2e_measurements.json`, `reports/phase4/asset_optimization.json`, `reports/phase4/building_height_audit.json`.

## 1. Kullanılan harita kaynağı

| Bileşen | Seçim |
|---|---|
| Çizim motoru | MapLibre GL JS 6.15.0 (BSD-3) — veri sağlayıcısı değildir |
| Vektör karolar | OpenFreeMap genel örneği `https://tiles.openfreemap.org/planet` (OpenMapTiles şeması, OSM verisi; karo sürümü `20261011_080001_pt`, z0–14, üstü aşırı yakınlaştırma) |
| Yazı tipleri | OpenFreeMap glyph uç noktası (Noto Sans) |
| Stil | Projede yazılmış gece/gündüz stili (`frontend/src/map/style.ts`), gökyüzü/sis ve extrüzyon ışığı dahil |
| İlçe sınırları | NYC DCP *Borough Boundaries* (`gthc-hcne`, sürüm 26b), Faz 2 anlık görüntüsü, SHA-256 doğrulamalı |

**Lisans ve kullanım koşulları** (openfreemap.org, 2026-10-20'de okundu): genel örnek ücretsiz; görüntüleme/istek sınırı,
kayıt, API anahtarı ve çerez yok; ticari kullanım serbest. Atıf zorunludur — MapLibre atıf denetiminde
"OpenFreeMap · © OpenMapTiles · Veri © OpenStreetMap katkıcıları" ve NYC Open Data gösterilir. OSM verisi ODbL
lisanslıdır. SLA ve kişisel destek yoktur; çevrimdışı toplu indirme 3.000 karo / 50 MB ve en fazla 4 paralel istekle
sınırlıdır. **API anahtarı yapılandırması gerekmez.** Kesinti riskine karşı haftalık planet MBTiles ile kendi barındırma
mümkündür (Faz 6 önerisi).

## 2. Beş ilçenin destek durumu

| İlçe | Kamera kutusu (gerçek DCP sınırı) | Test |
|---|---|---|
| Manhattan | −74,0477 … −73,9067 / 40,6829 … 40,8790 | E2E-B ✓ |
| Brooklyn | −74,0419 … −73,8336 / 40,5695 … 40,7391 | E2E-B ✓, E2E-C ✓ |
| Queens | −73,9626 … −73,7000 / 40,5418 … 40,8010 | E2E-B ✓ |
| Bronx | −73,9336 … −73,7653 / 40,7854 … 40,9155 | E2E-B ✓ |
| Staten Island | −74,2556 … −74,0492 / 40,4961 … 40,6489 | E2E-B ✓ |

Kamera hedefleri sabit kodlu değildir; API'nin döndürdüğü resmî sınırların gerçek sınırlayıcı kutularından hesaplanır.
Açılışta beş ilçenin birleşim kutusu gösterilir (E2E-A: beş ilçe merkezinin tamamı görüntü alanında).

## 3. Gerçek 3D bina entegrasyonu

Binalar OpenMapTiles `building` katmanının gerçek OSM ayak izlerinden `fill-extrusion` ile üretilir (zoom ≥ 13;
`render_height`, `render_min_height`; `hide_3d` yapı parçaları ayrıca çizilir). NYC'deki OSM bina yüksekliklerinin önemli kısmının şehrin
bina ayak izi verisinin OSM'ye içe aktarımından geldiği bilinmektedir; bu, projede ayrıca doğrulanmadı.

**Yükseklik verisi denetimi** (`npm run tiles:audit`): beş ilçeden 15 z14 karosunda 65.229 bina poligonu. OpenMapTiles,
yükseklik etiketi olmayan binalara varsayılan `render_height = 5` atar; bu değer poligonların %6,3'ünde görülür
(Manhattan %5,1, Brooklyn %3,3, Queens %9,2, Bronx %6,1, Staten Island %10,3). **Bu binalar extrüde edilmez**; düz ve ayrı
renkte ("Yükseklik verisi yok", lejantta) çizilir. Böylece uydurma yükseklik gerçek veri gibi gösterilmez. Gerçekten 5 m
olan az sayıdaki bina da bu gruba düşer (muhafazakâr seçim, K-26). Not: Planetiler aynı öznitelikli binaları tek
MultiPolygon özelliğinde birleştirir; denetim özellik değil dış halka (bina poligonu) sayar.

## 4. Kullanılan GLB modeller

Otomobil (sedan), taksi, SUV, kamyonet, teslimat kamyonu (Kenney Car Kit 2.0); trafik lambası, DUR levhası, uyarı
levhası, bariyer, trafik konisi (Kenney City Kit Roads 2.2). Kitlerde otobüs yoktur; ağır taşıt olarak kamyonet ve
teslimat kamyonu kullanıldı. Araçlarda tekerlekler ayrı düğümdür ve hızla orantılı döner.

## 5. Model kaynakları ve lisanslar

| Paket | Kaynak | Lisans | Atıf | Durum |
|---|---|---|---|---|
| Car Kit 2.0 | https://kenney.nl/assets/car-kit (`kenney_car-kit.zip`, SHA-256 `f8a69b83…`) | CC0 1.0 | Zorunlu değil; "Kenney" belirtildi | Kullanıldı |
| City Kit (Roads) 2.2 | https://kenney.nl/assets/city-kit-roads (`kenney_city-kit-roads.zip`, SHA-256 `374a4552…`) | CC0 1.0 | Zorunlu değil; "Kenney" belirtildi | Kullanıldı |
| Cars Bundle (7 GLB) | Arşivde kaynak/yazar/lisans bilgisi yok; GLB meta verisi yalnızca `obj2gltf` | Doğrulanamadı | — | **Kullanılmadı** |

Her modelin kaynak arşiv özeti, ZIP içi yolu, orijinal ve optimize dosya SHA-256'sı `frontend/public/models/registry.json`
içindedir. Uygulama kaydı açılışta doğrular; lisans/kaynak alanı eksik veya CC0/CC BY dışı model yüklenmez.

## 6. Model optimizasyon sonuçları

gltf-transform 4.5.1 + meshoptimizer 1.3.0 (Blender kurulu değil, kullanılmadı; paketlerde hazır GLB var, OBJ/FBX
dönüşümü gerekmedi). Adımlar: harici dokunun gömülmesi, dedup, prune, weld, reorder, quantize (KHR_mesh_quantization),
meshopt sıkıştırma (EXT_meshopt_compression); araçlarda LOD1 (%50 hedef, hata ≤ %1).

| Model | Doku gömülü referans → optimize | Üçgen LOD0 (önce = sonra) / LOD1 | Doku |
|---|---|---|---|
| Sedan | 177,3 → 30,6 KB (−%83) | 2.032 / 1.596 | 512×512 PNG |
| Taksi | 180,6 → 29,9 KB (−%83) | 2.072 / 1.630 | 512×512 PNG |
| SUV | 211,3 → 34,7 KB (−%84) | 2.474 / 1.947 | 512×512 PNG |
| Kamyonet | 181,3 → 31,2 KB (−%83) | 2.082 / 1.618 | 512×512 PNG |
| Teslimat kamyonu | 243,7 → 33,7 KB (−%86) | 2.476 / 1.719 | 512×512 PNG |
| Trafik lambası | 30,8 → 16,3 KB (−%47) | 212 / — | 512×512 PNG |
| DUR / uyarı levhası | 21,4 / 22,1 → 15,1 / 15,2 KB | 104 / — | 512×512 PNG |
| Bariyer / koni | 17,7 → 14,3 / 14,4 KB | 60 / 66 | 512×512 PNG |

Görsel kalite: LOD0'da çizilen üçgen sayısı değişmez (ölçüldü); nicemleme konum hatası model boyutunun ~1/65535'i.
Doku (~11 KB paletli PNG) palet renklerinde sızma riski nedeniyle küçültülmedi. Seçili kümede aynı anda en fazla 6 araç
+ 2 donatı + 1 inceleme modeli bulunur; kopyalar tek şablondan klonlanıp GPU tamponlarını paylaşır, bu sayıda nesne için
`InstancedMesh` gerekmedi. Mesafeye göre detay: piksel başına 0,12 m üzerinde LOD1; zoom < 14'te model katmanı çizilmez.

## 7. Coğrafi koordinat doğruluğu

- **Dönüşüm zinciri:** `clip = mainMatrix(MapLibre) · T(çapa) · S(s, −s, s) · Rx(π/2) · yerel`; yerel çerçeve +X doğu,
  +Y yukarı, +Z güney (metre); `s` çapa enleminde 1 m'nin mercator karşılığı. Nesne konumu mercator farkının çapa
  ölçeğine bölünmesiyle bulunur ve aynı ölçekle geri çarpıldığından konum hatasızdır.
- **Birim testleri:** Mercator dönüşümü MapLibre'nin kendi `MercatorCoordinate` sınıfıyla 14 ondalık basamakta aynı; çapa
  matrisi + yerel ofset hedef noktanın mercator konumuna 15 basamakta eşleşir; irtifa, yön (kuzey/doğu/güney) ve ters
  dönüşüm sınanır.
- **Tarayıcıda (E2E-E):** Three.js zinciriyle hesaplanan model ekran konumu ile `map.project(boylam, enlem)` arasındaki
  fark, dönüş/eğim/zoom değişimlerinde ölçüldü (bkz. §15). Kabul eşiği 1,5 px.
- **Zemin:** Model tabanı bounding box'tan `y = 0`'a hizalanır (gömülme/havada durma yok); irtifa parametresi metre
  cinsindendir (10 m → ekranda yukarı hareket, E2E-E).
- **Yön:** Kenney araçlarının ön ekseni +Z; kuzeye yönlendirilen taksi güneyden bakıldığında arka lambalarını,
  kuzeyden bakıldığında ön ızgarasını gösterir (görsel doğrulama). Trafik sağ şeritten akar.
- **Derinlik ve sıra:** Model katmanı `renderingMode: "3d"` ile haritanın derinlik tamponunu paylaşır; binalar arkadaki
  araçları örter. Zemin düzlemindeki veri katmanları bina extrüzyonlarının altına eklenir (aksi hâlde binaların üstünde
  "yüzüyordu" — görsel denetimde bulunup düzeltildi). Model katmanı yol etiketlerinin üstündedir.
- **WebGL kaynak paylaşımı / bağlam kaybı:** Three.js aynı bağlamı kullanır, her karede `resetState()` çağrılır. MapLibre
  bağlam geri yüklemesinde stili asenkron yeniden kurar ve özel katmanları geri getirmez; uygulama `style.load` sonrasında
  veri kaynaklarını, seçim durumunu ve model katmanını yeniden kurar (GLB'ler bellek önbelleğinden). `WEBGL_lose_context`
  ile E2E testi: model aynı konumda (< 1,5 px) yeniden çizilir.
- **GeoJSON:** Tüm koordinatlar RFC 7946 [boylam, enlem]; katman üretiminde her geometri koordinatı denetlenir.

## 8. Gerçek küme sayısı

Değerler arayüze sabit yazılmadı; `model_metadata.json`, `algorithm_comparison.json` ve üyelik dosyasından okunur:

| Ölçü | Değer | Kaynak |
|---|---:|---|
| Model | DBSCAN `dbscan-52abd2c018`, eps = 25 m, min_samples = 100 | `model_metadata.json` |
| Küme | 4.179 | üyeliklerden sayıldı = Faz 3 `n_clusters_full` |
| Kümelenmiş olay | 814.578 | üyeliklerden |
| Gürültü olayı | 1.206.060 (oran %59,69) | üyeliklerden = Faz 3 `noise_ratio_full` |
| Toplam olay | 2.020.638 | = manifest satır sayısı |
| Benzersiz konum | 349.122 (36.986 kümelenmiş, 312.136 gürültü) | `locations_layer.parquet` |

**Manifest doğrulaması:** `saferoute viz-build`, `phase4_manifest.json`'daki 9 dosyanın varlığını, boyutunu ve SHA-256
özetini doğrular; uyuşmazlıkta katman üretilmez. Sunucu açılışta ürettiği 6 katman dosyasının özetini yeniden denetler.
Ayrıca: üyelik, özet ve geometri dosyalarının deney kimliği seçilen deneyle aynı; küme kimlik kümeleri üç dosyada aynı;
küme başına olay sayıları üyeliklerle aynı.

## 9. Kaza noktası görüntüleme stratejisi

| Zoom | Gösterilen | Veri yolu | Boyut (gzip) |
|---|---|---|---|
| < 12 | Yoğunluk ısı haritası (1 km UTM ızgarası, 877 hücre) + 4.179 küme merkezi | `/api/density?cell=1000`, `/api/clusters` | 15 KB + 121 KB |
| 12–15,5 | Yoğunluk (250 m ızgara, 10.860 hücre) + küme geometrileri | `/api/density?cell=250`, `/api/clusters/geometries` | 137 KB + 360 KB (bir kez) |
| ≥ 15 | Görünen alandaki benzersiz konumlar (kümelenmiş/gürültü) | `/api/points?bbox=…` (≤ 0,05°, ≤ 8.000 konum) | ~7–96 KB |

- **Kayıpsız indirgeme:** Ağırlıklı DBSCAN'de aynı koordinattaki tüm olaylar aynı etiketi alır; olaylar benzersiz
  konuma indirgenir ve her konumun tek etiketi olduğu doğrulanır. Nokta boyutu konumdaki olay sayısıyla ölçeklenir.
- **Tutarlılık:** Izgara hücre toplamları 2.020.638'e eşittir. Kesilen bbox yanıtında (en yoğun 8.000 konum, deterministik
  sıra) gerçek toplam konum/olay sayıları da döner ve lejantta "Gösterilen: en yoğun N konum" uyarısıyla gösterilir
  (E2E-D: ekrandaki sayılar aynı bbox için API toplamlarıyla aynı).
- **Sınırlar:** 0,05°'den büyük nokta sorgusu 413, geçersiz bbox/limit/tür 422 döner. Kaydırmada istekler 200 ms geciktirilir,
  önceki istek iptal edilir, kutu 0,002° ızgaraya genişletilerek küçük kaymalarda tekrar istek yapılmaz.
- Rastgele örnekleme veya üretilmiş konum yoktur.

## 10. Gürültü noktalarının yönetimi

Gürültü (−1) ayrı katmandır (`points-noise`, gri), varsayılan kapalıdır ve kullanıcı açıp kapatabilir. Açıkken nokta
sorgusu `kind=all`, yalnızca gürültü açıkken `kind=noise` olur; ikisi de kapalıysa istek yapılmaz. Gürültü olayları yoğunluk
ızgarasında ayrıca sayılır (`noise` alanı) ve model kartında toplam (1.206.060) gösterilir. Gürültü sıradan bir küme gibi
renklendirilmez veya seçilemez.

## 11. Harita katmanları

1. İlçe sınırları (resmî DCP, kesikli çizgi + hafif dolgu) 2. Yoğunluk (1 km / 250 m ısı haritası) 3. Küme merkezleri
(olay sayısına göre boyut/renk) 4. Küme geometrileri (dışbükey zarf; "istatistiksel kontur değildir" anlamıyla)
5. Kümelenmiş noktalar 6. Gürültü noktaları 7. 3D binalar (+ yükseklik verisi olmayan düz binalar) 8. 3D modeller.
Her katman panelden açılıp kapatılır; geçerli zoom dışında olduğunda panel "yakınlaştırınca/uzaklaştırınca görünür"
uyarısı verir. Katman geçişlerinde saydamlık geçişi (350 ms) kullanılır.

## 12. Kamera özellikleri

Fareyle kaydırma/yakınlaştırma/döndürme/eğme (MapLibre), araç çubuğunda yakınlaştır, uzaklaştır, ±30° döndür, ±10° eğ,
kuzeye çevir, görünümü sıfırla (beş ilçe, yön −17°, eğim 45°). İlçe seçici gerçek sınır kutusuna `fitBounds` ile gider.
Küme seçiminde `flyTo` (eğri 1,42) ile küme yarıçapına göre zoom 17,2–19,2, eğim 62°; mevcut yön korunur. Panel kenar
boşlukları hesaba katılır. Animasyon "kapalı"da geçişler anlık, "azaltılmış"ta %40 süre.

## 13. Etkileşim özellikleri

- Küme merkezine veya geometrisine tıklama → tıklanan noktaya **ekranda en yakın** küme merkezi seçilir. İlk sürümde
  ilçe ölçeğinde üst üste binen dairelerde en üstte çizilen kümenin açıldığı (#1344 yerine #1331) E2E sırasında
  bulundu ve düzeltildi; kural birim testiyle sabitlendi.
- Seçimde: merkez ve geometri vurgulanır (feature-state), kamera yakınlaşır, panelde küme kimliği ve sırası, gerçek kaza
  sayısı, ilçe, merkez koordinatı, yaralanmalı/ölümlü kaza, yaralı/ölü kişi, benzersiz konum, tarih aralığı, etkin yıl,
  p90 yarıçap, saatlik dağılım, araç türleri ve başlıca etkenler (Faz 3 küme özetinden) gösterilir.
- Kimlik güvenliği: istek `experiment_id` ile yapılır; sunucu farklı deneyin kimliğini 409 ile reddeder; istemci yanıtın
  kimlik + deney eşleşmesini ayrıca doğrular.
- 3D varlık inceleyici: model seçimi; boylam, enlem, irtifa (m), yön (° kuzeyden), ölçek parametreleri; kaynak, lisans,
  üçgen, boyut ve doku bilgisi.
- Durumlar: yükleniyor (iskelet), hata (ağ/API, "Yeniden dene"), veri yok ("Bu alanda kayıt yok"), başarı (durum çubuğu).

## 14. Animasyonlar

Seçilen kümede ışık halkası (küme p90 yarıçapına bağlı, 12–120 m) ve 2,2 sn'lik kontrollü genişleyen nabız; yumuşak
radyal parıltı; katman saydamlık geçişleri; gece/gündüz modu (boya özellikleri + gökyüzü/sis). Temsili trafik: küme
merkezine 60 m içindeki, en az 60 m kullanılabilir uzunluğu olan gerçek OSM yol çizgisinde en fazla 6 araç sağ şeritten
7–10 m/sn ile hareket eder, uçlarda görünmez olur; yol kenarına trafik lambası ve DUR levhası konur. Arayüz "N temsili
araç … simülasyondur; geçmiş kazaların hareket kaydı değildir" notunu gösterir; uygun yol yoksa araç gösterilmez ve bu
söylenir. Animasyon düzeyi: tam / azaltılmış (araçlar durur, halka sabit) / kapalı; `prefers-reduced-motion` açılışta
"azaltılmış" seçer. Parçacık efekti yoktur.

## 15. Performans ölçümleri

**Ortam:** Windows 11, 15,6 GB RAM; tarayıcı ölçümleri GPU'suz Chromium headless (SwiftShader yazılım WebGL),
1600×960. Mutlak kare süreleri donanıma bağlıdır; aşağıdaki değerler alt sınır niteliğindedir.

| Ölçü | Değer | Kaynak |
|---|---:|---|
| Katman üretimi (`viz-build`, manifest doğrulama dahil) | 1,95 sn, süreç tepe belleği 375 MB | `layer_manifest.json` |
| API sunucusu açılışı (6 dosya SHA-256 denetimi dahil) | 0,37 sn, tepe bellek 221 MB | `api_benchmark.json` |
| Açılışta API yükü (ağda, gzip) | meta 2,5 KB + kümeler 121 KB + yoğunluk 15 KB + ilçeler 142 KB ≈ 280 KB | `e2e_measurements.json` |
| Açılışta nokta isteği | 0 (2 milyon olay gönderilmez) | E2E-A |
| İlk yükleme (gezinme → veri hazır + karolar boşta) | 5,0 sn | E2E-A |
| `/api/points` Midtown z16 (1.996 konum) | medyan 37,5 ms, 20 KB gzip | `api_benchmark.json` |
| `/api/points` geniş kutu (14.814 konum → 8.000 döndü, kesildi) | medyan 128,7 ms, 96 KB gzip | `api_benchmark.json` |
| `/api/clusters/{id}` | medyan 6,9 ms | `api_benchmark.json` |
| Manhattan boyunca 5 duraklı yakın zoom gezintisi | 5 nokta isteği, en çok 2.807 konum; uzun görev 5 adet, en uzun 272 ms; ana iş parçacığı yanıt gecikmesi ≤ 30 ms | E2E-G |
| Tarayıcı JS yığını (gezinti sonrası) | 69 MB | E2E-G |
| Model–harita konum farkı (Three.js zinciri vs `map.project`, 4 kamera durumu) | en çok 3·10⁻⁸ px | E2E-E |
| Ön yüz derlemesi (gzip) | MapLibre 285 KB, Three.js 161 KB, uygulama 88 KB; GLB'ler toplam 391 KB (10 LOD0 + 5 LOD1) | `vite build` |

Konum farkı ölçümü, Three.js tarafının her karede kullandığı matrisin MapLibre'nin kendi izdüşümüyle aynı noktayı
verdiğini doğrular (çapa/ölçek/eksen hatası olsaydı fark metre-piksel düzeyinde olurdu); piksel düzeyinde görsel
doğrulama ekran görüntüleri ve yön testiyle yapıldı.

## 16. Ekran görüntüleri

Gerçek tarayıcıda (Chromium, 1600×960) Playwright ile alındı: `reports/phase4/screenshots/`

| Dosya | Görünüm |
|---|---|
| `01-nyc-genel-gorunum.png` | Açılış: beş ilçe, yoğunluk, 4.179 küme merkezi |
| `02-brooklyn-ilce-gorunumu.png` | Brooklyn odağı |
| `02-manhattan-yakin-gorunum.png` | Harlem, zoom 16: 3D binalar, kümeler, noktalar |
| `03-brooklyn-kume-secimi.png` | #1344 seçimi: halka, vurgulu geometri, temsili araçlar, panel |
| `04-gurultu-noktalari-acik.png` | Gürültü noktaları açık |
| `04-kavsak-yakin-gorunum.png` | Tillary St / Flatbush Ave Ext kavşağı, araçlar gerçek şeritte |
| `05-gece-modu.png`, `05b-gunduz-modu.png` | Aynı görünüm gece/gündüz |
| `06-glb-arac-modeli.png` | Taksi GLB, inceleyici ve lisans bilgisi |
| `07-kume-detay-paneli.png` | Küme ayrıntı paneli |

Görsel denetimde bulunup düzeltilen sorunlar: MapLibre CSS'inin harita kabını 0 yükseklikte bırakması; zoom ifadesi
hatası nedeniyle küme merkezlerinin hiç çizilmemesi (ve hatanın sessizce yutulması); yoğunluğun "puantiyeli" görünmesi
(ısı yarıçapı hücre aralığına bağlandı); sol panel ile lejantın, sağ panel ile kamera kontrollerinin çakışması; yanlış
küme seçimi; veri katmanlarının binaların üstünde yüzmesi; yol etiketlerinin araçların üstüne yazılması; araçların
zoom 18,2'de çok küçük kalması; araç olmadığında "araçlar hareket ediyor" notunun görünmesi.

## 17. Test sonuçları

| Paket | Sonuç |
|---|---|
| Arka uç pytest (Faz 1–3 + Faz 4) | **163 geçti** (149 önceki + 14 yeni: manifest bütünlüğü/kurcalama, sayı korunumu, kayıpsız indirgeme, deney kimliği, [boylam, enlem], NaN güvenliği, meta, küme kimliği eşleşmesi, bbox sorgusu ve sayılar, girdi doğrulama/limitler, yoğunluk/geometri filtreleri, kurcalanmış katman, gerçek veri tutarlılığı) |
| Ön yüz Vitest | **44 geçti**: Mercator ↔ MapLibre, çapa matrisi, yön/irtifa, bbox; varlık kaydı ve lisanslar, 10 GLB'nin yüklenmesi/üçgen/doku, bozuk-kesik-yanlış sürüm GLB, 404/ağ hatası; kamera odakları; katman görünürlüğü; küme kimliği eşleşmesi; en yakın küme seçimi; yol seçimi; temalar |
| Playwright E2E (gerçek uygulama) | **11 geçti** (5,8 dk): A açılış/beş ilçe/gerçek karo ve veri, B beş ilçe odağı, C doğru küme seçimi (gerçek fare tıklaması), D gürültü aç/kapa ve sayı tutarlılığı, E GLB konum/irtifa/yön/ölçek ve kaymazlık, F kamera, G yük ve yanıt verme, kavşak + gece/gündüz, animasyon düzeyi, WebGL bağlam kaybı, API hata durumu |
| Tip denetimi | `tsc -b` hatasız |

## 18. Graphify durumu

Graphify v0.9.90 korunarak `graphify update .` çalıştırıldı (yeniden kurulmadı): **1.491 düğüm, 3.646 kenar,
79 topluluk** (Faz 3 sonunda 1.058 / 2.714 / 53). Sağlık kontrolü: `graphify check-update .` bekleyen yeniden çıkarım
bildirmedi; `graphify diagnose multigraph` derleme sonrası grafiği basit grafik (3.646 kenar, bağlam varyantı grubu 0) olarak raporladı; çıkarıcıda 12 üretici bastırma noktası listeledi (araç notuna göre ham üretici kaybı derleme öncesinde ölçülür; bu fazda ölçülmedi);
`graphify query` yeni modülleri (`CityModelsLayer`, `anchorMatrix`, `LayerStore`, `ManifestError`) buluyor. Sembol
üretmeyen 5 yapılandırma dosyası (ör. `vite.config.ts`) beklenen uyarıdır. Topluluk adları LLM ile yeniden
etiketlenmedi (API anahtarı gerektirir).

## 19. Git commit kimliği

Bu raporu içeren commit: `feat: implement SafeRoute 3D phase 4 city visualization` (kimlik kapanış mesajında).

## 20. Bilinen sınırlılıklar

1. Harita karoları için internet gerekir; OpenFreeMap genel örneğinin SLA'sı yoktur.
2. Bina yükseklikleri OSM'den gelir; resmî NYC bina veri setiyle karşılaştırmalı doğrulama yapılmadı. `render_height = 5`
   kuralı gerçek 5 m binaları da düz gösterir.
3. Arazi (yükseklik modeli) yok; modeller deniz seviyesi düzlemine (irtifa 0) yerleşir. NYC'de eğimli caddelerde
   yerden birkaç metre fark olabilir (bina tabanları da aynı düzlemde olduğundan görsel tutarlılık korunur).
4. Küme geometrileri dışbükey zarftır; istatistiksel yoğunluk konturu değildir.
5. Temsili trafik yalnızca seçili küme çevresindedir; yol yönü (tek/çift yön) ve şerit sayısı OSM'den okunmaz.
6. Performans ölçümleri GPU'suz yazılım WebGL (SwiftShader) ile alındı; gerçek GPU'da kare süreleri daha iyidir, mutlak
   değerler donanıma bağlıdır.
7. Kitlerde otobüs modeli yok. Cars Bundle paketi lisans belirsizliği nedeniyle kullanılmadı.
8. Mobil düzende (< 768 px) yan paneller gizlenir; tam mobil deneyim Faz 5 kapsamındadır.
9. Etken metinleri kaynak veri setindeki İngilizce NYPD kodlarıdır.

## 21. Faz 5 için öneriler

1. Gösterge paneli ve kümeleme laboratuvarı: Faz 4 API'sine tarih/saat/ilçe/araç türü filtreleri (sunucu tarafı, aynı
   kayıpsız konum katmanı üzerinde), K-Means/HDBSCAN katmanları (deney kimliği zaten modele bağlı).
2. Zaman oynatma: yıllık/saatlik katmanlar için önceden hesaplanmış özetler.
3. Karolu sunum: nokta katmanını PMTiles/vektör karo olarak üretmek (bbox sınırını kaldırır).
4. shadcn/ui bileşen sistemine geçiş, mobil düzen ve klavye ile harita gezintisi.
5. Kendi barındırılan karo sunucusu (planet MBTiles) ve isteğe bağlı NYC resmî bina yükseklikleriyle karşılaştırma.
6. Gerçek GPU'da performans profili (kare süresi, bellek) ve düşük donanım modu.
