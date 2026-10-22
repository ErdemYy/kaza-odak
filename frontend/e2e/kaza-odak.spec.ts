// Kaza Odak marka geçişi — gerçek tarayıcı doğrulaması. Beş ekran, sekme başlığı, kenar çubuğu marka kilidi ve ipucu,
// mobil menü, favikon, Gece/Gündüz düğmesinin erişilebilir adı (WCAG 2.5.3), GLB önizleme ve 390 px Genel bakış yerleşimi.
// Çıktı: reports/kaza-odak/ (SAFEROUTE_KAZA_ODAK_OUT ile yönlendirilebilir).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.SAFEROUTE_KAZA_ODAK_OUT ? resolve(process.env.SAFEROUTE_KAZA_ODAK_OUT) : resolve(HERE, "../../reports/kaza-odak");
const SHOTS = resolve(OUT, "screenshots");
mkdirSync(SHOTS, { recursive: true });
const SUBTITLE = "Makine Öğrenmesi ile Trafik Kazalarının Mekânsal Analizi ve 3D Görselleştirilmesi";
const results: Record<string, unknown> = {};
test.afterAll(() => writeFileSync(resolve(OUT, "kaza_odak_results.json"), JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2)));

async function idleMap(page: Page) {
  await expect(page.getByTestId("load-status")).toHaveAttribute("data-phase", "ready", { timeout: 90_000 });
  await page.waitForFunction(() => { const m = (window as any).__saferoute?.map; return m && m.loaded() && !m.isMoving(); }, null, { timeout: 90_000 });
  await page.waitForTimeout(800);
}

test("Masaüstü: beş ekran, sekme başlığı, marka kilidi, ipucu, favikon", async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && !/openfreemap|openmaptiles/.test(m.text())) errors.push(m.text()); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  const routes = await page.evaluate(() => [...document.querySelectorAll("[data-route]")].map((a) => [a.getAttribute("data-route"), a.getAttribute("href")]));
  const titles: Record<string, string> = {};
  for (const [id, href] of routes as [string, string][]) {
    await page.locator(`nav [data-route="${id}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    titles[id] = await page.title();
    expect(titles[id]).toMatch(/ · Kaza Odak$/);
    if (id === "explorer") await idleMap(page); else await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/ekran-${id}.png` });
  }
  results.titles = titles;
  expect(Object.keys(titles)).toHaveLength(5);

  // Kenar çubuğu (Genel bakışta açık): marka kilidi + kısa alt satır + tam alt başlık ipucu
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  const nav = page.getByTestId("navigation");
  if ((await nav.getAttribute("data-collapsed")) === "true") await page.getByTestId("nav-toggle").click();
  await expect(nav.getByTestId("brand-wordmark")).toHaveText("Kaza Odak");
  await expect(nav.getByTestId("brand-mark")).toBeVisible();
  await nav.getByTestId("brand").hover();
  await expect(page.getByRole("tooltip")).toContainText(SUBTITLE);
  await nav.screenshot({ path: `${SHOTS}/kenar-cubugu-acik.png` });
  await page.mouse.move(700, 500);
  await page.getByTestId("nav-toggle").click();
  await expect(nav).toHaveAttribute("data-collapsed", "true");
  await expect(nav.getByRole("img", { name: "Kaza Odak" })).toBeVisible();
  await nav.getByTestId("brand").hover();
  await expect(page.getByRole("tooltip")).toContainText("Kaza Odak");
  await page.screenshot({ path: `${SHOTS}/kenar-cubugu-dar-ipucu.png`, clip: { x: 0, y: 0, width: 420, height: 160 } });
  await page.getByTestId("nav-toggle").click();

  // Favikon ve sayfa meta verisi
  const head = await page.evaluate(() => ({
    icon: document.querySelector('link[rel="icon"][type="image/svg+xml"]')?.getAttribute("href"),
    desc: document.querySelector('meta[name="description"]')?.getAttribute("content"),
    app: document.querySelector('meta[name="application-name"]')?.getAttribute("content"),
  }));
  expect(head.icon).toBe("/favicon.svg");
  expect(head.desc).toContain(SUBTITLE);
  expect(head.app).toBe("Kaza Odak");
  const fav = await (await page.request.get("/favicon.svg")).text();
  expect(fav).toContain("<title>Kaza Odak</title>");
  expect(fav).not.toMatch(/SafeRoute/);
  for (const f of ["kaza-odak-logo.svg", "kaza-odak-mark.svg", "kaza-odak-app-icon.svg"]) expect((await page.request.get(`/brand/${f}`)).status()).toBe(200);
  results.head = head;
  expect(errors).toEqual([]);
});

test("Gece/Gündüz düğmesi: erişilebilir ad görünen metinle başlar; axe label-in-name 0", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/kesif");
  await idleMap(page);
  const btn = page.getByTestId("theme-toggle");
  const states: unknown[] = [];
  for (let i = 0; i < 2; i++) {
    const visible = (await btn.innerText()).trim();
    const name = await btn.evaluate((el) => el.getAttribute("aria-label"));
    expect(name!.toLocaleLowerCase("tr").startsWith(visible.toLocaleLowerCase("tr"))).toBe(true);
    const axe = await new AxeBuilder({ page }).withRules(["label-content-name-mismatch"]).analyze();
    expect(axe.violations).toEqual([]);
    states.push({ visible, name, bg: await page.evaluate(() => (window as any).__saferoute.map.getPaintProperty("background", "background-color")) });
    if (i === 0) {
      await btn.click();
      await page.waitForTimeout(800);
      await idleMap(page);
      await page.screenshot({ path: `${SHOTS}/gunduz-modu.png` });
    }
  }
  await btn.click();
  results.theme = states;
  expect((states[0] as { bg: string }).bg).toBe("#0B1120");
  expect((states[1] as { bg: string }).bg).toBe("#E8EDF3");
});

test("GLB önizleme yeni markayla çalışır", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/kesif");
  await idleMap(page);
  await page.evaluate(() => (window as any).__saferoute.map.jumpTo({ center: [-73.98397, 40.69471], zoom: 19, pitch: 60, bearing: 335 }));
  await page.getByTestId("assets-toggle").click();
  await page.click('[data-model="taxi"]');
  await expect(page.getByTestId("glb-preview")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await expect(page.getByTestId("preview-license-short")).toContainText("CC0");
  await page.getByTestId("right-panel").screenshot({ path: `${SHOTS}/glb-onizleme.png` });
  await page.getByTestId("asset-inspector").getByRole("button", { name: "Kapat" }).click();
  const d = await page.evaluate(() => (window as any).__saferoutePreview);
  expect(d.live).toBe(0);
  expect(d.lastDispose.gpuGeometriesLeft).toBe(0);
  results.glb = d.lastDispose;
});

test("Mobil 390 px: menü, marka, alt başlık ve Genel bakış yerleşimi", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#/genel-bakis");
  await expect(page.getByTestId("hero-eligible")).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(800);
  // Kayma ölçüsü: ana sayının ilk ekrandaki konumu (Faz 8: ~472 px, Faz 8B: ~650 px)
  const heroTop = (await page.getByTestId("hero-eligible").boundingBox())!.y;
  const scope = (await page.getByTestId("ov-scope").boundingBox())!;
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over).toBeLessThanOrEqual(0);
  await expect(page.getByTestId("freshness-warning")).toBeVisible();
  await expect(page.getByTestId("ov-coverage")).toBeVisible();
  await expect(page.getByTestId("ov-model-period")).toBeVisible();
  expect(heroTop).toBeLessThan(560);
  await page.screenshot({ path: `${SHOTS}/mobil-genel-bakis.png` });
  results.mobile = { heroTop: Math.round(heroTop), scopeHeight: Math.round(scope.height), overflow: over };

  await page.getByTestId("mobile-menu").click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByTestId("brand-wordmark")).toHaveText("Kaza Odak");
  await expect(sheet.getByTestId("brand-subtitle")).toHaveText(SUBTITLE);
  await expect(sheet.getByTestId("brand-subtitle")).toBeInViewport();
  await page.waitForTimeout(600); // çekmece kayma animasyonu bitsin (görsel kanıt)
  await page.screenshot({ path: `${SHOTS}/mobil-menu.png` });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("img", { name: "Kaza Odak" }).first()).toBeVisible(); // mobil üst çubuk simgesi
});
