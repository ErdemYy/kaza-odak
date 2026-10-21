// Faz 6 — sunucu yeniden başlatma senaryosu (GERÇEK süreçler). Ana sunucuya ve ana iş kaydına dokunmamak için
// ayrı bir port (8011) ve yalıtılmış laboratuvar dizini (test-results/phase6-restart-lab) kullanılır.
//  1) Sunucu A çalışırken gerçek bir laboratuvar işi başlar (çalışan süreç ayrı PID).
//  2) Sunucu A ÇÖKER (TerminateProcess; kapanış kancası çalışmaz).
//  3) Windows iş nesnesi (KILL_ON_JOB_CLOSE) çalışan süreci de sonlandırmış olmalı: yetim Python süreci yok.
//  4) Sunucu B aynı kayıtla açılır: iş "Yarıda kaldı" görünür, kendiliğinden yeniden ÇALIŞTIRILMAZ.
//  5) Arayüzden "Yeniden dene" → yeni iş kimliği, retry_of bağlantısı, gerçek tamamlanma.
import { expect, test } from "@playwright/test";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../..");
const PORT = 8011;
const BASE = `http://127.0.0.1:${PORT}`;
const LAB = resolve(HERE, "../test-results/phase6-restart-lab");
const OUT = resolve(ROOT, "reports/phase6");
const PY = resolve(ROOT, process.platform === "win32" ? "backend/.venv/Scripts/python.exe" : "backend/.venv/bin/python");
mkdirSync(resolve(OUT, "screenshots"), { recursive: true });
const log: Record<string, unknown> = {};

test.use({ baseURL: BASE, viewport: { width: 1440, height: 900 } });
test.describe.configure({ mode: "serial" });

async function getJSON(path: string) {
  const r = await fetch(`${BASE}${path}`);
  return { status: r.status, body: await r.json() };
}
async function waitReady(proc: ChildProcess, timeoutMs = 120_000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (proc.exitCode !== null) throw new Error(`Sunucu açılmadan sonlandı (çıkış ${proc.exitCode})`);
    try {
      const s = await getJSON("/api/analytics/status");
      if (s.body.ready) return { ...s.body, ready_ms: Date.now() - t0 };
    } catch { /* henüz dinlemiyor */ }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error("Sunucu hazır olmadı");
}
function startServer(extraEnv: Record<string, string> = {}) {
  return spawn(PY, ["-c", "import sys; from saferoute.cli import main; sys.exit(main())", "serve", "--port", String(PORT), "--lab-root", LAB],
    { cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf-8", ...extraEnv }, stdio: "ignore", windowsHide: true });
}
function alive(pid: number): boolean {
  try { process.kill(pid, 0); return true; } catch { return false; }
}
function crash(proc: ChildProcess) {
  // Sert sonlandırma: Windows'ta TerminateProcess (yalnızca sunucu; alt süreç ağacı ÖLDÜRÜLMEZ)
  if (process.platform === "win32") execFileSync("taskkill", ["/PID", String(proc.pid), "/F"]);
  else proc.kill("SIGKILL");
}

let server: ChildProcess | null = null;
test.afterAll(() => {
  if (server && server.exitCode === null) server.kill();
  writeFileSync(resolve(OUT, "restart_scenario.json"), JSON.stringify({ generated_at: new Date().toISOString(), ...log }, null, 2));
});

test("Sunucu çökmesi → yetim süreç yok → iş 'Yarıda kaldı' → açık yeniden deneme", async ({ page }) => {
  test.setTimeout(420_000);
  rmSync(LAB, { recursive: true, force: true });
  server = startServer({ SAFEROUTE_LAB_TEST_DELAY_S: "90" });
  const st = await waitReady(server);
  log.server_a_ready_ms = st.ready_ms;
  const res = (await getJSON("/api/lab/resources")).body;
  log.resources_before = res;
  test.skip(!res.can_start, `Bellek yetersiz (${res.available_memory_mb} MB < ${res.min_free_memory_mb} MB): gerçek iş başlatılamadığı için senaryo atlandı`);

  const body = { algorithm: "dbscan", feature_set: "spatial_haversine", params: { eps_m: 35, min_samples: 15 },
    filters: { boroughs: "MANHATTAN", years: "2018" } };
  const sub = await fetch(`${BASE}/api/lab/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const job = await sub.json();
  expect(sub.status).toBe(202);
  let workerPid: number | null = null;
  for (let i = 0; i < 200 && !workerPid; i++) {
    const j = (await getJSON(`/api/lab/jobs/${job.job_id}`)).body;
    if (j.state === "running" && j.worker_pid) workerPid = j.worker_pid;
    else await new Promise((r) => setTimeout(r, 150));
  }
  expect(workerPid, "çalışan süreç başlamalı").toBeTruthy();
  expect(alive(workerPid!)).toBe(true);
  log.job_before_crash = { job_id: job.job_id, worker_pid: workerPid, state: "running" };

  crash(server);
  const t0 = Date.now();
  while (alive(workerPid!) && Date.now() - t0 < 10_000) await new Promise((r) => setTimeout(r, 100));
  log.worker_alive_after_crash = alive(workerPid!);
  log.worker_exit_after_crash_ms = Date.now() - t0;
  expect(alive(workerPid!), "iş nesnesi çalışanı sonlandırmalı (yetim süreç yok)").toBe(false);

  // Sunucu B: gecikme kancası OLMADAN (yeniden deneme gerçek sürede tamamlansın)
  server = startServer();
  const st2 = await waitReady(server);
  log.server_b_ready_ms = st2.ready_ms;
  log.recovery = st2.job_recovery;
  expect(st2.job_recovery.interrupted).toContain(job.job_id);
  expect(st2.job_recovery.orphans_killed).toEqual([]); // zaten iş nesnesi tarafından sonlandırılmıştı

  await page.goto("/#/laboratuvar");
  await page.getByTestId("tab-history").click();
  await page.getByTestId("job-history").locator("button", { hasText: job.job_id }).click();
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", "interrupted");
  await expect(page.getByTestId("job-interrupted")).toContainText("kurtarılamaz");
  await page.waitForTimeout(2000);
  expect((await getJSON("/api/lab/resources")).body.running).toBe(0); // kendiliğinden yeniden çalıştırma yok
  await page.screenshot({ path: resolve(OUT, "screenshots/10-yeniden-baslatma-yarida-kalan-is.png") });

  const res2 = (await getJSON("/api/lab/resources")).body;
  log.resources_before_retry = res2;
  await page.getByTestId("job-retry").click();
  await expect(page.getByTestId("job-ids")).toContainText(`${job.job_id} işinin yeniden denemesi`, { timeout: 30_000 });
  const expected = res2.can_start ? "completed" : "resource_limited";
  await expect(page.getByTestId("job-state")).toHaveAttribute("data-state", expected, { timeout: 180_000 });
  const ids = await page.getByTestId("job-ids").textContent();
  const newId = /iş ([0-9a-f]{12})/.exec(ids ?? "")?.[1];
  const nj = (await getJSON(`/api/lab/jobs/${newId}`)).body;
  log.retry_job = { job_id: newId, state: nj.state, retry_of: nj.retry_of, experiment_id: nj.experiment_id,
    n_events: nj.n_events, n_clusters: nj.result?.summary?.n_clusters ?? null, monitor: nj.worker?.monitor ?? null };
  expect(nj.retry_of).toBe(job.job_id);
  expect(newId).not.toBe(job.job_id);
  await page.screenshot({ path: resolve(OUT, "screenshots/11-yeniden-deneme-sonucu.png") });

  // Temiz kapanış (Ctrl+C eşdeğeri değil; süreç sonlandırılır) → yeni açılışta tamamlanan sonuç korunur
  crash(server);
  server = startServer();
  const st3 = await waitReady(server);
  const again = (await getJSON(`/api/lab/jobs/${newId}`)).body;
  log.after_second_restart = { state: again.state, recovery: st3.job_recovery };
  expect(again.state).toBe(expected);
  if (expected === "completed") {
    const s = await getJSON(`/api/results/lab-${newId}/summary`);
    expect(s.status).toBe(200);
    expect(s.body.summary.n_clusters).toBe(nj.result.summary.n_clusters);
  }
});
