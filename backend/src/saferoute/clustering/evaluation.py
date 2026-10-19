"""Değerlendirme: küme istatistikleri, iç geçerlilik metrikleri, eşdeğerlik ve kararlılık.

Kurallar:
  * Gürültü (-1) hiçbir zaman sıradan bir küme gibi ele alınmaz. Siluet ve Davies–Bouldin
    gürültü dışlanarak hesaplanır; dışlanan oran ayrıca raporlanır. DBCV gürültüyü
    tanımı gereği cezalandırır.
  * Siluet O(n²) olduğu için kümelere göre ORANTILI TABAKALI, sabit tohumlu örneklemle
    hesaplanır; kullanılan metrik ve örneklem boyutu sonuca yazılır.
  * Tanımsız durumlar (2'den az küme, yetersiz örneklem, metrik uygun değil) N/A olarak,
    nedeniyle birlikte döner — asla sayı uydurulmaz.
  * Davies–Bouldin Öklid merkezlere dayanır; Haversine uzayında tanımlı değildir.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from sklearn.neighbors import BallTree


def na(reason: str) -> dict[str, Any]:
    return {"value": None, "status": "N/A", "reason": reason}


def cluster_stats(labels: np.ndarray, weights: np.ndarray | None = None) -> dict[str, Any]:
    """Küme sayısı, gürültü oranı ve küme boyutu dağılımı (ağırlık = olay sayısı)."""
    labels = np.asarray(labels)
    w = np.ones(len(labels)) if weights is None else np.asarray(weights, dtype=np.float64)
    total = float(w.sum())
    noise = labels < 0
    clustered = labels[~noise]
    n_clusters = int(len(np.unique(clustered)))
    sizes = np.bincount(clustered, weights=w[~noise]) if n_clusters else np.array([])
    sizes = sizes[sizes > 0]
    q = (lambda p: float(np.percentile(sizes, p))) if len(sizes) else (lambda p: None)
    return {
        "n_points": int(len(labels)), "n_events": int(round(total)), "n_clusters": n_clusters,
        "noise_events": int(round(w[noise].sum())), "noise_ratio": float(w[noise].sum() / total) if total else None,
        "clustered_events": int(round(w[~noise].sum())),
        "cluster_size": {"min": q(0), "p25": q(25), "median": q(50), "p75": q(75), "p90": q(90), "p99": q(99),
                         "max": q(100), "mean": float(sizes.mean()) if len(sizes) else None},
        "largest_cluster_share": float(sizes.max() / total) if len(sizes) and total else None,
        "clusters_ge": {str(t): int((sizes >= t).sum()) for t in (50, 100, 500, 1000, 5000)},
    }


def stratified_sample(labels: np.ndarray, n: int, seed: int, include_noise: bool = False,
                      min_per_cluster: int = 2) -> np.ndarray:
    """Kümelere göre orantılı tabakalı örneklem (indeksler). Her temsil edilen kümeden >= ``min_per_cluster``.

    Orantılı payı ``min_per_cluster``'dan küçük kalan çok küçük kümeler örneklemde
    temsil edilmeyebilir; bu durum çağırana ``n_clusters_used`` ile bildirilir.
    """
    labels = np.asarray(labels)
    rng = np.random.default_rng(seed)
    pool = np.arange(len(labels)) if include_noise else np.flatnonzero(labels >= 0)
    if len(pool) <= n:
        return np.sort(pool)
    order = pool[np.argsort(labels[pool], kind="stable")]
    _, starts = np.unique(labels[order], return_index=True)
    groups = np.split(order, starts[1:])  # binlerce kümede O(n log n)
    total = len(pool)
    chosen = []
    for idx in groups:
        take = int(round(n * len(idx) / total))
        if take < min_per_cluster:
            if len(idx) >= min_per_cluster and rng.random() < (n * len(idx) / total) / min_per_cluster:
                take = min_per_cluster
            else:
                continue
        chosen.append(rng.choice(idx, size=min(take, len(idx)), replace=False))
    return np.sort(np.concatenate(chosen)) if chosen else np.array([], dtype=np.int64)


def silhouette(X: np.ndarray, labels: np.ndarray, metric: str, sample_n: int, seed: int) -> dict[str, Any]:
    labels = np.asarray(labels)
    if (labels >= 0).sum() == 0:
        return na("küme yok (tüm noktalar gürültü)")
    if len(np.unique(labels[labels >= 0])) < 2:
        return na("2'den az küme: siluet tanımsız")
    idx = stratified_sample(labels, sample_n, seed)
    lab = labels[idx]
    k = len(np.unique(lab))
    if k < 2 or len(idx) <= k:
        return na(f"örneklemde yetersiz küme/nokta (k={k}, n={len(idx)})")
    value = float(silhouette_score(X[idx], lab, metric=metric))
    return {"value": value, "status": "ok", "metric": metric, "n_used": int(len(idx)), "n_clusters_used": int(k),
            "noise_excluded_ratio": float((labels < 0).mean()), "sampling": "kümelere göre orantılı tabakalı",
            "seed": seed}


def davies_bouldin(X_euclid: np.ndarray, labels: np.ndarray, sample_n: int, seed: int) -> dict[str, Any]:
    labels = np.asarray(labels)
    if len(np.unique(labels[labels >= 0])) < 2:
        return na("2'den az küme: Davies–Bouldin tanımsız")
    idx = stratified_sample(labels, sample_n, seed)
    lab = labels[idx]
    if len(np.unique(lab)) < 2:
        return na("örneklemde 2'den az küme")
    return {"value": float(davies_bouldin_score(X_euclid[idx], lab)), "status": "ok", "metric": "euclidean",
            "n_used": int(len(idx)), "noise_excluded_ratio": float((labels < 0).mean()), "seed": seed}


def dbcv(X_euclid: np.ndarray, labels: np.ndarray, sample_n: int, seed: int) -> dict[str, Any]:
    """DBCV (Moulavi vd., 2014) — ``hdbscan.validity.validity_index``; gürültü dahil tabakalı örneklem."""
    labels = np.asarray(labels)
    if len(np.unique(labels[labels >= 0])) < 2:
        return na("2'den az küme: DBCV tanımsız")
    try:
        from hdbscan.validity import validity_index
    except ImportError:
        return na("hdbscan paketi kurulu değil")
    idx = stratified_sample(labels, sample_n, seed, include_noise=True, min_per_cluster=3)
    lab = labels[idx]
    clusters, counts = np.unique(lab[lab >= 0], return_counts=True)
    if len(clusters) < 2:
        return na("örneklemde 2'den az küme")
    # validity_index kümelerin ardışık numaralı olmasını bekler; az üyeli kümeler sayısal olarak kararsızdır.
    keep = np.isin(lab, clusters[counts >= 3]) | (lab < 0)
    lab = lab[keep]
    uniq = np.unique(lab[lab >= 0])
    remap = {c: i for i, c in enumerate(uniq)}
    lab = np.array([remap.get(c, -1) for c in lab], dtype=np.int64)
    if len(uniq) < 2:
        return na("örneklemde 3+ üyeli 2'den az küme")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            value = float(validity_index(X_euclid[idx][keep].astype(np.float64), lab))
        except Exception as exc:  # sayısal hata: N/A olarak raporlanır, uydurulmaz
            return na(f"DBCV hesaplanamadı: {type(exc).__name__}: {exc}")
    if not np.isfinite(value):
        return na("DBCV sonlu değil (yinelenen noktalar / sayısal kararsızlık)")
    return {"value": value, "status": "ok", "metric": "euclidean", "n_used": int(keep.sum()),
            "n_clusters_used": int(len(uniq)), "seed": seed,
            "warnings": sorted({str(w.message)[:120] for w in caught})[:3]}


def ari(a: np.ndarray, b: np.ndarray) -> float:
    """Adjusted Rand Index (etiket numaralarından bağımsız). Gürültü tek bir sınıf olarak ele alınır."""
    return float(adjusted_rand_score(a, b))


def compare_partitions(rec_labels: np.ndarray, rec_core: np.ndarray, w_labels: np.ndarray, w_core: np.ndarray,
                       X_rad: np.ndarray, eps_rad: float) -> dict[str, Any]:
    """Kayıt düzeyi ve ağırlıklı (kayda geri eşlenmiş) DBSCAN sonuçlarını etiket-bağımsız karşılaştırır.

    * Çekirdek ve gürültü kümeleri birebir aynı olmalı (teori).
    * Çekirdek noktaların bölümlemesi aynı olmalı (ARI = 1 ve küme eşlemesi birebir).
    * Sınır noktaları, birden fazla kümenin çekirdeğine komşuysa işleme sırasına göre farklı kümeye
      atanabilir (DBSCAN'in bilinen sıra bağımlılığı). Farklı atanan her sınır noktası için komşu
      çekirdeklerin kaç farklı kümeye ait olduğu ölçülür.
    """
    core_equal = bool(np.array_equal(rec_core, w_core))
    noise_equal = bool(np.array_equal(rec_labels < 0, w_labels < 0))
    both_core = rec_core & w_core
    ari_core = ari(rec_labels[both_core], w_labels[both_core]) if both_core.sum() > 1 else None
    # Çekirdek eşlemesi: her kayıt kümesi tek bir ağırlıklı kümeye karşılık gelmeli (ve tersi)
    pairs = np.unique(np.column_stack([rec_labels[both_core], w_labels[both_core]]), axis=0)
    bijective = (len(np.unique(pairs[:, 0])) == len(pairs) == len(np.unique(pairs[:, 1]))) if len(pairs) else True
    mapping = dict(zip(pairs[:, 0].tolist(), pairs[:, 1].tolist())) if bijective else {}
    border = (rec_labels >= 0) & ~rec_core
    mapped = np.array([mapping.get(int(c), -999) for c in rec_labels[border]]) if bijective else None
    differing = np.zeros(len(rec_labels), dtype=bool)
    if mapped is not None:
        differing[np.flatnonzero(border)] = mapped != w_labels[border]
    ambiguous_ok = None
    if differing.any():
        tree = BallTree(X_rad[rec_core], metric="haversine")
        core_labels = rec_labels[rec_core]
        neigh = tree.query_radius(X_rad[differing], eps_rad)
        n_clusters_adjacent = np.array([len(np.unique(core_labels[n])) for n in neigh])
        ambiguous_ok = bool((n_clusters_adjacent >= 2).all())
    return {
        "n_events": int(len(rec_labels)),
        "core_identical": core_equal, "core_mismatches": int((rec_core != w_core).sum()),
        "noise_identical": noise_equal, "noise_mismatches": int(((rec_labels < 0) != (w_labels < 0)).sum()),
        "n_clusters_records": int(len(np.unique(rec_labels[rec_labels >= 0]))),
        "n_clusters_weighted": int(len(np.unique(w_labels[w_labels >= 0]))),
        "core_partition_ari": ari_core, "core_mapping_bijective": bool(bijective),
        "ari_all_events": ari(rec_labels, w_labels),
        "border_events": int(border.sum()),
        "border_events_different_cluster": int(differing.sum()),
        "differing_borders_all_adjacent_to_multiple_clusters": ambiguous_ok,
    }


# ----------------------------------------------------------------------------- zamansal / mekânsal örtüşme
def footprint(x_m: np.ndarray, y_m: np.ndarray, labels: np.ndarray, cell_m: float) -> set[tuple[int, int]]:
    """Kümelenmiş (gürültü olmayan) olayların kapladığı ızgara hücreleri."""
    keep = labels >= 0
    cells = np.column_stack([np.floor(x_m[keep] / cell_m), np.floor(y_m[keep] / cell_m)]).astype(np.int64)
    return set(map(tuple, np.unique(cells, axis=0))) if len(cells) else set()


def jaccard(a: set, b: set) -> float | None:
    union = len(a | b)
    return len(a & b) / union if union else None


def structure_diagnostics(labels: np.ndarray, x_m: np.ndarray, y_m: np.ndarray, location_index: np.ndarray,
                          year: np.ndarray, years: list[int], chain_threshold_m: float = 200.0) -> dict[str, Any]:
    """Küme yapısının coğrafi anlamlılık / zincirlenme / zamansal süreklilik tanıları (olay düzeyi).

    * Uzanım: küme olaylarının UTM sınırlayıcı kutusunun köşegeni (m). Uzun köşegen, yoğunluk
      zincirlenmesinin (ardışık komşular üzerinden cadde boyunca birleşme) göstergesidir.
    * Tek konumlu küme: tüm olayları aynı koordinatta (salt tekrar eden geokod) olan küme.
    * Etkin yıl: kümenin ``years`` içinde en az bir olay içerdiği yıl sayısı.
    """
    keep = labels >= 0
    if not keep.any():
        return {"n_clusters": 0, "reason": "küme yok"}
    _, inv = np.unique(labels[keep], return_inverse=True)
    size = np.bincount(inv)
    o = np.argsort(inv, kind="stable")
    starts = np.r_[0, np.cumsum(size)[:-1]]
    xs, ys = x_m[keep][o], y_m[keep][o]
    diag = np.hypot(np.maximum.reduceat(xs, starts) - np.minimum.reduceat(xs, starts),
                    np.maximum.reduceat(ys, starts) - np.minimum.reduceat(ys, starts))
    pairs = np.unique(np.column_stack([inv, location_index[keep]]), axis=0)
    n_loc = np.bincount(pairs[:, 0], minlength=len(size))
    in_years = np.isin(year[keep], years)
    yp = np.unique(np.column_stack([inv[in_years], year[keep][in_years]]), axis=0)
    active = np.bincount(yp[:, 0], minlength=len(size))
    q = lambda a, p: float(np.percentile(a, p))  # noqa: E731
    single = n_loc == 1
    return {
        "n_clusters": int(len(size)), "clustered_events": int(size.sum()),
        "events_per_cluster": {"median": q(size, 50), "p90": q(size, 90), "max": int(size.max())},
        "unique_locations_per_cluster": {"median": q(n_loc, 50), "p90": q(n_loc, 90), "max": int(n_loc.max())},
        "single_location_cluster_share": float(single.mean()),
        "events_in_single_location_clusters_share": float(size[single].sum() / size.sum()),
        "extent_diag_m": {"median": q(diag, 50), "p95": q(diag, 95), "max": float(diag.max())},
        "chain_threshold_m": chain_threshold_m,
        "clusters_over_threshold_share": float((diag > chain_threshold_m).mean()),
        "events_in_clusters_over_threshold_share": float(size[diag > chain_threshold_m].sum() / size.sum()),
        "active_years": {"n_years": len(years), "median": q(active, 50),
                         "share_all_years": float((active == len(years)).mean()),
                         "share_10plus_years": float((active >= 10).mean())},
    }


def match_centroids(c1: np.ndarray, c2: np.ndarray) -> dict[str, Any]:
    """Macar algoritmasıyla merkezleri birebir eşler; eşleşen merkezler arası mesafe (m)."""
    d = np.hypot(c1[:, None, 0] - c2[None, :, 0], c1[:, None, 1] - c2[None, :, 1])
    r, c = linear_sum_assignment(d)
    dist = d[r, c]
    return {"matched": int(len(r)), "median_m": float(np.median(dist)), "p90_m": float(np.percentile(dist, 90)),
            "max_m": float(dist.max())}
