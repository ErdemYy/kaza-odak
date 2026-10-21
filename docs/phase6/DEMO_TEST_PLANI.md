# SafeRoute 3D — Faz 6 Akademik Demo Test Planı

> Gerçek veri (NYC `h9gi-nx95`, anlık görüntü `20261019T155113Z`) ve kayıtlı Faz 3 deneyleriyle tekrar edilebilir sunum
> senaryosu. Her adımın beklenen değeri API'den alınmıştır ve `frontend/e2e/phase6.spec.ts` içindeki "Demo senaryosu —
> 14 adım" testiyle otomatik doğrulanır. Ekran görüntüleri: `reports/phase6/screenshots/demo-*.png`.

## 0. Hazırlık (sunumdan önce, bir kez)

| Kontrol | Komut / işlem | Beklenen |
|---|---|---|
| Uygulamayı demo profiliyle aç | `powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1 -Demo -Background -Open` | Tüm denetimler `[tamam]`; "SafeRoute 3D hazır: http://127.0.0.1:8000"; demo ısıtması birkaç saniye |
| İnternet | Betik OpenFreeMap erişimini denetler | Ağ yoksa uyarı: altlık harita/bina/yol karoları görünmez; kaza katmanları ve tüm analiz ekranları çalışır |
| Bellek | Betik ve Laboratuvar "Kaynak:" satırı | Dinamik analiz için ≥ 1.500 MB boş bellek. Azsa 13. adım "Kaynak sınırı" mesajıyla gösterilir (bu da doğru davranıştır) |
| Tarayıcı | Chrome/Edge, donanım hızlandırma açık | `chrome://gpu` → WebGL: Hardware accelerated |
| Kapatma | `scripts\stop_saferoute.ps1` | "SafeRoute sunucusu durduruldu" |

**Çevrimdışı not:** OpenFreeMap karolarının yerel bir kopyası bu fazda oluşturulmadı. OpenFreeMap verisi OSM tabanlıdır
(ODbL) ve toplu indirme için sağlayıcının belgelenmiş yolu planet dosyalarıdır; demo için sınırlı bir yerel karo arşivi
hazırlanması lisans/atıf koşulları ayrıca incelenerek Faz 7'de değerlendirilebilir. Bu fazda sağlayıcının izin vermediği
bir çoğaltma yapılmadı.

## 1. Senaryo

| # | Adım | Ekranda yapılacak | Beklenen (gerçek değer) |
|---|---|---|---|
| 1 | Uygulama başlatılır | Betik çıktısı | `/api/health` → `ok`; 2.020.638 olay yüklendi |
| 2 | Genel Bakış | Varsayılan ekran | Coğrafi analize uygun kayıt **2.020.638 / 2.269.187 (%89,0)**; model DBSCAN eps 25 m, min_samples 100; **4.179 küme**; gürültü **%59,7**; veri güncellik uyarısı görünür |
| 3 | Veri Gezgini: 29 orijinal öznitelik | "Veri Gezgini" → "Ham sütunlar" sekmesi | **29 / 29 sütun**; ham satır **2.269.187** |
| 4 | Ön işleme sonuçları | "Veri hattı" sekmesi | Uygun kayıt **2.020.638**; 00:00 şüpheli kayıt notu (**24.566** kesin 00:00); koordinat temizleme ve ilçe çıkarımı adımları |
| 5 | Model Karşılaştırma | "Model Karşılaştırma" | Üç seçili konfigürasyon yan yana; HDBSCAN satırında "örneklem (100k olay)" rozeti |
| 6 | DBSCAN sonuçları | Karşılaştırma tablosu + DBSCAN ızgarası | Siluet **0,945** (doğruluk değildir — bilgi simgesi); Davies–Bouldin 0,090; DBCV 0,394; K-Means gürültüsü **Uygulanamaz** |
| 7 | 3D Şehir Keşfi | "3D Şehir Keşfi" | Harita + kümeler; durum: "Gerçek veri yüklendi: 4.179 küme · 2.020.638 olay" |
| 8 | Brooklyn seçilir | Görünüm → İlçe (kamera) → Brooklyn | Kamera Brooklyn'e gider (kayıtlar SÜZÜLMEZ; yalnızca kamera) |
| 9 | Tillary St / Flatbush Ave Ext kümesine gidilir | Haritada Brooklyn Köprüsü girişindeki en büyük daireye tıklanır (veya Genel Bakış → en büyük 10 küme → #1344 "haritada aç") | Küme **#1344**, sıra 1 |
| 10 | Kümenin gerçek istatistikleri | Sağ panel | **1.444 kaza**; baskın ilçe Brooklyn; en sık sokaklar TILLARY STREET / FLATBUSH AVENUE EXTENSION; saatlik dağılım, araç türleri, katkı faktörleri. Temsili araçların simülasyon olduğu notu |
| 11 | Kümeleme Laboratuvarı | "Kümeleme Laboratuvarı" | Kaynak satırı (boş bellek, çalışan tavanı); kayıtlı 115 deney |
| 12 | Önceden hesaplanmış DBSCAN deneyi | "Kayıtlı deneyler" → seçili model dışındaki bir DBSCAN ızgara deneyi | Kayıtlı Faz 3 deneyi rozeti; küme/gürültü değerleri o deneyin etiket dosyasından; siluet/DBCV Faz 3 kaydından |
| 13 | Gerçek küçük dinamik analiz (kaynak uygunsa) | 3D Keşif → Filtreler: Manhattan + 2018 → "Bu filtreyle yeni kümeleme" → DBSCAN eps 35 m, min_samples 15 → Analizi başlat | Kapsam = Manhattan 2018 kayıt sayısı (API ile aynı); aşamalar gerçek çalışan süreçten; sonuç `dyn-…` deney kimliğiyle. Bellek yetersizse: "Kaynak sınırı — iş tamamlanmadı" + gerekçe (iş çalıştırılmaz) |
| 14 | Algoritma sonuçları ve küme değişiklikleri | Sonuç kartı → "Haritada göster" | Küme sayısı/gürültü (dinamik), DBCV **N/A** (dinamikte hesaplanmaz), siluet örneklem notu; haritada "Dinamik analiz sonucu" bandı; bu sonucun küme numaraları seçili modelinkilerle **eşleştirilmez** |

Önerilen ek gösterimler (isteğe bağlı): kayıtlı HDBSCAN sonucunu haritada açıp **zaman oynatma** (deney kapsamı
2012-07-01 → 2026-06-10, 100.000 olay; "Kümeleme yeniden çalıştırıldı mı? Hayır"); saat ölçeğinde 00:00 kovasının uyarı
rengi.

## 2. Bağlantı kaybı ve yeniden deneme davranışı

| Durum | Kullanıcının gördüğü | Yapılacak |
|---|---|---|
| Sunucu demo sırasında kapanır / ağ kopar (laboratuvar işi izlenirken) | "Sunucuya ulaşılamıyor; otomatik yeniden deneniyor (n. deneme)" — 1, 2, 4, 8, 15 sn aralıklarla | Sunucuyu `start_saferoute.ps1` ile yeniden açın; iş durumu kalıcı kayıttan yeniden görünür |
| Sunucu iş çalışırken çöktü | İş "Yarıda kaldı"; "yarım hesaplama diske yazılmadığı için kurtarılamaz; sonuç uydurulmadı" | "Yeniden dene" → yeni iş kimliği, önceki işe bağlantı |
| Harita veri isteği başarısız | Üst durum çubuğu kırmızı: "Veri yüklenemedi: Katman sunucusuna ulaşılamadı…" | Bağlantı dönünce filtreyi yeniden uygulamak veya ekranı yenilemek yeterli |
| Harita karoları alınamıyor | "Harita karoları alınamadı (ağ). Kaza katmanları çalışmaya devam eder." | İnternet bağlantısını denetleyin |
| Bellek yetersiz | Laboratuvar: "Bellek yetersiz — yeni iş şu an başlatılamaz"; gönderilen iş "Kaynak sınırı" | Diğer uygulamaları kapatın veya kayıtlı deneylerle devam edin |

## 3. Otomatik doğrulama

```powershell
cd frontend
npx playwright test e2e/phase6.spec.ts            # demo + zaman oynatma + mod ayrımı + WebGL + bağlantı + klavye + responsive + axe
npx playwright test e2e/phase6-restart.spec.ts    # gerçek çökme / yeniden başlatma senaryosu (ayrı port 8011, yalıtılmış iş kaydı)
npx playwright test -c playwright.perf.config.ts  # GPU / yazılım WebGL performans ölçümü
```

Sonuçlar: `reports/phase6/e2e_measurements.json`, `reports/phase6/restart_scenario.json`,
`reports/phase6/map_performance.json`. Gerçekleşen sonuçlar `docs/phase6/TEKNIK_RAPOR.md` §11'dedir.
