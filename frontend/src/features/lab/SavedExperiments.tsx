// Faz 3 deney kaydı (115 deney): algoritma/aşama/kapsam süzgeci, seçim → doğrulanmış etiketlerden sonuç.
import { useMemo, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ScopeBadge } from "../../components/common";
import { fmtInt, fmtNum, fmtPct } from "../../lib/format";
import type { Experiment } from "../../lib/types";

const STAGE_TR: Record<string, string> = {
  dbscan_grid: "DBSCAN ızgarası", kmeans_grid: "K-Means ızgarası", hdbscan_grid: "HDBSCAN ızgarası", temporal: "Zamansal (yıllık)",
  equivalence: "Eşdeğerlik testi", sensitivity: "Veri kalitesi duyarlılığı",
};

export function SavedExperiments({ experiments, selected, onSelect }: { experiments: Experiment[]; selected: string | null; onSelect: (e: Experiment) => void }) {
  const [algo, setAlgo] = useState("all");
  const [stage, setStage] = useState("grid");
  const stages = useMemo(() => [...new Set(experiments.map((e) => e.stage))], [experiments]);
  const rows = experiments.filter((e) => (algo === "all" || e.algorithm === algo)
    && (stage === "all" || (stage === "grid" ? e.stage.endsWith("grid") : e.stage === stage)));
  return (
    <div data-testid="saved-experiments">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <Select value={algo} onValueChange={setAlgo}>
          <SelectTrigger className="h-9 w-[176px]" aria-label="Algoritma süzgeci"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tüm algoritmalar</SelectItem>
            <SelectItem value="dbscan">DBSCAN</SelectItem><SelectItem value="kmeans">K-Means</SelectItem><SelectItem value="hdbscan">HDBSCAN</SelectItem>
          </SelectContent>
        </Select>
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="h-9 w-[210px]" aria-label="Aşama süzgeci"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="grid">Parametre ızgaraları</SelectItem>
            <SelectItem value="all">Tüm aşamalar</SelectItem>
            {stages.map((s) => <SelectItem key={s} value={s}>{STAGE_TR[s] ?? s}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="ml-auto text-[12px] text-muted-foreground tabular">{rows.length} / {experiments.length} deney</span>
      </div>
      <div className="overflow-x-auto max-h-[460px] overflow-y-auto scroll-thin rounded-md border border-line">
        <Table className="text-[12.5px] min-w-[640px]">
          <TableHeader className="sticky top-0 bg-surface z-[1]">
            <TableRow>
              <TableHead>Deney · aşama · kapsam</TableHead><TableHead>Parametreler</TableHead>
              <TableHead className="text-right">Olay</TableHead><TableHead className="text-right">Küme</TableHead><TableHead className="text-right">Gürültü</TableHead>
              <TableHead className="text-right">Siluet</TableHead><TableHead className="text-right">Süre</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((e) => {
              const m = e.metrics;
              const kmeans = e.algorithm === "kmeans";
              return (
                <TableRow key={e.experiment_id} aria-selected={selected === e.experiment_id}
                  className={cn("cursor-pointer", selected === e.experiment_id && "bg-primary/10")} onClick={() => onSelect(e)}>
                  <TableCell>
                    <button type="button" className="font-mono text-[12px] text-primary hover:underline focus-visible:ring-2 focus-visible:ring-ring rounded-sm outline-none"
                      onClick={(ev) => { ev.stopPropagation(); onSelect(e); }} data-experiment={e.experiment_id}>{e.experiment_id}</button>
                    {e.selected_as && <span className="ml-1.5 text-[11px] text-primary font-semibold">seçili</span>}
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
                      {STAGE_TR[e.stage] ?? e.stage} <ScopeBadge scope={e.scope_class} title={e.scope_text} />
                    </div>
                  </TableCell>
                  <TableCell className="tabular whitespace-normal">{Object.entries(e.params).map(([k, v]) => `${k}=${v ?? "—"}`).join(" ")}</TableCell>
                  <TableCell className="text-right tabular">{fmtInt(e.n_events)}</TableCell>
                  <TableCell className="text-right tabular">{fmtInt(m?.n_clusters_full ?? m?.n_clusters_eval ?? (e.raw_metrics?.n_clusters as number | undefined) ?? null)}</TableCell>
                  <TableCell className="text-right tabular">{kmeans ? <span className="text-subtle" title="K-Means gürültü ayırmaz">Uyg. değil</span>
                    : fmtPct(m?.noise_ratio_full ?? m?.noise_ratio_eval ?? (e.raw_metrics?.noise_ratio as number | undefined) ?? null)}</TableCell>
                  <TableCell className="text-right tabular">{m?.silhouette != null ? fmtNum(m.silhouette, 3) : "—"}</TableCell>
                  <TableCell className="text-right tabular">{e.status === "success" ? `${fmtNum(e.runtime_s, 1)} sn` : <span className="text-warning">{e.status === "skipped_resource_limit" ? "kaynak sınırı" : e.status}</span>}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <p className="mt-2 text-[11.5px] text-subtle">Metrik sütunları yalnızca ızgara deneyleri için değerlendirildi; zamansal/bölgesel deneylerde "—" gösterilir. Bir satırı seçerek doğrulanmış etiketlerden sonucu yükleyin.</p>
    </div>
  );
}
