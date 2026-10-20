"""Kümeleme Laboratuvarı istek şeması: algoritma × öznitelik seti uyumluluğu, parametre sınırları,
kaynak bütçesi. Desteklenmeyen kombinasyonlar sessizce kabul edilmez; gerekçeli hata döner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from saferoute.analytics.filters import FilterSpec, parse_filters

LAB_CODE_VERSION = "phase5-lab:5.0.0"


class LabRequestError(ValueError):
    """Geçersiz veya desteklenmeyen laboratuvar isteği (API'de 422)."""


# Öznitelik setleri: Faz 2 öznitelik matrisleriyle aynı tanımlar (preprocess/features.py FEATURE_SETS).
FEATURE_SETS: dict[str, dict[str, Any]] = {
    "spatial_haversine": {
        "label": "Mekânsal — enlem/boylam (Haversine)", "phase2_set": "A_dbscan_haversine_weighted",
        "features": ["lat_rad", "lon_rad"], "metric": "Haversine (büyük çember), eps metre → radyan",
        "level": "benzersiz konum + ağırlık (olay sayısı)", "kind": "spatial",
        "note": "Ağırlıklı DBSCAN kayıt düzeyiyle eşdeğerdir (Faz 3'te gerçek veride doğrulandı).",
    },
    "spatial_projected": {
        "label": "Mekânsal — UTM 18N metre (Öklid)", "phase2_set": "B_kmeans_projected(_weighted)",
        "features": ["x_m", "y_m"], "metric": "Öklid (EPSG:32618, metre)",
        "level": "K-Means: benzersiz konum + ağırlık; HDBSCAN: kayıt düzeyi", "kind": "spatial",
        "note": "Projeksiyonlu metre koordinatları; ham derece üzerinde Öklid kullanılmaz.",
    },
    "spatial_haversine_records": {
        "label": "Mekânsal — enlem/boylam, kayıt düzeyi (Haversine)", "phase2_set": "C_hdbscan_haversine",
        "features": ["lat_rad", "lon_rad"], "metric": "Haversine",
        "level": "kayıt düzeyi (HDBSCAN ağırlık desteklemez)", "kind": "spatial",
        "note": "scikit-learn HDBSCAN sample_weight desteklemez; olaylar tek tek girer.",
    },
    "spatiotemporal": {
        "label": "Uzay-zaman (deneysel)", "phase2_set": "D_spatiotemporal_experimental",
        "features": ["x_m", "y_m", "days_since_epoch"],
        "metric": "Ayrı eşikli komşuluk: mesafe ≤ eps_m VE |Δgün| ≤ eps_days (ST-DBSCAN)",
        "level": "kayıt düzeyi", "kind": "spatiotemporal",
        "note": "Faz 3'te çalıştırılmadı; Faz 2'de tanımlanan uzay-zaman stratejisinin uygulamasıdır. "
                "Kümeler 'aynı yerde VE aynı dönemde' tekrar eden kazalardır; mekânsal kümelerle doğrudan karşılaştırılamaz.",
    },
}

# Algoritma → izin verilen öznitelik setleri ve izin verilmeyenlerin gerekçesi
COMPATIBILITY: dict[str, dict[str, Any]] = {
    "dbscan": {"allowed": ["spatial_haversine", "spatiotemporal"],
               "reasons": {"spatial_projected": "Ana DBSCAN Haversine ile tanımlıdır; projeksiyonlu Öklid varyantı Faz 3 "
                                                "deney kaydında yok ve kayıtlı sonuçlarla karşılaştırılamaz.",
                           "spatial_haversine_records": "Kayıt düzeyi DBSCAN ağırlıklı sürümle aynı sonucu verir ancak "
                                                        "bellek maliyeti çok yüksektir; ağırlıklı sürüm kullanılır."}},
    "kmeans": {"allowed": ["spatial_projected"],
               "reasons": {"spatial_haversine": "K-Means ortalama alır; küresel açılar üzerinde ortalama/Öklid geçerli değildir.",
                           "spatial_haversine_records": "K-Means ortalama alır; küresel açılar üzerinde ortalama/Öklid geçerli değildir.",
                           "spatiotemporal": "K-Means metre ve gün eksenlerini tek Öklid uzayında karıştırır; ölçek "
                                             "seçimi keyfi olur. Desteklenmez."}},
    "hdbscan": {"allowed": ["spatial_projected", "spatial_haversine_records"],
                "reasons": {"spatial_haversine": "HDBSCAN sample_weight desteklemez; ağırlıklı benzersiz konum temsili "
                                                 "yoğunluğu bozar. Kayıt düzeyi Haversine seçin.",
                            "spatiotemporal": "HDBSCAN için uzay-zaman mesafe stratejisi tanımlanmadı."}},
}

PARAM_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "dbscan": {"eps_m": (5, 500), "min_samples": (2, 5000), "eps_days": (1, 365)},
    "kmeans": {"k": (2, 200), "n_init": (1, 20), "max_iter": (50, 1000), "random_state": (0, 2**31 - 1)},
    "hdbscan": {"min_cluster_size": (2, 5000), "min_samples": (1, 1000)},
}

# Kaynak bütçesi (etkileşimli kullanım; Faz 3 toplu deney sınırlarından daha sıkı)
BUDGET = {
    "max_neighbor_pairs": 120_000_000,     # ~0,9 GiB komşuluk indeksi
    "max_st_events": 300_000,              # uzay-zaman DBSCAN (kayıt düzeyi)
    "max_st_pairs": 40_000_000,
    "max_hdbscan_events": 100_000,         # Faz 3: 100k olay ≈ 69 sn
    "min_free_memory_mb": 1500,
    "timeout_s": 900,
    "metric_sample": 10_000,
}


@dataclass(frozen=True)
class LabRequest:
    algorithm: str
    feature_set: str
    params: dict[str, Any]
    filters: FilterSpec = field(default_factory=FilterSpec)
    sample: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm, "feature_set": self.feature_set, "params": self.params,
                "filters": self.filters.to_dict(), "sample": self.sample}

    def cache_key(self, dataset_version: str) -> str:
        blob = json.dumps({**self.to_dict(), "dataset_version": dataset_version, "code": LAB_CODE_VERSION},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _int(v: Any, name: str, algo: str) -> int:
    if isinstance(v, bool) or v is None:
        raise LabRequestError(f"{name} tamsayı olmalı")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise LabRequestError(f"{name} tamsayı olmalı: {v!r}") from None
    if f != int(f):
        raise LabRequestError(f"{name} tamsayı olmalı: {v!r}")
    lo, hi = PARAM_BOUNDS[algo][name]
    if not lo <= f <= hi:
        raise LabRequestError(f"{name} {int(lo)}–{int(hi)} aralığında olmalı: {v}")
    return int(f)


def _num(v: Any, name: str, algo: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise LabRequestError(f"{name} sayı olmalı: {v!r}") from None
    if f != f or f in (float("inf"), float("-inf")):
        raise LabRequestError(f"{name} sonlu olmalı")
    lo, hi = PARAM_BOUNDS[algo][name]
    if not lo <= f <= hi:
        raise LabRequestError(f"{name} {lo:g}–{hi:g} aralığında olmalı: {v}")
    return int(f) if f == int(f) else f


def validate_request(body: dict[str, Any], factors: set[str] | None = None) -> LabRequest:
    algo = str(body.get("algorithm", "")).lower()
    if algo not in COMPATIBILITY:
        raise LabRequestError("algorithm 'dbscan', 'kmeans' veya 'hdbscan' olmalı")
    fs = str(body.get("feature_set", ""))
    if fs not in FEATURE_SETS:
        raise LabRequestError(f"Bilinmeyen öznitelik seti: {fs!r}")
    comp = COMPATIBILITY[algo]
    if fs not in comp["allowed"]:
        raise LabRequestError(f"{algo.upper()} + '{FEATURE_SETS[fs]['label']}' desteklenmiyor: {comp['reasons'].get(fs, '')}")
    p = body.get("params") or {}
    unknown = set(p) - set(PARAM_BOUNDS[algo]) - {"cluster_selection_method"}
    if unknown:
        raise LabRequestError(f"{algo.upper()} için tanımsız parametre: {sorted(unknown)}")
    params: dict[str, Any]
    if algo == "dbscan":
        params = {"eps_m": _num(p.get("eps_m"), "eps_m", algo), "min_samples": _int(p.get("min_samples"), "min_samples", algo)}
        if fs == "spatiotemporal":
            params["eps_days"] = _int(p.get("eps_days"), "eps_days", algo)
        elif "eps_days" in p and p["eps_days"] is not None:
            raise LabRequestError("eps_days yalnızca uzay-zaman öznitelik setinde kullanılır")
    elif algo == "kmeans":
        params = {"k": _int(p.get("k"), "k", algo), "n_init": _int(p.get("n_init", 10), "n_init", algo),
                  "max_iter": _int(p.get("max_iter", 300), "max_iter", algo),
                  "random_state": _int(p.get("random_state", 42), "random_state", algo)}
    else:
        ms = p.get("min_samples")
        params = {"min_cluster_size": _int(p.get("min_cluster_size"), "min_cluster_size", algo),
                  "min_samples": None if ms in (None, "") else _int(ms, "min_samples", algo),
                  "cluster_selection_method": str(p.get("cluster_selection_method", "eom"))}
        if params["cluster_selection_method"] not in ("eom", "leaf"):
            raise LabRequestError("cluster_selection_method 'eom' veya 'leaf' olmalı")
    sample = body.get("sample")
    if sample:
        try:
            sample = {"n": int(sample["n"]), "seed": int(sample.get("seed", 42))}
        except (KeyError, TypeError, ValueError):
            raise LabRequestError("sample {n, seed} biçiminde olmalı") from None
        if not 1000 <= sample["n"] <= 2_100_000:
            raise LabRequestError("Örneklem boyutu 1.000–2.100.000 aralığında olmalı")
    filters = body.get("filters") or {}
    try:
        spec = filters if isinstance(filters, FilterSpec) else parse_filters(filters, factors)
    except ValueError as exc:
        raise LabRequestError(str(exc)) from None
    return LabRequest(algorithm=algo, feature_set=fs, params=params, filters=spec, sample=sample or None)


def capabilities() -> dict[str, Any]:
    return {"feature_sets": FEATURE_SETS, "compatibility": COMPATIBILITY, "bounds": PARAM_BOUNDS, "budget": BUDGET,
            "code_version": LAB_CODE_VERSION}
