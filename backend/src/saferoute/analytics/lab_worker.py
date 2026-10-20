"""Kümeleme Laboratuvarı çalışanı: AYRI bir süreçte (spawn) tek bir işi çalıştırır.

Girdi (ebeveyn süreç hazırlar, ``<iş>/input.npz``): fit satırlarının koordinatları ve ağırlıkları.
Çıktı: ``<iş>/output.npz`` (satır etiketleri) ve ``<iş>/worker.json`` (süre, bellek, metrikler).
Durum: ``<iş>/status.json`` — her GERÇEK aşamada yazılır (yüzde tahmini yoktur).

Süreç yalıtımı: bellek hatası veya iptal (``terminate``) API sürecini etkilemez; ölçülen bellek
tepe değeri yalnızca bu işe aittir.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

STAGES = {
    "loading": "Girdi yükleniyor",
    "estimating": "Kaynak gereksinimi ölçülüyor",
    "fitting": "Model eğitiliyor (fit)",
    "metrics": "Değerlendirme metrikleri hesaplanıyor",
    "writing": "Sonuç yazılıyor",
}


def _write_json(path: Path, obj: Any, attempts: int = 50) -> None:
    """Atomik yazma. Windows'ta okuyucu dosyayı açık tutarken ``os.replace`` reddedilebilir (WinError 5);
    kısa aralıklarla yeniden denenir."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, default=float), encoding="utf-8")
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.02)


def _stage(job: Path, stage: str, **extra: Any) -> None:
    """Aşama bildirimi en-iyi-çabadır: yazılamazsa iş sürer (durum sorgusu bir önceki aşamayı gösterir)."""
    try:
        _write_json(job / "status.json", {"stage": stage, "stage_label": STAGES.get(stage, stage),
                                          "pid": os.getpid(), "at": time.time(), **extra}, attempts=10)
    except OSError:
        pass


class ResourceRejected(RuntimeError):
    pass


def _metrics(X: np.ndarray, row_labels: np.ndarray, weights: np.ndarray, n: int, seed: int) -> dict[str, Any]:
    """Siluet ve Davies–Bouldin: gürültü hariç, olay düzeyinde basit rastgele örneklem (Öklid, metre)."""
    import sklearn
    from sklearn.metrics import davies_bouldin_score, silhouette_score

    # Faz 3 ile aynı: parçalı ikili uzaklık hesabının bellek tavanı (phase3.toml sklearn_working_memory_mb)
    sklearn.set_config(working_memory=256)

    ev_rows = np.repeat(np.arange(len(row_labels)), weights.astype(np.int64))
    lab = row_labels[ev_rows]
    keep = np.flatnonzero(lab >= 0)
    out: dict[str, Any] = {"metric": "Öklid (EPSG:32618 metre)", "sampling": "gürültü hariç basit rastgele olay örneklemi",
                           "seed": seed, "noise_excluded": int(len(lab) - len(keep))}
    if len(keep) < 3 or len(np.unique(lab[keep])) < 2:
        out.update({"silhouette": None, "davies_bouldin": None, "n_used": int(len(keep)),
                    "status": "tanımsız: en az 2 küme ve 3 kümelenmiş olay gerekir"})
        return out
    rng = np.random.default_rng(seed)
    take = keep if len(keep) <= n else np.sort(rng.choice(keep, size=n, replace=False))
    Xs, ls = X[ev_rows[take]], lab[take]
    if len(np.unique(ls)) < 2:
        out.update({"silhouette": None, "davies_bouldin": None, "n_used": int(len(take)),
                    "status": "tanımsız: örneklemde tek küme"})
        return out
    out.update({"silhouette": float(silhouette_score(Xs, ls)), "davies_bouldin": float(davies_bouldin_score(Xs, ls)),
                "n_used": int(len(take)), "n_clusters_in_sample": int(len(np.unique(ls))), "status": "ok"})
    return out


def st_dbscan(x: np.ndarray, y: np.ndarray, days: np.ndarray, eps_m: float, eps_days: int, min_samples: int,
              max_pairs: int) -> dict[str, Any]:
    """Uzay-zaman DBSCAN: komşuluk = (mesafe ≤ eps_m) VE (|Δgün| ≤ eps_days). Önce mekânsal komşu
    çifti sayılır (bütçe), sonra seyrek komşuluk grafiği üzerinde DBSCAN (metric='precomputed')."""
    from scipy.sparse import csr_matrix
    from sklearn.cluster import DBSCAN
    from sklearn.neighbors import KDTree

    X = np.column_stack([x, y])
    tree = KDTree(X)
    pairs = int(tree.query_radius(X, eps_m, count_only=True).sum())
    if pairs > max_pairs:
        raise ResourceRejected(f"Mekânsal komşu çifti {pairs:,} > bütçe {max_pairs:,}; filtreyi daraltın veya "
                               "eps_m'yi küçültün.".replace(",", "."))
    ind = tree.query_radius(X, eps_m)
    counts = np.fromiter((len(a) for a in ind), dtype=np.int64, count=len(ind))
    cols = np.concatenate(ind) if len(ind) else np.array([], dtype=np.int64)
    rows = np.repeat(np.arange(len(ind)), counts)
    keep = np.abs(days[rows].astype(np.int64) - days[cols].astype(np.int64)) <= eps_days
    rows, cols = rows[keep], cols[keep]
    # Tüm kenarlar (öz-komşuluk dahil) 1,0 uzaklığıyla saklanır; eps=1,5 → saklanan her kenar komşudur.
    g = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(X), len(X)))
    model = DBSCAN(eps=1.5, min_samples=int(min_samples), metric="precomputed").fit(g)
    return {"labels": model.labels_.astype(np.int32), "n_spatial_pairs": pairs, "n_st_pairs": int(len(rows))}


def run_job(job_dir: str) -> None:
    """Çocuk süreç giriş noktası. İstisnaları dışarı sızdırmaz; sonucu dosyalara yazar."""
    from saferoute.perf import available_memory_mb, peak_memory_mb

    job = Path(job_dir)
    res: dict[str, Any] = {"status": "failed"}
    try:
        _stage(job, "loading")
        req = json.loads((job / "request.json").read_text(encoding="utf-8"))
        budget = req["budget"]
        z = np.load(job / "input.npz")
        algo, fs, p = req["algorithm"], req["feature_set"], req["params"]
        w = z["weight"]
        free = available_memory_mb()
        if free is not None and free < budget["min_free_memory_mb"]:
            raise ResourceRejected(f"Boş fiziksel bellek {free:.0f} MB < gereken {budget['min_free_memory_mb']} MB.")
        _stage(job, "estimating")
        extra: dict[str, Any] = {}
        if algo == "dbscan" and fs == "spatial_haversine":
            from saferoute.clustering import algorithms

            X = np.column_stack([z["lat_rad"], z["lon_rad"]])
            pairs = algorithms.count_neighbor_pairs(X, p["eps_m"])
            extra["n_neighbor_pairs"] = pairs
            if pairs > budget["max_neighbor_pairs"]:
                raise ResourceRejected(f"Tahmini komşu çifti {pairs:,} > etkileşimli bütçe {budget['max_neighbor_pairs']:,} "
                                       f"(~{pairs * 8 / 2**30:.1f} GiB indeks). eps_m'yi küçültün veya filtreyi daraltın."
                                       .replace(",", "."))
            _stage(job, "fitting", **extra)
            t0 = time.perf_counter()
            r = algorithms.dbscan_haversine(X, p["eps_m"], p["min_samples"], w.astype(float), None, n_jobs=1)
            runtime = time.perf_counter() - t0
            labels = r["labels"]
        elif algo == "dbscan" and fs == "spatiotemporal":
            if len(w) > budget["max_st_events"]:
                raise ResourceRejected(f"Uzay-zaman DBSCAN kayıt düzeyidir: {len(w):,} olay > bütçe "
                                       f"{budget['max_st_events']:,}. Filtreyi daraltın veya örneklem seçin.".replace(",", "."))
            _stage(job, "fitting")
            t0 = time.perf_counter()
            r = st_dbscan(z["x"], z["y"], z["days"], p["eps_m"], p["eps_days"], p["min_samples"], budget["max_st_pairs"])
            runtime = time.perf_counter() - t0
            labels = r["labels"]
            extra.update({"n_spatial_pairs": r["n_spatial_pairs"], "n_st_pairs": r["n_st_pairs"]})
        elif algo == "kmeans":
            from saferoute.clustering import algorithms

            if p["k"] > len(w):
                raise ValueError(f"k ({p['k']}) fit noktası sayısını ({len(w)}) aşamaz")
            _stage(job, "fitting")
            t0 = time.perf_counter()
            r = algorithms.kmeans_projected(np.column_stack([z["x"], z["y"]]), p["k"], w.astype(float), p["n_init"],
                                            p["max_iter"], p["random_state"])
            runtime = time.perf_counter() - t0
            labels = r["labels"]
            extra.update({"inertia": r["inertia"], "n_iter": r["n_iter"]})
        elif algo == "hdbscan":
            from sklearn.cluster import HDBSCAN

            if len(w) > budget["max_hdbscan_events"]:
                raise ResourceRejected(f"HDBSCAN kayıt düzeyidir ve ~karesel ölçeklenir: {len(w):,} olay > bütçe "
                                       f"{budget['max_hdbscan_events']:,}. Örneklem boyutu seçin.".replace(",", "."))
            _stage(job, "fitting")
            if fs == "spatial_haversine_records":
                X, metric, alg = np.column_stack([z["lat_rad"], z["lon_rad"]]), "haversine", "ball_tree"
            else:
                X, metric, alg = np.column_stack([z["x"], z["y"]]), "euclidean", "auto"
            t0 = time.perf_counter()
            model = HDBSCAN(min_cluster_size=p["min_cluster_size"], min_samples=p["min_samples"], metric=metric,
                            algorithm=alg, cluster_selection_method=p.get("cluster_selection_method", "eom"),
                            copy=True).fit(X)
            runtime = time.perf_counter() - t0
            labels = model.labels_.astype(np.int32)
        else:
            raise ValueError(f"Desteklenmeyen kombinasyon: {algo} + {fs}")

        _stage(job, "metrics", **extra)
        if fs == "spatiotemporal":
            metrics = {"silhouette": None, "davies_bouldin": None,
                       "status": "uygulanamaz: uzay-zaman komşuluğu tek bir mesafe metriği değildir"}
        else:
            metrics = _metrics(np.column_stack([z["x"], z["y"]]), labels, w, budget["metric_sample"], 42)
        _stage(job, "writing", **extra)
        np.savez_compressed(job / "output.npz", labels=labels)
        res = {"status": "completed", "runtime_s": round(runtime, 3), "peak_memory_mb": peak_memory_mb(),
               "n_fit_rows": int(len(w)), "metrics": metrics, **extra}
    except ResourceRejected as exc:
        res = {"status": "rejected_resource", "error": str(exc), "peak_memory_mb": peak_memory_mb()}
    except MemoryError as exc:
        res = {"status": "rejected_resource", "error": f"Bellek yetersiz (MemoryError): {exc}",
               "peak_memory_mb": peak_memory_mb()}
    except Exception as exc:
        res = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-1500:]}
    _write_json(job / "worker.json", res)
