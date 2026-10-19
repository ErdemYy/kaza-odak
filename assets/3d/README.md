# 3D varlık kaydı (Faz 4)

Makinece okunabilir kayıt: [`frontend/public/models/registry.json`](../../frontend/public/models/registry.json)
(kaynak arşiv SHA-256, ZIP içi yol, orijinal ve optimize dosya özetleri, üçgen/doku ölçümleri, ölçek, eksenler).
Ölçüm raporu: [`reports/phase4/asset_optimization.json`](../../reports/phase4/asset_optimization.json).
Üretim: `cd frontend && npm run assets` (ZIP'ler salt-okunur okunur; orijinaller değişmez).

`downloads/` klasöründeki ZIP paketleri üçüncü taraf dağıtımıdır ve git dışında tutulur (`.gitignore`).

## Kaynak paketler

| Arşiv | Paket | Boyut | SHA-256 | Yazar | Lisans | Durum |
|---|---|---:|---|---|---|---|
| `kenney_car-kit.zip` | Car Kit 2.0 — https://kenney.nl/assets/car-kit | 3.668.013 B | `f8a69b83fbf94c98…` | Kenney | CC0 1.0 | Kullanıldı |
| `kenney_city-kit-roads.zip` | City Kit (Roads) 2.2 — https://kenney.nl/assets/city-kit-roads | 2.852.289 B | `374a4552115cbd11…` | Kenney | CC0 1.0 | Kullanıldı |
| `Cars Bundle-glb.zip` | 7 araç GLB'si | 1.228.676 B | — | **Belirsiz** | **Belirsiz** | **Kullanılmadı** |

**Lisans doğrulaması:** Kenney paketlerinin içindeki `License.txt` CC0 1.0 (kamu malı adanması) beyan eder; atıf zorunlu
değildir, isteğe bağlı olarak "Kenney" belirtilir (uygulamada ve bu belgede belirtildi). `Cars Bundle-glb.zip`
içinde lisans, yazar veya kaynak dosyası yoktur; GLB meta verisi yalnızca `obj2gltf` üreticisini içerir. Lisansı
doğrulanamadığı için bu paket kullanılmadı.

## Seçilen modeller

Seçim önceliği: görsel kalite → tutarlı sanat stili (tüm modeller tek yazar/tek palet dokusu) → lisans (CC0) →
düşük poligon → WebGL performansı → animasyona uygunluk (araçlarda tekerlekler ayrı düğüm).

| Model | Dosya | Paket | Orijinal GLB (doku harici) | Doku gömülü referans | Optimize (LOD0) | Üçgen LOD0 / LOD1 | Gerçek boy |
|---|---|---|---:|---:|---:|---:|---|
| Otomobil (sedan) | `sedan.glb` | Car Kit | 168,2 KB | 177,3 KB | 30,6 KB (−%83) | 2.032 / 1.596 | 4,8 m uzunluk |
| Taksi | `taxi.glb` | Car Kit | 171,5 KB | 180,6 KB | 29,9 KB (−%83) | 2.072 / 1.630 | 5,0 m uzunluk |
| SUV | `suv.glb` | Car Kit | 202,7 KB | 211,3 KB | 34,7 KB (−%84) | 2.474 / 1.947 | 4,9 m uzunluk |
| Kamyonet | `truck.glb` | Car Kit | 172,2 KB | 181,3 KB | 31,2 KB (−%83) | 2.082 / 1.618 | 5,6 m uzunluk |
| Teslimat kamyonu | `delivery.glb` | Car Kit | 234,7 KB | 243,7 KB | 33,7 KB (−%86) | 2.476 / 1.719 | 6,5 m uzunluk |
| Trafik lambası | `traffic-light.glb` | City Kit (Roads) | 19,9 KB | 30,8 KB | 16,3 KB (−%47) | 212 / — | 4,6 m yükseklik |
| DUR levhası | `road-sign-stop.glb` | City Kit (Roads) | 10,5 KB | 21,4 KB | 15,1 KB (−%29) | 104 / — | 2,4 m yükseklik |
| Uyarı levhası | `road-sign-warning.glb` | City Kit (Roads) | 11,2 KB | 22,1 KB | 15,2 KB (−%31) | 104 / — | 2,4 m yükseklik |
| Bariyer | `construction-barrier.glb` | City Kit (Roads) | 6,9 KB | 17,7 KB | 14,3 KB (−%19) | 60 / — | 1,0 m yükseklik |
| Trafik konisi | `construction-cone.glb` | City Kit (Roads) | 6,9 KB | 17,7 KB | 14,4 KB (−%19) | 66 / — | 0,7 m yükseklik |

Yüzdeler doku gömülü referansa göredir (orijinal GLB'ler dokuyu `Textures/colormap.png` olarak harici tutar ve tek
başına yüklenemez; küçük donatılarda optimize dosyanın orijinal GLB'den büyük görünmesinin nedeni gömülü ~11 KB dokudur).
Kitte otobüs modeli yoktur; ağır taşıt olarak kamyonet ve teslimat kamyonu kullanıldı.

## Optimizasyon

Araç: gltf-transform 4.5.1 + meshoptimizer 1.3.0 (Node.js). Blender kurulu değildir ve kullanılmadı; OBJ/FBX dönüşümü
gerekmedi (paketlerde hazır GLB var).

1. Harici doku GLB'ye gömülür (tek dosya, kendi başına yüklenebilir).
2. `dedup` (özdeş tekerlek mesh'leri ve erişimciler paylaşılır), `prune` (kullanılmayan düğüm/erişimci), `weld` (indeksleme),
   `reorder` (köşe önbelleği), `quantize` (KHR_mesh_quantization, 16 bit konum), `meshopt` (EXT_meshopt_compression).
3. Düğümler birleştirilmez: araç tekerlekleri (`wheel-*`) ayrı düğüm olarak dönüş animasyonuna açık kalır.
4. LOD1: araçlar için meshopt sadeleştirme (hedef oran 0,5, hata ≤ %1); uygulamada piksel başına 0,12 m'nin üstünde
   (uzak kamera) LOD1 kullanılır.
5. Doku: 512×512 paletli PNG (~11 KB). Küçültme, palet renklerinde sızma riski taşıdığı için yapılmadı.

**Görsel kalite:** LOD0'da çizilen üçgen sayısı değişmez (ölçüm: önce = sonra); nicemleme hatası model boyutunun
~1/65535'i. Referans (doku gömülü, optimize edilmemiş) modeller `npm run assets` ile `public/models/reference/`
altına üretilir (git dışı). Ön yön ekseni (+Z) tarayıcıda doğrulandı: kuzeye (0°) yönlendirilen taksi güneyden
bakıldığında arka lambalarını, kuzeyden bakıldığında ön ızgarasını gösterir.

**Örnekleme (instancing):** Aynı modelin kopyaları tek şablondan klonlanır ve geometri/doku GPU tamponlarını paylaşır.
Sahnede aynı anda en fazla 6 araç + 2 donatı + 1 inceleme modeli bulunduğundan `InstancedMesh` gerekmedi.
