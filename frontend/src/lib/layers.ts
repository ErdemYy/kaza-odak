// Harita katmanı tanımları ve görünürlük kuralları (saf fonksiyonlar; birim testli).

export type LayerKey = "boroughs" | "density" | "centroids" | "geometries" | "clustered" | "noise" | "buildings" | "models";

export interface LayerDef {
  key: LayerKey;
  label: string;
  hint: string;
  minZoom: number;
  maxZoom: number;
  defaultOn: boolean;
}

/** Zoom düşükken özetler, yüksekken ayrıntılı noktalar (sunucu bbox sorgusu). */
export const LAYERS: LayerDef[] = [
  { key: "boroughs", label: "İlçe sınırları", hint: "Resmî DCP sınırları (gthc-hcne)", minZoom: 0, maxZoom: 24, defaultOn: true },
  { key: "density", label: "Yoğunluk", hint: "Gösterilen kapsamdaki olaylar; sunucu tarafı ızgara özeti", minZoom: 0, maxZoom: 15, defaultOn: true },
  { key: "centroids", label: "Küme merkezleri", hint: "Gösterilen modelin veya sonucun küme merkezleri", minZoom: 0, maxZoom: 24, defaultOn: true },
  { key: "geometries", label: "Küme geometrileri", hint: "Üye konumların dışbükey zarfı; gerçek yoğunluk sınırı değildir", minZoom: 12, maxZoom: 24, defaultOn: true },
  { key: "clustered", label: "Kümelenmiş noktalar", hint: "Görünen alandaki konumlar (zoom ≥ 15)", minZoom: 15, maxZoom: 24, defaultOn: true },
  { key: "noise", label: "Gürültü noktaları", hint: "Kümeye atanmayan konumlar (−1), zoom ≥ 15", minZoom: 15, maxZoom: 24, defaultOn: false },
  { key: "buildings", label: "3D binalar", hint: "OSM bina yükseklikleri", minZoom: 13, maxZoom: 24, defaultOn: true },
  { key: "models", label: "3D modeller", hint: "Seçili küme çevresinde temsili sahne", minZoom: 14, maxZoom: 24, defaultOn: true },
];

export const POINT_MIN_ZOOM = 15;

export type Visibility = Record<LayerKey, boolean>;

export function defaultVisibility(): Visibility {
  return Object.fromEntries(LAYERS.map((l) => [l.key, l.defaultOn])) as Visibility;
}

export function toggleLayer(v: Visibility, key: LayerKey): Visibility {
  return { ...v, [key]: !v[key] };
}

/** Katman kullanıcı tarafından açık mı VE geçerli zoom aralığında mı? */
export function isActive(v: Visibility, key: LayerKey, zoom: number): boolean {
  const def = LAYERS.find((l) => l.key === key);
  if (!def) return false;
  return v[key] && zoom >= def.minZoom && zoom <= def.maxZoom;
}

/** Nokta katmanı için hangi tür sorgulanmalı (ikisi de kapalıysa null: istek yapılmaz). */
export function pointQueryKind(v: Visibility, zoom: number): "clustered" | "noise" | "all" | null {
  const c = isActive(v, "clustered", zoom);
  const n = isActive(v, "noise", zoom);
  if (c && n) return "all";
  if (c) return "clustered";
  if (n) return "noise";
  return null;
}

/** Yoğunluk ızgarası hücre boyu: şehir ölçeğinde 1 km, mahalle ölçeğinde 250 m. */
export function densityCell(zoom: number): 1000 | 250 {
  return zoom >= 12 ? 250 : 1000;
}

export type MotionLevel = "full" | "reduced" | "off";
