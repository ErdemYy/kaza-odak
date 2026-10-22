// Genel bakış: tüm sayılar /api/overview'dan (Faz 1–4 doğrulanmış kayıtları). Sabit örnek değer yoktur.
import { AlertTriangle, ExternalLink, Map as MapIcon, Table2, BarChart3 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import { ColumnChart } from "../../components/charts";
import { ExportMenu } from "../../components/ExportMenu";
import { ErrorBlock, InfoTip, LoadingBlock, MetricCard, PageHeader, Section } from "../../components/common";
import { BOROUGH_TR } from "../../lib/camera";
import { fmtInt, fmtPct } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { Overview } from "../../lib/types";

const REASON_TR: Record<string, string> = {
  missing: "Koordinat eksik", zero: "Koordinat 0,0", invalid_range: "Geçersiz aralık", outside_nyc_far: "NYC'den uzak",
  invalid_crash_date: "Geçersiz tarih",
};

export default function OverviewPage() {
  const q = useQuery<Overview>("/api/overview");
  const setRoute = useApp((s) => s.setRoute);
  const setSource = useApp((s) => s.setSource);
  const requestFocus = useApp((s) => s.requestFocus);
  const [yearTable, setYearTable] = useState(false);

  if (q.status === "error" && !q.data) return <div className="p-4 sm:p-6"><ErrorBlock error={q.error} onRetry={q.reload} /></div>;
  const o = q.data;
  if (!o) return <div className="p-4 sm:p-6 space-y-4"><LoadingBlock lines={3} /><LoadingBlock lines={8} /></div>;

  const fr = o.source.freshness;
  const stale = fr.verdict_at_check === "stale";
  const partial = new Map(o.coverage.partial_years.map((p) => [p.year, p.reason]));
  const eligibleShare = o.records.eligible / o.records.raw_total;
  const boroughs = o.by_borough.filter((b) => b.borough !== "UNKNOWN");
  const unknown = o.by_borough.find((b) => b.borough === "UNKNOWN");
  const maxEv = Math.max(...boroughs.map((b) => b.events));
  // Model tüm uygun kayıtlarla mı eğitildi? (kümelenmiş + gürültü = uygun) — eşitse modelin veri dönemi analiz kapsamıdır.
  const modelOnAllEligible = o.model.events_clustered + o.model.events_noise === o.records.eligible;
  const day = (iso: string | null | undefined) => iso?.slice(0, 10) ?? "—";
  const exclusions = Object.entries(o.records.exclusion_reasons).filter(([k]) => k !== "none").sort((a, b) => b[1] - a[1]);
  const openCluster = (id: number) => {
    setSource({ kind: "model" });
    requestFocus("model", id);
    setRoute("explorer");
  };

  return (
    <div className="mx-auto w-full max-w-[1480px] p-4 sm:p-6 space-y-5" data-testid="overview">
      <PageHeader eyebrow="NYC Motorlu Araç Kazaları" title="Genel bakış"
        description={<>Kaynak: <a className="text-primary underline underline-offset-2 hover:decoration-2" href={o.source.source_url} target="_blank" rel="noopener">{o.source.dataset_name ?? o.source.dataset_id} <ExternalLink className="inline size-3" /></a> · {o.source.attribution ?? "NYPD"}</>}
        actions={<>
          <ExportMenu base="/api/export/records" label="Özeti dışa aktar" testId="overview-export" />
          <Button size="sm" onClick={() => setRoute("explorer")}><MapIcon /> 3D haritada aç</Button>
        </>} />

      {/* Kaynak ve kapsam bloğu: güncellik uyarısı (gizlenmez) + kaynak tarihi, analiz kapsamı ve modelin veri dönemi daima
          görünür. Uyarı ile şerit tek blokta: uyarı cümlesi kaynak tarihini zaten içerdiği için ayrı kutu dikey yer kaybıydı. */}
      <section className={cn("surface overflow-hidden", stale && "border-warning/45")} aria-label="Veri kaynağı ve analiz kapsamı" data-testid="ov-scope">
        {stale && (
          <div role="note" data-testid="freshness-warning" className="flex items-start gap-2.5 border-b border-warning/35 bg-warning/[0.07] px-4 py-2.5 text-[12.5px] leading-snug">
            <AlertTriangle className="size-4 shrink-0 mt-[1px] text-warning" aria-hidden />
            <p className="min-w-0 text-muted-foreground">
              <b className="font-semibold text-foreground">Veri güncellik uyarısı:</b> kaynak satırları en son{" "}
              <b className="font-semibold text-foreground">{day(fr.rows_updated_at)}</b> tarihinde güncellendi (bugün itibarıyla{" "}
              {fmtInt(fr.days_since_rows_updated_now)} gün; eşik {fr.staleness_threshold_days} gün); analiz{" "}
              <b className="font-semibold text-foreground">{o.coverage.date_max}</b> tarihine kadarki kayıtları kapsar.{" "}
              <span className="inline-flex align-middle" data-testid="freshness-details">
                <InfoTip label="Güncellik ayrıntıları">
                  Yayıncı günlük güncelleme beyan ediyor. Kontrol tarihi {day(fr.checked_at)}: son güncellemeden {fmtInt(fr.days_since_rows_updated_at_check)} gün
                  geçmişti. Analizde kullanılan anlık görüntü {o.source.snapshot}.
                </InfoTip>
              </span>
            </p>
          </div>
        )}
        <div className="grid grid-cols-1 divide-y divide-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="px-4 py-2.5 min-w-0">
            <div className="text-[11.5px] font-medium text-muted-foreground">Kaynak tarihi</div>
            <div className="font-display font-bold text-[15px] tabular" data-testid="ov-source-date">{day(fr.rows_updated_at)}</div>
            <div className="text-[11.5px] text-subtle truncate">son satır güncellemesi · indirme {day(o.source.acquisition?.retrieval_completed_utc as string | undefined)}</div>
          </div>
          <div className="px-4 py-2.5 min-w-0" data-testid="ov-coverage">
            <div className="text-[11.5px] font-medium text-muted-foreground">Analiz kapsamı</div>
            <div className="font-display font-bold text-[15px] tabular">{o.coverage.date_min} → {o.coverage.date_max}</div>
            <div className="text-[11.5px] text-subtle">{o.coverage.partial_years.length ? `Kısmi yıllar: ${o.coverage.partial_years.map((p) => p.year).join(", ")}` : "Tam yıllar"}</div>
          </div>
          <div className="px-4 py-2.5 min-w-0" data-testid="ov-model-period">
            <div className="text-[11.5px] font-medium text-muted-foreground">Modelin veri dönemi</div>
            <div className="font-display font-bold text-[15px] tabular">{modelOnAllEligible ? `${o.coverage.date_min} → ${o.coverage.date_max}` : "—"}</div>
            <div className="text-[11.5px] text-subtle">{modelOnAllEligible ? `Tüm uygun kayıtlar (${fmtInt(o.records.eligible)})` : "Kapsam meta verisinde doğrulanamadı"}</div>
          </div>
        </div>
      </section>

      {/* Odak: analize uygun kayıtlar */}
      <section className="surface grid gap-6 p-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]" aria-labelledby="hero-title">
        <div className="min-w-0">
          <h2 id="hero-title" className="eyebrow">Coğrafi analize uygun kayıt</h2>
          <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-display text-[44px] sm:text-[56px] font-extrabold leading-none tabular" data-testid="hero-eligible">{fmtInt(o.records.eligible)}</span>
            <span className="text-[15px] text-muted-foreground">/ {fmtInt(o.records.raw_total)} kaynak kaydı ({fmtPct(eligibleShare)})</span>
          </div>
          <div className="mt-4 h-2.5 w-full overflow-hidden rounded-sm bg-surface-2 flex" role="img"
            aria-label={`Uygun ${fmtInt(o.records.eligible)}, dışlanan ${fmtInt(o.records.excluded)} kayıt`}>
            <span className="h-full bg-primary" style={{ width: `${eligibleShare * 100}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-[12.5px] tabular">
            <span><span className="inline-block size-2 rounded-sm bg-primary mr-1.5" aria-hidden />Uygun {fmtInt(o.records.eligible)}</span>
            <span className="text-muted-foreground"><span className="inline-block size-2 rounded-sm bg-surface-3 mr-1.5" aria-hidden />Dışlanan {fmtInt(o.records.excluded)}</span>
          </div>
          <details className="disclosure mt-3 rounded-md border border-line px-3 py-2" data-testid="exclusion-details">
            <summary className="text-[12.5px] font-semibold">Dışlanan kayıtların nedenleri ve eksik koordinatlar</summary>
            <dl className="mt-2.5 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2 text-[12.5px]">
              {exclusions.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2 border-b border-line/60 pb-1">
                  <dt className="text-muted-foreground">{REASON_TR[k] ?? k}</dt><dd className="tabular">{fmtInt(v)}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2.5 text-[12px] text-subtle leading-snug">
              Uygun = geçerli NYC koordinatı (resmî ilçe sınırı içinde veya kıyıya yakın) ve geçerli tarih. Dışlanan kayıtlar ham veride
              korunur; yalnızca coğrafi analizden çıkarılır.
            </p>
          </details>
        </div>
        <div className="grid grid-cols-2 gap-x-5 gap-y-4 content-start border-t border-line pt-5 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6">
          <MetricCard label="Seçilen model" testId="ov-model"
            value={<span className="text-[18px]">{o.model.algorithm.toUpperCase()}</span>}
            hint={<>eps = {o.model.parameters.eps_m} m · min_samples = {o.model.parameters.min_samples}<br /><span className="text-[11px]">Deney kimliği <code>{o.model.experiment_id}</code></span></>} />
          <MetricCard label="Küme sayısı" value={fmtInt(o.model.clusters)} tone="primary" testId="ov-clusters"
            hint={`${fmtInt(o.model.events_clustered)} olay kümelerde`} />
          <MetricCard label="Gürültü oranı" value={fmtPct(o.model.noise_ratio)} testId="ov-noise"
            info="DBSCAN'in hiçbir kümeye atamadığı olayların payı (etiket −1). Yüksek oran, modelin yalnızca kavşak ölçeğindeki kronik yoğunlaşmaları temsil ettiğini gösterir; bir hata ölçüsü değildir."
            hint={`${fmtInt(o.model.events_noise)} olay · hata ölçüsü değil`} />
          <MetricCard label="Benzersiz konum" value={fmtInt(o.records.unique_locations)} testId="ov-locations"
            hint="uygun kayıtların tekil koordinatları" />
          <MetricCard label="Yaralanmalı kaza" value={fmtInt(o.totals.injury_crashes)} tone="warning" hint={`${fmtInt(o.totals.persons_injured)} yaralı kişi`} />
          <MetricCard label="Ölümle sonuçlanan kaza" value={fmtInt(o.totals.fatal_crashes)} tone="hotspot" hint={`${fmtInt(o.totals.persons_killed)} ölü kişi`} />
        </div>
      </section>

      <div className="grid gap-5 2xl:grid-cols-2">
        <Section id="years" title="Yıllara göre kaza sayısı"
          description={<>Payda: {o.denominators.by_year}. Soluk çubuklar kısmi yıllardır; yıllar arası karşılaştırmada dikkate alınmalıdır.</>}
          actions={<Button size="sm" variant="ghost" onClick={() => setYearTable((t) => !t)} aria-pressed={yearTable}>
            {yearTable ? <><BarChart3 /> Grafik</> : <><Table2 /> Tablo</>}
          </Button>}>
          {yearTable ? (
            <Table>
              <TableHeader><TableRow><TableHead>Yıl</TableHead><TableHead className="text-right">Kaza</TableHead><TableHead>Not</TableHead></TableRow></TableHeader>
              <TableBody>
                {o.by_year.map((y) => (
                  <TableRow key={y.year}><TableCell>{y.year}</TableCell><TableCell className="text-right tabular">{fmtInt(y.count)}</TableCell>
                    <TableCell className="text-muted-foreground text-[12px]">{partial.get(y.year) ?? ""}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <ColumnChart testId="year-chart" ariaLabel="Yıllara göre kümelemeye uygun kaza sayısı" valueLabel="Kaza" height={240}
              data={o.by_year.map((y) => ({ label: String(y.year), value: y.count, flag: partial.get(y.year) ?? null }))} />
          )}
        </Section>

        <Section id="boroughs" title="Beş ilçenin karşılaştırmalı özeti"
          description={<>Payda: {o.denominators.by_borough}.{unknown && unknown.events > 0 ? ` İlçesi belirlenemeyen ${fmtInt(unknown.events)} uygun kayıt tabloda yok.` : ""}</>}>
          <div className="overflow-x-auto -mx-1 px-1">
            <Table data-testid="borough-table" className="text-[12.5px]">
              <TableHeader>
                <TableRow>
                  <TableHead>İlçe</TableHead>
                  <TableHead className="text-right">Kaza</TableHead>
                  <TableHead className="text-right">Yaralanmalı</TableHead>
                  <TableHead className="text-right">Ölümlü</TableHead>
                  <TableHead className="text-right">
                    <span className="inline-flex items-center gap-1">Kümelerde <InfoTip>Seçili DBSCAN modelinin bir kümesine düşen olayların payı.</InfoTip></span>
                  </TableHead>
                  <TableHead className="text-right">
                    <span className="inline-flex items-center gap-1">Küme <InfoTip>Baskın ilçesi bu ilçe olan küme sayısı.</InfoTip></span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {boroughs.map((b) => (
                  <TableRow key={b.borough}>
                    <TableCell className="font-semibold">{BOROUGH_TR[b.borough] ?? b.borough}</TableCell>
                    <TableCell className="text-right tabular">
                      <div className="flex items-center justify-end gap-2">
                        <span className="hidden md:block h-1.5 w-20 rounded-sm bg-surface-2" aria-hidden><span className="block h-full rounded-sm bg-primary" style={{ width: `${(b.events / maxEv) * 100}%` }} /></span>
                        {fmtInt(b.events)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular">{fmtPct(b.injury_crashes / b.events)}</TableCell>
                    <TableCell className="text-right tabular">{fmtInt(b.fatal_crashes)}</TableCell>
                    <TableCell className="text-right tabular">{fmtPct(b.events_in_clusters / b.events)}</TableCell>
                    <TableCell className="text-right tabular">{fmtInt(b.clusters_dominant ?? null)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-[11.5px] text-subtle">Yaralanmalı oran = en az bir yaralı bildirilen kaza / ilçedeki kaza. Kaza yoğunluğu araç veya yaya başına risk anlamına gelmez (trafik hacmi verisi yok).</p>
        </Section>
      </div>

      <Section id="top" title="En yüksek kayıt sayısına sahip kümeler"
        description={<>Seçili model {o.model.experiment_id}; olay sayısına göre ilk 10. Küme numaraları yalnızca bu deneye aittir.</>}>
        <div className="overflow-x-auto -mx-1 px-1">
          <Table data-testid="top-clusters" className="text-[12.5px]">
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead><TableHead>Küme</TableHead><TableHead>İlçe</TableHead><TableHead>Başlıca cadde</TableHead>
                <TableHead className="text-right">Kaza</TableHead><TableHead className="text-right">Yaralanmalı</TableHead>
                <TableHead className="text-right">Ölümlü</TableHead><TableHead className="text-right">Konum</TableHead>
                <TableHead className="text-right">Zirve saat</TableHead><TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {o.top_clusters.map((c) => (
                <TableRow key={c.cluster_id}>
                  <TableCell className="tabular text-muted-foreground">{c.rank_by_events}</TableCell>
                  <TableCell className="tabular font-semibold">#{c.cluster_id}</TableCell>
                  <TableCell>{c.dominant_borough ? BOROUGH_TR[c.dominant_borough] : "—"}</TableCell>
                  <TableCell className="max-w-[260px] truncate" title={c.top_street ?? ""}>{c.top_street ?? "—"}</TableCell>
                  <TableCell className="text-right tabular font-semibold">{fmtInt(c.n_events)}</TableCell>
                  <TableCell className="text-right tabular">{fmtInt(c.injury_crashes)}</TableCell>
                  <TableCell className="text-right tabular">{fmtInt(c.fatal_crashes)}</TableCell>
                  <TableCell className="text-right tabular">{fmtInt(c.n_unique_locations)}</TableCell>
                  <TableCell className={cn("text-right tabular", c.peak_hour === 0 && "text-warning")} title={c.peak_hour === 0 ? "00:00 zirvesi gece yarısı yuvarlama şüphesiyle tutarlı olabilir" : undefined}>
                    {String(c.peak_hour).padStart(2, "0")}:00
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="xs" variant="ghost" onClick={() => openCluster(c.cluster_id)} aria-label={`Küme #${c.cluster_id} haritada aç`} data-testid={`open-cluster-${c.cluster_id}`}>
                      <MapIcon /> Haritada
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>

      <p className="text-[11.5px] text-subtle">
        Veri sürümü <code>{o.model.dataset_version}</code> · işlem sürümü <code>{o.model.processing_version}</code>
        {o.model.software ? ` · scikit-learn ${o.model.software["scikit-learn"]}` : ""}
      </p>
    </div>
  );
}
