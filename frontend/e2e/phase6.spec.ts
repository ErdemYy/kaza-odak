// Faz 6 uçtan uca testleri — GERÇEK çalışan uygulama (FastAPI + derlenmiş ön yüz + OpenFreeMap karoları).
// Demo senaryosu (14 adım), kayıtlı deneyde zaman oynatma (üyelik sabit), filtre/yeniden kümeleme ayrımı, WebGL bağlam
// kaybı + GLB, bağlantı kaybında yeniden deneme, klavye, responsive/yüksek çözünürlük ve axe. Ekran görüntüleri ve
// ölçümler: reports/phase6/ (SAFEROUTE_PHASE6_OUT ile yönlendirilebilir).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.SAFEROUTE_PHASE6_OUT ? resolve(process.env.SAFEROUTE_PHASE6_OUT) : resolve(HERE, "../../reports/phase6");
const SHOTS = resolve(OUT, "screenshots");
mkdirSync(SHOTS, { recursive: true });
const measurements: Record<string, unknown> = {};
const a11y: Record<string, unknown> = {};
const tr = (n: number) => n.toLocaleString("tr-TR");
const api = <T = any>(page: Page, path: string): Promise<T> => page.evaluate(async (p) => (await fetch(p)).json(), path);
const TILLARY = 1344;
const HDBSCAN = "hdbscan-ba3a1ff58d";

test.use({ viewport: { width: 1440, height: 900 } });
test.describe.configure({ mode: "serial" });

async function mapIdle(page: Page, extra = 600) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && m.areTilesLoaded() && !m.isMoving(); }, null, { timeout: 90_000 });
  await page.waitForTimeout(extra);
}
async function openExplorer(page: Page) {
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await mapIdle(page, 1000);
}
const pagePoint = (page: Page, p: [number, number]) => page.evaluate((q) => {
  const m = (window as any).__saferoute.map; const r = m.project(q); const c = m.getCanvas().getBoundingClientRect();
  return [r.x + c.left, r.y + c.top] as [number, number];
}, p);
async function axe(page: Page, name: string) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).exclude(".maplibregl-canvas").analyze();
  a11y[name] = { violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })), passes: r.passes.length };
  return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id);
}
async function shot(page: Page, file: string, full = false) {
  if (full) {
    const vp = page.viewportSize()!;
    const h = await page.evaluate(() => (document.querySelector("main > div:last-child") as HTMLElement | null)?.scrollHeight ?? 0);
    if (h > vp.height) await page.setViewportSize({ width: vp.width, height: Math.min(h, 2600) });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${SHOTS}/${file}` });
    await page.setViewportSize(vp);
  } else await page.screenshot({ path: `${SHOTS}/${file}` });
}
const centroidSnapshot = (page: Page) => page.evaluate(async () => {
  const fc = await (window as any).__saferoute.map.getSource("centroids").getData();
  return fc?.features ? fc.features.map((f: any) => [f.properties.cluster_id, f.geometry.coordinates[0], f.geometry.coordinates[1], f.properties.n_events]) : null;
});

test.afterAll(() => {
  writeFileSync(resolve(OUT, "e2e_measurements.json"), JSON.stringify({ generated_at: new Date().toISOString(), measurements, a11y }, null, 2));
});

test("Demo senaryosu — 14 adım gerçek veri ve kayıtlı deneylerle", async ({ page }) => {
  test.setTimeout(420_000);
  const steps: Record<string, unknown> = {};
  // 1) Uygulama çalışıyor
  const health = await (await page.request.get("/api/health")).json();
  expect(health.status).toBe("ok");
  // 2) Genel bakış
  const t0 = Date.now();
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toContainText("2.020.638", { timeout: 60_000 });
  steps.overview_ready_ms = Date.now() - t0;
  await shot(page, "demo-02-genel-bakis.png");
  // 3) Veri Gezgini: 29 orijinal öznitelik
  await page.goto("/#/veri");
  await expect(page.getByTestId("raw-rows")).toHaveText("2.269.187", { timeout: 60_000 });
  await page.getByTestId("tab-raw").click();
  await expect(page.getByTestId("dict-raw")).toContainText("29 / 29 sütun");
  await shot(page, "demo-03-veri-gezgini-29-oznitelik.png");
  // 4) Ön işleme sonuçları (veri hattı: koordinat temizleme, uygun kayıt, 00:00 bayrağı)
  await page.getByRole("tab").first().click();
  await expect(page.getByTestId("eligible-rows")).toContainText("2.020.638");
  await expect(page.getByTestId("midnight-note")).toContainText("24.566");
  await shot(page, "demo-04-on-isleme.png", true);
  // 5–6) Model karşılaştırma ve DBSCAN sonuçları
  await page.goto("/#/modeller");
  await expect(page.getByTestId("comparison-table")).toBeVisible({ timeout: 60_000 });
  const cmp = await api(page, "/api/models/comparison");
  const db = cmp.rows.find((r: any) => r.algorithm === "dbscan");
  await expect(page.getByTestId("cmp-silhouette-dbscan")).toContainText(db.silhouette.toFixed(3).replace(".", ","));
  await expect(page.getByTestId("cmp-noise-kmeans")).toHaveText("Uygulanamaz");
  await expect(page.getByTestId("cmp-clusters-hdbscan")).toContainText("örneklem");
  await expect(page.getByTestId("dbscan-grid")).toBeVisible();
  await shot(page, "demo-06-model-karsilastirma-dbscan.png");
  // 7–8) 3D Şehir Keşfi → Brooklyn
  await openExplorer(page);
  await page.getByTestId("tab-view").click();
  await page.locator('[data-borough="BROOKLYN"]').click();
  await mapIdle(page, 1200);
  await shot(page, "demo-08-brooklyn.png");
  // 9–10) Tillary St / Flatbush Ave Ext kümesi (#1344) ve gerçek istatistikleri
  const c = await api(page, `/api/clusters/${TILLARY}`);
  expect(c.top_streets[0].value).toContain("TILLARY");
  await page.evaluate(([lon, lat]) => (window as any).__saferoute.map.jumpTo({ center: [lon, lat], zoom: 14.2 }), [c.centroid_lon, c.centroid_lat]);
  await mapIdle(page, 800);
  const [x, y] = await pagePoint(page, [c.centroid_lon, c.centroid_lat]);
  await page.mouse.click(x, y);
  await expect(page.getByTestId("cluster-title")).toContainText(String(TILLARY), { timeout: 30_000 });
  await expect(page.getByTestId("cluster-events")).toContainText(tr(c.n_events));
  await expect(page.getByTestId("cluster-borough")).toContainText("Brooklyn");
  await mapIdle(page, 2500);
  await shot(page, "demo-10-tillary-kumesi.png");
  steps.tillary = { cluster_id: TILLARY, n_events: c.n_events, injury_crashes: c.injury_crashes, peak_hour: c.peak_hour };
  // 11–12) Kümeleme Laboratuvarı → önceden hesaplanmış DBSCAN deneyi
  await page.goto("/#/laboratuvar");
  await page.getByTestId("tab-saved").click();
  const exps = await api(page, "/api/experiments");
  const grid = exps.experiments.find((e: any) => e.algorithm === "dbscan" && e.stage === "dbscan_grid" && e.has_labels && e.experiment_id !== "dbscan-52abd2c018");
  await page.locator(`[data-experiment="${grid.experiment_id}"]`).first().click();
  await expect(page.getByTestId("saved-view")).toHaveAttribute("data-experiment", grid.experiment_id);
  const gs = (await api(page, `/api/results/${grid.experiment_id}/summary`)).summary;
  await expect(page.getByTestId("result-clusters")).toContainText(tr(gs.n_clusters), { timeout: 60_000 });
  steps.saved_dbscan = { experiment_id: grid.experiment_id, params: grid.params, n_clusters: gs.n_clusters, noise_ratio: gs.noise_ratio };
  await shot(page, "demo-12-kayitli-dbscan.png", true);
  // 13–14) Kaynak uygunsa gerçek küçük kapsamlı dinamik analiz (Manhattan 2018, eps 35 m, min_samples 15)
  await openExplorer(page);
  await page.getByTestId("tab-filters").click();
  await page.getByTestId("f-borough-MANHATTAN").click();
  await page.getByTestId("f-year-2018").click();
  await page.getByTestId("filter-to-lab").click();
  await expect(page.getByTestId("lab-filter-scope")).toBeVisible();
  await page.getByTestId("lab-algo-dbscan").click();
  await page.getByTestId("lab-param-eps_m").fill("35");
  await page.getByTestId("lab-param-min_samples").fill("15");
  const res = await api(page, "/api/lab/resources");
  steps.resources_at_submit = res;
  const tj = Date.now();
  await page.getByTestId("lab-submit").click();
  if (res.can_start) {
    await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", /completed/, { timeout: 180_000 });
    const jobId = await page.getByTestId("job-view").getAttribute("data-job");
    const job = await api(page, `/api/lab/jobs/${jobId}`);
    const scope = await api(page, "/api/records/summary?boroughs=MANHATTAN&years=2018");
    expect(job.n_events).toBe(scope.n_events);
    expect(job.experiment_id).toMatch(/^dyn-|^dbscan-/);
    await expect(page.getByTestId("result-clusters")).toContainText(tr(job.result.summary.n_clusters));
    await expect(page.getByTestId("result-dbcv")).toContainText(job.source === "phase3_registry" ? "," : "N/A");
    steps.dynamic = { ms: Date.now() - tj, job_id: jobId, experiment_id: job.experiment_id, source: job.source, n_events: job.n_events,
      n_clusters: job.result.summary.n_clusters, noise_ratio: job.result.summary.noise_ratio, worker: job.worker };
    await shot(page, "demo-14-dinamik-analiz.png", true);
    await page.getByTestId("show-on-map").click();
    await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "result");
    await mapIdle(page, 1500);
    await shot(page, "demo-14b-dinamik-sonuc-haritada.png");
  } else {
    await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "resource_limited", { timeout: 30_000 });
    await expect(page.getByTestId("job-rejected")).toContainText("Bellek yetersiz");
    steps.dynamic = { skipped: `boş bellek ${res.available_memory_mb} MB < ${res.min_free_memory_mb} MB — iş çalıştırılmadı, açık mesaj gösterildi` };
    await shot(page, "demo-13-kaynak-siniri.png", true);
  }
  measurements.demo = steps;
});

test("Zaman oynatma — kayıtlı HDBSCAN deneyinde üyelik sabit, kapsam aşılmaz", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/#/laboratuvar");
  await page.getByTestId("tab-saved").click();
  await page.locator(`[data-experiment="${HDBSCAN}"]`).first().click();
  await expect(page.getByTestId("result-clusters")).toContainText("768", { timeout: 60_000 });
  await page.getByTestId("show-on-map").click();
  await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "result");
  await expect(page.getByTestId("result-scope-note")).toContainText("kayıt filtreleri bu görünüme uygulanmaz");
  await expect(page.getByTestId("time-coverage")).toContainText("100.000 olay", { timeout: 60_000 });
  await expect(page.getByTestId("time-recluster")).toContainText("Hayır");
  await mapIdle(page, 1000);
  const density = await api(page, `/api/results/${HDBSCAN}/density?cell=1000`);
  expect(density.total_events).toBe(100_000); // 100k örneklem tüm NYC verisi gibi gösterilmez
  const full = await centroidSnapshot(page);
  const pos = new Map((full ?? []).map((r: any) => [r[0], `${r[1]},${r[2]}`]));
  const tl = await api(page, `/api/results/${HDBSCAN}/timeline?granularity=year`);
  const steps: unknown[] = [];
  await page.getByTestId("time-play").click(); // ilk kovaya geçer ve oynatır
  await page.getByTestId("time-play").click(); // duraklat
  for (let i = 0; i < 3; i++) {
    const readout = await page.getByTestId("time-readout").textContent();
    const key = /(\d{4})/.exec(readout ?? "")?.[1];
    const bucket = tl.buckets.find((b: any) => b.key === key);
    expect(bucket, `kova ${key}`).toBeTruthy();
    await expect(page.getByTestId("time-readout")).toContainText(`${tr(bucket.count)} görünür olay`);
    await expect(page.getByTestId("load-status")).toContainText("bu dilimde", { timeout: 30_000 });
    await mapIdle(page, 600);
    const snap = await centroidSnapshot(page);
    const sliced = await api(page, `/api/results/${HDBSCAN}/clusters?years=${key}`);
    expect(snap!.length).toBe(sliced.returned);
    expect(sliced.time_slice.visible_events).toBe(bucket.count);
    for (const r of snap!) expect(pos.get(r[0])).toBe(`${r[1]},${r[2]}`);  // merkez/üyelik değişmez
    steps.push({ year: key, visible_events: bucket.count, clusters_with_events: sliced.returned });
    if (i === 1) await page.screenshot({ path: `${SHOTS}/12-zaman-oynatma-kayitli-hdbscan.png` });
    await page.getByRole("button", { name: "Sonraki adım" }).click();
  }
  // Saat ölçeği: 00:00 kovası uyarı renginde, bilgi notu korunur
  await page.getByTestId("time-g-hour").click();
  await expect(page.locator('button[title^="00:00"]')).toHaveClass(/bg-warning/);
  expect(await axe(page, "explorer-result-playback")).toEqual([]);
  measurements.time_playback = { experiment: HDBSCAN, coverage: tl.coverage, steps, reclustered: tl.reclustered };
  await page.getByTestId("mode-banner").getByRole("button", { name: /Seçili model/ }).click();
});

test("Mod A / Mod B ayrımı — filtre etiketleri korur; dinamik sonuç ayrı deney kimliğinde", async ({ page }) => {
  await openExplorer(page);
  await page.getByTestId("tab-filters").click();
  await page.getByTestId("f-borough-BROOKLYN").click();
  await page.getByTestId("filter-apply").click();
  await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "filtered", { timeout: 30_000 });
  await expect(page.getByTestId("mode-banner")).toContainText("yeniden kümeleme yapılmadı");
  await mapIdle(page, 800);
  const rc = await api(page, "/api/records/clusters?boroughs=BROOKLYN");
  const snap = await centroidSnapshot(page);
  expect(snap!.length).toBe(rc.returned);
  expect(rc.experiment_id).toBe("dbscan-52abd2c018");
  const full = await api(page, "/api/clusters");
  const ids = new Set(full.features.map((f: any) => f.properties.cluster_id));
  for (const r of snap!) expect(ids.has(r[0])).toBe(true);  // yalnızca mevcut modelin küme kimlikleri
  const r = await page.request.get("/api/results/dbscan-52abd2c018/clusters?boroughs=BROOKLYN");
  expect(r.status()).toBe(422); // sonuç uç noktası kayıt filtresiyle birleştirilmez
  measurements.mode_a = { returned: rc.returned, events_in_clusters: rc.events_in_clusters };
  await page.getByTestId("filter-reset").click();
});

test("WebGL bağlam kaybı sonrası toparlanma ve GLB modelleri", async ({ page }) => {
  test.setTimeout(240_000);
  await openExplorer(page);
  const c = await api(page, `/api/clusters/${TILLARY}`);
  await page.evaluate(([lon, lat]) => (window as any).__saferoute.map.jumpTo({ center: [lon, lat], zoom: 14.2 }), [c.centroid_lon, c.centroid_lat]);
  await mapIdle(page, 600);
  const [x, y] = await pagePoint(page, [c.centroid_lon, c.centroid_lat]);
  await page.mouse.click(x, y);
  await expect(page.getByTestId("cluster-title")).toContainText(String(TILLARY), { timeout: 30_000 });
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.status.loaded.length ?? 0) > 0, null, { timeout: 90_000 });
  const glb = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.endsWith(".glb"))
    .map((e: any) => ({ file: e.name.split("/").pop(), ms: Math.round(e.duration), bytes: e.encodedBodySize })));
  const loaded = await page.evaluate(() => (window as any).__saferoute.layer().status.loaded);
  expect(glb.length).toBeGreaterThan(0);
  await mapIdle(page, 1500);
  await page.screenshot({ path: `${SHOTS}/13-glb-sahne-oncesi.png` });
  const t0 = Date.now();
  await page.evaluate(() => {
    const gl = (window as any).__saferoute.map.painter.context.gl;
    (window as any).__lose = gl.getExtension("WEBGL_lose_context");
    (window as any).__lose.loseContext();
  });
  await expect(page.getByTestId("load-status")).toContainText("kaybedildi", { timeout: 20_000 });
  await page.waitForTimeout(500);
  await page.evaluate(() => (window as any).__lose.restoreContext());
  await expect(page.getByTestId("load-status")).toContainText("geri yüklendi", { timeout: 60_000 });
  await page.waitForFunction(() => (window as any).__saferoute.layer()?.status.ready === true, null, { timeout: 60_000 });
  const recoveryMs = Date.now() - t0;
  await mapIdle(page, 1500);
  const after = await page.evaluate(() => {
    const m = (window as any).__saferoute.map;
    return { cityModels: !!m.getLayer("city-models"), centroids: m.querySourceFeatures("centroids").length,
      layerReady: (window as any).__saferoute.layer().status.ready, contextLost: (window as any).__saferoute.layer().status.contextLost };
  });
  expect(after.cityModels && after.layerReady && !after.contextLost).toBe(true);
  expect(after.centroids).toBeGreaterThan(0);
  await page.screenshot({ path: `${SHOTS}/14-webgl-toparlanma-sonrasi.png` });
  measurements.webgl_recovery = { recovery_ms: recoveryMs, after, glb_loaded: loaded, glb_requests: glb };
});

test("Bağlantı kaybı: iş durumu otomatik yeniden denenir; harita veri hatası gösterilir ve toparlanır", async ({ page }) => {
  await page.goto("/#/laboratuvar");
  await expect(page.getByTestId("lab-submit")).toBeVisible({ timeout: 60_000 });
  await page.getByTestId("lab-algo-dbscan").click();
  await page.getByTestId("lab-param-eps_m").fill("25");
  await page.getByTestId("lab-param-min_samples").fill("100");
  await page.getByTestId("lab-submit").click(); // kayıtlı sonuç (anında tamamlanır)
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 30_000 });
  const jobId = await page.getByTestId("job-view").getAttribute("data-job");
  let blocked = 0;
  await page.route(`**/api/lab/jobs/${jobId}`, (r) => { blocked++; return r.abort("connectionrefused"); });
  await page.getByTestId("tab-saved").click();
  await page.getByTestId("tab-history").click();
  await page.getByTestId("job-history").locator("button", { hasText: jobId! }).first().click();
  await expect(page.getByTestId("job-reconnecting")).toContainText("yeniden deneniyor", { timeout: 20_000 });
  await page.screenshot({ path: `${SHOTS}/15-baglanti-kaybi-yeniden-deneme.png` });
  await page.unroute(`**/api/lab/jobs/${jobId}`);
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 30_000 });
  await expect(page.getByTestId("job-reconnecting")).toHaveCount(0);
  // Harita veri isteği başarısız → açık hata; bağlantı dönünce yeni istekle toparlanır
  await openExplorer(page);
  await page.route("**/api/records/**", (r) => r.abort("connectionrefused"));
  await page.getByTestId("tab-filters").click();
  await page.getByTestId("f-borough-QUEENS").click();
  await page.getByTestId("filter-apply").click();
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "error", { timeout: 30_000 });
  await expect(page.getByTestId("load-status")).toContainText("ulaşılamadı");
  await page.unroute("**/api/records/**");
  await page.getByTestId("f-borough-BRONX").click();
  await page.getByTestId("filter-apply").click();
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  measurements.connection_loss = { blocked_job_requests: blocked, recovered: true };
  await page.getByTestId("filter-reset").click();
});

test("Klavye gezinmesi: atlama bağlantısı, menü, zaman kaydırıcısı", async ({ page }) => {
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toHaveText("İçeriğe geç");
  await page.keyboard.press("Enter");
  expect(await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName)).toMatch(/main/i);
  const nav = page.getByTestId("navigation").getByRole("link", { name: /Kümeleme Laboratuvarı/ });
  await nav.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/laboratuvar/);
  await openExplorer(page);
  const range = page.getByTestId("time-range");
  await range.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("time-readout")).toContainText("kayıt");
  const v = await range.getAttribute("aria-valuetext");
  expect(v).toMatch(/\d{4}, [\d.]+ kayıt/);
  await page.getByTestId("time-clear").click();
});

const VIEWPORTS = [
  { name: "telefon", width: 390, height: 844, dsf: 3 },
  { name: "tablet", width: 820, height: 1180, dsf: 2 },
  { name: "dizustu", width: 1280, height: 800, dsf: 1 },
  { name: "genis", width: 1920, height: 1080, dsf: 1 },
  { name: "yuksek-cozunurluk", width: 2560, height: 1440, dsf: 2 },
];
for (const vp of VIEWPORTS) {
  test(`Responsive ${vp.name} ${vp.width}×${vp.height}@${vp.dsf}x: 5 ekranda yatay taşma yok`, async ({ browser }) => {
    test.setTimeout(240_000);
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.dsf });
    const page = await ctx.newPage();
    const result: Record<string, unknown> = {};
    for (const [hash, id] of [["genel-bakis", "overview"], ["kesif", "explorer"], ["laboratuvar", "lab"], ["modeller", "models"], ["veri", "data"]] as const) {
      await page.goto(`/#/${hash}`);
      if (id === "explorer") {
        await page.waitForFunction(() => document.querySelector('[data-testid="time-controls"]'), null, { timeout: 90_000 });
        await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded(); }, null, { timeout: 90_000 });
      } else await page.waitForSelector(`[data-testid="${id === "data" ? "data-explorer" : id}"]`, { timeout: 60_000 });
      await page.waitForTimeout(900);
      const o = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        body: document.body.scrollWidth - document.body.clientWidth }));
      result[id] = o;
      expect(o.doc, `${vp.name}/${id} belge taşması`).toBeLessThanOrEqual(0);
      if (id === "explorer" || id === "overview") await page.screenshot({ path: `${SHOTS}/16-${vp.name}-${id}.png` });
    }
    if (vp.width >= 1280) {
      // Panel çakışması: sol panel, sağ panel, alt zaman çubuğu birbirine binmez; harita alanı görünür kalır
      await page.goto("/#/kesif");
      await page.waitForSelector('[data-testid="left-panel"]', { timeout: 60_000 });
      const boxes = await page.evaluate(() => Object.fromEntries(["left-panel", "right-panel", "time-controls", "camera-controls"].map((t) => {
        const r = document.querySelector(`[data-testid="${t}"]`)?.getBoundingClientRect();
        return [t, r ? { x: r.x, y: r.y, w: r.width, h: r.height } : null];
      })));
      const L = boxes["left-panel"]!, T = boxes["time-controls"]!;
      expect(T.x).toBeGreaterThanOrEqual(L.x + L.w - 1);
      const mapFree = vp.width - (L.w + 24) - 352;
      expect(mapFree).toBeGreaterThan(vp.width * 0.4);
      result.boxes = boxes;
    }
    measurements[`responsive_${vp.name}`] = result;
    await ctx.close();
  });
}

test("Erişilebilirlik (axe) — beş ekran", async ({ page }) => {
  test.setTimeout(240_000);
  const out: Record<string, string[]> = {};
  for (const [hash, sel] of [["genel-bakis", "overview"], ["laboratuvar", "lab"], ["modeller", "comparison-table"], ["veri", "data-explorer"]] as const) {
    await page.goto(`/#/${hash}`);
    await page.waitForSelector(`[data-testid="${sel}"]`, { timeout: 60_000 });
    await page.waitForTimeout(800);
    out[hash] = await axe(page, hash);
  }
  await openExplorer(page);
  out.kesif = await axe(page, "kesif");
  for (const [k, v] of Object.entries(out)) expect(v, `axe ${k}`).toEqual([]);
});
