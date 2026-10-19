// Faz 4 3D varlık hattı: seçilen Kenney (CC0) GLB modellerini ZIP'ten salt-okunur okur, harici dokuyu
// gömer, web için optimize eder, LOD üretir ve lisans/ölçüm kaydını yazar. Orijinal ZIP'ler değişmez.
//
// Kullanım: npm run assets
// Çıktılar:
//   public/models/<id>.glb, <id>.lod1.glb        (depoda izlenir; küçük)
//   public/models/reference/<id>.glb             (yalnızca doku gömülü, optimize edilmemiş; QA karşılaştırması, git dışı)
//   public/models/registry.json                  (uygulamanın okuduğu varlık kaydı)
//   ../reports/phase4/asset_optimization.json    (öncesi/sonrası ölçümleri)
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, meshopt, prune, quantize, reorder, simplify, weld } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";
import { glbToJSONDocument, readZip } from "./lib/zip.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "../..");
const DOWNLOADS = resolve(ROOT, "assets/3d/downloads");
const OUT = resolve(here, "../public/models");
const REPORT = resolve(ROOT, "reports/phase4/asset_optimization.json");
const GLB_DIR = "Models/GLB format/";

const KENNEY = {
  author: "Kenney (www.kenney.nl)",
  license: "CC0 1.0 Universal (Kamu malı adanması)",
  license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
  attribution: "Zorunlu değil; kaynak olarak 'Kenney' belirtilir (lisans dosyasındaki isteğe bağlı rica).",
};
const PACKS = {
  "kenney_car-kit.zip": { pack: "Car Kit 2.0", source_url: "https://kenney.nl/assets/car-kit" },
  "kenney_city-kit-roads.zip": { pack: "City Kit (Roads) 2.2", source_url: "https://kenney.nl/assets/city-kit-roads" },
};
// real_m: modelin en uzun yatay boyutu (araç: uzunluk) veya yüksekliği için hedef gerçek ölçü (m).
// Kaynak: tipik NYC araç/donatı boyutları; temsili görselleştirme ölçeğidir.
const SELECTION = [
  { id: "sedan", zip: "kenney_car-kit.zip", name_tr: "Otomobil (sedan)", category: "vehicle", real_m: 4.8, measure: "length", lod1: true },
  { id: "taxi", zip: "kenney_car-kit.zip", name_tr: "Taksi", category: "vehicle", real_m: 5.0, measure: "length", lod1: true },
  { id: "suv", zip: "kenney_car-kit.zip", name_tr: "SUV", category: "vehicle", real_m: 4.9, measure: "length", lod1: true },
  { id: "truck", zip: "kenney_car-kit.zip", name_tr: "Kamyonet", category: "vehicle", real_m: 5.6, measure: "length", lod1: true },
  { id: "delivery", zip: "kenney_car-kit.zip", name_tr: "Teslimat kamyonu", category: "vehicle", real_m: 6.5, measure: "length", lod1: true },
  { id: "traffic-light", zip: "kenney_city-kit-roads.zip", name_tr: "Trafik lambası", category: "prop", real_m: 4.6, measure: "height", lod1: false },
  { id: "road-sign-stop", zip: "kenney_city-kit-roads.zip", name_tr: "DUR levhası", category: "prop", real_m: 2.4, measure: "height", lod1: false },
  { id: "road-sign-warning", zip: "kenney_city-kit-roads.zip", name_tr: "Uyarı levhası", category: "prop", real_m: 2.4, measure: "height", lod1: false },
  { id: "construction-barrier", zip: "kenney_city-kit-roads.zip", name_tr: "Bariyer", category: "prop", real_m: 1.0, measure: "height", lod1: false },
  { id: "construction-cone", zip: "kenney_city-kit-roads.zip", name_tr: "Trafik konisi", category: "prop", real_m: 0.7, measure: "height", lod1: false },
];
const NOT_USED = [
  { file: "Cars Bundle-glb.zip", reason: "Arşivde lisans, yazar veya kaynak bilgisi yok; GLB meta verisi yalnızca 'obj2gltf' üreticisini içeriyor. Lisans doğrulanamadığı için kullanılmadı." },
];

const sha256 = (b) => createHash("sha256").update(b).digest("hex");

function stats(doc) {
  const root = doc.getRoot();
  // Sayımlar sahnede ÇİZİLEN örnekler üzerindendir (dedup'un paylaştırdığı mesh her düğüm için sayılır).
  const instances = [];
  for (const scene of root.listScenes()) scene.traverse((node) => node.getMesh() && instances.push(node.getMesh()));
  let tris = 0, verts = 0, degenerate = 0;
  for (const m of instances) for (const p of m.listPrimitives()) {
    const pos = p.getAttribute("POSITION");
    const idx = p.getIndices();
    verts += pos.getCount();
    const n = idx ? idx.getCount() : pos.getCount();
    tris += n / 3;
    // Sıfır alanlı üçgen: iki köşesi aynı konumda veya üç köşe doğrusal (çapraz çarpım ~0)
    const a = [], b = [], c = [];
    for (let i = 0; i < n; i += 3) {
      pos.getElement(idx ? idx.getScalar(i) : i, a);
      pos.getElement(idx ? idx.getScalar(i + 1) : i + 1, b);
      pos.getElement(idx ? idx.getScalar(i + 2) : i + 2, c);
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const cr = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
      if (Math.hypot(...cr) < 1e-10) degenerate++;
    }
  }
  const textures = root.listTextures().map((t) => ({ size: t.getSize(), bytes: t.getImage()?.byteLength ?? 0, mime: t.getMimeType() }));
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (const scene of root.listScenes()) scene.traverse((node) => {
    const mesh = node.getMesh();
    if (!mesh) return;
    const w = node.getWorldMatrix();
    for (const p of mesh.listPrimitives()) {
      const a = p.getAttribute("POSITION");
      const lo = a.getMin([]), hi = a.getMax([]);
      for (const x of [lo[0], hi[0]]) for (const y of [lo[1], hi[1]]) for (const z of [lo[2], hi[2]]) {
        const v = [w[0] * x + w[4] * y + w[8] * z + w[12], w[1] * x + w[5] * y + w[9] * z + w[13], w[2] * x + w[6] * y + w[10] * z + w[14]];
        v.forEach((c, k) => { min[k] = Math.min(min[k], c); max[k] = Math.max(max[k], c); });
      }
    }
  });
  return { triangles: tris, degenerate_triangles: degenerate, vertices: verts, materials: root.listMaterials().length, nodes: root.listNodes().length,
    node_names: root.listNodes().map((n) => n.getName()), textures, bbox_min: min, bbox_max: max };
}

await MeshoptEncoder.ready;
await MeshoptSimplifier.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ "meshopt.encoder": MeshoptEncoder });
mkdirSync(resolve(OUT, "reference"), { recursive: true });
mkdirSync(dirname(REPORT), { recursive: true });

const zips = {};
const registry = [];
const report = [];
for (const sel of SELECTION) {
  const zipPath = resolve(DOWNLOADS, sel.zip);
  zips[sel.zip] ??= { zip: readZip(zipPath), sha256: sha256(readFileSync(zipPath)), bytes: statSync(zipPath).size };
  const { zip } = zips[sel.zip];
  const entry = `${GLB_DIR}${sel.id}.glb`;
  const original = zip.read(entry);
  const load = () => io.readJSON(glbToJSONDocument(original, (uri) => zip.read(GLB_DIR + uri)));

  // Referans: yalnızca harici doku gömülür (geometri değişmez) — görsel karşılaştırma için.
  const refDoc = await load();
  const before = stats(refDoc);
  const refBytes = await io.writeBinary(refDoc);
  writeFileSync(resolve(OUT, "reference", `${sel.id}.glb`), refBytes);

  // Optimize: tekrarları birleştir, kullanılmayanları ayıkla, köşe noktalarını kaynakla (indeksleme),
  // önbellek dostu sıralama, nicemleme (KHR_mesh_quantization) ve meshopt sıkıştırma.
  // Düğümler birleştirilmez: araç tekerlekleri ayrı düğüm olarak animasyona açık kalır.
  const doc = await load();
  await doc.transform(dedup(), prune(), weld(), reorder({ encoder: MeshoptEncoder }), quantize(),
    meshopt({ encoder: MeshoptEncoder, level: "medium" }));
  const after = stats(doc);
  const bytes = await io.writeBinary(doc);
  writeFileSync(resolve(OUT, `${sel.id}.glb`), bytes);

  let lod1 = null;
  if (sel.lod1) {
    const d1 = await load();
    await d1.transform(dedup(), prune(), weld(), simplify({ simplifier: MeshoptSimplifier, ratio: 0.5, error: 0.01 }),
      reorder({ encoder: MeshoptEncoder }), quantize(), meshopt({ encoder: MeshoptEncoder, level: "medium" }));
    const s1 = stats(d1);
    const b1 = await io.writeBinary(d1);
    writeFileSync(resolve(OUT, `${sel.id}.lod1.glb`), b1);
    lod1 = { file: `models/${sel.id}.lod1.glb`, bytes: b1.byteLength, triangles: s1.triangles, sha256: sha256(b1) };
  }

  const size = before.bbox_max.map((v, k) => v - before.bbox_min[k]);
  const native = sel.measure === "height" ? size[1] : Math.max(size[0], size[2]);
  const pack = PACKS[sel.zip];
  const rec = {
    id: sel.id, name_tr: sel.name_tr, category: sel.category, file: `models/${sel.id}.glb`, lod1,
    source: { pack: pack.pack, archive: sel.zip, archive_sha256: zips[sel.zip].sha256, entry, source_url: pack.source_url,
      original_bytes: original.byteLength, original_sha256: sha256(original), external_texture: "Textures/colormap.png" },
    ...KENNEY,
    optimized: { bytes: bytes.byteLength, sha256: sha256(bytes), triangles: after.triangles, vertices: after.vertices,
      textures: after.textures, extensions: doc.getRoot().listExtensionsUsed().map((e) => e.extensionName) },
    // Kenney modelleri: +Y yukarı; araçların ön yönü +Z (uzunluk Z ekseninde).
    axes: { up: "+Y", forward: sel.category === "vehicle" ? "+Z" : null },
    native_size: size, real_size_m: sel.real_m, measure: sel.measure, scale: sel.real_m / native,
    ground_offset: -before.bbox_min[1],
    animated_nodes: after.node_names.filter((n) => n.startsWith("wheel")),
    optimization_status: "optimize edildi (dedup, prune, weld, reorder, quantize, meshopt)" + (lod1 ? " + LOD1 (%50 sadeleştirme)" : ""),
  };
  registry.push(rec);
  report.push({ id: sel.id, before: { bytes_original_glb: original.byteLength, bytes_embedded: refBytes.byteLength,
    triangles: before.triangles, degenerate_triangles: before.degenerate_triangles, vertices: before.vertices,
    textures: before.textures },
    after: { bytes: bytes.byteLength, triangles: after.triangles, degenerate_triangles: after.degenerate_triangles,
      vertices: after.vertices, textures: after.textures },
    lod1, size_reduction_vs_embedded: 1 - bytes.byteLength / refBytes.byteLength,
    geometry_note: "LOD0'da çizilen üçgen sayısı değişmez (dedup özdeş tekerlek mesh'lerini paylaştırır). " +
      "Nicemleme konum hatası 16 bitte model boyutunun ~1/65535'i. Doku 512×512 paletli PNG (~11 KB); " +
      "küçültme palet renklerinde sızma riski taşıdığı için yapılmadı." });
  console.log(`${sel.id.padEnd(22)} ${refBytes.byteLength} B -> ${bytes.byteLength} B, üçgen ${before.triangles} -> ${after.triangles}` +
    (lod1 ? `, LOD1 ${lod1.triangles} üçgen / ${lod1.bytes} B` : ""));
}

const out = { generated_at: new Date().toISOString(), tool: "gltf-transform 4.5.1 + meshoptimizer 1.3.0",
  archives: Object.fromEntries(Object.entries(zips).map(([k, v]) => [k, { sha256: v.sha256, bytes: v.bytes, ...PACKS[k], ...KENNEY }])),
  not_used: NOT_USED, models: registry };
writeFileSync(resolve(OUT, "registry.json"), JSON.stringify(out, null, 2));
writeFileSync(REPORT, JSON.stringify({ generated_at: out.generated_at, tool: out.tool, models: report }, null, 2));
console.log(`Kayıt: ${resolve(OUT, "registry.json")}`);
