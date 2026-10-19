"""Faz 4 API gecikme ve yük ölçümü (gerçek katmanlar, süreç içi istemci; ağ gecikmesi hariç)."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

# Tipik kullanım: şehir açılışı, mahalle ızgarası, Midtown ve Brooklyn'de yakın zoom bbox sorguları, küme ayrıntısı
REQUESTS = [
    ("meta", "/api/meta"), ("kume_merkezleri", "/api/clusters"), ("kume_geometrileri", "/api/clusters/geometries"),
    ("ilce_sinirlari", "/api/boroughs"), ("yogunluk_1km", "/api/density?cell=1000"), ("yogunluk_250m", "/api/density?cell=250"),
    ("noktalar_midtown_z16", "/api/points?bbox=-73.990,40.752,-73.978,40.762&kind=all"),
    ("noktalar_midtown_genis", "/api/points?bbox=-74.000,40.740,-73.960,40.780&kind=all"),
    ("noktalar_brooklyn_gurultu", "/api/points?bbox=-73.990,40.690,-73.978,40.700&kind=noise"),
    ("kume_ayrintisi", "/api/clusters/1344"),
]


def run_benchmark(layers_dir: Path | None = None, repeats: int = 15, out: Path | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from saferoute import config
    from saferoute.perf import peak_memory_mb
    from saferoute.viz.api import create_app

    t0 = time.perf_counter()
    app = create_app(layers_dir)
    startup = time.perf_counter() - t0
    c = TestClient(app)
    rows = {}
    for name, url in REQUESTS:
        times, size, gz = [], 0, 0
        for _ in range(repeats):
            s = time.perf_counter()
            r = c.get(url, headers={"Accept-Encoding": "gzip"})
            times.append((time.perf_counter() - s) * 1000)
            size = len(r.content)
            gz = int(r.headers.get("content-length", size)) if r.headers.get("content-encoding") == "gzip" else size
        j = r.json()
        rows[name] = {"url": url, "status": r.status_code, "median_ms": round(statistics.median(times), 1),
                      "p95_ms": round(sorted(times)[int(0.95 * (len(times) - 1))], 1), "json_bytes": size, "wire_bytes_gzip": gz,
                      **{k: j[k] for k in ("total_locations", "total_events", "returned_locations", "truncated", "returned")
                         if isinstance(j, dict) and k in j}}
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repeats": repeats, "startup_s": round(startup, 2),
           "server_peak_memory_mb": peak_memory_mb(), "note": "Süreç içi TestClient; ağ gecikmesi hariç.", "requests": rows}
    out = Path(out or config.REPORTS_DIR / "phase4" / "api_benchmark.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res
