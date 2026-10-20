// Faz 5 saf mantık testleri: filtreler, zaman dilimi, laboratuvar formu, yönlendirme, önbellek.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  activeCount, applySlice, describe as describeFilters, EMPTY_FILTERS, hourRangeLabel, isEmpty, sliceLabel, toQuery, validate,
} from "../../src/lib/filters";
import { budgetWarnings, defaultForm, registryMatch, validateForm, type LabForm } from "../../src/features/lab/labForm";
import type { Experiment, LabCapabilities } from "../../src/lib/types";

const labels = { borough: (b: string) => b, vehicle: (v: string) => v };

describe("filtreler", () => {
  it("boş filtre sorgu üretmez; aynı filtre aynı kanonik sorguyu üretir", () => {
    expect(toQuery(EMPTY_FILTERS)).toBe("");
    expect(isEmpty(EMPTY_FILTERS)).toBe(true);
    const a = toQuery({ ...EMPTY_FILTERS, years: [2020, 2019, 2020], boroughs: ["QUEENS", "BRONX"] });
    const b = toQuery({ ...EMPTY_FILTERS, years: [2019, 2020], boroughs: ["BRONX", "QUEENS"] });
    expect(a).toBe(b);
    expect(a).toBe("boroughs=BRONX%2CQUEENS&years=2019%2C2020");
  });
  it("yarım saat aralığı ve ters tarih reddedilir", () => {
    expect(validate({ ...EMPTY_FILTERS, hourFrom: 7 })).toContain("Saat aralığının iki ucu da seçilmeli.");
    expect(validate({ ...EMPTY_FILTERS, dateFrom: "2020-02-01", dateTo: "2020-01-01" })[0]).toMatch(/sonra/);
    expect(validate({ ...EMPTY_FILTERS, hourFrom: 22, hourTo: 4 })).toEqual([]);
  });
  it("saat aralığı yalnızca iki uç varsa sorguya girer; gece yarısını aşan aralık etiketlenir", () => {
    expect(toQuery({ ...EMPTY_FILTERS, hourFrom: 5, hourTo: null })).toBe("");
    expect(toQuery({ ...EMPTY_FILTERS, hourFrom: 22, hourTo: 4 })).toBe("hour_from=22&hour_to=4");
    expect(hourRangeLabel(22, 4)).toContain("gece yarısını aşar");
    expect(hourRangeLabel(7, 9)).toBe("07:00–09:59");
  });
  it("ölümlü/yaralanma/00:00 filtreleri doğru parametre adlarıyla gider", () => {
    const q = toQuery({ ...EMPTY_FILTERS, fatal: "fatal", injury: "no_injury", excludeMidnight: true, factor: "Driver Inattention/Distraction" });
    expect(q).toContain("fatal=fatal");
    expect(q).toContain("injury=no_injury");
    expect(q).toContain("exclude_midnight=true");
    expect(q).toContain("factor=Driver+Inattention%2FDistraction");
    expect(activeCount({ ...EMPTY_FILTERS, hourFrom: 1, hourTo: 2, boroughs: ["BRONX"] })).toBe(2);
    expect(describeFilters({ ...EMPTY_FILTERS, fatal: "fatal" }, labels)).toEqual(["Ölümle sonuçlanan kazalar"]);
  });
  it("zaman dilimi kullanıcı filtresinin ilgili alanını daraltır", () => {
    const base = { ...EMPTY_FILTERS, boroughs: ["BROOKLYN"], years: [2018, 2019] };
    expect(applySlice(base, { granularity: "year", key: "2019" }).years).toEqual([2019]);
    const m = applySlice(base, { granularity: "month", key: "2019-03" });
    expect([m.years, m.months, m.boroughs]).toEqual([[2019], [3], ["BROOKLYN"]]);
    const h = applySlice(base, { granularity: "hour", key: "07" });
    expect([h.hourFrom, h.hourTo]).toEqual([7, 7]);
    expect(applySlice(base, null)).toBe(base);
    expect(sliceLabel({ granularity: "month", key: "2019-03" })).toBe("Mart 2019");
    expect(sliceLabel({ granularity: "dow", key: "6" })).toBe("Pazar");
  });
});

const CAP: Pick<LabCapabilities, "bounds" | "compatibility"> = {
  bounds: {
    dbscan: { eps_m: [5, 500], min_samples: [2, 5000], eps_days: [1, 365] },
    kmeans: { k: [2, 200], n_init: [1, 20], max_iter: [50, 1000], random_state: [0, 2 ** 31 - 1] },
    hdbscan: { min_cluster_size: [2, 5000], min_samples: [1, 1000] },
  },
  compatibility: {
    dbscan: { allowed: ["spatial_haversine", "spatiotemporal"], reasons: { spatial_projected: "x" } },
    kmeans: { allowed: ["spatial_projected"], reasons: { spatiotemporal: "karıştırır" } },
    hdbscan: { allowed: ["spatial_projected", "spatial_haversine_records"], reasons: { spatial_haversine: "ağırlık" } },
  },
};
const BUDGET = { max_hdbscan_events: 100_000, max_st_events: 300_000 };
const form = (p: Partial<LabForm>): LabForm => ({ ...defaultForm(), ...p });

describe("laboratuvar formu", () => {
  it("DBSCAN: eps ondalık olabilir, min_samples tamsayı ve sınırlı", () => {
    expect(validateForm(form({ params: { eps_m: "25,5", min_samples: "100" } }), CAP).params).toEqual({ eps_m: 25.5, min_samples: 100 });
    expect(validateForm(form({ params: { eps_m: "2", min_samples: "100" } }), CAP).errors.eps_m).toMatch(/5–500/);
    expect(validateForm(form({ params: { eps_m: "25", min_samples: "1.5" } }), CAP).errors.min_samples).toBe("Tamsayı olmalı.");
    expect(validateForm(form({ params: { eps_m: "", min_samples: "10" } }), CAP).errors.eps_m).toBe("Sayı girin.");
  });
  it("DBSCAN uzay-zaman: eps_gün gerekir", () => {
    const v = validateForm(form({ featureSet: "spatiotemporal", params: { eps_m: "50", min_samples: "5", eps_days: "0" } }), CAP);
    expect(v.errors.eps_days).toMatch(/1–365/);
  });
  it("K-Means: k, n_init, max_iter, random_state sınırları", () => {
    const f = form({ algorithm: "kmeans", featureSet: "spatial_projected", params: { k: "1", n_init: "50", max_iter: "300", random_state: "-1" } });
    const v = validateForm(f, CAP);
    expect(Object.keys(v.errors).sort()).toEqual(["k", "n_init", "random_state"]);
  });
  it("HDBSCAN: min_samples otomatik olabilir; yöntem eom/leaf", () => {
    const v = validateForm(form({ algorithm: "hdbscan", featureSet: "spatial_projected", hdbAutoMinSamples: true,
      params: { min_cluster_size: "25", min_samples: "", cluster_selection_method: "leaf" } }), CAP);
    expect(v.errors).toEqual({});
    expect(v.params).toEqual({ min_cluster_size: 25, min_samples: null, cluster_selection_method: "leaf" });
  });
  it("desteklenmeyen algoritma × öznitelik kombinasyonu sessizce kabul edilmez", () => {
    const v = validateForm(form({ algorithm: "kmeans", featureSet: "spatiotemporal", params: { k: "5", n_init: "10", max_iter: "300", random_state: "42" } }), CAP);
    expect(v.compatibilityError).toBe("karıştırır");
  });
  it("örneklem doğrulaması ve bütçe uyarıları", () => {
    expect(validateForm(form({ useSample: true, sampleN: "10", sampleSeed: "1" }), CAP).errors.sampleN).toBeDefined();
    const hd = form({ algorithm: "hdbscan", featureSet: "spatial_projected", useSample: false, params: { min_cluster_size: "25", min_samples: "25" } });
    expect(budgetWarnings(hd, 2_020_638, BUDGET)[0].level).toBe("block");
    expect(budgetWarnings({ ...hd, useSample: true, sampleN: "100000" }, 2_020_638, BUDGET).some((w) => w.level === "block")).toBe(false);
    expect(budgetWarnings(form({ featureSet: "spatiotemporal" }), 400_000, BUDGET)[0].level).toBe("block");
    expect(budgetWarnings(hd, null, BUDGET)).toEqual([]);
  });
  it("kayıtlı Faz 3 konfigürasyonu yalnızca filtresiz ve birebir aynı parametrede eşleşir", () => {
    const exps = [
      { experiment_id: "dbscan-x", algorithm: "dbscan", status: "success", stage: "dbscan_grid", has_labels: true, scope_class: "full_weighted", params: { eps_m: 25, min_samples: 100 } },
      { experiment_id: "kmeans-y", algorithm: "kmeans", status: "success", stage: "kmeans_grid", has_labels: true, scope_class: "full_weighted", params: { k: 5 } },
      { experiment_id: "hdbscan-z", algorithm: "hdbscan", status: "success", stage: "hdbscan_grid", has_labels: true, scope_class: "sample", params: { min_cluster_size: 25, min_samples: 25 } },
    ] as unknown as Experiment[];
    const f = form({ params: { eps_m: "25", min_samples: "100" } });
    expect(registryMatch(f, validateForm(f, CAP), true, exps)?.experiment_id).toBe("dbscan-x");
    expect(registryMatch(f, validateForm(f, CAP), false, exps)).toBeNull(); // filtreli → yeni iş
    const f2 = form({ params: { eps_m: "26", min_samples: "100" } });
    expect(registryMatch(f2, validateForm(f2, CAP), true, exps)).toBeNull();
    const k = form({ algorithm: "kmeans", featureSet: "spatial_projected", params: { k: "5", n_init: "10", max_iter: "300", random_state: "42" } });
    expect(registryMatch(k, validateForm(k, CAP), true, exps)?.experiment_id).toBe("kmeans-y");
    const k2 = { ...k, params: { ...k.params, random_state: "7" } };
    expect(registryMatch(k2, validateForm(k2, CAP), true, exps)).toBeNull();
    const h = form({ algorithm: "hdbscan", featureSet: "spatial_projected", useSample: true, sampleN: "100000", sampleSeed: "42",
      params: { min_cluster_size: "25", min_samples: "25", cluster_selection_method: "eom" } });
    expect(registryMatch(h, validateForm(h, CAP), true, exps)?.experiment_id).toBe("hdbscan-z");
  });
});

describe("yönlendirme ve durum", () => {
  it("hash ↔ ekran eşlemesi; bilinmeyen hash genel bakışa düşer", async () => {
    const { routeFromHash, hashFor } = await import("../../src/app/store");
    expect(routeFromHash("#/kesif")).toBe("explorer");
    expect(routeFromHash("#/laboratuvar")).toBe("lab");
    expect(routeFromHash("#/yok")).toBe("overview");
    expect(routeFromHash("")).toBe("overview");
    expect(hashFor("models")).toBe("#/modeller");
  });
  it("taslak filtre uygulanınca kanonikleşir; sıfırlama zaman dilimini de temizler", async () => {
    const { useApp } = await import("../../src/app/store");
    const s = useApp.getState();
    s.setDraft({ years: [2020, 2019] });
    expect(useApp.getState().applied.years).toEqual([]);
    useApp.getState().applyDraft();
    expect(useApp.getState().applied.years).toEqual([2019, 2020]);
    useApp.getState().setSlice({ granularity: "year", key: "2019" });
    useApp.getState().resetFilters();
    expect(useApp.getState().slice).toBeNull();
    expect(isEmpty(useApp.getState().applied)).toBe(true);
  });
});

describe("önbellekli istek", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("eşzamanlı aynı URL tek ağ isteğine iner; hata önbelleğe yazılmaz; iptal yalnız bekleyeni bırakır", async () => {
    const { cachedGet } = await import("../../src/lib/query");
    let n = 0;
    vi.stubGlobal("fetch", vi.fn(async () => { n++; return new Response(JSON.stringify({ ok: n }), { status: 200 }); }));
    const [a, b] = await Promise.all([cachedGet<{ ok: number }>("/api/x"), cachedGet<{ ok: number }>("/api/x")]);
    expect(n).toBe(1);
    expect(a).toEqual(b);
    const ctrl = new AbortController();
    const p = cachedGet("/api/y", ctrl.signal);
    ctrl.abort();
    await expect(p).rejects.toMatchObject({ name: "AbortError" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Bakımda" }), { status: 503 })));
    await expect(cachedGet("/api/z")).rejects.toMatchObject({ status: 503, message: "Bakımda" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })));
    await expect(cachedGet("/api/z")).resolves.toEqual({ ok: true });
  });
});
