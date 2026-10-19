import type { Meta } from "../lib/api";
import { BOROUGH_ORDER, BOROUGH_TR } from "../lib/camera";
import { fmtInt, fmtPct } from "../lib/format";
import type { LayerKey, Visibility } from "../lib/layers";
import { LAYERS } from "../lib/layers";
import { Stat, Switch } from "./ui";

export function SidePanel({ meta, borough, onBorough, visibility, onToggle, zoom }: {
  meta: Meta | null; borough: string | null; onBorough: (b: string | null) => void; visibility: Visibility;
  onToggle: (k: LayerKey) => void; zoom: number;
}) {
  const m = meta?.model;
  return (
    <aside className="pointer-events-auto min-h-0 flex-1 overflow-y-auto scroll-thin panel p-3.5 space-y-4" aria-label="Görünüm ve katmanlar">
      <section data-testid="model-card">
        <h2 className="panel-title mb-2">Kümeleme modeli</h2>
        {m ? (
          <div className="rounded-xl border border-line bg-surface-2/60 p-3 space-y-2.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-display font-bold text-[14px]">{m.algorithm.toUpperCase()}</span>
              <code className="text-[11px] text-muted" data-testid="experiment-id">{m.experiment_id}</code>
            </div>
            <div className="text-[12.5px] text-muted tabular" data-testid="model-params">
              eps = {m.parameters.eps_m} m · min_samples = {m.parameters.min_samples}
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <Stat label="Küme" value={<span data-testid="meta-clusters">{fmtInt(meta!.counts.clusters)}</span>} tone="primary" />
              <Stat label="Gürültü oranı" value={<span data-testid="meta-noise">{fmtPct(meta!.counts.noise_ratio)}</span>} />
              <Stat label="Kümelenmiş olay" value={<span data-testid="meta-clustered">{fmtInt(meta!.counts.events_clustered)}</span>} tone="warning" />
              <Stat label="Gürültü olayı" value={fmtInt(meta!.counts.events_noise)} />
            </div>
            <p className="text-[11px] text-subtle leading-snug">
              Toplam {fmtInt(meta!.counts.events_total)} olay. Değerler SHA-256 ile doğrulanmış Faz 3 çıktılarından okunur; küme numaraları yalnızca bu deneye aittir.
            </p>
          </div>
        ) : (
          <div className="h-[150px] rounded-xl bg-surface-2/60 animate-pulse" aria-label="Model bilgisi yükleniyor" />
        )}
      </section>

      <section>
        <h2 className="panel-title mb-2">İlçe</h2>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="İlçe seçici" data-testid="borough-picker">
          <button type="button" className="chip" aria-pressed={borough === null} onClick={() => onBorough(null)}>Tüm NYC</button>
          {BOROUGH_ORDER.map((b) => (
            <button key={b} type="button" className="chip" aria-pressed={borough === b} disabled={!meta?.boroughs?.bounds[b]}
              onClick={() => onBorough(b)} data-borough={b}>{BOROUGH_TR[b]}</button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="panel-title mb-1">Katmanlar</h2>
        <ul data-testid="layer-list">
          {LAYERS.map((l) => {
            const tooFar = zoom < l.minZoom;
            const outOfZoom = tooFar || zoom > l.maxZoom;
            return (
              <li key={l.key} className="flex items-center gap-2.5 py-1">
                <Switch checked={visibility[l.key]} onChange={() => onToggle(l.key)} label={l.label} />
                <div className="min-w-0 flex-1" title={l.hint}>
                  <div className="text-[13px] font-semibold leading-tight" data-layer={l.key}>{l.label}</div>
                  <div className={`text-[11px] leading-tight truncate ${outOfZoom && visibility[l.key] ? "text-warning" : "text-subtle"}`}>
                    {outOfZoom && visibility[l.key]
                      ? tooFar ? `Yakınlaştırınca görünür (zoom ≥ ${l.minZoom})` : `Uzaklaştırınca görünür (zoom ≤ ${l.maxZoom})`
                      : l.hint}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </aside>
  );
}
