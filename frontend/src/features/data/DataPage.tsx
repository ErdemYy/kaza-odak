// Veri gezgini: ham 29 ve işlenmiş 87 sütun, temizleme hattı, ilçe çıkarımı, araç normalizasyonu,
// tarih/saat öznitelikleri, 00:00 bayrağı ve model öznitelik setleri. Sayılar Faz 2 özetinden.
import { ArrowDown } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ColumnChart, RowChart } from "../../components/charts";
import { ErrorBlock, LoadingBlock, MetricCard, Note, PageHeader, Section } from "../../components/common";
import { BOROUGH_TR } from "../../lib/camera";
import { fmtInt, fmtNum, fmtPct, trLabel } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { DataDictionary } from "../../lib/types";
import { DataDictionaryTable, toRows } from "./DataDictionary";

const COORD_TR: Record<string, string> = {
  missing: "Koordinat eksik", unparseable: "Ayrıştırılamadı", non_finite: "Sonlu değil", zero: "0,0 (yer tutucu)",
  invalid_range: "Geçersiz enlem/boylam aralığı", outside_nyc_far: "NYC'den uzak (dışlandı)",
  outside_nyc_nearshore: "Kıyıya yakın (dahil, bayraklı)", boundary_ambiguous: "Sınırda belirsiz", valid_in_boundary: "Resmî sınır içinde",
};
const SET_TR: Record<string, string> = {
  A_dbscan_haversine: "A — DBSCAN, kayıt düzeyi", A_dbscan_haversine_weighted: "A — DBSCAN, ağırlıklı benzersiz konum (ana model)",
  B_kmeans_projected: "B — K-Means/HDBSCAN, metre", B_kmeans_projected_weighted: "B — K-Means, ağırlıklı benzersiz konum",
  C_hdbscan_haversine: "C — HDBSCAN, Haversine", D_spatiotemporal_experimental: "D — Uzay-zaman (deneysel)",
  D_spatiotemporal_experimental_no_midnight: "D — Uzay-zaman, 00:00 hariç (duyarlılık)",
};

function Pipeline({ d }: { d: DataDictionary }) {
  const c = d.cleaning;
  const rows = c.rows;
  const coord = Object.entries(c.coordinates).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const b = c.boroughs as Record<string, number | Record<string, number>>;
  const v = c.vehicles;
  const t = c.temporal;
  const h0 = t.minute_heaping?.per_hour?.["0"];
  const others = Object.entries(t.minute_heaping?.per_hour ?? {}).filter(([k]) => k !== "0").map(([, x]) => x.ratio);
  return (
    <div className="space-y-5">
      <Section id="funnel" title="Koordinat temizleme ve analiz kapsamı" description="Dışlanan kayıtlar ham veride korunur; yalnızca coğrafi analizden çıkarılır.">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <ol className="space-y-2" aria-label="Kayıt hunisi">
            <li className="rounded-md border border-line bg-surface-2 p-3">
              <div className="text-[12px] text-muted-foreground">Ham kayıt (29 sütun)</div>
              <div className="font-display text-[22px] font-bold tabular" data-testid="raw-rows">{fmtInt(rows.raw)}</div>
            </li>
            <li className="flex justify-center text-subtle" aria-hidden><ArrowDown className="size-4" /></li>
            <li className="rounded-md border border-line bg-surface-2 p-3">
              <div className="text-[12px] text-muted-foreground">İşlenmiş (87 sütun, satır kaybı yok)</div>
              <div className="font-display text-[22px] font-bold tabular">{fmtInt(rows.processed)}</div>
            </li>
            <li className="flex justify-center text-subtle" aria-hidden><ArrowDown className="size-4" /></li>
            <li className="rounded-md border border-primary/50 bg-primary/[0.07] p-3">
              <div className="text-[12px] text-muted-foreground">Kümelemeye uygun (geçerli koordinat + tarih)</div>
              <div className="font-display text-[22px] font-bold tabular text-primary" data-testid="eligible-rows">{fmtInt(rows.eligible_for_spatial_clustering)}</div>
              <div className="text-[12px] text-subtle">{fmtPct(rows.eligible_for_spatial_clustering / rows.raw)} · {fmtInt(rows.raw - rows.eligible_for_spatial_clustering)} kayıt dışlandı</div>
            </li>
          </ol>
          <div>
            <h3 className="text-[13px] font-semibold mb-2">Koordinat kalite durumu (tüm kayıtlar)</h3>
            <Table className="text-[12.5px]">
              <TableHeader><TableRow><TableHead>Durum</TableHead><TableHead className="text-right">Kayıt</TableHead><TableHead className="text-right">Pay</TableHead></TableRow></TableHeader>
              <TableBody>
                {coord.map(([k, n]) => (
                  <TableRow key={k}><TableCell>{COORD_TR[k] ?? k}</TableCell><TableCell className="text-right tabular">{fmtInt(n)}</TableCell>
                    <TableCell className="text-right tabular text-muted-foreground">{fmtPct(n / rows.raw, 2)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-2 text-[11.5px] text-subtle">Sınır denetimi: NYC DCP resmî ilçe poligonları (gthc-hcne). Kıyıya yakın noktalar (sınır dışı ≤ eşik) analize dahildir ve bayraklıdır.</p>
          </div>
        </div>
      </Section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section id="borough-infer" title="İlçe çıkarımı" description="Kayıtta bildirilen ilçe eksikse koordinatın düştüğü resmî poligondan çıkarılır (borough_final).">
          <div className="grid grid-cols-2 gap-4">
            <MetricCard label="Bildirilen ilçesi eksik" value={fmtInt(b.original_missing as number)} hint={fmtPct((b.original_missing as number) / rows.raw)} />
            <MetricCard label="Poligondan kurtarılan" value={fmtInt(b.recovered_by_polygon as number)} tone="primary" />
            <MetricCard label="Hâlâ bilinmeyen" value={fmtInt(b.still_missing as number)} hint="Çoğu geçerli koordinatı olmayan kayıtlar" />
            <MetricCard label="Bildirilen ≠ çıkarılan" value={fmtInt(b.conflicts as number)}
              hint={`Karşılaştırılabilir ${fmtInt(b.comparable_original_and_inferred as number)} kaydın %${fmtNum(b.conflict_pct_of_comparable as number, 2)}'i; bayraklı`} />
          </div>
          <div className="mt-4">
            <RowChart ariaLabel="Son ilçe dağılımı" valueLabel="Kayıt"
              data={Object.entries(b.final_counts as Record<string, number>).sort((x, y) => y[1] - x[1]).map(([k, n]) => ({ label: BOROUGH_TR[k] ?? (k === "(eksik)" ? "Bilinmiyor" : k), value: n }))} />
          </div>
        </Section>
        <Section id="vehicles" title="Araç türü normalizasyonu"
          description={`${fmtInt(v.raw_distinct_labels)} ham araç etiketi → ${fmtInt(v.normalized_distinct_labels)} normalize etiket → ${v.category_count} kategori (kural tabanlı). Kategoriler araç geçişi sayısıdır (bir kazada 5 araca kadar).`}>
          <RowChart ariaLabel="Araç kategorisi geçişleri" valueLabel="Araç geçişi"
            data={Object.entries(v.by_category).sort((x, y) => y[1] - x[1]).map(([k, n]) => ({ label: trLabel(k), value: n }))} />
        </Section>
      </div>

      <Section id="temporal" title="Tarih / saat öznitelikleri ve 00:00 şüpheli kayıt bayrağı">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div className="space-y-3 text-[13px] leading-relaxed">
            <p>crash_date ve crash_time ayrıştırılarak yıl, ay, gün, saat, dakika, haftanın günü, hafta sonu ve gün dilimi üretildi.
              Saat, ay ve gün döngüsel (sin/cos) olarak da kodlandı; döngüsel saat ve gün yalnızca deneysel uzay-zaman setinde (D) kullanılır.</p>
            <Note tone="warning" title="00:00 kayıtları" testId="midnight-note">
              Saati tam 00:00 olan {fmtInt(t.midnight_suspect)} kayıt var (%{fmtNum(t.midnight_suspect_pct, 2)}).
              {h0 && <> 00:00'daki tam saat kaydı, aynı saatin diğer dakikalarının ortalamasının {fmtNum(h0.ratio, 1)} katı ({fmtInt(h0.on_the_hour)} / {fmtNum(h0.mean_other_minutes, 0)});
                diğer saatlerde bu oran {fmtNum(Math.min(...others), 1)}–{fmtNum(Math.max(...others), 1)}× arasındadır. Yani her saatte tam dakikaya yuvarlama vardır, gece yarısında ise yaklaşık iki katıdır.</>}
              {" "}Bu yığılma, saati bilinmeyen kayıtların gece yarısına yuvarlanmasıyla tutarlıdır. Kayıtlar silinmez; <code>midnight_suspect_flag</code> ile
              işaretlenir, filtrelerde hariç tutulabilir ve D setinin duyarlılık sürümünde dışlanır.
            </Note>
          </div>
          <div>
            <h3 className="text-[13px] font-semibold mb-2">Tam saat (:00) kaydı / diğer dakikaların ortalaması</h3>
            <ColumnChart ariaLabel="Saatlere göre tam saat kaydı yığılma oranı" valueLabel="Oran" format={(x) => `${fmtNum(x, 1)}×`} height={200}
              data={Object.entries(t.minute_heaping?.per_hour ?? {}).map(([hh, x]) => ({ label: hh.padStart(2, "0"), value: x.ratio, highlight: hh === "0" }))} />
            <p className="mt-1 text-[11.5px] text-subtle">Her saatte dakika :00'da yığılma vardır (kayıtların yuvarlanması); 00:00 kırmızı.</p>
          </div>
        </div>
      </Section>
    </div>
  );
}

function FeatureSets({ d }: { d: DataDictionary }) {
  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="feature-sets">
      {d.feature_sets.map((f) => (
        <section key={f.name} className="surface p-4 space-y-2">
          <h3 className="text-[15px] font-bold">{SET_TR[f.name] ?? f.name}</h3>
          <code className="text-[11.5px] text-subtle">{f.name}</code>
          <dl className="text-[12.5px] space-y-1.5">
            <div><dt className="inline text-muted-foreground">Öznitelikler: </dt><dd className="inline font-mono">{f.features.join(", ")}</dd></div>
            <div><dt className="inline text-muted-foreground">Mesafe: </dt><dd className="inline">{f.metric}</dd></div>
            <div><dt className="inline text-muted-foreground">Birim: </dt><dd className="inline">{f.units}</dd></div>
            <div><dt className="inline text-muted-foreground">Düzey: </dt><dd className="inline">{f.level === "unique_location" ? "benzersiz konum + ağırlık" : "kayıt"} · {fmtInt(f.rows)} satır{f.weight_sum ? ` (ağırlık toplamı ${fmtInt(f.weight_sum)})` : ""}</dd></div>
            {f.row_filter && <div><dt className="inline text-muted-foreground">Satır süzgeci: </dt><dd className="inline font-mono">{f.row_filter}</dd></div>}
            {f.note && <div><dt className="sr-only">Not</dt><dd className="text-subtle">{f.note}</dd></div>}
          </dl>
        </section>
      ))}
      <Note className="md:col-span-2" title="Neden yalnızca koordinatlar?">
        Ana model mekânsaldır: "kazalar nerede tekrar ediyor?" sorusu yalnızca konumla yanıtlanır. İlçe, posta kodu ve sokak adları
        konumun türevleridir (coğrafyayı ikinci kez kodlar); yaralanma ve araç türü sonuç/betimleme alanlarıdır, kümeleri açıklamak için kullanılır.
        Ham derece üzerinde Öklid mesafesi kullanılmaz: Haversine (radyan) veya UTM 18N metre koordinatları.
      </Note>
    </div>
  );
}

export default function DataPage() {
  const q = useQuery<DataDictionary>("/api/data/dictionary", { ttlMs: 30 * 60_000 });
  if (q.status === "error" && !q.data) return <div className="p-4 sm:p-6"><ErrorBlock error={q.error} onRetry={q.reload} /></div>;
  const d = q.data;
  if (!d) return <div className="p-4 sm:p-6"><LoadingBlock lines={10} /></div>;
  const lin = d.cleaning.lineage as Record<string, string>;
  return (
    <div className="mx-auto w-full max-w-[1480px] p-4 sm:p-6 space-y-5" data-testid="data-explorer">
      <PageHeader eyebrow="Faz 1–2 veri hattı" title="Veri gezgini"
        description={<>Orijinal {d.raw.column_count} sütun, işlenmiş {d.processed.column_count} sütun. Ham anlık görüntü <code>{lin.raw_snapshot}</code>,
          hat sürümü {lin.pipeline_version}. Bir sütuna tıklayarak anlamını, modele girip girmediğini, dönüşümünü ve seçim gerekçesini görün.</>} />
      <Tabs defaultValue="pipeline" className="gap-4">
        <TabsList className="bg-surface-2 flex-wrap h-auto">
          <TabsTrigger value="pipeline">Veri hattı</TabsTrigger>
          <TabsTrigger value="raw" data-testid="tab-raw">Ham sütunlar ({d.raw.column_count})</TabsTrigger>
          <TabsTrigger value="processed" data-testid="tab-processed">İşlenmiş sütunlar ({d.processed.column_count})</TabsTrigger>
          <TabsTrigger value="sets" data-testid="tab-sets">Model öznitelik setleri</TabsTrigger>
        </TabsList>
        <TabsContent value="pipeline"><Pipeline d={d} /></TabsContent>
        <TabsContent value="raw">
          <Section id="raw" title="Orijinal sütunlar (NYC Open Data h9gi-nx95)" description={`${fmtInt(d.raw.rows)} kayıt; eksik oranları Faz 2 standartlaştırma raporundan.`}>
            <DataDictionaryTable rows={toRows(d, "raw")} label="Ham sütunlar" testId="dict-raw" />
          </Section>
        </TabsContent>
        <TabsContent value="processed">
          <Section id="processed" title="İşlenmiş sütunlar (crashes_processed.parquet)" description={`${fmtInt(d.processed.rows)} kayıt; eksik sayıları ${d.processed.null_count_method}.`}>
            <DataDictionaryTable rows={toRows(d, "processed")} label="İşlenmiş sütunlar" testId="dict-processed" />
          </Section>
        </TabsContent>
        <TabsContent value="sets"><FeatureSets d={d} /></TabsContent>
      </Tabs>
    </div>
  );
}
