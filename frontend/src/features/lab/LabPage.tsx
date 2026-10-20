// Kümeleme Laboratuvarı: yeni analiz (gerçek arka uç işi), kayıtlı Faz 3 deneyleri ve iş geçmişi.
import { useEffect, useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "../../app/store";
import { EmptyBlock, ErrorBlock, LoadingBlock, Note, PageHeader, Section } from "../../components/common";
import { postJSON } from "../../lib/api";
import { BOROUGH_TR } from "../../lib/camera";
import { describe, isEmpty, toBody, toQuery } from "../../lib/filters";
import { trLabel } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { Experiment, Job, LabCapabilities, RecordsSummary } from "../../lib/types";
import { AlgorithmControls } from "./AlgorithmControls";
import { JobView, SavedResultView, StateBadge } from "./ExperimentResults";
import { defaultForm, validateForm, type LabForm } from "./labForm";
import { SavedExperiments } from "./SavedExperiments";

export default function LabPage() {
  const applied = useApp((s) => s.applied);
  const activeJobId = useApp((s) => s.activeJobId);
  const setActiveJob = useApp((s) => s.setActiveJob);
  const setRoute = useApp((s) => s.setRoute);
  const setLeftPanel = useApp((s) => s.setLeftPanel);
  const cap = useQuery<LabCapabilities>("/api/lab/capabilities", { ttlMs: 30 * 60_000 });
  const exps = useQuery<{ experiments: Experiment[] }>("/api/experiments", { ttlMs: 30 * 60_000 });
  const q = toQuery(applied);
  const scope = useQuery<RecordsSummary>(`/api/records/summary${q ? `?${q}` : ""}`);
  const [form, setForm] = useState<LabForm>(defaultForm);
  // İş yokken sonuç alanı boş kalmasın: kayıtlı Faz 3 deneyleri varsayılan sekme
  const [tab, setTab] = useState<string>(activeJobId ? "result" : "saved");
  const [saved, setSaved] = useState<Experiment | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [history, setHistory] = useState(0);
  const jobs = useQuery<{ jobs: Job[] }>(tab === "history" ? `/api/lab/jobs?n=${history}` : null, { ttlMs: 0 });

  const validation = useMemo(() => (cap.data ? validateForm(form, cap.data) : null), [form, cap.data]);
  const filtersTr = describe(applied, { borough: (b) => BOROUGH_TR[b] ?? b, vehicle: trLabel });
  useEffect(() => setSubmitError(null), [form, applied]);

  const submit = async () => {
    if (!validation) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const job = await postJSON<Job>("/api/lab/jobs", { algorithm: form.algorithm, feature_set: form.featureSet, params: validation.params,
        filters: toBody(applied), sample: validation.sample });
      setActiveJob(job.job_id);
      setSaved(null);
      setTab("result");
      // Dar ekranda sonuç formun altında: sonuca kaydır
      requestAnimationFrame(() => document.getElementById("lab-results")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (cap.status === "error" && !cap.data) return <div className="p-4 sm:p-6"><ErrorBlock error={cap.error} onRetry={cap.reload} /></div>;
  if (!cap.data || !validation) return <div className="p-4 sm:p-6"><LoadingBlock lines={10} /></div>;
  const experiments = exps.data?.experiments ?? [];

  return (
    <div className="mx-auto w-full max-w-[1480px] p-4 sm:p-6 space-y-5" data-testid="lab">
      <PageHeader eyebrow="Kümeleme Laboratuvarı" title="Deney tasarla, çalıştır, karşılaştır"
        description="Yeni analiz sunucuda ayrı bir süreçte gerçek kayıtlar üzerinde çalışır; kaynak bütçesi fit öncesinde denetlenir. Faz 3 ızgarasındaki bir konfigürasyon seçilirse doğrulanmış kayıtlı sonuç yüklenir." />
      {!isEmpty(applied) && (
        <Note title="Filtre kapsamı etkin" testId="lab-filter-scope">
          Bu analiz yalnızca 3D Keşif'te uygulanan filtrelere uyan kayıtlar üzerinde YENİ kümeleme yapar. Haritadaki "mevcut kümelerde göster"
          görünümü yeniden kümeleme değildir.
        </Note>
      )}
      <div className="grid gap-5 lg:grid-cols-[400px_minmax(0,1fr)] items-start">
        <Section id="controls" title="Yeni analiz" className="lg:sticky lg:top-4">
          <AlgorithmControls form={form} setForm={setForm} cap={cap.data} validation={validation} scope={scope.data}
            filtersTr={filtersTr} filtersEmpty={isEmpty(applied)} experiments={experiments} submitting={submitting} submitError={submitError}
            onEditFilters={() => { setLeftPanel("filters"); setRoute("explorer"); }} onSubmit={submit} />
        </Section>
        <section id="lab-results" className="surface p-4 sm:p-5 min-w-0 scroll-mt-4" aria-label="Sonuçlar">
          <Tabs value={tab} onValueChange={setTab} className="gap-4">
            <TabsList className="bg-surface-2 flex-wrap h-auto">
              <TabsTrigger value="result" data-testid="tab-result">Sonuç</TabsTrigger>
              <TabsTrigger value="saved" data-testid="tab-saved">Kayıtlı deneyler ({experiments.length})</TabsTrigger>
              <TabsTrigger value="history" data-testid="tab-history" onClick={() => setHistory((n) => n + 1)}>İş geçmişi</TabsTrigger>
            </TabsList>
            <TabsContent value="result">
              {saved ? <SavedResultView exp={saved} /> : activeJobId ? <JobView jobId={activeJobId} /> : (
                <EmptyBlock>Henüz analiz yok. Soldan bir konfigürasyon seçip "Analizi başlat"a basın veya "Kayıtlı deneyler" sekmesinden bir Faz 3 deneyi yükleyin.</EmptyBlock>
              )}
            </TabsContent>
            <TabsContent value="saved">
              {exps.status === "error" ? <ErrorBlock error={exps.error} /> : !exps.data ? <LoadingBlock lines={6} /> : (
                <SavedExperiments experiments={experiments} selected={saved?.experiment_id ?? null}
                  onSelect={(e) => { setSaved(e); setTab("result"); }} />
              )}
            </TabsContent>
            <TabsContent value="history">
              {jobs.status === "error" ? <ErrorBlock error={jobs.error} /> : !jobs.data ? <LoadingBlock lines={4} /> : jobs.data.jobs.length === 0 ? (
                <EmptyBlock>Bu sunucu oturumunda iş yok. (Tamamlanan sonuçlar diskte önbelleklenir; aynı istek yeniden hesaplanmaz.)</EmptyBlock>
              ) : (
                <ul className="divide-y divide-line" data-testid="job-history">
                  {jobs.data.jobs.map((j) => (
                    <li key={j.job_id}>
                      <button type="button" className="flex w-full flex-wrap items-center gap-2 py-2.5 text-left text-[12.5px] hover:bg-surface-2/60 focus-visible:ring-2 focus-visible:ring-ring rounded-sm outline-none px-1"
                        onClick={() => { setSaved(null); setActiveJob(j.job_id); setTab("result"); }}>
                        <StateBadge state={j.state} />
                        <span className="font-semibold">{j.request.algorithm.toUpperCase()}</span>
                        <span className="tabular text-muted-foreground">{Object.entries(j.request.params).map(([k, v]) => `${k}=${v ?? "oto"}`).join(" ")}</span>
                        <span className="text-subtle truncate">{j.filters_tr.join(" · ")}</span>
                        <code className="ml-auto text-[11px] text-subtle">{j.job_id}</code>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </div>
  );
}
