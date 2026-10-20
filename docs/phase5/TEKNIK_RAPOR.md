# SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı

> Tarih: 2026-10-20 · Temel commit (Faz 4): `bc0119712b1f0153321092c151813fe30b663266` · Analitik sürümü `5.0.0` ·
> Laboratuvar kod sürümü `phase5-lab:5.0.0` · Veri sürümü `raw:2fe1297c24f7|p2cfg:c7ffbfdc478d|p2:2.1.1`
> Ölçüm dosyaları: [`reports/phase5/api_benchmark.json`](../../reports/phase5/api_benchmark.json),
> [`reports/phase5/e2e_measurements.json`](../../reports/phase5/e2e_measurements.json) ·
> Ekran görüntüleri: [`reports/phase5/screenshots/`](../../reports/phase5/screenshots/)

Bu rapordaki tüm sayılar ölçüm dosyalarından, test çıktılarından veya API yanıtlarından alınmıştır.

## 0. Başlangıç incelemesi

- **Çalışma dizini:** Faz 4 commit'inde temizdi (`git status` boş).
- **Arka plandaki işlemler:** SafeRoute ile ilgili çalışan süreç yoktu. Görülen süreçler başka araçlara aitti
  (OpenAI Codex çalışma zamanı `node_repl.exe`/`server.mjs` ve başka bir projenin `expo start --web --port 8081`
  sunucusu). Bunlara dokunulmadı. Bu fazda başlatılan tek süreç `saferoute serve --port 8000`'dir.
- **Graphify'ın 12 bastırma noktası:** `graphify diagnose multigraph` çıktısındaki satır numaraları (L1785, L2349, L2351,
  L3018, L3165, L4175, L4361, L7452 …) proje kodunda değil, Graphify'ın kendi çıkarıcı dosyasındadır
  (`graphifyy/…/graphify/extract.py`, 10.858 satır). İncelendi: hepsi aynı düğüm/kenarın iki kez eklenmesini önleyen
  idempotent tekilleştirme korumalarıdır (`seen_ids`, `seen_doc_refs`, `seen_keys` kümeleri; ör. L7452 `add_node`
  içinde `if nid not in seen_ids`). Derleme sonrası grafikte eksik uç 0, sarkan uç 0, birebir yinelenen kenar 0,
  aynı uçlara çökertilmiş kenar 0'dır. **Sonuç: gerçek kod hatası değildir**; araç notunun söylediği gibi ham üretici
  kaybı yalnızca derleme öncesinde ölçülebilir ve proje kodunu etkilemez. Faz 5 sonunda da sayı 12'dir.
- Okunan kaynaklar: `PROJECT_SPEC.md`, `CLAUDE.md`, Faz 3 ve Faz 4 teknik raporları, Faz 4 ekran görüntüleri, ön yüz
  bileşenleri, harita/GLB altyapısı, FastAPI uç noktaları, `model_metadata.json`, `algorithm_comparison.json`,
  `experiments.json` (115 deney), `results.json`, Faz 2 `preprocessing_summary.json` ve `FeatureSpec` kayıtları,
  Graphify grafiği (`graphify query`).

## 1. Ön yüz mimarisi

```text
App (kabuk: atlama bağlantısı, Navigation, mobil çekmece, ekran yönlendirme)
├── ExplorerPage  ── ilk açılışta kurulur, ekranlar arasında KORUNUR (harita/WebGL/GLB yeniden oluşturulmaz)
│   ├── CityMap (Faz 4 motoru; imperative handle: kamera, ilçe, seçim, inceleyici)
│   ├── ViewPanel | FilterPanel (sekmeler) · Legend
│   ├── ClusterDetails | AssetInspector (sağ panel)
│   └── TimeControls · CameraControls (alt sıra) · ModeBanner (mod bandı)
├── OverviewPage · LabPage (AlgorithmControls, ExperimentResults, SavedExperiments) · ModelsPage (ComparisonCharts)
└── DataPage (DataDictionary)   ← tembel yüklenen parçalar
```

- **Durum yönetimi (Zustand, `src/app/store.ts`):** ekran, gezinme daraltma, filtre taslağı/uygulanan filtre (ayrı),
  harita veri kaynağı (`model` | `result`), katman görünürlüğü, tema, hareket düzeyi, ilçe, odak isteği, zaman dilimi,
  oynatma, aktif iş, sol panel sekmesi, mobil çekmece. Harita motorunun iç durumu (kamera, kaynaklar) `CityMap`'te kalır.
- **Yönlendirme:** hash tabanlı (`#/genel-bakis`, `#/kesif`, `#/laboratuvar`, `#/modeller`, `#/veri`); ek bağımlılık yok.
  Ekran değişiminde odak ana içeriğe taşınır.
- **Veri katmanı:** `lib/query.ts` — URL anahtarlı önbellek (TTL), eşzamanlı aynı isteğin tek ağ isteğine indirgenmesi,
  `AbortController` ile iptal, isteğe bağlı gecikme (debounce). `lib/api.ts` Faz 4 istemcisini korur ve genel
  `getJSON/postJSON/deleteJSON` ekler.
- **Arka uç (yeni paket `saferoute/analytics`):** `filters` (doğrulama, kanonik anahtar, maske), `events`
  (`EventStore`: 2.020.638 olayın filtre sütunları bellekte), `catalog` (genel bakış, deney kaydı, karşılaştırma, veri
  sözlüğü), `lab_spec` (algoritma × öznitelik uyumluluğu, sınırlar, bütçe), `jobs` (iş yöneticisi), `lab_worker`
  (ayrı süreç), `results` (etiket → küme tablosu/harita/profil), `reporting` (rapor belgesi), `api` (rotalar),
  `benchmark`. Faz 4 `create_app` yalnızca bir `register(...)` çağrısıyla genişletildi; Faz 4 uç noktaları değişmedi.

## 2. Oluşturulan ekranlar

| Ekran | İçerik |
|---|---|
| Genel bakış | Odak öğe: coğrafi analize uygun kayıt (2.020.638 / 2.269.187, %89,0) ve dışlanma nedenleri; seçilen model, küme sayısı, gürültü oranı, tarih kapsamı, yaralanmalı/ölümlü kaza; veri güncellik uyarısı; yıllara göre kaza (kısmi yıllar işaretli, tablo görünümü); beş ilçe karşılaştırması; en büyük 10 küme ("haritada aç"); dışa aktarma |
| 3D Şehir Keşfi | Faz 4 haritası + filtre paneli, mod bandı, zaman oynatma, küme ayrıntısı, kayıtlı/dinamik sonuç gösterimi |
| Kümeleme Laboratuvarı | Algoritma/öznitelik/parametre/kapsam denetimleri, kaynak bütçesi, gerçek arka uç işi, sonuçlar, kayıtlı 115 deney, iş geçmişi |
| Model Karşılaştırma | Seçilen üç konfigürasyon (metrik × algoritma), sınırlılıklar, DBSCAN ve HDBSCAN ızgaraları, K-Means k taraması, veri kalitesi duyarlılığı |
| Veri Gezgini | Veri hattı (koordinat temizleme, ilçe çıkarımı, araç normalizasyonu, tarih/saat, 00:00 bayrağı), 29 ham ve 87 işlenmiş sütun sözlüğü, öznitelik setleri |

## 3. Tasarım sistemi

"Premium Urban Intelligence": shadcn/ui (Radix ilkelleri, `components.json`, `src/components/ui/*` — 22 bileşen)
Tailwind 4 belirteçlerine bağlandı. Kullanıcının Erdem tasarım sisteminin web/yerleşim ilkelerinden uygulananlar
(proje spesifikasyonu renk/font konusunda önceliklidir): her ekranda tek odak öğesi (eşit kutucuklu "SaaS ızgarası"
yok), düşük köşe yarıçapı (4–10 px), gölge yerine yüzey kontrastı + ince çizgi, görünümde tek bulanık katman (yalnızca
harita üstü paneller), atlama bağlantısı, `svh` birimleri, mobilde küçültme değil yeniden kompozisyon, belge düzeyinde
yatay taşma kırpma. Ortak bileşenler: `MetricCard` (eksik değer → "—"), `InfoTip`, `Note`, `ScopeBadge`,
`LoadingBlock`/`ErrorBlock`/`EmptyBlock`, `Section`, `PageHeader`, `NotApplicable`, `ExportMenu`.

shadcn CLI'nin iki yan etkisi düzeltildi: istenmeyen `cn@^0.5.0` npm paketini bağımlılıklara eklemişti (kaldırıldı;
`cn` yerel `src/lib/utils.ts`'tedir) ve TypeScript 7'de kaldırılan `baseUrl` nedeniyle içe aktarma yolunu `"cn"` olarak
yazmıştı (düzeltildi). Ekran okuyucu metinleri Türkçeleştirildi ("Close" → "Kapat").

## 4. Fontlar ve renkler

| Belirteç | Değer | #0B1120 üzerinde kontrast |
|---|---|---|
| Background / Surface / Surface-2 | #0B1120 / #111C30 / #16233B | — |
| Primary | #38BDF8 (düğme metni #04131F, 8,8:1) | 8,8:1 |
| Warning / Hotspot | #F59E0B / #F87171 | 8,8:1 / 6,8:1 |
| Text / muted-foreground / subtle | #E2E8F0 / #94A3B8 / #8494AA | 15,3 / 7,3 / 6,1 |
| Giriş kenarlığı (input) | #516892 | yüzeyde ≥ 3:1 (WCAG bileşen kontrastı) |

İlk taslaktaki `subtle` #64748B (3,96:1) AA altında kaldığı için #8494AA'ya yükseltildi. Fontlar yerel
`@fontsource` paketlerinden (Plus Jakarta Sans 600/700/800, Manrope 400–700). E2E doğrulaması:
`document.fonts.check` iki aile için `true`; `h1` hesaplanan ailesi "Plus Jakarta Sans", `body` "Manrope".
Sayılar `tabular-nums`, Türkçe biçim (binlik nokta, ondalık virgül).

## 5. Gerçek veri entegrasyonu

Yeni uç noktalar (tümü gerçek kayıtlar / doğrulanmış kayıt dosyaları):

| Uç nokta | Kaynak |
|---|---|
| `GET /api/overview` | Faz 1 edinim + kaynak durum kaydı, Faz 2 özeti, Faz 4 katman manifesti, olay deposu |
| `GET /api/filters/options` | Olay deposu (yıl, ilçe, 12 araç kategorisi, 66 etken metni ve sayıları) |
| `GET /api/records/{summary,timeline,density,points,clusters,clusters/{id}}` | Olay deposu + Faz 4 konum etiketleri |
| `GET /api/models/comparison`, `/api/experiments[/{id}]` | Faz 3 `algorithm_comparison.json`, `results.json`, `experiments.json` |
| `GET /api/results/{kimlik}/{summary,clusters,table,points,clusters/{id}}` | Faz 3 etiket dosyaları (`labels/*.npz`) veya laboratuvar işi |
| `POST/GET/DELETE /api/lab/jobs`, `GET /api/lab/capabilities` | İş yöneticisi |
| `GET /api/data/dictionary` | Faz 2 `FeatureSpec` + Parquet satır grubu istatistikleri (`null_count`) |
| `GET /api/export/records`, `/api/export/results/{kimlik}` | Rapor belgesi (MD/CSV/JSON) |

**Olay deposu doğrulaması (gerçek veri):** filtresiz toplamlar Faz 4 manifestiyle birebir (2.020.638 olay; 814.578
kümede; 1.206.060 gürültü; #1344 = 1.444 olay; 1 km ızgara toplamı 2.020.638). Kayıtlı DBSCAN etiketlerinden üretilen
küme tablosu Faz 3 özetiyle 4.179 kümenin tamamında eşleşir: merkez farkı ≤ 1,3·10⁻¹³°, p90 yarıçap farkı ≤ 5,4·10⁻⁸ m,
zirve saat, benzersiz konum, yaralanma/ölüm ve "Unspecified" payı aynı (Faz 3 tanımları — UTM merkez, doğrusal
enterpolasyonlu p90, NA'sız payda — birebir uygulandı). Bellek: depo 0,55–0,66 sn'de yüklenir, API süreci 431–443 MB
(Faz 4: 221 MB). İlk taslak 926 MB tutuyordu; etken metinleri sözlük kodlamasıyla okunarak düşürüldü.

Kaynak güncelliği gizlenmez: kontrol anında (2026-10-19) kaynak satırları 125 gündür güncellenmemişti (beyan:
günlük, eşik 3 gün → "stale"); arayüz hem kontrol anındaki hem bugünkü gün sayısını gösterir. Kısmi yıllar (2012:
1 Temmuz'da başlar; 2026: 11 Haziran'da biter) grafikte soluk çubuk ve notla işaretlenir.

## 6. Filtreleme işlevleri

İlçe, başlangıç/bitiş tarihi (tek gün dahil), yıl, ay, haftanın günü, saat aralığı (gece yarısını aşan 22–04 dahil),
araç türü (12 kategori, en az biri), kayıtlı katkı faktörü (beş araç alanından herhangi biri), yaralanma durumu,
ölümle sonuçlanan kaza, 00:00 şüpheli kayıtları hariç tutma. Filtreler **sunucuda** gerçek kayıtlara uygulanır
(`FilterSpec` → NumPy maskesi; maske ve özet LRU önbellekli). Taslak/uygulanan ayrımı vardır; taslak değişirken
gecikmeli (350 ms) canlı kayıt sayısı gösterilir. Geçersiz giriş istemcide ve sunucuda (422) reddedilir.

**Filtre ile yeniden kümeleme ayrımı:**

1. **"Mevcut kümelerde göster"** — filtrelenmiş kayıtlar tam veri modelinin (dbscan-52abd2c018) etiketleriyle
   gösterilir. Haritada mod bandı: "Filtrelenmiş kayıtlar · Küme etiketleri tam veri modelinden · **yeniden kümeleme
   yapılmadı**". Küme merkezleri yalnızca filtreye uyan kaydı olan kümelerdir; boyutları filtrelenmiş sayıdır; küme
   paneli tam küme ve filtrelenmiş değerleri yan yana gösterir.
2. **"Bu filtreyle yeni kümeleme başlat…"** — Laboratuvar'a filtre kapsamıyla geçer; kümeleme orada açıkça
   başlatılır, ayrı süreçte çalışır ve haritada "Dinamik analiz sonucu" olarak ayrı etiketlenir. Yeni kümeleme
   yapılmadıysa arayüz bunu iddia etmez.

## 7. Clustering Lab

| Algoritma | Öznitelik seti (izinli) | Parametre sınırları |
|---|---|---|
| DBSCAN | Mekânsal Haversine (ağırlıklı benzersiz konum); Uzay-zaman (deneysel, ST-DBSCAN) | eps 5–500 m, min_samples 2–5000, eps_gün 1–365 |
| K-Means | Mekânsal UTM 18N metre (ağırlıklı) | k 2–200, n_init 1–20, max_iter 50–1000, random_state |
| HDBSCAN | UTM metre (kayıt düzeyi); Haversine (kayıt düzeyi) | min_cluster_size 2–5000, min_samples 1–1000 veya otomatik, eom/leaf |

Desteklenmeyen kombinasyonlar seçilemez ve gerekçesi gösterilir (ör. K-Means + uzay-zaman: "metre ve gün eksenlerini
tek Öklid uzayında karıştırır"); sunucu da aynı kurallarla 422 döner. Ekranda kullanılan öznitelikler, mesafe
metriği, fit düzeyi, veri kapsamı (kayıt sayısı, payda, filtreler), algoritma sürümü (scikit-learn 1.9.1,
`phase5-lab:5.0.0`) ve iş gönderilince atanan deney kimliği (iş kimliği + önbellek anahtarı) gösterilir.

**Uzay-zaman DBSCAN** Faz 2'de tanımlanıp Faz 3'te çalıştırılmamış stratejinin uygulamasıdır: komşuluk = (mesafe ≤
eps_m) VE (|Δgün| ≤ eps_gün); KD ağacı ile mekânsal komşular sayılır (bütçe), zaman eşiğiyle süzülür, seyrek komşuluk
grafiği üzerinde `DBSCAN(metric="precomputed")`. Arayüzde "deneysel" rozetlidir ve mekânsal kümelerle
karşılaştırılamayacağı yazılır; siluet/Davies–Bouldin "uygulanamaz" olarak raporlanır.

**İş yönetimi ve kaynak bütçesi:** iş kimliği; durumlar `pending → running → completed | failed | cancelled |
rejected_resource`; çalışırken gerçek aşama (girdi yükleme, kaynak ölçümü, fit, metrik, yazma) çalışan sürecin
durum dosyasından okunur — **ilerleme yüzdesi gösterilmez**. İptal süreci sonlandırır. Aynı anda bir iş, en fazla
3 bekleyen (fazlası 429). Bütçe: ≤ 120 M komşu çifti (fit öncesi sayılır), HDBSCAN ≤ 100.000 olay, uzay-zaman
≤ 300.000 olay ve ≤ 40 M mekânsal çift, ≥ 1.500 MB boş bellek, 900 sn zaman aşımı. Aşılırsa iş çalıştırılmaz ve
"Kaynak yetersiz" mesajı gerekçesiyle gösterilir (ör. tam veride eps = 400 m: "133.783.834 > 120.000.000"). Sonuçlar
istek + veri sürümü + kod sürümü anahtarıyla diskte önbelleklenir; aynı istek yeniden hesaplanmaz.

Windows'ta gerçek bir yarış durumu bulundu ve düzeltildi: API durum dosyasını okurken çalışanın atomik `os.replace`
çağrısı `WinError 5` alıyordu; yazma kısa aralıklı yeniden denemeli ve aşama bildirimi en-iyi-çaba yapıldı. Ayrıca
"tamamlandı" durumu önbellek dosyası yazılmadan önce görünüyordu (aynı isteğin hemen tekrarı önbelleği kaçırıyordu);
sıra düzeltildi.

## 8. Kayıtlı ve dinamik deney yönetimi

- **Kayıtlı deneyler:** 115 Faz 3 deneyi (114 etiket dosyası) algoritma/aşama süzgeciyle listelenir; seçilen deneyin
  sonucu doğrulanmış etiketlerden üretilir (olay indeksi sınırı ve kayıttaki olay sayısıyla denetimli), haritada
  gösterilebilir ve dışa aktarılabilir.
- **Kayıtlı konfigürasyon eşleşmesi:** filtresiz ve Faz 3 ızgarasındaki bir konfigürasyonla birebir aynı istek
  (DBSCAN eps/min_samples; K-Means k + n_init=10, max_iter=300, random_state=42; HDBSCAN 100k/tohum 42 örneklem)
  yeniden fit edilmez, kayıtlı sonuç "Kayıtlı Faz 3 sonucu · <deney kimliği>" olarak yüklenir. Arayüz bunu gönderimden
  önce bildirir. Filtreli aynı konfigürasyon kayıtlı sonuç DEĞİLDİR (yeni iş).
- **Dinamik sonuç metrikleri:** gürültü hariç 10.000 olaylık basit rastgele örneklemde siluet ve Davies–Bouldin
  (Öklid, metre; scikit-learn çalışma belleği 256 MB). Faz 3 ortak değerlendirme kümesiyle karşılaştırılamayacağı
  yazılır. DBCV maliyet nedeniyle dinamik işlerde hesaplanmaz ve "—" gösterilir.
- **Raporlama:** `saferoute.report/1` belge şeması (kaynak, veri tarihi/sürümü, algoritma, parametreler, öznitelikler,
  metrik, kapsam, kayıt sayısı, metrikler, sınırlılıklar, bölümler, tablo) → Markdown özet, CSV (Excel için BOM) ve
  JSON. Bölüm türleri (`facts`, `table`, `list`, `text`) Faz 6–7'de genişletilebilir; bilinmeyen tür ham JSON yazılır.

## 9. Model karşılaştırmaları

Tablo ölçüt × algoritma biçimindedir: parametreler, model kapsamı (rozet: Tam veri / Örneklem), kullanılan olay ve fit
noktası, küme sayısı ve kapsamı, gürültü oranı ve kapsamı, en büyük küme payı, siluet, Davies–Bouldin, DBCV, parametre
kararlılığı (ARI), fit süresi, bellek (tepe/fit artışı), kabul ölçütleri. Korunan gerçekler:

- HDBSCAN 100.000 olaylık örneklemde (768 küme, gürültü %54,7), DBSCAN tam veride (4.179 küme, %59,7) — her değerin
  yanında kapsamı yazılır; sınırlılık kutusu bunu açıkça söyler.
- Siluet 0,945 "0,945" olarak yazılır; bilgi simgesi "%94,5 doğruluk DEĞİLDİR" der (E2E ve bileşen testiyle sabit).
- K-Means gürültüsü "Uygulanamaz" (0 değil; sunucu da `null` döndürür).
- Tek bir başarı puanı üretilmez; ızgara hücre tonu yalnızca göreli değerdir ("iyi/kötü anlamı taşımaz").

## 10. Zaman oynatma

Yıl, ay (2012-07 … 2026-06), haftanın günü ve saat ölçekleri; kovalar `/api/records/timeline` ile gerçek kayıtlardan
(uygulanan filtrelerle) sayılır. Oynat/duraklat, önceki/sonraki adım, kovaya tıklama ve erişilebilir aralık girdisi
(`aria-valuetext`: "<dilim>, <kayıt sayısı> kayıt" biçiminde). Her adım filtrelerin üzerine bir zaman dilimi ekler ve
haritanın yoğunluk, küme merkezi ve nokta katmanları sunucudan yeniden filtrelenir (E2E: saat 01 adımında durum
çubuğu ve yoğunluk katmanı ilgili kova toplamıyla tutarlı). Küme etiketleri değişmez. Saat ölçeğinde 00:00 kovası
uyarı rengindedir ve bilgi metni yuvarlama şüphesini açıklar; Veri Gezgini her saatte :00 yığılması olduğunu
(9,5–15,7×) ve 00:00'da 28,3× olduğunu gösterir. Temsili araç animasyonlarının gerçek kaza verisi olmadığı yazılır.
Kayıtlı/dinamik sonuç gösterilirken oynatma gerekçesiyle kapalıdır (sonuç sabit bir kapsama aittir).

## 11. Küme detayları

Küme ID, deney/sonuç kimliği, kaza sayısı, benzersiz koordinat, ilgili ilçeler (sayılarıyla), tarih aralığı, etkin
yıl, yarıçap p90, yaralanmalı/ölümlü kaza ve yaralı/ölü kişi, saatlik dağılım (zirve; 00:00 zirvesinde uyarı), araç
türü dağılımı (kazaya karışan kategoriler; çoklu sayım açıklamalı), kaydedilmiş katkı faktörleri (kaza başına,
"Unspecified" ayrıca), model parametreleri, odakla düğmesi. Filtre etkinse tam küme ve filtrelenmiş kayıtlar ayrı
sütunlarda. Kaynakta olmayan alan "Mevcut değil"; ek profil alınamazsa Faz 4 ayrıntısı yine gösterilir.

Harita senkronu: tıklama (Faz 4 en yakın merkez kuralı), "haritada aç" (genel bakıştan), seçim vurgusu, kameranın
kümeye uçuşu, temsili sahne. Görsel denetimde bulunan bir Faz 4 kamera sorunu düzeltildi: küçük yarıçaplı kümelerde
(ör. #1359, 0,6 m → zoom 19,2, eğim 62°) kamera yüksek bir binanın arkasında kalıyordu; uçuştan sonra hedef ekran
noktasında 3D bina çiziliyorsa kamera bir kez 25°'ye dikleşir ve bu kullanıcıya not olarak söylenir.

## 12. Erişilebilirlik

axe-core (WCAG 2.0/2.1/2.2 A–AA) beş ekranda **0 ihlal** (geçen kural: genel bakış 31, keşif 31, laboratuvar 32,
modeller 28, veri 28). Taramada bulunup düzeltilenler: metin içi bağlantının yalnızca renkle ayrılması (1,19:1 →
alt çizgi), rolsüz `aria-label` (iskeletlere `role="status"`), daraltılmış gezinmede adı olmayan bağlantılar
(`aria-label`), geçersiz tanım listesi (`dl` içinde `dt/dd`'siz öğe). Diğer önlemler: atlama bağlantısı (ilk Tab),
ekran değişiminde odağın ana içeriğe taşınması, görünür odak halkaları, tüm form öğelerinde etiket, `aria-invalid` +
hata metni, `role="alert"` hata kutuları, `aria-live` durum ve önizleme metinleri, grafiklerde `role="img"` + özet
etiketi ve tablo görünümü, Radix bileşenlerinin klavye davranışı (Esc ile çekmece kapatma vb.),
`prefers-reduced-motion` → "azaltılmış" ve CSS geçişlerinin kısaltılması, kullanıcı hareket seçeneği (tam/azaltılmış/
kapalı), `lang="tr"`, Türkçe karakterler (İ/ı/ş/ğ) doğru çizilir (ekran görüntüleri).

## 13. Responsive tasarım

| Genişlik | Kompozisyon |
|---|---|
| ≥ 1280 | Genişletilmiş kenar çubuğu (keşfe girişte otomatik daralır), sol filtre/görünüm paneli 320 px, sağ küme paneli 340 px, alt zaman + kamera; diğer ekranlarda iki sütun |
| 768–1279 | Daraltılmış kenar çubuğu (ikon + ipucu), aynı keşif paneli düzeni, sayfalarda tek sütuna inen ızgaralar |
| < 768 | Kenar çubuğu yerine üst çubuk + gezinme çekmecesi; keşifte masaüstü panelleri yerine alttan açılan "Görünüm ve filtreler" ve "Küme ayrıntısı" sayfaları, kompakt zaman çubuğu, 4 düğmeli kamera; tablolar kendi içinde yatay kaydırılır |

E2E: 390×844 ve 820×1180'de dört içerik ekranında belge ve kap düzeyinde yatay taşma 0; 1920×1080'de sol panel, sağ
panel, zaman ve kamera denetimleri arasında çakışma yok. Görsel denetimde bulunup düzeltilen: ızgara öğelerinin
`min-width:auto` nedeniyle mobilde taşması (`Section`'a `min-w-0`), kamera düğmelerinin harita atfıyla çakışması.

## 14. Performans ölçümleri

**Ortam:** Windows 11, Python 3.12, Chromium headless (SwiftShader yazılım WebGL, GPU yok). Süreç içi ölçüm (ağ hariç).

| İstek | İlk (ms) | Medyan (ms) | p95 (ms) | gzip (B) |
|---|---:|---:|---:|---:|
| Genel bakış | 350,6 | 7,0 | 8,0 | 2.953 |
| Filtre seçenekleri | 97,2 | 3,5 | 3,6 | 1.567 |
| Özet, filtreli (Brooklyn+bisiklet+yaralanmalı) | 61,1 | 4,0 | 4,3 | 1.564 |
| Özet, gece saatleri + ölümlü | 21,8 | 3,7 | 3,8 | 1.538 |
| Zaman çizelgesi (ay, filtreli) | 17,5 | 21,8 | 29,0 | 965 |
| Yoğunluk 1 km / 250 m (filtreli) | 16,2 / 38,9 | 15,7 / 39,0 | 16,5 / 52,8 | 3.355 / 23.129 |
| Kümeler (filtreli, mevcut model) | 23,3 | 23,0 | 23,7 | 29.084 |
| Noktalar (filtreli, Brooklyn bbox) | 11,6 | 10,7 | 11,1 | 2.417 |
| Küme ayrıntısı (filtreli) | 23,0 | 23,4 | 27,7 | 1.359 |
| Model karşılaştırma / deney kaydı | 13,4 / 24,4 | 13,3 / 23,2 | 14,1 / 24,6 | 13.376 / 11.232 |
| Kayıtlı sonuç (K-Means, 2 M olay etiketi) | 1257,0 | 6,3 | 6,5 | 1.336 |
| Veri sözlüğü | 22,8 | 8,6 | 9,4 | 9.780 |

- Uygulama + olay deposu hazır: 0,97 sn; API süreci 431–443 MB, ölçüm sırasında tepe 857 MB.
- Dinamik DBSCAN (Manhattan 2018: 42.712 olay → 11.290 fit noktası, eps 35 m, ms 15): fit 0,255 sn, uçtan uca
  4,63 sn (yeni süreç başlatma ve scikit-learn içe aktarma baskın), çalışan tepe belleği 681,5 MB, 737 küme.
- Tarayıcı (E2E): genel bakış hazır 1,18 sn; filtre uygulama → katmanlar hazır 180 ms; bir filtre değişiminde
  4 `/api/records/*` isteği. Harita ekranlar arasında korunur (aynı nesne), GLB'ler yeniden indirilmez (E2E 8).
- İyileştirmeler: özet ve filtre seçenekleri önbelleği (tekrar ~470 → ~4 ms), etken sayımı satır içi sıralamayla
  vektörleştirildi (sonuç eski yöntemle birebir aynı, gerçek veride doğrulandı), olay deposu belleği 926 → ~440 MB.
- Ön yüz derlemesi (gzip): MapLibre 280 KB, Three.js 160 KB, Recharts parçası 110 KB, uygulama çekirdeği 116 KB,
  ekranlar tembel parçalar (genel bakış 4 KB, laboratuvar 11 KB, veri 6 KB, modeller 5 KB), CSS 37 KB.
- Ağır hesaplama UI iş parçacığında yapılmaz; binlerce React DOM işaretçisi yoktur (tüm noktalar MapLibre katmanı);
  bbox sınırı, sayfalama (`/table?limit&offset`), zoom'a göre katman seçimi Faz 4'ten korunur.

**Gerçek ekran kartında performans testi yapılamadı:** bu oturumdaki tüm tarayıcı ölçümleri GPU'suz SwiftShader
ile alındı; değerler alt sınır niteliğindedir.

## 15. Görsel test bulguları

Playwright ile gerçek uygulamada alınan 18 ekran görüntüsü `reports/phase5/screenshots/` altındadır (genel bakış,
3D keşif, filtre uygulanmış, küme seçili + panel, zaman oynatma, laboratuvar, dinamik analiz sonucu, dinamik sonuç
haritada, model karşılaştırma, veri hattı, öznitelik çekmecesi, mobil genel bakış/laboratuvar/3D/çekmece, tablet,
1920 geniş ekran). Görsel denetimde bulunup düzeltilenler:

1. Filtreli küme seçiminde kamera bir binanın arkasında kalıyordu (bina engeli denetimi eklendi).
2. Gizlenen keşif ekranının harita atfı diğer ekranlarda görünüyordu (MapLibre `visibility:visible`; alt ağaç zorla gizlendi).
3. Karşılaştırma tablosu 1440 px'te taşıyordu (ölçüt × algoritma biçimine çevrildi).
4. K-Means grafiğinde kenardaki seçili nokta kırpılıyordu (eksen dolgusu).
5. İlçe tablosu ve yıl grafiği mobilde ekrandan taşıyordu (`min-w-0`).
6. Dakika yığılma grafiği 24 satırlık uzun listeydi (sütun grafiğine çevrildi) ve not, her saatteki yığılmayı söylemiyordu (eklendi).
7. Lejant başlığı iki kez yazılıyordu; kaynak satırında çift parantez; çevrilmemiş varyant adı (`cap_repeated_weights`).
8. Sonuç haritada açılınca sol panel Filtreler sekmesinde kalıyor, sonuç kartı görünmüyordu; kamera eski yakın konumda kalıyordu (şehir görünümüne alınıyor).
9. Laboratuvarda iş yokken sağ alan boştu (varsayılan "Kayıtlı deneyler"); desteklenmeyen seçenek gerekçeleri sütunu uzatıyordu (2 satırla sınırlandı).
10. Gezinme etiketi "Kümeleme Laboratuvarı" kesiliyordu (kenar çubuğu 248 px).

## 16. Test sayıları

| Paket | Sonuç |
|---|---|
| Backend pytest (Faz 1–4 + Faz 5) | **194 geçti** (163 önceki + 31 yeni: filtre doğrulama ve el sayımlı maske, mevcut-küme/yeniden kümeleme ayrımı, yoğunluk/nokta/zaman toplamları, etkenlerin kaza başına sayımı, 14 laboratuvar istek doğrulaması, sonuç özeti ve K-Means gürültüsü, rapor biçimleri, kayıtlı deney yükleme ve kayıtlı konfigürasyon eşleşmesi, gerçek ayrı süreçte DBSCAN/K-Means/HDBSCAN işleri, önbellek, kaynak reddi, boş kapsam, iptal, analitiğin veri yokken devre dışı kalması, gerçek veri tutarlılığı) |
| Ön yüz Vitest | **69 geçti** (44 önceki + 15 mantık: filtre kanonikleştirme/doğrulama, zaman dilimi, DBSCAN/K-Means/HDBSCAN parametre denetimleri, uyumluluk, bütçe, kayıtlı eşleşme, yönlendirme, önbellek/iptal/hata + 10 jsdom bileşen: eksik değer, iş durumları, K-Means "Uygulanamaz", siluet yüzde değil, API hata ve yeniden deneme, ağ hatası, sonuç kümesi ayrıntısı, hata/boş durum, zaman kovaları, katman anahtarları) |
| Playwright Faz 5 (gerçek uygulama) | **11 geçti**: genel bakış sayıları + fontlar + axe; harita korunumu + filtre doğruluğu + mod ayrımı + filtreli küme ayrıntısı; zaman oynatma; laboratuvar (kayıtlı konfigürasyon, parametre sınırları, uyumsuz kombinasyon, bütçe, dinamik iş, haritada sonuç); kayıtlı deney seçimi + gerçek iptal + API 429/503 hataları; model karşılaştırma; veri gezgini; klavye/odak/azaltılmış hareket/harita kalıcılığı; mobil; tablet; 1920 düzeni |
| Playwright Faz 4 regresyonu (yeni arayüzde) | **11 geçti** (artefaktlar `test-results/phase4-regression`'a yönlendirildi; `reports/phase4` değişmedi) |
| Tip denetimi / derleme | `tsc -b` hatasız, `vite build` başarılı |

Faz 4 E2E dosyasına yapılan uyarlamalar: keşif adresi `/#/kesif`, tıklama koordinatına tuval ofseti, artefakt dizini
için isteğe bağlı `SAFEROUTE_PHASE4_OUT` (varsayılan Faz 4 yolu korunur). `__saferoute.selected()` test kancasının
`cluster_id` sözleşmesi korundu.

## 17. Bilinen sınırlılıklar

1. Gerçek GPU'da performans profili alınmadı (yalnızca SwiftShader).
2. Dinamik işlerde uçtan uca süre çoğunlukla Windows'ta yeni süreç başlatma ve kütüphane içe aktarmadır (~4 sn);
   kalıcı bir çalışan havuzu kurulmadı (iptal için süreç yalıtımı tercih edildi).
3. İş kuyruğu sunucu belleğindedir; sunucu yeniden başlarsa bekleyen işler kaybolur (tamamlanan sonuçlar disk
   önbelleğinde kalır ve aynı istekte yeniden kullanılır). Disk önbelleği için temizleme politikası yoktur.
4. Dinamik işlerde DBCV hesaplanmaz; siluet/Davies–Bouldin basit rastgele örneklemdedir ve Faz 3 ortak değerlendirme
   kümesiyle karşılaştırılamaz. Uzay-zaman setinde bu metrikler uygulanamaz.
5. Küme geometrileri (dışbükey zarf) yalnızca seçili Faz 3 modelinde vardır; kayıtlı/dinamik sonuçlar merkez ve
   nokta olarak gösterilir. Sonuç gösterilirken zaman oynatma kapalıdır.
6. Kayıt düzeyi algoritmalarda (HDBSCAN, uzay-zaman) bir konumda birden çok etiket olabilir; haritada baskın etiket
   gösterilir (`n_labels` alanı yanıtta vardır, arayüzde ayrıca gösterilmez).
7. Yoğunluk katmanı Faz 4 ızgara hücrelerine bağlıdır (1 km / 250 m); yeni hücre boyu eklenmedi.
8. Etken metinleri NYPD'nin İngilizce kodlarıdır; çevrilmedi (anlam kaybı riski).
9. Uygulamada kimlik doğrulama ve çok kullanıcılı iş yalıtımı yoktur (yerel/akademik kullanım).
10. Açık tema yoktur (karanlık tema önceliği); haritanın gece/gündüz modu Faz 4'teki gibi vardır.
11. Kaynak verisi kontrol anında 125 gündür güncellenmemişti; bu faz yeni veri indirmedi.

## 18. Graphify durumu

Graphify v0.9.90 yapılandırması korunarak `graphify update .` çalıştırıldı (AST; yeniden kurulum yok):
**2.172 düğüm, 6.001 kenar, 95 topluluk** (Faz 4: 1.491 / 3.646 / 79). Sağlık: `check-update` bekleyen iş bildirmedi;
`diagnose multigraph` — eksik uç 0, sarkan uç 0, birebir yinelenen 0, aynı uçlara çökertilen 0, derleme sonrası basit
grafik; 12 üretici bastırma noktası Graphify'ın kendi kodundadır (bkz. §0). `graphify query` yeni modülleri
(`EventStore`, `JobManager`, `LabelResult`, `Phase3Catalog`, `register()`, `CityMap`, `ExplorerPage`) buluyor.
Sembol üretmeyen 5 yapılandırma dosyası beklenen uyarıdır. Topluluk adları LLM ile yeniden etiketlenmedi (API anahtarı
gerektirir).

## 19. Git commit kimliği

Bu raporu içeren commit: `feat: implement SafeRoute 3D phase 5 interactive dashboard` (kimlik kapanış mesajında).
Büyük veri ve model arşivleri (`data/`, laboratuvar önbelleği, `frontend/dist`, `test-results`) Git dışındadır.

## 20. Faz 6 için öneriler

1. **Kalıcı çalışan havuzu** (önceden ısınmış süreç, iptal için süreç başına iş sınırı) ile dinamik iş başlangıç
   süresini ~4 sn'den saniye altına indirmek; iş kuyruğunu kalıcı hâle getirmek (SQLite/PostgreSQL).
2. **PostGIS** (spesifikasyondaki üretim hedefi) ile filtre + bbox sorgularını veritabanına taşımak; nokta katmanını
   vektör karo (PMTiles/MVT) olarak sunmak.
3. Dinamik sonuçlar için dışbükey zarf üretimi ve kayıtlı/dinamik sonuçların yan yana karşılaştırması (ARI, Jaccard).
4. Laboratuvar önbelleği için boyut/yaş tabanlı temizleme; iş sonuçlarına imza (SHA-256) ve manifest.
5. Gerçek GPU'da kare süresi/bellek profili ve düşük donanım modu; Lighthouse ölçümleri.
6. Uçtan uca test ortamında harita karoları için yerel karo sunucusu (ağ bağımsız CI).
7. Etken kodları için doğrulanmış Türkçe sözlük (kaynak metin korunarak).
