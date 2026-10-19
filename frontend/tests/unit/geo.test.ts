import { MercatorCoordinate } from "maplibre-gl";
import { describe, expect, it } from "vitest";
import {
  anchorMatrix, bearingDeg, fromMercator, haversineM, headingToRotationY, localOffsetM, localToLngLat, meterInMercatorUnits,
  snapBBox, toMercator, transformPoint, type LngLat,
} from "../../src/lib/geo";

const TIMES_SQ: LngLat = [-73.98513, 40.75890];
const SI: LngLat = [-74.15, 40.58];

describe("Mercator dönüşümü MapLibre ile birebir", () => {
  for (const p of [TIMES_SQ, SI, [-73.70001, 40.91553] as LngLat]) {
    it(`toMercator ${p}`, () => {
      const ours = toMercator(p, 37);
      const ml = MercatorCoordinate.fromLngLat({ lng: p[0], lat: p[1] }, 37);
      expect(ours.x).toBeCloseTo(ml.x, 14);
      expect(ours.y).toBeCloseTo(ml.y, 14);
      expect(ours.z).toBeCloseTo(ml.z, 14);
      expect(meterInMercatorUnits(p[1])).toBeCloseTo(ml.meterInMercatorCoordinateUnits(), 16);
    });
  }
  it("ters dönüşüm", () => {
    const m = toMercator(TIMES_SQ);
    const [lng, lat] = fromMercator(m.x, m.y);
    expect(lng).toBeCloseTo(TIMES_SQ[0], 10);
    expect(lat).toBeCloseTo(TIMES_SQ[1], 10);
  });
});

describe("Çapa matrisi ve yerel çerçeve", () => {
  it("çapanın kendisi mercator konumuna gider", () => {
    const m = anchorMatrix(TIMES_SQ);
    const [x, y, z, w] = transformPoint(m, [0, 0, 0]);
    const ml = MercatorCoordinate.fromLngLat({ lng: TIMES_SQ[0], lat: TIMES_SQ[1] });
    expect([x / w, y / w, z / w]).toEqual([ml.x, ml.y, 0]);
  });
  it("yerel ofset → matris → mercator, hedef noktanın mercator konumuyla aynı (konum hatasız)", () => {
    const target: LngLat = [-73.9851, 40.7601]; // ~135 m kuzey
    const off = localOffsetM(TIMES_SQ, target);
    const [x, y] = transformPoint(anchorMatrix(TIMES_SQ), off);
    const ml = MercatorCoordinate.fromLngLat({ lng: target[0], lat: target[1] });
    expect(x).toBeCloseTo(ml.x, 15);
    expect(y).toBeCloseTo(ml.y, 15);
  });
  it("yön: +X doğu, +Z güney, +Y yukarı; mesafe haversine ile tutarlı", () => {
    const north = localOffsetM(TIMES_SQ, [TIMES_SQ[0], TIMES_SQ[1] + 0.001]);
    const east = localOffsetM(TIMES_SQ, [TIMES_SQ[0] + 0.001, TIMES_SQ[1]]);
    expect(north[2]).toBeLessThan(0);
    expect(Math.abs(north[0])).toBeLessThan(1e-9);
    expect(east[0]).toBeGreaterThan(0);
    // Mercator ölçeği yerelde haversine metreyle %0,1 içinde
    expect(Math.abs(-north[2] - haversineM(TIMES_SQ, [TIMES_SQ[0], TIMES_SQ[1] + 0.001]))).toBeLessThan(0.15);
    expect(localOffsetM(TIMES_SQ, TIMES_SQ, 12)[1]).toBe(12);
  });
  it("irtifa: yukarı = mercator z, 1 m = meterInMercatorUnits", () => {
    const [, , z] = transformPoint(anchorMatrix(TIMES_SQ), [0, 10, 0]);
    expect(z).toBeCloseTo(10 * meterInMercatorUnits(TIMES_SQ[1]), 18);
  });
  it("localToLngLat, localOffsetM'in tersidir", () => {
    const [x, , z] = localOffsetM(TIMES_SQ, SI);
    const back = localToLngLat(TIMES_SQ, x, z);
    expect(back[0]).toBeCloseTo(SI[0], 9);
    expect(back[1]).toBeCloseTo(SI[1], 9);
  });
});

describe("Model yönü", () => {
  const forward = (rotY: number) => [Math.sin(rotY), Math.cos(rotY)]; // R_y(+Z) = (sin, cos) yerel (x, z)
  it("kuzey (0°) → yerel −Z, doğu (90°) → +X, güney → +Z", () => {
    const n = forward(headingToRotationY(0));
    expect(n[0]).toBeCloseTo(0, 12);
    expect(n[1]).toBeCloseTo(-1, 12);
    const e = forward(headingToRotationY(90));
    expect(e[0]).toBeCloseTo(1, 12);
    const s = forward(headingToRotationY(180));
    expect(s[1]).toBeCloseTo(1, 12);
  });
  it("pusula yönü", () => {
    expect(bearingDeg(TIMES_SQ, [TIMES_SQ[0], TIMES_SQ[1] + 0.01])).toBeCloseTo(0, 6);
    expect(bearingDeg(TIMES_SQ, [TIMES_SQ[0] + 0.01, TIMES_SQ[1]])).toBeCloseTo(90, 1);
  });
});

it("bbox ızgaraya genişletilir (her zaman orijinali kapsar)", () => {
  const b = snapBBox([-73.9951, 40.7501, -73.9752, 40.7649]);
  expect(b[0]).toBeLessThanOrEqual(-73.9951);
  expect(b[2]).toBeGreaterThanOrEqual(-73.9752);
  expect(b[1]).toBeLessThanOrEqual(40.7501);
  expect(b[3]).toBeGreaterThanOrEqual(40.7649);
});
