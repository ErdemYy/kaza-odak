"""Kümeleme algoritmalarının sarmalayıcıları (scikit-learn 1.9.1).

DBSCAN (ana model):
  * Girdi [enlem, boylam] RADYAN, ``metric="haversine"``, ``algorithm="ball_tree"``.
  * ``eps`` kullanıcıya metre olarak sunulur; modele ``eps_m / R`` (R = 6 371 008,8 m) verilir.
  * ``sample_weight``: bir noktanın çekirdek olup olmadığı, ``eps`` komşuluğundaki AĞIRLIK
    toplamıyla (nokta kendisi dahil) belirlenir. Benzersiz konum + ağırlık (= olay sayısı)
    temsilinde çekirdek koşulu, kayıt düzeyindeki sayımla matematiksel olarak aynıdır.
  * Bellek: scikit-learn tüm komşuluk listelerini bellekte tutar. Bu yüzden koşudan önce
    BallTree ``count_only`` ile komşu çifti sayısı ölçülür; sınırı aşan koşu reddedilir.
  * Etiket ``-1`` = gürültü. Küme numaraları anlamsal sınıf DEĞİLDİR; yalnızca bir koşu
    içindeki kümeleri ayırır ve koşular arasında eşleştirilemez.

K-Means (karşılaştırma): [x_m, y_m] (EPSG:32618), Öklid, ``sample_weight`` = olay sayısı.
HDBSCAN (karşılaştırma): [x_m, y_m], Öklid; ``sample_weight`` desteklenmez.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN, HDBSCAN, KMeans
from sklearn.neighbors import BallTree

from saferoute.preprocess.coordinates import meters_to_radians


class ResourceLimitExceeded(RuntimeError):
    """Tahmini kaynak kullanımı yapılandırmadaki sınırı aşıyorsa fırlatılır."""


class InvalidParameter(ValueError):
    """Kümeleme parametresi geçersizse fırlatılır."""


def validate_dbscan(eps_m: Any, min_samples: Any) -> None:
    if isinstance(eps_m, bool) or not isinstance(eps_m, (int, float)) or not np.isfinite(eps_m) or eps_m <= 0:
        raise InvalidParameter(f"eps_m pozitif sonlu bir sayı olmalı: {eps_m!r}")
    if isinstance(min_samples, bool) or not isinstance(min_samples, (int, np.integer)) or min_samples < 1:
        raise InvalidParameter(f"min_samples >= 1 tamsayı olmalı: {min_samples!r}")


def validate_kmeans(k: Any, n_points: int) -> None:
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < 2:
        raise InvalidParameter(f"k >= 2 tamsayı olmalı: {k!r}")
    if k > n_points:
        raise InvalidParameter(f"k ({k}) nokta sayısını ({n_points}) aşamaz")


def validate_hdbscan(min_cluster_size: Any, min_samples: Any) -> None:
    if isinstance(min_cluster_size, bool) or not isinstance(min_cluster_size, (int, np.integer)) or min_cluster_size < 2:
        raise InvalidParameter(f"min_cluster_size >= 2 tamsayı olmalı: {min_cluster_size!r}")
    if min_samples is not None and (not isinstance(min_samples, (int, np.integer)) or min_samples < 1):
        raise InvalidParameter(f"min_samples >= 1 tamsayı olmalı: {min_samples!r}")


def _check_radians(X: np.ndarray) -> None:
    if X.ndim != 2 or X.shape[1] != 2:
        raise InvalidParameter("X [enlem, boylam] radyan biçiminde (n, 2) olmalı")
    if np.nanmax(np.abs(X[:, 0])) > np.pi / 2 or np.nanmax(np.abs(X[:, 1])) > np.pi:
        raise InvalidParameter("X radyan değil gibi görünüyor (|enlem| > π/2 veya |boylam| > π)")
    if not np.isfinite(X).all():
        raise InvalidParameter("X sonlu olmayan değer içeriyor")


def count_neighbor_pairs(X_rad: np.ndarray, eps_m: float) -> int:
    """eps komşuluğundaki (nokta kendisi dahil) toplam çift sayısı; yalnızca sayım, düşük bellek."""
    tree = BallTree(X_rad, metric="haversine")
    return int(tree.query_radius(X_rad, meters_to_radians(eps_m), count_only=True).sum())


def dbscan_haversine(X_rad: np.ndarray, eps_m: float, min_samples: int, sample_weight: np.ndarray | None = None,
                     max_neighbor_pairs: int | None = None, n_jobs: int = -1) -> dict[str, Any]:
    """Haversine DBSCAN. Dönüş: labels, core_mask, n_neighbor_pairs."""
    validate_dbscan(eps_m, min_samples)
    _check_radians(X_rad)
    if sample_weight is not None and (len(sample_weight) != len(X_rad) or (np.asarray(sample_weight) < 0).any()):
        raise InvalidParameter("sample_weight uzunluğu X ile aynı ve negatif olmayan olmalı")
    pairs = count_neighbor_pairs(X_rad, eps_m)
    if max_neighbor_pairs is not None and pairs > max_neighbor_pairs:
        raise ResourceLimitExceeded(
            f"Tahmini komşu çifti {pairs:,} > sınır {max_neighbor_pairs:,} "
            f"(~{pairs * 8 / 2**30:.1f} GiB yalnızca indeks); koşu çalıştırılmadı.")
    model = DBSCAN(eps=meters_to_radians(eps_m), min_samples=int(min_samples), metric="haversine",
                   algorithm="ball_tree", n_jobs=n_jobs).fit(X_rad, sample_weight=sample_weight)
    core = np.zeros(len(X_rad), dtype=bool)
    core[model.core_sample_indices_] = True
    return {"labels": model.labels_.astype(np.int32), "core_mask": core, "n_neighbor_pairs": pairs}


def kmeans_projected(X_m: np.ndarray, k: int, sample_weight: np.ndarray | None, n_init: int, max_iter: int,
                     seed: int) -> dict[str, Any]:
    validate_kmeans(k, len(X_m))
    model = KMeans(n_clusters=int(k), n_init=int(n_init), max_iter=int(max_iter), random_state=int(seed)).fit(
        X_m, sample_weight=sample_weight)
    return {"labels": model.labels_.astype(np.int32), "centers": model.cluster_centers_,
            "inertia": float(model.inertia_), "n_iter": int(model.n_iter_)}


def hdbscan_projected(X_m: np.ndarray, min_cluster_size: int, min_samples: int | None,
                      method: str = "eom") -> dict[str, Any]:
    validate_hdbscan(min_cluster_size, min_samples)
    model = HDBSCAN(min_cluster_size=int(min_cluster_size), min_samples=min_samples,
                    cluster_selection_method=method, copy=True).fit(X_m)
    return {"labels": model.labels_.astype(np.int32), "probabilities": model.probabilities_.astype(np.float32)}
