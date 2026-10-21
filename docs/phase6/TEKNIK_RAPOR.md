# SafeRoute 3D — Faz 6 Teknik Raporu: Sistem Stabilizasyonu, Güvenilirlik, Performans ve Uçtan Uca Entegrasyon

> Tarih: 2026-10-21 · Temel commit (Faz 5): `98e61a01738598735373315e225115a857020b21` ·
> Laboratuvar kod sürümü `phase5-lab:5.0.0` (hesaplama değişmedi; önbellek anahtarları geçerli kaldı) ·
> Veri sürümü `raw:2fe1297c24f7|p2cfg:c7ffbfdc478d|p2:2.1.1`.
> Ek belgeler: [`PERFORMANS_RAPORU.md`](PERFORMANS_RAPORU.md), [`DEMO_TEST_PLANI.md`](DEMO_TEST_PLANI.md),
> [`KALAN_RISKLER.md`](KALAN_RISKLER.md). Ölçüm/ekran görüntüleri: [`reports/phase6/`](../../reports/phase6/).

## 0. Ön inceleme

- **Git:** Faz 5 commit'inde, çalışma dizini temiz.
- **Süreçler:** SafeRoute sunucusu çalışmıyordu. Görülen tek ilgili olmayan süreç OpenAI Codex çalışma zamanına ait
  `host-daemon.mjs` (node) idi; dokunulmadı. Bu fazda başlatılan/durdurulan süreçler yalnızca SafeRoute sunucuları
  (8000, test için 8011) ve Playwright tarayıcılarıdır.
- **Okunanlar:** `PROJECT_SPEC.md`, `CLAUDE.md`, Faz 3–5 teknik raporları, Faz 5 ekran görüntüleri, FastAPI uç noktaları
  (`viz/api.py`, `analytics/api.py`), iş yöneticisi (`analytics/jobs.py`, `lab_worker.py`, `lab_spec.py`), sonuç katmanı
  (`results.py`), olay deposu, Zustand deposu, `CityMap`/`ExplorerPage`/`TimeControls`, laboratuvar bileşenleri, Faz 3
  model manifesti (`model_metadata.json`, `experiments.json`). Graphify (`graphify query`) ile ilişkiler bulundu,
  satırlar kaynak koddan doğrulandı.
- **Temel çizgi:** backend pytest 194 geçti; Vitest 69 geçti.
- **Kaynak durumu:** 15,6 GB RAM; ölçüm boyunca boş bellek 0,5–3,3 GB (başka uygulamalar). Gerçek GPU mevcut: AMD Radeon
  tümleşik + NVIDIA RTX 4050 Laptop.

## 1. Geliştirilen altyapı

| Modül / dosya | Yeni / değişen | Amaç |
|---|---|---|
| `analytics/jobstore.py` | **yeni** | SQLite (WAL, `synchronous=FULL`) kalıcı iş kaydı; karşılaştır-ve-değiştir durum geçişleri; şema sürümü |
| `analytics/procguard.py` | **yeni** | Windows iş nesnesi (KILL_ON_JOB_CLOSE + süreç bellek tavanı), psutil CPU/bellek örnekleme, süreç ağacı sonlandırma ve doğrulama, kimlik doğrulamalı yetim temizliği |
| `analytics/jobs.py` | yeniden yazıldı (davranış korunarak) | Kalıcı işler, açılış uzlaştırması, açık yeniden deneme, kaynak ön denetimi, izleme, SHA-256'lı sonuç, deney kimliği, yinelenen istek birleştirme |
| `analytics/results.py` | genişletildi | Zaman dilimi (üyelik sabit), sonuç kapsamı yoğunluğu, kapsam bilgisi, deterministik sayfalama |
| `analytics/api.py` | genişletildi | Kimlik doğrulama, `/api/results/{id}/timeline|density`, zaman süzgeci, `retry`, `resources`, kapanış kancası |
| `viz/api.py` | genişletildi | Host izin listesi, güvenlik başlıkları, gövde sınırı, sızıntısız 500, `lifespan` kapanış kancaları, `/api/points` ofseti |
| `analytics/filters.py`, `events.py`, `lab_spec.py`, `lab_worker.py`, `cli.py` | küçük | Tarih aralığı denetimi, maske tabanlı zaman çizelgesi, bellek/iş parçacığı bütçesi, test gecikme kancası, `serve --lab-root` |
| `scripts/start_saferoute.ps1`, `stop_saferoute.ps1` | **yeni** | Tek komutla denetim + derleme + başlatma (demo profili), güvenli durdurma |
| `scripts/phase6_geo_benchmark.py`, `frontend/e2e-perf/*`, `playwright.perf.config.ts` | **yeni** | Coğrafi format karşılaştırması, GPU/yazılım WebGL ölçümü |
| Ön yüz: `ExperimentResults`, `LabPage`, `TimeControls`, `ExplorerPage`, `CityMap`, `Legend`, `ViewPanel`, `common`, `layers`, `types`, `ModelsPage` | değişti | Yeni iş durumları, yeniden deneme, bağlantı kaybında otomatik yeniden deneme, N/A metrikleri, kaynak durumu, sonuçlarda zaman oynatma, gizli harita yeniden boyutlandırma, akademik metinler |

## 2. İş kuyruğu ve kalıcılık

**Seçim:** SQLite (Python standart kütüphanesi, ek sunucu yok, tek dosya `<lab_root>/jobs.sqlite3`). Mevcut mimari
(tek süreçli FastAPI + ayrı çalışan süreçleri + disk önbelleği) için Redis/Celery gereksiz bağımlılık olurdu.

- **Durumlar:** `queued`, `running`, `completed`, `failed`, `cancelled`, `interrupted`, `resource_limited`
  (`CHECK` kısıtıyla). Faz 5 adları `pending`→`queued`, `rejected_resource`→`resource_limited` olarak değişti; ön yüz ve
  testler buna göre güncellendi.
- **Kayıt alanları:** iş kimliği, deney kimliği, algoritma, parametreler, filtreler, örneklem, tam istek, öznitelik
  seti, veri sürümü, kod sürümü, gönderim/başlama/bitiş zamanı, durum, hata metni ve türü (`resource_memory`,
  `resource_budget`, `timeout`, `worker_crash`, `worker_error`, `interrupted_restart`, `interrupted_shutdown`,
  `user_cancel`), çıktı yolu + SHA-256, önbellek anahtarı, kaynak (dinamik / önbellek / Faz 3 kaydı), çalışan PID ve
  oluşturulma zamanı, `retry_of`, kurtarıldı bayrağı.
- **Atomiklik:** her güncelleme tek `UPDATE`; durum geçişleri `WHERE state IN (...)` ile karşılaştır-ve-değiştir. Ör.
  iptal edilmiş bir iş, izleme döngüsünün geç gelen "tamamlandı" yazımıyla başarılı işaretlenemez (pytest).
- **Sonuç bütünlüğü:** önce `labels.npz` + SHA-256'lı `result.json` atomik yazılır, sonra durum `completed` olur;
  okumada SHA-256 ve olay indeksi aralığı doğrulanır; bozuk/eksik çıktı kullanılmaz.
- **Yarış koşulları:** aynı istek kuyruktayken/çalışırken ikinci kopya açılmaz (aynı iş döner; aynı dizine eşzamanlı
  yazma yok); çalışma başlamadan önce önbellek yeniden denetlenir; iptal, başlatma kilidi altında denetlenir.
- **Deney kimliği:** kayıtlı sonuçta Faz 3 kimliği (ör. `dbscan-52abd2c018`), dinamikte `dyn-<önbellek anahtarı>`;
  `/api/results/dyn-…` en son tamamlanan işe çözülür. Arayüz iş ve deney kimliğini birlikte gösterir.

## 3. Yeniden başlatma senaryosu

Açılışta `queued`/`running` kalan her iş için (otomatik yeniden çalıştırma **yok**):

1. Kayıttaki çalışan PID hâlâ yaşıyorsa ve oluşturulma zamanı + komut satırı (`multiprocessing`) eşleşiyorsa süreç ağacı
   sonlandırılır ve doğrulanır (PID yeniden kullanımında başka sürece dokunulmaz — pytest'te pytest sürecinin kendi
   PID'iyle doğrulandı).
2. İş dizininde eksiksiz, SHA-256'sı tutan, aynı veri/kod sürümlü `completed` sonuç varsa iş `completed` + "kurtarıldı"
   olur (sonuç diske yazılmış ama durum güncellenmeden çöken iş).
3. Aksi hâlde `interrupted`: "Yarım kalan hesaplama diske yazılmadığı için kurtarılamaz; sonuç uydurulmadı."
4. Kullanıcı "Yeniden dene" ile isteği **güncel kurallarla yeniden doğrulanmış** yeni bir iş olarak başlatır
   (`retry_of` bağlantısı). Tamamlanan iş yeniden denenemez (409).

Temiz kapanışta (`lifespan`) çalışan iş sonlandırılır ve `interrupted` (shutdown) işaretlenir; kuyruktakiler başlatılmaz.

**Gerçek süreçlerle uçtan uca doğrulama** (`e2e/phase6-restart.spec.ts`, yalıtılmış port 8011 ve iş kaydı):
sunucu A'da gerçek DBSCAN işi çalışırken (çalışan PID 21184) sunucu `taskkill /F` ile çökertildi → çalışan süreç
**0 ms** içinde yoktu (iş nesnesi KILL_ON_JOB_CLOSE); sunucu B açılışında iş `interrupted`, yetim temizliğine gerek
kalmadı (`orphans_killed: []`), 2 sn boyunca çalışan iş yok; arayüzden "Yeniden dene" → yeni iş `c53f712225cc`
tamamlandı (42.712 olay, 737 küme); ikinci çökme + açılıştan sonra iş yine `completed` ve sonuç uç noktası 200.

## 4. Kaynak yönetimi

| Önlem | Uygulama | Doğrulama |
|---|---|---|
| Fiziksel bellek ölçümü | `GlobalMemoryStatusEx` (`ullAvailPhys`); gönderimde ve süreç başlatmadan hemen önce | `/api/lab/resources`; arayüzde "Kaynak:" satırı / "Bellek yetersiz" notu |
| Ön denetim | boş bellek < 1.500 MB → iş çalıştırılmaz, `resource_limited` + Türkçe gerekçe | pytest (bellek ölçümü taklidi) + E2E |
| Ayrı süreç | `multiprocessing` spawn (Faz 5'ten) | — |
| Eşzamanlılık | 1 çalışan iş, ≤ 3 kuyrukta (429) | pytest |
| Sert bellek tavanı | Windows iş nesnesi `ProcessMemoryLimit` = min(4.096, boş − 768) MB (alt sınır 1.024) | pytest: 120 MB tavanla iş başarılı işaretlenmedi; tepe commit ≤ 121 MB |
| Yetim önleme | iş nesnesi KILL_ON_JOB_CLOSE + açılışta kimlik doğrulamalı temizlik | gerçek çökme E2E + pytest |
| İptal doğrulaması | psutil süreç ağacı `terminate` → bekle → `kill` → `wait_procs`; sonuç `termination.verified` | pytest: PID iptal sonrası yok |
| CPU / bellek ölçümü | 0,25 sn'de bir RSS, CPU %, CPU süresi; iş nesnesinden tepe commit | iş kaydında `worker.monitor`; arayüzde tek satır |
| Zaman aşımı | 900 sn → süreç sonlandırılır, `resource_limited` (`timeout`) | — |
| BLAS iş parçacığı | çalışanlarda `OPENBLAS/OMP/MKL_NUM_THREADS` = 4 | bkz. bulgu |

**Bulgu (gerçek kök neden):** yeni bellek tavanı devreye girince küçük test verisinde bile çalışan `MemoryError` verdi.
Ölçüm: OpenBLAS 16 mantıksal çekirdek için iş parçacığı başına arabellek ayırıyor — çalışanın commit'i **1.376 MB**
(RSS yalnızca 159 MB). 4 iş parçacığıyla **475 MB**. Bu, Faz 3'teki bellek baskısının da olası bir katkıcısıdır.
Claude Code'un bellek güvenlik önlemleri devre dışı bırakılmadı; kaynak kısıtını aşmak için sonuç uydurulmadı veya
deney kontrolsüz yeniden çalıştırılmadı.

## 5. Dinamik analiz güvenilirliği ve sonuç bütünlüğü

| # | Senaryo | Sonuç | Kanıt |
|---|---|---|---|
| 1–3 | Kayıtlı DBSCAN / K-Means / HDBSCAN yükleme (gerçek veri) | DBSCAN 4.179 küme, gürültü 0,59687; K-Means 5 küme, gürültü **N/A** (Faz 3 kaydındaki 0,0 "gürültü yok" anlamına gelmez); HDBSCAN 100.000 olay, 768 küme, gürültü 0,54708 — Faz 3 kaydıyla birebir | `test_real_saved_models_match_phase3_registry` |
| 4–6 | Yeni DBSCAN / K-Means / HDBSCAN | Gerçek ayrı süreçte tamamlanır (sentetik veri); gerçek veride DBSCAN taze fit 737 küme | pytest + restart E2E |
| 7 | Geçersiz parametre | eps −5, 1e9, "nan"; k=1; tanımsız parametre; HDBSCAN örneklem 10; geçersiz algoritma → 422 | pytest |
| 8 | Kaynak sınırını aşan iş | HDBSCAN bütçe, komşu çifti bütçesi, boş bellek, iş nesnesi tavanı → `resource_limited` | pytest |
| 9 | İptal | Çalışan süreç sonlandırılır ve doğrulanır; durum geri çevrilemez; sonuç uç noktası 409 | pytest |
| 10 | Sunucu yeniden başlatma | Bkz. §3 | pytest + gerçek çökme E2E |

Her sonuçta deney kimliği, veri kapsamı (olay sayısı, filtreler, örneklem), öznitelik seti, parametreler, küme
üyelikleri, gürültü ve metrikler aynı kayıttan gelir. HDBSCAN'in 100k örneklemi tüm NYC verisine uygulanmış gibi
gösterilmez: sonuç modunda yoğunluk katmanı artık sonucun **kendi** olaylarından üretilir (100.000; Faz 5'te tüm
kayıtların yoğunluğu görünüyordu) ve kapsam her yerde yazılır. Dinamik sonuçta hesaplanmayan DBCV ve hesaplanamayan
siluet/Davies–Bouldin **N/A** gösterilir (sıfır veya "—" değil, gerekçeli).

**Yeniden üretilebilirlik:** Manhattan 2018 DBSCAN (35 m / 15) isteği yalıtılmış iş kaydında sıfırdan yeniden fit
edildi; Faz 5'teki önbellekle aynı deney kimliği (`dyn-ffa2ddf23cc1eeda`) ve aynı küme sayısı (737).

### Filtreleme (Mod A) ve yeniden kümeleme (Mod B) ayrımı

- Mod A: `/api/records/*`; küme kimlikleri yalnızca seçili modelden; bant "yeniden kümeleme yapılmadı" (E2E: Brooklyn
  filtresinde 1.197 küme, 222.744 kümelenmiş olay, haritadaki merkezler API ile aynı ve hepsi model kimliklerinde).
- Mod B: `/api/lab/jobs` → ayrı deney kimliği; harita/tablo/istatistik `/api/results/<kimlik>` ile bağlanır.
- **Birleşme engeli:** sonuç uç noktaları kayıt filtresi (ilçe, araç…) aldığında 422 döner; yalnızca zaman süzgeci
  kabul edilir. API düzeyinde aynı filtre için Mod A kayıt sayısı = Mod B iş kapsamı = sonuç özeti olay sayısı
  (pytest + E2E); merkezlerdeki olay toplamları ilgili özetle eşleşir.

## 6. API güvenliği

| Kontrol | Uygulama |
|---|---|
| Girdi doğrulama | Parametre sınırları (Faz 5) + tarih yılı 1900–2100, nokta ofseti 0–10⁷, bbox metni ≤ 200 karakter, iş listesi ≤ 500 |
| Koordinatlar | sonlu sayı, batı<doğu, güney<kuzey, aralık; nokta kutusu ≤ 0,05° (413) |
| Kimlik doğrulama (deney/iş) | iş `^[0-9a-f]{12}$`; sonuç `lab-<12 hex>` / `dyn-<16 hex>` / `<algoritma>-<alfasayısal>`; uymayan → dosya sistemine dokunmadan 404 (`..%2F`, `..%5C`, Türkçe karakter denendi) |
| Dosya yolu güvenliği | Kullanıcı girdisinden yol kurulmaz; iş dizini sunucunun ürettiği önbellek anahtarı |
| Kaynak tüketimi | gövde ≤ 64 KB (413), kuyruk/eşzamanlılık sınırı, bellek ön denetimi ve tavanı, zaman aşımı |
| Host / DNS yeniden bağlama | `TrustedHostMiddleware` (yalnızca yerel adlar + `SAFEROUTE_ALLOWED_HOSTS`) — `Host: evil.example` → 400 |
| CORS | eklenmedi (aynı köken); `Origin` başlığına izin başlığı dönmez |
| Hata sızıntısı | beklenmeyen hata → genel 500 mesajı, yığın izi yalnızca sunucu günlüğü; iş hatalarında mutlak yollar maskelenir |
| Güvenlik başlıkları | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `COOP: same-origin` |
| Yarış koşulları | §2 |

Kimlik doğrulama eklenmedi (yerel kullanım). Uygulama internete doğrudan açılmaya **hazır değildir**; sınırlar
`KALAN_RISKLER.md` §1'de belgelendi.

## 7. Harita performansı

Ayrıntı ve tüm tablolar: `PERFORMANS_RAPORU.md`. Özet (gerçek GPU, doğrulanmış çizici):

| | AMD Radeon tümleşik | NVIDIA RTX 4050 | SwiftShader (yazılım, GPU değil) |
|---|---:|---:|---:|
| Veri katmanları hazır | 102,7 sn* (tekrarında 2,1 sn) | 2,1–2,2 sn | 7,0 sn |
| 3D döndürme FPS | 76,5 | 96,3–104,4 | 2,6 |
| Yakınlaştırma / uzaklaştırma FPS | 99,8 / 113,8 (3–5 takılma) | 140,9–143,0 / 141,2–142,6 (takılma yok) | 9,2 / 4,7 |
| WebGL bağlam kaybı → toparlanma | 1,1 sn | 1,25–1,27 sn | 3,6 sn |

\* tek seferlik soğuk başlangıç aykırı değeri; kök neden doğrulanmadı.

Coğrafi format: PMTiles/vektör karo karşılaştırması gerçek ölçüme (bbox API'si ve statik dosya) ve gerçek karo
sayımına dayanır; vektör karo bayt boyutu tahmindir, prototip kurulmadı. Mimari değiştirilmedi (gerekçe:
PERFORMANS_RAPORU §5).

**Bulunan ve düzeltilen sorun:** keşif ekranı diğer ekranlarda `visibility:hidden` ile düzende kaldığından pencere
boyutu değiştiğinde MapLibre'nin `trackResize`'ı gizli haritayı yeni boyutta yeniden çiziyor ve karo indiriyordu
(E2E'de 1440×6000 ekran görüntüsünde SwiftShader 400+ sn CPU). Harita artık yalnızca etkinken yeniden boyutlanır.

## 8. GLB optimizasyonu

Faz 4 GLB'leri ve LOD'ları değişmeden korundu (12 dosya, 241.991 B). Ölçülen: tekil GLB isteği 9–18 ms; küme seçimi
→ sahne hazır 3,8–5,5 sn (GPU), 6,6 sn (yazılım); GLB sahnesiyle döndürme 140–144 FPS (GPU). Modeller tembel yüklenir,
ekranlar arasında yeniden indirilmez, bağlam kaybında önbellekten yeniden kurulur (E2E: 7 model `loaded`,
`city-models` katmanı ve 19 merkez geri geldi). 4.179 küme 3D nesne olarak değil MapLibre daire katmanı olarak çizilir;
3D sahne yalnızca seçili küme çevresindedir. Yeni bir GLB işlemi gerekmedi.

## 9. Zaman oynatma

Faz 5'te kayıtlı/dinamik sonuçlarda kapalıydı; artık açık:

- `/api/results/{id}/timeline` kovaları **yalnızca o sonucun olaylarından** sayılır; yıl/ay ölçeğinde kapsam dışı boş
  baş/son kovaları çıkarılır (oynatma deneyin kapsamını aşamaz).
- Her adımda merkezler, noktalar ve yoğunluk `years/months/dows/hour_from/hour_to` ile süzülür; **merkez koordinatları
  ve üyelik değişmez**, yalnızca dilimdeki olay sayıları değişir; olayı olmayan kümeler gizlenir.
- Arayüz gösterir: seçilen dilim, deney kapsamı (ör. HDBSCAN: 2012-07-01 → 2026-06-10, 100.000 olay), o an görünür olay
  sayısı, "Kümeleme yeniden çalıştırıldı mı? **Hayır**".
- Eşleşme yoksa (sonuç alınamazsa) özellik gerekçeli hata ile devre dışı kalır. Dinamik sonuçlarda da aynı olay indeksi
  eşleşmesiyle desteklenir.
- 00:00 kovası uyarı renginde; bilgi notu korunur.
- Doğrulama: pytest (4 ölçek × her kova: dilim olayları = kova sayısı, merkez sabit, yoğunluk toplamı = kova; toplam =
  60) ve E2E (HDBSCAN 2012/2013/2014: 4.317 / 8.608 / 8.520 görünür olay; 643 / 739 / 732 küme; tüm merkezler tam
  sonuçla aynı).

## 10. Tasarım ve responsive kontrolleri

Faz 5 tasarım sistemi korundu; yeni tasarım yapılmadı. Gerçek tarayıcı ekran görüntüleri incelendi
(`reports/phase6/screenshots/`, 23 dosya). Görsel denetimde bulunup düzeltilenler:

1. Katman açıklamaları tek satırda kesiliyordu (yeni akademik uyarı "…gerçek yoğunl…" görünüyordu) → 2 satır.
2. Sonuç modunda katman açıklamaları "Tüm olaylar" ve "Seçilen DBSCAN kümeleri" diyordu (HDBSCAN gösterilirken yanlış)
   → kapsamdan bağımsız doğru metin.
3. Önbellekten gelen işte "Toplam 0,0 sn" yanıltıcıydı → "İlk hesaplamanın ölçümü (önbellekten)".
4. README'de Faz 4 Windows betik yolu `\r` kaçışı nedeniyle bozuktu (`scripts⏎un_phase4.ps1`) → düzeltildi.

Otomatik: 390×844@3x, 820×1180@2x, 1280×800, 1920×1080, 2560×1440@2x — beş ekranın tamamında belge düzeyinde yatay
taşma 0; ≥1280 genişlikte sol panel / zaman çubuğu çakışmıyor ve harita alanı genişliğin ≥ %40'ı. Fontlar (Plus
Jakarta Sans, Manrope), Türkçe sayı biçimi (2.020.638; %59,7; 0,945) ekran görüntülerinde doğrulandı. Yükleniyor/hata/
boş durumları: bağlantı kaybı (iş ve harita verisi) E2E ile tetiklendi. axe-core (WCAG 2.0/2.1/2.2 A–AA): genel bakış,
keşif, sonuç modunda oynatma, laboratuvar, modeller, veri — **0 ihlal**. Klavye: atlama bağlantısı → ana içerik,
menüden Enter ile ekran değişimi, zaman kaydırıcısında ok tuşu (`aria-valuetext`).

### Akademik doğruluk denetimi

Arayüz metinleri tarandı ve Faz 3 raporuyla çapraz kontrol edildi (seçili üç modelin küme, gürültü, siluet,
Davies–Bouldin, DBCV ve kabul değerleri API ile birebir aynı). Değişiklikler: gürültü oranı açıklamalarına "başarısız
kaza tespiti değildir"; DBCV açıklamalarına anlam (küme içi yoğun / kümeler arası seyrek) + "doğruluk veya trafik riski
değildir"; lejantta "Küme zarfı (dışbükey)" + "gerçek yoğunluk sınırı değildir" + "kaza yoğunluğu risk değildir";
yoğunluk lejantı "kayıtlı kaza yoğunluğu (gösterilen kapsam)". Korunanlar: siluet ≠ doğruluk, K-Means gürültüsü
"Uygulanamaz", HDBSCAN örneklem rozeti, farklı deneylerin küme numaralarının eşleştirilmemesi (409), veri güncellik
uyarısı (kaynak 127 gündür güncellenmedi).

## 11. Gerçek test sonuçları

| Paket | Sonuç |
|---|---|
| Backend pytest (Faz 1–5 + Faz 6) | **210 geçti** (194 önceki + 16 yeni `test_phase6.py`: kalıcı kayıt CAS, tamamlanan işin yeniden başlatmada korunması, eskimiş işlerin uzlaştırılması + gerçek yetim süreç + PID yeniden kullanımı, açık yeniden deneme, çalışan iptali ve süreç doğrulaması, kapanışta interrupted, kaynak sınırları, iş nesnesi bellek tavanı, yinelenen istek, dinamik/kayıtlı kimlik ve mod ayrımı, 4 ölçekte zaman oynatma, GeoJSON geçerliliği + deterministik sayfalama, API girdi/güvenlik sınırları, gerçek veride kayıtlı modellerin Faz 3 ile eşleşmesi) |
| Ön yüz Vitest | **75 geçti** (69 önceki + 6 yeni: yarıda kalan iş + açık yeniden deneme, kaynak sınırı mesajı, N/A metrikleri, bağlantı kaybında otomatik yeniden deneme, sonuç modunda yalnızca zaman süzgeci, deney kapsamı gösterimi) |
| Playwright Faz 6 (`phase6.spec.ts`) | **12 geçti**: 14 adımlı demo, kayıtlı HDBSCAN'de zaman oynatma, Mod A/B ayrımı, WebGL bağlam kaybı + GLB, bağlantı kaybı, klavye, 5 çözünürlük, axe |
| Playwright yeniden başlatma (`phase6-restart.spec.ts`) | **1 geçti** (gerçek çökme, yetim yok, interrupted, yeniden deneme, ikinci yeniden başlatma) |
| Playwright performans (`playwright.perf.config.ts`) | **3 proje geçti** (+ AMD/NVIDIA seçimi nedeniyle varsayılan proje bir kez daha) |
| Playwright Faz 4 + Faz 5 regresyonu | **22 geçti** (Faz 5: 11, Faz 4: 11; son kod değişikliklerinden sonra yeniden çalıştırıldı) (çıktılar `test-results/` altına yönlendirildi; `reports/phase4`, `reports/phase5` değişmedi) |
| Tip denetimi / derleme | `tsc -b` hatasız, `vite build` başarılı |
| Başlatma/durdurma betikleri | Gerçek çalıştırma: tüm denetimler, demo ısıtması 6,1 sn, arka plan PID kaydı; durdurma betiği süreci doğrulayıp durdurdu |

Faz 5 testlerinde yapılan uyarlamalar (Faz 6'nın bilinçli davranış değişiklikleri): yeni durum adları; sonuç modunda
zaman oynatmanın artık kapalı değil açık olması; dinamik iş testinin boş bellek < 1.500 MB ise "Kaynak sınırı" yolunu
doğrulaması; `SAFEROUTE_PHASE5_OUT` çıktı yönlendirmesi (varsayılan Faz 5 yolu korunur).

**Demo testinde dinamik iş hakkında not:** demo E2E'sinde Manhattan 2018 işi Faz 5'te aynı istek hesaplandığı için
**önbellekten** geldi (doğru davranış; arayüz "Önbellekten" rozetini gösterir). Aynı isteğin taze fiti yeniden
başlatma E2E'sinde yalıtılmış kayıtta gerçekten çalıştırıldı (§3).

## 12. Graphify durumu

Graphify v0.9.90 kurulumu korunarak `graphify update .` çalıştırıldı (AST; yeniden kurulum yok): **2.413 düğüm, 6.546 kenar, 112 topluluk** (Faz 5: 2.172 / 6.001 / 95). Sağlık: `diagnose multigraph` — eksik uç 0, sarkan uç 0, doğrulanmamış kod düğümü 0; 12 üretici bastırma noktası Faz 5'teki gibi Graphify'ın kendi çıkarıcı kodundaki tekilleştirme korumalarıdır (proje kodu değil). `graphify query` yeni modülleri (`JobStore`, `WorkerGuard`, `JobManager.retry`, `procguard.py`) buluyor. Sembol üretmeyen 6 yapılandırma dosyası beklenen uyarıdır. Topluluk adları LLM ile yeniden etiketlenmedi (API anahtarı gerektirir); 67 topluluk merkez düğümüne göre adlandırıldı.

## 13. Git commit kimliği

Bu raporu içeren commit: `feat: harden SafeRoute 3D phase 6 reliability` (kimlik kapanış mesajında). Büyük veri,
laboratuvar önbelleği/iş kaydı (`data/`), `frontend/dist`, `test-results`, `.saferoute/` Git dışındadır.

## 14. Açık sınırlılıklar

1. İnternete açık dağıtım için hazır değil (kimlik doğrulama, TLS, hız sınırlama, CSP yok).
2. Bu makinede bellek sıkışık; dinamik analiz boş bellek < 1.500 MB iken çalıştırılmaz.
3. Windows dışında iş nesnesi yok (yazılımsal bekçi + açılış temizliği).
4. PMTiles prototipi yok; vektör karo boyutu tahmindir. Çevrimdışı karo önbelleği yok.
5. AMD tümleşik GPU'daki 102 sn'lik tek seferlik soğuk başlangıcın kök nedeni doğrulanmadı.
6. Dinamik işlerde DBCV yok; dinamik metrikler Faz 3 ortak kümesiyle karşılaştırılamaz.
7. Dinamik K-Means sonuçları BLAS iş parçacığı sınırı nedeniyle Faz 5'teki aynı istekle bit düzeyinde aynı olmayabilir.
8. `start_saferoute.ps1 -Background` çıktısı bir boruya bağlanırsa çağrı dönmez (konsoldan sorun yok).
9. Ekran okuyucuyla elle test, uzun süreli bellek sızıntısı testi ve gerçek GPU sürücü sıfırlaması yapılmadı.

Tam liste: `KALAN_RISKLER.md`.

## 15. Faz 7 için öneriler

1. Ağa açılacaksa: kimlik doğrulama, TLS'li ters vekil, hız sınırlama, CSP, `pip-audit`/`npm audit`.
2. Lisans koşulları incelenerek yalnızca demo bölgesi için yerel karo arşivi (PMTiles altlık) ve çevrimdışı demo modu.
3. Isıtılmış kalıcı çalışan havuzu (süreç başlatma + içe aktarma ~2–4 sn) — iptal yalıtımı korunarak.
4. Laboratuvar önbelleği için boyut/yaş temizleme politikası ve iş kaydı arşivleme.
5. Dinamik sonuçlar için örneklemli DBCV ve kayıtlı/dinamik sonuç karşılaştırması (ARI/Jaccard).
6. Düşük donanım profili (GPU'suz makinede 3D binaları/sahneyi otomatik kapatma) — SwiftShader'da 2–9 FPS ölçüldü.
7. Karo ön ısıtması (demo profiline harita karoları için isteğe bağlı ısıtma).
