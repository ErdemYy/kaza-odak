# SafeRoute 3D — Arka Uç (Python)

Faz 1 kapsamı: resmi NYC çarpışma verisinin değişmez ham anlık görüntüsünü indirmek ve keşifsel veri analizi (EDA) raporu üretmek.

## Kurulum

```bash
cd backend
uv venv .venv
uv pip install -e ".[dev]" --python .venv/Scripts/python.exe   # Linux/macOS: .venv/bin/python
```

İsteğe bağlı: Socrata kısıtlamalarını azaltmak için bir uygulama anahtarı tanımlanabilir. Anahtar yalnızca ortam değişkeninden okunur, depoya yazılmaz:

```bash
export SODA_APP_TOKEN=...   # PowerShell: $env:SODA_APP_TOKEN = "..."
```

## Kullanım

```bash
saferoute download                 # yeni anlık görüntü: data/raw/h9gi-nx95/snapshot_<UTC>/
saferoute download --resume <dizin> # yarım kalan indirmeyi kaldığı sayfadan sürdürür
saferoute verify [<dizin>]         # SHA-256 bütünlük doğrulaması (varsayılan: en yeni)
saferoute eda [--snapshot <dizin>] # reports/phase1/ altına EDA raporu
```

Ham veri dizini `SAFEROUTE_DATA_DIR` ortam değişkeniyle değiştirilebilir.

## Testler

```bash
.venv/Scripts/python.exe -m pytest
```

Testler ağ erişimi gerektirmez; sahte bir Socrata sunucusu ve kusurları bilinen küçük bir örnek veri kullanır.

## Modüller

| Modül | Görev |
|---|---|
| `saferoute.data.source` | Yayıncı meta verisi ve sunucu tarafı sayım/kapsam sorguları |
| `saferoute.data.download` | Sayfalı, yeniden denemeli, sürdürülebilir indirme; manifest ve SHA-256 |
| `saferoute.data.loader` | Bütünlük doğrulamalı, tamamen metin sütunlu ham yükleme |
| `saferoute.eda.profile` | Ölçüm fonksiyonları (veriyi değiştirmez, doldurmaz) |
| `saferoute.eda.figures` | Ölçülmüş değerlerden PNG şekiller |
| `saferoute.eda.report` | `eda_summary.json`, `EDA_RAPORU.md`, `source_manifest.json` |
