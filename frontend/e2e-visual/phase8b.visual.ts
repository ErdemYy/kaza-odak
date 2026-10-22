// Faz 8B — önce/sonra görsel karşılaştırma sahneleri. Her sahne SABİT kamera (merkez, zoom, eğim, yön), aynı filtre
// (filtre yok), aynı model (seçili DBSCAN) ve animasyon "kapalı" ile yakalanır; böylece iki çalıştırma piksel düzeyinde
// karşılaştırılabilir. Önizleyici gibi yalnızca yeni sürümde olan öğeler yoksa sahne yine yakalanır ve
// scenes.json'da "yok" olarak kaydedilir (eski sürümde karşılığı olmadığı açıkça görülsün).
import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const OUT = resolve(process.env.SAFEROUTE_PHASE8B_SHOTS ?? "../reports/phase8b/screenshots/after");
mkdirSync(OUT, { recursive: true });
const TILLARY = 1344;
const scenes: Record<string, unknown> = {};

type Cam = { center: [number, number]; zoom: number; pitch: number; bearing: number };
const CAMS: Record<string, Cam> = {
  nyc: { center: [-73.94, 40.7], zoom: 10.3, pitch: 45, bearing: -17 },
  midzoom: { center: [-73.99, 40.735], zoom: 13.4, pitch: 50, bearing: -17 },
  manhattan: { center: [-73.9855, 40.7505], zoom: 15.4, pitch: 60, bearing: 29 },
  glb: { center: [-73.98397, 40.69471], zoom: 19.6, pitch: 62, bearing: 335 },
};

async function idle(page: Page, extra = 900) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && !m.isMoving() && m.areTilesLoaded(); }, null, { timeout: 120_000 });
  await page.waitForTimeout(extra);
}
async function cam(page: Page, c: Cam) {
  await page.evaluate((x) => (window as any).__saferoute.map.jumpTo(x), c);
  await idle(page);
}
const consoleErrors: string[] = [];
async function openExplorer(page: Page) {
  page.on("console", (m) => { if (m.type() === "error" && !/openfreemap|openmaptiles/.test(m.text())) consoleErrors.push(m.text().slice(0, 240)); });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message.slice(0, 240)}`));
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 120_000 });
  const motion = page.getByTestId("motion-select");
  if (await motion.isVisible()) await motion.selectOption("off"); // < 640 px seçici çekmecededir; sahnede araç yok
  await idle(page);
}
async function snap(page: Page, name: string, meta: Record<string, unknown> = {}) {
  await page.screenshot({ path: `${OUT}/${name}.png` });
  scenes[name] = { ...meta, viewport: page.viewportSize() };
}

// Her testten sonra birleştirilerek yazılır (tek bir sahne yeniden çalıştırılsa da diğerleri korunur)
test.afterEach(() => {
  const file = `${OUT}/scenes.json`;
  const prev = existsSync(file) ? JSON.parse(readFileSync(file, "utf-8")).scenes : {};
  scenes.console_errors = [...new Set(consoleErrors)];
  writeFileSync(file, JSON.stringify({ generated_at: new Date().toISOString(), cams: CAMS, scenes: { ...prev, ...scenes } }, null, 2));
});

test("masaüstü 1440×900 sahneleri", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openExplorer(page);
  const renderer = await page.evaluate(() => {
    const gl = (window as any).__saferoute.map.getCanvas().getContext("webgl2");
    const ext = gl?.getExtension("WEBGL_debug_renderer_info");
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "bilinmiyor";
  });
  scenes.renderer = renderer;

  await cam(page, CAMS.nyc);
  await snap(page, "01-nyc-genel", { cam: CAMS.nyc });
  await cam(page, CAMS.midzoom);
  await snap(page, "02-orta-yakinlik-gece", { cam: CAMS.midzoom });
  await cam(page, CAMS.manhattan);
  await snap(page, "03-manhattan-3d-gece", { cam: CAMS.manhattan });

  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(600);
  await cam(page, CAMS.midzoom);
  await snap(page, "04-orta-yakinlik-gunduz", { cam: CAMS.midzoom, theme: "day" });
  await cam(page, CAMS.manhattan);
  await snap(page, "05-manhattan-3d-gunduz", { cam: CAMS.manhattan, theme: "day" });
  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(600);

  // Brooklyn Tillary kümesi (#1344): gerçek tıklama ile seçim, sonra sabit kamera
  const d = await page.evaluate(async (id) => (await fetch(`/api/clusters/${id}`)).json(), TILLARY);
  await cam(page, { center: [d.centroid_lon, d.centroid_lat], zoom: 14.2, pitch: 40, bearing: -17 });
  const [x, y] = await page.evaluate((p) => {
    const m = (window as any).__saferoute.map; const r = m.project(p); const c = m.getCanvas().getBoundingClientRect();
    return [r.x + c.left, r.y + c.top];
  }, [d.centroid_lon, d.centroid_lat]);
  await page.mouse.click(x, y);
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 60_000 });
  await expect(page.getByTestId("sim-note")).toBeVisible({ timeout: 60_000 });
  const selected = await page.evaluate(() => (window as any).__saferoute.selected()?.cluster_id);
  const tillaryCam: Cam = { center: [d.centroid_lon, d.centroid_lat], zoom: 16.6, pitch: 50, bearing: -17 };
  await cam(page, tillaryCam);
  await snap(page, "06-brooklyn-tillary-secili", { cam: tillaryCam, selected });
  await page.getByTestId("right-panel").screenshot({ path: `${OUT}/07-kume-detay-paneli.png` });
  const panel = await page.getByTestId("right-panel").evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));
  scenes["07-kume-detay-paneli"] = { selected, panel };
  const tillaryMid: Cam = { center: [d.centroid_lon, d.centroid_lat], zoom: 13.6, pitch: 45, bearing: -17 };
  await cam(page, tillaryMid);
  await snap(page, "08-secili-kume-orta-yakinlik", { cam: tillaryMid, selected });
  await page.getByTestId("cluster-panel").getByRole("button", { name: "Seçimi kapat" }).click();

  // GLB: önizleyici + haritaya yerleştirilmiş model
  await cam(page, CAMS.glb);
  await page.getByTestId("assets-toggle").click();
  await expect(page.getByTestId("asset-inspector")).toBeVisible();
  await page.click('[data-model="taxi"]');
  await page.getByTestId("insp-heading").fill("3");
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.debugObjects() ?? []).some((o: any) => o.name === "inspector:taxi"), null, { timeout: 60_000 });
  const preview = page.getByTestId("glb-preview");
  const hasPreview = (await preview.count()) > 0;
  if (hasPreview) await expect(preview).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await cam(page, CAMS.glb);
  await page.getByTestId("right-panel").screenshot({ path: `${OUT}/09-glb-onizleyici-paneli.png` });
  scenes["09-glb-onizleyici-paneli"] = { model: "taxi", preview: hasPreview ? "var" : "yok (bu sürümde önizleyici yok)" };
  await snap(page, "10-glb-haritaya-yerlesmis", { cam: CAMS.glb, model: "taxi", heading: 3 });

  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1200);
  await snap(page, "11-genel-bakis");
  await page.screenshot({ path: `${OUT}/11b-genel-bakis-tam.png`, fullPage: true });
});

for (const vp of [{ w: 1920, h: 1080 }, { w: 1280, h: 720 }, { w: 768, h: 1024 }, { w: 390, h: 844 }]) {
  test(`yerleşim ${vp.w}×${vp.h}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await openExplorer(page);
    await cam(page, CAMS.midzoom);
    await snap(page, `12-yerlesim-${vp.w}x${vp.h}`, { cam: CAMS.midzoom });
    if (vp.w === 390) {
      await page.goto("/#/genel-bakis");
      await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
      await page.waitForTimeout(1000);
      await snap(page, "13-mobil-genel-bakis");
    }
  });
}
