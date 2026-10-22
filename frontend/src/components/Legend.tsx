import type { PointsResponse } from "../lib/api";
import { fmtInt, fmtNum } from "../lib/format";
import { CENTROID_SCALE, centroidRadius, COLORS } from "../map/dataLayers";
import { PALETTES } from "../map/style";

export type ViewportInfo =
  | { state: "zoom-in"; minZoom: number }
  | { state: "off" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: Pick<PointsResponse, "total_locations" | "total_events" | "returned_locations" | "returned_events" | "truncated" | "kind"> & { limit?: number } };

/** Küme merkezi boyut lejantı: yarıçaplar haritadaki MapLibre ifadesiyle AYNI işlevden (centroidRadius) ve
 *  geçerli zoom'da hesaplanır; renkler aynı kayıt sayısı kademelerinden gelir. */
function SizeScale({ zoom }: { zoom: number }) {
  const z = Math.min(15, Math.max(9, zoom));
  const samples = [...CENTROID_SCALE.colorStops.map(([n]) => n), CENTROID_SCALE.sqrtMax ** 2];
  const color = (n: number) => [...CENTROID_SCALE.colorStops].reverse().find(([s]) => n >= s)?.[1] ?? COLORS.primary;
  const rMax = centroidRadius(samples[samples.length - 1], z);
  return (
    <div data-testid="legend-size">
      <div className="flex items-end gap-3" aria-hidden>
        {samples.map((n) => {
          const r = centroidRadius(n, z);
          return (
            <span key={n} className="flex flex-col items-center gap-1">
              <svg width={rMax * 2 + 4} height={rMax * 2 + 4}><circle cx={rMax + 2} cy={rMax * 2 + 2 - r} r={r} fill={color(n)} fillOpacity={0.9} stroke="#0B1120" strokeWidth={1} /></svg>
              <span className="text-[10.5px] tabular text-muted-foreground">{fmtInt(n)}{n === samples[samples.length - 1] ? "+" : ""}</span>
            </span>
          );
        })}
      </div>
      <p className="text-[11px] text-subtle leading-snug mt-1">
        Küme merkezi: <b className="text-foreground font-semibold">boyut ve renk kayıt sayısını</b> gösterir (yarıçap √kayıt ile doğrusal; zoom {fmtNum(z, 1)}).
        Boyut kaza riskini değil, kayıtlı kaza sayısını temsil eder.
      </p>
    </div>
  );
}

export function Legend({ viewport, zoom = 13 }: { viewport: ViewportInfo; zoom?: number }) {
  const night = PALETTES.night;
  return (
    <div className="px-0.5" data-testid="legend">
      <h2 className="panel-title mb-2">Lejant</h2>
      <SizeScale zoom={zoom} />
      <ul className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full border-2 border-hotspot bg-hotspot/20 ring-1 ring-white/80" />Seçili küme</li>
        <li className="flex items-center gap-2" title="Üye konumların dışbükey zarfı; gerçek bir yoğunluk sınırı değildir">
          <span className="w-3 h-3 rounded-sm bg-warning/40 border border-warning" />Küme zarfı (dışbükey)
        </li>
        <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-primary border border-bg" />Kümelenmiş nokta</li>
        <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full border border-[#94A3B8] bg-[#94A3B8]/20" />Gürültü (−1)</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm" style={{ background: `linear-gradient(180deg, ${night.buildingTop}, ${night.buildingLow})` }} />3D bina (OSM yük.)</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm border" style={{ background: night.buildingUnknown, borderColor: night.buildingUnknownLine }} />Yükseklik verisi yok</li>
        <li className="col-span-2 flex items-center gap-2">
          <span className="w-14 h-2 rounded bg-gradient-to-r from-primary/40 via-warning to-hotspot" />Kayıtlı kaza yoğunluğu (gösterilen kapsam)
        </li>
        <li className="col-span-2 text-[11px] text-subtle leading-snug" data-testid="legend-semantics">
          Zarf, üye konumları çevreleyen dışbükey çokgendir; gerçek yoğunluk sınırı değildir. Yüksek kaza yoğunluğu trafik hacmine
          göre risk anlamına gelmez. Yükseklik verisi olmayan binalar düz çizilir (uydurma yükseklik yok).
        </li>
      </ul>
      <div className="mt-2.5 pt-2.5 border-t border-line text-[11.5px] tabular" data-testid="viewport-stats" data-state={viewport.state}>
        {viewport.state === "zoom-in" && <span className="text-muted-foreground">Tekil noktalar için yakınlaştırın (zoom ≥ {viewport.minZoom}).</span>}
        {viewport.state === "off" && <span className="text-muted-foreground">Nokta katmanları kapalı.</span>}
        {viewport.state === "loading" && <span className="text-muted-foreground">Görünen alan sorgulanıyor…</span>}
        {viewport.state === "error" && <span className="text-hotspot">{viewport.message}</span>}
        {viewport.state === "ready" && (
          <span>
            Görünen alan: <b>{fmtInt(viewport.data.total_locations)}</b> konum · <b>{fmtInt(viewport.data.total_events)}</b> olay
            {viewport.data.truncated ? (
              <span className="block text-warning" data-testid="points-truncated">Gösterilen: en yoğun {fmtInt(viewport.data.returned_locations)} konum ({fmtInt(viewport.data.returned_events)} olay) · görselleştirme sınırı {fmtInt(viewport.data.limit ?? viewport.data.returned_locations)} konum. Gerçek toplam yukarıdadır; tümü için yakınlaştırın.</span>
            ) : viewport.data.total_locations === 0 ? <span className="block text-muted-foreground">Bu alanda kayıt yok.</span> : null}
          </span>
        )}
      </div>
    </div>
  );
}
