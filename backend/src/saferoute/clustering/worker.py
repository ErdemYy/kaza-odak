"""Tek bir kümeleme deneyini (tercihen ayrı bir süreçte) çalıştırır.

Ayrı süreç (spawn) kullanmanın iki amacı vardır:
  1. Ölçülen bellek tepe değeri yalnızca bu deneye aittir (veri yükleme + fit).
  2. Bellek hatası veya çökme ana süreci düşürmez; deney ``failed`` olarak kaydedilir.

Etiketler olay (event) düzeyinde ``.npz`` dosyasına yazılır: ``event_index`` (EventData içindeki
olay indeksleri), ``labels``, ``core`` (DBSCAN), ``probabilities`` (HDBSCAN).
"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import active_children, get_context
from pathlib import Path
from typing import Any

import numpy as np

from saferoute.clustering import algorithms
from saferoute.clustering.data import load_events, subset_mask, weighted_view
from saferoute.perf import current_memory_mb, peak_memory_mb


def execute(task: dict[str, Any]) -> dict[str, Any]:
    """Görevi bu süreçte çalıştırır; hiçbir istisnayı dışarı sızdırmaz (durum + hata döner)."""
    out: dict[str, Any] = {"status": "failed", "error": None, "extra": {}}
    try:
        ev = load_events(Path(task["processed_dir"]))
        mask = subset_mask(ev, task.get("subset"))
        event_index = np.flatnonzero(mask)
        kind, p = task["kind"], task["params"]
        out["n_events"] = int(mask.sum())
        save: dict[str, np.ndarray] = {"event_index": event_index}

        if kind in ("dbscan_weighted", "kmeans_weighted"):
            view = weighted_view(ev, mask, task.get("weight_cap"))
            loc = view["loc"]
            out["n_unique_locations"] = int(len(loc))
            out["extra"]["weight_sum"] = float(view["weight"].sum())
            if kind == "dbscan_weighted":
                X = np.column_stack([ev.loc_lat_rad[loc], ev.loc_lon_rad[loc]])
                before = current_memory_mb()
                t0 = time.perf_counter()
                res = algorithms.dbscan_haversine(X, p["eps_m"], p["min_samples"], view["weight"],
                                                  task.get("max_neighbor_pairs"))
                runtime = time.perf_counter() - t0
                save["labels"] = res["labels"][view["event_to_row"]]
                save["core"] = res["core_mask"][view["event_to_row"]]
                save["loc"] = loc
                save["loc_labels"] = res["labels"]
                save["loc_core"] = res["core_mask"]
                out["extra"]["n_neighbor_pairs"] = res["n_neighbor_pairs"]
            else:
                X = np.column_stack([ev.loc_x_m[loc], ev.loc_y_m[loc]])
                before = current_memory_mb()
                t0 = time.perf_counter()
                res = algorithms.kmeans_projected(X, p["k"], view["weight"], task["n_init"], task["max_iter"],
                                                  task["seed"])
                runtime = time.perf_counter() - t0
                save["labels"] = res["labels"][view["event_to_row"]]
                save["centers"] = res["centers"]
                out["extra"].update({"inertia": res["inertia"], "n_iter": res["n_iter"]})
        elif kind == "dbscan_records":
            X = np.column_stack([ev.lat_rad[mask], ev.lon_rad[mask]])
            out["n_unique_locations"] = int(len(np.unique(ev.location_index[mask])))
            before = current_memory_mb()
            t0 = time.perf_counter()
            res = algorithms.dbscan_haversine(X, p["eps_m"], p["min_samples"], None, task.get("max_neighbor_pairs"))
            runtime = time.perf_counter() - t0
            save["labels"], save["core"] = res["labels"], res["core_mask"]
            out["extra"]["n_neighbor_pairs"] = res["n_neighbor_pairs"]
        elif kind == "hdbscan_events":
            X = np.column_stack([ev.x_m[mask], ev.y_m[mask]])
            out["n_unique_locations"] = int(len(np.unique(ev.location_index[mask])))
            before = current_memory_mb()
            t0 = time.perf_counter()
            res = algorithms.hdbscan_projected(X, p["min_cluster_size"], p.get("min_samples"),
                                               task.get("method", "eom"))
            runtime = time.perf_counter() - t0
            save["labels"], save["probabilities"] = res["labels"], res["probabilities"]
        else:
            raise ValueError(f"Bilinmeyen görev türü: {kind}")

        Path(task["labels_out"]).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(task["labels_out"], **save)
        out.update({"status": "success", "runtime_s": round(runtime, 3), "memory_before_fit_mb": before,
                    "peak_memory_mb": peak_memory_mb(), "labels_path": str(task["labels_out"])})
    except algorithms.ResourceLimitExceeded as exc:
        out.update({"status": "skipped_resource_limit", "error": str(exc), "peak_memory_mb": peak_memory_mb()})
    except MemoryError as exc:
        out.update({"status": "failed", "error": f"MemoryError: {exc}", "peak_memory_mb": peak_memory_mb()})
    except Exception as exc:
        out.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()[-2000:]})
    return out


def run_isolated(task: dict[str, Any], isolate: bool = True, timeout_s: float | None = None) -> dict[str, Any]:
    """Görevi yeni bir süreçte (spawn) çalıştırır; süreç çökerse ``failed`` döner."""
    if not isolate:
        return execute(task)
    try:
        with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
            res = pool.submit(execute, task).result(timeout=timeout_s)
    except Exception as exc:  # BrokenProcessPool, zaman aşımı vb.
        res = {"status": "failed", "error": f"Süreç hatası: {type(exc).__name__}: {exc}", "extra": {}}
    # Havuz kapanışında (shutdown(wait=True)) çocuk süreç sonlanmış olmalı.
    res["child_closed"] = len(active_children()) == 0
    return res
