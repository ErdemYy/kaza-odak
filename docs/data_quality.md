# Veri Kalitesi Raporu — Faz 1

**Anlık görüntü:** `snapshot_20261019T155113Z` (2.269.187 satır × 29 sütun)

Tüm değerler `saferoute eda` ile ölçülmüştür. Tam tablolar `reports/phase1/EDA_RAPORU.md`, sütun bazlı eksikler ise `docs/data_dictionary.md` dosyasındadır. Bu fazda **hiçbir kayıt silinmedi, düzeltilmedi veya doldurulmadı**.

## Özet

| Konu | Bulgu | Önem | Faz 2 eylemi |
|---|---|---|---|
| Kimlik | `collision_id` tümü dolu, tam sayı ve benzersiz (2.269.187); birebir tekrar satır 0 | — | Kimlik olarak korunacak |
| Tarih | `crash_date` eksik 0, ayrıştırılamaz 0 | — | — |
| Saat | `crash_time` eksik 0, geçersiz 0; **tam 00:00 olan 24.566 kayıt** (%1,08) | Orta | `time_is_midnight_placeholder` bayrağı |
| Koordinat | Geçerli 2.020.640 (%89,05); eksik 240.806 (%10,61); sıfır 7.591 (%0,33); kutu dışı 150 (%0,01); ayrıştırılamaz 0 | Yüksek | Dışlama nedeniyle sütun, poligon kontrolü |
| Koordinat tekrarı | 2.020.640 geçerli noktada 349.124 farklı konum (ortalama 5,8 kayıt/konum) | Yüksek (modelleme) | Ağırlıklı benzersiz nokta stratejisinin değerlendirilmesi |
| İlçe | Eksik 691.375 (%30,47), beklenmeyen etiket 0; **487.026'sının koordinatı geçerli** | Yüksek | Geometrik ilçe çıkarımı |
| Posta kodu | Eksik 691.703 (%30,48), dolu olanların hepsi 5 haneli | Düşük | Yalnızca filtre/betimleme |
| Yaralı/ölü | Negatif ve ayrıştırılamaz değer yok; `persons_killed` 8.913, `persons_injured` 18 kayıtta eksik | Orta | Eksik toplamlar alt kırılımdan türetilmeyecek, işaretlenecek |
| İç tutarlılık | Yaralı: kişi > alt toplam 10.687, kişi < alt toplam 227. Ölü: sırasıyla 78 ve 6 | Orta | Tutarsızlık bayrağı |
| Araç türü | 3.149 ham farklı değer, normalizasyon sonrası 2.168; çoklu adlandırma şemaları | Yüksek (filtre) | Belgelenmiş kategori eşlemesi |
| Faktör | Araç 1 için `Unspecified` 756.643 (%33,34), eksik 8.202 | Orta | "Bilinmiyor" olarak ayrı ele alınacak |
| Metin | Sokak adlarında yaygın baş/son boşluk (`on_street_name` 1.412.004 kayıt) | Düşük | Kırpma + büyük harf |
| Zamana bağlı kalite | Geçerli koordinat oranı 2012–2016'da %83,6–85,0, 2017'de %93,90; ilçe doluluğu 2015'te %75,09, 2017'de %61,88 | Orta | Yıllar arası karşılaştırmada not |
| Güncellik | Kaynak 125 gündür güncellenmemiş (beyan: günlük); 2026-06 kısmi ay | Yüksek (iletişim) | Arayüzde güncellik uyarısı |

## Koordinat sınıflandırması

Sınıflar birbirini dışlar ve toplamları satır sayısına eşittir. Öncelik sırası şöyledir:

1. **Eksik:** enlem veya boylam boş.
2. **Ayrıştırılamaz:** dolu ama sayı değil.
3. **Sıfır:** enlem veya boylam 0.
4. **NYC kutusu dışı:** enlem 40,4774–40,9176, boylam −74,2591 – −73,7004 aralığının dışında.
5. **Geçerli.**

Sıfır koordinatlar "konum bilinmiyor" anlamına gelen sahte bir değerdir ve geçersiz sayılır. **Eksik koordinatlar sıfırla doldurulmaz.**

Kutu yalnızca kaba bir kontroldür ve **ilçe ataması için kullanılmaz**: New Jersey'nin bazı kısımlarını ve su alanlarını da kapsar. Yoğunluk haritasında kara sınırı dışında tekil noktalar görülüyor. Kesin kontrol Faz 2'de DCP ilçe poligonlarıyla yapılacak.

**İlçe × koordinat çapraz tablosu:**

| İlçe kaydı | Geçerli | Eksik | Sıfır | Kutu dışı |
|---|---:|---:|---:|---:|
| Manhattan | 337.018 | 10.097 | 1.370 | 0 |
| Brooklyn | 494.301 | 10.437 | 2.066 | 2 |
| Queens | 412.087 | 8.722 | 1.600 | 0 |
| Bronx | 226.052 | 6.969 | 1.067 | 0 |
| Staten Island | 64.156 | 1.650 | 218 | 0 |
| *İlçe eksik* | 487.026 | 202.931 | 1.270 | 148 |

Kutu dışı 150 kaydın 148'inin ilçe alanı da boş.

## Gözlemlenen ama nedeni belirlenemeyen örüntüler

- **2020 düşüşü:** Kayıt sayısı Mart–Nisan 2020'de keskin biçimde düşüyor (aylık 13.704 → 11.079 → 4.129). Zamanlama COVID-19 dönemiyle örtüşüyor, ancak bu veriyle nedensellik kurulamaz.
- **Yeni düzey:** Sonraki yıllarda yıllık sayı 2019 öncesi düzeyin belirgin biçimde altında kalıyor (2018: 231.564, 2025: 85.546). Bu fark kaza sıklığındaki gerçek bir değişimden de, raporlama/kayıt uygulamasındaki bir değişiklikten de kaynaklanabilir; veri seti ikisini ayırt etmeye yetmiyor.
- **2016/2017 kırılması:** Koordinat ve ilçe doluluk oranları bu yıllarda değişiyor.

Bu örüntüler kümeleme sonuçlarının yıllar arası karşılaştırılmasını doğrudan etkiler. Faz 3'te zaman dilimleri ayrı ayrı kümelenecek ve karşılaştırmada bu kalite farkları raporlanacak.

## Kapsam ve yorum sınırlılıkları

- Veri yalnızca **polise raporlanmış** kazaları içeriyor; raporlanmayan kazalar görünmez.
- Yoğunluk maruziyete (trafik hacmi, yaya/bisiklet sayısı) göre normalize edilmediği için **risk değildir**.
- İlk yıl (2012, Temmuz–Aralık) ve son yıl (2026, Ocak–11 Haziran) kısmi olduğundan yıllık karşılaştırmalara tam yıl gibi katılmamalıdır.
