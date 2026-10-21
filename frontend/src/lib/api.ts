// Faz 4 katman API'si istemcisi. Tüm sayılar sunucudaki doğrulanmış katman dosyalarından gelir.
import type { BBox } from "./geo";

export interface ModelInfo {
  algorithm: string;
  experiment_id: string;
  parameters: { eps_m: number; min_samples: number };
  primary_model: string | null;
  label_semantics: string;
  geometry_semantics: string;
  reported: { n_clusters_full: number; noise_ratio_full: number; largest_cluster_share_full: number; runtime_s: number };
}

export interface Meta {
  model: ModelInfo;
  counts: {
    events_total: number; events_clustered: number; events_noise: number; noise_ratio: number; clusters: number;
    locations_total: number; locations_clustered: number; locations_noise: number;
  };
  dataset_version: string;
  processing_version: string;
  density: Record<string, { cells: number; events: number; max_events_per_cell: number }>;
  boroughs: { bounds: Record<string, BBox>; source: Record<string, string> } | null;
  source_manifest: { sha256: string; verified_files: string[] };
  point_reduction: string;
  layer_version: string;
  limits: { max_point_bbox_span_deg: number; max_point_limit: number };
}

export interface RankedValue { value: string; count: number; share: number }

export interface ClusterDetail {
  cluster_id: number; experiment_id: string; rank_by_events: number; n_events: number; n_unique_locations: number;
  centroid_lon: number; centroid_lat: number; bbox_min_lon: number; bbox_min_lat: number; bbox_max_lon: number;
  bbox_max_lat: number; radius_p90_m: number; hull_area_km2: number | null; geometry_kind: string;
  date_min: string; date_max: string; active_years: number; injury_crashes: number; fatal_crashes: number;
  persons_injured: number; persons_killed: number; injury_crash_share: number; peak_hour: number;
  dominant_borough: string | null; dominant_borough_share: number | null; factor_unspecified_share: number;
  hour_histogram: number[]; top_streets: RankedValue[]; top_contributing_factors: RankedValue[];
  top_vehicle_categories: RankedValue[]; time_periods: RankedValue[];
}

export interface PointsResponse extends GeoJSON.FeatureCollection<GeoJSON.Point> {
  experiment_id: string; kind: string; bbox: BBox; total_locations: number; total_events: number;
  returned_locations: number; returned_events: number; truncated: boolean; limit?: number; offset?: number; next_offset?: number | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Katman sunucusuna ulaşılamadı. 'saferoute serve' çalışıyor mu?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* gövde JSON değil */
    }
    throw new ApiError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

const bboxParam = (b: BBox) => b.map((v) => v.toFixed(6)).join(",");

/** Faz 5 uç noktaları için genel istemci (aynı hata modeli). */
export const getJSON = <T,>(path: string, signal?: AbortSignal) => get<T>(path, signal);
export const postJSON = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  get<T>(path, signal, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const deleteJSON = <T,>(path: string) => get<T>(path, undefined, { method: "DELETE" });
export { bboxParam };

export const api = {
  meta: (s?: AbortSignal) => get<Meta>("/api/meta", s),
  boroughs: (s?: AbortSignal) => get<GeoJSON.FeatureCollection>("/api/boroughs", s),
  clusters: (s?: AbortSignal) => get<GeoJSON.FeatureCollection<GeoJSON.Point> & { experiment_id: string; total_clusters: number }>("/api/clusters", s),
  geometries: (s?: AbortSignal) => get<GeoJSON.FeatureCollection & { experiment_id: string }>("/api/clusters/geometries", s),
  density: (cell: number, s?: AbortSignal) => get<GeoJSON.FeatureCollection<GeoJSON.Point> & { total_events: number }>(`/api/density?cell=${cell}`, s),
  points: (b: BBox, kind: "clustered" | "noise" | "all", limit: number, s?: AbortSignal) =>
    get<PointsResponse>(`/api/points?bbox=${bboxParam(b)}&kind=${kind}&limit=${limit}`, s),
  cluster: (id: number, experimentId: string, s?: AbortSignal) =>
    get<ClusterDetail>(`/api/clusters/${id}?experiment_id=${encodeURIComponent(experimentId)}`, s),
};

/** Seçilen kümenin yanıtı tıklanan kimlik ve deneyle birebir eşleşmeli (yanlış küme açılmaz). */
export function assertClusterMatch(detail: ClusterDetail, clusterId: number, experimentId: string): void {
  if (detail.cluster_id !== clusterId || detail.experiment_id !== experimentId) {
    throw new ApiError(409, `Küme yanıtı eşleşmiyor: beklenen ${experimentId}#${clusterId}, gelen ${detail.experiment_id}#${detail.cluster_id}`);
  }
}
