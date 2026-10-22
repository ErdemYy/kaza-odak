// Harita stili: OpenFreeMap vektör karoları (OpenMapTiles şeması, OSM verisi), API anahtarı gerektirmez.
// Altlık katmanları burada; Faz 3 veri katmanları dataLayers.ts içinde eklenir.
import type { LayerSpecification, SkySpecification, StyleSpecification } from "maplibre-gl";

export const TILEJSON_URL = "https://tiles.openfreemap.org/planet";
export const GLYPHS_URL = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
export const ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> · ' +
  '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">© OpenMapTiles</a> · ' +
  'Veri <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap katkıcıları</a> · ' +
  'Kaza ve ilçe verisi: NYC Open Data';

export type Theme = "night" | "day";

interface Palette {
  background: string; water: string; park: string; landuse: string; road: string; roadMajor: string; roadMotorway: string;
  roadCasing: string; rail: string; building: string; buildingTop: string; buildingUnknown: string; label: string;
  labelHalo: string; waterLabel: string;
}

export const PALETTES: Record<Theme, Palette> = {
  night: {
    background: "#0B1120", water: "#0A1A2E", park: "#0F1E25", landuse: "#0E1729", road: "#1C2A42", roadMajor: "#26385A",
    roadMotorway: "#2F4670", roadCasing: "#0B1120", rail: "#22314D", building: "#1A2740", buildingTop: "#2A3B5C",
    buildingUnknown: "#141F33", label: "#94A3B8", labelHalo: "#0B1120", waterLabel: "#3B5B80",
  },
  day: {
    background: "#E8EDF3", water: "#B9D3E8", park: "#D3E4D0", landuse: "#E1E6EC", road: "#FFFFFF", roadMajor: "#FFFFFF",
    roadMotorway: "#F6D9A8", roadCasing: "#C7CFDA", rail: "#B8C0CC", building: "#CBD3DE", buildingTop: "#DCE2EA",
    buildingUnknown: "#D9DEE5", label: "#334155", labelHalo: "#F8FAFC", waterLabel: "#4A6E92",
  },
};

/**
 * Bina yüksekliği: OpenMapTiles render_height (OSM height / building:levels). OSM'de yükseklik etiketi
 * yoksa OpenMapTiles varsayılan 5 m atar; bu binalar (render_height = 5 ve taban = 0) "yükseklik verisi
 * yok olası" sayılır, extrüde edilmez ve düz, ayrı renkte çizilir (uydurma yükseklik gösterilmez).
 * Denetim: reports/phase4/building_height_audit.json.
 */
const UNKNOWN_HEIGHT = ["all", ["==", ["get", "render_height"], 5], ["==", ["coalesce", ["get", "render_min_height"], 0], 0]];
const NOT_HIDDEN = ["!=", ["get", "hide_3d"], true];

function roadWidth(base: number): unknown {
  return ["interpolate", ["exponential", 1.5], ["zoom"], 10, base * 0.4, 14, base * 1.6, 18, base * 12];
}

/** Tema renklerine bağlı boya özellikleri (gece/gündüz geçişinde setPaintProperty ile uygulanır). */
export function themePaint(theme: Theme): Record<string, Record<string, unknown>> {
  const p = PALETTES[theme];
  return {
    background: { "background-color": p.background },
    water: { "fill-color": p.water },
    park: { "fill-color": p.park },
    landuse: { "fill-color": p.landuse },
    "road-casing": { "line-color": p.roadCasing },
    "road-minor": { "line-color": p.road },
    "road-major": { "line-color": p.roadMajor },
    "road-motorway": { "line-color": p.roadMotorway },
    rail: { "line-color": p.rail },
    "building-unknown-height": { "fill-color": p.buildingUnknown, "fill-outline-color": p.building },
    "building-3d": { "fill-extrusion-color": ["interpolate", ["linear"], ["coalesce", ["get", "render_height"], 0], 0, p.building, 120, p.buildingTop] },
    "road-label": { "text-color": p.label, "text-halo-color": p.labelHalo },
    "place-label": { "text-color": p.label, "text-halo-color": p.labelHalo },
    "water-label": { "text-color": p.waterLabel, "text-halo-color": p.labelHalo },
  };
}

/** Eğik kamerada ufuk ve uzak sis (gece/gündüz). */
export function themeSky(theme: Theme): SkySpecification {
  return theme === "night"
    ? { "sky-color": "#0B1120", "horizon-color": "#1B2B4A", "fog-color": "#0E1729", "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.6, "fog-ground-blend": 0.75, "atmosphere-blend": 0 }
    : { "sky-color": "#BFD6EE", "horizon-color": "#E8EEF5", "fog-color": "#E1E7EE", "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.6, "fog-ground-blend": 0.8, "atmosphere-blend": 0 };
}

export function buildBaseStyle(theme: Theme): StyleSpecification {
  const paint = themePaint(theme);
  const layers: LayerSpecification[] = [
    { id: "background", type: "background", paint: paint.background },
    { id: "landuse", type: "fill", source: "omt", "source-layer": "landuse", paint: { ...paint.landuse, "fill-opacity": 0.6 } },
    { id: "park", type: "fill", source: "omt", "source-layer": "park", paint: { ...paint.park, "fill-opacity": 0.8 } },
    { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: paint.water },
    { id: "rail", type: "line", source: "omt", "source-layer": "transportation", minzoom: 12,
      filter: ["in", ["get", "class"], ["literal", ["rail", "transit"]]], paint: { ...paint.rail, "line-width": 1 } },
    { id: "road-casing", type: "line", source: "omt", "source-layer": "transportation", minzoom: 12,
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]],
      layout: { "line-cap": "round", "line-join": "round" }, paint: { ...paint["road-casing"], "line-width": roadWidth(1.6) as never } },
    { id: "road-minor", type: "line", source: "omt", "source-layer": "transportation", minzoom: 12,
      filter: ["in", ["get", "class"], ["literal", ["tertiary", "minor", "service", "track"]]],
      layout: { "line-cap": "round", "line-join": "round" }, paint: { ...paint["road-minor"], "line-width": roadWidth(0.8) as never } },
    { id: "road-major", type: "line", source: "omt", "source-layer": "transportation", minzoom: 8,
      filter: ["in", ["get", "class"], ["literal", ["trunk", "primary", "secondary"]]],
      layout: { "line-cap": "round", "line-join": "round" }, paint: { ...paint["road-major"], "line-width": roadWidth(1.2) as never } },
    { id: "road-motorway", type: "line", source: "omt", "source-layer": "transportation", minzoom: 6,
      filter: ["==", ["get", "class"], "motorway"], layout: { "line-cap": "round", "line-join": "round" },
      paint: { ...paint["road-motorway"], "line-width": roadWidth(1.4) as never } },
    { id: "building-unknown-height", type: "fill", source: "omt", "source-layer": "building", minzoom: 13,
      filter: ["all", NOT_HIDDEN, UNKNOWN_HEIGHT] as never, paint: paint["building-unknown-height"] },
    { id: "building-3d", type: "fill-extrusion", source: "omt", "source-layer": "building", minzoom: 13,
      filter: ["all", NOT_HIDDEN, ["!", UNKNOWN_HEIGHT]] as never,
      paint: { ...paint["building-3d"], "fill-extrusion-height": ["coalesce", ["get", "render_height"], 0], // bazı OSM parçalarında null (konsol uyarısı + siyah dolgu)
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": ["interpolate", ["linear"], ["zoom"], 13, 0, 14, 0.92] } as never },
    { id: "water-label", type: "symbol", source: "omt", "source-layer": "water_name", minzoom: 10,
      layout: { "text-field": ["coalesce", ["get", "name:tr"], ["get", "name_en"], ["get", "name"]], "text-font": ["Noto Sans Italic"], "text-size": 12 },
      paint: { ...paint["water-label"], "text-halo-width": 1 } },
    { id: "road-label", type: "symbol", source: "omt", "source-layer": "transportation_name", minzoom: 14,
      layout: { "symbol-placement": "line", "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"], "text-size": 11 },
      paint: { ...paint["road-label"], "text-halo-width": 1.2 } },
    { id: "place-label", type: "symbol", source: "omt", "source-layer": "place", minzoom: 11,
      filter: ["in", ["get", "class"], ["literal", ["suburb", "neighbourhood", "quarter"]]],
      layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Bold"], "text-size": 11, "text-transform": "uppercase", "text-letter-spacing": 0.08 },
      paint: { ...paint["place-label"], "text-halo-width": 1.2 } },
  ];
  return {
    version: 8,
    name: `SafeRoute 3D ${theme}`,
    glyphs: GLYPHS_URL,
    sky: themeSky(theme),
    // Extrüzyon gölgelemesi: haritaya bağlı ışık, duvarlar arasında yön farkı oluşur
    light: { anchor: "map", position: [1.3, 210, 35], intensity: 0.55, color: "#FFFFFF" },
    sources: { omt: { type: "vector", url: TILEJSON_URL, attribution: ATTRIBUTION } },
    layers,
  };
}

/** Etiket katmanlarının ilki (veri katmanları için yedek ekleme noktası). */
export const LABEL_LAYER_BEFORE = "water-label";
/** Zemin düzlemindeki Faz 3 veri katmanları bina katmanlarının altına eklenir. */
export const DATA_LAYER_BEFORE = "building-unknown-height";
