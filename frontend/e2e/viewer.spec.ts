// Faz 4 uçtan uca testleri — GERÇEK çalışan uygulama (FastAPI + derlenmiş ön yüz + OpenFreeMap karoları).
// Ekran görüntüleri reports/phase4/screenshots/ altına yazılır.
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "../../reports/phase4/screenshots");
const PERF = resolve(HERE, "../../reports/phase4/e2e_measurements.json");
mkdirSync(SHOTS, { recursive: true });
const measurements: Record<string, unknown> = {};

type LngLat = [number, number];
const TOP_CLUSTER = 1344; // Faz 3: olay sayısına göre 1. küme (Tillary St / Flatbush Ave Ext, Brooklyn)

async function idle(page: Page, extraMs = 600) {
  await page.waitForFunction(() => {
    const m = (window as any).__saferoute?.map;
    return m && m.loaded() && m.areTilesLoaded() && !m.isMoving();
  }, null, { timeout: 90_000 });
  await page.waitForTimeout(extraMs);
}

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await idle(page, 1500);
}

const project = (page: Page, p: LngLat) =>
  page.evaluate((q) => { const r = (window as any).__saferoute.map.project(q); return [r.x, r.y] as [number, number]; }, p);

/** Three.js zincirinin hesapladığı ekran konumu ile MapLibre'nin aynı coğrafi nokta için verdiği konum farkı (px). */
async function modelDrift(page: Page) {
  return page.evaluate(() => {
    const s = (window as any).__saferoute;
    s.map.triggerRepaint();
    return (s.layer()?.debugObjects() ?? []).filter((o: any) => o.screen && o.visible).map((o: any) => {
      const p = s.map.project(o.lngLat);
      return { name: o.name, drift: Math.hypot(p.x - o.screen[0], p.y - o.screen[1]) };
    });
  });
}

async function clusterAtScreen(page: Page, id: number) {
  const c = await page.evaluate(async (cid) => (await (await fetch(`/api/clusters/${cid}`)).json()), id);
  return { detail: c, screen: await project(page, [c.centroid_lon, c.centroid_lat]) };
}

test.describe.configure({ mode: "serial" });

test("A — açılışta tüm New York görünür, gerçek veri ve gerçek harita karoları yüklenir", async ({ page }) => {
  const apiBytes: Record<string, number> = {};
  page.on("response", async (r) => {
    if (r.url().includes("/api/")) apiBytes[new URL(r.url()).pathname] = (apiBytes[new URL(r.url()).pathname] ?? 0) + Number(r.headers()["content-length"] ?? (await r.body()).length);
  });
  const t0 = Date.now();
  await open(page);
  measurements.initial_load_ms = Date.now() - t0;
  const meta = await page.evaluate(async () => (await fetch("/api/meta")).json());
  // UI değerleri sabit kodlu değil: API meta verisiyle aynı
  await expect(page.getByTestId("model-params")).toHaveText(`eps = ${meta.model.parameters.eps_m} m · min_samples = ${meta.model.parameters.min_samples}`);
  await expect(page.getByTestId("experiment-id")).toHaveText(meta.model.experiment_id);
  await expect(page.getByTestId("meta-clusters")).toHaveText(meta.counts.clusters.toLocaleString("tr-TR"));
  await expect(page.getByTestId("meta-clustered")).toHaveText(meta.counts.events_clustered.toLocaleString("tr-TR"));
  expect(meta.counts.events_clustered + meta.counts.events_noise).toBe(meta.counts.events_total);
  // Beş ilçenin her birinin merkezi görüntü alanında
  const inView = await page.evaluate((bounds) => {
    const m = (window as any).__saferoute.map;
    const c = m.getCanvas();
    return Object.entries(bounds as Record<string, number[]>).map(([b, [w, s, e, n]]) => {
      const p = m.project([(w + e) / 2, (s + n) / 2]);
      return [b, p.x > 0 && p.y > 0 && p.x < c.clientWidth && p.y < c.clientHeight];
    });
  }, meta.boroughs.bounds);
  for (const [b, ok] of inView) expect(ok, `${b} görünmüyor`).toBe(true);
  // Gerçek vektör karoları (OSM) ve gerçek kümeler çizildi
  const rendered = await page.evaluate(() => {
    const m = (window as any).__saferoute.map;
    return { water: m.queryRenderedFeatures({ layers: ["water"] }).length, roads: m.queryRenderedFeatures({ layers: ["road-motorway", "road-major"] }).length,
      centroids: m.queryRenderedFeatures({ layers: ["centroid-circle"] }).length, boroughs: m.querySourceFeatures("boroughs").length };
  });
  expect(rendered.water).toBeGreaterThan(0);
  expect(rendered.roads).toBeGreaterThan(0);
  expect(rendered.centroids).toBeGreaterThan(1000);
  expect(rendered.boroughs).toBeGreaterThanOrEqual(5);
  measurements.initial_api_bytes = apiBytes;
  // 2 milyon olay tarayıcıya gönderilmez: açılıştaki toplam API yükü küçük, nokta isteği yok
  expect(Object.keys(apiBytes).some((k) => k.startsWith("/api/points"))).toBe(false);
  expect(Object.values(apiBytes).reduce((a, b) => a + b, 0)).toBeLessThan(6_000_000);
  await page.screenshot({ path: `${SHOTS}/01-nyc-genel-gorunum.png` });
});

test("B — Brooklyn seçilince kamera Brooklyn'e gider (beş ilçe)", async ({ page }) => {
  await open(page);
  const meta = await page.evaluate(async () => (await fetch("/api/meta")).json());
  for (const b of ["MANHATTAN", "QUEENS", "BRONX", "STATEN ISLAND", "BROOKLYN"]) {
    await page.click(`[data-borough="${b}"]`);
    await idle(page, 300);
    const center = await page.evaluate(() => (window as any).__saferoute.map.getCenter().toArray());
    const [w, s, e, n] = meta.boroughs.bounds[b];
    expect(center[0], `${b} boylam`).toBeGreaterThan(w);
    expect(center[0]).toBeLessThan(e);
    expect(center[1], `${b} enlem`).toBeGreaterThan(s);
    expect(center[1]).toBeLessThan(n);
    await expect(page.locator(`[data-borough="${b}"]`)).toHaveAttribute("aria-pressed", "true");
  }
  await page.screenshot({ path: `${SHOTS}/02-brooklyn-ilce-gorunumu.png` });
});

test("C — kümeye tıklanınca DOĞRU kümenin ayrıntıları açılır, kamera kümeye gider", async ({ page }) => {
  await open(page);
  await page.click('[data-borough="BROOKLYN"]');
  await idle(page, 500);
  const { detail, screen } = await clusterAtScreen(page, TOP_CLUSTER);
  await page.mouse.click(screen[0], screen[1]); // gerçek fare tıklaması, ilçe ölçeğinde (komşu daireler üst üste)
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready");
  await expect(page.getByTestId("cluster-title")).toContainText(`Küme #${TOP_CLUSTER}`);
  await expect(page.getByTestId("cluster-events")).toHaveText(detail.n_events.toLocaleString("tr-TR"));
  await expect(page.getByTestId("cluster-borough")).toHaveText("Brooklyn");
  await expect(page.getByTestId("cluster-experiment")).toHaveText(detail.experiment_id);
  await expect(page.getByTestId("cluster-center")).toContainText(detail.centroid_lat.toFixed(5));
  await idle(page, 1500);
  const state = await page.evaluate((id) => {
    const m = (window as any).__saferoute.map;
    return { sel: m.getFeatureState({ source: "centroids", id }).selected, geom: m.getFeatureState({ source: "geometries", id }).selected,
      center: m.getCenter().toArray(), zoom: m.getZoom(), selected: (window as any).__saferoute.selected()?.cluster_id };
  }, TOP_CLUSTER);
  expect(state.sel).toBe(true);
  expect(state.geom).toBe(true);
  expect(state.selected).toBe(TOP_CLUSTER);
  expect(state.zoom).toBeGreaterThan(17);
  const dLng = (state.center[0] - detail.centroid_lon) * 84_400, dLat = (state.center[1] - detail.centroid_lat) * 111_100;
  expect(Math.hypot(dLng, dLat), "kamera merkezi küme merkezine uzaklık (m)").toBeLessThan(5);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/03-brooklyn-kume-secimi.png` });
  await page.getByTestId("cluster-panel").screenshot({ path: `${SHOTS}/07-kume-detay-paneli.png` });
  // Kayma yok: temsili araçlar/donatılar haritaya kilitli
  const drift = await modelDrift(page);
  expect(drift.length).toBeGreaterThan(0);
  for (const d of drift) expect(d.drift, d.name).toBeLessThan(1.5);
  measurements.cluster_scene_objects = drift.map((d) => d.name);
});

test("D — gürültü noktaları açılıp kapatılır; görünen alan sayıları API ile tutarlı", async ({ page }) => {
  await open(page);
  const { detail } = await clusterAtScreen(page, TOP_CLUSTER);
  await page.evaluate((c) => (window as any).__saferoute.map.jumpTo({ center: c, zoom: 17, pitch: 40 }), [detail.centroid_lon, detail.centroid_lat]);
  await idle(page);
  await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "ready");
  const noiseRendered = () => page.evaluate(() => (window as any).__saferoute.map.queryRenderedFeatures({ layers: ["points-noise"] }).length);
  expect(await noiseRendered()).toBe(0); // varsayılan kapalı
  await page.getByRole("switch", { name: "Gürültü noktaları" }).click();
  await expect(page.getByRole("switch", { name: "Gürültü noktaları" })).toHaveAttribute("aria-checked", "true");
  await page.waitForFunction(() => (window as any).__saferoute.map.queryRenderedFeatures({ layers: ["points-noise"] }).length > 0, null, { timeout: 30_000 });
  await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "ready");
  // Ekrandaki toplamlar = sunucunun aynı bbox için gerçek toplamları
  const check = await page.evaluate(async () => {
    const m = (window as any).__saferoute.map;
    const src = m.getSource("points")._data ?? null;
    const b = m.getBounds();
    const step = 0.002;
    const bbox = [Math.floor(b.getWest() / step) * step, Math.floor(b.getSouth() / step) * step, Math.ceil(b.getEast() / step) * step, Math.ceil(b.getNorth() / step) * step].map((v) => v.toFixed(6)).join(",");
    const api = await (await fetch(`/api/points?bbox=${bbox}&kind=all&limit=8000`)).json();
    return { text: document.querySelector('[data-testid="viewport-stats"]')!.textContent, api: { loc: api.total_locations, ev: api.total_events, noise: api.features.filter((f: any) => f.properties.noise).length }, hasSrc: !!src };
  });
  expect(check.text).toContain(check.api.ev.toLocaleString("tr-TR"));
  expect(check.text).toContain(check.api.loc.toLocaleString("tr-TR"));
  expect(check.api.noise).toBeGreaterThan(0);
  await page.screenshot({ path: `${SHOTS}/04-gurultu-noktalari-acik.png` });
  await page.getByRole("switch", { name: "Gürültü noktaları" }).click();
  await idle(page, 400);
  expect(await page.evaluate(() => (window as any).__saferoute.map.getLayoutProperty("points-noise", "visibility"))).toBe("none");
  expect(await noiseRendered()).toBe(0);
  // Kümelenmiş noktalar da kapatılınca nokta sorgusu yapılmaz
  await page.getByRole("switch", { name: "Kümelenmiş noktalar" }).click();
  await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "off");
});

test("E — GLB araç modeli inceleme: konum/irtifa/yön/ölçek; dönüş ve zoomda koordinattan kopmaz", async ({ page }) => {
  await open(page);
  const site: LngLat = [-73.98397, 40.69471]; // Flatbush Ave Extension şeridi (Brooklyn), yol yönü ~3°
  await page.evaluate((c) => (window as any).__saferoute.map.jumpTo({ center: c, zoom: 19.8, pitch: 62, bearing: 335 }), site);
  await idle(page);
  await page.getByTestId("assets-toggle").click();
  await expect(page.getByTestId("asset-inspector")).toBeVisible();
  await page.click('[data-model="taxi"]');
  await page.getByTestId("insp-lng").fill(String(site[0]));
  await page.getByTestId("insp-lat").fill(String(site[1]));
  await page.getByTestId("insp-heading").fill("3");
  await expect(page.getByTestId("asset-license")).toContainText("CC0");
  await expect(page.getByTestId("asset-license")).toContainText("Kenney");
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.debugObjects() ?? []).some((o: any) => o.name === "inspector:taxi"), null, { timeout: 30_000 });
  await idle(page, 800);
  const before = await modelDrift(page);
  expect(before.find((d) => d.name === "inspector:taxi")!.drift).toBeLessThan(1.5);
  await page.screenshot({ path: `${SHOTS}/06-glb-arac-modeli.png` });
  // Dönüş, eğim ve zoom: model aynı coğrafi noktada kalır
  const drifts: number[] = [];
  for (const cam of [{ bearing: 120 }, { bearing: -60, pitch: 70 }, { zoom: 18.2 }, { zoom: 19.6, pitch: 30 }]) {
    await page.evaluate((c) => (window as any).__saferoute.map.jumpTo(c), cam);
    await idle(page, 300);
    const d = (await modelDrift(page)).find((x) => x.name === "inspector:taxi")!;
    drifts.push(d.drift);
    expect(d.drift, JSON.stringify(cam)).toBeLessThan(1.5);
  }
  measurements.model_drift_px = { max: Math.max(...drifts, before[0].drift), samples: drifts };
  // Parametrelerle kontrol: boylam/enlem değişince model yeni noktaya taşınır; irtifa 10 m → ekranda yukarı
  const lng = page.getByTestId("insp-lng");
  await lng.fill(String(site[0] + 0.0002));
  await page.waitForTimeout(500);
  const moved = await page.evaluate(() => (window as any).__saferoute.layer().debugObjects().find((o: any) => o.name === "inspector:taxi").lngLat);
  expect(moved[0]).toBeCloseTo(site[0] + 0.0002, 7);
  const y0 = (await page.evaluate(() => (window as any).__saferoute.layer().debugObjects().find((o: any) => o.name === "inspector:taxi").screen))[1];
  await page.getByTestId("insp-alt").fill("10");
  await page.waitForTimeout(500);
  await idle(page, 200);
  const y1 = (await page.evaluate(() => (window as any).__saferoute.layer().debugObjects().find((o: any) => o.name === "inspector:taxi").screen))[1];
  expect(y1).toBeLessThan(y0 - 5);
  await page.getByTestId("insp-heading").fill("90");
  await page.getByTestId("insp-scale").fill("2");
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => (window as any).__saferoute.layer().status.error)).toBeNull();
});

test("F — kamera döndürülür, yakınlaştırılır, eğilir ve sıfırlanır", async ({ page }) => {
  await open(page);
  const cam = () => page.evaluate(() => { const m = (window as any).__saferoute.map; return { z: m.getZoom(), b: m.getBearing(), p: m.getPitch() }; });
  const c0 = await cam();
  await page.click('[data-action="rotR"]');
  await idle(page, 200);
  expect((await cam()).b).toBeCloseTo(c0.b + 30, 0);
  await page.click('[data-action="zoomIn"]');
  await idle(page, 200);
  expect((await cam()).z).toBeCloseTo(c0.z + 1, 0);
  await page.click('[data-action="pitchUp"]');
  await idle(page, 200);
  expect((await cam()).p).toBeCloseTo(Math.min(78, c0.p + 10), 0);
  // Fareyle sürükleyerek kaydırma
  const before = await page.evaluate(() => (window as any).__saferoute.map.getCenter().toArray());
  await page.mouse.move(800, 500);
  await page.mouse.down();
  await page.mouse.move(650, 420, { steps: 8 });
  await page.mouse.up();
  await idle(page, 200);
  const after = await page.evaluate(() => (window as any).__saferoute.map.getCenter().toArray());
  expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeGreaterThan(0.001);
  await page.click('[data-action="reset"]');
  await idle(page, 300);
  const r = await cam();
  expect(r.b).toBeCloseTo(-17, 0);
  expect(r.p).toBeCloseTo(45, 0);
  expect(Math.abs(r.z - c0.z)).toBeLessThan(0.05);
});

test("G — büyük veri yükünde donma yok; nokta katmanı yalnızca yakın zoomda ve sınırlı yüklenir", async ({ page }) => {
  await open(page);
  const pointRequests: { url: string; returned: number; truncated: boolean }[] = [];
  page.on("response", async (r) => {
    if (r.url().includes("/api/points")) {
      const j = await r.json().catch(() => null);
      if (j) pointRequests.push({ url: r.url(), returned: j.returned_locations, truncated: j.truncated });
    }
  });
  await page.evaluate(() => {
    (window as any).__longTasks = [];
    new PerformanceObserver((l) => l.getEntries().forEach((e) => (window as any).__longTasks.push(e.duration))).observe({ type: "longtask", buffered: true });
  });
  // Şehir ölçeğinde nokta isteği yok
  expect(pointRequests.length).toBe(0);
  // Manhattan boyunca yakın zoomda kaydırma (gerçek kullanıcı hareketi gibi ardışık kamera geçişleri)
  const route: LngLat[] = [[-74.006, 40.712], [-73.99, 40.735], [-73.985, 40.758], [-73.968, 40.785], [-73.944, 40.81]];
  const t0 = Date.now();
  for (const c of route) {
    await page.evaluate((q) => (window as any).__saferoute.map.easeTo({ center: q, zoom: 16, pitch: 55, duration: 900 }), c);
    // Ana iş parçacığı yanıt veriyor mu? (her adımda küçük bir değerlendirme gecikmesi ölçülür)
    const s = Date.now();
    await page.evaluate(() => 1);
    (measurements.eval_latency_ms ??= [] as number[]) && (measurements.eval_latency_ms as number[]).push(Date.now() - s);
    await page.waitForTimeout(1000);
  }
  await idle(page, 800);
  measurements.pan_route_ms = Date.now() - t0;
  const lt: number[] = await page.evaluate(() => (window as any).__longTasks);
  const mem = await page.evaluate(() => (performance as any).memory?.usedJSHeapSize ?? null);
  measurements.long_tasks = { count: lt.length, max_ms: lt.length ? Math.max(...lt) : 0 };
  measurements.js_heap_mb = mem && Math.round(mem / 1048576);
  measurements.point_requests = pointRequests.length;
  measurements.max_point_features = Math.max(0, ...pointRequests.map((p) => p.returned));
  expect(pointRequests.length).toBeGreaterThan(0);
  for (const p of pointRequests) expect(p.returned).toBeLessThanOrEqual(8000);
  expect(Math.max(...(measurements.eval_latency_ms as number[]))).toBeLessThan(3000);
  if (mem) expect(mem / 1048576).toBeLessThan(600);
  await page.screenshot({ path: `${SHOTS}/02-manhattan-yakin-gorunum.png` });
});

test("Kavşak yakın görünümü, gece ve gündüz modları", async ({ page }) => {
  await open(page);
  await page.click('[data-borough="BROOKLYN"]');
  await idle(page, 300);
  const { detail, screen } = await clusterAtScreen(page, TOP_CLUSTER);
  await page.mouse.click(screen[0], screen[1]);
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready");
  await idle(page, 1000);
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.debugObjects() ?? []).some((o: any) => o.name.startsWith("vehicle:")), null, { timeout: 30_000 });
  // Flatbush Ave Extension koridoru boyunca güneyden kavşağa bakış (binalar görüşü kapatmaz)
  void detail;
  await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.98405, 40.69455], zoom: 18.9, pitch: 62, bearing: 350 }));
  await idle(page, 1500);
  await page.screenshot({ path: `${SHOTS}/04-kavsak-yakin-gorunum.png` });
  await page.screenshot({ path: `${SHOTS}/05-gece-modu.png` });
  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(800);
  expect(await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color"))).toBe("#E8EDF3");
  await page.screenshot({ path: `${SHOTS}/05b-gunduz-modu.png` });
  await page.getByTestId("theme-toggle").click();
  expect(await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color"))).toBe("#0B1120");
});

test("Animasyon düzeyi: kapalıyken araçlar durur, halka nabzı durur", async ({ page }) => {
  await open(page);
  await page.click('[data-borough="BROOKLYN"]');
  await idle(page, 300);
  const { screen } = await clusterAtScreen(page, TOP_CLUSTER);
  await page.mouse.click(screen[0], screen[1]);
  await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready");
  await idle(page, 2000);
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.debugObjects() ?? []).some((o: any) => o.name.startsWith("vehicle:")), null, { timeout: 30_000 });
  const pos = () => page.evaluate(() => (window as any).__saferoute.layer().debugObjects().filter((o: any) => o.name.startsWith("vehicle:")).map((o: any) => o.lngLat));
  const a = await pos();
  await page.waitForTimeout(1200);
  const b = await pos();
  expect(JSON.stringify(a)).not.toBe(JSON.stringify(b)); // tam: hareket var
  await page.selectOption('[data-testid="motion-select"]', "off");
  await page.waitForTimeout(300);
  const c = await pos();
  await page.waitForTimeout(1200);
  const d = await pos();
  expect(JSON.stringify(c)).toBe(JSON.stringify(d)); // kapalı: hareket yok
  await expect(page.getByTestId("sim-note")).toContainText("temsili");
});

test("WebGL bağlam kaybı sonrası 3D katman yeniden kurulur", async ({ page }) => {
  await open(page);
  await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.98513, 40.7589], zoom: 19, pitch: 55 }));
  await idle(page);
  await page.getByTestId("assets-toggle").click();
  await page.click('[data-model="sedan"]');
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.debugObjects() ?? []).some((o: any) => o.name === "inspector:sedan"), null, { timeout: 30_000 });
  const first = await page.evaluate(() => (window as any).__saferoute.layer());
  void first;
  await page.evaluate(() => {
    const gl = (window as any).__saferoute.map.getCanvas().getContext("webgl2");
    const ext = gl.getExtension("WEBGL_lose_context");
    (window as any).__lose = ext;
    ext.loseContext();
  });
  await expect(page.getByTestId("load-status")).toContainText("kaybedildi", { timeout: 15_000 });
  await page.evaluate(() => (window as any).__lose.restoreContext());
  await expect(page.getByTestId("load-status")).toContainText("geri yüklendi", { timeout: 30_000 });
  await idle(page, 1500);
  const after = await page.evaluate(() => {
    const l = (window as any).__saferoute.layer();
    return { ready: l.status.ready, lost: l.status.contextLost, objs: l.debugObjects().map((o: any) => o.name) };
  });
  expect(after.ready).toBe(true);
  expect(after.lost).toBe(false);
  expect(after.objs).toContain("inspector:sedan");
  const drift = (await modelDrift(page)).find((d) => d.name === "inspector:sedan")!;
  expect(drift.drift).toBeLessThan(1.5);
});

test("Hata durumu: API'ye ulaşılamazsa kullanıcıya anlaşılır hata gösterilir", async ({ page }) => {
  await page.route("**/api/meta", (r) => r.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Bakımda" }) }));
  await page.goto("/");
  await expect(page.getByTestId("fatal-error")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("fatal-error")).toContainText("Bakımda");
});

test.afterAll(() => {
  // Kısmi çalıştırmalar (-g) önceki ölçümleri silmez: alan bazında birleştirilir.
  let prev: Record<string, unknown> = {};
  try {
    prev = JSON.parse(readFileSync(PERF, "utf8"));
  } catch {
    /* ilk çalıştırma */
  }
  writeFileSync(PERF, JSON.stringify({ ...prev, generated_at: new Date().toISOString(),
    renderer: "Chromium headless (SwiftShader yazılım WebGL, GPU yok)", viewport: "1600×960", ...measurements }, null, 2));
});
