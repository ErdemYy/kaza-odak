# SafeRoute 3D — Faz 6 Kalan Riskler ve Güvenlik Sınırları

> Bu belge Faz 6 sonunda **bilinen ve çözülmemiş** riskleri listeler. Kısmen çözülen konular "kısmen" olarak işaretlidir.
> Ölçümlere dayalı ayrıntı: `docs/phase6/TEKNIK_RAPOR.md`, `docs/phase6/PERFORMANS_RAPORU.md`.

## 1. Güvenlik sınırı (internete açık dağıtım için HAZIR DEĞİLDİR)

Uygulama tek kullanıcılı **yerel** akademik kullanım için tasarlandı. Varsayılan bağlama adresi `127.0.0.1`'dir.

| Konu | Faz 6 durumu | Kalan risk |
|---|---|---|
| Kimlik doğrulama / yetkilendirme | Bilinçli olarak YOK (yerel kullanım) | `--host 0.0.0.0` ile açılırsa ağdaki herkes iş başlatabilir, iptal edebilir, sonuç indirebilir |
| Host başlığı (DNS yeniden bağlama) | `TrustedHostMiddleware`: yalnızca `127.0.0.1`, `localhost`, `::1` (+ `SAFEROUTE_ALLOWED_HOSTS`) | Ters vekil arkasında doğru Host listesi verilmezse istekler 400 alır |
| CORS | Başlık eklenmez (yalnızca aynı köken) | — |
| İstek sınırları | bbox ≤ 0,05°, nokta ≤ 20.000, sayfa ofseti ≤ 10⁷, tablo ≤ 500 satır, gövde ≤ 64 KB, kuyruk ≤ 3, eşzamanlı iş 1 | Hız sınırlama (rate limiting) yok: aynı istemci çok sayıda GET ile CPU'yu meşgul edebilir |
| Dosya yolu güvenliği | Kimlikler katı desenle doğrulanır (`lab-<12 hex>`, `dyn-<16 hex>`, `<algoritma>-<alfasayısal>`); dosya yolu kullanıcı girdisinden kurulmaz (iş dizini = sunucunun ürettiği SHA-256 önbellek anahtarı) | — |
| Hata mesajları | Beklenmeyen hatalar genel bir mesajla 500 döner, yığın izi yalnızca sunucu günlüğüne yazılır; iş hata metinlerinde mutlak yollar `<proje>`, `<lab_cache>`, `~` ile maskelenir | Doğrulama hataları (422) kullanıcının gönderdiği değeri geri yansıtır (yerel kullanımda sorun değil) |
| Güvenlik başlıkları | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `COOP` | İçerik Güvenliği Politikası (CSP) eklenmedi: harita karo/glif kaynakları ve satır içi stiller için ayrıca ayarlanmalı |
| TLS | Yok | Ağ üzerinden kullanım için ters vekil + TLS gerekir |
| Bağımlılık açıkları | Denetlenmedi (`pip-audit` / `npm audit` çalıştırılmadı) | Faz 7'de önerilir |

## 2. Kaynak ve güvenilirlik

| Risk | Durum |
|---|---|
| **Bu geliştirme makinesinde bellek sıkışık** (15,6 GB toplam; ölçüm sırasında boş bellek 0,5–3 GB arasında dalgalandı; başka uygulamalar — Unity, tarayıcılar, OneDrive — belleğin çoğunu kullanıyor). | Dinamik işler boş bellek < 1.500 MB iken bilinçli olarak çalıştırılmaz ("Kaynak sınırı"). Demo sırasında diğer uygulamalar kapatılmalıdır. |
| Çalışan bellek tavanı (Windows iş nesnesi, commit) aşıldığında Python `MemoryError` yerine bazı C uzantıları süreci doğrudan sonlandırabilir. | İş "Kaynak sınırı" olarak işaretlenir (tepe commit tavanın ≥ %95'i ise) veya "Başarısız" (çıkış kodu ile). Başarılı işaretlenmez. |
| Windows dışı platformlarda iş nesnesi yoktur. | Yazılımsal bekçi (psutil RSS örneklemesi, 0,25 sn) tavanı aşan çalışanı sonlandırır; API süreci sert biçimde ölürse çalışan `daemon` olsa da yetim kalabilir — bir sonraki açılışta PID + oluşturulma zamanı + komut satırı eşleşmesiyle temizlenir. |
| BLAS/OpenMP iş parçacığı sayısı çalışanlarda 4 ile sınırlandı (OpenBLAS commit'i 1.376 → 475 MB). | K-Means'in kayan nokta toplam sırası iş parçacığı sayısına bağlı olabilir; dinamik K-Means sonuçları Faz 5'teki aynı istekle bit düzeyinde aynı olmayabilir (kayıtlı Faz 3 sonuçları etkilenmez: yeniden fit edilmez). |
| Uzun süren tek bir HDBSCAN işi (100k olay ≈ 69 sn) sırasında kuyruktaki işler bekler. | Eşzamanlı iş sayısı bilinçli olarak 1. |
| Laboratuvar önbelleği için boyut/yaş tabanlı temizleme yok. | Disk kullanımı zamanla artar (iş başına birkaç MB). |
| `start_saferoute.ps1 -Background` çıktısı bir boruya (`| Select-Object` vb.) bağlanırsa, PowerShell 5.1 `Start-Process` tutamaç kalıtımı nedeniyle çağrı sunucu kapanana kadar dönmez. | Doğrudan konsoldan çalıştırıldığında sorun yok (doğrulandı). Boruya bağlamayın. |
| `stop_saferoute.ps1` süreci dışarıdan sonlandırır (temiz kapanış kancası çalışmaz). | Tasarım gereği güvenli: yarım işler bir sonraki açılışta "Yarıda kaldı" olur; tamamlanmış sonuçlar SHA-256 ile korunur. Ön planda Ctrl+C temiz kapanıştır. |
| SQLite iş kaydı tek dosyadır; iki ayrı sunucu aynı `lab_root` ile açılırsa ikincisinin açılış uzlaştırması birincinin etkin işlerini "Yarıda kaldı" işaretler. | Varsayılan kullanımda tek sunucu. Yalıtılmış test/demo için `saferoute serve --lab-root <dizin>`. |

## 3. Veri ve akademik yorum

- Kaynak veri kontrol anında 125 gündür güncellenmemişti (bugün itibarıyla 127 gün); bu faz yeni veri indirmedi.
- Siluet doğruluk değildir; DBCV yoğunluğa dayalı küme geçerliliğidir (−1…1); gürültü oranı başarısız tespit değildir;
  yüksek kaza yoğunluğu trafik hacmine göre risk değildir; dışbükey zarf gerçek yoğunluk sınırı değildir — arayüzde bu
  açıklamalar var, ancak kullanıcı bilgi simgelerini okumazsa yanlış yorum riski sürer.
- HDBSCAN yalnızca 100.000 olaylık örneklemde; arayüz ve API bunu her yerde belirtir. Tam veri HDBSCAN çalıştırılmadı.
- Dinamik işlerde DBCV hesaplanmaz (N/A); siluet/Davies–Bouldin basit rastgele örneklemdedir ve Faz 3 ortak
  değerlendirme kümesiyle karşılaştırılamaz.
- Kayıt düzeyi algoritmalarda (HDBSCAN) bir konumda birden çok etiket olabilir; haritada baskın etiket gösterilir.
- Etken metinleri NYPD'nin İngilizce kodlarıdır; çevrilmedi.

## 4. Harita, 3D ve çevrimdışı kullanım

- Altlık harita, 3D bina ve yol karoları OpenFreeMap'ten (internet) gelir; yerel karo önbelleği oluşturulmadı.
  Çevrimdışıyken kaza katmanları ve analizler çalışır, zemin harita boş görünür.
- WebGL bağlam kaybından toparlanma test edildi (yapay `WEBGL_lose_context`); gerçek sürücü çökmesi / GPU sıfırlaması
  ile test edilmedi.
- Performans ölçümleri tek bir dizüstü bilgisayarda (AMD Radeon tümleşik + NVIDIA RTX 4050 Laptop) alındı; düşük
  donanımlı makinelerde FPS ölçülmedi. Ayrıntı: `PERFORMANS_RAPORU.md`.
- PMTiles/vektör karo prototipi kurulmadı; karşılaştırma mevcut çözümün ölçümüne ve statik alternatifin ölçülen
  boyutuna dayanır (vektör karo bayt boyutu tahmindir).

## 5. Test kapsamı boşlukları

- Gerçek veriyle dinamik iş, bellek durumuna bağlı olarak E2E'de çalıştırılabildi veya "Kaynak sınırı" yolu doğrulandı
  (hangisinin gerçekleştiği `reports/phase6/e2e_measurements.json` içinde kayıtlıdır).
- Güç kesintisi (işletim sistemi düzeyinde) senaryosu test edilmedi; SQLite `synchronous=FULL` + WAL ile tasarlandı.
- Ekran okuyucu (NVDA/JAWS) ile elle test yapılmadı; axe ve klavye testleri otomatik.
