// Faz 5 uçtan uca testleri — GERÇEK çalışan uygulama (FastAPI + derlenmiş ön yüz + OpenFreeMap karoları).
// Arayüzdeki her sayı aynı anda API'den alınan değerle karşılaştırılır. Ekran görüntüleri: reports/phase5/screenshots/
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "../../reports/phase5");
const SHOTS = resolve(OUT, "screenshots");
mkdirSync(SHOTS, { recursive: true });
const measurements: Record<string, unknown> = {};
const a11y: Record<string, unknown> = {};
const tr = (n: number) => n.toLocaleString("tr-TR");
const api = <T = any>(page: Page, path: string): Promise<T> => page.evaluate(async (p) => (await fetch(p)).json(), path);

test.use({ viewport: { width: 1440, height: 900 } });
test.describe.configure({ mode: "serial" });

async function mapIdle(page: Page, extra = 600) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && m.areTilesLoaded() && !m.isMoving(); }, null, { timeout: 90_000 });
  await page.waitForTimeout(extra);
}
async function openExplorer(page: Page) {
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await mapIdle(page, 1200);
}
/** Kaydırma kabının tamamını yakalamak için görünüm yüksekliği geçici olarak büyütülür. */
async function fullShot(page: Page, file: string) {
  const vp = page.viewportSize()!;
  const h = await page.evaluate(() => (document.querySelector("main > div:last-child") as HTMLElement | null)?.scrollHeight ?? 0);
  if (h > vp.height) await page.setViewportSize({ width: vp.width, height: Math.min(h + (vp.width < 768 ? 48 : 0), 7000) });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/${file}` });
  await page.setViewportSize(vp);
}
const pagePoint = (page: Page, p: [number, number]) => page.evaluate((q) => {
  const m = (window as any).__saferoute.map; const r = m.project(q); const c = m.getCanvas().getBoundingClientRect();
  return [r.x + c.left, r.y + c.top] as [number, number];
}, p);
async function axe(page: Page, name: string) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).exclude(".maplibregl-canvas").analyze();
  const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  a11y[name] = { violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })), passes: r.passes.length };
  return bad;
}

test("1 — Genel bakış: tüm sayılar API ile aynı, güncellik uyarısı, fontlar", async ({ page }) => {
  const t0 = Date.now();
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  measurements.overview_ready_ms = Date.now() - t0;
  const ov = await api(page, "/api/overview");
  await expect(page.getByTestId("hero-eligible")).toHaveText(tr(ov.records.eligible));
  await expect(page.getByTestId("ov-clusters")).toContainText(tr(ov.model.clusters));
  await expect(page.getByTestId("ov-model")).toContainText(ov.model.experiment_id);
  await expect(page.getByTestId("ov-coverage")).toContainText(ov.coverage.date_min);
  expect(ov.records.raw_total).toBe(2269187);
  if (ov.source.freshness.verdict_at_check === "stale") await expect(page.getByTestId("freshness-warning")).toBeVisible();
  const rows = page.getByTestId("borough-table").locator("tbody tr");
  await expect(rows).toHaveCount(5);
  const bk = ov.by_borough.find((b: any) => b.borough === "BROOKLYN");
  await expect(rows.filter({ hasText: "Brooklyn" })).toContainText(tr(bk.events));
  await expect(page.getByTestId("top-clusters").locator("tbody tr")).toHaveCount(10);
  await expect(page.getByTestId("year-chart")).toBeVisible();
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    return { jakarta: document.fonts.check('700 28px "Plus Jakarta Sans"'), manrope: document.fonts.check('400 14px "Manrope"'),
      h1: getComputedStyle(document.querySelector("h1")!).fontFamily, body: getComputedStyle(document.body).fontFamily };
  });
  expect(fonts.jakarta && fonts.manrope).toBe(true);
  expect(fonts.h1).toContain("Plus Jakarta Sans");
  expect(fonts.body).toContain("Manrope");
  measurements.fonts = fonts;
  expect(await axe(page, "overview")).toEqual([]);
  await fullShot(page, "01-genel-bakis.png");
});

test("2 — 3D Şehir: Faz 4 haritası korunur; filtre gerçek kayıtları sorgular; mod ayrımı açık", async ({ page }) => {
  await openExplorer(page);
  const meta = await api(page, "/api/meta");
  await expect(page.getByTestId("meta-clusters")).toHaveText(tr(meta.counts.clusters));
  expect(await page.evaluate(() => (window as any).__saferoute.map.querySourceFeatures("centroids").length)).toBeGreaterThan(1000);
  await expect(page.getByTestId("mode-banner")).toHaveCount(0); // filtresiz model: bant yok
  await page.screenshot({ path: `${SHOTS}/02-3d-sehir-kesfi.png` });
  expect(await axe(page, "explorer")).toEqual([]);

  // Filtre: Brooklyn + bisiklet + yaralanmalı
  await page.getByTestId("tab-filters").click();
  await page.getByTestId("f-borough-BROOKLYN").click();
  await page.getByTestId("f-vehicle-BICYCLE").click();
  await page.getByRole("radio", { name: "Yaralanmalı" }).click();
  const q = "boroughs=BROOKLYN&vehicles=BICYCLE&injury=injury";
  const summary = await api(page, `/api/records/summary?${q}`);
  await expect(page.getByTestId("filter-preview")).toContainText(tr(summary.n_events), { timeout: 15_000 });
  let requests = 0;
  page.on("request", (r) => { if (r.url().includes("/api/records/")) requests++; });
  const t0 = Date.now();
  await page.getByTestId("filter-apply").click();
  await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "filtered");
  await expect(page.getByTestId("mode-banner")).toContainText("yeniden kümeleme yapılmadı");
  await expect(page.getByTestId("load-status")).toContainText(tr(summary.n_events), { timeout: 30_000 });
  measurements.filter_apply_to_layers_ms = Date.now() - t0;
  await mapIdle(page);
  const clusters = await api(page, `/api/records/clusters?${q}`);
  const onMap = await page.evaluate(() => {
    const m = (window as any).__saferoute.map;
    const ids = new Set(m.querySourceFeatures("centroids").map((f: any) => f.properties.cluster_id));
    return ids.size;
  });
  // Haritadaki küme merkezleri = filtrelenmiş kayıt içeren gerçek kümeler; etiketler tam veri modelinden
  expect(onMap).toBe(clusters.returned);
  expect(clusters.label_source).toContain("yeniden kümeleme yok");
  expect(summary.model.clusters_with_events).toBe(clusters.returned);
  await expect(page.getByTestId("filtered-cluster-count")).toHaveCount(0); // görünüm sekmesinde
  measurements.filter_change_api_requests = requests;
  await page.screenshot({ path: `${SHOTS}/03-filtre-uygulanmis.png` });

  // Filtreli küme seçimi: tam küme ve filtrelenmiş kayıtlar ayrı
  const top = clusters.features.sort((a: any, b: any) => b.properties.n_events - a.properties.n_events)[0].properties;
  const full = await api(page, `/api/clusters/${top.cluster_id}`);
  await page.evaluate((c) => (window as any).__saferoute.map.jumpTo({ center: c, zoom: 14.5, pitch: 40 }), [full.centroid_lon, full.centroid_lat]);
  await mapIdle(page);
  const pt = await pagePoint(page, [full.centroid_lon, full.centroid_lat]);
  await page.mouse.click(pt[0], pt[1]);
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 30_000 });
  await expect(page.getByTestId("cluster-title")).toContainText(`Küme #${top.cluster_id}`);
  await expect(page.getByTestId("cluster-events")).toHaveText(tr(full.n_events));
  await expect(page.getByTestId("cluster-filtered-events")).toHaveText(tr(top.n_events));
  await page.waitForTimeout(3500);
  await mapIdle(page, 1500);
  await page.screenshot({ path: `${SHOTS}/04-kume-secili.png` });
  await page.getByTestId("right-panel").screenshot({ path: `${SHOTS}/04b-kume-detay-paneli.png` });
});

test("3 — Zaman oynatma gerçek kayıtlara dayanır; görünen kaza katmanı değişir", async ({ page }) => {
  await openExplorer(page);
  await page.getByTestId("time-g-hour").click();
  const tl = await api(page, "/api/records/timeline?granularity=hour");
  expect(tl.buckets).toHaveLength(24);
  expect(tl.buckets.reduce((a: number, b: any) => a + b.count, 0)).toBe(tl.n_events);
  await page.getByRole("button", { name: "Sonraki adım" }).click(); // 00
  await page.getByRole("button", { name: "Sonraki adım" }).click(); // 01
  await expect(page.getByTestId("time-readout")).toContainText(`${tr(tl.buckets[1].count)} kayıt`);
  await expect(page.getByTestId("mode-banner")).toContainText("Zaman dilimi");
  await expect(page.getByTestId("load-status")).toContainText(tr(tl.buckets[1].count), { timeout: 30_000 });
  await mapIdle(page);
  const density = await page.evaluate(() => {
    const feats = (window as any).__saferoute.map.querySourceFeatures("density");
    const seen = new Set<string>(); let s = 0;
    for (const f of feats) { const k = JSON.stringify(f.geometry.coordinates); if (!seen.has(k)) { seen.add(k); s += f.properties.events; } }
    return s;
  });
  expect(density).toBeLessThanOrEqual(tl.buckets[1].count); // ekranda kalan hücreler: alt küme
  expect(density).toBeGreaterThan(0);
  await page.screenshot({ path: `${SHOTS}/05-zaman-oynatma-saat.png` });
  await page.getByTestId("time-clear").click();
  await expect(page.getByTestId("mode-banner")).toHaveCount(0);
});

test("4 — Laboratuvar: kayıtlı konfigürasyon, parametre denetimleri, bütçe, dinamik iş, haritada sonuç", async ({ page }) => {
  await page.goto("/#/laboratuvar");
  await expect(page.getByTestId("lab-submit")).toBeVisible({ timeout: 60_000 });
  const all = await api(page, "/api/records/summary");
  await expect(page.getByTestId("lab-scope-count")).toHaveText(tr(all.n_events));
  // Varsayılan DBSCAN 25/100, filtresiz → Faz 3 kaydı
  await expect(page.getByTestId("lab-registry-hint")).toContainText("dbscan-52abd2c018");
  await page.getByTestId("lab-submit").click();
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 30_000 });
  await expect(page.getByTestId("job-source")).toContainText("dbscan-52abd2c018");
  await expect(page.getByTestId("result-clusters")).toContainText("4.179");
  // Parametre denetimleri
  await page.getByTestId("lab-param-eps_m").fill("700");
  await expect(page.getByText("5–500 aralığında olmalı.")).toBeVisible();
  await expect(page.getByTestId("lab-submit")).toBeDisabled();
  await page.getByTestId("lab-param-eps_m").fill("25");
  await page.getByTestId("lab-algo-kmeans").click();
  await expect(page.getByTestId("lab-fs-spatiotemporal")).toHaveAttribute("data-disabled", "true");
  await expect(page.getByTestId("lab-fs-reason-spatiotemporal")).toContainText("Desteklenmiyor");
  await page.getByTestId("lab-param-k").fill("1");
  await expect(page.getByText("2–200 aralığında olmalı.")).toBeVisible();
  await page.getByTestId("lab-param-k").fill("8");
  await page.getByTestId("lab-algo-hdbscan").click();
  await page.getByLabel("Basit rastgele olay örneklemi kullan").click(); // örneklemi kapat → bütçe aşılır
  await expect(page.getByTestId("lab-budget-block")).toContainText("bütçe");
  await expect(page.getByTestId("lab-submit")).toBeDisabled();
  await fullShot(page, "06-kumeleme-laboratuvari.png");
  expect(await axe(page, "lab")).toEqual([]);

  // Filtre kapsamında YENİ DBSCAN (dinamik iş, ayrı süreç) → haritada sonuç
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await page.getByTestId("tab-filters").click();
  await page.getByTestId("f-borough-STATEN ISLAND").click();
  await page.getByTestId("f-year-2019").click();
  await page.getByTestId("filter-to-lab").click();
  await expect(page.getByTestId("lab-filter-scope")).toBeVisible();
  const scope = await api(page, "/api/records/summary?boroughs=STATEN%20ISLAND&years=2019");
  await expect(page.getByTestId("lab-scope-count")).toHaveText(tr(scope.n_events));
  await page.getByTestId("lab-param-eps_m").fill("40");
  await page.getByTestId("lab-param-min_samples").fill("8");
  const prevJob = await page.getByTestId("job-view").getAttribute("data-job").catch(() => null);
  const t0 = Date.now();
  await page.getByTestId("lab-submit").click();
  await expect(page.getByTestId("job-view")).not.toHaveAttribute("data-job", prevJob ?? "-", { timeout: 30_000 });
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 120_000 });
  measurements.dynamic_dbscan_job_ms = Date.now() - t0;
  const jobId = await page.getByTestId("job-view").getAttribute("data-job");
  const job = await api(page, `/api/lab/jobs/${jobId}`);
  expect(job.request.filters).toMatchObject({ boroughs: ["STATEN ISLAND"], years: [2019] }); // sunucunun kanonik filtre biçimi
  expect(job.n_events).toBe(scope.n_events);
  await expect(page.getByTestId("result-clusters")).toContainText(tr(job.result.summary.n_clusters));
  measurements.dynamic_dbscan_worker = job.worker;
  await fullShot(page, "07-dinamik-analiz-sonucu.png");
  await page.getByTestId("show-on-map").click();
  await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "result");
  await expect(page.getByTestId("result-id")).toHaveText(`lab-${jobId}`);
  await expect(page.getByTestId("time-controls")).toHaveAttribute("data-state", "disabled");
  await mapIdle(page, 1500);
  expect(await page.evaluate(() => new Set((window as any).__saferoute.map.querySourceFeatures("centroids").map((f: any) => f.properties.cluster_id)).size))
    .toBe(job.result.summary.n_clusters);
  await page.screenshot({ path: `${SHOTS}/08-dinamik-sonuc-haritada.png` });
  await page.getByTestId("back-to-model").click();
  await expect(page.getByTestId("model-params")).toBeVisible();
});

test("5 — Laboratuvar: kayıtlı deney seçimi, iş iptali, API hata durumu", async ({ page }) => {
  await page.goto("/#/laboratuvar");
  await page.getByTestId("tab-saved").click();
  await page.locator('[data-experiment="kmeans-24c07e9946"]').first().click();
  await expect(page.getByTestId("saved-view")).toHaveAttribute("data-experiment", "kmeans-24c07e9946");
  await expect(page.getByTestId("result-noise")).toContainText("Uygulanamaz");
  await expect(page.getByTestId("result-clusters")).toContainText("5");
  // İptal: büyük HDBSCAN örneklemi gerçek süreçte başlar, iptal edilir
  await page.getByTestId("lab-algo-hdbscan").click();
  await page.getByTestId("lab-param-min_cluster_size").fill("12");
  await page.getByTestId("lab-param-min_samples").fill("7");
  await page.getByTestId("lab-sample-n").fill("95000");
  await page.getByTestId("lab-submit").click();
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", /running|pending|completed/, { timeout: 30_000 });
  const state = await page.getByTestId("job-state").getAttribute("data-state");
  if (state !== "completed") {
    await expect(page.getByTestId("job-stage")).toBeVisible();
    await page.getByTestId("job-cancel").click();
    await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "cancelled", { timeout: 30_000 });
  }
  measurements.cancel_tested = state !== "completed";
  // Sunucu hatası: laboratuvar isteği 429 → kullanıcıya mesaj
  await page.route("**/api/lab/jobs", (r) => r.request().method() === "POST"
    ? r.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ detail: "Kuyrukta 3 iş bekliyor" }) }) : r.continue());
  await page.getByTestId("lab-sample-n").fill("94000");
  await page.getByTestId("lab-submit").click();
  await expect(page.getByTestId("lab-submit-error")).toContainText("Kuyrukta 3 iş bekliyor");
  await page.route("**/api/overview", (r) => r.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Olay deposu yükleniyor" }) }));
  await page.goto("/#/genel-bakis");
  await expect(page.getByRole("alert")).toContainText("Olay deposu yükleniyor", { timeout: 30_000 });
});

test("6 — Model karşılaştırma: gerçek metrikler, kapsamlar, uygunsuz dönüşüm yok", async ({ page }) => {
  await page.goto("/#/modeller");
  await expect(page.getByTestId("comparison-table")).toBeVisible({ timeout: 60_000 });
  const cmp = await api(page, "/api/models/comparison");
  const db = cmp.rows.find((r: any) => r.algorithm === "dbscan");
  await expect(page.getByTestId("cmp-silhouette-dbscan")).toContainText(db.silhouette.toFixed(3).replace(".", ","));
  await expect(page.getByTestId("cmp-silhouette-dbscan")).not.toContainText("%");
  await expect(page.getByTestId("cmp-noise-kmeans")).toHaveText("Uygulanamaz");
  await expect(page.getByTestId("cmp-clusters-hdbscan")).toContainText("örneklem");
  await expect(page.getByTestId("comparison-caveats")).toContainText("100.000");
  await expect(page.getByTestId("dbscan-grid").locator("td")).toHaveCount(20);
  expect(await axe(page, "models")).toEqual([]);
  await fullShot(page, "09-model-karsilastirma.png");
});

test("7 — Veri gezgini: 29 ham / 87 işlenmiş sütun, öznitelik açıklaması, 00:00 bayrağı", async ({ page }) => {
  await page.goto("/#/veri");
  await expect(page.getByTestId("raw-rows")).toHaveText("2.269.187", { timeout: 60_000 });
  await expect(page.getByTestId("midnight-note")).toContainText("24.566");
  await fullShot(page, "10-veri-gezgini-hat.png");
  await page.getByTestId("tab-processed").click();
  await expect(page.getByTestId("dict-processed")).toContainText("87 / 87 sütun");
  await page.locator('[data-column="midnight_suspect_flag"]').click();
  const sheet = page.getByTestId("feature-sheet");
  await expect(sheet).toContainText("Ne anlama geliyor?");
  await expect(sheet).toContainText("Kesin 00:00 saat");
  await expect(sheet).toContainText("Neden seçildi veya elendi?");
  await page.screenshot({ path: `${SHOTS}/11-veri-gezgini-oznitelik.png` });
  await page.keyboard.press("Escape");
  await page.getByTestId("tab-raw").click();
  await expect(page.getByTestId("dict-raw")).toContainText("29 / 29 sütun");
  await page.getByTestId("tab-sets").click();
  await expect(page.getByTestId("feature-sets")).toContainText("A_dbscan_haversine_weighted");
  expect(await axe(page, "data")).toEqual([]);
});

test("8 — Klavye, azaltılmış hareket ve harita kalıcılığı (yeniden oluşturulmaz, GLB yeniden yüklenmez)", async ({ page, browser }) => {
  await openExplorer(page);
  await page.evaluate(() => { ((window as any).__saferoute.map as any).__marker = "ilk"; });
  const glb: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith(".glb")) glb.push(r.url()); });
  await page.click('[data-borough="BROOKLYN"]');
  await mapIdle(page);
  for (const r of ["genel-bakis", "modeller", "kesif"]) {
    await page.locator(`[data-route="${r === "kesif" ? "explorer" : r === "modeller" ? "models" : "overview"}"]`).first().click();
    await page.waitForTimeout(800);
  }
  expect(await page.evaluate(() => ((window as any).__saferoute.map as any).__marker)).toBe("ilk");
  expect(glb).toEqual([]);
  // Klavye: ilk odak atlama bağlantısı; gezinme bağlantıları Tab ile erişilebilir
  // Ekran değişiminde odak ana içeriğe taşınır
  await page.locator('[data-route="models"]').click();
  expect(await page.evaluate(() => document.activeElement?.id)).toBe("main");
  await page.goto("about:blank");
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.textContent)).toBe("İçeriğe geç");
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => (document.activeElement as HTMLElement)?.dataset.route)).toBe("overview");
  await page.keyboard.press("Tab");
  // Klavye odağı görünür (odak halkası): gölge veya dış çizgi
  const ring = await page.evaluate(() => { const st = getComputedStyle(document.activeElement!); return { shadow: st.boxShadow, outline: st.outlineStyle }; });
  expect(ring.shadow !== "none" || ring.outline !== "none").toBe(true);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/kesif/);
  expect(await page.evaluate(() => document.activeElement?.id)).toBe("main");
  // Azaltılmış hareket tercihi
  const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
  const p2 = await ctx.newPage();
  await p2.goto("/#/kesif");
  await expect(p2.getByTestId("motion-select")).toHaveValue("reduced");
  await ctx.close();
});

for (const vp of [{ name: "mobil", width: 390, height: 844 }, { name: "tablet", width: 820, height: 1180 }]) {
  test(`9 — Responsive (${vp.name} ${vp.width}×${vp.height}): yatay taşma yok, çekmece düzeni`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, hasTouch: true, isMobile: vp.width < 768 });
    const page = await ctx.newPage();
    for (const r of ["genel-bakis", "laboratuvar", "modeller", "veri"]) {
      await page.goto(`/#/${r}`);
      await page.waitForTimeout(2500);
      const overflow = await page.evaluate(() => {
        const el = document.querySelector("main > div:last-child") as HTMLElement;
        return { doc: document.documentElement.scrollWidth - window.innerWidth, inner: el ? el.scrollWidth - el.clientWidth : 0 };
      });
      expect(overflow.doc, `${r} belge taşması`).toBeLessThanOrEqual(0);
      expect(overflow.inner, `${r} kap taşması`).toBeLessThanOrEqual(0);
      if (vp.name === "mobil" && (r === "genel-bakis" || r === "laboratuvar")) await fullShot(page, `12-${vp.name}-${r}.png`);
    }
    await page.goto("/#/kesif");
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
    if (vp.width < 768) {
      await expect(page.getByTestId("left-panel")).toHaveCount(0); // masaüstü paneli küçültülmez; çekmeceye dönüşür
      await page.getByTestId("mobile-panel").click();
      await expect(page.getByRole("dialog")).toContainText("Görünüm ve filtreler");
      await page.waitForTimeout(700); // çekmece açılış geçişi
      await page.screenshot({ path: `${SHOTS}/13-mobil-kesif-cekmece.png` });
      await page.keyboard.press("Escape");
      await page.getByTestId("mobile-menu").click();
      await expect(page.getByRole("dialog")).toContainText("Veri Gezgini");
      await page.keyboard.press("Escape");
    }
    await mapIdle(page, 1000);
    await page.screenshot({ path: `${SHOTS}/13-${vp.name}-3d-sehir.png` });
    await ctx.close();
  });
}

test("10 — Geniş ekran 1920×1080 düzeni: paneller üst üste binmez", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();
  await openExplorer(page);
  const boxes = await page.evaluate(() => Object.fromEntries(["left-panel", "right-panel", "time-controls", "camera-controls"].map((id) => {
    const r = document.querySelector(`[data-testid="${id}"]`)!.getBoundingClientRect(); return [id, [r.left, r.top, r.right, r.bottom]];
  })));
  const overlap = (a: number[], b: number[]) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
  const ids = Object.keys(boxes);
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) expect(overlap(boxes[ids[i]], boxes[ids[j]]), `${ids[i]} × ${ids[j]}`).toBe(false);
  await page.screenshot({ path: `${SHOTS}/14-genis-ekran-1920.png` });
  await ctx.close();
});

test.afterAll(() => {
  writeFileSync(resolve(OUT, "e2e_measurements.json"), JSON.stringify({ generated_at: new Date().toISOString(),
    renderer: "Chromium headless (SwiftShader yazılım WebGL, GPU yok)", viewport: "1440×900 (aksi belirtilmedikçe)", ...measurements, axe: a11y }, null, 2));
});
