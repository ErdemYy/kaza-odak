import { defineConfig } from "@playwright/test";

// Faz 6 performans ölçümü: aynı senaryo üç WebGL arka ucunda. Hangi donanımın kullanıldığı ölçüm sırasında
// WEBGL_debug_renderer_info ile DOĞRULANIR ve sonuç dosyasına yazılır; yazılım WebGL (SwiftShader) sonuçları
// GPU performansı olarak raporlanmaz. Çalıştırma: npx playwright test -c playwright.perf.config.ts
// Uygulama sunucusu çalışıyor olmalıdır (scripts\start_saferoute.ps1).
const common = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--disable-renderer-backgrounding",
  "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows"];
export default defineConfig({
  testDir: "e2e-perf",
  testMatch: "*.perf.ts",
  timeout: 300_000,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: process.env.SAFEROUTE_E2E_URL ?? "http://127.0.0.1:8000", viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 },
  projects: [
    { name: "gpu-varsayilan", use: { channel: "chromium", launchOptions: { args: [...common, "--use-angle=d3d11", "--enable-gpu"] } } },
    { name: "gpu-yuksek-performans", use: { channel: "chromium", launchOptions: { args: [...common, "--use-angle=d3d11", "--enable-gpu", "--force_high_performance_gpu"] } } },
    { name: "swiftshader-yazilim", use: { launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] } } },
  ],
});
