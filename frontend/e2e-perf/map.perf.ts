// Faz 6 harita ve 3D performans ölçümü (gerçek uygulama, gerçek veri). Her proje (WebGL arka ucu) için:
// ilk yükleme, katman/API süreleri, GLB yükleme, kamera hareketinde kare süreleri (FPS, p95, takılma),
// yakınlaştırma/uzaklaştırma takılmaları, JS yığın belleği, WebGL bağlam kaybı sonrası toparlanma.
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
// SAFEROUTE_PERF_OUT ile yönlendirilebilir (Faz 8 ölçümü Faz 6 dosyalarını değiştirmesin; verilmezse Faz 6 yolu).
const OUT = process.env.SAFEROUTE_PERF_OUT ? resolve(process.env.SAFEROUTE_PERF_OUT) : resolve(HERE, "../../reports/phase6");
const FILE = resolve(OUT, "map_performance.json");
mkdirSync(resolve(OUT, "screenshots"), { recursive: true });

async function idle(page: Page, extra = 500) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && m.areTilesLoaded() && !m.isMoving(); }, null, { timeout: 120_000 });
  await page.waitForTimeout(extra);
}

/** Bir kamera hareketi boyunca requestAnimationFrame aralıklarını ölçer. */
async function frames(page: Page, move: string, ms: number) {
  return page.evaluate(async ([code, dur]) => {
    const m = (window as any).__saferoute.map;
    const ts: number[] = [];
    let run = true;
    const tick = (t: number) => { ts.push(t); if (run) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    // eslint-disable-next-line no-new-func
    new Function("m", "d", code)(m, dur);
    await new Promise((r) => setTimeout(r, (dur as number) + 300));
    run = false;
    const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
    const sum = d.reduce((a, b) => a + b, 0);
    const q = (p: number) => d[Math.min(d.length - 1, Math.floor(p * d.length))];
    return { frames: d.length, fps: Math.round((d.length / sum) * 1000 * 10) / 10, median_ms: Math.round(q(0.5) * 10) / 10,
      p95_ms: Math.round(q(0.95) * 10) / 10, max_ms: Math.round(d[d.length - 1] * 10) / 10,
      long_frames_50ms: d.filter((x) => x > 50).length, long_frames_100ms: d.filter((x) => x > 100).length };
  }, [move, ms] as const);
}

test("Harita + 3D performansı", async ({ page }, info) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  const t0 = Date.now();
  await page.goto("/#/kesif");
  const renderer = await page.evaluate(() => {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl2") || c.getContext("webgl")) as WebGLRenderingContext | null;
    if (!gl) return { webgl: false };
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    return { webgl: true, vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER) };
  });
  const software = /swiftshader|llvmpipe|software|basic render/i.test(String(renderer.renderer));
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 120_000 });
  const readyMs = Date.now() - t0;
  await idle(page);
  const firstIdleMs = Date.now() - t0;
  const api = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.includes("/api/"))
    .map((e: any) => ({ path: new URL(e.name).pathname + (new URL(e.name).search.length > 60 ? "?…" : new URL(e.name).search),
      ms: Math.round(e.duration), bytes: e.encodedBodySize })));
  const nav = await page.evaluate(() => { const n = performance.getEntriesByType("navigation")[0] as any;
    return { dom_content_loaded_ms: Math.round(n.domContentLoadedEventEnd), load_ms: Math.round(n.loadEventEnd) }; });

  // Manhattan, 3D binalar + eğim: döndürme (kamera hareketi FPS)
  await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.9855, 40.758], zoom: 15.5, pitch: 60, bearing: -20 }));
  await idle(page, 800);
  const rotate = await frames(page, "m.easeTo({ bearing: m.getBearing() + 120, duration: d, easing: (t) => t })", 5000);
  // Yakınlaştırma / uzaklaştırma (zoom'a göre katman geçişleri: yoğunluk 1 km → 250 m → noktalar)
  await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.95, 40.70], zoom: 10.5, pitch: 45, bearing: 0 }));
  await idle(page, 500);
  const zoomIn = await frames(page, "m.easeTo({ zoom: 16, duration: d })", 4000);
  const zoomOut = await frames(page, "m.easeTo({ zoom: 10.5, duration: d })", 4000);
  await idle(page, 500);

  // Küme seçimi → temsili sahne (GLB) yükleme
  const c = await page.evaluate(async () => (await fetch("/api/clusters/1344")).json());
  await page.evaluate(([lon, lat]) => (window as any).__saferoute.map.jumpTo({ center: [lon, lat], zoom: 14.2 }), [c.centroid_lon, c.centroid_lat]);
  await idle(page, 400);
  const pt = await page.evaluate(([lon, lat]) => { const m = (window as any).__saferoute.map; const r = m.project([lon, lat]);
    const b = m.getCanvas().getBoundingClientRect(); return [r.x + b.left, r.y + b.top]; }, [c.centroid_lon, c.centroid_lat]);
  const tg = Date.now();
  await page.mouse.click(pt[0], pt[1]);
  await page.waitForFunction(() => ((window as any).__saferoute.layer()?.status.loaded.length ?? 0) > 0, null, { timeout: 120_000 });
  const sceneMs = Date.now() - tg;
  await idle(page, 2500);
  const glb = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.endsWith(".glb"))
    .map((e: any) => ({ file: e.name.split("/").pop(), ms: Math.round(e.duration), bytes: e.encodedBodySize })));
  const scene = await frames(page, "m.easeTo({ bearing: m.getBearing() + 60, duration: d, easing: (t) => t })", 4000);

  // WebGL bağlam kaybı → toparlanma
  const tl = Date.now();
  await page.evaluate(() => { const gl = (window as any).__saferoute.map.painter.context.gl;
    (window as any).__lose = gl.getExtension("WEBGL_lose_context"); (window as any).__lose.loseContext(); });
  await expect(page.getByTestId("load-status")).toContainText("kaybedildi", { timeout: 20_000 });
  await page.evaluate(() => (window as any).__lose.restoreContext());
  await page.waitForFunction(() => (window as any).__saferoute.layer()?.status.ready === true && !!(window as any).__saferoute.map.getLayer("city-models"), null, { timeout: 60_000 });
  await idle(page, 500);
  const recoveryMs = Date.now() - tl;

  const heap = await page.evaluate(() => { const m = (performance as any).memory; return m ? { used_mb: Math.round(m.usedJSHeapSize / 2 ** 20), total_mb: Math.round(m.totalJSHeapSize / 2 ** 20) } : null; });
  const metrics = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m: any) => [m.name, m.value]));
  await page.screenshot({ path: resolve(OUT, `screenshots/perf-${info.project.name}.png`) });

  const result = {
    project: info.project.name, measured_at: new Date().toISOString(), renderer, software_webgl: software,
    note: software ? "YAZILIM WebGL (CPU) — GPU performansı DEĞİLDİR" : "Donanım WebGL (GPU)",
    initial: { navigation: nav, load_status_ready_ms: readyMs, first_map_idle_ms: firstIdleMs },
    api_requests: api, camera_rotate_manhattan_3d: rotate, zoom_in: zoomIn, zoom_out: zoomOut,
    cluster_scene: { cluster_id: 1344, glb_ready_ms: sceneMs, glb_requests: glb, rotate_with_models: scene },
    webgl_context_recovery_ms: recoveryMs, js_heap: heap,
    cdp: { JSHeapUsedSize_mb: Math.round((metrics.JSHeapUsedSize ?? 0) / 2 ** 20), Nodes: metrics.Nodes, LayoutCount: metrics.LayoutCount },
  };
  const all = existsSync(FILE) ? JSON.parse(readFileSync(FILE, "utf8")) : {};
  all[info.project.name] = result;
  writeFileSync(FILE, JSON.stringify(all, null, 2));
  console.log(JSON.stringify({ project: info.project.name, renderer: renderer.renderer, fps_rotate: rotate.fps, fps_zoom_in: zoomIn.fps, recoveryMs }));
});
