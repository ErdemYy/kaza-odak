// MapLibre özel 3D katmanı: Three.js ile GLB modellerini coğrafi konumlarına yerleştirir.
//
// Dönüşüm zinciri: clip = mainMatrix(MapLibre kamera) · A(çapa) · yerel
//   A = T(mercator çapa) · S(s, −s, s) · Rx(π/2)  (s = çapa enleminde 1 m'nin mercator karşılığı)
//   yerel çerçeve: +X doğu, +Y yukarı, +Z güney (metre). Bkz. lib/geo.ts anchorMatrix().
// Harita ile aynı WebGL bağlamı ve derinlik tamponu kullanılır (renderingMode "3d"): binalar modelleri
// doğru örter. Her karede renderer.resetState() ile GL durumu MapLibre'den devralınır.
import type { CustomLayerInterface, CustomRenderMethodInput, Map as MlMap } from "maplibre-gl";
import * as THREE from "three";
import type { LngLat } from "../lib/geo";
import { anchorMatrix, headingToRotationY, localOffsetM, localToLngLat, transformPoint } from "../lib/geo";
import { loadGlb } from "../lib/glb";
import type { MotionLevel } from "../lib/layers";
import type { AssetRecord } from "../lib/registry";

export interface InspectorPlacement {
  modelId: string;
  lngLat: LngLat;
  altitudeM: number;
  headingDeg: number;
  scale: number; // kayıttaki gerçek boyut ölçeğine çarpan
}

export interface ClusterScene {
  clusterId: number;
  center: LngLat;
  radiusM: number;
  road: LngLat[] | null; // küme yakınındaki gerçek yol çizgisi (OSM), yoksa araç yok
}

export interface DebugObject {
  name: string;
  lngLat: LngLat;
  screen: [number, number] | null;
  visible: boolean;
}

const VEHICLES = ["taxi", "sedan", "suv", "truck", "delivery", "taxi"];
const LANE_M = 1.8; // şerit merkezinin yol eksenine uzaklığı
const LOD1_METERS_PER_PIXEL = 0.12; // bu çözünürlüğün üstünde (uzak) LOD1 kullanılır
const WHEEL_RADIUS_M = 0.36;
const MIN_ZOOM = 14;

interface Vehicle {
  root: THREE.Object3D;
  lod0: THREE.Object3D;
  lod1: THREE.Object3D | null;
  wheels: THREE.Object3D[];
  s: number; // yol boyunca konum (m)
  speed: number; // m/sn
  dir: 1 | -1;
}

function prepare(gltf: THREE.Object3D, rec: AssetRecord, extraScale = 1): THREE.Object3D {
  const inner = gltf;
  inner.position.y = rec.ground_offset; // model tabanı y=0 (yerde; gömülü/havada değil)
  const holder = new THREE.Group();
  holder.add(inner);
  holder.scale.setScalar(rec.scale * extraScale);
  holder.name = rec.id;
  return holder;
}

export class CityModelsLayer implements CustomLayerInterface {
  readonly id = "city-models";
  readonly type = "custom" as const;
  readonly renderingMode = "3d" as const;

  private map!: MlMap;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene = new THREE.Scene();
  private camera = new THREE.Camera();
  private anchor: LngLat;
  private anchorM = new THREE.Matrix4();
  private lastMatrix: number[] | null = null;
  private timer = new THREE.Timer();
  private registry: Map<string, AssetRecord>;
  private templates = new Map<string, Promise<{ lod0: THREE.Object3D; lod1: THREE.Object3D | null }>>();
  private clusterGroup = new THREE.Group();
  private inspectorGroup = new THREE.Group();
  private ring: THREE.Mesh | null = null;
  private glow: THREE.Mesh | null = null;
  private vehicles: Vehicle[] = [];
  private path: { pts: THREE.Vector3[]; cum: number[]; length: number } | null = null;
  private pulseT = 0;
  private sceneToken = 0;
  motion: MotionLevel = "full";
  status: { ready: boolean; error: string | null; loaded: string[]; contextLost: boolean } = { ready: false, error: null, loaded: [], contextLost: false };
  onStatus: (s: CityModelsLayer["status"]) => void = () => {};

  constructor(registry: AssetRecord[], anchor: LngLat) {
    this.registry = new Map(registry.map((r) => [r.id, r]));
    this.anchor = anchor;
    this.setAnchor(anchor);
    const hemi = new THREE.HemisphereLight(0xdbeafe, 0x0b1120, 2.2);
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(-60, 120, -40);
    this.scene.add(hemi, sun, this.clusterGroup, this.inspectorGroup);
  }

  setAnchor(anchor: LngLat): void {
    this.anchor = anchor;
    this.anchorM.fromArray(anchorMatrix(anchor));
  }

  onAdd(map: MlMap, gl: WebGL2RenderingContext): void {
    this.map = map;
    this.renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true });
    this.renderer.autoClear = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.status.ready = true;
    this.status.contextLost = false;
    this.onStatus({ ...this.status });
  }

  onRemove(): void {
    this.clear(this.clusterGroup);
    this.clear(this.inspectorGroup);
    this.renderer?.dispose();
    this.renderer = null;
    this.status.ready = false;
  }

  private clear(g: THREE.Group): void {
    // Şablondan klonlanan nesneler geometri/doku paylaşır; yalnızca bu katmana özgü (halka) kaynaklar bırakılır.
    for (const c of [...g.children]) {
      g.remove(c);
      c.traverse((o) => {
        if ((o as THREE.Mesh).userData.owned) {
          (o as THREE.Mesh).geometry.dispose();
          ((o as THREE.Mesh).material as THREE.Material).dispose();
        }
      });
    }
  }

  private template(id: string): Promise<{ lod0: THREE.Object3D; lod1: THREE.Object3D | null }> {
    let t = this.templates.get(id);
    if (!t) {
      const rec = this.registry.get(id);
      if (!rec) return Promise.reject(new Error(`Kayıtta model yok: ${id}`));
      t = (async () => {
        const g0 = await loadGlb(rec.file);
        const g1 = rec.lod1 ? await loadGlb(rec.lod1.file) : null;
        this.status.loaded = [...new Set([...this.status.loaded, id])];
        this.onStatus({ ...this.status });
        return { lod0: g0.scene, lod1: g1?.scene ?? null };
      })();
      t.catch((e: Error) => {
        this.templates.delete(id);
        this.status.error = e.message;
        this.onStatus({ ...this.status });
      });
      this.templates.set(id, t);
    }
    return t;
  }

  /** Yerel (doğu, güney) metre konumu; çapadan uzaklık ne olursa olsun konum hatasızdır. */
  private local(p: LngLat, alt = 0): THREE.Vector3 {
    const [x, y, z] = localOffsetM(this.anchor, p, alt);
    return new THREE.Vector3(x, y, z);
  }

  /** Seçili küme sahnesi: ışık halkası + gerçek yol üzerinde sınırlı sayıda temsili araç + donatılar. */
  /** Döndürür: yerleştirilen temsili araç sayısı (sahne iptal edildiyse −1). */
  async setClusterScene(cs: ClusterScene | null): Promise<number> {
    const token = ++this.sceneToken;
    this.clear(this.clusterGroup);
    this.vehicles = [];
    this.path = null;
    this.ring = this.glow = null;
    if (!cs) {
      this.map?.triggerRepaint();
      return 0;
    }
    this.setAnchor(cs.center);
    const r = Math.max(12, Math.min(cs.radiusM || 0, 120));

    const ring = new THREE.Mesh(new THREE.RingGeometry(r * 0.92, r, 96),
      new THREE.MeshBasicMaterial({ color: 0xf87171, transparent: true, opacity: 0.85, depthWrite: false, side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.4;
    ring.userData.owned = true;
    const glowTex = radialTexture();
    const glow = new THREE.Mesh(new THREE.CircleGeometry(r * 1.6, 64),
      new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    glow.rotation.x = -Math.PI / 2;
    glow.position.y = 0.2;
    glow.userData.owned = true;
    this.ring = ring;
    this.glow = glow;
    this.clusterGroup.add(glow, ring);
    this.pulseT = 0;

    if (cs.road && cs.road.length >= 2) {
      const pts = cs.road.map((p) => this.local(p));
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + pts[i].distanceTo(pts[i - 1]));
      this.path = { pts, cum, length: cum[cum.length - 1] };
      if (this.path.length >= 30) {
        const n = this.path.length < 80 ? 3 : VEHICLES.length;
        for (let i = 0; i < n; i++) {
          const id = VEHICLES[i % VEHICLES.length];
          const rec = this.registry.get(id);
          if (!rec) continue;
          const tpl = await this.template(id).catch(() => null);
          if (token !== this.sceneToken) return -1;
          if (!tpl) continue;
          const lod0 = prepare(tpl.lod0.clone(true), rec);
          const lod1 = tpl.lod1 ? prepare(tpl.lod1.clone(true), rec) : null;
          const root = new THREE.Group();
          root.name = `vehicle:${id}:${i}`;
          root.add(lod0);
          if (lod1) {
            lod1.visible = false;
            root.add(lod1);
          }
          const wheels: THREE.Object3D[] = [];
          lod0.traverse((o) => { if (o.name.startsWith("wheel")) wheels.push(o); });
          this.vehicles.push({ root, lod0, lod1, wheels, s: (this.path.length * i) / n, speed: 7 + (i % 3) * 1.5, dir: i % 2 === 0 ? 1 : -1 });
          this.clusterGroup.add(root);
        }
        // Donatılar: yol kenarında (şerit dışı) trafik lambası ve DUR levhası
        for (const [id, side, along] of [["traffic-light", 1, -6], ["road-sign-stop", -1, 6]] as const) {
          const rec = this.registry.get(id);
          const tpl = rec && (await this.template(id).catch(() => null));
          if (!rec || !tpl || token !== this.sceneToken) continue;
          const p = this.pointAt(this.path.length / 2 + along);
          const o = prepare(tpl.lod0.clone(true), rec);
          o.position.copy(p.pos).addScaledVector(p.right, side * (LANE_M * 2 + 2.6));
          o.rotation.y = Math.atan2(-side * p.right.x, -side * p.right.z);
          o.name = `prop:${id}`;
          this.clusterGroup.add(o);
        }
      }
    }
    if (token !== this.sceneToken) return -1;
    this.updateVehicles(0);
    this.map?.triggerRepaint();
    return this.vehicles.length;
  }

  private pointAt(s: number): { pos: THREE.Vector3; dir: THREE.Vector3; right: THREE.Vector3 } {
    const path = this.path!;
    const d = Math.max(0, Math.min(path.length, s));
    let i = 1;
    while (i < path.cum.length - 1 && path.cum[i] < d) i++;
    const a = path.pts[i - 1], b = path.pts[i];
    const seg = path.cum[i] - path.cum[i - 1] || 1;
    const pos = a.clone().lerp(b, (d - path.cum[i - 1]) / seg);
    const dir = b.clone().sub(a).normalize();
    // Sağ el trafiği: yerel (x doğu, z güney) düzleminde ilerleme yönünün sağı = (−dz, dx)
    const right = new THREE.Vector3(-dir.z, 0, dir.x);
    return { pos, dir, right };
  }

  private updateVehicles(dt: number): void {
    if (!this.path) return;
    const move = this.motion === "full" ? dt : 0;
    const mpp = this.metersPerPixel();
    for (const v of this.vehicles) {
      v.s = (v.s + v.dir * v.speed * move + this.path.length) % this.path.length;
      const p = this.pointAt(v.s);
      const heading = p.dir.clone().multiplyScalar(v.dir);
      v.root.position.copy(p.pos).addScaledVector(p.right, v.dir * LANE_M);
      v.root.rotation.y = Math.atan2(heading.x, heading.z); // model ileri ekseni +Z
      // Uçlarda (yol parçasının bittiği yerde) görünmez: ani ışınlanma görülmez
      const edge = Math.min(v.s, this.path.length - v.s);
      v.root.visible = edge > 4;
      for (const w of v.wheels) w.rotation.x += (v.speed * move) / WHEEL_RADIUS_M;
      const far = mpp > LOD1_METERS_PER_PIXEL && v.lod1 !== null;
      v.lod0.visible = !far;
      if (v.lod1) v.lod1.visible = far;
    }
  }

  private metersPerPixel(): number {
    if (!this.map) return 0;
    const lat = this.map.getCenter().lat;
    return (40075016.686 * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** this.map.getZoom());
  }

  /** Varlık inceleyici: kullanıcı boylam/enlem/irtifa/yön/ölçek ile tek bir modeli yerleştirir. */
  async setInspector(p: InspectorPlacement | null): Promise<void> {
    this.clear(this.inspectorGroup);
    if (!p) return this.map?.triggerRepaint();
    const rec = this.registry.get(p.modelId);
    if (!rec) throw new Error(`Kayıtta model yok: ${p.modelId}`);
    const tpl = await this.template(p.modelId);
    this.clear(this.inspectorGroup);
    const o = prepare(tpl.lod0.clone(true), rec, p.scale);
    o.position.copy(this.local(p.lngLat, p.altitudeM));
    o.rotation.y = headingToRotationY(p.headingDeg); // pusula yönü → +Z ileri ekseni
    o.name = `inspector:${p.modelId}`;
    o.userData.lngLat = p.lngLat;
    this.inspectorGroup.add(o);
    this.map?.triggerRepaint();
  }

  render(_gl: WebGL2RenderingContext, options: CustomRenderMethodInput): void {
    if (!this.renderer) return;
    this.timer.update();
    const dt = Math.min(this.timer.getDelta(), 0.1);
    if (this.map.getZoom() < MIN_ZOOM) return; // şehir ölçeğinde modeller piksel altı: çizilmez
    this.updateVehicles(dt);
    if (this.ring && this.glow) {
      if (this.motion === "full") {
        this.pulseT = (this.pulseT + dt / 2.2) % 1;
        const k = 1 + this.pulseT * 0.45;
        this.ring.scale.setScalar(k);
        (this.ring.material as THREE.MeshBasicMaterial).opacity = 0.85 * (1 - this.pulseT);
      } else {
        this.ring.scale.setScalar(1);
        (this.ring.material as THREE.MeshBasicMaterial).opacity = 0.85;
      }
    }
    const main = options.defaultProjectionData.mainMatrix as unknown as number[];
    this.lastMatrix = Array.from(main);
    this.camera.projectionMatrix = new THREE.Matrix4().fromArray(main).multiply(this.anchorM);
    this.renderer.resetState();
    this.renderer.render(this.scene, this.camera);
    const animating = this.motion === "full" && (this.vehicles.length > 0 || this.ring !== null);
    if (animating) this.map.triggerRepaint();
  }

  /** Test/denetim: sahnedeki nesnelerin coğrafi konumu ve Three.js zinciriyle hesaplanan ekran konumu. */
  debugObjects(): DebugObject[] {
    const out: DebugObject[] = [];
    const canvas = this.map?.getCanvas();
    const full = this.lastMatrix ? new THREE.Matrix4().fromArray(this.lastMatrix).multiply(this.anchorM) : null;
    const visit = (o: THREE.Object3D) => {
      if (!/^(vehicle|prop|inspector):/.test(o.name)) return;
      const wp = new THREE.Vector3();
      o.getWorldPosition(wp);
      const [lng, lat] = localToLngLat(this.anchor, wp.x, wp.z);
      let screen: [number, number] | null = null;
      if (full && canvas) {
        const c = transformPoint(full.elements, [wp.x, wp.y, wp.z]);
        if (c[3] > 0) screen = [((c[0] / c[3] + 1) / 2) * canvas.clientWidth, ((1 - c[1] / c[3]) / 2) * canvas.clientHeight];
      }
      out.push({ name: o.name, lngLat: [lng, lat], screen, visible: o.visible });
    };
    this.clusterGroup.children.forEach(visit);
    this.inspectorGroup.children.forEach(visit);
    return out;
  }
}

function radialTexture(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, "rgba(248,113,113,0.45)");
  grd.addColorStop(0.55, "rgba(248,113,113,0.12)");
  grd.addColorStop(1, "rgba(248,113,113,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
