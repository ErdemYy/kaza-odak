// Faz 8 — tam işlevsel denetim. GERÇEK uygulama: FastAPI (gerçek NYC verisi, doğrulanmış Faz 3 çıktıları) + derlenmiş
// ön yüz + OpenFreeMap karoları. Her kullanıcı etkileşimi kimlikli olarak kaydedilir (ekran, bileşen, beklenen, gerçek,
// sonuç, neden). Bir etkileşim başarısız olursa test sonunda başarısız sayılır; kayıt gizlenmez.
// Konsol hataları/uyarıları ve başarısız ağ istekleri uygulama ile üçüncü taraf (harita karosu) olarak ayrılır.
// Çıktılar: reports/phase8/ (SAFEROUTE_PHASE8_OUT ile yönlendirilebilir).
// Dinamik laboratuvar işleri ana iş kaydına dokunmamak için yalıtılmış sunucuda (port 8012) çalışır.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../..");
const OUT = process.env.SAFEROUTE_PHASE8_OUT ? resolve(process.env.SAFEROUTE_PHASE8_OUT) : resolve(ROOT, "reports/phase8");
const SHOTS = resolve(OUT, "screenshots");
const RUNS = resolve(OUT, "runs"); // test başına kayıt: başarısız test işçiyi yeniden başlatsa da sonuçlar kaybolmaz
mkdirSync(SHOTS, { recursive: true });
mkdirSync(RUNS, { recursive: true });
const tr = (n: number) => n.toLocaleString("tr-TR");
const TILLARY = 1344;

// ------------------------------------------------------------------ kayıt altyapısı
type Result = "geçti" | "başarısız";
interface Rec { id: string; screen: string; component: string; expected: string; actual: string; result: Result; cause?: string; ms: number; test: string }
const records: Rec[] = [];
const logs: Record<string, { app_console: string[]; third_party_console: string[]; app_failed: string[]; third_party_failed: string[]; http_errors: string[] }> = {};
const a11y: Record<string, unknown> = {};
const measurements: Record<string, unknown> = {};
let currentTest = "";
let failures: string[] = [];

const THIRD = /openfreemap\.org|openmaptiles|openstreetmap/;
function track(page: Page, name: string) {
  const l = logs[name] ??= { app_console: [], third_party_console: [], app_failed: [], third_party_failed: [], http_errors: [] };
  page.on("console", (m) => {
    if (m.type() !== "error" && m.type() !== "warning") return;
    const text = `${m.type()}: ${m.text().slice(0, 300)}`;
    (THIRD.test(m.text()) || THIRD.test(m.location().url ?? "") ? l.third_party_console : l.app_console).push(text);
  });
  page.on("pageerror", (e) => l.app_console.push(`pageerror: ${e.message.slice(0, 300)}`));
  page.on("requestfailed", (r) => {
    const err = r.failure()?.errorText ?? "";
    if (err.includes("ERR_ABORTED")) return; // iptal edilen (AbortController) istekler beklenen davranıştır
    (THIRD.test(r.url()) ? l.third_party_failed : l.app_failed).push(`${r.url().slice(0, 160)} ${err}`);
  });
  page.on("response", (r) => { if (r.status() >= 400 && !THIRD.test(r.url())) l.http_errors.push(`${r.status()} ${r.url().slice(0, 160)}`); });
}

async function step(id: string, screen: string, component: string, expected: string, fn: () => Promise<string>) {
  const t0 = Date.now();
  try {
    const actual = await fn();
    records.push({ id, screen, component, expected, actual, result: "geçti", ms: Date.now() - t0, test: currentTest });
  } catch (e) {
    const msg = (e as Error).message.replace(/\u001b\[[0-9;]*m/g, "").split("\n").filter(Boolean).slice(0, 4).join(" | ").slice(0, 500);
    records.push({ id, screen, component, expected, actual: "Beklenen gerçekleşmedi", result: "başarısız", cause: msg, ms: Date.now() - t0, test: currentTest });
    failures.push(id);
  }
}

test.beforeEach(({ page }, info) => { currentTest = info.title; failures = []; track(page, info.title); });
test.afterEach(({}, info) => {
  const slug = info.titlePath.slice(1).join(" › ").replace(/[^\p{L}\p{N}]+/gu, "-").slice(0, 120);
  writeFileSync(resolve(RUNS, `${slug}.json`), JSON.stringify({ test: info.title, status: failures.length ? "failed" : info.status, duration_ms: info.duration,
    records: records.filter((r) => r.test === info.title), logs: logs[info.title] ?? null, a11y, measurements }, null, 2));
  expect(failures, `Başarısız etkileşimler: ${failures.join(", ")}`).toEqual([]);
});
test.afterAll(() => {
  const runs = readdirSync(RUNS).filter((f) => f.endsWith(".json")).map((f) => JSON.parse(readFileSync(resolve(RUNS, f), "utf-8")));
  const all = runs.flatMap((r) => r.records as Rec[]);
  const passed = all.filter((r) => r.result === "geçti").length;
  writeFileSync(resolve(OUT, "interaction_results.json"), JSON.stringify({
    generated_at: new Date().toISOString(), total: all.length, passed, failed: all.length - passed,
    tests: runs.map((r) => ({ test: r.test, status: r.status, duration_ms: r.duration_ms })),
    records: all, logs: Object.fromEntries(runs.map((r) => [r.test, r.logs])),
    a11y: Object.assign({}, ...runs.map((r) => r.a11y)), measurements: Object.assign({}, ...runs.map((r) => r.measurements)),
  }, null, 2));
});

test.use({ viewport: { width: 1440, height: 900 }, actionTimeout: 20_000 });

// ------------------------------------------------------------------ yardımcılar
const api = <T = any>(page: Page, path: string): Promise<T> => page.evaluate(async (p) => (await fetch(p)).json(), path);
const mapState = (page: Page) => page.evaluate(() => {
  const m = (window as any).__saferoute.map;
  return { zoom: m.getZoom(), bearing: m.getBearing(), pitch: m.getPitch(), center: [m.getCenter().lng, m.getCenter().lat] as [number, number] };
});
async function mapIdle(page: Page, extra = 500) {
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && !m.isMoving(); }, null, { timeout: 90_000 });
  await page.waitForTimeout(extra);
}
async function openExplorer(page: Page) {
  await page.goto("/#/kesif");
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await mapIdle(page, 800);
}
const pagePoint = (page: Page, p: [number, number]) => page.evaluate((q) => {
  const m = (window as any).__saferoute.map; const r = m.project(q); const c = m.getCanvas().getBoundingClientRect();
  return [r.x + c.left, r.y + c.top] as [number, number];
}, p);
const centroidIds = (page: Page) => page.evaluate(async () => {
  const fc = await (window as any).__saferoute.map.getSource("centroids").getData();
  return (fc?.features ?? []).map((f: any) => Number(f.properties.cluster_id)) as number[];
});
async function shot(page: Page, file: string) { await page.screenshot({ path: `${SHOTS}/${file}` }); }
async function noOverflow(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}
async function flyTo(page: Page, center: [number, number], zoom: number, pitch = 50) {
  await page.evaluate(([c, z, p]) => (window as any).__saferoute.map.jumpTo({ center: c, zoom: z, pitch: p }), [center, zoom, pitch] as const);
  await mapIdle(page, 600);
}

// ================================================================== 1) Marka ve gezinme
test("Marka, favikon ve gezinme", async ({ page, browser }) => {
  test.setTimeout(180_000);
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });

  await step("G01", "Genel", "Navigation › Brand", "Yeni SVG logo (simge + Kaza Odak wordmark) kenar çubuğunda görünür", async () => {
    const nav = page.getByTestId("navigation");
    await expect(nav.getByTestId("brand-mark")).toBeVisible();
    await expect(nav.getByTestId("brand-wordmark")).toHaveText("Kaza Odak");
    const paths = await nav.getByTestId("brand-mark").locator("path, circle").count();
    return `simge ${paths} vektör öğe; wordmark "Kaza Odak"`;
  });
  await shot(page, "03-kenar-cubugu-logo.png");
  await page.screenshot({ path: `${SHOTS}/03b-logo-kenar-cubugu-yakin.png`, clip: { x: 0, y: 0, width: 250, height: 56 } });

  await step("G02", "Genel", "index.html › favikon", "SVG favikon ve PNG yedekleri 200 döner, <link rel=icon> bunları gösterir", async () => {
    const hrefs = await page.locator("link[rel~=icon], link[rel=apple-touch-icon]").evaluateAll((ls) => ls.map((l) => l.getAttribute("href")));
    const out: string[] = [];
    for (const h of hrefs) {
      const r = await page.request.get(h!);
      expect(r.status(), h!).toBe(200);
      out.push(`${h} ${r.headers()["content-type"]}`);
    }
    expect(hrefs).toContain("/favicon.svg");
    return out.join(" · ");
  });

  const routes: [string, string, string, string][] = [
    ["overview", "genel-bakis", "Genel bakış", "overview"], ["explorer", "kesif", "3D Şehir Keşfi", "explorer-host"],
    ["lab", "laboratuvar", "Kümeleme Laboratuvarı", "lab"], ["models", "modeller", "Model Karşılaştırma", "models"], ["data", "veri", "Veri Gezgini", "data-explorer"],
  ];
  for (const [id, hash, label, tid] of routes) {
    await step(`G03-${id}`, "Genel", `Navigation › ${label}`, `Tıklayınca #/${hash}, başlık "${label} · Kaza Odak", ekran içeriği görünür`, async () => {
      await page.getByTestId("navigation").locator(`[data-route=${id}]`).click();
      await expect(page).toHaveURL(new RegExp(`#/${hash}$`));
      await expect(page).toHaveTitle(`${label} · Kaza Odak`);
      await expect(page.getByTestId(tid)).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("navigation").locator(`[data-route=${id}]`)).toHaveAttribute("aria-current", "page");
      return `URL #/${hash}, aria-current=page`;
    });
  }

  await step("G04", "Genel", "Navigation › Daralt/Genişlet", "Kenar çubuğu 248↔64 px; daraltılmışken simge ve ipucu görünür", async () => {
    await page.getByTestId("navigation").locator("[data-route=overview]").click();
    const nav = page.getByTestId("navigation");
    const w = async () => { await page.waitForTimeout(350); return Math.round((await nav.boundingBox())!.width); };
    if ((await w()) > 100) await page.getByTestId("nav-toggle").click();
    const collapsed = await w();
    expect(collapsed).toBe(64);
    await expect(nav).toHaveAttribute("data-collapsed", "true");
    await nav.locator("[data-route=lab]").hover();
    await expect(page.getByRole("tooltip").filter({ hasText: "Kümeleme Laboratuvarı" })).toBeVisible();
    await expect(nav.getByTestId("brand-mark")).toBeVisible();
    await page.getByTestId("nav-toggle").click();
    const expanded = await w();
    expect(expanded).toBe(248);
    await expect(nav).toHaveAttribute("data-collapsed", "false");
    return `${collapsed} px (ipucu + simge) → ${expanded} px`;
  });

  await step("G05", "Genel", "Atlama bağlantısı", "İlk Tab 'İçeriğe geç'e odaklanır; Enter odağı ana içeriğe taşır", async () => {
    await page.goto("about:blank");
    await page.goto("/#/genel-bakis");
    await expect(page.getByTestId("overview")).toBeVisible({ timeout: 60_000 });
    await page.keyboard.press("Tab");
    await expect(page.locator(".skip-link")).toBeFocused();
    await page.keyboard.press("Enter");
    expect(await page.evaluate(() => document.activeElement?.id)).toBe("main");
    return "odak #main";
  });

  await step("G06", "Genel", "Tarayıcı geri / doğrudan hash", "Geri tuşu önceki ekrana döner; #/modeller doğrudan açılır", async () => {
    await page.getByTestId("navigation").locator("[data-route=data]").click();
    await expect(page.getByTestId("data-explorer")).toBeVisible({ timeout: 60_000 });
    await page.goBack();
    await expect(page.getByTestId("overview")).toBeVisible();
    await page.goto("/#/modeller");
    await expect(page.getByTestId("models")).toBeVisible({ timeout: 60_000 });
    return "geri → Genel bakış; #/modeller → Model karşılaştırma";
  });

  await step("G07", "Genel (mobil)", "Mobil üst çubuk › Menü çekmecesi", "390 px'te menü düğmesi çekmeceyi açar; logo görünür; bağlantı ekranı değiştirip çekmeceyi kapatır", async () => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
    const m = await ctx.newPage();
    track(m, currentTest);
    await m.goto("/#/genel-bakis");
    await expect(m.getByTestId("overview")).toBeVisible({ timeout: 60_000 });
    await expect(m.locator("[data-testid=brand-mark]:visible")).toHaveCount(1);
    await m.getByTestId("mobile-menu").click();
    const sheet = m.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByTestId("brand-wordmark")).toHaveText("Kaza Odak");
    await m.screenshot({ path: `${SHOTS}/20-mobil-menu-cekmecesi.png` });
    await sheet.locator("[data-route=data]").click();
    await expect(sheet).toBeHidden();
    await expect(m.getByTestId("data-explorer")).toBeVisible({ timeout: 60_000 });
    await ctx.close();
    return "çekmece açıldı, Veri Gezgini'ne geçildi, çekmece kapandı";
  });
});

// ================================================================== 2) Genel bakış
test("Genel bakış etkileşimleri", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toHaveText("2.020.638", { timeout: 60_000 });
  const ov = await api(page, "/api/overview");
  await shot(page, "04-genel-bakis.png");

  await step("O01", "Genel bakış", "Özeti dışa aktar (menü)", "Menü üç biçim sunar; her bağlantı 200 ve doğru içerik türü döner", async () => {
    await page.getByTestId("overview-export").click();
    const items = page.getByRole("menuitem");
    await expect(items).toHaveCount(3);
    const out: string[] = [];
    for (const [i, ct] of [[0, "markdown"], [1, "csv"], [2, "json"]] as const) {
      const href = await items.nth(i).getAttribute("href");
      const r = await page.request.get(href!);
      expect(r.status()).toBe(200);
      expect(r.headers()["content-type"]).toContain(ct);
      out.push(`${href} → ${r.headers()["content-type"].split(";")[0]} ${tr((await r.body()).length)} B`);
    }
    const [dl] = await Promise.all([page.waitForEvent("download"), items.nth(1).click()]);
    out.push(`indirme: ${dl.suggestedFilename()}`);
    return out.join(" · ");
  });

  await step("O02", "Genel bakış", "Yıllara göre grafik › Tablo/Grafik düğmesi", "Tablo görünümü yıl satırlarını, Grafik görünümü çubuk grafiği gösterir", async () => {
    await page.getByRole("button", { name: "Tablo" }).click();
    const rows = page.locator("#years-title").locator("xpath=ancestor::section").locator("tbody tr");
    await expect(rows).toHaveCount(ov.by_year.length);
    await page.getByRole("button", { name: "Grafik" }).click();
    await expect(page.getByTestId("year-chart")).toBeVisible();
    return `${ov.by_year.length} yıl satırı ↔ grafik`;
  });

  await step("O03", "Genel bakış", "Yıl grafiği › çubuk ipucu", "Çubuğun üzerine gelince yıl ve kaza sayısı ipucu görünür", async () => {
    const box = (await page.getByTestId("year-chart").boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.55);
    const tip = page.locator(".recharts-tooltip-wrapper");
    await expect(tip).toContainText("Kaza");
    return (await tip.innerText()).replace(/\s+/g, " ").trim();
  });

  await step("O04", "Genel bakış", "Gürültü oranı › bilgi ipucu", "Bilgi simgesine odaklanınca açıklama (hata ölçüsü değildir) görünür", async () => {
    await page.getByTestId("ov-noise").getByRole("button", { name: "Açıklama" }).focus();
    await expect(page.getByRole("tooltip")).toContainText("hata ölçüsü değildir");
    await page.keyboard.press("Escape");
    return "ipucu klavye odağıyla açıldı";
  });

  await step("O05", "Genel bakış", "Kaynak bağlantısı", "NYC Open Data bağlantısı yeni sekmede, rel=noopener", async () => {
    const a = page.getByTestId("overview").locator("header a").first();
    const href = await a.getAttribute("href");
    expect(href).toMatch(/data\.cityofnewyork\.us/);
    expect(await a.getAttribute("target")).toBe("_blank");
    expect(await a.getAttribute("rel")).toContain("noopener");
    return href!;
  });

  await step("O06", "Genel bakış", "Model kartları", "Küme 4.179, gürültü %59,7, eligible 2.020.638 — API ile aynı", async () => {
    await expect(page.getByTestId("ov-clusters")).toContainText(tr(ov.model.clusters));
    await expect(page.getByTestId("ov-noise")).toContainText("%59,7");
    expect(ov.model.clusters).toBe(4179);
    return `küme ${tr(ov.model.clusters)}, gürültü %${(ov.model.noise_ratio * 100).toFixed(2)}`;
  });

  await step("O07", "Genel bakış", "3D haritada aç", "3D Şehir Keşfi açılır", async () => {
    await page.getByRole("button", { name: "3D haritada aç" }).click();
    await expect(page).toHaveURL(/#\/kesif$/);
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
    return "#/kesif, harita hazır";
  });

  await step("O08", "Genel bakış", "En yüksek kümeler › Haritada", "İlk küme haritada seçilir; ayrıntıdaki kayıt sayısı API ile aynı", async () => {
    await page.goto("/#/genel-bakis");
    const top = ov.top_clusters[0];
    await page.getByTestId(`open-cluster-${top.cluster_id}`).click();
    await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 90_000 });
    await expect(page.getByTestId("cluster-title")).toContainText(`Küme #${top.cluster_id}`);
    const d = await api(page, `/api/clusters/${top.cluster_id}`);
    await expect(page.getByTestId("cluster-events")).toHaveText(tr(d.n_events));
    expect(d.n_events).toBe(top.n_events);
    return `Küme #${top.cluster_id}: ${tr(d.n_events)} kayıt (genel bakış = ayrıntı = API)`;
  });
});

// ================================================================== 3) 3D Şehir — görünüm, kamera, katmanlar
test("3D Şehir Keşfi — kamera, ilçeler, katmanlar, tema, animasyon", async ({ page }) => {
  test.setTimeout(420_000);
  await openExplorer(page);
  await shot(page, "05-3d-sehir-genel.png");
  const meta = await api(page, "/api/meta");

  await step("E01", "3D Şehir", "Sol panel sekmeleri (Görünüm/Filtreler)", "Sekmeler panel içeriğini değiştirir", async () => {
    await page.getByTestId("tab-filters").click();
    await expect(page.getByTestId("filter-panel")).toBeVisible();
    await page.getByTestId("tab-view").click();
    await expect(page.getByTestId("model-card")).toBeVisible();
    return "Filtreler ↔ Görünüm";
  });
  await step("E02", "3D Şehir", "Araç çubuğu › Filtreler", "Düğme Filtreler sekmesini açıp kapatır (aria-pressed)", async () => {
    await page.getByTestId("toolbar-filters").click();
    await expect(page.getByTestId("toolbar-filters")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("filter-panel")).toBeVisible();
    await page.getByTestId("toolbar-filters").click();
    await expect(page.getByTestId("model-card")).toBeVisible();
    return "aria-pressed true → false";
  });

  for (const b of ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"]) {
    await step(`E03-${b}`, "3D Şehir", `İlçe kamerası › ${b}`, "Kamera ilçeye gider; harita merkezi ilçe sınır kutusunun içindedir", async () => {
      await page.getByTestId("borough-picker").locator(`[data-borough="${b}"]`).click();
      await expect(page.getByTestId("borough-picker").locator(`[data-borough="${b}"]`)).toHaveAttribute("aria-pressed", "true");
      await mapIdle(page, 400);
      const s = await mapState(page);
      const [w, so, e, n] = meta.boroughs.bounds[b];
      expect(s.center[0]).toBeGreaterThan(w); expect(s.center[0]).toBeLessThan(e);
      expect(s.center[1]).toBeGreaterThan(so); expect(s.center[1]).toBeLessThan(n);
      return `merkez ${s.center[0].toFixed(3)}, ${s.center[1].toFixed(3)} · zoom ${s.zoom.toFixed(1)}`;
    });
  }
  await shot(page, "06-3d-sehir-staten-island.png");
  await step("E03-TUM", "3D Şehir", "İlçe kamerası › Tüm NYC", "Kamera şehir ölçeğine döner", async () => {
    await page.getByTestId("borough-picker").getByRole("button", { name: "Tüm NYC" }).click();
    await mapIdle(page, 400);
    const s = await mapState(page);
    expect(s.zoom).toBeLessThan(11);
    return `zoom ${s.zoom.toFixed(2)}`;
  });

  // Kamera düğmeleri
  const cam = async (a: string) => { await page.getByTestId("camera-controls").locator(`[data-action=${a}]`).click(); await mapIdle(page, 300); return mapState(page); };
  await step("E05-zoom", "3D Şehir", "Kamera › Yakınlaştır / Uzaklaştır", "Zoom +1 / −1", async () => {
    const s0 = await mapState(page); const s1 = await cam("zoomIn"); const s2 = await cam("zoomOut");
    expect(s1.zoom - s0.zoom).toBeGreaterThan(0.9); expect(s1.zoom - s2.zoom).toBeGreaterThan(0.9);
    return `${s0.zoom.toFixed(2)} → ${s1.zoom.toFixed(2)} → ${s2.zoom.toFixed(2)}`;
  });
  await step("E05-rotate", "3D Şehir", "Kamera › Sola / Sağa döndür", "Yön ∓30°", async () => {
    const s0 = await mapState(page); const s1 = await cam("rotL"); const s2 = await cam("rotR");
    const d = (a: number, b: number) => ((a - b + 540) % 360) - 180;
    expect(Math.abs(d(s1.bearing, s0.bearing) + 30)).toBeLessThan(1); expect(Math.abs(d(s2.bearing, s0.bearing))).toBeLessThan(1);
    return `${s0.bearing.toFixed(0)}° → ${s1.bearing.toFixed(0)}° → ${s2.bearing.toFixed(0)}°`;
  });
  await step("E05-pitch", "3D Şehir", "Kamera › Eğimi artır / azalt", "Eğim ±10°", async () => {
    const s0 = await mapState(page); const s1 = await cam("pitchDown"); const s2 = await cam("pitchUp");
    expect(Math.round(s0.pitch - s1.pitch)).toBe(10); expect(Math.round(s2.pitch - s1.pitch)).toBe(10);
    return `${s0.pitch.toFixed(0)}° → ${s1.pitch.toFixed(0)}° → ${s2.pitch.toFixed(0)}°`;
  });
  await step("E05-north", "3D Şehir", "Kamera › Kuzeye çevir", "Yön 0°", async () => {
    await cam("rotR"); const s = await cam("north");
    expect(Math.abs(s.bearing)).toBeLessThan(0.5);
    return `yön ${s.bearing.toFixed(1)}°`;
  });
  await step("E17", "3D Şehir", "Fareyle harita döndürme (sağ tık sürükle)", "Sağ tuşla sürüklemek yönü değiştirir", async () => {
    const s0 = await mapState(page);
    const box = (await page.getByTestId("map").boundingBox())!;
    const x = box.x + box.width * 0.6, y = box.y + box.height * 0.5;
    await page.mouse.move(x, y); await page.mouse.down({ button: "right" });
    for (let i = 1; i <= 10; i++) await page.mouse.move(x + i * 15, y, { steps: 2 });
    await page.mouse.up({ button: "right" });
    await mapIdle(page, 300);
    const s1 = await mapState(page);
    expect(Math.abs(s1.bearing - s0.bearing)).toBeGreaterThan(5);
    return `yön ${s0.bearing.toFixed(1)}° → ${s1.bearing.toFixed(1)}°`;
  });
  await step("E05-reset", "3D Şehir", "Kamera › Görünümü sıfırla", "Tüm NYC görünümüne döner, ilçe seçimi temizlenir", async () => {
    await page.getByTestId("borough-picker").locator('[data-borough="BRONX"]').click();
    await mapIdle(page, 300);
    const s = await cam("reset");
    expect(s.zoom).toBeLessThan(11);
    await expect(page.getByTestId("borough-picker").getByRole("button", { name: "Tüm NYC" })).toHaveAttribute("aria-pressed", "true");
    return `zoom ${s.zoom.toFixed(2)}, Tüm NYC seçili`;
  });

  // Katmanlar
  const LAYER_MAP: Record<string, [string, string]> = {
    boroughs: ["İlçe sınırları", "borough-line"], density: ["Yoğunluk", "density-heat-1000"], centroids: ["Küme merkezleri", "centroid-circle"],
    geometries: ["Küme geometrileri", "geom-fill"], clustered: ["Kümelenmiş noktalar", "points-clustered"], noise: ["Gürültü noktaları", "points-noise"],
    buildings: ["3D binalar", "building-3d"], models: ["3D modeller", "city-models"],
  };
  for (const [key, [label, layerId]] of Object.entries(LAYER_MAP)) {
    await step(`E04-${key}`, "3D Şehir", `Katman anahtarı › ${label}`, "Anahtar katman görünürlüğünü değiştirir; tekrar basınca geri döner", async () => {
      const sw = page.getByTestId("layer-list").getByRole("switch", { name: label });
      const v0 = await page.evaluate((k) => (window as any).__saferoute.visibility()[k], key);
      await sw.click();
      const vis1 = await page.evaluate(([k, id]) => [(window as any).__saferoute.visibility()[k], (window as any).__saferoute.map.getLayoutProperty(id, "visibility") ?? "visible"], [key, layerId]);
      expect(vis1[0]).toBe(!v0);
      expect(vis1[1]).toBe(v0 ? "none" : "visible");
      await sw.click();
      const v2 = await page.evaluate((k) => (window as any).__saferoute.visibility()[k], key);
      expect(v2).toBe(v0);
      return `${v0 ? "açık" : "kapalı"} → ${vis1[1]} → ${v2 ? "açık" : "kapalı"} (${layerId})`;
    });
  }

  await step("E06", "3D Şehir", "Gece/Gündüz düğmesi", "Tema arka plan rengini değiştirir; etiket güncellenir", async () => {
    const bg0 = await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color"));
    await page.getByTestId("theme-toggle").click();
    // Kaza Odak geçişi: erişilebilir ad görünen metinle başlar (WCAG 2.5.3); eski beklenti "Gece moduna geç" idi
    await expect(page.getByTestId("theme-toggle")).toHaveAccessibleName("Gündüz modu — gece moduna geç");
    await expect(page.getByTestId("theme-toggle")).toContainText("Gündüz");
    await mapIdle(page, 600);
    const bg1 = await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color"));
    expect(bg1).not.toEqual(bg0);
    await shot(page, "07-3d-sehir-gunduz.png");
    await page.getByTestId("theme-toggle").click();
    const bg2 = await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color"));
    expect(bg2).toEqual(bg0);
    return `${bg0} → ${bg1} → ${bg2}`;
  });

  await step("E07", "3D Şehir", "Animasyon düzeyi seçicisi", "tam/azaltılmış/kapalı: belge ve 3D katman hareket düzeyi değişir", async () => {
    const out: string[] = [];
    for (const v of ["off", "reduced", "full"]) {
      await page.getByTestId("motion-select").selectOption(v);
      const st = await page.evaluate(() => [document.documentElement.dataset.motion, (window as any).__saferoute.layer()?.motion]);
      expect(st).toEqual([v, v]);
      out.push(v);
    }
    return out.join(" → ");
  });
});

// ================================================================== 4) Kümeler, noktalar, gürültü, GLB
test("3D Şehir — küme seçimi, ayrıntı paneli, noktalar, gürültü, GLB", async ({ page }) => {
  test.setTimeout(420_000);
  await openExplorer(page);

  await step("E09", "3D Şehir", "Haritada küme merkezine tıklama", "Tıklanan küme seçilir; panelde kimlik ve kayıt sayısı API ile aynı", async () => {
    const d = await api(page, `/api/clusters/${TILLARY}`);
    await flyTo(page, [d.centroid_lon, d.centroid_lat], 14.2, 40);
    const [x, y] = await pagePoint(page, [d.centroid_lon, d.centroid_lat]);
    await page.mouse.click(x, y);
    await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 60_000 });
    const sel = await page.evaluate(() => (window as any).__saferoute.selected()?.cluster_id);
    const det = await api(page, `/api/clusters/${sel}`);
    await expect(page.getByTestId("cluster-title")).toContainText(`Küme #${sel}`);
    await expect(page.getByTestId("cluster-events")).toHaveText(tr(det.n_events));
    await expect(page.getByTestId("cluster-experiment")).toHaveText(det.experiment_id);
    return `Küme #${sel}: ${tr(det.n_events)} kayıt, ${det.experiment_id}`;
  });
  await step("E21", "3D Şehir", "Seçim sonrası kamera / bina engeli", "Kümeye yaklaşınca merkez bir 3D binanın arkasında kalmaz; temsili araç notu gösterilir", async () => {
    await expect(page.getByTestId("sim-note")).toBeVisible({ timeout: 60_000 });
    await mapIdle(page, 800);
    const r = await page.evaluate(() => {
      const w = (window as any).__saferoute; const m = w.map; const s = w.selected();
      const p = m.project(s.centroid);
      const hits = m.getLayer("building-3d") ? m.queryRenderedFeatures([[p.x - 3, p.y - 3], [p.x + 3, p.y + 3]], { layers: ["building-3d"] }).length : 0;
      return { hits, zoom: m.getZoom(), pitch: m.getPitch() };
    });
    expect(r.hits).toBe(0);
    const note = await page.getByTestId("sim-note").innerText();
    expect(note).toMatch(/temsili|simülasyon|araç gösterilmiyor/);
    await shot(page, "08-kumeye-yakin-gorunum.png");
    return `bina örtüşmesi ${r.hits}, zoom ${r.zoom.toFixed(1)}, eğim ${r.pitch.toFixed(0)}° · not: "${note.slice(0, 90)}…"`;
  });
  await step("E22", "3D Şehir", "Temsili araç sahnesi (GLB)", "Seçili küme çevresinde GLB araçlar yüklenir; gerçek kaza animasyonu olarak sunulmaz", async () => {
    const st = await page.evaluate(() => (window as any).__saferoute.layer()?.status);
    expect(st.ready).toBe(true);
    expect(st.loaded.length).toBeGreaterThan(0);
    const legend = await page.getByTestId("sim-note").innerText();
    expect(legend).not.toMatch(/gerçek kaza (animasyonu|hareketi)/i);
    return `yüklenen GLB: ${st.loaded.join(", ")}`;
  });
  await page.getByTestId("right-panel").screenshot({ path: `${SHOTS}/09-kume-detay-paneli.png` });

  await step("E10", "3D Şehir", "Küme ayrıntısı › Odakla", "Kamera seçili kümeye geri uçar", async () => {
    const sel = await page.evaluate(() => (window as any).__saferoute.selected());
    await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.9, 40.75], zoom: 12 }));
    await mapIdle(page, 200);
    await page.getByTestId("cluster-panel").getByRole("button", { name: "Odakla" }).click();
    await mapIdle(page, 400);
    const s = await mapState(page);
    const dist = Math.hypot(s.center[0] - sel.centroid[0], s.center[1] - sel.centroid[1]);
    expect(dist).toBeLessThan(0.01);
    return `merkeze uzaklık ${dist.toFixed(5)}°, zoom ${s.zoom.toFixed(1)}`;
  });
  await step("E11", "3D Şehir", "Küme ayrıntısı › Kapat (X)", "Seçim temizlenir, ipucu metni geri gelir", async () => {
    await page.getByTestId("cluster-panel").getByRole("button", { name: "Seçimi kapat" }).click();
    await expect(page.getByTestId("cluster-hint")).toBeVisible();
    expect(await page.evaluate(() => (window as any).__saferoute.selected())).toBeNull();
    return "seçim yok";
  });

  await step("E12", "3D Şehir", "Zoom'a göre nokta yükleme", "zoom < 15 'yakınlaştırın'; zoom ≥ 15 görünen alan sayıları sunucudan gelir", async () => {
    const d = await api(page, `/api/clusters/${TILLARY}`);
    await flyTo(page, [d.centroid_lon, d.centroid_lat], 13.5, 0);
    await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "zoom-in");
    await flyTo(page, [d.centroid_lon, d.centroid_lat], 16.2, 0);
    await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "ready", { timeout: 30_000 });
    const txt = await page.getByTestId("viewport-stats").innerText();
    return txt.replace(/\s+/g, " ").slice(0, 140);
  });
  await step("E13", "3D Şehir", "Gürültü noktaları anahtarı", "Açılınca gürültü (−1) ve kümelenmiş noktalar ayrı katmanlarda; gürültüde küme kimliği yok", async () => {
    await page.getByTestId("layer-list").getByRole("switch", { name: "Gürültü noktaları" }).click();
    await expect(page.getByTestId("viewport-stats")).toHaveAttribute("data-state", "ready", { timeout: 30_000 });
    await page.waitForTimeout(800);
    const r = await page.evaluate(async () => {
      const fc = await (window as any).__saferoute.map.getSource("points").getData();
      const f = fc.features as any[];
      const noise = f.filter((x) => x.properties.noise);
      const clustered = f.filter((x) => !x.properties.noise);
      return { noise: noise.length, clustered: clustered.length,
        noiseWithCluster: noise.filter((x) => x.properties.cluster_id != null && x.properties.cluster_id >= 0).length,
        clusteredWithoutCluster: clustered.filter((x) => !(x.properties.cluster_id >= 0)).length };
    });
    expect(r.noise).toBeGreaterThan(0); expect(r.clustered).toBeGreaterThan(0);
    expect(r.noiseWithCluster).toBe(0); expect(r.clusteredWithoutCluster).toBe(0);
    await shot(page, "10-gurultu-ve-kumelenmis-noktalar.png");
    await page.getByTestId("layer-list").getByRole("switch", { name: "Gürültü noktaları" }).click();
    return `gürültü ${r.noise} konum (küme kimliği yok), kümelenmiş ${r.clustered} konum`;
  });

  await step("E08", "3D Şehir", "3D varlıklar › model yerleştir / düzenle / kaldır", "Panel açılır; model seçince GLB yerleştirilir; alanlar ve 'Harita merkezine taşı' çalışır; 'Modeli kaldır' sahneden siler", async () => {
    await page.getByTestId("assets-toggle").click();
    await expect(page.getByTestId("asset-inspector")).toBeVisible();
    const btn = page.getByTestId("asset-inspector").locator("[data-model]").first();
    const id = await btn.getAttribute("data-model");
    await btn.click();
    await expect(btn).toHaveAttribute("aria-pressed", "true");
    const count = () => page.evaluate(() => (window as any).__saferoute.layer()?.inspectorGroup?.children.length ?? -1);
    await expect.poll(count, { timeout: 30_000 }).toBe(1);
    await page.getByTestId("insp-heading").fill("90");
    await expect(page.getByTestId("insp-heading")).toHaveValue("90");
    await page.getByTestId("place-here").click();
    await expect(page.getByTestId("asset-license")).toBeVisible();
    await shot(page, "11-glb-varlik-inceleyici.png");
    await page.getByTestId("remove-model").click();
    await expect.poll(count).toBe(0);
    await page.getByTestId("asset-inspector").getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByTestId("asset-inspector")).toBeHidden();
    return `${id} yerleştirildi (1 nesne), yön 90°, merkeze taşındı, kaldırıldı (0 nesne), panel kapandı`;
  });
});

// ================================================================== 5) Zaman oynatma
test("3D Şehir — zaman oynatma", async ({ page }) => {
  test.setTimeout(300_000);
  await openExplorer(page);
  const readout = page.getByTestId("time-readout");

  for (const g of ["month", "dow", "hour", "year"]) {
    await step(`E14-${g}`, "3D Şehir", `Zaman ölçeği › ${g}`, "Ölçek değişince kova sayısı ve kaydırıcı aralığı değişir; dilim sıfırlanır", async () => {
      await page.getByTestId(`time-g-${g}`).click();
      await expect(page.getByTestId(`time-g-${g}`)).toHaveAttribute("data-state", "on");
      const tl = await api(page, `/api/records/timeline?granularity=${g}`);
      await expect.poll(async () => Number(await page.getByTestId("time-range").getAttribute("max")), { timeout: 30_000 }).toBe(tl.buckets.length - 1);
      return `${tl.buckets.length} kova`;
    });
  }
  await step("E15-next", "3D Şehir", "Zaman › Sonraki/Önceki adım", "Dilim ilerler/geriler; okuma alanında yıl ve kayıt sayısı API kovasıyla aynı", async () => {
    const tl = await api(page, "/api/records/timeline?granularity=year");
    await page.getByRole("button", { name: "Sonraki adım" }).click();
    await expect(readout).toContainText(tl.buckets[0].key);
    await expect(readout).toContainText(tr(tl.buckets[0].count));
    await page.getByRole("button", { name: "Sonraki adım" }).click();
    await expect(readout).toContainText(tl.buckets[1].key);
    await page.getByRole("button", { name: "Önceki adım" }).click();
    await expect(readout).toContainText(tl.buckets[0].key);
    return `${tl.buckets[0].key} (${tr(tl.buckets[0].count)} kayıt) ↔ ${tl.buckets[1].key}`;
  });
  await step("E15-slice-map", "3D Şehir", "Zaman dilimi › harita verisi", "Dilim seçilince merkezler /api/records/clusters'tan gelir; kimlikler modelin alt kümesi (etiket değişmez)", async () => {
    await mapIdle(page, 1200);
    const all = new Set((await api(page, "/api/clusters")).features.map((f: any) => f.properties.cluster_id));
    const ids = await centroidIds(page);
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.every((i) => all.has(i))).toBe(true);
    expect(await page.evaluate(() => (window as any).__saferoute.mode())).toContain("years=");
    return `${tr(ids.length)} küme (tümü model kimliği) · mod ${await page.evaluate(() => (window as any).__saferoute.mode())}`;
  });
  await step("E15-play", "3D Şehir", "Zaman › Oynat / Duraklat", "Oynat dilimi otomatik ilerletir; Duraklat durdurur", async () => {
    const before = await readout.innerText();
    await page.getByTestId("time-play").click();
    await expect(page.getByTestId("time-play")).toHaveAccessibleName("Oynatmayı duraklat");
    await expect(readout).not.toHaveText(before, { timeout: 8000 });
    await page.getByTestId("time-play").click();
    await expect(page.getByTestId("time-play")).toHaveAccessibleName("Zaman içinde oynat");
    const after = await readout.innerText();
    await page.waitForTimeout(3000);
    expect(await readout.innerText()).toBe(after);
    return `${before.split("·")[0].trim()} → ${after.split("·")[0].trim()} (duraklatınca sabit)`;
  });
  await step("E15-slider", "3D Şehir", "Zaman kaydırıcısı (klavye)", "Ok tuşu dilimi değiştirir; aria-valuetext güncellenir", async () => {
    const r = page.getByTestId("time-range");
    await r.focus();
    const v0 = await r.inputValue();
    await page.keyboard.press("ArrowRight");
    const v1 = await r.inputValue();
    expect(Number(v1)).toBe(Number(v0) + 1);
    return `değer ${v0} → ${v1}; ${await r.getAttribute("aria-valuetext")}`;
  });
  await step("E16", "3D Şehir", "Zaman histogramı çubuğuna tıklama", "Tıklanan kova seçilir", async () => {
    const bars = page.getByTestId("time-controls").locator("button[title]");
    const n = await bars.count();
    const title = (await bars.nth(n - 3).getAttribute("title"))!;
    await bars.nth(n - 3).click();
    await expect(readout).toContainText(title.split(" — ")[0]);
    return `"${title}" seçildi`;
  });
  await step("E15-clear", "3D Şehir", "Zaman › Dilimi kaldır (X)", "Tüm dönem görünümüne döner", async () => {
    await page.getByTestId("time-clear").click();
    await expect(readout).toContainText("Tüm dönem");
    await expect(page.getByTestId("time-controls")).toHaveAttribute("data-state", "all");
    return "Tüm dönem";
  });
});

// ================================================================== 6) Filtreler
test("3D Şehir — filtreler, birleşimler, boş sonuç, sıfırlama", async ({ page }) => {
  test.setTimeout(420_000);
  await openExplorer(page);
  await page.getByTestId("tab-filters").click();
  const preview = page.getByTestId("filter-preview");
  const expectPreview = async (q: string) => {
    const s = await api(page, `/api/records/summary?${q}`);
    await expect(preview).toContainText(`${tr(s.n_events)} kayıt`, { timeout: 30_000 });
    return s.n_events as number;
  };

  await step("F01", "3D Şehir › Filtreler", "İlçe çipleri (çoklu)", "Seçilen ilçeler önizlemeyi API sayısıyla günceller", async () => {
    await page.getByTestId("f-borough-STATEN ISLAND").click();
    const n1 = await expectPreview("boroughs=STATEN%20ISLAND");
    await page.getByTestId("f-borough-BRONX").click();
    const n2 = await expectPreview("boroughs=BRONX,STATEN%20ISLAND");
    await page.getByTestId("f-borough-BRONX").click();
    await expectPreview("boroughs=STATEN%20ISLAND");
    return `Staten Island ${tr(n1)} · + Bronx ${tr(n2)}`;
  });
  await step("F03", "3D Şehir › Filtreler", "Yıl çipleri", "Yıl seçimi önizlemeyi günceller; kısmi yıllar kesikli kenarlı", async () => {
    await page.getByTestId("f-year-2019").click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019");
    const dashed = await page.getByTestId("f-year-2012").evaluate((e) => getComputedStyle(e).borderStyle);
    expect(dashed).toBe("dashed");
    return `${tr(n)} kayıt · 2012 kenarı ${dashed}`;
  });
  await step("F04", "3D Şehir › Filtreler", "Ay çipleri", "Ay seçimi uygulanır", async () => {
    await page.getByRole("group", { name: "Ay filtresi" }).getByRole("button", { name: "Şub" }).click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2");
    return `${tr(n)} kayıt`;
  });
  await step("F05", "3D Şehir › Filtreler", "Haftanın günü çipleri", "Gün seçimi uygulanır (çoklu)", async () => {
    const g = page.getByRole("group", { name: "Gün filtresi" });
    await g.getByRole("button", { name: "Cmt" }).click(); await g.getByRole("button", { name: "Paz" }).click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6");
    return `${tr(n)} kayıt (hafta sonu)`;
  });
  await step("F06", "3D Şehir › Filtreler", "Saat aralığı anahtarı + seçiciler + gece örneği", "Anahtar 07–10'u açar; seçici değeri değiştirir; gece örneği 22–04 yapar", async () => {
    await page.locator("#f-hour-on").click();
    await expect(page.getByText("07:00 – 10:59")).toBeVisible();
    await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&hour_from=7&hour_to=10");
    await page.locator("#f-hourTo").click();
    await page.getByRole("option", { name: "12:00–12:59" }).click();
    await expect(page.getByText("07:00 – 12:59")).toBeVisible();
    await page.getByRole("button", { name: "Gece aralığı örneği: 22:00–04:59" }).click();
    await expect(page.getByText("(gece yarısını aşar)")).toBeVisible();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&hour_from=22&hour_to=4");
    await page.locator("#f-hour-on").click();
    await expect(page.getByText("Tüm saatler")).toBeVisible();
    return `07–10 → 07–12 → 22–04 (${tr(n)} kayıt) → kapalı`;
  });
  await step("F07", "3D Şehir › Filtreler", "Araç türü çipleri", "Kategori seçimi uygulanır", async () => {
    await page.getByTestId("f-vehicle-SUV").click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&vehicles=SUV");
    await page.getByTestId("f-vehicle-SUV").click();
    return `${tr(n)} kayıt (SUV), sonra kaldırıldı`;
  });
  await step("F08", "3D Şehir › Filtreler", "Katkı faktörü seçici", "Faktör seçimi uygulanır; 'Tümü' kaldırır", async () => {
    await page.locator("#f-factor").click();
    await page.getByRole("option", { name: /^Driver Inattention\/Distraction/ }).click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&factor=Driver%20Inattention%2FDistraction");
    await page.locator("#f-factor").click();
    await page.getByRole("option", { name: "Tümü" }).click();
    return `${tr(n)} kayıt, sonra Tümü`;
  });
  await step("F09", "3D Şehir › Filtreler", "Yaralanma durumu (tekli seçim)", "Yaralanmalı seçimi uygulanır", async () => {
    await page.getByRole("radiogroup", { name: "Yaralanma durumu" }).getByRole("radio", { name: "Yaralanmalı" }).click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&injury=injury");
    await page.getByRole("radiogroup", { name: "Yaralanma durumu" }).getByRole("radio", { name: "Tümü" }).click();
    return `${tr(n)} kayıt`;
  });
  await step("F11", "3D Şehir › Filtreler", "00:00 şüpheli kayıtları hariç tut", "Onay kutusu uygulanır", async () => {
    await page.locator("#f-midnight").click();
    const n = await expectPreview("boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6&exclude_midnight=true");
    await page.locator("#f-midnight").click();
    return `${tr(n)} kayıt`;
  });
  await step("F13", "3D Şehir › Filtreler", "Mevcut kümelerde göster", "Filtrelenmiş mod: bant 'yeniden kümeleme yapılmadı'; merkez kimlikleri model kimliklerinin alt kümesi; sayaç API ile aynı", async () => {
    await page.getByTestId("filter-apply").click();
    await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "filtered");
    await expect(page.getByTestId("mode-banner")).toContainText("yeniden kümeleme yapılmadı");
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
    await mapIdle(page, 800);
    const q = "boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6";
    const rc = await api(page, `/api/records/clusters?${q}`);
    const all = new Set((await api(page, "/api/clusters")).features.map((f: any) => f.properties.cluster_id));
    const ids = await centroidIds(page);
    expect(ids.length).toBe(rc.features.length);
    expect(ids.every((i) => all.has(i))).toBe(true);
    await page.getByTestId("tab-view").click();
    await expect(page.getByTestId("filtered-cluster-count")).toContainText(`${tr(rc.features.length)} / ${tr(rc.total_clusters)}`);
    await shot(page, "12-filtre-uygulanmis.png");
    return `${tr(ids.length)} / ${tr(rc.total_clusters)} küme; tüm kimlikler tam veri modelinde`;
  });
  await step("F18", "3D Şehir › Filtreler", "Filtre etkinken küme ayrıntısı", "Tam küme ve filtrelenmiş sayılar ayrı; küme kimliği değişmez", async () => {
    const q = "boroughs=STATEN%20ISLAND&years=2019&months=2&dows=5,6";
    const rc = await api(page, `/api/records/clusters?${q}`);
    const f = rc.features.sort((a: any, b: any) => b.properties.n_events - a.properties.n_events)[0];
    const [lon, lat] = f.geometry.coordinates;
    await flyTo(page, [lon, lat], 14.5, 30);
    const [x, y] = await pagePoint(page, [lon, lat]);
    await page.mouse.click(x, y);
    await expect(page.getByTestId("cluster-panel")).toHaveAttribute("data-status", "ready", { timeout: 60_000 });
    const sel = await page.evaluate(() => (window as any).__saferoute.selected()?.cluster_id);
    const det = await api(page, `/api/records/clusters/${sel}?experiment_id=dbscan-52abd2c018&${q}`);
    await expect(page.getByTestId("cluster-filtered")).toBeVisible();
    await expect(page.getByTestId("cluster-filtered-events")).toHaveText(tr(det.filtered.n_events));
    await expect(page.getByTestId("cluster-events")).toHaveText(tr(det.full.n_events));
    expect(det.full.cluster_id).toBe(sel);
    return `Küme #${sel}: tam ${tr(det.full.n_events)} / filtrelenmiş ${tr(det.filtered.n_events)}`;
  });
  await page.getByTestId("cluster-panel").getByRole("button", { name: "Seçimi kapat" }).click().catch(() => {});

  await page.getByTestId("tab-filters").click();
  await step("F15", "3D Şehir › Filtreler", "Geçersiz tarih aralığı", "Başlangıç > bitiş: hata mesajı, Uygula ve Laboratuvar düğmeleri devre dışı", async () => {
    await page.locator("#f-date-from").fill("2020-05-01");
    await page.locator("#f-date-to").fill("2019-05-01");
    await expect(page.getByTestId("filter-panel").getByRole("alert")).toContainText("Başlangıç tarihi bitiş tarihinden sonra olamaz");
    await expect(page.getByTestId("filter-apply")).toBeDisabled();
    await expect(page.getByTestId("filter-to-lab")).toBeDisabled();
    return "hata gösterildi, düğmeler kilitli";
  });
  await step("F16", "3D Şehir › Filtreler", "Boş sonuç birleşimi", "0 kayıt: önizleme 0, haritada 0 küme ve açık bir boş durum mesajı", async () => {
    await page.locator("#f-date-from").fill("2019-02-03");
    await page.locator("#f-date-to").fill("2019-02-03");
    await page.getByRole("radiogroup", { name: "Ölümlü kaza filtresi" }).getByRole("radio", { name: "Yalnızca ölümlü" }).click();
    await expect(preview).toContainText("0 kayıt", { timeout: 30_000 });
    await page.getByTestId("filter-apply").click();
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
    await mapIdle(page, 600);
    expect((await centroidIds(page)).length).toBe(0);
    await expect(page.getByTestId("empty-filter-result")).toBeVisible();
    await shot(page, "13-bos-filtre-sonucu.png");
    return `0 kayıt, 0 küme, boş durum: "${(await page.getByTestId("empty-filter-result").innerText()).replace(/\s+/g, " ").slice(0, 120)}"`;
  });
  await step("F14", "3D Şehir › Filtreler", "Filtreleri sıfırla", "Tüm filtreler temizlenir, seçili model moduna dönülür (4.179 küme)", async () => {
    await page.getByTestId("filter-reset").click();
    await expect(page.getByTestId("mode-banner")).toHaveCount(0);
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
    await mapIdle(page, 600);
    expect((await centroidIds(page)).length).toBe(4179);
    await expect(page.getByTestId("filter-reset")).toBeDisabled();
    return "4.179 küme, bant yok";
  });
  await step("F17", "3D Şehir › Filtreler", "Bu filtreyle yeni kümeleme başlat", "Filtre uygulanır ve Laboratuvar filtre kapsamıyla açılır; kapsam sayısı API ile aynı", async () => {
    await page.getByTestId("f-borough-STATEN ISLAND").click();
    await page.getByTestId("f-year-2019").click();
    await expectPreview("boroughs=STATEN%20ISLAND&years=2019");
    await page.getByTestId("filter-to-lab").click();
    await expect(page).toHaveURL(/#\/laboratuvar$/);
    await expect(page.getByTestId("lab-filter-scope")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("lab-scope-count")).toHaveText("6.686");
    return "Laboratuvar: kapsam 6.686 kayıt";
  });
  await step("F19", "Laboratuvar", "Kapsam › Filtreleri düzenle (3D Keşif)", "3D Keşif Filtreler sekmesiyle açılır, filtreler korunur", async () => {
    await page.getByRole("button", { name: "Filtreleri düzenle (3D Keşif)" }).click();
    await expect(page).toHaveURL(/#\/kesif$/);
    await expect(page.getByTestId("filter-panel")).toBeVisible();
    await expect(page.getByTestId("f-borough-STATEN ISLAND")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("filter-reset").click();
    return "Filtreler sekmesi açık, Staten Island seçili";
  });
});

// ================================================================== 7) Laboratuvar (ana sunucu; ağır hesaplama YOK)
test("Kümeleme Laboratuvarı — form, doğrulama, kayıtlı deneyler, geçmiş", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto("/#/laboratuvar");
  await expect(page.getByTestId("algorithm-controls")).toBeVisible({ timeout: 60_000 });
  await shot(page, "14-kumeleme-laboratuvari.png");

  await step("L01", "Laboratuvar", "Algoritma seçimi (DBSCAN/K-Means/HDBSCAN)", "Algoritma parametre alanlarını değiştirir", async () => {
    await page.getByTestId("lab-algo-kmeans").click();
    await expect(page.getByTestId("lab-param-k")).toHaveValue("20");
    await page.getByTestId("lab-algo-hdbscan").click();
    await expect(page.getByTestId("lab-param-min_cluster_size")).toBeVisible();
    await expect(page.getByTestId("lab-sample-n")).toHaveValue("100000");
    await page.getByTestId("lab-algo-dbscan").click();
    await expect(page.getByTestId("lab-param-eps_m")).toHaveValue("25");
    return "k / min_cluster_size + örneklem 100.000 / eps";
  });
  await step("L02", "Laboratuvar", "Öznitelik seti radyo düğmeleri", "Desteklenmeyen setler devre dışı ve gerekçeli; uzay-zaman seçilince eps_gün alanı çıkar", async () => {
    const dis = page.locator("[data-testid^=lab-fs-][data-disabled=true]");
    const n = await dis.count();
    expect(n).toBeGreaterThan(0);
    await expect(page.locator("[data-testid^=lab-fs-reason-]").first()).toContainText("Desteklenmiyor");
    await page.getByTestId("lab-fs-spatiotemporal").click();
    await expect(page.getByTestId("lab-param-eps_days")).toBeVisible();
    await page.getByTestId("lab-fs-spatial_haversine").click();
    await expect(page.getByTestId("lab-param-eps_days")).toHaveCount(0);
    return `${n} devre dışı set (gerekçeli); uzay-zaman → eps_gün`;
  });
  await step("L03", "Laboratuvar", "Parametre doğrulama (istemci)", "Sayı olmayan / aralık dışı değer hata verir, gönder düğmesi kilitlenir", async () => {
    await page.getByTestId("lab-param-eps_m").fill("abc");
    await expect(page.getByText("Sayı girin.")).toBeVisible();
    await expect(page.getByTestId("lab-submit")).toBeDisabled();
    await page.getByTestId("lab-param-eps_m").fill("99999");
    await expect(page.getByText(/aralığında olmalı/)).toBeVisible();
    await page.getByTestId("lab-param-min_samples").fill("2.5");
    await expect(page.getByText("Tamsayı olmalı.")).toBeVisible();
    await page.getByTestId("lab-param-eps_m").fill("25"); await page.getByTestId("lab-param-min_samples").fill("100");
    await expect(page.getByTestId("lab-submit")).toBeEnabled();
    return "abc → 'Sayı girin', 99999 → aralık hatası, 2.5 → tamsayı hatası";
  });
  await step("L18", "Laboratuvar", "Sunucu tarafı doğrulama (API)", "Geçersiz parametreler 422 ve Türkçe gerekçeyle reddedilir", async () => {
    const bad = [{ params: { eps_m: -5, min_samples: 10 } }, { params: { eps_m: 25, min_samples: 10, foo: 1 } }];
    const out: string[] = [];
    for (const b of bad) {
      const r = await page.request.post("/api/lab/jobs", { data: { algorithm: "dbscan", feature_set: "spatial_haversine", filters: {}, sample: null, ...b } });
      expect(r.status()).toBe(422);
      out.push(`${JSON.stringify(b.params)} → 422 ${JSON.stringify((await r.json()).detail).slice(0, 80)}`);
    }
    return out.join(" · ");
  });
  await step("L04", "Laboratuvar", "HDBSCAN › min_samples otomatik + eom/leaf", "Onay kutusu min_samples alanını kilitler; küme seçim yöntemi değişir", async () => {
    await page.getByTestId("lab-algo-hdbscan").click();
    await page.locator("#hdb-auto").click();
    await expect(page.getByTestId("lab-param-min_samples")).toBeDisabled();
    await page.getByRole("radiogroup", { name: "Küme seçim yöntemi" }).getByRole("radio", { name: "leaf" }).click();
    await expect(page.getByRole("radiogroup", { name: "Küme seçim yöntemi" }).getByRole("radio", { name: "leaf" })).toHaveAttribute("data-state", "on");
    await page.locator("#hdb-auto").click();
    return "min_samples kilitli, leaf seçili";
  });
  await step("L17", "Laboratuvar", "Kaynak bütçesi engeli", "HDBSCAN örneklemsiz tam veride bütçe uyarısı, gönder kilitli", async () => {
    await page.locator("#use-sample").click();
    await expect(page.getByTestId("lab-budget-block")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("lab-submit")).toBeDisabled();
    const t = await page.getByTestId("lab-budget-block").innerText();
    await page.locator("#use-sample").click();
    return t.replace(/\s+/g, " ").slice(0, 140);
  });
  await step("L05", "Laboratuvar", "Örneklem boyutu / tohum doğrulaması", "Geçersiz örneklem boyutu hata verir", async () => {
    await page.getByTestId("lab-sample-n").fill("10");
    await expect(page.getByText("1.000–2.100.000 arası tamsayı.")).toBeVisible();
    await page.getByTestId("lab-sample-n").fill("100000");
    await page.getByTestId("lab-algo-dbscan").click();
    return "10 → hata; 100.000 geri";
  });
  await step("L07", "Laboratuvar", "Kayıtlı konfigürasyon eşleşmesi → Kayıtlı sonucu yükle", "DBSCAN 25 m/100 (filtresiz) Faz 3 kaydıyla eşleşir; yeniden fit yok; 4.179 küme", async () => {
    await expect(page.getByTestId("lab-registry-hint")).toContainText("dbscan-52abd2c018");
    await expect(page.getByTestId("lab-submit")).toHaveText(/Kayıtlı sonucu yükle/);
    await page.getByTestId("lab-submit").click();
    await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 60_000 });
    await expect(page.getByTestId("job-source")).toContainText("Kayıtlı Faz 3 sonucu");
    await expect(page.getByTestId("result-clusters")).toContainText("4.179");
    await expect(page.getByTestId("result-noise")).toContainText("%59,7");
    return `${await page.getByTestId("job-ids").innerText()}`;
  });
  await step("L13", "Laboratuvar", "Kayıtlı deneyler › süzgeçler", "Algoritma ve aşama seçicileri satırları süzer", async () => {
    await page.getByTestId("tab-saved").click();
    const se = page.getByTestId("saved-experiments");
    await se.getByRole("combobox", { name: "Algoritma süzgeci" }).click();
    await page.getByRole("option", { name: "K-Means" }).click();
    const t1 = await se.locator("span.tabular").first().innerText();
    await se.getByRole("combobox", { name: "Aşama süzgeci" }).click();
    await page.getByRole("option", { name: "Tüm aşamalar" }).click();
    const t2 = await se.locator("span.tabular").first().innerText();
    expect(t1).not.toBe(t2);
    return `K-Means ızgara: ${t1}; tüm aşamalar: ${t2}`;
  });
  await step("L13b", "Laboratuvar", "Kayıtlı deney seçimi", "K-Means k=5 sonucu: 5 küme, gürültü 'Uygulanamaz'", async () => {
    await page.locator('[data-experiment="kmeans-24c07e9946"]').first().click();
    await expect(page.getByTestId("saved-view")).toHaveAttribute("data-experiment", "kmeans-24c07e9946");
    await expect(page.getByTestId("result-clusters")).toContainText("5");
    await expect(page.getByTestId("result-noise")).toContainText("Uygulanamaz");
    return "5 küme, gürültü Uygulanamaz";
  });
  await step("L15", "Laboratuvar", "Sonucu dışa aktar", "Menü bağlantıları 200 döner", async () => {
    await page.getByTestId("saved-view").getByRole("button", { name: "Sonucu dışa aktar" }).click();
    const items = page.getByRole("menuitem");
    const out: string[] = [];
    for (let i = 0; i < 3; i++) {
      const h = (await items.nth(i).getAttribute("href"))!;
      const r = await page.request.get(h);
      expect(r.status()).toBe(200);
      out.push(r.headers()["content-type"].split(";")[0]);
    }
    await page.keyboard.press("Escape");
    return out.join(", ");
  });
  await step("L14", "Laboratuvar", "Kayıtlı sonuç › Haritada göster", "3D Keşif sonuç modunda açılır; merkez sayısı sonuçla aynı; 'Seçili modele dön' çalışır", async () => {
    await page.locator('[data-experiment="hdbscan-ba3a1ff58d"]').first().click().catch(async () => {
      await page.getByTestId("tab-saved").click();
      await page.locator('[data-experiment="hdbscan-ba3a1ff58d"]').first().click();
    });
    await expect(page.getByTestId("saved-view")).toHaveAttribute("data-experiment", "hdbscan-ba3a1ff58d", { timeout: 30_000 });
    await page.getByTestId("show-on-map").click();
    await expect(page.getByTestId("mode-banner")).toHaveAttribute("data-mode", "result", { timeout: 60_000 });
    await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
    await mapIdle(page, 800);
    const n = (await centroidIds(page)).length;
    expect(n).toBe(768);
    await expect(page.getByTestId("time-coverage")).toContainText("100.000 olay");
    await shot(page, "15-kayitli-hdbscan-haritada.png");
    await page.getByTestId("back-to-model").click();
    await expect(page.getByTestId("mode-banner")).toHaveCount(0);
    await mapIdle(page, 800);
    expect((await centroidIds(page)).length).toBe(4179);
    return "HDBSCAN 768 küme / 100.000 olay kapsamı → modele dönüş 4.179";
  });
  await step("L16", "Laboratuvar", "İş geçmişi", "Geçmiş listelenir; bir işe tıklayınca iş görünümü açılır; kaynak sınırı işi gerekçesiyle görünür", async () => {
    await page.goto("/#/laboratuvar");
    await page.getByTestId("tab-history").click();
    const list = page.getByTestId("job-history");
    await expect(list).toBeVisible({ timeout: 30_000 });
    const n = await list.locator("li").count();
    const limited = list.locator("li", { has: page.locator('[data-state="resource_limited"]') }).first();
    let note = "kaynak sınırı işi yok";
    if (await limited.count()) {
      await limited.locator("button").click();
      await expect(page.getByTestId("job-rejected")).toBeVisible();
      note = (await page.getByTestId("job-rejected").innerText()).replace(/\s+/g, " ").slice(0, 120);
      await shot(page, "16-kaynak-siniri-is.png");
    } else {
      await list.locator("li button").first().click();
      await expect(page.getByTestId("job-view")).toBeVisible();
    }
    return `${n} iş; ${note}`;
  });
  await step("L20", "Laboratuvar", "Bellek yetersiz uyarısı (kaynak ölçümü)", "can_start=false iken açık uyarı ve gerekçe (yanıt tarayıcıda değiştirildi; gerçek ölçüm aşağıda)", async () => {
    const real = await api(page, "/api/lab/resources");
    await page.route("**/api/lab/resources*", (r) => r.fulfill({ json: { ...real, available_memory_mb: 900, can_start: false } }));
    await page.reload();
    await expect(page.getByTestId("lab-resources")).toHaveAttribute("data-testid", "lab-resources");
    await expect(page.getByText("Bellek yetersiz — yeni iş şu an başlatılamaz")).toBeVisible({ timeout: 30_000 });
    await page.unroute("**/api/lab/resources*");
    return `uyarı gösterildi · gerçek boş bellek ${tr(real.available_memory_mb)} MB (eşik ${tr(real.min_free_memory_mb)} MB)`;
  });
});

// ================================================================== 8) Laboratuvar — gerçek dinamik işler (yalıtılmış sunucu)
test.describe("Laboratuvar — dinamik iş, iptal, yeniden deneme, önbellek (yalıtılmış sunucu)", () => {
  const PORT = 8012;
  const BASE = `http://127.0.0.1:${PORT}`;
  const LAB = resolve(HERE, "../test-results/phase8-lab");
  const PY = resolve(ROOT, process.platform === "win32" ? "backend/.venv/Scripts/python.exe" : "backend/.venv/bin/python");
  let server: ChildProcess | null = null;
  test.use({ baseURL: BASE });
  test.beforeAll(async () => {
    rmSync(LAB, { recursive: true, force: true });
    mkdirSync(LAB, { recursive: true });
    server = spawn(PY, ["-c", "import sys; from saferoute.cli import main; sys.exit(main())", "serve", "--port", String(PORT), "--lab-root", LAB],
      { cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf-8", SAFEROUTE_LAB_TEST_DELAY_S: "6" }, stdio: "ignore", windowsHide: true });
    const t0 = Date.now();
    while (Date.now() - t0 < 150_000) {
      try { const r = await fetch(`${BASE}/api/analytics/status`); if (r.ok && (await r.json()).ready) return; } catch { /* açılıyor */ }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error("Yalıtılmış sunucu hazır olmadı");
  });
  test.afterAll(() => { if (server && server.exitCode === null) server.kill(); });

  test("Dinamik DBSCAN: başlat, iptal, yeniden dene, tamamla, önbellek, haritada göster", async ({ page }) => {
    test.setTimeout(420_000);
    await page.goto("/#/kesif");
    await page.getByTestId("tab-filters").click();
    await page.getByTestId("f-borough-STATEN ISLAND").click();
    await page.getByTestId("f-year-2019").click();
    await expect(page.getByTestId("filter-preview")).toContainText("6.686 kayıt", { timeout: 60_000 });
    await page.getByTestId("filter-to-lab").click();
    await expect(page.getByTestId("lab-scope-count")).toHaveText("6.686", { timeout: 60_000 });
    await page.getByTestId("lab-param-min_samples").fill("10");
    const free = (await api(page, "/api/lab/resources")).available_memory_mb;
    measurements.free_memory_before_dynamic_mb = free;

    let firstJob = "";
    await step("L08", "Laboratuvar", "Analizi başlat (gerçek ayrı süreç)", "İş kuyruğa alınır ve çalışır; aşama bilgisi gösterilir (ilerleme yüzdesi uydurulmaz)", async () => {
      await page.getByTestId("lab-submit").click();
      await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", /queued|running/, { timeout: 30_000 });
      await expect(page.getByTestId("job-stage")).toBeVisible();
      firstJob = (await page.getByTestId("job-view").getAttribute("data-job"))!;
      await shot(page, "17-dinamik-is-calisiyor.png");
      return `iş ${firstJob}: ${await page.getByTestId("job-stage").innerText().then((t) => t.split("\n")[0])}`;
    });
    await step("L09", "Laboratuvar", "İptal et", "Çalışan iş iptal edilir; durum 'İptal edildi'; çalışan süreç sonlandırılır", async () => {
      await page.getByTestId("job-cancel").click();
      await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "cancelled", { timeout: 30_000 });
      const j = await api(page, `/api/lab/jobs/${firstJob}`);
      return `durum ${j.state}; sonlandırma doğrulandı: ${JSON.stringify(j.worker?.termination?.verified ?? j.termination?.verified ?? "kayıtta yok")}`;
    });
    let retryJob = "";
    await step("L10", "Laboratuvar", "Yeniden dene", "Yeni iş kimliği, retry_of bağlantısı; iş gerçek olarak tamamlanır", async () => {
      await page.getByTestId("job-retry").click();
      await expect(page.getByTestId("job-view")).not.toHaveAttribute("data-job", firstJob, { timeout: 30_000 });
      retryJob = (await page.getByTestId("job-view").getAttribute("data-job"))!;
      await expect(page.getByTestId("job-ids")).toContainText(`${firstJob} işinin yeniden denemesi`);
      await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", /completed|resource_limited/, { timeout: 240_000 });
      const j = await api(page, `/api/lab/jobs/${retryJob}`);
      if (j.state === "resource_limited") throw new Error(`Kaynak sınırı: ${j.error}`);
      await shot(page, "18-dinamik-is-tamamlandi.png");
      measurements.dynamic_job = { job: retryJob, n_events: j.n_events, clusters: j.result.summary.n_clusters, runtime_s: j.worker?.runtime_s, peak_mb: j.worker?.peak_memory_mb };
      return `iş ${retryJob}: ${tr(j.n_events)} olay → ${tr(j.result.summary.n_clusters)} küme, fit ${j.worker?.runtime_s?.toFixed?.(2)} sn`;
    });
    await step("L11", "Laboratuvar", "Aynı istek yeniden → önbellek", "Aynı istek yeniden hesaplanmaz; 'Önbellekten' rozeti", async () => {
      await page.getByTestId("lab-submit").click();
      await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "completed", { timeout: 60_000 });
      await expect(page.getByTestId("job-source")).toContainText("Önbellekten");
      return `iş ${await page.getByTestId("job-view").getAttribute("data-job")} önbellekten`;
    });
    await step("L14b", "Laboratuvar", "Dinamik sonuç › Haritada göster", "Sonuç modunda merkez sayısı sonuç özetiyle aynı; bant 'Dinamik analiz sonucu'", async () => {
      const j = await api(page, `/api/lab/jobs/${retryJob}`);
      await page.getByTestId("show-on-map").click();
      await expect(page.getByTestId("mode-banner")).toContainText("Dinamik analiz sonucu", { timeout: 60_000 });
      await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
      await mapIdle(page, 800);
      expect((await centroidIds(page)).length).toBe(j.result.summary.n_clusters);
      return `${j.result.summary.n_clusters} merkez = sonuç özeti`;
    });
  });
});

// ================================================================== 9) Model karşılaştırma
test("Model karşılaştırma — akademik doğruluk ve etkileşimler", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/#/modeller");
  await expect(page.getByTestId("comparison-table")).toBeVisible({ timeout: 60_000 });
  const c = await api(page, "/api/models/comparison");
  await shot(page, "19-model-karsilastirma.png");
  const row = (a: string) => c.rows.find((r: any) => r.algorithm === a);

  await step("M01", "Model karşılaştırma", "Karşılaştırma tablosu", "DBSCAN 4.179 küme / %59,7 / 0,945; K-Means k=5 gürültü 'Uygulanamaz'; HDBSCAN 100.000 örneklem", async () => {
    expect(row("dbscan").n_clusters).toBe(4179);
    expect(row("dbscan").silhouette.toFixed(3)).toBe("0.945");
    expect(row("dbscan").noise_ratio).toBeCloseTo(0.5969, 3);
    expect(row("kmeans").parameters.k).toBe(5);
    expect(row("hdbscan").fit_n_events).toBe(100000);
    await expect(page.getByTestId("cmp-clusters-dbscan")).toContainText("4.179");
    await expect(page.getByTestId("cmp-noise-dbscan")).toContainText("%59,7");
    await expect(page.getByTestId("cmp-silhouette-dbscan")).toContainText("0,945");
    await expect(page.getByTestId("cmp-noise-kmeans")).toContainText("Uygulanamaz");
    await expect(page.getByTestId("cmp-clusters-hdbscan")).toContainText("örneklem (100k olay)");
    return `DBSCAN ${tr(row("dbscan").n_clusters)} / %${(row("dbscan").noise_ratio * 100).toFixed(2)} / ${row("dbscan").silhouette.toFixed(3)}; K-Means k=${row("kmeans").parameters.k}; HDBSCAN ${tr(row("hdbscan").fit_n_events)} olay`;
  });
  await step("M02", "Model karşılaştırma", "Siluet ≠ doğruluk", "Sayfada 'doğruluk/accuracy' etiketli metrik yok; %94,5 yalnızca olumsuzlanmış uyarıda geçer", async () => {
    const text = await page.getByTestId("models").innerText();
    expect(text).not.toMatch(/accuracy/i);
    const hits = text.split("\n").filter((l) => /%94,5/.test(l));
    expect(hits.every((l) => /değil|DEĞİL/.test(l))).toBe(true);
    const headers = await page.getByTestId("comparison-table").locator("th[scope=row]").allInnerTexts();
    expect(headers.some((h) => /doğruluk/i.test(h))).toBe(false);
    return `${hits.length} satırda %94,5 (hepsi olumsuz); satır başlıkları: ${headers.slice(6, 9).join(", ")}`;
  });
  for (const g of ["dbscan-grid", "hdbscan-grid"]) {
    await step(`M03-${g}`, "Model karşılaştırma", `${g} › metrik seçici`, "Metrik düğmesi hücre değerlerini değiştirir", async () => {
      const grid = page.getByTestId(g);
      const before = await grid.locator("tbody").innerText();
      await grid.getByRole("radio", { name: "Siluet" }).click();
      const after = await grid.locator("tbody").innerText();
      expect(after).not.toBe(before);
      await grid.getByRole("radio", { name: "Küme" }).click();
      return "Küme → Siluet → Küme";
    });
  }
  await step("M04", "Model karşılaştırma", "Bilgi ipuçları (Siluet satırı)", "İpucu 'doğruluk DEĞİLDİR' açıklamasını gösterir", async () => {
    const r = page.getByTestId("comparison-table").locator("th[scope=row]", { hasText: "Siluet" });
    await r.getByRole("button", { name: "Açıklama" }).hover();
    await expect(page.getByRole("tooltip")).toContainText("doğruluk DEĞİLDİR");
    return "ipucu görünür";
  });
  await step("M05", "Model karşılaştırma", "K-Means k taraması grafiği ipucu", "Noktanın üzerine gelince k ve siluet değeri görünür", async () => {
    const fig = page.getByTestId("kmeans-sweep").locator("figure").first();
    await fig.scrollIntoViewIfNeeded();
    const b = (await fig.boundingBox())!;
    for (const fx of [0.3, 0.5, 0.7]) {
      await page.mouse.move(b.x + b.width * fx, b.y + b.height * 0.5);
      if (await page.getByTestId("kmeans-sweep").locator(".recharts-tooltip-wrapper").filter({ hasText: "k =" }).count()) break;
    }
    const tip = page.getByTestId("kmeans-sweep").locator(".recharts-tooltip-wrapper").filter({ hasText: "k =" }).first();
    await expect(tip).toBeVisible();
    return (await tip.innerText()).replace(/\s+/g, " ");
  });
});

// ================================================================== 10) Veri gezgini
test("Veri Gezgini — sütunlar, arama, süzgeç, ayrıntı çekmecesi", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/#/veri");
  await expect(page.getByTestId("raw-rows")).toHaveText("2.269.187", { timeout: 60_000 });
  await shot(page, "21-veri-gezgini.png");
  const d = await api(page, "/api/data/dictionary");

  await step("D01", "Veri Gezgini", "Sekmeler (Veri hattı / Ham / İşlenmiş / Setler)", "Her sekme kendi içeriğini gösterir", async () => {
    await page.getByTestId("tab-raw").click(); await expect(page.getByTestId("dict-raw")).toBeVisible();
    await page.getByTestId("tab-processed").click(); await expect(page.getByTestId("dict-processed")).toBeVisible();
    await page.getByTestId("tab-sets").click(); await expect(page.getByTestId("feature-sets")).toBeVisible();
    await page.getByRole("tab", { name: "Veri hattı" }).click(); await expect(page.getByTestId("eligible-rows")).toBeVisible();
    return "4 sekme";
  });
  await step("D02", "Veri Gezgini", "Ham sütunlar: 29 sütun ve açıklamalar", "29/29 sütun; her satırda anlam", async () => {
    await page.getByTestId("tab-raw").click();
    const t = page.getByTestId("dict-raw");
    await expect(t).toContainText("29 / 29 sütun");
    expect(d.raw.column_count).toBe(29);
    const meanings = await t.locator("tbody tr td:nth-child(4)").allInnerTexts();
    const missing = meanings.filter((m) => m.trim() === "—").length;
    return `29 sütun; anlamı boş olan ${missing}`;
  });
  await step("D03", "Veri Gezgini", "Arama kutusu + boş sonuç", "Arama satırları süzer; eşleşme yoksa boş durum", async () => {
    const t = page.getByTestId("dict-raw");
    await t.getByRole("textbox").fill("borough");
    const n = await t.locator("tbody tr").count();
    expect(n).toBeGreaterThan(0); expect(n).toBeLessThan(29);
    await t.getByRole("textbox").fill("zzzyok");
    await expect(t.getByText("Aramayla eşleşen sütun yok.")).toBeVisible();
    await shot(page, "22-veri-gezgini-bos-arama.png");
    await t.getByRole("textbox").fill("");
    return `"borough" → ${n} sütun; "zzzyok" → boş durum`;
  });
  await step("D04", "Veri Gezgini", "Grup ve 'Modele giriş' seçicileri", "Seçiciler satırları süzer", async () => {
    const t = page.getByTestId("dict-raw");
    await t.getByRole("combobox", { name: "Modele giriş" }).click();
    await page.getByRole("option", { name: "Modele girenler" }).click();
    const a = await t.locator("[aria-live=polite]").innerText();
    await t.getByRole("combobox", { name: "Modele giriş" }).click();
    await page.getByRole("option", { name: "Tümü" }).click();
    await t.getByRole("combobox", { name: "Grup" }).click();
    await page.getByRole("option").nth(1).click();
    const b = await t.locator("[aria-live=polite]").innerText();
    await t.getByRole("combobox", { name: "Grup" }).click();
    await page.getByRole("option", { name: "Tüm gruplar" }).click();
    return `modele girenler: ${a}; ilk grup: ${b}`;
  });
  await step("D05", "Veri Gezgini", "Sütun ayrıntı çekmecesi", "Sütuna tıklayınca anlam/model/dönüşüm/gerekçe/eksik değer çekmecesi açılır ve kapanır", async () => {
    await page.locator('[data-column="latitude"]').click();
    const sh = page.getByTestId("feature-sheet");
    await expect(sh).toBeVisible();
    await expect(sh).toContainText("Ne anlama geliyor?");
    await expect(sh).toContainText("Eksik değer");
    await shot(page, "23-veri-gezgini-sutun-ayrintisi.png");
    await page.keyboard.press("Escape");
    await expect(sh).toBeHidden();
    return "latitude çekmecesi açıldı/kapandı (Esc)";
  });
  await step("D06", "Veri Gezgini", "İşlenmiş sütunlar (87) ve öznitelik setleri", "87 sütun; model setleri listelenir", async () => {
    await page.getByTestId("tab-processed").click();
    await expect(page.getByTestId("dict-processed")).toContainText(`${d.processed.column_count} / ${d.processed.column_count} sütun`);
    await page.getByTestId("tab-sets").click();
    const n = await page.getByTestId("feature-sets").locator("section").count();
    expect(n).toBe(d.feature_sets.length);
    return `${d.processed.column_count} sütun, ${n} öznitelik seti`;
  });
});

// ================================================================== 11) Hata ve boş durumları
test("Hata, yüklenme ve boş durumları", async ({ page }) => {
  test.setTimeout(180_000);
  await step("S01", "Genel bakış", "API hatası + Yeniden dene", "Sunucu 500 dönerse hata kutusu ve Yeniden dene; düzelince içerik gelir", async () => {
    await page.route("**/api/overview", (r) => r.fulfill({ status: 500, json: { detail: "Sunucu hatası (test)" } }));
    await page.goto("/#/genel-bakis");
    await expect(page.getByRole("alert")).toContainText("Veri alınamadı", { timeout: 30_000 });
    await shot(page, "24-hata-durumu.png");
    await page.unroute("**/api/overview");
    await page.getByRole("button", { name: "Yeniden dene" }).click();
    await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
    return "hata → yeniden dene → içerik";
  });
  await step("S02", "Laboratuvar", "Boş iş geçmişi / sonuç yok durumu", "İş yokken açıklayıcı boş durum", async () => {
    await page.route("**/api/lab/jobs?*", (r) => r.fulfill({ json: { jobs: [] } }));
    await page.goto("/#/laboratuvar");
    await page.getByTestId("tab-history").click();
    await expect(page.getByText("Kayıtlı iş yok.")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("tab-result").click();
    await page.unroute("**/api/lab/jobs?*");
    return "boş durum metni gösterildi";
  });
  await step("S03", "Model karşılaştırma", "Yüklenme durumu", "Yanıt gelene kadar iskelet (role=status) gösterilir", async () => {
    await page.route("**/api/models/comparison", async (r) => { await new Promise((x) => setTimeout(x, 1500)); await r.continue(); });
    await page.goto("/#/modeller");
    await expect(page.locator("[role=status][aria-busy=true]").first()).toBeVisible();
    await expect(page.getByTestId("comparison-table")).toBeVisible({ timeout: 60_000 });
    await page.unroute("**/api/models/comparison");
    return "iskelet → tablo";
  });
});

// ================================================================== 12) WebGL bağlam kaybı
test("WebGL bağlam kaybından dönüş", async ({ page }) => {
  test.setTimeout(240_000);
  await openExplorer(page);
  await step("E18", "3D Şehir", "WebGL bağlam kaybı → geri yükleme", "Bağlam geri gelince veri katmanları, 4.179 merkez ve 3D katman yeniden kurulur", async () => {
    const t0 = Date.now();
    await page.evaluate(() => {
      const gl = (window as any).__saferoute.map.painter.context.gl as WebGL2RenderingContext;
      const ext = gl.getExtension("WEBGL_lose_context")!;
      (window as any).__loseExt = ext;
      ext.loseContext();
    });
    await expect(page.getByTestId("load-status")).toContainText("WebGL bağlamı kaybedildi");
    await page.evaluate(() => (window as any).__loseExt.restoreContext());
    await expect(page.getByTestId("load-status")).toContainText("WebGL bağlamı geri yüklendi", { timeout: 60_000 });
    await mapIdle(page, 800);
    expect((await centroidIds(page)).length).toBe(4179);
    expect(await page.evaluate(() => !!(window as any).__saferoute.map.getLayer("city-models"))).toBe(true);
    return `toparlanma ${((Date.now() - t0) / 1000).toFixed(1)} sn; 4.179 merkez, city-models katmanı var`;
  });
});

// ================================================================== 12b) Altlık servis bağımsızlığı (Faz 8 kök neden düzeltmesi)
test("Altlık harita servisi erişilemezken kaza katmanları yine yüklenir", async ({ page }) => {
  test.setTimeout(180_000);
  await step("E20", "3D Şehir", "Üçüncü taraf altlık (OpenFreeMap) kesintisi", "Karo/tilejson/glif istekleri engellense de yerel API'den 4.179 küme merkezi yüklenir ve durum 'hazır' olur", async () => {
    let blocked = 0;
    await page.route(/openfreemap\.org/, (r) => { blocked += 1; return r.abort("connectionfailed"); });
    const t0 = Date.now();
    await page.goto("/#/kesif");
    await expect(page.getByTestId("load-status")).toContainText("Gerçek veri yüklendi", { timeout: 60_000 });
    const ms = Date.now() - t0;
    expect((await centroidIds(page)).length).toBe(4179);
    await shot(page, "27-altlik-kesintisinde-kaza-katmanlari.png");
    await page.unroute(/openfreemap\.org/);
    measurements.basemap_blocked_data_ready_ms = ms;
    return `${blocked} altlık isteği engellendi; kaza verisi ${(ms / 1000).toFixed(1)} sn'de hazır, 4.179 merkez`;
  });
});

// ================================================================== 13) Responsive
const VIEWPORTS = [
  { name: "1920x1080", width: 1920, height: 1080 }, { name: "1440x900", width: 1440, height: 900 }, { name: "1280x720", width: 1280, height: 720 },
  { name: "768x1024", width: 768, height: 1024 }, { name: "390x844", width: 390, height: 844 },
];
const SCREENS: [string, string][] = [["genel-bakis", "overview"], ["kesif", "explorer-host"], ["laboratuvar", "lab"], ["modeller", "models"], ["veri", "data-explorer"]];

async function responsive(browser: Browser, vp: typeof VIEWPORTS[number]) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  track(p, currentTest);
  const out: string[] = [];
  for (const [hash, tid] of SCREENS) {
    await p.goto(`/#/${hash}`);
    await expect(p.getByTestId(tid)).toBeVisible({ timeout: 90_000 });
    if (hash === "kesif") await expect(p.getByTestId("load-status").or(p.getByTestId("mobile-panel")).first()).toBeAttached({ timeout: 60_000 });
    await p.waitForTimeout(hash === "kesif" ? 2500 : 600);
    const ov = await noOverflow(p);
    expect(ov, `${hash} yatay taşma`).toBeLessThanOrEqual(0);
    if (vp.width === 1440 || vp.width <= 768) await p.screenshot({ path: `${SHOTS}/25-responsive-${vp.name}-${hash}.png` });
    out.push(`${hash}: taşma ${ov}`);
  }
  if (vp.width < 768) {
    await p.goto("/#/kesif");
    await p.getByTestId("mobile-panel").click();
    await expect(p.getByRole("dialog")).toBeVisible();
    await expect(p.getByRole("dialog").getByTestId("borough-picker")).toBeVisible();
    await p.screenshot({ path: `${SHOTS}/26-mobil-3d-katman-cekmecesi.png` });
    await p.keyboard.press("Escape");
    out.push("mobil katman çekmecesi açıldı");
    await expect(p.getByTestId("mobile-motion-select")).toBeVisible();
    out.push("mobil animasyon seçicisi görünür");
  }
  await ctx.close();
  return out.join(" · ");
}
for (const vp of VIEWPORTS) {
  test(`Responsive ${vp.name}`, async ({ browser }) => {
    test.setTimeout(300_000);
    await step(`R-${vp.name}`, "Tüm ekranlar", `Görüntü alanı ${vp.name}`, "Beş ekranda yatay taşma yok; mobilde çekmeceler çalışır", () => responsive(browser, vp));
  });
}

// ================================================================== 14) Klavye, odak, azaltılmış hareket, erişilebilirlik
test("Klavye odağı, azaltılmış hareket ve axe", async ({ page, browser }) => {
  test.setTimeout(300_000);
  await step("A01", "Genel", "Odak göstergesi", "Klavyeyle odaklanan gezinme bağlantısında görünür odak halkası (odaklı/odaksız stil farklı)", async () => {
    await page.goto("about:blank");
    await page.goto("/#/genel-bakis");
    await expect(page.getByTestId("overview")).toBeVisible({ timeout: 60_000 });
    await page.keyboard.press("Tab"); await page.keyboard.press("Tab");
    const style = () => page.evaluate(() => { const e = document.activeElement as HTMLElement; const c = getComputedStyle(e); return { route: e.dataset.route, ring: `${c.boxShadow}|${c.outlineStyle}|${c.outlineWidth}` }; });
    const focused = await style();
    expect(focused.route).toBe("overview");
    const unfocused = await page.locator("[data-route=lab]").evaluate((e) => { const c = getComputedStyle(e); return `${c.boxShadow}|${c.outlineStyle}|${c.outlineWidth}`; });
    expect(focused.ring).not.toBe(unfocused);
    return `odaklı: ${focused.ring.slice(0, 70)}…`;
  });
  await step("A02", "3D Şehir", "prefers-reduced-motion", "İşletim sistemi azaltılmış hareket isterse animasyon düzeyi 'azaltılmış' başlar", async () => {
    const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
    const p = await ctx.newPage();
    await p.goto("/#/kesif");
    await expect(p.getByTestId("motion-select")).toHaveValue("reduced", { timeout: 60_000 });
    await ctx.close();
    return "motion-select = reduced";
  });
  for (const [hash, tid] of SCREENS) {
    await step(`A03-${hash}`, hash, "axe-core (WCAG 2.0/2.1/2.2 A–AA)", "Ciddi/kritik ihlal yok", async () => {
      await page.goto(`/#/${hash}`);
      await expect(page.getByTestId(tid)).toBeVisible({ timeout: 90_000 });
      if (hash === "kesif") await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
      await page.waitForTimeout(800);
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).exclude(".maplibregl-canvas").analyze();
      a11y[hash] = { violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })), passes: r.passes.length };
      const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => v.id)).toEqual([]);
      return `${r.violations.length} ihlal (${r.violations.map((v) => `${v.id}:${v.impact}`).join(", ") || "yok"}), ${r.passes.length} geçen kural`;
    });
  }
});
