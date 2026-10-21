// Gerçek NYC 3D şehir haritası (Faz 4 motoru: MapLibre + Three.js GLB katmanı). Harita BİR KEZ kurulur;
// filtre, veri kaynağı, katman veya tema değişiminde yalnızca kaynak verisi / boya özellikleri güncellenir.
//
// Veri kaynağı modları (arayüzde açıkça ayrılır):
//  * model, filtresiz  → Faz 4 uç noktaları (tam veri etiketleri)
//  * model, filtreli   → /api/records/* : filtrelenmiş GERÇEK kayıtlar, etiketler tam veri modelinden (yeniden kümeleme YOK)
//  * result            → /api/results/{kimlik}/* : kayıtlı Faz 3 deneyi veya tamamlanmış laboratuvar işi
import { Map as MaplibreMap, type MapMouseEvent, type Map as MlMap } from "maplibre-gl";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import type { CameraAction } from "../../components/CameraControls";
import type { ViewportInfo } from "../../components/Legend";
import { api, ApiError, assertClusterMatch, bboxParam, type ClusterDetail, type Meta, type PointsResponse } from "../../lib/api";
import { boroughTarget, cityTarget, clusterTarget, durationFor, type FitTarget, type FlyTarget } from "../../lib/camera";
import { fmtInt } from "../../lib/format";
import type { BBox, LngLat } from "../../lib/geo";
import { bboxSpan, snapBBox } from "../../lib/geo";
import { densityCell, POINT_MIN_ZOOM, pointQueryKind, type MotionLevel, type Visibility } from "../../lib/layers";
import { cachedGet } from "../../lib/query";
import { validateRegistry, type AssetRegistry } from "../../lib/registry";
import type { ClusterRow, FilteredClusterProfile, Profile } from "../../lib/types";
import { addDataLayers, applyVisibility, setSelected, setSourceData } from "../../map/dataLayers";
import { pickCluster, type CentroidIndex } from "../../map/picking";
import { buildBaseStyle, themePaint, themeSky, type Theme } from "../../map/style";
import { CityModelsLayer, type InspectorPlacement } from "../../map/threeLayer";
import { nearbyRoads, pickRoadSegment } from "../../map/traffic";
import type { MapSource } from "../../app/store";

// Yalnızca ilk kare için: gerçek ilçe sınırları API'den gelince kamera bunlara oturtulur.
const INITIAL_BOUNDS: BBox = [-74.26, 40.49, -73.7, 40.92];

declare global {
  interface Window { __saferoute?: Record<string, unknown> }
}

export type LoadState = { phase: "loading" | "ready" | "error"; message: string };

export interface RecordsClusterDetail {
  full: ClusterDetail; filtered: FilteredClusterProfile & { boroughs: { value: string; count: number }[] };
  filters_tr: string[]; filters_active: boolean;
  model: { algorithm: string; experiment_id: string; parameters: Record<string, number>; features: string; metric: string };
}

export type Selection =
  | { kind: "model"; detail: ClusterDetail; records: RecordsClusterDetail | null; recordsError: string | null }
  | { kind: "result"; resultId: string; row: ClusterRow & Profile & { experiment_id: string }; meta: Record<string, unknown> };

export type ClusterState =
  | { status: "idle" }
  | { status: "loading"; clusterId: number }
  | { status: "error"; clusterId: number; message: string }
  | { status: "ready"; selection: Selection };

export interface CityMapHandle {
  camera: (a: CameraAction) => void;
  goBorough: (b: string | null) => void;
  focusSelected: () => void;
  selectCluster: (clusterId: number) => void;
  clearSelection: () => void;
  setInspector: (p: InspectorPlacement | null) => void;
  center: () => LngLat;
}

export interface CityMapProps {
  active: boolean;
  source: MapSource;
  filterQuery: string; // boş = filtre yok
  visibility: Visibility;
  theme: Theme;
  motion: MotionLevel;
  padding: (width: number) => FitTarget["padding"];
  onMeta: (m: Meta) => void;
  onLoad: (s: LoadState) => void;
  onViewport: (v: ViewportInfo) => void;
  onView: (v: { zoom: number; bearing: number; center: LngLat }) => void;
  onCluster: (c: ClusterState) => void;
  onRoadNote: (n: string | null) => void;
  onRegistry: (r: AssetRegistry) => void;
  onInspectorError: (e: string | null) => void;
  onLayerCounts: (c: { clusters: number; total: number; label: string } | null) => void;
}

type Mode = { source: MapSource; q: string };

/** Hedef noktanın ekran konumunda (±3 px) 3D bina extrüzyonu çiziliyor mu? */
function occluded(map: MlMap, target: LngLat): boolean {
  if (!map.getLayer("building-3d") || map.getLayoutProperty("building-3d", "visibility") === "none") return false;
  const p = map.project(target);
  return map.queryRenderedFeatures([[p.x - 3, p.y - 3], [p.x + 3, p.y + 3]], { layers: ["building-3d"] }).length > 0;
}
const modeKey = (m: Mode) => `${m.source.kind === "model" ? "model" : m.source.id}|${m.q}`;

function endpoints(m: Mode) {
  const q = m.q ? `&${m.q}` : "";
  if (m.source.kind === "result") {
    // Sonuç modu: q yalnızca zaman dilimidir (üyelik sabit). Yoğunluk da sonucun KENDİ olay kapsamından gelir
    // (ör. HDBSCAN 100k örneklemi tüm NYC kayıtlarıyla birlikte gösterilmez).
    const id = encodeURIComponent(m.source.id);
    return {
      centroids: `/api/results/${id}/clusters${m.q ? `?${m.q}` : ""}`,
      density: (cell: number) => `/api/results/${id}/density?cell=${cell}${q}`,
      points: (b: BBox) => `/api/results/${id}/points?bbox=${bboxParam(b)}&limit=8000${q}`,
    };
  }
  if (!m.q) {
    return { centroids: "/api/clusters", density: (cell: number) => `/api/density?cell=${cell}`, points: null };
  }
  return {
    centroids: `/api/records/clusters?${m.q}`,
    density: (cell: number) => `/api/records/density?cell=${cell}${q}`,
    points: (b: BBox, kind?: string) => `/api/records/points?bbox=${bboxParam(b)}&kind=${kind ?? "all"}&limit=8000${q}`,
  };
}

export const CityMap = forwardRef<CityMapHandle, CityMapProps>(function CityMap(props, ref) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const layerRef = useRef<CityModelsLayer | null>(null);
  const metaRef = useRef<Meta | null>(null);
  const registryRef = useRef<AssetRegistry | null>(null);
  const cb = useRef(props);
  cb.current = props;
  const motionRef = useRef<MotionLevel>(props.motion);
  const activeRef = useRef(props.active);
  const visRef = useRef<Visibility>(props.visibility);
  const modeRef = useRef<Mode>({ source: props.source, q: props.filterQuery });
  const sceneRef = useRef<{ cluster: Parameters<CityModelsLayer["setClusterScene"]>[0]; inspector: InspectorPlacement | null }>({ cluster: null, inspector: null });
  const pointsAbort = useRef<AbortController | null>(null);
  const dataAbort = useRef<AbortController | null>(null);
  const lastPointsKey = useRef<string>("");
  const loaded = useRef<{ geometries: boolean; density250: string }>({ geometries: false, density250: "" });
  const selectedRef = useRef<{ clusterId: number; centroid: LngLat; radius: number } | null>(null);
  const centroidIndex = useRef<CentroidIndex>(new Map());
  const styleReady = useRef(false);
  const selectSeq = useRef(0);
  // Bağlam kaybından sonra kaynakları yeniden doldurmak için son yüklenen GeoJSON'lar (nokta katmanı hariç)
  const dataCache = useRef<Record<string, GeoJSON.FeatureCollection>>({});
  const put = useCallback((map: MlMap, src: "geometries" | "density250" | "boroughs" | "centroids" | "density", data: GeoJSON.FeatureCollection) => {
    dataCache.current[src] = data;
    setSourceData(map, src, data);
  }, []);

  const goTo = useCallback((t: FitTarget | FlyTarget) => {
    const map = mapRef.current;
    if (!map) return;
    if (t.kind === "fit") map.fitBounds(t.bounds, { pitch: t.pitch, bearing: t.bearing, padding: t.padding, duration: t.duration, essential: true });
    else map.flyTo({ center: t.center, zoom: t.zoom, pitch: t.pitch, bearing: t.bearing, duration: t.duration, essential: true, curve: 1.42 });
  }, []);

  const withPadding = useCallback(<T extends FitTarget>(t: T): T => ({ ...t, padding: cb.current.padding(window.innerWidth) }), []);

  const resetView = useCallback(() => {
    const b = metaRef.current?.boroughs?.bounds;
    if (b) goTo(withPadding(cityTarget(b, motionRef.current, window.innerWidth)));
  }, [goTo, withPadding]);

  // ---------------------------------------------------------------- görünen alan noktaları (bbox)
  const refreshViewport = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    const kind = pointQueryKind(visRef.current, zoom);
    if (zoom < POINT_MIN_ZOOM) {
      lastPointsKey.current = "";
      setSourceData(map, "points", { type: "FeatureCollection", features: [] });
      return cb.current.onViewport({ state: "zoom-in", minZoom: POINT_MIN_ZOOM });
    }
    if (!kind) {
      lastPointsKey.current = "";
      setSourceData(map, "points", { type: "FeatureCollection", features: [] });
      return cb.current.onViewport({ state: "off" });
    }
    const b = map.getBounds();
    const bbox = snapBBox([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    const maxSpan = metaRef.current?.limits.max_point_bbox_span_deg ?? 0.05;
    if (bboxSpan(bbox) > maxSpan) return cb.current.onViewport({ state: "error", message: "Görünen alan nokta sorgusu için çok geniş; biraz yakınlaştırın veya eğimi azaltın." });
    const mode = modeRef.current;
    const key = `${bbox.join(",")}|${kind}|${modeKey(mode)}`;
    if (key === lastPointsKey.current) return;
    lastPointsKey.current = key;
    pointsAbort.current?.abort();
    const ctrl = new AbortController();
    pointsAbort.current = ctrl;
    cb.current.onViewport({ state: "loading" });
    const ep = endpoints(mode);
    const req: Promise<PointsResponse> = ep.points ? cachedGet<PointsResponse>(ep.points(bbox, kind), ctrl.signal, 60_000)
      : api.points(bbox, kind, 8000, ctrl.signal);
    req.then((res) => {
      // Sonuç modunda tür süzgeci istemcide (sonuç uç noktası tüm konumları döndürür; sayılar yine sunucudan)
      const data = mode.source.kind === "result" && kind !== "all"
        ? { ...res, features: res.features.filter((f) => (kind === "noise") === Boolean(f.properties?.noise)) } : res;
      setSourceData(map, "points", data);
      cb.current.onViewport({ state: "ready", data: res });
    }).catch((e: Error) => {
      if (e.name === "AbortError") return;
      lastPointsKey.current = "";
      cb.current.onViewport({ state: "error", message: e.message });
    });
  }, []);

  const ensureLazyLayers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    const mode = modeRef.current;
    if (!loaded.current.geometries && zoom >= 11.5 && visRef.current.geometries) {
      loaded.current.geometries = true;
      api.geometries().then((g) => put(map, "geometries", g)).catch(() => { loaded.current.geometries = false; });
    }
    const key = modeKey(mode);
    if (loaded.current.density250 !== key && densityCell(zoom) === 250 && visRef.current.density) {
      loaded.current.density250 = key;
      cachedGet<GeoJSON.FeatureCollection>(endpoints(mode).density(250)).then((d) => {
        if (modeKey(modeRef.current) === key) put(map, "density250", d);
      }).catch(() => { loaded.current.density250 = ""; });
    }
  }, [put]);

  // ---------------------------------------------------------------- mod verisi (merkezler + yoğunluk)
  const loadModeData = useCallback(async () => {
    const map = mapRef.current;
    if (!map || !styleReady.current) return;
    const mode = modeRef.current;
    const key = modeKey(mode);
    dataAbort.current?.abort();
    const ctrl = new AbortController();
    dataAbort.current = ctrl;
    const ep = endpoints(mode);
    try {
      const [clusters, density] = await Promise.all([
        cachedGet<GeoJSON.FeatureCollection<GeoJSON.Point> & { experiment_id: string; total_clusters: number; returned?: number }>(ep.centroids, ctrl.signal),
        cachedGet<GeoJSON.FeatureCollection<GeoJSON.Point> & { total_events: number }>(ep.density(1000), ctrl.signal),
      ]);
      if (modeKey(modeRef.current) !== key) return;
      const meta = metaRef.current;
      if (mode.source.kind === "model" && meta && clusters.experiment_id !== meta.model.experiment_id) {
        throw new ApiError(409, "Küme katmanı ile model meta verisinin deney kimliği farklı.");
      }
      put(map, "centroids", clusters);
      centroidIndex.current = new Map(clusters.features.map((f) => [Number(f.properties!.cluster_id),
        { lngLat: f.geometry.coordinates as LngLat, experimentId: String(f.properties!.experiment_id) }]));
      put(map, "density", density);
      // Küme geometrileri yalnızca seçili modelde vardır; filtrede yalnızca filtrelenmiş olay içeren kümeler
      if (map.getLayer("geom-fill")) {
        const filter = mode.source.kind === "result" ? ["==", ["get", "cluster_id"], -999]
          : mode.q ? ["in", ["get", "cluster_id"], ["literal", [...centroidIndex.current.keys()]]] : null;
        for (const id of ["geom-fill", "geom-line"]) map.setFilter(id, filter as never);
      }
      loaded.current.density250 = "";
      ensureLazyLayers();
      lastPointsKey.current = "";
      refreshViewport();
      const label = mode.source.kind === "result" ? mode.source.label : mode.q ? "Filtrelenmiş kayıtlar" : "Seçili model";
      cb.current.onLayerCounts({ clusters: clusters.features.length, total: clusters.total_clusters, label });
      cb.current.onLoad({ phase: "ready", message: mode.source.kind === "result"
        ? (mode.q ? `${mode.source.label}: bu dilimde ${fmtInt(clusters.features.length)} / ${fmtInt(clusters.total_clusters)} küme`
          : `${mode.source.label}: ${fmtInt(clusters.total_clusters)} küme`)
        : `Gerçek veri yüklendi: ${fmtInt(clusters.features.length)} küme · ${fmtInt(density.total_events)} olay (yoğunluk özeti)` });
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      cb.current.onLoad({ phase: "error", message: `Veri yüklenemedi: ${(e as Error).message}` });
    }
  }, [ensureLazyLayers, put, refreshViewport]);

  // ---------------------------------------------------------------- 3D sahne
  const placeClusterScene = useCallback((clusterId: number, center: LngLat, radius: number, prefix = "") => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    const road = pickRoadSegment(center, nearbyRoads(map));
    const cs = { clusterId, center, radiusM: radius, road };
    sceneRef.current.cluster = cs;
    cb.current.onRoadNote(null);
    layer.setClusterScene(cs).then((n) => {
      if (n < 0) return; // daha yeni bir seçim bu sahneyi geçersiz kıldı
      cb.current.onRoadNote(prefix + (n > 0
        ? `${n} temsili araç, küme yakınındaki gerçek bir yol (OSM) üzerinde hareket eden bir simülasyondur; geçmiş kazaların hareket kaydı değildir.`
        : road
          ? "Küme yakınındaki yol parçası temsili trafik için çok kısa; araç gösterilmiyor."
          : "Küme merkezine 60 m içinde uygun yol bulunamadı; temsili araç gösterilmiyor."));
    }).catch((e: Error) => cb.current.onInspectorError(e.message));
  }, []);

  const flyToSelected = useCallback(() => {
    const map = mapRef.current;
    const s = selectedRef.current;
    if (!map || !s) return;
    goTo(clusterTarget(s.centroid, s.radius, map.getBearing(), motionRef.current));
  }, [goTo]);

  const selectCluster = useCallback(async (clusterId: number, experimentId?: string) => {
    const map = mapRef.current;
    if (!map) return;
    const mode = modeRef.current;
    const seq = ++selectSeq.current;
    const exp = experimentId ?? centroidIndex.current.get(clusterId)?.experimentId ?? "";
    setSelected(map, clusterId);
    cb.current.onCluster({ status: "loading", clusterId });
    try {
      let selection: Selection;
      let center: LngLat;
      let radius: number;
      if (mode.source.kind === "result") {
        const r = await cachedGet<{ cluster: ClusterRow & Profile & { experiment_id: string }; meta: Record<string, unknown> }>(
          `/api/results/${encodeURIComponent(mode.source.id)}/clusters/${clusterId}`);
        if (r.cluster.cluster_id !== clusterId) throw new ApiError(409, "Küme yanıtı seçilen kümeyle eşleşmiyor");
        selection = { kind: "result", resultId: mode.source.id, row: r.cluster, meta: r.meta };
        center = [r.cluster.centroid_lon, r.cluster.centroid_lat];
        radius = r.cluster.radius_p90_m;
      } else {
        const d = await api.cluster(clusterId, exp);
        assertClusterMatch(d, clusterId, exp);
        // Zenginleştirme (filtrelenmiş profil, ilçeler, araçlar): olay deposu hazır değilse ayrıntı yine gösterilir
        let records: RecordsClusterDetail | null = null;
        let recordsError: string | null = null;
        try {
          records = await cachedGet<RecordsClusterDetail>(`/api/records/clusters/${clusterId}?experiment_id=${encodeURIComponent(exp)}${mode.q ? `&${mode.q}` : ""}`);
        } catch (e) {
          recordsError = (e as Error).message;
        }
        selection = { kind: "model", detail: d, records, recordsError };
        center = [d.centroid_lon, d.centroid_lat];
        radius = d.radius_p90_m;
      }
      if (seq !== selectSeq.current) return;
      selectedRef.current = { clusterId, centroid: center, radius };
      cb.current.onCluster({ status: "ready", selection });
      // Uçuş bitip hedefteki karolar yüklenince gerçek yol geometrisi sorgulanır. Dinleyici geçişten ÖNCE
      // kaydedilir (süre 0 olan geçişte moveend eşzamanlı tetiklenir).
      map.once("moveend", () => {
        const t0 = performance.now();
        let adjusted = false;
        const wait = () => {
          if (selectedRef.current?.clusterId !== clusterId) return;
          if (!(map.areTilesLoaded() || performance.now() - t0 > 4000)) return void window.setTimeout(wait, 100);
          // Bina engeli: kümenin ekran noktasında bir 3D bina çiziliyorsa kamera binanın arkasında/içinde kalmıştır.
          // Bir kez daha dik bir açıya geçilir (kamera yükselir); sahne geçiş bittikten sonra kurulur.
          if (!adjusted && occluded(map, center)) {
            adjusted = true;
            map.once("moveend", () => placeClusterScene(clusterId, center, radius, "Kümeyi örten bir bina nedeniyle kamera eğimi 25°'ye indirildi. "));
            map.easeTo({ pitch: 25, duration: durationFor(motionRef.current, 900), essential: true });
            return;
          }
          placeClusterScene(clusterId, center, radius);
        };
        wait();
      });
      goTo(clusterTarget(center, radius, map.getBearing(), motionRef.current));
    } catch (e) {
      if (seq !== selectSeq.current) return;
      cb.current.onCluster({ status: "error", clusterId, message: (e as Error).message });
    }
  }, [goTo, placeClusterScene]);

  const clearSelection = useCallback(() => {
    const map = mapRef.current;
    if (map) setSelected(map, null);
    selectSeq.current++;
    selectedRef.current = null;
    sceneRef.current.cluster = null;
    cb.current.onRoadNote(null);
    cb.current.onCluster({ status: "idle" });
    layerRef.current?.setClusterScene(null);
  }, []);

  const addModelLayer = useCallback((map: MlMap, reg: AssetRegistry) => {
    const c = map.getCenter();
    const layer = new CityModelsLayer(reg.models, [c.lng, c.lat]);
    layer.motion = motionRef.current;
    layer.onStatus = (s) => { if (s.error) cb.current.onInspectorError(s.error); };
    layerRef.current = layer;
    map.addLayer(layer); // en üstte: araçlar yol etiketlerinin altında kalmaz; derinlik testi binalarla ortak
    if (!visRef.current.models) map.setLayoutProperty(layer.id, "visibility", "none");
    if (sceneRef.current.cluster) layer.setClusterScene(sceneRef.current.cluster);
    if (sceneRef.current.inspector) layer.setInspector(sceneRef.current.inspector).catch((e: Error) => cb.current.onInspectorError(e.message));
  }, []);

  // ---------------------------------------------------------------- harita kurulumu (bir kez)
  useEffect(() => {
    if (!container.current) return;
    const map = new MaplibreMap({
      container: container.current,
      style: buildBaseStyle("night"),
      bounds: INITIAL_BOUNDS,
      pitch: 45,
      bearing: -17,
      maxPitch: 78,
      minZoom: 8.5,
      maxZoom: 20,
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
      // Boyut izleme elle yapılır: keşif ekranı gizliyken (diğer ekranlar) pencere/kap boyutu değişse de harita
      // yeniden çizilmez ve yeni karo indirmez; ekran görünür olunca bir kez yeniden boyutlandırılır.
      trackResize: false,
    });
    mapRef.current = map;
    const resizeObserver = new ResizeObserver(() => {
      if (activeRef.current) map.resize();
    });
    resizeObserver.observe(container.current);
    const ctrl = new AbortController();

    map.on("load", async () => {
      addDataLayers(map);
      applyVisibility(map, visRef.current);
      styleReady.current = true;
      try {
        const [m, boroughs] = await Promise.all([api.meta(ctrl.signal), api.boroughs(ctrl.signal)]);
        metaRef.current = m;
        cb.current.onMeta(m);
        put(map, "boroughs", boroughs);
        if (m.boroughs) goTo(withPadding(cityTarget(m.boroughs.bounds, "off", window.innerWidth)));
        await loadModeData();
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        cb.current.onLoad({ phase: "error", message: `Veri yüklenemedi: ${(e as Error).message}` });
        return;
      }
      try {
        const res = await fetch("models/registry.json", { signal: ctrl.signal });
        if (!res.ok) throw new Error(`Varlık kaydı bulunamadı (${res.status})`);
        const reg = (await res.json()) as AssetRegistry;
        const problems = validateRegistry(reg);
        if (problems.length) throw new Error(`Varlık kaydı geçersiz: ${problems.join("; ")}`);
        registryRef.current = reg;
        cb.current.onRegistry(reg);
        addModelLayer(map, reg);
      } catch (e) {
        if ((e as Error).name !== "AbortError") cb.current.onInspectorError((e as Error).message);
      }
    });

    const onMove = () => cb.current.onView({ zoom: map.getZoom(), bearing: map.getBearing(), center: [map.getCenter().lng, map.getCenter().lat] });
    let debounce: number | undefined;
    map.on("move", onMove);
    map.on("moveend", () => {
      onMove();
      ensureLazyLayers();
      window.clearTimeout(debounce);
      debounce = window.setTimeout(refreshViewport, 200);
    });
    map.on("error", (e) => {
      // Karo/glyph ağ hataları haritayı durdurmaz; kullanıcıya gösterilir. Diğer hatalar konsola yazılır.
      const msg = (e.error as Error | undefined)?.message ?? String(e.error);
      if (/Failed to fetch|NetworkError|ERR_|AJAXError/.test(msg)) cb.current.onLoad({ phase: "error", message: "Harita karoları alınamadı (ağ). Kaza katmanları çalışmaya devam eder." });
      else console.error("MapLibre:", msg);
    });

    const clickable = ["centroid-circle", "geom-fill"];
    const onClick = (e: MapMouseEvent) => {
      const hit = pickCluster(map, e.point.x, e.point.y, centroidIndex.current, clickable);
      if (hit) selectCluster(hit.clusterId, hit.experimentId);
    };
    // Tek tıklama dinleyicisi: üst üste binen dairelerde iki kez seçim yapılmaz.
    map.on("click", onClick);
    for (const l of clickable) {
      map.on("mouseenter", l, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", l, () => { map.getCanvas().style.cursor = ""; });
    }

    // WebGL bağlam kaybı: 3D model katmanı yeni bağlamla yeniden kurulur (modeller önbellekteki GLB'lerden).
    map.on("webglcontextlost", () => {
      if (layerRef.current) layerRef.current.status.contextLost = true;
      cb.current.onLoad({ phase: "loading", message: "WebGL bağlamı kaybedildi; yeniden kuruluyor…" });
    });
    map.on("webglcontextrestored", () => {
      // MapLibre stili asenkron yeniden kurar (setStyle, diff: false); özel katmanlar geri gelmez.
      const rebuild = () => {
        addDataLayers(map);
        for (const [src, data] of Object.entries(dataCache.current)) setSourceData(map, src as never, data);
        applyVisibility(map, visRef.current);
        if (selectedRef.current) setSelected(map, selectedRef.current.clusterId);
        const reg = registryRef.current;
        if (map.getLayer("city-models")) map.removeLayer("city-models");
        if (reg) addModelLayer(map, reg);
        lastPointsKey.current = "";
        refreshViewport();
        cb.current.onLoad({ phase: "ready", message: "WebGL bağlamı geri yüklendi; 3D sahne yeniden kuruldu." });
      };
      if (map.isStyleLoaded()) rebuild();
      else map.once("style.load", rebuild);
    });

    window.__saferoute = {
      map,
      layer: () => layerRef.current,
      // Faz 4 test kancası sözleşmesi: seçili kümenin cluster_id alanı
      selected: () => (selectedRef.current ? { cluster_id: selectedRef.current.clusterId, ...selectedRef.current } : null),
      visibility: () => visRef.current,
      mode: () => modeKey(modeRef.current),
    };
    return () => {
      resizeObserver.disconnect();
      ctrl.abort();
      pointsAbort.current?.abort();
      dataAbort.current?.abort();
      map.remove();
      mapRef.current = null;
    };
  }, [addModelLayer, ensureLazyLayers, goTo, loadModeData, put, refreshViewport, selectCluster, withPadding]);

  // ---------------------------------------------------------------- dış durum → harita (yeniden kurulum YOK)
  useEffect(() => {
    const next: Mode = { source: props.source, q: props.filterQuery };
    if (modeKey(next) === modeKey(modeRef.current)) return;
    const sourceChanged = (next.source.kind === "model" ? "model" : next.source.id) !== (modeRef.current.source.kind === "model" ? "model" : modeRef.current.source.id);
    modeRef.current = next;
    // Farklı sonucun küme numaraları eşleşmez: kaynak değişince seçim temizlenir. Filtre değişince seçili
    // kümenin filtrelenmiş profili yeniden alınır.
    if (sourceChanged) {
      clearSelection();
      resetView(); // yeni sonucun kümeleri şehir ölçeğinde görülsün
    } else if (selectedRef.current) selectCluster(selectedRef.current.clusterId);
    loadModeData();
  }, [props.source, props.filterQuery, clearSelection, loadModeData, resetView, selectCluster]);

  useEffect(() => {
    visRef.current = props.visibility;
    const map = mapRef.current;
    if (!map || !styleReady.current) return;
    applyVisibility(map, props.visibility);
    ensureLazyLayers();
    lastPointsKey.current = "";
    refreshViewport();
  }, [props.visibility, ensureLazyLayers, refreshViewport]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady.current) return;
    for (const [layer, paint] of Object.entries(themePaint(props.theme))) {
      if (!map.getLayer(layer)) continue;
      for (const [prop, value] of Object.entries(paint)) map.setPaintProperty(layer, prop as never, value as never);
    }
    map.setSky(themeSky(props.theme));
  }, [props.theme]);

  useEffect(() => {
    motionRef.current = props.motion;
    if (layerRef.current) layerRef.current.motion = props.active ? props.motion : "off";
    mapRef.current?.triggerRepaint();
  }, [props.motion, props.active]);

  // Ekran görünür olunca kap boyutu değişmiş olabilir; gizliyken temsili animasyon durur ve yeniden boyutlandırma
  // ertelenir (GPU boşta, karo indirilmez).
  useEffect(() => {
    activeRef.current = props.active;
    if (props.active) mapRef.current?.resize();
  }, [props.active]);

  useImperativeHandle(ref, () => ({
    camera: (a) => {
      const map = mapRef.current;
      if (!map) return;
      const duration = durationFor(motionRef.current, 450);
      switch (a) {
        case "zoomIn": return void map.zoomIn({ duration });
        case "zoomOut": return void map.zoomOut({ duration });
        case "rotL": return void map.rotateTo(map.getBearing() - 30, { duration });
        case "rotR": return void map.rotateTo(map.getBearing() + 30, { duration });
        case "pitchUp": return void map.easeTo({ pitch: Math.min(78, map.getPitch() + 10), duration });
        case "pitchDown": return void map.easeTo({ pitch: Math.max(0, map.getPitch() - 10), duration });
        case "north": return void map.easeTo({ bearing: 0, duration });
        case "reset": return resetView();
      }
    },
    goBorough: (b) => {
      const bounds = metaRef.current?.boroughs?.bounds;
      if (!bounds) return;
      goTo(withPadding(b ? boroughTarget(b, bounds, motionRef.current, window.innerWidth) : cityTarget(bounds, motionRef.current, window.innerWidth)));
    },
    focusSelected: flyToSelected,
    selectCluster: (id) => { selectCluster(id); },
    clearSelection,
    setInspector: (p) => {
      sceneRef.current.inspector = p;
      const map = mapRef.current;
      if (p && map && map.getZoom() < 16.5) map.flyTo({ center: p.lngLat, zoom: 18.2, pitch: 60, duration: durationFor(motionRef.current, 1800), essential: true });
      layerRef.current?.setInspector(p).catch((e: Error) => cb.current.onInspectorError(e.message));
    },
    center: () => {
      const c = mapRef.current?.getCenter();
      return c ? [c.lng, c.lat] : [-73.95, 40.7];
    },
  }), [clearSelection, flyToSelected, goTo, resetView, selectCluster, withPadding]);

  // MapLibre CSS'i .maplibregl-map'e position:relative verir (katmansız CSS, Tailwind yardımcılarını ezer):
  // konumlandırma sarmalayıcıda, harita kabı yalnızca tam boyut.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="w-full h-full" data-testid="map" aria-label="New York 3D haritası" role="region" />
    </div>
  );
});
