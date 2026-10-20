// Parametre duyarlılığı: Faz 3 ızgara deneyleri (gerçek kayıt). Izgaralar renk yoğunluklu tablo olarak
// (tek ton, açık→koyu) ve K-Means k taraması küçük çoklu çizgi grafikleriyle gösterilir.
import { useMemo, useState } from "react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { SweepChart } from "../../components/charts";
import { fmtInt, fmtNum, fmtPct } from "../../lib/format";
import type { Experiment } from "../../lib/types";

type MetricKey = "n_clusters" | "noise" | "silhouette" | "dbcv" | "ari" | "runtime";
const METRICS: { key: MetricKey; label: string; fmt: (v: number) => string; higherIs: string }[] = [
  { key: "n_clusters", label: "Küme", fmt: (v) => fmtInt(v), higherIs: "" },
  { key: "noise", label: "Gürültü", fmt: (v) => fmtPct(v), higherIs: "" },
  { key: "silhouette", label: "Siluet", fmt: (v) => fmtNum(v, 3), higherIs: "" },
  { key: "dbcv", label: "DBCV", fmt: (v) => fmtNum(v, 3), higherIs: "" },
  { key: "ari", label: "Komşu ARI", fmt: (v) => fmtNum(v, 3), higherIs: "" },
  { key: "runtime", label: "Süre (sn)", fmt: (v) => fmtNum(v, 1), higherIs: "" },
];

function value(e: Experiment, k: MetricKey, scope: "full" | "eval"): number | null {
  const m = e.metrics;
  if (!m) return null;
  switch (k) {
    case "n_clusters": return scope === "full" ? m.n_clusters_full : m.n_clusters_eval;
    case "noise": return scope === "full" ? m.noise_ratio_full : m.noise_ratio_eval;
    case "silhouette": return m.silhouette;
    case "dbcv": return m.dbcv;
    case "ari": return m.parameter_stability_ari;
    case "runtime": return e.runtime_s;
  }
}

/** İki parametreli ızgara: satır × sütun; hücre yoğunluğu metriğin ızgara içindeki sırasıyla (tek ton). */
export function GridTable({ rows, rowKey, colKey, rowLabel, colLabel, selectedId, scope, testId, caption }: {
  rows: Experiment[]; rowKey: string; colKey: string; rowLabel: string; colLabel: string; selectedId: string | null;
  scope: "full" | "eval"; testId?: string; caption: string;
}) {
  const [metric, setMetric] = useState<MetricKey>("n_clusters");
  const def = METRICS.find((m) => m.key === metric)!;
  const rVals = useMemo(() => [...new Set(rows.map((e) => Number(e.params[rowKey])))].sort((a, b) => a - b), [rows, rowKey]);
  const cVals = useMemo(() => [...new Set(rows.map((e) => Number(e.params[colKey])))].sort((a, b) => a - b), [rows, colKey]);
  const vals = rows.map((e) => value(e, metric, scope)).filter((v): v is number => v !== null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const available = METRICS.filter((m) => rows.some((e) => value(e, m.key, scope) !== null));
  return (
    <div data-testid={testId}>
      <ToggleGroup type="single" size="sm" variant="outline" value={metric} onValueChange={(v) => v && setMetric(v as MetricKey)} aria-label="Gösterilen metrik" className="flex-wrap mb-3">
        {available.map((m) => <ToggleGroupItem key={m.key} value={m.key} className="px-2.5 text-[12px]">{m.label}</ToggleGroupItem>)}
      </ToggleGroup>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-separate border-spacing-[3px] text-[12.5px] tabular">
          <caption className="caption-bottom text-left text-[11.5px] text-subtle pt-2">{caption}</caption>
          <thead>
            <tr>
              <th className="text-left font-medium text-muted-foreground px-2" scope="col">{rowLabel} ↓ · {colLabel} →</th>
              {cVals.map((c) => <th key={c} scope="col" className="font-semibold px-2 text-center">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {rVals.map((r) => (
              <tr key={r}>
                <th scope="row" className="text-left font-semibold px-2">{r}</th>
                {cVals.map((c) => {
                  const e = rows.find((x) => Number(x.params[rowKey]) === r && Number(x.params[colKey]) === c);
                  const v = e ? value(e, metric, scope) : null;
                  const t = v === null || hi === lo ? 0 : (v - lo) / (hi - lo);
                  const sel = e?.experiment_id === selectedId;
                  return (
                    <td key={c} className={cn("rounded-[4px] px-2 py-2 text-center", sel && "ring-2 ring-hotspot")}
                      style={{ background: v === null ? "transparent" : `rgba(56,189,248,${0.08 + t * 0.5})` }}
                      title={e ? `${e.experiment_id}${e.metrics?.admissible === false ? " · kabul ölçütünü sağlamıyor" : ""}` : "deney yok"}>
                      {v === null ? <span className="text-subtle">—</span> : def.fmt(v)}
                      {e?.metrics?.admissible === false && <span className="ml-1 text-warning" aria-label="kabul edilmedi">×</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function KMeansSweep({ rows, selectedK, elbowK }: { rows: Experiment[]; selectedK: number | null; elbowK: number | null }) {
  const pts = [...rows].sort((a, b) => Number(a.params.k) - Number(b.params.k));
  const sil = pts.map((e) => ({ x: Number(e.params.k), y: e.metrics?.silhouette ?? null }));
  const db = pts.map((e) => ({ x: Number(e.params.k), y: e.metrics?.davies_bouldin ?? null }));
  const big = pts.map((e) => ({ x: Number(e.params.k), y: e.metrics?.largest_cluster_share_full ?? null }));
  return (
    <div className="grid gap-4 md:grid-cols-3" data-testid="kmeans-sweep">
      <div>
        <div className="text-[12.5px] font-semibold">Siluet (ortak değerlendirme kümesi)</div>
        <SweepChart data={sil} xLabel="k" yLabel="Siluet" selectedX={selectedK ?? undefined} ariaLabel="K-Means k değerine göre siluet" />
      </div>
      <div>
        <div className="text-[12.5px] font-semibold">Davies–Bouldin (düşük = ayrık)</div>
        <SweepChart data={db} xLabel="k" yLabel="Davies–Bouldin" selectedX={selectedK ?? undefined} ariaLabel="K-Means k değerine göre Davies–Bouldin" />
      </div>
      <div>
        <div className="text-[12.5px] font-semibold">En büyük küme payı (tam veri)</div>
        <SweepChart data={big} xLabel="k" yLabel="Pay" format={(v) => fmtPct(v)} selectedX={selectedK ?? undefined}
          refY={{ y: 0.05, label: "kabul sınırı %5" }} ariaLabel="K-Means k değerine göre en büyük küme payı" />
      </div>
      <p className="md:col-span-3 text-[11.5px] text-subtle">
        Kırmızı nokta Faz 3'te siluet kuralıyla seçilen k'dır. Dirsek yöntemi k = {elbowK ?? "—"} önerdi. K-Means her olayı bir kümeye atar
        (gürültü yoktur); bu nedenle yoğunluk tabanlı algoritmalarla gürültü oranı karşılaştırılmaz.
      </p>
    </div>
  );
}
