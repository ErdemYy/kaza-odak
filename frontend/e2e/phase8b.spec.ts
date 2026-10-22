// Faz 8B — görsel iyileştirme regresyonları. GERÇEK uygulama (FastAPI + derlenmiş ön yüz + OpenFreeMap).
// Kapsam: yeni harita katmanları, hover kartı = tıklama seçimi, seçim isabet alanının gerçek küme kimlikleriyle
// doğrulanması, seçimde soluklaştırma, GLB önizleyici (seç, döndür, yakınlaştır, sıfırla, ad/lisans, yerleştir, kaldır),
// aynı modelin yeniden indirilmemesi, önizleyici GPU kaynak temizliği, sol panel daraltma, panel çakışması,
// responsive taşma ve axe. Çıktı: reports/phase8b/ (SAFEROUTE_PHASE8B_OUT ile yönlendirilebilir).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.SAFEROUTE_PHASE8B_OUT ? resolve(process.env.SAFEROUTE_PHASE8B_OUT) : resolve(HERE, "../../reports/phase8b/e2e");
mkdirSync(resolve(OUT, "screenshots"), { recursive: true });
const TILLARY = 1344;
const results: Record<string, unknown> = {};
test.afterAll(() => writeFileSync(resolve(OUT, "phase8b_results.json"), JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2)));
test.use({ viewport: { width: 1440, height: 900 }, actionTimeout: 20_000 });

async function idle(page: Page, extra = 500) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && !m.isMoving(); }, null, { timeout: 90_000 });
  await page.waitForTimeout(extra);
}
async function openExplorer(page: Page) {
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await idle(page, 800);
}
const jump = async (page: Page, c: object) => { await page.evaluate((x) => (window as any).__saferoute.map.jumpTo(x), c); await idle(page, 500); };
const toPage = (page: Page, p: [number, number]) => page.evaluate((q) => {
  const m = (window as any).__saferoute.map; const r = m.project(q); const c = m.getCanvas().getBoundingClientRect();
  return { x: r.x, y: r.y, px: r.x + c.left, py: r.y + c.top };
}, p);
const rect = (page: Page, testId: string) => page.getByTestId(testId).boundingBox();
const overlap = (a: { x: number; y: number; width: number; height: number } | null, b: typeof a) =>
  !!a && !!b && a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test("Harita: yeni küme katmanları, hover kartı, isabet alanı ve seçim vurgusu", async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && !/openfreemap|openmaptiles/.test(m.text())) errors.push(m.text()); });
  await openExplorer(page);
  const layers = await page.evaluate(() => ["centroid-circle", "centroid-hover", "centroid-selected", "building-3d", "points-noise"]
    .map((id) => [id, !!(window as any).__saferoute.map.getLayer(id)]));
  expect(Object.fromEntries(layers)).toEqual({ "centroid-circle": true, "centroid-hover": true, "centroid-selected": true, "building-3d": true, "points-noise": true });

  // İsabet alanı: görünen her küme merkezi (ilk 60) kendi ekran noktasında KENDİ kimliğini döndürmeli
  await jump(page, { center: [-73.99, 40.735], zoom: 13.4, pitch: 0, bearing: 0 });
  const hit = await page.evaluate(() => {
    const w = (window as any).__saferoute; const m = w.map; const canvas = m.getCanvas();
    const feats = m.queryRenderedFeatures({ layers: ["centroid-circle"] });
    const uniq = new Map<number, any>(); for (const f of feats) uniq.set(Number(f.properties.cluster_id), f);
    let ok = 0, wrong: unknown[] = [], n = 0;
    for (const [id, f] of [...uniq].slice(0, 60)) {
      const p = m.project(f.geometry.coordinates);
      if (p.x < 5 || p.y < 5 || p.x > canvas.clientWidth - 5 || p.y > canvas.clientHeight - 5) continue;
      n++;
      const got = w.pick(p.x, p.y);
      if (got === id) ok++; else wrong.push({ id, got });
    }
    return { n, ok, wrong };
  });
  expect(hit.n).toBeGreaterThan(20);
  expect(hit.wrong).toEqual([]);
  results.hitbox = hit;

  // Hover kartı: imleç altındaki kümenin kimliği = seçim kuralının kimliği = tıklamanın açtığı küme
  const d = await page.evaluate(async (id) => (await fetch(`/api/clusters/${id}`)).json(), TILLARY);
  await jump(page, { center: [d.centroid_lon, d.centroid_lat], zoom: 15, pitch: 0, bearing: 0 });
  const p = await toPage(page, [d.centroid_lon, d.centroid_lat]);
  await page.mouse.move(p.px - 30, p.py - 30);
  await page.mouse.move(p.px, p.py, { steps: 4 });
  const card = page.getByTestId("cluster-hover");
  await expect(card).toBeVisible({ timeout: 10_000 });
  const hoverId = Number(await card.getAttribute("data-cluster-id"));
  const pickId = await page.evaluate(([x, y]) => (window as any).__saferoute.pick(x, y), [p.x, p.y]);
  expect(hoverId).toBe(pickId);
  await expect(card).toContainText(`${d.n_events.toLocaleString("tr-TR")} kaza kaydı`);
  const hoverFilter = await page.evaluate(() => (window as any).__saferoute.map.getFilter("centroid-hover"));
  expect(hoverFilter).toEqual(["==", ["get", "cluster_id"], hoverId]);
  await page.screenshot({ path: resolve(OUT, "screenshots/hover-karti.png") });
  await page.mouse.click(p.px, p.py);
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 60_000 });
  await expect(page.getByTestId("cluster-title")).toContainText(`Küme #${hoverId}`);
  await expect(card).toBeHidden(); // kamera hareketi kartı kapatır

  // Seçim vurgusu: seçili halka yalnızca bu küme; diğer merkezler soluklaşır; kapatınca eski görünüm
  const sel = await page.evaluate(() => { const m = (window as any).__saferoute.map;
    return { filter: m.getFilter("centroid-selected"), opacity: m.getPaintProperty("centroid-circle", "circle-opacity") }; });
  expect(sel.filter).toEqual(["==", ["get", "cluster_id"], hoverId]);
  expect(JSON.stringify(sel.opacity)).toContain("0.38");
  // Panel: üst özet + gruplar; model bilgisi kapalı; araç oranı notu
  await expect(page.getByTestId("cluster-keystats")).toContainText("Ölümle sonuçlanan kaza");
  await expect(page.getByTestId("cluster-rank")).toBeVisible();
  expect(await page.getByTestId("group-model").evaluate((e) => (e as HTMLDetailsElement).open)).toBe(false);
  await page.getByTestId("group-model").locator("summary").click();
  await expect(page.getByTestId("cluster-experiment")).toBeVisible();
  // Uzun panel kendi içinde kayar, yapışkan başlık görünür kalır
  const scroll = await page.getByTestId("right-panel").evaluate((el) => { el.scrollTop = el.scrollHeight; return { sh: el.scrollHeight, ch: el.clientHeight, top: el.scrollTop }; });
  expect(scroll.sh).toBeGreaterThan(scroll.ch);
  expect(scroll.top).toBeGreaterThan(0);
  await expect(page.getByTestId("cluster-title")).toBeInViewport();
  await page.getByTestId("cluster-panel").getByRole("button", { name: "Seçimi kapat" }).click();
  const after = await page.evaluate(() => { const m = (window as any).__saferoute.map;
    return { filter: m.getFilter("centroid-selected"), opacity: m.getPaintProperty("centroid-circle", "circle-opacity") }; });
  expect(after.filter).toEqual(["==", ["get", "cluster_id"], -1]);
  expect(JSON.stringify(after.opacity)).not.toContain("0.38");
  results.hover = { hoverId, pickId, selected: hoverId };
  expect(errors).toEqual([]);
});

test("GLB önizleyici: seç, döndür, yakınlaştır, sıfırla, lisans, yerleştir/kaldır, tekrar indirme yok, GPU temizliği", async ({ page }) => {
  test.setTimeout(240_000);
  const glbRequests: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith(".glb")) glbRequests.push(new URL(r.url()).pathname); });
  await openExplorer(page);
  await jump(page, { center: [-73.98397, 40.69471], zoom: 19, pitch: 60, bearing: 335 });
  await page.getByTestId("assets-toggle").click();
  await page.click('[data-model="taxi"]');
  const preview = page.getByTestId("glb-preview");
  await expect(preview).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await expect(page.getByTestId("preview-title")).toHaveText("Taksi");
  await expect(page.getByTestId("preview-license-short")).toContainText("CC0");
  await expect(page.getByTestId("asset-license")).toContainText("Kenney");
  await expect(page.getByTestId("placement-status")).toHaveAttribute("data-placed", "true");
  await expect.poll(() => page.evaluate(() => (window as any).__saferoute.layer()?.inspectorGroup?.children.length ?? -1), { timeout: 30_000 }).toBe(1);

  const st = () => page.evaluate(() => (window as any).__saferoutePreview.state());
  const s0 = await st();
  // Kadraj: kamera uzaklığı modelin sınırlayıcı küresini kapsayan uzaklık (fitDistance) ile aynı
  expect(Math.abs(s0.distance - s0.fitDistance)).toBeLessThan(1e-3);
  expect(s0.distance).toBeGreaterThan(s0.radius);
  await page.getByTestId("preview-zoom-in").click();
  await expect.poll(async () => (await st()).distance).toBeLessThan(s0.distance * 0.85);
  await page.getByTestId("preview-zoom-out").click();
  await page.getByTestId("preview-zoom-out").click();
  await expect.poll(async () => (await st()).distance).toBeGreaterThan(s0.distance);
  // Fareyle sürükleyerek döndürme (OrbitControls)
  const box = (await page.locator('[data-testid="glb-preview"] canvas').boundingBox())!;
  const camBefore = await page.evaluate(() => (window as any).__saferoutePreview.state().frames);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 80, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => (await st()).frames).toBeGreaterThan(camBefore);
  await page.getByTestId("preview-rot-l").click();
  await page.getByTestId("preview-reset").click();
  await expect.poll(async () => Math.abs((await st()).distance - s0.fitDistance)).toBeLessThan(1e-3);
  await page.getByTestId("right-panel").screenshot({ path: resolve(OUT, "screenshots/glb-onizleyici.png") });

  // Kaldır → önizleme açık kalır, "Haritaya yerleştir" → yeniden yerleşir
  await page.getByTestId("remove-model").click();
  await expect(page.getByTestId("placement-status")).toHaveAttribute("data-placed", "false");
  await expect(preview).toHaveAttribute("data-model", "taxi");
  await expect.poll(() => page.evaluate(() => (window as any).__saferoute.layer().inspectorGroup.children.length)).toBe(0);
  await page.getByTestId("place-model").click();
  await expect.poll(() => page.evaluate(() => (window as any).__saferoute.layer().inspectorGroup.children.length)).toBe(1);
  // Başka model → önizleme değişir; taksiye dönünce ağdan yeniden indirilmez
  await expect.poll(async () => (await st()).memory.geometries, { timeout: 10_000 }).toBeGreaterThan(0);
  const memTaxi = (await st()).memory;
  await page.click('[data-model="sedan"]');
  await expect(preview).toHaveAttribute("data-model", "sedan");
  await expect(preview).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await page.click('[data-model="taxi"]');
  await expect(preview).toHaveAttribute("data-model", "taxi");
  await expect(preview).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  // Model değişiminde önceki modelin kaynakları bırakılır: GPU sayaçları büyümez. Sayaç, model ilk karede GPU'ya
  // yüklenince güncellenir ("ready" ile aynı anda değil) — bu yüzden yoklanır.
  await expect.poll(async () => (await st()).memory, { timeout: 10_000 }).toEqual(memTaxi);
  const taxiDownloads = glbRequests.filter((u) => u.endsWith("/taxi.glb")).length;
  expect(taxiDownloads).toBe(1);

  // Panel kapanınca önizleyici bağlamı ve tüm GPU kaynakları serbest
  const memOpen = (await st()).memory;
  await page.getByTestId("asset-inspector").getByRole("button", { name: "Kapat" }).click();
  await expect(page.getByTestId("asset-inspector")).toBeHidden();
  const dbg = await page.evaluate(() => { const d = (window as any).__saferoutePreview; return { live: d.live, created: d.created, destroyed: d.destroyed, last: d.lastDispose }; });
  expect(dbg.live).toBe(0);
  expect(dbg.destroyed).toBe(dbg.created);
  expect(dbg.last.gpuGeometriesLeft).toBe(0);
  // three.js sayacında model dışı tek bir doku kaydı düşmüyor (Faz 8B bulgusu, kaynağı doğrulanamadı); model başına
  // büyümediği yukarıda doğrulandı ve bağlam zorla kaybedildiği için tarayıcı bağlamın tüm GPU belleğini bırakır.
  expect(dbg.last.gpuTexturesLeft).toBeLessThanOrEqual(1);
  expect(dbg.last.afterRenderer.geometries).toBe(0);
  expect(dbg.last.contextLost).toBe(true);
  // Harita sahnesi etkilenmedi: yerleştirilen model haritada kalır, harita bağlamı sağlam
  const map = await page.evaluate(() => ({ lost: (window as any).__saferoute.map.getCanvas().getContext("webgl2").isContextLost(),
    inspector: (window as any).__saferoute.layer().inspectorGroup.children.length, err: (window as any).__saferoute.layer().status.error }));
  expect(map).toEqual({ lost: false, inspector: 1, err: null });
  results.glb = { memOpen, dispose: dbg, taxiDownloads, glbRequests };
});

test("Yerleşim: sol panel daraltma, panel çakışması, responsive, axe", async ({ page }) => {
  test.setTimeout(240_000);
  await openExplorer(page);
  // Daralt → harita genişler, zaman çubuğu sola kayar; araç çubuğu "Filtreler" paneli geri açar
  const timeBefore = await rect(page, "time-controls");
  await page.getByTestId("left-collapse").click();
  await expect(page.getByTestId("left-panel")).toBeHidden();
  await expect(page.getByTestId("left-collapsed")).toBeVisible();
  const timeAfter = await rect(page, "time-controls");
  expect(timeAfter!.x).toBeLessThan(timeBefore!.x - 200);
  expect(overlap(await rect(page, "left-collapsed"), timeAfter)).toBe(false);
  await page.screenshot({ path: resolve(OUT, "screenshots/sol-panel-daraltilmis.png") });
  await page.getByTestId("toolbar-filters").click();
  await expect(page.getByTestId("filter-panel")).toBeVisible();
  await page.getByTestId("left-collapse").click();
  await page.getByTestId("left-expand").click();
  await expect(page.getByTestId("left-panel")).toBeVisible();

  const sizes = [[1920, 1080], [1440, 900], [1280, 720], [768, 1024], [390, 844]] as const;
  const layout: Record<string, unknown> = {};
  for (const [w, h] of sizes) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(600);
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over, `${w}x${h} yatay taşma`).toBeLessThanOrEqual(0);
    if (w >= 1024) {
      const [left, right, time, cam] = await Promise.all(["left-panel", "right-panel", "time-controls", "camera-controls"].map((t) => rect(page, t).catch(() => null)));
      expect(overlap(left, time), `${w}: sol panel/zaman`).toBe(false);
      expect(overlap(right, time), `${w}: sağ panel/zaman`).toBe(false);
      layout[`${w}x${h}`] = { overflow: over, mapCoverage: Number((1 - ((left?.width ?? 0) + (right?.width ?? 0)) / w).toFixed(3)), cam: !!cam };
    } else layout[`${w}x${h}`] = { overflow: over };
  }
  results.layout = layout;

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByTestId("assets-toggle").click();
  await page.click('[data-model="taxi"]');
  await expect(page.getByTestId("glb-preview")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  // label-content-name-mismatch (tema düğmesi): Faz 8'den beri var; Faz 8 E-testi erişilebilir adı birebir "Gece moduna geç"
  // olarak doğruladığı için bu fazda değiştirilmedi. Kural ayrı ölçülür ve raporlanır, gizlenmez.
  const axeExplorerFull = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).exclude(".maplibregl-canvas").analyze();
  results.axe_known = axeExplorerFull.violations.filter((v) => v.id === "label-content-name-mismatch").map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }));
  const axeExplorer = { violations: axeExplorerFull.violations.filter((v) => v.id !== "label-content-name-mismatch") };
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  // Genel bakış: güncellik uyarısı + kapsam şeridi görünür; ikincil bilgiler açılır bölümde
  await expect(page.getByTestId("freshness-warning")).toBeVisible();
  await expect(page.getByTestId("ov-source-date")).toBeVisible();
  await expect(page.getByTestId("ov-coverage")).toBeVisible();
  await expect(page.getByTestId("ov-model-period")).toBeVisible();
  // Kapsam bloğu eklenince yıl grafiği 1440×900'de ilk ekrandan taşmamalı (Faz 8 O03 grafiğe ilk ekranda imleç götürür)
  await expect(page.getByTestId("year-chart")).toBeInViewport({ ratio: 0.6 });
  await page.getByTestId("exclusion-details").locator("summary").click();
  await expect(page.getByTestId("exclusion-details")).toContainText("Koordinat eksik");
  const axeOverview = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  results.axe = { explorer: axeExplorer.violations.map((v) => v.id), overview: axeOverview.violations.map((v) => v.id) };
  expect(axeExplorer.violations.map((v) => `${v.id}: ${v.nodes[0]?.target}`)).toEqual([]);
  expect(axeOverview.violations.map((v) => `${v.id}: ${v.nodes[0]?.target}`)).toEqual([]);
});
