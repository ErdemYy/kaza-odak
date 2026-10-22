# Kaza Odak — Marka Geçişi ve Sürüm Cilası

> Tarih: 2026-10-22 · Temel commit: `790d469` (Faz 8B) · Önceki ad: **SafeRoute 3D**
> Yeni ad: **Kaza Odak** — *Makine Öğrenmesi ile Trafik Kazalarının Mekânsal Analizi ve 3D Görselleştirilmesi*
> Makine öğrenmesi sonuçları, veri setleri, deney kimlikleri, manifestler, SHA-256 özetleri ve 3D sahne **değişmedi**.
> Kanıtlar: [`reports/kaza-odak/`](../../reports/kaza-odak/).

## 1. Marka ve logo

- **Simge:** Faz 8 "Kaçınan rota" geometrisi birebir korundu (`scripts/phase8_brand.py` `cand_a`).
- **Marka kilidi:** "Kaza" (metin rengi) + "Odak" (rota mavisi), Plus Jakarta Sans ExtraBold; Faz 8 kilidiyle aynı punto
  ve taban çizgisi. SVG'ler `scripts/kaza_odak_brand.py` ile glif yollarından üretilir (`<text>`, yazı tipi bağımlılığı,
  dış kaynak yok): `assets/brand/kaza-odak-{logo,logo-on-dark,logo-on-light,logo-mono,mark,mark-light,mark-mono,app-icon}.svg`.
- **Favikon:** geometri aynı; yalnızca `<title>`/`aria-label` "Kaza Odak". PNG simgeler (`icon-32`, `icon-180`) yazı
  içermediği için değişmedi.
- Faz 8'in `saferoute-*.svg` dosyaları `assets/brand/` altında tarihsel sürüm olarak kaldı; uygulamanın dağıttığı
  `frontend/public/brand/` kopyaları yeni dosyalarla değiştirildi.

## 2. Güncellenen kullanıcıya görünen alanlar

| Alan | Önce | Sonra |
|---|---|---|
| Kenar çubuğu (açık) | SafeRoute **3D** · "NYC kaza analitiği" | Kaza **Odak** · "Mekânsal kaza analizi"; üzerine gelince ad + akademik alt başlık ipucu |
| Kenar çubuğu (daraltılmış) | simge, ad "SafeRoute 3D" | simge, erişilebilir ad "Kaza Odak"; ipucunda ad + alt başlık |
| Mobil üst çubuk / çekmece | SafeRoute 3D | Kaza Odak; çekmecede tam akademik alt başlık görünür |
| Sekme başlığı | "… · SafeRoute 3D" | "… · Kaza Odak" (`document.title`), `index.html` başlık, açıklama, `application-name` |
| Genel bakış üst satırı | "NYC Motorlu Araç Kazaları" | "Kaza Odak · NYC motorlu araç kazaları" |
| Dışa aktarılan rapor başlıkları | "SafeRoute 3D — …" | "Kaza Odak — …" (`analytics/api.py`) |
| API belgesi başlığı (`/docs`) | "SafeRoute 3D — Faz 4 katman API'si" | "Kaza Odak — katman API'si" |
| CLI yardım metni | "SafeRoute 3D veri hattı" | "Kaza Odak veri hattı" (program adı `saferoute` aynı) |
| Başlat/durdur betiği mesajları | "SafeRoute 3D hazır …" | "Kaza Odak hazır …" |
| README (kök, ön yüz, teslim) | SafeRoute 3D | Kaza Odak + geçiş notu |

**Bilinçli olarak değiştirilmeyenler:** Python paketi ve komut `saferoute`, `start_saferoute.ps1`/`stop_saferoute.ps1`
dosya adları, `.saferoute/` çalışma dizini, `__saferoute` test kancası, rapor şeması `saferoute.report/1`, veri edinim
User-Agent'ı (`SafeRoute3D/0.1`, edinim kayıtlarıyla tutarlı), deney/model kimlikleri, JSON anahtarları, manifestler,
dosya yolları, faz raporları (`docs/phase1–8B`, tarihsel kayıt) ve git geçmişi. Kaynak kod yorumlarındaki eski ad
yalnızca marka bileşenlerinde güncellendi.

## 3. Düzeltilen kalite sorunları

1. **Gece/Gündüz erişilebilir adı (WCAG 2.5.3):** ad artık görünen metinle başlıyor — "Gece modu — gündüz moduna geç" /
   "Gündüz modu — gece moduna geç" (+ `title` ipucu). axe `label-content-name-mismatch` 0. Faz 8 `E06` beklentisi
   ("Gece moduna geç") yeni doğru davranışa göre güncellendi ve görünen metin kontrolü eklendi; Faz 8B testindeki
   axe istisnası kaldırıldı.
2. **GLB önizleyicide kalan doku kaydı:** kaynağı bulundu ve deneyle doğrulandı. three.js r186, fiziksel tabanlı
   malzemeler için modül düzeyinde **tek** bir DFG arama tablosu oluşturur (`src/renderers/shaders/DFGLUTData.js`,
   `getDFGLUT`, 16×16 RG16F ≈ 1 KB) ve tüm çiziciler paylaşır; hiç serbest bırakılmaz. Deney: aynı taksi modeli
   `MeshStandardMaterial` ile çizildiğinde kapanışta kalan kayıt **1**, `MeshBasicMaterial`'a çevrildiğinde **0**.
   Model değiştirildikçe sayaç büyümüyor (taksi → sedan → taksi: sabit), geometri 0'a iniyor ve önizleme bağlamı
   `forceContextLoss` ile kapatılıyor. **Gerçek bellek sızıntısı yok**; kod yorumu ve test açıklaması güncellendi.
3. **390 px Genel bakış kayması:** kapsam hücreleri mobilde de üç sütun (değer sarılır, ikincil alt satır ≥ 640 px'te).
   Ana sayının konumu Faz 8: ~472 px → Faz 8B: ~650 px → **456 px**; kapsam bloğu 159 px; yatay taşma 0.
   Güncellik uyarısı, analiz kapsamı ve model dönemi mobilde görünür kaldı (testle doğrulandı).
4. **Gündüz bina kontrastı:** `#AAB7C8 / #BCC7D5 / #D3DBE6` → `#A2AFC1 / #B3BFCE / #C5CFDB`, gündüz ışığı 0,42 → 0,48.
   WCAG kontrastı (zemin `#E8EDF3`): taban 1,73 → 1,89, orta 1,45 → 1,58, tepe **1,19 → 1,34** (Faz 8 tek ton 1,28).
   Aynı kamerayla önce/sonra (`reports/kaza-odak/screenshots/gunduz-karsilastirma-*.jpg`): 3D Manhattan'da yüzeyler daha
   belirgin, yollar binalardan daha iyi ayrışıyor; orta yakınlıkta fark yok denecek kadar az. Kötüleşme görülmedi,
   **korundu**. Zemin `#E8EDF3` (Faz 4 sözleşmesi) değişmedi.

## 4. Akademik teslim dosyaları

Yeni: `deliverables/Kaza_Odak_Sunum.pptx` (17 slayt, notlu, yazı tipleri gömülü), `Kaza_Odak_Proje_Raporu.docx` /
`.pdf` (32 sayfa). Güncellenen: `SUNUM_KONUSMA_NOTLARI.md`, `CANLI_DEMO_REHBERI.md`, `HOCA_SORULARI_VE_CEVAPLARI.md`,
`ONEMLI_KODLAR_VE_ACIKLAMALAR.md`, `README.md`. Korunan: `SafeRoute_3D_*.pptx/.docx/.pdf` (yerinde, dokunulmadı) ve
Markdown belgelerinin SafeRoute 3D kopyaları (`deliverables/gecmis_surum_saferoute_3d/`).

Üretim Faz 7 betikleriyle yapıldı (`scripts/phase7_build_deck.py`, `phase7_build_report.py`); marka değerleri
`scripts/teslim_marka.py`'de. Arayüz görüntüleri Kaza Odak markalı güncel uygulamadan yeniden çekildi (Faz 6 demo
senaryosu → `reports/kaza-odak/phase6/screenshots/`); görüntü yoksa betik eski görüntüye sessizce dönmez.

Office son işlemi: `ExportAsFixedFormat` otomasyon oturumunda iki kez süresiz bekledi (DOCX kaydı tamamlanmıştı; asılı
`/Automation` Word örneği kapatıldı). PDF adımı `SaveAs2` (wdFormatPDF) ile değiştirildi ve betik `-Prefix` ile hem
yeni hem geçmiş sürümü işleyebilir hâle getirildi; ilk denemede `Join-Path` sonucunun COM'a sarmalı nesne olarak
geçmesi hatası düzeltildi.

Doğrulama: kod blokları 59/59 (geçmiş + yeni sürüm), uyuşmazlık 0; PDF'te tüm yazı tipleri gömülü; "SafeRoute" yalnızca
rapor kapağındaki "Önceki proje adı" satırında; sunum metni ve notlarında yok. Sunum PowerPoint ile açılıp 17 slayt
PNG'ye aktarıldı, rapor 32 sayfa görüntüye çevrildi ve incelendi (`reports/kaza-odak/teslim/`): kapak, içindekiler,
altlıklar ve görseller doğru; taşma yok. Ara bulgu düzeltildi: 5. slaytın kaynak satırı görüntüyü hâlâ "Faz 6 demo"
diye anıyordu.

## 5. Test sonuçları (son derleme, yeniden başlatılmış sunucu)

| Paket | Sonuç | Çıktı |
|---|---|---|
| Backend pytest | **210 / 210** (tek başına) | — |
| Vitest | **102 / 102** | — |
| TypeScript `tsc -b` / `vite build` | temiz / başarılı | — |
| Playwright Kaza Odak (`e2e/kaza-odak.spec.ts`, yeni) | **4 / 4** | `reports/kaza-odak/regresyon/kaza-odak.log`, `reports/kaza-odak/kaza_odak_results.json` |
| Playwright Faz 8B | **3 / 3** (axe 3D Şehir + Genel bakış: 0 ihlal, istisnasız; isabet alanı 53/53) | `regresyon/phase8b*` |
| Playwright Faz 8 | **19 / 19 — 125 / 125 etkileşim** | `regresyon/phase8*` |
| Playwright Faz 6 / yeniden başlatma | **12 / 12** / **1 / 1** | `regresyon/phase6*` |
| Playwright Faz 5 / Faz 4 | **11 / 11** / **11 / 11** | `regresyon/phase5*`, `regresyon/phase4*` |
| Teslim kod blokları | **59 / 59** | `deliverables/dogrulama/kod_dogrulama.json` |
| Graphify | 2.968 düğüm, 7.463 kenar, 132 topluluk; eksik/sarkan/yinelenen kenar 0 | `graphify-out/` |

Marka nedeniyle güncellenen test beklentileri (yalnızca metin): Faz 8 `G01`, `G03-*`, mobil çekmece wordmark'ı ve
sekme başlığı ("SafeRoute 3D" → "Kaza Odak"); Faz 8 birim testlerinde logo/wordmark adı ve alt satır denetimi. Davranış
değişikliğiyle güncellenen: Faz 8 `E06` tema düğmesi adı (WCAG 2.5.3). Hiçbir test silinmedi veya gevşetilmedi;
Faz 8B'deki axe istisnası **kaldırıldı** (denetim sıkılaştı). Yeni testler: gündüz tepe kontrastı (Vitest), Kaza Odak
tarayıcı paketi (sekme başlıkları, marka kilidi, ipucu, favikon, meta, tema adı her iki durumda, GLB önizleme, 390 px).

## 6. Görsel kontroller

`reports/kaza-odak/screenshots/`: beş ekran (`ekran-overview|explorer|lab|models|data.png`), kenar çubuğu açık ve
daraltılmış + ipucu, mobil Genel bakış ve mobil menü, gündüz modu, GLB önizleme, gündüz önce/sonra.

## 7. Bilinen sınırlılıklar

1. DFG arama tablosu kaydı three.js'in tasarımı gereği paylaşılır ve sayaçta 1 olarak kalır (gerçek sızıntı değil).
2. Faz 1–8B raporları, ekran görüntüleri ve `docs/phase8/LOGO_KULLANIM_KURALLARI.md` eski adı içerir (tarihsel kayıt).
3. Rapor ve sunumun metni Faz 7 içeriğidir; Faz 8/8B arayüz özellikleri (ör. GLB önizleyici) belgelerde anlatılmaz,
   yalnızca güncel ekran görüntülerinde görünür.
4. Office son işlemi Windows'ta Word/PowerPoint gerektirir.
