// Küme seçimi: tıklanan noktaya EKRANDA en yakın küme merkezi. Düşük zoomda komşu kümelerin daireleri
// üst üste biner; "en üstte çizilen" öğeyi almak yanlış kümeyi açabilir.
import type { Map as MlMap } from "maplibre-gl";
import type { LngLat } from "../lib/geo";

export type CentroidIndex = Map<number, { lngLat: LngLat; experimentId: string }>;

const HIT_PX = 6;

/** Saf seçim kuralı: adaylar arasından piksel uzaklığı en küçük olanı (eşitlikte küçük kimlik). */
export function nearestCandidate(click: [number, number], candidates: { id: number; screen: [number, number] }[]): number | null {
  let best: { id: number; d: number } | null = null;
  for (const c of candidates) {
    const d = Math.hypot(c.screen[0] - click[0], c.screen[1] - click[1]);
    if (!best || d < best.d - 1e-9 || (Math.abs(d - best.d) <= 1e-9 && c.id < best.id)) best = { id: c.id, d };
  }
  return best?.id ?? null;
}

export function pickCluster(map: MlMap, x: number, y: number, index: CentroidIndex, layers: string[]): { clusterId: number; experimentId: string } | null {
  const feats = map.queryRenderedFeatures([[x - HIT_PX, y - HIT_PX], [x + HIT_PX, y + HIT_PX]], { layers: layers.filter((l) => map.getLayer(l)) });
  const ids = [...new Set(feats.map((f) => Number(f.properties.cluster_id)).filter((v) => Number.isInteger(v) && index.has(v)))];
  const candidates = ids.map((id) => {
    const p = map.project(index.get(id)!.lngLat);
    return { id, screen: [p.x, p.y] as [number, number] };
  });
  const id = nearestCandidate([x, y], candidates);
  return id === null ? null : { clusterId: id, experimentId: index.get(id)!.experimentId };
}
