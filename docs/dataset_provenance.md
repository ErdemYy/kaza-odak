# Veri Kökeni (Provenance)

## Kaynak

| Alan | Değer |
|---|---|
| Veri seti | Motor Vehicle Collisions - Crashes |
| Kimlik | `h9gi-nx95` |
| Yayıncı | NYC Open Data; atıf: Police Department (NYPD) |
| Kaynak sayfa | https://data.cityofnewyork.us/d/h9gi-nx95 |
| Katalog | https://catalog.data.gov/dataset/motor-vehicle-collisions-crashes |
| Meta veri API | https://data.cityofnewyork.us/api/views/h9gi-nx95.json |
| Veri API (SODA) | https://data.cityofnewyork.us/resource/h9gi-nx95.csv |
| Birim | Her satır polise bildirilmiş bir kaza olayıdır |
| Lisans alanı | Socrata meta verisinde **boş** (`license: null`). NYC Open Data kullanım koşulları akademik raporda ayrıca belirtilmelidir. |

## Edinim yöntemi

API dokümantasyonu 2026-10-19 tarihinde incelendi (dev.socrata.com):

- **Sayfalama:** `$limit` ve `$offset` ile yapılır. `$offset`, 0'dan başlayan kayıt sırasıdır.
- **Uygulama anahtarı:** `X-App-Token` HTTP başlığıyla gönderilir. Anahtarsız istekler paylaşılan IP havuzundan kısıtlanır ve sunucu kısıtlama durumunda HTTP 429 döndürür.
- **Sıralama:** İncelenen dokümanda kararlı sayfalama için `$order` şartı açıkça yazılmıyor. Yine de `$order=:id` (sistem kimliği) kullanıldı. Gerekçe için `decision_log.md` K-02'ye bakın.

Uygulama (`backend/src/saferoute/data/download.py`):

1. **Başlangıç ölçümleri:** İndirme öncesinde meta veri (`rowsUpdatedAt`, sütun şeması) ve sunucu tarafı sayım/kapsam (`count(*)`, `min/max(crash_date)`) alınır.
2. **Sayfa indirme:** Her sayfa (250.000 satır) önce `.partial` dosyasına akıtılır. Ardından iki kontrol yapılır: CSV başlığı meta veri şemasıyla birebir karşılaştırılır ve satırlar tırnak içi satır sonları doğru ele alınarak sayılır. Kontrolden geçen dosya atomik olarak `part-NNNNN.csv` adını alır.
3. **Hata yönetimi:**
   - HTTP 408/429/5xx, bağlantı hatası ve akış kopmasında üstel geri çekilmeyle en çok 5 deneme yapılır.
   - 4xx hatalarında ve şema değişikliğinde yeniden deneme yapılmaz.
4. **Yarım kalan indirme:** `_progress.json` dosyası `acquisition_status: "partial"` taşır. `saferoute download --resume <dizin>` ile kalınan sayfadan devam edilir; `saferoute record` kısmi kaydı yazar.
5. **Bitiş ölçümleri ve kontroller:** İndirme sonrasında meta veri ve sunucu sayımı yeniden alınır, ardından şunlar kontrol edilir:
   - Satır sayısı eşleşmesi.
   - `rowsUpdatedAt` değişimi.
   - Sayfalar arasındaki `X-SODA2-Truth-Last-Modified` tutarlılığı.

   Sorun bulunursa manifest `status` alanına `complete_with_warnings` yazılır.
6. **Değişmezlik:** Parça dosyaları ve `manifest.json` salt-okunur yapılır. Her yüklemede SHA-256 yeniden doğrulanır.

## Bu projede kullanılan anlık görüntü

| Alan | Değer |
|---|---|
| Dizin | `data/raw/h9gi-nx95/snapshot_20261019T155113Z/` |
| İndirme (UTC) | 2026-10-19T15:51:15Z → 2026-10-19T16:01:15Z |
| Kaynak `rowsUpdatedAt` | 2026-06-15T23:05:47Z (indirme öncesi ve sonrası aynı) |
| Kaynak `viewLastModified` | 2026-07-31T20:59:38Z (meta veri/görünüm değişikliği; satır güncellemesi değil) |
| `X-SODA2-Truth-Last-Modified` | Tüm sayfalarda tek değer: Mon, 15 Jun 2026 23:05:52 GMT |
| Satır / sütun | 2.269.187 / 29 |
| Sunucu sayımı | 2.269.187 (birebir eşleşme) |
| En erken / en geç `crash_date` | 2012-07-01 / 2026-06-11 |
| Parça sayısı / CSV boyutu | 10 / 600.459.645 bayt |
| Birleşik SHA-256 | `2fe1297c24f7aad761bca1dc3c04ec0de3459d297e06af20fbfe5e35ad10be5e` |
| Edinim durumu | **full**, uyarı yok |
| Parquet kopyası | `data/interim/h9gi-nx95/snapshot_20261019T155113Z/crashes_raw_text.parquet`: 53.707.718 bayt, zstd. SHA-256 `37e755824ea37963c0bf6c4401c7afff9d525f8e5934a1bda526c7a0a5f0da59`. Ham CSV ile birebir eşitliği doğrulandı. |

Makine-okur kayıtlar:
- `data/metadata/acquisition_snapshot_20261019T155113Z.json`: edinim kaydı ve parça bazlı SHA-256 değerleri
- `data/metadata/source_status_*.json`: kaynak durumu kontrolleri
- `reports/phase1/source_manifest.json`: manifestin tam kopyası

## Güncellik değerlendirmesi

`saferoute check-source` 2026-10-19T16:25Z tarihinde çalıştırıldı:

- Beyan edilen güncelleme sıklığı: **Daily**
- Son satır güncellemesinin üzerinden geçen süre: **125 gün**
- Karar: **`stale`**. Ölçüt: Daily için 3 günlük eşik aşıldı.

Sonuç: Kaynak şu anda güncellenmiyor görünüyor ve 2026-06-11 sonrasındaki kazalar veride yok. Uygulama veri güncelliğini kullanıcıya bu tarihlerle göstermelidir.

## Gelecekteki ilçe sınırı kaynağı (Faz 2)

| Alan | Değer |
|---|---|
| Veri seti | Borough Boundaries (`gthc-hcne`), NYC Open Data |
| Yayıncı | Department of City Planning (DCP), provenance: official |
| Açıklama | İlçe sınırları, **su alanları hariç**; sürüm 26b (DCP BYTES of the BIG APPLE) |
| Alanlar | `borocode`, `boroname`, `shape_area`, `shape_leng`, `the_geom` (multipolygon) |
| Son güncelleme | 2026-05-26 |
| Erişilebilirlik | 2026-10-19'da doğrulandı; beş ilçenin tamamı mevcut |

Zenginleştirme stratejisi `feature_candidates.md` §4'te anlatılıyor.
