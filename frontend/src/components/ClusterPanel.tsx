import type { ClusterDetail } from "../lib/api";
import { BOROUGH_TR } from "../lib/camera";
import { fmtCoord, fmtInt, fmtNum, fmtPct, trLabel } from "../lib/format";
import { Icon, ICONS, Stat } from "./ui";

export type ClusterState =
  | { status: "idle" }
  | { status: "loading"; clusterId: number }
  | { status: "error"; clusterId: number; message: string }
  | { status: "ready"; detail: ClusterDetail };

function HourBars({ hist, peak }: { hist: number[]; peak: number }) {
  const max = Math.max(...hist, 1);
  return (
    <div className="flex items-end gap-[2px] h-10" aria-label={`Saatlere göre kaza dağılımı, zirve ${peak}:00`} role="img">
      {hist.map((v, h) => (
        <div key={h} title={`${String(h).padStart(2, "0")}:00 — ${fmtInt(v)}`}
          className={`flex-1 rounded-[2px] ${h === peak ? "bg-hotspot" : "bg-primary/55"}`} style={{ height: `${Math.max(4, (v / max) * 100)}%` }} />
      ))}
    </div>
  );
}

export function ClusterPanel({ state, onClose, onFocus, roadNote }: { state: ClusterState; onClose: () => void; onFocus: () => void; roadNote: string | null }) {
  if (state.status === "idle") {
    return (
      <div className="absolute z-10 right-3 top-[84px] w-[340px] panel p-3.5 hidden md:block fade-in" data-testid="cluster-hint">
        <h2 className="panel-title mb-1">Küme ayrıntısı</h2>
        <p className="text-[12.5px] text-muted leading-snug">Ayrıntıları görmek için haritada bir küme merkezine veya küme geometrisine tıklayın.</p>
      </div>
    );
  }
  return (
    <aside className="absolute z-10 right-3 top-[84px] w-[340px] max-h-[calc(100%-120px)] overflow-y-auto scroll-thin panel p-3.5 fade-in"
      aria-label="Seçilen küme" data-testid="cluster-panel" data-status={state.status}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h2 className="panel-title">Seçilen küme</h2>
          {state.status === "ready" && (
            <div className="font-display font-bold text-[18px] leading-tight mt-0.5" data-testid="cluster-title">
              Küme #{state.detail.cluster_id}
              <span className="ml-2 text-[12px] font-semibold text-muted">{fmtInt(state.detail.rank_by_events)}. sırada</span>
            </div>
          )}
        </div>
        <button type="button" className="btn !p-1.5" onClick={onClose} aria-label="Seçimi kapat"><Icon d={ICONS.close} size={14} /></button>
      </div>

      {state.status === "loading" && (
        <div className="space-y-2" aria-busy="true">
          <div className="h-5 rounded bg-surface-2 animate-pulse" />
          <div className="h-16 rounded bg-surface-2 animate-pulse" />
          <p className="text-[12px] text-muted">Küme #{state.clusterId} yükleniyor…</p>
        </div>
      )}
      {state.status === "error" && (
        <div role="alert" className="rounded-lg border border-hotspot/50 bg-hotspot/10 p-3 text-[12.5px]">
          Küme #{state.clusterId} yüklenemedi: {state.message}
        </div>
      )}
      {state.status === "ready" && <Detail d={state.detail} onFocus={onFocus} roadNote={roadNote} />}
    </aside>
  );
}

function Detail({ d, onFocus, roadNote }: { d: ClusterDetail; onFocus: () => void; roadNote: string | null }) {
  const street = d.top_streets.slice(0, 2).map((s) => s.value);
  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
        <Stat label="Kaza (kayıt)" value={<span data-testid="cluster-events">{fmtInt(d.n_events)}</span>} tone="hotspot" />
        <Stat label="İlçe" value={<span data-testid="cluster-borough">{d.dominant_borough ? BOROUGH_TR[d.dominant_borough] ?? d.dominant_borough : "Bilinmiyor"}</span>} />
        <Stat label="Yaralanmalı kaza" value={fmtInt(d.injury_crashes)} tone="warning" />
        <Stat label="Ölümlü kaza" value={fmtInt(d.fatal_crashes)} />
        <Stat label="Yaralı / ölü kişi" value={`${fmtInt(d.persons_injured)} / ${fmtInt(d.persons_killed)}`} />
        <Stat label="Benzersiz konum" value={fmtInt(d.n_unique_locations)} />
      </div>
      <dl className="text-[12px] space-y-1.5">
        <div className="flex justify-between gap-3"><dt className="text-muted">Merkez</dt><dd className="tabular text-right" data-testid="cluster-center">{fmtCoord(d.centroid_lon, d.centroid_lat)}</dd></div>
        <div className="flex justify-between gap-3"><dt className="text-muted">Başlıca caddeler</dt><dd className="text-right">{street.join(" / ") || "—"}</dd></div>
        <div className="flex justify-between gap-3"><dt className="text-muted">Tarih aralığı</dt><dd className="tabular">{d.date_min} → {d.date_max}</dd></div>
        <div className="flex justify-between gap-3"><dt className="text-muted">Etkin yıl</dt><dd className="tabular">{d.active_years}</dd></div>
        <div className="flex justify-between gap-3"><dt className="text-muted">Yarıçap (p90)</dt><dd className="tabular">{fmtNum(d.radius_p90_m, 1)} m</dd></div>
        <div className="flex justify-between gap-3"><dt className="text-muted">Yaralanmalı pay</dt><dd className="tabular">{fmtPct(d.injury_crash_share)}</dd></div>
      </dl>
      <div>
        <div className="text-[11px] text-muted mb-1">Saatlik dağılım (zirve {String(d.peak_hour).padStart(2, "0")}:00)</div>
        <HourBars hist={d.hour_histogram} peak={d.peak_hour} />
      </div>
      <div>
        <div className="text-[11px] text-muted mb-1">Araç türleri</div>
        <ul className="space-y-1">
          {d.top_vehicle_categories.slice(0, 3).map((v) => (
            <li key={v.value} className="flex items-center gap-2 text-[12px]">
              <span className="w-28 truncate">{trLabel(v.value)}</span>
              <span className="flex-1 h-1.5 rounded bg-surface-2"><span className="block h-full rounded bg-primary" style={{ width: `${v.share * 100}%` }} /></span>
              <span className="tabular w-10 text-right text-muted">{fmtPct(v.share, 0)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="text-[11px] text-muted mb-1">Başlıca etkenler</div>
        <ul className="text-[12px] space-y-0.5">
          {d.top_contributing_factors.slice(0, 3).map((f) => (
            <li key={f.value} className="flex justify-between gap-2"><span className="truncate">{f.value}</span><span className="tabular text-muted">{fmtPct(f.share, 0)}</span></li>
          ))}
        </ul>
        <p className="text-[10.5px] text-subtle mt-1">Etken metinleri kaynak veri setindeki (NYPD) İngilizce kodlardır.</p>
      </div>
      <div className="flex items-center justify-between gap-2 pt-1 border-t border-line">
        <code className="text-[10.5px] text-subtle truncate" data-testid="cluster-experiment">{d.experiment_id}</code>
        <button type="button" className="btn" onClick={onFocus}><Icon d={ICONS.target} size={14} /> Odakla</button>
      </div>
      {roadNote && <p className="text-[11px] text-subtle leading-snug" data-testid="sim-note">{roadNote}</p>}
    </div>
  );
}
