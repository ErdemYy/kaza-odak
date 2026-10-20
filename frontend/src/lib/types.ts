// Faz 5 API yanıt tipleri (backend/src/saferoute/analytics). Değerler sunucudan gelir; istemci üretmez.

export interface Counted { value: string; count: number }
export interface YearCount { year: number; count: number }

export interface BoroughRow {
  borough: string; events: number; injury_crashes: number; fatal_crashes: number; persons_injured: number;
  persons_killed: number; events_in_clusters: number; clusters_dominant?: number;
}

export interface FactorRow { value: string; crashes: number; share: number | null }

export interface Freshness {
  checked_at: string | null; rows_updated_at: string | null; declared_update_frequency: string | null;
  days_since_rows_updated_at_check: number | null; days_since_rows_updated_now: number | null;
  staleness_threshold_days: number | null; verdict_at_check: string | null;
}

export interface Overview {
  source: { dataset_id: string; dataset_name: string | null; source_url: string; catalog_url: string; attribution: string | null;
    snapshot: string; acquisition: Record<string, unknown> | null; freshness: Freshness };
  records: { raw_total: number; eligible: number; excluded: number; unique_locations: number; exclusion_reasons: Record<string, number> };
  coverage: { date_min: string; date_max: string; source_earliest: string; source_latest: string;
    partial_years: { year: number; reason: string }[] };
  model: { algorithm: string; experiment_id: string; parameters: Record<string, number>; clusters: number; noise_ratio: number;
    events_clustered: number; events_noise: number; dataset_version: string; processing_version: string;
    software: Record<string, string> | null };
  by_year: YearCount[];
  by_borough: BoroughRow[];
  totals: { injury_crashes: number; fatal_crashes: number; persons_injured: number; persons_killed: number; midnight_suspect: number };
  denominators: Record<string, string>;
  top_clusters: { cluster_id: number; rank_by_events: number; n_events: number; n_unique_locations: number;
    dominant_borough: string | null; injury_crashes: number; fatal_crashes: number; centroid_lon: number; centroid_lat: number;
    peak_hour: number; date_min: string; date_max: string; top_street: string | null }[];
}

export interface FilterOptions {
  date_min: string; date_max: string; years: YearCount[]; boroughs: Counted[]; borough_unknown: number;
  vehicles: Counted[]; factors: Counted[]; midnight_suspect: number; n_events: number; factor_count_unit: string;
}

export interface RecordsSummary {
  filters: Record<string, unknown>; filters_tr: string[]; denominator: string; n_events_total: number; n_events: number;
  share_of_total: number | null; injury_crashes: number; fatal_crashes: number; persons_injured: number; persons_killed: number;
  midnight_suspect: number; date_min: string | null; date_max: string | null;
  model: { experiment_id: string; label_source: string; events_in_clusters: number; events_noise: number;
    clusters_with_events: number; clusters_total: number };
  by_year: YearCount[]; by_month: number[]; by_dow: number[]; by_hour: number[]; by_borough: BoroughRow[];
  by_vehicle: Counted[]; top_factors: FactorRow[]; factor_unspecified_share: number | null; factor_definition: string;
}

export interface Timeline { granularity: string; n_events: number; buckets: { key: string; count: number }[] }

export interface MetricDetail { value: number; status: string; metric: string; n_used: number; n_clusters_used?: number;
  noise_excluded_ratio?: number; sampling?: string; seed: number }

export interface ComparisonRow {
  algorithm: string; experiment_id: string; parameters: Record<string, number>; features: string; fit_scope: string;
  fit_n_events: number | null; fit_n_points: number | null; scope_class: string | null; n_clusters: number | null;
  n_clusters_scope: string; noise_ratio: number | null; noise_applicable: boolean; noise_scope: string | null;
  largest_cluster_share: number | null; silhouette: number | null; silhouette_detail: MetricDetail | null;
  silhouette_haversine: number | null; davies_bouldin: number | null; davies_bouldin_detail: MetricDetail | null;
  dbcv: number | null; dbcv_detail: MetricDetail | null; parameter_stability_ari: number | null; runtime_s: number | null;
  peak_memory_mb: number | null; fit_memory_mb: number | null; admissible: boolean; rejection_reasons: string[]; primary: boolean;
}

export interface ExperimentMetrics {
  silhouette: number | null; silhouette_haversine: number | null; davies_bouldin: number | null; dbcv: number | null;
  parameter_stability_ari: number | null; admissible: boolean | null; rejection_reasons: string[];
  n_clusters_full: number | null; noise_ratio_full: number | null; largest_cluster_share_full: number | null;
  cluster_size_full: Record<string, number> | null; n_clusters_eval: number | null; noise_ratio_eval: number | null;
  largest_cluster_share_eval: number | null; fit_memory_mb: number | null; fit_scope: string | null;
}

export interface Experiment {
  experiment_id: string; stage: string; algorithm: string; params: Record<string, number | null>; feature_set: string;
  scope_class: string; scope_text: string; status: string; error: string | null; n_events: number | null;
  n_unique_locations: number | null; runtime_s: number | null; peak_memory_mb: number | null; seed: number | null;
  dataset_version: string; processing_version: string; software: Record<string, string> | null; created_at: string | null;
  selected_as: string | null; has_labels: boolean; metrics: ExperimentMetrics | null; raw_metrics: Record<string, unknown> | null;
}

export interface Comparison {
  dataset_version: string; processing_version: string; software: Record<string, string>;
  eval_set: { n_events: number; seed: number; definition: string };
  selection_criteria: { max_largest_cluster_share: number; min_clusters: number; ranking: string[]; kmeans_rule: string; hdbscan_rule: string };
  kmeans_elbow_k: number | null;
  rows: ComparisonRow[];
  grids: Record<"dbscan" | "kmeans" | "hdbscan", Experiment[]>;
  selection_review: { definition: string; rows: Record<string, unknown>[] } | null;
  sensitivity: { baseline: string; params: Record<string, number>; variants: Record<string, unknown>[] } | null;
  final_choice: Record<string, unknown> | null;
  temporal: { years: Record<string, unknown>[]; refit_rule: unknown; note: unknown; persistence: unknown };
  caveats: string[]; label_semantics: string; eps_conversion: string;
}

export interface FeatureSetInfo { label: string; phase2_set: string; features: string[]; metric: string; level: string; kind: string; note: string }

export interface LabCapabilities {
  feature_sets: Record<string, FeatureSetInfo>;
  compatibility: Record<string, { allowed: string[]; reasons: Record<string, string> }>;
  bounds: Record<string, Record<string, [number, number]>>;
  budget: Record<string, number>;
  code_version: string;
  software: Record<string, string>;
}

export interface ResultSummary {
  n_events: number; n_clusters: number; noise_events: number | null; noise_ratio: number | null; noise_applicable: boolean;
  clustered_events: number; largest_cluster_share: number | null;
  cluster_size: { min: number | null; p25: number | null; median: number | null; p75: number | null; p90: number | null; max: number | null };
  size_histogram: { from: number; to: number | null; clusters: number }[];
}

export interface DynamicMetrics { silhouette: number | null; davies_bouldin: number | null; status: string; metric?: string;
  sampling?: string; n_used?: number; seed?: number; noise_excluded?: number; n_clusters_in_sample?: number }

export type JobState = "pending" | "running" | "completed" | "failed" | "cancelled" | "rejected_resource";

export interface Job {
  job_id: string; cache_key: string; state: JobState; stage: { stage: string; stage_label: string; at?: number } | null;
  request: { algorithm: string; feature_set: string; params: Record<string, number | string | null>; filters: Record<string, unknown>;
    sample: { n: number; seed: number } | null };
  filters_tr: string[]; feature_set: FeatureSetInfo; created_at: number; started_at: number | null; finished_at: number | null;
  elapsed_s: number | null; error: string | null; source: "dynamic" | "cache" | "phase3_registry"; phase3_experiment: string | null;
  n_events: number | null; n_fit_rows: number | null;
  worker: { status: string; runtime_s?: number; peak_memory_mb?: number; note?: string; n_neighbor_pairs?: number;
    n_spatial_pairs?: number; n_st_pairs?: number; inertia?: number } | null;
  result: { summary: ResultSummary; metrics?: DynamicMetrics; phase3_metrics?: ExperimentMetrics } | null;
  code_version: string;
}

export interface ClusterRow {
  cluster_id: number; rank_by_events: number | null; n_events: number; n_unique_locations: number; centroid_lon: number;
  centroid_lat: number; radius_p90_m: number; injury_crashes: number; fatal_crashes: number; persons_injured: number;
  persons_killed: number; date_min: string; date_max: string; dominant_borough: string | null; dominant_borough_share: number;
  peak_hour: number;
}

export interface Profile {
  hour_histogram: number[]; vehicles: { value: string; count: number; share: number | null }[]; top_factors: FactorRow[];
  factor_unspecified_share: number | null; midnight_suspect: number; boroughs: Counted[]; years: YearCount[];
}

export interface FilteredClusterProfile {
  cluster_id: number; experiment_id: string; n_events: number; injury_crashes: number; fatal_crashes: number;
  persons_injured: number; persons_killed: number; n_unique_locations: number; date_min: string | null; date_max: string | null;
  by_hour: number[]; by_vehicle: Counted[]; top_factors: FactorRow[]; factor_unspecified_share: number | null; midnight_suspect: number;
}

export interface DictColumnSpec { meaning: string; origin: string; transform: string; models: string; exclusion_reason: string;
  filter_use: string; interpretation_use: string; source?: string }

export interface DataDictionary {
  raw: { rows: number; column_count: number; source: string;
    columns: { name: string; source_name: string; source_type: string; missing_pct: number | null; missing_count: number | null;
      processed_as: string | null; spec: DictColumnSpec | null; group: string }[] };
  processed: { rows: number; column_count: number; null_count_method: string;
    columns: { name: string; dtype: string; missing_count: number | null; rows: number; origin: string; in_feature_sets: string[];
      in_model: boolean; group: string; spec: DictColumnSpec | null }[] };
  feature_sets: { name: string; model: string; level: string; features: string[]; metric: string; units: string;
    weight?: string; note?: string; row_filter?: string; rows: number | null; weight_sum: number | null }[];
  cleaning: {
    coordinates: Record<string, number>; exclusion_reasons: Record<string, number>; rows: Record<string, number>;
    boroughs: Record<string, unknown>; vehicles: { raw_distinct_labels: number; normalized_distinct_labels: number; category_count: number;
      label_mentions: number; by_category: Record<string, number>; by_rule: Record<string, number> };
    temporal: { midnight_suspect: number; midnight_suspect_pct: number;
      minute_heaping: { per_hour: Record<string, { on_the_hour: number; mean_other_minutes: number; ratio: number }> } };
    casualties: Record<string, unknown>; repetition: Record<string, unknown>; lineage: Record<string, unknown>;
  };
}
