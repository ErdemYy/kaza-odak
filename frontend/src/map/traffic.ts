// Temsili trafik için yol seçimi: küme merkezine en yakın GERÇEK yol çizgisi (OSM, OpenMapTiles
// "transportation" katmanı). Araç hareketi temsili bir simülasyondur; geçmiş kaza hareket kaydı değildir.
import type { Map as MlMap } from "maplibre-gl";
import type { LngLat } from "../lib/geo";
import { closestPointOnSegment, localOffsetM, localToLngLat } from "../lib/geo";

const ROAD_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "minor"];
const MAX_SNAP_M = 60; // merkezden bu mesafede yol yoksa araç gösterilmez
const HALF_LENGTH_M = 90;

const MIN_USABLE_M = 60;

/**
 * Saf işlev: merkeze `maxSnap` içindeki çizgilerden, merkez etrafında en az MIN_USABLE_M kullanılabilir
 * uzunluğu olanların en yakınını seçer (yoksa en uzun kullanılabilir olanı); ±yarı uzunluk kadar keser.
 * Karo sınırlarında bölünmüş kısa parçalar böylece tercih edilmez.
 */
export function pickRoadSegment(center: LngLat, lines: LngLat[][], halfLength = HALF_LENGTH_M, maxSnap = MAX_SNAP_M): LngLat[] | null {
  type Cand = { line: [number, number][]; cum: number[]; s: number; dist: number; usable: number };
  const cands: Cand[] = [];
  for (const line of lines) {
    const loc = line.map((p) => {
      const [x, , z] = localOffsetM(center, p);
      return [x, z] as [number, number];
    });
    if (loc.length < 2) continue;
    const cum = [0];
    for (let i = 1; i < loc.length; i++) cum.push(cum[i - 1] + Math.hypot(loc[i][0] - loc[i - 1][0], loc[i][1] - loc[i - 1][1]));
    let best: { s: number; dist: number } | null = null;
    for (let i = 1; i < loc.length; i++) {
      const c = closestPointOnSegment([0, 0], loc[i - 1], loc[i]);
      if (!best || c.dist < best.dist) best = { s: cum[i - 1] + c.t * (cum[i] - cum[i - 1]), dist: c.dist };
    }
    if (!best || best.dist > maxSnap) continue;
    const L = cum[cum.length - 1];
    cands.push({ line: loc, cum, s: best.s, dist: best.dist, usable: Math.min(best.s, halfLength) + Math.min(L - best.s, halfLength) });
  }
  if (!cands.length) return null;
  const long = cands.filter((c) => c.usable >= MIN_USABLE_M).sort((a, b) => a.dist - b.dist);
  const best = long[0] ?? cands.sort((a, b) => b.usable - a.usable)[0];
  const { cum, s } = best;
  const s0 = Math.max(0, s - halfLength), s1 = Math.min(cum[cum.length - 1], s + halfLength);
  const at = (d: number): [number, number] => {
    let i = 1;
    while (i < cum.length - 1 && cum[i] < d) i++;
    const k = (d - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
    return [best.line[i - 1][0] + k * (best.line[i][0] - best.line[i - 1][0]), best.line[i - 1][1] + k * (best.line[i][1] - best.line[i - 1][1])];
  };
  const pts: [number, number][] = [at(s0)];
  for (let i = 0; i < cum.length; i++) if (cum[i] > s0 && cum[i] < s1) pts.push(best.line[i]);
  pts.push(at(s1));
  return pts.map(([x, z]) => localToLngLat(center, x, z));
}

/** Haritada yüklü karolardan yol çizgilerini toplar (karo sınırlarında bölünmüş parçalar dahil). */
export function nearbyRoads(map: MlMap): LngLat[][] {
  const feats = map.querySourceFeatures("omt", {
    sourceLayer: "transportation",
    filter: ["in", ["get", "class"], ["literal", ROAD_CLASSES]],
  });
  const lines: LngLat[][] = [];
  for (const f of feats) {
    const g = f.geometry;
    if (g.type === "LineString") lines.push(g.coordinates as LngLat[]);
    else if (g.type === "MultiLineString") for (const l of g.coordinates) lines.push(l as LngLat[]);
  }
  return lines;
}
