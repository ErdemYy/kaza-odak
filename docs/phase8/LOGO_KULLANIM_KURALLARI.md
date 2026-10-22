# SafeRoute 3D — Logo Kullanım Kuralları (Faz 8)

> Kaynak: `scripts/phase8_brand.py` (tekrarlanabilir üretim) → `assets/brand/`. Uygulamada kullanılan kopyalar:
> `frontend/public/favicon.svg`, `frontend/public/brand/`, satır içi React bileşeni `frontend/src/components/brand/Logo.tsx`
> (aynı geometri).

## 1. Kavram

**"Kaçınan rota"** — Şehir ızgarasına (Manhattan sokak düzeni) oturan, kavşak ölçeğindeki bir kaza yoğunlaşmasından
(kırmızı nokta, amber hale) uzaklaşan güvenli bir rota. Başlangıç düğümü dolu, varış düğümü halka: iki analiz noktası
rota ile birbirine bağlıdır. Sıcak nokta ızgaranın bir kesişimine (kavşak) yerleşir; bu, projenin ana DBSCAN modelinin
kavşak ölçeğinde (eps = 25 m) kronik yoğunlaşmaları bulmasıyla tutarlıdır.

Simge risk tahmini veya "güvenli rota önerisi" iddia etmez; proje bir kümeleme analizidir. Simge markanın fikrini
(nerede yoğunlaşıyor → nasıl farkında olunur) görselleştirir.

## 2. Varlıklar

| Dosya | Kullanım | Boyut |
|---|---|---:|
| `saferoute-logo.svg` | Ana logo (simge + wordmark), koyu zemin, şeffaf | ~10 KB |
| `saferoute-logo-on-dark.svg` | Ana logo, `#0B1120` zeminli (sunum, belge kapağı) | ~10 KB |
| `saferoute-logo-on-light.svg` | Açık zemin varyantı (beyaz zemin, koyu metin, kontrastı artırılmış tonlar) | ~10 KB |
| `saferoute-logo-mono.svg` | Tek renk (`currentColor`) — baskı, damga, tek renkli ortamlar | ~10 KB |
| `saferoute-mark.svg` | Yalnız simge, koyu zemin, şeffaf | < 1 KB |
| `saferoute-mark-light.svg` | Yalnız simge, açık zemin | < 1 KB |
| `saferoute-mark-mono.svg` | Yalnız simge, tek renk (`currentColor`) | < 1 KB |
| `saferoute-app-icon.svg` | Uygulama simgesi (karo zeminli, ızgaralı) | < 1 KB |
| `saferoute-sidebar.svg` | Küçük kenar çubuğu sürümü (karo zeminli, ızgarasız) | < 1 KB |
| `favicon.svg` | Favikon (kenar çubuğu sürümüyle aynı) | < 1 KB |
| `icon-32.png`, `icon-180.png` | SVG favikonu desteklemeyen tarayıcılar / apple-touch-icon | 1–7 KB |
| `candidates/` | Üç tasarım adayı ve karşılaştırma sayfası | — |

## 3. Renkler

| Rol | Koyu zemin | Açık zemin | Not |
|---|---|---|---|
| Rota, düğümler, "3D" | Cyan `#38BDF8` | `#0284C7` | Açık zeminde `#38BDF8` grafik kontrastı (≈2,1:1) yetersiz; `#0284C7` ≈4,1:1 |
| Sıcak nokta | Hotspot Red `#F87171` | `#DC2626` | Kontrollü vurgu: tek nokta, parlama yok |
| Sıcak nokta halesi | Amber `#F59E0B` %22 opak | `#D97706` %22 opak | Düz dolgu; bulanıklık/glow değildir |
| Wordmark "SafeRoute" | `#F1F5F9` | `#0B1120` | |
| Karo zemini | `#111C30` | `#F1F5F9` | Uygulama simgesi / favikon |
| Izgara | `#1E2D49` | `#DCE3EC` | Yalnızca ≥ 48 px'te |
| Sayfa zemini | Background `#0B1120` | `#FFFFFF` | |

Gradyan, neon, dış parlama, gölge veya 3D kabartma **kullanılmaz**.

## 4. Tipografi

- Wordmark: **Plus Jakarta Sans ExtraBold (800)**, harf aralığı −0,015 em, "SafeRoute" ile "3D" arasında tek boşluk;
  "3D" vurgu rengindedir. SVG dosyalarında wordmark glif yollarına çevrilmiştir (yazı tipi yüklemesi gerekmez,
  `<text>` öğesi yoktur).
- Alt başlık / slogan (ör. "NYC kaza analitiği"): **Manrope**, 11–13 px, ikincil metin rengi; logonun parçası değildir.

## 5. Boyut ve boşluk

- **En küçük boyut:** simge 16 px (favikon); simge + wordmark 96 px genişlik. 32 px ve altında ızgarasız sürüm kullanılır
  (`saferoute-sidebar.svg` / `favicon.svg`): ince ızgara çizgileri küçük boyutta piksel gürültüsü üretir.
- **Koruma alanı:** logonun her yanında simge yüksekliğinin en az ¼'ü (48 birimlik simgede 12 birim) boş bırakılır.
- Wordmark simgenin dikey ortasına hizalıdır; simge ile metin arası simge genişliğinin ¼'üdür.

## 6. Yapılmaması gerekenler

- Renkleri değiştirmek, rotayı veya sıcak noktayı farklı renge boyamak (tek renk sürümü hariç).
- Simgeyi döndürmek, eğmek, oranını bozmak; perspektif/3D efekt, gölge, parlama eklemek.
- Kırmızı noktayı "tehlike uyarısı" veya risk puanı göstergesi gibi sunmak.
- Wordmark'ı başka yazı tipiyle yeniden yazmak veya "3D"yi ayırmak.
- Düşük kontrastlı zeminde (ör. orta ton fotoğraf) koyu zemin sürümünü kullanmak: bu durumda `on-dark` (zeminli)
  veya tek renk sürüm kullanılır.

## 7. Uygulamadaki kullanım

| Yer | Varlık |
|---|---|
| Masaüstü kenar çubuğu (açık) | `LogoMark` 32 px (karo, ızgarasız) + wordmark (Plus Jakarta Sans 800, 15,5 px) + "NYC kaza analitiği" |
| Masaüstü kenar çubuğu (daraltılmış) | `LogoMark` 30 px, `aria-label="SafeRoute 3D"` |
| Mobil üst çubuk | `LogoMark` 30 px + ekran başlığı |
| Mobil gezinme çekmecesi | `LogoMark` + wordmark |
| Tarayıcı sekmesi | `favicon.svg` (+ `icon-32.png`, `apple-touch-icon` için `icon-180.png`), `theme-color #0B1120` |

## 8. Erişilebilirlik ve güvenlik

- Her SVG dosyası `role="img"`, `aria-label` ve `<title>` içerir; uygulamada wordmark metin olarak okunur
  ("SafeRoute 3D"), simge yanında metin varsa dekoratiftir (`aria-hidden`).
- SVG'lerde betik, dış kaynak (`href`, `xlink:href`, görüntü, yazı tipi), `foreignObject` veya olay özniteliği yoktur;
  yalnızca `path`, `circle`, `rect`, `g`, `title` öğeleri kullanılır.
- Ölçeklenebilir: `viewBox` tabanlı, sabit piksel boyutu yoktur.
- Yazı tipi lisansı: Plus Jakarta Sans — SIL Open Font License 1.1 (`assets/brand/OFL-PlusJakartaSans.txt`).
