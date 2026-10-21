import type { PointsResponse } from "../lib/api";
import { fmtInt } from "../lib/format";

export type ViewportInfo =
  | { state: "zoom-in"; minZoom: number }
  | { state: "off" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: Pick<PointsResponse, "total_locations" | "total_events" | "returned_locations" | "returned_events" | "truncated" | "kind"> & { limit?: number } };

export function Legend({ viewport }: { viewport: ViewportInfo }) {
  return (
    <div className="px-0.5" data-testid="legend">
      <h2 className="panel-title mb-2">Lejant</h2>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-primary" />Küme merkezi (küçük)</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-hotspot" />Küme merkezi (büyük)</li>
        <li className="flex items-center gap-2" title="Üye konumların dışbükey zarfı; gerçek bir yoğunluk sınırı değildir">
          <span className="w-3 h-3 rounded-sm bg-warning/40 border border-warning" />Küme zarfı (dışbükey)
        </li>
        <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-[#94A3B8]" />Gürültü (−1)</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-[#2A3B5C]" />3D bina (OSM yük.)</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-[#141F33] border border-[#2A3B5C]" />Yükseklik verisi yok</li>
        <li className="col-span-2 flex items-center gap-2">
          <span className="w-14 h-2 rounded bg-gradient-to-r from-primary/40 via-warning to-hotspot" />Kayıtlı kaza yoğunluğu (gösterilen kapsam)
        </li>
        <li className="col-span-2 text-[11px] text-subtle leading-snug" data-testid="legend-semantics">
          Zarf, üye konumları çevreleyen dışbükey çokgendir; gerçek yoğunluk sınırı değildir. Yüksek kaza yoğunluğu trafik hacmine
          göre risk anlamına gelmez.
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
