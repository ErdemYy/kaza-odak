# SafeRoute 3D

New York City'de polise raporlanmış motorlu taşıt kazalarının mekânsal yoğunlaşmalarını denetimsiz öğrenme (DBSCAN; karşılaştırma için K-Means ve HDBSCAN) ile keşfeden ve sonuçları gerçek coğrafyaya hizalı 3B bir şehir haritasında sunan akademik makine öğrenmesi projesi.

- **Kalıcı şartname:** [`PROJECT_SPEC.md`](PROJECT_SPEC.md)
- **Güncel durum:** Faz 1 (Veri Seti Temeli ve EDA) tamamlandı. Rapor: [`docs/phase1/TEKNIK_RAPOR.md`](docs/phase1/TEKNIK_RAPOR.md)

> Kaza yoğunluğu tek başına risk değildir. Bu proje trafik kazası **tahmini yapmaz**; kaydedilmiş kazaların mekânsal yoğunlaşmalarını inceler.

## Depo yapısı

```text
PROJECT_SPEC.md          Kalıcı mimari ve akademik sözleşme
backend/                 Python paketi (saferoute): veri hattı, doğrulama, EDA; testler
  src/saferoute/data/    source, download, loader, validate, metadata, convert
  src/saferoute/eda/     profile, figures, report, dictionary
notebooks/               01_dataset_exploration.ipynb (çalıştırılmış, Türkçe)
data/raw/                Değişmez ham anlık görüntüler (git dışı)
data/interim/            Kayıpsız Parquet kopyası (git dışı)
data/processed/          Faz 2+ çıktıları (git dışı)
data/metadata/           Edinim ve kaynak durumu kayıtları (git'te izlenir)
reports/phase1/          Otomatik EDA raporu, özet JSON, manifest kopyası, şekiller
docs/                    Veri sözlüğü, köken, kalite, özellik adayları, karar günlüğü, faz raporları
scripts/                 Faz 1 hattını uçtan uca çalıştıran betikler
frontend/                Faz 5'te oluşturulacak (şimdilik yalnızca README)
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

## Faz 1 hattını çalıştırma

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

Testler (ağ gerektirmez): `cd backend && .venv/Scripts/python.exe -m pytest`

**Yeniden üretilebilirlik notu:** Yeni bir indirme, kaynak bu arada güncellendiyse farklı bir anlık görüntü üretir. Raporlanan sonuçlar, `data/metadata/acquisition_snapshot_20261019T155113Z.json` içindeki SHA-256 değerine sahip anlık görüntüye aittir.

## Belgeler

| Belge | İçerik |
|---|---|
| [`docs/dataset_provenance.md`](docs/dataset_provenance.md) | Kaynak, API yöntemi, sürüm, güncellik, lisans |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Her sütun: tür, eksik sayı/oran, kullanım, not (otomatik) |
| [`docs/data_quality.md`](docs/data_quality.md) | Veri kalitesi bulguları ve etkileri |
| [`docs/feature_candidates.md`](docs/feature_candidates.md) | Özellik sınıflandırması ve önerilen deneyler |
| [`docs/decision_log.md`](docs/decision_log.md) | Teknik kararlar ve gerekçeleri |
| [`reports/phase1/EDA_RAPORU.md`](reports/phase1/EDA_RAPORU.md) | Otomatik EDA raporu ve şekiller |

## Veri kaynağı ve atıf

NYC Open Data — *Motor Vehicle Collisions - Crashes* (`h9gi-nx95`), New York City Police Department (NYPD). https://data.cityofnewyork.us/d/h9gi-nx95
