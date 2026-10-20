// Model karşılaştırma: Faz 3'ün gerçek metrikleri, kapsamlarıyla birlikte. Tek bir "başarı puanı" üretilmez;
// siluet yüzde doğruluk olarak yazılmaz; K-Means gürültüsü "Uygulanamaz" gösterilir.
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorBlock, InfoTip, LoadingBlock, Note, NotApplicable, PageHeader, ScopeBadge, Section } from "../../components/common";
import { fmtInt, fmtNum, fmtPct } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { Comparison, ComparisonRow } from "../../lib/types";
import { GridTable, KMeansSweep } from "./ComparisonCharts";

const ALGO = { dbscan: "DBSCAN", kmeans: "K-Means", hdbscan: "HDBSCAN" } as Record<string, string>;
const params = (p: Record<string, number | null>) => Object.entries(p).map(([k, v]) => `${k} = ${v ?? "—"}`).join(" · ");
const n3 = (v: number | null) => (v === null ? null : fmtNum(v, 3));

function MetricCell({ v, detail, note }: { v: number | null; detail?: { n_used: number; metric: string; seed: number } | null; note?: string }) {
  if (v === null) return <span className="text-subtle">—</span>;
  return (
    <span className="inline-flex items-center gap-1 tabular">
      {fmtNum(v, 3)}
      {detail && <InfoTip>{`${detail.metric === "haversine" ? "Haversine" : "Öklid (metre)"} · n = ${fmtInt(detail.n_used)} (gürültü hariç örneklem) · tohum ${detail.seed}.${note ? ` ${note}` : ""}`}</InfoTip>}
    </span>
  );
}

type RowDef = { key: string; label: string; info?: string; cell: (r: ComparisonRow) => React.ReactNode };

const ROWS: RowDef[] = [
  { key: "params", label: "Parametreler", cell: (r) => <span className="tabular">{params(r.parameters)}</span> },
  { key: "scope", label: "Model kapsamı", info: "Modelin eğitildiği (fit) veri kapsamı. HDBSCAN örneklemde, DBSCAN ve K-Means tam veride çalıştı.",
    cell: (r) => <><ScopeBadge scope={r.scope_class} /><div className="text-[11.5px] text-muted-foreground mt-1">{r.fit_scope}</div><div className="text-[11px] text-subtle">{r.features}</div></> },
  { key: "events", label: "Kullanılan olay", cell: (r) => <span className="tabular">{fmtInt(r.fit_n_events)}<span className="block text-[11px] text-subtle">{fmtInt(r.fit_n_points)} fit noktası</span></span> },
  { key: "clusters", label: "Küme sayısı", cell: (r) => <span className="tabular" data-testid={`cmp-clusters-${r.algorithm}`}>{fmtInt(r.n_clusters)}<span className="block text-[11px] text-subtle">{r.n_clusters_scope}</span></span> },
  { key: "noise", label: "Gürültü oranı", info: "Hiçbir kümeye atanmayan olay payı. K-Means'in gürültü kavramı yoktur: her olayı bir kümeye atar; bu nedenle 0 değil \"uygulanamaz\".",
    cell: (r) => <span data-testid={`cmp-noise-${r.algorithm}`}>{r.noise_applicable ? <span className="tabular">{fmtPct(r.noise_ratio)}<span className="block text-[11px] text-subtle">{r.noise_scope}</span></span> : <NotApplicable reason="K-Means gürültü ayırmaz" />}</span> },
  { key: "largest", label: "En büyük küme payı", info: "Kabul ölçütü: ≤ %5.", cell: (r) => <span className="tabular">{fmtPct(r.largest_cluster_share, 2)}</span> },
  { key: "sil", label: "Siluet", info: "−1…1 aralığında küme ayrıklığı; doğruluk değildir. 0,945 = %94,5 doğruluk DEĞİLDİR. Aynı 100k ortak değerlendirme kümesinde, gürültü hariç.",
    cell: (r) => <span data-testid={`cmp-silhouette-${r.algorithm}`}><MetricCell v={r.silhouette} detail={r.silhouette_detail} note={r.silhouette_haversine !== null ? `Haversine siluet: ${n3(r.silhouette_haversine)}.` : undefined} /></span> },
  { key: "db", label: "Davies–Bouldin", info: "Düşük değer daha ayrık kümeler. Gürültü hariç, ortak değerlendirme kümesi.", cell: (r) => <MetricCell v={r.davies_bouldin} detail={r.davies_bouldin_detail} /> },
  { key: "dbcv", label: "DBCV", info: "Yoğunluk tabanlı geçerlilik (−1…1). 4.000 olaylık örneklemde hesaplandı.", cell: (r) => <MetricCell v={r.dbcv} detail={r.dbcv_detail} /> },
  { key: "ari", label: "Parametre kararlılığı (ARI)", info: "Komşu ızgara konfigürasyonlarıyla Ayarlanmış Rand İndeksi (yalnızca DBSCAN seçim kuralında).", cell: (r) => <span className="tabular">{r.parameter_stability_ari === null ? <span className="text-subtle">—</span> : fmtNum(r.parameter_stability_ari, 3)}</span> },
  { key: "time", label: "Fit süresi", cell: (r) => <span className="tabular">{r.runtime_s === null ? "—" : `${fmtNum(r.runtime_s, 1)} sn`}</span> },
  { key: "mem", label: "Bellek (tepe / fit artışı)", info: "Süreç tepe belleği / fit sırasında artış (MB). Her deney ayrı süreçte ölçüldü.", cell: (r) => <span className="tabular">{fmtInt(r.peak_memory_mb)} / {fmtInt(r.fit_memory_mb)} MB</span> },
  { key: "adm", label: "Kabul ölçütleri", cell: (r) => <>
    {r.admissible ? <span className="inline-flex items-center gap-1 text-success"><Check className="size-4" /> Sağlıyor</span>
      : <span className="inline-flex items-center gap-1 text-warning"><X className="size-4" /> Sağlamıyor</span>}
    {r.rejection_reasons.length > 0 && <div className="text-[11px] text-subtle mt-0.5">{r.rejection_reasons.join("; ")}</div>}</> },
];

function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <Table data-testid="comparison-table" className="text-[12.5px] min-w-[720px] table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[220px]">Ölçüt</TableHead>
            {rows.map((r) => (
              <TableHead key={r.experiment_id} className="align-bottom py-2.5" data-algo={r.algorithm}>
                <div className="font-display font-bold text-[14px] text-foreground">{ALGO[r.algorithm] ?? r.algorithm}</div>
                {r.primary && <Badge className="mt-1 bg-primary/15 text-primary border-primary/40" variant="outline">Ana model</Badge>}
                <code className="block text-[11px] text-subtle mt-1 font-normal">{r.experiment_id}</code>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {ROWS.map((d) => (
            <TableRow key={d.key}>
              <TableHead scope="row" className="font-medium text-muted-foreground whitespace-normal">
                <span className="inline-flex items-center gap-1">{d.label}{d.info && <InfoTip>{d.info}</InfoTip>}</span>
              </TableHead>
              {rows.map((r) => <TableCell key={r.experiment_id} className="whitespace-normal align-top">{d.cell(r)}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function ModelsPage() {
  const q = useQuery<Comparison>("/api/models/comparison");
  if (q.status === "error" && !q.data) return <div className="p-4 sm:p-6"><ErrorBlock error={q.error} onRetry={q.reload} /></div>;
  const c = q.data;
  if (!c) return <div className="p-4 sm:p-6"><LoadingBlock lines={10} /></div>;
  const sel = Object.fromEntries(c.rows.map((r) => [r.algorithm, r.experiment_id]));
  const selK = c.rows.find((r) => r.algorithm === "kmeans")?.parameters.k ?? null;
  const variants = (c.sensitivity?.variants ?? []) as Record<string, number | string | null>[];
  const VARIANT_TR: Record<string, string> = {
    exclude_geocode_fallback: "Yedek geokodlama şüphesi hariç", exclude_borough_conflict: "İlçe çelişkisi hariç",
    exclude_nearshore: "Kıyıya yakın kayıtlar hariç", cap_repeated_weights: "Tekrar ağırlığı 99. yüzdelikte kırpılmış",
  };
  return (
    <div className="mx-auto w-full max-w-[1480px] p-4 sm:p-6 space-y-5" data-testid="models">
      <PageHeader eyebrow="Faz 3 deney kaydı" title="Model karşılaştırma"
        description={<>DBSCAN, K-Means ve HDBSCAN'in seçilen konfigürasyonları. Değerlendirme kümesi: {c.eval_set.definition} (n = {fmtInt(c.eval_set.n_events)}, tohum {c.eval_set.seed}). Seçim ölçütleri sonuçlardan önce tanımlandı: en büyük küme ≤ {fmtPct(c.selection_criteria.max_largest_cluster_share, 0)}, en az {c.selection_criteria.min_clusters} küme.</>} />

      <Note tone="warning" title="Karşılaştırmanın sınırlılıkları" testId="comparison-caveats">
        <ul className="list-disc pl-4 space-y-1">{c.caveats.map((x) => <li key={x}>{x}</li>)}</ul>
      </Note>

      <Section id="cmp" title="Seçilen konfigürasyonlar" description="Metrikler bağlamlarıyla birlikte okunmalıdır; tablo bir sıralama değildir.">
        <ComparisonTable rows={c.rows} />
      </Section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section id="dbscan-grid" title="DBSCAN parametre ızgarası (tam veri)"
          description="eps (metre) × min_samples. Küme ve gürültü tam veriden; siluet/DBCV ortak değerlendirme kümesinden. Kırmızı çerçeve seçili model, × kabul ölçütünü sağlamayan.">
          <GridTable rows={c.grids.dbscan} rowKey="eps_m" colKey="min_samples" rowLabel="eps (m)" colLabel="min_samples" selectedId={sel.dbscan ?? null}
            scope="full" testId="dbscan-grid" caption="Hücre tonu metriğin bu ızgaradaki göreli değeridir (açık → koyu); iyi/kötü anlamı taşımaz." />
        </Section>
        <Section id="hdbscan-grid" title="HDBSCAN parametre ızgarası (100k olay örneklemi)"
          description="min_cluster_size × min_samples. Tüm değerler 100.000 olaylık örneklemdedir; DBSCAN'in tam veri sayılarıyla doğrudan karşılaştırılamaz.">
          <GridTable rows={c.grids.hdbscan} rowKey="min_cluster_size" colKey="min_samples" rowLabel="min_cluster_size" colLabel="min_samples"
            selectedId={sel.hdbscan ?? null} scope="eval" testId="hdbscan-grid" caption="Örneklem kapsamı: küme ve gürültü 100k olay üzerinden." />
        </Section>
      </div>

      <Section id="kmeans-sweep" title="K-Means k taraması (tam veri, ağırlıklı)">
        <KMeansSweep rows={c.grids.kmeans} selectedK={selK as number | null} elbowK={c.kmeans_elbow_k} />
      </Section>

      {variants.length > 0 && (
        <Section id="sensitivity" title="Veri kalitesi duyarlılığı (seçili DBSCAN)"
          description={<>Temel: {c.sensitivity?.baseline}. ARI ortak olaylar üzerinde hesaplandı.</>}>
          <div className="overflow-x-auto">
            <Table className="text-[12.5px] min-w-[640px]" data-testid="sensitivity-table">
              <TableHeader><TableRow>
                <TableHead>Varyant</TableHead><TableHead className="text-right">Hariç olay</TableHead><TableHead className="text-right">Küme</TableHead>
                <TableHead className="text-right">Gürültü</TableHead><TableHead className="text-right">ARI (temel ile)</TableHead><TableHead className="text-right">Korunan temel küme</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {variants.map((v) => (
                  <TableRow key={String(v.variant)}>
                    <TableCell>{VARIANT_TR[String(v.variant)] ?? String(v.variant)}</TableCell>
                    <TableCell className="text-right tabular">{fmtInt(v.excluded_events as number)}</TableCell>
                    <TableCell className="text-right tabular">{fmtInt(v.n_clusters as number)}</TableCell>
                    <TableCell className="text-right tabular">{fmtPct(v.noise_ratio as number)}</TableCell>
                    <TableCell className="text-right tabular">{fmtNum(v.ari_vs_baseline_common_events as number, 4)}</TableCell>
                    <TableCell className="text-right tabular">{fmtPct(v.baseline_clusters_retained_share as number)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Section>
      )}

      <p className="text-[11.5px] text-subtle">
        {c.label_semantics} · {c.eps_conversion} · scikit-learn {c.software["scikit-learn"]}, hdbscan {c.software.hdbscan} · veri sürümü <code>{c.dataset_version}</code>
      </p>
    </div>
  );
}
