// Faz 3 DBSCAN sonuç katmanları (MapLibre kaynakları + katmanları). Koordinatlar [boylam, enlem].
import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import type { LayerKey, Visibility } from "../lib/layers";
import { LAYERS } from "../lib/layers";
import { DATA_LAYER_BEFORE, LABEL_LAYER_BEFORE } from "./style";

export const COLORS = { primary: "#38BDF8", warning: "#F59E0B", hotspot: "#F87171", text: "#E2E8F0", noise: "#94A3B8" };
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export const SOURCES = ["boroughs", "density", "density250", "centroids", "geometries", "points"] as const;

/** Her mantıksal katmanın MapLibre katman kimlikleri. */
export const LAYER_IDS: Record<LayerKey, string[]> = {
  boroughs: ["borough-fill", "borough-line"],
  density: ["density-heat-1000", "density-heat-250"],
  centroids: ["centroid-circle"],
  geometries: ["geom-fill", "geom-line"],
  clustered: ["points-clustered"],
  noise: ["points-noise"],
  buildings: ["building-3d", "building-unknown-height"],
  models: ["city-models"],
};

const FADE = { duration: 350, delay: 0 };

export function addDataLayers(map: MlMap): void {
  for (const s of SOURCES) if (!map.getSource(s)) map.addSource(s, { type: "geojson", data: EMPTY, promoteId: s === "centroids" || s === "geometries" ? "cluster_id" : undefined });
  // Zemin düzlemindeki veri katmanları bina extrüzyonlarının ALTINA eklenir: binalar arkalarında kalan
  // poligon/daireleri örter (aksi hâlde 2D katmanlar binaların üstünde "yüzer").
  const before = map.getLayer(DATA_LAYER_BEFORE) ? DATA_LAYER_BEFORE : map.getLayer(LABEL_LAYER_BEFORE) ? LABEL_LAYER_BEFORE : undefined;
  const add = (l: Parameters<MlMap["addLayer"]>[0]) => { if (!map.getLayer(l.id)) map.addLayer(l, before); };

  add({ id: "borough-fill", type: "fill", source: "boroughs", paint: { "fill-color": COLORS.primary, "fill-opacity": 0.025, "fill-opacity-transition": FADE } });
  add({ id: "borough-line", type: "line", source: "boroughs",
    paint: { "line-color": COLORS.primary, "line-opacity": 0.55, "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.8, 14, 2], "line-dasharray": [3, 2], "line-opacity-transition": FADE } });
  // Yoğunluk: sunucu ızgarası hücre merkezleri. Isı yarıçapı hücre aralığının ~1,6 katı (piksel cinsinden
  // zoom'la 2× büyür) — aksi hâlde hücreler ayrık lekeler olarak görünür. 1 km ızgara z < 12, 250 m ızgara z ≥ 12.
  const heat = (source: string, cellM: number, minzoom: number, maxzoom: number, weightMax: number) => {
    const px = (z: number) => (1.6 * cellM) / ((40075016.686 * Math.cos((40.7 * Math.PI) / 180)) / (512 * 2 ** z));
    add({ id: `density-heat-${cellM}`, type: "heatmap", source, minzoom, maxzoom,
      paint: {
        "heatmap-weight": ["interpolate", ["linear"], ["get", "events"], 0, 0, weightMax, 1],
        "heatmap-intensity": 0.9,
        "heatmap-radius": ["interpolate", ["exponential", 2], ["zoom"], minzoom, px(minzoom), maxzoom, px(maxzoom)],
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(11,17,32,0)", 0.15, "rgba(56,189,248,0.18)",
          0.4, "rgba(56,189,248,0.45)", 0.65, "rgba(245,158,11,0.6)", 0.9, "rgba(248,113,113,0.75)"],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], minzoom, 0.85, maxzoom, maxzoom > 13 ? 0 : 0.85],
        "heatmap-opacity-transition": FADE,
      } });
  };
  heat("density", 1000, 8, 12, 9000);
  heat("density250", 250, 12, 15.5, 1200);
  add({ id: "geom-fill", type: "fill", source: "geometries", minzoom: 12,
    paint: { "fill-color": ["case", ["boolean", ["feature-state", "selected"], false], COLORS.hotspot, COLORS.warning],
      "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.35, 0.16], "fill-opacity-transition": FADE } });
  add({ id: "geom-line", type: "line", source: "geometries", minzoom: 12,
    paint: { "line-color": ["case", ["boolean", ["feature-state", "selected"], false], COLORS.hotspot, COLORS.warning],
      "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1], "line-opacity": 0.9, "line-opacity-transition": FADE } });
  add({ id: "points-noise", type: "circle", source: "points", minzoom: 15, filter: ["==", ["get", "noise"], true],
    paint: { "circle-color": COLORS.noise, "circle-opacity": 0.55, "circle-stroke-width": 0,
      "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 1, 2, 10, 7], "circle-opacity-transition": FADE } });
  add({ id: "points-clustered", type: "circle", source: "points", minzoom: 15, filter: ["==", ["get", "noise"], false],
    paint: { "circle-color": COLORS.primary, "circle-opacity": 0.85, "circle-stroke-color": "#0B1120", "circle-stroke-width": 0.6,
      "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 1, 2.5, 10, 9], "circle-opacity-transition": FADE } });
  add({ id: "centroid-circle", type: "circle", source: "centroids",
    paint: {
      "circle-color": ["case", ["boolean", ["feature-state", "selected"], false], COLORS.hotspot,
        ["interpolate", ["linear"], ["get", "n_events"], 100, COLORS.primary, 400, COLORS.warning, 900, COLORS.hotspot]],
      // MapLibre: ["zoom"] yalnızca en üst düzey interpolate/step girdisi olabilir.
      "circle-radius": ["interpolate", ["linear"], ["zoom"],
        9, ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 10, 1.4, 38, 5],
        13, ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 10, 3, 38, 11],
        17, ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 10, 6, 38, 20]],
      "circle-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.8, 16, 0.9],
      "circle-stroke-color": ["case", ["boolean", ["feature-state", "selected"], false], "#FFFFFF", "#0B1120"],
      "circle-stroke-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.5, 0.8],
      "circle-opacity-transition": FADE,
    } });
}

export function setSourceData(map: MlMap, source: (typeof SOURCES)[number], data: GeoJSON.FeatureCollection): void {
  (map.getSource(source) as GeoJSONSource | undefined)?.setData(data);
}

/** Görünürlük: önce saydamlık geçişi, sonra layout görünürlüğü (yumuşak katman geçişi). */
export function applyVisibility(map: MlMap, v: Visibility): void {
  for (const def of LAYERS) {
    for (const id of LAYER_IDS[def.key]) {
      if (!map.getLayer(id)) continue;
      map.setLayoutProperty(id, "visibility", v[def.key] ? "visible" : "none");
    }
  }
}

let selectedId: number | null = null;

/** Seçili kümenin merkez ve geometri öznitelik durumunu günceller (promoteId = cluster_id). */
export function setSelected(map: MlMap, clusterId: number | null): void {
  for (const source of ["centroids", "geometries"]) {
    if (selectedId !== null) map.setFeatureState({ source, id: selectedId }, { selected: false });
    if (clusterId !== null) map.setFeatureState({ source, id: clusterId }, { selected: true });
  }
  selectedId = clusterId;
}
