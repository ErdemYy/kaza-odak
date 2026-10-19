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
