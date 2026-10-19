import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder } from "meshoptimizer";
import { beforeAll, describe, expect, it } from "vitest";
import { fetchGlb, ModelLoadError, validateGlbHeader } from "../../src/lib/glb";
import { validateRegistry, type AssetRegistry } from "../../src/lib/registry";

const PUB = resolve(__dirname, "../../public");
const registry = JSON.parse(readFileSync(resolve(PUB, "models/registry.json"), "utf8")) as AssetRegistry;
const ab = (b: Buffer) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;

describe("Varlık kaydı ve lisanslar", () => {
  it("her modelin kaynak, yazar, lisans ve atıf bilgisi var; lisans CC0/CC BY", () => {
    expect(validateRegistry(registry)).toEqual([]);
    for (const m of registry.models) {
      expect(m.license).toMatch(/^CC0/);
      expect(m.source.archive_sha256).toMatch(/^[0-9a-f]{64}$/);
    }
  });
  it("lisansı doğrulanamayan paket kullanılmaz ve gerekçesi kaydedilir", () => {
    expect(registry.not_used.map((n) => n.file)).toContain("Cars Bundle-glb.zip");
    expect(registry.models.every((m) => m.source.archive !== "Cars Bundle-glb.zip")).toBe(true);
  });
  it("eksik lisans alanı reddedilir", () => {
    const bad = structuredClone(registry);
    bad.models[0].license = "";
    bad.models[1].license = "Proprietary";
    const p = validateRegistry(bad);
    expect(p.some((s) => s.includes("'license' eksik"))).toBe(true);
    expect(p.some((s) => s.includes("lisans kabul dışı"))).toBe(true);
  });
  it("en az bir araç modeli, trafik lambası, levha ve bariyer seçildi", () => {
    const ids = registry.models.map((m) => m.id);
    for (const id of ["taxi", "sedan", "suv", "truck", "traffic-light", "road-sign-stop", "construction-barrier"]) expect(ids).toContain(id);
  });
});

describe("GLB yükleme", () => {
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  beforeAll(async () => {
    await MeshoptDecoder.ready;
    io.registerDependencies({ "meshopt.decoder": MeshoptDecoder });
  });

  for (const m of registry.models) {
    it(`${m.id}: dosya bütünlüğü, çözümleme, üçgen sayısı, gömülü doku`, async () => {
      const buf = readFileSync(resolve(PUB, m.file));
      expect(buf.byteLength).toBe(m.optimized.bytes);
      expect(() => validateGlbHeader(ab(buf))).not.toThrow();
      const doc = await io.readBinary(new Uint8Array(buf));
      const root = doc.getRoot();
      let tris = 0;
      for (const s of root.listScenes()) s.traverse((n) => {
        for (const p of n.getMesh()?.listPrimitives() ?? []) tris += (p.getIndices()?.getCount() ?? 0) / 3;
      });
      expect(tris).toBe(m.optimized.triangles);
      expect(root.listTextures().every((t) => (t.getImage()?.byteLength ?? 0) > 0)).toBe(true); // harici doku yok
      if (m.category === "vehicle") expect(m.animated_nodes.length).toBeGreaterThanOrEqual(4);
    });
  }

  it("bozuk/kesik/yanlış dosya başlıkları reddedilir", () => {
    const good = readFileSync(resolve(PUB, registry.models[0].file));
    expect(() => validateGlbHeader(new ArrayBuffer(4))).toThrow(/çok kısa/);
    expect(() => validateGlbHeader(ab(Buffer.from("<!doctype html><html>not a model</html>")))).toThrow(/sihirli/);
    expect(() => validateGlbHeader(ab(good.subarray(0, good.byteLength - 100)))).toThrow(/uzunluk/);
    const v1 = Buffer.from(good);
    v1.writeUInt32LE(1, 4);
    expect(() => validateGlbHeader(ab(v1))).toThrow(/sürüm/);
  });

  it("eksik dosya (404) ve bozuk içerik ModelLoadError ile sınıflandırılır, önbelleğe alınmaz", async () => {
    const notFound = (async () => new Response("yok", { status: 404 })) as typeof fetch;
    await expect(fetchGlb("models/yok.glb", notFound)).rejects.toMatchObject({ reason: "not-found" });
    const html = (async () => new Response("<html></html>", { status: 200 })) as typeof fetch;
    await expect(fetchGlb("models/bozuk.glb", html)).rejects.toBeInstanceOf(ModelLoadError);
    await expect(fetchGlb("models/bozuk.glb", html)).rejects.toMatchObject({ reason: "invalid" });
    const down = (async () => { throw new TypeError("Failed to fetch"); }) as typeof fetch;
    await expect(fetchGlb("models/ag.glb", down)).rejects.toMatchObject({ reason: "network" });
    const good = readFileSync(resolve(PUB, registry.models[0].file));
    const ok = (async () => new Response(good, { status: 200 })) as typeof fetch;
    await expect(fetchGlb("models/bozuk.glb", ok)).resolves.toBeInstanceOf(ArrayBuffer); // hata önbelleklenmedi
  });
});
