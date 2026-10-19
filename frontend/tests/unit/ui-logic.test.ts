import { describe, expect, it } from "vitest";
import { assertClusterMatch, type ClusterDetail } from "../../src/lib/api";
import { BOROUGH_ORDER, boroughTarget, cityTarget, clusterTarget, durationFor } from "../../src/lib/camera";
import type { BBox, LngLat } from "../../src/lib/geo";
import { haversineM, localOffsetM } from "../../src/lib/geo";
import { defaultVisibility, densityCell, isActive, pointQueryKind, toggleLayer } from "../../src/lib/layers";
import { PALETTES, themePaint } from "../../src/map/style";
import { nearestCandidate } from "../../src/map/picking";
import { pickRoadSegment } from "../../src/map/traffic";

// Gerçek DCP ilçe sınırı kutuları (layer_manifest.json'dan; sunucu bu değerleri döndürür)
const BOUNDS: Record<string, BBox> = {
  MANHATTAN: [-74.04773, 40.682917, -73.906651, 40.879038], BRONX: [-73.933606, 40.785357, -73.765332, 40.915533],
  BROOKLYN: [-74.041897, 40.56953, -73.833559, 40.739128], QUEENS: [-73.96262, 40.541834, -73.700009, 40.801011],
  "STATEN ISLAND": [-74.255591, 40.496134, -74.049236, 40.648926],
};

describe("Kamera odaklama", () => {
  it("beş ilçenin her biri kendi gerçek sınır kutusuna gider", () => {
    for (const b of BOROUGH_ORDER) {
      const t = boroughTarget(b, BOUNDS, "full", 1600);
      expect(t.bounds).toEqual(BOUNDS[b]);
      expect(t.duration).toBeGreaterThan(0);
    }
    expect(() => boroughTarget("NEWARK", BOUNDS, "full", 1600)).toThrow(/Bilinmeyen ilçe/);
  });
  it("varsayılan görünüm beş ilçenin birleşimini kapsar", () => {
    const t = cityTarget(BOUNDS, "full", 1600);
    expect(t.bounds).toEqual([-74.255591, 40.496134, -73.700009, 40.915533]);
  });
  it("animasyon kapalıyken geçişler anlık, azaltılmışta kısalır", () => {
    expect(durationFor("off", 2000)).toBe(0);
    expect(durationFor("reduced", 2000)).toBe(800);
    expect(boroughTarget("BROOKLYN", BOUNDS, "off", 1600).duration).toBe(0);
  });
  it("küme odağı: merkez korunur, geniş kümede daha uzak zoom, yön korunur", () => {
    const c: LngLat = [-73.98453, 40.69603];
    const small = clusterTarget(c, 1, 30, "full");
    const wide = clusterTarget(c, 120, 30, "full");
    expect(small.center).toEqual(c);
    expect(small.bearing).toBe(30);
    expect(wide.zoom).toBeLessThan(small.zoom);
    expect(small.zoom).toBeLessThanOrEqual(19.2);
    expect(wide.zoom).toBeGreaterThanOrEqual(17.2);
  });
});

describe("Küme seçimi (üst üste binen daireler)", () => {
  it("tıklanan noktaya ekranda en yakın merkez seçilir, çizim sırası değil", () => {
    // 1331 daha sonra çizilip üstte olsa bile tıklama 1344'ün merkezine daha yakın
    const c = [{ id: 1331, screen: [512, 300] as [number, number] }, { id: 1344, screen: [500, 304] as [number, number] }];
    expect(nearestCandidate([501, 304], c)).toBe(1344);
    expect(nearestCandidate([511, 300], c)).toBe(1331);
  });
  it("eşit uzaklıkta deterministik (küçük kimlik), aday yoksa null", () => {
    expect(nearestCandidate([0, 0], [{ id: 9, screen: [1, 0] }, { id: 3, screen: [-1, 0] }])).toBe(3);
    expect(nearestCandidate([0, 0], [])).toBeNull();
  });
});

describe("Katman görünürlüğü", () => {
  it("gürültü varsayılan kapalı; açılıp kapatılabilir", () => {
    const v = defaultVisibility();
    expect(v.noise).toBe(false);
    const on = toggleLayer(v, "noise");
    expect(on.noise).toBe(true);
    expect(toggleLayer(on, "noise").noise).toBe(false);
    expect(v.noise).toBe(false); // değişmez (saf)
  });
  it("noktalar yalnızca yüksek zoomda sorgulanır; tür seçimi görünürlüğe bağlı", () => {
    const v = defaultVisibility();
    expect(pointQueryKind(v, 12)).toBeNull();
    expect(pointQueryKind(v, 16)).toBe("clustered");
    expect(pointQueryKind(toggleLayer(v, "noise"), 16)).toBe("all");
    expect(pointQueryKind(toggleLayer(toggleLayer(v, "noise"), "clustered"), 16)).toBe("noise");
    expect(pointQueryKind(toggleLayer(v, "clustered"), 16)).toBeNull();
    expect(isActive(v, "geometries", 10)).toBe(false);
    expect(isActive(v, "centroids", 10)).toBe(true);
  });
  it("yoğunluk hücresi zoom'a göre", () => {
    expect(densityCell(10)).toBe(1000);
    expect(densityCell(13)).toBe(250);
  });
});

describe("Küme kimliği eşleşmesi", () => {
  const d = { cluster_id: 1344, experiment_id: "dbscan-52abd2c018" } as ClusterDetail;
  it("aynı deney + kimlik kabul edilir", () => expect(() => assertClusterMatch(d, 1344, "dbscan-52abd2c018")).not.toThrow());
  it("farklı kimlik veya farklı modelin kimliği reddedilir", () => {
    expect(() => assertClusterMatch(d, 1345, "dbscan-52abd2c018")).toThrow(/eşleşmiyor/);
    expect(() => assertClusterMatch(d, 1344, "kmeans-24c07e9946")).toThrow(/eşleşmiyor/);
  });
});

describe("Temsili trafik için yol seçimi", () => {
  const c: LngLat = [-73.98453, 40.69603];
  it("en yakın yol seçilir ve merkez etrafında ±90 m kesilir", () => {
    const near: LngLat[] = [[-73.9870, 40.69610], [-73.9820, 40.69610]]; // ~8 m kuzeyde doğu-batı yol
    const far: LngLat[] = [[-73.9870, 40.6990], [-73.9820, 40.6990]];
    const seg = pickRoadSegment(c, [far, near])!;
    expect(seg).not.toBeNull();
    for (const p of seg) expect(Math.abs(p[1] - 40.6961)).toBeLessThan(1e-6);
    const len = haversineM(seg[0], seg[seg.length - 1]);
    expect(len).toBeGreaterThan(175);
    expect(len).toBeLessThan(185);
  });
  it("60 m içinde yol yoksa null (araç gösterilmez)", () => {
    expect(pickRoadSegment(c, [[[-73.9870, 40.6990], [-73.9820, 40.6990]]])).toBeNull();
    expect(pickRoadSegment(c, [])).toBeNull();
  });
  it("daha yakın ama çok kısa parça yerine kullanılabilir uzunluğu yeterli yol seçilir", () => {
    const shortNear: LngLat[] = [[-73.98455, 40.69604], [-73.98450, 40.69604]]; // ~4 m, merkeze 1 m
    const longFar: LngLat[] = [[-73.9870, 40.69630], [-73.9820, 40.69630]]; // ~30 m uzakta, 400+ m uzun
    const seg = pickRoadSegment(c, [shortNear, longFar])!;
    expect(haversineM(seg[0], seg[seg.length - 1])).toBeGreaterThan(170);
  });
  it("kısa yol kendi uzunluğunda kalır", () => {
    const seg = pickRoadSegment(c, [[[-73.9846, 40.6961], [-73.9844, 40.6961]]])!;
    const [x0, , z0] = localOffsetM(c, seg[0]);
    const [x1, , z1] = localOffsetM(c, seg[seg.length - 1]);
    expect(Math.hypot(x1 - x0, z1 - z0)).toBeLessThan(20);
  });
});

it("gece/gündüz paletleri aynı katmanları kapsar", () => {
  expect(Object.keys(themePaint("night"))).toEqual(Object.keys(themePaint("day")));
  expect(PALETTES.night.background).toBe("#0B1120");
});
