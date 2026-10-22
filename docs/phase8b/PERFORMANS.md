# SafeRoute 3D — Faz 8B Performans Ölçümü

> Betik: Faz 6 `frontend/e2e-perf/map.perf.ts` (değiştirilmedi), proje `gpu-varsayilan`.
> Çizici her çalıştırmada `WEBGL_debug_renderer_info` ile doğrulandı:
> **ANGLE (NVIDIA GeForce RTX 4050 Laptop GPU, Direct3D11)** — donanım WebGL, yazılım (SwiftShader) değil.
> Çıktılar: `reports/phase8b/perf/before/` (oturum başı temel), `reports/phase8b/perf/ab/{before,after}-{1,2}/`.

## Yöntem

Önce/sonra karşılaştırması **aynı oturumda, aynı sunucu ve GPU ile dönüşümlü** yapıldı: değişiklik öncesi derleme
(`fc7c176`, ayrı saklandı) ve Faz 8B derlemesi sırayla `frontend/dist`'e konup önce-1 → sonra-1 → önce-2 → sonra-2
ölçüldü (16:06–16:09 UTC). Bu, Faz 8 raporundaki sayılarla (başka gün, başka sistem yükü) doğrudan kıyaslamaktan daha
güvenilirdir.

## Sonuçlar

| Ölçüm | Faz 8 raporu | Önce-0 (oturum başı) | Önce-1 | Sonra-1 | Önce-2 | Sonra-2 |
|---|---:|---:|---:|---:|---:|---:|
| Kaza verisi hazır (`load_status_ready`) | 0,98 sn | 0,99 sn | 0,99 sn | 1,11 sn | 0,91 sn | 1,00 sn |
| İlk harita boşta | 1,98 sn | 2,18 sn | 2,36 sn | 2,94 sn | 2,11 sn | 2,33 sn |
| 3D döndürme FPS | 143,6 | 99,6 | 109,1 | 100,8 | 95,1 | 94,8 |
| Döndürme kare süresi medyan / p95 | — / 7 ms | 7 / 14 ms | 7 / 13,9 ms | 7 / 14 ms | 13,8 / 14 ms | 13,8 / 14 ms |
| Yakınlaştırma FPS | 143,2 | 143,0 | 143,0 | 137,2 | 142,5 | 135,3 |
| Uzaklaştırma FPS | 143,1 | 138,2 | 143,1 | 137,0 | 138,6 | 128,7 |
| Yakın/uzak medyan kare | — | 6,9 ms | 6,9 ms | 6,9 ms | 6,9 ms | 6,9–7,0 ms |
| > 50 ms kare (tüm hareketler) | 0 | 0 | 0 | 0 | 0 | 0 |
| Küme seçimi → GLB sahnesi hazır | 3,64 sn | 3,85 sn | 3,70 sn | 3,85 sn | 3,75 sn | 3,88 sn |
| WebGL bağlam kaybı → toparlanma | 0,87 sn | 1,20 sn | 1,11 sn | 1,14 sn | 1,05 sn | 1,17 sn |

## Yorum

- **Kare süresi:** yakınlaştırma/uzaklaştırma ve döndürmede medyan kare süresi önce ve sonra **aynı** (6,9 ms ≈ 144 Hz
  ekran tavanı; döndürmede iki turda 7 ve 13,8 ms — ikinci turda her iki sürüm de 72 Hz'e inmiş, yani sürümden bağımsız).
  Uzun kare (> 50 ms) hiçbirinde yok. Sonra sürümünde yakın/uzak FPS 3–7 % daha düşük; bu fark medyanda değil,
  ara sıra kaçırılan dikey senkron karelerinde (p95 7 → 13,8 ms, ikinci tur). Olası nedenler: seçim/hover halka
  katmanları, zoom'a bağlı kontur ifadesi, üç duraklı bina rengi. Fark ölçüm gürültüsünün (önce-1/önce-2 arasında
  döndürmede 109 ↔ 95 FPS) aralığında kaldığı ve uzun kare olmadığı için **belirgin kötüleşme sayılmadı, efekt geri
  alınmadı**; kesin neden katman katman ölçülmedi.
- **Veri hazır olma:** sonra 1,00–1,11 sn, önce 0,91–0,99 sn (~+0,1 sn). Faz 8 referansının (0,86–0,98 sn) biraz
  üstünde. Paket boyutu artışı (sıkıştırılmamış: ana parça 385,7 → 403,3 kB, `three` 639,1 → 660,5 kB, CSS 124,3 → 130,4 kB, Genel bakış 12,2 → 15,4 kB) olası katkıdır; doğrulanmadı.
- **GLB sahnesi:** ~+0,13 sn, iki turda tutarlı. Olası neden: doğrusal + mipmap örneklemeye geçiş (`smoothTextureSampling`);
  doğrulanmadı.
- **WebGL toparlanma:** 1,05–1,11 ↔ 1,14–1,17 sn; fark küçük. Faz 8'deki 0,87 sn bu oturumun önce ölçümlerinde de
  tekrarlanmadı (1,05–1,20 sn) — oturumlar arası değişkenlik.
- **Faz 8 referansıyla:** bu oturumda değişiklik öncesi derleme de döndürmede 95–109 FPS verdi (Faz 8: 143,6). Bu fark
  Faz 8B'den değil, ölçüm koşullarından kaynaklanır; bu nedenle karar dönüşümlü A/B'ye dayandırıldı.
- **JS yığını:** 62–419 MB arasında sürümden bağımsız dalgalanıyor (ölçüm anı çöp toplama zamanlamasına bağlı); önce/sonra
  karşılaştırması için **güvenilir değil**, sonuç çıkarılmadı.

## GLB önizleyici maliyeti

- Ayrı, küçük (200 px yükseklik) bir WebGL bağlamı; `powerPreference: low-power`, piksel oranı ≤ 2.
- İstek üzerine çizim: kare yalnızca kamera hareketi, sönümleme veya model değişiminde çizilir; hareketsizken 0 kare
  (`__saferoutePreview.state().frames` testte yalnızca sürükleme sonrası artar).
- Yalnızca panel açıkken vardır; model başına GPU sayaçları sabittir (4 geometri / 2 doku), panel kapanınca bağlam
  bırakılır. Önizleyici açıkken harita kare süresi ayrıca ölçülmedi.
- PMREM ortam haritası denendi ve kaldırıldı (gereksiz ön işleme + bırakılmayan iç render hedefi).

## Ölçülemeyen / yapılmayan

- AMD tümleşik GPU ve SwiftShader bu fazda ölçülmedi (yalnız `gpu-varsayilan`).
- Hover kartının çizim maliyeti ayrıca ölçülmedi (kare başına en çok bir `queryRenderedFeatures`, tek Popup).
