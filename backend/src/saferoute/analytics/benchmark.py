"""Faz 5 API gecikme/yük ölçümü (gerçek veri, süreç içi istemci; ağ gecikmesi hariç).

Her istek için ilk çağrı (soğuk: filtre maskesi hesaplanır) ve tekrarlar (maske önbellekte) ayrı raporlanır.
Ayrıca olay deposu yükleme süresi/bellek ve bir dinamik DBSCAN işinin uçtan uca süresi ölçülür.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

F = "boroughs=BROOKLYN&vehicles=BICYCLE&injury=injury"
REQUESTS = [
    ("genel_bakis", "/api/overview"),
    ("filtre_secenekleri", "/api/filters/options"),
    ("ozet_filtresiz", "/api/records/summary"),
    ("ozet_filtreli", f"/api/records/summary?{F}"),
    ("ozet_saat_gece", "/api/records/summary?hour_from=22&hour_to=4&fatal=fatal"),
    ("zaman_ay", f"/api/records/timeline?granularity=month&{F}"),
    ("yogunluk_1km_filtreli", f"/api/records/density?cell=1000&{F}"),
    ("yogunluk_250m_filtreli", f"/api/records/density?cell=250&{F}"),
    ("kumeler_filtreli", f"/api/records/clusters?{F}"),
    ("noktalar_filtreli_brooklyn", f"/api/records/points?bbox=-73.990,40.690,-73.978,40.700&{F}"),
    ("kume_ayrintisi_filtreli", f"/api/records/clusters/1344?{F}"),
    ("model_karsilastirma", "/api/models/comparison"),
    ("deney_kaydi", "/api/experiments"),
    ("kayitli_sonuc_kmeans", "/api/results/kmeans-24c07e9946/clusters"),
    ("veri_sozlugu", "/api/data/dictionary"),
]


def run_benchmark(repeats: int = 10, out: Path | None = None, job: bool = True) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from saferoute import config
    from saferoute.perf import current_memory_mb, peak_memory_mb
    from saferoute.viz.api import create_app

    import tempfile

    # Geçici, boş laboratuvar önbelleği: dinamik iş ölçümü her zaman gerçek bir fit içerir (önbellekten gelmez)
    lab_tmp = tempfile.mkdtemp(prefix="saferoute-bench-")
    t0 = time.perf_counter()
    app = create_app(analytics={"lab_root": Path(lab_tmp)})
    c = TestClient(app)
    while not c.get("/api/analytics/status").json()["ready"]:
        time.sleep(0.05)
    ready_s = time.perf_counter() - t0
    status = c.get("/api/analytics/status").json()
    rss_after_load = current_memory_mb()
    rows: dict[str, Any] = {}
    for name, url in REQUESTS:
        times, size, gz = [], 0, 0
        for i in range(repeats + 1):
            s = time.perf_counter()
            r = c.get(url, headers={"Accept-Encoding": "gzip"})
            times.append((time.perf_counter() - s) * 1000)
            size = len(r.content)
            gz = int(r.headers.get("content-length", size)) if r.headers.get("content-encoding") == "gzip" else size
        warm = times[1:]
        rows[name] = {"url": url, "status": r.status_code, "first_ms": round(times[0], 1),
                      "median_ms": round(statistics.median(warm), 1), "p95_ms": round(sorted(warm)[int(0.95 * (len(warm) - 1))], 1),
                      "json_bytes": size, "wire_bytes_gzip": gz}
    res: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repeats": repeats, "app_and_store_ready_s": round(ready_s, 2),
        "event_store_load_s": status["load_seconds"], "rss_after_store_mb": rss_after_load,
        "note": "Süreç içi TestClient; ağ gecikmesi hariç. first_ms = ilk çağrı (filtre maskesi hesaplanır), median/p95 = tekrarlar.",
        "requests": rows,
    }
    if job:
        body = {"algorithm": "dbscan", "feature_set": "spatial_haversine", "params": {"eps_m": 35, "min_samples": 15},
                "filters": {"boroughs": "MANHATTAN", "years": "2018"}}
        s = time.perf_counter()
        j = c.post("/api/lab/jobs", json=body).json()
        while j["state"] in ("pending", "running"):
            time.sleep(0.1)
            j = c.get(f"/api/lab/jobs/{j['job_id']}").json()
        wall = time.perf_counter() - s
        res["dynamic_job"] = {"request": body, "state": j["state"], "source": j["source"], "wall_s": round(wall, 2),
                              "worker": j.get("worker"), "n_events": j["n_events"], "n_fit_rows": j["n_fit_rows"],
                              "n_clusters": (j.get("result") or {}).get("summary", {}).get("n_clusters"),
                              "note": "source=cache ise sonuç daha önce hesaplanmıştı (önbellek); wall_s önbellekten okuma süresidir."}
    res["server_peak_memory_mb"] = peak_memory_mb()
    import shutil

    app.state.analytics.jobs.shutdown()
    shutil.rmtree(lab_tmp, ignore_errors=True)
    out = Path(out or config.REPORTS_DIR / "phase5" / "api_benchmark.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res
