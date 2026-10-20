// Uygulama durumu (Zustand). Harita motorunun kendi iç durumu (kamera, kaynaklar) CityMap'te kalır;
// burada yalnızca ekranlar arasında paylaşılan kararlar tutulur.
import { create } from "zustand";
import { defaultVisibility, toggleLayer, type LayerKey, type MotionLevel, type Visibility } from "../lib/layers";
import { EMPTY_FILTERS, normalize, type FilterState, type Granularity, type TimeSlice } from "../lib/filters";
import type { Theme } from "../map/style";

export type Route = "overview" | "explorer" | "lab" | "models" | "data";

export const ROUTES: { id: Route; hash: string; label: string }[] = [
  { id: "overview", hash: "genel-bakis", label: "Genel bakış" },
  { id: "explorer", hash: "kesif", label: "3D Şehir Keşfi" },
  { id: "lab", hash: "laboratuvar", label: "Kümeleme Laboratuvarı" },
  { id: "models", hash: "modeller", label: "Model Karşılaştırma" },
  { id: "data", hash: "veri", label: "Veri Gezgini" },
];

export function routeFromHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "").split("?")[0];
  return ROUTES.find((r) => r.hash === h)?.id ?? "overview";
}

export function hashFor(route: Route): string {
  return `#/${ROUTES.find((r) => r.id === route)!.hash}`;
}

/** Haritada gösterilen kümelerin kaynağı. "model" = seçili Faz 3 DBSCAN (tam veri etiketleri);
 *  "result" = kayıtlı bir Faz 3 deneyi veya tamamlanmış laboratuvar işi (kimlik: deney kimliği / "lab-<iş>"). */
export type MapSource =
  | { kind: "model" }
  | { kind: "result"; id: string; label: string; algorithm: string; dynamic: boolean };

export interface FocusRequest { sourceId: string | "model"; clusterId: number; nonce: number }

interface AppState {
  route: Route;
  navCollapsed: boolean;
  draft: FilterState;
  applied: FilterState;
  source: MapSource;
  visibility: Visibility;
  theme: Theme;
  motion: MotionLevel;
  borough: string | null;
  focus: FocusRequest | null;
  slice: TimeSlice | null;
  granularity: Granularity;
  playing: boolean;
  activeJobId: string | null;
  leftPanel: "view" | "filters";
  mobileSheet: "panel" | "details" | "nav" | null;

  setRoute: (r: Route) => void;
  toggleNav: () => void;
  setDraft: (patch: Partial<FilterState>) => void;
  applyDraft: () => void;
  resetFilters: () => void;
  setApplied: (f: FilterState) => void;
  setSource: (s: MapSource) => void;
  toggleLayer: (k: LayerKey) => void;
  setVisibility: (v: Visibility) => void;
  setTheme: (t: Theme) => void;
  setMotion: (m: MotionLevel) => void;
  setBorough: (b: string | null) => void;
  requestFocus: (sourceId: string | "model", clusterId: number) => void;
  setSlice: (s: TimeSlice | null) => void;
  setGranularity: (g: Granularity) => void;
  setPlaying: (p: boolean) => void;
  setActiveJob: (id: string | null) => void;
  setLeftPanel: (p: "view" | "filters") => void;
  setMobileSheet: (s: AppState["mobileSheet"]) => void;
}

function initialMotion(): MotionLevel {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "reduced" : "full";
}

export const useApp = create<AppState>((set, get) => ({
  route: typeof window !== "undefined" ? routeFromHash(window.location.hash) : "overview",
  navCollapsed: typeof window !== "undefined" ? window.innerWidth < 1280 : false,
  draft: EMPTY_FILTERS,
  applied: EMPTY_FILTERS,
  source: { kind: "model" },
  visibility: defaultVisibility(),
  theme: "night",
  motion: initialMotion(),
  borough: null,
  focus: null,
  slice: null,
  granularity: "year",
  playing: false,
  activeJobId: null,
  leftPanel: "view",
  mobileSheet: null,

  setRoute: (route) => {
    if (typeof window !== "undefined" && routeFromHash(window.location.hash) !== route) window.location.hash = hashFor(route);
    set({ route, mobileSheet: null });
  },
  toggleNav: () => set({ navCollapsed: !get().navCollapsed }),
  setDraft: (patch) => set({ draft: { ...get().draft, ...patch } }),
  applyDraft: () => set({ applied: normalize(get().draft) }),
  resetFilters: () => set({ draft: EMPTY_FILTERS, applied: EMPTY_FILTERS, slice: null, playing: false }),
  setApplied: (f) => set({ applied: normalize(f), draft: normalize(f) }),
  setSource: (source) => set({ source }),
  toggleLayer: (k) => set({ visibility: toggleLayer(get().visibility, k) }),
  setVisibility: (visibility) => set({ visibility }),
  setTheme: (theme) => set({ theme }),
  setMotion: (motion) => {
    document.documentElement.dataset.motion = motion;
    set({ motion });
  },
  setBorough: (borough) => set({ borough }),
  requestFocus: (sourceId, clusterId) => set({ focus: { sourceId, clusterId, nonce: Date.now() } }),
  setSlice: (slice) => set({ slice }),
  setGranularity: (granularity) => set({ granularity, slice: null, playing: false }),
  setPlaying: (playing) => set({ playing }),
  setActiveJob: (activeJobId) => set({ activeJobId }),
  setLeftPanel: (leftPanel) => set({ leftPanel }),
  setMobileSheet: (mobileSheet) => set({ mobileSheet }),
}));
