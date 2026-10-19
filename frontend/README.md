# SafeRoute 3D — Ön Yüz (Faz 4 görüntüleyici)

Gerçek New York haritası üzerinde Faz 3 DBSCAN sonuçlarını ve lisanslı GLB modellerini gösteren temel 3D şehir
görüntüleyicisi. Faz 5'in gösterge paneli, kümeleme laboratuvarı ve gelişmiş filtre ekranları henüz yoktur.

| Katman | Teknoloji |
|---|---|
| Arayüz | React 19, TypeScript 7, Vite 8, Tailwind CSS 4 (Plus Jakarta Sans + Manrope, yerel @fontsource) |
| Harita | MapLibre GL JS 6.15 + OpenFreeMap vektör karoları (OpenMapTiles şeması, OSM verisi; API anahtarı yok) |
| 3D | Three.js 0.186 — MapLibre özel katmanı (ortak WebGL bağlamı ve derinlik tamponu) |
| Veri | FastAPI katman API'si (`saferoute serve`): doğrulanmış Faz 3 çıktıları, bbox sorguları |

## Çalıştırma

```bash
# depo kökünden
backend/.venv/Scripts/saferoute.exe viz-build   # katmanlar (bir kez)
cd frontend && npm ci && npm run build && cd ..
backend/.venv/Scripts/saferoute.exe serve       # http://127.0.0.1:8000
```

Geliştirme: `saferoute serve` çalışırken `npm run dev` → http://127.0.0.1:5173 (`/api` 8000'e yönlendirilir).

## Komutlar

| Komut | İş |
|---|---|
| `npm run build` | Tip denetimi + üretim derlemesi (`dist/`) |
| `npm test` | Vitest birim testleri (coğrafi dönüşüm, GLB/lisans, kamera, katmanlar, seçim, yol seçimi) |
| `npm run e2e` | Playwright: gerçek çalışan uygulama; ekran görüntüleri `reports/phase4/screenshots/` |
| `npm run assets` | GLB optimizasyonu + `public/models/registry.json` (kaynak ZIP'ler: `assets/3d/downloads/`) |
| `npm run tiles:audit` | Bina yüksekliği veri denetimi → `reports/phase4/building_height_audit.json` |

## Yapı

```text
src/lib/        geo (Mercator/çapa matrisi), api, camera, layers, glb, registry, format
src/map/        style (gece/gündüz), dataLayers (Faz 3 katmanları), threeLayer (GLB sahnesi),
                traffic (gerçek yol seçimi), picking (en yakın küme seçimi)
src/components/ TopBar, SidePanel, ClusterPanel, Legend, CameraControls, AssetInspector
tests/unit/     Vitest        e2e/   Playwright        scripts/   varlık hattı ve karo denetimi
```

Ön yüz yalnızca arka uçtan gelen gerçek analiz sonuçlarını gösterir; metrikler sabit kodlanmaz. Araç hareketleri
temsili simülasyondur ve arayüzde bu şekilde etiketlenir.
