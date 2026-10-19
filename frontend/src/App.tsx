import { Map as MaplibreMap, type MapMouseEvent, type Map as MlMap } from "maplibre-gl";
import { useCallback, useEffect, useRef, useState } from "react";
import { AssetInspector } from "./components/AssetInspector";
import { CameraControls, type CameraAction } from "./components/CameraControls";
import { ClusterPanel, type ClusterState } from "./components/ClusterPanel";
import { Legend, type ViewportInfo } from "./components/Legend";
import { SidePanel } from "./components/SidePanel";
import { TopBar, type LoadState } from "./components/TopBar";
import { api, ApiError, assertClusterMatch, type ClusterDetail, type Meta } from "./lib/api";
import { BOROUGH_TR, boroughTarget, cityTarget, clusterTarget, durationFor, type FitTarget, type FlyTarget } from "./lib/camera";
import type { BBox, LngLat } from "./lib/geo";
import { bboxSpan, snapBBox } from "./lib/geo";
import { densityCell, defaultVisibility, POINT_MIN_ZOOM, pointQueryKind, toggleLayer, type LayerKey, type MotionLevel, type Visibility } from "./lib/layers";
import { fmtInt } from "./lib/format";
import { validateRegistry, type AssetRegistry } from "./lib/registry";
import { addDataLayers, applyVisibility, setSelected, setSourceData } from "./map/dataLayers";
import { buildBaseStyle, themePaint, themeSky, type Theme } from "./map/style";
import { pickCluster, type CentroidIndex } from "./map/picking";
import { CityModelsLayer, type InspectorPlacement } from "./map/threeLayer";
import { nearbyRoads, pickRoadSegment } from "./map/traffic";

// Yalnızca ilk kare için: gerçek ilçe sınırları API'den gelince kamera bunlara oturtulur.
const INITIAL_BOUNDS: BBox = [-74.26, 40.49, -73.7, 40.92];

declare global {
  interface Window { __saferoute?: Record<string, unknown> }
}

function initialMotion(): MotionLevel {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "reduced" : "full";
}

export default function App() {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const layerRef = useRef<CityModelsLayer | null>(null);
  const metaRef = useRef<Meta | null>(null);
  const registryRef = useRef<AssetRegistry | null>(null);
  const motionRef = useRef<MotionLevel>(initialMotion());
  const visRef = useRef<Visibility>(defaultVisibility());
  const sceneRef = useRef<{ cluster: Parameters<CityModelsLayer["setClusterScene"]>[0]; inspector: InspectorPlacement | null }>({ cluster: null, inspector: null });
  const pointsAbort = useRef<AbortController | null>(null);
  const lastPointsKey = useRef<string>("");
  const loaded = useRef<{ geometries: boolean; density250: boolean }>({ geometries: false, density250: false });
  const selectedRef = useRef<ClusterDetail | null>(null);
  const centroidIndex = useRef<CentroidIndex>(new Map());
  // Bağlam kaybından sonra kaynakları yeniden doldurmak için son yüklenen GeoJSON'lar (nokta katmanı hariç)
  const dataCache = useRef<Record<string, GeoJSON.FeatureCollection>>({});
  const put = useCallback((map: MlMap, src: "geometries" | "density250" | "boroughs" | "centroids" | "density", data: GeoJSON.FeatureCollection) => {
    dataCache.current[src] = data;
    setSourceData(map, src, data);
  }, []);

  const [meta, setMeta] = useState<Meta | null>(null);
  const [registry, setRegistry] = useState<AssetRegistry | null>(null);
  const [load, setLoad] = useState<LoadState>({ phase: "loading", message: "Harita ve doğrulanmış katmanlar yükleniyor…" });
  const [theme, setTheme] = useState<Theme>("night");
  const [motion, setMotionState] = useState<MotionLevel>(motionRef.current);
  const [visibility, setVisibility] = useState<Visibility>(visRef.current);
  const [borough, setBorough] = useState<string | null>(null);
  const [view, setView] = useState({ zoom: 10, bearing: 0, center: [-73.95, 40.7] as LngLat });
  const [cluster, setCluster] = useState<ClusterState>({ status: "idle" });
  const [viewport, setViewport] = useState<ViewportInfo>({ state: "zoom-in", minZoom: POINT_MIN_ZOOM });
  const [assetsOpen, setAssetsOpen] = useState(false);
  const [placement, setPlacement] = useState<InspectorPlacement | null>(null);
  const [inspectorError, setInspectorError] = useState<string | null>(null);
  const [roadNote, setRoadNote] = useState<string | null>(null);

  const goTo = useCallback((t: FitTarget | FlyTarget) => {
    const map = mapRef.current;
    if (!map) return;
    if (t.kind === "fit") map.fitBounds(t.bounds, { pitch: t.pitch, bearing: t.bearing, padding: t.padding, duration: t.duration, essential: true });
    else map.flyTo({ center: t.center, zoom: t.zoom, pitch: t.pitch, bearing: t.bearing, duration: t.duration, essential: true, curve: 1.42 });
  }, []);

  const resetView = useCallback(() => {
    const b = metaRef.current?.boroughs?.bounds;
    if (b) goTo(cityTarget(b, motionRef.current, window.innerWidth));
    setBorough(null);
  }, [goTo]);

  // ---------------------------------------------------------------- görünen alan noktaları (bbox)
  const refreshViewport = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    const kind = pointQueryKind(visRef.current, zoom);
    if (zoom < POINT_MIN_ZOOM) {
      lastPointsKey.current = "";
      setSourceData(map, "points", { type: "FeatureCollection", features: [] });
      return setViewport({ state: "zoom-in", minZoom: POINT_MIN_ZOOM });
    }
    if (!kind) {
      lastPointsKey.current = "";
      setSourceData(map, "points", { type: "FeatureCollection", features: [] });
      return setViewport({ state: "off" });
    }
    const b = map.getBounds();
    const bbox = snapBBox([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    const maxSpan = metaRef.current?.limits.max_point_bbox_span_deg ?? 0.05;
    if (bboxSpan(bbox) > maxSpan) return setViewport({ state: "error", message: "Görünen alan nokta sorgusu için çok geniş; biraz yakınlaştırın veya eğimi azaltın." });
    const key = `${bbox.join(",")}|${kind}`;
    if (key === lastPointsKey.current) return;
    lastPointsKey.current = key;
    pointsAbort.current?.abort();
    const ctrl = new AbortController();
    pointsAbort.current = ctrl;
    setViewport({ state: "loading" });
    api.points(bbox, kind, 8000, ctrl.signal).then((res) => {
      setSourceData(map, "points", res);
      setViewport({ state: "ready", data: res });
    }).catch((e: Error) => {
      if (e.name === "AbortError") return;
      lastPointsKey.current = "";
      setViewport({ state: "error", message: e.message });
    });
  }, []);

  const ensureLazyLayers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    if (!loaded.current.geometries && zoom >= 11.5 && visRef.current.geometries) {
      loaded.current.geometries = true;
      api.geometries().then((g) => put(map, "geometries", g)).catch(() => { loaded.current.geometries = false; });
    }
    if (!loaded.current.density250 && densityCell(zoom) === 250 && visRef.current.density) {
      loaded.current.density250 = true;
      api.density(250).then((d) => put(map, "density250", d)).catch(() => { loaded.current.density250 = false; });
    }
  }, []);

  // ---------------------------------------------------------------- 3D sahne
  const placeClusterScene = useCallback((d: ClusterDetail) => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    const center: LngLat = [d.centroid_lon, d.centroid_lat];
    const road = pickRoadSegment(center, nearbyRoads(map));
    const cs = { clusterId: d.cluster_id, center, radiusM: d.radius_p90_m, road };
    sceneRef.current.cluster = cs;
    setRoadNote(null);
    layer.setClusterScene(cs).then((n) => {
      if (n < 0) return; // daha yeni bir seçim bu sahneyi geçersiz kıldı
      setRoadNote(n > 0
        ? `${n} temsili araç, küme yakınındaki gerçek bir yol (OSM) üzerinde hareket eden bir simülasyondur; geçmiş kazaların hareket kaydı değildir.`
        : road
          ? "Küme yakınındaki yol parçası temsili trafik için çok kısa; araç gösterilmiyor."
          : "Küme merkezine 60 m içinde uygun yol bulunamadı; temsili araç gösterilmiyor.");
    }).catch((e: Error) => setInspectorError(e.message));
  }, []);

  const selectCluster = useCallback(async (clusterId: number, experimentId: string) => {
    const map = mapRef.current;
    if (!map) return;
    setSelected(map, clusterId);
    setCluster({ status: "loading", clusterId });
    try {
      const d = await api.cluster(clusterId, experimentId);
      assertClusterMatch(d, clusterId, experimentId);
      selectedRef.current = d;
      setCluster({ status: "ready", detail: d });
      // Uçuş bitip hedefteki karolar yüklenince gerçek yol geometrisi sorgulanır. Dinleyici geçişten ÖNCE
      // kaydedilir (süre 0 olan geçişte moveend eşzamanlı tetiklenir).
      map.once("moveend", () => {
        const t0 = performance.now();
        const wait = () => {
          if (selectedRef.current?.cluster_id !== d.cluster_id) return;
          if (map.areTilesLoaded() || performance.now() - t0 > 4000) placeClusterScene(d);
          else window.setTimeout(wait, 100);
        };
        wait();
      });
      goTo(clusterTarget([d.centroid_lon, d.centroid_lat], d.radius_p90_m, map.getBearing(), motionRef.current));
    } catch (e) {
      setCluster({ status: "error", clusterId, message: (e as Error).message });
    }
  }, [goTo, placeClusterScene]);

  const clearSelection = useCallback(() => {
    const map = mapRef.current;
    if (map) setSelected(map, null);
    selectedRef.current = null;
    sceneRef.current.cluster = null;
    setRoadNote(null);
    setCluster({ status: "idle" });
    layerRef.current?.setClusterScene(null);
  }, []);

  const addModelLayer = useCallback((map: MlMap, reg: AssetRegistry) => {
    const c = map.getCenter();
    const layer = new CityModelsLayer(reg.models, [c.lng, c.lat]);
    layer.motion = motionRef.current;
    layer.onStatus = (s) => { if (s.error) setInspectorError(s.error); };
    layerRef.current = layer;
    map.addLayer(layer); // en üstte: araçlar yol etiketlerinin altında kalmaz; derinlik testi binalarla ortak
    if (!visRef.current.models) map.setLayoutProperty(layer.id, "visibility", "none");
    if (sceneRef.current.cluster) layer.setClusterScene(sceneRef.current.cluster);
    if (sceneRef.current.inspector) layer.setInspector(sceneRef.current.inspector).catch((e: Error) => setInspectorError(e.message));
  }, []);

  // ---------------------------------------------------------------- harita kurulumu
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
    });
    mapRef.current = map;
    const ctrl = new AbortController();

    map.on("load", async () => {
      addDataLayers(map);
      applyVisibility(map, visRef.current);
      try {
        const [m, boroughs, clusters, density] = await Promise.all([
          api.meta(ctrl.signal), api.boroughs(ctrl.signal), api.clusters(ctrl.signal), api.density(1000, ctrl.signal),
        ]);
        if (clusters.experiment_id !== m.model.experiment_id) throw new ApiError(409, "Küme katmanı ile model meta verisinin deney kimliği farklı.");
        metaRef.current = m;
        setMeta(m);
        put(map, "boroughs", boroughs);
        put(map, "centroids", clusters);
        centroidIndex.current = new Map(clusters.features.map((f) => [Number(f.properties!.cluster_id),
          { lngLat: f.geometry.coordinates as LngLat, experimentId: String(f.properties!.experiment_id) }]));
        put(map, "density", density);
        if (m.boroughs) goTo({ ...cityTarget(m.boroughs.bounds, "off", window.innerWidth) });
        setLoad({ phase: "ready", message: `Gerçek veri yüklendi: ${fmtInt(clusters.total_clusters)} küme · ${fmtInt(density.total_events)} olay (yoğunluk özeti)` });
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setLoad({ phase: "error", message: `Veri yüklenemedi: ${(e as Error).message}` });
        return;
      }
      try {
        const res = await fetch("models/registry.json", { signal: ctrl.signal });
        if (!res.ok) throw new Error(`Varlık kaydı bulunamadı (${res.status})`);
        const reg = (await res.json()) as AssetRegistry;
        const problems = validateRegistry(reg);
        if (problems.length) throw new Error(`Varlık kaydı geçersiz: ${problems.join("; ")}`);
        registryRef.current = reg;
        setRegistry(reg);
        addModelLayer(map, reg);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setInspectorError((e as Error).message);
      }
    });

    const onMove = () => setView({ zoom: map.getZoom(), bearing: map.getBearing(), center: [map.getCenter().lng, map.getCenter().lat] });
    let debounce: number | undefined;
    map.on("move", onMove);
    map.on("moveend", () => {
      onMove();
      ensureLazyLayers();
      window.clearTimeout(debounce);
      debounce = window.setTimeout(refreshViewport, 200);
    });
    map.on("error", (e) => {
      // Karo/glyph ağ hataları haritayı durdurmaz; kullanıcıya gösterilir. Diğer hatalar (ör. stil ifadesi)
      // sessizce yutulmaz: konsola yazılır.
      const msg = (e.error as Error | undefined)?.message ?? String(e.error);
      if (/Failed to fetch|NetworkError|ERR_|AJAXError/.test(msg)) setLoad({ phase: "error", message: "Harita karoları alınamadı (ağ). Kaza katmanları çalışmaya devam eder." });
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
      setLoad({ phase: "loading", message: "WebGL bağlamı kaybedildi; yeniden kuruluyor…" });
    });
    map.on("webglcontextrestored", () => {
      // MapLibre stili asenkron yeniden kurar (setStyle, diff: false); özel katmanlar geri gelmez.
      const rebuild = () => {
        addDataLayers(map);
        for (const [src, data] of Object.entries(dataCache.current)) setSourceData(map, src as never, data);
        applyVisibility(map, visRef.current);
        if (selectedRef.current) setSelected(map, selectedRef.current.cluster_id);
        const reg = registryRef.current;
        if (map.getLayer("city-models")) map.removeLayer("city-models");
        if (reg) addModelLayer(map, reg);
        lastPointsKey.current = "";
        refreshViewport();
        setLoad({ phase: "ready", message: "WebGL bağlamı geri yüklendi; 3D sahne yeniden kuruldu." });
      };
      if (map.isStyleLoaded()) rebuild();
      else map.once("style.load", rebuild);
    });

    window.__saferoute = {
      map,
      layer: () => layerRef.current,
      selected: () => selectedRef.current,
      visibility: () => visRef.current,
    };
    return () => {
      ctrl.abort();
      pointsAbort.current?.abort();
      map.remove();
      mapRef.current = null;
    };
  }, [addModelLayer, ensureLazyLayers, goTo, refreshViewport, selectCluster]);

  // ---------------------------------------------------------------- kullanıcı eylemleri
  const onBorough = (b: string | null) => {
    const bounds = metaRef.current?.boroughs?.bounds;
    if (!bounds) return;
    setBorough(b);
    goTo(b ? boroughTarget(b, bounds, motionRef.current, window.innerWidth) : cityTarget(bounds, motionRef.current, window.innerWidth));
  };

  const onToggle = (k: LayerKey) => {
    const v = toggleLayer(visRef.current, k);
    visRef.current = v;
    setVisibility(v);
    const map = mapRef.current;
    if (!map) return;
    applyVisibility(map, v);
    ensureLazyLayers();
    lastPointsKey.current = "";
    refreshViewport();
  };

  const onTheme = () => {
    const next: Theme = theme === "night" ? "day" : "night";
    setTheme(next);
    const map = mapRef.current;
    if (!map) return;
    for (const [layer, props] of Object.entries(themePaint(next))) {
      if (!map.getLayer(layer)) continue;
      for (const [prop, value] of Object.entries(props)) map.setPaintProperty(layer, prop as never, value as never);
    }
    map.setSky(themeSky(next));
    document.documentElement.dataset.theme = next;
  };

  const setMotion = (m: MotionLevel) => {
    motionRef.current = m;
    setMotionState(m);
    if (layerRef.current) layerRef.current.motion = m;
    mapRef.current?.triggerRepaint();
  };

  const onCamera = (a: CameraAction) => {
    const map = mapRef.current;
    if (!map) return;
    const duration = durationFor(motionRef.current, 450);
    switch (a) {
      case "zoomIn": return map.zoomIn({ duration });
      case "zoomOut": return map.zoomOut({ duration });
      case "rotL": return map.rotateTo(map.getBearing() - 30, { duration });
      case "rotR": return map.rotateTo(map.getBearing() + 30, { duration });
      case "pitchUp": return map.easeTo({ pitch: Math.min(78, map.getPitch() + 10), duration });
      case "pitchDown": return map.easeTo({ pitch: Math.max(0, map.getPitch() - 10), duration });
      case "north": return map.easeTo({ bearing: 0, duration });
      case "reset": return resetView();
    }
  };

  const updatePlacement = (p: InspectorPlacement | null) => {
    setPlacement(p);
    setInspectorError(null);
    sceneRef.current.inspector = p;
    const map = mapRef.current;
    if (p && map && map.getZoom() < 16.5) map.flyTo({ center: p.lngLat, zoom: 18.2, pitch: 60, duration: durationFor(motionRef.current, 1800), essential: true });
    layerRef.current?.setInspector(p).catch((e: Error) => setInspectorError(e.message));
  };

  const mapCenter: LngLat = view.center;

  return (
    <main className="relative w-full h-full" data-theme={theme}>
      {/* MapLibre CSS'i .maplibregl-map'e position:relative verir (katmansız CSS, Tailwind yardımcılarını ezer):
          konumlandırma sarmalayıcıda, harita kabı yalnızca tam boyut. */}
      <div className="absolute inset-0">
        <div ref={container} className="w-full h-full" data-testid="map" aria-label="New York 3D haritası" role="region" />
      </div>
      <TopBar load={load} theme={theme} onTheme={onTheme} motion={motion} onMotion={setMotion}
        onAssets={() => setAssetsOpen((o) => !o)} assetsOpen={assetsOpen} />
      <div className="absolute z-10 left-3 top-[84px] bottom-9 w-[300px] hidden md:flex flex-col gap-3 pointer-events-none">
        <SidePanel meta={meta} borough={borough} onBorough={onBorough} visibility={visibility} onToggle={onToggle} zoom={view.zoom} />
        <Legend viewport={viewport} />
      </div>
      {assetsOpen ? (
        <AssetInspector registry={registry} placement={placement} onChange={updatePlacement} error={inspectorError}
          onClose={() => setAssetsOpen(false)} mapCenter={mapCenter}
          onPlaceHere={() => placement && updatePlacement({ ...placement, lngLat: mapCenter })} />
      ) : (
        <ClusterPanel state={cluster} onClose={clearSelection} roadNote={roadNote}
          onFocus={() => cluster.status === "ready" && goTo(clusterTarget([cluster.detail.centroid_lon, cluster.detail.centroid_lat], cluster.detail.radius_p90_m, view.bearing, motionRef.current))} />
      )}
      <CameraControls onAction={onCamera} bearing={view.bearing}
        readout={`zoom ${view.zoom.toFixed(1)} · yön ${Math.round(((view.bearing % 360) + 360) % 360)}°${borough ? ` · ${BOROUGH_TR[borough]}` : ""}`} />
      {load.phase === "error" && !meta && (
        <div className="absolute inset-0 z-30 grid place-items-center bg-bg/70" role="alert" data-testid="fatal-error">
          <div className="panel p-5 max-w-md text-center space-y-3">
            <h2 className="font-display font-bold text-[17px]">Veri yüklenemedi</h2>
            <p className="text-[13px] text-muted">{load.message}</p>
            <button type="button" className="btn" onClick={() => window.location.reload()}>Yeniden dene</button>
          </div>
        </div>
      )}
    </main>
  );
}
