# SafeRoute 3D — Faz 8B Regresyon Sonuçları

> Tüm son sonuçlar **aynı son derleme** üzerinde alındı (Faz 8B kaynakları, `npm run build`). Playwright çıktıları ortam
> değişkenleriyle `reports/phase8b/regresyon/` altına yönlendirildi; `reports/phase4–8` dizinlerinin hiçbiri yeniden
> yazılmadı. Hiçbir önceki test silinmedi, devre dışı bırakılmadı veya beklentisi gevşetilmedi.

## Son durum

| Paket | Sonuç | Çıktı |
|---|---|---|
| Backend pytest (Faz 1–6) | **210 / 210** (82,9 sn, tek başına) | — |
| Vitest | **102 / 102** (86 önceki + 16 yeni `phase8b.test.tsx`) | — |
| TypeScript `tsc -b` | hatasız | — |
| Production build (`vite build`) | başarılı | `frontend/dist` (Git dışı) |
| Playwright Faz 8B (`phase8b.spec.ts`) | **3 / 3** | `reports/phase8b/phase8b-e2e.log`, `reports/phase8b/e2e/` |
| Playwright Faz 8 (`phase8.spec.ts`) | **19 / 19 — 125 / 125 etkileşim** | `regresyon/phase8.log`, `regresyon/phase8/interaction_results.json` |
| Playwright Faz 6 (`phase6.spec.ts`) | **12 / 12** | `regresyon/phase6.log` |
| Playwright Faz 6 yeniden başlatma | **1 / 1** | `regresyon/phase6-restart.log` |
| Playwright Faz 5 | **11 / 11** | `regresyon/phase5.log` |
| Playwright Faz 4 (`viewer.spec.ts`) | **11 / 11** | `regresyon/phase4.log` |
| Görsel sahne yakalama (önce/sonra) | 5 / 5 + 5 / 5 | `screenshots/before`, `screenshots/after` (konsol hatası 0) |
| Performans A/B (GPU) | 4 / 4 | `reports/phase8b/perf/` |

## Faz 8B yeni testleri

**Vitest (`tests/unit/phase8b.test.tsx`, 16):** gece ve gündüz stillerinin tamamı (altlık + tüm veri katmanları)
`@maplibre/maplibre-gl-style-spec` `validateStyleMin` ile 0 hata; hover/seçim katmanları tek öğe süzgeciyle başlar ve
bina extrüzyonlarının altına eklenir; palet ışıklılık sıralaması ve Faz 8'e göre kontrast; tema zemin renkleri (Faz 4
sözleşmesi); tema ışığı aralığı; `centroidRadius` monotonluğu ve kıstırma; lejant boyut ölçeği aynı sabitlerden ve "risk
değil" metni; 4 px yakın iki kümenin seçim kuralı; `fitDistance` kadrajı; `disposeObject` (paylaşılan kaynak bir kez);
küme paneli üst özet, grup sırası, kapalı model grubu; araç oranı %100 notu; varlık inceleyici yerleştir/kaldır/yeniden
yerleştir ve kısa lisans; WebGL yokken önizleyici hata durumu.

**Playwright (`e2e/phase8b.spec.ts`, 3 test):**

| Test | Doğrulananlar |
|---|---|
| Harita | Yeni katmanlar (`centroid-hover`, `centroid-selected`) mevcut; **isabet alanı: ekranda görünen 53 küme merkezinin 53'ünde seçim kuralı kendi kimliğini döndürdü (yanlış 0)**; hover kartı kimliği = `pick` = tıklamanın açtığı küme; kartta API kayıt sayısı; hover süzgeci tek küme; seçimde halka süzgeci ve diğer merkezlerin 0,38 opaklığı, kapatınca geri dönüş; panel özet bandı, sıra, kapalı model grubu açılır; panel kendi içinde kayar, başlık görünür kalır; uygulama konsol hatası 0 |
| GLB önizleyici | Ad, kısa ve tam lisans; Faz 4/8 sözleşmesi (düğme = yerleştir, harita nesnesi 1); kadraj uzaklığı = `fitDistance`; yakınlaştır/uzaklaştır; fareyle sürükleyerek döndür; ±30° düğmesi; sıfırla → kadraj; kaldır → önizleme açık, harita nesnesi 0; "Haritaya yerleştir" → 1; taksi → sedan → taksi sonrası `taxi.glb` isteği **1** ve GPU sayaçları büyümedi; kapanınca canlı önizleyici 0, GPU geometri 0, bağlam kayıp; harita bağlamı sağlam ve yerleştirilen model haritada |
| Yerleşim | Sol panel daralt/aç; daraltınca zaman çubuğu ≥ 200 px sola kayar ve şeritle çakışmaz; araç çubuğu "Filtreler" paneli geri açar; 1920/1440/1280/768/390 yatay taşma 0; sol/sağ panel ↔ zaman çubuğu çakışması yok; Genel bakışta uyarı + kaynak tarihi + analiz kapsamı + model dönemi görünür, yıl grafiği 1440×900 ilk ekranda; axe (WCAG 2.0/2.1/2.2 A–AA) 3D Şehir (GLB paneli açık) ve Genel bakış: **0 ihlal** — bilinen tek istisna aşağıda ayrıca kaydedilir |

## Bu fazda yakalanan başarısızlıklar (gizlenmedi)

| Deneme | Sonuç | Neden | Çözüm |
|---|---|---|---|
| Faz 8 deneme 1 (`regresyon/phase8-deneme1*`) | 18 / 19 test, **124 / 125** etkileşim; `O03` başarısız | Faz 8B'nin Genel bakışa eklediği ayrı uyarı + kapsam kutuları yıl grafiğini 1440×900'de ilk ekranın altına itti; O03 imleci görünür alan dışına götürüyordu | Uyarı ve şerit tek blokta birleştirildi (~85 px kısa); Faz 8B'ye `toBeInViewport` koruması eklendi. Faz 8 testi **değiştirilmedi** |
| Faz 4 deneme 1 (`regresyon/phase4-deneme1*`) | 7 geçti, 1 başarısız, 3 çalışmadı (seri) | Gündüz zemin rengi `#E4E9F0` yapılmıştı; Faz 4 testi `#E8EDF3` bekliyor | Zemin `#E8EDF3`'e geri alındı; birim testiyle kilitlendi |
| Faz 5 deneme 1 | 11 / 11 | — | Genel bakış değiştiği için son derlemeyle yeniden çalıştırıldı |
| Faz 6 ara çalıştırma (`phase6-ara*`) | 12 / 12 + 1 / 1 | — | Son değişikliklerden önce koştuğu için son derlemeyle yeniden çalıştırıldı |
| Faz 8B deneme 1 (`phase8b-e2e-deneme1.log`) | 2 / 3 | Test yarışı: model "hazır" olduğunda yeni geometri henüz GPU'ya yüklenmemişti (sayaç 0/1) | Sayaç karşılaştırması `expect.poll` ile bir sonraki çizime bekletildi (ürün değişmedi) |
| Faz 8B geliştirme sırasında | — | Ön sürümlerde: GPU'da 2 doku kalması (PMREM) → ortam haritası kaldırıldı; `dl` içinde `p` (axe) → düzeltildi | — |
| Backend pytest temel çizgi | 208 / 210 | Vitest ile **eşzamanlı** çalıştırılınca iki Faz 6 zamanlama testi (`test_duplicate_active_request_not_run_twice`, `test_dynamic_vs_saved_identity_and_filter_recluster_separation`) | Kod değişmeden tek başına 16/16 ve tam paket 210/210; backend bu fazda değişmedi. Yük altında oynaklık (Faz 8'deki gözlemle tutarlı), kök neden doğrulanmadı |

## Bilinen, düzeltilmeyen bulgu

- **axe `label-content-name-mismatch`** — `button[data-testid="theme-toggle"]`: görünür "Gece/Gündüz" metni erişilebilir
  adda yok. Faz 8 `E` testi adı birebir `"Gece moduna geç"` olarak doğruladığı için değiştirilmedi. Faz 8B testinde bu
  kural ayrı ölçülür ve `reports/phase8b/e2e/phase8b_results.json` → `axe_known` alanına yazılır.

## Konsol ve ağ

Görsel sahne betiği ve Faz 8B haritası testi: uygulama kaynaklı konsol hatası **0**. Faz 8 paketinin konsol/ağ kayıtları
`regresyon/phase8/interaction_results.json` → `logs` (Faz 8 raporundaki bilinçli hatalar: `S01` 500 yanıtı, `E20`
altlık kesintisi, bağlam kaybı uyarısı).
