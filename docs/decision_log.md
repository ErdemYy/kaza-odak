# Karar Günlüğü

Her kararda dört bilgi kaydedilir: bağlam, karar, gerekçe ve değerlendirilen alternatifler. Kararlar ancak yeni bir kayıtla değiştirilebilir; eski kayıt silinmez.

---

### K-01 — Edinim yöntemi: SODA API ile sayfalı CSV (2026-10-19, Faz 1)
- **Bağlam:** Yaklaşık 2,27 milyon satır (yaklaşık 600 MB CSV) var. İndirmenin yeniden denenebilir ve sürdürülebilir olması gerekiyor.
- **Karar:** `/resource/h9gi-nx95.csv` uç noktası 250.000 satırlık sayfalarla indirilir. Her sayfa ayrı dosyaya yazılır ve SHA-256 değeri kaydedilir.
- **Gerekçe:**
  - Hata halinde yalnızca başarısız sayfa yeniden indirilir ve kalınan sayfadan devam edilebilir.
  - Sayfa bazlı şema ve satır sayısı denetimi yapılabilir.
  - Belgelenmiş bir API mekanizmasıdır.
- **Alternatif:** Tek parça toplu dışa aktarma (`/api/views/.../rows.csv`). Daha basit, ama kopmada baştan başlamak gerekir ve ara doğrulama yoktur.

### K-02 — Sıralama: `$order=:id` (2026-10-19, Faz 1)
- **Bağlam:** Offset sayfalaması kararlı bir sıralama gerektirir. İncelenen Socrata dokümanında bu konuda açık bir ifade bulunamadı.
- **Karar:** Sistem kimliği `:id` ile sıralanır.
- **Gerekçe:** `collision_id` tekrar etseydi, `collision_id` ile anahtar-tabanlı sayfalama sayfa sınırındaki satırları atlayabilirdi. `:id` her satır için benzersizdir. (Ölçümde `collision_id` de benzersiz çıktı, ancak tasarım bu varsayıma dayanmıyor.)
- **Doğrulama:** İndirilen satır sayısı, indirme öncesi ve sonrası sunucu sayımıyla birebir eşleşti (2.269.187).

### K-03 — Ham veri her zaman metin olarak yüklenir (2026-10-19, Faz 1)
- **Karar:** Tüm sütunlar `string` türünde okunur. Yalnızca boş CSV alanları null sayılır; `"NA"` ve `"NULL"` gibi metinler veri olarak korunur.
- **Gerekçe:** Erken tür dönüşümü ayrıştırılamayan değerleri sessizce NaN'a çevirir. Böylece "eksik" ile "geçersiz" ayırt edilemez ve şartnamedeki "geçersiz değer tespiti" gereği karşılanamaz.

### K-04 — Ham verinin değişmezliği (2026-10-19, Faz 1)
- **Karar:**
  - Tamamlanan anlık görüntüdeki parça dosyaları ve manifest salt-okunur yapılır.
  - Tamamlanmış bir anlık görüntü yeniden yazılmaz.
  - Her yüklemede SHA-256 doğrulaması yapılır.
  - Ham veri git'e girmez; tanımlayıcı kayıtları (`data/metadata/`) git'e girer.
- **Alternatif:** Ham veriyi Git LFS ile depolamak. Reddedildi: 600 MB'lık veri yeniden indirilebilir ve kimliği SHA-256 ile sabitlenmiş durumda.

### K-05 — Parquet kopyası kayıpsız ve tamamı metin (2026-10-19, Faz 1)
- **Karar:** `data/interim/` altında, ham veriyle birebir aynı içerikli, zstd sıkıştırmalı ve tamamı string türünde bir Parquet kopyası tutulur.
- **Gerekçe:**
  - Tür dönüşümü ve temizlik Faz 2'nin işidir. Bu kopya yalnızca hızlı, sütun-seçmeli okuma sağlar: 0,73 sn'ye karşı CSV 1,58 sn; 53,7 MB'a karşı 600 MB.
  - Ham CSV ile birebir eşitliği gerçek veride doğrulandı.

### K-06 — Koordinat geçerliliği: dışlayıcı sınıflar ve kaba kutu (2026-10-19, Faz 1)
- **Karar:** Koordinatlar beş dışlayıcı sınıfa ayrılır (eksik, ayrıştırılamaz, sıfır, kutu dışı, geçerli). Kutu yalnızca kaba bir geçerlilik testidir.
- **Gerekçe:** Şartname, ilçe üyeliğinin kaba kutularla sessizce atanmasını yasaklıyor. Kesin kontrol için resmi poligonlar (`gthc-hcne`) Faz 2'de kullanılacak.

### K-07 — Eksik değerler bu fazda doldurulmaz (2026-10-19, Faz 1)
- **Karar:** Faz 1 yalnızca ölçüm yapar. Faz 2'deki dışlamalar da ham veriyi değiştirmeyecek: bir neden sütunu ve sayımlarla, türetilmiş veri üzerinde yapılacak.

### K-08 — Depo yapısında şartname örneğinden farklar (2026-10-19, Faz 1)
- `analysis/eda.py` yerine `saferoute/eda/` paketi kullanıldı (`profile`, `figures`, `report`, `dictionary`). Ölçüm, çizim ve raporlama ayrı ayrı test edilebiliyor.
- `data/profile.py` yerine profil `eda/profile.py` içinde; `data/` paketi edinim, doğrulama ve yükleme ile sınırlı tutuldu.
- `data/metadata.py` mevcut: kaynak durumu ve edinim kaydı. Bunlara ek olarak `source.py` (HTTP erişimi), `loader.py` (yükleme) ve `convert.py` (Parquet) var.
- Şekiller `reports/figures/` yerine `reports/phase1/figures/` altında: her fazın çıktıları kendi dizininde.

### K-09 — Performans ölçümü: süreç bellek tepe değeri (2026-10-19, Faz 1)
- **Karar:** Bellek, işletim sistemi düzeyinde süreç tepe değeri olarak ölçülür (Windows `PeakWorkingSetSize`, Unix `ru_maxrss`).
- **Gerekçe:** İlk denemede Python `tracemalloc` ile ölçüm yapıldı. Bu yöntem profil süresini yaklaşık 43 sn'den 349 sn'ye çıkardı ve Arrow arabelleklerini kapsamıyordu, bu yüzden bırakıldı.

### K-10 — Defterde elle yazılmış istatistik yok (2026-10-19, Faz 1)
- **Karar:** Defterdeki markdown hücreleri yalnızca yöntem ve yorum içerir. Tüm sayılar kod hücresi çıktılarında, `saferoute` paketinin fonksiyonlarıyla hesaplanır.
- **Gerekçe:** Anlık görüntü değişirse metindeki sayılar eskimez. Ayrıca iş mantığı defterde tekrar edilmez.

---

## Faz 2 kararları

### K-11 — Katman yapısı ve idempotentlik (2026-10-19, Faz 2)
- **Karar:** `raw → interim → processed → features` katmanları kullanılır. Her Parquet dosyasının yanında bir yan kayıt (sidecar) bulunur: kaynak SHA-256, ilçe sınırı SHA-256, yapılandırma ve özeti, hat sürümü, satır/sütun sayısı, dosya SHA-256 ve içerik özeti.
- **Atlama koşulu:** Bu kimlik bilgileri değişmediyse ve dosya özetleri doğrulanıyorsa hat atlanır.
- **Doğrulama:** `--force` ile yeniden üretilen çıktının içerik özeti öncekiyle aynı çıkar; bu testle doğrulandı.

### K-12 — İlçe çıkarımında yüklem: `covered_by` (intersects) ve belirsizlik politikası (2026-10-19, Faz 2)
- **Karar:** Bir nokta tam olarak tek bir ilçe poligonunu kapsıyorsa (iç veya sınır, `intersects_xy`) o ilçe atanır.
- **Belirsiz ve dış noktalar:** İki veya daha fazla ilçeyle kesişen nokta `boundary_ambiguous` olur ve atama yapılmaz. Poligon dışındaki noktalar, kıyıya yakın olsalar bile, **hiçbir ilçeye atanmaz**.
- **Ölçüm:** Gerçek veride 349.140 benzersiz noktada `intersects` ve `contains` sonuçları aynı çıktı; sınır çizgisi üstünde ya da birden fazla ilçede nokta yok. Yüklem seçimi bu veride sonucu değiştirmiyor; politika yine de testlerle sabitlendi.

### K-13 — Kıyıya yakınlık tamponu 500 m (2026-10-19, Faz 2)
- **Bağlam:** Resmî poligonlar su alanlarını hariç tutar. Köprü ve kıyı yolu kazaları poligon dışında kalır; en çok tekrarlanan konumlar arasında Verrazzano (887 kaza) ve Whitestone (477) köprüleri var.
- **Karar:** Poligon dışında ve NYC karasına en fazla 500 m uzaklıktaki noktalar `outside_nyc_nearshore` olarak sınıflanır. Bu noktalar geçerli coğrafi kayıttır ve kümelemeye alınır, ama ilçeleri atanmaz.
- **Gerekçe:** Gerçek mesafe dağılımında 500–1000 m arasında hiç nokta yok; bu doğal bir kırılma. Uzak kalan 46 kayıt ise yaklaşık 3.600 km'ye kadar uzanıyor.
- **Esneklik:** `clustering_include_nearshore` ayarıyla bu noktalar kümelemeden çıkarılabilir; bu davranış test edildi.

### K-14 — Eksik değer doldurma yapılmaz (2026-10-19, Faz 2)
- **Karar:** Koordinat, saat, ilçe ve yaralı/ölü değerleri **doldurulmaz**. İlçe yalnızca resmî poligondan çıkarılır. Diğer eksikler bayrakla işaretlenir veya gerekçesiyle dışlanır.
- **Gerekçe:** Uydurulan bir konum ya da saat, yoğunluk tabanlı kümelemede gerçekte olmayan yoğunluklar üretir.

### K-15 — Bildirilen ilçe çelişkide korunur (2026-10-19, Faz 2)
- **Karar:** `borough_final` alanı bildirilen değeri, yoksa poligonla çıkarılan değeri taşır. Çelişki durumunda bildirilen değer korunur ve `borough_conflict_flag` işaretlenir.
- **Gerekçe:** Çelişkilerin bir kısmında koordinatın kendisi hatalı (bkz. K-16), bir kısmında ise idari ilçe coğrafi ilçeden farklı (Marble Hill). Kaynağın hangisinin doğru olduğu kayıt düzeyinde bilinemez; bu yüzden sessiz düzeltme yapılmaz.

### K-16 — Yedek geokodlama şüphesi bayrağı (2026-10-19, Faz 2)
- **Bulgu:** Bazı tekil koordinatlarda beş farklı ilçeden bildirilmiş kazalar var. Örneğin 40.7136, −74.0091 noktasında 192 kayıt bulunuyor ve hepsi 2016 yılına ait. Tek bir fiziksel nokta en fazla iki ilçenin ortak sınırında olabilir.
- **Karar:** Aynı koordinatta en az 3 farklı bildirilmiş ilçe varsa `geocode_fallback_suspect_flag` işaretlenir: 15 konum, 1.844 kayıt.
- **Kapsam:** Kayıtlar silinmez ve kümeleme uygunluğundan çıkarılmaz. Faz 3'te bu kayıtlarla ve onlarsız duyarlılık analizi yapılacak.

### K-17 — 00:00 kayıtları: bayrak, dönüşüm yok (2026-10-19, Faz 2)
- **Bulgu:** Tüm saatlerde tam saate yuvarlama alışkanlığı var; diğer saatlerin HH:00 oranının medyanı 13,3. 00:00'da bu oran 28,3.
- **Karar:** Kesin 00:00 kayıtları `midnight_suspect_flag` ile işaretlenir; kayıtlar silinmez ve saatleri değiştirilmez.
- **Kapsam:** Zaman kullanmayan A, B ve C modelleri bu bayraktan etkilenmez. D modeli için 00:00 hariç bir duyarlılık seti ayrıca üretildi.

### K-18 — Araç türü eşlemesi: sıralı açık kurallar, zorla atama yok (2026-10-19, Faz 2)
- **Karar:** Etiketler önce normalize edilir: kırpma, boşluk tekleme, büyük harf.
- **Kurallar:** 15 sıralı düzenli ifade kuralı uygulanır ve ilk eşleşen kazanır. Hiçbir kurala uymayan etiket `OTHER/unmatched` olarak tutulur ve ayrıca raporlanır.
- **Sonuç:** 3.149 ham etiket → 2.165 normalize etiket → 12 kategori. Eşleşmeyen etiket sayısı 1.473; bunlar etiket geçişlerinin yalnızca %0,14'ü.
- Tam tablo `reports/phase2/vehicle_type_mapping.csv` dosyasında.

### K-19 — Koordinat temsilleri ve ölçekleme yok (2026-10-19, Faz 2)
- **Karar:**
  - A ve C modelleri: `[lat_rad, lon_rad]` (scikit-learn haversine sırası).
  - B modeli: EPSG:32618 `[x_m, y_m]`.
  - Standartlaştırma (z-skoru) uygulanmaz.
- **Doğrulama** (WGS84 jeodezik mesafeye göre):
  - UTM hatası: medyan %0,030.
  - Haversine'in küre yaklaşımı hatası: medyan %0,11.
  - Bu, 100 m'lik `eps` için yaklaşık 0,1 m demek; ihmal edilebilir.

### K-20 — Ağırlıklı benzersiz konum temsili (2026-10-19, Faz 2)
- **Karar:** A ve B modelleri için kayıt düzeyi matrislere ek olarak benzersiz konum + ağırlık matrisleri de üretilir: 349.122 satır, ağırlık toplamı 2.020.638.
- **Ağırlık desteği** (scikit-learn 1.9.1 imzalarıyla doğrulandı):
  - `DBSCAN.fit` ve `KMeans.fit`: `sample_weight` destekliyor.
  - `HDBSCAN.fit`: desteklemiyor. Bu yüzden C modeli yalnızca kayıt düzeyinde.
- **Eşdeğerlik:** Ağırlıklı DBSCAN'in kayıt düzeyiyle aynı bölümlemeyi verdiği sentetik testte doğrulandı. Gerçek veride doğrulama Faz 3'e bırakıldı.

### K-21 — Graphify tarihli yedekleri git dışında (2026-10-19, Faz 2)
- **Bulgu:** `graphify-out/2026-10-19/` klasörü, `graphify update`'in otomatik oluşturduğu ve Faz 1 öncesindeki 19 düğümlü grafiğin yedeği. Aynı içerik git geçmişinde (commit `0fce519`) de var.
- **Karar:** Klasör silinmedi. Bu ve benzeri tarihli klasörler `.gitignore` ile git dışında tutuluyor. Aktif kaynak `graphify-out/graph.json`.

### K-22 — DBSCAN seçimi yeniden sınandı, kural değiştirilmedi (2026-10-19, Faz 3)
- **Bulgu:** Önceden tanımlı kural eps=25 m, min_samples=100'ü seçti (komşu ARI 0,480). Kayıtlı etiketlerden yapı tanıları: en geniş küme köşegeni 174 m (eps=50 adaylarında 4,4–7,5 km zincirlenme), medyan 8 konum / 41 m (kavşak ölçeği), kümelerin %85'i 13 yılın tamamında etkin; gürültü %59,7.
- **Karar:** Seçim korunur; sonuçlar görüldükten sonra kural değiştirilmez. Model "kronik kavşak sıcak noktası" katmanı olarak etiketlenir. Daha geniş kapsam için eps=25/ms=50 alternatif olarak raporlanır (Faz 4 kullanım kararı).

### K-23 — Yıllık sabit eşik kararlılık ölçüsü sayılmaz (2026-10-19, Faz 3)
- **Bulgu:** ms=100 tek bir yılın hacmiyle neredeyse hiç sağlanmaz; 2020 sonrası hacim yarıya inince yıllık küme sayısı 0–1'e düşer.
- **Karar:** Zamansal kararlılık hacme ölçekli eşik (c) ve tam veri kümelerinin kalıcılığı (b) ile yorumlanır; (a) yalnızca hacim etkisini göstermek için raporlanır.

### K-24 — Faz 4 devri SHA-256 bildirimiyle (2026-10-19, Faz 3)
- **Karar:** Faz 4'e devredilen olay düzeyi üyelikler, küme profilleri ve geometriler `phase4_manifest.json` içinde SHA-256, boyut ve satır sayısıyla kaydedilir; büyük dosyalar git dışında kalır.

### K-25 — Harita karo kaynağı: OpenFreeMap (2026-10-20, Faz 4)
- **Karar:** MapLibre GL JS yalnızca çizim motorudur; vektör karolar OpenFreeMap genel örneğinden (`tiles.openfreemap.org/planet`, OpenMapTiles şeması, OSM verisi) alınır. Stil (gece/gündüz) projede tanımlıdır.
- **Gerekçe:** API anahtarı, kayıt veya çerez yok; görüntüleme/istek sınırı yok; ticari kullanım serbest (openfreemap.org, 2026-10-20). Bina ayak izleri ve `render_height` içerir.
- **Koşullar:** Atıf zorunlu (MapLibre atıf denetimi otomatik gösterir). SLA yok. Çevrimdışı indirme 3.000 karo / 50 MB, en fazla 4 paralel istek ile sınırlı. Kesinti riski için kendi barındırma (haftalık planet MBTiles) seçeneği vardır.

### K-26 — Yüksekliği bilinmeyen binalar extrüde edilmez (2026-10-20, Faz 4)
- **Bulgu:** OpenMapTiles, OSM'de `height`/`building:levels` olmayan binalara `render_height = 5` atar. Beş ilçeden 15 z14 karosundaki 65.229 bina poligonunda bu değer %6,3 (Manhattan %5,1 … Staten Island %10,3); `reports/phase4/building_height_audit.json`.
- **Karar:** `render_height = 5` ve tabanı 0 olan binalar düz, ayrı renkte ("yükseklik verisi yok") çizilir; diğerleri gerçek `render_height` ile extrüde edilir. Gerçekten 5 m olan az sayıdaki bina da bu gruba düşer (muhafazakâr yaklaşım).

### K-27 — Nokta sunumu: benzersiz konum, bbox ve sunucu özeti (2026-10-20, Faz 4)
- **Karar:** 2.020.638 olay tarayıcıya gönderilmez. Ağırlıklı DBSCAN'de aynı konumdaki olaylar aynı etiketi aldığından olaylar 349.122 benzersiz konuma kayıpsız indirgenir (her konumda tek etiket doğrulanır). Düşük zoomda küme merkezleri (4.179) ve 1 km / 250 m UTM ızgara yoğunluk özeti; zoom ≥ 15'te yalnızca görünen bbox (≤ 0,05°) içindeki konumlar, en fazla 8.000; kesilen yanıtta gerçek toplamlar ayrıca gösterilir.

### K-28 — 3D varlıklar: Kenney CC0; lisansı belirsiz paket kullanılmaz (2026-10-20, Faz 4)
- **Karar:** Kenney Car Kit 2.0 ve City Kit (Roads) 2.2 (CC0) modelleri gltf-transform ile optimize edilir. `Cars Bundle-glb.zip` lisans/yazar bilgisi içermediği için kullanılmaz. Ayrıntı: `assets/3d/README.md`.

### K-29 — Three.js özel katmanı ve temsili trafik (2026-10-20, Faz 4)
- **Karar:** Modeller tek bir MapLibre özel katmanında (renderingMode "3d", ortak WebGL bağlamı ve derinlik tamponu) çizilir. Çapa noktası seçili küme merkezidir; nesne konumu mercator farkının çapa ölçeğine bölünmesiyle bulunur (konum hatasız, yalnızca boyut ~1e-5 oranında değişir). Doğrulama: model ekran konumu ile `map.project` farkı < 1,5 px (E2E).
- **Temsili trafik:** Araçlar küme merkezine 60 m içindeki gerçek bir OSM yol çizgisinde, en fazla 6 adet, sağ şeritte hareket eder; arayüzde "temsili simülasyon, geçmiş kaza hareketi değildir" notu gösterilir. Uygun yol yoksa araç gösterilmez.
- **Bağlam kaybı:** MapLibre stili geri yüklerken özel katmanları geri getirmez; katman, veri kaynakları ve seçim durumu `style.load` sonrasında yeniden kurulur (GLB'ler bellekteki ArrayBuffer önbelleğinden).
