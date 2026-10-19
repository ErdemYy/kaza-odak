# SafeRoute 3D — Arka Uç (Python)

`saferoute` paketi: resmi NYC çarpışma verisinin değişmez ham anlık görüntüsünü indirir, doğrular, kayıpsız Parquet kopyasını üretir ve keşifsel veri analizi (EDA) raporlarını oluşturur. Kurulum ve uçtan uca kullanım için depo kökündeki `README.md` dosyasına bakın.

## Kurulum

```bash
cd backend
uv venv .venv
uv pip install -e ".[dev,notebook]" --python .venv/Scripts/python.exe   # Linux/macOS: .venv/bin/python
```

`dev` ekstrası pytest'i, `notebook` ekstrası ise defteri çalıştırmak için ipykernel, nbclient ve nbformat'ı kurar.

## Komutlar

```bash
saferoute check-source              # kaynak erişilebilirliği + güncellik -> data/metadata/
saferoute download                  # yeni anlık görüntü: data/raw/h9gi-nx95/snapshot_<UTC>/
saferoute download --resume <dizin> # yarım kalan indirmeyi sürdürür
saferoute verify [<dizin>]          # SHA-256 bütünlük doğrulaması (varsayılan: en yeni)
saferoute record [<dizin>]          # edinim kaydı (full/partial) -> data/metadata/
saferoute parquet [<dizin>]         # kayıpsız Parquet kopyası -> data/interim/
saferoute eda [--snapshot <dizin>]  # reports/phase1/ + docs/data_dictionary.md
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
