// Görünüm paneli: haritadaki veri kaynağı (model kartı), ilçe seçimi ve katman kontrolü.
import { Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import type { Meta } from "../../lib/api";
import { BOROUGH_ORDER, BOROUGH_TR } from "../../lib/camera";
import { isEmpty } from "../../lib/filters";
import { fmtInt, fmtPct } from "../../lib/format";
import { LAYERS } from "../../lib/layers";
import { Stat } from "../../components/ui";

export function ViewPanel({ meta, onBorough, zoom, layerCounts }: {
  meta: Meta | null; onBorough: (b: string | null) => void; zoom: number;
  layerCounts: { clusters: number; total: number; label: string } | null;
}) {
  const source = useApp((s) => s.source);
  const setSource = useApp((s) => s.setSource);
  const borough = useApp((s) => s.borough);
  const visibility = useApp((s) => s.visibility);
  const toggleLayer = useApp((s) => s.toggleLayer);
  const filtered = useApp((s) => s.applied);
  const m = meta?.model;
  const hasFilters = !isEmpty(filtered);

  return (
    <div className="space-y-4">
      <section data-testid="model-card" aria-label="Haritadaki kümeleme sonucu">
        <h2 className="eyebrow mb-2">{source.kind === "model" ? "Kümeleme modeli" : "Gösterilen sonuç"}</h2>
        {source.kind === "result" ? (
          <div className="rounded-md border border-warning/40 bg-warning/[0.06] p-3 space-y-2" data-testid="result-card">
            <div className="flex items-center justify-between gap-2">
              <span className="font-display font-bold text-[14px]">{source.algorithm.toUpperCase()}</span>
              <Badge variant="outline" className="border-warning/60 text-warning">{source.dynamic ? "Dinamik analiz" : "Kayıtlı deney"}</Badge>
            </div>
            <code className="block text-[11.5px] text-muted-foreground break-all" data-testid="result-id">{source.id}</code>
            <p className="text-[12px] text-muted-foreground leading-snug">{source.label}</p>
            {layerCounts && <p className="text-[12px] tabular">{fmtInt(layerCounts.total)} küme</p>}
            <Button size="sm" variant="outline" className="w-full" onClick={() => setSource({ kind: "model" })} data-testid="back-to-model">
              <Undo2 /> Seçili modele dön
            </Button>
          </div>
        ) : m ? (
          <div className="rounded-md border border-line bg-surface-2/60 p-3 space-y-2.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-display font-bold text-[14px]">{m.algorithm.toUpperCase()}</span>
              <code className="text-[11px] text-muted-foreground" data-testid="experiment-id">{m.experiment_id}</code>
            </div>
            <div className="text-[12.5px] text-muted-foreground tabular" data-testid="model-params">
              eps = {m.parameters.eps_m} m · min_samples = {m.parameters.min_samples}
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <Stat label="Küme" value={<span data-testid="meta-clusters">{fmtInt(meta!.counts.clusters)}</span>} tone="primary" />
              <Stat label="Gürültü oranı" value={<span data-testid="meta-noise">{fmtPct(meta!.counts.noise_ratio)}</span>} />
              <Stat label="Kümelenmiş olay" value={<span data-testid="meta-clustered">{fmtInt(meta!.counts.events_clustered)}</span>} tone="warning" />
              <Stat label="Gürültü olayı" value={fmtInt(meta!.counts.events_noise)} />
            </div>
            {hasFilters && layerCounts && (
              <p className="text-[12px] text-warning leading-snug" data-testid="filtered-cluster-count">
                Filtreyle kayıt içeren küme: {fmtInt(layerCounts.clusters)} / {fmtInt(layerCounts.total)}
              </p>
            )}
            <p className="text-[11.5px] text-subtle leading-snug">
              Toplam {fmtInt(meta!.counts.events_total)} olay. Değerler SHA-256 ile doğrulanmış Faz 3 çıktılarından okunur; küme numaraları yalnızca bu deneye aittir.
            </p>
          </div>
        ) : (
          <div className="h-[150px] rounded-md bg-surface-2/60 animate-pulse" role="status" aria-label="Model bilgisi yükleniyor" />
        )}
      </section>

      <section>
        <h2 className="eyebrow mb-2">İlçe (kamera)</h2>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="İlçe seçici" data-testid="borough-picker">
          <button type="button" className="chip" aria-pressed={borough === null} onClick={() => onBorough(null)}>Tüm NYC</button>
          {BOROUGH_ORDER.map((b) => (
            <button key={b} type="button" className="chip" aria-pressed={borough === b} disabled={!meta?.boroughs?.bounds[b]}
              onClick={() => onBorough(b)} data-borough={b}>{BOROUGH_TR[b]}</button>
          ))}
        </div>
        <p className="text-[11.5px] text-subtle mt-1.5">Kamerayı ilçeye götürür; kayıtları süzmek için Filtreler sekmesini kullanın.</p>
      </section>

      <section>
        <h2 className="eyebrow mb-1">Katmanlar</h2>
        <ul data-testid="layer-list">
          {LAYERS.map((l) => {
            const tooFar = zoom < l.minZoom;
            const outOfZoom = tooFar || zoom > l.maxZoom;
            const unavailable = l.key === "geometries" && source.kind === "result";
            return (
              <li key={l.key} className="flex items-center gap-2.5 py-1">
                <Switch checked={visibility[l.key]} onCheckedChange={() => toggleLayer(l.key)} aria-label={l.label} />
                <div className="min-w-0 flex-1" title={l.hint}>
                  <div className="text-[13px] font-semibold leading-tight" data-layer={l.key}>{l.label}</div>
                  <div className={cn("text-[11.5px] leading-tight line-clamp-2", (outOfZoom && visibility[l.key]) || unavailable ? "text-warning" : "text-subtle")}>
                    {unavailable ? "Yalnızca seçili modelde (dışbükey zarf) mevcut"
                      : outOfZoom && visibility[l.key]
                        ? tooFar ? `Yakınlaştırınca görünür (zoom ≥ ${l.minZoom})` : `Uzaklaştırınca görünür (zoom ≤ ${l.maxZoom})`
                        : l.hint}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
