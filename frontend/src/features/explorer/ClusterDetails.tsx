// Seçili küme ayrıntıları. Tüm değerler sunucudan; kaynakta olmayan alan "mevcut değil" olarak gösterilir.
// Filtre etkinse tam küme ile filtrelenmiş kayıtlar ayrı sütunlarda gösterilir (etiketler değişmez).
import { Crosshair, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { InfoTip } from "../../components/common";
import { Stat } from "../../components/ui";
import { BOROUGH_TR } from "../../lib/camera";
import { fmtCoord, fmtInt, fmtNum, fmtPct, trLabel } from "../../lib/format";
import type { ClusterState, Selection } from "./CityMap";

function HourBars({ hist, peak, label }: { hist: number[]; peak: number; label: string }) {
  const max = Math.max(...hist, 1);
  const total = hist.reduce((a, b) => a + b, 0);
  return (
    <figure>
      <div className="flex items-end gap-[2px] h-11" role="img" aria-label={`${label}. Zirve ${String(peak).padStart(2, "0")}:00, toplam ${fmtInt(total)} kayıt.`}>
        {hist.map((v, h) => (
          <div key={h} title={`${String(h).padStart(2, "0")}:00 — ${fmtInt(v)} kayıt`}
            className={cn("flex-1 rounded-[2px]", h === peak ? "bg-hotspot" : "bg-primary/55")} style={{ height: `${Math.max(3, (v / max) * 100)}%` }} />
        ))}
      </div>
      <div className="flex justify-between text-[10.5px] text-subtle tabular mt-1" aria-hidden><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
    </figure>
  );
}

function Bars({ rows, note }: { rows: { label: string; share: number | null; count: number }[]; note?: string }) {
  if (!rows.length) return <p className="text-[12px] text-subtle">Mevcut değil.</p>;
  return (
    <>
      <ul className="space-y-1.5">
        {rows.map((v) => (
          <li key={v.label} className="grid grid-cols-[minmax(0,1fr)_72px_44px] items-center gap-2 text-[12px]">
            <span className="truncate" title={v.label}>{v.label}</span>
            <span className="h-1.5 rounded bg-surface-2" aria-hidden><span className="block h-full rounded bg-primary" style={{ width: `${Math.min(100, (v.share ?? 0) * 100)}%` }} /></span>
            <span className="tabular text-right text-muted-foreground" title={`${fmtInt(v.count)} kaza`}>{fmtPct(v.share, 0)}</span>
          </li>
        ))}
      </ul>
      {note && <p className="text-[11px] text-subtle mt-1.5 leading-snug">{note}</p>}
    </>
  );
}

const borough = (b: string | null | undefined) => (b ? BOROUGH_TR[b] ?? (b === "UNKNOWN" ? "Bilinmiyor" : b) : "Bilinmiyor");

function Row({ k, v, testId }: { k: string; v: React.ReactNode; testId?: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground shrink-0">{k}</dt>
      <dd className="text-right tabular min-w-0" data-testid={testId}>{v}</dd>
    </div>
  );
}

export function ClusterDetails({ state, onClose, onFocus, roadNote }: { state: ClusterState; onClose: () => void; onFocus: () => void; roadNote: string | null }) {
  if (state.status === "idle") {
    return (
      <div className="p-3.5" data-testid="cluster-hint">
        <h2 className="eyebrow mb-1">Küme ayrıntısı</h2>
        <p className="text-[12.5px] text-muted-foreground leading-snug">Ayrıntıları görmek için haritada bir küme merkezine veya küme geometrisine tıklayın.</p>
      </div>
    );
  }
  const id = state.status === "ready" ? (state.selection.kind === "model" ? state.selection.detail.cluster_id : state.selection.row.cluster_id) : state.clusterId;
  return (
    <div className="p-3.5" data-testid="cluster-panel" data-status={state.status} aria-busy={state.status === "loading"}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <h2 className="eyebrow">Seçilen küme</h2>
          {state.status === "ready" && (
            <div className="font-display font-bold text-[18px] leading-tight mt-0.5" data-testid="cluster-title">
              Küme #{id}
              {(state.selection.kind === "model" ? state.selection.detail.rank_by_events : state.selection.row.rank_by_events) && (
                <span className="ml-2 text-[12px] font-semibold text-muted-foreground">
                  {fmtInt(state.selection.kind === "model" ? state.selection.detail.rank_by_events : state.selection.row.rank_by_events)}. sırada
                </span>
              )}
            </div>
          )}
        </div>
        <Button variant="outline" size="icon-sm" onClick={onClose} aria-label="Seçimi kapat"><X /></Button>
      </div>
      {state.status === "loading" && (
        <div className="space-y-2">
          <div className="h-5 rounded bg-surface-2 animate-pulse" />
          <div className="h-16 rounded bg-surface-2 animate-pulse" />
          <p className="text-[12px] text-muted-foreground" role="status">Küme #{state.clusterId} yükleniyor…</p>
        </div>
      )}
      {state.status === "error" && (
        <div role="alert" className="rounded-md border border-hotspot/50 bg-hotspot/10 p-3 text-[12.5px]">
          Küme #{state.clusterId} yüklenemedi: {state.message}
        </div>
      )}
      {state.status === "ready" && (state.selection.kind === "model"
        ? <ModelDetail s={state.selection} onFocus={onFocus} roadNote={roadNote} />
        : <ResultDetail s={state.selection} onFocus={onFocus} roadNote={roadNote} />)}
    </div>
  );
}

function ModelDetail({ s, onFocus, roadNote }: { s: Extract<Selection, { kind: "model" }>; onFocus: () => void; roadNote: string | null }) {
  const d = s.detail;
  const r = s.records;
  const f = r?.filtered;
  const filtered = !!r?.filters_active;
  const street = d.top_streets.slice(0, 2).map((x) => x.value);
  const hours = filtered && f ? f.by_hour : d.hour_histogram;
  const peak = hours.indexOf(Math.max(...hours));
  const n = filtered && f ? f.n_events : d.n_events;
  const vehicles = f
    ? f.by_vehicle.filter((v) => v.count > 0).sort((a, b) => b.count - a.count).slice(0, 4).map((v) => ({ label: trLabel(v.value), count: v.count, share: n ? v.count / n : null }))
    : d.top_vehicle_categories.slice(0, 3).map((v) => ({ label: trLabel(v.value), count: v.count, share: v.share }));
  const factors = f
    ? f.top_factors.slice(0, 4).map((x) => ({ label: x.value, count: x.crashes, share: x.share }))
    : d.top_contributing_factors.slice(0, 3).map((x) => ({ label: x.value, count: x.count, share: x.share }));
  const boroughs = f?.boroughs ?? [];
  return (
    <div className="space-y-3.5">
      {filtered && f && (
        <div className="rounded-md border border-warning/40 bg-warning/[0.06] p-2.5" data-testid="cluster-filtered">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <Badge variant="outline" className="border-warning/60 text-warning">Filtre etkin</Badge>
            <InfoTip>Küme sınırları ve üyeliği tam veri modelinden gelir (yeniden kümeleme yapılmadı). Sağ sütun, bu kümenin filtreye uyan kayıtlarıdır.</InfoTip>
          </div>
          <table className="w-full text-[12px] tabular">
            <thead><tr className="text-muted-foreground"><th className="text-left font-medium" /><th className="text-right font-medium">Tam küme</th><th className="text-right font-medium">Filtrelenmiş</th></tr></thead>
            <tbody>
              <tr><td>Kaza</td><td className="text-right">{fmtInt(d.n_events)}</td><td className="text-right font-semibold" data-testid="cluster-filtered-events">{fmtInt(f.n_events)}</td></tr>
              <tr><td>Yaralanmalı</td><td className="text-right">{fmtInt(d.injury_crashes)}</td><td className="text-right">{fmtInt(f.injury_crashes)}</td></tr>
              <tr><td>Ölümlü</td><td className="text-right">{fmtInt(d.fatal_crashes)}</td><td className="text-right">{fmtInt(f.fatal_crashes)}</td></tr>
            </tbody>
          </table>
        </div>
      )}
      <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Stat label="Kaza (kayıt)" value={<span data-testid="cluster-events">{fmtInt(d.n_events)}</span>} tone="hotspot" />
        <Stat label="İlçe" value={<span data-testid="cluster-borough">{borough(d.dominant_borough)}</span>} />
        <Stat label="Yaralanmalı kaza" value={fmtInt(d.injury_crashes)} tone="warning" />
        <Stat label="Ölümlü kaza" value={fmtInt(d.fatal_crashes)} />
        <Stat label="Yaralı / ölü kişi" value={`${fmtInt(d.persons_injured)} / ${fmtInt(d.persons_killed)}`} />
        <Stat label="Benzersiz konum" value={fmtInt(d.n_unique_locations)} />
      </div>
      <dl className="text-[12px] space-y-1.5">
        <Row k="Merkez" v={fmtCoord(d.centroid_lon, d.centroid_lat)} testId="cluster-center" />
        <Row k="Başlıca caddeler" v={street.join(" / ") || "Mevcut değil"} />
        <Row k="İlgili ilçeler" v={boroughs.length ? boroughs.map((b) => `${borough(b.value)} (${fmtInt(b.count)})`).join(", ")
          : d.dominant_borough_share != null ? `${borough(d.dominant_borough)} (%${fmtNum(d.dominant_borough_share * 100, 0)})` : "Mevcut değil"} />
        <Row k="Tarih aralığı" v={`${d.date_min} → ${d.date_max}`} />
        <Row k="Etkin yıl" v={d.active_years} />
        <Row k="Yarıçap (p90)" v={`${fmtNum(d.radius_p90_m, 1)} m`} />
      </dl>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">
          Saatlik dağılım{filtered ? " (filtrelenmiş)" : ""} · zirve {String(peak).padStart(2, "0")}:00
        </div>
        <HourBars hist={hours} peak={peak} label="Saatlere göre kaza dağılımı" />
        {peak === 0 && <p className="text-[11px] text-warning mt-1 leading-snug">00:00 zirvesi, saati bilinmeyen kayıtların gece yarısına yuvarlanmasından kaynaklanabilir.</p>}
      </div>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">Araç türleri</div>
        <Bars rows={vehicles} note={f ? "Kazaya karışan araç kategorileri; bir kaza birden çok kategoride sayılabilir." : "Araç 1 kategorisi (Faz 3 profili)."} />
      </div>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">Kaydedilmiş katkı faktörleri</div>
        <Bars rows={factors} note={`${f ? `'Unspecified' payı (araç 1): ${fmtPct(f.factor_unspecified_share, 0)}. ` : ""}Metinler kaynak veri setindeki (NYPD) İngilizce kodlardır; nedensellik kanıtı değildir.`} />
      </div>
      {s.recordsError && <p className="text-[11px] text-subtle">Ek profil alınamadı: {s.recordsError}</p>}
      <div className="rounded-md border border-line p-2.5 text-[12px] space-y-1">
        <div className="text-[11.5px] text-muted-foreground">Model parametreleri</div>
        <div className="tabular">{r ? `${r.model.algorithm.toUpperCase()} · eps = ${r.model.parameters.eps_m} m · min_samples = ${r.model.parameters.min_samples}` : "DBSCAN (seçili model)"}</div>
        {r && <div className="text-subtle text-[11.5px]">{r.model.features} · {r.model.metric}</div>}
      </div>
      <div className="flex items-center justify-between gap-2 pt-1 border-t border-line">
        <code className="text-[11px] text-subtle truncate" data-testid="cluster-experiment">{d.experiment_id}</code>
        <Button size="sm" variant="outline" onClick={onFocus}><Crosshair /> Odakla</Button>
      </div>
      {roadNote && <p className="text-[11.5px] text-subtle leading-snug" data-testid="sim-note">{roadNote}</p>}
    </div>
  );
}

function ResultDetail({ s, onFocus, roadNote }: { s: Extract<Selection, { kind: "result" }>; onFocus: () => void; roadNote: string | null }) {
  const r = s.row;
  const meta = s.meta as { request?: { algorithm: string; params: Record<string, unknown> }; algorithm?: string; params?: Record<string, unknown>; scope_text?: string; filters_tr?: string[] };
  const algo = meta.request?.algorithm ?? meta.algorithm ?? "";
  const params = meta.request?.params ?? meta.params ?? {};
  const peak = r.hour_histogram.indexOf(Math.max(...r.hour_histogram));
  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Stat label="Kaza (kayıt)" value={<span data-testid="cluster-events">{fmtInt(r.n_events)}</span>} tone="hotspot" />
        <Stat label="İlçe" value={<span data-testid="cluster-borough">{borough(r.dominant_borough)}</span>} />
        <Stat label="Yaralanmalı kaza" value={fmtInt(r.injury_crashes)} tone="warning" />
        <Stat label="Ölümlü kaza" value={fmtInt(r.fatal_crashes)} />
        <Stat label="Yaralı / ölü kişi" value={`${fmtInt(r.persons_injured)} / ${fmtInt(r.persons_killed)}`} />
        <Stat label="Benzersiz konum" value={fmtInt(r.n_unique_locations)} />
      </div>
      <dl className="text-[12px] space-y-1.5">
        <Row k="Merkez" v={fmtCoord(r.centroid_lon, r.centroid_lat)} testId="cluster-center" />
        <Row k="İlgili ilçeler" v={r.boroughs.map((b) => `${borough(b.value)} (${fmtInt(b.count)})`).join(", ") || "Mevcut değil"} />
        <Row k="Tarih aralığı" v={`${r.date_min} → ${r.date_max}`} />
        <Row k="Yarıçap (p90)" v={`${fmtNum(r.radius_p90_m, 1)} m`} />
      </dl>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">Saatlik dağılım · zirve {String(peak).padStart(2, "0")}:00</div>
        <HourBars hist={r.hour_histogram} peak={peak} label="Saatlere göre kaza dağılımı" />
      </div>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">Araç türleri</div>
        <Bars rows={r.vehicles.filter((v) => v.count > 0).sort((a, b) => b.count - a.count).slice(0, 4).map((v) => ({ label: trLabel(v.value), count: v.count, share: v.share }))}
          note="Bir kaza birden çok kategoride sayılabilir." />
      </div>
      <div>
        <div className="text-[11.5px] text-muted-foreground mb-1">Kaydedilmiş katkı faktörleri</div>
        <Bars rows={r.top_factors.slice(0, 4).map((x) => ({ label: x.value, count: x.crashes, share: x.share }))}
          note={`'Unspecified' payı (araç 1): ${fmtPct(r.factor_unspecified_share, 0)}. NYPD İngilizce kodları; nedensellik kanıtı değildir.`} />
      </div>
      <div className="rounded-md border border-line p-2.5 text-[12px] space-y-1">
        <div className="text-[11.5px] text-muted-foreground">Model parametreleri</div>
        <div className="tabular break-words">{algo.toUpperCase()} · {Object.entries(params).map(([k, v]) => `${k} = ${v ?? "—"}`).join(" · ")}</div>
        {meta.scope_text && <div className="text-subtle text-[11.5px]">{meta.scope_text}</div>}
      </div>
      <div className="flex items-center justify-between gap-2 pt-1 border-t border-line">
        <code className="text-[11px] text-subtle truncate" data-testid="cluster-experiment">{s.resultId}</code>
        <Button size="sm" variant="outline" onClick={onFocus}><Crosshair /> Odakla</Button>
      </div>
      <p className="text-[11px] text-subtle">Küme numaraları yalnızca bu sonuca aittir; seçili modelin numaralarıyla eşleştirilemez.</p>
      {roadNote && <p className="text-[11.5px] text-subtle leading-snug" data-testid="sim-note">{roadNote}</p>}
    </div>
  );
}
