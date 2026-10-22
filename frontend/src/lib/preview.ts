// GLB önizleyici için saf yardımcılar (kadraja sığdırma, kaynak temizliği). Three.js sahnesinden bağımsız test edilir.
import type * as THREE from "three";

/** Sınırlayıcı küre yarıçapı r olan modelin tamamını dikey görüş açısı fovDeg ve en/boy oranı aspect olan perspektif
 *  kamerada kadraja sığdıran uzaklık (kenar payı margin). Dar tuvalde yatay görüş açısı sınırlayıcıdır. */
export function fitDistance(radius: number, fovDeg: number, aspect: number, margin = 1.18): number {
  const vFov = (fovDeg * Math.PI) / 180;
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * Math.max(aspect, 1e-3));
  const limiting = Math.min(vFov, hFov);
  return (Math.max(radius, 1e-3) / Math.sin(limiting / 2)) * margin;
}

type Disposable = { dispose: () => void };
const TEXTURE_KEYS = ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap", "alphaMap", "bumpMap", "lightMap", "envMap"] as const;

/** Nesne ağacındaki TÜM geometri, malzeme ve dokuları serbest bırakır (önizleyici bunların tek sahibidir).
 *  Döndürür: serbest bırakılan benzersiz kaynak sayıları. */
export function disposeObject(root: THREE.Object3D): { geometries: number; materials: number; textures: number } {
  const geometries = new Set<Disposable>();
  const materials = new Set<Disposable>();
  const textures = new Set<Disposable>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry);
    const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
    for (const m of mats) {
      materials.add(m);
      for (const k of TEXTURE_KEYS) {
        const t = (m as unknown as Record<string, Disposable | null | undefined>)[k];
        if (t && typeof t.dispose === "function") textures.add(t);
      }
    }
  });
  root.removeFromParent();
  for (const set of [textures, materials, geometries]) for (const x of set) x.dispose();
  return { geometries: geometries.size, materials: materials.size, textures: textures.size };
}
