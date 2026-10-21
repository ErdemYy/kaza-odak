// @vitest-environment jsdom
// Faz 6: kalıcı iş durumları (yarıda kaldı / kaynak sınırı), açık yeniden deneme, bağlantı kaybında otomatik yeniden
// deneme, dinamik sonuçta eksik metriklerin N/A gösterimi, sonuç modunda zaman oynatmanın yalnızca zaman süzgeci
// kullanması ve deney kapsamının gösterilmesi.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { EMPTY_FILTERS, applySlice, toQuery } from "../../src/lib/filters";

beforeAll(() => {
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, onchange: null,
    addListener() {}, removeListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const SUMMARY = { n_events: 1000, n_clusters: 3, noise_events: 100, noise_ratio: 0.1, noise_applicable: true, clustered_events: 900,
  largest_cluster_share: 0.5, cluster_size: { min: 100, p25: 200, median: 300, p75: 400, p90: 450, max: 500 }, size_histogram: [] };

function job(over: Record<string, unknown>) {
  return {
    job_id: "aaaaaaaaaaaa", experiment_id: "dyn-0123456789abcdef", cache_key: "0123456789abcdef", state: "completed", stage: null,
    request: { algorithm: "dbscan", feature_set: "spatial_haversine", params: { eps_m: 40, min_samples: 6 }, filters: {}, sample: null },
    filters_tr: [], feature_set: { label: "Mekânsal", metric: "Haversine", level: "konum", kind: "spatial", features: [], phase2_set: "A", note: "" },
    created_at: 0, started_at: 0, finished_at: 1, elapsed_s: 1, error: null, error_kind: null, retryable: false, retry_of: null,
    recovered: false, output_sha256: "x", source: "dynamic", phase3_experiment: null, n_events: 1000, n_fit_rows: 500,
    worker: { status: "completed", runtime_s: 0.5, peak_memory_mb: 300,
      monitor: { samples: 4, peak_rss_mb: 290, mean_cpu_percent: 95, max_cpu_percent: 100, cpu_time_s: 1.2, peak_commit_mb: 480,
        available_memory_mb_at_start: 3000, exit_code: 0, guard: { job_object: true, kill_on_close: true, memory_limit_mb: 2232, error: null } } },
    result: { summary: SUMMARY, metrics: { silhouette: 0.8, davies_bouldin: null, status: "ok", sampling: "örneklem", n_used: 900, metric: "Öklid" } },
    code_version: "phase5-lab:5.0.0", ...over,
  };
}

describe("Faz 6 laboratuvar iş görünümü", () => {
  it("yarıda kalan iş açıklanır ve yeniden deneme YENİ iş başlatır (otomatik değil)", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.includes("/table")) return json({ total: 0, rows: [] });
      if (url.endsWith("/retry")) return json(job({ job_id: "bbbbbbbbbbbb", state: "queued", retry_of: "aaaaaaaaaaaa", result: null }), 202);
      if (url.includes("bbbbbbbbbbbb")) return json(job({ job_id: "bbbbbbbbbbbb", retry_of: "aaaaaaaaaaaa" }));
      return json(job({ state: "interrupted", retryable: true, result: null, error: "Sunucu bu iş çalışırken kapandı; sonuç uydurulmadı." }));
    }));
    const { JobView } = await import("../../src/features/lab/ExperimentResults");
    const { useApp } = await import("../../src/app/store");
    useApp.getState().setActiveJob("aaaaaaaaaaaa");
    const View = () => <JobView jobId={useApp((s) => s.activeJobId)!} />;
    wrap(<View />);
    expect((await screen.findByTestId("job-state")).getAttribute("data-state")).toBe("interrupted");
    expect(screen.getByTestId("job-interrupted").textContent).toContain("uydurulmadı");
    expect(calls.filter((c) => c.startsWith("POST"))).toHaveLength(0); // kendiliğinden yeniden çalıştırma yok
    fireEvent.click(screen.getByTestId("job-retry"));
    await waitFor(() => expect(useApp.getState().activeJobId).toBe("bbbbbbbbbbbb"));
    expect(calls).toContain("POST /api/lab/jobs/aaaaaaaaaaaa/retry");
    expect((await screen.findByTestId("job-ids")).textContent).toContain("aaaaaaaaaaaa işinin yeniden denemesi");
  });

  it("kaynak sınırı açıkça bildirilir ve sonuç üretilmediği yazılır", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(job({ state: "resource_limited", retryable: true, result: null,
      error: "Bellek yetersiz: kullanılabilir fiziksel bellek 900 MB < gereken 1.500 MB." }))));
    const { JobView } = await import("../../src/features/lab/ExperimentResults");
    wrap(<JobView jobId="cccccccccccc" />);
    const note = await screen.findByTestId("job-rejected");
    expect(note.textContent).toContain("Bellek yetersiz");
    expect(note.textContent).toContain("Sonuç üretilmedi");
    expect(screen.getByText("Kaynak sınırı")).toBeTruthy();
  });

  it("dinamik sonuçta hesaplanmayan metrikler N/A gösterilir (0 veya uydurma değer değil)", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/table") ? json({ total: 0, rows: [] }) : json(job({})))));
    const { JobView } = await import("../../src/features/lab/ExperimentResults");
    wrap(<JobView jobId="dddddddddddd" />);
    const dbcv = await screen.findByTestId("result-dbcv");
    expect(dbcv.textContent).toContain("N/A");
    expect(screen.getByTestId("result-silhouette").textContent).toContain("0,800");
    expect(screen.getAllByTestId("metric-na").length).toBeGreaterThanOrEqual(2); // Davies–Bouldin null + DBCV
    expect(screen.getByTestId("job-monitor").textContent).toMatch(/tepe commit 480 MB/);
    expect(screen.getByTestId("job-ids").textContent).toContain("dyn-0123456789abcdef");
  });

  it("bağlantı koparsa iş durumu otomatik yeniden denenir ve dönünce görünür", async () => {
    let n = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/table")) return json({ total: 0, rows: [] });
      n += 1;
      if (n <= 2) throw new TypeError("Failed to fetch");
      return json(job({}));
    }));
    const { JobView } = await import("../../src/features/lab/ExperimentResults");
    wrap(<JobView jobId="eeeeeeeeeeee" />);
    expect((await screen.findByTestId("job-reconnecting")).textContent).toContain("yeniden deneniyor");
    expect((await screen.findByTestId("job-state", {}, { timeout: 6000 })).getAttribute("data-state")).toBe("completed");
    expect(screen.queryByTestId("job-reconnecting")).toBeNull();
  });
});

describe("Faz 6 zaman oynatma (sonuç modu)", () => {
  it("sonuç modunda sorgu yalnızca zaman süzgeci içerir (kayıt filtreleri karışmaz)", () => {
    const applied = { ...EMPTY_FILTERS, boroughs: ["BROOKLYN"], vehicles: ["BICYCLE"] };
    const q = toQuery(applySlice(EMPTY_FILTERS, { granularity: "month", key: "2019-03" }));
    expect(q).toBe("years=2019&months=3");
    expect(toQuery(applySlice(applied, { granularity: "hour", key: "07" }))).toContain("boroughs=BROOKLYN");
    expect(toQuery(applySlice(EMPTY_FILTERS, { granularity: "hour", key: "07" }))).toBe("hour_from=7&hour_to=7");
  });

  it("deney kapsamı, görünür olay sayısı ve 'yeniden kümeleme yok' bilgisi gösterilir", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url);
      return json({ granularity: "year", n_events: 100000, result_id: "hdbscan-ba3a1ff58d", reclustered: false,
        coverage: { n_events: 100000, date_min: "2012-07-01", date_max: "2026-06-11" },
        buckets: [{ key: "2012", count: 4000 }, { key: "2013", count: 9000 }] });
    }));
    const { TimeControls } = await import("../../src/features/explorer/TimeControls");
    wrap(<TimeControls disabledReason={null} resultId="hdbscan-ba3a1ff58d" />);
    expect((await screen.findByTestId("time-coverage")).textContent).toContain("2012-07-01 → 2026-06-11");
    expect(screen.getByTestId("time-recluster").textContent).toContain("Hayır");
    expect(urls[0]).toBe("/api/results/hdbscan-ba3a1ff58d/timeline?granularity=year");
    expect(screen.getByTestId("time-readout").textContent).toContain("100.000 görünür olay");
  });
});
