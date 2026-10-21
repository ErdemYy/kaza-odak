# SafeRoute 3D — Faz 6 Performans Raporu

> Tarih: 2026-10-21 · Ölçüm dosyaları: [`reports/phase6/map_performance.json`](../../reports/phase6/map_performance.json),
> [`reports/phase6/geo_benchmark.json`](../../reports/phase6/geo_benchmark.json),
> [`reports/phase6/e2e_measurements.json`](../../reports/phase6/e2e_measurements.json),
> [`reports/phase6/restart_scenario.json`](../../reports/phase6/restart_scenario.json).
> Ölçüm betikleri: `frontend/e2e-perf/map.perf.ts` (`npx playwright test -c playwright.perf.config.ts`),
> `scripts/phase6_geo_benchmark.py`. Tüm sayılar bu dosyalardan alınmıştır.

## 1. Ortam

| Bileşen | Değer |
|---|---|
| Makine | Windows 11 Home, AMD Ryzen 7 7735HS (8 çekirdek / 16 iş parçacığı), 15,6 GB RAM |
| GPU | AMD Radeon tümleşik (512 MB) + **NVIDIA GeForce RTX 4050 Laptop** (6 GB sınıfı; Windows 4 GB raporluyor) |
| Tarayıcı | Chrome for Testing 156 (Playwright chromium 1248), başsız; 1600×900, DPR 1 |
| Sunucu | `saferoute serve` (FastAPI/uvicorn, Python 3.12), aynı makinede |
| Bellek koşulu | Ölçümler sırasında sistemin boş fiziksel belleği 0,5–3,3 GB arasında dalgalandı (başka uygulamalar açık) |

**Donanım doğrulaması:** her ölçümde `WEBGL_debug_renderer_info` okunup dosyaya yazıldı. Faz 5'teki tüm tarayıcı
ölçümleri SwiftShader (yazılım) ile alınmıştı; **bu fazda ilk kez gerçek GPU ölçüldü.** Yazılım WebGL sonuçları ayrı
satırda ve "GPU değildir" etiketiyle verilmiştir.

| Proje | Doğrulanan çizici | Tür |
|---|---|---|
| gpu-amd (1. çalıştırma) | ANGLE (AMD Radeon(TM) Graphics, Direct3D11) | Donanım (tümleşik GPU) |
| gpu-varsayilan (2. çalıştırma) | ANGLE (NVIDIA GeForce RTX 4050 Laptop GPU, Direct3D11) | Donanım (harici GPU) |
| gpu-yuksek-performans | ANGLE (NVIDIA GeForce RTX 4050 Laptop GPU, Direct3D11) | Donanım (harici GPU) |
| swiftshader-yazilim | ANGLE (SwiftShader Device (Subzero)) | **Yazılım — GPU performansı DEĞİLDİR** |

Not: aynı "varsayılan" yapılandırmada Windows ilk çalıştırmada AMD tümleşik GPU'yu, ikincisinde NVIDIA'yı seçti
(sürücü/güç politikası). İkisi de ayrı satırda raporlandı.

## 2. Harita ve 3D (gerçek uygulama, gerçek veri)

Senaryo: `/#/kesif` açılışı → Manhattan Midtown, zoom 15,5, eğim 60°, 3D binalar → 5 sn'de 120° döndürme →
zoom 10,5 → 16 → 10,5 (her biri 4 sn) → küme #1344 seçimi (temsili GLB sahnesi) → modellerle 4 sn döndürme →
yapay WebGL bağlam kaybı + geri yükleme.

| Ölçüm | AMD tümleşik | NVIDIA (varsayılan) | NVIDIA (yüksek perf.) | SwiftShader (yazılım) |
|---|---:|---:|---:|---:|
| HTML yüklendi (DOMContentLoaded) | 360 ms | 304 ms | 311 ms | 414 ms |
| Veri katmanları hazır (`load-status = ready`) | 102.693 ms* | 2.088 ms | 2.175 ms | 6.962 ms |
| İlk harita boşta (karolar yüklendi) | 103.790 ms* | 2.939 ms | 2.719 ms | 8.874 ms |
| Kamera döndürme, 3D binalar — FPS | 76,5 | 96,3 | 104,4 | 2,6 |
| Döndürme — p95 / en uzun kare | 20,7 / 41,9 ms | 14,0 / 20,9 ms | 14,0 / 14,0 ms | 716,6 / 716,6 ms |
| Yakınlaştırma 10,5→16 — FPS · >50 ms kare | 99,8 · 5 | 143,0 · 0 | 140,9 · 0 | 9,2 · 9 |
| Uzaklaştırma 16→10,5 — FPS · >50 ms kare · en uzun | 113,8 · 3 · 493 ms | 142,6 · 0 · 20,7 ms | 141,2 · 0 · 27,7 ms | 4,7 · 15 · 500 ms |
| Küme tıklaması → GLB sahnesi hazır | 3.849 ms | 3.785 ms | 5.547 ms | 6.633 ms |
| GLB sahnesiyle döndürme — FPS · p95 | 140,3 · 7,1 ms | 144,0 · 7,0 ms | 140,3 · 7,1 ms | 7,6 · 233 ms |
| WebGL bağlam kaybı → 3D sahne yeniden kuruldu | 1.113 ms | 1.274 ms | 1.250 ms | 3.630 ms |
| JS yığını (kullanılan) | 431 MB** | 66 MB | 99 MB | 290 MB |

\* Tek seferlik soğuk başlangıç aykırı değeri: bu çalıştırmada `/api/meta` ve `/api/boroughs` 1,6 sn sürdü ve harita
stil/karo zinciri ~100 sn'de tamamlandı; aynı yapılandırmanın yeniden ölçümünde 2,1 sn. Kök neden doğrulanmadı (en
olası: karo sağlayıcısına ilk ağ erişimi). Kullanıcı tarafında bu durum "Harita ve doğrulanmış katmanlar yükleniyor…"
göstergesiyle görünür; sunum öncesi `-Demo` profili sunucu tarafını ısıtır, karo önbelleğini ısıtmaz.
\*\* AMD ölçümündeki yüksek yığın değeri o çalıştırmanın uzun yükleme süresiyle birlikte görüldü; NVIDIA ölçümlerinde
66–99 MB. Sızıntı testi (uzun süreli kullanım) yapılmadı.

**Yorum:** Gerçek GPU'da (her iki kart) 3D binalı eğik görünümde kamera hareketi 76–104 FPS, yakınlaştırma/
uzaklaştırma 100–143 FPS'tir; NVIDIA'da 50 ms'yi aşan kare yoktur. AMD tümleşik GPU'da yakınlaştırma sırasında yoğunluk
katmanının 1 km → 250 m geçişi ve karo yüklemesiyle 3–5 takılma (en uzun 493 ms) ölçüldü. SwiftShader 2–9 FPS ile
kullanılamaz düzeydedir; Faz 5'teki ölçümlerin GPU olmadığını bu fark açıkça gösterir.

## 3. GLB varlıkları

12 GLB isteği (6 model × tam + LOD1), toplam 241.991 bayt (sıkıştırılmış). Tekil istek 9–18 ms (NVIDIA yüksek
performans koşusunda tek seferlik 1.843 ms'lik bir istek görüldü). Yüklenen modeller: taxi, sedan, suv, truck,
delivery, traffic-light, road-sign-stop. Modeller yalnızca bir küme seçildiğinde ve zoom ≥ 14'te yüklenir (tembel);
ekranlar arasında geçişte yeniden indirilmez (Faz 5 E2E 8 korunuyor). Geometri ve malzemeler Faz 4'teki önbellekten
paylaşılır; bağlam kaybından sonra GLB'ler yeniden indirilmez, önbellekten yeniden kurulur.

## 4. API yanıt süreleri

### 4.1 Tarayıcıdan (harita açılışı, NVIDIA koşusu, ağ dahil)

| İstek | Süre | Sıkıştırılmış boyut |
|---|---:|---:|
| `/api/records/timeline?granularity=year` | 15 ms | 702 B |
| `/api/meta` | 15 ms | 1.266 B |
| `/api/density?cell=1000` | 54 ms | 15.081 B |
| `/api/boroughs` | 75 ms | 141.531 B |
| `/api/clusters` (4.179 merkez) | 89 ms | 120.604 B |

### 4.2 Görünen alan noktaları (20 gerçek görünüm, 0,04° × 0,025°, 5 tekrar medyanı, HTTP)

| Uç nokta | Medyan | p95 | Medyan gzip | En çok toplam konum | Kesilen görünüm |
|---|---:|---:|---:|---:|---:|
| Faz 4 model noktaları | 77,8 ms | 120,4 ms | 54.296 B | 8.952 | 2 / 20 |
| Filtreli kayıt noktaları (bisiklet) | 17,5 ms | 29,3 ms | 10.498 B | 2.149 | 0 |
| Kayıtlı HDBSCAN sonucu | 15,1 ms | 27,5 ms | 11.207 B | 1.746 | 0 |
| Kayıtlı HDBSCAN, 2019 zaman dilimi | 17,6 ms | 20,6 ms | 2.136 B | 293 | 0 |

Kesilen görünümlerde yanıt `total_locations` (gerçek toplam), `returned_locations` (gösterilen), `limit` (görselleştirme
sınırı) ve `next_offset` (deterministik sayfalama) alanlarını ayrı ayrı döndürür; lejant bunları ayrı satırlarda gösterir.

## 5. Coğrafi veri formatı karşılaştırması (PMTiles / vektör karo)

| Yaklaşım | Ölçülen / hesaplanan | Not |
|---|---|---|
| A) Mevcut bbox API'si | 15–78 ms medyan, 2–54 KB gzip (yukarıda) | Filtre, kayıtlı/dinamik sonuç ve zaman dilimi aynı uç noktayla |
| B) Tek statik GeoJSON (349.122 konum) | 51,6 MB JSON, **3,32 MB gzip**, Python ayrıştırma 806 ms | Yalnızca filtresiz TEK model için; her filtre/deney/dilim için ayrı dosya gerekir |
| C) Vektör karo (z14) | 296 karo, karo başına medyan 848 / p95 3.208 / en çok 6.100 konum | **Prototip üretilmedi.** Karo bayt boyutu (~10 KB medyan) 12 B/nokta varsayımıyla TAHMİNDİR |

**Karar:** mimari değiştirilmedi. Önceden üretilmiş PMTiles yalnızca tek bir sabit katmanı (filtresiz, tek model)
hızlandırabilir; uygulamanın asıl kullanımı olan 13 boyutlu filtreler, 115 kayıtlı deney, dinamik işler ve zaman
oynatması için her kombinasyona ayrı karo seti gerekir. Ölçülen bbox yanıtları zaten onlarca milisaniye ve birkaç
kilobayt düzeyinde olduğundan belirgin bir kazanç beklenmez. Bu karşılaştırma bir PMTiles prototipinin ölçümü
DEĞİLDİR; prototip Faz 7'de yalnızca altlık katman için değerlendirilebilir.

## 6. Bu fazda yapılan optimizasyonlar

| Optimizasyon | Etki (ölçülen) |
|---|---|
| Çalışan süreçlerde BLAS/OpenMP iş parçacığı sınırı (4) | Çalışan commit belleği 1.376 → 475 MB (sklearn/numpy içe aktarma + küçük K-Means; RSS ~160 MB her iki durumda) |
| Gizli keşif ekranında haritanın yeniden boyutlandırılmasının ertelenmesi (`trackResize: false` + yalnızca etkinken `ResizeObserver`) | Diğer ekranlarda pencere boyutu değişince gizli harita yeniden çizilmez/karo indirmez. Bulgu: E2E'de 1440×6000 tam sayfa ekran görüntüsü sırasında gizli harita SwiftShader'da 400+ sn CPU harcıyordu. Düzeltmeyle birlikte test ekran görüntüsü yüksekliği de 2.600 px ile sınırlandığı için iyileşmenin ne kadarının bu düzeltmeden geldiği ayrıca ölçülmedi |
| Sonuç modunda yoğunluk katmanının sonucun kendi kapsamından üretilmesi | HDBSCAN 100k örneklemi gösterilirken yoğunluk 2.020.638 değil 100.000 olay |
| Zaman dilimli sonuç uç noktaları (üyelik sabit, `np.bincount`) | Dilim başına 15–20 ms (HDBSCAN noktaları, 2019) |
| Deterministik `offset` sayfalaması (tüm nokta uç noktaları) | Sayfaların birleşimi tek büyük yanıtla birebir aynı (pytest) |

Faz 4–5'ten korunanlar: zoom'a duyarlı katmanlar (1 km / 250 m yoğunluk, zoom ≥ 15 noktalar), bbox ≤ 0,05° ve ≤ 20.000
konum sınırı, istek iptali (`AbortController`), URL anahtarlı istemci önbelleği, GLB LOD ve tembel yükleme, 4.179
kümenin MapLibre daire katmanı olarak (3D nesne olarak değil) çizilmesi — 3D sahne yalnızca seçili küme çevresinde
kurulur. 2 milyon olay hiçbir zaman tek istekle gönderilmez.

## 7. Laboratuvar iş performansı ve kaynak kullanımı (gerçek veri)

Manhattan 2018, DBSCAN eps 35 m, min_samples 15 (42.712 olay → 11.290 fit satırı), yalıtılmış iş kaydında TAZE fit:

| Ölçüm | Değer |
|---|---|
| Sonuç | 737 küme (Faz 5 önbelleğindeki aynı istekle aynı deney kimliği `dyn-ffa2ddf23cc1eeda` ve aynı küme sayısı) |
| Çalışan tepe RSS / tepe commit | 638,4 MB / 867,4 MB |
| Bellek tavanı (iş nesnesi) | 2.444 MB (= min(4.096, boş 3.213 − 768)) |
| CPU süresi / ortalama · en yüksek CPU | 7,62 sn / %39,3 · %200,5 (tek çekirdek = %100) |
| Sunucu açılışı (olay deposu dahil) | 4,2–5,1 sn (yalıtılmış sunucu), ana sunucu 1,3–1,6 sn |

## 8. Ölçülmeyenler

- Düşük donanımlı (GPU'suz dizüstü, eski tümleşik grafik) makine.
- Uzun süreli kullanımda bellek sızıntısı.
- Gerçek GPU sürücü sıfırlaması (yalnızca `WEBGL_lose_context` ile benzetildi).
- Lighthouse / Core Web Vitals.
