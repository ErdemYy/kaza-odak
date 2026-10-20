// Laboratuvar formu: istemci tarafı doğrulama (sunucu aynı kuralları ayrıca uygular). Saf fonksiyonlar; birim testli.
import type { Experiment, LabCapabilities } from "../../lib/types";

export type Algorithm = "dbscan" | "kmeans" | "hdbscan";

export interface LabForm {
  algorithm: Algorithm;
  featureSet: string;
  params: Record<string, string>; // girdiler metin olarak tutulur; doğrulama sayıya çevirir
  hdbAutoMinSamples: boolean;
  useSample: boolean;
  sampleN: string;
  sampleSeed: string;
}

export const DEFAULT_PARAMS: Record<Algorithm, Record<string, string>> = {
  dbscan: { eps_m: "25", min_samples: "100", eps_days: "30" },
  kmeans: { k: "20", n_init: "10", max_iter: "300", random_state: "42" },
  hdbscan: { min_cluster_size: "25", min_samples: "25", cluster_selection_method: "eom" },
};

export const PARAM_LABELS: Record<string, { label: string; unit?: string; help: string }> = {
  eps_m: { label: "eps", unit: "metre", help: "Komşuluk yarıçapı. İçeride metreden radyana çevrilir (eps_rad = eps_m / 6 371 008,8)." },
  min_samples: { label: "min_samples", help: "Çekirdek nokta için eps içinde gereken en az olay sayısı (ağırlık toplamı; nokta kendisi dahil)." },
  eps_days: { label: "eps_gün", unit: "gün", help: "Uzay-zaman komşuluğu: iki olay en çok bu kadar gün arayla olmalı." },
  k: { label: "k", help: "Küme sayısı. K-Means her olayı bir kümeye atar (gürültü yok)." },
  n_init: { label: "n_init", help: "Farklı başlangıçlarla tekrar sayısı; en düşük atalet seçilir." },
  max_iter: { label: "max_iter", help: "Tek bir çalıştırmada en çok yineleme." },
  random_state: { label: "random_state", help: "Rastgele tohum (tekrarlanabilirlik)." },
  min_cluster_size: { label: "min_cluster_size", help: "Bir kümenin en az olay sayısı." },
};

export function defaultForm(): LabForm {
  return { algorithm: "dbscan", featureSet: "spatial_haversine", params: { ...DEFAULT_PARAMS.dbscan }, hdbAutoMinSamples: false,
    useSample: false, sampleN: "50000", sampleSeed: "42" };
}

export function paramKeys(f: Pick<LabForm, "algorithm" | "featureSet">): string[] {
  if (f.algorithm === "dbscan") return f.featureSet === "spatiotemporal" ? ["eps_m", "min_samples", "eps_days"] : ["eps_m", "min_samples"];
  if (f.algorithm === "kmeans") return ["k", "n_init", "max_iter", "random_state"];
  return ["min_cluster_size", "min_samples"];
}

export interface Validation {
  errors: Record<string, string>;
  compatibilityError: string | null;
  params: Record<string, number | string | null>;
  sample: { n: number; seed: number } | null;
}

export function validateForm(f: LabForm, cap: Pick<LabCapabilities, "bounds" | "compatibility">): Validation {
  const errors: Record<string, string> = {};
  const params: Record<string, number | string | null> = {};
  const comp = cap.compatibility[f.algorithm];
  const compatibilityError = comp && !comp.allowed.includes(f.featureSet) ? (comp.reasons[f.featureSet] ?? "Bu öznitelik seti bu algoritmayla desteklenmiyor.") : null;
  for (const k of paramKeys(f)) {
    if (f.algorithm === "hdbscan" && k === "min_samples" && f.hdbAutoMinSamples) {
      params[k] = null;
      continue;
    }
    const raw = (f.params[k] ?? "").trim().replace(",", ".");
    const [lo, hi] = cap.bounds[f.algorithm]?.[k] ?? [Number.NEGATIVE_INFINITY, Number.POSITIVE_INFINITY];
    const v = Number(raw);
    if (raw === "" || !Number.isFinite(v)) errors[k] = "Sayı girin.";
    else if (k !== "eps_m" && !Number.isInteger(v)) errors[k] = "Tamsayı olmalı.";
    else if (v < lo || v > hi) errors[k] = `${lo}–${hi} aralığında olmalı.`;
    else params[k] = v;
  }
  if (f.algorithm === "hdbscan") params.cluster_selection_method = f.params.cluster_selection_method === "leaf" ? "leaf" : "eom";
  let sample: Validation["sample"] = null;
  if (f.useSample) {
    const n = Number(f.sampleN), seed = Number(f.sampleSeed);
    if (!Number.isInteger(n) || n < 1000 || n > 2_100_000) errors.sampleN = "1.000–2.100.000 arası tamsayı.";
    if (!Number.isInteger(seed) || seed < 0) errors.sampleSeed = "Negatif olmayan tamsayı.";
    if (!errors.sampleN && !errors.sampleSeed) sample = { n, seed };
  }
  return { errors, compatibilityError, params, sample };
}

/** Kapsamdaki olay sayısına göre bütçe ön değerlendirmesi (sunucu kesin kararı verir). */
export function budgetWarnings(f: LabForm, nScope: number | null, budget: Record<string, number>): { level: "block" | "warn"; text: string }[] {
  if (nScope === null) return [];
  const n = f.useSample ? Math.min(nScope, Number(f.sampleN) || nScope) : nScope;
  const out: { level: "block" | "warn"; text: string }[] = [];
  if (f.algorithm === "hdbscan" && n > budget.max_hdbscan_events) {
    out.push({ level: "block", text: `HDBSCAN kayıt düzeyidir ve ~karesel ölçeklenir: ${n.toLocaleString("tr-TR")} olay > ${budget.max_hdbscan_events.toLocaleString("tr-TR")} bütçe. Örneklem kullanın veya filtreyi daraltın.` });
  }
  if (f.featureSet === "spatiotemporal" && n > budget.max_st_events) {
    out.push({ level: "block", text: `Uzay-zaman DBSCAN kayıt düzeyidir: ${n.toLocaleString("tr-TR")} olay > ${budget.max_st_events.toLocaleString("tr-TR")} bütçe.` });
  }
  if (f.algorithm === "dbscan" && f.featureSet === "spatial_haversine" && Number(f.params.eps_m) > 150) {
    out.push({ level: "warn", text: "Büyük eps komşu çifti sayısını hızla artırır; sunucu fit öncesi sayar ve bütçeyi aşarsa çalıştırmaz." });
  }
  if (f.algorithm === "hdbscan" && n > 50_000 && n <= budget.max_hdbscan_events) {
    out.push({ level: "warn", text: "HDBSCAN 100.000 olayda Faz 3'te ~69 sn sürdü; bu boyutta işlem birkaç dakika sürebilir." });
  }
  return out;
}

/** Filtresiz istek Faz 3 ızgarasındaki bir konfigürasyonla aynıysa o deney (sunucu da aynı eşleşmeyi yapar). */
export function registryMatch(f: LabForm, v: Validation, filtersEmpty: boolean, experiments: Experiment[]): Experiment | null {
  if (!filtersEmpty || Object.keys(v.errors).length || v.compatibilityError) return null;
  const grid = experiments.filter((e) => e.algorithm === f.algorithm && e.status === "success" && e.stage.endsWith("grid") && e.has_labels);
  const p = v.params;
  if (f.algorithm === "dbscan" && f.featureSet === "spatial_haversine" && !v.sample) {
    return grid.find((e) => e.scope_class === "full_weighted" && e.params.eps_m === p.eps_m && e.params.min_samples === p.min_samples) ?? null;
  }
  if (f.algorithm === "kmeans" && !v.sample && p.n_init === 10 && p.max_iter === 300 && p.random_state === 42) {
    return grid.find((e) => e.scope_class === "full_weighted" && e.params.k === p.k) ?? null;
  }
  if (f.algorithm === "hdbscan" && f.featureSet === "spatial_projected" && v.sample?.n === 100_000 && v.sample.seed === 42 && p.cluster_selection_method === "eom") {
    return grid.find((e) => e.scope_class === "sample" && e.params.min_cluster_size === p.min_cluster_size && e.params.min_samples === p.min_samples) ?? null;
  }
  return null;
}
