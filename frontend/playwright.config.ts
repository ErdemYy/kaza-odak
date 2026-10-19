import { defineConfig, devices } from "@playwright/test";

// Uçtan uca testler GERÇEK çalışan uygulamada yürür: FastAPI katman sunucusu (doğrulanmış Faz 3
// çıktıları) + derlenmiş ön yüz (frontend/dist) + OpenFreeMap vektör karoları (ağ gerekir).
// Sunucu çalışmıyorsa `saferoute serve` başlatılır.
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "test-results/e2e-results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    viewport: { width: 1600, height: 960 },
    deviceScaleFactor: 1,
    ...devices["Desktop Chrome"],
    launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] },
  },
  projects: [{ name: "chromium", use: { viewport: { width: 1600, height: 960 } } }],
  webServer: {
    command: process.platform === "win32"
      ? "..\\backend\\.venv\\Scripts\\saferoute.exe serve --port 8000"
      : "../backend/.venv/bin/saferoute serve --port 8000",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
    env: { PYTHONIOENCODING: "utf-8" },
  },
});
