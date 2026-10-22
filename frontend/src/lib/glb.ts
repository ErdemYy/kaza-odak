// GLB yükleme: başlık doğrulaması, meshopt çözücü, hata sınıflandırması ve ArrayBuffer önbelleği
// (WebGL bağlam kaybından sonra GPU nesneleri yeniden kurulurken ağdan tekrar indirilmez).
import { LinearFilter, LinearMipmapLinearFilter, type Mesh, type Object3D, type Texture } from "three";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";

export class ModelLoadError extends Error {
  constructor(public url: string, public reason: "network" | "not-found" | "invalid" | "parse", message: string) {
    super(message);
  }
}

const GLB_MAGIC = 0x46546c67; // "glTF"

/** İkili glTF 2.0 başlığını doğrular (sihirli sayı, sürüm, toplam uzunluk, JSON parçası). */
export function validateGlbHeader(buf: ArrayBuffer): void {
  if (buf.byteLength < 20) throw new Error("dosya çok kısa (GLB başlığı yok)");
  const v = new DataView(buf);
  if (v.getUint32(0, true) !== GLB_MAGIC) throw new Error("GLB sihirli sayısı yok (glTF ikili dosyası değil)");
  if (v.getUint32(4, true) !== 2) throw new Error(`desteklenmeyen glTF sürümü ${v.getUint32(4, true)}`);
  if (v.getUint32(8, true) !== buf.byteLength) throw new Error("uzunluk alanı dosya boyutuyla uyuşmuyor (kesik/bozuk dosya)");
  if (v.getUint32(16, true) !== 0x4e4f534a) throw new Error("ilk parça JSON değil");
}

const bufferCache = new Map<string, Promise<ArrayBuffer>>();

export function fetchGlb(url: string, fetcher: typeof fetch = fetch): Promise<ArrayBuffer> {
  let p = bufferCache.get(url);
  if (!p) {
    p = (async () => {
      let res: Response;
      try {
        res = await fetcher(url);
      } catch (e) {
        throw new ModelLoadError(url, "network", `Model indirilemedi: ${(e as Error).message}`);
      }
      if (!res.ok) throw new ModelLoadError(url, "not-found", `Model bulunamadı (${res.status}): ${url}`);
      const buf = await res.arrayBuffer();
      try {
        validateGlbHeader(buf);
      } catch (e) {
        throw new ModelLoadError(url, "invalid", `Geçersiz GLB: ${(e as Error).message}`);
      }
      return buf;
    })();
    bufferCache.set(url, p);
    p.catch(() => bufferCache.delete(url)); // hatalı yüklemeler önbellekte kalmaz
  }
  return p;
}

let loaderPromise: Promise<{ parse: (buf: ArrayBuffer) => Promise<GLTF> }> | null = null;

async function loader() {
  loaderPromise ??= (async () => {
    const [{ GLTFLoader }, { MeshoptDecoder }] = await Promise.all([
      import("three/examples/jsm/loaders/GLTFLoader.js"),
      import("three/examples/jsm/libs/meshopt_decoder.module.js"),
    ]);
    const l = new GLTFLoader();
    l.setMeshoptDecoder(MeshoptDecoder);
    return { parse: (buf: ArrayBuffer) => l.parseAsync(buf, "") };
  })();
  return loaderPromise;
}

/** GLB'yi indirir/doğrular ve Three.js sahnesine çözer. */
export async function loadGlb(url: string): Promise<GLTF> {
  const buf = await fetchGlb(url);
  try {
    return await (await loader()).parse(buf.slice(0));
  } catch (e) {
    throw new ModelLoadError(url, "parse", `GLB çözümlenemedi: ${(e as Error).message}`);
  }
}

/**
 * Faz 8B: Kenney dokuları NEAREST örnekleme ile gelir (mag 9728, min 9984). Bazı UV köşeleri tam texel sınırına oturur
 * (taksi: 6 köşe, ön plaka); en yakın örneklemede kayan nokta yuvarlaması bu yüzeylerde siyah-beyaz piksel gürültüsü
 * üretir. Doku VERİSİ değiştirilmez; yalnızca örnekleme doğrusal + mipmap yapılır. Döndürür: güncellenen doku sayısı.
 */
export function smoothTextureSampling(root: Object3D): number {
  const seen = new Set<Texture>();
  root.traverse((o) => {
    const mats = (o as Mesh).material;
    for (const m of mats ? (Array.isArray(mats) ? mats : [mats]) : []) {
      const t = (m as unknown as { map?: Texture | null }).map;
      if (!t || seen.has(t)) continue;
      seen.add(t);
      t.magFilter = LinearFilter;
      t.minFilter = LinearMipmapLinearFilter;
      t.needsUpdate = true;
    }
  });
  return seen.size;
}
