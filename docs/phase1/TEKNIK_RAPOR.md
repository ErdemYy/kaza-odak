# Faz 1 Tamamlanma Raporu — Veri Seti Temeli, Proje İskeleti ve Keşifsel Veri Analizi

**Proje:** SafeRoute 3D · **Faz:** 1 / 7 · **Tarih:** 2026-10-19 · **Durum:** Kabul ölçütleri karşılandı; Faz 2 için onay bekleniyor

Bu rapordaki tüm sayılar `snapshot_20261019T155113Z` anlık görüntüsünden ölçülmüştür:
- Birleşik SHA-256: `2fe1297c24f7aad761bca1dc3c04ec0de3459d297e06af20fbfe5e35ad10be5e`
- Ayrıntılı ölçümler: `reports/phase1/EDA_RAPORU.md` ve `reports/phase1/eda_summary.json`

---

## 1. Uygulananlar

| Alan | Uygulama |
|---|---|
| Depo iskeleti | `PROJECT_SPEC.md`, `README.md`, `.env.example`, `backend/`, `frontend/README.md`, `notebooks/`, `data/{raw,interim,processed,metadata}`, `reports/phase1/`, `docs/`, `scripts/` |
| Ortam | `backend/pyproject.toml` (hatchling, src düzeni); `uv` ile sanal ortam; `dev` ve `notebook` ekstraları |
| Git yoksayma kuralları | Ham, ara ve işlenmiş veri, sanal ortamlar, `.env`, derleme çıktıları, `.partial`/`.tmp`, defter kontrol noktaları. `data/metadata/` ve `.gitkeep` dosyaları izleniyor. |
| Kaynak kontrolü | `saferoute check-source`: erişilebilirlik, sürüm, sunucu sayımı ve kapsamı, beyan edilen sıklığa göre güncellik kararı, ilçe sınırı kaynağının erişilebilirliği |
| İndirme hattı | SODA API; `$order=:id` + `$limit/$offset`; 5 denemeli üstel geri çekilme; zaman aşımları; `.partial` → atomik yeniden adlandırma; sayfa bazlı şema ve satır denetimi; kaldığı yerden sürdürme; isteğe bağlı `X-App-Token` |
| Bütünlük | Parça bazlı ve birleşik SHA-256; indirme öncesi/sonrası sunucu sayımı, `rowsUpdatedAt` ve `Truth-Last-Modified` karşılaştırması; salt-okunur ham dosyalar; `saferoute verify` |
| Edinim kaydı | `saferoute record`: `full` / `partial` / `unverified` durumlu JSON (`data/metadata/`) |
| Parquet | `saferoute parquet`: kayıpsız, tamamı metin, zstd; yan kayıt; aynı kaynaktan yeniden yazmaz |
| Doğrulama modülü | Şema kontrolü (eksik/beklenmeyen sütun, sıra), boş girdi, eksik yüzdesi, tarih/saat ayrıştırma, ilçe etiketi sınıflandırma |
| Profil | Sütun genel bakışı (kaynak türü, ölçülen tür, eksik, benzersiz, aday kimlik), eksik değerler, kimlik/tekrar, zaman, koordinat sınıfları, ilçe ve ilçe × koordinat, yıllık kalite, yaralı/ölü ve tutarlılık, kategorik alanlar, metin alanları |
| Şekiller | 13 adet, Türkçe, gerçek veriden: yıllık, aylık, haftalık, saatlik, ilçe, ilçe × koordinat, eksik değer, koordinat sınıfları, mekânsal yoğunluk (tüm kayıtlar, örneklemesiz), yıllık kalite, araç türü, faktör, yaralı/ölü |
| Belgeler | Otomatik veri sözlüğü, kaynak bilgisi, veri kalitesi, özellik adayları ve 4 deney önerisi, karar günlüğü (K-01…K-10) |
| Defter | `notebooks/01_dataset_exploration.ipynb`: 15 bölüm, Türkçe, paket fonksiyonlarını kullanıyor, çalıştırılmış ve çıktıları kayıtlı |
| Otomasyon | `scripts/run_phase1.sh`, `scripts/run_phase1.ps1`, `scripts/execute_notebook.py` |

## 2. Gerçek satır sayısı

**2.269.187.** Sunucu tarafındaki `count(*)` ile indirme öncesinde ve sonrasında birebir eşleşiyor. Değer kodda sabit olarak yazılı değil; her indirmede ölçülüyor.

## 3. Gerçek sütun sayısı

**29.** Meta veri şeması ve CSV başlığı birebir aynı; beklenmeyen veya eksik sütun yok, sıra beklenenle aynı.

## 4. İndirme ve kaynak durumu

- **Edinim:** `full`, uyarı yok. 10 parça, 600.459.645 bayt CSV, yaklaşık 10 dakika (uygulama anahtarı olmadan).
- **Kaynak sürümü:** `rowsUpdatedAt` = 2026-06-15T23:05:47Z; indirme öncesi ve sonrası değişmedi.
- **Kapsam:** 2012-07-01 → 2026-06-11.
- **Güncellik:** Yayıncı **günlük** güncelleme beyan ediyor, ancak son satır güncellemesinin üzerinden **125 gün** geçmiş. `check-source` kararı **`stale`**: kaynak şu anda güncellenmiyor ve 2026-06-11 sonrasındaki kazalar veride yok.
- **Lisans:** Kaynak meta verisinde lisans alanı **boş**.
- **Parquet:** 53.707.718 bayt. Gerçek veride ham CSV ile birebir eşitliği doğrulandı (`DataFrame.equals` → `True`).

## 5. Eksik koordinat istatistikleri

Beş dışlayıcı sınıfın toplamı satır sayısına eşittir:

| Sınıf | Kayıt | Oran |
|---|---:|---:|
| Eksik (enlem veya boylam boş) | 240.806 | %10,61 |
| Ayrıştırılamaz | 0 | %0,00 |
| Sıfır (0,0) | 7.591 | %0,33 |
| NYC kutusu dışı | 150 | %0,01 |

- `latitude`, `longitude` ve `location` alanları her satırda birlikte dolu ya da birlikte boş; uyumsuzluk sayısı 0.
- Eksik koordinatlar **doldurulmadı**, ham kayıtlar korundu.

## 6. Geçerli koordinat sayısı

- **2.020.640 kayıt (%89,05).**
- Farklı konum sayısı 349.124; konum başına ortalama 5,8 kayıt düşüyor.
- Geçerli noktaların kapsamı: enlem 40,498947–40,912884, boylam −74,25496 – −73,70048.

## 7. İlçe dağılımı

| Kaydedilen ilçe | Kayıt | Bunların geçerli koordinatlı olanı |
|---|---:|---:|
| Brooklyn | 506.806 | 494.301 |
| Queens | 422.409 | 412.087 |
| Manhattan | 348.485 | 337.018 |
| Bronx | 234.088 | 226.052 |
| Staten Island | 66.024 | 64.156 |
| **Eksik** | **691.375 (%30,47)** | **487.026** |
| Beklenmeyen etiket | 0 | — |

- Beş ilçenin tamamı veride temsil ediliyor.
- Eksik ilçeli kayıtlar atılmadı.
- Kaba sınırlayıcı kutu ile ilçe ataması **yapılmadı**.
- İlçe sınırları için güvenilir kaynak belirlendi ve erişilebilirliği doğrulandı: DCP *Borough Boundaries* (`gthc-hcne`, sürüm 26b).

## 8. Başlıca özellik mühendisliği fırsatları (Faz 2)

1. **Geometrik ilçe:** Resmi poligonlarla `borough_inferred` türetilir. Hedef, koordinatı geçerli ama ilçesi boş 487.026 kayıt. Bildirilen ve çıkarılan ilçe ayrı sütunlarda tutulur ve uyuşma oranı raporlanır.
2. **Dışlama nedeni sütunu:** `coord_status` (eksik / sıfır / kutu dışı / poligon dışı / geçerli). Ham kayıt korunur.
3. **Zaman özellikleri:** Saat ve haftanın günü döngüsel kodlanır (sin/cos), yıl/ay çıkarılır. 00:00 yığılması `time_is_midnight_placeholder` ile işaretlenir; ölçüm, saat 0'ın dakika ortalamasının 19,4 katı.
4. **Kategori eşleme:** Araç türleri sınırlı bir sınıf kümesine indirilir (3.149 ham, 2.168 normalize değer). Faktörlerde `Unspecified` "bilinmiyor" olarak ele alınır (araç 1'de %33,34).
5. **Tutarlılık bayrakları:** Kişi toplamı ile yaya + bisikletli + motorlu toplamı arasındaki uyumsuzluklar işaretlenir (yaralıda 10.914, ölüde 84 kayıt).
6. **Benzersiz konum ağırlıklandırması:** 349.124 benzersiz konum `sample_weight` ile kullanılarak kümeleme maliyeti düşürülebilir. Kayıt düzeyiyle eşdeğerlik Faz 3'te doğrulanacak.
7. **Metrik projeksiyon:** K-Means için UTM 18N (EPSG:32618) dönüşümü.
8. **Metin normalizasyonu:** Sokak adlarında kırpma ve büyük harfe çevirme; `on_street_name` için farklı ham değer sayısı 23.332'den 14.669'a iniyor.

Sınıflandırma (A–E), gerekçeler ve Deney A–D: `docs/feature_candidates.md`.

## 9. Oluşturulan / değiştirilen dosyalar

**Kök:** `PROJECT_SPEC.md` (önceki `docs/MASTER_SPEC.md` taşındı), `README.md`, `.env.example`, `.gitignore` (güncellendi)

**Arka uç kaynak kodu** (`backend/src/saferoute/`):
- `config.py`, `cli.py`, `perf.py`
- `data/`: `source.py`, `download.py`, `loader.py`, `validate.py`, `metadata.py`, `convert.py`
- `eda/`: `profile.py`, `figures.py`, `report.py`, `dictionary.py`

**Testler** (`backend/tests/`): `conftest.py`, `test_download.py`, `test_loader.py`, `test_validate.py`, `test_profile.py`, `test_metadata_convert.py`, `test_report.py`

**Defter ve betikler:** `notebooks/01_dataset_exploration.ipynb`, `scripts/run_phase1.sh`, `scripts/run_phase1.ps1`, `scripts/execute_notebook.py`

**Belgeler:** `docs/data_dictionary.md` (otomatik), `docs/dataset_provenance.md`, `docs/data_quality.md`, `docs/feature_candidates.md`, `docs/decision_log.md`, `docs/phase1/TEKNIK_RAPOR.md`, `frontend/README.md`, `backend/README.md`

**Raporlar:** `reports/phase1/EDA_RAPORU.md`, `eda_summary.json`, `source_manifest.json`, `figures/` (13 PNG)

**Git'te izlenen veri kayıtları:** `data/metadata/acquisition_snapshot_20261019T155113Z.json`, `data/metadata/source_status_*.json`

**Git dışı veri:** `data/raw/h9gi-nx95/snapshot_20261019T155113Z/` (10 CSV + manifest, salt-okunur), `data/interim/.../crashes_raw_text.parquet`

## 10. Çalıştırılan testler ve sonuçları

| Doğrulama | Sonuç |
|---|---|
| `pytest` (ağ bağımsız, sentetik test verisi) | **60 passed** |
| `saferoute verify` (gerçek veri) | OK, 2.269.187 satır, 10 parça |
| Parquet = ham CSV (gerçek veri) | `True` |
| Defterin sırayla çalıştırılması (`execute_notebook.py`) | 20 kod hücresi hatasız (75–87 sn) |
| `scripts/run_phase1.sh` uçtan uca (indirme hariç, mevcut anlık görüntüyle) | Hatasız, 3 dk 9 sn |
| Profil iç tutarlılığı | Koordinat sınıfları ve ilçe × koordinat tablosu satır sayısına eşit (2.020.640 + 240.806 + 7.591 + 150 = 2.269.187) |

Testlerin kapsamı (şartname Görev 8):
- Şema işleme ve eksik/beklenmeyen sütun tespiti.
- Boş girdi.
- Kimlik tekrarı raporlama.
- Tarih ve saat ayrıştırma (var olmayan tarih, 24:00, 12:60 gibi uç durumlar dahil).
- Geçersiz koordinatlar (eksik, ayrıştırılamaz, sıfır, kutu dışı).
- İlçe etiketi doğrulama (küçük harf, boşluk, beklenmeyen etiket).
- Eksik yüzdesi (sıfıra bölme ve geçersiz sayımlar).
- Profil çıktısının değerleri ve JSON'a yazılabilirliği.
- İndirme bütünlüğü:
  - Yeniden deneme, kesinti ve sürdürme.
  - 4xx hatasında durma, şema değişikliğinin reddi.
  - Sayım uyuşmazlığının raporlanması.
  - Salt-okunur ham dosyalar, SHA-256 ile değişiklik tespiti.
  - Kısmi edinim kaydı.
- Parquet kopyasının kayıpsızlığı.
- Uçtan uca EDA ve CLI.

**Performans** (Windows 11, 16 mantıksal çekirdek, 15,2 GB RAM, Python 3.12.10, pandas 3.0.6, pyarrow 26.0.0):

| Adım | Süre | Bellek |
|---|---:|---:|
| İndirme | ~10 dk | — |
| Yükleme + SHA-256 doğrulama | 1,4–1,9 sn | DataFrame 677 MB; süreç tepe değeri ~1,0 GB |
| Parquet dönüşümü | ~7 sn | — |
| Parquet okuma | 0,73 sn | — |
| Profil | 57–66 sn | Süreç tepe değeri ~2,3 GB |
| Şekiller | 6–7 sn | — |

- Bellekte tek bir DataFrame tutuluyor.
- Tam ikili uzaklık hesabı yapılmadı.
- Hat tipik bir öğrenci bilgisayarında (≥ 4 GB RAM) çalışabilecek ölçekte.

## 11. Önemli sınırlılıklar

1. **Güncellik:** Kaynak 2026-06-15'ten beri güncellenmiyor (beyan edilen sıklık günlük).
2. **2026-06 kısmi ay:** Bu ay yalnızca 11 gün içeriyor. Kapsamın ilk ve son yılı da kısmi.
3. **Kaba sınır kontrolü:** Bu fazdaki sınır kontrolü bir dikdörtgendir; kutu içinde olup NYC dışında kalan noktalar "geçerli" sayılıyor.
4. **Raporlama kapsamı:** Veride yalnızca polise raporlanmış kazalar var. Yoğunluk maruziyete göre normalize edilmediği için **risk değildir**.
5. **Açıklanamayan kırılmalar:** 2016/2017 kalite kırılmasının ve 2020 sonrası düzey değişiminin nedeni bu veriyle belirlenemiyor.
6. **Lisans:** Kaynak meta verisinde lisans alanı boş; kullanım koşulları akademik raporda ayrıca doğrulanmalı.
7. **Tekrar üretilebilirlik sınırı:** Yeni bir indirme, kaynak güncellendiyse farklı bir anlık görüntü üretir. Sonuçlar yukarıdaki SHA-256 değerine bağlıdır.
8. **Bellek ölçümü:** Tepe değerleri tek bir makinede ölçüldü; diğer platformlarda farklılık gösterebilir.
9. **API dokümantasyonu:** İncelenen Socrata sayfası sıralama şartından açıkça söz etmiyor. `$order=:id` tasarım kararıdır (K-02); doğruluğu sayım eşleşmesiyle desteklendi.

## 12. Faz 2 için önerilen adımlar

1. DCP *Borough Boundaries* (`gthc-hcne`) poligonlarını sürüm ve SHA-256 kaydıyla indirmek.
2. `crashes_raw_text.parquet` dosyasından tür dönüşümlü bir ara katman (`data/processed/`) oluşturmak. Her dönüşüm testli ve belgeli olacak.
3. Kesin coğrafi geçerlilik (poligon içi/dışı) ve `borough_inferred` + uyuşma oranı (bkz. `feature_candidates.md` §4).
4. Dışlama kuralları: her kural için neden sütunu ve sayım tablosu; ham veri değişmeden kalacak.
5. 00:00 saat bayrağı, yaralı/ölü tutarsızlık bayrakları, araç türü/faktör eşleme tabloları (belgeli CSV/YAML).
6. Döngüsel zaman kodlaması ve EPSG:32618 projeksiyonu.
7. Özellik seçiminin son hâli ve gerekçesi; Faz 3 deney konfigürasyon şeması.
8. Faz 2 testleri, raporu ve kabul listesi.

---

## Kabul ölçütleri

| Ölçüt | Durum |
|---|---|
| Gerçek kaynak verisi alındı | ✅ 2.269.187 satır, `full` |
| Veri kökeni kaydedildi | ✅ Manifest, edinim kaydı, `dataset_provenance.md` |
| Gerçek satır/sütun sayıları hesaplandı | ✅ 2.269.187 / 29 |
| Profil sonuçları tutarlı | ✅ Sınıf toplamları satır sayısına eşit; defter ve rapor aynı değerleri veriyor |
| Beş ilçe kapsamı analiz edildi | ✅ Eksik ve beklenmeyen etiketler ile ilçe × koordinat tablosu dahil |
| Akademik EDA şekilleri üretildi | ✅ 13 şekil |
| Defter hatasız çalışıyor | ✅ 20/20 kod hücresi |
| Otomatik testler geçiyor | ✅ 60/60 |
| Çıktılar belgelenmiş komutlarla yeniden üretilebiliyor | ✅ `scripts/run_phase1.{sh,ps1}`, README |
| Sahte üretim verisi yok | ✅ Sentetik veri yalnızca `backend/tests/` içinde |
| Faz 2–7 uygulanmadı | ✅ Temizleme, özellik dönüşümü, model eğitimi ve ön yüz yok |
