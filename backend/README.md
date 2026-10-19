# SafeRoute 3D — Arka Uç (Python)

`saferoute` paketi: resmi NYC çarpışma verisinin değişmez ham anlık görüntüsünü indirir, doğrular, kayıpsız Parquet kopyasını üretir ve keşifsel veri analizi (EDA) raporlarını oluşturur; Faz 2'de resmî ilçe sınırlarıyla zenginleştirilmiş işlenmiş katmanı ve model öznitelik matrislerini üretir. Kurulum ve uçtan uca kullanım için depo kökündeki `README.md` dosyasına bakın.

## Kurulum

```bash
cd backend
uv venv .venv
uv pip install -e ".[dev,notebook]" --python .venv/Scripts/python.exe   # Linux/macOS: .venv/bin/python
```

`dev` ekstrası pytest ve scikit-learn'ü (Haversine ve ağırlıklı DBSCAN uyumluluk testleri için), `notebook` ekstrası ise defteri çalıştırmak için ipykernel, nbclient ve nbformat'ı kurar.

## Komutlar

```bash
saferoute check-source              # kaynak erişilebilirliği + güncellik -> data/metadata/
saferoute download                  # yeni anlık görüntü: data/raw/h9gi-nx95/snapshot_<UTC>/
saferoute download --resume <dizin> # yarım kalan indirmeyi sürdürür
saferoute verify [<dizin>]          # SHA-256 bütünlük doğrulaması (varsayılan: en yeni)
saferoute record [<dizin>]          # edinim kaydı (full/partial) -> data/metadata/
saferoute parquet [<dizin>]         # kayıpsız Parquet kopyası -> data/interim/
saferoute eda [--snapshot <dizin>]  # reports/phase1/ + docs/data_dictionary.md
saferoute boundaries                # resmî ilçe sınırları -> data/raw/gthc-hcne/
saferoute preprocess [--force]      # Faz 2: interim, processed, features + reports/phase2/
```

## Testler

```bash
.venv/Scripts/python.exe -m pytest
```

Testler ağ erişimi gerektirmez. Sahte bir Socrata sunucusu (`tests/conftest.py`) ve kusurları bilinen küçük **sentetik** örnek veri kullanırlar. Bu örnekler yalnızca testlerde bulunur; hiçbir rapor veya proje verisinde kullanılmaz.

## Modüller

| Modül | Görev |
|---|---|
| `saferoute.config` | Sabitler, dizinler, NYC sınırlayıcı kutusu, ilçe sınırı kaynağı |
| `saferoute.data.source` | Yayıncı meta verisi ve sunucu tarafı sayım/kapsam sorguları |
| `saferoute.data.download` | Sayfalı, yeniden denemeli, sürdürülebilir indirme; manifest ve SHA-256 |
| `saferoute.data.loader` | Bütünlük doğrulamalı, tamamen metin sütunlu ham yükleme; Parquet okuma |
| `saferoute.data.validate` | Şema kontrolü, eksik sütun tespiti, tarih/saat ayrıştırma, ilçe etiketi doğrulama, eksik yüzdesi |
| `saferoute.data.metadata` | Kaynak durumu (güncellik kararı) ve edinim kaydı (full/partial) |
| `saferoute.data.convert` | Kayıpsız Parquet kopyası ve yan kayıt |
| `saferoute.eda.profile` | Ölçüm fonksiyonları (veriyi değiştirmez, doldurmaz) |
| `saferoute.eda.figures` | Ölçülmüş değerlerden Türkçe PNG şekiller |
| `saferoute.eda.dictionary` | Sütun anlamları, kullanım sınıfları; veri sözlüğü üretimi |
| `saferoute.eda.report` | `eda_summary.json`, `EDA_RAPORU.md`, `source_manifest.json`, veri sözlüğü |
| `saferoute.perf` | Adım süreleri ve süreç bellek tepe değeri |
| `saferoute.preprocess.settings` | Faz 2 yapılandırması, yapılandırma SHA-256, hat sürümü |
| `saferoute.preprocess.standardize` | Interim katman: tür doğrulama, metin standardizasyonu, koordinat ayrıştırma durumu |
| `saferoute.preprocess.boundaries` | DCP ilçe sınırları: indirme, doğrulama, CRS kontrolleri |
| `saferoute.preprocess.geo` | Koordinat kalite durumu, point-in-polygon ilçe çıkarımı, çelişki analizi |
| `saferoute.preprocess.temporal` | Tarih/saat öznitelikleri, döngüsel kodlama, 00:00 bayrağı, dakika yığılması |
| `saferoute.preprocess.vehicles` | Araç türü normalizasyonu ve kural tabanlı kategori eşlemesi |
| `saferoute.preprocess.casualties` | Yaralı/ölü tutarlılık bayrakları |
| `saferoute.preprocess.coordinates` | Radyan, Haversine, eps dönüşümü, EPSG:32618 ve doğruluk kontrolü |
| `saferoute.preprocess.duplicates` | Konum kimlikleri, ağırlıklı benzersiz konumlar, tekrar analizi, yedek geokodlama bayrağı |
| `saferoute.preprocess.features` | Öznitelik seçimi kayıt defteri ve model matrisleri |
| `saferoute.preprocess.pipeline` | Orkestrasyon, yan kayıtlar, idempotentlik, ham veri doğrulaması |
| `saferoute.preprocess.report` | Faz 2 şekilleri, tabloları ve raporları |
