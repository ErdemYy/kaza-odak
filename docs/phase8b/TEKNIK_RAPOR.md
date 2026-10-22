# SafeRoute 3D — Faz 8B Teknik Raporu: Görsel İyileştirme ve 3D Deneyim Kalitesi

> Tarih: 2026-10-22 · Temel commit: `fc7c176` · Veri sürümü ve Faz 3 model çıktıları **değişmedi**
> (`dbscan-52abd2c018`, 4.179 küme, 814.578 kümelenmiş olay — değerler arayüzde meta veriden okunur, sabit yazılmadı).
> Ek belgeler: [`GORSEL_KARSILASTIRMA.md`](GORSEL_KARSILASTIRMA.md), [`PERFORMANS.md`](PERFORMANS.md),
> [`REGRESYON_SONUCLARI.md`](REGRESYON_SONUCLARI.md). Kanıtlar: [`reports/phase8b/`](../../reports/phase8b/).

## 0. Ön inceleme

- Git temiz, `main` @ `fc7c176`. Okunanlar: `PROJECT_SPEC.md`, `CLAUDE.md`, Faz 8 teknik raporu ve ekran görüntüleri.
  İlişkiler `graphify query` ile çıkarıldı (MapLibre stili ↔ veri katmanları ↔ seçim ↔ Three.js GLB katmanı ↔ varlık
  inceleyici ↔ keşif ekranı), ardından ilgili kaynak dosyalar doğrudan okundu.
- Süreçler: 4173 dahil dinlenen başka proje portu yoktu; yalnızca SafeRoute sunucusu (8000; Faz 8 testi için yalıtılmış
  8012) ve Playwright tarayıcıları başlatıldı. Başka projelerin süreçlerine dokunulmadı.
- Temel çizgi (değişiklik öncesi): Vitest 86/86, `tsc -b` temiz, `vite build` başarılı. Backend pytest ilk çalıştırmada
  208/210 (Vitest ile **eşzamanlı** çalıştırıldığı için iki Faz 6 zamanlama testi başarısız); kod değişmeden tek başına
  yeniden çalıştırılınca `test_phase6.py` 16/16 geçti → yük altında zamanlama oynaklığı (§10).
- "Önce" ekran görüntüleri ve "önce" performans ölçümü, değişiklik öncesi derlemeyle alındı (temel `dist` ayrıca
  saklandı; önce/sonra performansı aynı oturumda dönüşümlü ölçüldü).

## 1. Önceki görsel sorunlar ve kök nedenleri

| # | Sorun (ekran görüntüsünde) | Kök neden (kodda doğrulandı) |
|---|---|---|
| S1 | 3D şehirde bina ve yollar düşük kontrast | `style.ts` gece paletinde yol `#1C2A42` ile bina tabanı `#1A2740` aynı ton bandında; bina rengi yalnızca iki duraklı (0→120 m) ve ışık dik (kutup 35°, yoğunluk 0,55) → bütün kütle tek düz ton. Gündüz bina `#CBD3DE` / zemin `#E8EDF3` (kontrast 1,28) |
| S2 | Orta yakınlıkta "hayalet" binalar | `fill-extrusion-opacity` z 13 → 14 arası doğrusal: z 13,4'te %37 saydam kütleler |
| S3 | İnce yollar | `roadWidth` z 14'te taban × 1,6 → ara yol 1,3 px |
| S4 | Kümeler uzak/orta yakınlıkta ayırt edilemiyor | Merkez yarıçapı z 9'da 1,4 px; kontur sabit 0,8 px; yoğunluk ışıması (opaklık 0,85) turuncu/kırmızı merkezlerle aynı renklerde ve arkalarında |
| S5 | Seçili küme çevreden ayrışmıyor | Seçimde yalnızca o merkezin rengi/konturu değişiyor; diğer 4.178 merkez ve zarflar aynı parlaklıkta |
| S6 | Lejant "küçük/büyük" diyor ama ölçeği açıklamıyor | `Legend.tsx` sabit iki renk; boyutun neyi temsil ettiği yazmıyor |
| S7 | GLB modelleri haritada incelemek zor | Model yalnızca haritada (z ≥ 18, gerçek 5 m boyut) görülebiliyordu; önizleme yoktu |
| S8 | GLB ön plakada piksel gürültüsü | Kenney dokuları `NEAREST` örnekleme (mag 9728, min 9984); taksinin 6 UV köşesi tam texel köşesinde. Z-fighting ve bozuk normal ayrıca **elendi** (eş düzlemli üst üste üçgen 0, bozuk normal 0) |
| S9 | Küme paneli sıkışık | Altı `Stat` + 6 satır + grafikler + model kutusu tek blokta; ana değerler ile ikincil bilgiler aynı ağırlıkta |
| S10 | Genel bakışta teknik açıklamalar fazla yer kaplıyor | Güncellik uyarısı tek uzun cümle; dışlama nedenleri ve açıklama kahraman alanında; tarih kapsamı küçük kartta |
| S11 | Paneller haritayı fazla kapatıyor | 1440 px'te sol 320 + sağ 340 px; sol panel kapatılamıyordu |
| S12 | Logo | Değerlendirildi; §8 |

## 2. Değiştirilen ve eklenen dosyalar

| Dosya | Tür | Amaç |
|---|---|---|
| `frontend/src/map/style.ts` | değişti | Gece/gündüz paletleri (zemin < yol < bina), üç duraklı bina tonu, `themeLight`, yol genişliği, bina geçişi |
| `frontend/src/map/dataLayers.ts` | değişti | `CENTROID_SCALE` + `centroidRadius` (tek kaynak), zoom'a duyarlı kontur, hover ve seçim halkası katmanları (tek öğe süzgeci), seçimde soluklaştırma, gürültü halkası, yoğunluk opaklığı |
| `frontend/src/features/explorer/CityMap.tsx` | değişti | Hover kartı (tek Popup, `pickCluster` ile aynı kural), tema ışığı, `pick` test kancası |
| `frontend/src/components/Legend.tsx` | değişti | Veriye bağlı boyut ölçeği ("boyut ve renk kayıt sayısı; risk değil"), palet renkleri |
| `frontend/src/components/ModelPreview.tsx` | yeni | Bağımsız WebGL GLB önizleyici |
| `frontend/src/lib/preview.ts` | yeni | `fitDistance`, `disposeObject` (saf, test edilir) |
| `frontend/src/lib/glb.ts` | değişti | `smoothTextureSampling` |
| `frontend/src/map/threeLayer.ts` | değişti | Harita modellerinde doğrusal doku örnekleme (1 satır) |
| `frontend/src/components/AssetInspector.tsx` | değişti | Önizleyici, yerleştir/kaldır durumu, açılır "Konum…" ve "Kaynak ve lisans" |
| `frontend/src/features/explorer/ClusterDetails.tsx` | değişti | Yapışkan başlık, özet bant, açılır gruplar |
| `frontend/src/features/explorer/ExplorerPage.tsx` | değişti | Sol panel daralt/aç, harita dolgusu, lejant zoom'u |
| `frontend/src/features/explorer/TimeControls.tsx` | değişti | Histogram 36 → 32 px |
| `frontend/src/features/overview/OverviewPage.tsx` | değişti | Kısa uyarı + ayrıntı, kapsam şeridi, açılır dışlama nedenleri, benzersiz konum kartı |
| `frontend/src/styles.css` | değişti | Hover kartı, `.disclosure` |
| `frontend/tests/unit/phase8b.test.tsx` | yeni | 16 Vitest testi |
| `frontend/e2e/phase8b.spec.ts` | yeni | 3 Playwright regresyon testi |
| `frontend/e2e-visual/phase8b.visual.ts`, `frontend/playwright.visual.config.ts` | yeni | Önce/sonra sahne yakalama |
| `scripts/phase8b_compare.py` | yeni | Yan yana birleşim + piksel farkı özeti |
| `docs/phase8b/*`, `reports/phase8b/*` | yeni | Raporlar ve kanıtlar |
| `graphify-out/*` | güncellendi | Bilgi grafiği |

Değiştirilmeyenler: backend kodu, ham/işlenmiş veri, Faz 3 model sonuçları, GLB dosyaları ve `registry.json`, harita
motoru (MapLibre + Three.js) ve render yapısı, logo varlıkları, Faz 1–8 belgeleri ve test dosyaları.

## 3. 3D şehir iyileştirmeleri

- **Ton sıralaması:** gece zemin `#0B1120` < ara yol `#253147` (kontrast 1,31 → 1,44) < ana yol `#34425C` (1,61 → 1,87);
  binalar mavi tonlu, yollar desatüre arduvaz: renk tonu ve ışıklılık birlikte ayrışır.
- **Kontrollü bina tonu:** render_height'e göre üç durak (0 m `#202C43` → 25 m `#2A3852` → 150 m `#3A4B6B`); taban
  kontrastı 1,26 → 1,35, tepe 1,68 → 2,15. Gündüz: `#AAB7C8` → `#BCC7D5` → `#D3DBE6` (zemin `#E8EDF3` korunur — Faz 4 `viewer.spec` tema sözleşmesi; ara sürümde `#E4E9F0` yapılmış, Faz 4 testi yakalamış, geri alınmıştır).
- **Işık:** temaya göre (`themeLight`), kutup 35° → 48°, gece 0,6, gündüz 0,42 — duvar yönleri farklı gölgelenir.
- **Çizgi kalınlıkları:** z 13 ve z 15 ara durakları; ara yol z 14'te ~1,3 → ~1,9 px.
- **Bina geçişi:** z 13,1 → 13,8 (Faz 8: 13 → 14).
- **Yükseklik verisi olmayan binalar** önceki gibi extrüde edilmez; düz, ayrı renk ve konturla çizilir (uydurma yükseklik yok);
  lejantta açıkça yazılır.
- Neon, bloom veya şehir çapında parlama yoktur; harita motoru ve coğrafi hizalama değişmedi (Faz 4 `viewer.spec`
  sürüklenme ölçümü yeniden geçti, §10).

## 4. Kaza kümesi görünümü

- **Boyut = kayıt sayısı:** yarıçap √kayıt ile doğrusal (100 → 1.444 kayıt aralığı, dışı kıstırılır), renk aynı sayıyı üç
  kademede tekrarlar. Estetik amaçlı ölçek dışı büyütme yok. `centroidRadius` hem MapLibre ifadesini hem lejantı üretir;
  lejant "boyut ve renk kayıt sayısını gösterir … kaza riskini değil" diye açıkça yazar.
- **Zoom'a göre boyut ve kontur:** z 9/11/13/15/17 durakları; koyu kontur 0,5 → 1,4 px — üst üste binen iki komşu küme iki
  ayrı daire olarak okunur.
- **Seçim:** ek `centroid-selected` halka katmanı + diğer merkezler %38, zarflar %7 opaklık; seçim kalkınca eski görünüm.
- **Hover:** tek bir MapLibre `Popup` (DOM öğesi sayısı sabit; 4.179 küme için DOM işaretçisi yok); kare başına en çok bir
  sorgu (`requestAnimationFrame`). Kart: küme no, sıra, kayıt, ilçe, yaralanmalı/ölümlü — değerler `/api/clusters`
  özelliklerinden, ek istek yok. Kart ile tıklama **aynı** seçim kuralını (`pickCluster`, ekranda en yakın merkez) kullanır.
- **Hover/seçim halkaları** `setFilter` ile yalnızca ilgili tek kümeyi çizer (4.179 öğelik ek katman maliyeti yok).
- **Gürültü (−1):** dolu mavi kümelenmiş noktalardan ayrı, içi soluk gri halka.
- **Yoğunluk ile çakışma:** ısı haritası opaklığı 0,85 → 0,62 (z ≤ 12) / 0,5; merkezler ısının üstünde.
- **İsabet alanı doğrulaması:** z 13,4'te ekranda görünen 53 küme merkezinin (ilk 60 adaydan kenara yakın olmayanlar) her birinin ekran noktasında seçim kuralı **kendi
  kimliğini** döndürdü (yanlış 0) — `phase8b.spec.ts`; 4 px yakın iki küme birim testi.

## 5. GLB önizleme özellikleri

- Model düğmesi → **önizleme** + (Faz 4/8 sözleşmesi korunarak) haritaya yerleştirme. "Modeli kaldır" sonrası önizleme
  açık kalır, **"Haritaya yerleştir"** ile yeniden yerleştirilir. Durum satırı: "Haritada / Haritada değil".
- **Döndür** (sürükle veya ±30° düğmeleri), **yakınlaştır/uzaklaştır** (tekerlek veya düğme), **kamerayı sıfırla**;
  eğim zemin altına inmez. Ad, kısa lisans (CC0 1.0 Universal · Kenney), açılır tam kaynak/lisans, gerçek ölçüler (G×U×Y)
  ve 1 m ızgara.
- **Kadraj:** sınırlayıcı küre + dikey/yatay görüş açısı → `fitDistance` (×1,18 pay); testte kamera uzaklığı = hesaplanan
  kadraj uzaklığı (fark < 0,001).
- **Işık:** anahtar + dolgu yönlü ışık + yarım küre; ton eşleme Khronos PBR Neutral (taban renkleri kaydırılmaz).
  PMREM ortam haritası denendi, **kaldırıldı** (Kenney malzemeleri metalness 0 / roughness 1: katkısı yalnızca dağınık
  ortam ışığıydı; iç render hedefi GPU sayacında kalıyordu).
- **WebGL ayrımı:** önizleme ayrı, küçük bir bağlam (`powerPreference: low-power`); harita bağlamına, derinlik tamponuna,
  `city-models` katmanına dokunmaz. İstek üzerine çizim (hareketsizken kare yok).
- **Tekrar indirme yok:** GLB ikili verisi `fetchGlb` önbelleğinden; testte taksi → sedan → taksi sonrası `taxi.glb` isteği **1**.
- **Kaynak temizliği:** model değişince önceki geometri/malzeme/dokular bırakılır (sayaçlar sabit: 4 geometri / 2 doku);
  panel kapanınca `controls.dispose`, `disposeObject`, `renderer.dispose`, `forceContextLoss`. Ölçüm: GPU geometri 0,
  bağlam kayıp = evet; three.js doku sayacında model dışı **1** kayıt düşmüyor (bkz. §12).

## 6. Küme detay paneli

Yapışkan başlık (eyebrow'da sıra, "Küme #…", Odakla, Kapat) → özet bant (**toplam kaza**, ilçe, yaralanmalı, ölümle
sonuçlanan, yaralı/ölü kişi) → açılır gruplar: **Konum bilgisi** (özet: başlıca cadde), **Zaman dağılımı** (özet: zirve
saat; histogram 44 → 56 px), **Araç türleri**, **Kayıtlı katkı faktörleri**, **Model bilgisi** (varsayılan kapalı; deney
kimliği burada). Panel kendi içinde kayar, başlık görünür kalır (testte doğrulandı). Araç oranlarının toplamının %100'ü
aşabileceği notu korundu ve netleştirildi. Hiçbir değer değişmedi; hepsi aynı API alanlarından okunur.

## 7. Genel bakış

Güncellik uyarısı **gizlenmedi** ve kaynak/kapsam bilgileriyle **tek blokta** birleştirildi (`ov-scope`): üstte uyarı
satırı (son güncelleme tarihi, bugün itibarıyla gün sayısı, eşik, analiz bitiş tarihi; hesap ayrıntısı — yayıncı beyanı,
kontrol tarihi, anlık görüntü — bilgi ipucunda), altında daima görünen üç hücre: **kaynak tarihi**, **analiz kapsamı**
(kısmi yıllar), **modelin veri dönemi**. Sonuncusu sabit yazılmaz; `kümelenmiş + gürültü = uygun` eşitliği API'den
doğrulanınca gösterilir, aksi hâlde "—". Dışlama nedenleri / eksik koordinat açıklaması açılır bölüme taşındı; uygun ve
dışlanan toplamları görünür kaldı. Deney kimliği model kartında küçük satırda; gürültü oranı açıklaması ipucunda + "hata
ölçüsü değil" kısa notu. Benzersiz konum açıklama metninden karta taşındı.

Ara sürümde uyarı ve şerit iki ayrı kutuydu; bu, yıl grafiğini 1440×900'de ilk ekranın altına itti ve Faz 8 `O03`
etkileşimi (grafik ipucu) başarısız oldu. Uyarı şeride katılarak blok ~85 px kısaltıldı; grafik yeniden ilk ekranda
(Faz 8B testinde `toBeInViewport` ile korunur).

## 8. Logo rötuşu

Faz 8 "Kaçınan rota" simgesi (A) ile aday optik rötuş (B: ≤ 24 px'te rota 4,5 → 5,6, düğümler ve sıcak nokta büyük, hale
yok) 16/24/32/48 px, koyu ve açık zeminde, wordmark ile birlikte gerçek boyutta çizildi
(`screenshots/kanit/logo-karsilastirma-1x.png`, `-3x.png`). Bulgular: 16/24 px'te B'de kırmızı nokta daha seçik, açık
zeminde A'nın turuncu halesi pembe lekeye dönüşüyor; 32 px ve üstünde iki sürüm birebir aynı. Uygulama içinde logo yalnızca
30/32 px çiziliyor. **Karar: logo değiştirilmedi** (belirgin iyileşme yok). B yalnızca favikon için anlamlı olabilir; bu,
marka betiği (`scripts/phase8_brand.py`) ile üretilen varlıkların değişmesini gerektirdiği için bu fazda yapılmadı.

## 9. Önce/sonra karşılaştırması

Ayrıntı ve sahne sahne yargı: [`GORSEL_KARSILASTIRMA.md`](GORSEL_KARSILASTIRMA.md). Kötüleşen iki ara deneme (parlak mavi
binalar, kaybolan küme merkezleri) ve bir gerileme (koyu gece tabanı) geri alındı/düzeltildi.

## 10. Test sonuçları

[`REGRESYON_SONUCLARI.md`](REGRESYON_SONUCLARI.md).

## 11. Performans sonuçları

[`PERFORMANS.md`](PERFORMANS.md).

## 12. Bilinen sınırlılıklar

1. **Önizleyici doku sayacı:** panel kapanınca three.js `info.memory.textures` 1'de kalıyor. Modelin kendi dokusu ve
   geometrileri bırakılıyor, model değişiminde sayaç büyümüyor (sızıntı yok) ve bağlam `forceContextLoss` ile kaybediliyor
   (tarayıcı o bağlamın tüm GPU belleğini bırakır). Kalan kaydın kaynağı (çizici iç kaynağı olduğu düşünülüyor; ton eşleme
   ve PMREM elendi) **doğrulanamadı**.
2. **axe `label-content-name-mismatch` (tema düğmesi):** görünür "Gece/Gündüz" metni erişilebilir adda ("Gündüz moduna
   geç") geçmiyor. Faz 8'den beri var; Faz 8 `E` testi adı birebir doğruladığı için değiştirilmedi. Faz 8B testinde ayrı
   kaydedilir (`results.axe_known`), gizlenmez.
3. Gündüz modu gece modu kadar rafine değil; yüksek bina tepeleri zeminden düşük kontrastlı (1,19; Faz 8 tek ton: 1,28) — ton farkı yüksekliği
   gösterir, ancak açık zeminde siluet zayıf kalır.
4. 3D varlık paneli < 640 px'te gizlidir (Faz 8'den); önizleyici mobilde yoktur.
5. Mobil Genel bakışta (390 px) kapsam şeridi üç satır dikey yer kaplar; ana sayı Faz 8'e göre ~180 px aşağıda.
6. Kenney dokusunun `NEAREST` → doğrusal örneklemesi harita modellerine de uygulandı; renk paleti şeritlerinin sınırına çok
   yakın UV'lerde komşu şeritle hafif harmanlama mümkündür (gözle fark edilmedi).
7. Altlık karoları OpenFreeMap'e bağlıdır (Faz 8 ile aynı).

## 13. Graphify

`graphify update .` (AST, kurulum korunarak): **2.830 düğüm, 7.270 kenar, 131 topluluk** (Faz 8: 2.722 / 7.036 / 129).
`graphify diagnose multigraph`: doğrulanmamış kod düğümü 0, eksik uç 0, sarkan uç 0, yinelenen kenar 0. `graphify query`
yeni düğümleri buluyor (`ModelPreview()`, `fitDistance()`, `disposeObject()`, `smoothTextureSampling()`,
`centroidRadius()`). Topluluk adları LLM ile yeniden etiketlenmedi (API anahtarı gerekir).

## 14. Git

Commit: `style: refine SafeRoute 3D visual experience`. Büyük veri, `frontend/dist`, `test-results/` ve regresyon çalışma
çıktılarının ekran görüntüleri Git dışındadır.
