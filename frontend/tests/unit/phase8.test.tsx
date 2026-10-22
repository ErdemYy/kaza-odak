// @vitest-environment jsdom
// Faz 8: yeni logo (bileşen + SVG varlıklarının güvenliği), 3D varlık inceleyicide modeli kaldırma, 3D Keşif'te boş
// filtre sonucu durumu ve mobilde animasyon düzeyi seçicisi.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef, useEffect, type ReactNode } from "react";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";

// Harita motoru jsdom'da çalışmaz: CityMap, gerçek bileşenin ExplorerPage'e bildirdiği durumları üreten bir taklitle değiştirilir.
const mapState = vi.hoisted(() => ({ clusters: 0 }));
vi.mock("../../src/features/explorer/CityMap", () => ({
  CityMap: forwardRef(function FakeMap(props: { filterQuery: string; onLoad: (s: unknown) => void; onLayerCounts: (c: unknown) => void }, _ref) {
    useEffect(() => {
      props.onLayerCounts({ clusters: props.filterQuery ? mapState.clusters : 4179, total: 4179, label: "" });
      props.onLoad({ phase: "ready", message: "hazır" });
    }, [props.filterQuery]); // eslint-disable-line react-hooks/exhaustive-deps
    return <div data-testid="map" />;
  }),
}));

import { AssetInspector } from "../../src/components/AssetInspector";
import { LogoMark, Wordmark } from "../../src/components/brand/Logo";
import { Brand } from "../../src/components/layout/Navigation";
import { useApp } from "../../src/app/store";
import { EMPTY_FILTERS } from "../../src/lib/filters";
import { ExplorerPage } from "../../src/features/explorer/ExplorerPage";

let mobile = false;
beforeAll(() => {
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  window.matchMedia = ((q: string) => ({ matches: q.includes("max-width: 1023px") ? mobile : false, media: q, addEventListener() {}, removeEventListener() {},
    onchange: null, addListener() {}, removeListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); mobile = false; useApp.setState({ applied: EMPTY_FILTERS, draft: EMPTY_FILTERS, mobileSheet: null, motion: "full", slice: null }); });

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

describe("Faz 8 logo", () => {
  it("simge: başlıkla görüntü rolü, başlıksız dekoratif; ızgara yalnızca > 32 px", () => {
    const { container, rerender } = render(<LogoMark size={48} title="Kaza Odak" />);
    expect(screen.getByRole("img", { name: "Kaza Odak" })).toBeTruthy();
    expect(container.querySelectorAll("path").length).toBe(2); // ızgara + rota
    rerender(<LogoMark size={28} />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelectorAll("path").length).toBe(1); // yalnızca rota
  });

  it("wordmark düz metin 'Kaza Odak' (rolsüz öğede aria-label yok); daraltılmış marka adlı görüntü", () => {
    render(<><Wordmark /><Brand /></>);
    expect(screen.getAllByTestId("brand-wordmark").map((e) => e.textContent)).toEqual(["Kaza Odak", "Kaza Odak"]);
    expect(screen.getAllByTestId("brand-wordmark").every((e) => !e.hasAttribute("aria-label"))).toBe(true);
    cleanup();
    render(<Brand compact />);
    expect(screen.getByRole("img", { name: "Kaza Odak" })).toBeTruthy();
    expect(screen.queryByTestId("brand-subtitle")).toBeNull();
  });

  it("marka SVG dosyaları güvenli: betik, dış kaynak, foreignObject, olay özniteliği ve <text> yok; erişilebilir başlık var", () => {
    const dirs = [resolve(__dirname, "../../../assets/brand"), resolve(__dirname, "../../public/brand"), resolve(__dirname, "../../public")];
    const files = dirs.flatMap((d) => readdirSync(d).filter((f) => f.endsWith(".svg")).map((f) => resolve(d, f)));
    expect(files.length).toBeGreaterThanOrEqual(10);
    for (const f of files) {
      const s = readFileSync(f, "utf-8");
      expect(s, f).not.toMatch(/<script|<foreignObject|<image|<text|\son[a-z]+=|xlink:href|\shref=|@import|url\(/i);
      expect(s, f).toMatch(/<title>[^<]+<\/title>/);
      expect(s, f).toMatch(/viewBox="0 0 /);
      expect(s.length, f).toBeLessThan(16_000);
    }
  });

  it("favikon index.html'de bağlı", () => {
    const html = readFileSync(resolve(__dirname, "../../index.html"), "utf-8");
    expect(html).toContain('href="/favicon.svg"');
    expect(html).toContain('rel="apple-touch-icon"');
  });
});

describe("Faz 8 3D varlık inceleyici", () => {
  const registry = { version: 1, models: [{ id: "sedan", name_tr: "Sedan", real_size_m: 4.6, measure: "length", author: "Kenney", license: "CC0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/", attribution: "Kenney", source: { pack: "Car Kit", source_url: "https://kenney.nl", original_bytes: 1000 },
    optimized: { bytes: 500, triangles: 100, textures: [] }, lod1: null }] } as never;

  it("'Modeli kaldır' yerleşimi null yapar; ipucu metni paneli kapatmanın modeli bıraktığını söyler", () => {
    const onChange = vi.fn();
    render(<AssetInspector registry={registry} placement={{ modelId: "sedan", lngLat: [-73.9, 40.7], altitudeM: 0, headingDeg: 0, scale: 1 }}
      onChange={onChange} onClose={() => {}} onPlaceHere={() => {}} error={null} mapCenter={[-73.9, 40.7]} />);
    expect(screen.getByText(/Paneli kapatmak yerleştirilen modeli haritada bırakır/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("remove-model"));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("yerleşim yokken 'Modeli kaldır' görünmez", () => {
    render(<AssetInspector registry={registry} placement={null} onChange={() => {}} onClose={() => {}} onPlaceHere={() => {}} error={null} mapCenter={[-73.9, 40.7]} />);
    expect(screen.queryByTestId("remove-model")).toBeNull();
  });
});

describe("Faz 8 3D Keşif boş filtre sonucu ve mobil animasyon seçicisi", () => {
  function stubApi(nEvents: number) {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (u: string) => {
      calls.push(String(u));
      if (String(u).startsWith("/api/records/summary")) return json({ n_events: nEvents, share_of_total: 0, denominator: "x", filters_tr: [] });
      if (String(u).includes("/timeline")) return json({ granularity: "year", buckets: [], n_events: 0 });
      return json({});
    }));
    return calls;
  }

  it("filtre 0 kayıt döndürürse harita üzerinde açık boş durum ve sıfırlama düğmesi gösterilir", async () => {
    const calls = stubApi(0);
    mapState.clusters = 0;
    useApp.setState({ applied: { ...EMPTY_FILTERS, fatal: "fatal", dateFrom: "2019-02-03", dateTo: "2019-02-03" } });
    wrap(<ExplorerPage active />);
    const box = await screen.findByTestId("empty-filter-result");
    await waitFor(() => expect(box.textContent).toContain("uyan kaza kaydı bulunmuyor"));
    expect(box.textContent).toContain("Küme etiketleri değiştirilmedi");
    expect(calls.some((c) => c.startsWith("/api/records/summary?") && c.includes("fatal=fatal"))).toBe(true);
    act(() => { fireEvent.click(screen.getByTestId("empty-reset")); });
    expect(useApp.getState().applied).toEqual(EMPTY_FILTERS);
    await waitFor(() => expect(screen.queryByTestId("empty-filter-result")).toBeNull());
  });

  it("kayıt var ama kümeye düşmüyorsa 'tümü gürültü' açıklaması yapılır", async () => {
    stubApi(12);
    mapState.clusters = 0;
    useApp.setState({ applied: { ...EMPTY_FILTERS, boroughs: ["STATEN ISLAND"] } });
    wrap(<ExplorerPage active />);
    const box = await screen.findByTestId("empty-filter-result");
    await waitFor(() => expect(box.textContent).toContain("12 kayıt var"));
    expect(box.textContent).toContain("tümü gürültü");
  });

  it("filtresiz modelde boş durum gösterilmez", async () => {
    stubApi(0);
    wrap(<ExplorerPage active />);
    await screen.findByTestId("map");
    expect(screen.queryByTestId("empty-filter-result")).toBeNull();
  });

  it("mobilde katman çekmecesinde animasyon düzeyi seçilebilir", async () => {
    stubApi(0);
    mobile = true;
    useApp.setState({ mobileSheet: "panel" });
    wrap(<ExplorerPage active />);
    const sel = await screen.findByTestId("mobile-motion-select");
    fireEvent.change(sel, { target: { value: "off" } });
    expect(useApp.getState().motion).toBe("off");
    expect(document.documentElement.dataset.motion).toBe("off");
  });
});

describe("Faz 8 laboratuvar algoritma geçişi", () => {
  it("HDBSCAN'in zorladığı örneklem DBSCAN'e dönünce kapanır; kayıtlı konfigürasyon yeniden eşleşir", async () => {
    const { AlgorithmControls } = await import("../../src/features/lab/AlgorithmControls");
    const { defaultForm, validateForm } = await import("../../src/features/lab/labForm");
    const cap = {
      feature_sets: { spatial_haversine: { label: "H", kind: "spatial", metric: "Haversine", level: "konum", features: ["lat", "lon"], phase2_set: "A", note: "" },
        spatial_projected: { label: "P", kind: "spatial", metric: "Öklid", level: "kayıt", features: ["x", "y"], phase2_set: "B", note: "" } },
      compatibility: { dbscan: { allowed: ["spatial_haversine"], reasons: {} }, kmeans: { allowed: ["spatial_projected"], reasons: {} }, hdbscan: { allowed: ["spatial_projected"], reasons: {} } },
      bounds: { dbscan: { eps_m: [5, 500], min_samples: [2, 5000] }, kmeans: { k: [2, 200], n_init: [1, 50], max_iter: [10, 2000], random_state: [0, 1e9] },
        hdbscan: { min_cluster_size: [5, 5000], min_samples: [1, 5000] } },
      budget: { max_hdbscan_events: 150000, max_st_events: 300000 }, software: {}, code_version: "x",
    } as never;
    let form = defaultForm();
    const setForm = (f: typeof form) => { form = f; };
    const ui = () => <AlgorithmControls form={form} setForm={setForm} cap={cap} validation={validateForm(form, cap)} scope={undefined} filtersTr={[]} filtersEmpty
      experiments={[]} onEditFilters={() => {}} onSubmit={() => {}} submitting={false} submitError={null} />;
    const { rerender } = wrap(ui());
    fireEvent.click(screen.getByTestId("lab-algo-hdbscan"));
    expect(form.useSample).toBe(true);
    expect(form.sampleN).toBe("100000");
    rerender(<TooltipProvider>{ui()}</TooltipProvider>);
    fireEvent.click(screen.getByTestId("lab-algo-dbscan"));
    expect(form.algorithm).toBe("dbscan");
    expect(form.useSample).toBe(false);
    expect(form.sampleN).toBe(defaultForm().sampleN);
  });
});
