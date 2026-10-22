// Faz 3 DBSCAN sonuç katmanları (MapLibre kaynakları + katmanları). Koordinatlar [boylam, enlem].
import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import type { LayerKey, Visibility } from "../lib/layers";
import { LAYERS } from "../lib/layers";
import { DATA_LAYER_BEFORE, LABEL_LAYER_BEFORE } from "./style";

export const COLORS = { primary: "#38BDF8", warning: "#F59E0B", hotspot: "#F87171", text: "#E2E8F0", noise: "#94A3B8" };
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export const SOURCES = ["boroughs", "density", "density250", "centroids", "geometries", "points"] as const;

/**
 * Küme merkezi görsel kodlaması (Faz 8B). Daire YARIÇAPI kayıt sayısının karekökü ile doğrusal artar (alan ≈ kayıt
 * sayısıyla orantılı büyür); RENK aynı kayıt sayısını üç kademede tekrar eder. Estetik amaçlı ölçek dışı büyütme yoktur;
 * lejant bu sabitlerden üretilir (Legend.tsx). sqrt(10..38) = 100..1.444 kayıt; aralık dışı değerler sınıra kıstırılır.
 */
export const CENTROID_SCALE = {
  sqrtMin: 10, sqrtMax: 38,
  /** zoom → [en küçük, en büyük] yarıçap (px) */
  radius: [[9, 1.7, 5.5], [11, 2.3, 7.5], [13, 3, 11], [15, 4.5, 15], [17, 6, 20]] as [number, number, number][],
  colorStops: [[100, COLORS.primary], [400, COLORS.warning], [900, COLORS.hotspot]] as [number, string][],
};

/** Saf: verilen zoom ve kayıt sayısında daire yarıçapı (MapLibre ifadesiyle aynı; lejant ve testler için). */
export function centroidRadius(nEvents: number, zoom: number): number {
  const { sqrtMin, sqrtMax, radius } = CENTROID_SCALE;
  const t = Math.min(1, Math.max(0, (Math.sqrt(nEvents) - sqrtMin) / (sqrtMax - sqrtMin)));
  const z = Math.min(radius[radius.length - 1][0], Math.max(radius[0][0], zoom));
  let i = 1;
  while (i < radius.length - 1 && radius[i][0] < z) i++;
  const [z0, a0, b0] = radius[i - 1], [z1, a1, b1] = radius[i];
  const k = (z - z0) / (z1 - z0 || 1);
  const lo = a0 + (a1 - a0) * k, hi = b0 + (b1 - b0) * k;
  return lo + (hi - lo) * t;
}

const SQRT_N = ["sqrt", ["get", "n_events"]];
const radiusExpr = (extra = 0) => ["interpolate", ["linear"], ["zoom"],
  ...CENTROID_SCALE.radius.flatMap(([z, lo, hi]) => [z, ["interpolate", ["linear"], SQRT_N, CENTROID_SCALE.sqrtMin, lo + extra, CENTROID_SCALE.sqrtMax, hi + extra]])];
const SELECTED = ["boolean", ["feature-state", "selected"], false] as never;

/** Her mantıksal katmanın MapLibre katman kimlikleri. */
export const LAYER_IDS: Record<LayerKey, string[]> = {
  boroughs: ["borough-fill", "borough-line"],
  density: ["density-heat-1000", "density-heat-250"],
  centroids: ["centroid-circle", "centroid-hover", "centroid-selected"],
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
        // Faz 8B: 0,85 → 0,62/0,5. Turuncu ışıma turuncu/kırmızı küme merkezlerinin arkasında kontrastı yok ediyordu.
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], minzoom, 0.62, maxzoom, maxzoom > 13 ? 0 : 0.5],
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
  // Gürültü (−1): içi soluk, konturlu gri halka — dolu mavi kümelenmiş noktalarla renk körlüğünde de karışmaz.
  add({ id: "points-noise", type: "circle", source: "points", minzoom: 15, filter: ["==", ["get", "noise"], true],
    paint: { "circle-color": COLORS.noise, "circle-opacity": 0.18, "circle-stroke-color": COLORS.noise, "circle-stroke-width": 1, "circle-stroke-opacity": 0.75,
      "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 1, 2, 10, 7], "circle-opacity-transition": FADE } });
  add({ id: "points-clustered", type: "circle", source: "points", minzoom: 15, filter: ["==", ["get", "noise"], false],
    paint: { "circle-color": COLORS.primary, "circle-opacity": 0.85, "circle-stroke-color": "#0B1120", "circle-stroke-width": 0.6,
      "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "n_events"]], 1, 2.5, 10, 9], "circle-opacity-transition": FADE } });
  add({ id: "centroid-circle", type: "circle", source: "centroids",
    paint: {
      "circle-color": ["case", SELECTED, COLORS.hotspot,
        ["interpolate", ["linear"], ["get", "n_events"], ...CENTROID_SCALE.colorStops.flat()]],
      // MapLibre: ["zoom"] yalnızca en üst düzey interpolate/step girdisi olabilir.
      "circle-radius": radiusExpr() as never,
      "circle-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.85, 16, 0.95],
      // Koyu kontur zoom'la kalınlaşır: üst üste binen iki komşu küme tek leke gibi değil, iki ayrı daire olarak okunur.
      "circle-stroke-color": ["case", SELECTED, "#FFFFFF", "#0B1120"],
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 9, ["case", SELECTED, 2.5, 0.5], 12, ["case", SELECTED, 2.5, 0.9], 15, ["case", SELECTED, 2.5, 1.4]] as never,
      "circle-opacity-transition": FADE,
    } });
  // Hover ve seçim halkaları: süzgeçle yalnızca İLGİLİ TEK küme çizilir (4.179 öğe için ek çizim maliyeti yok).
  add({ id: "centroid-hover", type: "circle", source: "centroids", filter: ["==", ["get", "cluster_id"], -1],
    paint: { "circle-radius": radiusExpr(3) as never, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#E2E8F0", "circle-stroke-width": 1.5, "circle-stroke-opacity": 0.95 } });
  add({ id: "centroid-selected", type: "circle", source: "centroids", filter: ["==", ["get", "cluster_id"], -1],
    paint: { "circle-radius": radiusExpr(7) as never, "circle-color": "rgba(248,113,113,0.14)", "circle-stroke-color": COLORS.hotspot, "circle-stroke-width": 2, "circle-stroke-opacity": 0.95 } });
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

/** Seçili kümenin merkez ve geometri öznitelik durumunu günceller (promoteId = cluster_id). Seçim varken diğer küme
 *  merkezleri ve zarfları soluklaştırılır (seçili küme çevresindeki şehirden ayrışır); seçim kalkınca eski görünüm döner. */
export function setSelected(map: MlMap, clusterId: number | null): void {
  for (const source of ["centroids", "geometries"]) {
    if (selectedId !== null) map.setFeatureState({ source, id: selectedId }, { selected: false });
    if (clusterId !== null) map.setFeatureState({ source, id: clusterId }, { selected: true });
  }
  selectedId = clusterId;
  const active = clusterId !== null;
  if (map.getLayer("centroid-selected")) map.setFilter("centroid-selected", ["==", ["get", "cluster_id"], clusterId ?? -1]);
  if (map.getLayer("centroid-circle")) {
    map.setPaintProperty("centroid-circle", "circle-opacity", active
      ? ["case", SELECTED, 1, 0.38] as never
      : ["interpolate", ["linear"], ["zoom"], 9, 0.85, 16, 0.95]);
  }
  if (map.getLayer("geom-fill")) map.setPaintProperty("geom-fill", "fill-opacity", ["case", SELECTED, 0.35, active ? 0.07 : 0.16] as never);
  if (map.getLayer("geom-line")) map.setPaintProperty("geom-line", "line-opacity", ["case", SELECTED, 0.95, active ? 0.4 : 0.9] as never);
}

/** Hover halkası (yalnızca bir küme çizilir). */
export function setHovered(map: MlMap, clusterId: number | null): void {
  if (map.getLayer("centroid-hover")) map.setFilter("centroid-hover", ["==", ["get", "cluster_id"], clusterId ?? -1]);
}
