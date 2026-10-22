# SafeRoute 3D — Faz 8B Görsel Karşılaştırma (Önce / Sonra)

> Önce: `fc7c176` derlemesi · Sonra: Faz 8B derlemesi · Aynı makine, aynı GPU (NVIDIA RTX 4050, ANGLE D3D11),
> aynı tarayıcı bayrakları (`playwright.visual.config.ts`), aynı sahne betiği (`frontend/e2e-visual/phase8b.visual.ts`).
> Her sahnede sabit kamera (merkez, zoom, eğim, yön), filtre yok, seçili DBSCAN modeli, animasyon "kapalı".
> Görüntüler: `reports/phase8b/screenshots/{before,after}/`, yan yana birleşimler: `reports/phase8b/screenshots/karsilastirma/` (JPEG; kaynak PNG'ler `before/`, `after/`)
> (`scripts/phase8b_compare.py`). Piksel farkı yalnızca "ne kadar değişti" bilgisidir; "daha iyi" yargısı aşağıda,
> görüntüler tek tek incelenerek verilmiştir.

## Sahne kameraları

| Sahne | Merkez | Zoom | Eğim | Yön |
|---|---|---:|---:|---:|
| NYC genel | −73,94 / 40,70 | 10,3 | 45° | −17° |
| Orta yakınlık (gece/gündüz) | −73,99 / 40,735 | 13,4 | 50° | −17° |
| Manhattan 3D (gece/gündüz) | −73,9855 / 40,7505 | 15,4 | 60° | 29° |
| Brooklyn Tillary (#1344), seçili | küme merkezi | 16,6 | 50° | −17° |
| Seçili küme, orta yakınlık | küme merkezi | 13,6 | 45° | −17° |
| GLB yerleştirilmiş (taksi, yön 3°) | −73,98397 / 40,69471 | 19,6 | 62° | 335° |

## Değerlendirme

| # | Sahne | Önce (sorun) | Sonra | Yargı |
|---|---|---|---|---|
| 01 | NYC genel | Küme merkezleri 1,4 px'e kadar küçülüyor, komşular tek leke; turuncu yoğunluk ışıması turuncu merkezlerin arkasında kontrastı siliyor | Merkezler 1,7–5,5 px, koyu kontur ile ayrı daireler; yoğunluk saydamlığı 0,85 → 0,62 | **Daha iyi** (ayrışma); şehir ölçeğinde fark küçük |
| 02 | Orta yakınlık, gece | z 13,4'te binalar %37 saydam "hayalet" kütleler; ara yollar ~1 px ve bina tabanıyla aynı ton | Bina geçişi z 13,1–13,8'e kısaltıldı (hayalet görünüm büyük ölçüde gitti); yol ızgarası belirgin; merkez konturları zoom'la kalınlaşıyor | **Daha iyi** |
| 03 | Manhattan 3D, gece | Bütün bina kütlesi tek düz mavi ton; çatı/duvar ve yönler ayırt edilmiyor | Yükseklikle kontrollü üç ton (alçak → yüksek) + daha yatık ışık (kutup 35° → 48°): duvar yüzleri farklı gölgelenir, derinlik okunur | **Orta düzeyde daha iyi** (genel ton öncekinden biraz daha açık; yollar binaların arasında yine az görünür). Not: ilk denemede (#3A5683 tepe, yoğunluk 0,68) binalar fazla parlak/doygun mavi oldu; bu sürüm **geri alındı**, desatüre tonlara inildi |
| 04 | Orta yakınlık, gündüz | Binalar zeminle neredeyse aynı (WCAG kontrast 1,28) | Alçak/orta binalar daha koyu, serin gri (1,73 / 1,45). Yüksek bina tepesi tasarım gereği açık (1,19 — Faz 8'in 1,28 değerinin altında); yükseklik ayrımı ton farkıyla okunur | **Daha iyi** |
| 05 | Manhattan 3D, gündüz | Beyaza yakın, yüzeyler birbirine karışıyor | Gri tonlu, duvar gölgelemesi görünür | **Daha iyi** (gündüz hâlâ gece kadar "premium" değil; bkz. sınırlılıklar) |
| 06 | Brooklyn Tillary seçili | Seçili merkez kırmızı + beyaz kontur, ama çevredeki kümeler aynı parlaklıkta | Seçili kümede ek kırmızı halka/hale; diğer merkezler %38 opaklığa, zarflar %7'ye iner | **Daha iyi** |
| 07 | Küme ayrıntı paneli | Altı istatistik + uzun liste tek blok; model parametreleri ve deney kimliği listenin ortasında | Yapışkan başlık (küme no, sıra, Odakla, Kapat) → özet bant (toplam, ilçe, yaralanmalı, ölümlü) → Konum / Zaman / Araç / Faktör / Model açılır grupları | **Daha iyi**. İlk sürümde sıra rozeti başlığı iki satıra kırıyordu ve "Toplam / İlçe" etiketleri farklı hizadaydı — **düzeltildi** |
| 08 | Seçili küme, orta yakınlık | Seçili küme kalabalıkta kayboluyor | Seçili küme belirgin; diğerleri geri planda | **Daha iyi** |
| 09 | GLB paneli | Yalnızca düğme listesi + sayı alanları; modeli görmek için haritada z 19,6'ya inmek gerekiyordu | Ayrı önizleme alanı: döndür/yakınlaştır/sıfırla, 1 m ızgara, ad, kısa lisans, ölçüler, "Haritada / Haritaya yerleştir / Modeli kaldır" | **Daha iyi** (yeni özellik) |
| 10 | GLB haritada | Aynı | Aynı yerleşim; doku örneklemesi doğrusal (plaka gürültüsü giderildi) | **Eşit / biraz daha iyi** |
| 11 | Genel bakış | Güncellik uyarısı tek uzun satır; dışlama nedenleri ve deney kimliği ana alanı kaplıyor; tarih kapsamı küçük kartta | Uyarı tek satır ve kapsam şeridiyle tek blokta (ayrıntı ipucunda); kaynak tarihi, analiz kapsamı ve modelin veri dönemi daima görünür; dışlama nedenleri açılır bölümde; benzersiz konum karta taşındı; yıl grafiği ilk ekranda kaldı | **Daha iyi**. Ara sürümde uyarı ve şerit ayrı kutulardı; grafik ilk ekranın altına itildi ve Faz 8 `O03` başarısız oldu — **birleştirilerek düzeltildi** |
| 12 | Yerleşim 1920/1440/1280/768/390 | Sol panel kapatılamıyordu (1440'ta haritanın ~%46'sı panel) | Sol panel açık bir düğmeyle daraltılabilir (1440'ta panellerin kapsamadığı genişlik %54 → daraltınca %73); taşma 0 | **Daha iyi** |
| 13 | Mobil genel bakış (390 px) | Uzun uyarı paragrafı; dışlama nedenleri kahraman alanında | Uyarı daha kısa; kaynak tarihi / analiz kapsamı / model dönemi görünür; ancak üç hücre alt alta dizildiği için ana sayı (2.020.638) ~180 px aşağı iner | **Karışık**: bilgi daha düzenli, ilk ekran daha uzun. Geri alınmadı (kapsam bilgisinin görünür olması istenen bir şart); mobilde hücreleri yatay sıkıştırmak sonraki iyileştirme |

## Geri alınan / düzeltilen ara denemeler

1. **Parlak mavi binalar** (ilk deneme): tepe `#3A5683`, ışık 0,68 — neon etkisine yakın, geri alındı.
2. **Küme merkezlerinin kaybolması**: kontur kalınlığında `["zoom"]` bir `case` içinde kullanılmıştı; MapLibre katmanı
   hiç eklemedi, orta yakınlıkta yalnız zarflar kaldı. Düzeltildi; tüm stil artık `validateStyleMin` birim testinden geçiyor.
3. **Gece bina tabanı**: ikinci denemede taban `#1B2537` Faz 8'den (`#1A2740`) daha düşük kontrastlıydı; birim testi
   yakaladı, `#202C43` yapıldı.
4. **Gündüz zemin rengi**: `#E4E9F0` yapılmıştı; Faz 4 tema sözleşmesini (`#E8EDF3`) bozduğu için geri alındı.
5. **Logo rötuşu**: aday B (≤ 24 px'te kalın rota, hale yok) 16/24 px'te biraz daha okunur; uygulamada logo yalnızca
   30/32 px çizildiği ve bu boyutlarda iki sürüm birebir aynı olduğu için **uygulanmadı** (bkz. TEKNIK_RAPOR §8).

## GLB doku gürültüsü (kanıt)

`screenshots/kanit/glb-doku-nearest-once.png` ↔ `glb-doku-linear-sonra.png`: taksinin ön plakasındaki siyah-beyaz
piksel gürültüsü. Kök neden doğrulandı: Kenney dokuları `NEAREST` örnekleme ile gelir (mag 9728, min 9984) ve taksinin
6 UV köşesi tam texel köşesine oturur; z-fighting (eş düzlemli üst üste üçgen 0) ve bozuk normal (0) **değil**.
Doku verisi değiştirilmedi; yalnızca örnekleme doğrusal + mipmap yapıldı (`smoothTextureSampling`).
