"""Faz 3 yapılandırmasının (TOML) yüklenmesi ve doğrulanması."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from saferoute import config

# Faz 3 kodu değiştiğinde artırılır; deney kimliğine ve kayıtlara girer.
CLUSTERING_CODE_VERSION = "3.0.0"
DEFAULT_CONFIG = config.REPO_ROOT / "backend" / "configs" / "phase3.toml"


class ConfigError(ValueError):
    """Yapılandırma eksik veya geçersizse fırlatılır."""


REQUIRED = {
    "meta": ["random_seed"], "resources": ["max_neighbor_pairs"], "dbscan": ["eps_m", "min_samples"],
    "kmeans": ["k", "n_init"], "hdbscan": ["sample_events", "min_cluster_size", "min_samples"],
    "evaluation": ["silhouette_sample", "dbcv_sample"], "selection": ["max_largest_cluster_share", "min_clusters"],
    "temporal": ["years", "grid_cell_m"], "sensitivity": ["variants"],
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or DEFAULT_CONFIG)
    raw = path.read_bytes()
    cfg = tomllib.loads(raw.decode("utf-8"))
    for section, keys in REQUIRED.items():
        if section not in cfg:
            raise ConfigError(f"Eksik bölüm: [{section}]")
        for k in keys:
            if k not in cfg[section]:
                raise ConfigError(f"Eksik anahtar: [{section}].{k}")
    for eps in cfg["dbscan"]["eps_m"]:
        if not (isinstance(eps, (int, float)) and eps > 0):
            raise ConfigError(f"Geçersiz eps_m: {eps}")
    for ms in cfg["dbscan"]["min_samples"] + cfg["hdbscan"]["min_samples"]:
        if not (isinstance(ms, int) and ms >= 1):
            raise ConfigError(f"Geçersiz min_samples: {ms}")
    for k in cfg["kmeans"]["k"]:
        if not (isinstance(k, int) and k >= 2):
            raise ConfigError(f"Geçersiz k: {k}")
    for m in cfg["hdbscan"]["min_cluster_size"]:
        if not (isinstance(m, int) and m >= 2):
            raise ConfigError(f"Geçersiz min_cluster_size: {m}")
    cfg["_path"] = str(path)
    cfg["_sha256"] = hashlib.sha256(raw).hexdigest()
    return cfg


def stable_hash(obj: Any, n: int = 12) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:n]
