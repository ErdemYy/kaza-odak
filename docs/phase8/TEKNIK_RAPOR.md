# SafeRoute 3D — Faz 8 Teknik Raporu: Profesyonel Arayüz Cilası, Logo Yenileme ve Tam İşlevsel Denetim

> Tarih: 2026-10-22 · Temel commit (Faz 7): `0bfe3b4` · Veri sürümü ve Faz 3 model çıktıları **değişmedi**
> (`dbscan-52abd2c018`, 4.179 küme). Ek belgeler: [`ARAYUZ_KALITE_RAPORU.md`](ARAYUZ_KALITE_RAPORU.md),
> [`FONKSIYONEL_TEST_ENVANTERI.md`](FONKSIYONEL_TEST_ENVANTERI.md),
> [`BULUNAN_VE_DUZELTILEN_HATALAR.md`](BULUNAN_VE_DUZELTILEN_HATALAR.md),
> [`LOGO_KULLANIM_KURALLARI.md`](LOGO_KULLANIM_KURALLARI.md). Kanıtlar: [`reports/phase8/`](../../reports/phase8/).

## 0. Başlangıç incelemesi

- Git temiz, `main` @ `0bfe3b4`. Okunanlar: `PROJECT_SPEC.md`, `CLAUDE.md`, Faz 4–6 teknik raporları, Faz 7 teslim
  klasörü, Faz 5/6 ekran görüntüleri, tüm ön yüz bileşenleri, FastAPI uç noktaları; ilişkiler `graphify query` ile.
- Temel çizgi: backend pytest **210 geçti**, Vitest **75 geçti**, `tsc -b` temiz, `vite build` başarılı.
- Süreçler: port 4173'teki `vite preview` ve `world-check.ts` başka projeye (YasayanDunya) aittir; **dokunulmadı**.
  Bu fazda yalnızca SafeRoute sunucuları (8000; test için 8011, 8012) ve Playwright tarayıcıları başlatıldı/durduruldu.
- "Önce" ekran görüntüleri: `reports/phase8/screenshots/before/` (5 ekran, kenar çubuğu logosu, mobil).
- Kesinti notu: rapor yazımı sırasında oturum bağlantısı koptu. Faz 8 sıfırdan başlatılmadı; tamamlanmış sonuçlar
  dosyalardan doğrulandı, yarım kalan Faz 4–6 regresyon zinciri yeniden çalıştırıldı (§6).

## 1. Yenilenen logo

Üç aday tasarlandı ve aynı sayfada 128/48/32/16 px, açık zemin ve tek renk olarak karşılaştırıldı
(`screenshots/01-logo-adaylari.png`):

| Aday | Kavram | Değerlendirme |
|---|---|---|
| **A — Kaçınan rota (seçildi)** | Şehir ızgarasına oturan güvenli rota, kavşak ölçeğindeki sıcak noktadan (kırmızı) uzaklaşır; iki bağlı analiz düğümü | 16 px'te S biçimli rota ve kırmızı nokta ayırt edilir; ürün fikrini ve ana DBSCAN'in kavşak ölçeğini anlatır; tek renkte çalışır |
| B — Ağ altıgeni | Altıgen pafta, merkezde sıcak nokta, üç düğüm | Molekül/blokzincir simgelerine benziyor; rota fikri yok |
| C — İzometrik pafta | 2,5B katmanlı pafta + rota | Genel "katmanlar" simgesine benziyor; 16 px'te bulanık |

Üretim tekrarlanabilir: `scripts/phase8_brand.py` (wordmark Plus Jakarta Sans ExtraBold glif yollarına çevrilir; SVG'de
yazı tipi, `<text>`, betik veya dış kaynak yoktur). Varlıklar `assets/brand/`:
ana logo, koyu/açık zeminli, tek renk logo; yalnız simge (koyu/açık/tek renk); uygulama simgesi; kenar çubuğu sürümü;
`favicon.svg`; `icon-32.png`, `icon-180.png`. Simge < 1 KB, logo ~10 KB. Kullanım kuralları:
[`LOGO_KULLANIM_KURALLARI.md`](LOGO_KULLANIM_KURALLARI.md).

**Uygulamada kullanıldığı yerler:** `frontend/src/components/brand/Logo.tsx` (`LogoMark`, `Wordmark`) →
`Navigation.tsx` `Brand` (masaüstü kenar çubuğu açık/daraltılmış, mobil üst çubuk, mobil gezinme çekmecesi);
`frontend/index.html` (`/favicon.svg`, `/brand/icon-32.png`, `apple-touch-icon` `/brand/icon-180.png`,
`theme-color #0B1120`); `frontend/public/brand/` (dış kullanım kopyaları). Tarayıcıda doğrulama: `G01`, `G02`, `G07`.

## 2. Değiştirilen ve eklenen dosyalar

| Dosya | Tür | Amaç |
|---|---|---|
| `frontend/src/components/brand/Logo.tsx` | yeni | Satır içi logo simgesi + wordmark |
| `frontend/src/components/layout/Navigation.tsx` | değişti | Yeni marka bileşeni |
| `frontend/index.html` | değişti | Favikon bağlantıları, `theme-color`, açıklama |
| `frontend/public/favicon.svg`, `frontend/public/brand/*` | yeni | Favikon ve marka varlıkları |
| `frontend/src/features/explorer/CityMap.tsx` | değişti | H01 (`style.load`), H02 (deney kimliği yedeği) |
| `frontend/src/features/explorer/ExplorerPage.tsx` | değişti | H02 odak koruması, H03 kompakt düzen < 1024 px, H05 boş durum, H07 mobil animasyon seçicisi |
| `frontend/src/map/style.ts` | değişti | H08 `null` bina yüksekliği |
| `frontend/src/components/AssetInspector.tsx` | değişti | H06 "Modeli kaldır" |
| `frontend/src/features/lab/AlgorithmControls.tsx` | değişti | H04 örneklem geçişi, H09 gerekçe metni |
| `frontend/src/features/lab/SavedExperiments.tsx`, `LabPage.tsx` | değişti | H09–H10 görsel |
| `frontend/e2e/phase8.spec.ts` | yeni | 19 test / 125 etkileşimli gerçek tarayıcı denetimi |
| `frontend/tests/unit/phase8.test.tsx` | yeni | 11 Vitest regresyon testi |
| `frontend/e2e/phase6-restart.spec.ts`, `frontend/e2e-perf/map.perf.ts` | değişti | Çıktı yönlendirme ortam değişkeni (Faz 6 raporları değişmesin) |
| `scripts/phase8_brand.py`, `scripts/phase8_inventory.py` | yeni | Marka üretimi; envanter tablosu |
| `assets/brand/` | yeni | Logo varlıkları + adaylar + OFL lisansı |
| `docs/phase8/*.md`, `reports/phase8/` | yeni | Raporlar, ekran görüntüleri, ölçümler |
| `graphify-out/*` | güncellendi | Bilgi grafiği |

Değiştirilmeyenler: ham ve işlenmiş veri, Faz 3 model sonuçları, GLB modelleri, backend kodu, harita motorunun yapısı,
Faz 1–7 belgeleri ve teslim dosyaları.

## 3. Görsel kalite iyileştirmeleri

Ayrıntı: [`ARAYUZ_KALITE_RAPORU.md`](ARAYUZ_KALITE_RAPORU.md). Özet: yeni marka; tablet (768–1023 px) 3D düzeni;
açıklamalı boş filtre durumu; Laboratuvar seçici/gerekçe/tablo okunabilirliği; mobil animasyon seçicisi; bina
yüksekliği olmayan parçalarda siyah dolgu yerine palet rengi. Premium koyu görsel dil korundu.

## 4. Etkileşim testleri (Playwright, gerçek sunucu)

| | Değer |
|---|---|
| Test edilen etkileşim | **125** |
| Başarılı | **125** |
| Başarısız | **0** |
| Faz 8 Playwright testi | **19 / 19 geçti** (son tam çalıştırma 6,3 dk; sonraki CSS düzeltmesinden sonra ilgili filtre testi yeniden: 1/1) |
| İlk çalıştırma (düzeltme öncesi) | 59 kayıt · 56 geçti · 3 başarısız; 10 test başarısız/zaman aşımı (bkz. hata raporu) |

Ekran dağılımı: 3D Şehir 45, Filtreler 15, Laboratuvar 21, Genel/gezinme 12, Genel bakış 9, Model karşılaştırma 7,
Veri gezgini 6, responsive 5, axe 5. Tam tablo: [`FONKSIYONEL_TEST_ENVANTERI.md`](FONKSIYONEL_TEST_ENVANTERI.md).

Görünen ama işlevsiz bırakılan kontrol **kalmadı**. Sonuç modunda "Küme geometrileri" anahtarı işlev göstermez; bu,
arayüzde "Yalnızca seçili modelde (dışbükey zarf) mevcut" olarak açıkça yazılıdır (Faz 6'dan beri, bilinçli).

## 5. Bulunan ve düzeltilen hatalar

10 uygulama hatası bulundu ve **10'u da düzeltildi**; ayrıca Faz 8'in kendi değişikliklerinden 2 gerileme yakalanıp
düzeltildi. Kök neden ve testleriyle: [`BULUNAN_VE_DUZELTILEN_HATALAR.md`](BULUNAN_VE_DUZELTILEN_HATALAR.md).

| # | Hata | Önem |
|---|---|---|
| H01 | Kaza katmanları üçüncü taraf altlık servisinin tam yüklenmesine bağlıydı | Yüksek |
| H02 | "Haritada aç" yarış durumu → boş deney kimliği, 409, konsol hataları | Orta |
| H03 | 768–1023 px tablette 3D panelleri haritayı/zaman çubuğunu eziyordu | Orta |
| H04 | HDBSCAN örneklemi DBSCAN/K-Means'e taşınıyordu | Orta |
| H05 | Boş filtre sonucunda açıklama yoktu | Orta |
| H06 | Yerleştirilen GLB modeli kaldırılamıyordu | Düşük |
| H07 | Mobilde animasyon düzeyi seçicisi yoktu | Düşük |
| H08 | `null` bina yüksekliği → konsol uyarısı + siyah dolgu | Düşük |
| H09 | Laboratuvar seçici/gerekçe/kaynak satırı okunabilirliği | Düşük |
| H10 | Kayıtlı deney tablosunda metrik sütunları gizli | Düşük |

**Düzeltilemeyen:** yok. Bilinen sınırlılıklar §11'de.

## 6. API ve veri doğruluğu testleri

- Model karşılaştırma (`M01`): DBSCAN **4.179** küme, gürültü **%59,69**, siluet **0,945**; K-Means **k = 5**, gürültü
  "Uygulanamaz"; HDBSCAN **100.000** olay örneklemi, 768 küme — API, arayüz ve Faz 3 kaydı aynı. `M02`: "accuracy"
  geçmez; %94,5 yalnızca "doğruluk anlamına gelmez" uyarısında.
- Küme ayrıntısı: Küme #1344 = 1.444 kayıt (genel bakış = ayrıntı = `/api/clusters/1344`) (`O08`, `E09`).
- Filtre: önizleme her adımda `/api/records/summary` ile aynı (Staten Island 99.401; + 2019 6.686; …);
  filtrelenmiş modda 33 / 4.179 küme, tüm kimlikler tam veri modelinde (etiketler değişmedi) (`F13`); filtre etkinken
  Küme #243 tam 255 / filtrelenmiş 4 (`F18`).
- Sunucu doğrulaması: geçersiz `eps_m = −5` ve tanımsız parametre → **422** Türkçe gerekçe (`L18`).
- Dinamik iş (yalıtılmış sunucu, Staten Island 2019, 6.686 olay): başlat → iptal (süreç sonlandırması doğrulandı)
  → yeniden dene → **72 küme**, fit 0,03 sn, tepe 183 MB → aynı istek önbellekten → haritada 72 merkez (`L08–L11`, `L14b`).
- Yeniden başlatmada kalıcılık: Faz 6 `phase6-restart.spec.ts` gerçek çökme senaryosu **geçti** (§10).
- Backend pytest: **210 / 210 geçti** (Faz 8'de backend değişmedi).

## 7. 3D harita testleri

| Test | Sonuç |
|---|---|
| Beş ilçe + Tüm NYC kamera geçişi (merkez ilçe sınır kutusunda) | 6/6 |
| Kamera düğmeleri (yakın/uzak, döndür, eğim, kuzey, sıfırla) + sağ tık sürükle döndürme | 6/6 |
| 8 katman anahtarı (MapLibre görünürlüğü doğrulandı) | 8/8 |
| Gece/gündüz (arka plan `#0B1120` ↔ `#E8EDF3`), animasyon tam/azaltılmış/kapalı | 2/2 |
| Küme tıklama, detay paneli, Odakla, Kapat | 4/4 |
| Bina engeli: seçimden sonra merkezde bina örtüşmesi 0 (zoom 19,2, eğim 62°) | geçti |
| GLB: 7 model yüklendi (taxi, sedan, suv, truck, delivery, traffic-light, road-sign-stop); not "temsili … simülasyon" | geçti |
| Zoom'a göre noktalar: zoom 13,5 "yakınlaştırın" → 16,2: 290 konum · 10.431 olay | geçti |
| Gürültü 1.014 konum (küme kimliği yok) ↔ kümelenmiş 290 konum ayrı katman | geçti |
| Zaman oynatma (4 ölçek, ileri/geri, oynat/duraklat, kaydırıcı, çubuk, temizle; merkezler model alt kümesi) | 9/9 |
| WebGL bağlam kaybı → 1,6 sn'de toparlanma (SwiftShader), 4.179 merkez + `city-models` | geçti |
| Altlık servisi engelliyken kaza verisi 0,65 sn'de hazır (H01 regresyonu) | geçti |

## 8. Konsol ve ağ hataları

Son çalıştırmada (19 test) uygulama kaynaklı beklenmeyen konsol hatası, başarısız istek veya ≥ 400 yanıt **yok**.
Kayıttaki tüm mesajların nedeni bilinmektedir:

| Mesaj | Kaynak | Neden |
|---|---|---|
| `500 /api/overview` | Uygulama (bilinçli) | `S01` hata durumu testi yanıtı değiştirir |
| `net::ERR_CONNECTION_FAILED tiles.openfreemap.org` | Üçüncü taraf (bilinçli) | `E20` altlık kesintisi testi |
| `Custom layer 'city-models' cannot be restored after WebGL context loss` | MapLibre uyarısı | Beklenen; uygulama katmanı bağlam geri gelince yeniden ekler (`E18`) |

İlk çalıştırmada görülen ve **düzeltilen**: `409 /api/clusters/1344?experiment_id=` + `source 'centroids' does not
exist` (H02); `fill-extrusion-height … null` (H08); `Map cannot fit within canvas` (H03). Üçüncü taraf ağ sorunları
ayrı kaydedildi: OpenFreeMap `ERR_CONNECTION_RESET` / `ERR_NETWORK_CHANGED` (servis kaynaklı; uygulama hatası değil,
ancak H01'i ortaya çıkardı). Ölçülen gecikme: tilejson 4,4 sn, glif 16,7 sn.

## 9. Performans ölçümleri (gerçek GPU)

`npx playwright test -c playwright.perf.config.ts` (Faz 6 betiği), çıktı `reports/phase8/perf/map_performance.json`.
Çizici `WEBGL_debug_renderer_info` ile doğrulandı.

| | NVIDIA RTX 4050 (varsayılan) | NVIDIA RTX 4050 (yüksek perf.) | SwiftShader (yazılım — GPU değil) |
|---|---:|---:|---:|
| Kaza verisi hazır (`load_status_ready`) | **0,98 sn** (Faz 6: 2,09) | **0,86 sn** (Faz 6: 2,18) | 1,12 sn (Faz 6: 6,96) |
| İlk harita boşta | 1,98 sn | 2,11 sn | 3,11 sn |
| 3D döndürme FPS | 143,6 (p95 7 ms, > 50 ms kare 0) | 143,6 | 4,2 |
| Yakınlaştırma / uzaklaştırma FPS | 143,2 / 143,1 | 143,7 / 142,8 | 10,4 / 5,9 |
| Küme seçimi → GLB sahnesi hazır | 3,64 sn | 3,63 sn | 5,94 sn |
| WebGL bağlam kaybı → toparlanma | 0,87 sn | 0,89 sn | 2,69 sn |

Yorum: veri hazır olma süresindeki düşüş H01 ile tutarlıdır (artık altlık karoları beklenmiyor). FPS'teki artış
(Faz 6: 96–104) çizim kodu değişmediği için iyileştirme olarak sunulmaz; ~144 Hz ekran yenilemesine yakın tavan ve
ölçüm anındaki sistem yükü farkı olası nedenlerdir (doğrulanmadı). Faz 6'da kök nedeni belirlenemeyen AMD tümleşik GPU
102 sn soğuk başlangıcının H01 ile aynı mekanizma (altlık karolarını bekleme) olması olasıdır; AMD bu fazda yeniden
ölçülmediği için **doğrulanmadı**.

## 10. Regresyon testleri

| Paket | Sonuç | Çıktı |
|---|---|---|
| Backend pytest (Faz 1–6) | **210 / 210** | — |
| Vitest | **86 / 86** (75 önceki + 11 yeni) | — |
| `tsc -b` | hatasız | — |
| `vite build` | başarılı | — |
| Playwright Faz 8 | **19 / 19** (125/125 etkileşim) | `reports/phase8/` |
| Playwright Faz 6 (`phase6.spec.ts`) | **12 / 12** | `reports/phase8/regresyon/phase6.log` |
| Playwright Faz 6 yeniden başlatma | **1 / 1** | `regresyon/phase6-deneme1.log` |
| Playwright Faz 5 | **11 / 11** | `regresyon/phase5.log` |
| Playwright Faz 4 | **11 / 11** | `regresyon/phase4.log` |
| Performans (3 WebGL arka ucu) | **3 / 3** | `reports/phase8/perf/` |

Gizlenmeyen not: Faz 6 ana paketinin **ilk denemesi** (`phase6-deneme1.log`) oturum kesintisi sırasında çalışırken
demo testinde Laboratuvar'ın "Kayıtlı deneyler" sekmesi 420 sn içinde bulunamadı ve seri modda kalan 11 test
çalışmadı. Aynı akış hemen ardından tarayıcıda elle 5,8 sn'de açıldı; paket tek başına yeniden çalıştırıldığında
12/12 geçti. Kesintideki eşzamanlı yük (eski zincirin artık süreçleri) dışında bir neden bulunamadı; kök neden
doğrulanmadı. Faz 4–6 çıktıları ortam değişkenleriyle `reports/phase8/regresyon/` altına yönlendirildi;
`reports/phase4–6` değişmedi. Hiçbir test kaldırılmadı veya devre dışı bırakılmadı. Faz 6 testlerinde değişiklik yalnızca
çıktı yolu yönlendirmesidir.

## 11. Responsive ve erişilebilirlik

- 1920×1080, 1440×900, 1280×720, 768×1024, 390×844: beş ekranın tamamında yatay taşma **0**; Faz 6 paketi ayrıca
  390×844@3x, 820×1180@2x, 1280×800, 1920×1080, 2560×1440@2x geçti.
- Boş durum paneli 390/768/1280'de mod bandı ve zaman çubuğuyla çakışmıyor (ölçüldü; `13b-bos-filtre-*.png`).
- axe (WCAG 2.0/2.1/2.2 A–AA): beş ekranda **0 ihlal**. Klavye, odak halkası, `prefers-reduced-motion` doğrulandı.

## 12. Bilinen sınırlılıklar

1. Altlık harita görüntüsü OpenFreeMap'e bağlıdır; çevrimdışı karo yoktur (kaza katmanları artık bağımsızdır).
2. 3D varlık inceleyici < 640 px'te gizlidir.
3. Zaman ölçeği değişiminde yanıt gelene kadar (< 1 sn) önceki ölçeğin kovaları görünür.
4. "Bellek yetersiz" uyarısı tarayıcıda yanıt değiştirilerek gösterildi (makinede yeterli bellek vardı: 5.952 MB);
   gerçek kaynak sınırı işi Faz 6 geçmişinden doğrulandı.
5. Ekran okuyucuyla elle test yapılmadı; AMD tümleşik GPU bu fazda ölçülmedi.
6. Faz 6 §14'teki güvenlik sınırlılıkları (kimlik doğrulama, TLS, CSP yok) aynen geçerlidir; Faz 6 güvenlik
   önlemleri (girdi doğrulama, bellek koruma, süreç sonlandırma, kalıcı iş kaydı, önbellek) değiştirilmedi ve
   pytest + `L18`, `L09`, `L11` ile yeniden doğrulandı.

## 13. Graphify güncellemesi

`graphify update .` (AST; kurulum korunarak): **2.722 düğüm, 7.036 kenar, 129 topluluk** (Faz 6: 2.413 / 6.546 / 112).
`diagnose multigraph`: eksik uç 0, sarkan uç 0, doğrulanmamış kod düğümü 0, yinelenen kenar 0. `graphify query`
yeni düğümleri buluyor (`LogoMark()`, `Brand()`, `phase8_brand.py`, `phase8.spec.ts`). Topluluk adları LLM ile yeniden
etiketlenmedi (API anahtarı gerekir). Sembolsüz 7 yapılandırma dosyası uyarısı beklenendir.

## 14. Git

Bu raporu içeren commit: `fix: polish SafeRoute 3D UI and complete functional audit` (kimlik kapanış mesajında).
Büyük veri, `frontend/dist`, `test-results/`, regresyon/ilk çalıştırma ekran görüntüleri Git dışındadır.
