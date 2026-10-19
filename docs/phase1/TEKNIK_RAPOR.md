# Faz 1 Teknik Raporu — Veri Seti Temeli ve Keşifsel Veri Analizi

**Proje:** SafeRoute 3D  
**Faz:** 1 / 7  
**Tarih:** 2026-10-19  
**Durum:** Tamamlandı, onay bekliyor

Bu rapordaki tüm sayılar, aşağıda kimliği verilen ham anlık görüntüden `saferoute eda` komutuyla ölçülmüştür. Ayrıntılı tablolar ve şekiller `reports/phase1/EDA_RAPORU.md` dosyasında, makine-okur hâli `reports/phase1/eda_summary.json` dosyasındadır.

---

## 1. Kapsam

Faz 1'in amacı şunlardır:

1. Resmi kaynaktan gerçek veriyi izlenebilir ve değişmez biçimde elde etmek.
2. Verinin yapısını, kalitesini ve sınırlılıklarını ölçmek.

Bu fazda veri temizlenmez, dönüştürülmez ve modellenmez. Bunlar Faz 2 ve 3'ün konusudur.

## 2. Veri kaynağı ve anlık görüntü kimliği

| Alan | Değer |
|---|---|
| Veri seti | Motor Vehicle Collisions - Crashes (`h9gi-nx95`) |
| Yayıncı / atıf | NYC Open Data, Police Department (NYPD) |
| Kaynak sayfa | https://data.cityofnewyork.us/d/h9gi-nx95 |
| Katalog | https://catalog.data.gov/dataset/motor-vehicle-collisions-crashes |
| Anlık görüntü | `data/raw/h9gi-nx95/snapshot_20261019T155113Z/` |
| İndirme (UTC) | 2026-10-19 15:51:15 → 16:01:15 (yaklaşık 10 dk) |
| Kaynak sürümü (`rowsUpdatedAt`) | 2026-06-15T23:05:47Z (indirme öncesi ve sonrası aynı) |
| `X-SODA2-Truth-Last-Modified` | Tüm sayfalarda tek değer: Mon, 15 Jun 2026 23:05:52 GMT |
| Satır / sütun | 2.269.187 / 29 |
| Sunucu sayımı | 2.269.187 (indirme öncesi ve sonrası; birebir eşleşme) |
| Tarih kapsamı | 2012-07-01 → 2026-06-11 |
| Birleşik SHA-256 | `2fe1297c24f7aad761bca1dc3c04ec0de3459d297e06af20fbfe5e35ad10be5e` |
| Manifest durumu | `complete`, uyarı yok |
| Lisans alanı | Socrata meta verisinde **boş**. NYC Open Data kullanım koşulları akademik raporda ayrıca belirtilmelidir. |

### İndirme yöntemi

- Socrata SODA 2.x CSV uç noktası kullanıldı. Sıralama `$order=:id`, sayfalama `$limit=250000` / `$offset` ile yapıldı.
- Sıralama `collision_id` yerine sistem kimliği `:id` ile yapıldı. Böylece kimlik tekrarları olsa bile sayfa sınırında satır atlanmaz.
- Sayfalar önce `.partial` dosyasına yazılıyor. Başlık şema denetiminden ve satır sayımından geçen sayfa atomik olarak `part-NNNNN.csv` adını alıyor.
- Geçici hatalarda (HTTP 408/429/5xx, bağlantı kopması, akış kesilmesi) üstel geri çekilmeyle en çok 5 deneme yapılır.
  - 4xx hataları ve şema değişikliği yeniden denenmez; işlem hatayla durur.
  - Yarım kalan indirme, `_progress.json` dosyası aracılığıyla `--resume` ile kaldığı sayfadan sürdürülür.
- Tutarlılık için indirme öncesinde ve sonrasında üç şey karşılaştırılır: `rowsUpdatedAt`, sunucu sayımı ve her sayfanın `Truth-Last-Modified` başlığı. Bu indirmede üçü de eşleşti.
- Ham veri değişmezdir:
  - Parça dosyaları ve manifest salt-okunur yapılır.
  - Her yüklemede SHA-256 değerleri yeniden doğrulanır (`saferoute verify`).
  - Ham veri git'e girmez (`data/` yoksayılır). Kimliği `reports/phase1/source_manifest.json` dosyasıyla depoda izlenir.

## 3. Veri güncelliği (açık sınırlılık)

- Yayıncı **günlük** güncelleme beyan ediyor. Buna karşın son satır güncellemesi **2026-06-15** tarihinde.
- İndirme tarihinde kaynak **125 gündür güncellenmemiş**. En son kaza tarihi (2026-06-11) indirmeden 130 gün önce.
- Sonuç: Haziran 2026 sonrasındaki kazalar bu anlık görüntüde **yoktur**. Uygulama, veri güncelliğini kullanıcıya bu tarihlerle göstermelidir.
- 2026-06 ayı **kısmidir**: yalnızca 11 gün kapsanıyor, 2.322 kayıt var.
  - Önceki yılın aynı ayına oranı 0,31. 11/30 gün kapsamdan beklenebilecek kaba oran ise yaklaşık 0,37.
  - Bu ay, yıllık karşılaştırmalarda tam ay gibi kullanılmamalıdır.
- 2026'nın Ocak–Mayıs ayları, önceki yılın aynı aylarıyla 0,96–1,08 oranında. Bu oranlar belirgin bir raporlama gecikmesine işaret etmiyor; ancak gecikmenin olmadığını da kanıtlamaz.

## 4. Temel bulgular

### 4.1 Bütünlük ve kimlikler

- `collision_id` 2.269.187 satırın tamamında dolu, tam sayı ve **benzersiz**. Tüm sütunları birebir aynı olan tekrar satır yok.
- `crash_date` ve `crash_time` hiçbir satırda eksik veya ayrıştırılamaz değil.
  - `crash_date` değerlerinin saat bileşeni her zaman 00:00. Saat bilgisi yalnızca `crash_time` alanında bulunuyor.

### 4.2 Koordinatlar

Koordinatlar birbirini dışlayan beş sınıfa ayrıldı (toplamları satır sayısına eşit):

| Sınıf | Kayıt | Oran |
|---|---:|---:|
| Eksik | 240.806 | %10,61 |
| Ayrıştırılamaz | 0 | %0,00 |
| Sıfır (0,0) | 7.591 | %0,33 |
| NYC kutusu dışı | 150 | %0,01 |
| **Geçerli (kutu içi)** | **2.020.640** | **%89,05** |

- `latitude`, `longitude` ve `location` alanları her satırda birlikte dolu ya da birlikte boş. `location` bilgi taşımayan, tekrarlanmış bir coğrafi temsildir; spec §5 gereği model dışı bırakılmalıdır.
- **Koordinat tekrarı yüksek.** 2.020.640 geçerli noktada yalnızca 349.124 farklı (enlem, boylam) çifti var. Kazaların büyük kısmı aynı noktalara, büyük olasılıkla kavşak merkezlerine, kodlanmış görünüyor. Bu durumun Faz 3'e iki sonucu var:
  - Aynı noktada üst üste binen kayıtlar DBSCAN'in `min_samples` yorumunu doğrudan etkiler.
  - Benzersiz noktalar `sample_weight` ile ağırlıklandırılırsa hesaplama yükü büyük ölçüde azaltılabilir. Bu yöntemin tam kayıt düzeyiyle eşdeğerliği Faz 3'te ayrıca doğrulanmalıdır.
- Sınırlayıcı kutu kaba bir kontroldür. Kutu New Jersey'nin bazı kısımlarını ve su alanlarını da kapsar. Yoğunluk haritasında kara sınırı dışına düşen tekil noktalar görülüyor; gerçek sınır kontrolü Faz 2'de ilçe poligonlarıyla yapılacak.

### 4.3 İlçe (borough) alanı

- İlçe alanı **%30,47 oranında boş** (691.375 kayıt).
- Bunların **487.026'sının koordinatı geçerli**. Bu kayıtların ilçesi, spec §2'deki "geometrik olarak çıkarılan ilçe" ile kurtarılabilir. Bu zenginleştirme Faz 2'nin ana işidir; raporlanan ve çıkarılan ilçe ayrı sütunlarda tutulmalıdır.
- Dolu değerlerin hepsi beklenen beş ilçeden biri, beklenmeyen değer yok. Dağılım: Brooklyn 506.806, Queens 422.409, Manhattan 348.485, Bronx 234.088, Staten Island 66.024.
- 44.198 kaydın ilçesi dolu ama koordinatı kullanılamaz. Bu kayıtlar ilçe düzeyi özetlerde kullanılabilir, mekânsal kümelemede kullanılamaz.

### 4.4 Zamana göre veri kalitesi

- Geçerli koordinat oranı 2012–2016 arasında %83,6–85,0 düzeyinde. 2017'de %93,90'a sıçrıyor ve sonraki yıllarda %89,6–96,9 arasında kalıyor.
- İlçe doluluğu 2015'te %75,09 iken 2017'de %61,88'e düşüyor, 2025'te %80,09'a çıkıyor.
- Bu değişimler kayıt ya da coğrafi kodlama sürecindeki bir değişikliğe işaret edebilir. **Nedeni bu veriyle belirlenemez.** Yıllar arası karşılaştırmalarda kalite farkı göz önünde tutulmalıdır.

### 4.5 Zamansal dağılım

- Yıllık kayıt sayısı 2017–2018'de yaklaşık 231 bindi. 2019'da 211.486'ya, 2020'de 112.918'e indi.
- Aylık seride düşüş Mart–Nisan 2020'de keskinleşiyor: Şubat'ta 13.704, Mart'ta 11.079, Nisan'da 4.129 kayıt. Zamanlama COVID-19 dönemiyle örtüşüyor, ancak bu veri nedensellik kurmaya yetmez.
- Sonraki yıllarda seri 2019 öncesi düzeye dönmüyor: 2025'te 85.546 kayıt var.
- 2012 yılı yalnızca Temmuz–Aralık aylarını kapsıyor, 2026 yılı ise Ocak–11 Haziran'ı. Bu iki yıl tam yıl karşılaştırmalarına katılmamalıdır.
- **Gece yarısı yığılması:** 24.566 kayıt (%1,08) saat 00:00 olarak girilmiş.
  - Saat 0'daki toplam kayıt 75.806. Bu, dakika başına ortalama yaklaşık 1.263 kayıt demektir.
  - 00:00 dakikası bu ortalamanın yaklaşık 19 katı. Saat bilinmediğinde 00:00 girilmesi olasıdır.
  - Faz 2'de bu kayıtlar zaman filtrelerinde ayrıca işaretlenmelidir.

### 4.6 Yaralanma ve ölümler

- Toplamda 756.353 yaralanma ve 3.617 ölüm var. 558.603 kayıtta en az bir yaralı, 3.469 kayıtta en az bir ölü bulunuyor.
- `number_of_persons_killed` 8.913 kayıtta eksik, `number_of_persons_injured` 18 kayıtta eksik. Alt kırılım sütunlarında eksik yok. Negatif değer ya da ayrıştırılamaz değer yok.
- **İç tutarlılık** (kişi = yaya + bisikletli + motorlu):
  - Yaralılarda 2.269.169 karşılaştırılabilir kaydın 10.687'sinde kişi toplamı alt kırılımdan büyük, 227'sinde küçük.
  - Ölülerde 78 kayıtta büyük, 6 kayıtta küçük.
  - Faz 2'de bu kayıtlar düzeltilmeyecek, yalnızca işaretlenecek. Hangi sütunun esas alınacağı belgelenecek.

### 4.7 Kategorik alanlar

- Katkıda bulunan faktör (araç 1) kayıtların %33,34'ünde "Unspecified" (756.643 kayıt), 8.202 kayıtta boş. 5 faktör sütununda toplam 66 farklı değer var.
- **Araç türü alanı çok dağınık:**
  - Ham hâliyle 3.149 farklı değer var; büyük harfe çevirip boşlukları kırpınca 2.168'e iniyor.
  - Farklı adlandırma şemaları bir arada kullanılıyor: "Sedan" / "4 dr sedan" / "PASSENGER VEHICLE", "Taxi" / "TAXI".
  - Filtreleme için Faz 2'de belgelenmiş bir kategori eşleme tablosu gerekiyor.
- Kayıtların 1.648.247'sinde iki araç türü dolu; 17.081 kayıtta hiçbiri dolu değil.
- Sokak adı alanlarında doldurma boşlukları çok yaygın (`on_street_name` alanında 1.412.004 kayıt). Normalizasyon farklı değer sayısını 23.332'den 14.669'a düşürüyor.
- Posta kodu %30,48 oranında eksik. Dolu olanların hepsi 5 haneli.

## 5. Ölçülen performans

| Adım | Süre | Not |
|---|---:|---|
| İndirme (10 sayfa, yaklaşık 600 MB CSV) | yaklaşık 10 dk | Uygulama anahtarı olmadan, tek bağlantıyla |
| Ham yükleme + SHA-256 doğrulama | 1,5 sn | pyarrow CSV okuyucu |
| Profil çıkarma | 30–43 sn | Üç ayrı koşuda ölçüldü |
| Şekiller dahil toplam | 36–51 sn | |
| Bellek: DataFrame | 677 MB | Arrow metin sütunları |
| Bellek: süreç tepe değeri | 2.277 MB | Windows PeakWorkingSet ölçümü |

Ortam: Windows 11, Python 3.12.10, pandas 3.0.6, pyarrow 26.0.0, NumPy 2.5.4, matplotlib 3.11.2, requests 2.34.2.

Python `tracemalloc` ile bellek izlendiğinde profil süresi 349 saniyeye çıktı. Bu nedenle bellek izleme isteğe bağlı yapıldı (`--trace-memory`). Süre ölçümleri izleme kapalıyken alındı.

## 6. Kod ve testler

```
backend/
  pyproject.toml
  src/saferoute/
    config.py            Sabitler, yollar, NYC sınırlayıcı kutusu
    cli.py               saferoute download | verify | eda
    data/source.py       Meta veri ve sunucu tarafı sayım
    data/download.py     Sayfalı, yeniden denemeli, sürdürülebilir indirme ve manifest
    data/loader.py       Bütünlük doğrulamalı ham yükleme
    eda/profile.py       Ölçüm fonksiyonları (veriyi değiştirmez)
    eda/figures.py       Şekiller
    eda/report.py        JSON ve Markdown raporları
  tests/                 30 test, ağ gerektirmez
reports/phase1/          EDA_RAPORU.md, eda_summary.json, source_manifest.json, figures/
docs/MASTER_SPEC.md      Proje şartnamesi
```

**Test sonucu:** `30 passed`. Testlerin kapsadığı başlıca davranışlar:

- **İndirme:** Sayfalama ve tam katlı sayfa sınırı.
- **Hata yönetimi:**
  - 503, bağlantı ve akış kopması hatalarında yeniden deneme ve geri çekilme süreleri.
  - Denemeler tükenince sürdürülebilir durumun korunması ve kaldığı yerden devam.
  - 4xx hatasında yeniden denenmemesi.
  - Şema değişikliğinin reddi.
- **Bütünlük:**
  - Sunucu sayımı uyuşmazlığının raporlanması.
  - Tamamlanmış anlık görüntünün üzerine yazılmaması ve salt-okunur dosyalar.
  - SHA-256 ile değişiklik tespiti.
- **Yükleme:**
  - "NA" ve "NULL" metinlerinin veri olarak korunması.
  - Tırnak içinde satır sonu bulunan alanlar.
- **Profil:** Kusurları bilinen 7 satırlık örnekte her ölçümün birebir doğrulanması.
- **Uçtan uca:** EDA koşusu ve CLI.

**Yeniden üretim:**

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]" --python .venv/Scripts/python.exe
.venv/Scripts/saferoute download && .venv/Scripts/saferoute verify && .venv/Scripts/saferoute eda
.venv/Scripts/python.exe -m pytest
```

Not: Yeni bir indirme, kaynak o arada güncellenmişse farklı bir anlık görüntü üretir. Bu rapordaki sonuçları birebir yeniden üretmek için yukarıdaki SHA-256 değerine sahip anlık görüntü kullanılmalıdır.

## 7. Bilinen sınırlılıklar

1. **Veri güncelliği:** Kaynak 2026-06-15'ten beri güncellenmemiş, bu tarihten sonraki kazalar yok (§3).
2. **Coğrafi sınır kontrolü kaba:** Dikdörtgen kutu kullanıldığı için kutu içinde olup NYC dışında kalan noktalar "geçerli" sayılıyor. İlçe poligonlarıyla kontrol Faz 2'de yapılacak.
3. **Kayıt kapsamı:** Veri yalnızca polise raporlanmış kazaları içerir. Yoğunluk, maruziyete (trafik hacmi, yaya sayısı) göre normalize edilmediği sürece **risk anlamına gelmez**.
4. **Zamana bağlı kalite farkları:** 2016/2017 civarındaki doluluk değişimlerinin nedeni bilinmiyor (§4.4).
5. **Tek kaynaklı indirme:** Anlık görüntü SODA API'nin o anki durumunu yansıtır. NYPD'nin geriye dönük düzeltmeleri sonraki anlık görüntülerde farklılık yaratabilir.
6. **Bellek ölçümü:** Tepe değeri Windows'a özgü bir yöntemle, yalnızca bir koşuda ölçüldü.
7. **Lisans:** Kaynak meta verisinde lisans alanı boş. Kullanım koşulları akademik raporda ayrıca doğrulanıp atıfla belirtilmelidir.

## 8. Faz 2'ye aktarılan girdiler (bu fazda uygulanmadı)

- İlçe poligonlarıyla geometrik ilçe çıkarımı. Hedef: koordinatı geçerli ama ilçesi boş 487.026 kayıt. Raporlanan ve çıkarılan ilçe ayrı tutulacak.
- Kesin sınır kontrolü ve kutu içi/NYC dışı noktaların dışlanması; dışlama nedenleri ve sayıları kaydedilecek.
- 00:00 saat yığılmasının işaretlenmesi.
- Araç türü ve faktör kategorilerinin eşlenmesi; "Unspecified" değerinin ayrı ele alınması.
- Yaralı/ölü tutarsızlıklarının işaretlenmesi.
- Metin alanlarının normalizasyonu.
- `location`, `collision_id` ve sokak adlarının model özelliklerinden dışlanma gerekçesi.
- Parquet ara veri formatı.

## 9. Kabul kontrol listesi

| # | Ölçüt (spec §3, §5, §12) | Durum |
|---|---|---|
| 1 | Gerçek kaynak verisi indirildi; sahte kayıt yok | ✅ 2.269.187 satır |
| 2 | Kaynak URL, indirme zamanı, sürüm, satır/sütun, kapsam, sağlama toplamı kaydedildi | ✅ `manifest.json` |
| 3 | Güncelleme durumu kontrol edildi, güncellik sınırlılığı açıkça belirtildi | ✅ §3 |
| 4 | Ham veri değişmez biçimde korunuyor | ✅ Salt-okunur + SHA-256 doğrulaması |
| 5 | Sayfalama, yeniden deneme, yarım indirme ve hata yönetimi | ✅ Test edildi |
| 6 | Eksik değerler uydurulmadı, doldurulmadı | ✅ Yalnızca ölçüm yapıldı |
| 7 | Eksik değer denetimi | ✅ |
| 8 | Kimlik tekrarı incelemesi | ✅ |
| 9 | Koordinat doğrulama ve (kaba) sınır kontrolü | ✅ Poligon kontrolü Faz 2'ye bırakıldı |
| 10 | Tarih/saat ayrıştırma ve geçersiz değer tespiti | ✅ |
| 11 | Otomatik testler | ✅ 30/30 geçti |
| 12 | Dokümantasyon, ölçülen sonuçlar, bilinen sınırlılıklar | ✅ Bu rapor + EDA raporu |
| 13 | Sonraki faz öğeleri uygulanmadı | ✅ Temizleme, özellik mühendisliği ve modelleme yok |
| 14 | Doğrulama sonrası git commit | ✅ |
