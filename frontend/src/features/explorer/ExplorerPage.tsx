// 3D Şehir Keşfi: Faz 4 harita motoru + filtreler, zaman oynatma, küme ayrıntısı ve sonuç kaynağı seçimi.
import { Box, FlaskConical, Inbox, Layers, Moon, PanelLeftClose, PanelLeftOpen, RotateCcw, SlidersHorizontal, Sun, Undo2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import { AssetInspector } from "../../components/AssetInspector";
import { CameraControls } from "../../components/CameraControls";
import { Legend, type ViewportInfo } from "../../components/Legend";
import type { Meta } from "../../lib/api";
import { BOROUGH_TR } from "../../lib/camera";
import { EMPTY_FILTERS, activeCount, applySlice, describe, sliceLabel, toQuery } from "../../lib/filters";
import { fmtInt, trLabel } from "../../lib/format";
import { POINT_MIN_ZOOM, type MotionLevel } from "../../lib/layers";
import type { LngLat } from "../../lib/geo";
import type { AssetRegistry } from "../../lib/registry";
import { useQuery } from "../../lib/query";
import type { RecordsSummary } from "../../lib/types";
import type { InspectorPlacement } from "../../map/threeLayer";
import { CityMap, type CityMapHandle, type ClusterState, type LoadState } from "./CityMap";
import { ClusterDetails } from "./ClusterDetails";
import { FilterPanel } from "./FilterPanel";
import { TimeControls } from "./TimeControls";
import { ViewPanel } from "./ViewPanel";

// Kompakt düzen (alttan açılan çekmeceler) < 1024 px: 768 px tablette masaüstü panelleri (320 + 340 px) haritayı ve
// zaman çubuğunu ezip kamera kontrolleriyle çakıştırıyordu (Faz 8 bulgusu).
const COMPACT_QUERY = "(max-width: 1023px)";
function useIsMobile() {
  const [m, setM] = useState(() => window.matchMedia(COMPACT_QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(COMPACT_QUERY);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return m;
}

/** Haritanın görünen kısmını ortalamak için panel boşlukları (≥ 1024 px: sol 332 px panel — daraltılmışsa yok —,
 *  sağ 352 px panel, alt zaman çubuğu). */
function padding(width: number, leftOpen: boolean) {
  return width < 1024 ? { top: 70, bottom: 150, left: 20, right: 20 } : { top: 76, bottom: 150, left: leftOpen ? 344 : 64, right: 364 };
}

export function ExplorerPage({ active }: { active: boolean }) {
  const mapApi = useRef<CityMapHandle>(null);
  const mobile = useIsMobile();
  const source = useApp((s) => s.source);
  const setSource = useApp((s) => s.setSource);
  const applied = useApp((s) => s.applied);
  const slice = useApp((s) => s.slice);
  const visibility = useApp((s) => s.visibility);
  const theme = useApp((s) => s.theme);
  const setTheme = useApp((s) => s.setTheme);
  const motion = useApp((s) => s.motion);
  const setMotion = useApp((s) => s.setMotion);
  const setBorough = useApp((s) => s.setBorough);
  const borough = useApp((s) => s.borough);
  const focus = useApp((s) => s.focus);
  const leftPanel = useApp((s) => s.leftPanel);
  const setLeftPanel = useApp((s) => s.setLeftPanel);
  const mobileSheet = useApp((s) => s.mobileSheet);
  const setMobileSheet = useApp((s) => s.setMobileSheet);
  const setRoute = useApp((s) => s.setRoute);
  const navCollapsed = useApp((s) => s.navCollapsed);
  const toggleNav = useApp((s) => s.toggleNav);
  const resetFilters = useApp((s) => s.resetFilters);

  const [meta, setMeta] = useState<Meta | null>(null);
  const [load, setLoad] = useState<LoadState>({ phase: "loading", message: "Harita ve doğrulanmış katmanlar yükleniyor…" });
  const [view, setView] = useState({ zoom: 10, bearing: 0, center: [-73.95, 40.7] as LngLat });
  const [cluster, setCluster] = useState<ClusterState>({ status: "idle" });
  const [viewport, setViewport] = useState<ViewportInfo>({ state: "zoom-in", minZoom: POINT_MIN_ZOOM });
  const [registry, setRegistry] = useState<AssetRegistry | null>(null);
  const [assetsOpen, setAssetsOpen] = useState(false);
  const [placement, setPlacement] = useState<InspectorPlacement | null>(null);
  const [inspectorError, setInspectorError] = useState<string | null>(null);
  const [roadNote, setRoadNote] = useState<string | null>(null);
  const [layerCounts, setLayerCounts] = useState<{ clusters: number; total: number; label: string } | null>(null);
  // Faz 8B: sol panel açıkça daraltılabilir (3D şehir ana odak); işlev kaldırılmaz, tek tıkla geri açılır.
  const [leftOpen, setLeftOpen] = useState(true);
  const mapPadding = useCallback((w: number) => padding(w, leftOpen), [leftOpen]);

  // Harita alanı en büyük olsun: keşif ekranına ilk girişte kenar çubuğu daraltılır.
  const collapsedOnce = useRef(false);
  useEffect(() => {
    if (active && !collapsedOnce.current) {
      collapsedOnce.current = true;
      if (!navCollapsed) toggleNav();
    }
  }, [active, navCollapsed, toggleNav]);

  const resultMode = source.kind === "result";
  // Sonuç modunda kayıt filtreleri uygulanmaz (sonucun kendi kapsamı vardır); yalnızca zaman dilimi süzülür.
  const effective = useMemo(() => applySlice(resultMode ? EMPTY_FILTERS : applied, slice), [applied, slice, resultMode]);
  const setSlice = useApp((s) => s.setSlice);
  const setPlaying = useApp((s) => s.setPlaying);
  const sourceId = source.kind === "model" ? "model" : source.id;
  const prevSource = useRef(sourceId);
  useEffect(() => {
    // Farklı deneyin zaman kapsamı farklıdır: kaynak değişince dilim ve oynatma sıfırlanır
    if (prevSource.current !== sourceId) {
      prevSource.current = sourceId;
      setPlaying(false);
      setSlice(null);
    }
  }, [sourceId, setPlaying, setSlice]);
  const filterQuery = toQuery(effective);
  const nFilters = activeCount(applied);
  const filtersTr = describe(applied, { borough: (b) => BOROUGH_TR[b] ?? b, vehicle: trLabel });

  // Genel bakış / laboratuvardan "haritada aç": istenen kümeyi seç
  // Harita verisi (merkezler, model meta verisi) yüklenmeden seçim yapılmaz: aksi hâlde deney kimliği boş gider (409)
  // ve henüz eklenmemiş kaynaklara durum yazılır. Veri hazır olunca bu etki yeniden çalışır.
  const dataReady = layerCounts !== null;
  useEffect(() => {
    if (!focus || !active || !dataReady) return;
    const wanted = focus.sourceId === "model" ? "model" : focus.sourceId;
    const cur = source.kind === "model" ? "model" : source.id;
    if (wanted !== cur) return; // kaynak değişimi önce uygulanır, sonra bu etki yeniden çalışır
    const t = window.setTimeout(() => mapApi.current?.selectCluster(focus.clusterId), 300);
    return () => window.clearTimeout(t);
  }, [focus, active, source, dataReady]);

  useEffect(() => {
    if (cluster.status !== "idle" && mobile) setMobileSheet("details");
  }, [cluster.status, mobile, setMobileSheet]);

  const onBorough = useCallback((b: string | null) => {
    setBorough(b);
    mapApi.current?.goBorough(b);
  }, [setBorough]);

  const updatePlacement = (p: InspectorPlacement | null) => {
    setPlacement(p);
    setInspectorError(null);
    mapApi.current?.setInspector(p);
  };

  const mode = resultMode ? "result" : filterQuery ? "filtered" : "model";
  // Boş sonuç: filtre (veya zaman dilimi) hiçbir kümeye kayıt düşürmüyorsa harita boş kalır; neden açıkça yazılır.
  const emptyFiltered = mode === "filtered" && load.phase === "ready" && layerCounts?.clusters === 0;
  const emptySummary = useQuery<RecordsSummary>(emptyFiltered ? `/api/records/summary?${filterQuery}` : null);
  const readout = `zoom ${view.zoom.toFixed(1)} · yön ${Math.round(((view.bearing % 360) + 360) % 360)}°${borough ? ` · ${BOROUGH_TR[borough]}` : ""}`;
  const dot = load.phase === "ready" ? "bg-success" : load.phase === "error" ? "bg-hotspot" : "bg-warning animate-pulse";

  const leftContent = (
    <Tabs value={leftPanel} onValueChange={(v) => setLeftPanel(v as "view" | "filters")} className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-1.5">
        <TabsList className="grid min-w-0 flex-1 grid-cols-2 bg-surface-2">
          <TabsTrigger value="view" data-testid="tab-view"><Layers /> Görünüm</TabsTrigger>
          <TabsTrigger value="filters" data-testid="tab-filters">
            <SlidersHorizontal /> Filtreler {nFilters > 0 && <Badge className="ml-0.5 h-4 min-w-4 px-1 text-[10px] bg-warning text-primary-foreground">{nFilters}</Badge>}
          </TabsTrigger>
        </TabsList>
        {!mobile && (
          <Button size="icon-sm" variant="ghost" onClick={() => setLeftOpen(false)} aria-label="Paneli daralt" title="Paneli daralt (harita alanını genişletir)"
            aria-expanded aria-controls="explorer-left-panel" data-testid="left-collapse"><PanelLeftClose /></Button>
        )}
      </div>
      <TabsContent value="view" className="min-h-0 flex-1 overflow-y-auto scroll-thin space-y-4 pr-1 mt-0">
        <ViewPanel meta={meta} onBorough={onBorough} zoom={view.zoom} layerCounts={layerCounts} />
        <div className="border-t border-line pt-3"><Legend viewport={viewport} zoom={view.zoom} /></div>
      </TabsContent>
      <TabsContent value="filters" className="min-h-0 flex-1 flex flex-col mt-0">
        <FilterPanel onStartLab={() => setRoute("lab")} />
      </TabsContent>
    </Tabs>
  );

  const rightContent = assetsOpen ? (
    <AssetInspector registry={registry} placement={placement} onChange={updatePlacement} error={inspectorError}
      onClose={() => setAssetsOpen(false)} mapCenter={view.center}
      onPlaceHere={() => placement && updatePlacement({ ...placement, lngLat: mapApi.current?.center() ?? view.center })} />
  ) : (
    <ClusterDetails state={cluster} roadNote={roadNote} onClose={() => { mapApi.current?.clearSelection(); setMobileSheet(null); }}
      onFocus={() => mapApi.current?.focusSelected()} />
  );

  return (
    <div className="relative h-full w-full overflow-hidden bg-bg">
      <CityMap ref={mapApi} active={active} source={source} filterQuery={filterQuery} visibility={visibility} theme={theme} motion={motion}
        padding={mapPadding} onMeta={setMeta} onLoad={setLoad} onViewport={setViewport} onView={setView} onCluster={setCluster}
        onRoadNote={setRoadNote} onRegistry={setRegistry} onInspectorError={setInspectorError} onLayerCounts={setLayerCounts} />

      {/* Üst araç çubuğu */}
      <div className="absolute z-20 left-3 right-3 top-3 flex items-start gap-2 pointer-events-none">
        <div role="status" aria-live="polite" data-testid="load-status" data-phase={load.phase}
          className="panel pointer-events-auto hidden lg:flex items-center gap-2 px-3 h-10 text-[12.5px] max-w-[340px] shrink-0">
          <span className={cn("size-2 rounded-full shrink-0", dot)} aria-hidden />
          <span className="truncate">{load.message}</span>
        </div>
        <ModeBanner mode={mode} source={source} filters={filtersTr} sliceText={slice ? sliceLabel(slice) : null}
          onBack={() => setSource({ kind: "model" })} onLab={() => setRoute("lab")} />
        <div className="flex-1" />
        <div className="panel pointer-events-auto flex items-center gap-1 p-1 shrink-0">
          <Button size="sm" variant={leftPanel === "filters" ? "secondary" : "ghost"} className="hidden lg:inline-flex"
            onClick={() => {
              // Daraltılmış panelde "Filtreler" paneli açar ve filtre sekmesini gösterir
              if (!leftOpen) { setLeftOpen(true); setLeftPanel("filters"); return; }
              setLeftPanel(leftPanel === "filters" ? "view" : "filters");
            }} aria-pressed={leftOpen && leftPanel === "filters"} data-testid="toolbar-filters">
            <SlidersHorizontal /> Filtreler{nFilters > 0 ? ` (${nFilters})` : ""}
          </Button>
          <Button size="sm" variant="ghost" className="lg:hidden" onClick={() => setMobileSheet("panel")} data-testid="mobile-panel">
            <Layers /> Katmanlar{nFilters > 0 ? ` · ${nFilters}` : ""}
          </Button>
          <Button size="sm" variant={assetsOpen ? "secondary" : "ghost"} aria-pressed={assetsOpen} onClick={() => setAssetsOpen((o) => !o)} data-testid="assets-toggle" className="hidden sm:inline-flex">
            <Box /> 3D varlıklar
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setTheme(theme === "night" ? "day" : "night")} data-testid="theme-toggle"
            aria-label={theme === "night" ? "Gündüz moduna geç" : "Gece moduna geç"}>
            {theme === "night" ? <Moon /> : <Sun />} <span className="hidden sm:inline">{theme === "night" ? "Gece" : "Gündüz"}</span>
          </Button>
          <label className="sr-only" htmlFor="motion">Animasyon düzeyi</label>
          <select id="motion" data-testid="motion-select" value={motion} onChange={(e) => setMotion(e.target.value as MotionLevel)}
            className="h-8 rounded-md bg-transparent px-2 text-[12.5px] font-semibold text-foreground hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-ring outline-none hidden sm:block" title="Animasyon düzeyi">
            <option value="full">Animasyon: tam</option>
            <option value="reduced">Animasyon: azaltılmış</option>
            <option value="off">Animasyon: kapalı</option>
          </select>
        </div>
      </div>

      {/* Masaüstü: sol panel (daraltılabilir) */}
      {!mobile && leftOpen && (
        <aside id="explorer-left-panel" className="panel absolute z-10 left-3 top-[64px] bottom-8 w-[320px] flex flex-col p-3" aria-label="Görünüm ve filtreler" data-testid="left-panel">
          {leftContent}
        </aside>
      )}
      {!mobile && !leftOpen && (
        <div className="panel absolute z-10 left-3 top-[64px] flex flex-col items-center gap-1 p-1" data-testid="left-collapsed">
          <Button size="icon-sm" variant="ghost" onClick={() => setLeftOpen(true)} aria-label="Görünüm ve filtreler panelini aç" title="Paneli aç"
            aria-expanded={false} aria-controls="explorer-left-panel" data-testid="left-expand"><PanelLeftOpen /></Button>
          <Button size="icon-sm" variant="ghost" onClick={() => { setLeftOpen(true); setLeftPanel("view"); }} aria-label="Katmanlar" title="Katmanlar"><Layers /></Button>
          <Button size="icon-sm" variant="ghost" onClick={() => { setLeftOpen(true); setLeftPanel("filters"); }} aria-label={`Filtreler${nFilters ? ` (${nFilters} etkin)` : ""}`} title="Filtreler"
            className={cn(nFilters > 0 && "text-warning")}><SlidersHorizontal /></Button>
        </div>
      )}
      {/* Masaüstü: sağ panel */}
      {!mobile && (
        <aside className={cn("panel absolute z-10 right-3 top-[64px] w-[340px] overflow-y-auto scroll-thin enter",
          cluster.status === "idle" && !assetsOpen ? "" : "bottom-[150px]")} aria-label={assetsOpen ? "3D varlık inceleyici" : "Seçilen küme"}
          data-testid="right-panel">
          {rightContent}
        </aside>
      )}
      {/* Alt: zaman + kamera */}
      <div className={cn("absolute z-10 flex items-end gap-2", mobile ? "bottom-14 left-2 right-2 flex-col items-stretch" : cn("bottom-8 right-3", leftOpen ? "left-[344px]" : "left-[64px]"))}>
        <div className="min-w-0 flex-1">
          <TimeControls compact={mobile} disabledReason={null} resultId={source.kind === "result" ? source.id : null} />
        </div>
        <div className={cn(mobile && "self-center")}>
          <CameraControls compact={mobile} bearing={view.bearing} readout={readout} onAction={(a) => {
            if (a === "reset") setBorough(null);
            mapApi.current?.camera(a);
          }} />
        </div>
      </div>

      {emptyFiltered && (
        <div className="absolute z-20 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(440px,calc(100%-24px))]" role="status" aria-live="polite" data-testid="empty-filter-result">
          <div className="panel p-4 space-y-2.5 text-[12.5px] leading-snug">
            <div className="flex items-center gap-2 font-display font-bold text-[14px]"><Inbox className="size-4 text-warning" aria-hidden /> Bu filtreyle haritada küme yok</div>
            <p className="text-muted-foreground">
              {emptySummary.data && emptyFiltered
                ? emptySummary.data.n_events === 0
                  ? "Seçilen filtre birleşimine uyan kaza kaydı bulunmuyor."
                  : `Filtreye uyan ${fmtInt(emptySummary.data.n_events)} kayıt var; ancak hiçbiri seçili modelin bir kümesine düşmüyor (tümü gürültü −1).`
                : "Filtreye uyan kayıt sayısı sorgulanıyor…"}{" "}
              Küme etiketleri değiştirilmedi; filtreyi genişletin veya sıfırlayın.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={resetFilters} data-testid="empty-reset"><RotateCcw /> Filtreleri sıfırla</Button>
              <Button size="sm" variant="ghost" onClick={() => { setLeftPanel("filters"); if (mobile) setMobileSheet("panel"); }}><SlidersHorizontal /> Filtreleri düzenle</Button>
            </div>
          </div>
        </div>
      )}

      {load.phase === "error" && !meta && (
        <div className="absolute inset-0 z-30 grid place-items-center bg-bg/70 p-4" role="alert" data-testid="fatal-error">
          <div className="panel p-5 max-w-md text-center space-y-3">
            <h2 className="font-display font-bold text-[17px]">Veri yüklenemedi</h2>
            <p className="text-[13px] text-muted-foreground">{load.message}</p>
            <Button onClick={() => window.location.reload()}>Yeniden dene</Button>
          </div>
        </div>
      )}

      {/* Mobil çekmeceler: masaüstü paneller küçültülmez, alttan açılan sayfalara dönüşür */}
      {mobile && (
        <>
          <Sheet open={mobileSheet === "panel"} onOpenChange={(o) => setMobileSheet(o ? "panel" : null)}>
            <SheetContent side="bottom" className="h-[78svh] bg-surface border-line p-3 flex flex-col">
              <SheetHeader className="p-0">
                <SheetTitle className="text-[15px]">Görünüm ve filtreler</SheetTitle>
                <SheetDescription className="text-[12px]">Katmanlar, ilçe kamerası ve kayıt filtreleri</SheetDescription>
              </SheetHeader>
              <label className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 text-[12.5px] font-semibold">
                Animasyon düzeyi
                <select data-testid="mobile-motion-select" value={motion} onChange={(e) => setMotion(e.target.value as MotionLevel)}
                  className="h-8 rounded-md bg-surface-2 px-2 text-[12.5px] font-semibold text-foreground focus-visible:ring-2 focus-visible:ring-ring outline-none">
                  <option value="full">Tam</option>
                  <option value="reduced">Azaltılmış</option>
                  <option value="off">Kapalı</option>
                </select>
              </label>
              {leftContent}
            </SheetContent>
          </Sheet>
          <Sheet open={mobileSheet === "details"} onOpenChange={(o) => { if (!o) { setMobileSheet(null); mapApi.current?.clearSelection(); } }}>
            <SheetContent side="bottom" className="max-h-[70svh] overflow-y-auto bg-surface border-line p-0">
              <SheetHeader className="sr-only"><SheetTitle>Küme ayrıntısı</SheetTitle><SheetDescription>Seçilen kümenin gerçek kayıt profili</SheetDescription></SheetHeader>
              {rightContent}
            </SheetContent>
          </Sheet>
        </>
      )}
    </div>
  );
}

function ModeBanner({ mode, source, filters, sliceText, onBack, onLab }: {
  mode: "model" | "filtered" | "result"; source: ReturnType<typeof useApp.getState>["source"]; filters: string[];
  sliceText: string | null; onBack: () => void; onLab: () => void;
}) {
  if (mode === "model" && !sliceText) return null;
  return (
    <div className={cn("panel pointer-events-auto min-w-0 max-w-[560px] px-3 py-2 text-[12.5px] leading-snug",
      mode === "result" ? "border-warning/50" : "border-primary/40")} data-testid="mode-banner" data-mode={mode}>
      {mode === "result" && source.kind === "result" ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge variant="outline" className="border-warning/60 text-warning">{source.dynamic ? "Dinamik analiz sonucu" : "Kayıtlı deney"}</Badge>
          <span className="truncate"><b className="font-semibold">{source.algorithm.toUpperCase()}</b> · {source.label}</span>
          <Button size="xs" variant="ghost" onClick={onBack}><Undo2 /> Seçili model</Button>
          <span className="basis-full text-[11.5px] text-subtle truncate" data-testid="result-scope-note">
            Sonucun kendi veri kapsamı gösterilir; kayıt filtreleri bu görünüme uygulanmaz{sliceText ? ` · Zaman dilimi: ${sliceText} (üyelik sabit, yeniden kümeleme yok)` : ""}
          </span>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge variant="outline" className="border-primary/60 text-primary">Filtrelenmiş kayıtlar</Badge>
          <span className="text-muted-foreground">Küme etiketleri tam veri modelinden · <b className="text-foreground font-semibold">yeniden kümeleme yapılmadı</b></span>
          <Button size="xs" variant="ghost" onClick={onLab} data-testid="banner-to-lab"><FlaskConical /> Yeni kümeleme…</Button>
          {(filters.length > 0 || sliceText) && (
            <span className="basis-full text-[11.5px] text-subtle truncate">{[...filters, ...(sliceText ? [`Zaman dilimi: ${sliceText}`] : [])].join(" · ")}</span>
          )}
        </div>
      )}
    </div>
  );
}
