// Laboratuvar işi ve kayıtlı deney sonuçları. Durum sunucudan sorgulanır (ilerleme yüzdesi uydurulmaz):
// bekliyor → çalışıyor (gerçek aşama) → tamamlandı | başarısız | iptal | kaynak yetersiz.
import { Ban, CheckCircle2, CircleAlert, Clock, Hourglass, Loader2, Map as MapIcon, OctagonX } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import { ColumnChart } from "../../components/charts";
import { EmptyBlock, ErrorBlock, InfoTip, LoadingBlock, MetricCard, Note, NotApplicable } from "../../components/common";
import { ExportMenu } from "../../components/ExportMenu";
import { deleteJSON, getJSON } from "../../lib/api";
import { BOROUGH_TR } from "../../lib/camera";
import { fmtInt, fmtNum, fmtPct } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { ClusterRow, Experiment, Job, JobState, ResultSummary } from "../../lib/types";

export const STATE_TR: Record<JobState, { label: string; tone: string; Icon: typeof Clock }> = {
  pending: { label: "Kuyrukta", tone: "border-line-strong text-muted-foreground", Icon: Hourglass },
  running: { label: "Çalışıyor", tone: "border-primary/60 text-primary", Icon: Loader2 },
  completed: { label: "Tamamlandı", tone: "border-success/60 text-success", Icon: CheckCircle2 },
  failed: { label: "Başarısız", tone: "border-hotspot/60 text-hotspot", Icon: CircleAlert },
  cancelled: { label: "İptal edildi", tone: "border-line-strong text-muted-foreground", Icon: Ban },
  rejected_resource: { label: "Kaynak yetersiz", tone: "border-warning/60 text-warning", Icon: OctagonX },
};

export function StateBadge({ state }: { state: JobState }) {
  const s = STATE_TR[state];
  return (
    <Badge variant="outline" className={cn("gap-1 font-semibold", s.tone)} data-testid="job-state" data-state={state}>
      <s.Icon className={cn("size-3.5", state === "running" && "animate-spin")} /> {s.label}
    </Badge>
  );
}

/** Aktif işi sorgular (bitene kadar). */
export function useJob(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let t: number | undefined;
    const tick = async () => {
      try {
        const j = await getJSON<Job>(`/api/lab/jobs/${jobId}`);
        if (stop) return;
        setJob(j);
        setError(null);
        if (j.state === "pending" || j.state === "running") t = window.setTimeout(tick, 700);
      } catch (e) {
        if (!stop) setError(e as Error);
      }
    };
    setJob(null);
    tick();
    return () => { stop = true; window.clearTimeout(t); };
  }, [jobId]);
  return { job, error, setJob };
}

function SummaryMetrics({ s, algorithm, extra }: { s: ResultSummary; algorithm: string; extra?: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-5 gap-y-4" data-testid="result-metrics">
      <MetricCard label="Kullanılan olay" value={fmtInt(s.n_events)} />
      <MetricCard label="Küme sayısı" value={fmtInt(s.n_clusters)} tone="primary" testId="result-clusters" />
      <MetricCard label="Gürültü oranı" testId="result-noise"
        value={s.noise_applicable ? fmtPct(s.noise_ratio) : <NotApplicable reason="K-Means gürültü ayırmaz; her olay bir kümeye atanır" />}
        info={algorithm === "kmeans" ? "K-Means'te gürültü kavramı yoktur; 0 olarak gösterilmez." : "Hiçbir kümeye atanmayan (−1) olay payı."} />
      <MetricCard label="En büyük küme payı" value={fmtPct(s.largest_cluster_share, 2)} hint={`Medyan küme: ${fmtNum(s.cluster_size.median, 0)} olay`} />
      {extra}
    </div>
  );
}

function TopClusters({ rid }: { rid: string }) {
  const t = useQuery<{ total: number; rows: ClusterRow[] }>(`/api/results/${encodeURIComponent(rid)}/table?limit=10`);
  if (t.status === "error") return <ErrorBlock error={t.error} />;
  if (!t.data) return <LoadingBlock lines={4} />;
  if (!t.data.rows.length) return <EmptyBlock>Bu sonuçta küme yok (tüm olaylar gürültü).</EmptyBlock>;
  return (
    <div className="overflow-x-auto">
      <Table className="text-[12.5px] min-w-[560px]" data-testid="result-table">
        <TableHeader><TableRow>
          <TableHead>#</TableHead><TableHead>Küme</TableHead><TableHead>İlçe</TableHead><TableHead className="text-right">Kaza</TableHead>
          <TableHead className="text-right">Konum</TableHead><TableHead className="text-right">Yarıçap p90</TableHead><TableHead className="text-right">Yaralanmalı</TableHead><TableHead className="text-right">Ölümlü</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {t.data.rows.map((r) => (
            <TableRow key={r.cluster_id}>
              <TableCell className="tabular text-muted-foreground">{r.rank_by_events}</TableCell>
              <TableCell className="tabular font-semibold">#{r.cluster_id}</TableCell>
              <TableCell>{r.dominant_borough ? BOROUGH_TR[r.dominant_borough] : "Bilinmiyor"}</TableCell>
              <TableCell className="text-right tabular">{fmtInt(r.n_events)}</TableCell>
              <TableCell className="text-right tabular">{fmtInt(r.n_unique_locations)}</TableCell>
              <TableCell className="text-right tabular">{fmtNum(r.radius_p90_m, 1)} m</TableCell>
              <TableCell className="text-right tabular">{fmtInt(r.injury_crashes)}</TableCell>
              <TableCell className="text-right tabular">{fmtInt(r.fatal_crashes)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SizeHistogram({ s }: { s: ResultSummary }) {
  const data = s.size_histogram.filter((b) => b.clusters > 0 || b.from < 1000).map((b) => ({
    label: b.to === null ? `${fmtInt(b.from)}+` : `${fmtInt(b.from)}–${fmtInt(b.to)}`, value: b.clusters,
  }));
  return <ColumnChart data={data} valueLabel="Küme" ariaLabel="Küme büyüklüğü dağılımı (olay sayısına göre)" height={180} testId="size-histogram" />;
}

function ShowOnMap({ rid, label, algorithm, dynamic }: { rid: string; label: string; algorithm: string; dynamic: boolean }) {
  const setSource = useApp((s) => s.setSource);
  const setRoute = useApp((s) => s.setRoute);
  const setLeftPanel = useApp((s) => s.setLeftPanel);
  return (
    <Button size="sm" onClick={() => { setSource({ kind: "result", id: rid, label, algorithm, dynamic }); setLeftPanel("view"); setRoute("explorer"); }} data-testid="show-on-map">
      <MapIcon /> Haritada göster
    </Button>
  );
}

export function JobView({ jobId }: { jobId: string }) {
  const { job, error, setJob } = useJob(jobId);
  const [cancelling, setCancelling] = useState(false);
  if (error && !job) return <ErrorBlock error={error} />;
  if (!job) return <LoadingBlock lines={4} label="İş durumu alınıyor…" />;
  const rid = `lab-${job.job_id}`;
  const req = job.request;
  const params = Object.entries(req.params).map(([k, v]) => `${k} = ${v ?? "otomatik"}`).join(" · ");
  const label = `${params}${job.filters_tr.length ? ` · ${job.filters_tr.join(" · ")}` : " · tüm kayıtlar"}`;
  const active = job.state === "pending" || job.state === "running";
  const m = job.result?.metrics;
  const p3 = job.result?.phase3_metrics;
  return (
    <div className="space-y-4" data-testid="job-view" data-job={job.job_id}>
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={job.state} />
        {job.source === "phase3_registry" && <Badge variant="outline" className="border-primary/50 text-primary" data-testid="job-source">Kayıtlı Faz 3 sonucu · {job.phase3_experiment}</Badge>}
        {job.source === "cache" && <Badge variant="outline" className="border-line-strong text-muted-foreground" data-testid="job-source">Önbellekten (daha önce hesaplandı)</Badge>}
        <code className="text-[11.5px] text-subtle">iş {job.job_id} · anahtar {job.cache_key}</code>
        {active && (
          <Button size="sm" variant="outline" className="ml-auto" disabled={cancelling} data-testid="job-cancel"
            onClick={async () => { setCancelling(true); try { setJob(await deleteJSON<Job>(`/api/lab/jobs/${job.job_id}`)); } finally { setCancelling(false); } }}>
            <Ban /> İptal et
          </Button>
        )}
      </div>
      <div className="text-[12.5px] text-muted-foreground"><span className="font-semibold text-foreground">{req.algorithm.toUpperCase()}</span> · {params} · {job.feature_set.label}
        {req.sample ? ` · örneklem ${fmtInt(req.sample.n)} (tohum ${req.sample.seed})` : ""} · kapsam {fmtInt(job.n_events)} olay{job.n_fit_rows ? `, ${fmtInt(job.n_fit_rows)} fit satırı` : ""}</div>

      {active && (
        <div className="rounded-md border border-primary/40 bg-primary/[0.06] p-3 text-[13px]" role="status" aria-live="polite" data-testid="job-stage">
          {job.state === "pending" ? "Kuyrukta bekliyor; önceki iş bitince başlayacak." : (
            <>Aşama: <b>{job.stage?.stage_label ?? "Süreç başlatılıyor"}</b> · geçen süre {fmtNum(job.elapsed_s ?? 0, 1)} sn</>
          )}
          <div className="text-[11.5px] text-subtle mt-1">İlerleme yüzdesi gösterilmez: kümeleme algoritmaları güvenilir bir ilerleme ölçüsü vermez. Aşamalar çalışan süreçten okunur.</div>
        </div>
      )}
      {job.state === "rejected_resource" && <Note tone="warning" title="Kaynak yetersiz — iş çalıştırılmadı" testId="job-rejected">{job.error}</Note>}
      {job.state === "failed" && <ErrorBlock title="İş başarısız" error={job.error ?? "Bilinmeyen hata"} />}
      {job.state === "cancelled" && <Note title="İş iptal edildi">{job.error}</Note>}

      {job.state === "completed" && job.result && (
        <>
          <SummaryMetrics s={job.result.summary} algorithm={req.algorithm} extra={<>
            <MetricCard label="Siluet" value={m?.silhouette != null ? fmtNum(m.silhouette, 3) : p3?.silhouette != null ? fmtNum(p3.silhouette, 3) : null}
              info={m ? `${m.status === "ok" ? `${m.sampling}, n = ${fmtInt(m.n_used ?? 0)}, ${m.metric}.` : m.status} Doğruluk değildir; Faz 3 ortak değerlendirme kümesiyle karşılaştırılamaz.`
                : "Faz 3 ortak değerlendirme kümesinden (100k olay, gürültü hariç). Doğruluk değildir."} />
            <MetricCard label="Davies–Bouldin" value={m?.davies_bouldin != null ? fmtNum(m.davies_bouldin, 3) : p3?.davies_bouldin != null ? fmtNum(p3.davies_bouldin, 3) : null}
              info="Düşük değer daha ayrık kümeler. Gürültü hariç." />
            <MetricCard label="Fit süresi" value={job.worker?.runtime_s != null ? fmtNum(job.worker.runtime_s, 2) : null} unit="sn"
              hint={job.source === "phase3_registry" ? "Faz 3 ölçümü" : `Toplam ${fmtNum(job.elapsed_s ?? 0, 1)} sn (süreç + veri hazırlığı dahil)`} />
            <MetricCard label="Tepe bellek" value={job.worker?.peak_memory_mb != null ? fmtInt(job.worker.peak_memory_mb) : null} unit="MB" hint="Çalışan sürecin tepe değeri" />
          </>} />
          {m && m.status !== "ok" && <p className="text-[12px] text-subtle">Siluet/Davies–Bouldin: {m.status}</p>}
          {job.result.summary.n_clusters > 0 && <SizeHistogram s={job.result.summary} />}
          <TopClusters rid={rid} />
          <div className="flex flex-wrap gap-2">
            <ShowOnMap rid={rid} label={label} algorithm={req.algorithm} dynamic={job.source !== "phase3_registry"} />
            <ExportMenu base={`/api/export/results/${rid}`} label="Sonucu dışa aktar" testId="job-export" />
          </div>
          {req.feature_set === "spatiotemporal" && (
            <Note>Uzay-zaman kümeleri "aynı yerde VE aynı dönemde" tekrar eden kazalardır; mekânsal kümelerle (ör. ana DBSCAN) sayıca doğrudan karşılaştırılamaz.</Note>
          )}
          {!job.filters_tr.length || job.source === "phase3_registry" ? null : (
            <Note>Bu sonuç yalnızca filtre kapsamındaki kayıtlar üzerinde YENİDEN kümelenmiştir; seçili modelin küme numaralarıyla eşleştirilemez.</Note>
          )}
        </>
      )}
    </div>
  );
}

export function SavedResultView({ exp }: { exp: Experiment }) {
  const q = useQuery<{ summary: ResultSummary }>(exp.has_labels ? `/api/results/${encodeURIComponent(exp.experiment_id)}/summary` : null);
  const m = exp.metrics;
  const params = Object.entries(exp.params).map(([k, v]) => `${k} = ${v ?? "—"}`).join(" · ");
  return (
    <div className="space-y-4" data-testid="saved-view" data-experiment={exp.experiment_id}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="border-primary/50 text-primary">Kayıtlı Faz 3 deneyi</Badge>
        {exp.selected_as && <Badge className="bg-primary/15 text-primary border-primary/40" variant="outline">Seçilen {exp.selected_as.toUpperCase()}</Badge>}
        <code className="text-[11.5px] text-subtle">{exp.experiment_id}</code>
      </div>
      <div className="text-[12.5px] text-muted-foreground"><span className="font-semibold text-foreground">{exp.algorithm.toUpperCase()}</span> · {params} · {exp.feature_set} · {exp.scope_text}</div>
      {!exp.has_labels ? <Note tone="warning">Bu deneyin etiket dosyası yok (durum: {exp.status}){exp.error ? `: ${exp.error}` : ""}.</Note> : q.status === "error" ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock lines={3} /> : (
        <>
          <SummaryMetrics s={q.data.summary} algorithm={exp.algorithm} extra={<>
            <MetricCard label="Siluet" value={m?.silhouette != null ? fmtNum(m.silhouette, 3) : null} info="Faz 3 ortak değerlendirme kümesi (gürültü hariç). Doğruluk değildir." />
            <MetricCard label="DBCV" value={m?.dbcv != null ? fmtNum(m.dbcv, 3) : null} info="Yoğunluk tabanlı geçerlilik; 4.000 olaylık örneklem." />
            <MetricCard label="Fit süresi" value={exp.runtime_s != null ? fmtNum(exp.runtime_s, 2) : null} unit="sn" />
            <MetricCard label="Tepe bellek" value={exp.peak_memory_mb != null ? fmtInt(exp.peak_memory_mb) : null} unit="MB" />
          </>} />
          {m?.admissible === false && <Note tone="warning" title="Kabul ölçütünü sağlamıyor">{m.rejection_reasons.join("; ")}</Note>}
          {q.data.summary.n_clusters > 0 && <SizeHistogram s={q.data.summary} />}
          <TopClusters rid={exp.experiment_id} />
          <div className="flex flex-wrap gap-2">
            <ShowOnMap rid={exp.experiment_id} label={`${params} · ${exp.scope_text}`} algorithm={exp.algorithm} dynamic={false} />
            <ExportMenu base={`/api/export/results/${exp.experiment_id}`} label="Sonucu dışa aktar" />
          </div>
        </>
      )}
      <div className="text-[11.5px] text-subtle">Yazılım: {exp.software ? Object.entries(exp.software).filter(([k]) => k !== "platform").map(([k, v]) => `${k} ${v}`).join(", ") : "—"} · <InfoTip>Faz 3 deney kaydı: her deney ayrı süreçte çalıştı; süre ve bellek o sürece aittir.</InfoTip></div>
    </div>
  );
}
