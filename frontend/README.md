# SafeRoute 3D — Ön Yüz (Faz 5 analiz uygulaması)

Gerçek New York kaza kayıtları üzerinde beş ekranlı analiz uygulaması: Genel bakış, 3D Şehir Keşfi (Faz 4 harita
motoru), Kümeleme Laboratuvarı, Model Karşılaştırma ve Veri Gezgini. Tüm sayılar arka uçtaki doğrulanmış Faz 1–4
kayıtlarından ve canlı sunucu sorgularından gelir; sabit örnek değer yoktur.

| Katman | Teknoloji |
|---|---|
| Arayüz | React 19, TypeScript 7, Vite 8, Tailwind CSS 4, shadcn/ui (Radix), lucide ikonları |
| Tipografi | Plus Jakarta Sans (başlık, metrik) + Manrope (gövde), yerel @fontsource |
| Durum | Zustand (ekran, filtreler, veri kaynağı, katmanlar, zaman dilimi, aktif iş) |
| Grafik | Recharts (tek seri, tek ton; çift eksen yok) |
| Harita | MapLibre GL JS 6.15 + OpenFreeMap karoları; Three.js 0.186 GLB katmanı |
| Veri | FastAPI (`saferoute serve`): Faz 4 katmanları + Faz 5 analitik API'si |

## Çalıştırma

```bash
# depo kökünden
backend/.venv/Scripts/saferoute.exe viz-build   # Faz 4 katmanları (bir kez)
cd frontend && npm ci && npm run build && cd ..
backend/.venv/Scripts/saferoute.exe serve       # http://127.0.0.1:8000  (ekranlar: #/genel-bakis, #/kesif, #/laboratuvar, #/modeller, #/veri)
```

Geliştirme: `saferoute serve` çalışırken `npm run dev` → http://127.0.0.1:5173 (`/api` 8000'e yönlendirilir).

## Komutlar

| Komut | İş |
|---|---|
| `npm run build` | Tip denetimi + üretim derlemesi (`dist/`) |
| `npm test` | Vitest: Faz 4 mantığı + Faz 5 filtre/laboratuvar formu/yönlendirme/önbellek + jsdom bileşen testleri |
| `npx playwright test e2e/phase5.spec.ts` | Faz 5 uçtan uca (gerçek uygulama); ekran görüntüleri `reports/phase5/screenshots/` |
| `SAFEROUTE_PHASE4_OUT=test-results/phase4-regression npx playwright test e2e/viewer.spec.ts` | Faz 4 regresyonu (Faz 4 artefaktlarının üzerine yazmaz) |
| `npm run assets` / `npm run tiles:audit` | Faz 4 GLB hattı / bina yüksekliği denetimi |

## Yapı

```text
src/app/            store (Zustand + hash yönlendirme)
src/components/     ui/ (shadcn), layout/ (Navigation), common (MetricCard, InfoTip, durumlar), charts, ExportMenu,
                    Faz 4: CameraControls, Legend, AssetInspector
src/features/
  overview/         OverviewPage
  explorer/         ExplorerPage, CityMap (Faz 4 motoru), FilterPanel, ViewPanel, ClusterDetails, TimeControls
  lab/              LabPage, AlgorithmControls, labForm (doğrulama), ExperimentResults, SavedExperiments
  models/           ModelsPage, ComparisonCharts
  data/             DataPage, DataDictionary
src/lib/            api, filters, query (önbellek/iptal), types, geo, camera, layers, glb, registry, format
src/map/            style, dataLayers, threeLayer, traffic, picking (Faz 4)
```

**Filtre ≠ yeniden kümeleme.** "Mevcut kümelerde göster" filtrelenmiş gerçek kayıtları tam veri modelinin etiketleriyle
gösterir; yeni kümeleme yalnızca Laboratuvar'da, sunucuda ayrı bir süreçte çalışan bir iş olarak başlatılır ve haritada
"Dinamik analiz sonucu" olarak ayrıca etiketlenir. Araç hareketleri temsili simülasyondur.
