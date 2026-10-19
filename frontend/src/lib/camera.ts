// Kamera hedefleri: gerçek ilçe sınırı kutularından ve gerçek küme merkezlerinden hesaplanır.
import type { BBox, LngLat } from "./geo";
import { bboxUnion } from "./geo";
import type { MotionLevel } from "./layers";

export const BOROUGH_TR: Record<string, string> = {
  MANHATTAN: "Manhattan", BROOKLYN: "Brooklyn", QUEENS: "Queens", BRONX: "Bronx", "STATEN ISLAND": "Staten Island",
};
export const BOROUGH_ORDER = ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"] as const;

// Manhattan cadde ızgarası gerçek kuzeye göre ~29° döndürülmüştür; genel görünümde hafif açı.
export const DEFAULT_PITCH = 45;
export const DEFAULT_BEARING = -17;

export interface FitTarget {
  kind: "fit";
  bounds: BBox;
  pitch: number;
  bearing: number;
  padding: { top: number; bottom: number; left: number; right: number };
  duration: number;
}

export interface FlyTarget {
  kind: "fly";
  center: LngLat;
  zoom: number;
  pitch: number;
  bearing: number;
  duration: number;
}

export function durationFor(motion: MotionLevel, ms: number): number {
  return motion === "off" ? 0 : motion === "reduced" ? Math.round(ms * 0.4) : ms;
}

/** Arayüz panellerinin kapladığı kenar boşlukları (haritanın görünen kısmı ortalanır). */
export function panelPadding(width: number): FitTarget["padding"] {
  return width < 900 ? { top: 80, bottom: 200, left: 24, right: 24 } : { top: 96, bottom: 72, left: 340, right: 380 };
}

export function cityTarget(bounds: Record<string, BBox>, motion: MotionLevel, width: number): FitTarget {
  return { kind: "fit", bounds: bboxUnion(Object.values(bounds)), pitch: DEFAULT_PITCH, bearing: DEFAULT_BEARING,
    padding: panelPadding(width), duration: durationFor(motion, 2200) };
}

export function boroughTarget(name: string, bounds: Record<string, BBox>, motion: MotionLevel, width: number): FitTarget {
  const b = bounds[name];
  if (!b) throw new Error(`Bilinmeyen ilçe: ${name}`);
  return { kind: "fit", bounds: b, pitch: 50, bearing: DEFAULT_BEARING, padding: panelPadding(width), duration: durationFor(motion, 2400) };
}

/** Kümeye yakınlaşma: küme yarıçapına göre zoom (geniş kümede daha uzak), mevcut yön korunur. */
export function clusterTarget(center: LngLat, radiusP90M: number, bearing: number, motion: MotionLevel): FlyTarget {
  const r = Math.max(15, Math.min(radiusP90M || 0, 200));
  // r=15 m → 19,2 (araç modelleri ~20 px); r=120 m → 17,5 (zarfın tamamı görünür)
  const zoom = Math.max(17.2, Math.min(19.2, 19.2 - Math.log2(r / 15) * 0.57));
  return { kind: "fly", center, zoom, pitch: 62, bearing, duration: durationFor(motion, 2600) };
}
