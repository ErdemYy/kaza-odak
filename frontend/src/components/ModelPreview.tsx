// GLB model önizleyicisi (Faz 8B). Harita sahnesinden BAĞIMSIZ, küçük bir WebGL bağlamı: harita bağlamının durumuna,
// derinlik tamponuna ve GPU kaynaklarına dokunmaz. GLB ikili verisi lib/glb.ts önbelleğinden gelir (aynı model ağdan
// yeniden indirilmez); çözümlenen geometri/malzeme/dokular yalnızca önizleyiciye aittir ve model değişince ya da panel
// kapanınca serbest bırakılır. Çizim istek üzerinedir (kamera hareketsizken GPU boşta).
import { RotateCcw, RotateCw, Scan, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Button } from "@/components/ui/button";
import { fmtNum } from "../lib/format";
import { loadGlb, smoothTextureSampling } from "../lib/glb";
import { disposeObject, fitDistance } from "../lib/preview";
import type { AssetRecord } from "../lib/registry";

const FOV = 32;
const HOME_DIR = new THREE.Vector3(1, 0.55, 1.25).normalize(); // ön-sağ-üst üç çeyrek görünüş

/** Test/denetim kancası: canlı önizleyici sayısı ve son temizlikte serbest bırakılan / GPU'da kalan kaynaklar. */
interface PreviewDebug {
  live: number; created: number; destroyed: number; baseline?: { geometries: number; textures: number };
  lastDispose: { geometries: number; textures: number; gpuGeometriesLeft: number; gpuTexturesLeft: number; afterRenderer: { geometries: number; textures: number }; contextLost: boolean } | null;
  state?: () => { distance: number; fitDistance: number; radius: number; model: string | null; frames: number; textureSlots: string[]; memory: { geometries: number; textures: number } };
  action?: (a: PreviewAction) => void;
}
declare global {
  interface Window { __saferoutePreview?: PreviewDebug }
}
const debug = (): PreviewDebug => (window.__saferoutePreview ??= { live: 0, created: 0, destroyed: 0, lastDispose: null });

type PreviewAction = "zoomIn" | "zoomOut" | "rotL" | "rotR" | "reset";

interface Engine {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls;
  grid: THREE.GridHelper | null; model: THREE.Object3D | null;
  home: { pos: THREE.Vector3; target: THREE.Vector3; fit: number; radius: number };
  frame: number; frames: number; request: () => void;
}

export function ModelPreview({ record }: { record: AssetRecord }) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const engine = useRef<Engine | null>(null);
  const [state, setState] = useState<{ phase: "loading" | "ready" | "error"; message?: string }>({ phase: "loading" });
  const [dims, setDims] = useState<[number, number, number] | null>(null);

  // ---------------------------------------------------------------- motor: bileşen ömrü boyunca bir kez
  useEffect(() => {
    if (!canvas.current || !host.current) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas.current, antialias: true, powerPreference: "low-power" });
    } catch (e) {
      setState({ phase: "error", message: `WebGL önizlemesi başlatılamadı: ${(e as Error).message}` });
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    // Khronos PBR Neutral: taban renkleri (dokular) ton eşlemede kaydırmaz; aşırı parlak alanlar yumuşak sıkıştırılır.
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0E1729");
    // Işık: Kenney malzemeleri metalness 0 / roughness 1 (yalnızca dağınık yansıma) → ortam haritası (PMREM) gereksiz;
    // yarım küre ışığı aynı dağınık ortam katkısını verir. PMREM iç render hedefi kapanışta GPU sayacında kalıyordu (Faz 8B ölçümü).
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(-3, 6, 4);
    const fill = new THREE.DirectionalLight(0xdbeafe, 0.6);
    fill.position.set(4, 2, -3);
    scene.add(key, fill, new THREE.HemisphereLight(0xf1f5ff, 0x1c2b47, 1.6));
    const camera = new THREE.PerspectiveCamera(FOV, 1, 0.05, 500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.enablePan = false;
    controls.maxPolarAngle = Math.PI * 0.495; // zeminin altına inilmez

    const e: Engine = {
      renderer, scene, camera, controls, grid: null, model: null,
      home: { pos: new THREE.Vector3(4, 3, 5), target: new THREE.Vector3(), fit: 6, radius: 1 }, frame: 0, frames: 0,
      request: () => {
        if (e.frame) return;
        e.frame = requestAnimationFrame(() => {
          e.frame = 0;
          controls.update(); // sönümleme sürüyorsa "change" olayı yeni kare ister
          renderer.render(scene, camera);
          e.frames++;
        });
      },
    };
    engine.current = e;
    controls.addEventListener("change", e.request);
    const resize = () => {
      const w = host.current?.clientWidth ?? 0, h = host.current?.clientHeight ?? 0;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      e.request();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(host.current);
    resize();
    const onLost = (ev: Event) => { ev.preventDefault(); setState({ phase: "error", message: "Önizleme WebGL bağlamı kaybedildi; paneli kapatıp yeniden açın." }); };
    renderer.domElement.addEventListener("webglcontextlost", onLost);

    const d = debug();
    d.baseline = { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
    d.live++;
    d.created++;
    d.state = () => ({
      distance: camera.position.distanceTo(controls.target), fitDistance: e.home.fit, radius: e.home.radius,
      model: e.model?.name ?? null, frames: e.frames, textureSlots: textureSlots(e.model), memory: { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures },
    });
    d.action = (a) => act(e, a);

    return () => {
      cancelAnimationFrame(e.frame);
      ro.disconnect();
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      controls.dispose();
      const freed = e.model ? disposeObject(e.model) : { geometries: 0, textures: 0 };
      if (e.grid) disposeObject(e.grid);
      // Sahne çizildikten sonra kalan GPU kaynakları sayılır. Beklenen: 0 geometri, 1 doku. Kalan doku modele ait değildir:
      // three.js r186 fiziksel malzemeler için modül düzeyinde TEK bir DFG arama tablosu (getDFGLUT, 16×16 RG16F ≈ 1 KB)
      // oluşturur ve tüm çiziciler paylaşır; bırakılmaz. Doğrulama (Kaza Odak geçişi): aynı model MeshBasicMaterial ile
      // çizildiğinde kalan kayıt 0. Bağlam aşağıda zorla kaybedildiği için GPU tarafı tarayıcı tarafından bırakılır.
      const left = { gpuGeometriesLeft: renderer.info.memory.geometries, gpuTexturesLeft: renderer.info.memory.textures };
      renderer.dispose();
      // Çizicinin kendi iç kaynakları (ör. ton eşleme ara hedefi) renderer.dispose() ile bırakılır; ayrıca ölçülür
      const afterRenderer = { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
      renderer.forceContextLoss(); // tarayıcının bağlam sınırına (≈16) yığılmasın
      d.live--;
      d.destroyed++;
      d.lastDispose = { geometries: freed.geometries, textures: freed.textures, ...left, afterRenderer, contextLost: renderer.getContext().isContextLost() };
      d.state = undefined;
      d.action = undefined;
      engine.current = null;
    };
  }, []);

  // ---------------------------------------------------------------- model: kayıt değişince yeniden çözümlenir
  useEffect(() => {
    const e = engine.current;
    if (!e) return;
    let cancelled = false;
    setState({ phase: "loading" });
    loadGlb(record.file).then((gltf) => {
      if (cancelled || engine.current !== e) return void disposeObject(gltf.scene);
      if (e.model) disposeObject(e.model);
      if (e.grid) disposeObject(e.grid);
      // Haritadakiyle aynı hazırlık: gerçek boyut ölçeği, taban y = 0 (registry.json), doğrusal doku örnekleme
      const inner = gltf.scene;
      smoothTextureSampling(inner);
      inner.position.y = record.ground_offset;
      const holder = new THREE.Group();
      holder.add(inner);
      holder.scale.setScalar(record.scale);
      holder.name = record.id;
      e.scene.add(holder);
      e.model = holder;
      const box = new THREE.Box3().setFromObject(holder);
      const size = box.getSize(new THREE.Vector3());
      const sphere = box.getBoundingSphere(new THREE.Sphere());
      setDims([size.x, size.y, size.z]);
      // 1 m ızgara: ölçek okunur; modelin ayak izinden biraz geniş
      const cells = Math.max(4, Math.ceil(Math.max(size.x, size.z) * 1.6));
      const grid = new THREE.GridHelper(cells, cells, 0x2e4166, 0x1c2b47);
      grid.position.y = 0.001;
      e.scene.add(grid);
      e.grid = grid;
      const fit = fitDistance(sphere.radius, FOV, e.camera.aspect);
      e.home = { pos: sphere.center.clone().addScaledVector(HOME_DIR, fit), target: sphere.center.clone(), fit, radius: sphere.radius };
      e.controls.minDistance = sphere.radius * 1.15;
      e.controls.maxDistance = fit * 3;
      e.camera.near = Math.max(0.01, sphere.radius / 100);
      e.camera.far = fit * 10;
      e.camera.updateProjectionMatrix();
      act(e, "reset");
      setState({ phase: "ready" });
    }).catch((err: Error) => { if (!cancelled) setState({ phase: "error", message: err.message }); });
    return () => { cancelled = true; };
  }, [record]);

  const run = (a: PreviewAction) => engine.current && act(engine.current, a);
  return (
    <figure className="space-y-2" data-testid="glb-preview" data-state={state.phase} data-model={record.id}>
      <div ref={host} className="relative h-[200px] w-full overflow-hidden rounded-lg border border-line bg-[#0E1729]">
        <canvas ref={canvas} className="block h-full w-full cursor-grab active:cursor-grabbing touch-none" tabIndex={-1}
          aria-label={`${record.name_tr} 3D model önizlemesi; sürükleyerek döndürün, tekerlekle yakınlaştırın`} />
        {state.phase === "loading" && <div className="absolute inset-0 grid place-items-center text-[12px] text-muted-foreground" role="status">Model hazırlanıyor…</div>}
        {state.phase === "error" && <div className="absolute inset-0 grid place-items-center p-3 text-center text-[12px] text-hotspot" role="alert">{state.message}</div>}
        <div className="absolute right-1.5 top-1.5 flex flex-col gap-1" role="group" aria-label="Önizleme kamerası">
          <PreviewButton label="Yakınlaştır" onClick={() => run("zoomIn")} testId="preview-zoom-in"><ZoomIn /></PreviewButton>
          <PreviewButton label="Uzaklaştır" onClick={() => run("zoomOut")} testId="preview-zoom-out"><ZoomOut /></PreviewButton>
          <PreviewButton label="Sola döndür" onClick={() => run("rotL")} testId="preview-rot-l"><RotateCcw /></PreviewButton>
          <PreviewButton label="Sağa döndür" onClick={() => run("rotR")} testId="preview-rot-r"><RotateCw /></PreviewButton>
          <PreviewButton label="Kamerayı sıfırla" onClick={() => run("reset")} testId="preview-reset"><Scan /></PreviewButton>
        </div>
      </div>
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-[11px] text-subtle">
        <span>Sürükle: döndür · tekerlek: yakınlaştır · ızgara 1 m</span>
        {dims && <span className="tabular whitespace-nowrap" data-testid="preview-dims" title="Genişlik × uzunluk × yükseklik (kayıttaki gerçek boyut ölçeğiyle)">G×U×Y {fmtNum(dims[0], 1)} × {fmtNum(dims[2], 1)} × {fmtNum(dims[1], 1)} m</span>}
      </figcaption>
    </figure>
  );
}

function PreviewButton({ label, onClick, testId, children }: { label: string; onClick: () => void; testId: string; children: React.ReactNode }) {
  return (
    <Button type="button" size="icon-sm" variant="outline" className="size-7 bg-surface/85 backdrop-blur-sm" aria-label={label} title={label} onClick={onClick} data-testid={testId}>
      {children}
    </Button>
  );
}

/** Kamera eylemleri: hedef etrafında yörünge (döndür), hedefe doğru yaklaşma (yakınlaştır), ilk kadraja dönüş. */
function act(e: Engine, a: PreviewAction): void {
  const { camera, controls } = e;
  const offset = camera.position.clone().sub(controls.target);
  if (a === "reset") {
    camera.position.copy(e.home.pos);
    controls.target.copy(e.home.target);
  } else if (a === "zoomIn" || a === "zoomOut") {
    const d = THREE.MathUtils.clamp(offset.length() * (a === "zoomIn" ? 0.8 : 1.25), controls.minDistance, controls.maxDistance);
    camera.position.copy(controls.target).addScaledVector(offset.normalize(), d);
  } else {
    offset.applyAxisAngle(new THREE.Vector3(0, 1, 0), (a === "rotL" ? -1 : 1) * (Math.PI / 6));
    camera.position.copy(controls.target).add(offset);
  }
  camera.lookAt(controls.target);
  controls.update();
  e.request();
}

/** Denetim: modeldeki malzemelerin doku taşıyan TÜM alanları (temizliğin hiçbir dokuyu atlamadığını doğrulamak için). */
function textureSlots(root: THREE.Object3D | null): string[] {
  const out = new Set<string>();
  root?.traverse((o) => {
    const m = (o as THREE.Mesh).material;
    for (const mat of m ? (Array.isArray(m) ? m : [m]) : []) {
      for (const [k, v] of Object.entries(mat)) if ((v as THREE.Texture | null)?.isTexture) out.add(`${mat.type}.${k}#${(v as THREE.Texture).uuid.slice(0, 6)}`);
    }
  });
  return [...out];
}
