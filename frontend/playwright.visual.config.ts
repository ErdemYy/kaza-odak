import { defineConfig } from "@playwright/test";

// Faz 8B görsel karşılaştırma: aynı sahneler (kamera, zoom, eğim, yön, filtre, model) değişiklik öncesi ve sonrası
// aynı GPU arka ucunda yakalanır. Çıktı dizini SAFEROUTE_PHASE8B_SHOTS ile verilir (ör. reports/phase8b/screenshots/before);
// önce/sonra çalıştırmaları birbirinin dosyalarını silmez. Uygulama sunucusu çalışıyor olmalıdır (port 8000).
export default defineConfig({
  testDir: "e2e-visual",
  testMatch: "*.visual.ts",
  timeout: 600_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.SAFEROUTE_E2E_URL ?? "http://127.0.0.1:8000",
    deviceScaleFactor: 1,
    channel: "chromium",
    launchOptions: { args: ["--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=d3d11", "--enable-gpu-rasterization",
      "--disable-renderer-backgrounding", "--disable-background-timer-throttling"] },
  },
});
