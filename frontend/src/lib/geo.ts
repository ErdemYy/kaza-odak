// Coğrafi dönüşümler: WGS84 boylam/enlem ↔ MapLibre Web Mercator birimleri (0..1 dünya karesi).
// MapLibre ile aynı küre yarıçapı kullanılır (MercatorCoordinate ile birebir; birim testlerinde doğrulanır).

export const EARTH_RADIUS_M = 6371008.8;
const CIRCUMFERENCE_M = 2 * Math.PI * EARTH_RADIUS_M;

export type LngLat = [number, number];

export interface Mercator {
  x: number;
  y: number;
  z: number;
}

/** WGS84 → Mercator (x doğuya, y güneye artar; z = metre cinsinden irtifanın mercator karşılığı). */
export function toMercator([lng, lat]: LngLat, altitudeM = 0): Mercator {
  const x = (180 + lng) / 360;
  const y = (180 - (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))) / 360;
  return { x, y, z: altitudeM * meterInMercatorUnits(lat) };
}

export function fromMercator(x: number, y: number): LngLat {
  const y2 = 180 - y * 360;
  return [x * 360 - 180, (360 / Math.PI) * Math.atan(Math.exp((y2 * Math.PI) / 180)) - 90];
}

/** Verilen enlemde 1 metrenin mercator birimi karşılığı. */
export function meterInMercatorUnits(lat: number): number {
  return 1 / (CIRCUMFERENCE_M * Math.cos((lat * Math.PI) / 180));
}

/**
 * Yerel sahne çerçevesi (Three.js): çapa noktasında +X doğu, +Y yukarı, +Z güney (metre).
 * Konum, mercator farkının ÇAPA ölçeğine bölünmesiyle bulunur; sahne matrisi aynı ölçekle geri
 * çarptığı için konum hatasızdır (yalnızca model boyutu enlem farkı oranında, ~1e-5, değişir).
 */
export function localOffsetM(anchor: LngLat, p: LngLat, altitudeM = 0): [number, number, number] {
  const a = toMercator(anchor);
  const b = toMercator(p);
  const s = meterInMercatorUnits(anchor[1]);
  return [(b.x - a.x) / s, altitudeM, (b.y - a.y) / s];
}

export function localToLngLat(anchor: LngLat, eastM: number, southM: number): LngLat {
  const a = toMercator(anchor);
  const s = meterInMercatorUnits(anchor[1]);
  return fromMercator(a.x + eastM * s, a.y + southM * s);
}

/**
 * Çapa → mercator dönüşüm matrisi (sütun-öncelikli 4×4, WebGL düzeni):
 * T(çapa) · S(s, −s, s) · Rx(π/2). Yerel (x doğu, y yukarı, z güney) → mercator (x, y güney, z yukarı).
 */
export function anchorMatrix(anchor: LngLat, altitudeM = 0): number[] {
  const m = toMercator(anchor, altitudeM);
  const s = meterInMercatorUnits(anchor[1]);
  // S·Rx(π/2): (x, y, z) → (s·x, s·z, s·y)
  return [s, 0, 0, 0, 0, 0, s, 0, 0, s, 0, 0, m.x, m.y, m.z, 1];
}

/** 4×4 sütun-öncelikli matris × [x, y, z, 1]. */
export function transformPoint(m: ArrayLike<number>, [x, y, z]: [number, number, number]): [number, number, number, number] {
  return [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
    m[3] * x + m[7] * y + m[11] * z + m[15],
  ];
}

/**
 * Pusula yönü (derece, kuzeyden saat yönünde) → Three.js Y ekseni dönüşü (radyan),
 * ileri yönü +Z olan model için (Kenney araçları). Kuzey yerel −Z, doğu +X'tir.
 */
export function headingToRotationY(headingDeg: number): number {
  return Math.PI - (headingDeg * Math.PI) / 180;
}

/** İki nokta arası pusula yönü (derece, 0 = kuzey, 90 = doğu). */
export function bearingDeg(a: LngLat, b: LngLat): number {
  const [l1, p1] = a.map((v) => (v * Math.PI) / 180);
  const [l2, p2] = b.map((v) => (v * Math.PI) / 180);
  const y = Math.sin(l2 - l1) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(l2 - l1);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export function haversineM(a: LngLat, b: LngLat): number {
  const r = Math.PI / 180;
  const dLat = (b[1] - a[1]) * r;
  const dLng = (b[0] - a[0]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

export type BBox = [number, number, number, number]; // batı, güney, doğu, kuzey

export function bboxUnion(boxes: BBox[]): BBox {
  return boxes.reduce<BBox>((u, b) => [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])],
    [Infinity, Infinity, -Infinity, -Infinity]);
}

export function bboxSpan(b: BBox): number {
  return Math.max(b[2] - b[0], b[3] - b[1]);
}

/** Kutuyu en yakın ızgaraya genişletir: küçük kaydırmalarda aynı API isteği tekrar kullanılır. */
export function snapBBox(b: BBox, step = 0.002): BBox {
  return [Math.floor(b[0] / step) * step, Math.floor(b[1] / step) * step, Math.ceil(b[2] / step) * step,
    Math.ceil(b[3] / step) * step].map((v) => Number(v.toFixed(6))) as BBox;
}

export function bboxContains(outer: BBox, inner: BBox): boolean {
  return outer[0] <= inner[0] && outer[1] <= inner[1] && outer[2] >= inner[2] && outer[3] >= inner[3];
}

/** Bir çizgi parçasına en yakın nokta (yerel düzlemde, metre). */
export function closestPointOnSegment(p: [number, number], a: [number, number], b: [number, number]): { point: [number, number]; t: number; dist: number } {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  const point: [number, number] = [a[0] + t * dx, a[1] + t * dy];
  return { point, t, dist: Math.hypot(p[0] - point[0], p[1] - point[1]) };
}
