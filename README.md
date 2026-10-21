# SafeRoute 3D

New York City'de polise raporlanmış motorlu taşıt kazalarının mekânsal yoğunlaşmalarını denetimsiz öğrenme (DBSCAN; karşılaştırma için K-Means ve HDBSCAN) ile keşfeden ve sonuçları gerçek coğrafyaya hizalı 3B bir şehir haritasında sunan akademik makine öğrenmesi projesi.

- **Kalıcı şartname:** [`PROJECT_SPEC.md`](PROJECT_SPEC.md)
- **Güncel durum:** Faz 7 (akademik sunum, proje raporu, kod açıklamaları, savunma soruları ve canlı demo rehberi) tamamlandı: [`deliverables/`](deliverables/README.md). Faz 6 (güvenilirlik, kalıcı iş kaydı, kaynak güvenliği, performans ölçümü, tek komutla çalıştırma) uygulandı. Raporlar: [`docs/phase1/TEKNIK_RAPOR.md`](docs/phase1/TEKNIK_RAPOR.md), [`docs/phase2/TEKNIK_RAPOR.md`](docs/phase2/TEKNIK_RAPOR.md), [`docs/phase3/TEKNIK_RAPOR.md`](docs/phase3/TEKNIK_RAPOR.md), [`docs/phase4/TEKNIK_RAPOR.md`](docs/phase4/TEKNIK_RAPOR.md), [`docs/phase5/TEKNIK_RAPOR.md`](docs/phase5/TEKNIK_RAPOR.md), [`docs/phase6/TEKNIK_RAPOR.md`](docs/phase6/TEKNIK_RAPOR.md)

> Kaza yoğunluğu tek başına risk değildir. Bu proje trafik kazası **tahmini yapmaz**; kaydedilmiş kazaların mekânsal yoğunlaşmalarını inceler.

## Depo yapısı

```text
PROJECT_SPEC.md          Kalıcı mimari ve akademik sözleşme
backend/                 Python paketi (saferoute): veri hattı, doğrulama, EDA; testler
  src/saferoute/data/    source, download, loader, validate, metadata, convert
  src/saferoute/eda/     profile, figures, report, dictionary
  src/saferoute/preprocess/  Faz 2: standardize, boundaries, geo, temporal, vehicles, casualties,
                         coordinates, duplicates, features, pipeline, report
  src/saferoute/clustering/  Faz 3: deney kaydı, DBSCAN/K-Means/HDBSCAN, değerlendirme, raporlar
  src/saferoute/viz/     Faz 4: manifest doğrulamalı coğrafi katmanlar + FastAPI katman API'si
notebooks/               01_dataset_exploration, 02_preprocessing_feature_engineering, 03_clustering_experiments
data/raw/                Değişmez ham anlık görüntüler: kazalar + resmî ilçe sınırları (git dışı)
data/interim/            Kayıpsız metin Parquet + türleri doğrulanmış interim katman (git dışı)
data/processed/          İşlenmiş katman, konum tablosu, model öznitelik matrisleri (git dışı)
data/metadata/           Edinim ve kaynak durumu kayıtları (git'te izlenir)
reports/phase1/          Otomatik EDA raporu, özet JSON, manifest kopyası, şekiller
reports/phase2/          Ön işleme raporu, özet JSON, eşleme/çelişki/tekrar tabloları, şekiller
reports/phase3/          Kümeleme raporu, akademik tablolar, şekiller, Faz 4 manifest kopyası
reports/phase4/          Ekran görüntüleri, varlık optimizasyonu, bina yüksekliği denetimi, ölçümler
docs/                    Veri sözlüğü, köken, kalite, özellik adayları, karar günlüğü, faz raporları
scripts/                 Faz 1 hattını uçtan uca çalıştıran betikler
frontend/                Faz 4 görüntüleyici: React + TypeScript + Vite + Tailwind + MapLibre + Three.js
  public/models/         Optimize GLB modeller + varlık/lisans kaydı (registry.json)
assets/3d/               Varlık kaydı açıklaması; indirilen ZIP paketleri (downloads/) git dışı
```

Şartnamedeki örnek yapıdan bilinçli farklar `docs/decision_log.md` içinde açıklanmıştır (ör. `analysis/eda.py` yerine `eda/` paketi, şekillerin `reports/phase1/figures/` altında tutulması).

## Kurulum

Gereksinimler: Python ≥ 3.11 ve [uv](https://docs.astral.sh/uv/). Yaklaşık 1 GB boş disk alanı ve 4 GB RAM yeterlidir (ölçülen süreç tepe değeri yaklaşık 2,3 GB).

```bash
cd backend
uv venv .venv
uv pip install -e ".[dev,notebook]" --python .venv/Scripts/python.exe   # Linux/macOS: .venv/bin/python
```

İsteğe bağlı: Socrata kısıtlamalarını azaltmak için uygulama anahtarı. `.env.example` dosyasına bakın; anahtar yalnızca ortam değişkeninden okunur ve depoya yazılmaz.

## Uygulamayı çalıştırma (Windows, tek komut)

Veri hatları (Faz 1–4) bir kez çalıştırıldıktan sonra uygulama tek komutla açılır. Betik veri setini yeniden
**indirmez** ve model eğitimini **başlatmaz**; yalnızca denetler, gerekirse ön yüzü derler ve sunucuyu başlatır.

```powershell
# Depo kökünden (PowerShell):
powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1            # ön planda; Ctrl+C ile durur
powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1 -Demo -Background -Open   # akademik demo profili
powershell -ExecutionPolicy Bypass -File scripts\stop_saferoute.ps1             # arka plandaki sunucuyu durdurur
```

| Seçenek | Ne yapar |
|---|---|
| (yok) | Python ≥ 3.11 + paketler, Faz 2–4 veri/model dosyaları, GLB varlık kaydı, boş bellek ve harita karo erişimi denetlenir; ön yüz kaynakları derlemeden yeniyse `npm run build`; sunucu bu pencerede başlar, hazır olunca adres yazılır |
| `-Demo` | Ek olarak genel bakış, model karşılaştırma, veri sözlüğü ve seçili üç modelin kayıtlı sonuçlarını önceden yükler; dinamik analiz için kaynak uygun mu söyler; demo planını gösterir |
| `-Background` | Sunucuyu arka planda başlatır (PID `.saferoute\server.pid`, günlük `.saferoute\server.log`) |
| `-Port 8010` | Farklı port (8000 başka bir uygulamadaysa o sürece dokunulmaz, hata verilir) |
| `-Rebuild` / `-Open` | Ön yüzü her durumda derle / hazır olunca tarayıcıyı aç |

- Adres: http://127.0.0.1:8000 (yalnızca bu bilgisayardan erişilir).
- **İnternet:** altlık harita, 3D bina ve yol karoları OpenFreeMap'ten gelir ve ağ gerektirir. Ağ yoksa kaza
  katmanları, kümeler ve tüm analiz ekranları yerel sunucudan çalışır; harita zemini boş görünür. Karo sağlayıcısının
  izin vermediği çevrimdışı çoğaltma yapılmaz.
- **Durdurma:** ön planda Ctrl+C; arka planda `stop_saferoute.ps1` (yalnızca kaydettiği ve komut satırı doğrulanan
  SafeRoute sürecini durdurur). Sunucu kapanırken veya çökerse yarım kalan laboratuvar işleri bir sonraki açılışta
  "Yarıda kaldı" olarak işaretlenir; kendiliğinden yeniden çalıştırılmaz (Laboratuvar → İş geçmişi → Yeniden dene).
- Demo senaryosu ve beklenen sonuçlar: [`docs/phase6/DEMO_TEST_PLANI.md`](docs/phase6/DEMO_TEST_PLANI.md).

## Hatları çalıştırma

### Faz 1

Tek komut (depo kökünden):

```bash
bash scripts/run_phase1.sh          # Windows PowerShell: scripts\run_phase1.ps1
```

Adım adım (`backend/` içinden, `.venv/Scripts/` veya `.venv/bin/` önekiyle):

| Komut | Ne yapar | Çıktı |
|---|---|---|
| `saferoute check-source` | Kaynak erişilebilirliği, sürüm, güncellik | `data/metadata/source_status_*.json` |
| `saferoute download` | Sayfalı + yeniden denemeli tam indirme | `data/raw/h9gi-nx95/snapshot_*/`, edinim kaydı |
| `saferoute download --resume <dizin>` | Yarım kalan indirmeyi sürdürür | |
| `saferoute verify` | SHA-256 bütünlük doğrulaması | |
| `saferoute record` | Edinim kaydı (tam veya kısmi) | `data/metadata/acquisition_*.json` |
| `saferoute parquet` | Kayıpsız Parquet kopyası | `data/interim/.../crashes_raw_text.parquet` |
| `saferoute eda` | Profil, şekiller, rapor, veri sözlüğü | `reports/phase1/`, `docs/data_dictionary.md` |

Defter: `backend/.venv/Scripts/python.exe scripts/execute_notebook.py notebooks/01_dataset_exploration.ipynb`

### Faz 2

```bash
bash scripts/run_phase2.sh          # Windows PowerShell: scripts\run_phase2.ps1 [-Force]
```

| Komut | Ne yapar | Çıktı |
|---|---|---|
| `saferoute boundaries` | Resmî DCP ilçe sınırlarını indirir ve doğrular | `data/raw/gthc-hcne/snapshot_*/` |
| `saferoute preprocess` | raw → interim → processed → features; idempotent | `data/interim/`, `data/processed/`, `reports/phase2/`, `docs/feature_selection_report.md` |
| `saferoute preprocess --force` | Güncel olsa da yeniden üretir (içerik özeti aynı kalır) | |

Defter: `backend/.venv/Scripts/python.exe scripts/execute_notebook.py notebooks/02_preprocessing_feature_engineering.ipynb`

Testler (ağ gerektirmez): `cd backend && .venv/Scripts/python.exe -m pytest`

### Faz 3

```bash
backend/.venv/Scripts/saferoute.exe cluster                     # kayıtlı başarılı deneyler yeniden çalıştırılmaz
backend/.venv/Scripts/saferoute.exe cluster --stages profiles   # yalnızca belirli aşamalar (kontrol noktasından)
```

Defter: `notebooks/03_clustering_experiments.ipynb` (sunum + çapraz doğrulama; model eğitmez).

### Faz 4 — 3D şehir görüntüleyici

Ek gereksinim: Node.js ≥ 20. Harita karoları için ağ erişimi (OpenFreeMap, API anahtarı gerekmez).

```bash
cd backend && uv pip install -e ".[dev,api]" --python .venv/Scripts/python.exe && cd ..
backend/.venv/Scripts/saferoute.exe viz-build     # Faz 3 manifestini SHA-256 ile doğrular, katmanları üretir
cd frontend && npm ci && npm run build && cd ..
backend/.venv/Scripts/saferoute.exe serve         # http://127.0.0.1:8000 (API + derlenmiş ön yüz)
```

Tek komut: `bash scripts/run_phase4.sh` (Windows: `scripts\run_phase4.ps1`). Geliştirme: `saferoute serve` + `cd frontend && npm run dev` (http://127.0.0.1:5173, `/api` vekili).

| Komut | Ne yapar |
|---|---|
| `npm run assets` | Kenney (CC0) GLB'lerini ZIP'ten okur, optimize eder, LOD ve lisans kaydı üretir |
| `npm run tiles:audit` | OpenFreeMap bina yüksekliği verisini NYC karolarında denetler |
| `npm test` | Birim testleri (Vitest) |
| `npm run e2e` | Gerçek çalışan uygulamada Playwright testleri + ekran görüntüleri |
| `saferoute viz-bench` | API gecikme/yük ölçümü |

**Yeniden üretilebilirlik notu:** Yeni bir indirme, kaynak bu arada güncellendiyse farklı bir anlık görüntü üretir. Raporlanan sonuçlar, `data/metadata/acquisition_snapshot_20261019T155113Z.json` içindeki SHA-256 değerine sahip anlık görüntüye aittir.

## Belgeler

| Belge | İçerik |
|---|---|
| [`docs/dataset_provenance.md`](docs/dataset_provenance.md) | Kaynak, API yöntemi, sürüm, güncellik, lisans |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Her sütun: tür, eksik sayı/oran, kullanım, not (otomatik) |
| [`docs/data_quality.md`](docs/data_quality.md) | Veri kalitesi bulguları ve etkileri |
| [`docs/feature_candidates.md`](docs/feature_candidates.md) | Özellik sınıflandırması ve önerilen deneyler |
| [`docs/decision_log.md`](docs/decision_log.md) | Teknik kararlar ve gerekçeleri (K-01…K-29) |
| [`assets/3d/README.md`](assets/3d/README.md) | 3D varlık kaydı: kaynak, lisans, optimizasyon |
| [`docs/feature_selection_report.md`](docs/feature_selection_report.md) | Faz 2 öznitelik seçimi tablosu (otomatik) |
| [`reports/phase2/ON_ISLEME_RAPORU.md`](reports/phase2/ON_ISLEME_RAPORU.md) | Otomatik ön işleme raporu ve şekiller |
| [`reports/phase1/EDA_RAPORU.md`](reports/phase1/EDA_RAPORU.md) | Otomatik EDA raporu ve şekiller |

## Veri kaynağı ve atıf

- NYC Open Data — *Motor Vehicle Collisions - Crashes* (`h9gi-nx95`), New York City Police Department (NYPD). https://data.cityofnewyork.us/d/h9gi-nx95
- NYC Open Data — *Borough Boundaries* (`gthc-hcne`), Department of City Planning (DCP). https://data.cityofnewyork.us/City-Government/Borough-Boundaries/gthc-hcne
- Harita karoları: [OpenFreeMap](https://openfreemap.org) · © [OpenMapTiles](https://www.openmaptiles.org/) · Veri © [OpenStreetMap katkıcıları](https://www.openstreetmap.org/copyright) (ODbL)
- 3D modeller: [Kenney](https://kenney.nl) — Car Kit, City Kit (Roads), CC0 1.0
