// @vitest-environment jsdom
// Faz 8B: harita stilinin MapLibre şemasına uygunluğu (veri katmanları dahil), palet kontrast sıralaması, küme merkezi
// boyut ölçeği ve lejant tutarlılığı, yakın kümelerin seçim kuralı, GLB önizleyici yardımcıları (kadraj, kaynak temizliği),
// küme ayrıntı paneli ve varlık inceleyicinin "Haritaya yerleştir" akışı.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { validateStyleMin } from "@maplibre/maplibre-gl-style-spec";
import * as THREE from "three";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AssetInspector } from "../../src/components/AssetInspector";
import { Legend } from "../../src/components/Legend";
import { ClusterDetails } from "../../src/features/explorer/ClusterDetails";
import { disposeObject, fitDistance } from "../../src/lib/preview";
import { addDataLayers, CENTROID_SCALE, centroidRadius, SOURCES } from "../../src/map/dataLayers";
import { nearestCandidate } from "../../src/map/picking";
import { buildBaseStyle, PALETTES, themeLight, type Theme } from "../../src/map/style";

afterEach(() => cleanup());
const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

/** addDataLayers'ın eklediği katmanları toplayan sahte harita (ekleme sırası ve "before" konumu korunur). */
function collectDataLayers() {
  const layers: { spec: Record<string, unknown>; before?: string }[] = [];
  const sources: Record<string, unknown> = {};
  const fake = {
    getSource: (id: string) => sources[id],
    addSource: (id: string, s: unknown) => { sources[id] = s; },
    getLayer: (id: string) => (id === "building-unknown-height" ? {} : layers.find((l) => l.spec.id === id)),
    addLayer: (spec: Record<string, unknown>, before?: string) => { layers.push({ spec, before }); },
  };
  addDataLayers(fake as never);
  return { layers, sources };
}

describe("Faz 8B harita stili", () => {
  for (const theme of ["night", "day"] as Theme[]) {
    it(`${theme}: altlık + tüm veri katmanları MapLibre stil şemasından geçer (zoom ifadesi iç içe değil)`, () => {
      const base = buildBaseStyle(theme);
      const { layers } = collectDataLayers();
      const style = {
        ...base,
        sources: { ...base.sources, ...Object.fromEntries(SOURCES.map((s) => [s, { type: "geojson", data: { type: "FeatureCollection", features: [] } }])) },
        layers: [...base.layers, ...layers.map((l) => l.spec)],
      };
      const errors = validateStyleMin(style as never).map((e) => e.message);
      expect(errors).toEqual([]);
    });
  }

  it("hover ve seçim halkası katmanları süzgeçle tek kümeye sınırlı başlar (4.179 öğe için ek çizim yok)", () => {
    const { layers } = collectDataLayers();
    for (const id of ["centroid-hover", "centroid-selected"]) {
      const l = layers.find((x) => x.spec.id === id)!;
      expect(l.spec.filter).toEqual(["==", ["get", "cluster_id"], -1]);
      expect(l.before).toBe("building-unknown-height"); // veri katmanları bina extrüzyonlarının altında
    }
  });

  // WCAG göreli ışıklılık: zemin < yol < bina (gece) ve gündüz binaları zeminden belirgin koyu.
  const lum = (hex: string) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

  it("gece: zemin < ara yol < ana yol; bina tabanı ve tepesi zeminden ayrışır", () => {
    const p = PALETTES.night;
    expect(lum(p.background)).toBeLessThan(lum(p.road));
    expect(lum(p.road)).toBeLessThan(lum(p.roadMajor));
    expect(lum(p.roadMajor)).toBeLessThan(lum(p.roadMotorway));
    // Faz 8 gece binaları: taban #1A2740, tepe #2A3B5C — yeni tonlar zeminden en az onlar kadar ayrışmalı
    expect(contrast(p.buildingLow, p.background)).toBeGreaterThan(contrast("#1A2740", "#0B1120"));
    expect(contrast(p.buildingTop, p.background)).toBeGreaterThan(contrast("#2A3B5C", "#0B1120"));
    expect(lum(p.buildingLow)).toBeLessThan(lum(p.buildingTop)); // yükseklikle kontrollü açılma
  });

  it("gündüz: binalar zeminden en az Faz 8'deki kadar ayrışır (Faz 8: #CBD3DE / #E8EDF3)", () => {
    const p = PALETTES.day;
    const phase8 = contrast("#CBD3DE", "#E8EDF3");
    expect(contrast(p.buildingLow, p.background)).toBeGreaterThan(phase8 * 1.25);
    expect(contrast(p.building, p.background)).toBeGreaterThan(phase8);
  });

  it("tema zemin renkleri Faz 4 sözleşmesiyle aynı (viewer.spec gece/gündüz denetimi)", () => {
    expect(PALETTES.night.background).toBe("#0B1120");
    expect(PALETTES.day.background).toBe("#E8EDF3");
  });

  it("extrüzyon ışığı temaya göre tanımlı ve geçerli aralıkta", () => {
    for (const t of ["night", "day"] as Theme[]) {
      const l = themeLight(t);
      expect(l.intensity).toBeGreaterThan(0);
      expect(l.intensity).toBeLessThanOrEqual(1);
      expect((l.position as number[])[2]).toBeLessThanOrEqual(90);
    }
  });
});

describe("Faz 8B küme merkezi kodlaması", () => {
  it("yarıçap kayıt sayısı ve zoom ile monoton artar; uçlar ölçek tablosuyla aynı", () => {
    const [z0, lo0, hi0] = CENTROID_SCALE.radius[0];
    expect(centroidRadius(CENTROID_SCALE.sqrtMin ** 2, z0)).toBeCloseTo(lo0, 6);
    expect(centroidRadius(CENTROID_SCALE.sqrtMax ** 2, z0)).toBeCloseTo(hi0, 6);
    expect(centroidRadius(7, 13)).toBeCloseTo(centroidRadius(100, 13), 6); // aralık dışı: kıstırılır, büyütülmez
    for (const z of [9, 11.5, 13, 16]) {
      expect(centroidRadius(400, z)).toBeGreaterThan(centroidRadius(100, z));
      expect(centroidRadius(1444, z)).toBeGreaterThan(centroidRadius(400, z));
    }
    expect(centroidRadius(400, 15)).toBeGreaterThan(centroidRadius(400, 11));
  });

  it("lejant boyut ölçeği aynı sabitlerden üretilir ve boyutun kayıt sayısı olduğunu açıkça söyler", () => {
    wrap(<Legend viewport={{ state: "zoom-in", minZoom: 15 }} zoom={13} />);
    const el = screen.getByTestId("legend-size");
    for (const [n] of CENTROID_SCALE.colorStops) expect(el.textContent).toContain(n.toLocaleString("tr-TR"));
    expect(el.textContent).toContain("1.444+");
    expect(el.textContent).toMatch(/boyut ve renk kayıt sayısını/);
    expect(el.textContent).toMatch(/riskini değil/);
    const radii = [...el.querySelectorAll("circle")].map((c) => Number(c.getAttribute("r")));
    expect(radii).toEqual([...radii].sort((a, b) => a - b));
    expect(radii[0]).toBeCloseTo(centroidRadius(100, 13), 6);
  });

  it("birbirine 4 px yakın iki küme: tıklama hangisine yakınsa o seçilir (tek küme gibi davranılmaz)", () => {
    const a = { id: 10, screen: [100, 100] as [number, number] };
    const b = { id: 11, screen: [104, 100] as [number, number] };
    expect(nearestCandidate([101, 100], [a, b])).toBe(10);
    expect(nearestCandidate([103.5, 100], [a, b])).toBe(11);
    expect(nearestCandidate([102, 100], [b, a])).toBe(10); // eşitlikte küçük kimlik (deterministik)
  });
});

describe("Faz 8B GLB önizleyici yardımcıları", () => {
  it("fitDistance: sınırlayıcı küre görüş konisine sığar; dar tuvalde uzaklık artar", () => {
    const r = 2.5, fov = 32;
    const d = fitDistance(r, fov, 1.6, 1);
    expect(d * Math.sin((fov * Math.PI) / 360)).toBeCloseTo(r, 6);
    expect(fitDistance(r, fov, 0.6)).toBeGreaterThan(fitDistance(r, fov, 1.6));
    expect(fitDistance(r, fov, 1.6, 1.18)).toBeCloseTo(d * 1.18, 6);
  });

  it("disposeObject: paylaşılan kaynaklar bir kez, dokular dahil serbest bırakılır; nesne sahneden çıkar", () => {
    const tex = new THREE.Texture();
    const mat = new THREE.MeshStandardMaterial({ map: tex });
    const geo = new THREE.BoxGeometry(1, 1, 1);
    const spies = [vi.spyOn(tex, "dispose"), vi.spyOn(mat, "dispose"), vi.spyOn(geo, "dispose")];
    const scene = new THREE.Scene();
    const root = new THREE.Group();
    root.add(new THREE.Mesh(geo, mat), new THREE.Mesh(geo, mat));
    scene.add(root);
    expect(disposeObject(root)).toEqual({ geometries: 1, materials: 1, textures: 1 });
    for (const s of spies) expect(s).toHaveBeenCalledTimes(1);
    expect(scene.children).toHaveLength(0);
  });
});

describe("Faz 8B küme ayrıntı paneli", () => {
  const row = { cluster_id: 7, rank_by_events: 1, n_events: 120, n_unique_locations: 4, centroid_lon: -73.98, centroid_lat: 40.7, radius_p90_m: 12.5,
    injury_crashes: 30, fatal_crashes: 2, persons_injured: 41, persons_killed: 2, date_min: "2019-01-02", date_max: "2019-12-30",
    dominant_borough: "BROOKLYN", dominant_borough_share: 0.9, peak_hour: 17, experiment_id: "lab-x",
    hour_histogram: Array.from({ length: 24 }, (_, h) => (h === 17 ? 20 : 4)), vehicles: [{ value: "SEDAN", count: 90, share: 0.75 }, { value: "SUV", count: 60, share: 0.5 }],
    top_factors: [{ value: "Driver Inattention/Distraction", crashes: 30, share: 0.25 }], factor_unspecified_share: 0.4, midnight_suspect: 1,
    boroughs: [{ value: "BROOKLYN", count: 108 }], years: [{ year: 2019, count: 120 }] };
  const state = { status: "ready", selection: { kind: "result", resultId: "lab-x", row, meta: { request: { algorithm: "dbscan", params: { eps_m: 30, min_samples: 5 } } } } } as const;

  it("üst bölüm: küme no, toplam, ilçe, yaralanmalı, ölümlü; gruplar mantıklı sırada; model bilgisi kapalı ama DOM'da", () => {
    wrap(<ClusterDetails roadNote="not" onClose={() => {}} onFocus={() => {}} state={state as never} />);
    const keys = screen.getByTestId("cluster-keystats").textContent!;
    for (const t of ["Toplam kaza", "120", "Brooklyn", "Yaralanmalı kaza", "30", "Ölümle sonuçlanan kaza", "2"]) expect(keys).toContain(t);
    expect(screen.getByTestId("cluster-title").textContent).toContain("Küme #7");
    const groups = [...document.querySelectorAll("details[data-testid^='group-']")].map((d) => d.getAttribute("data-testid"));
    expect(groups).toEqual(["group-location", "group-time", "group-vehicles", "group-factors", "group-model"]);
    expect((screen.getByTestId("group-model") as HTMLDetailsElement).open).toBe(false);
    expect((screen.getByTestId("group-location") as HTMLDetailsElement).open).toBe(true);
    expect(screen.getByTestId("cluster-experiment").textContent).toBe("lab-x");
    expect(screen.getByRole("button", { name: /Odakla/ })).toBeTruthy();
    expect(screen.getByTestId("sim-note").textContent).toBe("not");
  });

  it("araç oranlarının toplamı %100'ü aşabilir açıklaması korunur; oranlar sunucu değerleri (uydurma yok)", () => {
    wrap(<ClusterDetails roadNote={null} onClose={() => {}} onFocus={() => {}} state={state as never} />);
    const g = screen.getByTestId("group-vehicles").textContent!;
    expect(g).toMatch(/birden çok kategoride sayılabilir/);
    expect(g).toMatch(/%100'ü aşabilir/);
    expect(g).toContain("%75");
    expect(g).toContain("%50");
  });
});

describe("Faz 8B varlık inceleyici", () => {
  const registry = { version: 1, models: [{ id: "sedan", name_tr: "Sedan", real_size_m: 4.6, measure: "length", author: "Kenney (www.kenney.nl)", license: "CC0 1.0 Universal (Kamu malı adanması)",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/", attribution: "Kenney", source: { pack: "Car Kit", source_url: "https://kenney.nl", original_bytes: 1000 },
    optimized: { bytes: 500, triangles: 100, textures: [] }, lod1: null, file: "models/sedan.glb", scale: 1, ground_offset: 0 }] } as never;

  it("model seçimi yerleştirir (Faz 4/8 sözleşmesi) ve önizleyiciyi adı + kısa lisansla açar; kaldırınca 'Haritaya yerleştir' görünür", () => {
    const onChange = vi.fn();
    const { rerender } = wrap(<AssetInspector registry={registry} placement={null} onChange={onChange} onClose={() => {}} onPlaceHere={() => {}} error={null} mapCenter={[-73.9, 40.7]} />);
    fireEvent.click(screen.getByText("Sedan", { selector: "button" }));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ modelId: "sedan", lngLat: [-73.9, 40.7] }));
    expect(screen.getByTestId("glb-preview").getAttribute("data-model")).toBe("sedan");
    expect(screen.getByTestId("preview-title").textContent).toBe("Sedan");
    expect(screen.getByTestId("preview-license-short").textContent).toContain("CC0 1.0 Universal");
    expect(screen.getByTestId("preview-license-short").textContent).toContain("Kenney");
    // yerleşim kaldırıldıktan sonra önizleme açık kalır
    rerender(<TooltipProvider><AssetInspector registry={registry} placement={null} onChange={onChange} onClose={() => {}} onPlaceHere={() => {}} error={null} mapCenter={[-73.8, 40.6]} /></TooltipProvider>);
    expect(screen.getByTestId("placement-status").getAttribute("data-placed")).toBe("false");
    expect(screen.queryByTestId("remove-model")).toBeNull();
    fireEvent.click(screen.getByTestId("place-model"));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ modelId: "sedan", lngLat: [-73.8, 40.6] }));
  });

  it("WebGL yoksa önizleyici hata durumunu açıkça gösterir (sessiz boş tuval değil)", () => {
    wrap(<AssetInspector registry={registry} placement={{ modelId: "sedan", lngLat: [-73.9, 40.7], altitudeM: 0, headingDeg: 0, scale: 1 }}
      onChange={() => {}} onClose={() => {}} onPlaceHere={() => {}} error={null} mapCenter={[-73.9, 40.7]} />);
    expect(screen.getByTestId("glb-preview").getAttribute("data-state")).toBe("error");
    expect(screen.getByRole("alert").textContent).toMatch(/WebGL önizlemesi başlatılamadı/);
  });
});
