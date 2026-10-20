// @vitest-environment jsdom
// Faz 5 bileşen testleri (jsdom): veri doğruluğu kuralları, hata/boş durumları, erişilebilir adlar.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";

beforeAll(() => {
  // jsdom'da olmayan tarayıcı API'leri (Radix, Recharts)
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, onchange: null,
    addListener() {}, removeListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("MetricCard ve StateBadge", () => {
  it("eksik değer sahte sayı yerine — gösterir", async () => {
    const { MetricCard } = await import("../../src/components/common");
    wrap(<MetricCard label="DBCV" value={null} testId="m" />);
    expect(screen.getByTestId("m").textContent).toContain("—");
  });
  it("iş durumları Türkçe etiketlenir", async () => {
    const { StateBadge } = await import("../../src/features/lab/ExperimentResults");
    wrap(<><StateBadge state="rejected_resource" /><StateBadge state="cancelled" /></>);
    expect(screen.getByText("Kaynak yetersiz")).toBeTruthy();
    expect(screen.getByText("İptal edildi")).toBeTruthy();
  });
});

const COMPARISON = {
  dataset_version: "dv", processing_version: "pv", software: { "scikit-learn": "1.9.1", hdbscan: "0.8.44" },
  eval_set: { n_events: 100000, seed: 42, definition: "basit rastgele olay örneklemi" },
  selection_criteria: { max_largest_cluster_share: 0.05, min_clusters: 20, ranking: [], kmeans_rule: "", hdbscan_rule: "" },
  kmeans_elbow_k: 20, grids: { dbscan: [], kmeans: [], hdbscan: [] }, selection_review: null, sensitivity: null, final_choice: null,
  temporal: { years: [], refit_rule: null, note: null, persistence: null }, caveats: ["HDBSCAN örneklemde."], label_semantics: "-1 = gürültü", eps_conversion: "",
  rows: [
    { algorithm: "dbscan", experiment_id: "dbscan-a", parameters: { eps_m: 25, min_samples: 100 }, features: "A", fit_scope: "tam veri",
      fit_n_events: 2020638, fit_n_points: 349122, scope_class: "full_weighted", n_clusters: 4179, n_clusters_scope: "tam veri", noise_ratio: 0.5969,
      noise_applicable: true, noise_scope: "tam veri", largest_cluster_share: 0.0007, silhouette: 0.945052, silhouette_detail: null, silhouette_haversine: null,
      davies_bouldin: 0.09, davies_bouldin_detail: null, dbcv: 0.394, dbcv_detail: null, parameter_stability_ari: 0.48, runtime_s: 3.87,
      peak_memory_mb: 962, fit_memory_mb: 138, admissible: true, rejection_reasons: [], primary: true },
    { algorithm: "kmeans", experiment_id: "kmeans-b", parameters: { k: 5 }, features: "B", fit_scope: "tam veri", fit_n_events: 2020638,
      fit_n_points: 349122, scope_class: "full_weighted", n_clusters: 5, n_clusters_scope: "tam veri", noise_ratio: null, noise_applicable: false,
      noise_scope: null, largest_cluster_share: 0.28, silhouette: 0.458, silhouette_detail: null, silhouette_haversine: null, davies_bouldin: 0.69,
      davies_bouldin_detail: null, dbcv: -0.85, dbcv_detail: null, parameter_stability_ari: null, runtime_s: 0.8, peak_memory_mb: 965, fit_memory_mb: 139,
      admissible: false, rejection_reasons: ["küme sayısı 5 < 20"], primary: false },
    { algorithm: "hdbscan", experiment_id: "hdbscan-c", parameters: { min_cluster_size: 25, min_samples: 25 }, features: "B", fit_scope: "örneklem (100k olay)",
      fit_n_events: 100000, fit_n_points: 56969, scope_class: "sample", n_clusters: 768, n_clusters_scope: "örneklem (100k olay)", noise_ratio: 0.547,
      noise_applicable: true, noise_scope: "örneklem (100k olay)", largest_cluster_share: 0.0085, silhouette: 0.6, silhouette_detail: null,
      silhouette_haversine: null, davies_bouldin: 0.48, davies_bouldin_detail: null, dbcv: 0.26, dbcv_detail: null, parameter_stability_ari: null,
      runtime_s: 68.9, peak_memory_mb: 965, fit_memory_mb: 180, admissible: true, rejection_reasons: [], primary: false },
  ],
};

describe("Model karşılaştırma", () => {
  it("K-Means gürültüsü 0 değil 'Uygulanamaz'; siluet yüzde doğruluk olarak yazılmaz; örneklem kapsamı rozetli", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(COMPARISON)));
    const { default: ModelsPage } = await import("../../src/features/models/ModelsPage");
    wrap(<ModelsPage />);
    await screen.findByTestId("comparison-table");
    expect(screen.getByTestId("cmp-noise-kmeans").textContent).toBe("Uygulanamaz");
    expect(screen.getByTestId("cmp-noise-dbscan").textContent).toContain("%59,7");
    const sil = screen.getByTestId("cmp-silhouette-dbscan").textContent!;
    expect(sil).toContain("0,945");
    expect(sil).not.toContain("%");
    expect(screen.getByTestId("cmp-clusters-hdbscan").textContent).toContain("örneklem (100k olay)");
    expect(within(screen.getByTestId("comparison-table")).getAllByText("Örneklem").length).toBe(1);
    expect(screen.getByTestId("comparison-caveats").textContent).toContain("HDBSCAN örneklemde.");
  });
});

describe("Hata ve yüklenme durumları", () => {
  it("API hatası kullanıcıya anlaşılır mesaj ve yeniden deneme olarak gösterilir", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async () => { calls++; return json({ detail: "Olay deposu hâlâ yükleniyor" }, 503); }));
    const { default: OverviewPage } = await import("../../src/features/overview/OverviewPage");
    wrap(<OverviewPage />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Olay deposu hâlâ yükleniyor");
    const before = calls;
    fireEvent.click(within(alert).getByRole("button", { name: /Yeniden dene/ }));
    await waitFor(() => expect(calls).toBeGreaterThan(before));
  });
  it("ağ hatası 'sunucuya ulaşılamadı' olarak çevrilir", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const { default: DataPage } = await import("../../src/features/data/DataPage");
    wrap(<DataPage />);
    expect((await screen.findByRole("alert")).textContent).toMatch(/ulaşılamadı/);
  });
});

describe("Küme ayrıntısı", () => {
  it("dinamik sonuç kümesi: gerçek profil, ilgili ilçeler, sonuç kimliği; eşleştirilemezlik notu", async () => {
    const { ClusterDetails } = await import("../../src/features/explorer/ClusterDetails");
    const row = { cluster_id: 7, rank_by_events: 1, n_events: 120, n_unique_locations: 4, centroid_lon: -73.98, centroid_lat: 40.7, radius_p90_m: 12.5,
      injury_crashes: 30, fatal_crashes: 0, persons_injured: 41, persons_killed: 0, date_min: "2019-01-02", date_max: "2019-12-30",
      dominant_borough: "BROOKLYN", dominant_borough_share: 0.9, peak_hour: 17, experiment_id: "lab-x",
      hour_histogram: Array.from({ length: 24 }, (_, h) => (h === 17 ? 20 : 4)), vehicles: [{ value: "BICYCLE", count: 120, share: 1 }],
      top_factors: [{ value: "Driver Inattention/Distraction", crashes: 30, share: 0.25 }], factor_unspecified_share: 0.4, midnight_suspect: 1,
      boroughs: [{ value: "BROOKLYN", count: 108 }, { value: "MANHATTAN", count: 12 }], years: [{ year: 2019, count: 120 }] };
    wrap(<ClusterDetails roadNote={null} onClose={() => {}} onFocus={() => {}}
      state={{ status: "ready", selection: { kind: "result", resultId: "lab-x", row, meta: { request: { algorithm: "dbscan", params: { eps_m: 30, min_samples: 5 } } } } }} />);
    expect(screen.getByTestId("cluster-title").textContent).toContain("Küme #7");
    expect(screen.getByTestId("cluster-events").textContent).toBe("120");
    expect(screen.getByTestId("cluster-experiment").textContent).toBe("lab-x");
    expect(screen.getByText(/Brooklyn \(108\), Manhattan \(12\)/)).toBeTruthy();
    expect(screen.getByText(/eps_m = 30 · min_samples = 5/)).toBeTruthy();
    expect(screen.getByText(/eşleştirilemez/)).toBeTruthy();
    expect(screen.getByRole("img", { name: /Zirve 17:00/ })).toBeTruthy();
  });
  it("seçim yokken yönlendirme metni; hata durumunda alert", async () => {
    const { ClusterDetails } = await import("../../src/features/explorer/ClusterDetails");
    const { rerender } = wrap(<ClusterDetails state={{ status: "idle" }} roadNote={null} onClose={() => {}} onFocus={() => {}} />);
    expect(screen.getByTestId("cluster-hint")).toBeTruthy();
    rerender(<TooltipProvider><ClusterDetails state={{ status: "error", clusterId: 3, message: "409" }} roadNote={null} onClose={() => {}} onFocus={() => {}} /></TooltipProvider>);
    expect(screen.getByRole("alert").textContent).toContain("Küme #3 yüklenemedi");
    expect(screen.getByRole("button", { name: "Seçimi kapat" })).toBeTruthy();
  });
});

describe("Zaman oynatma ve katman kontrolü", () => {
  it("sonuç modunda oynatma gerekçesiyle kapalıdır (sahte zaman verisi yok)", async () => {
    const f = vi.fn();
    vi.stubGlobal("fetch", f);
    const { TimeControls } = await import("../../src/features/explorer/TimeControls");
    wrap(<TimeControls disabledReason="Gösterilen sonuç sabit bir kapsama ait." />);
    expect(screen.getByTestId("time-controls").dataset.state).toBe("disabled");
    expect(f).not.toHaveBeenCalled();
  });
  it("zaman kovaları sunucudan gelir; adım ilerletme seçilen dilimi gösterir", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ granularity: "year", n_events: 30, buckets: [{ key: "2019", count: 10 }, { key: "2020", count: 20 }] })));
    const { TimeControls } = await import("../../src/features/explorer/TimeControls");
    const { useApp } = await import("../../src/app/store");
    useApp.getState().setGranularity("year");
    wrap(<TimeControls disabledReason={null} />);
    await screen.findByText(/30 kayıt/);
    fireEvent.click(screen.getByRole("button", { name: "Sonraki adım" }));
    await waitFor(() => expect(screen.getByTestId("time-readout").textContent).toContain("2019"));
    expect(useApp.getState().slice).toEqual({ granularity: "year", key: "2019" });
    expect(screen.getByRole("slider", { name: "Zaman dilimi" })).toBeTruthy();
    useApp.getState().setSlice(null);
  });
  it("katman anahtarları erişilebilir adlarla açılıp kapanır", async () => {
    const { ViewPanel } = await import("../../src/features/explorer/ViewPanel");
    const { useApp } = await import("../../src/app/store");
    wrap(<ViewPanel meta={null} onBorough={() => {}} zoom={16} layerCounts={null} />);
    const sw = screen.getByRole("switch", { name: "Gürültü noktaları" });
    expect(sw.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(sw);
    expect(useApp.getState().visibility.noise).toBe(true);
    expect(screen.getByRole("switch", { name: "Gürültü noktaları" }).getAttribute("aria-checked")).toBe("true");
    useApp.getState().toggleLayer("noise");
  });
});
